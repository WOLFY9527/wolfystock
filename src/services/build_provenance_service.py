# -*- coding: utf-8 -*-
"""Read-only backend/frontend build provenance helpers."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


_MAIN_JS_RE = re.compile(r"""<script\b[^>]*\bsrc=["'](?P<src>[^"']+\.js)["']""", re.IGNORECASE)
_INDEX_HASH_RE = re.compile(r"^index-(?P<hash>[A-Za-z0-9_-]+)\.js$")
_SAFE_SHA_RE = re.compile(r"^[a-fA-F0-9]{7,64}$")
_SAFE_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/\-]{1,120}$")
_SENSITIVE_TEXT_MARKERS = (
    "authorization",
    "bearer",
    "cookie",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
    "postgres://",
    "sqlite://",
    "://",
)


@dataclass(frozen=True)
class BackendBuildInfo:
    git_sha: str | None = None
    branch: str | None = None
    commit_timestamp: datetime | str | None = None


class BuildProvenanceService:
    """Build a bounded provenance snapshot without changing runtime behavior."""

    def __init__(self, *, repo_root: Path | None = None) -> None:
        self.repo_root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]

    def build(self, *, app_state: object | None = None) -> dict[str, Any]:
        static_root = getattr(app_state, "frontend_static_dir", None) if app_state is not None else None
        if static_root is None:
            static_root = self.repo_root / "static"
        runtime_started_at = getattr(app_state, "backend_runtime_started_at", None) if app_state is not None else None
        dev_proxy_url = getattr(app_state, "frontend_dev_proxy_url", None) if app_state is not None else None
        return build_build_provenance(
            static_root=Path(static_root) if static_root is not None else None,
            backend_info=self._read_backend_info(),
            runtime_started_at=runtime_started_at,
            dev_proxy_url=str(dev_proxy_url or "") or None,
            repo_root=self.repo_root,
        )

    def _read_backend_info(self) -> BackendBuildInfo:
        return BackendBuildInfo(
            git_sha=_first_safe_sha(
                os.environ.get("GIT_COMMIT"),
                os.environ.get("GITHUB_SHA"),
                os.environ.get("COMMIT_SHA"),
                os.environ.get("SOURCE_VERSION"),
                self._git_output("rev-parse", "HEAD"),
            ),
            branch=_first_safe_branch(
                os.environ.get("GIT_BRANCH"),
                os.environ.get("GITHUB_REF_NAME"),
                os.environ.get("BRANCH_NAME"),
                self._git_output("branch", "--show-current"),
            ),
            commit_timestamp=_parse_datetime(
                os.environ.get("SOURCE_COMMIT_TIMESTAMP")
                or os.environ.get("GIT_COMMIT_TIMESTAMP")
                or self._git_output("show", "-s", "--format=%cI", "HEAD")
            ),
        )

    def _git_output(self, *args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repo_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
        except Exception:
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None


def build_unknown_provenance(*, reason_code: str = "provenance_unavailable") -> dict[str, Any]:
    return _base_payload(
        backend_info=BackendBuildInfo(),
        runtime_started_at=None,
        static_asset_mode="unknown",
        static_asset_root_provenance="unknown",
        static_asset_root_label=None,
        static_asset_root_exists=False,
        static_index_present=False,
        freshness_status="unknown",
        stale=None,
        reason_codes=[reason_code],
    )


def build_build_provenance(
    *,
    static_root: Path | str | None,
    backend_info: BackendBuildInfo | None = None,
    runtime_started_at: datetime | str | None = None,
    dev_proxy_url: str | None = None,
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    backend = backend_info or BackendBuildInfo()
    root = Path(static_root) if static_root is not None else None
    repo = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    root_exists = bool(root and root.exists())
    index_path = root / "index.html" if root is not None else None
    index_present = bool(index_path and index_path.is_file())
    root_provenance, root_label = _safe_root_provenance(root, repo_root=repo)
    reason_codes: list[str] = []

    if root is None:
        static_asset_mode = "unknown"
        reason_codes.append("static_root_unknown")
    elif index_present:
        static_asset_mode = "static_dist"
    elif dev_proxy_url:
        static_asset_mode = "dev_proxy"
        reason_codes.append("frontend_dev_proxy_configured")
    elif not root_exists:
        static_asset_mode = "unavailable"
        reason_codes.append("static_root_missing")
    else:
        static_asset_mode = "unavailable"
        reason_codes.append("index_html_missing")

    main_asset_filename = None
    main_asset_hash = None
    static_build_at: datetime | None = None
    manifest_hash = None
    manifest_source = None

    if index_present and index_path is not None and root is not None:
        main_asset_ref = _find_main_asset_ref(index_path)
        if main_asset_ref is None:
            reason_codes.append("frontend_main_asset_unknown")
        else:
            main_asset_path = _resolve_static_ref(root, main_asset_ref)
            main_asset_filename = main_asset_path.name
            main_asset_hash = _extract_main_asset_hash(main_asset_filename)
            if main_asset_path.is_file():
                static_build_at = _mtime_datetime(main_asset_path)
            else:
                reason_codes.append("main_asset_missing")

        manifest_hash, manifest_source = _frontend_manifest_hash(root)
        if manifest_hash is None:
            reason_codes.append("frontend_asset_manifest_unavailable")

    freshness_status, stale, comparison_basis, freshness_reasons = _classify_freshness(
        static_asset_mode=static_asset_mode,
        static_build_at=static_build_at,
        backend_commit_at=_parse_datetime(backend.commit_timestamp),
        main_asset_missing="main_asset_missing" in reason_codes,
    )
    reason_codes.extend(freshness_reasons)

    if not backend.git_sha:
        reason_codes.append("backend_git_sha_unavailable")
    if not backend.branch:
        reason_codes.append("backend_branch_unavailable")

    return _base_payload(
        backend_info=backend,
        runtime_started_at=runtime_started_at,
        static_asset_mode=static_asset_mode,
        static_asset_root_provenance=root_provenance,
        static_asset_root_label=root_label,
        static_asset_root_exists=root_exists,
        static_index_present=index_present,
        freshness_status=freshness_status,
        stale=stale,
        reason_codes=_dedupe(reason_codes) or ["provenance_observed"],
        frontend_main_asset_filename=main_asset_filename,
        frontend_main_asset_hash=main_asset_hash,
        frontend_asset_manifest_hash=manifest_hash,
        frontend_asset_manifest_source=manifest_source,
        frontend_static_build_timestamp=_iso_datetime(static_build_at),
        comparison_basis=comparison_basis,
    )


def _base_payload(
    *,
    backend_info: BackendBuildInfo,
    runtime_started_at: datetime | str | None,
    static_asset_mode: str,
    static_asset_root_provenance: str,
    static_asset_root_label: str | None,
    static_asset_root_exists: bool,
    static_index_present: bool,
    freshness_status: str,
    stale: bool | None,
    reason_codes: list[str],
    frontend_main_asset_filename: str | None = None,
    frontend_main_asset_hash: str | None = None,
    frontend_asset_manifest_hash: str | None = None,
    frontend_asset_manifest_source: str | None = None,
    frontend_static_build_timestamp: str | None = None,
    comparison_basis: str | None = None,
) -> dict[str, Any]:
    backend_commit_at = _parse_datetime(backend_info.commit_timestamp)
    return {
        "contract": "admin_build_provenance_v1",
        "readOnly": True,
        "noExternalCalls": True,
        "runtimeBehaviorChanged": False,
        "consumerVisible": False,
        "backendGitSha": _safe_sha(backend_info.git_sha),
        "backendBranch": _safe_branch(backend_info.branch),
        "backendCommitTimestamp": _iso_datetime(backend_commit_at),
        "backendRuntimeStartedAt": _iso_datetime(_parse_datetime(runtime_started_at)),
        "frontendMainAssetFilename": _safe_asset_filename(frontend_main_asset_filename),
        "frontendMainAssetHash": _safe_asset_hash(frontend_main_asset_hash),
        "frontendAssetManifestHash": _safe_sha(frontend_asset_manifest_hash),
        "frontendAssetManifestSource": frontend_asset_manifest_source,
        "frontendStaticBuildTimestamp": frontend_static_build_timestamp,
        "staticAssetMode": static_asset_mode,
        "staticAssetRootProvenance": static_asset_root_provenance,
        "staticAssetRootLabel": static_asset_root_label,
        "staticAssetRootExists": bool(static_asset_root_exists),
        "staticIndexPresent": bool(static_index_present),
        "freshnessStatus": freshness_status,
        "comparisonBasis": comparison_basis,
        "stale": stale,
        "reasonCodes": reason_codes,
    }


def _find_main_asset_ref(index_path: Path) -> str | None:
    try:
        html = index_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    refs = [match.group("src").strip() for match in _MAIN_JS_RE.finditer(html)]
    if not refs:
        return None
    for ref in refs:
        if Path(ref.split("?", 1)[0]).name.startswith("index-"):
            return ref
    return refs[0]


def _resolve_static_ref(static_root: Path, ref: str) -> Path:
    ref_path = ref.split("?", 1)[0].split("#", 1)[0].lstrip("/")
    return static_root / ref_path


def _extract_main_asset_hash(filename: str | None) -> str | None:
    if not filename:
        return None
    match = _INDEX_HASH_RE.match(filename)
    if match:
        return match.group("hash")
    return None


def _frontend_manifest_hash(static_root: Path) -> tuple[str | None, str | None]:
    for manifest_path in (static_root / ".vite" / "manifest.json", static_root / "manifest.json"):
        if manifest_path.is_file():
            digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            return digest, "vite_manifest"

    assets_dir = static_root / "assets"
    if not assets_dir.is_dir():
        return None, None
    records: list[str] = []
    for path in sorted(item for item in assets_dir.rglob("*") if item.is_file()):
        try:
            stat = path.stat()
        except OSError:
            continue
        relative = path.relative_to(static_root).as_posix()
        records.append(f"{relative}\0{stat.st_size}\0{stat.st_mtime_ns}")
    if not records:
        return None, None
    digest = hashlib.sha256("\n".join(records).encode("utf-8")).hexdigest()
    return digest, "static_asset_inventory"


def _classify_freshness(
    *,
    static_asset_mode: str,
    static_build_at: datetime | None,
    backend_commit_at: datetime | None,
    main_asset_missing: bool,
) -> tuple[str, bool | None, str | None, list[str]]:
    if static_asset_mode == "dev_proxy":
        return "unknown", None, None, ["frontend_dev_proxy_runtime_not_inspected"]
    if static_asset_mode == "unavailable":
        return "unavailable", None, None, ["frontend_static_dist_unavailable"]
    if static_asset_mode != "static_dist":
        return "unknown", None, None, ["static_asset_mode_unknown"]
    if main_asset_missing:
        return "unknown", None, None, ["frontend_main_asset_missing"]
    if static_build_at is None:
        return "unknown", None, None, ["frontend_build_time_unavailable"]
    if backend_commit_at is None:
        return "unknown", None, None, ["backend_commit_timestamp_unavailable"]
    if static_build_at < backend_commit_at:
        return "stale", True, "backend_commit_timestamp", ["frontend_build_older_than_backend_commit"]
    return "fresh", False, "backend_commit_timestamp", ["frontend_build_not_older_than_backend_commit"]


def _safe_root_provenance(root: Path | None, *, repo_root: Path) -> tuple[str, str | None]:
    if root is None:
        return "unknown", None
    try:
        relative = root.resolve().relative_to(repo_root.resolve())
    except Exception:
        return "configured_static_dir", "configured_static_dir"
    label = relative.as_posix() or "."
    if label == "static":
        return "repo_static_dir", "static"
    if _looks_sensitive_text(label):
        return "repo_relative_static_dir", "repo_relative_static_dir"
    return "repo_relative_static_dir", label


def _mtime_datetime(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text or _looks_sensitive_text(text):
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _first_safe_sha(*values: str | None) -> str | None:
    for value in values:
        safe = _safe_sha(value)
        if safe:
            return safe
    return None


def _first_safe_branch(*values: str | None) -> str | None:
    for value in values:
        safe = _safe_branch(value)
        if safe:
            return safe
    return None


def _safe_sha(value: str | None) -> str | None:
    text = str(value or "").strip()
    if _SAFE_SHA_RE.match(text) and not _looks_sensitive_text(text):
        return text
    return None


def _safe_branch(value: str | None) -> str | None:
    text = str(value or "").strip()
    if _SAFE_BRANCH_RE.match(text) and not _looks_sensitive_text(text):
        return text
    return None


def _safe_asset_filename(value: str | None) -> str | None:
    text = Path(str(value or "").strip()).name
    if not text or _looks_sensitive_text(text) or "/" in text:
        return None
    return text[:160]


def _safe_asset_hash(value: str | None) -> str | None:
    text = str(value or "").strip()
    if re.match(r"^[A-Za-z0-9_-]{4,80}$", text) and not _looks_sensitive_text(text):
        return text
    return None


def _looks_sensitive_text(value: str) -> bool:
    text = str(value or "").strip().lower()
    return any(marker in text for marker in _SENSITIVE_TEXT_MARKERS)


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result
