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

export interface WatchlistItem {
  id: number;
  symbol: string;
  market: string;
  name?: string | null;
  source: string;
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
  themeId?: string | null;
  universeType?: string | null;
  notes?: string | null;
  intelligence?: WatchlistIntelligence | null;
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
