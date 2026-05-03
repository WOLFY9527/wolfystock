import type { AnalysisReport } from '../types/analysis';

const EMPTY_FIELD_VALUE = '-';

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
  return text && text !== '-' && !/^n\/?a$/i.test(text) ? text : '--';
}

function stripTickerFromName(value: unknown, ticker: string): string {
  const text = String(value || '').trim();
  const normalizedTicker = normalizeTickerQuery(ticker);
  if (!text || !normalizedTicker) {
    return text;
  }

  const tickerPattern = normalizedTicker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const withoutWrappedTicker = text
    .replace(new RegExp(`\\s*[（(]\\s*${tickerPattern}\\s*[）)]`, 'gi'), ' ')
    .replace(new RegExp(`(?:^|\\s)${tickerPattern}(?:\\s|$)`, 'gi'), ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return withoutWrappedTicker || normalizedTicker;
}

export function normalizeCompanyNameCandidate(value: unknown, ticker: string): string {
  const normalizedTicker = normalizeTickerQuery(ticker);
  const cleaned = stripTickerFromName(value, normalizedTicker);
  if (!cleaned || cleaned.toUpperCase() === normalizedTicker) {
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
    ?? readObjectField(result, ['details', 'standardReport', 'summaryPanel', 'ticker']);
  return normalizeTickerQuery(String(direct || '')) || EMPTY_FIELD_VALUE;
}

export function getCompanyDisplayName(result: unknown): string {
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
    readObjectField(result, ['fundamental', 'profile', 'name']),
    readObjectField(result, ['meta', 'stockName']),
    readObjectField(result, ['details', 'standardReport', 'summaryPanel', 'stock']),
  ];
  const company = candidates
    .map((candidate) => normalizeCompanyNameCandidate(candidate, ticker))
    .find(Boolean);
  return company || ticker;
}

export function getCompanyWithTicker(result: unknown): string {
  const ticker = getSymbolDisplay(result);
  const company = getCompanyDisplayName(result);
  if (!ticker || ticker === EMPTY_FIELD_VALUE || !company || company.toUpperCase() === ticker) {
    return ticker || company || EMPTY_FIELD_VALUE;
  }
  return `${company} (${ticker})`;
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
  const generatedAt = override?.generatedAt || report?.meta.reportGeneratedAt || report?.meta.createdAt;
  const dataSources = report?.decisionTrace?.dataSources || [];
  const providers = dataSources.map((source) => source.provider || source.name).filter(Boolean).join(', ') || '--';
  const dataStatus = [
    ...new Set([
      ...dataSources.map((source) => source.status).filter(Boolean),
      report?.decisionTrace?.llm?.schemaValidated ? 'schema ok' : 'schema unverified',
    ]),
  ].join(' / ') || '--';

  return [
    `# Wolfy AI Equity Research: ${companyWithTicker}`,
    '',
    `- Action: ${safeReportValue(summaryPanel?.operationAdvice || report?.summary.operationAdvice)}`,
    `- Score: ${safeReportValue(summaryPanel?.score ?? report?.summary.sentimentScore)} / 100`,
    `- Confidence: ${safeReportValue(decisionPanel?.confidence || report?.decisionTrace?.decisionFields?.confidence?.value)}`,
    `- Report generated: ${formatReportDateTime(generatedAt)}`,
    `- Market: ${safeReportValue(report?.decisionTrace?.market)}`,
    `- Data providers: ${providers}`,
    `- Data status: ${dataStatus}`,
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
    '## 执行计划 / Trading Plan',
    `- 理想买点: ${safeReportValue(decisionPanel?.idealEntry || report?.strategy?.idealBuy)}`,
    `- 次级买点: ${safeReportValue(decisionPanel?.backupEntry || report?.strategy?.secondaryBuy)}`,
    `- 目标: ${safeReportValue(decisionPanel?.target || decisionPanel?.targetZone || report?.strategy?.takeProfit)}`,
    `- 止损: ${safeReportValue(decisionPanel?.stopLoss || report?.strategy?.stopLoss)}`,
    `- 风控策略: ${safeReportValue(decisionPanel?.riskControlStrategy || decisionPanel?.stopReason)}`,
    '',
    '## 核心证据 / Key Evidence',
    ...(reasonLayer?.coreReasons?.length ? reasonLayer.coreReasons.map((item) => `- ${item}`) : ['- 数据缺失']),
    '',
    '## 风险警报 / Risk Alerts',
    `- ${safeReportValue(reasonLayer?.topRisk)}`,
    '',
    '## 利好催化 / Positive Catalysts',
    `- ${safeReportValue(reasonLayer?.topCatalyst)}`,
    '',
    '## 市场快照 / Market Snapshot',
    `- Close: ${safeReportValue(summaryPanel?.currentPrice)}`,
    `- Change pct: ${safeReportValue(summaryPanel?.changePct)}`,
    '',
    '## 技术透视 / Technical View',
    ...(standardReport?.technicalFields?.length ? standardReport.technicalFields.map((field) => `- ${field.label}: ${safeReportValue(field.value)}`) : ['- 数据缺失']),
    '',
    '## 基本面摘要 / Fundamental Snapshot',
    ...(standardReport?.fundamentalFields?.length ? standardReport.fundamentalFields.map((field) => `- ${field.label}: ${safeReportValue(field.value)}`) : ['- 数据缺失']),
    '',
    '## 检查清单 / Decision Checklist',
    ...(standardReport?.checklistItems?.length ? standardReport.checklistItems.map((item) => `- [${item.status}] ${item.text}`) : ['- [UNKNOWN] 数据覆盖待确认']),
    '',
    '## 数据说明 / Data Notes',
    ...(coverageNotes?.dataSources?.length ? coverageNotes.dataSources.map((item) => `- ${item}`) : ['- 数据源未完整标注']),
    ...(coverageNotes?.coverageGaps?.length ? coverageNotes.coverageGaps.map((item) => `- ${item}`) : ['- 缺失字段会以 -- 展示']),
  ].join('\n');
}
