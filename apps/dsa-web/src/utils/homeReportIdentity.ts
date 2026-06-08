import type { AnalysisReport } from '../types/analysis';

const EMPTY_FIELD_VALUE = '-';
const EMPTY_DISPLAY_VALUE = '--';
const CONSUMER_REPORT_OBSERVATION_FALLBACK = '当前研究包仍不完整，仅支持继续跟踪。';
const CONSUMER_REPORT_DATA_GAP_FALLBACK = '数据不足，仅支持情景参考。';

const CONSUMER_REPORT_INTERNAL_PATTERN =
  /reasonCode|reasonCodes|reason_code|reason_codes|reasonFamilies|sourceRefId|sourceRefIds|source_ref_id|source_ref_ids|raw_result|rawResult|raw_ai_response|rawAiResponse|context_snapshot|contextSnapshot|rawPayload|raw_payload|rawRows|provider|backend|debug|diagnostic|diagnostics|trace|schema|cache|payload|prompt|model|fallback_cache|provider_timeout|synthetic_fixture|snake_case|\b[a-z]+(?:_[a-z0-9]+)+\b/i;

const CONSUMER_REPORT_ACTION_PATTERN =
  /投资结论|理想买点|理想买入|理想买入点|次级买点|二次买入|次优买入|次优买点|回踩买点|突破买点|分批试仓|试仓|目标价|目标位|目标区间|目标一区|目标二区|止损|止损位|止损线|止盈|止盈目标|仓位建议|持仓建议|空仓建议|建议\s*(买入|卖出|加仓|减仓|持有)|买入|卖出|加仓|减仓|建仓|开仓|平仓|减持|\bAction\b|Ideal buy|Ideal entry|Pullback entry|Secondary buy|Secondary entry|Stop loss|Take profit|\bTarget\b|Target 1|Target 2|Target zone|Position sizing|Entry strategy|Risk control strategy|holding advice|empty-position advice|empty-position|holding-position|\bbuy\b|\bsell\b|\badd(?:ing)?\b|\breduce\b|\bentry\b|\bexit\b|\baccumulate\b|\bscale(?:\s|-)?in\b|\bbuild(?:ing)? position\b|\bstop(?: loss)?\b|\btake profit\b|\btarget(?: price| zone)?\b|\bposition sizing\b/i;

const CONSUMER_REPORT_PRICE_TOKEN_PATTERN =
  /(?:[$¥€￥]\s*)?\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:-|–|—|~|至|到)\s*(?:[$¥€￥]\s*)?\d+(?:,\d{3})*(?:\.\d+)?)?/g;

function normalizeTickerQuery(value?: string): string {
  return String(value || '').trim().toUpperCase();
}

