import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
  },
}));

describe('scannerApi investor signal normalization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('converts consumer_diagnostics investor_signal into typed camelCase fields', async () => {
    const { scannerApi } = await import('../scanner');
    get.mockResolvedValueOnce({
      data: {
        id: 42,
        market: 'us',
        profile: 'preopen',
        status: 'completed',
        universe_name: 'US Pre-open',
        shortlist_size: 1,
        universe_size: 20,
        preselected_size: 8,
        evaluated_size: 5,
        universe_notes: [],
        scoring_notes: [],
        universe_type: 'default',
        requested_symbols_count: 0,
        accepted_symbols_count: 0,
        rejected_symbols: [],
        diagnostics: {},
        notification: {
          attempted: false,
          status: 'skipped',
          channels: [],
        },
        comparison_to_previous: {
          available: false,
          new_count: 0,
          retained_count: 0,
          dropped_count: 0,
          new_symbols: [],
          retained_symbols: [],
          dropped_symbols: [],
        },
        review_summary: {
          available: false,
          review_window_days: 5,
          review_status: 'pending',
          candidate_count: 1,
          reviewed_count: 0,
          pending_count: 1,
          strong_count: 0,
          mixed_count: 0,
          weak_count: 0,
        },
        shortlist: [
          {
            symbol: 'NVDA',
            name: 'NVIDIA',
            rank: 1,
            score: 92,
            reasons: [],
            key_metrics: [],
            feature_signals: [],
            risk_notes: [],
            watch_context: [],
            boards: [],
            appeared_in_recent_runs: 1,
            ai_interpretation: {
              available: false,
              status: 'unavailable',
            },
            realized_outcome: {
              review_status: 'pending',
              outcome_label: 'Pending',
              thesis_match: 'unknown',
              review_window_days: 5,
            },
            diagnostics: {},
            consumer_diagnostics: {
              status: 'limited',
              score_grade_allowed: false,
              score_confidence: 0.4,
              cap_reason: 'fallback_source',
              source_class: 'fallback',
              investor_signal: {
                contract_version: 'investor_signal_contract_v1',
                diagnostic_only: true,
                observation_only: true,
                authority_grant: false,
                decision_grade: false,
                source_authority_allowed: false,
                score_contribution_allowed: false,
                market_regime: 'risk_off',
                market_regime_label: '防御偏好升温',
                capital_flow_regime: 'outflow',
                capital_flow_label: '资金净流出观察',
                theme_flow_state: 'fading',
                theme_flow_label: '热度回落观察',
                confidence_label: 'blocked',
                confidence_text: '禁止判断',
                freshness: 'fallback',
                reason_codes: ['fallback_source', 'source_authority_missing'],
                contradiction_codes: [],
              },
            },
          },
        ],
      },
    });

    const payload = await scannerApi.getRun(42);
    const investorSignal = payload.shortlist[0].consumerDiagnostics?.investorSignal;

    expect(payload.shortlist[0].consumerDiagnostics?.scoreGradeAllowed).toBe(false);
    expect(payload.shortlist[0].consumerDiagnostics?.scoreConfidence).toBe(0.4);
    expect(payload.shortlist[0].consumerDiagnostics?.capReason).toBe('fallback_source');
    expect(payload.shortlist[0].consumerDiagnostics?.sourceClass).toBe('fallback');
    expect(investorSignal?.contractVersion).toBe('investor_signal_contract_v1');
    expect(investorSignal?.marketRegime).toBe('risk_off');
    expect(investorSignal?.capitalFlowRegime).toBe('outflow');
    expect(investorSignal?.themeFlowState).toBe('fading');
    expect(investorSignal?.confidenceLabel).toBe('blocked');
    expect(investorSignal?.reasonCodes).toEqual(['fallback_source', 'source_authority_missing']);
  });
});
