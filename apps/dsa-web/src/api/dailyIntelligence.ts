import apiClient from './index';
import { toCamelCase } from './utils';

export type DailyIntelligenceMarketRegimeSummary = {
  regime?: string | null;
  confidence?: string | null;
  summary?: string | null;
  supportingObservations?: string[];
  invalidationObservations?: string[];
};

export type DailyIntelligenceEvidenceLink = {
  label?: string | null;
  route?: string | null;
  section?: string | null;
  reason?: string | null;
};

export type DailyIntelligencePriorityItem = {
  label?: string | null;
  source?: string | null;
  priority?: string | null;
  ticker?: string | null;
  observations?: string[];
  whatToVerify?: string[];
  evidenceGaps?: string[];
  evidenceLinks?: DailyIntelligenceEvidenceLink[];
};

export type DailyIntelligenceScannerHighlight = {
  ticker?: string | null;
  priority?: string | null;
  observations?: string[];
  whatToVerify?: string[];
  evidenceGaps?: string[];
  riskFlags?: string[];
  evidenceLinks?: DailyIntelligenceEvidenceLink[];
};

export type DailyIntelligenceWatchlistHighlight = {
  ticker?: string | null;
  structureState?: string | null;
  researchPriority?: string | null;
  whyWatching?: string | null;
  whatToVerify?: string[];
  evidenceGaps?: string[];
  riskFlags?: string[];
  evidenceLinks?: DailyIntelligenceEvidenceLink[];
};

export type DailyIntelligencePortfolioStructureHighlight = {
  ticker?: string | null;
  structureState?: string | null;
  confidence?: string | null;
  watchNext?: string[];
  riskFlags?: string[];
  missingEvidence?: string[];
  evidenceLinks?: DailyIntelligenceEvidenceLink[];
};

export type DailyIntelligenceScenarioRisk = {
  label?: string | null;
  source?: string | null;
  observations?: string[];
  evidenceGaps?: string[];
  evidenceLinks?: DailyIntelligenceEvidenceLink[];
};

export type DailyIntelligenceDegradedInput = {
  section?: string | null;
  status?: 'degraded' | 'unavailable' | null;
  reason?: string | null;
};

export type DailyIntelligenceResponse = {
  schemaVersion: string;
  generatedAt?: string | null;
  briefingDate?: string | null;
  sessionLabel?: string | null;
  marketRegimeSummary: DailyIntelligenceMarketRegimeSummary;
  whatChanged: string[];
  sectionLinks: DailyIntelligenceEvidenceLink[];
  topResearchPriorities: DailyIntelligencePriorityItem[];
  scannerHighlights: DailyIntelligenceScannerHighlight[];
  watchlistHighlights: DailyIntelligenceWatchlistHighlight[];
  portfolioStructureHighlights: DailyIntelligencePortfolioStructureHighlight[];
  scenarioRisks: DailyIntelligenceScenarioRisk[];
  evidenceGaps: string[];
  degradedInputs: DailyIntelligenceDegradedInput[];
  observationOnly: boolean;
  decisionGrade: boolean;
};

function normalizeEvidenceLinks(payload: unknown): DailyIntelligenceEvidenceLink[] {
  if (!Array.isArray(payload)) {
    return [];
  }
  return payload.map((item) => ({
    label: item?.label ?? null,
    route: item?.route ?? null,
    section: item?.section ?? null,
    reason: item?.reason ?? null,
  }));
}

function normalizeDailyIntelligenceResponse(payload: unknown): DailyIntelligenceResponse {
  const normalized = toCamelCase<DailyIntelligenceResponse>(payload);

  return {
    schemaVersion: normalized.schemaVersion,
    generatedAt: normalized.generatedAt ?? null,
    briefingDate: normalized.briefingDate ?? null,
    sessionLabel: normalized.sessionLabel ?? null,
    marketRegimeSummary: {
      regime: normalized.marketRegimeSummary?.regime ?? null,
      confidence: normalized.marketRegimeSummary?.confidence ?? null,
      summary: normalized.marketRegimeSummary?.summary ?? null,
      supportingObservations: normalized.marketRegimeSummary?.supportingObservations ?? [],
      invalidationObservations: normalized.marketRegimeSummary?.invalidationObservations ?? [],
    },
    whatChanged: normalized.whatChanged ?? [],
    sectionLinks: normalizeEvidenceLinks(normalized.sectionLinks),
    topResearchPriorities: Array.isArray(normalized.topResearchPriorities)
      ? normalized.topResearchPriorities.map((item) => ({
        ...item,
        evidenceLinks: normalizeEvidenceLinks(item?.evidenceLinks),
      }))
      : [],
    scannerHighlights: Array.isArray(normalized.scannerHighlights)
      ? normalized.scannerHighlights.map((item) => ({
        ...item,
        evidenceLinks: normalizeEvidenceLinks(item?.evidenceLinks),
      }))
      : [],
    watchlistHighlights: Array.isArray(normalized.watchlistHighlights)
      ? normalized.watchlistHighlights.map((item) => ({
        ...item,
        evidenceLinks: normalizeEvidenceLinks(item?.evidenceLinks),
      }))
      : [],
    portfolioStructureHighlights: Array.isArray(normalized.portfolioStructureHighlights)
      ? normalized.portfolioStructureHighlights.map((item) => ({
        ...item,
        evidenceLinks: normalizeEvidenceLinks(item?.evidenceLinks),
      }))
      : [],
    scenarioRisks: Array.isArray(normalized.scenarioRisks) ? normalized.scenarioRisks : [],
    evidenceGaps: normalized.evidenceGaps ?? [],
    degradedInputs: Array.isArray(normalized.degradedInputs)
      ? normalized.degradedInputs.map((item) => ({
        section: item?.section ?? null,
        status: item?.status ?? null,
        reason: item?.reason ?? null,
      }))
      : [],
    observationOnly: normalized.observationOnly !== false,
    decisionGrade: normalized.decisionGrade === true,
  };
}

export const dailyIntelligenceApi = {
  async getDailyIntelligence(): Promise<DailyIntelligenceResponse> {
    const response = await apiClient.get('/api/v1/market/daily-intelligence');
    return normalizeDailyIntelligenceResponse(response.data);
  },
};
