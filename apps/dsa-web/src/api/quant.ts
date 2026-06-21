import apiClient from './index';
import { toCamelCase } from './utils';

export type QuantDuckDBHealthResponse = {
  enabled: boolean;
  available: boolean;
  databasePath: string;
  parquetRoot: string;
  version?: string | null;
  error?: string | null;
  schemaInitialized: boolean;
  status: string;
  engine: string;
};

export type QuantDuckDBCoverageSymbol = {
  symbol: string;
  ohlcvRows: number;
  minTradeDate?: string | null;
  maxTradeDate?: string | null;
  factorRows: number;
  latestFactorDate?: string | null;
};

export type QuantDuckDBCoverageResponse = {
  status: string;
  engine: string;
  enabled: boolean;
  databasePath: string;
  totalOhlcvRows: number;
  totalFactorRows: number;
  symbolCount: number;
  minTradeDate?: string | null;
  maxTradeDate?: string | null;
  latestFactorDate?: string | null;
  symbols: QuantDuckDBCoverageSymbol[];
  emptyReason?: string | null;
  error?: string | null;
};

export type QuantDuckDBBenchmarkTopResult = {
  symbol: string;
  tradeDate?: string | null;
  close?: number | null;
  return1d?: number | null;
  ma20?: number | null;
  momentum20d?: number | null;
  volatility20d?: number | null;
  closeVsMa20?: number | null;
  factorScore?: number | null;
};

export type QuantDuckDBBenchmarkResponse = {
  status: string;
  engine: string;
  elapsedMs: number;
  durationMs: number;
  ohlcvRows: number;
  factorRows: number;
  rowsScanned: number;
  symbolsScanned: number;
  symbolCount: number;
  dateCount: number;
  factorCount: number;
  queryType: string;
  dataMode: string;
  startDate?: string | null;
  endDate?: string | null;
  topResults: QuantDuckDBBenchmarkTopResult[];
  error?: string | null;
};

export type QuantDuckDBFactorCoverageSummary = {
  requestedSymbols: number;
  coveredSymbols: number;
  missingSymbols: number;
  sufficientSymbols: number;
  rowCount: number;
  minFactorDate?: string | null;
  maxFactorDate?: string | null;
};

export type QuantDuckDBFactorSnapshotRow = {
  symbol: string;
  tradeDate?: string | null;
  factors: Record<string, number | null>;
  factorTrend?: string | null;
  factorMomentum?: string | null;
  factorDataMode: string;
  factorWarnings: string[];
};

export type QuantDuckDBFactorSnapshotResponse = {
  status: string;
  engine: string;
  dataMode: string;
  durationMs: number;
  rowCount: number;
  coverage: QuantDuckDBFactorCoverageSummary;
  factorDates: string[];
  missingSymbols: string[];
  factors: string[];
  snapshots: QuantDuckDBFactorSnapshotRow[];
  warnings: string[];
  error?: string | null;
};

export type QuantDuckDBValidateFactorPathResponse = {
  status: string;
  engine: string;
  dataMode: string;
  durationMs: number;
  rowCount: number;
  coverage: QuantDuckDBFactorCoverageSummary;
  factorDates: string[];
  missingSymbols: string[];
  insufficientSymbols: string[];
  warnings: string[];
  error?: string | null;
};

export type QuantDuckDBCompareRuntimeContextResponse = {
  status: string;
  engine: string;
  dataMode: string;
  durationMs: number;
  runtimeContexts: string[];
  coverage: QuantDuckDBFactorCoverageSummary;
  diagnostics: {
    productionRuntimeChanged?: boolean;
    diagnosticOnly?: boolean;
    missingSymbols?: string[];
    insufficientSymbols?: string[];
    scannerSymbols?: string[];
    backtestSymbols?: string[];
    [key: string]: unknown;
  };
  snapshots: QuantDuckDBFactorSnapshotRow[];
  warnings: string[];
  error?: string | null;
};

export type QuantDuckDBInitResponse = {
  status: string;
  engine: string;
  version?: string | null;
  error?: string | null;
  schemaInitialized: boolean;
};

export type QuantDuckDBBuildFactorsResponse = {
  status: string;
  engine: string;
  ohlcvRows: number;
  factorRows: number;
  factorCount: number;
  durationMs: number;
  error?: string | null;
};

export type QuantFactorResearchBoundary = {
  purpose: string;
  researchOnly: boolean;
  diagnosticOnly: boolean;
  suppliedObservationsOnly: boolean;
  portfolioOptimizer: boolean;
  professionalReadinessClaimed: boolean;
  forwardReturnsRequiredForPerformance: boolean;
  externalDataHydrationExecuted: boolean;
  liveQuoteHydrationExecuted: boolean;
  forwardReturnsComputed: boolean;
};

