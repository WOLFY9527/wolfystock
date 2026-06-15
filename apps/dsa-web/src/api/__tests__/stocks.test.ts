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

  it('calls the structure decision endpoint and normalizes explanation arrays', async () => {
    const { stocksApi } = await import('../stocks');

    get.mockResolvedValueOnce({
      data: {
        schema_version: 'stock_structure_decision_api_v1',
        ticker: 'AAPL',
        structure_state: 'breakout',
        confidence: 'high',
        component_scores: {
          trend: 78,
          relative_strength: 71,
        },
        explanation: {
          why_this_structure: 'Price stayed above the recent range.',
          what_confirms_it: ['Volume remained constructive.'],
          what_invalidates_it: ['Closes fall back into the prior range.'],
          key_levels: [
            {
              kind: 'recent_range_high',
              value: 131.2,
              description: 'Upper observation from recent highs.',
            },
          ],
        },
        research_notes: {
          watch_next: ['Observe follow-through on the next close.'],
          needs_more_evidence: ['Need broader market confirmation.'],
          risk_flags: ['Extension risk if price outruns volume.'],
        },
        data_quality: {
          status: 'available',
          source: 'local_db',
          period: 'daily',
          requested_days: 90,
          observed_bars: 55,
          usable_bars: 55,
          reason: 'history_available',
        },
        missing_evidence: [
          {
            kind: 'benchmark_context',
            message: 'Need benchmark context.',
          },
        ],
        no_advice_disclosure: 'Observation-only research context.',
      },
    });

    const payload = await stocksApi.getStructureDecision('AAPL');

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/AAPL/structure-decision');
    expect(payload.ticker).toBe('AAPL');
    expect(payload.structureState).toBe('breakout');
    expect(payload.componentScores.trend).toBe(78);
    expect(payload.explanation.whatConfirmsIt).toEqual(['Volume remained constructive.']);
    expect(payload.explanation.keyLevels?.[0]?.kind).toBe('recent_range_high');
    expect(payload.researchNotes.watchNext).toEqual(['Observe follow-through on the next close.']);
    expect(payload.dataQuality.usableBars).toBe(55);
    expect(payload.missingEvidence[0]?.kind).toBe('benchmark_context');
  });
});
