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
  ResearchConsoleShell,
  WolfyCommandBar,
} from '../components/linear/LinearPrimitives';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import { StatusBadge } from '../components/ui/StatusBadge';
import { TerminalButton, TerminalChip } from '../components/terminal/TerminalPrimitives';
import { createParsedApiError, getParsedApiError, type ParsedApiError } from '../api/error';
import {
  researchRadarApi,
  type ResearchRadarEvidenceHubItem,
  type ResearchRadarItem,
  type ResearchRadarMarketLevelFallback,
  type ResearchRadarOnboardingGuidance,
  type ResearchRadarResponse,
  type UnifiedResearchQueueItem,
  type UnifiedResearchQueueResponse,
} from '../api/researchRadar';
import { useI18n } from '../contexts/UiLanguageContext';
import { getConsumerStatusLabel, mapConsumerStatusText } from '../utils/consumerStatusLabels';
import {
  consumerPresentationList,
  consumerPresentationText,
} from '../utils/consumerPresentationBoundary';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';
import { formatDateTime } from '../utils/format';
import { createConsumerDataHealthSummary } from '../utils/consumerDataQualityViewModel';
import { buildResearchWorkspacePath } from '../utils/researchWorkspaceRoute';
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
const INTERNAL_DIAGNOSTIC_WORDS = /sourceRefs?|reasonCodes?|sourceRefId|request[_\s-]?id|trace[_\s-]?id|correlation[_\s-]?id|queueItemId|provider|cache|runtime|debug|raw|json|schemaVersion|admin|diagnostic|payload|backend snake_case|\b[a-z]+(?:_[a-z0-9]+)+\b|clean research handoff|evidence famil(?:y|ies)|business-quality review|peer group metadata|daily ohlcv|observation-only research readiness|personalized financial advice/i;

