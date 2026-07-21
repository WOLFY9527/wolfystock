import apiClient from './index';
import { toCamelCase } from './utils';
import type { OptionsResearchReadiness } from '../types/researchReadiness';
import { projectMarketTruth } from '../utils/consumerDataQualityViewModel';

export type OptionsDirection = 'bullish' | 'bearish' | 'neutral' | 'volatility';
export type OptionsRiskProfile = 'conservative' | 'balanced' | 'aggressive';
export type OptionsFreshness = 'live' | 'delayed' | 'cached' | 'stale' | 'mock' | 'error' | string;
export type OptionSide = 'call' | 'put';
export type OptionMoneyness = 'itm' | 'atm' | 'otm';
export type OptionsStrategyType = 'long_call' | 'long_put' | 'bull_call_spread' | 'bear_put_spread';

export type OptionsUnderlyingSnapshot = {
  price: number | null;
  changePct?: number | null;
  source: string;
  asOf: string;
  freshness: OptionsFreshness;
};

export type OptionsAvailability = {
  supported: boolean;
  provider: string;
  limitations: string[];
};

export type OptionsLabMetadata = {
  readOnly: boolean;
  noExternalCallsInTests: boolean;
  limitations: string[];
  sourceLabel?: string;
  updatedAt?: string;
};

export type OptionsUnderlyingSummaryResponse = {
  symbol: string;
  market: string;
  underlying: OptionsUnderlyingSnapshot;
  optionsAvailability: OptionsAvailability;
  metadata: OptionsLabMetadata;
  optionsReadiness?: OptionsResearchReadiness | null;
  optionsResearchReadiness?: OptionsResearchReadiness | null;
};

export type OptionsExpiration = {
  date: string;
  dte: number;
  type: 'weekly' | 'monthly' | 'quarterly' | string;
  chainAvailable: boolean;
  asOf: string;
  source: string;
  warnings: string[];
};

export type OptionsExpirationsResponse = {
  symbol: string;
  expirations: OptionsExpiration[];
  metadata: OptionsLabMetadata;
  optionsReadiness?: OptionsResearchReadiness | null;
  optionsResearchReadiness?: OptionsResearchReadiness | null;
};

export type OptionContract = {
  contractSymbol: string;
  side: OptionSide;
  strike: number;
  bid: number | null;
  ask: number | null;
  mid: number | null;
  volume: number | null;
  openInterest: number | null;
  impliedVolatility: number | null;
  delta?: number | null;
  gamma?: number | null;
  theta?: number | null;
  vega?: number | null;
  rho?: number | null;
  spreadPct?: number | null;
  moneyness: OptionMoneyness;
  liquidityScore?: number | null;
  warnings?: string[];
};

export type OptionsChainResponse = {
  symbol: string;
  expiration: string;
  underlying: OptionsUnderlyingSnapshot | null;
  calls: OptionContract[];
  puts: OptionContract[];
  filtersApplied: {
    minOpenInterest?: number;
    maxSpreadPct?: number;
  };
  chainAsOf: string;
  source: string;
  limitations: string[];
  metadata: OptionsLabMetadata;
  optionsReadiness?: OptionsResearchReadiness | null;
  optionsResearchReadiness?: OptionsResearchReadiness | null;
  optionsStructureSignalPacket?: OptionsStructureSignalPacket | null;
  optionsChainReadiness?: OptionsChainReadiness | null;
  optionsChainReadinessView?: OptionsChainReadinessView;
};

export type OptionsChainCoverageReadiness = {
  state: 'available' | 'limited' | 'missing' | string;
};

export type OptionsChainExpirationCoverageReadiness = OptionsChainCoverageReadiness & {
  expirationCount?: number | null;
  missingCount?: number | null;
  coveredExpirations?: string[] | null;
};

export type OptionsChainStrikeCoverageReadiness = OptionsChainCoverageReadiness & {
  strikeCount?: number | null;
  sparseCount?: number | null;
};

export type OptionsChainFieldCompleteness = {
  state: 'available' | 'partial' | 'missing' | string;
  availableCount?: number | null;
  missingCount?: number | null;
  totalCount?: number | null;
};

export type OptionsChainCompletenessReadiness = {
  iv?: OptionsChainFieldCompleteness | null;
  greeks?: OptionsChainFieldCompleteness | null;
  openInterest?: OptionsChainFieldCompleteness | null;
  volume?: OptionsChainFieldCompleteness | null;
  quote?: OptionsChainFieldCompleteness | null;
};

