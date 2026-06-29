import apiClient from './index';
import { toCamelCase } from './utils';

export type MarketDecisionCockpitDriverScore = {
  score?: number | null;
  direction?: string | null;
  evidenceState?: string | null;
  reasons?: string[];
};

export type MarketDecisionCockpitResearchCandidate = {
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

export type MarketDecisionCockpitResponse = {
  schemaVersion: string;
  generatedAt?: string | null;
  marketRegimeReadModel?: {
    available?: boolean;
    primaryContext?: boolean;
    readinessLabel?: string | null;
    status?: string | null;
    regimeLabel?: string | null;
    regimeStatus?: string | null;
    summary?: string | null;
    evidenceCards?: Array<{
      id?: string | null;
      title?: string | null;
      status?: string | null;
      severity?: string | null;
      headline?: string | null;
    }>;
    missingDataFamilies?: string[];
    blockedProductSurfaces?: string[];
    noAdvice?: boolean;
  } | null;
  marketRegimeDecision: {
    regime?: string | null;
    confidence?: string | null;
    confidenceScore?: number | null;
    driverScores?: Record<string, MarketDecisionCockpitDriverScore>;
    explanation?: {
      whyThisRegime?: string[];
      whatConfirmsIt?: string[];
      whatInvalidatesIt?: string[];
    } | null;
    invalidationConditions?: string[];
    researchPriorities?: {
      watchToday?: string[];
      needsMoreEvidence?: string[];
      investigateNext?: string[];
    } | null;
  };
  researchQueuePreview: {
    topCandidates: MarketDecisionCockpitResearchCandidate[];
    queueQuality?: string | null;
    evidenceGaps?: string[];
    previewOnly?: boolean;
    degradedState?: {
      status?: string | null;
      reasonCodes?: string[];
    } | null;
  };
  optionsStructureStatus: {
    gammaEvidenceStatus?: string | null;
    observationOnly?: boolean;
    decisionGrade?: boolean;
    missingEvidence?: Array<{
      code?: string | null;
      field?: string | null;
      contractSymbol?: string | null;
      kind?: string | null;
      message?: string | null;
    }>;
    blockedReasonCodes?: string[];
  };
  cockpitSummary: {
    whatChanged?: string[];
    whyItMatters?: string[];
    whatToWatch?: string[];
    confidenceLimits?: string[];
  };
  degradedInputs?: Array<{
    section?: string | null;
    status?: string | null;
    reason?: string | null;
  }>;
  noAdviceDisclosure?: string | null;
  dataQuality?: {
    status?: string | null;
    reasonCodes?: string[];
    primaryReadModelReady?: boolean;
    primaryReadModelStatus?: string | null;
    advancedEvidenceStatus?: string | null;
  } | null;
};

function normalizeCockpitResponse(payload: unknown): MarketDecisionCockpitResponse {
  const normalized = toCamelCase<MarketDecisionCockpitResponse>(payload);
  return {
    schemaVersion: normalized.schemaVersion,
    generatedAt: normalized.generatedAt ?? null,
    marketRegimeReadModel: normalized.marketRegimeReadModel ?? null,
    marketRegimeDecision: {
      regime: normalized.marketRegimeDecision?.regime ?? null,
      confidence: normalized.marketRegimeDecision?.confidence ?? null,
      confidenceScore: normalized.marketRegimeDecision?.confidenceScore ?? null,
      driverScores: normalized.marketRegimeDecision?.driverScores ?? {},
      explanation: normalized.marketRegimeDecision?.explanation ?? null,
      invalidationConditions: normalized.marketRegimeDecision?.invalidationConditions ?? [],
      researchPriorities: normalized.marketRegimeDecision?.researchPriorities ?? null,
    },
    researchQueuePreview: {
      topCandidates: Array.isArray(normalized.researchQueuePreview?.topCandidates)
        ? normalized.researchQueuePreview.topCandidates
        : [],
      queueQuality: normalized.researchQueuePreview?.queueQuality ?? null,
      evidenceGaps: normalized.researchQueuePreview?.evidenceGaps ?? [],
      previewOnly: normalized.researchQueuePreview?.previewOnly ?? false,
      degradedState: normalized.researchQueuePreview?.degradedState ?? null,
    },
    optionsStructureStatus: {
      gammaEvidenceStatus: normalized.optionsStructureStatus?.gammaEvidenceStatus ?? null,
      observationOnly: normalized.optionsStructureStatus?.observationOnly ?? false,
      decisionGrade: normalized.optionsStructureStatus?.decisionGrade ?? false,
      missingEvidence: normalized.optionsStructureStatus?.missingEvidence ?? [],
      blockedReasonCodes: normalized.optionsStructureStatus?.blockedReasonCodes ?? [],
    },
    cockpitSummary: {
      whatChanged: normalized.cockpitSummary?.whatChanged ?? [],
      whyItMatters: normalized.cockpitSummary?.whyItMatters ?? [],
      whatToWatch: normalized.cockpitSummary?.whatToWatch ?? [],
      confidenceLimits: normalized.cockpitSummary?.confidenceLimits ?? [],
    },
    degradedInputs: normalized.degradedInputs ?? [],
    noAdviceDisclosure: normalized.noAdviceDisclosure ?? null,
    dataQuality: normalized.dataQuality ?? null,
  };
}

export const marketDecisionCockpitApi = {
  async getDecisionCockpit(): Promise<MarketDecisionCockpitResponse> {
    const response = await apiClient.get('/api/v1/market/decision-cockpit');
    return normalizeCockpitResponse(response.data);
  },
};
