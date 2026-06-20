import { mapConsumerStatusText } from './consumerStatusLabels';
import { sanitizeUserFacingDataIssue } from './userFacingDataIssues';

export type ResearchQueueConsumerLocale = 'zh' | 'en';

type ResearchQueuePriorityTier = 'attention' | 'follow_up' | 'monitor' | 'urgent_review' | string;

type ResearchQueueSuggestedPath = {
  label?: string | null;
  route?: string | null;
  reason?: string | null;
};

type ResearchQueueConsumerInput = {
  priorityTier?: ResearchQueuePriorityTier | null;
  priorityReason?: string | null;
  evidenceState?: string | null;
  missingEvidence?: Array<string | null | undefined> | null;
  suggestedResearchPath?: ResearchQueueSuggestedPath[] | null;
};

type ResearchQueueSafePathCopy = {
  label: string;
  reason: string | null;
};

export type ResearchQueueConsumerCopy = {
  priorityTierLabel: string;
  priorityVariant: 'caution' | 'info' | 'neutral';
  evidenceStateLabel: string;
  priorityReason: string;
  missingEvidence: string[];
  suggestedResearchPath: ResearchQueueSafePathCopy[];
};

const ADVICE_OR_TRADE_WORDS = /建议(买入|卖出|加仓|减仓|持有)|买入|卖出|下单|交易建议|投资建议|止损|止盈|目标价|仓位建议|\b(buy|sell|hold|recommend(?:ation)?|target price|stop loss|position sizing|trade advice|investment advice)\b/i;
const INTERNAL_DIAGNOSTIC_WORDS = /sourceRefs?|reasonCodes?|sourceRefId|request[_\s-]?id|trace[_\s-]?id|correlation[_\s-]?id|queueItemId|provider|cache|runtime|debug|raw|json|schemaVersion|admin|diagnostic|payload|backend snake_case|\b[a-z]+(?:_[a-z0-9]+)+\b/i;
const ENGLISH_OR_TOKEN_WORDS = /[A-Za-z]/;
const STOCK_STRUCTURE_ROUTE = /^\/stocks\/[^/?#]+\/structure-decision$/i;

const EXACT_QUEUE_TEXT: Record<string, Record<ResearchQueueConsumerLocale, string>> = {
  'review structure detail': {
    zh: '查看个股结构，补做资料核对。',
    en: 'Review stock structure and supporting context.',
  },
  'open symbol structure detail': {
    zh: '先核对结构与资料完整性。',
    en: 'Review structure and context completeness first.',
  },
  'stock structure': {
    zh: '查看个股结构',
    en: 'Open Stock Structure',
  },
};

function normalizeCopyKey(value: string | null | undefined): string {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/[.。!?]+$/g, '');
}

function defaultQueueReason(locale: ResearchQueueConsumerLocale): string {
  return locale === 'en' ? 'Evidence coverage still needs review.' : '当前条目的证据覆盖仍需复核。';
}

function defaultEvidenceGap(locale: ResearchQueueConsumerLocale): string {
  return locale === 'en' ? 'Key context still needs review' : '部分关键资料待补充';
}

function defaultPathLabel(locale: ResearchQueueConsumerLocale): string {
  return locale === 'en' ? 'Open research path' : '查看研究路径';
}

function defaultPathReason(locale: ResearchQueueConsumerLocale): string {
  return locale === 'en' ? 'Review the evidence before going further.' : '先补做证据复核。';
}

function structurePathLabel(locale: ResearchQueueConsumerLocale): string {
  return locale === 'en' ? 'Open Stock Structure' : '查看个股结构';
}

function structurePathReason(locale: ResearchQueueConsumerLocale): string {
  return locale === 'en' ? 'Review structure and context completeness first.' : '先核对结构与资料完整性。';
}

export function getResearchQueuePriorityTierLabel(
  tier: ResearchQueuePriorityTier | null | undefined,
  locale: ResearchQueueConsumerLocale = 'zh',
): string {
  if (locale === 'en') {
    if (tier === 'urgent_review') return 'Urgent review';
    if (tier === 'attention') return 'Needs review';
    if (tier === 'follow_up') return 'Follow up';
    return 'Monitor';
  }
  if (tier === 'urgent_review') return '紧急复核';
  if (tier === 'attention') return '建议复核';
  if (tier === 'follow_up') return '持续跟进';
  return '继续观察';
}

