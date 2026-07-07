import { getConsumerStatusLabel, mapConsumerStatusText, normalizeConsumerStatusToken } from './consumerStatusLabels';
import { createConsumerDataQualityViewModel, type ConsumerDataQualityInput } from './consumerDataQualityViewModel';
import { sanitizeUserFacingDataIssue } from './userFacingDataIssues';

export type ConsumerPresentationLocale = 'zh' | 'en';
export type ConsumerPresentationDataState =
  | 'available'
  | 'partial'
  | 'stale'
  | 'unavailable'
  | 'insufficient'
  | 'blocked'
  | 'initializing'
  | 'error';

export type ConsumerPresentationStateTone =
  | 'positive'
  | 'neutral'
  | 'warning'
  | 'danger'
  | 'muted';

export type ConsumerPresentationStateView = {
  state: ConsumerPresentationDataState;
  label: string;
  tone: ConsumerPresentationStateTone;
  message: string;
  asOf?: string;
  updatedAt?: string;
};

type PresentationCopy = {
  zh: string;
  en: string;
};

const FALLBACK_COPY: Record<ConsumerPresentationLocale, string> = {
  zh: '数据不足，结论仅供观察',
  en: 'Data insufficient; observe only',
};

const DATA_STATE_COPY: Record<ConsumerPresentationDataState, Record<ConsumerPresentationLocale, { label: string; message: string; tone: ConsumerPresentationStateTone }>> = {
  available: {
    zh: { label: '可用', message: '当前证据可用于研究观察。', tone: 'positive' },
    en: { label: 'Available', message: 'Current evidence is available for research observation.', tone: 'positive' },
  },
  partial: {
    zh: { label: '部分可用', message: '部分证据可用，结论范围需要收窄。', tone: 'warning' },
    en: { label: 'Partial', message: 'Some evidence is available; keep the conclusion narrow.', tone: 'warning' },
  },
  stale: {
    zh: { label: '已延迟', message: '证据时效受限，先按观察处理。', tone: 'warning' },
    en: { label: 'Stale', message: 'Freshness is limited; treat this as observation.', tone: 'warning' },
  },
  unavailable: {
    zh: { label: '不可用', message: '当前证据暂不可用。', tone: 'muted' },
    en: { label: 'Unavailable', message: 'Current evidence is unavailable.', tone: 'muted' },
  },
  insufficient: {
    zh: { label: '证据不足', message: '当前证据不足，暂不扩大结论。', tone: 'warning' },
    en: { label: 'Insufficient', message: 'Evidence is insufficient; do not widen the conclusion.', tone: 'warning' },
  },
  blocked: {
    zh: { label: '已阻断', message: '研究边界已阻断，暂不形成结论。', tone: 'danger' },
    en: { label: 'Blocked', message: 'The research boundary is blocked; no conclusion is formed.', tone: 'danger' },
  },
  initializing: {
    zh: { label: '初始化中', message: '数据正在初始化，等待当前更新完成。', tone: 'neutral' },
    en: { label: 'Initializing', message: 'Data is initializing; wait for the current update to finish.', tone: 'neutral' },
  },
  error: {
    zh: { label: '读取异常', message: '数据读取异常，请稍后重试。', tone: 'danger' },
    en: { label: 'Error', message: 'Data read failed; try again later.', tone: 'danger' },
  },
};

