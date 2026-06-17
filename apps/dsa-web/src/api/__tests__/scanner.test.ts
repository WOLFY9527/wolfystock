import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  ScannerCandidateResearchPacket,
  ScannerEvidencePacket,
  ScannerRunDetail,
  ScannerScoreExplainability,
} from '../../types/scanner';

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

  it('preserves score cap explainability metadata while keeping score order stable', async () => {
    const { scannerApi } = await import('../scanner');
    get.mockResolvedValueOnce({
      data: {
        id: 43,
        market: 'cn',
        profile: 'cn_preopen_v1',
        status: 'completed',
        universe_name: 'CN pre-open',
        shortlist_size: 2,
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
        summary: {
          limited_by_result_cap: true,
        },
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
          candidate_count: 2,
          reviewed_count: 0,
          pending_count: 2,
          strong_count: 0,
          mixed_count: 0,
          weak_count: 0,
        },
        shortlist: [
          {
            symbol: '600001',
            name: '股票600001',
            rank: 1,
            score: 40,
            raw_score: 81.6,
            final_score: 40,
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
            diagnostics: {
              score_explainability: {
                raw_score: 81.6,
                final_score: 40,
                score_delta: -41.6,
                score_cap: 40,
                score_confidence: 0.4,
                evidence_coverage: 0.76,
                cap_reason: 'fallback_source',
                degradation_reason: 'fallback_source',
                cap_applied: true,
                missing_evidence: ['history_depth', 'quote_context'],
                reason_codes: ['fallback_source'],
                score_grade_allowed: false,
                source_confidence: {
                  source: 'fallback_snapshot',
                  source_label: 'Fallback snapshot',
                  source_type: 'fallback_static',
                  freshness: 'fallback',
                  is_fallback: true,
                  is_stale: true,
                  is_partial: true,
                  confidence_weight: 0.4,
                  coverage: 0.76,
                  cap_reason: 'fallback_source',
                  degradation_reason: 'fallback_source',
                  source_authority_allowed: false,
                  score_contribution_allowed: false,
                  observation_only: true,
                },
              },
              evidence_packet: {
                symbol: '600001',
                market: 'cn',
                rank: 1,
                score: 40,
                raw_score: 81.6,
                final_score: 40,
                score_confidence: 0.4,
                evidence_coverage: 0.76,
                cap_reason: 'fallback_source',
                degradation_reason: 'fallback_source',
                evidence_version: 'scanner_evidence_v1',
                run_id: 43,
                data_quality_state: 'partial',
                freshness_state: 'fallback',
                freshness_detail: {
                  quote_state: 'fallback',
                  history_state: 'stale',
                  latest_trade_date: '2026-05-08',
                },
                provider_observation: {
                  observation_only: true,
                  score_contribution_allowed: false,
                  entries: [
                    {
                      stage: 'snapshot',
                      provider_name: 'akshare',
                      source_type: 'public_proxy',
                      observation_only: true,
                      score_contribution_allowed: false,
                    },
                  ],
                },
                missing_evidence: ['history_depth', 'quote_context'],
                user_facing_labels: ['仅供观察', '需人工复核'],
                warning_flags: ['仅供观察', '需人工复核'],
              },
            },
            consumer_diagnostics: {
              status: 'limited',
              score_grade_allowed: false,
              score_confidence: 0.4,
              cap_reason: 'fallback_source',
              degradation_reason: 'fallback_source',
              data_quality_state: 'partial',
              freshness_state: 'fallback',
              source_class: 'fallback',
              missing_evidence: ['history_depth', 'quote_context'],
              user_facing_labels: ['仅供观察', '需人工复核'],
              warning_flags: ['仅供观察', '需人工复核'],
            },
          },
          {
            symbol: '600002',
            name: '股票600002',
            rank: 2,
            score: 39,
            raw_score: 39,
            final_score: 39,
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
          },
        ],
      },
    });

    const payload: ScannerRunDetail = await scannerApi.getRun(43);
    const explainability: ScannerScoreExplainability | undefined = payload.shortlist[0].diagnostics.scoreExplainability;
    const evidencePacket: ScannerEvidencePacket | undefined = payload.shortlist[0].diagnostics.evidencePacket;

    expect(payload.shortlist.map((item) => [item.symbol, item.rank, item.score])).toEqual([
      ['600001', 1, 40],
      ['600002', 2, 39],
    ]);
    expect(payload.summary?.limitedByResultCap).toBe(true);
    expect(explainability?.rawScore).toBe(81.6);
    expect(explainability?.finalScore).toBe(40);
    expect(explainability?.scoreDelta).toBe(-41.6);
    expect(explainability?.scoreCap).toBe(40);
    expect(explainability?.scoreConfidence).toBe(0.4);
    expect(explainability?.evidenceCoverage).toBe(0.76);
    expect(explainability?.capApplied).toBe(true);
    expect(explainability?.missingEvidence).toEqual(['history_depth', 'quote_context']);
    expect(explainability?.sourceConfidence?.sourceType).toBe('fallback_static');
    expect(explainability?.sourceConfidence?.isFallback).toBe(true);
    expect(explainability?.sourceConfidence?.isStale).toBe(true);
    expect(explainability?.sourceConfidence?.isPartial).toBe(true);
    expect(explainability?.sourceConfidence?.sourceAuthorityAllowed).toBe(false);
    expect(explainability?.sourceConfidence?.scoreContributionAllowed).toBe(false);
    expect(explainability?.sourceConfidence?.observationOnly).toBe(true);
    expect(evidencePacket?.rawScore).toBe(81.6);
    expect(evidencePacket?.finalScore).toBe(40);
    expect(evidencePacket?.evidenceCoverage).toBe(0.76);
    expect(evidencePacket?.missingEvidence).toEqual(['history_depth', 'quote_context']);
    expect(evidencePacket?.freshnessDetail?.quoteState).toBe('fallback');
    expect(evidencePacket?.freshnessDetail?.historyState).toBe('stale');
    expect(evidencePacket?.providerObservation?.entries?.[0]?.sourceType).toBe('public_proxy');
    expect(payload.shortlist[0].consumerDiagnostics?.degradationReason).toBe('fallback_source');
    expect(payload.shortlist[0].consumerDiagnostics?.dataQualityState).toBe('partial');
    expect(payload.shortlist[0].consumerDiagnostics?.freshnessState).toBe('fallback');
    expect(payload.shortlist[0].consumerDiagnostics?.missingEvidence).toEqual(['history_depth', 'quote_context']);
  });

  it('normalizes candidate research packets with bounded safe fields without changing rank order', async () => {
    const { scannerApi } = await import('../scanner');
    get.mockResolvedValueOnce({
      data: {
        id: 44,
        market: 'us',
        profile: 'us_preopen_v1',
        status: 'completed',
        universe_name: 'US pre-open',
        shortlist_size: 2,
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
          candidate_count: 2,
          reviewed_count: 0,
          pending_count: 2,
          strong_count: 0,
          mixed_count: 0,
          weak_count: 0,
        },
        shortlist: [
          {
            symbol: 'NVDA',
            name: 'NVIDIA',
            rank: 1,
            score: 82,
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
            candidate_research_packet: {
              why_surfaced: 'Trend and liquidity evidence moved this symbol into follow-up review.',
              primary_evidence: [
                'Technicals available',
                'Liquidity available',
                'provider_timeout raw detail',
                'buy now',
              ],
              limiting_evidence: ['Fundamentals pending', 'trace_id=req-raw-1'],
              data_quality_notes: ['data quality: partial', 'debug_ref=scanner:nvda'],
              rejected_or_limited_reason_safe_label: 'Ready for research review',
              research_next_step: 'Refresh fundamentals before follow-up review.',
              observation_only: true,
              reason_codes: ['source_authority_missing'],
              source_refs: ['debug-source'],
              provider_diagnostics: { raw_payload: true },
              debug_ref: 'scanner:nvda:debug',
            },
          },
          {
            symbol: 'MSFT',
            name: 'Microsoft',
            rank: 2,
            score: 79,
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
          },
        ],
      },
    });

    const payload: ScannerRunDetail = await scannerApi.getRun(44);
    const packet: ScannerCandidateResearchPacket | null | undefined = payload.shortlist[0].candidateResearchPacket;

    expect(payload.shortlist.map((item) => [item.symbol, item.rank, item.score])).toEqual([
      ['NVDA', 1, 82],
      ['MSFT', 2, 79],
    ]);
    expect(packet?.whySurfaced).toBe('Trend and liquidity evidence moved this symbol into follow-up review.');
    expect(packet?.primaryEvidence).toEqual(['Technicals available', 'Liquidity available']);
    expect(packet?.limitingEvidence).toEqual(['Fundamentals pending']);
    expect(packet?.dataQualityNotes).toEqual(['data quality: partial']);
    expect(packet?.rejectedOrLimitedReasonSafeLabel).toBe('Ready for research review');
    expect(packet?.researchNextStep).toBe('Refresh fundamentals before follow-up review.');
    expect(packet?.observationOnly).toBe(true);
    expect(payload.shortlist[1].candidateResearchPacket).toBeUndefined();
    expect(JSON.stringify(packet)).not.toMatch(/provider_timeout|reasonCodes|sourceRefs|providerDiagnostics|debugRef|trace_id|buy now|raw_payload/i);
  });
});
