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
      'research packet',
      'evidence packet',
      'scanner handoff',
      'evidence families',
      'Some symbol evidence is present, but the packet is not complete enough for a clean research handoff.',
      'Missing or incomplete evidence families: quote, fundamental, news.',
      'Add fundamental coverage before business-quality review.',
      'OBSERVATION-ONLY',
      'No verified local peer group metadata for this symbol.',
      'Add verified local peer group metadata before interpreting peer movement.',
      'Load recent local daily OHLCV before opening this page.',
      'historical ohlcv',
      'quote snapshot',
      'universe',
      'provider error',
      'debug',
      'dry-run',
      'pipeline',
      'Observation-only research readiness; not personalized financial advice',
      'Observe whether downside volume pressure fades or remains persistent',
      'No portfolio exposure available',
      'evidence limited',
      '数据不足，暂不形成结论。数据不足，暂不形成结论。数据不足，暂不形成结论。',
    ] as const;

    for (const example of examples) {
      expect(findConsumerRawLeakage(example), example).not.toEqual([]);
    }
  });

  it('supports explicitly checking zh guest-gate english fallback phrases without making them globally forbidden', () => {
    const sample = 'Sign-in required Go to sign in Return home';
    const hits = findConsumerRawLeakage(sample, {
      extraForbiddenPatterns: [
        /\bSign-in required\b/i,
        /\bGo to sign in\b/i,
        /\bReturn home\b/i,
      ],
    });

    expect(hits.map((hit) => hit.match)).toEqual([
      'Sign-in required',
      'Go to sign in',
      'Return home',
    ]);
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
