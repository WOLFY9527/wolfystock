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

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/BRK%2FB/evidence');
    expect(payload.symbols).toEqual(['AAPL']);
    expect(payload.meta).toEqual({
      generatedAt: '2026-06-02T00:00:00Z',
      source: 'read_only_evidence_v2',
    });
    expect(packet?.schemaVersion).toBe('stock_evidence_packet_v1');
    expect(packet?.notInvestmentAdvice).toBe(true);
    expect(packet?.observationOnly).toBe(true);
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
        },
      ],
    });

    expect(payload.items[0].stockEvidencePacket?.schemaVersion).toBe('stock_evidence_packet_v1');
    expect(payload.items[0].stockEvidencePacket).not.toHaveProperty('fundamentalsSummary');
  });
});
