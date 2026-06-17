import type { AxiosResponse } from 'axios';
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

function httpError(status: number, data: unknown): Error & { response: AxiosResponse } {
  return {
    name: 'AxiosError',
    message: `HTTP ${status}`,
    response: {
      data,
      status,
      statusText: String(status),
      headers: {},
      config: {},
    } as AxiosResponse,
  };
}

function walkKeys(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.flatMap(walkKeys);
  }
  if (value && typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>).flatMap(([key, entry]) => [key, ...walkKeys(entry)]);
  }
  return [];
}

describe('portfolioApi scenario risk adapter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('camel-cases snapshot pricing and evidence metadata without clipping raw boundary fields', async () => {
    const { portfolioApi } = await import('../portfolio');

    get.mockResolvedValueOnce({
      data: {
        as_of: '2026-03-19',
        cost_method: 'fifo',
        currency: 'CNY',
        total_cash: 1000,
        total_market_value: 2000,
        total_equity: 3000,
        realized_pnl: 0,
        unrealized_pnl: 120,
        fee_total: 0,
        tax_total: 0,
        fx_stale: true,
        fx_freshness_state: 'missing',
        valuation_lineage_state: 'price_fallback',
        confidence_cap: {
          value: 55,
          reason_codes: ['fx_fallback_1_to_1', 'price_fallback', 'provider_timeout'],
        },
        fx_rates: [
          {
            from_currency: 'USD',
            to_currency: 'CNY',
            rate: null,
            rate_date: null,
            source: 'missing',
            is_stale: true,
            updated_at: null,
            source_direction: 'fallback_1_to_1',
          },
        ],
        portfolio_risk_evidence: {
          limitation_labels: ['FX 汇率缺失'],
          source_refs: [
            { id: 'fx-source-1', provider: 'provider-a', source_class: 'cache_snapshot' },
          ],
          admin_diagnostics: {
            provider: 'provider-a',
            cache_layer: 'portfolio_fx_cache',
            runtime_state: 'stale_refresh',
            debug_trace: 'collapsed',
          },
        },
        exposure_research_context: {
          dominant_exposure: {
            type: 'position',
            source: 'snapshot_analytics',
            symbol: 'AAPL',
            label: 'AAPL',
            market: 'us',
            currency: 'USD',
            market_value: 1600,
            weight_pct: 100,
            fx_status: 'live',
            raw_payload: 'hidden',
          },
          concentration_context: {
            state: 'elevated',
            top_weight_pct: 100,
            alert: true,
            holding_count: 1,
            account_count: 1,
            dominant_type: 'position',
            dominant_label: 'AAPL',
            warning_codes: ['single_position_gt_30'],
          },
          currency_context: {
            state: 'limited',
            base_currency: 'CNY',
            fx_freshness_state: 'stale',
            largest_currency: {
              currency: 'USD',
              label: 'USD',
              weight_pct: 100,
              fx_status: 'stale',
              provider: 'hidden-provider',
            },
            stale_pairs: ['USD/CNY'],
          },
          market_context: {
            state: 'limited',
            largest_market: { market: 'us', label: 'US', weight_pct: 100 },
            market_breakdown: [
              { market: 'us', weight_pct: 100, position_count: 1, debug_trace: 'hidden' },
            ],
            benchmark_mapping_state: 'unmapped',
            factor_mapping_state: 'unmapped',
            sector_context_state: 'unavailable',
          },
          stale_inputs: [
            { input: 'fx_freshness', status: 'stale', reason: 'aggregate_currency_context_limited', provider: 'hidden' },
          ],
          evidence_gaps: ['fx_freshness', 'benchmark_mapping'],
          observation_boundary: {
            observation_only: true,
            decision_grade: false,
            accounting_mutation: false,
            portfolio_mutation: false,
            provider_routing_changed: false,
            external_provider_calls_added: false,
            advice_boundary: 'no_advice',
            message: 'Observation-only portfolio research context; not personalized financial advice and not an instruction.',
          },
          research_next_steps: [
            { topic: 'dominant_exposure', check: 'Review latest research evidence for AAPL and its market context.', raw_payload: 'hidden' },
          ],
        },
        accounts: [
          {
            account_id: 1,
            account_name: 'Main',
            broker: 'Demo',
            market: 'us',
            base_currency: 'CNY',
            as_of: '2026-03-19',
            cost_method: 'fifo',
            total_cash: 1000,
            total_market_value: 2000,
            total_equity: 3000,
            realized_pnl: 0,
            unrealized_pnl: 120,
            fee_total: 0,
            tax_total: 0,
            fx_stale: true,
            positions: [
              {
                symbol: 'AAPL',
                market: 'us',
                currency: 'USD',
                quantity: 10,
                avg_cost: 150,
                total_cost: 1500,
                last_price: 160,
                market_value_base: 1600,
                unrealized_pnl_base: 100,
                valuation_currency: 'USD',
                cost_basis_native: 1500,
                market_value_native: 1600,
                unrealized_pnl_native: 100,
                display_market_value: 1600,
                display_unrealized_pnl: 100,
                display_currency: 'USD',
                display_fx_status: 'live',
                price_source: 'daily_close_quote',
                price_source_label: 'Daily close quote',
                price_as_of: '2026-03-19',
                is_price_fallback: true,
                price_fallback_reason: 'current_quote_unavailable',
                valuation_confidence: 0.55,
              },
            ],
          },
        ],
      },
    });

    const payload = await portfolioApi.getSnapshot({ accountId: 1, costMethod: 'fifo' });

    expect(get).toHaveBeenCalledWith('/api/v1/portfolio/snapshot', {
      params: {
        account_id: 1,
        cost_method: 'fifo',
      },
    });

    expect(payload.valuationLineageState).toBe('price_fallback');
    expect(payload.fxFreshnessState).toBe('missing');
    expect(payload.confidenceCap).toEqual({
      value: 55,
      reasonCodes: ['fx_fallback_1_to_1', 'price_fallback', 'provider_timeout'],
    });
    expect(payload.portfolioRiskEvidence).toMatchObject({
      limitationLabels: ['FX 汇率缺失'],
      sourceRefs: [
        { id: 'fx-source-1', provider: 'provider-a', sourceClass: 'cache_snapshot' },
      ],
      adminDiagnostics: {
        provider: 'provider-a',
        cacheLayer: 'portfolio_fx_cache',
        runtimeState: 'stale_refresh',
        debugTrace: 'collapsed',
      },
    });
    expect(payload.exposureResearchContext).toEqual({
      dominantExposure: {
        type: 'position',
        symbol: 'AAPL',
        label: 'AAPL',
        market: 'us',
        currency: 'USD',
        marketValue: 1600,
        weightPct: 100,
        fxStatus: 'live',
      },
      concentrationContext: {
        state: 'elevated',
        topWeightPct: 100,
        alert: true,
        holdingCount: 1,
        accountCount: 1,
        dominantType: 'position',
        dominantLabel: 'AAPL',
      },
      currencyContext: {
        state: 'limited',
        baseCurrency: 'CNY',
        fxFreshnessState: 'stale',
        largestCurrency: {
          currency: 'USD',
          label: 'USD',
          weightPct: 100,
          fxStatus: 'stale',
        },
        stalePairs: ['USD/CNY'],
      },
      marketContext: {
        state: 'limited',
        largestMarket: { market: 'us', label: 'US', weightPct: 100 },
        marketBreakdown: [{ market: 'us', weightPct: 100, positionCount: 1 }],
        benchmarkMappingState: 'unmapped',
        factorMappingState: 'unmapped',
        sectorContextState: 'unavailable',
      },
      staleInputs: [{ input: 'fx_freshness', status: 'stale', reason: 'aggregate_currency_context_limited' }],
      evidenceGaps: ['fx_freshness', 'benchmark_mapping'],
      observationBoundary: {
        observationOnly: true,
        decisionGrade: false,
        accountingMutation: false,
        portfolioMutation: false,
        adviceBoundary: 'no_advice',
        message: 'Observation-only portfolio research context; not personalized financial advice and not an instruction.',
      },
      researchNextSteps: [{ topic: 'dominant_exposure', check: 'Review latest research evidence for AAPL and its market context.' }],
    });
    const contextKeys = new Set(walkKeys(payload.exposureResearchContext));
    for (const forbiddenKey of ['source', 'warningCodes', 'providerRoutingChanged', 'externalProviderCallsAdded', 'rawPayload', 'debugTrace']) {
      expect(contextKeys.has(forbiddenKey)).toBe(false);
    }
    expect(payload.fxRates?.[0]).toEqual({
      fromCurrency: 'USD',
      toCurrency: 'CNY',
      rate: null,
      rateDate: null,
      source: 'missing',
      isStale: true,
      updatedAt: null,
      sourceDirection: 'fallback_1_to_1',
    });
    expect(payload.accounts[0].positions[0]).toMatchObject({
      priceSource: 'daily_close_quote',
      priceSourceLabel: 'Daily close quote',
      priceAsOf: '2026-03-19',
      isPriceFallback: true,
      priceFallbackReason: 'current_quote_unavailable',
      displayFxStatus: 'live',
      valuationConfidence: 0.55,
    });

    const keys = new Set(walkKeys(payload));
    for (const forbiddenKey of [
      'as_of',
      'cost_method',
      'fx_stale',
      'fx_freshness_state',
      'valuation_lineage_state',
      'reason_codes',
      'source_refs',
      'admin_diagnostics',
      'cache_layer',
      'runtime_state',
      'debug_trace',
      'price_source',
      'price_source_label',
      'price_as_of',
      'is_price_fallback',
      'price_fallback_reason',
      'display_fx_status',
      'from_currency',
      'to_currency',
      'rate_date',
      'is_stale',
      'updated_at',
      'source_direction',
      'dominant_exposure',
      'concentration_context',
      'currency_context',
      'market_context',
      'stale_inputs',
      'observation_boundary',
      'research_next_steps',
      'warning_codes',
      'provider_routing_changed',
      'external_provider_calls_added',
      'raw_payload',
    ]) {
      expect(keys.has(forbiddenKey)).toBe(false);
    }
  });

  it('normalizes portfolio risk exposure research context with the same bounded projection', async () => {
    const { portfolioApi } = await import('../portfolio');

    get.mockResolvedValueOnce({
      data: {
        as_of: '2026-03-19',
        account_id: null,
        cost_method: 'fifo',
        currency: 'CNY',
        thresholds: {},
        concentration: { total_market_value: 2000, top_weight_pct: 55, alert: true, top_positions: [] },
        sector_concentration: { total_market_value: 2000, top_weight_pct: 0, alert: false, top_sectors: [], coverage: {}, errors: [] },
        drawdown: { series_points: 0, max_drawdown_pct: 0, current_drawdown_pct: 0, alert: false, fx_stale: false },
        stop_loss: { near_alert: false, triggered_count: 0, near_count: 0, items: [] },
        exposure_research_context: {
          dominant_exposure: { type: 'currency', currency: 'USD', label: 'USD', weight_pct: 82, source: 'risk_debug' },
          concentration_context: { state: 'elevated', top_weight_pct: 82, alert: true, warning_codes: ['single_currency_gt_80'] },
          currency_context: { state: 'observable', base_currency: 'CNY', fx_freshness_state: 'current', stale_pairs: [] },
          market_context: { state: 'observable', benchmark_mapping_state: 'mapped', factor_mapping_state: 'mapped' },
          stale_inputs: [],
          evidence_gaps: [],
          observation_boundary: {
            observation_only: true,
            decision_grade: false,
            accounting_mutation: false,
            portfolio_mutation: false,
            provider_routing_changed: false,
            external_provider_calls_added: false,
            advice_boundary: 'no_advice',
            message: 'Observation-only portfolio research context; not personalized financial advice and not an instruction.',
          },
          research_next_steps: [{ topic: 'dominant_exposure', check: 'Review the largest exposure bucket before interpreting portfolio context.' }],
        },
      },
    });

    const payload = await portfolioApi.getRisk({ costMethod: 'fifo' });

    expect(get).toHaveBeenCalledWith('/api/v1/portfolio/risk', {
      params: { cost_method: 'fifo' },
    });
    expect(payload.exposureResearchContext).toMatchObject({
      dominantExposure: { type: 'currency', currency: 'USD', label: 'USD', weightPct: 82 },
      concentrationContext: { state: 'elevated', topWeightPct: 82, alert: true },
      currencyContext: { state: 'observable', baseCurrency: 'CNY', fxFreshnessState: 'current', stalePairs: [] },
      marketContext: { state: 'observable', benchmarkMappingState: 'mapped', factorMappingState: 'mapped' },
      staleInputs: [],
      evidenceGaps: [],
      observationBoundary: {
        observationOnly: true,
        decisionGrade: false,
        accountingMutation: false,
        portfolioMutation: false,
        adviceBoundary: 'no_advice',
      },
      researchNextSteps: [{ topic: 'dominant_exposure', check: 'Review the largest exposure bucket before interpreting portfolio context.' }],
    });

    const keys = new Set(walkKeys(payload.exposureResearchContext));
    for (const forbiddenKey of ['source', 'warningCodes', 'providerRoutingChanged', 'externalProviderCallsAdded']) {
      expect(keys.has(forbiddenKey)).toBe(false);
    }
  });

  it('posts only caller-supplied scenario risk fields with canonical camelCase payload', async () => {
    const { portfolioApi } = await import('../portfolio');
    const syncTokenKey = 'sync' + 'Token';

    post.mockResolvedValueOnce({
      data: {
        readModelType: 'portfolio_scenario_risk_advisory_v1',
        advisoryOnly: true,
        executionReadiness: 'advisory_only_not_trade_execution',
        coverage: {},
        scenarios: [],
        insufficientDataReasons: [],
        missingDataWarnings: [],
        metadata: {
          sideEffectFree: true,
          noBrokerSync: true,
          noAccountingMutation: true,
          noOrderPlacement: true,
          notInvestmentAdvice: true,
        },
      },
    });

    await portfolioApi.projectScenarioRisk({
      asOf: '2026-05-18T09:30:00Z',
      positions: [
        {
          symbol: 'NVDA',
          market_value: 1000,
          bucket_label: 'AI Semis',
        } as never,
      ],
      exposures: [
        {
          symbol: 'NVDA',
          label: 'QQQ',
          label_type: 'index_proxy',
          exposure: 1,
        } as never,
      ],
      scenarioShocks: [
        {
          name: 'qqq_proxy_down',
          shocks: {
            QQQ: {
              shock_pct: -5,
              label_type: 'index_proxy',
            },
          },
        } as never,
      ],
      accountId: 'acct-1',
      brokerConnectionId: 'broker-1',
      [syncTokenKey]: 'local-test-marker',
      providerRefresh: true,
      orderId: 'order-1',
      tradeId: 'trade-1',
      portfolioMutation: true,
    } as never);

    expect(post).toHaveBeenCalledWith('/api/v1/portfolio/scenario-risk', {
      asOf: '2026-05-18T09:30:00Z',
      positions: [
        {
          symbol: 'NVDA',
          marketValue: 1000,
          bucketLabel: 'AI Semis',
        },
      ],
      exposures: [
        {
          symbol: 'NVDA',
          label: 'QQQ',
          labelType: 'index_proxy',
          exposure: 1,
        },
      ],
      scenarioShocks: [
        {
          name: 'qqq_proxy_down',
          shocks: {
            QQQ: {
              shockPct: -5,
              labelType: 'index_proxy',
            },
          },
        },
      ],
    });
  });


  it('loads the portfolio structure review projection through the typed client and strips raw payload keys', async () => {
    const { portfolioApi } = await import('../portfolio');

    get.mockResolvedValueOnce({
      data: {
        schema_version: 'portfolio_structure_review_v1',
        aggregate_summary: {
          as_of: '2026-06-15',
          account_count: 1,
          holding_count: 2,
          evaluated_count: 2,
          largest_holding: { ticker: 'AAPL', percent: 60 },
        },
        exposure_by_theme_or_sector: [
          { key: 'ai', label: 'AI Infrastructure', market_value: 1500, percent: 75, holding_count: 2 },
        ],
        counts_by_structure_state: { breakout: 1, mixed: 1 },
        holdings_structure: [
          {
            ticker: 'AAPL',
            structure_state: 'breakout',
            confidence: 'high',
            evidence_quality: { score: 92, status: 'available' },
            risk_flags: ['coverage_gap'],
            research_notes: { watch_next: ['observe'], needs_more_evidence: [], risk_flags: [] },
            missing_evidence: [{ kind: 'daily_ohlcv', message: 'Daily OHLCV evidence is unavailable.' }],
            structure_decision_route: '/stocks/AAPL/structure-decision',
            debug_trace: 'collapsed',
          },
          {
            ticker: 'MSFT',
            structure_state: 'mixed',
            confidence: 'medium',
            evidence_quality: { score: 52, status: 'partial' },
            risk_flags: [],
            research_notes: { watch_next: [], needs_more_evidence: ['Need more bars'], risk_flags: [] },
            missing_evidence: [],
          },
        ],
        strongest_structures: [{ ticker: 'AAPL', structure_state: 'breakout', score: 92 }],
        weakest_evidence: [{ ticker: 'MSFT', status: 'partial', usable_bars: 22, evidence_quality: 52 }],
        common_risk_flags: [{ flag: 'coverage_gap', count: 1, tickers: ['AAPL'] }],
        missing_evidence: [{ kind: 'cached_portfolio_holdings', message: 'Cached portfolio holdings are unavailable.' }],
        data_quality: {
          status: 'partial',
          holding_metadata_status: 'available',
          structure_evidence_status: 'available',
          read_only: true,
          fail_closed: false,
          provider: 'backend-debug',
        },
        no_advice_disclosure: 'Observation-only research context; not personalized financial advice and not an instruction.',
      },
    });

    const payload = await portfolioApi.getStructureReview({
      accountId: 7,
      asOf: '2026-06-15',
      costMethod: 'fifo',
      benchmark: 'SPY',
      maxItems: 5,
    });

    expect(get).toHaveBeenCalledWith('/api/v1/portfolio/structure-review', {
      params: {
        account_id: 7,
        as_of: '2026-06-15',
        cost_method: 'fifo',
        benchmark: 'SPY',
        max_items: 5,
      },
    });
    expect(payload.schemaVersion).toBe('portfolio_structure_review_v1');
    expect(payload.holdingsStructure[0]).toMatchObject({
      ticker: 'AAPL',
      structureState: 'breakout',
      confidence: 'high',
      evidenceQuality: { score: 92, status: 'available' },
      riskFlags: ['coverage_gap'],
      researchNotes: { watchNext: ['observe'], needsMoreEvidence: [], riskFlags: [] },
      missingEvidence: [{ kind: 'daily_ohlcv', message: 'Daily OHLCV evidence is unavailable.' }],
    });
    expect(payload.dataQuality).toMatchObject({
      status: 'partial',
      holdingMetadataStatus: 'available',
      structureEvidenceStatus: 'available',
      readOnly: true,
      failClosed: false,
    });

    const keys = new Set(walkKeys(payload));
    for (const forbiddenKey of ['schema_version', 'aggregate_summary', 'exposure_by_theme_or_sector', 'counts_by_structure_state', 'holdings_structure', 'strongest_structures', 'weakest_evidence', 'common_risk_flags', 'missing_evidence', 'no_advice_disclosure', 'provider', 'debug_trace']) {
      expect(keys.has(forbiddenKey)).toBe(false);
    }
  });
  it('normalizes scenario risk response to consumer-safe advisory fields only', async () => {
    const { portfolioApi } = await import('../portfolio');

    post.mockResolvedValueOnce({
      data: {
        read_model_type: 'portfolio_scenario_risk_advisory_v1',
        advisory_only: true,
        accounting_mutation: false,
        broker_integration: false,
        trade_execution: false,
        execution_readiness: 'advisory_only_not_trade_execution',
        as_of: '2026-05-18T09:30:00Z',
        coverage: {
          total_positions: 3,
          positions_with_usable_weight: 3,
          positions_with_market_value: 3,
          effective_weight_sum: 1,
          total_market_value: 2000,
          explicit_exposure_rows: 4,
          labels_with_explicit_coverage: ['AI_THEME', 'QQQ'],
        },
        scenarios: [
          {
            name: 'qqq_proxy_down',
            portfolio_impact_pct: -3.5,
            portfolio_impact_amount: -70,
            covered_weight: 0.75,
            covered_market_value: 1500,
            warnings: ['missing_scenario_coverage'],
            missing_coverage: [
              {
                label: 'QQQ',
                label_type: 'index_proxy',
                missing_symbols: ['BND'],
              },
            ],
            position_contributions: [
              {
                symbol: 'NVDA',
                bucket: 'AI Semis',
                weight: 0.5,
                market_value: 1000,
                impact_pct: -2.5,
                impact_amount: -50,
                contribution_to_scenario_loss: 0.7143,
                warnings: [],
                applied_shocks: [
                  {
                    label: 'QQQ',
                    label_type: 'index_proxy',
                    shock_pct: -5,
                    exposure: 1,
                    impact_pct: -2.5,
                    impact_amount: -50,
                  },
                ],
              },
            ],
            bucket_contributions: [
              {
                bucket: 'AI Semis',
                position_count: 1,
                impact_pct: -2.5,
                impact_amount: -50,
                contribution_to_scenario_loss: 0.7143,
              },
            ],
          },
        ],
        insufficient_data_reasons: [],
        missing_data_warnings: ['scenario_coverage_incomplete'],
        metadata: {
          deterministic: true,
          side_effect_free: true,
          input_source: 'caller_supplied_positions_exposures_and_scenarios',
          no_live_prices: true,
          no_broker_sync: true,
          no_accounting_mutation: true,
          no_order_placement: true,
          not_investment_advice: true,
          no_provider_runtime: true,
          advisory_only: true,
        },
      },
    });

    const payload = await portfolioApi.projectScenarioRisk({
      asOf: '2026-05-18T09:30:00Z',
      positions: [],
      exposures: [],
      scenarioShocks: [],
    });

    expect(payload).toEqual({
      readModelType: 'portfolio_scenario_risk_advisory_v1',
      advisoryOnly: true,
      executionReadiness: 'advisory_only_not_trade_execution',
      asOf: '2026-05-18T09:30:00Z',
      coverage: {
        totalPositions: 3,
        positionsWithUsableWeight: 3,
        positionsWithMarketValue: 3,
        effectiveWeightSum: 1,
        totalMarketValue: 2000,
        explicitExposureRows: 4,
        labelsWithExplicitCoverage: ['AI_THEME', 'QQQ'],
      },
      scenarios: [
        {
          name: 'qqq_proxy_down',
          portfolioImpactPct: -3.5,
          portfolioImpactAmount: -70,
          coveredWeight: 0.75,
          coveredMarketValue: 1500,
          warnings: ['missing_scenario_coverage'],
          missingCoverage: [
            {
              label: 'QQQ',
              labelType: 'index_proxy',
              missingSymbols: ['BND'],
            },
          ],
          positionContributions: [
            {
              symbol: 'NVDA',
              bucket: 'AI Semis',
              weight: 0.5,
              marketValue: 1000,
              impactPct: -2.5,
              impactAmount: -50,
              contributionToScenarioLoss: 0.7143,
              warnings: [],
              appliedShocks: [
                {
                  label: 'QQQ',
                  labelType: 'index_proxy',
                  shockPct: -5,
                  exposure: 1,
                  impactPct: -2.5,
                  impactAmount: -50,
                },
              ],
            },
          ],
          bucketContributions: [
            {
              bucket: 'AI Semis',
              positionCount: 1,
              impactPct: -2.5,
              impactAmount: -50,
              contributionToScenarioLoss: 0.7143,
            },
          ],
        },
      ],
      insufficientDataReasons: [],
      missingDataWarnings: ['scenario_coverage_incomplete'],
      metadata: {
        sideEffectFree: true,
        noBrokerSync: true,
        noAccountingMutation: true,
        noOrderPlacement: true,
        notInvestmentAdvice: true,
      },
    });

    const keys = new Set(walkKeys(payload));
    for (const forbiddenKey of [
      'accountingMutation',
      'brokerIntegration',
      'tradeExecution',
      'noProviderRuntime',
      'inputSource',
      'noLivePrices',
      'deterministic',
      'providerRefresh',
      'orderId',
      'tradeId',
    ]) {
      expect(keys.has(forbiddenKey)).toBe(false);
    }
  });

  it('normalizes missing coverage fields from snake_case payloads', async () => {
    const { portfolioApi } = await import('../portfolio');

    post.mockResolvedValueOnce({
      data: {
        read_model_type: 'portfolio_scenario_risk_advisory_v1',
        advisory_only: true,
        execution_readiness: 'advisory_only_not_trade_execution',
        coverage: {
          labels_with_explicit_coverage: ['GROWTH_THEME'],
        },
        scenarios: [
          {
            name: 'theme_and_currency',
            missing_coverage: [
              {
                label: 'GROWTH_THEME',
                label_type: 'theme',
                missing_symbols: ['BBB'],
              },
              {
                label: 'USD',
                label_type: 'explicit_label',
                missing_symbols: ['AAA', 'BBB'],
              },
            ],
            position_contributions: [],
            bucket_contributions: [],
          },
        ],
        insufficient_data_reasons: [],
        missing_data_warnings: ['scenario_coverage_incomplete'],
        metadata: {
          side_effect_free: true,
          no_broker_sync: true,
          no_accounting_mutation: true,
          no_order_placement: true,
          not_investment_advice: true,
        },
      },
    });

    const payload = await portfolioApi.projectScenarioRisk({
      asOf: '2026-05-18',
      positions: [],
      exposures: [],
      scenarioShocks: [],
    });

    expect(payload.coverage.labelsWithExplicitCoverage).toEqual(['GROWTH_THEME']);
    expect(payload.scenarios[0].missingCoverage).toEqual([
      {
        label: 'GROWTH_THEME',
        labelType: 'theme',
        missingSymbols: ['BBB'],
      },
      {
        label: 'USD',
        labelType: 'explicit_label',
        missingSymbols: ['AAA', 'BBB'],
      },
    ]);
  });

  it('propagates backend validation errors unchanged', async () => {
    const { portfolioApi } = await import('../portfolio');
    const error = httpError(422, {
      detail: [
        {
          loc: ['body', 'asOf'],
          msg: 'Field required',
          type: 'missing',
        },
      ],
    });
    post.mockRejectedValueOnce(error);

    await expect(portfolioApi.projectScenarioRisk({
      asOf: '',
      positions: [],
      exposures: [],
      scenarioShocks: [],
    })).rejects.toMatchObject({
      response: {
        status: 422,
        data: {
          detail: [
            {
              loc: ['body', 'asOf'],
              msg: 'Field required',
              type: 'missing',
            },
          ],
        },
      },
    });
  });
});
