import apiClient from './index';
import { normalizeMarketIntelligenceEvidenceItem } from './marketIntelligenceEvidence';
import { toCamelCase } from './utils';
import type { InvestorSignalAssetPressure, InvestorSignalContract } from '../types/scanner';
import { projectMarketTruth } from '../utils/consumerDataQualityViewModel';

export type LiquidityMonitorFreshness = 'live' | 'cached' | 'delayed' | 'partial' | 'stale' | 'fallback' | 'mock' | 'error' | 'unavailable';
export type LiquidityEvidenceFreshness = LiquidityMonitorFreshness | 'fresh' | 'synthetic' | 'unknown';
export type LiquidityMonitorRegime = 'abundant' | 'supportive' | 'neutral' | 'tight' | 'stress' | 'unavailable';
export type LiquidityMonitorIndicatorStatus = 'live' | 'partial' | 'unavailable';
export type OfficialRiskBundleStatus = 'available' | 'partial' | 'missing' | 'stale' | 'blocked' | string;
export type LiquidityConsumerDataQualityState = 'ready' | 'delayed' | 'cached' | 'partial' | 'no_evidence' | 'unavailable' | string;

export interface LiquidityMonitorScore {
  value: number;
  regime: LiquidityMonitorRegime;
  /** Measured confidence in [0,1]. Null/undefined means unavailable, not observed zero. */
  confidence: number | null;
  includedIndicatorCount: number;
  possibleIndicatorWeight: number;
  includedIndicatorWeight: number;
}

export interface LiquidityConsumerDataQuality {
  state: LiquidityConsumerDataQualityState;
  label: string;
  available: boolean;
}

export interface LiquidityMonitorFreshnessSummary {
  status: LiquidityMonitorFreshness;
  weakestIndicatorFreshness: LiquidityMonitorFreshness;
  latestAsOf?: string | null;
}

export interface LiquidityMonitorIndicator {
  key: string;
  label: string;
  status: LiquidityMonitorIndicatorStatus;
  freshness: LiquidityMonitorFreshness;
  includedInScore: boolean;
  scoreContribution: number;
  scoreWeight: number;
  summary?: string | null;
  updatedAt?: string | null;
  evidence?: LiquidityMonitorEvidenceSnapshot | null;
  coverageDiagnostics?: LiquidityMonitorCoverageDiagnostics | null;
}

export interface LiquidityMonitorSourceMetadata {
  externalProviderCalls: boolean;
  providerRuntimeChanged: boolean;
  marketCacheMutation: boolean;
}

export interface LiquidityMonitorEvidenceInput {
  key: string;
  label: string;
  source: string;
  sourceLabel?: string | null;
  sourceType?: string | null;
  sourceTier?: string | null;
  trustLevel?: string | null;
  asOf?: string | null;
  freshness: LiquidityEvidenceFreshness;
  isFallback?: boolean;
  isStale?: boolean;
  isPartial?: boolean;
  isUnavailable?: boolean;
  observationOnly?: boolean;
  sourceAuthorityAllowed?: boolean;
  scoreContributionAllowed?: boolean;
  sourceAuthorityReason?: string | null;
  sourceAuthorityRouteRejected?: boolean;
  routeRejectedReasonCodes?: string[];
  officialSeriesId?: string | null;
  officialObservationDate?: string | null;
  officialAsOf?: string | null;
  coverage?: number | null;
  confidenceWeight?: number | null;
  degradationReason?: string | null;
  capReason?: string | null;
}

export interface LiquidityMonitorEvidenceSnapshot {
  contractVersion: string;
  source: string;
  sourceLabel?: string | null;
  asOf?: string | null;
  freshness: LiquidityEvidenceFreshness;
  isFallback?: boolean;
  isStale?: boolean;
  isPartial?: boolean;
  isUnavailable?: boolean;
  coverage?: number | null;
  confidenceWeight?: number | null;
  degradationReason?: string | null;
  capReason?: string | null;
  inputs: LiquidityMonitorEvidenceInput[];
}

