import { expect, expectNoHorizontalOverflow, test, type Page, type Route } from './fixtures/adminAuth';
import {
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
      { id: 'market-card-failed', event: 'MarketSentimentCard', category: 'data_source', provider: 'finnhub', reason: 'timeout', error_summary: 'provider timeout（已脱敏）', started_at: timestamp, status: 'failed' },
    ],
    actor_breakdown: [{ key: 'admin', label: 'admin', count: 2 }],
    latest_critical_error: { id: 'market-card-failed', event: 'MarketSentimentCard', category: 'data_source', provider: 'finnhub', reason: 'timeout', error_summary: 'provider timeout（已脱敏）', started_at: timestamp, status: 'failed' },
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
        error_summary: 'News API timeout（已脱敏）',
        request_id: 'req-tsla-123456789',
        trace_id: 'trace-tsla-abcdef',
        root_cause_summary: 'News API timeout（已脱敏）',
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
        error_summary: 'provider timeout（已脱敏）',
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
        error_summary: 'provider timeout（已脱敏）',
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

function providerOperationsMatrixPayload() {
  return {
    generated_at: timestamp,
    diagnostic_only: true,
    rows: [
      {
        provider_id: 'market_fixture',
        provider_name: 'Market fixture',
        source_label: 'Local audit fixture',
        provider_category: 'market',
        source_type: 'admin_fixture',
        source_tier: 'local',
        trust_level: 'operator_check',
        freshness_expectation: 'same_day',
        runtime_state: 'ready',
        credential_state: 'not_required',
        dependency_state: 'ready',
        enabled_by_default: true,
        observation_only: false,
        score_contribution_allowed: true,
        source_authority_allowed: true,
        score_eligible: true,
        inert_metadata_only: false,
        paid_data_likely_required: false,
        key_required: false,
        no_default_live_http_calls: true,
        cache_required: false,
        supported_capabilities: ['market_overview'],
        affected_surfaces: ['Market Overview'],
        product_affected_surfaces: ['Market Overview'],
        router_reason_codes: [],
        reason_codes: [],
        fulfilled_metrics: ['readiness'],
        missing_metrics: [],
        authority_basis: 'Local audit fixture for admin route density.',
        universe: 'US',
        coverage_count: 1,
        diagnostic_only: true,
      },
    ],
    summary: {
      total_rows: 1,
      observation_only_rows: 0,
      inert_metadata_only_rows: 0,
      missing_provider_rows: 0,
      score_eligible_rows: 1,
      paid_data_likely_required_rows: 0,
    },
    metadata: {
      source: 'local_audit_fixture',
      read_only: true,
      diagnostic_only: true,
      external_provider_calls: false,
      network_calls_enabled: false,
      cache_mutation: false,
      secret_values_included: false,
      raw_provider_payloads_included: false,
      readiness_status: 'ready',
      row_count: 1,
    },
  };
}

