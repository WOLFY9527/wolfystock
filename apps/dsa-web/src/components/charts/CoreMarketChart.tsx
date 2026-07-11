import type React from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { BarChart, CandlestickChart, LineChart } from 'echarts/charts';
import type { BarSeriesOption, CandlestickSeriesOption, LineSeriesOption } from 'echarts/charts';
import {
  DataZoomComponent,
  GridComponent,
  TooltipComponent,
} from 'echarts/components';
import type {
  DataZoomComponentOption,
  GridComponentOption,
  TooltipComponentOption,
} from 'echarts/components';
import * as echarts from 'echarts/core';
import type { ComposeOption, ECharts, SetOptionOpts } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion';
import {
  resolveMotionDurationMs,
  shouldEnableNonEssentialMotion,
} from '../../utils/motionPreference';
import {
  CHART_GRAPHIC_ROLE,
  buildCoreMarketChartAccessibleSemantics,
} from './chartAccessibility';

echarts.use([
  CandlestickChart,
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  CanvasRenderer,
]);

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
type CoreMarketChartRange = '1D' | '1W' | '1M' | '3M' | 'ALL';
type CoreMarketRenderMode = 'candlestick' | 'line';

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

type ChartPoint = {
  date: string;
  label?: string | null;
  open?: number;
  high?: number;
  low?: number;
  close: number;
  volume?: number;
  ma5?: number;
  ma20?: number;
};

type CoreMarketChartOption = ComposeOption<
  | CandlestickSeriesOption
  | LineSeriesOption
  | BarSeriesOption
  | GridComponentOption
  | TooltipComponentOption
  | DataZoomComponentOption
>;

const RANGE_OPTIONS: Array<{ key: CoreMarketChartRange; labelZh: string; labelEn: string; bars?: number }> = [
  { key: '1D', labelZh: '1D', labelEn: '1D', bars: 1 },
  { key: '1W', labelZh: '1W', labelEn: '1W', bars: 5 },
  { key: '1M', labelZh: '1M', labelEn: '1M', bars: 22 },
  { key: '3M', labelZh: '3M', labelEn: '3M', bars: 66 },
  { key: 'ALL', labelZh: '全部', labelEn: 'All' },
];

const PRICE_COLORS = {
  up: '#2FC48D',
  down: '#E76576',
  ma5: '#38BDF8',
  ma20: '#F59E0B',
  line: '#8BA4FF',
};

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

function formatDateLabel(value: string | null | undefined): string {
  if (!value) return '--';
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  return `${match[1]}-${match[2]}-${match[3]}`;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function toneClass(tone: CoreMarketChartTone): string {
  if (tone === 'success') return 'border-[color:var(--state-success-border)] bg-[var(--state-success-bg)] text-[color:var(--state-success-text)]';
  if (tone === 'warning') return 'border-amber-300/24 bg-amber-300/10 text-amber-100';
  if (tone === 'error') return 'border-[color:var(--state-danger-border)] bg-[var(--state-danger-bg)] text-[color:var(--state-danger-text)]';
  return 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] text-[color:var(--wolfy-text-secondary)]';
}

function movingAverage(values: number[], index: number, length: number): number | undefined {
  if (index < length - 1) return undefined;
  const slice = values.slice(index - length + 1, index + 1);
  return Number((slice.reduce((sum, value) => sum + value, 0) / length).toFixed(2));
}

function normalizePoints(points: CoreMarketChartPoint[], compact: boolean): ChartPoint[] {
  const normalized = points
    .filter((point) => finiteNumber(point.close) != null && point.date)
    .map((point) => {
      const open = finiteNumber(point.open);
      const high = finiteNumber(point.high);
      const low = finiteNumber(point.low);
      const volume = finiteNumber(point.volume);
      return {
        date: String(point.date),
        label: point.label,
        close: Number(point.close),
        open: open ?? undefined,
        high: high ?? undefined,
        low: low ?? undefined,
        volume: volume ?? undefined,
      };
    })
    .slice(compact ? -64 : -240);
  const closes = normalized.map((point) => point.close);
  return normalized.map((point, index) => ({
    ...point,
    ma5: movingAverage(closes, index, 5),
    ma20: movingAverage(closes, index, 20),
  }));
}

