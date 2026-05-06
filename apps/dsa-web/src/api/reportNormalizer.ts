import type {
  AnalysisReport,
  DataQualityReport,
  DecisionTrace,
  FrontendReportContractMeta,
  ReportDetails,
  ReportMeta,
  ReportQuality,
  ReportSummary,
  ReportStandardSource,
  StandardReport,
} from '../types/analysis';

interface ReportMetaFallback extends Partial<ReportMeta> {
  queryId?: string;
  stockCode?: string;
  stockName?: string;
  companyName?: string;
  createdAt?: string;
}

const DEFAULT_SENTIMENT_SCORE = 50;

const toRecord = (value: unknown): Record<string, unknown> | undefined => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return undefined;
};

const toFiniteNumber = (value: unknown): number | undefined => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
};

const isNonEmptyText = (value: unknown): boolean => {
  const text = String(value ?? '').trim();
  return Boolean(text && text !== '-' && !/^n\/?a$/i.test(text) && !text.startsWith('NA（'));
};

const hasObjectContent = (value: unknown): boolean => {
  const record = toRecord(value);
  return Boolean(record && Object.keys(record).length > 0);
};

const hasFailedAnalysisText = (value: unknown): boolean => (
  typeof value === 'string'
  && /all llm models failed|serviceunavailable|rate limit|ratelimiterror|timeout|timed out|分析过程出错|llm.*failed|分析失败/i.test(value)
);

const hasVisibleFailureMarker = (report: AnalysisReport): boolean => [
  report.summary?.analysisSummary,
  report.summary?.operationAdvice,
  report.summary?.trendPrediction,
  report.details?.analysisResult ? (report.details.analysisResult as Record<string, unknown>).error : undefined,
  report.details?.analysisResult ? (report.details.analysisResult as Record<string, unknown>).status : undefined,
].some(hasFailedAnalysisText);

const readAnalysisResultField = (analysisResult: Record<string, unknown> | undefined, fields: string[]): unknown => {
  if (!analysisResult) {
    return undefined;
  }
  for (const field of fields) {
    const value = analysisResult[field];
    if (isNonEmptyText(value) || typeof value === 'number') {
      return value;
    }
  }
  return undefined;
};

