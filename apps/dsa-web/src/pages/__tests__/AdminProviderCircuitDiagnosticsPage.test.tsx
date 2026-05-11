import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminProviderCircuitDiagnosticsPage from '../AdminProviderCircuitDiagnosticsPage';

const { getDiagnostics, useProductSurfaceMock } = vi.hoisted(() => ({
  getDiagnostics: vi.fn(),
  useProductSurfaceMock: vi.fn(),
}));

vi.mock('../../api/adminProviderCircuits', () => ({
  adminProviderCircuitsApi: {
    getDiagnostics,
  },
}));

vi.mock('../../hooks/useProductSurface', () => ({
  useProductSurface: () => useProductSurfaceMock(),
}));

const response = {
  states: {
    generatedAt: '2026-05-06T09:10:00+08:00',
    metadata: {
      readOnly: true,
      noExternalCalls: true,
      liveEnforcement: false,
      providerBehaviorChanged: false,
      marketCacheBehaviorChanged: false,
      dataSources: ['provider_circuit_states'],
      redaction: ['metadata_omitted'],
      limit: 50,
      filters: {},
      rawSecret: 'SECRET',
    },
    items: [
      {
        provider: 'finnhub',
        providerCategory: 'quote',
        routeFamily: 'analysis',
        state: 'open',
        reasonBucket: 'provider_429',
        cooldownUntil: '2026-05-06T09:30:00+08:00',
        updatedAt: '2026-05-06T09:08:00+08:00',
      },
    ],
  },
  events: {
    generatedAt: '2026-05-06T09:10:00+08:00',
    metadata: { readOnly: true, noExternalCalls: true, liveEnforcement: false, providerBehaviorChanged: false, marketCacheBehaviorChanged: false, dataSources: [], redaction: [], limit: 50, filters: {} },
    items: [
      {
        provider: 'finnhub',
        providerCategory: 'quote',
        routeFamily: 'analysis',
        eventType: 'state_transition',
        fromState: 'closed',
        toState: 'open',
        reasonBucket: 'provider_429',
        requestCountBucket: '10_20',
        durationBucketMs: 250,
        failureCountBucket: '5_10',
        createdAt: '2026-05-06T09:08:00+08:00',
      },
    ],
  },
  quotaWindows: {
    generatedAt: '2026-05-06T09:10:00+08:00',
    metadata: { readOnly: true, noExternalCalls: true, liveEnforcement: false, providerBehaviorChanged: false, marketCacheBehaviorChanged: false, dataSources: [], redaction: [], limit: 50, filters: {} },
    items: [
      {
        provider: 'finnhub',
        providerCategory: 'quote',
        routeFamily: 'analysis',
        windowType: 'hour',
        windowStart: '2026-05-06T09:00:00+08:00',
        windowEnd: '2026-05-06T10:00:00+08:00',
        requestCount: 12,
        reservedUnits: 0,
        consumedUnits: 12,
        releasedUnits: 0,
        rejectedCount: 2,
        successCount: 7,
        failureCount: 5,
        timeoutCount: 1,
        provider429Count: 4,
        provider403Count: 0,
        fallbackCount: 3,
        probeCount: 1,
        cacheOnlyCount: 0,
        staleServedCount: 0,
      },
    ],
  },
  probeEvents: {
    generatedAt: '2026-05-06T09:10:00+08:00',
    metadata: { readOnly: true, noExternalCalls: true, liveEnforcement: false, providerBehaviorChanged: false, marketCacheBehaviorChanged: false, dataSources: [], redaction: [], limit: 50, filters: {} },
    items: [
      {
        provider: 'finnhub',
        providerCategory: 'probe',
        routeFamily: 'admin_provider_probe',
        probeType: 'admin_connectivity',
        probeSource: 'admin',
        resultBucket: 'success',
        durationBucketMs: 120,
        createdAt: '2026-05-06T09:07:00+08:00',
      },
    ],
  },
  slaReadiness: {
    generatedAt: '2026-05-06T09:10:00+08:00',
    metadata: { readOnly: true, noExternalCalls: true, liveEnforcement: false, providerBehaviorChanged: false, marketCacheBehaviorChanged: false, dataSources: [], redaction: [], limit: 50, filters: {} },
    items: [
      {
        provider: 'tradier',
        providerCategory: 'options',
        routeFamily: 'options_lab',
        readinessState: 'live_credentials_present_live_calls_disabled',
        reasonCode: 'options_provider_live_calls_disabled',
        credentialState: 'configured',
        liveProvidersEnabled: true,
        providerEnabled: true,
        credentialsPresent: true,
        dryRunEnabled: false,
        liveHttpCallsEnabled: false,
        brokerOrderPathEnabled: false,
        portfolioMutationPathEnabled: false,
        tradeableData: false,
        latencyBucketMs: 1500,
        latencyState: 'slow',
        errorRate: 0.2,
        errorState: 'elevated',
        freshnessSeconds: 300,
        freshnessState: 'fresh',
        recentErrors: [
          { reasonBucket: 'timeout', countBucket: '1', latestAt: '2026-05-06T09:07:00+08:00' },
        ],
        trendSummary: {
          windowCountBucket: '1',
          requestCountBucket: '6_20',
          failureCountBucket: '2_5',
          timeoutCountBucket: '1',
          provider429CountBucket: '2_5',
          provider403CountBucket: '0',
          latestObservationAt: '2026-05-06T09:07:00+08:00',
        },
        circuitAdvisoryState: 'open_candidate',
        circuitStateCandidate: 'open',
        liveEnforcement: false,
        wouldBlockCall: false,
        wouldChangeProviderOrder: false,
        wouldChangeFallbackBehavior: false,
        noExternalCalls: true,
      },
    ],
  },
};

describe('AdminProviderCircuitDiagnosticsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useProductSurfaceMock.mockReturnValue({ canReadProviders: true });
  });

  it('renders provider circuit states, events, quota windows, probes, and read-only boundary copy', async () => {
    getDiagnostics.mockResolvedValue(response);

    const { container } = render(<AdminProviderCircuitDiagnosticsPage />);

    expect(screen.getByText('Provider 熔断诊断')).toBeInTheDocument();
    expect(container.querySelector('[data-terminal-primitive="page-shell"]')).not.toBeNull();
    expect(container.querySelector('[data-terminal-primitive="page-heading"]')).not.toBeNull();
    expect(container.querySelector('[data-terminal-primitive="notice"]')).not.toBeNull();
    expect(container.querySelector('[data-terminal-primitive="disclosure"]')).not.toBeNull();
    expect(await screen.findByText('页面用途')).toBeInTheDocument();
    expect(screen.getByText('当前状态')).toBeInTheDocument();
    expect(screen.getByText('下一步')).toBeInTheDocument();
    expect(screen.getByText('定位 provider 熔断风险')).toBeInTheDocument();
    expect(screen.getByText('部分生产调用应暂缓')).toBeInTheDocument();
    expect(screen.getByText('1 个熔断打开')).toBeInTheDocument();
    expect(screen.getByText('先核对凭证与当前熔断')).toBeInTheDocument();
    expect(screen.getByText('需关注')).toBeInTheDocument();
    expect(screen.getByText('诊断范围')).toBeInTheDocument();
    expect((await screen.findAllByText('finnhub')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('当前为诊断观测，不会改变 provider fallback 或 MarketCache 行为。').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Provider 429').length).toBeGreaterThan(0);
    expect(screen.getByText('Provider SLA / 凭证就绪')).toBeInTheDocument();
    expect(screen.getByText('已配置')).toBeInTheDocument();
    expect(screen.getByText('趋势请求')).toBeInTheDocument();
    expect(screen.getByText('6_20')).toBeInTheDocument();
    expect(screen.getByText('最近错误 buckets')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '展开 二级细节：探测、事件、配额窗口、路由 bucket' }));
    expect(screen.getByText('最近熔断事件')).toBeInTheDocument();
    expect(screen.getAllByText('配额窗口').length).toBeGreaterThan(0);
    expect(screen.getByText('探测事件')).toBeInTheDocument();
    expect(screen.getByText('只读诊断').closest('[data-terminal-primitive="chip"]')).not.toBeNull();
    expect(screen.getByText('不触发外部调用')).toBeInTheDocument();
    expect(screen.getByText('不执行熔断门禁')).toBeInTheDocument();
    expect(screen.getByText('不触发外部调用').closest('[data-terminal-primitive="chip"]')).not.toBeNull();
    expect(screen.getByText('不执行熔断门禁').closest('[data-terminal-primitive="chip"]')).not.toBeNull();
    expect(screen.getByText('只读快照').closest('[data-terminal-primitive="chip"]')).not.toBeNull();
    expect(screen.getByText('打开').closest('[data-terminal-primitive="chip"]')).not.toBeNull();
    expect(screen.getByText('只读 · 外部调用关闭').closest('[data-terminal-primitive="chip"]')).not.toBeNull();
    expect(screen.queryByText('ops:providers:read')).not.toBeInTheDocument();
    expect(screen.queryByText(/live call/i)).not.toBeInTheDocument();
    expect(screen.queryByText('SECRET')).not.toBeInTheDocument();
  });

  it('does not render or fetch when provider read capability is missing', () => {
    useProductSurfaceMock.mockReturnValue({ canReadProviders: false });

    const { container } = render(<AdminProviderCircuitDiagnosticsPage />);

    expect(container).toBeEmptyDOMElement();
    expect(getDiagnostics).not.toHaveBeenCalled();
  });

  it('redacts suspicious URL or secret-shaped values before display', async () => {
    getDiagnostics.mockResolvedValue({
      ...response,
      states: {
        ...response.states,
        items: [
          {
            ...response.states.items[0],
            reasonBucket: 'https://provider.example/query?token=SECRET',
          },
        ],
      },
    });

    render(<AdminProviderCircuitDiagnosticsPage />);

    expect(await screen.findByText('已脱敏')).toBeInTheDocument();
    expect(screen.queryByText('https://provider.example/query?token=SECRET')).not.toBeInTheDocument();
  });

  it('renders API errors with the shared alert pattern', async () => {
    getDiagnostics.mockRejectedValue(new Error('admin required'));

    render(<AdminProviderCircuitDiagnosticsPage />);

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByText('读取 provider 熔断诊断失败')).toBeInTheDocument();
  });
});
