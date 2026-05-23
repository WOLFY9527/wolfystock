import apiClient from './index';
import { toCamelCase } from './utils';

export type OptionsDirection = 'bullish' | 'bearish' | 'neutral' | 'volatility';
export type OptionsRiskProfile = 'conservative' | 'balanced' | 'aggressive';
export type OptionsFreshness = 'live' | 'delayed' | 'cached' | 'stale' | 'fallback' | 'mock' | 'error';
export type OptionSide = 'call' | 'put';
export type OptionMoneyness = 'itm' | 'atm' | 'otm';
export type OptionsStrategyType = 'long_call' | 'long_put' | 'bull_call_spread' | 'bear_put_spread';

export type OptionsUnderlyingSnapshot = {
  price: number | null;
  changePct?: number | null;
  source: string;
  asOf: string;
  freshness: OptionsFreshness;
};

export type OptionsAvailability = {
  supported: boolean;
  provider: string;
  limitations: string[];
};

export type OptionsLabMetadata = {
  readOnly: boolean;
  noExternalCallsInTests: boolean;
  limitations: string[];
  sourceLabel?: string;
  updatedAt?: string;
};

export type OptionsUnderlyingSummaryResponse = {
  symbol: string;
  market: string;
  underlying: OptionsUnderlyingSnapshot;
  optionsAvailability: OptionsAvailability;
  metadata: OptionsLabMetadata;
};

export type OptionsExpiration = {
  date: string;
  dte: number;
  type: 'weekly' | 'monthly' | 'quarterly' | string;
  chainAvailable: boolean;
  asOf: string;
  source: string;
  warnings: string[];
};

export type OptionsExpirationsResponse = {
  symbol: string;
  expirations: OptionsExpiration[];
  metadata: OptionsLabMetadata;
};

export type OptionContract = {
  contractSymbol: string;
  side: OptionSide;
  strike: number;
  bid: number | null;
  ask: number | null;
  mid: number | null;
  volume: number | null;
  openInterest: number | null;
  impliedVolatility: number | null;
  delta?: number | null;
  gamma?: number | null;
  theta?: number | null;
  vega?: number | null;
  rho?: number | null;
  spreadPct?: number | null;
  moneyness: OptionMoneyness;
  liquidityScore?: number | null;
  warnings?: string[];
};

export type OptionsChainResponse = {
  symbol: string;
  expiration: string;
  underlying: OptionsUnderlyingSnapshot | null;
  calls: OptionContract[];
  puts: OptionContract[];
  filtersApplied: {
    minOpenInterest?: number;
    maxSpreadPct?: number;
  };
  chainAsOf: string;
  source: string;
  limitations: string[];
  metadata: OptionsLabMetadata;
};

export type OptionsStrategyCompareRequest = {
  symbol: string;
  direction: OptionsDirection;
  targetPrice: number;
  targetDate: string;
  maxPremium?: number;
  riskProfile: OptionsRiskProfile;
  strategies?: OptionsStrategyType[];
  forceRefresh?: boolean;
};

export type OptionsStrategyLeg = {
  action: 'buy' | 'sell';
  side: OptionSide;
  contractSymbol: string;
  expiration: string;
  strike: number;
  mid: number;
  quantity: number;
};

export type OptionsStrategyComparison = {
  strategyType: OptionsStrategyType;
  legs: OptionsStrategyLeg[];
  netDebit: number;
  maxLoss: number;
  maxGain: number | null;
  breakeven: number;
  requiredMovePct: number;
  payoffAtTarget: number;
  riskRewardRatio: number | null;
  liquidityWarnings: string[];
  ivThetaNotes: string[];
  suitabilityNotes: string[];
  limitations: string[];
  noAdviceDisclosure: string;
};

export type OptionsStrategyCompareMetadata = {
  readOnly?: boolean;
  fixtureBacked?: boolean;
  syntheticData?: boolean;
  noExternalCalls?: boolean;
  noLlmCalls?: boolean;
  noOrderPlacement?: boolean;
  noBrokerConnection?: boolean;
  noPortfolioMutation?: boolean;
  noTradingRecommendation?: boolean;
  scoringEngine?: string;
  strategyEngine?: string;
  forceRefreshIgnored?: boolean;
};

export type OptionsGateDetails = Record<string, unknown> | null;

export type OptionsStrategyCompareResponse = {
  symbol: string;
  underlying: Record<string, unknown>;
  assumptions: Record<string, unknown>;
  strategies: OptionsStrategyComparison[];
  limitations: string[];
  metadata: OptionsStrategyCompareMetadata;
};

