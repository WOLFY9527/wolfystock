import type React from 'react';
import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { AnimatePresence, domAnimation, LazyMotion, m } from 'motion/react';
import { useLocation, useNavigate } from 'react-router-dom';
import { backtestApi } from '../api/backtest';
import type { ParsedApiError } from '../api/error';
import { getApiErrorMessage, getParsedApiError } from '../api/error';
import type { RuleWizardStep } from '../components/backtest/DeterministicBacktestFlow';
import type { NormalStrategyTemplate } from '../components/backtest/pointAndShootTemplateOptions';
import { buildPointAndShootStrategyText } from '../components/backtest/strategyCatalog';
import {
  getDefaultRuleDateRange,
  getPeriodicNumber,
  getPeriodicString,
  type RuleBenchmarkMode,
  getStrategyPreviewSpec,
  parsePositiveInt,
} from '../components/backtest/shared';
import type { BacktestRunFeedback } from '../components/backtest/BacktestRunFeedbackBanner';
import type {
  AssumptionMap,
  BacktestResultItem,
  BacktestRunHistoryItem,
  BacktestRunResponse,
  BacktestSampleStatusResponse,
  PerformanceMetrics,
  PrepareBacktestSamplesResponse,
  RuleBacktestHistoryItem,
  RuleBacktestParseResponse,
  RuleBacktestRunResponse,
} from '../types/backtest';
import { useI18n } from '../contexts/UiLanguageContext';
import {
  getSafariReadySurfaceClassName,
  shouldApplySafariA11yGuard,
  useSafariRenderReady,
  useSafariWarmActivation,
} from '../hooks/useSafariInteractionReady';
import { translate } from '../i18n/core';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import ObservationOnlyBoundary from '../components/common/ObservationOnlyBoundary';
import { TerminalPageHeading } from '../components/terminal/TerminalPrimitives';
import { getConsumerSafeApiErrorCopy } from '../utils/consumerErrorCopy';

const HISTORICAL_PAGE_SIZE = 20;
const HISTORY_PAGE_SIZE = 10;
const RULE_HISTORY_PAGE_SIZE = 10;
const PRO_MONTE_CARLO_SIMULATION_DEFAULT = '12';
const PRO_MONTE_CARLO_SIMULATION_MIN = 1;
const PRO_MONTE_CARLO_SIMULATION_MAX = 64;
const PRO_WALK_FORWARD_PRESET = {
  trainWindow: 24,
  testWindow: 12,
  step: 12,
  maxWindows: 4,
} as const;
const NormalBacktestWorkspace = lazy(() => import('../components/backtest/NormalBacktestWorkspace'));
const HistoricalEvaluationPanel = lazy(() => import('../components/backtest/HistoricalEvaluationPanel'));
const ProBacktestWorkspace = lazy(() => import('../components/backtest/ProBacktestWorkspace'));

type ActiveModule = 'historical' | 'rule';
type ControlPanelMode = 'normal' | 'professional';
type BacktestPageLocationState = {
  draftRun?: RuleBacktestRunResponse;
  prefillCode?: string;
  prefillName?: string;
};

type ScannerBacktestHandoff = {
  symbol: string;
  market: 'CN' | 'US' | 'HK' | null;
  scannerRunId: number | null;
  scannerRank: number | null;
  scannerProfile: string | null;
  themeId: string | null;
  universeType: string | null;
};

type PerformanceNotice = {
  tone: 'warning' | 'danger';
  message: string;
};

type BacktestLanguage = 'zh' | 'en';
function bt(language: BacktestLanguage, key: string, vars?: Record<string, string | number | undefined>): string {
  return translate(language, `backtest.${key}`, vars);
}

function buildRuleParseSignature(payload: {
  code: string;
  strategyText: string;
  startDate: string;
  endDate: string;
  initialCapital: string;
  feeBps: string;
  slippageBps: string;
}): string {
  return JSON.stringify({
    code: payload.code.trim().toUpperCase(),
    strategyText: payload.strategyText.trim(),
    startDate: payload.startDate,
    endDate: payload.endDate,
    initialCapital: payload.initialCapital.trim(),
    feeBps: payload.feeBps.trim(),
    slippageBps: payload.slippageBps.trim(),
  });
}

function normalizeBacktestSymbol(value?: string | null): string | null {
  const normalized = String(value || '').trim().toUpperCase();
  return normalized || null;
}

function normalizeBacktestMarket(value?: string | null): ScannerBacktestHandoff['market'] {
  const normalized = String(value || '').trim().toUpperCase();
  if (normalized === 'CN' || normalized === 'US' || normalized === 'HK') {
    return normalized;
  }
  return null;
}

