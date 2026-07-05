/**
 * Backtest API type definitions
 * Mirrors api/v1/schemas/backtest.py
 */

import type { ProductReadModel } from './productReadModel';

export type AssumptionMap = Record<string, unknown>;

export interface BacktestDiagnosticWarning {
  code?: string | null;
  severity?: string | null;
  message?: string | null;
}

export interface BacktestDataQualityAnomaly {
  date?: string | null;
  type?: string | null;
  field?: string | null;
  value?: number | null;
  [key: string]: unknown;
}

export interface BacktestDataQuality {
  symbol?: string | null;
  benchmarkSymbol?: string | null;
  provider?: string | null;
  source?: string | null;
  frequency?: string | null;
  requestedStart?: string | null;
  requestedEnd?: string | null;
  actualStart?: string | null;
  actualEnd?: string | null;
  barCount?: number | null;
  expectedBarCount?: number | null;
  missingBarCount?: number | null;
  missingDates?: string[];
  anomalyCount?: number | null;
  anomalies?: BacktestDataQualityAnomaly[];
  adjustmentMode?: string | null;
  dividendsHandled?: string | null;
  splitsHandled?: string | null;
  timezone?: string | null;
  currency?: string | null;
  market?: string | null;
  isComplete?: boolean | null;
  qualityScore?: number | null;
  warnings?: BacktestDiagnosticWarning[];
}

export interface RuleBacktestExecutionMarketRules {
  tradingDayExecution?: string | null;
  terminalBarFillFallback?: string | null;
  windowEndPositionHandling?: string | null;
}

export interface RuleBacktestExecutionModel {
  version?: string;
  timeframe?: string;
  signalEvaluationTiming?: string | null;
  entryTiming?: string | null;
  exitTiming?: string | null;
  entryFillPriceBasis?: string | null;
  exitFillPriceBasis?: string | null;
  positionSizing?: string | null;
  feeModel?: string | null;
  feeBpsPerSide?: number | null;
  slippageModel?: string | null;
  slippageBpsPerSide?: number | null;
  marketRules?: RuleBacktestExecutionMarketRules;
}

export interface StatusHistoryItem {
  status: string;
  at?: string;
}

export interface BacktestExecutionReadiness {
  contractVersion?: string;
  state?: string | null;
  resultContractAvailable?: boolean | null;
  engineState?: string | null;
  dataStatus?: string | null;
  calculationStatus?: string | null;
  sampleStatus?: string | null;
  benchmarkState?: string | null;
  reasonCodes?: string[];
  observationOnly?: boolean | null;
  consumerSafe?: boolean | null;
  noAdviceDisclosure?: string | null;
}

export interface BacktestHistoricalOhlcvReadiness {
  contractVersion?: string;
  status?: string | null;
  executable?: boolean | null;
  requestedSymbol?: string | null;
  requestedMarket?: string | null;
  requestedDateRange?: {
    start?: string | null;
    end?: string | null;
  } | null;
  requiredBarCount?: number | null;
  availableBarCount?: number | null;
  missingDateCoverage?: {
    missingBarCount?: number | null;
    state?: string | null;
  } | null;
  adjustedDataRequirement?: {
    required?: boolean | null;
    state?: string | null;
  } | null;
  benchmarkReadiness?: {
    required?: boolean | null;
    symbol?: string | null;
    status?: string | null;
  } | null;
  historicalOhlcvRuntimeStatus?: string | null;
  operatorNextAction?: string | null;
  consumerSafeMessage?: string | null;
  blockedExecutionReason?: string | null;
  missingDataClasses?: string[];
  consumerSafe?: boolean | null;
}

export interface BacktestResponseContractFields {
  dataStatus?: string;
  calculationStatus?: string;
  sampleStatus?: string;
  sourceWindow?: Record<string, unknown>;
  asOf?: string | null;
  limitations?: string[];
  executionReadiness?: BacktestExecutionReadiness;
  noAdviceDisclosure?: string;
}

// ============ Request / Response ============

export interface BacktestRunRequest {
  code?: string;
  force?: boolean;
  evalWindowDays?: number;
  minAgeDays?: number;
  limit?: number;
}

export interface BacktestRunResponse extends BacktestResponseContractFields {
  runId?: number;
  runAt?: string | null;
  processed: number;
  saved: number;
  completed: number;
  insufficient: number;
  errors: number;
  candidateCount: number;
  noResultReason?: string | null;
  noResultMessage?: string | null;
  latestPreparedSampleDate?: string | null;
  latestEligibleSampleDate?: string | null;
  excludedRecentReason?: string | null;
  excludedRecentMessage?: string | null;
  evaluationMode?: string | null;
  requestedMode?: string | null;
  resolvedSource?: string | null;
  fallbackUsed?: boolean | null;
  pricingResolvedSource?: string | null;
  pricingFallbackUsed?: boolean | null;
  evaluationWindowTradingBars?: number | null;
  maturityCalendarDays?: number | null;
  executionAssumptions: AssumptionMap;
}

export interface PrepareBacktestSamplesRequest {
  code: string;
  sampleCount?: number;
  evalWindowDays?: number;
  minAgeDays?: number;
  forceRefresh?: boolean;
}

export interface PrepareBacktestSamplesResponse {
  code: string;
  sampleCount: number;
  prepared: number;
  skippedExisting: number;
  marketRowsSaved: number;
  candidateRows: number;
  evalWindowDays: number;
  minAgeDays: number;
  preparedStartDate?: string | null;
  preparedEndDate?: string | null;
  latestPreparedAt?: string | null;
  latestPreparedSampleDate?: string | null;
  latestEligibleSampleDate?: string | null;
  excludedRecentReason?: string | null;
  excludedRecentMessage?: string | null;
  noResultReason?: string | null;
  noResultMessage?: string | null;
  requestedMode?: string | null;
  resolvedSource?: string | null;
  fallbackUsed?: boolean | null;
  pricingResolvedSource?: string | null;
  pricingFallbackUsed?: boolean | null;
  evaluationWindowTradingBars?: number | null;
  maturityCalendarDays?: number | null;
  executionReadiness?: BacktestExecutionReadiness;
}

