import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import OptionsLabPage, { OptionsLabErrorBoundary } from '../OptionsLabPage';
import { optionsLabApi } from '../../api/optionsLab';
import type { OptionsResearchReadiness } from '../../types/researchReadiness';

vi.mock('../../api/optionsLab', () => ({
  optionsLabApi: {
    getUnderlyingSummary: vi.fn(),
    getExpirations: vi.fn(),
    getOptionChain: vi.fn(),
    compareStrategies: vi.fn(),
    evaluateDecision: vi.fn(),
  },
}));

const NO_CONCLUSION_LABEL = '数据不足，暂不形成结论';
const WAITING_STATE_LABEL = '等待数据确认';
const SAFE_INSTRUCTION_BOUNDARY = '不构成交易或下单指令';
const OBSERVE_ONLY_EVIDENCE_COPY = '仅供观察，不作为结论依据';
const DEMO_EVIDENCE_COPY = '演示数据：当前数据延迟，仅用于界面与情景验证，不作为结论依据。';
const NON_DECISION_BOUNDARY_COPY = '未达到可判断等级，仅供情景观察，暂不形成结论。';

function buildOptionsResearchReadiness(
  overrides: Partial<OptionsResearchReadiness> = {},
): OptionsResearchReadiness {
  return {
    optionsResearchReady: false,
    readinessState: 'blocked',
    dataQualityTier: 'synthetic_demo_only',
    decisionGrade: false,
    providerAuthority: 'observationOnly',
    liquidityGate: 'manual_review',
    ivGreeksGate: 'blocked',
    spreadGate: 'manual_review',
    scenarioCoverage: 'single_contract',
    noTradingBoundary: {
      analyticalOnly: true,
      noBrokerExecution: true,
      noOrderPlacement: true,
      noPortfolioMutation: true,
      noTradingRecommendation: true,
    },
    blockingReasons: [
      'provider_authority_tier_observation_only',
      'synthetic_or_fixture_data_not_decision_grade',
      'missing_iv',
      'missing_greeks',
      'low_or_missing_volume',
      'wide_bid_ask_spread',
    ],
    nextEvidenceNeeded: [
      '补充 provider authority 与 live chain 证据',
      '补充 Greeks 与 IV 证据',
      '补充 OI/成交量与更紧价差证据',
    ],
    ...overrides,
  };
}

function withOptionsReadiness<T extends object>(
  payload: T,
  readiness?: OptionsResearchReadiness | null,
): T & {
  optionsReadiness?: OptionsResearchReadiness | null;
  optionsResearchReadiness?: OptionsResearchReadiness | null;
} {
  if (!readiness) return payload;
  return {
    ...payload,
    optionsReadiness: readiness,
    optionsResearchReadiness: readiness,
  };
}

function buildScenarioEvidenceFrame(overrides: Record<string, unknown> = {}) {
  return {
    contractVersion: 'options-consumer-scenario-frame-v1',
    frameState: 'blocked',
    scenarioCoverage: 'strategy_compare_ready',
    chainQuality: {
      hasChain: true,
      contractCount: 2,
      callCount: 2,
      putCount: 0,
      freshness: 'synthetic_delayed',
      sourceType: 'synthetic_fixture',
      coverageState: 'strategy_compare_ready',
    },
    liquidityGate: 'manual_review',
    ivGreeksGate: 'blocked',
    spreadGate: 'manual_review',
    payoffEvidence: {
      targetPrice: 65,
      payoffAtTarget: 270,
      expectedMoveAbs: 7.5,
      expectedMovePct: 14.31,
      expectedMoveSource: 'straddle_mid',
      candidateCount: 4,
      comparisonState: 'strategy_compare_ready',
    },
    riskEvidence: {
      premiumAtRisk: 230,
      maxLoss: 230,
      maxGain: 270,
      breakeven: 52.3,
      requiredMovePct: -0.19,
    },
    assumptions: {
      inputMode: 'decision',
      direction: 'bullish',
      targetPrice: 65,
      targetDate: '2026-08-21',
      riskProfile: 'balanced',
      targetPriceStatus: 'target_above_breakeven',
    },
    missingEvidence: ['provider authority', 'live chain', 'iv greeks', 'bid ask'],
    nextEvidenceNeeded: [
      '补充 provider authority 与 live chain 证据',
      '补充 Greeks 与 IV 证据',
      '补充 OI/成交量与更紧价差证据',
    ],
    noTradingBoundary: {
      analyticalOnly: true,
      noBrokerExecution: true,
      noOrderPlacement: true,
      noPortfolioMutation: true,
      noTradingRecommendation: true,
    },
    ...overrides,
  };
}

function mockHappyPath(readiness?: OptionsResearchReadiness | null) {
  vi.mocked(optionsLabApi.getUnderlyingSummary).mockResolvedValue(withOptionsReadiness({
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
  }, readiness));
  vi.mocked(optionsLabApi.getExpirations).mockResolvedValue(withOptionsReadiness({
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
  }, readiness));
  vi.mocked(optionsLabApi.getOptionChain).mockResolvedValue(withOptionsReadiness({
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
  }, readiness));
  vi.mocked(optionsLabApi.compareStrategies).mockResolvedValue(withOptionsReadiness({
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
    optionsConsumerScenarioFrame: buildScenarioEvidenceFrame({
      frameState: 'blocked',
      scenarioCoverage: 'strategy_compare_ready',
      chainQuality: {
        hasChain: true,
        contractCount: 2,
        callCount: 2,
        putCount: 0,
        freshness: 'unknown',
        sourceType: 'unknown',
        coverageState: 'strategy_compare_ready',
      },
      payoffEvidence: {
        targetPrice: 65,
        payoffAtTarget: 270,
        candidateCount: 4,
        comparisonState: 'strategy_compare_ready',
      },
      assumptions: {
        inputMode: 'strategy_compare',
        direction: 'bullish',
        targetPrice: 65,
        targetDate: '2026-08-21',
        riskProfile: 'balanced',
      },
      missingEvidence: ['provider authority', 'live chain', 'bid ask', 'iv greeks'],
    }),
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
  }, readiness));
  vi.mocked(optionsLabApi.evaluateDecision).mockResolvedValue(withOptionsReadiness({
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
    optionsConsumerScenarioFrame: buildScenarioEvidenceFrame(),
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
  }, readiness));
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/zh/options-lab']}>
      <OptionsLabPage />
    </MemoryRouter>,
  );
}

async function expectContractSymbolVisible(symbol: string) {
  expect((await screen.findAllByText(symbol)).length).toBeGreaterThan(0);
}

