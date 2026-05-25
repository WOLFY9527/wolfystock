export type ConsumerDataQualityStatus =
  | 'AVAILABLE'
  | 'UPDATING'
  | 'DELAYED'
  | 'PARTIAL'
  | 'INSUFFICIENT'
  | 'PAUSED'
  | 'UNAVAILABLE';

export type ConsumerDataQualityFreshnessCategory =
  | 'CURRENT'
  | 'RECENT'
  | 'DELAYED'
  | 'STALE'
  | 'UNAVAILABLE'
  | 'UNKNOWN';

export type ConsumerDataQualityConfidenceCategory =
  | 'HIGH'
  | 'MEDIUM'
  | 'LOW'
  | 'LIMITED'
  | 'UNKNOWN';

export interface ConsumerDataQualityInput {
  [key: string]: unknown;
}

export interface ConsumerDataQualityViewModel {
  status: ConsumerDataQualityStatus;
  confidenceCategory: ConsumerDataQualityConfidenceCategory;
  freshnessCategory: ConsumerDataQualityFreshnessCategory;
  messageKey: string;
  message: string;
  asOf?: string;
  updatedAt?: string;
  isActionableForUser: boolean;
}

type ConsumerDataQualityFacts = {
  asOf?: string;
  updatedAt?: string;
  freshnessText: string;
  stateText: string;
  confidence?: number;
  coverage?: number;
  isFallback: boolean;
  isProxy: boolean;
  isStale: boolean;
  isPartial: boolean;
  isUnavailable: boolean;
  isUpdating: boolean;
  observationOnly: boolean;
  scoreContributionDenied: boolean;
  sourceAuthorityDenied: boolean;
};

const STATUS_MESSAGES: Record<ConsumerDataQualityStatus, { key: string; message: string }> = {
  AVAILABLE: {
    key: 'dataQuality.available',
    message: '当前数据可用于观察。',
  },
  UPDATING: {
    key: 'dataQuality.updating',
    message: '数据更新中，稍后将自动刷新。',
  },
  DELAYED: {
    key: 'dataQuality.delayed',
    message: '已使用最近一次可用数据。',
  },
  PARTIAL: {
    key: 'dataQuality.partial',
    message: '部分数据暂不可用。',
  },
  INSUFFICIENT: {
    key: 'dataQuality.insufficient',
    message: '当前信号置信度较低，仅供观察。',
  },
  PAUSED: {
    key: 'dataQuality.paused',
    message: '部分数据暂不可用，当前评分已暂停。',
  },
  UNAVAILABLE: {
    key: 'dataQuality.unavailable',
    message: '本模块暂不可用，请稍后重试。',
  },
};

const FRESH_TEXT_KEYS = [
  'freshness',
  'freshness_state',
  'freshnessState',
  'freshness_class',
  'freshnessClass',
  'freshness_label',
  'freshnessLabel',
  'data_quality_state',
  'dataQualityState',
] as const;

const STATE_TEXT_KEYS = [
  'status',
  'state',
  'decision_status',
  'decisionStatus',
  'cap_reason',
  'capReason',
  'degradation_reason',
  'degradationReason',
] as const;

const CONFIDENCE_KEYS = [
  'confidence',
  'confidence_weight',
  'confidenceWeight',
  'score_confidence',
  'scoreConfidence',
  'evidence_coverage',
  'evidenceCoverage',
] as const;

const COVERAGE_KEYS = [
  'coverage',
  'coverage_ratio',
  'coverageRatio',
  'metric_coverage_ratio',
  'metricCoverageRatio',
] as const;

const FALLBACK_MARKERS = ['fallback', 'mock', 'fixture', 'synthetic'];
const PROXY_MARKERS = ['proxy'];
const STALE_MARKERS = ['stale', 'fallback', 'mock', 'fixture', 'synthetic'];
const DELAYED_MARKERS = ['delayed'];
const CURRENT_MARKERS = ['live', 'fresh', 'current', 'ready'];
const RECENT_MARKERS = ['cached', 'cache', 'recent'];
const UNAVAILABLE_MARKERS = ['unavailable', 'missing', 'error', 'failed', 'empty'];
const UPDATING_MARKERS = ['refreshing', 'updating', 'loading', 'pending'];
const SOURCE_AUTHORITY_DENIED_MARKERS = ['source_authority_denied', 'authority_denied'];

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function normalizeText(value: unknown): string {
  return typeof value === 'string' ? value.trim().toLowerCase() : '';
}

