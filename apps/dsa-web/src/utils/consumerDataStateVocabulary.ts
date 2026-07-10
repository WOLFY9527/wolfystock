export type ConsumerDataState =
  | 'available'
  | 'partial'
  | 'degraded'
  | 'stale'
  | 'delayed'
  | 'cached'
  | 'missing'
  | 'no_evidence'
  | 'insufficient'
  | 'insufficient_history'
  | 'disabled'
  | 'unavailable'
  | 'freshness_unavailable'
  | 'blocked'
  | 'pending'
  | 'pending_heavy'
  | 'initializing'
  | 'refreshing'
  | 'unknown'
  | 'observation_only'
  | 'rejected'
  | 'error'
  | 'failed'
  | 'failed_closed'
  | 'maintenance';

export type ConsumerDataStateSeverity = 'success' | 'info' | 'warning' | 'critical';
export type ConsumerDataStateTone = 'positive' | 'neutral' | 'warning' | 'danger' | 'muted';
export type ConsumerStateLocale = 'zh' | 'en';

export interface ConsumerDataStateVocabularyEntry {
  state: ConsumerDataState;
  label: string;
  shortLabel: string;
  explanation: string;
  severity: ConsumerDataStateSeverity;
  tone: ConsumerDataStateTone;
  nextStep: string;
}

type ConsumerDataStateCopy = {
  label: string;
  shortLabel: string;
  explanation: string;
  nextStep: string;
};

type LocalizedConsumerDataStateCopy = Record<ConsumerStateLocale, ConsumerDataStateCopy>;
type ConsumerDataStateCopyTuple = [label: string, shortLabel: string, explanation: string, nextStep: string];

function copy(tuple: ConsumerDataStateCopyTuple): ConsumerDataStateCopy {
  const [label, shortLabel, explanation, nextStep] = tuple;
  return { label, shortLabel, explanation, nextStep };
}

function stateVocabularyEntry(
  severity: ConsumerDataStateSeverity,
  tone: ConsumerDataStateTone,
  zh: ConsumerDataStateCopyTuple,
  en: ConsumerDataStateCopyTuple,
) {
  return { severity, tone, copy: { zh: copy(zh), en: copy(en) } };
}

