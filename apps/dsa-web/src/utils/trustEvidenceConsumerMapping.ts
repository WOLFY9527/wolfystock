export type TrustEvidenceConsumerState =
  | 'AVAILABLE'
  | 'UPDATING'
  | 'DELAYED'
  | 'PARTIAL'
  | 'INSUFFICIENT'
  | 'OBSERVATION_ONLY'
  | 'UNAVAILABLE';

export type TrustEvidenceAvailabilityState =
  | 'available'
  | 'updating'
  | 'delayed'
  | 'partial'
  | 'insufficient'
  | 'observation_only'
  | 'unavailable';

export type TrustEvidenceFreshnessState =
  | 'live'
  | 'fresh'
  | 'delayed'
  | 'cached'
  | 'stale'
  | 'fallback'
  | 'partial'
  | 'synthetic'
  | 'unavailable'
  | 'unknown';

export type TrustEvidenceSourceClass =
  | 'official_public'
  | 'licensed_authorized'
  | 'public_proxy'
  | 'local_cache'
  | 'synthetic'
  | 'unknown';

export type TrustEvidenceConsumerBadgeKey =
  | 'source_current'
  | 'source_delayed'
  | 'source_stale'
  | 'source_partial'
  | 'source_fallback'
  | 'source_unavailable'
  | 'observation_only';

export interface TrustEvidenceSnapshotLike {
  contractVersion?: unknown;
  surfaceKey?: unknown;
  entityKey?: unknown;
  generatedAt?: unknown;
  asOf?: unknown;
  availabilityState?: unknown;
  freshnessState?: unknown;
  sourceClass?: unknown;
  hasFallback?: unknown;
  isStale?: unknown;
  isPartial?: unknown;
  isSynthetic?: unknown;
  isAdminOnlyDetail?: unknown;
  consumerState?: unknown;
  consumerMessageKey?: unknown;
  consumerBadgeKeys?: readonly unknown[];
  adminDiagnosticRefs?: readonly unknown[];
  [key: string]: unknown;
}

export interface TrustEvidenceConsumerCopy {
  key: `trust_evidence.${string}`;
  label: string;
  message: string;
}

export interface TrustEvidenceConsumerBadge {
  key: TrustEvidenceConsumerBadgeKey;
  label: string;
}

export interface TrustEvidenceConsumerViewModel {
  state: TrustEvidenceConsumerState;
  statusLabel: string;
  messageKey: `trust_evidence.${string}`;
  message: string;
  badges: TrustEvidenceConsumerBadge[];
  asOf?: string;
  isConsumerVisible: true;
}

export const TRUST_EVIDENCE_CONSUMER_COPY: Record<TrustEvidenceConsumerState, TrustEvidenceConsumerCopy> = {
  AVAILABLE: {
    key: 'trust_evidence.available',
    label: '可用',
    message: '当前证据可用于观察。',
  },
  UPDATING: {
    key: 'trust_evidence.updating',
    label: '正在更新',
    message: '数据正在更新，稍后会刷新状态。',
  },
  DELAYED: {
    key: 'trust_evidence.delayed',
    label: '延迟可用',
    message: '已使用最近一次可用证据。',
  },
  PARTIAL: {
    key: 'trust_evidence.partial',
    label: '部分可用',
    message: '部分证据暂不可用，结论需保留限制。',
  },
  INSUFFICIENT: {
    key: 'trust_evidence.insufficient',
    label: '证据不足',
    message: '当前证据不足，仅可作为观察参考。',
  },
  OBSERVATION_ONLY: {
    key: 'trust_evidence.observation_only',
    label: '仅供观察',
    message: '当前仅供观察，不代表可直接行动。',
  },
  UNAVAILABLE: {
    key: 'trust_evidence.unavailable',
    label: '暂不可用',
    message: '本模块暂不可用，请稍后重试。',
  },
};

export const TRUST_EVIDENCE_CONSUMER_BADGE_COPY: Record<
  TrustEvidenceConsumerBadgeKey,
  TrustEvidenceConsumerBadge
> = {
  source_current: {
    key: 'source_current',
    label: '当前',
  },
  source_delayed: {
    key: 'source_delayed',
    label: '延迟',
  },
  source_stale: {
    key: 'source_stale',
    label: '已过时',
  },
  source_partial: {
    key: 'source_partial',
    label: '不完整',
  },
  source_fallback: {
    key: 'source_fallback',
    label: '替代证据',
  },
  source_unavailable: {
    key: 'source_unavailable',
    label: '不可用',
  },
  observation_only: {
    key: 'observation_only',
    label: '仅观察',
  },
};

const CONSUMER_STATES = new Set<TrustEvidenceConsumerState>([
  'AVAILABLE',
  'UPDATING',
  'DELAYED',
  'PARTIAL',
  'INSUFFICIENT',
  'OBSERVATION_ONLY',
  'UNAVAILABLE',
]);

