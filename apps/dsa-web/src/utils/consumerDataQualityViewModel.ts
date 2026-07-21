export type ConsumerDataQualityStatus =
  | 'AVAILABLE'
  | 'UPDATING'
  | 'DELAYED'
  | 'PARTIAL'
  | 'INSUFFICIENT'
  | 'PAUSED'
  | 'UNAVAILABLE'
  | 'OBSERVATION_ONLY';

type OptionalFields<Key extends PropertyKey, Value> = Partial<Record<Key, Value>>;

export type MarketObservationTruthInput =
  & OptionalFields<
    | 'source' | 'sourceLabel' | 'sourceClass' | 'sourceType' | 'sourceTier' | 'trustLevel'
    | 'providerClass' | 'providerTier' | 'quoteMode' | 'dataBoundary' | 'sampleState'
    | 'freshness' | 'freshnessState' | 'freshnessLabel' | 'freshnessFloor'
    | 'readiness' | 'readinessState' | 'calculationState' | 'overallState' | 'chainState' | 'status' | 'dataQualityState'
    | 'authorityState' | 'sourceAuthority' | 'sourceAuthorityState' | 'scoreAuthority'
    | 'evidencePosture' | 'consumerSafeMessage'
    | 'observedAt' | 'marketTime' | 'providerTime' | 'receivedAt'
    | 'generatedAt' | 'asOf' | 'updatedAt' | 'expiresAt',
    string
  >
  & OptionalFields<
    | 'domainReady' | 'runtimeAvailable' | 'observationOnly' | 'decisionGrade'
    | 'sourceAuthorityAllowed' | 'scoreContributionAllowed' | 'scoreAuthorityAllowed'
    | 'scoreAuthorityEligible' | 'sourceAuthorityRouteRejected'
    | 'isProxy' | 'isFallback' | 'isSynthetic' | 'isFixture' | 'isStale' | 'isPartial'
    | 'isUnavailable' | 'isRefreshing' | 'includedInScore' | 'contributesToScore'
    | 'proxyOnly' | 'fallbackUsed' | 'malformed' | 'incomplete'
    | 'noAdvice' | 'noAdviceBoundary' | 'blocked',
    boolean
  >
  & OptionalFields<
    | 'confidence' | 'confidenceWeight' | 'confidence_weight'
    | 'scoreConfidence' | 'score_confidence' | 'confidenceCap',
    number
  >
  & OptionalFields<
    | 'reasonCodes' | 'confidenceCapReasons' | 'confidenceReasons' | 'capReasons'
    | 'missingFamilies' | 'blockedReasons' | 'blockingReasons' | 'missingDataFamilies'
    | 'missingEvidence' | 'missingInputs' | 'staleInputs' | 'blockedInputs' | 'blockedSeries'
    | 'observationOnlyInputs' | 'scoreGradeInputs' | 'evidenceLabels',
    string[]
  >
  & {
    availability?: string | boolean;
    providerObservation?: OptionalFields<
      'sourceClass' | 'sourceType' | 'sourceTier' | 'sourceAuthority' | 'authorityState' | 'scoreAuthority' | 'score_authority',
      string | null
    > & OptionalFields<
      | 'proxyOnly' | 'observationOnly' | 'observation_only'
      | 'sourceAuthorityAllowed' | 'source_authority_allowed'
      | 'scoreContributionAllowed' | 'score_contribution_allowed',
      boolean | null
    > | null;
    providerFreshness?: OptionalFields<'state', string | null>
      & OptionalFields<'isStale' | 'isUnavailable', boolean | null> | null;
    dataQuality?: OptionalFields<'state' | 'freshness', string | null>
      & OptionalFields<'available', boolean | null> | null;
  };

type NullableMarketObservationTruthInput = {
  [Key in keyof MarketObservationTruthInput]?: MarketObservationTruthInput[Key] | null;
};