export type QuantFactorResearchWindow = {
  asOfStart?: string | null;
  asOfEnd?: string | null;
  asOfCount: number;
  observationCount: number;
};

export type QuantFactorResearchCoverageItem = {
  factorId: string;
  observationCount: number;
  symbolCount: number;
  window: QuantFactorResearchWindow;
};

export type QuantFactorResearchMetricEstimate = {
  horizon?: string | null;
  value?: number | null;
  sampleSize: number;
  insufficientReason?: string | null;
};

export type QuantFactorResearchDecayPoint = {
  horizon: string;
  icValue?: number | null;
  decayRatio?: number | null;
  sampleSize: number;
  insufficientReason?: string | null;
};

export type QuantFactorResearchPeerCorrelation = {
  peerFactorId: string;
  value?: number | null;
  sampleSize: number;
  insufficientReason?: string | null;
};

export type QuantFactorResearchMetricsSummary = {
  factorId: string;
  window: QuantFactorResearchWindow;
  ic: QuantFactorResearchMetricEstimate[];
  rankIc: QuantFactorResearchMetricEstimate[];
  decay: QuantFactorResearchDecayPoint[];
  turnover: QuantFactorResearchMetricEstimate;
  factorCorrelation: QuantFactorResearchPeerCorrelation[];
};

export type QuantFactorResearchNeutralizationSummary = {
  factorId: string;
  axis: string;
  neutralizationMethod: string;
  sampleSize: number;
  totalObservations: number;
  neutralizedObservations: number;
  missingGroupMetadata: number;
  insufficientGroupObservations: number;
  invalidObservationValues: number;
  warnings: string[];
};

export type QuantFactorResearchExposureSummary = {
  scope: string;
  factorId: string;
  exposure?: number | null;
  weightedExposure: number;
  grossExposure: number;
  netExposure: number;
  sampleSize: number;
  coverage: number;
  missingFactorCount: number;
  window: QuantFactorResearchWindow;
  warnings: string[];
  longExposure?: number | null;
  shortExposure?: number | null;
};

export type QuantFactorResearchMissingDataReason = {
  section: string;
  reason: string;
  factorId?: string | null;
  context?: string | null;
};

export type QuantFactorResearchReportBody = {
  window: QuantFactorResearchWindow;
  factorCoverage: QuantFactorResearchCoverageItem[];
  metricsSummary: QuantFactorResearchMetricsSummary[];
  neutralizationSummary: QuantFactorResearchNeutralizationSummary[];
  exposureSummary: QuantFactorResearchExposureSummary[];
  missingDataReasons: QuantFactorResearchMissingDataReason[];
  warnings: string[];
};

export type QuantFactorResearchRegistryMetadata = {
  factorId: string;
  registryState: string;
  label?: string | null;
  description?: string | null;
  family?: string | null;
  direction?: string | null;
  unit?: string | null;
  defaultLookbackDays?: number | null;
  expectedRangeMin?: number | null;
  expectedRangeMax?: number | null;
  tags?: string[];
  neutralization?: Record<string, unknown> | null;
  [key: string]: unknown;
};

export type QuantFactorResearchInputShape = {
  observationCount: number;
  metricObservationCount: number;
  forwardReturnObservationCount: number;
  factorCount: number;
  factorIds: string[];
  symbolCount: number;
  symbols: string[];
  asOfStart?: string | null;
  asOfEnd?: string | null;
  asOfCount: number;
  forwardReturnHorizons: string[];
  portfolioWeightCount: number;
  longWeightCount: number;
  shortWeightCount: number;
  neutralizationAxes: string[];
  minGroupSize: number;
  marketCapBucketCount: number;
  hashAlgorithm: string;
  inputContentHash: string;
};

export type QuantFactorResearchReportRequest = {
  observations: Array<Record<string, unknown>>;
  metricObservations: Array<Record<string, unknown>>;
  portfolioWeights?: Array<Record<string, unknown>> | null;
  longWeights?: Array<Record<string, unknown>> | null;
  shortWeights?: Array<Record<string, unknown>> | null;
  neutralizationAxes?: string[];
  minGroupSize?: number;
  marketCapBucketCount?: number;
};

export type QuantFactorResearchReportResponse = {
  status: string;
  boundary: QuantFactorResearchBoundary;
  factorMetadata: QuantFactorResearchRegistryMetadata[];
  inputShape: QuantFactorResearchInputShape;
  report: QuantFactorResearchReportBody;
  missingDataReasons: QuantFactorResearchMissingDataReason[];
  warnings: string[];
};

export type QuantDuckDBBenchmarkRequest = {
  symbolLimit?: number;
  startDate?: string;
  endDate?: string;
};

