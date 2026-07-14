import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AxiosResponse } from 'axios';
import apiClient from '../index';
import { optionsLabApi } from '../optionsLab';

vi.mock('../index', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
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

describe('optionsLabApi fail-closed boundaries', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('rejects summary network failures without producing fixture data', async () => {
    const error = new Error('Network Error');
    vi.mocked(apiClient.get).mockRejectedValueOnce(error);

    await expect(optionsLabApi.getUnderlyingSummary('tem')).rejects.toBe(error);
  });

  it('rejects expiration network failures without producing fixed dates', async () => {
    const error = new Error('Network Error');
    vi.mocked(apiClient.get).mockRejectedValueOnce(error);

    await expect(optionsLabApi.getExpirations('tem')).rejects.toBe(error);
  });

  it('rejects chain network failures without producing fixed quotes or Greeks', async () => {
    const error = new Error('Network Error');
    vi.mocked(apiClient.get).mockRejectedValueOnce(error);

    await expect(optionsLabApi.getOptionChain('tem', '2030-01-18')).rejects.toBe(error);
  });

  it('does not mask authenticated or unsupported-symbol HTTP responses with fixtures', async () => {
    const authError = httpError(401, {
      error: 'unauthorized',
      message: 'Login required',
    });
    vi.mocked(apiClient.get).mockRejectedValueOnce(authError);

    await expect(optionsLabApi.getUnderlyingSummary('TEM')).rejects.toBe(authError);
    expect(authError).toMatchObject({ message: 'HTTP 401', response: { status: 401 } });

    const unsupportedError = httpError(404, {
      detail: {
        error: 'unsupported_symbol',
        message: 'Options Lab Phase 1 supports fixture-backed US listed equity options only.',
      },
    });
    vi.mocked(apiClient.get).mockRejectedValueOnce(unsupportedError);

    await expect(optionsLabApi.getExpirations('HK00700')).rejects.toBe(unsupportedError);
    expect(unsupportedError).toMatchObject({ message: 'HTTP 404', response: { status: 404 } });
  });

  it('keeps successful unsupported and empty-expiration responses unchanged', async () => {
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({
        data: {
          symbol: 'HK00700',
          market: 'hk',
          underlying: {
            price: null,
            source: 'unavailable',
            as_of: '',
            freshness: 'error',
          },
          options_availability: {
            supported: false,
            provider: 'unavailable',
            limitations: ['unsupported_symbol'],
          },
          metadata: {
            read_only: true,
            no_external_calls_in_tests: false,
            limitations: ['unsupported_symbol'],
          },
        },
      } as never)
      .mockResolvedValueOnce({
        data: {
          symbol: 'TEM',
          expirations: [],
          metadata: {
            read_only: true,
            no_external_calls_in_tests: false,
            limitations: [],
          },
        },
      } as never);

    await expect(optionsLabApi.getUnderlyingSummary('HK00700')).resolves.toMatchObject({
      symbol: 'HK00700',
      optionsAvailability: {
        supported: false,
        limitations: ['unsupported_symbol'],
      },
    });
    await expect(optionsLabApi.getExpirations('TEM')).resolves.toMatchObject({
      symbol: 'TEM',
      expirations: [],
    });
  });

  it('normalizes the options structure signal packet on chain responses', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        symbol: 'TEM',
        expiration: '2026-06-19',
        underlying: null,
        calls: [],
        puts: [],
        filters_applied: {},
        chain_as_of: '2026-05-06T13:45:00Z',
        source: 'synthetic_options_lab_fixture',
        limitations: [],
        metadata: {
          read_only: true,
          no_order_placement: true,
          no_broker_connection: true,
          no_portfolio_mutation: true,
        },
        options_structure_signal_packet: {
          gamma_coverage_state: 'covered',
          iv_coverage_state: 'covered',
          skew_observation: {
            state: 'observed',
            call_average_iv: 0.62,
            put_average_iv: 0.66,
            call_put_iv_spread: -0.04,
            contract_count: 4,
          },
          liquidity_observation: {
            state: 'partial',
            contract_count: 4,
            contracts_with_bid_ask: 4,
            wide_spread_count: 1,
            thin_liquidity_count: 1,
            minimum_open_interest: 40,
            minimum_volume: 8,
          },
          expiration_coverage: {
            state: 'single_expiration',
            expiration_count: 1,
            nearest_dte: 44,
            contracts_by_expiration: [
              { expiration: '2026-06-19', contract_count: 4 },
            ],
          },
          missing_greeks: [],
          stale_or_demo_boundary: {
            state: 'demo_or_stale',
            source_freshness: 'synthetic_delayed',
            fixture_backed: true,
            synthetic_data: true,
            force_refresh_ignored: true,
          },
          observation_boundary: {
            research_only: true,
            decision_grade: false,
            execution_supported: false,
            order_placement: false,
            broker_execution: false,
            portfolio_mutation: false,
          },
          research_next_steps: [
            'Confirm non-demo chain freshness before elevating confidence.',
          ],
        },
      },
    } as never);

    await expect(optionsLabApi.getOptionChain('tem', '2026-06-19')).resolves.toMatchObject({
      symbol: 'TEM',
      optionsStructureSignalPacket: {
        gammaCoverageState: 'covered',
        ivCoverageState: 'covered',
        skewObservation: {
          callAverageIv: 0.62,
          putAverageIv: 0.66,
          callPutIvSpread: -0.04,
        },
        liquidityObservation: {
          state: 'partial',
          wideSpreadCount: 1,
          thinLiquidityCount: 1,
        },
        expirationCoverage: {
          nearestDte: 44,
          contractsByExpiration: [
            { expiration: '2026-06-19', contractCount: 4 },
          ],
        },
        staleOrDemoBoundary: {
          state: 'demo_or_stale',
          forceRefreshIgnored: true,
        },
        observationBoundary: {
          researchOnly: true,
          executionSupported: false,
          orderPlacement: false,
          brokerExecution: false,
          portfolioMutation: false,
        },
        researchNextSteps: [
          'Confirm non-demo chain freshness before elevating confidence.',
        ],
      },
    });
  });

  it('normalizes complete options chain readiness into consumer-safe labels', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        symbol: 'TEM',
        expiration: '2026-06-19',
        underlying: null,
        calls: [],
        puts: [],
        filters_applied: {},
        chain_as_of: '2026-05-06T13:45:00Z',
        source: 'authorized_snapshot',
        limitations: [],
        metadata: {
          read_only: true,
        },
        options_chain_readiness: {
          contract_version: 'options-chain-readiness-v1',
          overall_state: 'ready',
          chain_state: 'available',
          configuration_state: 'available',
          data_boundary: 'provider_backed',
          authority_state: 'authoritative',
          score_authority: 'authoritative',
          expiration_coverage: {
            state: 'available',
            expiration_count: 2,
            missing_count: 0,
            covered_expirations: ['2026-06-19', '2026-08-21'],
          },
          strike_coverage: {
            state: 'available',
            strike_count: 12,
            sparse_count: 0,
          },
          field_completeness: {
            iv: { state: 'available', available_count: 12, missing_count: 0, total_count: 12 },
            greeks: { state: 'available', available_count: 12, missing_count: 0, total_count: 12 },
            open_interest: { state: 'available', available_count: 12, missing_count: 0, total_count: 12 },
            volume: { state: 'available', available_count: 12, missing_count: 0, total_count: 12 },
            quote: { state: 'available', available_count: 12, missing_count: 0, total_count: 12 },
          },
          blocking_reasons: [],
          warnings: [],
          next_evidence_needed: [],
        },
      },
    } as never);

    await expect(optionsLabApi.getOptionChain('tem', '2026-06-19')).resolves.toMatchObject({
      symbol: 'TEM',
      optionsChainReadiness: {
        contractVersion: 'options-chain-readiness-v1',
        overallState: 'ready',
        chainState: 'available',
        dataBoundary: 'provider_backed',
        authorityState: 'authoritative',
        expirationCoverage: {
          coveredExpirations: ['2026-06-19', '2026-08-21'],
        },
        fieldCompleteness: {
          openInterest: {
            totalCount: 12,
          },
        },
      },
      optionsChainReadinessView: {
        labels: ['链可用', '到期覆盖可用', '结构比较可用'],
        blockerLabels: [],
        allLabels: ['链可用', '到期覆盖可用', '结构比较可用'],
      },
    });
  });

  it('normalizes the options structure summary endpoint without fixture fallback', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        contract_version: 'options-structure-summary-v1',
        symbol: 'aapl',
        status: 'degraded',
        calculation_state: 'degraded',
        observation_only: true,
        decision_grade: false,
        provider_configured: true,
        spot_price: 214.55,
        as_of: '2026-06-19T13:30:00Z',
        freshness: 'live',
        snapshot: {
          contract_version: 'option-chain-snapshot-v1',
          symbol: 'AAPL',
          spot_price: 214.55,
          as_of: '2026-06-19T13:30:00Z',
          freshness: 'live',
          contracts: [
            {
              contract_symbol: 'AAPL260619C00215000',
              side: 'call',
              expiration: '2026-06-19',
              strike: 215,
              open_interest: 1200,
              volume: 320,
              charm: -0.12,
              vanna: 0.34,
              dealer_gamma_exposure: 125000.5,
              missing_inputs: [],
            },
          ],
        },
        strike_summaries: [
          {
            strike: 215,
            contract_count: 2,
            call_open_interest: 1200,
            put_open_interest: 800,
            call_volume: 320,
            put_volume: 240,
            net_dealer_gamma_exposure: 200000,
            calculation_state: 'available',
          },
        ],
        expiration_summaries: [
          {
            expiration: '2026-06-19',
            dte: 0,
            is_zero_dte: true,
            strike_count: 1,
            contract_count: 2,
            call_open_interest: 1200,
            put_open_interest: 800,
            call_volume: 320,
            put_volume: 240,
            net_dealer_gamma_exposure: 200000,
            calculation_state: 'available',
          },
        ],
        nearest_expirations: [
          { expiration: '2026-06-19', dte: 0, contract_count: 2 },
        ],
        zero_dte: {
          state: 'available',
          expiration: '2026-06-19',
          dte: 0,
          contract_count: 2,
          call_open_interest: 1200,
          put_open_interest: 800,
          call_volume: 320,
          put_volume: 240,
          open_interest_share: 0.42,
          volume_share: 0.35,
        },
        gamma_flip_level: {
          state: 'available',
          level: 212.5,
          reason: 'methodology_available',
        },
        total_dealer_gamma_exposure: 200000,
        blocking_reasons: ['degraded'],
        warnings: ['missing_inputs'],
        next_evidence_needed: ['configure_authorized_options_structure_provider'],
      },
    } as never);

    await expect(optionsLabApi.getOptionsStructure('aapl')).resolves.toMatchObject({
      symbol: 'AAPL',
      status: 'degraded',
      calculationState: 'degraded',
      providerConfigured: true,
      asOf: '2026-06-19T13:30:00Z',
      snapshot: {
        contracts: [
          {
            contractSymbol: 'AAPL260619C00215000',
            openInterest: 1200,
            volume: 320,
            charm: -0.12,
            vanna: 0.34,
            dealerGammaExposure: 125000.5,
          },
        ],
      },
      expirationSummaries: [
        {
          expiration: '2026-06-19',
          isZeroDte: true,
          callOpenInterest: 1200,
          putVolume: 240,
        },
      ],
      zeroDte: {
        state: 'available',
        openInterestShare: 0.42,
        volumeShare: 0.35,
      },
      gammaFlipLevel: {
        state: 'available',
        level: 212.5,
      },
      totalDealerGammaExposure: 200000,
      blockingReasons: ['degraded'],
      warnings: ['missing_inputs'],
      nextEvidenceNeeded: ['configure_authorized_options_structure_provider'],
    });
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/options/underlyings/AAPL/structure');
  });

  it('maps demo sample options chain readiness to observation labels', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        symbol: 'TEM',
        expiration: '2026-06-19',
        underlying: null,
        calls: [],
        puts: [],
        filters_applied: {},
        chain_as_of: '2026-05-06T13:45:00Z',
        source: 'synthetic_options_lab_fixture',
        limitations: [],
        metadata: {
          read_only: true,
        },
        options_chain_readiness: {
          contract_version: 'options-chain-readiness-v1',
          overall_state: 'blocked',
          chain_state: 'available',
          configuration_state: 'available',
          data_boundary: 'demo_sample',
          authority_state: 'observation_only',
          score_authority: 'observation_only',
          expiration_coverage: {
            state: 'available',
            expiration_count: 1,
            missing_count: 0,
            covered_expirations: ['2026-06-19'],
          },
          strike_coverage: {
            state: 'available',
            strike_count: 4,
            sparse_count: 0,
          },
          field_completeness: {
            iv: { state: 'available', available_count: 4, missing_count: 0, total_count: 4 },
            greeks: { state: 'available', available_count: 4, missing_count: 0, total_count: 4 },
            open_interest: { state: 'available', available_count: 4, missing_count: 0, total_count: 4 },
            volume: { state: 'available', available_count: 4, missing_count: 0, total_count: 4 },
            quote: { state: 'available', available_count: 4, missing_count: 0, total_count: 4 },
          },
          blocking_reasons: ['demo_sample_data', 'provider_not_authoritative'],
          warnings: [],
          next_evidence_needed: ['补充授权链路证据'],
        },
      },
    } as never);

    const response = await optionsLabApi.getOptionChain('tem', '2026-06-19');

    expect(response.optionsChainReadinessView?.allLabels).toEqual([
      '链可用',
      '到期覆盖可用',
      '演示样本',
      '仅观察',
    ]);
    expect(response.optionsChainReadinessView?.allLabels.join(' ')).not.toMatch(/demo_sample|observation_only|provider_not_authoritative/);
  });

  it('maps partial missing chain fields into compact blockers', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        symbol: 'TEM',
        expiration: '2026-06-19',
        underlying: null,
        calls: [],
        puts: [],
        filters_applied: {},
        chain_as_of: '2026-05-06T13:45:00Z',
        source: 'authorized_snapshot',
        limitations: [],
        metadata: {
          read_only: true,
        },
        options_chain_readiness: {
          contract_version: 'options-chain-readiness-v1',
          overall_state: 'partial',
          chain_state: 'partial',
          configuration_state: 'available',
          data_boundary: 'provider_backed',
          authority_state: 'authoritative',
          score_authority: 'authoritative',
          expiration_coverage: {
            state: 'available',
            expiration_count: 2,
            missing_count: 0,
            covered_expirations: ['2026-06-19', '2026-08-21'],
          },
          strike_coverage: {
            state: 'limited',
            strike_count: 2,
            sparse_count: 1,
          },
          field_completeness: {
            iv: { state: 'partial', available_count: 1, missing_count: 1, total_count: 2 },
            greeks: { state: 'partial', available_count: 1, missing_count: 1, total_count: 2 },
            open_interest: { state: 'partial', available_count: 1, missing_count: 1, total_count: 2 },
            volume: { state: 'partial', available_count: 1, missing_count: 1, total_count: 2 },
            quote: { state: 'partial', available_count: 1, missing_count: 1, total_count: 2 },
          },
          blocking_reasons: [
            'limited_strike_coverage',
            'partial_iv',
            'partial_greeks',
            'partial_open_interest',
            'partial_volume',
            'partial_quote',
          ],
          warnings: [],
          next_evidence_needed: [
            '补充 IV 与 Greeks 覆盖',
            '补充 OI 与成交量覆盖',
            '补充 bid/ask/last 报价字段',
          ],
        },
      },
    } as never);

    const response = await optionsLabApi.getOptionChain('tem', '2026-06-19');

    expect(response.optionsChainReadinessView?.labels).toEqual([
      '链部分可用',
      '到期覆盖可用',
    ]);
    expect(response.optionsChainReadinessView?.blockerLabels).toEqual([
      '行权价覆盖有限',
      'IV待补',
      '希腊值待补',
      'OI/成交待补',
      '报价字段待补',
    ]);
    expect(response.optionsChainReadinessView?.allLabels.join(' ')).not.toMatch(/partial_iv|partial_greeks|partial_open_interest|partial_volume|partial_quote|limited_strike_coverage/);
  });

  it('keeps missing options chain readiness backward compatible', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: {
        symbol: 'TEM',
        expiration: '2026-06-19',
        underlying: null,
        calls: [],
        puts: [],
        filters_applied: {},
        chain_as_of: '2026-05-06T13:45:00Z',
        source: 'legacy_snapshot',
        limitations: [],
        metadata: {
          read_only: true,
        },
      },
    } as never);

    await expect(optionsLabApi.getOptionChain('tem', '2026-06-19')).resolves.toMatchObject({
      symbol: 'TEM',
      optionsChainReadiness: null,
      optionsChainReadinessView: {
        labels: [],
        blockerLabels: [],
        allLabels: [],
      },
    });
  });

  it('posts strategy analyzer requests and normalizes observation-only response fields', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        symbol: 'TEM',
        underlying: {
          price: 52.34,
          freshness: 'synthetic_delayed',
        },
        assumptions: {
          scenario_prices: [45, 52.34, 65],
          risk_free_rate: 0.04,
        },
        analyses: [
          {
            strategy_type: 'long_strangle',
            legs: [
              {
                leg_action: 'long',
                side: 'call',
                contract_symbol: 'TEM260619C00055000',
                expiration: '2026-06-19',
                strike: 55,
                mid: 4.23,
                quantity: 1,
              },
              {
                leg_action: 'long',
                side: 'put',
                contract_symbol: 'TEM260619P00050000',
                expiration: '2026-06-19',
                strike: 50,
                mid: 3.35,
                quantity: 1,
              },
            ],
            net_debit: 758,
            net_credit: null,
            max_profit: null,
            max_loss: 758,
            breakevens: [42.42, 62.58],
            payoff_table: [
              {
                underlying_price: 45,
                gross_payoff: 500,
                net_payoff: -258,
              },
            ],
            aggregate_greeks: {
              delta: 0.06,
              gamma: 0.08,
              theta: -0.09,
              vega: 0.21,
              rho: 0.01,
            },
            missing_greeks_blockers: [],
            model_implied_probability: {
              state: 'available',
              model_implied_probability_of_profit: 0.4123,
              inputs: {
                risk_free_rate: 0.04,
              },
              blockers: [],
            },
            historical_win_rate: {
              state: 'unavailable',
              value: null,
              blockers: ['historical_options_chain_data_unavailable'],
            },
            readiness: {
              strategy_structure_state: 'available',
              chain_data_state: 'partial',
              analysis_state: 'observation_only',
              observation_only: true,
              decision_grade: false,
              data_blockers: ['historical_options_chain_data_unavailable'],
            },
            limitations: ['model_implied_probability_is_assumption_based'],
          },
        ],
        strategy_readiness: {
          strategy_structure_state: 'available',
          chain_data_state: 'partial',
          analysis_state: 'observation_only',
          observation_only: true,
          decision_grade: false,
          data_blockers: ['historical_options_chain_data_unavailable'],
        },
        limitations: ['analysis_only_not_advice'],
        observation_only: true,
        decision_grade: false,
        metadata: {
          read_only: true,
          no_order_placement: true,
          no_broker_connection: true,
          no_portfolio_mutation: true,
          no_trading_recommendation: true,
        },
      },
    } as never);

    await expect(optionsLabApi.analyzeStrategies({
      symbol: 'tem',
      expiration: '2026-06-19',
      strategies: ['long_strangle'],
      scenarioPrices: [45, 52.34, 65],
    })).resolves.toMatchObject({
      symbol: 'TEM',
      observationOnly: true,
      decisionGrade: false,
      strategyReadiness: {
        analysisState: 'observation_only',
        observationOnly: true,
        decisionGrade: false,
      },
      analyses: [
        {
          strategyType: 'long_strangle',
          netDebit: 758,
          breakevens: [42.42, 62.58],
          payoffTable: [
            {
              underlyingPrice: 45,
              netPayoff: -258,
            },
          ],
          aggregateGreeks: {
            delta: 0.06,
            theta: -0.09,
          },
          modelImpliedProbability: {
            modelImpliedProbabilityOfProfit: 0.4123,
            inputs: {
              riskFreeRate: 0.04,
            },
          },
          historicalWinRate: {
            state: 'unavailable',
            value: null,
            blockers: ['historical_options_chain_data_unavailable'],
          },
          readiness: {
            dataBlockers: ['historical_options_chain_data_unavailable'],
          },
        },
      ],
      metadata: {
        readOnly: true,
        noOrderPlacement: true,
      },
    });
    expect(apiClient.post).toHaveBeenCalledWith('/api/v1/options/strategies/analyze', expect.objectContaining({
      symbol: 'TEM',
      expiration: '2026-06-19',
      strategies: ['long_strangle'],
      scenarioPrices: [45, 52.34, 65],
    }));
  });

  it('posts decision evaluation and preserves successful backend data', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        symbol: 'TEM',
        strategy: 'long_call',
        data_quality: {
          data_quality_score: 25,
          data_quality_tier: 'synthetic_demo_only',
          source_type: 'synthetic',
          blocking_reasons: ['synthetic_or_fixture_data_not_decision_grade'],
        },
        liquidity: {
          liquidity_score: 50,
          spread_pct: 12,
          liquidity_warnings: [],
        },
        iv_greeks: {
          iv_readiness: 60,
          iv_rank_status: 'unavailable',
          iv_rank: null,
          iv_percentile: null,
          warnings: ['iv_rank_unavailable'],
        },
        iv_rank: null,
        iv_percentile: null,
        iv_rank_status: 'unavailable',
        decision_grade: false,
        gate_decision: 'blocked',
        fail_closed_reason_codes: ['synthetic_or_fixture_data_not_decision_grade'],
        data_quality_gates: {
          decision_grade: false,
          tier: 'synthetic_demo_only',
        },
        liquidity_gates: {
          passed: true,
          liquidity_score: 50,
        },
        expected_move: {
          expected_move_abs: 7.5,
          expected_move_pct: 14.31,
          expected_move_source: 'straddle_mid',
          expected_move_warnings: ['expected_move_uses_fixture_mid_prices'],
        },
        optimizer: {
          preferred_strategy_key: null,
          optimizer_label: '数据不足，禁止判断',
          no_trade_reason: 'data_quality_not_decision_grade',
          alternatives: [
            {
              strategy_key: 'bull_call_spread',
              data_quality_tier: 'synthetic_demo_only',
              liquidity_score: 76,
              breakeven_pressure: 0.19,
              max_loss: 230,
              max_gain: 270,
              risk_reward_ratio: 1.17,
              expected_move_alignment: 92,
              iv_readiness: 82,
              trade_quality_score: 35,
              decision_label: '数据不足，禁止判断',
              primary_reasons: ['当前为 synthetic delayed / 演示数据'],
              risk_warnings: ['不可用于真实交易判断'],
            },
          ],
        },
        ranked_alternatives: [],
        breakeven: {
          breakeven: 57.7,
          required_move_pct: 10.11,
          target_price_status: 'target_above_breakeven',
          score: 70,
        },
        risk_reward: {
          max_loss: 270,
          max_gain: null,
          risk_reward_ratio: null,
          score: 50,
        },
        trade_quality_score: 35,
        decision_label: '数据不足，禁止判断',
        primary_reasons: ['当前为 synthetic delayed / 演示数据'],
        risk_warnings: ['不可用于真实交易判断'],
        no_advice_disclosure: 'Analytical output only; not personalized financial advice.',
        freshness: {
          source: 'synthetic_options_lab_fixture',
          freshness: 'synthetic_delayed',
        },
        metadata: {
          read_only: true,
          no_external_calls: true,
        },
      },
    } as never);

    await expect(optionsLabApi.evaluateDecision({
      symbol: 'tem',
      strategy: 'long_call',
      targetPrice: 65,
    })).resolves.toMatchObject({
      symbol: 'TEM',
      decisionLabel: '数据不足，禁止判断',
      decisionGrade: false,
      gateDecision: 'blocked',
      failClosedReasonCodes: ['synthetic_or_fixture_data_not_decision_grade'],
      dataQualityGates: {
        decisionGrade: false,
        tier: 'synthetic_demo_only',
      },
      liquidityGates: {
        passed: true,
        liquidityScore: 50,
      },
      dataQuality: {
        dataQualityTier: 'synthetic_demo_only',
      },
      expectedMove: {
        expectedMoveSource: 'straddle_mid',
      },
      optimizer: {
        optimizerLabel: '数据不足，禁止判断',
      },
    });
    expect(apiClient.post).toHaveBeenCalledWith('/api/v1/options/decision/evaluate', expect.objectContaining({
      symbol: 'TEM',
      strategy: 'long_call',
    }));

  });

  it('rejects decision network failures without producing a synthetic decision', async () => {
    const error = new Error('Network Error');
    vi.mocked(apiClient.post).mockRejectedValueOnce(error);

    await expect(optionsLabApi.evaluateDecision({
      symbol: 'TEM',
      strategy: 'bull_call_spread',
    })).rejects.toBe(error);
  });
});
