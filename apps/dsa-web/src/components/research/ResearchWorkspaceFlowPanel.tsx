import type React from 'react';
import { BarChart3, BookmarkCheck, BriefcaseBusiness, FileSearch, FlaskConical, Search } from 'lucide-react';
import { Link } from 'react-router-dom';
import { translate, type UiLanguage } from '../../i18n/core';
import { cn } from '../../utils/cn';
import {
  buildResearchWorkspacePath,
  getResearchWorkspaceRoute,
  normalizeResearchWorkspaceMarket,
  normalizeResearchWorkspaceSource,
  normalizeResearchWorkspaceSymbol,
  type ResearchWorkspaceRouteContext,
  type ResearchWorkspaceSource,
  type ResearchWorkspaceSurface,
} from '../../utils/researchWorkspaceRoute';
import { sanitizeUserFacingDataIssue } from '../../utils/userFacingDataIssues';
import { TerminalChip } from '../terminal/TerminalPrimitives';

type ResearchWorkspaceFlowPanelProps = {
  language: UiLanguage;
  current: ResearchWorkspaceSurface;
  symbol?: string | null;
  market?: string | null;
  source?: ResearchWorkspaceSource | null;
  title?: string;
  summary?: string;
  knownEvidence?: Array<string | null | undefined>;
  missingEvidence?: Array<string | null | undefined>;
  stateNotes?: Array<string | null | undefined>;
  nextSteps?: Array<string | null | undefined>;
  className?: string;
  testId?: string;
};

const WORKFLOW_STEPS: Array<{
  key: ResearchWorkspaceSurface;
  icon: React.ComponentType<{ className?: string; 'aria-hidden'?: boolean }>;
}> = [
  { key: 'scanner', icon: Search },
  { key: 'stock-structure', icon: FileSearch },
  { key: 'watchlist', icon: BookmarkCheck },
  { key: 'portfolio', icon: BriefcaseBusiness },
  { key: 'backtest', icon: BarChart3 },
  { key: 'options', icon: FlaskConical },
];

const SAFE_COPY = {
  zh: {
    title: '研究工作流',
    summary: '只读研究上下文',
    known: '已知证据',
    missing: '待补证据',
    state: '证据状态',
    next: '下一步核验',
    noKnown: '当前页面尚未形成可展示证据。',
    noMissing: '未识别到必须补充的证据。',
    noState: '未标记特殊数据状态。',
    noNext: '继续在当前工作台观察。',
    open: '打开',
    current: '当前',
    latestAvailable: '已使用最近一次可用数据，需复核时间。',
    localSample: '本地验证样例，仅用于界面验证。',
    limitedConfidence: '当前置信度受限，仅供观察。',
    hidden: '技术细节已隐藏，仅展示消费者可用证据。',
  },
  en: {
    title: 'Research workflow',
    summary: 'Read-only research context',
    known: 'Known evidence',
    missing: 'Missing evidence',
    state: 'Evidence state',
    next: 'Next verification',
    noKnown: 'No displayable evidence is available on this page yet.',
    noMissing: 'No required evidence gap has been identified.',
    noState: 'No special data state is marked.',
    noNext: 'Continue observing in the current workspace.',
    open: 'Open',
    current: 'Current',
    latestAvailable: 'Using latest available data; verify the timestamp.',
    localSample: 'Local validation sample for interface verification only.',
    limitedConfidence: 'Confidence is capped; observation only.',
    hidden: 'Technical details are hidden; consumer evidence only.',
  },
} as const;

const INTERNAL_PATTERN = /sourceauthority|scorecontribution|reasoncode|\bprovider\b|\bcache\b|\bfallback\b|\braw\b|\bdebug\b|\bjson\b|\bruntime\b|\bdiagnostic\b|\bschema\b|\btrace\b/i;
const RAW_CONSUMER_COPY_PATTERN = /universe\s*\/\s*historical\s+ohlcv\s*\/\s*quote\s+snapshot|clean research handoff|evidence famil(?:y|ies)|business-quality review|peer group metadata|daily ohlcv|observation-only research readiness|personalized financial advice/i;
const STALE_PATTERN = /stale|expired|older|过期|陈旧|较旧/i;
const SAMPLE_PATTERN = /fixture|mock|synthetic|sample|样例|演示/i;
const CONFIDENCE_PATTERN = /confidence|置信|cap|limited/i;

function normalizeEvidenceLine(value: string | null | undefined, language: UiLanguage): string | null {
  const text = String(value || '').trim();
  if (!text) return null;
  const copy = SAFE_COPY[language === 'en' ? 'en' : 'zh'];
  if (RAW_CONSUMER_COPY_PATTERN.test(text)) {
    return sanitizeUserFacingDataIssue(text, language === 'en' ? 'en' : 'zh');
  }
  if (SAMPLE_PATTERN.test(text)) return copy.localSample;
  if (STALE_PATTERN.test(text) || /\bfallback\b|\bcache\b/i.test(text)) return copy.latestAvailable;
  if (CONFIDENCE_PATTERN.test(text)) return copy.limitedConfidence;
  if (INTERNAL_PATTERN.test(text)) return copy.hidden;
  return text;
}

