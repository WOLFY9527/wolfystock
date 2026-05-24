import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MarketProviderOperationsPage from '../MarketProviderOperationsPage';
import { resolveProductSetupSurface } from '../../utils/productSetupSurface';

const { getOperations } = vi.hoisted(() => ({
  getOperations: vi.fn(),
}));

const { getOperationsMatrix } = vi.hoisted(() => ({
  getOperationsMatrix: vi.fn(),
}));

const { getDataReadiness } = vi.hoisted(() => ({
  getDataReadiness: vi.fn(),
}));

vi.mock('../../api/marketProviderOperations', () => ({
  marketProviderOperationsApi: {
    getOperations,
    getOperationsMatrix,
  },
}));

vi.mock('../../api/market', () => ({
  marketApi: {
    getDataReadiness,
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
    providerDiagnostics: {
      tickflowCnBreadth: {
        provider: 'tickflow',
        market: 'cn',
        diagnosticTarget: 'cn_breadth',
        status: 'permission_denied',
        credentialState: 'configured',
        credentialConfigured: true,
        reachabilityState: 'reachable',
        tickflowReachable: true,
        breadthEntitlementState: 'permission_denied',
        breadthEntitlementUsable: false,
        reasonCode: 'tickflow_permission_unavailable',
        observedSource: 'fallback',
        sourceType: 'public_api',
        summary: 'TickFlow 已配置，但当前 key 没有 A 股宽度权限。',
      },
    },
    rawProviderToken: 'SECRET',
  },
};

const readinessPayload = {
  readinessStatus: 'partial',
  diagnosticOnly: true,
  providerRuntimeCalled: false,
  networkCallsEnabled: false,
  representativeSymbols: ['AAPL', 'SPY', 'BTC-USD'],
  checks: [
    {
      id: 'tushare_token',
      status: 'missing',
      severity: 'warning',
      userFacingMessage: 'Tushare token is not configured.',
      remediationHint: 'Set TUSHARE_TOKEN when local operators need Tushare-backed CN/HK market intelligence inputs.',
      affectsSurfaces: ['market_overview', 'liquidity_monitor'],
      productAffectedSurfaces: ['market_overview', 'liquidity_monitor'],
      secretConfigured: false,
    },
    {
      id: 'local_us_parquet_representative_files',
      status: 'partial',
      severity: 'warning',
      userFacingMessage: 'Representative US parquet files are missing for part of the requested symbol set.',
      remediationHint: 'Sync the missing parquet files or reduce the representative symbol list to locally available coverage.',
      affectsSurfaces: ['stock_history'],
      productAffectedSurfaces: ['provider_ops'],
      details: {
        representativeSymbols: ['AAPL', 'SPY', 'BTC-USD'],
        missingSymbols: ['BTC-USD'],
        existingCount: 2,
      },
    },
  ],
};

const operationsMatrixPayload = {
  generatedAt: '2026-05-06T09:12:00+08:00',
  diagnosticOnly: true,
  rows: [
    {
      providerId: 'official_public.fed_liquidity',
      providerName: 'Fed Liquidity',
      providerCategory: 'capability_support_contract',
      sourceType: 'missing',
      sourceTier: 'official_public',
      trustLevel: 'unknown',
      freshnessExpectation: 'delayed',
      runtimeState: 'missing_provider_configuration',
      credentialState: 'not_required',
      dependencyState: 'not_required',
      enabledByDefault: false,
      observationOnly: true,
      scoreContributionAllowed: false,
      sourceAuthorityAllowed: false,
      scoreEligible: false,
      inertMetadataOnly: true,
      paidDataLikelyRequired: false,
      keyRequired: false,
      noDefaultLiveHttpCalls: true,
      cacheRequired: true,
      supportedCapabilities: ['fed_liquidity'],
      affectedSurfaces: ['market_overview', 'liquidity_impulse'],
      productAffectedSurfaces: ['market_overview', 'liquidity_monitor'],
      routerReasonCodes: ['cache_required', 'freshness_floor_required', 'missing_provider_configuration'],
      missingProviderReason: 'official_fed_liquidity_contract_not_configured',
      degradationReason: 'missing_provider_configuration',
      remediationHint: 'Configure https://example.com/feed and read /var/tmp/provider before runtime.',
      diagnosticOnly: true,
    },
    {
      providerId: 'tushare_pro',
      providerName: 'Tushare Pro',
      providerCategory: 'runtime_capability',
      sourceType: 'official_public',
      sourceTier: 'runtime_metadata',
      trustLevel: 'score_grade',
      freshnessExpectation: 'daily',
      runtimeState: 'credential_missing',
      credentialState: 'missing',
      dependencyState: 'installed',
      enabledByDefault: true,
      observationOnly: false,
      scoreContributionAllowed: true,
      sourceAuthorityAllowed: true,
      scoreEligible: true,
      inertMetadataOnly: false,
      paidDataLikelyRequired: false,
      keyRequired: true,
      noDefaultLiveHttpCalls: true,
      cacheRequired: false,
      supportedCapabilities: ['cn_history_daily'],
      affectedSurfaces: ['scanner'],
      productAffectedSurfaces: ['scanner'],
      routerReasonCodes: ['credential_missing'],
      missingProviderReason: null,
      degradationReason: 'credential_missing',
      remediationHint: 'TUSHARE_TOKEN=super-secret-token',
      diagnosticOnly: true,
    },
    {
      providerId: 'polygon_us_grouped_daily',
      providerName: 'Polygon grouped daily US equities (computed breadth)',
      sourceLabel: 'Polygon grouped daily US equities (computed breadth)',
      providerCategory: 'computed_breadth_projection',
      sourceType: 'authorized_licensed_feed',
      sourceTier: 'official_or_authorized_licensed_feed',
      trustLevel: 'score_grade_for_computed_ad_metrics_when_fresh',
      freshnessExpectation: 'polygon_grouped_daily_eod_recent_completed_us_weekday',
      runtimeState: 'read_only_projection',
      credentialState: 'present',
      dependencyState: 'not_required',
      enabledByDefault: false,
      observationOnly: false,
      scoreContributionAllowed: true,
      sourceAuthorityAllowed: true,
      scoreEligible: false,
      inertMetadataOnly: true,
      paidDataLikelyRequired: true,
      keyRequired: true,
      noDefaultLiveHttpCalls: true,
      cacheRequired: true,
      supportedCapabilities: ['us_advancers_decliners'],
      affectedSurfaces: ['market_overview', 'liquidity_impulse'],
      productAffectedSurfaces: ['market_overview', 'liquidity_monitor'],
      routerReasonCodes: [],
      reasonCodes: ['polygon_high_low_history_unavailable'],
      fulfilledMetrics: ['ADVANCERS', 'DECLINERS', 'UNCHANGED', 'ADVANCE_DECLINE_RATIO'],
      missingMetrics: ['NEW_HIGHS', 'NEW_LOWS', 'HIGH_LOW_RATIO'],
      coverageCount: null,
      authorityBasis: 'computed_from_authorized_polygon_grouped_daily',
      universe: 'polygon_us_grouped_daily_ex_otc',
      officialExchangePublishedBreadth: false,
      fullBreadthAuthority: false,
      sourceFreshnessEvidence: {
        freshness: 'delayed',
        freshnessPolicy: 'polygon_grouped_daily_eod_recent_completed_us_weekday',
        isFallback: false,
        isPartial: true,
        isUnavailable: false,
      },
      missingProviderReason: null,
      degradationReason: null,
      remediationHint: null,
      diagnosticOnly: true,
    },
    {
      providerId: 'official_public.cn_money_market_cache',
      providerName: 'CN money-market official-public cache',
      sourceLabel: 'CN money-market official-public cache',
      providerCategory: 'capability_support_contract',
      sourceType: 'official_public',
      sourceTier: 'official_public',
      trustLevel: 'observation_grade',
      freshnessExpectation: 'daily',
      runtimeState: 'cache_ready_only',
      credentialState: 'not_required',
      dependencyState: 'not_required',
      enabledByDefault: false,
      observationOnly: false,
      scoreContributionAllowed: false,
      sourceAuthorityAllowed: true,
      scoreEligible: false,
      inertMetadataOnly: true,
      paidDataLikelyRequired: false,
      keyRequired: false,
      noDefaultLiveHttpCalls: true,
      cacheRequired: true,
      supportedCapabilities: ['cn_money_market'],
      affectedSurfaces: ['market_overview'],
      productAffectedSurfaces: ['market_overview'],
      routerReasonCodes: ['cache_required'],
      reasonCodes: [],
      fulfilledMetrics: ['money_market_levels'],
      missingMetrics: [],
      authorityBasis: 'official_public_cache_snapshot',
      universe: 'cn_money_market',
      coverageCount: 1,
      sourceFreshnessEvidence: {
        freshness: 'delayed',
        freshnessPolicy: 'daily_cache_snapshot',
        isFallback: false,
        isPartial: false,
        isUnavailable: false,
      },
      missingProviderReason: null,
      degradationReason: 'cache_only_contract',
      remediationHint: 'Refresh /var/cache/cn-money-market before runtime.',
      diagnosticOnly: true,
    },
    {
      providerId: 'cache.cn_hk_connect_daily',
      providerName: 'CN/HK connect cache',
      sourceLabel: 'CN/HK connect cache',
      providerCategory: 'capability_support_contract',
      sourceType: 'official_public',
      sourceTier: 'official_public',
      trustLevel: 'observation_grade',
      freshnessExpectation: 'daily',
      runtimeState: 'cache_ready_only',
      credentialState: 'not_required',
      dependencyState: 'not_required',
      enabledByDefault: false,
      observationOnly: true,
      scoreContributionAllowed: false,
      sourceAuthorityAllowed: true,
      scoreEligible: false,
      inertMetadataOnly: true,
      paidDataLikelyRequired: false,
      keyRequired: false,
      noDefaultLiveHttpCalls: true,
      cacheRequired: true,
      supportedCapabilities: ['northbound_southbound_connect_flow'],
      affectedSurfaces: ['rotation_radar'],
      productAffectedSurfaces: ['rotation_radar'],
      routerReasonCodes: ['cache_required'],
      reasonCodes: [],
      fulfilledMetrics: ['northbound_flow'],
      missingMetrics: ['southbound_flow'],
      authorityBasis: 'official_public_cache_snapshot',
      universe: 'cn_hk_connect',
      coverageCount: 1,
      sourceFreshnessEvidence: {
        freshness: 'delayed',
        freshnessPolicy: 'daily_cache_snapshot',
        isFallback: false,
        isPartial: true,
        isUnavailable: false,
      },
      missingProviderReason: null,
      degradationReason: 'cache_only_contract',
      remediationHint: 'Read /tmp/connect-cache before runtime.',
      diagnosticOnly: true,
    },
    {
      providerId: 'authorized.cn_index_futures_feed',
      providerName: 'Index futures authorized feed',
      sourceLabel: 'Index futures authorized feed',
      providerCategory: 'runtime_capability',
      sourceType: 'authorized_licensed_feed',
      sourceTier: 'authorized_licensed_feed',
      trustLevel: 'score_grade_when_fresh',
      freshnessExpectation: 'intraday',
      runtimeState: 'missing_provider_configuration',
      credentialState: 'missing',
      dependencyState: 'not_required',
      enabledByDefault: false,
      observationOnly: false,
      scoreContributionAllowed: false,
      sourceAuthorityAllowed: false,
      scoreEligible: false,
      inertMetadataOnly: false,
      paidDataLikelyRequired: true,
      keyRequired: true,
      noDefaultLiveHttpCalls: true,
      cacheRequired: false,
      supportedCapabilities: ['cn_index_futures'],
      affectedSurfaces: ['liquidity_monitor', 'options_lab'],
      productAffectedSurfaces: ['liquidity_monitor', 'options_lab'],
      routerReasonCodes: ['credential_missing'],
      reasonCodes: [],
      fulfilledMetrics: [],
      missingMetrics: ['if_main_contract', 'ih_main_contract'],
      authorityBasis: 'authorized_feed_contract',
      universe: 'cn_index_futures',
      coverageCount: null,
      sourceFreshnessEvidence: {
        freshness: 'unavailable',
        freshnessPolicy: 'authorized_intraday_feed',
        isFallback: false,
        isPartial: false,
        isUnavailable: true,
      },
      missingProviderReason: 'authorized_feed_missing',
      degradationReason: 'credential_missing',
      remediationHint: 'Load token from /opt/feeds/index-futures before runtime.',
      diagnosticOnly: true,
    },
    {
      providerId: 'legacy_surface_projection',
      providerName: 'Legacy surface projection',
      sourceLabel: 'Legacy surface projection',
      providerCategory: 'runtime_capability',
      sourceType: 'cache_snapshot',
      sourceTier: 'local_cache',
      trustLevel: 'reproducible_local_or_stored',
      freshnessExpectation: 'daily',
      runtimeState: 'observation_only',
      credentialState: 'not_required',
      dependencyState: 'not_required',
      enabledByDefault: false,
      observationOnly: true,
      scoreContributionAllowed: false,
      sourceAuthorityAllowed: true,
      scoreEligible: false,
      inertMetadataOnly: true,
      paidDataLikelyRequired: false,
      keyRequired: false,
      noDefaultLiveHttpCalls: true,
      cacheRequired: true,
      supportedCapabilities: ['diagnostic_surface_projection'],
      affectedSurfaces: ['mystery_surface'],
      productAffectedSurfaces: ['portfolio', 'watchlist'],
      routerReasonCodes: ['cache_required'],
      reasonCodes: [],
      fulfilledMetrics: [],
      missingMetrics: [],
      coverageCount: null,
      missingProviderReason: null,
      degradationReason: 'cache_only_contract',
      remediationHint: 'Refresh local diagnostic cache only.',
      diagnosticOnly: true,
    },
  ],
  summary: {
    totalRows: 7,
    observationOnlyRows: 3,
    inertMetadataOnlyRows: 5,
    missingProviderRows: 2,
    scoreEligibleRows: 1,
    paidDataLikelyRequiredRows: 2,
  },
  metadata: {
    source: 'provider_fit_capability_readiness_router_contracts',
    readOnly: true,
    diagnosticOnly: true,
    externalProviderCalls: false,
    providerProbesForced: false,
    networkCallsEnabled: false,
    cacheMutation: false,
    providerOrderChanged: false,
    dataFetcherManagerChanged: false,
    frontendChanged: false,
    dbChanged: false,
    secretValuesIncluded: false,
    rawProviderPayloadsIncluded: false,
    readinessStatus: 'partial',
    rowCount: 3,
    rawProviderUrl: 'https://secret-provider.example.com',
    localConfigPath: '/Users/example/provider',
  },
};

describe('MarketProviderOperationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getDataReadiness.mockResolvedValue(readinessPayload);
    getOperationsMatrix.mockResolvedValue(operationsMatrixPayload);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the loading state before the read-only operations payload resolves', async () => {
    getOperations.mockReturnValue(new Promise(() => {}));

    render(<MarketProviderOperationsPage />);

    expect(screen.getByText('数据源维护路线图')).toBeInTheDocument();
    expect(screen.getByText('正在读取数据源维护快照')).toBeInTheDocument();
  });

  it('lets the shared shell own the page background instead of locking a local pure-black slab', async () => {
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    const pageRoot = screen.getByTestId('market-provider-operations-page');
    expect(await screen.findByRole('heading', { name: '数据源维护路线图' })).toBeInTheDocument();
    expect(pageRoot.className).not.toContain('bg-[#050505]');
    expect(pageRoot.className).not.toContain('bg-black');
  });

  it('renders Chinese-first operator hierarchy and keeps diagnostics available without exposing raw secrets or backend credential names', async () => {
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    expect(await screen.findByRole('heading', { name: '数据源维护路线图' })).toBeInTheDocument();
    expect(screen.getAllByText('数据源健康').length).toBeGreaterThan(0);
    expect(screen.getAllByText('熔断状态').length).toBeGreaterThan(0);
    expect(screen.getAllByText('失败率').length).toBeGreaterThan(0);
    expect(screen.getAllByText('缓存状态').length).toBeGreaterThan(0);
    expect(screen.getAllByText('最近异常').length).toBeGreaterThan(0);
    expect(screen.getByText('新浪财经')).toBeInTheDocument();
    expect(screen.getByText('只读')).toBeInTheDocument();
    expect(screen.getByText('外部调用关闭')).toBeInTheDocument();
    expect(screen.getByText('缓存不变更')).toBeInTheDocument();
    expect(screen.getByText('本地行情就绪诊断')).toBeInTheDocument();
    expect(screen.getByText('diagnosticOnly')).toBeInTheDocument();
    expect(screen.getByText('providerRuntimeCalled')).toBeInTheDocument();
    expect(screen.getByText('networkCallsEnabled')).toBeInTheDocument();
    expect(screen.getByText('未配置')).toBeInTheDocument();
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('BTC-USD')).toBeInTheDocument();
    expect(screen.getByText('Tushare token is not configured.')).toBeInTheDocument();
    expect(screen.getByText('Set TUSHARE_TOKEN when local operators need Tushare-backed CN/HK market intelligence inputs.')).toBeInTheDocument();
    expect(screen.getByText('Representative US parquet files are missing for part of the requested symbol set.')).toBeInTheDocument();
    expect(screen.getByText('限制与快照摘要')).toBeInTheDocument();
    const gapBoard = screen.getByTestId('market-provider-source-gap-board');
    expect(gapBoard).toHaveTextContent('优先级路线图');
    expect(gapBoard).toHaveTextContent('P0 市场方向判断');
    expect(gapBoard).toHaveTextContent('P1 流动性方向');
    expect(gapBoard).toHaveTextContent('P3 区域 / 期货确认');
    expect(gapBoard).toHaveTextContent('Fed Liquidity');
    expect(gapBoard).toHaveTextContent('Polygon grouped daily US equities');
    expect(gapBoard).toHaveTextContent('AD-only');
    expect(gapBoard).toHaveTextContent('High/low missing');
    expect(gapBoard).not.toHaveTextContent('NYSE');
    expect(gapBoard).not.toHaveTextContent('Nasdaq');
    expect(gapBoard).toHaveTextContent('当前为什么不可用');
    expect(gapBoard).toHaveTextContent('解锁能力');
    expect(gapBoard).toHaveTextContent('所需工作');
    expect(gapBoard).toHaveTextContent('阻断评分级结论：是');
    expect(gapBoard).not.toHaveTextContent('missing_provider_configuration');
    expect(screen.queryByText('official_public.fed_liquidity')).not.toBeInTheDocument();
    expect(screen.getAllByText('缓存状态').length).toBeGreaterThan(0);
    expect(screen.getAllByText('最近异常').length).toBeGreaterThan(0);
    expect(screen.getAllByText('查看 Admin Logs').length).toBeGreaterThan(0);
    expect(screen.getAllByText('熔断状态').length).toBeGreaterThan(0);
    expect(screen.getAllByText('已脱敏').length).toBeGreaterThan(0);
    expect(screen.getByText('TickFlow A股宽度')).toBeInTheDocument();
    expect(screen.getByText('Key 已配置')).toBeInTheDocument();
    expect(screen.getByText('可达')).toBeInTheDocument();
    expect(screen.getByText('权限拒绝')).toBeInTheDocument();
    expect(screen.queryByText('SECRET')).not.toBeInTheDocument();
    expect(screen.queryByText(/token=/i)).not.toBeInTheDocument();
    expect(screen.queryByText('TUSHARE_TOKEN=super-secret-token')).not.toBeInTheDocument();
    expect(screen.queryByText('tickflow_permission_unavailable')).not.toBeInTheDocument();
    expect(screen.queryByText('https://secret-provider.example.com')).not.toBeInTheDocument();
    expect(screen.queryByText('/Users/example/provider')).not.toBeInTheDocument();

    const diagnosticsDisclosure = screen.getByTestId('market-provider-diagnostics-disclosure');
    const disclosureToggle = screen.getByRole('button', { name: '展开 二级细节：限制代码、快照摘要、追踪标识' });
    expect(disclosureToggle).toBeInTheDocument();
    expect(diagnosticsDisclosure).not.toHaveAttribute('open');
    fireEvent.click(disclosureToggle);
    expect(diagnosticsDisclosure).toHaveAttribute('open');
    expect(screen.getByRole('button', { name: '收起 二级细节：限制代码、快照摘要、追踪标识' })).toBeInTheDocument();
    expect(screen.getByText('cache_metadata_unavailable:rates')).toBeVisible();

    const matrixDisclosure = screen.getByTestId('market-provider-matrix-disclosure');
    expect(matrixDisclosure).not.toHaveAttribute('open');
    fireEvent.click(within(matrixDisclosure).getByRole('button', { name: '展开 完整 provider matrix' }));
    expect(matrixDisclosure).toHaveTextContent('official_public.fed_liquidity');
    expect(matrixDisclosure).toHaveTextContent('missing_provider_configuration');
    expect(matrixDisclosure).toHaveTextContent('cache_required');
    expect(matrixDisclosure).toHaveTextContent('polygon_us_grouped_daily');
    expect(matrixDisclosure).toHaveTextContent('present');
    expect(matrixDisclosure).toHaveTextContent('polygon_high_low_history_unavailable');
    expect(matrixDisclosure).toHaveTextContent('sourceAuthority=false');
    expect(matrixDisclosure).toHaveTextContent('score=false');
    expect(matrixDisclosure).toHaveTextContent('cache-required');
  });

  it('renders a provider setup checklist with grouped affected surfaces, safe badges, and curated guidance only', async () => {
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    expect(await screen.findByText('Provider Setup Checklist')).toBeInTheDocument();
    const checklist = screen.getByTestId('market-provider-setup-checklist');
    expect(checklist).toHaveTextContent('Market Overview');
    expect(checklist).toHaveTextContent('Liquidity Monitor');
    expect(checklist).toHaveTextContent('Rotation Radar');
    expect(checklist).toHaveTextContent('Scanner');
    expect(checklist).toHaveTextContent('Portfolio');
    expect(checklist).toHaveTextContent('Watchlist');
    expect(checklist).toHaveTextContent('Options Lab');
    expect(checklist).toHaveTextContent('Provider Ops / system diagnostics');
    expect(checklist).toHaveTextContent('需要凭据');
    expect(checklist).toHaveTextContent('可能需付费');
    expect(checklist).toHaveTextContent('需要缓存');
    expect(checklist).toHaveTextContent('official-public cache-only');
    expect(checklist).toHaveTextContent('默认关闭');
    expect(checklist).toHaveTextContent('聚合证据');
    expect(checklist).toHaveTextContent('仅观察');
    expect(checklist).toHaveTextContent('评分阻断');
    expect(checklist).toHaveTextContent('missing provider');
    expect(checklist).toHaveTextContent('Use the existing Tushare credential setup and keep secret values out of this page.');
    expect(checklist).toHaveTextContent('Keep Polygon grouped-daily breadth on the approved credential-plus-cache path before using it for primary US posture context.');
    expect(checklist).toHaveTextContent('Sync the approved local US parquet/cache coverage before expecting representative history checks to clear.');
    expect(checklist).toHaveTextContent('Refresh the approved official-public money-market cache snapshot; this page stays read-only.');
    expect(checklist).toHaveTextContent('Refresh the CN/HK connect cache snapshot so rotation context is available without live provider calls.');
    expect(checklist).toHaveTextContent('Add the existing Fed liquidity aggregate evidence cache so broad liquidity context is visible without implying a trade signal.');
    expect(checklist).toHaveTextContent('Complete the existing authorized feed setup for index futures before relying on it for futures confirmation.');
    expect(checklist).not.toHaveTextContent('polygon_high_low_history_unavailable');
    expect(checklist).not.toHaveTextContent('missing_provider_configuration');
    expect(checklist).not.toHaveTextContent('cache_only_contract');
    expect(checklist).not.toHaveTextContent('authorized_feed_missing');
    expect(checklist).not.toHaveTextContent('https://secret-provider.example.com');
    expect(checklist).not.toHaveTextContent('/Users/example/provider');
    expect(checklist).not.toHaveTextContent('/var/cache/cn-money-market');
    expect(checklist).not.toHaveTextContent('/tmp/connect-cache');
    expect(checklist).not.toHaveTextContent('/opt/feeds/index-futures');
    expect(checklist).not.toHaveTextContent('super-secret-token');
    expect(checklist).not.toHaveTextContent('mystery_surface');
    expect(checklist).not.toHaveTextContent('credential required');
    expect(checklist).not.toHaveTextContent('paid likely');
    expect(checklist).not.toHaveTextContent('cache required');
    expect(checklist).not.toHaveTextContent('disabled by default');
    expect(checklist).not.toHaveTextContent('aggregate-supported');
    expect(checklist).not.toHaveTextContent('observation-only');
    expect(checklist).not.toHaveTextContent('score-blocked');

    const checklistText = checklist.textContent || '';
    expect(checklistText.indexOf('Portfolio')).toBeLessThan(checklistText.indexOf('Watchlist'));
    expect(checklistText.indexOf('Watchlist')).toBeLessThan(checklistText.indexOf('Options Lab'));

    const matrixDisclosure = screen.getByTestId('market-provider-matrix-disclosure');
    fireEvent.click(within(matrixDisclosure).getByRole('button', { name: '展开 完整 provider matrix' }));
    expect(matrixDisclosure).toHaveTextContent('cache-required');
    expect(matrixDisclosure).toHaveTextContent('present');
    expect(matrixDisclosure).toHaveTextContent('polygon_high_low_history_unavailable');
    expect(matrixDisclosure).toHaveTextContent('missing_provider_configuration');
    expect(within(matrixDisclosure).getByRole('button', { name: '收起 完整 provider matrix' })).toBeInTheDocument();
  });

  it('honors a safe surface query for setup focus without hiding full diagnostics', async () => {
    const previousPath = window.location.pathname;
    const previousSearch = window.location.search;
    window.history.replaceState({}, '', '/admin/market-providers?surface=market_overview');
    getOperations.mockResolvedValue(populatedPayload);

    try {
      render(<MarketProviderOperationsPage />);

      expect(await screen.findByText('Provider Setup Checklist')).toBeInTheDocument();
      const focus = screen.getByTestId('market-provider-setup-surface-focus');
      expect(focus).toHaveTextContent('已按 Market Overview 聚焦');
      expect(focus).toHaveTextContent('改善证据覆盖');
      const checklist = screen.getByTestId('market-provider-setup-checklist');
      expect(checklist).toHaveTextContent('Market Overview');
      expect(checklist).toHaveTextContent('Fed Liquidity');
      expect(checklist).toHaveTextContent('Polygon grouped daily US equities');
      expect(checklist).not.toHaveTextContent('Rotation Radar');
      expect(checklist).not.toHaveTextContent('Portfolio');

      const matrixDisclosure = screen.getByTestId('market-provider-matrix-disclosure');
      fireEvent.click(within(matrixDisclosure).getByRole('button', { name: '展开 完整 provider matrix' }));
      expect(matrixDisclosure).toHaveTextContent('cache.cn_hk_connect_daily');
      expect(matrixDisclosure).toHaveTextContent('authorized.cn_index_futures_feed');
    } finally {
      window.history.replaceState({}, '', `${previousPath}${previousSearch}`);
    }
  });

  it('ignores unknown unsafe surface query text without rendering it', async () => {
    const previousPath = window.location.pathname;
    const previousSearch = window.location.search;
    window.history.replaceState({}, '', '/admin/market-providers?surface=%2FUsers%2Fexample%2Fprovider&token=super-secret-token');
    getOperations.mockResolvedValue(populatedPayload);

    try {
      render(<MarketProviderOperationsPage />);

      expect(await screen.findByText('Provider Setup Checklist')).toBeInTheDocument();
      expect(screen.queryByTestId('market-provider-setup-surface-focus')).not.toBeInTheDocument();
      const checklist = screen.getByTestId('market-provider-setup-checklist');
      expect(checklist).toHaveTextContent('Market Overview');
      expect(checklist).toHaveTextContent('Rotation Radar');
      expect(document.body.textContent || '').not.toContain('/Users/example/provider');
      expect(document.body.textContent || '').not.toContain('super-secret-token');
    } finally {
      window.history.replaceState({}, '', `${previousPath}${previousSearch}`);
    }
  });

  it('accepts existing and new safe setup surfaces while rejecting unknown or unsafe values', () => {
    expect(resolveProductSetupSurface('market_overview')?.key).toBe('market_overview');
    expect(resolveProductSetupSurface('liquidity_monitor')?.key).toBe('liquidity_monitor');
    expect(resolveProductSetupSurface('rotation_radar')?.key).toBe('rotation_radar');
    expect(resolveProductSetupSurface('portfolio')?.key).toBe('portfolio');
    expect(resolveProductSetupSurface('watchlist')?.key).toBe('watchlist');
    expect(resolveProductSetupSurface('options_lab')?.key).toBe('options_lab');
    expect(resolveProductSetupSurface('/Users/example/provider')).toBeNull();
    expect(resolveProductSetupSurface('javascript:alert(1)')).toBeNull();
    expect(resolveProductSetupSurface('watchlist&token=secret')).toBeNull();
  });

  it('supports a compact representative symbol override for readiness checks', async () => {
    getOperations.mockResolvedValue(populatedPayload);
    getDataReadiness.mockResolvedValue(readinessPayload);

    render(<MarketProviderOperationsPage />);

    expect(await screen.findByText('本地行情就绪诊断')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('代表符号'), { target: { value: 'msft, qqq, nvda' } });
    fireEvent.click(screen.getByRole('button', { name: '更新样本' }));

    await waitFor(() => {
      expect(getDataReadiness).toHaveBeenLastCalledWith({ symbols: 'msft, qqq, nvda' });
    });
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

  it('shows a compact empty state when the operations matrix has no rows', async () => {
    getOperations.mockResolvedValue(populatedPayload);
    getOperationsMatrix.mockResolvedValue({
      ...operationsMatrixPayload,
      rows: [],
      summary: {
        ...operationsMatrixPayload.summary,
        totalRows: 0,
        observationOnlyRows: 0,
        inertMetadataOnlyRows: 0,
        missingProviderRows: 0,
        scoreEligibleRows: 0,
      },
      metadata: {
        ...operationsMatrixPayload.metadata,
        rowCount: 0,
      },
    });

    render(<MarketProviderOperationsPage />);

    expect(await screen.findByText('数据源优先级路线图')).toBeInTheDocument();
    expect(screen.getByText('暂无 provider matrix 行')).toBeInTheDocument();
  });

  it('renders a section-scoped API error when the operations matrix request fails', async () => {
    getOperations.mockResolvedValue(populatedPayload);
    getOperationsMatrix.mockRejectedValue(new Error('forbidden'));

    render(<MarketProviderOperationsPage />);

    expect(await screen.findByRole('heading', { name: '数据源维护路线图' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('读取 provider operations matrix 失败')).toBeInTheDocument());
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
    expect(screen.getByRole('button', { name: '展开 二级细节：限制代码、快照摘要、追踪标识' })).toBeInTheDocument();
  });

  it('renders API errors with the existing alert pattern', async () => {
    getOperations.mockRejectedValue(new Error('admin required'));

    render(<MarketProviderOperationsPage />);

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(within(screen.getByRole('alert')).getByText('读取市场数据源运维失败')).toBeInTheDocument();
  });
});
