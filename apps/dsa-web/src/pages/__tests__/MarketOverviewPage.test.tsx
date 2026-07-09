import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { createElement, StrictMode } from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MarketOverviewPage, { __resetMarketOverviewRequestOwnershipForTests } from '../MarketOverviewPage';
import { MarketOverviewWorkbench } from '../../components/market-overview/MarketOverviewWorkbench';
import { MARKET_OVERVIEW_TAB_CONFIG } from '../MarketOverviewTabConfig';
import { marketOverviewApi } from '../../api/marketOverview';
import { marketApi } from '../../api/market';
import { DataFreshnessBadge, MarketDataRow, MarketOverviewPanelFooter } from '../../components/market-overview/marketOverviewPrimitives';
import { TerminalPageHeading } from '../../components/terminal/TerminalPrimitives';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../i18n/core';
import { marketIntelligenceReasonLabel } from '../../utils/marketIntelligenceGuidance';

const marketOverviewTopSurfaceSource = readFileSync(
  resolve(process.cwd(), 'src/components/market-overview/MarketOverviewWorkbenchTopSurface.tsx'),
  'utf8',
);
const marketOverviewDecisionDebugDetailsSource = readFileSync(
  resolve(process.cwd(), 'src/components/market-overview/MarketOverviewDecisionDebugDetails.tsx'),
  'utf8',
);

const RAW_MARKET_OVERVIEW_PROXY_LABEL_PATTERN = /ETF flow proxy|Institutional pressure proxy|Industry breadth proxy|\bproxy\b/i;

const { useProductSurfaceMock } = vi.hoisted(() => ({
  useProductSurfaceMock: vi.fn(),
}));

vi.mock('../../api/marketOverview', () => ({
  marketOverviewApi: {
    getIndices: vi.fn(),
    getVolatility: vi.fn(),
    getFundsFlow: vi.fn(),
    getMacro: vi.fn(),
  },
}));

vi.mock('../../api/market', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/market')>();
  return {
    ...actual,
    marketApi: {
      getCrypto: vi.fn(),
      getSentiment: vi.fn(),
      getCnIndices: vi.fn(),
      getCnBreadth: vi.fn(),
      getCnFlows: vi.fn(),
      getSectorRotation: vi.fn(),
      getUsBreadth: vi.fn(),
      getRates: vi.fn(),
      getFxCommodities: vi.fn(),
      getTemperature: vi.fn(),
      getMarketBriefing: vi.fn(),
      getFutures: vi.fn(),
      getCnShortSentiment: vi.fn(),
      getRegimeReadModel: vi.fn(),
      getDataReadiness: vi.fn(),
      getProfessionalDataCapabilities: vi.fn(),
      cryptoStreamUrl: vi.fn(() => '/api/v1/market/crypto/stream'),
      normalizeCryptoStreamPayload: vi.fn((payload) => payload),
    },
  };
});

vi.mock('../../hooks/useProductSurface', () => ({
  useProductSurface: useProductSurfaceMock,
}));

const panel = (panelName: string, symbol: string, label = symbol) => ({
  panelName,
  lastRefreshAt: '2026-04-29T10:00:00',
  status: 'success' as const,
  logSessionId: `${panelName}-log`,
  source: 'yahoo',
  sourceLabel: 'Yahoo Finance',
  updatedAt: '2026-04-29T10:01:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'delayed' as const,
  isFallback: false,
  isStale: false,
  items: [
    {
      symbol,
      label,
      value: 100,
      unit: 'pts',
      changePct: 1.2,
      riskDirection: 'decreasing' as const,
      trend: [96, 98, 100],
      source: 'yahoo',
      sourceLabel: 'Yahoo Finance',
      updatedAt: '2026-04-29T10:01:00',
      asOf: '2026-04-29T10:00:00',
      freshness: 'delayed' as const,
      isFallback: false,
      isStale: false,
    },
  ],
});

const quoteItem = (
  symbol: string,
  label: string,
  value: number,
  changePct: number,
  source = 'yahoo',
) => ({
  symbol,
  label,
  value,
  unit: 'pts',
  changePct,
  riskDirection: changePct >= 0 ? 'decreasing' as const : 'increasing' as const,
  trend: [value * 0.98, value * 0.99, value],
  source,
  sourceLabel: source === 'sina' ? 'Sina' : 'Yahoo Finance',
  updatedAt: '2026-04-29T10:01:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'delayed' as const,
  isFallback: false,
  isStale: false,
});

const denseQuotePanel = (panelName: string, items: ReturnType<typeof quoteItem>[], source = 'yahoo') => ({
  ...panel(panelName, items[0]?.symbol || 'SPX', items[0]?.label || 'S&P 500'),
  source: source === 'mixed' ? 'mixed' : source,
  sourceLabel: source === 'mixed' ? 'Sina + Yahoo Finance' : source === 'sina' ? 'Sina' : 'Yahoo Finance',
  items,
});

const officialRiskReadinessPayload = () => ({
  readinessStatus: 'ready',
  diagnosticOnly: true,
  providerRuntimeCalled: false,
  networkCallsEnabled: false,
  representativeSymbols: [],
  checks: [],
  officialRiskSourceReadiness: {
    bundleState: 'partial',
    vix: { state: 'ready', freshness: 'live' },
    rates: { state: 'stale', freshness: 'stale' },
    fedLiquidity: { state: 'blocked', freshness: 'unavailable' },
  },
  crossAssetDriverReadiness: {
    contractVersion: 'cross_asset_driver_readiness_v1',
    consumerSafe: true,
    diagnosticOnly: true,
    networkCallsEnabled: false,
    externalProviderCalls: false,
    mutationEnabled: false,
    supportedStates: ['available', 'missing', 'stale', 'insufficient_history', 'not_configured'],
    consumerSummary: 'Cross-asset drivers are reported as data-readiness inputs only; no market conclusion is inferred.',
    summary: {
      totalDrivers: 3,
      availableCount: 1,
      missingCount: 1,
      staleCount: 1,
      insufficientHistoryCount: 0,
      notConfiguredCount: 0,
    },
    drivers: [
      {
        category: 'equities_index',
        label: 'Equities/index trend',
        supported: true,
        state: 'available',
        configuredIdentifiers: [{ kind: 'symbol', value: 'SPY', market: 'us' }],
        cachedOhlcv: {
          requiredBars: 60,
          usableBars: 90,
          missingBars: 0,
          cacheState: 'cache_hit',
          freshnessState: 'fresh',
          latestBarDate: '2026-06-25',
        },
        missingReasons: [],
        consumerSafeSummary: 'Configured data is present for readiness evaluation.',
      },
      {
        category: 'oil_energy',
        label: 'Oil/energy',
        supported: true,
        state: 'stale',
        configuredIdentifiers: [{ kind: 'symbol', value: 'USO', market: 'us' }],
        cachedOhlcv: {
          requiredBars: 60,
          usableBars: 82,
          missingBars: 0,
          cacheState: 'cache_hit',
          freshnessState: 'stale',
          latestBarDate: '2026-06-20',
        },
        missingReasons: ['stale'],
        consumerSafeSummary: 'Configured data exists but is stale for readiness evaluation.',
      },
      {
        category: 'credit',
        label: 'Credit spreads',
        supported: false,
        state: 'not_configured',
        configuredIdentifiers: [],
        cachedOhlcv: {
          requiredBars: 60,
          usableBars: 0,
          missingBars: 60,
          cacheState: 'not_applicable',
          freshnessState: 'unknown',
          latestBarDate: null,
        },
        missingReasons: ['not_configured'],
        consumerSafeSummary: 'Driver category is not configured for readiness evaluation.',
      },
    ],
  },
});

const professionalDataCapabilitiesPayload = () => ({
  contractVersion: 'professional_data_capability_registry_v1',
  consumerSafe: true,
  summary: {
    totalCapabilities: 6,
    liveCount: 1,
    degradedCount: 2,
    entitlementRequiredCount: 1,
    configuredMissingCount: 1,
    notImplementedCount: 1,
  },
  categories: [
    'options_structure',
    'market_breadth_flows',
    'sector_rotation',
    'macro_cross_asset_regime',
    'stock_research_data',
    'backtest_data_availability',
  ],
  capabilities: [
    {
      capabilityId: 'options.chain',
      label: 'Options structure and gamma inputs',
      category: 'options_structure',
      status: 'entitlement_required',
      sourceLabel: 'Options Lab readiness boundary',
      reason: 'Display is blocked until entitlement evidence is verified.',
      freshness: 'Unavailable until rights are proven.',
    },
    {
      capabilityId: 'market.breadth_flows',
      label: 'Market breadth and flows',
      category: 'market_breadth_flows',
      status: 'degraded',
      sourceLabel: 'Market readiness registry',
      reason: 'Breadth context exists with incomplete source authority.',
      freshness: 'Partial and delayed.',
    },
    {
      capabilityId: 'market.positioning_flows',
      label: 'Flows and positioning',
      category: 'market_breadth_flows',
      status: 'configured_missing',
      sourceLabel: 'Market readiness registry',
      reason: 'Positioning inputs are not configured for product use.',
      freshness: 'Missing provider configuration.',
    },
    {
      capabilityId: 'market.sector_rotation',
      label: 'Sector and industry leadership',
      category: 'sector_rotation',
      status: 'degraded',
      sourceLabel: 'Market rotation readiness registry',
      reason: 'Membership and quote authority remain incomplete.',
      freshness: 'Partial and delayed.',
    },
    {
      capabilityId: 'macro.cross_asset_regime',
      label: 'Macro and cross-asset inputs',
      category: 'macro_cross_asset_regime',
      status: 'live',
      sourceLabel: 'Macro readiness registry',
      reason: 'Stored macro rows are available for observation.',
      freshness: 'Stored or delayed observations.',
    },
    {
      capabilityId: 'stock.news',
      label: 'Stock news and catalysts',
      category: 'stock_research_data',
      status: 'configured_missing',
      sourceLabel: 'Single-stock readiness registry',
      reason: 'Catalyst evidence is not consistently configured.',
      freshness: 'Missing or inconsistent across symbols.',
    },
    {
      capabilityId: 'backtest.data_availability',
      label: 'Backtest data availability',
      category: 'backtest_data_availability',
      status: 'not_implemented',
      sourceLabel: 'Backtest readiness registry',
      reason: 'Point-in-time lineage remains incomplete.',
      freshness: 'Research-useful, but lineage is incomplete.',
    },
  ],
});

const regimeReadModelPayload = () => ({
  consumerSafe: true,
  noAdvice: true,
  contractVersion: 'market_regime_read_model_v1',
  sourceEvidenceContractVersion: 'market_regime_evidence_pack_v1',
  status: 'ok',
  market: 'US',
  symbols: ['SPY', 'QQQ', 'AAPL', 'MSFT'],
  benchmarkSymbol: 'SPY',
  growthProxySymbol: 'QQQ',
  regime: {
    label: 'risk_on_confirming',
    status: 'ok',
    source: 'deterministic_evidence_fields',
  },
  productSummary: 'Risk-on confirming evidence is currently present because local evidence fields align.',
  evidenceCards: [
    {
      id: 'benchmark_trend',
      title: 'Benchmark Trend',
      status: 'positive',
      severity: 'info',
      headline: 'Benchmark trend evidence is positive.',
      metrics: [{ label: 'return20d', value: 0.12 }],
      reasons: ['Benchmark local trend fields are aligned.'],
      sourceFields: ['evidence.benchmarkTrend.return20d'],
      consumerSafe: true,
    },
    {
      id: 'growth_risk_proxy',
      title: 'Growth Risk Proxy',
      status: 'positive',
      severity: 'info',
      headline: 'Growth proxy evidence is positive.',
      metrics: [{ label: 'relativeReturn20d', value: 0.03 }],
      reasons: ['Growth proxy relative return is available.'],
      sourceFields: ['evidence.growthRiskProxy.relativeReturn20d'],
      consumerSafe: true,
    },
    {
      id: 'breadth',
      title: 'Breadth',
      status: 'positive',
      severity: 'info',
      headline: 'Breadth evidence is broad.',
      metrics: [{ label: 'percentAboveMa20', value: 1 }],
      reasons: ['Breadth evidence is available.'],
      sourceFields: ['evidence.breadthProxy.percentAboveMa20'],
      consumerSafe: true,
    },
    {
      id: 'volatility',
      title: 'Volatility',
      status: 'neutral',
      severity: 'info',
      headline: 'Volatility evidence is normal.',
      metrics: [{ label: 'volatilityState', value: 'normal' }],
      reasons: ['Volatility evidence is available.'],
      sourceFields: ['evidence.volatilityProxy.volatilityState'],
      consumerSafe: true,
    },
    {
      id: 'quote_snapshot',
      title: 'Quote Snapshot',
      status: 'positive',
      severity: 'info',
      headline: 'Quote snapshot evidence is available.',
      metrics: [{ label: 'availabilityState', value: 'available' }],
      reasons: ['Quote snapshot rows are available.'],
      sourceFields: ['quoteSnapshotEvidence.availabilityState'],
      consumerSafe: true,
    },
    {
      id: 'data_quality',
      title: 'Data Quality',
      status: 'positive',
      severity: 'info',
      headline: 'Data quality is product-ready.',
      metrics: [{ label: 'missingDataFamilies', value: [] }],
      reasons: ['No missing evidence families are present.'],
      sourceFields: ['missingDataFamilies'],
      consumerSafe: true,
    },
  ],
  symbolContext: [],
  dataQuality: {
    adjustedCoverageState: 'available',
    ohlcvCoverage: { state: 'available', requiredBars: 60, availableSymbols: ['SPY', 'QQQ', 'AAPL', 'MSFT'], missingSymbols: [] },
    quoteSnapshotCoverage: { state: 'available', availabilityState: 'available', freshnessState: 'fresh', availableSymbols: ['SPY', 'QQQ', 'AAPL', 'MSFT'], missingSymbols: [], staleSymbols: [] },
    missingDataFamilies: [],
    blockedProductSurfaces: [],
    nextOperatorAction: 'Market regime read model is available from local evidence inputs.',
    failClosedReasons: [],
  },
  readiness: {
    label: 'product_ready',
    status: 'ok',
    missingDataFamilies: [],
    blockedProductSurfaces: [],
    nextOperatorAction: 'Market regime read model is available from local evidence inputs.',
  },
  surfaceHints: [{ surface: 'market_overview', readOnly: true }],
  missingDataFamilies: [],
  blockedProductSurfaces: [],
  nextOperatorAction: 'Market regime read model is available from local evidence inputs.',
  networkCallsEnabled: false,
  mutationEnabled: false,
  providerCallsEnabled: false,
});

const allMissingMarketRegimeCapabilitiesPayload = () => ({
  contractVersion: 'professional_data_capability_registry_v1',
  consumerSafe: true,
  summary: {
    totalCapabilities: 6,
    liveCount: 0,
    degradedCount: 0,
    entitlementRequiredCount: 0,
    configuredMissingCount: 5,
    notImplementedCount: 1,
  },
  categories: [
    'options_structure',
    'market_breadth_flows',
    'sector_rotation',
    'macro_cross_asset_regime',
  ],
  capabilities: [
    {
      capabilityId: 'market.breadth',
      label: 'Breadth',
      category: 'market_breadth_flows',
      status: 'configured_missing',
      sourceLabel: 'Readiness registry',
      reason: 'Breadth provider is not configured.',
      freshness: 'No timestamp.',
    },
    {
      capabilityId: 'market.sector_leadership',
      label: 'Sector leadership',
      category: 'sector_rotation',
      status: 'configured_missing',
      sourceLabel: 'Readiness registry',
      reason: 'Sector leadership provider is not configured.',
      freshness: 'No timestamp.',
    },
    {
      capabilityId: 'market.volatility_regime',
      label: 'Volatility regime',
      category: 'macro_cross_asset_regime',
      status: 'configured_missing',
      sourceLabel: 'Readiness registry',
      reason: 'Volatility input provider is not configured.',
      freshness: 'No timestamp.',
    },
    {
      capabilityId: 'options.gamma_inputs',
      label: 'Gamma inputs',
      category: 'options_structure',
      status: 'not_implemented',
      sourceLabel: 'Options Lab readiness boundary',
      reason: 'Gamma inputs are not available for market regime use.',
      freshness: 'No timestamp.',
    },
    {
      capabilityId: 'market.positioning_flows',
      label: 'Positioning flows',
      category: 'market_breadth_flows',
      status: 'configured_missing',
      sourceLabel: 'Readiness registry',
      reason: 'Positioning provider is not configured.',
      freshness: 'No timestamp.',
    },
    {
      capabilityId: 'macro.cross_asset_inputs',
      label: 'Macro cross-asset inputs',
      category: 'macro_cross_asset_regime',
      status: 'configured_missing',
      sourceLabel: 'Readiness registry',
      reason: 'Macro input provider is not configured.',
      freshness: 'No timestamp.',
    },
  ],
});

const macroPanel = () => ({
  ...panel('MacroIndicatorsCard', 'US10Y', 'US 10Y'),
  items: [
    ...panel('MacroIndicatorsCard', 'US10Y').items,
    {
      symbol: 'FEDFUNDS',
      label: 'Fed Funds',
      value: null,
      unit: '%',
      changePct: null,
      riskDirection: 'neutral' as const,
      trend: [],
    },
  ],
});

const officialMacroPanel = () => ({
  ...panel('MacroIndicatorsCard', 'VIX', 'VIX'),
  source: 'mixed',
  sourceLabel: 'Official macro mix',
  freshness: 'cached' as const,
  isFallback: false,
  items: [
    {
      symbol: 'VIX',
      label: 'VIX',
      value: 18.4,
      unit: 'pts',
      changePct: -1.2,
      riskDirection: 'decreasing' as const,
      trend: [19.2, 18.9, 18.4],
      source: 'fred',
      sourceLabel: 'FRED VIXCLS',
      sourceType: 'official_public',
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      updatedAt: '2026-05-21T10:00:05+08:00',
      asOf: '2026-05-21T10:00:00+08:00',
      freshness: 'cached' as const,
      isFallback: false,
      isPartial: false,
      isUnavailable: false,
      observationOnly: false,
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      sourceAuthorityReason: null,
      sourceAuthorityRouteRejected: false,
      routeRejectedReasonCodes: [],
      officialSeriesId: 'VIXCLS',
      officialObservationDate: '2026-05-20',
      officialAsOf: '2026-05-20',
    },
    {
      symbol: 'FEDFUNDS',
      label: 'Fed Funds',
      value: 5.33,
      unit: '%',
      changePct: 0,
      riskDirection: 'neutral' as const,
      trend: [5.33, 5.33, 5.33],
      source: 'fred',
      sourceLabel: 'FRED DFF',
      sourceType: 'official_public',
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      updatedAt: '2026-05-21T10:00:05+08:00',
      asOf: '2026-05-21T10:00:00+08:00',
      freshness: 'cached' as const,
      isFallback: false,
      isPartial: false,
      isUnavailable: false,
      observationOnly: false,
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      sourceAuthorityReason: null,
      sourceAuthorityRouteRejected: false,
      routeRejectedReasonCodes: [],
      officialSeriesId: 'DFF',
      officialObservationDate: '2026-05-20',
      officialAsOf: '2026-05-20',
    },
    {
      symbol: 'CREDIT',
      label: 'Credit spreads',
      value: 3.75,
      unit: '%',
      changePct: 0.1,
      riskDirection: 'increasing' as const,
      trend: [3.6, 3.7, 3.75],
      source: 'fred',
      sourceLabel: 'FRED BAMLH0A0HYM2',
      sourceType: 'official_public',
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      updatedAt: '2026-05-21T10:00:05+08:00',
      asOf: '2026-05-21T10:00:00+08:00',
      freshness: 'cached' as const,
      isFallback: false,
      isPartial: false,
      isUnavailable: false,
      observationOnly: true,
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: false,
      sourceAuthorityReason: null,
      sourceAuthorityRouteRejected: false,
      routeRejectedReasonCodes: [],
      officialSeriesId: 'BAMLH0A0HYM2',
      officialObservationDate: '2026-05-20',
      officialAsOf: '2026-05-20',
    },
    {
      symbol: 'US2Y',
      label: 'US 2Y',
      value: null,
      unit: '%',
      changePct: null,
      riskDirection: 'neutral' as const,
      trend: [],
      source: 'yahoo',
      sourceLabel: 'Yahoo proxy',
      sourceType: 'public_proxy',
      sourceTier: 'unofficial_public_api',
      trustLevel: 'usable_with_caution',
      updatedAt: '2026-05-21T10:00:05+08:00',
      asOf: '2026-05-21T10:00:00+08:00',
      freshness: 'fallback' as const,
      isFallback: true,
      isPartial: true,
      isUnavailable: false,
      observationOnly: false,
      sourceAuthorityAllowed: false,
      scoreContributionAllowed: false,
      sourceAuthorityReason: 'proxy_context_only',
      sourceAuthorityRouteRejected: false,
      routeRejectedReasonCodes: [],
      officialSeriesId: 'DGS2',
      officialObservationDate: null,
      officialAsOf: null,
    },
    {
      symbol: 'US30Y',
      label: 'US 30Y',
      value: null,
      unit: '%',
      changePct: null,
      riskDirection: 'neutral' as const,
      trend: [],
      source: 'unavailable',
      sourceLabel: 'Not returned',
      sourceType: 'unavailable',
      sourceTier: 'unavailable',
      trustLevel: 'unavailable',
      updatedAt: '2026-05-21T10:00:05+08:00',
      asOf: '2026-05-21T10:00:00+08:00',
      freshness: 'unavailable' as const,
      isFallback: false,
      isPartial: false,
      isUnavailable: true,
      observationOnly: false,
      sourceAuthorityAllowed: false,
      scoreContributionAllowed: false,
      sourceAuthorityReason: 'source_authority_router_rejected',
      sourceAuthorityRouteRejected: true,
      routeRejectedReasonCodes: ['provider_forbidden_for_use_case'],
      officialSeriesId: 'DGS30',
      officialObservationDate: null,
      officialAsOf: null,
    },
  ],
});

const cryptoPanel = () => ({
  panelName: 'CryptoCard',
  lastRefreshAt: '2026-04-29T10:00:00',
  status: 'success' as const,
  logSessionId: 'crypto-log',
  items: [
    {
      symbol: 'BTC',
      label: 'Bitcoin',
      value: 76837.04,
      unit: 'USD',
      changePct: 1.47,
      riskDirection: 'decreasing' as const,
      trend: [74211, 75120, 76003, 76837.04],
      hoverDetails: ['24H +1.47%', '7D +3.22%'],
    },
  ],
});

const cryptoFullPanel = () => ({
  ...cryptoPanel(),
  source: 'binance',
  sourceLabel: 'Binance',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'delayed' as const,
  isFallback: false,
  isRefreshing: false,
  items: [
    ...cryptoPanel().items,
    {
      symbol: 'ETH',
      label: 'Ethereum',
      value: 3120,
      unit: 'USD',
      changePct: -0.4,
      riskDirection: 'increasing' as const,
      trend: [3090, 3148, 3120],
      hoverDetails: ['24H -0.40%'],
    },
    {
      symbol: 'SOL',
      label: 'Solana',
      value: 143.2,
      unit: 'USD',
      changePct: 1.8,
      riskDirection: 'decreasing' as const,
      trend: [139, 141, 143.2],
      hoverDetails: ['24H +1.80%'],
    },
    {
      symbol: 'BNB',
      label: 'BNB',
      value: 590,
      unit: 'USD',
      changePct: 0.3,
      riskDirection: 'decreasing' as const,
      trend: [584, 588, 590],
      hoverDetails: ['24H +0.30%'],
    },
    {
      symbol: 'BTC_FUNDING',
      label: 'BTC Funding',
      value: 0.012,
      unit: '%',
      changePct: 0.012,
      riskDirection: 'increasing' as const,
      trend: [0.01, 0.012],
      hoverDetails: ['Binance Futures'],
    },
  ],
});

const usBreadthPanel = () => denseQuotePanel('UsBreadthCard', [
  quoteItem('SECTORS_UP', 'Sectors Up', 8, 0),
  quoteItem('SECTORS_DOWN', 'Sectors Down', 3, 0),
  quoteItem('STRONGEST_SECTOR', 'Strongest XLK', 1.8, 1.8),
  quoteItem('WEAKEST_SECTOR', 'Weakest XLE', -0.6, -0.6),
  quoteItem('RSP_SPY', 'RSP vs SPY', -0.4, -0.4),
  quoteItem('IWM_SPY', 'IWM vs SPY', -0.8, -0.8),
], 'yahoo');

const polygonUsBreadthPanel = () => ({
  ...denseQuotePanel('UsBreadthCard', [
    {
      ...quoteItem('ADVANCERS', '上涨家数', 2874, 0, 'polygon'),
      unit: '家',
      sourceLabel: 'Polygon grouped daily',
      sourceType: 'authorized_computed',
      sourceTier: 'authorized_market_data',
      trustLevel: 'score_grade_partial',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
    },
    {
      ...quoteItem('DECLINERS', '下跌家数', 1986, 0, 'polygon'),
      unit: '家',
      sourceLabel: 'Polygon grouped daily',
      sourceType: 'authorized_computed',
      sourceTier: 'authorized_market_data',
      trustLevel: 'score_grade_partial',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
    },
    {
      ...quoteItem('UNCHANGED', '平盘家数', 214, 0, 'polygon'),
      unit: '家',
      sourceLabel: 'Polygon grouped daily',
      sourceType: 'authorized_computed',
      sourceTier: 'authorized_market_data',
      trustLevel: 'score_grade_partial',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
    },
    {
      ...quoteItem('ADVANCE_DECLINE_RATIO', '上涨/下跌比', 1.45, 0, 'polygon'),
      unit: '',
      sourceLabel: 'Polygon grouped daily',
      sourceType: 'authorized_computed',
      sourceTier: 'authorized_market_data',
      trustLevel: 'score_grade_partial',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
    },
  ], 'polygon'),
  source: 'computed_from_authorized_polygon_grouped_daily',
  sourceLabel: 'Polygon grouped daily',
  sourceType: 'authorized_computed',
  freshness: 'delayed' as const,
  isFallback: false,
  isPartial: true,
  breadthClaimType: 'computed_from_authorized_eod_grouped_daily',
  officialExchangePublishedBreadth: false,
  fulfilledMetrics: ['ADVANCERS', 'DECLINERS', 'UNCHANGED', 'ADVANCE_DECLINE_RATIO'],
  missingMetrics: ['NEW_HIGHS', 'NEW_LOWS', 'HIGH_LOW_RATIO'],
  metricCoverageRatio: 4 / 7,
  sourceAuthorityAllowed: true,
  scoreContributionAllowed: true,
  broadMarketClaimAllowed: true,
  reasonCodes: ['polygon_high_low_history_unavailable'],
  providerHealth: {
    provider: 'polygon',
    status: 'partial' as const,
    asOf: '2026-05-21',
    updatedAt: '2026-05-22T04:00:00Z',
    latencyMs: 120,
    isFallback: false,
    isStale: false,
    isRefreshing: false,
    sourceLabel: 'Polygon grouped daily',
  },
  warning: 'High/low breadth unavailable.',
});

const officialUsBreadthPanel = () => ({
  ...denseQuotePanel('UsBreadthCard', [
    {
      ...quoteItem('ADVANCERS', '上涨家数', 4123, 0, 'nyse_official_breadth'),
      unit: '家',
      sourceLabel: 'NYSE Official Breadth Cache',
      sourceType: 'official_public',
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      observationOnly: false,
    },
    {
      ...quoteItem('DECLINERS', '下跌家数', 1834, 0, 'nyse_official_breadth'),
      unit: '家',
      sourceLabel: 'NYSE Official Breadth Cache',
      sourceType: 'official_public',
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      observationOnly: false,
    },
    {
      ...quoteItem('UNCHANGED', '平盘家数', 201, 0, 'nyse_official_breadth'),
      unit: '家',
      sourceLabel: 'NYSE Official Breadth Cache',
      sourceType: 'official_public',
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      observationOnly: false,
    },
    {
      ...quoteItem('ADVANCE_DECLINE_RATIO', '上涨/下跌比', 2.25, 0, 'nyse_official_breadth'),
      unit: '',
      sourceLabel: 'NYSE Official Breadth Cache',
      sourceType: 'official_public',
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      observationOnly: false,
    },
    {
      ...quoteItem('NEW_HIGHS', '新高家数', 318, 0, 'nyse_official_breadth'),
      unit: '家',
      sourceLabel: 'NYSE Official Breadth Cache',
      sourceType: 'official_public',
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      observationOnly: false,
    },
    {
      ...quoteItem('NEW_LOWS', '新低家数', 42, 0, 'nyse_official_breadth'),
      unit: '家',
      sourceLabel: 'NYSE Official Breadth Cache',
      sourceType: 'official_public',
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      observationOnly: false,
    },
    {
      ...quoteItem('HIGH_LOW_RATIO', '新高/新低比', 7.57, 0, 'nyse_official_breadth'),
      unit: '',
      sourceLabel: 'NYSE Official Breadth Cache',
      sourceType: 'official_public',
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      observationOnly: false,
    },
  ], 'nyse_official_breadth'),
  source: 'nyse_official_breadth',
  sourceLabel: 'NYSE Official Breadth Cache',
  sourceType: 'official_public',
  sourceTier: 'official_public',
  trustLevel: 'reliable',
  freshness: 'delayed' as const,
  isFallback: false,
  isPartial: false,
  officialExchangePublishedBreadth: true,
  fulfilledMetrics: ['ADVANCERS', 'DECLINERS', 'UNCHANGED', 'ADVANCE_DECLINE_RATIO', 'NEW_HIGHS', 'NEW_LOWS', 'HIGH_LOW_RATIO'],
  missingMetrics: [],
  metricCoverageRatio: 1,
  sourceAuthorityAllowed: true,
  scoreContributionAllowed: true,
  broadMarketClaimAllowed: true,
  observationOnly: false,
  routeRejectedReasonCodes: [],
});

