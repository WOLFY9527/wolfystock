import apiClient from './index';
import { toCamelCase } from './utils';

export type OptionsDirection = 'bullish' | 'bearish' | 'neutral' | 'volatility';
export type OptionsRiskProfile = 'conservative' | 'balanced' | 'aggressive';
export type OptionsFreshness = 'live' | 'delayed' | 'cached' | 'stale' | 'fallback' | 'mock' | 'error';
export type OptionSide = 'call' | 'put';
export type OptionMoneyness = 'itm' | 'atm' | 'otm';

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
};
