from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from src.services.scanner_universe_readiness import build_scanner_universe_readiness_from_coverage


_BLOCKING_OHLCV_PRIORITY = ("provider_missing", "provider_unavailable", "entitlement_required", "insufficient_history")
_BLOCKING_OHLCV_REQUIREMENTS = frozenset(_BLOCKING_OHLCV_PRIORITY)
_CRITICAL_CANDIDATE_BLOCKERS = frozenset(
    {
        "universe_missing",
        "empty_universe",
        "missing_quote_snapshot",
        "missing_history",
        "missing_adjustments",
        "missing_benchmark",
        "factor_evidence_unavailable",
        "factor_evidence_insufficient",
        "factor_evidence_stale",
        "factor_evidence_rejected",
    }
)
_SYNTHETIC_MARKERS = ("synthetic", "mock")
_FIXTURE_MARKERS = ("fixture", "test_fixture")
_READINESS_COPY = {
    "missing_universe": ("Scanner 缺少可用标的池，暂时无法生成候选。", "补充可扫描标的池后重新运行 Scanner。"),
    "universe_missing": ("Scanner 缺少可用标的池，暂时无法生成候选。", "补充可扫描标的池后重新运行 Scanner。"),
    "universe_not_configured": ("Scanner 标的池尚未配置，暂时无法生成候选。", "配置并刷新可扫描标的池后重新运行 Scanner。"),
    "stale_universe": ("Scanner 标的池已过期，暂时无法生成候选。", "刷新扫描标的池后重新运行 Scanner。"),
    "empty_universe": ("候选池为空，Scanner 暂时无法生成候选。", "补充可扫描标的池后重新运行 Scanner。"),
    "missing_quote_snapshot": ("行情快照不足，Scanner 暂时无法完成候选生成。", "补充行情快照后重新运行 Scanner。"),
    "missing_history": ("历史行情覆盖不足，Scanner 暂时无法完成候选生成。", "补充历史行情覆盖后重新运行 Scanner。"),
    "insufficient_history": ("历史行情覆盖不足，Scanner 暂时无法完成候选生成。", "补充 required bars 后重新运行 Scanner。"),
    "provider_missing": ("历史行情 provider 未配置，Scanner 暂时无法生成可执行候选。", "配置显式 OHLCV runtime/provider 或补充本地历史后重新运行 Scanner。"),
    "provider_unavailable": ("历史行情 provider 当前不可用，Scanner 暂时无法生成可执行候选。", "恢复 OHLCV 数据源后重新运行 Scanner。"),
    "entitlement_required": ("历史行情需要额外授权，Scanner 暂时无法生成可执行候选。", "确认数据授权后重新运行 Scanner。"),
    "stale_data": ("历史行情不够新，Scanner 只能给出受限结果。", "刷新历史行情后再复核 Scanner。"),
    "missing_adjustments": ("历史行情缺少复权/公司行动处理，Scanner 结果仅可观察。", "补充复权历史后再复核 Scanner。"),
    "missing_benchmark": ("Scanner 缺少所需市场基准历史，结果仅可观察。", "补充 benchmark 历史后再复核 Scanner。"),
    "stale_history": ("历史行情不够新，Scanner 只能给出受限结果。", "刷新历史行情后再复核 Scanner。"),
    "insufficient_coverage": ("标的池可用，但行情或历史覆盖不足，暂不生成候选。", "补齐行情与历史覆盖后重新运行 Scanner。"),
    "profile_filters_rejected_all": ("本轮 profile 过滤后没有留下候选。", "复核扫描配置、标的池和数据覆盖后重新运行 Scanner。"),
    "source_quality_capped": ("本轮数据质量不足，候选结果被限制。", "补充可用于评分的数据覆盖后重新运行 Scanner。"),
    "factor_evidence_unavailable": ("必需因子证据不可用，Scanner 未生成可排序候选。", "补齐缺失因子证据后重新运行 Scanner。"),
    "factor_evidence_insufficient": ("必需因子尚未完成 warm-up，Scanner 未生成可排序候选。", "补齐所需历史 bars 后重新运行 Scanner。"),
    "factor_evidence_stale": ("必需因子证据已过期，Scanner 未生成可排序候选。", "刷新过期观测后重新运行 Scanner。"),
    "factor_evidence_rejected": ("必需因子来源不具备评分权威性，Scanner 未生成可排序候选。", "提供官方或已授权来源后重新运行 Scanner。"),
    "scanner_runtime_unavailable": ("Scanner 本轮运行未完成，暂时无法判断候选。", "修复运行条件后重新运行 Scanner。"),
}


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(item) for item in value))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class ScannerReadinessEvidence:
    market: str = "unknown"
    profile: str = "unknown"
    status: str = "unknown"
    universe_size: int | None = None
    evaluated_size: int | None = None
    shortlist_size: int | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    summary: Mapping[str, Any] = field(default_factory=dict)
    candidates: Sequence[Mapping[str, Any]] = ()
    cache_universe_readiness: Mapping[str, Any] = field(default_factory=dict)
    ohlcv_readiness: Mapping[str, Any] = field(default_factory=dict)
    quote_snapshot_readiness: Mapping[str, Any] = field(default_factory=dict)
    source_markers: Sequence[str] = ()
    bounded_us_symbols: Sequence[str] = ()

    def __post_init__(self) -> None:
        for name in (
            "diagnostics",
            "summary",
            "candidates",
            "cache_universe_readiness",
            "ohlcv_readiness",
            "quote_snapshot_readiness",
            "source_markers",
            "bounded_us_symbols",
        ):
            object.__setattr__(self, name, _freeze(getattr(self, name)))


