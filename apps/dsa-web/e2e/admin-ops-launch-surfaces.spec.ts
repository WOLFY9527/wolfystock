import { expect, test, type Page, type Route } from './fixtures/adminAuth';
import {
  expectNoHorizontalOverflow,
  expectNoRawSecretLikeText,
  installAdminAuthHarness,
} from './fixtures/adminAuth';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

const timestamp = '2026-05-06T10:30:00+08:00';

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

function adminLogHealthSummary() {
  return {
    total_events: 4,
    failed_events: 1,
    warning_events: 1,
    slow_events: 1,
    failure_rate: 0.25,
    status: 'degraded',
    failures_by_category: [{ key: 'data_source', label: 'data_source', count: 1 }],
    failures_by_provider: [{ key: 'finnhub', label: 'finnhub', count: 1 }],
    failures_by_reason: [{ key: 'timeout', label: 'timeout', count: 1 }],
    top_recent_errors: [
      { id: 'market-card-failed', event: 'MarketSentimentCard', category: 'data_source', provider: 'finnhub', reason: 'timeout', error_summary: 'provider timeout token=***', started_at: timestamp, status: 'failed' },
    ],
    actor_breakdown: [{ key: 'admin', label: 'admin', count: 2 }],
    latest_critical_error: { id: 'market-card-failed', event: 'MarketSentimentCard', category: 'data_source', provider: 'finnhub', reason: 'timeout', error_summary: 'provider timeout token=***', started_at: timestamp, status: 'failed' },
  };
}

function businessEventsPayload() {
  return {
    total: 2,
    limit: 20,
    offset: 0,
    has_more: false,
    health_summary: adminLogHealthSummary(),
    items: [
      {
        id: 'analysis-tsla',
        event: 'TSLA',
        category: 'analysis',
        type: 'stock_analysis',
        event_type: 'stock_analysis',
        status: 'partial',
        summary: 'TSLA 分析完成，数据源部分降级',
        symbol: 'TSLA',
        market: 'US',
        actor_type: 'user',
        actor_label: 'alice',
        context_label: 'TSLA',
        provider: 'newsapi',
        source: 'Yahoo',
        reason: 'timeout',
        error_summary: 'News API timeout token=***',
        request_id: 'req-tsla-123456789',
        trace_id: 'trace-tsla-abcdef',
        root_cause_summary: 'News API timeout token=***',
        step_trace_available: true,
        started_at: timestamp,
        duration_ms: 12345,
        step_count: 4,
        success_step_count: 3,
        failed_step_count: 1,
        skipped_step_count: 0,
        unknown_step_count: 0,
      },
      {
        id: 'market-card-failed',
        event: 'MarketSentimentCard',
        category: 'data_source',
        type: 'market_overview_fetch',
        event_type: 'ExternalSourceTimeout',
        status: 'failed',
        summary: '市场情绪卡片刷新失败',
        context_label: 'MarketSentimentCard',
        provider: 'finnhub',
        source: 'market_overview',
        reason: 'timeout',
        error_summary: 'provider timeout token=***',
        request_id: 'req-market-card-123456',
        trace_id: 'trace-market-card-abcdef',
        step_trace_available: false,
        started_at: timestamp,
        duration_ms: 0,
        step_count: 0,
        success_step_count: 0,
        failed_step_count: 0,
        skipped_step_count: 0,
        unknown_step_count: 0,
      },
    ],
  };
}

function adminLogStoragePayload() {
  return {
    total_log_count: 32,
    total_event_count: 118,
    oldest_log_timestamp: '2026-05-01T10:30:00+08:00',
    newest_log_timestamp: timestamp,
    retention_days: 90,
    minimum_retention_days: 7,
    retention_cutoff: '2026-02-06T10:30:00+08:00',
    logs_older_than_retention_count: 0,
    storage_size_bytes: 1048576,
    storage_size_label: '1 MB',
    storage_size_available: true,
    measurement_scope: 'sqlite_database_file',
    measurement_status: 'available',
    storage_soft_limit_bytes: 536870912,
    storage_hard_limit_bytes: 1073741824,
    capacity_cleanup_recommended: false,
    auto_cleanup_enabled: false,
    auto_cleanup_performed: false,
    warning_threshold_count: 50000,
    critical_threshold_count: 100000,
    status: 'ok',
    status_reasons: [],
    recommended_cleanup_action: 'No cleanup needed.',
  };
}

