from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from scripts import web_build_artifact as artifact
from scripts.uat_fresh_build_verifier import VerificationResult


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
        "environment": artifact._environment_contract(repo)[0],
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
    monkeypatch.setattr(
        artifact,
        "_environment_contract",
        lambda _repo: (
            {
                "managed": {
                    "schemaVersion": "wolfystock_environment_evidence_v1",
                    "environmentPolicyVersion": "wolfystock_test_environment_policy_v1",
                    "environmentFingerprint": "e" * 64,
                    "componentFingerprints": {
                        "python": {"input": "p" * 64, "installed": "q" * 64},
                        "web": {"input": "w" * 64, "installed": "x" * 64},
                        "browser": {"input": "b" * 64, "installed": "c" * 64},
                        "rg": {"input": "r" * 64, "installed": "s" * 64},
                    },
                },
                "buildVariables": {"NODE_ENV": "env"},
            },
            [],
        ),
    )


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


def test_release_typecheck_uses_non_incremental_configs_without_snapshot_writes(monkeypatch, tmp_path: Path) -> None:
    repo, _artifact_path = _write_fixture(tmp_path)
    commands: list[list[str]] = []

    def run(_repo: Path, *args: str, capture: bool = True) -> subprocess.CompletedProcess[str]:
        commands.append(list(args))
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(artifact, "_run", run)

    result = artifact.run_typecheck(repo)

    assert result.ok is True
    assert commands == [
        [
            "npm",
            "--prefix",
            "apps/dsa-web",
            "exec",
            "--",
            "tsc",
            "--noEmit",
            "--incremental",
            "false",
            "-p",
            "apps/dsa-web/tsconfig.app.json",
        ],
        [
            "npm",
            "--prefix",
            "apps/dsa-web",
            "exec",
            "--",
            "tsc",
            "--noEmit",
            "--incremental",
            "false",
            "-p",
            "apps/dsa-web/tsconfig.node.json",
        ],
    ]
    assert all("node_modules/.tmp" not in " ".join(command) for command in commands)
    assert str(repo) not in json.dumps(result.payload)


