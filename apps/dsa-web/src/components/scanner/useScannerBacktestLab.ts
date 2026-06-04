import { useRef, useState } from 'react';
import { getParsedApiError } from '../../api/error';
import type { RuleBacktestRunResponse } from '../../types/backtest';
import type { ScannerCandidate } from '../../types/scanner';
import {
  dedupeBacktestCandidates,
  getScannerBacktestConfig,
  getScannerBacktestKey,
  normalizeCandidateSymbol,
  type ScannerBacktestBatchSource,
  type ScannerBacktestItem,
  type ScannerBacktestSource,
  type ScannerBacktestStatus,
} from './scannerBacktestShared';

const SCANNER_BACKTEST_CONCURRENCY = 2;

type Language = 'zh' | 'en';
type ScannerBacktestBatchCandidates = Record<ScannerBacktestBatchSource, ScannerCandidate[]>;
type ScannerBacktestRuntime = Awaited<ReturnType<typeof loadScannerBacktestRuntime>>;

async function loadScannerBacktestRuntime() {
  const [{ backtestApi }, { buildPointAndShootStrategyText }] = await Promise.all([
    import('../../api/backtest'),
    import('../backtest/strategyCatalog'),
  ]);

  return {
    backtestApi,
    buildPointAndShootStrategyText,
  };
}

function getBacktestErrorMessage(error: unknown, language: Language): string {
  if (error instanceof Error && error.message) return error.message;
  const parsed = getParsedApiError(error);
  return parsed.message || (error instanceof Error ? error.message : '') || (language === 'en' ? 'Backtest failed.' : '回测失败。');
}

function getSharpeFromRun(run: RuleBacktestRunResponse): number | null {
  const summary = run.summary || {};
  const value = summary.sharpe ?? summary.sharpeRatio ?? summary.sharpe_ratio;
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

export function useScannerBacktestLab({
  language,
  batchCandidatesBySource,
}: {
  language: Language;
  batchCandidatesBySource: ScannerBacktestBatchCandidates;
}) {
  const [backtestItemsBySymbol, setBacktestItemsBySymbol] = useState<Record<string, ScannerBacktestItem>>({});
  const [isBacktestBatchRunning, setIsBacktestBatchRunning] = useState(false);
  const inFlightBacktestKeysRef = useRef<Set<string> | null>(null);
  const completedBacktestKeysRef = useRef<Map<string, ScannerBacktestItem> | null>(null);
  const runtimeRef = useRef<Promise<ScannerBacktestRuntime> | null>(null);
  if (inFlightBacktestKeysRef.current === null) {
    inFlightBacktestKeysRef.current = new Set();
  }
  if (completedBacktestKeysRef.current === null) {
    completedBacktestKeysRef.current = new Map();
  }
  const inFlightBacktestKeys = inFlightBacktestKeysRef.current;
  const completedBacktestKeys = completedBacktestKeysRef.current;

  const backtestItems = Object.values(backtestItemsBySymbol).sort((left, right) => left.symbol.localeCompare(right.symbol));

  const backtestCounts: Record<ScannerBacktestBatchSource, number> = {
    official_selected: dedupeBacktestCandidates(batchCandidatesBySource.official_selected).length,
    preview_selected: dedupeBacktestCandidates(batchCandidatesBySource.preview_selected).length,
    top_5: dedupeBacktestCandidates(batchCandidatesBySource.top_5).length,
    current_filter: dedupeBacktestCandidates(batchCandidatesBySource.current_filter).length,
  };

  const getRuntime = () => {
    if (!runtimeRef.current) {
      runtimeRef.current = loadScannerBacktestRuntime();
    }
    return runtimeRef.current;
  };

  const runScannerBacktests = async (source: ScannerBacktestSource, candidates: ScannerCandidate[]) => {
    const targetCandidates = dedupeBacktestCandidates(candidates);
    if (!targetCandidates.length) return;
    if (source !== 'manual' && isBacktestBatchRunning) return;

    const queue: ScannerCandidate[] = [];
    targetCandidates.forEach((candidate) => {
      const symbol = normalizeCandidateSymbol(candidate.symbol);
      if (!symbol) return;
      const key = getScannerBacktestKey(symbol);
      const existing = completedBacktestKeys.get(key);
      if (existing) {
        setBacktestItemsBySymbol((current) => ({
          ...current,
          [symbol]: { ...existing, status: 'skipped_existing' },
        }));
        return;
      }
      if (inFlightBacktestKeys.has(key)) return;
      inFlightBacktestKeys.add(key);
      queue.push({ ...candidate, symbol });
      setBacktestItemsBySymbol((current) => ({
        ...current,
        [symbol]: { symbol, status: 'queued' },
      }));
    });
    if (!queue.length) return;

    const config = getScannerBacktestConfig();
    const runtime = await getRuntime();
    const runOne = async (candidate: ScannerCandidate) => {
      const symbol = normalizeCandidateSymbol(candidate.symbol);
      if (!symbol) return;
      const key = getScannerBacktestKey(symbol);
      setBacktestItemsBySymbol((current) => ({
        ...current,
        [symbol]: { ...(current[symbol] || { symbol }), status: 'running' },
      }));
      try {
        const strategyText = runtime.buildPointAndShootStrategyText(language, config.strategyTemplate, {
          code: symbol,
          startDate: config.startDate,
          endDate: config.endDate,
          initialCapital: String(config.initialCapital),
        });
        const response = await runtime.backtestApi.runRuleBacktest({
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
        completedBacktestKeys.set(key, item);
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
        inFlightBacktestKeys.delete(key);
      }
    };

    if (source !== 'manual') setIsBacktestBatchRunning(true);
    try {
      const runBatch = async (startIndex: number): Promise<void> => {
        if (startIndex >= queue.length) return;
        await Promise.all(queue.slice(startIndex, startIndex + SCANNER_BACKTEST_CONCURRENCY).map(runOne));
        await runBatch(startIndex + SCANNER_BACKTEST_CONCURRENCY);
      };

      await runBatch(0);
    } finally {
      if (source !== 'manual') setIsBacktestBatchRunning(false);
    }
  };

  const handleBacktestCandidate = (candidate: ScannerCandidate) => {
    void runScannerBacktests('manual', [candidate]);
  };

  const handleBacktestBatch = (source: ScannerBacktestBatchSource) => {
    void runScannerBacktests(source, batchCandidatesBySource[source]);
  };

  const getBacktestItem = (symbol?: string | null) => (
    backtestItemsBySymbol[normalizeCandidateSymbol(symbol) || '']
  );

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

export type {
  ScannerBacktestBatchSource,
  ScannerBacktestItem,
  ScannerBacktestSource,
  ScannerBacktestStatus,
} from './scannerBacktestShared';
