import type React from 'react';
import { RefreshCcw } from 'lucide-react';
import { useI18n } from '../../contexts/UiLanguageContext';
import type { MarketDataFreshness, MarketDataMeta, MarketOverviewItem, MarketOverviewPanel, MarketProviderHealthStatus } from '../../api/marketOverview';
import { cn } from '../../utils/cn';
import { GlassCard } from '../common';
import { formatMarketOverviewTimestamp } from './marketOverviewFormat';
import {
  formatChangeSummary,
  formatMetricValue,
  getDirectionTone,
} from './marketOverviewUtils';
import { resolveMarketOverviewDisplayLabel } from './marketOverviewLabels';

const FRESHNESS_LABELS: Record<MarketDataFreshness, string> = {
  live: '实时',
  delayed: '缓存',
  cached: '缓存',
  stale: '过期',
  fallback: '备用',
  mock: '备用',
  error: '数据异常',
};

const STATUS_LABELS: Record<MarketProviderHealthStatus, string> = {
  live: '实时',
  cache: '缓存',
  stale: '过期',
  fallback: '备用',
  partial: '部分数据',
  unavailable: '暂不可用',
  error: '数据异常',
  refreshing: '刷新中',
};

const FRESHNESS_CLASSES: Record<MarketProviderHealthStatus, string> = {
  live: 'border-emerald-300/30 bg-emerald-400/10 text-emerald-200',
  cache: 'border-white/15 bg-white/[0.06] text-white/65',
  stale: 'border-amber-300/30 bg-amber-400/10 text-amber-200',
  fallback: 'border-orange-300/30 bg-orange-400/10 text-orange-200',
  partial: 'border-cyan-300/25 bg-cyan-400/10 text-cyan-200',
  unavailable: 'border-white/12 bg-white/[0.04] text-white/48',
  error: 'border-rose-300/35 bg-rose-400/10 text-rose-200',
  refreshing: 'border-sky-300/25 bg-sky-400/10 text-sky-200',
};

export const MARKET_OVERVIEW_GHOST_CARD_CLASS = 'bg-white/[0.02] border border-white/5 rounded-xl backdrop-blur-md p-5 transition-all hover:border-white/10';
export const MARKET_OVERVIEW_CARD_TITLE_CLASS = 'text-[10px] font-bold uppercase tracking-widest text-white/40 mb-5 block';
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
  <GlassCard
    as="section"
    data-testid={testId}
    data-market-card-size={size}
    data-rail-card={railKey}
    className={cn(
      MARKET_OVERVIEW_GHOST_CARD_CLASS,
      MARKET_OVERVIEW_CARD_SIZE_CLASS[size],
      'flex min-w-0 flex-col overflow-hidden',
      className,
    )}
  >
    {title || eyebrow || subtitle ? (
      <div className="mb-3 min-w-0 shrink-0">
        {eyebrow ? <p className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">{eyebrow}</p> : null}
        {title ? <h2 className="mt-1 truncate text-sm font-semibold text-white/84">{title}</h2> : null}
        {subtitle ? <p className="mt-1 truncate text-[11px] leading-4 text-white/42">{subtitle}</p> : null}
      </div>
    ) : null}
    <div className="min-h-0 min-w-0 flex-1 overflow-hidden">{children}</div>
    {footer ? <div className="mt-3 shrink-0 border-t border-white/5 pt-2 text-[10px] leading-4 text-white/34">{footer}</div> : null}
  </GlassCard>
);

