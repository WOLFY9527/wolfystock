export type CompareTerminalChipVariant = 'neutral' | 'success' | 'caution' | 'danger' | 'info';

export function formatCompareStateLabel(value?: string | null): string {
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

export function formatCompareStateWithRaw(value?: string | null): string {
  const raw = String(value || '').trim();
  const label = formatCompareStateLabel(raw);
  return raw && label !== raw.replaceAll('_', ' ') ? label : label;
}

export function getTerminalChipVariantFromState(state?: string): CompareTerminalChipVariant {
  const normalized = String(state || '').toLowerCase();
  if (normalized.includes('winner') || normalized.includes('aligned') || normalized.includes('direct')) return 'success';
  if (normalized.includes('missing') || normalized.includes('unavailable')) return 'danger';
  if (normalized.includes('limited') || normalized.includes('partial')) return 'caution';
  if (normalized.includes('different') || normalized.includes('divergent') || normalized.includes('comparable')) return 'info';
  return 'neutral';
}