export type OptionsChainReadiness = {
  contractVersion?: string | null;
  overallState: 'ready' | 'partial' | 'blocked' | string;
  chainState: 'available' | 'partial' | 'stale' | 'missing' | string;
  configurationState: 'available' | 'missing' | string;
  dataBoundary: 'provider_backed' | 'demo_sample' | 'unavailable' | string;
  authorityState: 'authoritative' | 'observation_only' | string;
  scoreAuthority?: 'authoritative' | 'observation_only' | string | null;
  expirationCoverage?: OptionsChainExpirationCoverageReadiness | null;
  strikeCoverage?: OptionsChainStrikeCoverageReadiness | null;
  fieldCompleteness?: OptionsChainCompletenessReadiness | null;
  blockingReasons?: string[] | null;
  warnings?: string[] | null;
  nextEvidenceNeeded?: string[] | null;
};

export type OptionsChainReadinessLabel =
  | '链可用'
  | '链待接入'
  | '链部分可用'
  | '到期覆盖可用'
  | '行权价覆盖有限'
  | 'IV待补'
  | '希腊值待补'
  | 'OI/成交待补'
  | '报价字段待补'
  | '演示样本'
  | '仅观察'
  | '结构比较可用';

export type OptionsChainReadinessView = {
  labels: OptionsChainReadinessLabel[];
  blockerLabels: OptionsChainReadinessLabel[];
  allLabels: OptionsChainReadinessLabel[];
};

export type OptionsStructureSignalPacket = {
  gammaCoverageState: 'covered' | 'partial' | 'missing' | string;
  ivCoverageState: 'covered' | 'partial' | 'missing' | string;
  skewObservation: {
    state: 'observed' | 'insufficient' | string;
    callAverageIv?: number | null;
    putAverageIv?: number | null;
    callPutIvSpread?: number | null;
    contractCount?: number | null;
  };
  liquidityObservation: {
    state: 'complete' | 'partial' | 'missing' | string;
    contractCount?: number | null;
    contractsWithBidAsk?: number | null;
    wideSpreadCount?: number | null;
    thinLiquidityCount?: number | null;
    minimumOpenInterest?: number | null;
    minimumVolume?: number | null;
  };
  expirationCoverage: {
    state: 'single_expiration' | 'multi_expiration' | 'missing' | string;
    expirationCount?: number | null;
    nearestDte?: number | null;
    contractsByExpiration?: Array<{
      expiration: string;
      contractCount: number;
    }> | null;
  };
  missingGreeks: string[];
  staleOrDemoBoundary: {
    state: 'live' | 'demo_or_stale' | string;
    sourceFreshness?: string | null;
    fixtureBacked?: boolean | null;
    syntheticData?: boolean | null;
    forceRefreshIgnored?: boolean | null;
  };
  observationBoundary: {
    researchOnly?: boolean | null;
    decisionGrade?: boolean | null;
    executionSupported?: boolean | null;
    orderPlacement?: boolean | null;
    brokerExecution?: boolean | null;
    portfolioMutation?: boolean | null;
  };
  researchNextSteps: string[];
};

export type OptionsStructureAvailabilityState = 'available' | 'degraded' | 'not_available' | string;
export type OptionsStructureCalculationState = 'available' | 'degraded' | 'not_available' | string;
export type OptionsStructureBucketState = 'available' | 'not_available' | string;

export type OptionContractStructureRow = {
  contractVersion?: string | null;
  contractSymbol?: string | null;
  side?: OptionSide | string | null;
  expiration?: string | null;
  strike?: number | null;
  multiplier?: number | null;
  openInterest?: number | null;
  volume?: number | null;
  impliedVolatility?: number | null;
  delta?: number | null;
  gamma?: number | null;
  vega?: number | null;
  theta?: number | null;
  charm?: number | null;
  vanna?: number | null;
  dealerGammaExposure?: number | null;
  asOf?: string | null;
  freshness?: string | null;
  missingInputs?: string[] | null;
};

export type OptionChainStructureSnapshot = {
  contractVersion?: string | null;
  symbol?: string | null;
  spotPrice?: number | null;
  asOf?: string | null;
  freshness?: string | null;
  contracts: OptionContractStructureRow[];
  missingInputs?: string[] | null;
};

export type OptionsZeroDteConcentration = {
  state: OptionsStructureBucketState;
  expiration?: string | null;
  dte?: number | null;
  contractCount: number;
  callOpenInterest: number;
  putOpenInterest: number;
  callVolume: number;
  putVolume: number;
  openInterestShare?: number | null;
  volumeShare?: number | null;
};

export type OptionsGammaFlipLevel = {
  state: OptionsStructureBucketState;
  level?: number | null;
  reason?: string | null;
};

