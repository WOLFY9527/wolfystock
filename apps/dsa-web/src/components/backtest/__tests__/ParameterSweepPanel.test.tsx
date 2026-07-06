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

type EvidencePack = {
  schemaVersion: string;
  generatedAt: string;
  appSurface: string;
  suppliedInputs: {
    symbol: string;
    dateRange: {
      startDate: string;
      endDate: string;
    };
    strategy: {
      provided: boolean;
      confirmed: boolean;
      parseFresh: boolean;
    };
    parameterGrid: Record<string, Array<string | number | boolean | null>>;
  };
  parameterBounds: {
    maxCombinations: number;
    requestedCombinations: number;
    parameterKeys: string[];
  };
  datasetLineageReadiness: {
    readinessState: string;
    barBoundary: {
      suppliedBarsToRunner: boolean | string;
      externalDataCallsExecuted: boolean | string;
    };
    missingLineageFields?: string[];
  };
  resultCounts: {
    rowCount: number;
    scenarioCount: number | string;
    runCount: number | string;
    completedCount: number | string;
  };
  resultSummary: {
    diagnosticOnly: boolean;
    researchOnly: boolean;
    decisionGrade: boolean;
    sampleRows: Array<Record<string, unknown>>;
  };
};

async function submitValidSweep(response = makeResponse()) {
  vi.mocked(backtestApi.runRuleParameterSweep).mockResolvedValueOnce(response);

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
}

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: {
      writeText: vi.fn().mockResolvedValue(undefined),
    },
  });
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

  it('shows evidence pack export controls only after bounded sweep data exists', async () => {
    renderPanel();

    const initialRegistry = screen.getByTestId('pro-parameter-sweep-artifact-registry');
    expect(initialRegistry).toHaveTextContent('研究证据包');
    expect(initialRegistry).toHaveTextContent('Backtest Sweep');
    expect(initialRegistry).toHaveTextContent('待补证');
    expect(initialRegistry).toHaveTextContent('已输入条件、有界参数、谱系、告警与紧凑结果计数');
    expect(initialRegistry).not.toHaveTextContent('backtest-sweep-evidence-pack.v1');
    expect(initialRegistry).not.toHaveTextContent('Artifact key');
    expect(initialRegistry).not.toHaveTextContent('Schema version');

    expect(screen.queryByTestId('pro-parameter-sweep-evidence-copy')).not.toBeInTheDocument();
    expect(screen.queryByTestId('pro-parameter-sweep-evidence-download')).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('参数网格 JSON'), {
      target: { value: '{"strategy_spec.signal.fast_period":[2,3]}' },
    });
    fireEvent.change(screen.getByLabelText('输入 bars JSON'), {
      target: {
        value: '[{"date":"2024-01-02","open":100,"high":101,"low":99,"close":100.5,"volume":1000}]',
      },
    });
    vi.mocked(backtestApi.runRuleParameterSweep).mockResolvedValueOnce(makeResponse());

    fireEvent.click(screen.getByTestId('pro-parameter-sweep-run-button'));

    const registry = await screen.findByTestId('pro-parameter-sweep-artifact-registry');
    expect(registry).toHaveTextContent('可用');
    expect(registry).toHaveTextContent('来源页面');
    expect(registry).not.toHaveTextContent('Artifact key');
    expect(registry).not.toHaveTextContent('Schema version');
    expect(registry).not.toHaveTextContent('Source surface');
    expect(await screen.findByTestId('pro-parameter-sweep-evidence-copy')).toHaveTextContent('复制证据包');
    expect(screen.getByTestId('pro-parameter-sweep-evidence-download')).toHaveTextContent('导出研究证据包');
  });

  it('copies deterministic evidence pack JSON with supplied inputs, lineage, bounds, and result counts', async () => {
    await submitValidSweep(makeResponse({
      parameterRows: [
        { parameterSetId: 'row-1', state: 'completed', parameterValues: { fast: 2 }, metrics: { total_return_pct: 1.2 } },
        { parameterSetId: 'row-2', state: 'completed', parameterValues: { fast: 3 }, metrics: { total_return_pct: -0.4 } },
      ],
    }));

    fireEvent.click(screen.getByTestId('pro-parameter-sweep-evidence-copy'));

    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    const copied = String((navigator.clipboard.writeText as ReturnType<typeof vi.fn>).mock.calls.at(-1)?.[0] || '');
    const pack = JSON.parse(copied) as EvidencePack;

    expect(pack.schemaVersion).toBe('backtest-sweep-evidence-pack.v1');
    expect(pack.generatedAt).toEqual(expect.any(String));
    expect(pack.appSurface).toBe('Backtest / Parameter Sweep');
    expect(pack.suppliedInputs).toMatchObject({
      symbol: 'AAPL',
      dateRange: { startDate: '2024-01-01', endDate: '2024-02-01' },
      strategy: {
        provided: true,
        confirmed: true,
        parseFresh: true,
      },
      parameterGrid: {
        'strategy_spec.signal.fast_period': [2, 3],
        'strategy_spec.signal.slow_period': [5],
      },
    });
    expect(pack.parameterBounds).toMatchObject({
      maxCombinations: 10,
      requestedCombinations: 2,
      parameterKeys: ['strategy_spec.signal.fast_period', 'strategy_spec.signal.slow_period'],
    });
    expect(pack.datasetLineageReadiness).toMatchObject({
      readinessState: 'diagnostic-only',
      barBoundary: {
        suppliedBarsToRunner: true,
        externalDataCallsExecuted: false,
      },
    });
    expect(pack.resultCounts).toMatchObject({
      rowCount: 2,
      scenarioCount: 2,
      runCount: 2,
      completedCount: 2,
    });
    expect(pack.resultSummary).toMatchObject({
      diagnosticOnly: true,
      researchOnly: true,
      decisionGrade: false,
    });
  });

  it('marks missing evidence pack fields as unknown instead of inferring values', async () => {
    await submitValidSweep(makeResponse({
      datasetLineageReadiness: {
        readinessState: null,
        missingLineageFields: ['adjustedBasis', 'calendarSessionPolicy'],
        barBoundary: {},
        provenanceStatus: {},
      },
      summary: {},
      parameterRows: [],
    }));

    fireEvent.click(screen.getByTestId('pro-parameter-sweep-evidence-copy'));

    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    const copied = String((navigator.clipboard.writeText as ReturnType<typeof vi.fn>).mock.calls.at(-1)?.[0] || '');
    const pack = JSON.parse(copied) as EvidencePack;

    expect(pack.datasetLineageReadiness.readinessState).toBe('待补证');
    expect(pack.datasetLineageReadiness.missingLineageFields).toEqual(['复权基础', '交易日历策略']);
    expect(pack.resultCounts.rowCount).toBe(0);
    expect(pack.resultCounts.scenarioCount).toBe('待补证');
    expect(pack.resultSummary.sampleRows).toEqual([]);
  });

  it('does not export fake evidence for blocked or unavailable sweep results', async () => {
    vi.mocked(backtestApi.runRuleParameterSweep).mockResolvedValueOnce(makeResponse({
      state: 'rejected',
      failClosedReasonCode: 'blocked_missing_supplied_bars',
      datasetLineageReadiness: {
        readinessState: 'blocked',
        stateReasonCode: 'blocked_missing_supplied_bars',
      },
    }));

    renderPanel();

    fireEvent.change(screen.getByLabelText('参数网格 JSON'), {
      target: { value: '{"strategy_spec.signal.fast_period":[2,3]}' },
    });
    fireEvent.change(screen.getByLabelText('输入 bars JSON'), {
      target: {
        value: '[{"date":"2024-01-02","open":100,"high":101,"low":99,"close":100.5,"volume":1000}]',
      },
    });
    fireEvent.click(screen.getByTestId('pro-parameter-sweep-run-button'));

    await screen.findByTestId('pro-parameter-sweep-blocked');
    const registry = screen.getByTestId('pro-parameter-sweep-artifact-registry');
    expect(registry).toHaveTextContent('阻断');
    expect(registry).not.toHaveTextContent('backtest-sweep-evidence-pack');
    expect(screen.getByTestId('pro-parameter-sweep-registry-copy-blocked')).toBeDisabled();
    expect(navigator.clipboard.writeText).not.toHaveBeenCalled();
    expect(screen.queryByTestId('pro-parameter-sweep-evidence-copy')).not.toBeInTheDocument();
    expect(screen.queryByTestId('pro-parameter-sweep-evidence-download')).not.toBeInTheDocument();
  });

  it('keeps exported evidence pack free of advice, winner, and raw internal fields', async () => {
    await submitValidSweep(makeResponse({
      winnerPromotion: true,
      requestId: 'req-123',
      traceId: 'trace-123',
      debugTraceId: 'debug-123',
      rawPayload: { recommendation: 'buy now', targetPrice: 999 },
      providerPayload: { credential: 'secret' },
      parameterRows: [
        {
          parameterSetId: 'row-1',
          state: 'completed',
          parameterValues: { fast: 2 },
          metrics: { total_return_pct: 1.2 },
          rawPayload: { secret: true },
        },
      ],
    }));

    fireEvent.click(screen.getByTestId('pro-parameter-sweep-evidence-copy'));

    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    const copied = String((navigator.clipboard.writeText as ReturnType<typeof vi.fn>).mock.calls.at(-1)?.[0] || '');

    expect(copied).not.toMatch(/winner|best|optimal|recommend|buy|sell|hold|target price|stop loss|position sizing/i);
    expect(copied).not.toMatch(/requestId|traceId|debugTraceId|rawPayload|providerPayload|credential/i);
  });
});
