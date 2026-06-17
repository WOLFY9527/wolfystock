import apiClient from './index';
import { toCamelCase } from './utils';

export type ResearchRadarItem = {
  symbol?: string | null;
  ticker?: string | null;
  priority?: string | null;
  researchBias?: string | null;
  driverScores?: Record<string, number>;
  whyOnRadar?: string[];
  whatToVerify?: string[];
  invalidationObservations?: string[];
  riskFlags?: string[];
  evidenceQuality?: {
    status?: string | null;
    score?: number | null;
  } | null;
};

export type ResearchRadarOnboardingGuidance = {
  title?: string | null;
  summary?: string | null;
  conditionsDetected?: string[];
};

export type ResearchRadarEmptyStateAction = {
  label?: string | null;
  route?: string | null;
  description?: string | null;
};

export type ResearchRadarSuggestedResearchEntrypoint = {
  surface?: string | null;
  route?: string | null;
  description?: string | null;
};

export type ResearchRadarResponse = {
  schemaVersion: string;
  generatedAt?: string | null;
  researchQueue: ResearchRadarItem[];
  aggregateSummary: {
    queueQuality?: string | null;
    priorityCounts?: Record<string, number>;
    source?: {
      scannerRunId?: number | null;
      market?: string | null;
      profile?: string | null;
    } | null;
  };
  evidenceGaps: string[];
  marketContextFit?: string | null;
  noAdviceDisclosure?: string | null;
  dataQuality?: {
    status?: string | null;
    missingEvidence?: string[];
  } | null;
  onboardingGuidance?: ResearchRadarOnboardingGuidance | null;
  emptyStateActions: ResearchRadarEmptyStateAction[];
  starterResearchWorkflow: string[];
  firstRunChecklist: string[];
  suggestedResearchEntrypoints: ResearchRadarSuggestedResearchEntrypoint[];
};

export type UnifiedResearchQueueSourceSurface = 'scanner' | 'watchlist' | 'market' | 'manual_gap';
export type UnifiedResearchQueuePriorityTier = 'urgent_review' | 'follow_up' | 'monitor';
export type UnifiedResearchQueueFreshnessState = 'current' | 'needs_review' | 'unavailable' | 'unknown';

export type UnifiedResearchQueueFreshness = {
  state: UnifiedResearchQueueFreshnessState;
  lastReviewedAt?: string | null;
};

export type UnifiedResearchQueueSuggestedResearchPath = {
  label: string;
  route: string;
  section: string;
  reason: string;
};

export type UnifiedResearchQueueItem = {
  queueItemId: string;
  sourceSurface: UnifiedResearchQueueSourceSurface;
  symbol: string;
  title: string;
  priorityTier: UnifiedResearchQueuePriorityTier;
  whyQueued: string[];
  evidenceUsed: string[];
  evidenceGaps: string[];
  freshness: UnifiedResearchQueueFreshness;
  suggestedResearchPath: UnifiedResearchQueueSuggestedResearchPath[];
  observationOnly: boolean;
};

export type UnifiedResearchQueueResponse = {
  schemaVersion: string;
  researchQueue: UnifiedResearchQueueItem[];
  aggregateSummary: {
    itemCount: number;
    limit: number;
    bounded: boolean;
    bySourceSurface: Record<string, number>;
    byPriorityTier: Record<string, number>;
  };
  sourceSurfacesAggregated: string[];
  evidenceGaps: string[];
  dataQuality: {
    state?: string | null;
    itemCount: number;
    sourceSurfacesAvailable: string[];
    sourceSurfacesExpected: string[];
    failClosed: boolean;
  };
  noAdviceDisclosure?: string | null;
  observationOnly: boolean;
  decisionGrade: boolean;
};

const UNIFIED_RESEARCH_QUEUE_SCHEMA_VERSION = 'research_queue_v1';

function normalizeStringList(payload: unknown): string[] {
  return Array.isArray(payload)
    ? payload.map((item) => String(item ?? '').trim()).filter(Boolean)
    : [];
}

function normalizeNumberRecord(payload: unknown): Record<string, number> {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return {};
  }
  return Object.fromEntries(
    Object.entries(payload as Record<string, unknown>)
      .map(([key, value]) => [key.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase(), Number(value)])
      .filter(([, value]) => Number.isFinite(value)),
  );
}

function normalizeResearchRadarResponse(payload: unknown): ResearchRadarResponse {
  const normalized = toCamelCase<ResearchRadarResponse>(payload);
  return {
    schemaVersion: normalized.schemaVersion,
    generatedAt: normalized.generatedAt ?? null,
    researchQueue: Array.isArray(normalized.researchQueue) ? normalized.researchQueue : [],
    aggregateSummary: {
      queueQuality: normalized.aggregateSummary?.queueQuality ?? null,
      priorityCounts: normalized.aggregateSummary?.priorityCounts ?? {},
      source: normalized.aggregateSummary?.source ?? null,
    },
    evidenceGaps: normalized.evidenceGaps ?? [],
    marketContextFit: normalized.marketContextFit ?? null,
    noAdviceDisclosure: normalized.noAdviceDisclosure ?? null,
    dataQuality: normalized.dataQuality ?? null,
    onboardingGuidance: normalized.onboardingGuidance ? {
      title: normalized.onboardingGuidance.title ?? null,
      summary: normalized.onboardingGuidance.summary ?? null,
      conditionsDetected: normalizeStringList(normalized.onboardingGuidance.conditionsDetected),
    } : null,
    emptyStateActions: Array.isArray(normalized.emptyStateActions)
      ? normalized.emptyStateActions.map((item) => ({
        label: item?.label ?? null,
        route: item?.route ?? null,
        description: item?.description ?? null,
      }))
      : [],
    starterResearchWorkflow: normalizeStringList(normalized.starterResearchWorkflow),
    firstRunChecklist: normalizeStringList(normalized.firstRunChecklist),
    suggestedResearchEntrypoints: Array.isArray(normalized.suggestedResearchEntrypoints)
      ? normalized.suggestedResearchEntrypoints.map((item) => ({
        surface: item?.surface ?? null,
        route: item?.route ?? null,
        description: item?.description ?? null,
      }))
      : [],
  };
}