export type OptionsStrikeExposureSummary = {
  strike?: number | null;
  expiration?: string | null;
  contractCount: number;
  callOpenInterest: number;
  putOpenInterest: number;
  callVolume: number;
  putVolume: number;
  callDealerGammaExposure?: number | null;
  putDealerGammaExposure?: number | null;
  netDealerGammaExposure?: number | null;
  calculationState: OptionsStructureCalculationState;
  missingInputs?: string[] | null;
};

export type OptionsExpirationExposureSummary = {
  expiration?: string | null;
  dte?: number | null;
  isZeroDte: boolean;
  strikeCount: number;
  contractCount: number;
  callOpenInterest: number;
  putOpenInterest: number;
  callVolume: number;
  putVolume: number;
  netDealerGammaExposure?: number | null;
  calculationState: OptionsStructureCalculationState;
  missingInputs?: string[] | null;
};

export type OptionsNearestExpirationBucket = {
  expiration?: string | null;
  dte?: number | null;
  contractCount: number;
};

export type OptionsStructureSummary = {
  contractVersion?: string | null;
  symbol: string;
  status: OptionsStructureAvailabilityState;
  calculationState: OptionsStructureCalculationState;
  observationOnly: boolean;
  decisionGrade: boolean;
  providerConfigured: boolean;
  spotPrice?: number | null;
  asOf?: string | null;
  freshness?: string | null;
  snapshot: OptionChainStructureSnapshot;
  strikeSummaries: OptionsStrikeExposureSummary[];
  expirationSummaries: OptionsExpirationExposureSummary[];
  nearestExpirations: OptionsNearestExpirationBucket[];
  zeroDte: OptionsZeroDteConcentration;
  gammaFlipLevel: OptionsGammaFlipLevel;
  totalDealerGammaExposure?: number | null;
  blockingReasons: string[];
  warnings: string[];
  nextEvidenceNeeded: string[];
};

export type OptionsStrategyCompareRequest = {
  symbol: string;
  direction: OptionsDirection;
  targetPrice: number;
  targetDate: string;
  maxPremium?: number;
  riskProfile: OptionsRiskProfile;
  strategies?: OptionsStrategyType[];
  forceRefresh?: boolean;
};

export type OptionsStrategyLeg = {
  action: 'buy' | 'sell';
  side: OptionSide;
  contractSymbol: string;
  expiration: string;
  strike: number;
  mid: number;
  quantity: number;
};

export type OptionsStrategyComparison = {
  strategyType: OptionsStrategyType;
  legs: OptionsStrategyLeg[];
  netDebit: number;
  maxLoss: number;
  maxGain: number | null;
  breakeven: number;
  requiredMovePct: number;
  payoffAtTarget: number;
  riskRewardRatio: number | null;
  liquidityWarnings: string[];
  ivThetaNotes: string[];
  suitabilityNotes: string[];
  limitations: string[];
  noAdviceDisclosure: string;
};

export type OptionsStrategyCompareMetadata = {
  readOnly?: boolean;
  fixtureBacked?: boolean;
  syntheticData?: boolean;
  noExternalCalls?: boolean;
  noLlmCalls?: boolean;
  noOrderPlacement?: boolean;
  noBrokerConnection?: boolean;
  noPortfolioMutation?: boolean;
  noTradingRecommendation?: boolean;
  scoringEngine?: string;
  strategyEngine?: string;
  forceRefreshIgnored?: boolean;
};

export type OptionsGateDetails = Record<string, unknown> | null;

export type OptionsConsumerScenarioFrame = {
  contractVersion?: string | null;
  frameState?: 'ready' | 'observe_only' | 'insufficient' | 'blocked' | string | null;
  underlying?: Record<string, unknown> | null;
  strategyType?: string | null;
  expiration?: string | null;
  scenarioCoverage?: string | null;
  chainQuality?: {
    hasChain?: boolean | null;
    contractCount?: number | null;
    callCount?: number | null;
    putCount?: number | null;
    freshness?: string | null;
    sourceType?: string | null;
    coverageState?: string | null;
  } | null;
  liquidityGate?: string | null;
  ivGreeksGate?: string | null;
  spreadGate?: string | null;
  payoffEvidence?: {
    targetPrice?: number | null;
    payoffAtTarget?: number | null;
    expectedMoveAbs?: number | null;
    expectedMovePct?: number | null;
    expectedMoveSource?: string | null;
    candidateCount?: number | null;
    comparisonState?: string | null;
    scenarioPoints?: number | null;
    theoreticalPricingAvailable?: boolean | null;
  } | null;
  riskEvidence?: {
    premiumAtRisk?: number | null;
    maxLoss?: number | null;
    maxGain?: number | null;
    breakeven?: number | null;
    requiredMovePct?: number | null;
  } | null;
  assumptions?: Record<string, unknown> | null;
  missingEvidence?: string[] | null;
  blockingReasons?: string[] | null;
  nextEvidenceNeeded?: string[] | null;
  noTradingBoundary?: {
    analyticalOnly?: boolean | null;
    noBrokerExecution?: boolean | null;
    noOrderPlacement?: boolean | null;
    noPortfolioMutation?: boolean | null;
    noTradingRecommendation?: boolean | null;
  } | null;
};