function safeEvidenceLines(
  values: Array<string | null | undefined> | undefined,
  fallback: string,
  language: UiLanguage,
): string[] {
  const seen = new Set<string>();
  const lines: string[] = [];
  for (const value of values || []) {
    const line = normalizeEvidenceLine(value, language);
    if (!line || seen.has(line)) continue;
    seen.add(line);
    lines.push(line);
    if (lines.length >= 4) break;
  }
  return lines.length ? lines : [fallback];
}

const chipVariantForSurface: Record<ResearchWorkspaceSurface, React.ComponentProps<typeof TerminalChip>['variant']> = {
  scanner: 'info',
  'stock-structure': 'info',
  watchlist: 'success',
  portfolio: 'neutral',
  backtest: 'caution',
  options: 'info',
};

export default function ResearchWorkspaceFlowPanel({
  language,
  current,
  symbol,
  market,
  source,
  title,
  summary,
  knownEvidence,
  missingEvidence,
  stateNotes,
  nextSteps,
  className,
  testId = 'research-workspace-flow',
}: ResearchWorkspaceFlowPanelProps) {
  const ui = SAFE_COPY[language === 'en' ? 'en' : 'zh'];
  const normalizedSymbol = normalizeResearchWorkspaceSymbol(symbol);
  const normalizedMarket = normalizeResearchWorkspaceMarket(market);
  const normalizedSource = normalizeResearchWorkspaceSource(source) || current;
  const routeContext: ResearchWorkspaceRouteContext = {
    symbol: normalizedSymbol,
    market: normalizedMarket,
    source: normalizedSource,
  };
  const knownLines = safeEvidenceLines(knownEvidence, ui.noKnown, language);
  const missingLines = safeEvidenceLines(missingEvidence, ui.noMissing, language);
  const stateLines = safeEvidenceLines(stateNotes, ui.noState, language);
  const nextLines = safeEvidenceLines(nextSteps, ui.noNext, language);

  return (
    <section
      data-testid={testId}
      aria-label={title || ui.title}
      className={cn(
        'min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-console)_92%,transparent)] px-4 py-4 text-sm text-[color:var(--wolfy-text-secondary)]',
        className,
      )}
    >
      <div className="flex min-w-0 flex-col gap-3">
        <div className="flex min-w-0 flex-col gap-2 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <h2 className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{title || ui.title}</h2>
              {normalizedSymbol ? <TerminalChip variant="neutral" className="font-mono">{normalizedSymbol}</TerminalChip> : null}
              {normalizedMarket ? <TerminalChip variant="neutral">{normalizedMarket}</TerminalChip> : null}
              <TerminalChip variant={chipVariantForSurface[current]}>{ui.current}</TerminalChip>
            </div>
            <p className="mt-1 max-w-4xl text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{summary || ui.summary}</p>
          </div>
          <nav
            aria-label={language === 'en' ? 'Research workspace routes' : '研究工作流路由'}
            className="flex min-w-0 flex-wrap gap-1.5"
          >
            {WORKFLOW_STEPS.map((step) => {
              const Icon = step.icon;
              const isCurrent = step.key === current;
              const label = translate(language, getResearchWorkspaceRoute(step.key).labelKey);
              return (
                <Link
                  key={step.key}
                  to={buildResearchWorkspacePath(step.key, language, routeContext)}
                  aria-current={isCurrent ? 'step' : undefined}
                  className={cn(
                    'inline-flex h-8 max-w-full items-center gap-1.5 rounded-md border px-2.5 text-xs transition-colors',
                    isCurrent
                      ? 'border-[color:var(--wolfy-accent)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_14%,transparent)] text-[color:var(--wolfy-text-primary)]'
                      : 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-secondary)] hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)]',
                  )}
                  data-testid={`research-workspace-link-${step.key}`}
                >
                  <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
                  <span className="truncate">{isCurrent ? label : `${ui.open} ${label}`}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="grid min-w-0 gap-2 md:grid-cols-2 xl:grid-cols-4">
          {[
            [ui.known, knownLines, 'research-workspace-known'],
            [ui.missing, missingLines, 'research-workspace-missing'],
            [ui.state, stateLines, 'research-workspace-state'],
            [ui.next, nextLines, 'research-workspace-next'],
          ].map(([label, lines, id]) => (
            <div key={String(id)} data-testid={String(id)} className="min-w-0 rounded-md border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-3 py-2">
              <p className="text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">{label as string}</p>
              <ul className="mt-1 space-y-1 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                {(lines as string[]).map((line) => (
                  <li key={line} className="break-words">{line}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