export interface BacktestRunHistoryItem extends BacktestResponseContractFields {
  id: number;
  code?: string | null;
  evalWindowDays: number;
  evaluationWindowTradingBars?: number | null;
  minAgeDays: number;
  maturityCalendarDays?: number | null;
  force: boolean;
  runAt?: string | null;
  completedAt?: string | null;
  processed: number;
  saved: number;
  completed: number;
  insufficient: number;
  errors: number;
  candidateCount: number;
  resultCount: number;
  noResultReason?: string | null;
  noResultMessage?: string | null;
  status: string;
  totalEvaluations: number;
  completedCount: number;
  insufficientCount: number;
  longCount: number;
  cashCount: number;
  winCount: number;
  lossCount: number;
  neutralCount: number;
  winRatePct?: number | null;
  avgStockReturnPct?: number | null;
  avgSimulatedReturnPct?: number | null;
  directionAccuracyPct?: number | null;
  summary: Record<string, unknown>;
  evaluationMode?: string | null;
  requestedMode?: string | null;
  resolvedSource?: string | null;
  fallbackUsed?: boolean | null;
  executionAssumptions: AssumptionMap;
}

export interface BacktestRunHistoryResponse {
  total: number;
  page: number;
  limit: number;
  items: BacktestRunHistoryItem[];
}

export interface BacktestSampleStatusResponse {
  code: string;
  preparedCount: number;
  preparedStartDate?: string | null;
  preparedEndDate?: string | null;
  latestPreparedAt?: string | null;
  latestPreparedSampleDate?: string | null;
  latestEligibleSampleDate?: string | null;
  excludedRecentReason?: string | null;
  excludedRecentMessage?: string | null;
  evalWindowDays: number;
  minAgeDays: number;
  requestedMode?: string | null;
  resolvedSource?: string | null;
  fallbackUsed?: boolean | null;
  pricingResolvedSource?: string | null;
  pricingFallbackUsed?: boolean | null;
  evaluationWindowTradingBars?: number | null;
  maturityCalendarDays?: number | null;
  sampleReadinessState?: string | null;
  sampleBlockingReasons?: string[];
  executionReadiness?: BacktestExecutionReadiness;
  productReadModel?: ProductReadModel | null;
  historicalOhlcvReadiness?: BacktestHistoricalOhlcvReadiness;
}

export interface BacktestClearResponse {
  code: string;
  deletedRuns: number;
  deletedResults: number;
  deletedSamples: number;
  deletedSummaries: number;
  message?: string | null;
}

// ============ Rule Backtest ============

export interface RuleBacktestParseRequest {
  code?: string;
  strategyText: string;
  startDate?: string;
  endDate?: string;
  initialCapital?: number;
  feeBps?: number;
  slippageBps?: number;
}

export interface RuleBacktestRuleOperand {
  kind: 'indicator' | 'value';
  indicator?: string;
  period?: number | null;
  value?: number | null;
}

export interface RuleBacktestRuleNode {
  type: 'group' | 'comparison';
  op?: 'and' | 'or';
  rules?: RuleBacktestRuleNode[];
  left?: RuleBacktestRuleOperand;
  right?: RuleBacktestRuleOperand;
  compare?: '>' | '<' | '>=' | '<=';
  text?: string;
}

export interface RuleBacktestParsedStrategy {
  version: string;
  timeframe: string;
  sourceText: string;
  normalizedText: string;
  entry: RuleBacktestRuleNode;
  exit: RuleBacktestRuleNode;
  confidence: number;
  needsConfirmation: boolean;
  ambiguities: Array<Record<string, unknown>>;
  summary: Record<string, string>;
  maxLookback: number;
  strategyKind?: string;
  setup?: Record<string, unknown>;
  strategySpec?: RuleBacktestStrategySpec;
  executable?: boolean;
  normalizationState?: string;
  assumptions?: Array<Record<string, unknown>>;
  assumptionGroups?: Array<Record<string, unknown>>;
  detectedStrategyFamily?: string | null;
  unsupportedReason?: string | null;
  unsupportedDetails?: Array<Record<string, unknown>>;
  unsupportedExtensions?: Array<Record<string, unknown>>;
  coreIntentSummary?: string | null;
  interpretationConfidence?: number | null;
  supportedPortionSummary?: string | null;
  rewriteSuggestions?: Array<Record<string, unknown>>;
  parseWarnings?: Array<Record<string, unknown>>;
}

export interface RuleBacktestStrategySupport {
  executable?: boolean;
  normalizationState?: string;
  requiresConfirmation?: boolean;
  unsupportedReason?: string | null;
  detectedStrategyFamily?: string | null;
}

export interface RuleBacktestStrategyDateRange {
  startDate?: string | null;
  endDate?: string | null;
}

export interface RuleBacktestStrategyCapital {
  initialCapital?: number | null;
  currency?: string | null;
}

export interface RuleBacktestStrategyCosts {
  feeBps?: number | null;
  slippageBps?: number | null;
}

export interface RuleBacktestStrategySpecBase {
  version?: string;
  strategyType?: string;
  strategyFamily?: string;
  symbol?: string | null;
  timeframe?: string;
  maxLookback?: number;
  dateRange?: RuleBacktestStrategyDateRange;
  capital?: RuleBacktestStrategyCapital;
  costs?: RuleBacktestStrategyCosts;
  support?: RuleBacktestStrategySupport;
  [key: string]: unknown;
}

export interface RuleBacktestPeriodicSchedule {
  frequency?: string | null;
  timing?: string | null;
}

export interface RuleBacktestPeriodicOrder {
  mode?: string | null;
  quantity?: number | null;
  amount?: number | null;
}

export interface RuleBacktestPeriodicEntry {
  side?: string | null;
  order?: RuleBacktestPeriodicOrder;
  priceBasis?: string | null;
}

export interface RuleBacktestPeriodicExit {
  policy?: string | null;
  priceBasis?: string | null;
}

export interface RuleBacktestPeriodicPositionBehavior {
  accumulate?: boolean | null;
  cashPolicy?: string | null;
}