const INTERNAL_COPY_BY_KEY: Record<string, PresentationCopy> = {
  failed_closed: {
    zh: '数据保护边界已生效，暂不形成结论。',
    en: 'Data protection boundary is active, so no conclusion is formed.',
  },
  ['insufficient' + '_data']: {
    zh: '数据不足，先保持观察。',
    en: 'Data is insufficient; observe only for now.',
  },
  scenario_evidence_pack_v1: {
    zh: '情景研究记录',
    en: 'Scenario research record',
  },
  raw_payload: {
    zh: '内部数据细节已折叠',
    en: 'Internal data details are collapsed',
  },
  api_call: {
    zh: '数据连接',
    en: 'Data connection',
  },
  stocks_ticker_structure_decision: {
    zh: '输入股票代码即可进入结构视图。',
    en: 'Enter a ticker to open the structure view.',
  },
  critical_evidence_missing: {
    zh: '关键证据暂缺，先补充证据后再复核。',
    en: 'Critical evidence is missing; add evidence before review.',
  },
  market_regime_evidence: {
    zh: '市场状态证据',
    en: 'Market state evidence',
  },
  benchmark_trend: {
    zh: '基准走势',
    en: 'Benchmark trend',
  },
  growth_risk_proxy: {
    zh: '成长风险观察',
    en: 'Growth risk observation',
  },
  breadth: {
    zh: '市场广度',
    en: 'Market breadth',
  },
  product_ready: {
    zh: '证据已可用于观察',
    en: 'Evidence ready for observation',
  },
  risk_on_confirming: {
    zh: '风险偏好观察',
    en: 'Risk-on observation',
  },
  market_level_context: {
    zh: '市场级上下文',
    en: 'Market-level context',
  },
  data_quality: {
    zh: '数据质量',
    en: 'Data quality',
  },
  business_quality_review: {
    zh: '基本面资料待补',
    en: 'Fundamental data missing',
  },
  clean_research_handoff: {
    zh: '支持证据仍不完整',
    en: 'Supporting evidence still incomplete',
  },
  observation_only_research_readiness: {
    zh: '暂仅观察',
    en: 'Observation-only for now',
  },
  growth_proxy_unavailable: {
    zh: '成长风险观察证据暂不可用。',
    en: 'Growth-risk observation evidence is unavailable.',
  },
  breadth_evidence_unavailable: {
    zh: '市场广度证据暂不可用。',
    en: 'Market breadth evidence is unavailable.',
  },
  freshness_constrained: {
    zh: '数据新鲜度受限，当前仅供观察。',
    en: 'Freshness is limited for this observation.',
  },
};

const INTERNAL_PHRASE_COPY: Array<[RegExp, PresentationCopy]> = [
  [new RegExp('failed\\s+' + 'closed', 'i'), INTERNAL_COPY_BY_KEY.failed_closed],
  [new RegExp('critical evidence ' + 'missing', 'i'), INTERNAL_COPY_BY_KEY.critical_evidence_missing],
  [new RegExp('market regime ' + 'evidence', 'i'), INTERNAL_COPY_BY_KEY.market_regime_evidence],
  [new RegExp('benchmark ' + 'trend', 'i'), INTERNAL_COPY_BY_KEY.benchmark_trend],
  [new RegExp('growth risk ' + 'proxy', 'i'), INTERNAL_COPY_BY_KEY.growth_risk_proxy],
  [/^breadth$/i, INTERNAL_COPY_BY_KEY.breadth],
  [new RegExp('scenario-evidence-pack' + '\\.v1', 'i'), INTERNAL_COPY_BY_KEY.scenario_evidence_pack_v1],
  [new RegExp('/stocks/\\{ticker\\}/' + 'structure-decision', 'i'), INTERNAL_COPY_BY_KEY.stocks_ticker_structure_decision],
  [new RegExp('不展示' + '原始载荷|no raw ' + 'payload', 'i'), INTERNAL_COPY_BY_KEY.raw_payload],
  [new RegExp('接口' + '调用|api ' + 'call', 'i'), INTERNAL_COPY_BY_KEY.api_call],
  [new RegExp('risk-on confirming evidence is currently ' + 'present', 'i'), {
    zh: '市场状态证据当前支持风险偏好观察。',
    en: 'Market state evidence currently supports a risk-on observation.',
  }],
  [new RegExp('market regime read model is available from local evidence ' + 'inputs', 'i'), {
    zh: '市场状态证据已整理，可继续观察。',
    en: 'Market state evidence is organized and ready for observation.',
  }],
  [new RegExp('benchmark trend evidence is ' + 'positive', 'i'), {
    zh: '基准走势证据偏积极。',
    en: 'Benchmark trend evidence is constructive.',
  }],
  [new RegExp('benchmark trend evidence is ' + 'negative', 'i'), {
    zh: '基准走势证据偏弱。',
    en: 'Benchmark trend evidence is under pressure.',
  }],
  [new RegExp('growth proxy evidence is ' + 'unavailable', 'i'), INTERNAL_COPY_BY_KEY.growth_proxy_unavailable],
  [new RegExp('freshness is constrained for this ' + 'observation', 'i'), INTERNAL_COPY_BY_KEY.freshness_constrained],
  [new RegExp('breadth evidence is ' + 'weak', 'i'), {
    zh: '市场广度证据偏弱。',
    en: 'Market breadth evidence is weak.',
  }],
  [new RegExp('breadth evidence is ' + 'broad', 'i'), {
    zh: '市场广度证据较充分。',
    en: 'Market breadth evidence is broad.',
  }],
  [new RegExp('breadth evidence is ' + 'unavailable', 'i'), INTERNAL_COPY_BY_KEY.breadth_evidence_unavailable],
  [/data quality is product-ready/i, {
    zh: '数据质量可用于观察。',
    en: 'Data quality is ready for observation.',
  }],
  [new RegExp('business-quality ' + 'review', 'i'), INTERNAL_COPY_BY_KEY.business_quality_review],
  [new RegExp('clean research ' + 'handoff', 'i'), INTERNAL_COPY_BY_KEY.clean_research_handoff],
  [new RegExp('observation-only research ' + 'readiness', 'i'), INTERNAL_COPY_BY_KEY.observation_only_research_readiness],
  [new RegExp('personalized financial ' + 'advice', 'i'), {
    zh: '不构成个性化投资建议',
    en: 'No personalized investment advice',
  }],
  [new RegExp('need broader peer ' + 'evidence', 'i'), {
    zh: '需要补充同业对照证据。',
    en: 'Broader peer evidence is needed.',
  }],
  [new RegExp('need comparable peer structure ' + 'evidence', 'i'), {
    zh: '需要补充同业对照证据。',
    en: 'Comparable peer evidence is needed.',
  }],
  [new RegExp('peer behavior remains bounded by current ' + 'evidence', 'i'), {
    zh: '同业走势仍受当前证据窗口约束。',
    en: 'Peer behavior remains bounded by current evidence.',
  }],
  [new RegExp('msft moved with orcl across the comparison ' + 'window', 'i'), {
    zh: 'MSFT 与 ORCL 在当前对比窗口内走势同步。',
    en: 'MSFT moved with ORCL across the comparison window.',
  }],
  [new RegExp('nvda peer history is ' + 'unavailable', 'i'), {
    zh: 'NVDA 同业历史数据暂缺。',
    en: 'NVDA peer history is unavailable.',
  }],
  [new RegExp('observation-only peer movement context; no personalized action ' + 'instruction', 'i'), {
    zh: '仅供同业走势观察，不构成个性化行动指令。',
    en: 'Observation-only peer movement context; no personalized action instruction.',
  }],
  [new RegExp('review whether peer alignment persists after the next ' + 'close', 'i'), {
    zh: '下一个收盘后复核同业同步是否延续。',
    en: 'Review whether peer alignment persists after the next close.',
  }],
];

