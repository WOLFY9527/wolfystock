# -*- coding: utf-8 -*-
"""Portfolio broker file import service with extensible parser registry."""

from __future__ import annotations

import hashlib
import io
import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

import pandas as pd

from src.repositories.portfolio_repo import PortfolioRepository
from src.services.portfolio_ibkr_currency import (
    IbkrCurrencyClassification,
    IbkrCurrencyStatus,
    classify_ibkr_currency,
)
from src.services.portfolio_service import (
    PortfolioBusyError,
    PortfolioConflictError,
    PortfolioOversellError,
    PortfolioService,
)
from src.utils.symbol_normalization import canonical_stock_code

logger = logging.getLogger(__name__)

IBKR_BROKER = "ibkr"
IBKR_BROKER_ALIASES: Tuple[str, ...] = (
    "interactivebrokers",
    "interactive_brokers",
    "interactive-brokers",
)
IBKR_FILE_EXTENSIONS: Tuple[str, ...] = ("xml",)
CSV_FILE_EXTENSIONS: Tuple[str, ...] = ("csv",)


class PortfolioIbkrImportError(ValueError):
    """Structured IBKR import rejection raised before persistence starts."""

    def __init__(self, *, code: str, message: str, issues: List[Dict[str, Any]]) -> None:
        self.code = str(code)
        self.issues = list(issues)
        super().__init__(f"{self.code}: {message}")


@dataclass(frozen=True)
class CsvParserSpec:
    """CSV parser specification for one broker."""

    broker: str
    aliases: Tuple[str, ...]
    display_name: str
    column_hints: Dict[str, Tuple[str, ...]]


DEFAULT_PARSER_SPECS: Tuple[CsvParserSpec, ...] = (
    CsvParserSpec(
        broker="huatai",
        aliases=(),
        display_name="华泰",
        column_hints={
            "trade_date": ("成交日期", "成交时间", "发生日期", "日期"),
            "symbol": ("证券代码", "股票代码", "代码"),
            "side": ("买卖标志", "买卖方向", "操作"),
            "quantity": ("成交数量", "数量", "成交股数"),
            "price": ("成交均价", "成交价格", "价格", "成交价", "均价"),
            "trade_uid": ("成交编号", "成交序号", "流水号"),
        },
    ),
    CsvParserSpec(
        broker="citic",
        aliases=("zhongxin",),
        display_name="中信",
        column_hints={
            "trade_date": ("发生日期", "成交日期", "日期"),
            "symbol": ("证券代码", "股票代码", "代码"),
            "side": ("买卖方向", "买卖标志", "业务名称"),
            "quantity": ("成交数量", "数量", "成交股数"),
            "price": ("成交价格", "成交均价", "价格", "成交价"),
            "trade_uid": ("合同编号", "成交编号", "委托编号"),
        },
    ),
    CsvParserSpec(
        broker="cmb",
        aliases=("zhaoshang", "cmbchina"),
        display_name="招商",
        column_hints={
            "trade_date": ("日期", "成交日期", "发生日期"),
            "symbol": ("证券代码", "股票代码", "代码"),
            "side": ("交易方向", "买卖方向", "买卖标志"),
            "quantity": ("成交股数", "成交数量", "数量"),
            "price": ("成交价", "成交价格", "成交均价", "均价"),
            "trade_uid": ("流水号", "成交编号", "成交序号"),
        },
    ),
)


