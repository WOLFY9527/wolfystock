import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { translate } from '../../i18n/core';
import AdminLogsPage from '../AdminLogsPage';

const { listBusinessEvents, getBusinessEventDetail, listSessions, getSessionDetail, getStorageSummary, cleanupLogs, listDataMissingDrilldown, listOperatorIssueRollup, getIncidentTimeline } = vi.hoisted(() => ({
  listBusinessEvents: vi.fn(),
  getBusinessEventDetail: vi.fn(),
  listSessions: vi.fn(),
  getSessionDetail: vi.fn(),
  getStorageSummary: vi.fn(),
  cleanupLogs: vi.fn(),
  listDataMissingDrilldown: vi.fn(),
  listOperatorIssueRollup: vi.fn(),
  getIncidentTimeline: vi.fn(),
}));

vi.mock('../../api/adminLogs', () => ({
  adminLogsApi: {
    listBusinessEvents,
    getBusinessEventDetail,
    listSessions,
    getSessionDetail,
    getStorageSummary,
    cleanupLogs,
    listDataMissingDrilldown,
    listOperatorIssueRollup,
    getIncidentTimeline,
  },
}));

let mockLanguage: 'zh' | 'en' = 'zh';

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: mockLanguage,
    t: (key: string, params?: Record<string, string | number | undefined>) => translate(mockLanguage, key, params),
  }),
}));

vi.mock('../../components/common/ApiErrorAlert', () => ({
  ApiErrorAlert: ({ error }: { error: { title: string; message: string } }) => (
    <div role="alert" data-testid="api-error-alert">
      <strong>{error.title}</strong>
      <span>{error.message}</span>
    </div>
  ),
}));

function expectZhL0OverviewStrip(testId: string) {
  const overviewStrip = screen.getByTestId(testId);
  expect(within(overviewStrip).getByText('信任状态')).toBeInTheDocument();
  expect(within(overviewStrip).getByText('影响范围')).toBeInTheDocument();
  expect(within(overviewStrip).getByText('建议动作')).toBeInTheDocument();
  expect(within(overviewStrip).getByText('证据参考')).toBeInTheDocument();
  expect(within(overviewStrip).getByText('最近更新')).toBeInTheDocument();
}

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
    market: 'US',
    source: 'local_db / yfinance',
    startedAt: '2026-04-30T11:20:00Z',
    durationMs: 2200,
    stepCount: 3,
    successStepCount: 2,
    skippedStepCount: 1,
    failedStepCount: 0,
    unknownStepCount: 0,
    metadata: {
      eventNames: ['ScannerRunStarted', 'ScannerRunCompleted'],
      configName: 'US Pre-open Scanner v1',
      universeCount: 120,
      evaluatedCount: 30,
      selectedCount: 5,
      rejectedCount: 25,
      dataFailedCount: 2,
      skippedCount: 90,
      topSymbol: 'NVDA',
      durationMs: 2200,
      sourceProviderSummary: 'local_db / yfinance',
    },
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

const dataMissingDrilldown = [
  {
    affectedSurface: 'Home quote panel',
    symbol: 'NVDA',
    market: 'US',
    missingDomain: 'news',
    provider: 'newsapi',
    source: 'Yahoo',
    freshnessStatus: 'missing',
    fallbackUsed: true,
    stale: false,
    partial: true,
    reasonCode: 'timeout',
    latestSeenAt: '2026-04-30T13:20:04Z',
    count: 2,
    sampleEventIds: ['evt-tsla'],
    sampleSessionIds: ['session-tsla'],
    sampleBusinessEventIds: ['analysis-tsla'],
  },
];

const operatorIssueRollup = [
  {
    issueId: 'provider-timeout:finnhub:market-overview',
    issueClass: 'provider_timeout',
    issueTitle: 'Provider timeout · finnhub',
    severity: 'warning',
    count: 3,
    latestTimestamp: '2026-04-30T13:20:04Z',
    firstTimestamp: '2026-04-30T13:10:04Z',
    sampleEventIds: ['evt-timeout-1', 'evt-timeout-2'],
    affectedSurfaces: ['market_overview'],
    affectedDomains: ['quote'],
    provider: 'finnhub',
    source: 'market_overview',
    model: null,
    channel: null,
    reasonCode: 'provider_timeout',
    eventType: 'ExternalSourceTimeout',
    freshnessStatus: 'missing',
    status: 'timed_out',
    operatorGuidance: 'provider timeout: check provider credentials and upstream status.',
  },
  {
    issueId: 'fallback-served:unsafe-provider',
    issueClass: 'fallback_served',
    issueTitle: 'Fallback served from /Users/alice/.env token=FRONTENDTOKEN',
    severity: 'warning',
    count: 1,
    latestTimestamp: '2026-04-30T12:00:00Z',
    firstTimestamp: '2026-04-30T12:00:00Z',
    sampleEventIds: ['evt-fallback-1'],
    affectedSurfaces: ['market_overview'],
    affectedDomains: ['news'],
    provider: '/Users/alice/.env token=FRONTENDTOKEN',
    source: 'cache',
    model: null,
    channel: null,
    reasonCode: 'fallback_used',
    eventType: 'DataSourceFallbackServed',
    freshnessStatus: 'fallback',
    status: 'success',
    operatorGuidance: 'fallback served: inspect configured primary provider without exposing /private/tmp/key token=FRONTENDTOKEN.',
  },
];