export interface LiquidityMonitorCoverageDiagnostics {
  indicatorId: string;
  indicatorName: string;
  requiredInputs: string[];
  fulfilledInputs: string[];
  missingInputs: string[];
  requiredInputCount?: number;
  fulfilledInputCount?: number;
  missingInputCount?: number;
  scoreEligibleInputCount?: number;
  observationOnlyInputCount?: number;
  requiredProviderClass?: string | null;
  configuredProviderAvailable?: boolean;
  realSourceAvailable?: boolean;
  proxyOnly?: boolean;
  observationOnly?: boolean;
  scoreContributionAllowed?: boolean;
  scoreExclusionReason?: string | null;
  requiredRealSourceForScore?: boolean;
  proxyObservationOnlyReason?: string | null;
  missingProviderReason?: string | null;
  paidDataLikelyRequired?: boolean;
  sourceTier?: string | null;
  freshness?: string | null;
  trustLevel?: string | null;
  contributesToScore?: boolean;
  scoreContribution?: number | null;
  capReason?: string | null;
  degradationReason?: string | null;
  sourceAuthorityRouteRejected?: boolean;
  sourceAuthorityReason?: string | null;
  routeRejectedReasonCodes?: string[];
  activationHint?: string | null;
}

export interface LiquidityMonitorCoverageFamily {
  indicatorId: string;
  label: string;
  requiredInputs: string[];
  fulfilledInputs: string[];
  missingInputs: string[];
  requiredInputCount: number;
  fulfilledInputCount: number;
  missingInputCount: number;
  scoreEligibleInputCount: number;
  observationOnlyInputCount: number;
  contributesToScore: boolean;
  scoreContributionAllowed: boolean;
  observationOnly: boolean;
  proxyOnly: boolean;
}

export interface LiquidityMonitorCoverageContract {
  contractVersion: string;
  label: string;
  summary: string;
  denominatorKind: 'required_inputs';
  denominatorLabel: string;
  requiredFamilyCount: number;
  requiredInputCount: number;
  fulfilledInputCount: number;
  missingInputCount: number;
  scoreEligibleInputCount: number;
  observationOnlyInputCount: number;
  scoreWeightBudget: number;
  scoreWeightIncluded: number;
  families: LiquidityMonitorCoverageFamily[];
}

export interface OfficialRiskBundleFamilyReadiness {
  familyId: string;
  label: string;
  required: boolean;
  status: OfficialRiskBundleStatus;
  sourceType?: string;
  sourceAuthorityAllowed?: boolean;
  scoreAuthorityEligible?: boolean;
  observationOnly?: boolean;
  freshness: LiquidityEvidenceFreshness;
  asOf?: string | null;
  freshnessWindow: string;
  requiredSeries: string[];
  fulfilledSeries: string[];
  missingSeries: string[];
  staleSeries: string[];
  blockedSeries: string[];
  nextEvidenceRequired: string[];
}

export interface OfficialRiskBundleReadiness {
  contractVersion?: string;
  status: OfficialRiskBundleStatus;
  scoreAuthority: 'eligible' | 'observation_only' | string;
  scoreAuthorityEligible?: boolean;
  observationOnly?: boolean;
  sourceAuthorityState?: OfficialRiskBundleStatus;
  asOf?: string | null;
  freshness: LiquidityEvidenceFreshness;
  requiredFamilies: string[];
  availableFamilies: string[];
  partialFamilies: string[];
  missingRequiredFamilies: string[];
  staleFamilies: string[];
  blockedFamilies: string[];
  requiredSeries: string[];
  missingRequiredSeries: string[];
  nextEvidenceRequired: string[];
  families: OfficialRiskBundleFamilyReadiness[];
}

export interface OfficialRiskBundleReadinessChip {
  key: string;
  label: string;
  variant: 'success' | 'info' | 'caution' | 'neutral';
}

export interface OfficialRiskBundleReadinessView {
  bundleLabel: string;
  bundleVariant: 'success' | 'info' | 'caution' | 'neutral';
  chips: OfficialRiskBundleReadinessChip[];
  summary: string;
}

export interface LiquidityImpulseSynthesisEvidenceItem {
  key: string;
  label?: string | null;
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
  includedInScore?: boolean;
  proxyOnly?: boolean;
  discountReasons?: string[];
  degradationReason?: string | null;
}

export interface LiquidityImpulseSynthesis {
  liquidityImpulse: string;
  impulseLabel: string;
  subtype: string;
  /** Measured confidence in [0,1]. Null means unavailable, not observed zero. */
  confidence: number | null;
  confidenceLabel: string;
  pillarScores: Record<string, number>;
  directionScore: number;
  dominantDrivers: LiquidityImpulseSynthesisEvidenceItem[];
  counterEvidence: LiquidityImpulseSynthesisEvidenceItem[];
  dataGaps: LiquidityImpulseSynthesisEvidenceItem[];
  narrativeBullets: string[];
  evidenceQuality: Record<string, unknown>;
  notInvestmentAdvice: boolean;
}

