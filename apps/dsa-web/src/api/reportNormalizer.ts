import type {
  AnalysisReport,
  DecisionTrace,
  FrontendReportContractMeta,
  ReportDetails,
  ReportMeta,
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
  const rawResult = toRecord(details?.rawResult);
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
  ];
  const decisionTraceMatch = decisionTraceCandidates.find((candidate) => toRecord(candidate));
  const normalizedDecisionTrace = (
    decisionTraceMatch ? camelizeDeep(decisionTraceMatch) : undefined
  ) as DecisionTrace | undefined;
  const normalizedAnalysisResult = toRecord(camelizeDeep(
    (details as Record<string, unknown> | undefined)?.analysisResult
      ?? (details as Record<string, unknown> | undefined)?.analysis_result,
  ));
  const payloadVariant: FrontendReportContractMeta['payloadVariant'] = normalizedStandardReport
    ? 'standard_report'
    : report.details
      ? 'legacy_only'
      : 'legacy_empty';

  const sentimentScore = toFiniteNumber(summary.sentimentScore) ?? DEFAULT_SENTIMENT_SCORE;
  const normalizedDetails: ReportDetails | undefined = report.details
    ? {
        ...report.details,
        standardReport: normalizedStandardReport,
        analysisResult: normalizedAnalysisResult,
      }
    : report.details;

  return {
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
    contractMeta: {
      payloadVariant,
      standardReportSource,
    },
  };
};

export const normalizeFrontendReportContract = normalizeAnalysisReport;