export type OptionsDecisionLeg = {
  action: 'buy' | 'sell';
  side: OptionSide;
  contractSymbol?: string;
  expiration?: string;
  strike?: number;
  quantity?: number;
};

export type OptionsDecisionRequest = {
  symbol: string;
  strategy: OptionsStrategyType;
  expiration?: string;
  legs?: OptionsDecisionLeg[];
  targetPrice?: number;
  targetDate?: string;
  holdingHorizonDays?: number;
  riskBudget?: number;
  scenarioAssumptions?: Record<string, unknown>;
  forceRefresh?: boolean;
};

export type OptionsDecisionResponse = {
  symbol: string;
  strategy: OptionsStrategyType;
  dataQuality: {
    dataQualityScore: number | null;
    dataQualityTier: 'live_usable' | 'delayed_usable' | 'synthetic_demo_only' | 'insufficient' | string;
    sourceType?: string | null;
    asOfAgeMinutes?: number | null;
    blockingReasons?: string[] | null;
    warnings?: string[] | null;
  } | null;
  liquidity: {
    liquidityScore: number | null;
    spreadPct?: number | null;
    liquidityWarnings?: string[] | null;
  } | null;
  ivGreeks: {
    ivReadiness: number | null;
    ivRankStatus: 'unavailable' | 'available' | string;
    ivRank?: number | null;
    ivPercentile?: number | null;
    ivRankSource?: string | null;
    ivRankConfidence?: string | null;
    warnings?: string[] | null;
    dteBucket?: string | null;
  } | null;
  ivRank?: number | null;
  ivPercentile?: number | null;
  ivRankStatus?: 'unavailable' | 'available' | string | null;
  decisionGrade?: boolean | null;
  gateDecision?: string | null;
  failClosedReasonCodes?: string[] | null;
  gateIssues?: string[] | null;
  dataQualityGates?: OptionsGateDetails;
  liquidityGates?: OptionsGateDetails;
  expectedMove?: {
    expectedMoveAbs?: number | null;
    expectedMovePct?: number | null;
    expectedMoveSource?: 'straddle_mid' | 'iv_dte' | 'unavailable' | string | null;
    expectedMoveWarnings?: string[] | null;
  } | null;
  optimizer?: {
    preferredStrategyKey?: OptionsStrategyType | null;
    optimizerLabel?: '数据不足，禁止判断' | '不建议交易' | '仅观察' | '可关注替代结构' | '有条件可交易' | string | null;
    alternatives?: OptionsOptimizerAlternative[] | null;
    noTradeReason?: string | null;
  } | null;
  rankedAlternatives?: OptionsOptimizerAlternative[] | null;
  breakeven: {
    breakeven?: number | null;
    requiredMovePct?: number | null;
    targetPriceStatus?: string | null;
    score: number | null;
  } | null;
  riskReward: {
    maxLoss?: number | null;
    maxGain?: number | null;
    riskRewardRatio?: number | null;
    score: number | null;
    warnings?: string[] | null;
  } | null;
  tradeQualityScore: number | null;
  decisionLabel: string | null;
  primaryReasons?: string[] | null;
  riskWarnings?: string[] | null;
  betterAlternative?: {
    strategyType: OptionsStrategyType;
    reason: string;
    maxLoss?: number | null;
    riskRewardRatio?: number | null;
  } | null;
  noAdviceDisclosure?: string | null;
  freshness?: {
    source?: string | null;
    freshness?: string | null;
    asOf?: string | null;
  } | null;
  metadata?: OptionsStrategyCompareMetadata | null;
};

export type OptionsOptimizerAlternative = {
  strategyKey: OptionsStrategyType;
  dataQualityTier: 'live_usable' | 'delayed_usable' | 'synthetic_demo_only' | 'insufficient' | string;
  liquidityScore: number | null;
  breakevenPressure?: number | null;
  maxLoss?: number | null;
  maxGain?: number | null;
  riskRewardRatio?: number | null;
  expectedMoveAlignment?: number | null;
  ivReadiness?: number | null;
  tradeQualityScore: number | null;
  decisionLabel: string | null;
  primaryReasons?: string[] | null;
  riskWarnings?: string[] | null;
};

const FIXTURE_METADATA: OptionsLabMetadata = {
  readOnly: true,
  noExternalCallsInTests: true,
  limitations: ['mocked_frontend_shell', 'provider_validation_required'],
  sourceLabel: 'Fixture',
  updatedAt: '2026-05-06T09:45:00-04:00',
};