export interface LiquidityCapitalFlowSignal extends InvestorSignalContract {
  sourceAssetPressure?: InvestorSignalAssetPressure[];
}

export interface LiquidityMonitorResponse {
  endpoint: string;
  generatedAt: string;
  score: LiquidityMonitorScore;
  coverageContract?: LiquidityMonitorCoverageContract;
  freshness: LiquidityMonitorFreshnessSummary;
  dataQuality?: LiquidityConsumerDataQuality;
  indicators: LiquidityMonitorIndicator[];
  officialRiskBundleReadiness?: OfficialRiskBundleReadiness;
  liquidityImpulseSynthesis?: LiquidityImpulseSynthesis;
  capitalFlowSignal?: LiquidityCapitalFlowSignal;
  advisoryDisclosure: string;
  sourceMetadata: LiquidityMonitorSourceMetadata;
}

function normalizeInvestorSignalAssetPressure(
  item?: InvestorSignalAssetPressure | null,
): InvestorSignalAssetPressure | null {
  if (!item || typeof item !== 'object') {
    return null;
  }
  return {
    asset: item.asset || null,
    pressure: item.pressure || null,
    freshness: item.freshness,
    isFallback: item.isFallback === true,
    isStale: item.isStale === true,
    isPartial: item.isPartial === true,
  };
}

function normalizeCapitalFlowSignal(
  signal?: LiquidityCapitalFlowSignal | null,
): LiquidityCapitalFlowSignal | undefined {
  if (!signal || typeof signal !== 'object') {
    return undefined;
  }
  return {
    ...signal,
    reasonCodes: Array.isArray(signal.reasonCodes) ? signal.reasonCodes.filter(Boolean) : [],
    contradictionCodes: Array.isArray(signal.contradictionCodes) ? signal.contradictionCodes.filter(Boolean) : [],
    sourceAssetPressure: Array.isArray(signal.sourceAssetPressure)
      ? signal.sourceAssetPressure
        .map((item) => normalizeInvestorSignalAssetPressure(item))
        .filter((item): item is InvestorSignalAssetPressure => Boolean(item))
      : [],
    contradictionSignals: Array.isArray(signal.contradictionSignals) ? signal.contradictionSignals.filter(Boolean) : [],
  };
}

function normalizeLiquidityImpulseEvidenceItem(
  item?: Partial<LiquidityImpulseSynthesisEvidenceItem> | null,
): LiquidityImpulseSynthesisEvidenceItem | null {
  const normalized = normalizeMarketIntelligenceEvidenceItem<LiquidityImpulseSynthesisEvidenceItem>(item, {
    additionalFields: (evidenceItem) => ({
      includedInScore: evidenceItem.includedInScore,
      proxyOnly: evidenceItem.proxyOnly,
    }),
  });
  if (!normalized) return null;
  const truth = projectMarketTruth(normalized);
  return {
    ...normalized,
    observationOnly: truth.observationOnly ?? normalized.observationOnly,
    proxyOnly: truth.source.class === 'proxy' ? true : normalized.proxyOnly,
  };
}

function normalizeLiquidityImpulseSynthesis(
  synthesis?: Partial<LiquidityImpulseSynthesis> | null,
): LiquidityImpulseSynthesis | undefined {
  if (!synthesis?.liquidityImpulse || !synthesis.impulseLabel || !synthesis.subtype || !synthesis.confidenceLabel) {
    return undefined;
  }

  const normalizeEvidenceList = (
    items?: Array<Partial<LiquidityImpulseSynthesisEvidenceItem> | null>,
  ): LiquidityImpulseSynthesisEvidenceItem[] => (
    Array.isArray(items)
      ? items
        .map((item) => normalizeLiquidityImpulseEvidenceItem(item))
        .filter((item): item is LiquidityImpulseSynthesisEvidenceItem => Boolean(item))
      : []
  );

  return {
    liquidityImpulse: synthesis.liquidityImpulse,
    impulseLabel: synthesis.impulseLabel,
    subtype: synthesis.subtype,
    confidence: typeof synthesis.confidence === 'number' && Number.isFinite(synthesis.confidence)
      ? synthesis.confidence
      : null,
    confidenceLabel: synthesis.confidenceLabel,
    pillarScores: synthesis.pillarScores || {},
    directionScore: typeof synthesis.directionScore === 'number' ? synthesis.directionScore : 0,
    dominantDrivers: normalizeEvidenceList(synthesis.dominantDrivers),
    counterEvidence: normalizeEvidenceList(synthesis.counterEvidence),
    dataGaps: normalizeEvidenceList(synthesis.dataGaps),
    narrativeBullets: Array.isArray(synthesis.narrativeBullets) ? synthesis.narrativeBullets.filter(Boolean) : [],
    evidenceQuality: synthesis.evidenceQuality || {},
    notInvestmentAdvice: synthesis.notInvestmentAdvice !== false,
  };
}

