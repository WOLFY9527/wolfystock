export type ConsumerDataState =
  | 'ready'
  | 'partial'
  | 'stale'
  | 'missing'
  | 'disabled'
  | 'unavailable'
  | 'failed_closed'
  | 'maintenance';

export type ConsumerDataStateSeverity = 'success' | 'info' | 'warning' | 'critical';

export interface ConsumerDataStateVocabularyEntry {
  state: ConsumerDataState;
  label: string;
  explanation: string;
  severity: ConsumerDataStateSeverity;
  nextStep: string;
}

const CONSUMER_DATA_STATE_VOCABULARY: Record<ConsumerDataState, ConsumerDataStateVocabularyEntry> = {
  ready: {
    state: 'ready',
    label: '数据可用',
    explanation: '当前信息满足本页面观察所需，可继续按研究边界阅读。',
    severity: 'success',
    nextStep: '继续观察关键证据是否保持一致。',
  },
  partial: {
    state: 'partial',
    label: '部分可用',
    explanation: '已返回部分真实数据，但仍有证据缺口，结论强度需要降低。',
    severity: 'warning',
    nextStep: '先查看已返回的模块，再等待缺口补齐。',
  },
  stale: {
    state: 'stale',
    label: '最近可用',
    explanation: '当前展示的是历史观察快照，不代表实时信号。',
    severity: 'warning',
    nextStep: '等待下一次数据刷新后再扩大解读。',
  },
  missing: {
    state: 'missing',
    label: '证据待补',
    explanation: '关键输入暂缺，当前不形成候选或强结论。',
    severity: 'critical',
    nextStep: '等待数据补齐，或先查看已有历史记录。',
  },
  disabled: {
    state: 'disabled',
    label: '暂未启用',
    explanation: '该能力当前未对本页面开放，只保留可观察内容。',
    severity: 'info',
    nextStep: '查看其他已启用模块，或等待功能开放。',
  },
  unavailable: {
    state: 'unavailable',
    label: '暂不可用',
    explanation: '该模块暂时无法提供可读数据，页面不会补造结果。',
    severity: 'critical',
    nextStep: '稍后刷新，或查看其他仍可用的观察模块。',
  },
  failed_closed: {
    state: 'failed_closed',
    label: '已安全关闭',
    explanation: '关键证据未满足门槛，系统保持关闭以避免误导。',
    severity: 'critical',
    nextStep: '等待证据恢复后再重新查看。',
  },
  maintenance: {
    state: 'maintenance',
    label: '维护中',
    explanation: '数据管道维护中，当前只展示已确认的历史观察。',
    severity: 'warning',
    nextStep: '等待下一次数据刷新。',
  },
};

const RAW_CONSUMER_DATA_STATE_PATTERN =
  /\b(provider|debug|trace|schema|raw|runtime|cache|pipeline|dry[-_\s]?run|operator|sourceauthority|reasoncode|contractversion|universe|historical[-_\s]?ohlcv|quote[-_\s]?snapshot)\b|sourceAuthority|reasonCode|contractVersion|historical_ohlcv|quote_snapshot/i;

function normalizeStateToken(value: string | null | undefined): string {
  return String(value || '')
    .trim()
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .toLowerCase()
    .replace(/[:=./\\\s-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
}

export function resolveConsumerDataState(value: string | null | undefined): ConsumerDataState {
  const token = normalizeStateToken(value);
  if (!token) return 'partial';
  if (['ready', 'ok', 'available', 'healthy', 'complete', 'product_ready'].includes(token)) return 'ready';
  if (['partial', 'mixed', 'thin', 'degraded', 'limited', 'insufficient_coverage'].includes(token)) return 'partial';
  if (['stale', 'delayed', 'expired', 'old', 'cached'].includes(token) || token.includes('stale')) return 'stale';
  if (['missing', 'empty', 'not_configured', 'no_data', 'no_evidence', 'insufficient', 'insufficient_history'].includes(token)) return 'missing';
  if (['disabled', 'not_enabled', 'entitlement_required', 'not_implemented'].includes(token)) return 'disabled';
  if (['maintenance', 'refreshing', 'updating', 'pending'].includes(token)) return 'maintenance';
  if (['failed_closed', 'fail_closed', 'blocked'].includes(token)) return 'failed_closed';
  if (['unavailable', 'error', 'failed', 'timeout', 'critical'].includes(token) || token.includes('unavailable')) return 'unavailable';
  return 'partial';
}

export function getConsumerDataStateEntry(value: ConsumerDataState | string | null | undefined): ConsumerDataStateVocabularyEntry {
  return CONSUMER_DATA_STATE_VOCABULARY[resolveConsumerDataState(value)];
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
  const normalized = normalizeStateToken(text);
  const entry = getConsumerDataStateEntry(state || value);
  if (!text) return entry.nextStep;
  if (/maintenance|pipeline|backfill|repair|provider|operator|runtime|debug|trace/.test(normalized)) {
    return '数据管道维护中。';
  }
  if (/schedule|next_refresh|wait|pending|refreshing|updating/.test(normalized)) {
    return '等待下一次数据刷新。';
  }
  if (/universe|scanner|rerun|refresh|quote|ohlcv|history|cache/.test(normalized)) {
    return '等待数据刷新后再查看。';
  }
  if (isRawConsumerDataStateText(text)) return entry.nextStep;
  return sanitizeConsumerDataStateText(text, entry.state);
}