function marketDataReadinessPayload() {
  return {
    readiness_status: 'ready',
    diagnostic_only: true,
    provider_runtime_called: false,
    network_calls_enabled: false,
    representative_symbols: ['ORCL'],
    checks: [
      {
        id: 'market_fixture_ready',
        status: 'ready',
        severity: 'info',
        user_facing_message: '本地审核样例已覆盖市场数据读取。',
        remediation_hint: null,
        affects_surfaces: ['Market Overview'],
        product_affected_surfaces: ['Market Overview'],
        secret_configured: false,
        details: { read_only: true },
      },
    ],
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
  await page.route('**/api/v1/admin/providers/operations-matrix', (route) => fulfillJson(route, providerOperationsMatrixPayload()));
  await page.route('**/api/v1/market/data-readiness**', (route) => fulfillJson(route, marketDataReadinessPayload()));
  await page.route('**/api/v1/admin/market-providers/operations**', (route) => fulfillJson(route, marketProviderOperationsPayload()));
}

async function visibleText(page: Page) {
  return page.locator('body').innerText();
}

async function expectL0OverviewStrip(page: Page, dataTestId: string) {
  const strip = page.getByTestId(dataTestId);
  await expect(strip).toBeVisible();
  await expect(strip).toContainText('L0 总览');
  await expect(strip).toContainText('信任状态');
  await expect(strip).toContainText('影响范围');
  await expect(strip).toContainText('建议动作');
  await expect(strip).toContainText('证据参考');
  await expect(strip).toContainText('最近更新');
}

async function expectClosedDisclosureButtons(page: Page) {
  await expect(page.getByRole('button', { name: /^收起 / })).toHaveCount(0);

  const expandButtons = page.getByRole('button', { name: /^展开 / });
  const count = await expandButtons.count();
  for (let index = 0; index < count; index += 1) {
    await expect(expandButtons.nth(index)).toHaveAttribute('aria-expanded', 'false');
  }
}

const forbiddenDefaultLeakPattern =
  /raw\s+(payload|response)|debug\s+(payload|response|panel)|provider\s+payload|request\s+body|stack\s+trace|prompt\s+(text|payload)|router\s+(state|payload)|\.env|token\s*[=:]|secret\s*[=:]|password\s*[=:]|bearer\s+[a-z0-9._-]+|api[_\s-]?key|credential\s*[=:]/i;

const routes = [
  {
    key: 'logs',
    path: '/zh/admin/logs',
    ready: 'admin-logs-workspace',
    l0: 'admin-logs-l0-overview-strip',
    first: ['定位失败与审计线索', '当前状态', '下一步', '整体状态'],
    secondary: ['L4 日志容量建议与显式清理：容量 / 保留期 / 预览'],
    drillLink: {
      label: '查看数据源维护',
      href: /^\/zh\/admin\/market-providers\?surface=market_overview$/,
    },
  },
  {
    key: 'cost',
    path: '/zh/admin/cost-observability',
    ready: 'admin-cost-observability-page',
    l0: 'admin-cost-l0-overview-strip',
    first: ['成本观测', '需关注', '下一步', '压力、异常、归属', 'L2 配额 / 成本运维：配额试运行'],
    secondary: [],
    secondaryButtons: [],
    groupings: ['L2 / Quota-Cost Ops'],
    disclosures: [],
    drillLink: {
      label: '查看数据源维护',
      href: /^\/zh\/admin\/market-providers\?surface=market_overview$/,
    },
  },
  {
    key: 'evidence',
    path: '/zh/admin/evidence-workflow',
    ready: 'admin-evidence-workflow-page',
    l0: 'admin-evidence-l0-overview-strip',
    first: ['证据工作流复核', '人工门禁', '操作员证据路径', 'L0 运维结论'],
    secondary: [],
    secondaryButtons: [],
    disclosures: [],
    drillLink: {
      label: '查看相关日志',
      href: /^\/zh\/admin\/logs\?tab=business&query=evidence&since=24h$/,
    },
  },
  {
    key: 'market-providers',
    path: '/zh/admin/market-providers',
    ready: 'market-provider-operations-page',
    l0: 'market-provider-l0-overview-strip',
    first: ['数据源维护路线图', '数据源健康', '熔断状态', '失败率', '数据源运维'],
    secondary: [],
    secondaryButtons: [],
    groupings: ['L1 / 数据源就绪', 'L2 / 运维矩阵', 'L2 / 本地就绪', 'L2 / 配额与成本'],
    testIds: [
      'market-provider-readability-summary',
      'market-provider-source-gap-disclosure',
      'market-provider-matrix-disclosure',
      'market-provider-diagnostics-disclosure',
    ],
    disclosures: [],
    drillLink: {
      label: '查看证据工作流',
      href: /^\/zh\/admin\/evidence-workflow\?ref=provider_bundle#schema-ref$/,
    },
  },
  {
    key: 'provider-circuits',
    path: '/zh/admin/provider-circuits',
    ready: 'admin-provider-circuit-diagnostics-page',
    l0: 'provider-circuit-l0-overview-strip',
    first: ['Provider 熔断诊断', '生产调用', 'SLA 阻断', '下一步', '优先处理项'],
    secondary: [],
    secondaryButtons: [],
    groupings: ['L2 分组诊断：熔断状态 / 事件 / 配额 / 探测 / SLA（已脱敏摘要）'],
    disclosures: ['L2 分组诊断：熔断状态 / 事件 / 配额 / 探测 / SLA（已脱敏摘要）'],
    drillLink: {
      label: '查看成本观测',
      href: /^\/zh\/admin\/cost-observability\?window=24h&area=provider$/,
    },
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
        await expectNoRawSecretLikeText(page);
        const bodyText = await visibleText(page);
        for (const text of route.first) {
          expect(bodyText).toContain(text);
        }
        for (const text of route.secondary) {
          expect(bodyText).toContain(text);
        }
        await expectL0OverviewStrip(page, route.l0);
        for (const text of route.groupings || []) {
          expect(bodyText).toContain(text);
        }
        for (const testId of route.testIds || []) {
          await expect(page.getByTestId(testId)).toBeVisible();
        }
        for (const text of route.disclosures || []) {
          expect(bodyText).toContain(text);
        }
        expect(bodyText).not.toMatch(forbiddenDefaultLeakPattern);
        if (route.drillLink) {
          await expect(page.getByRole('link', { name: route.drillLink.label }).first()).toHaveAttribute('href', route.drillLink.href);
        }
        for (const text of route.secondaryButtons || []) {
          await expect(page.getByRole('button', { name: `展开 ${text}` })).toBeVisible();
        }
        if (route.disclosureCountMin) {
          const disclosureCount = await page.getByRole('button', { name: /^展开 / }).count();
          expect(disclosureCount).toBeGreaterThanOrEqual(route.disclosureCountMin);
        }
        await expectClosedDisclosureButtons(page);
        await expectNoHorizontalOverflow(page);
        await page.unrouteAll({ behavior: 'ignoreErrors' });
      }
    });
  }
});
