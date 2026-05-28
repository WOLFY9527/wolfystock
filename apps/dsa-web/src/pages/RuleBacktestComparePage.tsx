import type React from 'react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { backtestApi } from '../api/backtest';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Button } from '../components/common/ApiErrorAlert';
import {
  TerminalChip,
  TerminalEmptyState,
  TerminalNestedBlock,
  TerminalPageShell,
  TerminalSectionHeader,
} from '../components/terminal';
import {
  ConsoleBoard,
  ConsoleContextRail,
  ConsoleDisclosure,
  ConsoleStatusStrip,
  KeyLevelStrip,
  ResearchConsoleShell,
  WolfyCommandBar,
} from '../components/linear';
import RuleBacktestCompareHeatmapProjectionPanel from '../components/backtest/RuleBacktestCompareHeatmapProjectionPanel';
import {
  Banner,
  SummaryStrip,
  formatDateTime,
  formatNumber,
  pct,
} from '../components/backtest/shared';
import type {
  RuleBacktestCompareHighlightItem,
  RuleBacktestCompareMetricDelta,
  RuleBacktestCompareParameterComparison,
  RuleBacktestCompareParameterDetail,
  RuleBacktestCompareResponse,
  RuleBacktestCompareRobustnessDimension,
  RuleBacktestCompareRunItem,
} from '../types/backtest';

const COMPARE_METRIC_LABELS: Record<string, string> = {
  totalReturnPct: '总收益',
  annualizedReturnPct: '年化收益',
  maxDrawdownPct: '最大回撤',
  benchmarkReturnPct: '基准收益',
  excessReturnVsBenchmarkPct: '相对基准',
};

const COMPARE_SECTION_LINKS = [
  { id: 'compare-summary', label: '比较摘要' },
  { id: 'compare-chart-strip', label: '指标条带' },
  { id: 'compare-highlights', label: '比较亮点' },
  { id: 'compare-metric-matrix', label: '指标矩阵' },
  { id: 'compare-parameter-sensitivity', label: '参数敏感度' },
  { id: 'compare-robustness', label: '稳健性画像' },
  { id: 'compare-market-period', label: '市场与区间' },
  { id: 'compare-parameter-metrics', label: '参数与指标' },
  { id: 'compare-items', label: '参与运行' },
] as const;

const COMPARE_CHART_STRIP_KEYS = [
  'totalReturnPct',
  'annualizedReturnPct',
  'excessReturnVsBenchmarkPct',
] as const;

function parseRunIdsParam(value: string | null): number[] {
  if (!value) return [];
  const orderedIds: number[] = [];
  value.split(',').forEach((part) => {
    const parsed = Number.parseInt(part.trim(), 10);
    if (!Number.isFinite(parsed) || parsed <= 0 || orderedIds.includes(parsed)) return;
    orderedIds.push(parsed);
  });
  return orderedIds;
}

function renderBooleanLabel(value: boolean | undefined): string {
  return value ? '是' : '否';
}

function formatCompareStateLabel(value?: string | null): string {
  const key = String(value || '').trim();
  if (!key) return '--';
  const normalized = key.toLowerCase();
  const labels: Record<string, string> = {
    aligned: '一致',
    divergent: '差异',
    available: '可用',
    unavailable: '不可用',
    missing: '缺失',
    ambiguous: '歧义',
    partial: '部分',
    limited: '有限',
    comparable: '可比',
    direct: '直接可比',
    winner: '领先',
    baseline: '基准',
    candidate: '候选',
    partially_comparable: '部分可比',
    same_family_comparable: '同类可比',
    limited_context_winner: '有限上下文领先',
    metric_unavailable: '指标不可用',
    partial_metric_deltas: '部分指标差异',
    partially_comparable_context: '部分可比上下文',
    same_code: '同一标的',
    overlapping: '区间重叠',
    same_code_different_periods: '同标的不同区间',
    same_parameter: '参数一致',
    different_parameter: '参数不同',
    missing_parameter: '参数缺失',
    stored_rule_backtest_runs: '已保存结果',
    stored_first: '优先使用已完成结果',
    stored_projection_only: '基于已完成结果',
    stored_compare_projection: '已完成比较结果',
    first_comparable_run_by_request_order: '按请求顺序首个可比运行',
    market_code_comparison: '市场与代码',
    period_comparison: '区间',
    comparison_summary: '比较摘要',
    market_code: '市场 / 代码',
    periods: '区间',
    moving_average_crossover: '均线交叉',
    macd_crossover: 'MACD 交叉',
    rsi_threshold: 'RSI 阈值',
    same_normalized_code: '代码一致',
    overlapping_periods: '区间重叠',
  };
  if (labels[normalized]) return labels[normalized];
  if (/[_.]|provider|authority|trace|payload|contract|diagnostic|stored|execution|source/i.test(key)) {
    return '比较边界需复核';
  }
  return key.replaceAll('_', ' ');
}

function formatCompareRoleLabel(isBaseline: boolean): string {
  return isBaseline ? '基准' : '候选';
}

function formatCompareStateWithRaw(value?: string | null): string {
  const raw = String(value || '').trim();
  const label = formatCompareStateLabel(raw);
  return raw && label !== raw.replaceAll('_', ' ') ? label : label;
}

function formatCompareList(values?: Array<string | null | undefined>): string {
  if (!values?.length) return '--';
  const labels = values.map((value) => formatCompareStateWithRaw(value));
  const uniqueLabels = labels.filter((label, index) => labels.indexOf(label) === index);
  return uniqueLabels.join(', ');
}

function formatCompareSourceLabel(value?: string | null): string {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return '--';
  if (normalized.includes('stored')) return '已保存结果';
  if (normalized.includes('request')) return '当前请求';
  return formatCompareStateWithRaw(value);
}

function formatRunCountLabel(runIds: number[]): string {
  return runIds.length ? `${runIds.length} 条运行` : '--';
}

function formatUnavailableRunReason(reason?: string | null): string {
  const normalized = String(reason || '').trim().toLowerCase();
  if (!normalized) return '该运行暂不可用于比较。';
  if (normalized.includes('missing') || normalized.includes('not_found')) return '部分运行结果暂不可用。';
  if (normalized.includes('status') || normalized.includes('completed')) return '部分运行尚未生成可比较结果。';
  if (normalized.includes('metric') || normalized.includes('data')) return '部分运行数据质量有限，比较结果仅供评估。';
  return '部分运行暂不可用于比较。';
}

function collectCompareDiagnostics(...groups: Array<Array<string | null | undefined> | null | undefined>): string[] {
  const seen = new Set<string>();
  const values: string[] = [];
  groups.forEach((group) => {
    group?.forEach((value) => {
      const key = String(value || '').trim();
      if (!key || seen.has(key)) return;
      seen.add(key);
      values.push(key);
    });
  });
  return values;
}

function slugifyCompareKey(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function normalizeCompareKey(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '');
}

function formatSensitivityLabel(key: string): string {
  const labels: Record<string, string> = {
    'strategy_spec.signal.fast_period': '快线周期',
    'strategy_spec.signal.fast_type': '快线类型',
    'strategy_spec.signal.slow_period': '慢线周期',
    'strategy_spec.signal.slow_type': '慢线类型',
    'strategy_spec.signal.signal_period': '信号周期',
    'strategy_spec.signal.lower_threshold': '下阈值',
    'strategy_spec.signal.upper_threshold': '上阈值',
    'strategy_spec.execution.signal_timing': '信号时点',
    lookback_bars: '回看窗口',
    lookbackBars: '回看窗口',
    fee_bps: '手续费',
    feeBps: '手续费',
    slippage_bps: '滑点',
    slippageBps: '滑点',
    benchmark_mode: '基准模式',
    benchmarkMode: '基准模式',
    benchmark_code: '基准代码',
    benchmarkCode: '基准代码',
    period_window: '回测区间',
  };
  if (labels[key]) return labels[key];

  const fallback = key.split('.').at(-1) || key;
  return fallback.replaceAll('_', ' ').replaceAll(/([a-z0-9])([A-Z])/g, '$1 $2');
}