export interface RuleBacktestPeriodicAccumulationStrategySpec extends RuleBacktestStrategySpecBase {
  strategyType: 'periodic_accumulation';
  strategyFamily?: 'periodic_accumulation';
  dateRange?: RuleBacktestStrategyDateRange;
  capital?: RuleBacktestStrategyCapital;
  costs?: RuleBacktestStrategyCosts;
  schedule?: RuleBacktestPeriodicSchedule;
  entry?: RuleBacktestPeriodicEntry;
  exit?: RuleBacktestPeriodicExit;
  positionBehavior?: RuleBacktestPeriodicPositionBehavior;
}

export interface RuleBacktestMovingAverageSignalSpec {
  indicatorFamily: 'moving_average';
  fastPeriod: number;
  slowPeriod: number;
  fastType: string;
  slowType: string;
  entryCondition: string;
  exitCondition: string;
}

export interface RuleBacktestMacdSignalSpec {
  indicatorFamily: 'macd';
  fastPeriod: number;
  slowPeriod: number;
  signalPeriod: number;
  entryCondition: string;
  exitCondition: string;
}

export interface RuleBacktestRsiSignalSpec {
  indicatorFamily: 'rsi';
  period: number;
  lowerThreshold: number;
  upperThreshold: number;
  entryCondition: string;
  exitCondition: string;
}

export interface RuleBacktestIndicatorExecutionSpec {
  frequency?: string | null;
  signalTiming?: string | null;
  fillTiming?: string | null;
}

export interface RuleBacktestIndicatorPositionBehaviorSpec {
  direction?: string | null;
  entrySizing?: string | null;
  maxPositions?: number | null;
  pyramiding?: boolean | null;
}

export interface RuleBacktestIndicatorEndBehaviorSpec {
  policy?: string | null;
  priceBasis?: string | null;
}

export interface RuleBacktestIndicatorRiskControls {
  stopLossPct?: number | null;
  takeProfitPct?: number | null;
  trailingStopPct?: number | null;
}

export interface RuleBacktestMovingAverageCrossoverStrategySpec extends RuleBacktestStrategySpecBase {
  strategyType: 'moving_average_crossover';
  strategyFamily?: 'moving_average_crossover';
  signal?: RuleBacktestMovingAverageSignalSpec;
  execution?: RuleBacktestIndicatorExecutionSpec;
  positionBehavior?: RuleBacktestIndicatorPositionBehaviorSpec;
  endBehavior?: RuleBacktestIndicatorEndBehaviorSpec;
  riskControls?: RuleBacktestIndicatorRiskControls;
}

export interface RuleBacktestMacdCrossoverStrategySpec extends RuleBacktestStrategySpecBase {
  strategyType: 'macd_crossover';
  strategyFamily?: 'macd_crossover';
  signal?: RuleBacktestMacdSignalSpec;
  execution?: RuleBacktestIndicatorExecutionSpec;
  positionBehavior?: RuleBacktestIndicatorPositionBehaviorSpec;
  endBehavior?: RuleBacktestIndicatorEndBehaviorSpec;
  riskControls?: RuleBacktestIndicatorRiskControls;
}

export interface RuleBacktestRsiThresholdStrategySpec extends RuleBacktestStrategySpecBase {
  strategyType: 'rsi_threshold';
  strategyFamily?: 'rsi_threshold';
  signal?: RuleBacktestRsiSignalSpec;
  execution?: RuleBacktestIndicatorExecutionSpec;
  positionBehavior?: RuleBacktestIndicatorPositionBehaviorSpec;
  endBehavior?: RuleBacktestIndicatorEndBehaviorSpec;
  riskControls?: RuleBacktestIndicatorRiskControls;
}

export interface RuleBacktestGenericStrategySpec extends RuleBacktestStrategySpecBase {
  signal?: Record<string, unknown>;
  execution?: Record<string, unknown>;
  schedule?: Record<string, unknown>;
  entry?: Record<string, unknown>;
  exit?: Record<string, unknown>;
  positionBehavior?: Record<string, unknown>;
  endBehavior?: Record<string, unknown>;
  [key: string]: unknown;
}

export type RuleBacktestStrategySpec =
  | RuleBacktestPeriodicAccumulationStrategySpec
  | RuleBacktestMovingAverageCrossoverStrategySpec
  | RuleBacktestMacdCrossoverStrategySpec
  | RuleBacktestRsiThresholdStrategySpec
  | RuleBacktestGenericStrategySpec;

export interface RuleBacktestParseResponse {
  code?: string;
  strategyText: string;
  parsedStrategy: RuleBacktestParsedStrategy;
  normalizedStrategyFamily?: string;
  detectedStrategyFamily?: string | null;
  executable?: boolean;
  normalizationState?: string;
  assumptions?: Array<Record<string, unknown>>;
  assumptionGroups?: Array<Record<string, unknown>>;
  unsupportedReason?: string | null;
  unsupportedDetails?: Array<Record<string, unknown>>;
  unsupportedExtensions?: Array<Record<string, unknown>>;
  coreIntentSummary?: string | null;
  interpretationConfidence?: number | null;
  supportedPortionSummary?: string | null;
  rewriteSuggestions?: Array<Record<string, unknown>>;
  parseWarnings?: Array<Record<string, unknown>>;
  confidence: number;
  needsConfirmation: boolean;
  ambiguities: Array<Record<string, unknown>>;
  summary: Record<string, string>;
  maxLookback: number;
}

export interface RuleBacktestMonteCarloRobustnessConfig {
  simulationCount?: number;
  seed?: number;
  noiseScale?: number;
}

export interface RuleBacktestWalkForwardRobustnessConfig {
  trainWindow?: number;
  testWindow?: number;
  step?: number;
  maxWindows?: number;
}

export interface RuleBacktestRobustnessConfig {
  monteCarlo?: RuleBacktestMonteCarloRobustnessConfig;
  walkForward?: RuleBacktestWalkForwardRobustnessConfig;
}

export interface RuleBacktestRunRequest {
  code: string;
  strategyText: string;
  parsedStrategy?: RuleBacktestParsedStrategy;
  startDate?: string;
  endDate?: string;
  lookbackBars?: number;
  initialCapital?: number;
  feeBps?: number;
  slippageBps?: number;
  benchmarkMode?: string;
  benchmarkCode?: string;
  robustnessConfig?: RuleBacktestRobustnessConfig;
  confirmed?: boolean;
  waitForCompletion?: boolean;
}

