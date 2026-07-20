#!/usr/bin/env python3
"""Lightweight WolfyStock frontend design-constitution guard."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = [
    ROOT / "apps" / "dsa-web" / "src" / "pages",
    ROOT / "apps" / "dsa-web" / "src" / "components",
]

MIGRATED_PAGES = {
    "apps/dsa-web/src/pages/PortfolioPage.tsx",
    "apps/dsa-web/src/pages/UserScannerPage.tsx",
}

KEY_ROUTE_PAGES = {
    "apps/dsa-web/src/pages/UserScannerPage.tsx",
    "apps/dsa-web/src/pages/MarketOverviewPage.tsx",
    "apps/dsa-web/src/pages/BacktestPage.tsx",
    "apps/dsa-web/src/pages/OptionsLabPage.tsx",
    "apps/dsa-web/src/pages/PersonalSettingsPage.tsx",
}

USER_PAGE_PARTS = (
    "/PortfolioPage.tsx",
    "/UserScannerPage.tsx",
    "/OptionsLabPage.tsx",
    "/HomeBentoDashboardPage.tsx",
    "/MarketOverviewPage.tsx",
    "/BacktestPage.tsx",
    "/DeterministicBacktestResultPage.tsx",
    "/ResearchRadarPage.tsx",
    "/MarketRotationRadarPage.tsx",
    "/MarketDecisionCockpitPage.tsx",
    "/WatchlistPage.tsx",
    "/ScenarioLabPage.tsx",
    "/StockStructureDecisionPage.tsx",
    "/StockStructureDecisionEntryPage.tsx",
    "/ChatPage.tsx",
)

INTERNAL_TERMS = (
    "开发者详情",
    "provider_timeout",
    "not_enough_history",
    "fundamentals_unavailable",
    "optional_news_timeout",
    "LLM Ledger",
    "QUOTA PILOT",
    "MarketCache",
    "local_db",
    "generatedCandidates",
    "failedCandidates",
    "fixture",
    "mock",
)

RAW_VISIBLE_TERMS = ("raw", "debug", "schema", "trace")

CONSUMER_VISIBLE_INTERNAL_COPY_RULES = (
    (
        re.compile(r"\braw\s+OHLCV\s+(?:readiness|status|state|quality)\b", re.IGNORECASE),
        "Raw OHLCV readiness/status wording must be mapped before it is shown in consumer status surfaces.",
    ),
    (
        re.compile(r"\b(?:provider|runtime|internal|cache|source)[_-](?:status|state|key|payload|trace|error|reason)\b", re.IGNORECASE),
        "Consumer-visible copy must not expose provider/runtime/internal snake_case keys.",
    ),
    (
        re.compile(r"\b(?:internal|runtime|cache|source)\s+(?:key|payload|trace|enum)\b", re.IGNORECASE),
        "Consumer-visible copy must not expose internal/runtime implementation keys.",
    ),
    (
        re.compile(r"\b(?:broker adapter|broker protocol|accounting engine|ledger implementation|order execution adapter|order router)\b", re.IGNORECASE),
        "Ordinary consumer pages must not expose broker/accounting/order implementation-boundary wording.",
    ),
)

ADVICE_DENY_LIST_CONTEXT_RE = re.compile(
    r"(?:not\s+(?:investment\s+)?advice|not\s+a\s+recommendation|不(?:构成|提供|作为).{0,12}(?:投资建议|交易建议)|非投资建议)",
    re.IGNORECASE,
)
ADVICE_ACTION_RE = re.compile(r"\b(?:buy|sell|hold)\b|买入|卖出|持有|加仓|减仓", re.IGNORECASE)

WATCHLIST_RETIRED_TERMINAL_SURFACE_RULES = [
    (
        re.compile(r"\bWATCHLIST_(?:BUTTON_CLASS|LINK_BUTTON_CLASS|BADGE_CLASS)\b"),
        "Watchlist migrated terminal surface must not restore retired local button/badge class bridges.",
    ),
    (
        re.compile(r"\bdisplayBadgeVariant\b"),
        "Watchlist migrated status chips must keep using TerminalChip instead of retired displayBadgeVariant mapping.",
    ),
    (
        re.compile(r"\bSectionShell\b"),
        "Watchlist migrated page frame must keep using TerminalPanel and TerminalPageShell instead of SectionShell.",
    ),
    (
        re.compile(r"import\s*\{[^}]*\bBadge\b[^}]*\}\s*from\s*['\"][^'\"]*components/common['\"]"),
        "Watchlist migrated evidence badges must not re-import common Badge after TerminalChip migration.",
    ),
    (
        re.compile(r"import\s*\{[^}]*\bStatusBadge\b[^}]*\}\s*from\s*['\"][^'\"]*StatusBadge['\"]"),
        "Watchlist migrated evidence/status chips must not re-import retired StatusBadge.",
    ),
    (
        re.compile(r"<Badge\b"),
        "Watchlist migrated evidence/status chips must keep using TerminalChip instead of local Badge tags.",
    ),
    (
        re.compile(r"<StatusBadge\b"),
        "Watchlist migrated evidence/status chips must keep using TerminalChip instead of retired StatusBadge.",
    ),
    (
        re.compile(r"\bGlassCard\b"),
        "Watchlist migrated terminal surface must keep using TerminalPanel or TerminalNotice instead of GlassCard.",
    ),
    (
        re.compile(r"\bSummaryTile\b"),
        "Watchlist migrated summary cells must not restore retired SummaryTile material helpers.",
    ),
    (
        re.compile(r"<details\b"),
        "Watchlist migrated advanced details must keep using TerminalDisclosure instead of native details shells.",
    ),
    (
        re.compile(r"<summary\b"),
        "Watchlist migrated advanced details must keep using TerminalDisclosure instead of native summary shells.",
    ),
    (
        re.compile(r"import\s*\{[^}]*\bButton\b[^}]*\}\s*from\s*['\"][^'\"]*components/common['\"]"),
        "Watchlist migrated actions must not re-import the retired common Button surface.",
    ),
    (
        re.compile(r"<Button\b"),
        "Watchlist migrated actions must keep using TerminalButton instead of the retired common Button surface.",
    ),
    (
        re.compile(r"import\s*\{[^}]*\bDisclosure\b[^}]*\}\s*from\s*['\"][^'\"]*components/common['\"]"),
        "Watchlist migrated advanced details must not re-import the retired common Disclosure surface.",
    ),
    (
        re.compile(r"<Disclosure\b"),
        "Watchlist migrated advanced details must keep using TerminalDisclosure instead of the retired common Disclosure surface.",
    ),
]

ADMIN_TERMINAL_SURFACE_RETIREMENT_RULES = [
    (
        re.compile(r"\bGlassCard\b"),
        "Migrated admin terminal surfaces must keep using TerminalPanel or TerminalNestedBlock instead of GlassCard.",
    ),
    (
        re.compile(r"import\s*\{[^}]*\bBadge\b[^}]*\}\s*from\s*['\"][^'\"]*components/common['\"]"),
        "Migrated admin terminal surfaces must not re-import common Badge after TerminalChip migration.",
    ),
    (
        re.compile(r"<Badge\b"),
        "Migrated admin terminal surfaces must keep using TerminalChip instead of local Badge tags.",
    ),
    (
        re.compile(r"\bSummaryTile\b"),
        "Migrated admin terminal surfaces must not restore retired SummaryTile material helpers.",
    ),
    (
        re.compile(r"\bSectionCard\b"),
        "Migrated admin terminal surfaces must not restore retired SectionCard wrappers.",
    ),
    (
        re.compile(r"\btoneClass\b"),
        "Migrated admin terminal surfaces must not restore retired toneClass-style badge material helpers.",
    ),
    (
        re.compile(r"<details\b"),
        "Migrated admin terminal surfaces must keep using TerminalDisclosure instead of native details shells.",
    ),
    (
        re.compile(r"<summary\b"),
        "Migrated admin terminal surfaces must keep using TerminalDisclosure instead of native summary shells.",
    ),
]

ADMIN_COST_EVIDENCE_TERMINAL_SURFACE_RETIREMENT_RULES = [
    *ADMIN_TERMINAL_SURFACE_RETIREMENT_RULES,
    (
        re.compile(r"import\s*\{[^}]*\bStatusBadge\b[^}]*\}\s*from\s*['\"][^'\"]*StatusBadge['\"]"),
        "Admin Cost/Admin Evidence migrated status chips must not re-import the retired StatusBadge component.",
    ),
    (
        re.compile(r"<StatusBadge\b"),
        "Admin Cost/Admin Evidence migrated status chips must keep using TerminalChip-based status pills instead of StatusBadge.",
    ),
    (
        re.compile(r"import\s*\{[^}]*\bButton\b[^}]*\}\s*from\s*['\"][^'\"]*components/common['\"]"),
        "Admin Cost/Admin Evidence migrated actions must not re-import the retired common Button surface.",
    ),
    (
        re.compile(r"<Button\b"),
        "Admin Cost/Admin Evidence migrated actions must keep using TerminalButton instead of the retired common Button surface.",
    ),
    (
        re.compile(r"import\s*\{[^}]*\bDisclosure\b[^}]*\}\s*from\s*['\"][^'\"]*components/common['\"]"),
        "Admin Cost/Admin Evidence migrated advanced details must not re-import the retired common Disclosure surface.",
    ),
    (
        re.compile(r"<Disclosure\b"),
        "Admin Cost/Admin Evidence migrated advanced details must keep using TerminalDisclosure instead of the retired common Disclosure surface.",
    ),
]

ADMIN_LOGS_RETIRED_TERMINAL_SURFACE_RULES = [
    (
        re.compile(r"\bGlassCard\b"),
        "Admin Logs migrated terminal surface must keep using TerminalPageShell/TerminalPanel instead of GlassCard.",
    ),
    (
        re.compile(r"import\s*\{[^}]*\bBadge\b[^}]*\}\s*from\s*['\"][^'\"]*components/common['\"]"),
        "Admin Logs migrated status chips must not re-import common Badge after TerminalChip migration.",
    ),
    (
        re.compile(r"<Badge\b"),
        "Admin Logs migrated status chips must keep using TerminalChip instead of local Badge tags.",
    ),
    (
        re.compile(r"import\s*\{[^}]*\bStatusBadge\b[^}]*\}\s*from\s*['\"][^'\"]*StatusBadge['\"]"),
        "Admin Logs migrated status chips must not re-import the retired StatusBadge component.",
    ),
    (
        re.compile(r"<StatusBadge\b"),
        "Admin Logs migrated status chips must keep using TerminalChip-based status pills instead of StatusBadge.",
    ),
    (
        re.compile(r"\bLEVEL_CLASS\b"),
        "Admin Logs migrated level badges must not restore retired LEVEL_CLASS material maps.",
    ),
    (
        re.compile(r"\bseverityClass\b"),
        "Admin Logs migrated severity badges must not restore retired severityClass material helpers.",
    ),
    (
        re.compile(r"\bSummaryTile\b"),
        "Admin Logs migrated summary cells must not restore retired SummaryTile helpers.",
    ),
    (
        re.compile(r"\bAdminLogsDisclosure\b"),
        "Admin Logs migrated advanced details must keep using TerminalDisclosure instead of a retired page-local disclosure wrapper.",
    ),
    (
        re.compile(r"<details\b"),
        "Admin Logs migrated advanced details must keep using TerminalDisclosure instead of native details shells.",
    ),
    (
        re.compile(r"<summary\b"),
        "Admin Logs migrated advanced details must keep using TerminalDisclosure instead of native summary shells.",
    ),
    (
        re.compile(r"rounded-(?:\[20px\]|2xl|3xl)\s+border\s+border-white/(?:5|6|8)\s+bg-(?:black/20|white/\[(?:0\.018|0\.02|0\.025)\])"),
        "Admin Logs migrated page-local shell classes removed by the terminal wave must not be reintroduced.",
    ),
]

ADMIN_USERS_RETIRED_TERMINAL_SURFACE_RULES = [
    (
        re.compile(r"\bGlassCard\b"),
        "Admin Users migrated terminal surface must keep using TerminalPanel/TerminalNestedBlock instead of GlassCard.",
    ),
    (
        re.compile(r"import\s*\{[^}]*\bBadge\b[^}]*\}\s*from\s*['\"][^'\"]*components/common['\"]"),
        "Admin Users migrated status chips must not re-import common Badge after TerminalChip migration.",
    ),
    (
        re.compile(r"<Badge\b"),
        "Admin Users migrated status chips must keep using TerminalChip instead of local Badge tags.",
    ),
    (
        re.compile(r"import\s*\{[^}]*\bButton\b[^}]*\}\s*from\s*['\"][^'\"]*components/common['\"]"),
        "Admin Users migrated actions must not re-import the retired common Button surface.",
    ),
    (
        re.compile(r"<Button\b"),
        "Admin Users migrated actions must keep using TerminalButton instead of the retired common Button surface.",
    ),
    (
        re.compile(r"import\s*\{[^}]*\bDisclosure\b[^}]*\}\s*from\s*['\"][^'\"]*components/common['\"]"),
        "Admin Users migrated advanced details must not re-import the retired common Disclosure surface.",
    ),
    (
        re.compile(r"<Disclosure\b"),
        "Admin Users migrated advanced details must keep using TerminalDisclosure instead of the retired common Disclosure surface.",
    ),
    (
        re.compile(r"\bReadOnlyBadges\b"),
        "Admin Users migrated header badges must not restore retired ReadOnlyBadges helper material.",
    ),
    (
        re.compile(r"\bSummaryTile\b"),
        "Admin Users migrated summary cells must not restore retired SummaryTile helpers.",
    ),
    (
        re.compile(r"\briskTone\b"),
        "Admin Users migrated risk chips must not restore retired riskTone badge material helpers.",
    ),
    (
        re.compile(r"\bstatusTone\b"),
        "Admin Users migrated status chips must not restore retired statusTone badge material helpers.",
    ),
    (
        re.compile(r"<details\b"),
        "Admin Users migrated advanced details must keep using TerminalDisclosure instead of native details shells.",
    ),
    (
        re.compile(r"<summary\b"),
        "Admin Users migrated advanced details must keep using TerminalDisclosure instead of native summary shells.",
    ),
    (
        re.compile(r"密码、哈希、Cookie、(?:token|令牌)\s*或原始\s*(?:session id|会话值)"),
        "Admin Users default operator copy must keep using sanitized credential wording instead of raw sensitive-field lists.",
    ),
]

ADMIN_NOTIFICATIONS_RETIRED_TERMINAL_SURFACE_RULES = [
    (
        re.compile(r"\bGlassCard\b"),
        "Admin Notifications migrated terminal surface must keep using TerminalPanel or TerminalNestedBlock instead of GlassCard.",
    ),
    (
        re.compile(r"import\s*\{[^}]*\bBadge\b[^}]*\}\s*from\s*['\"][^'\"]*components/common['\"]"),
        "Admin Notifications migrated status chips must not re-import common Badge after TerminalChip migration.",
    ),
    (
        re.compile(r"<Badge\b"),
        "Admin Notifications migrated status chips must keep using TerminalChip instead of local Badge tags.",
    ),
    (
        re.compile(r"import\s*\{[^}]*\bButton\b[^}]*\}\s*from\s*['\"][^'\"]*components/common['\"]"),
        "Admin Notifications migrated actions must not re-import the retired common Button surface.",
    ),
    (
        re.compile(r"<Button\b"),
        "Admin Notifications migrated actions must keep using TerminalButton instead of the retired common Button surface.",
    ),
    (
        re.compile(r"import\s*\{[^}]*\bDisclosure\b[^}]*\}\s*from\s*['\"][^'\"]*components/common['\"]"),
        "Admin Notifications migrated advanced details must not re-import the retired common Disclosure surface.",
    ),
    (
        re.compile(r"<Disclosure\b"),
        "Admin Notifications migrated advanced details must keep using TerminalDisclosure instead of the retired common Disclosure surface.",
    ),
    (
        re.compile(r"<details\b"),
        "Admin Notifications migrated advanced details must keep using TerminalDisclosure instead of native details shells.",
    ),
    (
        re.compile(r"<summary\b"),
        "Admin Notifications migrated advanced details must keep using TerminalDisclosure instead of native summary shells.",
    ),
]

RETIRED_LOCAL_PRIMITIVE_RULES = {
    "apps/dsa-web/src/pages/MarketOverviewPage.tsx": [
        (
            re.compile(r"\bMARKET_OVERVIEW_GHOST_CARD_CLASS\b"),
            "Market Overview migrated panel shells must keep using TerminalPanel, not retired ghost-card bridge constants.",
        ),
        (
            re.compile(r"\bMARKET_OVERVIEW_CARD_TITLE_CLASS\b"),
            "Market Overview migrated panel headings must not reintroduce retired local title material helpers.",
        ),
        (
            re.compile(r"\bbuildDecisionChipTone\b"),
            "Market Overview migrated decision chips must keep using TerminalChip instead of local tone builders.",
        ),
    ],
    "apps/dsa-web/src/pages/MarketRotationRadarPage.tsx": [
        (
            re.compile(r"\bEvidenceBadge\b"),
            "Rotation Radar migrated evidence/status chips must keep using TerminalChip instead of local EvidenceBadge.",
        ),
    ],
    "apps/dsa-web/src/pages/AdminProviderCircuitDiagnosticsPage.tsx": [
        (
            re.compile(r"<Badge\b"),
            "Admin Provider Circuit Diagnostics migrated status chips must keep using TerminalChip instead of local Badge tags.",
        ),
        (
            re.compile(r"import\s*\{[^}]*\bBadge\b[^}]*\}\s*from"),
            "Admin Provider Circuit Diagnostics must not re-import a local Badge for migrated status chips.",
        ),
        (
            re.compile(r"\bGlassCard\b"),
            "Admin Provider Circuit Diagnostics migrated terminal surface must keep using TerminalPanel or TerminalNestedBlock instead of GlassCard.",
        ),
        (
            re.compile(r"\bSummaryTile\b"),
            "Admin Provider Circuit Diagnostics migrated summary cells must not restore retired SummaryTile helpers.",
        ),
        (
            re.compile(r"import\s*\{[^}]*\bStatusBadge\b[^}]*\}\s*from\s*['\"][^'\"]*StatusBadge['\"]"),
            "Admin Provider Circuit Diagnostics migrated status chips must not re-import the retired StatusBadge component.",
        ),
        (
            re.compile(r"<StatusBadge\b"),
            "Admin Provider Circuit Diagnostics migrated status chips must keep using TerminalChip-based status pills instead of StatusBadge.",
        ),
        (
            re.compile(r"\bCollapsibleTerminalBlock\b"),
            "Admin Provider Circuit Diagnostics migrated advanced details must keep using TerminalDisclosure instead of the retired CollapsibleTerminalBlock helper.",
        ),
        (
            re.compile(r"\bReadOnlyBadges\b"),
            "Admin Provider Circuit Diagnostics migrated header chips must stay inline with TerminalChip instead of the retired ReadOnlyBadges helper.",
        ),
        (
            re.compile(r"\btoneClass\b"),
            "Admin Provider Circuit Diagnostics migrated metric tones must not restore the retired toneClass helper.",
        ),
        (
            re.compile(r"<details\b"),
            "Admin Provider Circuit Diagnostics migrated advanced details must keep using TerminalDisclosure instead of native details shells in the page source.",
        ),
        (
            re.compile(r"<summary\b"),
            "Admin Provider Circuit Diagnostics migrated advanced details must keep using TerminalDisclosure instead of native summary shells in the page source.",
        ),
    ],
    "apps/dsa-web/src/pages/WatchlistPage.tsx": WATCHLIST_RETIRED_TERMINAL_SURFACE_RULES,
    "apps/dsa-web/src/pages/AdminCostObservabilityPage.tsx": ADMIN_COST_EVIDENCE_TERMINAL_SURFACE_RETIREMENT_RULES,
    "apps/dsa-web/src/pages/AdminEvidenceWorkflowPage.tsx": ADMIN_COST_EVIDENCE_TERMINAL_SURFACE_RETIREMENT_RULES,
    "apps/dsa-web/src/pages/AdminLogsPage.tsx": ADMIN_LOGS_RETIRED_TERMINAL_SURFACE_RULES,
    "apps/dsa-web/src/pages/AdminNotificationsPage.tsx": ADMIN_NOTIFICATIONS_RETIRED_TERMINAL_SURFACE_RULES,
    "apps/dsa-web/src/pages/AdminUsersPage.tsx": ADMIN_USERS_RETIRED_TERMINAL_SURFACE_RULES,
}

SOLID_WRAPPER_RE = re.compile(r"\bbg-(?:black|\[#000\]|\[#050505\]|gray-\S+|zinc-\S+|slate-\S+|neutral-\S+)")
LOUD_WARNING_RE = re.compile(r"\bbg-(yellow|amber)-(\d{2,3})(?:/(\d+))?\b")
HAND_ROLLED_MATERIAL_RE = re.compile(
    r"className=.*(?:rounded-(?:xl|2xl|\[16px\])|border\s+border-white/5|bg-white/\[0\.02\]|bg-white/\[0\.025\])"
)
NATIVE_CONTROL_RE = re.compile(r"<(?:select|input)\b(?:(?!className=).)*>", re.DOTALL)


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int
    message: str
    excerpt: str


@dataclass(frozen=True)
class ScanResult:
    findings: list[Finding]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def iter_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix not in {".tsx", ".ts"}:
                continue
            relative = rel(path)
            if "__tests__" in relative or relative.endswith(".test.tsx") or relative.endswith(".test.ts"):
                continue
            files.append(path)
    return sorted(files)


def normalize_candidate_file(value: str) -> Path | None:
    raw = value.strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / raw
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return None
    if relative.startswith("apps/dsa-web/src/") is False:
        return None
    if resolved.suffix not in {".tsx", ".ts"}:
        return None
    if "__tests__" in relative or relative.endswith(".test.tsx") or relative.endswith(".test.ts"):
        return None
    if not resolved.is_file():
        return None
    return resolved


def read_files_from(path: str) -> list[str]:
    if path == "-":
        return sys.stdin.read().splitlines()
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = ROOT / file_path
    return file_path.read_text(encoding="utf-8").splitlines()


def iter_limited_files(files: list[str], files_from: list[str]) -> list[Path]:
    candidates: list[str] = []
    candidates.extend(files)
    for file_list in files_from:
        candidates.extend(read_files_from(file_list))
    normalized = [path for path in (normalize_candidate_file(value) for value in candidates) if path is not None]
    return sorted(set(normalized))


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def is_user_page(path: str) -> bool:
    return any(path.endswith(part.lstrip("/")) or path.endswith(part) for part in USER_PAGE_PARTS)


def is_guarded_file(path: str) -> bool:
    return path in MIGRATED_PAGES or path.startswith("apps/dsa-web/src/components/terminal/")


def is_key_route_page(path: str) -> bool:
    return path in KEY_ROUTE_PAGES


def repo_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def strip_jsx_comments(text: str) -> str:
    return re.sub(r"\{/\*.*?\*/\}", "", text, flags=re.DOTALL)


def count_jsx_element_openings(text: str, element_name: str) -> int:
    return len(re.findall(rf"(?<![\"'`])<{re.escape(element_name)}\b", text))


def has_dense_page_header_heading_contract() -> bool:
    source = repo_text("apps/dsa-web/src/components/terminal/DenseWorkbenchPrimitives.tsx")
    return (
        "export function DensePageHeader" in source
        and count_jsx_element_openings(strip_jsx_comments(source), "TerminalPageHeading") == 1
    )


def count_dense_page_header_heading_markers(path: str, text: str) -> int:
    if path != "apps/dsa-web/src/pages/UserScannerPage.tsx":
        return 0
    if not has_dense_page_header_heading_contract():
        return 0
    return count_jsx_element_openings(text, "DensePageHeader")


def has_market_overview_observation_heading_contract() -> bool:
    top_surface = repo_text("apps/dsa-web/src/components/market-overview/MarketOverviewWorkbenchTopSurface.tsx")
    observation_head = repo_text("apps/dsa-web/src/components/research/anatomy/ObservationHead.tsx")
    typography = repo_text("apps/dsa-web/src/components/research/anatomy/ResearchTypography.tsx")
    return (
        count_jsx_element_openings(strip_jsx_comments(top_surface), "ObservationHead") == 1
        and 'data-testid="market-overview-observation-head"' in top_surface
        and "Market State Overview" in top_surface
        and "市场状态概览" in top_surface
        and count_jsx_element_openings(strip_jsx_comments(observation_head), "ObservationTitle") == 1
        and "renderTypography('h1'" in typography
        and "'observation-title'" in typography
    )


def count_market_overview_observation_heading_markers(path: str, text: str) -> int:
    if path != "apps/dsa-web/src/pages/MarketOverviewPage.tsx":
        return 0
    if not has_market_overview_observation_heading_contract():
        return 0
    return count_jsx_element_openings(text, "MarketOverviewWorkbench")


def count_level_one_heading_markers(path: str, text: str) -> int:
    semantic_text = strip_jsx_comments(text)
    component_heading_count = (
        count_jsx_element_openings(semantic_text, "TerminalPageHeading")
        + count_dense_page_header_heading_markers(path, semantic_text)
        + count_market_overview_observation_heading_markers(path, semantic_text)
    )
    if component_heading_count:
        return component_heading_count
    return (
        count_jsx_element_openings(semantic_text, "h1")
        + len(re.findall(r'aria-level\s*=\s*(?:\{1\}|"1")', semantic_text))
    )


def is_loud_warning_material(line: str) -> bool:
    for match in LOUD_WARNING_RE.finditer(line):
        if match.group(3) is None and line[match.end():].startswith('/['):
            continue
        opacity = int(match.group(3) or "100")
        if opacity >= 20:
            return True
    return False


def is_visible_line(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("//") or stripped.startswith("*"):
        return False
    return bool(
        (">" in stripped and "<" in stripped)
        or re.search(r'(?:title|label|placeholder|summary|message|body|description)\s*=\s*["{\']', stripped)
        or re.search(r'(?:title|label|placeholder|message|body|description)\s*:\s*["\']', stripped)
    )


def add(finding_list: list[Finding], rule: str, path: str, text: str, offset: int, message: str, excerpt: str) -> None:
    finding_list.append(Finding(rule=rule, path=path, line=line_number(text, offset), message=message, excerpt=excerpt.strip()[:180]))


def scan_text(path: str, text: str) -> ScanResult:
    findings: list[Finding] = []
    normalized = path.replace("\\", "/")
    lines = text.splitlines()
    guarded = is_guarded_file(normalized)
    key_route_page = is_key_route_page(normalized)

    if key_route_page:
        heading_count = count_level_one_heading_markers(normalized, text)
        if heading_count == 0:
            findings.append(Finding(
                rule="route-semantic-page-heading",
                path=normalized,
                line=1,
                message="Key user routes must expose exactly one compact semantic page heading.",
                excerpt="missing semantic page heading marker",
            ))
        elif heading_count > 1:
            findings.append(Finding(
                rule="route-semantic-page-heading",
                path=normalized,
                line=1,
                message="Key user routes must not declare multiple page-level semantic headings.",
                excerpt=f"found {heading_count} page heading markers",
            ))

    for index, line in enumerate(lines):
        if "design-constitution-allow" in line:
            continue
        lower_line = line.lower()
        likely_wrapper = (
            "terminalpageshell" in lower_line
            or (
                "data-testid" in line
                and any(token in lower_line for token in ("page", "workspace", "root", "shell", "stage"))
            )
        )
        if key_route_page and SOLID_WRAPPER_RE.search(line) and likely_wrapper:
            if "bg-black/20" not in line and "TerminalNestedBlock" not in line:
                findings.append(Finding(
                    rule="page-level-solid-slab",
                    path=normalized,
                    line=index + 1,
                    message="Avoid page-level solid black/gray/zinc/slate/neutral slabs; use docs/design/frontend.md paper shell/panel primitives.",
                    excerpt=line.strip()[:180],
                ))
        if key_route_page and is_loud_warning_material(line):
                findings.append(Finding(
                    rule="loud-warning-material",
                    path=normalized,
                    line=index + 1,
                    message="Avoid loud yellow/amber warning slabs; use semantic paper-token caution states.",
                    excerpt=line.strip()[:180],
                ))
        if key_route_page and is_user_page(normalized) and is_visible_line(line):
            for term in INTERNAL_TERMS:
                if term.lower() in lower_line:
                    findings.append(Finding(
                        rule="user-facing-internal-term",
                        path=normalized,
                        line=index + 1,
                        message="User pages must map internal/debug terms to plain Chinese or hide them in disclosure.",
                        excerpt=line.strip()[:180],
                    ))
                    break
            for term in RAW_VISIBLE_TERMS:
                if re.search(rf"\b{re.escape(term)}\b", lower_line):
                    findings.append(Finding(
                        rule="user-facing-internal-term",
                        path=normalized,
                        line=index + 1,
                        message="Raw/debug/schema/trace wording must not be visible on user pages by default.",
                        excerpt=line.strip()[:180],
                    ))
                    break

        if is_user_page(normalized) and is_visible_line(line):
            for pattern, message in CONSUMER_VISIBLE_INTERNAL_COPY_RULES:
                if pattern.search(line):
                    findings.append(Finding(
                        rule="consumer-visible-internal-boundary-copy",
                        path=normalized,
                        line=index + 1,
                        message=message,
                        excerpt=line.strip()[:180],
                    ))
                    break
            if ADVICE_DENY_LIST_CONTEXT_RE.search(line) and len(ADVICE_ACTION_RE.findall(line)) >= 2:
                findings.append(Finding(
                    rule="consumer-visible-advice-deny-list",
                    path=normalized,
                    line=index + 1,
                    message="Avoid deny-list style advice disclaimers that enumerate trading actions; use the product research boundary wording.",
                    excerpt=line.strip()[:180],
                ))

    if normalized in MIGRATED_PAGES and "Terminal" not in text:
        findings.append(Finding(
            rule="migrated-page-terminal-primitives",
            path=normalized,
            line=1,
            message="Migrated pages must import and use shared research primitives.",
            excerpt="missing Terminal primitive import/use",
        ))

    if normalized in MIGRATED_PAGES and "Terminal" not in text:
        for match in HAND_ROLLED_MATERIAL_RE.finditer(text):
            start = match.start()
            context = text[max(0, start - 160): start + 260]
            if "Terminal" in context or "design-constitution-allow" in context:
                continue
            add(
                findings,
                "migrated-page-terminal-primitives",
                normalized,
                text,
                start,
                "Migrated pages should use shared paper-token primitives instead of page-local material classes.",
                match.group(0),
            )
            break

    for pattern, message in RETIRED_LOCAL_PRIMITIVE_RULES.get(normalized, []):
        match = pattern.search(text)
        if not match:
            continue
        add(
            findings,
            "retired-local-terminal-primitive",
            normalized,
            text,
            match.start(),
            message,
            match.group(0),
        )

    if not guarded:
        return ScanResult(findings=findings)

    for match in NATIVE_CONTROL_RE.finditer(text):
        tag = match.group(0)
        if "appearance-none" in tag or "select-surface" in tag or "design-constitution-allow" in tag:
            continue
        add(
            findings,
            "native-control-style",
            normalized,
            text,
            match.start(),
            "Native controls need project styling or terminal input/select treatment.",
            tag,
        )

    return ScanResult(findings=findings)


def scan_project(files: list[Path] | None = None) -> ScanResult:
    findings: list[Finding] = []
    paths = iter_files() if files is None else files
    for path in paths:
        findings.extend(scan_text(rel(path), path.read_text(encoding="utf-8")).findings)
    return ScanResult(findings=findings)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="WolfyStock frontend design constitution guard.",
        epilog=(
            "By default this scans all guarded frontend page/component files. "
            "Use --files/--files-from for changed-file validation tiers."
        ),
    )
    parser.add_argument("--files", nargs="*", default=None, help="limit scan to these repo-relative or absolute files")
    parser.add_argument("--files-from", action="append", default=[], help="read newline-delimited file paths from PATH, or '-' for stdin")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    limited_files = iter_limited_files(args.files or [], args.files_from) if args.files is not None or args.files_from else None
    result = scan_project(limited_files)
    files_scanned = len(iter_files()) if limited_files is None else len(limited_files)
    print("WolfyStock frontend design constitution guard")
    print(f"Files scanned: {files_scanned}")
    if not result.findings:
        print("PASS: no blocking design-constitution violations found.")
        return 0
    print(f"FAIL: {len(result.findings)} blocking design-constitution violation(s).")
    for finding in result.findings[:80]:
        print(f"- {finding.path}:{finding.line} [{finding.rule}] {finding.message}")
        print(f"  {finding.excerpt}")
    if len(result.findings) > 80:
        print(f"- ... {len(result.findings) - 80} more finding(s) omitted")
    return 1


if __name__ == "__main__":
    sys.exit(main())