const CONSUMER_DATA_STATE_VOCABULARY: Record<ConsumerDataState, {
  severity: ConsumerDataStateSeverity;
  tone: ConsumerDataStateTone;
  copy: LocalizedConsumerDataStateCopy;
}> = {
  available: stateVocabularyEntry('success', 'positive', ['数据可用', '可用', '当前信息满足本页面观察所需，可继续按研究边界阅读。', '继续观察关键证据是否保持一致。'], ['Data available', 'Available', 'Current evidence is available for research observation.', 'Keep checking whether key evidence stays aligned.']),
  partial: stateVocabularyEntry('warning', 'warning', ['部分证据可用', '部分可用', '已返回部分真实数据，但仍有证据缺口，结论强度需要降低。', '先查看已返回的模块，再等待缺口补齐。'], ['Partial evidence available', 'Partial', 'Some real evidence is available; keep the conclusion narrow.', 'Review the available modules first, then wait for gaps to close.']),
  degraded: stateVocabularyEntry('warning', 'warning', ['数据质量受限', '降级可读', '证据质量受限，当前只适合保守观察。', '交叉复核关键证据后再扩大解读。'], ['Data quality limited', 'Degraded', 'Evidence quality is limited; keep the read conservative.', 'Cross-check key evidence before widening the interpretation.']),
  stale: stateVocabularyEntry('warning', 'warning', ['数据可能已过期', '已过期', '当前展示的是历史观察快照，不代表实时信号。', '等待下一次数据刷新后再扩大解读。'], ['Data may be stale', 'Stale', 'The current view uses the latest available historical snapshot, not a live signal.', 'Wait for the next data refresh before widening the read.']),
  delayed: stateVocabularyEntry('warning', 'warning', ['数据延迟', '已延迟', '证据存在延迟，当前先按观察处理。', '等待延迟消除后再复核。'], ['Data delayed', 'Delayed', 'Evidence is delayed; treat it as observation for now.', 'Review again after the delay clears.']),
  cached: stateVocabularyEntry('warning', 'warning', ['最近快照', '最近可用', '当前展示的是最近一次可用快照，不代表实时状态。', '等待刷新后再复核。'], ['Recent snapshot', 'Recent available', 'The view uses a recent available snapshot, not live state.', 'Review again after the next refresh.']),
  missing: stateVocabularyEntry('critical', 'muted', ['证据待补', '证据待补', '关键输入暂缺，当前不形成候选或强结论。', '等待数据补齐，或先查看已有历史记录。'], ['Evidence missing', 'Missing', 'Key inputs are missing, so no candidate or strong conclusion is formed.', 'Wait for evidence to fill in, or review existing history first.']),
  no_evidence: stateVocabularyEntry('critical', 'muted', ['暂无证据', '暂无证据', '当前没有足够证据支撑页面结论。', '先补齐关键证据，再继续观察。'], ['No evidence', 'No evidence', 'There is not enough evidence to support a page conclusion.', 'Add key evidence before continuing the observation.']),
  insufficient: stateVocabularyEntry('warning', 'warning', ['证据不足', '证据不足', '当前证据不足，暂不扩大结论。', '先补充关键证据，再继续观察。'], ['Evidence insufficient', 'Insufficient', 'Evidence is insufficient; do not widen the conclusion.', 'Add key evidence before continuing the observation.']),
  insufficient_history: stateVocabularyEntry('warning', 'warning', ['历史样本不足', '历史样本不足', '历史样本不足，当前不形成扩大结论。', '补齐历史样本后再复核。'], ['History insufficient', 'History insufficient', 'Historical samples are insufficient, so the conclusion stays narrow.', 'Add historical samples before reviewing again.']),
  disabled: stateVocabularyEntry('info', 'neutral', ['暂未启用', '暂未启用', '该能力当前未对本页面开放，只保留可观察内容。', '查看其他已启用模块，或等待功能开放。'], ['Not enabled', 'Not enabled', 'This capability is not enabled for the page; only observable content remains.', 'Review other enabled modules, or wait for this capability to open.']),
  unavailable: stateVocabularyEntry('critical', 'muted', ['数据暂不可用', '不可用', '该模块暂时无法提供可读数据，页面不会补造结果。', '稍后刷新，或查看其他仍可用的观察模块。'], ['Data temporarily unavailable', 'Unavailable', 'This module cannot provide readable data right now; the page will not invent results.', 'Refresh later, or review other available observation modules.']),
  freshness_unavailable: stateVocabularyEntry('critical', 'muted', ['数据新鲜度暂不可用', '新鲜度不可用', '当前无法确认数据新鲜度，页面不会按实时状态展示。', '等待新鲜度证据恢复后再复核。'], ['Freshness currently unavailable', 'Freshness unavailable', 'Freshness cannot be confirmed, so the page will not present the data as current.', 'Review again after freshness evidence recovers.']),
  blocked: stateVocabularyEntry('critical', 'danger', ['当前无法分析', '已阻断', '关键证据门槛未满足，当前保持观察边界。', '等待阻断条件解除后再复核。'], ['Analysis currently unavailable', 'Blocked', 'Key evidence thresholds are not met, so the view stays within observation boundaries.', 'Review again after the blocking condition clears.']),
  pending: stateVocabularyEntry('info', 'neutral', ['正在等待数据确认', '待确认', '数据仍待确认，暂不形成新结论。', '等待确认完成后再复核。'], ['Waiting for data confirmation', 'Pending', 'Data still awaits confirmation, so no new conclusion is formed.', 'Review again after confirmation completes.']),
  pending_heavy: stateVocabularyEntry('info', 'neutral', ['多项数据仍待确认', '多项待确认', '多项数据仍待确认，暂不形成新结论。', '等待关键数据确认后再复核。'], ['Several data points still await confirmation', 'Pending', 'Several data points still await confirmation, so no new conclusion is formed.', 'Review again after key data is confirmed.']),
  initializing: stateVocabularyEntry('info', 'neutral', ['初始化中', '初始化中', '当前数据仍在准备或刷新，暂不形成新结论。', '等待当前更新完成后再复核。'], ['Initializing', 'Initializing', 'Data is initializing or refreshing; no new conclusion is formed yet.', 'Review again after the current update finishes.']),
  refreshing: stateVocabularyEntry('info', 'neutral', ['更新中', '更新中', '数据正在刷新，暂不形成新结论。', '等待刷新完成后再复核。'], ['Refreshing', 'Refreshing', 'Data is refreshing, so no new conclusion is formed yet.', 'Review again after the refresh finishes.']),
  unknown: stateVocabularyEntry('info', 'neutral', ['状态暂不明确', '暂不明确', '当前状态尚未确认，先保持观察。', '等待状态确认后再复核。'], ['State not yet clear', 'Unknown', 'The state is not confirmed yet; keep it as observation.', 'Review again after the state is confirmed.']),
  observation_only: stateVocabularyEntry('warning', 'warning', ['仅供研究观察', '仅作观察', '当前证据只支持研究观察，不支持扩大结论。', '补齐证据后再提升解读强度。'], ['Research observation only', 'Observation only', 'Current evidence supports observation only, not a wider conclusion.', 'Add evidence before increasing conclusion strength.']),
  rejected: stateVocabularyEntry('critical', 'danger', ['已拒绝', '已拒绝', '当前请求或证据未通过边界检查。', '修正输入或等待证据恢复后再复核。'], ['Rejected', 'Rejected', 'The current request or evidence did not pass boundary checks.', 'Correct the input or wait for evidence to recover before reviewing again.']),
  error: stateVocabularyEntry('critical', 'danger', ['数据读取异常', '读取异常', '当前数据读取异常，页面不会补造结果。', '稍后刷新，或查看其他仍可用的观察模块。'], ['Data read error', 'Read error', 'Data failed to load; the page will not invent results.', 'Refresh later, or review other available observation modules.']),
  failed: stateVocabularyEntry('critical', 'danger', ['数据读取异常', '读取异常', '数据读取失败，页面不会补造结果。', '稍后刷新，或查看其他仍可用的观察模块。'], ['Data read error', 'Read error', 'Data failed to load; the page will not invent results.', 'Refresh later, or review other available observation modules.']),
  failed_closed: stateVocabularyEntry('critical', 'danger', ['已安全关闭', '已安全关闭', '关键证据未满足门槛，系统保持关闭以避免误导。', '等待证据恢复后再重新查看。'], ['Safely closed', 'Safely closed', 'Key evidence did not meet the threshold, so the view stays fail-closed.', 'Review again after evidence recovers.']),
  maintenance: stateVocabularyEntry('warning', 'warning', ['维护中', '维护中', '数据管道维护中，当前只展示已确认的历史观察。', '等待下一次数据刷新。'], ['Maintenance in progress', 'Maintenance', 'The data pipeline is under maintenance; only confirmed historical observations are shown.', 'Wait for the next data refresh.']),
};