export interface MarketTruthProjection {
  source: {
    identity?: string;
    label?: string;
    /** Unknown is intentional when backend source metadata is absent. */
    class: 'official' | 'licensed' | 'proxy' | 'fallback' | 'synthetic' | 'fixture' | 'unknown';
    authority: 'allowed' | 'denied' | 'unknown';
  };
  freshness:
    | 'live' | 'fresh' | 'aging' | 'delayed' | 'cached' | 'stale' | 'expired' | 'partial' | 'fallback' | 'proxy'
    | 'mock' | 'synthetic' | 'fixture' | 'malformed' | 'incomplete' | 'blocked' | 'error' | 'unavailable' | 'not_checked' | 'unknown';
  availability: 'available' | 'partial' | 'unavailable' | 'malformed' | 'incomplete' | 'missing' | 'blocked' | 'not_checked' | 'unknown';
  readiness: 'ready' | 'partial' | 'insufficient' | 'not_ready' | 'blocked' | 'unavailable' | 'malformed' | 'incomplete' | 'missing' | 'not_checked' | 'unknown';
  runtimeAvailability: 'available' | 'unavailable' | 'unknown';
  observationOnly?: boolean;
  decisionGrade?: boolean;
  mode: 'decision_grade' | 'observation_only' | 'unknown';
  scoreContribution: 'eligible' | 'ineligible' | 'unknown';
  evidencePosture: 'blocked' | 'insufficient' | 'observation_only' | 'review_required' | 'metadata_only' | 'unknown';
  confidence: {
    value?: number;
    cap?: number;
    category: ConsumerDataQualityConfidenceCategory;
    reasons: string[];
  };
  timestamps: Partial<Record<
    'observedAt' | 'marketTime' | 'providerTime' | 'receivedAt' | 'generatedAt' | 'asOf' | 'updatedAt' | 'expiresAt',
    string
  >>;
  limitation: {
    noAdvice: boolean;
    blocked: boolean;
    reasonCodes: string[];
    missingFamilies: string[];
    consumerSafeMessage?: string;
  };
  consumer: {
    status: ConsumerDataQualityStatus;
    freshnessCategory: ConsumerDataQualityFreshnessCategory;
    messageKey: string;
    message: string;
    isActionableForUser: boolean;
  };
}

type MarketTruthSourceClass = MarketTruthProjection['source']['class'];
type MarketTruthFreshness = MarketTruthProjection['freshness'];
type MarketTruthAvailability = MarketTruthProjection['availability'];
type MarketTruthReadiness = MarketTruthProjection['readiness'];

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

export type ConsumerDataQualityInput = NullableMarketObservationTruthInput & Record<string, unknown>;

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
  supportingNotes?: string[];
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
  supportingNotes?: string[];
}

export interface ConsumerDataHealthSummary {
  overallState: ConsumerDataHealthState;
  items: ConsumerDataHealthSummaryItem[];
}

