import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
    window.history.replaceState({}, '', '/zh/admin/provider-circuits');
  });

  it('renders compressed operational verdict and four L1 summary metrics', async () => {
    getDiagnostics.mockResolvedValue(response);

    const { container } = render(<AdminProviderCircuitDiagnosticsPage />);
    const overviewStrip = await screen.findByTestId('provider-circuit-l0-overview-strip');

    expect(screen.getByText('Provider 熔断诊断')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('信任状态')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('影响范围')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('建议动作')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('证据参考')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('最近更新')).toBeInTheDocument();
    expect(container.querySelector('[data-terminal-primitive="page-shell"]')).not.toBeNull();
    expect(container.querySelector('[data-terminal-primitive="page-heading"]')).not.toBeNull();
    expect(container.querySelector('[data-terminal-primitive="disclosure"]')).not.toBeNull();
    expect(getDiagnostics).toHaveBeenCalledWith({ limit: 50 });

    expect(await screen.findByText('L0 运行判定')).toBeInTheDocument();
    expect(screen.getByText('Provider 熔断需要管理员处理')).toBeInTheDocument();
    const verdict = screen.getByTestId('provider-circuit-operational-verdict');
    expect(within(verdict).getByText('BLOCKED')).toBeInTheDocument();
    expect(within(verdict).getByText('按下方动作列表先处理阻断项')).toBeInTheDocument();

    const summaryMetrics = screen.getByTestId('provider-circuit-summary-metrics');
    expect(summaryMetrics.querySelectorAll('[data-terminal-primitive="nested-block"]')).toHaveLength(4);
    expect(within(summaryMetrics).getByText('熔断状态')).toBeInTheDocument();
    expect(within(summaryMetrics).getByText('1 打开')).toBeInTheDocument();
    expect(within(summaryMetrics).getByText('SLA 阻断')).toBeInTheDocument();
    expect(within(summaryMetrics).getByText('1 观察')).toBeInTheDocument();
    expect(within(summaryMetrics).getByText('配额压力')).toBeInTheDocument();
    expect(within(summaryMetrics).getByText('2 拒绝')).toBeInTheDocument();
    expect(within(summaryMetrics).getByText('探测结果')).toBeInTheDocument();
    expect(within(summaryMetrics).getByText('1 正常')).toBeInTheDocument();
  });

  it('renders a compact ranked action list from degraded state, quota, SLA, and probe signals', async () => {
    getDiagnostics.mockResolvedValue({
      ...response,
      probeEvents: {
        ...response.probeEvents,
        items: [
          {
            ...response.probeEvents.items[0],
            resultBucket: 'timeout',
          },
        ],
      },
    });

    render(<AdminProviderCircuitDiagnosticsPage />);

    const actionList = await screen.findByTestId('provider-circuit-action-list');
    await waitFor(() => {
      expect(within(actionList).getAllByRole('listitem')).toHaveLength(4);
    });
    expect(within(actionList).queryByText('正在根据现有熔断、SLA、配额与探测快照生成动作队列。')).not.toBeInTheDocument();
    const rows = within(actionList).getAllByRole('listitem');
    expect(rows).toHaveLength(4);
    expect(within(rows[0]).getByText('finnhub 熔断打开')).toBeInTheDocument();
    expect(within(rows[1]).getByText('finnhub 探测未成功')).toBeInTheDocument();
    expect(within(rows[2]).getByText('finnhub 配额窗口出现拒绝或限流')).toBeInTheDocument();
    expect(within(rows[3]).getByText('tradier SLA / 凭证需核对')).toBeInTheDocument();
    expect(within(actionList).getAllByText('影响')).toHaveLength(4);
    expect(within(actionList).getAllByText('下一步')).toHaveLength(4);
  });

  it('keeps provider, event, quota, probe, bucket, and boundary diagnostics behind collapsed L3 disclosure', async () => {
    getDiagnostics.mockResolvedValue(response);

    render(<AdminProviderCircuitDiagnosticsPage />);

    expect(await screen.findByText('L2 分组诊断：熔断状态 / 事件 / 配额 / 探测 / SLA（已脱敏摘要）')).toBeInTheDocument();
    expect(screen.queryByText('最近熔断事件')).not.toBeInTheDocument();
    expect(screen.queryByText('配额窗口')).not.toBeInTheDocument();
    expect(screen.queryByText('探测事件')).not.toBeInTheDocument();
    expect(screen.queryByText('Provider SLA / 凭证就绪')).not.toBeInTheDocument();
    expect(screen.queryByText('Provider 429')).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('展开 L2 分组诊断：熔断状态 / 事件 / 配额 / 探测 / SLA（已脱敏摘要）'));

    expect((await screen.findAllByText('finnhub')).length).toBeGreaterThan(0);
    expect(screen.getByText('熔断状态与当前门禁')).toBeInTheDocument();
    expect(screen.getByText('SLA / 凭证就绪')).toBeInTheDocument();
    expect(screen.getByText('熔断事件、配额窗口与探测事件')).toBeInTheDocument();
    expect(screen.getAllByText('当前为诊断观测，不会改变 provider fallback 或 MarketCache 行为。').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Provider 429').length).toBeGreaterThan(0);
    expect(screen.getByText('Provider SLA / 凭证就绪')).toBeInTheDocument();
    expect(screen.getByText('已配置')).toBeInTheDocument();
    expect(screen.getByText('趋势请求')).toBeInTheDocument();
    expect(screen.getByText('6_20')).toBeInTheDocument();
    expect(screen.getByText('L3 最近错误 buckets：已脱敏原因 / 计数 / 最近观察')).toBeInTheDocument();
    expect(screen.getByText('最近熔断事件')).toBeInTheDocument();
    expect(screen.getAllByText('配额窗口').length).toBeGreaterThan(0);
    expect(screen.getByText('探测事件')).toBeInTheDocument();
    expect(screen.getByText('只读诊断').closest('[data-terminal-primitive="chip"]')).not.toBeNull();
    expect(screen.getByText('不触发外部调用')).toBeInTheDocument();
    expect(screen.getByText('不执行熔断门禁')).toBeInTheDocument();
    expect(screen.getByText('不触发外部调用').closest('[data-terminal-primitive="chip"]')).not.toBeNull();
    expect(screen.getByText('不执行熔断门禁').closest('[data-terminal-primitive="chip"]')).not.toBeNull();
    expect(
      screen
        .getAllByText(/个状态快照|只读快照/)
        .find((element) => element.closest('[data-terminal-primitive="chip"]'))
        ?.closest('[data-terminal-primitive="chip"]'),
    ).not.toBeNull();
    expect(screen.getByText('打开').closest('[data-terminal-primitive="chip"]')).not.toBeNull();
    expect(
      screen
        .getAllByText(/个就绪信号 · 外呼关闭|只读 · 外部调用关闭/)
        .find((element) => element.closest('[data-terminal-primitive="chip"]'))
        ?.closest('[data-terminal-primitive="chip"]'),
    ).not.toBeNull();
    expect(screen.queryByText('ops:providers:read')).not.toBeInTheDocument();
    expect(screen.queryByText(/live call/i)).not.toBeInTheDocument();
    expect(screen.queryByText('SECRET')).not.toBeInTheDocument();
  });

  it('does not keep a page-local pure-black slab on the route root', async () => {
    getDiagnostics.mockResolvedValue(response);

    render(<AdminProviderCircuitDiagnosticsPage />);

    const routeRoot = await screen.findByTestId('admin-provider-circuit-diagnostics-page');
    const shell = routeRoot.querySelector('[data-terminal-primitive="page-shell"]');

    expect(routeRoot).not.toHaveClass('bg-[#050505]');
    expect(routeRoot).not.toHaveClass('py-5', 'md:py-6');
    expect(shell).toHaveClass('py-5', 'md:py-6');
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

    expect(await screen.findByText(/已脱敏线索/)).toBeInTheDocument();
    expect(screen.queryByText('https://provider.example/query?token=SECRET')).not.toBeInTheDocument();
  });

  it('initializes safe provider filters from query params and exposes sanitized drill-through links', async () => {
    window.history.replaceState({}, '', '/zh/admin/provider-circuits?provider=Finnhub&routeFamily=analysis&since=24h&token=SECRET');
    getDiagnostics.mockResolvedValue(response);

    render(<AdminProviderCircuitDiagnosticsPage />);

    await screen.findByTestId('provider-circuit-l0-overview-strip');
    expect(getDiagnostics).toHaveBeenCalledWith({ limit: 50, provider: 'finnhub', routeFamily: 'analysis', since: '24h' });
    expect(screen.getByRole('link', { name: /查看相关日志/i })).toHaveAttribute('href', '/zh/admin/logs?tab=data_source&query=finnhub&since=24h');
    expect(screen.getByRole('link', { name: /查看数据源维护/i })).toHaveAttribute('href', '/zh/admin/market-providers?surface=market_overview');
    expect(screen.getByRole('link', { name: /查看成本观测/i })).toHaveAttribute('href', '/zh/admin/cost-observability?window=24h&area=provider');
    expect(document.body).not.toHaveTextContent('SECRET');
  });

  it('renders API errors with the shared alert pattern', async () => {
    getDiagnostics.mockRejectedValue(new Error('admin required'));

    render(<AdminProviderCircuitDiagnosticsPage />);

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByText('读取 provider 熔断诊断失败')).toBeInTheDocument();
  });
});
