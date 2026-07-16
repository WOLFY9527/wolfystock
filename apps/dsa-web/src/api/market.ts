import apiClient from './index';
import type { MarketDataMeta, MarketOverviewPanel, MarketOverviewItem, MarketProviderHealth } from './marketOverview';
import { isMarketDataFreshnessValue } from './marketOverview';
import { toCamelCase } from './utils';
import { API_BASE_URL } from '../utils/constants';
import { buildAbsoluteApiUrl, joinApiPath } from './path';
import { normalizeMarketIntelligenceEvidenceItem } from './marketIntelligenceEvidence';
import type { ResearchReadinessV1 } from '../types/researchReadiness';

function isMarketContractRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function hasMarketContractText(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isFiniteMarketContractNumberOrNull(value: unknown): boolean {
  return value === null || (typeof value === 'number' && Number.isFinite(value));
}

function isMarketContractStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

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
  providerFreshness?: MarketDataMeta['providerFreshness'];
  dataQuality?: MarketDataMeta['dataQuality'];
  updatedAt?: string;
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isProxy?: boolean;
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
  sourceConfidence?: string | null;
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
  proxyFor?: string | null;
  proxySymbol?: string | null;
  proxyLabel?: string | null;
  officialSeriesId?: string | null;
  officialObservationDate?: string | null;
  officialAsOf?: string | null;
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
  /** Explicit panel status when backend already projects one (Market Overview-style). */
  status?: MarketOverviewPanel['status'] | string | null;
  source?: string | null;
  sourceLabel?: string | null;
  sourceType?: string | null;
  providerHealth?: MarketProviderHealth;
  providerFreshness?: MarketDataMeta['providerFreshness'];
  dataQuality?: MarketDataMeta['dataQuality'];
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isProxy?: boolean;
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
  sourceConfidence?: string | null;
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
  proxyFor?: string | null;
  proxySymbol?: string | null;
  proxyLabel?: string | null;
  officialSeriesId?: string | null;
  officialObservationDate?: string | null;
  officialAsOf?: string | null;
  degradationReason?: string | null;
  degradationReasons?: string[];
  warning?: string | null;
  logSessionId?: string | null;
};

const EXPLICIT_PANEL_STATUSES = new Set<MarketOverviewPanel['status']>([
  'success',
  'partial',
  'unavailable',
  'failure',
]);

function isExplicitPanelStatus(value: unknown): value is MarketOverviewPanel['status'] {
  return typeof value === 'string' && EXPLICIT_PANEL_STATUSES.has(value as MarketOverviewPanel['status']);
}

/** Preserve backend evidence timestamps; never invent client wall-clock time. */
function resolveSnapshotEvidenceTimestamp(
  ...candidates: Array<string | null | undefined>
): string | undefined {
  for (const candidate of candidates) {
    const text = String(candidate || '').trim();
    if (text) {
      return text;
    }
  }
  return undefined;
}

function normalizeItem(item: MarketSnapshotItem): MarketOverviewItem {
  const hoverDetails = Array.isArray(item.hoverDetails) ? [...item.hoverDetails] : [];
  if (item.market) {
    hoverDetails.push(`Market ${item.market}`);
  }
  if (item.explanation) {
    hoverDetails.push(item.explanation);
  }
  // Prefer first present field. Explicit null means unavailable evidence; omit only when both absent.
  // Observed zero remains 0 (not missing).
  const value = item.price !== undefined ? item.price : item.value;
  const changePct = item.changePercent !== undefined ? item.changePercent : item.change;
  return {
    symbol: item.symbol || '',
    label: item.label || item.name || item.symbol || '',
    value,
    unit: item.unit,
    changePct,
    changeText: item.changeText,
    riskDirection: item.riskDirection,
    trend: Array.isArray(item.trend) ? item.trend : Array.isArray(item.sparkline) ? item.sparkline : [],
    source: item.source || undefined,
    sourceLabel: item.sourceLabel || undefined,
    sourceType: item.sourceType || undefined,
    providerHealth: item.providerHealth,
    providerFreshness: item.providerFreshness,
    dataQuality: item.dataQuality,
    updatedAt: resolveSnapshotEvidenceTimestamp(item.updatedAt),
    asOf: resolveSnapshotEvidenceTimestamp(item.asOf),
    freshness: item.freshness,
    isProxy: item.isProxy,
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
    sourceConfidence: item.sourceConfidence,
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
    proxyFor: item.proxyFor,
    proxySymbol: item.proxySymbol,
    proxyLabel: item.proxyLabel,
    officialSeriesId: item.officialSeriesId,
    officialObservationDate: item.officialObservationDate,
    officialAsOf: item.officialAsOf,
    degradationReason: item.degradationReason,
    degradationReasons: item.degradationReasons,
    warning: item.warning,
    hoverDetails,
  };
}

function hasUsableSnapshotValue(payload: MarketSnapshotPayload): boolean {
  return Boolean(
    Array.isArray(payload.items)
    && payload.items.some((item) => {
      if (!item) {
        return false;
      }
      // Observed zero is usable evidence; null/undefined is not.
      if (typeof item.price === 'number' && Number.isFinite(item.price)) {
        return true;
      }
      if (typeof item.value === 'number' && Number.isFinite(item.value)) {
        return true;
      }
      return false;
    })
  );
}

function isMarketSnapshotItemContract(value: unknown): value is MarketSnapshotItem {
  if (!isMarketContractRecord(value) || !hasMarketContractText(value.symbol)) {
    return false;
  }
  for (const key of ['price', 'value', 'change', 'changePercent'] as const) {
    if (key in value && value[key] !== undefined && !isFiniteMarketContractNumberOrNull(value[key])) {
      return false;
    }
  }
  for (const key of ['trend', 'sparkline'] as const) {
    if (key in value && value[key] !== undefined && (
      !Array.isArray(value[key])
      || !value[key].every((point) => typeof point === 'number' && Number.isFinite(point))
    )) {
      return false;
    }
  }
  return value.freshness === undefined || isMarketDataFreshnessValue(value.freshness);
}

function hasMarketSnapshotAuthority(payload: MarketSnapshotPayload): boolean {
  return hasMarketContractText(payload.source)
    && !['unknown', 'unavailable', 'error'].includes(payload.source.trim().toLowerCase())
    && isMarketDataFreshnessValue(payload.freshness)
    && !['unknown', 'unavailable', 'error'].includes(payload.freshness);
}

function isExplicitlyUnavailableSnapshot(payload: MarketSnapshotPayload): boolean {
  const freshness = String(payload.freshness || '').trim().toLowerCase();
  const source = String(payload.source || '').trim().toLowerCase();
  const providerStatus = String(payload.providerHealth?.status || '').trim().toLowerCase();
  const providerFreshnessState = String(payload.providerFreshness?.state || '').trim().toLowerCase();
  return Boolean(
    payload.isUnavailable
    || payload.providerFreshness?.isUnavailable
    || providerStatus === 'unavailable'
    || freshness === 'unavailable'
    || freshness === 'error'
    || providerFreshnessState === 'unavailable'
    || providerFreshnessState === 'error'
    || source === 'unavailable'
  );
}

function deriveSnapshotPanelStatus(payload: MarketSnapshotPayload): MarketOverviewPanel['status'] {
  // Prefer explicit backend panel status when present (Market Overview contract).
  if (isExplicitPanelStatus(payload.status)) {
    return payload.status;
  }

  const hasUsableValue = hasUsableSnapshotValue(payload);
  const freshness = String(payload.freshness || '').trim().toLowerCase();
  const source = String(payload.source || '').trim().toLowerCase();
  const providerStatus = String(payload.providerHealth?.status || '').trim().toLowerCase();
  const providerFreshnessState = String(payload.providerFreshness?.state || '').trim().toLowerCase();
  const explicitlyUnavailable = isExplicitlyUnavailableSnapshot(payload);
  const hasDegradedValue = Boolean(
    payload.isPartial
    || payload.isStale
    || payload.isFallback
    || payload.fallbackUsed
    || payload.isFromSnapshot
    || payload.isProxy
    || payload.refreshError
    || providerStatus === 'partial'
    || providerStatus === 'stale'
    || providerStatus === 'fallback'
    || freshness === 'partial'
    || freshness === 'stale'
    || freshness === 'fallback'
    || freshness === 'proxy'
    || freshness === 'delayed'
    || freshness === 'cached'
    || providerFreshnessState === 'partial'
    || providerFreshnessState === 'stale'
    || providerFreshnessState === 'fallback'
    || providerFreshnessState === 'proxy'
    || providerFreshnessState === 'delayed'
    || providerFreshnessState === 'cached'
    || payload.providerFreshness?.isProxy
    || payload.providerFreshness?.isStale
  );

  // Explicit unavailability must not be promoted to success by numeric presence alone.
  if (explicitlyUnavailable) {
    return hasUsableValue ? 'partial' : 'unavailable';
  }

  if (hasUsableValue) {
    return hasDegradedValue ? 'partial' : 'success';
  }

  if (
    payload.isFallback
    || payload.fallbackUsed
    || freshness === 'fallback'
    || source === 'fallback'
    || providerStatus === 'fallback'
  ) {
    return 'unavailable';
  }

  if (payload.error || payload.refreshError || payload.lastError) {
    return 'failure';
  }

  // Missing usable evidence without explicit success signals is unavailable, not success.
  return 'unavailable';
}

function deriveSnapshotPanelErrorMessage(
  payload: MarketSnapshotPayload,
  status: MarketOverviewPanel['status'],
): string | null {
  if (status === 'success' || status === 'partial') {
    return null;
  }
  return payload.error || payload.refreshError || payload.lastError || null;
}

