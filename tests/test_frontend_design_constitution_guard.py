import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_frontend_design_constitution.py"


def load_guard_module():
    spec = importlib.util.spec_from_file_location("check_frontend_design_constitution", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_flags_migrated_page_handrolled_materials():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/PortfolioPage.tsx",
        '<section className="rounded-2xl border border-white/5 bg-white/[0.02] p-5">bad</section>',
    )

    assert any(item.rule == "migrated-page-terminal-primitives" for item in result.findings)


def test_allows_terminal_nested_black_material():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/PortfolioPage.tsx",
        '<TerminalNestedBlock className="bg-black/20">ok</TerminalNestedBlock>',
    )

    assert not result.findings


def test_flags_user_page_internal_terms():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/UserScannerPage.tsx",
        '<p>provider_timeout raw schema trace</p>',
    )

    rules = {item.rule for item in result.findings}
    assert "user-facing-internal-term" in rules
