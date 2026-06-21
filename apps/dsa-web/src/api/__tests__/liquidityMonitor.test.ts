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
    const { buildOfficialRiskBundleReadinessView, liquidityMonitorApi } = await import('../liquidityMonitor');
    get.mockResolvedValueOnce({
      data: {
        endpoint: '/api/v1/market/liquidity-monitor',
        generated_at: '2026-05-07T10:00:00+08:00',
        score: {
          value: 69,
          regime: 'supportive',
          confidence: 0.44,
          included_indicator_count: 3,
          possible_indicator_weight: 49,
          included_indicator_weight: 19,
        },
        coverage_contract: {
          contract_version: 'liquidity_coverage_contract_v1',
          label: 'Liquidity coverage contract',
          summary: 'Coverage is measured as fulfilled required input slots.',
          denominator_kind: 'required_inputs',
          denominator_label: 'Required liquidity input slots',
          required_family_count: 12,
          required_input_count: 39,
          fulfilled_input_count: 7,
          missing_input_count: 32,
          score_eligible_input_count: 7,
          observation_only_input_count: 0,
          score_weight_budget: 49,
          score_weight_included: 19,
          families: [
            {
              indicator_id: 'vix_pressure',
              label: 'VIX / 波动率压力',
              required_inputs: ['VIX'],
              fulfilled_inputs: ['VIX'],
              missing_inputs: [],
              required_input_count: 1,
              fulfilled_input_count: 1,
              missing_input_count: 0,
              score_eligible_input_count: 1,
              observation_only_input_count: 0,
              contributes_to_score: true,
              score_contribution_allowed: true,
              observation_only: false,
              proxy_only: false,
            },
          ],
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
            evidence: {
              contract_version: 'source_confidence_contract_v1',
              source: 'mixed',
              source_label: 'Official macro mix',
              as_of: '2026-05-07T10:00:00+08:00',
              freshness: 'partial',
              is_fallback: true,
              is_stale: false,
              is_partial: true,
              is_unavailable: false,
              coverage: 0.66,
              confidence_weight: 0.45,
              inputs: [
                {
                  key: 'VIX',
                  label: 'VIX',
                  source: 'fred',
                  source_label: 'FRED VIXCLS',
                  source_type: 'official_public',
                  source_tier: 'official_public',
                  trust_level: 'reliable',
                  as_of: '2026-05-07T10:00:00+08:00',
                  freshness: 'cached',
                  is_fallback: false,
                  is_stale: false,
                  is_partial: false,
                  is_unavailable: false,
                  observation_only: false,
                  source_authority_allowed: true,
                  score_contribution_allowed: true,
                  source_authority_reason: null,
                  source_authority_route_rejected: false,
                  route_rejected_reason_codes: [],
                  official_series_id: 'VIXCLS',
                  official_observation_date: '2026-05-06',
                  official_as_of: '2026-05-06',
                  confidence_weight: 1,
                },
                {
                  key: 'CREDIT',
                  label: 'Credit spreads',
                  source: 'fred',
                  source_label: 'FRED BAMLH0A0HYM2',
                  source_type: 'official_public',
                  source_tier: 'official_public',
                  trust_level: 'reliable',
                  as_of: '2026-05-07T10:00:00+08:00',
                  freshness: 'cached',
                  is_fallback: false,
                  is_stale: false,
                  is_partial: false,
                  is_unavailable: false,
                  observation_only: true,
                  source_authority_allowed: true,
                  score_contribution_allowed: false,
                  source_authority_reason: null,
                  source_authority_route_rejected: false,
                  route_rejected_reason_codes: [],
                  official_series_id: 'BAMLH0A0HYM2',
                  official_observation_date: '2026-05-06',
                  official_as_of: '2026-05-06',
                  confidence_weight: 0.35,
                },
              ],
            },
            coverage_diagnostics: {
              indicator_id: 'vix_pressure',
              indicator_name: 'VIX / 波动率压力',
              required_inputs: ['VIX'],
              fulfilled_inputs: ['VIX'],
              missing_inputs: [],
              required_input_count: 1,
              fulfilled_input_count: 1,
              missing_input_count: 0,
              score_eligible_input_count: 1,
              observation_only_input_count: 0,
              required_provider_class: 'official_public.vix_or_volatility',
              configured_provider_available: true,
              real_source_available: true,
              proxy_only: false,
              observation_only: false,
              score_contribution_allowed: true,
              score_exclusion_reason: null,
              required_real_source_for_score: true,
              proxy_observation_only_reason: null,
              missing_provider_reason: null,
              paid_data_likely_required: false,
              source_tier: 'official_public',
              freshness: 'live',
              trust_level: 'reliable',
              contributes_to_score: true,
              score_contribution: 8,
              cap_reason: null,
              degradation_reason: null,
              source_authority_route_rejected: false,
              source_authority_reason: null,
              route_rejected_reason_codes: [],
            },
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
              source_tier: 'official_public',
              trust_level: 'reliable',
              freshness: 'delayed',
              observation_only: false,
              score_contribution_allowed: true,
              included_in_score: true,
              proxy_only: false,
              discount_reasons: ['stale', ''],
              degradation_reason: 'delayed_source',
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
        capital_flow_signal: {
          contract_version: 'investor_signal_contract_v1',
          diagnostic_only: true,
          observation_only: true,
          authority_grant: false,
          decision_grade: false,
          source_authority_allowed: false,
          score_contribution_allowed: false,
          market_regime: 'risk_on',
          market_regime_label: '风险偏好回升',
          capital_flow_regime: 'inflow',
          capital_flow_label: '资金净流入观察',
          theme_flow_state: 'leading',
          theme_flow_label: '主线领涨观察',
          confidence_label: 'medium',
          confidence_text: '中',
          confidence: 'medium',
          freshness: 'partial',
          is_fallback: false,
          is_stale: false,
          is_partial: true,
          reason_codes: ['source_authority_missing', 'score_rights_missing', 'partial_source'],
          contradiction_codes: ['capital_flow_signal_mismatch'],
          likely_destination: 'growth_ai_software_semis',
          source_asset_pressure: [
            { asset: 'growth_ai_software_semis', pressure: 'absorbing', freshness: 'delayed', is_partial: true },
            { asset: 'btc', pressure: 'lagging', freshness: 'live', is_partial: false },
          ],
          contradiction_signals: ['btc_not_confirming_growth_absorption'],
          explanation: 'Growth is absorbing more attention while BTC is not confirming the move.',
        },
        official_risk_bundle_readiness: {
          contract_version: 'official_risk_bundle_readiness_v1',
          status: 'partial',
          score_authority: 'observation_only',
          score_authority_eligible: false,
          observation_only: true,
          source_authority_state: 'partial',
          as_of: '2026-05-07T10:00:00+08:00',
          freshness: 'cached',
          required_families: ['vix', 'rates', 'fedLiquidity'],
          available_families: ['vix'],
          partial_families: ['rates'],
          missing_required_families: ['fedLiquidity'],
          stale_families: [],
          blocked_families: [],
          required_series: ['VIXCLS', 'DGS2', 'DGS10', 'DGS30', 'WALCL'],
          missing_required_series: ['WALCL'],
          next_evidence_required: ['fedLiquidity_missing_official_series'],
          families: [
            {
              family_id: 'vix',
              label: 'VIX volatility proxy',
              required: true,
              status: 'available',
              source_type: 'official_public',
              source_authority_allowed: true,
              score_authority_eligible: true,
              observation_only: false,
              freshness: 'cached',
              as_of: '2026-05-07T10:00:00+08:00',
              freshness_window: 'official_daily_us_weekday_t_plus_1',
              required_series: ['VIXCLS'],
              fulfilled_series: ['VIXCLS'],
              missing_series: [],
              stale_series: [],
              blocked_series: [],
              next_evidence_required: [],
            },
            {
              family_id: 'fedLiquidity',
              label: 'Fed liquidity',
              required: true,
              status: 'missing',
              source_type: 'official_public',
              source_authority_allowed: false,
              score_authority_eligible: false,
              observation_only: true,
              freshness: 'unavailable',
              as_of: null,
              freshness_window: 'official_weekly_fed_liquidity_t_plus_7',
              required_series: ['WALCL'],
              fulfilled_series: [],
              missing_series: ['WALCL'],
              stale_series: [],
              blocked_series: [],
              next_evidence_required: ['fedLiquidity_missing_official_series'],
            },
          ],
        },
      },
    });

    const payload = await liquidityMonitorApi.getLiquidityMonitor();

    expect(get).toHaveBeenCalledWith('/api/v1/market/liquidity-monitor');
    expect(payload.score.regime).toBe('supportive');
    expect(payload.score.possibleIndicatorWeight).toBe(49);
    expect(payload.coverageContract).toMatchObject({
      denominatorKind: 'required_inputs',
      requiredFamilyCount: 12,
      requiredInputCount: 39,
      scoreWeightBudget: 49,
    });
    expect(payload.freshness.weakestIndicatorFreshness).toBe('delayed');
    expect(payload.indicators[0].includedInScore).toBe(true);
    expect(payload.indicators[0].evidence?.inputs[0]).toMatchObject({
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      officialSeriesId: 'VIXCLS',
      officialObservationDate: '2026-05-06',
      officialAsOf: '2026-05-06',
    });
    expect(payload.indicators[0].evidence?.inputs[1]).toMatchObject({
      observationOnly: true,
      scoreContributionAllowed: false,
      officialSeriesId: 'BAMLH0A0HYM2',
    });
    expect(payload.indicators[0].coverageDiagnostics).toMatchObject({
      requiredProviderClass: 'official_public.vix_or_volatility',
      requiredInputCount: 1,
      scoreEligibleInputCount: 1,
      realSourceAvailable: true,
      scoreContributionAllowed: true,
      routeRejectedReasonCodes: [],
    });
    expect(payload.liquidityImpulseSynthesis?.liquidityImpulse).toBe('contracting_liquidity');
    expect(payload.liquidityImpulseSynthesis?.dominantDrivers[0].source).toBe('treasury');
    expect(payload.liquidityImpulseSynthesis?.dominantDrivers[0]).toMatchObject({
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      freshness: 'delayed',
      observationOnly: false,
      scoreContributionAllowed: true,
      includedInScore: true,
      proxyOnly: false,
      discountReasons: ['stale'],
      degradationReason: 'delayed_source',
    });
    expect(payload.liquidityImpulseSynthesis?.counterEvidence[0].reason).toBe('conflicts_with_primary_regime');
    expect(payload.liquidityImpulseSynthesis?.counterEvidence[0].scoreContributionAllowed).toBeUndefined();
    expect(payload.capitalFlowSignal?.contractVersion).toBe('investor_signal_contract_v1');
    expect(payload.capitalFlowSignal?.freshness).toBe('partial');
    expect(payload.capitalFlowSignal?.confidence).toBe('medium');
    expect(payload.capitalFlowSignal?.reasonCodes).toEqual([
      'source_authority_missing',
      'score_rights_missing',
      'partial_source',
    ]);
    expect(payload.capitalFlowSignal?.sourceAssetPressure[0]).toEqual({
      asset: 'growth_ai_software_semis',
      pressure: 'absorbing',
      freshness: 'delayed',
      isFallback: false,
      isStale: false,
      isPartial: true,
    });
    expect(payload.capitalFlowSignal?.contradictionSignals).toEqual(['btc_not_confirming_growth_absorption']);
    expect(payload.sourceMetadata.externalProviderCalls).toBe(false);
    expect(payload.officialRiskBundleReadiness).toMatchObject({
      status: 'partial',
      scoreAuthority: 'observation_only',
      requiredFamilies: ['vix', 'rates', 'fedLiquidity'],
      missingRequiredSeries: ['WALCL'],
    });
    expect(payload.officialRiskBundleReadiness?.families[0]).toMatchObject({
      familyId: 'vix',
      requiredSeries: ['VIXCLS'],
      fulfilledSeries: ['VIXCLS'],
    });
    expect(payload.officialRiskBundleReadiness).not.toHaveProperty('sourceAuthorityState');
    expect(payload.officialRiskBundleReadiness).not.toHaveProperty('scoreAuthorityEligible');
    expect(payload.officialRiskBundleReadiness?.families[0]).not.toHaveProperty('sourceType');
    expect(payload.officialRiskBundleReadiness?.families[0]).not.toHaveProperty('sourceAuthorityAllowed');
    expect(buildOfficialRiskBundleReadinessView(payload.officialRiskBundleReadiness)).toMatchObject({
      bundleLabel: '官方风险包部分待补',
      bundleVariant: 'info',
      summary: expect.stringContaining('待补序列 1 项'),
    });
  });

  it('preserves evidence boundary metadata for fallback, stale, synthetic, and unavailable inputs', async () => {
    const { liquidityMonitorApi } = await import('../liquidityMonitor');
    get.mockResolvedValueOnce({
      data: {
        endpoint: '/api/v1/market/liquidity-monitor',
        generated_at: '2026-05-21T16:00:00+08:00',
        score: {
          value: 51,
          regime: 'unavailable',
          confidence: 0.12,
          included_indicator_count: 0,
          possible_indicator_weight: 49,
          included_indicator_weight: 0,
        },
        freshness: {
          status: 'mock',
          weakest_indicator_freshness: 'unavailable',
          latest_as_of: '2026-05-21T16:00:00+08:00',
        },
        indicators: [
          {
            key: 'us_breadth_proxy',
            label: 'US Breadth Proxy',
            status: 'partial',
            freshness: 'stale',
            included_in_score: false,
            score_contribution: 0,
            score_weight: 0,
            summary: 'Synthetic breadth fixture kept only for boundary validation.',
            updated_at: '2026-05-21T16:00:00+08:00',
            evidence: {
              contract_version: 'source_confidence_contract_v1',
              source: 'synthetic_fixture',
              source_label: 'Synthetic boundary fixture',
              as_of: '2026-05-21T16:00:00+08:00',
              freshness: 'mock',
              is_fallback: true,
              is_stale: true,
              is_partial: true,
              is_unavailable: false,
              coverage: 0.4,
              confidence_weight: 0.15,
              degradation_reason: 'synthetic_or_fixture_data_not_decision_grade',
              cap_reason: 'partial_coverage',
              inputs: [
                {
                  key: 'SECTORS_UP',
                  label: 'Sectors Up',
                  source: 'synthetic_fixture',
                  source_label: 'Synthetic breadth fixture',
                  source_type: 'synthetic_fixture',
                  source_tier: 'synthetic_fixture',
                  trust_level: 'synthetic',
                  as_of: '2026-05-21T16:00:00+08:00',
                  freshness: 'mock',
                  is_fallback: true,
                  is_stale: true,
                  is_partial: true,
                  is_unavailable: false,
                  observation_only: true,
                  source_authority_allowed: false,
                  score_contribution_allowed: false,
                  source_authority_reason: 'synthetic_or_fixture_data_not_decision_grade',
                  source_authority_route_rejected: false,
                  route_rejected_reason_codes: ['synthetic_or_fixture_data_not_decision_grade'],
                  confidence_weight: 0.15,
                },
                {
                  key: 'RSP_SPY',
                  label: 'RSP/SPY',
                  source: 'unavailable',
                  source_label: 'Breadth pair unavailable',
                  source_type: 'official_public',
                  source_tier: 'official_public',
                  trust_level: 'unavailable',
                  as_of: '2026-05-21T16:00:00+08:00',
                  freshness: 'unavailable',
                  is_fallback: false,
                  is_stale: false,
                  is_partial: false,
                  is_unavailable: true,
                  observation_only: true,
                  source_authority_allowed: false,
                  score_contribution_allowed: false,
                  source_authority_reason: 'provider_unavailable',
                  source_authority_route_rejected: true,
                  route_rejected_reason_codes: ['provider_unavailable'],
                  official_series_id: 'RSP_SPY',
                  official_observation_date: null,
                  official_as_of: null,
                  confidence_weight: 0,
                },
              ],
            },
          },
        ],
        advisory_disclosure: '仅用于观察市场流动性环境，非买卖建议，不触发扫描、回测或组合动作。',
        source_metadata: {
          external_provider_calls: false,
          provider_runtime_changed: false,
          market_cache_mutation: false,
        },
      },
    });

    const payload = await liquidityMonitorApi.getLiquidityMonitor();

    expect(payload.freshness).toMatchObject({
      status: 'mock',
      weakestIndicatorFreshness: 'unavailable',
      latestAsOf: '2026-05-21T16:00:00+08:00',
    });
    expect(payload.indicators[0]).toMatchObject({
      key: 'us_breadth_proxy',
      freshness: 'stale',
      includedInScore: false,
    });
    expect(payload.indicators[0].evidence).toMatchObject({
      source: 'synthetic_fixture',
      sourceLabel: 'Synthetic boundary fixture',
      asOf: '2026-05-21T16:00:00+08:00',
      freshness: 'mock',
      isFallback: true,
      isStale: true,
      isPartial: true,
      isUnavailable: false,
      degradationReason: 'synthetic_or_fixture_data_not_decision_grade',
      capReason: 'partial_coverage',
    });
    expect(payload.indicators[0].evidence?.inputs[0]).toMatchObject({
      source: 'synthetic_fixture',
      sourceType: 'synthetic_fixture',
      sourceTier: 'synthetic_fixture',
      asOf: '2026-05-21T16:00:00+08:00',
      freshness: 'mock',
      isFallback: true,
      isStale: true,
      isPartial: true,
      isUnavailable: false,
      sourceAuthorityAllowed: false,
      scoreContributionAllowed: false,
      routeRejectedReasonCodes: ['synthetic_or_fixture_data_not_decision_grade'],
    });
    expect(payload.indicators[0].evidence?.inputs[1]).toMatchObject({
      source: 'unavailable',
      asOf: '2026-05-21T16:00:00+08:00',
      freshness: 'unavailable',
      isFallback: false,
      isStale: false,
      isPartial: false,
      isUnavailable: true,
      sourceAuthorityAllowed: false,
      scoreContributionAllowed: false,
      sourceAuthorityRouteRejected: true,
      routeRejectedReasonCodes: ['provider_unavailable'],
      officialSeriesId: 'RSP_SPY',
      officialObservationDate: null,
      officialAsOf: null,
    });
    expect(payload.officialRiskBundleReadiness).toBeUndefined();
  });
});
