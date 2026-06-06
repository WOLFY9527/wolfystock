import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { translate, UI_LANGUAGE_STORAGE_KEY } from '../../i18n/core';
import type {
  BacktestRunHistoryItem,
  BacktestRunResponse,
  PrepareBacktestSamplesResponse,
  RuleBacktestParseResponse,
  RuleBacktestRunResponse,
} from '../../types/backtest';
import { RULE_BACKTEST_PRESET_STORAGE_KEY } from '../../components/backtest/ruleBacktestP6';
import BacktestPage from '../BacktestPage';
import DeterministicBacktestResultPage from '../DeterministicBacktestResultPage';

function bt(language: 'zh' | 'en', key: string, vars?: Record<string, string | number | undefined>) {
  return translate(language, `backtest.${key}`, vars);
}

const CHART_IMPORT_TIMEOUT = 5000;

const {
  runBacktest,
  getResults,
  getOverallPerformance,
  getStockPerformance,
  prepareSamples,
  getHistory,
  getSampleStatus,
  clearSamples,
  clearResults,
  parseRuleStrategy,
  runRuleBacktest,
  getRuleBacktestRuns,
  getRuleBacktestRun,
  getRuleBacktestRunStatus,
  cancelRuleBacktestRun,
} = vi.hoisted(() => ({
  runBacktest: vi.fn(),
  getResults: vi.fn(),
  getOverallPerformance: vi.fn(),
  getStockPerformance: vi.fn(),
  prepareSamples: vi.fn(),
  getHistory: vi.fn(),
  getSampleStatus: vi.fn(),
  clearSamples: vi.fn(),
  clearResults: vi.fn(),
  parseRuleStrategy: vi.fn(),
  runRuleBacktest: vi.fn(),
  getRuleBacktestRuns: vi.fn(),
  getRuleBacktestRun: vi.fn(),
  getRuleBacktestRunStatus: vi.fn(),
  cancelRuleBacktestRun: vi.fn(),
}));

vi.mock('motion/react', async () => {
  const React = await import('react');
  type StaticMotionDivProps = React.HTMLAttributes<HTMLDivElement> & {
    children?: React.ReactNode;
    animate?: unknown;
    exit?: unknown;
    initial?: unknown;
    layout?: unknown;
    transition?: unknown;
    variants?: unknown;
    whileHover?: unknown;
    whileTap?: unknown;
  };

  const StaticDiv = React.forwardRef<HTMLDivElement, StaticMotionDivProps>(
    ({ children, ...props }, ref) => {
      const rest = { ...props } as Record<string, unknown>;
      delete rest.animate;
      delete rest.exit;
      delete rest.initial;
      delete rest.layout;
      delete rest.transition;
      delete rest.variants;
      delete rest.whileHover;
      delete rest.whileTap;
      return React.createElement('div', { ...rest, ref }, children);
    },
  );
  StaticDiv.displayName = 'StaticMotionDiv';

  return {
    LazyMotion: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
    AnimatePresence: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
    domAnimation: {},
    m: {
      div: StaticDiv,
      section: StaticDiv,
    },
  };
});

vi.mock('../../api/backtest', () => ({
  backtestApi: {
    run: runBacktest,
    getResults,
    getOverallPerformance,
    getStockPerformance,
    prepareSamples,
    getHistory,
    getSampleStatus,
    clearSamples,
    clearResults,
    parseRuleStrategy,
    runRuleBacktest,
    getRuleBacktestRuns,
    getRuleBacktestRun,
    getRuleBacktestRunStatus,
    cancelRuleBacktestRun,
  },
}));

function renderBacktestRoutes(
  initialEntries: Array<string | { pathname: string; state?: unknown }> = ['/backtest'],
) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <UiLanguageProvider>
        <Routes>
          <Route path="/backtest" element={<BacktestPage />} />
          <Route path="/backtest/results/:runId" element={<DeterministicBacktestResultPage />} />
          <Route path="/:locale/backtest" element={<BacktestPage />} />
          <Route path="/:locale/backtest/results/:runId" element={<DeterministicBacktestResultPage />} />
        </Routes>
      </UiLanguageProvider>
    </MemoryRouter>,
  );
}

async function flushPendingUiWork() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await vi.dynamicImportSettled();
  });
}

async function clickAndFlush(target: HTMLElement) {
  await act(async () => {
    fireEvent.click(target);
    await Promise.resolve();
    await Promise.resolve();
  });
}

function makeRunResponse(overrides: Partial<BacktestRunResponse> = {}): BacktestRunResponse {
  return {
    runId: 1,
    runAt: '2026-04-07T08:00:00Z',
    processed: 1,
    saved: 1,
    completed: 1,
    insufficient: 0,
    errors: 0,
    candidateCount: 1,
    noResultReason: null,
    noResultMessage: null,
    evaluationMode: 'historical_analysis_evaluation',
    requestedMode: 'local_first',
    resolvedSource: 'LocalParquet',
    fallbackUsed: false,
    evaluationWindowTradingBars: 10,
    maturityCalendarDays: 14,
    executionAssumptions: {
      moduleType: 'historical_analysis_evaluation',
      priceBasis: 'close',
    },
    ...overrides,
  };
}

function makeHistoryItem(): BacktestRunHistoryItem {
  return {
    id: 1,
    code: 'ORCL',
    evalWindowDays: 10,
    evaluationWindowTradingBars: 10,
    minAgeDays: 14,
    maturityCalendarDays: 14,
    force: false,
    runAt: '2026-04-07T08:00:00Z',
    completedAt: '2026-04-07T08:00:00Z',
    processed: 1,
    saved: 1,
    completed: 1,
    insufficient: 0,
    errors: 0,
    candidateCount: 1,
    resultCount: 1,
    noResultReason: null,
    noResultMessage: null,
    status: 'completed',
    totalEvaluations: 1,
    completedCount: 1,
    insufficientCount: 0,
    longCount: 1,
    cashCount: 0,
    winCount: 1,
    lossCount: 0,
    neutralCount: 0,
    winRatePct: 100,
    avgStockReturnPct: 6,
    avgSimulatedReturnPct: 10,
    directionAccuracyPct: 100,
    summary: {},
    evaluationMode: 'historical_analysis_evaluation',
    requestedMode: 'local_first',
    resolvedSource: 'LocalParquet',
    fallbackUsed: false,
    executionAssumptions: {
      moduleType: 'historical_analysis_evaluation',
    },
  };
}

function makeRuleParseResponse(): RuleBacktestParseResponse {
  return {
    code: 'ORCL',
    strategyText: '资金100000，从2025-01-01到2025-12-31，每天买100股ORCL，买到资金耗尽为止',
    normalizedStrategyFamily: 'periodic_accumulation',
    executable: true,
    normalizationState: 'assumed',
    assumptions: [
      { key: 'fill_timing', label: '成交时点', value: '当日开盘价', reason: '按定投计划在交易日开盘执行。' },
    ],
    assumptionGroups: [
      {
        key: 'execution_defaults',
        label: '执行默认值',
        items: [
          { key: 'fill_timing', label: '成交时点', value: '当日开盘价', reason: '按定投计划在交易日开盘执行。' },
        ],
      },
    ],
    detectedStrategyFamily: 'periodic_accumulation',
    unsupportedReason: null,
    unsupportedDetails: [],
    unsupportedExtensions: [],
    coreIntentSummary: '已识别为单标的区间定投：ORCL，按固定频率买入。',
    interpretationConfidence: 0.97,
    supportedPortionSummary: '已识别为单标的区间定投规则。',
    rewriteSuggestions: [],
    parseWarnings: [],
    parsedStrategy: {
      version: 'v1',
      timeframe: 'daily',
      sourceText: '资金100000，从2025-01-01到2025-12-31，每天买100股ORCL，买到资金耗尽为止',
      normalizedText: '资金 100000，2025-01-01 至 2025-12-31，每个交易日买入 100 股 ORCL，现金不足即停止买入。',
      entry: { type: 'group', op: 'and', rules: [] },
      exit: { type: 'group', op: 'or', rules: [] },
      confidence: 0.97,
      needsConfirmation: false,
      ambiguities: [],
      summary: {
        entry: '每个交易日买入 100 股 ORCL',
        exit: '区间结束统一按收盘价平仓',
        strategy: '中文定投策略草稿',
      },
      maxLookback: 1,
      strategyKind: 'periodic_accumulation',
      executable: true,
      normalizationState: 'assumed',
      assumptions: [
        { key: 'fill_timing', label: '成交时点', value: '当日开盘价', reason: '按定投计划在交易日开盘执行。' },
      ],
      assumptionGroups: [
        {
          key: 'execution_defaults',
          label: '执行默认值',
          items: [
            { key: 'fill_timing', label: '成交时点', value: '当日开盘价', reason: '按定投计划在交易日开盘执行。' },
          ],
        },
      ],
      detectedStrategyFamily: 'periodic_accumulation',
      unsupportedReason: null,
      unsupportedDetails: [],
      unsupportedExtensions: [],
      coreIntentSummary: '已识别为单标的区间定投：ORCL，按固定频率买入。',
      interpretationConfidence: 0.97,
      supportedPortionSummary: '已识别为单标的区间定投规则。',
      rewriteSuggestions: [],
      parseWarnings: [],
      setup: {
        symbol: 'ORCL',
        startDate: '2025-01-01',
        endDate: '2025-12-31',
        initialCapital: 100000,
        executionFrequency: 'daily',
        action: 'buy',
        orderMode: 'fixed_shares',
        quantityPerTrade: 100,
        cashPolicy: 'stop_when_insufficient_cash',
        executionPriceBasis: 'open',
        feeBps: 0,
        slippageBps: 0,
        exitPolicy: 'close_at_end',
      },
      strategySpec: {
        strategyType: 'periodic_accumulation',
        version: 'v1',
        symbol: 'ORCL',
        timeframe: 'daily',
        dateRange: {
          startDate: '2025-01-01',
          endDate: '2025-12-31',
        },
        capital: {
          initialCapital: 100000,
          currency: 'USD',
        },
        schedule: {
          frequency: 'daily',
          timing: 'session_open',
        },
        entry: {
          side: 'buy',
          order: {
            mode: 'fixed_shares',
            quantity: 100,
            amount: null,
          },
          priceBasis: 'open',
        },
        exit: {
          policy: 'close_at_end',
          priceBasis: 'close',
        },
        positionBehavior: {
          accumulate: true,
          cashPolicy: 'stop_when_insufficient_cash',
        },
        riskControls: {
          stopLossPct: 5,
          takeProfitPct: 10,
          trailingStopPct: 8,
        },
        costs: {
          feeBps: 0,
          slippageBps: 0,
        },
      },
    },
    confidence: 0.97,
    needsConfirmation: true,
    ambiguities: [],
    summary: {
      entry: '每个交易日买入 100 股 ORCL',
      exit: '区间结束统一按收盘价平仓',
      strategy: '中文定投策略草稿',
    },
    maxLookback: 1,
  };
}

