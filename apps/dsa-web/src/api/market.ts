import apiClient from './index';
import type { MarketDataMeta, MarketOverviewPanel, MarketOverviewItem, MarketProviderHealth } from './marketOverview';
import { toCamelCase } from './utils';
import { API_BASE_URL } from '../utils/constants';
import { buildAbsoluteApiUrl, joinApiPath } from './path';
import { normalizeMarketIntelligenceEvidenceItem } from './marketIntelligenceEvidence';
import type { ResearchReadinessV1 } from '../types/researchReadiness';

const CONSUMER_SOURCE_LABEL_MAP: Record<string, string> = {
  'PROVIDER ALTERNATIVE_ME': '可用',
  ALTERNATIVE_ME: '可用',
  'ALTERNATIVE.ME': '可用',
  YFINANCE: '可用',
  'YAHOO FINANCE': '可用',
  CBOE: '可用',
  BINANCE: '可用',
  'BINANCE FUTURES': '可用',
  'ETF FLOW PROXY': 'ETF 资金流指标',
  'INSTITUTIONAL PRESSURE PROXY': '机构压力指标',
  'INDUSTRY BREADTH PROXY': '行业广度指标',
  'SECTOR ETF PROXY': '部分可用',
  REAL: '可用',
  MIXED: '部分可用',
  'ROTATION NON SCORING OR TAXONOMY ONLY': '轮动仅作分类参考',
  'YAHOO PROXY': '部分可用',
  SINA: '可用',
  'BINANCE WS': '可用',
  'BINANCE + CACHE': '延迟可用',
  'BINANCE PARTIAL SNAPSHOT': '延迟可用',
  'RECENT CACHE': '延迟可用',
  'LOCAL CACHE': '延迟可用',
  FALLBACK: '延迟可用',
  MOCK: '证据不足',
  'SYNTHETIC FIXTURE': '证据不足',
  '备用数据': '延迟可用',
  '最近可用数据': '延迟可用',
  'OFFICIAL MACRO MIX': '可用',
  'NYSE OFFICIAL BREADTH CACHE': '可用',
  'POLYGON GROUPED DAILY': '可用',
  'SINA + YAHOO FINANCE': '部分可用',
  'SINA + 备用数据': '部分可用',
  'NOT RETURNED': '待补数据',
  'FRESHNESS=UNAVAILABLE': '数据新鲜度暂不可用',
  'FRESHNESS UNAVAILABLE': '数据新鲜度暂不可用',
};

const CONSUMER_SOURCE_LABEL_RULES: Array<[RegExp, string]> = [
  [/FRED\s+[A-Z0-9_]+/gi, '可用'],
  [/Yahoo Finance|YFinance|YFINANCE|CBOE|Binance Futures|Binance|Alternative\.?me/gi, '可用'],
  [/ETF flow proxy/gi, 'ETF 资金流指标'],
  [/Institutional pressure proxy/gi, '机构压力指标'],
  [/Industry breadth proxy/gi, '行业广度指标'],
  [/Sector ETF proxy|proxy/gi, '部分可用'],
  [/local cache|recent cache|cache|fallback/gi, '延迟可用'],
  [/mock|synthetic/gi, '证据不足'],
  [/Rotation Non Scoring Or Taxonomy Only/gi, '轮动仅作分类参考'],
  [/freshness\s*=\s*unavailable|freshness unavailable/gi, '数据新鲜度暂不可用'],
];

const CONSUMER_TEXT_RULES: Array<[RegExp, string]> = [
  [/当前真实数据不足/g, '当前关键数据不足'],
  [/市场温度仅供界面演示/g, '暂不形成方向判断'],
  [/当前关键数据不足[，,]\s*暂不形成方向判断。?/g, '数据待补'],
  [/备用示例数据仅用于保持界面结构/g, '最近可用数据仅保留市场结构观察'],
  [/备用示例数据，不代表当前行情/g, '已使用最近一次可用数据，不代表当前实时行情'],
  [/等待真实行情源/g, '等待数据恢复'],
  [/数据源异常/g, '数据更新中'],
  [/数据源暂不可用/g, '部分数据暂不可用'],
  [/数据源刷新失败/g, '数据更新失败'],
  [/数据源请求超时/g, '数据更新超时'],
  [/保持界面结构/g, '保持页面可读'],
  [/界面演示/g, '临时状态展示'],
];

function normalizeConsumerSourceKey(value?: string | null): string {
  return String(value || '').replace(/\s+/g, ' ').trim().toUpperCase();
}

export function normalizeMarketConsumerText(value?: string | null): string | undefined {
  const trimmed = String(value || '').replace(/\s+/g, ' ').trim();
  if (!trimmed) {
    return undefined;
  }

  const exactMatch = CONSUMER_SOURCE_LABEL_MAP[normalizeConsumerSourceKey(trimmed)];
  if (exactMatch) {
    return exactMatch;
  }

  let normalized = trimmed;
  CONSUMER_SOURCE_LABEL_RULES.forEach(([pattern, replacement]) => {
    normalized = normalized.replace(pattern, replacement);
  });
  CONSUMER_TEXT_RULES.forEach(([pattern, replacement]) => {
    normalized = normalized.replace(pattern, replacement);
  });

  return normalized;
}

function normalizeMarketConsumerSourceLabel(sourceLabel?: string | null, source?: string | null): string | undefined {
  return normalizeMarketConsumerText(sourceLabel)
    || normalizeMarketConsumerText(source);
}

function normalizeMarketProviderHealth(providerHealth?: MarketProviderHealth | null): MarketProviderHealth | undefined {
  if (!providerHealth) {
    return undefined;
  }
  return {
    ...providerHealth,
    sourceLabel: normalizeMarketConsumerSourceLabel(providerHealth.sourceLabel, providerHealth.provider) || providerHealth.sourceLabel,
  };
}

function normalizeMarketOverviewItemConsumerCopy(item: MarketOverviewItem): MarketOverviewItem {
  return {
    ...item,
    label: normalizeMarketConsumerText(item.label) || item.label,
    sourceLabel: normalizeMarketConsumerSourceLabel(item.sourceLabel, item.source) || item.sourceLabel,
    providerHealth: normalizeMarketProviderHealth(item.providerHealth) || item.providerHealth,
    warning: normalizeMarketConsumerText(item.warning) || item.warning,
    hoverDetails: Array.isArray(item.hoverDetails)
      ? item.hoverDetails.map((detail) => normalizeMarketConsumerText(detail) || detail)
      : item.hoverDetails,
  };
}

export function normalizeMarketOverviewPanelConsumerCopy<T extends MarketOverviewPanel | null | undefined>(panel: T): T {
  if (!panel) {
    return panel;
  }
  return {
    ...panel,
    sourceLabel: normalizeMarketConsumerSourceLabel(panel.sourceLabel, panel.source) || panel.sourceLabel,
    providerHealth: normalizeMarketProviderHealth(panel.providerHealth) || panel.providerHealth,
    warning: normalizeMarketConsumerText(panel.warning) || panel.warning,
    items: Array.isArray(panel.items) ? panel.items.map(normalizeMarketOverviewItemConsumerCopy) : [],
  } as T;
}

export function normalizeMarketBriefingConsumerCopy<T extends MarketBriefingResponse | null | undefined>(response: T): T {
  if (!response) {
    return response;
  }
  return {
    ...response,
    sourceLabel: normalizeMarketConsumerSourceLabel(response.sourceLabel, response.source) || response.sourceLabel,
    providerHealth: normalizeMarketProviderHealth(response.providerHealth) || response.providerHealth,
    warning: normalizeMarketConsumerText(response.warning) || response.warning,
    items: Array.isArray(response.items)
      ? response.items.map((item) => ({
          ...item,
          title: normalizeMarketConsumerText(item.title) || item.title,
          message: normalizeMarketConsumerText(item.message) || item.message,
        }))
      : [],
  } as T;
}

export function normalizeMarketFuturesConsumerCopy<T extends MarketFuturesResponse | null | undefined>(response: T): T {
  if (!response) {
    return response;
  }
  return {
    ...response,
    sourceLabel: normalizeMarketConsumerSourceLabel(response.sourceLabel, response.source) || response.sourceLabel,
    providerHealth: normalizeMarketProviderHealth(response.providerHealth) || response.providerHealth,
    warning: normalizeMarketConsumerText(response.warning) || response.warning,
    items: Array.isArray(response.items)
      ? response.items.map((item) => ({
          ...item,
          sourceLabel: normalizeMarketConsumerSourceLabel(item.sourceLabel, item.source) || item.sourceLabel,
          providerHealth: normalizeMarketProviderHealth(item.providerHealth) || item.providerHealth,
          warning: normalizeMarketConsumerText(item.warning) || item.warning,
        }))
      : [],
  } as T;
}

export function normalizeCnShortSentimentConsumerCopy<T extends CnShortSentimentResponse | null | undefined>(response: T): T {
  if (!response) {
    return response;
  }
  return {
    ...response,
    sourceLabel: normalizeMarketConsumerSourceLabel(response.sourceLabel, response.source) || response.sourceLabel,
    providerHealth: normalizeMarketProviderHealth(response.providerHealth) || response.providerHealth,
    warning: normalizeMarketConsumerText(response.warning) || response.warning,
    summary: normalizeMarketConsumerText(response.summary) || response.summary,
  } as T;
}

type MarketSnapshotItem = {
  symbol?: string;
  name?: string;
  label?: string;
  price?: number | null;
  value?: number | null;
  change?: number | null;
  changePercent?: number | null;
  changeText?: string | null;
  trend?: number[];
  sparkline?: number[];
  unit?: string | null;
  source?: string | null;
  sourceLabel?: string | null;
  sourceType?: string | null;
  providerHealth?: MarketProviderHealth;
  updatedAt?: string;
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
  isPartial?: boolean;
  isUnavailable?: boolean;
  isRefreshing?: boolean;
  isFromSnapshot?: boolean;
  lastSuccessfulAt?: string;
  refreshError?: string | null;
  lastError?: string | null;
  delayMinutes?: number;
  sourceTier?: string | null;
  trustLevel?: string | null;
  observationOnly?: boolean;
  sourceAuthorityAllowed?: boolean;
  scoreContributionAllowed?: boolean;
  sourceAuthorityReason?: string | null;
  sourceAuthorityRouteRejected?: boolean;
  routeRejectedReasonCodes?: string[];
  reasonCodes?: string[];
  breadthClaimType?: string | null;
  officialExchangePublishedBreadth?: boolean;
  fulfilledMetrics?: string[];
  missingMetrics?: string[];
  metricCoverageRatio?: number | null;
  broadMarketClaimAllowed?: boolean;
  degradationReason?: string | null;
  degradationReasons?: string[];
  warning?: string | null;
  market?: string | null;
  explanation?: string | null;
  hoverDetails?: string[] | null;
  riskDirection?: 'increasing' | 'decreasing' | 'neutral';
};

type MarketSnapshotPayload = {
  items?: MarketSnapshotItem[];
  lastUpdate?: string;
  updatedAt?: string;
  error?: string | null;
  fallbackUsed?: boolean;
  source?: string | null;
  sourceLabel?: string | null;
  sourceType?: string | null;
  providerHealth?: MarketProviderHealth;
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
  isPartial?: boolean;
  isUnavailable?: boolean;
  isRefreshing?: boolean;
  isFromSnapshot?: boolean;
  lastSuccessfulAt?: string;
  refreshError?: string | null;
  lastError?: string | null;
  delayMinutes?: number;
  sourceTier?: string | null;
  trustLevel?: string | null;
  observationOnly?: boolean;
  sourceAuthorityAllowed?: boolean;
  scoreContributionAllowed?: boolean;
  sourceAuthorityReason?: string | null;
  sourceAuthorityRouteRejected?: boolean;
  routeRejectedReasonCodes?: string[];
  reasonCodes?: string[];
  breadthClaimType?: string | null;
  officialExchangePublishedBreadth?: boolean;
  fulfilledMetrics?: string[];
  missingMetrics?: string[];
  metricCoverageRatio?: number | null;
  broadMarketClaimAllowed?: boolean;
  degradationReason?: string | null;
  degradationReasons?: string[];
  warning?: string | null;
  logSessionId?: string | null;
};

