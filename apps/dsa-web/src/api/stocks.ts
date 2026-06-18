import apiClient from './index';
import { toCamelCase } from './utils';

export type ExtractItem = {
  code?: string | null;
  name?: string | null;
  confidence: string;
};

export type ExtractFromImageResponse = {
  codes: string[];
  items?: ExtractItem[];
  rawText?: string;
};

export type StockHistoryPoint = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
  amount?: number | null;
  changePercent?: number | null;
};

export type StockHistoryProviderTraceItem = {
  sequence?: number | null;
  provider?: string | null;
  action?: string | null;
  outcome?: string | null;
  status?: string | null;
  reason?: string | null;
  message?: string | null;
};

export type StockHistoryLocalFallback = {
  source?: string | null;
  rows?: number | null;
  latestTradeDate?: string | null;
  dataSources?: string[] | null;
};

export type StockHistoryDiagnostics = {
  status?: string | null;
  reason?: string | null;
  message?: string | null;
  source?: string | null;
  rows?: number | null;
  requestedDays?: number | null;
  providerTrace?: StockHistoryProviderTraceItem[] | null;
  localFallback?: StockHistoryLocalFallback | null;
  error?: string | null;
};

export type StockHistorySourceConfidence = {
  source?: string | null;
  sourceLabel?: string | null;
  asOf?: string | null;
  freshness?: string | null;
  isFallback?: boolean;
  isStale?: boolean;
  isPartial?: boolean;
  isSynthetic?: boolean;
  isUnavailable?: boolean;
  confidenceWeight?: number | null;
  coverage?: number | null;
  degradationReason?: string | null;
  capReason?: string | null;
};

export type StockHistoryResponse = {
  stockCode: string;
  stockName?: string | null;
  period: 'daily' | 'weekly' | 'monthly' | 'yearly' | string;
  source?: string | null;
  diagnostics?: StockHistoryDiagnostics | null;
  sourceConfidence?: StockHistorySourceConfidence | null;
  data: StockHistoryPoint[];
};

export type StockIntradayPoint = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
};

export type StockIntradayResponse = {
  stockCode: string;
  stockName?: string | null;
  interval: string;
  range: string;
  source?: string | null;
  data: StockIntradayPoint[];
};

export type StockValidationResponse = {
  stockCode: string;
  normalizedSymbol?: string | null;
  market?: string | null;
  status?: 'valid' | 'invalid_format' | 'unsupported_market' | 'ambiguous' | 'not_found' | 'unavailable' | 'unknown' | string;
  valid?: boolean;
  exists: boolean;
  stockName?: string | null;
  message?: string;
};

export type StockStructureDecisionKeyLevel = {
  kind?: string | null;
  value?: number | null;
  description?: string | null;
};

export type StockPeerCorrelationState = 'aligned' | 'diverging' | 'insufficient_evidence';

export type StockPeerCorrelationConfidenceCap = 'low' | 'medium' | 'high';

export type StockPeerCorrelationPeerGroup = {
  status: 'available' | 'unavailable';
  label?: string | null;
  symbols: string[];
};

export type StockPeerCorrelationEvidence = {
  symbol: string;
  correlation?: number | null;
  overlapDays: number;
  symbolReturnPct?: number | null;
  peerReturnPct?: number | null;
  spreadPct?: number | null;
  state: StockPeerCorrelationState;
  summary: string;
};

export type StockPeerCorrelationSnapshot = {
  symbol: string;
  peerGroup: StockPeerCorrelationPeerGroup;
  correlationState: StockPeerCorrelationState;
  peerEvidence: StockPeerCorrelationEvidence[];
  divergenceEvidence: StockPeerCorrelationEvidence[];
  staleInputs: string[];
  missingInputs: string[];
  confidenceCap: StockPeerCorrelationConfidenceCap;
  observationBoundary: string;
  researchNextSteps: string[];
};

export type StockStructureDecisionMissingEvidence = {
  kind?: string | null;
  code?: string | null;
  field?: string | null;
  message?: string | null;
};

export type StockStructureConfidenceCap = {
  value?: number | null;
  label?: string | null;
  reasons: string[];
};

export type StockStructureConfidenceState = {
  status?: string | null;
  label?: string | null;
  reasons: string[];
  freshnessConstrained?: boolean | null;
  sourceQualityLimited?: boolean | null;
  thesisBlocked?: boolean | null;
};

