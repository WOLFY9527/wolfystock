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

const { getHistoricalOhlcvCachePreflight } = vi.hoisted(() => ({
  getHistoricalOhlcvCachePreflight: vi.fn(),
}));

const { getDataReadiness } = vi.hoisted(() => ({
  getDataReadiness: vi.fn(),
}));

const { getDataSourceGapRegistry } = vi.hoisted(() => ({
  getDataSourceGapRegistry: vi.fn(),
}));

const { getProfessionalDataCapabilitiesAdmin } = vi.hoisted(() => ({
  getProfessionalDataCapabilitiesAdmin: vi.fn(),
}));

vi.mock('../../api/marketProviderOperations', () => ({
  marketProviderOperationsApi: {
    getOperations,
    getOperationsMatrix,
    getHistoricalOhlcvCachePreflight,
  },
}));

vi.mock('../../api/market', async () => {
  const actual = await vi.importActual<typeof import('../../api/market')>('../../api/market');
  return {
    ...actual,
    marketApi: {
      getDataReadiness,
      getDataSourceGapRegistry,
      getProfessionalDataCapabilitiesAdmin,
    },
  };
});

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
  consumerEvidenceReadinessMatrix: {
    contractVersion: 'consumer_evidence_readiness_matrix_v1',
    diagnosticOnly: true,
    networkCallsEnabled: false,
    mutationEnabled: false,
    items: [
      {
        surface: 'market_overview',
        evidenceFamily: 'market_regime',
        requiredInputs: ['macro context', 'liquidity context', 'rotation context', 'market breadth context'],
        fulfilledInputs: ['market overview read model'],
        missingInputs: ['market breadth context'],
        staleInputs: [],
        blockedInputs: ['macro context'],
        observationOnlyInputs: ['liquidity context', 'rotation context'],
        scoreGradeInputs: ['market overview read model'],
        readinessState: 'score_grade',
        confidenceCapReason: 'Only the overview read model is score-grade; supporting families still cap confidence.',
        sourceAuthorityReason: 'Supporting families need stronger display authority before they can lift the cap.',
        freshnessReason: 'Freshness is measured by each existing market surface before this matrix is shown.',
        nextDiagnostic: 'Compare overview evidence families against current safe surface snapshots.',
        consumerSafeSummary: 'Market overview has one score-grade input, while supporting evidence remains capped or observational.',
      },
      {
        surface: 'decision_cockpit',
        evidenceFamily: 'decision_context',
        requiredInputs: ['market overview', 'research radar', 'liquidity monitor', 'rotation radar', 'options observation'],
        fulfilledInputs: ['market overview'],
        missingInputs: ['research radar', 'options observation'],
        staleInputs: [],
        blockedInputs: ['liquidity monitor', 'rotation radar'],
        observationOnlyInputs: ['market overview'],
        scoreGradeInputs: [],
        readinessState: 'missing',
        confidenceCapReason: 'Cross-surface decision context is incomplete.',
        sourceAuthorityReason: 'Downstream surfaces cannot be promoted while required evidence is missing or blocked.',
        freshnessReason: 'Freshness remains unresolved until all required families are present.',
        nextDiagnostic: 'Build a cockpit driver table from existing market and research read models.',
        consumerSafeSummary: 'Decision cockpit is missing required cross-surface evidence and cannot make a strong market judgment.',
      },
      {
        surface: 'research_radar',
        evidenceFamily: 'research_prerequisites',
        requiredInputs: ['completed scanner evidence', 'watchlist research context', 'candidate evidence quality'],
        fulfilledInputs: ['consumer-safe research projection'],
        missingInputs: ['completed scanner evidence', 'watchlist research context'],
        staleInputs: [],
        blockedInputs: [],
        observationOnlyInputs: ['consumer-safe research projection'],
        scoreGradeInputs: [],
        readinessState: 'observation_only',
        confidenceCapReason: 'Research radar is bounded to observation while prerequisite evidence is incomplete.',
        sourceAuthorityReason: 'Research context stays consumer-safe and does not grant market conclusion authority.',
        freshnessReason: 'Candidate freshness is resolved by the research read model when evidence exists.',
        nextDiagnostic: 'Check scanner and watchlist prerequisites before expecting research evidence.',
        consumerSafeSummary: 'Research radar can explain available observations but prerequisite evidence is incomplete.',
      },
    ],
  },
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