function normalizeOfficialRiskBundleFamily(
  family?: Partial<OfficialRiskBundleFamilyReadiness> | null,
): OfficialRiskBundleFamilyReadiness | null {
  if (!family || typeof family !== 'object' || !family.familyId) {
    return null;
  }

  return {
    familyId: String(family.familyId),
    label: family.label || String(family.familyId),
    required: family.required === true,
    status: family.status || 'missing',
    sourceType: family.sourceType || 'unknown',
    ...(typeof family.sourceAuthorityAllowed === 'boolean'
      ? { sourceAuthorityAllowed: family.sourceAuthorityAllowed } : {}),
    ...(typeof family.scoreAuthorityEligible === 'boolean'
      ? { scoreAuthorityEligible: family.scoreAuthorityEligible } : {}),
    ...(typeof family.observationOnly === 'boolean'
      ? { observationOnly: family.observationOnly } : {}),
    freshness: family.freshness || 'unknown',
    asOf: family.asOf,
    freshnessWindow: family.freshnessWindow || '',
    requiredSeries: Array.isArray(family.requiredSeries) ? family.requiredSeries.filter(Boolean) : [],
    fulfilledSeries: Array.isArray(family.fulfilledSeries) ? family.fulfilledSeries.filter(Boolean) : [],
    missingSeries: Array.isArray(family.missingSeries) ? family.missingSeries.filter(Boolean) : [],
    staleSeries: Array.isArray(family.staleSeries) ? family.staleSeries.filter(Boolean) : [],
    blockedSeries: Array.isArray(family.blockedSeries) ? family.blockedSeries.filter(Boolean) : [],
    nextEvidenceRequired: Array.isArray(family.nextEvidenceRequired) ? family.nextEvidenceRequired.filter(Boolean) : [],
  };
}

function normalizeOfficialRiskBundleReadiness(
  readiness?: Partial<OfficialRiskBundleReadiness> | null,
): OfficialRiskBundleReadiness | undefined {
  if (!readiness || typeof readiness !== 'object' || !readiness.status) {
    return undefined;
  }

  return {
    contractVersion: readiness.contractVersion,
    status: readiness.status || 'missing',
    scoreAuthority: readiness.scoreAuthority || 'unknown',
    ...(typeof readiness.scoreAuthorityEligible === 'boolean'
      ? { scoreAuthorityEligible: readiness.scoreAuthorityEligible } : {}),
    ...(typeof readiness.observationOnly === 'boolean'
      ? { observationOnly: readiness.observationOnly } : {}),
    sourceAuthorityState: readiness.sourceAuthorityState,
    asOf: readiness.asOf,
    freshness: readiness.freshness || 'unknown',
    requiredFamilies: Array.isArray(readiness.requiredFamilies) ? readiness.requiredFamilies.filter(Boolean) : [],
    availableFamilies: Array.isArray(readiness.availableFamilies) ? readiness.availableFamilies.filter(Boolean) : [],
    partialFamilies: Array.isArray(readiness.partialFamilies) ? readiness.partialFamilies.filter(Boolean) : [],
    missingRequiredFamilies: Array.isArray(readiness.missingRequiredFamilies) ? readiness.missingRequiredFamilies.filter(Boolean) : [],
    staleFamilies: Array.isArray(readiness.staleFamilies) ? readiness.staleFamilies.filter(Boolean) : [],
    blockedFamilies: Array.isArray(readiness.blockedFamilies) ? readiness.blockedFamilies.filter(Boolean) : [],
    requiredSeries: Array.isArray(readiness.requiredSeries) ? readiness.requiredSeries.filter(Boolean) : [],
    missingRequiredSeries: Array.isArray(readiness.missingRequiredSeries) ? readiness.missingRequiredSeries.filter(Boolean) : [],
    nextEvidenceRequired: Array.isArray(readiness.nextEvidenceRequired) ? readiness.nextEvidenceRequired.filter(Boolean) : [],
    families: Array.isArray(readiness.families)
      ? readiness.families
        .map((family) => normalizeOfficialRiskBundleFamily(family))
        .filter((family): family is OfficialRiskBundleFamilyReadiness => Boolean(family))
      : [],
  };
}

