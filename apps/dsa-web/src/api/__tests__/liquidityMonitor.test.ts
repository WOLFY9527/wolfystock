import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
  },
}));

describe('liquidityMonitorApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('normalizes the advisory liquidity monitor response from the backend route', async () => {
    const { liquidityMonitorApi } = await import('../liquidityMonitor');
    get.mockResolvedValueOnce({
      data: {
        endpoint: '/api/v1/market/liquidity-monitor',
        generated_at: '2026-05-07T10:00:00+08:00',
        score: {
          value: 69,
          regime: 'supportive',
          confidence: 0.44,
          included_indicator_count: 3,
          possible_indicator_weight: 43,
          included_indicator_weight: 19,
        },
        freshness: {
          status: 'delayed',
          weakest_indicator_freshness: 'delayed',
          latest_as_of: '2026-05-07T10:00:00+08:00',
        },
        indicators: [
          {
            key: 'vix_pressure',
            label: 'VIX / 波动率压力',
            status: 'live',
            freshness: 'live',
            included_in_score: true,
            score_contribution: 8,
            score_weight: 8,
            summary: '均值 -2.50%',
            updated_at: '2026-05-07T10:00:00+08:00',
          },
        ],
        liquidity_impulse_synthesis: {
          liquidity_impulse: 'contracting_liquidity',
          impulse_label: 'Liquidity appears to be contracting',
          subtype: 'rates_driven_tightening',
          confidence: 0.71,
          confidence_label: 'high',
          pillar_scores: {
            rates_pressure: 0.63,
          },
          direction_score: -0.58,
          dominant_drivers: [
            {
              key: 'liquidity_monitor:us_rates_pressure',
              label: 'US Rates / 利率压力',
              pillar: 'rates_pressure',
              direction: 'supports_contraction',
              signal: 0.63,
              impact: 0.58,
              source: 'treasury',
              score_contribution_allowed: true,
            },
          ],
          counter_evidence: [
            {
              key: 'liquidity_monitor:btc_momentum',
              pillar: 'crypto_liquidity_beta',
              reason: 'conflicts_with_primary_regime',
            },
          ],
          data_gaps: [
            {
              key: 'liquidity_monitor:cn_hk_flows',
              reason: 'score_contribution_not_allowed',
            },
          ],
          narrative_bullets: ['Rates and dollar pressure are dominating the current liquidity signal.'],
          evidence_quality: {
            scoring_pillar_count: 2,
            data_gap_count: 1,
          },
          not_investment_advice: true,
        },
        advisory_disclosure: '仅用于观察市场流动性环境，非买卖建议，不触发扫描、回测或组合动作。',
        source_metadata: {
          external_provider_calls: false,
          provider_runtime_changed: false,
          market_cache_mutation: false,
        },
      },
    });

    const payload = await liquidityMonitorApi.getLiquidityMonitor();

    expect(get).toHaveBeenCalledWith('/api/v1/market/liquidity-monitor');
    expect(payload.score.regime).toBe('supportive');
    expect(payload.freshness.weakestIndicatorFreshness).toBe('delayed');
    expect(payload.indicators[0].includedInScore).toBe(true);
    expect(payload.liquidityImpulseSynthesis?.liquidityImpulse).toBe('contracting_liquidity');
    expect(payload.liquidityImpulseSynthesis?.dominantDrivers[0].source).toBe('treasury');
    expect(payload.liquidityImpulseSynthesis?.counterEvidence[0].reason).toBe('conflicts_with_primary_regime');
    expect(payload.sourceMetadata.externalProviderCalls).toBe(false);
  });
});