export type OptionsStrategyCompareResponse = {
  symbol: string;
  underlying: Record<string, unknown>;
  assumptions: Record<string, unknown>;
  strategies: OptionsStrategyComparison[];
  limitations: string[];
  metadata: OptionsStrategyCompareMetadata;
  optionsReadiness?: OptionsResearchReadiness | null;
  optionsResearchReadiness?: OptionsResearchReadiness | null;
  optionsConsumerScenarioFrame?: OptionsConsumerScenarioFrame | null;
};

export type OptionsStrategyAnalyzerTemplate =
  | 'long_straddle'
  | 'long_strangle'
  | 'bull_call_spread'
  | 'bear_put_spread'
  | 'iron_condor'
  | 'long_call'
  | 'long_put';

export type OptionsStrategyAnalyzerRequest = {
  symbol: string;
  expiration?: string;
  strategies?: OptionsStrategyAnalyzerTemplate[];
  scenarioPrices?: number[];
  riskFreeRate?: number;
  scenarioAssumptions?: Record<string, unknown>;
  forceRefresh?: boolean;
};

export type OptionsStrategyAnalyzerLeg = {
  legAction: 'long' | 'short' | string;
  side: OptionSide;
  contractSymbol: string;
  expiration: string;
  strike: number;
  mid: number;
  quantity: number;
};

export type OptionsStrategyPayoffRow = {
  underlyingPrice: number;
  grossPayoff: number;
  netPayoff: number;
};

export type OptionsStrategyAggregateGreeks = {
  delta?: number | null;
  gamma?: number | null;
  theta?: number | null;
  vega?: number | null;
  rho?: number | null;
};

export type OptionsModelImpliedProbability = {
  state: 'available' | 'partial' | 'unavailable' | string;
  modelImpliedProbabilityOfProfit?: number | null;
  inputs?: Record<string, unknown> | null;
  blockers?: string[] | null;
};

export type OptionsHistoricalWinRate = {
  state: 'available' | 'unavailable' | string;
  value?: number | null;
  blockers?: string[] | null;
};

export type OptionsStrategyAnalyzerReadiness = {
  strategyStructureState: 'available' | 'blocked' | string;
  chainDataState: 'sufficient' | 'partial' | 'blocked' | string;
  analysisState: 'analysis_ready' | 'observation_only' | 'blocked' | string;
  observationOnly: boolean;
  decisionGrade: boolean;
  dataBlockers?: string[] | null;
};

export type OptionsStrategyAnalysis = {
  strategyType: OptionsStrategyAnalyzerTemplate;
  legs: OptionsStrategyAnalyzerLeg[];
  netDebit?: number | null;
  netCredit?: number | null;
  maxProfit?: number | null;
  maxLoss?: number | null;
  breakevens: number[];
  payoffTable: OptionsStrategyPayoffRow[];
  aggregateGreeks?: OptionsStrategyAggregateGreeks | null;
  missingGreeksBlockers?: string[] | null;
  modelImpliedProbability: OptionsModelImpliedProbability;
  historicalWinRate: OptionsHistoricalWinRate;
  readiness: OptionsStrategyAnalyzerReadiness;
  limitations: string[];
};

export type OptionsStrategyAnalyzerResponse = {
  symbol: string;
  underlying: Record<string, unknown>;
  assumptions: Record<string, unknown>;
  analyses: OptionsStrategyAnalysis[];
  strategyReadiness: OptionsStrategyAnalyzerReadiness;
  limitations: string[];
  observationOnly: boolean;
  decisionGrade: boolean;
  metadata: OptionsStrategyCompareMetadata;
};

export type OptionsDecisionLeg = {
  action: 'buy' | 'sell';
  side: OptionSide;
  contractSymbol?: string;
  expiration?: string;
  strike?: number;
  quantity?: number;
};

export type OptionsDecisionRequest = {
  symbol: string;
  strategy: OptionsStrategyType;
  expiration?: string;
  legs?: OptionsDecisionLeg[];
  targetPrice?: number;
  targetDate?: string;
  holdingHorizonDays?: number;
  riskBudget?: number;
  scenarioAssumptions?: Record<string, unknown>;
  forceRefresh?: boolean;
};

