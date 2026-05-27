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
  exists: boolean;
  stockName?: string | null;
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

export const stocksApi = {
  async verifyTickerExists(stockCode: string): Promise<StockValidationResponse> {
    const response = await apiClient.get(`/api/v1/stocks/${encodeURIComponent(stockCode)}/validate`);
    return toCamelCase<StockValidationResponse>(response.data);
  },

  async getQuote(stockCode: string): Promise<StockQuote> {
    const response = await apiClient.get(`/api/v1/stocks/${encodeURIComponent(stockCode)}/quote`);
    return normalizeStockQuoteResponse(response.data);
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
