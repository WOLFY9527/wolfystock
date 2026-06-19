import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import ConsumerDataHealthSummaryPanel from '../components/common/ConsumerDataHealthSummaryPanel';
import { ConsumerOnboardingCtaPanel } from '../components/common/ConsumerOnboardingCtaPanel';
import { ConsumerResearchEmptyState } from '../components/common/ConsumerResearchEmptyState';
import { buildConsumerResearchEmptyState } from '../components/common/researchEmptyStateModel';
import { EvidenceGapExplanationList } from '../components/research/EvidenceGapExplanation';
import {
  ConsoleBoard,
  ConsoleContextRail,
  ConsoleStatusStrip,
  MetricStrip,
  ResearchConsoleShell,
  WolfyCommandBar,
} from '../components/linear/LinearPrimitives';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import { StatusBadge } from '../components/ui/StatusBadge';
import { TerminalButton, TerminalChip } from '../components/terminal/TerminalPrimitives';
import { createParsedApiError, getParsedApiError, type ParsedApiError } from '../api/error';
import {
  researchRadarApi,
  type ResearchRadarOnboardingGuidance,
  type ResearchRadarResponse,
  type UnifiedResearchQueueItem,
  type UnifiedResearchQueueResponse,
} from '../api/researchRadar';
import { useI18n } from '../contexts/UiLanguageContext';
import { getConsumerStatusLabel, mapConsumerStatusText } from '../utils/consumerStatusLabels';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';
import { formatDateTime } from '../utils/format';
import { createConsumerDataHealthSummary } from '../utils/consumerDataQualityViewModel';
import { sanitizeUserFacingDataIssue } from '../utils/userFacingDataIssues';
import {
  RoughBulletList,
  RoughKeyValueRows,
  RoughScoreRows,
  RoughSectionCard,
  RoughSurfaceIntro,
} from './roughShellShared';

const DRIVER_LABELS = {
  relativeStrength: { zh: '相对强弱', en: 'Relative strength' },
  themeAlignment: { zh: '主题匹配', en: 'Theme alignment' },
  regimeFit: { zh: '市场匹配', en: 'Regime fit' },
  volumeSupport: { zh: '量能支持', en: 'Volume support' },
  structureQuality: { zh: '结构质量', en: 'Structure quality' },
  eventReadiness: { zh: '事件就绪度', en: 'Event readiness' },
  evidenceQuality: { zh: '证据质量', en: 'Evidence quality' },
} as const;

function toneFor(value: string | null | undefined): string {
  const normalized = String(value || '').toLowerCase();
  if (['high', 'ready', 'strong', 'supportive', 'complete'].includes(normalized)) return 'success';
  if (['medium', 'mixed', 'partial', 'neutral'].includes(normalized)) return 'warning';
  if (['low', 'degraded', 'unavailable', 'thin'].includes(normalized)) return 'error';
  return 'info';
}

function driverLabel(key: string, language: 'zh' | 'en') {
  const mapped = DRIVER_LABELS[key as keyof typeof DRIVER_LABELS];
  if (mapped) {
    return mapped[language];
  }
  return key.replace(/([a-z])([A-Z])/g, '$1 $2');
}

const RESEARCH_QUEUE_SOURCE_ORDER: UnifiedResearchQueueItem['sourceSurface'][] = ['watchlist', 'scanner', 'market', 'manual_gap'];
const ADVICE_OR_TRADE_WORDS = /建议(买入|卖出|加仓|减仓|持有)|买入|卖出|下单|交易建议|投资建议|止损|止盈|目标价|仓位建议|\b(buy|sell|hold|recommend(?:ation)?|target price|stop loss|position sizing|trade advice|investment advice)\b/i;
const INTERNAL_DIAGNOSTIC_WORDS = /sourceRefs?|reasonCodes?|sourceRefId|request[_\s-]?id|trace[_\s-]?id|correlation[_\s-]?id|queueItemId|provider|cache|runtime|debug|raw|json|schemaVersion|admin|diagnostic|payload|backend snake_case|\b[a-z]+(?:_[a-z0-9]+)+\b/i;

function safeResearchQueueText(value: string | null | undefined, locale: 'zh' | 'en', fallback?: string): string | null {
  const raw = String(value || '').trim();
  if (!raw) return fallback ?? null;
  const mapped = mapConsumerStatusText(raw, locale);
  if (mapped !== raw) {
    return mapped;
  }
  if (ADVICE_OR_TRADE_WORDS.test(raw)) {
    return locale === 'en' ? 'Observation detail withheld.' : '观察细节已折叠。';
  }
  if (INTERNAL_DIAGNOSTIC_WORDS.test(raw)) {
    return sanitizeUserFacingDataIssue(raw, locale);
  }
  return raw;
}