function normalizeItem(item: MarketSnapshotItem): MarketOverviewItem {
  const hoverDetails = Array.isArray(item.hoverDetails) ? [...item.hoverDetails] : [];
  if (item.market) {
    hoverDetails.push(`Market ${item.market}`);
  }
  if (item.explanation) {
    hoverDetails.push(item.explanation);
  }
  return {
    symbol: item.symbol || '',
    label: item.label || item.name || item.symbol || '',
    value: item.price ?? item.value,
    unit: item.unit,
    changePct: item.changePercent ?? item.change,
    changeText: item.changeText,
    riskDirection: item.riskDirection,
    trend: Array.isArray(item.trend) ? item.trend : Array.isArray(item.sparkline) ? item.sparkline : [],
    source: item.source || undefined,
    sourceLabel: item.sourceLabel || undefined,
    sourceType: item.sourceType || undefined,
    providerHealth: item.providerHealth,
    updatedAt: item.updatedAt,
    asOf: item.asOf,
    freshness: item.freshness,
    isFallback: item.isFallback,
    isStale: item.isStale,
    isPartial: item.isPartial,
    isUnavailable: item.isUnavailable,
    isRefreshing: item.isRefreshing,
    isFromSnapshot: item.isFromSnapshot,
    lastSuccessfulAt: item.lastSuccessfulAt,
    refreshError: item.refreshError,
    lastError: item.lastError,
    delayMinutes: item.delayMinutes,
    sourceTier: item.sourceTier || undefined,
    trustLevel: item.trustLevel || undefined,
    observationOnly: item.observationOnly,
    sourceAuthorityAllowed: item.sourceAuthorityAllowed,
    scoreContributionAllowed: item.scoreContributionAllowed,
    sourceAuthorityReason: item.sourceAuthorityReason,
    sourceAuthorityRouteRejected: item.sourceAuthorityRouteRejected,
    routeRejectedReasonCodes: item.routeRejectedReasonCodes,
    reasonCodes: item.reasonCodes,
    breadthClaimType: item.breadthClaimType,
    officialExchangePublishedBreadth: item.officialExchangePublishedBreadth,
    fulfilledMetrics: item.fulfilledMetrics,
    missingMetrics: item.missingMetrics,
    metricCoverageRatio: item.metricCoverageRatio,
    broadMarketClaimAllowed: item.broadMarketClaimAllowed,
    degradationReason: item.degradationReason,
    degradationReasons: item.degradationReasons,
    warning: item.warning,
    hoverDetails,
  };
}

function normalizeMarketSnapshotPayload(rawPayload: Record<string, unknown>, panelName: string): MarketOverviewPanel {
  const payload = toCamelCase<MarketSnapshotPayload>(rawPayload);
  return {
    panelName,
    lastRefreshAt: payload.lastUpdate || payload.updatedAt || new Date().toISOString(),
    status: payload.fallbackUsed ? 'failure' : 'success',
    errorMessage: payload.fallbackUsed ? payload.error : null,
    logSessionId: payload.logSessionId,
    source: payload.source || undefined,
    sourceLabel: payload.sourceLabel || undefined,
    sourceType: payload.sourceType || undefined,
    providerHealth: payload.providerHealth,
    updatedAt: payload.updatedAt || payload.lastUpdate || new Date().toISOString(),
    asOf: payload.asOf,
    freshness: payload.freshness,
    isFallback: payload.isFallback ?? payload.fallbackUsed,
    isStale: payload.isStale,
    isPartial: payload.isPartial,
    isUnavailable: payload.isUnavailable,
    isRefreshing: payload.isRefreshing,
    isFromSnapshot: payload.isFromSnapshot,
    lastSuccessfulAt: payload.lastSuccessfulAt,
    refreshError: payload.refreshError,
    lastError: payload.lastError,
    delayMinutes: payload.delayMinutes,
    sourceTier: payload.sourceTier || undefined,
    trustLevel: payload.trustLevel || undefined,
    observationOnly: payload.observationOnly,
    sourceAuthorityAllowed: payload.sourceAuthorityAllowed,
    scoreContributionAllowed: payload.scoreContributionAllowed,
    sourceAuthorityReason: payload.sourceAuthorityReason,
    sourceAuthorityRouteRejected: payload.sourceAuthorityRouteRejected,
    routeRejectedReasonCodes: payload.routeRejectedReasonCodes,
    reasonCodes: payload.reasonCodes,
    breadthClaimType: payload.breadthClaimType,
    officialExchangePublishedBreadth: payload.officialExchangePublishedBreadth,
    fulfilledMetrics: payload.fulfilledMetrics,
    missingMetrics: payload.missingMetrics,
    metricCoverageRatio: payload.metricCoverageRatio,
    broadMarketClaimAllowed: payload.broadMarketClaimAllowed,
    degradationReason: payload.degradationReason,
    degradationReasons: payload.degradationReasons,
    warning: payload.warning,
    items: Array.isArray(payload.items) ? payload.items.map(normalizeItem) : [],
  };
}

async function getPanel(path: string, panelName: string): Promise<MarketOverviewPanel> {
  const response = await apiClient.get<Record<string, unknown>>(path);
  return normalizeMarketSnapshotPayload(response.data, panelName);
}

const MARKET_API_BASE_PATH = '/api/v1/market';

export type MarketDataReadinessStatus = 'ready' | 'partial' | 'missing' | 'misconfigured' | string;
export type MarketDataReadinessSeverity = 'error' | 'warning' | 'info' | string;

export type MarketDataReadinessCheck = {
  id: string;
  status: MarketDataReadinessStatus;
  severity: MarketDataReadinessSeverity;
  userFacingMessage: string;
  remediationHint?: string | null;
  affectsSurfaces: string[];
  productAffectedSurfaces?: string[];
  secretConfigured?: boolean;
  details?: Record<string, unknown>;
};

export type ConsumerEvidenceReadinessState =
  | 'score_grade'
  | 'observation_only'
  | 'blocked'
  | 'missing'
  | 'unavailable'
  | string;

export type ConsumerEvidenceReadinessItem = {
  surface: string;
  evidenceFamily: string;
  requiredInputs: string[];
  fulfilledInputs: string[];
  missingInputs: string[];
  staleInputs: string[];
  blockedInputs: string[];
  observationOnlyInputs: string[];
  scoreGradeInputs: string[];
  readinessState: ConsumerEvidenceReadinessState;
  confidenceCapReason: string;
  sourceAuthorityReason: string;
  freshnessReason: string;
  nextDiagnostic: string;
  consumerSafeSummary: string;
};

export type ConsumerEvidenceReadinessMatrix = {
  contractVersion: string;
  diagnosticOnly: boolean;
  networkCallsEnabled: boolean;
  mutationEnabled: boolean;
  items: ConsumerEvidenceReadinessItem[];
};

export type OfficialRiskSourceReadinessState = 'ready' | 'partial' | 'blocked' | 'unknown' | string;

export type OfficialRiskSourceReadinessPillarState = 'ready' | 'partial' | 'blocked' | 'unknown' | 'stale' | 'missing' | string;

export type OfficialRiskSourceReadinessPillar = {
  state?: OfficialRiskSourceReadinessPillarState;
  freshness?: MarketDataMeta['freshness'];
  latestDate?: string | null;
  asOf?: string | null;
  coveredSeriesCount?: number | null;
  blocker?: string | null;
};

export type OfficialRiskSourceReadiness = {
  bundleState?: OfficialRiskSourceReadinessState;
  vix?: OfficialRiskSourceReadinessPillar | null;
  rates?: OfficialRiskSourceReadinessPillar | null;
  fedLiquidity?: OfficialRiskSourceReadinessPillar | null;
  consumerSummary?: string | null;
  nextDataAction?: string | null;
};

export type OfficialRiskSourceReadinessChip = {
  key: string;
  label: string;
  variant: 'success' | 'info' | 'caution' | 'neutral';
};

export type OfficialRiskSourceReadinessView = {
  bundleLabel: string;
  bundleVariant: 'success' | 'info' | 'caution' | 'neutral';
  chips: OfficialRiskSourceReadinessChip[];
  note?: string;
};

export type ConsumerEvidenceBoundaryChip = {
  key: string;
  label: string;
  variant: 'success' | 'info' | 'caution' | 'neutral';
};

export type ConsumerEvidenceBoundaryView = {
  label: string;
  variant: 'success' | 'info' | 'caution' | 'neutral';
  chips: ConsumerEvidenceBoundaryChip[];
  nextEvidence: string;
  note?: string;
};

export type MarketDataReadinessResponse = {
  readinessStatus: MarketDataReadinessStatus;
  diagnosticOnly: boolean;
  providerRuntimeCalled: boolean;
  networkCallsEnabled: boolean;
  representativeSymbols: string[];
  checks: MarketDataReadinessCheck[];
  consumerEvidenceReadinessMatrix?: ConsumerEvidenceReadinessMatrix;
  officialRiskSourceReadiness?: OfficialRiskSourceReadiness;
};

export type DataSourceGapRegistryStatus =
  | 'ready'
  | 'partial'
  | 'missing'
  | 'blocked'
  | 'unauthorized'
  | 'stale'
  | 'observation-only'
  | 'planned'
  | string;

export type DataSourceGapRegistryAuthorityState =
  | 'allowed'
  | 'blocked'
  | 'unauthorized'
  | 'observation-only'
  | 'planned'
  | string;

export type DataSourceGapRegistryFreshnessState =
  | 'fresh'
  | 'live'
  | 'delayed'
  | 'cached'
  | 'stale'
  | 'partial'
  | 'fallback'
  | 'synthetic'
  | 'unavailable'
  | 'unknown'
  | string;

export type DataSourceSurfaceImpactState =
  | 'unlocked'
  | 'degraded'
  | 'observation-only'
  | 'blocked'
  | 'planned'
  | 'unknown'
  | string;

export type DataSourceSurfaceImpact = {
  surfaceKey: string;
  consumerLabel: string;
  impactState: DataSourceSurfaceImpactState;
  impactReason: string;
  affectedCapability: string;
  nextEvidenceStep: string;
};

export type DataSourceGapRegistryFamily = {
  familyKey: string;
  consumerLabel: string;
  status: DataSourceGapRegistryStatus;
  authorityState: DataSourceGapRegistryAuthorityState;
  freshnessState: DataSourceGapRegistryFreshnessState;
  entitlementOrLicensingBlocker?: string | null;
  integrationBlocker?: string | null;
  sourceEvidenceState: string;
  nextIntegrationStep: string;
  providerHydrationAllowed?: boolean;
  scoreTradingAuthorityAllowed?: boolean;
  consumerSafeDescription: string;
  surfaceImpactMatrix?: DataSourceSurfaceImpact[];
};

export type DataSourceGapRegistrySummary = {
  totalFamilies: number;
  readyCount: number;
  partialCount: number;
  missingCount: number;
  blockedCount: number;
  unauthorizedCount: number;
  staleCount: number;
  observationOnlyCount: number;
  plannedCount: number;
  providerHydrationAllowedCount: number;
  scoreTradingAuthorityAllowedCount: number;
};

export type DataSourceGapRegistryResponse = {
  contractVersion: string;
  diagnosticOnly: boolean;
  providerRuntimeCalled: boolean;
  networkCallsEnabled: boolean;
  scoreAuthorityAllowed: boolean;
  summary: DataSourceGapRegistrySummary;
  families: DataSourceGapRegistryFamily[];
  metadata?: Record<string, unknown>;
};

