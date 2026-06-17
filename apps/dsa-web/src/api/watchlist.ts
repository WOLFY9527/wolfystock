import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  WatchlistCatalystExposure,
  WatchlistDeleteResponse,
  WatchlistItem,
  WatchlistItemCreateRequest,
  WatchlistItemListResponse,
  WatchlistResearchOverlayDrilldownTarget,
  WatchlistResearchOverlayResponse,
  WatchlistResearchPriorityEvidenceAge,
  WatchlistResearchPriorityQueueItem,
  WatchlistResearchPriorityTier,
  WatchlistScoreRefreshRequest,
  WatchlistScoreRefreshResponse,
  WatchlistScoreRefreshStatus,
} from '../types/watchlist';

const SAFE_CATALYST_CATEGORY_CODES = new Set([
  'earnings_fundamental_snapshot',
  'stored_news_catalyst_proxy',
  'official_macro_cache_status',
]);

const SAFE_CATALYST_EVIDENCE_CODES = new Set([
  'delayed',
  'proxy',
  'stale',
  'unverified',
]);

const SAFE_CATALYST_REASON_CODES = new Set([
  'observation_only',
  'delayed_evidence',
  'stale_evidence',
  'proxy_evidence_not_authoritative',
  'not_earnings_calendar',
  'fundamental_snapshot_present',
  'official_macro_cache_status_present',
  'stored_news_catalyst_proxy',
]);

const SAFE_RESEARCH_PRIORITY_TIERS = new Set<WatchlistResearchPriorityTier>([
  'attention',
  'follow_up',
  'monitor',
]);

function normalizeOptionalText(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const normalized = value.trim();
  return normalized ? normalized : null;
}

function normalizeOptionalCode(value: unknown, allowList: Set<string>): string | null {
  const normalized = normalizeOptionalText(value)?.toLowerCase() ?? null;
  if (!normalized || !allowList.has(normalized)) {
    return null;
  }
  return normalized;
}

function normalizeOptionalStringList(value: unknown, allowList: Set<string>): string[] | null {
  if (!Array.isArray(value)) return null;

  const normalized = Array.from(
    new Set(
      value
        .map((entry) => normalizeOptionalCode(entry, allowList))
        .filter((entry): entry is string => Boolean(entry)),
    ),
  );

  return normalized.length ? normalized : null;
}

function normalizeOptionalBoolean(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null;
}

function normalizeConsumerTextList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return Array.from(new Set(
    value
      .map((entry) => normalizeOptionalText(entry))
      .filter((entry): entry is string => Boolean(entry)),
  ));
}

function normalizeResearchPriorityTier(value: unknown): WatchlistResearchPriorityTier | null {
  const normalized = normalizeOptionalText(value)?.toLowerCase() ?? null;
  return normalized && SAFE_RESEARCH_PRIORITY_TIERS.has(normalized as WatchlistResearchPriorityTier)
    ? normalized as WatchlistResearchPriorityTier
    : null;
}

function normalizeEvidenceAge(value: unknown): WatchlistResearchPriorityEvidenceAge | null {
  if (!value || typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;
  const state = normalizeOptionalText(record.state);
  if (!state) return null;
  return {
    state,
    lastReviewedAt: normalizeOptionalText(record.lastReviewedAt),
  };
}

function normalizeSuggestedResearchPath(value: unknown): WatchlistResearchOverlayDrilldownTarget[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (!entry || typeof entry !== 'object') return [];
    const record = entry as Record<string, unknown>;
    const label = normalizeOptionalText(record.label);
    const route = normalizeOptionalText(record.route);
    if (!label || !route) return [];
    return [{
      label,
      route,
      section: normalizeOptionalText(record.section) ?? '',
      reason: normalizeOptionalText(record.reason) ?? '',
    }];
  });
}

