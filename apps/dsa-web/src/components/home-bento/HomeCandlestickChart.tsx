import type React from 'react';
import { useEffect, useRef, useState } from 'react';
import * as echarts from 'echarts/core';
import { BarChart, CandlestickChart, LineChart } from 'echarts/charts';
import {
  DataZoomComponent,
  GridComponent,
  TooltipComponent,
} from 'echarts/components';
import type { ECharts, SetOptionOpts } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import {
  stocksApi,
  type StockHistoryDiagnostics,
  type StockHistorySourceConfidence,
} from '../../api/stocks';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useElementSize } from '../../hooks/useElementSize';
import { cn } from '../../utils/cn';
import {
  HomeCandlestickChartContextBadges,
  HomeCandlestickChartIndicatorChips,
  HomeCandlestickChartTimeframeStrip,
  HomeCandlestickChartUnavailablePanel,
} from './HomeCandlestickChartDisplay';
import {
  buildHomeCandlestickChartModel,
  buildHomeCandlestickChartOption,
  formatHomeCandlestickPrice,
  formatHomeCandlestickVolume,
  getHomeCandlestickDateLabel,
  isFiniteNumber,
  normalizeHomeCandlestickHistory,
  resolveHomeCandlestickTooltipPosition,
  type CandlePointBase,
  type HomeChartOption,
  type HomeIndicatorConfig,
  type HomeIndicatorKey,
  type HomeTimeframeKey,
} from './homeCandlestickChartUtils';

echarts.use([
  CandlestickChart,
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  CanvasRenderer,
]);

type HomeHistoryAvailabilityMeta = {
  rawRows: number;
  source?: string | null;
  diagnostics?: StockHistoryDiagnostics | null;
  sourceConfidence?: StockHistorySourceConfidence | null;
};

type UnavailableProductState = {
  status: string;
  title: string;
  body?: string | null;
};

type HomeCandlestickChartProps = {
  ticker: string;
  currentPrice?: number | null;
  isLocked?: boolean;
  onContextChange?: (context: HomeCandlestickChartContext | null) => void;
  className?: string;
  style?: React.CSSProperties;
};

export type HomeCandlestickChartContext = {
  timeframe: HomeTimeframeKey;
  sourceHint?: string;
};

type TimeframeOption = {
  key: HomeTimeframeKey;
  label: HomeTimeframeKey;
  description: string;
};

const TIMEFRAME_OPTIONS: TimeframeOption[] = [
  { key: '1D', label: '1D', description: 'Daily candles' },
  { key: '1W', label: '1W', description: 'Weekly candles derived from daily OHLC' },
  { key: '1M', label: '1M', description: 'Monthly candles derived from daily OHLC' },
];

const INDICATOR_CONFIGS: HomeIndicatorConfig[] = [
  { key: 'ma5', label: 'MA5', color: '#38BDF8' },
  { key: 'ma10', label: 'MA10', color: '#F59E0B' },
  { key: 'ma20', label: 'MA20', color: '#8B5CF6' },
  { key: 'ma60', label: 'MA60', color: '#EC4899' },
  { key: 'vwap', label: 'VWAP', color: '#22C55E' },
];

const DEFAULT_INDICATORS: Record<HomeIndicatorKey, boolean> = {
  ma5: true,
  ma10: true,
  ma20: true,
  ma60: false,
  vwap: false,
};

type ChartInteractionState = {
  ticker: string;
  activeTimeframe: HomeTimeframeKey;
  hoveredIndex: number | null;
  indicatorVisibility: Record<HomeIndicatorKey, boolean>;
};

const buildDefaultInteractionState = (ticker: string): ChartInteractionState => ({
  ticker,
  activeTimeframe: '1D',
  hoveredIndex: null,
  indicatorVisibility: DEFAULT_INDICATORS,
});

const getHomeCandlestickChartRect = (): Pick<DOMRect, 'left' | 'top'> | null => {
  if (typeof document === 'undefined') {
    return null;
  }
  const node = document.querySelector<HTMLElement>('[data-testid="home-candlestick-echarts-node"]');
  if (!node) {
    return null;
  }
  const rect = node.getBoundingClientRect();
  return { left: rect.left, top: rect.top };
};

