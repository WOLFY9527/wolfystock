import apiClient from './index';
import { normalizePeerCorrelationSnapshot } from './stocks';
import { toCamelCase } from './utils';
import type { ProductReadModel } from '../types/productReadModel';
import type {
  SymbolEvidenceReadiness,
  SymbolEvidenceReadinessTier,
  StockEvidenceFundamentalsSummary,
  StockEvidenceItem,
  StockEvidenceMeta,
  StockEvidencePacket,
  StockEvidenceResponse,
} from '../types/stockEvidence';

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function normalizeStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string' && item.length > 0)
    : [];
}

function assignNumberField<TKey extends keyof StockEvidenceFundamentalsSummary>(
  target: Partial<StockEvidenceFundamentalsSummary>,
  key: TKey,
  value: unknown,
): void {
  if (typeof value === 'number' && Number.isFinite(value)) {
    target[key] = value as StockEvidenceFundamentalsSummary[TKey];
  }
}

function assignStringField<TKey extends keyof StockEvidenceFundamentalsSummary>(
  target: Partial<StockEvidenceFundamentalsSummary>,
  key: TKey,
  value: unknown,
): void {
  if (typeof value === 'string') {
    target[key] = value as StockEvidenceFundamentalsSummary[TKey];
  }
}

function normalizeFundamentalsSummary(payload: unknown): StockEvidenceFundamentalsSummary | undefined {
  if (!isRecord(payload)) {
    return undefined;
  }

  const missingFields = normalizeStringArray(payload.missingFields);
  const hasConsumerSafeField = [
    payload.marketCap,
    payload.peTtm,
    payload.pb,
    payload.beta,
    payload.revenueTtm,
    payload.netIncomeTtm,
    payload.fcfTtm,
    payload.grossMargin,
    payload.operatingMargin,
    payload.roe,
    payload.roa,
    payload.period,
    payload.source,
    payload.freshness,
  ].some((value) => value !== undefined && value !== null)
    || missingFields.length > 0
    || typeof payload.notInvestmentAdvice === 'boolean'
    || typeof payload.observationOnly === 'boolean'
    || typeof payload.scoreContributionAllowed === 'boolean'
    || typeof payload.sourceAuthorityAllowed === 'boolean';

  if (!hasConsumerSafeField) {
    return undefined;
  }

  const normalized: Partial<StockEvidenceFundamentalsSummary> = {
    missingFields,
    notInvestmentAdvice: payload.notInvestmentAdvice !== false,
    observationOnly: payload.observationOnly !== false,
    scoreContributionAllowed: payload.scoreContributionAllowed === true,
    sourceAuthorityAllowed: payload.sourceAuthorityAllowed === true,
  };

  assignNumberField(normalized, 'marketCap', payload.marketCap);
  assignNumberField(normalized, 'peTtm', payload.peTtm);
  assignNumberField(normalized, 'pb', payload.pb);
  assignNumberField(normalized, 'beta', payload.beta);
  assignNumberField(normalized, 'revenueTtm', payload.revenueTtm);
  assignNumberField(normalized, 'netIncomeTtm', payload.netIncomeTtm);
  assignNumberField(normalized, 'fcfTtm', payload.fcfTtm);
  assignNumberField(normalized, 'grossMargin', payload.grossMargin);
  assignNumberField(normalized, 'operatingMargin', payload.operatingMargin);
  assignNumberField(normalized, 'roe', payload.roe);
  assignNumberField(normalized, 'roa', payload.roa);
  assignStringField(normalized, 'period', payload.period);
  assignStringField(normalized, 'source', payload.source);
  assignStringField(normalized, 'freshness', payload.freshness);

  return normalized as StockEvidenceFundamentalsSummary;
}

function normalizeOpaqueObject(payload: unknown): Record<string, unknown> | null | undefined {
  if (payload === null) {
    return null;
  }
  return isRecord(payload) ? payload : undefined;
}

function normalizeProductReadModel(payload: unknown): ProductReadModel | null | undefined {
  if (payload === null) {
    return null;
  }
  if (!isRecord(payload)) {
    return undefined;
  }

  const {
    rawProviderPayload,
    rawPayload,
    providerPayload,
    adminDiagnostics,
    ...safePayload
  } = payload;
  void rawProviderPayload;
  void rawPayload;
  void providerPayload;
  void adminDiagnostics;

  return safePayload as ProductReadModel;
}