function normalizeMarketSnapshotPayload(rawPayload: unknown, panelName: string): MarketOverviewPanel {
  if (!isMarketContractRecord(rawPayload)) {
    throw new Error('invalid_market_snapshot_contract');
  }
  const payload = toCamelCase<MarketSnapshotPayload>(rawPayload);
  if (!Array.isArray(payload.items) || !payload.items.every(isMarketSnapshotItemContract)) {
    throw new Error('invalid_market_snapshot_contract');
  }
  if (payload.status != null && !isExplicitPanelStatus(payload.status)) {
    throw new Error('invalid_market_snapshot_contract');
  }
  if (
    (hasUsableSnapshotValue(payload) || payload.status === 'success' || payload.status === 'partial')
    && !hasMarketSnapshotAuthority(payload)
  ) {
    throw new Error('invalid_market_snapshot_contract');
  }
  const status = deriveSnapshotPanelStatus(payload);
  const evidenceUpdatedAt = resolveSnapshotEvidenceTimestamp(
    payload.updatedAt,
    payload.lastUpdate,
  );
  const evidenceLastRefreshAt = resolveSnapshotEvidenceTimestamp(
    payload.lastUpdate,
    payload.updatedAt,
  );
  // lastRefreshAt is required by MarketOverviewPanel; preserve missing as empty string (not client now).
  const lastRefreshAt = evidenceLastRefreshAt || '';
  return {
    panelName,
    lastRefreshAt,
    status,
    errorMessage: deriveSnapshotPanelErrorMessage(payload, status),
    logSessionId: payload.logSessionId,
    source: payload.source || undefined,
    sourceLabel: payload.sourceLabel || undefined,
    sourceType: payload.sourceType || undefined,
    providerHealth: payload.providerHealth,
    providerFreshness: payload.providerFreshness,
    dataQuality: payload.dataQuality,
    updatedAt: evidenceUpdatedAt,
    asOf: resolveSnapshotEvidenceTimestamp(payload.asOf),
    freshness: payload.freshness,
    isProxy: payload.isProxy,
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
    sourceConfidence: payload.sourceConfidence,
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
    proxyFor: payload.proxyFor,
    proxySymbol: payload.proxySymbol,
    proxyLabel: payload.proxyLabel,
    officialSeriesId: payload.officialSeriesId,
    officialObservationDate: payload.officialObservationDate,
    officialAsOf: payload.officialAsOf,
    degradationReason: payload.degradationReason,
    degradationReasons: payload.degradationReasons,
    warning: payload.warning,
    items: payload.items.map(normalizeItem),
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

export type CrossAssetDriverReadinessState =
  | 'available'
  | 'missing'
  | 'stale'
  | 'insufficient_history'
  | 'not_configured'
  | string;

export type CrossAssetDriverIdentifier = {
  kind: string;
  value: string;
  market?: string;
};

export type CrossAssetDriverCachedOhlcv = {
  requiredBars: number;
  usableBars: number;
  missingBars: number;
  cacheState: string;
  freshnessState: string;
  latestBarDate?: string | null;
};

export type CrossAssetDriverReadinessItem = {
  category: string;
  label: string;
  supported: boolean;
  state: CrossAssetDriverReadinessState;
  configuredIdentifiers: CrossAssetDriverIdentifier[];
  cachedOhlcv: CrossAssetDriverCachedOhlcv;
  missingReasons: string[];
  consumerSafeSummary: string;
};

export type CrossAssetDriverReadiness = {
  contractVersion: string;
  consumerSafe: boolean;
  diagnosticOnly: boolean;
  networkCallsEnabled: boolean;
  externalProviderCalls: boolean;
  mutationEnabled: boolean;
  supportedStates: string[];
  consumerSummary: string;
  summary: Record<string, number>;
  drivers: CrossAssetDriverReadinessItem[];
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

export type CrossAssetDriverReadinessChip = {
  key: string;
  label: string;
  variant: 'success' | 'info' | 'caution' | 'neutral';
};

export type CrossAssetDriverReadinessView = {
  label: string;
  variant: 'success' | 'info' | 'caution' | 'neutral';
  chips: CrossAssetDriverReadinessChip[];
  note: string;
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
  crossAssetDriverReadiness?: CrossAssetDriverReadiness;
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

export type NewsCatalystCapabilityMapItem = {
  capabilityKey: string;
  consumerLabel: string;
  state: string;
  freshnessState: string;
  scope: string;
  evidenceState: string;
  missingReason: string;
  operatorNextAction: string;
};

export type DataSourceGapActionType =
  | 'provider-entitlement'
  | 'provider-integration'
  | 'evidence-validation'
  | 'schema-contract'
  | 'frontend-consumption'
  | 'manual-review'
  | 'blocked'
  | string;

export type DataSourceGapActionPriority = 'critical' | 'high' | 'medium' | 'low' | string;

export type DataSourceGapActionStatus =
  | 'ready-to-start'
  | 'blocked'
  | 'waiting-entitlement'
  | 'waiting-evidence'
  | 'planned'
  | 'not-required'
  | string;

export type DataSourceAcquisitionBlockerType =
  | 'entitlement'
  | 'provider-integration'
  | 'evidence-validation'
  | 'schema-contract'
  | 'frontend-consumption'
  | 'protected-review'
  | 'unknown'
  | string;

export type DataSourceGapRegistryActionPlanItem = {
  actionKey: string;
  actionLabel: string;
  actionType: DataSourceGapActionType;
  priority: DataSourceGapActionPriority;
  status: DataSourceGapActionStatus;
  reason: string;
  requiredEvidence?: string[];
  blockedBy?: string[];
  affectedSurfacesOrCapabilities?: string[];
  nextConcreteStep: string;
  requiresExternalProviderLicenseWork?: boolean;
  requiresProtectedDomainReview?: boolean;
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
  capabilityMap?: NewsCatalystCapabilityMapItem[];
  surfaceImpactMatrix?: DataSourceSurfaceImpact[];
  integrationActionPlan?: DataSourceGapRegistryActionPlanItem[];
};

export type DataSourceAcquisitionPriorityQueueItem = {
  familyKey: string;
  familyLabel: string;
  priority: DataSourceGapActionPriority;
  priorityReason: string;
  readinessState: DataSourceGapRegistryStatus;
  primaryBlockerType: DataSourceAcquisitionBlockerType;
  affectedSurfaceCount?: number;
  blockedOrDegradedCapabilityCount?: number;
  externalEntitlementRequired?: boolean;
  protectedDomainReviewRequired?: boolean;
  nextConcreteStep: string;
  requiredEvidence?: string[];
  consumerSafeWarning: string;
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
  acquisitionPriorityQueue?: DataSourceAcquisitionPriorityQueueItem[];
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
  capabilityMap: NewsCatalystCapabilityMapItem[];
  surfaceImpactMatrix: DataSourceSurfaceImpactView[];
  integrationActionPlan: DataSourceGapRegistryActionPlanItemView[];
};

export type DataSourceSurfaceImpactView = {
  surfaceKey: string;
  surfaceLabel: string;
  impactState: DataSourceGapRegistryStatusView;
  impactReason: string;
  affectedCapability: string;
  nextEvidenceStep: string;
};

export type DataSourceGapRegistryActionPlanItemView = {
  actionKey: string;
  actionLabel: string;
  actionTypeKey: string;
  actionType: DataSourceGapRegistryStatusView;
  priorityKey: string;
  priority: DataSourceGapRegistryStatusView;
  status: DataSourceGapRegistryStatusView;
  reason: string;
  requiredEvidence: string[];
  blockedBy: string[];
  affectedSurfacesOrCapabilities: string[];
  nextConcreteStep: string;
  externalProviderLicenseWork: string;
  externalProviderLicenseWorkVariant: DataSourceGapRegistryStatusView['variant'];
  protectedDomainReview: string;
  protectedDomainReviewVariant: DataSourceGapRegistryStatusView['variant'];
};

export type DataSourceAcquisitionPriorityQueueItemView = {
  familyKey: string;
  familyLabel: string;
  priorityKey: string;
  priority: DataSourceGapRegistryStatusView;
  priorityReason: string;
  readinessStateKey: string;
  readinessState: DataSourceGapRegistryStatusView;
  primaryBlockerTypeKey: string;
  primaryBlockerType: DataSourceGapRegistryStatusView;
  affectedSurfaceCount: number;
  blockedOrDegradedCapabilityCount: number;
  externalEntitlementRequired: string;
  externalEntitlementVariant: DataSourceGapRegistryStatusView['variant'];
  protectedDomainReviewRequired: string;
  protectedDomainReviewVariant: DataSourceGapRegistryStatusView['variant'];
  nextConcreteStep: string;
  requiredEvidence: string[];
  consumerSafeWarning: string;
};

export type DataSourceAcquisitionWorkbenchCount = {
  key: string;
  label: string;
  count: number;
  variant: DataSourceGapRegistryStatusView['variant'];
};

export type DataSourceAcquisitionWorkbenchAction = {
  familyKey: string;
  familyLabel: string;
  priorityKey: string;
  priority: DataSourceGapRegistryStatusView;
  primaryBlockerType: DataSourceGapRegistryStatusView;
  affectedSurfaceCount: number;
  nextConcreteStep: string;
  requiredEvidence: string[];
  affectedSurfaces: string[];
};

export type DataSourceAcquisitionWorkbenchLane = {
  key: 'protected-review' | 'external-entitlement' | 'evidence-validation';
  label: string;
  description: string;
  count: number;
  variant: DataSourceGapRegistryStatusView['variant'];
  items: DataSourceAcquisitionWorkbenchAction[];
  emptyCopy: string;
};

export type DataSourceGapRegistryGroupId =
  | 'quote_market'
  | 'news_catalyst'
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
  workbench: {
    blockedMissingPartialFamilyCount: number;
    urgentQueueCount: number;
    unknownFieldCount: number;
    consumerSafeWarning: string;
    blockerTypeCounts: DataSourceAcquisitionWorkbenchCount[];
    priorityCounts: DataSourceAcquisitionWorkbenchCount[];
    topNextActions: DataSourceAcquisitionWorkbenchAction[];
    lanes: DataSourceAcquisitionWorkbenchLane[];
  };
  acquisitionPriorityQueue: DataSourceAcquisitionPriorityQueueItemView[];
  families: DataSourceGapRegistryFamilyView[];
  groups: DataSourceGapRegistryGroupView[];
};

export type ProfessionalDataCapabilityStatus =
  | 'live'
  | 'degraded'
  | 'entitlement_required'
  | 'configured_missing'
  | 'not_implemented'
  | string;

export type ProfessionalDataCapabilityCategory =
  | 'options_structure'
  | 'market_breadth_flows'
  | 'sector_rotation'
  | 'macro_cross_asset_regime'
  | 'stock_research_data'
  | 'backtest_data_availability'
  | string;

export type ProfessionalDataCapability = {
  capabilityId: string;
  label: string;
  category: ProfessionalDataCapabilityCategory;
  status: ProfessionalDataCapabilityStatus;
  sourceLabel: string;
  reason?: string | null;
  freshness?: string | null;
  operatorNextAction?: string | null;
  asOf?: string | null;
  updatedAt?: string | null;
  readiness?: ProfessionalDataCapabilityReadiness | null;
};

export type ProfessionalDataCapabilityReadinessMeasure = {
  measureId: string;
  label: string;
  state: string;
  supportedMarkets: string[];
  missingMarkets: string[];
};

export type ProfessionalDataCapabilityReadinessMarket = {
  market: string;
  state: string;
  supportedMeasures: string[];
  missingMeasures: string[];
};

export type ProfessionalDataCapabilityReadiness = {
  contractVersion?: string | null;
  readinessStates?: string[];
  measures?: ProfessionalDataCapabilityReadinessMeasure[];
  markets?: ProfessionalDataCapabilityReadinessMarket[];
};

export type ProfessionalDataCapabilitySummary = {
  totalCapabilities: number;
  liveCount: number;
  degradedCount: number;
  entitlementRequiredCount: number;
  configuredMissingCount: number;
  notImplementedCount: number;
};

export type ProfessionalDataCapabilityRegistryResponse = {
  contractVersion: string;
  consumerSafe: boolean;
  summary: ProfessionalDataCapabilitySummary;
  categories: ProfessionalDataCapabilityCategory[];
  capabilities: ProfessionalDataCapability[];
  crossAssetDriverReadiness?: CrossAssetDriverReadiness;
};

export type ProfessionalDataCapabilityStatusView = {
  key: string;
  label: string;
  variant: DataSourceGapRegistryStatusView['variant'];
};

export type ProfessionalDataCapabilityViewItem = {
  capabilityId: string;
  categoryKey: ProfessionalDataCapabilityCategory;
  label: string;
  status: ProfessionalDataCapabilityStatusView;
  sourceLabel: string;
  detail: string;
  freshness?: string | null;
  asOf?: string | null;
  updatedAt?: string | null;
};

export type ProfessionalDataCapabilityCategoryView = {
  categoryKey: ProfessionalDataCapabilityCategory;
  label: string;
  description: string;
  items: ProfessionalDataCapabilityViewItem[];
};

export type ProfessionalDataCapabilityRegistryView = {
  hasItems: boolean;
  contractVersion: string;
  summary: ProfessionalDataCapabilitySummary;
  statusCounts: ProfessionalDataCapabilityStatusView[];
  categories: ProfessionalDataCapabilityCategoryView[];
  crossAssetDriverReadiness?: CrossAssetDriverReadiness;
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

function normalizeCrossAssetDriverReadiness(
  readiness?: Partial<CrossAssetDriverReadiness> | null,
): CrossAssetDriverReadiness | undefined {
  if (!readiness) {
    return undefined;
  }
  return {
    contractVersion: readiness.contractVersion || 'cross_asset_driver_readiness_v1',
    consumerSafe: readiness.consumerSafe !== false,
    diagnosticOnly: readiness.diagnosticOnly !== false,
    networkCallsEnabled: readiness.networkCallsEnabled === true,
    externalProviderCalls: readiness.externalProviderCalls === true,
    mutationEnabled: readiness.mutationEnabled === true,
    supportedStates: Array.isArray(readiness.supportedStates) ? readiness.supportedStates : [],
    consumerSummary: readiness.consumerSummary || '',
    summary: readiness.summary || {},
    drivers: Array.isArray(readiness.drivers)
      ? readiness.drivers.map((driver) => ({
        category: driver.category || 'unknown',
        label: driver.label || driver.category || 'unknown',
        supported: driver.supported === true,
        state: driver.state || 'missing',
        configuredIdentifiers: Array.isArray(driver.configuredIdentifiers)
          ? driver.configuredIdentifiers.map((identifier) => ({
            kind: identifier.kind || 'unknown',
            value: identifier.value || '',
            ...(identifier.market ? { market: identifier.market } : {}),
          }))
          : [],
        cachedOhlcv: {
          requiredBars: Number(driver.cachedOhlcv?.requiredBars || 0),
          usableBars: Number(driver.cachedOhlcv?.usableBars || 0),
          missingBars: Number(driver.cachedOhlcv?.missingBars || 0),
          cacheState: driver.cachedOhlcv?.cacheState || 'missing',
          freshnessState: driver.cachedOhlcv?.freshnessState || 'unknown',
          latestBarDate: driver.cachedOhlcv?.latestBarDate || null,
        },
        missingReasons: Array.isArray(driver.missingReasons) ? driver.missingReasons.filter(Boolean) : [],
        consumerSafeSummary: driver.consumerSafeSummary || '',
      }))
      : [],
  };
}

function normalizeMarketDataReadinessPayload(rawPayload: Record<string, unknown>): MarketDataReadinessResponse {
  const payload = toCamelCase<MarketDataReadinessResponse>(rawPayload);
  const matrix = payload.consumerEvidenceReadinessMatrix;
  const crossAsset = normalizeCrossAssetDriverReadiness(payload.crossAssetDriverReadiness);
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
    ...(crossAsset ? { crossAssetDriverReadiness: crossAsset } : {}),
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
    id: 'news_catalyst',
    label: '新闻 / 催化',
    description: '个股新闻、市场新闻、财报日历和政策事件 readiness。',
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
  news_catalyst_intelligence: 'news_catalyst',
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
const PROFESSIONAL_DATA_CAPABILITY_UNSAFE_TEXT_PATTERN =
  /provider\s*class|providerClass|provider\s*name|providerName|provider\s*attempted|providerAttempted|required\s*provider\s*class|requiredProviderClass|source\s*authority\s*router|sourceAuthorityRouter|endpoint\s*host|endpointHost|api\s*key\s*present|apiKeyPresent|exception\s*class|exceptionClass|exception\s*chain|exceptionChain|request[_ -]?id|requestId|trace[_ -]?id|traceId|cache[_ -]?key|cacheKey|raw[_ -]?payload|rawPayload|credential|token|env\b/i;
const DATA_SOURCE_ACQUISITION_BLOCKER_TYPE_KEYS = [
  'entitlement',
  'provider-integration',
  'evidence-validation',
  'schema-contract',
  'frontend-consumption',
  'protected-review',
  'unknown',
] as const;
const DATA_SOURCE_ACQUISITION_PRIORITY_KEYS = ['critical', 'high', 'medium', 'low'] as const;
const DATA_SOURCE_ACQUISITION_PRIORITY_WEIGHT: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  unknown: 4,
};

function normalizeGapToken(value?: string | null): string {
  return String(value || '').trim().toLowerCase();
}

function normalizeDataSourceAcquisitionBlockerTypeKey(value?: string | null): string {
  const normalized = normalizeGapToken(value);
  return DATA_SOURCE_ACQUISITION_BLOCKER_TYPE_KEYS.includes(
    normalized as (typeof DATA_SOURCE_ACQUISITION_BLOCKER_TYPE_KEYS)[number],
  )
    ? normalized
    : 'unknown';
}

function normalizeDataSourceAcquisitionPriorityKey(value?: string | null): string {
  const normalized = normalizeGapToken(value);
  return DATA_SOURCE_ACQUISITION_PRIORITY_KEYS.includes(
    normalized as (typeof DATA_SOURCE_ACQUISITION_PRIORITY_KEYS)[number],
  )
    ? normalized
    : 'unknown';
}

function normalizeDataSourceGapActionTypeKey(value?: string | null): string {
  const normalized = normalizeGapToken(value);
  return [
    'provider-entitlement',
    'provider-integration',
    'evidence-validation',
    'schema-contract',
    'frontend-consumption',
    'manual-review',
    'blocked',
  ].includes(normalized)
    ? normalized
    : 'manual-review';
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

function dataSourceGapActionTypeView(actionType?: string | null): DataSourceGapRegistryStatusView {
  const normalized = normalizeGapToken(actionType);
  if (normalized === 'provider-entitlement') return { label: 'Provider entitlement', variant: 'danger' };
  if (normalized === 'provider-integration') return { label: 'Provider integration', variant: 'info' };
  if (normalized === 'evidence-validation') return { label: 'Evidence validation', variant: 'info' };
  if (normalized === 'schema-contract') return { label: 'Schema contract', variant: 'caution' };
  if (normalized === 'frontend-consumption') return { label: 'Frontend consumption', variant: 'info' };
  if (normalized === 'manual-review') return { label: 'Manual review', variant: 'neutral' };
  if (normalized === 'blocked') return { label: 'Blocked', variant: 'danger' };
  return { label: 'Manual review', variant: 'neutral' };
}

function dataSourceGapActionPriorityView(priority?: string | null): DataSourceGapRegistryStatusView {
  const normalized = normalizeGapToken(priority);
  if (normalized === 'critical') return { label: '关键', variant: 'danger' };
  if (normalized === 'high') return { label: '高', variant: 'caution' };
  if (normalized === 'medium') return { label: '中', variant: 'info' };
  if (normalized === 'low') return { label: '低', variant: 'neutral' };
  return { label: '中', variant: 'info' };
}

function dataSourceGapActionStatusView(status?: string | null): DataSourceGapRegistryStatusView {
  const normalized = normalizeGapToken(status);
  if (normalized === 'ready-to-start') return { label: '可开始', variant: 'info' };
  if (normalized === 'blocked') return { label: '阻断', variant: 'danger' };
  if (normalized === 'waiting-entitlement') return { label: '等待授权', variant: 'danger' };
  if (normalized === 'waiting-evidence') return { label: '等待证据', variant: 'caution' };
  if (normalized === 'planned') return { label: '计划中', variant: 'neutral' };
  if (normalized === 'not-required') return { label: '暂不需要', variant: 'neutral' };
  return { label: '计划中', variant: 'neutral' };
}

function dataSourceAcquisitionBlockerTypeView(blockerType?: string | null): DataSourceGapRegistryStatusView {
  const normalized = normalizeGapToken(blockerType);
  if (normalized === 'entitlement') return { label: '授权阻断', variant: 'danger' };
  if (normalized === 'provider-integration') return { label: '数据接入', variant: 'info' };
  if (normalized === 'evidence-validation') return { label: '证据验证', variant: 'info' };
  if (normalized === 'schema-contract') return { label: '契约补齐', variant: 'caution' };
  if (normalized === 'frontend-consumption') return { label: '前端消费', variant: 'info' };
  if (normalized === 'protected-review') return { label: '保护域复核', variant: 'caution' };
  return { label: '阻断待确认', variant: 'neutral' };
}

function dataSourceGapSafeCount(value: number | undefined): number {
  return Number.isFinite(value) && value !== undefined ? Math.max(0, Math.floor(value)) : 0;
}

function dataSourceGapSafeText(value?: string | null, fallback = '待补证'): string {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text || DATA_SOURCE_GAP_UNSAFE_TEXT_PATTERN.test(text)) return fallback;
  return text.slice(0, 140);
}

function professionalCapabilitySafeText(value?: string | null, fallback = '待补证'): string {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text || PROFESSIONAL_DATA_CAPABILITY_UNSAFE_TEXT_PATTERN.test(text)) return fallback;
  return text.slice(0, 180);
}

function dataSourceGapSafeList(values?: string[] | null, fallback = '证据待补证'): string[] {
  const safeValues = Array.isArray(values)
    ? values.flatMap((value) => {
        const safe = dataSourceGapSafeText(value, '');
        return safe ? [safe] : [];
      })
    : [];
  return safeValues.length ? safeValues.slice(0, 4) : [fallback];
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

function dataSourceGapExternalLicenseView(
  value: boolean | undefined,
): Pick<DataSourceGapRegistryActionPlanItemView, 'externalProviderLicenseWork' | 'externalProviderLicenseWorkVariant'> {
  if (value === true) {
    return { externalProviderLicenseWork: '需要外部授权', externalProviderLicenseWorkVariant: 'danger' };
  }
  if (value === false) {
    return { externalProviderLicenseWork: '不需要外部授权', externalProviderLicenseWorkVariant: 'neutral' };
  }
  return { externalProviderLicenseWork: '外部授权待确认', externalProviderLicenseWorkVariant: 'caution' };
}

function dataSourceGapProtectedReviewView(
  value: boolean | undefined,
): Pick<DataSourceGapRegistryActionPlanItemView, 'protectedDomainReview' | 'protectedDomainReviewVariant'> {
  if (value === true) {
    return { protectedDomainReview: '需要保护域复核', protectedDomainReviewVariant: 'caution' };
  }
  if (value === false) {
    return { protectedDomainReview: '无需保护域复核', protectedDomainReviewVariant: 'neutral' };
  }
  return { protectedDomainReview: '保护域复核待确认', protectedDomainReviewVariant: 'caution' };
}

function dataSourceAcquisitionEntitlementView(
  value: boolean | undefined,
): Pick<DataSourceAcquisitionPriorityQueueItemView, 'externalEntitlementRequired' | 'externalEntitlementVariant'> {
  if (value === true) {
    return { externalEntitlementRequired: '需要外部授权', externalEntitlementVariant: 'danger' };
  }
  if (value === false) {
    return { externalEntitlementRequired: '无需外部授权', externalEntitlementVariant: 'neutral' };
  }
  return { externalEntitlementRequired: '外部授权待确认', externalEntitlementVariant: 'caution' };
}

function dataSourceAcquisitionProtectedReviewView(
  value: boolean | undefined,
): Pick<DataSourceAcquisitionPriorityQueueItemView, 'protectedDomainReviewRequired' | 'protectedDomainReviewVariant'> {
  if (value === true) {
    return { protectedDomainReviewRequired: '需要保护域复核', protectedDomainReviewVariant: 'caution' };
  }
  if (value === false) {
    return { protectedDomainReviewRequired: '无需保护域复核', protectedDomainReviewVariant: 'neutral' };
  }
  return { protectedDomainReviewRequired: '保护域复核待确认', protectedDomainReviewVariant: 'caution' };
}

function dataSourceGapFallbackActionPlan(familyKey: string): DataSourceGapRegistryActionPlanItemView[] {
  return [
    {
      actionKey: `${familyKey || 'unknown_family'}.manual_review`,
      actionLabel: '行动项待复核',
      actionTypeKey: 'manual-review',
      actionType: dataSourceGapActionTypeView('manual-review'),
      priorityKey: 'medium',
      priority: dataSourceGapActionPriorityView('medium'),
      status: dataSourceGapActionStatusView('planned'),
      reason: '原因待补证。',
      requiredEvidence: ['证据待补证'],
      blockedBy: ['阻断项待补证'],
      affectedSurfacesOrCapabilities: ['影响面待补证'],
      nextConcreteStep: '下一步待补证。',
      externalProviderLicenseWork: '外部授权待确认',
      externalProviderLicenseWorkVariant: 'caution',
      protectedDomainReview: '保护域复核待确认',
      protectedDomainReviewVariant: 'caution',
    },
  ];
}

function buildDataSourceGapActionPlanView(
  familyKey: string,
  actionPlan?: DataSourceGapRegistryActionPlanItem[] | null,
): DataSourceGapRegistryActionPlanItemView[] {
  if (!Array.isArray(actionPlan) || actionPlan.length === 0) {
    return dataSourceGapFallbackActionPlan(familyKey);
  }

  const views = actionPlan.flatMap((action) => {
    const actionKey = dataSourceGapSafeText(action.actionKey, '');
    const actionLabel = dataSourceGapSafeText(action.actionLabel, '');
    const reason = dataSourceGapSafeText(action.reason, '');
    const nextConcreteStep = dataSourceGapSafeText(action.nextConcreteStep, '');
    if (!actionKey || !actionLabel || !reason || !nextConcreteStep) {
      return dataSourceGapFallbackActionPlan(familyKey);
    }
    const externalLicense = dataSourceGapExternalLicenseView(
      typeof action.requiresExternalProviderLicenseWork === 'boolean'
        ? action.requiresExternalProviderLicenseWork
        : undefined,
    );
    const protectedReview = dataSourceGapProtectedReviewView(
      typeof action.requiresProtectedDomainReview === 'boolean'
        ? action.requiresProtectedDomainReview
        : undefined,
    );
    return [{
      actionKey,
      actionLabel,
      actionTypeKey: normalizeDataSourceGapActionTypeKey(action.actionType),
      actionType: dataSourceGapActionTypeView(action.actionType),
      priorityKey: normalizeDataSourceAcquisitionPriorityKey(action.priority),
      priority: dataSourceGapActionPriorityView(action.priority),
      status: dataSourceGapActionStatusView(action.status),
      reason,
      requiredEvidence: dataSourceGapSafeList(action.requiredEvidence, '证据待补证'),
      blockedBy: dataSourceGapSafeList(action.blockedBy, '阻断项待补证'),
      affectedSurfacesOrCapabilities: dataSourceGapSafeList(
        action.affectedSurfacesOrCapabilities,
        '影响面待补证',
      ),
      nextConcreteStep,
      ...externalLicense,
      ...protectedReview,
    }];
  });

  return views.length ? views.slice(0, 4) : dataSourceGapFallbackActionPlan(familyKey);
}

function buildDataSourceAcquisitionPriorityQueueView(
  queue?: DataSourceAcquisitionPriorityQueueItem[] | null,
): DataSourceAcquisitionPriorityQueueItemView[] {
  if (!Array.isArray(queue)) return [];

  return queue.flatMap((item) => {
    const familyKey = dataSourceGapSafeText(item.familyKey, '');
    const familyLabel = dataSourceGapSafeText(item.familyLabel, '数据家族');
    if (!familyKey) return [];
    const priorityKey = normalizeDataSourceAcquisitionPriorityKey(item.priority);
    const readinessStateKey = normalizeGapToken(item.readinessState) || 'missing';
    const primaryBlockerTypeKey = normalizeDataSourceAcquisitionBlockerTypeKey(item.primaryBlockerType);
    const entitlement = dataSourceAcquisitionEntitlementView(
      typeof item.externalEntitlementRequired === 'boolean'
        ? item.externalEntitlementRequired
        : undefined,
    );
    const protectedReview = dataSourceAcquisitionProtectedReviewView(
      typeof item.protectedDomainReviewRequired === 'boolean'
        ? item.protectedDomainReviewRequired
        : undefined,
    );
    return [{
      familyKey,
      familyLabel: DATA_SOURCE_GAP_FAMILY_LABELS[familyKey] || familyLabel,
      priorityKey,
      priority: dataSourceGapActionPriorityView(item.priority),
      priorityReason: dataSourceGapSafeText(item.priorityReason, '排序原因待补证。'),
      readinessStateKey,
      readinessState: dataSourceGapStatusView(item.readinessState),
      primaryBlockerTypeKey,
      primaryBlockerType: dataSourceAcquisitionBlockerTypeView(item.primaryBlockerType),
      affectedSurfaceCount: dataSourceGapSafeCount(item.affectedSurfaceCount),
      blockedOrDegradedCapabilityCount: dataSourceGapSafeCount(item.blockedOrDegradedCapabilityCount),
      ...entitlement,
      ...protectedReview,
      nextConcreteStep: dataSourceGapSafeText(item.nextConcreteStep, '下一步待补证。'),
      requiredEvidence: dataSourceGapSafeList(item.requiredEvidence, '证据待补证'),
      consumerSafeWarning: dataSourceGapSafeText(
        item.consumerSafeWarning,
        '工程补数队列；当前不是决策级证据。',
      ),
    }];
  }).slice(0, 12);
}

function dataSourceAcquisitionWorkbenchPriorityWeight(priorityKey: string): number {
  return DATA_SOURCE_ACQUISITION_PRIORITY_WEIGHT[priorityKey] ?? DATA_SOURCE_ACQUISITION_PRIORITY_WEIGHT.unknown;
}

function dataSourceAcquisitionWorkbenchSurfaceLabels(
  family: DataSourceGapRegistryFamilyView,
  item: DataSourceAcquisitionPriorityQueueItemView,
): string[] {
  const labels = family.surfaceImpactMatrix.map((impact) => impact.surfaceLabel);
  const fallback = item.familyLabel || family.familyLabel || '待补证';
  return labels.length ? labels.slice(0, 4) : [fallback];
}

function buildDataSourceAcquisitionWorkbenchAction(
  family: DataSourceGapRegistryFamilyView,
  item: DataSourceAcquisitionPriorityQueueItemView,
): DataSourceAcquisitionWorkbenchAction {
  return {
    familyKey: item.familyKey,
    familyLabel: item.familyLabel || family.familyLabel,
    priorityKey: item.priorityKey,
    priority: item.priority,
    primaryBlockerType: item.primaryBlockerType,
    affectedSurfaceCount: item.affectedSurfaceCount > 0
      ? item.affectedSurfaceCount
      : family.surfaceImpactMatrix.length || 0,
    nextConcreteStep: item.nextConcreteStep || family.nextIntegrationStep || '下一步待补证。',
    requiredEvidence: item.requiredEvidence.length ? item.requiredEvidence : ['证据待补证'],
    affectedSurfaces: dataSourceAcquisitionWorkbenchSurfaceLabels(family, item),
  };
}

function buildDataSourceAcquisitionWorkbenchLane(
  key: DataSourceAcquisitionWorkbenchLane['key'],
  label: string,
  description: string,
  variant: DataSourceGapRegistryStatusView['variant'],
  emptyCopy: string,
  actions: DataSourceAcquisitionWorkbenchAction[],
): DataSourceAcquisitionWorkbenchLane {
  return {
    key,
    label,
    description,
    count: actions.length,
    variant,
    items: actions,
    emptyCopy,
  };
}

function buildDataSourceAcquisitionWorkbenchView(
  registry: DataSourceGapRegistryResponse | null | undefined,
  familyViews: DataSourceGapRegistryFamilyView[],
  acquisitionPriorityQueue: DataSourceAcquisitionPriorityQueueItemView[],
): DataSourceGapRegistryView['workbench'] {
  const familyViewByKey = new Map(familyViews.map((family) => [family.familyKey, family] as const));
  const queueItems = acquisitionPriorityQueue.filter((item) => item.readinessStateKey !== 'ready');
  const queueItemsByKey = new Map(queueItems.map((item) => [item.familyKey, item] as const));
  const familyBlockedCount = (registry?.summary.blockedCount || 0)
    + (registry?.summary.missingCount || 0)
    + (registry?.summary.partialCount || 0);
  const unknownFieldCount = queueItems.filter((item) => item.primaryBlockerTypeKey === 'unknown').length
    + queueItems.filter((item) => item.priorityKey === 'unknown').length;

  const normalizedActions = queueItems
    .map((item) => {
      const family = familyViewByKey.get(item.familyKey);
      if (!family) return null;
      return buildDataSourceAcquisitionWorkbenchAction(family, item);
    })
    .filter((item): item is DataSourceAcquisitionWorkbenchAction => Boolean(item))
    .sort((left, right) => (
      dataSourceAcquisitionWorkbenchPriorityWeight(left.priorityKey) - dataSourceAcquisitionWorkbenchPriorityWeight(right.priorityKey)
      || right.affectedSurfaceCount - left.affectedSurfaceCount
      || left.familyLabel.localeCompare(right.familyLabel)
    ));

  const blockerTypeCounts = DATA_SOURCE_ACQUISITION_BLOCKER_TYPE_KEYS.map((key) => {
    const count = queueItems.filter((item) => item.primaryBlockerTypeKey === key).length;
    const variant: DataSourceGapRegistryStatusView['variant'] = key === 'entitlement' || key === 'protected-review'
      ? 'danger'
      : key === 'evidence-validation' || key === 'schema-contract'
        ? 'caution'
        : key === 'provider-integration' || key === 'frontend-consumption'
          ? 'info'
          : 'neutral';
    return {
      key,
      label: dataSourceAcquisitionBlockerTypeView(key).label,
      count,
      variant,
    };
  }).filter((item) => item.count > 0 || item.key === 'unknown');

  const priorityCounts = DATA_SOURCE_ACQUISITION_PRIORITY_KEYS.map((key) => {
    const count = queueItems.filter((item) => item.priorityKey === key).length;
    const variant: DataSourceGapRegistryStatusView['variant'] = key === 'critical'
      ? 'danger'
      : key === 'high'
        ? 'caution'
        : key === 'medium'
          ? 'info'
          : 'neutral';
    return {
      key,
      label: dataSourceGapActionPriorityView(key).label,
      count,
      variant,
    };
  }).filter((item) => item.count > 0);

  const protectedReviewItems = normalizedActions.filter((action) => {
    const family = familyViewByKey.get(action.familyKey);
    const queueItem = queueItemsByKey.get(action.familyKey);
    return Boolean(
      family?.integrationActionPlan.some((entry) => (
        entry.actionLabel !== '行动项待复核'
        && entry.protectedDomainReviewVariant === 'caution'
      ))
      || queueItem?.protectedDomainReviewRequired === '需要保护域复核'
      || queueItem?.primaryBlockerTypeKey === 'protected-review'
      || action.primaryBlockerType.label === '保护域复核',
    );
  });
  const externalEntitlementItems = normalizedActions.filter((action) => {
    const queueItem = queueItemsByKey.get(action.familyKey);
    return Boolean(queueItem?.externalEntitlementRequired === '需要外部授权' || action.primaryBlockerType.label === '授权阻断');
  });
  const evidenceValidationItems = normalizedActions.filter((action) => {
    const family = familyViewByKey.get(action.familyKey);
    const queueItem = queueItemsByKey.get(action.familyKey);
    return Boolean(
      family?.integrationActionPlan.some((entry) => entry.actionTypeKey === 'evidence-validation')
      || queueItem?.primaryBlockerTypeKey === 'evidence-validation'
      || action.primaryBlockerType.label === '证据验证',
    );
  });

  const topNextActions = normalizedActions.slice(0, 3);

  return {
    blockedMissingPartialFamilyCount: familyBlockedCount,
    urgentQueueCount: queueItems.length,
    unknownFieldCount,
    consumerSafeWarning: queueItems[0]?.consumerSafeWarning
      || '工程补数队列；当前不是决策级证据，不生成交易指令。',
    blockerTypeCounts,
    priorityCounts,
    topNextActions,
    lanes: [
      buildDataSourceAcquisitionWorkbenchLane(
        'protected-review',
        '保护域复核',
        '保留期权链、Gamma、dealer positioning 和其他受保护数据面在复核之后再推进。',
        'caution',
        '暂无需要保护域复核的队列项。',
        protectedReviewItems,
      ),
      buildDataSourceAcquisitionWorkbenchLane(
        'external-entitlement',
        '外部授权',
        '显示需要 provider entitlement / licensing work 的队列项，只做工程补数。',
        'danger',
        '暂无需要外部授权的队列项。',
        externalEntitlementItems,
      ),
      buildDataSourceAcquisitionWorkbenchLane(
        'evidence-validation',
        '证据验证',
        '显示需要字段覆盖、时效、授权和可复核证据的队列项。',
        'info',
        '暂无需要证据验证的队列项。',
        evidenceValidationItems,
      ),
    ],
  };
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
      capabilityMap: Array.isArray(family.capabilityMap)
        ? family.capabilityMap.map((item) => ({
          capabilityKey: item.capabilityKey || '',
          consumerLabel: item.consumerLabel || '',
          state: item.state || 'missing',
          freshnessState: item.freshnessState || 'unknown',
          scope: item.scope || 'unknown',
          evidenceState: item.evidenceState || 'unknown',
          missingReason: item.missingReason || '',
          operatorNextAction: item.operatorNextAction || '',
        }))
        : [],
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
      integrationActionPlan: Array.isArray(family.integrationActionPlan)
        ? family.integrationActionPlan.map((action) => ({
          actionKey: action.actionKey || '',
          actionLabel: action.actionLabel || '',
          actionType: action.actionType || 'manual-review',
          priority: action.priority || 'medium',
          status: action.status || 'planned',
          reason: action.reason || '',
          requiredEvidence: Array.isArray(action.requiredEvidence) ? action.requiredEvidence : [],
          blockedBy: Array.isArray(action.blockedBy) ? action.blockedBy : [],
          affectedSurfacesOrCapabilities: Array.isArray(action.affectedSurfacesOrCapabilities)
            ? action.affectedSurfacesOrCapabilities
            : [],
          nextConcreteStep: action.nextConcreteStep || '',
          requiresExternalProviderLicenseWork: typeof action.requiresExternalProviderLicenseWork === 'boolean'
            ? action.requiresExternalProviderLicenseWork
            : undefined,
          requiresProtectedDomainReview: typeof action.requiresProtectedDomainReview === 'boolean'
            ? action.requiresProtectedDomainReview
            : undefined,
        }))
        : [],
    })) : [],
    acquisitionPriorityQueue: Array.isArray(payload.acquisitionPriorityQueue)
      ? payload.acquisitionPriorityQueue.map((item) => ({
        familyKey: item.familyKey || '',
        familyLabel: item.familyLabel || '',
        priority: item.priority || 'medium',
        priorityReason: item.priorityReason || '',
        readinessState: item.readinessState || 'missing',
        primaryBlockerType: item.primaryBlockerType || 'unknown',
        affectedSurfaceCount: Number.isFinite(item.affectedSurfaceCount)
          ? Number(item.affectedSurfaceCount)
          : undefined,
        blockedOrDegradedCapabilityCount: Number.isFinite(item.blockedOrDegradedCapabilityCount)
          ? Number(item.blockedOrDegradedCapabilityCount)
          : undefined,
        externalEntitlementRequired: typeof item.externalEntitlementRequired === 'boolean'
          ? item.externalEntitlementRequired
          : undefined,
        protectedDomainReviewRequired: typeof item.protectedDomainReviewRequired === 'boolean'
          ? item.protectedDomainReviewRequired
          : undefined,
        nextConcreteStep: item.nextConcreteStep || '',
        requiredEvidence: Array.isArray(item.requiredEvidence) ? item.requiredEvidence : [],
        consumerSafeWarning: item.consumerSafeWarning || '',
      }))
      : [],
    metadata: payload.metadata || {},
  };
}

