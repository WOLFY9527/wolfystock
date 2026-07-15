import { render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { stocksApi } from '../../../api/stocks';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import { HomeCandlestickChart } from '../HomeCandlestickChart';

const elementSizeTestDouble = vi.hoisted(() => ({
  size: { width: 720, height: 360 },
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

const historyRows = Array.from({ length: 30 }, (_, index) => {
  const close = 100 + index;
  return {
    date: `2026-05-${String(index + 1).padStart(2, '0')}`,
    open: close - 0.5,
    high: close + 1,
    low: close - 1,
    close,
    volume: 1_000_000 + index * 10_000,
  };
});

describe('HomeCandlestickChart ECharts lifecycle', () => {
  beforeEach(() => {
    elementSizeTestDouble.size = { width: 720, height: 360 };
    echartsTestDouble.init.mockClear();
    echartsTestDouble.instance.setOption.mockClear();
    echartsTestDouble.instance.resize.mockClear();
    echartsTestDouble.instance.dispose.mockClear();
    vi.spyOn(stocksApi, 'getHistory').mockResolvedValue({
      stockCode: 'AAPL',
      stockName: 'Apple',
      period: 'daily',
      data: historyRows,
    } as never);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('keeps the v5 theme through resize and a repeated mount', async () => {
    const props = { ticker: 'AAPL', currentPrice: 129 };
    const firstMount = render(
      <UiLanguageProvider>
        <HomeCandlestickChart {...props} />
      </UiLanguageProvider>,
    );

    await waitFor(() => expect(echartsTestDouble.init).toHaveBeenCalledTimes(1));
    expect(echartsTestDouble.init).toHaveBeenLastCalledWith(
      expect.any(HTMLElement),
      'v5',
      { renderer: 'canvas' },
    );
    const [chartOption, setOptionOpts] = echartsTestDouble.instance.setOption.mock.calls[0];
    expect(chartOption).toEqual(expect.objectContaining({
      grid: expect.arrayContaining([
        expect.objectContaining({
          outerBoundsMode: 'same',
          outerBoundsContain: 'axisLabel',
        }),
      ]),
    }));
    expect(chartOption.grid.every((grid: object) => !('containLabel' in grid))).toBe(true);
    expect(setOptionOpts).toEqual({ notMerge: true, lazyUpdate: true });

    elementSizeTestDouble.size = { width: 520, height: 300 };
    firstMount.rerender(
      <UiLanguageProvider>
        <HomeCandlestickChart {...props} />
      </UiLanguageProvider>,
    );
    await waitFor(() => expect(echartsTestDouble.instance.resize).toHaveBeenCalledTimes(2));

    firstMount.unmount();
    expect(echartsTestDouble.instance.dispose).toHaveBeenCalledTimes(1);

    const secondMount = render(
      <UiLanguageProvider>
        <HomeCandlestickChart {...props} />
      </UiLanguageProvider>,
    );
    await waitFor(() => expect(echartsTestDouble.init).toHaveBeenCalledTimes(2));
    secondMount.unmount();
    expect(echartsTestDouble.instance.dispose).toHaveBeenCalledTimes(2);
  });
});