def test_build_artifact_uses_temporary_output_and_binds_managed_environment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo, artifact_path = _write_fixture(tmp_path)
    shutil.rmtree(repo / "static")
    playwright_output = repo / "playwright-output"
    monkeypatch.setenv("WOLFYSTOCK_FRONTEND_OUTPUT_DIR", str(playwright_output))
    _patch_current(monkeypatch)
    commands: list[list[str]] = []

    def run(_repo: Path, *args: str, capture: bool = True) -> subprocess.CompletedProcess[str]:
        command = list(args)
        commands.append(command)
        if "build:bundle" in command:
            output_dir = Path(command[command.index("--outDir") + 1])
            (output_dir / "assets").mkdir(parents=True)
            (output_dir / "index.html").write_text(
                '<script type="module" src="/assets/index.js"></script>',
                encoding="utf-8",
            )
            (output_dir / "assets" / "index.js").write_text("console.log('ok')\n", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(artifact, "_run", run)
    monkeypatch.setattr(
        "scripts.uat_fresh_build_verifier.write_frontend_build_identity",
        lambda **_kwargs: VerificationResult(ok=True, payload={}),
    )
    monkeypatch.setattr("scripts.uat_fresh_build_verifier.read_backend_info", lambda _repo: object())

    result = artifact.prepare_playwright_artifact(repo, expected_sha="candidate")

    assert result.ok is True
    prepared_artifact = playwright_output / artifact.PLAYWRIGHT_ARTIFACT_DIRECTORY / artifact.ARTIFACT_FILENAME
    assert prepared_artifact.is_file()
    assert not artifact_path.exists()
    assert result.payload["candidate"] == {"commit": "candidate", "tree": "tree", "dirty": False}
    assert result.payload["environment"]["managed"]["environmentFingerprint"] == "e" * 64
    assert set(result.payload["environment"]["managed"]["componentFingerprints"]) == {
        "python",
        "web",
        "browser",
        "rg",
    }
    assert [item["command"] for item in result.payload["typecheck"]["commands"]] == [
        "npm --prefix apps/dsa-web exec -- tsc --noEmit --incremental false -p apps/dsa-web/tsconfig.app.json",
        "npm --prefix apps/dsa-web exec -- tsc --noEmit --incremental false -p apps/dsa-web/tsconfig.node.json",
    ]
    assert result.payload["artifact"]["candidate"]["tree"] == "tree"
    bundle = next(command for command in commands if "build:bundle" in command)
    output_dir = Path(bundle[bundle.index("--outDir") + 1])
    assert output_dir != repo / "static"
    assert repo / "apps" / "dsa-web" / "node_modules" not in output_dir.parents
    assert all(command[-1] != "build" for command in commands)


def test_build_artifact_reuses_existing_verified_identity_without_rebuild(monkeypatch, tmp_path: Path) -> None:
    repo, artifact_path = _write_fixture(tmp_path)
    _patch_current(monkeypatch)
    expected = _manifest(repo, artifact_path)
    before = artifact_path.read_bytes()
    monkeypatch.setattr(artifact, "run_typecheck", lambda *_args: (_ for _ in ()).throw(AssertionError("must not rebuild")))

    result = artifact.build_artifact(repo, artifact_path, expected_sha="candidate")

    assert result.ok is True
    assert result.payload == expected
    assert artifact_path.read_bytes() == before


def test_build_artifact_rejects_existing_mismatch_without_replacing_identity(monkeypatch, tmp_path: Path) -> None:
    repo, artifact_path = _write_fixture(tmp_path)
    _patch_current(monkeypatch)
    _manifest(repo, artifact_path)
    (repo / "static" / "assets" / "index.js").write_text("tampered\n", encoding="utf-8")
    before = artifact_path.read_bytes()
    monkeypatch.setattr(artifact, "run_typecheck", lambda *_args: artifact.ArtifactResult(True, {"commands": []}))

    result = artifact.prepare_playwright_artifact(repo, artifact_path, expected_sha="candidate")

    assert result.ok is False
    assert {"existing_artifact_verification_failed", "artifact_asset_mismatch"} <= set(result.error_codes)
    assert artifact_path.read_bytes() == before


def test_verify_artifact_rejects_dirty_tree_and_wrong_sha(monkeypatch, tmp_path: Path) -> None:
    repo, artifact_path = _write_fixture(tmp_path)
    _patch_current(monkeypatch)
    _manifest(repo, artifact_path)
    monkeypatch.setattr(artifact, "_candidate", lambda _repo, expected_sha=None: ({"commit": "other", "tree": "other-tree", "dirty": True}, ["worktree_dirty", "candidate_sha_mismatch"]))

    monkeypatch.setattr(artifact, "run_typecheck", lambda *_args: (_ for _ in ()).throw(AssertionError("must not typecheck")))

    result = artifact.prepare_playwright_artifact(repo, artifact_path, expected_sha="candidate")

    assert result.ok is False
    assert {"worktree_dirty", "candidate_sha_mismatch"} <= set(result.error_codes)


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

    source_repo = Path(__file__).resolve().parents[2]
    config = (source_repo / "apps" / "dsa-web" / "playwright.config.ts").read_text(encoding="utf-8")
    package = json.loads((source_repo / "apps" / "dsa-web" / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["build:playwright-artifact"] == "python ../../scripts/web_build_artifact.py playwright"
    assert "WOLFYSTOCK_FRONTEND_OUTPUT_DIR" in config
    assert "WOLFYSTOCK_RELEASE_CANDIDATE_SHA" in config
    assert "fileURLToPath(import.meta.url)" in config
    assert "cwd: configRoot" in config
    assert "playwright-web-artifact" in config
    assert "npm run build:playwright-artifact -- --expected-sha ${candidateSha}" in config
    assert "&& ${preview}" in config
    assert "npm run build &&" not in config
    assert "usesExternalServer ? {}" in config
    assert "prebuiltArtifact" in config
    assert "--expected-sha" in config
    assert "executablePath: managedChromiumExecutable" in config
    assert "channel:" not in config
    assert "node_modules/.tmp" not in config
    assert "node_modules/.vite" not in config
