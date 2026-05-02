import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { translate } from '../../i18n/core';
import AdminLogsPage from '../AdminLogsPage';

const { listBusinessEvents, getBusinessEventDetail, listSessions, getSessionDetail, getStorageSummary, cleanupLogs } = vi.hoisted(() => ({
  listBusinessEvents: vi.fn(),
  getBusinessEventDetail: vi.fn(),
  listSessions: vi.fn(),
  getSessionDetail: vi.fn(),
  getStorageSummary: vi.fn(),
  cleanupLogs: vi.fn(),
}));

vi.mock('../../api/adminLogs', () => ({
  adminLogsApi: {
    listBusinessEvents,
    getBusinessEventDetail,
    listSessions,
    getSessionDetail,
    getStorageSummary,
    cleanupLogs,
  },
}));

let mockLanguage: 'zh' | 'en' = 'zh';

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: mockLanguage,
    t: (key: string, params?: Record<string, string | number | undefined>) => translate(mockLanguage, key, params),
  }),
}));

vi.mock('../../components/common', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../components/common')>();
  return {
    ...actual,
    ApiErrorAlert: ({ error }: { error: { title: string; message: string } }) => (
      <div role="alert" data-testid="api-error-alert">
        <strong>{error.title}</strong>
        <span>{error.message}</span>
      </div>
    ),
  };
});

const businessEvents = [
  {
    id: 'analysis-tsla',
    event: 'TSLA',
    category: 'analysis',
    type: 'stock_analysis',
    eventType: 'stock_analysis',
    status: 'partial',
    summary: '用户分析 TSLA，部分数据源失败',
    symbol: 'TSLA',
    market: 'US',
    actorType: 'user',
    actorLabel: 'alice',
    contextLabel: 'TSLA',
    provider: 'newsapi',
    source: 'Yahoo',
    reason: 'timeout',
    errorSummary: 'News API timeout after 3000ms token=***',
    requestId: 'req-tsla-123456789',
    traceId: 'trace-tsla-abcdef',
    rootCauseSummary: 'News API timeout after 3000ms token=***',
    stepTraceAvailable: true,
    startedAt: '2026-04-30T13:20:00Z',
    durationMs: 12345,
    stepCount: 4,
    successStepCount: 3,
    failedStepCount: 1,
    skippedStepCount: 0,
    unknownStepCount: 0,
    recordId: 'record-tsla',
  },
  {
    id: 'market-card-failed',
    event: 'MarketSentimentCard',
    category: 'data_source',
    type: 'market_overview_fetch',
    eventType: 'ExternalSourceTimeout',
    status: 'failed',
    summary: 'MarketSentimentCard refresh failed',
    subject: 'MarketSentimentCard',
    component: 'MarketSentimentCard',
    contextLabel: 'MarketSentimentCard',
    route: '/market-overview',
    endpoint: '/api/v1/market-overview/sentiment',
    provider: 'finnhub',
    source: 'market_overview',
    actorType: 'anonymous',
    actorLabel: 'anonymous',
    reason: 'timeout',
    errorSummary: 'provider timeout token=***',
    requestId: 'req-market-card-123456',
    traceId: 'trace-market-card-abcdef',
    stepTraceAvailable: false,
    startedAt: '2026-04-30T13:10:00Z',
    durationMs: 0,
    stepCount: 0,
    successStepCount: 0,
    failedStepCount: 0,
    skippedStepCount: 0,
    unknownStepCount: 0,
    metadata: {},
  },
  {
    id: 'analysis-aapl',
    event: 'AAPL',
    category: 'analysis',
    type: 'stock_analysis',
    status: 'success',
    summary: '用户分析 AAPL',
    symbol: 'AAPL',
    market: 'US',
    startedAt: '2026-04-30T12:20:00Z',
    durationMs: 4300,
    stepCount: 4,
    successStepCount: 4,
    failedStepCount: 0,
    skippedStepCount: 0,
    unknownStepCount: 0,
    recordId: 'record-aapl',
  },
  {
    id: 'provider-fallback-success',
    event: 'ProviderFallbackServed',
    category: 'data_source',
    type: 'provider_fallback',
    eventType: 'DataSourceFallback',
    status: 'success',
    summary: 'Primary provider failed, fallback source served cached data',
    subject: 'market overview',
    actorType: 'system',
    actorLabel: 'scheduler',
    contextLabel: 'US market snapshot',
    route: '/admin/logs',
    endpoint: '/api/v1/market-overview',
    provider: 'alpaca',
    source: 'finnhub',
    reason: 'fallback_used',
    errorSummary: 'Primary provider timeout, fallback source completed',
    requestId: 'req-fallback-123456',
    traceId: 'trace-fallback-abcdef',
    rootCauseSummary: 'Primary provider timeout',
    stepTraceAvailable: true,
    startedAt: '2026-04-30T12:00:00Z',
    durationMs: 900,
    stepCount: 2,
    successStepCount: 1,
    failedStepCount: 0,
    skippedStepCount: 1,
    unknownStepCount: 0,
    metadata: { apiKey: 'FRONTENDSECRET', token: 'FRONTENDTOKEN' },
  },
  {
    id: 'scanner-mainland',
    event: 'Scanner: 大盘单机游戏',
    category: 'scanner',
    type: 'scan_run',
    status: 'success',
    summary: '扫描器运行：大盘单机游戏',
    subject: '大盘单机游戏',
    scannerId: 'scanner-mainland',
    startedAt: '2026-04-30T11:20:00Z',
    durationMs: 2200,
    stepCount: 3,
    successStepCount: 2,
    skippedStepCount: 1,
    failedStepCount: 0,
    unknownStepCount: 0,
    metadata: { matchedCount: 18 },
  },
  {
    id: 'backtest-ma20',
    event: 'Backtest: MA20 Breakout',
    category: 'backtest',
    type: 'backtest_run',
    status: 'success',
    summary: '回测策略 MA20 Breakout',
    subject: 'MA20 Breakout',
    strategyId: 'strategy-ma20',
    backtestId: 'bt-1',
    startedAt: '2026-04-30T10:20:00Z',
    durationMs: 5200,
    stepCount: 3,
    successStepCount: 3,
    skippedStepCount: 0,
    failedStepCount: 0,
    unknownStepCount: 0,
    metadata: { startDate: '2024-01-01', endDate: '2024-12-31' },
  },
];

