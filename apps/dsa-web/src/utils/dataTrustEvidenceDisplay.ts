import type { NormalizedEvidenceSummary } from './evidenceDisplay';
import type { TrustEvidenceSnapshotLike } from './trustEvidenceConsumerMapping';

export type DataTrustEvidenceState =
  | 'authoritative'
  | 'partial'
  | 'stale'
  | 'fallback'
  | 'fixture-demo'
  | 'synthetic'
  | 'unavailable'
  | 'insufficient'
  | 'observation-only'
  | 'not-investment-advice';

export type DataTrustEvidenceLocale = 'zh' | 'en';

export type DataTrustEvidenceTone = 'neutral' | 'success' | 'caution' | 'danger' | 'info';

export type DataTrustEvidenceChip = {
  state: DataTrustEvidenceState;
  label: string;
  message: string;
  tone: DataTrustEvidenceTone;
};

export type DataTrustEvidenceViewModel = {
  primaryState: DataTrustEvidenceState | null;
  states: DataTrustEvidenceState[];
  chips: DataTrustEvidenceChip[];
  message: string;
  locale: DataTrustEvidenceLocale;
  confidenceCap?: number;
  confidenceCapLabel?: string;
  asOf?: string;
};

export type DataTrustEvidenceInput = {
  locale?: DataTrustEvidenceLocale;
  states?: readonly unknown[];
  terms?: readonly unknown[];
  trustEvidence?: TrustEvidenceSnapshotLike | null;
  normalizedEvidence?: NormalizedEvidenceSummary | null;
  confidenceCap?: number | null;
  asOf?: string | null;
  includeSafetyState?: boolean;
};

type LocalizedEvidenceCopy = Record<
  DataTrustEvidenceState,
  {
    tone: DataTrustEvidenceTone;
    zh: { label: string; message: string };
    en: { label: string; message: string };
  }
>;

export const DATA_TRUST_EVIDENCE_STATE_ORDER: DataTrustEvidenceState[] = [
  'authoritative',
  'partial',
  'stale',
  'fallback',
  'fixture-demo',
  'synthetic',
  'unavailable',
  'insufficient',
  'observation-only',
  'not-investment-advice',
];

export const DATA_TRUST_EVIDENCE_COPY: LocalizedEvidenceCopy = {
  authoritative: {
    tone: 'success',
    zh: {
      label: '证据可用',
      message: '当前证据可在产品观察边界内使用。',
    },
    en: {
      label: 'Authoritative',
      message: 'Evidence is usable within the current consumer observation boundary.',
    },
  },
  partial: {
    tone: 'info',
    zh: {
      label: '证据不完整',
      message: '部分证据暂不可用，结论需保留限制。',
    },
    en: {
      label: 'Partial evidence',
      message: 'Some evidence is incomplete; keep the conclusion bounded.',
    },
  },
  stale: {
    tone: 'caution',
    zh: {
      label: '数据过期',
      message: '当前使用的证据可能存在延迟。',
    },
    en: {
      label: 'Stale',
      message: 'The current evidence may be delayed.',
    },
  },
  fallback: {
    tone: 'caution',
    zh: {
      label: '备用数据',
      message: '当前使用替代证据，需降低解读强度。',
    },
    en: {
      label: 'Fallback',
      message: 'Fallback evidence is in use; interpret with limits.',
    },
  },
  'fixture-demo': {
    tone: 'neutral',
    zh: {
      label: '演示数据',
      message: '当前包含演示或测试数据，不作为结论依据。',
    },
    en: {
      label: 'Demo',
      message: 'Demo or fixture data is present; do not use it as conclusion evidence.',
    },
  },
  synthetic: {
    tone: 'neutral',
    zh: {
      label: '合成证据',
      message: '当前包含合成或推导值，仅作结构观察。',
    },
    en: {
      label: 'Synthetic',
      message: 'Synthetic or inferred evidence is present; use it for structure only.',
    },
  },
  unavailable: {
    tone: 'danger',
    zh: {
      label: '暂不可用',
      message: '本模块证据暂不可用，请稍后重试。',
    },
    en: {
      label: 'Unavailable',
      message: 'Evidence for this module is unavailable; retry later.',
    },
  },
  insufficient: {
    tone: 'danger',
    zh: {
      label: '证据不足',
      message: '当前证据不足，仅可作为观察参考。',
    },
    en: {
      label: 'Insufficient',
      message: 'Evidence is insufficient; treat this as observation only.',
    },
  },
  'observation-only': {
    tone: 'caution',
    zh: {
      label: '仅供观察',
      message: '当前仅供观察，不代表可直接行动。',
    },
    en: {
      label: 'Observation only',
      message: 'This output is for observation only and does not imply actionability.',
    },
  },
  'not-investment-advice': {
    tone: 'neutral',
    zh: {
      label: '不构成投资建议',
      message: '本信息不构成买卖、下单或持仓建议。',
    },
    en: {
      label: 'Not investment advice',
      message: 'This information is not a buy, sell, order, or portfolio instruction.',
    },
  },
};

