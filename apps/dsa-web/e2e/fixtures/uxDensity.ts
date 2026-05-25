import { expect, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

export type UxDensityViewport = {
  width: number;
  height: number;
};

export type UxDensityRoute = {
  path: string;
  label: string;
  harness: 'public' | 'product' | 'portfolio' | 'admin';
};

export type UxDensityAudience = 'consumer' | 'admin';

export type UxDensityTermHit = {
  term: string;
  count: number;
};

export type UxDensityMetric = {
  route: string;
  label: string;
  viewport: UxDensityViewport;
  finalUrl: string;
  approximateVisibleCardCount: number;
  visibleButtonInputCount: number;
  debugProviderRawTermHits: UxDensityTermHit[];
  strictBackendDiagnosticTokenHits: UxDensityTermHit[];
  rawUnsafePayloadTermHits: UxDensityTermHit[];
  glossaryHelpAffordanceCount: number;
  horizontalOverflow: boolean;
  consolePageErrors: string[];
  firstMeaningfulHeadingText: string | null;
  firstViewportContentOrder: string[];
};

export const uxDensityViewports: UxDensityViewport[] = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

export const uxDensityRoutes: UxDensityRoute[] = [
  { path: '/zh', label: 'Home', harness: 'public' },
  { path: '/zh/scanner', label: 'Scanner', harness: 'public' },
  { path: '/zh/watchlist', label: 'Watchlist', harness: 'public' },
  { path: '/zh/market-overview', label: 'Market Overview', harness: 'public' },
  { path: '/zh/market/liquidity-monitor', label: 'Liquidity Monitor', harness: 'public' },
  { path: '/zh/market/rotation-radar', label: 'Rotation Radar', harness: 'public' },
  { path: '/options-lab', label: 'Options Lab', harness: 'product' },
  { path: '/zh/backtest/results/34', label: 'Backtest Result 34', harness: 'public' },
  { path: '/zh/portfolio', label: 'Portfolio', harness: 'portfolio' },
  { path: '/zh/admin/logs', label: 'Admin Logs', harness: 'admin' },
  { path: '/zh/admin/cost-observability', label: 'Admin Cost Observability', harness: 'admin' },
  { path: '/zh/admin/evidence-workflow', label: 'Admin Evidence Workflow', harness: 'admin' },
  { path: '/zh/admin/market-providers', label: 'Admin Market Providers', harness: 'admin' },
  { path: '/zh/admin/provider-circuits', label: 'Admin Provider Circuits', harness: 'admin' },
];

const reportSchemaVersion = 'wolfystock_ux_density_audit_v1';
const rawSecretLikePattern =
  /(?:bearer\s+[a-z0-9._-]{12,}|sk-[a-z0-9_-]{12,}|ghp_[a-z0-9_]{12,}|xox[baprs]-[a-z0-9-]{12,}|api[_\s-]?key\s*[=:]\s*\S+|password\s*[=:]\s*\S+|session[_\s-]?id\s*[=:]\s*\S+|cookie\s*[=:]\s*\S+|secret\s*[=:]\s*\S+|access[_\s-]?token\s*[=:]\s*\S+|refresh[_\s-]?token\s*[=:]\s*\S+)/i;

const strictBackendDiagnosticTokens = [
  'sourceAuthorityAllowed',
  'scoreContributionAllowed',
  'observationOnly',
  'reasonCode',
  'reasonFamilies',
  'routeRejectedReasonCodes',
  'fallback_static',
  'synthetic_fixture',
  'official_public',
  'authorized_licensed_feed',
  'public_proxy',
  'unofficial_proxy',
  'raw_payload',
  'provider_payload',
  'debug payload',
  'raw JSON',
  'coverageDiagnostics',
  'liquidityImpulseSynthesis',
  'evidenceQuality',
  'sourceMetadata',
  'providerRuntimeChanged',
  'marketCacheMutation',
  'provider_unavailable',
  'score_contribution_not_allowed',
  'source_authority_router_rejected',
  'official_or_authorized',
  'yfinance_proxy',
];

const rawUnsafePayloadTokens = ['raw_payload', 'provider_payload', 'debug payload', 'raw JSON'];

function uxDensityAudienceForRoute(route: Pick<UxDensityRoute, 'harness'>): UxDensityAudience {
  return route.harness === 'admin' ? 'admin' : 'consumer';
}

function formatTermHits(hits: UxDensityTermHit[]) {
  return hits.map((hit) => `${hit.term} ×${hit.count}`).join(', ');
}

export function createConsolePageErrorCollector(page: Page): string[] {
  const errors: string[] = [];

  page.on('console', (message) => {
    if (message.type() === 'error' && !message.text().includes('favicon.ico')) {
      errors.push(message.text());
    }
  });
  page.on('pageerror', (error) => {
    errors.push(error.message);
  });

  return errors;
}

export async function installUxDensityAuthenticatedSession(page: Page) {
  const currentUser = {
    id: 'user-1',
    username: 'wolfy-user',
    displayName: 'Wolfy User',
    role: 'user',
    isAdmin: false,
    isAuthenticated: true,
    transitional: false,
    authEnabled: true,
  };

  await page.route('**/api/v1/auth/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        authEnabled: true,
        loggedIn: true,
        passwordSet: true,
        passwordChangeable: true,
        setupState: 'enabled',
        currentUser,
      }),
    });
  });
  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(currentUser),
    });
  });
}