export function readObjectField(payload: unknown, path: string[]): unknown {
  let current = payload;
  for (const key of path) {
    if (!current || typeof current !== 'object') {
      return undefined;
    }
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

function safeReportValue(value: unknown): string {
  const text = String(value ?? '').trim();
  return text && text !== '-' && !/^n\/?a$/i.test(text) ? text : EMPTY_DISPLAY_VALUE;
}

export function isConsumerInternalReportText(value: unknown): boolean {
  return CONSUMER_REPORT_INTERNAL_PATTERN.test(String(value ?? ''));
}

function extractConsumerPriceContext(value: string): string {
  const matches = value.match(CONSUMER_REPORT_PRICE_TOKEN_PATTERN) || [];
  return uniqueText(matches.map((item) => item.replace(/\s+/g, ' ').replace(/\s*[-–—~]\s*/g, ' - ').trim())).join(' / ');
}

export function consumerSafeReportText(
  value: unknown,
  fallback = CONSUMER_REPORT_OBSERVATION_FALLBACK,
): string {
  const text = safeReportValue(value);
  if (text === EMPTY_DISPLAY_VALUE) {
    return text;
  }
  if (isConsumerInternalReportText(text)) {
    return fallback;
  }
  if (CONSUMER_REPORT_ACTION_PATTERN.test(text)) {
    return fallback;
  }
  return text;
}

export function consumerSafeReportPriceContext(
  value: unknown,
  fallback = CONSUMER_REPORT_DATA_GAP_FALLBACK,
): string {
  const text = safeReportValue(value);
  if (text === EMPTY_DISPLAY_VALUE) {
    return text;
  }
  if (isConsumerInternalReportText(text)) {
    return fallback;
  }
  if (!CONSUMER_REPORT_ACTION_PATTERN.test(text)) {
    return text;
  }
  const priceContext = extractConsumerPriceContext(text);
  return priceContext || fallback;
}

export function consumerSafeReportLabel(value: unknown, fallback = '情景参考'): string {
  const label = String(value ?? '').trim();
  if (!label || isConsumerInternalReportText(label)) {
    return '';
  }
  if (/投资结论|Investment Thesis|\bAction\b|动作|操作建议|结论/i.test(label)) {
    return '研究包完整度';
  }
  if (/resistance|压力|target|目标/i.test(label)) {
    return '上方观察区';
  }
  if (/secondary|backup|次级|次优|参考/i.test(label)) {
    return '参考区间';
  }
  if (/理想|次级|买点|buy|entry|support|resistance|target|目标|支撑|压力/i.test(label)) {
    return '关键价格区间';
  }
  if (/止损|止盈|stop|risk|风险|仓位|position|持仓|空仓/i.test(label)) {
    return '风险边界';
  }
  if (/strategy|plan|reminder|condition|建仓|加仓|入场|执行|条件/i.test(label)) {
    return '继续跟踪';
  }
  return CONSUMER_REPORT_ACTION_PATTERN.test(label) ? fallback : label;
}

export function consumerSafeReportStatus(value: unknown): string {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'used' || normalized === 'available' || normalized === 'ready') return '可用';
  if (normalized === 'fallback' || normalized === 'stale' || normalized === 'cached') return '已使用最近一次可用数据';
  if (normalized === 'partial' || normalized === 'degraded') return '部分数据暂不可用';
  if (normalized === 'missing' || normalized === 'error' || normalized === 'unavailable') return '数据不足';
  if (normalized === 'unknown' || !normalized) return '状态待确认';
  return consumerSafeReportText(value, '状态待确认') || '状态待确认';
}

function isPlaceholderName(value: string): boolean {
  const normalized = value.trim().replace(/[（）]/g, '').replace(/\s+/g, ' ');
  return !normalized
    || normalized === EMPTY_FIELD_VALUE
    || normalized === EMPTY_DISPLAY_VALUE
    || /^n\/?a$/i.test(normalized)
    || /^unknown(?: stock)?$/i.test(normalized)
    || /^unnamed stock$/i.test(normalized)
    || normalized === '待确认股票';
}

function dedupeTickerFromName(value: unknown, ticker: string): string {
  const text = String(value || '').trim();
  const normalizedTicker = normalizeTickerQuery(ticker);
  if (!text || !normalizedTicker) {
    return text;
  }

  const tickerPattern = normalizedTicker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  let withoutWrappedTicker = text
    .replace(new RegExp(`\\s*[（(]\\s*${tickerPattern}\\s*[）)]`, 'gi'), ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (withoutWrappedTicker.toUpperCase() === normalizedTicker) {
    return normalizedTicker;
  }
  withoutWrappedTicker = withoutWrappedTicker
    .replace(new RegExp(`^${tickerPattern}\\s+`, 'i'), '')
    .replace(new RegExp(`\\s+${tickerPattern}$`, 'i'), '')
    .replace(/\s+/g, ' ')
    .trim();
  return withoutWrappedTicker || normalizedTicker;
}

export function normalizeCompanyNameCandidate(value: unknown, ticker: string): string {
  const normalizedTicker = normalizeTickerQuery(ticker);
  const cleaned = dedupeTickerFromName(value, normalizedTicker);
  if (!cleaned || isPlaceholderName(cleaned) || cleaned.toUpperCase() === normalizedTicker) {
    return '';
  }
  return cleaned;
}

export function getSymbolDisplay(result: unknown): string {
  const direct = readObjectField(result, ['meta', 'stockCode'])
    ?? readObjectField(result, ['stockCode'])
    ?? readObjectField(result, ['symbol'])
    ?? readObjectField(result, ['ticker'])
    ?? readObjectField(result, ['decisionTrace', 'symbol'])
    ?? readObjectField(result, ['details', 'standardReport', 'summaryPanel', 'ticker'])
    ?? readObjectField(result, ['details', 'rawResult', 'stock_code'])
    ?? readObjectField(result, ['details', 'rawResult', 'symbol'])
    ?? readObjectField(result, ['details', 'rawResult', 'dashboard', 'summary', 'ticker']);
  return normalizeTickerQuery(String(direct || '')) || EMPTY_FIELD_VALUE;
}

function getCompanyName(result: unknown): string | null {
  const ticker = getSymbolDisplay(result);
  const candidates = [
    readObjectField(result, ['meta', 'companyName']),
    readObjectField(result, ['companyName']),
    readObjectField(result, ['company_name']),
    readObjectField(result, ['displayName']),
    readObjectField(result, ['display_name']),
    readObjectField(result, ['stockName']),
    readObjectField(result, ['stock_name']),
    readObjectField(result, ['name']),
    readObjectField(result, ['profile', 'name']),
    readObjectField(result, ['quote', 'name']),
    readObjectField(result, ['quote', 'companyName']),
    readObjectField(result, ['fundamentals', 'companyName']),
    readObjectField(result, ['fundamental', 'companyName']),
    readObjectField(result, ['fundamental', 'profile', 'name']),
    readObjectField(result, ['overview', 'Name']),
    readObjectField(result, ['overview', 'name']),
    readObjectField(result, ['analysis', 'companyName']),
    readObjectField(result, ['report', 'companyName']),
    readObjectField(result, ['metadata', 'companyName']),
    readObjectField(result, ['meta', 'stockName']),
    readObjectField(result, ['details', 'standardReport', 'summaryPanel', 'stock']),
    readObjectField(result, ['details', 'standardReport', 'summaryPanel', 'companyName']),
    readObjectField(result, ['details', 'rawResult', 'stock_name']),
    readObjectField(result, ['details', 'rawResult', 'company_name']),
    readObjectField(result, ['details', 'rawResult', 'dashboard', 'summary', 'stock']),
    readObjectField(result, ['details', 'rawResult', 'dashboard', 'summary', 'company_name']),
  ];
  const company = candidates
    .map((candidate) => normalizeCompanyNameCandidate(candidate, ticker))
    .find(Boolean);
  return company || null;
}

export function getCompanyDisplayName(result: unknown): string {
  const ticker = getSymbolDisplay(result);
  return getCompanyName(result) || ticker || EMPTY_FIELD_VALUE;
}

export function getCompanyWithTicker(result: unknown): string {
  const ticker = getSymbolDisplay(result);
  const company = getCompanyDisplayName(result);
  if (!ticker || ticker === EMPTY_FIELD_VALUE || !company || company.toUpperCase() === ticker) {
    return ticker || company || EMPTY_FIELD_VALUE;
  }
  return `${company} (${ticker})`;
}

function uniqueText(values: Array<unknown>): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  values.forEach((value) => {
    const text = String(value ?? '').trim();
    if (!text || text === EMPTY_FIELD_VALUE || text === EMPTY_DISPLAY_VALUE) {
      return;
    }
    const key = text.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      result.push(text);
    }
  });
  return result;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return undefined;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function firstRecordValue(payload: unknown, paths: string[][]): Record<string, unknown> | undefined {
  for (const path of paths) {
    const record = asRecord(readObjectField(payload, path));
    if (record) {
      return record;
    }
  }
  return undefined;
}

function readRecordField(record: Record<string, unknown> | undefined, keys: string[]): unknown {
  if (!record) {
    return undefined;
  }
  for (const key of keys) {
    if (record[key] !== undefined && record[key] !== null) {
      return record[key];
    }
  }
  return undefined;
}

function conciseText(value: unknown): string | null {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    const text = String(value).trim();
    return text && text !== EMPTY_FIELD_VALUE && text !== EMPTY_DISPLAY_VALUE ? text : null;
  }
  return null;
}

