import { expect, test as base, type Page, type Route } from '@playwright/test';
import {
  createMockAdminUser,
  createMockAuthStatus,
  type AdminCapability,
  type MockAdminUserOptions,
} from '../../src/test-utils/adminAuthHarness';
import type { CurrentUser } from '../../src/api/auth';

type AdminAuthFixtures = {
  consoleErrors: string[];
};

type ApiRequestLog = {
  calls: string[];
  count: (method: string, path: string) => number;
  wasFetched: (method: string, path: string) => boolean;
};

type AdminAuthHarness = {
  currentUser: CurrentUser;
  requests: ApiRequestLog;
};

const timestamp = '2026-05-06T10:30:00+08:00';

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

function adminCostSummaryPayload() {
  return {
    generated_at: timestamp,
    window: { key: '24h', from: timestamp, to: timestamp, bucket: 'hour', historical: false },
    summary: {
      llm_calls: 12,
      llm_usage_calls: 8,
      llm_usage_tokens: 42000,
      estimated_duplicate_candidates: 3,
      provider_calls: 18,
      provider_cache_hits: 9,
      provider_cache_misses: 6,
      provider_inflight_joins: 2,
      provider_cache_hit_rate: 0.6,
      market_cache_hits: 15,
      market_cache_misses: 4,
      market_cache_stale_served: 2,
      market_cache_cold_fallbacks: 1,
      market_cache_hit_rate: 0.78,
      fallback_attempts: 5,
      integrity_retries: 1,
      scanner_ai_attempts: 4,
      scanner_ai_completed: 3,
      scanner_ai_skipped: 2,
    },
    llm: { by_call_type: [], duplicate_candidates: [], fallbacks: [], integrity_retries: [], usage_by_call_type: [], usage_by_model: [] },
    providers: { by_category: [], fallback_depth: [], cache_efficiency: [], duplicate_candidates: [] },
    market_cache: { by_panel_key: [], stale_served: [], cold_fallbacks: [], refreshes: [] },
    scanner_ai: { interpretations: [], duplicate_candidates: [], skips: [] },
    limitations: [{ code: 'observational_not_billing', message: 'Mocked observation only.', severity: 'info' }],
    metadata: {
      read_only: true,
      no_external_calls: true,
      counters_source: 'mocked_playwright',
      exactness: 'observational_not_billing',
      data_sources: ['mock'],
      unsupported_sources: [],
      redaction: ['raw_payload_omitted'],
      requested_area: 'all',
      limit: 50,
      notes: {},
    },
  };
}

function quotaDryRunPayload() {
  return {
    allowed: true,
    would_block: false,
    status: 'allowed',
    reason_code: null,
    route_family: 'analysis',
    estimated_units: 4,
    enforcement_mode: 'dry_run',
    operation: 'estimate',
    reservation_id: null,
    metadata: {
      diagnostic_only: true,
      live_enforcement: false,
      no_external_calls: true,
      data_sources: ['quota_policy_definitions'],
      redaction: ['credentials', 'stack_details'],
    },
  };
}

function llmLedgerSummaryPayload() {
  return {
    generated_at: timestamp,
    window: { key: '24h', from: timestamp, to: timestamp, bucket: 'day', historical: true },
    total: {
      calls: 5,
      prompt_tokens: 8000,
      cached_input_tokens: 1200,
      completion_tokens: 3000,
      total_tokens: 11000,
      total_cost_usd: '0.123456',
    },
    by_user: [
      { group: 'user-a', calls: 3, total_tokens: 7000, total_cost_usd: '0.090000', dimensions: { owner_user_id: 'user-a' } },
      { group: 'user-b', calls: 2, total_tokens: 4000, total_cost_usd: '0.033456', dimensions: { owner_user_id: 'user-b' } },
    ],
    by_provider_model: [
      { group: 'openai|gpt-4o-mini', calls: 4, total_tokens: 9000, total_cost_usd: '0.100000', dimensions: { provider: 'openai', model: 'gpt-4o-mini' } },
    ],
    by_route_family: [
      { group: 'analysis', calls: 5, total_tokens: 11000, total_cost_usd: '0.123456', dimensions: { route_family: 'analysis' } },
    ],
    metadata: {
      read_only: true,
      no_external_calls: true,
      live_enforcement: false,
      data_sources: ['llm_cost_ledger', 'model_pricing_policies'],
      redaction: ['prompts_omitted', 'provider_payloads_omitted', 'credentials_omitted'],
      result_status_counts: { pricing_unknown: 1, pricing_inactive: 2 },
    },
  };
}