const dataSourceGapRegistryPayload = {
  contractVersion: 'data_source_gap_registry_v1',
  diagnosticOnly: true,
  providerRuntimeCalled: false,
  networkCallsEnabled: false,
  scoreAuthorityAllowed: false,
  summary: {
    totalFamilies: 6,
    readyCount: 0,
    partialCount: 1,
    missingCount: 0,
    blockedCount: 2,
    unauthorizedCount: 1,
    staleCount: 0,
    observationOnlyCount: 1,
    plannedCount: 1,
    providerHydrationAllowedCount: 2,
    scoreTradingAuthorityAllowedCount: 0,
  },
  acquisitionPriorityQueue: [
    {
      familyKey: 'options_chains',
      familyLabel: 'Options Chains',
      priority: 'critical',
      priorityReason: '关键队列：影响 2 个产品面，1 项能力阻断或降级；当前行动为 确认期权链授权。',
      readinessState: 'unauthorized',
      primaryBlockerType: 'entitlement',
      affectedSurfaceCount: 2,
      blockedOrDegradedCapabilityCount: 1,
      externalEntitlementRequired: true,
      protectedDomainReviewRequired: true,
      nextConcreteStep: '收集授权与字段覆盖证据，不接入数据源运行链路。',
      requiredEvidence: ['授权证明', '字段覆盖清单'],
      consumerSafeWarning: '工程补数队列；当前不是决策级证据，不生成交易指令。',
    },
    {
      familyKey: 'stock_quote_spine',
      familyLabel: 'Stock Quote Spine',
      priority: 'high',
      priorityReason: '高优先级队列：影响 4 个产品面，3 项能力阻断或降级；当前行动为 补齐报价骨架集成。',
      readinessState: 'partial',
      primaryBlockerType: 'provider-integration',
      affectedSurfaceCount: 4,
      blockedOrDegradedCapabilityCount: 3,
      externalEntitlementRequired: false,
      protectedDomainReviewRequired: true,
      nextConcreteStep: '定义报价/OHLCV 快照读模型并补齐来源权限字段。',
      requiredEvidence: ['授权报价快照', '日线 as-of 血缘'],
      consumerSafeWarning: '工程补数队列；当前不是决策级证据，不生成交易指令。',
    },
    {
      familyKey: 'scenario_baselines',
      familyLabel: 'Scenario Baselines',
      priority: 'medium',
      priorityReason: '中优先级队列：影响 1 个产品面，0 项能力阻断或降级；当前行动为 补齐数据契约。',
      readinessState: 'planned',
      primaryBlockerType: 'schema-contract',
      affectedSurfaceCount: 1,
      blockedOrDegradedCapabilityCount: 0,
      externalEntitlementRequired: false,
      protectedDomainReviewRequired: true,
      nextConcreteStep: '存储 baseline snapshot IDs 并附输入 freshness/authority 摘要。',
      requiredEvidence: ['字段契约', '缺失状态定义'],
      consumerSafeWarning: '工程补数队列；当前不是决策级证据，不生成交易指令。',
    },
    {
      familyKey: 'macro_rates',
      familyLabel: 'Macro / Rates',
      priority: 'low',
      priorityReason: '低优先级监控：影响 1 个产品面，0 项能力阻断或降级；当前行动为 保持证据监控。',
      readinessState: 'observation-only',
      primaryBlockerType: 'unknown',
      affectedSurfaceCount: 1,
      blockedOrDegradedCapabilityCount: 0,
      externalEntitlementRequired: false,
      protectedDomainReviewRequired: false,
      nextConcreteStep: '持久化官方宏观序列并附覆盖和时效状态。',
      requiredEvidence: ['覆盖证据'],
      consumerSafeWarning: '工程补数队列；当前不是决策级证据，不生成交易指令。',
    },
  ],
  families: [
    {
      familyKey: 'stock_quote_spine',
      consumerLabel: 'Stock Quote Spine',
      status: 'partial',
      authorityState: 'blocked',
      freshnessState: 'delayed',
      entitlementOrLicensingBlocker: null,
      integrationBlocker: 'Durable quote/OHLCV snapshots and unified as-of lineage are still missing.',
      sourceEvidenceState: 'fragmented_runtime_evidence',
      nextIntegrationStep: 'Land bounded quote and OHLCV snapshot storage with authority metadata.',
      providerHydrationAllowed: true,
      scoreTradingAuthorityAllowed: false,
      consumerSafeDescription: 'Quote and OHLCV paths exist, but they are not yet a durable professional spine.',
      surfaceImpactMatrix: [
        {
          surfaceKey: 'watchlist',
          consumerLabel: 'Watchlist',
          impactState: 'degraded',
          impactReason: '保存标的不能从分散报价路径推断行级新鲜度。',
          affectedCapability: '行级价格、更新时间、研究状态',
          nextEvidenceStep: '让 watchlist row packet 引用明确的报价/日线快照 ID。',
        },
        {
          surfaceKey: 'stock_detail',
          consumerLabel: 'Stock Detail',
          impactState: 'degraded',
          impactReason: '个股研究包缺少统一报价、历史和 as-of 血缘。',
          affectedCapability: '个股价格、趋势、结构研究输入',
          nextEvidenceStep: '把报价、历史和证据引用合并为最小研究包。',
        },
        {
          surfaceKey: 'portfolio',
          consumerLabel: 'Portfolio',
          impactState: 'degraded',
          impactReason: '组合估值不能把价格来源、时效和 FX 血缘一起证明。',
          affectedCapability: '持仓估值可信度、P&L 读数说明',
          nextEvidenceStep: '接入价格和 FX lineage 后再提升估值置信说明。',
        },
        {
          surfaceKey: 'backtest_parameter_sweep',
          consumerLabel: 'Backtest / Parameter Sweep',
          impactState: 'observation-only',
          impactReason: '历史 bars 的来源、调整基准和可复现快照仍不完整。',
          affectedCapability: '研究级回测数据边界、参数扫读回边界',
          nextEvidenceStep: '补齐数据集 ID、调整基准、交易日历和缺失 bars 策略。',
        },
      ],
      integrationActionPlan: [
        {
          actionKey: 'stock_quote_spine.provider_integration',
          actionLabel: '补齐报价骨架集成',
          actionType: 'provider-integration',
          priority: 'high',
          status: 'ready-to-start',
          reason: '报价、日线和成交量血缘不统一。',
          requiredEvidence: ['授权报价快照', '日线 as-of 血缘'],
          blockedBy: ['持久化快照缺口'],
          affectedSurfacesOrCapabilities: ['Watchlist 行级价格', 'Portfolio 估值'],
          nextConcreteStep: '定义报价/OHLCV 快照读模型并补齐来源权限字段。',
          requiresExternalProviderLicenseWork: false,
          requiresProtectedDomainReview: true,
        },
        {
          actionKey: 'stock_quote_spine.evidence_validation',
          actionLabel: '验证报价血缘证据',
          actionType: 'evidence-validation',
          priority: 'high',
          status: 'waiting-evidence',
          reason: '需要证明来源权限、时效和覆盖范围。',
          requiredEvidence: ['覆盖率摘要', 'freshness evidence'],
          blockedBy: ['目标环境证据未齐'],
          affectedSurfacesOrCapabilities: ['Scanner 候选解释'],
          nextConcreteStep: '在目标环境采集脱敏覆盖和时效证据。',
          requiresExternalProviderLicenseWork: false,
          requiresProtectedDomainReview: true,
        },
      ],
    },
    {
      familyKey: 'macro_rates',
      consumerLabel: 'Macro / Rates',
      status: 'observation-only',
      authorityState: 'observation-only',
      freshnessState: 'cached',
      entitlementOrLicensingBlocker: null,
      integrationBlocker: 'Durable official macro rows are not yet surfaced as a complete product bundle.',
      sourceEvidenceState: 'diagnostic_contract',
      nextIntegrationStep: 'Persist official macro rows with freshness and coverage metadata.',
      providerHydrationAllowed: true,
      scoreTradingAuthorityAllowed: false,
      consumerSafeDescription: 'Macro and rates readiness is available only as a diagnostic contract today.',
      surfaceImpactMatrix: [
        {
          surfaceKey: 'market_overview',
          consumerLabel: 'Market Overview',
          impactState: 'observation-only',
          impactReason: '官方宏观行还不是完整产品数据包，风险读数只能保持边界说明。',
          affectedCapability: '利率压力、宏观风险摘要',
          nextEvidenceStep: '持久化官方宏观序列并附覆盖和时效状态。',
        },
      ],
    },
    {
      familyKey: 'options_chains',
      consumerLabel: 'Options Chains',
      status: 'unauthorized',
      authorityState: 'unauthorized',
      freshnessState: 'unavailable',
      entitlementOrLicensingBlocker: 'Options-chain rights and display rights are not proven.',
      integrationBlocker: 'No authorized live or delayed chain store is integrated.',
      sourceEvidenceState: 'rights_unproven',
      nextIntegrationStep: 'Attach an entitlement proof bundle before chain promotion.',
      providerHydrationAllowed: false,
      scoreTradingAuthorityAllowed: false,
      consumerSafeDescription: 'Options chains remain unavailable until authorized chain evidence exists.',
      surfaceImpactMatrix: [
        {
          surfaceKey: 'options_lab',
          consumerLabel: 'Options Lab',
          impactState: 'blocked',
          impactReason: '授权期权链、展示权、存储权和字段覆盖未证明。',
          affectedCapability: '链、IV、Greeks、OI、成交量观察',
          nextEvidenceStep: '先补齐权益证明包和字段覆盖证据。',
        },
        {
          surfaceKey: 'scenario_lab',
          consumerLabel: 'Scenario Lab',
          impactState: 'planned',
          impactReason: '期权链未授权时不得成为情景 baseline 输入。',
          affectedCapability: '期权敏感度情景输入',
          nextEvidenceStep: '保持缺失，直到授权链和方法证据齐备。',
        },
      ],
      integrationActionPlan: [
        {
          actionKey: 'options_chains.provider_entitlement',
          actionLabel: '确认期权链授权',
          actionType: 'provider-entitlement',
          priority: 'critical',
          status: 'waiting-entitlement',
          reason: '期权链访问、展示、存储和使用权尚未证明。',
          requiredEvidence: ['授权证明', '字段覆盖清单'],
          blockedBy: ['权益证明缺失'],
          affectedSurfacesOrCapabilities: ['Options Lab 链观察'],
          nextConcreteStep: '收集授权与字段覆盖证据，不接入数据源运行链路。',
          requiresExternalProviderLicenseWork: true,
          requiresProtectedDomainReview: true,
        },
      ],
    },
    {
      familyKey: 'options_strategy_analytics',
      consumerLabel: 'Options Strategy Analytics',
      status: 'blocked',
      authorityState: 'unauthorized',
      freshnessState: 'unavailable',
      entitlementOrLicensingBlocker: 'Authorized chain inputs and historical replay rights are not proven.',
      integrationBlocker: 'Strategy analytics cannot graduate before chain authority and history exist.',
      sourceEvidenceState: 'rights_unproven',
      nextIntegrationStep: 'Prove authorized chain, history, and methodology inputs first.',
      providerHydrationAllowed: false,
      scoreTradingAuthorityAllowed: false,
      consumerSafeDescription: 'Options strategy analytics remain blocked by missing authorized inputs.',
      surfaceImpactMatrix: [
        {
          surfaceKey: 'options_lab',
          consumerLabel: 'Options Lab',
          impactState: 'blocked',
          impactReason: '策略分析不能先于授权链、历史数据和方法输入毕业。',
          affectedCapability: '策略结构观察、历史回放边界',
          nextEvidenceStep: '先证明授权链、历史链和方法版本。',
        },
      ],
    },
    {
      familyKey: 'gamma_dealer_positioning',
      consumerLabel: 'Gamma / Dealer Positioning',
      status: 'blocked',
      authorityState: 'unauthorized',
      freshnessState: 'unavailable',
      entitlementOrLicensingBlocker: 'Options rights, methodology approval, and dealer positioning evidence are not proven.',
      integrationBlocker: 'No approved exposure methodology or rights-backed input set is integrated.',
      sourceEvidenceState: 'rights_unproven',
      nextIntegrationStep: 'Approve rights, inputs, and methodology before exposing gamma-family outputs.',
      providerHydrationAllowed: false,
      scoreTradingAuthorityAllowed: false,
      consumerSafeDescription: 'Gamma, GEX, vanna, charm, and dealer positioning remain blocked.',
      surfaceImpactMatrix: [
        {
          surfaceKey: 'options_lab',
          consumerLabel: 'Options Lab',
          impactState: 'blocked',
          impactReason: 'Gamma 家族和 dealer positioning 缺少授权输入、持仓假设和方法批准。',
          affectedCapability: 'Gamma/GEX/vanna/charm/dealer positioning 观察',
          nextEvidenceStep: '完成权利、字段覆盖、符号假设和方法版本评审。',
        },
        {
          surfaceKey: 'market_overview',
          consumerLabel: 'Market Overview',
          impactState: 'unknown',
          impactReason: '未证明的期权结构不能进入市场风险第一读。',
          affectedCapability: '期权结构风险背景',
          nextEvidenceStep: '在 Options Lab 方法通过前保持未知。',
        },
      ],
      integrationActionPlan: [
        {
          actionKey: 'gamma_dealer_positioning.provider_entitlement',
          actionLabel: '确认 Gamma 输入授权',
          actionType: 'provider-entitlement',
          priority: 'critical',
          status: 'waiting-entitlement',
          reason: '期权权利、方法批准和持仓证据尚未证明。',
          requiredEvidence: ['授权证明', '方法版本记录'],
          blockedBy: ['权益证明缺失', '方法评审未完成'],
          affectedSurfacesOrCapabilities: ['Options Lab Gamma 观察', 'Scenario Lab Gamma 驱动'],
          nextConcreteStep: '先完成授权、字段覆盖、符号假设和方法版本评审。',
          requiresExternalProviderLicenseWork: true,
          requiresProtectedDomainReview: true,
        },
      ],
    },
    {
      familyKey: 'scenario_baselines',
      consumerLabel: 'Scenario Baselines',
      status: 'planned',
      authorityState: 'planned',
      freshnessState: 'unknown',
      entitlementOrLicensingBlocker: null,
      integrationBlocker: 'Durable baseline snapshot storage is not yet integrated.',
      sourceEvidenceState: 'not_integrated',
      nextIntegrationStep: 'Store baseline snapshot IDs for market and portfolio scenario inputs.',
      providerHydrationAllowed: false,
      scoreTradingAuthorityAllowed: false,
      consumerSafeDescription: 'Scenario baselines are planned, but stored baseline inputs are not integrated.',
      surfaceImpactMatrix: [
        {
          surfaceKey: 'scenario_lab',
          consumerLabel: 'Scenario Lab',
          impactState: 'planned',
          impactReason: '存储化 baseline snapshot 尚未接入，常规路径仍偏 request/snapshot 驱动。',
          affectedCapability: '基线复现、市场/组合冲击输入',
          nextEvidenceStep: '存储 baseline snapshot IDs 并附输入 freshness/authority 摘要。',
        },
      ],
    },
  ],
  metadata: {
    requestId: 'req-secret',
    traceId: 'trace-secret',
    rawProviderPayloadsIncluded: false,
    cacheKey: 'internal-cache-key',
    credentialEnvName: 'SECRET_DATA_KEY',
    debugDump: { hidden: true },
  },
};

const professionalCapabilityAdminPayload = {
  contractVersion: 'professional_data_capability_registry_v1',
  consumerSafe: false,
  summary: {
    totalCapabilities: 2,
    liveCount: 0,
    degradedCount: 1,
    entitlementRequiredCount: 1,
    configuredMissingCount: 0,
    notImplementedCount: 0,
  },
  categories: ['options_structure', 'market_breadth_flows'],
  capabilities: [
    {
      capabilityId: 'options.chain',
      label: 'Options chain',
      category: 'options_structure',
      status: 'entitlement_required',
      sourceLabel: 'Options Lab readiness boundary',
      reason: 'Entitlement evidence is required.',
      freshness: 'Unavailable until rights are proven.',
    },
    {
      capabilityId: 'market.breadth_flows',
      label: 'Market breadth and flows',
      category: 'market_breadth_flows',
      status: 'degraded',
      sourceLabel: 'Market readiness registry',
      reason: 'Source authority remains incomplete.',
      freshness: 'Partial and delayed.',
    },
  ],
};

