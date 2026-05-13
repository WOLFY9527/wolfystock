import type React from 'react';
import { ApiErrorAlert, Button, Card } from '../common';
import {
  AssumptionList,
  Disclosure,
  RuleRunsTable,
  SummaryStrip,
  formatDateTime,
  formatNumber,
  getRuleRunStatusLabel,
  pct,
} from './shared';
import ExecutionTracePanel from './ExecutionTracePanel';
import { RuleRunComparisonPanel, type RuleComparisonItem } from './RuleRunComparisonPanel';
import {
  DeterministicAuditTable,
  DeterministicTradeEventTable,
} from './DeterministicBacktestResultView';
import BacktestSupportExportsDisclosure from './BacktestSupportExportsDisclosure';
import {
  formatRuleNormalizationStateLabel,
  getRuleStrategySpecSourceLabel,
  getRuleStrategyTypeLabel,
} from './strategyInspectability';
import type { RuleBacktestPreset } from './ruleBacktestP6';
import {
  RiskControlsLadder,
  RobustnessCoverageTrack,
  type CoverageTrackItem,
  type RiskControlVisualRow,
} from './BacktestChartWorkspace';
import type { ParsedApiError } from '../../api/error';
import type {
  RuleBacktestDrawdownRegimeAttribution,
  RuleBacktestHistoryItem,
  RuleBacktestRunResponse,
} from '../../types/backtest';
import type { DeterministicBacktestNormalizedResult } from './normalizeDeterministicBacktestResult';
import type { UiLanguage } from '../../i18n/core';

type TranslateFn = (key: string, vars?: Record<string, string | number | undefined>) => string;
type ResultPageTabKey = 'audit' | 'trades' | 'parameters' | 'history';