const DEFAULT_PROFESSIONAL_DATA_CAPABILITY_SUMMARY: ProfessionalDataCapabilitySummary = {
  totalCapabilities: 0,
  liveCount: 0,
  degradedCount: 0,
  entitlementRequiredCount: 0,
  configuredMissingCount: 0,
  notImplementedCount: 0,
};

const PROFESSIONAL_DATA_CAPABILITY_CATEGORY_META: Record<string, { label: string; description: string }> = {
  options_structure: {
    label: '期权结构',
    description: '期权链、Greeks、Gamma 与 0DTE 等结构输入。',
  },
  market_breadth_flows: {
    label: '广度 / 资金流',
    description: '市场参与度、资金流和 positioning 观察。',
  },
  sector_rotation: {
    label: '板块 / 市场状态',
    description: 'ETF、指数、板块轮动和市场 regime 证据。',
  },
  macro_cross_asset_regime: {
    label: '宏观 / 跨资产',
    description: '利率、波动率、流动性和信用压力输入。',
  },
  stock_research_data: {
    label: '个股研究',
    description: '基本面、技术面、新闻和催化剂覆盖。',
  },
  backtest_data_availability: {
    label: '回测数据',
    description: '数据集血缘、调整基准、日历和 PIT 证据。',
  },
};