export type OptionsDecisionResponse = {
  symbol: string;
  strategy: OptionsStrategyType;
  dataQuality: {
    dataQualityScore: number | null;
    dataQualityTier: 'live_usable' | 'delayed_usable' | 'synthetic_demo_only' | 'insufficient' | string;
    sourceType?: string | null;
    asOfAgeMinutes?: number | null;
    blockingReasons?: string[] | null;
    warnings?: string[] | null;
  } | null;
  liquidity: {
    liquidityScore: number | null;
    spreadPct?: number | null;
    liquidityWarnings?: string[] | null;
  } | null;
  ivGreeks: {
    ivReadiness: number | null;
    ivRankStatus: 'unavailable' | 'available' | string;
    ivRank?: number | null;
    ivPercentile?: number | null;
    ivRankSource?: string | null;
    ivRankConfidence?: string | null;
    warnings?: string[] | null;
    dteBucket?: string | null;
  } | null;
  ivRank?: number | null;
  ivPercentile?: number | null;
  ivRankStatus?: 'unavailable' | 'available' | string | null;
  decisionGrade?: boolean | null;
  gateDecision?: string | null;
  failClosedReasonCodes?: string[] | null;
  gateIssues?: string[] | null;
  dataQualityGates?: OptionsGateDetails;
  liquidityGates?: OptionsGateDetails;
  expectedMove?: {
    expectedMoveAbs?: number | null;
    expectedMovePct?: number | null;
    expectedMoveSource?: 'straddle_mid' | 'iv_dte' | 'unavailable' | string | null;
    expectedMoveWarnings?: string[] | null;
  } | null;
  optimizer?: {
    preferredStrategyKey?: OptionsStrategyType | null;
    optimizerLabel?: '数据不足，禁止判断' | '不建议交易' | '仅观察' | '可关注替代结构' | '有条件可交易' | string | null;
    alternatives?: OptionsOptimizerAlternative[] | null;
    noTradeReason?: string | null;
  } | null;
  rankedAlternatives?: OptionsOptimizerAlternative[] | null;
  breakeven: {
    breakeven?: number | null;
    requiredMovePct?: number | null;
    targetPriceStatus?: string | null;
    score: number | null;
  } | null;
  riskReward: {
    maxLoss?: number | null;
    maxGain?: number | null;
    riskRewardRatio?: number | null;
    score: number | null;
    warnings?: string[] | null;
  } | null;
  tradeQualityScore: number | null;
  decisionLabel: string | null;
  primaryReasons?: string[] | null;
  riskWarnings?: string[] | null;
  betterAlternative?: {
    strategyType: OptionsStrategyType;
    reason: string;
    maxLoss?: number | null;
    riskRewardRatio?: number | null;
  } | null;
  noAdviceDisclosure?: string | null;
  freshness?: {
    source?: string | null;
    freshness?: string | null;
    asOf?: string | null;
  } | null;
  metadata?: OptionsStrategyCompareMetadata | null;
  optionsReadiness?: OptionsResearchReadiness | null;
  optionsResearchReadiness?: OptionsResearchReadiness | null;
  optionsConsumerScenarioFrame?: OptionsConsumerScenarioFrame | null;
};

export type OptionsOptimizerAlternative = {
  strategyKey: OptionsStrategyType;
  dataQualityTier: 'live_usable' | 'delayed_usable' | 'synthetic_demo_only' | 'insufficient' | string;
  liquidityScore: number | null;
  breakevenPressure?: number | null;
  maxLoss?: number | null;
  maxGain?: number | null;
  riskRewardRatio?: number | null;
  expectedMoveAlignment?: number | null;
  ivReadiness?: number | null;
  tradeQualityScore: number | null;
  decisionLabel: string | null;
  primaryReasons?: string[] | null;
  riskWarnings?: string[] | null;
};


function normalizeSymbol(symbol: string): string {
  return symbol.trim().toUpperCase() || 'TEM';
}

const EMPTY_OPTIONS_CHAIN_READINESS_VIEW: OptionsChainReadinessView = {
  labels: [],
  blockerLabels: [],
  allLabels: [],
};

function uniqueChainReadinessLabels(labels: OptionsChainReadinessLabel[]): OptionsChainReadinessLabel[] {
  return [...new Set(labels)];
}

function isIncompleteField(value?: OptionsChainFieldCompleteness | null): boolean {
  return value?.state === 'partial' || value?.state === 'missing';
}

