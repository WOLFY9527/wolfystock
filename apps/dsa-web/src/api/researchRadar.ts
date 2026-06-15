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
};

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
};