function normalizeUnifiedResearchQueueResponse(payload: unknown): UnifiedResearchQueueResponse {
  const normalized = toCamelCase<UnifiedResearchQueueResponse>(payload);
  if (normalized.schemaVersion !== UNIFIED_RESEARCH_QUEUE_SCHEMA_VERSION) {
    throw new Error('Invalid research queue schema version');
  }
  if (
    normalized.observationOnly !== true
    || normalized.decisionGrade !== false
    || normalized.dataQuality?.failClosed !== true
  ) {
    throw new Error('Unsafe research queue boundary');
  }
  if (Array.isArray(normalized.researchQueue) && normalized.researchQueue.some((item) => item?.observationOnly !== true)) {
    throw new Error('Unsafe research queue boundary');
  }
  return {
    schemaVersion: normalized.schemaVersion,
    researchQueue: Array.isArray(normalized.researchQueue)
      ? normalized.researchQueue.map((item) => ({
        queueItemId: String(item?.queueItemId ?? ''),
        sourceSurface: (item?.sourceSurface || 'manual_gap') as UnifiedResearchQueueSourceSurface,
        symbol: String(item?.symbol ?? '').trim(),
        title: String(item?.title ?? '').trim(),
        priorityTier: (item?.priorityTier || 'monitor') as UnifiedResearchQueuePriorityTier,
        whyQueued: normalizeStringList(item?.whyQueued),
        evidenceUsed: normalizeStringList(item?.evidenceUsed),
        evidenceGaps: normalizeStringList(item?.evidenceGaps),
        freshness: {
          state: (item?.freshness?.state || 'unknown') as UnifiedResearchQueueFreshnessState,
          lastReviewedAt: item?.freshness?.lastReviewedAt ?? null,
        },
        suggestedResearchPath: Array.isArray(item?.suggestedResearchPath)
          ? item.suggestedResearchPath.map((path) => ({
            label: String(path?.label ?? '').trim(),
            route: String(path?.route ?? '').trim(),
            section: String(path?.section ?? '').trim(),
            reason: String(path?.reason ?? '').trim(),
          })).filter((path) => path.label || path.reason)
          : [],
        observationOnly: item?.observationOnly === true,
      })).filter((item) => item.symbol || item.title)
      : [],
    aggregateSummary: {
      itemCount: Number(normalized.aggregateSummary?.itemCount ?? 0) || 0,
      limit: Number(normalized.aggregateSummary?.limit ?? 10) || 10,
      bounded: normalized.aggregateSummary?.bounded === true,
      bySourceSurface: normalizeNumberRecord(normalized.aggregateSummary?.bySourceSurface),
      byPriorityTier: normalizeNumberRecord(normalized.aggregateSummary?.byPriorityTier),
    },
    sourceSurfacesAggregated: normalizeStringList(normalized.sourceSurfacesAggregated),
    evidenceGaps: normalizeStringList(normalized.evidenceGaps),
    dataQuality: {
      state: normalized.dataQuality?.state ?? null,
      itemCount: Number(normalized.dataQuality?.itemCount ?? 0) || 0,
      sourceSurfacesAvailable: normalizeStringList(normalized.dataQuality?.sourceSurfacesAvailable),
      sourceSurfacesExpected: normalizeStringList(normalized.dataQuality?.sourceSurfacesExpected),
      failClosed: true,
    },
    noAdviceDisclosure: normalized.noAdviceDisclosure ?? null,
    observationOnly: true,
    decisionGrade: false,
  };
}

export const researchRadarApi = {
  async getResearchRadar(params: {
    market?: string;
    profile?: string;
    limit?: number;
  } = {}): Promise<ResearchRadarResponse> {
    const response = await apiClient.get('/api/v1/research/radar', { params });
    return normalizeResearchRadarResponse(response.data);
  },
  async getResearchQueue(params: {
    market?: string;
    profile?: string;
    scannerLimit?: number;
    queueLimit?: number;
  } = {}): Promise<UnifiedResearchQueueResponse> {
    const query: Record<string, string | number> = {};
    if (params.market) query.market = params.market;
    if (params.profile) query.profile = params.profile;
    if (params.scannerLimit != null) query.scanner_limit = params.scannerLimit;
    if (params.queueLimit != null) query.queue_limit = params.queueLimit;
    const response = await apiClient.get('/api/v1/research/queue', { params: query });
    return normalizeUnifiedResearchQueueResponse(response.data);
  },
};