function modelPricingPoliciesPayload() {
  return {
    generated_at: timestamp,
    active_count: 1,
    policies: [
      {
        provider: 'openai',
        model: 'gpt-4o-mini',
        currency: 'USD',
        input_price_per_1m: '0.1500',
        cached_input_price_per_1m: '0.0750',
        output_price_per_1m: '0.6000',
        effective_from: '2026-01-01T00:00:00+08:00',
        effective_until: null,
        source_label: 'OpenAI pricing page',
        source_url: 'https://openai.com/api/pricing/',
        active: true,
      },
    ],
    metadata: {
      read_only: true,
      no_external_calls: true,
      live_enforcement: false,
      manual_maintenance: true,
      data_sources: ['model_pricing_policies'],
      redaction: ['credentials_omitted', 'provider_payloads_omitted'],
    },
  };
}

function providerCircuitMetadata() {
  return {
    read_only: true,
    no_external_calls: true,
    live_enforcement: false,
    provider_behavior_changed: false,
    market_cache_behavior_changed: false,
    data_sources: ['provider_circuit_state'],
    limit: 50,
    redaction: ['credentials_omitted', 'stack_details_omitted'],
    filters: {},
  };
}

function providerCircuitStatesPayload() {
  return {
    generated_at: timestamp,
    items: [
      {
        provider: 'mock-provider',
        provider_category: 'llm',
        route_family: 'analysis',
        state: 'closed',
        reason_bucket: 'success',
        cooldown_until: null,
        created_at: timestamp,
        updated_at: timestamp,
      },
    ],
    metadata: providerCircuitMetadata(),
  };
}

function providerCircuitEventsPayload() {
  return {
    generated_at: timestamp,
    items: [
      {
        provider: 'mock-provider',
        provider_category: 'llm',
        route_family: 'analysis',
        event_type: 'state_transition',
        from_state: 'half_open',
        to_state: 'closed',
        reason_bucket: 'success',
        request_count_bucket: '1-10',
        duration_bucket_ms: 250,
        failure_count_bucket: '0',
        created_at: timestamp,
      },
    ],
    metadata: providerCircuitMetadata(),
  };
}

function providerQuotaWindowsPayload() {
  return {
    generated_at: timestamp,
    items: [
      {
        provider: 'mock-provider',
        provider_category: 'llm',
        route_family: 'analysis',
        window_type: 'minute',
        window_start: timestamp,
        window_end: timestamp,
        request_count: 8,
        reserved_units: 4,
        consumed_units: 4,
        released_units: 0,
        rejected_count: 0,
        success_count: 8,
        failure_count: 0,
        timeout_count: 0,
        provider_429_count: 0,
        provider_403_count: 0,
        fallback_count: 1,
        probe_count: 1,
        cache_only_count: 0,
        stale_served_count: 0,
        created_at: timestamp,
        updated_at: timestamp,
      },
    ],
    metadata: providerCircuitMetadata(),
  };
}

function providerProbeEventsPayload() {
  return {
    generated_at: timestamp,
    items: [
      {
        provider: 'mock-provider',
        provider_category: 'llm',
        route_family: 'analysis',
        probe_type: 'half_open_probe',
        probe_source: 'diagnostic_scheduler',
        result_bucket: 'success',
        duration_bucket_ms: 120,
        created_at: timestamp,
      },
    ],
    metadata: providerCircuitMetadata(),
  };
}