function readString(input: ConsumerDataQualityInput, keys: readonly string[]): string | undefined {
  for (const key of keys) {
    const value = input[key];
    if (typeof value === 'string' && value.trim()) {
      return value;
    }
  }
  return undefined;
}

function readNumber(input: ConsumerDataQualityInput, keys: readonly string[]): number | undefined {
  for (const key of keys) {
    const value = input[key];
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
    if (isRecord(value)) {
      const nestedValue = value.value ?? value.ratio ?? value.coverageRatio ?? value.metricCoverageRatio;
      if (typeof nestedValue === 'number' && Number.isFinite(nestedValue)) {
        return nestedValue;
      }
    }
  }
  return undefined;
}

function collectPrimitiveFacts(value: unknown): { booleans: Array<[string, boolean]>; strings: string[] } {
  const booleans: Array<[string, boolean]> = [];
  const strings: string[] = [];

  const visit = (current: unknown): void => {
    if (Array.isArray(current)) {
      current.forEach(visit);
      return;
    }

    if (!isRecord(current)) return;

    for (const [key, nestedValue] of Object.entries(current)) {
      if (typeof nestedValue === 'boolean') {
        booleans.push([key, nestedValue]);
      } else if (typeof nestedValue === 'string') {
        strings.push(nestedValue.toLowerCase());
      } else if (Array.isArray(nestedValue) || isRecord(nestedValue)) {
        visit(nestedValue);
      }
    }
  };

  visit(value);
  return { booleans, strings };
}

function booleanValue(booleans: Array<[string, boolean]>, keys: readonly string[]): boolean {
  return booleans.some(([key, value]) => keys.includes(key) && value === true);
}

function falseBooleanValue(booleans: Array<[string, boolean]>, keys: readonly string[]): boolean {
  return booleans.some(([key, value]) => keys.includes(key) && value === false);
}

function containsAny(value: string, markers: readonly string[]): boolean {
  return markers.some((marker) => value.includes(marker));
}

function stringsContainAny(values: readonly string[], markers: readonly string[]): boolean {
  return values.some((value) => containsAny(value, markers));
}

function collectFacts(input: ConsumerDataQualityInput): ConsumerDataQualityFacts {
  const primitiveFacts = collectPrimitiveFacts(input);
  const freshnessText = normalizeText(readString(input, FRESH_TEXT_KEYS));
  const stateText = normalizeText(readString(input, STATE_TEXT_KEYS));
  const stateSignal = [freshnessText, stateText].filter(Boolean).join(' ');
  const allText = [freshnessText, stateText, ...primitiveFacts.strings].filter(Boolean).join(' ');

  return {
    asOf: readString(input, ['asOf', 'as_of']),
    updatedAt: readString(input, ['updatedAt', 'updated_at']),
    freshnessText,
    stateText,
    confidence: readNumber(input, CONFIDENCE_KEYS),
    coverage: readNumber(input, COVERAGE_KEYS),
    isFallback: booleanValue(primitiveFacts.booleans, ['isFallback', 'is_fallback', 'fallbackUsed', 'fallback_used'])
      || stringsContainAny(primitiveFacts.strings, FALLBACK_MARKERS),
    isProxy: booleanValue(primitiveFacts.booleans, ['proxyOnly', 'proxy_only'])
      || stringsContainAny(primitiveFacts.strings, PROXY_MARKERS),
    isStale: booleanValue(primitiveFacts.booleans, ['isStale', 'is_stale'])
      || containsAny(freshnessText, ['stale']),
    isPartial: booleanValue(primitiveFacts.booleans, ['isPartial', 'is_partial'])
      || containsAny(stateText, ['partial']),
    isUnavailable: booleanValue(primitiveFacts.booleans, ['isUnavailable', 'is_unavailable'])
      || containsAny(stateSignal, UNAVAILABLE_MARKERS),
    isUpdating: booleanValue(primitiveFacts.booleans, ['isRefreshing', 'is_refreshing'])
      || containsAny(stateSignal, UPDATING_MARKERS),
    observationOnly: booleanValue(primitiveFacts.booleans, ['observationOnly', 'observation_only']),
    scoreContributionDenied: falseBooleanValue(primitiveFacts.booleans, ['scoreContributionAllowed', 'score_contribution_allowed']),
    sourceAuthorityDenied: falseBooleanValue(primitiveFacts.booleans, ['sourceAuthorityAllowed', 'source_authority_allowed'])
      || containsAny(allText, SOURCE_AUTHORITY_DENIED_MARKERS),
  };
}