function hasCompleteOhlc(points: ChartPoint[]): boolean {
  return points.length > 0 && points.every((point) => (
    finiteNumber(point.open) != null
    && finiteNumber(point.high) != null
    && finiteNumber(point.low) != null
    && finiteNumber(point.close) != null
  ));
}

function visibleRangePoints(points: ChartPoint[], range: CoreMarketChartRange): ChartPoint[] {
  const option = RANGE_OPTIONS.find((item) => item.key === range);
  if (!option?.bars) return points;
  return points.slice(-option.bars);
}

function buildTooltip(point: ChartPoint, language: 'zh' | 'en', enabledOverlays: string[], renderMode: CoreMarketRenderMode): string {
  const labels = language === 'en'
    ? { date: 'Date', open: 'Open', high: 'High', low: 'Low', close: 'Close', volume: 'Volume' }
    : { date: '日期', open: '开盘', high: '最高', low: '最低', close: '收盘', volume: '成交量' };
  const ohlcRows = renderMode === 'candlestick'
    ? `
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.52);">${labels.open}</span><strong>${formatNumber(point.open, language)}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.52);">${labels.high}</span><strong>${formatNumber(point.high, language)}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.52);">${labels.low}</span><strong>${formatNumber(point.low, language)}</strong></div>
    `
    : '';
  const overlayRows = enabledOverlays
    .map((label) => {
      const value = label === 'MA5' ? point.ma5 : point.ma20;
      return finiteNumber(value) == null
        ? ''
        : `<div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.52);">${label}</span><strong>${formatNumber(value, language)}</strong></div>`;
    })
    .join('');
  return `
    <div style="min-width:190px;padding:8px 10px;font-size:11px;line-height:1.65;color:rgba(248,250,252,.86);">
      <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:5px;"><span style="color:rgba(248,250,252,.52);">${labels.date}</span><strong>${escapeHtml(formatDateLabel(point.label || point.date))}</strong></div>
      ${ohlcRows}
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.52);">${labels.close}</span><strong>${formatNumber(point.close, language)}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.52);">${labels.volume}</span><strong>${formatCompactNumber(point.volume, language)}</strong></div>
      ${overlayRows}
    </div>
  `;
}

