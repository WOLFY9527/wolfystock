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


def test_flags_key_route_page_missing_semantic_heading():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/BacktestPage.tsx",
        '<main data-testid="backtest-v1-page">missing heading</main>',
    )

    assert any(item.rule == "route-semantic-page-heading" for item in result.findings)


def test_allows_single_terminal_page_heading_on_key_route_page():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/OptionsLabPage.tsx",
        '<TerminalPageHeading title="期权实验室" />\n<main data-testid="options-lab-page-root">ok</main>',
    )

    assert not any(item.rule == "route-semantic-page-heading" for item in result.findings)


def test_flags_market_overview_retired_local_chip_and_panel_symbols():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/MarketOverviewPage.tsx",
        "\n".join([
            "const tone = buildDecisionChipTone('risk')",
            "const panelClass = MARKET_OVERVIEW_GHOST_CARD_CLASS",
            "const titleClass = MARKET_OVERVIEW_CARD_TITLE_CLASS",
        ]),
    )

    assert any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_flags_rotation_radar_evidence_badge_regression():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/MarketRotationRadarPage.tsx",
        "<EvidenceBadge tone='warn'>观察证据</EvidenceBadge>",
    )

    assert any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_flags_admin_provider_local_badge_regression():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx",
        "\n".join([
            "import { Badge } from '../components/common';",
            "export default function Page() {",
            "  return <Badge tone='danger'>打开</Badge>;",
            "}",
        ]),
    )

    assert any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_flags_watchlist_retired_local_material_regression():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/WatchlistPage.tsx",
        "\n".join([
            "import { Badge, SectionShell } from '../components/common';",
            "import { StatusBadge } from '../components/ui/StatusBadge';",
            "const buttonClass = WATCHLIST_BUTTON_CLASS;",
            "const linkClass = WATCHLIST_LINK_BUTTON_CLASS;",
            "const badgeClass = WATCHLIST_BADGE_CLASS;",
            "const variant = displayBadgeVariant('info');",
            "export default function Page() {",
            "  return <SectionShell><Badge variant='info' /><StatusBadge status='ready' label='ok' /></SectionShell>;",
            "}",
        ]),
    )

    assert any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_allows_watchlist_terminal_primitives_after_migration():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/WatchlistPage.tsx",
        "\n".join([
            "import { TerminalButton, TerminalChip, TerminalPageShell, TerminalPanel } from '../components/terminal';",
            "export default function Page() {",
            "  return <TerminalPageShell><TerminalPanel><TerminalChip variant='info'>观察</TerminalChip><TerminalButton variant='secondary'>刷新</TerminalButton></TerminalPanel></TerminalPageShell>;",
            "}",
        ]),
    )

    assert not any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_flags_admin_cost_retired_terminal_surface_regression():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminCostObservabilityPage.tsx",
        "\n".join([
            "import { Badge, GlassCard } from '../components/common';",
            "const tone = toneClass('warn');",
            "const Tile = SummaryTile;",
            "const Card = SectionCard;",
            "export default function Page() {",
            "  return <GlassCard><Badge variant='warning'>告警</Badge><details><summary>更多</summary></details></GlassCard>;",
            "}",
        ]),
    )

    assert any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_flags_admin_evidence_retired_terminal_surface_regression():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminEvidenceWorkflowPage.tsx",
        "\n".join([
            "import { Badge, GlassCard } from '../components/common';",
            "function toneClass(tone) { return tone; }",
            "export default function Page() {",
            "  return <GlassCard><Badge variant='info'>只读</Badge><details><summary>折叠</summary></details></GlassCard>;",
            "}",
        ]),
    )

    assert any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_allows_admin_terminal_disclosure_after_migration():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminCostObservabilityPage.tsx",
        "\n".join([
            "import { TerminalChip, TerminalDisclosure, TerminalPanel } from '../components/terminal';",
            "export default function Page() {",
            "  return <TerminalPanel><TerminalChip variant='info'>只读</TerminalChip><TerminalDisclosure title='细节' summary='默认折叠'>内容</TerminalDisclosure></TerminalPanel>;",
            "}",
        ]),
    )

    assert not any(item.rule == "retired-local-terminal-primitive" for item in result.findings)
