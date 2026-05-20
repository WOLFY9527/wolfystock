import apiClient from './index';
import type { MarketDataMeta, MarketOverviewPanel, MarketOverviewItem, MarketProviderHealth } from './marketOverview';
import { toCamelCase } from './utils';
import { API_BASE_URL } from '../utils/constants';
import { buildAbsoluteApiUrl, joinApiPath } from './path';

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
  isRefreshing?: boolean;
  isFromSnapshot?: boolean;
  lastSuccessfulAt?: string;
  refreshError?: string | null;
  lastError?: string | null;
  delayMinutes?: number;
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
  isRefreshing?: boolean;
  isFromSnapshot?: boolean;
  lastSuccessfulAt?: string;
  refreshError?: string | null;
  lastError?: string | null;
  delayMinutes?: number;
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
    isRefreshing: item.isRefreshing,
    isFromSnapshot: item.isFromSnapshot,
    lastSuccessfulAt: item.lastSuccessfulAt,
    refreshError: item.refreshError,
    lastError: item.lastError,
    delayMinutes: item.delayMinutes,
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
    isRefreshing: payload.isRefreshing,
    isFromSnapshot: payload.isFromSnapshot,
    lastSuccessfulAt: payload.lastSuccessfulAt,
    refreshError: payload.refreshError,
    lastError: payload.lastError,
    delayMinutes: payload.delayMinutes,
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
  secretConfigured?: boolean;
  details?: Record<string, unknown>;
};

export type MarketDataReadinessResponse = {
  readinessStatus: MarketDataReadinessStatus;
  diagnosticOnly: boolean;
  providerRuntimeCalled: boolean;
  networkCallsEnabled: boolean;
  representativeSymbols: string[];
  checks: MarketDataReadinessCheck[];
};

function normalizeReadinessSymbols(symbols?: string[] | string | null): string | undefined {
  if (Array.isArray(symbols)) {
    const sanitized = symbols.map((symbol) => String(symbol || '').trim()).filter(Boolean);
    return sanitized.length ? sanitized.join(',') : undefined;
  }
  if (typeof symbols !== 'string') {
    return undefined;
  }
  const sanitized = symbols
    .split(',')
    .map((symbol) => symbol.trim())
    .filter(Boolean)
    .join(',');
  return sanitized || undefined;
}

function normalizeMarketDataReadinessPayload(rawPayload: Record<string, unknown>): MarketDataReadinessResponse {
  const payload = toCamelCase<MarketDataReadinessResponse>(rawPayload);
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
      ...(typeof check.secretConfigured === 'boolean' ? { secretConfigured: check.secretConfigured } : {}),
      ...(check.details && typeof check.details === 'object' ? { details: check.details } : {}),
    })) : [],
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

export type MarketRegimeSynthesis = {
  primaryRegime: string;
  secondaryRegimes: string[];
  regimeScores: Record<string, number>;
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
  marketRegimeSynthesis?: MarketRegimeSynthesis;
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
  description: '当前真实数据不足，市场温度仅供界面演示。',
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
  if (!item?.key || !item?.label) {
    return null;
  }
  return {
    key: item.key,
    label: item.label,
    pillar: item.pillar,
    direction: item.direction,
    signal: item.signal,
    weight: item.weight,
    impact: item.impact,
    expectedDirection: item.expectedDirection,
    reason: item.reason,
    source: item.source,
    sourceTier: item.sourceTier,
    trustLevel: item.trustLevel,
    freshness: item.freshness,
    observationOnly: item.observationOnly,
    scoreContributionAllowed: item.scoreContributionAllowed,
    discountReasons: Array.isArray(item.discountReasons) ? item.discountReasons.filter(Boolean) : [],
    degradationReason: item.degradationReason,
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
    primaryRegime: synthesis.primaryRegime,
    secondaryRegimes: Array.isArray(synthesis.secondaryRegimes) ? synthesis.secondaryRegimes.filter(Boolean) : [],
    regimeScores: synthesis.regimeScores || {},
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
    sourceLabel: payload?.sourceLabel,
    providerHealth: payload?.providerHealth,
    updatedAt: payload?.updatedAt || new Date().toISOString(),
    asOf: payload?.asOf,
    freshness: payload?.freshness,
    isFallback: payload?.isFallback,
    isStale: payload?.isStale,
    isRefreshing: payload?.isRefreshing,
    delayMinutes: payload?.delayMinutes,
    warning: payload?.warning,
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
    marketRegimeSynthesis: normalizeMarketRegimeSynthesis(payload?.marketRegimeSynthesis),
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