function safeResearchQueueList(values: string[] | null | undefined, locale: 'zh' | 'en', fallback: string): string[] {
  const seen = new Set<string>();
  const next: string[] = [];
  for (const value of values ?? []) {
    const safe = safeResearchQueueText(value, locale);
    if (!safe || seen.has(safe)) continue;
    seen.add(safe);
    next.push(safe);
  }
  return next.length ? next : [fallback];
}

function sourceSurfaceLabel(surface: UnifiedResearchQueueItem['sourceSurface'], locale: 'zh' | 'en'): string {
  const labels: Record<UnifiedResearchQueueItem['sourceSurface'], Record<'zh' | 'en', string>> = {
    watchlist: { zh: 'Watchlist', en: 'Watchlist' },
    scanner: { zh: 'Scanner', en: 'Scanner' },
    market: { zh: 'Market', en: 'Market' },
    manual_gap: { zh: '证据补缺', en: 'Evidence follow-up' },
  };
  return labels[surface]?.[locale] || (locale === 'en' ? 'Research' : '研究');
}

function priorityTierLabel(priorityTier: UnifiedResearchQueueItem['priorityTier'], locale: 'zh' | 'en'): string {
  if (locale === 'en') {
    if (priorityTier === 'urgent_review') return 'Urgent review';
    if (priorityTier === 'follow_up') return 'Follow up';
    return 'Monitor';
  }
  if (priorityTier === 'urgent_review') return '紧急复核';
  if (priorityTier === 'follow_up') return '持续跟进';
  return '观察';
}

function priorityTierTone(priorityTier: UnifiedResearchQueueItem['priorityTier']): string {
  if (priorityTier === 'urgent_review') return 'warning';
  if (priorityTier === 'follow_up') return 'info';
  return 'unknown';
}

function consumerStatusValue(value: string | null | undefined, locale: 'zh' | 'en'): string {
  const mapped = getConsumerStatusLabel(value, locale) || mapConsumerStatusText(value, locale);
  return mapped || '--';
}

function freshnessLabel(state: UnifiedResearchQueueItem['freshness']['state'], locale: 'zh' | 'en'): string {
  if (locale === 'en') {
    if (state === 'current') return 'Current';
    if (state === 'needs_review') return 'Needs review';
    if (state === 'unavailable') return 'Unavailable';
    return 'Unconfirmed';
  }
  if (state === 'current') return '当前可用';
  if (state === 'needs_review') return '需复核';
  if (state === 'unavailable') return '暂不可用';
  return '未确认';
}

function freshnessTone(state: UnifiedResearchQueueItem['freshness']['state']): string {
  if (state === 'current') return 'success';
  if (state === 'needs_review') return 'warning';
  if (state === 'unavailable') return 'error';
  return 'unknown';
}

function isUnifiedResearchQueueDisplaySafe(data: UnifiedResearchQueueResponse | null): data is UnifiedResearchQueueResponse {
  return Boolean(
    data
    && data.schemaVersion === 'research_queue_v1'
    && data.observationOnly === true
    && data.decisionGrade === false
    && data.dataQuality?.failClosed === true
    && data.researchQueue.every((item) => item.observationOnly === true),
  );
}

function dataHealthQualityFromStatus(value: string | null | undefined) {
  const normalized = String(value || '').trim().toLowerCase();
  if (['ready', 'available', 'healthy', 'current', 'complete'].includes(normalized)) {
    return { status: 'ready', freshness: 'fresh' };
  }
  if (['partial', 'mixed', 'thin'].includes(normalized)) {
    return { status: 'partial', isPartial: true };
  }
  if (['stale', 'needs_review', 'delayed'].includes(normalized)) {
    return { status: 'stale', freshness: 'stale', isStale: true };
  }
  if (['unavailable', 'missing', 'blocked', 'no_evidence', 'empty', 'error'].includes(normalized)) {
    return { status: 'missing', isUnavailable: true };
  }
  return { status: 'degraded' };
}