const incidentTimelinePayload = {
  lookup: {
    sessionId: 'session-tsla',
    requestId: null,
    queryId: null,
    symbol: 'TSLA',
    dateFrom: '2026-04-29T13:20:04Z',
    dateTo: null,
    limit: 60,
  },
  total: 3,
  hooks: [
    {
      kind: 'data_quality',
      status: 'degraded',
      summary: '2 degraded data-quality signals matched this lookup.',
      count: 2,
      latestAt: '2026-04-30T13:20:04Z',
      provider: 'newsapi',
      model: null,
      channel: null,
      reasonCode: 'timeout',
      sampleSessionIds: ['session-tsla'],
      sampleBusinessEventIds: ['analysis-tsla'],
    },
    {
      kind: 'llm_cost',
      status: 'placeholder',
      summary: 'LLM/cost summary placeholder only; no matching ledger row or model event was found.',
      count: 0,
      latestAt: null,
      provider: null,
      model: null,
      channel: null,
      reasonCode: null,
      sampleSessionIds: [],
      sampleBusinessEventIds: [],
    },
  ],
  items: [
    {
      id: 'session:session-tsla',
      kind: 'business_event',
      timestamp: '2026-04-30T13:20:00Z',
      status: 'partial',
      severity: 'warning',
      title: 'TSLA',
      summary: '用户分析 TSLA，部分数据源失败',
      sessionId: 'session-tsla',
      businessEventId: 'analysis-tsla',
      queryId: null,
      requestId: 'req-tsla-123456789',
      symbol: 'TSLA',
      phase: null,
      category: 'analysis',
      provider: null,
      model: null,
      channel: null,
      reasonCode: 'timeout',
      navigation: {
        sessionId: 'session-tsla',
        businessEventId: 'analysis-tsla',
      },
    },
    {
      id: 'event:session-tsla:1',
      kind: 'data_quality',
      timestamp: '2026-04-30T13:20:04Z',
      status: 'failed',
      severity: 'error',
      title: '获取新闻',
      summary: 'News API timeout after 3000ms token=***',
      sessionId: 'session-tsla',
      businessEventId: 'analysis-tsla',
      queryId: null,
      requestId: 'req-tsla-123456789',
      symbol: 'TSLA',
      phase: 'data_fetch',
      category: 'news',
      provider: 'newsapi',
      model: null,
      channel: null,
      reasonCode: 'timeout',
      navigation: {
        sessionId: 'session-tsla',
        businessEventId: 'analysis-tsla',
      },
    },
  ],
  emptyState: {
    reason: null,
    readOnly: true,
    message: null,
  },
  metadata: {
    readOnly: true,
  },
};

async function expandStorageDisclosure() {
  const disclosure = await screen.findByTestId('admin-logs-storage-disclosure');
  const toggle = within(disclosure).getByRole('button');
  if (toggle.getAttribute('aria-expanded') !== 'true') {
    fireEvent.click(toggle);
  }
}

