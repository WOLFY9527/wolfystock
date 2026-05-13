import type React from 'react';
import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useLocation, useNavigate } from 'react-router-dom';
import { backtestApi } from '../api/backtest';
import type { ParsedApiError } from '../api/error';
import { getApiErrorMessage, getParsedApiError } from '../api/error';
import type { RuleWizardStep } from '../components/backtest/DeterministicBacktestFlow';
import NormalBacktestWorkspace from '../components/backtest/NormalBacktestWorkspace';
import {
  getDefaultRuleDateRange,
  getPeriodicNumber,
  getPeriodicString,
  type RuleBenchmarkMode,
  getStrategyPreviewSpec,
  parsePositiveInt,
} from '../components/backtest/shared';
import {
  buildPointAndShootStrategyText,
  type NormalStrategyTemplate,
} from '../components/backtest/strategyCatalog';
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
import { TerminalPageHeading, TerminalPageShell } from '../components/terminal';

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

const BacktestPage: React.FC = () => {
  const { isReady: isSafariReady, surfaceRef } = useSafariRenderReady();
  const shouldGuardA11y = shouldApplySafariA11yGuard();
  const navigate = useNavigate();
  const location = useLocation();
  const { language } = useI18n();
  const scannerHandoff = useMemo(() => parseScannerBacktestHandoff(location.search), [location.search]);

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

  const [ruleStrategyText, setRuleStrategyText] = useState(
    bt(language, 'page.defaultStrategyText'),
  );
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
  const [ruleHistoryItems, setRuleHistoryItems] = useState<RuleBacktestHistoryItem[]>([]);
  const [ruleHistoryTotal, setRuleHistoryTotal] = useState(0);
  const [ruleHistoryPage, setRuleHistoryPage] = useState(1);
  const [isLoadingRuleHistory, setIsLoadingRuleHistory] = useState(false);
  const [ruleHistoryError, setRuleHistoryError] = useState<ParsedApiError | null>(null);
  const [selectedRuleRunId, setSelectedRuleRunId] = useState<number | null>(null);
  const [ruleCurrentStep, setRuleCurrentStep] = useState<RuleWizardStep>('symbol');
  const [ruleParseSignature, setRuleParseSignature] = useState<string | null>(null);
  const [appliedRewriteText, setAppliedRewriteText] = useState<string | null>(null);
  const showRuleModuleButton = useSafariWarmActivation<HTMLButtonElement>(() => setActiveModule('rule'));
  const showHistoricalModuleButton = useSafariWarmActivation<HTMLButtonElement>(() => setActiveModule('historical'));
  const showNormalModeButton = useSafariWarmActivation<HTMLButtonElement>(() => setControlPanelMode('normal'));
  const showProfessionalModeButton = useSafariWarmActivation<HTMLButtonElement>(() => setControlPanelMode('professional'));

  const normalizedCode = String(codeFilter || '').trim().toUpperCase();
  const resolvedSampleCount = samplePreset === 'custom'
    ? parsePositiveInt(customSampleCount, 252)
    : parsePositiveInt(samplePreset, 60);

  const currentRuleParseSignature = useMemo(() => buildRuleParseSignature({
    code: normalizedCode,
    strategyText: ruleStrategyText,
    startDate: ruleStartDate,
    endDate: ruleEndDate,
    initialCapital: ruleInitialCapital,
    feeBps: ruleFeeBps,
    slippageBps: ruleSlippageBps,
  }), [normalizedCode, ruleEndDate, ruleFeeBps, ruleInitialCapital, ruleSlippageBps, ruleStartDate, ruleStrategyText]);

  const isRuleParseStale = Boolean(ruleParsedStrategy && ruleParseSignature && ruleParseSignature !== currentRuleParseSignature);
  const normalStrategyPreview = useMemo(() => buildPointAndShootStrategyText(language, normalStrategyTemplate, {
    code: normalizedCode,
    startDate: ruleStartDate,
    endDate: ruleEndDate,
    initialCapital: ruleInitialCapital,
  }), [language, normalStrategyTemplate, normalizedCode, ruleEndDate, ruleInitialCapital, ruleStartDate]);

  const historicalAssumptions = runResult?.executionAssumptions
    || overallPerf?.executionAssumptions
    || results[0]?.executionAssumptions
    || null;

  const historicalPerfSnapshot = stockPerf || overallPerf;
  const selectedHistoricalRun = useMemo(
    () => historyItems.find((item) => item.id === selectedRunId) || null,
    [historyItems, selectedRunId],
  );

  const historicalSourceMetadata = useMemo(() => {
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
  }, [overallPerf, prepareResult, runResult, sampleStatus, selectedHistoricalRun, stockPerf]);

  const historicalSummaryItems = useMemo(() => ([
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
  ]), [
    language,
    historicalPerfSnapshot?.completedCount,
    historicalPerfSnapshot?.directionAccuracyPct,
    historicalPerfSnapshot?.avgSimulatedReturnPct,
    historicalPerfSnapshot?.avgStockReturnPct,
    historicalPerfSnapshot?.totalEvaluations,
    historicalPerfSnapshot?.winRatePct,
    sampleStatus?.preparedCount,
    sampleStatus?.preparedEndDate,
    sampleStatus?.preparedStartDate,
  ]);

  const historicalSampleTransparency = useMemo(() => {
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
  }, [
    language,
    historicalSourceMetadata.fallbackUsed,
    historicalSourceMetadata.resolvedSource,
    prepareResult?.excludedRecentMessage,
    prepareResult?.latestEligibleSampleDate,
    prepareResult?.latestPreparedSampleDate,
    prepareResult?.pricingFallbackUsed,
    prepareResult?.pricingResolvedSource,
    runResult?.excludedRecentMessage,
    runResult?.latestEligibleSampleDate,
    runResult?.latestPreparedSampleDate,
    runResult?.pricingFallbackUsed,
    runResult?.pricingResolvedSource,
    sampleStatus?.excludedRecentMessage,
    sampleStatus?.latestEligibleSampleDate,
    sampleStatus?.latestPreparedSampleDate,
    sampleStatus?.pricingFallbackUsed,
    sampleStatus?.pricingResolvedSource,
  ]);

  const previewRuleAssumptions = useMemo<AssumptionMap>(() => ({
    timeframe: ruleParsedStrategy?.parsedStrategy.timeframe || 'daily',
    price_basis: 'close',
    signal_evaluation_timing: 'bar close',
    entry_fill_timing: 'next bar open',
    exit_fill_timing: 'next bar open; final bar may force close at close',
    position_sizing: '100% capital when long, otherwise cash',
    fee_bps_per_side: Number.parseFloat(ruleFeeBps) || 0,
    slippage_bps_per_side: Number.parseFloat(ruleSlippageBps) || 0,
  }), [ruleFeeBps, ruleParsedStrategy?.parsedStrategy.timeframe, ruleSlippageBps]);

  const applyRuleRunDraft = useCallback((data: RuleBacktestRunResponse) => {
    const parsedStrategyPayload = data.parsedStrategy as unknown as Record<string, unknown>;
    const detectedStrategyFamily = data.parsedStrategy.detectedStrategyFamily
      ?? (typeof parsedStrategyPayload.detected_strategy_family === 'string' ? parsedStrategyPayload.detected_strategy_family : undefined);
    const unsupportedExtensions = data.parsedStrategy.unsupportedExtensions
      ?? (Array.isArray(parsedStrategyPayload.unsupported_extensions) ? parsedStrategyPayload.unsupported_extensions as Array<Record<string, unknown>> : undefined);
    const coreIntentSummary = data.parsedStrategy.coreIntentSummary
      ?? (typeof parsedStrategyPayload.core_intent_summary === 'string' ? parsedStrategyPayload.core_intent_summary : undefined);
    const interpretationConfidence = data.parsedStrategy.interpretationConfidence
      ?? (typeof parsedStrategyPayload.interpretation_confidence === 'number' ? parsedStrategyPayload.interpretation_confidence : undefined);
    setSelectedRuleRunId(data.id);
    setActiveModule('rule');
    setCodeFilter(data.code);
    setRuleStrategyText(data.strategyText);
    setRuleStartDate(data.startDate || '');
    setRuleEndDate(data.endDate || '');
    setRuleLookbackBars(String(data.lookbackBars || 252));
    setRuleInitialCapital(String(data.initialCapital || 100000));
    setRuleFeeBps(String(data.feeBps ?? 0));
    setRuleSlippageBps(String(data.slippageBps ?? 0));
    setRuleBenchmarkMode((data.benchmarkMode as RuleBenchmarkMode | undefined) || 'auto');
    setRuleBenchmarkCode(data.benchmarkCode || '');
    const parsedStrategySummary = (data.summary.parsedStrategySummary as Record<string, string> | undefined)
      || data.parsedStrategy.summary;
    setRuleParsedStrategy({
      code: data.code,
      strategyText: data.strategyText,
      parsedStrategy: {
        ...data.parsedStrategy,
        summary: parsedStrategySummary,
      },
      normalizedStrategyFamily: String((data.parsedStrategy.strategySpec as Record<string, unknown> | undefined)?.strategyType || data.parsedStrategy.strategyKind || ''),
      executable: Boolean(data.parsedStrategy.executable),
      normalizationState: data.parsedStrategy.normalizationState,
      assumptions: data.parsedStrategy.assumptions,
      assumptionGroups: data.parsedStrategy.assumptionGroups,
      detectedStrategyFamily,
      unsupportedReason: data.parsedStrategy.unsupportedReason,
      unsupportedDetails: data.parsedStrategy.unsupportedDetails,
      unsupportedExtensions,
      coreIntentSummary,
      interpretationConfidence,
      supportedPortionSummary: data.parsedStrategy.supportedPortionSummary,
      rewriteSuggestions: data.parsedStrategy.rewriteSuggestions,
      parseWarnings: data.parsedStrategy.parseWarnings,
      confidence: data.parsedConfidence ?? data.parsedStrategy.confidence ?? 0,
      needsConfirmation: data.needsConfirmation,
      ambiguities: data.warnings,
      summary: parsedStrategySummary,
      maxLookback: data.parsedStrategy.maxLookback,
    });
    setRuleParseSignature(buildRuleParseSignature({
      code: data.code,
      strategyText: data.strategyText,
      startDate: data.startDate || '',
      endDate: data.endDate || '',
      initialCapital: String(data.initialCapital || 100000),
      feeBps: String(data.feeBps ?? 0),
      slippageBps: String(data.slippageBps ?? 0),
    }));
    setRuleConfirmed(true);
    setRuleCurrentStep('strategy');
    setAppliedRewriteText(null);
  }, []);

  const fetchResults = useCallback(async (page = 1, code?: string, windowBars?: number, runId?: number | null) => {
    setIsLoadingResults(true);
    try {
      const response = await backtestApi.getResults({
        code: code || undefined,
        evalWindowDays: windowBars,
        runId: runId || undefined,
        page,
        limit: HISTORICAL_PAGE_SIZE,
      });
      setResults(response.items);
      setTotalResults(response.total);
      setCurrentPage(response.page);
      setPageError(null);
    } catch (error) {
      setPageError(getParsedApiError(error));
    } finally {
      setIsLoadingResults(false);
    }
  }, []);

  const fetchHistory = useCallback(async (page = 1, code?: string) => {
    setIsLoadingHistory(true);
    try {
      const response = await backtestApi.getHistory({ code: code || undefined, page, limit: HISTORY_PAGE_SIZE });
      setHistoryItems(response.items);
      setHistoryTotal(response.total);
      setHistoryPage(response.page);
      setHistoryError(null);
    } catch (error) {
      setHistoryError(getParsedApiError(error));
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  const fetchSampleStatus = useCallback(async (code?: string) => {
    if (!code) {
      setSampleStatus(null);
      setSampleStatusError(null);
      return;
    }
    setIsLoadingSampleStatus(true);
    try {
      const response = await backtestApi.getSampleStatus(code);
      setSampleStatus(response);
      setSampleStatusError(null);
    } catch (error) {
      setSampleStatus(null);
      setSampleStatusError(getParsedApiError(error));
    } finally {
      setIsLoadingSampleStatus(false);
    }
  }, []);

  const fetchRuleHistory = useCallback(async (page = 1, code?: string) => {
    setIsLoadingRuleHistory(true);
    try {
      const response = await backtestApi.getRuleBacktestRuns({ code: code || undefined, page, limit: RULE_HISTORY_PAGE_SIZE });
      setRuleHistoryItems(response.items);
      setRuleHistoryTotal(response.total);
      setRuleHistoryPage(response.page);
      setRuleHistoryError(null);
    } catch (error) {
      setRuleHistoryError(getParsedApiError(error));
    } finally {
      setIsLoadingRuleHistory(false);
    }
  }, []);

  useEffect(() => {
    const state = location.state as BacktestPageLocationState | null;
    const draftRun = state?.draftRun;
    if (draftRun) {
      applyRuleRunDraft(draftRun);
      return;
    }

    if (scannerHandoff?.symbol) {
      setActiveModule('rule');
      setControlPanelMode('normal');
      setCodeFilter(scannerHandoff.symbol);
      return;
    }

    const prefillCode = state?.prefillCode?.trim().toUpperCase();
    if (!prefillCode) return;

    setActiveModule('rule');
    setCodeFilter(prefillCode);
  }, [applyRuleRunDraft, location.state, scannerHandoff]);

  const fetchPerformance = useCallback(async (code?: string, windowBars?: number, options: { showNotice?: boolean } = {}) => {
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
  }, [language]);

  useEffect(() => {
    const init = async () => {
      try {
        const overall = await backtestApi.getOverallPerformance();
        setOverallPerf(overall);
        const defaultWindow = overall?.evalWindowDays;
        if (defaultWindow) setEvaluationBars(String(defaultWindow));
        setPerformanceNotice(null);
      } catch (error) {
      setPerformanceNotice({
        tone: 'danger',
        message: getApiErrorMessage(error),
      });
      } finally {
        void fetchResults(1, undefined, undefined, null);
        void fetchHistory(1, undefined);
        void fetchRuleHistory(1, undefined);
      }
    };
    void init();
  }, [fetchHistory, fetchResults, fetchRuleHistory]);

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

  const handleRunHistoricalEvaluation = async () => {
    setIsRunningHistoricalEval(true);
    setRunResult(null);
    setRunError(null);
    setPrepareResult(null);
    setPrepareError(null);
    try {
      const windowBars = parsePositiveInt(evaluationBars, 10);
      const maturityCalendarDays = parsePositiveInt(maturityDays, 14, 0);
      const response = await backtestApi.run({
        code: normalizedCode || undefined,
        force: forceReplaceResults,
        evalWindowDays: windowBars,
        minAgeDays: maturityCalendarDays,
      });
      setRunResult(response);
      setSelectedRunId(response.runId ?? null);
      await Promise.all([
        fetchResults(1, normalizedCode || undefined, windowBars, response.runId ?? null),
        fetchHistory(1, normalizedCode || undefined),
        fetchSampleStatus(normalizedCode || undefined),
      ]);
      await fetchPerformance(normalizedCode || undefined, windowBars, { showNotice: true });
    } catch (error) {
      setRunError(getParsedApiError(error));
    } finally {
      setIsRunningHistoricalEval(false);
    }
  };

  const handlePrepareSamples = async (options: { forceRefresh?: boolean } = {}) => {
    if (!normalizedCode) {
      setPrepareError({
        title: bt(language, 'page.errors.missingCodeTitle'),
        message: bt(language, 'page.errors.missingPrepareSamples'),
        rawMessage: bt(language, 'page.errors.missingPrepareSamples'),
        category: 'missing_params',
      });
      return;
    }

    setIsPreparingSamples(true);
    setPrepareResult(null);
    setPrepareError(null);
    try {
      const response = await backtestApi.prepareSamples({
        code: normalizedCode,
        sampleCount: resolvedSampleCount,
        evalWindowDays: parsePositiveInt(evaluationBars, 10),
        minAgeDays: parsePositiveInt(maturityDays, 14, 0),
        forceRefresh: options.forceRefresh || false,
      });
      setPrepareResult(response);
      await Promise.all([
        fetchSampleStatus(normalizedCode),
        fetchHistory(1, normalizedCode),
      ]);
    } catch (error) {
      setPrepareError(getParsedApiError(error));
    } finally {
      setIsPreparingSamples(false);
    }
  };

  const handleRebuildSamples = async () => {
    if (!normalizedCode) {
      setPrepareError({
        title: bt(language, 'page.errors.missingCodeTitle'),
        message: bt(language, 'page.errors.missingRebuildSamples'),
        rawMessage: bt(language, 'page.errors.missingRebuildSamples'),
        category: 'missing_params',
      });
      return;
    }

    setIsPreparingSamples(true);
    setPrepareResult(null);
    setPrepareError(null);
    try {
      await backtestApi.clearSamples(normalizedCode);
      await handlePrepareSamples({ forceRefresh: false });
      await fetchResults(1, normalizedCode, parsePositiveInt(evaluationBars, 10), null);
    } catch (error) {
      setPrepareError(getParsedApiError(error));
      setIsPreparingSamples(false);
    }
  };

  const handleClearSamples = async () => {
    if (!normalizedCode) {
      setPrepareError({
        title: bt(language, 'page.errors.missingCodeTitle'),
        message: bt(language, 'page.errors.missingClearSamples'),
        rawMessage: bt(language, 'page.errors.missingClearSamples'),
        category: 'missing_params',
      });
      return;
    }

    setIsPreparingSamples(true);
    setPrepareError(null);
    try {
      await backtestApi.clearSamples(normalizedCode);
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
    } catch (error) {
      setPrepareError(getParsedApiError(error));
    } finally {
      setIsPreparingSamples(false);
    }
  };

  const handleClearResults = async () => {
    if (!normalizedCode) {
      setRunError({
        title: bt(language, 'page.errors.missingCodeTitle'),
        message: bt(language, 'page.errors.missingClearResults'),
        rawMessage: bt(language, 'page.errors.missingClearResults'),
        category: 'missing_params',
      });
      return;
    }

    setIsRunningHistoricalEval(true);
    setRunError(null);
    try {
      await backtestApi.clearResults(normalizedCode);
      setRunResult(null);
      setSelectedRunId(null);
      setResults([]);
      setTotalResults(0);
      await Promise.all([
        fetchHistory(1, normalizedCode),
        fetchResults(1, normalizedCode, parsePositiveInt(evaluationBars, 10), null),
      ]);
      await fetchPerformance(normalizedCode, parsePositiveInt(evaluationBars, 10), { showNotice: true });
    } catch (error) {
      setRunError(getParsedApiError(error));
    } finally {
      setIsRunningHistoricalEval(false);
    }
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

  const handleParseRuleStrategy = async () => {
    if (!ruleStrategyText.trim()) {
      setRuleParseError({
        title: bt(language, 'page.errors.missingStrategyTitle'),
        message: bt(language, 'page.errors.missingStrategyText'),
        rawMessage: bt(language, 'page.errors.missingStrategyText'),
        category: 'missing_params',
      });
      return;
    }

    setIsParsingRuleStrategy(true);
    setRuleParseError(null);
    setRuleRunError(null);
    setAppliedRewriteText(null);
    try {
      const response = await backtestApi.parseRuleStrategy({
        code: normalizedCode || undefined,
        strategyText: ruleStrategyText,
        startDate: ruleStartDate || undefined,
        endDate: ruleEndDate || undefined,
        initialCapital: Number.parseFloat(ruleInitialCapital) || undefined,
        feeBps: Number.parseFloat(ruleFeeBps) || 0,
        slippageBps: Number.parseFloat(ruleSlippageBps) || 0,
      });
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
    } catch (error) {
      setRuleParseError(getParsedApiError(error));
    } finally {
      setIsParsingRuleStrategy(false);
    }
  };

  const handleApplyRuleRewriteSuggestion = useCallback((value: string) => {
    setRuleStrategyText(value);
    setRuleParsedStrategy(null);
    setRuleParseError(null);
    setRuleRunError(null);
    setRuleConfirmed(false);
    setRuleCurrentStep('setup');
    setRuleParseSignature(null);
    setAppliedRewriteText(value);
  }, []);

  const handleRuleStrategyTextChange = useCallback((value: string) => {
    setRuleStrategyText(value);
    if (appliedRewriteText != null) {
      setAppliedRewriteText(null);
    }
  }, [appliedRewriteText]);

  const handleRunRuleBacktest = async () => {
    const strategySpec = getStrategyPreviewSpec(ruleParsedStrategy);
    const parsedSymbol = getPeriodicString(strategySpec, 'symbol');
    const resolvedCode = normalizedCode || (parsedSymbol !== '--' ? parsedSymbol.toUpperCase() : '');
    if (!resolvedCode) {
      setRuleRunError({
        title: bt(language, 'page.errors.missingCodeTitle'),
        message: bt(language, 'page.errors.missingRunCode'),
        rawMessage: bt(language, 'page.errors.missingRunCode'),
        category: 'missing_params',
      });
      return;
    }
    if (!ruleParsedStrategy) {
      setRuleRunError({
        title: bt(language, 'page.errors.needParsedStrategyTitle'),
        message: bt(language, 'page.errors.needParsedStrategy'),
        rawMessage: bt(language, 'page.errors.needParsedStrategy'),
        category: 'validation_error',
      });
      return;
    }
    if (isRuleParseStale) {
      setRuleRunError({
        title: bt(language, 'page.errors.staleParseTitle'),
        message: bt(language, 'page.errors.staleParse'),
        rawMessage: bt(language, 'page.errors.staleParse'),
        category: 'validation_error',
      });
      return;
    }
    if (!ruleConfirmed) {
      setRuleRunError({
        title: bt(language, 'page.errors.needConfirmTitle'),
        message: bt(language, 'page.errors.needConfirm'),
        rawMessage: bt(language, 'page.errors.needConfirm'),
        category: 'validation_error',
      });
      return;
    }
    if (!ruleStartDate || !ruleEndDate) {
      setRuleRunError({
        title: bt(language, 'page.errors.missingRangeTitle'),
        message: bt(language, 'page.errors.missingRange'),
        rawMessage: bt(language, 'page.errors.missingRange'),
        category: 'validation_error',
      });
      return;
    }
    if (ruleStartDate > ruleEndDate) {
      setRuleRunError({
        title: bt(language, 'page.errors.invalidRangeTitle'),
        message: bt(language, 'page.errors.invalidRange'),
        rawMessage: bt(language, 'page.errors.invalidRange'),
        category: 'validation_error',
      });
      return;
    }
    if (ruleBenchmarkMode === 'custom_code' && !ruleBenchmarkCode.trim()) {
      setRuleRunError({
        title: bt(language, 'page.errors.missingBenchmarkTitle'),
        message: bt(language, 'page.errors.missingBenchmark'),
        rawMessage: bt(language, 'page.errors.missingBenchmark'),
        category: 'validation_error',
      });
      return;
    }

    setIsSubmittingRuleBacktest(true);
    setRuleRunError(null);
    try {
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
      const response = await backtestApi.runRuleBacktest(
        robustnessConfig
          ? { ...requestPayload, robustnessConfig }
          : requestPayload,
      );
      setSelectedRuleRunId(response.id);
      void fetchRuleHistory(1, resolvedCode);
      navigate(`/backtest/results/${response.id}`, { state: { initialRun: response, resultMode: 'professional' } });
    } catch (error) {
      setRuleRunError(getParsedApiError(error));
    } finally {
      setIsSubmittingRuleBacktest(false);
    }
  };

  const handleLaunchNormalRuleBacktest = async () => {
    if (!normalizedCode) {
      setRuleRunError({
        title: bt(language, 'page.errors.missingCodeTitle'),
        message: bt(language, 'page.errors.missingRunCode'),
        rawMessage: bt(language, 'page.errors.missingRunCode'),
        category: 'missing_params',
      });
      return;
    }
    if (!ruleStartDate || !ruleEndDate) {
      setRuleRunError({
        title: bt(language, 'page.errors.missingRangeTitle'),
        message: bt(language, 'page.errors.missingRange'),
        rawMessage: bt(language, 'page.errors.missingRange'),
        category: 'validation_error',
      });
      return;
    }
    if (ruleStartDate > ruleEndDate) {
      setRuleRunError({
        title: bt(language, 'page.errors.invalidRangeTitle'),
        message: bt(language, 'page.errors.invalidRange'),
        rawMessage: bt(language, 'page.errors.invalidRange'),
        category: 'validation_error',
      });
      return;
    }
    if (ruleBenchmarkMode === 'custom_code' && !ruleBenchmarkCode.trim()) {
      setRuleRunError({
        title: bt(language, 'page.errors.missingBenchmarkTitle'),
        message: bt(language, 'page.errors.missingBenchmark'),
        rawMessage: bt(language, 'page.errors.missingBenchmark'),
        category: 'validation_error',
      });
      return;
    }

    const strategyText = buildPointAndShootStrategyText(language, normalStrategyTemplate, {
      code: normalizedCode,
      startDate: ruleStartDate,
      endDate: ruleEndDate,
      initialCapital: ruleInitialCapital,
    });

    if (!strategyText.trim()) {
      setRuleParseError({
        title: bt(language, 'page.errors.missingStrategyTitle'),
        message: bt(language, 'page.errors.missingStrategyText'),
        rawMessage: bt(language, 'page.errors.missingStrategyText'),
        category: 'missing_params',
      });
      return;
    }

    setIsLaunchingNormalRuleBacktest(true);
    setRuleParseError(null);
    setRuleRunError(null);
    setAppliedRewriteText(null);
    setRuleStrategyText(strategyText);

    try {
      const parsed = await backtestApi.parseRuleStrategy({
        code: normalizedCode,
        strategyText,
        startDate: ruleStartDate || undefined,
        endDate: ruleEndDate || undefined,
        initialCapital: Number.parseFloat(ruleInitialCapital) || undefined,
        feeBps: Number.parseFloat(ruleFeeBps) || 0,
        slippageBps: Number.parseFloat(ruleSlippageBps) || 0,
      });

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
        setRuleParseError({
          title: language === 'en' ? 'Template needs professional review' : '模板需要专业模式复查',
          message: language === 'en'
            ? 'The selected template did not compile into a runnable deterministic rule. The page has switched to Professional mode so you can inspect and revise it.'
            : '当前模板没有成功编译成可执行的确定性规则，已自动切到专业模式以便继续检查和改写。',
          rawMessage: language === 'en'
            ? 'The selected template did not compile into a runnable deterministic rule.'
            : '当前模板没有成功编译成可执行的确定性规则。',
          category: 'validation_error',
        });
        return;
      }

      setRuleConfirmed(true);
      setRuleCurrentStep('run');
      setIsSubmittingRuleBacktest(true);
      try {
        const response = await backtestApi.runRuleBacktest({
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
        });
        setSelectedRuleRunId(response.id);
        void fetchRuleHistory(1, normalizedCode);
        navigate(`/backtest/results/${response.id}`, { state: { initialRun: response, resultMode: 'simple' } });
      } catch (error) {
        setRuleRunError(getParsedApiError(error));
      } finally {
        setIsSubmittingRuleBacktest(false);
      }
    } catch (error) {
      setRuleParseError(getParsedApiError(error));
    } finally {
      setIsLaunchingNormalRuleBacktest(false);
    }
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

  const handleToggleProMonteCarlo = useCallback((nextEnabled: boolean) => {
    setProMonteCarloEnabled(nextEnabled);
    if (nextEnabled) {
      setProMonteCarloSimulationCount((current) => current.trim() || PRO_MONTE_CARLO_SIMULATION_DEFAULT);
    }
  }, []);

  const handleToggleProWalkForwardPreset = useCallback((nextEnabled: boolean) => {
    setProWalkForwardPresetEnabled(nextEnabled);
  }, []);

  const handleProMonteCarloSimulationCountChange = useCallback((value: string) => {
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
  }, []);

  const handleProMonteCarloSimulationCountBlur = useCallback(() => {
    if (!proMonteCarloEnabled) return;
    setProMonteCarloSimulationCount((current) => {
      const parsed = Number.parseInt(current, 10);
      if (!Number.isFinite(parsed)) return PRO_MONTE_CARLO_SIMULATION_DEFAULT;
      return String(clampInteger(parsed, PRO_MONTE_CARLO_SIMULATION_MIN, PRO_MONTE_CARLO_SIMULATION_MAX));
    });
  }, [proMonteCarloEnabled]);

  const resetRuleFlow = useCallback(() => {
    setRuleParsedStrategy(null);
    setRuleConfirmed(false);
    setRuleRunError(null);
    setRuleParseError(null);
    setRuleParseSignature(null);
    setRuleCurrentStep('symbol');
    setAppliedRewriteText(null);
    setRuleBenchmarkMode('auto');
    setRuleBenchmarkCode('');
    setProMonteCarloEnabled(false);
    setProMonteCarloSimulationCount('');
    setProWalkForwardPresetEnabled(false);
  }, []);
  const moduleTabs = (
    <div className="backtest-mode-toggle" role="tablist" aria-label={bt(language, 'page.moduleTabsLabel')}>
      <button
        ref={showRuleModuleButton.ref}
        type="button"
        role="tab"
        aria-selected={activeModule === 'rule'}
        className={`backtest-mode-toggle__button !min-h-[36px] md:!min-h-[32px]${activeModule === 'rule' ? ' is-active' : ''}`}
        onClick={showRuleModuleButton.onClick}
        onPointerUp={showRuleModuleButton.onPointerUp}
      >
        {bt(language, 'page.ruleTab')}
      </button>
      <button
        ref={showHistoricalModuleButton.ref}
        type="button"
        role="tab"
        aria-selected={activeModule === 'historical'}
        className={`backtest-mode-toggle__button !min-h-[36px] md:!min-h-[32px]${activeModule === 'historical' ? ' is-active' : ''}`}
        onClick={showHistoricalModuleButton.onClick}
        onPointerUp={showHistoricalModuleButton.onPointerUp}
      >
        {bt(language, 'page.historicalTab')}
      </button>
    </div>
  );

  const controlModeTabs = (
    <div className="backtest-mode-toggle" role="tablist" aria-label={bt(language, 'page.controlModeLabel')}>
      <button
        ref={showNormalModeButton.ref}
        type="button"
        role="tab"
        aria-selected={controlPanelMode === 'normal'}
        className={`backtest-mode-toggle__button !min-h-[36px] md:!min-h-[32px]${controlPanelMode === 'normal' ? ' is-active' : ''}`}
        onClick={showNormalModeButton.onClick}
        onPointerUp={showNormalModeButton.onPointerUp}
      >
        {bt(language, 'page.normalMode')}
      </button>
      <button
        ref={showProfessionalModeButton.ref}
        type="button"
        role="tab"
        aria-selected={controlPanelMode === 'professional'}
        className={`backtest-mode-toggle__button !min-h-[36px] md:!min-h-[32px]${controlPanelMode === 'professional' ? ' is-active' : ''}`}
        onClick={showProfessionalModeButton.onClick}
        onPointerUp={showProfessionalModeButton.onPointerUp}
      >
        {bt(language, 'page.professionalMode')}
      </button>
    </div>
  );

  return (
    <div
      ref={surfaceRef}
      data-testid="backtest-bento-page"
      aria-hidden={shouldGuardA11y && !isSafariReady ? true : undefined}
      aria-live={shouldGuardA11y ? (isSafariReady ? 'polite' : 'off') : undefined}
      className={getSafariReadySurfaceClassName(isSafariReady, 'w-full flex-1 min-w-0 min-h-0 bg-transparent')}
    >
      <TerminalPageShell data-testid="backtest-page-shell" className="flex-1 min-w-0 min-h-0 py-5 md:py-6">
        <TerminalPageHeading
          data-testid="backtest-page-heading"
          title={language === 'en' ? 'Backtest' : '回测'}
        />
        <div
          data-testid="backtest-subnav"
          className="w-full rounded-[24px] border border-white/5 bg-white/[0.02] px-4 py-3 backdrop-blur-sm"
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

        <main
          data-testid="backtest-v1-page"
          className="w-full flex-1 min-w-0 flex flex-col gap-6 bg-transparent"
        >
        {scannerHandoff ? (
          <section className="rounded-[24px] border border-sky-400/15 bg-sky-400/10 px-4 py-3 text-sm text-sky-50">
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
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={activeModule === 'rule' ? `${activeModule}-${controlPanelMode}` : activeModule}
            className={`backtest-v1-stage backtest-v1-stage--${activeModule} w-full min-w-0`}
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
                    templatePreview={normalStrategyPreview}
                    onLaunch={handleLaunchNormalRuleBacktest}
                    isLaunching={isLaunchingNormalRuleBacktest || isSubmittingRuleBacktest || isParsingRuleStrategy}
                    parseError={ruleParseError}
                    runError={ruleRunError}
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
          </motion.div>
        </AnimatePresence>
        </main>
      </TerminalPageShell>
    </div>
  );
};

export default BacktestPage;
