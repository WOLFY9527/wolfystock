import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
  },
}));

describe('dailyIntelligenceApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads and normalizes the daily intelligence briefing payload', async () => {
    const { dailyIntelligenceApi } = await import('../dailyIntelligence');

    get.mockResolvedValueOnce({
      data: {
        schema_version: 'daily_intelligence_briefing_v1',
        generated_at: '2026-06-15T09:30:00Z',
        briefing_date: '2026-06-15',
        session_label: 'pre-market',
        market_regime_summary: {
          regime: 'riskOn',
          confidence: 'medium',
          summary: 'Breadth and liquidity remain constructive.',
          supporting_observations: ['Breadth participation held.'],
          invalidation_observations: ['Breadth narrows materially.'],
        },
        what_changed: ['Queue focus rotated toward relative-strength names.'],
        section_links: [
          {
            label: 'Research Radar',
            route: '/research/radar',
            section: 'topResearchPriorities',
            reason: 'research_queue_origin',
          },
        ],
        top_research_priorities: [
          {
            label: 'ALFA research queue',
            source: 'research_radar',
            priority: 'high',
            ticker: 'ALFA',
            observations: ['Relative strength improved.'],
            what_to_verify: ['Confirm follow-through.'],
            evidence_gaps: ['themeBreadth'],
            evidence_links: [
              {
                label: 'Research Radar',
                route: '/research/radar',
                section: 'topResearchPriorities',
                reason: 'research_queue_origin',
              },
              {
                label: 'Stock Structure',
                route: '/stocks/ALFA/structure-decision',
                section: 'topResearchPriorities',
                reason: 'symbol_structure_detail',
              },
            ],
          },
        ],
        scanner_highlights: [
          {
            ticker: 'ALFA',
            priority: 'high',
            observations: ['Relative strength improved.'],
            what_to_verify: ['Confirm follow-through.'],
            evidence_gaps: ['themeBreadth'],
            risk_flags: ['evidence_partial'],
          },
        ],
        watchlist_highlights: [
          {
            ticker: 'NVDA',
            structure_state: 'structure_changed',
            research_priority: 'medium',
            why_watching: 'Structure changed and needs observation.',
            what_to_verify: ['Verify local OHLCV coverage.'],
            evidence_gaps: ['local_ohlcv_evidence'],
            risk_flags: ['cached_or_stale_evidence'],
          },
        ],
        portfolio_structure_highlights: [
          {
            ticker: 'AAPL',
            structure_state: 'mixed',
            confidence: 'medium',
            watch_next: ['Verify support persists.'],
            risk_flags: ['concentrated_exposure'],
            missing_evidence: ['cached_portfolio_holdings'],
          },
        ],
        scenario_risks: [
          {
            label: 'Scenario risk section unavailable',
            source: 'degraded_state',
            observations: ['Stored scenario read model is unavailable.'],
            evidence_gaps: ['scenario_risk_read_model_unavailable'],
          },
        ],
        evidence_gaps: ['scenario_risk_read_model_unavailable'],
        degraded_inputs: [
          {
            section: 'scenarioRisks',
            status: 'unavailable',
            reason: 'scenario_risk_read_model_unavailable',
          },
        ],
        observation_only: true,
        decision_grade: false,
      },
    });

    const payload = await dailyIntelligenceApi.getDailyIntelligence();

    expect(get).toHaveBeenCalledWith('/api/v1/market/daily-intelligence');
    expect(payload.schemaVersion).toBe('daily_intelligence_briefing_v1');
    expect(payload.marketRegimeSummary.supportingObservations).toEqual(['Breadth participation held.']);
    expect(payload.sectionLinks[0]).toEqual({
      label: 'Research Radar',
      route: '/research/radar',
      section: 'topResearchPriorities',
      reason: 'research_queue_origin',
    });
    expect(payload.topResearchPriorities[0]?.ticker).toBe('ALFA');
    expect(payload.topResearchPriorities[0]?.evidenceLinks).toEqual([
      {
        label: 'Research Radar',
        route: '/research/radar',
        section: 'topResearchPriorities',
        reason: 'research_queue_origin',
      },
      {
        label: 'Stock Structure',
        route: '/stocks/ALFA/structure-decision',
        section: 'topResearchPriorities',
        reason: 'symbol_structure_detail',
      },
    ]);
    expect(payload.watchlistHighlights[0]?.structureState).toBe('structure_changed');
    expect(payload.portfolioStructureHighlights[0]?.watchNext).toEqual(['Verify support persists.']);
    expect(payload.degradedInputs[0]).toEqual({
      section: 'scenarioRisks',
      status: 'unavailable',
      reason: 'scenario_risk_read_model_unavailable',
    });
    expect(payload.observationOnly).toBe(true);
    expect(payload.decisionGrade).toBe(false);
  });
});
