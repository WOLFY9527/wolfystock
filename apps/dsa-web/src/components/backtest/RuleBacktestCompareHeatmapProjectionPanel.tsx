import { Fragment } from 'react';
import { TerminalChip, TerminalEmptyState, TerminalNestedBlock, TerminalSectionHeader } from '../terminal/TerminalPrimitives';
import { formatNumber, pct } from './shared';
import {
  formatCompareStateWithRaw,
  getTerminalChipVariantFromState,
} from './compareDisplayHelpers';
import type { RuleBacktestCompareHeatmapProjection } from '../../types/backtest';

function renderBooleanLabel(value: boolean | undefined): string {
  return value ? '是' : '否';
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

function createHeatmapCellKey(xValue: unknown, yValue: unknown): string {
  return JSON.stringify([xValue ?? null, yValue ?? null]);
}

function formatHeatmapAxisLabel(axisKey?: string | null, axisLabel?: string | null): string {
  if (axisKey) return formatSensitivityLabel(axisKey);
  if (axisLabel) return formatSensitivityLabel(axisLabel);
  return '参数';
}

function getHeatmapCellLabel(state?: string | null): string {
  const normalized = String(state || '').toLowerCase();
  if (normalized === 'available') return '可用';
  if (normalized === 'missing') return '不可用';
  if (normalized === 'ambiguous') return '歧义';
  return formatCompareStateWithRaw(state);
}

function getHeatmapCellTone(state?: string | null): 'neutral' | 'success' | 'caution' | 'danger' | 'info' {
  const normalized = String(state || '').toLowerCase();
  if (normalized === 'available') return 'success';
  if (normalized === 'ambiguous') return 'caution';
  if (normalized === 'missing') return 'danger';
  return getTerminalChipVariantFromState(state || undefined);
}

function formatHeatmapMetricValue(value?: number | null): string {
  return value == null || Number.isNaN(value) ? '--' : pct(value);
}

export default function RuleBacktestCompareHeatmapProjectionPanel({
  projection,
}: {
  projection?: RuleBacktestCompareHeatmapProjection | null;
}) {
  if (!projection) {
    return (
      <TerminalEmptyState title="参数热力投影" className="mt-4" data-testid="compare-heatmap-empty">
        当前比较未提供可查看的参数热力投影。
      </TerminalEmptyState>
    );
  }

  const xAxis = projection.axes?.x;
  const yAxis = projection.axes?.y;
  const xValues = xAxis?.values || [];
  const yValues = yAxis?.values || [];
  const cells = projection.cells || [];

  if (!xValues.length || !yValues.length || !cells.length) {
    return (
      <TerminalEmptyState title="参数热力投影" className="mt-4" data-testid="compare-heatmap-empty">
        当前比较没有可渲染的参数组合结果。
      </TerminalEmptyState>
    );
  }

  const cellMap = new Map(cells.map((cell) => [createHeatmapCellKey(cell.xValue, cell.yValue), cell]));
  const xAxisLabel = formatHeatmapAxisLabel(xAxis.axisKey, xAxis.axisLabel);
  const yAxisLabel = formatHeatmapAxisLabel(yAxis.axisKey, yAxis.axisLabel);
  const hasLimitedCells = cells.some((cell) => {
    const state = String(cell.availabilityState || '').toLowerCase();
    return state === 'missing' || state === 'ambiguous';
  });

  return (
    <TerminalNestedBlock className="mt-4 space-y-3 min-w-0" data-testid="compare-heatmap-panel">
      <TerminalSectionHeader
        eyebrow="参数敏感度"
        title="参数热力投影"
        action={<TerminalChip variant={hasLimitedCells ? 'caution' : 'info'}>{hasLimitedCells ? '部分可用' : '诊断可查'}</TerminalChip>}
      />
      <p className="product-footnote">基于已完成回测结果生成，用于观察参数差异下的历史表现。</p>

      <div className="flex flex-wrap gap-2">
        <TerminalChip variant="neutral">结果可查看</TerminalChip>
        <TerminalChip variant={hasLimitedCells ? 'caution' : 'info'}>
          {hasLimitedCells ? '回测数据质量有限，结果仅供观察复盘。' : '当前结果仅用于观察参数差异下的历史表现。'}
        </TerminalChip>
      </div>

      <div className="flex flex-wrap gap-2">
        <TerminalChip variant="neutral">{`横轴 ${xAxisLabel}`}</TerminalChip>
        <TerminalChip variant="neutral">{`纵轴 ${yAxisLabel}`}</TerminalChip>
      </div>

      <div className="overflow-x-auto no-scrollbar">
        <div
          className="grid gap-2 min-w-[32rem]"
          style={{ gridTemplateColumns: `minmax(7rem, 1.05fr) repeat(${xValues.length}, minmax(8rem, 1fr))` }}
        >
          <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] p-3">
            <p className="metric-card__label">{yAxisLabel}</p>
            <p className="product-footnote">{`横向 ${xAxisLabel}`}</p>
          </div>
          {xValues.map((xValue) => (
            <div
              key={`compare-heatmap-x-${formatSensitivityValue(xValue)}`}
              className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] p-3"
            >
              <p className="metric-card__label">{xAxisLabel}</p>
              <p className="preview-card__text">{formatSensitivityValue(xValue)}</p>
            </div>
          ))}

          {yValues.map((yValue, yIndex) => (
            <Fragment key={`compare-heatmap-y-${formatSensitivityValue(yValue)}`}>
              <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] p-3">
                <p className="metric-card__label">{yAxisLabel}</p>
                <p className="preview-card__text">{formatSensitivityValue(yValue)}</p>
              </div>
              {xValues.map((xValue, xIndex) => {
                const cell = cellMap.get(createHeatmapCellKey(xValue, yValue));
                const state = cell?.availabilityState;
                const totalReturnMetric = cell?.metrics?.totalReturnPct;
                const maxDrawdownMetric = cell?.metrics?.maxDrawdownPct;
                const totalReturnAvailable = state === 'available' && totalReturnMetric?.value != null;
                const maxDrawdownAvailable = state === 'available' && maxDrawdownMetric?.value != null;

                return (
                  <div
                    key={`compare-heatmap-cell-${createHeatmapCellKey(xValue, yValue)}`}
                    className="rounded-xl border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] p-3"
                    data-state={state || 'missing_cell'}
                    data-testid={`compare-heatmap-cell-${yIndex}-${xIndex}`}
                  >
                    {cell ? (
                      <div className="space-y-2">
                        <TerminalChip variant={getHeatmapCellTone(state)}>{getHeatmapCellLabel(state)}</TerminalChip>
                        {state === 'available' ? (
                          <div className="space-y-1">
                            <p className="product-footnote">{`总收益 ${formatHeatmapMetricValue(totalReturnMetric?.value)}`}</p>
                            <p className="product-footnote">{`最大回撤 ${formatHeatmapMetricValue(maxDrawdownMetric?.value)}`}</p>
                            {!totalReturnAvailable && !maxDrawdownAvailable ? (
                              <p className="product-footnote">该单元未附带可展示指标。</p>
                            ) : null}
                          </div>
                        ) : state === 'ambiguous' ? (
                          <p className="product-footnote">存在多条来源运行，当前单元不直接展示指标。</p>
                        ) : (
                          <p className="product-footnote">当前参数组合没有可展示结果。</p>
                        )}
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <TerminalChip variant="neutral">未提供</TerminalChip>
                        <p className="product-footnote">后端未返回该坐标单元。</p>
                      </div>
                    )}
                  </div>
                );
              })}
            </Fragment>
          ))}
        </div>
      </div>
    </TerminalNestedBlock>
  );
}
