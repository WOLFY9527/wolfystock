import { render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import type { RuleBacktestRunResponse } from '../../../types/backtest';
import { DeterministicBacktestChartWorkspace } from '../DeterministicBacktestChartWorkspace';
import type { DeterministicResultDensityConfig } from '../deterministicResultDensity';
import type { DeterministicBacktestNormalizedResult } from '../normalizeDeterministicBacktestResult';

const elementSizeTestDouble = vi.hoisted(() => ({
  size: { width: 960, height: 520 },
}));

const echartsTestDouble = vi.hoisted(() => {
  const instance = {
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
  };
  return {
    init: vi.fn(() => instance),
    use: vi.fn(),
    instance,
  };
});

vi.mock('../../../hooks/useElementSize', () => ({
  useElementSize: () => ({ ref: () => undefined, size: elementSizeTestDouble.size }),
}));

vi.mock('echarts/core', () => ({
  init: echartsTestDouble.init,
  use: echartsTestDouble.use,
  graphic: { LinearGradient: vi.fn() },
}));

const normalized = {
  rows: [
    {
      date: '2026-05-01',
      totalValue: 100_000,
      holdingsValue: 70_000,
      cash: 30_000,
      dailyPnl: 250,
      drawdownPct: -1.2,
    },
    {
      date: '2026-05-02',
      totalValue: 100_250,
      holdingsValue: 70_250,
      cash: 30_000,
      dailyPnl: 250,
      drawdownPct: -0.9,
    },
  ],
  benchmarkMeta: {
    showBenchmark: false,
    benchmarkLabel: 'No benchmark',
  },
} as DeterministicBacktestNormalizedResult;

const run = {
  code: 'AAPL',
  initialCapital: 100_000,
  lookbackBars: 60,
  feeBps: 5,
  slippageBps: 2,
} as RuleBacktestRunResponse;

const densityConfig = { mode: 'dense' } as DeterministicResultDensityConfig;

describe('DeterministicBacktestChartWorkspace ECharts lifecycle', () => {
  beforeEach(() => {
    elementSizeTestDouble.size = { width: 960, height: 520 };
    echartsTestDouble.init.mockClear();
    echartsTestDouble.instance.setOption.mockClear();
    echartsTestDouble.instance.resize.mockClear();
    echartsTestDouble.instance.dispose.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('keeps deterministic chart output on the v5 theme through resize and remount', async () => {
    const renderWorkspace = () => (
      <UiLanguageProvider>
        <DeterministicBacktestChartWorkspace
          normalized={normalized}
          run={run}
          densityConfig={densityConfig}
        />
      </UiLanguageProvider>
    );
    const firstMount = render(renderWorkspace());

    await waitFor(() => expect(echartsTestDouble.init).toHaveBeenCalledTimes(1));
    expect(echartsTestDouble.init).toHaveBeenLastCalledWith(
      expect.any(HTMLElement),
      'v5',
      { renderer: 'canvas' },
    );
    expect(echartsTestDouble.instance.setOption).toHaveBeenCalledWith(
      expect.objectContaining({
        grid: expect.arrayContaining([
          expect.objectContaining({ outerBoundsMode: 'none' }),
        ]),
      }),
      { notMerge: true, lazyUpdate: true },
    );

    elementSizeTestDouble.size = { width: 720, height: 420 };
    firstMount.rerender(renderWorkspace());
    await waitFor(() => expect(echartsTestDouble.instance.resize).toHaveBeenCalledTimes(2));

    firstMount.unmount();
    expect(echartsTestDouble.instance.dispose).toHaveBeenCalledTimes(1);

    const secondMount = render(renderWorkspace());
    await waitFor(() => expect(echartsTestDouble.init).toHaveBeenCalledTimes(2));
    secondMount.unmount();
    expect(echartsTestDouble.instance.dispose).toHaveBeenCalledTimes(2);
  });
});