function providerSlaReadinessPayload() {
  return {
    generated_at: timestamp,
    items: [
      {
        provider: 'mock-provider',
        provider_category: 'llm',
        route_family: 'analysis',
        readiness_state: 'dry_run_enabled',
        reason_code: 'mocked_e2e_readiness',
        credential_state: 'missing_credentials',
        live_providers_enabled: false,
        provider_enabled: true,
        credentials_present: false,
        dry_run_enabled: true,
        live_http_calls_enabled: false,
        broker_order_path_enabled: false,
        portfolio_mutation_path_enabled: false,
        tradeable_data: false,
        latency_bucket_ms: 120,
        latency_state: 'normal',
        error_rate: 0,
        error_state: 'normal',
        freshness_seconds: 60,
        freshness_state: 'fresh',
        recent_errors: [],
        trend_summary: {
          window_count_bucket: '1',
          request_count_bucket: '6_20',
          failure_count_bucket: '0',
          timeout_count_bucket: '0',
          provider_429_count_bucket: '0',
          provider_403_count_bucket: '0',
          latest_observation_at: timestamp,
        },
        circuit_advisory_state: 'observe',
        circuit_state_candidate: 'closed',
        live_enforcement: false,
        would_block_call: false,
        would_change_provider_order: false,
        would_change_fallback_behavior: false,
        no_external_calls: true,
      },
    ],
    metadata: providerCircuitMetadata(),
  };
}

function adminUsersPayload() {
  const user = {
    id: 'user-123',
    username: 'alice',
    display_name: 'Alice',
    role: 'user',
    is_active: true,
    created_at: timestamp,
    updated_at: timestamp,
    password_state: 'set',
    last_seen_at: timestamp,
    session_summary: { active_count: 1, expired_count: 0, revoked_count: 0, last_seen_at: timestamp, next_expires_at: timestamp },
    risk_badges: [{ code: 'sessionless', label: 'No sessions', severity: 'info', source: 'session' }],
    links: { self: '/api/v1/admin/users/user-123' },
  };

  return {
    items: [user],
    total: 1,
    limit: 50,
    offset: 0,
    has_more: false,
  };
}

function adminUserDetailPayload() {
  return {
    user: adminUsersPayload().items[0],
    sessions: [
      {
        session_handle: 'session-hash-01',
        status: 'active',
        created_at: timestamp,
        last_seen_at: timestamp,
        expires_at: timestamp,
        revoked_at: null,
      },
    ],
    data_links: {
      self: '/api/v1/admin/users/user-123',
      activity: '/api/v1/admin/users/user-123/activity',
      portfolio: '/api/v1/admin/users/user-123/portfolio-summary',
    },
    limitations: ['mocked_browser_harness_no_raw_session_values'],
  };
}

function adminPortfolioSummaryPayload() {
  return {
    user_id: 'user-123',
    account_count: 1,
    active_account_count: 1,
    base_currencies: ['USD'],
    accounts: [
      {
        id: 1,
        name: 'Alice Launch Portfolio',
        broker: 'IBKR',
        market: 'us',
        base_currency: 'USD',
        is_active: true,
        broker_account_handle: '***1234',
        created_at: timestamp,
        updated_at: timestamp,
        broker_account_ref: 'mock-canary-admin-broker-account',
        sync_metadata_json: {
          api_key: 'mock-canary-admin-api-key',
          access_token: 'mock-canary-admin-access-token',
          brokerOrderPayload: 'mock-canary-admin-broker-order-payload',
          place_order: 'mock-canary-admin-place-order-payload',
          raw_provider_payload: 'mock-canary-admin-raw-provider-payload',
        },
      },
    ],
    total_cash: { amount: 12500, currency: 'USD' },
    total_market_value: { amount: 32000, currency: 'USD' },
    total_equity: { amount: 44500, currency: 'USD' },
    realized_pnl: { amount: 420, currency: 'USD' },
    unrealized_pnl: { amount: 1800, currency: 'USD' },
    ledger_counts: { trades: 3, cash_events: 1, corporate_actions: 0 },
    broker_sync_summary: {
      connections: 1,
      statuses: { success: 1 },
      last_sync_at: timestamp,
      fx_stale: false,
    },
    limitations: ['read_only_projection', 'credentials_omitted'],
    excluded_cross_owner_canary: {
      account_name: 'Bob Admin Portfolio',
      symbol: 'MSFT-ADMIN-BOB-PRIVATE',
      broker_account_ref: 'mock-canary-bob-admin-broker-account',
      session_token: 'mock-canary-bob-admin-session-token',
    },
  };
}

