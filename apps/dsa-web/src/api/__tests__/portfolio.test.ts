import type { AxiosResponse } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { post } = vi.hoisted(() => ({
  post: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
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