function normalizeStockEvidencePacket(payload: unknown): StockEvidencePacket | undefined {
  if (!isRecord(payload)) {
    return undefined;
  }

  const { fundamentalsSummary, peerCorrelationSnapshot, ...rest } = payload;
  const normalizedFundamentalsSummary = normalizeFundamentalsSummary(fundamentalsSummary);
  const normalizedPeerCorrelationSnapshot = normalizePeerCorrelationSnapshot(peerCorrelationSnapshot);

  return {
    ...rest,
    ...(normalizedFundamentalsSummary ? { fundamentalsSummary: normalizedFundamentalsSummary } : {}),
    ...(normalizedPeerCorrelationSnapshot ? { peerCorrelationSnapshot: normalizedPeerCorrelationSnapshot } : {}),
  };
}

function normalizeReadinessTier(value: unknown): SymbolEvidenceReadinessTier | null {
  if (value === 'sufficient' || value === 'partial' || value === 'insufficient') {
    return value;
  }
  return null;
}

function normalizeSymbolEvidenceReadiness(payload: unknown): SymbolEvidenceReadiness | undefined {
  if (!isRecord(payload)) {
    return undefined;
  }

  const readinessTier = normalizeReadinessTier(payload.readinessTier);
  const symbol = typeof payload.symbol === 'string' ? payload.symbol.trim() : '';
  const noAdviceDisclosure = typeof payload.noAdviceDisclosure === 'string'
    ? payload.noAdviceDisclosure.trim()
    : '';

  if (
    payload.symbolEvidenceReadiness !== true
    || !symbol
    || !readinessTier
    || payload.observationOnly !== true
    || !noAdviceDisclosure
  ) {
    return undefined;
  }

  return {
    symbolEvidenceReadiness: true,
    symbol,
    readinessTier,
    evidenceUsed: normalizeStringArray(payload.evidenceUsed),
    evidenceMissing: normalizeStringArray(payload.evidenceMissing),
    staleInputs: normalizeStringArray(payload.staleInputs),
    conflictingEvidence: normalizeStringArray(payload.conflictingEvidence),
    dataQualityNotes: normalizeStringArray(payload.dataQualityNotes),
    suggestedResearchPath: normalizeStringArray(payload.suggestedResearchPath),
    observationOnly: true,
    noAdviceDisclosure,
  };
}

function normalizeStockEvidenceItem(payload: unknown): StockEvidenceItem | null {
  if (!isRecord(payload) || typeof payload.symbol !== 'string' || payload.symbol.length === 0) {
    return null;
  }

  const item: StockEvidenceItem = {
    symbol: payload.symbol,
    market: typeof payload.market === 'string' ? payload.market : payload.market === null ? null : undefined,
    productReadModel: normalizeProductReadModel(payload.productReadModel),
    quote: normalizeOpaqueObject(payload.quote),
    technical: normalizeOpaqueObject(payload.technical),
    fundamental: normalizeOpaqueObject(payload.fundamental),
    news: normalizeOpaqueObject(payload.news),
    secFilingEvidence: normalizeOpaqueObject(payload.secFilingEvidence),
    stockEvidencePacket: normalizeStockEvidencePacket(payload.stockEvidencePacket),
  };

  const symbolEvidenceReadiness = normalizeSymbolEvidenceReadiness(payload.symbolEvidenceReadiness);
  if (symbolEvidenceReadiness) {
    item.symbolEvidenceReadiness = symbolEvidenceReadiness;
  }

  return item;
}

function normalizeStockEvidenceMeta(payload: unknown): StockEvidenceMeta | undefined {
  if (!isRecord(payload)) {
    return undefined;
  }

  return {
    generatedAt: typeof payload.generatedAt === 'string' ? payload.generatedAt : payload.generatedAt === null ? null : undefined,
    source: typeof payload.source === 'string' ? payload.source : payload.source === null ? null : undefined,
  };
}

export function normalizeStockEvidenceResponse(payload: unknown): StockEvidenceResponse {
  const normalized = toCamelCase<Record<string, unknown>>(payload);

  return {
    symbols: Array.isArray(normalized.symbols)
      ? normalized.symbols.filter((item): item is string => typeof item === 'string' && item.length > 0)
      : [],
    items: Array.isArray(normalized.items)
      ? normalized.items
        .map((item) => normalizeStockEvidenceItem(item))
        .filter((item): item is StockEvidenceItem => Boolean(item))
      : [],
    meta: normalizeStockEvidenceMeta(normalized.meta),
  };
}

export const stockEvidenceApi = {
  async getStockEvidence(stockCode: string): Promise<StockEvidenceResponse> {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/stocks/${encodeURIComponent(stockCode)}/evidence`,
    );
    return normalizeStockEvidenceResponse(response.data);
  },
};
