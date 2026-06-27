import apiClient from './index';
import { toCamelCase } from './utils';
import { consumerSafeReportText } from '../utils/homeReportIdentity';
import type {
  ScannerCandidate,
  ScannerCandidateResearchPacket,
  ScannerOperationalStatus,
  ScannerStrategySimulationResult,
  ScannerThemeGenerateRequest,
  ScannerThemeGenerationResponse,
  ScannerRunDetail,
  ScannerRunHistoryResponse,
  ScannerRunRequest,
  ScannerThemesResponse,
} from '../types/scanner';

export interface ScannerDataReadiness {
  state?: 'ready' | 'partial' | 'blocked' | 'unknown' | 'not_run' | string | null;
  market?: string | null;
  profile?: string | null;
  universeSize?: number | null;
  scannerUniverseReadiness?: {
    contractVersion?: string | null;
    status?: 'available' | 'missing' | 'stale' | 'not_configured' | 'insufficient_coverage' | 'unavailable' | string | null;
    market?: string | null;
    universeSize?: number | null;
    lastUpdatedAt?: string | null;
    freshnessState?: string | null;
    requiredDataClasses?: string[];
    availableDataClasses?: string[];
    missingDataClasses?: string[];
    blockedProductSurfaces?: string[];
    operatorNextAction?: string | null;
    consumerSafeMessage?: string | null;
    consumerSafe?: boolean | null;
  } | null;
  quoteCoverage?: string | null;
  historyCoverage?: string | null;
  freshness?: string | null;
  candidateEvaluationCount?: number | null;
  selectedCount?: number | null;
  rejectedCount?: number | null;
  failedCount?: number | null;
  blockerBucket?: string | null;
  consumerSummary?: string | null;
  nextDataAction?: string | null;
}

export type ScannerRunDetailWithDataReadiness = ScannerRunDetail & {
  diagnostics: ScannerRunDetail['diagnostics'] & {
    dataReadiness?: ScannerDataReadiness;
  };
};

export type ScannerOperationalStatusWithDataReadiness = ScannerOperationalStatus & {
  dataReadiness?: ScannerDataReadiness | null;
};

const SCANNER_RESEARCH_PACKET_TEXT_LIMIT = 220;
const SCANNER_RESEARCH_PACKET_LIST_LIMIT = 4;

function scannerResearchPacketText(value: unknown): string | null {
  const text = consumerSafeReportText(value, '').trim();
  if (!text || text.length > SCANNER_RESEARCH_PACKET_TEXT_LIMIT) return null;
  if (text === '--') return null;
  return text;
}

function scannerResearchPacketList(value: unknown, limit = SCANNER_RESEARCH_PACKET_LIST_LIMIT): string[] {
  if (!Array.isArray(value)) return [];
  const result: string[] = [];
  value.forEach((item) => {
    const text = scannerResearchPacketText(item);
    if (text && !result.includes(text) && result.length < limit) {
      result.push(text);
    }
  });
  return result;
}

function normalizeScannerResearchPacket(value: unknown): ScannerCandidateResearchPacket | undefined {
  if (!value || typeof value !== 'object') return undefined;
  const packet = value as Partial<ScannerCandidateResearchPacket>;
  const whySurfaced = scannerResearchPacketText(packet.whySurfaced);
  const primaryEvidence = scannerResearchPacketList(packet.primaryEvidence, 4);
  const limitingEvidence = scannerResearchPacketList(packet.limitingEvidence, 4);
  const dataQualityNotes = scannerResearchPacketList(packet.dataQualityNotes, 4);
  const rejectedOrLimitedReasonSafeLabel = scannerResearchPacketText(packet.rejectedOrLimitedReasonSafeLabel);
  const researchNextStep = scannerResearchPacketText(packet.researchNextStep);
  const hasContent = Boolean(
    whySurfaced
    || primaryEvidence.length
    || limitingEvidence.length
    || dataQualityNotes.length
    || rejectedOrLimitedReasonSafeLabel
    || researchNextStep,
  );

  if (!hasContent) return undefined;
  return {
    whySurfaced,
    primaryEvidence,
    limitingEvidence,
    dataQualityNotes,
    rejectedOrLimitedReasonSafeLabel,
    researchNextStep,
    observationOnly: packet.observationOnly === true,
  };
}

function normalizeScannerCandidate(candidate: ScannerCandidate): ScannerCandidate {
  const candidateResearchPacket = normalizeScannerResearchPacket(candidate.candidateResearchPacket);
  if (!candidateResearchPacket) {
    const rest = { ...candidate };
    delete rest.candidateResearchPacket;
    return rest;
  }
  return {
    ...candidate,
    candidateResearchPacket,
  };
}

function normalizeScannerCandidates(candidates?: ScannerCandidate[]): ScannerCandidate[] | undefined {
  return Array.isArray(candidates) ? candidates.map(normalizeScannerCandidate) : candidates;
}

function normalizeScannerDataReadiness(value: unknown): ScannerDataReadiness | undefined {
  if (!value || typeof value !== 'object') return undefined;
  const normalized = toCamelCase<ScannerDataReadiness>(value as Record<string, unknown>);
  if (!normalized.state && !normalized.blockerBucket) return undefined;
  return normalized;
}

