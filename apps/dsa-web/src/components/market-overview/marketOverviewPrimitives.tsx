import type React from 'react';
import { RefreshCcw } from 'lucide-react';
import { useI18n } from '../../contexts/UiLanguageContext';
import type { MarketDataFreshness, MarketDataMeta, MarketOverviewItem, MarketOverviewPanel } from '../../api/marketOverview';
import { cn } from '../../utils/cn';
import { formatMarketOverviewTimestamp } from './marketOverviewFormat';
import {
  formatChangeSummary,
  formatMetricValue,
  getDirectionTone,
} from './marketOverviewUtils';
import { resolveMarketOverviewDisplayLabel } from './marketOverviewLabels';

const FRESHNESS_LABELS: Record<MarketDataFreshness, string> = {
  live: '实时',
  delayed: '延迟',
  cached: '快照',
  stale: '旧数据',
  fallback: '备用',
  mock: '模拟',
  error: '异常',
};

const FRESHNESS_CLASSES: Record<MarketDataFreshness, string> = {
  live: 'border-emerald-300/30 bg-emerald-400/10 text-emerald-200',
  delayed: 'border-sky-300/25 bg-sky-400/10 text-sky-200',
  cached: 'border-white/15 bg-white/[0.06] text-white/65',
  stale: 'border-amber-300/30 bg-amber-400/10 text-amber-200',
  fallback: 'border-orange-300/30 bg-orange-400/10 text-orange-200',
  mock: 'border-fuchsia-300/30 bg-fuchsia-400/10 text-fuchsia-200',
  error: 'border-rose-300/35 bg-rose-400/10 text-rose-200',
};

export const MARKET_OVERVIEW_GHOST_CARD_CLASS = 'bg-white/[0.02] border border-white/5 rounded-xl backdrop-blur-md p-5 transition-all hover:border-white/10';
export const MARKET_OVERVIEW_CARD_TITLE_CLASS = 'text-[10px] font-bold uppercase tracking-widest text-white/40 mb-5 block';

function resolveFreshness(meta?: Partial<MarketDataMeta>): MarketDataFreshness {
  if (meta?.freshness) {
    return meta.freshness;
  }
  if (meta?.isFallback || meta?.source === 'fallback') {
    return 'fallback';
  }
  if (meta?.isStale) {
    return 'stale';
  }
  return 'cached';
}

export const DataFreshnessBadge: React.FC<{ freshness?: MarketDataFreshness; className?: string }> = ({ freshness, className }) => {
  const resolved = freshness || 'cached';
  return (
    <span
      data-testid={`data-freshness-badge-${resolved}`}
      className={cn('inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold leading-none', FRESHNESS_CLASSES[resolved], className)}
    >
      {FRESHNESS_LABELS[resolved]}
    </span>
  );
};

function metaText(meta?: Partial<MarketDataMeta>): string[] {
  const sourceLabel = meta?.sourceLabel || meta?.source;
  const parts = sourceLabel ? [sourceLabel] : [];
  const asOf = formatMarketOverviewTimestamp(meta?.asOf);
  const updatedAt = formatMarketOverviewTimestamp(meta?.updatedAt);
  if (asOf) {
    parts.push(`行情时间 ${asOf}`);
  }
  if (updatedAt) {
    parts.push(`更新 ${updatedAt}`);
  }
  return parts;
}

function metadataTitle(parts: string[], warning?: string | null, hoverDetails?: string[] | null): string | undefined {
  return [...parts, warning, ...(hoverDetails || [])].filter(Boolean).join(' · ') || undefined;
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
      className={cn('w-full overflow-visible', tone, className)}
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
  const freshness = resolveFreshness(resolvedMeta);

  return (
    <div className="mt-auto flex flex-col gap-2 border-t border-white/5 pt-3">
      <div className="flex flex-wrap items-center gap-2">
        <DataFreshnessBadge freshness={freshness} />
        <span className="text-[10px] uppercase tracking-widest text-white/34">
          {details.join(' · ') || fallbackUpdatedAt || sourceLabel}
        </span>
      </div>
      {resolvedMeta?.warning ? (
        <p className="text-[10px] leading-4 text-amber-200/75">{resolvedMeta.warning}</p>
      ) : null}
    </div>
  );
};