export type DataSourceGapRegistryStatusView = {
  label: string;
  variant: 'neutral' | 'success' | 'caution' | 'danger' | 'info';
};

export type DataSourceGapRegistryFamilyView = {
  familyKey: string;
  familyLabel: string;
  groupId: DataSourceGapRegistryGroupId;
  groupLabel: string;
  status: DataSourceGapRegistryStatusView;
  authorityState: DataSourceGapRegistryStatusView;
  freshnessState: DataSourceGapRegistryStatusView;
  entitlementOrLicensingBlocker: string;
  integrationBlocker: string;
  sourceEvidenceState: string;
  nextIntegrationStep: string;
  dataHydrationAllowed: string;
  dataHydrationVariant: DataSourceGapRegistryStatusView['variant'];
  scoreTradingAuthorityAllowed: string;
  scoreTradingAuthorityVariant: DataSourceGapRegistryStatusView['variant'];
  consumerSafeDescription: string;
  surfaceImpactMatrix: DataSourceSurfaceImpactView[];
};

export type DataSourceSurfaceImpactView = {
  surfaceKey: string;
  surfaceLabel: string;
  impactState: DataSourceGapRegistryStatusView;
  impactReason: string;
  affectedCapability: string;
  nextEvidenceStep: string;
};

export type DataSourceGapRegistryGroupId =
  | 'quote_market'
  | 'options'
  | 'macro_liquidity_credit'
  | 'backtest_research'
  | 'scenario'
  | 'portfolio'
  | 'positioning_flows'
  | 'other';

export type DataSourceGapRegistryGroupView = {
  groupId: DataSourceGapRegistryGroupId;
  groupLabel: string;
  groupDescription: string;
  families: DataSourceGapRegistryFamilyView[];
};

export type DataSourceGapRegistryView = {
  diagnosticOnly: boolean;
  runtimeCalled: boolean;
  networkCallsEnabled: boolean;
  scoreAuthorityAllowed: boolean;
  summary: DataSourceGapRegistrySummary;
  families: DataSourceGapRegistryFamilyView[];
  groups: DataSourceGapRegistryGroupView[];
};

function normalizeReadinessSymbols(symbols?: string[] | string | null): string | undefined {
  if (Array.isArray(symbols)) {
    const sanitized = symbols.flatMap((symbol) => {
      const trimmed = String(symbol || '').trim();
      return trimmed ? [trimmed] : [];
    });
    return sanitized.length ? sanitized.join(',') : undefined;
  }
  if (typeof symbols !== 'string') {
    return undefined;
  }
  const sanitized = symbols
    .split(',')
    .flatMap((symbol) => {
      const trimmed = symbol.trim();
      return trimmed ? [trimmed] : [];
    })
    .join(',');
  return sanitized || undefined;
}

function normalizeMarketDataReadinessPayload(rawPayload: Record<string, unknown>): MarketDataReadinessResponse {
  const payload = toCamelCase<MarketDataReadinessResponse>(rawPayload);
  const matrix = payload.consumerEvidenceReadinessMatrix;
  return {
    readinessStatus: payload.readinessStatus || 'missing',
    diagnosticOnly: payload.diagnosticOnly !== false,
    providerRuntimeCalled: payload.providerRuntimeCalled === true,
    networkCallsEnabled: payload.networkCallsEnabled === true,
    representativeSymbols: Array.isArray(payload.representativeSymbols) ? payload.representativeSymbols : [],
    checks: Array.isArray(payload.checks) ? payload.checks.map((check) => ({
      id: check.id,
      status: check.status || 'missing',
      severity: check.severity || 'warning',
      userFacingMessage: check.userFacingMessage || '',
      remediationHint: check.remediationHint || null,
      affectsSurfaces: Array.isArray(check.affectsSurfaces) ? check.affectsSurfaces : [],
      ...(Array.isArray(check.productAffectedSurfaces) ? { productAffectedSurfaces: check.productAffectedSurfaces } : {}),
      ...(typeof check.secretConfigured === 'boolean' ? { secretConfigured: check.secretConfigured } : {}),
      ...(check.details && typeof check.details === 'object' ? { details: check.details } : {}),
    })) : [],
    ...(matrix && Array.isArray(matrix.items) ? {
      consumerEvidenceReadinessMatrix: {
        contractVersion: matrix.contractVersion || 'consumer_evidence_readiness_matrix_v1',
        diagnosticOnly: matrix.diagnosticOnly !== false,
        networkCallsEnabled: matrix.networkCallsEnabled === true,
        mutationEnabled: matrix.mutationEnabled === true,
        items: matrix.items.map((item) => ({
          surface: item.surface || 'unknown',
          evidenceFamily: item.evidenceFamily || 'unknown',
          requiredInputs: Array.isArray(item.requiredInputs) ? item.requiredInputs : [],
          fulfilledInputs: Array.isArray(item.fulfilledInputs) ? item.fulfilledInputs : [],
          missingInputs: Array.isArray(item.missingInputs) ? item.missingInputs : [],
          staleInputs: Array.isArray(item.staleInputs) ? item.staleInputs : [],
          blockedInputs: Array.isArray(item.blockedInputs) ? item.blockedInputs : [],
          observationOnlyInputs: Array.isArray(item.observationOnlyInputs) ? item.observationOnlyInputs : [],
          scoreGradeInputs: Array.isArray(item.scoreGradeInputs) ? item.scoreGradeInputs : [],
          readinessState: item.readinessState || 'unavailable',
          confidenceCapReason: item.confidenceCapReason || '',
          sourceAuthorityReason: item.sourceAuthorityReason || '',
          freshnessReason: item.freshnessReason || '',
          nextDiagnostic: item.nextDiagnostic || '',
          consumerSafeSummary: item.consumerSafeSummary || '',
        })),
      },
    } : {}),
    ...(payload.officialRiskSourceReadiness ? {
      officialRiskSourceReadiness: {
        bundleState: payload.officialRiskSourceReadiness.bundleState || 'unknown',
        vix: payload.officialRiskSourceReadiness.vix ? { ...payload.officialRiskSourceReadiness.vix } : undefined,
        rates: payload.officialRiskSourceReadiness.rates ? { ...payload.officialRiskSourceReadiness.rates } : undefined,
        fedLiquidity: payload.officialRiskSourceReadiness.fedLiquidity
          ? { ...payload.officialRiskSourceReadiness.fedLiquidity }
          : undefined,
        consumerSummary: payload.officialRiskSourceReadiness.consumerSummary || null,
        nextDataAction: payload.officialRiskSourceReadiness.nextDataAction || null,
      },
    } : {}),
  };
}

const DEFAULT_DATA_SOURCE_GAP_REGISTRY_SUMMARY: DataSourceGapRegistrySummary = {
  totalFamilies: 0,
  readyCount: 0,
  partialCount: 0,
  missingCount: 0,
  blockedCount: 0,
  unauthorizedCount: 0,
  staleCount: 0,
  observationOnlyCount: 0,
  plannedCount: 0,
  providerHydrationAllowedCount: 0,
  scoreTradingAuthorityAllowedCount: 0,
};

const DATA_SOURCE_GAP_FAMILY_LABELS: Record<string, string> = {
  stock_quote_spine: '股票报价骨架',
  fundamentals: '基本面与财报',
  etf_index_coverage: 'ETF / 指数覆盖',
  macro_rates: '宏观与利率',
  fed_liquidity: 'Fed 流动性',
  credit_stress: '信用压力',
  vix_volatility: 'VIX / 波动率',
  breadth_flows_positioning: '广度 / 资金流 / 持仓',
  options_chains: '期权链',
  options_strategy_analytics: '期权策略分析',
  gamma_dealer_positioning: 'Gamma / Dealer Positioning',
  backtest_dataset_lineage: '回测数据集血缘',
  scenario_baselines: '情景基线',
  portfolio_valuation_lineage: '组合估值血缘',
};

const DATA_SOURCE_GAP_DESCRIPTIONS: Record<string, string> = {
  stock_quote_spine: '报价与日线链路已有基础，但尚未形成统一、可追溯的专业数据骨架。',
  fundamentals: '基本面数据已分散接入，期间、重述与来源血缘仍需补证。',
  etf_index_coverage: 'ETF 和指数报价部分可用，成分、权重与展示权仍未完整证明。',
  macro_rates: '宏观与利率目前仅作为诊断契约展示，尚未形成完整产品数据包。',
  fed_liquidity: 'Fed 流动性证据已有契约形态，但还不是稳定产品数据骨架。',
  credit_stress: '信用压力仍是受限上下文，不作为可计分证据。',
  vix_volatility: '波动率证据已有部分路径，但专业来源权限仍需补证。',
  breadth_flows_positioning: '广度已有部分证据，资金流与持仓仍处于评审边界内。',
  options_chains: '期权链在授权、展示、存储和使用权证明前保持不可用。',
  options_strategy_analytics: '期权策略分析在授权输入和历史链路证明前保持阻断。',
  gamma_dealer_positioning: 'Gamma、GEX、vanna、charm 与 dealer positioning 在权利、输入和方法批准前保持阻断。',
  backtest_dataset_lineage: '回测读回已有研究价值，但专业数据集血缘仍不完整。',
  scenario_baselines: '情景基线处于计划状态，存储化基线输入尚未接入。',
  portfolio_valuation_lineage: '组合估值已有部分追踪，价格、FX、基准与因子血缘仍需硬化。',
};

const DATA_SOURCE_GAP_NEXT_STEPS: Record<string, string> = {
  stock_quote_spine: '落地报价与日线快照，并附带来源权限与 as-of 血缘。',
  fundamentals: '按期间和来源归一化基本面、报表与公告血缘。',
  etf_index_coverage: '接入官方成分、权重快照与基准映射证据。',
  macro_rates: '持久化官方宏观行，并补齐时效与覆盖元数据。',
  fed_liquidity: '持久化所需流动性序列，并记录覆盖与滞后状态。',
  credit_stress: '用存储化信用压力序列替换仅代理上下文。',
  vix_volatility: '接入官方波动率行，并保持时效门槛 fail-closed。',
  breadth_flows_positioning: '拆分广度证明、资金流证明和持仓来源评审。',
  options_chains: '先补齐期权链权益证明包，再考虑提升链路状态。',
  options_strategy_analytics: '先证明授权期权链、历史数据和方法输入。',
  gamma_dealer_positioning: '先完成权利、输入和方法评审，再暴露 gamma 家族输出。',
  backtest_dataset_lineage: '持久化数据集 ID、调整基准证据与复现实验清单。',
  scenario_baselines: '存储市场与组合情景输入的基线快照 ID。',
  portfolio_valuation_lineage: '把价格、FX、估值、基准和因子血缘一起持久化。',
};