function normalizeProfessionalDataCapabilityStatus(status?: string | null): ProfessionalDataCapabilityStatus {
  const normalized = normalizeGapToken(status);
  if ([
    'live',
    'degraded',
    'entitlement_required',
    'configured_missing',
    'not_implemented',
  ].includes(normalized)) {
    return normalized;
  }
  return 'unavailable';
}

function professionalDataCapabilityStatusView(status?: string | null): ProfessionalDataCapabilityStatusView {
  const normalized = normalizeProfessionalDataCapabilityStatus(status);
  if (normalized === 'live') return { key: normalized, label: '可用', variant: 'success' };
  if (normalized === 'degraded') return { key: normalized, label: '降级', variant: 'caution' };
  if (normalized === 'entitlement_required') return { key: normalized, label: '需授权', variant: 'danger' };
  if (normalized === 'configured_missing') return { key: normalized, label: '配置待补', variant: 'caution' };
  if (normalized === 'not_implemented') return { key: normalized, label: '未实现', variant: 'neutral' };
  return { key: 'unavailable', label: '暂不可用', variant: 'danger' };
}

function professionalCapabilityReadinessStateLabel(state?: string | null): string {
  const normalized = normalizeGapToken(state);
  if (normalized === 'available') return '可用';
  if (normalized === 'stale') return '待更新';
  if (normalized === 'disabled_by_flag') return '已停用';
  return '待补';
}

