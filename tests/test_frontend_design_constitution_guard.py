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


def test_flags_consumer_visible_raw_ohlcv_readiness_copy():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/MarketOverviewPage.tsx",
        "<p>raw OHLCV readiness is missing</p>",
    )

    assert any(item.rule == "consumer-visible-internal-boundary-copy" for item in result.findings)


def test_flags_consumer_visible_provider_runtime_keys():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/WatchlistPage.tsx",
        "<span>provider_status: provider_timeout</span>",
    )

    assert any(item.rule == "consumer-visible-internal-boundary-copy" for item in result.findings)


def test_flags_consumer_visible_implementation_boundary_wording():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/PortfolioPage.tsx",
        "<p>broker adapter and accounting engine are unavailable</p>",
    )

    assert any(item.rule == "consumer-visible-internal-boundary-copy" for item in result.findings)


def test_flags_deny_list_style_advice_disclaimer():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/StockStructureDecisionPage.tsx",
        "<p>Not investment advice: do not buy, sell, or hold based on this page.</p>",
    )

    assert any(item.rule == "consumer-visible-advice-deny-list" for item in result.findings)


def test_allows_backtest_strategy_action_descriptions():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/BacktestPage.tsx",
        "<p>Strategy rule: buy on breakout and sell on trailing stop.</p>",
    )

    assert not any(item.rule == "consumer-visible-advice-deny-list" for item in result.findings)


def test_allows_admin_internal_vocabulary():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx",
        "<p>provider_status provider_timeout raw OHLCV readiness</p>",
    )

    assert not any(item.rule == "consumer-visible-internal-boundary-copy" for item in result.findings)


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


def test_ignores_inert_terminal_page_heading_marker_strings():
    guard = load_guard_module()
    inert_attribute = 'data-design-constitution-' + 'marker="' + '<' + 'TerminalPageHeading">'
    inert_comment = "{/* " + "<" + "TerminalPageHeading /> marker */}"

    result = guard.scan_text(
        "apps/dsa-web/src/pages/BacktestPage.tsx",
        "\n".join([
            f"<main {inert_attribute}>",
            inert_comment,
            "missing real heading",
            "</main>",
        ]),
    )

    assert any(item.rule == "route-semantic-page-heading" for item in result.findings)


def test_allows_market_overview_observation_head_heading_contract():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/MarketOverviewPage.tsx",
        "<MarketOverviewWorkbench heading={null} />",
    )

    assert not any(item.rule == "route-semantic-page-heading" for item in result.findings)


def test_allows_user_scanner_dense_page_header_heading_contract():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/UserScannerPage.tsx",
        '<DensePageHeader data-testid="scanner-page-heading" title="发现 / 扫描器" />',
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


def test_flags_admin_provider_circuit_retired_terminal_surface_regression():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx",
        "\n".join([
            "import { GlassCard } from '../components/common';",
            "import { StatusBadge } from '../components/ui/StatusBadge';",
            "const tile = SummaryTile;",
            "export default function Page() {",
            "  return <GlassCard><StatusBadge status='open' label='打开' /></GlassCard>;",
            "}",
        ]),
    )

    assert any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_flags_admin_provider_circuit_local_helper_regressions():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx",
        "\n".join([
            "const valueClass = toneClass('warn')",
            "const Chips = ReadOnlyBadges;",
            "export default function Page() {",
            "  return <CollapsibleTerminalBlock title='二级细节' summary='默认折叠'><details><summary>更多</summary></details></CollapsibleTerminalBlock>;",
            "}",
        ]),
    )

    assert any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_allows_admin_provider_circuit_terminal_primitives_after_migration():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx",
        "\n".join([
            "import { TerminalChip, TerminalNestedBlock, TerminalPanel } from '../components/terminal';",
            "export default function Page() {",
            "  return <TerminalPanel><TerminalNestedBlock><TerminalChip variant='caution'>只读诊断</TerminalChip></TerminalNestedBlock></TerminalPanel>;",
            "}",
        ]),
    )

    assert not any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_does_not_apply_admin_provider_circuit_retired_rules_to_non_target_pages():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/SettingsPage.tsx",
        "\n".join([
            "import { GlassCard } from '../components/common';",
            "import { StatusBadge } from '../components/ui/StatusBadge';",
            "const tile = SummaryTile;",
            "export default function Page() {",
            "  return <GlassCard><StatusBadge status='info' label='说明' /></GlassCard>;",
            "}",
        ]),
    )

    assert not any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


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