const DATA_SOURCE_GAP_BLOCKERS: Record<string, { entitlement?: string; integration?: string; sourceEvidence?: string }> = {
  stock_quote_spine: {
    integration: '缺少持久化报价 / 日线快照和统一 as-of 血缘。',
    sourceEvidence: '证据分散',
  },
  fundamentals: {
    integration: '点时覆盖和重述安全归一化尚未完成。',
    sourceEvidence: '证据分散',
  },
  etf_index_coverage: {
    entitlement: '官方成分与权重展示权尚未证明。',
    integration: '成分、权重、基准和广度链接尚未统一。',
    sourceEvidence: '证据分散',
  },
  macro_rates: {
    integration: '官方宏观行尚未作为完整产品数据包展示。',
    sourceEvidence: '诊断契约',
  },
  fed_liquidity: {
    integration: '周频流动性行尚未形成完整产品数据包。',
    sourceEvidence: '诊断契约',
  },
  credit_stress: {
    integration: '持久化信用压力序列尚未接入。',
    sourceEvidence: '诊断契约',
  },
  vix_volatility: {
    integration: '官方波动率行和权限元数据尚未统一。',
    sourceEvidence: '证据分散',
  },
  breadth_flows_positioning: {
    entitlement: '资金流与持仓授权尚未证明。',
    integration: '广度部分可用；资金流与持仓家族仍不完整。',
    sourceEvidence: '证据分散',
  },
  options_chains: {
    entitlement: '期权链访问、展示、存储和使用权尚未证明。',
    integration: '未接入授权的实时或延迟期权链存储。',
    sourceEvidence: '权益待证',
  },
  options_strategy_analytics: {
    entitlement: '授权期权链输入和历史回放权尚未证明。',
    integration: '策略分析不能先于期权链权限和历史数据毕业。',
    sourceEvidence: '权益待证',
  },
  gamma_dealer_positioning: {
    entitlement: '期权权利、方法批准和持仓证据尚未证明。',
    integration: '未接入批准的方法或有权利支撑的输入集。',
    sourceEvidence: '权益待证',
  },
  backtest_dataset_lineage: {
    integration: '数据集身份、调整基准、交易日历和 PIT 成分仍不完整。',
    sourceEvidence: '诊断契约',
  },
  scenario_baselines: {
    integration: '持久化基线快照存储尚未接入。',
    sourceEvidence: '尚未接入',
  },
  portfolio_valuation_lineage: {
    integration: '价格来源、FX 时效、基准和因子血缘仍不完整。',
    sourceEvidence: '证据分散',
  },
};

const DATA_SOURCE_GAP_GROUPS: Array<{
  id: DataSourceGapRegistryGroupId;
  label: string;
  description: string;
}> = [
  {
    id: 'quote_market',
    label: '报价 / 市场骨架',
    description: '报价、指数、ETF 和波动率输入的专业数据骨架。',
  },
  {
    id: 'options',
    label: '期权与衍生结构',
    description: '期权链、策略分析、Gamma 与 dealer positioning 权益边界。',
  },
  {
    id: 'macro_liquidity_credit',
    label: '宏观 / 流动性 / 信用',
    description: '利率、Fed 流动性、信用压力等官方风险输入。',
  },
  {
    id: 'backtest_research',
    label: '回测 / 研究血缘',
    description: '回测数据集、研究输入和复现实验血缘。',
  },
  {
    id: 'scenario',
    label: '情景基线',
    description: '情景实验所需的可复现基线输入。',
  },
  {
    id: 'portfolio',
    label: '组合估值',
    description: '组合价格、FX、估值、基准与因子血缘。',
  },
  {
    id: 'positioning_flows',
    label: '持仓 / 资金流',
    description: '广度、资金流和持仓来源评审边界。',
  },
];

const DATA_SOURCE_GAP_FAMILY_GROUP: Record<string, DataSourceGapRegistryGroupId> = {
  stock_quote_spine: 'quote_market',
  etf_index_coverage: 'quote_market',
  vix_volatility: 'quote_market',
  fundamentals: 'quote_market',
  options_chains: 'options',
  options_strategy_analytics: 'options',
  gamma_dealer_positioning: 'options',
  macro_rates: 'macro_liquidity_credit',
  fed_liquidity: 'macro_liquidity_credit',
  credit_stress: 'macro_liquidity_credit',
  backtest_dataset_lineage: 'backtest_research',
  scenario_baselines: 'scenario',
  portfolio_valuation_lineage: 'portfolio',
  breadth_flows_positioning: 'positioning_flows',
};

const DATA_SOURCE_IMPACT_SURFACE_LABELS: Record<string, string> = {
  market_overview: 'Market Overview',
  scanner: 'Scanner',
  watchlist: 'Watchlist',
  stock_detail: 'Stock Detail',
  options_lab: 'Options Lab',
  liquidity_monitor: 'Liquidity Monitor',
  backtest_parameter_sweep: '回测 / 参数扫描',
  factor_research: 'Factor Research',
  scenario_lab: 'Scenario Lab',
  portfolio: 'Portfolio',
  admin_diagnostics: 'Admin / Diagnostics',
  evidence_harness: 'Evidence Harness',
};

const DATA_SOURCE_GAP_UNSAFE_TEXT_PATTERN =
  /request[_ -]?id|trace[_ -]?id|raw[_ -]?(payload|diagnostic|dump)|cache[_ -]?key|credential|env\b|debug|token|secret|cookie|api[_-]?key/i;

function normalizeGapToken(value?: string | null): string {
  return String(value || '').trim().toLowerCase();
}

function dataSourceGapStatusView(status?: string | null): DataSourceGapRegistryStatusView {
  const normalized = normalizeGapToken(status);
  if (normalized === 'ready') return { label: '已就绪', variant: 'success' };
  if (normalized === 'partial') return { label: '部分可用', variant: 'info' };
  if (normalized === 'blocked') return { label: '阻断', variant: 'danger' };
  if (normalized === 'unauthorized') return { label: '未授权', variant: 'danger' };
  if (normalized === 'observation-only') return { label: '仅观察', variant: 'neutral' };
  if (normalized === 'planned') return { label: '计划中', variant: 'neutral' };
  if (normalized === 'stale') return { label: '待更新', variant: 'caution' };
  if (normalized === 'missing') return { label: '待补证', variant: 'caution' };
  return { label: '待补证', variant: 'caution' };
}

function dataSourceGapAuthorityView(state?: string | null): DataSourceGapRegistryStatusView {
  const normalized = normalizeGapToken(state);
  if (normalized === 'allowed') return { label: '可用', variant: 'success' };
  if (normalized === 'blocked') return { label: '阻断', variant: 'danger' };
  if (normalized === 'unauthorized') return { label: '未授权', variant: 'danger' };
  if (normalized === 'observation-only') return { label: '仅观察', variant: 'neutral' };
  if (normalized === 'planned') return { label: '计划中', variant: 'neutral' };
  return { label: '待补证', variant: 'caution' };
}

function dataSourceGapFreshnessView(state?: string | null): DataSourceGapRegistryStatusView {
  const normalized = normalizeGapToken(state);
  if (normalized === 'fresh' || normalized === 'live') return { label: '新鲜', variant: 'success' };
  if (normalized === 'delayed') return { label: '延迟', variant: 'info' };
  if (normalized === 'cached') return { label: '缓存', variant: 'info' };
  if (normalized === 'partial') return { label: '部分', variant: 'info' };
  if (normalized === 'stale') return { label: '待更新', variant: 'caution' };
  if (normalized === 'fallback' || normalized === 'synthetic') return { label: '待补证', variant: 'caution' };
  if (normalized === 'unavailable') return { label: '不可用', variant: 'danger' };
  return { label: '待补证', variant: 'caution' };
}

function dataSourceGapImpactStateView(state?: string | null): DataSourceGapRegistryStatusView {
  const normalized = normalizeGapToken(state);
  if (normalized === 'unlocked') return { label: '已解锁', variant: 'success' };
  if (normalized === 'degraded') return { label: '降级', variant: 'caution' };
  if (normalized === 'observation-only') return { label: '仅观察', variant: 'neutral' };
  if (normalized === 'blocked') return { label: '阻断', variant: 'danger' };
  if (normalized === 'planned') return { label: '计划中', variant: 'neutral' };
  return { label: '待补证', variant: 'caution' };
}

function dataSourceGapSafeText(value?: string | null, fallback = '待补证'): string {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text || DATA_SOURCE_GAP_UNSAFE_TEXT_PATTERN.test(text)) return fallback;
  return text.slice(0, 140);
}

function dataSourceGapBooleanView(value: boolean | undefined): Pick<DataSourceGapRegistryFamilyView, 'dataHydrationAllowed' | 'dataHydrationVariant'> {
  if (value === true) return { dataHydrationAllowed: '允许', dataHydrationVariant: 'success' };
  if (value === false) return { dataHydrationAllowed: '不允许', dataHydrationVariant: 'caution' };
  return { dataHydrationAllowed: '待补证', dataHydrationVariant: 'neutral' };
}

function dataSourceGapScoreAuthorityView(value: boolean | undefined): Pick<DataSourceGapRegistryFamilyView, 'scoreTradingAuthorityAllowed' | 'scoreTradingAuthorityVariant'> {
  if (value === true) return { scoreTradingAuthorityAllowed: '允许', scoreTradingAuthorityVariant: 'success' };
  if (value === false) return { scoreTradingAuthorityAllowed: '不允许', scoreTradingAuthorityVariant: 'caution' };
  return { scoreTradingAuthorityAllowed: '待补证', scoreTradingAuthorityVariant: 'neutral' };
}

function normalizeDataSourceGapRegistryPayload(rawPayload: Record<string, unknown>): DataSourceGapRegistryResponse {
  const payload = toCamelCase<DataSourceGapRegistryResponse>(rawPayload);
  const rawSummary = payload.summary || DEFAULT_DATA_SOURCE_GAP_REGISTRY_SUMMARY;
  return {
    contractVersion: payload.contractVersion || 'data_source_gap_registry_unknown',
    diagnosticOnly: payload.diagnosticOnly !== false,
    providerRuntimeCalled: payload.providerRuntimeCalled === true,
    networkCallsEnabled: payload.networkCallsEnabled === true,
    scoreAuthorityAllowed: payload.scoreAuthorityAllowed === true,
    summary: { ...DEFAULT_DATA_SOURCE_GAP_REGISTRY_SUMMARY, ...rawSummary },
    families: Array.isArray(payload.families) ? payload.families.map((family) => ({
      familyKey: family.familyKey || 'unknown_family',
      consumerLabel: family.consumerLabel || '数据家族',
      status: family.status || 'missing',
      authorityState: family.authorityState || 'blocked',
      freshnessState: family.freshnessState || 'unknown',
      entitlementOrLicensingBlocker: family.entitlementOrLicensingBlocker || null,
      integrationBlocker: family.integrationBlocker || null,
      sourceEvidenceState: family.sourceEvidenceState || 'unknown',
      nextIntegrationStep: family.nextIntegrationStep || '',
      providerHydrationAllowed: typeof family.providerHydrationAllowed === 'boolean' ? family.providerHydrationAllowed : undefined,
      scoreTradingAuthorityAllowed: typeof family.scoreTradingAuthorityAllowed === 'boolean' ? family.scoreTradingAuthorityAllowed : undefined,
      consumerSafeDescription: family.consumerSafeDescription || '',
      surfaceImpactMatrix: Array.isArray(family.surfaceImpactMatrix)
        ? family.surfaceImpactMatrix.map((impact) => ({
          surfaceKey: impact.surfaceKey || 'unknown_surface',
          consumerLabel: impact.consumerLabel || '影响面待补证',
          impactState: impact.impactState || 'unknown',
          impactReason: impact.impactReason || '',
          affectedCapability: impact.affectedCapability || '',
          nextEvidenceStep: impact.nextEvidenceStep || '',
        }))
        : [],
    })) : [],
    metadata: payload.metadata || {},
  };
}

