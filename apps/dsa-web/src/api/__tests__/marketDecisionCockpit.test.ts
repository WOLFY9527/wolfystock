import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
  },
}));

describe('marketDecisionCockpitApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads and normalizes the market decision cockpit payload', async () => {
    const { marketDecisionCockpitApi } = await import('../marketDecisionCockpit');

    get.mockResolvedValueOnce({
      data: {
        schema_version: 'market_decision_cockpit.v1',
        generated_at: '2026-06-15T00:00:00Z',
        market_regime_decision: {
          regime: 'riskOn',
          confidence: 'medium',
          driver_scores: {
            breadth_participation: {
              score: 62,
              evidence_state: 'partial',
              reasons: ['Breadth still needs confirmation.'],
            },
          },
          explanation: {
            why_this_regime: ['Breadth stabilized.'],
            what_confirms_it: ['Cross-asset pressure eased.'],
            what_invalidates_it: ['Breadth falls back quickly.'],
          },
          invalidation_conditions: ['Breadth falls back quickly.'],
          research_priorities: {
            watch_today: ['Confirm breadth participation.'],
            needs_more_evidence: ['Options data unavailable.'],
            investigate_next: ['Review research queue.'],
          },
        },
        research_queue_preview: {
          top_candidates: [
            {
              ticker: 'ALFA',
              priority: 'high',
              research_bias: 'strengthContinuation',
            },
          ],
          queue_quality: 'mixed',
          evidence_gaps: ['research_candidates_unavailable'],
          preview_only: true,
          degraded_state: {
            status: 'partial',
            reason_codes: ['research_candidates_unavailable'],
          },
        },
        options_structure_status: {
          gamma_evidence_status: 'unavailable',
          observation_only: true,
          decision_grade: false,
          missing_evidence: [{ code: 'missing_contracts' }],
          blocked_reason_codes: ['option_chain_unavailable'],
        },
        cockpit_summary: {
          what_changed: ['Breadth improved.'],
          why_it_matters: ['Queue triage changed.'],
          what_to_watch: ['Watch breadth participation.'],
          confidence_limits: ['Gamma evidence is unavailable.'],
        },
        no_advice_disclosure: 'Research context only.',
        data_quality: {
          status: 'degraded',
          reason_codes: ['option_chain_unavailable'],
        },
      },
    });

    const payload = await marketDecisionCockpitApi.getDecisionCockpit();

    expect(get).toHaveBeenCalledWith('/api/v1/market/decision-cockpit');
    expect(payload.schemaVersion).toBe('market_decision_cockpit.v1');
    expect(payload.marketRegimeDecision.driverScores?.breadthParticipation?.score).toBe(62);
    expect(payload.researchQueuePreview.topCandidates[0]?.researchBias).toBe('strengthContinuation');
    expect(payload.optionsStructureStatus.blockedReasonCodes).toEqual(['option_chain_unavailable']);
    expect(payload.cockpitSummary.whatToWatch).toEqual(['Watch breadth participation.']);
  });
});