const businessDetail = {
  ...businessEvents[0],
  stepCount: 6,
  successStepCount: 2,
  skippedStepCount: 2,
  failedStepCount: 1,
  unknownStepCount: 1,
  steps: [
    {
      name: 'fetch_quote',
      label: '获取行情',
      provider: 'yahoo',
      status: 'success',
      startedAt: '2026-04-30T13:20:00Z',
      finishedAt: '2026-04-30T13:20:00.320Z',
      durationMs: 320,
      metadata: { symbol: 'TSLA' },
    },
    {
      name: 'fetch_news',
      label: '获取新闻',
      provider: 'newsapi',
      status: 'failed',
      startedAt: '2026-04-30T13:20:01Z',
      finishedAt: '2026-04-30T13:20:04Z',
      durationMs: 3000,
      errorType: 'TimeoutError',
      errorMessage: 'News API timeout after 3000ms token=FRONTENDTOKEN',
      metadata: { source: 'newsapi', apiKey: 'FRONTENDSECRET', nested: { token: 'FRONTENDTOKEN' } },
    },
    {
      name: 'fetch_fundamentals',
      label: '获取财务数据',
      provider: 'fmp',
      status: 'skipped',
      reason: 'previous_provider_succeeded',
      message: '主数据源已成功，无需调用备用源',
      durationMs: 0,
      metadata: { apiKey: '***' },
    },
    {
      name: 'ai_analysis',
      label: 'AI 分析',
      provider: 'gemini',
      model: 'gemini-2.5-flash',
      status: 'success',
      message: 'AI model gemini/gemini-2.5-flash succeeded',
      durationMs: 4600,
      metadata: {},
    },
    {
      name: 'ai_analysis',
      label: 'AI 分析',
      provider: 'deepseek',
      model: 'deepseek-v4-pro',
      status: 'skipped',
      reason: 'previous_model_succeeded',
      message: '主模型已成功，无需调用备用模型',
      durationMs: 0,
      metadata: {},
    },
    {
      name: 'save_record',
      label: '保存分析记录',
      status: 'unknown',
      message: '旧数据未记录结束事件',
      recordId: 'record-tsla',
      metadata: {},
    },
  ],
};