function normalizeProfessionalCapabilityReadiness(
  readiness?: Partial<ProfessionalDataCapabilityReadiness> | null,
): ProfessionalDataCapabilityReadiness | null {
  if (!readiness || typeof readiness !== 'object') {
    return null;
  }
  const measures = Array.isArray(readiness.measures)
    ? readiness.measures.flatMap((measure) => {
      const measureId = professionalCapabilitySafeText(measure.measureId, '');
      const label = professionalCapabilitySafeText(measure.label, '');
      if (!measureId || !label) return [];
      return [{
        measureId,
        label,
        state: normalizeGapToken(measure.state),
        supportedMarkets: Array.isArray(measure.supportedMarkets)
          ? measure.supportedMarkets.flatMap((market) => {
            const value = professionalCapabilitySafeText(market, '');
            return value ? [value] : [];
          })
          : [],
        missingMarkets: Array.isArray(measure.missingMarkets)
          ? measure.missingMarkets.flatMap((market) => {
            const value = professionalCapabilitySafeText(market, '');
            return value ? [value] : [];
          })
          : [],
      }];
    })
    : [];
  const markets = Array.isArray(readiness.markets)
    ? readiness.markets.flatMap((market) => {
      const marketKey = professionalCapabilitySafeText(market.market, '');
      if (!marketKey) return [];
      return [{
        market: marketKey,
        state: normalizeGapToken(market.state),
        supportedMeasures: Array.isArray(market.supportedMeasures)
          ? market.supportedMeasures.flatMap((measure) => {
            const value = professionalCapabilitySafeText(measure, '');
            return value ? [value] : [];
          })
          : [],
        missingMeasures: Array.isArray(market.missingMeasures)
          ? market.missingMeasures.flatMap((measure) => {
            const value = professionalCapabilitySafeText(measure, '');
            return value ? [value] : [];
          })
          : [],
      }];
    })
    : [];
  return {
    contractVersion: professionalCapabilitySafeText(readiness.contractVersion, ''),
    readinessStates: Array.isArray(readiness.readinessStates)
      ? readiness.readinessStates.flatMap((state) => {
        const value = professionalCapabilitySafeText(state, '');
        return value ? [value] : [];
      })
      : [],
    measures,
    markets,
  };
}

function professionalCapabilityReadinessSummary(
  readiness?: ProfessionalDataCapabilityReadiness | null,
): string[] {
  if (!readiness) {
    return [];
  }
  const measureSummaries = (readiness.measures || []).slice(0, 2).map((measure) => {
    const supported = measure.supportedMarkets.join('/') || '无';
    const missing = measure.missingMarkets.join('/') || '无';
    return `${measure.label}: ${supported} 可用；${missing} 待补`;
  });
  const marketSummaries = (readiness.markets || []).slice(0, 2).map((market) => {
    const supported = market.supportedMeasures.join('/') || '无';
    const missing = market.missingMeasures.join('/') || '无';
    return `${market.market}: ${supported} ${professionalCapabilityReadinessStateLabel('available')}；${missing} 待补`;
  });
  return [...measureSummaries, ...marketSummaries].filter(Boolean);
}