export function normalizeOptionsChainReadinessView(
  readiness?: OptionsChainReadiness | null,
): OptionsChainReadinessView {
  if (!readiness) return EMPTY_OPTIONS_CHAIN_READINESS_VIEW;

  const truth = projectMarketTruth(readiness);
  const labels: OptionsChainReadinessLabel[] = [];
  const blockerLabels: OptionsChainReadinessLabel[] = [];
  const configurationMissing = readiness.configurationState === 'missing';
  const unavailableBoundary = truth.availability === 'unavailable';

  if (configurationMissing || unavailableBoundary || readiness.chainState === 'missing') {
    labels.push('链待接入');
  } else if (truth.availability === 'partial' || ['stale', 'delayed', 'cached'].includes(truth.freshness)) {
    labels.push('链部分可用');
  } else if (truth.availability === 'available') {
    labels.push('链可用');
  } else {
    labels.push('链待接入');
  }

  if (readiness.expirationCoverage?.state === 'available') {
    labels.push('到期覆盖可用');
  }

  if (readiness.strikeCoverage?.state === 'limited' || readiness.strikeCoverage?.state === 'missing') {
    blockerLabels.push('行权价覆盖有限');
  }

  const completeness = readiness.fieldCompleteness;
  if (isIncompleteField(completeness?.iv)) blockerLabels.push('IV待补');
  if (isIncompleteField(completeness?.greeks)) blockerLabels.push('希腊值待补');
  if (isIncompleteField(completeness?.openInterest) || isIncompleteField(completeness?.volume)) {
    blockerLabels.push('OI/成交待补');
  }
  if (isIncompleteField(completeness?.quote)) blockerLabels.push('报价字段待补');

  if (readiness.dataBoundary === 'demo_sample') {
    labels.push('演示样本');
  }

  if (truth.mode === 'observation_only' || truth.readiness === 'blocked') {
    labels.push('仅观察');
  } else if (
    truth.scoreContribution === 'eligible'
    && truth.readiness === 'ready'
    && truth.availability === 'available'
    && blockerLabels.length === 0
  ) {
    labels.push('结构比较可用');
  }

  const safeLabels = uniqueChainReadinessLabels(labels);
  const safeBlockers = uniqueChainReadinessLabels(blockerLabels);

  return {
    labels: safeLabels,
    blockerLabels: safeBlockers,
    allLabels: uniqueChainReadinessLabels([...safeLabels, ...safeBlockers]),
  };
}

function normalizeOptionsChainResponse(response: OptionsChainResponse): OptionsChainResponse {
  const readiness = response.optionsChainReadiness ?? null;

  return {
    ...response,
    optionsChainReadiness: readiness,
    optionsChainReadinessView: normalizeOptionsChainReadinessView(readiness),
  };
}

function normalizeNumberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function normalizeStringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : [];
}

function normalizeStructureContract(value: unknown): OptionContractStructureRow | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const row = value as Partial<OptionContractStructureRow>;
  return {
    contractVersion: row.contractVersion ?? null,
    contractSymbol: row.contractSymbol ?? null,
    side: row.side ?? null,
    expiration: row.expiration ?? null,
    strike: normalizeNumberOrNull(row.strike),
    multiplier: normalizeNumberOrNull(row.multiplier),
    openInterest: normalizeNumberOrNull(row.openInterest),
    volume: normalizeNumberOrNull(row.volume),
    impliedVolatility: normalizeNumberOrNull(row.impliedVolatility),
    delta: normalizeNumberOrNull(row.delta),
    gamma: normalizeNumberOrNull(row.gamma),
    vega: normalizeNumberOrNull(row.vega),
    theta: normalizeNumberOrNull(row.theta),
    charm: normalizeNumberOrNull(row.charm),
    vanna: normalizeNumberOrNull(row.vanna),
    dealerGammaExposure: normalizeNumberOrNull(row.dealerGammaExposure),
    asOf: row.asOf ?? null,
    freshness: row.freshness ?? null,
    missingInputs: normalizeStringList(row.missingInputs),
  };
}

function normalizeStructureSnapshot(value: unknown, symbol: string): OptionChainStructureSnapshot {
  const snapshot = value && typeof value === 'object' && !Array.isArray(value)
    ? value as Partial<OptionChainStructureSnapshot>
    : {};
  return {
    contractVersion: snapshot.contractVersion ?? null,
    symbol: snapshot.symbol ?? symbol,
    spotPrice: normalizeNumberOrNull(snapshot.spotPrice),
    asOf: snapshot.asOf ?? null,
    freshness: snapshot.freshness ?? null,
    contracts: Array.isArray(snapshot.contracts)
      ? snapshot.contracts.map(normalizeStructureContract).filter((row): row is OptionContractStructureRow => Boolean(row))
      : [],
    missingInputs: normalizeStringList(snapshot.missingInputs),
  };
}

