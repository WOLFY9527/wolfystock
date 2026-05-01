export interface WatchlistItem {
  id: number;
  symbol: string;
  market: string;
  name?: string | null;
  source: string;
  scannerRunId?: number | null;
  scannerRank?: number | null;
  scannerScore?: number | null;
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
