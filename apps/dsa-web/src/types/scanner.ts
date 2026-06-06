import type { SourceProvenanceSummary } from './analysis';
import type { ResearchReadinessV1, ScannerContextFrame } from './researchReadiness';

export interface ScannerRunRequest {
  market?: 'cn' | 'us' | 'hk';
  profile?: string;
  shortlistSize?: number;
  universeLimit?: number;
  detailLimit?: number;
  universeType?: 'default' | 'theme' | 'symbols';
  themeId?: string | null;
  symbols?: string[];
}

export interface ScannerTheme {
  id: string;
  labelZh: string;
  labelEn: string;
  market: 'cn' | 'us' | 'hk';
  description: string;
  symbols: string[];
  aliases: string[];
  tags: string[];
  source: string;
  version: string;
  isSeedList: boolean;
  requiresManualMaintenance: boolean;
  criteriaPrompt?: string | null;
  generatedAt?: string | null;
  updatedAt?: string | null;
  refreshPolicy?: string | null;
  aiMetadata?: Record<string, unknown>;
}

export interface ScannerThemesResponse {
  items: ScannerTheme[];
}

export interface ScannerThemeSuggestion {
  symbol: string;
  reason: string;
  confidence: number;
  evidence: string[];
}

export interface ScannerThemeGenerateRequest {
  id: string;
  label: string;
  market: 'cn' | 'us' | 'hk';
  prompt: string;
  manualSymbols?: string[];
}

export interface ScannerThemeGenerationResponse {
  theme: ScannerTheme;
  suggestions: ScannerThemeSuggestion[];
  message: string;
}

export interface ScannerLabeledValue {
  label: string;
  value: string;
}

export interface ScannerNotificationResult {
  attempted: boolean;
  status: string;
  success?: boolean | null;
  channels: string[];
  message?: string | null;
  reportPath?: string | null;
  sentAt?: string | null;
}

export interface ScannerAiInterpretation {
  available: boolean;
  status: string;
  summary?: string | null;
  opportunityType?: string | null;
  riskInterpretation?: string | null;
  watchPlan?: string | null;
  reviewCommentary?: string | null;
  provider?: string | null;
  model?: string | null;
  generatedAt?: string | null;
  message?: string | null;
}

export interface ScannerCandidateOutcome {
  reviewStatus: string;
  outcomeLabel: string;
  thesisMatch: string;
  reviewWindowDays: number;
  anchorDate?: string | null;
  windowEndDate?: string | null;
  sameDayCloseReturnPct?: number | null;
  nextDayReturnPct?: number | null;
  reviewWindowReturnPct?: number | null;
  maxFavorableMovePct?: number | null;
  maxAdverseMovePct?: number | null;
  benchmarkCode?: string | null;
  benchmarkReturnPct?: number | null;
  outperformedBenchmark?: boolean | null;
}

export interface ScannerReviewSummary {
  available: boolean;
  reviewWindowDays: number;
  reviewStatus: string;
  candidateCount: number;
  reviewedCount: number;
  pendingCount: number;
  hitRatePct?: number | null;
  outperformRatePct?: number | null;
  avgSameDayCloseReturnPct?: number | null;
  avgReviewWindowReturnPct?: number | null;
  avgMaxFavorableMovePct?: number | null;
  avgMaxAdverseMovePct?: number | null;
  strongCount: number;
  mixedCount: number;
  weakCount: number;
  bestSymbol?: string | null;
  bestReturnPct?: number | null;
  weakestSymbol?: string | null;
  weakestReturnPct?: number | null;
}

export interface ScannerWatchlistDeltaItem {
  symbol: string;
  name?: string | null;
  currentRank?: number | null;
  previousRank?: number | null;
  rankDelta?: number | null;
}

export interface ScannerWatchlistComparison {
  available: boolean;
  previousRunId?: number | null;
  previousWatchlistDate?: string | null;
  newCount: number;
  retainedCount: number;
  droppedCount: number;
  newSymbols: ScannerWatchlistDeltaItem[];
  retainedSymbols: ScannerWatchlistDeltaItem[];
  droppedSymbols: ScannerWatchlistDeltaItem[];
}

export interface ScannerQualitySummary {
  available: boolean;
  reviewWindowDays: number;
  benchmarkCode?: string | null;
  runCount: number;
  reviewedRunCount: number;
  reviewedCandidateCount: number;
  reviewCoveragePct?: number | null;
  avgCandidatesPerRun?: number | null;
  avgShortlistReturnPct?: number | null;
  positiveRunRatePct?: number | null;
  hitRatePct?: number | null;
  outperformRatePct?: number | null;
  positiveCandidateAvgScore?: number | null;
  negativeCandidateAvgScore?: number | null;
}

