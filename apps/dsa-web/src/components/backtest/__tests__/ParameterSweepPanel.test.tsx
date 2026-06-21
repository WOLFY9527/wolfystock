import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ParameterSweepPanel from '../ParameterSweepPanel';
import { backtestApi } from '../../../api/backtest';
import type { RuleBacktestParseResponse } from '../../../types/backtest';

vi.mock('../../../api/backtest', () => ({
  backtestApi: {
    runRuleParameterSweep: vi.fn(),
  },
}));

function makeParsedStrategy(): RuleBacktestParseResponse {
  return {
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
      executable: true,
    } as never,
    executable: true,
    normalizationState: 'ready',
    confidence: 0.91,
    needsConfirmation: false,
    ambiguities: [],
    summary: {},
    maxLookback: 20,
  };
}

function makeResponse(overrides: Record<string, unknown> = {}) {
  return {
    contractKind: 'rule_backtest_parameter_sweep_pilot',
    contractVersion: 'v1',
    state: 'completed',
    diagnosticOnly: true,
    researchOnly: true,
    notOptimizer: true,
    winnerPromotion: false,
    decisionGrade: false,
    code: 'AAPL',
    engine: { version: 'v1' },
    executionAssumptions: {},
    datasetMetadata: {},
    datasetLineageReadiness: {
      contractKind: 'rule_backtest_parameter_sweep_dataset_lineage_readiness',
      readinessState: 'diagnostic-only',
      diagnosticOnly: true,
      blocked: false,
      barBoundary: {
        suppliedBarsToRunner: true,
        providerCallsExecuted: false,
        localBars: true,
      },
      missingLineageFields: ['adjustedBasis', 'corporateActionPolicy', 'sourceAuthority'],
      provenanceStatus: {
        providerHydrationExecuted: false,
        storedReadbackAvailable: false,
      },
      reproducibility: {
        inputShapeHashSha256: 'input-shape-hash',
        gridDescriptorHashSha256: 'grid-hash',
      },
    },
    storage: { mode: 'response_only' },
    summary: {
      totalParameterSets: 2,
      runCount: 2,
      executedCount: 2,
      completedCount: 2,
      blockedCount: 0,
      failedCount: 0,
      skippedCount: 0,
    },
    parameterRows: [
      {
        parameterSetId: 'row-1',
        state: 'completed',
        parameterValues: { 'strategy_spec.signal.fast_period': 2 },
        metrics: { total_return_pct: 1.2 },
      },
    ],
    skippedRows: [],
    blockedRows: [],
    failedRows: [],
    failClosedReasonCode: null,
    failClosedDiagnostics: {},
    reproducibilityMetadata: {
      state: 'deterministic',
      gridDescriptorHashSha256: 'grid-hash',
    },
    ...overrides,
  } as const;
}

