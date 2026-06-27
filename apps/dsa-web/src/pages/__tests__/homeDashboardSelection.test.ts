import { describe, expect, it } from 'vitest';
import type { AnalysisReport, HistoryItem, TaskInfo } from '../../types/analysis';
import { resolveHomeDashboardSelection } from '../homeDashboardSelection';

function buildReport(stockCode: string, label = stockCode): AnalysisReport {
  return {
    meta: {
      id: Math.abs(Array.from(label).reduce((sum, char) => sum + char.charCodeAt(0), 0)),
      queryId: `report-${label}`,
      stockCode,
      stockName: label,
      reportType: 'detailed',
      createdAt: '2026-06-06T00:00:00Z',
    },
    summary: {
      analysisSummary: `${label} summary`,
      operationAdvice: 'Observe',
      trendPrediction: 'Neutral',
      sentimentScore: 50,
      sentimentLabel: 'Neutral',
    },
    strategy: {
      idealBuy: '-',
      stopLoss: '-',
      takeProfit: '-',
    },
    details: {
      standardReport: {
        summaryPanel: {
          stock: label,
          ticker: stockCode,
          oneSentence: `${label} summary`,
        },
        decisionContext: {
          shortTermView: `${label} context`,
        },
        decisionPanel: {
          idealEntry: '-',
          target: '-',
          stopLoss: '-',
          buildStrategy: `${label} strategy`,
        },
        reasonLayer: {
          coreReasons: [`${label} reason`],
        },
        technicalFields: [],
        fundamentalFields: [],
      },
    },
  } as AnalysisReport;
}

function buildTask(
  taskId: string,
  stockCode: string,
  status: TaskInfo['status'] = 'completed',
  report: AnalysisReport | null = buildReport(stockCode, `${taskId}-${stockCode}`),
): TaskInfo {
  return {
    taskId,
    stockCode,
    stockName: stockCode,
    status,
    progress: status === 'completed' ? 100 : 42,
    message: `${taskId}-${status}`,
    reportType: 'detailed',
    createdAt: '2026-06-06T00:00:00Z',
    updatedAt: '2026-06-06T00:02:00Z',
    result: report
      ? {
        queryId: `query-${taskId}`,
        stockCode,
        stockName: stockCode,
        createdAt: '2026-06-06T00:02:00Z',
        report,
      }
      : undefined,
  };
}

function buildHistoryItem(stockCode: string): HistoryItem {
  return {
    id: 1,
    queryId: `history-${stockCode || 'blank'}`,
    stockCode,
    stockName: stockCode,
    companyName: stockCode,
    createdAt: '2026-06-06T00:00:00Z',
    generatedAt: '2026-06-06T00:01:00Z',
    isTest: false,
  } as HistoryItem;
}

