import { expect, type Page, type Route } from '@playwright/test';

type ApiRequestLog = {
  calls: string[];
  count: (method: string, path: string) => number;
  wasFetched: (method: string, path: string) => boolean;
};

type PortfolioSmokeHarness = {
  requests: ApiRequestLog;
  scenarioRiskPayloads: unknown[];
};

const timestamp = '2026-05-06T09:45:00-04:00';

const visibleOwnerPortfolioSentinels = ['Launch Owner Main', 'AAPL'];
const forbiddenPortfolioOwnerSentinels = [
  'Bob Launch Main',
  'MSFT-BOB-PRIVATE',
  'mock-canary-bob-broker-account',
  'mock-canary-bob-session-token',
];
const forbiddenPortfolioCredentialSentinels = [
  'mock-canary-alice-api-key',
  'mock-canary-alice-access-token',
  'mock-canary-alice-session-token',
  'mock-canary-broker-order-payload',
  'mock-canary-place-order-payload',
  'mock-canary-raw-provider-payload',
  'mock-canary-sync-metadata',
];

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

function createRequestLog(calls: string[]): ApiRequestLog {
  return {
    calls,
    count: (method: string, path: string) => calls.filter((entry) => entry === `${method} ${path}`).length,
    wasFetched: (method: string, path: string) => calls.includes(`${method} ${path}`),
  };
}

function currentUser() {
  return {
    id: 'user-1',
    username: 'wolfy-user',
    displayName: 'Wolfy User',
    role: 'user',
    isAdmin: false,
    isAuthenticated: true,
    transitional: false,
    authEnabled: true,
  };
}

function accountsPayload() {
  return {
    accounts: [
      {
        id: 1,
        owner_id: 'user-1',
        name: 'Launch Owner Main',
        broker: 'IBKR',
        market: 'us',
        base_currency: 'USD',
        is_active: true,
        created_at: timestamp,
        updated_at: timestamp,
      },
    ],
    owner_scope_canary: {
      forbidden_cross_owner_account: 'Bob Launch Main',
      forbidden_cross_owner_symbol: 'MSFT-BOB-PRIVATE',
    },
  };
}

function brokersPayload() {
  return {
    brokers: [
      { broker: 'huatai', aliases: [], display_name: '华泰', file_extensions: ['csv'] },
      { broker: 'ibkr', aliases: ['interactivebrokers'], display_name: 'Interactive Brokers', file_extensions: ['xml'] },
    ],
  };
}

function brokerConnectionsPayload() {
  return {
    connections: [
      {
        id: 9,
        owner_id: 'user-1',
        portfolio_account_id: 1,
        portfolio_account_name: 'Launch Owner Main',
        connection_name: 'Primary IBKR',
        broker_type: 'ibkr',
        broker_account_ref: 'U1234567',
        import_mode: 'file',
        status: 'active',
        sync_metadata: {
          ibkr_api: {
            api_base_url: 'https://localhost:5000/v1/api',
            verify_ssl: false,
            broker_account_ref: 'U1234567',
          },
          api_key: 'mock-canary-alice-api-key',
          access_token: 'mock-canary-alice-access-token',
          session_token: 'mock-canary-alice-session-token',
          brokerOrderPayload: 'mock-canary-broker-order-payload',
          place_order: 'mock-canary-place-order-payload',
          raw: {
            provider_payload: 'mock-canary-raw-provider-payload',
            sync_metadata_secret: 'mock-canary-sync-metadata',
          },
          last_sync_at: null,
        },
      },
    ],
    excluded_cross_owner_connections: [
      {
        owner_id: 'user-2',
        portfolio_account_name: 'Bob Launch Main',
        broker_account_ref: 'mock-canary-bob-broker-account',
        sync_metadata: { session_token: 'mock-canary-bob-session-token' },
      },
    ],
  };
}