export interface RuleBacktestParameterSweepBar {
  code?: string | null;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
}

export interface RuleBacktestParameterSweepRequest {
  code: string;
  strategyText: string;
  parsedStrategy: RuleBacktestParsedStrategy;
  startDate?: string;
  endDate?: string;
  lookbackBars: number;
  initialCapital: number;
  feeBps: number;
  slippageBps: number;
  executionModel?: Record<string, unknown> | null;
  confirmed: boolean;
  parameterGrid: Record<string, Array<string | number | boolean | null>>;
  maxCombinations: number;
  totalTimeoutSeconds?: number | null;
  bars: RuleBacktestParameterSweepBar[];
}

export interface RuleBacktestParameterSweepSummary {
  totalParameterSets?: number;
  runCount?: number;
  executedCount?: number;
  completedCount?: number;
  blockedCount?: number;
  failedCount?: number;
  skippedCount?: number;
}

export interface RuleBacktestParameterSweepLineageField {
  state?: string;
  value?: unknown;
  evidenceSource?: string;
  acceptedAsProfessionalEvidence?: boolean;
}

export interface RuleBacktestParameterSweepLineageReadiness {
  contractKind?: string;
  contractVersion?: string;
  readinessState?: string;
  diagnosticOnly?: boolean;
  blocked?: boolean;
  professionalReadinessApproved?: boolean;
  decisionGrade?: boolean;
  stateReasonCode?: string | null;
  code?: string;
  barBoundary?: {
    barSource?: string;
    localBars?: boolean;
    suppliedBarsToRunner?: boolean;
    barCount?: number;
    acceptedAsProviderAuthority?: boolean;
    providerCallsExecuted?: boolean;
    marketCacheAccessed?: boolean;
    storageMutation?: boolean;
  };
  lineageFields?: Record<string, RuleBacktestParameterSweepLineageField>;
  sourceAuthority?: {
    authorityStatus?: string;
    authoritySourceType?: string;
    authorityReasonCodes?: string[];
    authorityAllowed?: boolean;
    acceptedAsProviderAuthority?: boolean;
    acceptedAsReadinessEvidence?: boolean;
  };
  provenanceStatus?: {
    state?: string;
    providerHydrationExecuted?: boolean;
    dataIngestionExecuted?: boolean;
    storedReadbackAvailable?: boolean;
  };
  missingLineageFields?: string[];
  markers?: Record<string, { state?: string; marker?: boolean | string; reasonCode?: string | null }>;
  reproducibility?: {
    state?: string;
    inputShapeHashSha256?: string | null;
    gridDescriptorHashSha256?: string | null;
    requestBundleId?: string | null;
    inputOrdering?: unknown;
    gridRunOrdering?: unknown;
    runIdPolicy?: unknown;
    storedManifestAvailable?: boolean;
    acceptedAsProfessionalDatasetEvidence?: boolean;
  };
  parameterSetBoundary?: {
    sharedDatasetBoundaryForAllParameterSets?: boolean;
    perMemberStoredLineageAvailable?: boolean;
    parameterSetIds?: string[];
  };
  professionalReadiness?: Record<string, unknown>;
}

