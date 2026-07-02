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
      'synthetic_provider_url',
      'synthetic_cache_key',
      'synthetic_request_id',
      'synthetic_debug_reason',
      'synthetic_score_trace',
      'synthetic_diagnostic_window',
      'synthetic_provider_payload_label',
      'https://provider.example.invalid/options?token=secret',
      'req-synth-123',
      'Traceback stack trace',
      'historical ohlcv',
      'quote snapshot',
      'Observation-only research readiness; not personalized financial advice',
      'Observe whether downside volume pressure fades or remains persistent',
      'No portfolio exposure available',
      'evidence limited',
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
