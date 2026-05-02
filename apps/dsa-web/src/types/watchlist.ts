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
  scoreError?: string | null;
  themeId?: string | null;
  universeType?: string | null;
  notes?: string | null;
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