class PortfolioImportService:
    """Parse broker CSV and commit normalized trade records with dedup."""
    _shared_parser_registry: Dict[str, CsvParserSpec] = {}
    _shared_broker_alias_map: Dict[str, str] = {}
    _shared_registry_initialized: bool = False

    def __init__(
        self,
        *,
        portfolio_service: Optional[PortfolioService] = None,
        repo: Optional[PortfolioRepository] = None,
    ):
        self.portfolio_service = portfolio_service or PortfolioService()
        self.repo = repo or PortfolioRepository()
        self._parser_registry = self.__class__._shared_parser_registry
        self._broker_alias_map = self.__class__._shared_broker_alias_map
        if not self.__class__._shared_registry_initialized:
            self._init_default_parsers()
            self.__class__._shared_registry_initialized = True

    def _init_default_parsers(self) -> None:
        for spec in DEFAULT_PARSER_SPECS:
            self.register_parser(spec)

    def register_parser(self, spec: CsvParserSpec) -> None:
        """Register or replace one broker parser spec."""
        broker = (spec.broker or "").strip().lower()
        if not broker:
            raise ValueError("broker is required")
        new_aliases = tuple(sorted({alias.strip().lower() for alias in spec.aliases if alias}))
        for alias in new_aliases:
            if alias == broker:
                raise ValueError(f"alias '{alias}' cannot be the same as broker id")
            existing_target = self._broker_alias_map.get(alias)
            if existing_target and existing_target != broker:
                raise ValueError(
                    f"alias '{alias}' already registered by broker '{existing_target}'"
                )
        for alias, target in list(self._broker_alias_map.items()):
            if target == broker and alias not in new_aliases:
                self._broker_alias_map.pop(alias, None)
        self._parser_registry[broker] = CsvParserSpec(
            broker=broker,
            aliases=new_aliases,
            display_name=spec.display_name or broker,
            column_hints=dict(spec.column_hints or {}),
        )
        for alias in self._parser_registry[broker].aliases:
            self._broker_alias_map[alias] = broker

    def list_supported_csv_brokers(self) -> List[Dict[str, Any]]:
        """List CSV-backed broker parsers for the legacy import surface."""
        items: List[Dict[str, Any]] = []
        for broker in sorted(self._parser_registry.keys()):
            aliases = sorted(alias for alias, target in self._broker_alias_map.items() if target == broker)
            items.append(
                {
                    "broker": broker,
                    "aliases": aliases,
                    "display_name": self._parser_registry[broker].display_name,
                    "file_extensions": list(CSV_FILE_EXTENSIONS),
                }
            )
        return items

    def list_supported_brokers(self) -> List[Dict[str, Any]]:
        """List canonical broker ids and file capabilities for the frontend selector."""
        items = self.list_supported_csv_brokers()
        items.append(
            {
                "broker": IBKR_BROKER,
                "aliases": list(IBKR_BROKER_ALIASES),
                "display_name": "Interactive Brokers",
                "file_extensions": list(IBKR_FILE_EXTENSIONS),
            }
        )
        return items

    def parse_import_file(
        self,
        *,
        broker: str,
        content: bytes,
    ) -> Dict[str, Any]:
        broker_norm = self._normalize_broker(broker)
        if broker_norm == IBKR_BROKER:
            return self.parse_ibkr_flex_report(content=content)
        return self.parse_trade_csv(broker=broker_norm, content=content)

    def commit_import_records(
        self,
        *,
        account_id: int,
        broker: str,
        parsed_payload: Dict[str, Any],
        dry_run: bool = False,
        broker_connection_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        broker_norm = self._normalize_broker(broker)
        if broker_norm != IBKR_BROKER:
            account = self._require_import_account(account_id)
            base = self.commit_trade_records(
                account_id=account_id,
                broker=broker_norm,
                records=list(parsed_payload.get("records", [])),
                dry_run=dry_run,
            )
            base.setdefault("cash_record_count", 0)
            base.setdefault("cash_inserted_count", 0)
            base.setdefault("cash_failed_count", 0)
            base.setdefault("corporate_action_count", 0)
            base.setdefault("corporate_action_inserted_count", 0)
            base.setdefault("corporate_action_failed_count", 0)
            base.setdefault("duplicate_import", False)
            base.setdefault("broker_connection_id", broker_connection_id)
            base.setdefault("warnings", list(parsed_payload.get("warnings", [])))
            base.setdefault("metadata", dict(parsed_payload.get("metadata", {})))
            self._attach_import_preview_contract(
                base,
                account=account,
                broker=broker_norm,
                parsed_payload=parsed_payload,
                broker_connection_id=broker_connection_id,
            )
            return base
        return self._commit_ibkr_import(
            account_id=account_id,
            parsed_payload=parsed_payload,
            dry_run=dry_run,
            broker_connection_id=broker_connection_id,
        )

    def _require_import_account(self, account_id: int) -> Dict[str, Any]:
        account = self.portfolio_service.get_account(account_id, include_inactive=True)
        if account is None:
            raise ValueError(f"Account not found: {account_id}")
        return account

    def _attach_import_preview_contract(
        self,
        result: Dict[str, Any],
        *,
        account: Dict[str, Any],
        broker: str,
        parsed_payload: Dict[str, Any],
        broker_connection_id: Optional[int],
    ) -> None:
        trade_records = list(parsed_payload.get("records", []))
        cash_entries = list(parsed_payload.get("cash_entries", []))
        inserted = int(result.get("inserted_count", 0) or 0)
        inserted += int(result.get("cash_inserted_count", 0) or 0)
        inserted += int(result.get("corporate_action_inserted_count", 0) or 0)
        rejected = int(result.get("failed_count", 0) or 0)
        rejected += int(parsed_payload.get("skipped_count", 0) or 0)
        rejected += int(parsed_payload.get("error_count", 0) or 0)
        duplicate_count = int(result.get("duplicate_count", 0) or 0)
        metadata = dict(parsed_payload.get("metadata", {}))
        base_currency = str(account.get("base_currency") or "").upper()
        connection_id = (
            broker_connection_id
            or result.get("broker_connection_id")
            or metadata.get("existing_connection_id")
        )
        will_create_connection = (
            broker == IBKR_BROKER
            and not connection_id
            and bool(str(metadata.get("broker_account_ref") or "").strip())
        )

        result["accepted_count"] = inserted
        result["rejected_count"] = rejected
        result["preview_only"] = bool(result.get("dry_run"))
        result["requires_confirmation"] = bool(result.get("dry_run")) and inserted > 0
        result["duplicate_candidates"] = (
            [
                {
                    "count": duplicate_count,
                    "reason": "existing_or_repeated_logical_record",
                    "recovery_action": "Remove duplicate records or leave them to be skipped.",
                }
            ]
            if duplicate_count
            else []
        )
        result["unknown_symbols"] = [
            {
                "row": item.get("_source_line_number") or item.get("source_line_number"),
                "symbol": item.get("symbol"),
                "reason": "market_unresolved",
                "recovery_action": "Confirm symbol market before import confirmation.",
            }
            for item in trade_records
            if item.get("symbol") and not item.get("market")
        ][:20]
        result["currency_issues"] = [
            *list(parsed_payload.get("currency_issues", [])),
            *[
                {
                    "scope": "trade",
                    "row": item.get("_source_line_number") or item.get("source_line_number"),
                    "symbol": item.get("symbol"),
                    "currency": item.get("currency"),
                    "account_base_currency": base_currency,
                    "reason": "currency_missing" if not item.get("currency") else "cross_currency_record",
                    "fatal": not bool(item.get("currency")),
                    "recovery_action": "Confirm settlement currency and FX availability.",
                }
                for item in trade_records
                if not item.get("currency")
                or (base_currency and str(item.get("currency") or "").upper() != base_currency)
            ],
            *[
                {
                    "scope": "cash",
                    "row": None,
                    "currency": item.get("currency"),
                    "account_base_currency": base_currency,
                    "reason": "cash_currency_missing" if not item.get("currency") else "cross_currency_cash",
                    "fatal": not bool(item.get("currency")),
                    "recovery_action": "Confirm cash currency and FX availability.",
                }
                for item in cash_entries
                if not item.get("currency")
                or (base_currency and str(item.get("currency") or "").upper() != base_currency)
            ],
        ][:20]
        has_fatal_currency_issue = any(
            item.get("fatal") for item in result["currency_issues"]
        )
        result["requires_confirmation"] = (
            bool(result.get("requires_confirmation")) and not has_fatal_currency_issue
        )
        result["account_mapping"] = {
            "account_id": account.get("id"),
            "account_name": account.get("name"),
            "account_base_currency": base_currency,
            "broker": broker,
            "broker_connection_id": connection_id,
            "status": (
                "existing_connection"
                if connection_id
                else "will_create_on_confirm"
                if will_create_connection
                else "selected_account"
            ),
        }
        result["validation_checks"] = [
            {
                "check": "date_quantity_price",
                "accepted_rows": len(trade_records),
                "rejected_rows": rejected,
            },
            {"check": "account_mapping", "status": result["account_mapping"]["status"]},
            {"check": "duplicate_detection", "duplicate_candidates": duplicate_count},
            {"check": "currency_review", "issue_count": len(result["currency_issues"])},
        ]
        recovery_actions: List[str] = []
        if rejected:
            recovery_actions.append("Fix rejected rows and retry preview before confirming.")
        if duplicate_count:
            recovery_actions.append("Review duplicate candidates before confirming.")
        if result["currency_issues"]:
            recovery_actions.append("Review currency and FX availability before confirming.")
        if result["unknown_symbols"]:
            recovery_actions.append("Confirm symbol market mapping before confirming.")
        result["recovery_actions"] = recovery_actions

    def parse_trade_csv(
        self,
        *,
        broker: str,
        content: bytes,
    ) -> Dict[str, Any]:
        broker_norm = self._normalize_broker(broker)
        parser_spec = self._parser_registry[broker_norm]
        df = self._read_csv(content)

        records: List[Dict[str, Any]] = []
        skipped = 0
        errors: List[str] = []

        for idx, row in df.iterrows():
            normalized = self._normalize_trade_row(row=row, parser_spec=parser_spec)
            if normalized is None:
                skipped += 1
                continue
            try:
                # Keep a stable line-level marker so repeated imports of the same
                # file remain idempotent, while identical split fills on separate
                # CSV lines do not collapse into one dedup key.
                normalized["_source_line_number"] = int(idx) + 2
                normalized["dedup_hash"] = self._build_dedup_hash(normalized)
                records.append(normalized)
            except Exception as exc:  # pragma: no cover - defensive path
                skipped += 1
                errors.append(f"row={idx + 1}: {exc}")

        return {
            "broker": broker_norm,
            "record_count": len(records),
            "skipped_count": skipped,
            "error_count": len(errors),
            "records": records,
            "cash_record_count": 0,
            "cash_entries": [],
            "corporate_action_count": 0,
            "corporate_actions": [],
            "warnings": [],
            "metadata": {
                "file_format": "broker_csv",
                "file_fingerprint": self._fingerprint_bytes(content),
            },
            "errors": errors[:20],
        }

    def commit_trade_records(
        self,
        *,
        account_id: int,
        broker: str,
        records: List[Dict[str, Any]],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        broker_norm = self._normalize_broker(broker)

        inserted_count = 0
        duplicate_count = 0
        failed_count = 0
        errors: List[str] = []
        seen_trade_uids: set[str] = set()
        seen_dedup_hashes: set[str] = set()

        for i, record in enumerate(records):
            try:
                trade_uid = (record.get("trade_uid") or "").strip() or None
                dedup_hash = (record.get("dedup_hash") or "").strip()
                if not dedup_hash:
                    dedup_hash = self._build_dedup_hash(record)

                if trade_uid and self.repo.has_trade_uid(account_id, trade_uid):
                    duplicate_count += 1
                    continue
                dedup_hash_to_use: Optional[str] = dedup_hash or None
                if dedup_hash_to_use and self.repo.has_trade_dedup_hash(account_id, dedup_hash_to_use):
                    duplicate_count += 1
                    continue

                if dry_run:
                    if trade_uid and trade_uid in seen_trade_uids:
                        duplicate_count += 1
                        continue
                    if dedup_hash_to_use and dedup_hash_to_use in seen_dedup_hashes:
                        duplicate_count += 1
                        continue
                    inserted_count += 1
                    if trade_uid:
                        seen_trade_uids.add(trade_uid)
                    if dedup_hash_to_use:
                        seen_dedup_hashes.add(dedup_hash_to_use)
                    continue

                trade_date_value = record.get("trade_date")
                if isinstance(trade_date_value, date):
                    trade_date_obj = trade_date_value
                else:
                    trade_date_obj = date.fromisoformat(str(trade_date_value))

                self.portfolio_service.record_trade(
                    account_id=account_id,
                    symbol=str(record["symbol"]),
                    trade_date=trade_date_obj,
                    side=str(record["side"]),
                    quantity=float(record["quantity"]),
                    price=float(record["price"]),
                    fee=float(record.get("fee", 0.0) or 0.0),
                    tax=float(record.get("tax", 0.0) or 0.0),
                    market=record.get("market"),
                    currency=record.get("currency"),
                    trade_uid=trade_uid,
                    dedup_hash=dedup_hash_to_use,
                    note=(record.get("note") or "").strip() or f"csv_import:{broker_norm}",
                )
                inserted_count += 1
            except PortfolioConflictError:
                duplicate_count += 1
            except PortfolioOversellError as exc:
                failed_count += 1
                errors.append(f"idx={i}: {exc}")
            except PortfolioBusyError as exc:
                failed_count += 1
                errors.append(f"idx={i}: portfolio_busy: {exc}")
            except Exception as exc:
                failed_count += 1
                errors.append(f"idx={i}: {exc}")

        return {
            "account_id": account_id,
            "record_count": len(records),
            "inserted_count": inserted_count,
            "duplicate_count": duplicate_count,
            "failed_count": failed_count,
            "dry_run": bool(dry_run),
            "errors": errors[:20],
        }

    def _commit_ibkr_import(
        self,
        *,
        account_id: int,
        parsed_payload: Dict[str, Any],
        dry_run: bool,
        broker_connection_id: Optional[int],
    ) -> Dict[str, Any]:
        trade_records = list(parsed_payload.get("records", []))
        cash_entries = list(parsed_payload.get("cash_entries", []))
        corporate_actions = list(parsed_payload.get("corporate_actions", []))
        warnings = list(parsed_payload.get("warnings", []))
        metadata = dict(parsed_payload.get("metadata", {}))
        account = self._require_import_account(account_id)

        currency_issues = self._collect_ibkr_commit_currency_issues(
            account=account,
            parsed_payload=parsed_payload,
            trade_records=trade_records,
            cash_entries=cash_entries,
            corporate_actions=corporate_actions,
        )
        preview_payload = dict(parsed_payload)
        preview_payload["currency_issues"] = currency_issues
        fatal_currency_issues = [item for item in currency_issues if item.get("fatal")]
        if fatal_currency_issues and not dry_run:
            code = (
                "ibkr_fx_unavailable"
                if all(item.get("reason") == "currency_operationally_unsupported" for item in fatal_currency_issues)
                else "ibkr_currency_invalid"
            )
            raise PortfolioIbkrImportError(
                code=code,
                message="IBKR Flex currency validation failed before persistence.",
                issues=fatal_currency_issues,
            )

        connection = self._resolve_import_broker_connection(
            account_id=account_id,
            broker_connection_id=broker_connection_id,
            broker=IBKR_BROKER,
            parsed_payload=parsed_payload,
            dry_run=dry_run,
        )

        fingerprint = str(metadata.get("file_fingerprint") or "").strip() or None
        if (
            not dry_run
            and connection is not None
            and fingerprint
            and str(connection.get("last_import_fingerprint") or "").strip() == fingerprint
        ):
            result = {
                "account_id": account_id,
                "record_count": len(trade_records),
                "inserted_count": 0,
                "duplicate_count": 0,
                "failed_count": 0,
                "cash_record_count": len(cash_entries),
                "cash_inserted_count": 0,
                "cash_failed_count": 0,
                "corporate_action_count": len(corporate_actions),
                "corporate_action_inserted_count": 0,
                "corporate_action_failed_count": 0,
                "dry_run": False,
                "duplicate_import": True,
                "broker_connection_id": connection.get("id"),
                "warnings": warnings,
                "metadata": metadata,
                "errors": [],
            }
            self._attach_import_preview_contract(
                result,
                account=account,
                broker=IBKR_BROKER,
                parsed_payload=preview_payload,
                broker_connection_id=broker_connection_id,
            )
            return result

        self._maybe_upgrade_account_market_for_ibkr(
            account_id=account_id,
            trade_records=trade_records,
            corporate_actions=corporate_actions,
            dry_run=dry_run,
        )

        trade_result = self.commit_trade_records(
            account_id=account_id,
            broker=IBKR_BROKER,
            records=trade_records,
            dry_run=dry_run,
        )
        cash_inserted_count, cash_failed_count, cash_errors = self._commit_cash_entries(
            account_id=account_id,
            entries=cash_entries,
            dry_run=dry_run,
        )
        corp_inserted_count, corp_failed_count, corp_errors = self._commit_corporate_actions(
            account_id=account_id,
            actions=corporate_actions,
            dry_run=dry_run,
        )

        combined_errors = list(trade_result.get("errors", [])) + cash_errors + corp_errors

        if not dry_run and connection is not None and not combined_errors:
            updated = self.portfolio_service.mark_broker_connection_imported(
                int(connection["id"]),
                import_source="ibkr_flex_xml",
                import_fingerprint=fingerprint,
                sync_metadata={
                    "last_statement_from": metadata.get("statement_from"),
                    "last_statement_to": metadata.get("statement_to"),
                    "base_currency": metadata.get("base_currency"),
                    "last_file_format": metadata.get("file_format"),
                },
            )
            if updated is not None:
                connection = updated

        result = {
            "account_id": account_id,
            "record_count": len(trade_records),
            "inserted_count": int(trade_result.get("inserted_count", 0)),
            "duplicate_count": int(trade_result.get("duplicate_count", 0)),
            "failed_count": int(trade_result.get("failed_count", 0)) + cash_failed_count + corp_failed_count,
            "cash_record_count": len(cash_entries),
            "cash_inserted_count": cash_inserted_count,
            "cash_failed_count": cash_failed_count,
            "corporate_action_count": len(corporate_actions),
            "corporate_action_inserted_count": corp_inserted_count,
            "corporate_action_failed_count": corp_failed_count,
            "dry_run": bool(dry_run),
            "duplicate_import": False,
            "broker_connection_id": connection.get("id") if connection else None,
            "warnings": warnings,
            "metadata": metadata,
            "errors": combined_errors[:20],
        }
        self._attach_import_preview_contract(
            result,
            account=account,
            broker=IBKR_BROKER,
            parsed_payload=preview_payload,
            broker_connection_id=broker_connection_id,
        )
        return result

    def _maybe_upgrade_account_market_for_ibkr(
        self,
        *,
        account_id: int,
        trade_records: List[Dict[str, Any]],
        corporate_actions: List[Dict[str, Any]],
        dry_run: bool,
    ) -> None:
        if dry_run:
            return
        markets = {
            str(item.get("market") or "").strip().lower()
            for item in [*trade_records, *corporate_actions]
            if str(item.get("market") or "").strip()
        }
        if len(markets) <= 1:
            return
        account = self.portfolio_service.get_account(account_id, include_inactive=True)
        if account is None:
            return
        if str(account.get("market") or "").strip().lower() == "global":
            return
        self.portfolio_service.update_account(account_id, market="global")

    def _resolve_import_broker_connection(
        self,
        *,
        account_id: int,
        broker_connection_id: Optional[int],
        broker: str,
        parsed_payload: Dict[str, Any],
        dry_run: bool = False,
    ) -> Optional[Dict[str, Any]]:
        metadata = dict(parsed_payload.get("metadata", {}))
        broker_account_ref = str(metadata.get("broker_account_ref") or "").strip() or None
        if broker_connection_id is not None:
            connection = self.portfolio_service.get_broker_connection(int(broker_connection_id))
            if connection is None:
                raise ValueError(f"Broker connection not found: {broker_connection_id}")
            if int(connection["portfolio_account_id"]) != int(account_id):
                raise ValueError("broker_connection_id must belong to the selected portfolio account")
            return connection
        if not broker_account_ref:
            return None
        existing = self.portfolio_service.get_broker_connection_by_ref(
            broker_type=broker,
            broker_account_ref=broker_account_ref,
        )
        if existing is not None:
            if int(existing["portfolio_account_id"]) != int(account_id):
                raise ValueError(
                    "Detected broker_account_ref is already linked to a different portfolio account"
                )
            return existing
        if dry_run:
            return None
        return self.portfolio_service.create_broker_connection(
            portfolio_account_id=account_id,
            broker_type=broker,
            broker_name="Interactive Brokers",
            connection_name=str(
                metadata.get("suggested_connection_name") or f"IBKR {broker_account_ref}"
            )[:64],
            broker_account_ref=broker_account_ref,
            import_mode="file",
            sync_metadata={
                "base_currency": metadata.get("base_currency"),
                "statement_from": metadata.get("statement_from"),
                "statement_to": metadata.get("statement_to"),
            },
        )

    def _commit_cash_entries(
        self,
        *,
        account_id: int,
        entries: List[Dict[str, Any]],
        dry_run: bool,
    ) -> Tuple[int, int, List[str]]:
        inserted_count = 0
        failed_count = 0
        errors: List[str] = []
        seen_keys: set[Tuple[str, str, str, str, str]] = set()
        for idx, entry in enumerate(entries):
            event_date_value = entry.get("event_date")
            if isinstance(event_date_value, date):
                event_date_obj = event_date_value
            else:
                event_date_obj = self._parse_date(event_date_value)
            if event_date_obj is None:
                failed_count += 1
                errors.append(f"cash_idx={idx}: missing event_date")
                continue
            key = (
                event_date_obj.isoformat(),
                str(entry.get("direction") or ""),
                f"{float(entry.get('amount', 0.0)):.8f}",
                str(entry.get("currency") or ""),
                str(entry.get("note") or ""),
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if dry_run:
                inserted_count += 1
                continue
            try:
                self.portfolio_service.record_cash_ledger(
                    account_id=account_id,
                    event_date=event_date_obj,
                    direction=str(entry["direction"]),
                    amount=abs(float(entry["amount"])),
                    currency=entry.get("currency"),
                    note=(entry.get("note") or "").strip() or "ibkr_flex_cash",
                )
                inserted_count += 1
            except Exception as exc:
                failed_count += 1
                errors.append(f"cash_idx={idx}: {exc}")
        return inserted_count, failed_count, errors

    def _commit_corporate_actions(
        self,
        *,
        account_id: int,
        actions: List[Dict[str, Any]],
        dry_run: bool,
    ) -> Tuple[int, int, List[str]]:
        inserted_count = 0
        failed_count = 0
        errors: List[str] = []
        seen_keys: set[Tuple[str, str, str, str, str]] = set()
        for idx, action in enumerate(actions):
            effective_date_value = action.get("effective_date")
            if isinstance(effective_date_value, date):
                effective_date_obj = effective_date_value
            else:
                effective_date_obj = self._parse_date(effective_date_value)
            if effective_date_obj is None:
                failed_count += 1
                errors.append(f"corp_idx={idx}: missing effective_date")
                continue
            key = (
                effective_date_obj.isoformat(),
                str(action.get("symbol") or ""),
                str(action.get("action_type") or ""),
                str(action.get("market") or ""),
                str(action.get("currency") or ""),
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if dry_run:
                inserted_count += 1
                continue
            try:
                self.portfolio_service.record_corporate_action(
                    account_id=account_id,
                    symbol=str(action["symbol"]),
                    effective_date=effective_date_obj,
                    action_type=str(action["action_type"]),
                    market=action.get("market"),
                    currency=action.get("currency"),
                    cash_dividend_per_share=action.get("cash_dividend_per_share"),
                    split_ratio=action.get("split_ratio"),
                    note=(action.get("note") or "").strip() or "ibkr_flex_corporate_action",
                )
                inserted_count += 1
            except Exception as exc:
                failed_count += 1
                errors.append(f"corp_idx={idx}: {exc}")
        return inserted_count, failed_count, errors

    def parse_ibkr_flex_report(self, *, content: bytes) -> Dict[str, Any]:
        fingerprint = self._fingerprint_bytes(content)
        root = self._parse_xml_root(content)
        statement = self._find_first_by_local_name(root, "FlexStatement")
        if statement is None:
            raise ValueError("Unsupported IBKR Flex XML: FlexStatement node not found")

        broker_account_ref = self._pick_attr(statement, "accountId", "account", "accountNumber")
        raw_base_currency = self._pick_attr(statement, "currency", "baseCurrency", "baseCurrencyCode")
        base_classification = classify_ibkr_currency(raw_base_currency)
        base_currency = (
            base_classification.code
            if base_classification.status == IbkrCurrencyStatus.VALID
            else None
        )
        currency_issues: List[Dict[str, Any]] = []
        if base_classification.status != IbkrCurrencyStatus.VALID:
            currency_issues.append(
                self._ibkr_currency_issue(
                    scope="statement",
                    classification=base_classification,
                    fatal=False,
                )
            )
        statement_from = self._normalize_optional_date(
            self._pick_attr(statement, "fromDate", "periodStart", "startDate")
        )
        statement_to = self._normalize_optional_date(
            self._pick_attr(statement, "toDate", "periodEnd", "endDate")
        )

        trade_records, trade_skipped, trade_errors = self._parse_ibkr_trade_records(statement)
        cash_entries, cash_skipped, cash_errors = self._parse_ibkr_cash_entries(statement)
        corporate_actions, corp_skipped, corp_errors = self._parse_ibkr_corporate_actions(statement)
        warnings: List[str] = []

        open_position_records: List[Dict[str, Any]] = []
        ignored_open_position_records: List[Dict[str, Any]] = []
        open_position_count = 0
        if not trade_records:
            open_position_records, open_position_count, position_warnings = self._parse_ibkr_open_position_seed_records(
                statement,
                statement_to=statement_to,
                broker_account_ref=broker_account_ref,
            )
            trade_records.extend(open_position_records)
            warnings.extend(position_warnings)
        else:
            ignored_open_position_records, open_position_count, position_warnings = self._parse_ibkr_open_position_seed_records(
                statement,
                statement_to=statement_to,
                broker_account_ref=broker_account_ref,
            )
            if open_position_count > 0:
                warnings.append(
                    "Open positions were detected but ignored because executable trades are already present in this import."
                )
            warnings.extend(position_warnings)

        trade_records, trade_currency_issues = self._filter_ibkr_currency_records(
            trade_records,
            scope="trade",
        )
        cash_entries, cash_currency_issues = self._filter_ibkr_currency_records(
            cash_entries,
            scope="cash",
        )
        corporate_actions, corp_currency_issues = self._filter_ibkr_currency_records(
            corporate_actions,
            scope="corporate_action",
        )
        _, ignored_open_position_currency_issues = self._filter_ibkr_currency_records(
            ignored_open_position_records,
            scope="open_position",
        )
        record_currency_issues = [
            *trade_currency_issues,
            *cash_currency_issues,
            *corp_currency_issues,
            *ignored_open_position_currency_issues,
        ]
        currency_issues.extend(record_currency_issues)

        errors = trade_errors + cash_errors + corp_errors + [
            f"ibkr_currency_invalid: {item['scope']} row={item.get('row')} reason={item['reason']}"
            for item in record_currency_issues
        ]
        skipped_count = trade_skipped + cash_skipped + corp_skipped + len(record_currency_issues)
        suggested_connection_name = (
            f"IBKR {broker_account_ref}"[:64]
            if broker_account_ref
            else "Interactive Brokers"
        )
        existing_connection_id: Optional[int] = None
        existing_connection_name: Optional[str] = None
        if broker_account_ref:
            existing_connection = self.portfolio_service.get_broker_connection_by_ref(
                broker_type=IBKR_BROKER,
                broker_account_ref=broker_account_ref,
            )
            if existing_connection is not None:
                existing_connection_id = int(existing_connection["id"])
                existing_connection_name = str(existing_connection["connection_name"])

        return {
            "broker": IBKR_BROKER,
            "record_count": len(trade_records),
            "skipped_count": skipped_count,
            "error_count": len(errors),
            "records": trade_records,
            "cash_record_count": len(cash_entries),
            "cash_entries": cash_entries,
            "corporate_action_count": len(corporate_actions),
            "corporate_actions": corporate_actions,
            "currency_issues": currency_issues,
            "warnings": warnings[:20],
            "metadata": {
                "file_format": "ibkr_flex_xml",
                "file_fingerprint": fingerprint,
                "broker_account_ref": broker_account_ref,
                "base_currency": base_currency,
                "statement_from": statement_from,
                "statement_to": statement_to,
                "suggested_connection_name": suggested_connection_name,
                "existing_connection_id": existing_connection_id,
                "existing_connection_name": existing_connection_name,
                "open_position_count": open_position_count,
                "open_position_seeded": bool(open_position_records),
            },
            "errors": errors[:20],
        }

    @staticmethod
    def _ibkr_currency_issue(
        *,
        scope: str,
        classification: IbkrCurrencyClassification,
        fatal: bool,
        row: Optional[int] = None,
        account_base_currency: Optional[str] = None,
    ) -> Dict[str, Any]:
        reason = f"currency_{classification.status.value}"
        return {
            "scope": scope,
            "row": row,
            "currency": classification.code,
            "account_base_currency": account_base_currency,
            "reason": reason,
            "fatal": bool(fatal),
            "recovery_action": "Provide an explicit canonical currency and required direct/inverse FX evidence.",
        }

    def _filter_ibkr_currency_records(
        self,
        records: List[Dict[str, Any]],
        *,
        scope: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        accepted: List[Dict[str, Any]] = []
        issues: List[Dict[str, Any]] = []
        for index, item in enumerate(records):
            classification = classify_ibkr_currency(item.get("currency"))
            issue_scope = str(item.get("_ibkr_currency_scope") or scope)
            if classification.status != IbkrCurrencyStatus.VALID or not classification.code:
                issues.append(
                    self._ibkr_currency_issue(
                        scope=issue_scope,
                        classification=classification,
                        fatal=True,
                        row=item.get("_source_line_number") or index + 1,
                    )
                )
                continue
            normalized = dict(item)
            normalized["currency"] = classification.code
            if scope == "trade":
                normalized["dedup_hash"] = self._build_dedup_hash(normalized)
            accepted.append(normalized)
        return accepted, issues

    def _collect_ibkr_commit_currency_issues(
        self,
        *,
        account: Dict[str, Any],
        parsed_payload: Dict[str, Any],
        trade_records: List[Dict[str, Any]],
        cash_entries: List[Dict[str, Any]],
        corporate_actions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        issues = [dict(item) for item in list(parsed_payload.get("currency_issues", []))]
        account_classification = classify_ibkr_currency(account.get("base_currency"))
        if account_classification.status != IbkrCurrencyStatus.VALID or not account_classification.code:
            issues.append(
                self._ibkr_currency_issue(
                    scope="account",
                    classification=account_classification,
                    fatal=True,
                )
            )
            return self._dedupe_ibkr_currency_issues(issues)
        account_base = account_classification.code

        metadata = dict(parsed_payload.get("metadata", {}))
        statement_classification = classify_ibkr_currency(metadata.get("base_currency"))
        if statement_classification.status == IbkrCurrencyStatus.VALID and statement_classification.code:
            statement_date = self._parse_date(metadata.get("statement_to")) or date.today()
            if not self._has_required_ibkr_fx(
                currency=statement_classification.code,
                account_base=account_base,
                as_of_date=statement_date,
            ):
                issues.append(
                    self._ibkr_currency_issue(
                        scope="statement",
                        classification=classify_ibkr_currency(
                            statement_classification.code,
                            operationally_supported=False,
                        ),
                        fatal=False,
                        account_base_currency=account_base,
                    )
                )

        record_groups = (
            ("trade", trade_records, "trade_date"),
            ("cash", cash_entries, "event_date"),
            ("corporate_action", corporate_actions, "effective_date"),
        )
        for scope, records, date_key in record_groups:
            for index, item in enumerate(records):
                classification = classify_ibkr_currency(item.get("currency"))
                if classification.status != IbkrCurrencyStatus.VALID or not classification.code:
                    issues.append(
                        self._ibkr_currency_issue(
                            scope=scope,
                            classification=classification,
                            fatal=True,
                            row=item.get("_source_line_number") or index + 1,
                            account_base_currency=account_base,
                        )
                    )
                    continue
                event_date = self._parse_date(item.get(date_key)) or date.today()
                if self._has_required_ibkr_fx(
                    currency=classification.code,
                    account_base=account_base,
                    as_of_date=event_date,
                ):
                    continue
                issues.append(
                    self._ibkr_currency_issue(
                        scope=scope,
                        classification=classify_ibkr_currency(
                            classification.code,
                            operationally_supported=False,
                        ),
                        fatal=True,
                        row=item.get("_source_line_number") or index + 1,
                        account_base_currency=account_base,
                    )
                )
        return self._dedupe_ibkr_currency_issues(issues)

    def _has_required_ibkr_fx(
        self,
        *,
        currency: str,
        account_base: str,
        as_of_date: date,
    ) -> bool:
        _, _, source = self.portfolio_service.convert_amount(
            amount=1.0,
            from_currency=currency,
            to_currency=account_base,
            as_of_date=as_of_date,
        )
        return source != "fallback_1_to_1"

    @staticmethod
    def _dedupe_ibkr_currency_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique: List[Dict[str, Any]] = []
        seen: set[Tuple[Any, ...]] = set()
        for issue in issues:
            key = (
                issue.get("scope"),
                issue.get("row"),
                issue.get("currency"),
                issue.get("reason"),
                bool(issue.get("fatal")),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(issue)
        return unique[:20]

    def _normalize_broker(self, value: str) -> str:
        broker = (value or "").strip().lower()
        if broker in IBKR_BROKER_ALIASES:
            broker = IBKR_BROKER
        broker = self._broker_alias_map.get(broker, broker)
        if broker == IBKR_BROKER:
            return broker
        if broker not in self._parser_registry:
            supported = ", ".join(sorted([*self._parser_registry.keys(), IBKR_BROKER]))
            raise ValueError(f"broker must be one of: {supported}")
        return broker

    @staticmethod
    def _read_csv(content: bytes) -> pd.DataFrame:
        for encoding in ("utf-8-sig", "gbk", "gb18030"):
            try:
                return pd.read_csv(
                    io.BytesIO(content),
                    encoding=encoding,
                    dtype=str,
                    keep_default_na=False,
                )
            except UnicodeDecodeError:
                continue
        return pd.read_csv(io.BytesIO(content), dtype=str, keep_default_na=False)

    def _normalize_trade_row(
        self,
        *,
        row: Any,
        parser_spec: CsvParserSpec,
    ) -> Optional[Dict[str, Any]]:
        broker_hints = parser_spec.column_hints

        trade_date_raw = self._pick(
            row,
            *(broker_hints.get("trade_date") or ()),
            "成交日期",
            "发生日期",
            "日期",
            "成交时间",
        )
        trade_date_obj = self._parse_date(trade_date_raw)
        if trade_date_obj is None:
            return None

        symbol_raw = self._pick(
            row,
            *(broker_hints.get("symbol") or ()),
            "证券代码",
            "股票代码",
            "代码",
        )
        symbol = canonical_stock_code(str(symbol_raw or "").strip())
        if not symbol:
            return None

        side_raw = self._pick(
            row,
            *(broker_hints.get("side") or ()),
            "买卖标志",
            "买卖方向",
            "交易方向",
            "业务名称",
            "操作",
        )
        side = self._normalize_side(side_raw)
        if side is None:
            return None

        quantity = self._parse_float(
            self._pick(row, *(broker_hints.get("quantity") or ()), "成交数量", "数量", "成交股数")
        )
        price = self._parse_float(
            self._pick(row, *(broker_hints.get("price") or ()), "成交均价", "成交价格", "价格", "成交价", "均价")
        )
        if quantity is None or quantity <= 0 or price is None or price <= 0:
            return None

        fee = 0.0
        for col in ("手续费", "佣金", "交易费", "规费", "过户费"):
            value = self._parse_float(self._pick(row, col))
            if value is not None:
                fee += value

        tax = 0.0
        for col in ("印花税", "税费", "其他税费"):
            value = self._parse_float(self._pick(row, col))
            if value is not None:
                tax += value

        trade_uid = self._pick(
            row,
            *(broker_hints.get("trade_uid") or ()),
            "成交编号",
            "成交序号",
            "合同编号",
            "委托编号",
            "流水号",
        )
        currency = self._pick(row, "币种", "货币")

        return {
            "trade_date": trade_date_obj,
            "symbol": symbol,
            "side": side,
            "quantity": float(quantity),
            "price": float(price),
            "fee": float(fee),
            "tax": float(tax),
            "trade_uid": (str(trade_uid).strip() if trade_uid is not None else None) or None,
            "currency": (str(currency).strip().upper() if currency is not None else None) or None,
        }

    @staticmethod
    def _pick(row: Any, *candidates: str) -> Any:
        for name in candidates:
            if name in row.index:
                value = row.get(name)
                if value is not None and str(value).strip() != "" and str(value).strip().lower() != "nan":
                    return value
        return None

    @staticmethod
    def _parse_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        text = str(value).strip().replace(",", "")
        if not text or text.lower() == "nan":
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return None
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date()

    @staticmethod
    def _normalize_side(value: Any) -> Optional[str]:
        text = str(value or "").strip().lower()
        if not text:
            return None
        compact = text.replace(" ", "")
        buy_exact = {"buy", "b", "买", "买入", "证券买入", "普通买入"}
        sell_exact = {"sell", "s", "卖", "卖出", "证券卖出", "普通卖出"}
        if compact in buy_exact:
            return "buy"
        if compact in sell_exact:
            return "sell"
        if "买入" in compact or compact.startswith("买"):
            return "buy"
        if "卖出" in compact or compact.startswith("卖"):
            return "sell"
        return None

    @staticmethod
    def _build_dedup_hash(record: Dict[str, Any]) -> str:
        payload = "|".join(
            [
                str(record.get("trade_date") or ""),
                str(record.get("symbol") or ""),
                str(record.get("side") or ""),
                f"{float(record.get('quantity', 0.0)):.8f}",
                f"{float(record.get('price', 0.0)):.8f}",
                f"{float(record.get('fee', 0.0)):.8f}",
                f"{float(record.get('tax', 0.0)):.8f}",
                str(record.get("currency") or ""),
                str(record.get("_source_line_number") or record.get("source_line_number") or ""),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _fingerprint_bytes(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _parse_xml_root(content: bytes) -> ET.Element:
        try:
            return ET.fromstring(content)
        except ET.ParseError as exc:
            raise ValueError(f"Unsupported XML input: {exc}") from exc

    @staticmethod
    def _local_name(tag: str) -> str:
        return str(tag or "").split("}", 1)[-1]

    def _find_first_by_local_name(self, root: ET.Element, name: str) -> Optional[ET.Element]:
        wanted = name.lower()
        for element in root.iter():
            if self._local_name(element.tag).lower() == wanted:
                return element
        return None

    def _iter_by_local_name(self, root: ET.Element, name: str):
        wanted = name.lower()
        for element in root.iter():
            if self._local_name(element.tag).lower() == wanted:
                yield element

    @staticmethod
    def _pick_attr(element: ET.Element, *names: str) -> Optional[str]:
        for name in names:
            value = element.attrib.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    @staticmethod
    def _normalize_optional_date(value: Any) -> Optional[str]:
        parsed = PortfolioImportService._parse_date(value)
        return parsed.isoformat() if parsed else None

    def _parse_ibkr_trade_records(self, statement: ET.Element) -> Tuple[List[Dict[str, Any]], int, List[str]]:
        records: List[Dict[str, Any]] = []
        skipped = 0
        errors: List[str] = []
        for idx, element in enumerate(self._iter_by_local_name(statement, "Trade")):
            try:
                record = self._normalize_ibkr_trade_record(element=element, source_index=idx)
                if record is None:
                    skipped += 1
                    continue
                records.append(record)
            except Exception as exc:
                skipped += 1
                errors.append(f"trade_idx={idx}: {exc}")
        return records, skipped, errors

    def _parse_ibkr_cash_entries(
        self,
        statement: ET.Element,
    ) -> Tuple[List[Dict[str, Any]], int, List[str]]:
        entries: List[Dict[str, Any]] = []
        skipped = 0
        errors: List[str] = []
        for idx, element in enumerate(self._iter_by_local_name(statement, "CashTransaction")):
            try:
                entry = self._normalize_ibkr_cash_entry(element=element)
                if entry is None:
                    skipped += 1
                    continue
                entries.append(entry)
            except Exception as exc:
                skipped += 1
                errors.append(f"cash_idx={idx}: {exc}")
        return entries, skipped, errors

    def _parse_ibkr_corporate_actions(
        self,
        statement: ET.Element,
    ) -> Tuple[List[Dict[str, Any]], int, List[str]]:
        actions: List[Dict[str, Any]] = []
        skipped = 0
        errors: List[str] = []
        for idx, element in enumerate(self._iter_by_local_name(statement, "CorporateAction")):
            try:
                action = self._normalize_ibkr_corporate_action(element=element)
                if action is None:
                    skipped += 1
                    continue
                actions.append(action)
            except Exception as exc:
                skipped += 1
                errors.append(f"corp_idx={idx}: {exc}")
        return actions, skipped, errors

    def _parse_ibkr_open_position_seed_records(
        self,
        statement: ET.Element,
        *,
        statement_to: Optional[str],
        broker_account_ref: Optional[str],
    ) -> Tuple[List[Dict[str, Any]], int, List[str]]:
        records: List[Dict[str, Any]] = []
        warnings: List[str] = []
        count = 0
        for idx, element in enumerate(self._iter_by_local_name(statement, "OpenPosition")):
            count += 1
            try:
                record = self._normalize_ibkr_open_position_record(
                    element=element,
                    source_index=idx,
                    statement_to=statement_to,
                    broker_account_ref=broker_account_ref,
                )
                if record is None:
                    continue
                records.append(record)
            except ValueError as exc:
                warnings.append(str(exc))
        return records, count, warnings[:20]

    def _normalize_ibkr_trade_record(self, *, element: ET.Element, source_index: int) -> Optional[Dict[str, Any]]:
        asset_category = (self._pick_attr(element, "assetCategory", "assetClass") or "STK").upper()
        if asset_category not in {"STK"}:
            return None
        symbol = canonical_stock_code(
            self._pick_attr(element, "symbol", "underlyingSymbol", "displaySymbol") or ""
        )
        if not symbol:
            return None
        trade_date_obj = self._parse_date(
            self._pick_attr(element, "tradeDate", "dateTime", "tradeDateTime", "reportDate")
        )
        if trade_date_obj is None:
            return None
        quantity_raw = self._parse_float(self._pick_attr(element, "quantity", "tradeQuantity"))
        if quantity_raw is None or abs(quantity_raw) <= 0:
            return None
        price = self._parse_float(self._pick_attr(element, "tradePrice", "price", "costBasisPrice"))
        if price is None or price <= 0:
            return None
        side = self._normalize_ibkr_side(
            self._pick_attr(element, "buySell", "side"),
            quantity_raw=quantity_raw,
        )
        if side is None:
            return None
        market = self._normalize_ibkr_market(
            self._pick_attr(element, "exchange", "listingExchange", "primaryExchange"),
            symbol=symbol,
        )
        currency = self._pick_attr(element, "currency", "currencyPrimary", "fxCurrency")
        fee = abs(self._parse_float(self._pick_attr(element, "ibCommission", "commission")) or 0.0)
        tax = abs(self._parse_float(self._pick_attr(element, "taxes", "tax", "salesTax")) or 0.0)
        trade_uid = self._pick_attr(element, "ibExecID", "executionId", "tradeID", "transactionID", "orderID")
        record = {
            "trade_date": trade_date_obj,
            "symbol": symbol,
            "market": market,
            "currency": str(currency).upper() if currency is not None else None,
            "side": side,
            "quantity": abs(float(quantity_raw)),
            "price": float(price),
            "fee": float(fee),
            "tax": float(tax),
            "trade_uid": trade_uid,
            "note": (self._pick_attr(element, "description", "notes") or "ibkr_flex_trade").strip(),
            "_source_line_number": source_index + 1,
        }
        record["dedup_hash"] = self._build_dedup_hash(record)
        return record

    def _normalize_ibkr_cash_entry(
        self,
        *,
        element: ET.Element,
    ) -> Optional[Dict[str, Any]]:
        event_date_obj = self._parse_date(
            self._pick_attr(element, "reportDate", "settleDate", "dateTime", "date")
        )
        if event_date_obj is None:
            return None
        amount = self._parse_float(self._pick_attr(element, "amount", "amountLocal", "amountBase"))
        if amount is None or abs(amount) <= 0:
            return None
        currency = self._pick_attr(element, "currency", "currencyPrimary")
        description = (
            self._pick_attr(element, "description", "type", "activityDescription")
            or "ibkr_flex_cash"
        ).strip()
        return {
            "event_date": event_date_obj,
            "direction": "in" if float(amount) > 0 else "out",
            "amount": abs(float(amount)),
            "currency": str(currency).upper() if currency is not None else None,
            "note": description[:255],
        }

    def _normalize_ibkr_corporate_action(
        self,
        *,
        element: ET.Element,
    ) -> Optional[Dict[str, Any]]:
        description = (self._pick_attr(element, "description", "type", "actionDescription") or "").strip()
        if "split" not in description.lower():
            return None
        effective_date_obj = self._parse_date(
            self._pick_attr(element, "reportDate", "dateTime", "effectiveDate", "date")
        )
        if effective_date_obj is None:
            return None
        split_ratio = self._parse_split_ratio(
            self._pick_attr(element, "ratio", "splitRatio", "quantity")
            or description
        )
        if split_ratio is None or split_ratio <= 0:
            return None
        symbol = canonical_stock_code(self._pick_attr(element, "symbol", "underlyingSymbol", "displaySymbol") or "")
        if not symbol:
            return None
        market = self._normalize_ibkr_market(
            self._pick_attr(element, "exchange", "listingExchange", "primaryExchange"),
            symbol=symbol,
        )
        currency = self._pick_attr(element, "currency", "currencyPrimary")
        return {
            "effective_date": effective_date_obj,
            "symbol": symbol,
            "market": market,
            "currency": str(currency).upper() if currency is not None else None,
            "action_type": "split_adjustment",
            "split_ratio": float(split_ratio),
            "note": description[:255] or "ibkr_flex_split",
        }

    def _normalize_ibkr_open_position_record(
        self,
        *,
        element: ET.Element,
        source_index: int,
        statement_to: Optional[str],
        broker_account_ref: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        asset_category = (self._pick_attr(element, "assetCategory", "assetClass") or "STK").upper()
        if asset_category not in {"STK"}:
            return None
        symbol = canonical_stock_code(
            self._pick_attr(element, "symbol", "underlyingSymbol", "displaySymbol") or ""
        )
        if not symbol:
            return None
        quantity = self._parse_float(self._pick_attr(element, "position", "quantity"))
        if quantity is None or abs(quantity) <= 0:
            return None
        if float(quantity) < 0:
            raise ValueError(f"IBKR short open position for {symbol} is not supported in this import phase")
        price = self._parse_float(self._pick_attr(element, "costBasisPrice", "costPrice", "openPrice"))
        if price is None or price <= 0:
            return None
        trade_date_obj = self._parse_date(
            self._pick_attr(element, "reportDate", "positionDate", "openDate", "date")
            or statement_to
        )
        if trade_date_obj is None:
            return None
        market = self._normalize_ibkr_market(
            self._pick_attr(element, "exchange", "listingExchange", "primaryExchange"),
            symbol=symbol,
        )
        currency = self._pick_attr(element, "currency", "currencyPrimary")
        trade_uid = f"ibkr-open:{broker_account_ref or 'unknown'}:{symbol}:{trade_date_obj.isoformat()}"
        record = {
            "trade_date": trade_date_obj,
            "symbol": symbol,
            "market": market,
            "currency": str(currency).upper() if currency is not None else None,
            "side": "buy",
            "quantity": abs(float(quantity)),
            "price": float(price),
            "fee": 0.0,
            "tax": 0.0,
            "trade_uid": trade_uid,
            "note": "ibkr_flex_open_position_seed",
            "_source_line_number": source_index + 1,
            "_ibkr_currency_scope": "open_position",
        }
        record["dedup_hash"] = self._build_dedup_hash(record)
        return record

    @staticmethod
    def _normalize_ibkr_side(value: Optional[str], *, quantity_raw: Optional[float] = None) -> Optional[str]:
        text = str(value or "").strip().lower()
        if text in {"buy", "b", "bot"}:
            return "buy"
        if text in {"sell", "s", "sld"}:
            return "sell"
        if quantity_raw is not None:
            return "buy" if float(quantity_raw) > 0 else "sell"
        return None

    @staticmethod
    def _normalize_ibkr_market(exchange: Optional[str], *, symbol: str) -> str:
        text = str(exchange or "").strip().upper()
        if any(token in text for token in ("HK", "SEHK")):
            return "hk"
        if any(token in text for token in ("NYSE", "NASDAQ", "ARCA", "AMEX", "BATS", "ISLAND", "IEX")):
            return "us"
        if symbol.startswith("HK") or re.fullmatch(r"\d{1,5}\.HK", symbol) or re.fullmatch(r"HK\d{5}", symbol):
            return "hk"
        if re.fullmatch(r"[A-Z][A-Z0-9.\-]*", symbol):
            return "us"
        return "cn"

    @staticmethod
    def _parse_split_ratio(value: Any) -> Optional[float]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        direct = PortfolioImportService._parse_float(text)
        if direct is not None and direct > 0:
            return direct
        patterns = [
            r"(\d+(?:\.\d+)?)\s*for\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)",
        ]
        lowered = text.lower()
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if not match:
                continue
            left = float(match.group(1))
            right = float(match.group(2))
            if right > 0:
                return left / right
        return None