describe('resolveHomeDashboardSelection', () => {
  it('gives routed tasks precedence over selected history and local ticker state', () => {
    const routeReport = buildReport('WULF', 'route-wulf');
    const selectedReport = buildReport('TSLA', 'history-tsla');

    const result = resolveHomeDashboardSelection({
      activeTasks: [
        buildTask('task-wulf', 'WULF', 'completed', routeReport),
        buildTask('task-tsla', 'TSLA', 'completed', buildReport('TSLA', 'task-tsla')),
      ],
      routeTaskId: 'task-wulf',
      routeSymbol: 'WULF',
      activeTicker: 'ORCL',
      pendingAnalysisTicker: null,
      selectedReport,
      recentHistoryItems: [buildHistoryItem('ORCL')],
      defaultTicker: 'ORCL',
    });

    expect(result.focusedTask?.taskId).toBe('task-wulf');
    expect(result.completedTaskReport).toBe(routeReport);
    expect(result.dashboardReport).toBe(routeReport);
    expect(result.activeTraceReport).toBe(routeReport);
    expect(result.effectiveTicker).toBe('WULF');
  });

  it('prefers the completed task report for the active analysis ticker', () => {
    const completedReport = buildReport('AMD', 'task-amd');

    const result = resolveHomeDashboardSelection({
      activeTasks: [buildTask('task-amd', 'AMD', 'completed', completedReport)],
      routeTaskId: null,
      routeSymbol: null,
      activeTicker: 'AMD',
      pendingAnalysisTicker: null,
      selectedReport: buildReport('TSLA', 'history-tsla'),
      recentHistoryItems: [buildHistoryItem('ORCL')],
      defaultTicker: 'ORCL',
    });

    expect(result.completedTaskReport).toBe(completedReport);
    expect(result.dashboardReport).toBe(completedReport);
    expect(result.activeTraceReport).toBe(completedReport);
    expect(result.effectiveTicker).toBe('AMD');
  });

  it('falls back to the explicitly selected history report when no task owns the surface', () => {
    const selectedReport = buildReport('TSLA', 'history-tsla');

    const result = resolveHomeDashboardSelection({
      activeTasks: [],
      routeTaskId: null,
      routeSymbol: null,
      activeTicker: null,
      pendingAnalysisTicker: null,
      selectedReport,
      recentHistoryItems: [buildHistoryItem('ORCL')],
      defaultTicker: 'ORCL',
    });

    expect(result.completedTaskReport).toBeNull();
    expect(result.dashboardReport).toBe(selectedReport);
    expect(result.activeTraceReport).toBe(selectedReport);
    expect(result.effectiveTicker).toBe('TSLA');
  });

  it('keeps the pending placeholder ahead of restored history when the active ticker matches the pending ticker', () => {
    const result = resolveHomeDashboardSelection({
      activeTasks: [buildTask('task-nvda', 'NVDA', 'processing', null)],
      routeTaskId: null,
      routeSymbol: null,
      activeTicker: 'NVDA',
      pendingAnalysisTicker: 'NVDA',
      selectedReport: null,
      recentHistoryItems: [buildHistoryItem('ORCL')],
      defaultTicker: 'ORCL',
    });

    expect(result.dashboardReport).toBeNull();
    expect(result.shouldUsePendingPlaceholder).toBe(true);
    expect(result.effectiveTicker).toBe('NVDA');
    expect(result.focusedTask?.taskId).toBe('task-nvda');
  });

  it('rejects a stale completed task snapshot when selection came from opened history instead', () => {
    const selectedReport = buildReport('TSLA', 'history-tsla');

    const result = resolveHomeDashboardSelection({
      activeTasks: [buildTask('task-tsla', 'TSLA', 'completed', buildReport('TSLA', 'task-tsla'))],
      routeTaskId: null,
      routeSymbol: null,
      activeTicker: null,
      pendingAnalysisTicker: null,
      selectedReport,
      recentHistoryItems: [buildHistoryItem('TSLA')],
      defaultTicker: 'ORCL',
    });

    expect(result.completedTaskReport).toBeNull();
    expect(result.dashboardReport).toBe(selectedReport);
    expect(result.activeTraceReport).toBe(selectedReport);
  });

  it('rejects a symbol-less selected report when it owns the current surface', () => {
    const reportWithoutSymbol = buildReport('', 'blank-history');

    const result = resolveHomeDashboardSelection({
      activeTasks: [],
      routeTaskId: null,
      routeSymbol: null,
      activeTicker: null,
      pendingAnalysisTicker: null,
      selectedReport: reportWithoutSymbol,
      recentHistoryItems: [buildHistoryItem('')],
      defaultTicker: 'ORCL',
    });

    expect(result.activeTraceReport).toBe(reportWithoutSymbol);
    expect(result.activeEvidenceTicker).toBe('');
    expect(result.reanalysisTicker).toBe('');
  });

  it('keeps a valid active ticker rerunnable when a symbol-less selected report does not own the surface', () => {
    const reportWithoutSymbol = buildReport('', 'blank-history');

    const result = resolveHomeDashboardSelection({
      activeTasks: [],
      routeTaskId: null,
      routeSymbol: null,
      activeTicker: 'ORCL',
      pendingAnalysisTicker: null,
      selectedReport: reportWithoutSymbol,
      recentHistoryItems: [buildHistoryItem('')],
      defaultTicker: 'ORCL',
    });

    expect(result.dashboardReport).toBeNull();
    expect(result.activeTraceReport).toBeNull();
    expect(result.activeEvidenceTicker).toBe('ORCL');
    expect(result.reanalysisTicker).toBe('ORCL');
  });

  it('aligns the evidence ticker with the active trace report instead of a restored ticker', () => {
    const selectedReport = buildReport('TSLA', 'history-tsla');

    const result = resolveHomeDashboardSelection({
      activeTasks: [],
      routeTaskId: null,
      routeSymbol: null,
      activeTicker: 'ORCL',
      pendingAnalysisTicker: null,
      selectedReport,
      recentHistoryItems: [buildHistoryItem('ORCL')],
      defaultTicker: 'ORCL',
    });

    expect(result.dashboardReport).toBeNull();
    expect(result.activeTraceReport).toBeNull();
    expect(result.activeEvidenceTicker).toBe('ORCL');
    expect(result.reanalysisTicker).toBe('ORCL');
  });

  it('does not silently attach an AAPL history report to the selected ORCL surface', () => {
    const selectedReport = buildReport('AAPL', 'history-aapl');

    const result = resolveHomeDashboardSelection({
      activeTasks: [],
      routeTaskId: null,
      routeSymbol: null,
      activeTicker: 'ORCL',
      pendingAnalysisTicker: null,
      selectedReport,
      recentHistoryItems: [buildHistoryItem('AAPL')],
      defaultTicker: 'ORCL',
    });

    expect(result.effectiveTicker).toBe('ORCL');
    expect(result.dashboardReport).toBeNull();
    expect(result.activeTraceReport).toBeNull();
    expect(result.activeEvidenceTicker).toBe('ORCL');
  });

  it('does not fetch evidence from recent history when no report owns the surface', () => {
    const result = resolveHomeDashboardSelection({
      activeTasks: [],
      routeTaskId: null,
      routeSymbol: null,
      activeTicker: null,
      pendingAnalysisTicker: null,
      selectedReport: null,
      recentHistoryItems: [buildHistoryItem('ORCL')],
      defaultTicker: '',
    });

    expect(result.effectiveTicker).toBe('');
    expect(result.dashboardReport).toBeNull();
    expect(result.activeTraceReport).toBeNull();
    expect(result.activeEvidenceTicker).toBe('');
    expect(result.reanalysisTicker).toBe('');
  });
});
