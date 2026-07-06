import { mapConsumerStatusText, normalizeConsumerStatusToken } from './consumerStatusLabels';
import { sanitizeUserFacingDataIssue } from './userFacingDataIssues';
import type { WatchlistRowResearchPacketResponse } from '../types/watchlist';

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

type WatchlistRowResearchPacketQuoteState = 'available' | 'missing' | 'stale' | 'unknown';
type WatchlistRowResearchPacketStatus = 'ready' | 'partial' | 'blocked' | 'unknown';

export type WatchlistRowResearchPacketConsumerCopy = {
  identityStateLabel: string | null;
  identityStateVariant: 'success' | 'info' | 'caution';
  freshnessStateLabel: string | null;
  freshnessStateVariant: 'success' | 'info' | 'caution' | 'danger';
  quoteStateLabel: string;
  quoteStateVariant: 'success' | 'info' | 'caution';
  quotePrice: number | null;
  quoteAsOf: string | null;
  researchStatusLabel: string;
  researchStatusVariant: 'success' | 'info' | 'caution' | 'danger';
  scannerLineageLabel: string;
  scannerLineageVariant: 'info' | 'caution';
  missingSummary: string | null;
  nextDataActionLabel: string;
  noAdviceLabel: string | null;
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
  'missing evidence needs review': {
    zh: '研究上下文待补',
    en: 'Research context pending',
  },
  'price-history evidence': {
    zh: '价格与历史数据待补',
    en: 'Price/history context pending',
  },
  'scanner score evidence': {
    zh: '扫描评分待更新',
    en: 'Scanner score pending',
  },
  'supporting evidence': {
    zh: '研究上下文待补',
    en: 'Research context pending',
  },
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

const PACKET_QUOTE_LABELS: Record<WatchlistRowResearchPacketQuoteState, Record<ResearchQueueConsumerLocale, string>> = {
  available: {
    zh: '报价可用',
    en: 'Quote ready',
  },
  missing: {
    zh: '报价待补',
    en: 'Quote needed',
  },
  stale: {
    zh: '报价待确认',
    en: 'Quote needs confirmation',
  },
  unknown: {
    zh: '时效未知',
    en: 'Freshness unknown',
  },
};

const PACKET_STATUS_LABELS: Record<WatchlistRowResearchPacketStatus, Record<ResearchQueueConsumerLocale, string>> = {
  ready: {
    zh: '可研究',
    en: 'Research ready',
  },
  partial: {
    zh: '部分可用',
    en: 'Partially ready',
  },
  blocked: {
    zh: '数据待补',
    en: 'Data needed',
  },
  unknown: {
    zh: '研究状态未知',
    en: 'Research status unknown',
  },
};

function packetIdentityStateLabel(
  state: string | null | undefined,
  locale: ResearchQueueConsumerLocale,
): { label: string | null; variant: WatchlistRowResearchPacketConsumerCopy['identityStateVariant'] } {
  const token = normalizeConsumerStatusToken(state);
  if (token === 'resolved') {
    return {
      label: locale === 'en' ? 'Identity confirmed' : '身份已确认',
      variant: 'success',
    };
  }
  if (token === 'unsupported' || token === 'unavailable') {
    return {
      label: locale === 'en' ? 'Identity unavailable' : '身份暂不可用',
      variant: 'caution',
    };
  }
  if (token === 'unresolved') {
    return {
      label: locale === 'en' ? 'Identity unresolved' : '身份待确认',
      variant: 'caution',
    };
  }
  return {
    label: null,
    variant: 'info',
  };
}

function packetFreshnessStateLabel(
  state: string | null | undefined,
  locale: ResearchQueueConsumerLocale,
): { label: string | null; variant: WatchlistRowResearchPacketConsumerCopy['freshnessStateVariant'] } {
  const token = normalizeConsumerStatusToken(state);
  if (token === 'available') {
    return {
      label: locale === 'en' ? 'Freshness available' : '时效可用',
      variant: 'success',
    };
  }
  if (token === 'partial') {
    return {
      label: locale === 'en' ? 'Freshness partial' : '时效部分可用',
      variant: 'info',
    };
  }
  if (token === 'stale') {
    return {
      label: locale === 'en' ? 'Freshness stale' : '时效较旧',
      variant: 'caution',
    };
  }
  if (token === 'unavailable') {
    return {
      label: locale === 'en' ? 'Freshness unavailable' : '时效不可用',
      variant: 'danger',
    };
  }
  if (token === 'pending') {
    return {
      label: locale === 'en' ? 'Freshness pending' : '时效待确认',
      variant: 'caution',
    };
  }
  if (token === 'unknown') {
    return {
      label: locale === 'en' ? 'Freshness unknown' : '时效未知',
      variant: 'caution',
    };
  }
  return {
    label: null,
    variant: 'caution',
  };
}

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

function uniqueLabels(labels: string[]): string[] {
  return Array.from(new Set(labels.filter(Boolean)));
}

function hasPacketMissingData(tokens: string[], candidates: string[]): boolean {
  return candidates.some((candidate) => tokens.includes(candidate));
}

function packetQuoteStateLabel(state: WatchlistRowResearchPacketQuoteState, locale: ResearchQueueConsumerLocale): string {
  return PACKET_QUOTE_LABELS[state][locale];
}

function packetResearchStatusLabel(state: WatchlistRowResearchPacketStatus, locale: ResearchQueueConsumerLocale): string {
  return PACKET_STATUS_LABELS[state][locale];
}

function packetScannerLineageLabel(
  packet: WatchlistRowResearchPacketResponse,
  locale: ResearchQueueConsumerLocale,
): { label: string; variant: WatchlistRowResearchPacketConsumerCopy['scannerLineageVariant'] } {
  const lineage = packet.scannerLineage;
  const hasScannerLineage = packet.savedItemSource === 'scanner'
    || Boolean(lineage.runId != null || lineage.rank != null || lineage.score != null || lineage.lastScoredAt);
  return hasScannerLineage
    ? {
        label: locale === 'en' ? 'From scanner' : '来自扫描',
        variant: 'info',
      }
    : {
        label: locale === 'en' ? 'Awaiting scan' : '待扫描',
        variant: 'caution',
      };
}

function packetMissingDataSummary(
  missingData: string[],
  quoteState: WatchlistRowResearchPacketQuoteState,
  locale: ResearchQueueConsumerLocale,
): string | null {
  const tokens = missingData.map((item) => normalizeConsumerStatusToken(item));
  const labels: string[] = [];

  if (hasPacketMissingData(tokens, ['quote', 'price_history', 'history'])) {
    labels.push(locale === 'en' ? 'Quote and history needed' : '报价与历史待补');
  }
  if (hasPacketMissingData(tokens, ['fundamentals', 'filing_event_catalyst', 'events', 'peer_benchmark', 'peer'])) {
    labels.push(locale === 'en' ? 'Fundamentals, events, and peer needed' : '基本面、事件、同业待补');
  }
  if (hasPacketMissingData(tokens, ['structure_analysis', 'structure'])) {
    labels.push(locale === 'en' ? 'Structure needed' : '结构待补');
  }

  if (!labels.length) {
    if (quoteState === 'missing') return locale === 'en' ? 'Quote needed' : '报价待补';
    if (quoteState === 'stale' || quoteState === 'unknown') return locale === 'en' ? 'Quote needs confirmation' : '报价待确认';
    return null;
  }

  return uniqueLabels(labels).join(locale === 'en' ? ' · ' : ' · ');
}

function packetNextDataActionLabel(
  missingData: string[],
  quoteState: WatchlistRowResearchPacketQuoteState,
  researchStatus: WatchlistRowResearchPacketStatus,
  locale: ResearchQueueConsumerLocale,
  readinessState?: string | null,
): string {
  const normalizedReadiness = normalizeConsumerStatusToken(readinessState);
  if (normalizedReadiness === 'unknown') {
    return locale === 'en' ? 'Review stock structure' : '查看个股结构';
  }
  const tokens = missingData.map((item) => normalizeConsumerStatusToken(item));
  if (hasPacketMissingData(tokens, ['quote', 'price_history', 'history'])) {
    return locale === 'en' ? 'Add quote and history' : '补报价与历史';
  }
  if (hasPacketMissingData(tokens, ['fundamentals', 'filing_event_catalyst', 'events', 'peer_benchmark', 'peer'])) {
    return locale === 'en' ? 'Add fundamentals, events, and peer' : '补基本面、事件、同业';
  }
  if (hasPacketMissingData(tokens, ['structure_analysis', 'structure'])) {
    return locale === 'en' ? 'Add structure evidence' : '补结构';
  }
  if (quoteState === 'missing') {
    return locale === 'en' ? 'Add quote' : '补报价';
  }
  if (quoteState === 'stale' || quoteState === 'unknown') {
    return locale === 'en' ? 'Confirm quote' : '确认报价';
  }
  if (researchStatus === 'ready') {
    return locale === 'en' ? 'Keep reviewing' : '继续复核';
  }
  return locale === 'en' ? 'Add data' : '补数据';
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

function normalizePacketQuoteState(value: string | null | undefined): WatchlistRowResearchPacketQuoteState {
  const token = normalizeConsumerStatusToken(value);
  if (token === 'available' || token === 'missing' || token === 'stale' || token === 'unknown') {
    return token;
  }
  return 'unknown';
}

function normalizePacketResearchStatus(value: string | null | undefined): WatchlistRowResearchPacketStatus {
  const token = normalizeConsumerStatusToken(value);
  if (token === 'ready' || token === 'partial' || token === 'blocked' || token === 'unknown') {
    return token;
  }
  return 'unknown';
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

export function getWatchlistRowResearchPacketConsumerCopy(
  packet: WatchlistRowResearchPacketResponse | null | undefined,
  locale: ResearchQueueConsumerLocale = 'zh',
): WatchlistRowResearchPacketConsumerCopy | null {
  if (!packet) return null;

  const quoteState = normalizePacketQuoteState(packet.quote?.state);
  const researchStatus = normalizePacketResearchStatus(packet.researchStatus);
  const scannerLineage = packetScannerLineageLabel(packet, locale);
  const identityState = packetIdentityStateLabel(
    packet.researchReadiness?.identityState || packet.identity?.identityState,
    locale,
  );
  const freshnessState = packetFreshnessStateLabel(packet.researchReadiness?.freshnessState, locale);
  const missingSummary = packetMissingDataSummary(packet.missingData || [], quoteState, locale);
  const nextDataActionLabel = packetNextDataActionLabel(
    packet.missingData || [],
    quoteState,
    researchStatus,
    locale,
    packet.researchReadiness?.state,
  );
  const noAdviceLabel = packet.observationOnly || packet.noAdviceDisclosure
    ? (locale === 'en' ? 'Observation only' : '仅供观察')
    : null;

  return {
    identityStateLabel: identityState.label,
    identityStateVariant: identityState.variant,
    freshnessStateLabel: freshnessState.label,
    freshnessStateVariant: freshnessState.variant,
    quoteStateLabel: packetQuoteStateLabel(quoteState, locale),
    quoteStateVariant: quoteState === 'available' ? 'success' : 'caution',
    quotePrice: typeof packet.quote?.price === 'number' && Number.isFinite(packet.quote.price) ? packet.quote.price : null,
    quoteAsOf: packet.quote?.asOf ?? null,
    researchStatusLabel: packetResearchStatusLabel(researchStatus, locale),
    researchStatusVariant: researchStatus === 'ready'
      ? 'success'
      : researchStatus === 'partial'
        ? 'info'
        : researchStatus === 'blocked'
          ? 'danger'
          : 'caution',
    scannerLineageLabel: scannerLineage.label,
    scannerLineageVariant: scannerLineage.variant,
    missingSummary,
    nextDataActionLabel,
    noAdviceLabel,
  };
}
