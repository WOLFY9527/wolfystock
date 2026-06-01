import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { portfolioApi } from '../../../api/portfolio';
import { stocksApi } from '../../../api/stocks';
import { watchlistApi } from '../../../api/watchlist';
import LeveragedEtfMapper from '../LeveragedEtfMapper';
import {
  calculateImpliedUnderlying,
  calculateLeveragedEtfEstimate,
} from '../leveragedEtfMapperMath';

const { getQuote, getSnapshot, listWatchlistItems } = vi.hoisted(() => ({
  getQuote: vi.fn(),
  getSnapshot: vi.fn(),
  listWatchlistItems: vi.fn(),
}));

vi.mock('../../../api/stocks', () => ({
  stocksApi: {
    getQuote,
  },
}));

vi.mock('../../../api/watchlist', () => ({
  watchlistApi: {
    listWatchlistItems,
  },
}));

vi.mock('../../../api/portfolio', () => ({
  portfolioApi: {
    getSnapshot,
  },
}));

function expandMapper() {
  render(<LeveragedEtfMapper defaultUnderlyingSymbol="NVDA" />);
  const disclosure = screen.getByTestId('leveraged-etf-mapper');
  const toggle = within(disclosure).getByRole('button', { name: '展开 杠杆 ETF 映射' });
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(toggle);
  expect(within(disclosure).getByRole('button', { name: '收起 杠杆 ETF 映射' })).toHaveAttribute('aria-expanded', 'true');
  return disclosure;
}

describe('leveragedEtfMapperMath', () => {
  it('calculates the forward ETF estimate from an underlying target', () => {
    expect(calculateLeveragedEtfEstimate({
      leverage: 2,
      underlyingReference: 100,
      etfReference: 10,
      underlyingTarget: 110,
    })).toBeCloseTo(12);

    expect(calculateLeveragedEtfEstimate({
      leverage: -2,
      underlyingReference: 100,
      etfReference: 20,
      underlyingTarget: 95,
    })).toBeCloseTo(22);
  });

  it('calculates the reverse implied underlying from an ETF target', () => {
    expect(calculateImpliedUnderlying({
      leverage: 2,
      underlyingReference: 100,
      etfReference: 10,
      etfTarget: 11,
    })).toBeCloseTo(105);

    expect(calculateImpliedUnderlying({
      leverage: -2,
      underlyingReference: 100,
      etfReference: 20,
      etfTarget: 18,
    })).toBeCloseTo(105);
  });
});

describe('LeveragedEtfMapper', () => {
  it('renders bounded warning copy and calculates both manual scenarios', () => {
    const disclosure = expandMapper();

    expect(within(disclosure).getByDisplayValue('NVDA')).toBeInTheDocument();
    expect(disclosure).toHaveTextContent('近似 / 手动输入 / 同日线性情景');
    expect(disclosure).toHaveTextContent('不是 NAV 预测');
    expect(disclosure).toHaveTextContent('不是投资建议');
    expect(disclosure).toHaveTextContent('不是可执行或保证价格');
    expect(disclosure).toHaveTextContent('每日重置、路径依赖、费用/融资、跟踪误差、溢折价、流动性');

    fireEvent.change(screen.getByLabelText('ETF 代码'), { target: { value: 'NVDL' } });
    fireEvent.change(screen.getByLabelText('杠杆倍数 / 方向'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('正股/指数参考价'), { target: { value: '100' } });
    fireEvent.change(screen.getByLabelText('ETF 参考价'), { target: { value: '10' } });
    fireEvent.change(screen.getByLabelText('正股/指数目标价'), { target: { value: '110' } });
    fireEvent.change(screen.getByLabelText('ETF 目标价'), { target: { value: '11' } });
    fireEvent.change(screen.getByLabelText('ETF 入场观察价'), { target: { value: '9.5' } });
    fireEvent.change(screen.getByLabelText('ETF 止损观察价'), { target: { value: '8.5' } });
    fireEvent.change(screen.getByLabelText('ETF 止盈观察价'), { target: { value: '12' } });

    expect(screen.getByTestId('leveraged-etf-forward-output')).toHaveTextContent('NVDL');
    expect(screen.getByTestId('leveraged-etf-forward-output')).toHaveTextContent('12.00');
    expect(screen.getByTestId('leveraged-etf-reverse-output')).toHaveTextContent('105.00');
    expect(screen.getByTestId('leveraged-etf-optional-marks')).toHaveTextContent('97.50');
    expect(screen.getByTestId('leveraged-etf-optional-marks')).toHaveTextContent('92.50');
    expect(screen.getByTestId('leveraged-etf-optional-marks')).toHaveTextContent('110.00');
  });

  it('shows inline errors for invalid values and suppresses calculated output', () => {
    expandMapper();

    fireEvent.change(screen.getByLabelText('杠杆倍数 / 方向'), { target: { value: '0' } });
    fireEvent.change(screen.getByLabelText('正股/指数参考价'), { target: { value: '-100' } });
    fireEvent.change(screen.getByLabelText('ETF 参考价'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('正股/指数目标价'), { target: { value: '110' } });

    expect(screen.getByText('杠杆倍数不能为 0。')).toBeInTheDocument();
    expect(screen.getByText('正股/指数参考价必须大于 0。')).toBeInTheDocument();
    expect(screen.getByText('ETF 参考价不能为空。')).toBeInTheDocument();
    expect(screen.queryByTestId('leveraged-etf-forward-output')).not.toBeInTheDocument();
    expect(screen.queryByTestId('leveraged-etf-reverse-output')).not.toBeInTheDocument();
  });

  it('does not call quote, watchlist, or portfolio APIs while editing manual fields', () => {
    expandMapper();

    fireEvent.change(screen.getByLabelText('正股/指数代码'), { target: { value: 'QQQ' } });
    fireEvent.change(screen.getByLabelText('ETF 代码'), { target: { value: 'TQQQ' } });
    fireEvent.change(screen.getByLabelText('正股/指数参考价'), { target: { value: '450' } });
    fireEvent.change(screen.getByLabelText('ETF 参考价'), { target: { value: '70' } });
    fireEvent.change(screen.getByLabelText('正股/指数目标价'), { target: { value: '465' } });

    expect(stocksApi.getQuote).not.toHaveBeenCalled();
    expect(watchlistApi.listWatchlistItems).not.toHaveBeenCalled();
    expect(portfolioApi.getSnapshot).not.toHaveBeenCalled();
  });
});
