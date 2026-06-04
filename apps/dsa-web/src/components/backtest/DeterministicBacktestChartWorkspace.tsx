import type React from 'react';
import { useEffect, useRef, useState } from 'react';
import * as echarts from 'echarts/core';
import { BarChart, LineChart } from 'echarts/charts';
import type { ComposeOption, ECharts, SetOptionOpts } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import {
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
} from 'echarts/components';
import type { BarSeriesOption, LineSeriesOption } from 'echarts/charts';
import type {
  GridComponentOption,
  TooltipComponentOption,
  DataZoomComponentOption,
} from 'echarts/components';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useElementSize } from '../../hooks/useElementSize';
import { translate } from '../../i18n/core';
import type { DeterministicResultDensityConfig } from './deterministicResultDensity';
import type { RuleBacktestRunResponse } from '../../types/backtest';
import type {
  DeterministicBacktestNormalizedResult,
  DeterministicBacktestNormalizedRow,
} from './normalizeDeterministicBacktestResult';


echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, DataZoomComponent, CanvasRenderer]);

type BacktestLanguage = 'zh' | 'en';
type EChartsOption = ComposeOption<
  | LineSeriesOption
  | BarSeriesOption
  | GridComponentOption
  | TooltipComponentOption
  | DataZoomComponentOption
>;

function ctw(language: BacktestLanguage, key: string, vars?: Record<string, string | number | undefined>): string {
  return translate(language, `backtest.resultPage.chartWorkspace.${key}`, vars);
}

function formatDateLabel(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value || '--';
  return `${match[2]}-${match[3]}`;
}

function formatSignedPercent(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return '--';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(digits)}%`;
}

function formatSignedNumber(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return '--';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(digits)}`;
}