function normalizeProfessionalDataCapabilityRegistryPayload(
  rawPayload: Record<string, unknown>,
): ProfessionalDataCapabilityRegistryResponse {
  const payload = toCamelCase<ProfessionalDataCapabilityRegistryResponse>(rawPayload);
  const rawSummary = payload.summary || DEFAULT_PROFESSIONAL_DATA_CAPABILITY_SUMMARY;
  const capabilities = Array.isArray(payload.capabilities)
    ? payload.capabilities.flatMap((capability) => {
      const capabilityId = professionalCapabilitySafeText(capability.capabilityId, '');
      const label = professionalCapabilitySafeText(capability.label, '');
      const category = professionalCapabilitySafeText(capability.category, '');
      if (!capabilityId || !label || !category) {
        return [];
      }
      return [{
        capabilityId,
        label,
        category,
        status: normalizeProfessionalDataCapabilityStatus(capability.status),
        sourceLabel: professionalCapabilitySafeText(capability.sourceLabel, '来源待补证'),
        reason: professionalCapabilitySafeText(capability.reason, ''),
        freshness: professionalCapabilitySafeText(capability.freshness, ''),
        operatorNextAction: professionalCapabilitySafeText(capability.operatorNextAction, ''),
        asOf: professionalCapabilitySafeText(capability.asOf, ''),
        updatedAt: professionalCapabilitySafeText(capability.updatedAt, ''),
        readiness: normalizeProfessionalCapabilityReadiness(capability.readiness),
      }];
    })
    : [];
  const categories = Array.isArray(payload.categories)
    ? payload.categories.flatMap((category) => {
      const safeCategory = professionalCapabilitySafeText(category, '');
      return safeCategory ? [safeCategory] : [];
    })
    : [];

  return {
    contractVersion: professionalCapabilitySafeText(
      payload.contractVersion,
      'professional_data_capability_registry_unknown',
    ),
    consumerSafe: payload.consumerSafe !== false,
    summary: {
      ...DEFAULT_PROFESSIONAL_DATA_CAPABILITY_SUMMARY,
      ...rawSummary,
      totalCapabilities: dataSourceGapSafeCount(rawSummary.totalCapabilities),
      liveCount: dataSourceGapSafeCount(rawSummary.liveCount),
      degradedCount: dataSourceGapSafeCount(rawSummary.degradedCount),
      entitlementRequiredCount: dataSourceGapSafeCount(rawSummary.entitlementRequiredCount),
      configuredMissingCount: dataSourceGapSafeCount(rawSummary.configuredMissingCount),
      notImplementedCount: dataSourceGapSafeCount(rawSummary.notImplementedCount),
    },
    categories,
    capabilities,
    crossAssetDriverReadiness: normalizeCrossAssetDriverReadiness(payload.crossAssetDriverReadiness),
  };
}

export function buildDataSourceGapRegistryView(
  registry?: DataSourceGapRegistryResponse | null,
): DataSourceGapRegistryView {
  const summary = registry?.summary || DEFAULT_DATA_SOURCE_GAP_REGISTRY_SUMMARY;
  const families = Array.isArray(registry?.families) ? registry.families : [];
  const acquisitionPriorityQueue = buildDataSourceAcquisitionPriorityQueueView(
    registry?.acquisitionPriorityQueue,
  );
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
    const integrationActionPlan = buildDataSourceGapActionPlanView(
      familyKey,
      family.integrationActionPlan,
    );
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
      capabilityMap: (family.capabilityMap || []).map((item) => ({
        capabilityKey: dataSourceGapSafeText(item.capabilityKey, 'unknown_capability'),
        consumerLabel: dataSourceGapSafeText(item.consumerLabel, '能力待补证'),
        state: normalizeGapToken(item.state) || 'missing',
        freshnessState: normalizeGapToken(item.freshnessState) || 'unknown',
        scope: dataSourceGapSafeText(item.scope, 'unknown'),
        evidenceState: dataSourceGapSafeText(item.evidenceState, 'unknown'),
        missingReason: dataSourceGapSafeText(item.missingReason, '缺失原因待补证。'),
        operatorNextAction: dataSourceGapSafeText(item.operatorNextAction, '下一步待补证。'),
      })),
      surfaceImpactMatrix,
      integrationActionPlan,
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
    workbench: buildDataSourceAcquisitionWorkbenchView(
      registry,
      familyViews,
      acquisitionPriorityQueue,
    ),
    acquisitionPriorityQueue,
    families: familyViews,
    groups,
  };
}