function formatSensitivityValue(value: unknown): string {
  if (value == null) return '缺失';
  if (typeof value === 'boolean') return renderBooleanLabel(value);
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return '--';
    return Number.isInteger(value) ? String(value) : formatNumber(value);
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed || '--';
  }
  if (Array.isArray(value)) {
    const parts = value.flatMap((entry) => { const v = formatSensitivityValue(entry); return v ? [v] : []; });
    return parts.length ? parts.join(' / ') : '--';
  }
  return '复杂值';
}

type CompareSensitivityMetricSignal = {
  metricKey: string;
  label: string;
  state?: string;
  winners: string[];
};

type CompareSensitivityRunValue = {
  runId: number;
  label: string;
  isBaseline: boolean;
};

type CompareSensitivityRow = {
  key: string;
  label: string;
  sourceLabel: string;
  state?: string;
  values: CompareSensitivityRunValue[];
  signals: CompareSensitivityMetricSignal[];
};

type CompareCostSlippageScenario = {
  runId: number;
  label: string;
  isBaseline: boolean;
  feeLabel: string;
  slippageLabel: string;
};

type CompareCostSlippageMetricSignal = {
  metricKey: string;
  label: string;
  state?: string;
  entries: string[];
};

type CompareCostSlippagePanelData = {
  scenarios: CompareCostSlippageScenario[];
  state?: string;
  sourceLabels: string[];
  signals: CompareCostSlippageMetricSignal[];
};

function formatBpsValue(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '缺失';
  return `${formatNumber(value, 1)}bp`;
}

function formatCostSlippageScenarioLabel({
  feeLabel,
  slippageLabel,
}: {
  feeLabel: string;
  slippageLabel: string;
}): string {
  return `手续费 ${feeLabel} · 滑点 ${slippageLabel}`;
}

function isFeeCompareKey(key: string): boolean {
  const normalized = normalizeCompareKey(key);
  return normalized === 'feebps' || normalized === 'feebpsperside';
}

function isSlippageCompareKey(key: string): boolean {
  const normalized = normalizeCompareKey(key);
  return normalized === 'slippagebps' || normalized === 'slippagebpsperside';
}

function getTerminalChipVariantFromState(state?: string): 'neutral' | 'success' | 'caution' | 'danger' | 'info' {
  const normalized = String(state || '').toLowerCase();
  if (normalized.includes('winner') || normalized.includes('aligned') || normalized.includes('direct')) return 'success';
  if (normalized.includes('missing') || normalized.includes('unavailable')) return 'danger';
  if (normalized.includes('limited') || normalized.includes('partial')) return 'caution';
  if (normalized.includes('different') || normalized.includes('divergent') || normalized.includes('comparable')) return 'info';
  return 'neutral';
}

function buildSensitivitySignals({
  metricEntries,
  valuesByRun,
}: {
  metricEntries: Array<[string, RuleBacktestCompareHighlightItem]>;
  valuesByRun: Map<number, string>;
}): CompareSensitivityMetricSignal[] {
  return metricEntries.map(([metricKey, highlight]) => ({
    metricKey,
    label: formatMetricLabel(metricKey, highlight.metric),
    state: highlight.state,
    winners: highlight.winnerRunIds.map((runId) => `#${runId} · ${valuesByRun.get(runId) || '--'}`),
  }));
}

function buildSensitivityRowsFromDetail({
  keys,
  details,
  sourceLabel,
  items,
  baselineRunId,
  metricEntries,
}: {
  keys: string[];
  details: Record<string, RuleBacktestCompareParameterDetail>;
  sourceLabel: string;
  items: RuleBacktestCompareRunItem[];
  baselineRunId?: number | null;
  metricEntries: Array<[string, RuleBacktestCompareHighlightItem]>;
}): CompareSensitivityRow[] {
  return keys.reduce<CompareSensitivityRow[]>((rows, key) => {
    const detail = details[key];
    if (!detail?.values?.length) return rows;

    const valuesByRun = new Map(detail.values.map((entry) => [entry.runId, formatSensitivityValue(entry.value)]));
    const values = items.map((item) => ({
      runId: item.metadata.id,
      label: valuesByRun.get(item.metadata.id) || '缺失',
      isBaseline: item.metadata.id === baselineRunId,
    }));
    const distinctValues = new Set(values.map((entry) => entry.label));
    if (distinctValues.size <= 1) return rows;

    rows.push({
      key,
      label: formatSensitivityLabel(key),
      sourceLabel,
      state: detail.state,
      values,
      signals: buildSensitivitySignals({ metricEntries, valuesByRun }),
    });
    return rows;
  }, []);
}

function buildScenarioMetadataSensitivityRows({
  items,
  baselineRunId,
  metricEntries,
  excludedKeys,
}: {
  items: RuleBacktestCompareRunItem[];
  baselineRunId?: number | null;
  metricEntries: Array<[string, RuleBacktestCompareHighlightItem]>;
  excludedKeys: Set<string>;
}): CompareSensitivityRow[] {
  const candidates = [
    {
      key: 'lookback_bars',
      label: formatSensitivityLabel('lookback_bars'),
      getValue: (item: RuleBacktestCompareRunItem) => item.metadata.lookbackBars,
    },
    {
      key: 'fee_bps',
      label: formatSensitivityLabel('fee_bps'),
      getValue: (item: RuleBacktestCompareRunItem) => item.metadata.feeBps == null ? null : `${formatNumber(item.metadata.feeBps, 1)}bp`,
    },
    {
      key: 'slippage_bps',
      label: formatSensitivityLabel('slippage_bps'),
      getValue: (item: RuleBacktestCompareRunItem) => item.metadata.slippageBps == null ? null : `${formatNumber(item.metadata.slippageBps, 1)}bp`,
    },
    {
      key: 'period_window',
      label: formatSensitivityLabel('period_window'),
      getValue: (item: RuleBacktestCompareRunItem) => {
        const start = item.metadata.startDate || item.metadata.periodStart;
        const end = item.metadata.endDate || item.metadata.periodEnd;
        return start || end ? `${start || '--'} -> ${end || '--'}` : null;
      },
    },
  ];

  return candidates.reduce<CompareSensitivityRow[]>((rows, candidate) => {
    if (excludedKeys.has(normalizeCompareKey(candidate.key))) return rows;

    const values = items.map((item) => ({
      runId: item.metadata.id,
      label: formatSensitivityValue(candidate.getValue(item)),
      isBaseline: item.metadata.id === baselineRunId,
    }));
    const distinctValues = new Set(values.map((entry) => entry.label));
    if (distinctValues.size <= 1) return rows;

    const valuesByRun = new Map(values.map((entry) => [entry.runId, entry.label]));
    rows.push({
      key: candidate.key,
      label: candidate.label,
      sourceLabel: '场景设置',
      state: 'different_parameter',
      values,
      signals: buildSensitivitySignals({ metricEntries, valuesByRun }),
    });
    return rows;
  }, []);
}