@dataclass(frozen=True)
class EvaluatedScannerReadiness:
    state: str
    availability_state: str
    execution_state: str
    universe_availability: str
    universe_size: int | None
    quote_coverage: str
    history_coverage: str
    candidate_generation_state: str
    candidate_generation_blockers: tuple[str, ...]
    candidate_generation_limitations: tuple[str, ...]
    freshness: str
    required_bars: int | None
    usable_bars: int | None
    missing_bars: int | None
    candidate_evaluation_count: int | None
    selected_count: int | None
    rejected_count: int | None
    failed_count: int | None
    blocker_bucket: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _freeze(self.payload))


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_int(value: Any) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None


def _projected_int(value: Any) -> int:
    parsed = _optional_int(value)
    return parsed if parsed is not None else 0


def _text_list(value: Any, *, upper: bool = False, limit: int | None = None) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        text = text.upper() if upper else text.lower()
        if text and text not in result:
            result.append(text)
        if limit is not None and len(result) >= limit:
            break
    return result


def _reason_counts(coverage_summary: Mapping[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in coverage_summary.get("excluded_by_reason") or ():
        if not isinstance(item, Mapping):
            continue
        reason = str(item.get("reason") or "").strip().lower()
        if reason:
            result[reason] = result.get(reason, 0) + _projected_int(item.get("count"))
    return result


def _status_counts(summary: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> tuple[int | None, int | None, int | None]:
    keys = ("selected_count", "rejected_count", "data_failed_count", "error_count")
    values = {key: _optional_int(summary.get(key)) if key in summary else None for key in keys}
    if candidates and not any((value or 0) for value in values.values()):
        derived = {"selected": 0, "rejected": 0, "data_failed": 0, "error": 0}
        for item in candidates:
            status = str(item.get("status") or "").strip().lower()
            if status in derived:
                derived[status] += 1
        if any(derived.values()) or not any(value is not None for value in values.values()):
            values = {
                "selected_count": derived["selected"],
                "rejected_count": derived["rejected"],
                "data_failed_count": derived["data_failed"],
                "error_count": derived["error"],
            }
    failed_parts = (values["data_failed_count"], values["error_count"])
    failed = sum(value or 0 for value in failed_parts) if any(value is not None for value in failed_parts) else None
    return values["selected_count"], values["rejected_count"], failed


def _factor_evidence_blockers(
    candidates: Sequence[Mapping[str, Any]],
) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    symbols: list[str] = []
    for candidate in candidates:
        diagnostics = _mapping(candidate.get("diagnostics") or candidate.get("_diagnostics"))
        factor_evidence = _mapping(candidate.get("factorEvidence") or diagnostics.get("factorEvidence"))
        if not factor_evidence or factor_evidence.get("rankingEligible") is True:
            continue
        symbol = str(candidate.get("symbol") or "").strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
        for item in factor_evidence.get("factors") or ():
            if not isinstance(item, Mapping) or item.get("required") is not True:
                continue
            state = str(item.get("state") or "").strip().lower()
            blocker = f"factor_evidence_{state}" if state in {"unavailable", "insufficient", "stale", "rejected"} else ""
            if blocker and blocker not in blockers:
                blockers.append(blocker)
    return blockers, symbols


def _blocker(status: str, diagnostics: Mapping[str, Any], reason_counts: Mapping[str, int], universe_size: int, selected_count: int) -> str:
    failure = _mapping(diagnostics.get("failure"))
    tokens = " ".join((
        str(diagnostics.get("reason_code") or "").strip().lower(),
        str(diagnostics.get("empty_reason") or "").strip().lower(),
        str(failure.get("message") or "").strip().lower(),
        *reason_counts,
    ))
    if status == "not_run" and universe_size <= 0:
        return "universe_missing"
    marker_outcomes = (
        (("universe_source_unavailable", "us_universe_unavailable", "hk_universe_unavailable"), "missing_universe"),
        (("no_realtime_snapshot_available", "missing_quote_or_snapshot", "snapshot_unavailable"), "missing_quote_snapshot"),
        (("stale_history",), "stale_history"),
        (("missing_history", "insufficient_history", "not_enough_history", "history_coverage"), "missing_history"),
        (("扫描宇宙为空", "empty universe"), "empty_universe"),
    )
    for markers, outcome in marker_outcomes:
        if any(marker in tokens for marker in markers):
            return outcome
    if selected_count <= 0 and reason_counts.get("filtered_by_profile_constraints", 0) > 0:
        return "profile_filters_rejected_all"
    if selected_count <= 0 and any(marker in tokens for marker in ("source_quality_capped", "source_cap", "score_cap")):
        return "source_quality_capped"
    return "scanner_runtime_unavailable" if status == "failed" else "unknown"


def _quote_coverage(diagnostics: Mapping[str, Any], owner_readiness: Mapping[str, Any], status: str, selected_count: int, evaluated_count: int, blocker: str) -> str:
    owner_state = str(owner_readiness.get("availabilityState") or "").strip().lower()
    if owner_state in {"available", "partial", "stale", "missing"}:
        return owner_state
    if blocker == "missing_quote_snapshot":
        return "missing"
    live_stats = _mapping(diagnostics.get("live_quote_stats"))
    attempted = _projected_int(live_stats.get("attempted_candidates"))
    available = _projected_int(live_stats.get("available_candidates"))
    if attempted > 0:
        if available <= 0:
            return "missing"
        return "available" if available >= attempted else "partial"
    scanner_data = _mapping(diagnostics.get("scanner_data"))
    snapshot_resolution = _mapping(scanner_data.get("snapshot_resolution"))
    if diagnostics.get("snapshot_source") or snapshot_resolution.get("source"):
        return "available"
    if status == "completed" and (selected_count > 0 or evaluated_count > 0):
        return "available"
    return "unknown"


def _history_coverage(diagnostics: Mapping[str, Any], status: str, evaluated_count: int, reason_counts: Mapping[str, int], blocker: str) -> str:
    if blocker == "missing_history":
        return "missing"
    if blocker == "stale_history":
        return "partial"
    history_stats = _mapping(diagnostics.get("history_stats"))
    available = _projected_int(history_stats.get("local_hits")) + _projected_int(history_stats.get("network_fetches"))
    skipped = _projected_int(history_stats.get("skipped_for_history"))
    if available > 0:
        return "partial" if skipped > 0 else "available"
    if skipped > 0 or reason_counts.get("missing_history", 0) > 0:
        return "missing"
    return "available" if status == "completed" and evaluated_count > 0 else "unknown"


def _freshness(status: str, quote: str, history: str, blocker: str, diagnostics: Mapping[str, Any]) -> str:
    tokens = " ".join(
        str(value or "").lower()
        for value in diagnostics.values()
        if not isinstance(value, (dict, list, tuple, Mapping))
    )
    if blocker == "stale_history" or quote == "stale" or "stale" in tokens:
        return "stale"
    if "missing" in {quote, history}:
        return "unknown"
    if "partial" in {quote, history}:
        return "delayed"
    return "fresh" if status == "completed" and quote == history == "available" else "unknown"


def _ohlcv_symbols(readiness: Mapping[str, Any]) -> tuple[list[str], list[str], list[str]]:
    seeded: list[str] = []
    eligible: list[str] = []
    blocked: list[str] = []

    def add(target: list[str], value: Any) -> None:
        symbol = str(value or "").strip().upper()
        if symbol and symbol not in target:
            target.append(symbol)

    for item in readiness.get("symbolStates") or ():
        if not isinstance(item, Mapping):
            continue
        symbol = str(item.get("symbol") or "").strip().upper()
        provider_state = str(item.get("providerState") or "").strip().lower()
        overall_state = str(item.get("overallState") or "").strip().lower()
        usable_bars = _projected_int(item.get("usableBars"))
        missing_bars = _projected_int(item.get("missingBars"))
        if provider_state == "available" and usable_bars > 0:
            add(seeded, symbol)
        if provider_state == "available" and overall_state == "ready" and missing_bars <= 0:
            add(eligible, symbol)
        else:
            add(blocked, symbol)
    for key in ("blockedSymbols", "degradedSymbols"):
        for symbol in readiness.get(key) or ():
            add(blocked, symbol)
    return seeded[:50], eligible[:50], blocked[:50]


def _missing_data_families(universe: str, quote: str, history: str, benchmark_missing: bool, requirements: Sequence[str], blockers: Sequence[str]) -> list[str]:
    families: list[str] = []
    if universe in {"missing", "empty", "stale"}:
        families.append("universe")
    if quote in {"missing", "stale"} or {"missing_quote_snapshot", "stale_quote_snapshot"}.intersection(blockers):
        families.append("quote_snapshot")
    if quote == "stale" or "stale_quote_snapshot" in blockers:
        families.append("freshness")
    if history == "missing" or "missing_history" in blockers:
        families.append("historical_ohlcv")
    if benchmark_missing or "missing_benchmark" in blockers:
        families.append("benchmark_ohlcv")
    if any(str(item).startswith("factor_evidence_") for item in blockers):
        families.append("factor_evidence")
    if "factor_evidence_rejected" in blockers:
        families.append("source_authority")
    if "factor_evidence_stale" in blockers:
        families.append("freshness")
    requirement_families = {
        "provider_missing": ("historical_ohlcv",),
        "provider_unavailable": ("historical_ohlcv",),
        "entitlement_required": ("historical_ohlcv",),
        "insufficient_history": ("historical_ohlcv", "date_coverage"),
        "stale_data": ("freshness",),
        "missing_adjustments": ("adjusted_prices",),
        "missing_benchmark": ("benchmark_ohlcv",),
    }
    for requirement in requirements:
        families.extend(requirement_families.get(str(requirement).lower(), ()))
    return list(dict.fromkeys(families))


def _operator_action(cache_status: str, quote: str, benchmark_missing: bool, requirements: Sequence[str], eligible_count: int, seeded_count: int) -> str | None:
    requirement_set = set(requirements)
    if cache_status in {"missing", "stale", "not_configured", "unavailable"}:
        return None
    if quote == "stale":
        return "Refresh quote snapshot coverage before candidate generation."
    actions = (
        ({"provider_missing"}, "Enable the existing historical OHLCV cache/readiness path, or seed local bars for the bounded scanner universe."),
        ({"provider_unavailable", "entitlement_required"}, "Restore historical OHLCV availability for the bounded scanner universe, then rerun Scanner readiness."),
        ({"insufficient_history"}, "Seed or refresh enough historical OHLCV bars for the blocked scanner symbols."),
        ({"stale_data"}, "Refresh stale historical OHLCV bars for the bounded scanner universe."),
    )
    for tokens, action in actions:
        if requirement_set.intersection(tokens):
            return action
    if "missing_adjustments" in requirement_set:
        if quote == "missing" and seeded_count > 0:
            return (
                f"Cache-backed historical OHLCV rows exist for {seeded_count} symbol(s), "
                "but quote snapshot coverage and adjusted prices or adjustment metadata still block Scanner candidates."
            )
        return "Provide adjusted historical OHLCV rows or adjustment metadata before generating Scanner candidates."
    if eligible_count > 0 and quote == "missing":
        return f"Seeded historical OHLCV is usable for {eligible_count} symbol(s); refresh quote snapshot coverage before candidate generation."
    if seeded_count > 0 and quote == "missing":
        return f"Seeded historical OHLCV exists for {seeded_count} symbol(s), but quote snapshot coverage is still missing."
    if benchmark_missing:
        return "Seed or refresh the scanner benchmark OHLCV before candidate generation."
    return None


def _cache_readiness(state: str, requirements: Sequence[str], history: str, freshness: str) -> dict[str, Any]:
    requirement_set = set(requirements)
    cases = (
        ("provider_missing", "missing", "missing_cache"),
        ("provider_unavailable", "unavailable", "cache_unavailable"),
        ("insufficient_history", "insufficient", "insufficient_history"),
        ("stale_data", "stale", "stale_cache"),
    )
    for requirement, cache_state, reason in cases:
        if requirement in requirement_set:
            break
    else:
        if "missing_adjustments" in requirement_set and history in {"available", "partial"}:
            cache_state, reason = "degraded", "cached_ohlcv_missing_adjustments"
        elif state in {"ready", "partial"} and history in {"available", "partial"}:
            cache_state = "available" if state == "ready" else "degraded"
            reason = "cached_ohlcv_available"
        else:
            cache_state, reason = "unknown", "cache_state_unknown"
    return {"state": cache_state, "reason": reason, "freshness": freshness, "consumerSafe": True}


def _blocked_states(status: str, blockers: Sequence[str], selected: int, universe: str) -> list[str]:
    states: list[str] = []

    def add(value: str) -> None:
        if value not in states:
            states.append(value)

    if status == "not_run":
        add("scanner_run_not_executed")
    if universe in {"missing", "empty", "stale"}:
        add("no_local_universe")
    tokens = set(blockers)
    if tokens.intersection(_BLOCKING_OHLCV_REQUIREMENTS | {"missing_history", "missing_adjustments", "missing_benchmark"}):
        add("insufficient_ohlcv")
    if tokens.intersection({"missing_quote_snapshot", "stale_quote_snapshot"}):
        add("quote_unavailable_or_stale")
    if status in {"empty", "failed"} and selected <= 0 and not states:
        add("candidate_scoring_unavailable")
    return states


def _copy(blocker: str, state: str) -> tuple[str, str]:
    if state == "not_run":
        return "Scanner 尚未运行，暂时没有数据准备度结论。", "运行 Scanner 后查看数据准备度。"
    if blocker in _READINESS_COPY:
        return _READINESS_COPY[blocker]
    defaults = {
        "ready": ("Scanner 数据已满足本轮候选生成。", "继续按当前数据节奏复核扫描结果。"),
        "partial": ("Scanner 已生成候选，但部分数据覆盖仍需复核。", "补充缺口数据后复核候选稳定性。"),
    }
    return defaults.get(state, ("Scanner 数据准备度暂时无法判断。", "补充运行记录后再复核。"))


def _lineage(evidence: ScannerReadinessEvidence, ohlcv: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = evidence.diagnostics
    evaluated: list[str] = []
    sufficient: list[str] = []
    skipped: list[dict[str, str]] = []

    def add(target: list[str], value: Any) -> None:
        symbol = str(value or "").strip().upper()
        if symbol and symbol not in target:
            target.append(symbol)

    def add_skipped(value: Any, reason: Any) -> None:
        symbol = str(value or "").strip().upper()
        reason = str(reason or "limited").strip().lower() or "limited"
        reason = "insufficient_history" if reason in {"history", "missing_history", "not_enough_history"} else reason
        if symbol and not any(item["symbol"] == symbol for item in skipped):
            skipped.append({"symbol": symbol, "reason": reason})

    candidate_items = list(_mapping(diagnostics.get("candidate_diagnostics")).items())
    candidate_items.extend((item.get("symbol"), item) for item in evidence.candidates)
    for key, raw in candidate_items:
        item = _mapping(raw)
        symbol = item.get("symbol") or key
        status = str(item.get("status") or "").strip().lower()
        if status in {"selected", "rejected", "evaluated"}:
            add(evaluated, symbol)
            add(sufficient, symbol)
        elif status:
            reasons = item.get("missing_fields") or item.get("failed_rules") or ()
            reason = reasons[0] if isinstance(reasons, Sequence) and not isinstance(reasons, (str, bytes, bytearray)) and reasons else status
            add_skipped(symbol, reason)
    for item in ohlcv.get("symbolStates") or ():
        if isinstance(item, Mapping) and str(item.get("overallState") or "").strip().lower() == "ready":
            add(sufficient, item.get("symbol"))

    scanner_data = _mapping(diagnostics.get("scanner_data"))
    resolution = _mapping(scanner_data.get("universe_resolution"))
    source = str(diagnostics.get("universeSource") or resolution.get("universeSource") or resolution.get("source") or diagnostics.get("stock_list_source") or "unknown")
    universe_values = diagnostics.get("boundedStarterUniverse") or resolution.get("boundedStarterUniverse") or resolution.get("resolvedStarterSymbols") or resolution.get("data") or ()
    universe_symbols = _text_list(universe_values, upper=True)
    resolved_symbols = _text_list(resolution.get("resolvedStarterSymbols") or resolution.get("data") or (), upper=True)
    strategy = str(resolution.get("coverage_strategy") or "").strip()
    bounded = source == "bounded_starter_market_data_spine" or strategy == "bounded_starter_local_only"
    bounded = bounded or bool(universe_symbols and universe_symbols == list(evidence.bounded_us_symbols))
    universe_mode = "bounded_starter_local" if bounded else strategy or "default"
    if bounded:
        active = set(resolved_symbols or evaluated or sufficient)
        for symbol in universe_symbols:
            if symbol not in active:
                add_skipped(symbol, "missing_cache")
    return {
        "source": source, "universeSource": source, "universeMode": universe_mode,
        "universeSymbols": universe_symbols,
        "generatedAt": diagnostics.get("generatedAt") or diagnostics.get("completedAt"),
        "runId": diagnostics.get("runId"),
        "symbolsEvaluated": evaluated[:50], "symbolsWithSufficientData": sufficient[:50],
        "symbolsSkipped": skipped[:50],
        "universeVersion": resolution.get("universeVersion") or resolution.get("activeUniverseVersion"),
        "sourceClass": resolution.get("sourceClass"),
        "sourceArtifactIdentity": resolution.get("sourceArtifactIdentity"),
        "asOf": resolution.get("asOf") or resolution.get("sourceAsOf"),
        "freshnessState": resolution.get("freshnessState"),
    }


def _non_production_limitation(source_markers: Sequence[str]) -> str | None:
    normalized = " ".join(str(value or "").strip().lower() for value in source_markers)
    if any(marker in normalized for marker in _SYNTHETIC_MARKERS):
        return "synthetic_evidence"
    if any(marker in normalized for marker in _FIXTURE_MARKERS):
        return "fixture_evidence"
    return None


def evaluate_scanner_readiness(evidence: ScannerReadinessEvidence) -> EvaluatedScannerReadiness:
    diagnostics = evidence.diagnostics
    coverage_summary = _mapping(diagnostics.get("coverage_summary"))
    reason_counts = _reason_counts(coverage_summary)
    summary_selected, rejected_count, failed_count = _status_counts(evidence.summary, evidence.candidates)
    selected_count = summary_selected
    if not (selected_count or 0) and evidence.shortlist_size is not None:
        selected_count = _optional_int(evidence.shortlist_size)
    evaluated_count = _optional_int(evidence.summary.get("evaluated_count")) if "evaluated_count" in evidence.summary else evidence.evaluated_size
    if (evaluated_count or 0) <= 0 and evidence.evaluated_size is not None:
        evaluated_count = _optional_int(evidence.evaluated_size)

    universe_size = _optional_int(evidence.universe_size)
    if (universe_size or 0) <= 0:
        eligible_size = _optional_int(coverage_summary.get("eligible_after_liquidity_filter"))
        input_size = _optional_int(coverage_summary.get("input_universe_size"))
        if (eligible_size or 0) > 0:
            universe_size = eligible_size
        elif str(evidence.status or "").strip().lower() == "completed" and (input_size or 0) > 0:
            universe_size = input_size

    status = str(evidence.status or "").strip().lower() or "unknown"
    selected = selected_count or 0
    evaluated = evaluated_count or 0
    resolved_size = universe_size or 0
    blocker = _blocker(status, diagnostics, reason_counts, resolved_size, selected)
    quote = _quote_coverage(
        diagnostics, evidence.quote_snapshot_readiness, status, selected, evaluated, blocker
    )
    history = _history_coverage(diagnostics, status, evaluated, reason_counts, blocker)

    if status == "not_run":
        state = "not_run"
    elif blocker != "unknown" and (selected <= 0 or status in {"empty", "failed"}):
        state = "blocked"
    elif status == "completed" and selected > 0 and quote == history == "available":
        state = "ready"
    elif status == "completed" and selected > 0:
        state = "partial"
    elif status in {"empty", "failed"}:
        state = "blocked"
    else:
        state = "unknown"
    freshness = _freshness(status, quote, history, blocker, diagnostics)

    ohlcv = evidence.ohlcv_readiness
    existing = _mapping(diagnostics.get("dataReadiness"))
    requirements = _text_list(ohlcv.get("missingRequirements") or existing.get("missingRequirements") or ())
    ohlcv_availability = str(ohlcv.get("availabilityState") or existing.get("availabilityState") or "unknown")
    ohlcv_execution = str(ohlcv.get("executionState") or existing.get("executionState") or "unknown")
    required_bars = _optional_int(ohlcv.get("requiredBars"))
    usable_bars = _optional_int(ohlcv.get("usableBars"))
    missing_bars = _optional_int(ohlcv.get("missingBars"))
    if (
        ohlcv_availability in {"available", "degraded"}
        and history == "unknown"
        and (usable_bars or 0) >= (required_bars or 0)
        and (missing_bars or 0) <= 0
    ):
        history = "available"
    if ohlcv_execution == "blocked" and status != "not_run":
        state = "blocked"
        blocker = next((item for item in _BLOCKING_OHLCV_PRIORITY if item in requirements), blocker)
        history = "missing"
    elif ohlcv_execution == "degraded" and state == "ready":
        state = "partial"
        blocker = next((item for item in ("stale_data", "missing_adjustments", "missing_benchmark") if item in requirements), blocker)
        history = "partial" if history == "available" else history
    if "stale_data" in requirements:
        freshness = "stale"

    universe = "available" if resolved_size > 0 else "unknown"
    cache = evidence.cache_universe_readiness
    cache_status = str(cache.get("status") or "unavailable")
    universe_selection = _mapping(diagnostics.get("universe_selection"))
    universe_type = str(universe_selection.get("universe_type") or "default").strip().lower()
    uses_default = universe_type == "default"
    uses_cn_default = evidence.market.lower() == "cn" and uses_default
    uses_us_default = evidence.market.lower() == "us" and uses_default
    if cache_status in {"available", "insufficient_coverage", "local_universe_available", "local_universe_seeded"}:
        cached_size = _projected_int(cache.get("universeSize"))
        if resolved_size <= 0 and cached_size > 0:
            resolved_size = cached_size
            universe_size = cached_size
            universe = "available"
        if blocker in {"missing_universe", "universe_missing"} and status == "not_run":
            blocker = "unknown"
    if status == "not_run":
        universe = "missing" if resolved_size <= 0 else "available"
    elif blocker in {"missing_universe", "universe_missing"}:
        universe = "missing"
    elif blocker == "empty_universe":
        universe = "empty"
    elif status not in {"completed", "empty", "failed"}:
        universe = "unknown"
    if uses_cn_default and cache_status in {"missing", "stale", "not_configured", "unavailable"}:
        universe = "stale" if cache_status == "stale" else "missing"
        blocker = "stale_universe" if cache_status == "stale" else "universe_not_configured" if cache_status == "not_configured" else "universe_missing"
        freshness = "stale" if cache_status == "stale" else freshness
        if status != "completed" or selected <= 0:
            state = "blocked"
    if status in {"completed", "empty", "failed", "not_run"} and resolved_size <= 0 and not cache:
        universe = "missing"
    if universe in {"missing", "empty", "stale"} and status != "not_run":
        state = "blocked"

    benchmark_context = _mapping(diagnostics.get("benchmark_context"))
    benchmark_code = str(benchmark_context.get("benchmark_code") or "").strip() or None
    benchmark_missing = "missing_benchmark" in requirements or bool(benchmark_code and benchmark_context.get("available") is not True)
    benchmark_state = "missing" if benchmark_missing else "available" if benchmark_code and benchmark_context.get("available") is True else "unknown"
    seeded_symbols, eligible_symbols, ohlcv_blocked_symbols = _ohlcv_symbols(ohlcv)
    owner_quote_state = str(evidence.quote_snapshot_readiness.get("availabilityState") or "").strip().lower()
    quote_available = _text_list(evidence.quote_snapshot_readiness.get("availableSymbols") or (), upper=True, limit=50)
    quote_missing = _text_list(evidence.quote_snapshot_readiness.get("missingSymbols") or (), upper=True, limit=50)
    quote_stale = _text_list(evidence.quote_snapshot_readiness.get("staleSymbols") or (), upper=True, limit=50)
    quote_sources = [str(item) for item in evidence.quote_snapshot_readiness.get("sourceFamilies") or ()][:10]
    if (
        owner_quote_state == "available"
        and blocker == "missing_quote_snapshot"
        and status not in {"empty", "failed"}
    ):
        blocker = "unknown"
    elif owner_quote_state == "stale":
        freshness = "stale"
        if blocker == "missing_quote_snapshot":
            blocker = "stale_quote_snapshot"

    optional_us_quote = (
        evidence.market.lower() == "us" and status == "completed" and selected > 0
        and history in {"available", "partial"} and quote in {"missing", "stale"}
    )
    if optional_us_quote and blocker in {"missing_quote_snapshot", "stale_quote_snapshot"}:
        blocker = "unknown"
    universe_reason = {"missing": "universe_missing", "stale": "stale_universe", "empty": "empty_universe", "available": "universe_available"}.get(universe, "universe_unknown")

    blockers: list[str] = []
    limitations: list[str] = []
    if universe in {"missing", "empty", "stale"}:
        blockers.append(universe_reason)
    if quote in {"missing", "stale"}:
        quote_blocker = "missing_quote_snapshot" if quote == "missing" else "stale_quote_snapshot"
        (limitations if optional_us_quote else blockers).append("quote_unavailable_or_stale" if optional_us_quote else quote_blocker)
    if owner_quote_state == "available" and status in {"empty", "failed"} and reason_counts.get("missing_quote_or_snapshot", 0) > 0:
        blockers.append("missing_quote_snapshot")
    if blocker == "missing_quote_snapshot" and status in {"empty", "failed"}:
        blockers.append("missing_quote_snapshot")
    if history == "missing":
        blockers.append("missing_history")
    blockers.extend(requirements)
    if benchmark_missing:
        blockers.append("missing_benchmark")
    if blocker != "unknown" and blocker not in blockers:
        blockers.append(blocker)
    factor_blockers, factor_blocked_symbols = _factor_evidence_blockers(evidence.candidates)
    blockers.extend(factor_blockers)
    blockers = list(dict.fromkeys(blockers))
    if factor_blockers and selected <= 0:
        state = "blocked"
        blocker = factor_blockers[0]
    limitation = _non_production_limitation(evidence.source_markers)
    if limitation:
        limitations.append(limitation)
        if state == "ready":
            state = "partial"
    limitations = list(dict.fromkeys(limitations))

    exact_blocked_states = _blocked_states(status, blockers, selected, universe)
    missing_families = _missing_data_families(universe, quote, history, benchmark_missing, requirements, blockers)
    operator_action = _operator_action(
        cache_status, quote, benchmark_missing, requirements, len(eligible_symbols), len(seeded_symbols)
    )
    universe_status = (
        cache_status
        if cache_status in {"local_universe_available", "local_universe_seeded"}
        else "quote_snapshot_stale"
        if quote == "stale" and universe == "available"
        else "provider_not_configured"
        if "provider_missing" in requirements and universe == "available"
        else "available"
        if universe == "available"
        else "stale"
        if universe == "stale"
        else cache_status
        if (uses_cn_default or uses_us_default) and cache_status in {"missing", "stale", "not_configured", "unavailable"}
        else "missing"
    )
    scanner_universe = build_scanner_universe_readiness_from_coverage(
        market=evidence.market,
        universe_status=universe_status,
        universe_size=resolved_size or _projected_int(cache.get("universeSize")),
        last_updated_at=cache.get("lastUpdatedAt"),
        freshness_state=str(cache.get("freshnessState") or freshness),
        quote_coverage=quote,
        history_coverage=history,
        blocked=bool(blockers),
        historical_requirements=requirements,
        seeded_symbols=seeded_symbols,
        eligible_symbols=eligible_symbols,
        blocked_symbols=list(dict.fromkeys([*ohlcv_blocked_symbols, *factor_blocked_symbols])),
        missing_data_families=missing_families,
        operator_next_action=operator_action,
        source_metadata=_thaw(cache.get("sourceMetadata")) if isinstance(cache.get("sourceMetadata"), Mapping) else None,
    )
    if scanner_universe["status"] == "insufficient_coverage" and blocker == "unknown" and status != "not_run":
        blocker = "insufficient_coverage"

    if state == "ready" and not blockers and not limitations:
        candidate_state = "ready"
    elif selected > 0 and not blockers and limitations:
        candidate_state = "degraded"
    elif state == "partial" and not _CRITICAL_CANDIDATE_BLOCKERS.intersection(blockers):
        candidate_state = "degraded"
    elif status == "not_run" and not blockers:
        candidate_state = "not_run"
    else:
        candidate_state = "blocked"
    cache_readiness = _cache_readiness(state, requirements, history, freshness)
    consumer_summary, next_action = _copy(blocker, state)
    lineage = _lineage(evidence, ohlcv)

    availability_state = ohlcv_availability if ohlcv_availability != "unknown" else {"ready": "available", "partial": "degraded", "blocked": "not_available"}.get(state, "unknown")
    execution_state = ohlcv_execution if ohlcv_execution != "unknown" else {"ready": "executable", "partial": "degraded", "blocked": "blocked"}.get(state, "unknown")
    if limitation and availability_state == "available":
        availability_state = "degraded"
    if limitation and execution_state == "executable":
        execution_state = "degraded"
    market = str(evidence.market or "").strip().lower() or "unknown"
    profile = str(evidence.profile or "").strip() or "unknown"
    quote_reason = {"missing": "missing_quote_snapshot", "stale": "stale_quote_snapshot", "partial": "quote_partial", "available": "quote_available"}.get(quote, "quote_unknown")
    history_reason = {"missing": "missing_history", "partial": "history_partial", "available": "history_available"}.get(history, "history_unknown")
    benchmark_reason = {"missing": "missing_benchmark", "available": "benchmark_available"}.get(benchmark_state, "benchmark_unknown")
    lineage_payload = _thaw(lineage)
    payload = {
        "state": state, "availabilityState": availability_state, "executionState": execution_state,
        "market": market, "profile": profile,
        "universeAvailability": universe, "universeSize": _projected_int(universe_size),
        "quoteCoverage": quote, "historyCoverage": history,
        "universeReadiness": {"state": universe, "reason": universe_reason, "universeSize": _projected_int(universe_size), "consumerSafe": True},
        "scannerUniverseReadiness": _thaw(scanner_universe),
        "quoteReadiness": {"state": quote, "reason": quote_reason, "availableSymbols": quote_available, "missingSymbols": quote_missing, "staleSymbols": quote_stale, "sourceFamilies": quote_sources, "consumerSafe": True},
        "historyReadiness": {"state": history, "reason": history_reason, "requiredBars": _projected_int(required_bars), "usableBars": _projected_int(usable_bars), "missingBars": _projected_int(missing_bars), "missingRequirements": requirements, "consumerSafe": True},
        "cacheReadiness": cache_readiness,
        "benchmarkReadiness": {"state": benchmark_state, "reason": benchmark_reason, "benchmarkCode": benchmark_code, "consumerSafe": True},
        "candidateGenerationState": candidate_state, "candidateGenerationBlockers": blockers,
        "candidateGenerationLimitations": limitations, "blockedStates": exact_blocked_states,
        "primaryBlockedState": exact_blocked_states[0] if exact_blocked_states else None,
        "freshness": freshness, "quoteFreshness": diagnostics.get("quoteFreshness") or quote,
        "quoteReadinessLimitation": diagnostics.get("quoteReadinessLimitation"),
        "universeSource": diagnostics.get("universeSource") or lineage["universeSource"],
        "scannerLineage": lineage_payload, "symbolsEvaluated": lineage_payload["symbolsEvaluated"],
        "symbolsWithSufficientData": lineage_payload["symbolsWithSufficientData"],
        "symbolsSkipped": lineage_payload["symbolsSkipped"],
        "noExternalCalls": bool(diagnostics.get("noExternalCalls")) if diagnostics.get("noExternalCalls") is not None else False,
        "providerCallsEnabled": bool(diagnostics.get("providerCallsEnabled")) if diagnostics.get("providerCallsEnabled") is not None else True,
        "historicalOhlcvReadinessSummary": _thaw(ohlcv),
        "requiredBars": _projected_int(required_bars), "usableBars": _projected_int(usable_bars),
        "missingBars": _projected_int(missing_bars),
        "missingRequirements": requirements,
        "blockedSymbols": list(dict.fromkeys([*list(ohlcv.get("blockedSymbols") or ()), *factor_blocked_symbols])),
        "degradedSymbols": list(ohlcv.get("degradedSymbols") or ()),
        "ohlcvReadiness": _thaw(ohlcv),
        "candidateEvaluationCount": _projected_int(evaluated_count), "selectedCount": _projected_int(selected_count),
        "rejectedCount": _projected_int(rejected_count), "failedCount": _projected_int(failed_count),
        "blockerBucket": blocker,
        "consumerSummary": consumer_summary,
        "nextDataAction": next_action,
    }
    return EvaluatedScannerReadiness(
        state=state, availability_state=availability_state, execution_state=execution_state,
        universe_availability=universe, universe_size=universe_size,
        quote_coverage=quote, history_coverage=history,
        candidate_generation_state=candidate_state,
        candidate_generation_blockers=tuple(blockers),
        candidate_generation_limitations=tuple(limitations),
        freshness=freshness,
        required_bars=required_bars, usable_bars=usable_bars, missing_bars=missing_bars,
        candidate_evaluation_count=evaluated_count,
        selected_count=selected_count, rejected_count=rejected_count, failed_count=failed_count,
        blocker_bucket=blocker,
        payload=payload,
    )


def serialize_scanner_readiness(result: EvaluatedScannerReadiness) -> dict[str, Any]:
    return _thaw(result.payload)


__all__ = ["EvaluatedScannerReadiness", "ScannerReadinessEvidence", "evaluate_scanner_readiness", "serialize_scanner_readiness"]