function adminPortfolioHoldingsPayload() {
  return {
    items: [
      {
        account_id: 1,
        account_name: 'Alice Launch Portfolio',
        broker: 'IBKR',
        broker_account_handle: '***1234',
        symbol: 'AAPL',
        market: 'us',
        currency: 'USD',
        quantity: 12,
        avg_cost: 150,
        last_price: 180,
        market_value_base: 2160,
        unrealized_pnl_base: 360,
        valuation_currency: 'USD',
        fx_status: 'current',
        updated_at: timestamp,
      },
    ],
    total: 1,
    limit: 50,
    offset: 0,
    has_more: false,
    limitations: ['read_only_projection'],
    excluded_cross_owner_canary: [{ account_name: 'Bob Admin Portfolio', symbol: 'MSFT-ADMIN-BOB-PRIVATE' }],
  };
}

function adminPortfolioActivityPayload() {
  return {
    items: [
      {
        id_hash: 'activity-hash-1',
        type: 'trade',
        account_id: 1,
        account_name: 'Alice Launch Portfolio',
        event_date: '2026-05-05',
        symbol: 'AAPL',
        market: 'us',
        currency: 'USD',
        side: 'buy',
        quantity: 12,
        price: 150,
        amount: null,
        created_at: timestamp,
        payload_json: {
          execute_order: 'mock-canary-admin-execute-order-payload',
          broker_credentials: 'mock-canary-admin-broker-credentials',
        },
      },
    ],
    total: 1,
    limit: 30,
    offset: 0,
    has_more: false,
    summary: { trades: 3, cash_events: 1, corporate_actions: 0 },
    limitations: ['read_only_projection'],
  };
}

function systemConfigPayload() {
  const schema = (key: string, category: string, displayOrder: number) => ({
    key,
    title: key,
    description: 'Mocked admin browser harness field.',
    category,
    data_type: 'string',
    ui_control: 'text',
    is_sensitive: false,
    is_required: false,
    is_editable: true,
    options: [],
    validation: {},
    display_order: displayOrder,
    raw_editable: true,
    ui_visibility: 'raw',
    managed_by: null,
  });

  return {
    config_version: 'pw-config-v1',
    mask_token: '******',
    updated_at: timestamp,
    items: [
      { key: 'SCHEDULE_ENABLED', value: 'false', raw_value_exists: true, is_masked: false, schema: schema('SCHEDULE_ENABLED', 'base', 10) },
      { key: 'DUCKDB_ENABLED', value: 'false', raw_value_exists: true, is_masked: false, schema: schema('DUCKDB_ENABLED', 'quant', 20) },
      { key: 'DEFAULT_LLM_PROVIDER', value: 'mock', raw_value_exists: true, is_masked: false, schema: schema('DEFAULT_LLM_PROVIDER', 'ai_model', 30) },
    ],
  };
}

function duckdbHealthPayload() {
  return {
    status: 'disabled',
    enabled: false,
    database_path: '/mock/redacted/duckdb.db',
    fallback_reason: 'disabled_for_playwright',
    checked_at: timestamp,
  };
}

function duckdbCoveragePayload() {
  return {
    status: 'disabled',
    database_path: '/mock/redacted/duckdb.db',
    total_ohlcv_rows: 0,
    total_factor_rows: 0,
    symbol_count: 0,
    latest_factor_date: null,
    min_trade_date: null,
    max_trade_date: null,
    symbols: [],
    empty_reason: 'DuckDB disabled in browser harness.',
  };
}

