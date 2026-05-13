import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MarketProviderOperationsPage from '../MarketProviderOperationsPage';

const { getOperations } = vi.hoisted(() => ({
  getOperations: vi.fn(),
}));

vi.mock('../../api/marketProviderOperations', () => ({
  marketProviderOperationsApi: {
    getOperations,
  },
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: 'zh',
    t: (key: string) => key,
  }),
}));

const populatedPayload = {
  generatedAt: '2026-05-06T09:10:00+08:00',
  window: { key: '24h', since: '24h' },
  summary: {
    totalItems: 2,
    liveCount: 1,
    cacheCount: 0,
    staleCount: 0,
    fallbackCount: 1,
    partialCount: 0,
    unavailableCount: 0,
    errorCount: 0,
    refreshingCount: 1,
    eventCount: 3,
    failureCount: 1,
    fallbackEventCount: 1,
    staleEventCount: 0,
    slowEventCount: 1,
  },
  items: [
    {
      provider: 'sina',
      sourceLabel: '新浪财经',
      sourceType: 'public_api',
      domain: 'equity_index',
      endpoint: '/api/v1/market/cn-indices',
      card: 'ChinaIndicesCard',
      cacheKey: 'cn_indices',
      status: 'live',
      freshness: 'live',
      asOf: '2026-05-06T09:05:00+08:00',
      updatedAt: '2026-05-06T09:08:00+08:00',
      lastSuccessfulAt: '2026-05-06T09:08:00+08:00',
      lastKnownGoodAgeMinutes: 2,
      latencyMs: 128.4,
      isFallback: false,
      isStale: false,
      isRefreshing: false,
      isFromSnapshot: false,
      fallbackUsed: false,
      warning: null,
      errorSummary: null,
      adminLogDrillThrough: {
        label: '查看 Admin Logs',
        route: '/zh/admin/logs',
        query: { since: '24h', provider: 'sina' },
        eventId: null,
      },
    },
    {
      provider: 'fallback',
      sourceLabel: '备用快照',
      sourceType: 'snapshot',
      domain: 'sentiment',
      endpoint: '/api/v1/market/market-briefing',
      card: 'MarketBriefingCard',
      cacheKey: 'market_briefing',
      status: 'fallback',
      freshness: 'fallback',
      asOf: null,
      updatedAt: '2026-05-06T08:10:00+08:00',
      lastSuccessfulAt: '2026-05-06T08:10:00+08:00',
      lastKnownGoodAgeMinutes: 60,
      latencyMs: null,
      isFallback: true,
      isStale: false,
      isRefreshing: true,
      isFromSnapshot: true,
      fallbackUsed: true,
      warning: '备用示例数据，不代表当前行情',
      errorSummary: 'primary provider timeout token=***',
      adminLogDrillThrough: {
        label: '查看 Admin Logs',
        route: '/zh/admin/logs',
        query: { since: '24h', provider: 'fallback' },
        eventId: 'evt-1',
      },
    },
  ],
  eventRollups: [
    {
      provider: 'fallback',
      endpoint: '/api/v1/market/market-briefing',
      card: 'MarketBriefingCard',
      category: 'data_source',
      eventCount: 2,
      failureCount: 1,
      fallbackCount: 1,
      staleServedCount: 0,
      slowCount: 1,
      failureRate: 0.5,
      topReasons: ['timeout', 'fallback_used'],
      latestLogEventId: 'evt-1',
      latestStartedAt: '2026-05-06T08:09:00+08:00',
      adminLogDrillThrough: {
        label: '查看 Admin Logs',
        route: '/zh/admin/logs',
        query: { since: '24h', provider: 'fallback' },
        eventId: 'evt-1',
      },
    },
  ],
  cacheStates: [
    {
      cacheKey: 'cn_indices',
      ttlSeconds: 120,
      fetchedAt: '2026-05-06T09:08:00+08:00',
      expiresAt: '2026-05-06T09:10:00+08:00',
      isFresh: true,
      isRefreshing: false,
      lastError: null,
      persistentSnapshotAvailable: true,
      persistentSnapshotAgeMinutes: 2,
      status: 'live',
    },
    {
      cacheKey: 'market_briefing',
      ttlSeconds: 300,
      fetchedAt: '2026-05-06T08:10:00+08:00',
      expiresAt: '2026-05-06T08:15:00+08:00',
      isFresh: false,
      isRefreshing: true,
      lastError: 'provider timeout token=***',
      persistentSnapshotAvailable: true,
      persistentSnapshotAgeMinutes: 60,
      status: 'fallback',
    },
  ],
  limitations: ['cache_metadata_unavailable:rates', 'admin_logs_no_degraded_market_events_in_window'],
  adminLogDrillThrough: {
    label: '查看 Admin Logs',
    route: '/zh/admin/logs',
    query: { since: '24h', query: 'market provider' },
    eventId: null,
  },
  metadata: {
    source: 'market_cache_and_admin_logs',
    readOnly: true,
    externalProviderCalls: false,
    cacheMutation: false,
    rawProviderToken: 'SECRET',
  },
};

