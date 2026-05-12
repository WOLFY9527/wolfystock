import { useCallback, useMemo, useRef, useState } from 'react';
import { backtestApi } from '../../api/backtest';
import { getParsedApiError } from '../../api/error';
import { getDefaultRuleDateRange } from '../backtest/shared';
import { buildPointAndShootStrategyText } from '../backtest/strategyCatalog';
import type { RuleBacktestRunResponse } from '../../types/backtest';
import type { ScannerCandidate } from '../../types/scanner';

const SCANNER_BACKTEST_CONCURRENCY = 2;
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

type Language = 'zh' | 'en';
type ScannerBacktestBatchCandidates = Record<ScannerBacktestBatchSource, ScannerCandidate[]>;

function normalizeCandidateSymbol(symbol?: string | null): string | null {
  const normalized = String(symbol || '').trim().toUpperCase();
  return normalized || null;
}

export function getScannerBacktestConfig() {
  const { startDate, endDate } = getDefaultRuleDateRange();
  return {
    startDate,
    endDate,
    initialCapital: SCANNER_BACKTEST_INITIAL_CAPITAL,
    feeBps: SCANNER_BACKTEST_FEE_BPS,
    slippageBps: SCANNER_BACKTEST_SLIPPAGE_BPS,
    benchmarkMode: SCANNER_BACKTEST_BENCHMARK_MODE,
    strategyTemplate: 'moving_average_crossover' as const,
  };
}

