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

type CandlePoint = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma5?: number;
  ma10?: number;
  ma20?: number;
};

type CandlePointBase = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma5?: number;
  ma10?: number;
  ma20?: number;
};

type HomeCandlestickChartProps = {
  ticker: string;
  currentPrice?: number | null;
  isLocked?: boolean;
};

type TooltipPositionSize = {
  contentSize: [number, number];
  viewSize: [number, number];
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

const movingAverage = (values: number[], index: number, length: number): number | undefined => {
  if (index < length - 1) {
    return undefined;
  }
  const slice = values.slice(index - length + 1, index + 1);
  const total = slice.reduce((sum, value) => sum + value, 0);
  return Number((total / length).toFixed(2));
};

const readPointMa = (point: StockHistoryPoint, key: 'ma5' | 'ma10' | 'ma20'): number | undefined => {
  const raw = (point as unknown as Record<string, unknown>)[key]
    ?? (point as unknown as Record<string, unknown>)[key.toUpperCase()];
  return toFiniteNumber(raw);
};

const normalizeCandles = (items: StockHistoryPoint[]): CandlePoint[] => {
  const candles = (items
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
        ma5: readPointMa(item, 'ma5'),
        ma10: readPointMa(item, 'ma10'),
        ma20: readPointMa(item, 'ma20'),
      };
    }) as Array<CandlePointBase | null>)
    .filter((item): item is CandlePointBase => Boolean(item))
    .sort((a, b) => a.date.localeCompare(b.date));

  const closes = candles.map((item) => item.close);
  return candles.map((item, index) => ({
    ...item,
    ma5: item.ma5 ?? movingAverage(closes, index, 5),
    ma10: item.ma10 ?? movingAverage(closes, index, 10),
    ma20: item.ma20 ?? movingAverage(closes, index, 20),
  }));
};

const buildTooltip = (point: CandlePoint, locale: string, reportReferencePrice?: number): string => {
  const isChinese = locale.startsWith('zh');
  const labels = isChinese
    ? {
        open: '开盘',
        high: '最高',
        low: '最低',
        close: '收盘',
        volume: '成交量',
        reportReferencePrice: '报告参考价',
      }
    : {
        open: 'Open',
        high: 'High',
        low: 'Low',
        close: 'Close',
        volume: 'Volume',
        reportReferencePrice: 'Report ref',
      };
  const maRows = [
    ['MA5', point.ma5],
    ['MA10', point.ma10],
    ['MA20', point.ma20],
  ]
    .filter(([, value]) => isFiniteNumber(value))
    .map(([label, value]) => `<div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${label}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatPrice(value as number)}</strong></div>`)
    .join('');

  const reportReferenceRow = isFiniteNumber(reportReferencePrice)
    ? `<div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.reportReferencePrice}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatPrice(reportReferencePrice)}</strong></div>`
    : '';

  return `
    <div style="min-width:188px;max-width:232px;padding:8px 10px;font-size:11px;line-height:1.65;">
      <p style="margin:0 0 5px;color:rgba(248,250,252,.92);font-weight:600;">${escapeHtml(formatDate(point.date, locale))}</p>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.open}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatPrice(point.open)}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.high}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatPrice(point.high)}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.low}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatPrice(point.low)}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.close}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatPrice(point.close)}</strong></div>
      <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(248,250,252,.48);">${labels.volume}</span><strong style="color:rgba(248,250,252,.86);font-weight:600;">${formatVolume(point.volume)}</strong></div>
      ${reportReferenceRow}
      ${maRows}
    </div>
  `;
};