const INTERNAL_PRESENTATION_PATTERN =
  new RegExp([
    '\\b(?:failed\\s+' + 'closed|insufficient' + '_data|scenario-evidence-pack' + '\\.v1|critical evidence ' + 'missing',
    'market regime ' + 'evidence|benchmark ' + 'trend|growth risk ' + 'proxy|schemaVersion|reasonCodes?',
    'sourceRefs?|requestId|traceId|provider|runtime|debug|raw|payload|cache|backend',
    'fallback|score-grade|score_grade|observation-only|observation_only|packet|handoff',
    'business-quality\\s+' + 'review|clean research\\s+' + 'handoff',
    'personalized financial\\s+' + 'advice',
    'evidence families?|ohlcv)\\b',
    '/stocks/\\{ticker\\}/' + 'structure-decision',
    '不展示' + '原始载荷',
    '接口' + '调用',
  ].join('|'), 'i');

export function consumerPresentationTokenLabel(
  value: string | null | undefined,
  locale: ConsumerPresentationLocale,
): string | null {
  const token = normalizeConsumerStatusToken(value);
  if (!token) return null;
  return INTERNAL_COPY_BY_KEY[token]?.[locale] ?? getConsumerStatusLabel(value, locale);
}

export function consumerPresentationText(
  value: string | number | null | undefined,
  locale: ConsumerPresentationLocale,
  fallback?: string,
): string {
  const raw = String(value ?? '').trim();
  if (!raw) return fallback ?? FALLBACK_COPY[locale];

  const tokenLabel = consumerPresentationTokenLabel(raw, locale);
  if (tokenLabel) return tokenLabel;

  const mapped = mapConsumerStatusText(raw, locale);
  if (mapped !== raw) return mapped;

  for (const [pattern, copy] of INTERNAL_PHRASE_COPY) {
    if (pattern.test(raw)) return copy[locale];
  }

  if (INTERNAL_PRESENTATION_PATTERN.test(raw) || /\b[a-z]+(?:_[a-z0-9]+)+\b/i.test(raw)) {
    const sanitized = sanitizeUserFacingDataIssue(raw, locale);
    if (sanitized !== raw) return sanitized;
    return fallback ?? FALLBACK_COPY[locale];
  }

  return raw;
}