function normalizeZeroDte(value: unknown): OptionsZeroDteConcentration {
  const bucket = value && typeof value === 'object' && !Array.isArray(value)
    ? value as Partial<OptionsZeroDteConcentration>
    : {};
  return {
    state: bucket.state ?? 'not_available',
    expiration: bucket.expiration ?? null,
    dte: normalizeNumberOrNull(bucket.dte),
    contractCount: normalizeNumberOrNull(bucket.contractCount) ?? 0,
    callOpenInterest: normalizeNumberOrNull(bucket.callOpenInterest) ?? 0,
    putOpenInterest: normalizeNumberOrNull(bucket.putOpenInterest) ?? 0,
    callVolume: normalizeNumberOrNull(bucket.callVolume) ?? 0,
    putVolume: normalizeNumberOrNull(bucket.putVolume) ?? 0,
    openInterestShare: normalizeNumberOrNull(bucket.openInterestShare),
    volumeShare: normalizeNumberOrNull(bucket.volumeShare),
  };
}

function normalizeGammaFlipLevel(value: unknown): OptionsGammaFlipLevel {
  const level = value && typeof value === 'object' && !Array.isArray(value)
    ? value as Partial<OptionsGammaFlipLevel>
    : {};
  return {
    state: level.state ?? 'not_available',
    level: normalizeNumberOrNull(level.level),
    reason: level.reason ?? null,
  };
}

function normalizeStrikeSummary(value: unknown): OptionsStrikeExposureSummary | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const row = value as Partial<OptionsStrikeExposureSummary>;
  return {
    strike: normalizeNumberOrNull(row.strike),
    expiration: row.expiration ?? null,
    contractCount: normalizeNumberOrNull(row.contractCount) ?? 0,
    callOpenInterest: normalizeNumberOrNull(row.callOpenInterest) ?? 0,
    putOpenInterest: normalizeNumberOrNull(row.putOpenInterest) ?? 0,
    callVolume: normalizeNumberOrNull(row.callVolume) ?? 0,
    putVolume: normalizeNumberOrNull(row.putVolume) ?? 0,
    callDealerGammaExposure: normalizeNumberOrNull(row.callDealerGammaExposure),
    putDealerGammaExposure: normalizeNumberOrNull(row.putDealerGammaExposure),
    netDealerGammaExposure: normalizeNumberOrNull(row.netDealerGammaExposure),
    calculationState: row.calculationState ?? 'not_available',
    missingInputs: normalizeStringList(row.missingInputs),
  };
}

function normalizeExpirationSummary(value: unknown): OptionsExpirationExposureSummary | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const row = value as Partial<OptionsExpirationExposureSummary>;
  return {
    expiration: row.expiration ?? null,
    dte: normalizeNumberOrNull(row.dte),
    isZeroDte: Boolean(row.isZeroDte),
    strikeCount: normalizeNumberOrNull(row.strikeCount) ?? 0,
    contractCount: normalizeNumberOrNull(row.contractCount) ?? 0,
    callOpenInterest: normalizeNumberOrNull(row.callOpenInterest) ?? 0,
    putOpenInterest: normalizeNumberOrNull(row.putOpenInterest) ?? 0,
    callVolume: normalizeNumberOrNull(row.callVolume) ?? 0,
    putVolume: normalizeNumberOrNull(row.putVolume) ?? 0,
    netDealerGammaExposure: normalizeNumberOrNull(row.netDealerGammaExposure),
    calculationState: row.calculationState ?? 'not_available',
    missingInputs: normalizeStringList(row.missingInputs),
  };
}

function normalizeNearestExpiration(value: unknown): OptionsNearestExpirationBucket | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const row = value as Partial<OptionsNearestExpirationBucket>;
  return {
    expiration: row.expiration ?? null,
    dte: normalizeNumberOrNull(row.dte),
    contractCount: normalizeNumberOrNull(row.contractCount) ?? 0,
  };
}

