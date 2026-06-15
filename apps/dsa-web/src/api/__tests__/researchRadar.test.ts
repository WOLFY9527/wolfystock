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
});