function parsePositiveInteger(value?: string | null): number | null {
  const parsed = Number.parseInt(String(value || '').trim(), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function clampInteger(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

function parseScannerBacktestHandoff(search: string): ScannerBacktestHandoff | null {
  const params = new URLSearchParams(search);
  if (params.get('source') !== 'scanner') return null;

  const symbol = normalizeBacktestSymbol(params.get('symbol'));
  if (!symbol) return null;

  return {
    symbol,
    market: normalizeBacktestMarket(params.get('market')),
    scannerRunId: parsePositiveInteger(params.get('scannerRunId')),
    scannerRank: parsePositiveInteger(params.get('scannerRank')),
    scannerProfile: params.get('scannerProfile')?.trim() || null,
    themeId: params.get('themeId')?.trim() || null,
    universeType: params.get('universeType')?.trim() || null,
  };
}

function normalizeReadinessState(value?: string | null): string {
  return String(value || '').trim().toLowerCase().replaceAll('-', '_').replace(/\s+/g, '_');
}

function shouldKeepRuleRunOnConfigPage(response: RuleBacktestRunResponse): boolean {
  const readinessState = normalizeReadinessState(response.executionReadiness?.state);
  if (['engine_disabled', 'data_disabled', 'no_samples', 'data_insufficient'].includes(readinessState)) {
    return true;
  }
  return Boolean(response.executionReadiness?.resultContractAvailable === false && response.noResultReason);
}

const BACKTEST_RUN_STATE_LABELS: Record<string, { zh: string; en: string }> = {
  engine_disabled: { zh: '回测引擎已关闭', en: 'Backtest engine disabled' },
  data_disabled: { zh: '数据访问不可用', en: 'Data access unavailable' },
  no_samples: { zh: '暂无可用样本', en: 'No usable samples' },
  data_insufficient: { zh: '历史数据不足', en: 'Insufficient history' },
  degraded: { zh: '结果已返回，证据降级', en: 'Result returned with degraded evidence' },
  executable: { zh: '已返回安全结果契约', en: 'Safe result contract returned' },
  calculation_unavailable: { zh: '等待执行回执', en: 'Waiting for execution receipt' },
  unknown: { zh: '等待就绪度', en: 'Waiting for readiness' },
};

const BACKTEST_RUN_REASON_LABELS: Record<string, { zh: string; en: string }> = {
  engine_disabled: { zh: '引擎开关关闭，未产生结果契约。', en: 'Engine switch is disabled, so no result contract was produced.' },
  provider_missing: { zh: '数据源未就绪，无法读取所需行情。', en: 'Data source is not ready for the required market data.' },
  entitlement_required: { zh: '数据授权不足，无法读取所需行情。', en: 'Data entitlement is missing for the required market data.' },
  no_samples: { zh: '缺少已准备的分析样本。', en: 'Prepared analysis samples are missing.' },
  insufficient_history: { zh: '历史 OHLCV 窗口不足，无法计算安全结果。', en: 'The OHLCV window is too short to calculate a safe result.' },
  insufficient_data: { zh: '可用数据不足，未生成收益、回撤、胜率或基准相对指标。', en: 'Available data is insufficient, so return, drawdown, win-rate, and benchmark-relative metrics are unavailable.' },
  missing_benchmark: { zh: '缺少基准，基准相对指标不可用。', en: 'Benchmark is missing, so benchmark-relative metrics are unavailable.' },
  missing_adjustments: { zh: '复权或公司行动证据不足，结果只能观察。', en: 'Adjustment or corporate-action evidence is incomplete; result is observation-only.' },
  stale_data: { zh: '数据可能过期，结果只能观察。', en: 'Data may be stale; result is observation-only.' },
  historical_ohlcv_not_configured: { zh: '历史 OHLCV 运行时未配置。', en: 'Historical OHLCV runtime is not configured.' },
  historical_ohlcv_stale: { zh: '历史 OHLCV 覆盖已过期。', en: 'Historical OHLCV coverage is stale.' },
  historical_ohlcv_insufficient_coverage: { zh: '请求区间的历史 OHLCV 覆盖不足。', en: 'Historical OHLCV coverage is insufficient for the requested range.' },
  historical_ohlcv_missing: { zh: '缺少必需的历史 OHLCV 输入。', en: 'Required historical OHLCV inputs are missing.' },
  historical_ohlcv_unavailable: { zh: '历史 OHLCV 运行时不可用。', en: 'Historical OHLCV runtime is unavailable.' },
};

function uniqueReadinessTokens(values?: string[] | null): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values || []) {
    const token = normalizeReadinessState(value);
    if (!token || seen.has(token)) continue;
    seen.add(token);
    result.push(token);
  }
  return result;
}

function getBacktestReasonLabels(
  readiness: RuleBacktestRunResponse['executionReadiness'] | null | undefined,
  language: BacktestLanguage,
): string[] {
  const reasons = uniqueReadinessTokens(readiness?.reasonCodes);
  const labels = reasons
    .map((reason) => BACKTEST_RUN_REASON_LABELS[reason]?.[language])
    .filter((value): value is string => Boolean(value));
  const benchmarkState = normalizeReadinessState(readiness?.benchmarkState);
  if (benchmarkState === 'missing' && !labels.includes(BACKTEST_RUN_REASON_LABELS.missing_benchmark[language])) {
    labels.push(BACKTEST_RUN_REASON_LABELS.missing_benchmark[language]);
  }
  return labels;
}

function buildPendingBacktestRunFeedback(language: BacktestLanguage, mode: 'normal' | 'professional'): BacktestRunFeedback {
  return {
    tone: 'default',
    title: language === 'en' ? 'Backtest request accepted' : '回测任务已受理',
    body: mode === 'normal'
      ? (language === 'en'
        ? 'Submitting the selected template and checking data readiness before any result view is shown.'
        : '正在提交回测请求，正在检查数据就绪度；结果结构返回前不会展示指标。')
      : (language === 'en'
        ? 'Submitting the backtest request and checking data readiness before opening any result view.'
        : '正在提交回测请求，正在检查数据就绪度；结果页打开前先等待回执。'),
  };
}

function buildBacktestValidationFeedback(message: string, language: BacktestLanguage): BacktestRunFeedback {
  return {
    tone: 'warning',
    title: language === 'en' ? 'Backtest request not submitted' : '回测任务未提交',
    body: message,
  };
}

function buildBacktestErrorFeedback(error: ParsedApiError, language: BacktestLanguage): BacktestRunFeedback {
  const safeCopy = getConsumerSafeApiErrorCopy(error, {
    language,
    fallbackTitle: language === 'en' ? 'Backtest unavailable' : '回测暂不可用',
    fallbackMessage: language === 'en' ? 'Please try again shortly.' : '请稍后重试。',
  });
  return {
    tone: 'danger',
    title: language === 'en' ? 'Backtest did not complete' : '回测未完成',
    body: safeCopy.message,
  };
}

function buildBacktestResponseFeedback(
  response: RuleBacktestRunResponse,
  language: BacktestLanguage,
): BacktestRunFeedback {
  const readiness = response.executionReadiness || null;
  const state = normalizeReadinessState(readiness?.state) || 'unknown';
  const stateLabel = BACKTEST_RUN_STATE_LABELS[state]?.[language] || BACKTEST_RUN_STATE_LABELS.unknown[language];
  const reasonLabels = getBacktestReasonLabels(readiness, language);
  if (readiness?.resultContractAvailable) {
    return {
      tone: 'success',
      title: stateLabel,
      body: language === 'en'
        ? 'A consumer-safe result view is ready. Metrics are shown only when returned by the backend.'
        : '消费者安全结果结构已返回；仅展示后端明确返回的指标。',
      details: reasonLabels,
    };
  }
  return {
    tone: 'warning',
    title: stateLabel,
    body: response.noResultMessage
      || reasonLabels[0]
      || (language === 'en'
        ? 'The run is blocked or still waiting for a safe result view.'
        : '本次运行被阻塞，或仍在等待安全结果结构。'),
    details: reasonLabels.slice(response.noResultMessage ? 0 : 1),
  };
}

const BacktestPage: React.FC = () => {
  const { isReady: isSafariReady, surfaceRef } = useSafariRenderReady();
  const shouldGuardA11y = shouldApplySafariA11yGuard();
  const navigate = useNavigate();
  const { search: routeSearch, state: routeState } = useLocation();
  const { language } = useI18n();
  const scannerHandoff = parseScannerBacktestHandoff(routeSearch);
  const ruleBacktestSubmitInFlightRef = useRef(false);
  const normalRuleLaunchInFlightRef = useRef(false);

  useEffect(() => {
    document.title = bt(language, 'page.documentTitle');
  }, [language]);

  const [activeModule, setActiveModule] = useState<ActiveModule>('rule');
  const [controlPanelMode, setControlPanelMode] = useState<ControlPanelMode>('normal');
  const [codeFilter, setCodeFilter] = useState('');
  const [normalStrategyTemplate, setNormalStrategyTemplate] = useState<NormalStrategyTemplate>('moving_average_crossover');
  const [evaluationBars, setEvaluationBars] = useState('10');
  const [maturityDays, setMaturityDays] = useState('14');
  const [samplePreset, setSamplePreset] = useState('60');
  const [customSampleCount, setCustomSampleCount] = useState('252');
  const [forceReplaceResults, setForceReplaceResults] = useState(false);

  const [isRunningHistoricalEval, setIsRunningHistoricalEval] = useState(false);
  const [runResult, setRunResult] = useState<BacktestRunResponse | null>(null);
  const [runError, setRunError] = useState<ParsedApiError | null>(null);

  const [prepareResult, setPrepareResult] = useState<PrepareBacktestSamplesResponse | null>(null);
  const [prepareError, setPrepareError] = useState<ParsedApiError | null>(null);
  const [isPreparingSamples, setIsPreparingSamples] = useState(false);

  const [pageError, setPageError] = useState<ParsedApiError | null>(null);
  const [historyError, setHistoryError] = useState<ParsedApiError | null>(null);
  const [sampleStatusError, setSampleStatusError] = useState<ParsedApiError | null>(null);

  const [sampleStatus, setSampleStatus] = useState<BacktestSampleStatusResponse | null>(null);
  const [results, setResults] = useState<BacktestResultItem[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [isLoadingResults, setIsLoadingResults] = useState(false);

  const [historyItems, setHistoryItems] = useState<BacktestRunHistoryItem[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingSampleStatus, setIsLoadingSampleStatus] = useState(false);

  const [overallPerf, setOverallPerf] = useState<PerformanceMetrics | null>(null);
  const [stockPerf, setStockPerf] = useState<PerformanceMetrics | null>(null);
  const [isLoadingPerf, setIsLoadingPerf] = useState(false);
  const [performanceNotice, setPerformanceNotice] = useState<PerformanceNotice | null>(null);

  const [ruleStrategyText, setRuleStrategyText] = useState(() => bt(language, 'page.defaultStrategyText'));
  const [ruleStartDate, setRuleStartDate] = useState(() => getDefaultRuleDateRange().startDate);
  const [ruleEndDate, setRuleEndDate] = useState(() => getDefaultRuleDateRange().endDate);
  const [ruleLookbackBars, setRuleLookbackBars] = useState('252');
  const [ruleInitialCapital, setRuleInitialCapital] = useState('100000');
  const [ruleFeeBps, setRuleFeeBps] = useState('0');
  const [ruleSlippageBps, setRuleSlippageBps] = useState('0');
  const [ruleBenchmarkMode, setRuleBenchmarkMode] = useState<RuleBenchmarkMode>('auto');
  const [ruleBenchmarkCode, setRuleBenchmarkCode] = useState('');
  const [proMonteCarloEnabled, setProMonteCarloEnabled] = useState(false);
  const [proMonteCarloSimulationCount, setProMonteCarloSimulationCount] = useState('');
  const [proWalkForwardPresetEnabled, setProWalkForwardPresetEnabled] = useState(false);
  const [ruleParsedStrategy, setRuleParsedStrategy] = useState<RuleBacktestParseResponse | null>(null);
  const [ruleConfirmed, setRuleConfirmed] = useState(false);
  const [isParsingRuleStrategy, setIsParsingRuleStrategy] = useState(false);
  const [isLaunchingNormalRuleBacktest, setIsLaunchingNormalRuleBacktest] = useState(false);
  const [ruleParseError, setRuleParseError] = useState<ParsedApiError | null>(null);
  const [isSubmittingRuleBacktest, setIsSubmittingRuleBacktest] = useState(false);
  const [ruleRunError, setRuleRunError] = useState<ParsedApiError | null>(null);
  const [lastRuleRunResult, setLastRuleRunResult] = useState<RuleBacktestRunResponse | null>(null);
  const [ruleRunFeedback, setRuleRunFeedback] = useState<BacktestRunFeedback | null>(null);
  const [ruleHistoryItems, setRuleHistoryItems] = useState<RuleBacktestHistoryItem[]>([]);
  const [ruleHistoryTotal, setRuleHistoryTotal] = useState(0);
  const [ruleHistoryPage, setRuleHistoryPage] = useState(1);
  const [isLoadingRuleHistory, setIsLoadingRuleHistory] = useState(false);
  const [ruleHistoryError, setRuleHistoryError] = useState<ParsedApiError | null>(null);
  const [selectedRuleRunId, setSelectedRuleRunId] = useState<number | null>(null);
  const [ruleCurrentStep, setRuleCurrentStep] = useState<RuleWizardStep>('symbol');
  const [ruleParseSignature, setRuleParseSignature] = useState<string | null>(null);
  const [appliedRewriteText, setAppliedRewriteText] = useState<string | null>(null);
  const {
    ref: showRuleModuleButtonRef,
    onClick: handleShowRuleModuleClick,
    onPointerUp: handleShowRuleModulePointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(() => setActiveModule('rule'));
  const {
    ref: showHistoricalModuleButtonRef,
    onClick: handleShowHistoricalModuleClick,
    onPointerUp: handleShowHistoricalModulePointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(() => setActiveModule('historical'));
  const {
    ref: showNormalModeButtonRef,
    onClick: handleShowNormalModeClick,
    onPointerUp: handleShowNormalModePointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(() => setControlPanelMode('normal'));
  const {
    ref: showProfessionalModeButtonRef,
    onClick: handleShowProfessionalModeClick,
    onPointerUp: handleShowProfessionalModePointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(() => setControlPanelMode('professional'));

  const normalizedCode = String(codeFilter || '').trim().toUpperCase();
  const resolvedSampleCount = samplePreset === 'custom'
    ? parsePositiveInt(customSampleCount, 252)
    : parsePositiveInt(samplePreset, 60);

  const currentRuleParseSignature = buildRuleParseSignature({
    code: normalizedCode,
    strategyText: ruleStrategyText,
    startDate: ruleStartDate,
    endDate: ruleEndDate,
    initialCapital: ruleInitialCapital,
    feeBps: ruleFeeBps,
    slippageBps: ruleSlippageBps,
  });

  const isRuleParseStale = Boolean(ruleParsedStrategy && ruleParseSignature && ruleParseSignature !== currentRuleParseSignature);

  const historicalAssumptions = runResult?.executionAssumptions
    || overallPerf?.executionAssumptions
    || results[0]?.executionAssumptions
    || null;

  const historicalPerfSnapshot = stockPerf || overallPerf;
  const selectedHistoricalRun = historyItems.find((item) => item.id === selectedRunId) || null;

  const historicalSourceMetadata = (() => {
    const candidates = [
      runResult,
      selectedHistoricalRun,
      sampleStatus,
      stockPerf,
      overallPerf,
      prepareResult,
    ];

    const firstString = (selector: (candidate: typeof candidates[number]) => string | null | undefined) => {
      for (const candidate of candidates) {
        const value = selector(candidate);
        if (typeof value === 'string' && value.trim()) return value;
      }
      return null;
    };

    const firstBoolean = (selector: (candidate: typeof candidates[number]) => boolean | null | undefined) => {
      for (const candidate of candidates) {
        const value = selector(candidate);
        if (typeof value === 'boolean') return value;
      }
      return null;
    };

    return {
      requestedMode: firstString((candidate) => candidate?.requestedMode),
      resolvedSource: firstString((candidate) => candidate?.resolvedSource),
      fallbackUsed: firstBoolean((candidate) => candidate?.fallbackUsed),
    };
  })();

  const historicalSummaryItems = [
    {
      label: bt(language, 'page.historicalSummary.preparedSamplesLabel'),
      value: sampleStatus?.preparedCount != null ? String(sampleStatus.preparedCount) : '--',
      note: sampleStatus?.preparedStartDate && sampleStatus?.preparedEndDate
        ? `${sampleStatus.preparedStartDate} -> ${sampleStatus.preparedEndDate}`
        : bt(language, 'page.historicalSummary.preparedSamplesNoteFallback'),
    },
    {
      label: bt(language, 'page.historicalSummary.completedEvaluationsLabel'),
      value: historicalPerfSnapshot?.completedCount != null ? String(historicalPerfSnapshot.completedCount) : '--',
      note: historicalPerfSnapshot?.totalEvaluations != null
        ? bt(language, 'page.historicalSummary.completedEvaluationsTotalSamples', { count: historicalPerfSnapshot.totalEvaluations })
        : bt(language, 'page.historicalSummary.completedEvaluationsNoteFallback'),
    },
    {
      label: bt(language, 'page.historicalSummary.directionAccuracyLabel'),
      value: historicalPerfSnapshot?.directionAccuracyPct != null ? `${historicalPerfSnapshot.directionAccuracyPct.toFixed(2)}%` : '--',
      note: bt(language, 'page.historicalSummary.directionAccuracyNote'),
    },
    {
      label: bt(language, 'page.historicalSummary.winRateLabel'),
      value: historicalPerfSnapshot?.winRatePct != null ? `${historicalPerfSnapshot.winRatePct.toFixed(2)}%` : '--',
      note: bt(language, 'page.historicalSummary.winRateNote'),
    },
    {
      label: bt(language, 'page.historicalSummary.averageForwardReturnLabel'),
      value: historicalPerfSnapshot?.avgSimulatedReturnPct != null ? `${historicalPerfSnapshot.avgSimulatedReturnPct.toFixed(2)}%` : '--',
      note: bt(language, 'page.historicalSummary.averageForwardReturnNote'),
    },
    {
      label: bt(language, 'page.historicalSummary.averageInstrumentReturnLabel'),
      value: historicalPerfSnapshot?.avgStockReturnPct != null ? `${historicalPerfSnapshot.avgStockReturnPct.toFixed(2)}%` : '--',
      note: bt(language, 'page.historicalSummary.averageInstrumentReturnNote'),
    },
  ];

  const historicalSampleTransparency = (() => {
    const latestPreparedSampleDate = runResult?.latestPreparedSampleDate
      || sampleStatus?.latestPreparedSampleDate
      || prepareResult?.latestPreparedSampleDate
      || null;
    const latestEligibleSampleDate = runResult?.latestEligibleSampleDate
      || sampleStatus?.latestEligibleSampleDate
      || prepareResult?.latestEligibleSampleDate
      || null;
    const excludedRecentMessage = runResult?.excludedRecentMessage
      || sampleStatus?.excludedRecentMessage
      || prepareResult?.excludedRecentMessage
      || null;
    const pricingResolvedSource = runResult?.pricingResolvedSource
      || sampleStatus?.pricingResolvedSource
      || prepareResult?.pricingResolvedSource
      || historicalSourceMetadata.resolvedSource
      || null;
    const pricingFallbackUsed = runResult?.pricingFallbackUsed
      ?? sampleStatus?.pricingFallbackUsed
      ?? prepareResult?.pricingFallbackUsed
      ?? historicalSourceMetadata.fallbackUsed
      ?? null;

    const parts = [
      bt(language, 'page.historicalTransparency.latestPreparedSample', { date: latestPreparedSampleDate || '--' }),
      bt(language, 'page.historicalTransparency.latestEvaluableSample', { date: latestEligibleSampleDate || '--' }),
    ];
    if (excludedRecentMessage) {
      parts.push(bt(language, 'page.historicalTransparency.excludedRecent', { message: excludedRecentMessage }));
    }
    if (pricingResolvedSource) {
      parts.push(
        bt(language, 'page.historicalTransparency.pricingSource', {
          source: pricingResolvedSource,
          detail: pricingFallbackUsed == null
            ? ''
            : bt(
              language,
              pricingFallbackUsed
                ? 'page.historicalTransparency.pricingFallbackUsedDetail'
                : 'page.historicalTransparency.pricingFallbackNotUsedDetail',
            ),
        }),
      );
    }
    return parts.join(' · ');
  })();

  const previewRuleAssumptions: AssumptionMap = {
    timeframe: ruleParsedStrategy?.parsedStrategy.timeframe || 'daily',
    price_basis: 'close',
    signal_evaluation_timing: 'bar close',
    entry_fill_timing: 'next bar open',
    exit_fill_timing: 'next bar open; final bar may force close at close',
    position_sizing: '100% capital when long, otherwise cash',
    fee_bps_per_side: Number.parseFloat(ruleFeeBps) || 0,
    slippage_bps_per_side: Number.parseFloat(ruleSlippageBps) || 0,
  };

  const fetchResults = (page = 1, code?: string, windowBars?: number, runId?: number | null) => {
    setIsLoadingResults(true);
    return backtestApi.getResults({
      code: code || undefined,
      evalWindowDays: windowBars,
      runId: runId || undefined,
      page,
      limit: HISTORICAL_PAGE_SIZE,
    })
      .then((response) => {
        setResults(response.items);
        setTotalResults(response.total);
        setCurrentPage(response.page);
        setPageError(null);
      })
      .catch((error) => {
        setPageError(getParsedApiError(error));
      })
      .finally(() => {
        setIsLoadingResults(false);
      });
  };

  const fetchHistory = (page = 1, code?: string) => {
    setIsLoadingHistory(true);
    return backtestApi.getHistory({ code: code || undefined, page, limit: HISTORY_PAGE_SIZE })
      .then((response) => {
        setHistoryItems(response.items);
        setHistoryTotal(response.total);
        setHistoryPage(response.page);
        setHistoryError(null);
      })
      .catch((error) => {
        setHistoryError(getParsedApiError(error));
      })
      .finally(() => {
        setIsLoadingHistory(false);
      });
  };

  const fetchSampleStatus = (code?: string) => {
    if (!code) {
      setSampleStatus(null);
      setSampleStatusError(null);
      return Promise.resolve();
    }
    setIsLoadingSampleStatus(true);
    return backtestApi.getSampleStatus(code)
      .then((response) => {
        setSampleStatus(response);
        setSampleStatusError(null);
      })
      .catch((error) => {
        setSampleStatus(null);
        setSampleStatusError(getParsedApiError(error));
      })
      .finally(() => {
        setIsLoadingSampleStatus(false);
      });
  };

  const fetchRuleHistory = (page = 1, code?: string) => {
    setIsLoadingRuleHistory(true);
    return backtestApi.getRuleBacktestRuns({ code: code || undefined, page, limit: RULE_HISTORY_PAGE_SIZE })
      .then((response) => {
        setRuleHistoryItems(response.items);
        setRuleHistoryTotal(response.total);
        setRuleHistoryPage(response.page);
        setRuleHistoryError(null);
      })
      .catch((error) => {
        setRuleHistoryError(getParsedApiError(error));
      })
      .finally(() => {
        setIsLoadingRuleHistory(false);
      });
  };

  useEffect(() => {
    const state = routeState as BacktestPageLocationState | null;
    const draftRun = state?.draftRun;
    const prefillCode = state?.prefillCode?.trim().toUpperCase();
    if (!draftRun && !scannerHandoff?.symbol && !prefillCode) return;

    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;

      if (draftRun) {
        const parsedStrategyPayload = draftRun.parsedStrategy as unknown as Record<string, unknown>;
        const detectedStrategyFamily = draftRun.parsedStrategy.detectedStrategyFamily
          ?? (typeof parsedStrategyPayload.detected_strategy_family === 'string' ? parsedStrategyPayload.detected_strategy_family : undefined);
        const unsupportedExtensions = draftRun.parsedStrategy.unsupportedExtensions
          ?? (Array.isArray(parsedStrategyPayload.unsupported_extensions) ? parsedStrategyPayload.unsupported_extensions as Array<Record<string, unknown>> : undefined);
        const coreIntentSummary = draftRun.parsedStrategy.coreIntentSummary
          ?? (typeof parsedStrategyPayload.core_intent_summary === 'string' ? parsedStrategyPayload.core_intent_summary : undefined);
        const interpretationConfidence = draftRun.parsedStrategy.interpretationConfidence
          ?? (typeof parsedStrategyPayload.interpretation_confidence === 'number' ? parsedStrategyPayload.interpretation_confidence : undefined);
        const parsedStrategySummary = (draftRun.summary.parsedStrategySummary as Record<string, string> | undefined)
          || draftRun.parsedStrategy.summary;

        setSelectedRuleRunId(draftRun.id);
        setActiveModule('rule');
        setCodeFilter(draftRun.code);
        setRuleStrategyText(draftRun.strategyText);
        setRuleStartDate(draftRun.startDate || '');
        setRuleEndDate(draftRun.endDate || '');
        setRuleLookbackBars(String(draftRun.lookbackBars || 252));
        setRuleInitialCapital(String(draftRun.initialCapital || 100000));
        setRuleFeeBps(String(draftRun.feeBps ?? 0));
        setRuleSlippageBps(String(draftRun.slippageBps ?? 0));
        setRuleBenchmarkMode((draftRun.benchmarkMode as RuleBenchmarkMode | undefined) || 'auto');
        setRuleBenchmarkCode(draftRun.benchmarkCode || '');
        setRuleParsedStrategy({
          code: draftRun.code,
          strategyText: draftRun.strategyText,
          parsedStrategy: {
            ...draftRun.parsedStrategy,
            summary: parsedStrategySummary,
          },
          normalizedStrategyFamily: String((draftRun.parsedStrategy.strategySpec as Record<string, unknown> | undefined)?.strategyType || draftRun.parsedStrategy.strategyKind || ''),
          executable: Boolean(draftRun.parsedStrategy.executable),
          normalizationState: draftRun.parsedStrategy.normalizationState,
          assumptions: draftRun.parsedStrategy.assumptions,
          assumptionGroups: draftRun.parsedStrategy.assumptionGroups,
          detectedStrategyFamily,
          unsupportedReason: draftRun.parsedStrategy.unsupportedReason,
          unsupportedDetails: draftRun.parsedStrategy.unsupportedDetails,
          unsupportedExtensions,
          coreIntentSummary,
          interpretationConfidence,
          supportedPortionSummary: draftRun.parsedStrategy.supportedPortionSummary,
          rewriteSuggestions: draftRun.parsedStrategy.rewriteSuggestions,
          parseWarnings: draftRun.parsedStrategy.parseWarnings,
          confidence: draftRun.parsedConfidence ?? draftRun.parsedStrategy.confidence ?? 0,
          needsConfirmation: draftRun.needsConfirmation,
          ambiguities: draftRun.warnings,
          summary: parsedStrategySummary,
          maxLookback: draftRun.parsedStrategy.maxLookback,
        });
        setRuleParseSignature(buildRuleParseSignature({
          code: draftRun.code,
          strategyText: draftRun.strategyText,
          startDate: draftRun.startDate || '',
          endDate: draftRun.endDate || '',
          initialCapital: String(draftRun.initialCapital || 100000),
          feeBps: String(draftRun.feeBps ?? 0),
          slippageBps: String(draftRun.slippageBps ?? 0),
        }));
        setRuleConfirmed(true);
        setRuleCurrentStep('strategy');
        setAppliedRewriteText(null);
        setLastRuleRunResult(draftRun);
        return;
      }

      if (scannerHandoff?.symbol) {
        setActiveModule('rule');
        setControlPanelMode('normal');
        setCodeFilter(scannerHandoff.symbol);
        return;
      }

      if (!prefillCode) return;
      setActiveModule('rule');
      setCodeFilter(prefillCode);
    });

    return () => {
      cancelled = true;
    };
  }, [routeState, scannerHandoff]);

  const fetchPerformance = async (code?: string, windowBars?: number, options: { showNotice?: boolean } = {}) => {
    const { showNotice = true } = options;
    setIsLoadingPerf(true);
    const notices: string[] = [];
    let hasDanger = false;

    try {
      const overall = await backtestApi.getOverallPerformance(windowBars);
      setOverallPerf(overall);
      if (overall == null && showNotice) notices.push(bt(language, 'page.performanceNotice.noAggregateSummary'));
    } catch (error) {
      setOverallPerf(null);
      hasDanger = true;
      if (showNotice) notices.push(getApiErrorMessage(error));
    }

    if (code) {
      try {
        const stock = await backtestApi.getStockPerformance(code, windowBars);
        setStockPerf(stock);
        if (stock == null && showNotice) notices.push(bt(language, 'page.performanceNotice.noInstrumentSummary', { code }));
      } catch (error) {
        setStockPerf(null);
        hasDanger = true;
        if (showNotice) notices.push(getApiErrorMessage(error));
      }
    } else {
      setStockPerf(null);
    }

    if (showNotice && notices.length > 0) {
      setPerformanceNotice({ tone: hasDanger ? 'danger' : 'warning', message: notices.join(' ') });
    } else if (showNotice) {
      setPerformanceNotice(null);
    }

    setIsLoadingPerf(false);
  };

  useEffect(() => {
    void backtestApi.getOverallPerformance()
      .then((overall) => {
        setOverallPerf(overall);
        const defaultWindow = overall?.evalWindowDays;
        if (defaultWindow) setEvaluationBars(String(defaultWindow));
        setPerformanceNotice(null);
      })
      .catch((error) => {
        setPerformanceNotice({
          tone: 'danger',
          message: getApiErrorMessage(error),
        });
      })
      .finally(() => {
        setIsLoadingResults(true);
        void backtestApi.getResults({
          code: undefined,
          evalWindowDays: undefined,
          runId: undefined,
          page: 1,
          limit: HISTORICAL_PAGE_SIZE,
        })
          .then((response) => {
            setResults(response.items);
            setTotalResults(response.total);
            setCurrentPage(response.page);
            setPageError(null);
          })
          .catch((error) => {
            setPageError(getParsedApiError(error));
          })
          .finally(() => {
            setIsLoadingResults(false);
          });

        setIsLoadingHistory(true);
        void backtestApi.getHistory({ code: undefined, page: 1, limit: HISTORY_PAGE_SIZE })
          .then((response) => {
            setHistoryItems(response.items);
            setHistoryTotal(response.total);
            setHistoryPage(response.page);
            setHistoryError(null);
          })
          .catch((error) => {
            setHistoryError(getParsedApiError(error));
          })
          .finally(() => {
            setIsLoadingHistory(false);
          });

        setIsLoadingRuleHistory(true);
        void backtestApi.getRuleBacktestRuns({ code: undefined, page: 1, limit: RULE_HISTORY_PAGE_SIZE })
          .then((response) => {
            setRuleHistoryItems(response.items);
            setRuleHistoryTotal(response.total);
            setRuleHistoryPage(response.page);
            setRuleHistoryError(null);
          })
          .catch((error) => {
            setRuleHistoryError(getParsedApiError(error));
          })
          .finally(() => {
            setIsLoadingRuleHistory(false);
          });
      });
  }, []);

  const handleFilter = () => {
    const code = normalizedCode || undefined;
    const windowBars = parsePositiveInt(evaluationBars, 10);
    setSelectedRunId(null);
    setHistoryPage(1);
    setCurrentPage(1);
    setRuleHistoryPage(1);
    setPerformanceNotice(null);
    setSelectedRuleRunId(null);
    void fetchResults(1, code, windowBars, null);
    void fetchHistory(1, code);
    void fetchSampleStatus(code);
    void fetchPerformance(code, windowBars, { showNotice: true });
    void fetchRuleHistory(1, code);
  };

  const handleRunHistoricalEvaluation = () => {
    setIsRunningHistoricalEval(true);
    setRunResult(null);
    setRunError(null);
    setPrepareResult(null);
    setPrepareError(null);
    const windowBars = parsePositiveInt(evaluationBars, 10);
    const maturityCalendarDays = parsePositiveInt(maturityDays, 14, 0);
    return backtestApi.run({
      code: normalizedCode || undefined,
      force: forceReplaceResults,
      evalWindowDays: windowBars,
      minAgeDays: maturityCalendarDays,
    })
      .then(async (response) => {
        setRunResult(response);
        setSelectedRunId(response.runId ?? null);
        await Promise.all([
          fetchResults(1, normalizedCode || undefined, windowBars, response.runId ?? null),
          fetchHistory(1, normalizedCode || undefined),
          fetchSampleStatus(normalizedCode || undefined),
        ]);
        await fetchPerformance(normalizedCode || undefined, windowBars, { showNotice: true });
      })
      .catch((error) => {
        setRunError(getParsedApiError(error));
      })
      .finally(() => {
        setIsRunningHistoricalEval(false);
      });
  };

  const handlePrepareSamples = (options: { forceRefresh?: boolean } = {}) => {
    if (!normalizedCode) {
      setPrepareError({
        title: bt(language, 'page.errors.missingCodeTitle'),
        message: bt(language, 'page.errors.missingPrepareSamples'),
        rawMessage: bt(language, 'page.errors.missingPrepareSamples'),
        category: 'missing_params',
      });
      return Promise.resolve();
    }

    setIsPreparingSamples(true);
    setPrepareResult(null);
    setPrepareError(null);
    return backtestApi.prepareSamples({
      code: normalizedCode,
      sampleCount: resolvedSampleCount,
      evalWindowDays: parsePositiveInt(evaluationBars, 10),
      minAgeDays: parsePositiveInt(maturityDays, 14, 0),
      forceRefresh: options.forceRefresh || false,
    })
      .then(async (response) => {
        setPrepareResult(response);
        await Promise.all([
          fetchSampleStatus(normalizedCode),
          fetchHistory(1, normalizedCode),
        ]);
      })
      .catch((error) => {
        setPrepareError(getParsedApiError(error));
      })
      .finally(() => {
        setIsPreparingSamples(false);
      });
  };

  const handleRebuildSamples = () => {
    if (!normalizedCode) {
      setPrepareError({
        title: bt(language, 'page.errors.missingCodeTitle'),
        message: bt(language, 'page.errors.missingRebuildSamples'),
        rawMessage: bt(language, 'page.errors.missingRebuildSamples'),
        category: 'missing_params',
      });
      return Promise.resolve();
    }

    setIsPreparingSamples(true);
    setPrepareResult(null);
    setPrepareError(null);
    return backtestApi.clearSamples(normalizedCode)
      .then(() => handlePrepareSamples({ forceRefresh: false }))
      .then(() => fetchResults(1, normalizedCode, parsePositiveInt(evaluationBars, 10), null))
      .catch((error) => {
        setPrepareError(getParsedApiError(error));
        setIsPreparingSamples(false);
      });
  };

  const handleClearSamples = () => {
    if (!normalizedCode) {
      setPrepareError({
        title: bt(language, 'page.errors.missingCodeTitle'),
        message: bt(language, 'page.errors.missingClearSamples'),
        rawMessage: bt(language, 'page.errors.missingClearSamples'),
        category: 'missing_params',
      });
      return Promise.resolve();
    }

    setIsPreparingSamples(true);
    setPrepareError(null);
    return backtestApi.clearSamples(normalizedCode)
      .then(async () => {
        setPrepareResult(null);
        setRunResult(null);
        setSelectedRunId(null);
        setResults([]);
        setTotalResults(0);
        setOverallPerf(null);
        setStockPerf(null);
        await Promise.all([
          fetchSampleStatus(normalizedCode),
          fetchHistory(1, normalizedCode),
          fetchResults(1, normalizedCode, parsePositiveInt(evaluationBars, 10), null),
        ]);
        await fetchPerformance(normalizedCode, parsePositiveInt(evaluationBars, 10), { showNotice: true });
      })
      .catch((error) => {
        setPrepareError(getParsedApiError(error));
      })
      .finally(() => {
        setIsPreparingSamples(false);
      });
  };

  const handleClearResults = () => {
    if (!normalizedCode) {
      setRunError({
        title: bt(language, 'page.errors.missingCodeTitle'),
        message: bt(language, 'page.errors.missingClearResults'),
        rawMessage: bt(language, 'page.errors.missingClearResults'),
        category: 'missing_params',
      });
      return Promise.resolve();
    }

    setIsRunningHistoricalEval(true);
    setRunError(null);
    return backtestApi.clearResults(normalizedCode)
      .then(async () => {
        setRunResult(null);
        setSelectedRunId(null);
        setResults([]);
        setTotalResults(0);
        await Promise.all([
          fetchHistory(1, normalizedCode),
          fetchResults(1, normalizedCode, parsePositiveInt(evaluationBars, 10), null),
        ]);
        await fetchPerformance(normalizedCode, parsePositiveInt(evaluationBars, 10), { showNotice: true });
      })
      .catch((error) => {
        setRunError(getParsedApiError(error));
      })
      .finally(() => {
        setIsRunningHistoricalEval(false);
      });
  };

  const handleOpenHistoricalRun = async (run: BacktestRunHistoryItem) => {
    setSelectedRunId(run.id);
    setCodeFilter(run.code || '');
    setEvaluationBars(String(run.evaluationWindowTradingBars || run.evalWindowDays));
    setMaturityDays(String(run.maturityCalendarDays || run.minAgeDays));
    setForceReplaceResults(false);
    setPerformanceNotice(null);
    await Promise.all([
      fetchHistory(1, run.code || undefined),
      fetchSampleStatus(run.code || undefined),
      fetchResults(1, run.code || undefined, run.evalWindowDays, run.id),
    ]);
    await fetchPerformance(run.code || undefined, run.evalWindowDays, { showNotice: true });
  };

  const handleParseRuleStrategy = () => {
    if (!ruleStrategyText.trim()) {
      setRuleParseError({
        title: bt(language, 'page.errors.missingStrategyTitle'),
        message: bt(language, 'page.errors.missingStrategyText'),
        rawMessage: bt(language, 'page.errors.missingStrategyText'),
        category: 'missing_params',
      });
      return Promise.resolve();
    }

    setIsParsingRuleStrategy(true);
    setRuleParseError(null);
    setRuleRunError(null);
    setLastRuleRunResult(null);
    setAppliedRewriteText(null);
    return backtestApi.parseRuleStrategy({
      code: normalizedCode || undefined,
      strategyText: ruleStrategyText,
      startDate: ruleStartDate || undefined,
      endDate: ruleEndDate || undefined,
      initialCapital: Number.parseFloat(ruleInitialCapital) || undefined,
      feeBps: Number.parseFloat(ruleFeeBps) || 0,
      slippageBps: Number.parseFloat(ruleSlippageBps) || 0,
    })
      .then(async (response) => {
        setRuleParsedStrategy(response);
        const strategySpec = getStrategyPreviewSpec(response);
        const parsedSymbol = getPeriodicString(strategySpec, 'symbol');
        const parsedStartDate = getPeriodicString(strategySpec, 'start_date');
        const parsedEndDate = getPeriodicString(strategySpec, 'end_date');
        const parsedInitialCapital = getPeriodicNumber(strategySpec, 'initial_capital');
        const resolvedCode = parsedSymbol !== '--' ? parsedSymbol.toUpperCase() : normalizedCode;
        const resolvedStartDate = parsedStartDate !== '--' ? parsedStartDate : ruleStartDate;
        const resolvedEndDate = parsedEndDate !== '--' ? parsedEndDate : ruleEndDate;
        const resolvedInitialCapital = parsedInitialCapital != null ? String(parsedInitialCapital) : ruleInitialCapital;
        if (parsedSymbol !== '--') setCodeFilter(resolvedCode);
        if (parsedStartDate !== '--') setRuleStartDate(parsedStartDate);
        if (parsedEndDate !== '--') setRuleEndDate(parsedEndDate);
        if (parsedInitialCapital != null) setRuleInitialCapital(String(parsedInitialCapital));
        setRuleConfirmed(false);
        setSelectedRuleRunId(null);
        setRuleParseSignature(buildRuleParseSignature({
          code: resolvedCode,
          strategyText: ruleStrategyText,
          startDate: resolvedStartDate,
          endDate: resolvedEndDate,
          initialCapital: resolvedInitialCapital,
          feeBps: ruleFeeBps,
          slippageBps: ruleSlippageBps,
        }));
        setRuleCurrentStep('strategy');
        await fetchRuleHistory(1, resolvedCode || undefined);
      })
      .catch((error) => {
        setRuleParseError(getParsedApiError(error));
      })
      .finally(() => {
        setIsParsingRuleStrategy(false);
      });
  };

  const handleApplyRuleRewriteSuggestion = (value: string) => {
    setRuleStrategyText(value);
    setRuleParsedStrategy(null);
    setRuleParseError(null);
    setRuleRunError(null);
    setLastRuleRunResult(null);
    setRuleConfirmed(false);
    setRuleCurrentStep('setup');
    setRuleParseSignature(null);
    setAppliedRewriteText(value);
  };

  const handleRuleStrategyTextChange = (value: string) => {
    setRuleStrategyText(value);
    if (appliedRewriteText != null) {
      setAppliedRewriteText(null);
    }
  };

  const handleRunRuleBacktest = () => {
    if (ruleBacktestSubmitInFlightRef.current) {
      return Promise.resolve();
    }
    const strategySpec = getStrategyPreviewSpec(ruleParsedStrategy);
    const parsedSymbol = getPeriodicString(strategySpec, 'symbol');
    const resolvedCode = normalizedCode || (parsedSymbol !== '--' ? parsedSymbol.toUpperCase() : '');
    if (!resolvedCode) {
      const error = {
        title: bt(language, 'page.errors.missingCodeTitle'),
        message: bt(language, 'page.errors.missingRunCode'),
        rawMessage: bt(language, 'page.errors.missingRunCode'),
        category: 'missing_params',
      } satisfies ParsedApiError;
      setRuleRunError(error);
      setRuleRunFeedback(buildBacktestValidationFeedback(error.message, language));
      return Promise.resolve();
    }
    if (!ruleParsedStrategy) {
      const error = {
        title: bt(language, 'page.errors.needParsedStrategyTitle'),
        message: bt(language, 'page.errors.needParsedStrategy'),
        rawMessage: bt(language, 'page.errors.needParsedStrategy'),
        category: 'validation_error',
      } satisfies ParsedApiError;
      setRuleRunError(error);
      setRuleRunFeedback(buildBacktestValidationFeedback(error.message, language));
      return Promise.resolve();
    }
    if (isRuleParseStale) {
      const error = {
        title: bt(language, 'page.errors.staleParseTitle'),
        message: bt(language, 'page.errors.staleParse'),
        rawMessage: bt(language, 'page.errors.staleParse'),
        category: 'validation_error',
      } satisfies ParsedApiError;
      setRuleRunError(error);
      setRuleRunFeedback(buildBacktestValidationFeedback(error.message, language));
      return Promise.resolve();
    }
    if (!ruleConfirmed) {
      const error = {
        title: bt(language, 'page.errors.needConfirmTitle'),
        message: bt(language, 'page.errors.needConfirm'),
        rawMessage: bt(language, 'page.errors.needConfirm'),
        category: 'validation_error',
      } satisfies ParsedApiError;
      setRuleRunError(error);
      setRuleRunFeedback(buildBacktestValidationFeedback(error.message, language));
      return Promise.resolve();
    }
    if (!ruleStartDate || !ruleEndDate) {
      const error = {
        title: bt(language, 'page.errors.missingRangeTitle'),
        message: bt(language, 'page.errors.missingRange'),
        rawMessage: bt(language, 'page.errors.missingRange'),
        category: 'validation_error',
      } satisfies ParsedApiError;
      setRuleRunError(error);
      setRuleRunFeedback(buildBacktestValidationFeedback(error.message, language));
      return Promise.resolve();
    }
    if (ruleStartDate > ruleEndDate) {
      const error = {
        title: bt(language, 'page.errors.invalidRangeTitle'),
        message: bt(language, 'page.errors.invalidRange'),
        rawMessage: bt(language, 'page.errors.invalidRange'),
        category: 'validation_error',
      } satisfies ParsedApiError;
      setRuleRunError(error);
      setRuleRunFeedback(buildBacktestValidationFeedback(error.message, language));
      return Promise.resolve();
    }
    if (ruleBenchmarkMode === 'custom_code' && !ruleBenchmarkCode.trim()) {
      const error = {
        title: bt(language, 'page.errors.missingBenchmarkTitle'),
        message: bt(language, 'page.errors.missingBenchmark'),
        rawMessage: bt(language, 'page.errors.missingBenchmark'),
        category: 'validation_error',
      } satisfies ParsedApiError;
      setRuleRunError(error);
      setRuleRunFeedback(buildBacktestValidationFeedback(error.message, language));
      return Promise.resolve();
    }

    ruleBacktestSubmitInFlightRef.current = true;
    setIsSubmittingRuleBacktest(true);
    setRuleRunError(null);
    setLastRuleRunResult(null);
    setRuleRunFeedback(buildPendingBacktestRunFeedback(language, 'professional'));
    const monteCarloConfig = proMonteCarloEnabled
      ? {
        simulationCount: clampInteger(
          parsePositiveInt(
            proMonteCarloSimulationCount,
            Number.parseInt(PRO_MONTE_CARLO_SIMULATION_DEFAULT, 10),
            PRO_MONTE_CARLO_SIMULATION_MIN,
          ),
          PRO_MONTE_CARLO_SIMULATION_MIN,
          PRO_MONTE_CARLO_SIMULATION_MAX,
        ),
      }
      : undefined;
    const robustnessConfig = monteCarloConfig || proWalkForwardPresetEnabled
      ? {
        ...(monteCarloConfig ? { monteCarlo: monteCarloConfig } : {}),
        ...(proWalkForwardPresetEnabled ? { walkForward: PRO_WALK_FORWARD_PRESET } : {}),
      }
      : undefined;
    const requestPayload = {
      code: resolvedCode,
      strategyText: ruleStrategyText,
      parsedStrategy: ruleParsedStrategy.parsedStrategy,
      startDate: ruleStartDate,
      endDate: ruleEndDate,
      lookbackBars: parsePositiveInt(ruleLookbackBars, 252, 10),
      initialCapital: Number.parseFloat(ruleInitialCapital) || 100000,
      feeBps: Number.parseFloat(ruleFeeBps) || 0,
      slippageBps: Number.parseFloat(ruleSlippageBps) || 0,
      benchmarkMode: ruleBenchmarkMode,
      benchmarkCode: ruleBenchmarkMode === 'custom_code'
        ? ruleBenchmarkCode.trim().toUpperCase()
        : undefined,
      confirmed: true,
      waitForCompletion: false,
    };
    return backtestApi.runRuleBacktest(
      robustnessConfig
        ? { ...requestPayload, robustnessConfig }
        : requestPayload,
    )
      .then((response) => {
        setSelectedRuleRunId(response.id);
        setLastRuleRunResult(response);
        setRuleRunFeedback(buildBacktestResponseFeedback(response, language));
        void fetchRuleHistory(1, resolvedCode);
        if (shouldKeepRuleRunOnConfigPage(response)) {
          return;
        }
        navigate(`/backtest/results/${response.id}`, { state: { initialRun: response, resultMode: 'professional' } });
      })
      .catch((error) => {
        const parsedError = getParsedApiError(error);
        setRuleRunError(parsedError);
        setRuleRunFeedback(buildBacktestErrorFeedback(parsedError, language));
      })
      .finally(() => {
        ruleBacktestSubmitInFlightRef.current = false;
        setIsSubmittingRuleBacktest(false);
      });
  };

  const handleLaunchNormalRuleBacktest = () => {
    if (normalRuleLaunchInFlightRef.current || ruleBacktestSubmitInFlightRef.current) {
      return Promise.resolve();
    }
    if (!normalizedCode) {
      const error = {
        title: bt(language, 'page.errors.missingCodeTitle'),
        message: bt(language, 'page.errors.missingRunCode'),
        rawMessage: bt(language, 'page.errors.missingRunCode'),
        category: 'missing_params',
      } satisfies ParsedApiError;
      setRuleRunError(error);
      setRuleRunFeedback(buildBacktestValidationFeedback(error.message, language));
      return Promise.resolve();
    }
    if (!ruleStartDate || !ruleEndDate) {
      const error = {
        title: bt(language, 'page.errors.missingRangeTitle'),
        message: bt(language, 'page.errors.missingRange'),
        rawMessage: bt(language, 'page.errors.missingRange'),
        category: 'validation_error',
      } satisfies ParsedApiError;
      setRuleRunError(error);
      setRuleRunFeedback(buildBacktestValidationFeedback(error.message, language));
      return Promise.resolve();
    }
    if (ruleStartDate > ruleEndDate) {
      const error = {
        title: bt(language, 'page.errors.invalidRangeTitle'),
        message: bt(language, 'page.errors.invalidRange'),
        rawMessage: bt(language, 'page.errors.invalidRange'),
        category: 'validation_error',
      } satisfies ParsedApiError;
      setRuleRunError(error);
      setRuleRunFeedback(buildBacktestValidationFeedback(error.message, language));
      return Promise.resolve();
    }
    if (ruleBenchmarkMode === 'custom_code' && !ruleBenchmarkCode.trim()) {
      const error = {
        title: bt(language, 'page.errors.missingBenchmarkTitle'),
        message: bt(language, 'page.errors.missingBenchmark'),
        rawMessage: bt(language, 'page.errors.missingBenchmark'),
        category: 'validation_error',
      } satisfies ParsedApiError;
      setRuleRunError(error);
      setRuleRunFeedback(buildBacktestValidationFeedback(error.message, language));
      return Promise.resolve();
    }

    const strategyText = buildPointAndShootStrategyText(language, normalStrategyTemplate, {
      code: normalizedCode,
      startDate: ruleStartDate,
      endDate: ruleEndDate,
      initialCapital: ruleInitialCapital,
    });

    if (!strategyText.trim()) {
      const error = {
        title: bt(language, 'page.errors.missingStrategyTitle'),
        message: bt(language, 'page.errors.missingStrategyText'),
        rawMessage: bt(language, 'page.errors.missingStrategyText'),
        category: 'missing_params',
      } satisfies ParsedApiError;
      setRuleParseError(error);
      setRuleRunFeedback(buildBacktestValidationFeedback(error.message, language));
      return Promise.resolve();
    }

    normalRuleLaunchInFlightRef.current = true;
    setIsLaunchingNormalRuleBacktest(true);
    setRuleParseError(null);
    setRuleRunError(null);
    setLastRuleRunResult(null);
    setRuleRunFeedback(buildPendingBacktestRunFeedback(language, 'normal'));
    setAppliedRewriteText(null);
    setRuleStrategyText(strategyText);

    return backtestApi.parseRuleStrategy({
      code: normalizedCode,
      strategyText,
      startDate: ruleStartDate || undefined,
      endDate: ruleEndDate || undefined,
      initialCapital: Number.parseFloat(ruleInitialCapital) || undefined,
      feeBps: Number.parseFloat(ruleFeeBps) || 0,
      slippageBps: Number.parseFloat(ruleSlippageBps) || 0,
    })
      .then((parsed) => {
        setRuleParsedStrategy(parsed);
        setRuleParseSignature(buildRuleParseSignature({
          code: normalizedCode,
          strategyText,
          startDate: ruleStartDate,
          endDate: ruleEndDate,
          initialCapital: ruleInitialCapital,
          feeBps: ruleFeeBps,
          slippageBps: ruleSlippageBps,
        }));

        if (!parsed.executable && !parsed.parsedStrategy.executable) {
          setRuleConfirmed(false);
          setControlPanelMode('professional');
          const error = {
            title: language === 'en' ? 'Template needs professional review' : '模板需要专业模式复查',
            message: language === 'en'
              ? 'The selected template could not be organized into a runnable fixed-rule backtest flow. The page has switched to Professional mode so you can inspect and revise it.'
              : '当前模板暂时无法整理成可执行的固定规则回测流程，已自动切到专业模式以便继续检查和改写。',
            rawMessage: language === 'en'
              ? 'The selected template could not be organized into a runnable fixed-rule backtest flow.'
              : '当前模板暂时无法整理成可执行的固定规则回测流程。',
            category: 'validation_error',
          } satisfies ParsedApiError;
          setRuleParseError(error);
          setRuleRunFeedback(buildBacktestValidationFeedback(error.message, language));
          return;
        }

        setRuleConfirmed(true);
        setRuleCurrentStep('run');
        ruleBacktestSubmitInFlightRef.current = true;
        setIsSubmittingRuleBacktest(true);
        return backtestApi.runRuleBacktest({
          code: normalizedCode,
          strategyText,
          parsedStrategy: parsed.parsedStrategy,
          startDate: ruleStartDate,
          endDate: ruleEndDate,
          lookbackBars: parsePositiveInt(ruleLookbackBars, 252, 10),
          initialCapital: Number.parseFloat(ruleInitialCapital) || 100000,
          feeBps: Number.parseFloat(ruleFeeBps) || 0,
          slippageBps: Number.parseFloat(ruleSlippageBps) || 0,
          benchmarkMode: ruleBenchmarkMode,
          benchmarkCode: ruleBenchmarkMode === 'custom_code'
            ? ruleBenchmarkCode.trim().toUpperCase()
            : undefined,
          confirmed: true,
          waitForCompletion: false,
        })
          .then((response) => {
            setSelectedRuleRunId(response.id);
            setLastRuleRunResult(response);
            setRuleRunFeedback(buildBacktestResponseFeedback(response, language));
            void fetchRuleHistory(1, normalizedCode);
            if (shouldKeepRuleRunOnConfigPage(response)) {
              return;
            }
            navigate(`/backtest/results/${response.id}`, { state: { initialRun: response, resultMode: 'simple' } });
          })
          .catch((error) => {
            const parsedError = getParsedApiError(error);
            setRuleRunError(parsedError);
            setRuleRunFeedback(buildBacktestErrorFeedback(parsedError, language));
          })
          .finally(() => {
            ruleBacktestSubmitInFlightRef.current = false;
            setIsSubmittingRuleBacktest(false);
          });
      })
      .catch((error) => {
        const parsedError = getParsedApiError(error);
        setRuleParseError(parsedError);
        setRuleRunFeedback(buildBacktestErrorFeedback(parsedError, language));
      })
      .finally(() => {
        normalRuleLaunchInFlightRef.current = false;
        setIsLaunchingNormalRuleBacktest(false);
      });
  };

  const handleOpenRuleRun = (run: RuleBacktestHistoryItem) => {
    setSelectedRuleRunId(run.id);
    setCodeFilter(run.code);
    navigate(`/backtest/results/${run.id}`);
  };

  const handleResultsPageChange = (page: number) => {
    void fetchResults(page, normalizedCode || undefined, parsePositiveInt(evaluationBars, 10), selectedRunId);
  };

  const handleCodeKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') handleFilter();
  };

  const handleRuleCodeKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter') return;
    const nextCode = event.currentTarget.value.trim().toUpperCase();
    setRuleHistoryPage(1);
    void fetchRuleHistory(1, nextCode || undefined);
  };

  const handleToggleProMonteCarlo = (nextEnabled: boolean) => {
    setProMonteCarloEnabled(nextEnabled);
    if (nextEnabled) {
      setProMonteCarloSimulationCount((current) => current.trim() || PRO_MONTE_CARLO_SIMULATION_DEFAULT);
    }
  };

  const handleToggleProWalkForwardPreset = (nextEnabled: boolean) => {
    setProWalkForwardPresetEnabled(nextEnabled);
  };

  const handleProMonteCarloSimulationCountChange = (value: string) => {
    if (!value.trim()) {
      setProMonteCarloSimulationCount('');
      return;
    }
    const digitsOnly = value.replace(/[^\d]/g, '');
    if (!digitsOnly) {
      setProMonteCarloSimulationCount('');
      return;
    }
    setProMonteCarloSimulationCount(String(clampInteger(
      Number.parseInt(digitsOnly, 10),
      PRO_MONTE_CARLO_SIMULATION_MIN,
      PRO_MONTE_CARLO_SIMULATION_MAX,
    )));
  };

  const handleProMonteCarloSimulationCountBlur = () => {
    if (!proMonteCarloEnabled) return;
    setProMonteCarloSimulationCount((current) => {
      const parsed = Number.parseInt(current, 10);
      if (!Number.isFinite(parsed)) return PRO_MONTE_CARLO_SIMULATION_DEFAULT;
      return String(clampInteger(parsed, PRO_MONTE_CARLO_SIMULATION_MIN, PRO_MONTE_CARLO_SIMULATION_MAX));
    });
  };

  const resetRuleFlow = () => {
    setRuleParsedStrategy(null);
    setRuleConfirmed(false);
    setRuleRunError(null);
    setRuleRunFeedback(null);
    setRuleParseError(null);
    setRuleParseSignature(null);
    setLastRuleRunResult(null);
    setRuleCurrentStep('symbol');
    setAppliedRewriteText(null);
    setRuleBenchmarkMode('auto');
    setRuleBenchmarkCode('');
    setProMonteCarloEnabled(false);
    setProMonteCarloSimulationCount('');
    setProWalkForwardPresetEnabled(false);
  };
  const moduleTabs = (
    <div className="backtest-mode-toggle" role="tablist" aria-label={bt(language, 'page.moduleTabsLabel')}>
      <button
        ref={showRuleModuleButtonRef}
        type="button"
        role="tab"
        aria-selected={activeModule === 'rule'}
        className={`backtest-mode-toggle__button !min-h-[36px] md:!min-h-[32px]${activeModule === 'rule' ? ' is-active' : ''}`}
        onClick={handleShowRuleModuleClick}
        onPointerUp={handleShowRuleModulePointerUp}
      >
        {bt(language, 'page.ruleTab')}
      </button>
      <button
        ref={showHistoricalModuleButtonRef}
        type="button"
        role="tab"
        aria-selected={activeModule === 'historical'}
        className={`backtest-mode-toggle__button !min-h-[36px] md:!min-h-[32px]${activeModule === 'historical' ? ' is-active' : ''}`}
        onClick={handleShowHistoricalModuleClick}
        onPointerUp={handleShowHistoricalModulePointerUp}
      >
        {bt(language, 'page.historicalTab')}
      </button>
    </div>
  );

  const controlModeTabs = (
    <div className="backtest-mode-toggle" role="tablist" aria-label={bt(language, 'page.controlModeLabel')}>
      <button
        ref={showNormalModeButtonRef}
        type="button"
        role="tab"
        aria-selected={controlPanelMode === 'normal'}
        className={`backtest-mode-toggle__button !min-h-[36px] md:!min-h-[32px]${controlPanelMode === 'normal' ? ' is-active' : ''}`}
        onClick={handleShowNormalModeClick}
        onPointerUp={handleShowNormalModePointerUp}
      >
        {bt(language, 'page.normalMode')}
      </button>
      <button
        ref={showProfessionalModeButtonRef}
        type="button"
        role="tab"
        aria-selected={controlPanelMode === 'professional'}
        className={`backtest-mode-toggle__button !min-h-[36px] md:!min-h-[32px]${controlPanelMode === 'professional' ? ' is-active' : ''}`}
        onClick={handleShowProfessionalModeClick}
        onPointerUp={handleShowProfessionalModePointerUp}
      >
        {bt(language, 'page.professionalMode')}
      </button>
    </div>
  );
  const configPanelRadiusClass = 'rounded-[14px]';
  const normalModeRadiusTaxonomyClass = [
    "[&_[data-testid='normal-backtest-consolidated-card']]:rounded-[14px]",
    "[&_[data-testid='normal-backtest-template-insights']>div]:rounded-xl",
    "[&_[data-testid='normal-backtest-template-insights-loading']>div]:rounded-xl",
  ].join(' ');

  return (
    <div
      ref={surfaceRef}
      data-testid="backtest-bento-page"
      aria-hidden={shouldGuardA11y && !isSafariReady ? true : undefined}
      aria-live={shouldGuardA11y ? (isSafariReady ? 'polite' : 'off') : undefined}
      className={getSafariReadySurfaceClassName(isSafariReady, 'w-full flex-1 min-w-0 min-h-0 bg-transparent')}
    >
      <ConsumerWorkspaceScope className="min-h-0 flex-1">
        <ConsumerWorkspacePageShell
          data-testid="backtest-page-shell"
          className="flex-1 min-w-0 min-h-0"
        >
          <TerminalPageHeading
            data-testid="backtest-page-heading"
            title={language === 'en' ? 'Backtest Lab' : '回测实验室'}
          />
          <p data-testid="backtest-consumer-status-sentence" className="max-w-4xl text-sm leading-6 text-white/58">
            {language === 'en'
              ? 'Configure a strategy, check data readiness, then inspect the result preview or latest saved run before opening a full report.'
              : '先配置策略与区间，再核对数据就绪度；运行前可预览将展示的结果结构或最近保存记录。'}
          </p>
          <div
            data-testid="backtest-subnav"
            className={`w-full ${configPanelRadiusClass} border border-white/5 bg-white/[0.02] px-4 py-3 backdrop-blur-sm`}
          >
            <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <nav
                className="flex min-w-0 items-center gap-4 overflow-x-auto no-scrollbar"
                aria-label={bt(language, 'page.moduleTabsLabel')}
              >
                {moduleTabs}
              </nav>
              <nav
                className="flex min-w-0 items-center gap-4 overflow-x-auto no-scrollbar xl:justify-end"
                aria-label={bt(language, 'page.controlModeLabel')}
              >
                {controlModeTabs}
              </nav>
            </div>
          </div>
          <ObservationOnlyBoundary
            language={language}
            surface="backtest"
            testId="backtest-research-boundary"
            className={`w-full ${configPanelRadiusClass}`}
          />

          <main
            data-testid="backtest-v1-page"
            className="w-full flex-1 min-w-0 flex flex-col gap-6 bg-transparent"
          >
            {scannerHandoff ? (
              <section className={`${configPanelRadiusClass} border border-sky-400/15 bg-sky-400/10 px-4 py-3 text-sm text-sky-50`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold">{language === 'en' ? 'From scanner' : '来自扫描器'}</span>
                  <span>{scannerHandoff.symbol}</span>
                  {scannerHandoff.market ? <span className="text-sky-100/75">· {scannerHandoff.market}</span> : null}
                  {scannerHandoff.scannerRunId ? <span className="text-sky-100/75">· {bt(language, 'scannerRunMeta', { runId: scannerHandoff.scannerRunId })}</span> : null}
                  {scannerHandoff.scannerRank ? <span className="text-sky-100/75">· {bt(language, 'scannerRankMeta', { rank: scannerHandoff.scannerRank })}</span> : null}
                  {scannerHandoff.scannerProfile ? <span className="text-sky-100/75">· {scannerHandoff.scannerProfile}</span> : null}
                </div>
              </section>
            ) : null}
            <LazyMotion features={domAnimation}>
          <AnimatePresence mode="wait" initial={false}>
            <m.div
              key={activeModule === 'rule' ? `${activeModule}-${controlPanelMode}` : activeModule}
              className={`backtest-v1-stage backtest-v1-stage--${activeModule} w-full min-w-0 ${normalModeRadiusTaxonomyClass}`}
              data-testid="backtest-v1-stage"
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{
                duration: 0.26,
                ease: [0.22, 1, 0.36, 1] as const,
              }}
            >
              <Suspense
                fallback={(
                  <section
                    data-testid="backtest-workspace-loading"
                    aria-busy="true"
                    className="workspace-loading-panel border border-white/10 bg-white/[0.02] backdrop-blur-md"
                  >
                    <div className="workspace-loading-panel__header">
                      <span className="workspace-loading-panel__status">
                        {language === 'en' ? 'Loading workspace' : '加载工作区'}
                      </span>
                      <span className="text-xs text-white/45">
                        {language === 'en' ? 'Preparing backtest surface' : '正在准备回测界面'}
                      </span>
                    </div>
                    <div className="workspace-loading-panel__hero min-h-[240px]" />
                    <div className="workspace-loading-panel__lines" aria-hidden="true">
                      <span />
                      <span />
                      <span />
                    </div>
                  </section>
                )}
              >
                {activeModule === 'historical' ? (
                  <HistoricalEvaluationPanel
                    normalizedCode={normalizedCode}
                    codeFilter={codeFilter}
                    onCodeChange={setCodeFilter}
                    onCodeEnter={handleCodeKeyDown}
                    evaluationBars={evaluationBars}
                    onEvaluationBarsChange={setEvaluationBars}
                    maturityDays={maturityDays}
                    onMaturityDaysChange={setMaturityDays}
                    samplePreset={samplePreset}
                    onSamplePresetChange={setSamplePreset}
                    customSampleCount={customSampleCount}
                    onCustomSampleCountChange={setCustomSampleCount}
                    resolvedSampleCount={resolvedSampleCount}
                    forceReplaceResults={forceReplaceResults}
                    onForceReplaceResultsChange={setForceReplaceResults}
                    onFilter={handleFilter}
                    onPrepareSamples={() => handlePrepareSamples({ forceRefresh: false })}
                    onRebuildSamples={handleRebuildSamples}
                    onClearSamples={handleClearSamples}
                    onRunEvaluation={handleRunHistoricalEvaluation}
                    onClearResults={handleClearResults}
                    isPreparingSamples={isPreparingSamples}
                    isRunningHistoricalEval={isRunningHistoricalEval}
                    runResult={runResult}
                    runError={runError}
                    prepareResult={prepareResult}
                    prepareError={prepareError}
                    sampleStatus={sampleStatus}
                    sampleStatusError={sampleStatusError}
                    historicalAssumptions={historicalAssumptions}
                    historicalSourceMetadata={historicalSourceMetadata}
                    historicalSampleTransparency={historicalSampleTransparency}
                    isLoadingSampleStatus={isLoadingSampleStatus}
                    isLoadingPerf={isLoadingPerf}
                    historicalSummaryItems={historicalSummaryItems}
                    performanceNotice={performanceNotice}
                    results={results}
                    totalResults={totalResults}
                    currentPage={currentPage}
                    pageSize={HISTORICAL_PAGE_SIZE}
                    onChangeResultsPage={handleResultsPageChange}
                    pageError={pageError}
                    isLoadingResults={isLoadingResults}
                    historyItems={historyItems}
                    historyTotal={historyTotal}
                    historyPage={historyPage}
                    historyPageSize={HISTORY_PAGE_SIZE}
                    onChangeHistoryPage={(page) => {
                      setHistoryPage(page);
                      void fetchHistory(page, normalizedCode || undefined);
                    }}
                    onOpenHistoricalRun={handleOpenHistoricalRun}
                    selectedRunId={selectedRunId}
                    historyError={historyError}
                    isLoadingHistory={isLoadingHistory}
                    panelMode={controlPanelMode}
                  />
                ) : (
                  controlPanelMode === 'normal' ? (
                    <NormalBacktestWorkspace
                      language={language}
                      code={normalizedCode}
                      onCodeChange={setCodeFilter}
                      startDate={ruleStartDate}
                      onStartDateChange={setRuleStartDate}
                      endDate={ruleEndDate}
                      onEndDateChange={setRuleEndDate}
                      initialCapital={ruleInitialCapital}
                      onInitialCapitalChange={setRuleInitialCapital}
                      feeBps={ruleFeeBps}
                      onFeeBpsChange={setRuleFeeBps}
                      slippageBps={ruleSlippageBps}
                      onSlippageBpsChange={setRuleSlippageBps}
                      benchmarkMode={ruleBenchmarkMode}
                      onBenchmarkModeChange={setRuleBenchmarkMode}
                      benchmarkCode={ruleBenchmarkCode}
                      onBenchmarkCodeChange={setRuleBenchmarkCode}
                      strategyTemplate={normalStrategyTemplate}
                      onStrategyTemplateChange={setNormalStrategyTemplate}
                      onLaunch={handleLaunchNormalRuleBacktest}
                      isLaunching={isLaunchingNormalRuleBacktest || isSubmittingRuleBacktest || isParsingRuleStrategy}
                      parseError={ruleParseError}
                      runError={ruleRunError}
                      runReadiness={lastRuleRunResult?.executionReadiness || null}
                      historicalOhlcvReadiness={lastRuleRunResult?.historicalOhlcvReadiness || null}
                      noAdviceDisclosure={lastRuleRunResult?.noAdviceDisclosure || null}
                      hasRunAttempt={Boolean(lastRuleRunResult)}
                      runFeedback={ruleRunFeedback}
                    />
                  ) : (
                    <ProBacktestWorkspace
                      language={language}
                      code={normalizedCode}
                      onCodeChange={setCodeFilter}
                      onCodeEnter={handleRuleCodeKeyDown}
                      strategyText={ruleStrategyText}
                      onStrategyTextChange={handleRuleStrategyTextChange}
                      startDate={ruleStartDate}
                      onStartDateChange={setRuleStartDate}
                      endDate={ruleEndDate}
                      onEndDateChange={setRuleEndDate}
                      initialCapital={ruleInitialCapital}
                      onInitialCapitalChange={setRuleInitialCapital}
                      lookbackBars={ruleLookbackBars}
                      onLookbackBarsChange={setRuleLookbackBars}
                      feeBps={ruleFeeBps}
                      onFeeBpsChange={setRuleFeeBps}
                      slippageBps={ruleSlippageBps}
                      onSlippageBpsChange={setRuleSlippageBps}
                      benchmarkMode={ruleBenchmarkMode}
                      onBenchmarkModeChange={setRuleBenchmarkMode}
                      benchmarkCode={ruleBenchmarkCode}
                      onBenchmarkCodeChange={setRuleBenchmarkCode}
                      monteCarloEnabled={proMonteCarloEnabled}
                      onToggleMonteCarloEnabled={handleToggleProMonteCarlo}
                      monteCarloSimulationCount={proMonteCarloSimulationCount}
                      onMonteCarloSimulationCountChange={handleProMonteCarloSimulationCountChange}
                      onMonteCarloSimulationCountBlur={handleProMonteCarloSimulationCountBlur}
                      walkForwardPresetEnabled={proWalkForwardPresetEnabled}
                      onToggleWalkForwardPresetEnabled={handleToggleProWalkForwardPreset}
                      parsedStrategy={ruleParsedStrategy}
                      confirmed={ruleConfirmed}
                      onToggleConfirmed={setRuleConfirmed}
                      isParsing={isParsingRuleStrategy}
                      parseError={ruleParseError}
                      onParse={handleParseRuleStrategy}
                      isSubmitting={isSubmittingRuleBacktest}
                      runError={ruleRunError}
                      onRun={handleRunRuleBacktest}
                      onReset={resetRuleFlow}
                      runReadiness={lastRuleRunResult?.executionReadiness || null}
                      historicalOhlcvReadiness={lastRuleRunResult?.historicalOhlcvReadiness || null}
                      noAdviceDisclosure={lastRuleRunResult?.noAdviceDisclosure || null}
                      hasRunAttempt={Boolean(lastRuleRunResult)}
                      runFeedback={ruleRunFeedback}
                      historyItems={ruleHistoryItems}
                      historyTotal={ruleHistoryTotal}
                      historyPage={ruleHistoryPage}
                      selectedRunId={selectedRuleRunId}
                      isLoadingHistory={isLoadingRuleHistory}
                      historyError={ruleHistoryError}
                      onRefreshHistory={() => void fetchRuleHistory(1, normalizedCode || undefined)}
                      onOpenHistoryRun={handleOpenRuleRun}
                      previewAssumptions={previewRuleAssumptions}
                      currentStep={ruleCurrentStep}
                      onStepChange={setRuleCurrentStep}
                      parseStale={isRuleParseStale}
                      onApplyRewriteSuggestion={handleApplyRuleRewriteSuggestion}
                      appliedRewriteText={appliedRewriteText}
                    />
                  )
                )}
              </Suspense>
            </m.div>
          </AnimatePresence>
            </LazyMotion>
          </main>
        </ConsumerWorkspacePageShell>
      </ConsumerWorkspaceScope>
    </div>
  );
};

export default BacktestPage;
