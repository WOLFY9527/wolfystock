import type React from 'react';

export type CoreMarketChartPoint = {
  date: string;
  label?: string | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close: number;
  volume?: number | null;
};

type CoreMarketChartTone = 'success' | 'warning' | 'error' | 'neutral';

type CoreMarketChartProps = {
  testId: string;
  chartKind: string;
  title: string;
  subtitle?: string;
  points: CoreMarketChartPoint[];
  language: 'zh' | 'en';
  statusLabel: string;
  statusTone?: CoreMarketChartTone;
  sourceLabel: string;
  freshnessLabel: string;
  rangeLabel: string;
  latestLabel?: string;
  changeLabel?: string;
  coverageLabel?: string;
  warningLabel?: string | null;
  emptyTitle: string;
  emptyDetail: string;
  showVolume?: boolean;
  compact?: boolean;
};

const WIDTH = 720;
const HEIGHT = 300;
const COMPACT_HEIGHT = 210;
const PRICE_TOP = 36;
const PRICE_BOTTOM = 188;
const COMPACT_PRICE_BOTTOM = 148;
const VOLUME_TOP = 214;
const VOLUME_BOTTOM = 276;
const LEFT = 54;
const RIGHT = 20;

function finiteNumber(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function formatNumber(value: number | null | undefined, language: 'zh' | 'en'): string {
  const numeric = finiteNumber(value);
  if (numeric == null) return '--';
  return new Intl.NumberFormat(language === 'en' ? 'en-US' : 'zh-CN', {
    maximumFractionDigits: Math.abs(numeric) >= 100 ? 2 : 3,
  }).format(numeric);
}

function formatCompactNumber(value: number | null | undefined, language: 'zh' | 'en'): string {
  const numeric = finiteNumber(value);
  if (numeric == null) return '--';
  const sign = numeric < 0 ? '-' : '';
  const abs = Math.abs(numeric);
  if (language === 'zh') {
    if (abs >= 100_000_000) return `${sign}${(abs / 100_000_000).toFixed(abs >= 1_000_000_000 ? 1 : 2)}亿`;
    if (abs >= 10_000) return `${sign}${(abs / 10_000).toFixed(abs >= 100_000 ? 1 : 2)}万`;
  }
  if (abs >= 1_000_000_000) return `${sign}${(abs / 1_000_000_000).toFixed(2)}b`;
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(2)}m`;
  if (abs >= 1_000) return `${sign}${(abs / 1_000).toFixed(1)}k`;
  return `${sign}${abs.toFixed(abs >= 100 ? 0 : 1)}`;
}

function formatDateTick(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value || '--';
  return `${match[2]}/${match[3]}`;
}

function toneClass(tone: CoreMarketChartTone): string {
  if (tone === 'success') return 'border-emerald-400/24 bg-emerald-400/10 text-emerald-100';
  if (tone === 'warning') return 'border-amber-300/24 bg-amber-300/10 text-amber-100';
  if (tone === 'error') return 'border-rose-300/24 bg-rose-300/10 text-rose-100';
  return 'border-white/[0.10] bg-white/[0.04] text-white/72';
}

function buildLinePath(points: CoreMarketChartPoint[], min: number, max: number, priceBottom: number): string {
  const range = max - min || 1;
  const innerWidth = WIDTH - LEFT - RIGHT;
  return points.map((point, index) => {
    const x = LEFT + (innerWidth * index) / Math.max(points.length - 1, 1);
    const y = PRICE_TOP + (priceBottom - PRICE_TOP) - ((point.close - min) / range) * (priceBottom - PRICE_TOP);
    return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join(' ');
}

function pointX(index: number, total: number): number {
  return LEFT + ((WIDTH - LEFT - RIGHT) * index) / Math.max(total - 1, 1);
}

function pointY(value: number, min: number, max: number, priceBottom: number): number {
  const range = max - min || 1;
  return PRICE_TOP + (priceBottom - PRICE_TOP) - ((value - min) / range) * (priceBottom - PRICE_TOP);
}

export const CoreMarketChart: React.FC<CoreMarketChartProps> = ({
  testId,
  chartKind,
  title,
  subtitle,
  points,
  language,
  statusLabel,
  statusTone = 'neutral',
  sourceLabel,
  freshnessLabel,
  rangeLabel,
  latestLabel,
  changeLabel,
  coverageLabel,
  warningLabel,
  emptyTitle,
  emptyDetail,
  showVolume = true,
  compact = false,
}) => {
  const usablePoints = points
    .filter((point) => finiteNumber(point.close) != null)
    .slice(compact ? -32 : -110);
  const hasChart = usablePoints.length >= 2;
  const hasVolume = showVolume && usablePoints.some((point) => (point.volume ?? 0) > 0);
  const priceBottom = compact || !hasVolume ? COMPACT_PRICE_BOTTOM : PRICE_BOTTOM;
  const svgHeight = compact || !hasVolume ? COMPACT_HEIGHT : HEIGHT;
  const lowsAndHighs = usablePoints.flatMap((point) => [
    finiteNumber(point.low) ?? point.close,
    finiteNumber(point.high) ?? point.close,
    point.close,
  ]);
  const minPrice = Math.min(...lowsAndHighs);
  const maxPrice = Math.max(...lowsAndHighs);
  const linePath = hasChart ? buildLinePath(usablePoints, minPrice, maxPrice, priceBottom) : '';
  const maxVolume = Math.max(...usablePoints.map((point) => point.volume ?? 0), 1);
  const first = usablePoints[0];
  const last = usablePoints.at(-1);
  const ariaSummary = hasChart
    ? `${title}: ${usablePoints.length} ${language === 'en' ? 'bars' : '根'} ${first?.date || ''} ${last?.date || ''}`
    : `${title}: ${emptyTitle}`;
  const yTicks = [maxPrice, (maxPrice + minPrice) / 2, minPrice];
  const xTicks = hasChart
    ? [0, Math.floor((usablePoints.length - 1) / 2), usablePoints.length - 1]
    : [];

  return (
    <section
      className={[
        'mt-4 overflow-hidden rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-muted)] shadow-[var(--wolfy-shadow-panel)]',
        compact ? 'p-3' : 'p-4',
      ].join(' ')}
      data-testid={testId}
      data-chart-kind={chartKind}
      data-point-count={usablePoints.length}
      data-has-volume={hasVolume ? 'true' : 'false'}
    >
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[color:var(--wolfy-text-muted)]">
            {compact ? (language === 'en' ? 'Market trend' : '市场趋势') : (language === 'en' ? 'Price trend' : '价格趋势')}
          </p>
          <h3 className={compact ? 'mt-1 text-sm font-semibold text-[color:var(--wolfy-text-primary)]' : 'mt-1 text-base font-semibold text-[color:var(--wolfy-text-primary)]'}>
            {title}
          </h3>
          {subtitle ? <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">{subtitle}</p> : null}
        </div>
        <div className="flex min-w-0 flex-wrap justify-end gap-1.5 text-[11px]">
          <span className={`rounded-full border px-2 py-1 font-medium ${toneClass(statusTone)}`}>{statusLabel}</span>
          {warningLabel ? <span className={`rounded-full border px-2 py-1 font-medium ${toneClass('warning')}`}>{warningLabel}</span> : null}
          <span className="rounded-full border border-white/[0.10] bg-white/[0.035] px-2 py-1 text-[color:var(--wolfy-text-secondary)]">{freshnessLabel}</span>
          {coverageLabel ? <span className="rounded-full border border-white/[0.10] bg-white/[0.035] px-2 py-1 text-[color:var(--wolfy-text-secondary)]">{coverageLabel}</span> : null}
        </div>
      </div>

      {hasChart ? (
        <div className="mt-3">
          <svg
            role="img"
            aria-label={ariaSummary}
            viewBox={`0 0 ${WIDTH} ${svgHeight}`}
            className={compact ? 'h-[210px] w-full overflow-visible' : 'h-[300px] w-full overflow-visible'}
            preserveAspectRatio="none"
            data-testid="core-market-chart-svg"
          >
            <title>{ariaSummary}</title>
            <defs>
              <linearGradient id={`${testId}-price-fill`} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="var(--wolfy-accent)" stopOpacity="0.22" />
                <stop offset="100%" stopColor="var(--wolfy-accent)" stopOpacity="0.01" />
              </linearGradient>
            </defs>
            {yTicks.map((value) => {
              const y = pointY(value, minPrice, maxPrice, priceBottom);
              return (
                <g key={`tick-${value}`}>
                  <line x1={LEFT} y1={y} x2={WIDTH - RIGHT} y2={y} stroke="var(--wolfy-border-subtle)" strokeOpacity="0.65" strokeWidth="1" />
                  <text x={LEFT - 10} y={y + 4} textAnchor="end" fill="var(--wolfy-text-muted)" fontSize="11">
                    {formatNumber(value, language)}
                  </text>
                </g>
              );
            })}
            <path
              d={`${linePath} L ${WIDTH - RIGHT} ${priceBottom} L ${LEFT} ${priceBottom} Z`}
              fill={`url(#${testId}-price-fill)`}
              opacity="0.95"
            />
            {usablePoints.map((point, index) => {
              const high = finiteNumber(point.high) ?? point.close;
              const low = finiteNumber(point.low) ?? point.close;
              const open = finiteNumber(point.open);
              const x = pointX(index, usablePoints.length);
              const highY = pointY(high, minPrice, maxPrice, priceBottom);
              const lowY = pointY(low, minPrice, maxPrice, priceBottom);
              const closeY = pointY(point.close, minPrice, maxPrice, priceBottom);
              const openY = open == null ? closeY : pointY(open, minPrice, maxPrice, priceBottom);
              const up = open == null ? index === 0 || point.close >= usablePoints[index - 1]?.close : point.close >= open;
              const color = up ? '#34d399' : '#fb7185';
              return (
                <g key={`${point.date}-${index}`} opacity={compact ? 0.28 : 0.46}>
                  <line x1={x} y1={highY} x2={x} y2={lowY} stroke={color} strokeWidth={compact ? 1 : 1.4} vectorEffect="non-scaling-stroke" />
                  {!compact ? <line x1={x - 4} y1={openY} x2={x + 4} y2={closeY} stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" /> : null}
                </g>
              );
            })}
            <path d={linePath} fill="none" stroke="var(--wolfy-accent)" strokeWidth={compact ? 2.4 : 3} vectorEffect="non-scaling-stroke" />
            {xTicks.map((index) => {
              const point = usablePoints[index];
              if (!point) return null;
              const x = pointX(index, usablePoints.length);
              return (
                <text key={`x-${index}`} x={x} y={priceBottom + 24} textAnchor={index === 0 ? 'start' : index === usablePoints.length - 1 ? 'end' : 'middle'} fill="var(--wolfy-text-muted)" fontSize="11">
                  {formatDateTick(point.label || point.date)}
                </text>
              );
            })}
            {hasVolume ? (
              <g data-testid="core-market-volume-bars">
                <line x1={LEFT} y1={VOLUME_TOP} x2={WIDTH - RIGHT} y2={VOLUME_TOP} stroke="var(--wolfy-border-subtle)" strokeOpacity="0.55" strokeWidth="1" />
                <text x={LEFT - 10} y={VOLUME_TOP + 4} textAnchor="end" fill="var(--wolfy-text-muted)" fontSize="11">
                  {language === 'en' ? 'Volume' : '成交量'}
                </text>
                {usablePoints.map((point, index) => {
                  const volume = Math.max(point.volume ?? 0, 0);
                  const x = LEFT + ((WIDTH - LEFT - RIGHT) * index) / usablePoints.length;
                  const barWidth = Math.max((WIDTH - LEFT - RIGHT) / usablePoints.length - 2, 1);
                  const barHeight = volume > 0 ? Math.max((volume / maxVolume) * (VOLUME_BOTTOM - VOLUME_TOP), 2) : 0;
                  const previousClose = usablePoints[index - 1]?.close ?? point.open ?? point.close;
                  const up = point.close >= previousClose;
                  return (
                    <rect
                      key={`vol-${point.date}-${index}`}
                      x={x}
                      y={VOLUME_BOTTOM - barHeight}
                      width={barWidth}
                      height={barHeight}
                      rx="1.5"
                      fill={up ? '#34d399' : '#fb7185'}
                      opacity="0.42"
                    />
                  );
                })}
              </g>
            ) : null}
          </svg>
          <div className="mt-3 grid gap-2 text-xs text-[color:var(--wolfy-text-secondary)] sm:grid-cols-3">
            <div>
              <span className="block text-[10px] uppercase tracking-[0.08em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Range' : '区间'}</span>
              <span className="font-medium text-[color:var(--wolfy-text-primary)]">{rangeLabel}</span>
            </div>
            <div>
              <span className="block text-[10px] uppercase tracking-[0.08em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Latest' : '最新'}</span>
              <span className="font-medium text-[color:var(--wolfy-text-primary)]">{latestLabel || formatNumber(last?.close, language)}</span>
            </div>
            <div>
              <span className="block text-[10px] uppercase tracking-[0.08em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Source' : '来源'}</span>
              <span className="font-medium text-[color:var(--wolfy-text-primary)]">{sourceLabel}</span>
            </div>
          </div>
          {hasVolume ? (
            <p className="mt-2 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
              {language === 'en'
                ? `Volume bars use only returned price and volume rows. Latest volume ${formatCompactNumber(last?.volume, language)}.`
                : `成交量柱仅使用接口返回的价格与成交量记录。最新成交量 ${formatCompactNumber(last?.volume, language)}。`}
            </p>
          ) : null}
          {changeLabel ? <p className="mt-1 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">{changeLabel}</p> : null}
        </div>
      ) : (
        <div
          className="mt-4 rounded-md border border-dashed border-[color:var(--wolfy-border-subtle)] bg-black/10 p-4"
          data-testid={`${testId}-empty-state`}
        >
          <p className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{emptyTitle}</p>
          <p className="mt-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{emptyDetail}</p>
          <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
            <span className={`rounded-full border px-2 py-1 font-medium ${toneClass(statusTone)}`}>{statusLabel}</span>
            <span className="rounded-full border border-white/[0.10] bg-white/[0.035] px-2 py-1 text-[color:var(--wolfy-text-secondary)]">{freshnessLabel}</span>
            <span className="rounded-full border border-white/[0.10] bg-white/[0.035] px-2 py-1 text-[color:var(--wolfy-text-secondary)]">{sourceLabel}</span>
          </div>
        </div>
      )}
    </section>
  );
};