type StrategySummaryRow = {
  label: string;
  value: string;
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

type ScenarioPlan = {
  id: string;
  label: string;
  description: string;
  variants: Array<{ id: string; label: string }>;
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

type DrawdownAttributionState = 'available' | 'partial' | 'unavailable';
type DrawdownAttributionBucketKey = 'peak' | 'shallow' | 'moderate' | 'deep' | 'severe' | 'unknown';

type DrawdownAttributionBucketRow = {
  key: string;
  label: string;
  count: string;
  share: string;
  avgDepth: string;
  worstDepth: string;
};

type DrawdownAttributionPanelModel = {
  stateLabel: string;
  sourceLabel: string;
  description: string;
  bucketCountSummary: string;
  classifiedShare: string;
  missingShare: string;
  bucketRows: DrawdownAttributionBucketRow[];
};

type BacktestAuditTablesProps = {
  activeTab: ResultPageTabKey;
  resultPage: TranslateFn;
  backtestCopy: TranslateFn;
  language: UiLanguage;
  run: RuleBacktestRunResponse;
  normalized: DeterministicBacktestNormalizedResult;
  selectedBenchmarkLabel: string;
  buyAndHoldLabel: string;
  benchmarkStatusNote: string;
  hasRobustnessAnalysis: boolean;
  robustnessAnalysisStateLabel: string;
  robustnessLensRows: CoverageTrackItem[];
  riskControlRows: RiskControlVisualRow[];
  activeRobustnessKey: string | null;
  activeRiskControlKey: RiskControlVisualRow['key'] | null;
  walkForwardWindowCount: string;
  monteCarloSimulationCount: string;
  stressScenarioCount: string;
  walkForwardMeanReturn: string;
  monteCarloMedianReturn: string;
  worstScenarioLabel: string;
  monteCarloDetailRows: RobustnessMetricRow[];
  monteCarloDetailEmptyText: string;
  stressScenarioRows: StressScenarioDetail[];
  stressScenarioDetailEmptyText: string;
  strategySummaryRows: StrategySummaryRow[];
  parsedSummaryEntries: Array<{ label: string; value: string }>;
  strategyWarningEntries: string[];
  comparisonItems: RuleComparisonItem[];
  compareRunIds: number[];
  historyItems: RuleBacktestHistoryItem[];
  historyError: ParsedApiError | null;
  compareError: ParsedApiError | null;
  isLoadingHistory: boolean;
  isLoadingCompareRuns: boolean;
  onRefreshHistory: () => void;
  onOpenCompareWorkbench: () => void;
  onClearComparison: () => void;
  onOpenHistoryRun: (item: RuleBacktestHistoryItem) => void;
  onToggleCompareRun: (item: RuleBacktestHistoryItem) => void;
  scenarioPlans: ScenarioPlan[];
  selectedScenarioPlanId: string | null;
  onSelectScenarioPlanId: (value: string) => void;
  onRunScenarioPlan: () => Promise<void>;
  isSubmittingScenarioRuns: boolean;
  scenarioRuns: ScenarioRunState[];
  scenarioError: ParsedApiError | null;
  scenarioComparisonItems: RuleComparisonItem[];
  availablePresets: RuleBacktestPreset[];
  onSavePreset: () => void;
  onOpenScenarioRun: (runId: number) => void;
};

const DRAWDOWN_ATTRIBUTION_STATES = new Set<DrawdownAttributionState>(['available', 'partial', 'unavailable']);
const DRAWDOWN_ATTRIBUTION_BUCKET_ORDER: DrawdownAttributionBucketKey[] = [
  'peak',
  'shallow',
  'moderate',
  'deep',
  'severe',
  'unknown',
];

function isDrawdownAttributionPayload(value: unknown): value is RuleBacktestDrawdownRegimeAttribution {
  return value != null && typeof value === 'object';
}

function getStoredDrawdownAttribution(run: RuleBacktestRunResponse): RuleBacktestDrawdownRegimeAttribution | null {
  const attribution = run.summary?.drawdownRegimeAttribution;
  return isDrawdownAttributionPayload(attribution) ? attribution : null;
}

function normalizeDrawdownAttributionState(value: string | null | undefined): DrawdownAttributionState {
  const normalized = String(value || '').trim().toLowerCase();
  return DRAWDOWN_ATTRIBUTION_STATES.has(normalized as DrawdownAttributionState)
    ? normalized as DrawdownAttributionState
    : 'unavailable';
}

function formatDrawdownAttributionCount(value: number | null | undefined): string {
  return value == null ? '--' : formatNumber(value, 0);
}

function formatDrawdownAttributionPercent(value: number | null | undefined): string {
  return value == null ? '--' : pct(value);
}

function getDrawdownAttributionSourceLabel(
  source: string | null | undefined,
  state: DrawdownAttributionState,
  resultPage: TranslateFn,
): string {
  if (state === 'unavailable' || String(source || '').trim().toLowerCase() === 'unavailable') {
    return resultPage('drawdownAttribution.sources.unavailable');
  }
  return resultPage('drawdownAttribution.sources.storedAuditRows');
}

function getDrawdownAttributionBucketLabel(key: string, resultPage: TranslateFn): string {
  const translation = resultPage(`drawdownAttribution.buckets.${key}`);
  return translation === `backtest.resultPage.drawdownAttribution.buckets.${key}` ? key : translation;
}

function getOrderedDrawdownAttributionBuckets(
  attribution: RuleBacktestDrawdownRegimeAttribution | null,
): Array<[string, NonNullable<RuleBacktestDrawdownRegimeAttribution['bucketCounts']>[string]]> {
  const bucketCounts = attribution?.bucketCounts;
  if (!bucketCounts || typeof bucketCounts !== 'object') {
    return [];
  }

  const ordered = DRAWDOWN_ATTRIBUTION_BUCKET_ORDER
    .filter((key) => isDrawdownAttributionPayload(bucketCounts[key]))
    .map((key) => [key, bucketCounts[key]!] as [string, NonNullable<RuleBacktestDrawdownRegimeAttribution['bucketCounts']>[string]]);

  const remaining = Object.entries(bucketCounts)
    .filter(([key, value]) => !DRAWDOWN_ATTRIBUTION_BUCKET_ORDER.includes(key as DrawdownAttributionBucketKey) && isDrawdownAttributionPayload(value))
    .map(([key, value]) => [key, value] as [string, NonNullable<RuleBacktestDrawdownRegimeAttribution['bucketCounts']>[string]]);

  return [...ordered, ...remaining];
}

function buildDrawdownAttributionPanelModel(
  run: RuleBacktestRunResponse,
  resultPage: TranslateFn,
): DrawdownAttributionPanelModel {
  const attribution = getStoredDrawdownAttribution(run);
  const state = normalizeDrawdownAttributionState(attribution?.state);
  const classifiedRows = attribution?.contributionSummaries?.classifiedRows;
  const missingRows = attribution?.contributionSummaries?.missingRows;
  const bucketRows = getOrderedDrawdownAttributionBuckets(attribution).map(([key, bucket]) => ({
    key,
    label: getDrawdownAttributionBucketLabel(key, resultPage),
    count: formatDrawdownAttributionCount(bucket.count),
    share: formatDrawdownAttributionPercent(bucket.sharePct),
    avgDepth: formatDrawdownAttributionPercent(bucket.avgDepthPct),
    worstDepth: formatDrawdownAttributionPercent(bucket.worstDepthPct),
  }));

  return {
    stateLabel: resultPage(`drawdownAttribution.states.${state}`),
    sourceLabel: getDrawdownAttributionSourceLabel(attribution?.source, state, resultPage),
    description: resultPage(`drawdownAttribution.descriptions.${state}`),
    bucketCountSummary: attribution
      ? `${formatDrawdownAttributionCount(bucketRows.length)} / ${formatDrawdownAttributionCount(classifiedRows?.count)}`
      : '--',
    classifiedShare: attribution ? formatDrawdownAttributionPercent(classifiedRows?.sharePct) : '--',
    missingShare: attribution ? formatDrawdownAttributionPercent(missingRows?.sharePct) : '--',
    bucketRows,
  };
}

const BacktestAuditTables: React.FC<BacktestAuditTablesProps> = ({
  activeTab,
  resultPage,
  backtestCopy,
  language,
  run,
  normalized,
  selectedBenchmarkLabel,
  buyAndHoldLabel,
  benchmarkStatusNote,
  hasRobustnessAnalysis,
  robustnessAnalysisStateLabel,
  robustnessLensRows,
  riskControlRows,
  activeRobustnessKey,
  activeRiskControlKey,
  walkForwardWindowCount,
  monteCarloSimulationCount,
  stressScenarioCount,
  walkForwardMeanReturn,
  monteCarloMedianReturn,
  worstScenarioLabel,
  monteCarloDetailRows,
  monteCarloDetailEmptyText,
  stressScenarioRows,
  stressScenarioDetailEmptyText,
  strategySummaryRows,
  parsedSummaryEntries,
  strategyWarningEntries,
  comparisonItems,
  compareRunIds,
  historyItems,
  historyError,
  compareError,
  isLoadingHistory,
  isLoadingCompareRuns,
  onRefreshHistory,
  onOpenCompareWorkbench,
  onClearComparison,
  onOpenHistoryRun,
  onToggleCompareRun,
  scenarioPlans,
  selectedScenarioPlanId,
  onSelectScenarioPlanId,
  onRunScenarioPlan,
  isSubmittingScenarioRuns,
  scenarioRuns,
  scenarioError,
  scenarioComparisonItems,
  availablePresets,
  onSavePreset,
  onOpenScenarioRun,
}) => {
  const drawdownAttribution = buildDrawdownAttributionPanelModel(run, resultPage);
  const denseParameterItems = [
    { label: resultPage('parameters.metricInitialCapital'), value: formatNumber(run.initialCapital) },
    { label: resultPage('parameters.metricLookback'), value: String(run.lookbackBars) },
    { label: resultPage('parameters.metricFeesSlippage'), value: `${formatNumber(run.feeBps, 1)}bp / ${formatNumber(run.slippageBps, 1)}bp` },
    { label: resultPage('parameters.metricParseConfidence'), value: run.parsedConfidence == null ? '--' : pct(run.parsedConfidence * 100) },
    { label: resultPage('parameters.instrument'), value: run.code },
    { label: resultPage('parameters.timeframe'), value: run.timeframe || '--' },
    { label: resultPage('parameters.backtestWindow'), value: `${run.startDate || '--'} -> ${run.endDate || '--'}` },
    { label: resultPage('parameters.submittedAt'), value: formatDateTime(run.runAt) },
    { label: resultPage('parameters.completedAt'), value: formatDateTime(run.completedAt) },
    { label: resultPage('parameters.chipStrategyFamily'), value: getRuleStrategyTypeLabel(run.parsedStrategy, undefined, language) },
    { label: resultPage('parameters.chipSpecSource'), value: getRuleStrategySpecSourceLabel(run.parsedStrategy, language) },
    { label: resultPage('parameters.chipNormalization'), value: formatRuleNormalizationStateLabel(run.parsedStrategy.normalizationState, language) },
  ];

  if (activeTab === 'audit') {
    return (
      <section
        className="backtest-display-section"
        id="deterministic-result-tab-panel-audit"
        data-testid="deterministic-result-tab-panel-audit"
        role="tabpanel"
        aria-labelledby="deterministic-result-tab-audit"
      >
        <ExecutionTracePanel run={run} />
        <BacktestSupportExportsDisclosure runId={run.id} code={run.code} />
        <div className="summary-block mt-4" data-testid="backtest-drawdown-attribution-panel">
          <div className="summary-block__header">
            <div>
              <h3 className="summary-block__title">{resultPage('drawdownAttribution.title')}</h3>
              <p className="product-section-copy">{drawdownAttribution.description}</p>
            </div>
          </div>
          <SummaryStrip
            items={[
              { label: resultPage('drawdownAttribution.summary.state'), value: drawdownAttribution.stateLabel },
              { label: resultPage('drawdownAttribution.summary.source'), value: drawdownAttribution.sourceLabel },
              { label: resultPage('drawdownAttribution.summary.bucketCount'), value: drawdownAttribution.bucketCountSummary },
              { label: resultPage('drawdownAttribution.summary.classifiedShare'), value: drawdownAttribution.classifiedShare },
              { label: resultPage('drawdownAttribution.summary.missingShare'), value: drawdownAttribution.missingShare },
            ]}
          />
          {drawdownAttribution.bucketRows.length ? (
            <div className="preview-grid mt-4">
              {drawdownAttribution.bucketRows.map((row) => (
                <div key={row.key} className="preview-card">
                  <p className="metric-card__label">{resultPage('drawdownAttribution.bucketLabel')}</p>
                  <p className="preview-card__text">{row.label}</p>
                  <div className="product-chip-list product-chip-list--tight mt-3">
                    <span className="product-chip">{resultPage('drawdownAttribution.bucketMetrics.count', { value: row.count })}</span>
                    <span className="product-chip">{resultPage('drawdownAttribution.bucketMetrics.share', { value: row.share })}</span>
                    <span className="product-chip">{resultPage('drawdownAttribution.bucketMetrics.avgDepth', { value: row.avgDepth })}</span>
                    <span className="product-chip">{resultPage('drawdownAttribution.bucketMetrics.worstDepth', { value: row.worstDepth })}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
        <DeterministicAuditTable run={run} rows={normalized.rows} />
      </section>
    );
  }

  if (activeTab === 'trades') {
    return (
      <section
        className="backtest-display-section"
        id="deterministic-result-tab-panel-trades"
        data-testid="deterministic-result-tab-panel-trades"
        role="tabpanel"
        aria-labelledby="deterministic-result-tab-trades"
      >
        <DeterministicTradeEventTable events={normalized.tradeEvents} />
      </section>
    );
  }

  if (activeTab === 'parameters') {
    const selectedScenarioPlan = scenarioPlans.find((plan) => plan.id === selectedScenarioPlanId) || null;
    return (
      <section
        className="backtest-display-section"
        id="deterministic-result-tab-panel-parameters"
        data-testid="deterministic-result-tab-panel-parameters"
        role="tabpanel"
        aria-labelledby="deterministic-result-tab-parameters"
      >
        <Card title={resultPage('parameters.title')} subtitle={resultPage('parameters.subtitle')} className="product-section-card product-section-card--backtest-secondary">
          <div className="backtest-parameter-matrix" data-testid="backtest-parameter-matrix">
            {denseParameterItems.map((item) => (
              <div key={item.label} className="backtest-parameter-matrix__cell">
                <span className="backtest-parameter-matrix__label">{item.label}</span>
                <span className="backtest-parameter-matrix__value">{item.value}</span>
              </div>
            ))}
          </div>
          <div className="backtest-result-page__tab-stack">
            <Disclosure summary={resultPage('parameters.snapshotDisclosure')}>
              <div className="preview-grid">
                <div className="preview-card">
                  <p className="metric-card__label">{resultPage('parameters.instrument')}</p>
                  <p className="preview-card__text">{run.code}</p>
                </div>
                <div className="preview-card">
                  <p className="metric-card__label">{resultPage('parameters.backtestWindow')}</p>
                  <p className="preview-card__text">{run.startDate || '--'} {'->'} {run.endDate || '--'}</p>
                </div>
                <div className="preview-card">
                  <p className="metric-card__label">{resultPage('parameters.submittedAt')}</p>
                  <p className="preview-card__text">{formatDateTime(run.runAt)}</p>
                </div>
                <div className="preview-card">
                  <p className="metric-card__label">{resultPage('parameters.completedAt')}</p>
                  <p className="preview-card__text">{formatDateTime(run.completedAt)}</p>
                </div>
              </div>
            </Disclosure>

            <Disclosure summary={resultPage('parameters.benchmarkDisclosure')}>
              <div className="preview-grid">
                <div className="preview-card">
                  <p className="metric-card__label">{resultPage('overview.selectedBenchmark')}</p>
                  <p className="preview-card__text">{selectedBenchmarkLabel}</p>
                </div>
                <div className="preview-card">
                  <p className="metric-card__label">{resultPage('parameters.benchmarkReturn')}</p>
                  <p className="preview-card__text">{pct(run.benchmarkReturnPct)}</p>
                </div>
                <div className="preview-card">
                  <p className="metric-card__label">{resultPage('overview.buyAndHold')}</p>
                  <p className="preview-card__text">{buyAndHoldLabel} · {pct(run.buyAndHoldReturnPct)}</p>
                </div>
                <div className="preview-card">
                  <p className="metric-card__label">{resultPage('overview.vsBenchmark')}</p>
                  <p className="preview-card__text">{pct(run.excessReturnVsBenchmarkPct)}</p>
                </div>
              </div>
              <p className="product-footnote mt-4">{benchmarkStatusNote}</p>
            </Disclosure>

            <Disclosure summary={resultPage('parameters.executionAssumptionsDisclosure')}>
              <AssumptionList assumptions={run.executionAssumptions} emptyText={resultPage('overview.emptyExecutionAssumptions')} />
            </Disclosure>

            {hasRobustnessAnalysis ? (
              <Disclosure summary={backtestCopy('resultPage.riskControls.robustnessDisclosure')}>
                <div className="backtest-result-page__tab-stack">
                  <SummaryStrip
                    items={[
                      { label: backtestCopy('resultPage.riskControls.status'), value: robustnessAnalysisStateLabel },
                      { label: backtestCopy('resultPage.riskControls.walkForwardWindow'), value: walkForwardWindowCount },
                      { label: backtestCopy('resultPage.riskControls.monteCarloSimulation'), value: monteCarloSimulationCount },
                      { label: backtestCopy('resultPage.riskControls.stressScenario'), value: stressScenarioCount },
                    ]}
                  />
                  <div className="preview-grid">
                    <div className="preview-card">
                      <p className="metric-card__label">{backtestCopy('resultPage.riskControls.walkForwardMeanReturn')}</p>
                      <p className="preview-card__text">{walkForwardMeanReturn}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">{backtestCopy('resultPage.riskControls.monteCarloMedianReturn')}</p>
                      <p className="preview-card__text">{monteCarloMedianReturn}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">{backtestCopy('resultPage.riskControls.worstScenario')}</p>
                      <p className="preview-card__text">{worstScenarioLabel}</p>
                    </div>
                  </div>
                  <div className="summary-block">
                    <div className="summary-block__header">
                      <div>
                        <h3 className="summary-block__title">{backtestCopy('resultPage.riskControls.monteCarloDetailsTitle')}</h3>
                      </div>
                    </div>
                    {monteCarloDetailRows.length ? (
                      <dl className="audit-grid">
                        {monteCarloDetailRows.map((row) => (
                          <div key={`${row.label}-${row.value}`} className="audit-grid__row">
                            <dt className="audit-grid__label">{row.label}</dt>
                            <dd className="audit-grid__value">{row.value}</dd>
                          </div>
                        ))}
                      </dl>
                    ) : (
                      <p className="product-empty-note">{monteCarloDetailEmptyText}</p>
                    )}
                  </div>
                  <div className="summary-block">
                    <div className="summary-block__header">
                      <div>
                        <h3 className="summary-block__title">{backtestCopy('resultPage.riskControls.stressScenarioDetailsTitle')}</h3>
                      </div>
                    </div>
                    {stressScenarioRows.length ? (
                      <div className="preview-grid">
                        {stressScenarioRows.map((row) => (
                          <div key={row.key} className="preview-card">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="metric-card__label">{backtestCopy('resultPage.riskControls.stressScenarioCardLabel')}</p>
                                <p className="preview-card__text">{row.label}</p>
                              </div>
                              {row.isWorst ? <span className="product-chip">{backtestCopy('resultPage.riskControls.worstScenario')}</span> : null}
                            </div>
                            <div className="product-chip-list product-chip-list--tight mt-3">
                              {row.totalReturn ? <span className="product-chip">{backtestCopy('resultPage.riskControls.stressScenarioReturnLabel', { value: row.totalReturn })}</span> : null}
                              {row.sharpe ? <span className="product-chip">{backtestCopy('resultPage.riskControls.stressScenarioSharpeLabel', { value: row.sharpe })}</span> : null}
                              {row.maxDrawdown ? <span className="product-chip">{backtestCopy('resultPage.riskControls.stressScenarioDrawdownLabel', { value: row.maxDrawdown })}</span> : null}
                              {row.stateLabel ? <span className="product-chip">{row.stateLabel}</span> : null}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="product-empty-note">{stressScenarioDetailEmptyText}</p>
                    )}
                  </div>
                  <div className="summary-block mt-4" data-testid="robustness-lens">
                    <div className="summary-block__header">
                      <div>
                        <h3 className="summary-block__title">{backtestCopy('resultPage.riskControls.robustnessLens')}</h3>
                      </div>
                    </div>
                    <div className="space-y-3">
                      {robustnessLensRows.map((row) => {
                        const width = row.ratio > 0 ? Math.max(14, row.ratio * 100) : 0;
                        return (
                          <div
                            key={row.key}
                            className={`space-y-1.5 rounded-[0.85rem] px-2 py-1.5 transition-colors ${
                              activeRobustnessKey === row.key ? 'bg-[rgba(125,211,252,0.1)]' : ''
                            }`}
                            data-linked-highlight={activeRobustnessKey === row.key ? 'true' : undefined}
                            data-testid={`robustness-lens-row-${row.key}`}
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div>
                                <p className="metric-card__label">{row.label}</p>
                                <p className="preview-card__text">{row.summary} · {row.detail}</p>
                              </div>
                              <span className="product-chip">{row.state}</span>
                            </div>
                            <div className="h-1.5 overflow-hidden rounded-full bg-[rgba(255,255,255,0.08)]">
                              <div
                                className="h-full rounded-full bg-[var(--backtest-accent,#7dd3fc)]"
                                style={{ width: `${width}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <RobustnessCoverageTrack rows={robustnessLensRows} />
                </div>
              </Disclosure>
            ) : null}

            <Disclosure summary={resultPage('parameters.executedSetupDisclosure')}>
              <div className="backtest-result-page__tab-stack">
                <div className="summary-block">
                  <div className="summary-block__header">
                    <div>
                      <h3 className="summary-block__title">{resultPage('parameters.executedSetupTitle')}</h3>
                    </div>
                  </div>
                  <p className="product-section-copy">{resultPage('parameters.executedSetupBody')}</p>
                  <div className="product-chip-list mt-4">
                    <span className="product-chip">{resultPage('parameters.chipStrategyFamily')} · {getRuleStrategyTypeLabel(run.parsedStrategy, undefined, language)}</span>
                    <span className="product-chip">{resultPage('parameters.chipSpecSource')} · {getRuleStrategySpecSourceLabel(run.parsedStrategy, language)}</span>
                    <span className="product-chip">{resultPage('parameters.chipNormalization')} · {formatRuleNormalizationStateLabel(run.parsedStrategy.normalizationState, language)}</span>
                    <span className="product-chip">{resultPage('parameters.chipNeedsConfirmation')} · {run.needsConfirmation ? backtestCopy('common.yes') : backtestCopy('common.no')}</span>
                    <span className="product-chip">{resultPage('parameters.chipExecutable')} · {run.parsedStrategy.executable ? backtestCopy('common.yes') : backtestCopy('common.no')}</span>
                  </div>
                </div>
                <div className="preview-grid">
                  {strategySummaryRows.map((row) => (
                    <div key={`${row.label}-${row.value}`} className="preview-card">
                      <p className="metric-card__label">{row.label}</p>
                      <p className="preview-card__text">{row.value}</p>
                    </div>
                  ))}
                </div>
                <RiskControlsLadder rows={riskControlRows} activeRiskControlKey={activeRiskControlKey} />
              </div>
            </Disclosure>

            <Disclosure summary={resultPage('parameters.originalInputDisclosure')}>
              <div className="backtest-result-page__tab-stack">
                <div className="summary-block">
                  <div className="summary-block__header">
                    <div>
                      <h3 className="summary-block__title">{resultPage('parameters.originalInputTitle')}</h3>
                    </div>
                  </div>
                  <p className="product-section-copy">{run.strategyText || '--'}</p>
                  {run.aiSummary ? <p className="product-footnote mt-3">{run.aiSummary}</p> : null}
                </div>
                <div className="preview-grid">
                  <div className="preview-card">
                    <p className="metric-card__label">{resultPage('parameters.timeframe')}</p>
                    <p className="preview-card__text">{run.timeframe || '--'}</p>
                  </div>
                  <div className="preview-card">
                    <p className="metric-card__label">{resultPage('parameters.chipSpecSource')}</p>
                    <p className="preview-card__text">{getRuleStrategySpecSourceLabel(run.parsedStrategy, language)}</p>
                  </div>
                  <div className="preview-card">
                    <p className="metric-card__label">{resultPage('parameters.chipStrategyFamily')}</p>
                    <p className="preview-card__text">{getRuleStrategyTypeLabel(run.parsedStrategy, undefined, language)}</p>
                  </div>
                  <div className="preview-card">
                    <p className="metric-card__label">{resultPage('parameters.normalizationState')}</p>
                    <p className="preview-card__text">{formatRuleNormalizationStateLabel(run.parsedStrategy.normalizationState, language)}</p>
                  </div>
                </div>
                {parsedSummaryEntries.length ? (
                  <dl className="audit-grid">
                    {parsedSummaryEntries.map((entry) => (
                      <div key={entry.label} className="audit-grid__row">
                        <dt className="audit-grid__label">{entry.label}</dt>
                        <dd className="audit-grid__value">{entry.value}</dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className="product-empty-note">{resultPage('parameters.interpretationSummaryEmpty')}</p>
                )}
              </div>
            </Disclosure>

            <Disclosure summary={resultPage('parameters.technicalNotesDisclosure')}>
              <div className="backtest-result-page__tab-stack">
                {strategyWarningEntries.length ? (
                  <div className="summary-block">
                    <div className="summary-block__header">
                      <div>
                        <h3 className="summary-block__title">{resultPage('parameters.defaultFillsTitle')}</h3>
                      </div>
                    </div>
                    <ul className="backtest-result-page__list">
                      {strategyWarningEntries.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {run.noResultMessage ? <p className="product-footnote">{run.noResultMessage}</p> : null}
                {run.parsedStrategy.unsupportedReason ? <p className="product-footnote">{run.parsedStrategy.unsupportedReason}</p> : null}
              </div>
            </Disclosure>

            <Disclosure summary={resultPage('parameters.scenarioComparisonDisclosure')}>
              <div className="backtest-result-page__tab-stack">
                <div className="summary-block">
                  <div className="summary-block__header">
                    <div>
                      <h3 className="summary-block__title">{resultPage('parameters.scenarioComparisonTitle')}</h3>
                      <p className="product-section-copy">{resultPage('parameters.scenarioComparisonBody')}</p>
                    </div>
                    <Button
                      variant="secondary"
                      onClick={() => void onRunScenarioPlan()}
                      isLoading={isSubmittingScenarioRuns}
                      loadingText={resultPage('parameters.submittingScenarios')}
                      disabled={!selectedScenarioPlan}
                    >
                      {resultPage('parameters.runCurrentScenarioSet')}
                    </Button>
                  </div>
                  <div className="comparison-card-grid">
                    {scenarioPlans.map((plan) => (
                      <button
                        key={plan.id}
                        type="button"
                        className={`comparison-card comparison-card--selectable${selectedScenarioPlanId === plan.id ? ' is-active' : ''}`}
                        onClick={() => onSelectScenarioPlanId(plan.id)}
                      >
                        <div className="comparison-card__header">
                          <div>
                            <p className="metric-card__label">{resultPage('parameters.scenarioPlan')}</p>
                            <h3 className="comparison-card__title">{plan.label}</h3>
                          </div>
                          <span className="product-chip">{resultPage('parameters.variants', { count: plan.variants.length })}</span>
                        </div>
                        <p className="comparison-card__narrative">{plan.description}</p>
                        <div className="product-chip-list product-chip-list--tight">
                          {plan.variants.map((variant) => (
                            <span key={`${plan.id}-${variant.id}`} className="product-chip">{variant.label}</span>
                          ))}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
                {scenarioError ? <ApiErrorAlert error={scenarioError} /> : null}
                {scenarioRuns.length > 0 ? (
                  <div className="product-table-shell">
                    <table className="product-table">
                      <thead>
                        <tr>
                          <th>{resultPage('parameters.scenario')}</th>
                          <th>{backtestCopy('common.status')}</th>
                          <th>Run ID</th>
                          <th className="product-table__align-right">{backtestCopy('common.action')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {scenarioRuns.map((item) => (
                          <tr key={item.variantId}>
                            <td>
                              <div className="product-table__stack">
                                <span>{item.label}</span>
                                <span>{item.description}</span>
                              </div>
                            </td>
                            <td>{getRuleRunStatusLabel(item.status, language)}</td>
                            <td className="product-table__mono">{item.runId || '--'}</td>
                            <td className="product-table__align-right">
                              {item.runId ? (
                                <Button size="sm" variant="ghost" onClick={() => onOpenScenarioRun(item.runId as number)}>
                                  {backtestCopy('common.open')}
                                </Button>
                              ) : (
                                '--'
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
                <RuleRunComparisonPanel
                  title={resultPage('parameters.scenarioResultComparisonTitle')}
                  subtitle={resultPage('parameters.scenarioResultComparisonSubtitle')}
                  items={scenarioComparisonItems}
                  emptyText={resultPage('parameters.scenarioResultComparisonEmpty')}
                />
              </div>
            </Disclosure>

            <Disclosure summary={resultPage('parameters.reusableSetupDisclosure')}>
              <div className="backtest-result-page__tab-stack">
                <div className="summary-block__header">
                  <div>
                    <h3 className="summary-block__title">{resultPage('parameters.reusableSetupTitle')}</h3>
                    <p className="product-section-copy">{resultPage('parameters.reusableSetupBody')}</p>
                  </div>
                  <Button variant="secondary" onClick={onSavePreset}>{resultPage('parameters.saveAsPreset')}</Button>
                </div>
                <div className="product-chip-list">
                  {availablePresets.map((preset) => (
                    <span key={preset.id} className="product-chip">
                      {preset.kind === 'saved' ? resultPage('parameters.presetKindSaved') : resultPage('parameters.presetKindRecent')} · {preset.name}
                    </span>
                  ))}
                </div>
              </div>
            </Disclosure>
          </div>
        </Card>
      </section>
    );
  }

  return (
    <section
      className="backtest-display-section"
      id="deterministic-result-tab-panel-history"
      data-testid="deterministic-result-tab-panel-history"
      role="tabpanel"
      aria-labelledby="deterministic-result-tab-history"
    >
      <Card title={resultPage('history.title')} subtitle={resultPage('history.subtitle')} className="product-section-card product-section-card--backtest-secondary">
        <div className="summary-block__header">
          <div>
            <h3 className="summary-block__title">{resultPage('history.runsTitle')}</h3>
            <p className="product-section-copy">{resultPage('history.runsBody')}</p>
          </div>
          <Button variant="ghost" onClick={onRefreshHistory} disabled={isLoadingHistory}>
            {isLoadingHistory ? resultPage('history.refreshing') : resultPage('history.refresh')}
          </Button>
        </div>
        {historyError ? <ApiErrorAlert error={historyError} className="mb-4" /> : null}
        {compareError ? <ApiErrorAlert error={compareError} className="mb-4" /> : null}
        {isLoadingCompareRuns ? <p className="product-footnote">{resultPage('history.loadingComparedRuns')}</p> : null}
        <RuleRunComparisonPanel
          title={resultPage('history.runComparisonTitle')}
          subtitle={resultPage('history.runComparisonSubtitle')}
          items={comparisonItems}
          emptyText={resultPage('history.runComparisonEmpty')}
        />
        <div className="product-action-row mt-4">
          <Button variant="secondary" onClick={onOpenCompareWorkbench} disabled={compareRunIds.length === 0}>
            {resultPage('history.openCompareWorkbench')}
          </Button>
          <Button variant="ghost" onClick={onClearComparison} disabled={compareRunIds.length === 0}>{resultPage('history.clearComparison')}</Button>
        </div>
        <RuleRunsTable
          rows={historyItems}
          selectedRunId={run.id}
          onOpen={onOpenHistoryRun}
          compareSelection={{
            selectedIds: compareRunIds,
            onToggle: onToggleCompareRun,
            maxSelections: 3,
          }}
        />
      </Card>
    </section>
  );
};

export default BacktestAuditTables;