const buildUnavailableProductState = (
  language: 'zh' | 'en',
  reason: 'history' | 'volume',
): UnavailableProductState => {
  if (reason === 'volume') {
    return {
      status: language === 'en' ? 'UNAVAILABLE' : '暂不可用',
      title: language === 'en'
        ? 'The chart is unavailable because reliable volume data is missing.'
        : '缺少可靠成交量，图表暂不可用。',
      body: language === 'en'
        ? 'Try again after volume history is available.'
        : '请在成交量历史可用后重试。',
    };
  }
  return {
    status: language === 'en' ? 'UNAVAILABLE' : '暂不可用',
    title: language === 'en'
      ? 'The candlestick chart is temporarily unavailable. Please try again shortly.'
      : '行情图表暂不可用，请稍后重试。',
    body: null,
  };
};

export const HomeCandlestickChart: React.FC<HomeCandlestickChartProps> = ({
  ticker,
  currentPrice,
  isLocked = false,
  onContextChange,
  className,
  style,
}) => {
  const { language } = useI18n();
  const locale = language === 'zh' ? 'zh-CN' : 'en-US';
  const { ref: sizeRef, size } = useElementSize<HTMLDivElement>();
  const chartNodeRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<ECharts | null>(null);
  const [dailyCandles, setDailyCandles] = useState<CandlePointBase[]>([]);
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'unavailable'>('idle');
  const [historyMeta, setHistoryMeta] = useState<HomeHistoryAvailabilityMeta | null>(null);
  const [interactionState, setInteractionState] = useState<ChartInteractionState>(() => buildDefaultInteractionState(ticker));

  useEffect(() => {
    let cancelled = false;
    const loadCandles = async () => {
      const normalizedTicker = String(ticker || '').trim().toUpperCase();
      if (!normalizedTicker || normalizedTicker === '-' || isLocked) {
        setDailyCandles([]);
        setHistoryMeta(null);
        setStatus('unavailable');
        return;
      }
      setStatus('loading');
      setDailyCandles([]);
      setHistoryMeta(null);
      try {
        const response = await stocksApi.getHistory(normalizedTicker, { period: 'daily', days: 365 });
        if (cancelled) {
          return;
        }
        const normalized = normalizeHomeCandlestickHistory(response.data || []);
        setHistoryMeta({
          rawRows: Array.isArray(response.data) ? response.data.length : 0,
          source: response.source ?? null,
          diagnostics: response.diagnostics ?? null,
          sourceConfidence: response.sourceConfidence ?? null,
        });
        setDailyCandles(normalized);
        setStatus(normalized.length ? 'ready' : 'unavailable');
      } catch {
        if (!cancelled) {
          setDailyCandles([]);
          setHistoryMeta({
            rawRows: 0,
            source: 'unavailable',
            diagnostics: {
              status: 'unavailable',
              reason: 'history_request_failed',
            },
            sourceConfidence: {
              source: 'unavailable',
              freshness: 'unavailable',
              isUnavailable: true,
            },
          });
          setStatus('unavailable');
        }
      }
    };

    void loadCandles();
    return () => {
      cancelled = true;
    };
  }, [isLocked, ticker]);

  const effectiveInteractionState = interactionState.ticker === ticker
    ? interactionState
    : buildDefaultInteractionState(ticker);
  const { activeTimeframe, hoveredIndex, indicatorVisibility } = effectiveInteractionState;

  const {
    candles,
    sourceHint,
    indicatorEnabledState,
    volumeSupportStatus: vwapStatus,
    maStructure,
  } = buildHomeCandlestickChartModel({
    dailyCandles,
    timeframe: activeTimeframe,
    language: language === 'en' ? 'en' : 'zh',
  });
  const enabledIndicators = INDICATOR_CONFIGS.filter(({ key }) => indicatorVisibility[key] && indicatorEnabledState[key]);
  const viewportWidth = typeof window !== 'undefined'
    ? window.innerWidth || document.documentElement.clientWidth || 0
    : 0;
  const isCompactChart = (size.width > 0 ? size.width : viewportWidth) < 520;
  const hasRenderableChart = status === 'ready' && candles.length > 0 && vwapStatus.available;
  const latestCandle = candles[candles.length - 1];
  const unavailableState = buildUnavailableProductState(
    language === 'en' ? 'en' : 'zh',
    status === 'ready' && candles.length > 0 && !vwapStatus.available ? 'volume' : 'history',
  );

  useEffect(() => {
    if (!hasRenderableChart) {
      onContextChange?.(null);
      return;
    }
    onContextChange?.({
      timeframe: activeTimeframe,
      sourceHint,
    });
  }, [activeTimeframe, hasRenderableChart, onContextChange, sourceHint]);

  const option: HomeChartOption | null = (() => {
    if (!hasRenderableChart) {
      return null;
    }
    return buildHomeCandlestickChartOption({
      candles,
      timeframe: activeTimeframe,
      currentPrice,
      isCompactChart,
      locale,
      enabledIndicators,
      resolveTooltipPosition: (point, sizeArg) => resolveHomeCandlestickTooltipPosition(
        point,
        sizeArg,
        getHomeCandlestickChartRect(),
      ),
    });
  })();

  useEffect(() => {
    const host = chartNodeRef.current;
    if (!host || !option || size.width <= 0 || size.height <= 0) {
      return undefined;
    }
    const instance = chartRef.current ?? echarts.init(host, undefined, { renderer: 'canvas' });
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

  const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!candles.length) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const width = rect.width || 1;
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / width));
    setInteractionState((current) => {
      const base = current.ticker === ticker ? current : buildDefaultInteractionState(ticker);
      return {
        ...base,
        hoveredIndex: Math.round(ratio * (candles.length - 1)),
      };
    });
  };

  const handleTimeframeChange = (nextTimeframe: HomeTimeframeKey) => {
    setInteractionState((current) => {
      const base = current.ticker === ticker ? current : buildDefaultInteractionState(ticker);
      return {
        ...base,
        activeTimeframe: nextTimeframe,
        hoveredIndex: null,
      };
    });
  };

  const handleIndicatorToggle = (key: HomeIndicatorKey) => {
    if (!indicatorEnabledState[key]) {
      return;
    }
    setInteractionState((current) => {
      const base = current.ticker === ticker ? current : buildDefaultInteractionState(ticker);
      return {
        ...base,
        indicatorVisibility: {
          ...base.indicatorVisibility,
          [key]: !base.indicatorVisibility[key],
        },
      };
    });
  };

  const hoveredCandle = hoveredIndex != null ? candles[hoveredIndex] : null;
  const enabledIndicatorLabels = enabledIndicators.map((item) => item.label).join(',');
  const timeframeControls = TIMEFRAME_OPTIONS.map((optionItem) => ({
    ...optionItem,
    pressed: activeTimeframe === optionItem.key,
    disabled: status !== 'ready',
  }));
  const indicatorChips = INDICATOR_CONFIGS.map(({ key, label, color }) => ({
    key,
    label,
    color,
    pressed: indicatorVisibility[key] && indicatorEnabledState[key],
    available: indicatorEnabledState[key],
    title: key === 'ma60' && !indicatorEnabledState[key]
      ? (language === 'en' ? 'MA60 needs more history' : 'MA60 需要更多历史 K 线')
      : key === 'vwap' && !indicatorEnabledState[key]
        ? (language === 'en' ? 'VWAP needs reliable volume' : 'VWAP 需要可靠成交量')
        : label,
  }));
  const priceContextLabel = language === 'en'
    ? `Price ${formatHomeCandlestickPrice(latestCandle?.close)}`
    : `价格 ${formatHomeCandlestickPrice(latestCandle?.close)}`;
  const volumeContextLabel = language === 'en'
    ? `Volume ${formatHomeCandlestickVolume(latestCandle?.volume)}`
    : `成交量 ${formatHomeCandlestickVolume(latestCandle?.volume)}`;
  const rangeHintLabel = language === 'en' ? 'Zoom to inspect range' : '缩放查看区间';
  const chartUnavailableTitle = status === 'loading'
    ? (language === 'en' ? 'Loading candles...' : '正在加载 K 线...')
    : unavailableState.title;
  const chartUnavailableBody = status === 'loading'
    ? null
    : unavailableState.body;
  const chartUnavailableStatus = status === 'loading'
    ? (language === 'en' ? 'UPDATING' : '数据更新中')
    : unavailableState.status;
  const chartUnavailableTimeframe = language === 'en' ? `Timeframe ${activeTimeframe}` : `当前周期 ${activeTimeframe}`;
  const shouldExposeHistoryDiagnostics = hasRenderableChart;

  return (
    <div
      ref={sizeRef}
      className={cn(
        'home-chart-well min-w-0 rounded-[14px] border border-[color:var(--wolfy-border-faint)] bg-[var(--wolfy-surface-inset)] px-3 py-2.5 shadow-[var(--wolfy-shadow-panel)]',
        className,
      )}
      style={style}
      data-testid="home-linear-technical-chart"
      data-visual-role="primary-chart"
      data-surface-system="reflect-linear-console"
      data-chart-engine="echarts"
      data-chart-source={activeTimeframe === '1D' ? 'stocks-history-daily' : 'stocks-history-daily-aggregated'}
      data-chart-timeframe={activeTimeframe}
      data-chart-points={String(candles.length)}
      data-history-source={shouldExposeHistoryDiagnostics ? historyMeta?.source || 'unknown' : undefined}
      data-history-status={shouldExposeHistoryDiagnostics ? historyMeta?.diagnostics?.status || 'unknown' : undefined}
      data-history-confidence={shouldExposeHistoryDiagnostics ? historyMeta?.sourceConfidence?.freshness || 'unknown' : undefined}
      data-enabled-indicators={enabledIndicatorLabels}
      data-vwap-available={String(indicatorEnabledState.vwap)}
      data-volume-panel={String(hasRenderableChart)}
      data-datazoom-mode="inside"
      data-compact-chart={String(isCompactChart)}
      data-axis-layout="split-price-volume"
      data-x-axis-density="sampled"
      data-tooltip-container="body"
      data-tooltip-bounds="viewport"
    >
      <div className="mb-2.5 flex min-w-0 flex-col gap-2.5">
        <HomeCandlestickChartTimeframeStrip
          controls={timeframeControls}
          ticker={ticker}
          sourceHint={sourceHint}
          maStructure={maStructure}
          onSelect={(key) => handleTimeframeChange(key as HomeTimeframeKey)}
        />

        <HomeCandlestickChartIndicatorChips
          chips={indicatorChips}
          vwapUnavailableLabel={!indicatorEnabledState.vwap && vwapStatus.zeroHeavy
            ? (language === 'en' ? 'VWAP unavailable' : 'VWAP 暂不可用')
            : null}
          onToggle={(key) => handleIndicatorToggle(key as HomeIndicatorKey)}
        />

        <HomeCandlestickChartContextBadges
          priceLabel={priceContextLabel}
          volumeLabel={volumeContextLabel}
          rangeHintLabel={rangeHintLabel}
        />
      </div>

      {hasRenderableChart ? (
        <div
          className="relative h-[304px] min-w-0 max-w-full overflow-visible sm:h-[336px] xl:h-[360px]"
          data-testid="home-candlestick-chart-frame"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => {
            setInteractionState((current) => {
              const base = current.ticker === ticker ? current : buildDefaultInteractionState(ticker);
              return {
                ...base,
                hoveredIndex: null,
              };
            });
          }}
        >
          <figure
            ref={chartNodeRef}
            className="size-full min-h-full min-w-0"
            aria-label={language === 'en' ? `Interactive ${activeTimeframe} OHLC candlestick chart` : `可交互 ${activeTimeframe} OHLC K 线图`}
            data-testid="home-candlestick-echarts-node"
          />
          {hoveredCandle ? (
            <output
              className="sr-only"
              data-testid="home-candlestick-hover-tooltip"
              aria-live="polite"
            >
              <p className="font-medium text-white/88">
                {language === 'en' ? 'Date' : '日期'} {getHomeCandlestickDateLabel(hoveredCandle, locale)}
              </p>
              <p>
                {language === 'en'
                  ? `Open ${formatHomeCandlestickPrice(hoveredCandle.open)} · High ${formatHomeCandlestickPrice(hoveredCandle.high)} · Low ${formatHomeCandlestickPrice(hoveredCandle.low)} · Close ${formatHomeCandlestickPrice(hoveredCandle.close)}`
                  : `开盘 ${formatHomeCandlestickPrice(hoveredCandle.open)} · 最高 ${formatHomeCandlestickPrice(hoveredCandle.high)} · 最低 ${formatHomeCandlestickPrice(hoveredCandle.low)} · 收盘 ${formatHomeCandlestickPrice(hoveredCandle.close)}`}
              </p>
              <p>{language === 'en' ? 'Volume' : '成交量'} {formatHomeCandlestickVolume(hoveredCandle.volume)}</p>
              {isFiniteNumber(currentPrice) ? (
                <p>{language === 'en' ? 'Report ref' : '报告参考价'} {formatHomeCandlestickPrice(currentPrice)}</p>
              ) : null}
              {enabledIndicators.length ? (
                <p className="text-white/48">
                  {enabledIndicators
                    .reduce<string[]>((acc, { key, label }) => {
                      if (isFiniteNumber(hoveredCandle[key])) acc.push(`${label} ${formatHomeCandlestickPrice(hoveredCandle[key])}`);
                      return acc;
                    }, [])
                    .join(' · ')}
                </p>
              ) : null}
            </output>
          ) : null}
        </div>
      ) : (
        <HomeCandlestickChartUnavailablePanel
          statusLabel={chartUnavailableStatus}
          timeframeLabel={chartUnavailableTimeframe}
          title={chartUnavailableTitle}
          body={chartUnavailableBody}
          isLoading={status === 'loading'}
        />
      )}
    </div>
  );
};