export async function installAdminAuthHarness(
  page: Page,
  options: MockAdminUserOptions = {},
): Promise<AdminAuthHarness> {
  const currentUser = createMockAdminUser(options);
  const calls: string[] = [];
  const requests = createRequestLog(calls);

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    calls.push(`${method} ${path}`);

    if (method === 'GET' && path === '/api/v1/auth/status') {
      return fulfillJson(route, createMockAuthStatus(currentUser));
    }
    if (method === 'GET' && path === '/api/v1/auth/me') {
      return fulfillJson(route, currentUser);
    }
    if (method === 'GET' && path === '/api/v1/agent/status') {
      return fulfillJson(route, { enabled: false });
    }
    if (method === 'GET' && path === '/api/v1/admin/cost/duplicate-summary') {
      return fulfillJson(route, adminCostSummaryPayload());
    }
    if (method === 'POST' && path === '/api/v1/admin/cost/quota-dry-run') {
      return fulfillJson(route, quotaDryRunPayload());
    }
    if (method === 'GET' && path === '/api/v1/admin/cost/llm-ledger-summary') {
      return fulfillJson(route, llmLedgerSummaryPayload());
    }
    if (method === 'GET' && path === '/api/v1/admin/cost/model-pricing-policies') {
      return fulfillJson(route, modelPricingPoliciesPayload());
    }
    if (method === 'GET' && path === '/api/v1/admin/providers/circuits') {
      return fulfillJson(route, providerCircuitStatesPayload());
    }
    if (method === 'GET' && path === '/api/v1/admin/providers/circuits/events') {
      return fulfillJson(route, providerCircuitEventsPayload());
    }
    if (method === 'GET' && path === '/api/v1/admin/providers/quota-windows') {
      return fulfillJson(route, providerQuotaWindowsPayload());
    }
    if (method === 'GET' && path === '/api/v1/admin/providers/probe-events') {
      return fulfillJson(route, providerProbeEventsPayload());
    }
    if (method === 'GET' && path === '/api/v1/admin/providers/sla-readiness') {
      return fulfillJson(route, providerSlaReadinessPayload());
    }
    if (method === 'GET' && path === '/api/v1/admin/users') {
      return fulfillJson(route, adminUsersPayload());
    }
    if (method === 'GET' && path === '/api/v1/admin/users/user-123') {
      return fulfillJson(route, adminUserDetailPayload());
    }
    if (method === 'GET' && path === '/api/v1/admin/users/user-123/portfolio-summary') {
      return fulfillJson(route, adminPortfolioSummaryPayload());
    }
    if (method === 'GET' && path === '/api/v1/admin/users/user-123/holdings') {
      return fulfillJson(route, adminPortfolioHoldingsPayload());
    }
    if (method === 'GET' && path === '/api/v1/admin/users/user-123/portfolio-activity') {
      return fulfillJson(route, adminPortfolioActivityPayload());
    }
    if (method === 'GET' && path === '/api/v1/system/config') {
      return fulfillJson(route, systemConfigPayload());
    }
    if (method === 'GET' && path === '/api/v1/quant/duckdb/health') {
      return fulfillJson(route, duckdbHealthPayload());
    }
    if (method === 'GET' && path === '/api/v1/quant/duckdb/coverage') {
      return fulfillJson(route, duckdbCoveragePayload());
    }

    return fulfillJson(route, { error: `Unhandled admin auth harness route: ${method} ${path}` }, 500);
  });

  return { currentUser, requests };
}

export async function openAdminRouteWithHarness(
  page: Page,
  path: string,
  options: MockAdminUserOptions = {},
): Promise<AdminAuthHarness> {
  const harness = await installAdminAuthHarness(page, options);
  await page.goto(path);
  await page.waitForLoadState('domcontentloaded');
  await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
  return harness;
}

export async function expectNoHorizontalOverflow(page: Page) {
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

export async function expectNoRawSecretLikeText(page: Page) {
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(/(?:sk-[a-z0-9_-]{12,}|bearer\s+[a-z0-9._-]+|api[_-]?key\s*[=:]|password\s*[=:]|session[_-]?id\s*[=:]|secret\s*[=:])/i);
}

export const test = base.extend<AdminAuthFixtures>({
  consoleErrors: [async ({ page }, use) => {
    const consoleErrors: string[] = [];

    page.on('console', (message) => {
      if (message.type() === 'error' && !message.text().includes('favicon.ico')) {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => {
      consoleErrors.push(error.message);
    });

    await use(consoleErrors);

    expect(consoleErrors).toEqual([]);
  }, { auto: true }],
});

export { expect };
export type { AdminCapability };
