import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as echarts from 'echarts/core';
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
import type { ComposeOption, ECharts, SetOptionOpts } from 'echarts/core';
import { SVGRenderer } from 'echarts/renderers';
import { stocksApi, type StockHistoryPoint } from '../../api/stocks';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useElementSize } from '../../hooks/useElementSize';
import { cn } from '../../utils/cn';

echarts.use([
  CandlestickChart,
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  SVGRenderer,
]);

type HomeChartOption = ComposeOption<
  | CandlestickSeriesOption
  | LineSeriesOption
  | BarSeriesOption
  | GridComponentOption
  | TooltipComponentOption
  | DataZoomComponentOption
>;

type HomeTimeframeKey = '1D' | '1W' | '1M';
type HomeIndicatorKey = 'ma5' | 'ma10' | 'ma20' | 'ma60' | 'vwap';

type CandlePoint = {
  date: string;
  rangeStart?: string;
  rangeEnd?: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma5?: number;
  ma10?: number;
  ma20?: number;
  ma60?: number;
  vwap?: number;
};

type CandlePointBase = {
  date: string;
  rangeStart?: string;
  rangeEnd?: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type HomeCandlestickChartProps = {
  ticker: string;
  currentPrice?: number | null;
  isLocked?: boolean;
  onContextChange?: (context: HomeCandlestickChartContext | null) => void;
};

export type HomeCandlestickChartContext = {
  timeframe: HomeTimeframeKey;
  sourceHint?: string;
};

type TooltipPositionSize = {
  contentSize: [number, number];
  viewSize: [number, number];
};

type TimeframeOption = {
  key: HomeTimeframeKey;
  label: HomeTimeframeKey;
  description: string;
};

type IndicatorConfig = {
  key: HomeIndicatorKey;
  label: string;
  color: string;
};

const TIMEFRAME_OPTIONS: TimeframeOption[] = [
  { key: '1D', label: '1D', description: 'Daily candles' },
  { key: '1W', label: '1W', description: 'Weekly candles derived from daily OHLC' },
  { key: '1M', label: '1M', description: 'Monthly candles derived from daily OHLC' },
];

const INDICATOR_CONFIGS: IndicatorConfig[] = [
  { key: 'ma5', label: 'MA5', color: '#8FA3D8' },
  { key: 'ma10', label: 'MA10', color: '#C4A46A' },
  { key: 'ma20', label: 'MA20', color: '#9B91D9' },
  { key: 'ma60', label: 'MA60', color: '#C88499' },
  { key: 'vwap', label: 'VWAP', color: '#7BAE88' },
];

const DEFAULT_INDICATORS: Record<HomeIndicatorKey, boolean> = {
  ma5: true,
  ma10: true,
  ma20: true,
  ma60: false,
  vwap: false,
};

const isFiniteNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);

const toFiniteNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value.replace(/[%,$\s]/g, ''));
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
};

const formatPrice = (value?: number | null): string => (
  Number.isFinite(value ?? NaN) ? Number(value).toFixed(2) : '--'
);

const formatVolume = (value?: number | null): string => {
  if (!Number.isFinite(value ?? NaN)) {
    return '--';
  }
  const numeric = Number(value);
  if (numeric >= 1_000_000_000) return `${(numeric / 1_000_000_000).toFixed(2)}B`;
  if (numeric >= 1_000_000) return `${(numeric / 1_000_000).toFixed(2)}M`;
  if (numeric >= 1_000) return `${(numeric / 1_000).toFixed(1)}K`;
  return numeric.toFixed(0);
};

const formatDate = (value: string, locale: string): string => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' });
};

const formatDateRange = (start: string, end: string, locale: string): string => {
  if (!start || !end || start === end) {
    return formatDate(end || start, locale);
  }
  return `${formatDate(start, locale)} - ${formatDate(end, locale)}`;
};

const escapeHtml = (value: string): string => value
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');