function buildChartOption({
  points,
  language,
  hasVolume,
  enabledOverlays,
  renderMode,
  compact,
  reducedMotion,
}: {
  points: ChartPoint[];
  language: 'zh' | 'en';
  hasVolume: boolean;
  enabledOverlays: string[];
  renderMode: CoreMarketRenderMode;
  compact: boolean;
  reducedMotion: boolean;
}): CoreMarketChartOption {
  // Series animation stays off: DESIGN warns against chart motion that obscures comparison.
  // Tooltip/axis pointer motion is preference-aware only.
  const enablePointerMotion = shouldEnableNonEssentialMotion(reducedMotion);
  const tooltipTransition = resolveMotionDurationMs(reducedMotion, 80) / 1000;
  const dates = points.map((point) => point.label || point.date);
  const xLabelInterval = Math.max(0, Math.ceil(points.length / (compact ? 4 : 8)) - 1);
  const grids: GridComponentOption[] = hasVolume
    ? [
        { left: '2%', right: '5%', top: compact ? '12%' : '10%', height: compact ? '60%' : '58%', containLabel: true },
        { left: '2%', right: '5%', top: compact ? '78%' : '76%', height: compact ? '11%' : '12%', containLabel: true },
      ]
    : [
        { left: '2%', right: '5%', top: compact ? '12%' : '10%', bottom: compact ? '18%' : '16%', containLabel: true },
      ];
  const xAxis = hasVolume
    ? [
        {
          type: 'category' as const,
          data: dates,
          boundaryGap: true,
          axisLine: { lineStyle: { color: 'rgba(166,176,230,0.13)' } },
          axisTick: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false },
        },
        {
          type: 'category' as const,
          gridIndex: 1,
          data: dates,
          boundaryGap: true,
          axisLine: { lineStyle: { color: 'rgba(166,176,230,0.10)' } },
          axisTick: { show: false },
          axisLabel: {
            show: true,
            interval: xLabelInterval,
            hideOverlap: true,
            color: 'rgba(213,219,235,0.48)',
            fontSize: compact ? 9 : 10,
            formatter: (value: string) => formatDateLabel(value).slice(5),
          },
          splitLine: { show: false },
        },
      ]
    : [
        {
          type: 'category' as const,
          data: dates,
          boundaryGap: true,
          axisLine: { lineStyle: { color: 'rgba(166,176,230,0.13)' } },
          axisTick: { show: false },
          axisLabel: {
            show: true,
            interval: xLabelInterval,
            hideOverlap: true,
            color: 'rgba(213,219,235,0.48)',
            fontSize: compact ? 9 : 10,
            formatter: (value: string) => formatDateLabel(value).slice(5),
          },
          splitLine: { show: false },
        },
      ];
  const yAxis = hasVolume
    ? [
        {
          scale: true,
          position: 'right' as const,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            hideOverlap: true,
            color: 'rgba(213,219,235,0.58)',
            fontSize: 10,
            formatter: (value: number) => formatNumber(value, language),
          },
          splitLine: { lineStyle: { color: 'rgba(166,176,230,0.08)' } },
        },
        {
          scale: true,
          gridIndex: 1,
          position: 'right' as const,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            show: !compact,
            hideOverlap: true,
            color: 'rgba(213,219,235,0.34)',
            fontSize: 9,
            formatter: (value: number) => formatCompactNumber(value, language),
          },
          splitLine: { lineStyle: { color: 'rgba(166,176,230,0.05)' } },
        },
      ]
    : [
        {
          scale: true,
          position: 'right' as const,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            hideOverlap: true,
            color: 'rgba(213,219,235,0.58)',
            fontSize: 10,
            formatter: (value: number) => formatNumber(value, language),
          },
          splitLine: { lineStyle: { color: 'rgba(166,176,230,0.08)' } },
        },
      ];
  const mainSeries: CandlestickSeriesOption | LineSeriesOption = renderMode === 'candlestick'
    ? {
        name: 'OHLC',
        type: 'candlestick',
        data: points.map((point) => [point.open, point.close, point.low, point.high]),
        itemStyle: {
          color: PRICE_COLORS.up,
          color0: PRICE_COLORS.down,
          borderColor: PRICE_COLORS.up,
          borderColor0: PRICE_COLORS.down,
        },
      }
    : {
        name: 'Close',
        type: 'line',
        data: points.map((point) => point.close),
        showSymbol: points.length <= 10,
        smooth: false,
        lineStyle: { color: PRICE_COLORS.line, width: compact ? 2 : 2.4 },
        areaStyle: { color: 'rgba(139,164,255,0.08)' },
      };
  const overlaySeries: LineSeriesOption[] = enabledOverlays.map((label) => ({
    name: label,
    type: 'line',
    data: points.map((point) => (label === 'MA5' ? point.ma5 : point.ma20) ?? null),
    showSymbol: false,
    connectNulls: false,
    lineStyle: {
      color: label === 'MA5' ? PRICE_COLORS.ma5 : PRICE_COLORS.ma20,
      width: label === 'MA5' ? 1.35 : 1.25,
      opacity: label === 'MA5' ? 0.88 : 0.76,
    },
    emphasis: { disabled: true },
  }));
  const volumeSeries: BarSeriesOption[] = hasVolume
    ? [{
        name: 'Volume',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: points.map((point) => ({
          value: point.volume ?? 0,
          itemStyle: {
            color: (point.close >= (point.open ?? point.close)) ? 'rgba(47,196,141,0.28)' : 'rgba(231,101,118,0.28)',
          },
        })),
        barWidth: '58%',
      }]
    : [];

  return {
    animation: false,
    animationDuration: 0,
    animationDurationUpdate: 0,
    backgroundColor: 'transparent',
    grid: grids,
    tooltip: {
      trigger: 'axis',
      renderMode: 'html',
      appendToBody: true,
      appendTo: 'body',
      confine: false,
      showDelay: 0,
      hideDelay: reducedMotion ? 0 : 50,
      transitionDuration: tooltipTransition,
      borderWidth: 1,
      borderColor: 'rgba(166,176,230,0.16)',
      backgroundColor: 'rgba(7,11,19,0.96)',
      padding: 0,
      extraCssText: 'pointer-events:none;white-space:normal;max-width:min(260px,calc(100vw - 20px));backdrop-filter:blur(10px);',
      axisPointer: {
        type: 'cross',
        crossStyle: { color: 'rgba(186,194,238,0.46)' },
        label: {
          backgroundColor: 'rgba(9,14,24,0.96)',
          color: 'rgba(248,250,252,0.82)',
          fontSize: 10,
        },
        animation: enablePointerMotion,
      },
      formatter: (params: unknown) => {
        const first = Array.isArray(params) ? params[0] as { dataIndex?: number } | undefined : undefined;
        const point = first?.dataIndex != null ? points[first.dataIndex] : undefined;
        return point ? buildTooltip(point, language, enabledOverlays, renderMode) : '';
      },
    },
    axisPointer: hasVolume ? { link: [{ xAxisIndex: [0, 1] }] } : undefined,
    xAxis,
    yAxis,
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: hasVolume ? [0, 1] : [0],
        start: 0,
        end: 100,
        minValueSpan: points.length > 24 ? 8 : undefined,
        filterMode: 'none',
      },
    ],
    series: [mainSeries, ...overlaySeries, ...volumeSeries],
  };
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
  const chartNodeRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<ECharts | null>(null);
  const [activeRange, setActiveRange] = useState<CoreMarketChartRange>('ALL');
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const reducedMotion = usePrefersReducedMotion();

  const usablePoints = useMemo(() => normalizePoints(points, compact), [compact, points]);
  const visiblePoints = useMemo(() => visibleRangePoints(usablePoints, activeRange), [activeRange, usablePoints]);
  const renderMode: CoreMarketRenderMode = hasCompleteOhlc(visiblePoints) ? 'candlestick' : 'line';
  const hasChart = visiblePoints.length >= 1;
  const hasVolume = showVolume && visiblePoints.some((point) => (point.volume ?? 0) > 0);
  const enabledOverlays = useMemo(() => (
    renderMode === 'candlestick'
      ? [
          usablePoints.some((point) => finiteNumber(point.ma5) != null) ? 'MA5' : null,
          usablePoints.some((point) => finiteNumber(point.ma20) != null) ? 'MA20' : null,
        ].filter((item): item is string => Boolean(item))
      : []
  ), [renderMode, usablePoints]);
  const latestPoint = visiblePoints.at(-1);
  const hoveredPoint = hoveredIndex == null ? null : visiblePoints[hoveredIndex] ?? null;
  const accessibleSemantics = useMemo(() => buildCoreMarketChartAccessibleSemantics({
    testId,
    title,
    language,
    hasChart,
    emptyTitle,
    barCount: visiblePoints.length,
    startDate: visiblePoints[0]?.date,
    endDate: latestPoint?.date,
    renderMode,
    latestLabel: latestLabel || (latestPoint ? formatNumber(latestPoint.close, language) : null),
    changeLabel,
    rangeLabel,
    sourceLabel,
    statusLabel,
    coverageLabel,
  }), [
    changeLabel,
    coverageLabel,
    emptyTitle,
    hasChart,
    language,
    latestLabel,
    latestPoint,
    rangeLabel,
    renderMode,
    sourceLabel,
    statusLabel,
    testId,
    title,
    visiblePoints,
  ]);
  const option = useMemo(() => (
    hasChart
      ? buildChartOption({
          points: visiblePoints,
          language,
          hasVolume,
          enabledOverlays,
          renderMode,
          compact,
          reducedMotion,
        })
      : null
  ), [compact, enabledOverlays, hasChart, hasVolume, language, reducedMotion, renderMode, visiblePoints]);

  useEffect(() => {
    const host = chartNodeRef.current;
    if (!host || !option) return undefined;
    const instance = chartRef.current ?? echarts.init(host, undefined, { renderer: 'canvas' });
    chartRef.current = instance;
    const setOpts: SetOptionOpts = { notMerge: true, lazyUpdate: true };
    instance.setOption(option, setOpts);
    instance.resize();
    const handleResize = () => instance.resize();
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [option]);

  useEffect(() => () => {
    chartRef.current?.dispose();
    chartRef.current = null;
  }, []);

  const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!visiblePoints.length) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const width = rect.width || 1;
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / width));
    setHoveredIndex(Math.round(ratio * (visiblePoints.length - 1)));
  };

  const handleChartFrameKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (!visiblePoints.length) return;
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault();
      setHoveredIndex((current) => {
        const last = visiblePoints.length - 1;
        if (current == null) return event.key === 'ArrowRight' ? 0 : last;
        if (event.key === 'ArrowRight') return Math.min(last, current + 1);
        return Math.max(0, current - 1);
      });
      return;
    }
    if (event.key === 'Home') {
      event.preventDefault();
      setHoveredIndex(0);
      return;
    }
    if (event.key === 'End') {
      event.preventDefault();
      setHoveredIndex(visiblePoints.length - 1);
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      setHoveredIndex(null);
    }
  };

  return (
    <section
      className={[
        'mt-4 overflow-hidden rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:var(--wolfy-surface-muted)] shadow-[var(--wolfy-shadow-panel)]',
        compact ? 'p-3' : 'p-4',
      ].join(' ')}
      data-testid={testId}
      data-chart-kind={chartKind}
      data-chart-engine="echarts"
      data-render-mode={renderMode}
      data-point-count={usablePoints.length}
      data-visible-points={visiblePoints.length}
      data-active-range={activeRange}
      data-has-volume={hasVolume ? 'true' : 'false'}
      data-volume-panel={hasVolume ? 'true' : 'false'}
      data-datazoom-mode="inside"
      data-enabled-overlays={enabledOverlays.length ? enabledOverlays.join(',') : 'none'}
      data-prefers-reduced-motion={reducedMotion ? 'true' : 'false'}
      data-chart-animation="disabled"
      data-tooltip-motion={shouldEnableNonEssentialMotion(reducedMotion) ? 'enabled' : 'disabled'}
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
          <span className="rounded-full border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-2 py-1 text-[color:var(--wolfy-text-secondary)]">{freshnessLabel}</span>
          {coverageLabel ? <span className="rounded-full border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-2 py-1 text-[color:var(--wolfy-text-secondary)]">{coverageLabel}</span> : null}
        </div>
      </div>

      {hasChart ? (
        <div className="mt-3">
          <div className="mb-2.5 flex min-w-0 flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 flex-wrap items-center gap-1.5" data-testid="core-market-chart-range-controls">
              {RANGE_OPTIONS.map((optionItem) => {
                const label = language === 'en' ? optionItem.labelEn : optionItem.labelZh;
                const disabled = Boolean(optionItem.bars && usablePoints.length < optionItem.bars && optionItem.key !== '1D');
                return (
                  <button
                    key={optionItem.key}
                    type="button"
                    className={[
                      'min-h-9 rounded-md border px-2.5 text-xs font-semibold transition-colors',
                      activeRange === optionItem.key
                        ? 'border-[color:var(--wolfy-accent)] bg-[color:var(--wolfy-accent)]/16 text-[color:var(--wolfy-text-primary)]'
                        : 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] text-[color:var(--wolfy-text-secondary)] hover:border-[color:var(--wolfy-border-subtle)] hover:text-[color:var(--wolfy-text-primary)]',
                      disabled ? 'cursor-not-allowed opacity-45' : 'cursor-pointer',
                    ].join(' ')}
                    aria-pressed={activeRange === optionItem.key}
                    disabled={disabled}
                    onClick={() => {
                      setActiveRange(optionItem.key);
                      setHoveredIndex(null);
                    }}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
            <div className="flex min-w-0 flex-wrap items-center gap-2 text-[11px] text-[color:var(--wolfy-text-muted)]" data-testid="core-market-chart-overlay-legend">
              {enabledOverlays.length ? enabledOverlays.map((label) => (
                <span key={label} className="inline-flex items-center gap-1.5">
                  <span
                    className="h-0.5 w-4 rounded-full"
                    style={{ backgroundColor: label === 'MA5' ? PRICE_COLORS.ma5 : PRICE_COLORS.ma20 }}
                    aria-hidden="true"
                  />
                  {label}
                </span>
              )) : (
                <span>{language === 'en' ? 'MA sample insufficient' : '均线样本不足'}</span>
              )}
            </div>
          </div>

          <div
            className={compact
              ? 'relative h-[210px] min-w-0 max-w-full overflow-visible outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-border-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--wolfy-surface-muted)]'
              : 'relative h-[320px] min-w-0 max-w-full overflow-visible outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-border-focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--wolfy-surface-muted)] sm:h-[360px]'}
            data-testid="core-market-chart-frame"
            tabIndex={0}
            role="group"
            aria-label={accessibleSemantics.exploreLabel}
            onMouseMove={handleMouseMove}
            onMouseLeave={() => setHoveredIndex(null)}
            onKeyDown={handleChartFrameKeyDown}
            onBlur={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
                setHoveredIndex(null);
              }
            }}
          >
            <figure
              ref={chartNodeRef}
              className="size-full min-h-full min-w-0"
              role={CHART_GRAPHIC_ROLE}
              aria-label={accessibleSemantics.ariaLabel}
              aria-describedby={accessibleSemantics.descriptionId}
              data-testid="core-market-echarts-node"
            />
            <p
              id={accessibleSemantics.descriptionId}
              className="sr-only"
              data-testid="core-market-chart-text-alternative"
            >
              {accessibleSemantics.description}
            </p>
            {hoveredPoint ? (
              <output
                className="sr-only"
                aria-live="polite"
                data-testid="core-market-hover-tooltip"
              >
                <p>{language === 'en' ? 'Date' : '日期'} {formatDateLabel(hoveredPoint.label || hoveredPoint.date)}</p>
                {renderMode === 'candlestick' ? (
                  <p>
                    {language === 'en'
                      ? `Open ${formatNumber(hoveredPoint.open, language)} · High ${formatNumber(hoveredPoint.high, language)} · Low ${formatNumber(hoveredPoint.low, language)}`
                      : `开盘 ${formatNumber(hoveredPoint.open, language)} · 最高 ${formatNumber(hoveredPoint.high, language)} · 最低 ${formatNumber(hoveredPoint.low, language)}`}
                  </p>
                ) : null}
                <p>{language === 'en' ? 'Close' : '收盘'} {formatNumber(hoveredPoint.close, language)}</p>
                <p>{language === 'en' ? 'Volume' : '成交量'} {formatCompactNumber(hoveredPoint.volume, language)}</p>
                {enabledOverlays.length ? (
                  <p>{enabledOverlays.map((label) => `${label} ${formatNumber(label === 'MA5' ? hoveredPoint.ma5 : hoveredPoint.ma20, language)}`).join(' · ')}</p>
                ) : null}
              </output>
            ) : null}
          </div>

          <div className="mt-3 grid gap-2 text-xs text-[color:var(--wolfy-text-secondary)] sm:grid-cols-3">
            <div>
              <span className="block text-[10px] uppercase tracking-[0.08em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Range' : '区间'}</span>
              <span className="font-medium text-[color:var(--wolfy-text-primary)]">{rangeLabel}</span>
            </div>
            <div>
              <span className="block text-[10px] uppercase tracking-[0.08em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Latest' : '最新'}</span>
              <span className="font-medium text-[color:var(--wolfy-text-primary)]">{latestLabel || formatNumber(latestPoint?.close, language)}</span>
            </div>
            <div>
              <span className="block text-[10px] uppercase tracking-[0.08em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Source' : '来源'}</span>
              <span className="font-medium text-[color:var(--wolfy-text-primary)]">{sourceLabel}</span>
            </div>
          </div>
          {hasVolume ? (
            <p className="mt-2 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]" data-testid="core-market-chart-volume-context">
              {language === 'en'
                ? `Volume uses returned rows only. Latest volume ${formatCompactNumber(latestPoint?.volume, language)}.`
                : `成交量仅使用接口返回记录。最新成交量 ${formatCompactNumber(latestPoint?.volume, language)}。`}
            </p>
          ) : null}
          {changeLabel ? <p className="mt-1 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">{changeLabel}</p> : null}
        </div>
      ) : (
        <div
          className="mt-4 rounded-md border border-dashed border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-4"
          data-testid={`${testId}-empty-state`}
        >
          <p className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{emptyTitle}</p>
          <p className="mt-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{emptyDetail}</p>
          <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
            <span className={`rounded-full border px-2 py-1 font-medium ${toneClass(statusTone)}`}>{statusLabel}</span>
            <span className="rounded-full border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-2 py-1 text-[color:var(--wolfy-text-secondary)]">{freshnessLabel}</span>
            <span className="rounded-full border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-2 py-1 text-[color:var(--wolfy-text-secondary)]">{sourceLabel}</span>
          </div>
        </div>
      )}
    </section>
  );
};