export const HomeCandlestickChart: React.FC<HomeCandlestickChartProps> = ({
  ticker,
  currentPrice,
  isLocked = false,
}) => {
  const { language } = useI18n();
  const locale = language === 'zh' ? 'zh-CN' : 'en-US';
  const { ref: sizeRef, size } = useElementSize<HTMLDivElement>();
  const chartNodeRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<ECharts | null>(null);
  const [candles, setCandles] = useState<CandlePoint[]>([]);
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'unavailable'>('idle');
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const loadCandles = async () => {
      const normalizedTicker = String(ticker || '').trim().toUpperCase();
      if (!normalizedTicker || isLocked) {
        setCandles([]);
        setStatus('unavailable');
        return;
      }
      setStatus('loading');
      setCandles([]);
      try {
        const response = await stocksApi.getHistory(normalizedTicker, { period: 'daily', days: 180 });
        if (cancelled) {
          return;
        }
        const normalized = normalizeCandles(response.data || []);
        setCandles(normalized);
        setStatus(normalized.length ? 'ready' : 'unavailable');
      } catch {
        if (!cancelled) {
          setCandles([]);
          setStatus('unavailable');
        }
      }
    };

    void loadCandles();
    return () => {
      cancelled = true;
    };
  }, [isLocked, ticker]);

  const option = useMemo<HomeChartOption | null>(() => {
    if (!candles.length) {
      return null;
    }
    const dates = candles.map((item) => item.date);
    const maSeries = [
      { key: 'ma5' as const, name: 'MA5', color: '#38BDF8' },
      { key: 'ma10' as const, name: 'MA10', color: '#F59E0B' },
      { key: 'ma20' as const, name: 'MA20', color: '#8B5CF6' },
    ].filter(({ key }) => candles.some((item) => isFiniteNumber(item[key])));
    const visibleStart = candles.length > 90 ? Math.round(((candles.length - 90) / candles.length) * 100) : 0;
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
          crossStyle: { color: 'rgba(226,232,240,0.52)' },
          label: {
            backgroundColor: 'rgba(8,12,18,0.95)',
            color: 'rgba(248,250,252,0.82)',
            fontSize: 10,
          },
        },
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.10)',
        backgroundColor: 'rgba(6,10,16,0.96)',
        borderRadius: 6,
        padding: 0,
        shadowBlur: 18,
        shadowColor: 'rgba(0,0,0,0.34)',
        shadowOffsetX: 0,
        shadowOffsetY: 10,
        extraCssText: 'pointer-events:none;white-space:normal;max-width:min(232px,calc(100vw - 20px));backdrop-filter:blur(10px);',
        textStyle: {
          color: 'rgba(248,250,252,0.86)',
          fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif',
          fontSize: 11,
          lineHeight: 16,
        },
        position: (point, _params, _dom, _rect, size) => resolveHomeCandlestickTooltipPosition(
          point as [number, number],
          size,
          chartNodeRef.current?.getBoundingClientRect(),
        ),
        formatter: (params: unknown) => {
          const first = Array.isArray(params) ? params[0] as { dataIndex?: number } | undefined : undefined;
          const point = first?.dataIndex != null ? candles[first.dataIndex] : undefined;
          return point ? buildTooltip(point, locale, safeCurrentPrice) : '';
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
          axisLine: { lineStyle: { color: 'rgba(255,255,255,0.10)' } },
          axisTick: { show: false },
          axisLabel: {
            show: false,
            color: 'rgba(255,255,255,0.42)',
            fontSize: 10,
            formatter: (value: string) => {
              const date = new Date(value);
              if (Number.isNaN(date.getTime())) return value;
              return date.toLocaleDateString(locale, { month: 'short', day: 'numeric' });
            },
          },
          splitLine: { show: false },
        },
        {
          type: 'category',
          gridIndex: 1,
          data: dates,
          boundaryGap: true,
          axisLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
          axisTick: { show: false },
          axisLabel: {
            show: true,
            interval: xLabelInterval,
            hideOverlap: true,
            margin: 8,
            color: 'rgba(255,255,255,0.36)',
            fontSize: isCompactChart ? 9 : 10,
            formatter: (value: string) => {
              const date = new Date(value);
              if (Number.isNaN(date.getTime())) return value;
              return date.toLocaleDateString(locale, { month: 'short', day: 'numeric' });
            },
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
            color: 'rgba(255,255,255,0.46)',
            fontSize: 10,
            formatter: (value: number) => formatPrice(value),
          },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.055)' } },
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
            color: 'rgba(255,255,255,0.28)',
            fontSize: 9,
            formatter: (value: number) => formatVolume(value),
          },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
        },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: visibleStart, end: 100, minValueSpan: 20, filterMode: 'none' },
      ],
      series: [
        {
          name: 'OHLC',
          type: 'candlestick',
          data: candles.map((item) => [item.open, item.close, item.low, item.high]),
          itemStyle: {
            color: '#34D399',
            color0: '#FB7185',
            borderColor: '#34D399',
            borderColor0: '#FB7185',
          },
          markLine: safeCurrentPrice
            ? {
                symbol: ['none', 'none'],
                silent: true,
                lineStyle: { color: 'rgba(52,211,153,0.58)', type: 'dashed', width: 1 },
                label: {
                  color: '#051016',
                  backgroundColor: 'rgba(52,211,153,0.92)',
                  borderRadius: 3,
                  padding: [2, 5],
                  formatter: () => formatPrice(safeCurrentPrice),
                },
                data: [{ yAxis: safeCurrentPrice }],
              }
            : undefined,
        },
        ...maSeries.map(({ key, name, color }) => ({
          name,
          type: 'line' as const,
          data: candles.map((item) => item[key] ?? null),
          smooth: true,
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 1.35, color, opacity: key === 'ma20' ? 0.66 : 0.86 },
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
              color: item.close >= item.open ? 'rgba(52,211,153,0.34)' : 'rgba(251,113,133,0.34)',
            },
          })),
          barWidth: '58%',
        },
      ],
    };
  }, [candles, currentPrice, locale, size.width]);

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

  const hoveredCandle = hoveredIndex != null ? candles[hoveredIndex] : null;
  const hasMa5 = candles.some((item) => isFiniteNumber(item.ma5));
  const hasMa10 = candles.some((item) => isFiniteNumber(item.ma10));
  const hasMa20 = candles.some((item) => isFiniteNumber(item.ma20));

  return (
    <div
      ref={sizeRef}
      className="min-w-0 rounded-md border border-white/[0.055] bg-[#070b10]/82 px-3 py-3"
      data-testid="home-linear-technical-chart"
      data-chart-engine="echarts"
      data-chart-source="stocks-history-daily"
      data-axis-layout="split-price-volume"
      data-x-axis-density="sampled"
      data-tooltip-container="body"
      data-tooltip-bounds="viewport"
    >
      <div className="mb-2 flex min-w-0 items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-[10px] font-medium text-white/46">
          <span className="rounded bg-white/[0.08] px-2 py-1 text-white/82">{language === 'en' ? 'Daily' : '日K'}</span>
          <span className="hidden text-white/34 sm:inline">{ticker}</span>
        </div>
        <div className="flex min-w-0 flex-wrap items-center justify-end gap-x-3 gap-y-1 text-[10px] text-white/38">
          {hasMa5 ? <span><span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-[#38BDF8]" />MA5</span> : null}
          {hasMa10 ? <span><span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-[#F59E0B]" />MA10</span> : null}
          {hasMa20 ? <span><span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-[#8B5CF6]" />MA20</span> : null}
        </div>
      </div>
      {status === 'ready' ? (
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
            aria-label={language === 'en' ? 'Interactive daily OHLC candlestick chart' : '可交互日线 OHLC K线图'}
            data-testid="home-candlestick-echarts-node"
          />
          {hoveredCandle ? (
            <div
              className="sr-only"
              data-testid="home-candlestick-hover-tooltip"
              role="status"
              aria-live="polite"
            >
              <p className="font-medium text-white/88">{formatDate(hoveredCandle.date, locale)}</p>
              <p>
                {language === 'en'
                  ? `Open ${formatPrice(hoveredCandle.open)} · High ${formatPrice(hoveredCandle.high)} · Low ${formatPrice(hoveredCandle.low)} · Close ${formatPrice(hoveredCandle.close)}`
                  : `开盘 ${formatPrice(hoveredCandle.open)} · 最高 ${formatPrice(hoveredCandle.high)} · 最低 ${formatPrice(hoveredCandle.low)} · 收盘 ${formatPrice(hoveredCandle.close)}`}
              </p>
              <p>{language === 'en' ? 'Volume' : '成交量'} {formatVolume(hoveredCandle.volume)}</p>
              {isFiniteNumber(currentPrice) ? (
                <p>{language === 'en' ? 'Report ref' : '报告参考价'} {formatPrice(currentPrice)}</p>
              ) : null}
              <p className="text-white/48">
                {[
                  hoveredCandle.ma5 ? `MA5 ${formatPrice(hoveredCandle.ma5)}` : null,
                  hoveredCandle.ma10 ? `MA10 ${formatPrice(hoveredCandle.ma10)}` : null,
                  hoveredCandle.ma20 ? `MA20 ${formatPrice(hoveredCandle.ma20)}` : null,
                ].filter(Boolean).join(' · ')}
              </p>
            </div>
          ) : null}
        </div>
      ) : (
        <div
          className={cn(
            'flex h-[228px] min-w-[280px] flex-col items-center justify-center rounded border border-white/[0.045] bg-white/[0.012] px-4 text-center sm:h-[238px] lg:h-[246px]',
            status === 'loading' ? 'text-white/46' : 'text-white/42',
          )}
          data-testid="home-candlestick-unavailable"
        >
          <p className="text-sm font-medium">{status === 'loading' ? (language === 'en' ? 'Loading daily candles...' : '正在加载日线K线...') : 'K线数据暂不可用'}</p>
          {status !== 'loading' ? (
            <p className="mt-2 max-w-xs text-xs leading-5 text-white/34">
              {language === 'en' ? 'Daily OHLC history was not returned for this ticker.' : '当前标的未返回可用的日线 OHLC 数据。'}
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
};