const failedNoStepDetail = {
  ...businessEvents[1],
  steps: [],
};

const fallbackSuccessDetail = {
  ...businessEvents[3],
  steps: [
    {
      name: 'primary_provider',
      label: 'Primary provider',
      provider: 'alpaca',
      status: 'skipped',
      reason: 'provider_unhealthy',
      message: 'Primary provider unhealthy; fallback used',
      metadata: { apiKey: 'FRONTENDSECRET' },
    },
    {
      name: 'fallback_provider',
      label: 'Fallback provider',
      provider: 'finnhub',
      status: 'success',
      message: 'Fallback provider completed',
      metadata: {},
    },
  ],
};

const rawSessions = [
  {
    sessionId: 'raw-timeout',
    name: 'ExternalSourceTimeout',
    overallStatus: 'failed',
    startedAt: '2026-04-30T13:21:00Z',
    readableSummary: {
      logLevel: 'WARNING',
      logCategory: 'data_source',
      eventName: 'ExternalSourceTimeout',
      eventMessage: 'source timeout',
      source: 'newsapi',
      operationTarget: 'newsapi',
    },
  },
];

describe('AdminLogsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
    mockLanguage = 'zh';
    listBusinessEvents.mockResolvedValue({
      total: businessEvents.length,
      limit: 20,
      offset: 0,
      hasMore: true,
      items: businessEvents,
      healthSummary: {
        totalEvents: businessEvents.length,
        failedEvents: 1,
        warningEvents: 1,
        slowEvents: 1,
        failureRate: 0.2,
        status: 'degraded',
        failuresByCategory: [{ key: 'data_source', label: 'data_source', count: 1 }],
        failuresByProvider: [{ key: 'finnhub', label: 'finnhub', count: 1 }],
        failuresByReason: [{ key: 'timeout', label: 'timeout', count: 2 }],
        actorBreakdown: [{ key: 'user', label: 'user', count: 2 }],
        topRecentErrors: [
          {
            id: 'market-card-failed',
            event: 'MarketSentimentCard',
            category: 'data_source',
            provider: 'finnhub',
            reason: 'timeout',
            errorSummary: 'provider timeout token=***',
            startedAt: '2026-04-30T13:10:00Z',
            status: 'failed',
          },
        ],
        latestCriticalError: null,
      },
    });
    getBusinessEventDetail.mockImplementation((eventId: string) => (
      eventId === 'market-card-failed'
        ? Promise.resolve(failedNoStepDetail)
        : eventId === 'provider-fallback-success'
          ? Promise.resolve(fallbackSuccessDetail)
        : Promise.resolve(businessDetail)
    ));
    listSessions.mockResolvedValue({
      total: rawSessions.length,
      items: rawSessions,
      summary: {
        errorCount: 0,
        warningCount: 1,
        dataSourceFailureCount: 1,
        slowRequestCount: 0,
        latestCriticalAt: null,
      },
    });
    getSessionDetail.mockResolvedValue({ ...rawSessions[0], events: [], operationDetail: {} });
    getStorageSummary.mockResolvedValue({
      totalLogCount: 120000,
      totalEventCount: 180000,
      oldestLogTimestamp: '2026-01-01T00:00:00Z',
      newestLogTimestamp: '2026-04-30T13:21:00Z',
      retentionDays: 90,
      retentionCutoff: '2026-01-30T00:00:00Z',
      logsOlderThanRetentionCount: 120,
      estimatedStorageBytes: 10485760,
      warningThresholdCount: 50000,
      criticalThresholdCount: 100000,
      status: 'critical',
      recommendedCleanupAction: 'Preview cleanup, then delete logs older than retention.',
      lastCleanupTimestamp: null,
    });
    cleanupLogs.mockResolvedValue({
      dryRun: true,
      cutoff: '2026-01-30T00:00:00Z',
      matchedLogCount: 120,
      matchedEventCount: 180,
      deletedLogCount: 0,
      deletedEventCount: 0,
      statusFilter: null,
      categoryFilter: null,
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('defaults to business events and does not show raw step names as the main list', async () => {
    render(<AdminLogsPage />);

    expect(screen.getByTestId('admin-logs-workspace')).toHaveClass('w-full', 'flex-1', 'min-w-0', 'overflow-x-hidden');
    expect(screen.getByRole('tab', { name: '业务事件' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '股票分析' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '扫描器' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '回测' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '数据源' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '安全事件' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '原始日志' })).toBeInTheDocument();
    expect(screen.getByTestId('admin-logs-filter-bar')).toBeInTheDocument();
    expect(await screen.findByTestId('admin-logs-health-summary')).toBeInTheDocument();
    expect(await screen.findByTestId('admin-logs-storage-summary')).toHaveTextContent('120000');
    expect(screen.getByTestId('admin-logs-storage-summary')).toHaveTextContent('90');
    expect(screen.getByTestId('admin-logs-storage-summary')).toHaveTextContent('120 older');
    expect(screen.getByText('Critical')).toBeInTheDocument();
    expect(screen.getAllByText('Degraded').length).toBeGreaterThan(0);
    expect(screen.getByText('1 / 6')).toBeInTheDocument();
    expect(screen.getByText('finnhub')).toBeInTheDocument();
    expect(screen.getAllByText('provider timeout token=***').length).toBeGreaterThan(0);
    expect(screen.queryByText(/FRONTENDSECRET|FRONTENDTOKEN/)).not.toBeInTheDocument();
    expect(screen.getByLabelText('搜索日志')).toBeInTheDocument();
    expect(screen.getByLabelText('状态筛选')).toBeInTheDocument();
    expect(screen.getByLabelText('时间范围')).toBeInTheDocument();
    expect(screen.queryByTestId('admin-logs-summary-grid')).not.toBeInTheDocument();
    expect((await screen.findAllByText('TSLA')).length).toBeGreaterThan(0);
    expect(screen.getByText('Actor')).toBeInTheDocument();
    expect(screen.getByText('Context')).toBeInTheDocument();
    expect(screen.getByText('Source / Provider')).toBeInTheDocument();
    expect(screen.getByText('Reason')).toBeInTheDocument();
    expect(screen.queryByText('Trace')).not.toBeInTheDocument();
    expect(screen.getByText('状态 / 严重度')).toBeInTheDocument();
    expect(screen.queryByText('耗时')).not.toBeInTheDocument();
    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('newsapi')).toBeInTheDocument();
    expect(screen.getByText('ProviderFallbackServed')).toBeInTheDocument();
    const fallbackRowLabel = screen.getByText('ProviderFallbackServed');
    const fallbackRow = fallbackRowLabel.closest('[data-testid="business-event-row"]');
    expect(fallbackRow).not.toBeNull();
    expect(within(fallbackRow as HTMLElement).getByTestId('event-severity-pill')).toHaveTextContent('Degraded');
    expect(within(fallbackRow as HTMLElement).getByTestId('event-severity-pill')).toHaveClass('text-amber-100');
    expect(within(fallbackRow as HTMLElement).getByTestId('event-severity-pill')).not.toHaveClass('text-rose-100');
    expect(screen.getAllByText('MarketSentimentCard').length).toBeGreaterThan(0);
    expect(screen.getByText('失败 · 无步骤明细')).toBeInTheDocument();
    expect(screen.queryByText('成功 0 · 跳过 0 · 失败 0 · 未确认 0')).not.toBeInTheDocument();
    expect(screen.getByText('Scanner: 大盘单机游戏')).toBeInTheDocument();
    expect(screen.getByText('Backtest: MA20 Breakout')).toBeInTheDocument();
    expect(screen.getByTestId('business-events-table-shell')).toHaveClass('overflow-x-auto');
    expect(screen.getByTestId('admin-logs-pagination')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '上一页' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '下一页' })).toBeInTheDocument();
    expect(screen.queryByText('fetch_news')).not.toBeInTheDocument();
    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({ since: '24h', limit: 20, offset: 0 })));
  });

  it('previews and confirms retention cleanup, then refreshes logs and storage summary', async () => {
    cleanupLogs
      .mockResolvedValueOnce({
        dryRun: true,
        cutoff: '2026-01-30T00:00:00Z',
        matchedLogCount: 120,
        matchedEventCount: 180,
        deletedLogCount: 0,
        deletedEventCount: 0,
        statusFilter: null,
        categoryFilter: null,
      })
      .mockResolvedValueOnce({
        dryRun: false,
        cutoff: '2026-01-30T00:00:00Z',
        matchedLogCount: 120,
        matchedEventCount: 180,
        deletedLogCount: 120,
        deletedEventCount: 180,
        statusFilter: null,
        categoryFilter: null,
      });

    render(<AdminLogsPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Preview cleanup' }));
    await waitFor(() => expect(cleanupLogs).toHaveBeenCalledWith({ useRetention: true, dryRun: true }));
    expect(await screen.findByText(/120 logs would be deleted/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Clean logs older than retention' }));
    await waitFor(() => expect(window.confirm).toHaveBeenCalled());
    await waitFor(() => expect(cleanupLogs).toHaveBeenLastCalledWith({ useRetention: true, dryRun: false }));
    expect(await screen.findByText(/Deleted 120 logs/)).toBeInTheDocument();
    expect(getStorageSummary).toHaveBeenCalledTimes(2);
    expect(listBusinessEvents).toHaveBeenCalled();
  });

  it('does not run destructive cleanup when confirmation is declined', async () => {
    (window.confirm as ReturnType<typeof vi.fn>).mockReturnValueOnce(false);

    render(<AdminLogsPage />);

    fireEvent.click(await screen.findByRole('button', { name: 'Clean logs older than retention' }));

    await waitFor(() => expect(window.confirm).toHaveBeenCalled());
    expect(cleanupLogs).not.toHaveBeenCalled();
  });

  it('filters the stock-analysis view by symbol, status, time range, and pagination', async () => {
    render(<AdminLogsPage />);

    fireEvent.click(await screen.findByRole('tab', { name: '股票分析' }));
    fireEvent.change(screen.getByLabelText('搜索日志'), { target: { value: 'TSLA' } });
    fireEvent.change(screen.getByLabelText('状态筛选'), { target: { value: 'partial' } });
    fireEvent.change(screen.getByLabelText('时间范围'), { target: { value: '1h' } });

    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({
      category: 'analysis',
      symbol: 'TSLA',
      status: 'partial',
      since: '1h',
    })));

    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 20 })));
  });

  it('opens business-event detail with call-chain steps and failed error message', async () => {
    render(<AdminLogsPage />);

    const row = (await screen.findAllByText('TSLA'))[0];
    const rowContainer = row.closest('[data-testid="business-event-row"]');
    expect(rowContainer).not.toBeNull();
    fireEvent.click(within(rowContainer as HTMLElement).getByRole('button', { name: translate('zh', 'adminLogs.viewDetails') }));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByTestId('admin-logs-workspace')).toHaveClass('overflow-x-hidden');
    expect(screen.getByTestId('business-events-table-shell')).toHaveClass('overflow-x-auto');
    expect(screen.getByText('调用链 timeline')).toBeInTheDocument();
    expect(screen.getByTestId('root-cause-section')).toBeInTheDocument();
    expect(screen.queryByText('Root Cause')).not.toBeInTheDocument();
    expect(screen.getByText('Degradation Summary')).toBeInTheDocument();
    expect(screen.getAllByText(/alice/).length).toBeGreaterThan(0);
    expect(screen.getByText(/trace-tsla-abcdef/)).toBeInTheDocument();
    expect(screen.getByText(/获取行情/)).toBeInTheDocument();
    expect(screen.getByText(/获取新闻/)).toBeInTheDocument();
    expect(screen.getByText(/获取财务数据/)).toBeInTheDocument();
    expect(screen.getAllByText(/AI 分析/).length).toBeGreaterThan(0);
    expect(screen.getByText(/保存分析记录/)).toBeInTheDocument();
    expect(screen.getAllByText('News API timeout after 3000ms token=***').length).toBeGreaterThan(0);
    expect(screen.queryByText(/FRONTENDSECRET/)).not.toBeInTheDocument();
    expect(screen.queryByText(/FRONTENDTOKEN/)).not.toBeInTheDocument();
    expect(screen.getAllByText('主数据源已成功，无需调用备用源').length).toBeGreaterThan(0);
    expect(screen.getAllByText('主模型已成功，无需调用备用模型').length).toBeGreaterThan(0);
    expect(screen.getByText(/步骤统计/)).toBeInTheDocument();
    expect(screen.getByText('成功 2 · 跳过 2 · 失败 1 · 未确认 1')).toBeInTheDocument();
    expect(document.querySelector('[data-status="success"]')).not.toBeNull();
    expect(document.querySelector('[data-status="skipped"]')).not.toBeNull();
    expect(document.querySelector('[data-status="failed"]')).not.toBeNull();
    expect(document.querySelector('[data-status="unknown"]')).not.toBeNull();
  });

  it('shows degraded execution summary for successful fallback events and copies a sanitized debug summary', async () => {
    render(<AdminLogsPage />);

    const row = await screen.findByText('ProviderFallbackServed');
    const rowContainer = row.closest('[data-testid="business-event-row"]');
    expect(rowContainer).not.toBeNull();
    fireEvent.click(within(rowContainer as HTMLElement).getByRole('button', { name: translate('zh', 'adminLogs.viewDetails') }));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.queryByText('Root Cause')).not.toBeInTheDocument();
    expect(screen.getByText('Degradation Summary')).toBeInTheDocument();
    const summarySection = screen.getByTestId('root-cause-section');
    expect(summarySection).toHaveClass('border-amber-300/16');
    expect(summarySection).not.toHaveClass('border-rose-300/12');

    fireEvent.click(screen.getByRole('button', { name: 'Copy debug summary' }));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    const copied = String((navigator.clipboard.writeText as ReturnType<typeof vi.fn>).mock.calls.at(-1)?.[0] || '');
    expect(copied).toContain('"event": "ProviderFallbackServed"');
    expect(copied).toContain('"status": "success"');
    expect(copied).toContain('"severity": "degraded"');
    expect(copied).toContain('"requestId": "req-fallback-123456"');
    expect(copied).toContain('"traceId": "trace-fallback-abcdef"');
    expect(copied).toContain('"route": "/admin/logs"');
    expect(copied).toContain('"endpoint": "/api/v1/market-overview"');
    expect(copied).not.toContain('FRONTENDSECRET');
    expect(copied).not.toContain('FRONTENDTOKEN');
  });

  it('shows failed no-step events without all-zero step stats and can copy trace id', async () => {
    render(<AdminLogsPage />);

    const row = (await screen.findAllByText('MarketSentimentCard')).find((item) => item.closest('[data-testid="business-event-row"]'));
    const rowContainer = row.closest('[data-testid="business-event-row"]');
    expect(rowContainer).not.toBeNull();
    expect(within(rowContainer as HTMLElement).getByText('失败 · 无步骤明细')).toBeInTheDocument();
    expect(within(rowContainer as HTMLElement).queryByText('成功 0 · 跳过 0 · 失败 0 · 未确认 0')).not.toBeInTheDocument();

    fireEvent.click(within(rowContainer as HTMLElement).getByRole('button', { name: translate('zh', 'adminLogs.viewDetails') }));
    expect(await screen.findByTestId('root-cause-section')).toHaveTextContent('该事件在步骤级 trace 记录前已失败');
    expect(screen.getByText('Root Cause')).toBeInTheDocument();
    expect(screen.getAllByText('provider timeout token=***').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: '复制' }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('trace-market-card-abcdef');
  });

  it('shows a unified message when the business-event list fails to load', async () => {
    listBusinessEvents.mockRejectedValueOnce({
      response: {
        status: 500,
        data: {
          message: 'Internal Server Error',
        },
      },
    });

    render(<AdminLogsPage />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('服务器暂时不可用');
    expect(alert).toHaveTextContent('服务器暂时不可用，请稍后重试。');
  });

  it('renders healthy health summary when there are no events', async () => {
    listBusinessEvents.mockResolvedValueOnce({
      total: 0,
      limit: 20,
      offset: 0,
      hasMore: false,
      items: [],
      healthSummary: {
        totalEvents: 0,
        failedEvents: 0,
        warningEvents: 0,
        slowEvents: 0,
        failureRate: 0,
        status: 'healthy',
        failuresByCategory: [],
        failuresByProvider: [],
        failuresByReason: [],
        actorBreakdown: [],
        topRecentErrors: [],
        latestCriticalError: null,
      },
    });

    render(<AdminLogsPage />);

    expect(await screen.findByTestId('admin-logs-health-summary')).toHaveTextContent('Healthy');
    expect(screen.getByText('0 / 0')).toBeInTheDocument();
    expect(screen.getAllByText('--').length).toBeGreaterThan(0);
  });

  it('shows a unified message when the detail drawer fails to load', async () => {
    getBusinessEventDetail.mockRejectedValueOnce({
      response: {
        status: 404,
        data: {
          message: 'Not Found',
        },
      },
    });

    render(<AdminLogsPage />);

    const row = (await screen.findAllByText('TSLA'))[0];
    const rowContainer = row.closest('[data-testid="business-event-row"]');
    expect(rowContainer).not.toBeNull();
    fireEvent.click(within(rowContainer as HTMLElement).getByRole('button', { name: translate('zh', 'adminLogs.viewDetails') }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('请求的资源不存在');
    expect(alert).toHaveTextContent('请求的资源不存在。');
  });

  it('renders unknown step status as 未确认 after execution has finished', async () => {
    getBusinessEventDetail.mockResolvedValueOnce({
      ...businessDetail,
      steps: businessDetail.steps.map((step) => (
        step.name === 'ai_analysis'
          ? step
          : step
      )),
    });

    render(<AdminLogsPage />);

    const row = (await screen.findAllByText('TSLA'))[0];
    const rowContainer = row.closest('[data-testid="business-event-row"]');
    expect(rowContainer).not.toBeNull();
    fireEvent.click(within(rowContainer as HTMLElement).getByRole('button', { name: translate('zh', 'adminLogs.viewDetails') }));

    expect(await screen.findAllByText('未确认')).not.toHaveLength(0);
    expect(document.querySelector('[data-status="running"]')).toBeNull();
  });

  it('renders missing_api_key skips as 已跳过 instead of success', async () => {
    getBusinessEventDetail.mockResolvedValueOnce({
      ...businessDetail,
      steps: [
        ...businessDetail.steps,
        {
          name: 'fetch_news',
          label: '获取新闻',
          provider: 'tushare',
          status: 'skipped',
          reason: 'missing_api_key',
          message: '未配置 API Key，已跳过',
          metadata: {},
        },
      ],
      skippedStepCount: 3,
      stepCount: 7,
    });

    render(<AdminLogsPage />);

    const row = (await screen.findAllByText('TSLA'))[0];
    const rowContainer = row.closest('[data-testid="business-event-row"]');
    expect(rowContainer).not.toBeNull();
    fireEvent.click(within(rowContainer as HTMLElement).getByRole('button', { name: translate('zh', 'adminLogs.viewDetails') }));

    expect(await screen.findAllByText('未配置 API Key，已跳过')).not.toHaveLength(0);
    const skippedBadges = document.querySelectorAll('[data-status="skipped"]');
    expect(skippedBadges.length).toBeGreaterThan(0);
  });

  it('filters scanner and backtest business tabs by category', async () => {
    render(<AdminLogsPage />);

    fireEvent.click(await screen.findByRole('tab', { name: '扫描器' }));
    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({ category: 'scanner' })));

    fireEvent.click(screen.getByRole('tab', { name: '回测' }));
    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({ category: 'backtest' })));
  });

  it('keeps raw logs available in the advanced raw tab', async () => {
    render(<AdminLogsPage />);

    fireEvent.click(await screen.findByRole('tab', { name: '原始日志' }));

    expect(await screen.findByText('ExternalSourceTimeout')).toBeInTheDocument();
    expect(screen.getByLabelText('级别筛选')).toBeInTheDocument();
    expect(screen.getByTestId('raw-logs-table-shell')).toHaveClass('overflow-x-auto');
    await waitFor(() => expect(listSessions).toHaveBeenCalledWith(expect.objectContaining({ minLevel: 'WARNING' })));
  });

  it('renders English page-local copy on English routes', async () => {
    mockLanguage = 'en';

    render(<AdminLogsPage />);

    expect(await screen.findByRole('heading', { name: translate('en', 'adminLogs.pageTitle') })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Business events' })).toBeInTheDocument();
    expect(screen.getByLabelText('Status filter')).toBeInTheDocument();
    expect((await screen.findAllByText('TSLA')).length).toBeGreaterThan(0);
  });
});