const LIMITING_STATES = new Set<DataTrustEvidenceState>(
  DATA_TRUST_EVIDENCE_STATE_ORDER.filter(
    (state) => state !== 'authoritative' && state !== 'not-investment-advice',
  ),
);

const STATE_ALIASES: Record<string, DataTrustEvidenceState> = {
  authoritative: 'authoritative',
  available: 'authoritative',
  current: 'authoritative',
  fresh: 'authoritative',
  ready: 'authoritative',
  partial: 'partial',
  incomplete: 'partial',
  degraded: 'partial',
  delayed: 'stale',
  cached: 'stale',
  stale: 'stale',
  expired: 'stale',
  fallback: 'fallback',
  backup: 'fallback',
  dry_run: 'fixture-demo',
  dryrun: 'fixture-demo',
  demo: 'fixture-demo',
  fixture: 'fixture-demo',
  mock: 'fixture-demo',
  synthetic_fixture: 'fixture-demo',
  synthetic: 'synthetic',
  inferred: 'synthetic',
  generated: 'synthetic',
  unavailable: 'unavailable',
  paused: 'unavailable',
  failed: 'unavailable',
  error: 'unavailable',
  insufficient: 'insufficient',
  blocked: 'insufficient',
  missing: 'insufficient',
  not_enough: 'insufficient',
  not_enough_history: 'insufficient',
  observe_only: 'observation-only',
  observation_only: 'observation-only',
  observation: 'observation-only',
  non_advice: 'not-investment-advice',
  not_investment_advice: 'not-investment-advice',
  not_trading_advice: 'not-investment-advice',
  no_advice: 'not-investment-advice',
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function readString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function readSafeAsOf(value: unknown): string | undefined {
  const text = readString(value);
  if (!text) return undefined;
  return /^\d{4}-\d{2}-\d{2}(?:[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:?\d{2}| ?UTC)?)?$/i.test(text)
    ? text
    : undefined;
}

function readBoolean(value: unknown): boolean {
  return value === true;
}

function readNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function normalizeTerm(value: unknown): string {
  return String(value || '').trim().toLowerCase().replace(/[\s/-]+/g, '_');
}

function addState(states: Set<DataTrustEvidenceState>, state: DataTrustEvidenceState | null | undefined): void {
  if (state) states.add(state);
}

function stateFromKnownValue(value: unknown): DataTrustEvidenceState | null {
  const normalized = normalizeTerm(value);
  if (!normalized) return null;
  if (normalized in STATE_ALIASES) return STATE_ALIASES[normalized];

  if (normalized.includes('not_investment_advice') || normalized.includes('not_trading_advice')) return 'not-investment-advice';
  if (normalized.includes('不构成') || normalized.includes('非投资建议')) return 'not-investment-advice';
  if (normalized.includes('仅供观察') || normalized.includes('仅观察') || normalized.includes('observe')) return 'observation-only';
  if (normalized.includes('数据不足') || normalized.includes('证据不足') || normalized.includes('insufficient') || normalized.includes('not_enough')) return 'insufficient';
  if (normalized.includes('暂不可用') || normalized.includes('unavailable') || normalized.includes('failed')) return 'unavailable';
  if (normalized.includes('合成') || normalized.includes('synthetic') || normalized.includes('inferred')) return 'synthetic';
  if (normalized.includes('演示') || normalized.includes('fixture') || normalized.includes('demo') || normalized.includes('dry_run') || normalized.includes('mock')) return 'fixture-demo';
  if (normalized.includes('fallback') || normalized.includes('备用')) return 'fallback';
  if (normalized.includes('stale') || normalized.includes('expired') || normalized.includes('过期') || normalized.includes('delayed') || normalized.includes('延迟')) return 'stale';
  if (normalized.includes('partial') || normalized.includes('coverage') || normalized.includes('不完整')) return 'partial';
  if (normalized.includes('available') || normalized.includes('ready') || normalized.includes('可用')) return 'authoritative';

  return null;
}

function addStatesFromTerms(states: Set<DataTrustEvidenceState>, terms: readonly unknown[] | undefined): void {
  for (const term of terms ?? []) {
    addState(states, stateFromKnownValue(term));
  }
}

function addStatesFromTrustEvidence(
  states: Set<DataTrustEvidenceState>,
  snapshot: TrustEvidenceSnapshotLike | null | undefined,
): boolean {
  if (!snapshot || !isRecord(snapshot)) return false;
  let hasPositiveSignal = false;
  const consumerState = normalizeTerm(snapshot.consumerState);
  const availabilityState = normalizeTerm(snapshot.availabilityState);
  const freshnessState = normalizeTerm(snapshot.freshnessState);
  const sourceClass = normalizeTerm(snapshot.sourceClass);

  if (consumerState === 'available' || availabilityState === 'available') {
    hasPositiveSignal = true;
  }
  if (consumerState === 'updating' || availabilityState === 'updating') addState(states, 'partial');
  if (consumerState === 'delayed' || availabilityState === 'delayed') addState(states, 'stale');
  if (consumerState === 'partial' || availabilityState === 'partial') addState(states, 'partial');
  if (consumerState === 'insufficient' || availabilityState === 'insufficient') addState(states, 'insufficient');
  if (consumerState === 'observation_only' || availabilityState === 'observation_only') addState(states, 'observation-only');
  if (consumerState === 'unavailable' || availabilityState === 'unavailable') addState(states, 'unavailable');

  if (freshnessState === 'live' || freshnessState === 'fresh') hasPositiveSignal = true;
  if (freshnessState === 'delayed' || freshnessState === 'cached' || freshnessState === 'stale') addState(states, 'stale');
  if (freshnessState === 'fallback') addState(states, 'fallback');
  if (freshnessState === 'partial') addState(states, 'partial');
  if (freshnessState === 'synthetic') addState(states, 'synthetic');
  if (freshnessState === 'unavailable') addState(states, 'unavailable');

  if (sourceClass === 'synthetic') addState(states, 'synthetic');
  if (readBoolean(snapshot.hasFallback)) addState(states, 'fallback');
  if (readBoolean(snapshot.isStale)) addState(states, 'stale');
  if (readBoolean(snapshot.isPartial)) addState(states, 'partial');
  if (readBoolean(snapshot.isSynthetic)) addState(states, 'synthetic');

  return hasPositiveSignal;
}

function addStatesFromSummary(
  states: Set<DataTrustEvidenceState>,
  summary: NormalizedEvidenceSummary | null | undefined,
): void {
  if (!summary) return;
  if (summary.posture === 'blocked') addState(states, 'insufficient');
  if (summary.posture === 'observe_only') addState(states, 'observation-only');
  if (summary.posture === 'review_required' || summary.posture === 'allowed_metadata_only') addState(states, 'partial');

  addStatesFromTerms(states, [
    summary.displayLabel,
    summary.freshnessLabel,
    ...summary.limitationLabels,
  ]);
}

function orderedStates(states: Set<DataTrustEvidenceState>): DataTrustEvidenceState[] {
  const hasLimitingState = [...states].some((state) => LIMITING_STATES.has(state));
  if (hasLimitingState) states.delete('authoritative');
  return DATA_TRUST_EVIDENCE_STATE_ORDER.filter((state) => states.has(state));
}

function confidenceCapFrom(input: DataTrustEvidenceInput): number | undefined {
  return readNumber(input.confidenceCap) ?? readNumber(input.normalizedEvidence?.confidenceCap);
}

function asOfFrom(input: DataTrustEvidenceInput): string | undefined {
  return readSafeAsOf(input.asOf) ?? readSafeAsOf(input.trustEvidence?.asOf);
}

function confidenceCapLabel(confidenceCap: number | undefined, locale: DataTrustEvidenceLocale): string | undefined {
  if (confidenceCap == null) return undefined;
  return locale === 'zh' ? `置信上限 ${confidenceCap}` : `Confidence cap ${confidenceCap}`;
}

export function createDataTrustEvidenceViewModel(
  input: DataTrustEvidenceInput = {},
): DataTrustEvidenceViewModel {
  const locale = input.locale ?? 'zh';
  const includeSafetyState = input.includeSafetyState !== false;
  const states = new Set<DataTrustEvidenceState>();
  let hasPositiveSignal = false;

  addStatesFromTerms(states, input.states);
  addStatesFromTerms(states, input.terms);
  hasPositiveSignal = addStatesFromTrustEvidence(states, input.trustEvidence) || hasPositiveSignal;
  addStatesFromSummary(states, input.normalizedEvidence);

  if (hasPositiveSignal && ![...states].some((state) => LIMITING_STATES.has(state))) {
    addState(states, 'authoritative');
  }
  if (includeSafetyState) addState(states, 'not-investment-advice');
  if (!includeSafetyState) states.delete('not-investment-advice');

  const resolvedStates = orderedStates(states);
  const chips = resolvedStates.map((state) => {
    const copy = DATA_TRUST_EVIDENCE_COPY[state];
    return {
      state,
      label: copy[locale].label,
      message: copy[locale].message,
      tone: copy.tone,
    };
  });
  const confidenceCap = confidenceCapFrom(input);
  const viewModel: DataTrustEvidenceViewModel = {
    primaryState: resolvedStates[0] ?? null,
    states: resolvedStates,
    chips,
    message: chips[0]?.message ?? '',
    locale,
  };
  const capLabel = confidenceCapLabel(confidenceCap, locale);
  const asOf = asOfFrom(input);

  if (confidenceCap != null) viewModel.confidenceCap = confidenceCap;
  if (capLabel) viewModel.confidenceCapLabel = capLabel;
  if (asOf) viewModel.asOf = asOf;
  return viewModel;
}