const CONSUMER_DATA_STATE_TOKEN_MAP: Record<string, ConsumerDataState> = {
  available: 'available',
  ready: 'available',
  ok: 'available',
  healthy: 'available',
  complete: 'available',
  product_ready: 'available',
  partial: 'partial',
  mixed: 'partial',
  thin: 'partial',
  evidence_partial: 'partial',
  insufficient_coverage: 'partial',
  degraded: 'degraded',
  limited: 'degraded',
  stale: 'stale',
  expired: 'stale',
  old: 'stale',
  delayed: 'delayed',
  cached: 'cached',
  recent: 'cached',
  missing: 'missing',
  empty: 'missing',
  not_configured: 'missing',
  no_data: 'missing',
  no_evidence: 'no_evidence',
  insufficient: 'insufficient',
  insufficient_history: 'insufficient_history',
  insufficient_evidence: 'insufficient',
  disabled: 'disabled',
  not_enabled: 'disabled',
  entitlement_required: 'disabled',
  not_implemented: 'disabled',
  unavailable: 'unavailable',
  freshness_unavailable: 'freshness_unavailable',
  blocked: 'blocked',
  pending: 'pending',
  pending_heavy: 'pending_heavy',
  waiting: 'pending',
  initializing: 'initializing',
  refreshing: 'refreshing',
  updating: 'initializing',
  loading: 'initializing',
  unknown: 'unknown',
  observation_only: 'observation_only',
  observation: 'observation_only',
  rejected: 'rejected',
  denied: 'rejected',
  error: 'error',
  timeout: 'error',
  critical: 'error',
  provider_error: 'error',
  failed: 'failed',
  failed_closed: 'failed_closed',
  fail_closed: 'failed_closed',
  maintenance: 'maintenance',
};