function formatCompactNumber(value: number | null | undefined, language: BacktestLanguage): string {
  if (value == null || Number.isNaN(value)) return '--';
  const sign = value > 0 ? '+' : value < 0 ? '-' : '';
  const abs = Math.abs(value);
  if (language === 'zh') {
    if (abs >= 10000) return `${sign}${(abs / 10000).toFixed(abs >= 100000 ? 0 : 1)}万`;
    if (abs >= 1000) return `${sign}${(abs / 1000).toFixed(abs >= 10000 ? 0 : 1)}k`;
    return `${sign}${abs.toFixed(abs >= 100 ? 0 : 1)}`;
  }
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(abs >= 10_000_000 ? 0 : 1)}m`;
  if (abs >= 1_000) return `${sign}${(abs / 1_000).toFixed(abs >= 10_000 ? 0 : 1)}k`;
  return `${sign}${abs.toFixed(abs >= 100 ? 0 : 1)}`;
}

function getEquityValue(row: DeterministicBacktestNormalizedRow): number | null {
  if (typeof row.totalValue === 'number' && Number.isFinite(row.totalValue)) return row.totalValue;
  if (typeof row.holdingsValue === 'number' && Number.isFinite(row.holdingsValue) && typeof row.cash === 'number' && Number.isFinite(row.cash)) {
    return row.holdingsValue + row.cash;
  }
  return null;
}

function getDateRangeLabel(rows: DeterministicBacktestNormalizedRow[]): string {
  if (!rows.length) return '--';
  const first = rows[0]?.date ?? '--';
  const last = rows[rows.length - 1]?.date ?? '--';
  return `${first} → ${last}`;
}

export const DeterministicBacktestChartWorkspace: React.FC<{
  normalized: DeterministicBacktestNormalizedResult;
  run: RuleBacktestRunResponse;
  densityConfig: DeterministicResultDensityConfig;
}> = ({ normalized, run, densityConfig }) => {
  const { language } = useI18n();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<ECharts | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { ref: sizeRef, size } = useElementSize();
  const width = size.width;
  const height = size.height;
  const rows = normalized.rows;

  const benchmarkLabel = normalized.benchmarkMeta.showBenchmark
    ? normalized.benchmarkMeta.benchmarkLabel
    : (language === 'en' ? 'No benchmark' : '无基准');
  const metaStrip = [
    { label: language === 'en' ? 'Date window' : '回测区间', value: getDateRangeLabel(rows) },
    { label: language === 'en' ? 'Initial capital' : '初始本金', value: formatCompactNumber(run.initialCapital, language) },
    { label: language === 'en' ? 'Benchmark' : '基准模式', value: benchmarkLabel },
    { label: language === 'en' ? 'Lookback' : '回看窗口', value: `${run.lookbackBars ?? '--'}` },
    { label: language === 'en' ? 'Costs' : '交易成本', value: `${run.feeBps ?? 0} / ${run.slippageBps ?? 0} bps` },
  ];

  const option: EChartsOption = (() => {
    const dates = rows.map((row) => row.date);
    const equitySeries = rows.map((row) => getEquityValue(row));
    const drawdownSeries = rows.map((row) => {
      if (row.drawdownPct == null || Number.isNaN(row.drawdownPct)) return null;
      return row.drawdownPct > 0 ? -row.drawdownPct : row.drawdownPct;
    });
    const pnlSeries = rows.map((row) => row.dailyPnl ?? 0);
    const startValue = Math.max(0, dates.length - Math.min(dates.length, densityConfig.mode === 'dense' ? 140 : 110));
    const tooltipLabels = {
      date: language === 'en' ? 'Date' : '日期',
      equity: language === 'en' ? 'Equity' : '权益',
      drawdown: language === 'en' ? 'Drawdown' : '回撤',
      pnl: language === 'en' ? 'Daily P&L' : '当日盈亏',
    };

    return {
      animation: false,
      backgroundColor: 'transparent',
      grid: [
        { left: 64, right: 20, top: 20, height: '42%' },
        { left: 64, right: 20, top: '49%', height: '18%' },
        { left: 64, right: 20, top: '73%', height: '18%' },
      ],
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(7, 10, 18, 0.88)',
        borderColor: 'rgba(255,255,255,0.08)',
        borderWidth: 1,
        padding: 16,
        textStyle: {
          color: '#f5f7fb',
          fontSize: 12,
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        },
        extraCssText: 'border-radius:18px;box-shadow:0 20px 60px rgba(0,0,0,0.45);backdrop-filter:blur(16px);',
        axisPointer: {
          type: 'cross',
          lineStyle: {
            color: 'rgba(255,255,255,0.22)',
            width: 1,
            type: 'solid',
          },
          crossStyle: {
            color: 'rgba(255,255,255,0.22)',
          },
          label: {
            backgroundColor: 'rgba(10,12,20,0.94)',
            color: '#f5f7fb',
          },
        },
        formatter: (params: unknown) => {
          const items = Array.isArray(params) ? params : [params];
          const first = items[0] as { axisValue?: string } | undefined;
          const date = first?.axisValue ?? '--';
          const index = Math.max(0, dates.indexOf(date));
          const equity = equitySeries[index];
          const drawdown = drawdownSeries[index];
          const pnl = pnlSeries[index];
          return [
            `<div style="font-size:11px;color:rgba(255,255,255,0.58);margin-bottom:10px;">${tooltipLabels.date}</div>`,
            `<div style="font-size:15px;font-weight:600;margin-bottom:12px;">${date}</div>`,
            `<div style="display:grid;grid-template-columns:auto auto;gap:8px 18px;">`,
            `<span style="color:rgba(255,255,255,0.64);">${tooltipLabels.equity}</span><span style="text-align:right;color:#7dd3fc;">${formatCompactNumber(equity, language)}</span>`,
            `<span style="color:rgba(255,255,255,0.64);">${tooltipLabels.drawdown}</span><span style="text-align:right;color:#fb7185;">${formatSignedPercent(drawdown)}</span>`,
            `<span style="color:rgba(255,255,255,0.64);">${tooltipLabels.pnl}</span><span style="text-align:right;color:${(pnl ?? 0) >= 0 ? '#34d399' : '#fb7185'};">${formatSignedNumber(pnl)}</span>`,
            `</div>`,
          ].join('');
        },
      },
      axisPointer: {
        link: [{ xAxisIndex: 'all' }],
      },
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1, 2],
          startValue,
          endValue: dates.length - 1,
          minSpan: 5,
          zoomLock: false,
          moveOnMouseWheel: true,
        },
      ],
      xAxis: [
        {
          type: 'category',
          boundaryGap: false,
          data: dates,
          gridIndex: 0,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false },
        },
        {
          type: 'category',
          boundaryGap: true,
          data: dates,
          gridIndex: 1,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false },
        },
        {
          type: 'category',
          boundaryGap: true,
          data: dates,
          gridIndex: 2,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            color: 'rgba(255,255,255,0.42)',
            margin: 14,
            formatter: (value: string) => formatDateLabel(value),
          },
          splitLine: { show: false },
        },
      ],
      yAxis: [
        {
          type: 'value',
          gridIndex: 0,
          scale: true,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            color: 'rgba(255,255,255,0.42)',
            formatter: (value: number) => formatCompactNumber(value, language),
          },
          splitLine: { show: false },
        },
        {
          type: 'value',
          gridIndex: 1,
          scale: true,
          max: 0,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            color: 'rgba(255,255,255,0.35)',
            formatter: (value: number) => `${value.toFixed(0)}%`,
          },
          splitLine: { show: false },
        },
        {
          type: 'value',
          gridIndex: 2,
          scale: true,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            color: 'rgba(255,255,255,0.35)',
            formatter: (value: number) => formatCompactNumber(value, language),
          },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: tooltipLabels.equity,
          type: 'line',
          xAxisIndex: 0,
          yAxisIndex: 0,
          smooth: 0.16,
          symbol: 'none',
          data: equitySeries,
          lineStyle: {
            width: 2.5,
            color: '#7dd3fc',
            shadowBlur: 12,
            shadowColor: 'rgba(125,211,252,0.45)',
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(125,211,252,0.18)' },
              { offset: 1, color: 'rgba(125,211,252,0.01)' },
            ]),
          },
        },
        {
          name: tooltipLabels.drawdown,
          type: 'line',
          xAxisIndex: 1,
          yAxisIndex: 1,
          smooth: 0.16,
          symbol: 'none',
          data: drawdownSeries,
          lineStyle: {
            width: 2,
            color: '#fb7185',
            shadowBlur: 10,
            shadowColor: 'rgba(251,113,133,0.24)',
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(251,113,133,0.14)' },
              { offset: 1, color: 'rgba(251,113,133,0.01)' },
            ]),
          },
        },
        {
          name: tooltipLabels.pnl,
          type: 'bar',
          xAxisIndex: 2,
          yAxisIndex: 2,
          data: pnlSeries.map((value) => ({
            value,
            itemStyle: {
              color: value >= 0 ? 'rgba(52,211,153,0.82)' : 'rgba(251,113,133,0.82)',
              borderRadius: [4, 4, 0, 0],
            },
          })),
          barWidth: '56%',
        },
      ],
    };
  })();

  useEffect(() => {
    const host = containerRef.current;
    if (!host || width <= 0 || height <= 0 || host.clientWidth <= 0 || host.clientHeight <= 0) return undefined;
    const instance = chartRef.current ?? echarts.init(containerRef.current, undefined, { renderer: 'canvas' });
    chartRef.current = instance;
    const setOpts: SetOptionOpts = { notMerge: true, lazyUpdate: true };
    instance.setOption(option, setOpts);
    instance.resize();
    return undefined;
  }, [height, option, width]);

  useEffect(() => () => {
    chartRef.current?.dispose();
    chartRef.current = null;
  }, []);

  return (
    <section
      className="backtest-void-workspace"
      data-testid="deterministic-backtest-chart-workspace"
      data-row-count={rows.length}
      data-main-series-length={rows.filter((row) => getEquityValue(row) != null).length}
      data-daily-pnl-series-length={rows.filter((row) => row.dailyPnl != null).length}
      data-position-series-length={rows.filter((row) => row.drawdownPct != null).length}
      data-chart-engine="echarts"
    >
      <div className="backtest-void-workspace__meta" data-testid="deterministic-chart-meta-strip">
        {metaStrip.map((item) => (
          <div key={item.label} className="backtest-void-workspace__meta-card">
            <span className="backtest-void-workspace__meta-label">{item.label}</span>
            <span className="backtest-void-workspace__meta-value">{item.value}</span>
          </div>
        ))}
      </div>
      <div className="backtest-void-workspace__body" ref={sizeRef as React.RefObject<HTMLDivElement>}>
        <aside className={`backtest-void-workspace__sidebar ${sidebarOpen ? 'is-open' : ''}`}>
          <button
            type="button"
            className="backtest-void-workspace__sidebar-toggle"
            onClick={() => setSidebarOpen((value) => !value)}
            aria-expanded={sidebarOpen}
          >
            <span>{language === 'en' ? 'Parameters' : '回测参数'}</span>
          </button>
          <div className="backtest-void-workspace__sidebar-panel">
            <dl className="backtest-void-workspace__facts">
              <div><dt>{language === 'en' ? 'Symbol' : '标的'}</dt><dd>{run.code}</dd></div>
              <div><dt>{language === 'en' ? 'Period' : '区间'}</dt><dd>{getDateRangeLabel(rows)}</dd></div>
              <div><dt>{language === 'en' ? 'Initial capital' : '初始本金'}</dt><dd>{formatCompactNumber(run.initialCapital, language)}</dd></div>
              <div><dt>{language === 'en' ? 'Fees' : '手续费'}</dt><dd>{run.feeBps ?? 0} bps</dd></div>
              <div><dt>{language === 'en' ? 'Slippage' : '滑点'}</dt><dd>{run.slippageBps ?? 0} bps</dd></div>
              <div><dt>{language === 'en' ? 'Benchmark' : '基准'}</dt><dd>{normalized.benchmarkMeta.benchmarkLabel}</dd></div>
            </dl>
          </div>
        </aside>
        <div className="backtest-void-workspace__chart-card">
          <div className="backtest-void-workspace__chart-header">
            <div>
              <p className="backtest-void-workspace__eyebrow">{language === 'en' ? 'Research result visuals' : '研究结果可视化'}</p>
              <h3>{language === 'en' ? 'Equity / Drawdown / Daily P&L' : '权益曲线 / 回撤 / 每日盈亏'}</h3>
            </div>
            <div className="backtest-void-workspace__legend">
              <span className="is-strategy">{language === 'en' ? 'Equity' : '权益'}</span>
              <span className="is-benchmark">{language === 'en' ? 'Drawdown' : '回撤'}</span>
              <span className="is-pnl">{language === 'en' ? 'Daily P&L' : '日盈亏'}</span>
            </div>
          </div>
          <div className="backtest-void-workspace__chart-shell">
            <figure
              ref={containerRef}
              className="backtest-void-workspace__chart-canvas"
              aria-label={ctw(language, 'cumulativeReturnChartAria')}
            />
          </div>
        </div>
      </div>
    </section>
  );
};
