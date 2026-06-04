import type { AnalysisReport } from '../types/analysis';

const EMPTY_FIELD_VALUE = '-';
const EMPTY_DISPLAY_VALUE = '--';

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

function conciseList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return uniqueText(value.flatMap((item) => { const t = conciseText(item); return t ? [t] : []; }));
  }
  const text = conciseText(value);
  return text ? [text] : [];
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
    return conciseText(item);
  }
  const label = uniqueText([
    conciseField(record, ['evidenceClass', 'evidence_class', 'surface', 'key', 'label']),
    conciseField(record, ['reasonCode', 'reason_code', 'reason']),
  ]).join(' / ');
  const detail = conciseField(record, ['detail', 'message', 'summary', 'status']);
  if (label && detail) {
    return `${label} - ${detail}`;
  }
  return label || detail;
}

function formatClaimBoundary(item: unknown): string | null {
  const record = asRecord(item);
  if (!record) {
    return conciseText(item);
  }
  const claim = conciseField(record, ['claim', 'key', 'label']);
  const allowed = readRecordField(record, ['allowed']);
  const state = typeof allowed === 'boolean' ? (allowed ? 'allowed' : 'blocked') : conciseField(record, ['status', 'state']);
  const reason = conciseField(record, ['reasonCode', 'reason_code', 'reason']);
  const detail = conciseField(record, ['detail', 'message', 'summary']);
  const claimState = uniqueText([claim, state]).join(' ');
  const head = uniqueText([claimState, reason]).join(' / ');
  if (head && detail) {
    return `${head} - ${detail}`;
  }
  return head || detail;
}

