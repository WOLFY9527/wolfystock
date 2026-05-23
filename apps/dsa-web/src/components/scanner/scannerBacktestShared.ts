import type { ScannerCandidate } from '../../types/scanner';

const SCANNER_BACKTEST_INITIAL_CAPITAL = 100000;
const SCANNER_BACKTEST_FEE_BPS = 0;
const SCANNER_BACKTEST_SLIPPAGE_BPS = 0;
const SCANNER_BACKTEST_BENCHMARK_MODE = 'auto';

export type ScannerBacktestStatus = 'idle' | 'queued' | 'running' | 'completed' | 'failed' | 'skipped_existing';
export type ScannerBacktestSource = 'official_selected' | 'preview_selected' | 'top_5' | 'current_filter' | 'manual';
export type ScannerBacktestBatchSource = Exclude<ScannerBacktestSource, 'manual'>;
export type ScannerBacktestItem = {
  symbol: string;
  status: ScannerBacktestStatus;
  resultId?: number | string;
  totalReturnPct?: number | null;
  maxDrawdownPct?: number | null;
  sharpe?: number | null;
  tradeCount?: number | null;
  error?: string | null;
};

export type ScannerBacktestConfig = {
  startDate: string;
  endDate: string;
  initialCapital: number;
  feeBps: number;
  slippageBps: number;
  benchmarkMode: 'auto';
  strategyTemplate: 'moving_average_crossover';
};

function toDateInputValue(value: Date): string {
  return value.toISOString().slice(0, 10);
}

export function normalizeCandidateSymbol(symbol?: string | null): string | null {
  const normalized = String(symbol || '').trim().toUpperCase();
  return normalized || null;
}

export function getScannerBacktestConfig(): ScannerBacktestConfig {
  const end = new Date();
  const start = new Date(end);
  start.setFullYear(end.getFullYear() - 1);

  return {
    startDate: toDateInputValue(start),
    endDate: toDateInputValue(end),
    initialCapital: SCANNER_BACKTEST_INITIAL_CAPITAL,
    feeBps: SCANNER_BACKTEST_FEE_BPS,
    slippageBps: SCANNER_BACKTEST_SLIPPAGE_BPS,
    benchmarkMode: SCANNER_BACKTEST_BENCHMARK_MODE,
    strategyTemplate: 'moving_average_crossover',
  };
}

export function getScannerBacktestKey(symbol: string): string {
  const config = getScannerBacktestConfig();
  return [
    symbol,
    config.startDate,
    config.endDate,
    config.initialCapital,
    config.feeBps,
    config.slippageBps,
    config.benchmarkMode,
    config.strategyTemplate,
  ].join('|');
}

export function dedupeBacktestCandidates(candidates: ScannerCandidate[]): ScannerCandidate[] {
  const seen = new Set<string>();
  const items: ScannerCandidate[] = [];

  candidates.forEach((candidate) => {
    const symbol = normalizeCandidateSymbol(candidate.symbol);
    if (!symbol || seen.has(symbol)) return;
    seen.add(symbol);
    items.push({ ...candidate, symbol });
  });

  return items;
}