export function buildDataSourceGapRegistryView(
  registry?: DataSourceGapRegistryResponse | null,
): DataSourceGapRegistryView {
  const summary = registry?.summary || DEFAULT_DATA_SOURCE_GAP_REGISTRY_SUMMARY;
  const families = Array.isArray(registry?.families) ? registry.families : [];
  const familyViews = families.map((family) => {
    const familyKey = family.familyKey || 'unknown_family';
    const blockerCopy = DATA_SOURCE_GAP_BLOCKERS[familyKey] || {};
    const hydration = dataSourceGapBooleanView(family.providerHydrationAllowed);
    const scoreAuthority = dataSourceGapScoreAuthorityView(family.scoreTradingAuthorityAllowed);
    const groupId = DATA_SOURCE_GAP_FAMILY_GROUP[familyKey] || 'other';
    const groupLabel = DATA_SOURCE_GAP_GROUPS.find((group) => group.id === groupId)?.label || '其他待补证';
    const surfaceImpactMatrix = (family.surfaceImpactMatrix || []).map((impact) => {
      const surfaceKey = impact.surfaceKey || 'unknown_surface';
      const impactState = normalizeGapToken(impact.impactState) === 'unlocked'
        && (normalizeGapToken(family.status) !== 'ready' || normalizeGapToken(family.authorityState) !== 'allowed')
        ? 'unknown'
        : impact.impactState;
      return {
        surfaceKey,
        surfaceLabel: DATA_SOURCE_IMPACT_SURFACE_LABELS[surfaceKey] || dataSourceGapSafeText(impact.consumerLabel, '影响面待补证'),
        impactState: dataSourceGapImpactStateView(impactState),
        impactReason: dataSourceGapSafeText(impact.impactReason, '影响原因待补证。'),
        affectedCapability: dataSourceGapSafeText(impact.affectedCapability, '影响能力待补证。'),
        nextEvidenceStep: dataSourceGapSafeText(impact.nextEvidenceStep, '下一证据步骤待补证。'),
      };
    });
    return {
      familyKey,
      familyLabel: DATA_SOURCE_GAP_FAMILY_LABELS[familyKey] || family.consumerLabel || '数据家族',
      groupId,
      groupLabel,
      status: dataSourceGapStatusView(family.status),
      authorityState: dataSourceGapAuthorityView(family.authorityState),
      freshnessState: dataSourceGapFreshnessView(family.freshnessState),
      entitlementOrLicensingBlocker: blockerCopy.entitlement || (family.entitlementOrLicensingBlocker ? '权益或授权阻断待复核。' : '暂无'),
      integrationBlocker: blockerCopy.integration || (family.integrationBlocker ? '集成阻断待复核。' : '暂无'),
      sourceEvidenceState: blockerCopy.sourceEvidence || '待补证',
      nextIntegrationStep: DATA_SOURCE_GAP_NEXT_STEPS[familyKey] || (family.nextIntegrationStep ? '按既有集成路径补证后再展示。' : '待补证'),
      dataHydrationAllowed: hydration.dataHydrationAllowed,
      dataHydrationVariant: hydration.dataHydrationVariant,
      scoreTradingAuthorityAllowed: scoreAuthority.scoreTradingAuthorityAllowed,
      scoreTradingAuthorityVariant: scoreAuthority.scoreTradingAuthorityVariant,
      consumerSafeDescription: DATA_SOURCE_GAP_DESCRIPTIONS[familyKey] || (family.consumerSafeDescription ? '已返回说明，需人工复核后展示。' : '数据说明待补证。'),
      surfaceImpactMatrix,
    };
  });
  const groups = [
    ...DATA_SOURCE_GAP_GROUPS,
    {
      id: 'other' as DataSourceGapRegistryGroupId,
      label: '其他待补证',
      description: '后端新增但前端尚未归类的数据家族。',
    },
  ]
    .map((group) => ({
      groupId: group.id,
      groupLabel: group.label,
      groupDescription: group.description,
      families: familyViews.filter((family) => family.groupId === group.id),
    }))
    .filter((group) => group.families.length > 0 || group.groupId !== 'other');

  return {
    diagnosticOnly: registry?.diagnosticOnly !== false,
    runtimeCalled: registry?.providerRuntimeCalled === true,
    networkCallsEnabled: registry?.networkCallsEnabled === true,
    scoreAuthorityAllowed: registry?.scoreAuthorityAllowed === true,
    summary,
    families: familyViews,
    groups,
  };
}

function officialRiskSourceBundleLabel(state?: OfficialRiskSourceReadinessState): OfficialRiskSourceReadinessView['bundleLabel'] {
  if (state === 'ready') return '官方风险源可用';
  if (state === 'partial') return '官方风险源部分可用';
  if (state === 'blocked') return '官方风险源待补';
  return '来源待确认';
}

function officialRiskSourceBundleVariant(state?: OfficialRiskSourceReadinessState): OfficialRiskSourceReadinessView['bundleVariant'] {
  if (state === 'ready') return 'success';
  if (state === 'partial') return 'info';
  if (state === 'blocked') return 'caution';
  return 'neutral';
}

function officialRiskSourcePillarLabel(
  title: string,
  pillar?: OfficialRiskSourceReadinessPillar | null,
): OfficialRiskSourceReadinessChip {
  const state = pillar?.state;
  const freshness = pillar?.freshness;
  if (state === 'ready') {
    return { key: title, label: `${title}可用`, variant: 'success' };
  }
  if (state === 'partial') {
    return { key: title, label: `${title}部分可用`, variant: 'info' };
  }
  if (state === 'stale' || freshness === 'stale' || freshness === 'fallback') {
    return { key: title, label: `${title}待更新`, variant: 'caution' };
  }
  return { key: title, label: `${title}待补`, variant: 'neutral' };
}

export function buildOfficialRiskSourceReadinessView(
  readiness?: OfficialRiskSourceReadiness | null,
): OfficialRiskSourceReadinessView {
  if (!readiness) {
    return {
      bundleLabel: '来源待确认',
      bundleVariant: 'neutral',
      chips: [],
    };
  }

  const chips = [
    officialRiskSourcePillarLabel('VIX', readiness.vix),
    officialRiskSourcePillarLabel('利率', readiness.rates),
    officialRiskSourcePillarLabel('Fed流动性', readiness.fedLiquidity),
  ];
  const note = readiness.consumerSummary || readiness.nextDataAction || undefined;
  return {
    bundleLabel: officialRiskSourceBundleLabel(readiness.bundleState),
    bundleVariant: officialRiskSourceBundleVariant(readiness.bundleState),
    chips,
    ...(note ? { note } : {}),
  };
}

const CONSUMER_EVIDENCE_INPUT_LABELS: Record<string, string> = {
  'market overview': '市场总览',
  'market overview read model': '市场总览读数',
  'market breadth context': '市场广度',
  'rotation context': '板块轮动',
  'liquidity context': '流动性',
  'macro context': '宏观背景',
  'research radar': '研究雷达',
  'rotation radar': '轮动雷达',
  'liquidity monitor': '流动性看板',
  'options observation': '期权观察',
  'completed scanner evidence': '扫描器证据',
  'watchlist research context': '观察名单研究上下文',
  'candidate evidence quality': '候选证据质量',
};

function normalizeConsumerEvidenceToken(value?: string | null): string {
  return String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
}

function consumerEvidenceInputLabel(value?: string | null): string {
  const normalized = normalizeConsumerEvidenceToken(value);
  if (!normalized) {
    return '数据项';
  }
  return CONSUMER_EVIDENCE_INPUT_LABELS[normalized] || '数据项';
}

function consumerEvidenceStateLabel(state?: string | null): { label: string; variant: ConsumerEvidenceBoundaryView['variant'] } {
  const normalized = normalizeConsumerEvidenceToken(state);
  if (normalized === 'score_grade' || normalized === 'ready') {
    return { label: '证据可用', variant: 'success' };
  }
  if (normalized === 'partial') {
    return { label: '部分可用', variant: 'info' };
  }
  if (normalized === 'observation_only') {
    return { label: '仅观察', variant: 'neutral' };
  }
  if (normalized === 'stale') {
    return { label: '待更新', variant: 'caution' };
  }
  if (normalized === 'blocked' || normalized === 'missing' || normalized === 'unavailable') {
    return { label: '待补', variant: 'caution' };
  }
  return { label: '证据待确认', variant: 'neutral' };
}

function consumerEvidenceInputState(
  item: ConsumerEvidenceReadinessItem,
  inputName: string,
): { label: string; variant: ConsumerEvidenceBoundaryView['variant'] } {
  const normalizedInput = normalizeConsumerEvidenceToken(inputName);
  const categoryName = consumerEvidenceInputLabel(inputName);
  const isMissing = item.missingInputs.some((value) => normalizeConsumerEvidenceToken(value) === normalizedInput);
  const isBlocked = item.blockedInputs.some((value) => normalizeConsumerEvidenceToken(value) === normalizedInput);
  const isStale = item.staleInputs.some((value) => normalizeConsumerEvidenceToken(value) === normalizedInput);
  const isObservationOnly = item.observationOnlyInputs.some((value) => normalizeConsumerEvidenceToken(value) === normalizedInput);
  const isReady = item.fulfilledInputs.some((value) => normalizeConsumerEvidenceToken(value) === normalizedInput)
    || item.scoreGradeInputs.some((value) => normalizeConsumerEvidenceToken(value) === normalizedInput);

  if (isMissing || isBlocked) {
    return { label: `${categoryName}待补`, variant: 'caution' };
  }
  if (isStale) {
    return { label: `${categoryName}待更新`, variant: 'caution' };
  }
  if (isObservationOnly) {
    return { label: `${categoryName}仅观察`, variant: 'neutral' };
  }
  if (isReady) {
    return { label: `${categoryName}可用`, variant: 'success' };
  }
  return { label: `${categoryName}待确认`, variant: 'neutral' };
}

function consumerEvidenceNextLine(item?: ConsumerEvidenceReadinessItem): string {
  if (!item) {
    return '继续观察现有证据。';
  }
  const nextInputs = [
    ...item.missingInputs,
    ...item.blockedInputs,
    ...item.staleInputs,
    ...item.observationOnlyInputs,
  ];
  const unique = Array.from(new Set(nextInputs.map((value) => consumerEvidenceInputLabel(value)).filter((value) => value !== '数据项')));
  if (!unique.length) {
    return '继续观察现有证据。';
  }
  return `下一步：补齐${unique.slice(0, 2).join('、')}`;
}

function selectConsumerEvidenceBoundaryItem(
  matrix?: ConsumerEvidenceReadinessMatrix | null,
): ConsumerEvidenceReadinessItem | undefined {
  const items = Array.isArray(matrix?.items) ? matrix.items : [];
  return items.find((item) => normalizeConsumerEvidenceToken(item.surface) === 'market_overview') || items[0];
}

export function buildConsumerEvidenceBoundaryView(
  matrix?: ConsumerEvidenceReadinessMatrix | null,
): ConsumerEvidenceBoundaryView {
  const item = selectConsumerEvidenceBoundaryItem(matrix);
  if (!matrix || !item) {
    return {
      label: '证据边界待确认',
      variant: 'neutral',
      chips: [
        { key: 'boundary', label: '证据边界待确认', variant: 'neutral' },
        { key: 'overview', label: '市场总览待补', variant: 'neutral' },
        { key: 'breadth', label: '广度待补', variant: 'neutral' },
        { key: 'rotation', label: '板块轮动待补', variant: 'neutral' },
        { key: 'risk', label: '风险状态待补', variant: 'neutral' },
      ],
      nextEvidence: '继续观察现有证据。',
      note: '当前未返回市场总览证据矩阵，保持观察。',
    };
  }

  const overallState = consumerEvidenceStateLabel(item.readinessState);
  const breadthState = consumerEvidenceInputState(item, 'market breadth context');
  const rotationState = consumerEvidenceInputState(item, 'rotation context');
  const riskState = item.observationOnlyInputs.length > 0 || item.readinessState === 'observation_only'
    ? { label: '风险状态仅观察', variant: 'neutral' as const }
    : item.missingInputs.length > 0 || item.blockedInputs.length > 0
      ? { label: '风险状态待补', variant: 'caution' as const }
      : item.staleInputs.length > 0
        ? { label: '风险状态待更新', variant: 'caution' as const }
        : { label: '风险状态可用', variant: 'success' as const };

  const chips: ConsumerEvidenceBoundaryChip[] = [
    { key: 'boundary', label: overallState.label, variant: overallState.variant },
    { key: 'overview', label: consumerEvidenceInputState(item, 'market overview read model').label, variant: consumerEvidenceInputState(item, 'market overview read model').variant },
    { key: 'breadth', label: breadthState.label, variant: breadthState.variant },
    { key: 'rotation', label: rotationState.label, variant: rotationState.variant },
    { key: 'risk', label: riskState.label, variant: riskState.variant },
  ];

  return {
    label: overallState.label,
    variant: overallState.variant,
    chips,
    nextEvidence: consumerEvidenceNextLine(item),
    note: matrix.diagnosticOnly ? '当前仅用于观察，不代表可形成结论。' : undefined,
  };
}

