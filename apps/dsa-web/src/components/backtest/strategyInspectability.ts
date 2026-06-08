import type { RuleBacktestParsedStrategy } from '../../types/backtest';
import {
  formatCashPolicyLabel,
  formatDraftOrderLabel,
  formatExecutionPriceBasisLabel,
  formatExitPolicyLabel,
  formatNumber,
  getPeriodicNumber,
  getPeriodicString,
  getStrategySpecValue,
} from './shared';
import { backtestStrategyDisplayCopy } from './strategyCatalog';

type BacktestLanguage = 'zh' | 'en';

export type RuleStrategySummaryRow = {
  key: string;
  label: string;
  value: string;
};

function formatRuleStrategyFamily(strategyType: string, language: BacktestLanguage = 'zh'): string {
  if (strategyType === 'periodic_accumulation') return language === 'en' ? 'Periodic accumulation' : '区间定投';
  if (strategyType === 'moving_average_crossover') return language === 'en' ? 'Moving-average crossover' : '均线交叉';
  if (strategyType === 'macd_crossover') return language === 'en' ? 'MACD crossover' : 'MACD 交叉';
  if (strategyType === 'rsi_threshold') return language === 'en' ? 'RSI threshold' : 'RSI 阈值';
  if (strategyType === 'rule_conditions') return language === 'en' ? 'Rule conditions' : '条件规则';
  return strategyType || '--';
}

export function getRuleStrategyTypeLabel(
  parsedStrategy: Pick<RuleBacktestParsedStrategy, 'strategyKind' | 'detectedStrategyFamily' | 'strategySpec' | 'setup'> | null | undefined,
  topLevelDetectedStrategyFamily?: string | null,
  language: BacktestLanguage = 'zh',
): string {
  const spec = parsedStrategy?.strategySpec && typeof parsedStrategy.strategySpec === 'object'
    ? parsedStrategy.strategySpec
    : parsedStrategy?.setup && typeof parsedStrategy.setup === 'object'
      ? parsedStrategy.setup
      : undefined;
  const normalizedStrategyType = String(getStrategySpecValue(spec, ['strategy_type']) || '');
  const parsedStrategyKind = String(parsedStrategy?.strategyKind || '');
  const detectedStrategyFamily = String(topLevelDetectedStrategyFamily || parsedStrategy?.detectedStrategyFamily || '') || '';
  const strategyType = normalizedStrategyType
    || (parsedStrategyKind && parsedStrategyKind !== 'rule_conditions' ? parsedStrategyKind : '')
    || detectedStrategyFamily
    || parsedStrategyKind;
  return formatRuleStrategyFamily(strategyType, language);
}

export function getRuleStrategySpecSourceLabel(
  parsedStrategy: Pick<RuleBacktestParsedStrategy, 'strategySpec' | 'setup'> | null | undefined,
  language: BacktestLanguage = 'zh',
): string {
  if (!parsedStrategy) return language === 'en' ? 'Unstructured' : '未结构化';
  const direct = parsedStrategy.strategySpec;
  if (direct && typeof direct === 'object') return language === 'en' ? 'Explicit strategy_spec' : '显式 strategy_spec';
  const fallback = parsedStrategy.setup;
  if (fallback && typeof fallback === 'object') return language === 'en' ? 'Compat setup' : '兼容 setup';
  return language === 'en' ? 'Unstructured' : '未结构化';
}

export function formatRuleNormalizationStateLabel(state?: string | null, language: BacktestLanguage = 'zh'): string {
  if (state === 'ready') return language === 'en' ? 'Ready' : '已完成归一化';
  if (state === 'assumed') return language === 'en' ? 'Defaults applied' : '含默认补全';
  if (state === 'unsupported') return language === 'en' ? 'Unsupported' : '当前不支持';
  if (state === 'pending') return language === 'en' ? 'Pending parse' : '待解析';
  return state || '--';
}