const STATUS_MESSAGES: Record<ConsumerDataQualityStatus, readonly [key: string, message: string]> = {
  AVAILABLE: ['dataQuality.available', '当前数据可用于观察。'],
  UPDATING: ['dataQuality.updating', '数据更新中，稍后将自动刷新。'],
  DELAYED: ['dataQuality.delayed', '已使用最近一次可用数据。'],
  PARTIAL: ['dataQuality.partial', '部分数据暂不可用。'],
  INSUFFICIENT: ['dataQuality.insufficient', '当前信号置信度较低，仅供观察。'],
  PAUSED: ['dataQuality.paused', '部分数据暂不可用，当前评分已暂停。'],
  UNAVAILABLE: ['dataQuality.unavailable', '本模块暂不可用，请稍后重试。'],
  OBSERVATION_ONLY: ['dataQuality.observation', '当前仅供观察。'],
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function readFirst<T>(
  input: Record<string, unknown>,
  keys: readonly string[],
  guard: (value: unknown) => value is T,
): T | undefined {
  for (const key of keys) {
    const value = input[key];
    if (guard(value)) return value;
  }
  return undefined;
}

function readNumber(input: Record<string, unknown>, keys: readonly string[]): number | undefined {
  return readFirst(input, keys, (value): value is number => typeof value === 'number' && Number.isFinite(value));
}

const FRESHNESS_STATES = new Set<MarketTruthFreshness>([
  'live', 'fresh', 'aging', 'delayed', 'cached', 'stale', 'expired', 'partial', 'fallback', 'mock',
  'synthetic', 'fixture', 'malformed', 'incomplete', 'blocked', 'error', 'unavailable', 'not_checked', 'unknown',
  'proxy',
]);

function readBoolean(input: Record<string, unknown>, keys: readonly string[]): boolean | undefined {
  return readFirst(input, keys, (value): value is boolean => typeof value === 'boolean');
}

function readList(input: Record<string, unknown>, keys: readonly string[]): string[] {
  const value = readFirst<unknown[]>(input, keys, Array.isArray);
  return value?.filter((item): item is string => typeof item === 'string' && item.trim().length > 0) ?? [];
}

function readValue(input: Record<string, unknown>, keys: readonly string[]): unknown {
  return readFirst(input, keys, (value): value is unknown => value !== undefined && value !== null);
}

function normalizeTruthToken(value: unknown): string {
  return typeof value === 'string' ? value.trim().toLowerCase().replace(/[\s-]+/g, '_') : '';
}

function nestedRecord(input: Record<string, unknown>, key: string): Record<string, unknown> {
  return isRecord(input[key]) ? input[key] : {};
}

function sourceClassFor(input: ConsumerDataQualityInput): MarketTruthSourceClass {
  const providerObservation = nestedRecord(input, 'providerObservation');
  const candidates = [
    ...['sourceClass', 'sourceType', 'sourceTier', 'providerClass', 'providerTier', 'quoteMode', 'dataBoundary', 'sampleState', 'source']
      .map((key) => input[key]),
    providerObservation.sourceClass,
    providerObservation.sourceType,
    providerObservation.sourceTier,
  ].map(normalizeTruthToken).filter(Boolean);
  const rules: Array<[MarketTruthSourceClass, boolean, string[]]> = [
    ['fixture', input.isFixture === true, ['fixture', 'demo', 'sample', 'mock']],
    ['synthetic', input.isSynthetic === true, ['synthetic']],
    ['proxy', input.isProxy === true || input.proxyOnly === true || providerObservation.proxyOnly === true, ['proxy', 'unofficial_public_api']],
    ['fallback', input.isFallback === true || input.fallbackUsed === true, ['fallback']],
    ['licensed', false, ['licensed', 'licensed_feed', 'authorized_licensed']],
    ['official', false, ['official', 'official_public', 'official_api', 'official_exchange', 'exchange_public']],
  ];
  return rules.find(([, explicit, markers]) => explicit || candidates.some((token) => markers.some((marker) => (
    token === marker || token.startsWith(`${marker}_`) || token.endsWith(`_${marker}`) || token.includes(`_${marker}_`)
  ))))?.[0] ?? 'unknown';
}

const ALLOWED_AUTHORITY_TOKENS = ['allowed', 'authorized', 'authoritative', 'available', 'eligible', 'score_grade', 'score_grade_allowed', 'scoregradeallowed', 'trusted_public', 'stored_snapshot'];
const DENIED_AUTHORITY_TOKENS = ['denied', 'blocked', 'unauthorized', 'unavailable', 'observation_only', 'observationonly', 'not_authoritative', 'fixture'];
const ALLOWED_SCORE_TOKENS = ['allowed', 'authorized', 'authoritative', 'eligible', 'score_grade', 'score_grade_allowed', 'scoregradeallowed'];
const DENIED_SCORE_TOKENS = ['denied', 'blocked', 'unavailable', 'observation_only', 'observationonly', 'observe_only', 'not_eligible'];

function permissionFor(
  value: unknown,
  allowed = ALLOWED_AUTHORITY_TOKENS,
  denied = DENIED_AUTHORITY_TOKENS,
): MarketTruthProjection['source']['authority'] {
  const token = normalizeTruthToken(value);
  if (allowed.includes(token)) return 'allowed';
  if (denied.includes(token)) return 'denied';
  return 'unknown';
}

function permissionBoolean(value: unknown): boolean | undefined {
  const permission = permissionFor(value, ALLOWED_SCORE_TOKENS, DENIED_SCORE_TOKENS);
  return permission === 'allowed' ? true : permission === 'denied' ? false : undefined;
}

function authorityFor(input: ConsumerDataQualityInput): MarketTruthProjection['source']['authority'] {
  const observation = nestedRecord(input, 'providerObservation');
  const direct = readBoolean(input, ['sourceAuthorityAllowed']);
  const nested = readBoolean(observation, ['sourceAuthorityAllowed', 'source_authority_allowed']);
  if (direct === true || nested === true) return 'allowed';
  if (direct === false || nested === false || input.sourceAuthorityRouteRejected === true) return 'denied';
  return permissionFor(
    readValue(input, ['sourceAuthority', 'authorityState', 'sourceAuthorityState'])
      ?? readValue(observation, ['sourceAuthority', 'authorityState']),
  );
}

function freshnessFor(input: ConsumerDataQualityInput): MarketTruthFreshness {
  const providerFreshness = nestedRecord(input, 'providerFreshness');
  const raw = normalizeTruthToken(
    readValue(input, ['freshness', 'freshnessState', 'freshnessFloor', 'freshnessLabel'])
      ?? providerFreshness.state ?? nestedRecord(input, 'dataQuality').freshness,
  );
  if (raw === 'refreshing' || raw === 'pending' || raw === 'initializing') return 'not_checked';
  if (FRESHNESS_STATES.has(raw as MarketTruthFreshness)) {
    return raw as MarketTruthFreshness;
  }
  const evidenceTokens = readList(input, ['evidenceLabels']).map(normalizeTruthToken);
  if (evidenceTokens.some((token) => token.includes('stale') || token.includes('expired') || token.includes('数据已过期'))) return 'stale';
  if (evidenceTokens.some((token) => token.includes('delayed'))) return 'delayed';
  if (evidenceTokens.some((token) => token.includes('cached'))) return 'cached';
  if (evidenceTokens.some((token) => token.includes('fallback') || token.includes('备用数据'))) return 'fallback';
  if (readList(input, ['staleInputs']).length) return 'stale';
  if (input.isRefreshing === true) return 'not_checked';
  if (input.isStale === true || providerFreshness.isStale === true) return 'stale';
  return 'unknown';
}

function availabilityFor(input: ConsumerDataQualityInput): MarketTruthAvailability {
  const quality = nestedRecord(input, 'dataQuality');
  const providerFreshness = nestedRecord(input, 'providerFreshness');
  const explicit = input.availability ?? (input.dataBoundary === 'unavailable' ? 'unavailable' : input.chainState);
  if (explicit === true) return 'available';
  if (explicit === false) return 'unavailable';
  if (input.isUnavailable === true || providerFreshness.isUnavailable === true) return 'unavailable';
  const token = normalizeTruthToken(explicit ?? input.dataQualityState ?? quality.state ?? input.status);
  if (token === 'available' || token === 'success' || token === 'ready' || token === 'live') return 'available';
  if (['partial', 'degraded', 'insufficient_history', 'observation_only', 'observe_only'].includes(token)) return 'partial';
  if (token === 'incomplete' || token === 'insufficient') return 'incomplete';
  if (token === 'malformed' || token === 'invalid') return 'malformed';
  if (token === 'missing' || token === 'no_evidence' || token === 'configured_missing' || token === 'not_configured' || token === 'not_implemented') return 'missing';
  if (token === 'blocked' || token === 'rejected' || token === 'failed_closed' || token === 'entitlement_required') return 'blocked';
  if (token === 'not_checked' || token === 'pending' || token === 'initializing' || token === 'refreshing') return 'not_checked';
  if (token === 'unavailable' || token === 'error' || token === 'failure' || token === 'failed') return 'unavailable';
  const source = normalizeTruthToken(input.source);
  if (
    quality.available === false
    || ['unavailable', 'error'].includes(source)
  ) return 'unavailable';
  if (input.malformed === true) return 'malformed';
  if (input.incomplete === true) return 'incomplete';
  if (input.isPartial === true) return 'partial';
  if (quality.available === true) return 'available';
  if (readList(input, ['blockedInputs', 'blockedSeries']).length) return 'blocked';
  if (readList(input, ['missingInputs']).length) return 'missing';
  if (readList(input, ['staleInputs']).length || readList(input, ['observationOnlyInputs']).length) return 'partial';
  return 'unknown';
}

function readinessFor(input: ConsumerDataQualityInput): MarketTruthReadiness {
  const token = normalizeTruthToken(input.readinessState ?? input.readiness ?? input.calculationState ?? input.overallState);
  if (token === 'blocked' || token === 'failed_closed' || token === 'entitlement_required' || token === 'unauthorized') return 'blocked';
  if (input.blocked === true || readList(input, ['blockedInputs', 'blockedSeries']).length) return 'blocked';
  if (input.domainReady === true) return 'ready';
  if (input.domainReady === false) return 'not_ready';
  if (['ready', 'success', 'supportive', 'product_ready', 'available', 'score_grade'].includes(token)) return 'ready';
  if (['partial', 'mixed', 'insufficient_history', 'observation_only', 'observe_only'].includes(token)) return 'partial';
  if (['degraded', 'limited', 'insufficient', 'data_insufficient', 'no_evidence'].includes(token)) return 'insufficient';
  if (token === 'not_ready') return 'not_ready';
  if (token === 'unavailable') return 'unavailable';
  if (token === 'malformed' || token === 'invalid') return 'malformed';
  if (token === 'incomplete') return 'incomplete';
  if (token === 'missing') return 'missing';
  if (token === 'not_checked' || token === 'waiting' || token === 'pending' || token === 'initializing' || token === 'refreshing') return 'not_checked';
  return 'unknown';
}

function evidencePostureFor(input: ConsumerDataQualityInput): MarketTruthProjection['evidencePosture'] {
  const tokens = [
    ...['evidencePosture', 'readinessState', 'readiness', 'authorityState', 'sourceAuthority', 'sourceAuthorityState', 'scoreAuthority']
      .map((key) => input[key]),
    ...readList(input, ['evidenceLabels']),
  ].map(normalizeTruthToken).filter(Boolean);
  const rules: Array<[MarketTruthProjection['evidencePosture'], boolean, string[]]> = [
    ['blocked', input.blocked === true, ['blocked', '数据不足_禁止判断', '禁止判断']],
    ['review_required', false, ['review_required', '需人工复核']],
    ['metadata_only', false, ['allowed_metadata_only', '依据需复核']],
    ['insufficient', false, ['insufficient_evidence', 'insufficient']],
    ['observation_only', input.observationOnly === true, ['observation_only', 'observe_only', 'research_prototype', 'proxy_only', '仅观察', '仅供观察', '仅供风险观察']],
  ];
  return rules.find(([, explicit, markers]) => (
    explicit || tokens.some((token) => markers.some((marker) => token === marker || token.includes(marker)))
  ))?.[0] ?? 'unknown';
}

function consumerStatusFor(
  projection: Pick<MarketTruthProjection, 'availability' | 'readiness' | 'freshness' | 'source' | 'observationOnly' | 'scoreContribution' | 'evidencePosture' | 'confidence' | 'limitation'>,
): ConsumerDataQualityStatus {
  if (['unavailable', 'malformed', 'missing', 'blocked'].includes(projection.availability)) return 'UNAVAILABLE';
  if (projection.readiness === 'blocked') return 'PAUSED';
  if (['unavailable', 'malformed', 'missing', 'insufficient', 'not_ready'].includes(projection.readiness)) return 'INSUFFICIENT';
  if (projection.evidencePosture === 'insufficient') return 'INSUFFICIENT';
  if (projection.freshness === 'not_checked' && ['unknown', 'not_checked'].includes(projection.availability)) return 'UPDATING';
  if (
    projection.observationOnly === true
    && (projection.limitation.blocked || projection.source.authority === 'denied')
  ) return 'PAUSED';
  if (
    ['partial', 'incomplete'].includes(projection.availability)
    || ['partial', 'incomplete'].includes(projection.readiness)
    || projection.freshness === 'incomplete'
    || projection.freshness === 'partial'
  ) return 'PARTIAL';
  if (['stale', 'expired', 'fallback', 'mock', 'synthetic', 'fixture', 'aging', 'delayed', 'cached'].includes(projection.freshness)) return 'DELAYED';
  if (['fallback', 'synthetic', 'fixture'].includes(projection.source.class)) return 'DELAYED';
  if (
    projection.observationOnly === true
    && !['proxy', 'fallback', 'synthetic', 'fixture'].includes(projection.source.class)
  ) return 'OBSERVATION_ONLY';
  if (projection.readiness === 'not_checked') return 'UPDATING';
  if (projection.scoreContribution === 'ineligible') return 'INSUFFICIENT';
  if (
    projection.source.authority === 'denied'
    || projection.source.authority === 'unknown' && ['live', 'fresh'].includes(projection.freshness)
    || (projection.confidence.value !== undefined && projection.confidence.value < 0.5)
  ) return 'INSUFFICIENT';
  if (['unknown', 'missing', 'not_checked'].includes(projection.availability) || projection.freshness === 'unknown') return 'INSUFFICIENT';
  return 'AVAILABLE';
}

/** The single market fact-to-consumer projection; domain value presence never establishes truth. */
export function projectMarketTruth(input: NullableMarketObservationTruthInput | null | undefined): MarketTruthProjection {
  const facts = (input && typeof input === 'object' ? input : {}) as ConsumerDataQualityInput;
  const sourceClass = sourceClassFor(facts);
  const authority = authorityFor(facts);
  const freshness = freshnessFor(facts);
  const availability = availabilityFor(facts);
  const readiness = readinessFor(facts);
  const runtimeAvailable = readBoolean(facts, ['runtimeAvailable']);
  const runtimeAvailability: MarketTruthProjection['runtimeAvailability'] = runtimeAvailable === true
    ? 'available'
    : runtimeAvailable === false ? 'unavailable' : 'unknown';
  const providerObservation = nestedRecord(facts, 'providerObservation');
  const evidencePosture = evidencePostureFor(facts);
  const observationOnly = readBoolean(facts, ['observationOnly'])
    ?? readBoolean(providerObservation, ['observationOnly', 'observation_only'])
    ?? (readList(facts, ['observationOnlyInputs']).length ? true : undefined)
    ?? (evidencePosture === 'observation_only' ? true : undefined);
  const scoreFlag = readBoolean(facts, [
    'scoreContributionAllowed',
    'scoreAuthorityAllowed',
    'scoreAuthorityEligible',
    'includedInScore',
    'contributesToScore',
  ])
    ?? readBoolean(providerObservation, ['scoreContributionAllowed', 'score_contribution_allowed'])
    ?? permissionBoolean(facts.scoreAuthority ?? providerObservation.scoreAuthority ?? providerObservation.score_authority)
    ?? permissionBoolean(facts.readinessState);
  const scoreEvidenceBlocked = observationOnly === true
    || [
      'delayed', 'stale', 'expired', 'partial', 'fallback', 'proxy', 'mock', 'synthetic', 'fixture',
      'malformed', 'incomplete', 'blocked', 'error', 'unavailable', 'not_checked',
    ].includes(freshness)
    || ['partial', 'unavailable', 'malformed', 'incomplete', 'missing', 'blocked', 'not_checked'].includes(availability)
    || [
      'partial', 'insufficient', 'not_ready', 'blocked', 'unavailable', 'malformed', 'incomplete', 'missing', 'not_checked',
    ].includes(readiness);
  const scoreContribution: MarketTruthProjection['scoreContribution'] = scoreFlag === false
    || authority === 'denied'
    || ['proxy', 'fallback', 'synthetic', 'fixture'].includes(sourceClass)
    || scoreEvidenceBlocked
    ? 'ineligible'
    : scoreFlag === true && authority === 'allowed' ? 'eligible' : 'unknown';
  const explicitDecisionGrade = readBoolean(facts, ['decisionGrade']);
  const decisionGrade = explicitDecisionGrade === true
    ? scoreContribution === 'eligible'
      && observationOnly !== true
      && readiness === 'ready'
      && availability === 'available'
    : explicitDecisionGrade === false || observationOnly === true
      ? false
      : undefined;
  const mode: MarketTruthProjection['mode'] = observationOnly === true
    ? 'observation_only'
    : decisionGrade === true ? 'decision_grade' : 'unknown';
  const confidenceValue = readNumber(facts, ['confidence', 'confidenceWeight', 'confidence_weight', 'scoreConfidence', 'score_confidence']);
  const cap = typeof facts.confidenceCap === 'number' && Number.isFinite(facts.confidenceCap) ? facts.confidenceCap : undefined;
  const consumerConfidence = cap === undefined
    ? confidenceValue
    : confidenceValue === undefined ? cap : Math.min(confidenceValue, cap);
  const reasons = readList(facts, ['confidenceCapReasons', 'confidenceReasons', 'capReasons', 'reasonCodes']);
  const limited = authority === 'denied'
    || scoreFlag === false
    || observationOnly === true
    || ['proxy', 'fallback', 'synthetic', 'fixture'].includes(sourceClass)
    || authority === 'unknown' && ['live', 'fresh'].includes(freshness);
  const confidenceCategory: ConsumerDataQualityConfidenceCategory = limited
    ? 'LIMITED'
    : consumerConfidence === undefined ? 'UNKNOWN'
      : consumerConfidence >= 0.75 ? 'HIGH' : consumerConfidence >= 0.5 ? 'MEDIUM' : 'LOW';
  const reasonCodes = readList(facts, ['reasonCodes', 'blockedReasons', 'blockingReasons']);
  const missingFamilies = readList(facts, ['missingFamilies', 'missingDataFamilies', 'missingEvidence']);
  const blocked = facts.blocked === true
    || readiness === 'blocked'
    || availability === 'blocked'
    || evidencePosture === 'blocked';
  const timestamps: MarketTruthProjection['timestamps'] = {};
  for (const key of ['observedAt', 'marketTime', 'providerTime', 'receivedAt', 'generatedAt', 'asOf', 'updatedAt', 'expiresAt'] as const) {
    const value = facts[key];
    if (typeof value === 'string' && value.trim()) timestamps[key] = value;
  }
  const projectionBase = {
    source: {
      identity: typeof facts.source === 'string' && facts.source.trim() ? facts.source : undefined,
      label: typeof facts.sourceLabel === 'string' && facts.sourceLabel.trim() ? facts.sourceLabel : undefined,
      class: sourceClass,
      authority,
    },
    freshness,
    availability,
    readiness,
    runtimeAvailability,
    observationOnly,
    decisionGrade,
    mode,
    evidencePosture,
    scoreContribution,
    confidence: {
      value: confidenceValue,
      cap,
      category: confidenceCategory,
      reasons,
    },
    timestamps,
    limitation: {
      noAdvice: facts.noAdvice === true || facts.noAdviceBoundary === true,
      blocked,
      reasonCodes,
      missingFamilies,
      consumerSafeMessage: typeof facts.consumerSafeMessage === 'string' && facts.consumerSafeMessage.trim()
        ? facts.consumerSafeMessage
        : undefined,
    },
  } as Omit<MarketTruthProjection, 'consumer'>;
  const consumerStatus = consumerStatusFor(projectionBase);
  const [messageKey, message] = STATUS_MESSAGES[consumerStatus];
  const freshnessCategory: ConsumerDataQualityFreshnessCategory = ['unavailable', 'error', 'malformed', 'blocked'].includes(freshness)
    ? 'UNAVAILABLE'
    : ['stale', 'expired', 'fallback', 'mock', 'synthetic', 'fixture'].includes(freshness) ? 'STALE'
      : ['delayed', 'aging', 'proxy'].includes(freshness) ? 'DELAYED'
        : freshness === 'cached' ? 'RECENT' : ['live', 'fresh'].includes(freshness) ? 'CURRENT' : 'UNKNOWN';
  return {
    ...projectionBase,
    consumer: {
      status: consumerStatus,
      freshnessCategory: ['CURRENT', 'UNKNOWN'].includes(freshnessCategory) && ['fallback', 'synthetic', 'fixture'].includes(sourceClass)
        ? 'STALE' : freshnessCategory,
      messageKey,
      message,
      isActionableForUser: consumerStatus === 'UNAVAILABLE',
    },
  };
}

export function createConsumerDataQualityViewModel(input: ConsumerDataQualityInput): ConsumerDataQualityViewModel {
  const projection = projectMarketTruth(input);
  const viewModel: ConsumerDataQualityViewModel = {
    ...projection.consumer,
    confidenceCategory: projection.confidence.category,
  };
  if (projection.timestamps.asOf) viewModel.asOf = projection.timestamps.asOf;
  if (projection.timestamps.updatedAt) viewModel.updatedAt = projection.timestamps.updatedAt;
  return viewModel;
}

type ConsumerDataHealthCategoryCopy = Record<
  ConsumerDataHealthCategory,
  Record<'label' | 'whyItMatters' | 'nextStep', Record<ConsumerDataHealthLocale, string>>
>;

const DATA_HEALTH_CATEGORY_COPY: ConsumerDataHealthCategoryCopy = {
  marketBreadth: {
    label: { zh: '市场广度', en: 'Market breadth' },
    whyItMatters: { zh: '广度影响市场背景和参与度判断。', en: 'Breadth shapes market context and participation reads.' },
    nextStep: { zh: '继续观察广度参与是否稳定。', en: 'Keep checking whether participation remains stable.' },
  },
  themeRotation: {
    label: { zh: '主题轮动', en: 'Theme rotation' },
    whyItMatters: { zh: '轮动质量影响主题延续性的解读。', en: 'Rotation quality affects how theme durability is interpreted.' },
    nextStep: { zh: '复核主题是否仍由多组证据支持。', en: 'Review whether themes remain supported by several evidence groups.' },
  },
  stockEvidence: {
    label: { zh: '个股证据', en: 'Stock evidence' },
    whyItMatters: { zh: '个股证据决定结构解读是否完整。', en: 'Stock evidence determines whether structure reads are complete.' },
    nextStep: { zh: '补齐缺口后再扩大结论范围。', en: 'Fill evidence gaps before widening the conclusion.' },
  },
  peerComparison: {
    label: { zh: '同业比较', en: 'Peer comparison' },
    whyItMatters: { zh: '同业证据帮助区分个股变化和板块同步。', en: 'Peer evidence helps separate symbol-specific moves from group behavior.' },
    nextStep: { zh: '复核同业样本和对比窗口。', en: 'Review peer samples and the comparison window.' },
  },
  portfolioExposure: {
    label: { zh: '组合暴露', en: 'Portfolio exposure' },
    whyItMatters: { zh: '组合暴露影响风险归因和集中度观察。', en: 'Portfolio exposure affects risk attribution and concentration reads.' },
    nextStep: { zh: '等组合暴露证据恢复后再解读影响。', en: 'Wait for exposure evidence before interpreting portfolio impact.' },
  },
  optionsStructure: {
    label: { zh: '期权结构', en: 'Options structure' },
    whyItMatters: { zh: '期权结构影响波动和 gamma 观察边界。', en: 'Options structure affects volatility and gamma observation boundaries.' },
    nextStep: { zh: '仅在结构证据恢复后阅读期权语境。', en: 'Read options context only after structure evidence recovers.' },
  },
  researchQueueFreshness: {
    label: { zh: '研究队列时效', en: 'Research queue freshness' },
    whyItMatters: { zh: '队列时效影响后续复核顺序。', en: 'Queue freshness affects follow-up review order.' },
    nextStep: { zh: '先复核需要更新的研究条目。', en: 'Review items that need updates first.' },
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

export function createConsumerDataHealthSummary(
  input: ConsumerDataHealthSummaryInput,
): ConsumerDataHealthSummary {
  const locale = input.locale === 'en' ? 'en' : 'zh';
  const items = input.categories.map((item) => {
    const quality = item.quality ?? {};
    const view = createConsumerDataQualityViewModel({
      ...quality,
      readiness: quality.readiness ?? quality.readinessState ?? quality.status,
    });
    const state = resolveHealthState(view);
    const categoryCopy = DATA_HEALTH_CATEGORY_COPY[item.category];
    return {
      category: item.category,
      state,
      label: categoryCopy.label[locale],
      stateLabel: DATA_HEALTH_STATE_LABELS[state][locale],
      whyItMatters: categoryCopy.whyItMatters[locale],
      confidenceEffect: DATA_HEALTH_CONFIDENCE_EFFECT[state][locale],
      nextResearchStep: categoryCopy.nextStep[locale],
      supportingNotes: item.supportingNotes?.filter((note) => note.trim().length > 0),
    };
  });

  return {
    overallState: items.reduce<ConsumerDataHealthState>(
      (current, item) => HEALTH_STATE_RANK[current] >= HEALTH_STATE_RANK[item.state] ? current : item.state,
      'healthy',
    ),
    items,
  };
}
