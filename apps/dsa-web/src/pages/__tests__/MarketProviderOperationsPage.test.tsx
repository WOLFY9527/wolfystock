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

const { getDataSourceGapRegistry } = vi.hoisted(() => ({
  getDataSourceGapRegistry: vi.fn(),
}));

vi.mock('../../api/marketProviderOperations', () => ({
  marketProviderOperationsApi: {
    getOperations,
    getOperationsMatrix,
  },
}));

vi.mock('../../api/market', async () => {
  const actual = await vi.importActual<typeof import('../../api/market')>('../../api/market');
  return {
    ...actual,
    marketApi: {
      getDataReadiness,
      getDataSourceGapRegistry,
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
    },
    {
      familyKey: 'options_chains',
      consumerLabel: 'Options Chains',
      status: 'unauthorized',
      authorityState: 'unauthorized',
      freshnessState: 'unavailable',
      entitlementOrLicensingBlocker: 'OPRA rights and display rights are not proven.',
      integrationBlocker: 'No authorized live or delayed chain store is integrated.',
      sourceEvidenceState: 'rights_unproven',
      nextIntegrationStep: 'Attach an entitlement proof bundle before chain promotion.',
      providerHydrationAllowed: false,
      scoreTradingAuthorityAllowed: false,
      consumerSafeDescription: 'Options chains remain unavailable until authorized chain evidence exists.',
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

describe('MarketProviderOperationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, '', '/zh/admin/market-providers');
    getDataReadiness.mockResolvedValue(readinessPayload);
    getOperationsMatrix.mockResolvedValue(operationsMatrixPayload);
    getDataSourceGapRegistry.mockResolvedValue(dataSourceGapRegistryPayload);
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
    expect(screen.getByText('AAPL')).toBeInTheDocument();
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
    expect(dataMap).toHaveTextContent('股票报价骨架');
    expect(dataMap).toHaveTextContent('stock_quote_spine');
    expect(dataMap).toHaveTextContent('期权链');
    expect(dataMap).toHaveTextContent('options_chains');
    expect(dataMap).toHaveTextContent('Gamma / Dealer Positioning');
    expect(dataMap).toHaveTextContent('gamma_dealer_positioning');
    expect(dataMap).toHaveTextContent('部分可用');
    expect(dataMap).toHaveTextContent('未授权');
    expect(dataMap).toHaveTextContent('阻断');
    expect(dataMap).toHaveTextContent('仅观察');
    expect(dataMap).toHaveTextContent('计划中');
    expect(dataMap).toHaveTextContent('计分权限 不允许');
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

  it('renders the backend data source gap registry as a fail-closed professional data map', async () => {
    getOperations.mockResolvedValue(populatedPayload);

    render(<MarketProviderOperationsPage />);

    const panel = await screen.findByTestId('data-source-gap-registry-panel');
    expect(panel).toHaveTextContent('专业数据地图');
    expect(panel).toHaveTextContent('只消费后端数据源缺口登记表');
    expect(panel).toHaveTextContent('未触发数据运行');
    expect(panel).toHaveTextContent('网络调用关闭');
    expect(panel).toHaveTextContent('不授予计分权限');
    expect(panel).toHaveTextContent('已就绪');
    expect(panel).toHaveTextContent('部分可用');
    expect(panel).toHaveTextContent('未授权');
    expect(panel).toHaveTextContent('阻断');
    expect(panel).toHaveTextContent('仅观察');
    expect(panel).toHaveTextContent('计划中');

    const quoteRow = screen.getByTestId('data-source-gap-registry-row-stock_quote_spine');
    expect(quoteRow).toHaveTextContent('股票报价骨架');
    expect(quoteRow).toHaveTextContent('stock_quote_spine');
    expect(quoteRow).toHaveTextContent('部分可用');
    expect(quoteRow).toHaveTextContent('权限 阻断');
    expect(quoteRow).toHaveTextContent('时效 延迟');
    expect(quoteRow).toHaveTextContent('补数 允许');
    expect(quoteRow).toHaveTextContent('计分权限 不允许');
    expect(quoteRow).toHaveTextContent('落地报价与日线快照');

    const optionsRow = screen.getByTestId('data-source-gap-registry-row-options_chains');
    expect(optionsRow).toHaveTextContent('期权链');
    expect(optionsRow).toHaveTextContent('未授权');
    expect(optionsRow).toHaveTextContent('权限 未授权');
    expect(optionsRow).toHaveTextContent('时效 不可用');
    expect(optionsRow).toHaveTextContent('补数 不允许');
    expect(optionsRow).toHaveTextContent('计分权限 不允许');
    expect(optionsRow).not.toHaveTextContent('已就绪');

    const gammaRow = screen.getByTestId('data-source-gap-registry-row-gamma_dealer_positioning');
    expect(gammaRow).toHaveTextContent('Gamma / Dealer Positioning');
    expect(gammaRow).toHaveTextContent('阻断');
    expect(gammaRow).toHaveTextContent('权限 未授权');
    expect(gammaRow).toHaveTextContent('时效 不可用');
    expect(gammaRow).not.toHaveTextContent('已就绪');

    const panelText = panel.textContent || '';
    expect(panelText).not.toMatch(/requestId|traceId|rawProviderPayload|cacheKey|credential|env|debug|raw dump|api[_-]?key|SECRET_DATA_KEY/i);
    expect(panelText).not.toMatch(/buy|sell|hold|best|recommended|recommendation|optimal|winner|target price|stop loss|position sizing|买入|卖出|持有|目标价|止损|仓位|推荐|最佳|最优|赢家/i);
  });

  it('keeps missing registry fields unknown instead of crashing or overclaiming readiness', async () => {
    getOperations.mockResolvedValue(populatedPayload);
    getDataSourceGapRegistry.mockResolvedValue({
      ...dataSourceGapRegistryPayload,
      summary: { totalFamilies: 1 },
      families: [
        {
          familyKey: 'unknown_new_family',
          consumerLabel: 'Unknown New Family',
        },
      ],
    });

    render(<MarketProviderOperationsPage />);

    await screen.findByTestId('data-source-gap-registry-panel');
    const row = screen.getByTestId('data-source-gap-registry-row-unknown_new_family');
    expect(row).toHaveTextContent('Unknown New Family');
    expect(row).toHaveTextContent('unknown_new_family');
    expect(row).toHaveTextContent('待补证');
    expect(row).toHaveTextContent('补数 待补证');
    expect(row).toHaveTextContent('计分权限 待补证');
    expect(row).not.toHaveTextContent('已就绪');
    expect(row).not.toHaveTextContent('权限 可用');
    expect(row).not.toHaveTextContent('时效 新鲜');
  });

  it('renders compact blocked copy when the data source gap registry API is unavailable', async () => {
    getOperations.mockResolvedValue(populatedPayload);
    getDataSourceGapRegistry.mockRejectedValue(new Error('registry unavailable'));

    render(<MarketProviderOperationsPage />);

    const panel = await screen.findByTestId('data-source-gap-registry-panel');
    expect(panel).toHaveTextContent('专业数据地图待补证');
    expect(panel).toHaveTextContent('登记表接口暂不可用');
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
