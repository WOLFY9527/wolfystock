import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CoreMarketChart, type CoreMarketChartPoint } from '../CoreMarketChart';
import { PREFERS_REDUCED_MOTION_QUERY } from '../../../utils/motionPreference';

const buildOhlcvPoints = (count: number): CoreMarketChartPoint[] => (
  Array.from({ length: count }, (_, index) => {
    const close = 100 + index * 0.8;
    return {
      date: `2026-05-${String(index + 1).padStart(2, '0')}`,
      open: close - 0.45,
      high: close + 1.15,
      low: close - 1.05,
      close,
      volume: 1_000_000 + index * 12_500,
    };
  })
);

function installMatchMedia(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: vi.fn((query: string) => ({
      matches: query === PREFERS_REDUCED_MOTION_QUERY ? matches : false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

describe('CoreMarketChart', () => {
  beforeEach(() => {
    installMatchMedia(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders an interactive candlestick chart with volume, MA overlays, range controls, and OHLCV inspection', () => {
    render(
      <CoreMarketChart
        testId="stock-history-core-chart"
        chartKind="stock-history"
        title="AAPL 价格与成交量历史"
        subtitle="仅使用接口返回的价格与成交量 K 线，缺失日期不补齐。"
        points={buildOhlcvPoints(25)}
        language="zh"
        statusLabel="历史数据可用"
        statusTone="success"
        sourceLabel="本地历史数据"
        freshnessLabel="历史数据可用"
        rangeLabel="2026-05-01 → 2026-05-25"
        coverageLabel="25 / 90 根"
        warningLabel="历史样本不足"
        emptyTitle="图表暂不可用"
        emptyDetail="历史 K 线暂不可用，因此不绘制价格线。"
        showVolume
      />,
    );

    const chart = screen.getByTestId('stock-history-core-chart');
    expect(chart).toHaveAttribute('data-chart-engine', 'echarts');
    expect(chart).toHaveAttribute('data-render-mode', 'candlestick');
    expect(chart).toHaveAttribute('data-volume-panel', 'true');
    expect(chart).toHaveAttribute('data-enabled-overlays', 'MA5,MA20');
    expect(chart).toHaveAttribute('data-chart-animation', 'disabled');
    expect(chart).toHaveAttribute('data-tooltip-motion', 'enabled');
    expect(chart).toHaveAttribute('data-prefers-reduced-motion', 'false');
    expect(chart).toHaveTextContent('历史数据可用');
    expect(chart).toHaveTextContent('历史样本不足');
    expect(chart).toHaveTextContent('25 / 90 根');
    expect(within(chart).getByTestId('core-market-chart-frame')).toBeInTheDocument();

    const graphic = within(chart).getByTestId('core-market-echarts-node');
    expect(graphic).toHaveAttribute('role', 'img');
    expect(graphic).toHaveAttribute(
      'aria-label',
      expect.stringContaining('AAPL 价格与成交量历史'),
    );
    expect(graphic).toHaveAttribute('aria-describedby', 'stock-history-core-chart-chart-text-alternative');

    const textAlternative = within(chart).getByTestId('core-market-chart-text-alternative');
    expect(textAlternative).toHaveTextContent('历史数据可用');
    expect(textAlternative).toHaveTextContent('来源 本地历史数据');
    expect(textAlternative).not.toHaveTextContent(/provider_missing|contractVersion|noExternalCalls/i);

    expect(within(chart).getByTestId('core-market-chart-volume-context')).toHaveTextContent('成交量');
    expect(within(chart).getByTestId('core-market-chart-range-controls')).toHaveTextContent('1D');
    expect(within(chart).getByTestId('core-market-chart-range-controls')).toHaveTextContent('全部');
    expect(within(chart).getByTestId('core-market-chart-overlay-legend')).toHaveTextContent('MA5');
    expect(within(chart).getByTestId('core-market-chart-overlay-legend')).toHaveTextContent('MA20');

    fireEvent.click(within(chart).getByRole('button', { name: /1M/ }));
    expect(chart).toHaveAttribute('data-active-range', '1M');
    expect(chart).toHaveAttribute('data-visible-points', '22');

    fireEvent.mouseMove(within(chart).getByTestId('core-market-chart-frame'), { clientX: 720 });
    const tooltip = within(chart).getByTestId('core-market-hover-tooltip');
    expect(tooltip).toHaveTextContent('日期');
    expect(tooltip).toHaveTextContent('开盘');
    expect(tooltip).toHaveTextContent('最高');
    expect(tooltip).toHaveTextContent('最低');
    expect(tooltip).toHaveTextContent('收盘');
    expect(tooltip).toHaveTextContent('成交量');
  });

  it('exposes keyboard bar inspection so critical bar detail is not hover-only', () => {
    render(
      <CoreMarketChart
        testId="stock-history-core-chart"
        chartKind="stock-history"
        title="AAPL 价格与成交量历史"
        points={buildOhlcvPoints(12)}
        language="zh"
        statusLabel="历史数据可用"
        sourceLabel="本地历史数据"
        freshnessLabel="历史数据可用"
        rangeLabel="12 bars"
        emptyTitle="图表暂不可用"
        emptyDetail="历史 K 线暂不可用，因此不绘制价格线。"
        showVolume
      />,
    );

    const frame = screen.getByTestId('core-market-chart-frame');
    expect(frame).toHaveAttribute('tabindex', '0');
    expect(frame).toHaveAttribute('role', 'group');
    frame.focus();
    fireEvent.keyDown(frame, { key: 'ArrowRight' });
    const tooltip = screen.getByTestId('core-market-hover-tooltip');
    expect(tooltip).toHaveTextContent('日期');
    expect(tooltip).toHaveTextContent('收盘');
    fireEvent.keyDown(frame, { key: 'Escape' });
    expect(screen.queryByTestId('core-market-hover-tooltip')).not.toBeInTheDocument();
  });

  it('marks tooltip motion disabled under prefers-reduced-motion', () => {
    installMatchMedia(true);
    render(
      <CoreMarketChart
        testId="stock-history-core-chart"
        chartKind="stock-history"
        title="AAPL 价格与成交量历史"
        points={buildOhlcvPoints(8)}
        language="zh"
        statusLabel="历史数据可用"
        sourceLabel="本地历史数据"
        freshnessLabel="历史数据可用"
        rangeLabel="8 bars"
        emptyTitle="图表暂不可用"
        emptyDetail="历史 K 线暂不可用，因此不绘制价格线。"
        showVolume
      />,
    );

    const chart = screen.getByTestId('stock-history-core-chart');
    expect(chart).toHaveAttribute('data-prefers-reduced-motion', 'true');
    expect(chart).toHaveAttribute('data-tooltip-motion', 'disabled');
    expect(chart).toHaveAttribute('data-chart-animation', 'disabled');
  });

  it('keeps close-only market overview trend points in line mode instead of fabricating OHLC candles', () => {
    render(
      <CoreMarketChart
        testId="market-overview-core-trend-chart-frame"
        chartKind="market-overview-trend"
        title="广义美股市场趋势"
        points={[
          { date: '2026-06-20', close: 540.1 },
          { date: '2026-06-21', close: 542.4 },
          { date: '2026-06-22', close: 541.8 },
        ]}
        language="zh"
        statusLabel="历史数据可用"
        statusTone="success"
        sourceLabel="Yahoo Finance"
        freshnessLabel="报价延迟"
        rangeLabel="3 点趋势"
        emptyTitle="紧凑趋势图暂不可用"
        emptyDetail="未收到返回点时，页面不会绘制市场趋势。"
        showVolume={false}
        compact
      />,
    );

    const chart = screen.getByTestId('market-overview-core-trend-chart-frame');
    expect(chart).toHaveAttribute('data-chart-engine', 'echarts');
    expect(chart).toHaveAttribute('data-render-mode', 'line');
    expect(chart).toHaveAttribute('data-volume-panel', 'false');
    expect(chart).toHaveAttribute('data-enabled-overlays', 'none');
    expect(within(chart).getByTestId('core-market-chart-frame')).toBeInTheDocument();
    expect(within(chart).getByTestId('core-market-echarts-node')).toHaveAttribute('role', 'img');
    expect(within(chart).queryByText(/provider_missing|data_disabled|sourceClass|local_bounded_us_parquet_universe|noExternalCalls|providerCallsEnabled|contractVersion/i)).not.toBeInTheDocument();
  });
});
