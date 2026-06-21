import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get, post } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
    post,
  },
}));

describe('quantApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('reads DuckDB health and coverage from existing admin endpoints', async () => {
    const { quantApi } = await import('../quant');
    get
      .mockResolvedValueOnce({ data: { enabled: false, database_path: 'wolfystock.duckdb', schema_initialized: false, status: 'disabled' } })
      .mockResolvedValueOnce({ data: { status: 'disabled', total_ohlcv_rows: 0, total_factor_rows: 0, symbol_count: 0, symbols: [] } });

    const health = await quantApi.getDuckDBHealth();
    const coverage = await quantApi.getDuckDBCoverage();

    expect(get).toHaveBeenNthCalledWith(1, '/api/v1/quant/duckdb/health');
    expect(get).toHaveBeenNthCalledWith(2, '/api/v1/quant/duckdb/coverage');
    expect(health.schemaInitialized).toBe(false);
    expect(coverage.totalOhlcvRows).toBe(0);
  });

  it('posts bounded diagnostic actions without adding new backend routes', async () => {
    const { quantApi } = await import('../quant');
    post.mockResolvedValue({ data: { status: 'ok', data_mode: 'empty', diagnostics: { production_runtime_changed: false } } });

    await quantApi.runDuckDBBenchmark({ symbolLimit: 2 });
    await quantApi.getDuckDBFactorSnapshot({ symbols: ['AAPL'], lookbackDays: 5, factors: ['return_1d'] });
    await quantApi.validateDuckDBFactorPath({ symbols: ['AAPL'], minFactorRows: 1 });
    await quantApi.compareDuckDBRuntimeContext({ symbols: ['AAPL'], scannerSnapshot: { AAPL: { score: 0 } } });

    expect(post).toHaveBeenNthCalledWith(1, '/api/v1/quant/duckdb/benchmark', { symbolLimit: 2 });
    expect(post).toHaveBeenNthCalledWith(2, '/api/v1/quant/duckdb/factor-snapshot', {
      symbols: ['AAPL'],
      lookbackDays: 5,
      factors: ['return_1d'],
    });
    expect(post).toHaveBeenNthCalledWith(3, '/api/v1/quant/duckdb/validate-factor-path', {
      symbols: ['AAPL'],
      minFactorRows: 1,
    });
    expect(post).toHaveBeenNthCalledWith(4, '/api/v1/quant/duckdb/compare-runtime-context', {
      symbols: ['AAPL'],
      scannerSnapshot: { AAPL: { score: 0 } },
    });
  });

  it('keeps init and factor build as explicit POST actions', async () => {
    const { quantApi } = await import('../quant');
    post.mockResolvedValue({ data: { status: 'ok', schema_initialized: true, factor_rows: 2 } });

    await quantApi.initDuckDB();
    await quantApi.buildDuckDBFactors({ symbols: ['AAPL', 'MSFT'] });

    expect(post).toHaveBeenNthCalledWith(1, '/api/v1/quant/duckdb/init', {});
    expect(post).toHaveBeenNthCalledWith(2, '/api/v1/quant/duckdb/build-factors', {
      symbols: ['AAPL', 'MSFT'],
    });
  });

  it('posts factor research reports without injecting fallback data', async () => {
    const { quantApi } = await import('../quant');
    post.mockResolvedValue({
      data: {
        status: 'partial',
        boundary: {
          purpose: 'diagnostic factor report',
          research_only: true,
          diagnostic_only: true,
          supplied_observations_only: true,
        },
        factor_metadata: [],
        input_shape: {
          observation_count: 1,
          metric_observation_count: 1,
          forward_return_observation_count: 1,
          factor_count: 1,
          factor_ids: ['momentum.momentum_21d'],
          symbol_count: 1,
          symbols: ['AAPL'],
          as_of_count: 1,
          forward_return_horizons: ['1d'],
          portfolio_weight_count: 0,
          long_weight_count: 0,
          short_weight_count: 0,
          neutralization_axes: [],
          min_group_size: 2,
          market_cap_bucket_count: 5,
          hash_algorithm: 'sha256',
          input_content_hash: 'abc123',
        },
        report: {
          window: {
            as_of_count: 1,
            observation_count: 1,
          },
          factor_coverage: [],
          metrics_summary: [],
          neutralization_summary: [],
          exposure_summary: [],
          missing_data_reasons: [],
          warnings: [],
        },
        missing_data_reasons: [],
        warnings: [],
      },
    });

    const payload = {
      observations: [{ factorId: 'momentum.momentum_21d' }],
      metricObservations: [{ factorId: 'momentum.momentum_21d' }],
      neutralizationAxes: ['sector'],
    };

    const result = await quantApi.buildFactorResearchReport(payload);

    expect(post).toHaveBeenCalledWith('/api/v1/quant/factor-research/report', payload);
    expect(result.inputShape.inputContentHash).toBe('abc123');
    expect(result.boundary.researchOnly).toBe(true);
  });
});