export function buildProfessionalDataCapabilityRegistryView(
  registry?: ProfessionalDataCapabilityRegistryResponse | null,
): ProfessionalDataCapabilityRegistryView {
  const summary = registry?.summary || DEFAULT_PROFESSIONAL_DATA_CAPABILITY_SUMMARY;
  const capabilities = Array.isArray(registry?.capabilities) ? registry.capabilities : [];
  const orderedCategories = [
    'options_structure',
    'market_breadth_flows',
    'sector_rotation',
    'macro_cross_asset_regime',
    'stock_research_data',
    'backtest_data_availability',
    ...(registry?.categories || []),
  ].filter((category, index, all) => category && all.indexOf(category) === index);
  const categoryViews = orderedCategories.map((categoryKey) => {
    const meta = PROFESSIONAL_DATA_CAPABILITY_CATEGORY_META[categoryKey] || {
      label: '其他专业数据',
      description: '后端已返回、前端尚未归类的数据能力。',
    };
    return {
      categoryKey,
      label: meta.label,
      description: meta.description,
      items: capabilities
        .filter((capability) => capability.category === categoryKey)
        .map((capability) => ({
          capabilityId: capability.capabilityId,
          categoryKey,
          label: capability.label,
          status: professionalDataCapabilityStatusView(capability.status),
          sourceLabel: professionalCapabilitySafeText(capability.sourceLabel, '来源待补证'),
          detail: [
            professionalCapabilitySafeText(capability.reason, ''),
            professionalCapabilitySafeText(capability.freshness, ''),
            ...professionalCapabilityReadinessSummary(capability.readiness),
          ].filter(Boolean).join(' · ') || '覆盖原因待补证。',
          freshness: professionalCapabilitySafeText(capability.freshness, ''),
          operatorNextAction: professionalCapabilitySafeText(capability.operatorNextAction, ''),
          asOf: professionalCapabilitySafeText(capability.asOf, ''),
          updatedAt: professionalCapabilitySafeText(capability.updatedAt, ''),
        })),
    };
  }).filter((category) => category.items.length > 0);

  return {
    hasItems: capabilities.length > 0,
    contractVersion: registry?.contractVersion || 'professional_data_capability_registry_unknown',
    summary,
    statusCounts: [
      { ...professionalDataCapabilityStatusView('live'), label: `可用 ${summary.liveCount}` },
      { ...professionalDataCapabilityStatusView('degraded'), label: `降级 ${summary.degradedCount}` },
      { ...professionalDataCapabilityStatusView('entitlement_required'), label: `需授权 ${summary.entitlementRequiredCount}` },
      { ...professionalDataCapabilityStatusView('configured_missing'), label: `配置待补 ${summary.configuredMissingCount}` },
      { ...professionalDataCapabilityStatusView('not_implemented'), label: `未实现 ${summary.notImplementedCount}` },
    ],
    categories: categoryViews,
    crossAssetDriverReadiness: registry?.crossAssetDriverReadiness,
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

function crossAssetDriverStateVariant(state?: CrossAssetDriverReadinessState): CrossAssetDriverReadinessChip['variant'] {
  if (state === 'available') return 'success';
  if (state === 'stale' || state === 'insufficient_history') return 'caution';
  if (state === 'missing') return 'neutral';
  if (state === 'not_configured') return 'neutral';
  return 'neutral';
}

function crossAssetDriverStateLabel(state?: CrossAssetDriverReadinessState): string {
  if (state === 'available') return '可用';
  if (state === 'stale') return '待更新';
  if (state === 'insufficient_history') return '历史不足';
  if (state === 'not_configured') return '未配置';
  return '待补';
}

function crossAssetDriverLabel(item: CrossAssetDriverReadinessItem): string {
  const identifierText = item.configuredIdentifiers
    .map((identifier) => identifier.value)
    .filter(Boolean)
    .slice(0, 3)
    .join('/');
  return `${item.label}: ${crossAssetDriverStateLabel(item.state)}${identifierText ? ` (${identifierText})` : ''}`;
}

export function buildCrossAssetDriverReadinessView(
  readiness?: CrossAssetDriverReadiness | null,
): CrossAssetDriverReadinessView {
  const drivers = Array.isArray(readiness?.drivers) ? readiness.drivers : [];
  if (!drivers.length) {
    return {
      label: '跨资产驱动待补',
      variant: 'neutral',
      chips: [],
      note: '仅展示已配置的驱动输入；未返回的数据不做推断。',
    };
  }
  const availableCount = drivers.filter((driver) => driver.state === 'available').length;
  const staleCount = drivers.filter((driver) => driver.state === 'stale').length;
  const insufficientCount = drivers.filter((driver) => driver.state === 'insufficient_history').length;
  const missingCount = drivers.filter((driver) => driver.state === 'missing' || driver.state === 'not_configured').length;
  const variant: CrossAssetDriverReadinessView['variant'] = availableCount === drivers.length
    ? 'success'
    : availableCount > 0
      ? 'info'
      : staleCount || insufficientCount
        ? 'caution'
        : 'neutral';
  const label = availableCount === drivers.length
    ? '跨资产驱动可用'
    : availableCount > 0
      ? '跨资产驱动部分可用'
      : '跨资产驱动待补';
  return {
    label,
    variant,
    chips: drivers.slice(0, 9).map((driver) => ({
      key: driver.category,
      label: crossAssetDriverLabel(driver),
      variant: crossAssetDriverStateVariant(driver.state),
    })),
    note: `可用 ${availableCount} · 待更新 ${staleCount} · 历史不足 ${insufficientCount} · 待补/未配置 ${missingCount}`,
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
  return items.find((item) => normalizeConsumerEvidenceToken(item.surface) === 'market_overview');
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
        : item.readinessState === 'score_grade'
          && item.scoreGradeInputs.some((input) => item.fulfilledInputs.includes(input))
          ? { label: '风险状态可用', variant: 'success' as const }
          : { label: '风险状态待补', variant: 'caution' as const };

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

export type MarketRegimeReadinessLabel = 'product_ready' | 'degraded' | 'blocked' | 'failed_closed' | string;

export type MarketRegimeReadModelMetric = {
  label: string;
  value: unknown;
};

export type MarketRegimeReadModelEvidenceCard = {
  id: string;
  title: string;
  status: string;
  severity: string;
  headline: string;
  metrics: MarketRegimeReadModelMetric[];
  reasons: string[];
  sourceFields?: string[];
  consumerSafe?: boolean;
};

export type MarketRegimeReadModelResponse = {
  consumerSafe: boolean;
  noAdvice: boolean;
  contractVersion: string;
  sourceEvidenceContractVersion: string;
  status: string;
  market: string;
  symbols: string[];
  benchmarkSymbol: string;
  growthProxySymbol: string;
  regime: {
    label: string;
    status: string;
    source?: string;
  };
  productSummary: string;
  evidenceCards: MarketRegimeReadModelEvidenceCard[];
  symbolContext: Array<Record<string, unknown>>;
  dataQuality: {
    adjustedCoverageState?: string;
    ohlcvCoverage?: {
      state?: string;
      requiredBars?: number | null;
      availableSymbols?: string[];
      missingSymbols?: string[];
      missingBars?: Record<string, unknown>;
    };
    quoteSnapshotCoverage?: {
      state?: string;
      availabilityState?: string;
      freshnessState?: string;
      availableSymbols?: string[];
      missingSymbols?: string[];
      staleSymbols?: string[];
    };
    missingDataFamilies?: string[];
    blockedProductSurfaces?: string[];
    nextOperatorAction?: string;
    failClosedReasons?: string[];
  };
  readiness: {
    label: MarketRegimeReadinessLabel;
    status: string;
    missingDataFamilies: string[];
    blockedProductSurfaces: string[];
    nextOperatorAction: string;
  };
  surfaceHints: Array<Record<string, unknown>>;
  missingDataFamilies: string[];
  blockedProductSurfaces: string[];
  nextOperatorAction: string;
  networkCallsEnabled: boolean;
  mutationEnabled: boolean;
  providerCallsEnabled: boolean;
};

function hasMarketAuxiliaryAuthority(value: Record<string, unknown>): boolean {
  if (!hasMarketContractText(value.source) || !isMarketDataFreshnessValue(value.freshness)) {
    return false;
  }
  const explicitlyUnavailable = value.source === 'unavailable'
    || value.source === 'error'
    || value.freshness === 'unavailable'
    || value.freshness === 'error';
  return explicitlyUnavailable
    || (value.freshness !== 'unknown' && (hasMarketContractText(value.updatedAt) || hasMarketContractText(value.asOf)));
}

export function isMarketBriefingContract(value: unknown): value is MarketBriefingResponse {
  if (!isMarketContractRecord(value) || !hasMarketAuxiliaryAuthority(value) || !Array.isArray(value.items)) {
    return false;
  }
  return value.items.every((item) => isMarketContractRecord(item)
    && hasMarketContractText(item.title)
    && hasMarketContractText(item.message)
    && ['positive', 'neutral', 'warning', 'risk'].includes(String(item.severity || ''))
    && hasMarketContractText(item.category)
    && (item.confidence === undefined || (typeof item.confidence === 'number' && Number.isFinite(item.confidence))));
}

export function isMarketFuturesContract(value: unknown): value is MarketFuturesResponse {
  if (!isMarketContractRecord(value) || !hasMarketAuxiliaryAuthority(value) || !Array.isArray(value.items)) {
    return false;
  }
  return value.items.every((item) => {
    if (!isMarketContractRecord(item)) {
      return false;
    }
    return hasMarketContractText(item.name)
      && hasMarketContractText(item.symbol)
      && hasMarketContractText(item.market)
      && hasMarketContractText(item.session)
      && hasMarketContractText(item.source)
      && isFiniteMarketContractNumberOrNull(item.value)
      && isFiniteMarketContractNumberOrNull(item.change)
      && isFiniteMarketContractNumberOrNull(item.changePercent)
      && Array.isArray(item.sparkline)
      && item.sparkline.every((point) => typeof point === 'number' && Number.isFinite(point))
      && (item.freshness === undefined || isMarketDataFreshnessValue(item.freshness));
  });
}

const CN_SHORT_SENTIMENT_METRIC_KEYS = [
  'limitUpCount',
  'limitDownCount',
  'failedLimitUpRate',
  'maxConsecutiveLimitUps',
  'yesterdayLimitUpPerformance',
  'firstBoardCount',
  'secondBoardCount',
  'highBoardCount',
  'twentyCmLimitUpCount',
] as const;

export function isCnShortSentimentContract(value: unknown): value is CnShortSentimentResponse {
  if (
    !isMarketContractRecord(value)
    || !hasMarketAuxiliaryAuthority(value)
    || typeof value.sentimentScore !== 'number'
    || !Number.isFinite(value.sentimentScore)
    || !hasMarketContractText(value.summary)
    || !isMarketContractRecord(value.metrics)
  ) {
    return false;
  }
  const metrics = value.metrics;
  return CN_SHORT_SENTIMENT_METRIC_KEYS.every((key) => (
    typeof metrics[key] === 'number' && Number.isFinite(metrics[key])
  ));
}

const MARKET_TEMPERATURE_SCORE_KEYS = [
  'overall',
  'usRiskAppetite',
  'cnMoneyEffect',
  'macroPressure',
  'liquidity',
] as const;

export function isMarketTemperatureContract(value: unknown): value is MarketTemperatureResponse {
  if (!isMarketContractRecord(value) || !hasMarketAuxiliaryAuthority(value) || !isMarketContractRecord(value.scores)) {
    return false;
  }
  const scores = value.scores;
  return MARKET_TEMPERATURE_SCORE_KEYS.every((key) => {
    const score = scores[key];
    return isMarketContractRecord(score)
      && isFiniteMarketContractNumberOrNull(score.value)
      && hasMarketContractText(score.label);
  });
}

function normalizeRegimeMetricValue(value: unknown): unknown {
  if (isMarketContractRecord(value)) {
    return null;
  }
  if (Array.isArray(value) && value.some(isMarketContractRecord)) {
    return null;
  }
  if (typeof value === 'number' && !Number.isFinite(value)) {
    return null;
  }
  return value;
}

function normalizeMarketRegimeEvidenceCards(value: unknown): MarketRegimeReadModelEvidenceCard[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((card) => {
    if (!isMarketContractRecord(card)) {
      return [];
    }
    const metrics = Array.isArray(card.metrics)
      ? card.metrics.flatMap((metric) => (
        isMarketContractRecord(metric) && hasMarketContractText(metric.label)
          ? [{ label: metric.label, value: normalizeRegimeMetricValue(metric.value) }]
          : []
      ))
      : [];
    return [{
      id: hasMarketContractText(card.id) ? card.id : '',
      title: hasMarketContractText(card.title) ? card.title : '',
      status: hasMarketContractText(card.status) ? card.status : 'unavailable',
      severity: hasMarketContractText(card.severity) ? card.severity : 'warning',
      headline: hasMarketContractText(card.headline) ? card.headline : '',
      metrics,
      reasons: isMarketContractStringArray(card.reasons) ? card.reasons : [],
      ...(isMarketContractStringArray(card.sourceFields) ? { sourceFields: card.sourceFields } : {}),
      ...(typeof card.consumerSafe === 'boolean' ? { consumerSafe: card.consumerSafe } : {}),
    }];
  });
}

function isCompleteProductReadyReadModel(value: MarketRegimeReadModelResponse): boolean {
  if (
    !Array.isArray(value.symbols)
    || !Array.isArray(value.evidenceCards)
    || !Array.isArray(value.symbolContext)
    || !Array.isArray(value.surfaceHints)
    || !Array.isArray(value.missingDataFamilies)
    || !Array.isArray(value.blockedProductSurfaces)
    || !isMarketContractRecord(value.regime)
    || !isMarketContractRecord(value.dataQuality)
    || !isMarketContractRecord(value.dataQuality.ohlcvCoverage)
    || !isMarketContractRecord(value.dataQuality.quoteSnapshotCoverage)
    || !isMarketContractRecord(value.readiness)
    || !Array.isArray(value.readiness.missingDataFamilies)
    || !Array.isArray(value.readiness.blockedProductSurfaces)
  ) {
    return false;
  }
  const dataQuality = value.dataQuality;
  const ohlcvCoverage = dataQuality.ohlcvCoverage!;
  const quoteSnapshotCoverage = dataQuality.quoteSnapshotCoverage!;
  return value.consumerSafe === true
    && value.noAdvice === true
    && hasMarketContractText(value.contractVersion)
    && hasMarketContractText(value.sourceEvidenceContractVersion)
    && value.status === 'ok'
    && hasMarketContractText(value.market)
    && value.symbols.length > 0
    && value.symbols.every(hasMarketContractText)
    && hasMarketContractText(value.benchmarkSymbol)
    && hasMarketContractText(value.growthProxySymbol)
    && hasMarketContractText(value.regime?.label)
    && value.regime?.status === 'ok'
    && hasMarketContractText(value.productSummary)
    && value.evidenceCards.length > 0
    && value.evidenceCards.every((card) => isMarketContractRecord(card)
      && hasMarketContractText(card.id)
      && hasMarketContractText(card.title)
      && hasMarketContractText(card.status)
      && hasMarketContractText(card.severity)
      && hasMarketContractText(card.headline)
      && card.consumerSafe === true
      && Array.isArray(card.metrics)
      && card.metrics.length > 0
      && card.metrics.every((metric) => isMarketContractRecord(metric)
        && hasMarketContractText(metric.label)
        && metric.value !== undefined
        && metric.value !== null
        && !isMarketContractRecord(metric.value))
      && Array.isArray(card.reasons)
      && card.reasons.length > 0
      && isMarketContractStringArray(card.sourceFields)
      && card.sourceFields.length > 0)
    && dataQuality.adjustedCoverageState === 'available'
    && ohlcvCoverage.state === 'available'
    && typeof ohlcvCoverage.requiredBars === 'number'
    && Number.isFinite(ohlcvCoverage.requiredBars)
    && ohlcvCoverage.requiredBars > 0
    && isMarketContractStringArray(ohlcvCoverage.availableSymbols)
    && isMarketContractStringArray(ohlcvCoverage.missingSymbols)
    && ohlcvCoverage.missingSymbols.length === 0
    && quoteSnapshotCoverage.state === 'available'
    && quoteSnapshotCoverage.availabilityState === 'available'
    && hasMarketContractText(quoteSnapshotCoverage.freshnessState)
    && isMarketContractStringArray(quoteSnapshotCoverage.availableSymbols)
    && isMarketContractStringArray(quoteSnapshotCoverage.missingSymbols)
    && quoteSnapshotCoverage.missingSymbols.length === 0
    && isMarketContractStringArray(quoteSnapshotCoverage.staleSymbols)
    && quoteSnapshotCoverage.staleSymbols.length === 0
    && isMarketContractStringArray(dataQuality.missingDataFamilies)
    && dataQuality.missingDataFamilies.length === 0
    && isMarketContractStringArray(dataQuality.blockedProductSurfaces)
    && dataQuality.blockedProductSurfaces.length === 0
    && isMarketContractStringArray(dataQuality.failClosedReasons)
    && dataQuality.failClosedReasons.length === 0
    && value.readiness.label === 'product_ready'
    && value.readiness.status === 'ok'
    && value.readiness.missingDataFamilies.length === 0
    && value.readiness.blockedProductSurfaces.length === 0
    && hasMarketContractText(value.readiness.nextOperatorAction)
    && value.missingDataFamilies.length === 0
    && value.blockedProductSurfaces.length === 0
    && hasMarketContractText(value.nextOperatorAction)
    && typeof value.networkCallsEnabled === 'boolean'
    && typeof value.mutationEnabled === 'boolean'
    && typeof value.providerCallsEnabled === 'boolean';
}

export function isMarketRegimeReadModelContract(value: unknown): value is MarketRegimeReadModelResponse {
  if (!isMarketContractRecord(value) || !isMarketContractRecord(value.readiness)) {
    return false;
  }
  const payload = value as unknown as MarketRegimeReadModelResponse;
  if (payload.status === 'ok' || payload.readiness.label === 'product_ready') {
    return isCompleteProductReadyReadModel(payload);
  }
  return hasMarketContractText(payload.status)
    && hasMarketContractText(payload.readiness.label)
    && hasMarketContractText(payload.readiness.status)
    && Array.isArray(payload.evidenceCards)
    && Array.isArray(payload.missingDataFamilies)
    && Array.isArray(payload.blockedProductSurfaces)
    && Array.isArray(payload.readiness.missingDataFamilies)
    && Array.isArray(payload.readiness.blockedProductSurfaces);
}

function failedClosedMarketRegimeReadModel(
  payload: MarketRegimeReadModelResponse,
): MarketRegimeReadModelResponse {
  return {
    ...payload,
    status: 'failed_closed',
    regime: {
      ...payload.regime,
      label: payload.regime?.label || 'insufficient_data',
      status: 'failed_closed',
    },
    readiness: {
      ...payload.readiness,
      label: 'failed_closed',
      status: 'failed_closed',
    },
  };
}

function normalizeMarketRegimeReadModelPayload(payload: unknown): MarketRegimeReadModelResponse {
  const normalized = isMarketContractRecord(payload)
    ? toCamelCase<Partial<MarketRegimeReadModelResponse>>(payload)
    : {};
  const readiness: Record<string, unknown> = isMarketContractRecord(normalized.readiness) ? normalized.readiness : {};
  const dataQuality: Record<string, unknown> = isMarketContractRecord(normalized.dataQuality) ? normalized.dataQuality : {};
  const ohlcvCoverage: Record<string, unknown> = isMarketContractRecord(dataQuality.ohlcvCoverage) ? dataQuality.ohlcvCoverage : {};
  const quoteSnapshotCoverage: Record<string, unknown> = isMarketContractRecord(dataQuality.quoteSnapshotCoverage) ? dataQuality.quoteSnapshotCoverage : {};
  const regime: Record<string, unknown> = isMarketContractRecord(normalized.regime) ? normalized.regime : {};
  const candidate: MarketRegimeReadModelResponse = {
    consumerSafe: normalized.consumerSafe === true,
    noAdvice: normalized.noAdvice === true,
    contractVersion: hasMarketContractText(normalized.contractVersion) ? normalized.contractVersion : '',
    sourceEvidenceContractVersion: hasMarketContractText(normalized.sourceEvidenceContractVersion) ? normalized.sourceEvidenceContractVersion : '',
    status: hasMarketContractText(normalized.status) ? normalized.status : 'failed_closed',
    market: hasMarketContractText(normalized.market) ? normalized.market : '',
    symbols: isMarketContractStringArray(normalized.symbols) ? normalized.symbols : [],
    benchmarkSymbol: hasMarketContractText(normalized.benchmarkSymbol) ? normalized.benchmarkSymbol : '',
    growthProxySymbol: hasMarketContractText(normalized.growthProxySymbol) ? normalized.growthProxySymbol : '',
    regime: {
      label: hasMarketContractText(regime.label) ? regime.label : 'insufficient_data',
      status: hasMarketContractText(regime.status) ? regime.status : 'failed_closed',
      ...(hasMarketContractText(regime.source) ? { source: regime.source } : {}),
    },
    productSummary: hasMarketContractText(normalized.productSummary) ? normalized.productSummary : '',
    evidenceCards: normalizeMarketRegimeEvidenceCards(normalized.evidenceCards),
    symbolContext: Array.isArray(normalized.symbolContext) ? normalized.symbolContext.filter(isMarketContractRecord) : [],
    dataQuality: {
      adjustedCoverageState: hasMarketContractText(dataQuality.adjustedCoverageState) ? dataQuality.adjustedCoverageState : undefined,
      ohlcvCoverage: {
        state: hasMarketContractText(ohlcvCoverage.state) ? ohlcvCoverage.state : undefined,
        requiredBars: typeof ohlcvCoverage.requiredBars === 'number' && Number.isFinite(ohlcvCoverage.requiredBars) ? ohlcvCoverage.requiredBars : null,
        availableSymbols: isMarketContractStringArray(ohlcvCoverage.availableSymbols) ? ohlcvCoverage.availableSymbols : [],
        missingSymbols: isMarketContractStringArray(ohlcvCoverage.missingSymbols) ? ohlcvCoverage.missingSymbols : [],
        missingBars: isMarketContractRecord(ohlcvCoverage.missingBars) ? ohlcvCoverage.missingBars : {},
      },
      quoteSnapshotCoverage: {
        state: hasMarketContractText(quoteSnapshotCoverage.state) ? quoteSnapshotCoverage.state : undefined,
        availabilityState: hasMarketContractText(quoteSnapshotCoverage.availabilityState) ? quoteSnapshotCoverage.availabilityState : undefined,
        freshnessState: hasMarketContractText(quoteSnapshotCoverage.freshnessState) ? quoteSnapshotCoverage.freshnessState : undefined,
        availableSymbols: isMarketContractStringArray(quoteSnapshotCoverage.availableSymbols) ? quoteSnapshotCoverage.availableSymbols : [],
        missingSymbols: isMarketContractStringArray(quoteSnapshotCoverage.missingSymbols) ? quoteSnapshotCoverage.missingSymbols : [],
        staleSymbols: isMarketContractStringArray(quoteSnapshotCoverage.staleSymbols) ? quoteSnapshotCoverage.staleSymbols : [],
      },
      missingDataFamilies: isMarketContractStringArray(dataQuality.missingDataFamilies) ? dataQuality.missingDataFamilies : [],
      blockedProductSurfaces: isMarketContractStringArray(dataQuality.blockedProductSurfaces) ? dataQuality.blockedProductSurfaces : [],
      nextOperatorAction: hasMarketContractText(dataQuality.nextOperatorAction) ? dataQuality.nextOperatorAction : '',
      failClosedReasons: isMarketContractStringArray(dataQuality.failClosedReasons) ? dataQuality.failClosedReasons : [],
    },
    readiness: {
      label: hasMarketContractText(readiness.label) ? readiness.label : 'failed_closed',
      status: hasMarketContractText(readiness.status) ? readiness.status : 'failed_closed',
      missingDataFamilies: isMarketContractStringArray(readiness.missingDataFamilies) ? readiness.missingDataFamilies : [],
      blockedProductSurfaces: isMarketContractStringArray(readiness.blockedProductSurfaces) ? readiness.blockedProductSurfaces : [],
      nextOperatorAction: hasMarketContractText(readiness.nextOperatorAction)
        ? readiness.nextOperatorAction
        : hasMarketContractText(normalized.nextOperatorAction) ? normalized.nextOperatorAction : '',
    },
    surfaceHints: Array.isArray(normalized.surfaceHints) ? normalized.surfaceHints.filter(isMarketContractRecord) : [],
    missingDataFamilies: isMarketContractStringArray(normalized.missingDataFamilies) ? normalized.missingDataFamilies : [],
    blockedProductSurfaces: isMarketContractStringArray(normalized.blockedProductSurfaces) ? normalized.blockedProductSurfaces : [],
    nextOperatorAction: hasMarketContractText(normalized.nextOperatorAction) ? normalized.nextOperatorAction : '',
    networkCallsEnabled: normalized.networkCallsEnabled === true,
    mutationEnabled: normalized.mutationEnabled === true,
    providerCallsEnabled: normalized.providerCallsEnabled === true,
  };
  const optimistic = candidate.status === 'ok'
    || candidate.readiness.label === 'product_ready'
    || candidate.readiness.status === 'ok';
  const runtimeFlagsDeclared = typeof normalized.networkCallsEnabled === 'boolean'
    && typeof normalized.mutationEnabled === 'boolean'
    && typeof normalized.providerCallsEnabled === 'boolean';
  return optimistic && !(runtimeFlagsDeclared && isCompleteProductReadyReadModel(candidate))
    ? failedClosedMarketRegimeReadModel(candidate)
    : candidate;
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
    const normalized = toCamelCase<MarketBriefingResponse>(response.data);
    if (!isMarketBriefingContract(normalized)) {
      throw new Error('invalid_market_briefing_contract');
    }
    return normalized;
  },
  getFutures: async (): Promise<MarketFuturesResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(buildMarketApiPath('futures'));
    const normalized = toCamelCase<MarketFuturesResponse>(response.data);
    if (!isMarketFuturesContract(normalized)) {
      throw new Error('invalid_market_futures_contract');
    }
    return normalized;
  },
  getCnShortSentiment: async (): Promise<CnShortSentimentResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(buildMarketApiPath('cn-short-sentiment'));
    const normalized = toCamelCase<CnShortSentimentResponse>(response.data);
    if (!isCnShortSentimentContract(normalized)) {
      throw new Error('invalid_cn_short_sentiment_contract');
    }
    return normalized;
  },
  getRegimeReadModel: async (): Promise<MarketRegimeReadModelResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(buildMarketApiPath('regime-read-model'));
    return normalizeMarketRegimeReadModelPayload(response.data);
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
  getProfessionalDataCapabilities: async (): Promise<ProfessionalDataCapabilityRegistryResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(buildMarketApiPath('professional-data-capabilities'));
    return normalizeProfessionalDataCapabilityRegistryPayload(response.data);
  },
  getProfessionalDataCapabilitiesAdmin: async (): Promise<ProfessionalDataCapabilityRegistryResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(buildMarketApiPath('professional-data-capabilities/admin'));
    return normalizeProfessionalDataCapabilityRegistryPayload(response.data);
  },
};