export const normalizeReportQuality = (report: AnalysisReport): ReportQuality => {
  const standardReport = report.details?.standardReport;
  const analysisResult = toRecord(report.details?.analysisResult);
  const trace = report.decisionTrace;
  const traceFieldCount = Object.keys(trace?.decisionFields || {}).length;
  const traceSourceCount = trace?.dataSources?.length || 0;
  const hasDecisionTrace = hasObjectContent(trace);
  const hasStandardReport = hasObjectContent(standardReport);
  const hasAnalysisResult = hasObjectContent(analysisResult);
  const hasAction = Boolean(
    isNonEmptyText(trace?.decisionFields?.action?.value)
    || isNonEmptyText(standardReport?.summaryPanel?.operationAdvice)
    || isNonEmptyText(standardReport?.decisionPanel?.keyAction)
    || isNonEmptyText(report.summary?.operationAdvice)
    || isNonEmptyText(readAnalysisResultField(analysisResult, ['action', 'decision'])),
  );
  const hasScore = Boolean(
    isNonEmptyText(trace?.decisionFields?.score?.value)
    || standardReport?.summaryPanel?.score !== undefined
    || report.contractMeta?.hasExplicitSentimentScore === true
    || isNonEmptyText(readAnalysisResultField(analysisResult, ['score', 'sentimentScore'])),
  );
  const hasConfidence = Boolean(
    isNonEmptyText(trace?.decisionFields?.confidence?.value)
    || isNonEmptyText(standardReport?.decisionPanel?.confidence)
    || isNonEmptyText(readAnalysisResultField(analysisResult, ['confidence', 'confidenceLevel'])),
  );
  const hasTradingPlan = Boolean(
    isNonEmptyText(trace?.decisionFields?.entry?.value)
    || isNonEmptyText(trace?.decisionFields?.target?.value)
    || isNonEmptyText(trace?.decisionFields?.stop?.value)
    || isNonEmptyText(standardReport?.decisionPanel?.idealEntry)
    || isNonEmptyText(standardReport?.decisionPanel?.target)
    || isNonEmptyText(standardReport?.decisionPanel?.stopLoss)
    || isNonEmptyText(report.strategy?.idealBuy)
    || isNonEmptyText(report.strategy?.takeProfit)
    || isNonEmptyText(report.strategy?.stopLoss)
    || isNonEmptyText(readAnalysisResultField(analysisResult, ['entryPrice', 'takeProfit', 'stopLoss'])),
  );
  const summaryFields = [
    report.summary?.analysisSummary,
    report.summary?.operationAdvice,
    report.summary?.trendPrediction,
    standardReport?.summaryPanel?.oneSentence,
    standardReport?.decisionContext?.shortTermView,
    readAnalysisResultField(analysisResult, ['summary', 'fullReasoning']),
  ].filter(isNonEmptyText).length;
  const summaryStatus = summaryFields >= 3 ? 'complete' : summaryFields > 0 ? 'partial' : 'missing';
  const reportSectionCount = [
    standardReport?.summaryPanel,
    standardReport?.decisionPanel,
    standardReport?.technicalFields?.length,
    standardReport?.fundamentalFields?.length,
    standardReport?.reasonLayer,
    standardReport?.coverageNotes,
    standardReport?.battlePlanCompact,
    report.details?.newsContent,
  ].filter((value) => (typeof value === 'number' ? value > 0 : hasObjectContent(value) || isNonEmptyText(value))).length;
  const reportStatus = hasStandardReport && reportSectionCount >= 3
    ? 'complete'
    : hasStandardReport || hasAnalysisResult || summaryStatus !== 'missing'
      ? 'partial'
      : 'missing';
  const traceStatus = hasDecisionTrace
    ? traceFieldCount > 0 || traceSourceCount > 0
      ? 'present'
      : 'partial'
    : 'missing';
  const schemaStatus = trace?.llm?.schemaValidated === true
    ? 'ok'
    : hasDecisionTrace
      ? 'unconfirmed'
      : hasStandardReport
        ? 'unconfirmed'
        : reportStatus === 'missing'
          ? 'missing'
          : 'unknown';
  const missingFields: string[] = [];
  if (!hasDecisionTrace) missingFields.push('决策溯源');
  if (!hasStandardReport) missingFields.push('标准报告');
  if (!hasAction) missingFields.push('操作建议');
  if (!hasScore) missingFields.push('评分');
  if (!hasConfidence) missingFields.push('置信度');
  if (!hasTradingPlan) missingFields.push('交易计划');
  if (summaryStatus === 'missing') missingFields.push('摘要');

  const failed = hasVisibleFailureMarker(report) || reportStatus === 'missing' && summaryStatus === 'missing' && hasAnalysisResult && hasFailedAnalysisText(analysisResult?.status);
  const level = failed
    ? 'failed'
    : hasDecisionTrace && hasStandardReport && hasAction && hasScore && hasConfidence && hasTradingPlan
      ? 'complete'
      : hasStandardReport && (hasAction || hasScore || hasTradingPlan || hasAnalysisResult)
        ? 'usable'
        : reportStatus !== 'missing' || summaryStatus !== 'missing'
          ? 'legacy'
          : hasAnalysisResult
            ? 'partial'
            : 'unknown';

  const userLabel = {
    complete: '完整',
    usable: '可用',
    partial: '部分信息',
    legacy: '旧版记录',
    failed: '分析失败',
    unknown: '状态未知',
  }[level];
  const userHint = failed
    ? '本次分析未完整生成，可重新分析。'
    : level === 'complete'
      ? '结构化摘要与决策溯源完整。'
      : level === 'usable'
        ? '报告内容可用，但部分溯源或结构字段缺失。'
        : level === 'legacy'
          ? '旧版历史记录可阅读，但结构化字段不完整。'
          : level === 'partial'
            ? '仅保留部分报告信息。'
            : '暂未确认报告完整性。';

  return {
    level,
    schemaStatus,
    traceStatus,
    summaryStatus,
    reportStatus,
    hasDecisionTrace,
    hasStandardReport,
    hasAnalysisResult,
    hasAction,
    hasScore,
    hasConfidence,
    hasTradingPlan,
    missingFields,
    userLabel,
    userHint,
  };
};

const toCamelKey = (key: string): string =>
  key.replace(/_([a-z])/g, (_match, char: string) => char.toUpperCase());

const camelizeDeep = (value: unknown): unknown => {
  if (Array.isArray(value)) {
    return value.map(camelizeDeep);
  }
  if (value && typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>).reduce<Record<string, unknown>>((acc, [key, entry]) => {
      acc[toCamelKey(key)] = camelizeDeep(entry);
      return acc;
    }, {});
  }
  return value;
};