export async function installUxDensityPublicMocks(page: Page) {
  const timestamp = '2026-05-09T10:30:00+08:00';

  await page.route('**/api/v1/stocks/ORCL/history**', async (route) => {
    if (route.request().method() !== 'GET') {
      return route.fallback();
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        stock_code: 'ORCL',
        stock_name: 'Oracle',
        period: 'daily',
        source: 'fixture_history',
        source_confidence: {
          source: 'fixture_history',
          source_label: '本地审核样例',
          as_of: timestamp,
          freshness: 'available',
          is_fallback: false,
          is_stale: false,
          is_partial: false,
          is_synthetic: false,
          is_unavailable: false,
          confidence_weight: 1,
          coverage: 1,
        },
        data: [
          { date: '2026-05-04', open: 188.4, high: 191.2, low: 187.9, close: 190.6, volume: 24100000, change_percent: 0.8 },
          { date: '2026-05-05', open: 190.8, high: 193.1, low: 189.7, close: 192.4, volume: 23800000, change_percent: 0.94 },
          { date: '2026-05-06', open: 192.1, high: 194.5, low: 191.2, close: 193.8, volume: 22100000, change_percent: 0.73 },
          { date: '2026-05-07', open: 193.5, high: 195.0, low: 191.8, close: 192.9, volume: 21600000, change_percent: -0.46 },
          { date: '2026-05-08', open: 193.0, high: 196.2, low: 192.4, close: 195.7, volume: 24400000, change_percent: 1.45 },
        ],
      }),
    });
  });

  await page.route('**/api/v1/market/liquidity-monitor', async (route) => {
    if (route.request().method() !== 'GET') {
      return route.fallback();
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        endpoint: '/api/v1/market/liquidity-monitor',
        generated_at: timestamp,
        score: {
          value: 64,
          regime: 'supportive',
          confidence: 0.76,
          included_indicator_count: 2,
          possible_indicator_weight: 2,
          included_indicator_weight: 2,
        },
        freshness: {
          status: 'live',
          weakest_indicator_freshness: 'live',
          latest_as_of: timestamp,
        },
        indicators: [
          {
            key: 'policy_liquidity',
            label: 'Policy liquidity',
            status: 'live',
            freshness: 'live',
            included_in_score: true,
            score_contribution: 0.38,
            score_weight: 0.5,
            summary: '政策流动性保持稳定。',
            updated_at: timestamp,
          },
          {
            key: 'market_breadth',
            label: 'Market breadth',
            status: 'live',
            freshness: 'live',
            included_in_score: true,
            score_contribution: 0.26,
            score_weight: 0.5,
            summary: '市场宽度对流动性读数形成支撑。',
            updated_at: timestamp,
          },
        ],
        liquidity_impulse_synthesis: {
          liquidity_impulse: 'expanding',
          impulse_label: 'Liquidity is improving',
          subtype: 'broad_support',
          confidence: 0.76,
          confidence_label: 'medium',
          pillar_scores: { policy_liquidity: 66, market_breadth: 62 },
          direction_score: 64,
          dominant_drivers: [],
          counter_evidence: [],
          data_gaps: [],
          narrative_bullets: ['流动性读数可用，当前适合观察。'],
          evidence_quality: {},
          not_investment_advice: true,
        },
        advisory_disclosure: '仅用于研究观察，不构成投资建议。',
        source_metadata: {
          external_provider_calls: false,
          provider_runtime_changed: false,
          market_cache_mutation: false,
        },
      }),
    });
  });
}

