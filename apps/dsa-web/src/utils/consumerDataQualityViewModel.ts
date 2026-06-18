export type ConsumerDataQualityStatus =
  | 'AVAILABLE'
  | 'UPDATING'
  | 'DELAYED'
  | 'PARTIAL'
  | 'INSUFFICIENT'
  | 'PAUSED'
  | 'UNAVAILABLE'
  | 'OBSERVATION_ONLY';

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

export type ConsumerDataHealthState =
  | 'healthy'
  | 'partial'
  | 'stale'
  | 'degraded'
  | 'unavailable';

export type ConsumerDataHealthCategory =
  | 'marketBreadth'
  | 'themeRotation'
  | 'stockEvidence'
  | 'peerComparison'
  | 'portfolioExposure'
  | 'optionsStructure'
  | 'researchQueueFreshness';

export type ConsumerDataHealthLocale = 'zh' | 'en';

export interface ConsumerDataHealthSummaryInputItem {
  category: ConsumerDataHealthCategory;
  quality?: ConsumerDataQualityInput | null;
}

export interface ConsumerDataHealthSummaryInput {
  locale?: ConsumerDataHealthLocale;
  categories: ConsumerDataHealthSummaryInputItem[];
}

export interface ConsumerDataHealthSummaryItem {
  category: ConsumerDataHealthCategory;
  state: ConsumerDataHealthState;
  label: string;
  stateLabel: string;
  whyItMatters: string;
  confidenceEffect: string;
  nextResearchStep: string;
}

