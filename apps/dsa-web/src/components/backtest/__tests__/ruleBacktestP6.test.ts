import { beforeEach, describe, expect, it } from 'vitest';
import type { RuleBacktestRunResponse } from '../../../types/backtest';
import { normalizeDeterministicBacktestResult } from '../normalizeDeterministicBacktestResult';
import {
  RULE_BACKTEST_PRESET_STORAGE_KEY,
  buildRuleRunComparisonWarnings,
  buildRuleRunReportMarkdown,
  createRuleBacktestPresetFromRun,
  getRuleScenarioPlans,
  loadRuleBacktestPresets,
  saveRuleBacktestPreset,
} from '../ruleBacktestP6';

function makeRun(overrides: Partial<RuleBacktestRunResponse> = {}): RuleBacktestRunResponse {
  return {
    id: 501,
    code: 'ORCL',
    strategyText: '5日均线上穿20日均线买入，下穿卖出',
    parsedStrategy: {
      version: 'v1',
      timeframe: 'daily',
      sourceText: '5日均线上穿20日均线买入，下穿卖出',
      normalizedText: 'SMA5 上穿 SMA20 买入，下穿卖出。',
      entry: { type: 'group', op: 'and', rules: [] },
      exit: { type: 'group', op: 'or', rules: [] },
      confidence: 0.92,
      needsConfirmation: false,
      ambiguities: [],
      summary: {
        entry: 'SMA5 上穿 SMA20',
        exit: 'SMA5 下穿 SMA20',
      },
      maxLookback: 20,
      strategyKind: 'moving_average_crossover',
      executable: true,
      normalizationState: 'ready',
      assumptions: [],
      assumptionGroups: [],
      detectedStrategyFamily: 'moving_average_crossover',
      unsupportedReason: null,
      unsupportedDetails: [],
      unsupportedExtensions: [],
      coreIntentSummary: '已识别为均线交叉。',
      interpretationConfidence: 0.92,
      supportedPortionSummary: '均线交叉已支持。',
      rewriteSuggestions: [],
      parseWarnings: [],
      setup: {
        symbol: 'ORCL',
      },
      strategySpec: {
        strategyType: 'moving_average_crossover',
        strategyFamily: 'moving_average_crossover',
        symbol: 'ORCL',
        timeframe: 'daily',
        signal: {
          indicatorFamily: 'moving_average',
          fastPeriod: 5,
          slowPeriod: 20,
          fastType: 'simple',
          slowType: 'simple',
          entryCondition: 'fast_crosses_above_slow',
          exitCondition: 'fast_crosses_below_slow',
        },
        execution: {
          frequency: 'daily',
          signalTiming: 'bar_close',
          fillTiming: 'next_bar_open',
        },
        positionBehavior: {
          direction: 'long_only',
          entrySizing: 'all_available_capital',
          maxPositions: 1,
          pyramiding: false,
        },
        endBehavior: {
          policy: 'liquidate_at_end',
          priceBasis: 'close',
        },
        capital: {
          initialCapital: 100000,
          currency: 'USD',
        },
        costs: {
          feeBps: 0,
          slippageBps: 0,
        },
      },
    } as RuleBacktestRunResponse['parsedStrategy'],
    strategyHash: 'hash',
    timeframe: 'daily',
    startDate: '2026-01-01',
    endDate: '2026-03-31',
    periodStart: '2026-01-01',
    periodEnd: '2026-03-31',
    lookbackBars: 252,
    initialCapital: 100000,
    feeBps: 0,
    slippageBps: 0,
    parsedConfidence: 0.92,
    needsConfirmation: false,
    warnings: [],
    runAt: '2026-04-10T08:00:00Z',
    completedAt: '2026-04-10T08:05:00Z',
    status: 'completed',
    statusMessage: '规则回测已完成。',
    statusHistory: [{ status: 'completed', at: '2026-04-10T08:05:00Z' }],
    noResultReason: null,
    noResultMessage: null,
    tradeCount: 4,
    winCount: 3,
    lossCount: 1,
    totalReturnPct: 12.5,
    annualizedReturnPct: 20.1,
    benchmarkMode: 'auto',
    benchmarkCode: null,
    benchmarkReturnPct: 8.2,
    excessReturnVsBenchmarkPct: 4.3,
    buyAndHoldReturnPct: 7.8,
    excessReturnVsBuyAndHoldPct: 4.7,
    winRatePct: 75,
    avgTradeReturnPct: 3.2,
    maxDrawdownPct: -5.4,
    avgHoldingDays: 8,
    avgHoldingBars: 8,
    avgHoldingCalendarDays: 10,
    finalEquity: 112500,
    summary: {},
    executionModel: {
      timeframe: 'daily',
      feeBpsPerSide: 0,
      slippageBpsPerSide: 0,
    },
    executionAssumptions: {
      signalEvaluationTiming: 'bar close',
      benchmarkMethod: 'market_index',
    },
    benchmarkCurve: [],
    benchmarkSummary: {
      label: 'QQQ',
      resolvedMode: 'etf_qqq',
      requestedMode: 'auto',
      method: 'benchmark_security',
      returnPct: 8.2,
      fallbackUsed: false,
    },
    buyAndHoldCurve: [],
    buyAndHoldSummary: {
      label: '当前标的买入并持有',
      resolvedMode: 'same_symbol_buy_and_hold',
      method: 'same_symbol_buy_and_hold',
      returnPct: 7.8,
    },
    auditRows: [
      {
        date: '2026-01-01',
        cumulativeStrategyReturnPct: 0,
        cumulativeBenchmarkReturnPct: 0,
        cumulativeBuyAndHoldReturnPct: 0,
        totalPortfolioValue: 100000,
        dailyPnl: 0,
        dailyReturnPct: 0,
        drawdownPct: 0,
        targetPosition: 0,
      },
      {
        date: '2026-02-01',
        cumulativeStrategyReturnPct: 6,
        cumulativeBenchmarkReturnPct: 3,
        cumulativeBuyAndHoldReturnPct: 2.8,
        totalPortfolioValue: 106000,
        dailyPnl: 6000,
        dailyReturnPct: 6,
        drawdownPct: -2,
        targetPosition: 1,
        executedAction: 'buy',
      },
      {
        date: '2026-03-31',
        cumulativeStrategyReturnPct: 12.5,
        cumulativeBenchmarkReturnPct: 8.2,
        cumulativeBuyAndHoldReturnPct: 7.8,
        totalPortfolioValue: 112500,
        dailyPnl: 6500,
        dailyReturnPct: 6.13,
        drawdownPct: -5.4,
        targetPosition: 0,
        executedAction: 'sell',
      },
    ],
    dailyReturnSeries: [],
    exposureCurve: [],
    aiSummary: null,
    equityCurve: [],
    trades: [],
    executionTrace: {
      source: 'storedExecutionTrace',
      rows: [],
      assumptionsDefaults: {
        summaryText: 'next bar open / long only',
      },
      fallback: {
        runFallback: false,
        traceRebuilt: false,
        note: '标准执行路径',
      },
    },
    ...overrides,
  };
}

