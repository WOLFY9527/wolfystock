import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
  },
}));

describe('watchlistApi investor signal normalization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('converts nested watchlist scanner investor_signal into camelCase fields', async () => {
    const { watchlistApi } = await import('../watchlist');
    get.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 1,
            symbol: 'WULF',
            market: 'us',
            source: 'scanner',
            intelligence: {
              scanner: {
                last_score: 60,
                last_rank: 8,
                status: 'selected',
                reason: 'cache-first diagnostic',
                investor_signal: {
                  contract_version: 'investor_signal_contract_v1',
                  diagnostic_only: true,
                  observation_only: true,
                  authority_grant: false,
                  decision_grade: false,
                  source_authority_allowed: false,
                  score_contribution_allowed: false,
                  market_regime: 'mixed',
                  market_regime_label: '信号分化',
                  capital_flow_regime: 'balanced',
                  capital_flow_label: '资金均衡观察',
                  theme_flow_state: 'mixed',
                  theme_flow_label: '主题分化',
                  confidence_label: 'blocked',
                  confidence_text: '禁止判断',
                  freshness: 'cached',
                  reason_codes: ['source_authority_missing', 'score_rights_missing'],
                  contradiction_codes: [],
                },
              },
            },
          },
        ],
      },
    });

    const payload = await watchlistApi.listWatchlistItems();
    const scanner = payload.items[0].intelligence?.scanner;

    expect(scanner?.lastScore).toBe(60);
    expect(scanner?.lastRank).toBe(8);
    expect(scanner?.investorSignal?.contractVersion).toBe('investor_signal_contract_v1');
    expect(scanner?.investorSignal?.freshness).toBe('cached');
    expect(scanner?.investorSignal?.marketRegime).toBe('mixed');
    expect(scanner?.investorSignal?.capitalFlowRegime).toBe('balanced');
    expect(scanner?.investorSignal?.themeFlowState).toBe('mixed');
    expect(scanner?.investorSignal?.reasonCodes).toEqual(['source_authority_missing', 'score_rights_missing']);
  });

  it('normalizes historical Scanner lineage without coercing cutoff, saved, or run timestamps', async () => {
    const { watchlistApi } = await import('../watchlist');
    const lineage = (overrides: Record<string, unknown> = {}) => ({
      contract_version: 'scanner_watchlist_lineage_v1',
      source: 'scanner',
      scanner_run_id: 84,
      symbol: 'AAPL',
      market: 'us',
      rank_at_scan: 1,
      score_at_scan: 74.3,
      score_snapshot_kind: 'saved_at_add',
      run_profile: 'us_historical_research_v1',
      evaluation_mode: 'historical_development',
      evaluation_cutoff: '2024-12-31',
      historical_research: true,
      run_completed_at: '2026-09-08T10:31:00Z',
      watchlist_added_at: '2026-09-09T09:00:00Z',
      research_reason: 'Historical evidence entered the research queue.',
      research_next_step: 'Review the cutoff-bound evidence.',
      data_state: 'cached',
      freshness_label: 'Historical evidence through cutoff',
      no_advice_boundary: true,
      raw_diagnostics: { provider: 'hidden' },
      ...overrides,
    });
    get.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 1,
            symbol: 'AAPL',
            market: 'us',
            source: 'scanner',
            intelligence: { scanner: { scanner_lineage_v1: lineage() } },
          },
          {
            id: 2,
            symbol: 'MSFT',
            market: 'us',
            source: 'scanner',
            intelligence: { scanner: { scanner_lineage_v1: lineage({ symbol: 'MSFT', evaluation_cutoff: null }) } },
          },
          {
            id: 3,
            symbol: 'NVDA',
            market: 'us',
            source: 'scanner',
            intelligence: { scanner: { scanner_lineage_v1: lineage({ symbol: 'NVDA', evaluation_cutoff: '2024-02-30' }) } },
          },
          {
            id: 4,
            symbol: 'TSLA',
            market: 'us',
            source: 'scanner',
            intelligence: {
              scanner: {
                scanner_lineage_v1: lineage({
                  symbol: 'TSLA',
                  evaluation_mode: 'current',
                  evaluation_cutoff: null,
                  historical_research: false,
                }),
              },
            },
          },
          {
            id: 5,
            symbol: 'META',
            market: 'us',
            source: 'scanner',
            intelligence: {
              scanner: {
                scanner_lineage_v1: lineage({
                  symbol: 'META',
                  evaluation_mode: 'current',
                  historical_research: false,
                }),
              },
            },
          },
        ],
      },
    });

    const payload = await watchlistApi.listWatchlistItems();
    const historical = payload.items[0].intelligence?.scanner?.scannerLineageV1;
    expect(historical).toEqual(expect.objectContaining({
      evaluationMode: 'historical_development',
      evaluationCutoff: '2024-12-31',
      historicalResearch: true,
      runCompletedAt: '2026-09-08T10:31:00Z',
      watchlistAddedAt: '2026-09-09T09:00:00Z',
    }));
    expect(historical).not.toHaveProperty('rawDiagnostics');
    expect(payload.items[1].intelligence?.scanner?.scannerLineageV1?.evaluationCutoff).toBeNull();
    expect(payload.items[1].intelligence?.scanner?.scannerLineageV1?.watchlistAddedAt).toBe('2026-09-09T09:00:00Z');
    expect(payload.items[2].intelligence?.scanner?.scannerLineageV1?.evaluationMode).toBe('historical_development');
    expect(payload.items[2].intelligence?.scanner?.scannerLineageV1?.evaluationCutoff).toBeNull();
    expect(payload.items[3].intelligence?.scanner?.scannerLineageV1).toEqual(expect.objectContaining({
      evaluationMode: 'current',
      evaluationCutoff: null,
      historicalResearch: false,
    }));
    expect(payload.items[4].intelligence?.scanner?.scannerLineageV1).toBeNull();
  });

  it('whitelists catalyst exposures to consumer-safe fields and strips raw/internal payloads', async () => {
    const { watchlistApi } = await import('../watchlist');
    get.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 1,
            symbol: 'NVDA',
            market: 'us',
            source: 'scanner',
            intelligence: {
              catalyst_exposures: [
                {
                  id: 'catalyst:NVDA:us:fundamental',
                  symbol: 'NVDA',
                  market: 'us',
                  category: 'earnings_fundamental_snapshot',
                  title: 'Fundamental snapshot exposure',
                  summary: 'Quarterly revenue and margin snapshot is available.',
                  evidence_status: 'delayed',
                  evidence_labels: ['delayed', 'unverified', 'provider_internal_only'],
                  as_of: '2026-05-17T20:00:00+00:00',
                  published_at: '2026-05-17T13:00:00+00:00',
                  timeframe: '2026Q2',
                  reason_codes: [
                    'observation_only',
                    'delayed_evidence',
                    'not_earnings_calendar',
                    'provider_internal_only',
                  ],
                  observation_only: true,
                  raw_provider_payload: { unsafe: true },
                  admin_diagnostics: { trace: 'hidden' },
                  provider_route: 'polygon.news',
                  source_authority_allowed: false,
                  score_contribution_allowed: false,
                  calendar_claim_allowed: false,
                  authority_grant: false,
                  provider: 'polygon',
                  source: 'news_proxy',
                  raw_category: 'provider_internal_only',
                  raw_reason_codes: ['provider_internal_only'],
                  debug: { enabled: true },
                },
              ],
            },
          },
        ],
      },
    });

    const payload = await watchlistApi.listWatchlistItems();
    const exposure = payload.items[0].intelligence?.catalystExposures?.[0];

    expect(exposure).toEqual({
      id: 'catalyst:NVDA:us:fundamental',
      symbol: 'NVDA',
      market: 'us',
      category: 'earnings_fundamental_snapshot',
      title: 'Fundamental snapshot exposure',
      summary: 'Quarterly revenue and margin snapshot is available.',
      evidenceStatus: 'delayed',
      evidenceLabels: ['delayed', 'unverified'],
      asOf: '2026-05-17T20:00:00+00:00',
      publishedAt: '2026-05-17T13:00:00+00:00',
      timeframe: '2026Q2',
      reasonCodes: ['observation_only', 'delayed_evidence', 'not_earnings_calendar'],
      observationOnly: true,
    });
    expect(exposure).not.toHaveProperty('rawProviderPayload');
    expect(exposure).not.toHaveProperty('adminDiagnostics');
    expect(exposure).not.toHaveProperty('providerRoute');
    expect(exposure).not.toHaveProperty('sourceAuthorityAllowed');
    expect(exposure).not.toHaveProperty('scoreContributionAllowed');
    expect(exposure).not.toHaveProperty('calendarClaimAllowed');
    expect(exposure).not.toHaveProperty('authorityGrant');
    expect(exposure).not.toHaveProperty('provider');
    expect(exposure).not.toHaveProperty('source');
    expect(exposure).not.toHaveProperty('rawCategory');
    expect(exposure).not.toHaveProperty('rawReasonCodes');
    expect(exposure).not.toHaveProperty('debug');
  });

  it('normalizes row research packets while preserving rows without readiness context', async () => {
    const { watchlistApi } = await import('../watchlist');
    get.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 1,
            symbol: 'msft',
            market: 'us',
            source: 'manual',
            row_research_packet: {
              symbol: 'msft',
              market: 'US',
              identity: {
                name: 'Microsoft',
                exchange: 'NASDAQ',
                sector: 'Technology',
                industry: 'Software',
              },
              saved_item_source: 'manual',
              quote: {
                state: 'stale',
                price: '421.35',
                change_percent: '-0.42',
                as_of: '2026-05-01T11:00:00Z',
                provider_runtime_trace: 'hidden',
              },
              scanner_lineage: {
                run_id: null,
                rank: null,
                score: null,
                status: null,
                last_scored_at: null,
                source_authority: 'hidden',
              },
              research_status: 'partial',
              missing_data: ['fundamentals', 'filing_event_catalyst', 'peer_benchmark'],
              next_data_action: 'Add fundamentals, filing/event/catalyst, and peer evidence.',
              observation_only: true,
              no_advice_disclosure: 'Observation-only research packet.',
              raw_provider_payload: { hidden: true },
              debug: { trace: true },
              source_authority: false,
            },
          },
          {
            id: 2,
            symbol: '600519',
            market: 'cn',
            source: 'manual',
          },
        ],
      },
    });

    const payload = await watchlistApi.listWatchlistItems();
    const packet = payload.items[0].rowResearchPacket;

    expect(packet).toEqual({
      symbol: 'MSFT',
      market: 'us',
      identity: {
        name: 'Microsoft',
        exchange: 'NASDAQ',
        sector: 'Technology',
        industry: 'Software',
        canonicalSymbol: 'MSFT',
        displaySymbol: 'MSFT',
        displayName: 'Microsoft',
        identityState: 'unknown',
      },
      savedItemSource: 'manual',
      quote: {
        state: 'stale',
        price: 421.35,
        changePercent: -0.42,
        asOf: '2026-05-01T11:00:00Z',
      },
      provenance: {
        sourceClass: 'unknown',
        provenanceState: 'unknown',
        asOf: null,
        freshnessState: 'unknown',
      },
      scannerLineage: {
        runId: null,
        rank: null,
        score: null,
        status: null,
        lastScoredAt: null,
      },
      researchStatus: 'partial',
      researchReadiness: null,
      missingData: ['fundamentals', 'filing_event_catalyst', 'peer_benchmark'],
      nextDataAction: 'Add fundamentals, filing/event/catalyst, and peer evidence.',
      observationOnly: true,
      noAdviceDisclosure: 'Observation-only research packet.',
    });
    expect(packet).not.toHaveProperty('rawProviderPayload');
    expect(packet).not.toHaveProperty('debug');
    expect(packet).not.toHaveProperty('sourceAuthority');
    expect(packet?.quote).not.toHaveProperty('providerRuntimeTrace');
    expect(packet?.scannerLineage).not.toHaveProperty('sourceAuthority');
    expect(payload.items[1].rowResearchPacket).toBeNull();
  });

  it('fetches the watchlist research overlay and keeps the priority queue consumer-safe', async () => {
    const { watchlistApi } = await import('../watchlist');
    get.mockResolvedValueOnce({
      data: {
        schema_version: 'watchlist_research_overlay_v1',
        overlay_state: 'degraded',
        research_summary: 'Some saved symbols need evidence review.',
        research_priority_queue: [
          {
            symbol: 'MSFT',
            priority_tier: 'attention',
            priority_reason_safe_label: 'Missing evidence needs review.',
            evidence_age: {
              state: 'no_evidence',
              last_reviewed_at: null,
              raw_provider_state: 'provider_timeout',
            },
            missing_evidence: ['Price-history evidence', ''],
            suggested_research_path: [
              {
                label: 'Stock Structure',
                route: '/stocks/MSFT/structure-decision',
                section: 'watchlistResearchOverlay',
                reason: 'Open symbol structure detail.',
                provider_route: 'hidden',
              },
            ],
            observation_only: true,
            raw_provider_payload: { hidden: true },
            provider_route: 'hidden',
            source_authority_allowed: false,
            score_contribution_allowed: false,
            debug: { enabled: true },
          },
          {
            symbol: 'BAD',
            priority_tier: 'urgent_review',
            priority_reason_safe_label: 'Should be dropped.',
            evidence_age: { state: 'ready' },
            observation_only: true,
          },
        ],
        observation_only: true,
        decision_grade: false,
        data_quality: {
          state: 'partial',
          item_count: 2,
        },
      },
    });

    const payload = await watchlistApi.getResearchOverlay();

    expect(get).toHaveBeenCalledWith('/api/v1/watchlist/research-overlay');
    expect(payload.researchPriorityQueue).toEqual([
      {
        symbol: 'MSFT',
        priorityTier: 'attention',
        priorityReasonSafeLabel: 'Missing evidence needs review.',
        evidenceAge: {
          state: 'no_evidence',
          lastReviewedAt: null,
        },
        missingEvidence: ['Price-history evidence'],
        suggestedResearchPath: [
          {
            label: 'Stock Structure',
            route: '/stocks/MSFT/structure-decision',
            section: 'watchlistResearchOverlay',
            reason: 'Open symbol structure detail.',
          },
        ],
        observationOnly: true,
      },
    ]);
    expect(payload.researchPriorityQueue[0]).not.toHaveProperty('rawProviderPayload');
    expect(payload.researchPriorityQueue[0]).not.toHaveProperty('providerRoute');
    expect(payload.researchPriorityQueue[0]).not.toHaveProperty('sourceAuthorityAllowed');
    expect(payload.researchPriorityQueue[0]).not.toHaveProperty('scoreContributionAllowed');
    expect(payload.researchPriorityQueue[0]).not.toHaveProperty('debug');
    expect(payload.researchPriorityQueue[0].evidenceAge).not.toHaveProperty('rawProviderState');
    expect(payload.researchPriorityQueue[0].suggestedResearchPath[0]).not.toHaveProperty('providerRoute');
  });

  it('marks malformed successful overlay payloads unavailable instead of a legitimate empty queue', async () => {
    const { watchlistApi } = await import('../watchlist');
    get.mockResolvedValueOnce({
      data: {
        research_priority_queue: [],
        observation_only: true,
        decision_grade: false,
      },
    });

    const payload = await watchlistApi.getResearchOverlay();

    expect(payload).toEqual({
      schemaVersion: 'watchlist_research_overlay_v1',
      overlayState: 'unavailable',
      researchSummary: 'Watchlist research follow-up is temporarily unavailable.',
      researchPriorityQueue: [],
      observationOnly: true,
      decisionGrade: false,
    });
  });
});