const RAW_CONSUMER_DATA_STATE_PATTERN =
  /\b(provider|debug|trace|schema|raw|runtime|cache|pipeline|dry[-_\s]?run|operator|sourceauthority|reasoncode|contractversion|universe|historical[-_\s]?ohlcv|quote[-_\s]?snapshot|packet|handoff|evidence[-_\s]?famil(?:y|ies)|peer[-_\s]?group[-_\s]?metadata)\b|sourceAuthority|reasonCode|contractVersion|historical_ohlcv|quote_snapshot/i;

export function normalizeConsumerStateToken(value: string | null | undefined): string {
  return String(value || '')
    .trim()
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .toLowerCase()
    .replace(/[:=./\\\s-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
}

export function isConsumerDataStateToken(value: string | null | undefined): boolean {
  const token = normalizeConsumerStateToken(value);
  if (!token) return false;
  if (CONSUMER_DATA_STATE_TOKEN_MAP[token]) return true;
  // Free-text limitation sentences normalize into long snake tokens such as
  // `growth_proxy_evidence_is_unavailable`. Those must not collapse to the
  // generic unavailable/stale state label — phrase maps own the wording.
  const parts = token.split('_').filter(Boolean);
  if (parts.length > 3) return false;
  return token.includes('stale') || token.includes('unavailable');
}

export function resolveConsumerDataState(value: string | null | undefined): ConsumerDataState {
  const token = normalizeConsumerStateToken(value);
  if (!token) return 'partial';
  const mapped = CONSUMER_DATA_STATE_TOKEN_MAP[token];
  if (mapped) return mapped;
  if (token.includes('stale')) return 'stale';
  if (token === 'unavailable' || token.includes('unavailable')) return 'unavailable';
  return 'partial';
}

export function getConsumerDataStateEntry(
  value: ConsumerDataState | string | null | undefined,
  locale: ConsumerStateLocale = 'zh',
): ConsumerDataStateVocabularyEntry {
  const state = resolveConsumerDataState(value);
  const entry = CONSUMER_DATA_STATE_VOCABULARY[state];
  const copy = entry.copy[locale];
  return {
    state,
    label: copy.label,
    shortLabel: copy.shortLabel || copy.label,
    explanation: copy.explanation,
    severity: entry.severity,
    tone: entry.tone,
    nextStep: copy.nextStep,
  };
}

export function getConsumerDataStateLabel(
  value: ConsumerDataState | string | null | undefined,
  locale: ConsumerStateLocale = 'zh',
  variant: 'label' | 'short' = 'label',
): string {
  const entry = getConsumerDataStateEntry(value, locale);
  return variant === 'short' ? entry.shortLabel : entry.label;
}

export function isRawConsumerDataStateText(value: string | null | undefined): boolean {
  return RAW_CONSUMER_DATA_STATE_PATTERN.test(String(value || ''));
}

export function sanitizeConsumerDataStateText(
  value: string | null | undefined,
  state: ConsumerDataState | string | null | undefined = null,
): string {
  const text = String(value || '').trim();
  const entry = getConsumerDataStateEntry(state || value);
  if (!text) return entry.explanation;
  if (isRawConsumerDataStateText(text)) return entry.explanation;
  return text;
}

export function consumerSafeOperatorAction(
  value: string | null | undefined,
  state: ConsumerDataState | string | null | undefined = null,
): string {
  const text = String(value || '').trim();
  const normalized = normalizeConsumerStateToken(text);
  const entry = getConsumerDataStateEntry(state || value);
  if (!text) return entry.nextStep;
  if (/maintenance|pipeline|backfill|repair|provider|operator|runtime|debug|trace/.test(normalized)) {
    return '数据管道维护中。';
  }
  if (/schedule|next_refresh|wait|pending|refreshing|updating/.test(normalized)) {
    return '等待下一次数据刷新。';
  }
  if (/universe|scanner|rerun|refresh|quote|ohlcv|history|cache|daily|handoff|packet/.test(normalized)) {
    return '等待数据刷新后再查看。';
  }
  if (isRawConsumerDataStateText(text)) return entry.nextStep;
  return sanitizeConsumerDataStateText(text, entry.state);
}