function normalizeLiquidityMonitor(payload: Record<string, unknown>): LiquidityMonitorResponse {
  const normalized = toCamelCase<LiquidityMonitorResponse>(payload);
  return {
    endpoint: normalized.endpoint,
    generatedAt: normalized.generatedAt,
    score: normalized.score,
    coverageContract: normalized.coverageContract,
    freshness: normalized.freshness,
    dataQuality: normalized.dataQuality,
    indicators: Array.isArray(normalized.indicators) ? normalized.indicators : [],
    officialRiskBundleReadiness: normalizeOfficialRiskBundleReadiness(normalized.officialRiskBundleReadiness),
    liquidityImpulseSynthesis: normalizeLiquidityImpulseSynthesis(normalized.liquidityImpulseSynthesis),
    capitalFlowSignal: normalizeCapitalFlowSignal(normalized.capitalFlowSignal),
    advisoryDisclosure: normalized.advisoryDisclosure,
    sourceMetadata: normalized.sourceMetadata,
  };
}

export const liquidityMonitorApi = {
  async getLiquidityMonitor(): Promise<LiquidityMonitorResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/market/liquidity-monitor');
    return normalizeLiquidityMonitor(response.data);
  },
};

const OFFICIAL_RISK_FAMILY_LABELS: Record<string, string> = {
  vix: 'VIX',
  rates: '利率',
  fedLiquidity: 'Fed流动性',
  creditStress: '信用压力',
};

export function buildOfficialRiskBundleReadinessView(
  readiness?: OfficialRiskBundleReadiness | null,
): OfficialRiskBundleReadinessView {
  if (!readiness) {
    return {
      bundleLabel: '官方风险包待补证',
      bundleVariant: 'neutral',
      chips: [],
      summary: '官方风险包未返回，当前不从其他流动性线索推断。',
    };
  }

  const truth = projectMarketTruth(readiness);
  const bundleLabel: OfficialRiskBundleReadinessView['bundleLabel'] = truth.availability === 'available'
    && truth.scoreContribution === 'eligible'
    ? '官方风险包可用'
    : truth.freshness === 'stale'
      ? '官方风险包待更新'
      : truth.availability === 'partial' ? '官方风险包部分待补' : '官方风险包待补证';
  const bundleVariant: OfficialRiskBundleReadinessView['bundleVariant'] = bundleLabel === '官方风险包可用'
    ? 'success'
    : bundleLabel === '官方风险包部分待补' ? 'info' : bundleLabel === '官方风险包待更新' ? 'caution' : 'neutral';
  const blockedCount = readiness.blockedFamilies.length;
  const staleCount = readiness.staleFamilies.length;
  const missingSeriesCount = readiness.missingRequiredSeries.length;
  const pieces = [
    missingSeriesCount > 0 ? `待补序列 ${missingSeriesCount} 项` : '',
    staleCount > 0 ? `待更新 ${staleCount} 项` : '',
    blockedCount > 0 ? `权限待确认 ${blockedCount} 项` : '',
    truth.freshness === 'cached' ? '当前为缓存快照' : '',
    truth.scoreContribution !== 'eligible' ? '仅观察，不升级结论' : '',
  ].filter(Boolean);
  const summary = truth.scoreContribution === 'eligible'
    ? 'VIX、利率与 Fed 流动性已满足官方来源、时效与完整性边界。'
    : pieces.length ? pieces.join('；') : '官方风险包待补证，当前仅显示已返回的安全状态。';

  return {
    bundleLabel,
    bundleVariant,
    chips: readiness.families.map((family) => {
      const familyTruth = projectMarketTruth(family);
      const blocked = familyTruth.availability === 'blocked';
      const label = familyTruth.availability === 'available' && !family.required
        ? '仅观察'
        : familyTruth.availability === 'available' && familyTruth.scoreContribution === 'eligible'
          ? '可用'
          : familyTruth.freshness === 'stale'
            ? '待更新'
            : blocked ? '权限待确认' : familyTruth.availability === 'partial' ? '部分待补' : '待补证';
      const variant: OfficialRiskBundleReadinessChip['variant'] = label === '可用'
        ? 'success'
        : label === '仅观察' || label === '部分待补' ? 'info' : label === '待更新' || label === '权限待确认' ? 'caution' : 'neutral';
      return {
        key: family.familyId,
        label: `${OFFICIAL_RISK_FAMILY_LABELS[family.familyId] || '风险线索'}${label}`,
        variant,
      };
    }),
    summary,
  };
}
