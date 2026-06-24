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
          us: ['ORCL', 'AAPL'],
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
                  state: 'ready',
                  summary: 'Cache preflight is ready.',
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
  });
});