def test_flags_watchlist_retired_terminal_surface_regression():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/WatchlistPage.tsx",
        "\n".join([
            "import { Button, Disclosure, GlassCard } from '../components/common';",
            "const tile = SummaryTile;",
            "export default function Page() {",
            "  return <GlassCard><Button>刷新</Button><Disclosure summary='高级细节'>内容</Disclosure><details><summary>更多</summary></details></GlassCard>;",
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


def test_allows_watchlist_terminal_disclosure_notice_and_button_primitives():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/WatchlistPage.tsx",
        "\n".join([
            "import { TerminalButton, TerminalChip, TerminalDisclosure, TerminalNotice, TerminalPanel } from '../components/terminal';",
            "export default function Page() {",
            "  return <TerminalPanel><TerminalChip variant='info'>观察</TerminalChip><TerminalNotice variant='info'>当前终端组件允许保留</TerminalNotice><TerminalDisclosure title='批次细节' summary='默认折叠'>只读内容</TerminalDisclosure><TerminalButton variant='secondary'>刷新</TerminalButton></TerminalPanel>;",
            "}",
        ]),
    )

    assert not any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_does_not_apply_watchlist_retired_rules_to_non_target_pages():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/SettingsPage.tsx",
        "\n".join([
            "import { Button, Disclosure, GlassCard } from '../components/common';",
            "const tile = SummaryTile;",
            "export default function Page() {",
            "  return <GlassCard><Button>保存</Button><Disclosure summary='高级选项'>内容</Disclosure><details><summary>更多</summary></details></GlassCard>;",
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


def test_flags_admin_cost_statusbadge_button_and_disclosure_regression():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminCostObservabilityPage.tsx",
        "\n".join([
            "import { Button, Disclosure } from '../components/common';",
            "import { StatusBadge } from '../components/ui/StatusBadge';",
            "export default function Page() {",
            "  return <><StatusBadge status='warn' label='告警' /><Button>刷新</Button><Disclosure summary='账本原始细节'>内容</Disclosure></>;",
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


def test_flags_admin_evidence_statusbadge_button_and_disclosure_regression():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminEvidenceWorkflowPage.tsx",
        "\n".join([
            "import { Button, Disclosure } from '../components/common';",
            "import { StatusBadge } from '../components/ui/StatusBadge';",
            "export default function Page() {",
            "  return <><StatusBadge status='info' label='只读' /><Button>刷新</Button><Disclosure summary='字段结构'>内容</Disclosure></>;",
            "}",
        ]),
    )

    assert any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_allows_admin_cost_terminal_primitives_after_migration():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminCostObservabilityPage.tsx",
        "\n".join([
            "import { TerminalButton, TerminalChip, TerminalDisclosure, TerminalPanel } from '../components/terminal';",
            "export default function Page() {",
            "  return <TerminalPanel><TerminalChip variant='info'>只读</TerminalChip><TerminalButton variant='secondary'>刷新</TerminalButton><TerminalDisclosure title='细节' summary='默认折叠'>内容</TerminalDisclosure></TerminalPanel>;",
            "}",
        ]),
    )

    assert not any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_allows_admin_evidence_terminal_primitives_after_migration():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminEvidenceWorkflowPage.tsx",
        "\n".join([
            "import { TerminalButton, TerminalChip, TerminalDisclosure, TerminalPanel } from '../components/terminal';",
            "export default function Page() {",
            "  return <TerminalPanel><TerminalChip variant='neutral'>脱敏状态</TerminalChip><TerminalButton variant='secondary'>刷新</TerminalButton><TerminalDisclosure title='字段结构' summary='默认收起'>内容</TerminalDisclosure></TerminalPanel>;",
            "}",
        ]),
    )

    assert not any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_does_not_apply_admin_cost_evidence_retired_rules_to_non_target_pages():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/SettingsPage.tsx",
        "\n".join([
            "import { Button, Disclosure } from '../components/common';",
            "import { StatusBadge } from '../components/ui/StatusBadge';",
            "export default function Page() {",
            "  return <><StatusBadge status='info' label='说明' /><Button>保存</Button><Disclosure summary='高级选项'>内容</Disclosure></>;",
            "}",
        ]),
    )

    assert not any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_flags_admin_logs_retired_terminal_surface_regression():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminLogsPage.tsx",
        "\n".join([
            "import { ApiErrorAlert, Drawer, GlassCard } from '../components/common';",
            "import { StatusBadge, getStatusLabel } from '../components/ui/StatusBadge';",
            "const levelClass = LEVEL_CLASS.DEBUG;",
            "const severity = severityClass('failed');",
            "export default function Page() {",
            "  return <GlassCard><details className='rounded-3xl border border-white/8 bg-white/[0.018] p-5'><summary className='cursor-pointer text-sm font-semibold text-foreground'>LLM 调用链</summary><StatusBadge status='failed' label='失败' variant='soft' size='sm' /></details></GlassCard>;",
            "}",
        ]),
    )

    assert any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_flags_admin_logs_remaining_retired_visual_patterns():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminLogsPage.tsx",
        "\n".join([
            "import { Badge } from '../components/common';",
            "const tile = SummaryTile;",
            "export default function Page() {",
            "  return <details><summary>执行细节</summary><Badge variant='warning'>告警</Badge></details>;",
            "}",
        ]),
    )

    assert any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_allows_admin_logs_terminal_primitives_with_status_utilities():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminLogsPage.tsx",
        "\n".join([
            "import { TerminalButton, TerminalChip, TerminalDisclosure, TerminalPanel } from '../components/terminal';",
            "import { getStatusLabel, normalizeStatus, type UnifiedStatus } from '../components/ui/StatusBadge';",
            "export default function Page() {",
            "  const status = normalizeStatus('running') as UnifiedStatus;",
            "  return <TerminalPanel><TerminalChip variant='info'>{getStatusLabel(status)}</TerminalChip><TerminalButton variant='secondary'>复制执行摘要</TerminalButton><TerminalDisclosure title='执行细节' summary='默认收起'>脱敏内容</TerminalDisclosure></TerminalPanel>;",
            "}",
        ]),
    )

    assert not any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_does_not_apply_admin_logs_retired_rules_to_non_target_pages():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/SettingsPage.tsx",
        "\n".join([
            "import { Badge } from '../components/common';",
            "const tile = SummaryTile;",
            "export default function Page() {",
            "  return <details><summary>高级选项</summary><Badge variant='info'>说明</Badge></details>;",
            "}",
        ]),
    )

    assert not any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_flags_admin_notifications_retired_terminal_surface_regression():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminNotificationsPage.tsx",
        "\n".join([
            "import { Badge, Button, Disclosure, GlassCard } from '../components/common';",
            "export default function Page() {",
            "  return <GlassCard><Badge variant='warning'>告警</Badge><Button>发送测试</Button><Disclosure summary='原始响应'>细节</Disclosure><details><summary>Webhook 错误</summary></details></GlassCard>;",
            "}",
        ]),
    )

    assert any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_allows_admin_notifications_terminal_primitives_after_migration():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminNotificationsPage.tsx",
        "\n".join([
            "import { TerminalButton, TerminalChip, TerminalDisclosure, TerminalNotice, TerminalPanel } from '../components/terminal';",
            "export default function Page() {",
            "  return <TerminalPanel><TerminalChip variant='caution'>Webhook 告警</TerminalChip><TerminalButton variant='secondary'>发送测试</TerminalButton><TerminalNotice variant='info' title='已脱敏'>仅展示安全诊断。</TerminalNotice><TerminalDisclosure title='Webhook 错误' summary='默认折叠'>细节</TerminalDisclosure></TerminalPanel>;",
            "}",
        ]),
    )

    assert not any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_does_not_apply_admin_notifications_retired_rules_to_non_target_pages():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/SettingsPage.tsx",
        "\n".join([
            "import { Badge, Button, Disclosure, GlassCard } from '../components/common';",
            "export default function Page() {",
            "  return <GlassCard><Badge variant='info'>说明</Badge><Button>保存</Button><Disclosure summary='高级选项'>内容</Disclosure><details><summary>更多</summary></details></GlassCard>;",
            "}",
        ]),
    )

    assert not any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_flags_admin_users_retired_terminal_surface_regression():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminUsersPage.tsx",
        "\n".join([
            "import { Badge, Button, Disclosure, GlassCard } from '../components/common';",
            "const badgeRow = ReadOnlyBadges;",
            "const tile = SummaryTile;",
            "const risk = riskTone('warning');",
            "const status = statusTone('active');",
            "export default function Page() {",
            "  return <GlassCard><Badge variant='info'>只读</Badge><Button>刷新目录</Button><Disclosure summary='后续阶段占位'>原始数据库浏览器、原始 prompt、provider 载荷与堆栈明细不在本阶段展示。</Disclosure><details><summary>脱敏元数据</summary></details></GlassCard>;",
            "}",
        ]),
    )

    assert any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_flags_admin_users_raw_sensitive_operator_copy_regression():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminUsersPage.tsx",
        '<p>响应不会返回密码、哈希、Cookie、token 或原始 session id。</p>',
    )

    assert any(item.rule == "retired-local-terminal-primitive" for item in result.findings)


def test_allows_admin_users_terminal_primitives_after_migration():
    guard = load_guard_module()

    result = guard.scan_text(
        "apps/dsa-web/src/pages/AdminUsersPage.tsx",
        "\n".join([
            "import { TerminalButton, TerminalChip, TerminalDisclosure, TerminalPanel } from '../components/terminal';",
            "export default function Page() {",
            "  return <TerminalPanel><TerminalChip variant='neutral'>敏感字段脱敏</TerminalChip><TerminalButton variant='secondary'>刷新目录</TerminalButton><TerminalDisclosure title='脱敏元数据' summary='默认收起'>默认只展示安全投影。</TerminalDisclosure></TerminalPanel>;",
            "}",
        ]),
    )

    assert not any(item.rule == "retired-local-terminal-primitive" for item in result.findings)