export function buildMarketApiPath(path: string): string {
  return joinApiPath(MARKET_API_BASE_PATH, path);
}

export function buildMarketApiUrl(baseUrl: string, path: string): string {
  return buildAbsoluteApiUrl(baseUrl, path);
}

export const marketApi = {
  getCrypto: () => getPanel(buildMarketApiPath('crypto'), 'CryptoCard'),
  cryptoStreamUrl: () => buildMarketApiUrl(API_BASE_URL, buildMarketApiPath('crypto/stream')),
  normalizeCryptoStreamPayload: (payload: Record<string, unknown>) => normalizeMarketSnapshotPayload(payload, 'CryptoCard'),
  getSentiment: () => getPanel(buildMarketApiPath('sentiment'), 'MarketSentimentCard'),
  getCnIndices: () => getPanel(buildMarketApiPath('cn-indices'), 'ChinaIndicesCard'),
  getCnBreadth: () => getPanel(buildMarketApiPath('cn-breadth'), 'ChinaBreadthCard'),
  getCnFlows: () => getPanel(buildMarketApiPath('cn-flows'), 'ChinaFlowsCard'),
  getSectorRotation: () => getPanel(buildMarketApiPath('sector-rotation'), 'SectorRotationCard'),
  getUsBreadth: () => getPanel(buildMarketApiPath('us-breadth'), 'UsBreadthCard'),
  getRates: () => getPanel(buildMarketApiPath('rates'), 'RatesCard'),
  getFxCommodities: () => getPanel(buildMarketApiPath('fx-commodities'), 'FxCommoditiesCard'),
  getTemperature: async (): Promise<MarketTemperatureResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(buildMarketApiPath('temperature'));
    return normalizeMarketTemperatureResponse(toCamelCase<MarketTemperatureResponse>(response.data));
  },
  getMarketBriefing: async (): Promise<MarketBriefingResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(buildMarketApiPath('market-briefing'));
    return toCamelCase<MarketBriefingResponse>(response.data);
  },
  getFutures: async (): Promise<MarketFuturesResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(buildMarketApiPath('futures'));
    return toCamelCase<MarketFuturesResponse>(response.data);
  },
  getCnShortSentiment: async (): Promise<CnShortSentimentResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(buildMarketApiPath('cn-short-sentiment'));
    return toCamelCase<CnShortSentimentResponse>(response.data);
  },
  getDataReadiness: async (options?: { symbols?: string[] | string | null }): Promise<MarketDataReadinessResponse> => {
    const params = normalizeReadinessSymbols(options?.symbols);
    const response = await apiClient.get<Record<string, unknown>>(buildMarketApiPath('data-readiness'), {
      ...(params ? { params: { symbols: params } } : {}),
    });
    return normalizeMarketDataReadinessPayload(response.data);
  },
  getDataSourceGapRegistry: async (): Promise<DataSourceGapRegistryResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(buildMarketApiPath('data-source-gap-registry'));
    return normalizeDataSourceGapRegistryPayload(response.data);
  },
};

export type MarketTemperatureTrend = 'improving' | 'stable' | 'cooling' | 'rising' | 'falling';

export type MarketTemperatureScore = {
  value: number;
  label: string;
  trend: MarketTemperatureTrend;
  description: string;
};

export type MarketRegimeSynthesisEvidenceItem = {
  key: string;
  label: string;
  family?: string | null;
  pillar?: string | null;
  direction?: string | null;
  signal?: number | null;
  weight?: number | null;
  impact?: number | null;
  expectedDirection?: string | null;
  reason?: string | null;
  source?: string | null;
  sourceTier?: string | null;
  trustLevel?: string | null;
  freshness?: string | null;
  observationOnly?: boolean;
  scoreContributionAllowed?: boolean;
  discountReasons?: string[];
  degradationReason?: string | null;
};

export type MarketRegimeSynthesisEvidenceFamily = {
  key: string;
  label: string;
  state?: string | null;
  pillars: string[];
  evidenceCount: number;
  supportiveCount: number;
  contradictoryCount: number;
  missingCount: number;
  freshness?: string | null;
  observationOnly?: boolean;
};

export type MarketRegimeSynthesisConfidenceCap = {
  value?: number | null;
  label?: string | null;
  reasons: string[];
};

export type MarketRegimeSynthesisObservationBoundary = {
  observationOnly?: boolean;
  decisionGrade?: boolean;
  sourceAuthorityAllowed?: boolean;
  scoreContributionAllowed?: boolean;
  consumerActionBoundary?: string | null;
  notInvestmentAdvice?: boolean;
  detail?: string | null;
};

export type MarketRegimeSynthesisResearchStep = {
  key: string;
  label: string;
  detail?: string | null;
};

export type MarketRegimeSynthesis = {
  contractVersion?: string | null;
  primaryRegime: string;
  secondaryRegimes: string[];
  regimeScores: Record<string, number>;
  regimeLabel?: string | null;
  regimePosture?: string | null;
  evidenceFamilies: MarketRegimeSynthesisEvidenceFamily[];
  supportiveEvidence: MarketRegimeSynthesisEvidenceItem[];
  contradictoryEvidence: MarketRegimeSynthesisEvidenceItem[];
  missingEvidence: MarketRegimeSynthesisEvidenceItem[];
  confidenceCap?: MarketRegimeSynthesisConfidenceCap;
  observationBoundary?: MarketRegimeSynthesisObservationBoundary;
  researchNextSteps: MarketRegimeSynthesisResearchStep[];
  generatedAt?: string | null;
  freshness?: string | null;
  liquidityImpulse?: number | null;
  riskAppetite?: number | null;
  ratesPressure?: number | null;
  dollarPressure?: number | null;
  volatilityStress?: number | null;
  cryptoRiskBeta?: number | null;
  breadthHealth?: number | null;
  chinaRiskAppetite?: number | null;
  rotationQuality?: number | null;
  confidence?: number | null;
  confidenceLabel?: string | null;
  topDrivers: MarketRegimeSynthesisEvidenceItem[];
  counterEvidence: MarketRegimeSynthesisEvidenceItem[];
  dataGaps: MarketRegimeSynthesisEvidenceItem[];
  narrativeBullets: string[];
  evidenceQuality?: Record<string, unknown>;
  notInvestmentAdvice?: boolean;
};

export type MarketDecisionSemanticsItem = Record<string, unknown> & {
  key?: string;
  label?: string;
  detail?: string;
  surface?: string;
  reason?: string;
  reasonCode?: string;
};

export type MarketDecisionSemanticsClaimBoundary = MarketDecisionSemanticsItem & {
  claim?: string;
  allowed?: boolean;
};

export type MarketDirectionReadinessStatus = 'direction_ready' | 'partial_context_only' | 'data_insufficient';
export type MarketDirectionReadinessConfidenceLabel = 'high' | 'medium' | 'low' | 'insufficient' | string;

export type MarketDirectionReadinessPillar = MarketDecisionSemanticsItem & {
  pillar?: string;
  reasonCode?: string;
  evidenceRefs?: MarketDecisionSemanticsItem[];
};

export type MarketDirectionReadinessBucket = {
  count: number;
  items: MarketDirectionReadinessPillar[];
};

export type MarketDirectionReadiness = {
  version?: string;
  status: MarketDirectionReadinessStatus;
  confidenceLabel: MarketDirectionReadinessConfidenceLabel;
  scoreGradePillars: MarketDirectionReadinessBucket;
  observationOnlyPillars: MarketDirectionReadinessBucket;
  missingPillars: MarketDirectionReadinessBucket;
  blockingReasons: string[];
  claimBoundaries: MarketDecisionSemanticsClaimBoundary[];
  notInvestmentAdvice: boolean;
};

export type MarketActionabilityVerdict = 'ready' | 'observe_only' | 'insufficient' | 'blocked' | 'waiting' | string;
export type MarketActionabilityConfidenceLabel = 'high' | 'medium' | 'low' | 'insufficient' | string;
export type MarketActionabilitySourceAuthority = 'scoreGradeAllowed' | 'observationOnly' | 'unavailable' | string;

export type MarketActionabilityConfidence = {
  value: number;
  label: MarketActionabilityConfidenceLabel;
  capReasons: string[];
};

export type MarketActionabilityCoverage = {
  scoreGradeCount: number;
  observationOnlyCount: number;
  missingCount: number;
  totalCount: number;
};

export type MarketActionabilityRegimeContext = {
  primaryRegime: string;
  liquidityImpulse: string;
  rotationPosture: string;
  contradictionCount: number;
  freshnessFloor: string;
};

export type MarketActionabilityFrame = {
  contractVersion?: string;
  verdict: MarketActionabilityVerdict;
  confidence: MarketActionabilityConfidence;
  evidenceCoverage: MarketActionabilityCoverage;
  missingEvidence: string[];
  regimeContext: MarketActionabilityRegimeContext;
  sourceAuthority: MarketActionabilitySourceAuthority;
  freshness: string;
  noAdviceBoundary: boolean;
  nextResearchStep: string;
  debugRef?: string;
};

export type MarketIntelligenceEvidenceState =
  | 'score_grade'
  | 'observation_only'
  | 'degraded'
  | 'missing'
  | 'waiting'
  | 'blocked'
  | string;

export type MarketIntelligenceEvidenceDomainFrame = {
  domain: string;
  state: MarketIntelligenceEvidenceState;
  freshness: string;
  blockingReasons: string[];
  primaryRegime?: string;
  likelyDestination?: string;
  leadingThemeCount?: number;
  breadthValue?: number | null;
  readinessState?: string;
  noAdviceBoundary?: boolean;
};

export type MarketIntelligenceEvidenceFrame = {
  contractVersion?: string;
  frameState: MarketActionabilityVerdict;
  evidenceCoverage: MarketActionabilityCoverage;
  regimeEvidence: MarketIntelligenceEvidenceDomainFrame;
  liquidityEvidence: MarketIntelligenceEvidenceDomainFrame;
  rotationEvidence: MarketIntelligenceEvidenceDomainFrame;
  breadthEvidence: MarketIntelligenceEvidenceDomainFrame;
  scannerContextEvidence: MarketIntelligenceEvidenceDomainFrame;
  missingEvidence: string[];
  blockingReasons: string[];
  sourceAuthority: MarketActionabilitySourceAuthority;
  freshness: string;
  nextEvidenceNeeded: string[];
  noAdviceBoundary: boolean;
  debugRef?: string;
};

export type MarketDecisionSemantics = {
  version?: string;
  posture: string;
  postureConfidence: {
    value?: number | null;
    label?: string | null;
    capReasons: string[];
  };
  exposureBias: string;
  styleTilts: MarketDecisionSemanticsItem[];
  confirmationSignals: MarketDecisionSemanticsItem[];
  invalidationTriggers: MarketDecisionSemanticsItem[];
  counterEvidence: MarketDecisionSemanticsItem[];
  dataGaps: MarketDecisionSemanticsItem[];
  directionReadiness?: MarketDirectionReadiness;
  claimBoundaries: MarketDecisionSemanticsClaimBoundary[];
  notInvestmentAdvice: boolean;
};

export type MarketRegimeSummaryEntry = {
  key: string;
  label: string;
  detail: string;
};