const FIXTURE_UNDERLYING: OptionsUnderlyingSnapshot = {
  price: 52.34,
  changePct: 1.2,
  source: 'fixture',
  asOf: '2026-05-06T09:45:00-04:00',
  freshness: 'mock',
};

const FIXTURE_EXPIRATION = '2026-06-19';

function fixtureSummary(symbol: string): OptionsUnderlyingSummaryResponse {
  return {
    symbol,
    market: 'us',
    underlying: FIXTURE_UNDERLYING,
    optionsAvailability: {
      supported: true,
      provider: 'fixture',
      limitations: ['provider_validation_required'],
    },
    metadata: FIXTURE_METADATA,
  };
}

function fixtureExpirations(symbol: string): OptionsExpirationsResponse {
  return {
    symbol,
    expirations: [
      {
        date: FIXTURE_EXPIRATION,
        dte: 44,
        type: 'monthly',
        chainAvailable: true,
        asOf: FIXTURE_UNDERLYING.asOf,
        source: 'fixture',
        warnings: ['mocked_chain'],
      },
      {
        date: '2026-08-21',
        dte: 107,
        type: 'monthly',
        chainAvailable: true,
        asOf: FIXTURE_UNDERLYING.asOf,
        source: 'fixture',
        warnings: ['mocked_chain'],
      },
    ],
    metadata: FIXTURE_METADATA,
  };
}

function fixtureChain(symbol: string, expiration = FIXTURE_EXPIRATION): OptionsChainResponse {
  return {
    symbol,
    expiration,
    underlying: FIXTURE_UNDERLYING,
    calls: [
      {
        contractSymbol: `${symbol}260619C00055000`,
        side: 'call',
        strike: 55,
        bid: 4.1,
        ask: 4.35,
        mid: 4.23,
        volume: 830,
        openInterest: 6120,
        impliedVolatility: 0.54,
        delta: 0.42,
        gamma: 0.04,
        theta: -0.05,
        vega: 0.11,
        spreadPct: 5.9,
        moneyness: 'otm',
        liquidityScore: 82,
        warnings: [],
      },
      {
        contractSymbol: `${symbol}260619C00060000`,
        side: 'call',
        strike: 60,
        bid: 2.15,
        ask: 2.4,
        mid: 2.28,
        volume: 510,
        openInterest: 3720,
        impliedVolatility: 0.59,
        delta: 0.28,
        gamma: 0.03,
        theta: -0.04,
        vega: 0.09,
        spreadPct: 11,
        moneyness: 'otm',
        liquidityScore: 69,
        warnings: ['wide_spread_watch'],
      },
    ],
    puts: [
      {
        contractSymbol: `${symbol}260619P00050000`,
        side: 'put',
        strike: 50,
        bid: 3.2,
        ask: 3.5,
        mid: 3.35,
        volume: 410,
        openInterest: 2900,
        impliedVolatility: 0.57,
        delta: -0.36,
        gamma: 0.04,
        theta: -0.04,
        vega: 0.1,
        spreadPct: 9,
        moneyness: 'otm',
        liquidityScore: 74,
        warnings: [],
      },
      {
        contractSymbol: `${symbol}260619P00045000`,
        side: 'put',
        strike: 45,
        bid: 1.45,
        ask: 1.75,
        mid: 1.6,
        volume: 155,
        openInterest: 980,
        impliedVolatility: 0.62,
        delta: -0.2,
        gamma: 0.02,
        theta: -0.03,
        vega: 0.07,
        spreadPct: 18.8,
        moneyness: 'otm',
        liquidityScore: 51,
        warnings: ['low_oi_watch'],
      },
    ],
    filtersApplied: {
      minOpenInterest: 100,
      maxSpreadPct: 20,
    },
    chainAsOf: FIXTURE_UNDERLYING.asOf,
    source: 'fixture',
    limitations: ['provider_validation_required', 'mocked_frontend_shell'],
    metadata: FIXTURE_METADATA,
  };
}

