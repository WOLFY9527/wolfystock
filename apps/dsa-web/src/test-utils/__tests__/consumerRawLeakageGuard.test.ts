import { describe, expect, it } from 'vitest';
import { findConsumerRawLeakage } from '../consumerRawLeakageGuard';

describe('consumer raw leakage guard', () => {
  it('detects the raw internal examples called out by the consumer guard contract', () => {
    const examples = [
      'score_contribution_not_allowed',
      'providerRuntime',
      'sourceAuthorityAllowed',
      'scoreContributionAllowed',
      'routeRejected',
      'fallback_used',
      'reason_codes',
      '/api/v1/market/rotation-radar',
    ] as const;

    for (const example of examples) {
      expect(findConsumerRawLeakage(example), example).not.toEqual([]);
    }
  });

  it('does not flag ordinary market labels or symbols', () => {
    const text = [
      'AAPL',
      'NVDA',
      'BRK.B',
      'ORCL',
      'ETF',
      'Market Overview',
      'Portfolio',
      'Liquidity Monitor',
      'Rotation Radar',
      'Scanner',
      'Watchlist',
      'Home',
      'Guest',
      'WolfyStock',
      'US 10Y',
      'S&P 500',
    ].join('\n');

    expect(findConsumerRawLeakage(text)).toEqual([]);
  });
});