function buildCompareSensitivityRows({
  items,
  baselineRunId,
  parameterComparison,
  highlights,
}: {
  items: RuleBacktestCompareRunItem[];
  baselineRunId?: number | null;
  parameterComparison?: RuleBacktestCompareParameterComparison | null;
  highlights: Record<string, RuleBacktestCompareHighlightItem>;
}): CompareSensitivityRow[] {
  if (!items.length) return [];

  const metricEntries = Object.entries(highlights || {})
    .filter(([, highlight]) => highlight.winnerRunIds.length > 0 || highlight.availableRunIds.length > 1)
    .slice(0, 4);

  if (!metricEntries.length) return [];

  const parameterRows = [
    ...buildSensitivityRowsFromDetail({
      keys: parameterComparison?.differingParameterKeys || [],
      details: parameterComparison?.differingParameters || {},
      sourceLabel: '参数差异',
      items,
      baselineRunId,
      metricEntries,
    }),
    ...buildSensitivityRowsFromDetail({
      keys: parameterComparison?.missingParameterKeys || [],
      details: parameterComparison?.missingParameters || {},
      sourceLabel: '参数缺失',
      items,
      baselineRunId,
      metricEntries,
    }),
  ];

  const excludedKeys = new Set(parameterRows.map((row) => normalizeCompareKey(row.key)));
  const scenarioRows = buildScenarioMetadataSensitivityRows({
    items,
    baselineRunId,
    metricEntries,
    excludedKeys,
  });

  return [...parameterRows, ...scenarioRows];
}

function buildCompareCostSlippagePanelData({
  items,
  baselineRunId,
  parameterComparison,
  highlights,
  metricDeltas,
}: {
  items: RuleBacktestCompareRunItem[];
  baselineRunId?: number | null;
  parameterComparison?: RuleBacktestCompareParameterComparison | null;
  highlights: Record<string, RuleBacktestCompareHighlightItem>;
  metricDeltas: Record<string, RuleBacktestCompareMetricDelta>;
}): CompareCostSlippagePanelData | null {
  if (!items.length) return null;

  const scenarios = items.map((item) => {
    const feeLabel = formatBpsValue(item.metadata.feeBps);
    const slippageLabel = formatBpsValue(item.metadata.slippageBps);
    return {
      runId: item.metadata.id,
      label: formatCostSlippageScenarioLabel({ feeLabel, slippageLabel }),
      isBaseline: item.metadata.id === baselineRunId,
      feeLabel,
      slippageLabel,
    };
  });

  const distinctScenarioCount = new Set(scenarios.map((scenario) => `${scenario.feeLabel}|${scenario.slippageLabel}`)).size;
  const sourceLabels: string[] = [];

  if (distinctScenarioCount > 1) sourceLabels.push('场景设置');

  const differingKeys = parameterComparison?.differingParameterKeys || [];
  const missingKeys = parameterComparison?.missingParameterKeys || [];
  const hasDifferingCostKeys = differingKeys.some((key) => isFeeCompareKey(key) || isSlippageCompareKey(key));
  const hasMissingCostKeys = missingKeys.some((key) => isFeeCompareKey(key) || isSlippageCompareKey(key));

  if (hasDifferingCostKeys) sourceLabels.push('参数差异');
  if (hasMissingCostKeys) sourceLabels.push('参数缺失');

  if (!sourceLabels.length) {
    return null;
  }

  const scenarioLabelsByRun = new Map(scenarios.map((scenario) => [scenario.runId, scenario.label]));
  const signals = Object.entries(metricDeltas || {})
    .filter(([, metric]) => metric.deltas.some((entry) => entry.runId !== baselineRunId && entry.deltaVsBaseline != null))
    .slice(0, 3)
    .map(([metricKey, metric]) => {
      const highlight = highlights[metricKey];
      const entries = metric.deltas
        .filter((entry) => entry.runId !== baselineRunId && entry.deltaVsBaseline != null)
        .map((entry) => {
          const scenarioLabel = scenarioLabelsByRun.get(entry.runId) || `#${entry.runId}`;
          const role = highlight?.winnerRunIds.includes(entry.runId) ? '领先' : '相对基准';
          return `${scenarioLabel} · ${role} ${formatSignedPct(entry.deltaVsBaseline)}`;
        });

      return {
        metricKey,
        label: formatMetricLabel(metricKey, metric.label),
        state: highlight?.state || metric.state,
        entries,
      };
    })
    .filter((signal) => signal.entries.length > 0);

  return {
    scenarios,
    state: distinctScenarioCount > 1 ? 'different_parameter' : parameterComparison?.state,
    sourceLabels,
    signals,
  };
}

function DiagnosticChipList({ diagnostics }: { diagnostics?: string[] }) {
  if (!diagnostics?.length) {
    return <p className="product-footnote">无额外限制。</p>;
  }
  const labels = diagnostics
    .map((diagnostic) => formatCompareStateLabel(diagnostic))
    .filter((label, index, allLabels) => allLabels.indexOf(label) === index);

  return (
    <div className="product-chip-list">
      {labels.map((label) => (
        <span key={label} className="product-chip">{label}</span>
      ))}
    </div>
  );
}

function HighlightCards({ highlights }: { highlights: Record<string, RuleBacktestCompareHighlightItem> }) {
  const entries = Object.entries(highlights || {});
  if (entries.length === 0) {
    return <div className="product-empty-state product-empty-state--compact">当前比较没有可展示的亮点。</div>;
  }

  return (
    <div className="preview-grid">
      {entries.map(([metricKey, item]) => (
        <div key={metricKey} className="preview-card">
          <p className="metric-card__label">{formatMetricLabel(metricKey, item.metric)}</p>
          <p className="preview-card__text">{formatCompareStateWithRaw(item.state)}</p>
          <p className="product-footnote">领先运行：{item.winnerRunIds.length ? item.winnerRunIds.join(', ') : '--'}</p>
          <p className="product-footnote">领先值：{item.winnerValue == null ? '--' : formatNumber(item.winnerValue)}</p>
          <p className="product-footnote">候选数：{item.candidateCount}</p>
          <p className="product-footnote">结果置信度：{item.diagnostics?.length ? '有限置信' : '正常评估'}</p>
        </div>
      ))}
    </div>
  );
}

function RobustnessDimensionCards({ dimensions }: { dimensions: Record<string, RuleBacktestCompareRobustnessDimension> }) {
  const entries = Object.entries(dimensions || {});
  if (entries.length === 0) return null;

  return (
    <div className="preview-grid">
      {entries.map(([dimensionKey, dimension]) => (
        <div key={dimensionKey} className="preview-card">
          <p className="metric-card__label">{formatCompareStateLabel(dimensionKey)}</p>
          <p className="preview-card__text">{formatCompareStateWithRaw(dimension.state)}</p>
          <p className="product-footnote">关系：{formatCompareStateWithRaw(dimension.relationship)}</p>
          <p className="product-footnote">可直接比较：{dimension.directlyComparable == null ? '--' : renderBooleanLabel(dimension.directlyComparable)}</p>
        </div>
      ))}
    </div>
  );
}

