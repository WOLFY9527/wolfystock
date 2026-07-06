import type { InvestorSignalContract } from './scanner';

export interface WatchlistScannerLineageV1 {
  contractVersion: 'scanner_watchlist_lineage_v1' | string;
  source: 'scanner';
  scannerRunId?: number | null;
  symbol: string;
  market: string;
  rankAtScan?: number | null;
  scoreAtScan?: number | null;
  scoreSnapshotKind: 'saved_at_add' | 'post_add_refresh';
  runProfile?: string | null;
  runCompletedAt?: string | null;
  watchlistAddedAt?: string | null;
  themeId?: string | null;
  universeType?: string | null;
  researchReason: string;
  researchNextStep: string;
  dataState: 'available' | 'limited' | 'observation_only' | 'insufficient' | 'updating' | 'unavailable' | string;
  freshnessLabel: string;
  noAdviceBoundary: boolean;
  observationOnly: boolean;
  scoreGradeAllowed: boolean;
}

export interface WatchlistScannerIntelligence {
  lastScore?: number | null;
  lastRank?: number | null;
  status?: 'selected' | 'preview' | 'rejected' | 'data_failed' | 'unknown' | string | null;
  theme?: string | null;
  themeLabel?: string | null;
  profile?: string | null;
  reason?: string | null;
  lastScannedAt?: string | null;
  investorSignal?: InvestorSignalContract | null;
  scannerLineageV1?: WatchlistScannerLineageV1 | null;
}

export interface WatchlistScoreStatusContext {
  scope?: string | null;
  freshMeans?: string | null;
  sourceFreshnessImplied?: boolean | null;
  sourceAuthorityImplied?: boolean | null;
}

export interface WatchlistCatalystExposure {
  id: string;
  symbol: string;
  market: string;
  category: string;
  title: string;
  summary: string;
  evidenceStatus: string;
  evidenceLabels?: string[] | null;
  asOf?: string | null;
  publishedAt?: string | null;
  timeframe?: string | null;
  reasonCodes?: string[] | null;
  observationOnly?: boolean | null;
  sourceAuthorityAllowed?: boolean | null;
  scoreContributionAllowed?: boolean | null;
  decisionGrade?: boolean | null;
  calendarClaimAllowed?: boolean | null;
}

export interface WatchlistStrategySimulationIntelligence {
  lookbackDays?: number | null;
  forwardDays?: number | null;
  avgForwardReturnPct?: number | null;
  hitRate?: number | null;
  avgExcessReturnPct?: number | null;
  selectionCount?: number | null;
  dataCoverage?: number | null;
  status?: 'ready' | 'partial' | 'insufficient_history' | 'unknown' | string | null;
}

export interface WatchlistBacktestIntelligence {
  lastResultId?: number | null;
  totalReturnPct?: number | null;
  maxDrawdownPct?: number | null;
  sharpe?: number | null;
  tradeCount?: number | null;
  testedAt?: string | null;
}

export interface WatchlistIntelligence {
  scanner?: WatchlistScannerIntelligence | null;
  strategySimulation?: WatchlistStrategySimulationIntelligence | null;
  backtest?: WatchlistBacktestIntelligence | null;
  catalystExposures?: WatchlistCatalystExposure[] | null;
}

export interface WatchlistRowResearchIdentity {
  name?: string | null;
  exchange?: string | null;
  sector?: string | null;
  industry?: string | null;
  canonicalSymbol?: string | null;
  displaySymbol?: string | null;
  displayName?: string | null;
  identityState?: string | null;
}

export interface WatchlistRowResearchQuote {
  state: 'available' | 'missing' | 'stale' | 'unknown' | string;
  price?: number | null;
  changePercent?: number | null;
  asOf?: string | null;
}

export interface WatchlistRowScannerLineage {
  runId?: number | null;
  rank?: number | null;
  score?: number | null;
  status?: string | null;
  lastScoredAt?: string | null;
}

