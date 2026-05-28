import type React from 'react';
import { useMemo, useState } from 'react';
import type { BacktestDiagnosticWarning, RuleBacktestRunResponse, RuleBacktestTradeItem } from '../../types/backtest';
import { useI18n } from '../../contexts/UiLanguageContext';
import { EvidenceChips } from '../evidence/EvidenceChips';
import { StatusBadge } from '../ui/StatusBadge';
import { normalizeBacktestReadiness } from '../../utils/evidenceDisplay';
import {
  downloadExecutionTraceCsv,
  downloadExecutionTraceJson,
  hasExecutionTraceRows,
} from './executionTraceUtils';
import {
  formatDeterministicActionLabel,
  normalizeDeterministicBacktestResult,
  type DeterministicBacktestNormalizedResult,
  type DeterministicBacktestNormalizedRow,
} from './normalizeDeterministicBacktestResult';
import {
  formatDateTime,
  formatNumber,
  getRuleRunStatusLabel,
  pct,
} from './shared';
import { DeterministicBacktestResultView } from './DeterministicBacktestResultView';
import type { DeterministicResultDensityConfig } from './deterministicResultDensity';

export type BacktestResultReportMode = 'simple' | 'professional';

type MetricItem = {
  key: string;
  label: string;
  value: string;
  rawValue?: number | null;
  tone?: 'positive' | 'negative' | 'neutral';
};

type DiagnosisItem = {
  key: string;
  title: string;
  label: string;
  value: string;
  tone: MetricItem['tone'];
  note: string;
};

type TradeSummary = {
  totalTrades: number;
  winningTrades: number | null;
  losingTrades: number | null;
  winRatePct: number | null;
  avgTradeReturnPct: number | null;
  avgWinPct: number | null;
  avgLossPct: number | null;
  profitFactor: number | null;
  avgHoldingDays: number | null;
  bestTradePct: number | null;
  worstTradePct: number | null;
};

type BacktestResultReportProps = {
  run: RuleBacktestRunResponse;
  mode: BacktestResultReportMode;
  normalized?: DeterministicBacktestNormalizedResult;
  densityConfig?: DeterministicResultDensityConfig;
  chartNode?: React.ReactNode;
};

type ConsumerReliabilityItem = {
  key: string;
  label: string;
  value: string;
  note: string;
  tone: MetricItem['tone'];
};

const GHOST_SECTION_CLASS = 'rounded-xl border border-white/5 bg-white/[0.02] p-4 backdrop-blur-md transition-all hover:border-white/10 sm:p-5';
const LABEL_CLASS = 'text-[10px] font-bold uppercase tracking-widest text-white/40';
const VALUE_CLASS = 'font-mono text-sm text-white';
const POSITIVE_CLASS = 'text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.4)]';
const NEGATIVE_CLASS = 'text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.4)]';
const SECONDARY_BUTTON_CLASS = 'inline-flex min-h-[36px] items-center justify-center rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-white/70 transition-all hover:bg-white/10 md:min-h-[32px]';
const PRIMARY_BUTTON_CLASS = 'inline-flex min-h-[36px] items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.18)] transition-all hover:border-emerald-400/45 hover:bg-emerald-500/15 md:min-h-[32px]';
const TRADE_ROW_LIMIT = 20;
const LEDGER_ROW_LIMIT = 30;
const EVENT_ROW_LIMIT = 12;
const ATTRIBUTION_ROW_LIMIT = 6;

function safeNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function safeText(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function signedPct(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function signedNumber(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}`;
}

function toneFor(value?: number | null): 'positive' | 'negative' | 'neutral' {
  if (value == null || !Number.isFinite(value) || value === 0) return 'neutral';
  return value > 0 ? 'positive' : 'negative';
}

function displayDrawdown(value?: number | null): number | null {
  if (value == null || !Number.isFinite(value)) return null;
  return value > 0 ? -value : value;
}

function valueToneClass(tone?: MetricItem['tone']): string {
  if (tone === 'positive') return POSITIVE_CLASS;
  if (tone === 'negative') return NEGATIVE_CLASS;
  return 'text-white';
}

function renderValue(value: string, tone?: MetricItem['tone']) {
  return <span className={`${VALUE_CLASS} ${valueToneClass(tone)}`}>{value}</span>;
}

function average(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function getTradeReturn(trade: RuleBacktestTradeItem): number | null {
  return safeNumber(trade.returnPct);
}

function getTradeSummary(run: RuleBacktestRunResponse, trades: RuleBacktestTradeItem[]): TradeSummary {
  const returns = trades.map(getTradeReturn).filter((value): value is number => value != null);
  const wins = returns.filter((value) => value > 0);
  const losses = returns.filter((value) => value < 0);
  const winCount = safeNumber(run.winCount) ?? (returns.length ? wins.length : null);
  const lossCount = safeNumber(run.lossCount) ?? (returns.length ? losses.length : null);
  const grossWin = wins.reduce((total, value) => total + value, 0);
  const grossLossAbs = Math.abs(losses.reduce((total, value) => total + value, 0));
  return {
    totalTrades: Number(run.tradeCount ?? trades.length ?? 0),
    winningTrades: winCount,
    losingTrades: lossCount,
    winRatePct: safeNumber(run.winRatePct)
      ?? (returns.length ? (wins.length / returns.length) * 100 : null),
    avgTradeReturnPct: safeNumber(run.avgTradeReturnPct) ?? average(returns),
    avgWinPct: average(wins),
    avgLossPct: average(losses),
    profitFactor: grossLossAbs > 0 ? grossWin / grossLossAbs : null,
    avgHoldingDays: safeNumber(run.avgHoldingDays)
      ?? average(trades.map((trade) => safeNumber(trade.holdingDays)).filter((value): value is number => value != null)),
    bestTradePct: returns.length ? Math.max(...returns) : null,
    worstTradePct: returns.length ? Math.min(...returns) : null,
  };
}

function csvCell(value: unknown): string {
  const text = value == null || value === '' ? '--' : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function downloadCsv(filename: string, headers: string[], rows: unknown[][]): void {
  const content = [headers, ...rows].map((row) => row.map(csvCell).join(',')).join('\n');
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function recordValue(source: Record<string, unknown>, ...keys: string[]): unknown {
  for (const key of keys) {
    const value = source[key];
    if (value != null && value !== '') return value;
  }
  return null;
}

function displayToken(value: unknown): string {
  const text = typeof value === 'string' ? value.trim() : value == null ? '' : String(value);
  return text ? text.replaceAll('_', ' ') : 'unknown';
}

function compactToken(value: unknown): string {
  const text = displayToken(value);
  return text === 'unknown' ? '--' : text;
}

function humanToken(value: unknown): string {
  const raw = safeText(typeof value === 'string' ? value : value == null ? null : String(value));
  if (!raw) return '未提供';
  const normalized = raw.toLowerCase().replaceAll('-', '_').replace(/\s+/g, '_');
  const labels: Record<string, string> = {
    adjustment_status_unknown: '复权状态未知',
    market_rules_not_modeled: '涨跌停/停牌未建模',
    signal_entry: '信号入场',
    signal_exit: '信号离场',
    stop_loss: '止损离场',
    take_profit: '止盈离场',
    forced_close: '期末平仓',
    moving_average_crossover: '均线交叉',
    bar_close: '收盘信号',
    next_bar_open: '次日开盘',
    open: '开盘价',
    close: '收盘价',
    deterministic: '确定性引擎',
    fractional: '允许碎股',
    whole_shares: '整股',
    not_modeled: '未建模',
    disabled: '禁用',
    unknown: '未提供',
    local_us_parquet: '本地美股 Parquet',
    benchmark_security: '基准证券',
    daily: '日线',
    '1d': '日线',
  };
  return labels[normalized] || raw.replaceAll('_', ' ');
}

function holdingBucketLabel(bucket: string): string {
  if (bucket === '0-7d') return '0-7 天';
  if (bucket === '8-30d') return '8-30 天';
  if (bucket === '31-90d') return '31-90 天';
  if (bucket === '90d+') return '90 天以上';
  return '未提供';
}

function formatBps(value: unknown): string {
  const parsed = safeNumber(value);
  if (parsed == null) return '未提供';
  return Number.isInteger(parsed) ? String(parsed) : formatNumber(parsed, 2);
}

function warningText(warning: BacktestDiagnosticWarning | Record<string, unknown>): string {
  return safeText(warning.code) ? humanToken(warning.code) : safeText(warning.message) || '元数据提示';
}

function assumptionEntries(run: RuleBacktestRunResponse): Array<[string, string]> {
  const source = (run.executionAssumptions || {}) as Record<string, unknown>;
  const feeModel = (recordValue(source, 'feeModel', 'fee_model') || {}) as Record<string, unknown>;
  const slippageModel = (recordValue(source, 'slippageModel', 'slippage_model') || {}) as Record<string, unknown>;
  const structured: Array<[string, string | null]> = [
    ['执行引擎', safeText(recordValue(source, 'engine') as string) ? humanToken(recordValue(source, 'engine')) : null],
    ['信号 / 成交', `${humanToken(recordValue(source, 'signalTiming', 'signal_timing', 'signalEvaluationTiming', 'signal_evaluation_timing'))} -> ${humanToken(recordValue(source, 'fillTiming', 'fill_timing', 'entryFillTiming', 'entry_fill_timing'))}`],
    ['成交价假设', humanToken(recordValue(source, 'fillPrice', 'fill_price', 'defaultFillPriceBasis', 'default_fill_price_basis'))],
    ['手续费 / 滑点', `${formatBps(recordValue(feeModel, 'commissionBps', 'commission_bps') ?? run.feeBps)}bp / ${formatBps(recordValue(slippageModel, 'slippageBps', 'slippage_bps') ?? run.slippageBps)}bp`],
    ['成交单位', `${recordValue(source, 'allowFractionalShares', 'allow_fractional_shares') === false ? '整股' : '允许碎股'} / lot ${displayToken(recordValue(source, 'lotSize', 'lot_size') ?? 1)}`],
    ['成交量限制', humanToken(recordValue(source, 'volumeParticipationLimit', 'volume_participation_limit'))],
    ['市场规则', `${humanToken(recordValue(source, 'limitUpDownHandling', 'limit_up_down_handling'))} / ${humanToken(recordValue(source, 'haltHandling', 'halt_handling'))}`],
    ['做空规则', humanToken(recordValue(source, 'shortSelling', 'short_selling'))],
  ];
  const hasStructured = Boolean(recordValue(source, 'engine', 'feeModel', 'fee_model', 'slippageModel', 'slippage_model'));
  if (hasStructured) {
    return structured
      .filter(([, value]) => value != null && value !== '')
      .map(([key, value]) => [key, String(value)]);
  }

  const explicit = Object.entries(source)
    .map(([key, value]): [string, string] | null => {
      if (value == null || value === '') return null;
      return [humanToken(key), typeof value === 'object' ? JSON.stringify(value) : humanToken(value)];
    })
    .filter((entry): entry is [string, string] => entry != null);
  if (explicit.length) return explicit;

  const inferred: Array<[string, string | number | null | undefined]> = [
    ['周期', run.timeframe],
    ['单边手续费', run.feeBps],
    ['单边滑点', run.slippageBps],
  ];
  return inferred
    .filter(([, value]) => value != null && value !== '')
    .map(([key, value]) => [key, String(value)]);
}

function dataQualityEntries(run: RuleBacktestRunResponse, normalized: DeterministicBacktestNormalizedResult): Array<[string, string]> {
  const explicit = run.dataQuality;
  if (explicit && Object.keys(explicit).length > 0) {
    const barCount = safeNumber(explicit.barCount);
    const expected = safeNumber(explicit.expectedBarCount);
    const warnings = Array.isArray(explicit.warnings) ? explicit.warnings.length : 0;
    const entries: Array<[string, string | number | null]> = [
      ['价格源', humanToken(explicit.provider || explicit.source)],
      ['样本频率', humanToken(explicit.frequency)],
      ['样本覆盖', `${barCount ?? '--'} / ${expected ?? '--'}`],
      ['实际区间', explicit.actualStart || explicit.actualEnd ? `${explicit.actualStart || '--'} -> ${explicit.actualEnd || '--'}` : null],
      ['复权 / 分红 / 拆股', `${humanToken(explicit.adjustmentMode)} / ${humanToken(explicit.dividendsHandled)} / ${humanToken(explicit.splitsHandled)}`],
      ['缺失交易日', safeNumber(explicit.missingBarCount) ?? 0],
      ['质量提示', warnings],
    ];
    return entries
      .filter(([, value]) => value != null && value !== '')
      .map(([key, value]) => [key, String(value)]);
  }

  const benchmark = run.benchmarkSummary || {};
  const source = safeText(run.executionTrace?.source) || safeText(benchmark.method);
  if (!source && normalized.viewerMeta.rowCount === 0) return [];
  const frequency = safeText(run.timeframe);
  const priceBasis = safeText(benchmark.priceBasis);
  const timezone = safeText((run.summary || {}).timezone);
  const missingBars = safeNumber((run.summary || {}).missingBars);
  const anomalousBars = safeNumber((run.summary || {}).anomalousBars);
  const entries: Array<[string, string | number | null]> = [
    ['数据源', source],
    ['频率', frequency],
    ['复权状态', priceBasis],
    ['缺失 bars', missingBars],
    ['异常 bars', anomalousBars],
    ['时区', timezone],
    ['实际区间', normalized.viewerMeta.firstDate && normalized.viewerMeta.lastDate
      ? `${normalized.viewerMeta.firstDate} -> ${normalized.viewerMeta.lastDate}`
      : null],
  ];
  return entries
    .filter(([, value]) => value != null && value !== '')
    .map(([key, value]) => [key, String(value)]);
}

function getBenchmarkVerdict(totalReturnPct: number | null, benchmarkReturnPct: number | null, excessReturnPct: number | null): { label: string; tone: MetricItem['tone']; note: string } {
  if (benchmarkReturnPct == null || totalReturnPct == null || excessReturnPct == null) {
    return { label: '基准缺失', tone: 'neutral', note: '暂无基准数据；不影响策略自身回测结果。' };
  }
  if (excessReturnPct >= 5) return { label: '明显跑赢', tone: 'positive', note: `策略相对基准多获得 ${signedPct(excessReturnPct)}。` };
  if (excessReturnPct > 1) return { label: '小幅跑赢', tone: 'positive', note: `策略相对基准多获得 ${signedPct(excessReturnPct)}。` };
  if (excessReturnPct >= -1) return { label: '接近基准', tone: 'neutral', note: `策略与基准差距 ${signedPct(excessReturnPct)}。` };
  return { label: '弱于基准', tone: 'negative', note: `策略相对基准落后 ${signedPct(Math.abs(excessReturnPct))}。` };
}

function getBenchmarkSentence(normalized: DeterministicBacktestNormalizedResult): string {
  const { totalReturnPct, benchmarkReturnPct, excessReturnVsBenchmarkPct, maxDrawdownPct } = normalized.metrics;
  const verdict = getBenchmarkVerdict(totalReturnPct, benchmarkReturnPct, excessReturnVsBenchmarkPct);
  if (verdict.label === '基准缺失') return verdict.note;
  const parts = [
    `策略 ${signedPct(totalReturnPct)}`,
    `基准 ${signedPct(benchmarkReturnPct)}`,
    `超额 ${signedPct(excessReturnVsBenchmarkPct)}`,
  ];
  if (maxDrawdownPct != null) parts.push(`策略最大回撤 ${signedPct(displayDrawdown(maxDrawdownPct))}`);
  return `${verdict.label}：${parts.join(' · ')}。`;
}

function getDiagnosisItems(
  normalized: DeterministicBacktestNormalizedResult,
  tradeSummary: TradeSummary,
  dataQualityWarnings: string[],
  executionWarnings: string[],
  hasExplicitAssumptions: boolean,
): DiagnosisItem[] {
  const metrics = normalized.metrics;
  const benchmarkVerdict = getBenchmarkVerdict(metrics.totalReturnPct, metrics.benchmarkReturnPct, metrics.excessReturnVsBenchmarkPct);
  const drawdownAbs = metrics.maxDrawdownPct == null ? null : Math.abs(metrics.maxDrawdownPct);
  const rowCount = normalized.viewerMeta.rowCount;
  const tradeCount = tradeSummary.totalTrades;
  const returnLabel = metrics.totalReturnPct == null
    ? '收益未提供'
    : metrics.benchmarkReturnPct == null
      ? (metrics.totalReturnPct >= 0 ? '策略收益为正' : '策略收益为负')
      : benchmarkVerdict.label === '弱于基准'
        ? '弱于基准'
        : benchmarkVerdict.label === '基准缺失'
          ? '基准缺失'
          : '跑赢基准';
  const riskLabel = drawdownAbs == null
    ? '回撤未提供'
    : drawdownAbs >= 20
      ? '回撤偏高'
      : drawdownAbs >= 10
        ? '回撤需跟踪'
        : '回撤受控';
  const tradeLabel = tradeCount < 5
    ? '交易样本偏少'
    : tradeSummary.winRatePct == null
      ? '胜率未提供'
      : tradeSummary.winRatePct < 45
        ? '胜率偏低'
        : '交易效率正常';
  const sharpeLabel = metrics.sharpeRatio == null
    ? '夏普未提供'
    : metrics.sharpeRatio >= 1
      ? '夏普稳健'
      : metrics.sharpeRatio >= 0
        ? '夏普通常'
        : '夏普承压';
  const dataLabel = dataQualityWarnings.length || rowCount < 30 ? '数据样本有限' : '数据覆盖正常';
  const executionLabel = executionWarnings.length || !hasExplicitAssumptions ? '执行假设需谨慎' : '执行假设完整';
  return [
    {
      key: 'return',
      title: '收益质量',
      label: returnLabel,
      value: signedPct(metrics.totalReturnPct),
      tone: metrics.totalReturnPct == null ? 'neutral' : benchmarkVerdict.tone,
      note: sharpeLabel,
    },
    {
      key: 'risk',
      title: '风险压力',
      label: riskLabel,
      value: signedPct(displayDrawdown(metrics.maxDrawdownPct)),
      tone: drawdownAbs == null ? 'neutral' : drawdownAbs >= 10 ? 'negative' : 'positive',
      note: '最大回撤',
    },
    {
      key: 'trade',
      title: '交易效率',
      label: tradeLabel,
      value: `${tradeCount} 笔`,
      tone: tradeCount < 5 || (tradeSummary.winRatePct != null && tradeSummary.winRatePct < 45) ? 'negative' : 'neutral',
      note: `胜率 ${signedPct(tradeSummary.winRatePct)}`,
    },
    {
      key: 'data',
      title: '数据可信度',
      label: dataLabel,
      value: `${rowCount} 行`,
      tone: dataQualityWarnings.length ? 'negative' : 'neutral',
      note: dataQualityWarnings.length ? `${dataQualityWarnings.length} 条提示` : '样本覆盖',
    },
    {
      key: 'execution',
      title: '执行口径',
      label: executionLabel,
      value: executionWarnings.length ? `${executionWarnings.length} 条提示` : '已披露',
      tone: executionWarnings.length || !hasExplicitAssumptions ? 'negative' : 'neutral',
      note: '非真实成交记录',
    },
  ];
}

function getMetricItems(normalized: DeterministicBacktestNormalizedResult): MetricItem[] {
  const metrics = normalized.metrics;
  return [
    { key: 'total', label: '总收益', value: signedPct(metrics.totalReturnPct), rawValue: metrics.totalReturnPct, tone: toneFor(metrics.totalReturnPct) },
    { key: 'benchmark', label: '基准收益', value: signedPct(metrics.benchmarkReturnPct), rawValue: metrics.benchmarkReturnPct, tone: toneFor(metrics.benchmarkReturnPct) },
    { key: 'excess', label: '超额收益', value: signedPct(metrics.excessReturnVsBenchmarkPct), rawValue: metrics.excessReturnVsBenchmarkPct, tone: toneFor(metrics.excessReturnVsBenchmarkPct) },
    { key: 'drawdown', label: '最大回撤', value: signedPct(displayDrawdown(metrics.maxDrawdownPct)), rawValue: metrics.maxDrawdownPct, tone: 'negative' },
    { key: 'cagr', label: 'CAGR', value: signedPct(metrics.annualizedReturnPct), rawValue: metrics.annualizedReturnPct, tone: toneFor(metrics.annualizedReturnPct) },
    { key: 'sharpe', label: '夏普', value: signedNumber(metrics.sharpeRatio), rawValue: metrics.sharpeRatio, tone: toneFor(metrics.sharpeRatio) },
    { key: 'winRate', label: '胜率', value: signedPct(metrics.winRatePct), rawValue: metrics.winRatePct, tone: toneFor(metrics.winRatePct) },
    { key: 'trades', label: '交易次数', value: String(metrics.tradeCount ?? 0), rawValue: metrics.tradeCount, tone: 'neutral' },
  ];
}

function getMoreMetricItems(run: RuleBacktestRunResponse, summary: TradeSummary): MetricItem[] {
  const lookup = run.summary || {};
  const items: Array<[string, string, number | null]> = [
    ['sortino', 'Sortino', safeNumber(lookup.sortino ?? lookup.sortinoRatio)],
    ['calmar', 'Calmar', safeNumber(lookup.calmar ?? lookup.calmarRatio)],
    ['volatility', '波动率', safeNumber(lookup.volatilityPct ?? lookup.volatility)],
    ['profitFactor', '盈亏比', summary.profitFactor],
    ['avgHolding', '平均持有天数', summary.avgHoldingDays],
    ['avgWin', '平均盈利', summary.avgWinPct],
    ['avgLoss', '平均亏损', summary.avgLossPct],
    ['maxLosses', '最大连亏', safeNumber(lookup.maxConsecutiveLosses)],
    ['maxWins', '最大连赢', safeNumber(lookup.maxConsecutiveWins)],
    ['alpha', 'Alpha', safeNumber(lookup.alpha)],
    ['beta', 'Beta', safeNumber(lookup.beta)],
    ['info', '信息比率', safeNumber(lookup.informationRatio)],
    ['tracking', '跟踪误差', safeNumber(lookup.trackingError)],
  ];
  return items.map(([key, label, value]) => ({
    key,
    label,
    value: key === 'profitFactor' || key === 'avgHolding' || key === 'beta' || key === 'info'
      ? signedNumber(value)
      : signedPct(value),
    rawValue: value,
    tone: toneFor(value),
  }));
}

type AttributionRow = {
  key: string;
  trades: number;
  netPnl: number | null;
  returnPct: number | null;
};

type EventRow = {
  date: string;
  type: 'ENTRY' | 'EXIT';
  label: string;
  tone: 'positive' | 'negative' | 'neutral';
};

function tradeNetPnl(trade: RuleBacktestTradeItem): number | null {
  const explicit = safeNumber(trade.netPnl);
  if (explicit != null) return explicit;
  const quantity = safeNumber(trade.quantity);
  const entry = safeNumber(trade.entryPrice);
  const exit = safeNumber(trade.exitPrice);
  if (quantity == null || entry == null || exit == null) return null;
  return (exit - entry) * quantity - (safeNumber(trade.fees) ?? 0);
}

function tradeFees(trade: RuleBacktestTradeItem): number | null {
  return safeNumber(trade.fees) ?? (
    safeNumber(trade.entryFeeAmount) != null || safeNumber(trade.exitFeeAmount) != null
      ? (safeNumber(trade.entryFeeAmount) ?? 0) + (safeNumber(trade.exitFeeAmount) ?? 0)
      : null
  );
}

function tradeSlippage(trade: RuleBacktestTradeItem): number | null {
  return safeNumber(trade.slippage) ?? (
    safeNumber(trade.entrySlippageAmount) != null || safeNumber(trade.exitSlippageAmount) != null
      ? (safeNumber(trade.entrySlippageAmount) ?? 0) + (safeNumber(trade.exitSlippageAmount) ?? 0)
      : null
  );
}

function holdingBucket(days: number | null): string {
  if (days == null) return 'unknown';
  if (days <= 7) return '0-7d';
  if (days <= 30) return '8-30d';
  if (days <= 90) return '31-90d';
  return '90d+';
}

function getTradeMonth(trade: RuleBacktestTradeItem): string {
  return safeText(trade.exitDate)?.slice(0, 7) || safeText(trade.entryDate)?.slice(0, 7) || 'unknown';
}

function getTradeYear(trade: RuleBacktestTradeItem): string {
  return safeText(trade.exitDate)?.slice(0, 4) || safeText(trade.entryDate)?.slice(0, 4) || 'unknown';
}

function buildAttribution(
  trades: RuleBacktestTradeItem[],
  keyFor: (trade: RuleBacktestTradeItem) => string,
): AttributionRow[] {
  const groups = new Map<string, RuleBacktestTradeItem[]>();
  trades.forEach((trade) => {
    const key = keyFor(trade);
    groups.set(key, [...(groups.get(key) || []), trade]);
  });
  return Array.from(groups.entries()).map(([key, group]) => {
    const returns = group.map(getTradeReturn).filter((value): value is number => value != null);
    const pnls = group.map(tradeNetPnl).filter((value): value is number => value != null);
    return {
      key,
      trades: group.length,
      netPnl: pnls.length ? pnls.reduce((total, value) => total + value, 0) : null,
      returnPct: average(returns),
    };
  }).sort((a, b) => {
    const aPnl = a.netPnl ?? a.returnPct ?? 0;
    const bPnl = b.netPnl ?? b.returnPct ?? 0;
    return Math.abs(bPnl) - Math.abs(aPnl);
  }).slice(0, ATTRIBUTION_ROW_LIMIT);
}

function buildEvents(trades: RuleBacktestTradeItem[]): EventRow[] {
  return trades.flatMap((trade) => {
    const events: EventRow[] = [];
    if (trade.entryDate) {
      events.push({
        date: trade.entryDate,
        type: 'ENTRY',
        label: humanToken(trade.entryReason || trade.entrySignal || trade.entryTrigger),
        tone: 'neutral',
      });
    }
    if (trade.exitDate) {
      events.push({
        date: trade.exitDate,
        type: 'EXIT',
        label: humanToken(trade.exitReason || trade.exitSignal || trade.exitTrigger),
        tone: toneFor(getTradeReturn(trade)),
      });
    }
    return events;
  }).sort((a, b) => a.date.localeCompare(b.date)).slice(0, EVENT_ROW_LIMIT);
}

function maxStreak(trades: RuleBacktestTradeItem[], predicate: (value: number) => boolean): number {
  let best = 0;
  let current = 0;
  trades.forEach((trade) => {
    const value = getTradeReturn(trade);
    if (value != null && predicate(value)) {
      current += 1;
      best = Math.max(best, current);
    } else {
      current = 0;
    }
  });
  return best;
}

function sumNullable(values: Array<number | null>): number | null {
  const numbers = values.filter((value): value is number => value != null);
  if (!numbers.length) return null;
  return numbers.reduce((total, value) => total + value, 0);
}

function drawdownPeriod(rows: DeterministicBacktestNormalizedRow[]): { start: string | null; trough: string | null; recovery: string | null; value: number | null } {
  let peakDate: string | null = null;
  let currentPeakDate: string | null = null;
  let trough: string | null = null;
  let recovery: string | null = null;
  let minDrawdown = 0;
  rows.forEach((row) => {
    const drawdown = safeNumber(row.drawdownPct) ?? 0;
    if (drawdown === 0) {
      currentPeakDate = row.date;
      if (trough && !recovery) recovery = row.date;
    }
    if (drawdown < minDrawdown) {
      minDrawdown = drawdown;
      peakDate = currentPeakDate;
      trough = row.date;
      recovery = null;
    }
  });
  return { start: peakDate, trough, recovery, value: minDrawdown || null };
}

function AttributionList({ rows, testId, formatKey = compactToken }: { rows: AttributionRow[]; testId: string; formatKey?: (key: string) => string }) {
  return (
    <div data-testid={testId} className="min-w-0 rounded-xl border border-white/5 bg-black/20 p-3">
      <div className="space-y-2">
        {rows.length ? rows.map((row) => {
          const contribution = row.netPnl != null ? signedNumber(row.netPnl) : signedPct(row.returnPct);
          return (
            <div key={row.key} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 text-xs">
              <span className="truncate text-white/62">{formatKey(row.key)}</span>
              <span className={`font-mono ${valueToneClass(toneFor(row.netPnl ?? row.returnPct))}`}>{contribution}</span>
              <span className="font-mono text-white/42">{row.trades}x</span>
            </div>
          );
        }) : <p className="text-xs text-white/42">--</p>}
      </div>
    </div>
  );
}

function MetricCard({ item }: { item: MetricItem }) {
  return (
    <div className="min-w-0 rounded-xl border border-white/5 bg-black/20 p-3">
      <p className={LABEL_CLASS}>{item.label}</p>
      <p className="mt-2 truncate">{renderValue(item.value, item.tone)}</p>
    </div>
  );
}

function DiagnosisCard({ item }: { item: DiagnosisItem }) {
  return (
    <div className="min-w-0 rounded-xl border border-white/5 bg-black/20 p-3" data-testid={`backtest-diagnosis-${item.key}`}>
      <div className="flex min-w-0 items-center justify-between gap-2">
        <p className={LABEL_CLASS}>{item.title}</p>
        <span className={`max-w-[60%] truncate rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] ${valueToneClass(item.tone)}`}>
          {item.label}
        </span>
      </div>
      <p className="mt-2 truncate font-mono text-sm text-white">{item.value}</p>
      <p className="mt-1 truncate text-xs text-white/42">{item.note}</p>
    </div>
  );
}

function getConsumerReliabilityItems({
  run,
  readinessSummary,
  hasExplicitTraceRows,
  hasExplicitAssumptions,
  hasDataQualityEntries,
  dataQualityWarnings,
  executionWarnings,
}: {
  run: RuleBacktestRunResponse;
  readinessSummary: ReturnType<typeof normalizeBacktestReadiness>;
  hasExplicitTraceRows: boolean;
  hasExplicitAssumptions: boolean;
  hasDataQualityEntries: boolean;
  dataQualityWarnings: string[];
  executionWarnings: string[];
}): ConsumerReliabilityItem[] {
  const isCompleted = run.status === 'completed';
  const isRunning = run.status === 'queued'
    || run.status === 'parsing'
    || run.status === 'running'
    || run.status === 'summarizing';
  const supportIncomplete = !hasExplicitTraceRows || !hasExplicitAssumptions || !hasDataQualityEntries;
  const limitedConfidence = readinessSummary.posture !== 'unknown'
    || readinessSummary.confidenceCap != null
    || readinessSummary.limitationLabels.length > 0
    || dataQualityWarnings.length > 0
    || executionWarnings.length > 0;

  return [
    {
      key: 'availability',
      label: '结果可用性',
      value: isCompleted ? '可查看' : isRunning ? '生成中' : '暂不可用',
      tone: isCompleted ? 'positive' : isRunning ? 'neutral' : 'negative',
      note: isCompleted ? '本次回测结果可查看。' : isRunning ? '结果生成中，请稍后刷新。' : '当前回测结果暂不可查看。',
    },
    {
      key: 'reproducibility',
      label: '复现状态',
      value: supportIncomplete ? '部分可用' : '可复查',
      tone: supportIncomplete ? 'neutral' : 'positive',
      note: supportIncomplete ? '本次回测结果可查看，但部分复现材料不完整。' : '复现材料已就绪，可按需展开复查。',
    },
    {
      key: 'freshness',
      label: '辅助证据',
      value: supportIncomplete ? '部分可用' : '可查看',
      tone: supportIncomplete ? 'neutral' : 'positive',
      note: supportIncomplete ? '部分辅助证据暂不可用，不影响历史收益曲线展示。' : '辅助证据可按需展开复查。',
    },
    {
      key: 'confidence',
      label: '结果置信度',
      value: limitedConfidence ? '有限置信' : '正常评估',
      tone: limitedConfidence ? 'neutral' : 'positive',
      note: limitedConfidence ? '回测数据质量有限，结果仅供评估。' : '当前结果可用于历史表现评估。',
    },
  ];
}

function ConsumerReliabilityCard({ item }: { item: ConsumerReliabilityItem }) {
  return (
    <div className="min-w-0 rounded-xl border border-white/5 bg-black/20 p-3" data-testid={`backtest-consumer-reliability-${item.key}`}>
      <div className="flex min-w-0 items-center justify-between gap-2">
        <p className={LABEL_CLASS}>{item.label}</p>
        <span className={`max-w-[58%] truncate rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] ${valueToneClass(item.tone)}`}>
          {item.value}
        </span>
      </div>
      <p className="mt-2 text-xs leading-5 text-white/58">{item.note}</p>
    </div>
  );
}

const BacktestResultReport: React.FC<BacktestResultReportProps> = ({
  run,
  mode,
  normalized: providedNormalized,
  densityConfig,
  chartNode,
}) => {
  const { language } = useI18n();
  const [moreMetricsOpen, setMoreMetricsOpen] = useState(mode === 'professional');
  const [dataQualityOpen, setDataQualityOpen] = useState(false);
  const [assumptionsOpen, setAssumptionsOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [ledgerOpen, setLedgerOpen] = useState(false);
  const [activeDetailTab, setActiveDetailTab] = useState<'trades' | 'risk' | 'params' | 'diagnostics'>('trades');
  const normalized = useMemo(
    () => providedNormalized ?? normalizeDeterministicBacktestResult(run, language),
    [language, providedNormalized, run],
  );
  const trades = useMemo(() => (Array.isArray(run.trades) ? run.trades : []), [run.trades]);
  const tradeSummary = useMemo(() => getTradeSummary(run, trades), [run, trades]);
  const attributionByMonth = useMemo(() => buildAttribution(trades, getTradeMonth), [trades]);
  const attributionByYear = useMemo(() => buildAttribution(trades, getTradeYear), [trades]);
  const attributionByExitReason = useMemo(() => buildAttribution(trades, (trade) => compactToken(trade.exitReason || trade.exitTrigger || trade.exitSignal)), [trades]);
  const attributionByHoldingBucket = useMemo(() => buildAttribution(trades, (trade) => holdingBucket(safeNumber(trade.holdingDays ?? trade.holdingCalendarDays ?? trade.holdingBars))), [trades]);
  const tradeEvents = useMemo(() => buildEvents(trades), [trades]);
  const grossPnlTotal = sumNullable(trades.map((trade) => safeNumber(trade.grossPnl)));
  const netPnlTotal = sumNullable(trades.map(tradeNetPnl));
  const feesTotal = sumNullable(trades.map(tradeFees));
  const slippageTotal = sumNullable(trades.map(tradeSlippage));
  const drawdown = drawdownPeriod(normalized.rows);
  const bestTrade = trades.reduce<RuleBacktestTradeItem | null>((best, trade) => {
    const value = getTradeReturn(trade);
    const bestValue = best ? getTradeReturn(best) : null;
    return value != null && (bestValue == null || value > bestValue) ? trade : best;
  }, null);
  const worstTrade = trades.reduce<RuleBacktestTradeItem | null>((worst, trade) => {
    const value = getTradeReturn(trade);
    const worstValue = worst ? getTradeReturn(worst) : null;
    return value != null && (worstValue == null || value < worstValue) ? trade : worst;
  }, null);
  const consecutiveWins = maxStreak(trades, (value) => value > 0);
  const consecutiveLosses = maxStreak(trades, (value) => value < 0);
  const metrics = useMemo(() => getMetricItems(normalized), [normalized]);
  const moreMetrics = useMemo(() => getMoreMetricItems(run, tradeSummary), [run, tradeSummary]);
  const dataQuality = useMemo(() => dataQualityEntries(run, normalized), [run, normalized]);
  const assumptions = assumptionEntries(run);
  const dataQualityWarnings = (run.dataQuality?.warnings || []).map(warningText);
  const executionWarnings = useMemo(() => {
    const assumptionsPayload = (run.executionAssumptions || {}) as Record<string, unknown>;
    const executionWarningItems = recordValue(assumptionsPayload, 'warnings') as Array<Record<string, unknown>> | null;
    return Array.isArray(executionWarningItems) ? executionWarningItems.map(warningText) : [];
  }, [run.executionAssumptions]);
  const hasExplicitAssumptions = Object.keys(run.executionAssumptions || {}).length > 0;
  const diagnosisItems = useMemo(
    () => getDiagnosisItems(normalized, tradeSummary, dataQualityWarnings, executionWarnings, hasExplicitAssumptions),
    [dataQualityWarnings, executionWarnings, hasExplicitAssumptions, normalized, tradeSummary],
  );
  const benchmarkVerdict = getBenchmarkVerdict(
    normalized.metrics.totalReturnPct,
    normalized.metrics.benchmarkReturnPct,
    normalized.metrics.excessReturnVsBenchmarkPct,
  );
  const volatilityPct = safeNumber(run.summary?.volatilityPct ?? run.summary?.volatility);
  const worstDailyReturn = (() => {
    const values = normalized.rows
      .map((row) => row.dailyReturn)
      .filter((value): value is number => value != null && Number.isFinite(value));
    return values.length ? Math.min(...values) : null;
  })();
  const visibleTrades = trades.slice(0, TRADE_ROW_LIMIT);
  const visibleLedgerRows = normalized.rows.slice(0, LEDGER_ROW_LIMIT);
  const statusLabel = getRuleRunStatusLabel(run.status, language);
  const statusWord = run.status === 'completed' ? '回测完成' : statusLabel;
  const firstDate = normalized.viewerMeta.firstDate || run.startDate || run.periodStart || null;
  const lastDate = normalized.viewerMeta.lastDate || run.endDate || run.periodEnd || null;
  const dateRange = firstDate || lastDate ? `${firstDate || '--'} -> ${lastDate || '--'}` : '--';
  const readinessSummary = useMemo(
    () => normalizeBacktestReadiness(run, { maxLimitationLabels: 5 }),
    [run],
  );
  const showReadinessChips = readinessSummary.posture !== 'unknown'
    || readinessSummary.confidenceCap != null
    || readinessSummary.limitationLabels.length > 0
    || readinessSummary.freshnessLabel != null;
  const hasTraceRows = hasExecutionTraceRows(run);
  const hasExplicitTraceRows = Array.isArray(run.executionTrace?.rows) && run.executionTrace.rows.length > 0;
  const consumerReliabilityItems = useMemo(
    () => getConsumerReliabilityItems({
      run,
      readinessSummary,
      hasExplicitTraceRows,
      hasExplicitAssumptions,
      hasDataQualityEntries: dataQuality.length > 0,
      dataQualityWarnings,
      executionWarnings,
    }),
    [dataQuality.length, dataQualityWarnings, executionWarnings, hasExplicitAssumptions, hasExplicitTraceRows, readinessSummary, run],
  );

  const exportTrades = () => {
    downloadCsv(
      `backtest_trades_${run.id}.csv`,
      ['Entry Date', 'Exit Date', 'Symbol', 'Quantity', 'Entry Price', 'Exit Price', 'Gross PnL', 'Net PnL', 'Return %', 'Fees', 'Slippage', 'Holding Days', 'Exit Reason', 'Signal Reason'],
      trades.map((trade) => [
        trade.entryDate,
        trade.exitDate,
        trade.code || run.code,
        trade.quantity,
        trade.entryPrice,
        trade.exitPrice,
        trade.grossPnl,
        tradeNetPnl(trade),
        trade.returnPct,
        tradeFees(trade),
        tradeSlippage(trade),
        trade.holdingDays ?? trade.holdingCalendarDays ?? trade.holdingBars,
        trade.exitReason ?? trade.exitTrigger ?? trade.exitSignal,
        trade.signalReason ?? trade.entrySignal ?? trade.entryTrigger,
      ]),
    );
  };

  const exportLedger = () => {
    downloadCsv(
      `backtest_daily_ledger_${run.id}.csv`,
      ['Date', 'Action', 'Close', 'Benchmark Close', 'Fill Price', 'Shares', 'Cash', 'Total Value', 'Daily PnL', 'Daily Return %', 'Strategy Return %'],
      normalized.rows.map((row) => [
        row.date,
        row.action,
        row.symbolClose,
        row.benchmarkClose,
        row.fillPrice,
        row.shares,
        row.cash,
        row.totalValue,
        row.dailyPnl,
        row.dailyReturn,
        row.strategyCumReturn,
      ]),
    );
  };
  const detailTabs = [
    { key: 'trades' as const, label: '交易明细' },
    { key: 'risk' as const, label: '风险分析' },
    { key: 'params' as const, label: '参数' },
    { key: 'diagnostics' as const, label: '可靠性' },
  ];

  return (
    <section
      className="backtest-display-section"
      data-testid="backtest-result-report"
      data-report-mode={mode}
    >
      <div className="flex min-w-0 flex-col gap-4 text-sm text-white/70">
        <nav className="no-scrollbar flex min-w-0 gap-2 overflow-x-auto pb-1 [scrollbar-width:none]" aria-label="Backtest result sections">
          {[
            { id: '概览', label: '概览' },
            { id: '曲线', label: '曲线' },
            { id: '交易', label: '交易' },
            { id: '归因', label: '归因' },
            { id: '风险', label: '风险' },
            { id: '证据', label: '复查' },
          ].map((item) => (
            <a key={item.id} href={`#backtest-report-${item.id}`} className="inline-flex min-h-[36px] shrink-0 items-center rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/60 hover:bg-white/10 md:min-h-[32px] md:py-1.5">
              {item.label}
            </a>
          ))}
        </nav>

        <div id="backtest-report-概览" data-testid="backtest-report-summary" className={`${GHOST_SECTION_CLASS} overflow-hidden`}>
          <div className="flex min-w-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <div className="truncate text-base font-semibold text-white">{run.code || '--'} · {statusWord}</div>
                <StatusBadge status={run.status} label={statusLabel} size="sm" variant="soft" />
                <span className="font-mono text-xs text-white/38">{dateRange}</span>
              </div>
              <div className="mt-3 flex min-w-0 flex-wrap gap-x-4 gap-y-2 text-xs text-white/58">
                <span>总收益 {renderValue(signedPct(normalized.metrics.totalReturnPct), toneFor(normalized.metrics.totalReturnPct))}</span>
                <span>基准 {renderValue(signedPct(normalized.metrics.benchmarkReturnPct), toneFor(normalized.metrics.benchmarkReturnPct))}</span>
                <span>超额 {renderValue(signedPct(normalized.metrics.excessReturnVsBenchmarkPct), toneFor(normalized.metrics.excessReturnVsBenchmarkPct))}</span>
              </div>
              <div className="mt-2 flex min-w-0 flex-wrap gap-x-4 gap-y-2 text-xs text-white/50">
                <span>最大回撤 {renderValue(signedPct(displayDrawdown(normalized.metrics.maxDrawdownPct)), 'negative')}</span>
                <span>夏普 {renderValue(signedNumber(normalized.metrics.sharpeRatio), toneFor(normalized.metrics.sharpeRatio))}</span>
                <span>胜率 {renderValue(signedPct(normalized.metrics.winRatePct), toneFor(normalized.metrics.winRatePct))}</span>
                <span>交易次数 <span className="font-mono text-white">{normalized.metrics.tradeCount}</span></span>
              </div>
            </div>
            <div className="font-mono text-xs text-white/38">{formatDateTime(run.completedAt || run.runAt)}</div>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4" data-testid="backtest-consumer-reliability-strip">
            {consumerReliabilityItems.map((item) => <ConsumerReliabilityCard key={item.key} item={item} />)}
          </div>
          {showReadinessChips ? (
            <div className="mt-4 flex flex-col gap-2" data-testid="backtest-readiness-strip">
              <div className={LABEL_CLASS}>结果置信度</div>
              <EvidenceChips
                summary={readinessSummary}
                maxLabels={5}
                data-testid="backtest-readiness-chips"
              />
            </div>
          ) : null}
          <div data-testid="backtest-report-result-summary" className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <MetricCard item={{ key: 'summary-return', label: '总收益', value: signedPct(normalized.metrics.totalReturnPct), tone: toneFor(normalized.metrics.totalReturnPct) }} />
            <MetricCard item={{ key: 'summary-risk', label: '最大回撤', value: signedPct(displayDrawdown(normalized.metrics.maxDrawdownPct)), tone: 'negative' }} />
            <MetricCard item={{ key: 'summary-win-rate', label: '胜率', value: signedPct(normalized.metrics.winRatePct), tone: toneFor(normalized.metrics.winRatePct) }} />
            <MetricCard item={{ key: 'summary-trades', label: '交易次数', value: `${normalized.metrics.tradeCount ?? 0} 次`, tone: 'neutral' }} />
            <MetricCard item={{ key: 'summary-data', label: '可靠性', value: dataQuality.length ? `${dataQuality.length} 项` : '待补充', tone: dataQuality.length ? 'positive' : 'neutral' }} />
            <div className="col-span-2 rounded-xl border border-white/5 bg-black/20 p-3 text-xs leading-5 text-white/50 lg:col-span-4">
              <span className={LABEL_CLASS}>研究结论</span>
              <span className="ml-2">先读总收益、最大回撤、胜率、交易次数与可靠性；曲线和风险解释跟随结论，复查材料默认折叠。</span>
            </div>
          </div>
          <div className="mt-4" data-testid="backtest-report-diagnosis">
            <div className="mb-2 flex min-w-0 flex-wrap items-center justify-between gap-2">
              <p className={LABEL_CLASS}>策略解读</p>
              <span className="text-xs text-white/42">基于收益、风险、交易和数据完整度生成</span>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
              {diagnosisItems.map((item) => <DiagnosisCard key={item.key} item={item} />)}
            </div>
          </div>
        </div>

        <div data-testid="backtest-report-primary-grid" className="grid grid-cols-1 gap-4 xl:grid-cols-12">
          <div id="backtest-report-曲线" data-testid="backtest-report-chart" className={`${GHOST_SECTION_CLASS} xl:col-span-8`}>
            <div className="mb-3 flex min-w-0 flex-wrap items-center justify-between gap-3">
              <div>
                <p className={LABEL_CLASS}>收益 / 回撤图</p>
                <h3 className="mt-1 text-sm font-semibold text-white">策略对比基准</h3>
              </div>
              <div className="flex flex-wrap gap-2 text-[11px] text-white/45">
                <span>策略</span>
                <span>基准</span>
                <span>每日盈亏</span>
              </div>
            </div>
            {chartNode ?? <DeterministicBacktestResultView run={run} normalized={normalized} densityConfig={densityConfig} />}
          </div>

          <aside data-testid="backtest-report-risk-side-rail" className="xl:col-span-4 flex min-w-0 flex-col gap-4">
            <div className={GHOST_SECTION_CLASS}>
              <p className={LABEL_CLASS}>风险摘要</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <MetricCard item={{ key: 'side-drawdown', label: 'Max DD', value: signedPct(displayDrawdown(normalized.metrics.maxDrawdownPct)), tone: 'negative' }} />
                <MetricCard item={{ key: 'side-sharpe', label: 'Sharpe', value: signedNumber(normalized.metrics.sharpeRatio), tone: toneFor(normalized.metrics.sharpeRatio) }} />
                <MetricCard item={{ key: 'side-win-rate', label: '胜率', value: signedPct(normalized.metrics.winRatePct), tone: toneFor(normalized.metrics.winRatePct) }} />
                <MetricCard item={{ key: 'side-trades', label: '交易次数', value: String(normalized.metrics.tradeCount ?? 0), tone: 'neutral' }} />
              </div>
              <p className="mt-3 text-xs leading-5 text-white/45">回撤、波动和交易胜率只说明历史检验压力，不代表真实成交或未来表现。</p>
            </div>

            <div id="backtest-report-benchmark" data-testid="backtest-report-benchmark" className={GHOST_SECTION_CLASS}>
              <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
                <div>
                  <p className={LABEL_CLASS}>基准对比</p>
                  <h3 className={`mt-1 text-sm font-semibold ${valueToneClass(benchmarkVerdict.tone)}`}>{benchmarkVerdict.label}</h3>
                </div>
                {benchmarkVerdict.label === '基准缺失' ? (
                  <span className="rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1 text-xs text-white/50">不影响策略自身回测结果</span>
                ) : null}
              </div>
              <p className="mt-2 text-sm text-white/78">{getBenchmarkSentence(normalized)}</p>
            </div>

            <div className={GHOST_SECTION_CLASS}>
              <p className={LABEL_CLASS}>数据质量</p>
              <p className="mt-2 text-xs leading-5 text-white/48">
                {dataQualityWarnings.length ? '回测数据质量有限，结果仅供评估。' : '数据质量明细默认折叠，必要时展开复查。'}
              </p>
            </div>
          </aside>
        </div>

        <div data-testid="backtest-report-detail-tabs" role="tablist" aria-label="Backtest report details" className="no-scrollbar flex min-w-0 gap-2 overflow-x-auto rounded-xl border border-white/5 bg-white/[0.02] p-1 [scrollbar-width:none]">
          {detailTabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={activeDetailTab === tab.key}
              className={`min-h-[34px] shrink-0 rounded-lg px-3 text-xs transition-all ${activeDetailTab === tab.key ? 'bg-white/10 text-white' : 'bg-transparent text-white/45 hover:bg-white/[0.05] hover:text-white/70'}`}
              onClick={() => setActiveDetailTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div id="backtest-report-key-metrics" data-testid="backtest-report-key-metrics" className={GHOST_SECTION_CLASS}>
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-white">核心指标</h3>
            <button type="button" className={SECONDARY_BUTTON_CLASS} onClick={() => setMoreMetricsOpen((value) => !value)}>
              {moreMetricsOpen ? '收起扩展指标' : '展开扩展指标'}
            </button>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            {metrics.map((item) => <MetricCard key={item.key} item={item} />)}
          </div>
          {moreMetricsOpen ? (
            <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4" data-testid="backtest-report-more-metrics">
              {moreMetrics.map((item) => <MetricCard key={item.key} item={item} />)}
            </div>
          ) : null}
        </div>

        <div id="backtest-report-交易" data-testid="backtest-report-trade-summary" className={GHOST_SECTION_CLASS}>
          <p className={LABEL_CLASS}>交易摘要</p>
          <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-5">
            <MetricCard item={{ key: 'total', label: '交易总数', value: String(tradeSummary.totalTrades), tone: 'neutral' }} />
            <MetricCard item={{ key: 'wins', label: '盈利交易', value: tradeSummary.winningTrades == null ? '--' : String(tradeSummary.winningTrades), tone: 'positive' }} />
            <MetricCard item={{ key: 'losses', label: '亏损交易', value: tradeSummary.losingTrades == null ? '--' : String(tradeSummary.losingTrades), tone: 'negative' }} />
            <MetricCard item={{ key: 'avg', label: '单笔均值', value: signedPct(tradeSummary.avgTradeReturnPct), tone: toneFor(tradeSummary.avgTradeReturnPct) }} />
            <MetricCard item={{ key: 'pf', label: '盈亏比', value: signedNumber(tradeSummary.profitFactor), tone: toneFor(tradeSummary.profitFactor) }} />
          </div>
        </div>

        <div id="backtest-report-归因" data-testid="backtest-report-attribution" className={GHOST_SECTION_CLASS}>
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
            <div>
              <p className={LABEL_CLASS}>交易归因</p>
              <h3 className="mt-1 text-sm font-semibold text-white">盈亏贡献</h3>
            </div>
            <div className="font-mono text-xs text-white/38">{trades.length} 笔交易</div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div>
              <p className={`${LABEL_CLASS} mb-2`}>按月份</p>
              <AttributionList rows={attributionByMonth} testId="backtest-attribution-month" />
            </div>
            <div>
              <p className={`${LABEL_CLASS} mb-2`}>按年份</p>
              <AttributionList rows={attributionByYear} testId="backtest-attribution-year" />
            </div>
            <div>
              <p className={`${LABEL_CLASS} mb-2`}>按退出原因</p>
              <AttributionList rows={attributionByExitReason} testId="backtest-attribution-exit-reason" formatKey={humanToken} />
            </div>
            <div>
              <p className={`${LABEL_CLASS} mb-2`}>按持有周期</p>
              <AttributionList rows={attributionByHoldingBucket} testId="backtest-attribution-holding-bucket" formatKey={holdingBucketLabel} />
            </div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
            <MetricCard item={{ key: 'gross', label: '毛盈亏', value: signedNumber(grossPnlTotal), tone: toneFor(grossPnlTotal) }} />
            <MetricCard item={{ key: 'net', label: '净盈亏', value: signedNumber(netPnlTotal), tone: toneFor(netPnlTotal) }} />
            <MetricCard item={{ key: 'fees', label: '费用', value: signedNumber(feesTotal), tone: feesTotal && feesTotal > 0 ? 'negative' : 'neutral' }} />
            <MetricCard item={{ key: 'slippage', label: '滑点', value: signedNumber(slippageTotal), tone: slippageTotal && slippageTotal > 0 ? 'negative' : 'neutral' }} />
          </div>
        </div>

        <div data-testid="backtest-report-event-timeline" data-visible-events={tradeEvents.length} data-total-events={trades.length * 2} className={GHOST_SECTION_CLASS}>
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
            <div>
              <p className={LABEL_CLASS}>持仓时间线</p>
              <h3 className="mt-1 text-sm font-semibold text-white">模拟买入事件 / 模拟卖出事件</h3>
              <p className="mt-1 text-xs leading-5 text-white/42">模拟事件仅用于回测复盘，不构成交易指令。</p>
            </div>
            <span className="font-mono text-xs text-white/38">前 {EVENT_ROW_LIMIT} 条</span>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {tradeEvents.length ? tradeEvents.map((event, index) => (
              <div key={`${event.date}-${event.type}-${index}`} className="grid min-w-0 grid-cols-[auto_1fr] gap-3 rounded-xl border border-white/5 bg-black/20 p-3">
                <div className={`font-mono text-[10px] font-bold ${valueToneClass(event.tone)}`}>{event.type === 'ENTRY' ? '模拟买入事件' : '模拟卖出事件'}</div>
                <div className="min-w-0">
                  <p className="truncate font-mono text-xs text-white/72">{event.date}</p>
                  <p className="mt-1 truncate text-xs text-white/42">{event.label}</p>
                </div>
              </div>
            )) : <p className="text-xs text-white/42">暂无交易事件</p>}
          </div>
        </div>

        <div id="backtest-report-风险" data-testid="backtest-report-risk-diagnostics" className={GHOST_SECTION_CLASS}>
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
            <div>
              <p className={LABEL_CLASS}>风险解读</p>
              <h3 className="mt-1 text-sm font-semibold text-white">回撤与压力解释</h3>
            </div>
            <span className="text-xs text-white/42">仅使用已返回指标与日账本摘要</span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
            <MetricCard item={{ key: 'max-drawdown', label: '最大回撤', value: signedPct(displayDrawdown(normalized.metrics.maxDrawdownPct)), tone: 'negative' }} />
            <MetricCard item={{ key: 'volatility', label: '波动压力', value: signedPct(volatilityPct), tone: toneFor(volatilityPct == null ? null : -volatilityPct) }} />
            <MetricCard item={{ key: 'worst-day', label: '极端亏损日', value: signedPct(worstDailyReturn), tone: toneFor(worstDailyReturn) }} />
            <MetricCard item={{ key: 'losses', label: '连续亏损', value: String(consecutiveLosses), tone: consecutiveLosses > 0 ? 'negative' : 'neutral' }} />
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
            <MetricCard item={{ key: 'best-trade', label: '最佳交易', value: signedPct(getTradeReturn(bestTrade || {} as RuleBacktestTradeItem)), tone: toneFor(getTradeReturn(bestTrade || {} as RuleBacktestTradeItem)) }} />
            <MetricCard item={{ key: 'worst-trade', label: '最差交易', value: signedPct(getTradeReturn(worstTrade || {} as RuleBacktestTradeItem)), tone: toneFor(getTradeReturn(worstTrade || {} as RuleBacktestTradeItem)) }} />
            <MetricCard item={{ key: 'wins', label: '连续盈利', value: String(consecutiveWins), tone: consecutiveWins > 0 ? 'positive' : 'neutral' }} />
          </div>
          <div className="mt-3 rounded-xl border border-white/5 bg-black/20 p-3">
            <p className={LABEL_CLASS}>最大回撤区间</p>
            <p className="mt-2 truncate font-mono text-xs text-white/70">
              {(drawdown.start || '--')} {'->'} {(drawdown.trough || '--')} · {signedPct(drawdown.value)}
              {drawdown.recovery ? ` · 修复 ${drawdown.recovery}` : ''}
            </p>
            <p className="mt-2 text-xs text-white/45">风险提示：回撤、波动和极端日只说明历史压力，不代表真实成交或未来表现。</p>
          </div>
        </div>

        <div data-testid="backtest-report-trade-table" data-visible-rows={visibleTrades.length} data-total-rows={trades.length} className={GHOST_SECTION_CLASS}>
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
            <div>
              <p className={LABEL_CLASS}>交易明细</p>
              <p className="mt-1 text-xs text-white/42">默认显示 {TRADE_ROW_LIMIT} 行 · 共 {trades.length} 行</p>
            </div>
            <button type="button" className={PRIMARY_BUTTON_CLASS} onClick={exportTrades} disabled={!trades.length}>
              导出交易CSV
            </button>
          </div>
          <div className="no-scrollbar mt-3 overflow-x-auto rounded-xl border border-white/5 [scrollbar-width:none]">
            <table className="min-w-[1220px] w-full text-left text-xs">
              <thead className="sticky top-0 bg-black/70 text-white/42">
                <tr>
                  {['入场日期', '退出日期', '标的', '数量', '入场价', '退出价', '毛盈亏', '净盈亏', '收益率', '费用', '滑点', '持有', '退出原因', '信号原因'].map((label) => (
                    <th key={label} className="px-3 py-2 font-semibold">{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleTrades.length ? visibleTrades.map((trade, index) => (
                  <tr key={`${trade.tradeIndex ?? index}-${trade.entryDate ?? index}`} data-testid={`backtest-trade-row-${index}`} className="border-t border-white/5 text-white/62">
                    <td className="px-3 py-2 font-mono">{trade.entryDate || '--'}</td>
                    <td className="px-3 py-2 font-mono">{trade.exitDate || '--'}</td>
                    <td className="px-3 py-2 font-mono">{trade.code || run.code || '--'}</td>
                    <td className="px-3 py-2 font-mono">{formatNumber(trade.quantity, 4)}</td>
                    <td className="px-3 py-2 font-mono">{formatNumber(trade.entryPrice)}</td>
                    <td className="px-3 py-2 font-mono">{formatNumber(trade.exitPrice)}</td>
                    <td className={`px-3 py-2 font-mono ${valueToneClass(toneFor(trade.grossPnl))}`}>{formatNumber(trade.grossPnl)}</td>
                    <td className={`px-3 py-2 font-mono ${valueToneClass(toneFor(tradeNetPnl(trade)))}`}>{formatNumber(tradeNetPnl(trade))}</td>
                    <td className={`px-3 py-2 font-mono ${valueToneClass(toneFor(trade.returnPct))}`}>{signedPct(trade.returnPct)}</td>
                    <td className="px-3 py-2 font-mono">{formatNumber(tradeFees(trade), 2)}</td>
                    <td className="px-3 py-2 font-mono">{formatNumber(tradeSlippage(trade), 2)}</td>
                    <td className="px-3 py-2 font-mono">{formatNumber(trade.holdingDays ?? trade.holdingCalendarDays ?? trade.holdingBars, 0)}</td>
                    <td className="max-w-[180px] truncate px-3 py-2">{humanToken(trade.exitReason || trade.exitTrigger || trade.exitSignal)}</td>
                    <td className="max-w-[220px] truncate px-3 py-2">{humanToken(trade.signalReason || trade.entrySignal || trade.entryTrigger)}</td>
                  </tr>
                )) : (
                  <tr><td colSpan={14} className="px-3 py-6 text-center text-white/42">暂无交易记录</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <details id="backtest-report-证据" data-testid="backtest-report-evidence-details" className={GHOST_SECTION_CLASS}>
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-left">
            <span>
              <span className={LABEL_CLASS}>复查材料</span>
              <span className="ml-2 text-xs text-white/42">数据质量 · 执行假设 · 每日账本</span>
            </span>
            <span className="text-xs text-white/45">展开</span>
          </summary>
          <p className="mt-3 text-xs leading-5 text-white/50">
            数据质量、执行假设和每日账本默认折叠，只在需要复查研究材料时展开。
          </p>
        </details>

        <div id="backtest-report-数据质量" data-testid="backtest-report-data-quality" className={GHOST_SECTION_CLASS}>
          <button type="button" className="flex min-h-[36px] w-full items-center justify-between gap-3 text-left" onClick={() => setDataQualityOpen((value) => !value)}>
            <span><span className={LABEL_CLASS}>数据质量</span></span>
            <span className="text-xs text-white/45">{dataQualityOpen ? '收起' : '展开'}</span>
          </button>
          {dataQualityOpen ? (
            dataQuality.length ? (
              <div data-testid="backtest-data-quality-grid" className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {dataQuality.map(([key, value]) => (
                  <div key={key} className="min-w-0 rounded-lg border border-white/5 bg-black/20 px-3 py-2">
                    <p className={LABEL_CLASS}>{key}</p>
                    <p className="mt-1 truncate font-mono text-xs text-white/70">{value}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-xs text-white/48">数据质量信息不足：当前结果未返回复权/分红/拆股元数据。</p>
            )
          ) : null}
          {dataQualityOpen ? dataQualityWarnings.length ? (
            <div className="mt-3 flex min-w-0 flex-wrap gap-2">
              {dataQualityWarnings.map((warning, index) => (
                <span
                  key={`${warning}-${index}`}
                  data-testid={`backtest-data-quality-warning-${index}`}
                  className="max-w-full truncate rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1 text-[11px] text-white/58"
                >
                  {warning}
                </span>
              ))}
            </div>
          ) : null : null}
        </div>

        <div id="backtest-report-执行假设" data-testid="backtest-report-execution-assumptions" className={GHOST_SECTION_CLASS}>
          <button type="button" className="flex min-h-[36px] w-full items-center justify-between gap-3 text-left" onClick={() => setAssumptionsOpen((value) => !value)}>
            <span><span className={LABEL_CLASS}>执行假设</span></span>
            <span className="text-xs text-white/45">{assumptionsOpen ? '收起' : '展开'}</span>
          </button>
          {assumptionsOpen ? (
            <>
              {!hasExplicitAssumptions ? (
                <p className="mt-3 text-xs text-white/48">执行假设信息不足：当前结果未返回成交时点/撮合规则。</p>
              ) : null}
              {assumptions.length ? (
                <div data-testid="backtest-execution-assumptions-grid" className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {assumptions.map(([key, value]) => (
                    <div key={key} className="min-w-0 rounded-lg border border-white/5 bg-black/20 px-3 py-2">
                      <p className={LABEL_CLASS}>{key}</p>
                      <p className="mt-1 truncate font-mono text-xs text-white/70">{value}</p>
                    </div>
                  ))}
                </div>
              ) : null}
              {executionWarnings.length ? (
                <div className="mt-3 flex min-w-0 flex-wrap gap-2">
                  {executionWarnings.map((warning, index) => (
                    <span
                      key={`${warning}-${index}`}
                      data-testid={`backtest-execution-warning-${index}`}
                      className="max-w-full truncate rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1 text-[11px] text-white/58"
                    >
                      {warning}
                    </span>
                  ))}
                </div>
              ) : null}
            </>
          ) : null}
        </div>

        <div id="backtest-report-账本" data-testid="backtest-report-advanced-details" className={GHOST_SECTION_CLASS}>
          <button type="button" className="flex min-h-[36px] w-full items-center justify-between gap-3 text-left" onClick={() => setAdvancedOpen((value) => !value)}>
            <span>
              <span className={LABEL_CLASS}>账本与导出</span>
              <span className="ml-2 text-xs text-white/42">完整指标 · 每日账本 · 复查导出</span>
            </span>
            <span className="text-xs text-white/45">{advancedOpen ? '收起' : '展开'}</span>
          </button>
          <div className="mt-4 flex min-w-0 flex-col gap-3">
            <div data-testid="backtest-report-ledger-summary" className="rounded-xl border border-white/5 bg-black/20 p-3 text-xs text-white/58">
              每日账本 {normalized.rows.length} 行 · {normalized.viewerMeta.firstDate || '--'} {'->'} {normalized.viewerMeta.lastDate || '--'} · 复查材料按需展开
            </div>
            {advancedOpen ? (
              <>
                <div className="flex flex-wrap gap-2">
                  <button type="button" className={SECONDARY_BUTTON_CLASS} onClick={() => setLedgerOpen((value) => !value)}>
                    {ledgerOpen ? '收起每日账本' : '展开每日账本'}
                  </button>
                  <button type="button" className={SECONDARY_BUTTON_CLASS} onClick={exportLedger} disabled={!normalized.rows.length}>
                    导出账本CSV
                  </button>
                  <button type="button" className={SECONDARY_BUTTON_CLASS} onClick={() => downloadExecutionTraceCsv(run)} disabled={!hasTraceRows}>
                    导出执行明细 CSV
                  </button>
                  <button type="button" className={SECONDARY_BUTTON_CLASS} onClick={() => downloadExecutionTraceJson(run)} disabled={!hasTraceRows}>
                    导出执行明细 JSON
                  </button>
                </div>
                <div className="rounded-xl border border-white/5 bg-black/20 p-3 text-xs text-white/48">
                  扩展指标在上方折叠区展示；执行明细仅提供导出，不默认渲染全部存储行。
                </div>
              </>
            ) : null}
              {ledgerOpen ? (
                <div data-testid="backtest-report-ledger-table" data-visible-rows={visibleLedgerRows.length} data-total-rows={normalized.rows.length} className="no-scrollbar max-h-[420px] overflow-auto rounded-xl border border-white/5 [scrollbar-width:none]">
                  <table className="min-w-[1100px] w-full text-left text-xs">
                    <thead className="sticky top-0 bg-black/85 text-white/42">
                      <tr>
                        {['日期', '动作', '收盘', '基准', '成交价', '股数', '现金', '权益', '日盈亏', '日收益', '策略收益'].map((label) => (
                          <th key={label} className="px-3 py-2 font-semibold">{label}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {visibleLedgerRows.map((row: DeterministicBacktestNormalizedRow, index) => (
                        <tr key={row.date} data-testid={`backtest-ledger-row-${index}`} className="border-t border-white/5 text-white/62">
                          <td className="px-3 py-2 font-mono">{row.date}</td>
                          <td className="px-3 py-2">{formatDeterministicActionLabel(row.action, language)}</td>
                          <td className="px-3 py-2 font-mono">{formatNumber(row.symbolClose)}</td>
                          <td className="px-3 py-2 font-mono">{formatNumber(row.benchmarkClose)}</td>
                          <td className="px-3 py-2 font-mono">{formatNumber(row.fillPrice)}</td>
                          <td className="px-3 py-2 font-mono">{formatNumber(row.shares, 4)}</td>
                          <td className="px-3 py-2 font-mono">{formatNumber(row.cash)}</td>
                          <td className="px-3 py-2 font-mono">{formatNumber(row.totalValue)}</td>
                          <td className={`px-3 py-2 font-mono ${valueToneClass(toneFor(row.dailyPnl))}`}>{formatNumber(row.dailyPnl)}</td>
                          <td className={`px-3 py-2 font-mono ${valueToneClass(toneFor(row.dailyReturn))}`}>{pct(row.dailyReturn)}</td>
                          <td className={`px-3 py-2 font-mono ${valueToneClass(toneFor(row.strategyCumReturn))}`}>{signedPct(row.strategyCumReturn)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
          </div>
        </div>
      </div>
    </section>
  );
};

export default BacktestResultReport;