const viewportSize = () => ({
  width: typeof window !== 'undefined'
    ? window.innerWidth || document.documentElement.clientWidth || 0
    : 0,
  height: typeof window !== 'undefined'
    ? window.innerHeight || document.documentElement.clientHeight || 0
    : 0,
});

// eslint-disable-next-line react-refresh/only-export-components -- tested geometry helper for viewport-constrained tooltips
export const resolveHomeCandlestickTooltipPosition = (
  point: [number, number],
  size: TooltipPositionSize,
  chartRect?: Pick<DOMRect, 'left' | 'top'> | null,
  viewport = viewportSize(),
): [number, number] => {
  const margin = 10;
  const cursorGap = 14;
  const [contentWidth = 180, contentHeight = 96] = size.contentSize;
  const [viewWidth, viewHeight] = size.viewSize;
  const [mouseX, mouseY] = point;

  if (chartRect && viewport.width > 0 && viewport.height > 0) {
    let viewportX = chartRect.left + mouseX + cursorGap;
    if (viewportX + contentWidth + margin > viewport.width) {
      viewportX = chartRect.left + mouseX - contentWidth - cursorGap;
    }
    viewportX = Math.max(margin, Math.min(viewportX, viewport.width - contentWidth - margin));

    let viewportY = chartRect.top + mouseY - contentHeight - cursorGap;
    if (viewportY < margin) {
      viewportY = chartRect.top + mouseY + cursorGap;
    }
    viewportY = Math.max(margin, Math.min(viewportY, viewport.height - contentHeight - margin));

    return [viewportX - chartRect.left, viewportY - chartRect.top];
  }

  let x = mouseX + cursorGap;
  if (x + contentWidth + margin > viewWidth) {
    x = mouseX - contentWidth - cursorGap;
  }
  x = Math.max(margin, Math.min(x, viewWidth - contentWidth - margin));

  let y = mouseY - contentHeight - cursorGap;
  if (y < margin) {
    y = mouseY + cursorGap;
  }
  y = Math.max(margin, Math.min(y, viewHeight - contentHeight - margin));
  return [x, y];
};

const parseUtcDate = (value: string): Date | null => {
  if (!value) {
    return null;
  }
  const normalized = value.includes('T') ? value : `${value}T00:00:00Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
};

const toUtcDayKey = (date: Date): string => (
  `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-${String(date.getUTCDate()).padStart(2, '0')}`
);

const toWeekKey = (value: string): string => {
  const date = parseUtcDate(value);
  if (!date) {
    return value;
  }
  const weekStart = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const utcDay = weekStart.getUTCDay() || 7;
  weekStart.setUTCDate(weekStart.getUTCDate() - utcDay + 1);
  return toUtcDayKey(weekStart);
};

const toMonthKey = (value: string): string => {
  const date = parseUtcDate(value);
  if (!date) {
    return value.slice(0, 7);
  }
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`;
};

const movingAverage = (values: number[], index: number, length: number): number | undefined => {
  if (index < length - 1) {
    return undefined;
  }
  const slice = values.slice(index - length + 1, index + 1);
  const total = slice.reduce((sum, value) => sum + value, 0);
  return Number((total / length).toFixed(2));
};

const normalizeCandles = (items: StockHistoryPoint[]): CandlePointBase[] => (
  items
    .map((item) => {
      const open = toFiniteNumber(item.open);
      const high = toFiniteNumber(item.high);
      const low = toFiniteNumber(item.low);
      const close = toFiniteNumber(item.close);
      if (!item.date || open === undefined || high === undefined || low === undefined || close === undefined) {
        return null;
      }
      return {
        date: String(item.date),
        open,
        high,
        low,
        close,
        volume: toFiniteNumber(item.volume) ?? 0,
      };
    })
    .filter((item): item is CandlePointBase => Boolean(item))
    .sort((a, b) => a.date.localeCompare(b.date))
);

