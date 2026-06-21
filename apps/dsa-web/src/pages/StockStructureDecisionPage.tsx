import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import {
  ConsoleBoard,
  ConsoleContextRail,
  ConsoleStatusStrip,
  MetricStrip,
  ResearchConsoleShell,
  WolfyCommandBar,
} from '../components/linear/LinearPrimitives';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import PeerCorrelationSnapshotBlock from '../components/common/PeerCorrelationSnapshotBlock';
import { StatusBadge } from '../components/ui/StatusBadge';
import { TerminalButton, TerminalChip, TerminalEmptyState } from '../components/terminal/TerminalPrimitives';
import { createParsedApiError, getParsedApiError, type ParsedApiError } from '../api/error';
import {
  stocksApi,
  type SymbolResearchPacket,
  type StockPeerCorrelationSnapshot,
  type StockStructureDecisionResponse,
  type StockValidationResponse,
  type StockSymbolCompareEvidenceEntry,
  type StockSymbolCompareEvidencePacket,
  type StockSymbolCompareFreshness,
} from '../api/stocks';
import { EvidenceGapExplanationList } from '../components/research/EvidenceGapExplanation';
import { useI18n } from '../contexts/UiLanguageContext';
import { getConsumerStatusLabel, mapConsumerStatusText } from '../utils/consumerStatusLabels';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';
import { sanitizeUserFacingDataIssue } from '../utils/userFacingDataIssues';
import {
  RoughBulletList,
  RoughKeyValueRows,
  RoughScoreRows,
  RoughSectionCard,
  RoughSurfaceIntro,
} from './roughShellShared';

const COMPONENT_LABELS = {
  trend: { zh: '趋势', en: 'Trend' },
  relativeStrength: { zh: '相对强弱', en: 'Relative strength' },
  volumePressure: { zh: '量能压力', en: 'Volume pressure' },
  volatilityCompression: { zh: '波动压缩', en: 'Volatility compression' },
  breakoutQuality: { zh: '突破质量', en: 'Breakout quality' },
  pullbackHealth: { zh: '回撤健康度', en: 'Pullback health' },
  riskExtension: { zh: '延展风险', en: 'Risk extension' },
  evidenceQuality: { zh: '证据质量', en: 'Evidence quality' },
} as const;

const CONSUMER_COPY_UNSAFE_PATTERN =
  /\b(sourceAuthority|source_authority|score-grade|score_grade|proxy-only|proxy_only|provider|debug|trace|traceId|raw|sourceRef|sourceRefId|reasonCode|requestId|cache|schema|schemaVersion|runtime|payload|json|policyVersion|local_db|backend|fallback|observation-only|observation_only|evidence families|evidence_families|insufficient_evidence|ohlcv|buy now|sell now|hold|recommend(?:ation)?|target price|stop loss|position sizing)\b|买入|卖出|持有|推荐|目标价|止损|仓位建议/i;

function looksUnsafeForConsumer(value: string | null | undefined): boolean {
  const text = String(value || '').trim();
  if (!text) return false;
  return CONSUMER_COPY_UNSAFE_PATTERN.test(text) || /\b[a-z]+(?:_[a-z0-9]+)+\b/i.test(text);
}

function safeConsumerText(
  value: string | number | null | undefined,
  language: 'zh' | 'en',
  fallback: string,
): string {
  const text = String(value ?? '').trim();
  if (!text) return fallback;
  if (!looksUnsafeForConsumer(text)) return text;
  const sanitized = sanitizeUserFacingDataIssue(text, language);
  return looksUnsafeForConsumer(sanitized) ? fallback : sanitized;
}

function safeOptionalConsumerText(
  value: string | number | null | undefined,
  language: 'zh' | 'en',
): string | null {
  const text = String(value ?? '').trim();
  if (!text || text === '--') return null;
  const safe = safeConsumerText(text, language, '');
  return safe.trim() || null;
}

function safeConsumerList(values: Array<string | null | undefined>, language: 'zh' | 'en'): string[] {
  return compactUnique(values
    .map((value) => safeOptionalConsumerText(value, language))
    .filter(Boolean) as string[]);
}

function compactUnique(values: string[]): string[] {
  return values.filter((value, index, list) => value && list.indexOf(value) === index);
}

function localLabel(key: string, language: 'zh' | 'en'): string {
  const mapped = COMPONENT_LABELS[key as keyof typeof COMPONENT_LABELS];
  if (mapped) {
    return mapped[language];
  }
  return key.replace(/([a-z])([A-Z])/g, '$1 $2');
}

function confidenceLabel(value: string, language: 'zh' | 'en') {
  switch (value.toLowerCase()) {
    case 'high':
      return language === 'en' ? 'High' : '高';
    case 'medium':
      return language === 'en' ? 'Medium' : '中';
    case 'low':
      return language === 'en' ? 'Low' : '低';
    default:
      return value;
  }
}

function confidenceCapLabel(value: unknown, language: 'zh' | 'en'): string {
  if (value == null || value === '') return '--';
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return confidenceLabel(String(value), language);
}

function toneFor(value: string | null | undefined): string {
  const normalized = String(value || '').toLowerCase();
  if (['available', 'high', 'ready', 'complete', 'breakout'].includes(normalized)) return 'success';
  if (['medium', 'partial', 'range', 'neutral'].includes(normalized)) return 'warning';
  if (['low', 'unavailable', 'lowconfidence', 'low_confidence', 'blocked'].includes(normalized)) return 'error';
  return 'info';
}