const AVAILABILITY_TO_CONSUMER_STATE: Record<TrustEvidenceAvailabilityState, TrustEvidenceConsumerState> = {
  available: 'AVAILABLE',
  updating: 'UPDATING',
  delayed: 'DELAYED',
  partial: 'PARTIAL',
  insufficient: 'INSUFFICIENT',
  observation_only: 'OBSERVATION_ONLY',
  unavailable: 'UNAVAILABLE',
};

const BADGE_KEYS = new Set<TrustEvidenceConsumerBadgeKey>([
  'source_current',
  'source_delayed',
  'source_stale',
  'source_partial',
  'source_fallback',
  'source_unavailable',
  'observation_only',
]);

function readString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function readBoolean(value: unknown): boolean {
  return value === true;
}

function isConsumerState(value: unknown): value is TrustEvidenceConsumerState {
  return typeof value === 'string' && CONSUMER_STATES.has(value as TrustEvidenceConsumerState);
}

function isBadgeKey(value: unknown): value is TrustEvidenceConsumerBadgeKey {
  return typeof value === 'string' && BADGE_KEYS.has(value as TrustEvidenceConsumerBadgeKey);
}

function resolveConsumerState(snapshot: TrustEvidenceSnapshotLike): TrustEvidenceConsumerState {
  if (isConsumerState(snapshot.consumerState)) {
    return snapshot.consumerState;
  }

  const availabilityState = readString(snapshot.availabilityState);
  if (availabilityState && availabilityState in AVAILABILITY_TO_CONSUMER_STATE) {
    return AVAILABILITY_TO_CONSUMER_STATE[availabilityState as TrustEvidenceAvailabilityState];
  }

  if (readBoolean(snapshot.isPartial)) return 'PARTIAL';
  if (readBoolean(snapshot.isStale) || readBoolean(snapshot.hasFallback)) return 'DELAYED';

  return 'INSUFFICIENT';
}

function maybeAddBadge(
  badges: TrustEvidenceConsumerBadgeKey[],
  badgeKey: TrustEvidenceConsumerBadgeKey,
  shouldAdd: boolean,
): void {
  if (shouldAdd && !badges.includes(badgeKey)) {
    badges.push(badgeKey);
  }
}

function resolveBadgeKeys(
  snapshot: TrustEvidenceSnapshotLike,
  state: TrustEvidenceConsumerState,
): TrustEvidenceConsumerBadgeKey[] {
  const requestedKeys = Array.isArray(snapshot.consumerBadgeKeys)
    ? snapshot.consumerBadgeKeys.filter(isBadgeKey)
    : [];
  const hasFallback = readBoolean(snapshot.hasFallback);
  const isStale = readBoolean(snapshot.isStale);
  const isPartial = readBoolean(snapshot.isPartial);
  const freshnessState = readString(snapshot.freshnessState);
  const badges: TrustEvidenceConsumerBadgeKey[] = [];

  for (const key of requestedKeys) {
    maybeAddBadge(badges, key, canShowBadge(key, { state, hasFallback, isPartial, isStale }));
  }

  maybeAddBadge(badges, 'source_unavailable', state === 'UNAVAILABLE' || freshnessState === 'unavailable');
  maybeAddBadge(badges, 'observation_only', state === 'OBSERVATION_ONLY');
  maybeAddBadge(badges, 'source_partial', isPartial);
  maybeAddBadge(badges, 'source_stale', isStale);
  maybeAddBadge(badges, 'source_fallback', hasFallback);
  maybeAddBadge(badges, 'source_delayed', state === 'DELAYED' || freshnessState === 'delayed' || freshnessState === 'cached');
  maybeAddBadge(
    badges,
    'source_current',
    state === 'AVAILABLE' && !hasFallback && !isStale && !isPartial && badges.length === 0,
  );

  return badges;
}

function canShowBadge(
  badgeKey: TrustEvidenceConsumerBadgeKey,
  flags: {
    state: TrustEvidenceConsumerState;
    hasFallback: boolean;
    isPartial: boolean;
    isStale: boolean;
  },
): boolean {
  if (badgeKey === 'source_stale') return flags.isStale;
  if (badgeKey === 'source_partial') return flags.isPartial;
  if (badgeKey === 'source_fallback') return flags.hasFallback;
  if (badgeKey === 'observation_only') return flags.state === 'OBSERVATION_ONLY';
  if (badgeKey === 'source_unavailable') return flags.state === 'UNAVAILABLE';
  return true;
}

export function createTrustEvidenceConsumerViewModel(
  snapshot: TrustEvidenceSnapshotLike,
): TrustEvidenceConsumerViewModel {
  const state = resolveConsumerState(snapshot);
  const copy = TRUST_EVIDENCE_CONSUMER_COPY[state];
  const asOf = readString(snapshot.asOf);
  const viewModel: TrustEvidenceConsumerViewModel = {
    state,
    statusLabel: copy.label,
    messageKey: copy.key,
    message: copy.message,
    badges: resolveBadgeKeys(snapshot, state).map((key) => TRUST_EVIDENCE_CONSUMER_BADGE_COPY[key]),
    isConsumerVisible: true,
  };

  if (asOf) {
    viewModel.asOf = asOf;
  }

  return viewModel;
}