describe('OptionsLabPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockHappyPath();
  });

  it('renders the Chinese-first scenario console with command area, main workspace, and dense chain matrices', async () => {
    renderPage();

    const heading = screen.getByRole('heading', { level: 1, name: '期权实验室' });
    expect(heading).toHaveClass('text-xl', 'md:text-2xl');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.queryByText('分析支持 / 不构成投资建议')).not.toBeInTheDocument();
    expect(screen.queryByText(/教程|如何使用|从这里开始/)).not.toBeInTheDocument();
    expect(screen.queryByText(/provider_timeout|MarketCache|generatedCandidates|failedCandidates/i)).not.toBeInTheDocument();
    const pageRoot = screen.getByTestId('options-lab-page-root');
    expect(pageRoot).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(pageRoot).toHaveClass('w-full', 'max-w-[var(--wolfy-consumer-shell-max,1880px)]', 'mx-auto', 'px-4', 'xl:px-8', 'flex', 'flex-col');
    expect(pageRoot).not.toHaveClass('max-w-[1600px]');
    expect(pageRoot.parentElement).toHaveAttribute('data-workspace-width', 'near-full');
    expect(pageRoot.closest('main')).toHaveClass('w-full', 'overflow-x-hidden', 'text-white');
    expect(pageRoot.closest('main')).not.toHaveClass('py-4');
    expect(pageRoot.className).not.toMatch(/\bbg-(black|\[#000\]|\[#050505\]|gray-|zinc-|slate-|neutral-)/);

    const commandArea = screen.getByTestId('options-lab-assumptions-panel');
    expect(commandArea).toHaveTextContent('情景控制台');
    expect(commandArea).toHaveTextContent('期权情景输入');
    expect(commandArea).toHaveTextContent('只读观察');
    expect(commandArea).toHaveTextContent('门控优先');
    expect(commandArea).toHaveTextContent(SAFE_INSTRUCTION_BOUNDARY);
    expect(commandArea).not.toHaveTextContent('ExperimentConsole');
    expect(within(commandArea).getByLabelText('标的代码')).toHaveValue('TEM');
    expect(within(commandArea).getByRole('button', { name: '刷新情景' })).toHaveAttribute('data-terminal-primitive', 'button');
    expect(within(commandArea).getByLabelText('到期日')).toBeInTheDocument();
    expect(within(commandArea).getByText('上行情景假设')).toBeInTheDocument();
    expect(within(commandArea).getByText('下行情景假设')).toBeInTheDocument();
    expect(within(commandArea).getByText('区间情景')).toBeInTheDocument();
    expect(within(commandArea).getByText('波动扩张')).toBeInTheDocument();

    const productHero = screen.getByTestId('options-lab-product-hero');
    expect(productHero).toHaveTextContent('情景分析台');
    await waitFor(() => {
      expect(productHero).toHaveTextContent('TEM');
      expect(productHero).toHaveTextContent(WAITING_STATE_LABEL);
      expect(productHero).toHaveTextContent('有限置信度');
      expect(productHero).toHaveTextContent('期权数据暂不可用，情景分析已暂停。');
      expect(productHero).toHaveTextContent('最后更新：');
    });
    expect(screen.getByTestId('options-lab-research-readiness-strip')).toHaveTextContent('研究就绪度');
    expect(screen.getByTestId('options-lab-research-readiness-strip')).toHaveTextContent(/研究结论受限|仅观察|等待证据更新/);
    const inputRegion = screen.getByTestId('options-lab-input-region');
    expect(inputRegion).toHaveTextContent('情景参数');
    expect(inputRegion).toHaveTextContent('这里仅记录研究输入，不直接形成交易或下单结论');
    const summaryStrip = screen.getByTestId('options-lab-summary-strip');
    expect(summaryStrip).toHaveTextContent('输入情景');
    expect(summaryStrip).toHaveTextContent('首个观察结构');
    expect(summaryStrip).toHaveTextContent('专业结构：牛市看涨价差');
    expect(summaryStrip).toHaveTextContent('风险边界');
    expect(inputRegion).toContainElement(summaryStrip);
    const outputRegion = screen.getByTestId('options-lab-output-region');
    expect(outputRegion).toHaveTextContent('分析结果');
    expect(outputRegion).toHaveTextContent('先看结构与风险，再下钻图形和明细');
    expect(screen.getByTestId('options-lab-bento-grid')).toHaveClass('mt-5', 'grid', 'gap-6');
    ['期权情景输入', '观察结构样例', '收益边界与 IV 快照', '情景判断', '风险边界', '数据注记', 'Call / Put 链', '流动性与下一步'].forEach((label) => {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    });
    expect(screen.getByTestId('options-lab-analysis-details')).toHaveTextContent('默认折叠');

    expect(await screen.findByTestId('options-lab-decision-engine')).toBeInTheDocument();
    expect(screen.getByTestId('options-lab-risk-boundary-panel')).toBeInTheDocument();
    expect(screen.getByTestId('options-lab-context-rail-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('options-lab-chain-details')).not.toBeInTheDocument();
    expect(screen.queryByTestId('options-lab-strategy-details')).not.toBeInTheDocument();
    expect((await screen.findAllByText('Call 链')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Put 链').length).toBeGreaterThan(0);
    expect(screen.getAllByText('行权价').length).toBeGreaterThan(0);
    expect(screen.getAllByText('中间价').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('options-lab-chain-panel')).toHaveLength(2);
    expect(screen.getByTestId('options-lab-risk-boundary-panel')).toHaveTextContent(/仅供观察|暂不形成结论/);
  });

  it('renders ranked compact strategy candidates with one highlighted primary row', async () => {
    renderPage();

    const section = await screen.findByTestId('options-lab-strategy-comparison');
    expect(within(section).getAllByText('观察结构样例').length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(within(section).getByText(/专业结构：看涨期权多头 · Call 多头/)).toBeInTheDocument();
      expect(within(section).getByText(/专业结构：看跌期权多头 · Put 多头/)).toBeInTheDocument();
      expect(within(section).getByText(/专业结构：牛市看涨价差 · Call 借方价差/)).toBeInTheDocument();
      expect(within(section).getByText(/专业结构：熊市看跌价差 · Put 借方价差/)).toBeInTheDocument();
    });
    ['状态', '最大亏损', '情景上沿', '盈亏平衡', '目标价下情景估算', '核心原因'].forEach((label) => {
      expect(within(section).getAllByText(label).length).toBeGreaterThan(0);
    });
    expect(within(section).getByTestId('options-lab-primary-strategy-row')).toHaveTextContent('样例顺序 #1');
    expect(within(section).getByTestId('options-lab-primary-strategy-row')).toHaveTextContent('观察结构样例 #1');
    expect(within(section).getByTestId('options-lab-primary-strategy-row')).toHaveTextContent('未达判断等级');
    expect(within(section).getByTestId('options-lab-strategy-grid')).toHaveClass('2xl:grid-cols-2');
    expect(within(section).queryByText('流动性提示')).not.toBeInTheDocument();
    expect(within(section).queryByText('波动率 / 时间价值提示')).not.toBeInTheDocument();
    expect(within(section).getByText('先把样例结构作为风险剖面阅读，再复核最大亏损、盈亏平衡与流动性边界。')).toBeInTheDocument();
    expect(within(section).queryByText('候选策略')).not.toBeInTheDocument();
    expect(within(section).queryByText('观察排序 #1')).not.toBeInTheDocument();
    expect(document.body.textContent || '').not.toContain('Bull Call Spread');
    expect(document.body.textContent || '').not.toContain('Long Call');
  });

  it('renders the R2 decision section with IV rank, expected move, optimizer, and synthetic guardrails', async () => {
    renderPage();

    const section = await screen.findByTestId('options-lab-decision-engine');
    expect(within(section).getByText('情景判断')).toBeInTheDocument();
    await waitFor(() => {
      expect(within(section).getAllByText('预期波动').length).toBeGreaterThan(0);
    });
    expect(screen.getByTestId('options-lab-risk-boundary-panel')).toHaveTextContent('数据状态');
    expect(within(section).getByText('最大亏损')).toBeInTheDocument();
    expect(within(section).getAllByText(NO_CONCLUSION_LABEL).length).toBeGreaterThan(0);
    expect(within(section).getAllByText('演示/延迟数据').length).toBeGreaterThan(0);
    expect(screen.getByTestId('options-lab-risk-boundary-panel')).toHaveTextContent(OBSERVE_ONLY_EVIDENCE_COPY);
    expect(within(section).getByText('IV / 敏感度')).toBeInTheDocument();
    expect(within(section).getAllByText('IV 分位不可用').length).toBeGreaterThan(0);
    expect(within(section).getAllByText('$7.50').length).toBeGreaterThan(0);
    expect(within(section).getAllByText('观察结构样例').length).toBeGreaterThan(0);
    expect(within(section).getAllByText(/边界原因：数据质量未达到可判断等级/).length).toBeGreaterThan(0);
    expect(within(section).getAllByText(/专业结构：牛市看涨价差/).length).toBeGreaterThan(0);
    expect(document.body.textContent || '').not.toContain('有条件可交易');
    expect(document.body.textContent || '').not.toContain('适合等待更好定价');
    expect(within(section).queryByText(/synthetic_or_fixture_data_not_decision_grade|provider_timeout/i)).not.toBeInTheDocument();
  });

  it('renders a compact scenario evidence section from the consumer scenario frame and keeps existing decision numerics unchanged', async () => {
    renderPage();

    const section = await screen.findByTestId('options-lab-scenario-evidence');
    expect(within(section).getByText('情景证据')).toBeInTheDocument();
    expect(within(section).getByText('证据状态')).toBeInTheDocument();
    expect(within(section).getByText('情景覆盖')).toBeInTheDocument();
    expect(within(section).getByText('链路质量')).toBeInTheDocument();
    expect(within(section).getByText('收益证据')).toBeInTheDocument();
    expect(within(section).getByText('风险证据')).toBeInTheDocument();
    expect(within(section).getByText('假设摘要')).toBeInTheDocument();
    expect(within(section).getByText('缺失证据')).toBeInTheDocument();
    expect(within(section).getByText('下一步补证')).toBeInTheDocument();
    expect(within(section).getByText('只读边界')).toBeInTheDocument();
    expect(within(section).getAllByText('已阻断').length).toBeGreaterThan(0);
    expect(within(section).getByText('策略比较覆盖')).toBeInTheDocument();
    expect(within(section).getByText('双边报价待补证')).toBeInTheDocument();
    expect(within(section).getByText('波动率与敏感度待补证')).toBeInTheDocument();
    expect(within(section).getByText('不触发执行动作')).toBeInTheDocument();
    expect(within(section).getByText('不改动现有持仓')).toBeInTheDocument();
    expect(within(section).getByText('结论仅用于研究记录')).toBeInTheDocument();
    expect(section).toHaveTextContent('$7.50');
    expect(section).toHaveTextContent('$230.00');
    expect(within(section).queryByText(/provider authority|live chain|iv greeks|bid ask|synthetic_fixture|debugRef/i)).not.toBeInTheDocument();
    expect(within(section).queryByText(/经纪商|订单|交易|buy|sell|trade|broker|order/i)).not.toBeInTheDocument();

    const decisionSection = screen.getByTestId('options-lab-decision-engine');
    expect(within(decisionSection).getAllByText('$7.50').length).toBeGreaterThan(0);
    expect(within(decisionSection).getAllByText('$230.00').length).toBeGreaterThan(0);
    expect(within(decisionSection).getAllByText(/专业结构：牛市看涨价差/).length).toBeGreaterThan(0);
  });

  it('renders payoff and IV visuals from existing strategy and chain data without changing read-only framing', async () => {
    renderPage();

    const section = await screen.findByTestId('options-lab-visuals-panel');
    expect(within(section).getByText('收益边界与 IV 快照')).toBeInTheDocument();
    expect(within(section).getByText('到期收益示意')).toBeInTheDocument();
    expect(within(section).getByText('IV 偏斜示意')).toBeInTheDocument();
    await waitFor(() => {
      expect(within(section).getByTestId('options-lab-payoff-visual')).toBeInTheDocument();
      expect(within(section).getByTestId('options-lab-iv-visual')).toBeInTheDocument();
    });
    expect(within(section).getByText('专业结构')).toBeInTheDocument();
    expect(within(section).getAllByText('牛市看涨价差').length).toBeGreaterThan(0);
    expect(within(section).getByText('Call / Put 点位')).toBeInTheDocument();
    expect(within(section).getByText('不构成买卖建议')).toBeInTheDocument();
    expect(within(section).getByText('不会提交订单')).toBeInTheDocument();
    expect(within(section).getByText('不连接经纪商')).toBeInTheDocument();
    expect(within(section).getByText('不改动投资组合')).toBeInTheDocument();
    expect(within(section).queryByText(/best contract|AI recommends you buy|buy now|sell now/i)).not.toBeInTheDocument();
  });

  it('shows compact missing-data states when payoff or IV inputs are unavailable', async () => {
    vi.mocked(optionsLabApi.getOptionChain).mockResolvedValueOnce(withOptionsReadiness({
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
          impliedVolatility: null,
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
          impliedVolatility: null,
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
    }, buildOptionsResearchReadiness()));
    vi.mocked(optionsLabApi.compareStrategies).mockResolvedValueOnce(withOptionsReadiness({
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
        riskProfile: 'balanced',
      },
      strategies: [
        {
          strategyType: 'bull_call_spread',
          legs: [],
          netDebit: 423,
          maxLoss: 423,
          maxGain: 500,
          breakeven: 59.23,
          requiredMovePct: 13.17,
          payoffAtTarget: 577,
          riskRewardRatio: 1.36,
          liquidityWarnings: [],
          ivThetaNotes: ['fixture_iv_only'],
          suitabilityNotes: ['scenario_analysis_only'],
          limitations: ['mocked_product_route_harness'],
          noAdviceDisclosure: 'Scenario analysis only; not personalized financial advice.',
        },
      ],
      limitations: ['mocked_product_route_harness'],
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
      },
    }, buildOptionsResearchReadiness()));

    renderPage();

    const section = await screen.findByTestId('options-lab-visuals-panel');
    expect(within(section).getByTestId('options-lab-payoff-empty')).toHaveTextContent('收益边界待补证');
    expect(within(section).getByTestId('options-lab-iv-empty')).toHaveTextContent('IV / 行权价快照待补证');
  });

  it('shows a non-decision-grade boundary for blocked gate payloads', async () => {
    renderPage();

    const section = await screen.findByTestId('options-lab-decision-engine');
    const riskPanel = screen.getByTestId('options-lab-risk-boundary-panel');
    await waitFor(() => {
      expect(screen.getByTestId('options-lab-decision-summary')).toBeInTheDocument();
    });

    expect(within(section).getAllByText(NON_DECISION_BOUNDARY_COPY).length).toBeGreaterThan(0);
    expect(within(riskPanel).getByText(NON_DECISION_BOUNDARY_COPY)).toBeInTheDocument();
    expect(within(section).getAllByText('观察结构样例').length).toBeGreaterThan(0);
    expect(within(section).queryByText('主要策略')).not.toBeInTheDocument();
    expect(document.body.textContent || '').not.toContain('决策中枢');
    expect(document.body.textContent || '').not.toContain('策略决策');
    expect(document.body.textContent || '').not.toContain('首选观察');
    expect(document.body.textContent || '').not.toContain('可观察结构');
  });

  it('renders compact readiness gate strips with observation-only framing and hidden raw codes', async () => {
    vi.mocked(optionsLabApi.evaluateDecision).mockResolvedValueOnce({
      symbol: 'TEM',
      strategy: 'bull_call_spread',
      dataQuality: {
        dataQualityScore: 25,
        dataQualityTier: 'synthetic_demo_only',
        blockingReasons: ['synthetic_or_fixture_data_not_decision_grade'],
        sourceType: 'synthetic',
      },
      liquidity: {
        liquidityScore: 42,
        spreadPct: 28,
        liquidityWarnings: ['wide_bid_ask_spread'],
      },
      ivGreeks: {
        ivReadiness: 44,
        ivRankStatus: 'unavailable',
        warnings: ['iv_rank_unavailable'],
      },
      decisionGrade: false,
      gateDecision: 'blocked',
      failClosedReasonCodes: ['synthetic_or_fixture_data_not_decision_grade'],
      gateIssues: ['synthetic_or_fixture_data_not_decision_grade', 'wide_bid_ask_spread'],
      dataQualityGates: {
        status: 'blocked',
        decisionGrade: false,
        tier: 'synthetic_demo_only',
      },
      liquidityGates: {
        status: 'restricted',
        passed: false,
        liquidityScore: 42,
      },
      expectedMove: {
        expectedMoveAbs: 7.5,
        expectedMovePct: 14.31,
        expectedMoveSource: 'straddle_mid',
      },
      optimizer: {
        preferredStrategyKey: null,
        optimizerLabel: '数据不足，禁止判断',
        noTradeReason: 'data_quality_not_decision_grade',
        alternatives: [],
      },
      rankedAlternatives: [
        {
          strategyKey: 'bull_call_spread',
          dataQualityTier: 'synthetic_demo_only',
          liquidityScore: 42,
          breakevenPressure: 0.19,
          maxLoss: 230,
          maxGain: 270,
          riskRewardRatio: 1.17,
          expectedMoveAlignment: 92,
          ivReadiness: 44,
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
    } as never);

    renderPage();

    const decisionStrip = await screen.findByTestId('options-lab-decision-readiness-strip');

    expect(decisionStrip).toHaveTextContent('未达判断等级');
    expect(decisionStrip).toHaveTextContent('仅观察');
    expect(decisionStrip).toHaveTextContent('数据质量受限');
    expect(decisionStrip).toHaveTextContent('流动性受限');
    expect(decisionStrip).toHaveTextContent('演示/延迟数据');
    expect(decisionStrip).toHaveTextContent('价差偏宽');
    expect(decisionStrip.textContent || '').not.toContain('synthetic_or_fixture_data_not_decision_grade');
    expect(decisionStrip.textContent || '').not.toContain('wide_bid_ask_spread');
    expect(decisionStrip.textContent || '').not.toMatch(/买入|卖出|推荐/);
  });

  it('surfaces additive readiness gates near the hero area without leaking internal labels', async () => {
    mockHappyPath(buildOptionsResearchReadiness());
    renderPage();

    const summary = await screen.findByTestId('options-lab-readiness-gate-summary');
    expect(summary).toHaveTextContent('门控摘要');
    expect(summary).toHaveTextContent('数据层级：演示/延迟');
    expect(summary).toHaveTextContent('授权级别：观察级');
    expect(summary).toHaveTextContent('流动性：人工复核');
    expect(summary).toHaveTextContent('IV / Greeks：已阻断');
    expect(summary).toHaveTextContent('价差：人工复核');
    expect(summary).toHaveTextContent('情景覆盖：单合约');
    expect(summary).toHaveTextContent('判断等级：未通过');
    expect(summary).toHaveTextContent('执行边界：只读无执行');
    expect(summary).toHaveTextContent('当前仍受授权、IV / Greeks 与流动性证据限制。');
    expect(summary).toHaveTextContent('下一步：补齐授权链路、IV / Greeks、OI / 成交量与更紧价差证据。');
    expect(summary.textContent || '').not.toContain('observationOnly');
    expect(summary.textContent || '').not.toContain('manual_review');
    expect(summary.textContent || '').not.toContain('single_contract');
    expect(summary.textContent || '').not.toContain('provider_authority_tier_observation_only');
    expect(summary.textContent || '').not.toContain('wide_bid_ask_spread');
  });

  it('fails closed when additive readiness is missing', async () => {
    renderPage();

    const summary = await screen.findByTestId('options-lab-readiness-gate-summary');
    expect(summary).toHaveTextContent('数据层级：证据不足');
    expect(summary).toHaveTextContent('授权级别：待补证');
    expect(summary).toHaveTextContent('流动性：已阻断');
    expect(summary).toHaveTextContent('IV / Greeks：已阻断');
    expect(summary).toHaveTextContent('价差：已阻断');
    expect(summary).toHaveTextContent('情景覆盖：缺少链路');
    expect(summary).toHaveTextContent('判断等级：未通过');
    expect(summary).toHaveTextContent('执行边界：只读无执行');
    expect(summary).toHaveTextContent('当前缺少就绪度回执，先按证据不足处理。');
    expect(summary).toHaveTextContent('下一步：补齐期权链、IV / Greeks 与流动性证据。');
  });

  it('keeps delayed usable readiness consumer-safe and observation-bounded', async () => {
    mockHappyPath(buildOptionsResearchReadiness({
      optionsResearchReady: true,
      readinessState: 'delayed_usable',
      dataQualityTier: 'delayed_usable',
      decisionGrade: true,
      providerAuthority: 'scoreGradeAllowed',
      liquidityGate: 'clear',
      ivGreeksGate: 'manual_review',
      spreadGate: 'clear',
      scenarioCoverage: 'single_contract',
      blockingReasons: [],
      nextEvidenceNeeded: ['等待更高新鲜度链路'],
    }));
    renderPage();

    const summary = await screen.findByTestId('options-lab-readiness-gate-summary');
    expect(summary).toHaveTextContent('数据层级：延迟可观察');
    expect(summary).toHaveTextContent('授权级别：授权链路');
    expect(summary).toHaveTextContent('流动性：已通过');
    expect(summary).toHaveTextContent('IV / Greeks：人工复核');
    expect(summary).toHaveTextContent('价差：已通过');
    expect(summary).toHaveTextContent('情景覆盖：单合约');
    expect(summary).toHaveTextContent('判断等级：可用');
    expect(summary).toHaveTextContent('执行边界：只读无执行');
    expect(summary).toHaveTextContent('等待更高新鲜度链路');
    expect(summary.textContent || '').not.toContain('scoreGradeAllowed');
    expect(summary.textContent || '').not.toContain('manual_review');
    expect(summary.textContent || '').not.toMatch(/买入|卖出|推荐|下单|经纪商/);
  });

  it('renders safe guarded UI when gateIssues arrive as API issue objects', async () => {
    vi.mocked(optionsLabApi.evaluateDecision).mockResolvedValueOnce({
      symbol: 'TEM',
      strategy: 'bull_call_spread',
      dataQuality: {
        dataQualityScore: 25,
        dataQualityTier: 'synthetic_demo_only',
        blockingReasons: ['synthetic_or_fixture_data_not_decision_grade'],
        sourceType: 'synthetic',
      },
      liquidity: {
        liquidityScore: 42,
        spreadPct: 28,
        liquidityWarnings: ['wide_bid_ask_spread'],
      },
      ivGreeks: {
        ivReadiness: 44,
        ivRankStatus: 'unavailable',
        warnings: ['iv_rank_unavailable'],
      },
      decisionGrade: false,
      gateDecision: 'blocked',
      failClosedReasonCodes: ['synthetic_or_fixture_data_not_decision_grade'],
      gateIssues: [
        {
          code: 'synthetic_or_fixture_data_not_decision_grade',
          category: 'freshness',
          status: 'blocked',
          label: '演示数据不可用于判断',
          decisionGrade: false,
          legIndex: 0,
          contractSymbol: 'TEM260619C00055000',
        },
        {
          code: 'wide_bid_ask_spread',
          category: 'liquidity',
          status: 'blocked',
          label: '买卖价差过宽',
          decisionGrade: false,
          legIndex: 1,
          contractSymbol: 'TEM260619C00060000',
        },
      ],
      dataQualityGates: {
        status: 'blocked',
        decisionGrade: false,
        tier: 'synthetic_demo_only',
      },
      liquidityGates: {
        status: 'blocked',
        passed: false,
        liquidityScore: 42,
      },
      expectedMove: {
        expectedMoveAbs: 7.5,
        expectedMovePct: 14.31,
        expectedMoveSource: 'straddle_mid',
      },
      optimizer: {
        preferredStrategyKey: null,
        optimizerLabel: '数据不足，禁止判断',
        noTradeReason: 'data_quality_not_decision_grade',
        alternatives: [
          {
            strategyKey: 'bull_call_spread',
            dataQualityTier: 'synthetic_demo_only',
            liquidityScore: 42,
            breakevenPressure: 0.19,
            maxLoss: 230,
            maxGain: 270,
            riskRewardRatio: 1.17,
            expectedMoveAlignment: 92,
            ivReadiness: 44,
            tradeQualityScore: 35,
            decisionLabel: '数据不足，禁止判断',
            primaryReasons: ['当前为 synthetic delayed / 演示数据'],
            riskWarnings: ['不可用于真实交易判断'],
          },
        ],
      },
      rankedAlternatives: [
        {
          strategyKey: 'bull_call_spread',
          dataQualityTier: 'synthetic_demo_only',
          liquidityScore: 42,
          breakevenPressure: 0.19,
          maxLoss: 230,
          maxGain: 270,
          riskRewardRatio: 1.17,
          expectedMoveAlignment: 92,
          ivReadiness: 44,
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
    } as never);

    renderPage();

    expect(await screen.findByRole('heading', { level: 1, name: '期权实验室' })).toBeInTheDocument();
    const decisionStrip = await screen.findByTestId('options-lab-decision-readiness-strip');

    expect(decisionStrip).toHaveTextContent('未达判断等级');
    expect(decisionStrip).toHaveTextContent('演示/延迟数据');
    expect(decisionStrip).toHaveTextContent('价差偏宽');
    expect(decisionStrip.textContent || '').not.toContain('synthetic_or_fixture_data_not_decision_grade');
    expect(decisionStrip.textContent || '').not.toContain('wide_bid_ask_spread');
    expect(decisionStrip.textContent || '').not.toMatch(/买入|卖出|推荐/);
    expect(screen.queryByText('期权实验室暂时无法加载，请刷新或稍后重试。')).not.toBeInTheDocument();
  });

  it('keeps maintainer setup actions out of the default consumer view', async () => {
    renderPage();

    const productHero = await screen.findByTestId('options-lab-product-hero');
    await waitFor(() => {
      expect(productHero).toHaveTextContent('期权数据暂不可用，情景分析已暂停。');
    });
    expect(screen.queryByTestId('options-lab-setup-path')).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '查看 Provider Ops' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '前往数据源设置' })).not.toBeInTheDocument();
    expect(screen.getByTestId('options-lab-risk-boundary-panel')).toHaveTextContent(OBSERVE_ONLY_EVIDENCE_COPY);
    expect(document.body.textContent || '').not.toMatch(/Provider Ops|数据源设置|fallback\/proxy|live options/i);
  });

  it('renders pass-but-review readiness gate strips for decision-grade payloads', async () => {
    vi.mocked(optionsLabApi.evaluateDecision).mockResolvedValueOnce({
      symbol: 'TEM',
      strategy: 'bull_call_spread',
      dataQuality: {
        dataQualityScore: 88,
        dataQualityTier: 'live_usable',
        warnings: [],
        sourceType: 'licensed',
      },
      liquidity: {
        liquidityScore: 84,
        spreadPct: 8,
        liquidityWarnings: [],
      },
      ivGreeks: {
        ivReadiness: 79,
        ivRankStatus: 'available',
        ivRank: 62,
        ivPercentile: 58,
        warnings: [],
      },
      ivRank: 62,
      ivPercentile: 58,
      ivRankStatus: 'available',
      decisionGrade: true,
      gateDecision: 'passed',
      failClosedReasonCodes: [],
      gateIssues: [],
      dataQualityGates: {
        status: 'passed',
        decisionGrade: true,
        tier: 'live_usable',
      },
      liquidityGates: {
        status: 'passed',
        passed: true,
        liquidityScore: 84,
      },
      expectedMove: {
        expectedMoveAbs: 6.2,
        expectedMovePct: 11.84,
        expectedMoveSource: 'straddle_mid',
      },
      optimizer: {
        preferredStrategyKey: 'bull_call_spread',
        optimizerLabel: '仅观察',
        noTradeReason: null,
        alternatives: [
          {
            strategyKey: 'bull_call_spread',
            dataQualityTier: 'live_usable',
            liquidityScore: 84,
            breakevenPressure: 0.12,
            maxLoss: 210,
            maxGain: 290,
            riskRewardRatio: 1.38,
            expectedMoveAlignment: 88,
            ivReadiness: 79,
            tradeQualityScore: 74,
            decisionLabel: '仅观察',
            primaryReasons: ['需人工复核'],
            riskWarnings: [],
          },
        ],
      },
      rankedAlternatives: [
        {
          strategyKey: 'bull_call_spread',
          dataQualityTier: 'live_usable',
          liquidityScore: 84,
          breakevenPressure: 0.12,
          maxLoss: 210,
          maxGain: 290,
          riskRewardRatio: 1.38,
          expectedMoveAlignment: 88,
          ivReadiness: 79,
          tradeQualityScore: 74,
          decisionLabel: '仅观察',
          primaryReasons: ['需人工复核'],
          riskWarnings: [],
        },
      ],
      breakeven: {
        breakeven: 56.1,
        requiredMovePct: 2.5,
        targetPriceStatus: 'target_above_breakeven',
        score: 78,
      },
      riskReward: {
        maxLoss: 210,
        maxGain: 290,
        riskRewardRatio: 1.38,
        score: 75,
      },
      tradeQualityScore: 74,
      decisionLabel: '仅观察',
      primaryReasons: ['需人工复核'],
      riskWarnings: [],
      noAdviceDisclosure: 'Analytical output only; not personalized financial advice.',
      freshness: {
        source: 'licensed_options',
        freshness: 'live',
      },
      metadata: {
        readOnly: true,
        noExternalCalls: true,
        noTradingRecommendation: true,
      },
    } as never);

    renderPage();

    const decisionStrip = await screen.findByTestId('options-lab-decision-readiness-strip');
    expect(decisionStrip).toHaveTextContent('判断条件较完整');
    expect(decisionStrip).toHaveTextContent('仍需人工复核');
    expect(decisionStrip.textContent || '').not.toMatch(/买入|卖出|推荐/);
  });

  it('keeps delayed and demo fixture states explicitly observation-only', async () => {
    renderPage();

    const section = await screen.findByTestId('options-lab-decision-engine');
    const evidence = await screen.findByTestId('options-lab-scenario-evidence');
    const productHero = screen.getByTestId('options-lab-product-hero');
    await waitFor(() => {
      expect(within(section).getAllByText(DEMO_EVIDENCE_COPY).length).toBeGreaterThan(0);
    });

    expect(within(productHero).getByText(WAITING_STATE_LABEL)).toBeInTheDocument();
    expect(within(productHero).getByText(NO_CONCLUSION_LABEL)).toBeInTheDocument();
    expect(within(section).getAllByText('演示/延迟数据').length).toBeGreaterThan(0);
    expect(evidence).toHaveTextContent('演示/延迟');
    expect(evidence).toHaveTextContent('仅观察');
    expect(document.body.textContent || '').not.toContain('适合等待更好定价');
  });

  it('consolidates risk warnings into a compact boundary with hidden overflow caveats', async () => {
    renderPage();

    const riskPanel = await screen.findByTestId('options-lab-risk-boundary-panel');
    await waitFor(() => {
      expect(within(riskPanel).getAllByText(NO_CONCLUSION_LABEL).length).toBeGreaterThan(0);
    });
    const visibleWarnings = within(riskPanel).getAllByTestId('options-lab-visible-risk-warning');
    expect(visibleWarnings.length).toBeLessThanOrEqual(3);
    expect(within(riskPanel).getByText('更多限制')).toBeInTheDocument();
    expect(within(riskPanel).getByText('数据状态')).toBeInTheDocument();
    expect(riskPanel.textContent || '').not.toContain('synthetic_or_fixture_data_not_decision_grade');
    expect(riskPanel.textContent || '').not.toContain('synthetic delayed');
  });

  it('deduplicates repeated external-data warnings into one counted summary', async () => {
    vi.mocked(optionsLabApi.evaluateDecision).mockResolvedValueOnce(withOptionsReadiness({
      symbol: 'TEM',
      strategy: 'bull_call_spread',
      dataQuality: {
        dataQualityScore: 25,
        dataQualityTier: 'synthetic_demo_only',
        blockingReasons: ['synthetic_or_fixture_data_not_decision_grade'],
        warnings: ['opaque_gap_a', 'opaque_gap_b'],
        sourceType: 'synthetic',
        asOfAgeMinutes: 0,
      },
      liquidity: {
        liquidityScore: 76,
        spreadPct: 10,
        liquidityWarnings: ['opaque_gap_c'],
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
      riskWarnings: ['opaque_gap_d', 'opaque_gap_e'],
      betterAlternative: {
        strategyType: 'bull_call_spread',
        reason: '定义风险结构降低权利金风险',
      },
      noAdviceDisclosure: 'Analytical output only; not personalized financial advice.',
      optionsConsumerScenarioFrame: buildScenarioEvidenceFrame(),
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
    }, buildOptionsResearchReadiness()));

    renderPage();

    const riskPanel = await screen.findByTestId('options-lab-risk-boundary-panel');
    await waitFor(() => {
      expect(within(riskPanel).getByText(/部分外部数据暂不可用（\d+项）/)).toBeInTheDocument();
    });
    expect(within(riskPanel).queryAllByText('部分外部数据暂不可用')).toHaveLength(0);
  });

  it('renders compact fail-closed evidence badges on decision and risk panels', async () => {
    renderPage();

    const decision = await screen.findByTestId('options-lab-decision-engine');
    const riskPanel = screen.getByTestId('options-lab-risk-boundary-panel');
    await waitFor(() => {
      expect(screen.getByTestId('options-lab-decision-summary')).toBeInTheDocument();
    });
    expect(within(decision).getAllByText(NO_CONCLUSION_LABEL).length).toBeGreaterThan(0);
    expect(within(decision).getAllByText('演示/延迟数据').length).toBeGreaterThan(0);
    expect(within(riskPanel).getAllByText(NO_CONCLUSION_LABEL).length).toBeGreaterThan(0);
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
    expect(summary).toHaveTextContent('判断状态');
    expect(summary).toHaveTextContent(NO_CONCLUSION_LABEL);
    expect(summary).toHaveTextContent('专业结构：牛市看涨价差');
    expect(summary).toHaveTextContent('边界原因：数据质量未达到可判断等级');
    expect(Boolean(assumptions.compareDocumentPosition(decision) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(within(analysisDetails).getByRole('button', { name: /展开/ })).toHaveAttribute('aria-expanded', 'false');
    expect(Boolean(decision.compareDocumentPosition(analysisDetails) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(callsTable).toBeInTheDocument();
    expect(putsTable).toBeInTheDocument();
    expect(strategyDetails).toHaveTextContent('观察结构样例');
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
    expect(within(decision).getAllByText(NO_CONCLUSION_LABEL).length).toBeGreaterThan(0);
    expect(within(decision).getByText(/边界原因：观察结构样例边际优势或风险回报不足/)).toBeInTheDocument();
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
      optionsConsumerScenarioFrame: buildScenarioEvidenceFrame({
        frameState: 'blocked',
        ivGreeksGate: 'blocked',
        spreadGate: 'manual_review',
        missingEvidence: ['iv greeks', 'bid ask', 'volume'],
        nextEvidenceNeeded: ['补充 Greeks 与 IV 证据', '补充 OI/成交量与更紧价差证据'],
      }),
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
    const evidence = await screen.findByTestId('options-lab-scenario-evidence');
    const riskPanel = screen.getByTestId('options-lab-risk-boundary-panel');
    await waitFor(() => {
      expect(within(riskPanel).getByRole('button', { name: /展开 更多限制/ })).toHaveAttribute('aria-expanded', 'false');
    });
    await act(async () => {
      within(riskPanel).getByRole('button', { name: /展开 更多限制/ }).click();
    });
    expect(within(riskPanel).getAllByText(/买卖价差过宽/).length).toBeGreaterThan(0);
    expect(within(riskPanel).getAllByText(/敏感度缺失/).length).toBeGreaterThan(0);
    expect(evidence).toHaveTextContent('波动率与敏感度待补证');
    expect(evidence).toHaveTextContent('双边报价待补证');
    expect(evidence).toHaveTextContent('人工复核');
    expect(evidence).toHaveTextContent('已阻断');
    expect(section).toHaveTextContent('情景判断');
  });

  it('keeps the page compatible when compare and decision responses do not include the new scenario frame', async () => {
    mockHappyPath();
    vi.mocked(optionsLabApi.compareStrategies).mockResolvedValueOnce(withOptionsReadiness({
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
      },
      strategies: [],
      limitations: ['fixture_backed_defined_risk_only'],
      metadata: {
        readOnly: true,
        fixtureBacked: true,
        syntheticData: true,
        noExternalCalls: true,
        noTradingRecommendation: true,
      },
    }));
    vi.mocked(optionsLabApi.evaluateDecision).mockResolvedValueOnce(withOptionsReadiness({
      symbol: 'TEM',
      strategy: 'bull_call_spread',
      dataQuality: {
        dataQualityScore: 25,
        dataQualityTier: 'synthetic_demo_only',
      },
      liquidity: {
        liquidityScore: 76,
        spreadPct: 10,
      },
      ivGreeks: {
        ivReadiness: 82,
        ivRankStatus: 'unavailable',
      },
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
      freshness: {
        source: 'synthetic_options_lab_fixture',
        freshness: 'synthetic_delayed',
      },
      metadata: {
        readOnly: true,
        fixtureBacked: true,
        syntheticData: true,
        noExternalCalls: true,
        noTradingRecommendation: true,
      },
    }));

    renderPage();

    expect(await screen.findByTestId('options-lab-decision-engine')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText('$230.00').length).toBeGreaterThan(0);
    });
    expect(screen.queryByTestId('options-lab-scenario-evidence')).not.toBeInTheDocument();
    expect(screen.getAllByText('$230.00').length).toBeGreaterThan(0);
    expect(screen.getByText('期权实验室')).toBeInTheDocument();
  });

  it('recomputes comparison and decision requests from the latest assumptions panel values', async () => {
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
        {
          date: '2026-07-17',
          dte: 72,
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
    vi.mocked(optionsLabApi.getOptionChain).mockImplementation(async (symbol, expiration) => ({
      symbol,
      expiration,
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
    }));

    renderPage();

    await expectContractSymbolVisible('TEM260619C00055000');

    vi.mocked(optionsLabApi.compareStrategies).mockClear();
    vi.mocked(optionsLabApi.evaluateDecision).mockClear();
    vi.mocked(optionsLabApi.getOptionChain).mockClear();

    const commandArea = screen.getByTestId('options-lab-assumptions-panel');
    fireEvent.change(within(commandArea).getByLabelText('假设价格'), { target: { value: '70' } });
    fireEvent.change(within(commandArea).getByLabelText('目标日期'), { target: { value: '2026-09-18' } });
    fireEvent.change(within(commandArea).getByLabelText('风险预算'), { target: { value: '1250' } });
    fireEvent.change(within(commandArea).getByLabelText('到期日'), { target: { value: '2026-07-17' } });
    fireEvent.click(within(commandArea).getByText('下行情景假设'));
    fireEvent.click(within(commandArea).getByText('进取'));

    await waitFor(() => {
      expect(vi.mocked(optionsLabApi.getOptionChain)).toHaveBeenCalledWith('TEM', '2026-07-17');
    });
    await waitFor(() => {
      expect(vi.mocked(optionsLabApi.compareStrategies)).toHaveBeenLastCalledWith(expect.objectContaining({
        symbol: 'TEM',
        direction: 'bearish',
        targetPrice: 70,
        targetDate: '2026-09-18',
        maxPremium: 1250,
        riskProfile: 'aggressive',
      }));
    });
    await waitFor(() => {
      expect(vi.mocked(optionsLabApi.evaluateDecision)).toHaveBeenLastCalledWith(expect.objectContaining({
        symbol: 'TEM',
        expiration: '2026-07-17',
        targetPrice: 70,
        targetDate: '2026-09-18',
        riskBudget: 1250,
      }));
    });

    const summaryStrip = screen.getByTestId('options-lab-summary-strip');
    expect(summaryStrip).toHaveTextContent('下行情景假设 · 假设价格 70');
    expect(summaryStrip).toHaveTextContent('风险预算 1250');
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
    expect(screen.getByText('等待结构比较前提')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('先选择可用到期日并加载合约后，再进入结构样例比较。')).toBeInTheDocument();
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

    expect((await screen.findAllByText('情景分析台')).length).toBeGreaterThan(0);
    const section = await screen.findByTestId('options-lab-strategy-comparison');
    expect(within(section).getByText('观察结构样例')).toBeInTheDocument();
    await waitFor(() => {
      expect(within(section).getByText('结构样例比较暂不可用。请稍后重试或调整假设。')).toBeInTheDocument();
    });
    await expectContractSymbolVisible('TEM260619C00055000');
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

    expect((await screen.findAllByText('情景分析台')).length).toBeGreaterThan(0);
    const section = await screen.findByTestId('options-lab-strategy-comparison');
    await waitFor(() => {
      expect(within(section).getByText(/专业结构：看涨期权多头 · Call 多头/)).toBeInTheDocument();
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

    expect((await screen.findAllByText('情景分析台')).length).toBeGreaterThan(0);
    const section = await screen.findByTestId('options-lab-strategy-comparison');
    expect(within(section).getByText('观察结构样例')).toBeInTheDocument();
    await waitFor(() => {
      expect(within(section).getByText('结构样例比较暂不可用。请稍后重试或调整假设。')).toBeInTheDocument();
    });
    await expectContractSymbolVisible('TEM260619C00055000');
  });

  it.each([401, 403])('keeps the base page usable when compare returns %s', async (status) => {
    vi.mocked(optionsLabApi.compareStrategies).mockRejectedValueOnce({
      response: { status, data: { detail: { error: 'auth_gated', raw_provider_payload: 'token=abc Traceback' } } },
      message: `HTTP ${status}`,
    });
    renderPage();

    expect((await screen.findAllByText('情景分析台')).length).toBeGreaterThan(0);
    const section = await screen.findByTestId('options-lab-strategy-comparison');
    await waitFor(() => {
      expect(within(section).getByText('结构样例比较暂不可用。请稍后重试或调整假设。')).toBeInTheDocument();
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
        expect(within(section).getByText('结构样例比较暂不可用。请稍后重试或调整假设。')).toBeInTheDocument();
      });
      expect((await screen.findAllByText('TEM260619C00055000')).length).toBeGreaterThan(0);
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
    expect(screen.getByText('期权链暂不可用，结构样例比较已暂停。')).toBeInTheDocument();
    expect(vi.mocked(optionsLabApi.compareStrategies)).not.toHaveBeenCalled();
    const domText = document.body.textContent || '';
    expect(domText).not.toContain('raw_provider_payload');
    expect(domText).not.toContain('token=abc');
    expect(domText).not.toContain('Traceback');
  });

  it('keeps data readiness user-facing without developer details', async () => {
    renderPage();

    await expectContractSymbolVisible('TEM260619C00055000');
    [
      'options-lab-developer-details',
      'options-lab-strategy-developer-details',
      'options-lab-decision-developer-details',
    ].forEach((testId) => {
      expect(screen.queryByTestId(testId)).not.toBeInTheDocument();
    });
    const productHero = screen.getByTestId('options-lab-product-hero');
    expect(productHero).toHaveTextContent(/当前期权信号数据不足，仅供观察。|期权数据暂不可用，情景分析已暂停。/);
    expect(productHero).toHaveTextContent('最后更新：');
    const decision = await screen.findByTestId('options-lab-decision-engine');
    await waitFor(() => {
      expect(screen.getByTestId('options-lab-decision-summary')).toBeInTheDocument();
    });
    expect(decision).toHaveTextContent(NO_CONCLUSION_LABEL);
    expect(decision).toHaveTextContent('演示数据');
    expect(screen.getByTestId('options-lab-risk-boundary-panel')).toHaveTextContent(OBSERVE_ONLY_EVIDENCE_COPY);
    expect(screen.getByTestId('options-lab-risk-boundary-panel')).toHaveTextContent('风险边界');
    expect(screen.getByTestId('options-lab-analysis-details')).toHaveTextContent('数据注记');
    expect(screen.getByTestId('options-lab-analysis-details')).toHaveTextContent('默认折叠');
    expect(within(screen.getByTestId('options-lab-analysis-details')).getByRole('button', { name: /展开/ })).toHaveAttribute('aria-expanded', 'false');
    expect(document.body.textContent || '').not.toMatch(/开发者|Developer|Provider Ops|数据源设置|backend|offline|provider_validation_required|mocked_frontend_shell|fixture_frontend_phase4|synthetic_or_fixture_data_not_decision_grade|provider_timeout/i);
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

    await expectContractSymbolVisible('TEM260619C00055000');
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
      'Provider Ops',
      'backend',
      'offline',
      'sourceAuthorityAllowed',
      'scoreContributionAllowed',
      'observationOnly',
      'reasonCode',
      'reasonFamilies',
    ].forEach((text) => {
      expect(domText.toLowerCase()).not.toContain(text.toLowerCase());
    });
  });

  it('uses ghost materials instead of local solid black slabs for major panels', async () => {
    renderPage();

    await expectContractSymbolVisible('TEM260619C00055000');
    [
      'options-lab-product-hero',
      'options-lab-decision-engine',
      'options-lab-risk-boundary-panel',
      'options-lab-strategy-comparison',
    ].forEach((testId) => {
      const panel = screen.getByTestId(testId);
      expect(panel.className).toMatch(/border-\[color:var\(--wolfy-border-subtle\)\]/);
      expect(panel.className).not.toMatch(/\bbg-(black|\[#000\]|\[#050505\]|gray-|zinc-|slate-|neutral-)/);
    });
    expect(screen.getByTestId('options-lab-analysis-details').className).toMatch(/bg-\[var\(--wolfy-surface-console\)\]/);
    expect(screen.getByTestId('options-lab-assumptions-panel')).not.toHaveTextContent('ExperimentConsole');
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
    expect(within(section).getByText('情景判断')).toBeInTheDocument();
    await waitFor(() => {
      expect(within(section).getAllByText(NO_CONCLUSION_LABEL).length).toBeGreaterThan(0);
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

    expect((await screen.findAllByText('情景分析台')).length).toBeGreaterThan(0);
    expect(await screen.findByText('暂无可用到期日')).toBeInTheDocument();
    expect(screen.getByText('先选择可用到期日并加载合约后，再进入结构样例比较。')).toBeInTheDocument();
    expect(vi.mocked(optionsLabApi.compareStrategies)).not.toHaveBeenCalled();
    expect(document.body.textContent || '').not.toContain('TypeError');
  });

  it('renders desktop chain tables and mobile chain cards from the same mocked chain data', async () => {
    renderPage();

    const callsTable = await screen.findByTestId('options-lab-calls-table');
    const putsTable = screen.getByTestId('options-lab-puts-table');
    const callsDesktopTable = within(callsTable).getByTestId('options-lab-calls-table-desktop-table');
    const putsDesktopTable = within(putsTable).getByTestId('options-lab-puts-table-desktop-table');
    const callsMobileList = within(callsTable).getByTestId('options-lab-calls-table-mobile-list');
    const putsMobileList = within(putsTable).getByTestId('options-lab-puts-table-mobile-list');

    expect(within(callsDesktopTable).getByText('TEM260619C00055000')).toBeInTheDocument();
    expect(within(putsDesktopTable).getByText('TEM260619P00050000')).toBeInTheDocument();

    const callCard = within(callsMobileList).getByTestId('options-lab-calls-table-mobile-card-TEM260619C00055000');
    const putCard = within(putsMobileList).getByTestId('options-lab-puts-table-mobile-card-TEM260619P00050000');
    expect(callCard).toHaveTextContent('TEM260619C00055000');
    expect(callCard).toHaveTextContent('行权价');
    expect(callCard).toHaveTextContent('$55.00');
    expect(callCard).toHaveTextContent('中间价');
    expect(callCard).toHaveTextContent('$4.23');
    expect(callCard).toHaveTextContent('买价 / 卖价');
    expect(callCard).toHaveTextContent('$4.10 / $4.35');
    expect(callCard).toHaveTextContent('IV');
    expect(callCard).toHaveTextContent('54.0%');
    expect(callCard).toHaveTextContent('Delta');
    expect(callCard).toHaveTextContent('0.42');
    expect(callCard).toHaveTextContent('Theta');
    expect(callCard).toHaveTextContent('-0.05');

    expect(putCard).toHaveTextContent('TEM260619P00050000');
    expect(putCard).toHaveTextContent('$50.00');
    expect(putCard).toHaveTextContent('$3.35');
    expect(putCard).toHaveTextContent('$3.20 / $3.50');
  });
});