export type MarketRegimeSummary = {
  label: string;
  title: string;
  diagnosticOnly: boolean;
  observationOnly: boolean;
  sourceAuthorityAllowed: boolean;
  scoreContributionAllowed: boolean;
  notInvestmentAdvice: boolean;
  drivers: MarketRegimeSummaryEntry[];
  blockers: MarketRegimeSummaryEntry[];
  contradictions: MarketRegimeSummaryEntry[];
  confidence: {
    value: number;
    label: string;
  };
  confidenceCaps: MarketRegimeSummaryEntry[];
  nextWatchItems: MarketRegimeSummaryEntry[];
  explanation: string;
};

export type MarketTemperatureResponse = {
  source: 'computed' | 'fallback' | 'mixed' | string;
  sourceLabel?: string;
  providerHealth?: MarketProviderHealth;
  updatedAt: string;
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
  isRefreshing?: boolean;
  delayMinutes?: number;
  warning?: string | null;
  confidence?: number;
  reliableInputCount?: number;
  requiredReliableInputCount?: number;
  reliablePanelCount?: number;
  requiredReliablePanelCount?: number;
  fallbackInputCount?: number;
  excludedInputCount?: number;
  isReliable?: boolean;
  temperatureAvailable?: boolean;
  disabledReason?: string | null;
  unavailableReason?: string | null;
  insufficientReliableInputs?: boolean;
  trustLevel?: string;
  sourceTier?: string;
  scoreCap?: number;
  degradationReasons?: string[];
  conclusionAllowed?: boolean;
  researchReadiness?: ResearchReadinessV1;
  marketActionabilityFrame?: MarketActionabilityFrame;
  marketIntelligenceEvidenceFrame?: MarketIntelligenceEvidenceFrame;
  regimeSummary?: MarketRegimeSummary;
  marketRegimeSynthesis?: MarketRegimeSynthesis;
  marketDecisionSemantics?: MarketDecisionSemantics;
  scores: {
    overall: MarketTemperatureScore;
    usRiskAppetite: MarketTemperatureScore;
    cnMoneyEffect: MarketTemperatureScore;
    macroPressure: MarketTemperatureScore;
    liquidity: MarketTemperatureScore;
  };
};

const DEFAULT_MARKET_TEMPERATURE_SCORE: MarketTemperatureScore = {
  value: 50,
  label: '数据不足',
  trend: 'stable',
  description: '数据待补',
};

function normalizeMarketTemperatureScore(score?: Partial<MarketTemperatureScore>): MarketTemperatureScore {
  return {
    ...DEFAULT_MARKET_TEMPERATURE_SCORE,
    ...score,
  };
}

function normalizeMarketRegimeEvidenceItem(
  item?: Partial<MarketRegimeSynthesisEvidenceItem> | null,
): MarketRegimeSynthesisEvidenceItem | null {
  return normalizeMarketIntelligenceEvidenceItem<MarketRegimeSynthesisEvidenceItem>(item, {
    requireLabel: true,
    additionalFields: (value) => ({
      family: value.family,
    }),
  });
}

function normalizeMarketRegimeEvidenceFamily(
  family?: Partial<MarketRegimeSynthesisEvidenceFamily> | null,
): MarketRegimeSynthesisEvidenceFamily | null {
  if (!family?.key || !family.label) {
    return null;
  }
  return {
    key: family.key,
    label: family.label,
    state: family.state,
    pillars: Array.isArray(family.pillars) ? family.pillars.filter(Boolean) : [],
    evidenceCount: typeof family.evidenceCount === 'number' ? family.evidenceCount : 0,
    supportiveCount: typeof family.supportiveCount === 'number' ? family.supportiveCount : 0,
    contradictoryCount: typeof family.contradictoryCount === 'number' ? family.contradictoryCount : 0,
    missingCount: typeof family.missingCount === 'number' ? family.missingCount : 0,
    freshness: family.freshness,
    observationOnly: family.observationOnly,
  };
}

function normalizeMarketRegimeResearchStep(
  step?: Partial<MarketRegimeSynthesisResearchStep> | null,
): MarketRegimeSynthesisResearchStep | null {
  if (!step?.key || !step.label) {
    return null;
  }
  return {
    key: step.key,
    label: step.label,
    detail: step.detail,
  };
}

function normalizeMarketRegimeSynthesis(
  synthesis?: Partial<MarketRegimeSynthesis> | null,
): MarketRegimeSynthesis | undefined {
  if (!synthesis?.primaryRegime) {
    return undefined;
  }

  const normalizeEvidenceList = (
    items?: Array<Partial<MarketRegimeSynthesisEvidenceItem> | null>,
  ): MarketRegimeSynthesisEvidenceItem[] => (
    Array.isArray(items)
      ? items
        .map((item) => normalizeMarketRegimeEvidenceItem(item))
        .filter((item): item is MarketRegimeSynthesisEvidenceItem => Boolean(item))
      : []
  );

  return {
    contractVersion: synthesis.contractVersion,
    primaryRegime: synthesis.primaryRegime,
    secondaryRegimes: Array.isArray(synthesis.secondaryRegimes) ? synthesis.secondaryRegimes.filter(Boolean) : [],
    regimeScores: synthesis.regimeScores || {},
    regimeLabel: synthesis.regimeLabel,
    regimePosture: synthesis.regimePosture,
    evidenceFamilies: Array.isArray(synthesis.evidenceFamilies)
      ? synthesis.evidenceFamilies
        .map((family) => normalizeMarketRegimeEvidenceFamily(family))
        .filter((family): family is MarketRegimeSynthesisEvidenceFamily => Boolean(family))
      : [],
    supportiveEvidence: normalizeEvidenceList(synthesis.supportiveEvidence),
    contradictoryEvidence: normalizeEvidenceList(synthesis.contradictoryEvidence),
    missingEvidence: normalizeEvidenceList(synthesis.missingEvidence),
    confidenceCap: synthesis.confidenceCap
      ? {
        value: synthesis.confidenceCap.value,
        label: synthesis.confidenceCap.label,
        reasons: Array.isArray(synthesis.confidenceCap.reasons) ? synthesis.confidenceCap.reasons.filter(Boolean) : [],
      }
      : undefined,
    observationBoundary: synthesis.observationBoundary ? { ...synthesis.observationBoundary } : undefined,
    researchNextSteps: Array.isArray(synthesis.researchNextSteps)
      ? synthesis.researchNextSteps
        .map((step) => normalizeMarketRegimeResearchStep(step))
        .filter((step): step is MarketRegimeSynthesisResearchStep => Boolean(step))
      : [],
    generatedAt: synthesis.generatedAt,
    freshness: synthesis.freshness,
    liquidityImpulse: synthesis.liquidityImpulse,
    riskAppetite: synthesis.riskAppetite,
    ratesPressure: synthesis.ratesPressure,
    dollarPressure: synthesis.dollarPressure,
    volatilityStress: synthesis.volatilityStress,
    cryptoRiskBeta: synthesis.cryptoRiskBeta,
    breadthHealth: synthesis.breadthHealth,
    chinaRiskAppetite: synthesis.chinaRiskAppetite,
    rotationQuality: synthesis.rotationQuality,
    confidence: synthesis.confidence,
    confidenceLabel: synthesis.confidenceLabel,
    topDrivers: normalizeEvidenceList(synthesis.topDrivers),
    counterEvidence: normalizeEvidenceList(synthesis.counterEvidence),
    dataGaps: normalizeEvidenceList(synthesis.dataGaps),
    narrativeBullets: Array.isArray(synthesis.narrativeBullets) ? synthesis.narrativeBullets.filter(Boolean) : [],
    evidenceQuality: synthesis.evidenceQuality || {},
    notInvestmentAdvice: synthesis.notInvestmentAdvice,
  };
}

function normalizeMarketDecisionSemanticsList<T extends MarketDecisionSemanticsItem>(
  items?: Array<T | null> | null,
): T[] {
  return Array.isArray(items)
    ? items
      .filter((item): item is T => Boolean(item && typeof item === 'object'))
      .map((item) => ({ ...item }))
    : [];
}

function normalizeMarketDirectionReadinessBucket(
  bucket?: Partial<MarketDirectionReadinessBucket> | null,
): MarketDirectionReadinessBucket {
  const items = normalizeMarketDecisionSemanticsList(bucket?.items);
  return {
    count: typeof bucket?.count === 'number' ? bucket.count : items.length,
    items,
  };
}

function normalizeMarketDirectionReadiness(
  readiness?: Partial<MarketDirectionReadiness> | null,
): MarketDirectionReadiness | undefined {
  if (!readiness?.status) {
    return undefined;
  }
  return {
    version: readiness.version,
    status: readiness.status,
    confidenceLabel: readiness.confidenceLabel || 'insufficient',
    scoreGradePillars: normalizeMarketDirectionReadinessBucket(readiness.scoreGradePillars),
    observationOnlyPillars: normalizeMarketDirectionReadinessBucket(readiness.observationOnlyPillars),
    missingPillars: normalizeMarketDirectionReadinessBucket(readiness.missingPillars),
    blockingReasons: Array.isArray(readiness.blockingReasons) ? readiness.blockingReasons.filter(Boolean) : [],
    claimBoundaries: normalizeMarketDecisionSemanticsList(readiness.claimBoundaries),
    notInvestmentAdvice: readiness.notInvestmentAdvice !== false,
  };
}

function normalizeMarketDecisionSemantics(
  semantics?: Partial<MarketDecisionSemantics> | null,
): MarketDecisionSemantics | undefined {
  if (!semantics?.posture) {
    return undefined;
  }
  return {
    version: semantics.version,
    posture: semantics.posture,
    postureConfidence: {
      value: semantics.postureConfidence?.value,
      label: semantics.postureConfidence?.label,
      capReasons: Array.isArray(semantics.postureConfidence?.capReasons)
        ? semantics.postureConfidence.capReasons.filter(Boolean)
        : [],
    },
    exposureBias: semantics.exposureBias || 'no_bias_data_insufficient',
    styleTilts: normalizeMarketDecisionSemanticsList(semantics.styleTilts),
    confirmationSignals: normalizeMarketDecisionSemanticsList(semantics.confirmationSignals),
    invalidationTriggers: normalizeMarketDecisionSemanticsList(semantics.invalidationTriggers),
    counterEvidence: normalizeMarketDecisionSemanticsList(semantics.counterEvidence),
    dataGaps: normalizeMarketDecisionSemanticsList(semantics.dataGaps),
    directionReadiness: normalizeMarketDirectionReadiness(semantics.directionReadiness),
    claimBoundaries: normalizeMarketDecisionSemanticsList(semantics.claimBoundaries),
    notInvestmentAdvice: semantics.notInvestmentAdvice !== false,
  };
}

function normalizeMarketActionabilityCoverage(
  coverage?: Partial<MarketActionabilityCoverage> | null,
): MarketActionabilityCoverage {
  return {
    scoreGradeCount: typeof coverage?.scoreGradeCount === 'number' ? coverage.scoreGradeCount : 0,
    observationOnlyCount: typeof coverage?.observationOnlyCount === 'number' ? coverage.observationOnlyCount : 0,
    missingCount: typeof coverage?.missingCount === 'number' ? coverage.missingCount : 0,
    totalCount: typeof coverage?.totalCount === 'number' ? coverage.totalCount : 0,
  };
}

function normalizeMarketActionabilityConfidence(
  confidence?: Partial<MarketActionabilityConfidence> | null,
): MarketActionabilityConfidence {
  return {
    value: typeof confidence?.value === 'number' ? confidence.value : 0,
    label: confidence?.label || 'insufficient',
    capReasons: Array.isArray(confidence?.capReasons) ? confidence.capReasons.filter(Boolean) : [],
  };
}

