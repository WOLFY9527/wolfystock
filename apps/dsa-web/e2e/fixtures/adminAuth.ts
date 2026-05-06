import { expect, test as base, type Page, type Route } from '@playwright/test';
import {
  createMockAdminUser,
  createMockAuthStatus,
  type AdminCapability,
  type MockAdminUserOptions,
} from '../../src/test-utils/adminAuthHarness';
import type { CurrentUser } from '../../src/api/auth';

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

function adminUsersPayload() {
  return {
    items: [{
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
    }],
    total: 1,
    limit: 50,
    offset: 0,
    has_more: false,
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
    if (method === 'GET' && path === '/api/v1/admin/users') {
      return fulfillJson(route, adminUsersPayload());
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

export { expect, base as test };
export type { AdminCapability };