const usBreadthUnavailablePanel = () => ({
  ...snapshotPanel('UsBreadthCard', 'SECTOR_PROXY_UNAVAILABLE', '数据暂不可用'),
  source: 'unavailable',
  sourceLabel: '未接入',
  freshness: 'fallback' as const,
  isFallback: true,
  items: [
    {
      ...snapshotPanel('UsBreadthCard', 'SECTOR_PROXY_UNAVAILABLE', '数据暂不可用').items[0],
      value: null,
      changePct: null,
      unit: '',
      source: 'unavailable',
      sourceLabel: '未接入',
      freshness: 'fallback' as const,
      isFallback: true,
      hoverDetails: ['Sector ETF proxy 暂不可用'],
    },
  ],
});

const cryptoLivePanel = () => ({
  ...cryptoFullPanel(),
  source: 'binance_ws',
  sourceLabel: 'Binance WS',
  updatedAt: '2026-04-29T10:00:01',
  asOf: '2026-04-29T10:00:01',
  freshness: 'live' as const,
  items: [
    {
      symbol: 'BTC',
      label: 'Bitcoin',
      value: 77001.25,
      unit: 'USD',
      changePct: 0.42,
      riskDirection: 'decreasing' as const,
      trend: [76837.04, 77001.25],
      source: 'binance_ws',
      sourceLabel: 'Binance WS',
      freshness: 'live' as const,
      isFallback: false,
    },
    {
      symbol: 'ETH',
      label: 'Ethereum',
      value: 3201,
      unit: 'USD',
      changePct: 0.8,
      riskDirection: 'decreasing' as const,
      trend: [3120, 3201],
      source: 'binance_ws',
      sourceLabel: 'Binance WS',
      freshness: 'live' as const,
      isFallback: false,
    },
    {
      symbol: 'BNB',
      label: 'BNB',
      value: 600,
      unit: 'USD',
      changePct: 0.5,
      riskDirection: 'decreasing' as const,
      trend: [590, 600],
      source: 'binance_ws',
      sourceLabel: 'Binance WS',
      freshness: 'live' as const,
      isFallback: false,
    },
  ],
});

const cryptoFallbackPanel = () => ({
  panelName: 'CryptoCard',
  lastRefreshAt: '2026-04-29T10:00:00',
  status: 'failure' as const,
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'fallback' as const,
  isFallback: true,
  isRefreshing: true,
  warning: '正在获取实时加密货币行情，当前显示备用快照',
  items: [
    {
      symbol: 'BTC',
      label: 'Bitcoin',
      value: 75800,
      unit: 'USD',
      changePct: -0.2,
      riskDirection: 'increasing' as const,
      trend: [75220, 75640, 75800],
      source: 'fallback',
      sourceLabel: '备用数据',
      freshness: 'fallback' as const,
      isFallback: true,
      warning: '正在获取实时加密货币行情，当前显示备用快照',
    },
    {
      symbol: 'ETH',
      label: 'Ethereum',
      value: 3120,
      unit: 'USD',
      changePct: -0.4,
      riskDirection: 'increasing' as const,
      trend: [3090, 3148, 3120],
      source: 'fallback',
      sourceLabel: '备用数据',
      freshness: 'fallback' as const,
      isFallback: true,
      warning: '正在获取实时加密货币行情，当前显示备用快照',
    },
    {
      symbol: 'BNB',
      label: 'BNB',
      value: 590,
      unit: 'USD',
      changePct: 0.3,
      riskDirection: 'decreasing' as const,
      trend: [584, 588, 590],
      source: 'fallback',
      sourceLabel: '备用数据',
      freshness: 'fallback' as const,
      isFallback: true,
      warning: '正在获取实时加密货币行情，当前显示备用快照',
    },
  ],
});

const cryptoPartialRefreshingPanel = () => ({
  ...cryptoFallbackPanel(),
  status: 'success' as const,
  source: 'mixed',
  sourceLabel: 'Binance + Cache',
  sourceType: 'mixed',
  freshness: 'stale' as const,
  isFallback: false,
  isStale: true,
  isRefreshing: true,
  providerHealth: {
    provider: 'binance',
    status: 'partial' as const,
    asOf: '2026-04-29T10:00:00',
    updatedAt: '2026-04-29T10:00:00',
    latencyMs: 480,
    errorSummary: 'background refresh in progress',
    isFallback: false,
    isStale: true,
    isRefreshing: true,
    sourceLabel: 'Binance partial snapshot',
    card: 'CryptoCard',
  },
  warning: '后台刷新进行中，当前显示部分可用快照',
  items: [
    {
      ...cryptoFallbackPanel().items[0],
      source: 'binance',
      sourceLabel: 'Binance',
      freshness: 'stale' as const,
      isFallback: false,
      isStale: true,
      isRefreshing: true,
    },
    {
      ...cryptoFallbackPanel().items[1],
      source: 'cache',
      sourceLabel: 'Recent Cache',
      freshness: 'stale' as const,
      isFallback: false,
      isStale: true,
      isRefreshing: true,
    },
    {
      ...cryptoFallbackPanel().items[2],
      source: 'cache',
      sourceLabel: 'Recent Cache',
      freshness: 'stale' as const,
      isFallback: false,
      isStale: true,
      isRefreshing: true,
    },
  ],
});

const sentimentPanel = () => ({
  panelName: 'MarketSentimentCard',
  lastRefreshAt: '2026-04-29T10:00:00',
  status: 'success' as const,
  logSessionId: 'sentiment-log',
  items: [
    {
      symbol: 'FGI',
      label: 'Fear & Greed',
      value: 26,
      unit: 'score',
      changePct: -7,
      riskDirection: 'increasing' as const,
      trend: [42, 38, 33, 26],
      hoverDetails: ['24H -7.00%', '7D -18.00%'],
    },
    {
      symbol: 'SOURCE',
      label: 'Provider',
      value: 26,
      unit: 'fallback',
      changePct: null,
      riskDirection: 'neutral' as const,
      trend: [26, 26],
    },
  ],
  errorMessage: '更新失败：已回退到最近一次有效数据',
});

const snapshotPanel = (panelName: string, symbol: string, label = symbol) => ({
  panelName,
  lastRefreshAt: '2026-04-29T10:00:00',
  status: 'success' as const,
  logSessionId: `${panelName}-log`,
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'fallback' as const,
  isFallback: true,
  warning: '备用示例数据，不代表当前行情',
  items: [
    {
      symbol,
      label,
      value: 100,
      unit: 'pts',
      changePct: 1.2,
      riskDirection: 'decreasing' as const,
      trend: [96, 98, 100],
      source: 'fallback',
      sourceLabel: '备用数据',
      updatedAt: '2026-04-29T10:00:00',
      asOf: '2026-04-29T10:00:00',
      freshness: 'fallback' as const,
      isFallback: true,
      warning: '备用示例数据，不代表当前行情',
      hoverDetails: ['fallback snapshot'],
    },
  ],
});

const temperaturePayload = () => ({
  source: 'computed',
  sourceLabel: '系统计算',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'cached' as const,
  isFallback: false,
  isStale: false,
  confidence: 0.82,
  reliableInputCount: 12,
  requiredReliableInputCount: 5,
  reliablePanelCount: 5,
  requiredReliablePanelCount: 3,
  fallbackInputCount: 2,
  excludedInputCount: 2,
  isReliable: true,
  temperatureAvailable: true,
  disabledReason: null,
  unavailableReason: null,
  insufficientReliableInputs: false,
  trustLevel: 'reliable',
  sourceTier: 'unofficial_public_api',
  conclusionAllowed: true,
  marketActionabilityFrame: {
    contractVersion: 'market_intelligence_actionability_v1',
    verdict: 'observe_only',
    confidence: {
      value: 0.41,
      label: 'low',
      capReasons: ['observation_only'],
    },
    evidenceCoverage: {
      scoreGradeCount: 2,
      observationOnlyCount: 1,
      missingCount: 0,
      totalCount: 3,
    },
    missingEvidence: [],
    regimeContext: {
      primaryRegime: 'risk_on_liquidity_expansion',
      liquidityImpulse: 'expanding_liquidity',
      rotationPosture: 'leading',
      contradictionCount: 1,
      freshnessFloor: 'delayed',
    },
    sourceAuthority: 'observationOnly',
    freshness: 'delayed',
    noAdviceBoundary: true,
    nextResearchStep: '继续确认流动性是否保持扩张',
    debugRef: 'market:temperature:actionability',
  },
  marketIntelligenceEvidenceFrame: {
    contractVersion: 'market_intelligence_evidence_v1',
    frameState: 'observe_only',
    evidenceCoverage: {
      scoreGradeCount: 3,
      observationOnlyCount: 2,
      missingCount: 0,
      totalCount: 5,
    },
    regimeEvidence: {
      domain: 'macro',
      state: 'score_grade',
      freshness: 'delayed',
      primaryRegime: 'risk_on_liquidity_expansion',
      blockingReasons: [],
    },
    liquidityEvidence: {
      domain: 'liquidity',
      state: 'observation_only',
      freshness: 'delayed',
      likelyDestination: 'broad_equities',
      blockingReasons: ['observation_only'],
    },
    rotationEvidence: {
      domain: 'rotation',
      state: 'observation_only',
      freshness: 'delayed',
      leadingThemeCount: 2,
      blockingReasons: ['observation_only'],
    },
    breadthEvidence: {
      domain: 'breadth',
      state: 'score_grade',
      freshness: 'delayed',
      breadthValue: 1.7,
      blockingReasons: [],
    },
    scannerContextEvidence: {
      domain: 'scanner_context',
      state: 'score_grade',
      freshness: 'delayed',
      readinessState: 'ready',
      noAdviceBoundary: true,
      blockingReasons: [],
    },
    missingEvidence: [],
    blockingReasons: ['observation_only'],
    sourceAuthority: 'observationOnly',
    freshness: 'delayed',
    nextEvidenceNeeded: [],
    noAdviceBoundary: true,
    debugRef: 'market:temperature:evidence',
  },
  regimeSummary: regimeSummaryPayload(),
  marketRegimeSynthesis: regimeSynthesisPayload(),
  marketDecisionSemantics: marketDecisionSemanticsPayload(),
  scores: {
    overall: { value: 62, label: '偏暖', trend: 'improving' as const, description: '风险偏好改善，但宏观压力仍需关注。' },
    usRiskAppetite: { value: 68, label: '偏暖', trend: 'improving' as const, description: '美股指数与风险情绪同步改善。' },
    cnMoneyEffect: { value: 55, label: '中性', trend: 'stable' as const, description: '指数表现尚可，但市场宽度一般。' },
    macroPressure: { value: 58, label: '中性偏高', trend: 'rising' as const, description: '美元与利率走强。' },
    liquidity: { value: 52, label: '中性', trend: 'stable' as const, description: '资金环境整体平稳。' },
  },
});

const marketDecisionSemanticsPayload = () => ({
  version: 'market_decision_semantics_v1',
  posture: 'offensive',
  postureConfidence: {
    value: 64,
    label: 'medium',
    capReasons: ['counter_evidence_present'],
  },
  exposureBias: 'risk_on_watch',
  directionReadiness: {
    status: 'direction_ready',
    confidenceLabel: 'medium',
    scoreGradePillars: {
      count: 3,
      items: [
        { pillar: 'official_macro_rates_volatility', label: 'Official macro/rates/volatility', reasonCode: 'score_grade_evidence' },
        { pillar: 'liquidity_conditions', label: 'Liquidity/conditions', reasonCode: 'score_grade_evidence' },
        { pillar: 'rotation_or_risk_participation', label: 'Rotation/risk participation', reasonCode: 'score_grade_evidence' },
      ],
    },
    observationOnlyPillars: { count: 0, items: [] },
    missingPillars: { count: 0, items: [] },
    blockingReasons: [],
    claimBoundaries: [
      { claim: 'market_direction_readiness_context', allowed: true, reasonCode: 'direction_ready' },
      { claim: 'trade_instruction', allowed: false, reasonCode: 'not_investment_advice' },
      { claim: 'allocation_or_suitability_guidance', allowed: false, reasonCode: 'not_investment_advice' },
    ],
    notInvestmentAdvice: true,
  },
  styleTilts: [
    { tilt: 'liquidity_beta_watch', label: 'Liquidity beta watch', detail: 'Risk-on regime and expanding liquidity align, but this remains watch-only.' },
    { tilt: 'rotation_leadership_watch', label: 'Rotation leadership watch', detail: 'Score-grade rotation leadership is confirming the posture watch.' },
  ],
  confirmationSignals: [
    { signal: 'regime_alignment', detail: 'Primary regime should remain score-grade.' },
    { signal: 'liquidity_alignment', detail: 'Liquidity impulse should remain expanding.' },
  ],
  invalidationTriggers: [
    { trigger: 'liquidity_stops_expanding', detail: 'Remove the risk-on watch if liquidity turns mixed or contracting.' },
  ],
  counterEvidence: [
    { surface: 'market_regime_synthesis', key: 'rates:US10Y', label: 'US10Y', detail: 'Rates pressure remains a contradiction.' },
  ],
  dataGaps: [
    { surface: 'liquidity_impulse_synthesis', key: 'official:fed_liquidity', label: 'Fed liquidity', reason: 'missing_scoring_evidence' },
  ],
  claimBoundaries: [
    { claim: 'observational_posture_watch', allowed: true, reasonCode: 'watch_only_language', detail: 'Only observational posture watch language is allowed.' },
    { claim: 'direct_trade_action', allowed: false, reasonCode: 'not_investment_advice', detail: 'No execution language.' },
    { claim: 'position_size_guidance', allowed: false, reasonCode: 'not_investment_advice', detail: 'No sizing language.' },
  ],
  notInvestmentAdvice: true,
});

const insufficientMarketDecisionSemanticsPayload = () => ({
  ...marketDecisionSemanticsPayload(),
  posture: 'data_insufficient',
  postureConfidence: {
    value: 18,
    label: 'insufficient',
    capReasons: ['missing_scoring_pillars', 'proxy_or_observation_only_evidence'],
  },
  exposureBias: 'no_bias_data_insufficient',
  directionReadiness: {
    status: 'data_insufficient',
    confidenceLabel: 'insufficient',
    scoreGradePillars: { count: 0, items: [] },
    observationOnlyPillars: {
      count: 2,
      items: [
        { pillar: 'official_macro_rates_volatility', label: 'Official macro/rates/volatility', reasonCode: 'fallback_or_proxy_evidence' },
        { pillar: 'rotation_or_risk_participation', label: 'Rotation/risk participation', reasonCode: 'observation_only_evidence' },
      ],
    },
    missingPillars: {
      count: 1,
      items: [
        { pillar: 'liquidity_conditions', label: 'Liquidity/conditions', reasonCode: 'missing_scoring_evidence' },
      ],
    },
    blockingReasons: [
      'no_meaningful_score_grade_pillars',
      'fallback_proxy_or_observation_only_evidence_present',
    ],
    claimBoundaries: [
      { claim: 'market_direction_readiness_context', allowed: false, reasonCode: 'data_insufficient' },
      { claim: 'trade_instruction', allowed: false, reasonCode: 'not_investment_advice' },
      { claim: 'allocation_or_suitability_guidance', allowed: false, reasonCode: 'not_investment_advice' },
    ],
    notInvestmentAdvice: true,
  },
  styleTilts: [],
  confirmationSignals: [],
  invalidationTriggers: [],
  counterEvidence: [],
  dataGaps: [
    { surface: 'market_regime_synthesis', key: 'crypto:BTC', label: 'BTC', reason: 'observation_only_discount' },
  ],
  claimBoundaries: [
    { claim: 'observational_posture_watch', allowed: false, reasonCode: 'insufficient_score_grade_evidence', detail: 'No posture watch is supportable.' },
    { claim: 'direct_trade_action', allowed: false, reasonCode: 'not_investment_advice', detail: 'No execution language.' },
    { claim: 'position_size_guidance', allowed: false, reasonCode: 'not_investment_advice', detail: 'No sizing language.' },
  ],
});

const regimeSynthesisPayload = () => ({
  contractVersion: 'market_regime_synthesis_research_v1',
  primaryRegime: 'risk_on_liquidity_expansion',
  secondaryRegimes: ['goldilocks_soft_landing'],
  regimeScores: {
    risk_on_liquidity_expansion: 0.72,
    goldilocks_soft_landing: 0.44,
  },
  regimeLabel: 'Risk-supportive liquidity expansion',
  regimePosture: 'risk_supportive',
  evidenceFamilies: [
    {
      key: 'marketOverview',
      label: 'Market overview',
      state: 'supported',
      pillars: ['risk_appetite', 'rates_pressure', 'volatility_stress', 'crypto_risk_beta'],
      evidenceCount: 5,
      supportiveCount: 3,
      contradictoryCount: 2,
      missingCount: 0,
      freshness: 'cached',
      observationOnly: true,
    },
    {
      key: 'breadth',
      label: 'Breadth',
      state: 'missing',
      pillars: ['breadth_health'],
      evidenceCount: 1,
      supportiveCount: 0,
      contradictoryCount: 0,
      missingCount: 1,
      freshness: 'unavailable',
      observationOnly: true,
    },
  ],
  supportiveEvidence: [
    {
      key: 'indices:SPX',
      label: '标普500',
      family: 'marketOverview',
      pillar: 'risk_appetite',
      direction: 'positive',
      freshness: 'cached',
      observationOnly: true,
    },
    {
      key: 'volatility:VIX',
      label: 'VIX',
      family: 'marketOverview',
      pillar: 'volatility_stress',
      direction: 'negative',
      freshness: 'cached',
      observationOnly: true,
    },
  ],
  contradictoryEvidence: [
    {
      key: 'rates:US10Y',
      label: '美国10年期国债收益率',
      family: 'marketOverview',
      pillar: 'rates_pressure',
      reason: 'contradictory_evidence',
      observationOnly: true,
    },
  ],
  missingEvidence: [
    {
      key: 'breadth:CN',
      label: 'A股宽度',
      family: 'breadth',
      pillar: 'breadth_health',
      reason: 'missing_evidence',
      observationOnly: true,
    },
  ],
  confidenceCap: {
    value: 0.58,
    label: 'medium',
    reasons: ['contradictory_evidence', 'missing_evidence'],
  },
  observationBoundary: {
    observationOnly: true,
    decisionGrade: false,
    sourceAuthorityAllowed: false,
    scoreContributionAllowed: false,
    consumerActionBoundary: 'no_advice',
    notInvestmentAdvice: true,
    detail: 'Research synthesis only; evidence is not promoted into execution or personalized direction.',
  },
  researchNextSteps: [
    {
      key: 'review_contradictions',
      label: 'Review contradictory evidence',
      detail: 'Compare the conflicting families before treating one regime as dominant.',
    },
    {
      key: 'fill_missing_evidence',
      label: 'Fill missing evidence families',
      detail: 'Re-check breadth before raising confidence.',
    },
  ],
  generatedAt: '2026-06-16T02:00:00Z',
  freshness: 'cached',
  liquidityImpulse: 0.31,
  riskAppetite: 0.58,
  ratesPressure: -0.14,
  dollarPressure: -0.18,
  volatilityStress: -0.36,
  cryptoRiskBeta: 0.42,
  breadthHealth: 0.16,
  chinaRiskAppetite: 0.08,
  rotationQuality: 0.02,
  confidence: 0.66,
  confidenceLabel: 'medium',
  topDrivers: [
    {
      key: 'indices:SPX',
      label: '标普500',
      pillar: 'risk_appetite',
      direction: 'positive',
      signal: 0.58,
      weight: 0.94,
      impact: 0.54,
      source: 'sina',
      sourceTier: 'official_public',
      trustLevel: 'high',
      freshness: 'cached',
      observationOnly: false,
      scoreContributionAllowed: true,
      discountReasons: [],
    },
    {
      key: 'volatility:VIX',
      label: 'VIX',
      pillar: 'volatility_stress',
      direction: 'negative',
      signal: -0.42,
      weight: 0.91,
      impact: 0.49,
      source: 'fred',
      sourceTier: 'official_public',
      trustLevel: 'high',
      freshness: 'cached',
      observationOnly: false,
      scoreContributionAllowed: true,
      discountReasons: [],
    },
    {
      key: 'crypto:BTC',
      label: '比特币',
      pillar: 'crypto_risk_beta',
      direction: 'positive',
      signal: 0.39,
      weight: 0.67,
      impact: 0.33,
      source: 'binance',
      sourceTier: 'exchange_public',
      trustLevel: 'usable',
      freshness: 'delayed',
      observationOnly: false,
      scoreContributionAllowed: true,
      discountReasons: ['freshness_discount'],
    },
  ],
  counterEvidence: [
    {
      key: 'rates:US10Y',
      label: '美国10年期国债收益率',
      pillar: 'rates_pressure',
      signal: 0.24,
      expectedDirection: 'negative',
      reason: 'conflicts_with_primary_regime',
    },
    {
      key: 'fx:DXY',
      label: '美元指数',
      pillar: 'dollar_pressure',
      signal: 0.18,
      expectedDirection: 'negative',
      reason: 'conflicts_with_primary_regime',
    },
  ],
  dataGaps: [
    {
      key: 'breadth:CN',
      label: 'A股宽度',
      pillar: 'breadth_health',
      reason: 'missing_scoring_evidence',
      source: 'unavailable',
      sourceTier: 'unavailable',
      trustLevel: 'unavailable',
      freshness: 'unavailable',
      observationOnly: false,
      scoreContributionAllowed: false,
      degradationReason: 'provider_unavailable',
    },
    {
      key: 'rotation:small_caps',
      label: '小盘股轮动',
      pillar: 'rotation_leadership',
      reason: 'freshness_discount',
      source: 'snapshot',
      sourceTier: 'cache_snapshot',
      trustLevel: 'weak',
      freshness: 'stale',
      observationOnly: false,
      scoreContributionAllowed: true,
      degradationReason: 'stale',
    },
  ],
  narrativeBullets: ['Risk appetite is improving but rates pressure remains a live contradiction.'],
  evidenceQuality: {
    scoringEvidenceCount: 6,
    scoringPillarCount: 5,
    discountedEvidenceCount: 1,
    dataGapCount: 2,
  },
  notInvestmentAdvice: true,
});

const regimeSummaryPayload = () => ({
  label: '偏观察的风险偏好修复',
  title: '风险偏好修复仍以观察为主',
  diagnosticOnly: true,
  observationOnly: true,
  sourceAuthorityAllowed: false,
  scoreContributionAllowed: false,
  notInvestmentAdvice: true,
  drivers: [
    {
      key: 'watch:liquidity_impulse',
      label: '流动性改善',
      detail: '流动性脉冲仍在扩张，支撑风险偏好修复观察。',
    },
    {
      key: 'watch:growth_rotation',
      label: '成长轮动延续',
      detail: '成长风格仍有延续，但暂不升级为方向性结论。',
    },
  ],
  blockers: [
    {
      key: 'gap:cn_breadth',
      label: 'A股宽度确认不足',
      detail: '宽度尚未回到评分级覆盖，观察结论仍需保守。',
    },
  ],
  contradictions: [
    {
      key: 'contra:rates_pressure',
      label: '美国10年期国债收益率',
      detail: '利率压力仍在，对风险偏好修复形成反证。',
    },
  ],
  confidence: {
    value: 0.62,
    label: 'medium',
  },
  confidenceCaps: [
    {
      key: 'partial_context_only',
      label: '仅限观察上下文',
      detail: '当前仅能作为观察性市场状态摘要。',
    },
  ],
  nextWatchItems: [
    {
      key: 'watch:small_caps_follow_through',
      label: '小盘轮动延续',
      detail: '继续观察小盘与高贝塔品种是否同步跟进。',
    },
  ],
  explanation: '流动性与成长轮动仍支持风险偏好修复观察，但宽度确认与利率反证尚未解除。',
});

const briefingPayload = () => ({
  source: 'computed',
  sourceLabel: '系统计算',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'cached' as const,
  isFallback: false,
  isStale: false,
  confidence: 0.82,
  reliableInputCount: 12,
  fallbackInputCount: 2,
  excludedInputCount: 2,
  isReliable: true,
  items: [
    { title: '美股风险偏好偏暖', message: '主要指数走强，VIX 回落。', severity: 'positive' as const, category: 'us', confidence: 0.82 },
    { title: 'A股赚钱效应中性', message: '指数上涨但上涨家数占比一般。', severity: 'neutral' as const, category: 'cn', confidence: 0.82 },
    { title: '宏观压力仍需关注', message: '美债收益率和美元指数同步走强。', severity: 'warning' as const, category: 'macro', confidence: 0.82 },
  ],
});

const unreliableTemperaturePayload = () => ({
  source: 'fallback',
  sourceLabel: '最近可用数据',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'fallback' as const,
  isFallback: true,
  warning: '数据待补',
  confidence: 0,
  reliableInputCount: 0,
  requiredReliableInputCount: 5,
  reliablePanelCount: 0,
  requiredReliablePanelCount: 3,
  fallbackInputCount: 18,
  excludedInputCount: 18,
  isReliable: false,
  temperatureAvailable: false,
  disabledReason: 'insufficient_reliable_inputs',
  unavailableReason: 'insufficient_reliable_inputs',
  insufficientReliableInputs: true,
  trustLevel: 'unavailable',
  sourceTier: 'static_fallback',
  conclusionAllowed: false,
  marketActionabilityFrame: {
    contractVersion: 'market_intelligence_actionability_v1',
    verdict: 'insufficient',
    confidence: {
      value: 0.12,
      label: 'insufficient',
      capReasons: ['missing_required_evidence', 'fallback_evidence'],
    },
    evidenceCoverage: {
      scoreGradeCount: 0,
      observationOnlyCount: 0,
      missingCount: 4,
      totalCount: 3,
    },
    missingEvidence: ['macro', 'liquidity', 'technical', 'freshness'],
    regimeContext: {
      primaryRegime: 'data_insufficient',
      liquidityImpulse: 'data_insufficient',
      rotationPosture: 'unavailable',
      contradictionCount: 0,
      freshnessFloor: 'fallback',
    },
    sourceAuthority: 'unavailable',
    freshness: 'fallback',
    noAdviceBoundary: true,
    nextResearchStep: '等待更高授权流动性证据',
    debugRef: 'market:temperature:actionability',
  },
  marketIntelligenceEvidenceFrame: {
    contractVersion: 'market_intelligence_evidence_v1',
    frameState: 'insufficient',
    evidenceCoverage: {
      scoreGradeCount: 0,
      observationOnlyCount: 0,
      missingCount: 5,
      totalCount: 5,
    },
    regimeEvidence: {
      domain: 'macro',
      state: 'missing',
      freshness: 'fallback',
      blockingReasons: ['missing_required_evidence'],
    },
    liquidityEvidence: {
      domain: 'liquidity',
      state: 'missing',
      freshness: 'fallback',
      blockingReasons: ['missing_required_evidence'],
    },
    rotationEvidence: {
      domain: 'rotation',
      state: 'missing',
      freshness: 'fallback',
      blockingReasons: ['missing_required_evidence'],
    },
    breadthEvidence: {
      domain: 'breadth',
      state: 'missing',
      freshness: 'fallback',
      blockingReasons: ['missing_required_evidence'],
    },
    scannerContextEvidence: {
      domain: 'scanner_context',
      state: 'missing',
      freshness: 'fallback',
      readinessState: 'insufficient',
      noAdviceBoundary: true,
      blockingReasons: ['missing_required_evidence'],
    },
    missingEvidence: ['macro', 'liquidity', 'rotation', 'scanner_context', 'freshness'],
    blockingReasons: ['missing_required_evidence', 'fallback_evidence'],
    sourceAuthority: 'unavailable',
    freshness: 'fallback',
    nextEvidenceNeeded: ['补充宏观证据', '补充流动性证据'],
    noAdviceBoundary: true,
    debugRef: 'market:temperature:evidence',
  },
  marketDecisionSemantics: insufficientMarketDecisionSemanticsPayload(),
  marketRegimeSynthesis: {
    primaryRegime: 'data_insufficient',
    secondaryRegimes: [],
    regimeScores: {},
    liquidityImpulse: 0,
    riskAppetite: 0,
    ratesPressure: 0,
    dollarPressure: 0,
    volatilityStress: 0,
    cryptoRiskBeta: 0,
    breadthHealth: 0,
    chinaRiskAppetite: 0,
    rotationQuality: 0,
    confidence: 0.22,
    confidenceLabel: 'insufficient',
    topDrivers: [
      {
        key: 'indices:SPX',
        label: '标普500',
        pillar: 'risk_appetite',
        direction: 'positive',
        signal: 0.18,
        weight: 0.35,
        impact: 0.08,
        source: 'fallback',
        sourceTier: 'static_fallback',
        trustLevel: 'weak',
        freshness: 'fallback',
        observationOnly: false,
        scoreContributionAllowed: false,
        discountReasons: ['source_tier_discount'],
      },
    ],
    counterEvidence: [],
    dataGaps: [
      {
        key: 'breadth:CN',
        label: 'A股宽度',
        pillar: 'breadth_health',
        reason: 'missing_scoring_evidence',
        source: 'unavailable',
        sourceTier: 'unavailable',
        trustLevel: 'unavailable',
        freshness: 'unavailable',
        observationOnly: false,
        scoreContributionAllowed: false,
        degradationReason: 'provider_unavailable',
      },
      {
        key: 'crypto:BTC',
        label: '比特币',
        pillar: 'crypto_risk_beta',
        reason: 'observation_only_discount',
        source: 'coinbase',
        sourceTier: 'exchange_public',
        trustLevel: 'usable',
        freshness: 'delayed',
        observationOnly: true,
        scoreContributionAllowed: false,
        degradationReason: 'observation_only',
      },
    ],
    narrativeBullets: ['Coverage remains below scoring threshold.'],
    evidenceQuality: {
      scoringEvidenceCount: 2,
      scoringPillarCount: 2,
      discountedEvidenceCount: 2,
      dataGapCount: 2,
    },
    notInvestmentAdvice: true,
  },
  scores: {
    overall: { value: 50, label: '数据不足', trend: 'stable' as const, description: '数据待补' },
    usRiskAppetite: { value: 50, label: '数据不足', trend: 'stable' as const, description: '数据待补' },
    cnMoneyEffect: { value: 50, label: '数据不足', trend: 'stable' as const, description: '数据待补' },
    macroPressure: { value: 50, label: '数据不足', trend: 'stable' as const, description: '数据待补' },
    liquidity: { value: 50, label: '数据不足', trend: 'stable' as const, description: '数据待补' },
  },
});

