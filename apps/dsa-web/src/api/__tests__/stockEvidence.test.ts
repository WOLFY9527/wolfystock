import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
  },
}));

describe('stockEvidenceApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads stock evidence and preserves only consumer-safe fundamentalsSummary fields', async () => {
    const { stockEvidenceApi } = await import('../stockEvidence');

    get.mockResolvedValueOnce({
      data: {
        symbols: ['AAPL'],
        items: [
          {
            symbol: 'AAPL',
            market: 'US',
            product_read_model: {
              contract_version: 'product_read_model_v1',
              surface: 'Stock Evidence',
              state: 'stale',
              ready: false,
              freshness: {
                state: 'stale',
                as_of: '2026-06-01',
              },
              provenance: {
                source_class: 'stock_evidence',
                as_of: '2026-06-01',
                freshness: 'stale',
                quality: 'partial',
              },
              evidence: {
                blockers: ['news'],
              },
              raw_provider_payload: { redacted_id: 'must-not-emit-prm' },
            },
            stock_evidence_packet: {
              schema_version: 'stock_evidence_packet_v1',
              not_investment_advice: true,
              observation_only: true,
              fundamentals_summary: {
                market_cap: 2800000000000,
                pe_ttm: 28.5,
                pb: 36.2,
                beta: 1.1,
                revenue_ttm: 390000000000,
                net_income_ttm: 97000000000,
                fcf_ttm: 90000000000,
                gross_margin: 0.44,
                operating_margin: 0.31,
                roe: 1.01,
                roa: 0.58,
                period: 'mixed',
                source: 'analysis_history',
                freshness: 'unknown',
                missing_fields: [],
                not_investment_advice: true,
                observation_only: true,
                score_contribution_allowed: false,
                source_authority_allowed: false,
                raw_provider_payload: { redacted_id: 'must-not-emit' },
                admin_diagnostics: { provider_route: 'must-not-emit' },
                provider_route: 'must-not-emit',
                valuation_opinion: 'must-not-emit',
                buy_advice: 'must-not-emit',
                sell_advice: 'must-not-emit',
                undervalued_advice: 'must-not-emit',
                overvalued_advice: 'must-not-emit',
                status: 'available',
              },
            },
            symbol_evidence_readiness: {
              symbol_evidence_readiness: true,
              symbol: 'AAPL',
              readiness_tier: 'partial',
              evidence_used: ['quote', 'fundamental', ''],
              evidence_missing: ['technical', 'news'],
              stale_inputs: ['quote'],
              conflicting_evidence: ['technical_vs_news'],
              data_quality_notes: ['Core evidence is incomplete; keep the research context bounded.'],
              suggested_research_path: ['Add recent OHLC or technical context.'],
              observation_only: true,
              no_advice_disclosure: '仅供研究观察，不构成个性化行动指令。',
              raw_provider_payload: { redacted_id: 'must-not-emit-readiness' },
              admin_diagnostics: { provider_route: 'must-not-emit-readiness' },
              source_ref_id: 'must-not-emit-readiness',
            },
          },
        ],
        meta: {
          generated_at: '2026-06-02T00:00:00Z',
          source: 'read_only_evidence_v2',
        },
      },
    });

    const payload = await stockEvidenceApi.getStockEvidence('BRK/B');
    const packet = payload.items[0].stockEvidencePacket;
    const summary = packet?.fundamentalsSummary;
    const readiness = payload.items[0].symbolEvidenceReadiness;

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/BRK%2FB/evidence');
    expect(payload.symbols).toEqual(['AAPL']);
    expect(payload.meta).toEqual({
      generatedAt: '2026-06-02T00:00:00Z',
      source: 'read_only_evidence_v2',
    });
    expect(packet?.schemaVersion).toBe('stock_evidence_packet_v1');
    expect(packet?.notInvestmentAdvice).toBe(true);
    expect(packet?.observationOnly).toBe(true);
    expect(payload.items[0].productReadModel).toMatchObject({
      contractVersion: 'product_read_model_v1',
      surface: 'Stock Evidence',
      state: 'stale',
      ready: false,
      freshness: {
        state: 'stale',
        asOf: '2026-06-01',
      },
      provenance: {
        sourceClass: 'stock_evidence',
        asOf: '2026-06-01',
        freshness: 'stale',
        quality: 'partial',
      },
      evidence: {
        blockers: ['news'],
      },
    });
    expect(JSON.stringify(payload.items[0].productReadModel)).not.toMatch(/rawProviderPayload|must-not-emit-prm/i);
    expect(summary).toEqual({
      marketCap: 2800000000000,
      peTtm: 28.5,
      pb: 36.2,
      beta: 1.1,
      revenueTtm: 390000000000,
      netIncomeTtm: 97000000000,
      fcfTtm: 90000000000,
      grossMargin: 0.44,
      operatingMargin: 0.31,
      roe: 1.01,
      roa: 0.58,
      period: 'mixed',
      source: 'analysis_history',
      freshness: 'unknown',
      missingFields: [],
      notInvestmentAdvice: true,
      observationOnly: true,
      scoreContributionAllowed: false,
      sourceAuthorityAllowed: false,
    });
    expect(readiness).toEqual({
      symbolEvidenceReadiness: true,
      symbol: 'AAPL',
      readinessTier: 'partial',
      evidenceUsed: ['quote', 'fundamental'],
      evidenceMissing: ['technical', 'news'],
      staleInputs: ['quote'],
      conflictingEvidence: ['technical_vs_news'],
      dataQualityNotes: ['Core evidence is incomplete; keep the research context bounded.'],
      suggestedResearchPath: ['Add recent OHLC or technical context.'],
      observationOnly: true,
      noAdviceDisclosure: '仅供研究观察，不构成个性化行动指令。',
    });

    const serialized = JSON.stringify(summary);
    for (const forbiddenKey of [
      'rawProviderPayload',
      'adminDiagnostics',
      'providerRoute',
      'valuationOpinion',
      'buyAdvice',
      'sellAdvice',
      'undervaluedAdvice',
      'overvaluedAdvice',
      'must-not-emit',
      'status',
    ]) {
      expect(summary).not.toHaveProperty(forbiddenKey);
      expect(serialized).not.toContain(forbiddenKey);
      expect(serialized).not.toContain('must-not-emit');
    }

    const serializedReadiness = JSON.stringify(readiness);
    for (const forbiddenKey of [
      'rawProviderPayload',
      'adminDiagnostics',
      'sourceRefId',
      'must-not-emit-readiness',
    ]) {
      expect(readiness).not.toHaveProperty(forbiddenKey);
      expect(serializedReadiness).not.toContain(forbiddenKey);
      expect(serializedReadiness).not.toContain('must-not-emit-readiness');
    }
  });

  it('preserves stock evidence item metadata blocks as opaque records', async () => {
    const { normalizeStockEvidenceResponse } = await import('../stockEvidence');

    const payload = normalizeStockEvidenceResponse({
      symbols: ['AAPL', 'MSFT'],
      items: [
        {
          symbol: 'AAPL',
          market: 'US',
          quote: {
            source: 'read_only_quote_diagnostic',
            freshness: 'unavailable',
            as_of: '2026-06-02T00:00:00Z',
            is_fallback: false,
            is_stale: true,
            is_partial: true,
            is_synthetic: false,
            is_unavailable: true,
            source_confidence: {
              source_label: 'read-only evidence',
              confidence_weight: 0,
              degradation_reason: 'read_only_fetch_disabled',
            },
          },
          technical: {
            source: 'technical_snapshot',
            freshness: 'stale',
            is_fallback: true,
            is_stale: true,
            is_partial: false,
            is_synthetic: false,
            is_unavailable: false,
            source_confidence: {
              source_label: 'technical snapshot',
              confidence_weight: 0.4,
            },
          },
          fundamental: {
            source: 'fundamentals_digest',
            freshness: 'partial',
            is_fallback: false,
            is_stale: false,
            is_partial: true,
            is_synthetic: false,
            is_unavailable: false,
            source_confidence: {
              source_label: 'fundamentals digest',
              coverage: 'partial',
            },
          },
          news: {
            source: 'news_digest',
            freshness: 'fresh',
            is_fallback: false,
            is_stale: false,
            is_partial: false,
            is_synthetic: false,
            is_unavailable: false,
            source_confidence: {
              source_label: 'news digest',
              confidence_weight: 0.7,
            },
          },
          sec_filing_evidence: {
            source: 'sec_filing_snapshot',
            freshness: 'recent',
            is_fallback: false,
            is_stale: false,
            is_partial: false,
            is_synthetic: true,
            is_unavailable: false,
            source_confidence: {
              source_label: 'SEC filing snapshot',
              cap_reason: 'opaque_transport_only',
            },
          },
        },
        {
          symbol: 'MSFT',
          quote: null,
          technical: ['invalid'],
        },
      ],
    });

    const item = payload.items[0];

    expect(item.quote).toEqual({
      source: 'read_only_quote_diagnostic',
      freshness: 'unavailable',
      asOf: '2026-06-02T00:00:00Z',
      isFallback: false,
      isStale: true,
      isPartial: true,
      isSynthetic: false,
      isUnavailable: true,
      sourceConfidence: {
        sourceLabel: 'read-only evidence',
        confidenceWeight: 0,
        degradationReason: 'read_only_fetch_disabled',
      },
    });
    expect(item.technical).toEqual({
      source: 'technical_snapshot',
      freshness: 'stale',
      isFallback: true,
      isStale: true,
      isPartial: false,
      isSynthetic: false,
      isUnavailable: false,
      sourceConfidence: {
        sourceLabel: 'technical snapshot',
        confidenceWeight: 0.4,
      },
    });
    expect(item.fundamental).toEqual({
      source: 'fundamentals_digest',
      freshness: 'partial',
      isFallback: false,
      isStale: false,
      isPartial: true,
      isSynthetic: false,
      isUnavailable: false,
      sourceConfidence: {
        sourceLabel: 'fundamentals digest',
        coverage: 'partial',
      },
    });
    expect(item.news).toEqual({
      source: 'news_digest',
      freshness: 'fresh',
      isFallback: false,
      isStale: false,
      isPartial: false,
      isSynthetic: false,
      isUnavailable: false,
      sourceConfidence: {
        sourceLabel: 'news digest',
        confidenceWeight: 0.7,
      },
    });
    expect(item.secFilingEvidence).toEqual({
      source: 'sec_filing_snapshot',
      freshness: 'recent',
      isFallback: false,
      isStale: false,
      isPartial: false,
      isSynthetic: true,
      isUnavailable: false,
      sourceConfidence: {
        sourceLabel: 'SEC filing snapshot',
        capReason: 'opaque_transport_only',
      },
    });
    expect(payload.items[1].quote).toBeNull();
    expect(payload.items[1].technical).toBeUndefined();
    expect(payload.items[1].fundamental).toBeUndefined();
    expect(payload.items[1].news).toBeUndefined();
    expect(payload.items[1].secFilingEvidence).toBeUndefined();
  });

  it('keeps fundamentalsSummary absent when the packet does not include it', async () => {
    const { stockEvidenceApi } = await import('../stockEvidence');

    get.mockResolvedValueOnce({
      data: {
        symbols: ['AAPL'],
        items: [
          {
            symbol: 'AAPL',
            stock_evidence_packet: {
              schema_version: 'stock_evidence_packet_v1',
              not_investment_advice: true,
            },
          },
        ],
        meta: {
          generated_at: '2026-06-02T00:00:00Z',
          source: 'read_only_evidence_v2',
        },
      },
    });

    const payload = await stockEvidenceApi.getStockEvidence('AAPL');
    const packet = payload.items[0].stockEvidencePacket;

    expect(packet?.schemaVersion).toBe('stock_evidence_packet_v1');
    expect(packet).not.toHaveProperty('fundamentalsSummary');
  });

  it('normalizes peerCorrelationSnapshot as a consumer-safe stock evidence packet field', async () => {
    const { normalizeStockEvidenceResponse } = await import('../stockEvidence');

    const payload = normalizeStockEvidenceResponse({
      symbols: ['ORCL'],
      items: [
        {
          symbol: 'ORCL',
          stock_evidence_packet: {
            schema_version: 'stock_evidence_packet_v1',
            peer_correlation_snapshot: {
              symbol: 'ORCL',
              peer_group: {
                status: 'available',
                label: 'Cloud software',
                symbols: ['MSFT', 'NVDA', ''],
                raw_provider_payload: 'must-not-emit-peer-group',
              },
              correlation_state: 'diverging',
              peer_evidence: [
                {
                  symbol: 'MSFT',
                  correlation: 0.42,
                  overlap_days: 22,
                  symbol_return_pct: -2.4,
                  peer_return_pct: 4.8,
                  spread_pct: -7.2,
                  state: 'diverging',
                  summary: 'MSFT moved away from ORCL across the comparison window.',
                  raw_provider_payload: 'must-not-emit-peer',
                  reason_code: 'must-not-emit-peer',
                },
              ],
              divergence_evidence: [
                {
                  symbol: 'MSFT',
                  overlap_days: 22,
                  state: 'diverging',
                  summary: 'MSFT diverged while ORCL weakened.',
                  trace_id: 'must-not-emit-divergence',
                },
              ],
              stale_inputs: ['MSFT comparison window is stale.'],
              missing_inputs: ['NVDA peer history is unavailable.'],
              confidence_cap: 'medium',
              observation_boundary: 'Observation-only peer movement context; no personalized action instruction.',
              research_next_steps: ['Compare updated peer closes before extending the structure read.'],
              provider_trace: 'must-not-emit-snapshot',
            },
          },
        },
      ],
    });

    const snapshot = payload.items[0].stockEvidencePacket?.peerCorrelationSnapshot;

    expect(snapshot).toEqual({
      symbol: 'ORCL',
      peerGroup: {
        status: 'available',
        label: 'Cloud software',
        symbols: ['MSFT', 'NVDA'],
      },
      correlationState: 'diverging',
      peerEvidence: [
        {
          symbol: 'MSFT',
          correlation: 0.42,
          overlapDays: 22,
          symbolReturnPct: -2.4,
          peerReturnPct: 4.8,
          spreadPct: -7.2,
          state: 'diverging',
          summary: 'MSFT moved away from ORCL across the comparison window.',
        },
      ],
      divergenceEvidence: [
        {
          symbol: 'MSFT',
          overlapDays: 22,
          state: 'diverging',
          summary: 'MSFT diverged while ORCL weakened.',
        },
      ],
      staleInputs: ['MSFT comparison window is stale.'],
      missingInputs: ['NVDA peer history is unavailable.'],
      confidenceCap: 'medium',
      observationBoundary: 'Observation-only peer movement context; no personalized action instruction.',
      researchNextSteps: ['Compare updated peer closes before extending the structure read.'],
    });
    expect(JSON.stringify(snapshot)).not.toMatch(/provider|raw|debug|trace|reason_code|reasonCode|must-not-emit/i);
  });

  it('drops invalid fundamentalsSummary payloads instead of fabricating a safe object', async () => {
    const { normalizeStockEvidenceResponse } = await import('../stockEvidence');

    const payload = normalizeStockEvidenceResponse({
      symbols: ['AAPL'],
      items: [
        {
          symbol: 'AAPL',
          stockEvidencePacket: {
            schemaVersion: 'stock_evidence_packet_v1',
            fundamentalsSummary: 'invalid-summary',
          },
          symbolEvidenceReadiness: {
            symbolEvidenceReadiness: true,
            symbol: 'AAPL',
            readinessTier: 'ranked',
            observationOnly: true,
            noAdviceDisclosure: 'invalid readiness tier should not be projected',
          },
        },
      ],
    });

    expect(payload.items[0].stockEvidencePacket?.schemaVersion).toBe('stock_evidence_packet_v1');
    expect(payload.items[0].stockEvidencePacket).not.toHaveProperty('fundamentalsSummary');
    expect(payload.items[0]).not.toHaveProperty('symbolEvidenceReadiness');
  });
});