function buildResearchRadarDataHealthSummary({
  data,
  unifiedQueue,
  locale,
}: {
  data: ResearchRadarResponse | null;
  unifiedQueue: UnifiedResearchQueueResponse | null;
  locale: 'zh' | 'en';
}) {
  const queueFreshnessStates = unifiedQueue?.researchQueue.map((item) => item.freshness.state) ?? [];
  const queueFreshnessQuality = !unifiedQueue
    ? { status: 'missing', isUnavailable: true }
    : queueFreshnessStates.includes('unavailable')
      ? { status: 'missing', isUnavailable: true }
      : queueFreshnessStates.some((state) => state === 'needs_review' || state === 'unknown') || (unifiedQueue.evidenceGaps.length > 0)
        ? { status: 'stale', freshness: 'stale', isStale: true }
        : { status: 'ready', freshness: 'fresh' };
  const stockEvidenceQuality = (unifiedQueue?.evidenceGaps.length ?? data?.evidenceGaps.length ?? 0) > 0
    ? { status: 'partial', isPartial: true }
    : dataHealthQualityFromStatus(data?.aggregateSummary.queueQuality || unifiedQueue?.dataQuality.state || data?.dataQuality?.status);

  return createConsumerDataHealthSummary({
    locale,
    categories: [
      {
        category: 'marketBreadth',
        quality: dataHealthQualityFromStatus(data?.dataQuality?.status),
      },
      {
        category: 'stockEvidence',
        quality: stockEvidenceQuality,
      },
      {
        category: 'researchQueueFreshness',
        quality: queueFreshnessQuality,
      },
    ],
  });
}

