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
});
