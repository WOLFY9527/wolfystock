from __future__ import annotations

from pathlib import Path

import scripts.build_ai_project_manual as manual_generator
import scripts.check_ai_assets as ai_assets


def _patch_generated_outputs(
    monkeypatch,
    tmp_path: Path,
    *,
    docs_index: str = "generated index\n",
    manual: str = "generated manual\n",
    manifest: str = '{"generated": true}\n',
) -> tuple[Path, Path, Path]:
    docs_index_path = tmp_path / "README.md"
    manual_path = tmp_path / "AI_PROJECT_MANUAL.md"
    manifest_path = tmp_path / "AI_PROJECT_MANUAL_SOURCES.json"
    monkeypatch.setattr(manual_generator, "DOCS_INDEX_PATH", docs_index_path)
    monkeypatch.setattr(manual_generator, "MANUAL_PATH", manual_path)
    monkeypatch.setattr(manual_generator, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(
        manual_generator,
        "build_generated_outputs",
        lambda: manual_generator.GeneratedOutputs(
            docs_index=docs_index,
            manual=manual,
            manifest_text=manifest,
            source_count=1,
            discovery={"markdownDiscovered": 0},
        ),
    )
    return docs_index_path, manual_path, manifest_path


def test_check_mode_passes_when_generated_outputs_match(tmp_path, monkeypatch, capsys) -> None:
    docs_index_path, manual_path, manifest_path = _patch_generated_outputs(monkeypatch, tmp_path)
    docs_index_path.write_text("generated index\n", encoding="utf-8")
    manual_path.write_text("generated manual\n", encoding="utf-8")
    manifest_path.write_text('{"generated": true}\n', encoding="utf-8")

    result = manual_generator.main(["--check"])

    assert result == 0
    assert "fresh" in capsys.readouterr().out


def test_check_mode_reports_stale_outputs_without_writing(tmp_path, monkeypatch, capsys) -> None:
    docs_index_path, manual_path, manifest_path = _patch_generated_outputs(monkeypatch, tmp_path)
    docs_index_path.write_text("hand edited index\n", encoding="utf-8")
    manual_path.write_text("hand edited manual\n", encoding="utf-8")
    manifest_path.write_text('{"stale": true}\n', encoding="utf-8")

    result = manual_generator.main(["--check"])

    assert result == 1
    assert docs_index_path.read_text(encoding="utf-8") == "hand edited index\n"
    assert manual_path.read_text(encoding="utf-8") == "hand edited manual\n"
    assert manifest_path.read_text(encoding="utf-8") == '{"stale": true}\n'
    stderr = capsys.readouterr().err
    assert "generated documentation is stale" in stderr
    assert "README.md" in stderr
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
    monkeypatch.setattr(
        ai_assets,
        "ensure_documentation_architecture",
        lambda: calls.append("documentation"),
    )

    ai_assets.main()

    assert calls == [
        "symlink",
        "copilot",
        "instructions",
        "skills",
        "gitignore",
        "claude",
        "manual",
        "documentation",
    ]
