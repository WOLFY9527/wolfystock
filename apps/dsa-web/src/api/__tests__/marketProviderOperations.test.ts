import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
  },
}));

describe('marketProviderOperationsApi.getHistoricalOhlcvCachePreflight', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses the canonical provider operations admin endpoint', async () => {
    const { marketProviderOperationsApi } = await import('../marketProviderOperations');
    get.mockResolvedValueOnce({
      data: {
        generated_at: '2026-06-29T00:00:00Z',
        window: { key: '24h' },
        summary: { total_items: 0 },
        items: [],
        event_rollups: [],
        cache_states: [],
        limitations: [],
        admin_log_drill_through: { label: 'Admin Logs', route: '/zh/admin/logs', query: {} },
        metadata: { read_only: true, external_provider_calls: false },
      },
    });

    const payload = await marketProviderOperationsApi.getOperations();

    expect(get).toHaveBeenCalledWith('/api/v1/admin/market-providers/operations', {
      params: { window: '24h' },
    });
    expect(get).not.toHaveBeenCalledWith(expect.stringContaining('/api/v1/admin/provider-operations'));
    expect(payload.metadata.readOnly).toBe(true);
    expect(payload.metadata.externalProviderCalls).toBe(false);
  });

  it('loads and normalizes the DATA-113 historical cache preflight response', async () => {
    const { marketProviderOperationsApi } = await import('../marketProviderOperations');
    get.mockResolvedValueOnce({
      data: {
        contract_version: 'historical_ohlcv_cache_preflight_v1',
        mode: 'preflight',
        dry_run: true,
        seed_enabled: false,
        network_calls_enabled: false,
        mutation_enabled: false,
        consumer_safe: true,
        representative_symbols: {
          cn: ['600519'],
          us: ['ORCL', 'AAPL', 'NVDA'],
        },
        activation_checklist: {
          contract_version: 'historical_ohlcv_data_activation_checklist_v1',
          operator_only: true,
          read_only: true,
          no_external_calls: true,
          consumer_visible: false,
          supported_states: [
            'disabled_by_config',
            'dependency_missing',
            'ready_to_seed',
            'seeded/cache_hit',
            'failed_safely',
          ],
          starter_symbol_sets: {
            us: {
              label: 'US first cache activation set',
              symbols: ['ORCL', 'AAPL', 'NVDA'],
              supported: true,
            },
            cn_if_supported: {
              label: 'CN first cache activation set if the local CN runtime is supported',
              symbols: ['600519', '000001', '601398'],
              supported: true,
            },
          },
          workflow_unlocks: ['Stock', 'Scanner', 'Backtest', 'Technical Indicators', 'Market Regime'],
          items: [
            {
              market: 'us',
              label: 'US activation checklist',
              state: 'ready_to_seed',
              runtime_enabled: true,
              dependency_available: true,
              seed_enabled: false,
              required_runtime_flags: [
                'WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED',
                'WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED',
              ],
              seed_flag: 'WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED',
              current_representative_symbols: ['ORCL', 'AAPL'],
              recommended_first_symbols: ['ORCL', 'AAPL', 'NVDA'],
              disabled_reason_codes: ['seed_flag_off_by_default'],
              cache_summary: {
                total_symbols: 2,
                cached_symbol_count: 1,
                ready_symbol_count: 0,
                stale_symbol_count: 1,
                missing_adjustment_count: 1,
                failed_safely_count: 0,
              },
              available_seed_actions: [
                'Review representative dry-run readiness before enabling any mutation.',
                'Run the explicit seed flow in dry-run mode first, then enable the seed flag only after approval.',
                'The seed flag remains default-off until an operator explicitly enables it.',
              ],
              workflow_unlocks: ['Stock', 'Scanner', 'Backtest', 'Technical Indicators', 'Market Regime'],
              current_status_summary: 'US starter symbols are ready for an explicit admin seed review.',
              next_step_summary: 'Use the documented starter symbols first, keep the seed flag explicit, and verify the unlocked product surfaces stay bounded.',
            },
          ],
        },
        markets: {
          cn: {
            market: 'cn',
            runtime_enabled: false,
            dependency_available: true,
            symbols: [
              {
                market: 'cn',
                symbol: '600519',
                runtime_state: 'disabled_by_config',
                cache_state: 'cache_hit',
                dependency_state: 'installed',
                dependency_available: true,
                cached_bars: 72,
                latest_bar_date: '2026-06-23',
                freshness_state: 'fresh',
                adjustment_state: 'available',
                data_state: 'fresh',
                seed_state: 'seed_skipped',
                next_action: {
                  state: 'disabled_by_config',
                  summary: 'Enable runtime before provider fetch is allowed.',
                },
              },
            ],
          },
          us: {
            market: 'us',
            runtime_enabled: true,
            dependency_available: false,
            symbols: [
              {
                market: 'us',
                symbol: 'AAPL',
                runtime_state: 'available',
                cache_state: 'cache_hit',
                dependency_state: 'installed',
                dependency_available: true,
                cached_bars: 44,
                latest_bar_date: '2026-06-20',
                freshness_state: 'stale',
                adjustment_state: 'missing',
                data_state: 'missing_adjustments',
                seed_state: 'seed_skipped',
                next_action: {
                  state: 'seeded/cache_hit',
                  summary: 'Representative cache is already present; validate bars, freshness, and adjustments before widening coverage.',
                },
              },
            ],
          },
        },
      },
    });

    const payload = await marketProviderOperationsApi.getHistoricalOhlcvCachePreflight({
      cnSymbols: ['600519', '000001'],
      usSymbols: 'ORCL,AAPL',
      requiredBars: 30,
      requireAdjusted: false,
    });

    expect(get).toHaveBeenCalledWith('/api/v1/admin/historical-ohlcv/cache-preflight', {
      params: {
        cn_symbols: '600519,000001',
        us_symbols: 'ORCL,AAPL',
        required_bars: 30,
        require_adjusted: false,
      },
    });
    expect(payload.contractVersion).toBe('historical_ohlcv_cache_preflight_v1');
    expect(payload.dryRun).toBe(true);
    expect(payload.seedEnabled).toBe(false);
    expect(payload.networkCallsEnabled).toBe(false);
    expect(payload.mutationEnabled).toBe(false);
    expect(payload.activationChecklist.contractVersion).toBe('historical_ohlcv_data_activation_checklist_v1');
    expect(payload.activationChecklist.operatorOnly).toBe(true);
    expect(payload.activationChecklist.consumerVisible).toBe(false);
    expect(payload.activationChecklist.supportedStates).toEqual([
      'disabled_by_config',
      'dependency_missing',
      'ready_to_seed',
      'seeded/cache_hit',
      'failed_safely',
    ]);
    expect(payload.activationChecklist.starterSymbolSets.us.symbols).toEqual(['ORCL', 'AAPL', 'NVDA']);
    expect(payload.activationChecklist.starterSymbolSets.cnIfSupported.symbols).toEqual(['600519', '000001', '601398']);
    expect(payload.activationChecklist.items[0]).toMatchObject({
      market: 'us',
      state: 'ready_to_seed',
      requiredRuntimeFlags: [
        'WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED',
        'WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED',
      ],
      currentRepresentativeSymbols: ['ORCL', 'AAPL'],
      recommendedFirstSymbols: ['ORCL', 'AAPL', 'NVDA'],
      workflowUnlocks: ['Stock', 'Scanner', 'Backtest', 'Technical Indicators', 'Market Regime'],
    });
    expect(payload.representativeSymbols.cn).toEqual(['600519']);
    expect(payload.markets.cn?.runtimeEnabled).toBe(false);
    expect(payload.markets.cn?.symbols[0]).toMatchObject({
      symbol: '600519',
      cacheState: 'cache_hit',
      cachedBars: 72,
      latestBarDate: '2026-06-23',
      freshnessState: 'fresh',
      adjustmentState: 'available',
      dataState: 'fresh',
    });
    expect(payload.markets.us?.dependencyAvailable).toBe(false);
    expect(payload.markets.us?.symbols[0].dataState).toBe('missing_adjustments');
    expect(payload.markets.us?.symbols[0].nextAction.state).toBe('seeded/cache_hit');
  });
});