export type StockStructureDecisionResponse = {
  schemaVersion: string;
  ticker: string;
  structureState: string;
  confidence: string;
  confidenceCap?: StockStructureConfidenceCap | null;
  confidenceState?: StockStructureConfidenceState | null;
  componentScores: Record<string, number>;
  explanation: {
    whyThisStructure?: string | null;
    whatConfirmsIt?: string[];
    whatInvalidatesIt?: string[];
    keyLevels?: StockStructureDecisionKeyLevel[];
  };
  researchNotes: {
    watchNext?: string[];
    needsMoreEvidence?: string[];
    riskFlags?: string[];
  };
  dataQuality: {
    status?: string | null;
    source?: string | null;
    period?: string | null;
    requestedDays?: number | null;
    observedBars?: number | null;
    usableBars?: number | null;
    reason?: string | null;
  };
  missingEvidence: StockStructureDecisionMissingEvidence[];
  peerCorrelationSnapshot?: StockPeerCorrelationSnapshot;
  noAdviceDisclosure: string;
};

export type StockStructureDecisionBatchRequest = {
  stockCodes: string[];
  benchmark?: string;
  maxItems?: number;
};

export type StockSymbolCompareEvidenceEntry = {
  kind?: string | null;
  symbols?: string[] | null;
  status?: string | null;
  period?: string | null;
  usableBarsMin?: number | null;
  usableBarsMax?: number | null;
  benchmark?: string | null;
  values?: Record<string, string | number | null | undefined> | null;
  [key: string]: unknown;
};

export type StockSymbolCompareFreshness = {
  status?: string | null;
  period?: string | null;
  usableBars?: number | null;
  [key: string]: unknown;
};

export type StockSymbolCompareEvidencePacket = {
  comparedSymbols: string[];
  sharedEvidence: StockSymbolCompareEvidenceEntry[];
  divergentEvidence: StockSymbolCompareEvidenceEntry[];
  missingEvidenceBySymbol: Record<string, StockStructureDecisionMissingEvidence[]>;
  freshnessBySymbol: Record<string, StockSymbolCompareFreshness>;
  confidenceCap: {
    value?: number | null;
    [key: string]: unknown;
  };
  observationBoundary: {
    observationOnly?: boolean | null;
    decisionGrade?: boolean | null;
    rankingAllowed?: boolean | null;
    adviceAllowed?: boolean | null;
  };
  researchNextSteps: string[];
};

export type StockStructureDecisionBatchResponse = {
  schemaVersion: string;
  items: Array<StockStructureDecisionResponse & {
    comparativeContext?: Record<string, unknown> | null;
  }>;
  aggregateSummary: Record<string, unknown>;
  missingEvidence: StockStructureDecisionMissingEvidence[];
  dataQuality: Record<string, unknown>;
  symbolCompareEvidencePacket?: StockSymbolCompareEvidencePacket | null;
  noAdviceDisclosure: string;
};

export type StockQuoteSourceConfidence = {
  source?: string | null;
  sourceLabel?: string | null;
  asOf?: string | null;
  freshness?: string | null;
  isFallback?: boolean;
  isStale?: boolean;
  isPartial?: boolean;
  isSynthetic?: boolean;
  isUnavailable?: boolean;
  confidenceWeight?: number | null;
  coverage?: number | null;
  degradationReason?: string | null;
  capReason?: string | null;
};

export type StockQuote = {
  stockCode: string;
  stockName?: string | null;
  currentPrice: number;
  change?: number | null;
  changePercent?: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  prevClose?: number | null;
  volume?: number | null;
  amount?: number | null;
  updateTime?: string | null;
  update_time?: string | null;
  source?: string | null;
  sourceType?: string | null;
  marketTimestamp?: string | null;
  observedAt?: string | null;
  freshness?: string | null;
  isFallback?: boolean;
  isStale?: boolean;
  isPartial?: boolean;
  isSynthetic?: boolean;
  sourceConfidence?: StockQuoteSourceConfidence | null;
};

function normalizeStockQuoteResponse(payload: unknown): StockQuote {
  const normalized = toCamelCase<StockQuote>(payload);
  const raw = (payload ?? {}) as { update_time?: string | null };
  const updateTime = normalized.updateTime ?? raw.update_time ?? null;

  return {
    stockCode: normalized.stockCode,
    stockName: normalized.stockName ?? null,
    currentPrice: normalized.currentPrice,
    change: normalized.change ?? null,
    changePercent: normalized.changePercent ?? null,
    open: normalized.open ?? null,
    high: normalized.high ?? null,
    low: normalized.low ?? null,
    prevClose: normalized.prevClose ?? null,
    volume: normalized.volume ?? null,
    amount: normalized.amount ?? null,
    updateTime,
    update_time: updateTime,
    source: normalized.source ?? null,
    sourceType: normalized.sourceType ?? null,
    marketTimestamp: normalized.marketTimestamp ?? null,
    observedAt: normalized.observedAt ?? null,
    freshness: normalized.freshness ?? null,
    isFallback: normalized.isFallback,
    isStale: normalized.isStale,
    isPartial: normalized.isPartial,
    isSynthetic: normalized.isSynthetic,
    sourceConfidence: normalized.sourceConfidence ?? null,
  };
}