describe('AdminLogsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
    window.history.replaceState({}, '', '/zh/admin/logs');
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
      minimumRetentionDays: 7,
      retentionCutoff: '2026-01-30T00:00:00Z',
      logsOlderThanRetentionCount: 120,
      estimatedStorageBytes: 690 * 1024 * 1024,
      sizeBytes: 690 * 1024 * 1024,
      storageSizeBytes: 690 * 1024 * 1024,
      sizeLabel: '690.0 MB',
      storageSizeLabel: '690.0 MB',
      storageSizeAvailable: true,
      measurementScope: 'postgres_tables',
      measurementStatus: 'available',
      measurementReason: null,
      storageSoftLimitBytes: 512 * 1024 * 1024,
      storageHardLimitBytes: 1024 * 1024 * 1024,
      usedPercentageOfSoftLimit: 134.77,
      usedPercentageOfHardLimit: 67.38,
      capacityCleanupRecommended: true,
      autoCleanupEnabled: true,
      autoCleanupPerformed: false,
      autoCleanupMessage: null,
      capacityCleanupPlan: {},
      postgresVacuumNote: 'Deleted rows may require PostgreSQL autovacuum to reclaim physical disk space.',
      warningThresholdCount: 50000,
      criticalThresholdCount: 100000,
      warningThresholdStorageBytes: null,
      statusReasons: ['storage_soft_limit_exceeded'],
      status: 'warning',
      recommendedCleanupAction: 'Storage is over the soft limit. Preview retention cleanup or capacity cleanup.',
      lastCleanupTimestamp: null,
    });
    cleanupLogs.mockResolvedValue({
      mode: 'retention',
      dryRun: true,
      cutoff: '2026-01-30T00:00:00Z',
      matchedLogCount: 120,
      matchedEventCount: 180,
      deletedLogCount: 0,
      deletedEventCount: 0,
      statusFilter: null,
      categoryFilter: null,
      additionalCleanupNeeded: false,
      message: null,
      postgresVacuumNote: null,
    });
    listDataMissingDrilldown.mockResolvedValue({
      total: dataMissingDrilldown.length,
      items: dataMissingDrilldown,
    });
    listOperatorIssueRollup.mockResolvedValue({
      total: operatorIssueRollup.length,
      items: operatorIssueRollup,
    });
    getIncidentTimeline.mockResolvedValue(incidentTimelinePayload);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('defaults to business events and does not show raw step names as the main list', async () => {
    render(<AdminLogsPage />);

    expectZhL0OverviewStrip('admin-logs-l0-overview-strip');
    expect(screen.getByTestId('admin-logs-workspace')).toHaveClass('w-full', 'flex-1', 'min-w-0', 'overflow-x-hidden');
    expect(screen.getByTestId('admin-logs-page-shell')).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(screen.getByTestId('admin-logs-page-shell')).toHaveClass('py-5', 'md:py-6');
    expect(screen.getByTestId('admin-logs-header-panel')).toHaveAttribute('data-terminal-primitive', 'panel');
    expect(screen.getByTestId('admin-logs-storage-disclosure')).toHaveAttribute('data-terminal-primitive', 'disclosure');
    expect(screen.getByText('L4 日志容量建议与显式清理：容量 / 保留期 / 预览')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '业务事件' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '股票分析' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '扫描器' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '回测' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '数据源' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '安全事件' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '原始日志' })).toBeInTheDocument();
    expect(screen.getByText('页面用途')).toBeInTheDocument();
    expect(screen.getByText('当前状态')).toBeInTheDocument();
    expect(screen.getByText('下一步')).toBeInTheDocument();
    expect(screen.getByText('定位失败与审计线索')).toBeInTheDocument();
    expect((await screen.findAllByText('1 个失败 / 6 条记录')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('先处理失败和数据源降级').length).toBeGreaterThan(0);
    expect(screen.getByTestId('admin-logs-filter-bar')).toBeInTheDocument();
    expect(await screen.findByTestId('admin-logs-health-summary')).toBeInTheDocument();
    expect(await screen.findByTestId('admin-logs-operator-issue-rollup')).toHaveTextContent('数据源健康摘要');
    expect(screen.getByTestId('admin-logs-operator-issue-rollup')).toHaveTextContent('响应超时');
    expect(screen.getByTestId('admin-logs-operator-issue-rollup')).toHaveTextContent('数据源配置与上游状态');
    expect(screen.getByTestId('admin-logs-operator-issue-rollup')).toHaveTextContent('evt-timeout-1');
    expect(screen.getByTestId('admin-logs-operator-issue-rollup')).not.toHaveTextContent('FRONTENDTOKEN');
    expect(screen.getByTestId('admin-logs-operator-issue-rollup')).not.toHaveTextContent('/Users/alice');
    expect(screen.getByTestId('admin-logs-operator-issue-rollup')).not.toHaveTextContent('/private/tmp');
    expect(await screen.findByTestId('admin-logs-data-missing-section')).toHaveTextContent('缺失 / 降级数据样本');
    expect(screen.getByTestId('admin-logs-data-missing-section')).toHaveTextContent('NVDA');
    expect(screen.getByTestId('admin-logs-data-missing-section')).toHaveTextContent('newsapi');
    await expandStorageDisclosure();
    expect(await screen.findByTestId('admin-logs-storage-summary')).toHaveTextContent('120,000 会话');
    expect(screen.getByTestId('admin-logs-storage-summary')).toHaveTextContent('180,000 事件');
    expect(screen.getByTestId('admin-logs-storage-summary')).toHaveTextContent('日志容量 690.0 MB');
    expect(screen.getByTestId('admin-logs-storage-summary')).toHaveTextContent('PostgreSQL 表容量');
    expect(screen.getByTestId('admin-logs-storage-summary')).toHaveTextContent('90');
    expect(screen.getByTestId('admin-logs-storage-summary')).toHaveTextContent('最少 7 天 · 120 条超期');
    expect(screen.getByRole('link', { name: '配置管理员通知通道' })).toHaveAttribute('href', '/admin/notifications');
    expect(screen.getAllByText('警告').length).toBeGreaterThan(0);
    expect(screen.getAllByText('降级').length).toBeGreaterThan(0);
    expect(screen.getByText('1 / 6')).toBeInTheDocument();
    expect(screen.getByText('finnhub')).toBeInTheDocument();
    expect(screen.getAllByText(/数据源响应超时.*token=\*\*\*/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/FRONTENDSECRET|FRONTENDTOKEN/)).not.toBeInTheDocument();
    expect(screen.getByLabelText('搜索日志')).toBeInTheDocument();
    expect(screen.getByLabelText('状态筛选')).toBeInTheDocument();
    expect(screen.getByLabelText('时间范围')).toBeInTheDocument();
    expect(screen.queryByTestId('admin-logs-summary-grid')).not.toBeInTheDocument();
    expect((await screen.findAllByText('TSLA')).length).toBeGreaterThan(0);
    expect(screen.getByText('操作者')).toBeInTheDocument();
    expect(screen.getByText('上下文')).toBeInTheDocument();
    expect(screen.getByText('来源 / 数据源')).toBeInTheDocument();
    expect(screen.getByText('原因')).toBeInTheDocument();
    expect(screen.queryByText('Trace')).not.toBeInTheDocument();
    expect(screen.getByText('状态 / 严重度')).toBeInTheDocument();
    expect(screen.queryByText('耗时')).not.toBeInTheDocument();
    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('newsapi')).toBeInTheDocument();
    const fallbackRowLabel = (await screen.findAllByText('备用链路激活')).find((item) => item.closest('[data-testid="business-event-row"]'));
    const fallbackRow = fallbackRowLabel.closest('[data-testid="business-event-row"]');
    expect(fallbackRow).not.toBeNull();
    expect(within(fallbackRow as HTMLElement).getByTestId('event-severity-pill')).toHaveTextContent('降级');
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
    const operatorCopy = (screen.getByTestId('admin-logs-operator-issue-rollup').textContent || '').replace(/evt-[a-z0-9-]+/gi, '');
    const businessCopy = screen.getByTestId('business-events-table-shell').textContent || '';
    expect(operatorCopy).not.toMatch(/\bprovider\b|\bfallback\b|\bstale\b|\btimeout\b|\bpartial\b|\bcache\b/i);
    expect(businessCopy).not.toMatch(/\bprovider\b|\bfallback\b|\bstale\b|\btimeout\b|\bpartial\b|\bcache\b/i);
    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({ since: '24h', limit: 20, offset: 0 })));
    await waitFor(() => expect(listDataMissingDrilldown).toHaveBeenCalledWith({ since: '24h', limit: 4 }));
    await waitFor(() => expect(listOperatorIssueRollup).toHaveBeenCalledWith({ since: '24h', limit: 6 }));
  });

  it('renders operator-safe labels for unavailable, timeout, fallback, stale, partial, cache, computed, RatesCard, and mixed states', async () => {
    listBusinessEvents.mockResolvedValueOnce({
      total: businessEvents.length + 1,
      limit: 20,
      offset: 0,
      hasMore: false,
      items: [
        {
          id: 'rates-card-computed',
          event: 'RatesCard',
          category: 'cache',
          type: 'computed',
          eventType: 'computed',
          status: 'partial',
          summary: 'RatesCard computed from mixed cache sources',
          subject: 'RatesCard',
          component: 'RatesCard',
          contextLabel: 'RatesCard',
          provider: 'computed',
          source: 'mixed',
          reason: 'cache',
          startedAt: '2026-04-30T13:30:00Z',
          durationMs: 120,
          stepCount: 1,
          successStepCount: 0,
          failedStepCount: 0,
          skippedStepCount: 0,
          unknownStepCount: 1,
        },
        ...businessEvents,
      ],
      healthSummary: {
        totalEvents: businessEvents.length + 1,
        failedEvents: 1,
        warningEvents: 2,
        slowEvents: 1,
        failureRate: 0.2,
        status: 'degraded',
        failuresByCategory: [{ key: 'data_source', label: 'data_source', count: 1 }],
        failuresByProvider: [{ key: 'finnhub', label: 'finnhub', count: 1 }],
        failuresByReason: [{ key: 'timeout', label: 'timeout', count: 2 }],
        actorBreakdown: [{ key: 'user', label: 'user', count: 2 }],
        topRecentErrors: [],
        latestCriticalError: null,
      },
    });
    listOperatorIssueRollup.mockResolvedValueOnce({
      total: 3,
      items: [
        {
          ...operatorIssueRollup[0],
          issueTitle: 'provider unavailable · newsapi',
          provider: 'newsapi',
          source: 'cache',
          reasonCode: 'provider_unavailable',
          freshnessStatus: 'stale',
          operatorGuidance: 'provider unavailable: fallback cache served.',
        },
        {
          ...operatorIssueRollup[0],
          issueId: 'rates-card-computed-mixed',
          issueClass: 'computed',
          issueTitle: 'RatesCard computed mixed cache',
          affectedSurfaces: ['RatesCard'],
          affectedDomains: ['mixed'],
          provider: 'computed',
          source: 'mixed',
          reasonCode: 'cache',
          eventType: 'computed',
          freshnessStatus: 'mixed',
          status: 'mixed',
          operatorGuidance: 'RatesCard computed from mixed cache inputs.',
        },
        operatorIssueRollup[1],
      ],
    });
    listDataMissingDrilldown.mockResolvedValueOnce({
      total: 2,
      items: [
        {
          ...dataMissingDrilldown[0],
          symbol: 'MSFT',
          freshnessStatus: 'stale',
          stale: true,
          partial: false,
          fallbackUsed: false,
          reasonCode: 'stale',
        },
        {
          ...dataMissingDrilldown[0],
          symbol: 'AMD',
          freshnessStatus: 'partial',
          stale: false,
          partial: true,
          fallbackUsed: false,
          reasonCode: 'partial',
        },
      ],
    });

    render(<AdminLogsPage />);

    const operatorSection = await screen.findByTestId('admin-logs-operator-issue-rollup');
    const dataGapSection = screen.getByTestId('admin-logs-data-missing-section');
    const businessTable = screen.getByTestId('business-events-table-shell');
    const operatorCopy = (operatorSection.textContent || '').replace(/evt-[a-z0-9-]+/gi, '');
    const dataGapCopy = dataGapSection.textContent || '';
    const businessCopy = businessTable.textContent || '';
    expect(operatorCopy).toContain('数据源健康摘要');
    expect(operatorCopy).toContain('数据源不可用');
    expect(operatorCopy).toContain('响应超时');
    expect(operatorCopy).toContain('备用链路激活');
    expect(operatorCopy).toContain('本地存储响应');
    expect(operatorCopy).toContain('计算结论');
    expect(operatorCopy).toContain('汇率模块');
    expect(operatorCopy).toContain('混合来源');
    expect(dataGapCopy).toContain('数据过期');
    expect(dataGapCopy).toContain('部分数据');
    expect(businessCopy).toContain('本地存储响应');
    expect(businessCopy).toContain('计算结论');
    expect(businessCopy).toContain('汇率模块');
    expect(businessCopy).toContain('混合来源');
    expect(operatorCopy).not.toMatch(/\bprovider\b|\bfallback\b|\bstale\b|\btimeout\b|\bpartial\b|\bcache\b|\bcomputed\b|RatesCard|\bmixed\b/i);
    expect(dataGapCopy).not.toMatch(/\bprovider\b|\bfallback\b|\bstale\b|\btimeout\b|\bpartial\b|\bcache\b|\bcomputed\b|RatesCard|\bmixed\b/i);
    expect(businessCopy).not.toMatch(/\bprovider\b|\bfallback\b|\bstale\b|\btimeout\b|\bpartial\b|\bcache\b|\bcomputed\b|RatesCard|\bmixed\b/i);
  });

  it('filters the existing logs table from an operator rollup issue', async () => {
    render(<AdminLogsPage />);

    const section = await screen.findByTestId('admin-logs-operator-issue-rollup');
    const firstIssue = within(section).getByText('数据源响应超时 · finnhub').closest('[data-testid="operator-issue-row"]');
    expect(firstIssue).not.toBeNull();
    fireEvent.click(within(firstIssue as HTMLElement).getByRole('button', { name: '筛选日志' }));

    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({
      category: 'data_source',
      query: expect.stringContaining('finnhub'),
    })));
  });

  it('opens the incident timeline drawer from data-missing drilldown samples', async () => {
    render(<AdminLogsPage />);

    fireEvent.click(await screen.findByRole('button', { name: '打开时间线' }));

    await waitFor(() => expect(getIncidentTimeline).toHaveBeenCalledWith(expect.objectContaining({
      sessionId: 'session-tsla',
      since: '24h',
      limit: 60,
    })));
    expect(await screen.findByTestId('admin-incident-timeline-drawer')).toHaveTextContent('只读');
    expect(screen.getByTestId('admin-incident-timeline-drawer')).toHaveTextContent('聚合线索');
    expect(screen.getByTestId('admin-incident-timeline-drawer')).toHaveTextContent('数据质量');
    expect(screen.getByTestId('admin-incident-timeline-drawer')).toHaveTextContent('2 degraded data-quality signals matched this lookup.');
    expect(screen.getByTestId('admin-incident-timeline-drawer')).toHaveTextContent('获取新闻');
    expect(screen.queryByText('FRONTENDSECRET')).not.toBeInTheDocument();
  });

  it('renders a readable empty state when no incident timeline matches the lookup', async () => {
    getIncidentTimeline.mockResolvedValueOnce({
      lookup: {
        sessionId: 'session-tsla',
        requestId: null,
        queryId: null,
        symbol: 'TSLA',
        dateFrom: '2026-04-29T13:20:04Z',
        dateTo: null,
        limit: 60,
      },
      total: 0,
      hooks: [],
      items: [],
      emptyState: {
        reason: 'no_matching_read_models',
        readOnly: true,
        message: 'No matching execution logs or read-model hints were found for the requested lookup.',
      },
      metadata: {
        readOnly: true,
      },
    });

    render(<AdminLogsPage />);

    fireEvent.click(await screen.findByRole('button', { name: '打开时间线' }));

    expect(await screen.findByTestId('admin-incident-timeline-empty-state')).toHaveTextContent('No matching execution logs or read-model hints were found for the requested lookup.');
  });

  it('previews and confirms retention cleanup, then refreshes logs and storage summary', async () => {
    cleanupLogs
      .mockResolvedValueOnce({
        mode: 'retention',
        dryRun: true,
        cutoff: '2026-01-30T00:00:00Z',
        matchedLogCount: 120,
        matchedEventCount: 180,
        deletedLogCount: 0,
        deletedEventCount: 0,
        statusFilter: null,
        categoryFilter: null,
        additionalCleanupNeeded: false,
        message: null,
        postgresVacuumNote: null,
      })
      .mockResolvedValueOnce({
        mode: 'retention',
        dryRun: false,
        cutoff: '2026-01-30T00:00:00Z',
        matchedLogCount: 120,
        matchedEventCount: 180,
        deletedLogCount: 120,
        deletedEventCount: 180,
        statusFilter: null,
        categoryFilter: null,
        additionalCleanupNeeded: false,
        message: null,
        postgresVacuumNote: null,
      });

    render(<AdminLogsPage />);

    await expandStorageDisclosure();
    fireEvent.click(await screen.findByRole('button', { name: '预览保留期清理' }));
    await waitFor(() => expect(cleanupLogs).toHaveBeenCalledWith({ mode: 'retention', useRetention: true, dryRun: true }));
    expect(await screen.findByText(/保留期清理预览：将在/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '清理超过保留期的日志' }));
    await waitFor(() => expect(window.confirm).toHaveBeenCalled());
    await waitFor(() => expect(cleanupLogs).toHaveBeenLastCalledWith({ mode: 'retention', useRetention: true, dryRun: false }));
    expect(await screen.findByText(/已删除 120 个会话/)).toBeInTheDocument();
    expect(getStorageSummary).toHaveBeenCalledTimes(2);
    expect(listBusinessEvents).toHaveBeenCalled();
  });

  it('shows size unavailable state when database storage size is unavailable', async () => {
    getStorageSummary.mockResolvedValueOnce({
      totalLogCount: 7441,
      totalEventCount: 10326,
      oldestLogTimestamp: '2026-04-17T18:27:00Z',
      newestLogTimestamp: '2026-04-30T13:21:00Z',
      retentionDays: 90,
      minimumRetentionDays: 7,
      retentionCutoff: '2026-01-30T00:00:00Z',
      logsOlderThanRetentionCount: 0,
      estimatedStorageBytes: null,
      sizeBytes: null,
      storageSizeBytes: null,
      sizeLabel: null,
      storageSizeLabel: null,
      storageSizeAvailable: false,
      measurementScope: 'unavailable',
      measurementStatus: 'unavailable',
      measurementReason: 'database path unavailable',
      storageSoftLimitBytes: 512 * 1024 * 1024,
      storageHardLimitBytes: 1024 * 1024 * 1024,
      usedPercentageOfSoftLimit: null,
      usedPercentageOfHardLimit: null,
      capacityCleanupRecommended: false,
      autoCleanupEnabled: true,
      autoCleanupPerformed: false,
      autoCleanupMessage: null,
      capacityCleanupPlan: {},
      postgresVacuumNote: null,
      warningThresholdCount: 50000,
      criticalThresholdCount: 100000,
      warningThresholdStorageBytes: null,
      statusReasons: [],
      status: 'ok',
      recommendedCleanupAction: 'Storage size unavailable; retention and row-count checks are active.',
      lastCleanupTimestamp: null,
    });

    render(<AdminLogsPage />);

    await expandStorageDisclosure();
    expect(await screen.findByTestId('admin-logs-storage-summary')).toHaveTextContent('容量暂不可用');
    expect(screen.getByTestId('admin-logs-storage-summary')).toHaveTextContent('数据库路径不可用');
    expect(screen.queryByText('大小不可用')).not.toBeInTheDocument();
    expect(screen.getByTestId('admin-logs-storage-summary')).toHaveTextContent('7,441 会话');
    expect(screen.getByRole('button', { name: '预览容量清理' })).toBeDisabled();
  });

  it('renders critical quota state and runs confirmed capacity cleanup', async () => {
    getStorageSummary.mockResolvedValue({
      totalLogCount: 120000,
      totalEventCount: 180000,
      oldestLogTimestamp: '2026-01-01T00:00:00Z',
      newestLogTimestamp: '2026-04-30T13:21:00Z',
      retentionDays: 90,
      minimumRetentionDays: 7,
      retentionCutoff: '2026-01-30T00:00:00Z',
      logsOlderThanRetentionCount: 120,
      estimatedStorageBytes: 1200 * 1024 * 1024,
      sizeBytes: 1200 * 1024 * 1024,
      storageSizeBytes: 1200 * 1024 * 1024,
      sizeLabel: '1.2 GB',
      storageSizeLabel: '1.2 GB',
      storageSizeAvailable: true,
      measurementScope: 'postgres_tables',
      measurementStatus: 'available',
      measurementReason: null,
      storageSoftLimitBytes: 512 * 1024 * 1024,
      storageHardLimitBytes: 1024 * 1024 * 1024,
      usedPercentageOfSoftLimit: 234.38,
      usedPercentageOfHardLimit: 117.19,
      capacityCleanupRecommended: true,
      autoCleanupEnabled: true,
      autoCleanupPerformed: false,
      autoCleanupMessage: null,
      capacityCleanupPlan: {},
      postgresVacuumNote: 'Deleted rows may require PostgreSQL autovacuum to reclaim physical disk space.',
      warningThresholdCount: 50000,
      criticalThresholdCount: 100000,
      warningThresholdStorageBytes: null,
      statusReasons: ['storage_hard_limit_exceeded'],
      status: 'critical',
      recommendedCleanupAction: 'Storage is over the hard limit. Run capacity cleanup.',
      lastCleanupTimestamp: null,
    });
    cleanupLogs
      .mockResolvedValueOnce({
        mode: 'capacity',
        dryRun: true,
        cutoff: '2026-04-23T00:00:00Z',
        matchedLogCount: 80,
        matchedEventCount: 160,
        deletedLogCount: 0,
        deletedEventCount: 0,
        statusFilter: null,
        categoryFilter: null,
        additionalCleanupNeeded: true,
        message: null,
        postgresVacuumNote: 'Deleted rows may require PostgreSQL autovacuum to reclaim physical disk space.',
      })
      .mockResolvedValueOnce({
        mode: 'capacity',
        dryRun: false,
        cutoff: '2026-04-23T00:00:00Z',
        matchedLogCount: 80,
        matchedEventCount: 160,
        deletedLogCount: 80,
        deletedEventCount: 160,
        statusFilter: null,
        categoryFilter: null,
        additionalCleanupNeeded: false,
        message: 'Deleted rows may require PostgreSQL autovacuum to reclaim physical disk space.',
        postgresVacuumNote: 'Deleted rows may require PostgreSQL autovacuum to reclaim physical disk space.',
      });

    render(<AdminLogsPage />);

    await expandStorageDisclosure();
    expect(await screen.findByText('严重')).toBeInTheDocument();
    expect(screen.getByTestId('admin-logs-storage-summary')).toHaveTextContent('日志容量 1.2 GB');
    expect(screen.getByTestId('admin-logs-storage-summary')).toHaveTextContent('建议执行显式容量清理。');
    fireEvent.click(screen.getByRole('button', { name: '预览容量清理' }));
    await waitFor(() => expect(cleanupLogs).toHaveBeenCalledWith({ mode: 'capacity', dryRun: true }));
    expect(await screen.findByText(/容量清理预览：将删除 80 个会话和 160 个事件/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '按容量清理日志' }));
    await waitFor(() => expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('运行容量清理')));
    await waitFor(() => expect(cleanupLogs).toHaveBeenLastCalledWith({ mode: 'capacity', dryRun: false }));
    expect(await screen.findByText(/已删除 80 个会话/)).toBeInTheDocument();
  });

  it('does not run destructive cleanup when confirmation is declined', async () => {
    (window.confirm as ReturnType<typeof vi.fn>).mockReturnValueOnce(false);

    render(<AdminLogsPage />);

    await expandStorageDisclosure();
    fireEvent.click(await screen.findByRole('button', { name: '清理超过保留期的日志' }));

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

  it('resets business pagination when tab and business filters change', async () => {
    render(<AdminLogsPage />);

    fireEvent.click(await screen.findByRole('tab', { name: '股票分析' }));
    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({ category: 'analysis', offset: 0 })));

    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({ category: 'analysis', offset: 20 })));

    fireEvent.change(screen.getByLabelText('搜索日志'), { target: { value: 'TSLA' } });
    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({ category: 'analysis', symbol: 'TSLA', offset: 0 })));

    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({ category: 'analysis', symbol: 'TSLA', offset: 20 })));

    fireEvent.change(screen.getByLabelText('状态筛选'), { target: { value: 'partial' } });
    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({ category: 'analysis', symbol: 'TSLA', status: 'partial', offset: 0 })));

    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({ category: 'analysis', symbol: 'TSLA', status: 'partial', offset: 20 })));

    fireEvent.change(screen.getByLabelText('时间范围'), { target: { value: '1h' } });
    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({ category: 'analysis', symbol: 'TSLA', status: 'partial', since: '1h', offset: 0 })));

    fireEvent.click(screen.getByRole('tab', { name: '数据源' }));
    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({ category: 'data_source', since: '1h', offset: 0 })));
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
    expect(screen.getByText('调用链时间线')).toBeInTheDocument();
    expect(screen.getByTestId('root-cause-section')).toBeInTheDocument();
    expect(screen.queryByText('Root Cause')).not.toBeInTheDocument();
    expect(screen.getByText('降级摘要')).toBeInTheDocument();
    expect(screen.getAllByText(/alice/).length).toBeGreaterThan(0);
    expect(screen.getByText(/trace-tsla-abcdef/)).toBeInTheDocument();
    expect(screen.getByText(/获取行情/)).toBeInTheDocument();
    expect(screen.getByText(/获取新闻/)).toBeInTheDocument();
    expect(screen.getByText(/获取财务数据/)).toBeInTheDocument();
    expect(screen.getAllByText(/AI 分析/).length).toBeGreaterThan(0);
    expect(screen.getByText(/保存分析记录/)).toBeInTheDocument();
    expect(screen.getAllByText(/News API .*响应超时.*token=\*\*\*/).length).toBeGreaterThan(0);
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

    const row = (await screen.findAllByText('备用链路激活')).find((item) => item.closest('[data-testid="business-event-row"]'));
    const rowContainer = row.closest('[data-testid="business-event-row"]');
    expect(rowContainer).not.toBeNull();
    fireEvent.click(within(rowContainer as HTMLElement).getByRole('button', { name: translate('zh', 'adminLogs.viewDetails') }));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.queryByText('Root Cause')).not.toBeInTheDocument();
    expect(screen.getByText('降级摘要')).toBeInTheDocument();
    const summarySection = screen.getByTestId('root-cause-section');
    expect(summarySection).toHaveClass('border-amber-300/16');
    expect(summarySection).not.toHaveClass('border-rose-300/12');

    fireEvent.click(screen.getByRole('button', { name: '复制执行摘要' }));
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
    expect(screen.getByText('根因')).toBeInTheDocument();
    expect(screen.getAllByText(/数据源响应超时.*token=\*\*\*/).length).toBeGreaterThan(0);
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

    expect(await screen.findByTestId('admin-logs-health-summary')).toHaveTextContent('健康');
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
    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({ category: 'scanner', minLevel: 'INFO' })));
    expect(await screen.findByTestId('admin-logs-scanner-summary')).toHaveTextContent('最近一次扫描');
    expect(screen.getByTestId('admin-logs-scanner-summary')).toHaveTextContent('包含 INFO 生命周期记录');

    fireEvent.click(screen.getByRole('tab', { name: '回测' }));
    await waitFor(() => expect(listBusinessEvents).toHaveBeenLastCalledWith(expect.objectContaining({ category: 'backtest' })));
  });

  it('renders scanner empty state with specific Chinese copy', async () => {
    listBusinessEvents.mockResolvedValue({
      total: 0,
      limit: 20,
      offset: 0,
      hasMore: false,
      items: [],
      healthSummary: null,
    });

    render(<AdminLogsPage />);

    fireEvent.click(await screen.findByRole('tab', { name: '扫描器' }));
    expect(await screen.findByText('暂无扫描器日志')).toBeInTheDocument();
    expect(screen.getByText('暂无扫描器日志。运行一次扫描后，这里会显示扫描开始、完成、失败和耗时。')).toBeInTheDocument();
  });

  it('renders SQLite database-file capacity source', async () => {
    getStorageSummary.mockResolvedValueOnce({
      totalLogCount: 10,
      totalEventCount: 20,
      oldestLogTimestamp: '2026-04-17T18:27:00Z',
      newestLogTimestamp: '2026-04-30T13:21:00Z',
      retentionDays: 90,
      minimumRetentionDays: 7,
      retentionCutoff: '2026-01-30T00:00:00Z',
      logsOlderThanRetentionCount: 0,
      estimatedStorageBytes: 123456,
      sizeBytes: 123456,
      storageSizeBytes: 123456,
      sizeLabel: '120.6 KB',
      storageSizeLabel: '120.6 KB',
      storageSizeAvailable: true,
      measurementScope: 'sqlite_database_file',
      measurementStatus: 'available',
      measurementReason: null,
      storageSoftLimitBytes: 512 * 1024 * 1024,
      storageHardLimitBytes: 1024 * 1024 * 1024,
      usedPercentageOfSoftLimit: 0.02,
      usedPercentageOfHardLimit: 0.01,
      capacityCleanupRecommended: false,
      autoCleanupEnabled: true,
      autoCleanupPerformed: false,
      autoCleanupMessage: null,
      capacityCleanupPlan: {},
      postgresVacuumNote: null,
      warningThresholdCount: 50000,
      criticalThresholdCount: 100000,
      warningThresholdStorageBytes: null,
      statusReasons: [],
      status: 'ok',
      recommendedCleanupAction: 'No cleanup needed.',
      lastCleanupTimestamp: null,
    });

    render(<AdminLogsPage />);

    await expandStorageDisclosure();
    expect(await screen.findByTestId('admin-logs-storage-summary')).toHaveTextContent('日志容量 120.6 KB');
    expect(screen.getByTestId('admin-logs-storage-summary')).toHaveTextContent('SQLite 数据库文件');
  });

  it('shows scanner execution summary and keeps raw metadata collapsed by default', async () => {
    getBusinessEventDetail.mockResolvedValueOnce({
      ...businessEvents[4],
      steps: [
        { name: 'ScannerRunStarted', label: '扫描启动', status: 'success', durationMs: 0, metadata: {} },
        { name: 'ScannerRunCompleted', label: '扫描完成', status: 'success', durationMs: 2200, metadata: businessEvents[4].metadata },
      ],
    });
    render(<AdminLogsPage />);

    fireEvent.click(await screen.findByRole('tab', { name: '扫描器' }));
    const row = (await screen.findAllByText('Scanner: 大盘单机游戏')).find((item) => item.closest('[data-testid="business-event-row"]'));
    const rowContainer = row.closest('[data-testid="business-event-row"]');
    expect(rowContainer).not.toBeNull();
    fireEvent.click(within(rowContainer as HTMLElement).getByRole('button', { name: translate('zh', 'adminLogs.viewDetails') }));

    expect(await screen.findByTestId('scanner-execution-summary')).toHaveTextContent('扫描器执行摘要');
    expect(screen.getByTestId('scanner-execution-summary')).toHaveTextContent('US · US Pre-open Scanner v1');
    expect(screen.getByTestId('scanner-execution-summary')).toHaveTextContent('30 / 5');
    const metadataToggle = screen.getByRole('button', { name: '展开 元数据' });
    expect(metadataToggle).toBeTruthy();
    expect(metadataToggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText('DEBUG')).not.toBeInTheDocument();
  });

  it('keeps raw logs available in the advanced raw tab', async () => {
    render(<AdminLogsPage />);

    fireEvent.click(await screen.findByRole('tab', { name: '原始日志' }));

    expect(await screen.findByText('数据源响应超时')).toBeInTheDocument();
    expect(screen.getByLabelText('级别筛选')).toBeInTheDocument();
    expect(screen.getByTestId('raw-logs-table-shell')).toHaveClass('overflow-x-auto');
    await waitFor(() => expect(listSessions).toHaveBeenCalledWith(expect.objectContaining({ minLevel: 'WARNING' })));
  });

  it('contains the default business event queue inside a narrow-safe horizontal rail', async () => {
    render(<AdminLogsPage />);

    const shell = await screen.findByTestId('business-events-table-shell');
    expect(shell).toHaveClass('overflow-x-auto');
    expect(screen.getByTestId('business-events-table-inner')).toHaveClass('min-w-[44rem]');
  });

  it('renders English page-local copy on English routes', async () => {
    mockLanguage = 'en';

    render(<AdminLogsPage />);

    expect(await screen.findByRole('heading', { name: translate('en', 'adminLogs.pageTitle') })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Business events' })).toBeInTheDocument();
    expect(screen.getByLabelText('Status filter')).toBeInTheDocument();
    expect((await screen.findAllByText('TSLA')).length).toBeGreaterThan(0);
  });

  it('initializes safe query params and renders sanitized drill-through controls for issue triage', async () => {
    window.history.replaceState({}, '', '/zh/admin/logs?tab=data_source&query=fallback%20market&since=24h&eventId=market-card-failed&token=SECRET');

    render(<AdminLogsPage />);

    const search = await screen.findByLabelText('搜索日志');
    expect(search).toHaveValue('fallback market');
    expect(screen.getByLabelText('时间范围')).toHaveValue('24h');
    expect(screen.getByRole('tab', { name: '数据源' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByTestId('admin-logs-drill-highlight')).toHaveTextContent('market-card-failed');
    expect(screen.getByRole('link', { name: /查看数据源维护/i })).toHaveAttribute('href', '/zh/admin/market-providers?surface=market_overview');
    expect(screen.getByRole('link', { name: /查看熔断与配额/i })).toHaveAttribute('href', '/zh/admin/provider-circuits?since=24h');
    expect(screen.getByRole('link', { name: /查看成本观测/i })).toHaveAttribute('href', '/zh/admin/cost-observability?window=24h&area=provider');
    expect(document.body).not.toHaveTextContent('SECRET');
  });
});