function normalizeCatalystExposure(
  exposure: WatchlistCatalystExposure | Record<string, unknown>,
): WatchlistCatalystExposure | null {
  const id = normalizeOptionalText(exposure.id);
  const symbol = normalizeOptionalText(exposure.symbol);
  const market = normalizeOptionalText(exposure.market);
  const category = normalizeOptionalCode(exposure.category, SAFE_CATALYST_CATEGORY_CODES);
  const title = normalizeOptionalText(exposure.title);
  const summary = normalizeOptionalText(exposure.summary);

  if (!id || !symbol || !market || (!title && !summary && !category)) {
    return null;
  }

  return {
    id,
    symbol,
    market,
    category: category ?? '',
    title: title ?? '',
    summary: summary ?? '',
    evidenceStatus: normalizeOptionalCode(exposure.evidenceStatus, SAFE_CATALYST_EVIDENCE_CODES) ?? '',
    evidenceLabels: normalizeOptionalStringList(exposure.evidenceLabels, SAFE_CATALYST_EVIDENCE_CODES),
    asOf: normalizeOptionalText(exposure.asOf),
    publishedAt: normalizeOptionalText(exposure.publishedAt),
    timeframe: normalizeOptionalText(exposure.timeframe),
    reasonCodes: normalizeOptionalStringList(exposure.reasonCodes, SAFE_CATALYST_REASON_CODES),
    observationOnly: normalizeOptionalBoolean(exposure.observationOnly),
  };
}

function normalizeWatchlistItem(item: WatchlistItem): WatchlistItem {
  const catalystExposures = Array.isArray(item.intelligence?.catalystExposures)
    ? item.intelligence.catalystExposures
      .map((exposure) => normalizeCatalystExposure(exposure))
      .filter((exposure): exposure is WatchlistCatalystExposure => Boolean(exposure))
    : item.intelligence?.catalystExposures;

  return {
    ...item,
    intelligence: item.intelligence
      ? {
        ...item.intelligence,
        catalystExposures,
      }
      : item.intelligence,
  };
}

function normalizeResearchPriorityQueueItem(value: unknown): WatchlistResearchPriorityQueueItem | null {
  if (!value || typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;
  const symbol = normalizeOptionalText(record.symbol)?.toUpperCase() ?? null;
  const priorityTier = normalizeResearchPriorityTier(record.priorityTier);
  const priorityReasonSafeLabel = normalizeOptionalText(record.priorityReasonSafeLabel);
  const evidenceAge = normalizeEvidenceAge(record.evidenceAge);
  if (!symbol || !priorityTier || !priorityReasonSafeLabel || !evidenceAge || record.observationOnly !== true) {
    return null;
  }

  return {
    symbol,
    priorityTier,
    priorityReasonSafeLabel,
    evidenceAge,
    missingEvidence: normalizeConsumerTextList(record.missingEvidence),
    suggestedResearchPath: normalizeSuggestedResearchPath(record.suggestedResearchPath),
    observationOnly: true,
  };
}

function normalizeResearchOverlay(payload: unknown): WatchlistResearchOverlayResponse {
  const normalized = toCamelCase<WatchlistResearchOverlayResponse>(payload);
  const queue = Array.isArray(normalized.researchPriorityQueue)
    ? normalized.researchPriorityQueue
      .map((item) => normalizeResearchPriorityQueueItem(item))
      .filter((item): item is WatchlistResearchPriorityQueueItem => Boolean(item))
      .slice(0, 5)
    : [];

  return {
    schemaVersion: normalizeOptionalText(normalized.schemaVersion) ?? 'watchlist_research_overlay_v1',
    overlayState: normalizeOptionalText(normalized.overlayState) ?? 'unknown',
    researchSummary: normalizeOptionalText(normalized.researchSummary) ?? '',
    researchPriorityQueue: queue,
    observationOnly: true,
    decisionGrade: false,
  };
}

export const watchlistApi = {
  async listWatchlistItems(): Promise<WatchlistItemListResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/watchlist/items');
    const payload = toCamelCase<WatchlistItemListResponse>(response.data);
    return {
      ...payload,
      items: Array.isArray(payload.items) ? payload.items.map((item) => normalizeWatchlistItem(item)) : [],
    };
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
    return normalizeWatchlistItem(toCamelCase<WatchlistItem>(response.data));
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

  async getResearchOverlay(): Promise<WatchlistResearchOverlayResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/watchlist/research-overlay');
    return normalizeResearchOverlay(response.data);
  },
};