function normalizeStockHistoryResponse(payload: unknown): StockHistoryResponse {
  const normalized = toCamelCase<StockHistoryResponse>(payload);
  return {
    stockCode: normalized.stockCode,
    stockName: normalized.stockName ?? null,
    period: normalized.period,
    source: normalized.source ?? null,
    diagnostics: normalized.diagnostics ?? null,
    sourceConfidence: normalized.sourceConfidence ?? null,
    data: Array.isArray(normalized.data) ? normalized.data : [],
  };
}

function normalizeStockIntradayResponse(payload: unknown): StockIntradayResponse {
  const normalized = toCamelCase<StockIntradayResponse>(payload);
  return {
    stockCode: normalized.stockCode,
    stockName: normalized.stockName ?? null,
    interval: normalized.interval,
    range: normalized.range,
    source: normalized.source ?? null,
    data: Array.isArray(normalized.data) ? normalized.data : [],
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function normalizeStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : [];
}

function normalizePeerCorrelationState(value: unknown): StockPeerCorrelationState | null {
  return value === 'aligned' || value === 'diverging' || value === 'insufficient_evidence'
    ? value
    : null;
}

function normalizePeerCorrelationConfidenceCap(value: unknown): StockPeerCorrelationConfidenceCap | null {
  return value === 'low' || value === 'medium' || value === 'high' ? value : null;
}

function normalizeOptionalNumber(value: unknown): number | null | undefined {
  if (value === null) return null;
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function assignOptionalNumber<TKey extends keyof StockPeerCorrelationEvidence>(
  target: StockPeerCorrelationEvidence,
  key: TKey,
  value: unknown,
): void {
  const normalized = normalizeOptionalNumber(value);
  if (normalized !== undefined) {
    target[key] = normalized as StockPeerCorrelationEvidence[TKey];
  }
}

function normalizePeerCorrelationPeerGroup(value: unknown): StockPeerCorrelationPeerGroup | null {
  if (!isRecord(value) || (value.status !== 'available' && value.status !== 'unavailable')) {
    return null;
  }

  const group: StockPeerCorrelationPeerGroup = {
    status: value.status,
    symbols: normalizeStringArray(value.symbols),
  };
  if (typeof value.label === 'string' || value.label === null) {
    group.label = value.label;
  }
  return group;
}

function normalizePeerCorrelationEvidenceItem(value: unknown): StockPeerCorrelationEvidence | null {
  if (!isRecord(value)) {
    return null;
  }

  const symbol = typeof value.symbol === 'string' ? value.symbol.trim() : '';
  const state = normalizePeerCorrelationState(value.state);
  const summary = typeof value.summary === 'string' ? value.summary.trim() : '';
  const overlapDays = typeof value.overlapDays === 'number' && Number.isFinite(value.overlapDays)
    ? value.overlapDays
    : null;
  if (!symbol || !state || !summary || overlapDays === null) {
    return null;
  }

  const evidence: StockPeerCorrelationEvidence = {
    symbol,
    overlapDays,
    state,
    summary,
  };
  assignOptionalNumber(evidence, 'correlation', value.correlation);
  assignOptionalNumber(evidence, 'symbolReturnPct', value.symbolReturnPct);
  assignOptionalNumber(evidence, 'peerReturnPct', value.peerReturnPct);
  assignOptionalNumber(evidence, 'spreadPct', value.spreadPct);
  return evidence;
}

function normalizePeerCorrelationEvidenceList(value: unknown): StockPeerCorrelationEvidence[] {
  return Array.isArray(value)
    ? value
      .map((item) => normalizePeerCorrelationEvidenceItem(item))
      .filter((item): item is StockPeerCorrelationEvidence => Boolean(item))
    : [];
}

export function normalizePeerCorrelationSnapshot(value: unknown): StockPeerCorrelationSnapshot | undefined {
  if (!isRecord(value)) {
    return undefined;
  }

  const symbol = typeof value.symbol === 'string' ? value.symbol.trim() : '';
  const peerGroup = normalizePeerCorrelationPeerGroup(value.peerGroup);
  const correlationState = normalizePeerCorrelationState(value.correlationState);
  const confidenceCap = normalizePeerCorrelationConfidenceCap(value.confidenceCap);
  const observationBoundary = typeof value.observationBoundary === 'string' ? value.observationBoundary.trim() : '';
  if (!symbol || !peerGroup || !correlationState || !confidenceCap || !observationBoundary) {
    return undefined;
  }

  return {
    symbol,
    peerGroup,
    correlationState,
    peerEvidence: normalizePeerCorrelationEvidenceList(value.peerEvidence),
    divergenceEvidence: normalizePeerCorrelationEvidenceList(value.divergenceEvidence),
    staleInputs: normalizeStringArray(value.staleInputs),
    missingInputs: normalizeStringArray(value.missingInputs),
    confidenceCap,
    observationBoundary,
    researchNextSteps: normalizeStringArray(value.researchNextSteps),
  };
}

function normalizeStockStructureDecisionResponse(payload: unknown): StockStructureDecisionResponse {
  const normalized = toCamelCase<StockStructureDecisionResponse>(payload);
  return {
    schemaVersion: normalized.schemaVersion,
    ticker: normalized.ticker,
    structureState: normalized.structureState,
    confidence: normalized.confidence,
    confidenceCap: normalizeStockStructureConfidenceCap(normalized.confidenceCap),
    confidenceState: normalizeStockStructureConfidenceState(normalized.confidenceState),
    componentScores: normalized.componentScores ?? {},
    explanation: {
      whyThisStructure: normalized.explanation?.whyThisStructure ?? null,
      whatConfirmsIt: normalized.explanation?.whatConfirmsIt ?? [],
      whatInvalidatesIt: normalized.explanation?.whatInvalidatesIt ?? [],
      keyLevels: normalized.explanation?.keyLevels ?? [],
    },
    researchNotes: {
      watchNext: normalized.researchNotes?.watchNext ?? [],
      needsMoreEvidence: normalized.researchNotes?.needsMoreEvidence ?? [],
      riskFlags: normalized.researchNotes?.riskFlags ?? [],
    },
    dataQuality: {
      status: normalized.dataQuality?.status ?? null,
      source: normalized.dataQuality?.source ?? null,
      period: normalized.dataQuality?.period ?? null,
      requestedDays: normalized.dataQuality?.requestedDays ?? null,
      observedBars: normalized.dataQuality?.observedBars ?? null,
      usableBars: normalized.dataQuality?.usableBars ?? null,
      reason: normalized.dataQuality?.reason ?? null,
    },
    missingEvidence: normalized.missingEvidence ?? [],
    peerCorrelationSnapshot: normalizePeerCorrelationSnapshot(normalized.peerCorrelationSnapshot),
    noAdviceDisclosure: normalized.noAdviceDisclosure,
  };
}

function normalizeStockStructureConfidenceCap(value: unknown): StockStructureConfidenceCap | null {
  if (!isRecord(value)) return null;
  return {
    value: numberField(value, ['value']),
    label: stringField(value, ['label']),
    reasons: stringArrayField(value, ['reasons', 'reasonCodes', 'reason_codes']),
  };
}

function normalizeStockStructureConfidenceState(value: unknown): StockStructureConfidenceState | null {
  if (!isRecord(value)) return null;
  return {
    status: stringField(value, ['status']),
    label: stringField(value, ['label']),
    reasons: stringArrayField(value, ['reasons', 'reasonCodes', 'reason_codes']),
    freshnessConstrained: booleanField(value, ['freshnessConstrained', 'freshness_constrained']),
    sourceQualityLimited: booleanField(value, ['sourceQualityLimited', 'source_quality_limited']),
    thesisBlocked: booleanField(value, ['thesisBlocked', 'thesis_blocked']),
  };
}

function firstField(record: Record<string, unknown>, keys: string[]): unknown {
  for (const key of keys) {
    if (key in record) return record[key];
  }
  return undefined;
}

function stringField(record: Record<string, unknown>, keys: string[]): string | null {
  const value = firstField(record, keys);
  return typeof value === 'string' ? value : null;
}

function numberField(record: Record<string, unknown>, keys: string[]): number | null {
  const value = firstField(record, keys);
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function booleanField(record: Record<string, unknown>, keys: string[]): boolean | null {
  const value = firstField(record, keys);
  return typeof value === 'boolean' ? value : null;
}

function stringArrayField(record: Record<string, unknown>, keys: string[]): string[] {
  const value = firstField(record, keys);
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && item.length > 0) : [];
}

function normalizeMissingEvidence(value: unknown): StockStructureDecisionMissingEvidence {
  const record = isRecord(value) ? value : {};
  return {
    kind: stringField(record, ['kind']),
    code: stringField(record, ['code']),
    field: stringField(record, ['field']),
    message: stringField(record, ['message']),
  };
}

function normalizeCompareEvidenceEntry(value: unknown): StockSymbolCompareEvidenceEntry {
  const record = isRecord(value) ? value : {};
  const rawValues = firstField(record, ['values']);
  const values = isRecord(rawValues)
    ? Object.fromEntries(
      Object.entries(rawValues).map(([symbol, item]) => [
        symbol,
        typeof item === 'string' || typeof item === 'number' || item === null ? item : String(item ?? ''),
      ]),
    )
    : null;
  return {
    kind: stringField(record, ['kind']),
    symbols: stringArrayField(record, ['symbols']),
    status: stringField(record, ['status']),
    period: stringField(record, ['period']),
    usableBarsMin: numberField(record, ['usableBarsMin', 'usable_bars_min']),
    usableBarsMax: numberField(record, ['usableBarsMax', 'usable_bars_max']),
    benchmark: stringField(record, ['benchmark']),
    values,
  };
}

function normalizeMissingEvidenceBySymbol(value: unknown): Record<string, StockStructureDecisionMissingEvidence[]> {
  if (!isRecord(value)) return {};
  return Object.fromEntries(
    Object.entries(value).map(([symbol, entries]) => [
      symbol,
      Array.isArray(entries) ? entries.map(normalizeMissingEvidence) : [],
    ]),
  );
}

function normalizeFreshnessBySymbol(value: unknown): Record<string, StockSymbolCompareFreshness> {
  if (!isRecord(value)) return {};
  return Object.fromEntries(
    Object.entries(value).map(([symbol, item]) => {
      const record = isRecord(item) ? item : {};
      return [
        symbol,
        {
          status: stringField(record, ['status']),
          period: stringField(record, ['period']),
          usableBars: numberField(record, ['usableBars', 'usable_bars']),
        },
      ];
    }),
  );
}

function normalizeSymbolCompareEvidencePacket(payload: unknown): StockSymbolCompareEvidencePacket | null {
  if (!isRecord(payload)) return null;
  const rawSharedEvidence = firstField(payload, ['sharedEvidence', 'shared_evidence']);
  const rawDivergentEvidence = firstField(payload, ['divergentEvidence', 'divergent_evidence']);
  const rawConfidenceCap = firstField(payload, ['confidenceCap', 'confidence_cap']);
  const confidenceCapRecord = isRecord(rawConfidenceCap) ? rawConfidenceCap : {};
  const rawObservationBoundary = firstField(payload, ['observationBoundary', 'observation_boundary']);
  const observationBoundaryRecord = isRecord(rawObservationBoundary) ? rawObservationBoundary : {};
  return {
    comparedSymbols: stringArrayField(payload, ['comparedSymbols', 'compared_symbols']),
    sharedEvidence: Array.isArray(rawSharedEvidence) ? rawSharedEvidence.map(normalizeCompareEvidenceEntry) : [],
    divergentEvidence: Array.isArray(rawDivergentEvidence) ? rawDivergentEvidence.map(normalizeCompareEvidenceEntry) : [],
    missingEvidenceBySymbol: normalizeMissingEvidenceBySymbol(firstField(payload, ['missingEvidenceBySymbol', 'missing_evidence_by_symbol'])),
    freshnessBySymbol: normalizeFreshnessBySymbol(firstField(payload, ['freshnessBySymbol', 'freshness_by_symbol'])),
    confidenceCap: {
      value: numberField(confidenceCapRecord, ['value']),
    },
    observationBoundary: {
      observationOnly: booleanField(observationBoundaryRecord, ['observationOnly', 'observation_only']),
      decisionGrade: booleanField(observationBoundaryRecord, ['decisionGrade', 'decision_grade']),
      rankingAllowed: booleanField(observationBoundaryRecord, ['rankingAllowed', 'ranking_allowed']),
      adviceAllowed: booleanField(observationBoundaryRecord, ['adviceAllowed', 'advice_allowed']),
    },
    researchNextSteps: stringArrayField(payload, ['researchNextSteps', 'research_next_steps']),
  };
}

function normalizeStockStructureDecisionBatchResponse(payload: unknown): StockStructureDecisionBatchResponse {
  const normalized = toCamelCase<StockStructureDecisionBatchResponse>(payload);
  const raw = isRecord(payload) ? payload : {};
  return {
    schemaVersion: normalized.schemaVersion,
    items: Array.isArray(normalized.items)
      ? normalized.items.map((item) => ({
        ...normalizeStockStructureDecisionResponse(item),
        comparativeContext: item.comparativeContext ?? null,
      }))
      : [],
    aggregateSummary: normalized.aggregateSummary ?? {},
    missingEvidence: normalized.missingEvidence ?? [],
    dataQuality: normalized.dataQuality ?? {},
    symbolCompareEvidencePacket: normalizeSymbolCompareEvidencePacket(firstField(raw, ['symbolCompareEvidencePacket', 'symbol_compare_evidence_packet'])),
    noAdviceDisclosure: normalized.noAdviceDisclosure,
  };
}

export const stocksApi = {
  async verifyTickerExists(stockCode: string): Promise<StockValidationResponse> {
    const response = await apiClient.get(`/api/v1/stocks/${encodeURIComponent(stockCode)}/validate`);
    return toCamelCase<StockValidationResponse>(response.data);
  },

  async getQuote(stockCode: string): Promise<StockQuote> {
    const response = await apiClient.get(`/api/v1/stocks/${encodeURIComponent(stockCode)}/quote`);
    return normalizeStockQuoteResponse(response.data);
  },

  async getStructureDecision(stockCode: string): Promise<StockStructureDecisionResponse> {
    const response = await apiClient.get(`/api/v1/stocks/${encodeURIComponent(stockCode)}/structure-decision`);
    return normalizeStockStructureDecisionResponse(response.data);
  },

  async getStructureDecisionsBatch(params: StockStructureDecisionBatchRequest): Promise<StockStructureDecisionBatchResponse> {
    const payload = {
      stockCodes: params.stockCodes,
      benchmark: params.benchmark,
      maxItems: params.maxItems,
    };
    const response = await apiClient.post('/api/v1/stocks/structure-decisions/batch', payload);
    return normalizeStockStructureDecisionBatchResponse(response.data);
  },

  async getHistory(
    stockCode: string,
    params: {
      period?: 'daily' | 'weekly' | 'monthly' | 'yearly';
      days?: number;
    } = {},
  ): Promise<StockHistoryResponse> {
    const response = await apiClient.get(`/api/v1/stocks/${encodeURIComponent(stockCode)}/history`, {
      params,
    });
    return normalizeStockHistoryResponse(response.data);
  },

  async getIntraday(
    stockCode: string,
    params: {
      interval?: '1m' | '2m' | '5m' | '15m' | '30m' | '60m' | '90m';
      range?: '1d' | '5d' | '1mo';
    } = {},
  ): Promise<StockIntradayResponse> {
    const response = await apiClient.get(`/api/v1/stocks/${encodeURIComponent(stockCode)}/intraday`, {
      params,
    });
    return normalizeStockIntradayResponse(response.data);
  },

  async extractFromImage(file: File): Promise<ExtractFromImageResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const headers: { [key: string]: string | undefined } = { 'Content-Type': undefined };
    const response = await apiClient.post(
      '/api/v1/stocks/extract-from-image',
      formData,
      {
        headers,
        timeout: 60000, // Vision API can be slow; 60s
      },
    );

    const data = response.data as { codes?: string[]; items?: ExtractItem[]; raw_text?: string };
    return {
      codes: data.codes ?? [],
      items: data.items,
      rawText: data.raw_text,
    };
  },

  async parseImport(file?: File, text?: string): Promise<ExtractFromImageResponse> {
    if (file) {
      const formData = new FormData();
      formData.append('file', file);
      const headers: { [key: string]: string | undefined } = { 'Content-Type': undefined };
      const response = await apiClient.post('/api/v1/stocks/parse-import', formData, { headers });
      const data = response.data as { codes?: string[]; items?: ExtractItem[] };
      return { codes: data.codes ?? [], items: data.items };
    }
    if (text) {
      const response = await apiClient.post('/api/v1/stocks/parse-import', { text });
      const data = response.data as { codes?: string[]; items?: ExtractItem[] };
      return { codes: data.codes ?? [], items: data.items };
    }
    throw new Error('请提供文件或粘贴文本');
  },
};
