import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  WatchlistDeleteResponse,
  WatchlistItem,
  WatchlistItemCreateRequest,
  WatchlistItemListResponse,
  WatchlistScoreRefreshRequest,
  WatchlistScoreRefreshResponse,
  WatchlistScoreRefreshStatus,
} from '../types/watchlist';

export const watchlistApi = {
  async listWatchlistItems(): Promise<WatchlistItemListResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/watchlist/items');
    return toCamelCase<WatchlistItemListResponse>(response.data);
  },

  async addWatchlistItem(payload: WatchlistItemCreateRequest): Promise<WatchlistItem> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/watchlist/items', {
      symbol: payload.symbol,
      market: payload.market,
      name: payload.name,
      source: payload.source ?? 'scanner',
      scanner_run_id: payload.scannerRunId,
      scanner_rank: payload.scannerRank,
      scanner_score: payload.scannerScore,
      theme_id: payload.themeId,
      universe_type: payload.universeType,
      notes: payload.notes,
    });
    return toCamelCase<WatchlistItem>(response.data);
  },

  async removeWatchlistItem(itemId: number): Promise<WatchlistDeleteResponse> {
    const response = await apiClient.delete<Record<string, unknown>>(`/api/v1/watchlist/items/${encodeURIComponent(itemId)}`);
    return toCamelCase<WatchlistDeleteResponse>(response.data);
  },

  async refreshScores(payload: WatchlistScoreRefreshRequest = {}): Promise<WatchlistScoreRefreshResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/watchlist/refresh-scores', {
      market: payload.market,
      source: payload.source,
      theme: payload.theme,
      symbols: payload.symbols,
      force: payload.force ?? false,
    });
    return toCamelCase<WatchlistScoreRefreshResponse>(response.data);
  },

  async getRefreshStatus(): Promise<WatchlistScoreRefreshStatus> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/watchlist/refresh-status');
    return toCamelCase<WatchlistScoreRefreshStatus>(response.data);
  },
};
