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
    decisionGrade: false,
    gateDecision: 'blocked',
    failClosedReasonCodes: ['synthetic_or_fixture_data_not_decision_grade'],
    dataQualityGates: {
      decisionGrade: false,
      tier: 'synthetic_demo_only',
    },
    liquidityGates: {
      passed: true,
      liquidityScore: 76,
    },
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

  it('renders the Chinese-first ExperimentConsole with command area, main workspace, and dense chain matrices', async () => {
    renderPage();

    const heading = screen.getByRole('heading', { level: 1, name: '期权实验室' });
    expect(heading).toHaveClass('text-xl', 'md:text-2xl');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.queryByText('分析支持 / 不构成投资建议')).not.toBeInTheDocument();
    expect(screen.queryByText(/教程|如何使用|从这里开始/)).not.toBeInTheDocument();
    expect(screen.queryByText(/provider_timeout|MarketCache|generatedCandidates|failedCandidates/i)).not.toBeInTheDocument();
    const pageRoot = screen.getByTestId('options-lab-page-root');
    expect(pageRoot).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(pageRoot).toHaveClass('w-full', 'max-w-[1600px]', 'mx-auto', 'px-4', 'xl:px-8', 'flex', 'flex-col');
    expect(pageRoot.closest('main')).toHaveClass('w-full', 'overflow-x-hidden', 'text-white');
    expect(pageRoot.closest('main')).not.toHaveClass('py-4');
    expect(pageRoot.className).not.toMatch(/\bbg-(black|\[#000\]|\[#050505\]|gray-|zinc-|slate-|neutral-)/);

    const commandArea = screen.getByTestId('options-lab-assumptions-panel');
    expect(commandArea).toHaveTextContent('实验命令区');
    expect(commandArea).toHaveTextContent('ExperimentConsole');
    expect(commandArea).toHaveTextContent('只读情景分析');
    expect(within(commandArea).getByLabelText('标的代码')).toHaveValue('TEM');
    expect(within(commandArea).getByRole('button', { name: '执行' })).toHaveAttribute('data-terminal-primitive', 'button');
    expect(within(commandArea).getByLabelText('到期日')).toBeInTheDocument();
    expect(within(commandArea).getByText('上涨情景')).toBeInTheDocument();
    expect(within(commandArea).getByText('下跌情景')).toBeInTheDocument();
    expect(within(commandArea).getByText('区间情景')).toBeInTheDocument();
    expect(within(commandArea).getByText('波动扩张')).toBeInTheDocument();

    const snapshotPanel = screen.getByTestId('options-lab-snapshot-panel');
    expect(snapshotPanel).toHaveTextContent('标的快照');
    expect(snapshotPanel).toHaveTextContent('状态总览');
    expect(snapshotPanel).toHaveTextContent('只读观察');
    expect(within(snapshotPanel).getByTestId('options-lab-snapshot-metric-grid')).toHaveClass('grid-cols-2', 'md:grid-cols-3', 'xl:grid-cols-6');
    expect(within(snapshotPanel).getAllByText('标的').length).toBeGreaterThan(0);
    expect(within(snapshotPanel).getAllByText('IV 分位').length).toBeGreaterThan(0);
    expect(screen.getByTestId('options-lab-bento-grid')).toHaveClass('mt-5', 'grid', 'gap-6');
    ['标的快照', '期权假设', '情景准备度', '风险边界', '策略候选', '数据限制', 'Call / Put 工作区'].forEach((label) => {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    });
    expect(screen.getByTestId('options-lab-analysis-details')).toHaveTextContent('保持折叠');

    expect(await screen.findByTestId('options-lab-decision-engine')).toBeInTheDocument();
    expect(screen.getByTestId('options-lab-risk-boundary-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('options-lab-chain-details')).not.toBeInTheDocument();
    expect(screen.queryByTestId('options-lab-strategy-details')).not.toBeInTheDocument();
    expect((await screen.findAllByText('Call 链')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Put 链').length).toBeGreaterThan(0);
    expect(screen.getAllByText('行权价').length).toBeGreaterThan(0);
    expect(screen.getAllByText('中间价').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('options-lab-chain-panel')).toHaveLength(2);
    expect(screen.getAllByText('不可作为交易信号').length).toBeGreaterThan(0);
  });

  it('renders ranked compact strategy candidates with one highlighted primary row', async () => {
    renderPage();

    const section = await screen.findByTestId('options-lab-strategy-comparison');
    expect(within(section).getByText('策略候选')).toBeInTheDocument();
    await waitFor(() => {
      expect(within(section).getByText('看涨期权多头')).toBeInTheDocument();
      expect(within(section).getByText('看跌期权多头')).toBeInTheDocument();
      expect(within(section).getByText('牛市看涨价差')).toBeInTheDocument();
      expect(within(section).getByText('熊市看跌价差')).toBeInTheDocument();
    });
    ['状态', '最大亏损', '最大收益', '盈亏平衡', '情景收益', '核心原因'].forEach((label) => {
      expect(within(section).getAllByText(label).length).toBeGreaterThan(0);
    });
    expect(within(section).getByTestId('options-lab-primary-strategy-row')).toHaveTextContent('观察排序 #1');
    expect(within(section).getByTestId('options-lab-primary-strategy-row')).toHaveTextContent('未达判断等级');
    expect(within(section).queryByText('流动性提示')).not.toBeInTheDocument();
    expect(within(section).queryByText('波动率 / 时间价值提示')).not.toBeInTheDocument();
    expect(within(section).getByText('风险提示已合并')).toBeInTheDocument();
    expect(document.body.textContent || '').not.toContain('Bull Call Spread');
    expect(document.body.textContent || '').not.toContain('Long Call');
  });

  it('renders the R2 decision section with IV rank, expected move, optimizer, and synthetic guardrails', async () => {
    renderPage();

    const section = await screen.findByTestId('options-lab-decision-engine');
    expect(within(section).getByText('情景准备度')).toBeInTheDocument();
    await waitFor(() => {
      expect(within(section).getAllByText('预期波动').length).toBeGreaterThan(0);
    });
    expect(screen.getByTestId('options-lab-risk-boundary-panel')).toHaveTextContent('数据状态');
    expect(within(section).getByText('最大亏损')).toBeInTheDocument();
    expect(within(section).getAllByText('数据不足，禁止判断').length).toBeGreaterThan(0);
    expect(within(section).getAllByText('演示/延迟数据').length).toBeGreaterThan(0);
    expect(screen.getByTestId('options-lab-risk-boundary-panel')).toHaveTextContent('不可作为交易信号');
    expect(within(section).getByText('IV / 敏感度')).toBeInTheDocument();
    expect(within(section).getAllByText('IV 分位不可用').length).toBeGreaterThan(0);
    expect(within(section).getAllByText('$7.50').length).toBeGreaterThan(0);
    expect(within(section).getByText('观察结构')).toBeInTheDocument();
    expect(within(section).getAllByText(/边界原因：数据质量未达到可判断等级/).length).toBeGreaterThan(0);
    expect(within(section).getAllByText(/牛市看涨价差/).length).toBeGreaterThan(0);
    expect(document.body.textContent || '').not.toContain('有条件可交易');
    expect(document.body.textContent || '').not.toContain('适合等待更好定价');
    expect(within(section).queryByText(/synthetic_or_fixture_data_not_decision_grade|provider_timeout/i)).not.toBeInTheDocument();
  });

  it('shows a non-decision-grade boundary for blocked gate payloads', async () => {
    renderPage();

    const section = await screen.findByTestId('options-lab-decision-engine');
    const riskPanel = screen.getByTestId('options-lab-risk-boundary-panel');
    await waitFor(() => {
      expect(screen.getByTestId('options-lab-decision-summary')).toBeInTheDocument();
    });

    expect(within(section).getAllByText('未达到可判断等级，仅供情景观察，不可作为交易信号。').length).toBeGreaterThan(0);
    expect(within(riskPanel).getByText('未达到可判断等级，仅供情景观察，不可作为交易信号。')).toBeInTheDocument();
    expect(within(section).getByText('观察结构')).toBeInTheDocument();
    expect(within(section).queryByText('主要策略')).not.toBeInTheDocument();
    expect(document.body.textContent || '').not.toContain('决策中枢');
    expect(document.body.textContent || '').not.toContain('策略决策');
    expect(document.body.textContent || '').not.toContain('首选观察');
    expect(document.body.textContent || '').not.toContain('可观察结构');
  });

  it('keeps delayed and demo fixture states explicitly observation-only', async () => {
    renderPage();

    const section = await screen.findByTestId('options-lab-decision-engine');
    const snapshotPanel = screen.getByTestId('options-lab-snapshot-panel');
    await waitFor(() => {
      expect(within(section).getAllByText('演示/延迟数据：仅用于界面与情景验证，不生成判断结论。').length).toBeGreaterThan(0);
    });

    expect(within(snapshotPanel).getAllByText('演示/延迟数据').length).toBeGreaterThan(0);
    expect(within(section).getAllByText('演示/延迟数据').length).toBeGreaterThan(0);
    expect(document.body.textContent || '').not.toContain('适合等待更好定价');
  });

  it('consolidates risk warnings into a compact boundary with hidden overflow caveats', async () => {
    renderPage();

    const riskPanel = await screen.findByTestId('options-lab-risk-boundary-panel');
    await waitFor(() => {
      expect(within(riskPanel).getAllByText('数据不足，禁止判断').length).toBeGreaterThan(0);
    });
    const visibleWarnings = within(riskPanel).getAllByTestId('options-lab-visible-risk-warning');
    expect(visibleWarnings.length).toBeLessThanOrEqual(3);
    expect(within(riskPanel).getByText('更多限制')).toBeInTheDocument();
    expect(within(riskPanel).getByText('数据状态')).toBeInTheDocument();
    expect(riskPanel.textContent || '').not.toContain('synthetic_or_fixture_data_not_decision_grade');
    expect(riskPanel.textContent || '').not.toContain('synthetic delayed');
  });

  it('renders compact fail-closed evidence badges on decision and risk panels', async () => {
    renderPage();

    const decision = await screen.findByTestId('options-lab-decision-engine');
    const riskPanel = screen.getByTestId('options-lab-risk-boundary-panel');
    await waitFor(() => {
      expect(screen.getByTestId('options-lab-decision-summary')).toBeInTheDocument();
    });
    expect(within(decision).getAllByText('数据不足，禁止判断').length).toBeGreaterThan(0);
    expect(within(decision).getAllByText('演示/延迟数据').length).toBeGreaterThan(0);
    expect(within(riskPanel).getAllByText('数据不足，禁止判断').length).toBeGreaterThan(0);
    expect(within(riskPanel).queryByText(/synthetic_or_fixture_data_not_decision_grade|provider_timeout/i)).not.toBeInTheDocument();
  });

  it('keeps the command area above the fold and the decision summary ahead of deep chain and limitation detail', async () => {
    renderPage();

    const decision = await screen.findByTestId('options-lab-decision-engine');
    const summary = await screen.findByTestId('options-lab-decision-summary');
    const analysisDetails = await screen.findByTestId('options-lab-analysis-details');
    const callsTable = await screen.findByTestId('options-lab-calls-table');
    const putsTable = await screen.findByTestId('options-lab-puts-table');
    const strategyDetails = await screen.findByTestId('options-lab-strategy-comparison');

    const assumptions = screen.getByTestId('options-lab-assumptions-panel');
    expect(decision).toContainElement(summary);
    expect(summary).toHaveTextContent('观察状态');
    expect(summary).toHaveTextContent('数据不足，禁止判断');
    expect(summary).toHaveTextContent('牛市看涨价差');
    expect(summary).toHaveTextContent('边界原因：数据质量未达到可判断等级');
    expect(Boolean(assumptions.compareDocumentPosition(decision) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(within(analysisDetails).getByRole('button', { name: /展开/ })).toHaveAttribute('aria-expanded', 'false');
    expect(Boolean(decision.compareDocumentPosition(analysisDetails) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(callsTable).toBeInTheDocument();
    expect(putsTable).toBeInTheDocument();
    expect(strategyDetails).toHaveTextContent('策略候选');
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

    const decision = await screen.findByTestId('options-lab-decision-engine');
    await waitFor(() => {
      expect(within(decision).getAllByText('暂无可判断结构').length).toBeGreaterThan(0);
    });
    expect(within(decision).getAllByText('数据不足，禁止判断').length).toBeGreaterThan(0);
    expect(within(decision).getByText(/边界原因：候选结构边际优势或风险回报不足/)).toBeInTheDocument();
  });

  it('renders missing sensitivity and liquidity warnings in the decision section', async () => {
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
    const riskPanel = screen.getByTestId('options-lab-risk-boundary-panel');
    await waitFor(() => {
      expect(within(riskPanel).getByRole('button', { name: /展开 更多限制/ })).toHaveAttribute('aria-expanded', 'false');
    });
    await act(async () => {
      within(riskPanel).getByRole('button', { name: /展开 更多限制/ }).click();
    });
    expect(within(riskPanel).getAllByText('买卖价差过宽').length).toBeGreaterThan(0);
    expect(within(riskPanel).getAllByText('敏感度缺失').length).toBeGreaterThan(0);
    expect(section).toHaveTextContent('情景准备度');
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

    expect(await screen.findByText('暂无可用到期日')).toBeInTheDocument();
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

    expect((await screen.findAllByText('标的快照')).length).toBeGreaterThan(0);
    const section = await screen.findByTestId('options-lab-strategy-comparison');
    expect(within(section).getByText('策略候选')).toBeInTheDocument();
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

    expect((await screen.findAllByText('标的快照')).length).toBeGreaterThan(0);
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

    expect((await screen.findAllByText('标的快照')).length).toBeGreaterThan(0);
    const section = await screen.findByTestId('options-lab-strategy-comparison');
    expect(within(section).getByText('策略候选')).toBeInTheDocument();
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

    expect((await screen.findAllByText('标的快照')).length).toBeGreaterThan(0);
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

  it('keeps data readiness user-facing without developer details', async () => {
    renderPage();

    expect(await screen.findByText('TEM260619C00055000')).toBeInTheDocument();
    expect(screen.queryByTestId('options-lab-developer-details')).not.toBeInTheDocument();
    expect(screen.queryByTestId('options-lab-strategy-developer-details')).not.toBeInTheDocument();
    expect(screen.queryByTestId('options-lab-decision-developer-details')).not.toBeInTheDocument();
    expect(screen.getByTestId('options-lab-risk-boundary-panel')).toHaveTextContent('风险边界');
    expect(screen.getByTestId('options-lab-analysis-details')).toHaveTextContent('数据限制');
    expect(within(screen.getByTestId('options-lab-analysis-details')).getByRole('button', { name: /展开/ })).toHaveAttribute('aria-expanded', 'false');
    expect(document.body.textContent || '').not.toMatch(/开发者|Developer|provider_validation_required|mocked_frontend_shell|fixture_frontend_phase4/i);
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
    expect(screen.queryByTestId('options-lab-crash-developer-details')).not.toBeInTheDocument();
    const crashShell = screen.getByText('期权实验室暂时无法加载，请刷新或稍后重试。').closest('main');
    expect(crashShell).not.toBeNull();
    expect(crashShell?.className).not.toContain('min-h-screen');
    expect(crashShell?.className).not.toContain('bg-[#050505]');
    const domText = document.body.textContent || '';
    expect(domText).not.toContain('TypeError');
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
      '开发者详情',
      'debug',
      'raw',
      'schema',
      'trace',
      'provider_timeout',
      'not_enough_history',
      'fundamentals_unavailable',
      'optional_news_timeout',
      'LLM Ledger',
      'QUOTA PILOT',
      'MarketCache',
      'provider.example',
    ].forEach((text) => {
      expect(domText.toLowerCase()).not.toContain(text.toLowerCase());
    });
  });

  it('uses ghost materials instead of local solid black slabs for major panels', async () => {
    renderPage();

    await screen.findByText('TEM260619C00055000');
    [
      'options-lab-snapshot-panel',
      'options-lab-decision-engine',
      'options-lab-risk-boundary-panel',
      'options-lab-strategy-comparison',
    ].forEach((testId) => {
      const panel = screen.getByTestId(testId);
      expect(panel.className).toMatch(/border-\[color:var\(--wolfy-border-subtle\)\]/);
      expect(panel.className).not.toMatch(/\bbg-(black|\[#000\]|\[#050505\]|gray-|zinc-|slate-|neutral-)/);
    });
    expect(screen.getByTestId('options-lab-analysis-details').className).toMatch(/bg-\[var\(--wolfy-surface-console\)\]/);
    expect(screen.getByTestId('options-lab-assumptions-panel')).toHaveTextContent('ExperimentConsole');
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
    expect(within(section).getByText('情景准备度')).toBeInTheDocument();
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
    expect((await screen.findAllByText('暂无数据')).length).toBeGreaterThan(0);

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

    expect((await screen.findAllByText('标的快照')).length).toBeGreaterThan(0);
    expect(await screen.findByText('暂无可用到期日')).toBeInTheDocument();
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