function getScannerBacktestKey(symbol: string): string {
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

function getBacktestErrorMessage(error: unknown, language: Language): string {
  if (error instanceof Error && error.message) return error.message;
  const parsed = getParsedApiError(error);
  return parsed.message || (error instanceof Error ? error.message : '') || (language === 'en' ? 'Backtest failed.' : '回测失败。');
}

function getSharpeFromRun(run: RuleBacktestRunResponse): number | null {
  const summary = run.summary || {};
  const value = summary.sharpe ?? summary.sharpeRatio ?? summary['sharpe_ratio'];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function mapRuleRunToScannerBacktestItem(run: RuleBacktestRunResponse, status: ScannerBacktestStatus = 'completed'): ScannerBacktestItem {
  return {
    symbol: normalizeCandidateSymbol(run.code) || run.code,
    status,
    resultId: run.id,
    totalReturnPct: run.totalReturnPct ?? null,
    maxDrawdownPct: run.maxDrawdownPct ?? null,
    sharpe: getSharpeFromRun(run),
    tradeCount: run.tradeCount ?? null,
    error: run.noResultMessage || run.statusMessage || null,
  };
}

function dedupeBacktestCandidates(candidates: ScannerCandidate[]): ScannerCandidate[] {
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

export function useScannerBacktestLab({
  language,
  batchCandidatesBySource,
}: {
  language: Language;
  batchCandidatesBySource: ScannerBacktestBatchCandidates;
}) {
  const [backtestItemsBySymbol, setBacktestItemsBySymbol] = useState<Record<string, ScannerBacktestItem>>({});
  const [isBacktestBatchRunning, setIsBacktestBatchRunning] = useState(false);
  const inFlightBacktestKeysRef = useRef<Set<string>>(new Set());
  const completedBacktestKeysRef = useRef<Map<string, ScannerBacktestItem>>(new Map());

  const backtestItems = useMemo(
    () => Object.values(backtestItemsBySymbol).sort((left, right) => left.symbol.localeCompare(right.symbol)),
    [backtestItemsBySymbol],
  );

  const backtestCounts = useMemo<Record<ScannerBacktestBatchSource, number>>(() => ({
    official_selected: dedupeBacktestCandidates(batchCandidatesBySource.official_selected).length,
    preview_selected: dedupeBacktestCandidates(batchCandidatesBySource.preview_selected).length,
    top_5: dedupeBacktestCandidates(batchCandidatesBySource.top_5).length,
    current_filter: dedupeBacktestCandidates(batchCandidatesBySource.current_filter).length,
  }), [
    batchCandidatesBySource.current_filter,
    batchCandidatesBySource.official_selected,
    batchCandidatesBySource.preview_selected,
    batchCandidatesBySource.top_5,
  ]);

  const runScannerBacktests = useCallback(async (source: ScannerBacktestSource, candidates: ScannerCandidate[]) => {
    const targetCandidates = dedupeBacktestCandidates(candidates);
    if (!targetCandidates.length) return;
    if (source !== 'manual' && isBacktestBatchRunning) return;

    const queue: ScannerCandidate[] = [];
    targetCandidates.forEach((candidate) => {
      const symbol = normalizeCandidateSymbol(candidate.symbol);
      if (!symbol) return;
      const key = getScannerBacktestKey(symbol);
      const existing = completedBacktestKeysRef.current.get(key);
      if (existing) {
        setBacktestItemsBySymbol((current) => ({
          ...current,
          [symbol]: { ...existing, status: 'skipped_existing' },
        }));
        return;
      }
      if (inFlightBacktestKeysRef.current.has(key)) return;
      inFlightBacktestKeysRef.current.add(key);
      queue.push({ ...candidate, symbol });
      setBacktestItemsBySymbol((current) => ({
        ...current,
        [symbol]: { symbol, status: 'queued' },
      }));
    });
    if (!queue.length) return;

    const config = getScannerBacktestConfig();
    const runOne = async (candidate: ScannerCandidate) => {
      const symbol = normalizeCandidateSymbol(candidate.symbol);
      if (!symbol) return;
      const key = getScannerBacktestKey(symbol);
      setBacktestItemsBySymbol((current) => ({
        ...current,
        [symbol]: { ...(current[symbol] || { symbol }), status: 'running' },
      }));
      try {
        const strategyText = buildPointAndShootStrategyText(language, config.strategyTemplate, {
          code: symbol,
          startDate: config.startDate,
          endDate: config.endDate,
          initialCapital: String(config.initialCapital),
        });
        const response = await backtestApi.runRuleBacktest({
          code: symbol,
          strategyText,
          startDate: config.startDate,
          endDate: config.endDate,
          lookbackBars: 252,
          initialCapital: config.initialCapital,
          feeBps: config.feeBps,
          slippageBps: config.slippageBps,
          benchmarkMode: config.benchmarkMode,
          confirmed: true,
          waitForCompletion: true,
        });
        const item = mapRuleRunToScannerBacktestItem(response, response.status === 'failed' ? 'failed' : 'completed');
        completedBacktestKeysRef.current.set(key, item);
        setBacktestItemsBySymbol((current) => ({
          ...current,
          [symbol]: item,
        }));
      } catch (error) {
        setBacktestItemsBySymbol((current) => ({
          ...current,
          [symbol]: {
            symbol,
            status: 'failed',
            error: getBacktestErrorMessage(error, language),
          },
        }));
      } finally {
        inFlightBacktestKeysRef.current.delete(key);
      }
    };

    if (source !== 'manual') setIsBacktestBatchRunning(true);
    try {
      for (let index = 0; index < queue.length; index += SCANNER_BACKTEST_CONCURRENCY) {
        await Promise.all(queue.slice(index, index + SCANNER_BACKTEST_CONCURRENCY).map(runOne));
      }
    } finally {
      if (source !== 'manual') setIsBacktestBatchRunning(false);
    }
  }, [isBacktestBatchRunning, language]);

  const handleBacktestCandidate = useCallback((candidate: ScannerCandidate) => {
    void runScannerBacktests('manual', [candidate]);
  }, [runScannerBacktests]);

  const handleBacktestBatch = useCallback((source: ScannerBacktestBatchSource) => {
    void runScannerBacktests(source, batchCandidatesBySource[source]);
  }, [batchCandidatesBySource, runScannerBacktests]);

  const getBacktestItem = useCallback((symbol?: string | null) => (
    backtestItemsBySymbol[normalizeCandidateSymbol(symbol) || '']
  ), [backtestItemsBySymbol]);

  const backtestUnavailableLabel = language === 'en'
    ? 'Backtest handoff requires a candidate symbol.'
    : '候选标的代码缺失时无法发起回测。';

  return {
    backtestCounts,
    backtestItems,
    backtestUnavailableLabel,
    getBacktestItem,
    handleBacktestBatch,
    handleBacktestCandidate,
    isBacktestBatchRunning,
  };
}