function makeUnsupportedMacdParseResponse(): RuleBacktestParseResponse {
  return {
    code: 'AAPL',
    strategyText: 'MACD金叉买入，止损5%，死叉卖出',
    normalizedStrategyFamily: 'macd_crossover',
    executable: false,
    normalizationState: 'unsupported',
    assumptions: [],
    assumptionGroups: [],
    detectedStrategyFamily: 'macd_crossover',
    unsupportedReason: '当前已支持 MACD 主规则，但不支持叠加固定止损 / 止盈 / trailing stop。',
    unsupportedDetails: [
      { code: 'unsupported_strategy_combination', title: '组合执行语义', message: '当前已支持技术信号主规则，但不支持叠加固定止损 / 止盈 / trailing stop。' },
    ],
    unsupportedExtensions: [
      { code: 'unsupported_strategy_combination', title: '组合执行语义', message: '当前已支持技术信号主规则，但不支持叠加固定止损 / 止盈 / trailing stop。' },
    ],
    coreIntentSummary: '已识别为 MACD 金叉 / 死叉主规则。',
    interpretationConfidence: 0.9,
    supportedPortionSummary: '已识别为 MACD 金叉 / 死叉主规则。',
    rewriteSuggestions: [
      { label: '改写成当前可执行版本', strategyText: 'AAPL，MACD金叉买入，死叉卖出' },
    ],
    parseWarnings: [
      { code: 'default_macd_periods', message: '未显式写出 MACD 参数，当前默认使用 (12, 26, 9)。' },
    ],
    parsedStrategy: {
      version: 'v1',
      timeframe: 'daily',
      sourceText: 'MACD金叉买入，止损5%，死叉卖出',
      normalizedText: 'MACD(12,26,9) 金叉买入，MACD(12,26,9) 死叉卖出。',
      entry: { type: 'group', op: 'and', rules: [] },
      exit: { type: 'group', op: 'or', rules: [] },
      confidence: 0.96,
      needsConfirmation: true,
      ambiguities: [],
      summary: {
        entry: '买入条件：MACD(12,26,9) 金叉',
        exit: '卖出条件：MACD(12,26,9) 死叉',
        strategy: 'MACD 交叉策略',
      },
      maxLookback: 35,
      strategyKind: 'macd_crossover',
      executable: false,
      normalizationState: 'unsupported',
      assumptions: [],
      assumptionGroups: [],
      detectedStrategyFamily: 'macd_crossover',
      unsupportedReason: '当前已支持 MACD 主规则，但不支持叠加固定止损 / 止盈 / trailing stop。',
      unsupportedDetails: [
        { code: 'unsupported_strategy_combination', title: '组合执行语义', message: '当前已支持技术信号主规则，但不支持叠加固定止损 / 止盈 / trailing stop。' },
      ],
      unsupportedExtensions: [
        { code: 'unsupported_strategy_combination', title: '组合执行语义', message: '当前已支持技术信号主规则，但不支持叠加固定止损 / 止盈 / trailing stop。' },
      ],
      coreIntentSummary: '已识别为 MACD 金叉 / 死叉主规则。',
      interpretationConfidence: 0.9,
      supportedPortionSummary: '已识别为 MACD 金叉 / 死叉主规则。',
      rewriteSuggestions: [
        { label: '改写成当前可执行版本', strategyText: 'AAPL，MACD金叉买入，死叉卖出' },
      ],
      parseWarnings: [
        { code: 'default_macd_periods', message: '未显式写出 MACD 参数，当前默认使用 (12, 26, 9)。' },
      ],
      strategySpec: {
        strategyType: 'macd_crossover',
        symbol: 'AAPL',
      },
    },
    confidence: 0.96,
    needsConfirmation: true,
    ambiguities: [],
    summary: {
      entry: '买入条件：MACD(12,26,9) 金叉',
      exit: '卖出条件：MACD(12,26,9) 死叉',
      strategy: 'MACD 交叉策略',
    },
    maxLookback: 35,
  };
}

function makeLegacySetupOnlyParseResponse(): RuleBacktestParseResponse {
  const response = makeRuleParseResponse();
  return {
    ...response,
    parsedStrategy: {
      ...response.parsedStrategy,
      strategySpec: undefined,
    },
  };
}

function makeRuleRunResponse(overrides: Partial<RuleBacktestRunResponse> = {}): RuleBacktestRunResponse {
  return {
    id: 99,
    code: 'ORCL',
    strategyText: '资金100000，从2025-01-01到2025-12-31，每天买100股ORCL，买到资金耗尽为止',
    parsedStrategy: makeRuleParseResponse().parsedStrategy,
    strategyHash: 'hash',
    timeframe: 'daily',
    startDate: '2025-01-01',
    endDate: '2025-12-31',
    periodStart: '2025-01-01',
    periodEnd: '2025-12-31',
    lookbackBars: 252,
    initialCapital: 100000,
    feeBps: 0,
    slippageBps: 0,
    parsedConfidence: 0.97,
    needsConfirmation: true,
    warnings: [],
    runAt: '2026-04-07T08:00:00Z',
    completedAt: null,
    status: 'queued',
    statusMessage: '策略已提交，等待开始执行。',
    statusHistory: [
      { status: 'queued', at: '2026-04-07T08:00:00Z' },
    ],
    noResultReason: null,
    noResultMessage: null,
    tradeCount: 0,
    winCount: 0,
    lossCount: 0,
    totalReturnPct: 0,
    annualizedReturnPct: 0,
    benchmarkMode: 'auto',
    benchmarkCode: null,
    benchmarkReturnPct: null,
    excessReturnVsBenchmarkPct: null,
    buyAndHoldReturnPct: 0,
    excessReturnVsBuyAndHoldPct: 0,
    winRatePct: 0,
    avgTradeReturnPct: 0,
    maxDrawdownPct: 0,
    avgHoldingDays: 0,
    avgHoldingBars: 0,
    avgHoldingCalendarDays: 0,
    finalEquity: 100000,
    summary: {
      parsedStrategySummary: makeRuleParseResponse().summary,
    },
    executionAssumptions: {
      priceBasis: 'close',
      signalEvaluationTiming: 'bar close',
      entryFillTiming: 'next bar open',
      positionSizing: 'all_available_capital',
    },
    professionalReadiness: {
      overall_state: 'research_prototype',
      professional_quant_ready: false,
      adjusted_data_state: 'unknown_or_mixed',
      corporate_action_state: 'not_ready',
      trading_calendar_state: 'available_bars_only',
      cost_model_state: 'baseline_bps_only',
      reproducibility_state: 'partial_without_dataset_lineage',
    },
    adjustedDataState: 'unknown_or_mixed',
    corporateActionState: 'not_ready',
    tradingCalendarState: 'available_bars_only',
    costModelState: 'baseline_bps_only',
    reproducibilityState: 'partial_without_dataset_lineage',
    benchmarkCurve: [],
    benchmarkSummary: {
      label: bt('zh', 'resultPage.buyAndHoldDefault'),
      requestedMode: 'auto',
      resolvedMode: 'same_symbol_buy_and_hold',
      method: 'same_symbol_buy_and_hold',
      priceBasis: 'close',
      startDate: '2025-01-01',
      endDate: '2025-12-31',
      returnPct: 0,
    },
    buyAndHoldCurve: [],
    buyAndHoldSummary: {
      label: bt('zh', 'resultPage.buyAndHoldDefault'),
      requestedMode: 'same_symbol_buy_and_hold',
      resolvedMode: 'same_symbol_buy_and_hold',
      method: 'same_symbol_buy_and_hold',
      priceBasis: 'close',
      startDate: '2025-01-01',
      endDate: '2025-12-31',
      returnPct: 0,
    },
    auditRows: [
      {
        date: '2025-01-01',
        targetPosition: 0,
        totalPortfolioValue: 100000,
        cumulativeStrategyReturnPct: 0,
        cumulativeBenchmarkReturnPct: 0,
        cumulativeBuyAndHoldReturnPct: 0,
        dailyPnl: 0,
        dailyReturnPct: 0,
        drawdownPct: 0,
      },
      {
        date: '2025-06-01',
        targetPosition: 1,
        executedAction: 'buy',
        fillPrice: 50,
        totalPortfolioValue: 103000,
        cumulativeStrategyReturnPct: 3,
        cumulativeBenchmarkReturnPct: 1.8,
        cumulativeBuyAndHoldReturnPct: 1.6,
        dailyPnl: 3000,
        dailyReturnPct: 3,
        drawdownPct: -1.2,
      },
      {
        date: '2025-12-31',
        targetPosition: 0,
        executedAction: 'sell',
        fillPrice: 55,
        totalPortfolioValue: 108000,
        cumulativeStrategyReturnPct: 8,
        cumulativeBenchmarkReturnPct: 4.2,
        cumulativeBuyAndHoldReturnPct: 3.9,
        dailyPnl: 5000,
        dailyReturnPct: 4.85,
        drawdownPct: -2.4,
      },
    ],
    dailyReturnSeries: [],
    exposureCurve: [],
    aiSummary: null,
    equityCurve: [],
    trades: [],
    ...overrides,
  };
}