const normalizeAnalysisReport = (
  report: AnalysisReport,
  fallbackMeta: ReportMetaFallback = {},
): AnalysisReport => {
  const meta = report.meta || ({} as ReportMeta);
  const summary = report.summary || ({} as ReportSummary);
  const details = toRecord(report.details);
  const rawResult = toRecord(details?.rawResult) ?? toRecord(details?.raw_result);
  const persistedReport = toRecord(rawResult?.persistedReport) ?? toRecord(rawResult?.persisted_report);
  const nestedReport = toRecord(rawResult?.report);
  const dashboard = toRecord(rawResult?.dashboard);

  const standardReportCandidates: Array<{ source: ReportStandardSource; value: unknown }> = [
    { source: 'details.standardReport', value: details?.standardReport },
    { source: 'details.standard_report', value: (details as Record<string, unknown> | undefined)?.standard_report },
    { source: 'details.rawResult.standardReport', value: rawResult?.standardReport },
    { source: 'details.rawResult.standard_report', value: rawResult?.standard_report },
    { source: 'details.rawResult.dashboard.standardReport', value: dashboard?.standardReport },
    { source: 'details.rawResult.dashboard.standard_report', value: dashboard?.standard_report },
  ];
  const standardReportMatch = standardReportCandidates.find((candidate) => toRecord(candidate.value));
  const standardReportSource = standardReportMatch?.source ?? 'none';
  const standardReport = standardReportMatch ? toRecord(standardReportMatch.value) : undefined;
  const normalizedStandardReport = (
    standardReport ? camelizeDeep(standardReport) : undefined
  ) as StandardReport | undefined;
  const decisionTraceCandidates = [
    report.decisionTrace,
    toRecord((report as unknown as Record<string, unknown>).decision_trace),
    details?.decisionTrace,
    toRecord(details?.decision_trace),
    rawResult?.decisionTrace,
    toRecord(rawResult?.decision_trace),
    persistedReport?.decisionTrace,
    toRecord(persistedReport?.decision_trace),
    nestedReport?.decisionTrace,
    toRecord(nestedReport?.decision_trace),
  ];
  const decisionTraceMatch = decisionTraceCandidates.find((candidate) => toRecord(candidate));
  const normalizedDecisionTrace = (
    decisionTraceMatch ? camelizeDeep(decisionTraceMatch) : undefined
  ) as DecisionTrace | undefined;
  const normalizedAnalysisResult = toRecord(camelizeDeep(
    (details as Record<string, unknown> | undefined)?.analysisResult
      ?? (details as Record<string, unknown> | undefined)?.analysis_result,
  ));
  const dataQualityCandidates = [
    (report as unknown as Record<string, unknown>).dataQualityReport,
    toRecord((report as unknown as Record<string, unknown>).data_quality_report),
    meta.dataQualityReport,
    toRecord((meta as unknown as Record<string, unknown>).data_quality_report),
    details?.dataQualityReport,
    toRecord(details?.data_quality_report),
    normalizedAnalysisResult?.dataQualityReport,
    toRecord(normalizedAnalysisResult?.data_quality_report),
    rawResult?.dataQualityReport,
    toRecord(rawResult?.data_quality_report),
    toRecord(rawResult?.dashboard)?.structuredAnalysis
      ? toRecord(toRecord(rawResult?.dashboard)?.structuredAnalysis)?.dataQualityReport
      : undefined,
  ];
  const dataQualityMatch = dataQualityCandidates.find((candidate) => toRecord(candidate));
  const normalizedDataQualityReport = (
    dataQualityMatch ? camelizeDeep(dataQualityMatch) : undefined
  ) as DataQualityReport | undefined;
  const payloadVariant: FrontendReportContractMeta['payloadVariant'] = normalizedStandardReport
    ? 'standard_report'
    : report.details
      ? 'legacy_only'
      : 'legacy_empty';

  const hasExplicitSentimentScore = toFiniteNumber(summary.sentimentScore) !== undefined
    || toFiniteNumber((summary as unknown as Record<string, unknown>).sentiment_score) !== undefined;
  const sentimentScore = toFiniteNumber(summary.sentimentScore) ?? DEFAULT_SENTIMENT_SCORE;
  const normalizedDetails: ReportDetails | undefined = report.details
    ? {
        ...report.details,
        standardReport: normalizedStandardReport,
        dataQualityReport: normalizedDataQualityReport,
        analysisResult: normalizedAnalysisResult,
      }
    : report.details;

  const normalizedReport = {
    ...report,
    meta: {
      ...meta,
      queryId: meta.queryId || fallbackMeta.queryId || '',
      stockCode: meta.stockCode || fallbackMeta.stockCode || '',
      stockName: meta.stockName || fallbackMeta.stockName || meta.stockCode || fallbackMeta.stockCode || '',
      companyName: meta.companyName || meta.stockName || fallbackMeta.companyName || fallbackMeta.stockName || meta.stockCode || fallbackMeta.stockCode || '',
      reportType: meta.reportType || 'detailed',
      createdAt: meta.createdAt || fallbackMeta.createdAt || '',
    },
    summary: {
      ...summary,
      analysisSummary: summary.analysisSummary || '',
      operationAdvice: summary.operationAdvice || '',
      trendPrediction: summary.trendPrediction || '',
      sentimentScore,
    },
    details: normalizedDetails,
    decisionTrace: normalizedDecisionTrace,
    dataQualityReport: normalizedDataQualityReport,
    contractMeta: {
      payloadVariant,
      standardReportSource,
      hasExplicitSentimentScore,
    },
  };
  return {
    ...normalizedReport,
    reportQuality: normalizeReportQuality(normalizedReport),
  };
};

export const normalizeFrontendReportContract = normalizeAnalysisReport;