function normalizeScannerRunDetail(payload: Record<string, unknown>): ScannerRunDetailWithDataReadiness {
  const normalized = toCamelCase<ScannerRunDetail>(payload);
  const normalizedDiagnostics = normalized.diagnostics as ScannerRunDetailWithDataReadiness['diagnostics'] | undefined;
  const diagnostics = {
    ...(normalizedDiagnostics || {}),
    dataReadiness: normalizeScannerDataReadiness(normalizedDiagnostics?.dataReadiness),
  };
  return {
    ...normalized,
    diagnostics,
    shortlist: normalizeScannerCandidates(normalized.shortlist) || [],
    selected: normalizeScannerCandidates(normalized.selected),
  };
}

function normalizeScannerOperationalStatus(payload: Record<string, unknown>): ScannerOperationalStatusWithDataReadiness {
  const normalized = toCamelCase<ScannerOperationalStatusWithDataReadiness>(payload);
  return {
    ...normalized,
    dataReadiness: normalizeScannerDataReadiness(normalized.dataReadiness),
  };
}

export const scannerApi = {
  run: async (params: ScannerRunRequest = {}): Promise<ScannerRunDetail> => {
    const requestData: Record<string, unknown> = {
      market: params.market || 'cn',
    };
    if (params.profile) requestData.profile = params.profile;
    if (params.shortlistSize != null) requestData.shortlist_size = params.shortlistSize;
    if (params.universeLimit != null) requestData.universe_limit = params.universeLimit;
    if (params.detailLimit != null) requestData.detail_limit = params.detailLimit;
    if (params.universeType) requestData.universe_type = params.universeType;
    if (params.themeId) requestData.theme_id = params.themeId;
    if (params.symbols?.length) requestData.symbols = params.symbols;

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/scanner/run',
      requestData,
      { timeout: 120000 },
    );
    return normalizeScannerRunDetail(response.data);
  },

  getThemes: async (params: { market?: string } = {}): Promise<ScannerThemesResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/scanner/themes',
      {
        params: params.market ? { market: params.market } : undefined,
      },
    );
    return toCamelCase<ScannerThemesResponse>(response.data);
  },

  createTheme: async (params: ScannerThemeGenerateRequest): Promise<ScannerThemeGenerationResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/scanner/themes',
      {
        id: params.id,
        label: params.label,
        market: params.market,
        prompt: params.prompt,
        manual_symbols: params.manualSymbols || [],
      },
      { timeout: 120000 },
    );
    return toCamelCase<ScannerThemeGenerationResponse>(response.data);
  },

  getRuns: async (params: {
    market?: string;
    profile?: string;
    page?: number;
    limit?: number;
  } = {}): Promise<ScannerRunHistoryResponse> => {
    const {
      market = 'cn',
      profile,
      page = 1,
      limit = 10,
    } = params;
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/scanner/runs',
      {
        params: {
          market,
          profile,
          page,
          limit,
        },
      },
    );
    return toCamelCase<ScannerRunHistoryResponse>(response.data);
  },

  getRun: async (runId: number): Promise<ScannerRunDetail> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/scanner/runs/${encodeURIComponent(runId)}`,
    );
    return normalizeScannerRunDetail(response.data);
  },

  getStrategySimulation: async (params: {
    theme?: string | null;
    profile: string;
    market: string;
    lookbackDays?: number;
    forwardDays?: number;
    limit?: number;
  }): Promise<ScannerStrategySimulationResult> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/scanner/strategy-simulation',
      {
        params: {
          theme: params.theme || undefined,
          profile: params.profile,
          market: params.market,
          lookback_days: params.lookbackDays ?? 90,
          forward_days: params.forwardDays ?? 5,
          limit: params.limit ?? 50,
        },
      },
    );
    return toCamelCase<ScannerStrategySimulationResult>(response.data);
  },

  getTodayWatchlist: async (params: {
    market?: string;
    profile?: string;
  } = {}): Promise<ScannerRunDetail> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/scanner/watchlists/today',
      {
        params: {
          market: params.market || 'cn',
          profile: params.profile,
        },
      },
    );
    return normalizeScannerRunDetail(response.data);
  },

  getRecentWatchlists: async (params: {
    market?: string;
    profile?: string;
    limitDays?: number;
  } = {}): Promise<ScannerRunHistoryResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/scanner/watchlists/recent',
      {
        params: {
          market: params.market || 'cn',
          profile: params.profile,
          limit_days: params.limitDays ?? 7,
        },
      },
    );
    return toCamelCase<ScannerRunHistoryResponse>(response.data);
  },

  getStatus: async (params: {
    market?: string;
    profile?: string;
  } = {}): Promise<ScannerOperationalStatusWithDataReadiness> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/scanner/status',
      {
        params: {
          market: params.market || 'cn',
          profile: params.profile,
        },
      },
    );
    return normalizeScannerOperationalStatus(response.data);
  },
};
