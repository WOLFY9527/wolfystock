import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import OptionsLabPage, { OptionsLabErrorBoundary } from '../OptionsLabPage';
import { optionsLabApi } from '../../api/optionsLab';

vi.mock('../../api/optionsLab', () => ({
  optionsLabApi: {
    getUnderlyingSummary: vi.fn(),
    getExpirations: vi.fn(),
    getOptionChain: vi.fn(),
    compareStrategies: vi.fn(),
    evaluateDecision: vi.fn(),
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
  vi.mocked(optionsLabApi.evaluateDecision).mockResolvedValue({
    symbol: 'TEM',
    strategy: 'bull_call_spread',
    dataQuality: {
      dataQualityScore: 25,
      dataQualityTier: 'synthetic_demo_only',
      blockingReasons: ['synthetic_or_fixture_data_not_decision_grade'],
      sourceType: 'synthetic',
      asOfAgeMinutes: 0,
    },
    liquidity: {
      liquidityScore: 76,
      spreadPct: 10,
      liquidityWarnings: [],
    },
    ivGreeks: {
      ivReadiness: 82,
      ivRankStatus: 'unavailable',
      ivRank: null,
      ivPercentile: null,
      warnings: ['iv_rank_unavailable'],
    },
    ivRank: null,
    ivPercentile: null,
    ivRankStatus: 'unavailable',
    expectedMove: {
      expectedMoveAbs: 7.5,
      expectedMovePct: 14.31,
      expectedMoveSource: 'straddle_mid',
      expectedMoveWarnings: ['expected_move_uses_fixture_mid_prices'],
    },
    optimizer: {
      preferredStrategyKey: null,
      optimizerLabel: '数据不足，禁止判断',
      noTradeReason: 'data_quality_not_decision_grade',
      alternatives: [
        {
          strategyKey: 'bull_call_spread',
          dataQualityTier: 'synthetic_demo_only',
          liquidityScore: 76,
          breakevenPressure: 0.19,
          maxLoss: 230,
          maxGain: 270,
          riskRewardRatio: 1.17,
          expectedMoveAlignment: 92,
          ivReadiness: 82,
          tradeQualityScore: 35,
          decisionLabel: '数据不足，禁止判断',
          primaryReasons: ['当前为 synthetic delayed / 演示数据'],
          riskWarnings: ['不可用于真实交易判断'],
        },
        {
          strategyKey: 'long_call',
          dataQualityTier: 'synthetic_demo_only',
          liquidityScore: 76,
          breakevenPressure: 10.11,
          maxLoss: 270,
          maxGain: null,
          riskRewardRatio: null,
          expectedMoveAlignment: 80,
          ivReadiness: 82,
          tradeQualityScore: 35,
          decisionLabel: '数据不足，禁止判断',
          primaryReasons: ['IV Rank 不可用，波动率位置置信度不足'],
          riskWarnings: ['iv_rank_unavailable_degrade_confidence'],
        },
      ],
    },
    rankedAlternatives: [
      {
        strategyKey: 'bull_call_spread',
        dataQualityTier: 'synthetic_demo_only',
        liquidityScore: 76,
        breakevenPressure: 0.19,
        maxLoss: 230,
        maxGain: 270,
        riskRewardRatio: 1.17,
        expectedMoveAlignment: 92,
        ivReadiness: 82,
        tradeQualityScore: 35,
        decisionLabel: '数据不足，禁止判断',
        primaryReasons: ['当前为 synthetic delayed / 演示数据'],
        riskWarnings: ['不可用于真实交易判断'],
      },
    ],
    breakeven: {
      breakeven: 52.3,
      requiredMovePct: -0.19,
      targetPriceStatus: 'target_above_breakeven',
      score: 86,
    },
    riskReward: {
      maxLoss: 230,
      maxGain: 270,
      riskRewardRatio: 1.17,
      score: 72,
    },
    tradeQualityScore: 35,
    decisionLabel: '数据不足，禁止判断',
    primaryReasons: ['当前为 synthetic delayed / 演示数据'],
    riskWarnings: ['不可用于真实交易判断'],
    betterAlternative: {
      strategyType: 'bull_call_spread',
      reason: '定义风险结构降低权利金风险',
    },
    noAdviceDisclosure: 'Analytical output only; not personalized financial advice.',
    freshness: {
      source: 'synthetic_options_lab_fixture',
      freshness: 'synthetic_delayed',
      asOf: '2026-05-06T09:45:00Z',
    },
    metadata: {
      readOnly: true,
      fixtureBacked: true,
      syntheticData: true,
      noExternalCalls: true,
      noOrderPlacement: true,
      noBrokerConnection: true,
      noPortfolioMutation: true,
      noTradingRecommendation: true,
      strategyEngine: 'options_decision_engine_r1',
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

  it('renders the R2 decision section with IV rank, expected move, optimizer, and synthetic guardrails', async () => {
    renderPage();

    const section = await screen.findByTestId('options-lab-decision-engine');
    expect(within(section).getByText('交易质量判断')).toBeInTheDocument();
    await waitFor(() => {
      expect(within(section).getByText('Expected Move')).toBeInTheDocument();
    });
    expect(within(section).getAllByText('数据不足，禁止判断').length).toBeGreaterThan(0);
    expect(within(section).getAllByText('当前为 synthetic delayed / 演示数据').length).toBeGreaterThan(0);
    expect(within(section).getAllByText('不可用于真实交易判断').length).toBeGreaterThan(0);
    expect(within(section).getByText('波动率 / Greeks 就绪度')).toBeInTheDocument();
    expect(within(section).getAllByText('IV Rank 不可用').length).toBeGreaterThan(0);
    expect(within(section).getByText('Expected Move')).toBeInTheDocument();
    expect(within(section).getByText('$7.50')).toBeInTheDocument();
    expect(within(section).getByText('策略优化')).toBeInTheDocument();
    expect(within(section).getByText('推荐状态：数据不足，禁止判断')).toBeInTheDocument();
    expect(within(section).getAllByText(/不交易：数据质量未达到可判断等级/).length).toBeGreaterThan(0);
    expect(within(section).getAllByText(/牛市看涨价差/).length).toBeGreaterThan(0);
    expect(document.body.textContent || '').not.toContain('有条件可交易');
  });

  it('puts the decision summary before deep option-chain and scenario detail sections', async () => {
    renderPage();

    const decision = await screen.findByTestId('options-lab-decision-engine');
    const summary = await screen.findByTestId('options-lab-decision-summary');
    const analysisDetails = await screen.findByTestId('options-lab-analysis-details');
    const chainDetails = await screen.findByTestId('options-lab-chain-details');
    const strategyDetails = await screen.findByTestId('options-lab-strategy-details');

    expect(decision).toContainElement(summary);
    expect(summary).toHaveTextContent('决策摘要');
    expect(summary).toHaveTextContent('数据不足，禁止判断');
    expect(summary).toHaveTextContent('不可用于真实交易判断');
    expect(analysisDetails).not.toHaveAttribute('open');
    expect(chainDetails).not.toHaveAttribute('open');
    expect(strategyDetails).not.toHaveAttribute('open');
    expect(Boolean(decision.compareDocumentPosition(analysisDetails) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(within(chainDetails).getByTestId('options-lab-calls-table')).toBeInTheDocument();
    expect(within(chainDetails).getByTestId('options-lab-puts-table')).toBeInTheDocument();
    expect(within(strategyDetails).getByTestId('options-lab-strategy-comparison')).toBeInTheDocument();
  });

  it('renders no-trade optimizer state without black-screening', async () => {
    vi.mocked(optionsLabApi.evaluateDecision).mockResolvedValueOnce({
      symbol: 'TEM',
      strategy: 'long_call',
      dataQuality: {
        dataQualityScore: 45,
        dataQualityTier: 'insufficient',
        sourceType: 'unknown',
        blockingReasons: ['missing_bid_ask'],
      },
      liquidity: { liquidityScore: 20, spreadPct: 80, liquidityWarnings: ['wide_bid_ask_spread'] },
      ivGreeks: { ivReadiness: 30, ivRankStatus: 'unavailable', warnings: ['iv_rank_unavailable'] },
      ivRank: null,
      ivPercentile: null,
      ivRankStatus: 'unavailable',
      expectedMove: {
        expectedMoveAbs: null,
        expectedMovePct: null,
        expectedMoveSource: 'unavailable',
        expectedMoveWarnings: ['expected_move_unavailable'],
      },
      optimizer: {
        preferredStrategyKey: null,
        optimizerLabel: '不建议交易',
        noTradeReason: 'all_candidates_have_weak_edge_or_unfavorable_risk_reward',
        alternatives: [],
      },
      rankedAlternatives: [],
      breakeven: { breakeven: 57.7, requiredMovePct: 10.11, targetPriceStatus: 'target_below_breakeven', score: 35 },
      riskReward: { maxLoss: 270, maxGain: null, riskRewardRatio: null, score: 30, warnings: ['max_gain_not_defined_for_long_option'] },
      tradeQualityScore: 28,
      decisionLabel: '不建议',
      primaryReasons: ['数据质量、流动性与风险回报需同时复核'],
      riskWarnings: ['expected_move_unavailable_degrade_confidence'],
      noAdviceDisclosure: 'Analytical output only; not personalized financial advice.',
      freshness: { source: 'fixture', freshness: 'synthetic_delayed', asOf: '2026-05-06T09:45:00Z' },
      metadata: { readOnly: true, noExternalCalls: true },
    } as never);

    renderPage();

    const optimizer = await screen.findByTestId('options-lab-strategy-optimizer');
    expect(within(optimizer).getByText('推荐状态：不建议交易')).toBeInTheDocument();
    expect(within(optimizer).getByText(/不交易：候选结构边际优势或风险回报不足/)).toBeInTheDocument();
    expect(within(optimizer).getByText('暂无可排序替代结构。')).toBeInTheDocument();
  });

  it('renders missing Greeks and liquidity warnings in the decision section', async () => {
    vi.mocked(optionsLabApi.evaluateDecision).mockResolvedValueOnce({
      symbol: 'TEM',
      strategy: 'long_call',
      dataQuality: {
        dataQualityScore: 35,
        dataQualityTier: 'synthetic_demo_only',
        blockingReasons: ['synthetic_or_fixture_data_not_decision_grade'],
        sourceType: 'synthetic',
      },
      liquidity: {
        liquidityScore: 42,
        spreadPct: 38,
        liquidityWarnings: ['wide_bid_ask_spread'],
      },
      ivGreeks: {
        ivReadiness: 30,
        ivRankStatus: 'unavailable',
        warnings: ['missing_greeks'],
      },
      breakeven: {
        breakeven: 57.7,
        requiredMovePct: 10.11,
        targetPriceStatus: 'target_above_breakeven',
        score: 68,
      },
      riskReward: {
        maxLoss: 270,
        maxGain: null,
        riskRewardRatio: null,
        score: 45,
      },
      tradeQualityScore: 35,
      decisionLabel: '数据不足，禁止判断',
      primaryReasons: ['Greeks 缺失，无法评估时间价值与敏感度'],
      riskWarnings: ['wide_bid_ask_spread', 'missing_greeks_degrade_confidence'],
      noAdviceDisclosure: 'Analytical output only; not personalized financial advice.',
      freshness: {
        source: 'synthetic_options_lab_fixture',
        freshness: 'synthetic_delayed',
      },
      metadata: {
        readOnly: true,
        fixtureBacked: true,
        syntheticData: true,
        noExternalCalls: true,
        noOrderPlacement: true,
        noBrokerConnection: true,
        noPortfolioMutation: true,
        noTradingRecommendation: true,
      },
    });

    renderPage();

    const section = await screen.findByTestId('options-lab-decision-engine');
    await waitFor(() => {
      expect(within(section).getAllByText('买卖价差过宽').length).toBeGreaterThan(0);
    });
    expect(within(section).getAllByText('Greeks 缺失').length).toBeGreaterThan(0);
    expect(within(section).getByText('Greeks 缺失，无法评估时间价值与敏感度')).toBeInTheDocument();
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
    expect(vi.mocked(optionsLabApi.evaluateDecision)).not.toHaveBeenCalled();
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

  it('keeps the page visible when compare returns incomplete strategy fields', async () => {
    vi.mocked(optionsLabApi.compareStrategies).mockResolvedValueOnce({
      symbol: 'TEM',
      underlying: {
        price: 52.34,
      },
      assumptions: {},
      strategies: [
        {
          strategyType: 'long_call',
          legs: [],
          netDebit: 423,
          maxLoss: 423,
          maxGain: null,
          breakeven: 59.23,
          requiredMovePct: 13.17,
          payoffAtTarget: 577,
          riskRewardRatio: null,
        } as never,
      ],
      limitations: null,
      metadata: null,
    } as never);

    renderPage();

    expect(await screen.findByText('期权实验室')).toBeInTheDocument();
    const section = await screen.findByTestId('options-lab-strategy-comparison');
    await waitFor(() => {
      expect(within(section).getByText('看涨期权多头')).toBeInTheDocument();
    });
    expect(document.body.textContent || '').not.toContain('TypeError');
    expect(document.body.textContent || '').not.toContain('stack');
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

  it.each([401, 403])('keeps the base page usable when compare returns %s', async (status) => {
    vi.mocked(optionsLabApi.compareStrategies).mockRejectedValueOnce({
      response: { status, data: { detail: { error: 'auth_gated', raw_provider_payload: 'token=abc Traceback' } } },
      message: `HTTP ${status}`,
    });
    renderPage();

    expect(await screen.findByText('期权实验室')).toBeInTheDocument();
    const section = await screen.findByTestId('options-lab-strategy-comparison');
    await waitFor(() => {
      expect(within(section).getByText('策略对比暂不可用。请稍后重试或调整假设。')).toBeInTheDocument();
    });
    const domText = document.body.textContent || '';
    expect(domText).not.toContain('raw_provider_payload');
    expect(domText).not.toContain('token=abc');
    expect(domText).not.toContain('Traceback');
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
    const decisionDetails = await screen.findByTestId('options-lab-decision-developer-details');
    expect(decisionDetails).not.toHaveAttribute('open');
  });

  it('renders the Options-only crash fallback with collapsed sanitized details', () => {
    const ThrowingPage = () => {
      throw new TypeError('provider exploded stack trace token=abc');
    };

    render(
      <MemoryRouter initialEntries={['/zh/options-lab']}>
        <OptionsLabErrorBoundary>
          <ThrowingPage />
        </OptionsLabErrorBoundary>
      </MemoryRouter>,
    );

    expect(screen.getByText('期权实验室暂时无法加载，请刷新或稍后重试。')).toBeInTheDocument();
    const details = screen.getByTestId('options-lab-crash-developer-details');
    expect(details).not.toHaveAttribute('open');
    const domText = document.body.textContent || '';
    expect(domText).toContain('TypeError');
    expect(domText).not.toContain('provider exploded');
    expect(domText).not.toContain('token=abc');
    expect(domText).not.toContain('stack trace');
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
      'password',
      'session=',
      'cookie',
      'authorization',
      'bearer',
      'secret',
      'stack trace',
      'Traceback',
      'broker credentials',
      'provider credential',
      'credential payload',
      '稳赚',
      '必买',
      '买入按钮',
      '下单',
      '立即交易',
      '立即买入',
      '立即卖出',
      '保证收益',
      'guaranteed',
      'guaranteed profit',
      'best contract',
      'AI recommends you buy',
      'must buy',
      'must sell',
      'buy now',
      'sell now',
      'trade-ready',
      'trade ready',
      'you should buy',
      'you should sell',
      'raw schema',
      'debug schema',
      'provider.example',
    ].forEach((text) => {
      expect(domText.toLowerCase()).not.toContain(text.toLowerCase());
    });
  });

  it('keeps the page visible when decision payload is malformed', async () => {
    vi.mocked(optionsLabApi.evaluateDecision).mockResolvedValueOnce({
      symbol: 'TEM',
      strategy: 'long_call',
      dataQuality: null,
      liquidity: null,
      ivGreeks: null,
      breakeven: null,
      riskReward: null,
      tradeQualityScore: null,
      decisionLabel: null,
      primaryReasons: null,
      riskWarnings: null,
      metadata: null,
    } as never);

    renderPage();

    const section = await screen.findByTestId('options-lab-decision-engine');
    expect(within(section).getByText('交易质量判断')).toBeInTheDocument();
    await waitFor(() => {
      expect(within(section).getAllByText('数据不足，禁止判断').length).toBeGreaterThan(0);
    });
    expect(document.body.textContent || '').not.toContain('TypeError');
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

  it('keeps the route visible when base response fields are missing, null, or empty', async () => {
    vi.mocked(optionsLabApi.compareStrategies).mockClear();
    vi.mocked(optionsLabApi.getUnderlyingSummary).mockResolvedValueOnce({
      symbol: 'TEM',
      market: 'us',
      underlying: null,
      optionsAvailability: null,
      metadata: null,
    } as never);
    vi.mocked(optionsLabApi.getExpirations).mockResolvedValueOnce({
      symbol: 'TEM',
      expirations: null,
      metadata: null,
    } as never);
    vi.mocked(optionsLabApi.getOptionChain).mockResolvedValueOnce({
      symbol: 'TEM',
      expiration: '2026-06-19',
      underlying: null,
      calls: null,
      puts: null,
      filtersApplied: null,
      chainAsOf: null,
      source: null,
      limitations: null,
      metadata: null,
    } as never);

    renderPage();

    expect(await screen.findByText('期权实验室')).toBeInTheDocument();
    expect(await screen.findByText('暂无可用到期日。')).toBeInTheDocument();
    expect(screen.getByText('先选择可用到期日并加载合约后，再进入策略对比。')).toBeInTheDocument();
    expect(vi.mocked(optionsLabApi.compareStrategies)).not.toHaveBeenCalled();
    expect(document.body.textContent || '').not.toContain('TypeError');
  });

  it('renders calls and puts in separate dense tables with mocked chain data', async () => {
    renderPage();

    const callsTable = await screen.findByTestId('options-lab-calls-table');
    const putsTable = screen.getByTestId('options-lab-puts-table');
    expect(within(callsTable).getByText('TEM260619C00055000')).toBeInTheDocument();
    expect(within(putsTable).getByText('TEM260619P00050000')).toBeInTheDocument();
  });
});