export async function installUxDensityAdminMocks(page: Page) {
  const timestamp = '2026-05-09T10:30:00+08:00';

  await page.route('**/api/v1/admin/logs**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathName = url.pathname;
    const method = request.method();

    if (method === 'GET' && pathName === '/api/v1/admin/logs') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: 2,
          limit: 50,
          offset: 0,
          has_more: false,
          health_summary: {
            total: 2,
            by_status: { success: 2 },
            by_category: { analysis: 1, admin: 1 },
            error_count: 0,
            warning_count: 0,
          },
          items: [
            {
              id: 'evt-analysis-1',
              event_id: 'evt-analysis-1',
              event_type: 'analysis.completed',
              category: 'analysis',
              status: 'success',
              level: 'info',
              title: '分析任务完成',
              summary: '本地审核样例：分析完成且无外部写入。',
              subject: 'ORCL',
              symbol: 'ORCL',
              user_id: 'user-1',
              created_at: timestamp,
              started_at: timestamp,
              completed_at: timestamp,
            },
            {
              id: 'evt-admin-1',
              event_id: 'evt-admin-1',
              event_type: 'admin.review',
              category: 'admin',
              status: 'success',
              level: 'info',
              title: '操作员复核',
              summary: '只读日志复核样例。',
              user_id: 'admin-1',
              created_at: timestamp,
              started_at: timestamp,
              completed_at: timestamp,
            },
          ],
        }),
      });
    }

    if (method === 'GET' && pathName === '/api/v1/admin/logs/storage/summary') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_log_count: 120,
          event_count: 2,
          session_count: 1,
          total_event_count: 2,
          retention_days: 90,
          minimum_retention_days: 7,
          storage_size_available: true,
          measurement_status: 'available',
          storage_size_bytes: 262144,
          storage_size_label: '256 KB',
          storage_soft_limit_bytes: 536870912,
          storage_hard_limit_bytes: 1073741824,
          status: 'ok',
          status_reasons: [],
          recommended_cleanup_action: '无需清理',
        }),
      });
    }

    if (method === 'GET' && pathName === '/api/v1/admin/logs/sessions') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: 1,
          summary: { total: 1, success: 1, warning: 0, error: 0 },
          items: [
            {
              session_id: 'session-ux-density-1',
              session_type: 'analysis',
              title: '本地 UX 审核样例',
              status: 'success',
              level: 'info',
              category: 'analysis',
              symbol: 'ORCL',
              user_id: 'user-1',
              started_at: timestamp,
              completed_at: timestamp,
              event_count: 2,
            },
          ],
        }),
      });
    }

    if (method === 'GET' && pathName === '/api/v1/admin/logs/data-missing-drilldown') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total: 0, items: [] }),
      });
    }

    if (method === 'GET' && pathName === '/api/v1/admin/logs/operator-issue-rollup') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total: 0, items: [] }),
      });
    }

    if (method === 'GET' && pathName === '/api/v1/admin/logs/incident-timeline') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          lookup: { limit: 20 },
          total: 0,
          items: [],
          hooks: [],
          empty_state: {
            read_only: true,
            message: 'No incident timeline entries in the local audit fixture.',
          },
          metadata: { read_only: true },
        }),
      });
    }

    if (method === 'POST' && pathName === '/api/v1/admin/logs/cleanup') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          mode: 'retention',
          dry_run: true,
          matched_log_count: 0,
          matched_event_count: 0,
          deleted_log_count: 0,
          deleted_event_count: 0,
          additional_cleanup_needed: false,
          message: 'Dry-run only.',
        }),
      });
    }

    return route.fallback();
  });

  await page.route('**/api/v1/admin/providers/operations-matrix', async (route) => {
    if (route.request().method() !== 'GET') {
      return route.fallback();
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
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
            contract_coverage_universes: ['US'],
            contract_cadences: ['daily'],
            contract_freshness_floors: ['same_day'],
            required_source_tiers: ['local'],
            score_eligibility_gates: ['operator_check'],
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
          provider_probes_forced: false,
          network_calls_enabled: false,
          cache_mutation: false,
          provider_order_changed: false,
          data_fetcher_manager_changed: false,
          frontend_changed: false,
          db_changed: false,
          secret_values_included: false,
          raw_provider_payloads_included: false,
          readiness_status: 'ready',
          row_count: 1,
        },
      }),
    });
  });

  await page.route('**/api/v1/market/data-readiness**', async (route) => {
    if (route.request().method() !== 'GET') {
      return route.fallback();
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
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
      }),
    });
  });

  await page.route('**/api/v1/admin/market-providers/operations**', async (route) => {
    if (route.request().method() !== 'GET') {
      return route.fallback();
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        generated_at: timestamp,
        window: { key: '24h', since: timestamp },
        summary: {
          total_items: 3,
          live_count: 1,
          cache_count: 1,
          stale_count: 0,
          fallback_count: 1,
          partial_count: 0,
          unavailable_count: 0,
          error_count: 0,
          refreshing_count: 0,
          event_count: 4,
          failure_count: 0,
          fallback_event_count: 1,
          stale_event_count: 0,
          slow_event_count: 0,
        },
        items: [
          {
            provider: 'playwright-fixture',
            source_label: '本地审核样例',
            source_type: 'mock',
            domain: 'market',
            endpoint: '/market-overview/indices',
            card: 'IndexTrendsCard',
            cache_key: 'market:index',
            status: 'healthy',
            freshness: 'mock',
            as_of: timestamp,
            updated_at: timestamp,
            latency_ms: 42,
            is_fallback: false,
            is_stale: false,
            is_refreshing: false,
            is_from_snapshot: false,
            fallback_used: false,
            admin_log_drill_through: { label: '查看 Admin Logs', route: '/zh/admin/logs', query: {} },
          },
        ],
        event_rollups: [],
        cache_states: [
          {
            cache_key: 'market:index',
            ttl_seconds: 300,
            fetched_at: timestamp,
            expires_at: timestamp,
            is_fresh: true,
            is_refreshing: false,
            persistent_snapshot_available: true,
            status: 'healthy',
          },
        ],
        limitations: ['playwright_fixture_only'],
        admin_log_drill_through: { label: '查看 Admin Logs', route: '/zh/admin/logs', query: {} },
        metadata: {
          source: 'playwright_fixture',
          read_only: true,
          external_provider_calls: false,
          cache_mutation: false,
        },
      }),
    });
  });
}

