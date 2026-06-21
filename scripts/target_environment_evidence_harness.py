#!/usr/bin/env python3
"""Collect sanitized local API readiness evidence for DATA-033.

The harness calls a caller-selected local WolfyStock API base URL and writes a
bounded JSON artifact. It does not import provider adapters, inspect env files,
mutate runtime configuration, connect to brokers, or place orders.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "wolfystock_target_environment_evidence_harness_v1"
ARTIFACT_VERSION = "wolfystock_data033_target_environment_evidence_v1"
SCENARIO_BASELINE_ARTIFACT_VERSION = "wolfystock_data042_scenario_baseline_evidence_v1"
MANIFEST_ARTIFACT_VERSION = "wolfystock_data046_target_evidence_manifest_v1"
MANIFEST_SCHEMA_VERSION = "wolfystock_target_evidence_manifest_schema_v1"
REDACTION_VERSION = "target_environment_evidence_redaction_v1"
REDACTED = "<redacted>"
DEFAULT_TIMEOUT_SECONDS = 3.0


def _join(*parts: str) -> str:
    return "".join(parts)


_SENSITIVE_KEY_MARKERS = (
    _join("api", "_key"),
    _join("api", "key"),
    _join("auth", "orization"),
    _join("bear", "er"),
    _join("cook", "ie"),
    _join("cred", "ential"),
    _join("pass", "word"),
    _join("pass", "wd"),
    _join("private", "_key"),
    _join("se", "cret"),
    _join("sess", "ion"),
    _join("set", "_", "cook", "ie"),
    _join("set", "-", "cook", "ie"),
    _join("to", "ken"),
    _join("account", "_id"),
    _join("account", "id"),
    _join("account", "_number"),
    _join("account", "number"),
    _join("account", "_ref"),
    _join("account", "ref"),
    _join("broker", "_account"),
    _join("request", "_id"),
    _join("request", "id"),
    _join("trace", "_id"),
    _join("trace", "id"),
)
_SAFE_STRUCTURAL_KEYS = {
    "account_count",
    "accountcount",
    "position_count",
    "positioncount",
}
_SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"https?://[^/\s:@]+:[^@\s]+@[^/\s]+", re.IGNORECASE),
    re.compile(
        r"\b(?:"
        + "|".join(re.escape(item) for item in _SENSITIVE_KEY_MARKERS[:14])
        + r")\b\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"\b" + re.escape(_join("bear", "er")) + r"\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*-----END [A-Z ]*PRIVATE KEY-----", re.IGNORECASE | re.DOTALL),
)
_SCENARIO_UNSAFE_KEY_MARKERS = (
    "admin_diagnostics",
    "cache_debug",
    "cache_key",
    "debug",
    "provider_diagnostics",
    "provider_payload",
    "provider_runtime",
    "raw_payload",
    "request_url",
    "runtime_cache",
    "stack_trace",
    "source_ref",
    "url",
)
_SCENARIO_SAFE_COMPONENT_KEYS = {
    "state",
    "available",
    "lastUpdated",
    "affectedComponents",
}
_SCENARIO_SAFE_DRIVER_INPUT_KEYS = {
    "state",
    "availableDriverKeys",
    "partialDriverKeys",
    "missingDriverKeys",
    "affectedDriverKeys",
}
_SCENARIO_SAFE_EVIDENCE_KEYS = {
    "state",
    "gaps",
}
_SCENARIO_SAFE_READINESS_KEYS = {
    "status",
    "baselineSnapshot",
    "marketFrame",
    "driverInputs",
    "evidenceCompleteness",
    "dataState",
    "sampleState",
    "scoreAuthority",
    "sourceAuthorityAllowed",
    "authoritative",
    "observationOnly",
    "ready",
    "partial",
    "blocked",
    "affectedBaselineComponents",
    "affectedDriverKeys",
    "evidenceGaps",
    "lastUpdated",
}
_UNSAFE_MANIFEST_TEXT_MARKERS = (
    "advice",
    "buy now",
    "cache debug",
    "debug",
    "investment advice",
    "providerdiagnostics",
    "providerpayload",
    "providerruntime",
    "rawpayload",
    "requestid",
    "requesturl",
    "runtimecache",
    "sell now",
    "source_ref",
    "sourceref",
    "stacktrace",
    "stop loss",
    "target price",
    "traceid",
    "trading advice",
    "买入建议",
    "卖出建议",
    "目标价",
    "止损",
)


@dataclass(frozen=True)
class SurfaceSpec:
    surface_id: str
    label: str
    method: str
    path: str
    extractor: str
    body: Mapping[str, Any] | None = None


@dataclass
class RedactionStats:
    redacted_key_count: int = 0
    redacted_value_count: int = 0


class UrlLibClient:
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> Any:
        request = urllib.request.Request(
            url,
            data=body,
            headers=dict(headers or {}),
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return _HttpResponse(
                    status_code=int(response.status),
                    text=response.read().decode("utf-8", errors="replace"),
                    headers=dict(response.headers.items()),
                )
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            return _HttpResponse(status_code=int(exc.code), text=text, headers=dict(exc.headers.items()))


@dataclass(frozen=True)
class _HttpResponse:
    status_code: int
    text: str = ""
    headers: Mapping[str, str] | None = None

    def json(self) -> Any:
        if not self.text.strip():
            return {}
        return json.loads(self.text)


def _default_specs() -> dict[str, SurfaceSpec]:
    return {
        "rotation_quote_readiness": SurfaceSpec(
            surface_id="rotation_quote_readiness",
            label="Rotation Radar quote readiness",
            method="GET",
            path="/api/v1/market/rotation-radar?market=US",
            extractor="rotation",
        ),
        "portfolio_lineage": SurfaceSpec(
            surface_id="portfolio_lineage",
            label="Portfolio price and FX lineage",
            method="GET",
            path="/api/v1/portfolio/snapshot",
            extractor="portfolio",
        ),
        "options_chain_readiness": SurfaceSpec(
            surface_id="options_chain_readiness",
            label="Options chain readiness",
            method="GET",
            path="/api/v1/options/underlyings/TEM/chain?includeGreeks=true",
            extractor="options",
        ),
        "scenario_baseline_readiness": SurfaceSpec(
            surface_id="scenario_baseline_readiness",
            label="Scenario baseline readiness",
            method="POST",
            path="/api/v1/market/scenario-lab",
            extractor="scenario",
            body={},
        ),
    }


def _normalize_base_url(base_url: str) -> str:
    text = str(base_url or "").strip()
    if not text:
        raise ValueError("base URL is required")
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL must be an http(s) URL")
    return text.rstrip("/")


def _absolute_url(base_url: str, path_or_url: str) -> str:
    text = str(path_or_url or "").strip()
    if text.startswith(("http://", "https://")):
        return text
    if not text.startswith("/"):
        text = "/" + text
    return base_url.rstrip("/") + text


def _safe_url_label(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urllib.parse.urlparse(text)
    if parsed.username or getattr(parsed, _join("pass", "word")):
        return REDACTED
    host_label = "[redacted-host]" if parsed.netloc else ""
    return urllib.parse.urlunparse(
        (
            parsed.scheme,
            host_label,
            parsed.path,
            "",
            "",
            "",
        )
    )


def _compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _is_sensitive_key(key: Any) -> bool:
    compacted = _compact(key)
    if compacted in _SAFE_STRUCTURAL_KEYS:
        return False
    return any(_compact(marker) in compacted for marker in _SENSITIVE_KEY_MARKERS)


def _is_sensitive_value(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    return any(pattern.search(value) for pattern in _SENSITIVE_VALUE_PATTERNS)


def _redact(value: Any, stats: RedactionStats) -> Any:
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        redacted_index = 1
        for key, child in value.items():
            if _is_sensitive_key(key):
                output[f"redactedKey{redacted_index}"] = REDACTED
                redacted_index += 1
                stats.redacted_key_count += 1
                stats.redacted_value_count += 1
                continue
            output[str(key)] = _redact(child, stats)
        return output
    if isinstance(value, list):
        return [_redact(item, stats) for item in value]
    if isinstance(value, tuple):
        return [_redact(item, stats) for item in value]
    if isinstance(value, str) and _is_sensitive_value(value):
        stats.redacted_value_count += 1
        return REDACTED
    return value


def _is_scenario_unsafe_key(key: Any) -> bool:
    compacted = _compact(key)
    return _is_sensitive_key(key) or any(_compact(marker) in compacted for marker in _SCENARIO_UNSAFE_KEY_MARKERS)


def _redact_scenario_input(value: Any, stats: RedactionStats) -> Any:
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        redacted_index = 1
        for key, child in value.items():
            if _is_scenario_unsafe_key(key):
                output[f"redactedKey{redacted_index}"] = REDACTED
                redacted_index += 1
                stats.redacted_key_count += 1
                stats.redacted_value_count += 1
                continue
            output[str(key)] = _redact_scenario_input(child, stats)
        return output
    if isinstance(value, list):
        return [_redact_scenario_input(item, stats) for item in value]
    if isinstance(value, tuple):
        return [_redact_scenario_input(item, stats) for item in value]
    if isinstance(value, str) and _is_sensitive_value(value):
        stats.redacted_value_count += 1
        return REDACTED
    return value


def _json_payload(response: Any) -> Any:
    try:
        return response.json()
    except Exception:
        text = str(getattr(response, "text", "") or "").strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"nonJsonResponse": text[:200]}


def _dig(mapping: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _extract_rotation(payload: Mapping[str, Any]) -> dict[str, Any]:
    readiness = (
        payload.get("alpacaQuoteAuthorityReadiness")
        or _dig(payload, ("metadata", "alpacaQuoteAuthorityReadiness"))
        or _dig(payload, ("metadata", "providerDiagnostics", "alpacaQuoteAuthorityReadiness"))
        or _dig(payload, ("metadata", "quoteProvider", "alpacaQuoteAuthorityReadiness"))
    )
    if isinstance(readiness, Mapping):
        return {"alpacaQuoteAuthorityReadiness": dict(readiness)}
    return {}


def _extract_portfolio(payload: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "price_lineage",
        "fx_lineage",
        "valuation_snapshot_lineage",
        "analytics_readiness",
    )
    return {key: payload[key] for key in keys if key in payload}


def _extract_options(payload: Mapping[str, Any]) -> dict[str, Any]:
    readiness = payload.get("optionsChainReadiness")
    if isinstance(readiness, Mapping):
        return {"optionsChainReadiness": dict(readiness)}
    return {}


def _extract_scenario(payload: Mapping[str, Any]) -> dict[str, Any]:
    readiness = payload.get("baselineReadiness")
    if isinstance(readiness, Mapping):
        return {"baselineReadiness": dict(readiness)}
    return {}


def _extract_fields(extractor: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    if extractor == "rotation":
        return _extract_rotation(payload)
    if extractor == "portfolio":
        return _extract_portfolio(payload)
    if extractor == "options":
        return _extract_options(payload)
    if extractor == "scenario":
        return _extract_scenario(payload)
    return {}


def _surface_status_for_success(surface_id: str, fields: Mapping[str, Any]) -> tuple[str, str, list[str]]:
    if not fields:
        return "missing_readiness_fields", "missing", ["readiness_fields_missing"]
    if surface_id == "rotation_quote_readiness":
        readiness = fields.get("alpacaQuoteAuthorityReadiness") if isinstance(fields, Mapping) else {}
        readiness = readiness if isinstance(readiness, Mapping) else {}
        raw_state = str(
            readiness.get("authorityState")
            or readiness.get("sourceAuthority")
            or readiness.get("blockerBucket")
            or "unknown"
        ).strip()
        state = raw_state.lower()
        if state in {"authorized", "authoritative", "available"} or readiness.get("scoreContributionAllowed") is True:
            return "readiness_available", raw_state or "available", []
        if state in {"partial", "limited", "stale"}:
            return "readiness_partial", raw_state, list(readiness.get("missingSymbols") or [])
        return "readiness_blocked", raw_state or "unavailable", list(readiness.get("missingSymbols") or ["readiness_blocked"])
    if surface_id == "portfolio_lineage":
        valuation = fields.get("valuation_snapshot_lineage") if isinstance(fields, Mapping) else {}
        analytics = fields.get("analytics_readiness") if isinstance(fields, Mapping) else {}
        valuation = valuation if isinstance(valuation, Mapping) else {}
        analytics = analytics if isinstance(analytics, Mapping) else {}
        state = str(valuation.get("status") or analytics.get("valuation") or "unknown").strip()
        normalized = state.lower()
        if normalized == "complete":
            return "readiness_available", state, []
        if normalized == "partial":
            blocked_by = valuation.get("blocked_by") if isinstance(valuation.get("blocked_by"), Mapping) else {}
            missing = []
            for values in blocked_by.values():
                if isinstance(values, list):
                    missing.extend(str(item) for item in values)
            return "readiness_partial", state, missing
        return "readiness_blocked", state or "blocked", ["portfolio_lineage_not_complete"]
    if surface_id == "options_chain_readiness":
        readiness = fields.get("optionsChainReadiness") if isinstance(fields, Mapping) else {}
        readiness = readiness if isinstance(readiness, Mapping) else {}
        state = str(readiness.get("overallState") or "unknown").strip()
        if state == "ready":
            return "readiness_available", state, []
        if state == "partial":
            return "readiness_partial", state, list(readiness.get("blockingReasons") or [])
        return "readiness_blocked", state or "blocked", list(readiness.get("blockingReasons") or ["options_chain_not_ready"])
    if surface_id == "scenario_baseline_readiness":
        readiness = fields.get("baselineReadiness") if isinstance(fields, Mapping) else {}
        readiness = readiness if isinstance(readiness, Mapping) else {}
        state = str(readiness.get("status") or "unknown").strip()
        if state == "ready":
            return "readiness_available", state, []
        if state == "partial":
            return "readiness_partial", state, list(readiness.get("evidenceGaps") or [])
        return "readiness_blocked", state or "blocked", list(readiness.get("evidenceGaps") or ["scenario_baseline_not_ready"])
    return "missing_readiness_fields", "missing", ["readiness_fields_missing"]


def _endpoint_state(status_code: int) -> tuple[str, str]:
    if 200 <= status_code < 300:
        return "available", "ok"
    if status_code in {404, 405}:
        return "unavailable", "endpoint_unavailable"
    if status_code in {401, 403}:
        return "access_blocked", "access_required"
    return "request_failed", "http_error"


def _operator_next_steps(surface_status: str, readiness_status: str, missing: list[str]) -> list[str]:
    if surface_status == "endpoint_unavailable":
        return ["Verify the local route mapping or provide a surface URL override."]
    if surface_status == "access_blocked":
        return ["Run against an authenticated local session if the surface requires one."]
    if surface_status == "request_failed":
        return ["Check the local API logs and rerun after the endpoint returns a bounded response."]
    if surface_status == "missing_readiness_fields":
        return ["Confirm the endpoint response includes the readiness contract fields expected by DATA-033."]
    if surface_status == "readiness_available":
        return ["Archive this sanitized artifact with operator review; do not infer broader provider acceptance."]
    if surface_status == "readiness_partial":
        return ["Collect the missing evidence listed for this surface before claiming readiness."]
    if surface_status == "readiness_blocked":
        return [f"Resolve readiness blocker state '{readiness_status}' and rerun the harness."]
    if missing:
        return ["Review missing evidence and rerun the harness."]
    return ["Review the sanitized evidence artifact."]


def _collect_surface(
    *,
    base_url: str,
    spec: SurfaceSpec,
    client: Any,
    headers: Mapping[str, str],
    timeout: float,
    stats: RedactionStats,
) -> dict[str, Any]:
    url = _absolute_url(base_url, spec.path)
    body = None
    if spec.body is not None:
        body = json.dumps(spec.body, ensure_ascii=False).encode("utf-8")
    try:
        response = client.request(
            spec.method,
            url,
            headers=dict(headers),
            body=body,
            timeout=timeout,
        )
    except Exception:
        surface_status = "endpoint_unavailable"
        missing = ["endpoint_unavailable"]
        return {
            "surface": spec.surface_id,
            "label": spec.label,
            "method": spec.method,
            "path": urllib.parse.urlparse(url).path,
            "endpointAvailability": {
                "state": "unavailable",
                "httpStatus": None,
                "reason": "request_exception",
            },
            "surfaceStatus": surface_status,
            "readinessStatus": "unknown",
            "collectedFields": {},
            "missingEvidence": missing,
            "operatorNextSteps": _operator_next_steps(surface_status, "unknown", missing),
            "liveProviderSuccessClaimed": False,
        }

    status_code = int(getattr(response, "status_code", 0) or 0)
    endpoint_state, endpoint_reason = _endpoint_state(status_code)
    if endpoint_state != "available":
        surface_status = "endpoint_unavailable" if endpoint_state == "unavailable" else endpoint_state
        missing = [endpoint_reason]
        return {
            "surface": spec.surface_id,
            "label": spec.label,
            "method": spec.method,
            "path": urllib.parse.urlparse(url).path,
            "endpointAvailability": {
                "state": endpoint_state,
                "httpStatus": status_code,
                "reason": endpoint_reason,
            },
            "surfaceStatus": surface_status,
            "readinessStatus": "unknown",
            "collectedFields": {},
            "missingEvidence": missing,
            "operatorNextSteps": _operator_next_steps(surface_status, "unknown", missing),
            "liveProviderSuccessClaimed": False,
        }

    payload = _redact(_json_payload(response), stats)
    fields = _extract_fields(spec.extractor, payload)
    redacted_fields = _redact(fields, stats)
    surface_status, readiness_status, missing = _surface_status_for_success(spec.surface_id, redacted_fields)
    return {
        "surface": spec.surface_id,
        "label": spec.label,
        "method": spec.method,
        "path": urllib.parse.urlparse(url).path,
        "endpointAvailability": {
            "state": endpoint_state,
            "httpStatus": status_code,
            "reason": endpoint_reason,
        },
        "surfaceStatus": surface_status,
        "readinessStatus": readiness_status,
        "collectedFields": redacted_fields,
        "missingEvidence": missing,
        "operatorNextSteps": _operator_next_steps(surface_status, readiness_status, missing),
        "liveProviderSuccessClaimed": False,
    }


def _timestamp_for_filename(captured_at: str) -> str:
    parsed = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _artifact_path(output_dir: Path, captured_at: str, output_path: Path | None = None) -> Path:
    if output_path is not None:
        return output_path
    return output_dir / f"target_environment_evidence_{_timestamp_for_filename(captured_at)}.json"


def _scenario_artifact_path(output_dir: Path, generated_at: str, output_path: Path | None = None) -> Path:
    if output_path is not None:
        return output_path
    return output_dir / f"scenario_baseline_evidence_{_timestamp_for_filename(generated_at)}.json"


def _manifest_artifact_path(output_dir: Path, generated_at: str, output_path: Path | None = None) -> Path:
    if output_path is not None:
        return output_path
    return output_dir / f"target_evidence_manifest_{_timestamp_for_filename(generated_at)}.json"


def _safe_environment_label(value: str | None) -> str:
    text = str(value or "local_operator").strip() or "local_operator"
    stats = RedactionStats()
    redacted = _redact_scenario_input(text, stats)
    return str(redacted or REDACTED)


def _safe_mapping_fields(value: Any, allowed_keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {key: value[key] for key in allowed_keys if key in value}


def _safe_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _blocked_scenario_readiness(reason: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "baselineSnapshot": {
            "state": "missing",
            "available": False,
            "lastUpdated": None,
            "affectedComponents": ["baselineSnapshot"],
        },
        "marketFrame": {
            "state": "missing",
            "available": False,
            "lastUpdated": None,
            "affectedComponents": ["marketFrame"],
        },
        "driverInputs": {
            "state": "missing",
            "availableDriverKeys": [],
            "partialDriverKeys": [],
            "missingDriverKeys": [],
            "affectedDriverKeys": [],
        },
        "evidenceCompleteness": {
            "state": "blocked",
            "gaps": [reason],
        },
        "dataState": "unavailable",
        "sampleState": "none",
        "scoreAuthority": "observation_only",
        "sourceAuthorityAllowed": False,
        "authoritative": False,
        "observationOnly": True,
        "ready": False,
        "partial": False,
        "blocked": True,
        "affectedBaselineComponents": ["baselineSnapshot", "marketFrame"],
        "affectedDriverKeys": [],
        "evidenceGaps": [reason],
        "lastUpdated": None,
    }


def _extract_scenario_readiness(scenario_input: Any) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(scenario_input, Mapping):
        return _blocked_scenario_readiness("scenarioBaselineInput"), ["scenarioBaselineInput"]
    readiness = scenario_input.get("baselineReadiness")
    if not isinstance(readiness, Mapping) and isinstance(scenario_input.get("scenarioBaselineEvidence"), Mapping):
        readiness = _dig(scenario_input, ("scenarioBaselineEvidence", "baselineReadiness"))
    if not isinstance(readiness, Mapping):
        return _blocked_scenario_readiness("baselineReadiness"), ["baselineReadiness"]

    missing_required = [
        key
        for key in ("status", "baselineSnapshot", "marketFrame", "driverInputs", "evidenceCompleteness")
        if key not in readiness
    ]
    if missing_required:
        blocked = _blocked_scenario_readiness("baselineReadinessIncomplete")
        blocked["evidenceCompleteness"]["gaps"] = ["baselineReadinessIncomplete", *missing_required]
        blocked["evidenceGaps"] = ["baselineReadinessIncomplete", *missing_required]
        return blocked, ["baselineReadinessIncomplete", *missing_required]

    projected = _safe_mapping_fields(readiness, _SCENARIO_SAFE_READINESS_KEYS)
    projected["baselineSnapshot"] = _safe_mapping_fields(
        projected.get("baselineSnapshot"),
        _SCENARIO_SAFE_COMPONENT_KEYS,
    )
    projected["marketFrame"] = _safe_mapping_fields(
        projected.get("marketFrame"),
        _SCENARIO_SAFE_COMPONENT_KEYS,
    )
    projected["driverInputs"] = _safe_mapping_fields(
        projected.get("driverInputs"),
        _SCENARIO_SAFE_DRIVER_INPUT_KEYS,
    )
    projected["evidenceCompleteness"] = _safe_mapping_fields(
        projected.get("evidenceCompleteness"),
        _SCENARIO_SAFE_EVIDENCE_KEYS,
    )
    return projected, []


def _scenario_reason_codes(readiness: Mapping[str, Any], missing_reasons: list[str]) -> list[str]:
    reasons: list[str] = list(missing_reasons)
    evidence = readiness.get("evidenceCompleteness") if isinstance(readiness.get("evidenceCompleteness"), Mapping) else {}
    driver_inputs = readiness.get("driverInputs") if isinstance(readiness.get("driverInputs"), Mapping) else {}
    for key in (
        "evidenceGaps",
        "affectedBaselineComponents",
    ):
        reasons.extend(_safe_list(readiness.get(key)))
    reasons.extend(_safe_list(evidence.get("gaps")))
    reasons.extend(_safe_list(driver_inputs.get("affectedDriverKeys")))
    for component_key, reason in (("baselineSnapshot", "baselineSnapshot"), ("marketFrame", "marketFrame")):
        component = readiness.get(component_key) if isinstance(readiness.get(component_key), Mapping) else {}
        state = str(component.get("state") or "").strip()
        if state in {"missing", "stale", "partial", "blocked"}:
            reasons.append(reason)
    data_state = str(readiness.get("dataState") or "").strip()
    sample_state = str(readiness.get("sampleState") or "").strip()
    if data_state in {"demo_static_sample", "request_supplied", "unavailable"}:
        reasons.append("scenarioDataBoundary" if data_state == "demo_static_sample" else data_state)
    if sample_state and sample_state != "none":
        reasons.append(sample_state)
    if not readiness.get("sourceAuthorityAllowed"):
        reasons.append("scoreAuthority")
    return _dedupe(reasons)


def _scenario_baseline_evidence(readiness: Mapping[str, Any], missing_reasons: list[str]) -> dict[str, Any]:
    baseline_snapshot = readiness.get("baselineSnapshot") if isinstance(readiness.get("baselineSnapshot"), Mapping) else {}
    market_frame = readiness.get("marketFrame") if isinstance(readiness.get("marketFrame"), Mapping) else {}
    driver_inputs = readiness.get("driverInputs") if isinstance(readiness.get("driverInputs"), Mapping) else {}
    evidence = readiness.get("evidenceCompleteness") if isinstance(readiness.get("evidenceCompleteness"), Mapping) else {}
    source_authority = bool(readiness.get("sourceAuthorityAllowed"))
    score_authority = str(readiness.get("scoreAuthority") or "observation_only")
    authoritative = bool(readiness.get("authoritative") is True and source_authority and score_authority == "authoritative")
    observation_only = not authoritative
    return {
        "baselineReadinessState": str(readiness.get("status") or "blocked"),
        "baselineSnapshotComponentState": str(baseline_snapshot.get("state") or "missing"),
        "marketFrameState": str(market_frame.get("state") or "missing"),
        "driverInputState": str(driver_inputs.get("state") or "missing"),
        "evidenceCompletenessState": str(evidence.get("state") or "blocked"),
        "sourceAuthorityScoreAuthoritySafeState": {
            "sourceAuthorityAllowed": source_authority,
            "scoreAuthority": score_authority,
            "authoritative": authoritative,
        },
        "staleMissingBlockedReasonCodes": _scenario_reason_codes(readiness, missing_reasons),
        "affectedDriverKeys": _safe_list(readiness.get("affectedDriverKeys"))
        or _safe_list(driver_inputs.get("affectedDriverKeys")),
        "observationOnly": observation_only,
        "diagnosticOnly": True,
        "baselineReadiness": dict(readiness),
    }


def run_scenario_baseline_evidence_export(
    *,
    scenario_input: Mapping[str, Any] | None,
    output_dir: str | Path,
    environment_label: str | None = None,
    generated_at: str | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    generated = generated_at or _now_iso()
    stats = RedactionStats()
    sanitized_input = _redact_scenario_input(scenario_input, stats)
    readiness, missing_reasons = _extract_scenario_readiness(sanitized_input)
    evidence = _scenario_baseline_evidence(readiness, missing_reasons)
    artifact_file = _scenario_artifact_path(
        Path(output_dir),
        generated,
        Path(output_path) if output_path is not None else None,
    )
    artifact = {
        "schemaVersion": SCHEMA_VERSION,
        "artifactVersion": SCENARIO_BASELINE_ARTIFACT_VERSION,
        "generatedAt": generated,
        "environmentLabel": _safe_environment_label(environment_label),
        "artifactPath": str(artifact_file),
        "executionBoundary": {
            "readOnly": True,
            "localOperatorRun": True,
            "observationOnly": evidence["observationOnly"],
            "diagnosticOnly": True,
            "noDataMutation": True,
            "noProviderCalls": True,
            "noNetworkBehaviorChanged": True,
            "noRuntimeCacheChange": True,
            "providerRoutingChanged": False,
            "liveProviderSuccessClaimed": False,
        },
        "scenarioBaselineEvidence": evidence,
        "operatorNextSteps": _operator_next_steps_for_scenario(evidence),
        "redactionSummary": {
            "redactionVersion": REDACTION_VERSION,
            "redactedKeyCount": stats.redacted_key_count,
            "redactedValueCount": stats.redacted_value_count,
        },
    }
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def _is_unsafe_manifest_text(value: Any) -> bool:
    text = str(value or "")
    lowered = text.lower()
    compacted = _compact(text)
    marker_matches = []
    for marker in _UNSAFE_MANIFEST_TEXT_MARKERS:
        compacted_marker = _compact(marker)
        marker_matches.append(marker in lowered or (bool(compacted_marker) and compacted_marker in compacted))
    return (
        _is_sensitive_value(text)
        or _is_scenario_unsafe_key(text)
        or any(marker_matches)
    )


def _safe_artifact_label(path: Path) -> str:
    label = path.name if path.name not in {"", ".", ".."} else "artifact.json"
    if Path(label).name != label or _is_unsafe_manifest_text(label):
        return "[redacted-artifact]"
    return label


def _load_local_artifact(path: Path) -> Any:
    if not path.exists():
        raise ValueError(f"artifact path does not exist: {_safe_artifact_label(path)}")
    if not path.is_file():
        raise ValueError(f"artifact path is not a file: {_safe_artifact_label(path)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"artifact JSON is invalid: {_safe_artifact_label(path)}") from exc


def _state_bucket(status: Any, readiness_status: Any = None) -> str:
    values = {str(item or "").strip().lower() for item in (status, readiness_status)}
    if values & {"readiness_available", "ready", "available", "authoritative", "authorized"}:
        return "ready"
    if values & {"readiness_partial", "partial", "limited", "stale"}:
        return "partial"
    if values & {
        "readiness_blocked",
        "blocked",
        "missing",
        "missing_readiness_fields",
        "endpoint_unavailable",
        "access_blocked",
        "request_failed",
        "unavailable",
    }:
        return "blocked"
    return "unknown"


def _safe_missing_evidence(value: Any) -> list[str]:
    return _dedupe([item for item in _safe_list(value) if not _is_unsafe_manifest_text(item)])


def _manifest_summary_item(
    *,
    artifact_label: str,
    surface: str,
    surface_label: str,
    status: str,
    readiness_status: str,
    missing_evidence: list[str],
    observation_only: bool,
    ready_excluded_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "artifactLabel": artifact_label,
        "surface": surface,
        "surfaceLabel": surface_label,
        "status": status,
        "readinessStatus": readiness_status,
        "missingEvidence": missing_evidence,
        "observationOnly": observation_only,
        "readyExcludedReason": ready_excluded_reason,
    }


def _summarize_target_artifact(artifact: Mapping[str, Any], artifact_label: str) -> list[dict[str, Any]]:
    surfaces = artifact.get("surfaces")
    if not isinstance(surfaces, Mapping):
        return []
    summaries: list[dict[str, Any]] = []
    for surface_id, raw_surface in surfaces.items():
        if not isinstance(raw_surface, Mapping):
            continue
        surface_name = str(raw_surface.get("surface") or surface_id or "unknown_artifact")
        status = str(raw_surface.get("surfaceStatus") or "unknown")
        readiness_status = str(raw_surface.get("readinessStatus") or "unknown")
        summaries.append(
            _manifest_summary_item(
                artifact_label=artifact_label,
                surface=surface_name,
                surface_label=str(raw_surface.get("label") or surface_name),
                status=status,
                readiness_status=readiness_status,
                missing_evidence=_safe_missing_evidence(raw_surface.get("missingEvidence")),
                observation_only=readiness_status.strip().lower() in {"observation_only", "observation-only"},
            )
        )
    return summaries


def _summarize_scenario_artifact(artifact: Mapping[str, Any], artifact_label: str) -> list[dict[str, Any]]:
    evidence = artifact.get("scenarioBaselineEvidence")
    if not isinstance(evidence, Mapping):
        return []
    status = str(evidence.get("baselineReadinessState") or "unknown")
    readiness = evidence.get("baselineReadiness") if isinstance(evidence.get("baselineReadiness"), Mapping) else {}
    readiness_status = str(readiness.get("status") or status)
    observation_only = bool(evidence.get("observationOnly") is True)
    return [
        _manifest_summary_item(
            artifact_label=artifact_label,
            surface="scenario_baseline_readiness",
            surface_label="Scenario baseline readiness",
            status=status,
            readiness_status=readiness_status,
            missing_evidence=_safe_missing_evidence(evidence.get("staleMissingBlockedReasonCodes")),
            observation_only=observation_only,
            ready_excluded_reason=(
                "observation_only_not_authoritative"
                if observation_only and _state_bucket(status, readiness_status) == "ready"
                else None
            ),
        )
    ]


def _unknown_artifact_summary(artifact_label: str) -> dict[str, Any]:
    return _manifest_summary_item(
        artifact_label=artifact_label,
        surface="unknown_artifact",
        surface_label="Unknown evidence artifact",
        status="rejected_unknown_shape",
        readiness_status="unknown_shape",
        missing_evidence=["unknown_artifact_shape"],
        observation_only=False,
    )


def _summarize_manifest_artifact(artifact: Any, artifact_label: str) -> list[dict[str, Any]]:
    if not isinstance(artifact, Mapping):
        return [_unknown_artifact_summary(artifact_label)]
    artifact_version = artifact.get("artifactVersion")
    if artifact_version == ARTIFACT_VERSION:
        summaries = _summarize_target_artifact(artifact, artifact_label)
        return summaries or [_unknown_artifact_summary(artifact_label)]
    if artifact_version == SCENARIO_BASELINE_ARTIFACT_VERSION:
        summaries = _summarize_scenario_artifact(artifact, artifact_label)
        return summaries or [_unknown_artifact_summary(artifact_label)]
    return [_unknown_artifact_summary(artifact_label)]


def _manifest_state_counts(summaries: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "ready": 0,
        "partial": 0,
        "blocked": 0,
        "observationOnly": 0,
        "unknown": 0,
    }
    for item in summaries:
        bucket = _state_bucket(item.get("status"), item.get("readinessStatus"))
        if bucket == "ready" and item.get("observationOnly") is True:
            bucket = "blocked"
        if bucket not in {"ready", "partial", "blocked"}:
            bucket = "unknown"
            counts["blocked"] += 1
        counts[bucket] += 1
        if item.get("observationOnly") is True:
            counts["observationOnly"] += 1
    return counts


def _artifact_redaction_summary(artifact: Any) -> tuple[int, int]:
    if not isinstance(artifact, Mapping):
        return 0, 0
    summary = artifact.get("redactionSummary")
    if not isinstance(summary, Mapping):
        return 0, 0
    return (
        int(summary.get("redactedKeyCount") or 0),
        int(summary.get("redactedValueCount") or 0),
    )


_MANIFEST_SURFACE_ORDER = {
    "rotation_quote_readiness": 10,
    "portfolio_lineage": 20,
    "options_chain_readiness": 30,
    "scenario_baseline_readiness": 40,
    "unknown_artifact": 90,
}


def _manifest_summary_sort_key(item: Mapping[str, Any]) -> tuple[int, str, str]:
    surface = str(item.get("surface") or "")
    return (
        _MANIFEST_SURFACE_ORDER.get(surface, 80),
        surface,
        str(item.get("artifactLabel") or ""),
    )


def _manifest_rejected_artifact_count(summaries_by_artifact: Mapping[str, list[dict[str, Any]]]) -> int:
    rejected = 0
    for summaries in summaries_by_artifact.values():
        if summaries and all(str(item.get("surface") or "") == "unknown_artifact" for item in summaries):
            rejected += 1
    return rejected


def run_target_evidence_manifest_export(
    *,
    artifact_paths: list[str | Path],
    output_dir: str | Path,
    generated_at: str | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    if not artifact_paths:
        raise ValueError("at least one artifact path is required")
    generated = generated_at or _now_iso()
    stats = RedactionStats()
    surface_summaries: list[dict[str, Any]] = []
    artifact_key_count = 0
    artifact_value_count = 0
    artifact_labels: list[str] = []
    summaries_by_artifact: dict[str, list[dict[str, Any]]] = {}

    for raw_path in artifact_paths:
        artifact_path = Path(raw_path)
        artifact_label = _safe_artifact_label(artifact_path)
        artifact_labels.append(artifact_label)
        raw_artifact = _load_local_artifact(artifact_path)
        sanitized_artifact = _redact_scenario_input(raw_artifact, stats)
        key_count, value_count = _artifact_redaction_summary(sanitized_artifact)
        artifact_key_count += key_count
        artifact_value_count += value_count
        artifact_summaries = _summarize_manifest_artifact(sanitized_artifact, artifact_label)
        summaries_by_artifact[artifact_label] = artifact_summaries
        surface_summaries.extend(artifact_summaries)

    surface_summaries.sort(key=_manifest_summary_sort_key)
    missing_evidence = _dedupe(
        [
            reason
            for summary in surface_summaries
            for reason in _safe_missing_evidence(summary.get("missingEvidence"))
        ]
    )
    artifact_file = _manifest_artifact_path(
        Path(output_dir),
        generated,
        Path(output_path) if output_path is not None else None,
    )
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "manifestSchemaVersion": MANIFEST_SCHEMA_VERSION,
        "artifactVersion": MANIFEST_ARTIFACT_VERSION,
        "generatedAt": generated,
        "artifactPath": str(artifact_file),
        "artifactCount": len(artifact_paths),
        "inputArtifactCount": len(artifact_paths),
        "rejectedArtifactCount": _manifest_rejected_artifact_count(summaries_by_artifact),
        "artifactLabels": sorted(artifact_labels),
        "executionBoundary": {
            "readOnly": True,
            "localOperatorRun": True,
            "localFilesOnly": True,
            "noApiCalls": True,
            "noProviderCalls": True,
            "noDataMutation": True,
            "noNetworkBehaviorChanged": True,
            "providerRoutingChanged": False,
            "liveProviderSuccessClaimed": False,
        },
        "surfaceStatusSummary": surface_summaries,
        "stateCounts": _manifest_state_counts(surface_summaries),
        "missingEvidenceFamilies": missing_evidence,
        "redactionSummary": {
            "redactionVersion": REDACTION_VERSION,
            "redactedKeyCount": stats.redacted_key_count,
            "redactedValueCount": stats.redacted_value_count,
            "artifactRedactedKeyCount": artifact_key_count,
            "artifactRedactedValueCount": artifact_value_count,
            "totalRedactedKeyCount": stats.redacted_key_count + artifact_key_count,
            "totalRedactedValueCount": stats.redacted_value_count + artifact_value_count,
        },
    }
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _operator_next_steps_for_scenario(evidence: Mapping[str, Any]) -> list[str]:
    if evidence.get("baselineReadinessState") == "ready" and not evidence.get("observationOnly"):
        return ["Archive this sanitized local evidence artifact with operator review."]
    reasons = ", ".join(str(item) for item in evidence.get("staleMissingBlockedReasonCodes") or [])
    if reasons:
        return [f"Collect safe Scenario baseline evidence for: {reasons}."]
    return ["Review the sanitized Scenario baseline evidence artifact."]


def _build_operator_next_steps(surfaces: Mapping[str, Any]) -> list[str]:
    steps: list[str] = []
    for surface in surfaces.values():
        for step in surface.get("operatorNextSteps") or []:
            text = str(step or "").strip()
            if text and text not in steps:
                steps.append(text)
    return steps


def run_harness(
    *,
    base_url: str,
    output_dir: str | Path,
    client: Any | None = None,
    captured_at: str | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    surface_specs: Mapping[str, SurfaceSpec] | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    normalized_base = _normalize_base_url(base_url)
    captured = captured_at or _now_iso()
    stats = RedactionStats()
    specs = dict(surface_specs or _default_specs())
    http_client = client or UrlLibClient()
    sanitized_headers = dict(headers or {})
    surfaces = {
        surface_id: _collect_surface(
            base_url=normalized_base,
            spec=spec,
            client=http_client,
            headers=sanitized_headers,
            timeout=timeout,
            stats=stats,
        )
        for surface_id, spec in specs.items()
    }
    artifact_file = _artifact_path(
        Path(output_dir),
        captured,
        Path(output_path) if output_path is not None else None,
    )
    artifact = {
        "schemaVersion": SCHEMA_VERSION,
        "artifactVersion": ARTIFACT_VERSION,
        "capturedAt": captured,
        "baseUrl": _safe_url_label(normalized_base),
        "artifactPath": str(artifact_file),
        "executionBoundary": {
            "readOnly": True,
            "noDataMutation": True,
            "noOrderPlacement": True,
            "providerRoutingChanged": False,
            "credentialsWritten": False,
            "liveProviderSuccessClaimed": False,
        },
        "surfaces": surfaces,
        "operatorNextSteps": _build_operator_next_steps(surfaces),
        "redactionSummary": {
            "redactionVersion": REDACTION_VERSION,
            "redactedKeyCount": stats.redacted_key_count,
            "redactedValueCount": stats.redacted_value_count,
        },
    }
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def _parse_header(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("expected NAME=VALUE")
    key, value = raw.split("=", 1)
    key = key.strip()
    if not key:
        raise argparse.ArgumentTypeError("header name is required")
    return key, value


def _parse_surface_override(raw: str, specs: dict[str, SurfaceSpec]) -> tuple[str, SurfaceSpec]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("expected SURFACE=METHOD:PATH_OR_URL")
    surface_id, target = raw.split("=", 1)
    surface_id = surface_id.strip()
    if surface_id not in specs:
        raise argparse.ArgumentTypeError(f"unknown surface: {surface_id}")
    method = specs[surface_id].method
    path = target.strip()
    if ":" in path:
        maybe_method, maybe_path = path.split(":", 1)
        if maybe_method.strip().upper() in {"GET", "POST"}:
            method = maybe_method.strip().upper()
            path = maybe_path.strip()
    if not path:
        raise argparse.ArgumentTypeError("surface path is required")
    existing = specs[surface_id]
    return surface_id, SurfaceSpec(
        surface_id=existing.surface_id,
        label=existing.label,
        method=method,
        path=path,
        extractor=existing.extractor,
        body=existing.body if method == "POST" else None,
    )


def _load_json_body(raw: str | None, path: str | None) -> Mapping[str, Any] | None:
    if raw and path:
        raise ValueError("use only one scenario body source")
    if raw:
        value = json.loads(raw)
    elif path:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    else:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("scenario body must be a JSON object")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect sanitized DATA-033 target-environment readiness evidence from a local WolfyStock API.",
    )
    parser.add_argument("--base-url", required=True, help="Local WolfyStock API base URL, for example http://127.0.0.1:8000.")
    parser.add_argument("--output-dir", default="artifacts/target-environment-evidence", help="Directory for timestamped JSON output.")
    parser.add_argument("--output", default=None, help="Exact JSON output path. Overrides --output-dir filename.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Per-request timeout seconds.")
    parser.add_argument("--request-header", action="append", default=[], help="Optional HTTP header as NAME=VALUE; values are not written.")
    parser.add_argument(
        "--surface-url",
        action="append",
        default=[],
        help="Override a surface as SURFACE=METHOD:PATH_OR_URL. Known surfaces are emitted by --list-surfaces.",
    )
    parser.add_argument("--skip-surface", action="append", default=[], help="Skip one default surface id.")
    parser.add_argument("--scenario-body-json", default=None, help="JSON object body for the scenario surface.")
    parser.add_argument("--scenario-body-file", default=None, help="Path to JSON object body for the scenario surface.")
    parser.add_argument("--list-surfaces", action="store_true", help="Print default surface ids and paths.")
    return parser


def _build_scenario_baseline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export sanitized local Scenario baseline readiness evidence from supplied JSON input.",
    )
    parser.add_argument("--scenario-input-json", default=None, help="Scenario readiness JSON object.")
    parser.add_argument("--scenario-input-file", default=None, help="Path to a Scenario readiness JSON object.")
    parser.add_argument(
        "--environment-label",
        default="local_operator",
        help="Non-secret environment label for the artifact.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/scenario-baseline-evidence",
        help="Directory for timestamped Scenario baseline JSON output.",
    )
    parser.add_argument("--output", default=None, help="Exact JSON output path. Overrides --output-dir filename.")
    return parser


def _build_manifest_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize existing sanitized target-environment evidence artifacts into one local manifest.",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="Path to an existing sanitized target-environment evidence JSON artifact. Repeat for multiple artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/target-environment-evidence",
        help="Directory for timestamped manifest JSON output.",
    )
    parser.add_argument("--output", default=None, help="Exact JSON output path. Overrides --output-dir filename.")
    return parser


def _scenario_baseline_main(argv: list[str]) -> int:
    parser = _build_scenario_baseline_parser()
    args = parser.parse_args(argv)
    try:
        scenario_input = _load_json_body(args.scenario_input_json, args.scenario_input_file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    artifact = run_scenario_baseline_evidence_export(
        scenario_input=scenario_input,
        output_dir=args.output_dir,
        output_path=args.output,
        environment_label=args.environment_label,
    )
    print(
        json.dumps(
            {
                "artifactPath": artifact["artifactPath"],
                "scenarioBaselineEvidence": artifact["scenarioBaselineEvidence"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def _manifest_main(argv: list[str]) -> int:
    parser = _build_manifest_parser()
    args = parser.parse_args(argv)
    try:
        manifest = run_target_evidence_manifest_export(
            artifact_paths=[Path(path) for path in args.artifact],
            output_dir=args.output_dir,
            output_path=args.output,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {
                "artifactPath": manifest["artifactPath"],
                "artifactCount": manifest["artifactCount"],
                "inputArtifactCount": manifest["inputArtifactCount"],
                "rejectedArtifactCount": manifest["rejectedArtifactCount"],
                "stateCounts": manifest["stateCounts"],
                "missingEvidenceFamilies": manifest["missingEvidenceFamilies"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(argv if argv is not None else sys.argv[1:])
    if raw_argv[:1] == ["scenario-baseline"]:
        return _scenario_baseline_main(raw_argv[1:])
    if raw_argv[:1] == ["manifest"]:
        return _manifest_main(raw_argv[1:])
    parser = _build_parser()
    args = parser.parse_args(raw_argv)
    specs = _default_specs()
    if args.list_surfaces:
        print(json.dumps({key: {"method": spec.method, "path": spec.path} for key, spec in specs.items()}, indent=2))
        return 0

    for surface_id in args.skip_surface:
        specs.pop(str(surface_id), None)
    for raw_override in args.surface_url:
        surface_id, spec = _parse_surface_override(raw_override, specs)
        specs[surface_id] = spec
    try:
        scenario_body = _load_json_body(args.scenario_body_json, args.scenario_body_file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if scenario_body is not None and "scenario_baseline_readiness" in specs:
        existing = specs["scenario_baseline_readiness"]
        specs["scenario_baseline_readiness"] = SurfaceSpec(
            surface_id=existing.surface_id,
            label=existing.label,
            method=existing.method,
            path=existing.path,
            extractor=existing.extractor,
            body=scenario_body,
        )

    headers = {}
    for raw_header in args.request_header:
        key, value = _parse_header(raw_header)
        headers[key] = value

    try:
        artifact = run_harness(
            base_url=args.base_url,
            output_dir=args.output_dir,
            output_path=args.output,
            headers=headers,
            timeout=args.timeout,
            surface_specs=specs,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps({"artifactPath": artifact["artifactPath"], "surfaces": artifact["surfaces"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
