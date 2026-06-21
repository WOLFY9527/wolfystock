import apiClient from './index';
import { toCamelCase } from './utils';

export type ScenarioLabRegime = {
  regime?: string | null;
  confidence?: string | null;
  confidenceScore?: number | null;
  status?: string | null;
};

export type ScenarioLabReadinessComponent = {
  state?: string | null;
  available?: boolean | null;
  lastUpdated?: string | null;
  affectedComponents: string[];
};

export type ScenarioLabDriverInputsReadiness = {
  state?: string | null;
  availableDriverKeys: string[];
  partialDriverKeys: string[];
  missingDriverKeys: string[];
  affectedDriverKeys: string[];
};

export type ScenarioLabEvidenceCompleteness = {
  state?: string | null;
  gaps: string[];
};

export type ScenarioLabBaselineReadiness = {
  status?: string | null;
  baselineSnapshot?: ScenarioLabReadinessComponent | null;
  marketFrame?: ScenarioLabReadinessComponent | null;
  driverInputs?: ScenarioLabDriverInputsReadiness | null;
  evidenceCompleteness?: ScenarioLabEvidenceCompleteness | null;
  dataState?: string | null;
  sampleState?: string | null;
  scoreAuthority?: string | null;
  sourceAuthorityAllowed?: boolean | null;
  authoritative?: boolean | null;
  observationOnly?: boolean | null;
  ready?: boolean | null;
  partial?: boolean | null;
  blocked?: boolean | null;
  affectedBaselineComponents: string[];
  affectedDriverKeys: string[];
  evidenceGaps: string[];
  lastUpdated?: string | null;
};

export type ScenarioLabResponse = {
  schemaVersion: string;
  baseRegime: ScenarioLabRegime;
  scenarioRegime: ScenarioLabRegime;
  baselineReadiness?: ScenarioLabBaselineReadiness | null;
  readinessLabels: string[];
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

const SAFE_READINESS_LABELS = {
  baselineReady: '基准可用',
  baselinePending: '基准待确认',
  baselinePartial: '基准部分可用',
  marketFrameReady: '当前框架可用',
  driversPending: '驱动待补',
  evidenceBoundary: '证据边界',
  scenarioPending: '情景待更新',
  demoSample: '演示样本',
  observationOnly: '仅观察',
  scenarioSummaryReady: '情景摘要可用',
} as const;

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0) : [];
}

function normalizeReadinessComponent(value: ScenarioLabReadinessComponent | null | undefined): ScenarioLabReadinessComponent | null {
  if (!value || typeof value !== 'object') {
    return null;
  }
  return {
    state: value.state ?? null,
    available: value.available ?? null,
    lastUpdated: value.lastUpdated ?? null,
    affectedComponents: asStringArray(value.affectedComponents),
  };
}

function normalizeDriverInputs(value: ScenarioLabDriverInputsReadiness | null | undefined): ScenarioLabDriverInputsReadiness | null {
  if (!value || typeof value !== 'object') {
    return null;
  }
  return {
    state: value.state ?? null,
    availableDriverKeys: asStringArray(value.availableDriverKeys),
    partialDriverKeys: asStringArray(value.partialDriverKeys),
    missingDriverKeys: asStringArray(value.missingDriverKeys),
    affectedDriverKeys: asStringArray(value.affectedDriverKeys),
  };
}

function normalizeEvidenceCompleteness(value: ScenarioLabEvidenceCompleteness | null | undefined): ScenarioLabEvidenceCompleteness | null {
  if (!value || typeof value !== 'object') {
    return null;
  }
  return {
    state: value.state ?? null,
    gaps: asStringArray(value.gaps),
  };
}

function normalizeBaselineReadiness(value: ScenarioLabBaselineReadiness | null | undefined): ScenarioLabBaselineReadiness | null {
  if (!value || typeof value !== 'object') {
    return null;
  }
  return {
    status: value.status ?? null,
    baselineSnapshot: normalizeReadinessComponent(value.baselineSnapshot),
    marketFrame: normalizeReadinessComponent(value.marketFrame),
    driverInputs: normalizeDriverInputs(value.driverInputs),
    evidenceCompleteness: normalizeEvidenceCompleteness(value.evidenceCompleteness),
    dataState: value.dataState ?? null,
    sampleState: value.sampleState ?? null,
    scoreAuthority: value.scoreAuthority ?? null,
    sourceAuthorityAllowed: value.sourceAuthorityAllowed ?? null,
    authoritative: value.authoritative ?? null,
    observationOnly: value.observationOnly ?? null,
    ready: value.ready ?? null,
    partial: value.partial ?? null,
    blocked: value.blocked ?? null,
    affectedBaselineComponents: asStringArray(value.affectedBaselineComponents),
    affectedDriverKeys: asStringArray(value.affectedDriverKeys),
    evidenceGaps: asStringArray(value.evidenceGaps),
    lastUpdated: value.lastUpdated ?? null,
  };
}

function pushUnique(labels: string[], label: string) {
  if (!labels.includes(label)) {
    labels.push(label);
  }
}

function buildReadinessLabels(readiness: ScenarioLabBaselineReadiness | null): string[] {
  if (!readiness) {
    return [];
  }
  const labels: string[] = [];
  const baselineState = readiness.baselineSnapshot?.state;
  const marketFrameState = readiness.marketFrame?.state;
  const driverState = readiness.driverInputs?.state;
  const evidenceState = readiness.evidenceCompleteness?.state;
  const sampleState = readiness.sampleState;

  if (readiness.status === 'ready' && readiness.scoreAuthority === 'authoritative') {
    pushUnique(labels, SAFE_READINESS_LABELS.baselineReady);
  } else if (baselineState === 'partial' || baselineState === 'stale') {
    pushUnique(labels, SAFE_READINESS_LABELS.baselinePartial);
  } else {
    pushUnique(labels, SAFE_READINESS_LABELS.baselinePending);
  }
  if (marketFrameState === 'available') {
    pushUnique(labels, SAFE_READINESS_LABELS.marketFrameReady);
  }
  if (driverState !== 'available') {
    pushUnique(labels, SAFE_READINESS_LABELS.driversPending);
  }
  if (evidenceState !== 'ready' || readiness.scoreAuthority !== 'authoritative') {
    pushUnique(labels, SAFE_READINESS_LABELS.evidenceBoundary);
  }
  if (readiness.status === 'blocked') {
    pushUnique(labels, SAFE_READINESS_LABELS.scenarioPending);
  }
  if (readiness.dataState === 'demo_static_sample' || (sampleState && sampleState !== 'none')) {
    pushUnique(labels, SAFE_READINESS_LABELS.demoSample);
  }
  if (readiness.observationOnly !== false || readiness.scoreAuthority !== 'authoritative') {
    pushUnique(labels, SAFE_READINESS_LABELS.observationOnly);
  }
  if (readiness.status !== 'blocked') {
    pushUnique(labels, SAFE_READINESS_LABELS.scenarioSummaryReady);
  }
  return labels;
}

function normalizeScenarioLabResponse(payload: unknown): ScenarioLabResponse {
  const normalized = toCamelCase<ScenarioLabResponse>(payload);
  const baselineReadiness = normalizeBaselineReadiness(normalized.baselineReadiness);
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
    baselineReadiness,
    readinessLabels: buildReadinessLabels(baselineReadiness),
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