function formatSourceRef(item: unknown): string | null {
  const record = asRecord(item);
  if (!record) {
    return conciseText(item);
  }
  const parts = uniqueText([
    conciseField(record, ['sourceRefId', 'source_ref_id', 'id']),
    conciseField(record, ['provider', 'providerId', 'provider_id']),
    conciseField(record, ['status']),
    conciseField(record, ['freshness', 'freshnessClass', 'freshness_class']),
  ]);
  const observationOnly = readRecordField(record, ['observationOnly', 'observation_only']);
  if (observationOnly === true) {
    parts.push('observation-only');
  }
  return parts.join(' / ') || null;
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
  const capReasons = uniqueText([
    ...conciseList(confidenceCapRecord?.reasonCodes),
    ...conciseList(confidenceCapRecord?.reason_codes),
    ...conciseList(dataQualityReport?.reasonCodes),
  ]);
  const thesisEligibility = asRecord(readRecordField(packet, ['thesisEligibility', 'thesis_eligibility']));
  const sourceRefs = asArray(readRecordField(packet, ['sourceRefs', 'source_refs']));
  const scoreEligibleEvidence = asArray(readRecordField(packet, ['scoreEligibleEvidence', 'score_eligible_evidence']));
  const observationOnlyEvidence = asArray(readRecordField(packet, ['observationOnlyEvidence', 'observation_only_evidence']));
  const lines: string[] = [];

  const notInvestmentAdvice = readRecordField(packet, ['notInvestmentAdvice', 'not_investment_advice']);
  if (typeof notInvestmentAdvice === 'boolean') {
    lines.push(`- Not investment advice: ${notInvestmentAdvice}`);
  }
  if (confidenceCapValue) {
    lines.push(`- Confidence cap: ${confidenceCapValue}`);
  }
  if (capReasons.length) {
    lines.push(`- Cap reasons: ${capReasons.slice(0, 5).join(', ')}`);
  }

  const confidenceLabel = conciseField(packet, ['confidenceLabel', 'confidence_label']);
  if (confidenceLabel) {
    lines.push(`- Packet confidence: ${confidenceLabel}`);
  }
  const promptSummary = conciseField(packet, ['promptSummary', 'prompt_summary']);
  if (promptSummary) {
    lines.push(`- Packet summary: ${promptSummary}`);
  }
  const thesisStatus = conciseField(thesisEligibility, ['status']);
  if (thesisStatus) {
    lines.push(`- Thesis eligibility: ${thesisStatus}`);
  }

  const dataGapLines = asArray(readRecordField(packet, ['dataGaps', 'data_gaps']))
    .map(formatEvidenceGap)
    .filter((item): item is string => Boolean(item))
    .slice(0, 5);
  dataGapLines.forEach((item) => lines.push(`- Data gap: ${item}`));

  const boundaryLines = asArray(readRecordField(packet, ['claimBoundaries', 'claim_boundaries']))
    .map(formatClaimBoundary)
    .filter((item): item is string => Boolean(item))
    .slice(0, 5);
  boundaryLines.forEach((item) => lines.push(`- Boundary: ${item}`));

  if (sourceRefs.length || scoreEligibleEvidence.length || observationOnlyEvidence.length) {
    lines.push(`- Source refs: ${sourceRefs.length} total; ${scoreEligibleEvidence.length} score-eligible; ${observationOnlyEvidence.length} observation-only`);
  }
  sourceRefs
    .map(formatSourceRef)
    .filter((item): item is string => Boolean(item))
    .slice(0, 5)
    .forEach((item) => lines.push(`- Source: ${item}`));

  const observationClasses = evidenceClasses(observationOnlyEvidence);
  if (observationClasses.length) {
    lines.push(`- Observation-only evidence: ${observationClasses.slice(0, 5).join(', ')}`);
  }

  return lines.length ? ['## 证据边界 / Evidence Boundaries', ...lines, ''] : [];
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
    return safeReportValue(field?.value);
  };
  const generatedAt = override?.generatedAt || report?.meta.reportGeneratedAt || report?.meta.createdAt;
  const dataSources = report?.decisionTrace?.dataSources || [];
  const dataStatus = [
    ...new Set(dataSources.flatMap((source) => source.status ? [source.status] : [])),
  ].join(' / ') || EMPTY_DISPLAY_VALUE;
  const alphaVantage = readObjectField(report, ['details', 'rawResult', 'dashboard', 'data_perspective', 'alpha_vantage']);
  const alphaEntries = alphaVantage && typeof alphaVantage === 'object'
    ? Object.entries(alphaVantage as Record<string, unknown>).map(([key, value]) => `- ${key}: ${safeReportValue(value)}`)
    : [];
  const battleCards = standardReport?.battlePlanCompact?.cards || [];
  const battleNotes = standardReport?.battlePlanCompact?.notes || [];
  const evidenceBoundaryLines = buildEvidenceBoundaryLines(report);
  const compactList = (items?: Array<string | undefined | null>, fallback = '- 数据缺失') => {
    const values = uniqueText(items || []);
    return values.length ? values.map((item) => `- ${item}`) : [fallback];
  };

  return [
    `# Wolfy AI Equity Research: ${companyWithTicker}`,
    '',
    `- Action: ${safeReportValue(summaryPanel?.operationAdvice || report?.summary.operationAdvice)}`,
    `- Score: ${safeReportValue(summaryPanel?.score ?? report?.summary.sentimentScore)} / 100`,
    `- Confidence: ${safeReportValue(decisionPanel?.confidence || report?.decisionTrace?.decisionFields?.confidence?.value)}`,
    `- Report generated: ${formatReportDateTime(generatedAt)}`,
    `- Market: ${safeReportValue(report?.decisionTrace?.market)}`,
    `- Currency: ${safeReportValue(readObjectField(standardReport, ['summaryPanel', 'currency']) || readObjectField(standardReport, ['market', 'currency']))}`,
    `- Data status: ${dataStatus}`,
    `- Time horizon: ${safeReportValue(summaryPanel?.timeSensitivity || decisionPanel?.marketStructure)}`,
    '',
    'AI 洞察仅供参考，不构成投资建议。',
    '',
    '## 投资结论 / Investment Thesis',
    `- 动作: ${safeReportValue(summaryPanel?.operationAdvice || report?.summary.operationAdvice)}`,
    `- 评分: ${safeReportValue(summaryPanel?.score ?? report?.summary.sentimentScore)}`,
    `- 趋势/结构: ${safeReportValue(decisionPanel?.marketStructure || summaryPanel?.trendPrediction || report?.summary.trendPrediction)}`,
    `- 一句话判断: ${safeReportValue(summaryPanel?.oneSentence || report?.summary.analysisSummary)}`,
    `- 关键理由: ${safeReportValue(reasonLayer?.coreReasons?.[0] || reasonLayer?.latestKeyUpdate)}`,
    '',
    '## 重要信息速览 / Important Brief',
    `- 舆情情绪: ${safeReportValue(highlights?.sentimentSummary || reasonLayer?.sentimentSummary || fieldValue(sentimentFields, ['sentiment', '舆情', '情绪']) || report?.summary.sentimentLabel)}`,
    `- 业绩预期: ${safeReportValue(highlights?.earningsOutlook || fieldValue(earningsFields, ['earnings', '业绩', 'eps']))}`,
    ...compactList(highlights?.latestNews || [reasonLayer?.latestKeyUpdate], '- 最新动态: 数据缺失'),
    '',
    '## 风险警报 / Risk Alerts',
    ...compactList([reasonLayer?.topRisk, ...(highlights?.riskAlerts || []), ...(highlights?.bearishFactors || [])]),
    '',
    '## 利好催化 / Positive Catalysts',
    ...compactList([reasonLayer?.topCatalyst, ...(highlights?.positiveCatalysts || []), ...(highlights?.bullishFactors || [])]),
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
    `- Support: ${safeReportValue(decisionPanel?.support || decisionPanel?.idealEntry || report?.strategy?.idealBuy)}`,
    `- Resistance: ${safeReportValue(decisionPanel?.resistance || decisionPanel?.target || decisionPanel?.targetZone || report?.strategy?.takeProfit)}`,
    ...(alphaEntries.length ? alphaEntries : ['- Alpha Vantage indicators: 数据缺失']),
    '',
    '## 技术透视 / Technical View',
    ...(technicalFields.length ? technicalFields.map((field) => `- ${field.label}: ${safeReportValue(field.value)}`) : ['- 数据缺失']),
    '',
    '## 基本面摘要 / Fundamental Snapshot',
    ...(fundamentalFields.length ? fundamentalFields.map((field) => `- ${field.label}: ${safeReportValue(field.value)}`) : ['- 数据缺失']),
    '',
    '## 观察计划 / Observation Plan',
    `- Ideal buy: ${safeReportValue(decisionPanel?.idealEntry || report?.strategy?.idealBuy || fieldValue(battleFields, ['ideal', '理想']))}`,
    `- Secondary buy: ${safeReportValue(decisionPanel?.backupEntry || report?.strategy?.secondaryBuy || fieldValue(battleFields, ['secondary', '次级']))}`,
    `- Stop loss: ${safeReportValue(decisionPanel?.stopLoss || report?.strategy?.stopLoss || fieldValue(battleFields, ['stop', '止损']))}`,
    `- Target: ${safeReportValue(decisionPanel?.target || decisionPanel?.targetZone || report?.strategy?.takeProfit || fieldValue(battleFields, ['target', '目标']))}`,
    `- Position sizing: ${safeReportValue(decisionPanel?.positionSizing || battleCards.find((item) => /position|仓位/i.test(item.label))?.value)}`,
    `- Entry strategy: ${safeReportValue(decisionPanel?.buildStrategy || battleNotes.find((item) => /entry|建仓|入场/i.test(item.label))?.value)}`,
    `- Risk control strategy: ${safeReportValue(decisionPanel?.riskControlStrategy || decisionPanel?.stopReason)}`,
    `- Empty-position advice: ${safeReportValue(decisionPanel?.noPositionAdvice)}`,
    `- Holding-position advice: ${safeReportValue(decisionPanel?.holderAdvice)}`,
    ...(decisionPanel?.executionReminders?.length ? decisionPanel.executionReminders.map((item) => `- ${item}`) : []),
    '',
    '## 检查清单 / Decision Checklist',
    ...(standardReport?.checklistItems?.length ? standardReport.checklistItems.map((item) => `- [${item.status}] ${item.text}`) : ['- [UNKNOWN] 数据覆盖待确认']),
    '',
    ...evidenceBoundaryLines,
    '## 数据说明 / Data Notes',
    ...(coverageNotes?.dataSources?.length ? coverageNotes.dataSources.map((item) => `- ${item}`) : ['- 数据源未完整标注']),
    ...(coverageNotes?.coverageGaps?.length ? coverageNotes.coverageGaps.map((item) => `- ${item}`) : ['- 缺失字段会以 -- 展示']),
  ].join('\n');
}