function resolveStatus(facts: ConsumerDataQualityFacts): ConsumerDataQualityStatus {
  const lowCoverage = typeof facts.coverage === 'number' && facts.coverage < 0.5;
  const lowConfidence = typeof facts.confidence === 'number' && facts.confidence < 0.5;

  if (facts.isUnavailable) return 'UNAVAILABLE';
  if (facts.isUpdating) return 'UPDATING';
  if (facts.sourceAuthorityDenied) return 'PAUSED';
  if (lowCoverage && (facts.observationOnly || facts.scoreContributionDenied || facts.isProxy)) return 'INSUFFICIENT';
  if (facts.isPartial) return 'PARTIAL';
  if (facts.scoreContributionDenied && facts.observationOnly) return 'PAUSED';
  if (lowCoverage || lowConfidence) return 'INSUFFICIENT';
  if (facts.isStale || facts.isFallback || facts.isProxy || containsAny(facts.freshnessText, DELAYED_MARKERS)) return 'DELAYED';
  return 'AVAILABLE';
}

function resolveFreshnessCategory(facts: ConsumerDataQualityFacts): ConsumerDataQualityFreshnessCategory {
  if (facts.isUnavailable || containsAny(facts.freshnessText, UNAVAILABLE_MARKERS)) return 'UNAVAILABLE';
  if (facts.isStale || facts.isFallback || containsAny(facts.freshnessText, STALE_MARKERS)) return 'STALE';
  if (containsAny(facts.freshnessText, DELAYED_MARKERS)) return 'DELAYED';
  if (containsAny(facts.freshnessText, RECENT_MARKERS)) return 'RECENT';
  if (containsAny(facts.freshnessText, CURRENT_MARKERS)) return 'CURRENT';
  return 'UNKNOWN';
}

function resolveConfidenceCategory(facts: ConsumerDataQualityFacts): ConsumerDataQualityConfidenceCategory {
  if (facts.sourceAuthorityDenied || facts.scoreContributionDenied || facts.observationOnly || facts.isFallback || facts.isProxy) {
    return 'LIMITED';
  }
  if (typeof facts.confidence !== 'number') return 'UNKNOWN';
  if (facts.confidence >= 0.75) return 'HIGH';
  if (facts.confidence >= 0.5) return 'MEDIUM';
  return 'LOW';
}

export function createConsumerDataQualityViewModel(
  input: ConsumerDataQualityInput,
): ConsumerDataQualityViewModel {
  const facts = collectFacts(input);
  const status = resolveStatus(facts);
  const statusMessage = STATUS_MESSAGES[status];
  const viewModel: ConsumerDataQualityViewModel = {
    status,
    confidenceCategory: resolveConfidenceCategory(facts),
    freshnessCategory: resolveFreshnessCategory(facts),
    messageKey: statusMessage.key,
    message: statusMessage.message,
    isActionableForUser: status === 'UNAVAILABLE',
  };

  if (facts.asOf) {
    viewModel.asOf = facts.asOf;
  }
  if (facts.updatedAt) {
    viewModel.updatedAt = facts.updatedAt;
  }

  return viewModel;
}
