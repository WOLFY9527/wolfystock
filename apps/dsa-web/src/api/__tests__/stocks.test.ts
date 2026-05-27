import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get, post } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
    post,
  },
}));

describe('stocksApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls the quote endpoint and preserves freshness/source metadata', async () => {
    const { stocksApi } = await import('../stocks');

    get.mockResolvedValueOnce({
      data: {
        stock_code: 'AAPL',
        stock_name: 'Apple',
        current_price: 214.55,
        change: 2.35,
        change_percent: 1.11,
        open: 213,
        high: 215,
        low: 212.5,
        prev_close: 212.2,
        volume: 1000,
        amount: 214550,
        update_time: '2026-05-28T09:31:00Z',
        source: 'alpaca',
        source_type: 'provider_runtime',
        market_timestamp: '2026-05-28T09:30:00Z',
        observed_at: '2026-05-28T09:31:00Z',
        freshness: 'live',
        is_fallback: false,
        is_stale: false,
        is_partial: false,
        is_synthetic: false,
        source_confidence: {
          source: 'alpaca',
          source_label: 'Alpaca',
          as_of: '2026-05-28T09:30:00Z',
          freshness: 'live',
          is_fallback: false,
          is_stale: false,
          is_partial: false,
          is_synthetic: false,
          is_unavailable: false,
          confidence_weight: 1,
          coverage: null,
          degradation_reason: null,
          cap_reason: null,
        },
      },
    });

    const quote = await stocksApi.getQuote('AAPL');

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/AAPL/quote');
    expect(quote.stockCode).toBe('AAPL');
    expect(quote.stockName).toBe('Apple');
    expect(quote.source).toBe('alpaca');
    expect(quote.sourceType).toBe('provider_runtime');
    expect(quote.marketTimestamp).toBe('2026-05-28T09:30:00Z');
    expect(quote.observedAt).toBe('2026-05-28T09:31:00Z');
    expect(quote.freshness).toBe('live');
    expect(quote.isFallback).toBe(false);
    expect(quote.isStale).toBe(false);
    expect(quote.isPartial).toBe(false);
    expect(quote.isSynthetic).toBe(false);
    expect(quote.sourceConfidence?.sourceLabel).toBe('Alpaca');
    expect(quote.sourceConfidence?.confidenceWeight).toBe(1);
    expect(quote.updateTime).toBe('2026-05-28T09:31:00Z');
    expect(quote.update_time).toBe('2026-05-28T09:31:00Z');
    expect(quote.update_time).not.toBe(quote.marketTimestamp);
  });

  it('keeps fallback and synthetic flags when quote data is non-fresh', async () => {
    const { stocksApi } = await import('../stocks');

    get.mockResolvedValueOnce({
      data: {
        stock_code: 'AAPL',
        stock_name: '股票AAPL',
        current_price: 0,
        change: null,
        change_percent: null,
        open: null,
        high: null,
        low: null,
        prev_close: null,
        volume: null,
        amount: null,
        update_time: '2026-05-28T09:31:00Z',
        source: 'placeholder',
        source_type: 'synthetic_placeholder',
        market_timestamp: null,
        observed_at: '2026-05-28T09:31:00Z',
        freshness: 'synthetic',
        is_fallback: false,
        is_stale: false,
        is_partial: true,
        is_synthetic: true,
        source_confidence: {
          source: 'placeholder',
          source_label: 'Placeholder',
          as_of: null,
          freshness: 'synthetic',
          is_fallback: false,
          is_stale: false,
          is_partial: true,
          is_synthetic: true,
          is_unavailable: false,
          confidence_weight: 0,
          coverage: null,
          degradation_reason: 'provider_runtime_unavailable_placeholder',
          cap_reason: null,
        },
      },
    });

    const quote = await stocksApi.getQuote('AAPL');

    expect(quote.sourceType).toBe('synthetic_placeholder');
    expect(quote.marketTimestamp).toBeNull();
    expect(quote.observedAt).toBe(quote.update_time);
    expect(quote.freshness).toBe('synthetic');
    expect(quote.isFallback).toBe(false);
    expect(quote.isStale).toBe(false);
    expect(quote.isPartial).toBe(true);
    expect(quote.isSynthetic).toBe(true);
    expect(quote.sourceConfidence?.isSynthetic).toBe(true);
    expect(quote.sourceConfidence?.degradationReason).toBe('provider_runtime_unavailable_placeholder');
  });
});