describe('BacktestPage', () => {
  async function switchToProfessionalMode() {
    fireEvent.click(screen.getByRole('tab', { name: /专业|Professional/i }));
    expect(await screen.findByTestId('pro-backtest-workspace')).toBeInTheDocument();
  }

  async function openDeterministicStrategyInput() {
    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));
    await switchToProfessionalMode();
    fireEvent.click(screen.getByTestId('pro-workflow-step-strategy'));
    expect(await screen.findByTestId('pro-step-strategy')).toBeInTheDocument();
  }

  async function parseDeterministicStrategy() {
    await openDeterministicStrategyInput();
    await clickAndFlush(within(screen.getByTestId('pro-step-strategy')).getByRole('button', { name: '解析策略' }));
    expect(await screen.findByTestId('pro-rule-preview')).toBeInTheDocument();
  }

  beforeEach(() => {
    vi.resetAllMocks();
    vi.useRealTimers();
    window.localStorage.removeItem(UI_LANGUAGE_STORAGE_KEY);

    getResults.mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    getHistory.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [makeHistoryItem()],
    });
    getSampleStatus.mockResolvedValue({
      code: 'ORCL',
      preparedCount: 8,
      preparedStartDate: '2026-03-01',
      preparedEndDate: '2026-03-18',
      latestPreparedAt: '2026-04-07T08:00:00Z',
      latestPreparedSampleDate: '2026-03-18',
      latestEligibleSampleDate: '2026-03-18',
      excludedRecentReason: 'evaluation_window_not_satisfied',
      excludedRecentMessage: '最新行情到 2026-04-07，但评估需要完整的 10 根未来窗口，所以最新可用于样本生成的日期只到 2026-03-18。',
      evalWindowDays: 10,
      minAgeDays: 14,
      requestedMode: 'local_first',
      resolvedSource: 'LocalParquet',
      fallbackUsed: false,
      pricingResolvedSource: 'LocalParquet',
      pricingFallbackUsed: false,
      evaluationWindowTradingBars: 10,
      maturityCalendarDays: 14,
    });
    clearSamples.mockResolvedValue({
      code: 'ORCL',
      deletedRuns: 0,
      deletedResults: 0,
      deletedSamples: 0,
      deletedSummaries: 0,
      message: 'ok',
    });
    clearResults.mockResolvedValue({
      code: 'ORCL',
      deletedRuns: 0,
      deletedResults: 0,
      deletedSamples: 0,
      deletedSummaries: 0,
      message: 'ok',
    });
    getOverallPerformance.mockResolvedValue(null);
    getStockPerformance.mockResolvedValue(null);
    prepareSamples.mockResolvedValue({
      code: 'ORCL',
      sampleCount: 60,
      prepared: 4,
      skippedExisting: 2,
      marketRowsSaved: 10,
      candidateRows: 12,
      evalWindowDays: 10,
      minAgeDays: 14,
      preparedStartDate: '2026-03-01',
      preparedEndDate: '2026-03-18',
      latestPreparedAt: '2026-04-07T08:00:00Z',
      noResultReason: null,
      noResultMessage: '已准备 4 条历史分析评估样本，可重新运行评估。',
      requestedMode: 'local_first',
      resolvedSource: 'LocalParquet',
      fallbackUsed: false,
      evaluationWindowTradingBars: 10,
      maturityCalendarDays: 14,
    } satisfies PrepareBacktestSamplesResponse);
    runBacktest.mockResolvedValue(makeRunResponse());
    parseRuleStrategy.mockResolvedValue(makeRuleParseResponse());
    runRuleBacktest.mockResolvedValue(makeRuleRunResponse());
    getRuleBacktestRuns.mockResolvedValue({
      total: 0,
      page: 1,
      limit: 10,
      items: [],
    });
    getRuleBacktestRun.mockResolvedValue(
      makeRuleRunResponse({
        status: 'completed',
        statusMessage: '规则回测已完成，可查看交易明细与执行假设。',
        completedAt: '2026-04-07T08:02:00Z',
        statusHistory: [
          { status: 'queued', at: '2026-04-07T08:00:00Z' },
          { status: 'running', at: '2026-04-07T08:00:30Z' },
          { status: 'summarizing', at: '2026-04-07T08:01:30Z' },
          { status: 'completed', at: '2026-04-07T08:02:00Z' },
        ],
        tradeCount: 2,
        winCount: 1,
        lossCount: 1,
        totalReturnPct: 8.5,
        annualizedReturnPct: 12.4,
        benchmarkMode: 'auto',
        benchmarkCode: null,
        benchmarkReturnPct: 6.4,
        excessReturnVsBenchmarkPct: 2.1,
        buyAndHoldReturnPct: 5.2,
        excessReturnVsBuyAndHoldPct: 3.3,
        winRatePct: 50,
        avgTradeReturnPct: 4.25,
        maxDrawdownPct: 3.2,
        avgHoldingDays: 6,
        avgHoldingBars: 5.5,
        avgHoldingCalendarDays: 6,
        finalEquity: 108500,
        aiSummary: '该策略相对 buy-and-hold 取得了正向超额收益，但交易样本仍然较少。',
        equityCurve: [
          { date: '2026-03-01', equity: 100000, cumulativeReturnPct: 0, drawdownPct: 0 },
          { date: '2026-03-10', equity: 103200, cumulativeReturnPct: 3.2, drawdownPct: -1.1 },
          { date: '2026-03-18', equity: 108500, cumulativeReturnPct: 8.5, drawdownPct: 0 },
        ],
        benchmarkCurve: [
          { date: '2026-03-01', close: 100, normalizedValue: 1, cumulativeReturnPct: 0 },
          { date: '2026-03-10', close: 103.1, normalizedValue: 1.031, cumulativeReturnPct: 3.1 },
          { date: '2026-03-18', close: 106.4, normalizedValue: 1.064, cumulativeReturnPct: 6.4 },
        ],
        benchmarkSummary: {
          label: 'QQQ',
          requestedMode: 'auto',
          resolvedMode: 'etf_qqq',
          code: 'QQQ',
          autoResolved: true,
          method: 'benchmark_security',
          priceBasis: 'close',
          startDate: '2026-03-01',
          endDate: '2026-03-18',
          startPrice: 100,
          endPrice: 106.4,
          returnPct: 6.4,
        },
        buyAndHoldCurve: [
          { date: '2026-03-01', close: 100, normalizedValue: 1, cumulativeReturnPct: 0 },
          { date: '2026-03-10', close: 102, normalizedValue: 1.02, cumulativeReturnPct: 2 },
          { date: '2026-03-18', close: 105.2, normalizedValue: 1.052, cumulativeReturnPct: 5.2 },
        ],
        buyAndHoldSummary: {
          label: bt('zh', 'resultPage.buyAndHoldDefault'),
          requestedMode: 'same_symbol_buy_and_hold',
          resolvedMode: 'same_symbol_buy_and_hold',
          method: 'same_symbol_buy_and_hold',
          priceBasis: 'close',
          startDate: '2026-03-01',
          endDate: '2026-03-18',
          startPrice: 100,
          endPrice: 105.2,
          returnPct: 5.2,
        },
        auditRows: [
          {
            date: '2026-03-01',
            symbolClose: 100,
            benchmarkClose: 100,
            signalSummary: '等待开仓信号',
            targetPosition: 0,
            executedAction: null,
            fillPrice: null,
            sharesHeld: 0,
            cash: 100000,
            holdingsValue: 0,
            totalPortfolioValue: 100000,
            dailyPnl: 0,
            dailyReturnPct: 0,
            cumulativeStrategyReturnPct: 0,
            cumulativeBenchmarkReturnPct: 0,
            cumulativeBuyAndHoldReturnPct: 0,
            fees: 0,
            slippage: 0,
            notes: null,
            unavailableReason: null,
          },
          {
            date: '2026-03-10',
            symbolClose: 102,
            benchmarkClose: 103.1,
            signalSummary: 'MA5 > MA20',
            targetPosition: 1,
            executedAction: 'buy',
            fillPrice: 100,
            sharesHeld: 1000,
            cash: 3200,
            holdingsValue: 100000,
            totalPortfolioValue: 103200,
            dailyPnl: 3200,
            dailyReturnPct: 3.2,
            cumulativeStrategyReturnPct: 3.2,
            cumulativeBenchmarkReturnPct: 3.1,
            cumulativeBuyAndHoldReturnPct: 2,
            fees: 0,
            slippage: 0,
            notes: null,
            unavailableReason: null,
          },
          {
            date: '2026-03-18',
            symbolClose: 105.2,
            benchmarkClose: 106.4,
            signalSummary: 'RSI6 > 70',
            targetPosition: 0,
            executedAction: 'sell',
            fillPrice: 106,
            sharesHeld: 0,
            cash: 108500,
            holdingsValue: 0,
            totalPortfolioValue: 108500,
            dailyPnl: 5300,
            dailyReturnPct: 5.135659,
            cumulativeStrategyReturnPct: 8.5,
            cumulativeBenchmarkReturnPct: 6.4,
            cumulativeBuyAndHoldReturnPct: 5.2,
            fees: 0,
            slippage: 0,
            notes: null,
            unavailableReason: null,
          },
        ],
        dailyReturnSeries: [
          { date: '2026-03-01', equity: 100000, dailyReturnPct: 0, dailyPnl: 0 },
          { date: '2026-03-10', equity: 103200, dailyReturnPct: 3.2, dailyPnl: 3200 },
          { date: '2026-03-18', equity: 108500, dailyReturnPct: 5.135659, dailyPnl: 5300 },
        ],
        exposureCurve: [
          { date: '2026-03-01', exposure: 0, positionState: 'flat' },
          { date: '2026-03-10', exposure: 1, positionState: 'long' },
          { date: '2026-03-18', exposure: 0, positionState: 'flat' },
        ],
        trades: [
          {
            code: 'ORCL',
            entryDate: '2026-03-03',
            exitDate: '2026-03-07',
            entrySignalDate: '2026-03-02',
            exitSignalDate: '2026-03-06',
            entryPrice: 100,
            exitPrice: 106,
            entrySignal: '买入条件：MA5 > MA20 且 RSI6 < 40',
            exitSignal: '卖出条件：MA5 < MA20 或 RSI6 > 70',
            entryTrigger: 'MA5 > MA20',
            exitTrigger: 'RSI6 > 70',
            returnPct: 6,
            holdingDays: 5,
            holdingBars: 4,
            holdingCalendarDays: 5,
            entryRule: makeRuleParseResponse().parsedStrategy.entry,
            exitRule: makeRuleParseResponse().parsedStrategy.exit,
            entryIndicators: { ma5: 101.1, ma20: 99.3 },
            exitIndicators: { rsi6: 72.4 },
            entryFillBasis: 'next_bar_open',
            exitFillBasis: 'next_bar_open',
            signalPriceBasis: 'close',
            priceBasis: 'close',
            feeBps: 0,
            slippageBps: 0,
            entryFeeAmount: 0,
            exitFeeAmount: 0,
            entrySlippageAmount: 0,
            exitSlippageAmount: 0,
            notes: null,
          },
        ],
      }),
    );
    getRuleBacktestRunStatus.mockResolvedValue({
      id: 99,
      code: 'ORCL',
      status: 'completed',
      statusMessage: '规则回测已完成，可查看交易明细与执行假设。',
      statusHistory: [
        { status: 'queued', at: '2026-04-07T08:00:00Z' },
        { status: 'running', at: '2026-04-07T08:00:30Z' },
        { status: 'summarizing', at: '2026-04-07T08:01:30Z' },
        { status: 'completed', at: '2026-04-07T08:02:00Z' },
      ],
      runAt: '2026-04-07T08:00:00Z',
      completedAt: '2026-04-07T08:02:00Z',
      noResultReason: null,
      noResultMessage: null,
      tradeCount: 2,
      parsedConfidence: 0.97,
      needsConfirmation: true,
    });
    cancelRuleBacktestRun.mockResolvedValue({
      id: 99,
      code: 'ORCL',
      status: 'cancelled',
      statusMessage: '规则回测已取消。',
      statusHistory: [
        { status: 'queued', at: '2026-04-07T08:00:00Z' },
        { status: 'cancelled', at: '2026-04-07T08:00:45Z' },
      ],
      runAt: '2026-04-07T08:00:00Z',
      completedAt: '2026-04-07T08:00:45Z',
      noResultReason: 'cancelled',
      noResultMessage: '规则回测已取消。',
      tradeCount: 0,
      parsedConfidence: 0.97,
      needsConfirmation: true,
    });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('defaults to the point-and-shoot normal workspace', async () => {
    renderBacktestRoutes();

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    const pageShell = screen.getByTestId('backtest-page-shell');

    expect(screen.getByTestId('backtest-bento-page')).toHaveClass('w-full', 'flex-1', 'min-w-0', 'min-h-0', 'bg-transparent');
    expect(screen.getByTestId('backtest-bento-page')).not.toHaveClass('px-6', 'md:px-8', 'xl:px-12', 'pt-6', 'pb-12', 'max-w-[1600px]');
    expect(screen.getByTestId('backtest-bento-page')).not.toHaveClass('container', 'mx-auto', 'max-w-[1600px]');
    expect(pageShell).toHaveClass(
      'w-full',
      '[--wolfy-consumer-shell-max:1880px]',
      'max-w-[var(--wolfy-consumer-shell-max,1880px)]',
      'mx-auto',
      'px-4',
      'xl:px-8',
      'flex',
      'flex-col',
      'gap-5',
    );
    expect(pageShell).not.toHaveClass('max-w-none', 'mx-0', 'px-0', 'xl:px-0', 'max-w-[1600px]');
    expect(pageShell).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(screen.getByTestId('backtest-subnav')).toHaveClass('w-full', 'rounded-[24px]', 'border', 'border-white/5', 'bg-white/[0.02]');
    expect(screen.getByTestId('backtest-v1-page')).toHaveClass('w-full', 'flex-1', 'min-w-0', 'flex', 'flex-col', 'gap-6', 'bg-transparent');
    expect(screen.getByTestId('backtest-v1-page')).not.toHaveClass('pt-6');
    expect(screen.getByRole('tab', { name: bt('zh', 'page.ruleTab') })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: bt('zh', 'page.historicalTab') })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: bt('zh', 'page.normalMode') })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: bt('zh', 'page.professionalMode') })).toHaveAttribute('aria-selected', 'false');

    expect(await screen.findByTestId('normal-backtest-workspace')).toBeInTheDocument();
    expect(screen.queryByTestId('pro-backtest-workspace')).not.toBeInTheDocument();
    expect(screen.getByTestId('normal-backtest-consolidated-card')).toBeInTheDocument();
    expect(screen.getByTestId('normal-backtest-form-grid')).toHaveClass('grid', 'md:grid-cols-4');
    expect(screen.getByLabelText('标的代码')).toBeInTheDocument();
    expect(screen.getByLabelText('回测区间开始')).toBeInTheDocument();
    expect(screen.getByLabelText('回测区间结束')).toBeInTheDocument();
    expect(screen.getByLabelText('初始资金')).toBeInTheDocument();
    expect(screen.getByLabelText('对比基准')).toHaveClass('min-h-[44px]', 'leading-6');
    expect(screen.getByLabelText('滑点')).toBeInTheDocument();
    expect(screen.getByLabelText('手续费 (bp)')).toBeInTheDocument();
    expect(screen.getByLabelText('策略模板')).toHaveClass('min-h-[44px]', 'leading-6');
    expect(screen.queryByLabelText('策略文本')).not.toBeInTheDocument();
    const researchBoundary = screen.getByTestId('backtest-research-boundary');
    expect(researchBoundary).toHaveTextContent('本工具仅用于回测分析与学习研究');
    expect(researchBoundary).toHaveTextContent('不构成投资建议');
    expect(researchBoundary).toHaveTextContent('过往表现不代表未来收益');
    expect(researchBoundary).toHaveTextContent('页面中的买入/卖出仅表示历史规则事件，不会提交订单、不会连接券商或改动组合持仓');
    expect(pageShell).not.toHaveTextContent(/立即交易|连接经纪商|真实下单|AI recommends you buy|must buy|must sell|buy now|sell now|place order|submit order|connect broker/i);
    expect(await screen.findByText('模板仅用于研究模拟，不构成交易建议。')).toBeInTheDocument();
    expect(await screen.findByText('回测规则预览')).toBeInTheDocument();
    expect(screen.getByText('普通模式会先把模板整理为固定规则回测流程，再跳转到独立结果页。')).toBeInTheDocument();
    expect(screen.queryByText('编译预览')).not.toBeInTheDocument();
    expect(screen.queryByText('确定性规则链路')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '执行回测任务' })).toHaveClass('bg-emerald-500/10', 'text-emerald-400', 'rounded-lg');
  });

  it('renders exactly one compact semantic backtest page heading without internal terms', async () => {
    renderBacktestRoutes(['/zh/backtest']);

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    const heading = screen.getByRole('heading', { level: 1, name: '回测' });
    expect(heading).toHaveClass('text-xl', 'md:text-2xl');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.queryByText(/provider_timeout|MarketCache|generatedCandidates|failedCandidates/i)).not.toBeInTheDocument();
  });

  it('includes every engine-supported classic strategy in point-and-shoot mode', async () => {
    renderBacktestRoutes();

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));
    expect(await screen.findByTestId('normal-backtest-workspace')).toBeInTheDocument();

    const templateSelect = screen.getByLabelText('策略模板');
    const optionLabels = within(templateSelect).getAllByRole('option').map((option) => option.textContent?.trim());

    expect(optionLabels).toEqual([
      'MACD 金叉 / 死叉',
      '均线交叉（SMA / EMA）',
      'RSI 超买 / 超卖',
      '定投策略',
      '布林带突破',
      '支撑 / 阻力反弹',
      'ATR 波动突破',
      'OBV 趋势确认',
      'MACD + RSI 共振',
      'SMA + 布林带组合',
      '趋势 + 动量 + 量能混合',
      '多指标趋势过滤',
      '布林带 + RSI 回归组合',
      '三重均线趋势栈',
      '支撑阻力 + MACD 组合',
      'VWAP + 放量突破组合',
    ]);
    expect(optionLabels).not.toContain('自定义代码');
  });

  it('prefills the symbol when navigated from scanner context', async () => {
    renderBacktestRoutes([{ pathname: '/backtest', state: { prefillCode: '600001', prefillName: '算力龙头' } }]);

    expect(await screen.findByDisplayValue('600001')).toBeInTheDocument();
  });

  it('prefills the symbol from scanner query params and shows scanner handoff context', async () => {
    renderBacktestRoutes(['/backtest?symbol=msft&market=US&source=scanner&scannerRunId=42&scannerRank=1&scannerProfile=us_preopen_v1']);

    expect(await screen.findByDisplayValue('MSFT')).toBeInTheDocument();
    expect(screen.getByText(/来自扫描器|From scanner/i)).toBeInTheDocument();
    expect(screen.getAllByText(/MSFT/).length).toBeGreaterThan(0);
    expect(screen.getByText(/扫描批次 #42/)).toBeInTheDocument();
    expect(screen.getByText(/排名 #1/)).toBeInTheDocument();
  });

  it('ignores invalid scanner query params without crashing', async () => {
    renderBacktestRoutes(['/backtest?symbol=%20%20&market=%3F%3F&source=scanner&scannerRank=abc']);

    expect(await screen.findByTestId('backtest-v1-page')).toBeInTheDocument();
    expect(screen.getByLabelText('标的代码')).toHaveValue('');
    expect(screen.queryByText(/来自扫描器|From scanner/i)).not.toBeInTheDocument();
  });

  it('renders the deterministic professional workspace shell', async () => {
    renderBacktestRoutes();

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    expect(screen.getByTestId('normal-backtest-workspace')).toBeInTheDocument();
    expect(screen.getByTestId('normal-backtest-consolidated-card')).toBeInTheDocument();
    expect(screen.getByTestId('normal-backtest-form-grid')).toHaveClass('grid', 'md:grid-cols-4');
    expect(screen.getByTestId('normal-backtest-cta-row')).toBeInTheDocument();
    expect(screen.queryByTestId('pro-backtest-workspace')).not.toBeInTheDocument();

    await switchToProfessionalMode();

    expect(screen.getByRole('tab', { name: bt('zh', 'page.professionalMode') })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByTestId('pro-backtest-workspace')).toHaveClass('w-full', 'pb-12');
    expect(screen.getByTestId('pro-backtest-workspace')).not.toHaveClass('max-w-[1680px]', 'mx-auto');
    expect(screen.getByTestId('pro-workflow-rail')).toHaveClass('hidden', 'lg:flex', 'lg:sticky');
    expect(screen.getByTestId('pro-mobile-step-chips')).toHaveClass('lg:hidden', 'overflow-x-auto', 'no-scrollbar');
    expect(screen.getByTestId('pro-workspace-grid')).toHaveClass('lg:grid-cols-[220px_minmax(0,1fr)_320px]');
    expect(screen.getByTestId('pro-step-workspace')).toBeInTheDocument();
    expect(screen.getByTestId('pro-execution-rail')).toHaveClass('lg:sticky', 'lg:top-6');
    expect(screen.getByTestId('pro-results-history-drawer')).toBeInTheDocument();
    expect(screen.getByTestId('pro-results-history-content')).toHaveAttribute('hidden');
    expect(within(screen.getByTestId('pro-workflow-rail')).getAllByRole('button')).toHaveLength(5);
    expect(screen.getByTestId('pro-step-assets')).toBeInTheDocument();
    expect(screen.queryByTestId('pro-step-strategy')).not.toBeInTheDocument();
    expect(screen.getByLabelText('标的代码')).toBeInTheDocument();
    expect(screen.getByLabelText('对比基准')).toBeInTheDocument();
    expect(screen.getByLabelText('开始日期')).toBeInTheDocument();
    expect(screen.getByLabelText('结束日期')).toBeInTheDocument();
    expect(screen.getByLabelText('初始资金')).toBeInTheDocument();
    expect(within(screen.getByTestId('pro-execution-rail')).getByText('执行摘要')).toBeInTheDocument();
    expect(within(screen.getByTestId('pro-execution-rail')).getByText('就绪度')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: '执行回测任务' }).length).toBeGreaterThan(0);
    expect(screen.queryByTestId('deterministic-backtest-chart-workspace')).not.toBeInTheDocument();
  });

  it('opens the strategy catalog drawer in professional mode and keeps unsupported templates marked inside it', async () => {
    renderBacktestRoutes();

    await switchToProfessionalMode();

    expect(screen.queryByTestId('pro-strategy-catalog')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('pro-workflow-step-strategy'));
    fireEvent.click(screen.getByTestId('pro-open-template-drawer'));
    expect(await screen.findByTestId('pro-strategy-catalog-drawer')).toBeInTheDocument();
    const catalog = screen.getByTestId('pro-strategy-catalog');
    expect(catalog).toBeInTheDocument();
    expect(screen.getByText('一次只浏览一个类别，选中后可带回编辑器继续研究。')).toBeInTheDocument();
    expect(screen.getAllByText('基础 / 默认策略').length).toBeGreaterThan(0);
    expect(within(catalog).getByText('均线交叉（SMA / EMA）')).toBeInTheDocument();
    expect(within(catalog).getAllByText('可执行').length).toBeGreaterThan(0);
    expect(within(catalog).getAllByText('该模板可直接用于当前固定规则回测流程。').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: '进阶 / 扩展策略' }));
    expect(screen.getByText('简单动量')).toBeInTheDocument();
    expect(screen.getAllByText('当前不支持').length).toBeGreaterThan(0);
  });

  it('loads unsupported reference templates into the editor and shows the direct-run warning', async () => {
    renderBacktestRoutes();

    await openDeterministicStrategyInput();
    await clickAndFlush(screen.getByTestId('pro-open-template-drawer'));
    expect(await screen.findByTestId('pro-strategy-catalog-drawer')).toBeInTheDocument();
    await clickAndFlush(screen.getByRole('button', { name: '进阶 / 扩展策略' }));

    const referenceTemplateCard = screen.getByText('简单动量').closest('article');
    expect(referenceTemplateCard).not.toBeNull();

    await clickAndFlush(within(referenceTemplateCard as HTMLElement).getByRole('button', { name: '载入参考模板' }));
    await waitFor(() => {
      expect(screen.queryByTestId('pro-strategy-catalog-drawer')).not.toBeInTheDocument();
    });

    expect(await screen.findByTestId('pro-strategy-catalog-toast')).toHaveTextContent('当前模板暂不支持直接运行，请在编辑器中修改后再执行');
    expect(screen.getByDisplayValue('近20日涨幅转正并创新高买入，跌破10日低点卖出')).toBeInTheDocument();
  });

  it('loads executable catalog templates without showing the unsupported warning', async () => {
    renderBacktestRoutes();

    await openDeterministicStrategyInput();
    await clickAndFlush(screen.getByTestId('pro-open-template-drawer'));
    expect(await screen.findByTestId('pro-strategy-catalog-drawer')).toBeInTheDocument();

    const executableTemplateCard = within(screen.getByTestId('pro-strategy-catalog')).getByText('MACD 金叉 / 死叉').closest('article');
    expect(executableTemplateCard).not.toBeNull();

    await clickAndFlush(within(executableTemplateCard as HTMLElement).getByRole('button', { name: '填入编辑器' }));
    await flushPendingUiWork();
    await waitFor(() => {
      expect(screen.queryByTestId('pro-strategy-catalog-drawer')).not.toBeInTheDocument();
    });

    expect(screen.queryByTestId('pro-strategy-catalog-toast')).not.toBeInTheDocument();
    expect(screen.getByDisplayValue('MACD 金叉买入，死叉卖出')).toBeInTheDocument();
  });

  it('switches the professional workspace through one active step at a time', async () => {
    renderBacktestRoutes();

    await switchToProfessionalMode();

    expect(screen.getByTestId('pro-step-assets')).toBeInTheDocument();
    expect(screen.queryByTestId('pro-step-strategy')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('pro-workflow-step-strategy'));
    expect(await screen.findByTestId('pro-step-strategy')).toBeInTheDocument();
    expect(screen.getByLabelText('策略文本')).toBeInTheDocument();
    expect(screen.getByTestId('pro-rule-preview')).toBeInTheDocument();
    expect(screen.queryByTestId('pro-step-assets')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('pro-workflow-step-orders'));
    expect(await screen.findByTestId('pro-step-orders')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '执行路由' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '风险护栏' })).toBeInTheDocument();
    expect(screen.queryByTestId('pro-step-strategy')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('pro-workflow-step-costs'));
    expect(await screen.findByTestId('pro-step-costs')).toBeInTheDocument();
    expect(screen.getByLabelText('回看范围')).toBeInTheDocument();
    expect(screen.getByLabelText('手续费 BP')).toBeInTheDocument();
    expect(screen.getByLabelText('滑点 BP')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('pro-workflow-step-advanced'));
    expect(await screen.findByTestId('pro-step-advanced')).toBeInTheDocument();
    expect(screen.getByText('当前能力说明')).toBeInTheDocument();
    expect(screen.getByText('网格搜索（计划中）')).toBeInTheDocument();
    expect(screen.getByText('贝叶斯搜索（计划中）')).toBeInTheDocument();
    expect(screen.queryByLabelText('启用网格搜索')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('启用贝叶斯搜索')).not.toBeInTheDocument();
    expect(screen.queryByText('Grid Search')).not.toBeInTheDocument();
    expect(screen.queryByText('Bayesian Search')).not.toBeInTheDocument();
    expect(screen.queryByText('为什么改成折叠')).not.toBeInTheDocument();
    expect(screen.queryByText('执行通道说明')).not.toBeInTheDocument();
    expect(screen.queryByText('控制策略')).not.toBeInTheDocument();
  });

  it('truth-labels non-wired professional controls instead of presenting them as executable toggles', async () => {
    renderBacktestRoutes();

    await switchToProfessionalMode();

    expect(screen.getByText('高级组合设置（计划中）')).toBeInTheDocument();
    fireEvent.click(screen.getByText('高级组合设置（计划中）'));
    expect(await screen.findByText('组合壳层')).toBeInTheDocument();
    expect(screen.getByText('计划中，尚未接入当前回测执行。')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('pro-workflow-step-orders'));
    const ordersStep = await screen.findByTestId('pro-step-orders');
    expect(within(ordersStep).getByText('执行路由覆盖（计划中）')).toBeInTheDocument();
    expect(within(ordersStep).queryByLabelText('事件驱动执行')).not.toBeInTheDocument();
    expect(within(ordersStep).queryByLabelText('止损路由')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('pro-workflow-step-advanced'));
    const advancedStep = await screen.findByTestId('pro-step-advanced');
    expect(within(advancedStep).getByText('网格搜索（计划中）')).toBeInTheDocument();
    expect(within(advancedStep).getByText('贝叶斯搜索（计划中）')).toBeInTheDocument();
    expect(within(advancedStep).queryByLabelText('启用网格搜索')).not.toBeInTheDocument();
    expect(within(advancedStep).queryByLabelText('启用贝叶斯搜索')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '稳健性' }));
    expect(within(advancedStep).getByText('Monte Carlo 稳健性诊断')).toBeInTheDocument();
    expect(within(advancedStep).getByText('滚动样本外稳健性预设')).toBeInTheDocument();
    const robustnessSummary = within(advancedStep).getByTestId('pro-robustness-selection-summary');
    expect(within(robustnessSummary).getByText('将随本次专业回测提交的诊断配置')).toBeInTheDocument();
    expect(within(robustnessSummary).getByText('本次不附加额外稳健性诊断')).toBeInTheDocument();
    expect(within(advancedStep).getByLabelText('启用 Monte Carlo 稳健性诊断')).not.toBeChecked();
    expect(within(advancedStep).getByLabelText('启用滚动样本外稳健性预设')).not.toBeChecked();
    expect(within(advancedStep).queryByLabelText('Monte Carlo 仿真次数')).not.toBeInTheDocument();
    expect(within(advancedStep).queryByText('24 / 12 / 12 / 4')).not.toBeInTheDocument();
    expect(within(advancedStep).queryByText(/seed/i)).not.toBeInTheDocument();
    expect(within(advancedStep).queryByText(/noise\s*scale/i)).not.toBeInTheDocument();
    expect(within(advancedStep).queryByLabelText(/训练窗口/i)).not.toBeInTheDocument();
    expect(within(advancedStep).queryByLabelText(/测试窗口/i)).not.toBeInTheDocument();
    expect(within(advancedStep).queryByLabelText(/^步长$/i)).not.toBeInTheDocument();
    expect(within(advancedStep).queryByLabelText(/最大窗口/i)).not.toBeInTheDocument();

    fireEvent.click(within(advancedStep).getByText('Monte Carlo 稳健性诊断'));
    expect(await within(advancedStep).findByLabelText('启用 Monte Carlo 稳健性诊断')).toBeInTheDocument();
    expect(within(advancedStep).queryByLabelText('Monte Carlo 仿真次数')).not.toBeInTheDocument();

    fireEvent.click(within(advancedStep).getByText('滚动样本外稳健性预设'));
    expect(await within(advancedStep).findByLabelText('启用滚动样本外稳健性预设')).toBeInTheDocument();
    expect(within(advancedStep).queryByText('24 / 12 / 12 / 4')).not.toBeInTheDocument();

    expect(screen.getAllByRole('button', { name: '执行回测任务' }).length).toBeGreaterThan(0);
  });

  it('summarizes professional robustness selections without exposing hidden diagnostics', async () => {
    renderBacktestRoutes();

    await parseDeterministicStrategy();

    fireEvent.click(screen.getByTestId('pro-workflow-step-advanced'));

    const advancedStep = await screen.findByTestId('pro-step-advanced');
    fireEvent.click(within(advancedStep).getByRole('button', { name: '稳健性' }));

    const summary = within(advancedStep).getByTestId('pro-robustness-selection-summary');
    expect(within(summary).getByText('本次不附加额外稳健性诊断')).toBeInTheDocument();
    expect(within(summary).queryByText(/seed/i)).not.toBeInTheDocument();
    expect(within(summary).queryByText(/noise\s*scale/i)).not.toBeInTheDocument();
    expect(within(summary).queryByText(/24 \/ 12 \/ 12 \/ 4/i)).not.toBeInTheDocument();

    fireEvent.click(within(advancedStep).getByText('Monte Carlo 稳健性诊断'));
    fireEvent.click(await within(advancedStep).findByLabelText('启用 Monte Carlo 稳健性诊断'));

    expect(within(summary).queryByText('本次不附加额外稳健性诊断')).not.toBeInTheDocument();
    expect(within(summary).getByText('Monte Carlo · 12 次仿真')).toBeInTheDocument();

    const simulationCountInput = await within(advancedStep).findByLabelText('Monte Carlo 仿真次数');
    fireEvent.change(simulationCountInput, { target: { value: '24' } });
    expect(within(summary).getByText('Monte Carlo · 24 次仿真')).toBeInTheDocument();

    fireEvent.click(within(advancedStep).getByText('滚动样本外稳健性预设'));
    fireEvent.click(await within(advancedStep).findByLabelText('启用滚动样本外稳健性预设'));

    expect(within(summary).getByText('Monte Carlo · 24 次仿真')).toBeInTheDocument();
    expect(within(summary).getByText('滚动样本外 · 固定窗口预设')).toBeInTheDocument();

    fireEvent.click(within(advancedStep).getByLabelText('启用 Monte Carlo 稳健性诊断'));
    expect(within(summary).queryByText('Monte Carlo · 24 次仿真')).not.toBeInTheDocument();
    expect(within(summary).getByText('滚动样本外 · 固定窗口预设')).toBeInTheDocument();
  });

  it('marks parsed strategy stale after setup changes', async () => {
    renderBacktestRoutes();

    await parseDeterministicStrategy();
    expect(screen.getByText('策略已解析')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('pro-workflow-step-assets'));
    fireEvent.change(screen.getByLabelText('结束日期'), { target: { value: '2025-11-30' } });
    await waitFor(() => expect(screen.getAllByText('输入已变更，请重新解析').length).toBeGreaterThan(0));
  });

  it('shows unsupported guidance and applies rewrite suggestions', async () => {
    parseRuleStrategy.mockResolvedValueOnce(makeUnsupportedMacdParseResponse());

    renderBacktestRoutes();

    await openDeterministicStrategyInput();
    fireEvent.change(screen.getByLabelText('策略文本'), { target: { value: 'MACD金叉买入，止损5%，死叉卖出' } });
    fireEvent.click(within(screen.getByTestId('pro-step-strategy')).getByRole('button', { name: '解析策略' }));

    const guidanceSection = await screen.findByTestId('pro-unsupported-guidance');
    const assumptionsSection = screen.getByTestId('pro-assumption-summary');
    expect(screen.getAllByText('当前不支持').length).toBeGreaterThan(0);
    expect(within(assumptionsSection).getByText('未显式写出 MACD 参数，当前默认使用 (12, 26, 9)。')).toBeInTheDocument();

    fireEvent.click(within(guidanceSection).getByRole('button', {
      name: /改写成当前可执行版本:\s*AAPL，MACD金叉买入，死叉卖出/i,
    }));

    expect(await screen.findByText('已应用建议改写')).toBeInTheDocument();
    expect(screen.getByDisplayValue('AAPL，MACD金叉买入，死叉卖出')).toBeInTheDocument();
  });

  it('keeps parse confirmation and history entry on the configuration page without embedding result analysis', async () => {
    renderBacktestRoutes();

    await parseDeterministicStrategy();

    expect(screen.getByTestId('pro-rule-preview')).toBeInTheDocument();
    const executableSpecSection = screen.getByTestId('pro-parsed-summary');
    expect(executableSpecSection).toBeInTheDocument();
    expect(within(executableSpecSection).getByText('实际执行内容')).toBeInTheDocument();
    expect(within(executableSpecSection).getByText('每个交易日')).toBeInTheDocument();
    expect(within(executableSpecSection).getByText('100 股 / 次')).toBeInTheDocument();
    expect(await screen.findByTestId('pro-assumption-summary')).toBeInTheDocument();
    expect(screen.queryByTestId('backtest-display-board')).not.toBeInTheDocument();
    expect(screen.getAllByLabelText(/我已确认当前解析结果与执行假设/i)).toHaveLength(1);
    expect(screen.queryByTestId('deterministic-backtest-chart-workspace')).not.toBeInTheDocument();
  });

  it('renders indicator risk controls in the confirmation panel when strategy_spec exposes them', async () => {
    renderBacktestRoutes();

    await parseDeterministicStrategy();

    fireEvent.click(screen.getByTestId('pro-workflow-step-orders'));
    const riskSection = await screen.findByTestId('pro-risk-controls-summary');
    expect(within(riskSection).getByText('止损')).toBeInTheDocument();
    expect(within(riskSection).getByText('5.00%')).toBeInTheDocument();
    expect(within(riskSection).getByText('止盈')).toBeInTheDocument();
    expect(within(riskSection).getByText('10.00%')).toBeInTheDocument();
    expect(within(riskSection).getByText('移动止损')).toBeInTheDocument();
    expect(within(riskSection).getByText('8.00%')).toBeInTheDocument();
  });

  it('marks executable spec fields as compatibility-derived when only legacy setup is available', async () => {
    parseRuleStrategy.mockResolvedValueOnce(makeLegacySetupOnlyParseResponse());

    renderBacktestRoutes();

    await parseDeterministicStrategy();

    const executableSpecSection = screen.getByTestId('pro-parsed-summary');
    expect(await within(executableSpecSection).findByText('规格来源 · 兼容 setup')).toBeInTheDocument();
  });

  it('keeps historical evaluation functional across Normal and Professional modes', async () => {
    renderBacktestRoutes();

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('tab', { name: '历史评估' }));

    const unifiedShell = await screen.findByTestId('backtest-unified-shell');
    expect(unifiedShell).toHaveAttribute('data-module', 'historical');
    expect(screen.getByRole('tab', { name: bt('zh', 'page.normalMode') })).toHaveAttribute('aria-selected', 'true');

    const controlPanel = screen.getByTestId('backtest-control-panel');
    const inspectionPanel = screen.getByTestId('historical-inspection-panel');
    const displayBoard = screen.getByTestId('backtest-display-board');
    expect(screen.getByTestId('backtest-control-window')).toBeInTheDocument();
    expect(unifiedShell).not.toHaveClass('h-full', 'min-h-0', 'overflow-hidden');
    expect(controlPanel).toHaveClass('col-span-1', 'lg:col-span-3', 'w-full', 'min-w-0', 'flex', 'flex-col', 'gap-4');
    expect(controlPanel).not.toHaveClass('h-full', 'min-h-0', 'overflow-y-auto', 'no-scrollbar');
    expect(inspectionPanel).toHaveClass('col-span-1', 'lg:col-span-4', 'w-full', 'min-w-0', 'flex', 'flex-col', 'gap-4');
    expect(displayBoard).toHaveClass('col-span-1', 'lg:col-span-5', 'w-full', 'min-w-0', 'flex', 'flex-col', 'gap-4');
    expect(displayBoard).not.toHaveClass('h-full', 'min-h-0', 'overflow-y-auto', 'no-scrollbar');

    expect(within(screen.getByTestId('historical-control-section-scope-samples')).getByText('范围与样本')).toBeInTheDocument();
    expect(screen.queryByTestId('historical-control-section-params')).not.toBeInTheDocument();
    expect(screen.queryByTestId('historical-control-section-execute')).not.toBeInTheDocument();
    expect(screen.queryByTestId('historical-control-section-results')).not.toBeInTheDocument();

    expect(within(displayBoard).getByText('评估概览')).toBeInTheDocument();
    expect(within(displayBoard).getByText('评估结果')).toBeInTheDocument();
    expect(within(displayBoard).getByText('历史记录')).toBeInTheDocument();
    expect(within(inspectionPanel).getByText('历史评估显示面板')).toBeInTheDocument();
    expect(within(displayBoard).queryByRole('button', { name: '运行历史评估' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: bt('zh', 'page.professionalMode') }));
    expect(controlPanel).toHaveClass('lg:col-span-12');
    expect(inspectionPanel).toHaveClass('lg:col-span-5');
    expect(displayBoard).toHaveClass('lg:col-span-7');
    expect(screen.getByTestId('backtest-control-panel-expanded')).toHaveClass('backtest-control-panel__stack--professional');
    expect(within(controlPanel).getByTestId('historical-control-section-scope-samples')).toBeInTheDocument();
    expect(within(controlPanel).getByTestId('historical-control-section-params')).toBeInTheDocument();
    expect(within(controlPanel).getByTestId('historical-control-section-execute')).toBeInTheDocument();
    expect(within(controlPanel).getByTestId('historical-control-section-results')).toBeInTheDocument();
  });

  it('keeps professional deterministic controls scoped to the active step', async () => {
    renderBacktestRoutes();

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    await switchToProfessionalMode();

    expect(screen.getByRole('tab', { name: bt('zh', 'page.professionalMode') })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByTestId('pro-backtest-workspace')).toHaveAttribute('data-module', 'rule');
    expect(screen.getByTestId('pro-step-assets')).toBeInTheDocument();
    expect(screen.queryByTestId('pro-step-strategy')).not.toBeInTheDocument();
    expect(screen.queryByTestId('pro-step-orders')).not.toBeInTheDocument();
    expect(screen.queryByTestId('pro-step-costs')).not.toBeInTheDocument();
    expect(screen.queryByTestId('pro-step-advanced')).not.toBeInTheDocument();
    expect(screen.getByTestId('pro-execution-readiness')).toBeInTheDocument();
    expect(screen.queryByTestId('deterministic-backtest-chart-workspace')).not.toBeInTheDocument();
  });

  it('launches deterministic backtests into the dedicated result page flow', async () => {
    runRuleBacktest.mockResolvedValueOnce(makeRuleRunResponse({
      status: 'completed',
      completedAt: '2026-04-07T08:02:00Z',
      statusMessage: '规则回测已完成。',
      tradeCount: 1,
    }));

    renderBacktestRoutes();

    await parseDeterministicStrategy();

    fireEvent.click(screen.getByLabelText(/我已确认当前解析结果与执行假设/i));
    fireEvent.click(within(screen.getByTestId('pro-execution-rail')).getByRole('button', { name: '执行回测任务' }));

    expect(runRuleBacktest).toHaveBeenCalledTimes(1);
    const payload = vi.mocked(runRuleBacktest).mock.calls[0]?.[0];
    expect(payload).toEqual(expect.objectContaining({
      code: 'ORCL',
      startDate: '2025-01-01',
      endDate: '2025-12-31',
      benchmarkMode: 'auto',
      waitForCompletion: false,
      confirmed: true,
    }));
    expect(payload).not.toHaveProperty('robustnessConfig');

    expect(await screen.findByTestId('deterministic-backtest-result-page')).toBeInTheDocument();
    expect(screen.getByTestId('deterministic-result-page-hero')).toHaveTextContent('ORCL');
    expect(screen.getByTestId('backtest-result-report')).toHaveAttribute('data-report-mode', 'professional');
    expect(screen.getByTestId('backtest-report-summary')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-readiness-chips')).toHaveTextContent('研究级回测');
    expect(screen.getByTestId('backtest-readiness-chips')).not.toHaveTextContent(/research_prototype|unknown_or_mixed|available_bars_only|professional_quant_ready/i);
    expect(screen.getByTestId('backtest-report-key-metrics')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-trade-table')).toBeInTheDocument();
    expect(await screen.findByTestId('deterministic-backtest-result-view')).toHaveAttribute('data-run-id', '99');
    expect(
      within(screen.getByTestId('deterministic-result-page-hero')).getAllByText('已完成', { selector: '[data-status="success"]' }).length,
    ).toBeGreaterThan(0);
    expect(await screen.findByTestId('deterministic-backtest-chart-workspace', undefined, { timeout: CHART_IMPORT_TIMEOUT })).toBeInTheDocument();
    expect(await screen.findByLabelText(
      bt('zh', 'resultPage.chartWorkspace.cumulativeReturnChartAria'),
      undefined,
      { timeout: CHART_IMPORT_TIMEOUT },
    )).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: bt('zh', 'resultPage.tabs.overview') })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: bt('zh', 'resultPage.tabs.audit') })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: bt('zh', 'resultPage.tabs.trades') })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: bt('zh', 'resultPage.tabs.parameters') })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: bt('zh', 'resultPage.tabs.history') })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: bt('zh', 'resultPage.tabs.audit') }));
    const auditDigest = await screen.findByTestId('deterministic-result-mobile-digest');
    expect(auditDigest).toHaveAttribute('data-digest-tab', 'audit');
    expect(auditDigest).toHaveTextContent('窄屏阅读顺序');
    expect(auditDigest).toHaveTextContent('审计行数');

    fireEvent.click(screen.getByRole('tab', { name: bt('zh', 'resultPage.tabs.trades') }));
    const tradeDigest = await screen.findByTestId('deterministic-result-mobile-digest');
    expect(tradeDigest).toHaveAttribute('data-digest-tab', 'trades');
    expect(tradeDigest).toHaveTextContent('窄屏交易速读');
    expect(tradeDigest).toHaveTextContent('交易事件');
  }, 10000);

  it('launches point-and-shoot normal mode into the shared simple result report', async () => {
    runRuleBacktest.mockResolvedValueOnce(makeRuleRunResponse({
      status: 'completed',
      completedAt: '2026-04-07T08:02:00Z',
      statusMessage: '规则回测已完成。',
      tradeCount: 1,
    }));

    renderBacktestRoutes();

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText('标的代码'), { target: { value: 'ORCL' } });
    fireEvent.click(screen.getByRole('button', { name: '执行回测任务' }));

    await waitFor(() => expect(parseRuleStrategy).toHaveBeenCalledTimes(1));
    expect(runRuleBacktest).toHaveBeenCalledTimes(1);
    expect(vi.mocked(runRuleBacktest).mock.calls[0]?.[0]).not.toHaveProperty('robustnessConfig');

    expect(await screen.findByTestId('deterministic-backtest-result-page')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-result-report')).toHaveAttribute('data-report-mode', 'simple');
    expect(screen.getByTestId('backtest-report-summary')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-key-metrics')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-chart')).toBeInTheDocument();
    expect(screen.getByTestId('backtest-report-advanced-details')).toBeInTheDocument();
    expect(screen.queryByTestId('backtest-report-ledger-table')).not.toBeInTheDocument();
  }, 10000);

  it('keeps walk-forward robustness preset disabled by default in professional mode', async () => {
    runRuleBacktest.mockResolvedValueOnce(makeRuleRunResponse({
      status: 'completed',
      completedAt: '2026-04-07T08:02:00Z',
      statusMessage: '规则回测已完成。',
      tradeCount: 1,
    }));

    renderBacktestRoutes();

    await parseDeterministicStrategy();

    fireEvent.click(screen.getByLabelText(/我已确认当前解析结果与执行假设/i));
    fireEvent.click(screen.getByTestId('pro-workflow-step-advanced'));

    const advancedStep = await screen.findByTestId('pro-step-advanced');
    fireEvent.click(within(advancedStep).getByRole('button', { name: '稳健性' }));

    fireEvent.click(within(screen.getByTestId('pro-execution-rail')).getByRole('button', { name: '执行回测任务' }));

    await waitFor(() => expect(runRuleBacktest).toHaveBeenCalledTimes(1));
    const payload = vi.mocked(runRuleBacktest).mock.calls[0]?.[0];
    expect(payload).not.toHaveProperty('robustnessConfig');
  });

  it('sends fixed walk-forward preset only when enabled in professional mode', async () => {
    runRuleBacktest.mockResolvedValueOnce(makeRuleRunResponse({
      status: 'completed',
      completedAt: '2026-04-07T08:02:00Z',
      statusMessage: '规则回测已完成。',
      tradeCount: 1,
    }));

    renderBacktestRoutes();

    await parseDeterministicStrategy();

    fireEvent.click(screen.getByLabelText(/我已确认当前解析结果与执行假设/i));
    fireEvent.click(screen.getByTestId('pro-workflow-step-advanced'));

    const advancedStep = await screen.findByTestId('pro-step-advanced');
    fireEvent.click(within(advancedStep).getByRole('button', { name: '稳健性' }));
    fireEvent.click(within(advancedStep).getByText('滚动样本外稳健性预设'));

    const toggle = await within(advancedStep).findByLabelText('启用滚动样本外稳健性预设');
    fireEvent.click(toggle);

    expect(within(advancedStep).getByText('24 / 12 / 12 / 4')).toBeInTheDocument();
    expect(within(advancedStep).getByText('固定训练窗 / 测试窗 / 步长 / 最大窗口')).toBeInTheDocument();

    fireEvent.click(within(screen.getByTestId('pro-execution-rail')).getByRole('button', { name: '执行回测任务' }));

    await waitFor(() => expect(runRuleBacktest).toHaveBeenCalledTimes(1));
    const payload = vi.mocked(runRuleBacktest).mock.calls[0]?.[0];
    expect(payload).toEqual(expect.objectContaining({
      robustnessConfig: {
        walkForward: {
          trainWindow: 24,
          testWindow: 12,
          step: 12,
          maxWindows: 4,
        },
      },
    }));
  });

  it('sends monte carlo and fixed walk-forward robustness diagnostics together when both are enabled', async () => {
    runRuleBacktest.mockResolvedValueOnce(makeRuleRunResponse({
      status: 'completed',
      completedAt: '2026-04-07T08:02:00Z',
      statusMessage: '规则回测已完成。',
      tradeCount: 1,
    }));

    renderBacktestRoutes();

    await parseDeterministicStrategy();

    fireEvent.click(screen.getByLabelText(/我已确认当前解析结果与执行假设/i));
    fireEvent.click(screen.getByTestId('pro-workflow-step-advanced'));

    const advancedStep = await screen.findByTestId('pro-step-advanced');
    fireEvent.click(within(advancedStep).getByRole('button', { name: '稳健性' }));

    fireEvent.click(within(advancedStep).getByText('Monte Carlo 稳健性诊断'));
    const monteCarloToggle = await within(advancedStep).findByLabelText('启用 Monte Carlo 稳健性诊断');
    fireEvent.click(monteCarloToggle);

    const simulationCountInput = await within(advancedStep).findByLabelText('Monte Carlo 仿真次数');
    expect(simulationCountInput).toHaveValue(12);

    fireEvent.change(simulationCountInput, { target: { value: '24' } });
    expect(simulationCountInput).toHaveValue(24);

    fireEvent.click(within(advancedStep).getByText('滚动样本外稳健性预设'));
    const walkForwardToggle = await within(advancedStep).findByLabelText('启用滚动样本外稳健性预设');
    fireEvent.click(walkForwardToggle);

    fireEvent.click(within(screen.getByTestId('pro-execution-rail')).getByRole('button', { name: '执行回测任务' }));

    await waitFor(() => expect(runRuleBacktest).toHaveBeenCalledTimes(1));
    const payload = vi.mocked(runRuleBacktest).mock.calls[0]?.[0];
    expect(payload).toEqual(expect.objectContaining({
      robustnessConfig: {
        monteCarlo: {
          simulationCount: 24,
        },
        walkForward: {
          trainWindow: 24,
          testWindow: 12,
          step: 12,
          maxWindows: 4,
        },
      },
    }));
    expect(payload?.robustnessConfig?.monteCarlo).not.toHaveProperty('seed');
    expect(payload?.robustnessConfig?.monteCarlo).not.toHaveProperty('noiseScale');
  });

  it('reveals the right-side KPI console after a historical run starts', async () => {
    renderBacktestRoutes();

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('tab', { name: '历史评估' }));
    fireEvent.click(screen.getByRole('tab', { name: bt('zh', 'page.professionalMode') }));
    fireEvent.click(screen.getByRole('button', { name: '运行历史评估' }));

    await waitFor(() => expect(runBacktest).toHaveBeenCalledTimes(1));

    expect(screen.getByTestId('historical-display-section-summary')).toBeInTheDocument();
    expect(screen.getByTestId('historical-inspection-panel')).toBeInTheDocument();
    expect(screen.getByText('评估概览')).toBeInTheDocument();
  });

  it('shows a unified message when the historical page fails to load', async () => {
    getResults.mockRejectedValueOnce({
      response: {
        status: 500,
        data: {
          message: 'Internal Server Error',
        },
      },
    });

    renderBacktestRoutes();

    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole('tab', { name: '历史评估' }));

    const alerts = await screen.findAllByRole('alert');
    const alert = alerts.find((node) => node.textContent?.includes('服务器暂时不可用'));
    expect(alert).toBeDefined();
    expect(alert).toHaveTextContent('服务器暂时不可用');
    expect(alert).toHaveTextContent('服务器暂时不可用，请稍后重试。');
  });

  it('shows a unified message when deterministic backtest submission fails', async () => {
    runRuleBacktest.mockRejectedValueOnce({
      response: {
        status: 503,
        data: {
          message: 'backend temporarily down',
        },
      },
    });

    renderBacktestRoutes();

    await parseDeterministicStrategy();

    fireEvent.click(screen.getByLabelText(/我已确认当前解析结果与执行假设/i));
    fireEvent.click(within(screen.getByTestId('pro-execution-rail')).getByRole('button', { name: '执行回测任务' }));

    const alerts = await screen.findAllByRole('alert');
    const alert = alerts.find((node) => node.textContent?.includes('服务器暂时不可用'));
    expect(alert).toBeDefined();
    expect(alert).toHaveTextContent('服务器暂时不可用');
    expect(alert).toHaveTextContent('服务器暂时不可用，请稍后重试。');
  });

  it('opens deterministic history items in the dedicated result page route', async () => {
    const historySummary = makeRuleRunResponse({
      id: 123,
      runAt: '2026-04-08T08:00:00Z',
      completedAt: '2026-04-08T08:02:00Z',
      status: 'completed',
      statusMessage: '历史运行已完成。',
      auditRows: [
        {
          date: '2026-02-01',
          targetPosition: 0,
          totalPortfolioValue: 100000,
          cumulativeStrategyReturnPct: 0,
          dailyPnl: 0,
          dailyReturnPct: 0,
        },
        {
          date: '2026-02-02',
          targetPosition: 1,
          executedAction: 'buy',
          fillPrice: 99,
          totalPortfolioValue: 101500,
          cumulativeStrategyReturnPct: 1.5,
          dailyPnl: 1500,
          dailyReturnPct: 1.5,
        },
        {
          date: '2026-02-03',
          targetPosition: 0,
          executedAction: 'sell',
          fillPrice: 104,
          totalPortfolioValue: 104000,
          cumulativeStrategyReturnPct: 4,
          dailyPnl: 2500,
          dailyReturnPct: 2.46,
        },
      ],
    });

    getRuleBacktestRuns.mockResolvedValue({
      total: 1,
      page: 1,
      limit: 10,
      items: [historySummary],
    });
    getRuleBacktestRun.mockResolvedValue(historySummary);

    renderBacktestRoutes();

    await waitFor(() => expect(getRuleBacktestRuns).toHaveBeenCalled());
    await switchToProfessionalMode();

    fireEvent.click(within(screen.getByTestId('pro-workflow-rail')).getByRole('button', { name: '查看' }));

    expect(await screen.findByTestId('deterministic-backtest-result-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /ORCL/i })).toBeInTheDocument();
    expect(
      within(screen.getByTestId('deterministic-result-page-hero')).getByText((content, element) => (
        element?.tagName === 'P'
        && content.includes('2025-01-01')
        && content.includes('2026/04/08')
      )),
    ).toBeInTheDocument();
    expect(await screen.findByTestId('deterministic-backtest-result-view')).toHaveAttribute('data-run-id', '123');
    expect(await screen.findByTestId('deterministic-backtest-chart-workspace', undefined, { timeout: CHART_IMPORT_TIMEOUT })).toHaveAttribute('data-row-count', '3');
  }, 10000);

  it('renders English canonical result-page copy on localized result routes', async () => {
    window.history.replaceState(window.history.state, '', '/en/backtest/results/99');
    renderBacktestRoutes(['/en/backtest/results/99']);

    expect(await screen.findByTestId('deterministic-backtest-result-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /ORCL/i })).toBeInTheDocument();
    const heroCommandBar = screen.getByTestId('deterministic-result-page-hero').querySelector('[data-linear-primitive="command-bar"]');
    expect(heroCommandBar).not.toBeNull();
    expect(
      within(heroCommandBar as HTMLElement).getByRole('button', { name: bt('en', 'resultPage.hero.backToConfig') }),
    ).toBeInTheDocument();
    expect(await screen.findByRole('tab', { name: bt('en', 'resultPage.tabs.overview') })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: bt('en', 'resultPage.tabs.audit') })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: bt('en', 'resultPage.tabs.trades') })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: bt('en', 'resultPage.tabs.parameters') })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: bt('en', 'resultPage.tabs.history') })).toBeInTheDocument();
    expect(screen.getAllByText('Selected benchmark').length).toBeGreaterThan(0);
    expect(screen.getAllByText('QQQ').length).toBeGreaterThan(0);
  }, 10000);

  it('applies saved presets on the configuration page', async () => {
    window.localStorage.setItem(RULE_BACKTEST_PRESET_STORAGE_KEY, JSON.stringify([
      {
        id: 'saved-1',
        kind: 'saved',
        name: 'ORCL Swing',
        savedAt: '2026-04-12T08:00:00Z',
        sourceRunId: 99,
        code: 'ORCL',
        strategyText: 'MACD金叉买入，死叉卖出',
        startDate: '2026-01-01',
        endDate: '2026-03-31',
        lookbackBars: '126',
        initialCapital: '150000',
        feeBps: '3',
        slippageBps: '2',
        benchmarkMode: 'etf_qqq',
        benchmarkCode: '',
      },
    ]));

    renderBacktestRoutes();

    await switchToProfessionalMode();
    fireEvent.click(within(screen.getByTestId('pro-results-history-drawer')).getByRole('button', { name: /历史记录|History/i }));
    expect(await screen.findByTestId('backtest-setup-presets')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect(screen.getByDisplayValue('ORCL')).toBeInTheDocument();
    expect(screen.getByDisplayValue('150000')).toBeInTheDocument();
  });

  it('renders English shell copy on localized routes', async () => {
    window.history.replaceState(window.history.state, '', '/en/backtest');
    renderBacktestRoutes(['/en/backtest']);
    await waitFor(() => expect(getResults).toHaveBeenCalledTimes(1));
    await flushPendingUiWork();

    expect(screen.getByRole('tablist', { name: bt('en', 'page.moduleTabsLabel') })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: bt('en', 'page.ruleTab') })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: bt('en', 'page.historicalTab') })).toBeInTheDocument();
    expect(screen.getByRole('tablist', { name: bt('en', 'page.controlModeLabel') })).toBeInTheDocument();
    expect(screen.getByLabelText('Strategy template')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Execute backtest task' })).toHaveClass('bg-emerald-500/10', 'text-emerald-400', 'rounded-lg');
  });
});