function conciseField(record: Record<string, unknown> | undefined, keys: string[]): string | null {
  return conciseText(readRecordField(record, keys));
}

function findStockEvidencePacket(report: AnalysisReport | null): Record<string, unknown> | undefined {
  const direct = firstRecordValue(report, [
    ['stockEvidencePacket'],
    ['stock_evidence_packet'],
    ['details', 'stockEvidencePacket'],
    ['details', 'stock_evidence_packet'],
    ['details', 'analysisResult', 'stockEvidencePacket'],
    ['details', 'analysisResult', 'stock_evidence_packet'],
    ['details', 'rawResult', 'stockEvidencePacket'],
    ['details', 'rawResult', 'stock_evidence_packet'],
    ['details', 'rawResult', 'report', 'stockEvidencePacket'],
    ['details', 'rawResult', 'report', 'stock_evidence_packet'],
  ]);
  if (direct) {
    return direct;
  }

  const rawItems = readObjectField(report, ['details', 'rawResult', 'items']);
  const itemPacket = asArray(rawItems)
    .map((item) => firstRecordValue(item, [['stockEvidencePacket'], ['stock_evidence_packet']]))
    .find(Boolean);
  return itemPacket;
}

function formatEvidenceGap(item: unknown): string | null {
  const record = asRecord(item);
  if (!record) {
    return consumerSafeReportText(item, '');
  }
  const detail = consumerSafeReportText(conciseField(record, ['detail', 'message', 'summary', 'status']), '');
  return detail || '数据不足，需继续跟踪。';
}