const aggregateCandles = (candles: CandlePointBase[], timeframe: HomeTimeframeKey): CandlePointBase[] => {
  if (timeframe === '1D') {
    return candles;
  }

  const keyFor = timeframe === '1W' ? toWeekKey : toMonthKey;
  const grouped = new Map<string, CandlePointBase[]>();

  candles.forEach((item) => {
    const key = keyFor(item.date);
    const existing = grouped.get(key);
    if (existing) {
      existing.push(item);
      return;
    }
    grouped.set(key, [item]);
  });

  return [...grouped.values()].map((bucket) => {
    const first = bucket[0];
    const last = bucket[bucket.length - 1];
    return {
      date: last.date,
      rangeStart: first.date,
      rangeEnd: last.date,
      open: first.open,
      high: Math.max(...bucket.map((item) => item.high)),
      low: Math.min(...bucket.map((item) => item.low)),
      close: last.close,
      volume: bucket.reduce((sum, item) => sum + item.volume, 0),
    };
  });
};

const withIndicators = (candles: CandlePointBase[]): CandlePoint[] => {
  const closes = candles.map((item) => item.close);
  let cumulativeWeightedPrice = 0;
  let cumulativeVolume = 0;

  return candles.map((item, index) => {
    const typicalPrice = (item.high + item.low + item.close) / 3;
    if (item.volume > 0) {
      cumulativeWeightedPrice += typicalPrice * item.volume;
      cumulativeVolume += item.volume;
    }
    return {
      ...item,
      ma5: movingAverage(closes, index, 5),
      ma10: movingAverage(closes, index, 10),
      ma20: movingAverage(closes, index, 20),
      ma60: movingAverage(closes, index, 60),
      vwap: cumulativeVolume > 0 ? Number((cumulativeWeightedPrice / cumulativeVolume).toFixed(2)) : undefined,
    };
  });
};

const candleDateLabel = (point: CandlePoint, locale: string): string => (
  point.rangeStart || point.rangeEnd
    ? formatDateRange(point.rangeStart || point.date, point.rangeEnd || point.date, locale)
    : formatDate(point.date, locale)
);

const buildTooltip = (
  point: CandlePoint,
  locale: string,
  enabledIndicators: IndicatorConfig[],
  reportReferencePrice?: number,
): string => {
  const isChinese = locale.startsWith('zh');
  const labels = isChinese
    ? {
        date: '日期',
        open: '开盘',
        high: '最高',
        low: '最低',
        close: '收盘',
        volume: '成交量',
        reportReferencePrice: '报告参考价',
      }
    : {
        date: 'Date',
        open: 'Open',
        high: 'High',
        low: 'Low',
        close: 'Close',
        volume: 'Volume',
        reportReferencePrice: 'Report ref',
      };

  const indicatorRows = enabledIndicators
    .map(({ label, key }) => {
      const value = point[key];
      if (!isFiniteNumber(value)) {
        return null;
      }
      return `<div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${label}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatPrice(value)}</strong></div>`;
    })
    .filter(Boolean)
    .join('');

  const reportReferenceRow = isFiniteNumber(reportReferencePrice)
    ? `<div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.reportReferencePrice}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatPrice(reportReferencePrice)}</strong></div>`
    : '';

  return `
    <div style="min-width:188px;max-width:248px;padding:8px 10px;font-size:11px;line-height:1.65;">
      <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:5px;"><span style="color:rgba(248,250,252,.48);">${labels.date}</span><strong style="color:rgba(248,250,252,.92);font-weight:600;">${escapeHtml(candleDateLabel(point, locale))}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.open}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatPrice(point.open)}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.high}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatPrice(point.high)}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.low}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatPrice(point.low)}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.close}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatPrice(point.close)}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.volume}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatVolume(point.volume)}</strong></div>
      ${reportReferenceRow}
      ${indicatorRows}
    </div>
  `;
};