export interface ScannerCoverageReason {
  reason: string;
  label?: string | null;
  count: number;
}

export interface ScannerCoverageSummary {
  inputUniverseSize: number;
  eligibleAfterUniverseFetch: number;
  eligibleAfterLiquidityFilter: number;
  eligibleAfterDataAvailabilityFilter: number;
  rankedCandidateCount: number;
  shortlistedCount: number;
  excludedTotal: number;
  excludedByReason: ScannerCoverageReason[];
  likelyBottleneck?: string | null;
  likelyBottleneckLabel?: string | null;
}

export interface ScannerProviderDiagnostics {
  configuredPrimaryProvider?: string | null;
  quoteSourceUsed?: string | null;
  snapshotSourceUsed?: string | null;
  historySourceUsed?: string | null;
  providersUsed: string[];
  fallbackOccurred: boolean;
  fallbackCount: number;
  providerFailureCount: number;
  missingDataSymbolCount: number;
  providerWarnings: string[];
}

export interface ScannerSourceConfidence {
  source?: string | null;
  sourceLabel?: string | null;
  sourceType?: string | null;
  asOf?: string | null;
  freshness?: string | null;
  isFallback?: boolean | null;
  isStale?: boolean | null;
  isPartial?: boolean | null;
  isSynthetic?: boolean | null;
  isUnavailable?: boolean | null;
  confidenceWeight?: number | null;
  coverage?: number | null;
  degradationReason?: string | null;
  capReason?: string | null;
  scoreContributionAllowed?: boolean | null;
  observationOnly?: boolean | null;
  proxyOnly?: boolean | null;
}

export interface ScannerScoreExplainability {
  rawScore?: number | null;
  finalScore?: number | null;
  scoreDelta?: number | null;
  scoreCap?: number | null;
  capReason?: string | null;
  degradationReason?: string | null;
  scoreConfidence?: number | null;
  evidenceCoverage?: number | null;
  capApplied?: boolean | null;
  scoreGradeAllowed?: boolean | null;
  missingEvidence?: string[];
  reasonCodes?: string[];
  sourceConfidence?: ScannerSourceConfidence | null;
}

export interface ScannerFreshnessDetail {
  quoteState?: string | null;
  historyState?: string | null;
  latestTradeDate?: string | null;
}

export interface ScannerProviderObservation {
  observationOnly?: boolean | null;
  scoreContributionAllowed?: boolean | null;
  entries?: Array<Record<string, unknown>>;
}

export interface ScannerEvidencePacket {
  symbol?: string | null;
  market?: string | null;
  rank?: number | null;
  score?: number | null;
  rawScore?: number | null;
  finalScore?: number | null;
  scoreConfidence?: number | null;
  evidenceCoverage?: number | null;
  capReason?: string | null;
  degradationReason?: string | null;
  evidenceVersion?: string | null;
  runId?: number | null;
  freshnessState?: string | null;
  dataQualityState?: string | null;
  freshnessDetail?: ScannerFreshnessDetail | null;
  missingEvidence?: string[];
  userFacingLabels?: string[];
  warningFlags?: string[];
  sourceConfidence?: ScannerSourceConfidence | null;
  providerObservation?: ScannerProviderObservation | null;
  [key: string]: unknown;
}

export interface InvestorSignalAssetPressure {
  asset?: string | null;
  pressure?: string | null;
  freshness?: string | null;
  isFallback?: boolean;
  isStale?: boolean;
  isPartial?: boolean;
}

export interface InvestorSignalContract {
  contractVersion?: string;
  diagnosticOnly?: boolean;
  observationOnly?: boolean;
  authorityGrant?: boolean;
  decisionGrade?: boolean;
  sourceAuthorityAllowed?: boolean;
  scoreContributionAllowed?: boolean;
  marketRegime?: string | null;
  marketRegimeLabel?: string | null;
  capitalFlowRegime?: string | null;
  capitalFlowLabel?: string | null;
  themeFlowState?: string | null;
  themeFlowLabel?: string | null;
  confidenceLabel?: string | null;
  confidenceText?: string | null;
  freshness?: string | null;
  reasonCodes?: string[];
  contradictionCodes?: string[];
  confidence?: string | number | null;
  isFallback?: boolean;
  isStale?: boolean;
  isPartial?: boolean;
  likelyDestination?: string | null;
  sourceAssetPressure?: InvestorSignalAssetPressure[];
  contradictionSignals?: string[];
  explanation?: string | null;
  relativeStrengthEvidence?: string | null;
  breadthEvidence?: string | null;
}