function safeResearchRoute(route: string | null | undefined): string | null {
  const trimmed = String(route || '').trim();
  if (!trimmed || !trimmed.startsWith('/') || trimmed.startsWith('/api/')) return null;
  if (trimmed.includes('://') || trimmed.includes('..') || /[?#]/.test(trimmed)) return null;
  const allowedConsumerRoutes = [
    /^\/research\/radar$/,
    /^\/scanner$/,
    /^\/watchlist$/,
    /^\/portfolio$/,
    /^\/market-overview$/,
    /^\/market\/decision-cockpit$/,
    /^\/scenario-lab$/,
    /^\/market\/scenario-lab$/,
    /^\/stocks\/[^/?#]+\/structure-decision$/,
  ];
  if (!allowedConsumerRoutes.some((pattern) => pattern.test(trimmed))) return null;
  return trimmed;
}

function groupResearchQueue(items: UnifiedResearchQueueItem[]) {
  const groups = new Map<UnifiedResearchQueueItem['sourceSurface'], UnifiedResearchQueueItem[]>();
  for (const surface of RESEARCH_QUEUE_SOURCE_ORDER) groups.set(surface, []);
  for (const item of items) {
    const current = groups.get(item.sourceSurface) ?? [];
    current.push(item);
    groups.set(item.sourceSurface, current);
  }
  return RESEARCH_QUEUE_SOURCE_ORDER
    .map((surface) => ({ surface, items: groups.get(surface) ?? [] }))
    .filter((group) => group.items.length > 0);
}

function normalizeRadarGapKey(value: string | null | undefined): string {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .replace(/[:=./\\\s-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function buildResearchRadarMissingEvidenceLabels(
  gaps: string[],
  locale: 'zh' | 'en',
): string[] {
  const seen = new Set<string>();
  const labels: string[] = [];

  gaps.forEach((gap) => {
    const normalized = normalizeRadarGapKey(gap);
    let label: string | null = null;
    if (
      normalized.includes('fundamental')
      || normalized.includes('company')
      || normalized.includes('issuer')
      || normalized.includes('business_profile')
      || normalized.includes('financial_summary')
    ) {
      label = locale === 'en' ? 'company context' : '公司资料';
    } else if (normalized.includes('news') || normalized.includes('headline') || normalized.includes('media')) {
      label = locale === 'en' ? 'media context' : '媒体语境';
    } else if (normalized.includes('catalyst') || normalized.includes('event')) {
      label = locale === 'en' ? 'event context' : '事件语境';
    } else if (normalized.includes('freshness') || normalized.includes('recency') || normalized.includes('staleevidence') || normalized.includes('asof')) {
      label = locale === 'en' ? 'recency checks' : '时效复核';
    }
    if (!label || seen.has(label)) return;
    seen.add(label);
    labels.push(label);
  });

  return labels;
}

function buildResearchRadarDerivedGuidance({
  data,
  unifiedQueue,
  locale,
}: {
  data: ResearchRadarResponse | null;
  unifiedQueue: UnifiedResearchQueueResponse | null;
  locale: 'zh' | 'en';
}): ResearchRadarOnboardingGuidance | null {
  const safeSummary = safeResearchQueueText(data?.onboardingGuidance?.summary, locale);
  const conditions = safeResearchQueueList(
    data?.onboardingGuidance?.conditionsDetected,
    locale,
    locale === 'en' ? 'Research Radar remains observation-only for now.' : '当前研究雷达先保持观察边界。',
  );
  const availableSurfaces = new Set(unifiedQueue?.dataQuality?.sourceSurfacesAvailable ?? []);
  const expectedSurfaces = unifiedQueue?.dataQuality?.sourceSurfacesExpected ?? [];
  const missingEvidenceLabels = buildResearchRadarMissingEvidenceLabels([
    ...(data?.evidenceGaps ?? []),
    ...(unifiedQueue?.evidenceGaps ?? []),
  ], locale);
  const queueQuality = normalizeRadarGapKey(data?.aggregateSummary?.queueQuality || '');
  const lowEvidenceActive = queueQuality === 'low_evidence' || queueQuality === 'thin'
    || conditions.some((item) => normalizeRadarGapKey(item).includes('low_evidence'));

  expectedSurfaces.forEach((surface) => {
    if (surface === 'manual_gap' || availableSurfaces.has(surface)) return;
    if (surface === 'scanner') {
      conditions.push(locale === 'en' ? 'Scanner candidates have not been created yet.' : 'Scanner 候选尚未建立。');
    } else if (surface === 'watchlist') {
      conditions.push(locale === 'en' ? 'Watchlist context has not been added yet.' : '观察列表上下文尚未建立。');
    } else if (surface === 'market') {
      conditions.push(locale === 'en' ? 'Market context still needs review.' : '市场背景仍待补充。');
    }
  });

  if (lowEvidenceActive) {
    conditions.push(locale === 'en' ? 'Low-evidence filter is active.' : '当前按低证据条件整理。');
  }

  if (!safeSummary && !conditions.length && !data?.onboardingGuidance?.title) {
    return null;
  }

  const dedupedConditions = Array.from(new Set(conditions));
  const derivedSummary = safeSummary
    || (
      lowEvidenceActive && missingEvidenceLabels.length
        ? (locale === 'en'
          ? `This queue remains observation-only while ${missingEvidenceLabels.join(', ')} still need review.`
          : `当前队列仍缺少${missingEvidenceLabels.join('、')}，因此先保持观察边界。`)
        : (expectedSurfaces.some((surface) => surface !== 'manual_gap' && !availableSurfaces.has(surface))
          ? (locale === 'en'
            ? 'Upstream research prerequisites are still incomplete, so this queue remains observation-only.'
            : '上游研究前置条件仍未补齐，因此当前队列先保持观察边界。')
          : null)
    );

  return {
    title: data?.onboardingGuidance?.title ?? null,
    summary: derivedSummary,
    conditionsDetected: dedupedConditions,
  };
}

function ResearchQueueHubPanel({
  data,
  loading,
  unavailable,
  locale,
  localize,
}: {
  data: UnifiedResearchQueueResponse | null;
  loading: boolean;
  unavailable: boolean;
  locale: 'zh' | 'en';
  localize: (path: string) => string;
}) {
  const items = data?.researchQueue ?? [];
  const emptyCase = loading ? 'loading' : unavailable ? 'unavailableData' : 'noQueueItems';
  const sourceGroups = groupResearchQueue(items);
  const countLabel = locale === 'en'
    ? `${data?.aggregateSummary.itemCount ?? items.length} queued`
    : `${data?.aggregateSummary.itemCount ?? items.length} 个待复核`;

  return (
    <RoughSectionCard
      data-testid="research-queue-hub"
      className="md:col-span-2"
      eyebrow={locale === 'en' ? 'Queue hub' : '队列中枢'}
      title={locale === 'en' ? 'Cross-surface research queue' : '跨页面研究队列'}
      action={<TerminalChip variant="neutral">{countLabel}</TerminalChip>}
    >
      <div className="space-y-3">
        <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
          {locale === 'en'
            ? 'Evidence-first follow-up across market, scanner, watchlist, and symbol research surfaces.'
            : '按证据优先级汇总市场、Scanner、Watchlist 与标的研究入口的后续复核事项。'}
        </p>

        {items.length === 0 ? (
          <ConsumerResearchEmptyState
            data-testid="research-queue-hub-empty-state"
            locale={locale}
            state={buildConsumerResearchEmptyState(emptyCase, locale)}
          />
        ) : (
          <div className="space-y-4">
            {sourceGroups.map((group) => (
              <section
                key={group.surface}
                data-testid={`research-queue-source-${group.surface.replaceAll('_', '-')}`}
                className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 p-3"
              >
                <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
                      {sourceSurfaceLabel(group.surface, locale)}
                    </h3>
                    <p className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">
                      {locale === 'en' ? 'Grouped by source surface.' : '按来源页面分组。'}
                    </p>
                  </div>
                  <TerminalChip variant="neutral" className="font-mono">{group.items.length}</TerminalChip>
                </div>

                <div className="mt-3 grid gap-3">
                  {group.items.map((item, index) => {
                    const safeTitle = safeResearchQueueText(item.title, locale, locale === 'en' ? 'Research item' : '研究条目');
                    const whyQueued = safeResearchQueueList(
                      item.whyQueued,
                      locale,
                      locale === 'en' ? 'Research follow-up is available.' : '可进行后续研究复核。',
                    );
                    const evidenceUsed = safeResearchQueueList(
                      item.evidenceUsed,
                      locale,
                      locale === 'en' ? 'Evidence summary available.' : '已整理可用证据。',
                    );
                    const reviewedAt = item.freshness.lastReviewedAt
                      ? formatDateTime(item.freshness.lastReviewedAt, { locale: locale === 'en' ? 'en-US' : 'zh-CN' })
                      : null;
                    return (
                      <article
                        key={`${item.symbol || group.surface}-${index}`}
                        data-testid={`research-queue-item-${item.symbol || index}`}
                        className="min-w-0 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3"
                      >
                        <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="font-mono text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{item.symbol || '--'}</div>
                            <p className="mt-1 text-sm leading-5 text-[color:var(--wolfy-text-secondary)]">{safeTitle}</p>
                          </div>
                          <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
                            <StatusBadge status={priorityTierTone(item.priorityTier)} label={priorityTierLabel(item.priorityTier, locale)} size="sm" />
                            <StatusBadge status={freshnessTone(item.freshness.state)} label={freshnessLabel(item.freshness.state, locale)} size="sm" />
                            {item.observationOnly ? (
                              <TerminalChip variant="neutral">
                                {locale === 'en' ? 'Research only' : '仅作观察'}
                              </TerminalChip>
                            ) : null}
                          </div>
                        </div>

                        <div className="mt-3 grid gap-3 lg:grid-cols-3">
                          <div>
                            <p className="mb-2 text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">
                              {locale === 'en' ? 'Why queued' : '入队原因'}
                            </p>
                            <RoughBulletList items={whyQueued} emptyText={locale === 'en' ? 'No reason available.' : '暂无原因。'} />
                          </div>
                          <div>
                            <p className="mb-2 text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">
                              {locale === 'en' ? 'Evidence used' : '已用证据'}
                            </p>
                            <RoughBulletList items={evidenceUsed} emptyText={locale === 'en' ? 'No evidence listed.' : '暂无证据。'} />
                          </div>
                          <div>
                            <p className="mb-2 text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">
                              {locale === 'en' ? 'Evidence gaps' : '证据缺口'}
                            </p>
                            <EvidenceGapExplanationList
                              gaps={item.evidenceGaps}
                              locale={locale}
                              title={locale === 'en' ? 'Gap explanation' : '缺口解释'}
                              emptyText={locale === 'en' ? 'No gap listed.' : '暂无缺口。'}
                            />
                          </div>
                        </div>

                        {reviewedAt ? (
                          <p className="mt-3 text-xs text-[color:var(--wolfy-text-muted)]">
                            {locale === 'en' ? 'Last reviewed ' : '上次复核 '}
                            <span className="font-mono text-[color:var(--wolfy-text-secondary)]">{reviewedAt}</span>
                          </p>
                        ) : null}

                        {item.suggestedResearchPath.length ? (
                          <div className="mt-3 space-y-2">
                            <p className="text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">
                              {locale === 'en' ? 'Suggested research path' : '后续研究路径'}
                            </p>
                            {item.suggestedResearchPath.map((path, pathIndex) => {
                              const safeLabel = safeResearchQueueText(path.label, locale, locale === 'en' ? 'Open research path' : '打开研究路径');
                              const safeReason = safeResearchQueueText(path.reason, locale);
                              const route = safeResearchRoute(path.route);
                              if (!route) return null;
                              const content = (
                                <>
                                  <span className="font-medium text-[color:var(--wolfy-text-primary)]">{safeLabel}</span>
                                  {safeReason ? <span className="ml-2 text-[color:var(--wolfy-text-muted)]">{safeReason}</span> : null}
                                </>
                              );
                              return (
                                <Link
                                  key={`${item.symbol}:path:${pathIndex}`}
                                  to={localize(route)}
                                  className="block rounded-md border border-[color:var(--wolfy-border-subtle)] bg-black/10 px-3 py-2 text-xs leading-5 transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                                >
                                  {content}
                                </Link>
                              );
                            })}
                          </div>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        )}

        {data?.noAdviceDisclosure ? (
          <p className="text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
            {safeResearchQueueText(data.noAdviceDisclosure, locale, locale === 'en' ? 'Research-only queue.' : '仅供研究队列观察。')}
          </p>
        ) : null}
      </div>
    </RoughSectionCard>
  );
}

export default function ResearchRadarPage() {
  const { language } = useI18n();
  const locale = language === 'en' ? 'en' : 'zh';
  const location = useLocation();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const [searchParams] = useSearchParams();
  const localize = useCallback((path: string) => (routeLocale ? buildLocalizedPath(path, routeLocale) : path), [routeLocale]);
  const [data, setData] = useState<ResearchRadarResponse | null>(null);
  const [unifiedQueue, setUnifiedQueue] = useState<UnifiedResearchQueueResponse | null>(null);
  const [unifiedQueueLoading, setUnifiedQueueLoading] = useState(true);
  const [unifiedQueueUnavailable, setUnifiedQueueUnavailable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);

  const market = searchParams.get('market') || undefined;
  const profile = searchParams.get('profile') || undefined;
  const limit = searchParams.get('limit');
  const parsedLimit = limit ? Number(limit) : undefined;

  const load = useCallback(async () => {
    setLoading(true);
    setUnifiedQueueLoading(true);
    setUnifiedQueueUnavailable(false);
    setError(null);
    try {
      const [response, queueResponse] = await Promise.all([
        researchRadarApi.getResearchRadar({
          market,
          profile,
          limit: Number.isFinite(parsedLimit) ? parsedLimit : undefined,
        }),
        researchRadarApi.getResearchQueue({
          market,
          profile,
          queueLimit: Number.isFinite(parsedLimit) ? parsedLimit : undefined,
        }).catch(() => null),
      ]);
      const safeQueueResponse = isUnifiedResearchQueueDisplaySafe(queueResponse) ? queueResponse : null;
      setData(response);
      setUnifiedQueue(safeQueueResponse);
      setUnifiedQueueUnavailable(!safeQueueResponse);
    } catch (err) {
      setError(getParsedApiError(err) || createParsedApiError({
        title: locale === 'en' ? 'Research radar unavailable' : '研究雷达暂不可用',
        message: locale === 'en' ? 'Please retry after the queue API responds again.' : '请在队列接口恢复后重试。',
      }));
      setUnifiedQueue(null);
      setUnifiedQueueUnavailable(true);
    } finally {
      setLoading(false);
      setUnifiedQueueLoading(false);
    }
  }, [locale, market, parsedLimit, profile]);

  useEffect(() => {
    void load();
  }, [load]);

  const queueItems = useMemo(() => data?.researchQueue ?? [], [data?.researchQueue]);
  const unifiedQueueSize = unifiedQueue?.aggregateSummary.itemCount ?? unifiedQueue?.researchQueue.length ?? queueItems.length;
  const showOnboardingCta = Boolean(data && (queueItems.length === 0 || data.emptyStateActions.length || data.starterResearchWorkflow.length));
  const dataHealthSummary = useMemo(
    () => buildResearchRadarDataHealthSummary({ data, unifiedQueue, locale }),
    [data, unifiedQueue, locale],
  );
  const onboardingGuidance = useMemo(
    () => buildResearchRadarDerivedGuidance({ data, unifiedQueue, locale }),
    [data, unifiedQueue, locale],
  );
  const firstItemScores = useMemo(
    () => Object.entries(queueItems[0]?.driverScores ?? {})
      .sort(([, left], [, right]) => (right ?? 0) - (left ?? 0))
      .map(([key, value]) => ({
        key,
        label: driverLabel(key, locale),
        value,
      })),
    [queueItems, locale],
  );

  return (
    <ConsumerWorkspaceScope className="flex min-h-0 flex-1">
      <ConsumerWorkspacePageShell className="flex min-h-0 flex-1 flex-col gap-4 md:gap-6">
        <ResearchConsoleShell
          className="flex-1"
          command={(
            <WolfyCommandBar
              leading={<span className="text-xs text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Research Queue / Radar' : '研究队列 / 雷达'}</span>}
              trailing={(
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    to={localize('/market/decision-cockpit')}
                    className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                  >
                    {locale === 'en' ? 'Market cockpit' : '市场驾驶舱'}
                  </Link>
                  <TerminalButton variant="compact" onClick={() => void load()}>
                    {locale === 'en' ? 'Refresh' : '刷新'}
                  </TerminalButton>
                </div>
              )}
            >
              <div className="text-xs text-[color:var(--wolfy-text-secondary)]">
                {locale === 'en' ? 'Core queue for priority, structure handoff, verification items, and evidence gaps.' : '用于优先级、结构交接、验证事项与证据缺口的核心研究队列。'}
              </div>
            </WolfyCommandBar>
          )}
          rail={(
            <ConsoleContextRail className="flex flex-col gap-3 p-3">
              <RoughSectionCard eyebrow={locale === 'en' ? 'Aggregate' : '汇总'} title={locale === 'en' ? 'Evidence gaps' : '证据缺口'}>
                <EvidenceGapExplanationList
                  gaps={data?.evidenceGaps ?? []}
                  locale={locale}
                  title={locale === 'en' ? 'Aggregate gap explanation' : '汇总缺口解释'}
                  emptyText={locale === 'en' ? 'No aggregate evidence gap.' : '暂无汇总证据缺口。'}
                />
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Queue state' : '队列状态'} title={locale === 'en' ? 'Priority counts' : '优先级计数'}>
                <RoughKeyValueRows
                  rows={Object.entries(data?.aggregateSummary.priorityCounts ?? {}).map(([key, value]) => ({
                    key,
                    label: priorityTierLabel(key as UnifiedResearchQueueItem['priorityTier'], locale),
                    value,
                  }))}
                />
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Disclosure' : '披露'} title={locale === 'en' ? 'Observation-only note' : '观察型说明'}>
                <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                  {data?.noAdviceDisclosure || (locale === 'en' ? 'Research queue only.' : '仅供研究队列观察。')}
                </p>
              </RoughSectionCard>
            </ConsoleContextRail>
          )}
        >
          <ConsoleBoard className="min-h-0" data-testid="research-radar-page">
            <RoughSurfaceIntro
              eyebrow={locale === 'en' ? 'Research radar' : '研究雷达'}
              title={locale === 'en' ? 'Research queue for market-structure follow-through' : '承接市场结构的研究队列'}
              description={locale === 'en'
                ? 'This route turns cockpit signals into reviewable ticker work, keeping queue order, why-on-radar rationale, verification items, and risk flags together.'
                : '这个路由把驾驶舱信号转成可复核的标的研究工作，把队列顺序、上榜原因、验证事项与风险标记放在一起。'}
            />
            {error ? (
              <div className="p-4 md:p-5">
                <ApiErrorAlert error={error} actionLabel={locale === 'en' ? 'Retry' : '重试'} onAction={() => void load()} />
              </div>
            ) : null}
            {loading && !data ? (
              <div className="p-4 md:p-5">
                <ConsumerResearchEmptyState
                  data-testid="research-radar-loading-empty-state"
                  locale={locale}
                  state={buildConsumerResearchEmptyState('loading', locale)}
                />
              </div>
            ) : null}
            {data ? (
              <>
                <ConsoleStatusStrip
                  items={[
                    {
                      label: locale === 'en' ? 'Updated' : '更新时间',
                      value: formatDateTime(data.generatedAt, { locale: locale === 'en' ? 'en-US' : 'zh-CN' }),
                    },
                    {
                      label: locale === 'en' ? 'Data quality' : '数据质量',
                      value: <StatusBadge status={toneFor(data.dataQuality?.status)} label={consumerStatusValue(data.dataQuality?.status, locale)} size="sm" />,
                    },
                    {
                      label: locale === 'en' ? 'Context fit' : '市场匹配',
                      value: consumerStatusValue(data.marketContextFit, locale),
                    },
                  ]}
                />
                <MetricStrip
                  items={[
                    {
                      key: 'queue-quality',
                      label: locale === 'en' ? 'Queue quality' : '队列质量',
                      value: consumerStatusValue(data.aggregateSummary.queueQuality, locale),
                    },
                    {
                      key: 'queue-size',
                      label: locale === 'en' ? 'Queue size' : '队列数量',
                      value: unifiedQueueSize,
                    },
                    {
                      key: 'market',
                      label: locale === 'en' ? 'Market filter' : '市场过滤',
                      value: market || '--',
                    },
                  ]}
                />
                <div className="p-3 pb-0">
                  <ConsumerDataHealthSummaryPanel
                    summary={dataHealthSummary}
                    title={locale === 'en' ? 'Data health' : '数据健康'}
                    testId="research-radar-data-health-summary"
                  />
                </div>
                <div className="grid gap-3 p-3 md:grid-cols-2">
                  {showOnboardingCta && data ? (
                    <ConsumerOnboardingCtaPanel
                      data-testid="research-radar-onboarding-cta"
                      language={locale}
                      title={locale === 'en' ? 'Start the loop before the radar queue fills' : '先完成研究循环，再回到雷达队列'}
                      guidance={onboardingGuidance}
                      actions={data.emptyStateActions}
                      starterResearchWorkflow={data.starterResearchWorkflow}
                      firstRunChecklist={data.firstRunChecklist}
                      suggestedResearchEntrypoints={data.suggestedResearchEntrypoints}
                      radarLabel={locale === 'en' ? 'Return to Research Radar' : '回到研究雷达'}
                      className="md:col-span-2"
                    />
                  ) : null}
                  <ResearchQueueHubPanel
                    data={unifiedQueue}
                    loading={unifiedQueueLoading}
                    unavailable={unifiedQueueUnavailable}
                    locale={locale}
                    localize={localize}
                  />
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Queue' : '队列'} title={locale === 'en' ? 'Research queue' : '研究队列'}>
                    {queueItems.length ? (
                      <div className="space-y-3">
                        {queueItems.map((item, index) => (
                          <div key={`${item.ticker || item.symbol || 'queue'}-${index}`} className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 p-3">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div className="min-w-0">
                                <div className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">{item.ticker || item.symbol || '--'}</div>
                                <div className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">
                                  {safeResearchQueueList(
                                    item.whyOnRadar,
                                    locale,
                                    locale === 'en' ? 'Observation queue item.' : '观察队列条目。',
                                  ).join(locale === 'en' ? '; ' : '；')}
                                </div>
                              </div>
                              <div className="flex flex-wrap items-center gap-2">
                                {item.priority ? <StatusBadge status={toneFor(item.priority)} label={consumerStatusValue(item.priority, locale)} size="sm" /> : null}
                                {item.researchBias ? <TerminalChip variant="info">{mapConsumerStatusText(item.researchBias, locale)}</TerminalChip> : null}
                              </div>
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {(item.riskFlags ?? []).length
                                ? (item.riskFlags ?? []).map((flag, riskIndex) => (
                                  <TerminalChip key={`${flag}-${riskIndex}`} variant="caution">{mapConsumerStatusText(flag, locale)}</TerminalChip>
                                ))
                                : <TerminalChip variant="success">{locale === 'en' ? 'No explicit risk flag' : '暂无明确风险标记'}</TerminalChip>}
                            </div>
                            <div className="mt-3 flex gap-2">
                              {item.ticker ? (
                                <Link
                                  to={localize(`/stocks/${encodeURIComponent(item.ticker)}/structure-decision`)}
                                  className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                                >
                                  {locale === 'en' ? 'Open structure panel' : '打开结构面板'}
                                </Link>
                              ) : null}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <ConsumerResearchEmptyState
                        data-testid="research-radar-queue-empty-state"
                        locale={locale}
                        state={buildConsumerResearchEmptyState('noQueueItems', locale)}
                      />
                    )}
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Lead item' : '队首条目'} title={locale === 'en' ? 'Driver scores' : '驱动评分'}>
                    <RoughScoreRows
                      items={firstItemScores}
                      emptyText={locale === 'en' ? 'No lead item yet.' : '暂无线索条目。'}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Lead item' : '队首条目'} title={locale === 'en' ? 'What to verify' : '待验证事项'}>
                    <RoughBulletList
                      items={safeResearchQueueList(queueItems[0]?.whatToVerify, locale, locale === 'en' ? 'No verify item yet.' : '暂未整理验证事项。')}
                      emptyText={locale === 'en' ? 'No verify item yet.' : '暂未整理验证事项。'}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Lead item' : '队首条目'} title={locale === 'en' ? 'Invalidation observations' : '失效观察'}>
                    <RoughBulletList
                      items={safeResearchQueueList(queueItems[0]?.invalidationObservations, locale, locale === 'en' ? 'No invalidation observation yet.' : '暂未整理失效观察。')}
                      emptyText={locale === 'en' ? 'No invalidation observation yet.' : '暂未整理失效观察。'}
                    />
                  </RoughSectionCard>
                </div>
              </>
            ) : null}
          </ConsoleBoard>
        </ResearchConsoleShell>
      </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
}