export async function waitForUxDensityRoute(page: Page) {
  await page.waitForLoadState('domcontentloaded');
  await page.locator('#root').waitFor({ state: 'visible', timeout: 15_000 });
  await expect.poll(async () => page.locator('#root').evaluate((root) => root.textContent?.trim().length ?? 0)).toBeGreaterThan(0);
  await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => undefined);
  await page.waitForTimeout(500);
}

export async function collectUxDensityMetric(
  page: Page,
  route: UxDensityRoute,
  viewport: UxDensityViewport,
  consolePageErrors: string[],
): Promise<UxDensityMetric> {
  const browserMetric = await page.evaluate(({ strictTokens, rawUnsafeTokens }) => {
    const viewportWidth = document.documentElement.clientWidth;
    const viewportHeight = window.innerHeight;

    const isVisibleInViewport = (element: Element) => {
      const style = window.getComputedStyle(element);
      if (style.visibility === 'hidden' || style.display === 'none' || Number(style.opacity) === 0) {
        return false;
      }
      const rect = element.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.right > 0 && rect.top < viewportHeight && rect.left < viewportWidth;
    };

    const normalizeText = (value: string | null | undefined) => (value || '').replace(/\s+/g, ' ').trim();
    const visibleElements = Array.from(document.body.querySelectorAll<HTMLElement>('body *')).filter(isVisibleInViewport);
    const viewportText = normalizeText(visibleElements.map((element) => normalizeText(element.innerText || element.textContent)).filter(Boolean).join(' '));
    const countMatches = (pattern: RegExp) => (viewportText.match(pattern) || []).length;
    const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const countExactTerm = (term: string) => {
      const source = term.trim().split(/\s+/).map(escapeRegExp).join('\\s+');
      const pattern = new RegExp(`(^|[^A-Za-z0-9_])${source}(?=$|[^A-Za-z0-9_])`, 'gi');
      return Array.from(viewportText.matchAll(pattern)).length;
    };
    const collectTermHits = (terms: string[]) => (
      terms
        .map((term) => ({ term, count: countExactTerm(term) }))
        .filter((entry) => entry.count > 0)
    );
    const cardSelectors = [
      'article',
      '[role="article"]',
      '[data-testid*="card"]',
      '[data-testid*="panel"]',
      '[data-testid*="summary"]',
      '[class*="rounded"]',
    ].join(',');
    const approximateVisibleCardCount = Array.from(document.body.querySelectorAll(cardSelectors))
      .filter((element, index, elements) => isVisibleInViewport(element) && elements.indexOf(element) === index)
      .length;
    const visibleButtonInputCount = Array.from(document.body.querySelectorAll('button, input, select, textarea, [role="button"], [role="combobox"], [role="textbox"]'))
      .filter(isVisibleInViewport)
      .length;
    const glossaryHelpAffordanceCount = visibleElements.filter((element) => {
      const text = normalizeText(element.innerText || element.textContent);
      const label = normalizeText(element.getAttribute('aria-label') || element.getAttribute('title'));
      const role = element.getAttribute('role') || '';
      return /帮助|说明|解释|Glossary|Help|Tooltip|什么是|为何|How it works|info/i.test(`${text} ${label}`) || role === 'tooltip';
    }).length;
    const headings = Array.from(document.body.querySelectorAll('h1,h2,h3,[role="heading"]'))
      .filter(isVisibleInViewport)
      .map((element) => normalizeText(element.textContent))
      .filter(Boolean);
    const firstViewportContentOrder = visibleElements
      .filter((element) => {
        if (!['H1', 'H2', 'H3', 'P', 'SUMMARY', 'BUTTON', 'A', 'LABEL'].includes(element.tagName)) {
          return element.matches('[role="heading"], [data-testid*="summary"], [data-testid*="hero"], [data-testid*="toolbar"]');
        }
        return true;
      })
      .map((element) => normalizeText(element.innerText || element.textContent))
      .filter((text, index, values) => text.length >= 2 && text.length <= 120 && values.indexOf(text) === index)
      .slice(0, 16);

    return {
      approximateVisibleCardCount,
      visibleButtonInputCount,
      debugProviderRawTermHits: [
        { term: 'debug', count: countMatches(/\bdebug\b|调试|诊断/gim) },
        { term: 'provider', count: countMatches(/\bprovider\b|数据源|供应商/gim) },
        { term: 'raw', count: countMatches(/\braw\b|原始/gim) },
        { term: 'fallback', count: countMatches(/\bfallback\b|备用|降级/gim) },
        { term: 'mock', count: countMatches(/\bmock\b|模拟/gim) },
        { term: 'reason', count: countMatches(/\breason\b|原因/gim) },
      ].filter((entry) => entry.count > 0),
      strictBackendDiagnosticTokenHits: collectTermHits(strictTokens),
      rawUnsafePayloadTermHits: collectTermHits(rawUnsafeTokens),
      glossaryHelpAffordanceCount,
      horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      firstMeaningfulHeadingText: headings[0] || null,
      firstViewportContentOrder,
    };
  }, { strictTokens: strictBackendDiagnosticTokens, rawUnsafeTokens: rawUnsafePayloadTokens });

  return {
    route: route.path,
    label: route.label,
    viewport,
    finalUrl: page.url(),
    consolePageErrors: [...consolePageErrors],
    ...browserMetric,
  };
}

