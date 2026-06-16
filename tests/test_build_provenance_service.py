# -*- coding: utf-8 -*-
"""Tests for read-only backend/frontend build provenance helpers."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.services.build_provenance_service import BackendBuildInfo, build_build_provenance


def _write_vite_static_dist(static_root: Path, *, asset_name: str = "index-CKPdXr8Q.js") -> Path:
    assets_dir = static_root / "assets"
    assets_dir.mkdir(parents=True)
    (static_root / "index.html").write_text(
        f'<html><head><script type="module" crossorigin src="/assets/{asset_name}"></script></head></html>',
        encoding="utf-8",
    )
    asset_path = assets_dir / asset_name
    asset_path.write_text("console.log('wolfystock build');\n", encoding="utf-8")
    return asset_path


def _set_mtime(path: Path, value: datetime) -> None:
    timestamp = value.timestamp()
    os.utime(path, (timestamp, timestamp))


def _backend_info(commit_timestamp: datetime) -> BackendBuildInfo:
    return BackendBuildInfo(
        git_sha="e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590",
        branch="main",
        commit_timestamp=commit_timestamp,
    )


def test_build_provenance_marks_static_bundle_stale_when_asset_older_than_backend_commit(tmp_path: Path) -> None:
    static_root = tmp_path / "static"
    asset_path = _write_vite_static_dist(static_root)
    frontend_built_at = datetime(2026, 6, 16, 3, 35, tzinfo=timezone.utc)
    backend_commit_at = datetime(2026, 6, 16, 11, 47, tzinfo=timezone.utc)
    _set_mtime(static_root / "index.html", frontend_built_at)
    _set_mtime(asset_path, frontend_built_at)

    payload = build_build_provenance(
        static_root=static_root,
        backend_info=_backend_info(backend_commit_at),
        runtime_started_at=datetime(2026, 6, 16, 12, 1, tzinfo=timezone.utc),
    )

    assert payload["staticAssetMode"] == "static_dist"
    assert payload["frontendMainAssetFilename"] == "index-CKPdXr8Q.js"
    assert payload["frontendMainAssetHash"] == "CKPdXr8Q"
    assert payload["frontendStaticBuildTimestamp"] == "2026-06-16T03:35:00+00:00"
    assert payload["backendGitSha"] == "e2a90b4bd5fd1f84a1e44abde7f2b23da6a16590"
    assert payload["backendBranch"] == "main"
    assert payload["backendCommitTimestamp"] == "2026-06-16T11:47:00+00:00"
    assert payload["backendRuntimeStartedAt"] == "2026-06-16T12:01:00+00:00"
    assert payload["freshnessStatus"] == "stale"
    assert payload["stale"] is True
    assert payload["comparisonBasis"] == "backend_commit_timestamp"
    assert "frontend_build_older_than_backend_commit" in payload["reasonCodes"]
    assert payload["frontendAssetManifestSource"] == "static_asset_inventory"
    assert len(payload["frontendAssetManifestHash"]) == 64
    assert str(tmp_path) not in json.dumps(payload, sort_keys=True)


def test_build_provenance_reports_missing_main_asset_as_unknown_without_absolute_path(tmp_path: Path) -> None:
    static_root = tmp_path / "static"
    assets_dir = static_root / "assets"
    assets_dir.mkdir(parents=True)
    (static_root / "index.html").write_text(
        '<html><head><script type="module" src="/assets/index-Missing123.js"></script></head></html>',
        encoding="utf-8",
    )

    payload = build_build_provenance(
        static_root=static_root,
        backend_info=_backend_info(datetime(2026, 6, 16, 11, 47, tzinfo=timezone.utc)),
    )

    assert payload["staticAssetMode"] == "static_dist"
    assert payload["frontendMainAssetFilename"] == "index-Missing123.js"
    assert payload["frontendMainAssetHash"] == "Missing123"
    assert payload["frontendStaticBuildTimestamp"] is None
    assert payload["freshnessStatus"] == "unknown"
    assert payload["stale"] is None
    assert "main_asset_missing" in payload["reasonCodes"]
    assert str(tmp_path) not in json.dumps(payload, sort_keys=True)


def test_build_provenance_reports_unavailable_or_dev_proxy_without_blocking_dev_usage(tmp_path: Path) -> None:
    missing_static = tmp_path / "missing-static"

    unavailable = build_build_provenance(
        static_root=missing_static,
        backend_info=BackendBuildInfo(),
    )
    assert unavailable["staticAssetMode"] == "unavailable"
    assert unavailable["freshnessStatus"] == "unavailable"
    assert unavailable["stale"] is None
    assert "static_root_missing" in unavailable["reasonCodes"]
    assert str(tmp_path) not in json.dumps(unavailable, sort_keys=True)

    dev_proxy = build_build_provenance(
        static_root=missing_static,
        backend_info=BackendBuildInfo(),
        dev_proxy_url="http://127.0.0.1:5173",
    )
    assert dev_proxy["staticAssetMode"] == "dev_proxy"
    assert dev_proxy["freshnessStatus"] == "unknown"
    assert dev_proxy["stale"] is None
    assert "frontend_dev_proxy_configured" in dev_proxy["reasonCodes"]
    assert "127.0.0.1" not in json.dumps(dev_proxy, sort_keys=True)