function resolveProviderStatus(meta?: Partial<MarketDataMeta>): MarketProviderHealthStatus {
  if (meta?.providerHealth?.status) {
    return meta.providerHealth.status;
  }
  if (meta?.isRefreshing) {
    return 'refreshing';
  }
  if (meta?.source === 'unavailable') {
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
  if (freshness === 'live') {
    return 'live';
  }
  if (freshness === 'stale') {
    return 'stale';
  }
  if (freshness === 'fallback' || freshness === 'mock') {
    return 'fallback';
  }
  if (freshness === 'error') {
    return 'error';
  }
  return 'cache';
}

export const DataFreshnessBadge: React.FC<{ freshness?: MarketDataFreshness; status?: MarketProviderHealthStatus; className?: string }> = ({ freshness, status, className }) => {
  const resolved = status || legacyFreshnessToStatus(freshness);
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
  const sourceLabel = meta?.sourceLabel || meta?.source;
  const parts = sourceLabel ? [sourceLabel] : [];
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

function metadataTitle(parts: string[], warning?: string | null, hoverDetails?: string[] | null): string | undefined {
  return [...parts, warning, ...(hoverDetails || [])].filter(Boolean).join(' · ') || undefined;
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
  tone = 'text-white/35',
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
    className="p-1.5 text-white/30 hover:text-white hover:bg-white/10 rounded-lg transition-all cursor-pointer disabled:cursor-wait disabled:text-white/45"
  >
    <RefreshCcw className={cn('h-4 w-4', refreshing ? 'animate-spin' : '')} aria-hidden="true" />
  </button>
);

export const MarketOverviewPanelFooter: React.FC<{ panel?: MarketOverviewPanel; sourceLabel?: string; meta?: Partial<MarketDataMeta> }> = ({ panel, sourceLabel, meta }) => {
  const { t } = useI18n();
  const resolvedMeta = meta || panel;
  const fallbackUpdatedAt = panel?.lastRefreshAt
    ? t('marketOverviewPage.footer.lastRefresh', {
        timestamp: formatMarketOverviewTimestamp(panel.lastRefreshAt) || t('marketOverviewPage.footer.pending'),
      })
    : '';
  const details = metaText(resolvedMeta);
  if (sourceLabel && !details.length) {
    details.push(sourceLabel);
  }
  if (resolvedMeta?.isRefreshing) {
    details.push(t('marketOverviewPage.footer.refreshingSnapshot'));
  }
  const compactDetails = compactMetaText(resolvedMeta) || fallbackUpdatedAt || sourceLabel || '';
  const freshness = resolveFreshness(resolvedMeta);

  return (
    <div className="mt-auto min-w-0 border-t border-white/5 pt-3">
      <div className="flex min-w-0 items-center gap-2 overflow-hidden whitespace-nowrap">
        <DataFreshnessBadge status={freshness} />
        <span
          data-testid="market-overview-footer-meta"
          className="min-w-0 truncate text-[10px] uppercase tracking-widest text-white/34"
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
}> = ({ item, neutralLabel, valueClassName, valueDigitsBelowHundred = 2 }) => {
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
      : 'text-white/35';

  return (
    <article
      data-testid="market-overview-data-row"
      data-row-layout="bounded-market-row"
      className="grid min-h-[48px] min-w-0 grid-cols-[minmax(0,1fr)_minmax(84px,0.65fr)_64px_minmax(88px,max-content)] items-center gap-x-2 overflow-hidden border-b border-white/[0.045] py-2 last:border-b-0 max-[640px]:grid-cols-[minmax(0,1fr)_minmax(82px,max-content)] max-[640px]:gap-y-0.5"
    >
      <div className="col-start-1 min-w-0 max-[640px]:row-start-1">
        <div className="flex min-w-0 items-center gap-2">
          <span className={cn('size-1.5 shrink-0 rounded-full bg-current shadow-[0_0_12px_currentColor]', tone)} aria-hidden="true" />
          <p className="min-w-0 truncate text-xs font-semibold text-white/78">{displayLabel.primary}</p>
        </div>
        <div className="mt-0.5 flex min-w-0 items-center gap-1.5 pl-3.5">
          {displayLabel.secondary ? (
            <span className="min-w-0 truncate font-mono text-[10px] font-semibold uppercase text-white/32">{displayLabel.secondary}</span>
          ) : null}
        </div>
      </div>
      {(item.freshness || item.sourceLabel || item.warning || item.hoverDetails?.length) ? (
        <div
          data-testid="market-overview-quote-metadata"
          data-metadata-position="middle-left"
          title={metadataTitle(itemDetails, item.warning, item.hoverDetails)}
          className="col-start-2 flex min-w-0 max-w-full items-center gap-x-1.5 overflow-hidden whitespace-nowrap text-[9px] text-white/32 max-[640px]:col-start-1 max-[640px]:row-start-2 max-[640px]:pl-3.5"
        >
          <DataFreshnessBadge status={freshness} className="shrink-0 px-1.5 text-[9px]" />
          {compactDetails ? <span className="min-w-0 overflow-hidden text-ellipsis leading-4">{compactDetails}</span> : null}
          {item.hoverDetails?.map((detail, index) => (
            <span key={`${detail}-${index}`} className="shrink-0 leading-4 text-white/28">{detail}</span>
          ))}
        </div>
      ) : null}
      <div data-testid="market-overview-dense-quote-sparkline" className="col-start-3 w-[64px] shrink-0 self-center max-[640px]:hidden">
        <MarketOverviewSparkline values={item.trend} tone={sparklineTone} className="h-7" />
      </div>
      <div data-testid="market-overview-quote-value" className="col-start-4 row-start-1 min-w-[88px] text-right font-mono tabular-nums max-[640px]:col-start-2">
        <p className={cn('truncate text-base font-semibold leading-none text-white', valueClassName)}>{formatMetricValue(item, valueDigitsBelowHundred)}</p>
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
}> = ({ item, neutralLabel, valueDigitsBelowHundred = 2 }) => {
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
      : 'text-white/35';

  return (
    <article
      data-testid="market-overview-dense-quote-item"
      data-quote-item-layout="compact-grid"
      className="grid min-h-[44px] min-w-0 grid-cols-[minmax(96px,1fr)_minmax(104px,0.9fr)_76px_minmax(82px,max-content)_minmax(92px,max-content)] items-center gap-x-2 border-b border-white/[0.045] px-1.5 py-1.5 last:border-b-0 max-[720px]:grid-cols-[minmax(0,1fr)_76px_minmax(82px,max-content)] max-[720px]:gap-y-0.5"
    >
      <div className="col-start-1 min-w-0 max-[720px]:row-start-1">
        <div className="flex min-w-0 items-center gap-2">
          <span className={cn('size-1.5 shrink-0 rounded-full bg-current shadow-[0_0_12px_currentColor]', tone)} aria-hidden="true" />
          <p className="min-w-0 truncate text-xs font-semibold text-white/78">{displayLabel.primary}</p>
        </div>
        {displayLabel.secondary ? (
          <p className="mt-0.5 truncate pl-3.5 font-mono text-[10px] font-semibold uppercase text-white/32">{displayLabel.secondary}</p>
        ) : null}
      </div>

      <div
        data-testid="market-overview-quote-metadata"
        data-metadata-position="middle-left"
        title={metadataTitle(itemDetails, item.warning, item.hoverDetails)}
        className="col-start-2 flex min-w-0 max-w-full items-center gap-x-1.5 overflow-hidden whitespace-nowrap text-[9px] text-white/32 max-[720px]:col-start-1 max-[720px]:row-start-2 max-[720px]:pl-3.5"
      >
        <DataFreshnessBadge status={freshness} className="shrink-0 px-1.5 text-[9px]" />
        {compactDetails ? <span className="min-w-0 overflow-hidden text-ellipsis leading-4">{compactDetails}</span> : null}
        {item.hoverDetails?.map((detail, index) => (
          <span key={`${detail}-${index}`} className="shrink-0 leading-4 text-white/28">{detail}</span>
        ))}
      </div>

      <div data-testid="market-overview-dense-quote-sparkline" className="col-start-3 w-[76px] shrink-0 self-center max-[720px]:col-start-2 max-[720px]:row-span-2 max-[720px]:row-start-1">
        <MarketOverviewSparkline values={item.trend} tone={sparklineTone} className="h-7" />
      </div>

      <div data-testid="market-overview-quote-value" className="col-start-4 min-w-[82px] text-right font-mono tabular-nums max-[720px]:col-start-3 max-[720px]:row-start-1">
        <p className="truncate text-base font-semibold leading-none text-white">{formatMetricValue(item, valueDigitsBelowHundred)}</p>
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