function symbolSegmentFromPathname(pathname: string): string {
  const match = pathname.match(/\/stocks\/([^/?#]+)\/structure-decision/i);
  if (!match?.[1]) return '';
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

function parseStockStructureSymbols(value: string | null | undefined): string[] {
  return [...new Set(String(value || '')
    .split(/[,\s;|+]+/)
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean))];
}

function parsePositiveInteger(value: string | null): number | undefined {
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
}

function evidenceKindLabel(kind: string | null | undefined, language: 'zh' | 'en'): string {
  const normalized = String(kind || '').toLowerCase();
  const labels: Record<string, { zh: string; en: string }> = {
    daily_ohlcv: { zh: '日线数据', en: 'Daily price history' },
    benchmark_ohlcv: { zh: '基准日线数据', en: 'Benchmark price history' },
    structure_state: { zh: '结构状态', en: 'Structure state' },
    data_quality: { zh: '数据质量', en: 'Data quality' },
    relative_strength: { zh: '相对强弱证据', en: 'Relative strength evidence' },
  };
  const mapped = labels[normalized];
  if (mapped) return mapped[language];
  if (looksUnsafeForConsumer(kind)) {
    return language === 'en' ? 'Evidence' : '证据';
  }
  const readable = normalized.replace(/[_-]+/g, ' ').trim();
  return readable || (language === 'en' ? 'Evidence' : '证据');
}

function statusLabel(status: string | null | undefined, language: 'zh' | 'en'): string {
  const consumerLabel = getConsumerStatusLabel(status, language);
  if (consumerLabel) {
    return consumerLabel;
  }
  const normalized = String(status || '').toLowerCase();
  const labels: Record<string, { zh: string; en: string }> = {
    available: { zh: '可用', en: 'Ready' },
    partial: { zh: '部分可用', en: 'Partial' },
    unavailable: { zh: '不可用', en: 'Not ready' },
    degraded: { zh: '降级', en: 'Degraded' },
  };
  const mapped = labels[normalized]?.[language];
  if (mapped) return mapped;
  if (looksUnsafeForConsumer(status)) {
    return language === 'en' ? 'not ready' : '暂未就绪';
  }
  return status || '--';
}

function normalizeStockConsumerToken(value: string | null | undefined): string {
  return String(value || '')
    .trim()
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .toLowerCase()
    .replace(/[:=./\\\s-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function stockStructureStateLabel(value: string | null | undefined, language: 'zh' | 'en'): string | null {
  const token = normalizeStockConsumerToken(value);
  if (!token) return null;
  const labels: Record<string, { zh: string; en: string }> = {
    accumulation: { zh: '吸筹阶段', en: 'Accumulation phase' },
    breakdown: { zh: '结构走弱', en: 'Structure under pressure' },
    breakout: { zh: '突破观察', en: 'Breakout watch' },
    distribution: { zh: '派发压力', en: 'Distribution pressure' },
    low_confidence: { zh: '证据不足', en: 'Evidence limited' },
    mixed: { zh: '结构分化', en: 'Mixed structure' },
    neutral: { zh: '结构中性', en: 'Neutral structure' },
    pullback: { zh: '回撤观察', en: 'Pullback watch' },
    range: { zh: '区间震荡', en: 'Range-bound' },
    insufficient_evidence: { zh: '证据不足', en: 'Evidence limited' },
    unavailable: { zh: '数据暂缺', en: 'Data temporarily missing' },
  };
  const mapped = labels[token]?.[language];
  if (mapped) return mapped;
  return safeOptionalConsumerText(mapConsumerStatusText(value, language), language);
}

function periodLabel(period: string | null | undefined, language: 'zh' | 'en'): string | null {
  if (!period) return null;
  const normalized = String(period).toLowerCase();
  if (normalized === 'daily') return language === 'en' ? 'Daily' : '日线';
  if (normalized === 'weekly') return language === 'en' ? 'Weekly' : '周线';
  return String(period);
}

function barsRangeLabel(min: unknown, max: unknown, language: 'zh' | 'en'): string | null {
  const minValue = Number(min);
  const maxValue = Number(max);
  const hasMin = Number.isFinite(minValue);
  const hasMax = Number.isFinite(maxValue);
  if (!hasMin && !hasMax) return null;
  if (hasMin && hasMax && minValue !== maxValue) {
    return language === 'en' ? `${minValue}-${maxValue} usable bars` : `${minValue}-${maxValue} 根可用`;
  }
  const value = hasMin ? minValue : maxValue;
  return language === 'en' ? `${value} usable bars` : `${value} 根可用`;
}

function barsCountLabel(value: unknown, language: 'zh' | 'en'): string | null {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return language === 'en' ? `${numeric} bars` : `${numeric} 根`;
}

function sharedEvidenceMeta(item: StockSymbolCompareEvidenceEntry, language: 'zh' | 'en'): string {
  return [
    statusLabel(item.status, language),
    periodLabel(item.period, language),
    barsRangeLabel(item.usableBarsMin, item.usableBarsMax, language),
  ].filter(Boolean).join(' · ');
}

function freshnessMeta(item: StockSymbolCompareFreshness | undefined, language: 'zh' | 'en'): string {
  if (!item) return language === 'en' ? 'No freshness summary' : '暂无新鲜度摘要';
  return [
    statusLabel(item.status, language),
    periodLabel(item.period, language),
    barsCountLabel(item.usableBars, language),
  ].filter(Boolean).join(' · ');
}

function safeEvidenceValue(value: string | number | null | undefined, language: 'zh' | 'en'): string {
  const mapped = typeof value === 'string' ? stockStructureStateLabel(value, language) : null;
  return mapped || safeConsumerText(value, language, language === 'en' ? 'Evidence pending' : '证据暂不可用');
}

function missingEvidenceCopy(
  symbol: string,
  gap: StockStructureDecisionResponse['missingEvidence'][number],
  language: 'zh' | 'en',
): string {
  const gapKey = String(gap.kind || gap.code || gap.field || '').toLowerCase();
  if (gapKey === 'symbol_validation' || gapKey === 'symbol_not_found' || gapKey === 'invalid_symbol') {
    return language === 'en'
      ? `${symbol} was not found. Check the code, or return to search and choose again.`
      : '标的未找到。未找到该标的，请检查代码是否正确，或返回搜索重新选择。';
  }
  const fallback = language === 'en'
    ? `${symbol} has missing compare evidence.`
    : `${symbol} 的部分对比证据暂未就绪。`;
  const raw = gap.message || gap.kind || gap.code || gap.field || '';
  if (!raw) return fallback;
  if (looksUnsafeForConsumer(raw)) return fallback;
  return safeConsumerText(raw || evidenceKindLabel(gap.kind, language), language, fallback);
}

function safeResearchNextSteps(values: string[], language: 'zh' | 'en'): string[] {
  const fallback = language === 'en'
    ? 'Complete comparable-symbol evidence before reviewing the comparison again.'
    : '补齐可比较标的的基础证据后再复核。';
  return compactUnique(values.map((value) => (
    looksUnsafeForConsumer(value) ? fallback : safeConsumerText(value, language, fallback)
  ))).slice(0, 4);
}

function hasPeerCorrelationContent(snapshot: StockPeerCorrelationSnapshot | null | undefined): snapshot is StockPeerCorrelationSnapshot {
  if (!snapshot) return false;
  return Boolean(
    snapshot.peerGroup.symbols.length
      || snapshot.peerEvidence.length
      || snapshot.divergenceEvidence.length
      || snapshot.staleInputs.length
      || snapshot.missingInputs.length
      || snapshot.researchNextSteps.length,
  );
}

function firstComparablePeerSymbol(
  snapshot: StockPeerCorrelationSnapshot | null | undefined,
  primarySymbol: string,
): string | null {
  if (!snapshot) return null;
  const primary = primarySymbol.toUpperCase();
  return snapshot.peerGroup.symbols
    .map((symbol) => symbol.trim().toUpperCase())
    .find((symbol) => symbol && symbol !== primary) ?? null;
}

function buildComparePath(symbols: string[]): string {
  return `/stocks/${symbols.map((symbol) => encodeURIComponent(symbol)).join(',')}/structure-decision`;
}

type SymbolNotFoundState = {
  symbol: string;
};

type StockResearchFact = {
  key: string;
  label: string;
  value: string;
  detail?: string;
};

type EvidenceStackBucket = 'available' | 'missing' | 'partial' | 'stale';

type EvidenceStackRow = {
  key: string;
  label: string;
  value: string;
  bucket: EvidenceStackBucket;
};

function evidenceStateBucket(value: string | null | undefined): EvidenceStackBucket {
  const token = normalizeStockConsumerToken(value);
  if (token === 'available' || token === 'ready') return 'available';
  if (token === 'stale' || token === 'delayed') return 'stale';
  if (token === 'partial' || token === 'insufficient') return 'partial';
  return 'missing';
}

function quoteEvidenceLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  const bucket = evidenceStateBucket(value);
  if (bucket === 'available') return language === 'en' ? 'Quote ready' : '报价可用';
  if (bucket === 'stale') return language === 'en' ? 'Quote may be delayed' : '报价可能延迟';
  return language === 'en' ? 'Quote needed' : '报价待补';
}

function historyEvidenceLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  const bucket = evidenceStateBucket(value);
  if (bucket === 'available') return language === 'en' ? 'History ready' : '历史可用';
  if (bucket === 'stale') return language === 'en' ? 'History may be stale' : '历史可能延迟';
  return language === 'en' ? 'History needed' : '历史待补';
}

function identityEvidenceLabel(bucket: EvidenceStackBucket, language: 'zh' | 'en'): string {
  return bucket === 'available'
    ? (language === 'en' ? 'Symbol context ready' : '标的上下文可用')
    : (language === 'en' ? 'Symbol context needed' : '标的上下文待补');
}

function fundamentalsEvidenceLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  return evidenceStateBucket(value) === 'available'
    ? (language === 'en' ? 'Fundamentals ready' : '基本面可用')
    : (language === 'en' ? 'Fundamentals needed' : '基本面待补');
}

function newsEvidenceLabel(value: string | null | undefined, hasLatest: boolean, language: 'zh' | 'en'): string {
  return evidenceStateBucket(value) === 'available' || hasLatest
    ? (language === 'en' ? 'News leads ready' : '新闻线索可用')
    : (language === 'en' ? 'News leads needed' : '新闻线索待补');
}

function riskEvidenceLabel(bucket: EvidenceStackBucket, language: 'zh' | 'en'): string {
  return bucket === 'available'
    ? (language === 'en' ? 'Risk source ready' : '风险来源可用')
    : (language === 'en' ? 'Risk source needed' : '风险来源待补');
}

function marketEvidenceLabel(bucket: EvidenceStackBucket, language: 'zh' | 'en'): string {
  return bucket === 'available'
    ? (language === 'en' ? 'Market context ready' : '市场线索可用')
    : (language === 'en' ? 'Market context needed' : '市场线索待补');
}

function researchPacketEvidenceLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  const token = normalizeStockConsumerToken(value);
  return token === 'blocked' || token === 'unknown'
    ? (language === 'en' ? 'Research packet pending' : '研究包待生成')
    : (language === 'en' ? 'Research packet ready' : '研究包可用');
}

function missingDataLabel(value: string, language: 'zh' | 'en'): string {
  const token = normalizeStockConsumerToken(value);
  const labels: Record<string, { zh: string; en: string }> = {
    quote: { zh: '报价', en: 'quote' },
    price_history: { zh: '历史', en: 'history' },
    history: { zh: '历史', en: 'history' },
    structure_analysis: { zh: '结构', en: 'structure' },
    structure: { zh: '结构', en: 'structure' },
    fundamentals: { zh: '基本面', en: 'fundamentals' },
    filing_event_catalyst: { zh: '事件', en: 'events' },
    events: { zh: '事件', en: 'events' },
    peer_benchmark: { zh: '同业', en: 'peer' },
    peer: { zh: '同业', en: 'peer' },
  };
  return labels[token]?.[language] ?? (language === 'en' ? 'data' : '资料');
}

function hasMissingData(packet: SymbolResearchPacket, tokens: string[]): boolean {
  const normalized = packet.missingData.map(normalizeStockConsumerToken);
  return tokens.some((token) => normalized.includes(token));
}

function buildEvidenceGapLabels(packet: SymbolResearchPacket, language: 'zh' | 'en'): string[] {
  const labels = packet.missingData.map((item) => {
    const token = normalizeStockConsumerToken(item);
    if (token === 'quote') return language === 'en' ? 'Quote needed' : '报价待补';
    if (token === 'history' || token === 'price_history') return language === 'en' ? 'History needed' : '历史待补';
    if (token === 'fundamentals') return language === 'en' ? 'Fundamentals needed' : '基本面待补';
    if (token === 'events' || token === 'filing_event_catalyst') return language === 'en' ? 'News leads needed' : '新闻线索待补';
    if (token === 'peer' || token === 'peer_benchmark' || token === 'market_context') return language === 'en' ? 'Market context needed' : '市场线索待补';
    if (token === 'structure' || token === 'risk') return language === 'en' ? 'Risk source needed' : '风险来源待补';
    return language === 'en' ? `${missingDataLabel(item, language)} needed` : `${missingDataLabel(item, language)}待补`;
  });
  return compactUnique(labels).slice(0, 5);
}

function buildEvidenceStackRows(packet: SymbolResearchPacket, language: 'zh' | 'en'): EvidenceStackRow[] {
  const hasSymbolContext = Boolean(
    packet.identity.name
      || packet.identity.exchange
      || packet.identity.sector
      || packet.identity.industry,
  );
  const hasMarketContext = Boolean(
    packet.identity.exchange
      || packet.identity.sector
      || packet.identity.industry
      || packet.peer.benchmark,
  ) && !hasMissingData(packet, ['peer_benchmark', 'market_context']);
  const riskBucket = evidenceStateBucket(packet.structure.state);
  const packetBucket = evidenceStateBucket(packet.researchStatus);
  return [
    {
      key: 'quote',
      label: language === 'en' ? 'Quote' : '报价',
      value: quoteEvidenceLabel(packet.quote.state, language),
      bucket: evidenceStateBucket(packet.quote.state),
    },
    {
      key: 'symbol-context',
      label: language === 'en' ? 'Symbol context' : '标的上下文',
      value: identityEvidenceLabel(hasSymbolContext ? 'available' : 'missing', language),
      bucket: hasSymbolContext ? 'available' : 'missing',
    },
    {
      key: 'history',
      label: language === 'en' ? 'History' : '历史',
      value: historyEvidenceLabel(packet.history.state, language),
      bucket: evidenceStateBucket(packet.history.state),
    },
    {
      key: 'fundamentals',
      label: language === 'en' ? 'Fundamentals' : '基本面',
      value: fundamentalsEvidenceLabel(packet.fundamentals.state, language),
      bucket: evidenceStateBucket(packet.fundamentals.state),
    },
    {
      key: 'news',
      label: language === 'en' ? 'News / events' : '新闻 / 事件',
      value: newsEvidenceLabel(packet.events.state, packet.events.latest.length > 0, language),
      bucket: packet.events.latest.length > 0 ? 'available' : evidenceStateBucket(packet.events.state),
    },
    {
      key: 'risk',
      label: language === 'en' ? 'Risk source' : '风险来源',
      value: riskEvidenceLabel(riskBucket, language),
      bucket: riskBucket,
    },
    {
      key: 'market-context',
      label: language === 'en' ? 'Market context' : '市场线索',
      value: marketEvidenceLabel(hasMarketContext ? 'available' : 'missing', language),
      bucket: hasMarketContext ? 'available' : 'missing',
    },
    {
      key: 'research-packet',
      label: language === 'en' ? 'Research packet' : '研究包',
      value: researchPacketEvidenceLabel(packet.researchStatus, language),
      bucket: packetBucket,
    },
  ];
}

function evidenceStackCounts(rows: EvidenceStackRow[]): Record<EvidenceStackBucket, number> {
  return rows.reduce<Record<EvidenceStackBucket, number>>((counts, row) => ({
    ...counts,
    [row.bucket]: counts[row.bucket] + 1,
  }), {
    available: 0,
    missing: 0,
    partial: 0,
    stale: 0,
  });
}

function evidenceCompletenessLabel(counts: Record<EvidenceStackBucket, number>, language: 'zh' | 'en'): string {
  const complete = counts.missing === 0 && counts.partial === 0 && counts.stale === 0;
  return complete
    ? (language === 'en' ? 'Evidence complete' : '证据完整')
    : (language === 'en' ? 'Evidence partially ready' : '证据部分可用');
}

function evidenceAuthorityLabels(packet: SymbolResearchPacket, language: 'zh' | 'en'): string[] {
  if (packet.observationOnly || !packet.decisionGrade) {
    return [
      language === 'en' ? 'Observation only' : '仅观察',
      language === 'en' ? 'Score needs confirmation' : '评分待确认',
    ];
  }
  return [language === 'en' ? 'Authoritative' : '权威证据可用'];
}

function evidenceCountLabels(counts: Record<EvidenceStackBucket, number>, language: 'zh' | 'en'): string[] {
  const labels = [
    [counts.available, language === 'en' ? 'ready' : '可用'],
    [counts.missing, language === 'en' ? 'needed' : '待补'],
    [counts.partial, language === 'en' ? 'partial' : '部分'],
    [counts.stale, language === 'en' ? 'delayed' : '延迟'],
  ] as const;
  return labels
    .filter(([count]) => count > 0)
    .map(([count, label]) => language === 'en' ? `${count} ${label}` : `${label} ${count}`);
}

function isSymbolNotFoundValidation(
  validation: StockValidationResponse | null | undefined,
): validation is StockValidationResponse {
  if (!validation) return false;
  if (validation.exists || validation.valid) return false;
  return ['invalid_format', 'unsupported_market', 'ambiguous', 'not_found'].includes(String(validation.status || ''));
}

function numericValue(value: unknown): number | null {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function isUnavailableStructureState(value: string | null | undefined): boolean {
  const normalized = String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_');
  return !normalized
    || ['lowconfidence', 'low_confidence', 'unavailable', 'unknown', 'insufficient_evidence', 'no_data', 'blocked'].includes(normalized);
}

function buildPacketFacts(
  data: StockStructureDecisionResponse,
  scoreRows: Array<{ key: string; label: string; value: number }>,
  language: 'zh' | 'en',
): StockResearchFact[] {
  const facts: StockResearchFact[] = [];
  const usableBars = numericValue(data.dataQuality.usableBars);
  const period = periodLabel(data.dataQuality.period, language);
  const status = statusLabel(data.dataQuality.status, language);
  const structureState = stockStructureStateLabel(data.structureState, language);
  const topScore = scoreRows[0];
  const riskFlags = safeConsumerList(data.researchNotes.riskFlags ?? [], language)
    .map((flag) => mapConsumerStatusText(flag, language))
    .filter(Boolean);
  const needsMoreEvidence = safeConsumerList(data.researchNotes.needsMoreEvidence ?? [], language);

  facts.push({
    key: 'symbol',
    label: language === 'en' ? 'Symbol' : '标的',
    value: safeConsumerText(data.ticker, language, language === 'en' ? 'Current symbol' : '当前标的'),
  });

  if (usableBars !== null && usableBars > 0) {
    facts.push({
      key: 'update-status',
      label: language === 'en' ? 'Update status' : '更新状态',
      value: [status, period, barsCountLabel(usableBars, language)].filter(Boolean).join(' · '),
    });
  }

  if (structureState && !isUnavailableStructureState(data.structureState)) {
    facts.push({
      key: 'structure-state',
      label: language === 'en' ? 'Technical state' : '技术状态',
      value: structureState,
    });
  }

  if (topScore) {
    facts.push({
      key: 'top-signal',
      label: language === 'en' ? 'Strongest component' : '主要结构线索',
      value: `${topScore.label}: ${topScore.value}`,
    });
  }

  if (riskFlags.length) {
    facts.push({
      key: 'risk',
      label: language === 'en' ? 'Risk / uncertainty' : '风险 / 不确定性',
      value: riskFlags.join(language === 'en' ? '; ' : '；'),
    });
  } else if (needsMoreEvidence.length) {
    facts.push({
      key: 'uncertainty',
      label: language === 'en' ? 'Risk / uncertainty' : '风险 / 不确定性',
      value: needsMoreEvidence.slice(0, 2).join(language === 'en' ? '; ' : '；'),
    });
  }

  return facts;
}

function hasMinimumResearchPacket(
  data: StockStructureDecisionResponse,
  scoreRows: Array<{ key: string; label: string; value: number }>,
  language: 'zh' | 'en',
): boolean {
  const usableBars = numericValue(data.dataQuality.usableBars);
  const hasUsablePriceHistory = usableBars !== null && usableBars > 0;
  const hasStructureState = Boolean(safeOptionalConsumerText(data.structureState, language))
    && !isUnavailableStructureState(data.structureState);
  const hasExplanation = Boolean(safeOptionalConsumerText(data.explanation.whyThisStructure, language))
    || safeConsumerList(data.explanation.whatConfirmsIt ?? [], language).length > 0
    || safeConsumerList(data.explanation.whatInvalidatesIt ?? [], language).length > 0;
  const hasResearchNotes = safeConsumerList(data.researchNotes.watchNext ?? [], language).length > 0
    || safeConsumerList(data.researchNotes.riskFlags ?? [], language).length > 0;
  const hasKeyLevels = (data.explanation.keyLevels ?? []).some((level) => (
    level.value != null || Boolean(safeOptionalConsumerText(level.description, language))
  ));

  return hasUsablePriceHistory
    || hasStructureState
    || scoreRows.length > 0
    || hasExplanation
    || hasResearchNotes
    || hasKeyLevels
    || hasPeerCorrelationContent(data.peerCorrelationSnapshot);
}

function buildMissingDataSummary(
  data: StockStructureDecisionResponse,
  language: 'zh' | 'en',
): string | null {
  const gaps = data.missingEvidence ?? [];
  const missingCopies = compactUnique(gaps.map((gap) => missingEvidenceCopy(data.ticker, gap, language)));
  if (missingCopies.length) {
    return missingCopies.slice(0, 2).join(language === 'en' ? ' ' : '');
  }
  if (data.confidenceState?.reasons?.length) {
    const reasons = safeConsumerList(data.confidenceState.reasons, language);
    if (reasons.length) return reasons.slice(0, 2).join(language === 'en' ? ' ' : '');
  }
  return null;
}

function StockStructureCannotResearchState({
  data,
  language,
  localize,
}: {
  data: StockStructureDecisionResponse;
  language: 'zh' | 'en';
  localize: (path: string) => string;
}) {
  const isEnglish = language === 'en';
  const summary = buildMissingDataSummary(data, language);

  return (
    <div className="p-4 md:p-5">
      <TerminalEmptyState
        className="items-start md:items-center"
        data-testid="stock-structure-unavailable-state"
        title={isEnglish ? `${data.ticker} cannot be researched yet` : `${data.ticker} 暂不能形成研究包`}
        action={(
          <div className="flex shrink-0 flex-wrap justify-end gap-2">
            <Link
              to={localize('/research/radar')}
              className="inline-flex min-h-9 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
            >
              {isEnglish ? 'Back to Research Radar' : '返回研究雷达'}
            </Link>
            <Link
              to={localize('/watchlist')}
              className="inline-flex min-h-9 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
            >
              {isEnglish ? 'Back to watchlist' : '返回观察列表'}
            </Link>
          </div>
        )}
      >
        <div className="space-y-1">
          <p>
            {isEnglish
              ? 'Limited facts for a research packet.'
              : '个股事实不足，暂不能组成研究包。'}
          </p>
          <p>
            {summary || (isEnglish
              ? 'Return after price or comparable evidence is ready.'
              : '价格或可比证据可用后，从研究队列重新进入。')}
          </p>
          <p>
            {isEnglish
              ? 'Research observation only.'
              : '仅研究观察。'}
          </p>
        </div>
      </TerminalEmptyState>
    </div>
  );
}

function StockMinimumResearchPacket({
  data,
  facts,
  language,
  missingSummary,
}: {
  data: StockStructureDecisionResponse;
  facts: StockResearchFact[];
  language: 'zh' | 'en';
  missingSummary: string | null;
}) {
  const isEnglish = language === 'en';
  const watchNext = safeConsumerList(data.researchNotes.watchNext ?? [], language);

  return (
    <div className="grid gap-3 border-t border-[color:var(--wolfy-divider)] p-3" data-testid="stock-minimum-research-packet">
      <RoughSectionCard
        eyebrow={isEnglish ? 'Minimum research packet' : '最低研究包'}
        title={isEnglish ? 'Known stock facts' : '已知个股事实'}
      >
        <RoughKeyValueRows
          rows={facts.map((fact) => ({
            key: fact.key,
            label: fact.label,
            value: fact.value,
            detail: fact.detail,
          }))}
        />
      </RoughSectionCard>
      {watchNext.length ? (
        <RoughSectionCard
          eyebrow={isEnglish ? 'Next check' : '下一步研究'}
          title={isEnglish ? 'What to verify next' : '下一步核对'}
        >
          <RoughBulletList
            items={watchNext.slice(0, 3)}
            emptyText={isEnglish ? 'No next check listed.' : '暂无下一步核对项。'}
          />
        </RoughSectionCard>
      ) : null}
      {missingSummary ? (
        <RoughSectionCard
          eyebrow={isEnglish ? 'Data boundary' : '数据边界'}
          title={isEnglish ? 'Missing data summarized once' : '缺失资料汇总'}
        >
          <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{missingSummary}</p>
        </RoughSectionCard>
      ) : null}
    </div>
  );
}

function StockResearchPacketPanel({
  packet,
  failed,
  language,
}: {
  packet: SymbolResearchPacket | null;
  failed: boolean;
  language: 'zh' | 'en';
}) {
  const isEnglish = language === 'en';
  if (failed) {
    return (
      <div className="border-t border-[color:var(--wolfy-divider)] p-3" data-testid="stock-research-packet-panel">
        <RoughSectionCard eyebrow={isEnglish ? 'Research packet' : '研究包'} title={isEnglish ? 'Research packet pending' : '研究包待更新'}>
          <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
            {isEnglish ? 'Refresh the packet after the stock data endpoint updates.' : '待个股数据接口更新后再复核。'}
          </p>
        </RoughSectionCard>
      </div>
    );
  }

  if (!packet) return null;

  const stackRows = buildEvidenceStackRows(packet, language);
  const counts = evidenceStackCounts(stackRows);
  const countLabels = evidenceCountLabels(counts, language);
  const authorityLabels = evidenceAuthorityLabels(packet, language);
  const gapLabels = buildEvidenceGapLabels(packet, language);
  const identityLabel = [
    safeOptionalConsumerText(packet.identity.name, language),
    safeOptionalConsumerText(packet.market, language),
  ].filter(Boolean).join(' · ') || packet.symbol;

  return (
    <div className="grid gap-3 border-t border-[color:var(--wolfy-divider)] p-3" data-testid="stock-research-packet-panel">
      <RoughSectionCard
        eyebrow={isEnglish ? 'Evidence stack' : '证据栈'}
        title={evidenceCompletenessLabel(counts, language)}
      >
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <TerminalChip variant="info">{packet.symbol}</TerminalChip>
          <TerminalChip variant="neutral">{identityLabel}</TerminalChip>
          {authorityLabels.map((label) => (
            <TerminalChip key={label} variant="neutral">{label}</TerminalChip>
          ))}
          {countLabels.map((label) => (
            <TerminalChip key={label} variant="info">{label}</TerminalChip>
          ))}
        </div>
        <RoughKeyValueRows
          rows={stackRows.map((row) => ({
            key: row.key,
            label: row.label,
            value: row.value,
          }))}
        />
      </RoughSectionCard>
      {gapLabels.length ? (
        <RoughSectionCard eyebrow={isEnglish ? 'Next evidence gaps' : '下一证据缺口'} title={isEnglish ? 'What remains missing' : '仍需补齐'}>
          <div className="flex flex-wrap gap-2">
            {gapLabels.map((label) => (
              <TerminalChip key={label} variant="caution">{label}</TerminalChip>
            ))}
          </div>
        </RoughSectionCard>
      ) : null}
    </div>
  );
}

function StockStructureSymbolNotFoundState({
  language,
  symbol,
  localize,
}: {
  language: 'zh' | 'en';
  symbol: string;
  localize: (path: string) => string;
}) {
  const isEnglish = language === 'en';
  const actions = [
    {
      to: localize('/research/radar'),
      label: isEnglish ? 'Back to Research Radar' : '返回研究雷达',
    },
    {
      to: localize('/watchlist'),
      label: isEnglish ? 'Back to watchlist' : '返回观察列表',
    },
    {
      to: localize('/'),
      label: isEnglish ? 'Back home' : '返回首页',
    },
  ];

  return (
    <div className="p-4 md:p-5">
      <TerminalEmptyState
        className="items-start md:items-center"
        data-testid="stock-structure-symbol-not-found-state"
        title={isEnglish ? 'Symbol not found' : '标的未找到'}
        action={(
          <div className="flex shrink-0 flex-wrap justify-end gap-2">
            {actions.map((action) => (
              <Link
                key={action.to}
                to={action.to}
                className="inline-flex min-h-9 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
              >
                {action.label}
              </Link>
            ))}
          </div>
        )}
      >
        <div className="space-y-1">
          <p>
            {isEnglish
              ? `${symbol || 'The symbol'} was not found. Check the code, or return to search and choose again.`
              : '未找到该标的，请检查代码是否正确，或返回搜索重新选择。'}
          </p>
          <p>
            {isEnglish
              ? `${symbol || 'The symbol'} cannot be confirmed; this differs from temporarily missing data.`
              : '当前无法确认该标的，不等同于数据暂时不可用。'}
          </p>
          <p>
            {isEnglish
              ? 'Research observation only.'
              : '仅研究观察。'}
          </p>
        </div>
      </TerminalEmptyState>
    </div>
  );
}

function CompareWithPeerLink({
  language,
  to,
  peerSymbol,
}: {
  language: 'zh' | 'en';
  to: string;
  peerSymbol: string;
}) {
  return (
    <Link
      to={to}
      className="inline-flex w-fit max-w-full items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
    >
      {language === 'en' ? `Compare evidence with ${peerSymbol}` : `与 ${peerSymbol} 对比证据`}
    </Link>
  );
}

function SymbolCompareEvidencePacketPanel({
  packet,
  language,
  requestedSymbols,
}: {
  packet: StockSymbolCompareEvidencePacket | null;
  language: 'zh' | 'en';
  requestedSymbols: string[];
}) {
  const comparedSymbols = (packet?.comparedSymbols ?? [])
    .map((symbol) => symbol.trim().toUpperCase())
    .filter(Boolean);
  const displaySymbols = [...new Set([
    ...requestedSymbols,
    ...comparedSymbols,
    ...Object.keys(packet?.missingEvidenceBySymbol ?? {}),
    ...Object.keys(packet?.freshnessBySymbol ?? {}),
  ].map((symbol) => symbol.trim().toUpperCase()).filter(Boolean))];

  if (!packet || displaySymbols.length <= 1) {
    const symbolLabel = displaySymbols[0] ?? (language === 'en' ? 'one symbol' : '一个标的');
    const isSingleSymbol = displaySymbols.length <= 1;
    return (
      <div className="grid gap-3 border-t border-[color:var(--wolfy-divider)] p-3" data-testid="symbol-compare-evidence-packet">
        <TerminalEmptyState
          title={isSingleSymbol
            ? (language === 'en' ? 'At least two comparable symbols are required' : '需要至少两个可比较标的')
            : (language === 'en' ? 'Compare evidence is not ready yet' : '对比证据暂未就绪')}
        >
          <div className="space-y-1">
            <p>
              {isSingleSymbol
                ? (language === 'en'
                  ? `Only ${symbolLabel} is present, so shared evidence or divergence evidence cannot be formed yet.`
                  : `当前只有 ${symbolLabel}，暂时不能形成标的间共享证据或分歧证据。`)
                : (language === 'en'
                  ? 'Shared evidence or divergence evidence is still missing for this symbol set.'
                  : '这组标的的共享证据或分歧证据仍缺失。')}
            </p>
            <p>
              {isSingleSymbol
                ? (language === 'en'
                  ? 'Add a comparable peer symbol before reviewing compare evidence.'
                  : '添加同业标的后再查看对比证据。')
                : (language === 'en'
                  ? 'Check stock evidence gaps first, then review the comparison again.'
                  : '先检查个股证据缺口，补齐可比较标的后再复核。')}
            </p>
          </div>
        </TerminalEmptyState>
      </div>
    );
  }

  const confidenceCapValue = packet.confidenceCap?.value;
  const boundary = packet.observationBoundary ?? {};
  const boundaryChips = [
    boundary.observationOnly ? (language === 'en' ? 'Research observation only' : '仅研究观察') : null,
    boundary.decisionGrade === false ? (language === 'en' ? 'Not decision grade' : '非判断等级') : null,
    boundary.rankingAllowed === false ? (language === 'en' ? 'No ordering output' : '不排序') : null,
    boundary.adviceAllowed === false ? (language === 'en' ? 'No action instruction' : '不生成行动指令') : null,
  ].filter(Boolean) as string[];
  const missingSymbols = displaySymbols.filter((symbol) => (packet.missingEvidenceBySymbol[symbol] ?? []).length > 0);

  return (
    <div className="grid gap-3 border-t border-[color:var(--wolfy-divider)] p-3 md:grid-cols-2" data-testid="symbol-compare-evidence-packet">
      <RoughSectionCard
        className="md:col-span-2"
        eyebrow={language === 'en' ? 'Evidence packet' : '证据包'}
        title={language === 'en' ? 'Compare evidence packet' : '对比证据包'}
      >
        <div className="flex flex-wrap items-center gap-2">
          {displaySymbols.map((symbol) => (
            <TerminalChip key={symbol} variant="info">{symbol}</TerminalChip>
          ))}
          <TerminalChip variant="caution">
            {language === 'en'
              ? `Confidence cap ${confidenceCapLabel(confidenceCapValue, language)}`
              : `置信上限 ${confidenceCapLabel(confidenceCapValue, language)}`}
          </TerminalChip>
          {boundaryChips.map((label) => (
            <TerminalChip key={label} variant="neutral">{label}</TerminalChip>
          ))}
        </div>
        {confidenceCapValue != null ? (
          <EvidenceGapExplanationList
            className="mt-3"
            gaps={['confidence_capped']}
            locale={language}
            title={language === 'en' ? 'Confidence impact' : '置信度影响'}
          />
        ) : null}
      </RoughSectionCard>

      <RoughSectionCard title={language === 'en' ? 'Shared evidence' : '共享证据'}>
        <RoughBulletList
          items={packet.sharedEvidence.map((item, index) => (
            <span key={index}>
              <span className="font-medium text-[color:var(--wolfy-text-primary)]">{evidenceKindLabel(item.kind, language)}</span>
              <span className="ml-2 text-[color:var(--wolfy-text-muted)]">{sharedEvidenceMeta(item, language)}</span>
            </span>
          ))}
          emptyText={language === 'en' ? 'No shared evidence is ready across these symbols yet.' : '这些标的之间暂无共同证据。'}
        />
      </RoughSectionCard>

      <RoughSectionCard title={language === 'en' ? 'Divergent evidence' : '分歧证据'}>
        <RoughBulletList
          items={packet.divergentEvidence.map((item, index) => {
            const values = item.values ?? {};
            const valueText = Object.entries(values)
              .map(([symbol, value]) => `${symbol}: ${safeEvidenceValue(value, language)}`)
              .join(' · ');
            return (
              <span key={index}>
                <span className="font-medium text-[color:var(--wolfy-text-primary)]">{evidenceKindLabel(item.kind, language)}</span>
                {valueText ? <span className="ml-2 text-[color:var(--wolfy-text-muted)]">{valueText}</span> : null}
              </span>
            );
          })}
          emptyText={language === 'en' ? 'No divergence is ready in this packet.' : '当前证据包暂无分歧观察。'}
        />
      </RoughSectionCard>

      <RoughSectionCard title={language === 'en' ? 'Missing evidence' : '缺失证据'}>
        {missingSymbols.length ? (
          <div className="grid gap-3">
            {missingSymbols.map((symbol) => {
            const gaps = packet.missingEvidenceBySymbol[symbol] ?? [];
            return (
              <div key={`missing-${symbol}`} className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 px-3 py-2.5">
                <div className="mb-2 font-mono text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{symbol}</div>
                <p className="mb-2 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                  {gaps.map((gap) => missingEvidenceCopy(symbol, gap, language)).join(language === 'en' ? ' ' : '')}
                </p>
                <EvidenceGapExplanationList
                  gaps={gaps}
                  locale={language}
                  title={language === 'en' ? 'Gap explanation' : '缺口解释'}
                />
              </div>
            );
            })}
          </div>
        ) : (
          <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
            {language === 'en' ? 'No missing compare item is listed for this symbol set.' : '这组标的暂无需要逐项展开的缺失资料。'}
          </p>
        )}
      </RoughSectionCard>

      <RoughSectionCard title={language === 'en' ? 'Freshness by symbol' : '新鲜度'}>
        <RoughKeyValueRows
          emptyText={language === 'en' ? 'No freshness summary yet.' : '暂无新鲜度摘要。'}
          rows={displaySymbols.map((symbol) => ({
            key: `freshness-${symbol}`,
            label: symbol,
            value: freshnessMeta(packet.freshnessBySymbol[symbol], language),
          }))}
        />
      </RoughSectionCard>

      <RoughSectionCard className="md:col-span-2" title={language === 'en' ? 'Next research steps' : '后续研究'}>
        <RoughBulletList
          items={safeResearchNextSteps(packet.researchNextSteps, language)}
          emptyText={language === 'en' ? 'No additional research step is listed.' : '暂无额外后续研究项。'}
        />
      </RoughSectionCard>
    </div>
  );
}

export default function StockStructureDecisionPage() {
  const { language } = useI18n();
  const locale = language === 'en' ? 'en' : 'zh';
  const { stockCode = '' } = useParams();
  const location = useLocation();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const localize = useCallback((path: string) => (routeLocale ? buildLocalizedPath(path, routeLocale) : path), [routeLocale]);
  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const symbolSegment = stockCode || symbolSegmentFromPathname(location.pathname);
  const requestedSymbols = useMemo(
    () => parseStockStructureSymbols(searchParams.get('symbols') || symbolSegment),
    [searchParams, symbolSegment],
  );
  const benchmark = searchParams.get('benchmark')?.trim().toUpperCase() || undefined;
  const maxItems = parsePositiveInteger(searchParams.get('maxItems'));
  const isCompareRequest = requestedSymbols.length > 1;
  const primarySymbol = requestedSymbols[0] || symbolSegment.toUpperCase();
  const titleSymbol = isCompareRequest ? requestedSymbols.join(' / ') : primarySymbol;
  const [data, setData] = useState<StockStructureDecisionResponse | null>(null);
  const [researchPacket, setResearchPacket] = useState<SymbolResearchPacket | null>(null);
  const [researchPacketFailed, setResearchPacketFailed] = useState(false);
  const [comparePacket, setComparePacket] = useState<StockSymbolCompareEvidencePacket | null>(null);
  const [symbolNotFound, setSymbolNotFound] = useState<SymbolNotFoundState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSymbolNotFound(null);
    setResearchPacket(null);
    setResearchPacketFailed(false);
    try {
      if (isCompareRequest) {
        const [packetResult, responseResult] = await Promise.allSettled([
          stocksApi.getResearchPacket(primarySymbol),
          stocksApi.getStructureDecisionsBatch({
            stockCodes: requestedSymbols,
            benchmark,
            maxItems,
          }),
        ]);
        if (packetResult.status === 'fulfilled') {
          setResearchPacket(packetResult.value);
        } else {
          setResearchPacketFailed(true);
        }
        if (responseResult.status === 'rejected') {
          throw responseResult.reason;
        }
        const response = responseResult.value;
        setData(response.items[0] ?? null);
        setComparePacket(response.symbolCompareEvidencePacket ?? null);
      } else {
        let validation: StockValidationResponse | null = null;
        try {
          validation = await stocksApi.verifyTickerExists(primarySymbol);
        } catch {
          validation = null;
        }
        if (isSymbolNotFoundValidation(validation)) {
          setData(null);
          setResearchPacket(null);
          setResearchPacketFailed(false);
          setComparePacket(null);
          setSymbolNotFound({
            symbol: validation.normalizedSymbol || validation.stockCode || primarySymbol,
          });
          return;
        }
        const [packetResult, responseResult] = await Promise.allSettled([
          stocksApi.getResearchPacket(primarySymbol),
          stocksApi.getStructureDecision(primarySymbol),
        ]);
        if (packetResult.status === 'fulfilled') {
          setResearchPacket(packetResult.value);
        } else {
          setResearchPacketFailed(true);
        }
        if (responseResult.status === 'rejected') {
          throw responseResult.reason;
        }
        const response = responseResult.value;
        setData(response);
        setComparePacket(null);
      }
    } catch (err) {
      setComparePacket(null);
      setSymbolNotFound(null);
      setError(getParsedApiError(err) || createParsedApiError({
        title: locale === 'en' ? 'Structure panel pending' : '结构面板暂不可用',
        message: locale === 'en' ? 'Please retry after the stock structure API responds again.' : '请在个股结构接口恢复后重试。',
      }));
    } finally {
      setLoading(false);
    }
  }, [benchmark, isCompareRequest, locale, maxItems, primarySymbol, requestedSymbols]);

  useEffect(() => {
    void load();
  }, [load]);

  const scoreRows = useMemo(
    () => Object.entries(data?.componentScores ?? {})
      .sort(([, left], [, right]) => (right ?? 0) - (left ?? 0))
      .map(([key, value]) => ({
        key,
        label: localLabel(key, locale),
        value,
      })),
    [data?.componentScores, locale],
  );
  const comparablePeerSymbol = useMemo(
    () => firstComparablePeerSymbol(data?.peerCorrelationSnapshot, data?.ticker || primarySymbol),
    [data?.peerCorrelationSnapshot, data?.ticker, primarySymbol],
  );
  const hasResearchPacket = data ? hasMinimumResearchPacket(data, scoreRows, locale) : false;
  const packetFacts = data ? buildPacketFacts(data, scoreRows, locale) : [];
  const missingDataSummary = data ? buildMissingDataSummary(data, locale) : null;
  const safeDisclosure = data
    ? safeConsumerText(
      data.noAdviceDisclosure,
      locale,
      locale === 'en' ? 'Research context only. No action instruction is generated.' : '仅供研究语境参考，不生成操作指令。',
    )
    : null;
  const safeWatchNext = data ? safeConsumerList(data.researchNotes.watchNext ?? [], locale) : [];
  const explainRows = data ? [
    {
      key: 'why',
      label: locale === 'en' ? 'Why this structure' : '形成原因',
      value: safeOptionalConsumerText(data.explanation.whyThisStructure, locale),
    },
    {
      key: 'confirm',
      label: locale === 'en' ? 'What confirms it' : '确认观察',
      value: safeConsumerList(data.explanation.whatConfirmsIt ?? [], locale).join(locale === 'en' ? '; ' : '；'),
    },
    {
      key: 'invalidate',
      label: locale === 'en' ? 'What changes it' : '变化条件',
      value: safeConsumerList(data.explanation.whatInvalidatesIt ?? [], locale).join(locale === 'en' ? '; ' : '；'),
    },
  ].filter((row) => row.value) : [];
  const researchRows = data ? [
    {
      key: 'more',
      label: locale === 'en' ? 'Needs more evidence' : '待补资料',
      value: safeConsumerList(data.researchNotes.needsMoreEvidence ?? [], locale).join(locale === 'en' ? '; ' : '；'),
    },
    {
      key: 'risk',
      label: locale === 'en' ? 'Risk flags' : '风险标记',
      value: safeConsumerList(data.researchNotes.riskFlags ?? [], locale)
        .map((flag) => mapConsumerStatusText(flag, locale))
        .join(locale === 'en' ? '; ' : '；'),
    },
  ].filter((row) => row.value) : [];
  const keyLevelRows = data ? (data.explanation.keyLevels ?? [])
    .map((level, index) => ({
      key: `${level.kind || 'level'}-${index}`,
      label: safeOptionalConsumerText(level.kind, locale) || (locale === 'en' ? 'Level' : '位置'),
      value: level.value ?? safeOptionalConsumerText(level.description, locale),
      detail: level.value != null ? safeOptionalConsumerText(level.description, locale) || undefined : undefined,
    }))
    .filter((row) => row.value != null && row.value !== '') : [];
  const compareWithPeerPath = data && comparablePeerSymbol && !isCompareRequest
    ? localize(buildComparePath([data.ticker || primarySymbol, comparablePeerSymbol]))
    : null;
  const introTitle = symbolNotFound
    ? (locale === 'en' ? 'Symbol not found' : '标的未找到')
    : (locale === 'en' ? `${titleSymbol} structure workspace` : `${titleSymbol} 结构工作区`);
  const introDescription = symbolNotFound
    ? (locale === 'en'
      ? 'Check the code or return to a research entrypoint.'
      : '请检查代码是否正确，或返回研究入口重新选择。')
    : (locale === 'en'
      ? 'Assembles known stock fact summaries.'
      : '汇总可用个股事实。');
  const railContent = data && hasResearchPacket ? (
    <ConsoleContextRail className="flex flex-col gap-3 p-3">
      {safeWatchNext.length ? (
        <RoughSectionCard eyebrow={locale === 'en' ? 'Research notes' : '研究备注'} title={locale === 'en' ? 'Watch next' : '下一步观察'}>
          <RoughBulletList
            items={safeWatchNext.slice(0, 3)}
            emptyText={locale === 'en' ? 'No next watch item yet.' : '暂未整理下一步观察项。'}
          />
        </RoughSectionCard>
      ) : null}
      {missingDataSummary ? (
        <RoughSectionCard eyebrow={locale === 'en' ? 'Boundary' : '边界'} title={locale === 'en' ? 'Data still missing' : '仍缺资料'}>
          <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{missingDataSummary}</p>
        </RoughSectionCard>
      ) : null}
      {safeDisclosure ? (
        <RoughSectionCard eyebrow={locale === 'en' ? 'Disclosure' : '披露'} title={locale === 'en' ? 'Research boundary' : '研究边界'}>
          <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{safeDisclosure}</p>
        </RoughSectionCard>
      ) : null}
    </ConsoleContextRail>
  ) : null;

  return (
    <ConsumerWorkspaceScope className="flex min-h-0 flex-1">
      <ConsumerWorkspacePageShell className="flex min-h-0 flex-1 flex-col gap-4 md:gap-6">
        <ResearchConsoleShell
          className="flex-1"
          command={(
            <WolfyCommandBar
              leading={<span className="text-xs text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Single-name Research / Structure' : '个股研究 / 结构'}</span>}
              trailing={(
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    to={localize('/market/decision-cockpit')}
                    className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                  >
                    {locale === 'en' ? 'Market cockpit' : '市场驾驶舱'}
                  </Link>
                  <TerminalButton variant="compact" onClick={() => void load()}>
                    {locale === 'en' ? 'Refresh' : '刷新'}
                  </TerminalButton>
                </div>
              )}
            >
              <div className="text-xs text-[color:var(--wolfy-text-secondary)]">
                {locale === 'en' ? 'Research workspace for structure state, key levels, useful notes, and one compact data boundary.' : '结构研究工作区，集中呈现状态、关键位置、有效备注与一处数据边界。'}
              </div>
            </WolfyCommandBar>
          )}
          rail={railContent}
        >
          <ConsoleBoard className="min-h-0" data-testid="stock-structure-decision-page">
            <RoughSurfaceIntro
              eyebrow={locale === 'en' ? 'Stock structure panel' : '个股结构面板'}
              title={introTitle}
              description={introDescription}
            />
            {error ? (
              <div className="p-4 md:p-5">
                <ApiErrorAlert error={error} actionLabel={locale === 'en' ? 'Retry' : '重试'} onAction={() => void load()} />
              </div>
            ) : null}
            {loading && !data ? (
              <div className="p-4 md:p-5">
                <TerminalEmptyState title={locale === 'en' ? 'Loading structure panel' : '正在整理结构面板'}>
                  {locale === 'en' ? 'Loading structure panel.' : '正在载入结构面板。'}
                </TerminalEmptyState>
              </div>
            ) : null}
            {!loading && !error && symbolNotFound ? (
              <StockStructureSymbolNotFoundState
                language={locale}
                symbol={symbolNotFound.symbol}
                localize={localize}
              />
            ) : null}
            {data ? (
              <>
                <StockResearchPacketPanel
                  packet={researchPacket}
                  failed={researchPacketFailed}
                  language={locale}
                />
                {hasResearchPacket ? (
                  <>
                    <ConsoleStatusStrip
                      items={[
                        {
                          label: locale === 'en' ? 'Ticker' : '标的',
                          value: data.ticker,
                        },
                        {
                          label: locale === 'en' ? 'Data status' : '数据状态',
                          value: <StatusBadge status={toneFor(data.dataQuality.status)} label={statusLabel(data.dataQuality.status, locale)} size="sm" />,
                        },
                        {
                          label: locale === 'en' ? 'Period' : '周期',
                          value: periodLabel(data.dataQuality.period, locale) || (locale === 'en' ? 'not listed' : '未列明'),
                        },
                      ]}
                    />
                    <MetricStrip
                      items={[
                        {
                          key: 'state',
                          label: locale === 'en' ? 'Structure state' : '结构状态',
                          value: stockStructureStateLabel(data.structureState, locale) || (locale === 'en' ? 'Under review' : '待确认'),
                        },
                        {
                          key: 'confidence',
                          label: locale === 'en' ? 'Confidence' : '置信度',
                          value: confidenceLabel(data.confidence, locale),
                        },
                        {
                          key: 'bars',
                          label: locale === 'en' ? 'Usable bars' : '可用 K 线',
                          value: data.dataQuality.usableBars ?? (locale === 'en' ? 'not listed' : '未列明'),
                        },
                      ]}
                    />
                    <StockMinimumResearchPacket
                      data={data}
                      facts={packetFacts}
                      language={locale}
                      missingSummary={missingDataSummary}
                    />
                    {isCompareRequest || comparePacket ? (
                      <SymbolCompareEvidencePacketPanel
                        packet={comparePacket}
                        language={locale}
                        requestedSymbols={requestedSymbols}
                      />
                    ) : null}
                    <div className="grid gap-3 p-3 md:grid-cols-2">
                      {scoreRows.length ? (
                        <RoughSectionCard eyebrow={locale === 'en' ? 'Scores' : '评分'} title={locale === 'en' ? 'Component scores' : '组件评分'}>
                          <RoughScoreRows
                            items={scoreRows}
                            emptyText={locale === 'en' ? 'No component score yet.' : '暂无组件评分。'}
                          />
                        </RoughSectionCard>
                      ) : null}
                      {explainRows.length ? (
                        <RoughSectionCard eyebrow={locale === 'en' ? 'Structure logic' : '结构逻辑'} title={locale === 'en' ? 'Why this structure' : '结构解释'}>
                          <RoughKeyValueRows rows={explainRows} />
                        </RoughSectionCard>
                      ) : null}
                      {researchRows.length ? (
                        <RoughSectionCard eyebrow={locale === 'en' ? 'Research notes' : '研究备注'} title={locale === 'en' ? 'What remains uncertain' : '仍需确认'}>
                          <RoughKeyValueRows rows={researchRows} />
                        </RoughSectionCard>
                      ) : null}
                      {hasPeerCorrelationContent(data.peerCorrelationSnapshot) ? (
                        <>
                          <PeerCorrelationSnapshotBlock
                            snapshot={data.peerCorrelationSnapshot}
                            locale={locale}
                            testId="stock-structure-peer-correlation-snapshot"
                            className="md:col-span-2"
                          />
                          {compareWithPeerPath && comparablePeerSymbol ? (
                            <div className="md:col-span-2">
                              <CompareWithPeerLink
                                language={locale}
                                to={compareWithPeerPath}
                                peerSymbol={comparablePeerSymbol}
                              />
                            </div>
                          ) : null}
                        </>
                      ) : null}
                      {keyLevelRows.length ? (
                        <RoughSectionCard eyebrow={locale === 'en' ? 'Reference levels' : '参考位置'} title={locale === 'en' ? 'Key levels' : '关键位置'}>
                          <RoughKeyValueRows rows={keyLevelRows} />
                        </RoughSectionCard>
                      ) : null}
                    </div>
                  </>
                ) : (
                  <StockStructureCannotResearchState
                    data={data}
                    language={locale}
                    localize={localize}
                  />
                )}
              </>
            ) : null}
          </ConsoleBoard>
        </ResearchConsoleShell>
      </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
}