export function getResearchQueuePriorityTierVariant(
  tier: ResearchQueuePriorityTier | null | undefined,
): ResearchQueueConsumerCopy['priorityVariant'] {
  if (tier === 'urgent_review') return 'caution';
  if (tier === 'attention') return 'caution';
  if (tier === 'follow_up') return 'info';
  return 'neutral';
}

export function getResearchQueueEvidenceStateLabel(
  state: string | null | undefined,
  locale: ResearchQueueConsumerLocale = 'zh',
): string {
  const token = normalizeCopyKey(state).replace(/\s+/g, '_');
  if (locale === 'en') {
    if (token === 'no_evidence') return 'Key evidence missing';
    if (token === 'stale_or_cached') return 'Needs review';
    if (token === 'ready' || token === 'current') return 'Evidence ready';
    if (token === 'needs_review') return 'Needs review';
    if (token === 'unavailable') return 'Temporarily unavailable';
    if (token === 'symbol_unknown') return 'Symbol needs check';
    if (token === 'unsupported_market') return 'Market needs check';
    return 'Evidence pending';
  }
  if (token === 'no_evidence') return '缺少关键证据';
  if (token === 'stale_or_cached' || token === 'needs_review') return '证据待复核';
  if (token === 'ready' || token === 'current') return '证据就绪';
  if (token === 'unavailable') return '暂不可用';
  if (token === 'symbol_unknown') return '代码待确认';
  if (token === 'unsupported_market') return '市场待确认';
  return '证据待确认';
}

export function getResearchQueueConsumerText(
  value: string | null | undefined,
  locale: ResearchQueueConsumerLocale = 'zh',
  fallback: string | null = null,
): string | null {
  const raw = String(value || '').trim();
  if (!raw) return fallback;

  const exact = EXACT_QUEUE_TEXT[normalizeCopyKey(raw)]?.[locale];
  if (exact) return exact;

  const mapped = mapConsumerStatusText(raw, locale);
  if (mapped !== raw) return mapped;

  if (ADVICE_OR_TRADE_WORDS.test(raw)) {
    return fallback;
  }

  if (INTERNAL_DIAGNOSTIC_WORDS.test(raw)) {
    return sanitizeUserFacingDataIssue(raw, locale);
  }

  if (ENGLISH_OR_TOKEN_WORDS.test(raw)) {
    return fallback;
  }

  return fallback;
}

function getResearchQueueSafePathCopy(
  path: ResearchQueueSuggestedPath,
  locale: ResearchQueueConsumerLocale,
): ResearchQueueSafePathCopy {
  const isStructurePath = STOCK_STRUCTURE_ROUTE.test(path.route || '');
  const fallbackLabel = isStructurePath ? structurePathLabel(locale) : defaultPathLabel(locale);
  const fallbackReason = isStructurePath ? structurePathReason(locale) : defaultPathReason(locale);

  return {
    label: isStructurePath
      ? fallbackLabel
      : (getResearchQueueConsumerText(path.label, locale, fallbackLabel) || fallbackLabel),
    reason: getResearchQueueConsumerText(path.reason, locale, fallbackReason),
  };
}

export function getResearchQueueConsumerCopy(
  input: ResearchQueueConsumerInput,
  locale: ResearchQueueConsumerLocale = 'zh',
): ResearchQueueConsumerCopy {
  const missingEvidence = Array.from(new Set((input.missingEvidence || [])
    .map((value) => getResearchQueueConsumerText(value, locale, defaultEvidenceGap(locale)))
    .filter((value): value is string => Boolean(value))));

  return {
    priorityTierLabel: getResearchQueuePriorityTierLabel(input.priorityTier, locale),
    priorityVariant: getResearchQueuePriorityTierVariant(input.priorityTier),
    evidenceStateLabel: getResearchQueueEvidenceStateLabel(input.evidenceState, locale),
    priorityReason: getResearchQueueConsumerText(input.priorityReason, locale, defaultQueueReason(locale)) || defaultQueueReason(locale),
    missingEvidence: missingEvidence.length ? missingEvidence : [defaultEvidenceGap(locale)],
    suggestedResearchPath: (input.suggestedResearchPath || []).map((path) => getResearchQueueSafePathCopy(path, locale)),
  };
}