describe('ruleBacktestP6', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('builds comparison warnings and a readable report summary', () => {
    const baseRun = makeRun();
    const compareRun = makeRun({
      id: 502,
      startDate: '2025-01-01',
      endDate: '2025-12-31',
      feeBps: 5,
      slippageBps: 5,
      benchmarkMode: 'none',
    });

    const warnings = buildRuleRunComparisonWarnings([baseRun, compareRun]);
    expect(warnings).toEqual(expect.arrayContaining([
      expect.stringContaining('不同日期区间'),
      expect.stringContaining('手续费或滑点假设不同'),
      expect.stringContaining('不同基准设置'),
    ]));

    const markdown = buildRuleRunReportMarkdown({
      run: baseRun,
      normalized: normalizeDeterministicBacktestResult(baseRun),
      comparedRuns: [compareRun],
    });

    expect(markdown).toContain('确定性回测决策摘要');
    expect(markdown).toContain('总收益：12.50%');
    expect(markdown).toContain('比较提醒');
    expect(markdown).toContain('#502');
  });

  it('appends a robustness appendix when stored robustness evidence exists', () => {
    const baseRun = makeRun({
      robustnessAnalysis: {
        state: 'available',
        walkForward: {
          state: 'available',
          windowCount: 4,
          aggregateMetrics: {
            meanTotalReturnPct: 6.2,
            maxDrawdownPct: -3.1,
          },
        },
        monteCarlo: {
          state: 'available',
          simulationCount: 200,
          seed: 20260423,
          aggregateMetrics: {
            p05TotalReturnPct: -3.6,
            medianTotalReturnPct: 8.4,
            p95TotalReturnPct: 16.8,
            meanTotalReturnPct: 7.1,
            worstMaxDrawdownPct: 12.5,
          },
        },
        stressTests: {
          state: 'available',
          scenarioCount: 3,
          scenarios: [
            {
              scenarioKey: 'single_day_shock_down_15',
              metrics: {
                totalReturnPct: -18.4,
                sharpeRatio: -1.1,
                maxDrawdownPct: 21.3,
              },
            },
            {
              scenarioKey: 'volatility_whipsaw',
              metrics: {
                totalReturnPct: -6.5,
                sharpeRatio: -0.4,
                maxDrawdownPct: 12.6,
              },
            },
          ],
          worstScenario: {
            scenarioKey: 'single_day_shock_down_15',
          },
        },
      },
    });

    const markdown = buildRuleRunReportMarkdown({
      run: baseRun,
      normalized: normalizeDeterministicBacktestResult(baseRun),
    });

    expect(markdown).toContain('## 稳健性附录');
    expect(markdown).toContain('Walk-forward / 样本外检验');
    expect(markdown).toContain('状态：可用');
    expect(markdown).toContain('窗口数：4');
    expect(markdown).toContain('平均收益：6.20%');
    expect(markdown).toContain('回撤：-3.10%');
    expect(markdown).toContain('蒙特卡洛分布');
    expect(markdown).toContain('P05 / 中位 / P95 / 平均总收益：-3.60% / 8.40% / 16.80% / 7.10%');
    expect(markdown).toContain('最差最大回撤：-12.50%');
    expect(markdown).toContain('模拟次数：200');
    expect(markdown).toContain('随机种子：20,260,423');
    expect(markdown).toContain('压力场景');
    expect(markdown).toContain('场景数：3');
    expect(markdown).toContain('最差场景：单日冲击下跌 15%');
    expect(markdown).toContain('单日冲击下跌 15%：收益 -18.40% · Sharpe -1.10 · 回撤 -21.30%');
    expect(markdown).toContain('波动率来回扫：收益 -6.50% · Sharpe -0.40 · 回撤 -12.60%');
    expect(markdown).not.toContain('single_day_shock_down_15');
  });

  it('keeps the appendix compact when robustness fields are unavailable or insufficient', () => {
    const baseRun = makeRun({
      robustnessAnalysis: {
        state: 'insufficient_history',
        walkForward: {
          state: 'insufficient_history',
        },
        monteCarlo: {
          state: 'partial',
        },
        stressTests: {
          state: 'insufficient_history',
          scenarioCount: 0,
        },
      },
    });

    const markdown = buildRuleRunReportMarkdown({
      run: baseRun,
      normalized: normalizeDeterministicBacktestResult(baseRun),
    });

    expect(markdown).toContain('## 稳健性附录');
    expect(markdown).toContain('Walk-forward / 样本外检验');
    expect(markdown).toContain('状态：样本不足');
    expect(markdown).toContain('当前结果未提供可展示的分布摘要。');
    expect(markdown).toContain('样本不足，暂无可展示的压力场景明细。');
  });

  it('appends a drawdown phase attribution appendix from stored summary fields', () => {
    const baseRun = makeRun({
      summary: {
        drawdownRegimeAttribution: {
          version: 'v1',
          source: 'summary.drawdown_regime_attribution',
          state: 'partial',
          bucketCounts: {
            peak: {
              count: 1,
              sharePct: 25,
              avgDepthPct: null,
              worstDepthPct: null,
            },
            moderate: {
              count: 1,
              sharePct: 25,
              avgDepthPct: 6.25,
              worstDepthPct: 6.25,
            },
            unknown: {
              count: 2,
              sharePct: 50,
              avgDepthPct: null,
              worstDepthPct: null,
            },
          },
          contributionSummaries: {
            classifiedRows: {
              count: 2,
              sharePct: 50,
            },
            missingRows: {
              count: 2,
              sharePct: 50,
            },
          },
        },
      },
    });

    const markdown = buildRuleRunReportMarkdown({
      run: baseRun,
      normalized: normalizeDeterministicBacktestResult(baseRun),
    });

    expect(markdown).toContain('## 回撤阶段归因附录');
    expect(markdown).toContain('基于已存审计行的回撤阶段汇总，仅用于解释回撤来源；不改变收益、最大回撤、交易、图表或报告结论口径。');
    expect(markdown).toContain('状态：部分可用');
    expect(markdown).toContain('来源：已存审计行汇总');
    expect(markdown).toContain('已归类行 / 桶数：2 / 3');
    expect(markdown).toContain('已归类占比：50.00%');
    expect(markdown).toContain('缺失占比：50.00%');
    expect(markdown).toContain('高点区间：行数 1 · 占比 25.00% · 平均深度 -- · 最深回撤 --');
    expect(markdown).toContain('中度回撤：行数 1 · 占比 25.00% · 平均深度 -6.25% · 最深回撤 -6.25%');
    expect(markdown).toContain('未归类：行数 2 · 占比 50.00% · 平均深度 -- · 最深回撤 --');
    expect(markdown).not.toContain('drawdown_regime_attribution');
    expect(markdown).not.toContain('regimeAttribution');
    expect(markdown).not.toContain('market regime');
    expect(markdown).not.toContain('schema');
    expect(markdown).not.toContain('payload');
    expect(markdown).not.toContain('stored_audit_rows');
  });

  it('keeps the drawdown phase attribution appendix compact when stored summary is absent', () => {
    const baseRun = makeRun({
      summary: {},
    });

    const markdown = buildRuleRunReportMarkdown({
      run: baseRun,
      normalized: normalizeDeterministicBacktestResult(baseRun),
    });

    expect(markdown).toContain('## 回撤阶段归因附录');
    expect(markdown).toContain('状态：未提供');
    expect(markdown).toContain('来源：当前未提供');
    expect(markdown).toContain('当前结果未提供回撤阶段归因。');
    expect(markdown).not.toContain('drawdown_regime_attribution');
  });

  it('creates scenario plans for supported strategies', () => {
    const plans = getRuleScenarioPlans(makeRun());
    const labels = plans.map((plan) => plan.label);

    expect(labels).toContain('基准情景');
    expect(labels).toContain('费用/滑点压力');
    expect(labels).toContain('Lookback 窗口');
    expect(labels).toContain('均线窗口变体');
    expect(plans.find((plan) => plan.id === 'ma_window_variants')?.variants.length).toBeGreaterThan(0);
  });

  it('persists saved presets and deduplicates recent drafts', () => {
    const run = makeRun();
    const savedPreset = createRuleBacktestPresetFromRun(run, { kind: 'saved', name: 'ORCL Swing' });
    const recentPreset = createRuleBacktestPresetFromRun(run, { kind: 'recent' });

    saveRuleBacktestPreset(savedPreset);
    saveRuleBacktestPreset(recentPreset);
    saveRuleBacktestPreset(createRuleBacktestPresetFromRun(run, { kind: 'recent' }));

    const stored = loadRuleBacktestPresets();
    expect(window.localStorage.getItem(RULE_BACKTEST_PRESET_STORAGE_KEY)).toBeTruthy();
    expect(stored.filter((item) => item.kind === 'saved')).toHaveLength(1);
    expect(stored.filter((item) => item.kind === 'recent')).toHaveLength(1);
    expect(stored[0]?.name).toBeTruthy();
  });
});