function formatFrequencyLabel(
  spec: Record<string, unknown> | undefined,
  strategyKind?: string | null,
  language: BacktestLanguage = 'zh',
): string {
  const strategyType = String(getStrategySpecValue(spec, ['strategy_type']) || strategyKind || '');
  if (strategyType === 'periodic_accumulation') {
    const frequency = getPeriodicString(spec, 'execution_frequency');
    if (frequency === 'daily') return language === 'en' ? 'Every trading day' : '每个交易日';
    if (frequency === 'weekly') return language === 'en' ? 'Weekly' : '每周';
    if (frequency === 'monthly') return language === 'en' ? 'Monthly' : '每月';
    return frequency === '--' ? '--' : frequency;
  }
  return language === 'en' ? 'Daily signal cadence' : '按日线信号';
}

function formatStrategyCondition(
  spec: Record<string, unknown> | undefined,
  parsedStrategy: Pick<RuleBacktestParsedStrategy, 'strategyKind' | 'summary'> | null | undefined,
  side: 'entry' | 'exit',
  language: BacktestLanguage,
): string {
  const strategyType = String(getStrategySpecValue(spec, ['strategy_type']) || parsedStrategy?.strategyKind || '');
  if (strategyType === 'periodic_accumulation') {
    return side === 'entry' ? formatDraftOrderLabel(spec, language) : formatExitPolicyLabel(spec, language);
  }
  if (strategyType === 'moving_average_crossover') {
    const fastPeriod = getStrategySpecValue(spec, ['signal', 'fast_period']);
    const slowPeriod = getStrategySpecValue(spec, ['signal', 'slow_period']);
    const fastType = String(getStrategySpecValue(spec, ['signal', 'fast_type']) || 'simple');
    const slowType = String(getStrategySpecValue(spec, ['signal', 'slow_type']) || 'simple');
    const fastLabel = `${fastType === 'ema' ? 'EMA' : 'SMA'}${fastPeriod ?? '--'}`;
    const slowLabel = `${slowType === 'ema' ? 'EMA' : 'SMA'}${slowPeriod ?? '--'}`;
    return `${fastLabel} ${side === 'entry' ? (language === 'en' ? 'crosses above' : '上穿') : (language === 'en' ? 'crosses below' : '下穿')} ${slowLabel}`;
  }
  if (strategyType === 'macd_crossover') {
    const fastPeriod = getStrategySpecValue(spec, ['signal', 'fast_period']) ?? 12;
    const slowPeriod = getStrategySpecValue(spec, ['signal', 'slow_period']) ?? 26;
    const signalPeriod = getStrategySpecValue(spec, ['signal', 'signal_period']) ?? 9;
    return `MACD(${fastPeriod},${slowPeriod},${signalPeriod}) ${side === 'entry' ? (language === 'en' ? 'bullish crossover' : '金叉') : (language === 'en' ? 'bearish crossover' : '死叉')}`;
  }
  if (strategyType === 'rsi_threshold') {
    const period = getStrategySpecValue(spec, ['signal', 'period']) ?? 14;
    const threshold = getStrategySpecValue(spec, ['signal', side === 'entry' ? 'lower_threshold' : 'upper_threshold']);
    return `RSI${period} ${side === 'entry' ? (language === 'en' ? 'below' : '低于') : (language === 'en' ? 'above' : '高于')} ${threshold ?? '--'}`;
  }
  return side === 'entry' ? parsedStrategy?.summary?.entry || '--' : parsedStrategy?.summary?.exit || '--';
}

function formatExecutionFrequency(spec: Record<string, unknown> | undefined, language: BacktestLanguage): string {
  const frequency = String(getStrategySpecValue(spec, ['execution', 'frequency']) || getStrategySpecValue(spec, ['schedule', 'frequency']) || '');
  if (frequency === 'daily') return language === 'en' ? 'Daily' : '日线';
  if (frequency === 'weekly') return language === 'en' ? 'Weekly' : '周线';
  if (frequency === 'monthly') return language === 'en' ? 'Monthly' : '月线';
  return frequency || '--';
}