export type QuantDuckDBFactorSnapshotRequest = {
  symbols: string[];
  asOfDate?: string;
  lookbackDays?: number;
  factors?: string[];
};

export type QuantDuckDBValidateFactorPathRequest = {
  symbols: string[];
  startDate?: string;
  endDate?: string;
  minFactorRows?: number;
};

export type QuantDuckDBCompareRuntimeContextRequest = {
  symbols: string[];
  scannerSnapshot?: Record<string, unknown>;
  backtestSnapshot?: Record<string, unknown>;
  dateRange?: {
    startDate?: string;
    endDate?: string;
  };
};

export type QuantDuckDBBuildFactorsRequest = {
  symbols: string[];
  startDate?: string;
  endDate?: string;
};

function withoutEmptyValues(payload: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => {
      if (value == null) return false;
      if (typeof value === 'string') return value.trim().length > 0;
      if (Array.isArray(value)) return value.length > 0;
      return true;
    }),
  );
}

export const quantApi = {
  async getDuckDBHealth(): Promise<QuantDuckDBHealthResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/quant/duckdb/health');
    return toCamelCase<QuantDuckDBHealthResponse>(response.data);
  },

  async getDuckDBCoverage(): Promise<QuantDuckDBCoverageResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/quant/duckdb/coverage');
    return toCamelCase<QuantDuckDBCoverageResponse>(response.data);
  },

  async initDuckDB(): Promise<QuantDuckDBInitResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/quant/duckdb/init', {});
    return toCamelCase<QuantDuckDBInitResponse>(response.data);
  },

  async runDuckDBBenchmark(payload: QuantDuckDBBenchmarkRequest = {}): Promise<QuantDuckDBBenchmarkResponse> {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/quant/duckdb/benchmark',
      withoutEmptyValues({
        symbolLimit: payload.symbolLimit,
        startDate: payload.startDate,
        endDate: payload.endDate,
      }),
    );
    return toCamelCase<QuantDuckDBBenchmarkResponse>(response.data);
  },

  async getDuckDBFactorSnapshot(payload: QuantDuckDBFactorSnapshotRequest): Promise<QuantDuckDBFactorSnapshotResponse> {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/quant/duckdb/factor-snapshot',
      withoutEmptyValues({
        symbols: payload.symbols,
        asOfDate: payload.asOfDate,
        lookbackDays: payload.lookbackDays,
        factors: payload.factors,
      }),
    );
    return toCamelCase<QuantDuckDBFactorSnapshotResponse>(response.data);
  },

  async validateDuckDBFactorPath(payload: QuantDuckDBValidateFactorPathRequest): Promise<QuantDuckDBValidateFactorPathResponse> {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/quant/duckdb/validate-factor-path',
      withoutEmptyValues({
        symbols: payload.symbols,
        startDate: payload.startDate,
        endDate: payload.endDate,
        minFactorRows: payload.minFactorRows,
      }),
    );
    return toCamelCase<QuantDuckDBValidateFactorPathResponse>(response.data);
  },

  async compareDuckDBRuntimeContext(
    payload: QuantDuckDBCompareRuntimeContextRequest,
  ): Promise<QuantDuckDBCompareRuntimeContextResponse> {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/quant/duckdb/compare-runtime-context',
      withoutEmptyValues({
        symbols: payload.symbols,
        scannerSnapshot: payload.scannerSnapshot,
        backtestSnapshot: payload.backtestSnapshot,
        dateRange: payload.dateRange,
      }),
    );
    return toCamelCase<QuantDuckDBCompareRuntimeContextResponse>(response.data);
  },

  async buildDuckDBFactors(payload: QuantDuckDBBuildFactorsRequest): Promise<QuantDuckDBBuildFactorsResponse> {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/quant/duckdb/build-factors',
      withoutEmptyValues({
        symbols: payload.symbols,
        startDate: payload.startDate,
        endDate: payload.endDate,
      }),
    );
    return toCamelCase<QuantDuckDBBuildFactorsResponse>(response.data);
  },

  async buildFactorResearchReport(payload: QuantFactorResearchReportRequest): Promise<QuantFactorResearchReportResponse> {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/quant/factor-research/report',
      withoutEmptyValues({
        observations: payload.observations,
        metricObservations: payload.metricObservations,
        portfolioWeights: payload.portfolioWeights,
        longWeights: payload.longWeights,
        shortWeights: payload.shortWeights,
        neutralizationAxes: payload.neutralizationAxes,
        minGroupSize: payload.minGroupSize,
        marketCapBucketCount: payload.marketCapBucketCount,
      }),
    );
    return toCamelCase<QuantFactorResearchReportResponse>(response.data);
  },
};