function formatClaimBoundary(item: unknown): string | null {
  const record = asRecord(item);
  if (!record) {
    return consumerSafeReportText(item, '');
  }
  const allowed = readRecordField(record, ['allowed']);
  const detail = consumerSafeReportText(conciseField(record, ['detail', 'message', 'summary']), '');
  if (detail) {
    return detail;
  }
  if (allowed === false) {
    return '风险边界已收敛为观察说明。';
  }
  return '情景参考边界已标注。';
}

function formatSourceRef(item: unknown): string | null {
  const record = asRecord(item);
  if (!record) {
    return consumerSafeReportText(item, '');
  }
  const status = consumerSafeReportStatus(readRecordField(record, ['status']));
  const freshness = consumerSafeReportStatus(readRecordField(record, ['freshness', 'freshnessClass', 'freshness_class']));
  return uniqueText([status, freshness]).join(' / ') || null;
}

function evidenceClasses(items: unknown[]): string[] {
  return uniqueText(items.map((item) => {
    const record = asRecord(item);
    return record
      ? conciseField(record, ['evidenceClass', 'evidence_class', 'class', 'key'])
      : conciseText(item);
  }));
}

function buildEvidenceBoundaryLines(report: AnalysisReport | null): string[] {
  const packet = findStockEvidencePacket(report);
  const dataQualityReport = report?.dataQualityReport || report?.details?.dataQualityReport || report?.meta.dataQualityReport;
  const confidenceCap = readRecordField(packet, ['confidenceCap', 'confidence_cap']);
  const confidenceCapRecord = asRecord(confidenceCap);
  const confidenceCapValue = conciseText(confidenceCapRecord?.value) || conciseText(confidenceCap) || conciseText(dataQualityReport?.confidenceCap);
  const thesisEligibility = asRecord(readRecordField(packet, ['thesisEligibility', 'thesis_eligibility']));
  const sourceRefs = asArray(readRecordField(packet, ['sourceRefs', 'source_refs']));
  const scoreEligibleEvidence = asArray(readRecordField(packet, ['scoreEligibleEvidence', 'score_eligible_evidence']));
  const observationOnlyEvidence = asArray(readRecordField(packet, ['observationOnlyEvidence', 'observation_only_evidence']));
  const lines: string[] = [];

  const notInvestmentAdvice = readRecordField(packet, ['notInvestmentAdvice', 'not_investment_advice']);
  if (notInvestmentAdvice === true) {
    lines.push('- 继续跟踪: 本报告仅支持观察和研究记录。');
  }
  if (confidenceCapValue) {
    lines.push(`- 研究包完整度: ${confidenceCapValue}`);
  }

  const confidenceLabel = conciseField(packet, ['confidenceLabel', 'confidence_label']);
  if (confidenceLabel) {
    lines.push(`- 情景参考: ${consumerSafeReportText(confidenceLabel, '数据不足')}`);
  }
  const promptSummary = conciseField(packet, ['promptSummary', 'prompt_summary']);
  if (promptSummary) {
    lines.push(`- 研究摘要: ${consumerSafeReportText(promptSummary, CONSUMER_REPORT_OBSERVATION_FALLBACK)}`);
  }
  const thesisStatus = conciseField(thesisEligibility, ['status']);
  if (thesisStatus) {
    lines.push(`- 数据不足: ${consumerSafeReportStatus(thesisStatus)}`);
  }

  const dataGapLines = asArray(readRecordField(packet, ['dataGaps', 'data_gaps']))
    .map(formatEvidenceGap)
    .filter((item): item is string => Boolean(item))
    .slice(0, 5);
  dataGapLines.forEach((item) => lines.push(`- 数据不足: ${item}`));

  const boundaryLines = asArray(readRecordField(packet, ['claimBoundaries', 'claim_boundaries']))
    .map(formatClaimBoundary)
    .filter((item): item is string => Boolean(item))
    .slice(0, 5);
  boundaryLines.forEach((item) => lines.push(`- 风险边界: ${item}`));

  if (sourceRefs.length || scoreEligibleEvidence.length || observationOnlyEvidence.length) {
    lines.push(`- 情景参考: 已折叠 ${sourceRefs.length} 条研究线索，未导出原始引用。`);
  }
  sourceRefs
    .map(formatSourceRef)
    .filter((item): item is string => Boolean(item))
    .slice(0, 5)
    .forEach((item) => lines.push(`- 研究包状态: ${item}`));

  const observationClasses = evidenceClasses(observationOnlyEvidence);
  if (observationClasses.length) {
    lines.push(`- 继续跟踪: ${observationClasses.length} 类证据仅作观察背景。`);
  }

  return lines.length ? ['## 研究包完整度 / Research Packet Completeness', ...lines, ''] : [];
}