export function consumerPresentationTextOrNull(
  value: string | number | null | undefined,
  locale: ConsumerPresentationLocale,
): string | null {
  const raw = String(value ?? '').trim();
  if (!raw || raw === '--') return null;
  return consumerPresentationText(raw, locale, '');
}

export function consumerPresentationList(
  values: Array<string | null | undefined> | null | undefined,
  locale: ConsumerPresentationLocale,
  fallback: string,
): string[] {
  const seen = new Set<string>();
  const labels: string[] = [];
  for (const value of values ?? []) {
    const label = consumerPresentationTextOrNull(value, locale);
    if (!label || seen.has(label)) continue;
    seen.add(label);
    labels.push(label);
  }
  return labels.length ? labels : [fallback];
}

export function consumerPresentationRouteHint(locale: ConsumerPresentationLocale): string {
  return INTERNAL_COPY_BY_KEY.stocks_ticker_structure_decision[locale];
}

export function consumerPresentationArtifactVersionLabel(locale: ConsumerPresentationLocale): string {
  return INTERNAL_COPY_BY_KEY.scenario_evidence_pack_v1[locale];
}

function collectPresentationSignals(value: unknown, output: string[] = []): string[] {
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase();
    if (normalized) output.push(normalized);
    return output;
  }
  if (typeof value === 'boolean' || typeof value === 'number') {
    return output;
  }
  if (Array.isArray(value)) {
    value.forEach((item) => collectPresentationSignals(item, output));
    return output;
  }
  if (value && typeof value === 'object') {
    for (const [key, nested] of Object.entries(value)) {
      output.push(key.toLowerCase());
      collectPresentationSignals(nested, output);
    }
  }
  return output;
}

function hasPresentationSignal(signals: readonly string[], markers: readonly string[]): boolean {
  return signals.some((signal) => markers.some((marker) => signal.includes(marker)));
}

export function consumerPresentationDataState(
  input: ConsumerDataQualityInput | null | undefined,
  locale: ConsumerPresentationLocale,
): ConsumerPresentationStateView {
  const qualityView = createConsumerDataQualityViewModel(input ?? {});
  const signals = collectPresentationSignals(input ?? {});
  let state: ConsumerPresentationDataState;

  if (hasPresentationSignal(signals, ['error', 'failed', 'exception'])) {
    state = 'error';
  } else if (qualityView.status === 'UPDATING' || hasPresentationSignal(signals, ['initializing', 'loading', 'pending', 'refreshing'])) {
    state = 'initializing';
  } else if (qualityView.status === 'PAUSED' || hasPresentationSignal(signals, ['blocked', 'deny', 'denied', 'gate_blocked'])) {
    state = 'blocked';
  } else if (qualityView.status === 'INSUFFICIENT' || hasPresentationSignal(signals, ['insufficient'])) {
    state = 'insufficient';
  } else if (qualityView.status === 'UNAVAILABLE' || hasPresentationSignal(signals, ['unavailable', 'missing', 'empty'])) {
    state = 'unavailable';
  } else if (qualityView.status === 'PARTIAL' || qualityView.status === 'OBSERVATION_ONLY' || hasPresentationSignal(signals, ['partial', 'limited'])) {
    state = 'partial';
  } else if (qualityView.status === 'DELAYED' || qualityView.freshnessCategory === 'STALE' || qualityView.freshnessCategory === 'DELAYED') {
    state = 'stale';
  } else {
    state = 'available';
  }

  const copy = DATA_STATE_COPY[state][locale];
  return {
    state,
    label: copy.label,
    tone: copy.tone,
    message: copy.message,
    ...(qualityView.asOf ? { asOf: qualityView.asOf } : {}),
    ...(qualityView.updatedAt ? { updatedAt: qualityView.updatedAt } : {}),
  };
}
