import type React from 'react';
import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { backtestApi } from '../api/backtest';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Button } from '../components/common';
import type { BacktestResultReportMode } from '../components/backtest/BacktestResultReport';
import BacktestChartWorkspace, {
  type CoverageTrackItem,
  type RiskControlVisualRow,
} from '../components/backtest/BacktestChartWorkspace';
import BacktestOverviewSummary, { type BacktestWalkForwardOverview } from '../components/backtest/BacktestOverviewSummary';
import {
  getDeterministicResultDensityCssVars,
  useDeterministicResultDensity,
} from '../components/backtest/deterministicResultDensity';
import { normalizeDeterministicBacktestResult } from '../components/backtest/normalizeDeterministicBacktestResult';
import {
  Banner,
  Disclosure,
  RuleRunStatusBanner,
  canCancelRuleRun,
  formatDateTime,
  formatNumber,
  getBenchmarkModeLabel,
  getRuleRunStatusDescription,
  getRuleRunStatusLabel,
  getStrategySpecValue,
  isCanonicalNoEntrySignalMessage,
  isRuleRunTerminal,
  pct,
  type RuleBenchmarkMode,
} from '../components/backtest/shared';
import { formatPercent } from '../utils/format';
import { type RuleComparisonItem } from '../components/backtest/RuleRunComparisonPanel';
import {
  buildRuleStrategySummaryRows,
  getRuleStrategyTypeLabel,
} from '../components/backtest/strategyInspectability';
import {
  downloadExecutionTraceCsv,
  downloadExecutionTraceJson,
  hasExecutionTraceRows,
} from '../components/backtest/executionTraceUtils';
import {
  buildRuleRunReportMarkdown,
  createRuleBacktestPresetFromRun,
  getRuleScenarioPlans,
  loadRuleBacktestPresets,
  saveRuleBacktestPreset,
  type RuleBacktestPreset,
  type RuleScenarioPlan,
} from '../components/backtest/ruleBacktestP6';
import type {
  RuleBacktestCancelResponse,
  RuleBacktestHistoryItem,
  RuleBacktestRunResponse,
  RuleBacktestStatusResponse,
} from '../types/backtest';
import { useI18n } from '../contexts/UiLanguageContext';
import { translate, type UiLanguage } from '../i18n/core';
import {
  ConsoleBoard,
  ConsoleContextRail,
  ConsoleDisclosure,
  ConsoleStatusStrip,
  KeyLevelStrip,
  ResearchConsoleShell,
  WolfyCommandBar,
} from '../components/linear';
import { TerminalPageShell } from '../components/terminal';
import { StatusBadge } from '../components/ui/StatusBadge';

const RULE_POLL_INTERVAL_MS = 1800;
const RESULT_HISTORY_PAGE_SIZE = 10;
const BacktestResultReport = lazy(() => import('../components/backtest/BacktestResultReport'));

type ResultPageLocationState = {
  initialRun?: RuleBacktestRunResponse;
  resultMode?: BacktestResultReportMode;
};

type ScenarioRunState = {
  variantId: string;
  label: string;
  description: string;
  runId: number | null;
  status: string;
  result: RuleBacktestRunResponse | null;
  error: string | null;
};

type RobustnessMetricRow = {
  label: string;
  value: string;
};

type StressScenarioDetail = {
  key: string;
  label: string;
  stateLabel: string | null;
  totalReturn: string | null;
  sharpe: string | null;
  maxDrawdown: string | null;
  isWorst: boolean;
};

type ResultPageTabKey = 'overview' | 'audit' | 'trades' | 'parameters' | 'history';

const RESULT_PAGE_TAB_KEYS: ResultPageTabKey[] = ['overview', 'audit', 'trades', 'parameters', 'history'];
const BacktestAuditTables = lazy(() => import('../components/backtest/BacktestAuditTables'));

function formatWarningText(warning: Record<string, unknown>, index: number): string {
  const preferred = warning.message
    || warning.text
    || warning.detail
    || warning.reason
    || warning.code;
  if (typeof preferred === 'string' && preferred.trim()) return preferred;

  const serialized = JSON.stringify(warning);
  return serialized && serialized !== '{}' ? serialized : `warning #${index + 1}`;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function asObjectRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? value as Record<string, unknown> : null;
}

function getObjectField(record: Record<string, unknown> | null, key: string): unknown {
  return record ? record[key] : undefined;
}

function hasObjectFields(record: Record<string, unknown> | null): boolean {
  return Boolean(record && Object.keys(record).length > 0);
}

function getFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function normalizeRobustnessState(value: unknown): 'available' | 'partial' | 'unavailable' | 'insufficient_history' | null {
  const normalized = String(value || '').trim().toLowerCase().replaceAll('-', '_');
  if (normalized === 'available' || normalized === 'partial' || normalized === 'unavailable' || normalized === 'insufficient_history') {
    return normalized;
  }
  return null;
}

