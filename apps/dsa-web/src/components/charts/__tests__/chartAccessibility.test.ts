import { describe, expect, it } from 'vitest';
import {
  CHART_GRAPHIC_ROLE,
  buildCoreMarketChartAccessibleSemantics,
} from '../chartAccessibility';

describe('chartAccessibility', () => {
  it('exposes img role constant for informational chart graphics', () => {
    expect(CHART_GRAPHIC_ROLE).toBe('img');
  });

  it('builds a bounded name and text alternative without dumping series data', () => {
    const semantics = buildCoreMarketChartAccessibleSemantics({
      testId: 'stock-history-core-chart',
      title: 'AAPL 价格与成交量历史',
      language: 'zh',
      hasChart: true,
      emptyTitle: '图表暂不可用',
      barCount: 25,
      startDate: '2026-05-01',
      endDate: '2026-05-25',
      renderMode: 'candlestick',
      latestLabel: '2026-05-25',
      changeLabel: '区间变动 +2.1%',
      rangeLabel: '2026-05-01 → 2026-05-25',
      sourceLabel: '本地历史数据',
      statusLabel: '历史数据可用',
      coverageLabel: '25 / 90 根',
    });

    expect(semantics.descriptionId).toBe('stock-history-core-chart-chart-text-alternative');
    expect(semantics.ariaLabel).toContain('AAPL 价格与成交量历史');
    expect(semantics.ariaLabel).toContain('25 根返回 K 线');
    expect(semantics.ariaLabel).toContain('2026-05-01');
    expect(semantics.description).toContain('历史数据可用');
    expect(semantics.description).toContain('最新 2026-05-25');
    expect(semantics.description).toContain('来源 本地历史数据');
    expect(semantics.description).not.toMatch(/provider_missing|contractVersion|rawRows|noExternalCalls/i);
    expect(semantics.exploreLabel).toMatch(/方向键/);
  });

  it('falls back to empty-state naming when the chart has no returned bars', () => {
    const semantics = buildCoreMarketChartAccessibleSemantics({
      testId: 'market-overview-core-trend-chart-frame',
      title: '市场趋势暂不可用',
      language: 'zh',
      hasChart: false,
      emptyTitle: '紧凑趋势图暂不可用',
      barCount: 0,
      renderMode: 'line',
      statusLabel: '报价延迟/不可用',
      sourceLabel: '市场数据来源待确认',
    });

    expect(semantics.ariaLabel).toContain('市场趋势暂不可用');
    expect(semantics.ariaLabel).toContain('紧凑趋势图暂不可用');
    expect(semantics.description).toContain('报价延迟/不可用');
  });
});
