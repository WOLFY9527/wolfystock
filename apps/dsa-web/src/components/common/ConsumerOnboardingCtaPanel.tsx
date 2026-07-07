import type React from 'react';
import { ArrowRight } from 'lucide-react';
import { buildLocalizedPath } from '../../utils/localeRouting';
import { cn } from '../../utils/cn';
import { sanitizeUserFacingDataIssue } from '../../utils/userFacingDataIssues';
import {
  resolveCoreProductRouteByCanonicalPath,
  type CoreProductRoute,
} from '../layout/coreProductRoutes';
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
  children?: React.ReactNode;
  className?: string;
  'data-testid'?: string;
};

type ConsumerCtaRoute = CoreProductRoute & {
  ctaLabel: NonNullable<CoreProductRoute['ctaLabel']>;
  ctaDescription: NonNullable<CoreProductRoute['ctaDescription']>;
};

function normalizeRoute(route?: string | null): ConsumerCtaRoute | null {
  const normalized = String(route || '').trim();
  if (!normalized || !normalized.startsWith('/')) {
    return null;
  }
  const routeMetadata = resolveCoreProductRouteByCanonicalPath(normalized);
  if (!routeMetadata?.ctaLabel || !routeMetadata.ctaDescription) {
    return null;
  }
  return routeMetadata as ConsumerCtaRoute;
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
): Array<{ route: ConsumerCtaRoute; description?: string | null }> {
  const seen = new Set<string>();
  const candidates = [
    ...(actions ?? []).map((item) => ({ route: item.route, description: item.description })),
    ...(entrypoints ?? []).map((item) => ({ route: item.route, description: item.description })),
  ];
  const result: Array<{ route: ConsumerCtaRoute; description?: string | null }> = [];
  for (const item of candidates) {
    const route = normalizeRoute(item.route);
    if (!route || seen.has(route.path)) continue;
    seen.add(route.path);
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
  children,
  className,
  'data-testid': dataTestId,
}: ConsumerOnboardingCtaPanelProps) {
  const ctaActions = buildActions(actions, suggestedResearchEntrypoints);
  const workflow = safeList(starterResearchWorkflow, language);
  const checklist = safeList(firstRunChecklist, language);
  const conditions = safeList(guidance?.conditionsDetected, language);
  const summary = safeText(guidance?.summary, language);

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
              key={action.route.path}
              href={buildLocalizedPath(action.route.path, language)}
              aria-label={action.route.ctaLabel[language]}
              className="group flex min-h-[84px] min-w-0 flex-col justify-between rounded-lg border border-[color:var(--line)] bg-[color:var(--surface)] px-3 py-2.5 text-left transition-colors hover:border-[color:var(--wolfy-accent)] hover:bg-[color:var(--surface-2)]"
            >
              <span className="flex min-w-0 items-center justify-between gap-2 text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                <span className="min-w-0 break-words">{action.route.ctaLabel[language]}</span>
                <ArrowRight className="size-3.5 shrink-0 text-[color:var(--wolfy-text-muted)] transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
              </span>
              <span className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                {safeText(action.description, language) || action.route.ctaDescription[language]}
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
