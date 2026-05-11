#!/usr/bin/env python3
"""Lightweight WolfyStock frontend design-constitution guard."""

from __future__ import annotations

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

ADMIN_LOGS_RETIRED_TERMINAL_SURFACE_RULES = [
    (
        re.compile(r"\bGlassCard\b"),
        "Admin Logs migrated terminal surface must keep using TerminalPageShell/TerminalPanel instead of GlassCard.",
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
        re.compile(r"\bAdminLogsDisclosure\b"),
        "Admin Logs migrated advanced details must keep using TerminalDisclosure instead of a retired page-local disclosure wrapper.",
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
    ],
    "apps/dsa-web/src/pages/WatchlistPage.tsx": WATCHLIST_RETIRED_TERMINAL_SURFACE_RULES,
    "apps/dsa-web/src/pages/AdminCostObservabilityPage.tsx": ADMIN_TERMINAL_SURFACE_RETIREMENT_RULES,
    "apps/dsa-web/src/pages/AdminEvidenceWorkflowPage.tsx": ADMIN_TERMINAL_SURFACE_RETIREMENT_RULES,
    "apps/dsa-web/src/pages/AdminLogsPage.tsx": ADMIN_LOGS_RETIRED_TERMINAL_SURFACE_RULES,
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


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def is_user_page(path: str) -> bool:
    return any(path.endswith(part.lstrip("/")) or path.endswith(part) for part in USER_PAGE_PARTS)


def is_guarded_file(path: str) -> bool:
    return path in MIGRATED_PAGES or path.startswith("apps/dsa-web/src/components/terminal/")


def is_key_route_page(path: str) -> bool:
    return path in KEY_ROUTE_PAGES


def count_level_one_heading_markers(text: str) -> int:
    terminal_page_heading_count = len(re.findall(r"<TerminalPageHeading\b", text))
    if terminal_page_heading_count:
        return terminal_page_heading_count
    explicit_heading_count = len(re.findall(r"<h1\b", text))
    explicit_heading_count += len(re.findall(r'aria-level\s*=\s*(?:\{1\}|"1")', text))
    return explicit_heading_count


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
        heading_count = count_level_one_heading_markers(text)
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
                    message="Avoid page-level solid black/gray/zinc/slate/neutral slabs; use terminal shell/panel primitives.",
                    excerpt=line.strip()[:180],
                ))
        if key_route_page and is_loud_warning_material(line):
            findings.append(Finding(
                rule="loud-warning-material",
                path=normalized,
                line=index + 1,
                message="Avoid loud yellow/amber warning slabs; use TerminalNotice or TerminalChip caution.",
                excerpt=line.strip()[:180],
            ))
        if key_route_page and is_user_page(normalized) and is_visible_line(line):
            lowered = line.lower()
            for term in INTERNAL_TERMS:
                if term.lower() in lowered:
                    findings.append(Finding(
                        rule="user-facing-internal-term",
                        path=normalized,
                        line=index + 1,
                        message="User pages must map internal/debug terms to plain Chinese or hide them in disclosure.",
                        excerpt=line.strip()[:180],
                    ))
                    break
            for term in RAW_VISIBLE_TERMS:
                if re.search(rf"\b{re.escape(term)}\b", lowered):
                    findings.append(Finding(
                        rule="user-facing-internal-term",
                        path=normalized,
                        line=index + 1,
                        message="Raw/debug/schema/trace wording must not be visible on user pages by default.",
                        excerpt=line.strip()[:180],
                    ))
                    break

    if normalized in MIGRATED_PAGES and "Terminal" not in text:
        findings.append(Finding(
            rule="migrated-page-terminal-primitives",
            path=normalized,
            line=1,
            message="Migrated pages must import and use terminal primitives.",
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
                "Migrated pages should use TerminalPanel/TerminalNestedBlock/TerminalButton/TerminalChip instead of page-local material classes.",
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


def scan_project() -> ScanResult:
    findings: list[Finding] = []
    for path in iter_files():
        findings.extend(scan_text(rel(path), path.read_text(encoding="utf-8")).findings)
    return ScanResult(findings=findings)


def main() -> int:
    result = scan_project()
    print("WolfyStock frontend design constitution guard")
    print(f"Files scanned: {len(iter_files())}")
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
