import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../index';
import { backtestApi } from '../backtest';

vi.mock('../index', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe('backtestApi support export contract exposure', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('serializes monte carlo robustness config to backend snake_case request fields', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        id: 91,
        code: 'AAPL',
        strategy_text: 'buy when close > sma(20)',
        parsed_strategy: {
          version: 'rule_v1',
          timeframe: '1d',
          source_text: 'buy when close > sma(20)',
          normalized_text: 'buy when close > sma(20)',
          entry: { type: 'comparison' },
          exit: { type: 'comparison' },
          confidence: 0.91,
          needs_confirmation: false,
          ambiguities: [],
          summary: {},
          max_lookback: 20,
        },
        strategy_hash: 'abc',
        timeframe: '1d',
        lookback_bars: 252,
        initial_capital: 100000,
        fee_bps: 0,
        slippage_bps: 0,
        needs_confirmation: false,
        warnings: [],
        status: 'queued',
        status_history: [],
        trade_count: 0,
        win_count: 0,
        loss_count: 0,
        summary: {},
        execution_assumptions: {},
        benchmark_curve: [],
        benchmark_summary: {},
        daily_return_series: [],
        exposure_curve: [],
        equity_curve: [],
        trades: [],
      },
    } as never);

    await backtestApi.runRuleBacktest({
      code: 'AAPL',
      strategyText: 'buy when close > sma(20)',
      confirmed: true,
      robustnessConfig: {
        monteCarlo: {
          simulationCount: 32,
          seed: 12345,
          noiseScale: 1.25,
        },
      },
    } as never);

    expect(apiClient.post).toHaveBeenCalledWith('/api/v1/backtest/rule/run', {
      code: 'AAPL',
      strategy_text: 'buy when close > sma(20)',
      confirmed: true,
      robustness_config: {
        monte_carlo: {
          simulation_count: 32,
          seed: 12345,
          noise_scale: 1.25,
        },
      },
    });
  });

  it('serializes walk-forward robustness config to backend snake_case request fields', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        id: 93,
        code: 'AAPL',
        strategy_text: 'buy when close > sma(20)',
        parsed_strategy: {
          version: 'rule_v1',
          timeframe: '1d',
          source_text: 'buy when close > sma(20)',
          normalized_text: 'buy when close > sma(20)',
          entry: { type: 'comparison' },
          exit: { type: 'comparison' },
          confidence: 0.91,
          needs_confirmation: false,
          ambiguities: [],
          summary: {},
          max_lookback: 20,
        },
        strategy_hash: 'ghi',
        timeframe: '1d',
        lookback_bars: 252,
        initial_capital: 100000,
        fee_bps: 0,
        slippage_bps: 0,
        needs_confirmation: false,
        warnings: [],
        status: 'queued',
        status_history: [],
        trade_count: 0,
        win_count: 0,
        loss_count: 0,
        summary: {},
        execution_assumptions: {},
        benchmark_curve: [],
        benchmark_summary: {},
        daily_return_series: [],
        exposure_curve: [],
        equity_curve: [],
        trades: [],
      },
    } as never);

    await backtestApi.runRuleBacktest({
      code: 'AAPL',
      strategyText: 'buy when close > sma(20)',
      confirmed: true,
      robustnessConfig: {
        walkForward: {
          trainWindow: 24,
          testWindow: 12,
          step: 12,
          maxWindows: 4,
        },
      },
    } as never);

    expect(apiClient.post).toHaveBeenCalledWith('/api/v1/backtest/rule/run', {
      code: 'AAPL',
      strategy_text: 'buy when close > sma(20)',
      confirmed: true,
      robustness_config: {
        walk_forward: {
          train_window: 24,
          test_window: 12,
          step: 12,
          max_windows: 4,
        },
      },
    });
  });

  it('serializes monte carlo and walk-forward robustness config together when both are enabled', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        id: 94,
        code: 'AAPL',
        strategy_text: 'buy when close > sma(20)',
        parsed_strategy: {
          version: 'rule_v1',
          timeframe: '1d',
          source_text: 'buy when close > sma(20)',
          normalized_text: 'buy when close > sma(20)',
          entry: { type: 'comparison' },
          exit: { type: 'comparison' },
          confidence: 0.91,
          needs_confirmation: false,
          ambiguities: [],
          summary: {},
          max_lookback: 20,
        },
        strategy_hash: 'jkl',
        timeframe: '1d',
        lookback_bars: 252,
        initial_capital: 100000,
        fee_bps: 0,
        slippage_bps: 0,
        needs_confirmation: false,
        warnings: [],
        status: 'queued',
        status_history: [],
        trade_count: 0,
        win_count: 0,
        loss_count: 0,
        summary: {},
        execution_assumptions: {},
        benchmark_curve: [],
        benchmark_summary: {},
        daily_return_series: [],
        exposure_curve: [],
        equity_curve: [],
        trades: [],
      },
    } as never);

    await backtestApi.runRuleBacktest({
      code: 'AAPL',
      strategyText: 'buy when close > sma(20)',
      confirmed: true,
      robustnessConfig: {
        monteCarlo: {
          simulationCount: 16,
        },
        walkForward: {
          trainWindow: 24,
          testWindow: 12,
          step: 12,
          maxWindows: 4,
        },
      },
    } as never);

    expect(apiClient.post).toHaveBeenCalledWith('/api/v1/backtest/rule/run', {
      code: 'AAPL',
      strategy_text: 'buy when close > sma(20)',
      confirmed: true,
      robustness_config: {
        monte_carlo: {
          simulation_count: 16,
        },
        walk_forward: {
          train_window: 24,
          test_window: 12,
          step: 12,
          max_windows: 4,
        },
      },
    });
  });

  it('omits robustness_config when no robustness config is provided', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        id: 92,
        code: 'AAPL',
        strategy_text: 'buy when close > sma(20)',
        parsed_strategy: {
          version: 'rule_v1',
          timeframe: '1d',
          source_text: 'buy when close > sma(20)',
          normalized_text: 'buy when close > sma(20)',
          entry: { type: 'comparison' },
          exit: { type: 'comparison' },
          confidence: 0.91,
          needs_confirmation: false,
          ambiguities: [],
          summary: {},
          max_lookback: 20,
        },
        strategy_hash: 'def',
        timeframe: '1d',
        lookback_bars: 252,
        initial_capital: 100000,
        fee_bps: 0,
        slippage_bps: 0,
        needs_confirmation: false,
        warnings: [],
        status: 'queued',
        status_history: [],
        trade_count: 0,
        win_count: 0,
        loss_count: 0,
        summary: {},
        execution_assumptions: {},
        benchmark_curve: [],
        benchmark_summary: {},
        daily_return_series: [],
        exposure_curve: [],
        equity_curve: [],
        trades: [],
      },
    } as never);

    await backtestApi.runRuleBacktest({
      code: 'AAPL',
      strategyText: 'buy when close > sma(20)',
      confirmed: false,
    });

    expect(apiClient.post).toHaveBeenCalledWith('/api/v1/backtest/rule/run', {
      code: 'AAPL',
      strategy_text: 'buy when close > sma(20)',
      confirmed: false,
    });
  });

  it('serializes bounded parameter sweep request to backend snake_case request fields', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        contract_kind: 'rule_backtest_parameter_sweep_pilot',
        contract_version: 'v1',
        state: 'completed',
        diagnostic_only: true,
        research_only: true,
        not_optimizer: true,
        winner_promotion: false,
        decision_grade: false,
        code: 'AAPL',
        engine: { version: 'v1' },
        execution_assumptions: {},
        dataset_metadata: {},
        dataset_lineage_readiness: {
          contract_kind: 'rule_backtest_parameter_sweep_dataset_lineage_readiness',
          contract_version: 'v1',
          readiness_state: 'diagnostic-only',
        },
        storage: { mode: 'response_only' },
        summary: {
          total_parameter_sets: 2,
          run_count: 2,
          skipped_count: 0,
          blocked_count: 0,
        },
        parameter_rows: [],
        skipped_rows: [],
        blocked_rows: [],
        failed_rows: [],
        reproducibility_metadata: {
          state: 'deterministic',
          grid_descriptor_hash_sha256: 'grid-hash',
        },
      },
    } as never);

    await backtestApi.runRuleParameterSweep({
      code: 'AAPL',
      strategyText: 'buy when close > sma(20)',
      parsedStrategy: {
        version: 'rule_v1',
        timeframe: '1d',
        sourceText: 'buy when close > sma(20)',
        normalizedText: 'buy when close > sma(20)',
        entry: { type: 'comparison' },
        exit: { type: 'comparison' },
        confidence: 0.91,
        needsConfirmation: false,
        ambiguities: [],
        summary: {},
        maxLookback: 20,
      } as never,
      startDate: '2024-01-01',
      endDate: '2024-02-01',
      lookbackBars: 20,
      initialCapital: 100000,
      feeBps: 0,
      slippageBps: 0,
      confirmed: true,
      parameterGrid: {
        'strategy_spec.signal.fast_period': [2, 3],
        'strategy_spec.signal.slow_period': [5],
      },
      maxCombinations: 6,
      totalTimeoutSeconds: 30,
      bars: [
        {
          code: 'AAPL',
          date: '2024-01-02',
          open: 100,
          high: 101,
          low: 99,
          close: 100.5,
          volume: 1000,
        },
      ],
    } as never);

    expect(apiClient.post).toHaveBeenCalledWith('/api/v1/backtest/rule/parameter-sweep', {
      code: 'AAPL',
      strategy_text: 'buy when close > sma(20)',
      parsed_strategy: expect.any(Object),
      start_date: '2024-01-01',
      end_date: '2024-02-01',
      lookback_bars: 20,
      initial_capital: 100000,
      fee_bps: 0,
      slippage_bps: 0,
      confirmed: true,
      parameter_grid: {
        'strategy_spec.signal.fast_period': [2, 3],
        'strategy_spec.signal.slow_period': [5],
      },
      max_combinations: 6,
      total_timeout_seconds: 30,
      bars: [
        {
          code: 'AAPL',
          date: '2024-01-02',
          open: 100,
          high: 101,
          low: 99,
          close: 100.5,
          volume: 1000,
        },
      ],
    });
  });

  it('loads the rule backtest support export index with camel-cased fields', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        run_id: 77,
        status: 'completed',
        exports: [
          {
            key: 'support_bundle_manifest',
            available: true,
            availability_reason: 'ready',
            format: 'json',
            media_type: 'application/json',
            delivery_mode: 'inline',
            endpoint_path: '/api/v1/backtest/rule/runs/77/support-bundle-manifest',
            payload_class: 'RuleBacktestSupportBundleManifestResponse',
          },
          {
            key: 'robustness_evidence_json',
            available: true,
            availability_reason: 'ready',
            format: 'json',
            media_type: 'application/json',
            delivery_mode: 'api',
            endpoint_path: '/api/v1/backtest/rule/runs/77/robustness-evidence.json',
            payload_class: 'RuleBacktestRobustnessEvidenceExportResponse',
          },
        ],
      },
    } as never);

    const payload = await backtestApi.getRuleBacktestSupportExportIndex(77);

    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/backtest/rule/runs/77/export-index');
    expect(payload).toMatchObject({
      runId: 77,
      status: 'completed',
      exports: [
        {
          key: 'support_bundle_manifest',
          available: true,
          availabilityReason: 'ready',
          format: 'json',
          mediaType: 'application/json',
          deliveryMode: 'inline',
          endpointPath: '/api/v1/backtest/rule/runs/77/support-bundle-manifest',
          payloadClass: 'RuleBacktestSupportBundleManifestResponse',
        },
        {
          key: 'robustness_evidence_json',
          available: true,
          availabilityReason: 'ready',
          format: 'json',
          mediaType: 'application/json',
          deliveryMode: 'api',
          endpointPath: '/api/v1/backtest/rule/runs/77/robustness-evidence.json',
          payloadClass: 'RuleBacktestRobustnessEvidenceExportResponse',
        },
      ],
    });
  });

  it('loads rule backtest support manifests without reconstructing nested payloads', async () => {
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({
        data: {
          manifest_version: 'rule_backtest_support_bundle_manifest_v1',
          manifest_kind: 'support_bundle_manifest',
          run: {
            run_id: 77,
            code: 'AAPL',
          },
          run_timing: {
            started_at: '2026-05-13T09:00:00Z',
          },
          run_diagnostics: {
            export_mode: 'stored_first',
          },
          artifact_availability: {
            execution_trace_json: true,
          },
          readback_integrity: {
            storage_state: 'stored',
          },
          result_authority: {
            source: 'stored_backtest_result',
          },
          artifact_counts: {
            trade_rows: 18,
          },
        },
      } as never)
      .mockResolvedValueOnce({
        data: {
          manifest_version: 'rule_backtest_support_bundle_reproducibility_manifest_v1',
          manifest_kind: 'support_bundle_reproducibility_manifest',
          run: {
            run_id: 77,
            code: 'AAPL',
          },
          run_timing: {
            completed_at: '2026-05-13T09:05:00Z',
          },
          run_diagnostics: {
            export_mode: 'stored_first',
          },
          artifact_availability: {
            execution_trace_csv: true,
          },
          readback_integrity: {
            storage_state: 'stored',
          },
          execution_assumptions_fingerprint: {
            sha256: 'abc123',
          },
          result_authority: {
            source: 'stored_backtest_result',
          },
        },
      } as never);

    const supportBundleManifest = await backtestApi.getRuleBacktestSupportBundleManifest(77);
    const reproducibilityManifest = await backtestApi.getRuleBacktestSupportBundleReproducibilityManifest(77);

    expect(apiClient.get).toHaveBeenNthCalledWith(1, '/api/v1/backtest/rule/runs/77/support-bundle-manifest');
    expect(apiClient.get).toHaveBeenNthCalledWith(2, '/api/v1/backtest/rule/runs/77/support-bundle-reproducibility-manifest');
    expect(supportBundleManifest.manifestVersion).toBe('rule_backtest_support_bundle_manifest_v1');
    expect(supportBundleManifest.run.runId).toBe(77);
    expect(supportBundleManifest.runTiming.startedAt).toBe('2026-05-13T09:00:00Z');
    expect(supportBundleManifest.artifactCounts.tradeRows).toBe(18);
    expect(reproducibilityManifest.manifestKind).toBe('support_bundle_reproducibility_manifest');
    expect(reproducibilityManifest.executionAssumptionsFingerprint.sha256).toBe('abc123');
    expect(reproducibilityManifest.resultAuthority.source).toBe('stored_backtest_result');
  });

  it('loads the rule backtest execution trace json export and returns csv as text', async () => {
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({
        data: {
          version: 'rule_backtest_execution_trace_export_v1',
          source: 'stored_execution_trace',
          completeness: 'full',
          missing_fields: [],
          trace_rows: [
            {
              date: '2026-05-12',
              event_type: 'buy',
              action_display: '买入',
              total_portfolio_value: 102500,
            },
          ],
          assumptions: {
            fill_price_basis: 'next_open',
          },
          execution_model: {
            fee_bps_per_side: 5,
            market_rules: {
              trading_day_execution: 'next_open',
            },
          },
          execution_assumptions: {
            slippage_bps: 3,
          },
          benchmark_summary: {
            resolved_mode: 'symbol',
          },
          fallback: {
            trace_rebuilt: false,
          },
        },
      } as never)
      .mockResolvedValueOnce({
        data: 'date,event_type,action_display,total_portfolio_value\n2026-05-12,buy,买入,102500\n',
      } as never);

    const jsonPayload = await backtestApi.getRuleBacktestExecutionTraceJson(77);
    const csvPayload = await backtestApi.getRuleBacktestExecutionTraceCsv(77);

    expect(apiClient.get).toHaveBeenNthCalledWith(1, '/api/v1/backtest/rule/runs/77/execution-trace.json');
    expect(apiClient.get).toHaveBeenNthCalledWith(2, '/api/v1/backtest/rule/runs/77/execution-trace.csv', {
      responseType: 'text',
    });
    expect(jsonPayload.traceRows?.[0]).toMatchObject({
      eventType: 'buy',
      actionDisplay: '买入',
      totalPortfolioValue: 102500,
    });
    expect(jsonPayload.executionModel?.marketRules?.tradingDayExecution).toBe('next_open');
    expect(jsonPayload.executionAssumptions.slippageBps).toBe(3);
    expect(jsonPayload.benchmarkSummary.resolvedMode).toBe('symbol');
    expect(jsonPayload.fallback.traceRebuilt).toBe(false);
    expect(csvPayload).toContain('date,event_type,action_display,total_portfolio_value');
  });

  it('loads the rule backtest robustness evidence export through the dedicated support endpoint', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        version: 'rule_backtest_robustness_evidence_export_v1',
        source: 'stored_robustness_analysis',
        robustness_analysis: {
          state: 'available',
          walk_forward: {
            state: 'available',
            windows: 4,
          },
        },
      },
    } as never);

    const payload = await backtestApi.getRuleBacktestRobustnessEvidenceJson(77);

    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/backtest/rule/runs/77/robustness-evidence.json');
    expect(payload).toMatchObject({
      version: 'rule_backtest_robustness_evidence_export_v1',
      source: 'stored_robustness_analysis',
      robustnessAnalysis: {
        state: 'available',
        walkForward: {
          state: 'available',
          windows: 4,
        },
      },
    });
  });
});
