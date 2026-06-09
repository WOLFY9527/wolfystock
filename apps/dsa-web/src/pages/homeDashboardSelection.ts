import type { AnalysisReport, HistoryItem, TaskInfo } from '../types/analysis';
import { getSymbolDisplay } from '../utils/homeReportIdentity';

const HOME_TICKER_ALIASES: Record<string, string> = {
  NVIDIA: 'NVDA',
  '英伟达': 'NVDA',
  ORACLE: 'ORCL',
  '甲骨文': 'ORCL',
  TESLA: 'TSLA',
  '特斯拉': 'TSLA',
};

const HOME_TICKER_FORMAT_RE = /^[A-Z]{1,5}$|^\d{6}$/;

function normalizeHomeTickerQuery(rawValue?: string | null): string {
  const trimmed = String(rawValue || '').trim();
  if (!trimmed) {
    return '';
  }

  return HOME_TICKER_ALIASES[trimmed.toUpperCase()] || HOME_TICKER_ALIASES[trimmed] || trimmed.toUpperCase();
}

function findCompletedTaskReportByTicker(activeTasks: TaskInfo[], ticker: string): AnalysisReport | null {
  if (!ticker) {
    return null;
  }

  return activeTasks.find(
    (task) => normalizeHomeTickerQuery(task.stockCode) === ticker && task.status === 'completed' && task.result?.report,
  )?.result?.report || null;
}

export type HomeDashboardSelectionInput = {
  activeTasks: TaskInfo[];
  routeTaskId: string | null;
  routeSymbol: string | null;
  activeTicker: string | null;
  pendingAnalysisTicker: string | null;
  selectedReport: AnalysisReport | null;
  recentHistoryItems: Pick<HistoryItem, 'stockCode'>[];
  defaultTicker: string;
};

export type HomeDashboardSelectionResult = {
  selectedTicker: string;
  completedTaskReport: AnalysisReport | null;
  focusedTask: TaskInfo | null;
  effectiveTicker: string;
  dashboardReport: AnalysisReport | null;
  shouldUsePendingPlaceholder: boolean;
  activeTraceReport: AnalysisReport | null;
  activeEvidenceTicker: string;
  reanalysisTicker: string;
};

export function resolveHomeDashboardSelection(
  input: HomeDashboardSelectionInput,
): HomeDashboardSelectionResult {
  const routeSymbol = normalizeHomeTickerQuery(input.routeSymbol);
  const activeTicker = normalizeHomeTickerQuery(input.activeTicker);
  const pendingAnalysisTicker = normalizeHomeTickerQuery(input.pendingAnalysisTicker);
  const selectedTicker = normalizeHomeTickerQuery(getSymbolDisplay(input.selectedReport));
  const restoredTicker = normalizeHomeTickerQuery(input.recentHistoryItems[0]?.stockCode);
  const defaultTicker = normalizeHomeTickerQuery(input.defaultTicker);

  const completedTaskReport = input.routeTaskId
    ? input.activeTasks.find(
      (task) => task.taskId === input.routeTaskId && task.status === 'completed' && task.result?.report,
    )?.result?.report || null
    : findCompletedTaskReportByTicker(input.activeTasks, pendingAnalysisTicker || activeTicker);

  const focusedTask = (() => {
    if (input.routeTaskId) {
      const matchedById = input.activeTasks.find((task) => task.taskId === input.routeTaskId);
      if (matchedById) {
        return matchedById;
      }
    }

    const taskTicker = pendingAnalysisTicker || activeTicker;
    if (taskTicker) {
      const matchedByTicker = input.activeTasks.find((task) => normalizeHomeTickerQuery(task.stockCode) === taskTicker);
      if (matchedByTicker) {
        return matchedByTicker;
      }
    }

    return input.activeTasks[0] || null;
  })();

  const effectiveTicker = routeSymbol || activeTicker || selectedTicker || restoredTicker || defaultTicker;
  const completedTaskTicker = normalizeHomeTickerQuery(completedTaskReport?.meta.stockCode);

  const dashboardReport = (() => {
    if (completedTaskReport && effectiveTicker && completedTaskTicker === effectiveTicker) {
      return completedTaskReport;
    }

    if (input.selectedReport && effectiveTicker && selectedTicker === effectiveTicker) {
      return input.selectedReport;
    }

    return null;
  })();

  const shouldUsePendingPlaceholder = Boolean(
    !dashboardReport
    && pendingAnalysisTicker
    && effectiveTicker === pendingAnalysisTicker,
  );

  const activeTraceReport = (() => {
    const traceTicker = routeSymbol || activeTicker || pendingAnalysisTicker || selectedTicker || '';
    if (completedTaskReport && traceTicker && completedTaskTicker === traceTicker) {
      return completedTaskReport;
    }
    if (input.selectedReport && (!traceTicker || selectedTicker === traceTicker)) {
      return input.selectedReport;
    }
    if (!traceTicker) {
      return completedTaskReport || input.selectedReport || null;
    }
    return null;
  })();

  const activeEvidenceTickerCandidate = normalizeHomeTickerQuery(
    activeTraceReport?.meta.stockCode
      || routeSymbol
      || activeTicker
      || selectedTicker
      || restoredTicker,
  );
  const activeEvidenceTicker = HOME_TICKER_FORMAT_RE.test(activeEvidenceTickerCandidate) ? activeEvidenceTickerCandidate : '';

  const reportTicker = normalizeHomeTickerQuery(getSymbolDisplay(activeTraceReport));
  const reanalysisCandidate = input.selectedReport && !selectedTicker
    ? ''
    : reportTicker || (activeTraceReport ? '' : effectiveTicker);
  const reanalysisTicker = HOME_TICKER_FORMAT_RE.test(reanalysisCandidate) ? reanalysisCandidate : '';

  return {
    selectedTicker,
    completedTaskReport,
    focusedTask,
    effectiveTicker,
    dashboardReport,
    shouldUsePendingPlaceholder,
    activeTraceReport,
    activeEvidenceTicker,
    reanalysisTicker,
  };
}
