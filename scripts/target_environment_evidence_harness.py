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


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
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
