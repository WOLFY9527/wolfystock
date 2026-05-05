import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { backtestApi } from '../api/backtest';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Button, Card } from '../components/common';
import BacktestAuditTables from '../components/backtest/BacktestAuditTables';
import BacktestResultReport, { type BacktestResultReportMode } from '../components/backtest/BacktestResultReport';
import BacktestChartWorkspace, {
  type CoverageTrackItem,
  type RiskControlVisualRow,
} from '../components/backtest/BacktestChartWorkspace';
import BacktestOverviewSummary from '../components/backtest/BacktestOverviewSummary';
import {
  getDeterministicResultDensityCssVars,
  useDeterministicResultDensity,
} from '../components/backtest/deterministicResultDensity';
import { normalizeDeterministicBacktestResult } from '../components/backtest/normalizeDeterministicBacktestResult';
import {
  Banner,
  Disclosure,
  MetricCard,
  RuleRunStatusBanner,
  SummaryStrip,
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
  StatusHistoryItem,
} from '../types/backtest';
import { useI18n } from '../contexts/UiLanguageContext';
import { translate, type UiLanguage } from '../i18n/core';
import { StatusBadge } from '../components/ui/StatusBadge';

const RULE_POLL_INTERVAL_MS = 1800;
const RESULT_HISTORY_PAGE_SIZE = 10;

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

type ResultPageTabKey = 'overview' | 'audit' | 'trades' | 'parameters' | 'history';

const RESULT_PAGE_TAB_KEYS: ResultPageTabKey[] = ['overview', 'audit', 'trades', 'parameters', 'history'];

function formatStatusHistoryLabel(item: StatusHistoryItem): string {
  return `${String(item.status || '--')} · ${item.at ? formatDateTime(item.at) : '--'}`;
}

function formatSummaryLabel(key: string): string {
  return key
    .replaceAll(/([a-z])([A-Z])/g, '$1 $2')
    .replaceAll('_', ' ')
    .trim();
}

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