function formatExecutionTimingValue(value: unknown, language: BacktestLanguage): string {
  const text = String(value || '');
  if (text === 'bar_close') return language === 'en' ? 'Evaluate after close' : '收盘后判定';
  if (text === 'next_bar_open') return language === 'en' ? 'Fill at next-bar open' : '下一根开盘成交';
  if (text === 'session_open') return language === 'en' ? 'Execute at open' : '开盘执行';
  return text || '--';
}

function formatEndBehavior(spec: Record<string, unknown> | undefined, language: BacktestLanguage): string {
  const periodic = formatExitPolicyLabel(spec, language);
  if (periodic !== '--') return periodic;
  const policy = String(getStrategySpecValue(spec, ['end_behavior', 'policy']) || '');
  if (policy === 'liquidate_at_end') return language === 'en' ? 'Force close at the end of the window' : '区间结束强制平仓';
  return policy || (language === 'en' ? 'Force close at the end of the window' : '区间结束强制平仓');
}

export function buildRuleStrategySummaryRows(
  parsedStrategy: Pick<RuleBacktestParsedStrategy, 'strategyKind' | 'detectedStrategyFamily' | 'strategySpec' | 'setup' | 'summary'> | null | undefined,
  currentCode: string,
  startDate: string,
  endDate: string,
  topLevelDetectedStrategyFamily?: string | null,
  language: BacktestLanguage = 'zh',
): RuleStrategySummaryRow[] {
  if (!parsedStrategy) return [];

  const spec = parsedStrategy.strategySpec && typeof parsedStrategy.strategySpec === 'object'
    ? parsedStrategy.strategySpec
    : parsedStrategy.setup && typeof parsedStrategy.setup === 'object'
      ? parsedStrategy.setup
      : undefined;
  const strategyType = String(getStrategySpecValue(spec, ['strategy_type']) || parsedStrategy.strategyKind || '');

  if (strategyType === 'periodic_accumulation') {
    return [
      { key: 'strategy_family', label: language === 'en' ? 'Strategy family' : '策略族', value: getRuleStrategyTypeLabel(parsedStrategy, topLevelDetectedStrategyFamily, language) },
      { key: 'symbol', label: language === 'en' ? 'Ticker' : '标的', value: getPeriodicString(spec, 'symbol') || currentCode || '--' },
      { key: 'date_range', label: language === 'en' ? 'Date range' : '日期区间', value: `${getPeriodicString(spec, 'start_date') || startDate || '--'} -> ${getPeriodicString(spec, 'end_date') || endDate || '--'}` },
      { key: 'initial_capital', label: language === 'en' ? 'Initial capital' : '初始资金', value: formatNumber(getPeriodicNumber(spec, 'initial_capital')) },
      { key: 'frequency', label: language === 'en' ? 'Execution frequency' : '执行频率', value: formatFrequencyLabel(spec, parsedStrategy.strategyKind, language) },
      { key: 'entry', label: language === 'en' ? 'Positive signal rule' : '正向信号条件', value: backtestStrategyDisplayCopy(formatDraftOrderLabel(spec, language)) },
      { key: 'fill_timing', label: language === 'en' ? 'Fill timing' : '成交时点', value: formatExecutionPriceBasisLabel(spec, language) },
      { key: 'exit', label: language === 'en' ? 'Observation release rule' : '观察解除条件', value: backtestStrategyDisplayCopy(formatExitPolicyLabel(spec, language)) },
      { key: 'cash_policy', label: language === 'en' ? 'Cash policy' : '现金策略', value: formatCashPolicyLabel(spec, language) },
      { key: 'costs', label: language === 'en' ? 'Trading costs' : '交易成本', value: language === 'en' ? `Fee ${formatNumber(getPeriodicNumber(spec, 'fee_bps'), 0)} bp / Slippage ${formatNumber(getPeriodicNumber(spec, 'slippage_bps'), 0)} bp` : `手续费 ${formatNumber(getPeriodicNumber(spec, 'fee_bps'), 0)} bp / 滑点 ${formatNumber(getPeriodicNumber(spec, 'slippage_bps'), 0)} bp` },
    ];
  }

  if (strategyType === 'moving_average_crossover' || strategyType === 'macd_crossover' || strategyType === 'rsi_threshold') {
    return [
      { key: 'strategy_family', label: language === 'en' ? 'Strategy family' : '策略族', value: getRuleStrategyTypeLabel(parsedStrategy, topLevelDetectedStrategyFamily, language) },
      { key: 'symbol', label: language === 'en' ? 'Ticker' : '标的', value: String(getStrategySpecValue(spec, ['symbol']) || currentCode || '--') },
      { key: 'date_range', label: language === 'en' ? 'Date range' : '日期区间', value: `${String(getStrategySpecValue(spec, ['date_range', 'start_date']) || startDate || '--')} -> ${String(getStrategySpecValue(spec, ['date_range', 'end_date']) || endDate || '--')}` },
      { key: 'initial_capital', label: language === 'en' ? 'Initial capital' : '初始资金', value: formatNumber(Number(getStrategySpecValue(spec, ['capital', 'initial_capital']) || 0)) },
      { key: 'entry', label: language === 'en' ? 'Positive signal rule' : '正向信号条件', value: backtestStrategyDisplayCopy(formatStrategyCondition(spec, parsedStrategy, 'entry', language)) },
      { key: 'exit', label: language === 'en' ? 'Observation release rule' : '观察解除条件', value: backtestStrategyDisplayCopy(formatStrategyCondition(spec, parsedStrategy, 'exit', language)) },
      { key: 'frequency', label: language === 'en' ? 'Execution frequency' : '执行频率', value: formatExecutionFrequency(spec, language) },
      { key: 'signal_timing', label: language === 'en' ? 'Signal timing' : '信号时点', value: formatExecutionTimingValue(getStrategySpecValue(spec, ['execution', 'signal_timing']), language) },
      { key: 'fill_timing', label: language === 'en' ? 'Fill timing' : '成交时点', value: formatExecutionTimingValue(getStrategySpecValue(spec, ['execution', 'fill_timing']), language) },
      { key: 'end_behavior', label: language === 'en' ? 'End-of-window handling' : '期末处理', value: formatEndBehavior(spec, language) },
      { key: 'costs', label: language === 'en' ? 'Trading costs' : '交易成本', value: language === 'en' ? `Fee ${formatNumber(Number(getStrategySpecValue(spec, ['costs', 'fee_bps']) || 0), 0)} bp / Slippage ${formatNumber(Number(getStrategySpecValue(spec, ['costs', 'slippage_bps']) || 0), 0)} bp` : `手续费 ${formatNumber(Number(getStrategySpecValue(spec, ['costs', 'fee_bps']) || 0), 0)} bp / 滑点 ${formatNumber(Number(getStrategySpecValue(spec, ['costs', 'slippage_bps']) || 0), 0)} bp` },
    ];
  }

  return [
    { key: 'strategy_family', label: language === 'en' ? 'Strategy family' : '策略族', value: getRuleStrategyTypeLabel(parsedStrategy, topLevelDetectedStrategyFamily, language) },
    { key: 'symbol', label: language === 'en' ? 'Ticker' : '标的', value: currentCode || '--' },
    { key: 'entry', label: language === 'en' ? 'Positive signal rule' : '正向信号条件', value: backtestStrategyDisplayCopy(parsedStrategy.summary?.entry || '--') },
    { key: 'exit', label: language === 'en' ? 'Observation release rule' : '观察解除条件', value: backtestStrategyDisplayCopy(parsedStrategy.summary?.exit || '--') },
    { key: 'date_range', label: language === 'en' ? 'Date range' : '日期区间', value: `${startDate || '--'} -> ${endDate || '--'}` },
  ];
}
