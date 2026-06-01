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
});
