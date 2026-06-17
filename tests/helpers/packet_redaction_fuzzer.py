# -*- coding: utf-8 -*-
"""Shared redaction-boundary assertions for consumer-visible research packets."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Pattern


REQUIRED_REDACTION_CATEGORIES = frozenset(
    {
        "raw_diagnostic",
        "advice_wording",
        "internal_reason_code",
        "admin_diagnostic_key",
        "raw_json_dump",
    }
)

_RAW_DIAGNOSTIC_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\bprovider(?:runtime|trace|diagnostics|state|route|payload)?\b", re.IGNORECASE),
    re.compile(r"\bmarketcache\b|\bcache(?:[-_ ]?(?:key|hit|miss|state|snapshot|payload))?\b", re.IGNORECASE),
    re.compile(
        r"\b(?:runtime|debug|trace|schema(?:version)?|raw(?:[-_ ]?(?:payload|diagnostics|dump|result|response|body))?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bsourceRef(?:Id|Ids)?\b", re.IGNORECASE),
    re.compile(r"\brequestId\b|\brequest[-_ ]?id\b", re.IGNORECASE),
    re.compile(r"\btraceId\b|\btrace[-_ ]?id\b", re.IGNORECASE),
)
_ADVICE_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(
        r"\b(?:buy|sell|hold|recommend(?:ation|ed)?|target(?: price)?|stop(?: loss)?|position[-\s]?sizing)\b",
        re.IGNORECASE,
    ),
    re.compile(r"买入|卖出|持有|推荐|交易建议|投资建议|目标价|止损|止盈|仓位|下单|立即交易|必买|稳赚|保证收益"),
)
_INTERNAL_REASON_CODE_PATTERN = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_ADMIN_DIAGNOSTIC_KEY_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(
        r"^(?:raw_payload|rawPayload|rawProviderPayload|rawJsonDump|adminDiagnostics|internalDiagnostics|"
        r"providerDiagnostics|providerTrace|debugRef|traceId|requestId|sourceRef(?:Id|Ids)?|"
        r"reasonCodes?|reasonFamilies|schemaVersion)$",
        re.IGNORECASE,
    ),
)
_RAW_JSON_DUMP_PATTERN = re.compile(r"^\s*[\[{].*[\]}]\s*$", re.DOTALL)
_RAW_JSON_DUMP_DIAGNOSTIC_FIELD = re.compile(
    r'"(?:raw[_A-Za-z]*|provider[A-Za-z]*|debug[A-Za-z]*|trace[A-Za-z]*|schemaVersion|'
    r'sourceRef(?:Id|Ids)?|requestId|adminDiagnostics)"\s*:',
    re.IGNORECASE,
)

_FUZZER_STRINGS: tuple[str, ...] = (
    "provider runtime debug trace sourceRef=src-raw requestId=req-raw traceId=trace-raw",
    "MarketCache cache_key=raw-cache-key schemaVersion=diagnostic_packet_v9",
    '{"raw_payload": {"providerDiagnostics": "leak", "schemaVersion": "raw_v9", "requestId": "REQ-1"}}',
    "buy sell hold recommend target price stop loss position sizing",
    "买入 卖出 持有 交易建议 投资建议 目标价 止损 仓位",
    "provider_timeout source_authority_missing score_rights_missing internal_debug_reason",
    "adminDiagnostics rawProviderPayload providerTrace debugRef sourceRefIds requestId",
)


@dataclass(frozen=True)
class PacketRedactionLeak:
    """A single forbidden token observed in a consumer-visible packet fragment."""

    surface: str
    path: str
    category: str
    pattern: str
    text: str


def redaction_fuzzer_strings() -> tuple[str, ...]:
    """Return adversarial strings spanning raw diagnostics, advice, and reason codes."""

    return _FUZZER_STRINGS


def redaction_fuzzer_payload() -> dict[str, Any]:
    """Return a reusable adversarial payload for packet-builder inputs."""

    return {
        "providerDiagnostics": _FUZZER_STRINGS[0],
        "cacheRuntimeTrace": _FUZZER_STRINGS[1],
        "rawJsonDump": _FUZZER_STRINGS[2],
        "actionWording": _FUZZER_STRINGS[3],
        "cnActionWording": _FUZZER_STRINGS[4],
        "internalReasonCodes": _FUZZER_STRINGS[5].split(),
        "adminDiagnostics": {
            "raw_payload": {"provider": "debug-provider", "requestId": "REQ-RAW-1"},
            "providerTrace": "trace debug payload",
            "sourceRefIds": ["sourceRef-raw-1"],
        },
    }


def collect_packet_redaction_leaks(
    payload: Any,
    *,
    surface: str = "packet",
    include_keys: bool = True,
    allowed_value_patterns: Iterable[str | Pattern[str]] = (),
    allowed_key_patterns: Iterable[str | Pattern[str]] = (),
) -> list[PacketRedactionLeak]:
    """Collect forbidden redaction-boundary terms from a visible packet fragment."""

    compiled_allowed_values = _compile_patterns(allowed_value_patterns)
    compiled_allowed_keys = _compile_patterns(allowed_key_patterns)
    leaks: list[PacketRedactionLeak] = []
    for path, text, is_key in _iter_text_nodes(payload, surface, include_keys=include_keys):
        if is_key and _is_allowed(text, compiled_allowed_keys):
            continue
        if not is_key and _is_allowed(text, compiled_allowed_values):
            continue
        leaks.extend(_classify_text(surface=surface, path=path, text=text, is_key=is_key))
    return leaks


def assert_packet_output_redacted(
    payload: Any,
    *,
    surface: str = "packet",
    include_keys: bool = True,
    allowed_value_patterns: Iterable[str | Pattern[str]] = (),
    allowed_key_patterns: Iterable[str | Pattern[str]] = (),
) -> None:
    """Assert a consumer-visible packet fragment has no raw diagnostics or advice wording."""

    leaks = collect_packet_redaction_leaks(
        payload,
        surface=surface,
        include_keys=include_keys,
        allowed_value_patterns=allowed_value_patterns,
        allowed_key_patterns=allowed_key_patterns,
    )
    if not leaks:
        return
    details = "\n".join(
        f"- {leak.category} at {leak.path}: matched {leak.pattern!r} in {_shorten(leak.text)!r}"
        for leak in leaks[:12]
    )
    remaining = "" if len(leaks) <= 12 else f"\n... {len(leaks) - 12} more leak(s)"
    raise AssertionError(f"{surface} leaked redaction-forbidden packet output:\n{details}{remaining}")


def _classify_text(*, surface: str, path: str, text: str, is_key: bool) -> list[PacketRedactionLeak]:
    leaks: list[PacketRedactionLeak] = []
    if is_key:
        for pattern in _ADMIN_DIAGNOSTIC_KEY_PATTERNS:
            if pattern.search(text):
                leaks.append(_leak(surface, path, "admin_diagnostic_key", pattern, text))
    for pattern in _RAW_DIAGNOSTIC_PATTERNS:
        if pattern.search(text):
            leaks.append(_leak(surface, path, "raw_diagnostic", pattern, text))
    for pattern in _ADVICE_PATTERNS:
        if pattern.search(text):
            leaks.append(_leak(surface, path, "advice_wording", pattern, text))
    if not is_key and _INTERNAL_REASON_CODE_PATTERN.search(text):
        leaks.append(_leak(surface, path, "internal_reason_code", _INTERNAL_REASON_CODE_PATTERN, text))
    if (
        not is_key
        and _RAW_JSON_DUMP_PATTERN.search(text)
        and _RAW_JSON_DUMP_DIAGNOSTIC_FIELD.search(text)
    ):
        leaks.append(_leak(surface, path, "raw_json_dump", _RAW_JSON_DUMP_DIAGNOSTIC_FIELD, text))
    return leaks


def _iter_text_nodes(payload: Any, path: str, *, include_keys: bool) -> Iterable[tuple[str, str, bool]]:
    if isinstance(payload, str):
        yield path, payload, False
        return
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_text = str(key)
            child_path = _join_path(path, key_text)
            if include_keys:
                yield child_path, key_text, True
            yield from _iter_text_nodes(value, child_path, include_keys=include_keys)
        return
    if isinstance(payload, Sequence) and not isinstance(payload, (bytes, bytearray)):
        for index, value in enumerate(payload):
            yield from _iter_text_nodes(value, f"{path}[{index}]", include_keys=include_keys)


def _leak(
    surface: str,
    path: str,
    category: str,
    pattern: Pattern[str],
    text: str,
) -> PacketRedactionLeak:
    return PacketRedactionLeak(
        surface=surface,
        path=path,
        category=category,
        pattern=pattern.pattern,
        text=text,
    )


def _join_path(path: str, key: str) -> str:
    if not path:
        return key
    return f"{path}.{key}"


def _compile_patterns(patterns: Iterable[str | Pattern[str]]) -> tuple[Pattern[str], ...]:
    compiled: list[Pattern[str]] = []
    for pattern in patterns:
        compiled.append(re.compile(pattern) if isinstance(pattern, str) else pattern)
    return tuple(compiled)


def _is_allowed(text: str, patterns: Sequence[Pattern[str]]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _shorten(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else f"{compact[: limit - 3]}..."


__all__ = [
    "PacketRedactionLeak",
    "REQUIRED_REDACTION_CATEGORIES",
    "assert_packet_output_redacted",
    "collect_packet_redaction_leaks",
    "redaction_fuzzer_payload",
    "redaction_fuzzer_strings",
]
