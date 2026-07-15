from __future__ import annotations

import json
from pathlib import Path

from scripts import web_build_artifact as artifact


def _write_fixture(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path
    web = repo / "apps" / "dsa-web"
    static = repo / "static"
    for path in (web / "src" / "i18n", static / "assets"):
        path.mkdir(parents=True, exist_ok=True)
    for name in ("package.json", "vite.config.ts", "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json", "package-lock.json"):
        (web / name).write_text("{}\n", encoding="utf-8")
    (web / "src" / "i18n" / "catalog.ts").write_text("export {}\n", encoding="utf-8")
    (static / "index.html").write_text('<script type="module" src="/assets/index.js"></script>', encoding="utf-8")
    (static / "assets" / "index.js").write_text("console.log('ok')\n", encoding="utf-8")
    return repo, static / artifact.ARTIFACT_FILENAME


def _manifest(repo: Path, artifact_path: Path) -> dict[str, object]:
    web = repo / "apps" / "dsa-web"
    candidate = {"commit": "candidate", "tree": "tree", "dirty": False}
    integrity = {"command": "npm --prefix apps/dsa-web ls --all --json", "sha256": "deps", "valid": True}
    manifest: dict[str, object] = {
        "contract": artifact.ARTIFACT_CONTRACT,
        "candidate": candidate,
        "packageLock": {"path": "apps/dsa-web/package-lock.json", "sha256": artifact._sha256_file(web / "package-lock.json")},
        "dependencyIntegrity": integrity,
        "toolchain": {"node": "v1", "npm": "1"},
        "configuration": {"sha256": artifact._config_hashes(web)[0]},
        "environment": {"NODE_ENV": "env"},
        "commands": [],
        "index": artifact._index_inventory(repo / "static" / "index.html", web),
        "assets": artifact._assets(repo / "static"),
    }
    manifest["fingerprint"] = artifact._sha256_json(manifest)
    artifact_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def _patch_current(monkeypatch) -> None:
    monkeypatch.setattr(artifact, "_candidate", lambda _repo, expected_sha=None: ({"commit": "candidate", "tree": "tree", "dirty": False}, [] if expected_sha in (None, "candidate") else ["candidate_sha_mismatch"]))
    monkeypatch.setattr(artifact, "_npm_integrity", lambda _repo: ({"command": "npm --prefix apps/dsa-web ls --all --json", "sha256": "deps", "valid": True}, []))
    monkeypatch.setattr(artifact, "_version", lambda _repo, *command: "v1" if command[0] == "node" else "1")
    monkeypatch.setattr(artifact, "_environment_contract", lambda: {"NODE_ENV": "env"})


def test_verify_artifact_accepts_matching_candidate(monkeypatch, tmp_path: Path) -> None:
    repo, artifact_path = _write_fixture(tmp_path)
    _patch_current(monkeypatch)
    _manifest(repo, artifact_path)

    result = artifact.verify_artifact(repo, artifact_path, expected_sha="candidate")

    assert result.ok is True


def test_manifest_regeneration_is_deterministic(monkeypatch, tmp_path: Path) -> None:
    repo, _artifact_path = _write_fixture(tmp_path)
    _patch_current(monkeypatch)

    first = artifact.generate_manifest(repo)
    second = artifact.generate_manifest(repo)

    assert first.ok is True
    assert second.ok is True
    assert first.payload == second.payload


def test_verify_artifact_rejects_dirty_tree_and_wrong_sha(monkeypatch, tmp_path: Path) -> None:
    repo, artifact_path = _write_fixture(tmp_path)
    _patch_current(monkeypatch)
    _manifest(repo, artifact_path)
    monkeypatch.setattr(artifact, "_candidate", lambda _repo, expected_sha=None: ({"commit": "other", "tree": "other-tree", "dirty": True}, ["worktree_dirty", "candidate_sha_mismatch"]))

    result = artifact.verify_artifact(repo, artifact_path, expected_sha="candidate")

    assert result.ok is False
    assert {"worktree_dirty", "candidate_sha_mismatch", "artifact_candidate_mismatch"} <= set(result.error_codes)


def test_verify_artifact_rejects_lock_config_missing_and_tampered_assets(monkeypatch, tmp_path: Path) -> None:
    repo, artifact_path = _write_fixture(tmp_path)
    _patch_current(monkeypatch)
    _manifest(repo, artifact_path)
    web = repo / "apps" / "dsa-web"
    (web / "package-lock.json").write_text("changed\n", encoding="utf-8")
    (web / "vite.config.ts").write_text("changed\n", encoding="utf-8")
    (repo / "static" / "assets" / "index.js").unlink()

    result = artifact.verify_artifact(repo, artifact_path)

    assert result.ok is False
    assert {"artifact_lockfile_mismatch", "artifact_config_mismatch", "artifact_asset_mismatch"} <= set(result.error_codes)


def test_verify_artifact_rejects_changed_asset_content(monkeypatch, tmp_path: Path) -> None:
    repo, artifact_path = _write_fixture(tmp_path)
    _patch_current(monkeypatch)
    _manifest(repo, artifact_path)
    (repo / "static" / "assets" / "index.js").write_text("console.log('tampered')\n", encoding="utf-8")

    result = artifact.verify_artifact(repo, artifact_path)

    assert result.ok is False
    assert "artifact_asset_mismatch" in result.error_codes


def test_verify_artifact_rejects_manifest_tampering(monkeypatch, tmp_path: Path) -> None:
    repo, artifact_path = _write_fixture(tmp_path)
    _patch_current(monkeypatch)
    manifest = _manifest(repo, artifact_path)
    manifest["toolchain"] = {"node": "v2", "npm": "2"}
    artifact_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = artifact.verify_artifact(repo, artifact_path)

    assert result.ok is False
    assert "artifact_manifest_tampered" in result.error_codes