const historicalOhlcvCachePreflightPayload = {
  contractVersion: 'historical_ohlcv_cache_preflight_v1',
  mode: 'preflight',
  dryRun: true,
  seedEnabled: false,
  networkCallsEnabled: false,
  mutationEnabled: false,
  consumerSafe: true,
  representativeSymbols: {
    cn: ['600519'],
    us: ['ORCL', 'AAPL', 'NVDA'],
  },
  activationChecklist: {
    contractVersion: 'historical_ohlcv_data_activation_checklist_v1',
    operatorOnly: true,
    readOnly: true,
    noExternalCalls: true,
    consumerVisible: false,
    supportedStates: [
      'disabled_by_config',
      'dependency_missing',
      'ready_to_seed',
      'seeded/cache_hit',
      'failed_safely',
    ],
    starterSymbolSets: {
      us: {
        label: 'US first cache activation set',
        symbols: ['ORCL', 'AAPL', 'NVDA'],
        supported: true,
      },
      cnIfSupported: {
        label: 'CN first cache activation set if the local CN runtime is supported',
        symbols: ['600519', '000001', '601398'],
        supported: true,
      },
    },
    workflowUnlocks: ['Stock', 'Scanner', 'Backtest', 'Technical Indicators', 'Market Regime'],
    items: [
      {
        market: 'cn',
        label: 'CN activation checklist',
        state: 'disabled_by_config',
        runtimeEnabled: false,
        dependencyAvailable: true,
        seedEnabled: false,
        requiredRuntimeFlags: ['WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED'],
        seedFlag: 'WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED',
        currentRepresentativeSymbols: ['600519'],
        recommendedFirstSymbols: ['600519', '000001', '601398'],
        disabledReasonCodes: ['runtime_flags_off', 'seed_flag_off_by_default'],
        cacheSummary: {
          totalSymbols: 1,
          cachedSymbolCount: 1,
          readySymbolCount: 1,
          staleSymbolCount: 0,
          missingAdjustmentCount: 0,
          failedSafelyCount: 0,
        },
        availableSeedActions: [
          'Enable the documented runtime flags first; keep providers default-off until operator approval.',
          'The seed flag remains default-off until an operator explicitly enables it.',
        ],
        workflowUnlocks: ['Stock', 'Scanner', 'Backtest', 'Technical Indicators', 'Market Regime'],
        currentStatusSummary: 'CN starter symbols remain intentionally disabled by runtime config.',
        nextStepSummary: 'Turn on the CN runtime flags, reload the checklist, and confirm cache readiness before any seed.',
      },
      {
        market: 'us',
        label: 'US activation checklist',
        state: 'ready_to_seed',
        runtimeEnabled: true,
        dependencyAvailable: true,
        seedEnabled: false,
        requiredRuntimeFlags: [
          'WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED',
          'WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED',
        ],
        seedFlag: 'WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED',
        currentRepresentativeSymbols: ['ORCL', 'AAPL', 'NVDA'],
        recommendedFirstSymbols: ['ORCL', 'AAPL', 'NVDA'],
        disabledReasonCodes: ['seed_flag_off_by_default', 'representative_cache_missing', 'adjustments_missing_for_some_symbols'],
        cacheSummary: {
          totalSymbols: 3,
          cachedSymbolCount: 1,
          readySymbolCount: 0,
          staleSymbolCount: 1,
          missingAdjustmentCount: 1,
          failedSafelyCount: 0,
        },
        availableSeedActions: [
          'Review representative dry-run readiness before enabling any mutation.',
          'Run the explicit seed flow in dry-run mode first, then enable the seed flag only after approval.',
          'The seed flag remains default-off until an operator explicitly enables it.',
        ],
        workflowUnlocks: ['Stock', 'Scanner', 'Backtest', 'Technical Indicators', 'Market Regime'],
        currentStatusSummary: 'US starter symbols are ready for an explicit admin seed review.',
        nextStepSummary: 'Use the documented starter symbols first, keep the seed flag explicit, and verify the unlocked product surfaces stay bounded.',
      },
    ],
  },
  markets: {
    cn: {
      market: 'cn',
      runtimeEnabled: false,
      dependencyAvailable: true,
      symbols: [
        {
          market: 'cn',
          symbol: '600519',
          runtimeState: 'disabled_by_config',
          cacheState: 'cache_hit',
          dependencyState: 'installed',
          dependencyAvailable: true,
          cachedBars: 72,
          latestBarDate: '2026-06-23',
          freshnessState: 'fresh',
          adjustmentState: 'available',
          dataState: 'fresh',
          seedState: 'seed_skipped',
          nextAction: {
            state: 'seeded/cache_hit',
            summary: 'Enable runtime before provider fetch is allowed.',
            requiredConfig: 'WOLFYSTOCK_AKSHARE_CN_OHLCV_CACHE_ENABLED=true',
          },
        },
      ],
    },
    us: {
      market: 'us',
      runtimeEnabled: true,
      dependencyAvailable: false,
      symbols: [
        {
          market: 'us',
          symbol: 'ORCL',
          runtimeState: 'dependency_missing',
          cacheState: 'cache_missing',
          dependencyState: 'missing',
          dependencyAvailable: false,
          cachedBars: 0,
          latestBarDate: null,
          freshnessState: 'unknown',
          adjustmentState: 'unknown',
          dataState: 'dependency_missing',
          seedState: 'seed_skipped',
          nextAction: {
            state: 'dependency_missing',
            summary: 'Install yfinance before provider fetch is allowed.',
          },
        },
        {
          market: 'us',
          symbol: 'AAPL',
          runtimeState: 'available',
          cacheState: 'cache_hit',
          dependencyState: 'installed',
          dependencyAvailable: true,
          cachedBars: 44,
          latestBarDate: '2026-06-20',
          freshnessState: 'stale',
          adjustmentState: 'missing',
          dataState: 'missing_adjustments',
          seedState: 'seed_skipped',
          nextAction: {
            state: 'seeded/cache_hit',
            summary: 'Representative cache is already present; validate bars, freshness, and adjustments before widening coverage.',
          },
        },
      ],
    },
  },
};