describe('MarketProviderOperationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the loading state before the read-only operations payload resolves', async () => {
    getOperations.mockReturnValue(new Promise(() => {}));

    render(<MarketProviderOperationsPage />);

    expect(screen.getByText('数据源运维')).toBeInTheDocument();
    expect(screen.getByText('正在读取市场数据源运维快照')).toBeInTheDocument();
  });

  it('lets the shared shell own the page background instead of locking a local pure-black slab', async () => {
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    const pageRoot = screen.getByTestId('market-provider-operations-page');
    expect(await screen.findByRole('heading', { name: '数据源运维' })).toBeInTheDocument();
    expect(pageRoot.className).not.toContain('bg-[#050505]');
    expect(pageRoot.className).not.toContain('bg-black');
  });

  it('renders Chinese-first operator hierarchy and keeps diagnostics available without exposing raw secrets', async () => {
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    expect(await screen.findByRole('heading', { name: '数据源运维' })).toBeInTheDocument();
    expect(screen.getAllByText('数据源健康').length).toBeGreaterThan(0);
    expect(screen.getAllByText('熔断状态').length).toBeGreaterThan(0);
    expect(screen.getAllByText('失败率').length).toBeGreaterThan(0);
    expect(screen.getAllByText('缓存状态').length).toBeGreaterThan(0);
    expect(screen.getAllByText('最近异常').length).toBeGreaterThan(0);
    expect(screen.getByText('新浪财经')).toBeInTheDocument();
    expect(screen.getByText('只读')).toBeInTheDocument();
    expect(screen.getByText('外部调用关闭')).toBeInTheDocument();
    expect(screen.getByText('缓存不变更')).toBeInTheDocument();
    expect(screen.getAllByText('诊断详情').length).toBeGreaterThan(0);
    expect(screen.getAllByText('缓存状态').length).toBeGreaterThan(0);
    expect(screen.getAllByText('最近异常').length).toBeGreaterThan(0);
    expect(screen.getAllByText('查看 Admin Logs').length).toBeGreaterThan(0);
    expect(screen.getAllByText('熔断状态').length).toBeGreaterThan(0);
    expect(screen.getAllByText('已脱敏').length).toBeGreaterThan(0);
    expect(screen.queryByText('SECRET')).not.toBeInTheDocument();
    expect(screen.queryByText(/token=/i)).not.toBeInTheDocument();

    const diagnosticsDisclosure = screen.getByTestId('market-provider-diagnostics-disclosure');
    const disclosureToggle = screen.getByRole('button', { name: '展开 诊断详情' });
    expect(disclosureToggle).toBeInTheDocument();
    expect(diagnosticsDisclosure).not.toHaveAttribute('open');
    fireEvent.click(disclosureToggle);
    expect(diagnosticsDisclosure).toHaveAttribute('open');
    expect(screen.getByRole('button', { name: '收起 诊断详情' })).toBeInTheDocument();
    expect(screen.getByText('cache_metadata_unavailable:rates')).toBeVisible();
  });

  it('normalizes missing metrics without rendering NaN or raising React warnings', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    getOperations.mockResolvedValue({
      ...populatedPayload,
      summary: { totalItems: 0 },
      items: [],
      eventRollups: [],
      cacheStates: [],
      limitations: [],
    } as typeof populatedPayload);

    render(<MarketProviderOperationsPage />);

    expect(await screen.findByText('暂无数据源运维条目')).toBeInTheDocument();
    expect(screen.getAllByText('待统计').length).toBeGreaterThan(0);
    expect(screen.queryByText('NaN')).not.toBeInTheDocument();
    expect(consoleErrorSpy.mock.calls.some((call) => call.join(' ').includes('Received NaN'))).toBe(false);
  });

  it('keeps raw diagnostics collapsed by default and preserves compact empty states', async () => {
    getOperations.mockResolvedValue({
      ...populatedPayload,
      summary: { ...populatedPayload.summary, totalItems: 0, eventCount: 0 },
      items: [],
      eventRollups: [],
      cacheStates: [],
      limitations: ['cache_metadata_unavailable:indices'],
    });

    render(<MarketProviderOperationsPage />);

    expect(await screen.findByText('暂无数据源运维条目')).toBeInTheDocument();
    expect(screen.getByText('暂无缓存状态')).toBeInTheDocument();
    expect(screen.getAllByText('窗口内暂无异常').length).toBeGreaterThan(0);
    expect(screen.getByText('缓存元数据未覆盖 indices')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '展开 诊断详情' })).toBeInTheDocument();
  });

  it('renders API errors with the existing alert pattern', async () => {
    getOperations.mockRejectedValue(new Error('admin required'));

    render(<MarketProviderOperationsPage />);

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(within(screen.getByRole('alert')).getByText('读取市场数据源运维失败')).toBeInTheDocument();
  });
});