const timeframeSourceHint = (timeframe: HomeTimeframeKey, language: 'zh' | 'en'): string | undefined => {
  if (timeframe === '1D') {
    return undefined;
  }
  return language === 'en' ? 'Derived from daily OHLC' : '由日线聚合';
};

const getMaStructure = (candles: CandlePoint[], language: 'zh' | 'en'): string | undefined => {
  const latest = [...candles].reverse().find((item) => isFiniteNumber(item.ma5) && isFiniteNumber(item.ma10) && isFiniteNumber(item.ma20));
  if (!latest || latest.ma5 === undefined || latest.ma10 === undefined || latest.ma20 === undefined) {
    return undefined;
  }
  if (latest.ma5 > latest.ma10 && latest.ma10 > latest.ma20) {
    return language === 'en' ? 'MA5 > MA10 > MA20' : 'MA5 > MA10 > MA20';
  }
  if (latest.ma5 < latest.ma10 && latest.ma10 < latest.ma20) {
    return language === 'en' ? 'MA5 < MA10 < MA20' : 'MA5 < MA10 < MA20';
  }
  return language === 'en' ? 'Mixed MA structure' : '均线结构分化';
};

const volumeSupportStatus = (candles: CandlePoint[]) => {
  if (!candles.length) {
    return { available: false, zeroHeavy: true };
  }
  const positiveVolumes = candles.filter((item) => item.volume > 0).length;
  const totalVolume = candles.reduce((sum, item) => sum + item.volume, 0);
  const positiveRatio = positiveVolumes / candles.length;
  return {
    available: positiveVolumes >= Math.max(3, Math.ceil(candles.length * 0.6)) && totalVolume > 0,
    zeroHeavy: positiveRatio < 0.6 || totalVolume <= 0,
  };
};