function pctDrawdown(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return pct(value);
  return pct(value > 0 ? -value : value);
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

function btr(language: UiLanguage, key: string, vars?: Record<string, string | number | undefined>): string {
  return translate(language, `backtest.resultPage.${key}`, vars);
}

function getRobustnessStateLabel(value: unknown, language: UiLanguage): string {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'available') return btr(language, 'robustnessState.available');
  if (normalized === 'partial') return btr(language, 'robustnessState.partial');
  if (normalized === 'unavailable') return btr(language, 'robustnessState.unavailable');
  return normalized ? String(value) : '--';
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
  const parsedRunId = useMemo(() => Number.parseInt(runId || '', 10), [runId]);
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
  const hasRobustnessAnalysis = useMemo(
    () => Boolean(
      getObjectField(robustnessAnalysis, 'state')
      || hasObjectFields(walkForward)
      || hasObjectFields(monteCarlo)
      || hasObjectFields(stressTests)
    ),
    [monteCarlo, robustnessAnalysis, stressTests, walkForward],
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
        detail: btr(language, 'riskControls.worst', { value: String(getObjectField(worstScenario, 'scenarioKey') || '--') }),
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
    worstScenario,
  ]);
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

  const handleOpenHistoryRun = useCallback((item: RuleBacktestHistoryItem) => {
    navigate(`/backtest/results/${item.id}`);
  }, [navigate]);

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
    .map(([key, value]) => ({ label: formatSummaryLabel(key), value: String(value) }));
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
  const compareWorkbenchRunIds = useMemo(
    () => (run ? [run.id, ...compareRunIds] : []),
    [compareRunIds, run],
  );
  const localizedNoResultMessage = isCanonicalNoEntrySignalMessage(run?.noResultMessage)
    ? resultPage('noEntrySignal')
    : (run?.noResultMessage || null);
  const statusSummaryItems = run ? [
    {
      label: resultPage('statusSummary.currentStageLabel'),
      value: getRuleRunStatusLabel(run.status, language),
      note: language === 'en'
        ? (localizedNoResultMessage || getRuleRunStatusDescription(run.status, language))
        : (run.statusMessage || localizedNoResultMessage || getRuleRunStatusDescription(run.status, language)),
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
      value: pctDrawdown(normalized.metrics.maxDrawdownPct),
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

  const handleToggleCompareRun = useCallback((item: RuleBacktestHistoryItem) => {
    setCompareRunIds((current) => {
      if (current.includes(item.id)) return current.filter((id) => id !== item.id);
      return [...current, item.id].slice(0, 3);
    });
  }, []);

  const handleOpenCompareWorkbench = useCallback(() => {
    if (!run || compareRunIds.length === 0) return;
    const params = new URLSearchParams({
      runIds: compareWorkbenchRunIds.join(','),
    });
    navigate(`/backtest/compare?${params.toString()}`);
  }, [compareRunIds.length, compareWorkbenchRunIds, navigate, run]);

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

  const handleExportDecisionReport = useCallback((format: 'md' | 'html') => {
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
  }, [decisionReportMarkdown, normalized, resultPage, run]);

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
          <Card title={resultPage('statusCard.title')} subtitle={resultPage('statusCard.loadingSubtitle')} className="product-section-card product-section-card--backtest-result">
            <div className="product-empty-state product-empty-state--compact">{resultPage('statusCard.loadingBody')}</div>
          </Card>
        </section>
      );
    }

    if (!run) {
      return (
        <section className="backtest-display-section" data-testid="deterministic-result-page-status">
          <Card title={resultPage('statusCard.title')} subtitle={resultPage('statusCard.unavailableSubtitle')} className="product-section-card product-section-card--backtest-result">
            {runError ? <ApiErrorAlert error={runError} /> : <div className="product-empty-state product-empty-state--compact">{resultPage('statusCard.unavailableBody')}</div>}
          </Card>
        </section>
      );
    }

    return (
      <section className="backtest-display-section" data-testid="deterministic-result-page-status">
        <Card title={resultPage('statusCard.title')} subtitle={resultPage('statusCard.controlsSubtitle')} className="product-section-card product-section-card--backtest-result">
          <RuleRunStatusBanner run={run} />
          <SummaryStrip items={statusSummaryItems} />
          {!isRuleRunTerminal(run.status) ? (
            <div className="mt-4">
              <Banner
                tone="info"
                title={resultPage('statusCard.autoTrackingTitle')}
                body={resultPage('statusCard.autoTrackingBody')}
              />
            </div>
          ) : null}
          {run.status === 'completed' ? (
            <div className="mt-4">
              <Banner
                tone="success"
                title={resultPage('statusCard.completedTitle')}
                body={resultPage('statusCard.completedBody')}
              />
            </div>
          ) : null}
          {run.status === 'cancelled' ? (
            <div className="mt-4">
              <Banner
                tone="warning"
                title={resultPage('statusCard.cancelledTitle')}
                body={resultPage('statusCard.cancelledBody')}
              />
            </div>
          ) : null}
          {run.status === 'failed' ? (
            <div className="mt-4">
              <Banner
                tone="danger"
                title={resultPage('statusCard.failedTitle')}
                body={resultPage('statusCard.failedBody')}
              />
            </div>
          ) : null}
          <div className="product-action-row mt-4">
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
                    {index + 1}. {formatStatusHistoryLabel(item)}
                  </span>
                ))}
              </div>
            </Disclosure>
          ) : null}
          {runError ? <ApiErrorAlert error={runError} className="mt-4" /> : null}
          {cancelError ? <ApiErrorAlert error={cancelError} className="mt-4" /> : null}
          {presetNotice ? (
            <div className="mt-4">
              <Banner tone="success" title={presetNotice} body={resultPage('statusCard.reusableBanner', { count: availablePresets.length })} />
            </div>
          ) : null}
        </Card>
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
          decisionReportMarkdown={decisionReportMarkdown}
          onExportDecisionReport={handleExportDecisionReport}
        />
      );
    }

    return (
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
        worstScenarioKey={String(getObjectField(worstScenario, 'scenarioKey') || '--')}
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
    );
  };

  const renderCompletedHero = () => {
    if (!run || !normalized) return null;

    const strategyLabel = getRuleStrategyTypeLabel(run.parsedStrategy, undefined, language);
    const headline = `${run.code} ${strategyLabel}`;
    const statusAt = run.completedAt || run.runAt || null;

    return (
      <section
        className="backtest-display-section"
        data-testid="deterministic-result-page-bento-hero"
      >
        <div className="backtest-result-bento">
          <div className="backtest-result-bento__intro" data-testid="deterministic-result-page-hero">
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-3">
                <StatusBadge
                  status={run.status}
                  label={getRuleRunStatusLabel(run.status, language)}
                  size="md"
                  variant="soft"
                />
                <span className="text-sm text-white/40">{formatDateTime(statusAt)}</span>
              </div>
              <div className="space-y-2">
                <p className="backtest-result-bento__eyebrow">WolfyStock</p>
                <h1 className="backtest-result-bento__title">{headline}</h1>
                <p className="backtest-result-bento__meta">
                  {run.startDate || '--'} {'->'} {run.endDate || '--'}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm text-white/72">
                <div className="backtest-result-bento__fact">
                  <span>{resultPage('overview.selectedBenchmark')}</span>
                  <strong>{selectedBenchmarkLabel}</strong>
                </div>
                <div className="backtest-result-bento__fact">
                  <span>{resultPage('parameters.metricInitialCapital')}</span>
                  <strong>{formatNumber(run.initialCapital)}</strong>
                </div>
                <div className="backtest-result-bento__fact">
                  <span>{resultPage('parameters.metricLookback')}</span>
                  <strong>{String(run.lookbackBars)}</strong>
                </div>
                <div className="backtest-result-bento__fact">
                  <span>{resultPage('statusSummary.lastRefreshLabel')}</span>
                  <strong>{lastStatusRefreshAt ? formatDateTime(lastStatusRefreshAt) : '--'}</strong>
                </div>
              </div>
            </div>
            <div className="backtest-result-bento__actions">
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
          </div>
          <div className="backtest-result-bento__metrics" data-testid="deterministic-result-kpi-bento">
            {completedHeroMetrics.map((metric) => (
              <MetricCard
                key={metric.label}
                label={metric.label}
                value={metric.value}
                tone={metric.tone}
                note={metric.note}
              />
            ))}
          </div>
        </div>
      </section>
    );
  };

  return (
    <div
      className="theme-page-transition backtest-v1-page workspace-page--backtest backtest-result-page"
      data-testid="deterministic-backtest-result-page"
      data-density={density.mode}
      style={getDeterministicResultDensityCssVars(density)}
    >
      {run?.status === 'completed' && normalized ? renderCompletedHero() : (
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
          <Card title={resultPage('invalidRun.title')} subtitle={resultPage('invalidRun.subtitle')} className="product-section-card product-section-card--backtest-result">
            <div className="product-empty-state product-empty-state--compact">{resultPage('invalidRun.body')}</div>
          </Card>
        </section>
      ) : null}

      {run?.status === 'completed' && normalized ? null : renderRunStatusSection()}

      {run?.status === 'completed' && normalized ? (
        <>
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
  );
};

export default DeterministicBacktestResultPage;