export interface ConsumerDataHealthSummary {
  overallState: ConsumerDataHealthState;
  items: ConsumerDataHealthSummaryItem[];
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
  sourceAuthorityGranted: boolean;
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
  OBSERVATION_ONLY: {
    key: 'dataQuality.observation',
    message: '当前仅供观察。',
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
    sourceAuthorityGranted: booleanValue(primitiveFacts.booleans, ['sourceAuthorityAllowed', 'source_authority_allowed']),
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
  if (facts.observationOnly) return 'OBSERVATION_ONLY';
  if (lowCoverage || lowConfidence) return 'INSUFFICIENT';
  if (facts.isStale || facts.isFallback || facts.isProxy || containsAny(facts.freshnessText, DELAYED_MARKERS)) return 'DELAYED';
  if (!facts.sourceAuthorityGranted || facts.scoreContributionDenied) return 'INSUFFICIENT';
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

function resolveConfidenceCategory(
  facts: ConsumerDataQualityFacts,
  status: ConsumerDataQualityStatus,
): ConsumerDataQualityConfidenceCategory {
  if (
    facts.sourceAuthorityDenied
    || facts.scoreContributionDenied
    || facts.observationOnly
    || facts.isFallback
    || facts.isProxy
    || (status === 'INSUFFICIENT' && !facts.sourceAuthorityGranted)
  ) {
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
    confidenceCategory: resolveConfidenceCategory(facts, status),
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

type ConsumerDataHealthCategoryCopy = Record<
  ConsumerDataHealthCategory,
  Record<ConsumerDataHealthLocale, {
    label: string;
    whyItMatters: string;
    nextStep: string;
  }>
>;

const DATA_HEALTH_CATEGORY_COPY: ConsumerDataHealthCategoryCopy = {
  marketBreadth: {
    zh: {
      label: '市场广度',
      whyItMatters: '广度影响市场背景和参与度判断。',
      nextStep: '继续观察广度参与是否稳定。',
    },
    en: {
      label: 'Market breadth',
      whyItMatters: 'Breadth shapes market context and participation reads.',
      nextStep: 'Keep checking whether participation remains stable.',
    },
  },
  themeRotation: {
    zh: {
      label: '主题轮动',
      whyItMatters: '轮动质量影响主题延续性的解读。',
      nextStep: '复核主题是否仍由多组证据支持。',
    },
    en: {
      label: 'Theme rotation',
      whyItMatters: 'Rotation quality affects how theme durability is interpreted.',
      nextStep: 'Review whether themes remain supported by several evidence groups.',
    },
  },
  stockEvidence: {
    zh: {
      label: '个股证据',
      whyItMatters: '个股证据决定结构解读是否完整。',
      nextStep: '补齐缺口后再扩大结论范围。',
    },
    en: {
      label: 'Stock evidence',
      whyItMatters: 'Stock evidence determines whether structure reads are complete.',
      nextStep: 'Fill evidence gaps before widening the conclusion.',
    },
  },
  peerComparison: {
    zh: {
      label: '同业比较',
      whyItMatters: '同业证据帮助区分个股变化和板块同步。',
      nextStep: '复核同业样本和对比窗口。',
    },
    en: {
      label: 'Peer comparison',
      whyItMatters: 'Peer evidence helps separate symbol-specific moves from group behavior.',
      nextStep: 'Review peer samples and the comparison window.',
    },
  },
  portfolioExposure: {
    zh: {
      label: '组合暴露',
      whyItMatters: '组合暴露影响风险归因和集中度观察。',
      nextStep: '等组合暴露证据恢复后再解读影响。',
    },
    en: {
      label: 'Portfolio exposure',
      whyItMatters: 'Portfolio exposure affects risk attribution and concentration reads.',
      nextStep: 'Wait for exposure evidence before interpreting portfolio impact.',
    },
  },
  optionsStructure: {
    zh: {
      label: '期权结构',
      whyItMatters: '期权结构影响波动和 gamma 观察边界。',
      nextStep: '仅在结构证据恢复后阅读期权语境。',
    },
    en: {
      label: 'Options structure',
      whyItMatters: 'Options structure affects volatility and gamma observation boundaries.',
      nextStep: 'Read options context only after structure evidence recovers.',
    },
  },
  researchQueueFreshness: {
    zh: {
      label: '研究队列时效',
      whyItMatters: '队列时效影响后续复核顺序。',
      nextStep: '先复核需要更新的研究条目。',
    },
    en: {
      label: 'Research queue freshness',
      whyItMatters: 'Queue freshness affects follow-up review order.',
      nextStep: 'Review items that need updates first.',
    },
  },
};

const DATA_HEALTH_STATE_LABELS: Record<ConsumerDataHealthState, Record<ConsumerDataHealthLocale, string>> = {
  healthy: { zh: '健康', en: 'Healthy' },
  partial: { zh: '部分可用', en: 'Partial' },
  stale: { zh: '已延迟', en: 'Stale' },
  degraded: { zh: '降级', en: 'Degraded' },
  unavailable: { zh: '不可用', en: 'Unavailable' },
};

const DATA_HEALTH_CONFIDENCE_EFFECT: Record<ConsumerDataHealthState, Record<ConsumerDataHealthLocale, string>> = {
  healthy: {
    zh: '置信度可按正常研究边界阅读。',
    en: 'Confidence can be read within the normal research boundary.',
  },
  partial: {
    zh: '置信度需要打折，避免过度精确解读。',
    en: 'Confidence should be discounted; avoid over-precise reads.',
  },
  stale: {
    zh: '置信度受时效影响，只适合观察趋势。',
    en: 'Confidence is freshness-limited; use it for trend observation only.',
  },
  degraded: {
    zh: '置信度受证据质量限制，需要交叉复核。',
    en: 'Confidence is limited by evidence quality and needs cross-checking.',
  },
  unavailable: {
    zh: '置信度不足，当前不应扩大结论。',
    en: 'Confidence is insufficient; do not widen the conclusion.',
  },
};

const HEALTH_STATE_RANK: Record<ConsumerDataHealthState, number> = {
  healthy: 0,
  partial: 1,
  stale: 2,
  degraded: 3,
  unavailable: 4,
};

function resolveHealthState(view: ConsumerDataQualityViewModel): ConsumerDataHealthState {
  if (view.status === 'UNAVAILABLE') return 'unavailable';
  if (view.status === 'PARTIAL') {
    return 'partial';
  }
  if (view.status === 'DELAYED' || view.freshnessCategory === 'STALE' || view.freshnessCategory === 'DELAYED') {
    return 'stale';
  }
  if (
    view.status === 'INSUFFICIENT'
    || view.status === 'PAUSED'
    || view.status === 'OBSERVATION_ONLY'
    || view.status === 'UPDATING'
    || view.confidenceCategory === 'LOW'
    || view.confidenceCategory === 'LIMITED'
  ) {
    return 'degraded';
  }
  return 'healthy';
}

function compareHealthState(left: ConsumerDataHealthState, right: ConsumerDataHealthState): ConsumerDataHealthState {
  return HEALTH_STATE_RANK[left] >= HEALTH_STATE_RANK[right] ? left : right;
}

function resolveHealthStateFromInput(
  input: ConsumerDataQualityInput | null | undefined,
  view: ConsumerDataQualityViewModel,
): ConsumerDataHealthState {
  const status = normalizeText(input?.status ?? input?.state);
  const freshness = normalizeText(input?.freshness ?? input?.freshnessState);

  if (['ready', 'available', 'healthy', 'current', 'complete'].includes(status)) {
    return freshness === 'stale' || freshness === 'delayed' ? 'stale' : 'healthy';
  }
  if (['partial', 'mixed', 'thin'].includes(status)) return 'partial';
  if (['stale', 'needs_review', 'delayed'].includes(status) || ['stale', 'delayed'].includes(freshness)) return 'stale';
  if (['degraded', 'limited', 'updating', 'refreshing'].includes(status)) return 'degraded';
  if (['unavailable', 'missing', 'blocked', 'no_evidence', 'empty', 'error'].includes(status)) return 'unavailable';

  return resolveHealthState(view);
}

export function createConsumerDataHealthSummary(
  input: ConsumerDataHealthSummaryInput,
): ConsumerDataHealthSummary {
  const locale = input.locale === 'en' ? 'en' : 'zh';
  const items = input.categories.map((item) => {
    const view = createConsumerDataQualityViewModel(item.quality ?? {});
    const state = resolveHealthStateFromInput(item.quality, view);
    const categoryCopy = DATA_HEALTH_CATEGORY_COPY[item.category][locale];
    return {
      category: item.category,
      state,
      label: categoryCopy.label,
      stateLabel: DATA_HEALTH_STATE_LABELS[state][locale],
      whyItMatters: categoryCopy.whyItMatters,
      confidenceEffect: DATA_HEALTH_CONFIDENCE_EFFECT[state][locale],
      nextResearchStep: categoryCopy.nextStep,
    };
  });

  return {
    overallState: items.reduce<ConsumerDataHealthState>(
      (current, item) => compareHealthState(current, item.state),
      'healthy',
    ),
    items,
  };
}