function normalizeMarketActionabilityRegimeContext(
  regimeContext?: Partial<MarketActionabilityRegimeContext> | null,
): MarketActionabilityRegimeContext {
  return {
    primaryRegime: regimeContext?.primaryRegime || 'data_insufficient',
    liquidityImpulse: regimeContext?.liquidityImpulse || 'data_insufficient',
    rotationPosture: regimeContext?.rotationPosture || 'unavailable',
    contradictionCount: typeof regimeContext?.contradictionCount === 'number' ? regimeContext.contradictionCount : 0,
    freshnessFloor: regimeContext?.freshnessFloor || 'unknown',
  };
}

function normalizeMarketActionabilityFrame(
  frame?: Partial<MarketActionabilityFrame> | null,
): MarketActionabilityFrame | undefined {
  if (!frame?.verdict) {
    return undefined;
  }
  return {
    contractVersion: frame.contractVersion,
    verdict: frame.verdict,
    confidence: normalizeMarketActionabilityConfidence(frame.confidence),
    evidenceCoverage: normalizeMarketActionabilityCoverage(frame.evidenceCoverage),
    missingEvidence: Array.isArray(frame.missingEvidence) ? frame.missingEvidence.filter(Boolean) : [],
    regimeContext: normalizeMarketActionabilityRegimeContext(frame.regimeContext),
    sourceAuthority: frame.sourceAuthority || 'unavailable',
    freshness: frame.freshness || 'unknown',
    noAdviceBoundary: frame.noAdviceBoundary !== false,
    nextResearchStep: frame.nextResearchStep || '',
    debugRef: frame.debugRef,
  };
}

function normalizeMarketIntelligenceEvidenceDomainFrame(
  frame?: Partial<MarketIntelligenceEvidenceDomainFrame> | null,
): MarketIntelligenceEvidenceDomainFrame {
  return {
    domain: frame?.domain || 'unknown',
    state: frame?.state || 'missing',
    freshness: frame?.freshness || 'unknown',
    blockingReasons: Array.isArray(frame?.blockingReasons) ? frame.blockingReasons.filter(Boolean) : [],
    primaryRegime: frame?.primaryRegime,
    likelyDestination: frame?.likelyDestination,
    leadingThemeCount: typeof frame?.leadingThemeCount === 'number' ? frame.leadingThemeCount : undefined,
    breadthValue: typeof frame?.breadthValue === 'number' ? frame.breadthValue : frame?.breadthValue === null ? null : undefined,
    readinessState: frame?.readinessState,
    noAdviceBoundary: typeof frame?.noAdviceBoundary === 'boolean' ? frame.noAdviceBoundary : undefined,
  };
}

function normalizeMarketIntelligenceEvidenceFrame(
  frame?: Partial<MarketIntelligenceEvidenceFrame> | null,
): MarketIntelligenceEvidenceFrame | undefined {
  if (!frame?.frameState) {
    return undefined;
  }
  return {
    contractVersion: frame.contractVersion,
    frameState: frame.frameState,
    evidenceCoverage: normalizeMarketActionabilityCoverage(frame.evidenceCoverage),
    regimeEvidence: normalizeMarketIntelligenceEvidenceDomainFrame(frame.regimeEvidence),
    liquidityEvidence: normalizeMarketIntelligenceEvidenceDomainFrame(frame.liquidityEvidence),
    rotationEvidence: normalizeMarketIntelligenceEvidenceDomainFrame(frame.rotationEvidence),
    breadthEvidence: normalizeMarketIntelligenceEvidenceDomainFrame(frame.breadthEvidence),
    scannerContextEvidence: normalizeMarketIntelligenceEvidenceDomainFrame(frame.scannerContextEvidence),
    missingEvidence: Array.isArray(frame.missingEvidence) ? frame.missingEvidence.filter(Boolean) : [],
    blockingReasons: Array.isArray(frame.blockingReasons) ? frame.blockingReasons.filter(Boolean) : [],
    sourceAuthority: frame.sourceAuthority || 'unavailable',
    freshness: frame.freshness || 'unknown',
    nextEvidenceNeeded: Array.isArray(frame.nextEvidenceNeeded) ? frame.nextEvidenceNeeded.filter(Boolean) : [],
    noAdviceBoundary: frame.noAdviceBoundary !== false,
    debugRef: frame.debugRef,
  };
}

function normalizeMarketRegimeSummaryEntry(
  item?: Partial<MarketRegimeSummaryEntry> | null,
): MarketRegimeSummaryEntry | null {
  if (!item?.key || !item.label || !item.detail) {
    return null;
  }
  return {
    key: item.key,
    label: item.label,
    detail: item.detail,
  };
}

function normalizeMarketRegimeSummary(
  summary?: Partial<MarketRegimeSummary> | null,
): MarketRegimeSummary | undefined {
  if (!summary?.label || !summary.title) {
    return undefined;
  }

  const normalizeEntries = (
    items?: Array<Partial<MarketRegimeSummaryEntry> | null>,
  ): MarketRegimeSummaryEntry[] => (
    Array.isArray(items)
      ? items
        .map((item) => normalizeMarketRegimeSummaryEntry(item))
        .filter((item): item is MarketRegimeSummaryEntry => Boolean(item))
      : []
  );

  return {
    label: summary.label,
    title: summary.title,
    diagnosticOnly: summary.diagnosticOnly !== false,
    observationOnly: summary.observationOnly !== false,
    sourceAuthorityAllowed: summary.sourceAuthorityAllowed === true,
    scoreContributionAllowed: summary.scoreContributionAllowed === true,
    notInvestmentAdvice: summary.notInvestmentAdvice !== false,
    drivers: normalizeEntries(summary.drivers),
    blockers: normalizeEntries(summary.blockers),
    contradictions: normalizeEntries(summary.contradictions),
    confidence: {
      value: typeof summary.confidence?.value === 'number' ? summary.confidence.value : 0,
      label: summary.confidence?.label || '',
    },
    confidenceCaps: normalizeEntries(summary.confidenceCaps),
    nextWatchItems: normalizeEntries(summary.nextWatchItems),
    explanation: summary.explanation || '',
  };
}

export function normalizeMarketTemperatureResponse(
  payload?: Partial<MarketTemperatureResponse> | null,
): MarketTemperatureResponse {
  const scores: Partial<MarketTemperatureResponse['scores']> = payload?.scores || {};
  const hasCompleteScores = Boolean(
    scores.overall
    && scores.usRiskAppetite
    && scores.cnMoneyEffect
    && scores.macroPressure
    && scores.liquidity,
  );
  const inferredReliable = payload?.confidence != null
    ? payload.confidence >= 0.45 && (payload.reliableInputCount == null || payload.reliableInputCount >= 3)
    : false;
  const temperatureAvailable = payload?.temperatureAvailable ?? payload?.isReliable ?? inferredReliable;
  const conclusionAllowed = payload?.conclusionAllowed ?? temperatureAvailable;
  const isReliable = (
    payload?.isReliable === false
    || temperatureAvailable === false
    || conclusionAllowed === false
  )
    ? false
    : hasCompleteScores
      ? payload?.isReliable ?? inferredReliable
      : false;

  return {
    source: payload?.source || 'fallback',
    sourceLabel: normalizeMarketConsumerSourceLabel(payload?.sourceLabel, payload?.source),
    providerHealth: normalizeMarketProviderHealth(payload?.providerHealth),
    updatedAt: payload?.updatedAt || new Date().toISOString(),
    asOf: payload?.asOf,
    freshness: payload?.freshness,
    isFallback: payload?.isFallback,
    isStale: payload?.isStale,
    isRefreshing: payload?.isRefreshing,
    delayMinutes: payload?.delayMinutes,
    warning: normalizeMarketConsumerText(payload?.warning) || payload?.warning,
    confidence: payload?.confidence,
    reliableInputCount: payload?.reliableInputCount,
    requiredReliableInputCount: payload?.requiredReliableInputCount,
    reliablePanelCount: payload?.reliablePanelCount,
    requiredReliablePanelCount: payload?.requiredReliablePanelCount,
    fallbackInputCount: payload?.fallbackInputCount,
    excludedInputCount: payload?.excludedInputCount,
    isReliable,
    temperatureAvailable,
    disabledReason: payload?.disabledReason,
    unavailableReason: payload?.unavailableReason,
    insufficientReliableInputs: payload?.insufficientReliableInputs,
    trustLevel: payload?.trustLevel,
    sourceTier: payload?.sourceTier,
    scoreCap: payload?.scoreCap,
    degradationReasons: payload?.degradationReasons,
    conclusionAllowed,
    researchReadiness: payload?.researchReadiness,
    marketActionabilityFrame: normalizeMarketActionabilityFrame(payload?.marketActionabilityFrame),
    marketIntelligenceEvidenceFrame: normalizeMarketIntelligenceEvidenceFrame(payload?.marketIntelligenceEvidenceFrame),
    regimeSummary: normalizeMarketRegimeSummary(payload?.regimeSummary),
    marketRegimeSynthesis: normalizeMarketRegimeSynthesis(payload?.marketRegimeSynthesis),
    marketDecisionSemantics: normalizeMarketDecisionSemantics(payload?.marketDecisionSemantics),
    scores: {
      overall: normalizeMarketTemperatureScore(scores.overall),
      usRiskAppetite: normalizeMarketTemperatureScore(scores.usRiskAppetite),
      cnMoneyEffect: normalizeMarketTemperatureScore(scores.cnMoneyEffect),
      macroPressure: normalizeMarketTemperatureScore(scores.macroPressure),
      liquidity: normalizeMarketTemperatureScore(scores.liquidity),
    },
  };
}

export type MarketBriefingItem = {
  title: string;
  message: string;
  severity: 'positive' | 'neutral' | 'warning' | 'risk';
  category: 'us' | 'cn' | 'macro' | 'liquidity' | 'risk' | string;
  confidence?: number;
};

export type MarketBriefingResponse = {
  source: 'computed' | 'fallback' | 'mixed' | string;
  sourceLabel?: string;
  providerHealth?: MarketProviderHealth;
  updatedAt: string;
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
  isRefreshing?: boolean;
  delayMinutes?: number;
  warning?: string | null;
  confidence?: number;
  reliableInputCount?: number;
  fallbackInputCount?: number;
  excludedInputCount?: number;
  isReliable?: boolean;
  items: MarketBriefingItem[];
};

export type MarketFutureItem = {
  name: string;
  symbol: string;
  value: number | null;
  change: number | null;
  changePercent: number | null;
  market: string;
  session: string;
  sparkline: number[];
  source: string;
  sourceLabel?: string;
  providerHealth?: MarketProviderHealth;
  updatedAt?: string;
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
  isRefreshing?: boolean;
  delayMinutes?: number;
  warning?: string | null;
};

export type MarketFuturesResponse = {
  source: 'fallback' | 'public' | 'mixed' | string;
  sourceLabel?: string;
  providerHealth?: MarketProviderHealth;
  updatedAt: string;
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
  isRefreshing?: boolean;
  delayMinutes?: number;
  warning?: string | null;
  items: MarketFutureItem[];
};

export type CnShortSentimentResponse = {
  source: 'fallback' | 'public' | 'mixed' | string;
  sourceLabel?: string;
  providerHealth?: MarketProviderHealth;
  updatedAt: string;
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
  isRefreshing?: boolean;
  delayMinutes?: number;
  warning?: string | null;
  sentimentScore: number;
  summary: string;
  metrics: {
    limitUpCount: number;
    limitDownCount: number;
    failedLimitUpRate: number;
    maxConsecutiveLimitUps: number;
    yesterdayLimitUpPerformance: number;
    firstBoardCount: number;
    secondBoardCount: number;
    highBoardCount: number;
    twentyCmLimitUpCount: number;
    stRiskLevel?: string;
  };
};
