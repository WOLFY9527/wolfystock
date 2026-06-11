from __future__ import annotations

from pathlib import Path

import scripts.build_ai_project_manual as manual_generator
import scripts.check_ai_assets as ai_assets


def _patch_generated_outputs(
    monkeypatch,
    tmp_path: Path,
    *,
    manual: str = "generated manual\n",
    manifest: str = '{"generated": true}\n',
) -> tuple[Path, Path]:
    manual_path = tmp_path / "AI_PROJECT_MANUAL.md"
    manifest_path = tmp_path / "AI_PROJECT_MANUAL_SOURCES.json"
    monkeypatch.setattr(manual_generator, "MANUAL_PATH", manual_path)
    monkeypatch.setattr(manual_generator, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(
        manual_generator,
        "build_generated_outputs",
        lambda: manual_generator.GeneratedOutputs(
            manual=manual,
            manifest_text=manifest,
            source_count=1,
            discovery={"markdownDiscovered": 0},
        ),
    )
    return manual_path, manifest_path


def test_check_mode_passes_when_generated_outputs_match(tmp_path, monkeypatch, capsys) -> None:
    manual_path, manifest_path = _patch_generated_outputs(monkeypatch, tmp_path)
    manual_path.write_text("generated manual\n", encoding="utf-8")
    manifest_path.write_text('{"generated": true}\n', encoding="utf-8")

    result = manual_generator.main(["--check"])

    assert result == 0
    assert "fresh" in capsys.readouterr().out


def test_check_mode_reports_stale_outputs_without_writing(tmp_path, monkeypatch, capsys) -> None:
    manual_path, manifest_path = _patch_generated_outputs(monkeypatch, tmp_path)
    manual_path.write_text("hand edited manual\n", encoding="utf-8")
    manifest_path.write_text('{"stale": true}\n', encoding="utf-8")

    result = manual_generator.main(["--check"])

    assert result == 1
    assert manual_path.read_text(encoding="utf-8") == "hand edited manual\n"
    assert manifest_path.read_text(encoding="utf-8") == '{"stale": true}\n'
    stderr = capsys.readouterr().err
    assert "generated AI project manual is stale" in stderr
    assert "AI_PROJECT_MANUAL.md" in stderr
    assert "AI_PROJECT_MANUAL_SOURCES.json" in stderr


def test_ai_assets_check_invokes_manual_freshness_guard(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(ai_assets, "ensure_symlink", lambda: calls.append("symlink"))
    monkeypatch.setattr(ai_assets, "ensure_copilot_entry", lambda: calls.append("copilot"))
    monkeypatch.setattr(ai_assets, "ensure_instruction_files", lambda: calls.append("instructions"))
    monkeypatch.setattr(ai_assets, "ensure_skill_files", lambda: calls.append("skills"))
    monkeypatch.setattr(ai_assets, "ensure_gitignore_rules", lambda: calls.append("gitignore"))
    monkeypatch.setattr(ai_assets, "ensure_no_tracked_claude_artifacts", lambda: calls.append("claude"))
    monkeypatch.setattr(ai_assets, "ensure_ai_project_manual_fresh", lambda: calls.append("manual"))

    ai_assets.main()

    assert calls == ["symlink", "copilot", "instructions", "skills", "gitignore", "claude", "manual"]