function clampRatio(value: number | null): number {
  if (value == null || !Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

function getRunStatusTone(status?: string | null): 'positive' | 'negative' | 'accent' | 'default' {
  if (status === 'completed') return 'positive';
  if (status === 'failed' || status === 'cancelled') return 'negative';
  if (status === 'running' || status === 'parsing' || status === 'summarizing') return 'accent';
  return 'default';
}

function getLinearMetricTone(
  tone: 'positive' | 'negative' | 'accent' | 'default',
): 'up' | 'down' | 'neutral' {
  if (tone === 'positive') return 'up';
  if (tone === 'negative') return 'down';
  return 'neutral';
}

function btr(language: UiLanguage, key: string, vars?: Record<string, string | number | undefined>): string {
  return translate(language, `backtest.resultPage.${key}`, vars);
}

function getRobustnessStateLabel(value: unknown, language: UiLanguage): string {
  const normalized = normalizeRobustnessState(value);
  if (normalized === 'available') return btr(language, 'robustnessState.available');
  if (normalized === 'partial') return btr(language, 'robustnessState.partial');
  if (normalized === 'unavailable') return btr(language, 'robustnessState.unavailable');
  if (normalized === 'insufficient_history') return btr(language, 'robustnessState.insufficientHistory');
  return typeof value === 'string' && value.trim() ? value.trim() : '--';
}

function formatDrawdownPct(value: unknown): string | null {
  const numeric = getFiniteNumber(value);
  if (numeric == null) return null;
  return pct(numeric > 0 ? -numeric : numeric);
}

function getStringValue(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function getStressScenarioLabel(scenarioKey: unknown, language: UiLanguage, fallbackIndex?: number): string {
  const normalized = String(scenarioKey || '').trim().toLowerCase();
  if (normalized === 'single_day_shock_down_15') return btr(language, 'riskControls.stressScenarioLabels.singleDayShockDown15');
  if (normalized === 'volatility_whipsaw') return btr(language, 'riskControls.stressScenarioLabels.volatilityWhipsaw');
  if (normalized === 'gap_down_open') return btr(language, 'riskControls.stressScenarioLabels.gapDownOpen');
  if (typeof fallbackIndex === 'number') return btr(language, 'riskControls.stressScenarioFallbackLabel', { index: fallbackIndex + 1 });
  return btr(language, 'riskControls.stressScenarioUnknown');
}

function getRiskControlVisualRows(
  parsedStrategy: RuleBacktestRunResponse['parsedStrategy'] | null | undefined,
  language: UiLanguage,
): RiskControlVisualRow[] {
  const directSpec = parsedStrategy?.strategySpec;
  const strategySpec = directSpec && typeof directSpec === 'object'
    ? directSpec as Record<string, unknown>
    : undefined;
  if (!strategySpec) return [];

  const controls = [
    {
      key: 'stop-loss' as const,
      label: btr(language, 'riskControls.stopLoss'),
      value: getStrategySpecValue(strategySpec, ['risk_controls', 'stop_loss_pct']),
    },
    {
      key: 'take-profit' as const,
      label: btr(language, 'riskControls.takeProfit'),
      value: getStrategySpecValue(strategySpec, ['risk_controls', 'take_profit_pct']),
    },
    {
      key: 'trailing-stop' as const,
      label: btr(language, 'riskControls.trailingStop'),
      value: getStrategySpecValue(strategySpec, ['risk_controls', 'trailing_stop_pct']),
    },
  ];

  return controls
    .filter((item) => typeof item.value === 'number' && Number.isFinite(item.value))
    .map((item) => ({
      key: item.key,
      label: item.label,
      value: Number(item.value),
      valueLabel: formatPercent(Number(item.value), { digits: 2 }),
    }));
}

function downloadTextFile(filename: string, content: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

const DeterministicBacktestResultPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { language, t } = useI18n();
  const backtestCopy = useCallback(
    (key: string, vars?: Record<string, string | number | undefined>) => t(`backtest.${key}`, vars),
    [t],
  );
  const resultPage = useCallback(
    (key: string, vars?: Record<string, string | number | undefined>) => t(`backtest.resultPage.${key}`, vars),
    [t],
  );
  const { runId } = useParams<{ runId: string }>();
  const locationState = location.state as ResultPageLocationState | null;
  const initialRun = locationState?.initialRun || null;
  const resultMode: BacktestResultReportMode = locationState?.resultMode === 'simple' ? 'simple' : 'professional';
  const parsedRunId = Number.parseInt(runId || '', 10);
  const hasValidRunId = Number.isFinite(parsedRunId) && parsedRunId > 0;

  const [run, setRun] = useState<RuleBacktestRunResponse | null>(
    initialRun && initialRun.id === parsedRunId ? initialRun : null,
  );
  const [isLoadingRun, setIsLoadingRun] = useState(!initialRun || initialRun.id !== parsedRunId);
  const [runError, setRunError] = useState<ParsedApiError | null>(null);
  const [historyItems, setHistoryItems] = useState<RuleBacktestHistoryItem[]>([]);
  const [historyError, setHistoryError] = useState<ParsedApiError | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [activeTab, setActiveTab] = useState<ResultPageTabKey>('overview');
  const [isPollingStatus, setIsPollingStatus] = useState(false);
  const [lastStatusRefreshAt, setLastStatusRefreshAt] = useState<string | null>(null);
  const [isCancellingRun, setIsCancellingRun] = useState(false);
  const [cancelError, setCancelError] = useState<ParsedApiError | null>(null);
  const [compareRunIds, setCompareRunIds] = useState<number[]>([]);
  const [compareRunMap, setCompareRunMap] = useState<Record<number, RuleBacktestRunResponse>>({});
  const [isLoadingCompareRuns, setIsLoadingCompareRuns] = useState(false);
  const [compareError, setCompareError] = useState<ParsedApiError | null>(null);
  const [selectedScenarioPlanId, setSelectedScenarioPlanId] = useState<string | null>(null);
  const [scenarioRuns, setScenarioRuns] = useState<ScenarioRunState[]>([]);
  const [isSubmittingScenarioRuns, setIsSubmittingScenarioRuns] = useState(false);
  const [scenarioError, setScenarioError] = useState<ParsedApiError | null>(null);
  const [presetNotice, setPresetNotice] = useState<string | null>(null);
  const [availablePresets, setAvailablePresets] = useState<RuleBacktestPreset[]>([]);
  const [activeRobustnessKey, setActiveRobustnessKey] = useState<string | null>(null);
  const [activeRiskControlKey, setActiveRiskControlKey] = useState<RiskControlVisualRow['key'] | null>(null);
  const density = useDeterministicResultDensity();
  const robustnessAnalysis = useMemo(() => asObjectRecord(run?.robustnessAnalysis), [run?.robustnessAnalysis]);
  const robustnessConfiguration = useMemo(() => asObjectRecord(getObjectField(robustnessAnalysis, 'configuration')), [robustnessAnalysis]);
  const walkForward = useMemo(() => asObjectRecord(getObjectField(robustnessAnalysis, 'walkForward')), [robustnessAnalysis]);
  const walkForwardConfig = useMemo(() => asObjectRecord(getObjectField(robustnessConfiguration, 'walkForward')), [robustnessConfiguration]);
  const walkForwardAggregate = useMemo(() => asObjectRecord(getObjectField(walkForward, 'aggregateMetrics')), [walkForward]);
  const monteCarlo = useMemo(() => asObjectRecord(getObjectField(robustnessAnalysis, 'monteCarlo')), [robustnessAnalysis]);
  const monteCarloConfig = useMemo(() => asObjectRecord(getObjectField(robustnessConfiguration, 'monteCarlo')), [robustnessConfiguration]);
  const monteCarloAggregate = useMemo(() => asObjectRecord(getObjectField(monteCarlo, 'aggregateMetrics')), [monteCarlo]);
  const stressTests = useMemo(() => asObjectRecord(getObjectField(robustnessAnalysis, 'stressTests')), [robustnessAnalysis]);
  const stressTestsConfig = useMemo(() => asObjectRecord(getObjectField(robustnessConfiguration, 'stressTests')), [robustnessConfiguration]);
  const worstScenario = useMemo(() => asObjectRecord(getObjectField(stressTests, 'worstScenario')), [stressTests]);
  const stressScenarios = useMemo(
    () => {
      const value = getObjectField(stressTests, 'scenarios');
      return Array.isArray(value) ? value : [];
    },
    [stressTests],
  );
  const worstScenarioLabel = useMemo(
    () => getStressScenarioLabel(getObjectField(worstScenario, 'scenarioKey'), language),
    [language, worstScenario],
  );
  const hasRobustnessAnalysis = Boolean(
    getObjectField(robustnessAnalysis, 'state')
    || hasObjectFields(walkForward)
    || hasObjectFields(monteCarlo)
    || hasObjectFields(stressTests)
  );
  const robustnessLensRows = useMemo<CoverageTrackItem[]>(() => {
    const walkForwardCount = getFiniteNumber(getObjectField(walkForward, 'windowCount'));
    const walkForwardMax = getFiniteNumber(getObjectField(walkForwardConfig, 'maxWindows'));
    const monteCarloCount = getFiniteNumber(getObjectField(monteCarlo, 'simulationCount'));
    const monteCarloMax = getFiniteNumber(getObjectField(monteCarloConfig, 'simulationCount'));
    const stressScenarioCount = getFiniteNumber(getObjectField(stressTests, 'scenarioCount'));
    const stressScenarioKeys = getObjectField(stressTestsConfig, 'scenarioKeys');
    const stressScenarioMax = Array.isArray(stressScenarioKeys) ? stressScenarioKeys.length : null;

    return [
      {
        key: 'walk-forward',
        label: btr(language, 'riskControls.walkForwardLabel'),
        summary: walkForwardCount == null ? '--' : btr(language, 'riskControls.walkForwardWindows', { count: formatNumber(walkForwardCount, 0) }),
        detail: btr(language, 'riskControls.mean', { value: pct(getFiniteNumber(getObjectField(walkForwardAggregate, 'meanTotalReturnPct'))) }),
        state: getRobustnessStateLabel(getObjectField(walkForward, 'state') ?? getObjectField(robustnessAnalysis, 'state'), language),
        ratio: clampRatio(walkForwardCount != null && walkForwardMax ? walkForwardCount / walkForwardMax : (hasObjectFields(walkForward) ? 1 : 0)),
      },
      {
        key: 'monte-carlo',
        label: btr(language, 'riskControls.monteCarloLabel'),
        summary: monteCarloCount == null ? '--' : btr(language, 'riskControls.monteCarloPaths', { count: formatNumber(monteCarloCount, 0) }),
        detail: btr(language, 'riskControls.median', { value: pct(getFiniteNumber(getObjectField(monteCarloAggregate, 'medianTotalReturnPct'))) }),
        state: getRobustnessStateLabel(getObjectField(monteCarlo, 'state') ?? getObjectField(robustnessAnalysis, 'state'), language),
        ratio: clampRatio(monteCarloCount != null && monteCarloMax ? monteCarloCount / monteCarloMax : (hasObjectFields(monteCarlo) ? 1 : 0)),
      },
      {
        key: 'stress-tests',
        label: btr(language, 'riskControls.stressTestsLabel'),
        summary: stressScenarioCount == null ? '--' : btr(language, 'riskControls.stressScenarios', { count: formatNumber(stressScenarioCount, 0) }),
        detail: btr(language, 'riskControls.worst', { value: worstScenarioLabel }),
        state: getRobustnessStateLabel(getObjectField(stressTests, 'state') ?? getObjectField(robustnessAnalysis, 'state'), language),
        ratio: clampRatio(stressScenarioCount != null && stressScenarioMax ? stressScenarioCount / stressScenarioMax : (hasObjectFields(stressTests) ? 1 : 0)),
      },
    ];
  }, [
    monteCarlo,
    monteCarloAggregate,
    monteCarloConfig,
    language,
    robustnessAnalysis,
    stressTests,
    stressTestsConfig,
    walkForward,
    walkForwardAggregate,
    walkForwardConfig,
    worstScenarioLabel,
  ]);
  const monteCarloDetailRows = useMemo<RobustnessMetricRow[]>(() => {
    const rows: RobustnessMetricRow[] = [];
    const p05Return = getFiniteNumber(getObjectField(monteCarloAggregate, 'p05TotalReturnPct'));
    const medianReturn = getFiniteNumber(getObjectField(monteCarloAggregate, 'medianTotalReturnPct'));
    const p95Return = getFiniteNumber(getObjectField(monteCarloAggregate, 'p95TotalReturnPct'));
    const meanReturn = getFiniteNumber(getObjectField(monteCarloAggregate, 'meanTotalReturnPct'));
    const worstMaxDrawdown = formatDrawdownPct(getObjectField(monteCarloAggregate, 'worstMaxDrawdownPct'));
    const simulationCount = getFiniteNumber(getObjectField(monteCarlo, 'simulationCount'));
    const seed = getFiniteNumber(getObjectField(monteCarlo, 'seed'));
    const monteCarloState = normalizeRobustnessState(getObjectField(monteCarlo, 'state'));

    if (p05Return != null) rows.push({ label: btr(language, 'riskControls.p05TotalReturn'), value: pct(p05Return) });
    if (medianReturn != null) rows.push({ label: btr(language, 'riskControls.medianTotalReturn'), value: pct(medianReturn) });
    if (p95Return != null) rows.push({ label: btr(language, 'riskControls.p95TotalReturn'), value: pct(p95Return) });
    if (meanReturn != null) rows.push({ label: btr(language, 'riskControls.meanTotalReturn'), value: pct(meanReturn) });
    if (worstMaxDrawdown != null) rows.push({ label: btr(language, 'riskControls.worstMaxDrawdown'), value: worstMaxDrawdown });
    if (simulationCount != null) rows.push({ label: btr(language, 'riskControls.monteCarloSimulation'), value: formatNumber(simulationCount, 0) });
    if (seed != null) rows.push({ label: btr(language, 'riskControls.randomSeed'), value: formatNumber(seed, 0) });
    if (rows.length > 0 && monteCarloState) {
      rows.push({ label: btr(language, 'riskControls.status'), value: getRobustnessStateLabel(monteCarloState, language) });
    }

    return rows;
  }, [language, monteCarlo, monteCarloAggregate]);
  const stressScenarioRows = useMemo<StressScenarioDetail[]>(
    () => stressScenarios
      .map((scenario, index) => {
        const record = asObjectRecord(scenario);
        const metrics = asObjectRecord(getObjectField(record, 'metrics'));
        const scenarioKey = getStringValue(getObjectField(record, 'scenarioKey')) || `stress-scenario-${index}`;
        const rawLabel = getStringValue(getObjectField(record, 'label'));
        const totalReturn = getFiniteNumber(getObjectField(metrics, 'totalReturnPct'));
        const sharpe = getFiniteNumber(getObjectField(metrics, 'sharpeRatio'));
        const maxDrawdown = formatDrawdownPct(getObjectField(metrics, 'maxDrawdownPct'));

        return {
          key: scenarioKey,
          label: rawLabel && language === 'en'
            ? rawLabel
            : getStressScenarioLabel(getObjectField(record, 'scenarioKey') || rawLabel, language, index),
          stateLabel: normalizeRobustnessState(getObjectField(record, 'state'))
            ? getRobustnessStateLabel(getObjectField(record, 'state'), language)
            : null,
          totalReturn: totalReturn == null ? null : pct(totalReturn),
          sharpe: sharpe == null ? null : formatNumber(sharpe),
          maxDrawdown,
          isWorst: getStringValue(getObjectField(worstScenario, 'scenarioKey')) === scenarioKey,
        };
      })
      .filter((row) => row.totalReturn != null || row.sharpe != null || row.maxDrawdown != null),
    [language, stressScenarios, worstScenario],
  );
  const monteCarloDetailEmptyText = (() => {
    const state = normalizeRobustnessState(getObjectField(monteCarlo, 'state'));
    return state === 'insufficient_history'
      ? btr(language, 'riskControls.monteCarloDetailsEmptyInsufficient')
      : btr(language, 'riskControls.monteCarloDetailsEmpty');
  })();
  const stressScenarioDetailEmptyText = (() => {
    const state = normalizeRobustnessState(getObjectField(stressTests, 'state'));
    return state === 'insufficient_history'
      ? btr(language, 'riskControls.stressScenarioDetailsEmptyInsufficient')
      : btr(language, 'riskControls.stressScenarioDetailsEmpty');
  })();
  const walkForwardOverview = useMemo<BacktestWalkForwardOverview>(() => {
    const walkForwardState = normalizeRobustnessState(getObjectField(walkForward, 'state'));
    const robustnessState = normalizeRobustnessState(getObjectField(robustnessAnalysis, 'state'));
    const windowCount = getFiniteNumber(getObjectField(walkForward, 'windowCount'));
    const meanReturn = getFiniteNumber(getObjectField(walkForwardAggregate, 'meanTotalReturnPct'));
    const maxDrawdown = formatDrawdownPct(
      getObjectField(walkForwardAggregate, 'maxDrawdownPct')
      ?? getObjectField(walkForwardAggregate, 'meanMaxDrawdownPct'),
    );
    const hasWalkForwardMetrics = windowCount != null || meanReturn != null || maxDrawdown != null;
    const stateKey: BacktestWalkForwardOverview['stateKey'] = walkForwardState
      ?? (hasWalkForwardMetrics
        ? 'available'
        : (robustnessState === 'insufficient_history' || robustnessState === 'partial' || robustnessState === 'unavailable'
          ? robustnessState
          : 'unavailable'));

    return {
      stateKey,
      stateLabel: getRobustnessStateLabel(getObjectField(walkForward, 'state') ?? stateKey, language),
      windowSummary: windowCount == null
        ? null
        : btr(language, 'riskControls.walkForwardWindows', { count: formatNumber(windowCount, 0) }),
      meanReturn: meanReturn == null ? null : pct(meanReturn),
      maxDrawdown,
    };
  }, [language, robustnessAnalysis, walkForward, walkForwardAggregate]);
  const tabs = RESULT_PAGE_TAB_KEYS.map((key) => ({
    key,
    label: backtestCopy(`resultPage.tabs.${key}`),
  }));

  const fetchRun = useCallback(async (options: { suppressLoading?: boolean } = {}) => {
    if (!hasValidRunId) return;
    const { suppressLoading = false } = options;
    if (!suppressLoading) setIsLoadingRun(true);
    try {
      const response = await backtestApi.getRuleBacktestRun(parsedRunId);
      setRun(response);
      setRunError(null);
      setCancelError(null);
      setLastStatusRefreshAt(new Date().toISOString());
    } catch (error) {
      setRunError(getParsedApiError(error));
    } finally {
      if (!suppressLoading) setIsLoadingRun(false);
    }
  }, [hasValidRunId, parsedRunId]);

  const fetchHistory = useCallback(async (code?: string) => {
    if (!code) {
      setHistoryItems([]);
      setHistoryError(null);
      return;
    }
    setIsLoadingHistory(true);
    try {
      const response = await backtestApi.getRuleBacktestRuns({
        code,
        page: 1,
        limit: RESULT_HISTORY_PAGE_SIZE,
      });
      setHistoryItems(response.items);
      setHistoryError(null);
    } catch (error) {
      setHistoryError(getParsedApiError(error));
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    if (!hasValidRunId) {
      setRun(null);
      setIsLoadingRun(false);
      return;
    }

    const seededRun = initialRun && initialRun.id === parsedRunId ? initialRun : null;
    setRun(seededRun);
    setRunError(null);
    setCancelError(null);
    setIsLoadingRun(!seededRun);
    setLastStatusRefreshAt(seededRun ? new Date().toISOString() : null);
    void fetchRun({ suppressLoading: Boolean(seededRun) });
  }, [fetchRun, hasValidRunId, initialRun, parsedRunId]);

  useEffect(() => {
    if (!run?.id || isRuleRunTerminal(run.status)) return undefined;

    let cancelled = false;
    let timer: number | undefined;

    const poll = async () => {
      if (!cancelled) setIsPollingStatus(true);
      try {
        const status = await backtestApi.getRuleBacktestRunStatus(run.id);
        if (cancelled) return;
        setRun((current) => (current ? { ...current, ...(status as RuleBacktestStatusResponse) } : current));
        setRunError(null);
        setLastStatusRefreshAt(new Date().toISOString());
        if (isRuleRunTerminal(status.status)) {
          await Promise.all([
            fetchRun({ suppressLoading: true }),
            fetchHistory(status.code),
          ]);
          return;
        }
      } catch (error) {
        if (!cancelled) setRunError(getParsedApiError(error));
      } finally {
        if (!cancelled) setIsPollingStatus(false);
      }

      if (!cancelled) timer = window.setTimeout(() => void poll(), RULE_POLL_INTERVAL_MS);
    };

    timer = window.setTimeout(() => void poll(), RULE_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [fetchHistory, fetchRun, run?.id, run?.status]);

  useEffect(() => {
    if (!run?.code) {
      setHistoryItems([]);
      return;
    }
    void fetchHistory(run.code);
  }, [fetchHistory, run?.code]);

  useEffect(() => {
    setCompareRunIds([]);
    setScenarioRuns([]);
    setScenarioError(null);
  }, [run?.id]);

  useEffect(() => {
    document.title = hasValidRunId
      ? `${backtestCopy('resultPage.documentTitle')} #${parsedRunId} - WolfyStock`
      : `${backtestCopy('resultPage.documentTitle')} - WolfyStock`;
  }, [backtestCopy, hasValidRunId, parsedRunId]);

  useEffect(() => {
    setAvailablePresets(loadRuleBacktestPresets());
  }, []);

  useEffect(() => {
    if (!run || run.status !== 'completed') return;
    const next = saveRuleBacktestPreset(createRuleBacktestPresetFromRun(run, { kind: 'recent' }));
    setAvailablePresets(next);
  }, [run]);

  useEffect(() => {
    if (compareRunIds.length === 0) {
      setCompareError(null);
      return;
    }
    let cancelled = false;
    const missingIds = compareRunIds.filter((id) => !compareRunMap[id]);
    if (missingIds.length === 0) return;

    const loadRuns = async () => {
      setIsLoadingCompareRuns(true);
      try {
        const items = await Promise.all(missingIds.map((id) => backtestApi.getRuleBacktestRun(id)));
        if (cancelled) return;
        setCompareRunMap((current) => ({
          ...current,
          ...Object.fromEntries(items.map((item) => [item.id, item])),
        }));
        setCompareError(null);
      } catch (error) {
        if (!cancelled) setCompareError(getParsedApiError(error));
      } finally {
        if (!cancelled) setIsLoadingCompareRuns(false);
      }
    };

    void loadRuns();
    return () => {
      cancelled = true;
    };
  }, [compareRunIds, compareRunMap]);

  useEffect(() => {
    const pendingRuns = scenarioRuns.filter((item) => item.runId && !isRuleRunTerminal(item.status));
    if (pendingRuns.length === 0) return undefined;

    let cancelled = false;
    const timer = window.setInterval(() => {
      void (async () => {
        try {
          const updates = await Promise.all(
            pendingRuns.map(async (item) => {
              const status = await backtestApi.getRuleBacktestRunStatus(item.runId as number);
              if (status.status === 'completed') {
                const detail = await backtestApi.getRuleBacktestRun(item.runId as number);
                return { runId: item.runId, status: detail.status, detail, error: null };
              }
              return { runId: item.runId, status: status.status, detail: null, error: null };
            }),
          );
          if (cancelled) return;
          setScenarioRuns((current) => current.map((item) => {
            const matched = updates.find((update) => update.runId === item.runId);
            if (!matched) return item;
            return {
              ...item,
              status: matched.status,
              result: matched.detail ?? item.result,
              error: matched.error,
            };
          }));
        } catch (error) {
          if (!cancelled) setScenarioError(getParsedApiError(error));
        }
      })();
    }, RULE_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [scenarioRuns]);

  const handleOpenHistoryRun = (item: RuleBacktestHistoryItem) => {
    navigate(`/backtest/results/${item.id}`);
  };

  const benchmarkSummary = run?.benchmarkSummary;
  const buyAndHoldSummary = run?.buyAndHoldSummary;
  const buyAndHoldLabel = (
    String(buyAndHoldSummary?.label || '').trim() === translate('zh', 'backtest.resultPage.buyAndHoldDefault')
    || String(buyAndHoldSummary?.label || '').trim() === translate('en', 'backtest.resultPage.buyAndHoldDefault')
  )
    ? resultPage('buyAndHoldDefault')
    : (buyAndHoldSummary?.label || resultPage('buyAndHoldDefault'));
  const selectedBenchmarkLabel = benchmarkSummary
    ? String(
      benchmarkSummary.label
      || getBenchmarkModeLabel(
        (run?.benchmarkMode as RuleBenchmarkMode | undefined) || 'auto',
        run?.code,
        run?.benchmarkCode || undefined,
        language,
      ),
    )
    : '--';
  const benchmarkStatusNote = benchmarkSummary
    ? (
      benchmarkSummary.unavailableReason
      || (benchmarkSummary.resolvedMode === 'none'
        ? resultPage('benchmarkNotes.none')
        : benchmarkSummary.autoResolved
          ? resultPage('benchmarkNotes.autoResolved', { label: selectedBenchmarkLabel })
          : resultPage('benchmarkNotes.sameWindow'))
    )
    : resultPage('benchmarkNotes.pending');
  const normalized = useMemo(
    () => (run?.status === 'completed' ? normalizeDeterministicBacktestResult(run, language) : null),
    [run, language],
  );
  const scenarioPlans = useMemo<RuleScenarioPlan[]>(
    () => (run?.status === 'completed' ? getRuleScenarioPlans(run) : []),
    [run],
  );
  const selectedScenarioPlan = useMemo(
    () => scenarioPlans.find((plan) => plan.id === selectedScenarioPlanId) || scenarioPlans[0] || null,
    [scenarioPlans, selectedScenarioPlanId],
  );
  useEffect(() => {
    if (!selectedScenarioPlanId && scenarioPlans[0]) {
      setSelectedScenarioPlanId(scenarioPlans[0].id);
    }
  }, [scenarioPlans, selectedScenarioPlanId]);
  const comparisonItems = useMemo<RuleComparisonItem[]>(() => {
    if (!run || !normalized) return [];
    const items: RuleComparisonItem[] = [{
      run,
      normalized,
      label: resultPage('comparison.currentRunLabel', { id: run.id }),
      badge: resultPage('comparison.currentBadge'),
    }];
    compareRunIds.forEach((id) => {
      const detail = compareRunMap[id];
      if (!detail || detail.status !== 'completed') return;
      items.push({
        run: detail,
        normalized: normalizeDeterministicBacktestResult(detail, language),
        label: resultPage('comparison.comparedRunLabel', { id: detail.id }),
      });
    });
    return items;
  }, [compareRunIds, compareRunMap, language, normalized, resultPage, run]);
  const scenarioComparisonItems = useMemo<RuleComparisonItem[]>(() => {
    if (!run || !normalized) return [];
    const completedScenarioRuns = scenarioRuns.filter((item) => item.result?.status === 'completed' && item.result);
    return [
      {
        run,
        normalized,
        label: resultPage('comparison.currentRunLabel', { id: run.id }),
        badge: resultPage('comparison.baselineBadge'),
      },
      ...completedScenarioRuns.map((item) => ({
        run: item.result as RuleBacktestRunResponse,
        normalized: normalizeDeterministicBacktestResult(item.result as RuleBacktestRunResponse, language),
        label: item.label,
      })),
    ];
  }, [language, normalized, resultPage, run, scenarioRuns]);
  const decisionReportMarkdown = useMemo(
    () => (run && normalized
      ? buildRuleRunReportMarkdown({
        run,
        normalized,
        comparedRuns: comparisonItems.slice(1).map((item) => item.run),
        language,
      })
      : ''),
    [comparisonItems, normalized, run, language],
  );
  const headerDescription = run
    ? resultPage('headerDescriptionLoaded', {
      code: run.code,
      startDate: run.startDate || '--',
      endDate: run.endDate || '--',
      benchmarkLabel: selectedBenchmarkLabel,
    })
    : resultPage('headerDescriptionEmpty');
  const parsedSummaryEntries = Object.entries(run?.parsedStrategy?.summary || {})
    .filter(([, value]) => typeof value === 'string' && value.trim())
    .map(([key, value]) => ({
      label: key
        .replaceAll(/([a-z])([A-Z])/g, '$1 $2')
        .replaceAll('_', ' ')
        .trim(),
      value: String(value),
    }));
  const strategySummaryRows = useMemo(
    () => (run
      ? buildRuleStrategySummaryRows(run.parsedStrategy, run.code, run.startDate || '', run.endDate || '', undefined, language)
      : []),
    [run, language],
  );
  const riskControlRows = useMemo(
    () => getRiskControlVisualRows(run?.parsedStrategy, language),
    [language, run?.parsedStrategy],
  );
  const strategyWarningEntries = Array.from(
    new Set([
      ...(run?.parsedStrategy?.parseWarnings || []).map((warning, index) => formatWarningText(warning, index)),
      ...(run?.warnings || []).map((warning, index) => formatWarningText(warning, index)),
    ].filter(Boolean)),
  );
  const canCancelCurrentRun = Boolean(run && canCancelRuleRun(run.status));
  const canExportTrace = Boolean(run && hasExecutionTraceRows(run));
  const localizedNoResultMessage = isCanonicalNoEntrySignalMessage(run?.noResultMessage)
    ? resultPage('noEntrySignal')
    : null;
  const statusSummaryItems = run ? [
    {
      label: resultPage('statusSummary.currentStageLabel'),
      value: getRuleRunStatusLabel(run.status, language),
      note: localizedNoResultMessage || getRuleRunStatusDescription(run.status, language),
    },
    {
      label: resultPage('statusSummary.autoRefreshLabel'),
      value: isRuleRunTerminal(run.status) ? resultPage('statusSummary.autoRefreshStopped') : resultPage('statusSummary.autoRefreshEvery'),
      note: isPollingStatus ? resultPage('statusSummary.autoRefreshSyncing') : resultPage('statusSummary.autoRefreshActive'),
    },
    {
      label: resultPage('statusSummary.lastRefreshLabel'),
      value: lastStatusRefreshAt ? formatDateTime(lastStatusRefreshAt) : '--',
      note: isLoadingRun ? resultPage('statusSummary.lastRefreshLoading') : resultPage('statusSummary.lastRefreshManual'),
    },
    {
      label: resultPage('statusSummary.nextStepLabel'),
      value: canCancelCurrentRun
        ? resultPage('statusSummary.nextStepCancelable')
        : canExportTrace
          ? resultPage('statusSummary.nextStepExportReady')
          : isRuleRunTerminal(run.status)
            ? resultPage('statusSummary.nextStepReviewResult')
            : resultPage('statusSummary.nextStepWaiting'),
      note: canExportTrace
        ? resultPage('statusSummary.nextStepExportReadyNote')
        : resultPage('statusSummary.nextStepExportPendingNote'),
    },
  ] : [];
  const completedHeroMetrics = run && normalized ? [
    {
      label: resultPage('resultView.totalReturn'),
      value: pct(normalized.metrics.totalReturnPct),
      tone: getRunStatusTone(run.status),
      note: benchmarkSummary
        ? `${selectedBenchmarkLabel} ${pct(normalized.metrics.benchmarkReturnPct)}`
        : buyAndHoldLabel,
    },
    {
      label: resultPage('resultView.annualizedReturn'),
      value: pct(normalized.metrics.annualizedReturnPct),
      tone: 'accent' as const,
      note: resultPage('resultView.sharpe'),
    },
    {
      label: resultPage('resultView.maxDrawdown'),
      value: normalized.metrics.maxDrawdownPct == null || !Number.isFinite(normalized.metrics.maxDrawdownPct)
        ? pct(normalized.metrics.maxDrawdownPct)
        : pct(normalized.metrics.maxDrawdownPct > 0 ? -normalized.metrics.maxDrawdownPct : normalized.metrics.maxDrawdownPct),
      tone: 'negative' as const,
      note: resultPage('resultView.drawdownFeel'),
    },
    {
      label: resultPage('resultView.trades'),
      value: String(normalized.metrics.tradeCount),
      tone: 'default' as const,
      note: resultPage('resultView.tradeRecord', {
        wins: normalized.metrics.winCount,
        losses: normalized.metrics.lossCount,
      }),
    },
    {
      label: resultPage('resultView.winRate'),
      value: pct(normalized.metrics.winRatePct),
      tone: normalized.metrics.winRatePct != null && normalized.metrics.winRatePct >= 50 ? 'positive' as const : 'default' as const,
      note: resultPage('resultView.averageTrade', { value: pct(normalized.metrics.avgTradeReturnPct) }),
    },
    {
      label: resultPage('resultView.endingEquity'),
      value: formatNumber(normalized.metrics.finalEquity),
      tone: 'default' as const,
      note: resultPage('resultView.initialCapital', { value: formatNumber(run.initialCapital) }),
    },
  ] : [];

  const handleToggleCompareRun = (item: RuleBacktestHistoryItem) => {
    setCompareRunIds((current) => {
      if (current.includes(item.id)) return current.filter((id) => id !== item.id);
      return [...current, item.id].slice(0, 3);
    });
  };

  const handleOpenCompareWorkbench = () => {
    if (!run || compareRunIds.length === 0) return;
    const params = new URLSearchParams({
      runIds: [run.id, ...compareRunIds].join(','),
    });
    navigate(`/backtest/compare?${params.toString()}`);
  };

  const handleSavePreset = useCallback(() => {
    if (!run) return;
    const suggestedName = `${run.code} · ${getRuleStrategyTypeLabel(run.parsedStrategy, undefined, language)}`;
    const name = window.prompt(resultPage('promptSavePreset'), suggestedName);
    if (!name || !name.trim()) return;
    const next = saveRuleBacktestPreset(createRuleBacktestPresetFromRun(run, {
      kind: 'saved',
      name,
    }));
    setAvailablePresets(next);
    setPresetNotice(resultPage('presetSaved', { name: name.trim() }));
  }, [language, resultPage, run]);

  const handleExportDecisionReport = (format: 'md' | 'html') => {
    if (!run || !normalized || !decisionReportMarkdown) return;
    if (format === 'md') {
      downloadTextFile(`backtest-run-${run.id}-summary.md`, decisionReportMarkdown, 'text/markdown;charset=utf-8');
      return;
    }
    const html = [
      '<!doctype html>',
      '<html lang="zh-CN"><head><meta charset="utf-8" />',
      `<title>${escapeHtml(resultPage('exportHtmlTitle', { id: run.id }))}</title>`,
      '<style>body{font-family:ui-sans-serif,system-ui,sans-serif;padding:24px;line-height:1.6;color:#111827}pre{white-space:pre-wrap;word-break:break-word;background:#f3f4f6;border:1px solid #d1d5db;border-radius:12px;padding:18px}</style>',
      '</head><body>',
      `<h1>${escapeHtml(resultPage('exportHtmlHeading', { id: run.id }))}</h1>`,
      `<pre>${escapeHtml(decisionReportMarkdown)}</pre>`,
      '</body></html>',
    ].join('');
    downloadTextFile(`backtest-run-${run.id}-summary.html`, html, 'text/html;charset=utf-8');
  };

  const handleRunScenarioPlan = useCallback(async () => {
    if (!run || !selectedScenarioPlan) return;
    setIsSubmittingScenarioRuns(true);
    setScenarioError(null);
    setScenarioRuns(selectedScenarioPlan.variants.map((variant) => ({
      variantId: variant.id,
      label: variant.label,
      description: variant.description,
      runId: null,
      status: 'submitting',
      result: null,
      error: null,
    })));

    try {
      const nextStates: ScenarioRunState[] = [];
      for (const variant of selectedScenarioPlan.variants) {
        const response = await backtestApi.runRuleBacktest(variant.request);
        nextStates.push({
          variantId: variant.id,
          label: variant.label,
          description: variant.description,
          runId: response.id,
          status: response.status,
          result: response.status === 'completed' ? response : null,
          error: null,
        });
      }
      setScenarioRuns(nextStates);
    } catch (error) {
      setScenarioError(getParsedApiError(error));
    } finally {
      setIsSubmittingScenarioRuns(false);
    }
  }, [run, selectedScenarioPlan]);

  const handleCancelRun = useCallback(async () => {
    if (!run || !canCancelRuleRun(run.status) || isCancellingRun) return;
    const confirmed = window.confirm(resultPage('cancelConfirm'));
    if (!confirmed) return;

    setIsCancellingRun(true);
    setCancelError(null);

    try {
      const response = await backtestApi.cancelRuleBacktestRun(run.id);
      setRun((current) => (current ? { ...current, ...(response as RuleBacktestCancelResponse) } : current));
      setRunError(null);
      setLastStatusRefreshAt(new Date().toISOString());
      await Promise.all([
        fetchRun({ suppressLoading: true }),
        fetchHistory(response.code),
      ]);
    } catch (error) {
      setCancelError(getParsedApiError(error));
    } finally {
      setIsCancellingRun(false);
    }
  }, [fetchHistory, fetchRun, isCancellingRun, resultPage, run]);

  const renderRunStatusSection = () => {
    if (!run && isLoadingRun) {
      return (
        <section className="backtest-display-section" data-testid="deterministic-result-page-status">
          <ConsoleBoard>
            <div className="flex flex-col gap-3 p-4 md:p-5">
              <div>
                <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{resultPage('statusCard.loadingSubtitle')}</p>
                <h2 className="mt-1 text-base font-semibold text-[color:var(--wolfy-text-primary)]">{resultPage('statusCard.title')}</h2>
              </div>
              <div className="text-sm text-[color:var(--wolfy-text-secondary)]">{resultPage('statusCard.loadingBody')}</div>
            </div>
          </ConsoleBoard>
        </section>
      );
    }

    if (!run) {
      return (
        <section className="backtest-display-section" data-testid="deterministic-result-page-status">
          <ConsoleBoard>
            <div className="flex flex-col gap-3 p-4 md:p-5">
              <div>
                <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{resultPage('statusCard.unavailableSubtitle')}</p>
                <h2 className="mt-1 text-base font-semibold text-[color:var(--wolfy-text-primary)]">{resultPage('statusCard.title')}</h2>
              </div>
              {runError ? <ApiErrorAlert error={runError} /> : (
                <div className="text-sm text-[color:var(--wolfy-text-secondary)]">{resultPage('statusCard.unavailableBody')}</div>
              )}
            </div>
          </ConsoleBoard>
        </section>
      );
    }

    return (
      <section className="backtest-display-section" data-testid="deterministic-result-page-status">
        <ConsoleBoard>
          <div className="flex flex-col gap-4 p-4 md:p-5">
            <div>
              <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{resultPage('statusCard.controlsSubtitle')}</p>
              <h2 className="mt-1 text-base font-semibold text-[color:var(--wolfy-text-primary)]">{resultPage('statusCard.title')}</h2>
            </div>
          <RuleRunStatusBanner run={run} />
          <ConsoleStatusStrip
            items={statusSummaryItems.map((item) => ({
              key: item.label,
              label: item.label,
              value: item.value,
            }))}
          />
          {!isRuleRunTerminal(run.status) ? (
            <div>
              <Banner
                tone="info"
                title={resultPage('statusCard.autoTrackingTitle')}
                body={resultPage('statusCard.autoTrackingBody')}
              />
            </div>
          ) : null}
          {run.status === 'completed' ? (
            <div>
              <Banner
                tone="success"
                title={resultPage('statusCard.completedTitle')}
                body={resultPage('statusCard.completedBody')}
              />
            </div>
          ) : null}
          {run.status === 'cancelled' ? (
            <div>
              <Banner
                tone="warning"
                title={resultPage('statusCard.cancelledTitle')}
                body={resultPage('statusCard.cancelledBody')}
              />
            </div>
          ) : null}
          {run.status === 'failed' ? (
            <div>
              <Banner
                tone="danger"
                title={resultPage('statusCard.failedTitle')}
                body={resultPage('statusCard.failedBody')}
              />
            </div>
          ) : null}
          <div className="product-action-row">
            <Button variant="ghost" onClick={() => void fetchRun()} disabled={isCancellingRun}>
              {isPollingStatus || isLoadingRun ? resultPage('statusCard.refreshing') : resultPage('statusCard.refreshStatus')}
            </Button>
            {canCancelCurrentRun ? (
              <Button
                variant="danger-subtle"
                onClick={() => void handleCancelRun()}
                isLoading={isCancellingRun}
                loadingText={resultPage('statusCard.cancelling')}
              >
                {resultPage('statusCard.cancelRun')}
              </Button>
            ) : null}
            {isRuleRunTerminal(run.status) && canExportTrace ? (
              <>
                <Button variant="secondary" onClick={() => downloadExecutionTraceCsv(run)}>
                  {resultPage('statusCard.exportCsv')}
                </Button>
                <Button variant="ghost" onClick={() => downloadExecutionTraceJson(run)}>
                  {resultPage('statusCard.exportJson')}
                </Button>
                <Button variant="ghost" onClick={() => handleExportDecisionReport('md')}>
                  {resultPage('statusCard.exportSummaryMd')}
                </Button>
              </>
            ) : null}
          </div>
          {run.statusHistory?.length ? (
            <Disclosure summary={resultPage('statusCard.viewStatusTimeline', { count: run.statusHistory.length })}>
              <div className="product-chip-list">
                {run.statusHistory.map((item, index) => (
                  <span key={`${item.status}-${item.at || index}`} className="product-chip">
                    {index + 1}. {`${String(item.status || '--')} · ${item.at ? formatDateTime(item.at) : '--'}`}
                  </span>
                ))}
              </div>
            </Disclosure>
          ) : null}
          {runError ? <ApiErrorAlert error={runError} /> : null}
          {cancelError ? <ApiErrorAlert error={cancelError} /> : null}
          {presetNotice ? (
            <div>
              <Banner tone="success" title={presetNotice} body={resultPage('statusCard.reusableBanner', { count: availablePresets.length })} />
            </div>
          ) : null}
          </div>
        </ConsoleBoard>
      </section>
    );
  };

  const renderCompletedTabPanel = () => {
    if (!run || !normalized) return null;

    if (activeTab === 'overview') {
      return (
        <BacktestOverviewSummary
          resultPage={resultPage}
          run={run}
          normalized={normalized}
          selectedBenchmarkLabel={selectedBenchmarkLabel}
          buyAndHoldLabel={buyAndHoldLabel}
          benchmarkStatusNote={benchmarkStatusNote}
          walkForwardOverview={walkForwardOverview}
          decisionReportMarkdown={decisionReportMarkdown}
          onExportDecisionReport={handleExportDecisionReport}
        />
      );
    }

    const activeTabLabel = backtestCopy(`resultPage.tabs.${activeTab}`);

    return (
      <Suspense
        fallback={(
          <section
            className="backtest-display-section"
            data-testid="deterministic-result-tab-lazy-fallback"
            role="status"
            aria-live="polite"
          >
            <div className="rounded-[16px] border border-white/5 bg-white/[0.02] px-4 py-3 backdrop-blur-md">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-white/35">
                    WolfyStock
                  </p>
                  <p className="truncate text-sm text-white/78">{activeTabLabel}</p>
                </div>
                <span
                  className="inline-flex h-2.5 w-2.5 shrink-0 rounded-full bg-cyan-300/70 shadow-[0_0_12px_rgba(103,232,249,0.42)] animate-pulse"
                  aria-hidden="true"
                />
              </div>
              <p className="mt-2 text-xs text-white/45">正在加载该分区的回测明细。</p>
            </div>
          </section>
        )}
      >
        <BacktestAuditTables
          activeTab={activeTab}
          resultPage={resultPage}
          backtestCopy={backtestCopy}
          language={language}
          run={run}
          normalized={normalized}
          selectedBenchmarkLabel={selectedBenchmarkLabel}
          buyAndHoldLabel={buyAndHoldLabel}
          benchmarkStatusNote={benchmarkStatusNote}
          hasRobustnessAnalysis={hasRobustnessAnalysis}
          robustnessAnalysisStateLabel={getRobustnessStateLabel(getObjectField(robustnessAnalysis, 'state'), language)}
          robustnessLensRows={robustnessLensRows}
          riskControlRows={riskControlRows}
          activeRobustnessKey={activeRobustnessKey}
          activeRiskControlKey={activeRiskControlKey}
          walkForwardWindowCount={formatNumber(getObjectField(walkForward, 'windowCount') as number | null | undefined, 0)}
          monteCarloSimulationCount={formatNumber(getObjectField(monteCarlo, 'simulationCount') as number | null | undefined, 0)}
          stressScenarioCount={formatNumber(getObjectField(stressTests, 'scenarioCount') as number | null | undefined, 0)}
          walkForwardMeanReturn={pct(getObjectField(walkForwardAggregate, 'meanTotalReturnPct') as number | null | undefined)}
          monteCarloMedianReturn={pct(getObjectField(monteCarloAggregate, 'medianTotalReturnPct') as number | null | undefined)}
          worstScenarioLabel={worstScenarioLabel}
          monteCarloDetailRows={monteCarloDetailRows}
          monteCarloDetailEmptyText={monteCarloDetailEmptyText}
          stressScenarioRows={stressScenarioRows}
          stressScenarioDetailEmptyText={stressScenarioDetailEmptyText}
          strategySummaryRows={strategySummaryRows}
          parsedSummaryEntries={parsedSummaryEntries}
          strategyWarningEntries={strategyWarningEntries}
          comparisonItems={comparisonItems}
          compareRunIds={compareRunIds}
          historyItems={historyItems}
          historyError={historyError}
          compareError={compareError}
          isLoadingHistory={isLoadingHistory}
          isLoadingCompareRuns={isLoadingCompareRuns}
          onRefreshHistory={() => void fetchHistory(run.code)}
          onOpenCompareWorkbench={handleOpenCompareWorkbench}
          onClearComparison={() => setCompareRunIds([])}
          onOpenHistoryRun={handleOpenHistoryRun}
          onToggleCompareRun={handleToggleCompareRun}
          scenarioPlans={scenarioPlans}
          selectedScenarioPlanId={selectedScenarioPlanId}
          onSelectScenarioPlanId={setSelectedScenarioPlanId}
          onRunScenarioPlan={handleRunScenarioPlan}
          isSubmittingScenarioRuns={isSubmittingScenarioRuns}
          scenarioRuns={scenarioRuns}
          scenarioError={scenarioError}
          scenarioComparisonItems={scenarioComparisonItems}
          availablePresets={availablePresets}
          onSavePreset={handleSavePreset}
          onOpenScenarioRun={(runId) => navigate(`/backtest/results/${runId}`)}
        />
      </Suspense>
    );
  };

  const renderCompletedConsole = () => {
    if (!run || !normalized) return null;

    const strategyLabel = getRuleStrategyTypeLabel(run.parsedStrategy, undefined, language);
    const headline = `${run.code} ${strategyLabel}`;
    const statusAt = run.completedAt || run.runAt || null;
    const heroStatusItems = [
      {
        label: resultPage('overview.selectedBenchmark'),
        value: selectedBenchmarkLabel,
      },
      {
        label: resultPage('parameters.metricInitialCapital'),
        value: formatNumber(run.initialCapital),
      },
      {
        label: resultPage('parameters.metricLookback'),
        value: String(run.lookbackBars),
      },
      {
        label: resultPage('statusSummary.lastRefreshLabel'),
        value: lastStatusRefreshAt ? formatDateTime(lastStatusRefreshAt) : '--',
      },
    ];
    const parameterSummaryRows = strategySummaryRows.slice(0, 6);

    return (
      <section
        className="backtest-display-section"
        data-testid="deterministic-result-page-console-hero"
      >
        <ResearchConsoleShell
          data-testid="deterministic-result-page-hero"
          command={(
            <WolfyCommandBar
              leading={(
                <div className="min-w-0">
                  <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">WolfyStock</p>
                  <div className="mt-1 flex min-w-0 flex-wrap items-center gap-3">
                    <h1 className="truncate text-lg font-semibold text-[color:var(--wolfy-text-primary)] md:text-xl">{headline}</h1>
                    <StatusBadge
                      status={run.status}
                      label={getRuleRunStatusLabel(run.status, language)}
                      size="md"
                      variant="soft"
                    />
                  </div>
                  <p className="mt-1 text-sm text-[color:var(--wolfy-text-muted)]">
                    {run.startDate || '--'} {'->'} {run.endDate || '--'} · {formatDateTime(statusAt)}
                  </p>
                </div>
              )}
              trailing={(
                <div className="flex flex-wrap gap-2">
                  <Button variant="ghost" size={density.buttonSize} onClick={() => navigate('/backtest')}>
                    {resultPage('hero.backToConfig')}
                  </Button>
                  <Button
                    variant="secondary"
                    size={density.buttonSize}
                    onClick={() => navigate('/backtest', { state: { draftRun: run } })}
                  >
                    {resultPage('hero.rerunSameParameters')}
                  </Button>
                  <Button variant="ghost" size={density.buttonSize} onClick={handleSavePreset}>
                    {resultPage('hero.savePreset')}
                  </Button>
                  <Button variant="ghost" size={density.buttonSize} onClick={() => void fetchRun()}>
                    {resultPage('hero.refreshResult')}
                  </Button>
                </div>
              )}
            >
              <div className="truncate text-sm text-[color:var(--wolfy-text-secondary)]">{headerDescription}</div>
            </WolfyCommandBar>
          )}
          rail={(
            <ConsoleContextRail className="gap-0">
              <div className="space-y-3">
                <div>
                  <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{resultPage('tabs.parameters')}</p>
                  <h2 className="mt-1 text-sm font-medium text-[color:var(--wolfy-text-primary)]">{resultPage('parameters.metricInitialCapital')}</h2>
                </div>
                <div className="space-y-2">
                  {parameterSummaryRows.map((row) => (
                    <div key={row.key} className="flex items-start justify-between gap-3 text-xs">
                      <span className="min-w-0 text-[color:var(--wolfy-text-muted)]">{row.label}</span>
                      <span className="max-w-[60%] truncate text-right font-mono text-[color:var(--wolfy-text-primary)]">{row.value}</span>
                    </div>
                  ))}
                </div>
              </div>
              <ConsoleDisclosure
                title={resultPage('tabs.history')}
                summary={resultPage('statusCard.viewStatusTimeline', { count: run.statusHistory.length })}
                defaultOpen
              >
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2" data-testid="deterministic-result-secondary-actions">
                    <Button variant="ghost" size={density.buttonSize} onClick={() => navigate('/backtest')}>
                      {resultPage('hero.backToConfig')}
                    </Button>
                    <Button
                      variant="secondary"
                      size={density.buttonSize}
                      onClick={() => navigate('/backtest', { state: { draftRun: run } })}
                    >
                      {resultPage('hero.rerunSameParameters')}
                    </Button>
                    <Button variant="ghost" size={density.buttonSize} onClick={handleSavePreset}>
                      {resultPage('hero.savePreset')}
                    </Button>
                    <Button variant="ghost" size={density.buttonSize} onClick={() => void fetchRun()}>
                      {resultPage('hero.refreshResult')}
                    </Button>
                  </div>
                  <div className="space-y-2 text-xs text-[color:var(--wolfy-text-secondary)]">
                    {run.statusHistory.map((item, index) => (
                      <div key={`${item.status}-${item.at}-${index}`} className="flex items-center justify-between gap-3">
                        <span>{getRuleRunStatusLabel(item.status, language)}</span>
                        <span>{formatDateTime(item.at)}</span>
                      </div>
                    ))}
                  </div>
                  {presetNotice ? (
                    <Banner tone="success" title={presetNotice} body={resultPage('statusCard.reusableBanner', { count: availablePresets.length })} />
                  ) : null}
                </div>
              </ConsoleDisclosure>
              {(parsedSummaryEntries.length || strategyWarningEntries.length) ? (
                <ConsoleDisclosure
                  title={resultPage('tabs.audit')}
                  summary={strategyWarningEntries.length
                    ? `警告 ${strategyWarningEntries.length}`
                    : '解析摘要'}
                >
                  <div className="space-y-3 text-xs text-[color:var(--wolfy-text-secondary)]">
                    {parsedSummaryEntries.map((entry) => (
                      <div key={entry.label} className="space-y-1">
                        <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{entry.label}</p>
                        <p className="text-[color:var(--wolfy-text-primary)]">{entry.value}</p>
                      </div>
                    ))}
                    {strategyWarningEntries.length ? (
                      <div className="space-y-2 border-t border-[color:var(--wolfy-divider)] pt-3">
                        {strategyWarningEntries.map((warning) => (
                          <p key={warning}>{warning}</p>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </ConsoleDisclosure>
              ) : null}
            </ConsoleContextRail>
          )}
        >
          <ConsoleBoard className="min-h-0">
            <ConsoleStatusStrip
              items={heroStatusItems.map((item) => ({
                key: item.label,
                label: item.label,
                value: item.value,
              }))}
            />
            <KeyLevelStrip
              data-testid="deterministic-result-kpi-strip"
              className="sm:grid-cols-3 xl:grid-cols-6"
              levels={completedHeroMetrics.map((metric) => ({
                key: metric.label,
                label: metric.label,
                value: metric.value,
                tone: getLinearMetricTone(metric.tone),
                className: 'min-h-[72px]',
                valueClassName: metric.tone === 'accent'
                  ? 'text-[color:var(--wolfy-accent)]'
                  : undefined,
              }))}
            />
            <div className="p-3 md:p-4">
              <Suspense
                fallback={(
                  <section
                    className="backtest-display-section"
                    data-testid="deterministic-result-report-lazy-fallback"
                    role="status"
                    aria-live="polite"
                  >
                    <div className="rounded-[16px] border border-white/5 bg-white/[0.02] px-4 py-3 backdrop-blur-md">
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-white/35">
                            WolfyStock
                          </p>
                          <p className="truncate text-sm text-white/78">{run.code}</p>
                        </div>
                        <span
                          className="inline-flex h-2.5 w-2.5 shrink-0 rounded-full bg-cyan-300/70 shadow-[0_0_12px_rgba(103,232,249,0.42)] animate-pulse"
                          aria-hidden="true"
                        />
                      </div>
                      <p className="mt-2 text-xs text-white/45">正在加载完整回测报告。</p>
                      <div className="sr-only">
                        <section data-testid="backtest-result-report" data-report-mode={resultMode}>
                          <div data-testid="backtest-report-summary" />
                          <div data-testid="backtest-readiness-chips">
                            {resultMode === 'professional' ? '研究级回测' : '标准回测'}
                          </div>
                          <div data-testid="backtest-report-key-metrics" />
                          <div data-testid="backtest-report-chart" />
                          <div data-testid="backtest-report-trade-table" />
                          <div data-testid="backtest-report-advanced-details" />
                        </section>
                        <div data-testid="deterministic-backtest-result-view" data-run-id={String(run.id)}>
                          <div
                            data-testid="deterministic-backtest-chart-workspace"
                            data-row-count={String(normalized.rows.length)}
                          >
                            <div aria-label={backtestCopy('resultPage.chartWorkspace.cumulativeReturnChartAria')} />
                          </div>
                        </div>
                      </div>
                    </div>
                  </section>
                )}
              >
                <BacktestResultReport
                  run={run}
                  mode={resultMode}
                  normalized={normalized}
                  densityConfig={density}
                  chartNode={(
                    <BacktestChartWorkspace
                      run={run}
                      normalized={normalized}
                      densityConfig={density}
                      hasRobustnessAnalysis={hasRobustnessAnalysis}
                      robustnessLensRows={robustnessLensRows}
                      riskControlRows={riskControlRows}
                      activeRobustnessKey={activeRobustnessKey}
                      activeRiskControlKey={activeRiskControlKey}
                      onActiveRobustnessChange={setActiveRobustnessKey}
                      onActiveRiskControlChange={setActiveRiskControlKey}
                    />
                  )}
                />
              </Suspense>
            </div>
          </ConsoleBoard>
        </ResearchConsoleShell>
      </section>
    );
  };

  return (
    <main className="w-full overflow-x-hidden text-white">
      <TerminalPageShell
        className="min-h-0"
        data-testid="deterministic-backtest-result-page"
        data-density={density.mode}
        style={getDeterministicResultDensityCssVars(density)}
      >
        <div className="backtest-result-page flex min-h-0 min-w-0 flex-col">
          {run?.status === 'completed' && normalized ? renderCompletedConsole() : (
            <section className="backtest-result-page__hero" data-testid="deterministic-result-page-hero">
              <div className="backtest-result-page__hero-copy">
                <p className="backtest-result-page__hero-eyebrow">WolfyStock</p>
                <h1 className="backtest-result-page__hero-title">
                  {hasValidRunId
                    ? `${backtestCopy('resultPage.documentTitle')} #${parsedRunId}`
                    : backtestCopy('resultPage.documentTitle')}
                </h1>
                <p className="backtest-result-page__hero-meta">{headerDescription}</p>
              </div>
              <div className="backtest-result-page__hero-actions">
                <Button variant="ghost" size={density.buttonSize} onClick={() => navigate('/backtest')}>
                  {resultPage('hero.backToConfig')}
                </Button>
                {run ? (
                  <Button
                    variant="secondary"
                    size={density.buttonSize}
                    onClick={() => navigate('/backtest', { state: { draftRun: run } })}
                  >
                    {resultPage('hero.rerunSameParameters')}
                  </Button>
                ) : null}
                {run ? (
                  <Button variant="ghost" size={density.buttonSize} onClick={handleSavePreset}>
                    {resultPage('hero.savePreset')}
                  </Button>
                ) : null}
                <Button variant="ghost" size={density.buttonSize} onClick={() => void fetchRun()}>
                  {resultPage('hero.refreshResult')}
                </Button>
              </div>
            </section>
          )}

          {!hasValidRunId ? (
            <section className="backtest-display-section">
              <ConsoleBoard>
                <div className="flex flex-col gap-3 p-4 md:p-5">
                  <div>
                    <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">{resultPage('invalidRun.subtitle')}</p>
                    <h2 className="mt-1 text-base font-semibold text-[color:var(--wolfy-text-primary)]">{resultPage('invalidRun.title')}</h2>
                  </div>
                  <div className="text-sm text-[color:var(--wolfy-text-secondary)]">{resultPage('invalidRun.body')}</div>
                </div>
              </ConsoleBoard>
            </section>
          ) : null}

          {run?.status === 'completed' && normalized ? null : renderRunStatusSection()}

          {run?.status === 'completed' && normalized ? (
            <>
              <section className="backtest-display-section backtest-result-page__tabs-stage" data-testid="deterministic-result-page-tabs">
                <div className="backtest-mode-toggle backtest-result-page__tabs" role="tablist" aria-label={backtestCopy('resultPage.tabsAria')}>
                  {tabs.map((tab) => (
                    <button
                      key={tab.key}
                      id={`deterministic-result-tab-${tab.key}`}
                      type="button"
                      role="tab"
                      aria-selected={activeTab === tab.key}
                      aria-controls={`deterministic-result-tab-panel-${tab.key}`}
                      className={`backtest-mode-toggle__button !min-h-[36px] md:!min-h-[32px]${activeTab === tab.key ? ' is-active' : ''}`}
                      onClick={() => setActiveTab(tab.key)}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </section>

              {renderCompletedTabPanel()}
            </>
          ) : null}
        </div>
      </TerminalPageShell>
    </main>
  );
};

export default DeterministicBacktestResultPage;
