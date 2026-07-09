import type React from 'react';
import { RefreshCcw } from 'lucide-react';
import { useI18n } from '../../contexts/UiLanguageContext';
import type { MarketDataFreshness, MarketDataMeta, MarketOverviewItem, MarketOverviewPanel, MarketProviderHealthStatus } from '../../api/marketOverview';
import { cn } from '../../utils/cn';
import { TerminalPanel } from '../terminal/TerminalPrimitives';
import { formatMarketOverviewTimestamp } from './marketOverviewFormat';
import {
  formatChangeSummary,
  formatMetricValue,
  getDirectionTone,
} from './marketOverviewUtils';
import { resolveMarketOverviewDisplayLabel } from './marketOverviewLabels';

const FRESHNESS_LABELS: Record<MarketDataFreshness, string> = {
  live: '实时',
  fresh: '实时',
  delayed: '延迟可读',
  cached: '保存快照',
  stale: '可能延迟',
  partial: '部分可用',
  fallback: '替代快照',
  mock: '示例观察',
  synthetic: '示例观察',
  error: '读取异常',
  unavailable: '暂不可用',
  unknown: '待确认',
  proxy: '代理数据',
};

type MarketFreshnessBadgeKey = MarketProviderHealthStatus | 'delayed' | 'mock' | 'proxy';

const STATUS_LABELS: Record<MarketFreshnessBadgeKey, string> = {
  live: '实时',
  cache: '保存快照',
  delayed: '延迟可读',
  stale: '可能延迟',
  fallback: '替代快照',
  mock: '示例观察',
  proxy: '代理数据',
  partial: '部分可用',
  unavailable: '暂不可用',
  error: '读取异常',
  refreshing: '更新中',
};

const FRESHNESS_CLASSES: Record<MarketFreshnessBadgeKey, string> = {
  live: 'border-[color:var(--state-success-border)] bg-[var(--state-success-bg)] text-[color:var(--state-success-text)]',
  cache: 'border-[color:var(--line)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-muted)]',
  delayed: 'border-[color:var(--state-info-border)] bg-[var(--state-info-bg)] text-[color:var(--state-info-text)]',
  stale: 'border-[color:var(--state-warning-border)] bg-[var(--state-warning-bg)] text-[color:var(--state-warning-text)]',
  fallback: 'border-[color:var(--state-warning-border)] bg-[var(--state-warning-bg)] text-[color:var(--state-warning-text)]',
  mock: 'border-[color:var(--state-warning-border)] bg-[var(--state-warning-bg)] text-[color:var(--state-warning-text)]',
  proxy: 'border-[color:var(--state-info-border)] bg-[var(--state-info-bg)] text-[color:var(--state-info-text)]',
  partial: 'border-[color:var(--state-info-border)] bg-[var(--state-info-bg)] text-[color:var(--state-info-text)]',
  unavailable: 'border-[color:var(--line)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-muted)]',
  error: 'border-[color:var(--state-danger-border)] bg-[var(--state-danger-bg)] text-[color:var(--state-danger-text)]',
  refreshing: 'border-[color:var(--state-info-border)] bg-[var(--state-info-bg)] text-[color:var(--state-info-text)]',
};

const CONSUMER_UNSAFE_DETAIL_PATTERN = /provider|fallback|proxy|raw|debug|reason|sourceauthority|scorecontribution|marketcache|runtime|diagnostic|json/i;

export type MarketOverviewCardSize = 'compact' | 'standard' | 'list' | 'large' | 'rail';

const MARKET_OVERVIEW_CARD_SIZE_CLASS: Record<MarketOverviewCardSize, string> = {
  compact: 'min-h-[130px] p-3',
  standard: 'min-h-[200px] p-3.5',
  list: 'min-h-[200px] max-h-[320px] p-3.5',
  large: 'min-h-[220px] max-h-[340px] p-4',
  rail: 'min-h-[96px] max-h-[130px] p-3',
};