function renderPanel() {
  render(
    <ParameterSweepPanel
      language="zh"
      code="AAPL"
      strategyText="buy when close > sma(20)"
      startDate="2024-01-01"
      endDate="2024-02-01"
      lookbackBars="20"
      initialCapital="100000"
      feeBps="0"
      slippageBps="0"
      parsedStrategy={makeParsedStrategy()}
      confirmed
      parseStale={false}
    />,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('ParameterSweepPanel', () => {
  it('renders diagnostic counts and lineage boundary for a valid sweep response', async () => {
    vi.mocked(backtestApi.runRuleParameterSweep).mockResolvedValueOnce(makeResponse());

    renderPanel();

    fireEvent.change(screen.getByLabelText('参数网格 JSON'), {
      target: { value: '{"strategy_spec.signal.fast_period":[2,3],"strategy_spec.signal.slow_period":[5]}' },
    });
    fireEvent.change(screen.getByLabelText('输入 bars JSON'), {
      target: {
        value: '[{"date":"2024-01-02","open":100,"high":101,"low":99,"close":100.5,"volume":1000}]',
      },
    });
    fireEvent.click(screen.getByTestId('pro-parameter-sweep-run-button'));

    const result = await screen.findByTestId('pro-parameter-sweep-result');
    expect(result).toHaveTextContent('运行数');
    expect(result).toHaveTextContent('2');
    expect(result).toHaveTextContent('诊断仅');
    expect(result).toHaveTextContent('研究仅');
    expect(result).toHaveTextContent('已输入 bars: true');
    expect(result).toHaveTextContent('补全调用: false');
    expect(result).toHaveTextContent('复权基础');
    expect(result).toHaveTextContent('公司行为政策');
    expect(result).toHaveTextContent('来源校验');
    expect(result).toHaveTextContent('输入形状: input-shape-hash');
    expect(result).toHaveTextContent('网格描述: grid-hash');
  });

  it('renders blocked copy for a fail-closed sweep response', async () => {
    vi.mocked(backtestApi.runRuleParameterSweep).mockResolvedValueOnce(makeResponse({
      state: 'rejected',
      diagnosticOnly: false,
      researchOnly: true,
      failClosedReasonCode: 'blocked_missing_supplied_bars',
      summary: {
        totalParameterSets: 2,
        runCount: 0,
        skippedCount: 2,
        blockedCount: 0,
      },
      datasetLineageReadiness: {
        readinessState: 'blocked',
        stateReasonCode: 'blocked_missing_supplied_bars',
        barBoundary: {
          suppliedBarsToRunner: false,
          providerCallsExecuted: false,
          localBars: false,
        },
        missingLineageFields: ['sourceAuthority'],
        provenanceStatus: {
          providerHydrationExecuted: false,
          storedReadbackAvailable: false,
        },
      },
    }));

    renderPanel();

    fireEvent.change(screen.getByLabelText('参数网格 JSON'), {
      target: { value: '{"strategy_spec.signal.fast_period":[2,3],"strategy_spec.signal.slow_period":[5]}' },
    });
    fireEvent.change(screen.getByLabelText('输入 bars JSON'), {
      target: {
        value: '[{"date":"2024-01-02","open":100,"high":101,"low":99,"close":100.5,"volume":1000}]',
      },
    });
    fireEvent.click(screen.getByTestId('pro-parameter-sweep-run-button'));

    const blocked = await screen.findByTestId('pro-parameter-sweep-blocked');
    expect(blocked).toHaveTextContent('阻断的诊断状态');
    expect(blocked).toHaveTextContent('blocked_missing_supplied_bars');
    expect(screen.getAllByText('阻断').length).toBeGreaterThan(0);
  });

  it('does not call the API when the supplied input is missing or invalid', async () => {
    renderPanel();

    fireEvent.click(screen.getByTestId('pro-parameter-sweep-run-button'));

    await waitFor(() => expect(backtestApi.runRuleParameterSweep).not.toHaveBeenCalled());
    expect(screen.getByTestId('pro-parameter-sweep-blocked')).toHaveTextContent('参数网格必须是包含非空数组的有效 JSON');
  });

  it('shows a fail-closed blocked state when the sweep API is unavailable', async () => {
    const api = backtestApi as typeof backtestApi & { runRuleParameterSweep?: unknown };
    const original = api.runRuleParameterSweep;
    api.runRuleParameterSweep = undefined;

    try {
      renderPanel();

      fireEvent.change(screen.getByLabelText('参数网格 JSON'), {
        target: { value: '{"strategy_spec.signal.fast_period":[2,3],"strategy_spec.signal.slow_period":[5]}' },
      });
      fireEvent.change(screen.getByLabelText('输入 bars JSON'), {
        target: {
          value: '[{"date":"2024-01-02","open":100,"high":101,"low":99,"close":100.5,"volume":1000}]',
        },
      });
      fireEvent.click(screen.getByTestId('pro-parameter-sweep-run-button'));

      const blocked = await screen.findByTestId('pro-parameter-sweep-blocked');
      expect(blocked).toHaveTextContent('参数扫描接口暂不可用');
    } finally {
      api.runRuleParameterSweep = original;
    }
  });

  it('does not leak winner, advice, or internal field copy into the rendered panel', async () => {
    vi.mocked(backtestApi.runRuleParameterSweep).mockResolvedValueOnce(makeResponse({
      providerHydration: true,
      debugTraceId: 'trace-1',
      rawPayload: { secret: true },
      internalNotes: 'do not show',
      recommendation: 'avoid',
    }));

    renderPanel();

    fireEvent.change(screen.getByLabelText('参数网格 JSON'), {
      target: { value: '{"strategy_spec.signal.fast_period":[2,3],"strategy_spec.signal.slow_period":[5]}' },
    });
    fireEvent.change(screen.getByLabelText('输入 bars JSON'), {
      target: {
        value: '[{"date":"2024-01-02","open":100,"high":101,"low":99,"close":100.5,"volume":1000}]',
      },
    });
    fireEvent.click(screen.getByTestId('pro-parameter-sweep-run-button'));

    await screen.findByTestId('pro-parameter-sweep-result');
    const panel = screen.getByTestId('pro-parameter-sweep-panel');
    expect(panel).not.toHaveTextContent(/winner|best|optimal|recommended/i);
    expect(panel).not.toHaveTextContent(/providerHydration|debugTraceId|rawPayload|internalNotes/i);
    expect(panel).toHaveTextContent('诊断仅');
    expect(panel).toHaveTextContent('研究仅');
  });
});