function snapshotPayload() {
  return {
    as_of: '2026-04-15',
    cost_method: 'fifo',
    currency: 'USD',
    account_count: 1,
    realized_pnl: 0,
    unrealized_pnl: 100,
    fee_total: 0,
    tax_total: 0,
    fx_stale: false,
    total_cash: 5000,
    total_market_value: 1600,
    total_equity: 6600,
    accounts: [
      {
        account_id: 1,
        account_name: 'Launch Owner Main',
        owner_id: 'user-1',
        broker: 'IBKR',
        market: 'us',
        base_currency: 'USD',
        as_of: '2026-04-15',
        cost_method: 'fifo',
        total_cash: 5000,
        total_market_value: 1600,
        total_equity: 6600,
        realized_pnl: 0,
        unrealized_pnl: 100,
        fee_total: 0,
        tax_total: 0,
        fx_stale: false,
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
          },
        ],
      },
    ],
    owner_scope_canary: {
      excluded_accounts: [
        {
          owner_id: 'user-2',
          account_name: 'Bob Launch Main',
          positions: [{ symbol: 'MSFT-BOB-PRIVATE' }],
        },
      ],
    },
  };
}

function riskPayload() {
  return {
    as_of: '2026-04-15',
    account_id: null,
    cost_method: 'fifo',
    currency: 'USD',
    thresholds: {},
    concentration: {
      total_market_value: 1600,
      top_weight_pct: 100,
      alert: false,
      top_positions: [{ symbol: 'AAPL', market_value_base: 1600, weight_pct: 100, is_alert: false }],
    },
    sector_concentration: {
      total_market_value: 0,
      top_weight_pct: 0,
      alert: false,
      top_sectors: [],
      coverage: {},
      errors: [],
    },
    drawdown: {
      series_points: 0,
      max_drawdown_pct: 0,
      current_drawdown_pct: 0,
      alert: false,
      fx_stale: false,
    },
    stop_loss: {
      near_alert: false,
      triggered_count: 0,
      near_count: 0,
      items: [],
    },
  };
}

function emptyListPayload() {
  return { items: [], total: 0, page: 1, page_size: 20 };
}