export type MarketTemperatureTrend = 'improving' | 'stable' | 'cooling' | 'rising' | 'falling';

export type MarketTemperatureScore = {
  /** Missing score is unknown evidence, not mid-scale 50. Observed 0 remains 0. */
  value: number | null;
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
  /** Missing confidence is unknown, not observed zero. */
  value?: number | null;
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
    /** Missing confidence is unknown, not observed zero. */
    value?: number | null;
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
  // Missing temperature score must not materialize mid-scale 50 as evidence.
  value: null,
  label: '数据不足',
  trend: 'stable',
  description: '数据待补',
};

function normalizeMarketTemperatureScore(score?: Partial<MarketTemperatureScore> | null): MarketTemperatureScore {
  const rawValue = score?.value;
  const value = typeof rawValue === 'number' && Number.isFinite(rawValue) ? rawValue : null;
  return {
    value,
    label: score?.label || DEFAULT_MARKET_TEMPERATURE_SCORE.label,
    trend: score?.trend || DEFAULT_MARKET_TEMPERATURE_SCORE.trend,
    description: score?.description || DEFAULT_MARKET_TEMPERATURE_SCORE.description,
  };
}

/**
 * Fail-closed reliability gate for market temperature evidence.
 * Null/missing confidence or input counts are not threshold passes.
 */
export function isMarketTemperatureReliable(data: Pick<
  MarketTemperatureResponse,
  | 'temperatureAvailable'
  | 'conclusionAllowed'
  | 'isReliable'
  | 'confidence'
  | 'reliableInputCount'
  | 'requiredReliableInputCount'
>): boolean {
  if (
    data.temperatureAvailable === false
    || data.conclusionAllowed === false
    || data.isReliable === false
  ) {
    return false;
  }

  if (typeof data.confidence !== 'number' || !Number.isFinite(data.confidence) || data.confidence < 0.45) {
    return false;
  }

  const requiredReliableInputCount = data.requiredReliableInputCount ?? 3;
  if (
    typeof data.reliableInputCount !== 'number'
    || !Number.isFinite(data.reliableInputCount)
    || data.reliableInputCount < requiredReliableInputCount
  ) {
    return false;
  }

  return true;
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
    // Preserve missing confidence as unknown; do not invent observed zero.
    value: typeof confidence?.value === 'number' && Number.isFinite(confidence.value)
      ? confidence.value
      : undefined,
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
      // Missing confidence is unknown, not observed zero.
      value: typeof summary.confidence?.value === 'number' && Number.isFinite(summary.confidence.value)
        ? summary.confidence.value
        : undefined,
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
  // Fail closed: missing confidence or sample coverage is not sufficient reliability evidence.
  const requiredReliableInputCount = payload?.requiredReliableInputCount ?? 3;
  const inferredReliable = typeof payload?.confidence === 'number'
    && Number.isFinite(payload.confidence)
    && payload.confidence >= 0.45
    && typeof payload?.reliableInputCount === 'number'
    && Number.isFinite(payload.reliableInputCount)
    && payload.reliableInputCount >= requiredReliableInputCount;
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
    // Backend as-of/update only; never substitute client render time as evidence observation time.
    updatedAt: resolveSnapshotEvidenceTimestamp(payload?.updatedAt) || '',
    asOf: resolveSnapshotEvidenceTimestamp(payload?.asOf),
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
