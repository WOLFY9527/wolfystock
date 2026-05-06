import { act, cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import OptionsLabPage from '../OptionsLabPage';
import { optionsLabApi } from '../../api/optionsLab';

vi.mock('../../api/optionsLab', () => ({
  optionsLabApi: {
    getUnderlyingSummary: vi.fn(),
    getExpirations: vi.fn(),
    getOptionChain: vi.fn(),
  },
}));

function mockHappyPath() {
  vi.mocked(optionsLabApi.getUnderlyingSummary).mockResolvedValue({
    symbol: 'TEM',
    market: 'us',
    underlying: {
      price: 52.34,
      changePct: 1.2,
      source: 'fixture',
      asOf: '2026-05-06T09:45:00-04:00',
      freshness: 'mock',
    },
    optionsAvailability: {
      supported: true,
      provider: 'fixture',
      limitations: ['provider_validation_required'],
    },
    metadata: {
      readOnly: true,
      noExternalCallsInTests: true,
      limitations: ['mocked_frontend_shell'],
    },
  });
  vi.mocked(optionsLabApi.getExpirations).mockResolvedValue({
    symbol: 'TEM',
    expirations: [
      {
        date: '2026-06-19',
        dte: 44,
        type: 'monthly',
        chainAvailable: true,
        asOf: '2026-05-06T09:45:00-04:00',
        source: 'fixture',
        warnings: ['mocked_chain'],
      },
    ],
    metadata: {
      readOnly: true,
      noExternalCallsInTests: true,
      limitations: ['mocked_frontend_shell'],
    },
  });
  vi.mocked(optionsLabApi.getOptionChain).mockResolvedValue({
    symbol: 'TEM',
    expiration: '2026-06-19',
    underlying: {
      price: 52.34,
      changePct: 1.2,
      source: 'fixture',
      asOf: '2026-05-06T09:45:00-04:00',
      freshness: 'mock',
    },
    calls: [
      {
        contractSymbol: 'TEM260619C00055000',
        side: 'call',
        strike: 55,
        bid: 4.1,
        ask: 4.35,
        mid: 4.23,
        volume: 830,
        openInterest: 6120,
        impliedVolatility: 0.54,
        delta: 0.42,
        theta: -0.05,
        spreadPct: 5.9,
        moneyness: 'otm',
        liquidityScore: 82,
      },
    ],
    puts: [
      {
        contractSymbol: 'TEM260619P00050000',
        side: 'put',
        strike: 50,
        bid: 3.2,
        ask: 3.5,
        mid: 3.35,
        volume: 410,
        openInterest: 2900,
        impliedVolatility: 0.57,
        delta: -0.36,
        theta: -0.04,
        spreadPct: 9,
        moneyness: 'otm',
        liquidityScore: 74,
      },
    ],
    filtersApplied: {
      minOpenInterest: 100,
      maxSpreadPct: 20,
    },
    chainAsOf: '2026-05-06T09:45:00-04:00',
    source: 'fixture',
    limitations: ['provider_validation_required'],
    metadata: {
      readOnly: true,
      noExternalCallsInTests: true,
      limitations: ['mocked_frontend_shell'],
    },
  });
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/zh/options-lab']}>
      <OptionsLabPage />
    </MemoryRouter>,
  );
}

describe('OptionsLabPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockHappyPath();
  });

  it('renders the Chinese shell labels, assumption panel, chain tables, and visible risk copy', async () => {
    renderPage();

    expect(screen.getByRole('heading', { name: '期权实验室' })).toBeInTheDocument();
    expect(screen.getByText('分析支持 / 不构成投资建议')).toBeInTheDocument();
    expect(screen.getByText('情景假设')).toBeInTheDocument();
    expect(screen.getByLabelText('标的代码')).toHaveValue('TEM');
    expect(screen.getByText('看涨')).toBeInTheDocument();
    expect(screen.getByText('看跌')).toBeInTheDocument();
    expect(screen.getByText('中性')).toBeInTheDocument();
    expect(screen.getByText('赌波动')).toBeInTheDocument();

    expect(await screen.findByText('TEM260619C00055000')).toBeInTheDocument();
    expect(screen.getByText('TEM260619P00050000')).toBeInTheDocument();
    expect(screen.getByText('候选合约排序')).toBeInTheDocument();
    expect(screen.getByText('策略比较')).toBeInTheDocument();
    expect(screen.getByText('情景收益结构')).toBeInTheDocument();
    expect(screen.getByText('期权可能归零，最大亏损可能达到全部权利金。')).toBeInTheDocument();
    expect(screen.getByText('本模块不提供下单或保证性收益建议。')).toBeInTheDocument();
  });

  it('keeps freshness and developer details collapsed by default', async () => {
    renderPage();

    expect(await screen.findByText('TEM260619C00055000')).toBeInTheDocument();
    const details = screen.getByTestId('options-lab-developer-details');
    expect(details).not.toHaveAttribute('open');
  });

  it('does not expose raw provider payloads, secrets, rejected recommendation wording, or order CTAs', async () => {
    renderPage();

    await screen.findByText('TEM260619C00055000');
    const domText = document.body.textContent || '';
    [
      'raw_provider_payload',
      'api_key',
      'token',
      'secret',
      'stack trace',
      'broker credentials',
      '稳赚',
      '必买',
      '最值得买',
      '确定盈利',
      '无风险',
      '保证翻倍',
      'AI 建议你买入',
      'buy now',
      'guaranteed',
      '提交订单',
    ].forEach((text) => {
      expect(domText.toLowerCase()).not.toContain(text.toLowerCase());
    });
  });

  it('shows loading, empty, and error states without raw stack traces', async () => {
    let resolveChain: (value: Awaited<ReturnType<typeof optionsLabApi.getOptionChain>>) => void = () => {};
    vi.mocked(optionsLabApi.getOptionChain).mockReturnValueOnce(new Promise((resolve) => {
      resolveChain = resolve;
    }));
    renderPage();
    expect(screen.getByText('正在加载期权链快照...')).toBeInTheDocument();
    await act(async () => resolveChain({
      symbol: 'TEM',
      expiration: '2026-06-19',
      underlying: null,
      calls: [],
      puts: [],
      filtersApplied: {},
      chainAsOf: '2026-05-06T09:45:00-04:00',
      source: 'fixture',
      limitations: [],
      metadata: { readOnly: true, noExternalCallsInTests: true, limitations: [] },
    }));
    expect((await screen.findAllByText('暂无合约数据，保留假设面板与风险提示。')).length).toBeGreaterThan(0);

    cleanup();
    vi.clearAllMocks();
    mockHappyPath();
    vi.mocked(optionsLabApi.getOptionChain).mockRejectedValueOnce(new Error('provider exploded stack trace token=abc'));
    renderPage();
    expect(await screen.findByText('期权链暂不可用。请稍后重试或调整标的。')).toBeInTheDocument();
    expect(document.body.textContent || '').not.toContain('provider exploded stack trace token=abc');
  });

  it('renders calls and puts in separate dense tables with mocked chain data', async () => {
    renderPage();

    const callsTable = await screen.findByTestId('options-lab-calls-table');
    const putsTable = screen.getByTestId('options-lab-puts-table');
    expect(within(callsTable).getByText('TEM260619C00055000')).toBeInTheDocument();
    expect(within(putsTable).getByText('TEM260619P00050000')).toBeInTheDocument();
  });
});