function sessionsPayload() {
  return {
    total: 1,
    summary: { error_count: 1, warning_count: 1, data_source_failure_count: 1, slow_request_count: 1, health_summary: adminLogHealthSummary() },
    items: [
      {
        session_id: 'session-analysis-tsla',
        code: 'TSLA',
        name: 'TSLA analysis',
        overall_status: 'partial_success',
        truth_level: 'recorded',
        started_at: timestamp,
        ended_at: timestamp,
        readable_summary: {
          actor_display: 'alice',
          actor_role: 'admin',
          subsystem: 'analysis',
          operation_category: 'single_stock_analysis',
          operation_type: '单股票分析',
          operation_target: 'TSLA',
          operation_status: '部分失败',
          top_failure_reason: '数据源超时',
          summary_paragraph: '数据源降级，报告部分完成。',
        },
      },
    ],
  };
}

function marketProviderOperationsPayload() {
  return {
    generated_at: timestamp,
    window: { key: '24h', since: '24h' },
    summary: {
      total_items: 2,
      live_count: 1,
      cache_count: 0,
      stale_count: 0,
      fallback_count: 1,
      partial_count: 0,
      unavailable_count: 0,
      error_count: 0,
      refreshing_count: 1,
      event_count: 2,
      failure_count: 1,
      fallback_event_count: 1,
      stale_event_count: 0,
      slow_event_count: 1,
    },
    items: [
      {
        provider: 'sina',
        source_label: '新浪财经',
        source_type: 'public_api',
        domain: 'equity_index',
        endpoint: '/api/v1/market/cn-indices',
        card: 'ChinaIndicesCard',
        cache_key: 'cn_indices',
        status: 'live',
        freshness: 'live',
        as_of: timestamp,
        updated_at: timestamp,
        last_successful_at: timestamp,
        last_known_good_age_minutes: 2,
        latency_ms: 128,
        is_fallback: false,
        is_stale: false,
        is_refreshing: false,
        is_from_snapshot: false,
        fallback_used: false,
        warning: null,
        error_summary: null,
        admin_log_drill_through: { label: '查看 Admin Logs', route: '/zh/admin/logs', query: { since: '24h', provider: 'sina' } },
      },
      {
        provider: 'fallback',
        source_label: '备用快照',
        source_type: 'snapshot',
        domain: 'sentiment',
        endpoint: '/api/v1/market/market-briefing',
        card: 'MarketBriefingCard',
        cache_key: 'market_briefing',
        status: 'fallback',
        freshness: 'fallback',
        as_of: null,
        updated_at: timestamp,
        last_successful_at: timestamp,
        last_known_good_age_minutes: 60,
        latency_ms: null,
        is_fallback: true,
        is_stale: false,
        is_refreshing: true,
        is_from_snapshot: true,
        fallback_used: true,
        warning: '备用快照，不代表当前行情',
        error_summary: 'provider timeout token=***',
        admin_log_drill_through: { label: '查看 Admin Logs', route: '/zh/admin/logs', query: { since: '24h', provider: 'fallback' }, event_id: 'evt-1' },
      },
    ],
    event_rollups: [],
    cache_states: [],
    limitations: ['admin_logs_no_degraded_market_events_in_window'],
    admin_log_drill_through: { label: '查看 Admin Logs', route: '/zh/admin/logs', query: { since: '24h' } },
    metadata: { source: 'mocked_playwright', read_only: true, external_provider_calls: false, cache_mutation: false },
  };
}

async function installAdminOpsMocks(page: Page) {
  await installAdminAuthHarness(page);
  await page.route('**/api/v1/admin/logs/storage/summary', (route) => fulfillJson(route, adminLogStoragePayload()));
  await page.route('**/api/v1/admin/logs/sessions**', (route) => fulfillJson(route, sessionsPayload()));
  await page.route('**/api/v1/admin/logs**', (route) => {
    if (route.request().method() === 'GET') {
      return fulfillJson(route, businessEventsPayload());
    }
    return fulfillJson(route, { mode: 'retention', dry_run: true, matched_log_count: 0, matched_event_count: 0, deleted_log_count: 0, deleted_event_count: 0, additional_cleanup_needed: false });
  });
  await page.route('**/api/v1/admin/market-providers/operations**', (route) => fulfillJson(route, marketProviderOperationsPayload()));
}

