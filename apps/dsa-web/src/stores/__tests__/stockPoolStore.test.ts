import { beforeEach, describe, expect, it, vi } from 'vitest';
import { analysisApi, DuplicateTaskError } from '../../api/analysis';
import { historyApi } from '../../api/history';
import { purgeZombieDashboardStorage, useStockPoolStore } from '../stockPoolStore';

vi.mock('../../api/history', () => ({
  historyApi: {
    getList: vi.fn(),
    getDetail: vi.fn(),
    deleteRecords: vi.fn(),
  },
}));

vi.mock('../../api/analysis', async () => {
  const actual = await vi.importActual<typeof import('../../api/analysis')>('../../api/analysis');
  return {
    ...actual,
    analysisApi: {
      analyzeAsync: vi.fn(),
    },
  };
});

const historyItem = {
  id: 1,
  queryId: 'q-1',
  stockCode: '600519',
  stockName: '贵州茅台',
  sentimentScore: 82,
  operationAdvice: '买入',
  createdAt: '2026-03-18T08:00:00Z',
};

const historyReport = {
  meta: {
    id: 1,
    queryId: 'q-1',
    stockCode: '600519',
    stockName: '贵州茅台',
    reportType: 'detailed' as const,
    createdAt: '2026-03-18T08:00:00Z',
  },
  summary: {
    analysisSummary: '趋势维持强势',
    operationAdvice: '继续观察买点',
    trendPrediction: '短线震荡偏强',
    sentimentScore: 78,
  },
};

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe('stockPoolStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    useStockPoolStore.getState().resetDashboardState();
  });

  it('loads initial history and auto-selects the first report', async () => {
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(historyReport);

    await useStockPoolStore.getState().loadInitialHistory();

    const state = useStockPoolStore.getState();
    expect(state.historyItems).toHaveLength(1);
    expect(state.selectedReport?.meta.stockCode).toBe('600519');
    expect(state.isLoadingHistory).toBe(false);
    expect(state.isLoadingReport).toBe(false);
  });

  it('deletes selected history and clears the selected report when nothing remains', async () => {
    useStockPoolStore.setState({
      historyItems: [historyItem],
      selectedHistoryIds: [1],
      selectedReport: historyReport,
    });

    vi.mocked(historyApi.deleteRecords).mockResolvedValue({ deleted: 1 });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    await useStockPoolStore.getState().deleteSelectedHistory();

    const state = useStockPoolStore.getState();
    expect(state.historyItems).toHaveLength(0);
    expect(state.selectedHistoryIds).toHaveLength(0);
    expect(state.selectedReport).toBeNull();
    expect(historyApi.getList).toHaveBeenCalledTimes(1);
  });

  it('clears report snapshots and selection after deleting all history records', async () => {
    useStockPoolStore.setState({
      historyItems: [historyItem],
      selectedReport: historyReport,
      reportSnapshotsByStockCode: {
        '600519': historyReport,
      },
    });

    vi.mocked(historyApi.deleteRecords).mockResolvedValue({ deleted: 1 });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    await useStockPoolStore.getState().deleteHistoryRecords([1], { deleteAll: true });

    const state = useStockPoolStore.getState();
    expect(historyApi.deleteRecords).toHaveBeenCalledWith([1], { deleteAll: true });
    expect(state.historyItems).toHaveLength(0);
    expect(state.selectedReport).toBeNull();
    expect(state.reportSnapshotsByStockCode).toEqual({});
    expect(window.localStorage.getItem('dsa-selected-history-id')).toBeNull();
  });

  it('deletes an explicit history record list and preserves other rows', async () => {
    const secondHistoryItem = {
      ...historyItem,
      id: 2,
      queryId: 'q-2',
      stockCode: 'AAPL',
      stockName: 'Apple',
    };
    const secondHistoryReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 2,
        queryId: 'q-2',
        stockCode: 'AAPL',
        stockName: 'Apple',
      },
    };

    useStockPoolStore.setState({
      historyItems: [historyItem, secondHistoryItem],
      selectedReport: historyReport,
    });

    vi.mocked(historyApi.deleteRecords).mockResolvedValue({ deleted: 1 });
    vi.mocked(historyApi.getDetail).mockResolvedValue(secondHistoryReport);
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 1,
      page: 1,
      limit: 20,
      items: [secondHistoryItem],
    });

    await useStockPoolStore.getState().deleteHistoryRecords([1]);

    const state = useStockPoolStore.getState();
    expect(historyApi.deleteRecords).toHaveBeenCalledWith([1], undefined);
    expect(state.historyItems.map((item) => item.id)).toEqual([2]);
    expect(state.selectedReport?.meta.id).toBe(2);
  });

  it('surfaces duplicate task errors without replacing the dashboard error state', async () => {
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValue(
      new DuplicateTaskError('600519', 'task-1', '股票 600519 正在分析中'),
    );

    useStockPoolStore.getState().setQuery('600519');
    await useStockPoolStore.getState().submitAnalysis();

    const state = useStockPoolStore.getState();
    expect(state.duplicateError).toContain('600519');
    expect(state.error).toBeNull();
    expect(state.isAnalyzing).toBe(false);
  });

  it('rejects obviously invalid mixed alphanumeric input before calling the API', async () => {
    useStockPoolStore.getState().setQuery('00aaaaa');

    await useStockPoolStore.getState().submitAnalysis();

    const state = useStockPoolStore.getState();
    expect(state.inputError).toBe('请输入有效的股票代码或股票名称');
    expect(state.isAnalyzing).toBe(false);
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
  });

  it('merges newly discovered history items during silent refresh', async () => {
    useStockPoolStore.setState({
      historyItems: [historyItem],
      currentPage: 1,
      hasMore: true,
    });

    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 2,
      page: 1,
      limit: 20,
      items: [
        { ...historyItem, id: 2, queryId: 'q-2', stockCode: 'AAPL', stockName: 'Apple' },
        historyItem,
      ],
    });

    await useStockPoolStore.getState().refreshHistory(true);

    const state = useStockPoolStore.getState();
    expect(state.historyItems.map((item) => item.id)).toEqual([2, 1]);
    expect(state.currentPage).toBe(1);
  });

  it('ignores late history responses after dashboard reset', async () => {
    const deferred = createDeferred<{
      total: number;
      page: number;
      limit: number;
      items: typeof historyItem[];
    }>();

    vi.mocked(historyApi.getList).mockImplementation(() => deferred.promise);

    const loadPromise = useStockPoolStore.getState().loadInitialHistory();
    useStockPoolStore.getState().resetDashboardState();

    deferred.resolve({
      total: 1,
      page: 1,
      limit: 20,
      items: [historyItem],
    });

    await loadPromise;

    const state = useStockPoolStore.getState();
    expect(state.historyItems).toHaveLength(0);
    expect(state.isLoadingHistory).toBe(false);
    expect(state.currentPage).toBe(1);
  });

  it('tracks task lifecycle updates and resets all dashboard state', () => {
    const pendingTask = {
      taskId: 'task-1',
      stockCode: '600519',
      stockName: '贵州茅台',
      status: 'pending' as const,
      progress: 0,
      reportType: 'detailed',
      createdAt: '2026-03-18T08:00:00Z',
    };

    useStockPoolStore.getState().syncTaskCreated(pendingTask);
    useStockPoolStore.getState().syncTaskUpdated({
      ...pendingTask,
      status: 'processing',
      progress: 60,
    });

    let state = useStockPoolStore.getState();
    expect(state.activeTasks).toHaveLength(1);
    expect(state.activeTasks[0].status).toBe('processing');

    useStockPoolStore.getState().removeTask('task-1');
    state = useStockPoolStore.getState();
    expect(state.activeTasks).toHaveLength(0);

    useStockPoolStore.setState({
      query: 'AAPL',
      selectedHistoryIds: [1],
      selectedReport: historyReport,
      markdownDrawerOpen: true,
      historyItems: [historyItem],
      highlightedHistoryId: 1,
      activeTasks: [
        {
          ...pendingTask,
          taskId: 'task-2',
          status: 'processing',
          progress: 80,
        },
      ],
    });
    window.localStorage.setItem('dsa-selected-history-id', '1');
    window.localStorage.setItem('dsa-task-queue-v1', '[{"taskId":"task-2"}]');

    useStockPoolStore.getState().resetDashboardState();
    state = useStockPoolStore.getState();
    expect(state.activeTasks).toHaveLength(0);
    expect(state.query).toBe('');
    expect(state.highlightedHistoryId).toBeNull();
    expect(state.selectedHistoryIds).toHaveLength(0);
    expect(state.selectedReport).toBeNull();
    expect(state.markdownDrawerOpen).toBe(false);
    expect(state.historyItems).toEqual([]);
    expect(window.localStorage.getItem('dsa-selected-history-id')).toBeNull();
    expect(window.localStorage.getItem('dsa-task-queue-v1')).toBeNull();
  });

  it('focuses the newest matching history item after a task completes', async () => {
    const latestHistoryItem = {
      ...historyItem,
      id: 2,
      queryId: 'q-2',
      stockCode: 'NVDA',
      stockName: 'NVIDIA',
      createdAt: '2026-03-19T09:00:00Z',
    };
    const latestHistoryReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        id: 2,
        queryId: 'q-2',
        stockCode: 'NVDA',
        stockName: 'NVIDIA',
      },
    };

    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 2,
      page: 1,
      limit: 20,
      items: [latestHistoryItem, historyItem],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(latestHistoryReport);

    const focusedId = await useStockPoolStore.getState().focusLatestHistoryForStock('NVDA');

    const state = useStockPoolStore.getState();
    expect(focusedId).toBe(2);
    expect(state.selectedReport?.meta.id).toBe(2);
    expect(state.highlightedHistoryId).toBe(2);
    expect(state.historyItems[0].id).toBe(2);
  });

  it('caches a loaded report snapshot and can later select it without refetching history detail', async () => {
    const cachedReport = {
      ...historyReport,
      meta: {
        ...historyReport.meta,
        stockCode: 'ORCL',
        stockName: 'Oracle',
      },
    };

    useStockPoolStore.setState({
      historyItems: [
        { ...historyItem, id: 2, queryId: 'q-2', stockCode: 'ORCL', stockName: 'Oracle' },
      ],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(cachedReport);

    await useStockPoolStore.getState().selectHistoryItem(2);
    vi.mocked(historyApi.getDetail).mockClear();

    const selectedFromCache = useStockPoolStore.getState().selectCachedHistoryForStock('ORCL');

    expect(selectedFromCache).toBe(true);
    expect(useStockPoolStore.getState().selectedReport?.meta.stockCode).toBe('ORCL');
    expect(historyApi.getDetail).not.toHaveBeenCalled();
    expect(window.localStorage.getItem('dsa-history-report-snapshots-v1')).toBeNull();
  });

  it('purges deprecated zombie dashboard storage keys on mount cleanup', () => {
    window.localStorage.setItem('dsa-history-report-snapshots-v1', JSON.stringify({
      NVDA: {
        meta: {
          stockCode: 'NVDA',
          stockName: '待确认股票',
        },
      },
    }));
    window.localStorage.setItem('recentHistory', JSON.stringify(['NVDA', 'TSLA']));
    window.localStorage.setItem('cachedHistory', JSON.stringify({
      stockName: '待确认股票',
    }));

    purgeZombieDashboardStorage();

    expect(window.localStorage.getItem('dsa-history-report-snapshots-v1')).toBeNull();
    expect(window.localStorage.getItem('recentHistory')).toBeNull();
    expect(window.localStorage.getItem('cachedHistory')).toBeNull();
  });

  it('does not cache zombie report snapshots from task results', () => {
    useStockPoolStore.setState({
      historyItems: [
        { ...historyItem, id: 2, queryId: 'q-2', stockCode: 'NVDA', stockName: 'NVIDIA' },
      ],
    });

    useStockPoolStore.getState().syncTaskCreated({
      taskId: 'task-zombie',
      stockCode: 'NVDA',
      stockName: '待确认股票',
      status: 'completed',
      progress: 100,
      reportType: 'detailed',
      createdAt: '2026-04-27T10:00:00Z',
      result: {
        report: {
          ...historyReport,
          meta: {
            ...historyReport.meta,
            id: 2,
            queryId: 'q-2',
            stockCode: 'NVDA',
            stockName: '待确认股票',
          },
          summary: {
            ...historyReport.summary,
            analysisSummary: '分析过程出错: All LLM models failed',
          },
        },
      },
    });

    expect(useStockPoolStore.getState().reportSnapshotsByStockCode).toEqual({});
    expect(useStockPoolStore.getState().selectCachedHistoryForStock('NVDA')).toBe(false);
  });

  it('normalizes nullable task progress modules from API snapshots', () => {
    useStockPoolStore.getState().syncTaskCreated({
      taskId: 'task-null-modules',
      stockCode: 'WULF',
      stockName: 'WULF',
      status: 'processing',
      progress: 12,
      message: 'Running AI analysis',
      reportType: 'detailed',
      createdAt: '2026-05-03T10:00:00Z',
      progressModules: null,
    } as never);

    expect(useStockPoolStore.getState().activeTasks[0].progressModules).toEqual([]);
  });

  it('ignores late task updates after a task has been removed', () => {
    const pendingTask = {
      taskId: 'task-1',
      stockCode: '600519',
      stockName: '贵州茅台',
      status: 'pending' as const,
      progress: 0,
      reportType: 'detailed',
      createdAt: '2026-03-18T08:00:00Z',
    };

    useStockPoolStore.getState().syncTaskCreated(pendingTask);
    useStockPoolStore.getState().removeTask('task-1');
    useStockPoolStore.getState().syncTaskUpdated({
      ...pendingTask,
      status: 'processing',
      progress: 35,
    });
    useStockPoolStore.getState().syncTaskCreated(pendingTask);

    expect(useStockPoolStore.getState().activeTasks).toHaveLength(0);
  });

  it('ignores unknown task updates after dashboard reset', () => {
    const pendingTask = {
      taskId: 'task-1',
      stockCode: '600519',
      stockName: '贵州茅台',
      status: 'pending' as const,
      progress: 0,
      reportType: 'detailed',
      createdAt: '2026-03-18T08:00:00Z',
    };

    useStockPoolStore.getState().syncTaskCreated(pendingTask);
    useStockPoolStore.getState().resetDashboardState();
    useStockPoolStore.getState().syncTaskUpdated({
      ...pendingTask,
      status: 'processing',
      progress: 35,
    });

    const state = useStockPoolStore.getState();
    expect(state.activeTasks).toHaveLength(0);
  });

  it('normalizes completed task reports before caching snapshots', () => {
    const pendingTask = {
      taskId: 'task-1',
      stockCode: 'NFLX',
      stockName: 'Netflix',
      status: 'pending' as const,
      progress: 0,
      reportType: 'detailed',
      createdAt: '2026-03-18T08:00:00Z',
    };

    useStockPoolStore.getState().syncTaskCreated(pendingTask);
    useStockPoolStore.getState().syncTaskUpdated({
      ...pendingTask,
      status: 'completed',
      progress: 100,
      result: {
        queryId: 'q-task-1',
        stockCode: 'NFLX',
        stockName: 'Netflix',
        createdAt: '2026-03-18T08:05:00Z',
        report: {
          meta: {
            queryId: 'q-task-1',
            stockCode: 'NFLX',
            stockName: 'Netflix',
            reportType: 'detailed',
            createdAt: '2026-03-18T08:05:00Z',
          },
          summary: {
            analysisSummary: 'Recovered from task payload.',
            operationAdvice: 'Hold',
            trendPrediction: 'Constructive',
            sentimentScore: 68,
          },
          details: {
            standard_report: {
              summary_panel: {
                ticker: 'NFLX',
                one_sentence: 'Recovered from task payload.',
              },
              decision_panel: {
                ideal_entry: '610-620',
              },
            },
          },
        },
      },
    });

    const snapshot = useStockPoolStore.getState().reportSnapshotsByStockCode.NFLX;
    expect(snapshot?.details?.standardReport?.summaryPanel?.ticker).toBe('NFLX');
    expect(snapshot?.details?.standardReport?.decisionPanel?.idealEntry).toBe('610-620');
  });

  it('does not backfill unknown failed tasks from SSE updates', () => {
    useStockPoolStore.getState().syncTaskFailed({
      taskId: 'task-404',
      stockCode: 'AAPL',
      stockName: 'Apple',
      status: 'failed',
      progress: 100,
      reportType: 'detailed',
      createdAt: '2026-03-18T08:00:00Z',
      error: '分析失败',
    });

    const state = useStockPoolStore.getState();
    expect(state.activeTasks).toHaveLength(0);
    expect(state.error).toBeTruthy();
  });
});