export const MarketOverviewCardFrame: React.FC<{
  title?: React.ReactNode;
  eyebrow?: React.ReactNode;
  subtitle?: React.ReactNode;
  size?: MarketOverviewCardSize;
  className?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  testId?: string;
  railKey?: string;
}> = ({
  title,
  eyebrow,
  subtitle,
  size = 'standard',
  className,
  children,
  footer,
  testId,
  railKey,
}) => (
  <TerminalPanel
    as="section"
    data-testid={testId}
    data-market-card-size={size}
    data-rail-card={railKey}
    className={cn(
      MARKET_OVERVIEW_CARD_SIZE_CLASS[size],
      'flex min-w-0 flex-col overflow-visible',
      className,
    )}
  >
    {title || eyebrow || subtitle ? (
      <div className="mb-3 min-w-0 shrink-0">
        {eyebrow ? <p className="truncate text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{eyebrow}</p> : null}
        {title ? <h2 className="mt-1 truncate text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{title}</h2> : null}
        {subtitle ? <p className="mt-1 truncate text-[11px] leading-4 text-[color:var(--wolfy-text-muted)]">{subtitle}</p> : null}
      </div>
    ) : null}
    <div className="min-h-0 min-w-0 flex-1 overflow-visible p-0.5">{children}</div>
    {footer ? <div className="mt-3 shrink-0 border-t border-[color:var(--line)] pt-2 text-[10px] leading-4 text-[color:var(--wolfy-text-muted)]">{footer}</div> : null}
  </TerminalPanel>
);

function resolveProviderStatus(meta?: Partial<MarketDataMeta>): MarketProviderHealthStatus {
  if (meta?.providerHealth?.status) {
    return meta.providerHealth.status;
  }
  if (meta?.isRefreshing) {
    return 'refreshing';
  }
  if (meta?.isUnavailable || meta?.source === 'unavailable' || meta?.freshness === 'unavailable') {
    return 'unavailable';
  }
  if (meta?.freshness === 'error') {
    return 'error';
  }
  if (meta?.isFallback || meta?.source === 'fallback' || meta?.freshness === 'fallback' || meta?.freshness === 'mock') {
    return 'fallback';
  }
  if (meta?.isStale || meta?.freshness === 'stale') {
    return 'stale';
  }
  if (meta?.freshness === 'live') {
    return 'live';
  }
  return 'cache';
}

function resolveFreshness(meta?: Partial<MarketDataMeta>): MarketProviderHealthStatus {
  return resolveProviderStatus(meta);
}

function legacyFreshnessToStatus(freshness?: MarketDataFreshness): MarketProviderHealthStatus {
  if (freshness === 'live' || freshness === 'fresh') {
    return 'live';
  }
  if (freshness === 'stale') {
    return 'stale';
  }
  if (freshness === 'fallback' || freshness === 'mock' || freshness === 'synthetic') {
    return 'fallback';
  }
  if (freshness === 'unavailable' || freshness === 'unknown') {
    return 'unavailable';
  }
  if (freshness === 'error') {
    return 'error';
  }
  if (freshness === 'partial') {
    return 'partial';
  }
  return 'cache';
}

function resolveFreshnessBadgeKey(freshness?: MarketDataFreshness, status?: MarketProviderHealthStatus): MarketFreshnessBadgeKey {
  if (freshness === 'proxy') {
    return 'proxy';
  }
  if (status === 'cache' && freshness === 'delayed') {
    return 'delayed';
  }
  if (status === 'fallback' && (freshness === 'mock' || freshness === 'synthetic')) {
    return 'mock';
  }
  if (status) {
    return status;
  }
  if (freshness === 'delayed') {
    return 'delayed';
  }
  if (freshness === 'mock') {
    return 'mock';
  }
  return legacyFreshnessToStatus(freshness);
}

export const DataFreshnessBadge: React.FC<{ freshness?: MarketDataFreshness; status?: MarketProviderHealthStatus; className?: string }> = ({ freshness, status, className }) => {
  const resolved = resolveFreshnessBadgeKey(freshness, status);
  return (
    <span
      data-testid={`data-freshness-badge-${resolved}`}
      className={cn('inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold leading-none', FRESHNESS_CLASSES[resolved], className)}
    >
      {STATUS_LABELS[resolved] || FRESHNESS_LABELS[freshness || 'cached']}
    </span>
  );
};

function metaText(meta?: Partial<MarketDataMeta>): string[] {
  const parts: string[] = [];
  const asOf = formatMarketOverviewTimestamp(meta?.asOf);
  const updatedAt = formatMarketOverviewTimestamp(meta?.updatedAt);
  if (asOf) {
    parts.push(`Quote ${asOf}`);
  }
  if (updatedAt) {
    parts.push(`Update ${updatedAt}`);
  }
  return parts;
}

function compactMetaText(meta?: Partial<MarketDataMeta>): string {
  return formatMarketOverviewTimestamp(meta?.asOf)
    || formatMarketOverviewTimestamp(meta?.updatedAt)
    || '';
}

function sortableTimestamp(value?: string | null): { time: number; label: string } | null {
  const text = String(value || '').trim();
  if (!text) {
    return null;
  }
  const time = new Date(text).getTime();
  const label = formatMarketOverviewTimestamp(text);
  if (!label || Number.isNaN(time)) {
    return null;
  }
  return { time, label };
}

function evidenceTimestampWindow(panel?: MarketOverviewPanel): string {
  const timestamps = (panel?.items || [])
    .map((item) => sortableTimestamp(item.asOf || item.updatedAt))
    .filter((item): item is { time: number; label: string } => Boolean(item))
    .sort((left, right) => left.time - right.time);
  const uniqueLabels = Array.from(new Set(timestamps.map((item) => item.label)));
  if (uniqueLabels.length < 2) {
    return '';
  }
  return `时间窗口 ${uniqueLabels[0]} - ${uniqueLabels[uniqueLabels.length - 1]}`;
}

function sanitizeConsumerDetails(details?: string[] | null): string[] {
  return (details || []).reduce<string[]>((acc, detail) => {
    if (acc.length >= 2) return acc;
    const normalized = String(detail || '').trim();
    if (normalized && !CONSUMER_UNSAFE_DETAIL_PATTERN.test(normalized)) {
      acc.push(normalized);
    }
    return acc;
  }, []);
}

function metadataTitle(parts: string[], warning?: string | null, hoverDetails?: string[] | null): string | undefined {
  return [...parts, warning, ...sanitizeConsumerDetails(hoverDetails)].filter(Boolean).join(' · ') || undefined;
}

function shouldShowInlineWarning(meta?: Partial<MarketDataMeta>): boolean {
  if (!meta?.warning) {
    return false;
  }
  if (meta.freshness === 'error' || meta.source === 'error' || meta.isStale || meta.freshness === 'stale') {
    return true;
  }
  return false;
}

export const MarketOverviewSparkline: React.FC<{ values?: number[]; tone?: string; className?: string }> = ({
  values,
  tone = 'text-[color:var(--wolfy-text-muted)]',
  className,
}) => {
  const points = Array.isArray(values) ? values.filter((value) => Number.isFinite(value)) : [];
  if (points.length < 2) {
    return <div className={cn('h-8', className)} data-testid="market-overview-sparkline" />;
  }
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const path = points.map((value, index) => {
    const x = (index / (points.length - 1)) * 100;
    const y = 32 - ((value - min) / span) * 24;
    return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join(' ');

  return (
    <svg
      viewBox="0 0 100 34"
      className={cn('w-full overflow-hidden', tone, className)}
      preserveAspectRatio="none"
      data-testid="market-overview-sparkline"
      aria-hidden="true"
    >
      <path d={path} fill="none" stroke="currentColor" strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
    </svg>
  );
};

export const MarketOverviewRefreshButton: React.FC<{
  label: string;
  refreshing?: boolean;
  onRefresh: () => void;
}> = ({ label, refreshing = false, onRefresh }) => (
  <button
    type="button"
    aria-label={label}
    onClick={onRefresh}
    disabled={refreshing}
    className="inline-flex h-[36px] w-[36px] scroll-m-3 items-center justify-center rounded-lg border border-[color:var(--line)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-muted)] transition-all hover:bg-[var(--surface-3)] hover:text-[color:var(--wolfy-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent-focus)] cursor-pointer disabled:cursor-wait disabled:text-[color:var(--wolfy-text-muted)] sm:h-[32px] sm:w-[32px]"
  >
    <RefreshCcw className={cn('size-4', refreshing ? 'animate-spin' : '')} aria-hidden="true" />
  </button>
);

export const MarketOverviewPanelFooter: React.FC<{ panel?: MarketOverviewPanel; sourceLabel?: string; meta?: Partial<MarketDataMeta> }> = ({ panel, sourceLabel, meta }) => {
  const { t } = useI18n();
  const resolvedMeta = meta || panel;
  const pendingLabel = t('marketOverviewPage.footer.pending');
  const fallbackUpdatedAt = panel?.lastRefreshAt
    ? t('marketOverviewPage.footer.lastRefresh', {
        timestamp: formatMarketOverviewTimestamp(panel.lastRefreshAt) || pendingLabel,
      })
    : '';
  const details = metaText(resolvedMeta);
  if (sourceLabel && !details.length) {
    details.push(sourceLabel);
  }
  if (resolvedMeta?.isRefreshing) {
    details.push(t('marketOverviewPage.footer.refreshingSnapshot'));
  }
  const timestampWindow = evidenceTimestampWindow(panel);
  if (timestampWindow) {
    details.unshift(timestampWindow);
  }
  const compactDetails = timestampWindow
    || compactMetaText(resolvedMeta)
    || fallbackUpdatedAt
    || (resolvedMeta?.isRefreshing ? t('marketOverviewPage.footer.refreshingSnapshot') : pendingLabel);
  const freshness = resolveFreshness(resolvedMeta);

  return (
    <div className="mt-auto min-w-0 border-t border-[color:var(--wolfy-border-subtle)] pt-3">
      <div className="flex min-w-0 items-center gap-2 overflow-hidden whitespace-nowrap">
        <DataFreshnessBadge freshness={resolvedMeta?.freshness} status={freshness} />
        <span
          data-testid="market-overview-footer-meta"
          className="min-w-0 truncate text-[10px] uppercase tracking-widest text-[color:var(--wolfy-text-muted)]"
          title={details.join(' · ') || fallbackUpdatedAt || sourceLabel}
        >
          {compactDetails}
        </span>
      </div>
      {shouldShowInlineWarning(resolvedMeta) ? (
        <p className="text-[10px] leading-4 text-amber-200/75">{resolvedMeta?.warning}</p>
      ) : null}
    </div>
  );
};

export const MarketDataRow: React.FC<{
  item: MarketOverviewItem;
  neutralLabel: string;
  valueClassName?: string;
  valueDigitsBelowHundred?: number;
  suppressFreshnessBadge?: boolean;
}> = ({ item, neutralLabel, valueClassName, valueDigitsBelowHundred = 2, suppressFreshnessBadge = false }) => {
  const { language } = useI18n();
  const direction = item.riskDirection || 'neutral';
  const tone = getDirectionTone(direction);
  const displayLabel = resolveMarketOverviewDisplayLabel(item, language);
  const freshness = resolveFreshness(item);
  const itemDetails = metaText(item);
  const compactDetails = compactMetaText(item);
  const sparklineTone = direction === 'increasing'
    ? 'text-rose-400'
    : direction === 'decreasing'
      ? 'text-emerald-400'
      : 'text-[color:var(--wolfy-text-muted)]';

  return (
    <article
      data-testid="market-overview-data-row"
      data-row-layout="bounded-market-row"
      className="grid min-h-[48px] min-w-0 grid-cols-[minmax(0,1fr)_minmax(84px,0.65fr)_64px_minmax(88px,max-content)] items-center gap-x-2 overflow-hidden border-b border-[color:var(--wolfy-border-subtle)] py-2 last:border-b-0 max-[640px]:grid-cols-[minmax(0,1fr)_minmax(82px,max-content)] max-[640px]:gap-y-0.5"
    >
      <div className="col-start-1 min-w-0 max-[640px]:row-start-1">
        <div className="flex min-w-0 items-center gap-2">
          <span className={cn('size-1.5 shrink-0 rounded-full bg-current shadow-[0_0_12px_currentColor]', tone)} aria-hidden="true" />
          <p className="min-w-0 truncate text-xs font-semibold text-[color:var(--wolfy-text-secondary)]">{displayLabel.primary}</p>
        </div>
        <div className="mt-0.5 flex min-w-0 items-center gap-1.5 pl-3.5">
          {displayLabel.secondary ? (
            <span className="min-w-0 truncate font-mono text-[10px] font-semibold uppercase text-[color:var(--wolfy-text-muted)]">{displayLabel.secondary}</span>
          ) : null}
        </div>
      </div>
      {((!suppressFreshnessBadge && item.freshness) || compactDetails || item.hoverDetails?.length) ? (
        <div
          data-testid="market-overview-quote-metadata"
          data-metadata-position="middle-left"
          title={metadataTitle(itemDetails, item.warning, item.hoverDetails)}
          className="col-start-2 flex min-w-0 max-w-full items-center gap-x-1.5 overflow-hidden whitespace-nowrap text-[9px] text-[color:var(--wolfy-text-muted)] max-[640px]:col-start-1 max-[640px]:row-start-2 max-[640px]:pl-3.5"
        >
          {!suppressFreshnessBadge ? <DataFreshnessBadge freshness={item.freshness} status={freshness} className="shrink-0 px-1.5 text-[9px]" /> : null}
          {compactDetails ? <span className="min-w-0 overflow-hidden text-ellipsis leading-4">{compactDetails}</span> : null}
        </div>
      ) : null}
      <div data-testid="market-overview-dense-quote-sparkline" className="col-start-3 w-[64px] shrink-0 self-center max-[640px]:hidden">
        <MarketOverviewSparkline values={item.trend} tone={sparklineTone} className="h-7" />
      </div>
      <div data-testid="market-overview-quote-value" className="col-start-4 row-start-1 min-w-[88px] text-right font-mono tabular-nums max-[640px]:col-start-2">
        <p className={cn('truncate text-base font-semibold leading-none text-[color:var(--wolfy-text-primary)]', valueClassName)}>{formatMetricValue(item, valueDigitsBelowHundred)}</p>
        <p className={cn('mt-1 truncate text-[11px] font-bold leading-none', tone)}>
          {formatChangeSummary(item, neutralLabel)}
        </p>
      </div>
      <div
        data-testid="market-overview-quote-change"
        className={cn('sr-only text-right font-mono', tone)}
      >
        {formatChangeSummary(item, neutralLabel)}
      </div>
    </article>
  );
};

export const MarketOverviewDataRow = MarketDataRow;

export const MarketOverviewDenseQuoteItem: React.FC<{
  item: MarketOverviewItem;
  neutralLabel: string;
  valueDigitsBelowHundred?: number;
  suppressFreshnessBadge?: boolean;
}> = ({ item, neutralLabel, valueDigitsBelowHundred = 2, suppressFreshnessBadge = false }) => {
  const { language } = useI18n();
  const direction = item.riskDirection || 'neutral';
  const tone = getDirectionTone(direction);
  const displayLabel = resolveMarketOverviewDisplayLabel(item, language);
  const freshness = resolveFreshness(item);
  const itemDetails = metaText(item);
  const compactDetails = compactMetaText(item);
  const sparklineTone = direction === 'increasing'
    ? 'text-rose-400'
    : direction === 'decreasing'
      ? 'text-emerald-400'
      : 'text-[color:var(--wolfy-text-muted)]';

  return (
    <article
      data-testid="market-overview-dense-quote-item"
      data-quote-item-layout="compact-grid"
      className="grid min-h-[44px] min-w-0 grid-cols-[minmax(96px,1fr)_minmax(104px,0.9fr)_76px_minmax(82px,max-content)_minmax(92px,max-content)] items-center gap-x-2 border-b border-[color:var(--wolfy-border-subtle)] p-1.5 last:border-b-0 max-[720px]:grid-cols-[minmax(0,1fr)_76px_minmax(82px,max-content)] max-[720px]:gap-y-0.5"
    >
      <div className="col-start-1 min-w-0 max-[720px]:row-start-1">
        <div className="flex min-w-0 items-center gap-2">
          <span className={cn('size-1.5 shrink-0 rounded-full bg-current shadow-[0_0_12px_currentColor]', tone)} aria-hidden="true" />
          <p className="min-w-0 truncate text-xs font-semibold text-[color:var(--wolfy-text-secondary)]">{displayLabel.primary}</p>
        </div>
        {displayLabel.secondary ? (
          <p className="mt-0.5 truncate pl-3.5 font-mono text-[10px] font-semibold uppercase text-[color:var(--wolfy-text-muted)]">{displayLabel.secondary}</p>
        ) : null}
      </div>

      <div
        data-testid="market-overview-quote-metadata"
        data-metadata-position="middle-left"
        title={metadataTitle(itemDetails, item.warning, item.hoverDetails)}
        className="col-start-2 flex min-w-0 max-w-full items-center gap-x-1.5 overflow-hidden whitespace-nowrap text-[9px] text-[color:var(--wolfy-text-muted)] max-[720px]:col-start-1 max-[720px]:row-start-2 max-[720px]:pl-3.5"
      >
        {!suppressFreshnessBadge ? <DataFreshnessBadge freshness={item.freshness} status={freshness} className="shrink-0 px-1.5 text-[9px]" /> : null}
        {compactDetails ? <span className="min-w-0 overflow-hidden text-ellipsis leading-4">{compactDetails}</span> : null}
      </div>

      <div data-testid="market-overview-dense-quote-sparkline" className="col-start-3 w-[76px] shrink-0 self-center max-[720px]:col-start-2 max-[720px]:row-span-2 max-[720px]:row-start-1">
        <MarketOverviewSparkline values={item.trend} tone={sparklineTone} className="h-7" />
      </div>

      <div data-testid="market-overview-quote-value" className="col-start-4 min-w-[82px] text-right font-mono tabular-nums max-[720px]:col-start-3 max-[720px]:row-start-1">
        <p className="truncate text-base font-semibold leading-none text-[color:var(--wolfy-text-primary)]">{formatMetricValue(item, valueDigitsBelowHundred)}</p>
      </div>
      <div
        data-testid="market-overview-quote-change"
        className={cn('col-start-5 min-w-[92px] text-right font-mono text-[11px] font-bold leading-none tabular-nums max-[720px]:col-start-3 max-[720px]:row-start-2', tone)}
      >
        {formatChangeSummary(item, neutralLabel)}
      </div>
    </article>
  );
};