export function normalizeOptionsStructureSummary(payload: unknown): OptionsStructureSummary {
  const normalized = toCamelCase<Partial<OptionsStructureSummary>>(payload);
  const symbol = typeof normalized.symbol === 'string' && normalized.symbol.trim()
    ? normalized.symbol.trim().toUpperCase()
    : '';
  const truth = projectMarketTruth(normalized);
  return {
    contractVersion: normalized.contractVersion ?? null,
    symbol,
    status: normalized.status ?? 'not_available',
    calculationState: normalized.calculationState ?? 'not_available',
    observationOnly: normalized.observationOnly !== false,
    decisionGrade: truth.mode === 'decision_grade',
    providerConfigured: normalized.providerConfigured === true,
    spotPrice: normalizeNumberOrNull(normalized.spotPrice),
    asOf: normalized.asOf ?? null,
    freshness: normalized.freshness ?? 'unknown',
    snapshot: normalizeStructureSnapshot(normalized.snapshot, symbol),
    strikeSummaries: Array.isArray(normalized.strikeSummaries)
      ? normalized.strikeSummaries.map(normalizeStrikeSummary).filter((row): row is OptionsStrikeExposureSummary => Boolean(row))
      : [],
    expirationSummaries: Array.isArray(normalized.expirationSummaries)
      ? normalized.expirationSummaries.map(normalizeExpirationSummary).filter((row): row is OptionsExpirationExposureSummary => Boolean(row))
      : [],
    nearestExpirations: Array.isArray(normalized.nearestExpirations)
      ? normalized.nearestExpirations.map(normalizeNearestExpiration).filter((row): row is OptionsNearestExpirationBucket => Boolean(row))
      : [],
    zeroDte: normalizeZeroDte(normalized.zeroDte),
    gammaFlipLevel: normalizeGammaFlipLevel(normalized.gammaFlipLevel),
    totalDealerGammaExposure: normalizeNumberOrNull(normalized.totalDealerGammaExposure),
    blockingReasons: normalizeStringList(normalized.blockingReasons),
    warnings: normalizeStringList(normalized.warnings),
    nextEvidenceNeeded: normalizeStringList(normalized.nextEvidenceNeeded),
  };
}

export const optionsLabApi = {
  getUnderlyingSummary(symbol: string): Promise<OptionsUnderlyingSummaryResponse> {
    const normalized = normalizeSymbol(symbol);
    return apiClient.get<Record<string, unknown>>(`/api/v1/options/underlyings/${encodeURIComponent(normalized)}/summary`)
      .then((response) => toCamelCase<OptionsUnderlyingSummaryResponse>(response.data));
  },
  getExpirations(symbol: string): Promise<OptionsExpirationsResponse> {
    const normalized = normalizeSymbol(symbol);
    return apiClient.get<Record<string, unknown>>(`/api/v1/options/underlyings/${encodeURIComponent(normalized)}/expirations`)
      .then((response) => toCamelCase<OptionsExpirationsResponse>(response.data));
  },
  getOptionChain(symbol: string, expiration: string): Promise<OptionsChainResponse> {
    const normalized = normalizeSymbol(symbol);
    const query = new URLSearchParams({ expiration, side: 'both' });
    return apiClient.get<Record<string, unknown>>(
      `/api/v1/options/underlyings/${encodeURIComponent(normalized)}/chain?${query.toString()}`,
    ).then((response) => normalizeOptionsChainResponse(toCamelCase<OptionsChainResponse>(response.data)));
  },
  getOptionsStructure(symbol: string): Promise<OptionsStructureSummary> {
    const normalized = normalizeSymbol(symbol);
    return apiClient.get<Record<string, unknown>>(`/api/v1/options/underlyings/${encodeURIComponent(normalized)}/structure`)
      .then((response) => normalizeOptionsStructureSummary(response.data));
  },
  compareStrategies(request: OptionsStrategyCompareRequest): Promise<OptionsStrategyCompareResponse> {
    const normalized = normalizeSymbol(request.symbol);
    const payload: OptionsStrategyCompareRequest = {
      ...request,
      symbol: normalized,
      strategies: request.strategies?.length
        ? request.strategies
        : ['long_call', 'long_put', 'bull_call_spread', 'bear_put_spread'],
    };
    return apiClient.post<Record<string, unknown>>('/api/v1/options/strategies/compare', payload)
      .then((response) => toCamelCase<OptionsStrategyCompareResponse>(response.data));
  },
  analyzeStrategies(request: OptionsStrategyAnalyzerRequest): Promise<OptionsStrategyAnalyzerResponse> {
    const normalized = normalizeSymbol(request.symbol);
    const payload: OptionsStrategyAnalyzerRequest = {
      ...request,
      symbol: normalized,
    };
    return apiClient.post<Record<string, unknown>>('/api/v1/options/strategies/analyze', payload)
      .then((response) => toCamelCase<OptionsStrategyAnalyzerResponse>(response.data));
  },
  evaluateDecision(request: OptionsDecisionRequest): Promise<OptionsDecisionResponse> {
    const normalized = normalizeSymbol(request.symbol);
    const payload: OptionsDecisionRequest = {
      ...request,
      symbol: normalized,
    };
    return apiClient.post<Record<string, unknown>>('/api/v1/options/decision/evaluate', payload)
      .then((response) => toCamelCase<OptionsDecisionResponse>(response.data));
  },
};
