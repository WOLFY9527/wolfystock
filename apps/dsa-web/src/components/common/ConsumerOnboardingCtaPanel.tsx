import type React from 'react';
import { ArrowRight } from 'lucide-react';
import { buildLocalizedPath } from '../../utils/localeRouting';
import { cn } from '../../utils/cn';
import { sanitizeUserFacingDataIssue } from '../../utils/userFacingDataIssues';
import { TerminalChip } from '../terminal/TerminalPrimitives';

type ConsumerOnboardingGuidance = {
  title?: string | null;
  summary?: string | null;
  conditionsDetected?: string[];
} | null;

type ConsumerOnboardingAction = {
  label?: string | null;
  route?: string | null;
  description?: string | null;
};

type ConsumerOnboardingEntrypoint = {
  surface?: string | null;
  route?: string | null;
  description?: string | null;
};

type ConsumerOnboardingCtaPanelProps = {
  language: 'zh' | 'en';
  title: string;
  guidance?: ConsumerOnboardingGuidance;
  actions?: ConsumerOnboardingAction[];
  starterResearchWorkflow?: string[];
  firstRunChecklist?: string[];
  suggestedResearchEntrypoints?: ConsumerOnboardingEntrypoint[];
  radarLabel?: string;
  portfolioLabel?: string;
  children?: React.ReactNode;
  className?: string;
  'data-testid'?: string;
};

const CANONICAL_ROUTES = new Set([
  '/market-overview',
  '/scanner',
  '/watchlist',
  '/research/radar',
  '/portfolio',
]);

function normalizeRoute(route?: string | null): string | null {
  const normalized = String(route || '').trim();
  if (!normalized || !normalized.startsWith('/')) {
    return null;
  }
  return CANONICAL_ROUTES.has(normalized) ? normalized : null;
}

function localizedActionLabel(
  route: string,
  language: 'zh' | 'en',
  options: Pick<ConsumerOnboardingCtaPanelProps, 'radarLabel' | 'portfolioLabel'>,
): string {
  if (language === 'en') {
    if (route === '/market-overview') return 'Start with Market Overview';
    if (route === '/scanner') return 'Run Scanner';
    if (route === '/watchlist') return 'Add Watchlist Symbol';
    if (route === '/research/radar') return options.radarLabel || 'Review Research Radar';
    if (route === '/portfolio') return options.portfolioLabel || 'Create portfolio account';
  }
  if (route === '/market-overview') return '先看市场概览';
  if (route === '/scanner') return '运行 Scanner';
  if (route === '/watchlist') return '选择观察标的';
  if (route === '/research/radar') return options.radarLabel || '查看研究雷达';
  if (route === '/portfolio') return options.portfolioLabel || '创建组合账户';
  return route;
}

function fallbackActionDescription(route: string, language: 'zh' | 'en'): string {
  if (language === 'en') {
    if (route === '/market-overview') return 'Read broad market context before choosing symbols.';
    if (route === '/scanner') return 'Run a user-triggered scan to create candidates.';
    if (route === '/watchlist') return 'Choose a symbol only when you want to keep observing it.';
    if (route === '/research/radar') return 'Review the queue after scanner or watchlist activity.';
    if (route === '/portfolio') return 'Create an account only when you want portfolio tracking.';
  }
  if (route === '/market-overview') return '先阅读市场背景，再决定是否继续进入标的研究。';
  if (route === '/scanner') return '由你手动运行扫描，形成可复核候选。';
  if (route === '/watchlist') return '只在你想持续观察某个代码时再保存。';
  if (route === '/research/radar') return '在扫描或观察列表有活动后，再回来看研究队列。';
  if (route === '/portfolio') return '只有你明确想跟踪组合时才创建账户。';
  return '';
}

function hasRawConsumerLeakage(value: string): boolean {
  return /source_?refs?|reason_?codes?|fundamentals?(?:[._\s-]|$)|\bnews\b|fallback[_\s-]?(?:used|static|diagnostics?)|provider[_\s-]?(?:timeout|runtime|diagnostics?|payload|route)|\b(?:raw|debug|schema|trace|cache)\b/i.test(value)
    || /\b[a-z]+(?:_[a-z0-9]+)+\b/i.test(value);
}