const limitedRealTemperaturePayload = () => ({
  ...unreliableTemperaturePayload(),
  source: 'mixed',
  sourceLabel: '多来源',
  freshness: 'stale' as const,
  isFallback: false,
  confidence: 0.32,
  reliableInputCount: 2,
  reliablePanelCount: 2,
  fallbackInputCount: 10,
  excludedInputCount: 10,
  trustLevel: 'weak',
  sourceTier: 'unofficial_public_api',
});

const unreliableBriefingPayload = () => ({
  source: 'fallback',
  sourceLabel: '最近可用数据',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'fallback' as const,
  isFallback: true,
  warning: '当前关键数据不足，暂不生成强市场判断。',
  confidence: 0,
  reliableInputCount: 0,
  fallbackInputCount: 18,
  excludedInputCount: 18,
  isReliable: false,
  items: [
    { title: '当前关键数据不足', message: '当前关键数据不足，暂不生成强市场判断。', severity: 'warning' as const, category: 'risk', confidence: 0 },
    { title: '评分已暂停', message: '最近可用数据仅保留市场结构观察，不参与市场温度评分。', severity: 'neutral' as const, category: 'risk', confidence: 0 },
  ],
});

const futuresPayload = () => ({
  source: 'fallback',
  sourceLabel: '最近可用数据',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'fallback' as const,
  isFallback: true,
  warning: '已使用最近一次可用数据，不代表当前实时行情。',
  items: [
    { name: '纳指期货', symbol: 'NQ', value: 18420.5, change: 65.2, changePercent: 0.35, market: 'US', session: 'premarket', sparkline: [18320, 18380, 18420.5], source: 'fallback', sourceLabel: '最近可用数据', freshness: 'fallback' as const, isFallback: true, warning: '已使用最近一次可用数据，不代表当前实时行情。' },
    { name: '富时A50期货', symbol: 'CN00Y', value: 12580, change: 38, changePercent: 0.3, market: 'CN', session: 'day', sparkline: [12420, 12542, 12580], source: 'fallback', sourceLabel: '最近可用数据', freshness: 'fallback' as const, isFallback: true, warning: '已使用最近一次可用数据，不代表当前实时行情。' },
  ],
});

const cnShortSentimentPayload = () => ({
  source: 'fallback',
  sourceLabel: '最近可用数据',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'fallback' as const,
  isFallback: true,
  warning: '已使用最近一次可用数据，不代表当前实时行情。',
  sentimentScore: 64,
  summary: '涨停家数占优，炸板率可控，短线情绪偏暖。',
  metrics: {
    limitUpCount: 68,
    limitDownCount: 18,
    failedLimitUpRate: 24.5,
    maxConsecutiveLimitUps: 5,
    yesterdayLimitUpPerformance: 2.8,
    firstBoardCount: 42,
    secondBoardCount: 12,
    highBoardCount: 6,
    twentyCmLimitUpCount: 9,
    stRiskLevel: 'normal',
  },
});

const MARKET_OVERVIEW_LKG_STORAGE_KEY = 'wolfystock.marketOverview.lastKnownGood.v1';

function localSnapshotPayload(overrides: Record<string, unknown> = {}) {
  return {
    schemaVersion: 1,
    savedAt: '2026-05-04T10:15:00.000Z',
    payload: {
      indices: {
        ...panel('IndexTrendsCard', 'SPX', 'S&P 500'),
        source: 'local-cache',
        sourceLabel: 'Local Cache',
        freshness: 'stale' as const,
        isStale: true,
        isFromSnapshot: true,
        lastSuccessfulAt: '2026-05-04T10:00:00+08:00',
        items: [
          {
            ...quoteItem('SPX', 'S&P 500', 5111.11, 0.31),
            source: 'local-cache',
            sourceLabel: 'Local Cache',
            freshness: 'stale' as const,
            isStale: true,
          },
        ],
      },
      crypto: {
        ...cryptoFullPanel(),
        source: 'local-cache',
        sourceLabel: 'Local Cache',
        freshness: 'stale' as const,
        isStale: true,
      },
      temperature: temperaturePayload(),
      briefing: briefingPayload(),
      futures: futuresPayload(),
      cnShortSentiment: cnShortSentimentPayload(),
      ...overrides,
    },
  };
}

function expandPendingDataSourceSection() {
  const button = screen.queryByRole('button', { name: /待接入真实数据源/i });
  if (!button) {
    return;
  }
  if (button.getAttribute('aria-expanded') !== 'true') {
    fireEvent.click(button);
  }
}

function getRowCardOrder(rowId: string): string[] {
  const row = document.querySelector(`[data-row-id="${rowId}"]`);
  return Array.from(row?.querySelectorAll('[data-testid^="market-overview-card-"]') || [])
    .map((node) => node.getAttribute('data-testid')?.replace('market-overview-card-', '') || '');
}

function getRowIds(): string[] {
  return Array.from(document.querySelectorAll('[data-testid="market-overview-row"]'))
    .map((node) => node.getAttribute('data-row-id') || '');
}

function getSideCardOrder(): string[] {
  return Array.from(screen.getByTestId('market-overview-side-rail').querySelectorAll('[data-testid^="market-overview-card-"]'))
    .map((node) => node.getAttribute('data-testid')?.replace('market-overview-card-', '') || '');
}

function getPulseText(): string {
  return screen.getByTestId('market-overview-hero-ribbon').textContent || '';
}

function expandMarketDecisionDetails() {
  const disclosure = screen.getByTestId('market-decision-debug-details');
  const toggle = within(disclosure).getByRole('button', { name: /展开 技术细节/i });
  fireEvent.click(toggle);
  return disclosure;
}

function expandMarketEvidenceDetails() {
  const disclosure = screen.getByTestId('market-overview-evidence-disclosure');
  const toggle = within(disclosure).getByRole('button', { name: /展开 数据说明|Expand 数据说明/i });
  fireEvent.click(toggle);
  return disclosure;
}

async function expectCoverageSummarySettled() {
  await waitFor(() => {
    expect(screen.getByTestId('market-overview-coverage-summary')).toHaveTextContent(/数据可用|最近更新：/);
  });
}

function expandMarketOverviewDataDiagnostics() {
  const disclosure = screen.getByTestId('market-overview-data-diagnostics-disclosure');
  const toggle = within(disclosure).getByRole('button', { name: /展开 查看数据诊断/i });
  fireEvent.click(toggle);
  return disclosure;
}

function renderMarketOverviewWithLanguage(language: 'zh' | 'en') {
  window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, language);
  return render(
    <UiLanguageProvider>
      <MarketOverviewPage />
    </UiLanguageProvider>,
  );
}

function renderMarketOverviewWorkbench() {
  return render(
    <UiLanguageProvider>
      <MarketOverviewWorkbench
        heading={<TerminalPageHeading data-testid="market-overview-page-heading" title="市场总览" />}
        panels={localSnapshotPayload().payload}
        loading={false}
        localSnapshotSavedAt="2026-04-29T10:00:00"
        refreshErrorCount={0}
        refreshingPanel={null}
        cryptoRealtimeStatus="snapshot"
        isCnShortSentimentBootstrapping={false}
        onRefreshPanel={() => {}}
      />
    </UiLanguageProvider>,
  );
}

function renderMarketOverviewWorkbenchWithProps(overrides: Partial<Parameters<typeof MarketOverviewWorkbench>[0]> = {}) {
  const basePanels = localSnapshotPayload().payload;
  return render(
    <UiLanguageProvider>
      <MarketOverviewWorkbench
        heading={<TerminalPageHeading data-testid="market-overview-page-heading" title="市场总览" />}
        panels={basePanels}
        loading={false}
        localSnapshotSavedAt="2026-04-29T10:00:00"
        refreshErrorCount={0}
        refreshingPanel={null}
        cryptoRealtimeStatus="snapshot"
        isCnShortSentimentBootstrapping={false}
        onRefreshPanel={() => {}}
        {...overrides}
      />
    </UiLanguageProvider>,
  );
}

const primaryMarketPanelRequests = [
  marketOverviewApi.getIndices,
  marketOverviewApi.getVolatility,
  marketApi.getCrypto,
  marketApi.getSentiment,
  marketOverviewApi.getFundsFlow,
  marketApi.getCnIndices,
  marketApi.getRates,
  marketApi.getFxCommodities,
  marketApi.getTemperature,
  marketApi.getMarketBriefing,
] as const;

const firstStagedMarketPanelRequests = [
  marketOverviewApi.getMacro,
  marketApi.getCnBreadth,
  marketApi.getUsBreadth,
] as const;

const secondStagedMarketPanelRequests = [
  marketApi.getCnFlows,
  marketApi.getSectorRotation,
  marketApi.getFutures,
  marketApi.getCnShortSentiment,
] as const;

const allMarketPanelRequests = [
  ...primaryMarketPanelRequests,
  ...firstStagedMarketPanelRequests,
  ...secondStagedMarketPanelRequests,
] as const;

function rejectAllMarketOverviewPanels(message = 'market overview unavailable') {
  allMarketPanelRequests.forEach((request) => {
    vi.mocked(request).mockRejectedValue(new Error(message));
  });
}

const FIRST_STAGE_PANEL_DELAY_MS = 250;
const SECOND_STAGE_PANEL_DELAY_MS = 650;
const SECOND_STAGE_PANEL_DELTA_MS = SECOND_STAGE_PANEL_DELAY_MS - FIRST_STAGE_PANEL_DELAY_MS;
const CRYPTO_PENDING_FALLBACK_DELAY_MS = 3_100;
const FAST_MARKET_POLL_INTERVAL_MS = 45_000;
const MEDIUM_MARKET_POLL_INTERVAL_MS = 120_000;
const SLOW_MARKET_POLL_INTERVAL_MS = 300_000;
const AUTO_REVALIDATE_OBSERVATION_WINDOW_MS = 5_000;

type MarketPanelRequestMock = (typeof allMarketPanelRequests)[number];
type DeferredPromise<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
};

function createDeferredPromise<T>(): DeferredPromise<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
}

function countMarketPanelRequests(): number {
  return allMarketPanelRequests.reduce((total, request) => total + vi.mocked(request).mock.calls.length, 0);
}

function expectMarketPanelRequestsCalledOnce(requests: readonly MarketPanelRequestMock[]): void {
  requests.forEach((request) => {
    expect(request).toHaveBeenCalledTimes(1);
  });
}

function expectMarketPanelRequestsNotCalled(requests: readonly MarketPanelRequestMock[]): void {
  requests.forEach((request) => {
    expect(request).not.toHaveBeenCalled();
  });
}