function safeResearchQueueText(value: string | null | undefined, locale: 'zh' | 'en', fallback?: string): string | null {
  const raw = String(value || '').trim();
  if (!raw) return fallback ?? null;
  if (ADVICE_OR_TRADE_WORDS.test(raw)) {
    return locale === 'en' ? 'Observation detail withheld.' : '观察细节已折叠。';
  }
  const safe = consumerPresentationText(raw, locale, fallback ?? (locale === 'en' ? 'Evidence needs review.' : '证据需要复核。'));
  if (INTERNAL_DIAGNOSTIC_WORDS.test(raw)) return safe;
  return safe || raw;
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
    watchlist: { zh: '观察列表', en: 'Watchlist' },
    scanner: { zh: '扫描器', en: 'Scanner' },
    market: { zh: '市场背景', en: 'Market' },
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

function evidenceHubLabel(item: ResearchRadarEvidenceHubItem, locale: 'zh' | 'en'): string {
  const key = String(item.key || '').toLowerCase();
  if (locale === 'en') {
    if (key === 'scanner') return 'Scanner candidates';
    if (key === 'backtest') return 'Backtest samples';
    if (key === 'stock') return 'Stock readiness';
    if (key === 'data') return 'Data activation';
    return safeResearchQueueText(item.label, locale, 'Evidence state') || 'Evidence state';
  }
  if (key === 'scanner') return '扫描候选';
  if (key === 'backtest') return '回测样本';
  if (key === 'stock') return '个股就绪';
  if (key === 'data') return '数据激活';
  return safeResearchQueueText(item.label, locale, '证据状态') || '证据状态';
}

function evidenceHubStatusTone(value: string | null | undefined): string {
  const normalized = String(value || '').toLowerCase();
  if (normalized === 'available') return 'success';
  if (normalized === 'partial') return 'warning';
  return 'error';
}

function readModelLabel(value: string | null | undefined, locale: 'zh' | 'en'): string {
  const raw = String(value || '').trim();
  const mapped = consumerStatusValue(value, locale);
  if (mapped !== '--' && mapped !== raw) return mapped;
  return raw ? consumerPresentationText(raw, locale, '--') : '--';
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

function evidenceQualityLabel(item: ResearchRadarItem, fallbackQuality: string | null | undefined, locale: 'zh' | 'en') {
  return consumerStatusValue(item.evidenceQuality?.status || fallbackQuality, locale);
}

function evidenceQualityTone(item: ResearchRadarItem, fallbackQuality: string | null | undefined) {
  return toneFor(item.evidenceQuality?.status || fallbackQuality);
}

function candidateReason(item: ResearchRadarItem, locale: 'zh' | 'en') {
  return safeResearchQueueList(
    item.whyOnRadar,
    locale,
    locale === 'en' ? 'Added to the observation queue for follow-up research.' : '该标的进入观察队列，适合继续做研究复核。',
  )[0];
}

function candidateMainGap(item: ResearchRadarItem, locale: 'zh' | 'en') {
  const gap = safeResearchQueueList(
    item.riskFlags?.length ? item.riskFlags : item.whatToVerify,
    locale,
    locale === 'en' ? 'No primary evidence gap reported.' : '未报告主要证据缺口。',
  )[0];
  return gap;
}

function candidateNextAction(item: ResearchRadarItem, locale: 'zh' | 'en') {
  return safeResearchQueueList(
    item.whatToVerify,
    locale,
    locale === 'en' ? 'Open the structure panel and review the supporting evidence.' : '打开结构面板，复核该标的的支持证据。',
  )[0];
}

function candidateSymbol(item: ResearchRadarItem): string {
  return String(item.ticker || item.symbol || '').trim().toUpperCase();
}

function candidateLimitations(item: ResearchRadarItem, locale: 'zh' | 'en'): string[] {
  return safeResearchQueueList(
    item.riskFlags?.length ? item.riskFlags : item.invalidationObservations,
    locale,
    locale === 'en' ? 'No primary limitation reported; keep the observation bounded.' : '未报告主要限制，继续保持观察边界。',
  );
}

function candidateVerificationItems(item: ResearchRadarItem, locale: 'zh' | 'en'): string[] {
  return safeResearchQueueList(
    item.whatToVerify,
    locale,
    locale === 'en' ? 'Review structure evidence before extending the research loop.' : '继续研究前先复核结构证据。',
  );
}

function candidateDriverScoreRows(item: ResearchRadarItem, locale: 'zh' | 'en') {
  return Object.entries(item.driverScores ?? {})
    .filter(([, value]) => typeof value === 'number' && Number.isFinite(value))
    .sort(([, left], [, right]) => (right ?? 0) - (left ?? 0))
    .map(([key, value]) => ({
      key,
      label: driverLabel(key, locale),
      value: Math.max(0, Math.min(100, Number(value))),
    }));
}

function buildEvidenceQualityDistribution(items: ResearchRadarItem[], fallbackQuality: string | null | undefined, locale: 'zh' | 'en') {
  if (!items.length) {
    return locale === 'en' ? 'No candidates' : '暂无候选';
  }
  const counts = new Map<string, number>();
  items.forEach((item) => {
    const label = evidenceQualityLabel(item, fallbackQuality, locale);
    counts.set(label, (counts.get(label) ?? 0) + 1);
  });
  return Array.from(counts.entries())
    .map(([label, count]) => `${label} ${count}`)
    .join(locale === 'en' ? ' · ' : '；');
}

function ResearchRadarQueueOverview({
  data,
  items,
  unifiedQueueSize,
  market,
  locale,
  linkLocale,
}: {
  data: ResearchRadarResponse;
  items: ResearchRadarItem[];
  unifiedQueueSize: number;
  market: string | undefined;
  locale: 'zh' | 'en';
  linkLocale: 'zh' | 'en';
}) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const queueQuality = data.aggregateSummary.queueQuality;
  const selectedItem = useMemo(() => {
    if (!items.length) return null;
    return items.find((item, index) => `${candidateSymbol(item) || 'candidate'}-${index}` === selectedKey) ?? items[0];
  }, [items, selectedKey]);
  const selectedSymbol = selectedItem ? candidateSymbol(selectedItem) : null;
  const selectedFactors = selectedItem ? candidateDriverScoreRows(selectedItem, locale) : [];
  const summaryItems = [
    {
      key: 'candidate-count',
      label: locale === 'en' ? 'Candidates' : '观察候选',
      value: items.length || unifiedQueueSize,
    },
    {
      key: 'evidence-quality',
      label: locale === 'en' ? 'Evidence quality' : '证据质量分布',
      value: buildEvidenceQualityDistribution(items, queueQuality, locale),
    },
    {
      key: 'queue-health',
      label: locale === 'en' ? 'Queue health' : '队列健康',
      value: <StatusBadge status={toneFor(queueQuality)} label={consumerStatusValue(queueQuality, locale)} size="sm" />,
    },
    {
      key: 'updated',
      label: locale === 'en' ? 'Updated' : '更新时间',
      value: formatDateTime(data.generatedAt, { locale: locale === 'en' ? 'en-US' : 'zh-CN' }),
    },
  ];

  return (
    <div className="border-b border-[color:var(--wolfy-divider)] p-3" data-testid="research-radar-consumer-overview">
      <RoughSectionCard
        eyebrow={locale === 'en' ? 'Observation queue' : '观察队列'}
        title={locale === 'en' ? 'Today’s observation queue' : '今日观察队列'}
      >
        <div className="space-y-4">
          <ConsoleStatusStrip items={summaryItems} />
          <div className="flex flex-wrap gap-2 text-xs text-[color:var(--wolfy-text-muted)]">
            <TerminalChip variant="neutral">{market || (locale === 'en' ? 'All markets' : '全部市场')}</TerminalChip>
            <TerminalChip variant="info">
              {locale === 'en' ? 'Symbols for research observation' : '仅展示研究观察标的'}
            </TerminalChip>
          </div>
          {items.length ? (
            <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(24rem,0.9fr)]">
              <div
                data-testid="research-radar-candidate-ledger"
                className="min-w-0 overflow-x-auto rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-panel)]"
              >
                <table className="min-w-[760px] w-full border-collapse text-left text-sm">
                  <caption className="sr-only">
                    {locale === 'en' ? 'Research Radar candidate queue' : '研究雷达候选队列'}
                  </caption>
                  <thead className="border-b border-[color:var(--wolfy-divider)] text-[11px] uppercase text-[color:var(--wolfy-text-muted)]">
                    <tr>
                      <th scope="col" className="px-3 py-2 font-medium">{locale === 'en' ? 'Symbol' : '标的'}</th>
                      <th scope="col" className="px-3 py-2 font-medium">{locale === 'en' ? 'Why queued' : '入队原因'}</th>
                      <th scope="col" className="px-3 py-2 font-medium">{locale === 'en' ? 'Evidence' : '证据强度'}</th>
                      <th scope="col" className="px-3 py-2 font-medium">{locale === 'en' ? 'Limitation' : '限制'}</th>
                      <th scope="col" className="px-3 py-2 font-medium">{locale === 'en' ? 'Next check' : '下一步检查'}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[color:var(--wolfy-divider)]">
                    {items.map((item, index) => {
                      const symbol = candidateSymbol(item) || '--';
                      const rowKey = `${symbol || 'candidate'}-${index}`;
                      const selected = selectedItem === item;
                      return (
                        <tr
                          key={rowKey}
                          data-testid={`research-radar-candidate-${symbol}`}
                          className={selected ? 'bg-[var(--wolfy-surface-input)]' : 'bg-transparent'}
                        >
                          <th scope="row" className="px-3 py-3 align-top">
                            <button
                              type="button"
                              aria-pressed={selected}
                              aria-label={locale === 'en' ? `Inspect ${symbol}` : `查看 ${symbol} 研究细节`}
                              className="flex min-w-0 flex-col items-start rounded-md border border-transparent px-2 py-1 text-left transition hover:border-[color:var(--wolfy-border-subtle)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent)]"
                              onClick={() => setSelectedKey(rowKey)}
                            >
                              <span className="font-mono text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{symbol}</span>
                              {item.priority ? (
                                <span className="mt-1">
                                  <StatusBadge status={toneFor(item.priority)} label={consumerStatusValue(item.priority, locale)} size="sm" />
                                </span>
                              ) : null}
                            </button>
                          </th>
                          <td className="max-w-[18rem] px-3 py-3 align-top text-[color:var(--wolfy-text-secondary)]">{candidateReason(item, locale)}</td>
                          <td className="px-3 py-3 align-top">
                            <StatusBadge
                              status={evidenceQualityTone(item, queueQuality)}
                              label={evidenceQualityLabel(item, queueQuality, locale)}
                              size="sm"
                            />
                          </td>
                          <td className="max-w-[16rem] px-3 py-3 align-top text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">{candidateMainGap(item, locale)}</td>
                          <td className="max-w-[16rem] px-3 py-3 align-top text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">{candidateNextAction(item, locale)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {selectedItem && selectedSymbol ? (
                <section
                  data-testid="research-radar-selected-candidate-detail"
                  aria-labelledby="research-radar-selected-candidate-title"
                  className="min-w-0 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-panel)] p-4"
                >
                  <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Selected research observation' : '已选研究观察'}</p>
                      <h3 id="research-radar-selected-candidate-title" className="mt-1 font-mono text-lg font-semibold text-[color:var(--wolfy-text-primary)]">
                        {selectedSymbol}
                      </h3>
                    </div>
                    <StatusBadge
                      status={evidenceQualityTone(selectedItem, queueQuality)}
                      label={evidenceQualityLabel(selectedItem, queueQuality, locale)}
                      size="sm"
                    />
                  </div>

                  <div className="mt-4 space-y-4">
                    <section>
                      <h4 className="text-xs font-semibold text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Current observation' : '当前研究观察'}</h4>
                      <p className="mt-1 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{candidateReason(selectedItem, locale)}</p>
                    </section>
                    <section>
                      <h4 className="text-xs font-semibold text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Factor contribution' : '因子贡献'}</h4>
                      {selectedFactors.length ? (
                        <div className="mt-2 space-y-2" data-testid="research-radar-factor-bars">
                          {selectedFactors.map((factor) => (
                            <div key={factor.key} className="grid min-w-0 grid-cols-[7.5rem_minmax(0,1fr)_3rem] items-center gap-2 text-xs">
                              <span className="truncate text-[color:var(--wolfy-text-secondary)]">{factor.label}</span>
                              <div
                                className="h-2 overflow-hidden rounded-full bg-[var(--wolfy-surface-input)]"
                                aria-label={`${factor.label} ${Math.round(factor.value)}`}
                              >
                                <div
                                  className="h-full rounded-full bg-[var(--wolfy-accent)]"
                                  style={{ width: `${factor.value}%` }}
                                />
                              </div>
                              <span className="text-right font-mono text-[color:var(--wolfy-text-muted)]">{Math.round(factor.value)}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="mt-1 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                          {locale === 'en' ? 'No factor dimensions are available for this candidate.' : '该候选暂无可展示的真实因子维度。'}
                        </p>
                      )}
                    </section>
                    <section>
                      <h4 className="text-xs font-semibold text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Limitation / risk' : '限制 / 风险'}</h4>
                      <RoughBulletList
                        items={candidateLimitations(selectedItem, locale)}
                        emptyText={locale === 'en' ? 'No limitation reported.' : '未报告限制。'}
                      />
                    </section>
                    <section>
                      <h4 className="text-xs font-semibold text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Data freshness' : '数据时效'}</h4>
                      <p className="mt-1 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                        {locale === 'en' ? 'Queue updated ' : '队列更新 '}
                        <span className="font-mono">{formatDateTime(data.generatedAt, { locale: locale === 'en' ? 'en-US' : 'zh-CN' })}</span>
                      </p>
                    </section>
                    <section>
                      <h4 className="text-xs font-semibold text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Next research check' : '下一步研究检查'}</h4>
                      <RoughBulletList
                        items={candidateVerificationItems(selectedItem, locale)}
                        emptyText={locale === 'en' ? 'No next check reported.' : '暂未报告下一步检查。'}
                      />
                    </section>
                    <div className="flex min-w-0 flex-wrap gap-2 pt-1">
                      <Link
                        to={buildResearchWorkspacePath('stock-structure', linkLocale, { symbol: selectedSymbol, market, source: 'scanner' })}
                        className="inline-flex min-h-9 items-center rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 text-xs font-medium text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent)]"
                      >
                        {locale === 'en' ? 'Open stock research' : '查看个股研究'}
                      </Link>
                      <Link
                        to={buildResearchWorkspacePath('watchlist', linkLocale, { symbol: selectedSymbol, market, source: 'scanner' })}
                        className="inline-flex min-h-9 items-center rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 text-xs font-medium text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent)]"
                      >
                        {locale === 'en' ? 'Open Watchlist view' : '打开观察列表视图'}
                      </Link>
                    </div>
                  </div>
                </section>
              ) : null}
            </div>
          ) : (
            <ConsumerResearchEmptyState
              data-testid="research-radar-queue-empty-state"
              locale={locale}
              state={buildConsumerResearchEmptyState('noQueueItems', locale)}
            />
          )}
          <p className="text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
            {locale === 'en' ? 'Research observation, not investment advice.' : '研究观察，不构成投资建议。'}
          </p>
        </div>
      </RoughSectionCard>
    </div>
  );
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
  const fallbackCards = (data?.marketLevelFallback?.evidenceCards ?? [])
    .filter((card) => card.observationOnly !== false && card.decisionGrade !== true);
  const notesForCategory = (category: 'marketBreadth' | 'stockEvidence' | 'researchQueueFreshness'): string[] => {
    const patterns: Record<typeof category, RegExp[]> = {
      marketBreadth: [/breadth/i],
      stockEvidence: [/growth|proxy/i],
      researchQueueFreshness: [/freshness|stale|recency/i],
    };
    return consumerPresentationList(
      fallbackCards
        .filter((card) => patterns[category].some((pattern) => pattern.test(`${card.cardId || ''} ${card.title || ''} ${card.headline || ''}`)))
        .map((card) => card.headline),
      locale,
      '',
    ).filter((note) => note.trim().length > 0);
  };

  return createConsumerDataHealthSummary({
    locale,
    categories: [
      {
        category: 'marketBreadth',
        quality: dataHealthQualityFromStatus(data?.dataQuality?.status),
        supportingNotes: notesForCategory('marketBreadth'),
      },
      {
        category: 'stockEvidence',
        quality: stockEvidenceQuality,
        supportingNotes: notesForCategory('stockEvidence'),
      },
      {
        category: 'researchQueueFreshness',
        quality: queueFreshnessQuality,
        supportingNotes: notesForCategory('researchQueueFreshness'),
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
    locale === 'en' ? 'Observation mode' : '观察模式',
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
      conditions.push(locale === 'en' ? 'Scanner candidates have not been created yet.' : '扫描器候选尚未建立。');
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
          ? `The queue is still missing ${missingEvidenceLabels.join(', ')}, so it stays in observation mode.`
          : `当前队列仍缺少${missingEvidenceLabels.join('、')}，因此先保持观察边界。`)
        : (expectedSurfaces.some((surface) => surface !== 'manual_gap' && !availableSurfaces.has(surface))
          ? (locale === 'en'
            ? 'Prerequisites incomplete'
            : '前置条件未完成')
          : null)
    );

  return {
    title: data?.onboardingGuidance?.title ?? null,
    summary: derivedSummary,
    conditionsDetected: dedupedConditions,
  };
}

function ResearchEvidenceHubPanel({
  data,
  locale,
}: {
  data: ResearchRadarResponse | null;
  locale: 'zh' | 'en';
}) {
  const hub = data?.evidenceHub;
  if (!hub) return null;

  const slices = [
    hub.scannerCandidates,
    hub.backtestSamples,
    hub.stockReadiness,
    hub.dataActivation,
  ];
  const missingStates = hub.missingEvidenceStates ?? [];

  return (
    <RoughSectionCard
      data-testid="research-radar-evidence-hub"
      className="md:col-span-2"
      eyebrow={locale === 'en' ? 'Evidence hub' : '证据中枢'}
      title={locale === 'en' ? 'Real evidence readiness' : '真实证据就绪状态'}
    >
      <div className="space-y-4">
        <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
          {locale === 'en'
            ? 'Scanner, backtest sample, stock readiness, and activation states from available product evidence.'
            : '汇总当前产品内已有的扫描候选、回测样本、个股就绪和数据激活状态。'}
        </p>

        <div className="grid gap-3 lg:grid-cols-4">
          {slices.map((item) => {
            const safeSummary = safeResearchQueueText(item.summary, locale, locale === 'en' ? 'Evidence state unavailable.' : '证据状态暂不可用。');
            const safeBlocker = safeResearchQueueText(item.blocker, locale);
            const safeAction = safeResearchQueueText(item.nextDataAction, locale, locale === 'en' ? 'Refresh evidence.' : '刷新证据。');
            const details = safeResearchQueueList(
              item.details,
              locale,
              locale === 'en' ? 'No detail listed.' : '暂无明细。',
            );
            return (
              <section
                key={String(item.key || item.label)}
                className="min-w-0 rounded-xl border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] p-3"
              >
                <div className="flex min-w-0 items-start justify-between gap-2">
                  <h3 className="min-w-0 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
                    {evidenceHubLabel(item, locale)}
                  </h3>
                  <StatusBadge
                    status={evidenceHubStatusTone(item.status)}
                    label={consumerStatusValue(item.status, locale)}
                    size="sm"
                  />
                </div>
                <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">{safeSummary}</p>
                {safeBlocker ? (
                  <p className="mt-2 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-2 py-1.5 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                    <span className="font-medium text-[color:var(--wolfy-text-primary)]">
                      {locale === 'en' ? 'Blocker: ' : '阻塞：'}
                    </span>
                    {safeBlocker}
                  </p>
                ) : null}
                <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                  <span className="font-medium text-[color:var(--wolfy-text-secondary)]">
                    {locale === 'en' ? 'Next data action: ' : '下一步数据动作：'}
                  </span>
                  {safeAction}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {(item.symbols ?? []).slice(0, 5).map((symbol) => (
                    <TerminalChip key={symbol} variant="neutral" className="font-mono">{symbol}</TerminalChip>
                  ))}
                </div>
                <RoughBulletList
                  items={details}
                  emptyText={locale === 'en' ? 'No detail listed.' : '暂无明细。'}
                />
              </section>
            );
          })}
        </div>

        {missingStates.length ? (
          <section
            data-testid="research-radar-missing-evidence-states"
            className="rounded-xl border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] p-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
                {locale === 'en' ? 'Missing evidence states' : '缺失证据状态'}
              </h3>
              <TerminalChip variant="caution">{missingStates.length}</TerminalChip>
            </div>
            <div className="mt-3 grid gap-2">
              {missingStates.map((item, index) => {
                const safeBlocker = safeResearchQueueText(item.blocker, locale, locale === 'en' ? 'Evidence is incomplete.' : '证据尚未完整。');
                const safeAction = safeResearchQueueText(item.nextDataAction, locale, locale === 'en' ? 'Refresh evidence.' : '刷新证据。');
                return (
                  <div
                    key={`${item.key || item.label}-${index}`}
                    className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-panel)] px-3 py-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]"
                  >
                    <span className="font-semibold text-[color:var(--wolfy-text-primary)]">
                      {evidenceHubLabel(item, locale)}
                    </span>
                    <span className="mx-2 text-[color:var(--wolfy-text-muted)]">/</span>
                    <span>{safeBlocker}</span>
                    <span className="mx-2 text-[color:var(--wolfy-text-muted)]">/</span>
                    <span>{safeAction}</span>
                  </div>
                );
              })}
            </div>
          </section>
        ) : null}
      </div>
    </RoughSectionCard>
  );
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
            ? 'Evidence-first follow-up across research surfaces.'
            : '按证据优先级汇总各研究入口的后续复核事项。'}
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
                className="rounded-xl border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] p-3"
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
                                  className="block rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-xs leading-5 transition-colors hover:text-[color:var(--wolfy-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent)]"
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

      </div>
    </RoughSectionCard>
  );
}

function MarketLevelFallbackPanel({
  fallback,
  locale,
}: {
  fallback: ResearchRadarMarketLevelFallback | null | undefined;
  locale: 'zh' | 'en';
}) {
  if (!fallback?.available || fallback.observationOnly === false || fallback.decisionGrade === true) {
    return null;
  }
  const cards = (fallback.evidenceCards ?? []).filter((card) => card.observationOnly !== false && card.decisionGrade !== true);
  const missingFamilies = consumerPresentationList(
    fallback.missingDataFamilies ?? fallback.readiness?.missingDataFamilies ?? fallback.dataQuality?.missingDataFamilies,
    locale,
    locale === 'en' ? 'No missing market evidence family reported.' : '未报告缺失的市场证据族。',
  );
  const blockedSurfaces = consumerPresentationList(
    fallback.blockedProductSurfaces ?? fallback.readiness?.blockedProductSurfaces ?? fallback.dataQuality?.blockedProductSurfaces,
    locale,
    locale === 'en' ? 'No blocked product surface reported.' : '未报告阻塞的产品界面。',
  );
  const action = safeResearchQueueText(
    fallback.nextOperatorAction ?? fallback.readiness?.nextOperatorAction,
    locale,
    locale === 'en' ? 'Review market evidence inputs before using candidate research.' : '先复核市场证据输入，再使用候选研究。',
  );
  return (
    <RoughSectionCard
      eyebrow={locale === 'en' ? 'Market-level context' : '市场级上下文'}
      title={locale === 'en' ? 'Market evidence while candidate research is unavailable' : '候选研究不可用时的市场证据'}
      className="md:col-span-2"
    >
      <div data-testid="research-radar-market-level-fallback" className="space-y-4">
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] p-3">
            <div className="text-xs text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Scope' : '范围'}</div>
            <div className="mt-1 text-sm font-medium text-[color:var(--wolfy-text-primary)]">
              {consumerPresentationText(fallback.label, locale, locale === 'en' ? 'Market-level context' : '市场级上下文')}
            </div>
            <div className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
              {locale === 'en'
                ? 'Candidate research is unavailable or has not executed. This is not stock candidate ranking.'
                : '候选研究不可用或尚未执行；这里不是个股候选排序。'}
            </div>
          </div>
          <div className="rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] p-3">
            <div className="text-xs text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Regime' : '市场状态'}</div>
            <div className="mt-1 flex flex-wrap gap-2">
              <StatusBadge status={toneFor(fallback.regime?.status)} label={readModelLabel(fallback.regime?.label, locale)} size="sm" />
              <StatusBadge status={toneFor(fallback.readiness?.label)} label={readModelLabel(fallback.readiness?.label, locale)} size="sm" />
            </div>
          </div>
          <div className="rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] p-3">
            <div className="text-xs text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Candidate state' : '候选状态'}</div>
            <div className="mt-1 text-sm font-medium text-[color:var(--wolfy-text-primary)]">
              {fallback.candidateGenerationExecuted
                ? (locale === 'en' ? 'Candidate generation executed' : '候选生成已执行')
                : (locale === 'en' ? 'Candidate generation not executed' : '候选生成未执行')}
            </div>
            <div className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
              {locale === 'en' ? 'No candidates, ranks, scores, or tickers are created by this fallback.' : '该市场级上下文不创建候选、排名、评分或标的。'}
            </div>
          </div>
        </div>
        <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
          {consumerPresentationText(fallback.productSummary, locale, locale === 'en' ? 'Market-level evidence summary is unavailable.' : '市场级证据摘要暂不可用。')}
        </p>
        <div className="grid gap-3 md:grid-cols-3">
          {cards.map((card, index) => (
            <div key={`${card.cardId || card.title || 'card'}-${index}`} className="rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                  {consumerPresentationText(card.title, locale, locale === 'en' ? 'Evidence card' : '证据卡')}
                </div>
                <StatusBadge status={toneFor(card.status)} label={readModelLabel(card.status, locale)} size="sm" />
              </div>
              <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                {consumerPresentationText(card.headline, locale, locale === 'en' ? 'Evidence needs review.' : '证据需要复核。')}
              </p>
            </div>
          ))}
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <RoughBulletList
            items={missingFamilies}
            emptyText={locale === 'en' ? 'No missing market evidence family reported.' : '未报告缺失的市场证据族。'}
          />
          <RoughBulletList
            items={blockedSurfaces}
            emptyText={locale === 'en' ? 'No blocked product surface reported.' : '未报告阻塞的产品界面。'}
          />
          <div className="rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] p-3">
            <div className="text-xs text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Next operator action' : '下一步操作'}</div>
            <div className="mt-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{action}</div>
          </div>
        </div>
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
  const hasMarketLevelFallback = Boolean(data?.marketLevelFallback?.available && queueItems.length === 0 && (unifiedQueue?.researchQueue.length ?? 0) === 0);
  const showOnboardingCta = Boolean(data && queueItems.length === 0 && (data.emptyStateActions.length || data.starterResearchWorkflow.length));
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
                {locale === 'en' ? 'Core queue for priority, verification, and evidence gaps.' : '优先级、验证事项与证据缺口的核心队列。'}
              </div>
            </WolfyCommandBar>
          )}
          rail={(
            <ConsoleContextRail className="flex flex-col gap-3 p-3">
              <RoughSectionCard eyebrow={locale === 'en' ? 'Queue state' : '队列状态'} title={locale === 'en' ? 'Today at a glance' : '今日概览'}>
                <RoughKeyValueRows
                  emptyText={locale === 'en' ? 'Queue summary is not ready yet.' : '队列摘要暂未形成。'}
                  rows={[
                    {
                      key: 'candidate-count',
                      label: locale === 'en' ? 'Candidates' : '观察候选',
                      value: queueItems.length || unifiedQueueSize || '--',
                    },
                    {
                      key: 'quality',
                      label: locale === 'en' ? 'Evidence quality' : '证据质量',
                      value: data ? buildEvidenceQualityDistribution(queueItems, data.aggregateSummary.queueQuality, locale) : '--',
                    },
                    {
                      key: 'health',
                      label: locale === 'en' ? 'Queue health' : '队列健康',
                      value: consumerStatusValue(data?.aggregateSummary.queueQuality, locale),
                    },
                  ]}
                />
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Details' : '明细'} title={locale === 'en' ? 'Evidence details are collapsed' : '证据明细默认折叠'}>
                <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                  {locale === 'en'
                    ? 'Open the details section for evidence gaps, data health, and queue readiness.'
                    : '完整证据缺口、数据健康与队列就绪状态已放入下方明细区。'}
                </p>
              </RoughSectionCard>
            </ConsoleContextRail>
          )}
        >
          <ConsoleBoard className="min-h-0" data-testid="research-radar-page">
            <RoughSurfaceIntro
              eyebrow={locale === 'en' ? 'Research radar' : '研究雷达'}
              title={locale === 'en' ? 'Today’s observation queue' : '今日观察队列'}
              description={locale === 'en'
                ? 'See which symbols are worth observing, why they surfaced, and what evidence still limits the read.'
                : '查看哪些标的值得观察、为什么进入队列，以及当前证据还有哪些限制。'}
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
                <ResearchRadarQueueOverview
                  data={data}
                  items={queueItems}
                  unifiedQueueSize={unifiedQueueSize}
                  market={market}
                  locale={locale}
                  linkLocale={routeLocale || locale}
                />
                {hasMarketLevelFallback ? (
                  <div className="grid gap-3 p-3 md:grid-cols-2">
                    <MarketLevelFallbackPanel
                      fallback={data.marketLevelFallback}
                      locale={locale}
                    />
                  </div>
                ) : null}
                <div className="p-3">
                  <details
                    data-testid="research-radar-diagnostics-disclosure"
                    className="rounded-[16px] border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3"
                  >
                    <summary className="cursor-pointer text-sm font-medium text-[color:var(--wolfy-text-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent)]">
                      {locale === 'en' ? 'View detailed evidence and data readiness' : '查看详细证据与数据就绪'}
                    </summary>
                    <div className="mt-3 space-y-3">
                      <ConsumerDataHealthSummaryPanel
                        summary={dataHealthSummary}
                        title={locale === 'en' ? 'Data health' : '数据健康'}
                        testId="research-radar-data-health-summary"
                      />
                      <div className="grid gap-3 md:grid-cols-2">
                        {showOnboardingCta ? (
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
                        <ResearchEvidenceHubPanel
                          data={data}
                          locale={locale}
                        />
                        <ResearchQueueHubPanel
                          data={unifiedQueue}
                          loading={unifiedQueueLoading}
                          unavailable={unifiedQueueUnavailable}
                          locale={locale}
                          localize={localize}
                        />
                        {!hasMarketLevelFallback && data.marketLevelFallback?.available ? (
                          <MarketLevelFallbackPanel
                            fallback={data.marketLevelFallback}
                            locale={locale}
                          />
                        ) : null}
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
                    </div>
                  </details>
                </div>
              </>
            ) : null}
          </ConsoleBoard>
        </ResearchConsoleShell>
      </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
}