async function visibleText(page: Page) {
  return page.locator('body').innerText();
}

async function expectClosedDetails(page: Page, testId?: string) {
  const details = testId ? page.getByTestId(testId) : page.locator('details');
  const count = await details.count();
  for (let index = 0; index < count; index += 1) {
    await expect(details.nth(index)).not.toHaveJSProperty('open', true);
  }
}

const routes = [
  {
    key: 'logs',
    path: '/zh/admin/logs',
    ready: 'admin-logs-workspace',
    first: ['定位失败与审计线索', '当前状态', '下一步', '整体状态'],
    secondary: ['二级细节：日志容量与破坏性清理'],
  },
  {
    key: 'cost',
    path: '/zh/admin/cost-observability',
    ready: 'admin-cost-observability-page',
    first: ['成本观测', '需关注', '下一步', '压力、异常、归属', '配额试运行诊断'],
    secondary: [],
    secondaryButtons: [],
    disclosureCountMin: 2,
  },
  {
    key: 'evidence',
    path: '/zh/admin/evidence-workflow',
    ready: 'admin-evidence-workflow-page',
    first: ['证据工作流复核', '当前状态', '下一步', '操作员证据路径'],
    secondary: [],
    secondaryButtons: [],
    disclosureCountMin: 4,
  },
  {
    key: 'market-providers',
    path: '/zh/admin/market-providers',
    ready: 'market-provider-operations-page',
    first: ['市场数据源运维', '当前状态', '需关注', '下一步', '数据源运维矩阵'],
    secondary: ['二级细节：缓存、事件回卷、限制与响应形状'],
  },
  {
    key: 'provider-circuits',
    path: '/zh/admin/provider-circuits',
    ready: 'admin-provider-circuit-diagnostics-page',
    first: ['Provider 熔断诊断', '生产调用', '当前阻断', '下一步', 'Provider SLA / 凭证就绪'],
    secondary: ['二级细节：探测、事件、配额窗口、路由 bucket'],
  },
  {
    key: 'system-settings',
    path: '/zh/settings/system',
    ready: 'system-settings-page',
    first: ['系统设置', '当前状态', '需关注', '下一步'],
    secondary: ['深层配置', '原始字段', '危险系统动作'],
  },
];

const routeFilter = (process.env.WOLFYSTOCK_ADMIN_OPS_ROUTE_FILTER || '')
  .split(',')
  .map((value) => value.trim())
  .filter(Boolean);

const activeRoutes = routeFilter.length
  ? routes.filter((route) => routeFilter.includes(route.key))
  : routes;

test.describe('admin ops launch surfaces', () => {
  for (const viewport of viewports) {
    test(`operator-first hierarchy stays clean at ${viewport.width}x${viewport.height}`, async ({ page }) => {
      await page.setViewportSize(viewport);

      for (const route of activeRoutes) {
        await installAdminOpsMocks(page);
        await page.goto(route.path);
        await page.waitForLoadState('domcontentloaded');
        await expect(page.getByTestId(route.ready)).toBeVisible({ timeout: 15_000 });
        await expectNoHorizontalOverflow(page);
        await expectNoRawSecretLikeText(page);
        const bodyText = await visibleText(page);
        for (const text of route.first) {
          expect(bodyText).toContain(text);
        }
        for (const text of route.secondary) {
          expect(bodyText).toContain(text);
        }
        for (const text of route.secondaryButtons || []) {
          await expect(page.getByRole('button', { name: `展开 ${text}` })).toBeVisible();
        }
        if (route.disclosureCountMin) {
          const disclosureCount = await page.locator('[data-terminal-primitive="disclosure"]').count();
          expect(disclosureCount).toBeGreaterThanOrEqual(route.disclosureCountMin);
        }
        await expectClosedDetails(page);
        await page.unrouteAll({ behavior: 'ignoreErrors' });
      }
    });
  }
});