export async function assertUxDensityHardSafety(page: Page, metric: UxDensityMetric, route: UxDensityRoute) {
  const audience = uxDensityAudienceForRoute(route);

  expect(metric.horizontalOverflow, `${metric.route} ${metric.viewport.width}x${metric.viewport.height} horizontal overflow`).toBe(false);
  expect(metric.consolePageErrors, `${metric.route} ${metric.viewport.width}x${metric.viewport.height} console/page errors`).toEqual([]);
  expect(
    metric.rawUnsafePayloadTermHits,
    `${metric.route} ${metric.viewport.width}x${metric.viewport.height} visible raw unsafe payload vocabulary: ${formatTermHits(metric.rawUnsafePayloadTermHits)}`,
  ).toEqual([]);
  if (audience === 'consumer') {
    expect(
      metric.strictBackendDiagnosticTokenHits,
      `${metric.route} ${metric.viewport.width}x${metric.viewport.height} consumer strict backend diagnostic vocabulary: ${formatTermHits(metric.strictBackendDiagnosticTokenHits)}`,
    ).toEqual([]);
  }
  const bodyText = await page.locator('body').innerText();
  expect(bodyText, `${metric.route} visible raw secret-like content`).not.toMatch(rawSecretLikePattern);
}

export function writeUxDensityReport(metrics: UxDensityMetric[]) {
  const outputPath = process.env.UX_DENSITY_AUDIT_OUTPUT
    ? path.resolve(process.env.UX_DENSITY_AUDIT_OUTPUT)
    : path.resolve(process.cwd(), 'test-results', 'ux-density-audit-report.json');
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(
    outputPath,
    JSON.stringify(
      {
        schemaVersion: reportSchemaVersion,
        generatedAt: new Date().toISOString(),
        routes: metrics,
      },
      null,
      2,
    ),
  );
  return outputPath;
}