export const HomeCandlestickChart: React.FC<HomeCandlestickChartProps> = ({
  ticker,
  currentPrice,
  isLocked = false,
  onContextChange,
}) => {
  const { language } = useI18n();
  const locale = language === 'zh' ? 'zh-CN' : 'en-US';
  const { ref: sizeRef, size } = useElementSize<HTMLDivElement>();
  const chartNodeRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<ECharts | null>(null);
  const [dailyCandles, setDailyCandles] = useState<CandlePointBase[]>([]);
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'unavailable'>('idle');
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [activeTimeframe, setActiveTimeframe] = useState<HomeTimeframeKey>('1D');
  const [indicatorVisibility, setIndicatorVisibility] = useState<Record<HomeIndicatorKey, boolean>>(DEFAULT_INDICATORS);

  useEffect(() => {
    let cancelled = false;
    const loadCandles = async () => {
      const normalizedTicker = String(ticker || '').trim().toUpperCase();
      if (!normalizedTicker || normalizedTicker === '-' || isLocked) {
        setDailyCandles([]);
        setStatus('unavailable');
        return;
      }
      setStatus('loading');
      setDailyCandles([]);
      try {
        const response = await stocksApi.getHistory(normalizedTicker, { period: 'daily', days: 365 });
        if (cancelled) {
          return;
        }
        const normalized = normalizeCandles(response.data || []);
        setDailyCandles(normalized);
        setStatus(normalized.length ? 'ready' : 'unavailable');
      } catch {
        if (!cancelled) {
          setDailyCandles([]);
          setStatus('unavailable');
        }
      }
    };

    void loadCandles();
    return () => {
      cancelled = true;
    };
  }, [isLocked, ticker]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- ticker changes reset local chart controls to their defaults
    setActiveTimeframe('1D');
    setHoveredIndex(null);
    setIndicatorVisibility(DEFAULT_INDICATORS);
  }, [ticker]);

  const aggregatedCandles = useMemo(
    () => aggregateCandles(dailyCandles, activeTimeframe),
    [activeTimeframe, dailyCandles],
  );
  const candles = useMemo(
    () => withIndicators(aggregatedCandles),
    [aggregatedCandles],
  );
  const sourceHint = useMemo(
    () => timeframeSourceHint(activeTimeframe, language === 'en' ? 'en' : 'zh'),
    [activeTimeframe, language],
  );
  const vwapStatus = useMemo(
    () => volumeSupportStatus(candles),
    [candles],
  );
  const indicatorEnabledState = useMemo(() => ({
    ma5: candles.some((item) => isFiniteNumber(item.ma5)),
    ma10: candles.some((item) => isFiniteNumber(item.ma10)),
    ma20: candles.some((item) => isFiniteNumber(item.ma20)),
    ma60: candles.some((item) => isFiniteNumber(item.ma60)),
    vwap: vwapStatus.available && candles.some((item) => isFiniteNumber(item.vwap)),
  }), [candles, vwapStatus.available]);
  const enabledIndicators = useMemo(
    () => INDICATOR_CONFIGS.filter(({ key }) => indicatorVisibility[key] && indicatorEnabledState[key]),
    [indicatorEnabledState, indicatorVisibility],
  );

  useEffect(() => {
    if (status !== 'ready' || !candles.length) {
      onContextChange?.(null);
      return;
    }
    onContextChange?.({
      timeframe: activeTimeframe,
      sourceHint,
    });
  }, [activeTimeframe, candles.length, onContextChange, sourceHint, status]);

  const option = useMemo<HomeChartOption | null>(() => {
    if (!candles.length) {
      return null;
    }
    const dates = candles.map((item) => item.date);
    const visibleStart = activeTimeframe === '1D' && candles.length > 120
      ? Math.round(((candles.length - 120) / candles.length) * 100)
      : 0;
    const safeCurrentPrice = isFiniteNumber(currentPrice) ? currentPrice : undefined;
    const isCompactChart = size.width > 0 && size.width < 520;
    const xLabelInterval = Math.max(0, Math.ceil(candles.length / (isCompactChart ? 4 : 7)) - 1);
    const rightAxisGutter = isCompactChart ? 44 : 56;

    return {
      animation: false,
      backgroundColor: 'transparent',
      grid: [
        { left: 6, right: rightAxisGutter, top: 12, height: '58%', containLabel: true },
        { left: 6, right: rightAxisGutter, top: '76%', height: '10%', containLabel: true },
      ],
      tooltip: {
        trigger: 'axis',
        renderMode: 'html',
        appendToBody: true,
        appendTo: 'body',
        confine: false,
        className: 'home-candlestick-echarts-tooltip',
        showDelay: 0,
        hideDelay: 60,
        transitionDuration: 0.08,
        axisPointer: {
          type: 'cross',
          crossStyle: { color: 'rgba(208,214,224,0.34)' },
          label: {
            backgroundColor: 'rgba(15,16,17,0.98)',
            color: 'rgba(247,248,248,0.82)',
            fontSize: 10,
          },
        },
        borderWidth: 1,
        borderColor: '#34343a',
        backgroundColor: 'rgba(15,16,17,0.98)',
        borderRadius: 6,
        padding: 0,
        shadowBlur: 0,
        shadowColor: 'transparent',
        shadowOffsetX: 0,
        shadowOffsetY: 0,
        extraCssText: 'pointer-events:none;white-space:normal;max-width:min(248px,calc(100vw - 20px));',
        textStyle: {
          color: 'rgba(247,248,248,0.86)',
          fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif',
          fontSize: 11,
          lineHeight: 16,
        },
        position: (point, _params, _dom, _rect, sizeArg) => resolveHomeCandlestickTooltipPosition(
          point as [number, number],
          sizeArg,
          chartNodeRef.current?.getBoundingClientRect(),
        ),
        formatter: (params: unknown) => {
          const first = Array.isArray(params) ? params[0] as { dataIndex?: number } | undefined : undefined;
          const point = first?.dataIndex != null ? candles[first.dataIndex] : undefined;
          return point ? buildTooltip(point, locale, enabledIndicators, safeCurrentPrice) : '';
        },
      },
      axisPointer: {
        link: [{ xAxisIndex: [0, 1] }],
      },
      xAxis: [
        {
          type: 'category',
          data: dates,
          boundaryGap: true,
          axisLine: { lineStyle: { color: '#23252a' } },
          axisTick: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false },
        },
        {
          type: 'category',
          gridIndex: 1,
          data: dates,
          boundaryGap: true,
          axisLine: { lineStyle: { color: '#23252a' } },
          axisTick: { show: false },
          axisLabel: {
            show: true,
            interval: xLabelInterval,
            hideOverlap: true,
            margin: 8,
            color: '#62666d',
            fontSize: isCompactChart ? 9 : 10,
            formatter: (value: string) => formatDate(value, locale),
          },
          splitLine: { show: false },
        },
      ],
      yAxis: [
        {
          scale: true,
          position: 'right',
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            hideOverlap: true,
            margin: 8,
            color: '#8a8f98',
            fontSize: 10,
            formatter: (value: number) => formatPrice(value),
          },
          splitLine: { lineStyle: { color: 'rgba(35,37,42,0.86)', width: 1 } },
        },
        {
          scale: true,
          gridIndex: 1,
          position: 'right',
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            show: !isCompactChart,
            showMinLabel: false,
            showMaxLabel: false,
            hideOverlap: true,
            margin: 6,
            color: '#62666d',
            fontSize: 9,
            formatter: (value: number) => formatVolume(value),
          },
          splitLine: { lineStyle: { color: 'rgba(35,37,42,0.68)', width: 1 } },
        },
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1],
          start: visibleStart,
          end: 100,
          minValueSpan: candles.length > 24 ? 12 : undefined,
          filterMode: 'none',
        },
      ],
      series: [
        {
          name: 'OHLC',
          type: 'candlestick',
          data: candles.map((item) => [item.open, item.close, item.low, item.high]),
          itemStyle: {
            color: '#7DBB8B',
            color0: '#D16D7C',
            borderColor: '#7DBB8B',
            borderColor0: '#D16D7C',
          },
          markLine: safeCurrentPrice
            ? {
                symbol: ['none', 'none'],
                silent: true,
                lineStyle: { color: '#5e6ad2', type: 'dashed', width: 1 },
                label: {
                  color: '#ffffff',
                  backgroundColor: '#5e6ad2',
                  borderRadius: 3,
                  padding: [2, 5],
                  formatter: () => formatPrice(safeCurrentPrice),
                },
                data: [{ yAxis: safeCurrentPrice }],
              }
            : undefined,
        },
        ...enabledIndicators.map(({ key, label, color }) => ({
          name: label,
          type: 'line' as const,
          data: candles.map((item) => item[key] ?? null),
          smooth: key === 'vwap',
          showSymbol: false,
          connectNulls: false,
          lineStyle: {
            width: key === 'vwap' ? 1.6 : 1.35,
            color,
            opacity: key === 'ma20' ? 0.66 : 0.86,
            type: key === 'vwap' ? ('dashed' as const) : ('solid' as const),
          },
          emphasis: { disabled: true },
        })),
        {
          name: 'Volume',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: candles.map((item) => ({
            value: item.volume,
            itemStyle: {
              color: item.close >= item.open ? 'rgba(125,187,139,0.28)' : 'rgba(209,109,124,0.28)',
            },
          })),
          barWidth: '58%',
        },
      ],
    };
  }, [activeTimeframe, candles, currentPrice, enabledIndicators, locale, size.width]);

  useEffect(() => {
    const host = chartNodeRef.current;
    if (!host || !option || size.width <= 0 || size.height <= 0) {
      return undefined;
    }
    const instance = chartRef.current ?? echarts.init(host, undefined, { renderer: 'svg' });
    chartRef.current = instance;
    const setOpts: SetOptionOpts = { notMerge: true, lazyUpdate: true };
    instance.setOption(option, setOpts);
    instance.resize();
    return undefined;
  }, [option, size.height, size.width]);

  useEffect(() => () => {
    chartRef.current?.dispose();
    chartRef.current = null;
  }, []);

  const handleMouseMove = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    if (!candles.length) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const width = rect.width || 1;
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / width));
    setHoveredIndex(Math.round(ratio * (candles.length - 1)));
  }, [candles]);

  const handleTimeframeChange = useCallback((nextTimeframe: HomeTimeframeKey) => {
    setActiveTimeframe(nextTimeframe);
    setHoveredIndex(null);
  }, []);

  const handleIndicatorToggle = useCallback((key: HomeIndicatorKey) => {
    if (!indicatorEnabledState[key]) {
      return;
    }
    setIndicatorVisibility((current) => ({
      ...current,
      [key]: !current[key],
    }));
  }, [indicatorEnabledState]);

  const hoveredCandle = hoveredIndex != null ? candles[hoveredIndex] : null;
  const enabledIndicatorLabels = enabledIndicators.map((item) => item.label).join(',');
  const maStructure = getMaStructure(candles, language === 'en' ? 'en' : 'zh');
  const chartUnavailableTitle = status === 'loading'
    ? (language === 'en' ? 'Loading candles...' : '正在加载 K 线...')
    : (language === 'en' ? 'Selected timeframe is unavailable' : '该周期行情暂不可用');
  const chartUnavailableBody = status === 'loading'
    ? null
    : (language === 'en'
      ? 'Daily OHLC history was not returned for this ticker.'
      : '当前标的未返回可用的日线 OHLC 数据。');

  return (
    <div
      ref={sizeRef}
      className="min-w-0 rounded-[12px] border border-[#23252a] bg-[#141516] px-3 py-3"
      data-testid="home-linear-technical-chart"
      data-chart-engine="echarts"
      data-chart-source={activeTimeframe === '1D' ? 'stocks-history-daily' : 'stocks-history-daily-aggregated'}
      data-chart-timeframe={activeTimeframe}
      data-chart-points={String(candles.length)}
      data-enabled-indicators={enabledIndicatorLabels}
      data-vwap-available={String(indicatorEnabledState.vwap)}
      data-axis-layout="split-price-volume"
      data-x-axis-density="sampled"
      data-tooltip-container="body"
      data-tooltip-bounds="viewport"
    >
      <div className="mb-3 flex min-w-0 flex-col gap-2.5">
        <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <div className="flex items-center gap-0.5 rounded-md border border-[#23252a] bg-[#0f1011] p-0.5">
              {TIMEFRAME_OPTIONS.map((optionItem) => (
                <button
                  key={optionItem.key}
                  type="button"
                  aria-pressed={activeTimeframe === optionItem.key}
                  className={cn(
                    'rounded px-2.5 py-1 text-[10px] font-medium transition-colors',
                    activeTimeframe === optionItem.key
                      ? 'bg-[#5e6ad2]/18 text-[#f7f8f8]'
                      : 'text-[#8a8f98] hover:bg-[#18191a] hover:text-[#d0d6e0]',
                  )}
                  onClick={() => handleTimeframeChange(optionItem.key)}
                  disabled={status !== 'ready'}
                  title={optionItem.description}
                >
                  {optionItem.label}
                </button>
              ))}
            </div>
            <span className="hidden text-[10px] text-[#62666d] sm:inline">{ticker}</span>
            {sourceHint ? (
              <span className="text-[10px] text-[#62666d]">{sourceHint}</span>
            ) : null}
          </div>
          {maStructure ? (
            <span className="text-[10px] text-[#62666d]">{maStructure}</span>
          ) : null}
        </div>

        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          {INDICATOR_CONFIGS.map(({ key, label, color }) => {
            const available = indicatorEnabledState[key];
            const pressed = indicatorVisibility[key] && available;
            const title = key === 'ma60' && !available
              ? (language === 'en' ? 'MA60 needs more history' : 'MA60 需要更多历史 K 线')
              : key === 'vwap' && !available
                ? (language === 'en' ? 'VWAP needs reliable volume' : 'VWAP 需要可靠成交量')
                : label;
            return (
              <button
                key={key}
                type="button"
                aria-pressed={pressed}
                disabled={!available}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-[10px] font-medium transition-colors',
                  pressed
                    ? 'border-[#34343a] bg-[#18191a] text-[#d0d6e0]'
                    : 'border-[#23252a] bg-[#0f1011] text-[#8a8f98] hover:border-[#34343a] hover:bg-[#18191a] hover:text-[#d0d6e0]',
                  !available ? 'cursor-not-allowed opacity-40 hover:border-[#23252a] hover:bg-[#0f1011] hover:text-[#8a8f98]' : '',
                )}
                onClick={() => handleIndicatorToggle(key)}
                title={title}
              >
                <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
                <span>{label}</span>
              </button>
            );
          })}
          {!indicatorEnabledState.vwap && vwapStatus.zeroHeavy ? (
            <span className="text-[10px] text-[#62666d]">{language === 'en' ? 'VWAP unavailable' : 'VWAP 暂不可用'}</span>
          ) : null}
        </div>
      </div>

      {status === 'ready' && candles.length ? (
        <div
          className="relative h-[228px] min-w-[280px] overflow-visible sm:h-[238px] lg:h-[246px]"
          data-testid="home-candlestick-chart-frame"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoveredIndex(null)}
        >
          <div
            ref={chartNodeRef}
            className="h-full w-full"
            role="img"
            aria-label={language === 'en' ? `Interactive ${activeTimeframe} OHLC candlestick chart` : `可交互 ${activeTimeframe} OHLC K 线图`}
            data-testid="home-candlestick-echarts-node"
          />
          {hoveredCandle ? (
            <div
              className="sr-only"
              data-testid="home-candlestick-hover-tooltip"
              role="status"
              aria-live="polite"
            >
              <p className="font-medium text-[#f7f8f8]">
                {language === 'en' ? 'Date' : '日期'} {candleDateLabel(hoveredCandle, locale)}
              </p>
              <p>
                {language === 'en'
                  ? `Open ${formatPrice(hoveredCandle.open)} · High ${formatPrice(hoveredCandle.high)} · Low ${formatPrice(hoveredCandle.low)} · Close ${formatPrice(hoveredCandle.close)}`
                  : `开盘 ${formatPrice(hoveredCandle.open)} · 最高 ${formatPrice(hoveredCandle.high)} · 最低 ${formatPrice(hoveredCandle.low)} · 收盘 ${formatPrice(hoveredCandle.close)}`}
              </p>
              <p>{language === 'en' ? 'Volume' : '成交量'} {formatVolume(hoveredCandle.volume)}</p>
              {isFiniteNumber(currentPrice) ? (
                <p>{language === 'en' ? 'Report ref' : '报告参考价'} {formatPrice(currentPrice)}</p>
              ) : null}
              {enabledIndicators.length ? (
                <p className="text-[#8a8f98]">
                  {enabledIndicators
                    .map(({ key, label }) => (isFiniteNumber(hoveredCandle[key]) ? `${label} ${formatPrice(hoveredCandle[key])}` : null))
                    .filter(Boolean)
                    .join(' · ')}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : (
        <div
          className={cn(
            'flex h-[228px] min-w-[280px] flex-col items-center justify-center rounded border border-[#23252a] bg-[#0f1011] px-4 text-center sm:h-[238px] lg:h-[246px]',
            status === 'loading' ? 'text-[#8a8f98]' : 'text-[#62666d]',
          )}
          data-testid="home-candlestick-unavailable"
        >
          <p className="text-sm font-medium">{chartUnavailableTitle}</p>
          {chartUnavailableBody ? (
            <p className="mt-2 max-w-xs text-xs leading-5 text-[#62666d]">
              {chartUnavailableBody}
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
};
