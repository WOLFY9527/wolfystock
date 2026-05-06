import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import OptionsLabPage from '../OptionsLabPage';
import { optionsLabApi } from '../../api/optionsLab';

vi.mock('../../api/optionsLab', () => ({
  optionsLabApi: {
    getUnderlyingSummary: vi.fn(),
    getExpirations: vi.fn(),
    getOptionChain: vi.fn(),
    compareStrategies: vi.fn(),
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
  vi.mocked(optionsLabApi.compareStrategies).mockResolvedValue({
    symbol: 'TEM',
    underlying: {
      price: 52.34,
      source: 'fixture',
      freshness: 'mock',
    },
    assumptions: {
      direction: 'bullish',
      targetPrice: 65,
      targetDate: '2026-08-21',
      maxPremium: 1000,
      riskProfile: 'balanced',
      strategies: ['long_call', 'long_put', 'bull_call_spread', 'bear_put_spread'],
      contractMultiplier: 100,
    },
    strategies: [
      {
        strategyType: 'long_call',
        legs: [{ action: 'buy', side: 'call', contractSymbol: 'TEM260619C00055000', expiration: '2026-06-19', strike: 55, mid: 4.23, quantity: 1 }],
        netDebit: 423,
        maxLoss: 423,
        maxGain: null,
        breakeven: 59.23,
        requiredMovePct: 13.17,
        payoffAtTarget: 577,
        riskRewardRatio: null,
        liquidityWarnings: [],
        ivThetaNotes: ['iv_and_theta_can_change_strategy_value_before_expiration'],
        suitabilityNotes: ['comparison_uses_user_assumptions_and_fixture_mid_prices', 'direction_assumption_bullish', 'risk_profile_balanced'],
        limitations: ['fixture_backed_defined_risk_only'],
        noAdviceDisclosure: 'Analytical comparison under explicit assumptions only; not investment advice or an instruction.',
      },
      {
        strategyType: 'long_put',
        legs: [{ action: 'buy', side: 'put', contractSymbol: 'TEM260619P00050000', expiration: '2026-06-19', strike: 50, mid: 3.35, quantity: 1 }],
        netDebit: 335,
        maxLoss: 335,
        maxGain: null,
        breakeven: 46.65,
        requiredMovePct: -10.87,
        payoffAtTarget: -335,
        riskRewardRatio: null,
        liquidityWarnings: ['thin_liquidity_in_one_or_more_legs'],
        ivThetaNotes: ['iv_and_theta_can_change_strategy_value_before_expiration'],
        suitabilityNotes: ['comparison_uses_user_assumptions_and_fixture_mid_prices', 'direction_assumption_bullish', 'risk_profile_balanced'],
        limitations: ['fixture_backed_defined_risk_only'],
        noAdviceDisclosure: 'Analytical comparison under explicit assumptions only; not investment advice or an instruction.',
      },
      {
        strategyType: 'bull_call_spread',
        legs: [
          { action: 'buy', side: 'call', contractSymbol: 'TEM260619C00055000', expiration: '2026-06-19', strike: 55, mid: 4.23, quantity: 1 },
          { action: 'sell', side: 'call', contractSymbol: 'TEM260619C00060000', expiration: '2026-06-19', strike: 60, mid: 2.28, quantity: 1 },
        ],
        netDebit: 195,
        maxLoss: 195,
        maxGain: 305,
        breakeven: 56.95,
        requiredMovePct: 8.81,
        payoffAtTarget: 305,
        riskRewardRatio: 1.56,
        liquidityWarnings: [],
        ivThetaNotes: ['iv_and_theta_can_change_strategy_value_before_expiration'],
        suitabilityNotes: ['comparison_uses_user_assumptions_and_fixture_mid_prices', 'defined_risk_debit_spread_caps_loss_and_gain'],
        limitations: ['fixture_backed_defined_risk_only'],
        noAdviceDisclosure: 'Analytical comparison under explicit assumptions only; not investment advice or an instruction.',
      },
      {
        strategyType: 'bear_put_spread',
        legs: [
          { action: 'buy', side: 'put', contractSymbol: 'TEM260619P00050000', expiration: '2026-06-19', strike: 50, mid: 3.35, quantity: 1 },
          { action: 'sell', side: 'put', contractSymbol: 'TEM260619P00045000', expiration: '2026-06-19', strike: 45, mid: 1.6, quantity: 1 },
        ],
        netDebit: 175,
        maxLoss: 175,
        maxGain: 325,
        breakeven: 48.25,
        requiredMovePct: -7.82,
        payoffAtTarget: -175,
        riskRewardRatio: 1.86,
        liquidityWarnings: ['thin_liquidity_in_one_or_more_legs'],
        ivThetaNotes: ['iv_and_theta_can_change_strategy_value_before_expiration', 'high_implied_volatility_in_one_or_more_legs'],
        suitabilityNotes: ['comparison_uses_user_assumptions_and_fixture_mid_prices', 'defined_risk_debit_spread_caps_loss_and_gain'],
        limitations: ['fixture_backed_defined_risk_only'],
        noAdviceDisclosure: 'Analytical comparison under explicit assumptions only; not investment advice or an instruction.',
      },
    ],
    limitations: ['fixture_backed_defined_risk_only', 'analytical_only_not_advice'],
    metadata: {
      readOnly: true,
      fixtureBacked: true,
      syntheticData: true,
      noExternalCalls: true,
      noLlmCalls: true,
      noOrderPlacement: true,
      noBrokerConnection: true,
      noPortfolioMutation: true,
      noTradingRecommendation: true,
      strategyEngine: 'fixture_frontend_phase4',
      forceRefreshIgnored: true,
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
    expect(screen.getByText('策略对比')).toBeInTheDocument();
    expect(screen.getByText('情景收益结构')).toBeInTheDocument();
    expect(screen.getByText('期权可能归零，最大亏损可能达到全部权利金。')).toBeInTheDocument();
    expect(screen.getByText('本模块不提供交易执行或收益承诺。')).toBeInTheDocument();
  });

  it('renders the Phase 4 strategy comparison cards with key metrics and warnings', async () => {
    renderPage();

    const section = await screen.findByTestId('options-lab-strategy-comparison');
    expect(within(section).getByText('策略对比')).toBeInTheDocument();
    await waitFor(() => {
      expect(within(section).getByText('看涨期权多头')).toBeInTheDocument();
      expect(within(section).getByText('看跌期权多头')).toBeInTheDocument();
      expect(within(section).getByText('牛市看涨价差')).toBeInTheDocument();
      expect(within(section).getByText('熊市看跌价差')).toBeInTheDocument();
    });
    ['净支出', '最大亏损', '最大收益', '盈亏平衡', '目标价格收益', '风险收益比'].forEach((label) => {
      expect(within(section).getAllByText(label).length).toBeGreaterThan(0);
    });
    expect(within(section).getAllByText('至少一腿流动性偏薄').length).toBeGreaterThan(0);
    expect(within(section).getAllByText('IV 与 Theta 会改变到期前估值').length).toBeGreaterThan(0);
    expect(within(section).getByText(/至少一腿隐含波动率偏高/)).toBeInTheDocument();
    expect(within(section).getAllByText('仅供情景分析，不构成交易建议').length).toBeGreaterThan(0);
  });

  it('does not fire compare before required assumptions are ready and shows a compact empty state', async () => {
    vi.mocked(optionsLabApi.compareStrategies).mockClear();
    vi.mocked(optionsLabApi.getExpirations).mockResolvedValueOnce({
      symbol: 'TEM',
      expirations: [],
      metadata: {
        readOnly: true,
        noExternalCallsInTests: true,
        limitations: ['mocked_frontend_shell'],
      },
    });
    vi.mocked(optionsLabApi.getOptionChain).mockResolvedValueOnce({
      symbol: 'TEM',
      expiration: '2026-06-19',
      underlying: null,
      calls: [],
      puts: [],
      filtersApplied: {},
      chainAsOf: '2026-05-06T09:45:00-04:00',
      source: 'fixture',
      limitations: ['provider_validation_required'],
      metadata: {
        readOnly: true,
        noExternalCallsInTests: true,
        limitations: ['mocked_frontend_shell'],
      },
    });
    renderPage();

    expect(await screen.findByText('暂无可用到期日。')).toBeInTheDocument();
    expect(screen.getByText('等待策略对比前提')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('先选择可用到期日并加载合约后，再进入策略对比。')).toBeInTheDocument();
    });
    expect(vi.mocked(optionsLabApi.compareStrategies)).not.toHaveBeenCalled();
  });

  it('keeps the base page usable when compare returns 500', async () => {
    vi.mocked(optionsLabApi.compareStrategies).mockRejectedValueOnce({
      response: { status: 500, data: { detail: { error: 'strategy_engine_down' } } },
      message: 'Internal Server Error',
    });
    renderPage();

    expect(await screen.findByText('期权实验室')).toBeInTheDocument();
    const section = await screen.findByTestId('options-lab-strategy-comparison');
    expect(within(section).getByText('策略对比')).toBeInTheDocument();
    await waitFor(() => {
      expect(within(section).getByText('策略对比暂不可用。请稍后重试或调整假设。')).toBeInTheDocument();
    });
    expect(screen.getByText('TEM260619C00055000')).toBeInTheDocument();
  });

  it('keeps the base page usable when compare returns 404', async () => {
    vi.mocked(optionsLabApi.compareStrategies).mockRejectedValueOnce({
      response: { status: 404, data: { detail: { error: 'not_found' } } },
      message: 'Not Found',
    });
    renderPage();

    expect(await screen.findByText('期权实验室')).toBeInTheDocument();
    const section = await screen.findByTestId('options-lab-strategy-comparison');
    expect(within(section).getByText('策略对比')).toBeInTheDocument();
    await waitFor(() => {
      expect(within(section).getByText('策略对比暂不可用。请稍后重试或调整假设。')).toBeInTheDocument();
    });
    expect(screen.getByText('TEM260619C00055000')).toBeInTheDocument();
  });

  it('keeps the base page usable when compare times out', async () => {
    const originalSetTimeout = window.setTimeout.bind(window);
    const timeoutSpy = vi.spyOn(window, 'setTimeout').mockImplementation(((handler: TimerHandler, timeout?: number, ...args: unknown[]) => (
      originalSetTimeout(handler, timeout === 12_000 ? 0 : timeout, ...args)
    )) as typeof window.setTimeout);
    vi.mocked(optionsLabApi.compareStrategies).mockReturnValueOnce(new Promise(() => {}));

    try {
      renderPage();

      const section = await screen.findByTestId('options-lab-strategy-comparison');
      await waitFor(() => {
        expect(within(section).getByText('策略对比暂不可用。请稍后重试或调整假设。')).toBeInTheDocument();
      });
      expect(screen.getByText('TEM260619C00055000')).toBeInTheDocument();
    } finally {
      timeoutSpy.mockRestore();
    }
  });

  it('terminates unsupported or auth-gated base data with sanitized copy and no compare call', async () => {
    vi.mocked(optionsLabApi.compareStrategies).mockClear();
    vi.mocked(optionsLabApi.getUnderlyingSummary).mockRejectedValueOnce({
      response: {
        status: 404,
        data: {
          detail: {
            error: 'unsupported_symbol',
            message: 'Options Lab Phase 1 supports fixture-backed US listed equity options only.',
            raw_provider_payload: 'token=abc Traceback',
          },
        },
      },
    });

    renderPage();

    expect(await screen.findByText('期权链暂不可用。请稍后重试或调整标的。')).toBeInTheDocument();
    expect(screen.getByText('期权链暂不可用，策略对比已暂停。')).toBeInTheDocument();
    expect(vi.mocked(optionsLabApi.compareStrategies)).not.toHaveBeenCalled();
    const domText = document.body.textContent || '';
    expect(domText).not.toContain('raw_provider_payload');
    expect(domText).not.toContain('token=abc');
    expect(domText).not.toContain('Traceback');
  });

  it('keeps freshness and developer details collapsed by default', async () => {
    renderPage();

    expect(await screen.findByText('TEM260619C00055000')).toBeInTheDocument();
    const details = screen.getByTestId('options-lab-developer-details');
    expect(details).not.toHaveAttribute('open');
    const strategyDetails = screen.getByTestId('options-lab-strategy-developer-details');
    expect(strategyDetails).not.toHaveAttribute('open');
  });

  it('does not expose raw provider payloads, secrets, rejected recommendation wording, or order CTAs', async () => {
    renderPage();

    await screen.findByText('TEM260619C00055000');
    const domText = document.body.textContent || '';
    [
      'raw_provider_payload',
      'raw provider payload',
      'api_key',
      'api key',
      'token',
      'secret',
      'stack trace',
      'Traceback',
      'broker credentials',
      '稳赚',
      '必买',
      '买入按钮',
      '下单',
      '立即交易',
      '保证收益',
      'guaranteed',
      'best contract',
      'AI recommends you buy',
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
