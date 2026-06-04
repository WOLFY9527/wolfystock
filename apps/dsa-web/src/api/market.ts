import apiClient from './index';
import type { MarketDataMeta, MarketOverviewPanel, MarketOverviewItem, MarketProviderHealth } from './marketOverview';
import { toCamelCase } from './utils';
import { API_BASE_URL } from '../utils/constants';
import { buildAbsoluteApiUrl, joinApiPath } from './path';
import { normalizeMarketIntelligenceEvidenceItem } from './marketIntelligenceEvidence';
import type { ResearchReadinessV1 } from '../types/researchReadiness';

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
  return normalizeMarketIntelligenceEvidenceItem<MarketRegimeSynthesisEvidenceItem>(item, { requireLabel: true });
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