function fixtureDecision(symbol: string): OptionsDecisionResponse {
  return {
    symbol,
    strategy: 'bull_call_spread',
    dataQuality: {
      dataQualityScore: 25,
      dataQualityTier: 'synthetic_demo_only',
      sourceType: 'synthetic',
      asOfAgeMinutes: null,
      blockingReasons: ['synthetic_or_fixture_data_not_decision_grade'],
      warnings: [],
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
      dteBucket: 'standard',
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
      expectedMovePct: 14.3,
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
          breakevenPressure: 0.08,
          maxLoss: 230,
          maxGain: 270,
          riskRewardRatio: 1.17,
          expectedMoveAlignment: 90,
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
          breakevenPressure: 10.1,
          maxLoss: 270,
          maxGain: null,
          riskRewardRatio: null,
          expectedMoveAlignment: 80,
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
        breakevenPressure: 0.08,
        maxLoss: 230,
        maxGain: 270,
        riskRewardRatio: 1.17,
        expectedMoveAlignment: 90,
        ivReadiness: 82,
        tradeQualityScore: 35,
        decisionLabel: '数据不足，禁止判断',
        primaryReasons: ['当前为 synthetic delayed / 演示数据'],
        riskWarnings: ['不可用于真实交易判断'],
      },
    ],
    breakeven: {
      breakeven: 52.3,
      requiredMovePct: -0.08,
      targetPriceStatus: 'target_above_breakeven',
      score: 86,
    },
    riskReward: {
      maxLoss: 230,
      maxGain: 270,
      riskRewardRatio: 1.17,
      score: 72,
      warnings: [],
    },
    tradeQualityScore: 35,
    decisionLabel: '数据不足，禁止判断',
    primaryReasons: ['当前为 synthetic delayed / 演示数据'],
    riskWarnings: ['不可用于真实交易判断'],
    betterAlternative: {
      strategyType: 'bull_call_spread',
      reason: '定义风险结构或更低权利金暴露可能降低单合约风险',
      maxLoss: 230,
      riskRewardRatio: 1.17,
    },
    noAdviceDisclosure: 'Analytical output under explicit assumptions only; not personalized financial advice and not an instruction to trade.',
    freshness: {
      source: 'synthetic_options_lab_fixture',
      freshness: 'synthetic_delayed',
      asOf: FIXTURE_UNDERLYING.asOf,
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
      forceRefreshIgnored: true,
    },
  };
}

function normalizeSymbol(symbol: string): string {
  return symbol.trim().toUpperCase() || 'TEM';
}

async function getOrFixture<T>(path: string, fixture: T): Promise<T> {
  try {
    const response = await apiClient.get<Record<string, unknown>>(path);
    return toCamelCase<T>(response.data);
  } catch (error) {
    if (typeof error === 'object' && error !== null && 'response' in error) {
      throw error;
    }
    return fixture;
  }
}

export const optionsLabApi = {
  getUnderlyingSummary(symbol: string): Promise<OptionsUnderlyingSummaryResponse> {
    const normalized = normalizeSymbol(symbol);
    return getOrFixture(`/api/v1/options/underlyings/${encodeURIComponent(normalized)}/summary`, fixtureSummary(normalized));
  },
  getExpirations(symbol: string): Promise<OptionsExpirationsResponse> {
    const normalized = normalizeSymbol(symbol);
    return getOrFixture(`/api/v1/options/underlyings/${encodeURIComponent(normalized)}/expirations`, fixtureExpirations(normalized));
  },
  getOptionChain(symbol: string, expiration: string): Promise<OptionsChainResponse> {
    const normalized = normalizeSymbol(symbol);
    const query = new URLSearchParams({ expiration, side: 'both' });
    return getOrFixture(`/api/v1/options/underlyings/${encodeURIComponent(normalized)}/chain?${query.toString()}`, fixtureChain(normalized, expiration));
  },
  compareStrategies(request: OptionsStrategyCompareRequest): Promise<OptionsStrategyCompareResponse> {
    const normalized = normalizeSymbol(request.symbol);
    const payload: OptionsStrategyCompareRequest = {
      ...request,
      symbol: normalized,
      strategies: request.strategies?.length
        ? request.strategies
        : ['long_call', 'long_put', 'bull_call_spread', 'bear_put_spread'],
    };
    return apiClient.post<Record<string, unknown>>('/api/v1/options/strategies/compare', payload)
      .then((response) => toCamelCase<OptionsStrategyCompareResponse>(response.data));
  },
  evaluateDecision(request: OptionsDecisionRequest): Promise<OptionsDecisionResponse> {
    const normalized = normalizeSymbol(request.symbol);
    const payload: OptionsDecisionRequest = {
      ...request,
      symbol: normalized,
    };
    return apiClient.post<Record<string, unknown>>('/api/v1/options/decision/evaluate', payload)
      .then((response) => toCamelCase<OptionsDecisionResponse>(response.data))
      .catch((error) => {
        if (typeof error === 'object' && error !== null && 'response' in error) {
          throw error;
        }
        return fixtureDecision(normalized);
      });
  },
};
