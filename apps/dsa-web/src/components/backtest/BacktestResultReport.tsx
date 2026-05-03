import type React from 'react';
import { useMemo, useState } from 'react';
import type { BacktestDiagnosticWarning, RuleBacktestRunResponse, RuleBacktestTradeItem } from '../../types/backtest';
import { useI18n } from '../../contexts/UiLanguageContext';
import { StatusBadge } from '../ui/StatusBadge';
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

const GHOST_SECTION_CLASS = 'rounded-xl border border-white/5 bg-white/[0.02] p-4 backdrop-blur-md transition-all hover:border-white/10 sm:p-5';
const LABEL_CLASS = 'text-[10px] font-bold uppercase tracking-widest text-white/40';
const VALUE_CLASS = 'font-mono text-sm text-white';
const POSITIVE_CLASS = 'text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.4)]';
const NEGATIVE_CLASS = 'text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.4)]';
const SECONDARY_BUTTON_CLASS = 'inline-flex items-center justify-center rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-medium text-white/70 transition-all hover:bg-white/10';
const PRIMARY_BUTTON_CLASS = 'inline-flex items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.18)] transition-all hover:border-emerald-400/45 hover:bg-emerald-500/15';
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

function formatBps(value: unknown): string {
  const parsed = safeNumber(value);
  if (parsed == null) return 'unknown';
  return Number.isInteger(parsed) ? String(parsed) : formatNumber(parsed, 2);
}

function warningText(warning: BacktestDiagnosticWarning | Record<string, unknown>): string {
  return safeText(warning.message) || safeText(warning.code) || 'metadata warning';
}