function MetricDeltaTable({ metricDeltas }: { metricDeltas: Record<string, RuleBacktestCompareMetricDelta> }) {
  const entries = Object.entries(metricDeltas || {});
  if (entries.length === 0) {
    return <div className="product-empty-state product-empty-state--compact">当前比较没有可展示的指标差异。</div>;
  }

  return (
    <div className="product-table-shell">
      <table className="product-table">
        <thead>
          <tr>
            <th>指标</th>
            <th>状态</th>
            <th className="product-table__align-right">基准</th>
            <th>可用运行</th>
            <th>差异</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([metricKey, metric]) => (
            <tr key={metricKey}>
              <td>{formatMetricLabel(metricKey, metric.label)}</td>
              <td>{formatCompareStateWithRaw(metric.state)}</td>
              <td className="product-table__align-right">{pct(metric.baselineValue)}</td>
              <td>{metric.availableRunIds.join(', ') || '--'}</td>
              <td>
                <div className="product-table__stack">
                  {metric.deltas.map((item) => (
                    <span key={`${metricKey}-${item.runId}`}>
                      #{item.runId}: {pct(item.value)} ({pct(item.deltaVsBaseline)})
                    </span>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatMetricLabel(metricKey: string, fallback?: string): string {
  return COMPARE_METRIC_LABELS[metricKey]
    || (fallback || metricKey)
      .replaceAll('_', ' ')
      .replaceAll(/([a-z0-9])([A-Z])/g, '$1 $2');
}

function formatSignedPct(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function getMetricSummaryTone(state?: string): string {
  const normalized = String(state || '').toLowerCase();
  if (normalized.includes('unavailable')) return 'unavailable';
  if (normalized.includes('limited') || normalized.includes('partial')) return 'limited';
  if (normalized.includes('winner')) return 'best';
  return 'neutral';
}

function getMetricStateTone({
  state,
  highlightApplies,
  isUnavailable,
}: {
  state?: string;
  highlightApplies: boolean;
  isUnavailable: boolean;
}): string {
  if (isUnavailable) return 'unavailable';
  if (highlightApplies) return 'best';
  const normalized = String(state || '').toLowerCase();
  if (normalized.includes('limited') || normalized.includes('partial')) return 'limited';
  return 'neutral';
}

function getMetricDeltaTone(value?: number | null, isBaseline?: boolean): string {
  if (isBaseline) return 'baseline';
  if (value == null || Number.isNaN(value) || value === 0) return 'neutral';
  return value > 0 ? 'positive' : 'negative';
}

function orderCompareItems(items: RuleBacktestCompareRunItem[], runIds: number[]): RuleBacktestCompareRunItem[] {
  const orderMap = new Map(runIds.map((runId, index) => [runId, index]));
  return [...items].sort((left, right) => {
    const leftOrder = orderMap.get(left.metadata.id) ?? Number.MAX_SAFE_INTEGER;
    const rightOrder = orderMap.get(right.metadata.id) ?? Number.MAX_SAFE_INTEGER;
    return leftOrder - rightOrder;
  });
}

function buildCompareShareSummary({
  runIds,
  baselineRunId,
  baselineCode,
  overallState,
  primaryProfile,
  comparableCount,
  requestedCount,
}: {
  runIds: number[];
  baselineRunId?: number | null;
  baselineCode?: string | null;
  overallState?: string;
  primaryProfile?: string;
  comparableCount?: number;
  requestedCount?: number;
}): string {
  return [
    `比较运行 ${runIds.join(',') || '--'}`,
    `基准 #${baselineRunId ?? '--'} ${baselineCode || '--'}`,
    `整体 ${formatCompareStateWithRaw(overallState)}`,
    `画像 ${formatCompareStateWithRaw(primaryProfile)}`,
    `可比 ${comparableCount ?? 0}/${requestedCount ?? 0}`,
  ].join(' | ');
}

function CompareMetricMatrix({
  items,
  baselineRunId,
  metricDeltas,
  highlights,
  overallState,
  primaryProfile,
}: {
  items: RuleBacktestCompareRunItem[];
  baselineRunId?: number | null;
  metricDeltas: Record<string, RuleBacktestCompareMetricDelta>;
  highlights: Record<string, RuleBacktestCompareHighlightItem>;
  overallState?: string;
  primaryProfile?: string;
}) {
  const metricEntries = Object.entries(metricDeltas || {});
  if (!items.length || !metricEntries.length) {
    return <div className="product-empty-state product-empty-state--compact">当前比较没有足够的指标数据来生成紧凑矩阵。</div>;
  }

  return (
    <div className="product-table-shell compare-metric-matrix" data-testid="compare-metric-matrix">
      <table className="product-table comparison-table">
        <thead>
          <tr>
            <th>指标</th>
            <th>摘要</th>
            {items.map((item) => {
              const runId = item.metadata.id;
              const roleLabel = formatCompareRoleLabel(runId === baselineRunId);
              return (
                <th key={runId} scope="col">
                  <div className="product-table__stack">
                    <span>{`#${runId} ${roleLabel}`}</span>
                    <span>{item.metadata.code || '--'}</span>
                  </div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {metricEntries.map(([metricKey, metric]) => {
            const highlight = highlights[metricKey];
            return (
              <tr key={metricKey}>
                <td>
                  <div className="product-table__stack">
                    <span>{formatMetricLabel(metricKey, metric.label)}</span>
                    <span className="compare-metric-badge" data-tone={getMetricSummaryTone(metric.state)}>{formatCompareStateWithRaw(metric.state)}</span>
                  </div>
                </td>
                <td>
                  <div className="product-table__stack">
                    <span
                      className="compare-metric-badge"
                      data-testid={`compare-metric-summary-${metricKey}`}
                      data-tone={getMetricSummaryTone(highlight?.state || metric.state)}
                    >
                      {formatCompareStateWithRaw(highlight?.state || metric.state)}
                    </span>
                    <span className="product-footnote">{`上下文 ${formatCompareStateWithRaw(overallState)} · 画像 ${formatCompareStateWithRaw(primaryProfile)}`}</span>
                  </div>
                </td>
                {items.map((item) => {
                  const runId = item.metadata.id;
                  const deltaItem = metric.deltas.find((entry) => entry.runId === runId);
                  const highlightApplies = Boolean(highlight?.winnerRunIds.includes(runId));
                  const isUnavailable = !deltaItem;
                  const cellTone = highlightApplies ? 'best' : 'default';
                  return (
                    <td key={`${metricKey}-${runId}`} data-tone={cellTone}>
                      {isUnavailable ? (
                        <div className="product-table__stack">
                          <span
                            className="compare-metric-badge"
                            data-testid={`compare-metric-state-${metricKey}-${runId}`}
                            data-tone="unavailable"
                          >
                            不可用
                          </span>
                          <span className="product-footnote">{formatCompareStateWithRaw(highlight?.state || metric.state)}</span>
                        </div>
                      ) : (
                        <div className="product-table__stack">
                          <span>{pct(deltaItem.value)}</span>
                          {runId === baselineRunId ? (
                            <span
                              className="compare-metric-badge"
                              data-testid={`compare-metric-delta-${metricKey}-${runId}`}
                              data-tone={getMetricDeltaTone(deltaItem.deltaVsBaseline, true)}
                            >
                              基准
                            </span>
                          ) : (
                            <span
                              className="compare-metric-badge"
                              data-testid={`compare-metric-delta-${metricKey}-${runId}`}
                              data-tone={getMetricDeltaTone(deltaItem.deltaVsBaseline)}
                            >
                              {`差异 ${formatSignedPct(deltaItem.deltaVsBaseline)}`}
                            </span>
                          )}
                          <span
                            className="compare-metric-badge"
                            data-testid={`compare-metric-state-${metricKey}-${runId}`}
                            data-tone={getMetricStateTone({
                              state: highlight?.state || metric.state,
                              highlightApplies,
                              isUnavailable: false,
                            })}
                          >
                            {formatCompareStateWithRaw(highlightApplies ? (highlight?.state || 'winner') : (highlight?.state || metric.state))}
                          </span>
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CompareMetricChartStrip({
  items,
  baselineRunId,
  metricDeltas,
  highlights,
}: {
  items: RuleBacktestCompareRunItem[];
  baselineRunId?: number | null;
  metricDeltas: Record<string, RuleBacktestCompareMetricDelta>;
  highlights: Record<string, RuleBacktestCompareHighlightItem>;
}) {
  const metricEntries = COMPARE_CHART_STRIP_KEYS.reduce<Array<[string, RuleBacktestCompareMetricDelta]>>((entries, metricKey) => {
    const metric = metricDeltas[metricKey];
    if (metric) entries.push([metricKey, metric]);
    return entries;
  }, []);

  if (!metricEntries.length || !items.length) {
    return <div className="product-empty-state product-empty-state--compact">当前比较没有足够的已校验指标来生成可视化条带。</div>;
  }

  return (
    <div className="comparison-chart compare-chart-strip" data-testid="compare-chart-strip">
      {metricEntries.map(([metricKey, metric]) => {
        const highlight = highlights[metricKey];
        const availableValues = metric.deltas.reduce<number[]>((acc, entry) => { const v = Math.abs(entry.value ?? 0); if (v > 0) acc.push(v); return acc; }, []);
        const maxValue = availableValues.length ? Math.max(...availableValues) : 1;

        return (
          <div key={metricKey} className="compare-chart-strip__row" data-testid={`compare-chart-strip-row-${metricKey}`}>
            <div className="compare-chart-strip__label">
              <span>{formatMetricLabel(metricKey, metric.label)}</span>
              <span className="compare-metric-badge" data-tone={getMetricSummaryTone(highlight?.state || metric.state)}>
                {formatCompareStateWithRaw(highlight?.state || metric.state)}
              </span>
            </div>
            <div className="compare-chart-strip__lanes">
              {items.map((item) => {
                const runId = item.metadata.id;
                const deltaItem = metric.deltas.find((entry) => entry.runId === runId);
                const isBaseline = runId === baselineRunId;
                const state = deltaItem ? 'available' : 'unavailable';
                const widthPct = deltaItem ? Math.max(12, (Math.abs(deltaItem.value ?? 0) / maxValue) * 100) : 0;
                const tone = deltaItem
                  ? (highlight?.winnerRunIds.includes(runId) ? 'best' : getMetricDeltaTone(deltaItem.value))
                  : 'unavailable';

                return (
                  <div
                    key={`${metricKey}-${runId}`}
                    className="compare-chart-strip__lane"
                    data-testid={`compare-chart-strip-${metricKey}-${runId}`}
                    data-role={isBaseline ? 'baseline' : 'candidate'}
                    data-state={state}
                  >
                    <div className="compare-chart-strip__meta">
                      <span>{`#${runId} ${formatCompareRoleLabel(isBaseline)}`}</span>
                      <span>{item.metadata.code || '--'}</span>
                    </div>
                    {deltaItem ? (
                      <>
                        <div className="compare-chart-strip__bar-shell">
                          <div className="compare-chart-strip__bar" data-tone={tone} style={{ width: `${widthPct}%` }} />
                        </div>
                        <div className="compare-chart-strip__value">
                          <span>{pct(deltaItem.value)}</span>
                          {!isBaseline ? <span className="product-footnote">{`相对基准 ${formatSignedPct(deltaItem.deltaVsBaseline)}`}</span> : null}
                        </div>
                      </>
                    ) : (
                      <span className="compare-metric-badge" data-tone="unavailable">不可用</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function CompareItemsTable({
  items,
  baselineRunId,
  onOpenRun,
  onMakeBaseline,
  onRemoveRun,
}: {
  items: RuleBacktestCompareRunItem[];
  baselineRunId?: number | null;
  onOpenRun: (runId: number) => void;
  onMakeBaseline: (runId: number) => void;
  onRemoveRun: (runId: number) => void;
}) {
  if (!items.length) {
    return <div className="product-empty-state product-empty-state--compact">当前比较没有可展示的运行详情。</div>;
  }

  return (
    <div className="product-table-shell">
      <table className="product-table">
        <thead>
          <tr>
            <th>运行</th>
            <th>代码 / 状态</th>
            <th>区间</th>
            <th className="product-table__align-right">总收益</th>
            <th className="product-table__align-right">超额</th>
            <th className="product-table__align-right">回撤</th>
            <th className="product-table__align-right">交易</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const metadata = item.metadata || { id: 0 };
            const metrics = item.metrics || {};
            const isBaseline = baselineRunId === metadata.id;
            return (
              <tr key={metadata.id} data-active={isBaseline ? 'true' : 'false'}>
                <td>
                  <div className="product-table__stack">
                    <span>#{metadata.id}</span>
                    <span>{formatCompareRoleLabel(isBaseline)}</span>
                  </div>
                </td>
                <td>
                  <div className="product-table__stack">
                    <span>{metadata.code || '--'}</span>
                    <span>{metadata.status || '--'}</span>
                  </div>
                </td>
                <td>
                  <div className="product-table__stack">
                    <span>{metadata.startDate || '--'} {'->'} {metadata.endDate || '--'}</span>
                    <span>{formatDateTime(metadata.completedAt)}</span>
                  </div>
                </td>
                <td className="product-table__align-right">{pct(metrics.totalReturnPct)}</td>
                <td className="product-table__align-right">{pct(metrics.excessReturnVsBenchmarkPct)}</td>
                <td className="product-table__align-right">{pct(metrics.maxDrawdownPct)}</td>
                <td className="product-table__align-right">{metrics.tradeCount ?? '--'}</td>
                <td>
                  <div className="product-table__stack compare-run-actions">
                    <Button size="sm" variant="ghost" aria-label={`打开结果页 ${metadata.id}`} onClick={() => onOpenRun(metadata.id)}>
                      打开结果页
                    </Button>
                    {isBaseline ? (
                      <span className="product-footnote">当前基准</span>
                    ) : (
                      <>
                        <Button size="sm" variant="ghost" aria-label={`设为基准 ${metadata.id}`} onClick={() => onMakeBaseline(metadata.id)}>
                          设为基准
                        </Button>
                        <Button size="sm" variant="ghost" aria-label={`移除运行 ${metadata.id}`} onClick={() => onRemoveRun(metadata.id)}>
                          移除运行
                        </Button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CompareSensitivityGrid({
  items,
  baselineRunId,
  parameterComparison,
  highlights,
}: {
  items: RuleBacktestCompareRunItem[];
  baselineRunId?: number | null;
  parameterComparison?: RuleBacktestCompareParameterComparison | null;
  highlights: Record<string, RuleBacktestCompareHighlightItem>;
}) {
  const rows = buildCompareSensitivityRows({
    items,
    baselineRunId,
    parameterComparison,
    highlights,
  });

  if (!rows.length) {
    return (
      <div className="product-empty-state product-empty-state--compact" data-testid="compare-sensitivity-empty">
        当前比较缺少可归因的参数差异或已校验亮点，暂不展示敏感度网格。
      </div>
    );
  }

  const parameterRows = rows.filter((row) => row.sourceLabel !== '场景设置').length;
  const scenarioRows = rows.filter((row) => row.sourceLabel === '场景设置').length;

  return (
    <div data-testid="compare-sensitivity-grid">
      <SummaryStrip
        items={[
          {
            label: '可归因行',
            value: String(rows.length),
            note: `参数 ${parameterRows} / 元数据 ${scenarioRows}`,
          },
          {
            label: '参数状态',
            value: formatCompareStateWithRaw(parameterComparison?.state),
            note: `共享 ${parameterComparison?.sharedParameterKeys.length ?? 0}`,
          },
          {
            label: '亮点覆盖',
            value: String(Object.keys(highlights || {}).length),
            note: '仅复用已完成比较亮点',
          },
        ]}
      />

      <div className="preview-grid mt-4">
        {rows.map((row) => (
          <article
            key={row.key}
            className="preview-card"
            data-testid={`compare-sensitivity-row-${slugifyCompareKey(row.key)}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="metric-card__label">{row.sourceLabel}</p>
                <p className="preview-card__text">{row.label}</p>
              </div>
              <span className="compare-metric-badge" data-tone={getMetricSummaryTone(row.state)}>{formatCompareStateWithRaw(row.state)}</span>
            </div>

            <div className="product-chip-list product-chip-list--tight mt-3">
              {row.values.map((value) => (
                <span key={`${row.key}-${value.runId}`} className="product-chip">
                  {`#${value.runId} ${formatCompareRoleLabel(value.isBaseline)} · ${value.label}`}
                </span>
              ))}
            </div>

            <div className="product-chip-list product-chip-list--tight mt-3">
              {row.signals.map((signal) => (
                <span key={`${row.key}-${signal.metricKey}`} className="product-chip">
                  {`${signal.label}: ${signal.winners.length ? signal.winners.join(' / ') : formatCompareStateWithRaw(signal.state)}`}
                </span>
              ))}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function CompareCostSlippagePanel({
  items,
  baselineRunId,
  parameterComparison,
  highlights,
  metricDeltas,
}: {
  items: RuleBacktestCompareRunItem[];
  baselineRunId?: number | null;
  parameterComparison?: RuleBacktestCompareParameterComparison | null;
  highlights: Record<string, RuleBacktestCompareHighlightItem>;
  metricDeltas: Record<string, RuleBacktestCompareMetricDelta>;
}) {
  const panelData = buildCompareCostSlippagePanelData({
    items,
    baselineRunId,
    parameterComparison,
    highlights,
    metricDeltas,
  });

  if (!panelData) {
    return (
      <TerminalEmptyState title="费用 / 滑点" className="mt-4" data-testid="compare-cost-slippage-empty">
        当前比较的费率与滑点设定没有形成可读差异，暂不单独展开费滑敏感度。
      </TerminalEmptyState>
    );
  }

  return (
    <TerminalNestedBlock className="mt-4 space-y-3 min-w-0" data-testid="compare-cost-slippage-panel">
      <TerminalSectionHeader
        eyebrow="费用 / 滑点"
        title="费滑场景"
        action={<TerminalChip variant={getTerminalChipVariantFromState(panelData.state)}>{formatCompareStateWithRaw(panelData.state)}</TerminalChip>}
      />

      <div className="flex flex-wrap gap-2">
        {panelData.sourceLabels.map((sourceLabel) => (
          <TerminalChip key={sourceLabel} variant="neutral">{sourceLabel}</TerminalChip>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {panelData.scenarios.map((scenario) => (
          <TerminalChip key={scenario.runId} variant={scenario.isBaseline ? 'info' : 'neutral'} className="whitespace-normal">
            {`#${scenario.runId} ${formatCompareRoleLabel(scenario.isBaseline)} · ${scenario.label}`}
          </TerminalChip>
        ))}
      </div>

      {panelData.signals.length ? (
        <div className="space-y-2">
          <p className="text-[10px] font-bold uppercase tracking-widest text-white/35">已完成指标差异</p>
          <div className="flex flex-wrap gap-2">
            {panelData.signals.map((signal) => (
              <TerminalChip key={signal.metricKey} variant={getTerminalChipVariantFromState(signal.state)} className="whitespace-normal">
                {`${signal.label} · ${signal.entries.join(' / ')}`}
              </TerminalChip>
            ))}
          </div>
        </div>
      ) : (
        <p className="product-footnote">当前比较没有可映射到费滑场景的已完成指标差异。</p>
      )}
    </TerminalNestedBlock>
  );
}

const RuleBacktestComparePage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const runIds = parseRunIdsParam(searchParams.get('runIds'));
  const [response, setResponse] = useState<RuleBacktestCompareResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const copyResetTimerRef = useRef<number | null>(null);

  const fetchCompare = async () => {
    if (runIds.length < 2) {
      setResponse(null);
      setError(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const payload = await backtestApi.compareRuleBacktestRuns({ runIds });
      setResponse(payload);
      setError(null);
    } catch (nextError) {
      setError(getParsedApiError(nextError));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    document.title = '规则回测比较工作台 - WolfyStock';
  }, []);

  useEffect(() => {
    void fetchCompare();
  }, [fetchCompare]);

  useEffect(() => () => {
    if (copyResetTimerRef.current != null) {
      window.clearTimeout(copyResetTimerRef.current);
    }
  }, []);

  const orderedItems = orderCompareItems(response?.items || [], runIds);
  const baselineRunId = response?.comparisonSummary?.baseline.runId
    ?? response?.robustnessSummary?.baselineRunId
    ?? response?.comparisonProfile?.baselineRunId
    ?? runIds[0]
    ?? null;
  const baselineItem = orderedItems.find((item) => item.metadata.id === baselineRunId) || null;
  const comparisonSummary = response?.comparisonSummary || null;
  const robustnessSummary = response?.robustnessSummary || null;
  const comparisonProfile = response?.comparisonProfile || null;
  const comparisonHighlights = response?.comparisonHighlights || null;
  const parameterComparison = response?.parameterComparison || null;
  const marketCodeComparison = response?.marketCodeComparison || null;
  const periodComparison = response?.periodComparison || null;
  const compareUrl = (() => {
    const query = searchParams.toString();
    return `${window.location.origin}/backtest/compare${query ? `?${query}` : ''}`;
  })();
  const compareSummaryText = buildCompareShareSummary({
    runIds,
    baselineRunId,
    baselineCode: baselineItem?.metadata.code || comparisonSummary?.baseline.code || '--',
    overallState: robustnessSummary?.overallState,
    primaryProfile: comparisonProfile?.primaryProfile,
    comparableCount: response?.comparableRunIds.length,
    requestedCount: response?.requestedRunIds.length,
  });
  const advancedDiagnostics = collectCompareDiagnostics(
    comparisonHighlights?.diagnostics,
    robustnessSummary?.diagnostics,
    comparisonProfile?.diagnostics,
    marketCodeComparison?.diagnostics,
    periodComparison?.diagnostics,
    Object.values(comparisonHighlights?.highlights || {}).flatMap((item) => item.diagnostics || []),
    Object.values(robustnessSummary?.dimensions || {}).flatMap((dimension) => dimension.diagnostics || []),
  );

  const handleOpenRun = (runId: number) => {
    navigate(`/backtest/results/${runId}`);
  };

  const handleCopyText = async (content: string, successMessage: string) => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('clipboard_unavailable');
      await navigator.clipboard.writeText(content);
      setCopyFeedback(successMessage);
    } catch {
      setCopyFeedback('复制失败，请手动复制');
    }
    if (copyResetTimerRef.current != null) {
      window.clearTimeout(copyResetTimerRef.current);
    }
    copyResetTimerRef.current = window.setTimeout(() => {
      setCopyFeedback(null);
      copyResetTimerRef.current = null;
    }, 2000);
  };

  const handleRemoveRun = (runId: number) => {
    const nextRunIds = runIds.filter((id) => id !== runId);
    const nextParams = new URLSearchParams(searchParams);
    setResponse(null);
    if (nextRunIds.length) {
      nextParams.set('runIds', nextRunIds.join(','));
    } else {
      nextParams.delete('runIds');
    }
    setSearchParams(nextParams);
  };

  const handleMakeBaseline = (runId: number) => {
    if (runIds[0] === runId) return;
    const nextRunIds = [runId, ...runIds.filter((id) => id !== runId)];
    const nextParams = new URLSearchParams(searchParams);
    setResponse(null);
    nextParams.set('runIds', nextRunIds.join(','));
    setSearchParams(nextParams);
  };

  return (
    <main className="w-full overflow-x-hidden text-white">
      <TerminalPageShell data-testid="rule-backtest-compare-page">
        <WolfyCommandBar
          leading={(
            <div className="min-w-0">
              <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">WolfyStock</p>
              <h1 className="mt-1 truncate text-lg font-semibold text-[color:var(--wolfy-text-primary)] md:text-xl">规则回测比较工作台</h1>
              <p className="mt-1 text-sm text-[color:var(--wolfy-text-secondary)]">
                对比已完成规则回测运行，先看可比性、结果来源和有限置信状态。
              </p>
            </div>
          )}
          trailing={(
            <div className="flex flex-wrap gap-2">
              <Button variant="ghost" onClick={() => navigate('/backtest')}>
                返回回测工作区
              </Button>
              <Button variant="secondary" onClick={() => void fetchCompare()} disabled={runIds.length < 2}>
                {isLoading ? '刷新中…' : '刷新比较'}
              </Button>
            </div>
          )}
        />

        {runIds.length < 2 ? (
          <section className="backtest-display-section">
            <ConsoleBoard>
              <div className="p-4 md:p-5">
                <TerminalEmptyState title="比较工作台未就绪">
                  至少需要 2 条已完成运行才能打开比较工作台。
                </TerminalEmptyState>
              </div>
            </ConsoleBoard>
          </section>
        ) : null}

        {runIds.length >= 2 && isLoading && !response ? (
          <section className="backtest-display-section">
            <ConsoleBoard>
              <div className="flex flex-col gap-3 p-4 md:p-5">
                <div>
                  <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">结果生成中，请稍后刷新。</p>
                  <h2 className="mt-1 text-base font-semibold text-[color:var(--wolfy-text-primary)]">加载比较结果</h2>
                </div>
                <div className="text-sm text-[color:var(--wolfy-text-secondary)]">正在拉取比较结果…</div>
              </div>
            </ConsoleBoard>
          </section>
        ) : null}

        {runIds.length >= 2 && error ? (
          <section className="backtest-display-section">
            <ConsoleBoard>
              <div className="flex flex-col gap-3 p-4 md:p-5">
                <div>
                  <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">比较接口返回了错误</p>
                  <h2 className="mt-1 text-base font-semibold text-[color:var(--wolfy-text-primary)]">比较加载失败</h2>
                </div>
                <ApiErrorAlert error={error} />
              </div>
            </ConsoleBoard>
          </section>
        ) : null}

        {runIds.length >= 2 && response ? (
          <ResearchConsoleShell
            command={(
              <ConsoleStatusStrip
                items={[
                  {
                    key: 'baseline',
                    label: '基准运行',
                    value: baselineRunId == null ? '--' : `#${baselineRunId}`,
                  },
                  {
                    key: 'overall',
                    label: '可比性',
                    value: formatCompareStateWithRaw(robustnessSummary?.overallState),
                  },
                  {
                    key: 'profile',
                    label: '结果置信度',
                    value: formatCompareStateWithRaw(comparisonProfile?.primaryProfile),
                  },
                  {
                    key: 'source',
                    label: '结果来源',
                    value: formatCompareSourceLabel(response.comparisonSource),
                  },
                ]}
              />
            )}
            rail={(
              <ConsoleContextRail className="gap-0">
                <section id="compare-summary" className="space-y-3">
                  <div>
                    <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">比较摘要</p>
                    <h2 className="mt-1 text-sm font-medium text-[color:var(--wolfy-text-primary)]">先看整体上下文，再决定是否相信单项领先</h2>
                  </div>
                  <nav aria-label="比较区块导航" className="flex flex-wrap gap-2">
                    {COMPARE_SECTION_LINKS.map((item) => (
                      <a key={item.id} className="product-chip product-chip--interactive compare-section-nav__link" href={`#${item.id}`}>
                        {item.label}
                      </a>
                    ))}
                  </nav>
                  <div className="space-y-2 text-xs text-[color:var(--wolfy-text-secondary)]">
                    <div className="flex items-start justify-between gap-3">
                      <span>基准</span>
                      <span className="max-w-[60%] truncate text-right font-mono text-[color:var(--wolfy-text-primary)]">
                        #{baselineRunId ?? '--'} · {formatCompareStateWithRaw(comparisonSummary?.baseline.strategyType)}
                      </span>
                    </div>
                    <div className="flex items-start justify-between gap-3">
                      <span>周期 / 代码</span>
                      <span className="max-w-[60%] truncate text-right font-mono text-[color:var(--wolfy-text-primary)]">
                        {comparisonSummary?.baseline.timeframe || '--'} · {comparisonSummary?.baseline.code || '--'}
                      </span>
                    </div>
                    <div className="flex items-start justify-between gap-3">
                      <span>缺失运行</span>
                      <span className="max-w-[60%] truncate text-right font-mono text-[color:var(--wolfy-text-primary)]">
                        {formatRunCountLabel(response.missingRunIds)}
                      </span>
                    </div>
                    <div className="flex items-start justify-between gap-3">
                      <span>比较维度</span>
                      <span className="max-w-[60%] truncate text-right font-mono text-[color:var(--wolfy-text-primary)]">
                        {formatCompareList(response.fieldGroups)}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="ghost" onClick={() => void handleCopyText(compareUrl, '已复制当前比较链接')}>复制链接</Button>
                    <Button size="sm" variant="ghost" onClick={() => void handleCopyText(runIds.join(','), '已复制当前运行 ID')}>复制运行 ID</Button>
                    <Button size="sm" variant="ghost" onClick={() => void handleCopyText(compareSummaryText, '已复制比较摘要')}>复制摘要</Button>
                  </div>
                  {copyFeedback ? <p className="text-xs text-[color:var(--wolfy-text-muted)]">{copyFeedback}</p> : null}
                  {response.unavailableRuns.length ? (
                    <Banner
                      tone="warning"
                      title="存在不可用运行"
                      body={response.unavailableRuns.map((item) => `#${item.runId}: ${formatUnavailableRunReason(item.reason)}`).join(' | ')}
                    />
                  ) : null}
                </section>
                <ConsoleDisclosure id="compare-highlights" title="比较亮点" summary="展示可读比较亮点，有限置信时保留提醒。" defaultOpen>
                  <SummaryStrip
                    items={[
                      {
                        label: '主要画像',
                        value: formatCompareStateWithRaw(comparisonHighlights?.primaryProfile),
                        note: '基于已完成比较结果',
                      },
                      {
                        label: '整体上下文',
                        value: formatCompareStateWithRaw(comparisonHighlights?.overallContextState),
                        note: `基准 #${comparisonHighlights?.baselineRunId ?? '--'}`,
                      },
                    ]}
                  />
                  <div className="mt-4">
                    <HighlightCards highlights={comparisonHighlights?.highlights || {}} />
                  </div>
                </ConsoleDisclosure>
                <ConsoleDisclosure id="compare-robustness" title="稳健性画像" summary="展示可比性和有限置信状态。" defaultOpen>
                  <SummaryStrip
                    items={[
                      {
                        label: '稳健性',
                        value: formatCompareStateWithRaw(robustnessSummary?.overallState),
                        note: `可直接比较 ${robustnessSummary?.directlyComparable == null ? '--' : renderBooleanLabel(robustnessSummary.directlyComparable)}`,
                      },
                      {
                        label: '一致维度',
                        value: String(robustnessSummary?.alignedDimensions.length ?? 0),
                        note: formatCompareList(robustnessSummary?.alignedDimensions),
                      },
                      {
                        label: '部分维度',
                        value: String(robustnessSummary?.partialDimensions.length ?? 0),
                        note: formatCompareList(robustnessSummary?.partialDimensions),
                      },
                      {
                        label: '主要画像',
                        value: formatCompareStateWithRaw(comparisonProfile?.primaryProfile),
                        note: formatCompareList(comparisonProfile?.drivingDimensions),
                      },
                    ]}
                  />
                  <div className="preview-grid mt-4">
                    <div className="preview-card">
                      <p className="metric-card__label">同一标的</p>
                      <p className="preview-card__text">{renderBooleanLabel(comparisonProfile?.dimensionFlags.sameCode)}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">同一市场</p>
                      <p className="preview-card__text">{renderBooleanLabel(comparisonProfile?.dimensionFlags.sameMarket)}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">存在参数差异</p>
                      <p className="preview-card__text">{renderBooleanLabel(comparisonProfile?.dimensionFlags.parameterDifferencesPresent)}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">存在区间差异</p>
                      <p className="preview-card__text">{renderBooleanLabel(comparisonProfile?.dimensionFlags.periodDifferencesPresent)}</p>
                    </div>
                  </div>
                  <div className="mt-4">
                    <RobustnessDimensionCards dimensions={robustnessSummary?.dimensions || {}} />
                  </div>
                </ConsoleDisclosure>
                <ConsoleDisclosure title="市场与区间上下文" summary="展示标的和区间是否适合放在一起比较。" defaultOpen>
                  <div id="compare-market-period" className="preview-grid">
                    <div className="preview-card">
                      <p className="metric-card__label">市场 / 代码比较</p>
                      <p className="preview-card__text">{formatCompareStateWithRaw(marketCodeComparison?.state)}</p>
                      <p className="product-footnote">关系：{formatCompareStateWithRaw(marketCodeComparison?.relationship)}</p>
                      <p className="product-footnote">可直接比较：{marketCodeComparison?.directlyComparable == null ? '--' : renderBooleanLabel(marketCodeComparison.directlyComparable)}</p>
                    </div>
                    <div className="preview-card">
                      <p className="metric-card__label">区间比较</p>
                      <p className="preview-card__text">{formatCompareStateWithRaw(periodComparison?.state)}</p>
                      <p className="product-footnote">关系：{formatCompareStateWithRaw(periodComparison?.relationship)}</p>
                      <p className="product-footnote">有意义可比：{periodComparison?.meaningfullyComparable == null ? '--' : renderBooleanLabel(periodComparison.meaningfullyComparable)}</p>
                    </div>
                  </div>
                </ConsoleDisclosure>
                <ConsoleDisclosure title="高级比较依据" summary="默认折叠，保留比较限制与边界说明。">
                  <DiagnosticChipList diagnostics={advancedDiagnostics} />
                </ConsoleDisclosure>
                <ConsoleDisclosure title="参数与指标" summary="参数差异与已校验指标差异放在同一工作台里读" defaultOpen>
                  <div id="compare-parameter-metrics" className="space-y-4">
                    <div className="preview-grid">
                      <div className="preview-card">
                        <p className="metric-card__label">参数比较</p>
                        <p className="preview-card__text">{formatCompareStateWithRaw(parameterComparison?.state)}</p>
                        <p className="product-footnote">共享：{parameterComparison?.sharedParameterKeys.length ?? 0}</p>
                        <p className="product-footnote">不同：{parameterComparison?.differingParameterKeys.length ?? 0}</p>
                        <p className="product-footnote">缺失：{parameterComparison?.missingParameterKeys.length ?? 0}</p>
                      </div>
                      <div className="preview-card">
                        <p className="metric-card__label">摘要上下文</p>
                        <p className="preview-card__text">全部同标的：{renderBooleanLabel(comparisonSummary?.context.allSameCode)}</p>
                        <p className="product-footnote">全部同周期：{renderBooleanLabel(comparisonSummary?.context.allSameTimeframe)}</p>
                        <p className="product-footnote">全部同日期区间：{renderBooleanLabel(comparisonSummary?.context.allSameDateRange)}</p>
                      </div>
                    </div>
                    <MetricDeltaTable metricDeltas={comparisonSummary?.metricDeltas || {}} />
                  </div>
                </ConsoleDisclosure>
              </ConsoleContextRail>
            )}
          >
            <ConsoleBoard className="min-h-0">
              <KeyLevelStrip
                className="sm:grid-cols-2 xl:grid-cols-4"
                levels={[
                  {
                    key: 'baseline',
                    label: '基准运行',
                    value: baselineRunId == null ? '--' : `#${baselineRunId}`,
                  },
                  {
                    key: 'overall',
                    label: '可比性',
                    value: formatCompareStateWithRaw(robustnessSummary?.overallState),
                  },
                  {
                    key: 'counts',
                    label: '请求 / 可比',
                    value: `${response.requestedRunIds.length} / ${response.comparableRunIds.length}`,
                  },
                  {
                    key: 'parameters',
                    label: '参数状态',
                    value: formatCompareStateWithRaw(parameterComparison?.state),
                  },
                ]}
              />
              <div className="flex flex-col gap-6 p-3 md:p-4">
                <section id="compare-chart-strip" className="space-y-3">
                  <div>
                    <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">指标条带</p>
                    <h2 className="mt-1 text-sm font-medium text-[color:var(--wolfy-text-primary)]">只取最小已校验指标子集，先用轻量条带看基准与候选的相对位置</h2>
                  </div>
                  <CompareMetricChartStrip
                    items={orderedItems}
                    baselineRunId={baselineRunId}
                    metricDeltas={comparisonSummary?.metricDeltas || {}}
                    highlights={comparisonHighlights?.highlights || {}}
                  />
                </section>

                <section id="compare-metric-matrix" className="space-y-4">
                  <div>
                    <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">指标矩阵</p>
                    <h2 className="mt-1 text-sm font-medium text-[color:var(--wolfy-text-primary)]">把基准、差异、领先项与不可用状态压到一张易扫读的比较表</h2>
                  </div>
                  <SummaryStrip
                    items={[
                      {
                        label: '基准',
                        value: baselineRunId == null ? '--' : `#${baselineRunId}`,
                        note: baselineItem?.metadata.code || '--',
                      },
                      {
                        label: '整体状态',
                        value: formatCompareStateWithRaw(robustnessSummary?.overallState),
                        note: formatCompareStateWithRaw(comparisonProfile?.primaryProfile),
                      },
                      {
                        label: '指标数',
                        value: String(Object.keys(comparisonSummary?.metricDeltas || {}).length),
                        note: response.comparableRunIds.map((id) => `#${id}`).join(', ') || '--',
                      },
                    ]}
                  />
                  <CompareMetricMatrix
                    items={orderedItems}
                    baselineRunId={baselineRunId}
                    metricDeltas={comparisonSummary?.metricDeltas || {}}
                    highlights={comparisonHighlights?.highlights || {}}
                    overallState={robustnessSummary?.overallState}
                    primaryProfile={comparisonProfile?.primaryProfile}
                  />
                </section>

                <section id="compare-parameter-sensitivity" className="space-y-4">
                  <div>
                    <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">参数敏感度网格</p>
                    <h2 className="mt-1 text-sm font-medium text-[color:var(--wolfy-text-primary)]">基于已完成比较结果展示参数差异、亮点指标与场景设置</h2>
                  </div>
                  <CompareCostSlippagePanel
                    items={orderedItems}
                    baselineRunId={baselineRunId}
                    parameterComparison={parameterComparison}
                    highlights={comparisonHighlights?.highlights || {}}
                    metricDeltas={comparisonSummary?.metricDeltas || {}}
                  />
                  <RuleBacktestCompareHeatmapProjectionPanel projection={response.heatmapProjection} />
                  <CompareSensitivityGrid
                    items={orderedItems}
                    baselineRunId={baselineRunId}
                    parameterComparison={parameterComparison}
                    highlights={comparisonHighlights?.highlights || {}}
                  />
                </section>

                <section id="compare-items" className="space-y-3">
                  <div>
                    <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">参与运行</p>
                    <h2 className="mt-1 text-sm font-medium text-[color:var(--wolfy-text-primary)]">保留紧凑运行表，方便快速对照基准与候选</h2>
                  </div>
                  <CompareItemsTable
                    items={orderedItems}
                    baselineRunId={baselineRunId}
                    onOpenRun={handleOpenRun}
                    onMakeBaseline={handleMakeBaseline}
                    onRemoveRun={handleRemoveRun}
                  />
                </section>
              </div>
            </ConsoleBoard>
          </ResearchConsoleShell>
        ) : null}
      </TerminalPageShell>
    </main>
  );
};

export default RuleBacktestComparePage;
