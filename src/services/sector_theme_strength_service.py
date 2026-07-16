# -*- coding: utf-8 -*-
"""Standalone sector/theme strength summary scaffold."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from api.v1.schemas.sector_theme_strength import (
    SectorThemeStrengthDataQualityModel,
    SectorThemeStrengthItemModel,
    SectorThemeStrengthNarrativeModel,
    SectorThemeStrengthSummaryModel,
)


NO_ADVICE_DISCLOSURE = "仅用于观察行业与主题强弱变化，非买卖建议。"

_NO_EVIDENCE_OBSERVATION = "未接入可安全复用的板块/主题强弱来源，当前仅供观察。"
_SAFE_OBSERVATION_FALLBACK = "仅供观察，等待更多证据。"
_SAFE_DATA_QUALITY_FALLBACK = "已做安全收敛，仅保留观察口径。"
_UNVERIFIED_DATA_QUALITY_OBSERVATION = "证据尚未完成核验，当前仅供观察。"
_UNVERIFIED_EVIDENCE_MARKERS = (
    "example/test",
    "example data",
    "fixture",
    "sample",
    "test data",
    "observation only",
    "observation-only",
    "unverified",
    "样例",
    "样本",
    "仅供观察",
    "未核验",
)
_MEASURE_DEFAULTS = {
    "leadership": "领先状态仅用于观察是否由少数龙头主导。",
    "diffusion": "扩散状态仅用于观察强势是否向更多成员扩散。",
    "concentration": "集中度状态仅用于观察强势是否仍集中于少数龙头。",
}
_ADVICE_PATTERN = re.compile(
    r"买入|卖出|加仓|减仓|清仓|目标价|目标位|目标区间|交易指令|交易建议|投资建议|下单|立即交易|"
    r"buy now|sell now|buy signal|add position|reduce position|clear position|target price|predicted return|"
    r"trade recommendation|trading advice|investment advice|execution ready",
    re.IGNORECASE,
)
_LEAK_PATTERN = re.compile(
    r"reasoncode|trustlevel|sourcetype|fallback|debug|traceback|token|secret|api[_ -]?key|"
    r"raw diagnostics|raw payload|internal diagnostics|https?://|www\.|url",
    re.IGNORECASE,
)
_ENGLISH_TRADE_WORD_PATTERN = re.compile(r"\btrade\b", re.IGNORECASE)


class SectorThemeStrengthService:
    """Build a bounded homepage sector/theme strength summary."""

    def build_summary(
        self,
        snapshot: Mapping[str, Any] | None = None,
    ) -> SectorThemeStrengthSummaryModel:
        if not snapshot:
            return self._build_no_evidence_summary()

        readiness_status = self._readiness_status(snapshot)
        if readiness_status == "unavailable":
            return self._build_unavailable_summary()

        strongest = self._build_items(snapshot.get("strongest"), readiness_status=readiness_status)
        weakest = self._build_items(snapshot.get("weakest"), readiness_status=readiness_status)
        has_evidence = bool(strongest or weakest or self._has_measure_evidence(snapshot))
        if not has_evidence:
            return self._build_no_evidence_summary()

        return SectorThemeStrengthSummaryModel(
            status=readiness_status,
            asOf=self._optional_text(snapshot.get("asOf")),
            strongest=strongest,
            weakest=weakest,
            leadership=self._build_narrative(
                snapshot.get("leadership"),
                default_status="neutral" if readiness_status == "ready" else "no_evidence",
                default_observation=_MEASURE_DEFAULTS["leadership"],
                readiness_status=readiness_status,
            ),
            diffusion=self._build_narrative(
                snapshot.get("diffusion"),
                default_status="neutral" if readiness_status == "ready" else "no_evidence",
                default_observation=_MEASURE_DEFAULTS["diffusion"],
                readiness_status=readiness_status,
            ),
            concentration=self._build_narrative(
                snapshot.get("concentration"),
                default_status="neutral" if readiness_status == "ready" else "no_evidence",
                default_observation=_MEASURE_DEFAULTS["concentration"],
                readiness_status=readiness_status,
            ),
            dataQuality=self._project_data_quality(
                snapshot.get("dataQuality"),
                default_status=readiness_status,
                default_observation=_UNVERIFIED_DATA_QUALITY_OBSERVATION,
                readiness_status=readiness_status,
            ),
            noAdviceDisclosure=NO_ADVICE_DISCLOSURE,
        )

    def _build_unavailable_summary(self) -> SectorThemeStrengthSummaryModel:
        unavailable_quality = self._build_data_quality(
            None,
            default_status="unavailable",
            default_observation="当前板块/主题强弱证据暂不可用，仅供观察。",
        )
        return SectorThemeStrengthSummaryModel(
            status="unavailable",
            asOf=None,
            strongest=[],
            weakest=[],
            leadership=self._build_narrative(
                None,
                default_status="unavailable",
                default_observation=unavailable_quality.observation,
                data_quality=unavailable_quality,
            ),
            diffusion=self._build_narrative(
                None,
                default_status="unavailable",
                default_observation=unavailable_quality.observation,
                data_quality=unavailable_quality,
            ),
            concentration=self._build_narrative(
                None,
                default_status="unavailable",
                default_observation=unavailable_quality.observation,
                data_quality=unavailable_quality,
            ),
            dataQuality=unavailable_quality,
            noAdviceDisclosure=NO_ADVICE_DISCLOSURE,
        )

    def _build_no_evidence_summary(self) -> SectorThemeStrengthSummaryModel:
        no_evidence_quality = self._build_data_quality(
            None,
            default_status="no_evidence",
            default_observation=_NO_EVIDENCE_OBSERVATION,
        )
        return SectorThemeStrengthSummaryModel(
            status="no_evidence",
            asOf=None,
            strongest=[],
            weakest=[],
            leadership=self._build_narrative(
                None,
                default_status="no_evidence",
                default_observation=_NO_EVIDENCE_OBSERVATION,
                data_quality=no_evidence_quality,
            ),
            diffusion=self._build_narrative(
                None,
                default_status="no_evidence",
                default_observation=_NO_EVIDENCE_OBSERVATION,
                data_quality=no_evidence_quality,
            ),
            concentration=self._build_narrative(
                None,
                default_status="no_evidence",
                default_observation=_NO_EVIDENCE_OBSERVATION,
                data_quality=no_evidence_quality,
            ),
            dataQuality=no_evidence_quality,
            noAdviceDisclosure=NO_ADVICE_DISCLOSURE,
        )

    def _build_items(
        self,
        items: Any,
        *,
        readiness_status: str,
    ) -> list[SectorThemeStrengthItemModel]:
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
            return []
        return [
            SectorThemeStrengthItemModel(
                name=str(item.get("name") or "").strip(),
                category=item.get("category") or "other",
                relativeStrength=self._optional_float(item.get("relativeStrength")),
                breadth=self._optional_float(item.get("breadth")),
                diffusionStatus=(
                    item.get("diffusionStatus") or "no_evidence"
                    if readiness_status == "ready"
                    else readiness_status
                ),
                leadershipStatus=(
                    item.get("leadershipStatus") or "no_evidence"
                    if readiness_status == "ready"
                    else readiness_status
                ),
                observation=self._safe_text(
                    item.get("observation"),
                    fallback=_SAFE_OBSERVATION_FALLBACK,
                ),
                dataQuality=self._project_data_quality(
                    item.get("dataQuality"),
                    default_status="no_evidence",
                    default_observation=_UNVERIFIED_DATA_QUALITY_OBSERVATION,
                    readiness_status=readiness_status,
                ),
            )
            for item in items
            if isinstance(item, Mapping) and str(item.get("name") or "").strip()
        ]

    def _build_narrative(
        self,
        payload: Any,
        *,
        default_status: str,
        default_observation: str,
        data_quality: SectorThemeStrengthDataQualityModel | None = None,
        readiness_status: str | None = None,
    ) -> SectorThemeStrengthNarrativeModel:
        mapping = payload if isinstance(payload, Mapping) else {}
        return SectorThemeStrengthNarrativeModel(
            status=(
                mapping.get("status") or default_status
                if readiness_status in {None, "ready"}
                else readiness_status
            ),
            observation=self._safe_text(
                mapping.get("observation"),
                fallback=default_observation,
            ),
            dataQuality=data_quality
            or self._project_data_quality(
                mapping.get("dataQuality"),
                default_status="no_evidence",
                default_observation=_UNVERIFIED_DATA_QUALITY_OBSERVATION,
                readiness_status=readiness_status,
            ),
        )

    def _project_data_quality(
        self,
        payload: Any,
        *,
        default_status: str,
        default_observation: str,
        readiness_status: str | None,
    ) -> SectorThemeStrengthDataQualityModel:
        quality = self._build_data_quality(
            payload,
            default_status=default_status,
            default_observation=default_observation,
        )
        if readiness_status in {None, "ready"}:
            return quality
        return SectorThemeStrengthDataQualityModel(
            status=readiness_status,
            observation=quality.observation,
        )

    def _build_data_quality(
        self,
        payload: Any,
        *,
        default_status: str,
        default_observation: str,
    ) -> SectorThemeStrengthDataQualityModel:
        mapping = payload if isinstance(payload, Mapping) else {}
        return SectorThemeStrengthDataQualityModel(
            status=mapping.get("status") or default_status,
            observation=self._safe_text(
                mapping.get("observation"),
                fallback=default_observation,
            ),
        )

    def _readiness_status(self, snapshot: Mapping[str, Any]) -> str:
        data_quality = snapshot.get("dataQuality")
        quality = data_quality if isinstance(data_quality, Mapping) else {}
        status = self._optional_text(snapshot.get("status"))
        quality_status = self._optional_text(quality.get("status"))

        if "unavailable" in {status, quality_status}:
            return "unavailable"
        if status != "ready" or quality_status != "ready":
            return "no_evidence"
        if self._contains_unverified_marker(snapshot):
            return "no_evidence"
        return "ready"

    def _contains_unverified_marker(self, value: Any) -> bool:
        if isinstance(value, Mapping):
            return any(self._contains_unverified_marker(item) for item in value.values())
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return any(self._contains_unverified_marker(item) for item in value)
        text = self._optional_text(value)
        return bool(text and any(marker in text.lower() for marker in _UNVERIFIED_EVIDENCE_MARKERS))

    def _has_measure_evidence(self, snapshot: Mapping[str, Any]) -> bool:
        for key in ("leadership", "diffusion", "concentration"):
            payload = snapshot.get(key)
            if not isinstance(payload, Mapping):
                continue
            if payload.get("status") not in {None, "no_evidence", "unavailable"}:
                return True
            if self._optional_text(payload.get("observation")):
                return True
        return False

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _optional_float(self, value: Any) -> float | None:
        if value is None or value == "":
            return None
        return float(value)

    def _safe_text(self, value: Any, *, fallback: str) -> str:
        text = self._optional_text(value)
        if not text:
            return fallback
        if (
            _ADVICE_PATTERN.search(text)
            or _LEAK_PATTERN.search(text)
            or _ENGLISH_TRADE_WORD_PATTERN.search(text)
        ):
            return fallback if fallback != "example/test data only" else _SAFE_DATA_QUALITY_FALLBACK
        return text
