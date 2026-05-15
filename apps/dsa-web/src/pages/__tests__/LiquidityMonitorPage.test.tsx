import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LiquidityMonitorPage from '../LiquidityMonitorPage';

const { getLiquidityMonitor } = vi.hoisted(() => ({
  getLiquidityMonitor: vi.fn(),
}));

vi.mock('../../api/liquidityMonitor', () => ({
  liquidityMonitorApi: {
    getLiquidityMonitor,
  },
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: 'zh',
    t: (key: string) => key,
  }),
}));

const payload = {
  endpoint: '/api/v1/market/liquidity-monitor',
  generatedAt: '2026-05-07T10:00:00+08:00',
  score: {
    value: 69,
    regime: 'supportive',
    confidence: 0.44,
    includedIndicatorCount: 3,
    possibleIndicatorWeight: 43,
    includedIndicatorWeight: 19,
  },
  freshness: {
    status: 'delayed',
    weakestIndicatorFreshness: 'delayed',
    latestAsOf: '2026-05-07T10:00:00+08:00',
  },
  indicators: [
    {
      key: 'vix_pressure',
      label: 'VIX / 波动率压力',
      status: 'live',
      freshness: 'live',
      includedInScore: true,
      scoreContribution: 8,
      scoreWeight: 8,
      summary: '均值 -2.50%',
      updatedAt: '2026-05-07T10:00:00+08:00',
    },
    {
      key: 'crypto_funding',
      label: 'Crypto Funding',
      status: 'unavailable',
      freshness: 'fallback',
      includedInScore: false,
      scoreContribution: 0,
      scoreWeight: 0,
      summary: '仅在真实 funding 快照存在时显示',
      updatedAt: '2026-05-07T10:00:00+08:00',
    },
    {
      key: 'us_breadth_proxy',
      label: 'US 广度代理',
      status: 'partial',
      freshness: 'delayed',
      includedInScore: true,
      scoreContribution: 6,
      scoreWeight: 6,
      summary: '8 / 3',
      updatedAt: '2026-05-07T10:00:00+08:00',
    },
  ],
  advisoryDisclosure: '仅用于观察市场流动性环境，非买卖建议，不触发扫描、回测或组合动作。',
  sourceMetadata: {
    externalProviderCalls: false,
    providerRuntimeChanged: false,
    marketCacheMutation: false,
  },
};

describe('LiquidityMonitorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders score regime confidence freshness and disclosure', async () => {
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    expect(await screen.findByRole('heading', { name: '流动性监测' })).toBeInTheDocument();
    const pageShell = screen.getByRole('heading', { name: '流动性监测' }).closest('[data-terminal-primitive="page-shell"]');
    expect(pageShell).toHaveAttribute('data-workspace-width', 'near-full');
    expect(pageShell).toHaveClass('max-w-[1840px]');
    expect(screen.getAllByText('支撑').length).toBeGreaterThan(0);
    expect(screen.getByText('69')).toBeInTheDocument();
    expect(screen.getByText('44%')).toBeInTheDocument();
    expect(screen.getAllByText('延迟').length).toBeGreaterThan(0);
    expect(screen.getByText('仅用于观察市场流动性环境，非买卖建议，不触发扫描、回测或组合动作。')).toBeInTheDocument();
  });

  it('renders partial and unavailable indicators compactly', async () => {
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    await screen.findByRole('heading', { name: '流动性监测' });
    expect(screen.getByText('部分可用')).toBeInTheDocument();
    expect(screen.getByText('暂不可用')).toBeInTheDocument();
    expect(screen.getByText('Crypto 资金费率')).toBeVisible();
    expect(screen.getByText('仅在真实 funding 快照存在时显示')).toBeVisible();
  });

  it('shows the selected indicator inspector and collapsed source details', async () => {
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    await screen.findByRole('heading', { name: '流动性监测' });
    expect(screen.getAllByText('VIX / 波动率压力').length).toBeGreaterThan(0);
    expect(screen.getAllByText('均值 -2.50%').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: '展开 数据源细节' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '展开 数据源细节' }));
    expect(screen.getByText('外部调用')).toBeInTheDocument();
    expect(screen.getAllByText('未发生').length).toBeGreaterThan(0);
  });
});
