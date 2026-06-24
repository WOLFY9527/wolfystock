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

  it('calls the history endpoint and normalizes readiness diagnostics', async () => {
    const { stocksApi } = await import('../stocks');

    get.mockResolvedValueOnce({
      data: {
        stock_code: 'ORCL',
        stock_name: 'Oracle',
        period: 'daily',
        source: 'local_db',
        diagnostics: {
          status: 'available',
          reason: 'history_available',
          requested_days: 90,
          rows: 2,
          local_fallback: {
            source: 'local_db',
            rows: 2,
            latest_trade_date: '2026-05-28',
            data_sources: ['daily_history'],
          },
        },
        source_confidence: {
          source: 'local_db',
          source_label: 'Local history',
          as_of: '2026-05-28',
          freshness: 'fresh',
          is_fallback: false,
          is_stale: false,
          is_partial: true,
          is_synthetic: false,
          is_unavailable: false,
          confidence_weight: 0.7,
          coverage: 0.4,
          degradation_reason: 'short_history',
          cap_reason: 'insufficient_bars',
        },
        data: [
          {
            date: '2026-05-27',
            open: 100,
            high: 105,
            low: 99,
            close: 104,
            volume: 1000,
            change_percent: 1.2,
          },
          {
            date: '2026-05-28',
            open: 104,
            high: 108,
            low: 103,
            close: 107,
            volume: 1200,
            amount: 128400,
          },
        ],
      },
    });

    const history = await stocksApi.getHistory('ORCL', { period: 'daily', days: 180 });

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/ORCL/history', {
      params: { period: 'daily', days: 180 },
    });
    expect(history.stockCode).toBe('ORCL');
    expect(history.stockName).toBe('Oracle');
    expect(history.period).toBe('daily');
    expect(history.diagnostics?.requestedDays).toBe(90);
    expect(history.diagnostics?.localFallback?.latestTradeDate).toBe('2026-05-28');
    expect(history.sourceConfidence?.sourceLabel).toBe('Local history');
    expect(history.sourceConfidence?.isPartial).toBe(true);
    expect(history.sourceConfidence?.coverage).toBe(0.4);
    expect(history.data).toHaveLength(2);
    expect(history.data[0]).toMatchObject({
      date: '2026-05-27',
      open: 100,
      close: 104,
      changePercent: 1.2,
    });
    expect(history.data[1]?.amount).toBe(128400);
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
        confidence: 'medium',
        confidence_cap: {
          value: 60,
          label: 'medium',
          reasons: ['critical evidence missing'],
        },
        confidence_state: {
          status: 'evidence limited',
          label: 'medium',
          reasons: ['critical evidence missing'],
          freshness_constrained: false,
          source_quality_limited: false,
          thesis_blocked: false,
        },
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
        peer_correlation_snapshot: {
          symbol: 'AAPL',
          peer_group: {
            status: 'available',
            label: 'Mega-cap technology',
            symbols: ['MSFT', 'NVDA'],
            debug_trace: 'must-not-emit-peer-group',
          },
          correlation_state: 'aligned',
          peer_evidence: [
            {
              symbol: 'MSFT',
              correlation: 0.61,
              overlap_days: 24,
              symbol_return_pct: 3.2,
              peer_return_pct: 2.9,
              spread_pct: 0.3,
              state: 'aligned',
              summary: 'MSFT moved with AAPL across the comparison window.',
              provider_payload: 'must-not-emit-peer',
            },
          ],
          divergence_evidence: [],
          stale_inputs: [],
          missing_inputs: [],
          confidence_cap: 'medium',
          observation_boundary: 'Observation-only peer movement context; no personalized action instruction.',
          research_next_steps: ['Review whether peer alignment persists after the next close.'],
          raw_payload: 'must-not-emit-snapshot',
        },
        no_advice_disclosure: 'Observation-only research context.',
      },
    });

    const payload = await stocksApi.getStructureDecision('AAPL');

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/AAPL/structure-decision');
    expect(payload.ticker).toBe('AAPL');
    expect(payload.structureState).toBe('breakout');
    expect(payload.confidence).toBe('medium');
    expect(payload.confidenceCap).toEqual({
      value: 60,
      label: 'medium',
      reasons: ['critical evidence missing'],
    });
    expect(payload.confidenceState).toEqual({
      status: 'evidence limited',
      label: 'medium',
      reasons: ['critical evidence missing'],
      freshnessConstrained: false,
      sourceQualityLimited: false,
      thesisBlocked: false,
    });
    expect(payload.componentScores.trend).toBe(78);
    expect(payload.explanation.whatConfirmsIt).toEqual(['Volume remained constructive.']);
    expect(payload.explanation.keyLevels?.[0]?.kind).toBe('recent_range_high');
    expect(payload.researchNotes.watchNext).toEqual(['Observe follow-through on the next close.']);
    expect(payload.dataQuality.usableBars).toBe(55);
    expect(payload.missingEvidence[0]?.kind).toBe('benchmark_context');
    expect(payload.peerCorrelationSnapshot?.correlationState).toBe('aligned');
    expect(payload.peerCorrelationSnapshot?.peerGroup.symbols).toEqual(['MSFT', 'NVDA']);
    expect(payload.peerCorrelationSnapshot?.peerEvidence[0]).toMatchObject({
      symbol: 'MSFT',
      overlapDays: 24,
      state: 'aligned',
      summary: 'MSFT moved with AAPL across the comparison window.',
    });
    expect(JSON.stringify(payload.peerCorrelationSnapshot)).not.toMatch(/provider|raw|debug|trace|must-not-emit/i);
  });

  it('calls the research packet endpoint and normalizes readiness fields', async () => {
    const { stocksApi } = await import('../stocks');

    get.mockResolvedValueOnce({
      data: {
        symbol: 'AAPL',
        market: 'us',
        identity: {
          name: 'Apple',
          exchange: null,
          sector: null,
          industry: null,
        },
        quote: {
          state: 'available',
          price: 214.55,
          change_percent: 1.11,
          as_of: '2026-05-28T09:30:00Z',
        },
        history: {
          state: 'available',
          bars: 60,
          period: 'daily',
          as_of: '2026-05-28',
        },
        structure: {
          state: 'insufficient',
          label: 'breakout',
          confidence: 'medium',
          as_of: null,
        },
        fundamentals: {
          state: 'not_integrated',
          fields_available: [],
        },
        events: {
          state: 'missing',
          latest: [],
        },
        peer: {
          state: 'insufficient',
          benchmark: null,
        },
        missing_data: ['fundamentals', 'filing_event_catalyst', 'peer_benchmark'],
        research_status: 'partial',
        next_data_action: 'Add fundamentals, filing/event/catalyst, and peer evidence before marking the packet ready.',
        observation_only: true,
        decision_grade: false,
        no_advice_disclosure: 'Observation-only research packet; no personalized action instruction.',
      },
    });

    const payload = await stocksApi.getResearchPacket('AAPL');

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/AAPL/research-packet');
    expect(payload.symbol).toBe('AAPL');
    expect(payload.market).toBe('us');
    expect(payload.identity.name).toBe('Apple');
    expect(payload.quote.changePercent).toBe(1.11);
    expect(payload.quote.asOf).toBe('2026-05-28T09:30:00Z');
    expect(payload.history.asOf).toBe('2026-05-28');
    expect(payload.structure.state).toBe('insufficient');
    expect(payload.fundamentals.state).toBe('not_integrated');
    expect(payload.fundamentals.fieldsAvailable).toEqual([]);
    expect(payload.events.latest).toEqual([]);
    expect(payload.peer.state).toBe('insufficient');
    expect(payload.missingData).toEqual(['fundamentals', 'filing_event_catalyst', 'peer_benchmark']);
    expect(payload.researchStatus).toBe('partial');
    expect(payload.observationOnly).toBe(true);
    expect(payload.decisionGrade).toBe(false);
    expect(payload.noAdviceDisclosure).toContain('Observation-only research packet');
  });

  it('keeps research packet readiness fields backward compatible when families are omitted', async () => {
    const { stocksApi } = await import('../stocks');

    get.mockResolvedValueOnce({
      data: {
        symbol: 'MSFT',
        market: 'us',
        identity: {
          name: 'Microsoft',
        },
        research_status: null,
        observation_only: true,
        decision_grade: false,
      },
    });

    const payload = await stocksApi.getResearchPacket('MSFT');

    expect(payload.symbol).toBe('MSFT');
    expect(payload.identity).toEqual({
      name: 'Microsoft',
      exchange: null,
      sector: null,
      industry: null,
    });
    expect(payload.quote.state).toBe('unknown');
    expect(payload.history.state).toBe('unknown');
    expect(payload.structure.state).toBe('unknown');
    expect(payload.fundamentals).toEqual({ state: 'unknown', fieldsAvailable: [] });
    expect(payload.events).toEqual({ state: 'unknown', latest: [] });
    expect(payload.peer).toEqual({ state: 'unknown', benchmark: null });
    expect(payload.missingData).toEqual([]);
    expect(payload.researchStatus).toBe('unknown');
    expect(payload.observationOnly).toBe(true);
    expect(payload.decisionGrade).toBe(false);
  });

  it('normalizes consumer-safe stock validation status fields', async () => {
    const { stocksApi } = await import('../stocks');

    get.mockResolvedValueOnce({
      data: {
        stock_code: 'INVALID_SYMBOL_XXXX',
        normalized_symbol: 'INVALID_SYMBOL_XXXX',
        market: null,
        status: 'invalid_format',
        valid: false,
        exists: false,
        stock_name: null,
        message: 'Enter a supported stock symbol format.',
      },
    });

    const payload = await stocksApi.verifyTickerExists('INVALID_SYMBOL_XXXX');

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/INVALID_SYMBOL_XXXX/validate');
    expect(payload).toEqual({
      stockCode: 'INVALID_SYMBOL_XXXX',
      normalizedSymbol: 'INVALID_SYMBOL_XXXX',
      market: null,
      status: 'invalid_format',
      valid: false,
      exists: false,
      stockName: null,
      message: 'Enter a supported stock symbol format.',
    });
  });

  it('calls the batch structure decision endpoint and preserves the compare evidence packet', async () => {
    const { stocksApi } = await import('../stocks');

    post.mockResolvedValueOnce({
      data: {
        schemaVersion: 'stock_structure_decision_batch_api_v1',
        items: [],
        aggregateSummary: {
          requestedCount: 2,
          evaluatedCount: 2,
          truncated: false,
        },
        missingEvidence: [],
        dataQuality: {
          status: 'partial',
        },
        symbolCompareEvidencePacket: {
          comparedSymbols: ['MSFT', 'AAPL'],
          sharedEvidence: [
            {
              kind: 'daily_ohlcv',
              symbols: ['MSFT', 'AAPL'],
              status: 'available',
              period: 'daily',
              source: 'local_db',
              usableBarsMin: 55,
              usableBarsMax: 60,
            },
          ],
          divergentEvidence: [
            {
              kind: 'structure_state',
              symbols: ['MSFT', 'AAPL'],
              values: {
                MSFT: 'mixed',
                AAPL: 'breakout',
              },
            },
          ],
          missingEvidenceBySymbol: {
            MSFT: [{ kind: 'daily_ohlcv', message: 'Daily OHLCV history is unavailable.' }],
            AAPL: [],
          },
          freshnessBySymbol: {
            MSFT: { status: 'unavailable', source: 'local_db', period: 'daily', usableBars: 0 },
            AAPL: { status: 'available', source: 'local_db', period: 'daily', usableBars: 60 },
          },
          confidenceCap: {
            value: 35,
            reasonCodes: ['symbol_evidence_unavailable'],
            policyVersion: 'symbol_compare_evidence_packet_v1',
          },
          observationBoundary: {
            observationOnly: true,
            decisionGrade: false,
            rankingAllowed: false,
            adviceAllowed: false,
          },
          researchNextSteps: [
            'Add daily OHLCV evidence for MSFT before using divergence observations.',
          ],
        },
        noAdviceDisclosure: 'Observation-only research context.',
      },
    });

    const payload = await stocksApi.getStructureDecisionsBatch({
      stockCodes: ['MSFT', 'AAPL'],
      benchmark: 'SPY',
      maxItems: 2,
    });

    expect(post).toHaveBeenCalledWith('/api/v1/stocks/structure-decisions/batch', {
      stockCodes: ['MSFT', 'AAPL'],
      benchmark: 'SPY',
      maxItems: 2,
    });
    expect(payload.symbolCompareEvidencePacket?.comparedSymbols).toEqual(['MSFT', 'AAPL']);
    expect(payload.symbolCompareEvidencePacket?.sharedEvidence[0]?.usableBarsMin).toBe(55);
    expect(payload.symbolCompareEvidencePacket?.divergentEvidence[0]?.values?.MSFT).toBe('mixed');
    expect(payload.symbolCompareEvidencePacket?.missingEvidenceBySymbol.MSFT[0]?.kind).toBe('daily_ohlcv');
    expect(payload.symbolCompareEvidencePacket?.freshnessBySymbol.AAPL?.usableBars).toBe(60);
    expect(payload.symbolCompareEvidencePacket?.confidenceCap.value).toBe(35);
    expect(payload.symbolCompareEvidencePacket?.observationBoundary.rankingAllowed).toBe(false);
    expect(payload.symbolCompareEvidencePacket?.researchNextSteps).toEqual([
      'Add daily OHLCV evidence for MSFT before using divergence observations.',
    ]);
  });
});