const REPORT_DATE_FORMATTER = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

function formatReportDateTime(value?: string): string {
  const text = String(value || '').trim();
  if (!text) {
    return '--';
  }
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return text;
  }
  return REPORT_DATE_FORMATTER.format(date);
}

export function buildInstitutionalReportMarkdown(
  report: AnalysisReport | null,
  override?: Partial<{ companyName: string; ticker: string; generatedAt: string }>,
): string {
  const ticker = override?.ticker || getSymbolDisplay(report);
  const companyName = override?.companyName || getCompanyDisplayName(report);
  const companyWithTicker = companyName.toUpperCase() === ticker ? ticker : `${companyName} (${ticker})`;
  const standardReport = report?.details?.standardReport;
  const summaryPanel = standardReport?.summaryPanel;
  const decisionPanel = standardReport?.decisionPanel;
  const reasonLayer = standardReport?.reasonLayer;
  const coverageNotes = standardReport?.coverageNotes;
  const highlights = standardReport?.highlights;
  const market = standardReport?.market;
  const marketFields = [
    ...(market?.displayFields || []),
    ...(market?.regularFields || []),
    ...(market?.extendedFields || []),
  ];
  const technicalFields = standardReport?.technicalFields || standardReport?.tableSections?.technical?.fields || [];
  const fundamentalFields = standardReport?.fundamentalFields || standardReport?.tableSections?.fundamental?.fields || [];
  const earningsFields = standardReport?.earningsFields || standardReport?.tableSections?.earnings?.fields || [];
  const sentimentFields = standardReport?.sentimentFields || [];
  const battleFields = standardReport?.battleFields || [];
  const fieldValue = (fields: Array<{ label?: string; value?: unknown }> | undefined, aliases: string[]) => {
    const loweredAliases = aliases.map((alias) => alias.toLowerCase());
    const field = fields?.find((item) => {
      const label = String(item.label || '').toLowerCase();
      return loweredAliases.some((alias) => label.includes(alias));
    });
    return consumerSafeReportText(field?.value, EMPTY_DISPLAY_VALUE);
  };
  const priceFieldValue = (fields: Array<{ label?: string; value?: unknown }> | undefined, aliases: string[]) => {
    const loweredAliases = aliases.map((alias) => alias.toLowerCase());
    const field = fields?.find((item) => {
      const label = String(item.label || '').toLowerCase();
      return loweredAliases.some((alias) => label.includes(alias));
    });
    return consumerSafeReportPriceContext(field?.value, EMPTY_DISPLAY_VALUE);
  };
  const generatedAt = override?.generatedAt || report?.meta.reportGeneratedAt || report?.meta.createdAt;
  const dataSources = report?.decisionTrace?.dataSources || [];
  const dataStatus = [
    ...new Set(dataSources.flatMap((source) => source.status ? [consumerSafeReportStatus(source.status)] : [])),
  ].join(' / ') || EMPTY_DISPLAY_VALUE;
  const battleCards = standardReport?.battlePlanCompact?.cards || [];
  const battleNotes = standardReport?.battlePlanCompact?.notes || [];
  const evidenceBoundaryLines = buildEvidenceBoundaryLines(report);
  const compactList = (items?: Array<string | undefined | null>, fallback = '- 数据缺失') => {
    const values = uniqueText((items || [])
      .map((item) => consumerSafeReportText(item, ''))
      .filter(Boolean));
    return values.length ? values.map((item) => `- ${item}`) : [fallback];
  };
  const safeFieldLines = (fields: Array<{ label?: string; value?: unknown }> | undefined, fallback = '- 数据缺失') => {
    const values = (fields || []).flatMap((field) => {
      const label = consumerSafeReportLabel(field.label);
      if (!label) return [];
      const value = ['关键价格区间', '参考区间', '上方观察区', '风险边界'].includes(label)
        ? consumerSafeReportPriceContext(field.value, CONSUMER_REPORT_DATA_GAP_FALLBACK)
        : consumerSafeReportText(field.value, CONSUMER_REPORT_DATA_GAP_FALLBACK);
      return value ? [`- ${label}: ${value}`] : [];
    });
    return values.length ? values : [fallback];
  };
  const checklistLines = (standardReport?.checklistItems || [])
    .flatMap((item) => {
      const text = consumerSafeReportText(item.text, '研究包完整度待复核。');
      return text ? [`- [${consumerSafeReportText(item.status, 'UNKNOWN')}] ${text}`] : [];
    });

  return [
    `# Wolfy AI Equity Research: ${companyWithTicker}`,
    '',
    `- 研究状态: ${consumerSafeReportText(summaryPanel?.operationAdvice || report?.summary.operationAdvice, '继续跟踪')}`,
    `- Score: ${safeReportValue(summaryPanel?.score ?? report?.summary.sentimentScore)} / 100`,
    `- Confidence: ${consumerSafeReportText(decisionPanel?.confidence || report?.decisionTrace?.decisionFields?.confidence?.value, '数据不足')}`,
    `- Report generated: ${formatReportDateTime(generatedAt)}`,
    `- Market: ${safeReportValue(report?.decisionTrace?.market)}`,
    `- Currency: ${safeReportValue(readObjectField(standardReport, ['summaryPanel', 'currency']) || readObjectField(standardReport, ['market', 'currency']))}`,
    `- 研究包状态: ${dataStatus}`,
    `- Time horizon: ${consumerSafeReportText(summaryPanel?.timeSensitivity || decisionPanel?.marketStructure, '情景参考')}`,
    '',
    'AI 洞察仅供参考，不构成投资建议。',
    '',
    '## 研究包完整度 / Research Packet Completeness',
    `- 继续跟踪: ${consumerSafeReportText(summaryPanel?.operationAdvice || report?.summary.operationAdvice, '继续跟踪')}`,
    `- 评分: ${safeReportValue(summaryPanel?.score ?? report?.summary.sentimentScore)}`,
    `- 情景参考: ${consumerSafeReportText(decisionPanel?.marketStructure || summaryPanel?.trendPrediction || report?.summary.trendPrediction, '情景参考')}`,
    `- 研究摘要: ${consumerSafeReportText(summaryPanel?.oneSentence || report?.summary.analysisSummary, CONSUMER_REPORT_OBSERVATION_FALLBACK)}`,
    `- 关键理由: ${consumerSafeReportText(reasonLayer?.coreReasons?.[0] || reasonLayer?.latestKeyUpdate, '价格与证据仍需继续跟踪。')}`,
    '',
    '## 重要信息速览 / Important Brief',
    `- 舆情情绪: ${consumerSafeReportText(highlights?.sentimentSummary || reasonLayer?.sentimentSummary || fieldValue(sentimentFields, ['sentiment', '舆情', '情绪']) || report?.summary.sentimentLabel, '数据不足')}`,
    `- 业绩预期: ${consumerSafeReportText(highlights?.earningsOutlook || fieldValue(earningsFields, ['earnings', '业绩', 'eps']), '数据不足')}`,
    ...compactList(highlights?.latestNews || [reasonLayer?.latestKeyUpdate], '- 最新动态: 数据缺失'),
    '',
    '## 风险边界 / Risk Boundaries',
    ...compactList([reasonLayer?.topRisk, ...(highlights?.riskAlerts || []), ...(highlights?.bearishFactors || [])], '- 风险边界: 暂无明确风险条目'),
    '',
    '## 情景参考 / Scenario Context',
    ...compactList([reasonLayer?.topCatalyst, ...(highlights?.positiveCatalysts || []), ...(highlights?.bullishFactors || [])], '- 情景参考: 数据不足'),
    '',
    '## 当日行情 / Market Snapshot',
    `- Open: ${fieldValue(marketFields, ['open', '开盘'])}`,
    `- High: ${fieldValue(marketFields, ['high', '最高'])}`,
    `- Low: ${fieldValue(marketFields, ['low', '最低'])}`,
    `- Close: ${safeReportValue(summaryPanel?.currentPrice || fieldValue(marketFields, ['close', '收盘', 'current']))}`,
    `- Change pct: ${safeReportValue(summaryPanel?.changePct || fieldValue(marketFields, ['change pct', 'change%', '涨跌幅']))}`,
    `- Volume: ${fieldValue(marketFields, ['volume', '成交量'])}`,
    `- Turnover: ${fieldValue(marketFields, ['turnover', 'amount', '成交额'])}`,
    '',
    '## 数据透视 / Data Lens',
    `- MA alignment: ${fieldValue(technicalFields, ['MA ALIGNMENT', 'Moving Averages', '均线'])}`,
    `- Current price: ${safeReportValue(summaryPanel?.currentPrice || decisionPanel?.analysisPrice)}`,
    `- MA5: ${fieldValue(technicalFields, ['MA5', '5日'])}`,
    `- MA10: ${fieldValue(technicalFields, ['MA10', '10日'])}`,
    `- MA20: ${fieldValue(technicalFields, ['MA20', '20日'])}`,
    `- MA60: ${fieldValue(technicalFields, ['MA60', '60日'])}`,
    `- 关键价格区间: ${consumerSafeReportPriceContext(decisionPanel?.support || decisionPanel?.idealEntry || report?.strategy?.idealBuy || priceFieldValue(battleFields, ['ideal', '理想']), '数据不足')}`,
    `- 上方观察区: ${consumerSafeReportPriceContext(decisionPanel?.resistance || decisionPanel?.target || decisionPanel?.targetZone || report?.strategy?.takeProfit || priceFieldValue(battleFields, ['target', '目标']), '数据不足')}`,
    '',
    '## 技术透视 / Technical View',
    ...safeFieldLines(technicalFields),
    '',
    '## 基本面摘要 / Fundamental Snapshot',
    ...safeFieldLines(fundamentalFields),
    '',
    '## 继续跟踪 / Observation Plan',
    `- 关键价格区间: ${consumerSafeReportPriceContext(decisionPanel?.idealEntry || report?.strategy?.idealBuy || priceFieldValue(battleFields, ['ideal', '理想']), '数据不足')}`,
    `- 参考区间: ${consumerSafeReportPriceContext(decisionPanel?.backupEntry || report?.strategy?.secondaryBuy || priceFieldValue(battleFields, ['secondary', '次级']), '数据不足')}`,
    `- 风险边界: ${consumerSafeReportPriceContext(decisionPanel?.stopLoss || report?.strategy?.stopLoss || priceFieldValue(battleFields, ['stop', '止损']), '数据不足')}`,
    `- 上方观察区: ${consumerSafeReportPriceContext(decisionPanel?.target || decisionPanel?.targetZone || report?.strategy?.takeProfit || priceFieldValue(battleFields, ['target', '目标']), '数据不足')}`,
    `- 风险边界: ${consumerSafeReportText(decisionPanel?.positionSizing || battleCards.find((item) => /position|仓位/i.test(item.label))?.value, '风险边界仅作情景约束。')}`,
    `- 继续跟踪: ${consumerSafeReportText(decisionPanel?.buildStrategy || battleNotes.find((item) => /entry|建仓|入场/i.test(item.label))?.value, '继续跟踪，等待研究包补齐。')}`,
    `- 风险边界: ${consumerSafeReportText(decisionPanel?.riskControlStrategy || decisionPanel?.stopReason, '风险边界用于说明不确定性。')}`,
    `- 数据不足: ${consumerSafeReportText(decisionPanel?.noPositionAdvice, '数据不足，仅支持继续跟踪。')}`,
    `- 继续跟踪: ${consumerSafeReportText(decisionPanel?.holderAdvice, '继续跟踪，不输出配置建议。')}`,
    ...(decisionPanel?.executionReminders?.length ? compactList(decisionPanel.executionReminders, '- 继续跟踪: 暂无额外提醒') : []),
    '',
    '## 研究清单 / Research Checklist',
    ...(checklistLines.length ? checklistLines : ['- [UNKNOWN] 数据覆盖待确认']),
    '',
    ...evidenceBoundaryLines,
    '## 数据说明 / Data Notes',
    ...(coverageNotes?.coverageGaps?.length ? compactList(coverageNotes.coverageGaps, '- 缺失字段会以 -- 展示') : ['- 缺失字段会以 -- 展示']),
    ...(coverageNotes?.conflictNotes?.length ? compactList(coverageNotes.conflictNotes, '- 暂无额外冲突说明') : []),
    ...(coverageNotes?.methodNotes?.length ? compactList(coverageNotes.methodNotes, '- AI 洞察仅供参考，不构成投资建议。') : []),
  ].join('\n');
}