function assumptionEntries(run: RuleBacktestRunResponse): Array<[string, string]> {
  const source = (run.executionAssumptions || {}) as Record<string, unknown>;
  const feeModel = (recordValue(source, 'feeModel', 'fee_model') || {}) as Record<string, unknown>;
  const slippageModel = (recordValue(source, 'slippageModel', 'slippage_model') || {}) as Record<string, unknown>;
  const structured: Array<[string, string | null]> = [
    ['Engine', safeText(recordValue(source, 'engine') as string) || null],
    ['Signal / Fill', `${displayToken(recordValue(source, 'signalTiming', 'signal_timing', 'signalEvaluationTiming', 'signal_evaluation_timing'))} -> ${displayToken(recordValue(source, 'fillTiming', 'fill_timing', 'entryFillTiming', 'entry_fill_timing'))}`],
    ['Fill Price', displayToken(recordValue(source, 'fillPrice', 'fill_price', 'defaultFillPriceBasis', 'default_fill_price_basis'))],
    ['Fee / Slippage', `${formatBps(recordValue(feeModel, 'commissionBps', 'commission_bps') ?? run.feeBps)}bp / ${formatBps(recordValue(slippageModel, 'slippageBps', 'slippage_bps') ?? run.slippageBps)}bp`],
    ['Fractional / Lot', `${recordValue(source, 'allowFractionalShares', 'allow_fractional_shares') === false ? 'whole shares' : 'fractional'} / lot ${displayToken(recordValue(source, 'lotSize', 'lot_size') ?? 1)}`],
    ['Volume Limit', displayToken(recordValue(source, 'volumeParticipationLimit', 'volume_participation_limit'))],
    ['Market Rules', `${displayToken(recordValue(source, 'limitUpDownHandling', 'limit_up_down_handling'))} / ${displayToken(recordValue(source, 'haltHandling', 'halt_handling'))}`],
    ['Short Selling', displayToken(recordValue(source, 'shortSelling', 'short_selling'))],
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
      return [key, typeof value === 'object' ? JSON.stringify(value) : String(value)];
    })
    .filter((entry): entry is [string, string] => entry != null);
  if (explicit.length) return explicit;

  const inferred: Array<[string, string | number | null | undefined]> = [
    ['timeframe', run.timeframe],
    ['fee_bps_per_side', run.feeBps],
    ['slippage_bps_per_side', run.slippageBps],
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
      ['Source', safeText(explicit.provider || '') || safeText(explicit.source || '')],
      ['Frequency', safeText(explicit.frequency || '')],
      ['Bar Coverage', `${barCount ?? '--'} / ${expected ?? '--'}`],
      ['Actual Range', explicit.actualStart || explicit.actualEnd ? `${explicit.actualStart || '--'} -> ${explicit.actualEnd || '--'}` : null],
      ['Adjust / Div / Split', `${displayToken(explicit.adjustmentMode)} / ${displayToken(explicit.dividendsHandled)} / ${displayToken(explicit.splitsHandled)}`],
      ['Warnings', warnings],
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

function getMetricItems(normalized: DeterministicBacktestNormalizedResult): MetricItem[] {
  const metrics = normalized.metrics;
  return [
    { key: 'total', label: 'Total Return', value: signedPct(metrics.totalReturnPct), rawValue: metrics.totalReturnPct, tone: toneFor(metrics.totalReturnPct) },
    { key: 'benchmark', label: 'Benchmark Return', value: signedPct(metrics.benchmarkReturnPct), rawValue: metrics.benchmarkReturnPct, tone: toneFor(metrics.benchmarkReturnPct) },
    { key: 'excess', label: 'Excess Return', value: signedPct(metrics.excessReturnVsBenchmarkPct), rawValue: metrics.excessReturnVsBenchmarkPct, tone: toneFor(metrics.excessReturnVsBenchmarkPct) },
    { key: 'drawdown', label: 'Max Drawdown', value: signedPct(displayDrawdown(metrics.maxDrawdownPct)), rawValue: metrics.maxDrawdownPct, tone: 'negative' },
    { key: 'cagr', label: 'CAGR', value: signedPct(metrics.annualizedReturnPct), rawValue: metrics.annualizedReturnPct, tone: toneFor(metrics.annualizedReturnPct) },
    { key: 'sharpe', label: 'Sharpe', value: signedNumber(metrics.sharpeRatio), rawValue: metrics.sharpeRatio, tone: toneFor(metrics.sharpeRatio) },
    { key: 'winRate', label: 'Win Rate', value: signedPct(metrics.winRatePct), rawValue: metrics.winRatePct, tone: toneFor(metrics.winRatePct) },
    { key: 'trades', label: 'Trades', value: String(metrics.tradeCount ?? 0), rawValue: metrics.tradeCount, tone: 'neutral' },
  ];
}

function getMoreMetricItems(run: RuleBacktestRunResponse, summary: TradeSummary): MetricItem[] {
  const lookup = run.summary || {};
  const items: Array<[string, string, number | null]> = [
    ['sortino', 'Sortino', safeNumber(lookup.sortino ?? lookup.sortinoRatio)],
    ['calmar', 'Calmar', safeNumber(lookup.calmar ?? lookup.calmarRatio)],
    ['volatility', 'Volatility', safeNumber(lookup.volatilityPct ?? lookup.volatility)],
    ['profitFactor', 'Profit Factor', summary.profitFactor],
    ['avgHolding', 'Average Holding Days', summary.avgHoldingDays],
    ['avgWin', 'Average Win', summary.avgWinPct],
    ['avgLoss', 'Average Loss', summary.avgLossPct],
    ['maxLosses', 'Max Consecutive Losses', safeNumber(lookup.maxConsecutiveLosses)],
    ['maxWins', 'Max Consecutive Wins', safeNumber(lookup.maxConsecutiveWins)],
    ['alpha', 'Alpha', safeNumber(lookup.alpha)],
    ['beta', 'Beta', safeNumber(lookup.beta)],
    ['info', 'Information Ratio', safeNumber(lookup.informationRatio)],
    ['tracking', 'Tracking Error', safeNumber(lookup.trackingError)],
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

function getBenchmarkSentence(normalized: DeterministicBacktestNormalizedResult): string {
  const { benchmarkReturnPct, excessReturnVsBenchmarkPct, maxDrawdownPct, sharpeRatio } = normalized.metrics;
  if (benchmarkReturnPct == null || excessReturnVsBenchmarkPct == null) {
    return '基准数据不足，无法计算超额收益。';
  }
  const result = excessReturnVsBenchmarkPct >= 0 ? '策略跑赢基准' : '策略未跑赢基准';
  const parts = [`${result} ${signedPct(excessReturnVsBenchmarkPct)}`];
  if (maxDrawdownPct != null) parts.push(`最大回撤 ${signedPct(displayDrawdown(maxDrawdownPct))}`);
  if (sharpeRatio != null) parts.push(`Sharpe ${signedNumber(sharpeRatio)}`);
  return `${parts.join(' · ')}。`;
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
        label: compactToken(trade.entryReason || trade.entrySignal || trade.entryTrigger),
        tone: 'neutral',
      });
    }
    if (trade.exitDate) {
      events.push({
        date: trade.exitDate,
        type: 'EXIT',
        label: compactToken(trade.exitReason || trade.exitSignal || trade.exitTrigger),
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

function AttributionList({ rows, testId }: { rows: AttributionRow[]; testId: string }) {
  return (
    <div data-testid={testId} className="min-w-0 rounded-xl border border-white/5 bg-black/20 p-3">
      <div className="space-y-2">
        {rows.length ? rows.map((row) => {
          const contribution = row.netPnl != null ? signedNumber(row.netPnl) : signedPct(row.returnPct);
          return (
            <div key={row.key} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 text-xs">
              <span className="truncate text-white/62">{compactToken(row.key)}</span>
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

const BacktestResultReport: React.FC<BacktestResultReportProps> = ({
  run,
  mode,
  normalized: providedNormalized,
  densityConfig,
  chartNode,
}) => {
  const { language } = useI18n();
  const [moreMetricsOpen, setMoreMetricsOpen] = useState(mode === 'professional');
  const [dataQualityOpen, setDataQualityOpen] = useState(mode === 'professional');
  const [assumptionsOpen, setAssumptionsOpen] = useState(mode === 'professional');
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [ledgerOpen, setLedgerOpen] = useState(false);
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
  const grossPnlTotal = useMemo(() => sumNullable(trades.map((trade) => safeNumber(trade.grossPnl))), [trades]);
  const netPnlTotal = useMemo(() => sumNullable(trades.map(tradeNetPnl)), [trades]);
  const feesTotal = useMemo(() => sumNullable(trades.map(tradeFees)), [trades]);
  const slippageTotal = useMemo(() => sumNullable(trades.map(tradeSlippage)), [trades]);
  const drawdown = useMemo(() => drawdownPeriod(normalized.rows), [normalized.rows]);
  const bestTrade = useMemo(() => trades.reduce<RuleBacktestTradeItem | null>((best, trade) => {
    const value = getTradeReturn(trade);
    const bestValue = best ? getTradeReturn(best) : null;
    return value != null && (bestValue == null || value > bestValue) ? trade : best;
  }, null), [trades]);
  const worstTrade = useMemo(() => trades.reduce<RuleBacktestTradeItem | null>((worst, trade) => {
    const value = getTradeReturn(trade);
    const worstValue = worst ? getTradeReturn(worst) : null;
    return value != null && (worstValue == null || value < worstValue) ? trade : worst;
  }, null), [trades]);
  const consecutiveWins = useMemo(() => maxStreak(trades, (value) => value > 0), [trades]);
  const consecutiveLosses = useMemo(() => maxStreak(trades, (value) => value < 0), [trades]);
  const metrics = useMemo(() => getMetricItems(normalized), [normalized]);
  const moreMetrics = useMemo(() => getMoreMetricItems(run, tradeSummary), [run, tradeSummary]);
  const dataQuality = useMemo(() => dataQualityEntries(run, normalized), [run, normalized]);
  const assumptions = useMemo(() => assumptionEntries(run), [run]);
  const dataQualityWarnings = useMemo(() => (run.dataQuality?.warnings || []).map(warningText), [run.dataQuality?.warnings]);
  const executionWarnings = useMemo(() => {
    const assumptionsPayload = (run.executionAssumptions || {}) as Record<string, unknown>;
    const warnings = recordValue(assumptionsPayload, 'warnings') as Array<Record<string, unknown>> | null;
    return Array.isArray(warnings) ? warnings.map(warningText) : [];
  }, [run.executionAssumptions]);
  const hasExplicitAssumptions = Object.keys(run.executionAssumptions || {}).length > 0;
  const visibleTrades = trades.slice(0, TRADE_ROW_LIMIT);
  const visibleLedgerRows = normalized.rows.slice(0, LEDGER_ROW_LIMIT);
  const statusLabel = getRuleRunStatusLabel(run.status, language);
  const statusWord = run.status === 'completed' ? '回测完成' : statusLabel;
  const firstDate = normalized.viewerMeta.firstDate || run.startDate || run.periodStart || null;
  const lastDate = normalized.viewerMeta.lastDate || run.endDate || run.periodEnd || null;
  const dateRange = firstDate || lastDate ? `${firstDate || '--'} -> ${lastDate || '--'}` : '--';

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

  return (
    <section
      className="backtest-display-section"
      data-testid="backtest-result-report"
      data-report-mode={mode}
    >
      <div className="flex min-w-0 flex-col gap-4 text-sm text-white/70">
        <nav className="flex min-w-0 gap-2 overflow-x-auto pb-1 [scrollbar-width:none]" aria-label="Backtest result sections">
          {['概览', '曲线', '交易', '归因', '风险', '数据质量', '执行假设', '账本'].map((item) => (
            <a key={item} href={`#backtest-report-${item}`} className="shrink-0 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/60 hover:bg-white/10">
              {item}
            </a>
          ))}
        </nav>

        <div id="backtest-report-概览" data-testid="backtest-report-summary" className={`${GHOST_SECTION_CLASS} overflow-hidden`}>
          <div className="flex min-w-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <div className="truncate text-base font-semibold text-white">{run.code || '--'} · {statusWord}</div>
                <StatusBadge status={run.status} label={run.status || statusLabel} size="sm" variant="soft" />
                <span className="font-mono text-xs text-white/38">{dateRange}</span>
              </div>
              <div className="mt-3 flex min-w-0 flex-wrap gap-x-4 gap-y-2 text-xs text-white/58">
                <span>策略收益 {renderValue(signedPct(normalized.metrics.totalReturnPct), toneFor(normalized.metrics.totalReturnPct))}</span>
                <span>基准 {renderValue(signedPct(normalized.metrics.benchmarkReturnPct), toneFor(normalized.metrics.benchmarkReturnPct))}</span>
                <span>超额 {renderValue(signedPct(normalized.metrics.excessReturnVsBenchmarkPct), toneFor(normalized.metrics.excessReturnVsBenchmarkPct))}</span>
              </div>
              <div className="mt-2 flex min-w-0 flex-wrap gap-x-4 gap-y-2 text-xs text-white/50">
                <span>最大回撤 {renderValue(signedPct(displayDrawdown(normalized.metrics.maxDrawdownPct)), 'negative')}</span>
                <span>Sharpe {renderValue(signedNumber(normalized.metrics.sharpeRatio), toneFor(normalized.metrics.sharpeRatio))}</span>
                <span>交易 <span className="font-mono text-white">{normalized.metrics.tradeCount}</span> 次</span>
              </div>
            </div>
            <div className="font-mono text-xs text-white/38">{formatDateTime(run.completedAt || run.runAt)}</div>
          </div>
        </div>

        <div id="backtest-report-key-metrics" data-testid="backtest-report-key-metrics" className={GHOST_SECTION_CLASS}>
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-white">Key Metrics</h3>
            <button type="button" className={SECONDARY_BUTTON_CLASS} onClick={() => setMoreMetricsOpen((value) => !value)}>
              {moreMetricsOpen ? '收起 More Metrics' : '展开 More Metrics'}
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

        <div id="backtest-report-曲线" data-testid="backtest-report-chart" className={GHOST_SECTION_CLASS}>
          <div className="mb-3 flex min-w-0 flex-wrap items-center justify-between gap-3">
            <div>
              <p className={LABEL_CLASS}>Equity / Drawdown Chart</p>
              <h3 className="mt-1 text-sm font-semibold text-white">Strategy vs Benchmark</h3>
            </div>
            <div className="flex flex-wrap gap-2 text-[11px] text-white/45">
              <span>Strategy</span>
              <span>Benchmark</span>
              <span>Daily P&L</span>
            </div>
          </div>
          {chartNode ?? <DeterministicBacktestResultView run={run} normalized={normalized} densityConfig={densityConfig} />}
        </div>

        <div id="backtest-report-benchmark" data-testid="backtest-report-benchmark" className={GHOST_SECTION_CLASS}>
          <p className={LABEL_CLASS}>Benchmark Comparison</p>
          <p className="mt-2 text-sm text-white/78">{getBenchmarkSentence(normalized)}</p>
          <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
            <MetricCard item={{ key: 'strategy', label: 'Strategy', value: signedPct(normalized.metrics.totalReturnPct), tone: toneFor(normalized.metrics.totalReturnPct) }} />
            <MetricCard item={{ key: 'bench', label: normalized.benchmarkMeta.benchmarkLabel || 'Benchmark', value: signedPct(normalized.metrics.benchmarkReturnPct), tone: toneFor(normalized.metrics.benchmarkReturnPct) }} />
            <MetricCard item={{ key: 'excess', label: 'Excess', value: signedPct(normalized.metrics.excessReturnVsBenchmarkPct), tone: toneFor(normalized.metrics.excessReturnVsBenchmarkPct) }} />
            <MetricCard item={{ key: 'dd', label: 'Drawdown', value: signedPct(displayDrawdown(normalized.metrics.maxDrawdownPct)), tone: 'negative' }} />
          </div>
        </div>

        <div id="backtest-report-交易" data-testid="backtest-report-trade-summary" className={GHOST_SECTION_CLASS}>
          <p className={LABEL_CLASS}>Trade Summary</p>
          <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-5">
            <MetricCard item={{ key: 'total', label: 'Total Trades', value: String(tradeSummary.totalTrades), tone: 'neutral' }} />
            <MetricCard item={{ key: 'wins', label: 'Winning Trades', value: tradeSummary.winningTrades == null ? '--' : String(tradeSummary.winningTrades), tone: 'positive' }} />
            <MetricCard item={{ key: 'losses', label: 'Losing Trades', value: tradeSummary.losingTrades == null ? '--' : String(tradeSummary.losingTrades), tone: 'negative' }} />
            <MetricCard item={{ key: 'avg', label: 'Avg Trade', value: signedPct(tradeSummary.avgTradeReturnPct), tone: toneFor(tradeSummary.avgTradeReturnPct) }} />
            <MetricCard item={{ key: 'pf', label: 'Profit Factor', value: signedNumber(tradeSummary.profitFactor), tone: toneFor(tradeSummary.profitFactor) }} />
          </div>
        </div>

        <div id="backtest-report-归因" data-testid="backtest-report-attribution" className={GHOST_SECTION_CLASS}>
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
            <div>
              <p className={LABEL_CLASS}>Trade Attribution</p>
              <h3 className="mt-1 text-sm font-semibold text-white">PnL Contribution</h3>
            </div>
            <div className="font-mono text-xs text-white/38">{trades.length} trades</div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div>
              <p className={`${LABEL_CLASS} mb-2`}>By Month</p>
              <AttributionList rows={attributionByMonth} testId="backtest-attribution-month" />
            </div>
            <div>
              <p className={`${LABEL_CLASS} mb-2`}>By Year</p>
              <AttributionList rows={attributionByYear} testId="backtest-attribution-year" />
            </div>
            <div>
              <p className={`${LABEL_CLASS} mb-2`}>By Exit Reason</p>
              <AttributionList rows={attributionByExitReason} testId="backtest-attribution-exit-reason" />
            </div>
            <div>
              <p className={`${LABEL_CLASS} mb-2`}>By Holding Duration</p>
              <AttributionList rows={attributionByHoldingBucket} testId="backtest-attribution-holding-bucket" />
            </div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
            <MetricCard item={{ key: 'gross', label: 'Gross PnL', value: signedNumber(grossPnlTotal), tone: toneFor(grossPnlTotal) }} />
            <MetricCard item={{ key: 'net', label: 'Net PnL', value: signedNumber(netPnlTotal), tone: toneFor(netPnlTotal) }} />
            <MetricCard item={{ key: 'fees', label: 'Fees', value: signedNumber(feesTotal), tone: feesTotal && feesTotal > 0 ? 'negative' : 'neutral' }} />
            <MetricCard item={{ key: 'slippage', label: 'Slippage', value: signedNumber(slippageTotal), tone: slippageTotal && slippageTotal > 0 ? 'negative' : 'neutral' }} />
          </div>
        </div>

        <div data-testid="backtest-report-event-timeline" data-visible-events={tradeEvents.length} data-total-events={trades.length * 2} className={GHOST_SECTION_CLASS}>
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
            <div>
              <p className={LABEL_CLASS}>Holding Timeline</p>
              <h3 className="mt-1 text-sm font-semibold text-white">Entry / Exit Events</h3>
            </div>
            <span className="font-mono text-xs text-white/38">top {EVENT_ROW_LIMIT}</span>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {tradeEvents.length ? tradeEvents.map((event, index) => (
              <div key={`${event.date}-${event.type}-${index}`} className="grid min-w-0 grid-cols-[auto_1fr] gap-3 rounded-xl border border-white/5 bg-black/20 p-3">
                <div className={`font-mono text-[10px] font-bold ${valueToneClass(event.tone)}`}>{event.type}</div>
                <div className="min-w-0">
                  <p className="truncate font-mono text-xs text-white/72">{event.date}</p>
                  <p className="mt-1 truncate text-xs text-white/42">{event.label}</p>
                </div>
              </div>
            )) : <p className="text-xs text-white/42">暂无交易事件</p>}
          </div>
        </div>

        <div id="backtest-report-风险" data-testid="backtest-report-risk-diagnostics" className={GHOST_SECTION_CLASS}>
          <p className={LABEL_CLASS}>Risk Diagnostics</p>
          <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
            <MetricCard item={{ key: 'best-trade', label: 'Best Trade', value: signedPct(getTradeReturn(bestTrade || {} as RuleBacktestTradeItem)), tone: toneFor(getTradeReturn(bestTrade || {} as RuleBacktestTradeItem)) }} />
            <MetricCard item={{ key: 'worst-trade', label: 'Worst Trade', value: signedPct(getTradeReturn(worstTrade || {} as RuleBacktestTradeItem)), tone: toneFor(getTradeReturn(worstTrade || {} as RuleBacktestTradeItem)) }} />
            <MetricCard item={{ key: 'wins', label: 'Consecutive Wins', value: String(consecutiveWins), tone: 'positive' }} />
            <MetricCard item={{ key: 'losses', label: 'Consecutive Losses', value: String(consecutiveLosses), tone: 'negative' }} />
          </div>
          <div className="mt-3 rounded-xl border border-white/5 bg-black/20 p-3">
            <p className={LABEL_CLASS}>Max Drawdown Period</p>
            <p className="mt-2 truncate font-mono text-xs text-white/70">
              {(drawdown.start || '--')} {'->'} {(drawdown.trough || '--')} · {signedPct(drawdown.value)}
              {drawdown.recovery ? ` · recovered ${drawdown.recovery}` : ''}
            </p>
          </div>
        </div>

        <div data-testid="backtest-report-trade-table" data-visible-rows={visibleTrades.length} data-total-rows={trades.length} className={GHOST_SECTION_CLASS}>
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
            <div>
              <p className={LABEL_CLASS}>Trade Table</p>
              <p className="mt-1 text-xs text-white/42">默认显示 {TRADE_ROW_LIMIT} 行 · 共 {trades.length} 行</p>
            </div>
            <button type="button" className={PRIMARY_BUTTON_CLASS} onClick={exportTrades} disabled={!trades.length}>
              导出交易CSV
            </button>
          </div>
          <div className="mt-3 overflow-x-auto rounded-xl border border-white/5 [scrollbar-width:none]">
            <table className="min-w-[1220px] w-full text-left text-xs">
              <thead className="sticky top-0 bg-black/70 text-white/42">
                <tr>
                  {['Entry Date', 'Exit Date', 'Symbol', 'Qty', 'Entry', 'Exit', 'Gross', 'Net', 'Return', 'Fees', 'Slip', 'Holding', 'Exit Reason', 'Signal Reason'].map((label) => (
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
                    <td className="max-w-[180px] truncate px-3 py-2">{compactToken(trade.exitReason || trade.exitTrigger || trade.exitSignal)}</td>
                    <td className="max-w-[220px] truncate px-3 py-2">{compactToken(trade.signalReason || trade.entrySignal || trade.entryTrigger)}</td>
                  </tr>
                )) : (
                  <tr><td colSpan={14} className="px-3 py-6 text-center text-white/42">暂无交易记录</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div id="backtest-report-数据质量" data-testid="backtest-report-data-quality" className={GHOST_SECTION_CLASS}>
          <button type="button" className="flex w-full items-center justify-between gap-3 text-left" onClick={() => setDataQualityOpen((value) => !value)}>
            <span><span className={LABEL_CLASS}>Data Quality</span></span>
            <span className="text-xs text-white/45">{dataQualityOpen ? '收起' : '展开'}</span>
          </button>
          {dataQualityOpen || mode === 'simple' ? (
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
          {dataQualityOpen || mode === 'simple' ? dataQualityWarnings.length ? (
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
          <button type="button" className="flex w-full items-center justify-between gap-3 text-left" onClick={() => setAssumptionsOpen((value) => !value)}>
            <span><span className={LABEL_CLASS}>Execution Assumptions</span></span>
            <span className="text-xs text-white/45">{assumptionsOpen ? '收起' : '展开'}</span>
          </button>
          {assumptionsOpen || mode === 'simple' ? (
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
          <button type="button" className="flex w-full items-center justify-between gap-3 text-left" onClick={() => setAdvancedOpen((value) => !value)}>
            <span>
              <span className={LABEL_CLASS}>Advanced Details</span>
              <span className="ml-2 text-xs text-white/42">Full metrics · Daily ledger · Raw trace</span>
            </span>
            <span className="text-xs text-white/45">{advancedOpen ? '收起' : '展开'}</span>
          </button>
          <div className="mt-4 flex min-w-0 flex-col gap-3">
            <div data-testid="backtest-report-ledger-summary" className="rounded-xl border border-white/5 bg-black/20 p-3 text-xs text-white/58">
              每日账本 {normalized.rows.length} 行 · {normalized.viewerMeta.firstDate || '--'} {'->'} {normalized.viewerMeta.lastDate || '--'} · 约 11 列
            </div>
            <div className="flex flex-wrap gap-2">
              <button type="button" className={SECONDARY_BUTTON_CLASS} onClick={() => setLedgerOpen((value) => !value)}>
                {ledgerOpen ? '收起每日账本' : '展开每日账本'}
              </button>
              <button type="button" className={SECONDARY_BUTTON_CLASS} onClick={exportLedger} disabled={!normalized.rows.length}>
                导出账本CSV
              </button>
              <button type="button" className={SECONDARY_BUTTON_CLASS} onClick={() => downloadExecutionTraceCsv(run)} disabled={!hasExecutionTraceRows(run)}>
                导出执行Trace CSV
              </button>
              <button type="button" className={SECONDARY_BUTTON_CLASS} onClick={() => downloadExecutionTraceJson(run)} disabled={!hasExecutionTraceRows(run)}>
                导出执行Trace JSON
              </button>
            </div>
            {advancedOpen ? (
              <div className="rounded-xl border border-white/5 bg-black/20 p-3 text-xs text-white/48">
                Full metrics use the More Metrics panel above. Raw execution trace exports stay available without rendering every stored row.
              </div>
            ) : null}
              {ledgerOpen ? (
                <div data-testid="backtest-report-ledger-table" data-visible-rows={visibleLedgerRows.length} data-total-rows={normalized.rows.length} className="max-h-[420px] overflow-auto rounded-xl border border-white/5 [scrollbar-width:none]">
                  <table className="min-w-[1100px] w-full text-left text-xs">
                    <thead className="sticky top-0 bg-black/85 text-white/42">
                      <tr>
                        {['Date', 'Action', 'Close', 'Benchmark', 'Fill', 'Shares', 'Cash', 'Equity', 'Daily PnL', 'Daily Return', 'Strategy Return'].map((label) => (
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