export async function installPortfolioSmokeHarness(page: Page): Promise<PortfolioSmokeHarness> {
  const calls: string[] = [];
  const requests = createRequestLog(calls);
  const scenarioRiskPayloads: unknown[] = [];

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    calls.push(`${method} ${path}`);

    if (method === 'GET' && path === '/api/v1/auth/status') {
      return fulfillJson(route, {
        authEnabled: true,
        loggedIn: true,
        passwordSet: true,
        passwordChangeable: true,
        setupState: 'enabled',
        currentUser: currentUser(),
      });
    }

    if (method === 'GET' && path === '/api/v1/auth/me') {
      return fulfillJson(route, currentUser());
    }

    if (method === 'GET' && path === '/api/v1/agent/status') {
      return fulfillJson(route, { enabled: false });
    }

    if (method === 'GET' && path === '/api/v1/history') {
      return fulfillJson(route, { total: 0, page: 1, limit: 20, items: [] });
    }

    if (method === 'GET' && path === '/api/v1/analysis/tasks') {
      return fulfillJson(route, { tasks: [], total: 0 });
    }

    if (method === 'GET' && path === '/api/v1/portfolio/accounts') {
      return fulfillJson(route, accountsPayload());
    }

    if (method === 'GET' && path === '/api/v1/portfolio/imports/brokers') {
      return fulfillJson(route, brokersPayload());
    }

    if (method === 'GET' && path === '/api/v1/portfolio/broker-connections') {
      return fulfillJson(route, brokerConnectionsPayload());
    }

    if (method === 'GET' && path === '/api/v1/portfolio/snapshot') {
      return fulfillJson(route, snapshotPayload());
    }

    if (method === 'GET' && path === '/api/v1/portfolio/risk') {
      return fulfillJson(route, riskPayload());
    }

    if (method === 'GET' && path === '/api/v1/portfolio/trades') {
      return fulfillJson(route, emptyListPayload());
    }

    if (method === 'GET' && path === '/api/v1/portfolio/cash-ledger') {
      return fulfillJson(route, emptyListPayload());
    }

    if (method === 'GET' && path === '/api/v1/portfolio/corporate-actions') {
      return fulfillJson(route, emptyListPayload());
    }

    if (method === 'POST' && path === '/api/v1/portfolio/sync/ibkr') {
      return fulfillJson(route, {
        account_id: 1,
        broker_connection_id: 9,
        broker_account_ref: 'U1234567',
        connection_name: 'Primary IBKR',
        snapshot_date: '2026-04-15',
        synced_at: '2026-04-15T10:00:00',
        base_currency: 'USD',
        total_cash: 5000,
        total_market_value: 1600,
        total_equity: 6600,
        realized_pnl: 0,
        unrealized_pnl: 100,
        position_count: 1,
        cash_balance_count: 1,
        fx_stale: false,
        snapshot_overlay_active: true,
        used_existing_connection: true,
        api_base_url: 'https://localhost:5000/v1/api',
        verify_ssl: false,
        warnings: [],
      });
    }

    if (method === 'POST' && path === '/api/v1/portfolio/scenario-risk') {
      try {
        scenarioRiskPayloads.push(request.postDataJSON());
      } catch {
        scenarioRiskPayloads.push(null);
      }

      return fulfillJson(route, {
        readModelType: 'portfolio_scenario_risk_advisory_v1',
        advisoryOnly: true,
        executionReadiness: 'advisory_only_not_trade_execution',
        asOf: '2026-04-15',
        coverage: {
          totalPositions: 1,
          positionsWithUsableWeight: 1,
          positionsWithMarketValue: 1,
          effectiveWeightSum: 1,
          totalMarketValue: 1600,
          explicitExposureRows: 0,
          labelsWithExplicitCoverage: [],
        },
        scenarios: [
          {
            name: 'symbol_aapl_down_-8',
            portfolioImpactPct: -8,
            portfolioImpactAmount: -128,
            coveredWeight: 0.85,
            coveredMarketValue: 1360,
            warnings: ['coverage_partial'],
            missingCoverage: [
              {
                label: '现金缓冲',
                labelType: 'cash_buffer',
                missingSymbols: ['USD cash', 'theme mapping pending'],
              },
            ],
            positionContributions: [
              {
                symbol: 'AAPL',
                bucket: 'Launch Owner Main',
                weight: 1,
                marketValue: 1600,
                impactPct: -8,
                impactAmount: -128,
                contributionToScenarioLoss: 1,
                warnings: [],
                appliedShocks: [
                  {
                    label: 'AAPL',
                    labelType: 'symbol',
                    shockPct: -8,
                    exposure: 1,
                    impactPct: -8,
                    impactAmount: -128,
                  },
                ],
              },
            ],
            bucketContributions: [
              {
                bucket: 'Launch Owner Main',
                positionCount: 1,
                impactPct: -8,
                impactAmount: -128,
                contributionToScenarioLoss: 1,
              },
            ],
          },
        ],
        insufficientDataReasons: ['theme_mapping_pending'],
        missingDataWarnings: ['scenario_coverage_incomplete'],
        metadata: {
          sideEffectFree: true,
          noBrokerSync: true,
          noAccountingMutation: true,
          noOrderPlacement: true,
          notInvestmentAdvice: true,
        },
      });
    }

    return fulfillJson(route, { error: `Unhandled portfolio smoke route: ${method} ${path}` }, 500);
  });

  return { requests, scenarioRiskPayloads };
}

export { expect };
export {
  forbiddenPortfolioCredentialSentinels,
  forbiddenPortfolioOwnerSentinels,
  visibleOwnerPortfolioSentinels,
};