export const MarketOverviewDataRow: React.FC<{
  item: MarketOverviewItem;
  neutralLabel: string;
  valueClassName?: string;
  valueDigitsBelowHundred?: number;
}> = ({ item, neutralLabel, valueClassName, valueDigitsBelowHundred = 2 }) => {
  const direction = item.riskDirection || 'neutral';
  const tone = getDirectionTone(direction);
  const displayLabel = resolveMarketOverviewDisplayLabel(item);
  const freshness = resolveFreshness(item);
  const itemDetails = metaText(item);
  const sparklineTone = direction === 'increasing'
    ? 'text-rose-400'
    : direction === 'decreasing'
      ? 'text-emerald-400'
      : 'text-white/35';

  return (
    <article className="group grid min-h-12 grid-cols-[minmax(0,1fr)_92px_minmax(92px,max-content)] items-center gap-x-3 gap-y-1 border-b border-white/[0.045] py-2.5 last:border-b-0">
      <div className="col-start-1 row-start-1 flex min-w-0 items-start gap-2">
        <span className={cn('mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-current shadow-[0_0_12px_currentColor]', tone)} aria-hidden="true" />
        <div className="min-w-0">
          <p className="truncate text-[10px] font-semibold tracking-widest text-white/65">{displayLabel.primary}</p>
          {displayLabel.secondary ? (
            <p className="mt-0.5 truncate text-[9px] font-semibold uppercase tracking-widest text-white/25">{displayLabel.secondary}</p>
          ) : null}
        </div>
      </div>
      {(item.freshness || item.sourceLabel || item.warning || item.hoverDetails?.length) ? (
        <div
          data-testid="market-overview-quote-metadata"
          data-metadata-position="under-label"
          title={metadataTitle(itemDetails, item.warning, item.hoverDetails)}
          className="col-start-1 row-start-2 flex min-w-0 max-w-full items-center gap-x-2 overflow-hidden whitespace-nowrap pl-3.5 text-[9px] text-white/32"
        >
          <DataFreshnessBadge freshness={freshness} className="shrink-0 px-1.5 text-[9px]" />
          {itemDetails.length ? <span className="min-w-0 overflow-hidden text-ellipsis leading-4">{itemDetails.join(' · ')}</span> : null}
          {item.warning ? <span className="shrink-0 leading-4 text-amber-200/70">{item.warning}</span> : null}
          {item.hoverDetails?.map((detail, index) => (
            <span key={`${detail}-${index}`} className="shrink-0 leading-4 text-white/28">{detail}</span>
          ))}
        </div>
      ) : null}
      <div className="col-start-2 row-span-2 row-start-1 w-[92px] shrink-0 self-center">
        <MarketOverviewSparkline values={item.trend} tone={sparklineTone} className="h-8" />
      </div>
      <div data-testid="market-overview-quote-value" className="col-start-3 row-span-2 row-start-1 min-w-[92px] text-right font-mono tabular-nums">
        <p className={cn('truncate text-lg font-semibold leading-none text-white', valueClassName)}>{formatMetricValue(item, valueDigitsBelowHundred)}</p>
        <p className={cn('mt-1 truncate text-[11px] font-bold leading-none', tone)}>
          {formatChangeSummary(item, neutralLabel)}
        </p>
      </div>
    </article>
  );
};

export const MarketOverviewDenseQuoteItem: React.FC<{
  item: MarketOverviewItem;
  neutralLabel: string;
  valueDigitsBelowHundred?: number;
}> = ({ item, neutralLabel, valueDigitsBelowHundred = 2 }) => {
  const direction = item.riskDirection || 'neutral';
  const tone = getDirectionTone(direction);
  const displayLabel = resolveMarketOverviewDisplayLabel(item);
  const freshness = resolveFreshness(item);
  const itemDetails = metaText(item);
  const sparklineTone = direction === 'increasing'
    ? 'text-rose-400'
    : direction === 'decreasing'
      ? 'text-emerald-400'
      : 'text-white/35';

  return (
    <article
      data-testid="market-overview-dense-quote-item"
      data-quote-item-layout="compact-grid"
      className="grid min-w-0 grid-cols-[minmax(0,1fr)_92px_minmax(90px,max-content)] items-center gap-x-3 gap-y-1 rounded-lg border border-white/[0.055] bg-white/[0.025] px-3 py-2"
    >
      <div className="col-start-1 row-start-1 min-w-0">
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
        data-metadata-position="under-label"
        title={metadataTitle(itemDetails, item.warning, item.hoverDetails)}
        className="col-start-1 row-start-2 flex min-w-0 max-w-full items-center gap-x-2 overflow-hidden whitespace-nowrap pl-3.5 text-[9px] text-white/32"
      >
        <DataFreshnessBadge freshness={freshness} className="shrink-0 px-1.5 text-[9px]" />
        {itemDetails.length ? <span className="min-w-0 overflow-hidden text-ellipsis leading-4">{itemDetails.join(' · ')}</span> : null}
        {item.warning ? <span className="shrink-0 leading-4 text-amber-200/70">{item.warning}</span> : null}
        {item.hoverDetails?.map((detail, index) => (
          <span key={`${detail}-${index}`} className="shrink-0 leading-4 text-white/28">{detail}</span>
        ))}
      </div>

      <div data-testid="market-overview-dense-quote-sparkline" className="col-start-2 row-span-2 row-start-1 w-[92px] shrink-0 self-center">
        <MarketOverviewSparkline values={item.trend} tone={sparklineTone} className="h-8" />
      </div>

      <div data-testid="market-overview-quote-value" className="col-start-3 row-span-2 row-start-1 min-w-[90px] text-right font-mono tabular-nums">
        <p className="truncate text-base font-semibold leading-none text-white">{formatMetricValue(item, valueDigitsBelowHundred)}</p>
        <p className={cn('mt-1 truncate text-[11px] font-bold leading-none', tone)}>
          {formatChangeSummary(item, neutralLabel)}
        </p>
      </div>
    </article>
  );
};
