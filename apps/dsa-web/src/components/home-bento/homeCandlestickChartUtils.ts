import type { BarSeriesOption, CandlestickSeriesOption, LineSeriesOption } from 'echarts/charts';
import type {
  DataZoomComponentOption,
  GridComponentOption,
  TooltipComponentOption,
} from 'echarts/components';
import type { ComposeOption } from 'echarts/core';
import type { StockHistoryPoint } from '../../api/stocks';

export type HomeChartOption = ComposeOption<
  | CandlestickSeriesOption
  | LineSeriesOption
  | BarSeriesOption
  | GridComponentOption
  | TooltipComponentOption
  | DataZoomComponentOption
>;

export type HomeTimeframeKey = '1D' | '1W' | '1M';
export type HomeIndicatorKey = 'ma5' | 'ma10' | 'ma20' | 'ma60' | 'vwap';

export type HomeIndicatorConfig = {
  key: HomeIndicatorKey;
  label: string;
  color: string;
};

export type CandlePoint = {
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

export type CandlePointBase = {
  date: string;
  rangeStart?: string;
  rangeEnd?: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type HomeChartIndicatorEnabledState = Record<HomeIndicatorKey, boolean>;

export type HomeChartVolumeSupportStatus = {
  available: boolean;
  zeroHeavy: boolean;
};

export type HomeCandlestickChartModel = {
  candles: CandlePoint[];
  sourceHint?: string;
  indicatorEnabledState: HomeChartIndicatorEnabledState;
  volumeSupportStatus: HomeChartVolumeSupportStatus;
  maStructure?: string;
};

export type TooltipPositionSize = {
  contentSize: [number, number];
  viewSize: [number, number];
};

type HomeChartLanguage = 'zh' | 'en';

type BuildHomeCandlestickChartModelArgs = {
  dailyCandles: CandlePointBase[];
  timeframe: HomeTimeframeKey;
  language: HomeChartLanguage;
};

type BuildHomeCandlestickChartOptionArgs = {
  candles: CandlePoint[];
  timeframe: HomeTimeframeKey;
  currentPrice?: number | null;
  isCompactChart: boolean;
  locale: string;
  enabledIndicators: HomeIndicatorConfig[];
  resolveTooltipPosition: (point: [number, number], size: TooltipPositionSize) => [number, number];
};

const HOME_CHART_GRID_SAFE_MARGIN = {
  left: '2%',
  right: '5%',
  outerBoundsMode: 'same',
  outerBoundsContain: 'axisLabel',
} satisfies Pick<GridComponentOption, 'left' | 'right' | 'outerBoundsMode' | 'outerBoundsContain'>;

const viewportSize = () => ({
  width: typeof window !== 'undefined'
    ? window.innerWidth || document.documentElement.clientWidth || 0
    : 0,
  height: typeof window !== 'undefined'
    ? window.innerHeight || document.documentElement.clientHeight || 0
    : 0,
});

export const isFiniteNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);

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

export const formatHomeCandlestickPrice = (value?: number | null): string => (
  Number.isFinite(value ?? NaN) ? Number(value).toFixed(2) : '--'
);

export const formatHomeCandlestickVolume = (value?: number | null): string => {
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

export const normalizeHomeCandlestickHistory = (items: StockHistoryPoint[]): CandlePointBase[] => (
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

const getTimeframeSourceHint = (
  timeframe: HomeTimeframeKey,
  language: HomeChartLanguage,
): string | undefined => {
  if (timeframe === '1D') {
    return undefined;
  }
  return language === 'en' ? 'Derived from daily OHLC' : '由日线聚合';
};

const getMaStructure = (candles: CandlePoint[], language: HomeChartLanguage): string | undefined => {
  const latest = [...candles].reverse().find((item) => isFiniteNumber(item.ma5) && isFiniteNumber(item.ma10) && isFiniteNumber(item.ma20));
  if (!latest || latest.ma5 === undefined || latest.ma10 === undefined || latest.ma20 === undefined) {
    return undefined;
  }
  if (latest.ma5 > latest.ma10 && latest.ma10 > latest.ma20) {
    return 'MA5 > MA10 > MA20';
  }
  if (latest.ma5 < latest.ma10 && latest.ma10 < latest.ma20) {
    return 'MA5 < MA10 < MA20';
  }
  return language === 'en' ? 'Mixed MA structure' : '均线结构分化';
};

const getVolumeSupportStatus = (candles: CandlePoint[]): HomeChartVolumeSupportStatus => {
  if (!candles.length) {
    return { available: false, zeroHeavy: true };
  }
  const positiveVolumes = candles.filter((item) => item.volume > 0).length;
  const totalVolume = candles.reduce((sum, item) => sum + item.volume, 0);
  const positiveRatio = positiveVolumes / candles.length;
  return {
    available: positiveVolumes > 0 && totalVolume > 0,
    zeroHeavy: positiveRatio < 0.6 || totalVolume <= 0,
  };
};

const getIndicatorEnabledState = (
  candles: CandlePoint[],
  volumeSupportStatus: HomeChartVolumeSupportStatus,
): HomeChartIndicatorEnabledState => ({
  ma5: candles.some((item) => isFiniteNumber(item.ma5)),
  ma10: candles.some((item) => isFiniteNumber(item.ma10)),
  ma20: candles.some((item) => isFiniteNumber(item.ma20)),
  ma60: candles.some((item) => isFiniteNumber(item.ma60)),
  vwap: volumeSupportStatus.available && candles.some((item) => isFiniteNumber(item.vwap)),
});

export const buildHomeCandlestickChartModel = ({
  dailyCandles,
  timeframe,
  language,
}: BuildHomeCandlestickChartModelArgs): HomeCandlestickChartModel => {
  const candles = withIndicators(aggregateCandles(dailyCandles, timeframe));
  const volumeSupportStatus = getVolumeSupportStatus(candles);
  return {
    candles,
    sourceHint: getTimeframeSourceHint(timeframe, language),
    indicatorEnabledState: getIndicatorEnabledState(candles, volumeSupportStatus),
    volumeSupportStatus,
    maStructure: getMaStructure(candles, language),
  };
};

export const getHomeCandlestickDateLabel = (point: CandlePoint, locale: string): string => (
  point.rangeStart || point.rangeEnd
    ? formatDateRange(point.rangeStart || point.date, point.rangeEnd || point.date, locale)
    : formatDate(point.date, locale)
);

const buildTooltip = (
  point: CandlePoint,
  locale: string,
  enabledIndicators: HomeIndicatorConfig[],
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
    .reduce<string[]>((acc, { label, key }) => {
      const value = point[key];
      if (isFiniteNumber(value)) {
        acc.push(`<div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${label}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatHomeCandlestickPrice(value)}</strong></div>`);
      }
      return acc;
    }, [])
    .join('');

  const reportReferenceRow = isFiniteNumber(reportReferencePrice)
    ? `<div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.reportReferencePrice}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatHomeCandlestickPrice(reportReferencePrice)}</strong></div>`
    : '';

  return `
    <div style="min-width:188px;max-width:248px;padding:8px 10px;font-size:11px;line-height:1.65;">
      <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:5px;"><span style="color:rgba(248,250,252,.48);">${labels.date}</span><strong style="color:rgba(248,250,252,.92);font-weight:600;">${escapeHtml(getHomeCandlestickDateLabel(point, locale))}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.open}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatHomeCandlestickPrice(point.open)}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.high}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatHomeCandlestickPrice(point.high)}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.low}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatHomeCandlestickPrice(point.low)}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.close}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatHomeCandlestickPrice(point.close)}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.volume}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatHomeCandlestickVolume(point.volume)}</strong></div>
      ${reportReferenceRow}
      ${indicatorRows}
    </div>
  `;
};

const resolveHomeCandlestickGrid = (): GridComponentOption[] => [
  {
    ...HOME_CHART_GRID_SAFE_MARGIN,
    top: '19%',
    height: '56%',
  },
  {
    ...HOME_CHART_GRID_SAFE_MARGIN,
    top: '77%',
    height: '12%',
  },
];

export const buildHomeCandlestickChartOption = ({
  candles,
  timeframe,
  currentPrice,
  isCompactChart,
  locale,
  enabledIndicators,
  resolveTooltipPosition,
}: BuildHomeCandlestickChartOptionArgs): HomeChartOption => {
  const dates = candles.map((item) => item.date);
  const visibleStart = timeframe === '1D' && candles.length > 120
    ? Math.round(((candles.length - 120) / candles.length) * 100)
    : 0;
  const safeCurrentPrice = isFiniteNumber(currentPrice) ? currentPrice : undefined;
  const xLabelInterval = Math.max(0, Math.ceil(candles.length / (isCompactChart ? 4 : 7)) - 1);

  return {
    animation: false,
    backgroundColor: 'transparent',
    grid: resolveHomeCandlestickGrid(),
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
        crossStyle: { color: 'rgba(186,194,238,0.46)' },
        label: {
          backgroundColor: 'rgba(9,14,24,0.96)',
          color: 'rgba(248,250,252,0.82)',
          fontSize: 10,
        },
      },
      borderWidth: 1,
      borderColor: 'rgba(166,176,230,0.16)',
      backgroundColor: 'rgba(7,11,19,0.96)',
      borderRadius: 8,
      padding: 0,
      shadowBlur: 18,
      shadowColor: 'rgba(0,0,0,0.34)',
      shadowOffsetX: 0,
      shadowOffsetY: 10,
      extraCssText: 'pointer-events:none;white-space:normal;max-width:min(248px,calc(100vw - 20px));backdrop-filter:blur(10px);',
      textStyle: {
        color: 'rgba(248,250,252,0.86)',
        fontFamily: '"SF Pro Text", "Segoe UI", ui-sans-serif, system-ui, sans-serif',
        fontSize: 11,
        lineHeight: 16,
      },
      position: (point, _params, _dom, _rect, sizeArg) => resolveTooltipPosition(
        point as [number, number],
        sizeArg,
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
        axisLine: { lineStyle: { color: 'rgba(166,176,230,0.13)' } },
        axisTick: { show: false },
        axisLabel: { show: false },
        splitLine: { show: false },
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        boundaryGap: true,
        axisLine: { lineStyle: { color: 'rgba(166,176,230,0.11)' } },
        axisTick: { show: false },
        axisLabel: {
          show: true,
          interval: xLabelInterval,
          hideOverlap: true,
          margin: 8,
          color: 'rgba(213,219,235,0.42)',
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
          color: 'rgba(213,219,235,0.52)',
          fontSize: 10,
          formatter: (value: number) => formatHomeCandlestickPrice(value),
        },
        splitLine: { lineStyle: { color: 'rgba(166,176,230,0.075)' } },
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
          color: 'rgba(213,219,235,0.34)',
          fontSize: 9,
          formatter: (value: number) => formatHomeCandlestickVolume(value),
        },
        splitLine: { lineStyle: { color: 'rgba(166,176,230,0.052)' } },
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
      {
        type: 'slider',
        xAxisIndex: [0, 1],
        start: visibleStart,
        end: 100,
        bottom: 4,
        height: 14,
        borderColor: 'rgba(166,176,230,0.08)',
        backgroundColor: 'rgba(255,255,255,0.02)',
        fillerColor: 'rgba(118,109,219,0.18)',
        dataBackground: {
          lineStyle: { color: 'rgba(186,194,238,0.16)' },
          areaStyle: { color: 'rgba(186,194,238,0.06)' },
        },
        selectedDataBackground: {
          lineStyle: { color: 'rgba(186,194,238,0.28)' },
          areaStyle: { color: 'rgba(118,109,219,0.08)' },
        },
        handleStyle: {
          color: 'rgba(230,236,250,0.88)',
          borderColor: 'rgba(9,14,24,0.92)',
        },
        moveHandleStyle: {
          color: 'rgba(166,176,230,0.18)',
        },
        brushSelect: false,
        showDetail: false,
        filterMode: 'none',
      },
    ],
    series: [
      {
        name: 'OHLC',
        type: 'candlestick',
        data: candles.map((item) => [item.open, item.close, item.low, item.high]),
        itemStyle: {
          color: '#2FC48D',
          color0: '#E76576',
          borderColor: '#2FC48D',
          borderColor0: '#E76576',
        },
        markLine: safeCurrentPrice
          ? {
              symbol: ['none', 'none'],
              silent: true,
              lineStyle: { color: 'rgba(47,196,141,0.58)', type: 'dashed', width: 1 },
              label: {
                color: '#051016',
                backgroundColor: 'rgba(47,196,141,0.92)',
                borderRadius: 3,
                padding: [2, 5],
                formatter: () => formatHomeCandlestickPrice(safeCurrentPrice),
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
            color: item.close >= item.open ? 'rgba(47,196,141,0.28)' : 'rgba(231,101,118,0.28)',
          },
        })),
        barWidth: '58%',
      },
    ],
  };
};

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