describe('MarketProviderOperationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, '', '/zh/admin/market-providers');
    getDataReadiness.mockResolvedValue(readinessPayload);
    getOperationsMatrix.mockResolvedValue(operationsMatrixPayload);
    getHistoricalOhlcvCachePreflight.mockResolvedValue(historicalOhlcvCachePreflightPayload);
    getDataSourceGapRegistry.mockResolvedValue(dataSourceGapRegistryPayload);
    getProfessionalDataCapabilitiesAdmin.mockResolvedValue(professionalCapabilityAdminPayload);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the loading state before the read-only operations payload resolves', async () => {
    getOperations.mockReturnValue(new Promise(() => {}));

    render(<MarketProviderOperationsPage />);

    expect(document.title).toBe('数据源运维 - WolfyStock');
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

  it('keeps page-level overflow hidden while exposing a contained mobile matrix scroll affordance', async () => {
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    const pageRoot = await screen.findByTestId('market-provider-operations-page');
    expect(pageRoot).toHaveClass('min-w-0', 'overflow-x-hidden');

    const matrixDisclosure = screen.getByTestId('market-provider-matrix-disclosure');
    fireEvent.click(within(matrixDisclosure).getByRole('button', { name: '展开 L4 完整数据源矩阵：来源 / 就绪 / 门槛 / 原因代码（已脱敏）' }));

    expect(within(matrixDisclosure).getByText('左右滑动查看完整矩阵列')).toBeInTheDocument();
    expect(within(matrixDisclosure).getByText('滚动仅限表格区域')).toBeInTheDocument();
    expect(screen.getByTestId('market-provider-matrix-table-shell')).toHaveClass(
      '-mx-4',
      'px-4',
      'overflow-x-auto',
      'overscroll-x-contain',
      'sm:mx-0',
      'sm:px-0',
    );
  });

  it('renders Chinese-first operator hierarchy and keeps diagnostics available without exposing raw secrets or backend credential names', async () => {
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    const overviewStrip = await screen.findByTestId('market-provider-l0-overview-strip');
    expect(screen.getByTestId('market-provider-section-ops-status')).toHaveClass(
      '[&_[data-terminal-primitive=section-header]_h2]:text-lg',
      'md:[&_[data-terminal-primitive=section-header]_h2]:text-xl',
    );
    expect(screen.getByTestId('market-provider-section-matrix')).toHaveClass(
      '[&_[data-terminal-primitive=section-header]_h2]:text-lg',
      'md:[&_[data-terminal-primitive=section-header]_h2]:text-xl',
    );
    expect(within(overviewStrip).getByText('信任状态')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('影响范围')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('建议动作')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('证据参考')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('最近更新')).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: '数据源维护路线图' })).toBeInTheDocument();
    expect(screen.getAllByText('数据源健康').length).toBeGreaterThan(0);
    expect(screen.getAllByText('熔断状态').length).toBeGreaterThan(0);
    expect(screen.getAllByText('失败率').length).toBeGreaterThan(0);
    expect(screen.getAllByText('缓存状态').length).toBeGreaterThan(0);
    expect(screen.getAllByText('最近异常').length).toBeGreaterThan(0);
    expect(screen.getAllByText('新浪财经').length).toBeGreaterThan(0);
    expect(screen.getByText('只读')).toBeInTheDocument();
    expect(screen.getByText('外部调用关闭')).toBeInTheDocument();
    expect(screen.getByText('缓存不变更')).toBeInTheDocument();
    const topSummary = screen.getByTestId('market-provider-readability-summary');
    expect(topSummary).toHaveTextContent('首屏摘要');
    expect(topSummary).toHaveTextContent('数据源可用');
    expect(topSummary).toHaveTextContent('需补齐');
    expect(topSummary).toHaveTextContent('仅诊断/观察');
    expect(topSummary).toHaveTextContent('影响产品页');
    expect(topSummary).toHaveTextContent('新浪财经');
    expect(topSummary).toHaveTextContent('Tushare Pro');
    expect(topSummary).toHaveTextContent('Market Overview');
    expect(topSummary).not.toHaveTextContent('official_public.fed_liquidity');
    expect(topSummary).not.toHaveTextContent('missing_provider_configuration');
    expect(topSummary).not.toHaveTextContent('TUSHARE_TOKEN');
    const betaChecklist = screen.getByTestId('market-provider-beta-readiness-checklist');
    expect(betaChecklist).toHaveTextContent('数据源配置');
    expect(betaChecklist).toHaveTextContent('本地样本与缓存');
    expect(betaChecklist).toHaveTextContent('降级 / 备用观察');
    expect(betaChecklist).toHaveTextContent('仅观察来源');
    expect(betaChecklist).toHaveTextContent('备用 2');
    expect(betaChecklist).toHaveTextContent('过期 0');
    expect(betaChecklist).toHaveTextContent('部分 0');
    expect(betaChecklist).toHaveTextContent('失败 1');
    expect(betaChecklist).toHaveTextContent('需补齐 5 项');
    expect(betaChecklist).toHaveTextContent('就绪状态 部分就绪');
    expect(betaChecklist).toHaveTextContent('先沿现有凭据、授权 feed、缓存与 provider 配置路径补齐，再回本页确认。');
    const actionQueue = screen.getByTestId('market-provider-action-queue');
    expect(actionQueue).toHaveTextContent('L1 行动队列');
    expect(actionQueue).toHaveTextContent('优先处理少量阻断和注意项');
    expect(actionQueue).toHaveTextContent('Fed Liquidity 需要运维确认');
    expect(actionQueue).toHaveTextContent('影响：Market Overview、Liquidity Monitor');
    expect(actionQueue).toHaveTextContent('补齐既有数据源运行配置');
    expect(actionQueue).not.toHaveTextContent('official_public.fed_liquidity');
    expect(actionQueue).not.toHaveTextContent('missing_provider_configuration');
    expect(actionQueue).not.toHaveTextContent('cache_required');
    expect(actionQueue).not.toHaveTextContent('TUSHARE_TOKEN');
    const roadmap = screen.getByTestId('admin-data-roadmap-panel');
    expect(roadmap).toHaveTextContent('专业数据能力路线图');
    expect(roadmap).toHaveTextContent('Stock research');
    expect(roadmap).toHaveTextContent('Market overview/regime');
    expect(roadmap).toHaveTextContent('Scanner/backtest');
    expect(roadmap).toHaveTextContent('Research Radar');
    expect(roadmap).toHaveTextContent('Portfolio risk');
    expect(roadmap).toHaveTextContent('Admin/operator readiness');
    expect(roadmap).toHaveTextContent('Options chain');
    expect(roadmap).toHaveTextContent('Missing entitlement');
    expect(roadmap).toHaveTextContent('fed liquidity');
    expect(roadmap).toHaveTextContent('Missing / needs configuration');
    expect(roadmap).toHaveTextContent('cache evidence required');
    expect(roadmap).toHaveTextContent('US / yfinance historical OHLCV');
    expect(roadmap).toHaveTextContent('ready 0/3 · stale 1 · adjustments missing 1');
    expect(roadmap).toHaveTextContent('research prerequisites');
    expect(roadmap).toHaveTextContent('Portfolio');
    expect(roadmap).toHaveTextContent('Provider operations snapshot');
    expect(roadmap).toHaveTextContent('No live calls or cache mutation');
    expect(roadmap).not.toHaveTextContent('TUSHARE_TOKEN');
    expect(roadmap).not.toHaveTextContent('super-secret-token');
    expect(roadmap).not.toHaveTextContent('SECRET');
    expect(roadmap).not.toHaveTextContent('https://');
    expect(roadmap).not.toHaveTextContent('/var/tmp/provider');
    expect(roadmap).not.toHaveTextContent('/Users/example/provider');
    expect(roadmap).not.toHaveTextContent('req-secret');
    expect(roadmap).not.toHaveTextContent('trace-secret');
    expect(roadmap).not.toHaveTextContent('internal-cache-key');
    expect(roadmap).not.toHaveTextContent('rawProviderPayload');
    const pageRoot = screen.getByTestId('market-provider-operations-page');
    expect(pageRoot).not.toHaveTextContent('Provider Setup Checklist');
    expect(pageRoot).not.toHaveTextContent('Why it matters');
    expect(pageRoot).not.toHaveTextContent('Safe next step');
    expect(pageRoot).not.toHaveTextContent('setup items');
    expect(pageRoot).not.toHaveTextContent('Provider Ops / system diagnostics');
    expect(pageRoot).not.toHaveTextContent('provider runtime');
    expect(screen.getByText('本地行情就绪诊断')).toBeInTheDocument();
    expect(screen.getAllByText('只读诊断').length).toBeGreaterThan(0);
    expect(screen.getByText('运行时调用')).toBeInTheDocument();
    expect(screen.getByText('网络调用')).toBeInTheDocument();
    expect(screen.getByText('未配置')).toBeInTheDocument();
    expect(screen.getAllByText('AAPL').length).toBeGreaterThan(0);
    expect(screen.getByText('BTC-USD')).toBeInTheDocument();
    expect(screen.getByText('凭据配置')).toBeInTheDocument();
    expect(screen.getByText('本地缓存/历史文件')).toBeInTheDocument();
    expect(screen.getAllByText('Tushare 覆盖凭据').length).toBeGreaterThan(0);
    expect(screen.getByText('Tushare 覆盖凭据未配置，相关 CN/HK 市场上下文只能保持缺口提示。')).toBeInTheDocument();
    expect(screen.getByText('部分代表样本缺少本地历史缓存，离线覆盖检查只能显示部分就绪。')).toBeInTheDocument();
    expect(screen.queryByText('Tushare token is not configured.')).not.toBeInTheDocument();
    expect(screen.queryByText('Set TUSHARE_TOKEN when local operators need Tushare-backed CN/HK market intelligence inputs.')).not.toBeInTheDocument();
    expect(screen.getAllByText('配额 / 成本线索与下钻').length).toBeGreaterThan(0);
    expect(screen.getByText('数据源就绪与运维状态')).toBeInTheDocument();
    expect(screen.getByText('来源缺口、配置清单与完整矩阵')).toBeInTheDocument();
    expect(screen.getByText('本地数据就绪与样本诊断')).toBeInTheDocument();
    const sourceGapDisclosure = screen.getByTestId('market-provider-source-gap-disclosure');
    expect(sourceGapDisclosure).toHaveAttribute('data-open', 'false');
    expect(within(sourceGapDisclosure).getByRole('button', { name: '展开 L2 来源缺口：影响产品面 / 解锁能力 / 下一步' })).toBeInTheDocument();
    expect(screen.queryByTestId('market-provider-source-gap-board')).not.toBeInTheDocument();
    expect(sourceGapDisclosure).not.toHaveTextContent('P0 市场方向判断');
    expect(sourceGapDisclosure).not.toHaveTextContent('当前为什么不可用');
    fireEvent.click(within(sourceGapDisclosure).getByRole('button', { name: '展开 L2 来源缺口：影响产品面 / 解锁能力 / 下一步' }));
    expect(sourceGapDisclosure).toHaveAttribute('data-open', 'true');
    const gapBoard = screen.getByTestId('market-provider-source-gap-board');
    expect(gapBoard).toHaveTextContent('优先级路线图');
    expect(gapBoard).toHaveTextContent('P0 市场方向判断');
    expect(gapBoard).toHaveTextContent('P1 流动性方向');
    expect(gapBoard).toHaveTextContent('P3 区域 / 期货确认');
    expect(gapBoard).toHaveTextContent('Fed Liquidity');
    expect(gapBoard).toHaveTextContent('Polygon grouped daily US equities');
    expect(gapBoard).toHaveTextContent('仅涨跌家数');
    expect(gapBoard).toHaveTextContent('高低点缺失');
    expect(gapBoard).not.toHaveTextContent('NYSE');
    expect(gapBoard).not.toHaveTextContent('Nasdaq');
    expect(gapBoard).toHaveTextContent('当前为什么不可用');
    expect(gapBoard).toHaveTextContent('解锁能力');
    expect(gapBoard).toHaveTextContent('所需工作');
    expect(gapBoard).toHaveTextContent('阻断评分级结论：是');
    expect(gapBoard).not.toHaveTextContent('missing_provider_configuration');
    expect(within(sourceGapDisclosure).getByRole('button', { name: '收起 L2 来源缺口：影响产品面 / 解锁能力 / 下一步' })).toBeInTheDocument();
    expect(screen.queryByText('official_public.fed_liquidity')).not.toBeInTheDocument();
    expect(screen.getAllByText('缓存状态').length).toBeGreaterThan(0);
    expect(screen.getAllByText('最近异常').length).toBeGreaterThan(0);
    expect(screen.getAllByText('查看 Admin Logs').length).toBeGreaterThan(0);
    expect(screen.getAllByText('熔断状态').length).toBeGreaterThan(0);
    expect(screen.getAllByText('已脱敏').length).toBeGreaterThan(0);
    const dataMap = screen.getByTestId('data-source-gap-registry-panel');
    expect(dataMap).toHaveTextContent('专业数据地图');
    expect(dataMap).toHaveTextContent('报价 / 市场骨架');
    expect(dataMap).toHaveTextContent('期权与衍生结构');
    expect(dataMap).toHaveTextContent('宏观 / 流动性 / 信用');
    expect(dataMap).toHaveTextContent('情景基线');
    expect(dataMap).toHaveTextContent('股票报价骨架');
    expect(dataMap).toHaveTextContent('期权链');
    expect(dataMap).toHaveTextContent('Gamma / Dealer Positioning');
    expect(dataMap).toHaveTextContent('部分可用');
    expect(dataMap).toHaveTextContent('未授权');
    expect(dataMap).toHaveTextContent('阻断');
    expect(dataMap).toHaveTextContent('仅观察');
    expect(dataMap).toHaveTextContent('计划中');
    const capabilityAdminPanel = await screen.findByTestId('professional-capability-admin-summary-panel');
    expect(capabilityAdminPanel).toHaveTextContent('专业数据能力诊断摘要');
    expect(capabilityAdminPanel).toHaveTextContent('Options chain');
    expect(capabilityAdminPanel).toHaveTextContent('Market breadth and flows');
    expect(capabilityAdminPanel).toHaveTextContent('需授权');
    expect(capabilityAdminPanel.textContent || '').not.toMatch(
      /providerClass|providerName|providerAttempted|requiredProviderClass|sourceAuthorityRouter|endpointHost|apiKeyPresent|exceptionClass|exceptionChain|requestId|traceId|cacheKey|rawPayload|credential|token|env/i,
    );
    const quoteDrilldown = screen.getByTestId('data-source-gap-registry-row-stock_quote_spine');
    fireEvent.click(within(quoteDrilldown).getByRole('button', { name: '展开 股票报价骨架' }));
    expect(dataMap).toHaveTextContent('计分/交易权限 不允许');
    expect(quoteDrilldown).toHaveTextContent('stock_quote_spine');
    expect(quoteDrilldown).toHaveTextContent('消费者标签');
    expect(quoteDrilldown).toHaveTextContent('Provider hydration');
    expect(quoteDrilldown).toHaveTextContent('Score / trading authority');
    const quoteImpactMatrix = screen.getByTestId('data-source-gap-registry-impact-matrix-stock_quote_spine');
    expect(quoteImpactMatrix).toHaveTextContent('影响产品面与研究能力');
    expect(quoteImpactMatrix).toHaveTextContent('4 个影响项');
    expect(quoteImpactMatrix).toHaveTextContent('Watchlist');
    expect(quoteImpactMatrix).toHaveTextContent('Stock Detail');
    expect(quoteImpactMatrix).toHaveTextContent('Portfolio');
    expect(quoteImpactMatrix).toHaveTextContent('回测 / 参数扫描');
    expect(quoteImpactMatrix).toHaveTextContent('降级');
    expect(quoteImpactMatrix).toHaveTextContent('仅观察');
    expect(quoteImpactMatrix).toHaveTextContent('行级价格、更新时间、研究状态');
    expect(quoteImpactMatrix).toHaveTextContent('组合估值不能把价格来源、时效和 FX 血缘一起证明。');
    expect(quoteImpactMatrix).toHaveTextContent('补齐数据集 ID、调整基准、交易日历和缺失 bars 策略。');
    const quoteActionPlan = screen.getByTestId('data-source-gap-registry-action-plan-stock_quote_spine');
    expect(quoteActionPlan).toHaveTextContent('行动计划');
    expect(quoteActionPlan).toHaveTextContent('补齐报价骨架集成');
    expect(quoteActionPlan).toHaveTextContent('高');
    expect(quoteActionPlan).toHaveTextContent('Provider integration');
    expect(quoteActionPlan).toHaveTextContent('可开始');
    expect(quoteActionPlan).toHaveTextContent('授权报价快照');
    expect(quoteActionPlan).toHaveTextContent('日线 as-of 血缘');
    expect(quoteActionPlan).toHaveTextContent('持久化快照缺口');
    expect(quoteActionPlan).toHaveTextContent('Watchlist 行级价格');
    expect(quoteActionPlan).toHaveTextContent('定义报价/OHLCV 快照读模型并补齐来源权限字段。');
    expect(quoteActionPlan).toHaveTextContent('保护域复核');
    expect(dataMap).not.toHaveTextContent('OPRA');
    expect(dataMap).not.toHaveTextContent('requestId');
    expect(dataMap).not.toHaveTextContent('traceId');
    expect(dataMap).not.toHaveTextContent('rawProviderPayloadsIncluded');
    expect(dataMap).not.toHaveTextContent('internal-cache-key');
    expect(dataMap).not.toHaveTextContent('SECRET_DATA_KEY');
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
    const disclosureToggle = screen.getByRole('button', { name: '展开 L4 已脱敏细节：限制代码 / 快照摘要 / 追踪标识' });
    expect(disclosureToggle).toBeInTheDocument();
    expect(diagnosticsDisclosure).not.toHaveAttribute('open');
    fireEvent.click(disclosureToggle);
    expect(diagnosticsDisclosure).toHaveAttribute('open');
    expect(screen.getByRole('button', { name: '收起 L4 已脱敏细节：限制代码 / 快照摘要 / 追踪标识' })).toBeInTheDocument();
    expect(screen.getByText('cache_metadata_unavailable:rates')).toBeVisible();

    const matrixDisclosure = screen.getByTestId('market-provider-matrix-disclosure');
    expect(matrixDisclosure).not.toHaveAttribute('open');
    fireEvent.click(within(matrixDisclosure).getByRole('button', { name: '展开 L4 完整数据源矩阵：来源 / 就绪 / 门槛 / 原因代码（已脱敏）' }));
    expect(matrixDisclosure).toHaveTextContent('数据源');
    expect(matrixDisclosure).toHaveTextContent('来源');
    expect(matrixDisclosure).toHaveTextContent('就绪状态');
    expect(matrixDisclosure).toHaveTextContent('门槛');
    expect(matrixDisclosure).toHaveTextContent('原因代码');
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

  it('renders historicalOhlcvCachePreflight for representative CN and US symbols without enabling seed by default', async () => {
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    const panel = await screen.findByTestId('historical-ohlcv-cache-preflight-panel');
    const checklist = screen.getByTestId('historical-ohlcv-activation-checklist');
    expect(getHistoricalOhlcvCachePreflight).toHaveBeenCalledWith();
    expect(panel).toHaveTextContent('历史行情缓存激活清单');
    expect(panel).toHaveTextContent('operator checklist');
    expect(panel).toHaveTextContent('consumer 页面不会显示这些 provider/ops 内部说明');
    expect(panel).toHaveTextContent('dry-run');
    expect(panel).toHaveTextContent('seed 默认关闭');
    expect(panel).toHaveTextContent('不触发写入');
    expect(within(panel).getByRole('button', { name: '历史缓存 seed 当前禁用' })).toBeDisabled();
    expect(panel).toHaveTextContent('CN 1 · US 3');
    expect(panel).toHaveTextContent('2 / 3');
    expect(panel).toHaveTextContent('缺少复权');
    expect(panel).toHaveTextContent('CN / AkShare');
    expect(panel).toHaveTextContent('US / yfinance');
    expect(panel).toHaveTextContent('运行时默认关闭');
    expect(panel).toHaveTextContent('运行时开启');
    expect(panel).toHaveTextContent('依赖可用');
    expect(panel).toHaveTextContent('依赖缺失');
    expect(panel).toHaveTextContent('600519');
    expect(panel).toHaveTextContent('ORCL');
    expect(panel).toHaveTextContent('AAPL');
    expect(checklist).toHaveTextContent('US: ORCL / AAPL / NVDA');
    expect(checklist).toHaveTextContent('CN if supported: 600519 / 000001 / 601398');
    expect(checklist).toHaveTextContent('disabled_by_config');
    expect(checklist).toHaveTextContent('ready_to_seed');
    expect(checklist).toHaveTextContent('Stock');
    expect(checklist).toHaveTextContent('Scanner');
    expect(checklist).toHaveTextContent('Backtest');
    expect(checklist).toHaveTextContent('Technical Indicators');
    expect(checklist).toHaveTextContent('Market Regime');
    expect(checklist).toHaveTextContent('WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED');
    expect(checklist).toHaveTextContent('WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED');
    expect(checklist).toHaveTextContent('WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED');
    expect(panel).toHaveTextContent('命中');
    expect(panel).toHaveTextContent('未命中');
    expect(panel).toHaveTextContent('72');
    expect(panel).toHaveTextContent('44');
    expect(panel).toHaveTextContent('新鲜 · 2026-06-23');
    expect(panel).toHaveTextContent('过期 · 2026-06-20');
    expect(panel).toHaveTextContent('复权缺失');
    expect(panel).toHaveTextContent('seeded/cache_hit');
    expect(panel).toHaveTextContent('dependency_missing');
    expect(panel).toHaveTextContent('缓存存在但缺少复权字段');
    expect(panel.textContent || '').not.toMatch(
      /requestId|traceId|cacheKey|rawProviderPayload|providerClass|api[_-]?key|token|secret|stack/i,
    );
  });

  it('renders the backend data source gap registry as a fail-closed professional data map', async () => {
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    const panel = await screen.findByTestId('data-source-gap-registry-panel');
    expect(panel).toHaveTextContent('专业数据地图');
    expect(panel).toHaveTextContent('只消费后端数据源缺口登记表');
    expect(panel).toHaveTextContent('未触发数据运行');
    expect(panel).toHaveTextContent('网络调用关闭');
    expect(panel).toHaveTextContent('不授予计分权限');
    expect(panel).toHaveTextContent('0');
    expect(panel).toHaveTextContent('1');
    expect(panel).toHaveTextContent('2');
    expect(panel).toHaveTextContent('已就绪');
    expect(panel).toHaveTextContent('部分可用');
    expect(panel).toHaveTextContent('未授权');
    expect(panel).toHaveTextContent('阻断');
    expect(panel).toHaveTextContent('仅观察');
    expect(panel).toHaveTextContent('计划中');
    expect(panel).toHaveTextContent('数据接入优先队列');
    expect(screen.getByTestId('data-source-acquisition-priority-queue')).toHaveTextContent('工程补数排序');
    expect(screen.getByTestId('data-source-acquisition-priority-options_chains')).toHaveTextContent('关键');
    expect(screen.getByTestId('data-source-acquisition-priority-stock_quote_spine')).toHaveTextContent('高');
    expect(screen.getByTestId('data-source-acquisition-priority-scenario_baselines')).toHaveTextContent('中');
    expect(screen.getByTestId('data-source-acquisition-priority-macro_rates')).toHaveTextContent('低');
    expect(screen.getByTestId('data-source-acquisition-priority-options_chains')).toHaveTextContent('授权阻断');
    expect(screen.getByTestId('data-source-acquisition-priority-stock_quote_spine')).toHaveTextContent('数据接入');
    expect(screen.getByTestId('data-source-acquisition-priority-scenario_baselines')).toHaveTextContent('契约补齐');
    expect(screen.getByTestId('data-source-acquisition-priority-macro_rates')).toHaveTextContent('阻断待确认');
    expect(screen.getByTestId('data-source-acquisition-priority-options_chains')).toHaveTextContent('影响面 2');
    expect(screen.getByTestId('data-source-acquisition-priority-stock_quote_spine')).toHaveTextContent('阻断/降级能力 3');
    expect(screen.getByTestId('data-source-acquisition-priority-scenario_baselines')).toHaveTextContent('所需证据');
    expect(screen.getByTestId('data-source-acquisition-priority-macro_rates')).toHaveTextContent('当前不是决策级证据，不生成交易指令');
    const workbench = screen.getByTestId('data-source-acquisition-workbench');
    expect(workbench).toHaveTextContent('接入执行工作台');
    expect(workbench).toHaveTextContent('阻断/缺失/部分家族');
    expect(workbench).toHaveTextContent('待处理队列');
    expect(workbench).toHaveTextContent('未知/待补证字段');
    expect(workbench).toHaveTextContent('授权阻断 1');
    expect(workbench).toHaveTextContent('数据接入 1');
    expect(workbench).toHaveTextContent('契约补齐 1');
    expect(workbench).toHaveTextContent('阻断待确认 1');
    expect(workbench).toHaveTextContent('关键 1');
    expect(workbench).toHaveTextContent('高 1');
    expect(workbench).toHaveTextContent('中 1');
    expect(workbench).toHaveTextContent('低 1');
    expect(workbench).toHaveTextContent('非决策级队列');
    const topActions = screen.getByTestId('data-source-acquisition-workbench-top-actions');
    expect(topActions).toHaveTextContent('前三项下一步');
    expect(topActions.textContent?.indexOf('期权链')).toBeLessThan(topActions.textContent?.indexOf('股票报价骨架') || 0);
    expect(topActions.textContent?.indexOf('股票报价骨架')).toBeLessThan(topActions.textContent?.indexOf('情景基线') || 0);
    expect(topActions).toHaveTextContent('收集授权与字段覆盖证据，不接入数据源运行链路。');
    expect(topActions).toHaveTextContent('定义报价/OHLCV 快照读模型并补齐来源权限字段。');
    expect(topActions).toHaveTextContent('存储 baseline snapshot IDs 并附输入 freshness/authority 摘要。');
    expect(screen.getByTestId('data-source-acquisition-workbench-lane-protected-review')).toHaveTextContent('保护域复核');
    expect(screen.getByTestId('data-source-acquisition-workbench-lane-protected-review')).toHaveTextContent('期权链');
    expect(screen.getByTestId('data-source-acquisition-workbench-lane-protected-review')).toHaveTextContent('股票报价骨架');
    expect(screen.getByTestId('data-source-acquisition-workbench-lane-external-entitlement')).toHaveTextContent('外部授权');
    expect(screen.getByTestId('data-source-acquisition-workbench-lane-external-entitlement')).toHaveTextContent('期权链');
    expect(screen.getByTestId('data-source-acquisition-workbench-lane-evidence-validation')).toHaveTextContent('证据验证');
    expect(screen.getByTestId('data-source-acquisition-workbench-lane-evidence-validation')).toHaveTextContent('股票报价骨架');
    expect(workbench.textContent || '').not.toMatch(/requestId|traceId|rawProviderPayload|cacheKey|credential|env|debug|api[_-]?key|buy|sell|hold|target price|stop loss|position sizing|买入|卖出|持有|目标价|止损|仓位|推荐|最佳|最优|赢家/i);
    expect(screen.getByTestId('data-source-gap-registry-group-quote_market')).toHaveTextContent('报价 / 市场骨架');
    expect(screen.getByTestId('data-source-gap-registry-group-options')).toHaveTextContent('期权与衍生结构');
    expect(screen.getByTestId('data-source-gap-registry-group-macro_liquidity_credit')).toHaveTextContent('宏观 / 流动性 / 信用');
    expect(screen.getByTestId('data-source-gap-registry-group-scenario')).toHaveTextContent('情景基线');

    const quoteRow = screen.getByTestId('data-source-gap-registry-row-stock_quote_spine');
    fireEvent.click(within(quoteRow).getByRole('button', { name: '展开 股票报价骨架' }));
    expect(quoteRow).toHaveTextContent('股票报价骨架');
    expect(quoteRow).toHaveTextContent('stock_quote_spine');
    expect(quoteRow).toHaveTextContent('部分可用');
    expect(quoteRow).toHaveTextContent('权限 阻断');
    expect(quoteRow).toHaveTextContent('时效 延迟');
    expect(quoteRow).toHaveTextContent('补数权限 允许');
    expect(quoteRow).toHaveTextContent('计分/交易权限 不允许');
    expect(quoteRow).toHaveTextContent('落地报价与日线快照');
    const quotePermissions = screen.getByTestId('data-source-gap-registry-permissions-stock_quote_spine');
    expect(quotePermissions).toHaveTextContent('Provider hydration');
    expect(quotePermissions).toHaveTextContent('Score / trading authority');

    const optionsRow = screen.getByTestId('data-source-gap-registry-row-options_chains');
    fireEvent.click(within(optionsRow).getByRole('button', { name: '展开 期权链' }));
    expect(optionsRow).toHaveTextContent('期权链');
    expect(optionsRow).toHaveTextContent('未授权');
    expect(optionsRow).toHaveTextContent('权限 未授权');
    expect(optionsRow).toHaveTextContent('时效 不可用');
    expect(optionsRow).toHaveTextContent('补数权限 不允许');
    expect(optionsRow).toHaveTextContent('计分/交易权限 不允许');
    expect(optionsRow).not.toHaveTextContent('已就绪');
    const optionsImpactMatrix = screen.getByTestId('data-source-gap-registry-impact-matrix-options_chains');
    expect(optionsImpactMatrix).toHaveTextContent('Options Lab');
    expect(optionsImpactMatrix).toHaveTextContent('Scenario Lab');
    expect(optionsImpactMatrix).toHaveTextContent('阻断');
    expect(optionsImpactMatrix).toHaveTextContent('计划中');
    expect(optionsImpactMatrix).not.toHaveTextContent('已解锁');
    const optionsActionPlan = screen.getByTestId('data-source-gap-registry-action-plan-options_chains');
    expect(optionsActionPlan).toHaveTextContent('确认期权链授权');
    expect(optionsActionPlan).toHaveTextContent('关键');
    expect(optionsActionPlan).toHaveTextContent('Provider entitlement');
    expect(optionsActionPlan).toHaveTextContent('等待授权');
    expect(optionsActionPlan).toHaveTextContent('授权证明');
    expect(optionsActionPlan).toHaveTextContent('权益证明缺失');
    expect(optionsActionPlan).toHaveTextContent('Options Lab 链观察');
    expect(optionsActionPlan).toHaveTextContent('外部授权');
    expect(optionsActionPlan).toHaveTextContent('保护域复核');

    const gammaRow = screen.getByTestId('data-source-gap-registry-row-gamma_dealer_positioning');
    fireEvent.click(within(gammaRow).getByRole('button', { name: '展开 Gamma / Dealer Positioning' }));
    expect(gammaRow).toHaveTextContent('Gamma / Dealer Positioning');
    expect(gammaRow).toHaveTextContent('gamma_dealer_positioning');
    expect(gammaRow).toHaveTextContent('阻断');
    expect(gammaRow).toHaveTextContent('权限 未授权');
    expect(gammaRow).toHaveTextContent('时效 不可用');
    expect(gammaRow).not.toHaveTextContent('已就绪');
    const gammaImpactMatrix = screen.getByTestId('data-source-gap-registry-impact-matrix-gamma_dealer_positioning');
    expect(gammaImpactMatrix).toHaveTextContent('Options Lab');
    expect(gammaImpactMatrix).toHaveTextContent('Market Overview');
    expect(gammaImpactMatrix).toHaveTextContent('阻断');
    expect(gammaImpactMatrix).toHaveTextContent('待补证');
    expect(gammaImpactMatrix).not.toHaveTextContent('已解锁');
    const gammaActionPlan = screen.getByTestId('data-source-gap-registry-action-plan-gamma_dealer_positioning');
    expect(gammaActionPlan).toHaveTextContent('确认 Gamma 输入授权');
    expect(gammaActionPlan).toHaveTextContent('等待授权');
    expect(gammaActionPlan).toHaveTextContent('方法版本记录');
    expect(gammaActionPlan).toHaveTextContent('方法评审未完成');

    const panelText = panel.textContent || '';
    expect(panelText).not.toMatch(/requestId|traceId|rawProviderPayload|cacheKey|credential|env|debug|raw dump|api[_-]?key|SECRET_DATA_KEY/i);
    expect(panelText).not.toMatch(/buy|sell|hold|best|recommended|recommendation|optimal|winner|target price|stop loss|position sizing|买入|卖出|持有|目标价|止损|仓位|推荐|最佳|最优|赢家/i);
  });

  it('copies a deterministic engineering action pack from the acquisition priority queue', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    const controls = await screen.findByTestId('data-acquisition-action-pack-controls');
    expect(controls).toHaveTextContent('导出接入行动包');
    expect(screen.getByTestId('data-source-acquisition-priority-options_chains')).toHaveTextContent('授权阻断');
    expect(screen.getByTestId('data-source-acquisition-priority-stock_quote_spine')).toHaveTextContent('数据接入');

    fireEvent.click(within(controls).getByRole('button', { name: '复制导出接入行动包 JSON' }));

    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    const actionPack = JSON.parse(writeText.mock.calls[0][0]);
    expect(actionPack).toMatchObject({
      schemaVersion: 'data_acquisition_action_pack_v1',
      sourceSurface: '数据源运维 / 数据接入优先队列',
      totalQueueItemCount: 4,
    });
    expect(actionPack.generatedAt).toEqual(expect.stringMatching(/^\d{4}-\d{2}-\d{2}T/));
    expect(actionPack.groupedByPriority).toEqual(expect.arrayContaining([
      expect.objectContaining({
        groupLabel: '关键',
        itemCount: 1,
      }),
      expect.objectContaining({
        groupLabel: '高',
        itemCount: 1,
      }),
    ]));
    expect(actionPack.groupedByBlockerType).toEqual(expect.arrayContaining([
      expect.objectContaining({
        groupLabel: '授权阻断',
        itemCount: 1,
      }),
      expect.objectContaining({
        groupLabel: '数据接入',
        itemCount: 1,
      }),
    ]));
    expect(actionPack.items[0]).toMatchObject({
      familyKey: 'options_chains',
      familyLabel: '期权链',
      readinessState: '未授权',
      statusState: '未授权',
      priority: '关键',
      primaryBlockerType: '授权阻断',
      affectedSurfaceCount: 2,
      blockedOrDegradedCapabilityCount: 1,
      externalEntitlementRequired: true,
      protectedDomainReviewRequired: true,
      nextConcreteStep: '收集授权与字段覆盖证据，不接入数据源运行链路。',
      requiredEvidence: ['授权证明', '字段覆盖清单'],
      consumerSafeWarning: '工程补数队列；当前不是决策级证据，不生成交易指令。',
    });
    expect(writeText.mock.calls[0][0]).not.toMatch(/requestId|traceId|rawProviderPayload|cacheKey|credential|env|debug|raw dump|api[_-]?key|SECRET_DATA_KEY/i);
    expect(writeText.mock.calls[0][0]).not.toMatch(/buy|sell|hold|best|recommended|recommendation|optimal|winner|target price|stop loss|position sizing|买入|卖出|持有|目标价|止损|仓位|推荐|最佳|最优|赢家/i);
  });

  it('keeps missing registry fields unknown instead of crashing or overclaiming readiness', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    getOperations.mockResolvedValue(populatedPayload);
    getDataSourceGapRegistry.mockResolvedValue({
      ...dataSourceGapRegistryPayload,
      summary: { totalFamilies: 1 },
      acquisitionPriorityQueue: [
        {
          familyKey: 'unknown_new_family',
          familyLabel: 'Unknown New Family',
          priorityReason: 'rawProviderPayload requestId traceId',
          primaryBlockerType: 'provider-integration',
          nextConcreteStep: 'token=secret next step',
          requiredEvidence: ['api_key secret evidence'],
          consumerSafeWarning: 'debug raw dump',
        },
      ],
      families: [
        {
          familyKey: 'unknown_new_family',
          consumerLabel: 'Unknown New Family',
          surfaceImpactMatrix: [
            {
              surfaceKey: 'unknown_surface',
              consumerLabel: 'requestId secret surface',
              impactState: 'unlocked',
              impactReason: 'rawProviderPayload requestId traceId',
              affectedCapability: 'debug cacheKey capability',
              nextEvidenceStep: 'token=secret next step',
            },
          ],
        },
      ],
    });

    render(<MarketProviderOperationsPage />);

    await screen.findByTestId('data-source-gap-registry-panel');
    const row = screen.getByTestId('data-source-gap-registry-row-unknown_new_family');
    expect(screen.getByTestId('data-source-gap-registry-group-other')).toHaveTextContent('其他待补证');
    fireEvent.click(within(row).getByRole('button', { name: '展开 Unknown New Family' }));
    expect(row).toHaveTextContent('Unknown New Family');
    expect(row).toHaveTextContent('unknown_new_family');
    expect(row).toHaveTextContent('待补证');
    expect(row).toHaveTextContent('补数权限 待补证');
    expect(row).toHaveTextContent('计分/交易权限 待补证');
    const unknownImpact = screen.getByTestId('data-source-gap-registry-impact-matrix-unknown_new_family');
    expect(unknownImpact).toHaveTextContent('影响面待补证');
    expect(unknownImpact).toHaveTextContent('待补证');
    expect(unknownImpact).toHaveTextContent('影响原因待补证。');
    expect(unknownImpact).not.toHaveTextContent('已解锁');
    expect(unknownImpact).not.toHaveTextContent(/requestId|traceId|rawProviderPayload|cacheKey|token|secret|debug/i);
    const unknownActionPlan = screen.getByTestId('data-source-gap-registry-action-plan-unknown_new_family');
    expect(unknownActionPlan).toHaveTextContent('行动计划待补证');
    expect(unknownActionPlan).not.toHaveTextContent(/requestId|traceId|rawProviderPayload|cacheKey|token|secret|debug/i);
    const unknownQueueItem = screen.getByTestId('data-source-acquisition-priority-unknown_new_family');
    expect(unknownQueueItem).toHaveTextContent('中');
    expect(unknownQueueItem).toHaveTextContent('待补证');
    expect(unknownQueueItem).toHaveTextContent('数据接入');
    expect(unknownQueueItem).toHaveTextContent('影响面 0');
    expect(unknownQueueItem).toHaveTextContent('阻断/降级能力 0');
    expect(unknownQueueItem).toHaveTextContent('下一步待补证。');
    expect(unknownQueueItem).toHaveTextContent('证据待补证');
    expect(unknownQueueItem).toHaveTextContent('工程补数队列；当前不是决策级证据。');
    expect(unknownQueueItem).not.toHaveTextContent(/requestId|traceId|rawProviderPayload|cacheKey|token|secret|debug/i);
    const workbench = screen.getByTestId('data-source-acquisition-workbench');
    expect(workbench).toHaveTextContent('接入执行工作台');
    expect(workbench).toHaveTextContent('数据接入 1');
    expect(workbench).toHaveTextContent('阻断待确认 0');
    expect(workbench).toHaveTextContent('未知/待补证字段');
    expect(workbench).toHaveTextContent('证据待补证');
    expect(workbench).toHaveTextContent('下一步待补证。');
    expect(workbench).not.toHaveTextContent(/requestId|traceId|rawProviderPayload|cacheKey|token|secret|debug/i);
    expect(row).not.toHaveTextContent('已就绪');
    expect(row).not.toHaveTextContent('权限 可用');
    expect(row).not.toHaveTextContent('时效 新鲜');

    fireEvent.click(screen.getByRole('button', { name: '复制导出接入行动包 JSON' }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    const actionPack = JSON.parse(writeText.mock.calls[0][0]);
    expect(actionPack.items).toMatchObject([
      {
        familyKey: 'unknown_new_family',
        familyLabel: 'Unknown New Family',
        readinessState: '待补证',
        affectedSurfaceCount: 'unknown/待补证',
        blockedOrDegradedCapabilityCount: 'unknown/待补证',
        externalEntitlementRequired: 'unknown/待补证',
        protectedDomainReviewRequired: 'unknown/待补证',
        nextConcreteStep: '下一步待补证。',
        requiredEvidence: ['证据待补证'],
        consumerSafeWarning: '工程补数队列；当前不是决策级证据。',
      },
    ]);
    expect(writeText.mock.calls[0][0]).not.toMatch(/已就绪|已解锁|权限 可用|新鲜|requestId|traceId|rawProviderPayload|cacheKey|token|secret|debug/i);
  });

  it('renders compact blocked copy when the data source gap registry API is unavailable', async () => {
    getOperations.mockResolvedValue(populatedPayload);
    getDataSourceGapRegistry.mockRejectedValue(new Error('registry unavailable'));

    render(<MarketProviderOperationsPage />);

    const panel = await screen.findByTestId('data-source-gap-registry-panel');
    expect(panel).toHaveTextContent('专业数据地图待补证');
    expect(panel).toHaveTextContent('登记表接口暂不可用');
    const workbench = screen.getByTestId('data-source-acquisition-workbench');
    expect(workbench).toHaveTextContent('接入执行工作台');
    expect(workbench).toHaveTextContent('工作台待补证');
    expect(workbench).toHaveTextContent('fail-closed');
    expect(workbench).toHaveTextContent('不使用本地替代队列');
    expect(screen.getByTestId('data-acquisition-action-pack-controls')).toHaveTextContent('导出接入行动包不可用');
    expect(screen.getByRole('button', { name: '复制导出接入行动包 JSON' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '下载导出接入行动包 JSON' })).toBeDisabled();
    expect(panel).not.toHaveTextContent('股票报价骨架');
    expect(panel).not.toHaveTextContent('期权链');
  });

  it('renders a provider setup checklist with grouped affected surfaces, safe badges, and curated guidance only', async () => {
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    expect(await screen.findByText('数据源配置清单')).toBeInTheDocument();
    const checklist = screen.getByTestId('market-provider-setup-checklist');
    const betaChecklist = screen.getByTestId('market-provider-beta-readiness-checklist');
    expect(checklist).toHaveTextContent('Beta readiness');
    expect(betaChecklist).toHaveTextContent('需补齐 5 项');
    expect(betaChecklist).toHaveTextContent('Fed Liquidity');
    expect(betaChecklist).toHaveTextContent('Tushare Pro');
    expect(betaChecklist).toHaveTextContent('本地样本与缓存');
    expect(betaChecklist).toHaveTextContent('需要缓存 5 条契约');
    expect(betaChecklist).toHaveTextContent('降级 / 备用观察');
    expect(betaChecklist).toHaveTextContent('仅观察来源');
    expect(checklist).toHaveTextContent('只读展示现有数据源缺口会影响哪些产品面');
    expect(checklist).toHaveTextContent('Market Overview');
    expect(checklist).toHaveTextContent('Liquidity Monitor');
    expect(checklist).toHaveTextContent('Rotation Radar');
    expect(checklist).toHaveTextContent('Scanner');
    expect(checklist).toHaveTextContent('Portfolio');
    expect(checklist).toHaveTextContent('Watchlist');
    expect(checklist).toHaveTextContent('Options Lab');
    expect(checklist).toHaveTextContent('数据源运维 / 系统诊断');
    const marketOverviewGroup = screen.getByTestId('market-provider-setup-surface-market-overview');
    const rotationGroup = screen.getByTestId('market-provider-setup-surface-rotation-radar');
    expect(marketOverviewGroup).not.toHaveAttribute('open');
    expect(marketOverviewGroup).toHaveTextContent('默认折叠');
    expect(rotationGroup).not.toHaveAttribute('open');
    expect(rotationGroup).toHaveTextContent('默认折叠');
    expect(rotationGroup).not.toHaveTextContent('刷新 CN/HK connect 缓存快照');
    within(checklist).getAllByRole('button', { name: /^展开 / }).forEach((button) => fireEvent.click(button));
    expect(checklist).toHaveTextContent('需要凭据');
    expect(checklist).toHaveTextContent('可能需付费');
    expect(checklist).toHaveTextContent('需要缓存');
    expect(checklist).toHaveTextContent('官方公开缓存');
    expect(checklist).toHaveTextContent('默认关闭');
    expect(checklist).toHaveTextContent('聚合证据');
    expect(checklist).toHaveTextContent('仅观察');
    expect(checklist).toHaveTextContent('评分阻断');
    expect(checklist).toHaveTextContent('缺少数据源配置');
    expect(checklist).toHaveTextContent('沿现有 Tushare 凭据配置路径处理，并继续避免在本页显示密钥值。');
    expect(checklist).toHaveTextContent('保持 Polygon grouped-daily 宽度走已批准的凭据与缓存路径');
    expect(checklist).toHaveTextContent('同步已批准的本地美股 parquet/cache 覆盖');
    expect(checklist).toHaveTextContent('刷新已批准的官方公开 money-market 缓存快照');
    expect(checklist).toHaveTextContent('刷新 CN/HK connect 缓存快照，减少覆盖缺口并保持不新增实时数据源调用。');
    expect(checklist).toHaveTextContent('补齐既有 Fed liquidity 聚合证据缓存');
    expect(checklist).toHaveTextContent('完成现有授权 feed 配置后，再返回本页确认期货确认链路是否通过。');
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
    expect(checklist).not.toHaveTextContent('official-public cache-only');
    expect(checklist).not.toHaveTextContent('missing provider');
    expect(checklist).not.toHaveTextContent('Provider Ops / system diagnostics');
    expect(checklist).not.toHaveTextContent('observation-only');
    expect(checklist).not.toHaveTextContent('score-blocked');

    const checklistText = checklist.textContent || '';
    expect(checklistText.indexOf('Portfolio')).toBeLessThan(checklistText.indexOf('Watchlist'));
    expect(checklistText.indexOf('Watchlist')).toBeLessThan(checklistText.indexOf('Options Lab'));

    const matrixDisclosure = screen.getByTestId('market-provider-matrix-disclosure');
    expect(matrixDisclosure).toHaveTextContent('L4 完整数据源矩阵：来源 / 就绪 / 门槛 / 原因代码（已脱敏）');
    expect(matrixDisclosure).not.toHaveTextContent('Provider');
    expect(matrixDisclosure).not.toHaveTextContent('Readiness');
    expect(matrixDisclosure).not.toHaveTextContent('Reason codes');
    fireEvent.click(within(matrixDisclosure).getByRole('button', { name: '展开 L4 完整数据源矩阵：来源 / 就绪 / 门槛 / 原因代码（已脱敏）' }));
    expect(matrixDisclosure).toHaveTextContent('cache-required');
    expect(matrixDisclosure).toHaveTextContent('present');
    expect(matrixDisclosure).toHaveTextContent('polygon_high_low_history_unavailable');
    expect(matrixDisclosure).toHaveTextContent('missing_provider_configuration');
    expect(within(matrixDisclosure).getByRole('button', { name: '收起 L4 完整数据源矩阵：来源 / 就绪 / 门槛 / 原因代码（已脱敏）' })).toBeInTheDocument();
  });

  it('renders a provider-free consumer evidence impact matrix with affected routes and next diagnostics', async () => {
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    const matrix = await screen.findByTestId('market-provider-consumer-evidence-matrix');
    expect(matrix).toHaveTextContent('消费者证据影响矩阵');
    expect(matrix).toHaveTextContent('admin 诊断视图');
    expect(matrix).toHaveTextContent('Market Overview');
    expect(matrix).toHaveTextContent('Decision Cockpit');
    expect(matrix).toHaveTextContent('Research Radar');
    expect(matrix).toHaveTextContent('market_regime');
    expect(matrix).toHaveTextContent('decision_context');
    expect(matrix).toHaveTextContent('research_prerequisites');
    expect(matrix).toHaveTextContent('/market-overview');
    expect(matrix).toHaveTextContent('/market/decision-cockpit');
    expect(matrix).toHaveTextContent('/research/radar');
    expect(matrix).toHaveTextContent('缺失 1');
    expect(matrix).toHaveTextContent('阻断 1');
    expect(matrix).toHaveTextContent('仅观察 2');
    expect(matrix).toHaveTextContent('评分级 1');
    expect(matrix).toHaveTextContent('Compare overview evidence families against current safe surface snapshots.');
    expect(matrix).toHaveTextContent('Build a cockpit driver table from existing market and research read models.');
    expect(matrix).toHaveTextContent('Check scanner and watchlist prerequisites before expecting research evidence.');
    expect(matrix).toHaveTextContent('Market overview has one score-grade input, while supporting evidence remains capped or observational.');
    expect(matrix).toHaveTextContent('Decision cockpit is missing required cross-surface evidence and cannot make a strong market judgment.');
    expect(matrix).toHaveTextContent('Research radar can explain available observations but prerequisite evidence is incomplete.');
    expect(matrix).not.toHaveTextContent('contractVersion');
    expect(matrix).not.toHaveTextContent('mutationEnabled');
    expect(matrix).not.toHaveTextContent('networkCallsEnabled');
    expect(matrix).not.toHaveTextContent('providerRuntimeCalled');
    expect(matrix).not.toHaveTextContent('https://');
    expect(matrix).not.toHaveTextContent('token=');
    expect(matrix).not.toHaveTextContent('/Users/example/provider');
    expect(matrix).not.toHaveTextContent(/buy|sell|recommend|target|stop|position|买入|卖出|止损|目标价/i);
  });

  it('keeps non-scoring setup copy conservative and leaves score eligibility to existing source gates', async () => {
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    const checklist = await screen.findByTestId('market-provider-setup-checklist');
    const sourceGapDisclosure = screen.getByTestId('market-provider-source-gap-disclosure');
    expect(sourceGapDisclosure).toHaveAttribute('data-open', 'false');
    fireEvent.click(within(sourceGapDisclosure).getByRole('button', { name: '展开 L2 来源缺口：影响产品面 / 解锁能力 / 下一步' }));
    const gapBoard = screen.getByTestId('market-provider-source-gap-board');

    expect(gapBoard).toHaveTextContent('补足可用性说明');
    expect(gapBoard).toHaveTextContent('减少备用/代理/缺失状态');
    expect(gapBoard).toHaveTextContent('改善数据覆盖披露');
    expect(gapBoard).toHaveTextContent('是否进入评分仍由既有 source-confidence gates 决定');
    expect(gapBoard).not.toHaveTextContent('提升到可支撑评分级结论');
    expect(gapBoard).not.toHaveTextContent('让当前仅观察的证据进入可用结论面');
    expect(checklist).toHaveTextContent('仅用于诊断/观察/配置指引');
    expect(checklist).toHaveTextContent('是否进入评分仍由既有 source-confidence gates 决定');
    expect(checklist).not.toHaveTextContent('提升为可评分证据');
    expect(checklist).not.toHaveTextContent('decision-grade');
    expect(checklist).not.toHaveTextContent('conclusion-ready');
  });

  it('describes synthetic fixture rows as diagnostic-only guidance instead of score-grade promotion', async () => {
    getOperations.mockResolvedValue(populatedPayload);
    getOperationsMatrix.mockResolvedValue({
      ...operationsMatrixPayload,
      rows: [
        ...operationsMatrixPayload.rows,
        {
          providerId: 'synthetic.fixture.market_context',
          providerName: 'Synthetic fixture context',
          sourceLabel: 'Synthetic fixture context',
          providerCategory: 'diagnostic_fixture',
          sourceType: 'synthetic_fixture',
          sourceTier: 'fixture',
          trustLevel: 'synthetic_fixture',
          freshnessExpectation: 'fixture',
          runtimeState: 'observation_only',
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
          cacheRequired: false,
          supportedCapabilities: ['diagnostic_surface_projection'],
          affectedSurfaces: ['provider_ops'],
          productAffectedSurfaces: ['watchlist'],
          routerReasonCodes: ['fixture_only'],
          reasonCodes: ['synthetic_fixture_only'],
          fulfilledMetrics: [],
          missingMetrics: [],
          coverageCount: 0,
          missingProviderReason: null,
          degradationReason: 'synthetic_fixture_only',
          remediationHint: 'Keep local synthetic fixture disabled outside diagnostics.',
          diagnosticOnly: true,
        },
      ],
      summary: {
        ...operationsMatrixPayload.summary,
        totalRows: 8,
        observationOnlyRows: 4,
        inertMetadataOnlyRows: 6,
      },
    });

    render(<MarketProviderOperationsPage />);

    const checklist = await screen.findByTestId('market-provider-setup-checklist');
    const watchlistGroup = screen.getByTestId('market-provider-setup-surface-watchlist');
    expect(watchlistGroup).not.toHaveAttribute('open');
    expect(watchlistGroup).not.toHaveTextContent('Synthetic fixture context');
    fireEvent.click(within(watchlistGroup).getByRole('button', { name: '展开 Watchlist' }));
    expect(checklist).toHaveTextContent('Synthetic fixture context');
    expect(checklist).toHaveTextContent('仅用于诊断/观察/配置指引');
    expect(checklist).toHaveTextContent('改善数据覆盖披露');
    expect(checklist).not.toHaveTextContent('提升为可评分证据');
    expect(checklist).not.toHaveTextContent('score-grade');
  });

  it('keeps product labels available without introducing trading-action wording', async () => {
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    const checklist = await screen.findByTestId('market-provider-setup-checklist');
    expect(checklist).toHaveTextContent('Portfolio');
    expect(checklist).toHaveTextContent('Watchlist');
    expect(checklist).toHaveTextContent('Options Lab');

    const bodyText = document.body.textContent || '';
    expect(bodyText).not.toMatch(/买入按钮|下单|立即交易|必买|稳赚|保证收益|guaranteed|best contract|AI recommends you buy/i);
  });

  it('honors a safe surface query for setup focus without hiding full diagnostics', async () => {
    const previousPath = window.location.pathname;
    const previousSearch = window.location.search;
    window.history.replaceState({}, '', '/admin/market-providers?surface=market_overview');
    getOperations.mockResolvedValue(populatedPayload);

    try {
      render(<MarketProviderOperationsPage />);

      expect(await screen.findByText('数据源配置清单')).toBeInTheDocument();
      const focus = screen.getByTestId('market-provider-setup-surface-focus');
      expect(focus).toHaveTextContent('已按 Market Overview 聚焦');
      expect(focus).toHaveTextContent('默认只标记该产品面');
      expect(focus).toHaveTextContent('确认覆盖缺口');
      const checklist = screen.getByTestId('market-provider-setup-checklist');
      expect(checklist).toHaveTextContent('Market Overview');
      expect(checklist).toHaveTextContent('Rotation Radar');
      expect(checklist).toHaveTextContent('Portfolio');
      const marketOverviewGroup = screen.getByTestId('market-provider-setup-surface-market-overview');
      expect(marketOverviewGroup).not.toHaveAttribute('open');
      expect(marketOverviewGroup).toHaveTextContent('默认折叠');
      expect(screen.getByTestId('market-provider-setup-surface-rotation-radar')).not.toHaveAttribute('open');
      expect(screen.getByTestId('market-provider-setup-surface-portfolio')).not.toHaveAttribute('open');
      expect(marketOverviewGroup).not.toHaveTextContent('Fed Liquidity');
      expect(marketOverviewGroup).not.toHaveTextContent('Polygon grouped daily US equities');
      expect(screen.getByTestId('market-provider-setup-surface-rotation-radar')).not.toHaveTextContent('CN/HK connect');
      expect(screen.getByTestId('market-provider-setup-surface-portfolio')).not.toHaveTextContent('Portfolio 手动');
      fireEvent.click(within(marketOverviewGroup).getByRole('button', { name: '展开 Market Overview' }));
      expect(marketOverviewGroup).toHaveTextContent('Fed Liquidity');
      expect(marketOverviewGroup).toHaveTextContent('Polygon grouped daily US equities');

      const matrixDisclosure = screen.getByTestId('market-provider-matrix-disclosure');
      fireEvent.click(within(matrixDisclosure).getByRole('button', { name: '展开 L4 完整数据源矩阵：来源 / 就绪 / 门槛 / 原因代码（已脱敏）' }));
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

      expect(await screen.findByText('数据源配置清单')).toBeInTheDocument();
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
    expect(screen.getByText('暂无数据源矩阵行')).toBeInTheDocument();
  });

  it('renders a section-scoped API error when the operations matrix request fails', async () => {
    getOperations.mockResolvedValue(populatedPayload);
    getOperationsMatrix.mockRejectedValue(new Error('forbidden'));

    render(<MarketProviderOperationsPage />);

    expect(await screen.findByRole('heading', { name: '数据源维护路线图' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByRole('alert').length).toBeGreaterThan(0));
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
    expect(screen.getByRole('button', { name: '展开 L4 已脱敏细节：限制代码 / 快照摘要 / 追踪标识' })).toBeInTheDocument();
  });

  it('renders API errors with the existing alert pattern', async () => {
    getOperations.mockRejectedValue(new Error('admin required'));

    render(<MarketProviderOperationsPage />);

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(within(screen.getByRole('alert')).getByText('读取市场数据源运维失败')).toBeInTheDocument();
  });

  it('renders unified drill-through controls to logs, circuits, cost, and evidence surfaces', async () => {
    getOperations.mockResolvedValue({
      ...populatedPayload,
      adminLogDrillThrough: {
        ...populatedPayload.adminLogDrillThrough,
        query: {
          tab: 'business',
          query: 'market provider',
          since: '24h',
          provider: 'fallback token=SECRET',
          source: 'quote',
          trace: 'trace-should-not-render',
        },
        eventId: 'evt-1 token=SECRET',
      },
    });

    render(<MarketProviderOperationsPage />);

    await screen.findByTestId('market-provider-l0-overview-strip');
    const adminLogHrefs = Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href^="/zh/admin/logs"]'))
      .map((link) => link.getAttribute('href') || '');
    expect(adminLogHrefs).toContain('/zh/admin/logs?tab=business&query=market%20provider%20fallback%20quote&since=24h&eventId=evt-1');
    for (const href of adminLogHrefs) {
      expect(href).not.toMatch(/provider=|source=|trace|token|SECRET/i);
    }
    expect(screen.getByRole('link', { name: /查看熔断与配额/i })).toHaveAttribute('href', '/zh/admin/provider-circuits?provider=fallback&since=24h');
    expect(screen.getByRole('link', { name: /查看成本观测/i })).toHaveAttribute('href', '/zh/admin/cost-observability?window=24h&area=provider');
    expect(screen.getByRole('link', { name: /查看证据工作流/i })).toHaveAttribute('href', '/zh/admin/evidence-workflow?ref=provider_bundle#schema-ref');
    expect(document.body).not.toHaveTextContent('super-secret-token');
    expect(document.body).not.toHaveTextContent('SECRET');
  });

  it('wraps visible code-like provider detail values instead of letting them overflow the side rail', async () => {
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    expect(await screen.findByText('诊断默认收起')).toBeInTheDocument();
    expect(screen.queryByTestId('market-provider-detail-endpoint')).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: '查看诊断' })[0]);
    const endpointField = await screen.findByTestId('market-provider-detail-endpoint');
    expect(endpointField).toHaveTextContent('已脱敏，仅保留产品面诊断引用');
    expect(endpointField).not.toHaveTextContent('/api/v1/market/cn-indices');
    expect(endpointField).not.toHaveTextContent('endpoint');
    expect(endpointField).toHaveClass('break-words');
    expect(screen.getByTestId('market-provider-detail-provider-id')).toHaveClass('break-all');
  });

  it('keeps provider endpoint values out of visible L3 and L4 diagnostics', async () => {
    getOperations.mockResolvedValue({
      ...populatedPayload,
      items: [
        {
          ...populatedPayload.items[0],
          endpoint: '/api/v1/market/cn-indices?token=secret-token&path=/Users/example/provider',
        },
      ],
    });

    render(<MarketProviderOperationsPage />);

    await screen.findByText('诊断默认收起');
    fireEvent.click(screen.getAllByRole('button', { name: '查看诊断' })[0]);
    expect(await screen.findByTestId('market-provider-detail-endpoint')).toHaveTextContent('已脱敏，仅保留产品面诊断引用');

    const diagnosticsDisclosure = screen.getByTestId('market-provider-diagnostics-disclosure');
    fireEvent.click(within(diagnosticsDisclosure).getByRole('button', { name: '展开 L4 已脱敏细节：限制代码 / 快照摘要 / 追踪标识' }));

    expect(document.body).not.toHaveTextContent('/api/v1/market/cn-indices');
    expect(document.body).not.toHaveTextContent('secret-token');
    expect(document.body).not.toHaveTextContent('/Users/example/provider');
    expect(diagnosticsDisclosure).not.toHaveTextContent('"endpoint"');
  });
});
