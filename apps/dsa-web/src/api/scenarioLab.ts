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

export type ScenarioLabBaselineReadinessSummary = {
  baselineSnapshot: string;
  marketFrame: string;
  driverInputs: string;
  boundary: string;
};

export type ScenarioLabResponse = {
  schemaVersion: string;
  baseRegime: ScenarioLabRegime;
  scenarioRegime: ScenarioLabRegime;
  baselineReadiness?: ScenarioLabBaselineReadiness | null;
  baselineReadinessSummary: ScenarioLabBaselineReadinessSummary;
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
  baselineEvidenceMissing: '基线证据待补齐',
  baselineSnapshotMissing: '基线快照待补齐',
  baselineSnapshotPartial: '基线快照部分可用',
  baselineSnapshotStale: '基线快照已过期',
  marketFrameReady: '当前框架可用',
  marketFrameMissing: '市场框架待补齐',
  marketFramePartial: '市场框架部分可用',
  marketFrameStale: '市场框架已过期',
  driversPending: '驱动待补',
  driversPartial: '驱动证据部分可用',
  evidenceBoundary: '证据边界',
  scenarioPending: '情景待更新',
  demoSample: '演示样本',
  observationOnly: '仅观察',
  scenarioSummaryReady: '情景摘要可用',
} as const;

const SAFE_BASELINE_READINESS_SUMMARY: ScenarioLabBaselineReadinessSummary = {
  baselineSnapshot: '基线证据待补齐',
  marketFrame: '市场框架待补齐',
  driverInputs: '驱动证据待补齐',
  boundary: '仅观察 / 非决策级',
};

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

function baselineSnapshotSummaryLabel(readiness: ScenarioLabBaselineReadiness, state: string | null): string {
  switch (state) {
    case 'available':
      return readiness.status === 'ready' && readiness.scoreAuthority === 'authoritative'
        ? SAFE_READINESS_LABELS.baselineReady
        : SAFE_READINESS_LABELS.baselinePending;
    case 'partial':
      return SAFE_READINESS_LABELS.baselineSnapshotPartial;
    case 'stale':
      return SAFE_READINESS_LABELS.baselineSnapshotStale;
    case 'missing':
      return SAFE_READINESS_LABELS.baselineSnapshotMissing;
    default:
      return SAFE_BASELINE_READINESS_SUMMARY.baselineSnapshot;
  }
}

function marketFrameSummaryLabel(state: string | null): string {
  switch (state) {
    case 'available':
      return SAFE_READINESS_LABELS.marketFrameReady;
    case 'partial':
      return SAFE_READINESS_LABELS.marketFramePartial;
    case 'stale':
      return SAFE_READINESS_LABELS.marketFrameStale;
    case 'missing':
      return SAFE_READINESS_LABELS.marketFrameMissing;
    default:
      return SAFE_BASELINE_READINESS_SUMMARY.marketFrame;
  }
}

function driverInputsSummaryLabel(state: string | null): string {
  switch (state) {
    case 'available':
      return '驱动证据可用';
    case 'partial':
      return SAFE_READINESS_LABELS.driversPartial;
    default:
      return SAFE_BASELINE_READINESS_SUMMARY.driverInputs;
  }
}

function buildBaselineReadinessSummary(readiness: ScenarioLabBaselineReadiness | null): ScenarioLabBaselineReadinessSummary {
  if (!readiness) {
    return SAFE_BASELINE_READINESS_SUMMARY;
  }

  const baselineSnapshotState = readiness.baselineSnapshot?.state ?? null;
  const marketFrameState = readiness.marketFrame?.state ?? null;
  const driverInputsState = readiness.driverInputs?.state ?? null;

  const boundary = readiness.observationOnly === false && readiness.scoreAuthority === 'authoritative' && readiness.status === 'ready'
    ? '可复用基线'
    : SAFE_BASELINE_READINESS_SUMMARY.boundary;

  return {
    baselineSnapshot: baselineSnapshotSummaryLabel(readiness, baselineSnapshotState),
    marketFrame: marketFrameSummaryLabel(marketFrameState),
    driverInputs: driverInputsSummaryLabel(driverInputsState),
    boundary,
  };
}

function pushUnique(labels: string[], label: string) {
  if (!labels.includes(label)) {
    labels.push(label);
  }
}

function buildReadinessLabels(readiness: ScenarioLabBaselineReadiness | null): string[] {
  if (!readiness) {
    return [
      SAFE_READINESS_LABELS.baselineEvidenceMissing,
      SAFE_READINESS_LABELS.observationOnly,
    ];
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
  } else if (baselineState === 'missing') {
    pushUnique(labels, SAFE_READINESS_LABELS.baselineEvidenceMissing);
  } else {
    pushUnique(labels, SAFE_READINESS_LABELS.baselinePending);
  }
  if (marketFrameState === 'available') {
    pushUnique(labels, SAFE_READINESS_LABELS.marketFrameReady);
  } else if (marketFrameState === 'partial') {
    pushUnique(labels, SAFE_READINESS_LABELS.marketFramePartial);
  } else if (marketFrameState === 'stale') {
    pushUnique(labels, SAFE_READINESS_LABELS.marketFrameStale);
  } else if (marketFrameState === 'missing') {
    pushUnique(labels, SAFE_READINESS_LABELS.marketFrameMissing);
  }
  if (driverState === 'partial') {
    pushUnique(labels, SAFE_READINESS_LABELS.driversPartial);
  } else if (driverState !== 'available') {
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
    baselineReadinessSummary: buildBaselineReadinessSummary(baselineReadiness),
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
