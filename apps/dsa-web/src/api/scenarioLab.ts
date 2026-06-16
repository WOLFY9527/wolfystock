import apiClient from './index';
import { toCamelCase } from './utils';

export type ScenarioLabRegime = {
  regime?: string | null;
  confidence?: string | null;
  confidenceScore?: number | null;
  status?: string | null;
};

export type ScenarioLabResponse = {
  schemaVersion: string;
  baseRegime: ScenarioLabRegime;
  scenarioRegime: ScenarioLabRegime;
  confidenceDelta: number;
  driverDeltas: Record<string, number>;
  changedDrivers: string[];
  scenarioSummary: string[];
  whatWouldConfirm: string[];
  whatWouldInvalidate: string[];
  evidenceLimits: string[];
  noAdviceDisclosure: string | null;
};

type ScenarioLabRequest = {
  baseRegime?: Record<string, unknown> | null;
  driverScores?: Record<string, unknown> | null;
  scenarioName?: string | null;
  scenario?: Record<string, unknown> | string | null;
  scenarioOverrides?: Record<string, unknown> | null;
};

function normalizeScenarioLabResponse(payload: unknown): ScenarioLabResponse {
  const normalized = toCamelCase<ScenarioLabResponse>(payload);
  return {
    schemaVersion: normalized.schemaVersion,
    baseRegime: {
      regime: normalized.baseRegime?.regime ?? null,
      confidence: normalized.baseRegime?.confidence ?? null,
      confidenceScore: normalized.baseRegime?.confidenceScore ?? null,
      status: normalized.baseRegime?.status ?? null,
    },
    scenarioRegime: {
      regime: normalized.scenarioRegime?.regime ?? null,
      confidence: normalized.scenarioRegime?.confidence ?? null,
      confidenceScore: normalized.scenarioRegime?.confidenceScore ?? null,
      status: normalized.scenarioRegime?.status ?? null,
    },
    confidenceDelta: normalized.confidenceDelta ?? 0,
    driverDeltas: normalized.driverDeltas ?? {},
    changedDrivers: normalized.changedDrivers ?? [],
    scenarioSummary: normalized.scenarioSummary ?? [],
    whatWouldConfirm: normalized.whatWouldConfirm ?? [],
    whatWouldInvalidate: normalized.whatWouldInvalidate ?? [],
    evidenceLimits: normalized.evidenceLimits ?? [],
    noAdviceDisclosure: normalized.noAdviceDisclosure ?? null,
  };
}

export const scenarioLabApi = {
  async runScenarioLab(request: ScenarioLabRequest = {}): Promise<ScenarioLabResponse> {
    const response = await apiClient.post('/api/v1/market/scenario-lab', request);
    return normalizeScenarioLabResponse(response.data);
  },
};