export interface WatchlistRowResearchPacketResponse {
  symbol: string;
  market: string;
  identity: WatchlistRowResearchIdentity;
  savedItemSource: string;
  quote: WatchlistRowResearchQuote;
  scannerLineage: WatchlistRowScannerLineage;
  researchStatus: 'ready' | 'partial' | 'blocked' | 'unknown' | string;
  researchReadiness?: WatchlistResearchReadiness | null;
  missingData: string[];
  nextDataAction: string;
  observationOnly: true;
  noAdviceDisclosure: string;
}

export interface WatchlistSymbolIdentity {
  canonicalSymbol: string;
  displaySymbol: string;
  market: string;
  exchange?: string | null;
  displayName?: string | null;
  identityState: string;
}

export interface WatchlistResearchReadiness {
  contractVersion?: string | null;
  state: 'available' | 'partial' | 'stale' | 'unavailable' | 'pending' | 'unknown' | string;
  freshnessState: 'available' | 'partial' | 'stale' | 'unavailable' | 'pending' | 'unknown' | string;
  identityState: string;
  lastReviewedAt?: string | null;
  scoreFreshnessImplied?: boolean | null;
  sourceAuthorityImplied?: boolean | null;
}

export interface WatchlistItem {
  id: number;
  symbol: string;
  market: string;
  identity?: WatchlistSymbolIdentity | null;
  name?: string | null;
  source: string;
  createdNew?: boolean | null;
  duplicateOfId?: number | null;
  scannerRunId?: number | null;
  scannerRank?: number | null;
  scannerScore?: number | null;
  lastScoredAt?: string | null;
  scoreSource?: string | null;
  scoreProfile?: string | null;
  scoreReason?: string | null;
  scoreStatus?: string | null;
  scoreStatusContext?: WatchlistScoreStatusContext | null;
  scoreError?: string | null;
  researchReadiness?: WatchlistResearchReadiness | null;
  themeId?: string | null;
  universeType?: string | null;
  notes?: string | null;
  intelligence?: WatchlistIntelligence | null;
  rowResearchPacket?: WatchlistRowResearchPacketResponse | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface WatchlistItemListResponse {
  items: WatchlistItem[];
}

export interface WatchlistItemCreateRequest {
  symbol: string;
  market: string;
  name?: string;
  source?: 'scanner';
  scannerRunId?: number;
  scannerRank?: number;
  scannerScore?: number;
  themeId?: string | null;
  universeType?: string | null;
  notes?: string | null;
}

export interface WatchlistDeleteResponse {
  deleted: number;
}

export type WatchlistResearchPriorityTier = 'attention' | 'follow_up' | 'monitor';

export interface WatchlistResearchPriorityEvidenceAge {
  state: string;
  lastReviewedAt?: string | null;
}

export interface WatchlistResearchOverlayDrilldownTarget {
  label: string;
  route: string;
  section: string;
  reason: string;
}

export interface WatchlistResearchPriorityQueueItem {
  symbol: string;
  priorityTier: WatchlistResearchPriorityTier;
  priorityReasonSafeLabel: string;
  evidenceAge: WatchlistResearchPriorityEvidenceAge;
  missingEvidence: string[];
  suggestedResearchPath: WatchlistResearchOverlayDrilldownTarget[];
  observationOnly: true;
}

export interface WatchlistResearchOverlayResponse {
  schemaVersion: string;
  overlayState: string;
  researchSummary: string;
  researchPriorityQueue: WatchlistResearchPriorityQueueItem[];
  observationOnly: true;
  decisionGrade: false;
}

export interface WatchlistScoreRefreshRequest {
  market?: string;
  source?: 'scanner';
  theme?: string;
  symbols?: string[];
  force?: boolean;
}

export interface WatchlistScoreRefreshResult {
  symbol: string;
  market: string;
  status: string;
  message?: string | null;
  score?: number | null;
  rank?: number | null;
  scannerRunId?: number | null;
}

export interface WatchlistScoreRefreshResponse {
  ok: boolean;
  updatedCount: number;
  failedCount: number;
  skippedCount: number;
  startedAt: string;
  completedAt: string;
  markets: string[];
  results: WatchlistScoreRefreshResult[];
}

export interface WatchlistScoreRefreshStatus {
  enabled: boolean;
  usTime: string;
  cnTime: string;
  hkTime: string;
  maxSymbols: number;
  running: boolean;
}