function safeText(value: string | null | undefined, language: 'zh' | 'en'): string | null {
  const trimmed = String(value || '').trim();
  if (!trimmed) return null;
  return hasRawConsumerLeakage(trimmed)
    ? sanitizeUserFacingDataIssue(trimmed, language)
    : trimmed;
}

function safeList(values: string[] | undefined, language: 'zh' | 'en'): string[] {
  return Array.isArray(values)
    ? values.map((value) => safeText(value, language)).filter((value): value is string => Boolean(value))
    : [];
}

function buildActions(
  actions: ConsumerOnboardingAction[] | undefined,
  entrypoints: ConsumerOnboardingEntrypoint[] | undefined,
): Array<{ route: string; description?: string | null }> {
  const seen = new Set<string>();
  const candidates = [
    ...(actions ?? []).map((item) => ({ route: item.route, description: item.description })),
    ...(entrypoints ?? []).map((item) => ({ route: item.route, description: item.description })),
  ];
  const result: Array<{ route: string; description?: string | null }> = [];
  for (const item of candidates) {
    const route = normalizeRoute(item.route);
    if (!route || seen.has(route)) continue;
    seen.add(route);
    result.push({ route, description: item.description });
  }
  return result;
}

export function ConsumerOnboardingCtaPanel({
  language,
  title,
  guidance,
  actions,
  starterResearchWorkflow,
  firstRunChecklist,
  suggestedResearchEntrypoints,
  radarLabel,
  portfolioLabel,
  children,
  className,
  'data-testid': dataTestId,
}: ConsumerOnboardingCtaPanelProps) {
  const ctaActions = buildActions(actions, suggestedResearchEntrypoints);
  const workflow = safeList(starterResearchWorkflow, language);
  const checklist = safeList(firstRunChecklist, language);
  const conditions = safeList(guidance?.conditionsDetected, language);
  const summary = safeText(guidance?.summary, language);
  const actionLabels = new Map(
    ctaActions.map((action) => [
      action.route,
      localizedActionLabel(action.route, language, { radarLabel, portfolioLabel }),
    ]),
  );

  if (!ctaActions.length && !workflow.length && !checklist.length && !summary && !children) {
    return null;
  }

  return (
    <section
      data-testid={dataTestId}
      className={cn(
        'min-w-0 rounded-xl border border-[color:color-mix(in_srgb,var(--wolfy-accent)_28%,transparent)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_7%,transparent)] p-3 text-left',
        className,
      )}
    >
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <TerminalChip variant="info">{language === 'en' ? 'First-run workflow' : '首次研究路径'}</TerminalChip>
          <h3 className="mt-2 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{title}</h3>
          {summary ? <p className="mt-1 max-w-[72ch] text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">{summary}</p> : null}
        </div>
      </div>
      {children ? <div className="mt-3 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">{children}</div> : null}
      {ctaActions.length ? (
        <div className="mt-3 grid min-w-0 gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {ctaActions.map((action) => (
            <a
              key={action.route}
              href={buildLocalizedPath(action.route, language)}
              aria-label={actionLabels.get(action.route)}
              className="group flex min-h-[84px] min-w-0 flex-col justify-between rounded-lg border border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-2.5 text-left transition-colors hover:border-[color:var(--wolfy-accent)] hover:bg-[color:var(--surface-2)]"
            >
              <span className="flex min-w-0 items-center justify-between gap-2 text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                <span className="min-w-0 break-words">{actionLabels.get(action.route)}</span>
                <ArrowRight className="size-3.5 shrink-0 text-[color:var(--wolfy-text-muted)] transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
              </span>
              <span className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                {safeText(action.description, language) || fallbackActionDescription(action.route, language)}
              </span>
            </a>
          ))}
        </div>
      ) : null}
      {workflow.length || checklist.length || conditions.length ? (
        <div className="mt-3 grid min-w-0 gap-2 md:grid-cols-3">
          {workflow.length ? (
            <div className="min-w-0 rounded-lg border border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Starter flow' : '起步流程'}</p>
              <ul className="mt-2 space-y-1 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                {workflow.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          ) : null}
          {checklist.length ? (
            <div className="min-w-0 rounded-lg border border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Checklist' : '检查清单'}</p>
              <ul className="mt-2 space-y-1 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                {checklist.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          ) : null}
          {conditions.length ? (
            <div className="min-w-0 rounded-lg border border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Detected state' : '当前状态'}</p>
              <ul className="mt-2 space-y-1 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                {conditions.slice(0, 4).map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