export interface RuleBacktestParameterSweepResponse {
  contractKind?: string;
  contractVersion?: string;
  state?: string;
  diagnosticOnly?: boolean;
  researchOnly?: boolean;
  notOptimizer?: boolean;
  winnerPromotion?: boolean;
  decisionGrade?: boolean;
  code?: string;
  strategyFamily?: string | null;
  engine?: Record<string, unknown>;
  executionAssumptions?: Record<string, unknown>;
  datasetMetadata?: Record<string, unknown>;
  datasetLineageReadiness?: RuleBacktestParameterSweepLineageReadiness;
  storage?: Record<string, unknown>;
  summary?: RuleBacktestParameterSweepSummary;
  parameterRows?: Array<Record<string, unknown>>;
  skippedRows?: Array<Record<string, unknown>>;
  blockedRows?: Array<Record<string, unknown>>;
  failedRows?: Array<Record<string, unknown>>;
  failClosedReasonCode?: string | null;
  failClosedDiagnostics?: Record<string, unknown>;
  parameterStabilitySurface?: unknown;
  reproducibilityMetadata?: {
    state?: string;
    plan?: Record<string, unknown>;
    requestBundleId?: string | null;
    gridDescriptorHashSha256?: string | null;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface RuleBacktestTradeItem {
  id?: number;
  runId?: number;
  tradeIndex?: number;
  code: string;
  side?: string | null;
  entrySignalDate?: string | null;
  exitSignalDate?: string | null;
  entryDate?: string | null;
  exitDate?: string | null;
  entryPrice?: number | null;
  exitPrice?: number | null;
  quantity?: number | null;
  grossPnl?: number | null;
  netPnl?: number | null;
  fees?: number | null;
  slippage?: number | null;
  entrySignal?: string | null;
  exitSignal?: string | null;
  entryTrigger?: string | null;
  exitTrigger?: string | null;
  entryReason?: string | null;
  exitReason?: string | null;
  signalReason?: string | null;
  returnPct?: number | null;
  holdingDays?: number | null;
  holdingBars?: number | null;
  holdingCalendarDays?: number | null;
  entryRule: RuleBacktestRuleNode | Record<string, unknown>;
  exitRule: RuleBacktestRuleNode | Record<string, unknown>;
  entryIndicators: Record<string, unknown>;
  exitIndicators: Record<string, unknown>;
  entryFillBasis?: string | null;
  exitFillBasis?: string | null;
  signalPriceBasis?: string | null;
  priceBasis?: string | null;
  feeBps?: number | null;
  slippageBps?: number | null;
  entryFeeAmount?: number | null;
  exitFeeAmount?: number | null;
  entrySlippageAmount?: number | null;
  exitSlippageAmount?: number | null;
  notes?: string | null;
}

export interface RuleBacktestEquityPointItem {
  date?: string;
  equity?: number;
  cumulativeReturnPct?: number;
  drawdownPct?: number;
  close?: number | null;
  signalSummary?: string | null;
  targetPosition?: number | null;
  executedAction?: string | null;
  fillPrice?: number | null;
  sharesHeld?: number | null;
  cash?: number | null;
  holdingsValue?: number | null;
  totalPortfolioValue?: number | null;
  positionState?: string | null;
  exposurePct?: number | null;
  feeAmount?: number | null;
  slippageAmount?: number | null;
  notes?: string | null;
}

export interface RuleBacktestBenchmarkPointItem {
  date?: string;
  close?: number;
  normalizedValue?: number;
  cumulativeReturnPct?: number;
}

export interface RuleBacktestBenchmarkSummary {
  label?: string;
  code?: string | null;
  method?: string;
  requestedMode?: string | null;
  resolvedMode?: string | null;
  normalizedBase?: number;
  priceBasis?: string;
  startDate?: string | null;
  endDate?: string | null;
  startPrice?: number | null;
  endPrice?: number | null;
  returnPct?: number | null;
  unavailableReason?: string | null;
  autoResolved?: boolean;
  fallbackUsed?: boolean;
}

export interface RuleBacktestExecutionTraceRowItem {
  date?: string | null;
  symbolClose?: number | null;
  benchmarkClose?: number | null;
  signalSummary?: string | null;
  eventType?: string | null;
  action?: string | null;
  actionDisplay?: string | null;
  fillPrice?: number | null;
  shares?: number | null;
  cash?: number | null;
  holdingsValue?: number | null;
  totalPortfolioValue?: number | null;
  dailyPnl?: number | null;
  dailyReturn?: number | null;
  cumulativeReturn?: number | null;
  benchmarkCumulativeReturn?: number | null;
  buyHoldCumulativeReturn?: number | null;
  position?: number | null;
  fees?: number | null;
  slippage?: number | null;
  notes?: string | null;
  unavailableReason?: string | null;
  assumptionsDefaults?: string | null;
  fallback?: string | null;
}

export interface RuleBacktestExecutionTraceAssumptionsDefaults {
  items?: Array<Record<string, unknown>>;
  summaryText?: string | null;
}

export interface RuleBacktestExecutionTraceFallback {
  runFallback?: boolean;
  traceRebuilt?: boolean;
  note?: string | null;
}

export interface RuleBacktestExecutionTracePayload {
  source?: string | null;
  rows?: RuleBacktestExecutionTraceRowItem[];
  executionModel?: RuleBacktestExecutionModel;
  executionAssumptions?: AssumptionMap;
  assumptionsDefaults?: RuleBacktestExecutionTraceAssumptionsDefaults;
  fallback?: RuleBacktestExecutionTraceFallback;
}

export interface RuleBacktestDailyReturnPointItem {
  date?: string;
  equity?: number;
  dailyReturnPct?: number;
  dailyPnl?: number;
}

export interface RuleBacktestExposurePointItem {
  date?: string;
  exposure?: number;
  positionState?: string;
  executedAction?: string | null;
  fillPrice?: number | null;
}

export interface RuleBacktestAuditRowItem {
  date?: string;
  symbolClose?: number | null;
  benchmarkClose?: number | null;
  position?: number | null;
  shares?: number | null;
  dailyReturn?: number | null;
  cumulativeReturn?: number | null;
  benchmarkCumulativeReturn?: number | null;
  buyHoldCumulativeReturn?: number | null;
  action?: string | null;
  signalSummary?: string | null;
  drawdownPct?: number | null;
  positionState?: string | null;
  fees?: number | null;
  slippage?: number | null;
  notes?: string | null;
  unavailableReason?: string | null;
  targetPosition?: number | null;
  executedAction?: string | null;
  fillPrice?: number | null;
  sharesHeld?: number | null;
  cash?: number | null;
  holdingsValue?: number | null;
  totalPortfolioValue?: number | null;
  exposurePct?: number | null;
  dailyPnl?: number | null;
  dailyReturnPct?: number | null;
  cumulativeStrategyReturnPct?: number | null;
  cumulativeBenchmarkReturnPct?: number | null;
  cumulativeBuyAndHoldReturnPct?: number | null;
}

export interface RuleBacktestCompareRunMetadata {
  id: number;
  code?: string | null;
  status?: string | null;
  runAt?: string | null;
  completedAt?: string | null;
  timeframe?: string | null;
  startDate?: string | null;
  endDate?: string | null;
  periodStart?: string | null;
  periodEnd?: string | null;
  lookbackBars?: number | null;
  initialCapital?: number | null;
  feeBps?: number | null;
  slippageBps?: number | null;
}

export interface RuleBacktestCompareRunMetrics {
  tradeCount?: number | null;
  winCount?: number | null;
  lossCount?: number | null;
  totalReturnPct?: number | null;
  annualizedReturnPct?: number | null;
  benchmarkReturnPct?: number | null;
  excessReturnVsBenchmarkPct?: number | null;
  buyAndHoldReturnPct?: number | null;
  excessReturnVsBuyAndHoldPct?: number | null;
  winRatePct?: number | null;
  avgTradeReturnPct?: number | null;
  maxDrawdownPct?: number | null;
  avgHoldingDays?: number | null;
  avgHoldingBars?: number | null;
  avgHoldingCalendarDays?: number | null;
  finalEquity?: number | null;
}

export interface RuleBacktestCompareRunBenchmark {
  mode?: string | null;
  code?: string | null;
  returnPct?: number | null;
}

export interface RuleBacktestCompareUnavailableRun {
  runId: number;
  reason: string;
}

export interface RuleBacktestCompareRunItem {
  metadata: RuleBacktestCompareRunMetadata;
  parsedStrategy?: Partial<RuleBacktestParsedStrategy>;
  metrics?: RuleBacktestCompareRunMetrics;
  benchmark?: RuleBacktestCompareRunBenchmark;
  resultAuthority?: Record<string, unknown>;
}

export interface RuleBacktestCompareSummaryBaseline {
  runId: number;
  selectionRule: string;
  code?: string | null;
  timeframe?: string | null;
  startDate?: string | null;
  endDate?: string | null;
  strategyFamily?: string | null;
  strategyType?: string | null;
}

export interface RuleBacktestCompareSummaryDateRange {
  runId: number;
  startDate?: string | null;
  endDate?: string | null;
}

export interface RuleBacktestCompareSummaryContext {
  codeValues: string[];
  timeframeValues: string[];
  strategyFamilyValues: string[];
  strategyTypeValues: string[];
  dateRanges: RuleBacktestCompareSummaryDateRange[];
  allSameCode: boolean;
  allSameTimeframe: boolean;
  allSameDateRange: boolean;
}

export interface RuleBacktestCompareMetricDeltaItem {
  runId: number;
  value?: number | null;
  deltaVsBaseline?: number | null;
}

export interface RuleBacktestCompareMetricDelta {
  label: string;
  state: string;
  baselineRunId: number;
  baselineValue?: number | null;
  availableRunIds: number[];
  unavailableRunIds: number[];
  deltas: RuleBacktestCompareMetricDeltaItem[];
}

export interface RuleBacktestCompareSummary {
  baseline: RuleBacktestCompareSummaryBaseline;
  context: RuleBacktestCompareSummaryContext;
  metricDeltas: Record<string, RuleBacktestCompareMetricDelta>;
}

export interface RuleBacktestComparePeriodBoundsItem {
  runId: number;
  periodStart?: string | null;
  periodEnd?: string | null;
  availability: string;
}

export interface RuleBacktestComparePeriodPair {
  runId: number;
  relationship: string;
  state: string;
  meaningfullyComparable?: boolean;
  overlapStart?: string | null;
  overlapEnd?: string | null;
  overlapDays?: number | null;
  gapDays?: number | null;
  diagnostics: string[];
}

export interface RuleBacktestComparePeriodComparison {
  baselineRunId: number;
  selectionRule: string;
  relationship: string;
  state: string;
  meaningfullyComparable?: boolean;
  periodBounds: RuleBacktestComparePeriodBoundsItem[];
  pairs: RuleBacktestComparePeriodPair[];
  diagnostics: string[];
}

export interface RuleBacktestCompareParameterValueItem {
  runId: number;
  value: unknown;
}

export interface RuleBacktestCompareParameterDetail {
  state: string;
  availableRunIds?: number[];
  unavailableRunIds?: number[];
  values: RuleBacktestCompareParameterValueItem[];
}

export interface RuleBacktestCompareParameterComparison {
  state: string;
  strategyFamilyValues: string[];
  strategyTypeValues: string[];
  sharedParameterKeys: string[];
  differingParameterKeys: string[];
  missingParameterKeys: string[];
  sharedParameters: Record<string, unknown>;
  differingParameters: Record<string, RuleBacktestCompareParameterDetail>;
  missingParameters: Record<string, RuleBacktestCompareParameterDetail>;
}

export interface RuleBacktestCompareMarketCodeRunItem {
  runId: number;
  code?: string | null;
  normalizedCode?: string | null;
  market?: string | null;
  availability: string;
  diagnostics: string[];
}

export interface RuleBacktestCompareMarketCodePair {
  runId: number;
  relationship: string;
  state: string;
  directlyComparable?: boolean;
  baselineCode?: string | null;
  candidateCode?: string | null;
  baselineMarket?: string | null;
  candidateMarket?: string | null;
  diagnostics: string[];
}

export interface RuleBacktestCompareMarketCodeComparison {
  baselineRunId: number;
  selectionRule: string;
  relationship: string;
  state: string;
  directlyComparable?: boolean;
  runs?: RuleBacktestCompareMarketCodeRunItem[];
  pairs?: RuleBacktestCompareMarketCodePair[];
  diagnostics: string[];
}

export interface RuleBacktestCompareRobustnessDimension {
  state: string;
  sourceState?: string | null;
  relationship?: string | null;
  directlyComparable?: boolean | null;
  meaningfullyComparable?: boolean | null;
  comparableMetricKeys?: string[];
  partialMetricKeys?: string[];
  unavailableMetricKeys?: string[];
  sharedParameterKeys?: string[];
  differingParameterKeys?: string[];
  missingParameterKeys?: string[];
  diagnostics: string[];
}

export interface RuleBacktestCompareRobustnessSummary {
  baselineRunId: number;
  selectionRule: string;
  overallState: string;
  directlyComparable?: boolean;
  alignedDimensions: string[];
  partialDimensions: string[];
  divergentDimensions: string[];
  unavailableDimensions: string[];
  dimensions: Record<string, RuleBacktestCompareRobustnessDimension>;
  diagnostics: string[];
}

export interface RuleBacktestCompareProfileFlags {
  sameCode?: boolean;
  sameMarket?: boolean;
  crossMarket?: boolean;
  sameStrategyFamily?: boolean;
  parameterDifferencesPresent?: boolean;
  periodDifferencesPresent?: boolean;
}

export interface RuleBacktestCompareProfileSummary {
  baselineRunId: number;
  selectionRule: string;
  primaryProfile: string;
  alignedDimensions: string[];
  drivingDimensions: string[];
  dimensionFlags: RuleBacktestCompareProfileFlags;
  diagnostics: string[];
}

export interface RuleBacktestCompareHighlightItem {
  metric: string;
  preference: string;
  state: string;
  winnerRunIds: number[];
  winnerValue?: number | null;
  availableRunIds: number[];
  candidateCount: number;
  diagnostics: string[];
}

export interface RuleBacktestCompareHighlightsSummary {
  baselineRunId: number;
  selectionRule: string;
  primaryProfile: string;
  overallContextState: string;
  highlights: Record<string, RuleBacktestCompareHighlightItem>;
  diagnostics: string[];
}

export interface RuleBacktestCompareHeatmapProjectionAuthority {
  projectionBasis?: string | null;
  comparisonSource?: string | null;
  executionMode?: string | null;
  executionCount?: number | null;
  providerCallsExecuted?: boolean | null;
  comparePayloadReused?: boolean | null;
  authorityScope?: string | null;
}

export interface RuleBacktestCompareHeatmapProjectionAxis {
  axisKey: string;
  axisLabel?: string | null;
  valueType?: string | null;
  values: Array<string | number | boolean | null>;
}

export interface RuleBacktestCompareHeatmapProjectionMetricValue {
  state?: string | null;
  value?: number | null;
}

export interface RuleBacktestCompareHeatmapProjectionCell {
  xValue?: string | number | boolean | null;
  yValue?: string | number | boolean | null;
  availabilityState: string;
  sourceRunIds: number[];
  metrics?: Record<string, RuleBacktestCompareHeatmapProjectionMetricValue>;
}

export interface RuleBacktestCompareHeatmapProjection {
  contractKind?: string | null;
  contractVersion?: string | null;
  source: string;
  readMode: string;
  authority?: RuleBacktestCompareHeatmapProjectionAuthority | null;
  requestedCompareRunIds?: number[];
  resolvedCompareRunIds?: number[];
  sourceRunIds?: number[];
  missingRunIds?: number[];
  axes: {
    x: RuleBacktestCompareHeatmapProjectionAxis;
    y: RuleBacktestCompareHeatmapProjectionAxis;
  };
  metricKeys: string[];
  cellAvailabilityStates: string[];
  cells: RuleBacktestCompareHeatmapProjectionCell[];
}

export interface RuleBacktestParameterStabilityEvidenceCoverage {
  requestedRunCount?: number | null;
  resolvedRunCount?: number | null;
  compatibleRunCount?: number | null;
  missingRunCount?: number | null;
  skippedRunCount?: number | null;
  compatibleRunIds?: number[];
  missingRunIds?: number[];
  skippedRunIds?: number[];
}

export interface RuleBacktestParameterStabilityEvidenceAuthority {
  inputMode?: string | null;
  executionCount?: number | null;
  strategyExecutionCount?: number | null;
  providerCallsExecuted?: boolean | null;
  engineMathChanged?: boolean | null;
  strategyParametersMutated?: boolean | null;
  [key: string]: unknown;
}

export interface RuleBacktestParameterStabilityEvidence {
  contractKind?: string | null;
  contractVersion?: string | null;
  state?: string | null;
  source?: string | null;
  readMode?: string | null;
  diagnosticOnly?: boolean | null;
  decisionGrade?: boolean | null;
  parameterKeys?: string[];
  parameterSetCount?: number | null;
  metricKeys?: string[];
  metricDispersion?: Record<string, Record<string, unknown>>;
  metricMissingCounts?: Record<string, number>;
  compatibleRunCoverage?: RuleBacktestParameterStabilityEvidenceCoverage | null;
  skippedRunDiagnostics?: Array<Record<string, unknown>>;
  missingRunDiagnostics?: Array<Record<string, unknown>>;
  authority?: RuleBacktestParameterStabilityEvidenceAuthority | null;
  [key: string]: unknown;
}

export interface RuleBacktestCompareResponse {
  comparisonSource: string;
  readMode: string;
  requestedRunIds: number[];
  resolvedRunIds: number[];
  comparableRunIds: number[];
  missingRunIds: number[];
  unavailableRuns: RuleBacktestCompareUnavailableRun[];
  fieldGroups: string[];
  marketCodeComparison?: RuleBacktestCompareMarketCodeComparison | null;
  periodComparison?: RuleBacktestComparePeriodComparison | null;
  comparisonSummary?: RuleBacktestCompareSummary | null;
  robustnessSummary?: RuleBacktestCompareRobustnessSummary | null;
  comparisonProfile?: RuleBacktestCompareProfileSummary | null;
  comparisonHighlights?: RuleBacktestCompareHighlightsSummary | null;
  parameterComparison?: RuleBacktestCompareParameterComparison | null;
  heatmapProjection?: RuleBacktestCompareHeatmapProjection | null;
  parameterStabilityEvidence?: RuleBacktestParameterStabilityEvidence | null;
  items: RuleBacktestCompareRunItem[];
}

export interface RuleBacktestDrawdownRegimeBucketSummary {
  count?: number | null;
  sharePct?: number | null;
  avgDepthPct?: number | null;
  worstDepthPct?: number | null;
}

export interface RuleBacktestDrawdownRegimeContributionSummary {
  count?: number | null;
  sharePct?: number | null;
}

export interface RuleBacktestDrawdownRegimeAttribution {
  version?: string | null;
  source?: string | null;
  state?: string | null;
  bucketCounts?: Record<string, RuleBacktestDrawdownRegimeBucketSummary> | null;
  contributionSummaries?: {
    classifiedRows?: RuleBacktestDrawdownRegimeContributionSummary | null;
    missingRows?: RuleBacktestDrawdownRegimeContributionSummary | null;
    causalityNote?: string | null;
  } | null;
  unavailableReason?: string | null;
}

export interface RuleBacktestRunSummary {
  drawdownRegimeAttribution?: RuleBacktestDrawdownRegimeAttribution | null;
  [key: string]: unknown;
}

export interface RuleBacktestRunResponse extends BacktestResponseContractFields {
  id: number;
  code: string;
  strategyText: string;
  parsedStrategy: RuleBacktestParsedStrategy;
  strategyHash: string;
  timeframe: string;
  startDate?: string | null;
  endDate?: string | null;
  periodStart?: string | null;
  periodEnd?: string | null;
  lookbackBars: number;
  initialCapital: number;
  feeBps: number;
  slippageBps: number;
  parsedConfidence?: number | null;
  needsConfirmation: boolean;
  warnings: Array<Record<string, unknown>>;
  runAt?: string | null;
  completedAt?: string | null;
  status: string;
  statusMessage?: string | null;
  statusHistory: StatusHistoryItem[];
  noResultReason?: string | null;
  noResultMessage?: string | null;
  tradeCount: number;
  winCount: number;
  lossCount: number;
  totalReturnPct?: number | null;
  annualizedReturnPct?: number | null;
  sharpeRatio?: number | null;
  benchmarkMode?: string | null;
  benchmarkCode?: string | null;
  benchmarkReturnPct?: number | null;
  excessReturnVsBenchmarkPct?: number | null;
  buyAndHoldReturnPct?: number | null;
  excessReturnVsBuyAndHoldPct?: number | null;
  winRatePct?: number | null;
  avgTradeReturnPct?: number | null;
  maxDrawdownPct?: number | null;
  avgHoldingDays?: number | null;
  avgHoldingBars?: number | null;
  avgHoldingCalendarDays?: number | null;
  finalEquity?: number | null;
  summary: RuleBacktestRunSummary;
  dataQuality?: BacktestDataQuality;
  historicalOhlcvReadiness?: BacktestHistoricalOhlcvReadiness;
  robustnessAnalysis?: Record<string, unknown>;
  executionModel?: RuleBacktestExecutionModel;
  executionAssumptions: AssumptionMap;
  benchmarkCurve: RuleBacktestBenchmarkPointItem[];
  benchmarkSummary: RuleBacktestBenchmarkSummary;
  buyAndHoldCurve?: RuleBacktestBenchmarkPointItem[];
  buyAndHoldSummary?: RuleBacktestBenchmarkSummary;
  auditRows?: RuleBacktestAuditRowItem[];
  dailyReturnSeries: RuleBacktestDailyReturnPointItem[];
  exposureCurve: RuleBacktestExposurePointItem[];
  aiSummary?: string | null;
  equityCurve: RuleBacktestEquityPointItem[];
  trades: RuleBacktestTradeItem[];
  executionTrace?: RuleBacktestExecutionTracePayload | null;
}

export type RuleBacktestHistoryItem = RuleBacktestRunResponse;

export interface RuleBacktestStatusResponse extends BacktestResponseContractFields {
  id: number;
  code: string;
  status: string;
  statusMessage?: string | null;
  statusHistory: StatusHistoryItem[];
  runAt?: string | null;
  completedAt?: string | null;
  noResultReason?: string | null;
  noResultMessage?: string | null;
  tradeCount: number;
  parsedConfidence?: number | null;
  needsConfirmation: boolean;
}

export type RuleBacktestCancelResponse = RuleBacktestStatusResponse;

export interface RuleBacktestHistoryResponse {
  total: number;
  page: number;
  limit: number;
  items: RuleBacktestHistoryItem[];
}

export interface RuleBacktestSupportExportIndexItem {
  key: string;
  available: boolean;
  availabilityReason: string;
  format: string;
  mediaType: string;
  deliveryMode: string;
  endpointPath?: string | null;
  payloadClass: string;
}

export interface RuleBacktestSupportExportIndexResponse {
  runId: number;
  status: string;
  exports: RuleBacktestSupportExportIndexItem[];
}

export interface RuleBacktestSupportBundleManifestResponse {
  manifestVersion: string;
  manifestKind: string;
  run: Record<string, unknown>;
  runTiming: Record<string, unknown>;
  runDiagnostics: Record<string, unknown>;
  artifactAvailability: Record<string, unknown>;
  readbackIntegrity: Record<string, unknown>;
  resultAuthority: Record<string, unknown>;
  artifactCounts: Record<string, number>;
}

export interface RuleBacktestSupportBundleReproducibilityManifestResponse {
  manifestVersion: string;
  manifestKind: string;
  run: Record<string, unknown>;
  runTiming: Record<string, unknown>;
  runDiagnostics: Record<string, unknown>;
  artifactAvailability: Record<string, unknown>;
  readbackIntegrity: Record<string, unknown>;
  executionAssumptionsFingerprint: Record<string, unknown>;
  resultAuthority: Record<string, unknown>;
}

export interface RuleBacktestRobustnessEvidenceExportResponse {
  [key: string]: unknown;
}

export interface RuleBacktestExecutionTraceExportResponse {
  version?: string | null;
  source?: string | null;
  completeness?: string | null;
  missingFields: string[];
  traceRows: RuleBacktestExecutionTraceRowItem[];
  assumptions: Record<string, unknown>;
  executionModel: RuleBacktestExecutionModel;
  executionAssumptions: AssumptionMap;
  benchmarkSummary: RuleBacktestBenchmarkSummary;
  fallback: RuleBacktestExecutionTraceFallback;
}

// ============ Result Item ============

export interface BacktestResultItem {
  analysisHistoryId: number;
  code: string;
  analysisDate?: string | null;
  evalWindowDays: number;
  evaluationWindowTradingBars?: number | null;
  engineVersion: string;
  evalStatus: string;
  evaluatedAt?: string | null;
  operationAdvice?: string | null;
  positionRecommendation?: string | null;
  startPrice?: number | null;
  endClose?: number | null;
  maxHigh?: number | null;
  minLow?: number | null;
  stockReturnPct?: number | null;
  directionExpected?: string | null;
  directionCorrect?: boolean | null;
  outcome?: string | null;
  stopLoss?: number | null;
  takeProfit?: number | null;
  hitStopLoss?: boolean | null;
  hitTakeProfit?: boolean | null;
  firstHit?: string | null;
  firstHitDate?: string | null;
  firstHitTradingDays?: number | null;
  simulatedEntryPrice?: number | null;
  simulatedExitPrice?: number | null;
  simulatedExitReason?: string | null;
  simulatedReturnPct?: number | null;
  marketDataSources: string[];
  dataQuality?: BacktestDataQuality;
  executionAssumptions: AssumptionMap;
}

export interface BacktestResultsResponse {
  total: number;
  page: number;
  limit: number;
  items: BacktestResultItem[];
}

// ============ Performance Metrics ============

export interface PerformanceMetrics {
  scope: string;
  code?: string | null;
  evalWindowDays: number;
  evaluationWindowTradingBars?: number | null;
  engineVersion: string;
  computedAt?: string | null;
  totalEvaluations: number;
  completedCount: number;
  insufficientCount: number;
  longCount: number;
  cashCount: number;
  winCount: number;
  lossCount: number;
  neutralCount: number;
  directionAccuracyPct?: number | null;
  winRatePct?: number | null;
  neutralRatePct?: number | null;
  avgStockReturnPct?: number | null;
  avgSimulatedReturnPct?: number | null;
  stopLossTriggerRate?: number | null;
  takeProfitTriggerRate?: number | null;
  ambiguousRate?: number | null;
  avgDaysToFirstHit?: number | null;
  adviceBreakdown: Record<string, unknown>;
  diagnostics: Record<string, unknown>;
  evaluationMode?: string | null;
  requestedMode?: string | null;
  resolvedSource?: string | null;
  fallbackUsed?: boolean | null;
  executionAssumptions: AssumptionMap;
}