export interface ScannerConsumerDiagnostics {
  status?: string | null;
  scoreGradeAllowed?: boolean | null;
  scoreConfidence?: number | null;
  capReason?: string | null;
  degradationReason?: string | null;
  dataQualityState?: string | null;
  freshnessState?: string | null;
  missingEvidence?: string[];
  userFacingLabels?: string[];
  warningFlags?: string[];
  sourceClass?: string | null;
  investorSignal?: InvestorSignalContract | null;
  [key: string]: unknown;
}

export interface ScannerRunDiagnostics {
  coverageSummary?: ScannerCoverageSummary;
  providerDiagnostics?: ScannerProviderDiagnostics;
  scoreExplainability?: ScannerScoreExplainability;
  evidencePacket?: ScannerEvidencePacket;
  universeSelection?: {
    universeType: string;
    themeId?: string | null;
    themeLabel?: string | null;
    requestedSymbolsCount: number;
    acceptedSymbolsCount: number;
    acceptedSymbols?: string[];
    rejectedSymbols: string[];
    universeNotes: string[];
  };
  [key: string]: unknown;
}

export type ScannerCandidateDiagnosticStatus = 'selected' | 'rejected' | 'data_failed' | 'skipped' | 'error' | 'evaluated';

export interface ScannerCandidateDiagnostic {
  symbol: string;
  name?: string | null;
  market?: string | null;
  rank?: number | null;
  status?: ScannerCandidateDiagnosticStatus;
  score?: number | null;
  provider?: string | null;
  reason?: string | null;
  failedRules?: string[];
  missingFields?: string[];
  metrics?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface ScannerThemeDiagnostics {
  id?: string | null;
  name?: string | null;
  universeCount?: number;
  symbols?: string[];
}

export interface ScannerSummaryDiagnostics {
  universeCount?: number;
  submittedCount?: number;
  evaluatedCount?: number;
  selectedCount?: number;
  rejectedCount?: number;
  dataFailedCount?: number;
  skippedCount?: number;
  errorCount?: number;
  limitedByResultCap?: boolean;
}

export interface ScannerCandidateEvidenceDomain {
  state?: string | null;
  observationOnly?: boolean | null;
  scoreGradeAllowed?: boolean | null;
}

export interface ScannerCandidateEvidenceFrame {
  contractVersion?: string | null;
  coverageState?: string | null;
  domains?: Record<string, ScannerCandidateEvidenceDomain> | null;
  coverage?: {
    availableCount?: number | null;
    partialCount?: number | null;
    observeOnlyCount?: number | null;
    missingCount?: number | null;
    totalCount?: number | null;
  } | null;
  noAdviceBoundary?: boolean | null;
  [key: string]: unknown;
}

export interface ScannerCandidateResearchSummaryTopDownRef {
  key?: string | null;
  state?: string | null;
  label?: string | null;
}

export interface ScannerCandidateResearchSummaryFrame {
  contractVersion?: string | null;
  frameState?: string | null;
  symbol?: string | null;
  rank?: number | null;
  scoreBand?: string | null;
  primaryResearchReason?: string | null;
  evidenceHighlights?: string[] | null;
  missingEvidence?: string[] | null;
  blockingReasons?: string[] | null;
  topDownContextRefs?: ScannerCandidateResearchSummaryTopDownRef[] | null;
  sourceAuthority?: string | null;
  freshness?: string | null;
  nextResearchStep?: string | null;
  noAdviceBoundary?: boolean | null;
  debugRef?: string | null;
  [key: string]: unknown;
}

export interface ScannerCandidate {
  symbol: string;
  name: string;
  companyName?: string | null;
  rank: number;
  score: number;
  rawScore?: number | null;
  finalScore?: number | null;
  qualityHint?: string | null;
  reasonSummary?: string | null;
  reasons: string[];
  keyMetrics: ScannerLabeledValue[];
  featureSignals: ScannerLabeledValue[];
  riskNotes: string[];
  watchContext: ScannerLabeledValue[];
  boards: string[];
  tags?: Array<{
    name: string;
    description: string;
    tone?: 'indigo' | 'emerald';
  }>;
  appearedInRecentRuns: number;
  lastTradeDate?: string | null;
  scanTimestamp?: string | null;
  aiInterpretation: ScannerAiInterpretation;
  realizedOutcome: ScannerCandidateOutcome;
  diagnostics: ScannerRunDiagnostics;
  consumerDiagnostics?: ScannerConsumerDiagnostics | null;
  candidateEvidenceFrame?: ScannerCandidateEvidenceFrame | null;
  candidateResearchReadiness?: ResearchReadinessV1 | null;
  candidateResearchSummaryFrame?: ScannerCandidateResearchSummaryFrame | null;
  candidateSourceProvenanceFrame?: SourceProvenanceSummary | null;
}

export interface ScannerRunDetail {
  id: number;
  market: string;
  profile: string;
  profileLabel?: string | null;
  status: string;
  runAt?: string | null;
  completedAt?: string | null;
  watchlistDate?: string | null;
  triggerMode?: string | null;
  universeName: string;
  shortlistSize: number;
  universeSize: number;
  preselectedSize: number;
  evaluatedSize: number;
  sourceSummary?: string | null;
  headline?: string | null;
  universeNotes: string[];
  scoringNotes: string[];
  universeType: string;
  themeId?: string | null;
  themeLabel?: string | null;
  requestedSymbolsCount: number;
  acceptedSymbolsCount: number;
  rejectedSymbols: string[];
  diagnostics: Record<string, unknown>;
  scannerContextFrame?: ScannerContextFrame | null;
  theme?: ScannerThemeDiagnostics;
  summary?: ScannerSummaryDiagnostics;
  selected?: ScannerCandidate[];
  candidates?: ScannerCandidateDiagnostic[];
  notification: ScannerNotificationResult;
  failureReason?: string | null;
  comparisonToPrevious: ScannerWatchlistComparison;
  reviewSummary: ScannerReviewSummary;
  shortlist: ScannerCandidate[];
}

export interface ScannerRunHistoryItem {
  id: number;
  market: string;
  profile: string;
  profileLabel?: string | null;
  status: string;
  runAt?: string | null;
  completedAt?: string | null;
  watchlistDate?: string | null;
  triggerMode?: string | null;
  universeName: string;
  shortlistSize: number;
  universeSize: number;
  preselectedSize: number;
  evaluatedSize: number;
  sourceSummary?: string | null;
  headline?: string | null;
  universeType: string;
  themeId?: string | null;
  themeLabel?: string | null;
  requestedSymbolsCount: number;
  acceptedSymbolsCount: number;
  rejectedSymbols: string[];
  topSymbols: string[];
  notificationStatus?: string | null;
  failureReason?: string | null;
  changeSummary: ScannerWatchlistComparison;
  reviewSummary: ScannerReviewSummary;
}

export interface ScannerRunHistoryResponse {
  total: number;
  page: number;
  limit: number;
  items: ScannerRunHistoryItem[];
}

export interface ScannerStrategySimulationWindow {
  lookbackDays: number;
  forwardDays: number;
  runCount: number;
}

export interface ScannerStrategySimulationSummary {
  historicalRuns: number;
  selectionEvents: number;
  avgSelectedPerRun?: number | null;
  hitRate?: number | null;
  avgForwardReturnPct?: number | null;
  medianForwardReturnPct?: number | null;
  avgBenchmarkReturnPct?: number | null;
  avgExcessReturnPct?: number | null;
  positiveSelectionRate?: number | null;
  bestSymbol?: string | null;
  worstSymbol?: string | null;
  dataCoverage?: number | null;
}

export interface ScannerStrategySimulationRun {
  runId: number;
  runAt?: string | null;
  selectedCount: number;
  rejectedCount: number;
  selectedSymbols: string[];
  avgForwardReturnPct?: number | null;
  benchmarkReturnPct?: number | null;
  excessReturnPct?: number | null;
}

export interface ScannerStrategySimulationSymbol {
  symbol: string;
  selectionCount: number;
  avgScore?: number | null;
  avgForwardReturnPct?: number | null;
  hitRate?: number | null;
  bestForwardReturnPct?: number | null;
  worstForwardReturnPct?: number | null;
}

export interface ScannerStrategySimulationResult {
  theme?: string | null;
  profile: string;
  market: string;
  window: ScannerStrategySimulationWindow;
  status: 'ready' | 'insufficient_history' | 'partial' | 'failed';
  summary: ScannerStrategySimulationSummary;
  runs: ScannerStrategySimulationRun[];
  symbols: ScannerStrategySimulationSymbol[];
  warnings: string[];
}

export interface ScannerOperationalRunSummary {
  id: number;
  watchlistDate?: string | null;
  triggerMode?: string | null;
  status: string;
  runAt?: string | null;
  headline?: string | null;
  shortlistSize: number;
  notificationStatus?: string | null;
  failureReason?: string | null;
}

export interface ScannerOperationalStatus {
  market: string;
  profile: string;
  profileLabel?: string | null;
  watchlistDate: string;
  todayTradingDay: boolean;
  scheduleEnabled: boolean;
  scheduleTime?: string | null;
  scheduleRunImmediately: boolean;
  notificationEnabled: boolean;
  todayWatchlist?: ScannerOperationalRunSummary | null;
  lastRun?: ScannerOperationalRunSummary | null;
  lastScheduledRun?: ScannerOperationalRunSummary | null;
  lastManualRun?: ScannerOperationalRunSummary | null;
  latestFailure?: ScannerOperationalRunSummary | null;
  qualitySummary: ScannerQualitySummary;
}
