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

export function dedupeTickerFromName(value: unknown, ticker: string): string {
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

export function getCompanyName(result: unknown): string | null {
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

export const getSymbol = getSymbolDisplay;

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

function formatReportDateTime(value?: string): string {
  const text = String(value || '').trim();
  if (!text) {
    return '--';
  }
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return text;
  }
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
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
  const providers = uniqueText(dataSources.map((source) => source.provider || source.name)).join(', ') || EMPTY_DISPLAY_VALUE;
  const dataStatus = [
    ...new Set([
      ...dataSources.map((source) => source.status).filter(Boolean),
      report?.decisionTrace?.llm?.schemaValidated ? 'schema ok' : 'schema unverified',
    ]),
  ].join(' / ') || EMPTY_DISPLAY_VALUE;
  const alphaVantage = readObjectField(report, ['details', 'rawResult', 'dashboard', 'data_perspective', 'alpha_vantage']);
  const alphaEntries = alphaVantage && typeof alphaVantage === 'object'
    ? Object.entries(alphaVantage as Record<string, unknown>).map(([key, value]) => `- ${key}: ${safeReportValue(value)}`)
    : [];
  const battleCards = standardReport?.battlePlanCompact?.cards || [];
  const battleNotes = standardReport?.battlePlanCompact?.notes || [];
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
    `- Data providers: ${providers}`,
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
    '## 作战计划 / Trading Plan',
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
    '## 数据说明 / Data Notes',
    ...(coverageNotes?.dataSources?.length ? coverageNotes.dataSources.map((item) => `- ${item}`) : ['- 数据源未完整标注']),
    ...(coverageNotes?.coverageGaps?.length ? coverageNotes.coverageGaps.map((item) => `- ${item}`) : ['- 缺失字段会以 -- 展示']),
  ].join('\n');
}
