import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
  },
}));

describe('researchRadarApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads and normalizes the research radar queue', async () => {
    const { researchRadarApi } = await import('../researchRadar');

    get.mockResolvedValueOnce({
      data: {
        schema_version: 'research_radar_api_v1',
        generated_at: '2026-06-15T09:30:00Z',
        research_queue: [
          {
            symbol: 'ALFA',
            ticker: 'ALFA',
            priority: 'medium',
            research_bias: 'strengthContinuation',
            driver_scores: { relative_strength: 70 },
            why_on_radar: ['Relative strength is above threshold.'],
            what_to_verify: ['Verify follow-through.'],
            invalidation_observations: ['Relative strength fades.'],
            risk_flags: [],
            evidence_quality: { status: 'partial', score: 54 },
          },
        ],
        aggregate_summary: {
          queue_quality: 'mixed',
          priority_counts: { medium: 1 },
          source: { scanner_run_id: 8, market: 'us' },
        },
        evidence_gaps: [],
        market_context_fit: 'neutral',
        no_advice_disclosure: 'Research-only queue.',
        data_quality: { status: 'partial', missing_evidence: [] },
      },
    });

    const payload = await researchRadarApi.getResearchRadar({ market: 'us', profile: 'us_preopen_v1', limit: 5 });

    expect(get).toHaveBeenCalledWith('/api/v1/research/radar', {
      params: { market: 'us', profile: 'us_preopen_v1', limit: 5 },
    });
    expect(payload.schemaVersion).toBe('research_radar_api_v1');
    expect(payload.researchQueue[0]?.driverScores?.relativeStrength).toBe(70);
    expect(payload.aggregateSummary.priorityCounts?.medium).toBe(1);
    expect(payload.aggregateSummary.source?.scannerRunId).toBe(8);
    expect(payload.marketContextFit).toBe('neutral');
  });

  it('loads and normalizes the unified research queue hub', async () => {
    const { researchRadarApi } = await import('../researchRadar');

    get.mockResolvedValueOnce({
      data: {
        schema_version: 'research_queue_v1',
        research_queue: [
          {
            queue_item_id: 'watchlist-MSFT-item-1',
            source_surface: 'watchlist',
            symbol: 'MSFT',
            title: 'Watchlist evidence follow-up',
            priority_tier: 'urgent_review',
            why_queued: ['Missing evidence needs review.'],
            evidence_used: ['Technicals available'],
            evidence_gaps: ['Price-history evidence'],
            freshness: { state: 'needs_review', last_reviewed_at: null },
            suggested_research_path: [
              {
                label: 'Stock Structure',
                route: '/stocks/MSFT/structure-decision',
                section: 'watchlistResearchOverlay',
                reason: 'Open symbol structure detail.',
              },
            ],
            observation_only: true,
          },
        ],
        aggregate_summary: {
          item_count: 1,
          limit: 4,
          bounded: true,
          by_source_surface: { watchlist: 1 },
          by_priority_tier: { urgent_review: 1, follow_up: 0, monitor: 0 },
        },
        source_surfaces_aggregated: ['watchlist'],
        evidence_gaps: ['Price-history evidence'],
        data_quality: {
          state: 'ready',
          item_count: 1,
          source_surfaces_available: ['watchlist'],
          source_surfaces_expected: ['scanner', 'watchlist', 'market', 'manual_gap'],
          fail_closed: true,
        },
        no_advice_disclosure: 'Research-only queue.',
        observation_only: true,
        decision_grade: false,
      },
    });

    const payload = await researchRadarApi.getResearchQueue({ market: 'us', queueLimit: 4, scannerLimit: 7 });

    expect(get).toHaveBeenCalledWith('/api/v1/research/queue', {
      params: { market: 'us', scanner_limit: 7, queue_limit: 4 },
    });
    expect(payload.schemaVersion).toBe('research_queue_v1');
    expect(payload.researchQueue[0]?.sourceSurface).toBe('watchlist');
    expect(payload.researchQueue[0]?.freshness.state).toBe('needs_review');
    expect(payload.aggregateSummary.bySourceSurface?.watchlist).toBe(1);
    expect(payload.aggregateSummary.byPriorityTier?.urgent_review).toBe(1);
    expect(payload.sourceSurfacesAggregated).toEqual(['watchlist']);
    expect(payload.observationOnly).toBe(true);
    expect(payload.decisionGrade).toBe(false);
  });

  it('rejects unified research queue responses with a missing or unexpected schema', async () => {
    const { researchRadarApi } = await import('../researchRadar');

    get.mockResolvedValueOnce({
      data: {
        research_queue: [],
        aggregate_summary: { item_count: 0, limit: 10, bounded: false },
        data_quality: { state: 'ready', item_count: 0, fail_closed: true },
        no_advice_disclosure: 'Research-only queue.',
        observation_only: true,
        decision_grade: false,
      },
    });
    await expect(researchRadarApi.getResearchQueue()).rejects.toThrow(/research queue schema/i);

    get.mockResolvedValueOnce({
      data: {
        schema_version: 'debug_queue_v0',
        research_queue: [],
        aggregate_summary: { item_count: 0, limit: 10, bounded: false },
        data_quality: { state: 'ready', item_count: 0, fail_closed: true },
        no_advice_disclosure: 'Research-only queue.',
        observation_only: true,
        decision_grade: false,
      },
    });
    await expect(researchRadarApi.getResearchQueue()).rejects.toThrow(/research queue schema/i);
  });

  it('rejects unified research queue responses that are not fail-closed observation-only payloads', async () => {
    const { researchRadarApi } = await import('../researchRadar');

    get.mockResolvedValueOnce({
      data: {
        schema_version: 'research_queue_v1',
        research_queue: [],
        aggregate_summary: { item_count: 0, limit: 10, bounded: false },
        data_quality: { state: 'ready', item_count: 0, fail_closed: false },
        no_advice_disclosure: 'Research-only queue.',
        observation_only: false,
        decision_grade: true,
      },
    });

    await expect(researchRadarApi.getResearchQueue()).rejects.toThrow(/research queue boundary/i);
  });
});
