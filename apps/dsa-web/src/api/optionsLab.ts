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

export type OptionsStrategyCompareResponse = {
  symbol: string;
  underlying: Record<string, unknown>;
  assumptions: Record<string, unknown>;
  strategies: OptionsStrategyComparison[];
  limitations: string[];
  metadata: OptionsStrategyCompareMetadata;
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

function fixtureStrategyComparison(symbol: string, request: OptionsStrategyCompareRequest): OptionsStrategyCompareResponse {
  const targetPrice = request.targetPrice || 65;
  const targetDate = request.targetDate || FIXTURE_EXPIRATION;
  const requestedStrategies = request.strategies?.length
    ? request.strategies
    : ['long_call', 'long_put', 'bull_call_spread', 'bear_put_spread'];
  const allStrategies: OptionsStrategyComparison[] = [
    {
      strategyType: 'long_call',
      legs: [{ action: 'buy', side: 'call', contractSymbol: `${symbol}260619C00055000`, expiration: FIXTURE_EXPIRATION, strike: 55, mid: 4.23, quantity: 1 }],
      netDebit: 423,
      maxLoss: 423,
      maxGain: null,
      breakeven: 59.23,
      requiredMovePct: 13.17,
      payoffAtTarget: 577,
      riskRewardRatio: null,
      liquidityWarnings: [],
      ivThetaNotes: ['iv_and_theta_can_change_strategy_value_before_expiration'],
      suitabilityNotes: ['comparison_uses_user_assumptions_and_fixture_mid_prices', `direction_assumption_${request.direction}`, `risk_profile_${request.riskProfile}`],
      limitations: ['fixture_backed_defined_risk_only'],
      noAdviceDisclosure: 'Analytical comparison under explicit assumptions only; not investment advice or an instruction.',
    },
    {
      strategyType: 'long_put',
      legs: [{ action: 'buy', side: 'put', contractSymbol: `${symbol}260619P00050000`, expiration: FIXTURE_EXPIRATION, strike: 50, mid: 3.35, quantity: 1 }],
      netDebit: 335,
      maxLoss: 335,
      maxGain: null,
      breakeven: 46.65,
      requiredMovePct: -10.87,
      payoffAtTarget: -335,
      riskRewardRatio: null,
      liquidityWarnings: [],
      ivThetaNotes: ['iv_and_theta_can_change_strategy_value_before_expiration'],
      suitabilityNotes: ['comparison_uses_user_assumptions_and_fixture_mid_prices', `direction_assumption_${request.direction}`, `risk_profile_${request.riskProfile}`],
      limitations: ['fixture_backed_defined_risk_only'],
      noAdviceDisclosure: 'Analytical comparison under explicit assumptions only; not investment advice or an instruction.',
    },
    {
      strategyType: 'bull_call_spread',
      legs: [
        { action: 'buy', side: 'call', contractSymbol: `${symbol}260619C00055000`, expiration: FIXTURE_EXPIRATION, strike: 55, mid: 4.23, quantity: 1 },
        { action: 'sell', side: 'call', contractSymbol: `${symbol}260619C00060000`, expiration: FIXTURE_EXPIRATION, strike: 60, mid: 2.28, quantity: 1 },
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
        { action: 'buy', side: 'put', contractSymbol: `${symbol}260619P00050000`, expiration: FIXTURE_EXPIRATION, strike: 50, mid: 3.35, quantity: 1 },
        { action: 'sell', side: 'put', contractSymbol: `${symbol}260619P00045000`, expiration: FIXTURE_EXPIRATION, strike: 45, mid: 1.6, quantity: 1 },
      ],
      netDebit: 175,
      maxLoss: 175,
      maxGain: 325,
      breakeven: 48.25,
      requiredMovePct: -7.82,
      payoffAtTarget: -175,
      riskRewardRatio: 1.86,
      liquidityWarnings: ['thin_liquidity_in_one_or_more_legs'],
      ivThetaNotes: ['iv_and_theta_can_change_strategy_value_before_expiration'],
      suitabilityNotes: ['comparison_uses_user_assumptions_and_fixture_mid_prices', 'defined_risk_debit_spread_caps_loss_and_gain'],
      limitations: ['fixture_backed_defined_risk_only'],
      noAdviceDisclosure: 'Analytical comparison under explicit assumptions only; not investment advice or an instruction.',
    },
  ];

  return {
    symbol,
    underlying: FIXTURE_UNDERLYING as unknown as Record<string, unknown>,
    assumptions: {
      direction: request.direction,
      targetPrice,
      targetDate,
      maxPremium: request.maxPremium,
      riskProfile: request.riskProfile,
      strategies: requestedStrategies,
      contractMultiplier: 100,
      pricingMode: 'expiration_intrinsic_minus_mid_debit',
    },
    strategies: allStrategies.filter((strategy) => requestedStrategies.includes(strategy.strategyType)),
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
      forceRefreshIgnored: Boolean(request.forceRefresh),
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
  } catch {
    return fixture;
  }
}

async function postOrFixture<T>(path: string, body: unknown, fixture: T): Promise<T> {
  try {
    const response = await apiClient.post<Record<string, unknown>>(path, body);
    return toCamelCase<T>(response.data);
  } catch {
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
    return postOrFixture('/api/v1/options/strategies/compare', payload, fixtureStrategyComparison(normalized, payload));
  },
};