async function advanceMarketOverviewTimersByTime(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

async function advanceFirstStagedMarketPanelRequests(): Promise<void> {
  await advanceMarketOverviewTimersByTime(FIRST_STAGE_PANEL_DELAY_MS);
}

async function advanceSecondStagedMarketPanelRequests(): Promise<void> {
  await advanceMarketOverviewTimersByTime(SECOND_STAGE_PANEL_DELTA_MS);
}

async function drainStagedMarketPanelRequests(): Promise<void> {
  await advanceMarketOverviewTimersByTime(SECOND_STAGE_PANEL_DELAY_MS);
}

async function advanceAutoRevalidateObservationWindow(): Promise<void> {
  await advanceMarketOverviewTimersByTime(AUTO_REVALIDATE_OBSERVATION_WINDOW_MS);
}

async function flushMarketOverviewMicrotasks(turns = 1): Promise<void> {
  await act(async () => {
    for (let index = 0; index < turns; index += 1) {
      await Promise.resolve();
    }
  });
}

async function runMarketOverviewAsyncStep(callback: () => void): Promise<void> {
  await act(async () => {
    callback();
    await Promise.resolve();
  });
}

function getMarketOverviewIntervalCallback(
  setIntervalSpy: { mock: { calls: Array<[TimerHandler, number | undefined, ...unknown[]]> } },
  delayMs: number,
): () => void {
  const callback = setIntervalSpy.mock.calls.find(([, delay]) => delay === delayMs)?.[0];
  expect(typeof callback).toBe('function');
  return callback as () => void;
}

describe('MarketOverviewPage', () => {
  let originalClipboard: Navigator['clipboard'] | undefined;
  const writeTextMock = vi.fn().mockResolvedValue(undefined);

  class MockEventSource {
    static instances: MockEventSource[] = [];
    onmessage: ((event: MessageEvent) => void) | null = null;
    onerror: (() => void) | null = null;
    closed = false;
    url: string;

    constructor(url: string) {
      this.url = url;
      MockEventSource.instances.push(this);
    }

    close() {
      this.closed = true;
    }

    emit(payload: unknown) {
      this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent);
    }

    error() {
      this.onerror?.();
    }
  }

  beforeEach(() => {
    window.localStorage.clear();
    MockEventSource.instances = [];
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: true,
      canReadProviders: true,
    });
    vi.stubGlobal('EventSource', MockEventSource);
    originalClipboard = navigator.clipboard;
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: writeTextMock,
      },
    });
    writeTextMock.mockClear();
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValue(panel('IndexTrendsCard', 'SPX'));
    vi.mocked(marketOverviewApi.getVolatility).mockResolvedValue(panel('VolatilityCard', 'VIX'));
    vi.mocked(marketOverviewApi.getFundsFlow).mockResolvedValue(panel('FundsFlowCard', 'ETF'));
    vi.mocked(marketOverviewApi.getMacro).mockResolvedValue(macroPanel());
    vi.mocked(marketApi.getCrypto).mockResolvedValue(cryptoPanel());
    vi.mocked(marketApi.getSentiment).mockResolvedValue(sentimentPanel());
    vi.mocked(marketApi.getCnIndices).mockResolvedValue({
      ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
      items: [
        ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300').items,
        {
          symbol: '000001.SH',
          label: '上证指数',
          value: 3120.55,
          unit: 'pts',
          changePct: 0.39,
          riskDirection: 'decreasing' as const,
          trend: [3098, 3105, 3120.55],
          source: 'fallback',
          sourceLabel: '备用数据',
          updatedAt: '2026-04-29T10:00:00',
          asOf: '2026-04-29T10:00:00',
          freshness: 'fallback' as const,
          isFallback: true,
          warning: '备用示例数据，不代表当前行情',
        },
      ],
    });
    vi.mocked(marketApi.getCnBreadth).mockResolvedValue(snapshotPanel('ChinaBreadthCard', 'BREADTH', '赚钱效应'));
    vi.mocked(marketApi.getCnFlows).mockResolvedValue(snapshotPanel('ChinaFlowsCard', 'NORTHBOUND', '北向资金'));
    vi.mocked(marketApi.getSectorRotation).mockResolvedValue(snapshotPanel('SectorRotationCard', 'AI', 'AI / 算力'));
    vi.mocked(marketApi.getUsBreadth).mockResolvedValue(usBreadthPanel());
    vi.mocked(marketApi.getRates).mockResolvedValue({
      ...snapshotPanel('RatesCard', 'US10Y', 'US 10Y'),
      items: [
        ...snapshotPanel('RatesCard', 'US10Y', 'US 10Y').items,
        {
          symbol: 'CN10Y',
          label: '中国10年国债收益率',
          value: 2.35,
          unit: '%',
          changePct: -1.5,
          riskDirection: 'decreasing' as const,
          trend: [2.4, 2.37, 2.35],
          source: 'fallback',
          sourceLabel: '备用数据',
          freshness: 'fallback' as const,
          isFallback: true,
          warning: '备用示例数据，不代表当前行情',
        },
      ],
    });
    vi.mocked(marketApi.getFxCommodities).mockResolvedValue({
      ...snapshotPanel('FxCommoditiesCard', 'DXY', 'DXY'),
      items: [
        ...snapshotPanel('FxCommoditiesCard', 'DXY', 'DXY').items,
        {
          symbol: 'USDCNH',
          label: 'USD/CNH',
          value: 7.24,
          unit: '',
          changePct: 0.2,
          riskDirection: 'increasing' as const,
          trend: [7.2, 7.22, 7.24],
          source: 'fallback',
          sourceLabel: '备用数据',
          freshness: 'fallback' as const,
          isFallback: true,
          warning: '备用示例数据，不代表当前行情',
        },
      ],
    });
    vi.mocked(marketApi.getTemperature).mockResolvedValue(temperaturePayload());
    vi.mocked(marketApi.getMarketBriefing).mockResolvedValue(briefingPayload());
    vi.mocked(marketApi.getFutures).mockResolvedValue(futuresPayload());
    vi.mocked(marketApi.getCnShortSentiment).mockResolvedValue(cnShortSentimentPayload());
    vi.mocked(marketApi.getRegimeReadModel).mockResolvedValue(regimeReadModelPayload());
    vi.mocked(marketApi.getDataReadiness).mockResolvedValue(officialRiskReadinessPayload());
    vi.mocked(marketApi.getProfessionalDataCapabilities).mockResolvedValue(professionalDataCapabilitiesPayload());
  });

  it('renders compact official risk source readiness labels without raw enums or advice wording', async () => {
    vi.mocked(marketApi.getDataReadiness).mockResolvedValueOnce(officialRiskReadinessPayload());

    render(createElement(MarketOverviewPage));
    expandMarketOverviewDataDiagnostics();

    const strip = await screen.findByTestId('market-overview-source-readiness');
    const boundary = await screen.findByTestId('market-overview-evidence-boundary');
    await waitFor(() => expect(strip).toHaveTextContent('官方风险源部分可用'));
    expect(strip).toHaveTextContent('VIX可用');
    expect(strip).toHaveTextContent('利率待更新');
    expect(strip).toHaveTextContent('Fed流动性待补');
    expect(boundary).toHaveTextContent('证据边界待确认');
    expect(boundary).toHaveTextContent('市场总览待补');
    expect(boundary).toHaveTextContent('广度待补');
    expect(strip.textContent || '').not.toMatch(
      /authorized|unavailable|partial|unknown|fallbackUsed|providerConfigured|sourceAuthority|scoreContributionAllowed|provider|runtime|credential/i,
    );
    expect(strip.textContent || '').not.toMatch(/buy|sell|hold|target price|stop-loss|position sizing|买入|卖出|持有|目标价|止损|仓位|建仓|加仓|减仓/i);
    expect(boundary.textContent || '').not.toMatch(/provider|cache|debug|raw|sourceAuthority|buy|sell|买入|卖出|目标价|止损|仓位/i);
  });

  it('renders market regime read model evidence cards and data quality without advice copy', async () => {
    vi.mocked(marketApi.getRegimeReadModel).mockResolvedValueOnce(regimeReadModelPayload());

    render(createElement(MarketOverviewPage));
    expandMarketOverviewDataDiagnostics();

    const surface = await screen.findByTestId('market-regime-read-model-surface');
    await waitFor(() => expect(surface).toHaveTextContent('risk_on_confirming'));
    expect(surface).toHaveTextContent('产品可用');
    expect(surface).toHaveTextContent('Risk-on confirming evidence is currently present');
    expect(within(surface).getByTestId('market-regime-evidence-card-benchmark_trend')).toHaveTextContent('Benchmark Trend');
    expect(within(surface).getByTestId('market-regime-evidence-card-growth_risk_proxy')).toHaveTextContent('Growth Risk Context');
    expect(within(surface).getByTestId('market-regime-evidence-card-breadth')).toHaveTextContent('Breadth');
    expect(within(surface).getByTestId('market-regime-evidence-card-volatility')).toHaveTextContent('Volatility');
    expect(within(surface).getByTestId('market-regime-evidence-card-quote_snapshot')).toHaveTextContent('Quote Snapshot');
    expect(within(surface).getByTestId('market-regime-evidence-card-data_quality')).toHaveTextContent('Data Quality');
    expect(surface).toHaveTextContent('复权序列: 可用');
    expect(surface).toHaveTextContent('价格走势: 可用');
    expect(surface).toHaveTextContent('报价状态: 可用');
    expect(surface.textContent || '').not.toMatch(/buy|sell|hold|recommendation|target price|enter|exit|long|short|加仓|减仓|买入|卖出|持有|目标价|推荐/i);
  });

  it('keeps blocked market regime read model states visible', async () => {
    vi.mocked(marketApi.getRegimeReadModel).mockResolvedValueOnce({
      ...regimeReadModelPayload(),
      status: 'partial',
      regime: {
        label: 'insufficient_data',
        status: 'partial',
        source: 'deterministic_evidence_fields',
      },
      productSummary: 'Market regime evidence is blocked by missing local source families or product surface blockers.',
      missingDataFamilies: ['adjusted_prices', 'quote_snapshot'],
      blockedProductSurfaces: ['Market Overview'],
      readiness: {
        label: 'blocked',
        status: 'blocked',
        missingDataFamilies: ['adjusted_prices', 'quote_snapshot'],
        blockedProductSurfaces: ['Market Overview'],
        nextOperatorAction: 'Resolve missing local evidence families or blocked product surfaces, then rerun.',
      },
      dataQuality: {
        ...regimeReadModelPayload().dataQuality,
        adjustedCoverageState: 'missing',
        ohlcvCoverage: { state: 'partial', requiredBars: 60, availableSymbols: ['SPY'], missingSymbols: ['QQQ'] },
        quoteSnapshotCoverage: { state: 'partial', availabilityState: 'partial', freshnessState: 'unknown', availableSymbols: ['SPY'], missingSymbols: ['AAPL'], staleSymbols: [] },
        missingDataFamilies: ['adjusted_prices', 'quote_snapshot'],
        blockedProductSurfaces: ['Market Overview'],
      },
    });

    render(createElement(MarketOverviewPage));
    expandMarketOverviewDataDiagnostics();

    const surface = await screen.findByTestId('market-regime-read-model-surface');
    await waitFor(() => expect(surface).toHaveTextContent('数据不足'));
    expect(surface).toHaveTextContent('数据不足');
    expect(surface).toHaveTextContent('已阻断');
    expect(surface).toHaveTextContent('adjusted_prices、quote_snapshot');
    expect(surface).toHaveTextContent('Market Overview');
    expect(surface).toHaveTextContent('复权序列: 待补');
    expect(surface).toHaveTextContent('价格走势: 部分可用');
    expect(surface).toHaveTextContent('报价状态: 部分可用');
    expect(surface).not.toHaveTextContent('insufficient_data');
  });

  it('renders market overview evidence boundary states from readiness matrix without raw internals', async () => {
    vi.mocked(marketApi.getDataReadiness).mockResolvedValue({
      ...officialRiskReadinessPayload(),
      consumerEvidenceReadinessMatrix: {
        contractVersion: 'consumer_evidence_readiness_matrix_v1',
        diagnosticOnly: true,
        networkCallsEnabled: false,
        mutationEnabled: false,
        items: [
          {
            surface: 'market_overview',
            evidenceFamily: 'market_regime',
            requiredInputs: ['market overview read model', 'market breadth context', 'rotation context', 'macro context', 'liquidity context'],
            fulfilledInputs: ['market overview read model'],
            missingInputs: ['market breadth context'],
            staleInputs: ['rotation context'],
            blockedInputs: ['macro context'],
            observationOnlyInputs: ['liquidity context'],
            scoreGradeInputs: ['market overview read model'],
            readinessState: 'score_grade',
            confidenceCapReason: 'cap reason',
            sourceAuthorityReason: 'source authority reason',
            freshnessReason: 'freshness reason',
            nextDiagnostic: 'compare raw diagnostics',
            consumerSafeSummary: 'market overview summary',
          },
        ],
      },
    });

    render(createElement(MarketOverviewPage));
    expandMarketOverviewDataDiagnostics();

    const boundary = await screen.findByTestId('market-overview-evidence-boundary');
    await waitFor(() => expect(boundary).toHaveTextContent('证据可用'));
    expect(boundary).toHaveTextContent('市场总览读数可用');
    expect(boundary).toHaveTextContent('市场广度待补');
    expect(boundary).toHaveTextContent('板块轮动待更新');
    expect(boundary).toHaveTextContent('风险状态仅观察');
    expect(boundary).toHaveTextContent('下一步：补齐市场广度、宏观背景');
    expect(boundary.textContent || '').not.toMatch(
      /contractVersion|market_overview|market_regime|confidenceCapReason|sourceAuthority|freshnessReason|nextDiagnostic|consumerSafeSummary|provider|runtime|credential|cache|debug|raw|buy|sell|hold|target price|position sizing|买入|卖出|持有|目标价|止损|仓位/i,
    );
  });

  it('renders cross-asset driver readiness without fabricating market conclusions', async () => {
    vi.mocked(marketApi.getDataReadiness).mockResolvedValueOnce(officialRiskReadinessPayload());

    render(createElement(MarketOverviewPage));
    expandMarketOverviewDataDiagnostics();

    const strip = await screen.findByTestId('market-overview-cross-asset-readiness');
    await waitFor(() => expect(strip).toHaveTextContent('跨资产驱动部分可用'));
    expect(strip).toHaveTextContent('Equities/index trend: 可用 (SPY)');
    expect(strip).toHaveTextContent('Oil/energy: 待更新 (USO)');
    expect(strip).toHaveTextContent('Credit spreads: 未配置');
    expect(strip).toHaveTextContent('可用 1 · 待更新 1 · 历史不足 0 · 待补/未配置 1');
    expect(strip).toHaveTextContent('仅展示已配置输入与缓存状态；未返回的驱动不做方向推断。');
    expect(strip.textContent || '').not.toMatch(
      /risk-on|risk-off|inflation|recession|providerClass|providerName|providerAttempted|requiredProviderClass|sourceAuthorityRouter|endpointHost|apiKeyPresent|exceptionClass|exceptionChain|requestId|traceId|cacheKey|rawPayload|credential|token|env|buy|sell|hold|target price|stop-loss|position sizing|买入|卖出|持有|目标价|止损|仓位|建仓|加仓|减仓/i,
    );
  });

  it('renders the market regime readiness surface with consumer-safe category states', async () => {
    render(createElement(MarketOverviewPage));
    expandMarketOverviewDataDiagnostics();

    const surface = await screen.findByTestId('market-regime-readiness-surface');
    await waitFor(() => expect(surface).toHaveTextContent('Market regime data readiness'));

    expect(surface).toHaveTextContent('breadth');
    expect(surface).toHaveTextContent('degraded');
    expect(surface).toHaveTextContent('sector/industry leadership');
    expect(surface).toHaveTextContent('volatility/risk regime');
    expect(surface).toHaveTextContent('available');
    expect(surface).toHaveTextContent('options structure / gamma inputs');
    expect(surface).toHaveTextContent('entitlement required');
    expect(surface).toHaveTextContent('flows/positioning');
    expect(surface).toHaveTextContent('missing provider');
    expect(surface).toHaveTextContent('macro/cross-asset inputs');
    expect(surface).toHaveTextContent('no fabricated regime score');
    expect(surface).toHaveTextContent('no fake gamma or flow values');
    expect(surface.textContent || '').not.toMatch(
      /GEX|vanna|charm|providerClass|providerName|providerAttempted|requiredProviderClass|sourceAuthorityRouter|endpointHost|apiKeyPresent|exceptionClass|exceptionChain|requestId|traceId|cacheKey|rawPayload|credential|token|env/i,
    );
  });

  it('fails closed when market overview panels are unavailable instead of rendering local sample markets', async () => {
    rejectAllMarketOverviewPanels('providerClass requestId rawPayload unavailable');
    vi.mocked(marketApi.getProfessionalDataCapabilities).mockResolvedValueOnce(allMissingMarketRegimeCapabilitiesPayload());
    vi.mocked(marketApi.getDataReadiness).mockResolvedValueOnce({
      readinessStatus: 'missing',
      diagnosticOnly: true,
      providerRuntimeCalled: false,
      networkCallsEnabled: false,
      representativeSymbols: [],
      checks: [],
      officialRiskSourceReadiness: {
        bundleState: 'blocked',
        vix: { state: 'missing', freshness: 'unavailable' },
        rates: { state: 'missing', freshness: 'unavailable' },
        fedLiquidity: { state: 'blocked', freshness: 'unavailable' },
      },
      consumerEvidenceReadinessMatrix: {
        contractVersion: 'consumer_evidence_readiness_matrix_v1',
        diagnosticOnly: true,
        networkCallsEnabled: false,
        mutationEnabled: false,
        items: [
          {
            surface: 'market_overview',
            evidenceFamily: 'market_index',
            requiredInputs: ['index_quotes'],
            fulfilledInputs: [],
            missingInputs: ['index_quotes'],
            staleInputs: [],
            blockedInputs: [],
            observationOnlyInputs: [],
            scoreGradeInputs: [],
            readinessState: 'missing',
            confidenceCapReason: 'missing_required_evidence',
            sourceAuthorityReason: '',
            freshnessReason: '',
            nextDiagnostic: '',
            consumerSafeSummary: 'Market/index evidence is missing.',
          },
        ],
      },
      crossAssetDriverReadiness: {
        contractVersion: 'cross_asset_driver_readiness_v1',
        consumerSafe: true,
        diagnosticOnly: true,
        networkCallsEnabled: false,
        externalProviderCalls: false,
        mutationEnabled: false,
        supportedStates: ['available', 'missing', 'stale', 'insufficient_history', 'not_configured'],
        consumerSummary: 'Cross-asset inputs are readiness only.',
        summary: { totalDrivers: 0, availableCount: 0, missingCount: 0 },
        drivers: [],
      },
    });

    render(createElement(MarketOverviewPage));
    expandMarketOverviewDataDiagnostics();

    const failClosedPanel = await screen.findByTestId('market-overview-readiness-empty-panel');
    expect(failClosedPanel).toHaveTextContent('Market Overview 数据待补');
    expect(failClosedPanel).toHaveTextContent('market/index');
    expect(failClosedPanel).toHaveTextContent('sector/industry rotation');
    expect(failClosedPanel).toHaveTextContent('market breadth');
    expect(failClosedPanel).toHaveTextContent('macro/regime');
    expect(failClosedPanel).toHaveTextContent('cross-asset drivers');
    expect(failClosedPanel).toHaveTextContent('news/catalyst/regime evidence');
    expect(failClosedPanel).toHaveTextContent('historical OHLCV');
    expect(failClosedPanel).toHaveTextContent(/missing|not_configured|unavailable/);
    expect(failClosedPanel).toHaveTextContent('查看数据状态');
    expect(failClosedPanel).toHaveTextContent('前往数据设置');

    const pageText = document.body.textContent || '';
    expect(pageText).not.toMatch(/18420\.5|5238\.25|38980|12580|17712|75800|3120|涨停家数占优|炸板率可控|短线情绪偏暖/);
    expect(pageText).not.toMatch(/providerClass|requestId|rawPayload|apiKey|token|traceId|cacheKey/i);
    expect(pageText).not.toMatch(/buy|sell|hold|target price|stop-loss|position sizing|买入|卖出|持有|目标价|止损|仓位|建仓|加仓|减仓/i);
  });

  it('keeps all-missing provider state explicit across market regime categories', async () => {
    vi.mocked(marketApi.getDataReadiness).mockResolvedValueOnce({
      ...officialRiskReadinessPayload(),
      officialRiskSourceReadiness: {
        bundleState: 'blocked',
        vix: { state: 'blocked', freshness: 'unavailable' },
        rates: { state: 'blocked', freshness: 'unavailable' },
        fedLiquidity: { state: 'blocked', freshness: 'unavailable' },
      },
    });
    vi.mocked(marketApi.getProfessionalDataCapabilities).mockResolvedValueOnce(allMissingMarketRegimeCapabilitiesPayload());

    render(createElement(MarketOverviewPage));
    expandMarketOverviewDataDiagnostics();

    const surface = await screen.findByTestId('market-regime-readiness-surface');
    await waitFor(() => expect(surface).toHaveTextContent('missing provider'));
    expect(surface).toHaveTextContent('breadth');
    expect(surface).toHaveTextContent('sector/industry leadership');
    expect(surface).toHaveTextContent('volatility/risk regime');
    expect(surface).toHaveTextContent('flows/positioning');
    expect(surface).toHaveTextContent('macro/cross-asset inputs');
    expect(surface).toHaveTextContent('options structure / gamma inputs');
    expect(surface).toHaveTextContent('not available');
    expect(surface.textContent || '').not.toMatch(/buy|sell|target price|position sizing|买入|卖出|目标价|仓位/i);
  });

  it('renders stale freshness with a timestamp when market regime inputs include one', async () => {
    vi.mocked(marketApi.getProfessionalDataCapabilities).mockResolvedValueOnce({
      ...professionalDataCapabilitiesPayload(),
      capabilities: [
        ...professionalDataCapabilitiesPayload().capabilities,
        {
          capabilityId: 'market.volatility_regime',
          label: 'Volatility and risk regime',
          category: 'macro_cross_asset_regime',
          status: 'degraded',
          sourceLabel: 'Risk readiness registry',
          reason: 'Volatility risk rows are delayed.',
          freshness: 'stale',
          asOf: '2026-06-22T13:45:00Z',
        } as never,
      ],
    } as never);

    render(createElement(MarketOverviewPage));
    expandMarketOverviewDataDiagnostics();

    const surface = await screen.findByTestId('market-regime-readiness-surface');
    await waitFor(() => expect(surface).toHaveTextContent('stale'));
    expect(surface).toHaveTextContent('2026-06-22');
    expect(surface).toHaveTextContent('volatility/risk regime');
  });

  it('shows a market regime readiness loading skeleton while the registry is pending', () => {
    vi.mocked(marketApi.getProfessionalDataCapabilities).mockReturnValueOnce(new Promise(() => {}));

    render(createElement(MarketOverviewPage));
    expandMarketOverviewDataDiagnostics();

    const surface = screen.getByTestId('market-regime-readiness-surface');
    expect(surface).toHaveTextContent('正在加载市场状态数据');
    expect(screen.getByTestId('market-regime-readiness-skeleton')).toBeInTheDocument();
  });

  it('shows a degraded market regime readiness state when the registry request fails', async () => {
    vi.mocked(marketApi.getProfessionalDataCapabilities).mockRejectedValueOnce(
      new Error('providerClass requestId rawPayload should stay hidden'),
    );

    render(createElement(MarketOverviewPage));
    expandMarketOverviewDataDiagnostics();

    const errorState = await screen.findByTestId('market-regime-readiness-error');
    expect(errorState).toHaveTextContent('市场状态数据可用性暂不可用，请稍后重试。');
    expect(errorState.textContent || '').not.toMatch(/providerClass|requestId|rawPayload|token|credential|env/i);

    fireEvent.click(within(errorState).getByRole('button', { name: '重试' }));
    await waitFor(() => {
      expect(marketApi.getProfessionalDataCapabilities).toHaveBeenCalledTimes(2);
    });
  });

  it('does not console-crash on a partial market regime readiness payload', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.mocked(marketApi.getProfessionalDataCapabilities).mockResolvedValueOnce({
      contractVersion: 'professional_data_capability_registry_v1',
      consumerSafe: true,
      summary: {
        totalCapabilities: 1,
        liveCount: 0,
        degradedCount: 1,
        entitlementRequiredCount: 0,
        configuredMissingCount: 0,
        notImplementedCount: 0,
      },
      categories: ['macro_cross_asset_regime'],
      capabilities: [
        {
          capabilityId: 'macro.cross_asset_inputs',
          label: 'Macro input',
          category: 'macro_cross_asset_regime',
          status: 'degraded',
          sourceLabel: 'Readiness registry',
        },
      ],
    } as never);

    render(createElement(MarketOverviewPage));
    expandMarketOverviewDataDiagnostics();

    const surface = await screen.findByTestId('market-regime-readiness-surface');
    await waitFor(() => expect(surface).toHaveTextContent('macro/cross-asset inputs'));
    expect(surface).toHaveTextContent('macro/cross-asset inputs');
    expect(surface).toHaveTextContent('degraded');
    expect(surface).toHaveTextContent('freshness pending');
    expect(consoleErrorSpy).not.toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });

  it('renders the MarketMonitor boundary with stable controls and collapsed diagnostics', async () => {
    renderMarketOverviewWorkbench();

    expect(screen.getByTestId('market-overview-workbench')).toBeInTheDocument();
    expect(screen.queryByTestId('market-overview-shell')).not.toBeInTheDocument();
    expect(screen.getByTestId('market-overview-market-monitor')).toBeInTheDocument();
    expect(screen.getByTestId('market-decision-semantics-strip')).toHaveTextContent(/市场论点/);
    expect(screen.getByTestId('market-decision-semantics-strip')).toHaveTextContent(/数据说明/);
    expect(screen.getByTestId('market-overview-visual-evidence-strip')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-visual-card-core-trends')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-visual-card-risk-pressure')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-visual-card-flow-rotation')).toBeInTheDocument();
    const gridLoading = screen.queryByTestId('market-overview-grid-loading');
    if (gridLoading) {
      expect(gridLoading).toHaveAttribute('aria-busy', 'true');
      expect(gridLoading).not.toHaveClass('bg-black');
    }
    expect(await screen.findByTestId('market-overview-main-grid')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-side-rail')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '展开 技术细节' })).not.toBeInTheDocument();
    expect(screen.queryByTestId('market-regime-synthesis-header')).not.toBeInTheDocument();

    const usTab = screen.getByRole('button', { name: '美股' });
    fireEvent.click(usTab);

    expect(usTab).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('market-overview-export-summary')).toBeInTheDocument();
  });

  it('renders bounded visual evidence cards and fail-closed unavailable copy without internal leakage', () => {
    renderMarketOverviewWorkbenchWithProps({
      panels: {
        ...localSnapshotPayload().payload,
        volatility: undefined,
        fundsFlow: undefined,
        sectorRotation: undefined,
        usBreadth: usBreadthUnavailablePanel(),
      },
    });

    const strip = screen.getByTestId('market-overview-visual-evidence-strip');
    expect(strip).toBeInTheDocument();
    expect(strip).toHaveTextContent('核心图表证据');
    expect(screen.getByTestId('market-overview-visual-card-core-trends-points')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-visual-card-risk-pressure-unavailable')).toHaveTextContent('风险压力图形证据缺失，当前保持观察。');
    expect(screen.getByTestId('market-overview-visual-card-flow-rotation-unavailable')).toHaveTextContent('资金与轮动图形证据缺失，当前保持观察。');
    expect(screen.queryByTestId('market-overview-visual-card-rifixture-token-redacted-for-secret-scan')).not.toBeInTheDocument();
    expect(strip.textContent || '').not.toMatch(/raw|debug|provider|cache|router|env|trace|credential|broker|trade|order|sourceAuthority|contractVersion/i);
  });

  it('maps proxy indicator labels across default consumer cards and visual evidence', () => {
    renderMarketOverviewWorkbenchWithProps({
      panels: {
        ...localSnapshotPayload().payload,
        fundsFlow: {
          ...snapshotPanel('FundsFlowCard', 'ETF_FLOW_PROXY', 'ETF flow proxy'),
          items: [
            snapshotPanel('FundsFlowCard', 'ETF_FLOW_PROXY', 'ETF flow proxy').items[0],
            snapshotPanel('FundsFlowCard', 'INST_PRESSURE', 'Institutional pressure proxy').items[0],
          ],
        },
        sectorRotation: snapshotPanel('SectorRotationCard', 'INDUSTRY_BREADTH', 'Industry breadth proxy'),
      },
    });

    expect(screen.getAllByText('ETF 资金流指标').length).toBeGreaterThan(0);
    expect(screen.getAllByText('机构压力指标').length).toBeGreaterThan(0);
    expect(screen.getByTestId('market-overview-visual-evidence-strip')).toHaveTextContent('行业广度指标');

    const titleText = Array.from(document.querySelectorAll<HTMLElement>('[title]'))
      .map((node) => node.getAttribute('title') || '')
      .join(' ');
    const defaultConsumerText = `${document.body.textContent || ''} ${titleText}`;
    expect(defaultConsumerText).not.toMatch(RAW_MARKET_OVERVIEW_PROXY_LABEL_PATTERN);
  });

  it('lazy loads technical diagnostics only after the admin disclosure opens', async () => {
    renderMarketOverviewWorkbenchWithProps({ showAdminDiagnostics: true });

    expect(screen.queryByTestId('market-decision-debug-loading')).not.toBeInTheDocument();
    expect(screen.queryByTestId('market-regime-synthesis-header')).not.toBeInTheDocument();

    const details = expandMarketDecisionDetails();

    expect(within(details).getByTestId('market-decision-debug-loading')).toHaveAttribute('aria-busy', 'true');
    expect(within(details).queryByTestId('market-regime-synthesis-header')).not.toBeInTheDocument();
    expect(await within(details).findByTestId('market-overview-official-macro-diagnostics')).toBeInTheDocument();
  });

  afterEach(() => {
    __resetMarketOverviewRequestOwnershipForTests();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: originalClipboard,
    });
  });

  it('renders exactly one compact semantic market state heading without internal terms', async () => {
    renderMarketOverviewWithLanguage('zh');

    const heading = await screen.findByRole('heading', { level: 1, name: '市场状态概览' });
    expect(heading).toHaveAttribute('data-research-type-role', 'observation-title');
    expect(screen.getByTestId('market-overview-observation-head')).toContainElement(heading);
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.queryByText(/开发者详情|debug|raw|schema|trace|provider_timeout|not_enough_history|MarketCache|generatedCandidates|failedCandidates|LLM Ledger|QUOTA PILOT/i)).not.toBeInTheDocument();
  });

  it('adopts research anatomy composition for observation, quality, risk limits, and next research actions', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: false,
      canReadProviders: false,
    });
    render(createElement(MarketOverviewPage));

    const observationHead = await screen.findByTestId('market-overview-observation-head');
    expect(observationHead).toHaveAttribute('data-research-anatomy', 'observation-head');
    expect(observationHead).toHaveAttribute('data-research-density', 'research');
    expect(within(observationHead).getByTestId('market-overview-top-verdict')).toBeInTheDocument();
    expect(within(observationHead).getByTestId('market-overview-summary-strip')).toBeInTheDocument();

    const quality = screen.getByTestId('market-overview-data-quality-composition');
    expect(quality).toHaveAttribute('data-research-anatomy', 'data-quality');
    expect(quality.querySelectorAll('[data-quality-facet]').length).toBeGreaterThan(0);

    const riskLimits = screen.getByTestId('market-overview-research-risk-limits');
    expect(riskLimits).toHaveAttribute('data-research-anatomy', 'risk-limits');
    expect(riskLimits).toHaveAttribute('data-risk-limits-placement', 'disclosure');
    expect(within(riskLimits).getByRole('button')).toHaveAttribute('aria-expanded', 'false');

    const nextAction = screen.getByTestId('market-overview-next-research-action');
    expect(nextAction).toHaveAttribute('data-research-anatomy', 'next-research-action');
    expect(nextAction.tagName.toLowerCase()).toBe('nav');
    expect(within(nextAction).getByText('研究雷达')).toBeInTheDocument();
    expect(within(nextAction).getByText('扫描器')).toBeInTheDocument();
    expect(nextAction.textContent || '').not.toMatch(/买入|卖出|加仓|减仓|推荐|目标价|position size/i);

    await waitFor(() => {
      expect(screen.getByTestId('market-overview-main-grid')).toHaveAttribute('data-market-overview-composition', 'grouped-evidence');
    });
    expect(screen.getByTestId('market-overview-secondary-grid')).toHaveAttribute('data-evidence-composition', 'grouped');
    expect(document.querySelectorAll('[data-evidence-group-role]').length).toBeGreaterThan(0);
    expect(screen.getByTestId('market-overview-workbench').className).not.toMatch(/\btext-white\b/);
  });

  it('does not render route-level actionability diagnostics by default for ready-ish frames', async () => {
    renderMarketOverviewWithLanguage('zh');

    await screen.findByTestId('market-overview-workbench');
    expect(screen.queryByTestId('market-overview-research-readiness-strip')).not.toBeInTheDocument();
    const diagnostics = screen.getByTestId('market-overview-data-diagnostics-disclosure');
    expect(diagnostics).toHaveTextContent('查看数据诊断');
    expect(diagnostics).not.toHaveAttribute('open');
    const firstViewport = screen.getByTestId('market-overview-workbench');
    expect(screen.getByTestId('market-overview-first-workbench')).toHaveAttribute('data-market-composition', 'research-workbench-path');
    expect(screen.getByTestId('market-overview-pulse-header')).toContainElement(screen.getByTestId('market-decision-semantics-strip'));
    expect(screen.getByTestId('market-overview-dominant-path')).toContainElement(screen.getByTestId('market-overview-core-trend-chart'));
    expect(firstViewport).toHaveTextContent(/市场论点|市场状态|发生了什么/);
    expect(firstViewport.textContent || '').not.toMatch(
      /available|missing|not configured|provider_missing|blockedProductSurfaces|missingDataFamilies|sourceClass|sourcePath|contractVersion|inputSource|local_bounded_us_parquet_universe|noExternalCalls|providerCallsEnabled|not_requested/i,
    );
    expect(screen.getByTestId('market-decision-semantics-strip')).toHaveTextContent(/研究观察，不构成投资建议/);
    expect((firstViewport.textContent || '').match(/研究观察，不构成投资建议/g)).toHaveLength(1);
  });

  it('keeps fail-closed market state without default route-level diagnostics when evidence is missing', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(unreliableTemperaturePayload());

    renderMarketOverviewWithLanguage('zh');

    const decisionReadiness = await screen.findByTestId('market-overview-decision-readiness');
    expect(decisionReadiness).toHaveTextContent(/偏强观察|中性观察|偏弱观察|数据不足|证据待补/);
    expect(screen.queryByTestId('market-overview-research-readiness-strip')).not.toBeInTheDocument();
  });

  it('does not promote stale or fallback evidence diagnostics into the default route surface', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce({
      ...temperaturePayload(),
      marketActionabilityFrame: {
        ...temperaturePayload().marketActionabilityFrame,
        verdict: 'insufficient',
        freshness: 'fallback',
        confidence: {
          value: 0.16,
          label: 'insufficient',
          capReasons: ['stale_evidence', 'fallback_evidence'],
        },
        missingEvidence: ['freshness'],
      },
      marketIntelligenceEvidenceFrame: {
        ...temperaturePayload().marketIntelligenceEvidenceFrame,
        frameState: 'insufficient',
        freshness: 'fallback',
        missingEvidence: ['freshness'],
        blockingReasons: ['stale_evidence', 'fallback_evidence', 'observation_only'],
        rotationEvidence: {
          ...temperaturePayload().marketIntelligenceEvidenceFrame.rotationEvidence,
          state: 'degraded',
          freshness: 'fallback',
          blockingReasons: ['fallback_evidence'],
        },
        scannerContextEvidence: {
          ...temperaturePayload().marketIntelligenceEvidenceFrame.scannerContextEvidence,
          state: 'degraded',
          freshness: 'fallback',
          blockingReasons: ['fallback_evidence'],
        },
      },
    });

    renderMarketOverviewWithLanguage('zh');

    await screen.findByTestId('market-overview-workbench');
    expect(screen.queryByText('市场研判可用性')).not.toBeInTheDocument();
  });

  it('keeps old temperature payloads compatible by omitting the actionability strip when additive frames are absent', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce({
      ...temperaturePayload(),
      marketActionabilityFrame: undefined,
      marketIntelligenceEvidenceFrame: undefined,
    });

    renderMarketOverviewWithLanguage('zh');

    await screen.findByTestId('market-overview-workbench');
    expect(screen.queryByTestId('market-overview-research-readiness-strip')).not.toBeInTheDocument();
  });

  it('exposes a distinct tab composition registry for market overview tabs', () => {
    expect(Object.keys(MARKET_OVERVIEW_TAB_CONFIG)).toEqual(['all', 'us', 'cn', 'global', 'crypto']);
    expect(MARKET_OVERVIEW_TAB_CONFIG.all.pulse).toEqual(expect.arrayContaining(['SPX', 'CSI300', 'HSI', 'BTC', 'VIX', 'US10Y', 'DXY']));
    expect(MARKET_OVERVIEW_TAB_CONFIG.us.pulse).toEqual(expect.arrayContaining(['SPX', 'NDX', 'DJI', 'RUT', 'VIX', 'US10Y', 'DXY']));
    expect(MARKET_OVERVIEW_TAB_CONFIG.cn.pulse).toEqual(expect.arrayContaining(['SHCOMP', 'SZCOMP', 'CSI300', 'HSI', 'HSTECH', 'A50', 'USDCNH']));
    expect(MARKET_OVERVIEW_TAB_CONFIG.global.pulse).toEqual(expect.arrayContaining(['US10Y', 'DXY', 'USDJPY', 'USDCNH', 'GOLD', 'WTI', 'VIX', 'BTC']));
    expect(MARKET_OVERVIEW_TAB_CONFIG.crypto.pulse).toEqual(expect.arrayContaining(['BTC', 'ETH', 'SOL', 'BNB']));
    expect(MARKET_OVERVIEW_TAB_CONFIG.crypto.pulse).not.toEqual(expect.arrayContaining(['SPX', 'CSI300', 'HSI', 'DJI']));
    expect(new Set(MARKET_OVERVIEW_TAB_CONFIG.crypto.modules)).not.toEqual(new Set(MARKET_OVERVIEW_TAB_CONFIG.us.modules));
    expect(MARKET_OVERVIEW_TAB_CONFIG.crypto.modules).toEqual(expect.arrayContaining(['cryptoMomentum', 'cryptoLiquidity', 'cryptoRiskContext']));
  });

  it('switches pulse metrics and primary modules from the tab registry', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
      quoteItem('DJI', 'Dow Jones', 38920.18, -0.12),
      quoteItem('RUT', 'Russell 2000', 2088.5, 0.21),
    ]));
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce(denseQuotePanel('ChinaIndicesCard', [
      quoteItem('000001.SH', 'Shanghai Composite', 3120.55, 0.39, 'sina'),
      quoteItem('399001.SZ', 'Shenzhen Component', 9842.31, -0.18, 'sina'),
      quoteItem('000300.SH', 'CSI 300', 3588.12, 0.44, 'sina'),
      quoteItem('HSI', 'Hang Seng Index', 17712.5, 0.73, 'sina'),
      quoteItem('HSTECH', 'Hang Seng TECH', 3650.1, 0.62, 'sina'),
    ], 'mixed'));
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce({
      ...cryptoFullPanel(),
      items: [
        ...cryptoFullPanel().items,
        quoteItem('SOL', 'Solana', 143.2, 1.8, 'binance'),
      ],
    });
    vi.mocked(marketApi.getRates).mockResolvedValueOnce(denseQuotePanel('RatesCard', [
      quoteItem('US10Y', 'US 10Y', 4.62, -0.14),
      quoteItem('US2Y', 'US 2Y', 4.91, 0.04),
      quoteItem('US30Y', 'US 30Y', 4.74, -0.08),
    ]));
    vi.mocked(marketApi.getFxCommodities).mockResolvedValueOnce(denseQuotePanel('FxCommoditiesCard', [
      quoteItem('DXY', 'US Dollar Index', 106.2, 0.2),
      quoteItem('USDJPY', 'USD/JPY', 155.9, 0.1),
      quoteItem('USDCNH', 'USD/CNH', 7.24, 0.2),
      quoteItem('GOLD', 'Gold', 2380.3, 0.5),
      quoteItem('WTI', 'WTI Crude', 78.4, -0.3),
    ]));

    render(createElement(MarketOverviewPage));

    await screen.findByTestId('market-overview-hero-ribbon');
    expect(getPulseText()).toMatch(/标普500/);
    expect(getPulseText()).toMatch(/沪深300/);
    expect(getPulseText()).toMatch(/恒生指数/);
    expect(getPulseText()).toMatch(/比特币/);

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    expect(getPulseText()).toMatch(/标普500/);
    expect(getPulseText()).toMatch(/纳斯达克100/);
    expect(getPulseText()).toMatch(/道琼斯工业平均指数/);
    expect(getPulseText()).toMatch(/罗素2000/);
    expect(getPulseText()).not.toMatch(/沪深300|恒生指数|比特币/);
    expect(screen.queryByTestId('market-overview-module-cryptoCore')).not.toBeInTheDocument();
    expect(screen.queryByTestId('market-overview-module-cnBreadth')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expect(getPulseText()).toMatch(/上证指数/);
    expect(getPulseText()).toMatch(/深证成指/);
    expect(getPulseText()).toMatch(/沪深300/);
    expect(getPulseText()).toMatch(/恒生科技指数/);
    expect(getPulseText()).toMatch(/USD\/CNH/);
    expect(getPulseText()).not.toMatch(/比特币|以太坊|标普500/);
    expect(screen.queryByTestId('market-overview-module-cryptoCore')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '全球宏观' }));
    expect(getPulseText()).toMatch(/美国10年期国债收益率/);
    expect(getPulseText()).toMatch(/美元指数/);
    expect(getPulseText()).toMatch(/USD\/JPY/);
    expect(getPulseText()).toMatch(/黄金/);
    expect(getPulseText()).toMatch(/WTI 原油/);

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    expect(getPulseText()).toMatch(/比特币/);
    expect(getPulseText()).toMatch(/以太坊/);
    expect(getPulseText()).toMatch(/Solana/);
    expect(getPulseText()).toMatch(/BNB/);
    expect(getPulseText()).not.toMatch(/标普500|沪深300|恒生指数|道琼斯/);
    expect(screen.getByTestId('market-overview-module-cryptoCore')).toHaveTextContent(/加密核心/);
    expect(screen.getByTestId('market-overview-module-cryptoMomentum')).toHaveTextContent(/加密动量/);
    expect(screen.getByTestId('market-overview-module-cryptoLiquidity')).toHaveTextContent(/BTC 资金费率|未接入/);
    expect(screen.getByTestId('market-overview-module-cryptoRiskContext')).toHaveTextContent(/宏观压力|加密风险上下文/);
    expect(screen.queryByTestId('market-overview-module-cnHkIndices')).not.toBeInTheDocument();
    expect(screen.queryByTestId('market-overview-module-usIndices')).not.toBeInTheDocument();
  });

  it('keeps signal watch and coverage labels tab aware while switching tabs', async () => {
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());
    render(createElement(MarketOverviewPage));

    await screen.findByTestId('market-overview-rail-signal-watch');
    await expectCoverageSummarySettled();
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/VIX/);
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/US 10Y|DXY/);

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    await expectCoverageSummarySettled();
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/VIX/);
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/US 10Y|DXY/);
    expect(screen.getByTestId('market-overview-rail-signal-watch')).not.toHaveTextContent(/HSI/);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    await expectCoverageSummarySettled();
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/沪深300/);
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/HSI|HSTECH/);

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    await expectCoverageSummarySettled();
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/Bitcoin/);
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/Ethereum/);
    expect(screen.getByTestId('market-overview-card-cryptoCore')).toBeInTheDocument();
    expect(screen.getByText(/复制证据快照|证据快照已复制/)).toBeInTheDocument();
  });

  it('uses metric aliases for executive summary cards instead of rendering N/A for explicit backend values', async () => {
    const basePanels = localSnapshotPayload().payload;
    renderMarketOverviewWorkbenchWithProps({
      panels: {
        ...basePanels,
        indices: denseQuotePanel('IndexTrendsCard', [
          quoteItem('^GSPC', 'S&P 500', 5120.25, 0.42),
        ]),
        cnIndices: denseQuotePanel('ChinaIndicesCard', [
          quoteItem('000300.SS', 'CSI 300', 3588.12, 0.44, 'sina'),
        ], 'sina'),
        rates: denseQuotePanel('RatesCard', [
          quoteItem('10Y YIELD', 'US 10Y', 4.62, -0.14),
        ]),
        fxCommodities: denseQuotePanel('FxCommoditiesCard', [
          quoteItem('US DOLLAR INDEX', 'US Dollar Index', 106.2, 0.2),
        ]),
        crypto: denseQuotePanel('CryptoCard', [
          quoteItem('BITCOIN', 'Bitcoin', 67000, 1.5, 'binance'),
        ], 'binance'),
      },
    });

    const usGroup = await screen.findByTestId('market-overview-secondary-group-us');
    const cnGroup = screen.getByTestId('market-overview-secondary-group-cn');
    const macroGroup = screen.getByTestId('market-overview-secondary-group-macro');
    const cryptoGroup = screen.getByTestId('market-overview-secondary-group-crypto');

    expect(usGroup).toHaveTextContent('5,120.25');
    expect(cnGroup).toHaveTextContent('3,588.12');
    expect(macroGroup).toHaveTextContent('4.62');
    expect(cryptoGroup).toHaveTextContent('67,000');
    [usGroup, cnGroup, macroGroup, cryptoGroup].forEach((group) => {
      expect(group).not.toHaveTextContent('N/A');
    });
  });

  it('renders stable main grid with primary and side rails', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
      source: 'mixed',
      sourceLabel: 'Sina + 备用数据',
      freshness: 'delayed' as const,
      isFallback: false,
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300').items[0],
          source: 'sina',
          sourceLabel: 'Sina',
          freshness: 'delayed' as const,
          isFallback: false,
        },
        snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
      ],
    });
    render(createElement(MarketOverviewPage));

    expect(screen.getByRole('button', { name: '全部' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '美股' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'A股/港股' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '全球宏观' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '加密货币' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /大市全景监控/i })).not.toBeInTheDocument();

    expect(screen.getByTestId('market-overview-hero-ribbon')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-hero-ribbon')).toHaveAttribute('data-linear-primitive', 'key-level-strip');
    expect(screen.getByTestId('market-decision-semantics-strip')).toBeInTheDocument();
    expect(screen.getByTestId('market-decision-semantics-strip')).toHaveTextContent(/市场论点/);
    expect(screen.getByTestId('market-decision-semantics-strip')).toHaveTextContent(/数据说明/);
    expect(screen.queryByTestId('market-overview-research-readiness-strip')).not.toBeInTheDocument();
    const conclusion = screen.getByTestId('market-overview-decision-readiness');
    expect(conclusion).toHaveTextContent('市场论点');
    expect(conclusion).toHaveTextContent('发生了什么');
    expect(conclusion).toHaveTextContent('重要点');
    expect(conclusion).toHaveTextContent('下一步看什么');
    expect(screen.getByTestId('market-overview-status-line')).toHaveTextContent(/信心水平/);
    expect(screen.queryByTestId('market-command-chips')).not.toBeInTheDocument();
    expect(screen.getByTestId('market-overview-quick-actions')).toHaveTextContent('决策驾驶舱');
    expect(screen.getByTestId('market-overview-quick-actions')).toHaveTextContent('研究雷达');
    expect(screen.getByTestId('market-overview-quick-actions')).toHaveTextContent('扫描器');
    expect(screen.getByTestId('market-overview-quick-actions')).toHaveTextContent('搜索个股');
    expect(screen.getByTestId('market-decision-semantics-advice-boundary')).toHaveTextContent(/偏强观察|中性观察|偏弱观察|数据不足|证据待补/);
    const details = expandMarketDecisionDetails();
    expect(screen.getByTestId('market-overview-regime-summary-lane')).toBeInTheDocument();
    expect(within(details).getByTestId('market-temperature-strip')).toBeInTheDocument();
    expect(within(details).getByTestId('market-briefing-card')).toHaveTextContent(/主要指数走强，VIX 回落|当前关键数据不足|数据待补/);

    const shell = screen.getByTestId('market-overview-shell');
    const workbench = screen.getByTestId('market-overview-workbench');
    expect(shell).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(shell).toHaveClass(
      'flex',
      'w-full',
      'flex-1',
      'min-h-0',
      'flex-col',
      'gap-4',
      'mx-auto',
      'max-w-[var(--wolfy-consumer-shell-max,1880px)]',
      'px-4',
      'xl:px-8',
      'py-5',
      'md:py-6',
    );
    expect(shell).not.toHaveClass('bg-[#030303]', 'bg-[#050505]');
    expect(shell.className).not.toContain('bg-black');
    expect(shell.parentElement).toHaveAttribute('data-workspace-width', 'near-full');
    expect(workbench).toHaveAttribute('data-bento-surface', 'true');
    expect(workbench).toHaveClass(
      'bento-surface-root',
      'w-full',
      'flex',
      'flex-1',
      'min-h-0',
      'min-w-0',
      'flex-col',
      'gap-4',
      'overflow-y-auto',
      'overflow-x-hidden',
      'no-scrollbar',
    );
    expect(workbench).not.toHaveClass('py-5', 'md:py-6', 'px-4', 'sm:px-6', 'lg:px-8', '2xl:px-10', 'py-6');
    expect(workbench).not.toHaveClass('max-w-[1600px]');
    expect(workbench.className).not.toContain('bg-black');
    expect(workbench.className).not.toContain('max-w-[1280px]');
    expect(workbench.className).not.toContain('max-w-[1600px]');
    expect(workbench.className).not.toContain('max-w-[1800px]');
    expect(shell.className).not.toContain('max-w-5xl');
    expect(shell.className).not.toContain('max-w-6xl');
    expect(screen.getByTestId('market-overview-category-tabs')).toHaveClass('w-full', 'min-w-0', 'backdrop-blur-md');
    expect(screen.getByTestId('market-overview-category-tabs').className).toMatch(/bg-\[color:var\(--wolfy-surface-input\)\]|bg-white\/\[0\.02\]/);
    expect(screen.getByTestId('market-overview-export-summary')).toHaveTextContent('复制证据快照');
    expect(screen.getByTestId('market-overview-export-summary')).not.toHaveTextContent('摘要');
    expect(screen.getByTestId('market-overview-category-tabs')).not.toHaveClass('sticky', 'top-0', 'z-20', '-mx-4');
    expect(screen.getByTestId('market-overview-top-stack')).toContainElement(screen.getByTestId('market-overview-category-tabs'));
    expect(screen.getByTestId('market-overview-top-stack').firstElementChild).toContainElement(screen.getByTestId('market-decision-semantics-strip'));
    expect(screen.getByTestId('market-overview-category-tabs')).toHaveAttribute('data-selector-position', 'static-safe');
    const categoryScroller = screen.getByTestId('market-overview-category-tabs').querySelector('.ui-scroll-x-quiet');
    expect(categoryScroller).not.toBeNull();
    expect(categoryScroller).toHaveClass('max-w-full', 'overflow-x-auto', 'overscroll-x-contain');
    expect(shell).toContainElement(screen.getByTestId('market-overview-category-tabs'));
    expect(shell).toContainElement(screen.getByTestId('market-overview-workbench'));
    expect(shell).toContainElement(screen.getByTestId('market-overview-hero-ribbon'));
    expect(shell).toContainElement(screen.getByTestId('market-data-quality'));
    expect(shell).toContainElement(screen.getByTestId('market-overview-main-grid'));
    expect(screen.queryByTestId('market-overview-research-readiness-strip')).not.toBeInTheDocument();

    expect(await screen.findByTestId('market-overview-main-grid')).toHaveClass('grid', 'grid-cols-1', 'xl:grid-cols-12', 'gap-4', 'items-start');
    expect(screen.getByTestId('market-overview-primary-rail')).toHaveClass('xl:col-span-9', 'flex', 'flex-col');
    expect(screen.getByTestId('market-overview-side-rail')).toHaveClass('xl:col-span-3', 'flex', 'flex-col', 'gap-3');
    expect(screen.getByTestId('market-overview-deep-panels')).toContainElement(screen.getByTestId('market-overview-executive-secondary-groups'));
    expect(screen.getByRole('heading', { name: /全球核心指数走势/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /加密货币行情/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /波动率与风险压力/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /ETF 资金流向/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /A股与港股指数/i })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /宏观经济与流动性/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /市场宽度与赚钱效应/i })).not.toBeInTheDocument();
    expect(screen.getByTestId('market-overview-rail-action-hint')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /同步最新行情/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/同步完成/i)).not.toBeInTheDocument();

    expect(screen.getAllByText(/比特币/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/标普500/i).length).toBeGreaterThan(0);
    expect(screen.queryByText('pts')).not.toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByTestId('market-overview-sparkline').length).toBeGreaterThanOrEqual(2);
    });
    expect(screen.queryByText(/Log:/i)).not.toBeInTheDocument();
    expect(screen.queryAllByTestId('market-overview-fallback-only-notice')).toHaveLength(0);
    expect(screen.getByTestId('market-data-quality')).toBeInTheDocument();
    await expectCoverageSummarySettled();
    expect(screen.getByTestId('market-data-quality')).toHaveTextContent(/数据可用|更新中|等待实时源|部分数据暂不可用/);
    expect(screen.queryAllByTestId('market-overview-compact-error-badge').length).toBeLessThanOrEqual(2);
    expect(screen.getAllByTestId('data-freshness-badge-fallback').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('data-freshness-badge-cache').length).toBeGreaterThan(0);
    await waitFor(() => expect(marketOverviewApi.getMacro).toHaveBeenCalledTimes(1));
  });

  it('hydrates market overview from localStorage before backend responses settle', async () => {
    window.localStorage.setItem(MARKET_OVERVIEW_LKG_STORAGE_KEY, JSON.stringify(localSnapshotPayload()));
    vi.mocked(marketOverviewApi.getIndices).mockReturnValueOnce(new Promise(() => {}));

    render(createElement(MarketOverviewPage));

    expect((await screen.findAllByText('5,111.11')).length).toBeGreaterThan(0);
    const details = expandMarketDecisionDetails();
    expect(within(details).getByTestId('market-overview-cache-status')).toHaveTextContent(/刷新中/i);
    expect(within(details).getByTestId('market-overview-cache-status')).not.toHaveTextContent(/LOCAL CACHE/i);
    expect(within(details).getByTestId('market-overview-cache-status')).toHaveTextContent(/更新时间/i);
    expect(screen.queryByText(/indices request timed out/i)).not.toBeInTheDocument();
  });

  it('persists latest usable backend data to the market overview local snapshot', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5222.22, 0.52),
    ]));

    render(createElement(MarketOverviewPage));

    await waitFor(() => {
      const saved = JSON.parse(window.localStorage.getItem(MARKET_OVERVIEW_LKG_STORAGE_KEY) || '{}');
      expect(saved.payload?.indices?.items?.[0]?.value).toBe(5222.22);
    });
    const saved = JSON.parse(window.localStorage.getItem(MARKET_OVERVIEW_LKG_STORAGE_KEY) || '{}');
    expect(saved.schemaVersion).toBe(1);
    expect(saved.payload.indices.items[0].value).toBe(5222.22);
    expect(JSON.stringify(saved)).not.toContain('request timed out');
  });

  it('persists one route-entry local snapshot after staggered panel settlement', async () => {
    vi.useFakeTimers();
    const setItemSpy = vi.spyOn(window.localStorage.__proto__, 'setItem');
    const indicesRequest = createDeferredPromise<ReturnType<typeof panel>>();
    const volatilityRequest = createDeferredPromise<ReturnType<typeof panel>>();
    const cryptoRequest = createDeferredPromise<ReturnType<typeof cryptoPanel>>();
    vi.mocked(marketOverviewApi.getIndices).mockReturnValueOnce(indicesRequest.promise);
    vi.mocked(marketOverviewApi.getVolatility).mockReturnValueOnce(volatilityRequest.promise);
    vi.mocked(marketApi.getCrypto).mockReturnValueOnce(cryptoRequest.promise);

    render(createElement(MarketOverviewPage));

    await drainStagedMarketPanelRequests();
    await flushMarketOverviewMicrotasks(4);

    await runMarketOverviewAsyncStep(() => {
      indicesRequest.resolve(panel('IndexTrendsCard', 'SPX'));
    });
    await flushMarketOverviewMicrotasks(2);
    await runMarketOverviewAsyncStep(() => {
      volatilityRequest.resolve(panel('VolatilityCard', 'VIX'));
    });
    await flushMarketOverviewMicrotasks(2);
    await runMarketOverviewAsyncStep(() => {
      cryptoRequest.resolve(cryptoPanel());
    });
    await flushMarketOverviewMicrotasks(4);

    const saved = JSON.parse(window.localStorage.getItem(MARKET_OVERVIEW_LKG_STORAGE_KEY) || '{}');
    expect(Object.keys(saved.payload || {}).length).toBeGreaterThanOrEqual(17);
    const lkgWrites = setItemSpy.mock.calls.filter(([key]) => key === MARKET_OVERVIEW_LKG_STORAGE_KEY);
    expect(lkgWrites).toHaveLength(1);
  });

  it('keeps local snapshot visible when backend refresh fails and keeps errors compact', async () => {
    window.localStorage.setItem(MARKET_OVERVIEW_LKG_STORAGE_KEY, JSON.stringify(localSnapshotPayload()));
    vi.mocked(marketOverviewApi.getIndices).mockRejectedValueOnce(new Error('indices request timed out'));
    vi.mocked(marketApi.getRates).mockRejectedValueOnce(new Error('rates request timed out'));

    render(createElement(MarketOverviewPage));

    expect((await screen.findAllByText('5,111.11')).length).toBeGreaterThan(0);
    const details = expandMarketDecisionDetails();
    await waitFor(() => expect(within(details).getByTestId('market-overview-cache-status')).toHaveTextContent(/待刷新|部分外部数据暂不可用|备用数据/i));
    expect(within(details).getByTestId('market-overview-cache-status')).not.toHaveTextContent(/REFRESH FAILED|CACHE|STALE|ERROR/i);
    expect(screen.getAllByText('标普500').length).toBeGreaterThan(0);
    expect(screen.queryByText(/更新失败：indices request timed out/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/provider_down|provider_error|UNKNOWN/i)).not.toBeInTheDocument();
    expect(within(details).getByTestId('market-overview-data-state-unavailable-chip')).toHaveTextContent(/部分外部数据暂不可用/);
    expect(within(details).getByTestId('market-overview-data-state-unavailable-chip')).toHaveAttribute('data-terminal-primitive', 'chip');
  });

  it('stages noncritical market overview panels after the primary route data starts loading', async () => {
    vi.useFakeTimers();

    render(createElement(MarketOverviewPage));

    expect(countMarketPanelRequests()).toBe(10);
    expectMarketPanelRequestsCalledOnce(primaryMarketPanelRequests);
    expectMarketPanelRequestsNotCalled([
      ...firstStagedMarketPanelRequests,
      ...secondStagedMarketPanelRequests,
    ]);
    expect(MockEventSource.instances).toHaveLength(1);

    await advanceFirstStagedMarketPanelRequests();

    expect(countMarketPanelRequests()).toBe(13);
    expectMarketPanelRequestsCalledOnce([
      ...primaryMarketPanelRequests,
      ...firstStagedMarketPanelRequests,
    ]);
    expectMarketPanelRequestsNotCalled(secondStagedMarketPanelRequests);

    await advanceSecondStagedMarketPanelRequests();

    expect(countMarketPanelRequests()).toBe(17);
    expectMarketPanelRequestsCalledOnce(allMarketPanelRequests);
    expect(MockEventSource.instances).toHaveLength(1);
  });

  it('dedupes route-entry market requests and the crypto stream under React StrictMode', async () => {
    vi.useFakeTimers();

    render(
      <StrictMode>
        <MarketOverviewPage />
      </StrictMode>,
    );

    expect(countMarketPanelRequests()).toBe(10);
    expectMarketPanelRequestsCalledOnce(primaryMarketPanelRequests);
    expectMarketPanelRequestsNotCalled([
      ...firstStagedMarketPanelRequests,
      ...secondStagedMarketPanelRequests,
    ]);

    await advanceFirstStagedMarketPanelRequests();

    expect(countMarketPanelRequests()).toBe(13);
    expectMarketPanelRequestsCalledOnce([
      ...primaryMarketPanelRequests,
      ...firstStagedMarketPanelRequests,
    ]);
    expectMarketPanelRequestsNotCalled(secondStagedMarketPanelRequests);

    await advanceSecondStagedMarketPanelRequests();

    expect(countMarketPanelRequests()).toBe(17);
    expectMarketPanelRequestsCalledOnce(allMarketPanelRequests);
    expect(MockEventSource.instances).toHaveLength(1);
  });

  it('keeps route-entry panel ownership until the canonical request settles', async () => {
    const indicesRequest = createDeferredPromise<ReturnType<typeof panel>>();
    vi.mocked(marketOverviewApi.getIndices).mockReturnValue(indicesRequest.promise);

    const firstView = render(createElement(MarketOverviewPage));
    await flushMarketOverviewMicrotasks(2);
    firstView.unmount();

    render(createElement(MarketOverviewPage));
    await flushMarketOverviewMicrotasks(2);

    expect(marketOverviewApi.getIndices).toHaveBeenCalledTimes(1);

    await runMarketOverviewAsyncStep(() => {
      indicesRequest.resolve(panel('IndexTrendsCard', 'SPX'));
    });
  });

  it('does not request operator-only readiness endpoints for consumer surface mode', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: false,
      canReadProviders: false,
    });

    render(createElement(MarketOverviewPage));

    await waitFor(() => expect(marketOverviewApi.getIndices).toHaveBeenCalledTimes(1));
    expect(marketApi.getDataReadiness).not.toHaveBeenCalled();
    expect(marketApi.getProfessionalDataCapabilities).not.toHaveBeenCalled();
    expect(marketApi.getRegimeReadModel).toHaveBeenCalledTimes(1);
  });

  it('allows admin operator readiness ownership when provider capability is present', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: true,
      canReadProviders: true,
    });

    render(createElement(MarketOverviewPage));

    await waitFor(() => expect(marketApi.getDataReadiness).toHaveBeenCalledTimes(1));
    expect(marketApi.getProfessionalDataCapabilities).toHaveBeenCalledTimes(1);
    expect(marketApi.getRegimeReadModel).toHaveBeenCalledTimes(1);
  });

  it('renders a stable MarketMonitor skeleton with grouped deep panels and collapsed diagnostics', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: false,
      canReadProviders: false,
    });
    render(createElement(MarketOverviewPage));

    expect(await screen.findByTestId('market-overview-pulse-header')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-category-tabs')).toBeInTheDocument();
    const categoryScroller = screen.getByTestId('market-overview-category-tabs').querySelector('.ui-scroll-x-quiet');
    expect(categoryScroller).not.toBeNull();
    expect(categoryScroller).toHaveClass('max-w-full', 'overflow-x-auto', 'overscroll-x-contain');
    expect(screen.getByTestId('market-overview-market-monitor')).toBeInTheDocument();
    expect(screen.getByTestId('market-decision-semantics-strip')).toBeInTheDocument();

    const mainGrid = screen.getByTestId('market-overview-main-grid');
    const primaryRail = screen.getByTestId('market-overview-primary-rail');
    const sideRail = screen.getByTestId('market-overview-side-rail');

    expect(mainGrid).toHaveAttribute('data-market-monitor-layout', 'drivers-plus-ledger');
    expect(primaryRail).toHaveClass('flex', 'flex-col');
    expect(primaryRail).not.toHaveClass('overflow-x-auto', 'stealth-scrollbar');
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-context-rail'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-rail-action-hint'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-rail-quality'));
    expect(screen.queryByRole('button', { name: '展开 技术细节' })).not.toBeInTheDocument();
    expect(within(sideRail).queryByRole('button', { name: /展开/i })).not.toBeInTheDocument();
    expect(screen.getByTestId('market-overview-deep-panels')).toContainElement(screen.getByTestId('market-overview-executive-secondary-groups'));
  });

  it('renders compact diagnostic disclosures instead of always-open rail cards', async () => {
    render(createElement(MarketOverviewPage));

    const sideRail = await screen.findByTestId('market-overview-side-rail');
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-context-rail'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-rail-action-hint'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-rail-quality'));
    expect(within(sideRail).queryByRole('button', { name: /展开/i })).not.toBeInTheDocument();
    expect(screen.queryByTestId('market-overview-compact-rail-card')).not.toBeInTheDocument();
    expect(screen.queryByTestId('market-overview-fallback-section')).not.toBeInTheDocument();
  });

  it('keeps mobile DOM order with data state ahead of the overview summary', async () => {
    render(createElement(MarketOverviewPage));

    await screen.findByTestId('market-overview-workbench');
    expect(screen.getByTestId('market-overview-top-stack').firstElementChild).toContainElement(
      screen.getByTestId('market-decision-semantics-strip'),
    );
    expect(screen.getByTestId('market-overview-top-stack')).toContainElement(screen.getByTestId('market-overview-category-tabs'));
    const categoryScroller = screen.getByTestId('market-overview-category-tabs').querySelector('.ui-scroll-x-quiet');
    expect(categoryScroller).not.toBeNull();
    expect(categoryScroller).toHaveClass('max-w-full', 'overflow-x-auto', 'overscroll-x-contain');
    expect(screen.getByTestId('market-overview-top-stack')).toContainElement(screen.getByTestId('market-overview-hero-ribbon'));
  });

  it('keeps mobile overview cards wrap-safe at 390px instead of truncating first-read evidence copy', async () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 390 });
    window.dispatchEvent(new Event('resize'));

    render(createElement(MarketOverviewPage));

    const visualCard = await screen.findByTestId('market-overview-visual-card-core-trends');
    const visualTitle = within(visualCard).getByTestId('market-overview-visual-card-title-core-trends');
    const visualEyebrow = within(visualCard).getByTestId('market-overview-visual-card-eyebrow-core-trends');
    const summaryStrip = screen.getByTestId('market-overview-summary-strip');

    expect(summaryStrip).toHaveClass('grid-cols-1');
    expect(visualTitle).toHaveClass('break-words', 'whitespace-normal');
    expect(visualEyebrow).toHaveClass('break-words', 'whitespace-normal');
    expect(screen.getByTestId('market-overview-top-verdict')).toHaveClass('break-words');
  });

  it('puts market state and compact data status ahead of controls and panel sprawl', async () => {
    render(createElement(MarketOverviewPage));

    const topStack = await screen.findByTestId('market-overview-top-stack');
    const decisionReadiness = screen.getByTestId('market-overview-decision-readiness');
    expect(topStack.firstElementChild).toContainElement(screen.getByTestId('market-decision-semantics-strip'));
    expect(topStack.querySelectorAll('[data-market-research-flow="research-workbench"]')).toHaveLength(1);
    expect(screen.getByTestId('market-overview-main-grid').compareDocumentPosition(screen.getByTestId('market-decision-semantics-strip'))).toBe(Node.DOCUMENT_POSITION_PRECEDING);
    expect(screen.queryByTestId('market-overview-research-readiness-strip')).not.toBeInTheDocument();
    expect(screen.getByTestId('market-overview-pulse-header')).toContainElement(screen.getByTestId('market-decision-semantics-strip'));
    expect(screen.getByTestId('market-overview-first-workbench')).toContainElement(screen.getByTestId('market-overview-dominant-path'));
    expect(decisionReadiness.compareDocumentPosition(screen.getByTestId('market-overview-main-grid'))).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(screen.getByTestId('market-overview-main-grid').compareDocumentPosition(screen.getByTestId('market-overview-visual-evidence-strip'))).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it('keeps a single first-read summary zone and leaves evidence details collapsed on the default surface', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: false,
      canReadProviders: false,
    });
    render(createElement(MarketOverviewPage));

    const decisionReadiness = await screen.findByTestId('market-overview-decision-readiness');
    const firstReadSummary = screen.getByRole('region', { name: /首读摘要|first-read summary/i });
    const evidenceDisclosure = screen.getByTestId('market-overview-evidence-disclosure');

    expect(within(decisionReadiness).getByText('市场论点')).toBeInTheDocument();
    expect(within(firstReadSummary).getAllByText('发生了什么')).toHaveLength(1);
    expect(within(firstReadSummary).getAllByText('重要点')).toHaveLength(1);
    expect(within(firstReadSummary).getAllByText('下一步看什么')).toHaveLength(1);
    expect(screen.getAllByText('发生了什么')).toHaveLength(1);
    expect(screen.getAllByText('重要点')).toHaveLength(1);
    expect(screen.getAllByText('下一步看什么')).toHaveLength(1);
    expect(evidenceDisclosure).not.toHaveAttribute('open');
    expect(within(evidenceDisclosure).getByRole('button', { name: '展开 数据说明' })).toBeInTheDocument();
    expect(firstReadSummary.compareDocumentPosition(evidenceDisclosure) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(evidenceDisclosure).queryByText('支持证据')).not.toBeInTheDocument();
    expect(within(evidenceDisclosure).queryByText('反证 / 风险')).not.toBeInTheDocument();
    expect(within(evidenceDisclosure).queryByText('缺失证据')).not.toBeInTheDocument();
    expect(within(evidenceDisclosure).queryByText('下一步观察')).not.toBeInTheDocument();
    expect(screen.queryByTestId('market-decision-debug-details')).not.toBeInTheDocument();
  });

  it('synthesizes first viewport market facts into what happened, what matters, and what to check next', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: false,
      canReadProviders: false,
    });
    vi.mocked(marketOverviewApi.getVolatility).mockResolvedValueOnce(denseQuotePanel('VolatilityCard', [
      quoteItem('VIX', 'VIX', 14.8, -2.4),
      quoteItem('VVIX', 'VVIX', 88.2, -1.1),
    ]));
    vi.mocked(marketApi.getRates).mockResolvedValueOnce(denseQuotePanel('RatesCard', [
      quoteItem('US10Y', 'US 10Y', 4.62, -0.14, 'fred'),
      quoteItem('US2Y', 'US 2Y', 4.91, 0.04, 'fred'),
    ], 'fred'));
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(createElement(MarketOverviewPage));

    const firstReadSummary = await screen.findByRole('region', { name: /首读摘要|first-read summary/i });
    expect(within(firstReadSummary).getByText('发生了什么')).toBeInTheDocument();
    expect(within(firstReadSummary).getByText('重要点')).toBeInTheDocument();
    expect(within(firstReadSummary).getByText('下一步看什么')).toBeInTheDocument();
    await waitFor(() => expect(firstReadSummary).toHaveTextContent(/VIX.*-2\.40%/));
    expect(firstReadSummary).toHaveTextContent(/US ?10Y.*-0\.14%/);
    expect(firstReadSummary).toHaveTextContent(/BTC|Bitcoin/);
    expect(firstReadSummary.textContent || '').not.toMatch(/sourceAuthority|score-grade|provider|cache|runtime|schema|proxy|fallback/i);
    expect(screen.queryByTestId('market-command-chips')).not.toBeInTheDocument();
  });

  it('renders each tab with deterministic row groups and the shared decision layer', async () => {
    render(createElement(MarketOverviewPage));

    const expectations: Array<[string, string[], string[]]> = [
      ['全部', ['all-hero', 'all-modules-1', 'all-modules-2', 'all-modules-3'], ['market-overview-card-indices', 'market-overview-card-sentiment']],
      ['美股', ['us-hero', 'us-modules-1', 'us-modules-2', 'us-modules-3'], ['market-overview-card-indices', 'market-overview-card-usBreadth']],
      ['A股/港股', ['cn-hero', 'cn-modules-1', 'cn-modules-2', 'cn-modules-3'], ['market-overview-card-cnIndices', 'market-overview-card-cnShortSentiment']],
      ['全球宏观', ['global-hero', 'global-modules-1', 'global-modules-2'], ['market-overview-card-rates', 'market-overview-card-globalRisk']],
      ['加密货币', ['crypto-hero', 'crypto-modules-1', 'crypto-modules-2'], ['market-overview-card-cryptoCore', 'market-overview-card-cryptoLiquidity']],
    ];

    for (const [tab, rowIds, visibleCards] of expectations) {
      fireEvent.click(await screen.findByRole('button', { name: tab }));
      const heroLane = await screen.findByTestId('market-overview-hero-lane');
      const secondaryGrid = screen.getByTestId('market-overview-secondary-grid');
      visibleCards.forEach((testId) => {
        expect(screen.getByTestId(testId)).toBeInTheDocument();
      });
      expect(getRowIds()).toEqual(rowIds);
      expect(screen.getByTestId('market-decision-semantics-strip')).toBeInTheDocument();
      expect(heroLane).toHaveAttribute('data-card-tier', 'hero');
      expect(secondaryGrid).toHaveAttribute('data-card-tier', 'secondary');
      if (tab === '全部' || tab === '美股' || tab === 'A股/港股') {
        expect(screen.getByTestId('market-overview-deep-panels')).toHaveAttribute('data-card-tier', 'deep');
      } else {
        expect(screen.queryByTestId('market-overview-deep-panels')).not.toBeInTheDocument();
      }
    }
  });

  it('renders bounded market row layout with value, change, and constrained sparkline', () => {
    render(
      <UiLanguageProvider>
        <MarketDataRow
          item={{
            ...quoteItem('VERY-LONG-SYMBOL-NAME', 'Very Long Cross Market Instrument Name That Must Truncate', 5120.25, 0.42),
            hoverDetails: ['extra source detail'],
          }}
          neutralLabel="中性"
        />
      </UiLanguageProvider>,
    );

    const row = screen.getByTestId('market-overview-data-row');
    expect(row).toHaveAttribute('data-row-layout', 'bounded-market-row');
    expect(row).toHaveClass('min-w-0', 'overflow-hidden');
    expect(within(row).getByTestId('market-overview-quote-value')).toHaveClass('text-right', 'font-mono');
    expect(within(row).getByTestId('market-overview-quote-change')).toHaveClass('text-right', 'font-mono');
    expect(within(row).getByTestId('market-overview-dense-quote-sparkline')).toHaveClass('w-[64px]');
  });

  it('places quote metadata in a compact middle column instead of a right-side stack', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
    ]));

    render(createElement(MarketOverviewPage));

    const indicesCard = await screen.findByTestId('market-overview-card-indices');
    await waitFor(() => {
      expect(within(indicesCard).getAllByTestId('market-overview-dense-quote-item').length).toBeGreaterThan(0);
    });
    const firstQuote = within(indicesCard).getAllByTestId('market-overview-dense-quote-item')[0];
    const metadata = within(firstQuote).getByTestId('market-overview-quote-metadata');
    const valueBlock = within(firstQuote).getByTestId('market-overview-quote-value');
    const changeBlock = within(firstQuote).getByTestId('market-overview-quote-change');

    expect(metadata).toHaveAttribute('data-metadata-position', 'middle-left');
    expect(metadata).toHaveClass('col-start-2', 'whitespace-nowrap', 'overflow-hidden');
    expect(metadata).not.toHaveClass('col-span-3', 'justify-end');
    expect(metadata).toHaveTextContent(/2026/);
    expect(metadata).not.toHaveTextContent(/Yahoo Finance/);
    expect(metadata).not.toHaveTextContent(/Quote/);
    expect(metadata).not.toHaveTextContent(/Update/);
    expect(metadata).toHaveAttribute('title', expect.stringContaining('2026'));
    expect(metadata.getAttribute('title') || '').not.toMatch(/Yahoo Finance|Provider|source/i);
    expect(valueBlock).toHaveClass('col-start-4', 'text-right');
    expect(changeBlock).toHaveClass('col-start-5', 'text-right');
  });

  it('translates raw provider and proxy copy into consumer-safe market labels', async () => {
    vi.mocked(marketApi.getSentiment).mockResolvedValueOnce({
      ...sentimentPanel(),
      items: [
        sentimentPanel().items[0],
        {
          symbol: 'PUTCALL',
          label: 'Put/Call',
          value: 0.92,
          unit: 'ratio',
          changePct: null,
          riskDirection: 'neutral' as const,
          trend: [0.95, 0.92],
          hoverDetails: [
            'ETF flow proxy',
            'Institutional pressure proxy',
            'Industry breadth proxy',
            'Rotation Non Scoring Or Taxonomy Only',
            'REAL',
            'MIXED',
            'freshness=unavailable',
            'Sector ETF proxy 暂不可用',
          ],
        },
        {
          symbol: 'AAII',
          label: 'AAII',
          value: 38,
          unit: 'score',
          changePct: -2,
          riskDirection: 'increasing' as const,
          trend: [41, 39, 38],
          hoverDetails: ['PROVIDER ALTERNATIVE_ME'],
        },
      ],
    });
    vi.mocked(marketApi.getCnShortSentiment).mockResolvedValueOnce({
      ...cnShortSentimentPayload(),
      source: 'ALTERNATIVE_ME',
      sourceLabel: 'PROVIDER ALTERNATIVE_ME',
      updatedAt: '',
      asOf: undefined,
    });

    render(createElement(MarketOverviewPage));

    await waitFor(() => {
      expect(document.body.textContent || '').toMatch(/ETF 资金流指标|机构压力指标|行业广度指标|数据新鲜度暂不可用/);
    });

    const renderedCopy = document.body.textContent || '';
    expect(renderedCopy).toMatch(/ETF 资金流指标|机构压力指标|行业广度指标|部分可用|延迟可用|证据不足|仅供观察|数据新鲜度暂不可用/);
    expect(renderedCopy).not.toMatch(
      /PROVIDER ALTERNATIVE_ME|ETF flow proxy|Institutional pressure proxy|Industry breadth proxy|Rotation Non Scoring Or Taxonomy Only|Sector ETF proxy|Alternative\.me|Yahoo Finance|Binance Futures|YFINANCE|CBOE|BINANCE|REAL|MIXED|FALLBACK|freshness=unavailable|providerClass|providerName|providerAttempted|requiredProviderClass|sourceAuthorityRouter|endpointHost|apiKeyPresent|exceptionClass|exceptionChain|requestId|traceId|cacheKey|rawPayload|credential|token|env|sourceTier|sourceLabel|reasonCode|diagnosticOnly|scoreContributionAllowed|sourceAuthorityAllowed|authorityGrant|raw|debug|backend|cache|schema|synthetic|mock|proxy|fallback/i,
    );
  });

  it('maps rotation_non_scoring_or_taxonomy_only to consumer-safe Chinese copy', () => {
    expect(marketIntelligenceReasonLabel('rotation_non_scoring_or_taxonomy_only', 'zh')).toBe('轮动证据仅作分类参考');
    expect(marketIntelligenceReasonLabel('Rotation Non Scoring Or Taxonomy Only', 'zh')).toBe('轮动证据仅作分类参考');
  });

  it('maps consumer-safety blocked reason codes to calm market copy', () => {
    expect(marketIntelligenceReasonLabel('freshness_blocked:fallback', 'zh')).toBe('当前以延迟或替代数据为主，先保持观察。');
    expect(marketIntelligenceReasonLabel('source_authority_or_score_gate_blocked', 'zh')).toBe('当前来源授权或评分条件未满足，暂不形成进一步判断。');
    expect(marketIntelligenceReasonLabel('avoidLowEvidence', 'zh')).toBe('当前证据质量偏弱，先保持观察。');
  });

  it('copies a market intelligence evidence snapshot from the current visible state', async () => {
    render(createElement(MarketOverviewPage));

    const exportButton = await screen.findByTestId('market-overview-export-summary');
    await waitFor(() => expect(screen.getByTestId('market-overview-top-verdict')).toHaveTextContent('偏强观察'));
    expect(exportButton).toHaveTextContent('复制证据快照');
    expect(exportButton).not.toHaveTextContent('摘要');
    fireEvent.click(exportButton);

    await waitFor(() => expect(writeTextMock).toHaveBeenCalledTimes(1));
    const copiedText = String(writeTextMock.mock.calls[0]?.[0] || '');
    expect(copiedText).toMatch(/# (Market Intelligence Evidence Snapshot|市场情报证据快照) \| 全部/);
    expect(copiedText).toContain('## Market regime observation');
    expect(copiedText).toContain('## Evidence used');
    expect(copiedText).toContain('## Evidence gaps');
    expect(copiedText).toContain('## Data freshness');
    expect(copiedText).toContain('## Research next steps');
    expect(copiedText).toContain('## No-advice disclosure');
    expect(copiedText).toContain('## Generated timestamp');
    expect(copiedText).toContain('- 市场温度: 偏暖 (62)');
    expect(copiedText).toMatch(/- 数据质量: (延迟可用|部分数据暂不可用)/);
    expect(copiedText).not.toMatch(/provider_timeout|sourceAuthorityAllowed|scoreContributionAllowed|raw|debug|trace|schema|MarketCache|buy|sell|target price|position sizing|买入|卖出|目标价|止损|仓位/i);
    expect(await screen.findByText('证据快照已复制')).toBeInTheDocument();
  });

  it('shows a clear failure state when evidence snapshot copy fails', async () => {
    writeTextMock.mockRejectedValueOnce(new Error('clipboard denied'));

    render(createElement(MarketOverviewPage));

    const exportButton = await screen.findByTestId('market-overview-export-summary');
    await waitFor(() => expect(screen.getByTestId('market-overview-top-verdict')).toHaveTextContent('偏强观察'));
    fireEvent.click(exportButton);

    await waitFor(() => expect(writeTextMock).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('复制失败，请重试')).toBeInTheDocument();
    expect(exportButton).not.toHaveTextContent('摘要');
  });

  it('shows a calm unavailable state when evidence snapshot copy inputs are missing', () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: undefined,
    });

    renderMarketOverviewWorkbench();

    const exportButton = screen.getByTestId('market-overview-export-summary');
    expect(exportButton).toBeDisabled();
    expect(exportButton).toHaveTextContent('证据快照暂不可用');
    expect(exportButton).toHaveAttribute('aria-label', '证据快照暂不可用');
  });

  it('resets copied feedback when switching evidence snapshot categories', async () => {
    render(createElement(MarketOverviewPage));

    const exportButton = await screen.findByTestId('market-overview-export-summary');
    await waitFor(() => expect(screen.getByTestId('market-overview-top-verdict')).toHaveTextContent('偏强观察'));
    fireEvent.click(exportButton);

    expect(await screen.findByText('证据快照已复制')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '美股' }));

    expect(screen.getByTestId('market-overview-export-summary')).toHaveTextContent('复制证据快照');
  });

  it('filters China indices out of the US core index card', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
      quoteItem('DJI', 'Dow Jones', 38920.18, -0.12),
      quoteItem('000001.SH', '上证指数', 3120.55, 0.39, 'sina'),
      quoteItem('399001.SZ', '深证成指', 9842.31, -0.18, 'sina'),
    ]));

    render(createElement(MarketOverviewPage));

    fireEvent.click(await screen.findByRole('button', { name: '美股' }));

    const indicesCard = await screen.findByTestId('market-overview-card-indices');
    expect(within(indicesCard).getByText('标普500')).toBeInTheDocument();
    expect(within(indicesCard).getByText('纳斯达克100')).toBeInTheDocument();
    expect(within(indicesCard).queryByText('上证指数')).not.toBeInTheDocument();
    expect(within(indicesCard).queryByText('深证成指')).not.toBeInTheDocument();
  });

  it('uses professional Chinese display names where market mappings exist', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
      quoteItem('DJI', 'Dow Jones', 38920.18, -0.12),
      quoteItem('RUT', 'Russell 2000', 2088.5, 0.21),
    ]));
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce(denseQuotePanel('ChinaIndicesCard', [
      quoteItem('000001.SH', 'Shanghai Composite', 3120.55, 0.39, 'sina'),
      quoteItem('399001.SZ', 'Shenzhen Component', 9842.31, -0.18, 'sina'),
      quoteItem('000300.SH', 'CSI 300', 3588.12, 0.44, 'sina'),
      quoteItem('HSI', 'Hang Seng Index', 17712.5, 0.73, 'sina'),
      quoteItem('HSTECH', 'Hang Seng TECH', 3650.1, 0.62, 'sina'),
    ], 'mixed'));
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());
    vi.mocked(marketApi.getRates).mockResolvedValueOnce(denseQuotePanel('RatesCard', [
      quoteItem('US10Y', 'US 10Y', 4.62, -0.14),
    ]));
    vi.mocked(marketApi.getFxCommodities).mockResolvedValueOnce(denseQuotePanel('FxCommoditiesCard', [
      quoteItem('DXY', 'US Dollar Index', 106.2, 0.2),
      quoteItem('GOLD', 'Gold', 2380.3, 0.5),
      quoteItem('WTI', 'WTI Crude', 78.4, -0.3),
    ]));

    renderMarketOverviewWithLanguage('zh');

    const indicesCard = await screen.findByTestId('market-overview-card-indices');
    await waitFor(() => {
      expect(within(indicesCard).getByText('标普500')).toBeInTheDocument();
      expect(within(indicesCard).getByText('纳斯达克100')).toBeInTheDocument();
      expect(within(indicesCard).getByText('道琼斯工业平均指数')).toBeInTheDocument();
      expect(within(indicesCard).getByText('罗素2000')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    const cnIndicesCard = await screen.findByTestId('market-overview-card-cnIndices');
    await waitFor(() => {
      expect(within(cnIndicesCard).getByText('上证指数')).toBeInTheDocument();
      expect(within(cnIndicesCard).getByText('深证成指')).toBeInTheDocument();
      expect(within(cnIndicesCard).getByText('沪深300')).toBeInTheDocument();
      expect(within(cnIndicesCard).getByText('恒生指数')).toBeInTheDocument();
      expect(within(cnIndicesCard).getByText('恒生科技指数')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    const cryptoCard = await screen.findByTestId('market-overview-card-cryptoCore');
    await waitFor(() => {
      expect(within(cryptoCard).getByText('比特币')).toBeInTheDocument();
      expect(within(cryptoCard).getByText('以太坊')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '全球宏观' }));
    await waitFor(() => {
      expect(screen.getAllByText('美国10年期国债收益率').length).toBeGreaterThan(0);
      expect(screen.getAllByText('美元指数').length).toBeGreaterThan(0);
      expect(screen.getAllByText('黄金').length).toBeGreaterThan(0);
      expect(screen.getAllByText('WTI 原油').length).toBeGreaterThan(0);
    });
  });

  it('keeps English display names in English UI', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
    ]));
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    renderMarketOverviewWithLanguage('en');

    expect((await screen.findAllByText('S&P 500')).length).toBeGreaterThan(0);
    expandMarketEvidenceDetails();
    expect(screen.getByTestId('market-overview-regime-summary-lane')).toHaveTextContent('Market Bias / Direction Summary');
    expect(screen.getByTestId('market-overview-regime-summary-lane')).toHaveTextContent('Current market:');
    fireEvent.click(screen.getByRole('button', { name: 'US' }));
    expect(screen.getAllByText('Nasdaq 100').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Bitcoin').length).toBeGreaterThan(0);
    expect(screen.queryByText('标普500')).not.toBeInTheDocument();
    expect(screen.queryByText('比特币')).not.toBeInTheDocument();
  });

  it('renders a top directional summary for mixed low-confidence evidence', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: false,
      canReadProviders: false,
    });
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(limitedRealTemperaturePayload());
    vi.mocked(marketApi.getMarketBriefing).mockResolvedValueOnce(unreliableBriefingPayload());

    render(createElement(MarketOverviewPage));

    const conclusion = await screen.findByTestId('market-overview-decision-readiness');
    expect(conclusion).toHaveTextContent('市场论点');
    expect(conclusion).toHaveTextContent('发生了什么');
    expect(conclusion).toHaveTextContent('重要点');
    expect(conclusion).toHaveTextContent('下一步看什么');
    expect(conclusion.textContent || '').not.toMatch(/买入|卖出|买卖|target|stop|recommend/i);
    expandMarketEvidenceDetails();
    await screen.findByTestId('market-overview-direction-summary');
    const summary = screen.getByTestId('market-overview-direction-summary');
    expect(summary).toHaveTextContent('市场方向摘要');
    expect(summary).toHaveTextContent(/当前市场：证据不足|Current market: Evidence insufficient/);
    expect(summary).toHaveTextContent(/主要拖累|关键阻力/);
    expect(summary).toHaveTextContent('A股宽度');
    expect(summary).toHaveTextContent('比特币');
    expect(summary).toHaveTextContent(/可观察方向|下一步观察/);
    expect(summary.textContent || '').not.toMatch(/买入|卖出|买卖|加仓|减仓|仓位|建议买入|建议卖出|buy now|sell now|target|stop|recommend/i);
    expect(summary.textContent || '').not.toMatch(/marketOverviewPage\./);
  });

  it('renders decision readiness states for ready, observation-only, and unavailable overview evidence', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: false,
      canReadProviders: false,
    });
    const readyView = render(createElement(MarketOverviewPage));

    const readyBand = await screen.findByTestId('market-overview-decision-readiness');
    expect(readyBand).toHaveTextContent('市场论点');
    expect(readyBand).toHaveTextContent('发生了什么');
    expect(readyBand).toHaveTextContent('重要点');
    expect(readyBand).toHaveTextContent('下一步看什么');
    await waitFor(() => expect(readyBand).toHaveTextContent('中等'));
    expect(readyBand).toHaveTextContent(/偏强观察|中性观察|偏弱观察|数据不足/);
    expect(within(readyBand).queryByText('查看需配置的数据源')).not.toBeInTheDocument();
    expect(readyBand.textContent || '').not.toMatch(/买入|卖出|买卖|buy now|sell now|target|stop|recommend/i);
    readyView.unmount();

    vi.clearAllMocks();
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce({
      ...temperaturePayload(),
      confidence: 0.42,
      reliableInputCount: 2,
      reliablePanelCount: 2,
      isReliable: false,
      temperatureAvailable: true,
      conclusionAllowed: false,
      marketDecisionSemantics: {
        ...marketDecisionSemanticsPayload(),
        posture: 'neutral',
        postureConfidence: {
          value: 42,
          label: 'low',
          capReasons: ['insufficient_score_grade_evidence'],
        },
        directionReadiness: {
          status: 'partial_context_only',
          confidenceLabel: 'low',
          scoreGradePillars: {
            count: 1,
            items: [
              { pillar: 'official_macro_rates_volatility', label: 'Official macro/rates/volatility', reasonCode: 'score_grade_evidence' },
            ],
          },
          observationOnlyPillars: {
            count: 2,
            items: [
              { pillar: 'rotation_or_risk_participation', label: 'Rotation/risk participation', reasonCode: 'observation_only_evidence' },
              { pillar: 'liquidity_conditions', label: 'Liquidity/conditions', reasonCode: 'fallback_or_proxy_evidence' },
            ],
          },
          missingPillars: {
            count: 1,
            items: [
              { pillar: 'breadth_health', label: 'Breadth health', reasonCode: 'missing_scoring_evidence' },
            ],
          },
          blockingReasons: ['insufficient_score_grade_evidence'],
          claimBoundaries: [
            { claim: 'market_direction_readiness_context', allowed: false, reasonCode: 'partial_context_only' },
          ],
          notInvestmentAdvice: true,
        },
      },
    });
    vi.mocked(marketApi.getMarketBriefing).mockResolvedValueOnce(unreliableBriefingPayload());

    const observationView = render(createElement(MarketOverviewPage));
    await screen.findByTestId('market-overview-decision-readiness');
    await waitFor(() => expect(screen.getByTestId('market-overview-decision-readiness')).toHaveTextContent(/偏强观察|中性观察|偏弱观察|数据不足/));
    const observationBand = screen.getByTestId('market-overview-decision-readiness');
    expect(observationBand).toHaveTextContent(/偏强观察|中性观察|偏弱观察|数据不足/);
    expect(observationBand).toHaveTextContent('重要点');
    expect(observationBand).toHaveTextContent('下一步看什么');
    expect(observationBand).toHaveTextContent('有限');
    expect(observationBand).toHaveTextContent('标普500');
    expect(observationBand).toHaveTextContent(/信心水平：有限|有限/);
    expect(observationBand).not.toHaveTextContent('partial_context_only');
    expect(within(observationBand).queryByTestId('market-overview-setup-path')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '展开 技术细节' })).not.toBeInTheDocument();
    observationView.unmount();

    vi.clearAllMocks();
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(unreliableTemperaturePayload());
    vi.mocked(marketApi.getMarketBriefing).mockResolvedValueOnce(unreliableBriefingPayload());

    const unavailableView = render(createElement(MarketOverviewPage));
    await screen.findByTestId('market-overview-decision-readiness');
    await waitFor(() => expect(screen.getByTestId('market-overview-decision-readiness')).toHaveTextContent(/数据不足|偏强观察|中性观察|偏弱观察/));
    const unavailableBand = screen.getByTestId('market-overview-decision-readiness');
    expect(unavailableBand).toHaveTextContent(/数据不足|偏强观察|中性观察|偏弱观察/);
    expect(unavailableBand).toHaveTextContent('信心水平：待补');
    expect(unavailableBand).toHaveTextContent(/关键证据未补齐|关键证据仍待补齐|关键确认仍待补齐|评分待恢复|数据更新中/);
    expect(within(unavailableBand).queryByTestId('market-overview-setup-path')).not.toBeInTheDocument();
    unavailableView.unmount();
  });

  it('downgrades unreliable market temperature and briefing copy', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(unreliableTemperaturePayload());
    vi.mocked(marketApi.getMarketBriefing).mockResolvedValueOnce(unreliableBriefingPayload());

    render(createElement(MarketOverviewPage));

    const details = expandMarketDecisionDetails();
    await waitFor(() => {
      expect(within(details).getByTestId('market-overview-temperature-summary')).toHaveTextContent('可靠输入不足');
    });
    const temperatureSummary = within(details).getByTestId('market-overview-temperature-summary');
    expect(temperatureSummary).toHaveTextContent('可靠输入不足');
    expect(temperatureSummary).toHaveTextContent('暂不判定');
    expect(temperatureSummary).not.toHaveTextContent('N/A');
    expect(within(details).getByTestId('market-temperature-unreliable-summary')).toHaveTextContent('可靠输入不足，暂不生成综合判断');
    expect(within(details).getByText(/可靠输入不足，暂不生成综合判断/i)).toBeInTheDocument();
    expect(within(details).getByText(/信号可信：数据不足/i)).toBeInTheDocument();
    expect(screen.queryByText(/综合市场温度/i)).not.toBeInTheDocument();
    await waitFor(() => {
      expect(within(details).getByTestId('market-regime-synthesis-title')).toHaveTextContent('数据不足');
    });
    expect(within(details).getByTestId('market-regime-synthesis-state-chip')).toHaveTextContent('证据不足');
    expect(within(details).getByTestId('market-regime-synthesis-confidence-chip')).toHaveTextContent('数据不足 · 22%');
    expect(within(details).getByTestId('market-regime-synthesis-summary')).toHaveTextContent('当前覆盖或置信度不足');
    expect(within(details).getByTestId('market-regime-synthesis-data-gaps')).toHaveTextContent(/A股宽度/);
    expect(screen.getByTestId('market-overview-rail-action-hint')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/A股宽度|US10Y|VIX|DXY/);
    expect(within(details).getByTestId('market-briefing-warning')).toHaveTextContent('当前关键数据不足，暂不生成强市场判断');
    expect(screen.getByTestId('market-decision-semantics-advice-boundary')).toHaveTextContent(/证据待补|偏强观察|中性观察|偏弱观察/);
  });

  it('renders a compact observational posture panel from market decision semantics', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: false,
      canReadProviders: false,
    });
    render(createElement(MarketOverviewPage));

    const posturePanel = await screen.findByTestId('market-decision-semantics-strip');

    expect(posturePanel).toHaveTextContent('市场论点');
    expect(posturePanel).toHaveTextContent('数据说明');
    expect(posturePanel).toHaveTextContent('重要点');
    expect(posturePanel).toHaveTextContent('下一步看什么');
    expect(posturePanel).not.toHaveTextContent('主要阻断原因');
    expect(posturePanel).not.toHaveTextContent('下一步需要的数据/配置');
    expect(posturePanel).not.toHaveTextContent('Liquidity beta watch');
    expect(posturePanel).not.toHaveTextContent('Remove the risk-on watch if liquidity turns mixed or contracting.');
    expect(posturePanel).not.toHaveTextContent('liquidity_stops_expanding');
    expect(posturePanel).toHaveTextContent(/研究观察，不构成投资建议/);
    expect(posturePanel).not.toHaveTextContent('counter_evidence_present');
    expect(posturePanel).not.toHaveTextContent('not_investment_advice');
    expect(within(posturePanel).queryByTestId('market-decision-debug-details')).not.toBeInTheDocument();

    const readinessBand = screen.getByTestId('market-overview-decision-readiness');
    expect(readinessBand).toHaveTextContent(/市场论点/);
    expect(readinessBand).toHaveTextContent(/偏强观察|中性观察|偏弱观察|数据不足|事实有限|证据待补/);

    const evidence = expandMarketEvidenceDetails();
    const regimeLane = await screen.findByTestId('market-overview-regime-summary-lane');
    const synthesisBlock = await within(regimeLane).findByTestId('market-regime-synthesis-research-block');
    const synthesisText = synthesisBlock.textContent || '';
    expect(synthesisBlock).toHaveTextContent('市场状态综合');
    expect(synthesisBlock).toHaveTextContent('风险偏好修复 / 流动性扩张');
    expect(synthesisBlock).toHaveTextContent('风险支持观察');
    expect(synthesisBlock).toHaveTextContent('置信上限');
    expect(synthesisBlock).toHaveTextContent('中 · 58%');
    expect(synthesisBlock).toHaveTextContent('时效');
    expect(synthesisBlock).toHaveTextContent('延迟可用');
    expect(synthesisBlock).toHaveTextContent('证据家族');
    expect(synthesisBlock).toHaveTextContent('支持证据');
    expect(synthesisBlock).toHaveTextContent('反证');
    expect(synthesisBlock).toHaveTextContent('缺失证据');
    expect(synthesisBlock).toHaveTextContent('下一步研究');
    expect(synthesisBlock).toHaveTextContent('复核反证');
    expect(synthesisText).not.toMatch(/contractVersion|risk_supportive|marketOverview|confidenceCap|observationBoundary|no_advice|sourceAuthorityAllowed|scoreContributionAllowed|reason|debug|raw|provider|cache|runtime|confidenceCapReason|sourceAuthorityReason|freshnessReason|nextDiagnostic|consumerSafeSummary|scoreGradeInputs|blockedInputs|observationOnlyInputs/i);
    expect(synthesisText).not.toMatch(/买入|卖出|下单|交易建议|投资建议|target|stop|position|recommend|buy|sell/i);

    expect(evidence).toHaveTextContent('支持证据');
    expect(evidence).toHaveTextContent('反证 / 风险');
    expect(evidence).toHaveTextContent('缺失证据');
    expect(evidence).toHaveTextContent('下一步观察');
    expect(evidence).toHaveTextContent('Liquidity beta watch');
    expect(evidence).toHaveTextContent('Liquidity impulse should remain expanding.');
    expect(evidence).toHaveTextContent('Remove the risk-on watch if liquidity turns partial or contracting.');
    expect(evidence).toHaveTextContent('US10Y');
    expect(evidence).toHaveTextContent('Fed liquidity');
  });

  it('keeps regimeSummary on the default regime lane with consumer-safe observation wording', async () => {
    render(createElement(MarketOverviewPage));

    const regimeLane = await screen.findByTestId('market-overview-regime-summary-lane');
    const regimeSummary = await within(regimeLane).findByTestId('market-overview-regime-summary');
    const regimeSummaryText = regimeSummary.textContent || '';

    expect(regimeSummaryText).toContain('风险偏好修复仍以观察为主');
    expect(regimeSummaryText).toContain('偏观察的风险偏好修复');
    expect(regimeSummaryText).toContain('中 · 62%');
    expect(regimeSummaryText).toContain('流动性与成长轮动仍支持风险偏好修复观察');
    expect(regimeSummaryText).toContain('流动性改善');
    expect(regimeSummaryText).toContain('A股宽度确认不足');
    expect(regimeSummaryText).toContain('美国10年期国债收益率');
    expect(regimeSummaryText).toContain('小盘轮动延续');
    expect(regimeSummaryText).not.toContain('diagnosticOnly');
    expect(regimeSummaryText).not.toContain('observationOnly');
    expect(regimeSummaryText).not.toContain('sourceAuthorityAllowed');
    expect(regimeSummaryText).not.toContain('scoreContributionAllowed');
    expect(regimeSummaryText).not.toContain('partial_context_only');
    expect(regimeSummaryText).not.toContain('watch:liquidity_impulse');
    expect(regimeSummaryText).not.toMatch(/买入|卖出|交易指令|评分级别|score[-\s]?grade|investment advice/i);
  });

  it('renders a compact broad-market trend chart from SPY proxy data with consumer-safe labeling', async () => {
    const basePanels = localSnapshotPayload().payload;
    renderMarketOverviewWorkbenchWithProps({
      panels: {
        ...basePanels,
        indices: denseQuotePanel('IndexTrendsCard', [
          {
            ...quoteItem('SPY', 'SPY', 548.22, 0.64),
            trend: [540.1, 542.4, 541.8, 545.3, 548.22],
            sourceLabel: 'Yahoo Finance',
            asOf: '2026-06-25T20:00:00Z',
            freshness: 'delayed',
          },
          {
            ...quoteItem('QQQ', 'QQQ', 486.1, 0.72),
            trend: [477.5, 480.3, 479.8, 484.9, 486.1],
            sourceLabel: 'Yahoo Finance',
            asOf: '2026-06-25T20:00:00Z',
            freshness: 'delayed',
          },
        ]),
      },
    });

    const chart = await screen.findByTestId('market-overview-core-trend-chart');
    expect(chart).toHaveAttribute('data-chart-kind', 'market-overview-trend');
    expect(chart).toHaveTextContent('广义美股市场趋势');
    expect(chart).toHaveTextContent('SPY proxy for broad US market');
    expect(chart).toHaveTextContent('报价延迟');
    expect(chart).toHaveTextContent('Yahoo Finance');
    expect(chart).toHaveTextContent('+0.64%');
    const chartFrame = within(chart).getByTestId('market-overview-core-trend-chart-frame');
    expect(chartFrame).toHaveAttribute('data-chart-engine', 'echarts');
    expect(chartFrame).toHaveAttribute('data-render-mode', 'line');
    expect(chartFrame).toHaveAttribute('data-volume-panel', 'false');
    expect(chartFrame).toHaveAttribute('data-enabled-overlays', 'none');
    expect(within(chartFrame).getByTestId('core-market-chart-frame')).toBeInTheDocument();
    expect(within(chart).queryByText(/provider_missing|data_disabled|sourceClass|local_bounded_us_parquet_universe|noExternalCalls|providerCallsEnabled|contractVersion/i)).not.toBeInTheDocument();
    expect(chart).not.toHaveTextContent(/buy|sell|hold|entry|exit|target|stop-loss|accumulate|reduce|overweight|underweight|买入|卖出|持有|目标价|止损|仓位/i);
  });

  it('keeps default consumer market overview surfaces free of raw evidence metadata vocabulary', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: false,
      canReadProviders: false,
    });
    render(createElement(MarketOverviewPage));

    const readinessBand = await screen.findByTestId('market-overview-decision-readiness');
    expect(readinessBand).toBeInTheDocument();

    expandMarketEvidenceDetails();
    await screen.findByTestId('market-overview-direction-summary');

    const titleText = Array.from(document.querySelectorAll<HTMLElement>('[title]'))
      .map((node) => node.getAttribute('title') || '')
      .join(' ');
    const visibleText = `${document.body.textContent || ''} ${titleText}`;

    expect(visibleText).not.toMatch(
      /sourceAuthorityAllowed|scoreContributionAllowed|observationOnly|reasonCodes?|reasonFamilies|routeRejectedReasonCodes|providerHealth|provider_runtime|sourceTier|trustLevel|debugRef|schemaVersion|MarketCache|runtime|internal|fallback_static|synthetic_fixture|official_public|authorized_licensed_feed|public_proxy|unofficial_public/i,
    );
    expect(visibleText).not.toContain('score_contribution_not_allowed');
    expect(visibleText).not.toMatch(/仅供界面演示|备用示例|保持界面结构|等待真实行情源|数据源异常/);
  });

  it('reveals technical diagnostics only in admin mode', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: true,
      canReadProviders: true,
    });
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(unreliableTemperaturePayload());
    vi.mocked(marketApi.getMarketBriefing).mockResolvedValueOnce(unreliableBriefingPayload());
    render(createElement(MarketOverviewPage));

    const posturePanel = await screen.findByTestId('market-decision-semantics-strip');
    const debug = within(posturePanel).getByTestId('market-decision-debug-details');
    expect(debug).not.toHaveAttribute('open');

    fireEvent.click(within(debug).getByRole('button', { name: '展开 技术细节' }));

    expect(await within(debug).findByTestId('market-overview-official-macro-diagnostics')).toBeInTheDocument();
    expect(within(debug).getByText('insufficient_score_grade_evidence')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-setup-path')).toBeInTheDocument();
  });

  it('keeps data-insufficient posture conservative without trading advice language', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: false,
      canReadProviders: false,
    });
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(unreliableTemperaturePayload());
    vi.mocked(marketApi.getMarketBriefing).mockResolvedValueOnce(unreliableBriefingPayload());

    render(createElement(MarketOverviewPage));

    const posturePanel = await screen.findByTestId('market-decision-semantics-strip');
    const text = posturePanel.textContent || '';

    expect(posturePanel).toHaveTextContent(/数据不足|偏强观察|中性观察|偏弱观察/);
    expect(posturePanel).toHaveTextContent(/关键证据未补齐|关键证据仍待补齐|关键确认仍待补齐|信号置信度仍偏有限|评分待恢复|数据更新中/);
    expect(posturePanel).toHaveTextContent(/待补|待确认|更新中/);
    expect(posturePanel).toHaveTextContent(/研究观察，不构成投资建议/);
    expect(posturePanel).toHaveTextContent(/可见事实有限|等待.*证据补齐|下一步看什么/);
    expect(posturePanel).not.toHaveTextContent('missing_scoring_pillars');
    const readinessBand = screen.getByTestId('market-overview-decision-readiness');
    expect(readinessBand).toHaveTextContent(/数据不足|偏强观察|中性观察|偏弱观察/);
    expect(readinessBand).toHaveTextContent(/关键证据未补齐|关键证据仍待补齐|关键确认仍待补齐|信号置信度仍偏有限|评分待恢复|数据更新中/);
    expect(readinessBand).not.toHaveTextContent('fallback_proxy_or_observation_only_evidence_present');
    expect(screen.getByTestId('market-decision-semantics-strip')).not.toHaveTextContent('fallback_proxy_or_observation_only_evidence_present');
    expect(text).not.toMatch(/买入|卖出|买卖|加仓|减仓|仓位|看多|看空|bullish|bearish|buy|sell|target|stop|recommend|add|reduce|position-size/i);
  });

  it('hides regime synthesis research blocks when the temperature payload omits the additive field', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce({
      source: 'computed',
      sourceLabel: '系统计算',
      updatedAt: '2026-04-29T10:00:00',
      asOf: '2026-04-29T10:00:00',
      freshness: 'cached',
      isFallback: false,
      confidence: 0.18,
      reliableInputCount: 1,
      requiredReliableInputCount: 5,
      reliablePanelCount: 1,
      requiredReliablePanelCount: 3,
      fallbackInputCount: 3,
      excludedInputCount: 2,
      isReliable: false,
      temperatureAvailable: false,
      disabledReason: 'insufficient_reliable_inputs',
      unavailableReason: 'insufficient_reliable_inputs',
      insufficientReliableInputs: true,
      trustLevel: 'weak',
      sourceTier: 'unofficial_public_api',
      conclusionAllowed: false,
      scores: {
        liquidity: { value: 51, label: '中性', trend: 'stable', description: '流动性输入部分可用。' },
      },
    } as never);

    render(createElement(MarketOverviewPage));

    expect(await screen.findByTestId('market-overview-shell')).toBeInTheDocument();
    const details = expandMarketDecisionDetails();
    const evidence = expandMarketEvidenceDetails();
    expect(within(details).getByTestId('market-temperature-unreliable-summary')).toHaveTextContent('可靠输入不足，暂不生成综合判断');
    expect(within(details).getByTestId('market-overview-temperature-summary')).toHaveTextContent(/可靠输入不足|暂不判定/);
    expect(within(details).getByTestId('market-overview-temperature-summary')).not.toHaveTextContent('N/A');
    expect(screen.getByTestId('market-decision-semantics-advice-boundary')).toHaveTextContent(/证据待补|偏强观察|中性观察|偏弱观察/);
    expect(screen.getByTestId('market-overview-regime-summary-lane')).toBeInTheDocument();
    expect(within(evidence).queryByTestId('market-regime-synthesis-research-block')).not.toBeInTheDocument();
    expect(screen.queryByText(/raw|payload/i)).not.toBeInTheDocument();
  });

  it('keeps the reliable-inputs fallback copy when additive flags are omitted but counts are still insufficient', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce({
      source: 'computed',
      sourceLabel: '系统计算',
      updatedAt: '2026-04-29T10:00:00',
      asOf: '2026-04-29T10:00:00',
      freshness: 'cached',
      isFallback: false,
      confidence: 0.18,
      reliableInputCount: 1,
      requiredReliableInputCount: 5,
      reliablePanelCount: 1,
      requiredReliablePanelCount: 3,
      fallbackInputCount: 3,
      excludedInputCount: 2,
      isReliable: false,
      temperatureAvailable: false,
      trustLevel: 'weak',
      sourceTier: 'unofficial_public_api',
      conclusionAllowed: false,
      scores: {
        liquidity: { value: 51, label: '中性', trend: 'stable', description: '流动性输入部分可用。' },
      },
    } as never);

    render(createElement(MarketOverviewPage));

    expect(await screen.findByTestId('market-overview-shell')).toBeInTheDocument();
    const details = expandMarketDecisionDetails();
    expect(within(details).getByTestId('market-temperature-unreliable-summary')).toHaveTextContent('可靠输入不足，暂不生成综合判断');
    expect(within(details).getByTestId('market-overview-temperature-summary')).not.toHaveTextContent('N/A');
  });

  it('shows limited real temperature inputs instead of collapsing them to zero', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(limitedRealTemperaturePayload());

    render(createElement(MarketOverviewPage));

    const details = expandMarketDecisionDetails();
    const summary = await within(details).findByTestId('market-temperature-unreliable-summary');
    expect(summary).toHaveTextContent('可靠输入不足，暂不生成综合判断');
    await waitFor(() => {
      expect(summary).toHaveTextContent('可靠输入不足，暂不生成综合判断');
      expect(within(details).getByTestId('market-temperature-strip')).toHaveTextContent(/真实 2.*备用 10.*排除 10/i);
    });
    expect(screen.queryByText(/R 0/i)).not.toBeInTheDocument();
  });

  it('does not overstate top status when delayed and proxy panels are mostly usable', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
      quoteItem('DJI', 'Dow Jones', 38920.18, -0.12),
    ]));
    vi.mocked(marketOverviewApi.getVolatility).mockResolvedValueOnce(denseQuotePanel('VolatilityCard', [
      quoteItem('VIX', 'VIX', 14.8, -2.4),
      quoteItem('VVIX', 'VVIX', 88.2, -1.1),
    ]));
    vi.mocked(marketOverviewApi.getFundsFlow).mockResolvedValueOnce(denseQuotePanel('FundsFlowCard', [
      quoteItem('SPY_FLOW', 'SPY Flow', 2.1, 2.1),
      quoteItem('QQQ_FLOW', 'QQQ Flow', 1.7, 1.7),
    ], 'yahoo'));
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce(denseQuotePanel('ChinaIndicesCard', [
      quoteItem('000300.SH', 'CSI 300', 3588.12, 0.44, 'sina'),
      quoteItem('HSI', 'Hang Seng Index', 17712.5, 0.73, 'sina'),
      {
        ...quoteItem('HSTECH', 'Hang Seng TECH', 3650.1, 0.62, 'fallback'),
        source: 'fallback',
        sourceLabel: '备用数据',
        freshness: 'fallback' as const,
        isFallback: true,
      },
    ], 'mixed'));
    vi.mocked(marketApi.getRates).mockResolvedValueOnce(denseQuotePanel('RatesCard', [
      quoteItem('US10Y', 'US 10Y', 4.62, -0.14, 'fred'),
      quoteItem('US2Y', 'US 2Y', 4.91, 0.04, 'fred'),
      quoteItem('US30Y', 'US 30Y', 4.74, -0.08, 'treasury'),
    ], 'fred'));
    vi.mocked(marketApi.getFxCommodities).mockResolvedValueOnce(denseQuotePanel('FxCommoditiesCard', [
      quoteItem('DXY', 'US Dollar Index', 106.2, 0.2, 'yfinance_proxy'),
      quoteItem('USDJPY', 'USD/JPY', 155.9, 0.1, 'yfinance_proxy'),
      {
        ...quoteItem('USDCNH', 'USD/CNH', 7.24, 0.2, 'fallback'),
        source: 'fallback',
        sourceLabel: '备用数据',
        freshness: 'fallback' as const,
        isFallback: true,
      },
    ], 'mixed'));
    vi.mocked(marketApi.getUsBreadth).mockResolvedValueOnce(usBreadthPanel());
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(limitedRealTemperaturePayload());
    vi.mocked(marketApi.getMarketBriefing).mockResolvedValueOnce(unreliableBriefingPayload());

    render(createElement(MarketOverviewPage));

    const topVerdict = await screen.findByTestId('market-overview-top-verdict');
    await waitFor(() => expect(topVerdict).toHaveTextContent(/偏强观察|中性观察|偏弱观察/));
    expect(topVerdict).not.toHaveTextContent('数据不足');
    expect(screen.getByTestId('market-decision-semantics-strip')).toHaveTextContent(/信号置信度仍偏有限|关键证据未补齐|待补/);
    const railActionHint = screen.queryByTestId('market-overview-rail-action-hint');
    if (railActionHint) {
      expect(railActionHint).not.toHaveTextContent(/等待实时源补齐后再生成强判断/);
    }
    expect(screen.queryByText(/等待实时源补齐后再生成强判断/)).not.toBeInTheDocument();
  });

  it('keeps a warning top status when visible panels are fallback-heavy', async () => {
    renderMarketOverviewWorkbenchWithProps({
      panels: {
        indices: snapshotPanel('IndexTrendsCard', 'SPX', 'S&P 500'),
        volatility: snapshotPanel('VolatilityCard', 'VIX', 'VIX'),
        crypto: snapshotPanel('CryptoCard', 'BTC', 'Bitcoin'),
        sentiment: snapshotPanel('MarketSentimentCard', 'FGI', 'Fear & Greed'),
        fundsFlow: snapshotPanel('FundsFlowCard', 'ETF', 'ETF'),
        macro: snapshotPanel('MacroIndicatorsCard', 'US10Y', 'US 10Y'),
        cnIndices: snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
        cnBreadth: snapshotPanel('ChinaBreadthCard', 'BREADTH', '赚钱效应'),
        cnFlows: snapshotPanel('ChinaFlowsCard', 'NORTHBOUND', '北向资金'),
        sectorRotation: snapshotPanel('SectorRotationCard', 'AI', 'AI / 算力'),
        usBreadth: usBreadthUnavailablePanel(),
        rates: snapshotPanel('RatesCard', 'US10Y', 'US 10Y'),
        fxCommodities: snapshotPanel('FxCommoditiesCard', 'DXY', 'DXY'),
        temperature: unreliableTemperaturePayload(),
        briefing: unreliableBriefingPayload(),
        futures: futuresPayload(),
        cnShortSentiment: cnShortSentimentPayload(),
      },
    });

    expect(screen.getByTestId('market-decision-semantics-advice-boundary')).toHaveTextContent(/证据待补|偏强观察|中性观察|偏弱观察/);
    expect(screen.getByTestId('market-decision-semantics-strip')).toHaveTextContent(/关键证据未补齐|评分待恢复|待补/);
  });

  it('uses a refresh-state top status only while the overview is truly refreshing', async () => {
    renderMarketOverviewWorkbenchWithProps({
      loading: true,
      showAdminDiagnostics: true,
      panels: {
        ...localSnapshotPayload({
          indices: snapshotPanel('IndexTrendsCard', 'SPX', 'S&P 500'),
          volatility: snapshotPanel('VolatilityCard', 'VIX', 'VIX'),
          crypto: snapshotPanel('CryptoCard', 'BTC', 'Bitcoin'),
          fundsFlow: snapshotPanel('FundsFlowCard', 'ETF', 'ETF'),
          macro: snapshotPanel('MacroIndicatorsCard', 'US10Y', 'US 10Y'),
          cnIndices: snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
          cnBreadth: snapshotPanel('ChinaBreadthCard', 'BREADTH', '赚钱效应'),
          cnFlows: snapshotPanel('ChinaFlowsCard', 'NORTHBOUND', '北向资金'),
          sectorRotation: snapshotPanel('SectorRotationCard', 'AI', 'AI / 算力'),
          usBreadth: usBreadthUnavailablePanel(),
          rates: snapshotPanel('RatesCard', 'US10Y', 'US 10Y'),
          fxCommodities: snapshotPanel('FxCommoditiesCard', 'DXY', 'DXY'),
          temperature: unreliableTemperaturePayload(),
          briefing: unreliableBriefingPayload(),
          futures: futuresPayload(),
          cnShortSentiment: cnShortSentimentPayload(),
        }).payload,
      },
    });

    expect(screen.getByTestId('market-decision-semantics-advice-boundary')).toHaveTextContent(/数据不足|偏强观察|中性观察|偏弱观察|证据待补/);
    expect(screen.getByTestId('market-decision-semantics-strip')).toHaveTextContent(/正在更新|更新中/);
    const details = expandMarketDecisionDetails();
    expect(within(details).getByTestId('market-overview-cache-status')).toHaveTextContent(/刷新中/i);
  });

  it('does not force indices and fundsFlow into the side rail globally', async () => {
    render(createElement(MarketOverviewPage));

    const primaryPath = await screen.findByTestId('market-overview-first-workbench');
    const sideRail = screen.getByTestId('market-overview-side-rail');

    expect(screen.getByTestId('market-overview-shell')).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(screen.getByTestId('market-overview-shell')).toHaveClass('w-full', 'flex-1', 'max-w-[var(--wolfy-consumer-shell-max,1880px)]');
    expect(screen.getByTestId('market-overview-workbench')).toHaveClass('bento-surface-root', 'w-full', 'flex-1');
    expect(screen.getByTestId('market-overview-workbench')).not.toHaveClass('mx-auto', 'max-w-[1800px]');
    expect(primaryPath).toContainElement(screen.getByTestId('market-overview-card-indices'));
    expect(primaryPath).toContainElement(screen.getByTestId('market-overview-card-fundsFlow'));
    expect(sideRail).not.toContainElement(screen.getByTestId('market-overview-card-indices'));
    expect(sideRail).not.toContainElement(screen.getByTestId('market-overview-card-fundsFlow'));
  });

  it('has no side rail internal scroll and makes wide primary cards span columns', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
      source: 'mixed',
      sourceLabel: 'Sina + 备用数据',
      freshness: 'delayed' as const,
      isFallback: false,
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300').items[0],
          source: 'sina',
          sourceLabel: 'Sina',
          freshness: 'delayed' as const,
          isFallback: false,
        },
        snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
      ],
    });
    render(createElement(MarketOverviewPage));

    const sideRail = await screen.findByTestId('market-overview-side-rail');
    expect(sideRail.className).not.toContain('max-h-[800px]');
    expect(sideRail.className).not.toContain('overflow-y-auto');
    expect(getRowCardOrder('all-hero')).toEqual(['indices', 'volatility', 'fundsFlow']);
    expect(document.querySelector('[data-row-id="all-hero"]')).toHaveAttribute('data-row-columns', '3');
    expect(screen.getByTestId('market-overview-card-indices')).toHaveAttribute('data-market-card-row', 'hero');
    expect(screen.getByTestId('market-overview-card-volatility')).toHaveAttribute('data-market-card-row', 'hero');
    expect(screen.getByTestId('market-overview-card-fundsFlow')).toHaveAttribute('data-market-card-row', 'hero');
    expect(screen.getByTestId('market-overview-secondary-group-cn')).toHaveClass('min-w-0');
    expect(screen.getByTestId('market-overview-card-crypto')).toHaveClass('min-w-0', 'w-full');
    expect(screen.queryByText('实时行情')).not.toBeInTheDocument();
  });

  it('keeps the primary market cards in a stable responsive grid below desktop', async () => {
    render(createElement(MarketOverviewPage));

    const primaryPath = await screen.findByTestId('market-overview-first-workbench');
    expect(primaryPath).toHaveClass('grid', 'gap-4');
    expect(primaryPath).toHaveAttribute('data-market-research-flow', 'primary-market-path');
    expect(screen.getByTestId('market-overview-hero-lane')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-secondary-grid')).toBeInTheDocument();
    expect(primaryPath).not.toHaveClass('stealth-scrollbar', 'overflow-x-auto', 'overscroll-x-contain');
    expect(screen.getByTestId('market-overview-card-indices')).toHaveClass('min-w-0', 'w-full');
  });

  it('renders quote-heavy primary cards as dense responsive quote grids', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
      quoteItem('DJI', 'Dow Jones', 38920.18, -0.12),
      quoteItem('RUT', 'Russell 2000', 2088.5, 0.21),
    ]));
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce(denseQuotePanel('ChinaIndicesCard', [
      quoteItem('000001.SH', '上证指数', 3120.55, 0.39, 'sina'),
      quoteItem('000300.SH', '沪深300', 3588.12, 0.44, 'sina'),
      quoteItem('399001.SZ', '深证成指', 9842.31, -0.18, 'sina'),
      quoteItem('HSI', '恒生指数', 17712.5, 0.73, 'sina'),
    ], 'mixed'));
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(createElement(MarketOverviewPage));

    const primaryPath = await screen.findByTestId('market-overview-first-workbench');
    for (const cardKey of ['indices', 'crypto'] as const) {
      const card = await screen.findByTestId(`market-overview-card-${cardKey}`);
      if (cardKey === 'indices') {
        expect(primaryPath).toContainElement(card);
      } else {
        expect(screen.getByTestId('market-overview-secondary-grid')).toContainElement(card);
      }
      expect(card).toHaveAttribute('data-market-card-size', cardKey === 'indices' ? 'large' : 'list');
      expect(card).toHaveAttribute('data-market-card-density', 'dense-quote');
      const grid = within(card).getByTestId('market-overview-dense-quote-grid');
      expect(grid).toHaveClass('flex', 'flex-col', 'border-y');
      expect(within(grid).getAllByTestId('market-overview-dense-quote-item').length).toBeGreaterThanOrEqual(2);
    }

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    const cnIndicesCard = await screen.findByTestId('market-overview-card-cnIndices');
    expect(screen.getByTestId('market-overview-hero-lane')).toContainElement(cnIndicesCard);
    expect(cnIndicesCard).toHaveAttribute('data-market-card-size', 'large');
  });

  it('uses compact quote item grids without a flexible empty sparkline region', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
    ]));

    render(createElement(MarketOverviewPage));

    const indicesCard = await screen.findByTestId('market-overview-card-indices');
    const firstQuote = await waitFor(() => within(indicesCard).getAllByTestId('market-overview-dense-quote-item')[0]);
    expect(firstQuote).toHaveAttribute('data-quote-item-layout', 'compact-grid');
    expect(firstQuote).toHaveClass('grid', 'min-w-0', 'grid-cols-[minmax(96px,1fr)_minmax(104px,0.9fr)_76px_minmax(82px,max-content)_minmax(92px,max-content)]');
    expect(indicesCard.className).toContain("[&_[data-testid='market-overview-dense-quote-grid']]:overflow-x-hidden");
    expect(indicesCard.className).toContain("[&_[data-testid='market-overview-dense-quote-item']]:grid-cols-[minmax(0,1fr)_minmax(0,0.72fr)_minmax(44px,56px)_minmax(62px,max-content)_minmax(64px,max-content)]");
    expect(indicesCard.className).toContain("max-[520px]:[&_[data-testid='market-overview-dense-quote-sparkline']]:hidden");
    expect(within(firstQuote).getByTestId('market-overview-quote-metadata')).toHaveClass('col-start-2');
    const sparklineSlot = within(firstQuote).getByTestId('market-overview-dense-quote-sparkline');
    expect(sparklineSlot.className).toContain('w-[76px]');
    expect(sparklineSlot.className).not.toContain('flex-1');
    expect(within(firstQuote).getByTestId('market-overview-quote-value')).toHaveClass('col-start-4');
    expect(within(firstQuote).getByTestId('market-overview-quote-change')).toHaveClass('col-start-5');
    expect(within(firstQuote).getByText('标普500')).toBeInTheDocument();
    expect(within(firstQuote).getByText('SPX')).toBeInTheDocument();
    expect(within(firstQuote).getByText('5,120.25')).toBeInTheDocument();
    expect(within(firstQuote).getByTestId('data-freshness-badge-delayed')).toBeInTheDocument();
  });

  it('keeps quote-heavy cards out of the insight rail and reserves it for compact helpers', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce(denseQuotePanel('ChinaIndicesCard', [
      quoteItem('000001.SH', '上证指数', 3120.55, 0.39, 'sina'),
      quoteItem('000300.SH', '沪深300', 3588.12, 0.44, 'sina'),
    ], 'mixed'));
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(createElement(MarketOverviewPage));

    const sideRail = await screen.findByTestId('market-overview-side-rail');
    expect(sideRail).not.toContainElement(screen.getByTestId('market-overview-card-indices'));
    expect(sideRail).not.toContainElement(screen.queryByTestId('market-overview-card-cnIndices'));
    expect(sideRail).not.toContainElement(screen.getByTestId('market-overview-card-crypto'));
    expect(sideRail).toContainElement(screen.getByTestId('market-data-quality'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-rail-signal-watch'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-rail-action-hint'));
    expect(sideRail).not.toContainElement(screen.queryByTestId('market-briefing-card'));
    expect(screen.getByTestId('market-overview-context-rail')).toBeInTheDocument();
    expect(sideRail.className).not.toContain('max-h');
    expect(sideRail.className).not.toContain('overflow-y-auto');
  });

  it('keeps temperature and briefing summaries compact while moving data quality into the data-state strip', async () => {
    render(createElement(MarketOverviewPage));

    const details = expandMarketDecisionDetails();
    const statusStrip = within(details).getByTestId('market-overview-status-strip');
    expect(statusStrip).toHaveClass('grid', 'grid-cols-1', 'gap-3');
    expect(statusStrip).toContainElement(within(details).getByTestId('market-overview-temperature-summary'));
    expect(statusStrip).toContainElement(within(details).getByTestId('market-overview-briefing-summary'));
    expect(within(details).getByTestId('market-temperature-strip')).toBeInTheDocument();
    expect(statusStrip).toContainElement(await within(details).findByTestId('market-temperature-strip'));
    expect(statusStrip).toContainElement(within(details).getByTestId('market-briefing-card'));
    expect(within(details).getByTestId('market-overview-data-state-strip')).toHaveTextContent(/数据状态/);
    expect(within(details).getByTestId('market-overview-data-state-strip')).toHaveTextContent(/备用数据/);
  });

  it('keeps decision debug shared types in a neutral module', () => {
    expect(marketOverviewDecisionDebugDetailsSource).not.toContain("from './MarketOverviewWorkbenchTopSurface'");
    expect(marketOverviewDecisionDebugDetailsSource).toContain("from './marketOverviewDecisionTypes'");
    expect(marketOverviewTopSurfaceSource).toContain("from './marketOverviewDecisionTypes'");
  });

  it('keeps VIX risk module high priority in US and global views', async () => {
    vi.mocked(marketOverviewApi.getVolatility).mockResolvedValueOnce(denseQuotePanel('VolatilityCard', [
      quoteItem('VIX', 'VIX', 17.8, -2.4),
      quoteItem('VVIX', 'VVIX', 86.1, -1.2),
    ]));
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce(denseQuotePanel('ChinaIndicesCard', [
      quoteItem('000001.SH', '上证指数', 3120.55, 0.39, 'sina'),
    ], 'mixed'));
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());
    vi.mocked(marketApi.getRates).mockResolvedValueOnce(panel('RatesCard', 'US10Y', 'US 10Y'));

    render(createElement(MarketOverviewPage));

    fireEvent.click(await screen.findByRole('button', { name: '美股' }));
    expect(getRowCardOrder('us-hero')).toEqual(['indices']);
    expect(getRowCardOrder('us-modules-1')).toEqual(['volatility', 'usRates']);
    expect(within(screen.getByTestId('market-overview-card-volatility')).getByText('VIX 恐慌指数')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '全球宏观' }));
    expect(getRowCardOrder('global-hero')).toEqual(['rates']);
    expect(getRowCardOrder('global-modules-1')).toEqual(['fxCommodities', 'globalRisk']);
  });

  it('keeps deterministic workstation card order for every category', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
      source: 'mixed',
      sourceLabel: 'Sina + 备用数据',
      freshness: 'delayed' as const,
      isFallback: false,
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300').items[0],
          source: 'sina',
          sourceLabel: 'Sina',
          freshness: 'delayed' as const,
          isFallback: false,
        },
        snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
      ],
    });
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());
    vi.mocked(marketApi.getRates).mockResolvedValueOnce(panel('RatesCard', 'US10Y', 'US 10Y'));

    render(createElement(MarketOverviewPage));

    await screen.findByTestId('market-overview-primary-rail');
    await waitFor(() => {
      expect(getRowIds()).toEqual(['all-hero', 'all-modules-1', 'all-modules-2', 'all-modules-3']);
    });
    expect(getRowCardOrder('all-hero')).toEqual(['indices', 'volatility', 'fundsFlow']);
    expect(getRowCardOrder('all-modules-1')).toEqual(['sentiment', 'rates']);
    expect(getRowCardOrder('all-modules-2')).toEqual(['fxCommodities', 'crypto']);
    expect(getRowCardOrder('all-modules-3')).toEqual(['cnIndices']);
    expect(screen.getByTestId('market-overview-deep-panels')).toContainElement(screen.getByTestId('market-overview-executive-secondary-groups'));
    expect(getSideCardOrder()).toEqual([]);

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    expect(getRowIds()).toEqual(['us-hero', 'us-modules-1', 'us-modules-2', 'us-modules-3']);
    expect(getRowCardOrder('us-hero')).toEqual(['indices']);
    expect(getRowCardOrder('us-modules-1')).toEqual(['volatility', 'usRates']);
    expect(getRowCardOrder('us-modules-2')).toEqual(['sentiment', 'usBreadth']);
    expect(getRowCardOrder('us-modules-3')).toEqual(['usSectorRotation', 'macroContext']);
    expect(getSideCardOrder()).toEqual([]);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expect(getRowIds()).toEqual(['cn-hero', 'cn-modules-1', 'cn-modules-2', 'cn-modules-3']);
    expect(getRowCardOrder('cn-hero')).toEqual(['cnIndices']);
    expect(getRowCardOrder('cn-modules-1')).toEqual(['cnBreadth', 'cnFlows']);
    expect(getRowCardOrder('cn-modules-2')).toEqual(['sectorRotation', 'cnShortSentiment']);
    expect(getRowCardOrder('cn-modules-3')).toEqual(['fxCnhContext']);
    expect(getSideCardOrder()).toEqual([]);

    fireEvent.click(screen.getByRole('button', { name: '全球宏观' }));
    expect(getRowIds()).toEqual(['global-hero', 'global-modules-1', 'global-modules-2']);
    expect(getRowCardOrder('global-hero')).toEqual(['rates']);
    expect(getRowCardOrder('global-modules-1')).toEqual(['fxCommodities', 'globalRisk']);
    expect(getRowCardOrder('global-modules-2')).toEqual(['sentiment', 'volatility']);
    expect(getSideCardOrder()).toEqual([]);
    expect(screen.getByTestId('market-overview-card-globalRisk')).toHaveClass('min-w-0', 'w-full');

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    expect(getRowIds()).toEqual(['crypto-hero', 'crypto-modules-1', 'crypto-modules-2']);
    expect(getRowCardOrder('crypto-hero')).toEqual(['cryptoCore']);
    expect(getRowCardOrder('crypto-modules-1')).toEqual(['cryptoMomentum', 'cryptoLiquidity']);
    expect(getRowCardOrder('crypto-modules-2')).toEqual(['cryptoRiskContext', 'sentiment']);
    expect(getSideCardOrder()).toEqual([]);
    expect(screen.getByTestId('market-overview-card-cryptoCore')).toHaveAttribute('data-market-card-row', 'hero');
  });

  it('keeps mixed data cards in grouped deep panels when the tab uses them as supporting content', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
      source: 'mixed',
      sourceLabel: 'Sina + 备用数据',
      freshness: 'delayed' as const,
      isFallback: false,
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300').items[0],
          source: 'sina',
          sourceLabel: 'Sina',
          freshness: 'delayed' as const,
          isFallback: false,
        },
        {
          ...snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
        },
      ],
    });

    render(createElement(MarketOverviewPage));

    await screen.findByTestId('market-overview-primary-rail');
    expect(screen.getByTestId('market-overview-card-cnIndices')).toHaveAttribute('data-market-overview-module', 'cnSnapshot');
    expect(getRowCardOrder('all-modules-2')).toEqual(['fxCommodities', 'crypto']);
    expect(getRowCardOrder('all-modules-3')).toEqual(['cnIndices']);
    expect(screen.getByTestId('market-overview-secondary-group-cn')).toHaveTextContent(/CN\/HK/);
  });

  it('counts A-share and Hong Kong mixed coverage without marking the category all fallback', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
      source: 'mixed',
      sourceLabel: 'Sina + 备用数据',
      freshness: 'delayed' as const,
      isFallback: false,
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
          source: 'sina',
          sourceLabel: 'Sina',
          freshness: 'delayed' as const,
          isFallback: false,
        },
        {
          ...snapshotPanel('ChinaIndicesCard', 'CN00Y', '富时A50期货').items[0],
        },
      ],
    });

    render(createElement(MarketOverviewPage));

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));

    await waitFor(() => {
      expect(screen.getByTestId('market-overview-coverage-summary')).toHaveTextContent(/数据可用|最近更新：/);
    });
    expect(screen.queryByTestId('market-overview-category-empty-state')).not.toBeInTheDocument();
  });

  it('shows category data coverage while keeping fallback-heavy cards grouped in the workstation', async () => {
    render(createElement(MarketOverviewPage));

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));

    await expectCoverageSummarySettled();

    expect(screen.getByRole('heading', { name: /市场宽度与赚钱效应/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /行业与主题强弱/i })).toBeInTheDocument();
  });

  it('counts a real crypto card in crypto category coverage', async () => {
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(createElement(MarketOverviewPage));

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));

    await waitFor(() => {
      expect(screen.getByTestId('market-overview-coverage-summary')).toHaveTextContent(/数据可用|最近更新：/);
    });
    expect(screen.getByTestId('market-overview-card-cryptoCore').closest('[data-testid="market-overview-first-workbench"]')).toBeTruthy();
  });

  it('renders US breadth and sector health from the depth endpoint', async () => {
    vi.mocked(marketApi.getUsBreadth).mockResolvedValue(usBreadthPanel());

    render(createElement(MarketOverviewPage));

    fireEvent.click(await screen.findByRole('button', { name: '美股' }));

    const breadthCard = await screen.findByTestId('market-overview-card-usBreadth');
    expect(within(breadthCard).getByRole('heading', { name: /市场宽度|美股宽度/i })).toBeInTheDocument();
    expect(breadthCard).toHaveTextContent(/行业强弱快照/);
    await waitFor(() => expect(breadthCard).toHaveTextContent(/Sectors Up|Strongest XLK|RSP vs SPY|当前只能看到局部广度线索/));
    expect(breadthCard).not.toHaveTextContent(/未接入/);
    const truthStrip = within(breadthCard).getByTestId('market-overview-us-breadth-truth-strip');
    expect(truthStrip).toHaveTextContent('宽度仅观察');
    expect(truthStrip).toHaveTextContent(/统计待补|仅作观察/);
    expect(truthStrip).not.toHaveTextContent('评分级证据');
    expect(truthStrip.textContent || '').not.toMatch(/买入|卖出|加仓|减仓|buy|sell|recommend/i);

    const sectorCard = screen.getByTestId('market-overview-card-usSectorRotation');
    await waitFor(() => expect(sectorCard).toHaveTextContent(/Sector Health|Strongest XLK|Weakest XLE/));
  });

  it('renders official full-coverage US breadth as score-grade evidence', async () => {
    renderMarketOverviewWorkbenchWithProps({
      panels: {
        ...localSnapshotPayload().payload,
        usBreadth: officialUsBreadthPanel(),
      },
    });

    fireEvent.click(screen.getByRole('button', { name: '美股' }));

    const breadthCard = await screen.findByTestId('market-overview-card-usBreadth');
    const truthStrip = within(breadthCard).getByTestId('market-overview-us-breadth-truth-strip');
    expect(truthStrip).toHaveTextContent('宽度可参考');
    expect(truthStrip).toHaveTextContent('统计较完整');
    expect(truthStrip).toHaveTextContent('覆盖 7/7');
    expect(truthStrip).toHaveTextContent('当前宽度扩散统计较完整，可与指数和波动一起参考。');
    expect(truthStrip).not.toHaveTextContent('仅观察');
    expect(truthStrip.textContent || '').not.toMatch(/买入|卖出|加仓|减仓|buy|sell|recommend/i);
  });

  it('renders Polygon EOD computed US breadth with visible partial high-low gaps', async () => {
    vi.mocked(marketApi.getUsBreadth).mockResolvedValue(polygonUsBreadthPanel());

    render(createElement(MarketOverviewPage));

    fireEvent.click(await screen.findByRole('button', { name: '美股' }));

    const breadthCard = await screen.findByTestId('market-overview-card-usBreadth');
    await waitFor(() => expect(breadthCard).toHaveTextContent(/上涨\/下跌统计可用，新高\/新低仍待补齐/));
    const truthStrip = within(breadthCard).getByTestId('market-overview-us-breadth-truth-strip');

    expect(breadthCard).toHaveTextContent(/上涨\/下跌统计可用/);
    expect(breadthCard).toHaveTextContent(/高低点宽度缺失/);
    expect(breadthCard).toHaveTextContent(/上涨家数|ADVANCERS/);
    expect(breadthCard).toHaveTextContent(/下跌家数|DECLINERS/);
    expect(breadthCard).toHaveTextContent(/平盘家数|UNCHANGED/);
    expect(breadthCard).toHaveTextContent(/上涨\/下跌比|ADVANCE_DECLINE_RATIO/);
    expect(breadthCard).toHaveTextContent(/NEW_HIGHS/);
    expect(breadthCard).toHaveTextContent(/NEW_LOWS/);
    expect(breadthCard).toHaveTextContent(/HIGH_LOW_RATIO/);
    expect(breadthCard).not.toHaveTextContent(/行业 ETF 代理|RSP vs SPY|IWM vs SPY/);
    expect(truthStrip).toHaveTextContent('宽度仅观察');
    expect(truthStrip).toHaveTextContent('统计待补');
    expect(truthStrip).toHaveTextContent('覆盖 4/7');
    expect(truthStrip).toHaveTextContent(/当前宽度统计仍有缺口，只适合作为辅助观察。/);
    expect(truthStrip).toHaveTextContent(/新高家数|新低家数/);
    expect(truthStrip).not.toHaveTextContent('评分级证据');
    expect(breadthCard.textContent || '').not.toMatch(/买入|卖出|加仓|减仓|buy|sell|add|reduce/i);
  });

  it('keeps US breadth unavailable state compact and honest', async () => {
    renderMarketOverviewWorkbenchWithProps({
      panels: {
        ...localSnapshotPayload().payload,
        usBreadth: usBreadthUnavailablePanel(),
      },
    });

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    const breadthCard = await screen.findByTestId('market-overview-card-usBreadth');
    const truthStrip = within(breadthCard).getByTestId('market-overview-us-breadth-truth-strip');

    await waitFor(() => expect(breadthCard).toHaveTextContent(/数据暂不可用|未接入/));
    expect(breadthCard).toHaveTextContent(/暂不可用|未接入/);
    expect(truthStrip).toHaveTextContent('宽度不足');
    expect(truthStrip).toHaveTextContent('待补数据');
    expect(truthStrip).toHaveTextContent('覆盖 0/7');
    expect(truthStrip).not.toHaveTextContent('评分级证据');
    expect(within(breadthCard).queryByText(/Advance \/ decline：未接入/)).not.toBeInTheDocument();
  });

  it('renders crypto funding and compact unavailable liquidity context without market dumps', async () => {
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(createElement(MarketOverviewPage));

    fireEvent.click(await screen.findByRole('button', { name: '加密货币' }));

    expect(await screen.findByTestId('market-overview-card-cryptoCore')).toHaveTextContent(/Bitcoin|Ethereum|Solana|BNB/);
    expect(screen.getByTestId('market-overview-card-cryptoMomentum')).toHaveTextContent(/Bitcoin|Ethereum|Solana|BNB/);
    const liquidityCard = screen.getByTestId('market-overview-card-cryptoLiquidity');
    expect(liquidityCard).toHaveTextContent(/资金费率|BTC Funding|BTC 资金费率/);
    expect(liquidityCard).toHaveTextContent(/稳定币流动性.*未接入|BTC 占比.*未接入/);
    expect(screen.getByTestId('market-overview-card-cryptoRiskContext')).toHaveTextContent(/DXY|US 10Y|VIX/);
    expect(screen.queryByTestId('market-overview-module-cnHkIndices')).not.toBeInTheDocument();
    expect(screen.queryByTestId('market-overview-module-usIndices')).not.toBeInTheDocument();
  });

  it('does not show an empty state when fallback cards are still useful grouped content', async () => {
    render(createElement(MarketOverviewPage));

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));

    expect(await screen.findByTestId('market-overview-card-cnIndices')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-card-cnBreadth')).toBeInTheDocument();
    expect(screen.queryByTestId('market-overview-category-empty-state')).not.toBeInTheDocument();
  });

  it('keeps fallback-only cards accessible without an empty-state detour', async () => {
    render(createElement(MarketOverviewPage));

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));

    expect(await screen.findByRole('heading', { name: /市场宽度与赚钱效应/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /行业与主题强弱/i })).toBeInTheDocument();
  });

  it('does not show the category empty state when real cards are visible', async () => {
    render(createElement(MarketOverviewPage));

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));

    expect(await screen.findByTestId('market-overview-card-cryptoCore')).toBeInTheDocument();
    expect(screen.queryByTestId('market-overview-category-empty-state')).not.toBeInTheDocument();
    expect(screen.queryByText(/当前分类暂无可用真实数据/i)).not.toBeInTheDocument();
  });

  it('uses REST crypto snapshot first and updates from the realtime stream', async () => {
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(createElement(MarketOverviewPage));

    await waitFor(() => expect(screen.getAllByText('76,837.04').length).toBeGreaterThan(0));
    expect(MockEventSource.instances[0].url).toContain('/api/v1/market/crypto/stream');

    act(() => {
      MockEventSource.instances[0].emit(cryptoLivePanel());
    });

    await waitFor(() => expect(screen.getAllByText('77,001.25').length).toBeGreaterThan(0));
    expect(screen.getAllByTestId('data-freshness-badge-live').length).toBeGreaterThan(0);
    expect(
      screen.getAllByTestId('market-overview-quote-metadata')
        .some((node) => (node.getAttribute('title') || '').includes('2026')),
    ).toBe(true);
    expect(
      screen.getAllByTestId('market-overview-quote-metadata')
        .some((node) => /Binance WS|provider|source/i.test(node.getAttribute('title') || '')),
    ).toBe(false);
  });

  it('keeps the latest crypto snapshot when the realtime stream errors', async () => {
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(createElement(MarketOverviewPage));

    await waitFor(() => expect(screen.getAllByText('76,837.04').length).toBeGreaterThan(0));
    act(() => {
      MockEventSource.instances[0].error();
    });

    expect(screen.getAllByText('76,837.04').length).toBeGreaterThan(0);
    expect(await screen.findByTestId('market-overview-card-crypto')).toBeInTheDocument();
  });

  it('closes the crypto realtime stream on unmount', async () => {
    const view = render(createElement(MarketOverviewPage));

    expect(await screen.findByTestId('market-overview-card-crypto')).toBeInTheDocument();
    const source = MockEventSource.instances[0];
    view.unmount();
    await flushMarketOverviewMicrotasks();

    expect(source.closed).toBe(true);
  });

  it('keeps REST mode when EventSource is unavailable', async () => {
    vi.stubGlobal('EventSource', undefined);
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(createElement(MarketOverviewPage));

    await waitFor(() => expect(screen.getAllByText('76,837.04').length).toBeGreaterThan(0));
    expect(screen.getByTestId('market-overview-card-crypto')).toBeInTheDocument();
    expect(MockEventSource.instances).toHaveLength(0);
  });

  it('keeps consumer freshness states materially distinct', () => {
    render(
      <div>
        {(['live', 'cache', 'stale', 'fallback', 'partial', 'unavailable', 'refreshing', 'error'] as const).map((status) => (
          <DataFreshnessBadge key={status} status={status} />
        ))}
        <DataFreshnessBadge freshness="delayed" />
        <DataFreshnessBadge freshness="proxy" />
      </div>,
    );

    expect(screen.getByText('实时')).toBeInTheDocument();
    expect(screen.getByText('保存快照')).toBeInTheDocument();
    expect(screen.getByText('延迟可读')).toBeInTheDocument();
    expect(screen.getByText('替代快照')).toBeInTheDocument();
    expect(screen.getByText('可能延迟')).toBeInTheDocument();
    expect(screen.getByText('部分可用')).toBeInTheDocument();
    expect(screen.getByText('代理数据')).toBeInTheDocument();
    expect(screen.getByText('暂不可用')).toBeInTheDocument();
    expect(screen.getByText('读取异常')).toBeInTheDocument();
    expect(screen.getByText('更新中')).toBeInTheDocument();
    expect(screen.getByTestId('data-freshness-badge-error')).not.toHaveTextContent('暂不可用');
    expect(screen.getByTestId('data-freshness-badge-fallback')).not.toHaveTextContent('实时');
    expect(screen.getByTestId('data-freshness-badge-proxy')).not.toHaveTextContent('实时');
  });

  it('summarizes mixed market footer timestamps as an evidence window', () => {
    render(
      <UiLanguageProvider>
        <MarketOverviewPanelFooter
          panel={{
            panelName: 'MixedFamilyPanel',
            lastRefreshAt: '2026-04-29T10:20:00+08:00',
            status: 'partial',
            updatedAt: '2026-04-29T10:20:00+08:00',
            asOf: '2026-04-29T10:15:00+08:00',
            freshness: 'cached',
            items: [
              {
                symbol: 'VIX',
                label: 'VIX',
                updatedAt: '2026-04-29T09:35:00+08:00',
                asOf: '2026-04-29T09:30:00+08:00',
                freshness: 'cached',
              },
              {
                symbol: 'DXY',
                label: 'DXY',
                updatedAt: '2026-04-29T10:16:00+08:00',
                asOf: '2026-04-29T10:15:00+08:00',
                freshness: 'delayed',
              },
            ],
          }}
        />
      </UiLanguageProvider>,
    );

    expect(screen.getByTestId('market-overview-footer-meta')).toHaveTextContent('时间窗口 2026-04-29 09:30:00 - 2026-04-29 10:15:00');
  });

  it('shows stale card data as expired data', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数'),
      freshness: 'stale' as const,
      isFallback: false,
      isStale: true,
      warning: '数据可能已过期，请以交易所/券商行情为准',
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
          freshness: 'stale' as const,
          isFallback: false,
          isStale: true,
          warning: '数据可能已过期，请以交易所/券商行情为准',
        },
      ],
    });

    render(createElement(MarketOverviewPage));

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    const details = expandMarketDecisionDetails();
    await waitFor(() => expect(within(details).getByTestId('market-overview-cache-status')).toHaveTextContent(/待刷新/i));
    expect(screen.getAllByText(/数据可能已过期/i).length).toBeGreaterThan(0);
  });

  it('shows snapshot refresh status without clearing stale card data', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数'),
      isRefreshing: true,
      providerHealth: {
        provider: 'sina',
        status: 'refreshing' as const,
        asOf: '2026-04-29T10:00:00',
        updatedAt: '2026-04-29T10:01:00',
        latencyMs: 120,
        errorSummary: null,
        isFallback: false,
        isStale: false,
        isRefreshing: true,
        sourceLabel: 'Sina',
      },
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
          value: 3120.55,
          providerHealth: {
            provider: 'sina',
            status: 'refreshing' as const,
            asOf: '2026-04-29T10:00:00',
            updatedAt: '2026-04-29T10:01:00',
            latencyMs: 120,
            errorSummary: null,
            isFallback: false,
            isStale: false,
            isRefreshing: true,
            sourceLabel: 'Sina',
          },
        },
      ],
    });

    render(createElement(MarketOverviewPage));

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expandPendingDataSourceSection();
    await waitFor(() => expect(screen.getAllByTestId('data-freshness-badge-refreshing').length).toBeGreaterThan(0));
    expect(screen.getAllByText('上证指数').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/3,120.55|3120.55/).length).toBeGreaterThan(0);
  });

  it('switches market categories without refetching all cards', async () => {
    render(createElement(MarketOverviewPage));

    await waitFor(() => expect(marketApi.getCnIndices).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expect(screen.getByRole('button', { name: 'A股/港股' })).toHaveAttribute('aria-pressed', 'true');
    await expectCoverageSummarySettled();
    expect(screen.getByRole('heading', { name: /A股短线情绪/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /A股与港股指数/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /市场宽度与赚钱效应/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /资金流向/i })).toBeInTheDocument();
    expect(getRowCardOrder('cn-hero')).toEqual(['cnIndices']);
    expect(getRowCardOrder('cn-modules-1')).toEqual(['cnBreadth', 'cnFlows']);
    expect(getRowCardOrder('cn-modules-2')).toEqual(['sectorRotation', 'cnShortSentiment']);

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    expect(screen.getByRole('heading', { name: /US Index Core/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /波动率与风险压力/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /US Rates/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /宏观压力/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /情绪与资金面/i })).toBeInTheDocument();
    expect(screen.queryByText('CSI 300')).not.toBeInTheDocument();
    expect(screen.queryByText('Shanghai Composite')).not.toBeInTheDocument();
    expect(screen.queryByText('Shenzhen Component')).not.toBeInTheDocument();
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent('DXY');
    expect(getRowCardOrder('us-hero')).toEqual(['indices']);
    expect(getRowCardOrder('us-modules-1')).toEqual(['volatility', 'usRates']);
    expect(getRowCardOrder('us-modules-2')).toEqual(['sentiment', 'usBreadth']);

    expect(marketApi.getCnIndices).toHaveBeenCalledTimes(1);
    expect(marketApi.getRates).toHaveBeenCalledTimes(1);
  });

  it('keeps other cards visible when one initial API request fails', async () => {
    vi.mocked(marketApi.getCnBreadth).mockRejectedValueOnce(new Error('breadth down'));

    render(createElement(MarketOverviewPage));

    expect(await screen.findByTestId('market-overview-main-grid')).toBeInTheDocument();
    expect(screen.getByTestId('market-decision-semantics-strip')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('heading', { name: /情绪与资金面/i })).toBeInTheDocument());
    await waitFor(() => expect(screen.getByRole('heading', { name: /波动率与风险压力/i })).toBeInTheDocument());
  });

  it('does not block settled cards when global indices request is still pending', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockReturnValueOnce(new Promise(() => {}));

    render(createElement(MarketOverviewPage));

    expect(await screen.findByTestId('market-sentiment-compact-card')).toBeInTheDocument();
    expect((await screen.findAllByText('26')).length).toBeGreaterThan(0);
    expect(screen.getByTestId('market-overview-main-grid')).toBeInTheDocument();
  });

  it('stops showing global indices loading when the request fails', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockRejectedValueOnce(new Error('indices down'));

    render(createElement(MarketOverviewPage));

    expect(await screen.findByTestId('market-overview-card-indices')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /全球核心指数走势/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText(/正在获取最新快照/i)).not.toBeInTheDocument();
    });
    expect(screen.getAllByTestId('data-freshness-badge-error').length).toBeGreaterThan(0);
  });

  it('does not leave crypto loading forever when the initial request is pending', async () => {
    vi.useFakeTimers();
    vi.mocked(marketApi.getCrypto).mockReturnValueOnce(new Promise(() => {}));

    render(createElement(MarketOverviewPage));

    await advanceMarketOverviewTimersByTime(CRYPTO_PENDING_FALLBACK_DELAY_MS);

    expandPendingDataSourceSection();
    expect(screen.getByTestId('market-overview-card-crypto')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /加密货币行情/i })).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-card-crypto')).toHaveTextContent(/部分数据暂不可用|数据更新超时|暂不可用/);
    expect(screen.queryByText('BTC')).not.toBeInTheDocument();
    expect(screen.queryByText('ETH')).not.toBeInTheDocument();
    expect(screen.queryByText('BNB')).not.toBeInTheDocument();
    expect(screen.getAllByTestId('data-freshness-badge-error').length).toBeGreaterThan(0);
    expect(screen.queryByText(/正在获取最新快照/i)).not.toBeInTheDocument();
  });

  it('renders the crypto fallback response as a card with freshness metadata', async () => {
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFallbackPanel());

    render(createElement(MarketOverviewPage));

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    expect(await screen.findByRole('heading', { name: /加密核心/i })).toBeInTheDocument();
    expect((await screen.findAllByText(/75,800/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/3,120/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/590/).length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('data-freshness-badge-fallback').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('data-freshness-badge-fallback').length).toBeGreaterThan(0);
    expect(screen.queryByTestId('data-freshness-badge-live')).not.toBeInTheDocument();
  });

  it('auto revalidates partial refreshing cards and replaces them without manual refresh', async () => {
    vi.useFakeTimers();
    vi.mocked(marketApi.getCrypto)
      .mockResolvedValueOnce(cryptoPartialRefreshingPanel())
      .mockResolvedValueOnce(cryptoFullPanel());

    render(createElement(MarketOverviewPage));

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    await flushMarketOverviewMicrotasks(2);
    expect(screen.getByRole('heading', { name: /加密核心/i })).toBeInTheDocument();
    expect(screen.getAllByTestId('data-freshness-badge-refreshing').length).toBeGreaterThan(0);
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(1);

    await advanceAutoRevalidateObservationWindow();

    expect(marketApi.getCrypto).toHaveBeenCalledTimes(2);
    expect(screen.getAllByText('76,837.04').length).toBeGreaterThan(0);

    await advanceAutoRevalidateObservationWindow();

    expect(marketApi.getCrypto).toHaveBeenCalledTimes(2);
  });

  it('stops auto revalidation after bounded attempts when a card remains partial', async () => {
    vi.useFakeTimers();
    vi.mocked(marketApi.getCrypto).mockResolvedValue(cryptoPartialRefreshingPanel());

    render(createElement(MarketOverviewPage));

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    await flushMarketOverviewMicrotasks(2);
    expect(screen.getByRole('heading', { name: /加密核心/i })).toBeInTheDocument();
    expect(screen.getAllByTestId('data-freshness-badge-refreshing').length).toBeGreaterThan(0);
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(1);

    await advanceAutoRevalidateObservationWindow();
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(2);

    await advanceAutoRevalidateObservationWindow();
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(3);

    await advanceAutoRevalidateObservationWindow();
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(4);

    await advanceAutoRevalidateObservationWindow();

    expect(marketApi.getCrypto).toHaveBeenCalledTimes(4);
  });

  it('uses the same crypto write path for initial load and manual refresh', async () => {
    vi.mocked(marketApi.getCrypto)
      .mockResolvedValueOnce(cryptoFallbackPanel())
      .mockResolvedValueOnce(cryptoFullPanel());

    render(createElement(MarketOverviewPage));

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    expect((await screen.findAllByText('BTC')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('ETH').length).toBeGreaterThan(0);
    expect(screen.getAllByText('BNB').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: /刷新 加密核心/i }));

    await waitFor(() => expect(marketApi.getCrypto).toHaveBeenCalledTimes(2));
    expect(screen.getAllByText('BTC').length).toBeGreaterThan(0);
    expect(screen.getAllByText('ETH').length).toBeGreaterThan(0);
    expect(screen.getAllByText('BNB').length).toBeGreaterThan(0);
    expect((await screen.findAllByText('76,837.04')).length).toBeGreaterThan(0);
  });

  it('keeps other market cards visible when crypto initial API fails', async () => {
    vi.mocked(marketApi.getCrypto).mockRejectedValueOnce(new Error('crypto down'));

    render(createElement(MarketOverviewPage));

    expandPendingDataSourceSection();
    const cryptoCard = await screen.findByTestId('market-overview-card-crypto');
    expect(cryptoCard).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /加密货币行情/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /情绪与资金面/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(cryptoCard).toHaveTextContent(/部分数据暂不可用|数据更新失败|暂不可用/);
    });
    expect(screen.queryByText('BTC')).not.toBeInTheDocument();
    expect(screen.queryByText(/正在获取最新快照/i)).not.toBeInTheDocument();
  });

  it('refreshes only the requested panel when a card refresh icon is clicked', async () => {
    vi.mocked(marketApi.getFutures).mockResolvedValue({
      ...futuresPayload(),
      source: 'computed',
      sourceLabel: '系统计算',
      freshness: 'cached' as const,
      isFallback: false,
      items: futuresPayload().items.map((item) => ({
        ...item,
        source: 'computed',
        sourceLabel: '系统计算',
        freshness: 'cached' as const,
        isFallback: false,
      })),
    });

    render(createElement(MarketOverviewPage));

    await waitFor(() => expect(marketOverviewApi.getMacro).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(marketApi.getFutures).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    fireEvent.click(screen.getByRole('button', { name: /刷新 波动率与风险压力/i }));

    await waitFor(() => {
      expect(marketOverviewApi.getVolatility).toHaveBeenCalledTimes(2);
    });
    expect(marketOverviewApi.getIndices).toHaveBeenCalledTimes(1);
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(1);
    expect(marketApi.getSentiment).toHaveBeenCalledTimes(1);
    expect(marketOverviewApi.getFundsFlow).toHaveBeenCalledTimes(1);
    expect(marketOverviewApi.getMacro).toHaveBeenCalledTimes(1);
    expect(marketApi.getFutures).toHaveBeenCalledTimes(1);
  });

  it('coalesces duplicate in-flight polling refreshes for the same market overview panels', async () => {
    vi.useFakeTimers();
    const setIntervalSpy = vi.spyOn(window, 'setInterval');

    render(createElement(MarketOverviewPage));

    await drainStagedMarketPanelRequests();
    expectMarketPanelRequestsCalledOnce(allMarketPanelRequests);

    const fastCallback = getMarketOverviewIntervalCallback(setIntervalSpy, FAST_MARKET_POLL_INTERVAL_MS);

    const indicesRefresh = createDeferredPromise<ReturnType<typeof panel>>();
    const volatilityRefresh = createDeferredPromise<ReturnType<typeof panel>>();
    const cryptoRefresh = createDeferredPromise<ReturnType<typeof cryptoPanel>>();
    vi.mocked(marketOverviewApi.getIndices).mockReturnValueOnce(indicesRefresh.promise);
    vi.mocked(marketOverviewApi.getVolatility).mockReturnValueOnce(volatilityRefresh.promise);
    vi.mocked(marketApi.getCrypto).mockReturnValueOnce(cryptoRefresh.promise);

    await runMarketOverviewAsyncStep(() => {
      fastCallback();
      fastCallback();
    });

    expect(marketOverviewApi.getIndices).toHaveBeenCalledTimes(2);
    expect(marketOverviewApi.getVolatility).toHaveBeenCalledTimes(2);
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(2);

    await runMarketOverviewAsyncStep(() => {
      indicesRefresh.resolve(panel('IndexTrendsCard', 'SPX'));
      volatilityRefresh.resolve(panel('VolatilityCard', 'VIX'));
      cryptoRefresh.resolve(cryptoPanel());
    });
  });

  it('coalesces manual refresh with an in-flight polling refresh for the same panel', async () => {
    vi.useFakeTimers();
    const setIntervalSpy = vi.spyOn(window, 'setInterval');

    render(createElement(MarketOverviewPage));

    await drainStagedMarketPanelRequests();
    expectMarketPanelRequestsCalledOnce(allMarketPanelRequests);

    const fastCallback = getMarketOverviewIntervalCallback(setIntervalSpy, FAST_MARKET_POLL_INTERVAL_MS);
    const volatilityRefresh = createDeferredPromise<ReturnType<typeof panel>>();
    vi.mocked(marketOverviewApi.getVolatility).mockReturnValueOnce(volatilityRefresh.promise);

    await runMarketOverviewAsyncStep(() => {
      fastCallback();
    });
    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    fireEvent.click(screen.getByRole('button', { name: /刷新 波动率与风险压力/i }));

    expect(marketOverviewApi.getVolatility).toHaveBeenCalledTimes(2);

    await runMarketOverviewAsyncStep(() => {
      volatilityRefresh.resolve(panel('VolatilityCard', 'VIX'));
    });
  });

  it('keeps different panel refreshes independent while one manual refresh is still in flight', async () => {
    const volatilityRefresh = createDeferredPromise<ReturnType<typeof panel>>();
    const sentimentRefresh = createDeferredPromise<ReturnType<typeof sentimentPanel>>();

    render(createElement(MarketOverviewPage));

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    await waitFor(() => expect(marketOverviewApi.getVolatility).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(marketApi.getSentiment).toHaveBeenCalledTimes(1));

    vi.mocked(marketOverviewApi.getVolatility).mockReturnValueOnce(volatilityRefresh.promise);
    vi.mocked(marketApi.getSentiment).mockReturnValueOnce(sentimentRefresh.promise);

    fireEvent.click(screen.getByRole('button', { name: /刷新 波动率与风险压力/i }));
    fireEvent.click(screen.getByRole('button', { name: /刷新 情绪与资金面/i }));

    expect(marketOverviewApi.getVolatility).toHaveBeenCalledTimes(2);
    expect(marketApi.getSentiment).toHaveBeenCalledTimes(2);

    await runMarketOverviewAsyncStep(() => {
      volatilityRefresh.resolve(panel('VolatilityCard', 'VIX'));
      sentimentRefresh.resolve(sentimentPanel());
    });
  });

  it('keeps fallback summary modules visible when new APIs fail', async () => {
    vi.mocked(marketApi.getTemperature).mockRejectedValueOnce(new Error('temperature down'));
    vi.mocked(marketApi.getMarketBriefing).mockRejectedValueOnce(new Error('briefing down'));
    vi.mocked(marketApi.getFutures).mockRejectedValueOnce(new Error('futures down'));
    vi.mocked(marketApi.getCnShortSentiment).mockRejectedValueOnce(new Error('sentiment down'));

    render(createElement(MarketOverviewPage));

    const details = expandMarketDecisionDetails();
    expect(await within(details).findByTestId('market-overview-temperature-summary')).toBeInTheDocument();
    expect(within(details).getByTestId('market-overview-briefing-summary')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    expandPendingDataSourceSection();
    expect(screen.getByRole('heading', { name: /美股宽度/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expandPendingDataSourceSection();
    expect(screen.getByRole('heading', { name: /A股短线情绪/i })).toBeInTheDocument();
  });

  it('keeps stale card data visible while refreshing a single card', async () => {
    let resolveRefresh: ((value: ReturnType<typeof snapshotPanel>) => void) | undefined;
    vi.mocked(marketApi.getCnIndices)
      .mockResolvedValueOnce(snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数'))
      .mockReturnValueOnce(new Promise((resolve) => {
        resolveRefresh = resolve;
      }));

    render(createElement(MarketOverviewPage));

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expandPendingDataSourceSection();
    expect((await screen.findAllByText('上证指数')).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: /刷新 A股与港股指数/i }));
    expect(screen.getAllByText('上证指数').length).toBeGreaterThan(0);

    resolveRefresh?.(snapshotPanel('ChinaIndicesCard', '399001.SZ', '深证成指'));
    expect((await screen.findAllByText('深证成指')).length).toBeGreaterThan(0);
  });

  it('polls market cards in TTL-aware groups instead of one all-panel interval', async () => {
    vi.useFakeTimers();
    const setIntervalSpy = vi.spyOn(window, 'setInterval');
    render(createElement(MarketOverviewPage));

    await drainStagedMarketPanelRequests();
    expectMarketPanelRequestsCalledOnce(allMarketPanelRequests);

    expect(setIntervalSpy).toHaveBeenCalledTimes(3);
    const fastCallback = getMarketOverviewIntervalCallback(setIntervalSpy, FAST_MARKET_POLL_INTERVAL_MS);
    const mediumCallback = getMarketOverviewIntervalCallback(setIntervalSpy, MEDIUM_MARKET_POLL_INTERVAL_MS);
    const slowCallback = getMarketOverviewIntervalCallback(setIntervalSpy, SLOW_MARKET_POLL_INTERVAL_MS);

    fastCallback();
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(2);
    expect(marketOverviewApi.getIndices).toHaveBeenCalledTimes(2);
    expect(marketOverviewApi.getVolatility).toHaveBeenCalledTimes(2);
    expect(marketApi.getSentiment).toHaveBeenCalledTimes(1);
    expect(marketApi.getCnIndices).toHaveBeenCalledTimes(1);
    expect(marketApi.getFutures).toHaveBeenCalledTimes(1);

    mediumCallback();
    expect(marketApi.getCnIndices).toHaveBeenCalledTimes(2);
    expect(marketApi.getCnBreadth).toHaveBeenCalledTimes(2);
    expect(marketApi.getFutures).toHaveBeenCalledTimes(2);
    expect(marketApi.getSentiment).toHaveBeenCalledTimes(1);
    expect(marketApi.getCnFlows).toHaveBeenCalledTimes(1);

    slowCallback();
    expect(marketApi.getSentiment).toHaveBeenCalledTimes(2);
    expect(marketOverviewApi.getMacro).toHaveBeenCalledTimes(2);
    expect(marketApi.getCnFlows).toHaveBeenCalledTimes(2);
    expect(marketApi.getRates).toHaveBeenCalledTimes(2);
    setIntervalSpy.mockRestore();
  });

  it('uses deterministic layout instead of drag-sorted local card order', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
      source: 'mixed',
      sourceLabel: 'Sina + 备用数据',
      freshness: 'delayed' as const,
      isFallback: false,
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300').items[0],
          source: 'sina',
          sourceLabel: 'Sina',
          freshness: 'delayed' as const,
          isFallback: false,
        },
        snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
      ],
    });
    render(createElement(MarketOverviewPage));

    await waitFor(() => expect(marketApi.getCrypto).toHaveBeenCalledTimes(1));

    expect(getRowCardOrder('all-hero')).toEqual(['indices', 'volatility', 'fundsFlow']);
    expect(getRowCardOrder('all-modules-1')).toEqual(['sentiment', 'rates']);
    expect(getRowCardOrder('all-modules-2')).toEqual(['fxCommodities', 'crypto']);
    expect(window.localStorage.getItem('market-overview-order-all')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));

    expect(getRowCardOrder('cn-hero')).toEqual(['cnIndices']);
    expect(getRowCardOrder('cn-modules-1')).toEqual(['cnBreadth', 'cnFlows']);
    expect(window.localStorage.getItem('market-overview-order-cn')).toBeNull();
  });

  it('shows compact official macro authority diagnostics without promoting degraded rows', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: true,
      canReadProviders: true,
    });
    vi.mocked(marketOverviewApi.getMacro).mockResolvedValueOnce(officialMacroPanel());

    render(createElement(MarketOverviewPage));

    const details = expandMarketDecisionDetails();
    const diagnostics = within(details).getByTestId('market-overview-official-macro-diagnostics');
    await waitFor(() => expect(diagnostics).toHaveTextContent('可计分 2'));
    expect(diagnostics).toHaveTextContent('官方 3');
    expect(diagnostics).toHaveTextContent('代理/观察 2');
    expect(diagnostics).toHaveTextContent('缺口 3');
    expect(within(diagnostics).queryByText(/provider_forbidden_for_use_case/, { selector: 'p' })).not.toBeInTheDocument();

    fireEvent.click(within(diagnostics).getByRole('button', { name: '展开 来源覆盖诊断' }));

    expect(diagnostics).toHaveTextContent('官方来源');
    expect(diagnostics).toHaveTextContent('可计分');
    expect(diagnostics).toHaveTextContent('仅观察');
    expect(diagnostics).toHaveTextContent('备用');
    expect(diagnostics).toHaveTextContent('已拒绝');
    expect(diagnostics).toHaveTextContent('provider_forbidden_for_use_case');
    expect(diagnostics).toHaveTextContent('截至 2026-05-20');
    expect(within(diagnostics).getByText(/provider_forbidden_for_use_case/, { selector: 'p' })).toBeVisible();
  });
});
