import type { Page, Route } from '@playwright/test';
import { expect, installAdminAuthHarness, test } from './fixtures/adminAuth';

const timestamp = '2026-05-06T10:30:00+08:00';

const viewports = [
  { width: 1280, height: 800 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
  { width: 320, height: 800 },
];

const adminRoutes = [
  { key: 'launch', path: '/en/admin/launch-cockpit', ready: 'admin-launch-cockpit-page' },
  { key: 'system', path: '/en/settings/system', ready: 'system-settings-page' },
  { key: 'users', path: '/en/admin/users', ready: 'admin-users-page-shell' },
  { key: 'activity', path: '/en/admin/users/user-123/activity', ready: 'admin-users-page-shell' },
  { key: 'provider-circuits', path: '/en/admin/provider-circuits', ready: 'admin-provider-circuit-diagnostics-page' },
];

async function fulfillJson(route: Route, payload: unknown) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

function launchDomainFixture(domainKey: string, priorityRank: number) {
  return {
    domain_key: domainKey,
    label: domainKey === 'security' ? 'Security / RBAC / MFA' : 'Quota / Cost',
    status: 'blocked',
    status_label: 'Blocked',
    detail_route: '/admin/logs',
    foundation_landed: true,
    evidence_tooling_present: true,
    real_operator_evidence_missing: true,
    approval_required: true,
    public_launch_no_go: true,
    read_only: true,
    advisory_only: true,
    no_external_calls: true,
    live_enforcement: false,
    runtime_behavior_changed: false,
    provider_runtime_changed: false,
    external_actions_enabled: false,
    evidence_refs: ['mocked_playwright_evidence'],
    blocker_refs: ['public_launch_no_go'],
    safe_next_actions: ['Collect real operator evidence before launch.'],
    limitations: ['mocked_browser_harness'],
    priority_rank: priorityRank,
    priority_tier: 'p0',
    impact_level: 'high',
    recommended_next_action: 'Review missing evidence.',
    blocking_reason_summary: 'Real operator evidence is missing.',
    owner_surface: 'admin',
    remediation_surface: 'admin',
    follow_up_proposals: [],
  };
}

function launchCockpitStatusPayload() {
  const domains = [launchDomainFixture('security', 1), launchDomainFixture('quota_cost', 2)];
  return {
    generated_at: timestamp,
    read_only: true,
    no_external_calls: true,
    live_enforcement: false,
    runtime_behavior_changed: false,
    consumer_visible: false,
    advisory_vs_enforcement: {
      label: 'Advisory only',
      enforcement_label: 'No live enforcement',
      source_unavailable_behavior: 'fail_closed',
      read_only: true,
      no_external_calls: true,
      live_enforcement: false,
      runtime_behavior_changed: false,
      consumer_visible: false,
    },
    provider_status_summary: {},
    quota_cost_advisory_status_summary: {},
    storage_readiness_summary: {},
    task_queue_status_summary: {},
    admin_log_evidence_summary: {},
    runtime_log_sink_summary: {},
    retention_policy_status: {},
    execution_log_retention_risk: {},
    db_size_risk: {},
    admin_role_assignment_status: {},
    durable_task_backlog_status: {},
    recommended_maintenance_actions: [],
    build_provenance: {
      contract: 'mocked_playwright_build_provenance',
      read_only: true,
      no_external_calls: true,
      runtime_behavior_changed: false,
      consumer_visible: false,
      backend_git_sha: null,
      backend_branch: null,
      backend_commit_timestamp: null,
      backend_runtime_started_at: null,
      frontend_main_asset_filename: null,
      frontend_main_asset_hash: null,
      frontend_asset_manifest_hash: null,
      frontend_asset_manifest_source: null,
      frontend_static_build_timestamp: null,
      static_asset_mode: 'mocked',
      static_asset_root_provenance: 'mocked',
      static_asset_root_label: null,
      static_asset_root_exists: false,
      static_index_present: false,
      freshness_status: 'unknown',
      comparison_basis: null,
      stale: null,
      reason_codes: [],
    },
    launch_cockpit: {
      contract: 'admin_ops_launch_cockpit_v1',
      status: 'blocked',
      last_checked_at: timestamp,
      message: 'Public launch remains blocked.',
      read_only: true,
      advisory_only: true,
      no_external_calls: true,
      public_launch_approved: false,
      public_launch_no_go: true,
      live_enforcement: false,
      runtime_behavior_changed: false,
      approval_required: true,
      summary_counts: {
        domainCount: 2,
        publicLaunchNoGoCount: 2,
        realEvidenceMissingCount: 2,
        approvalRequiredCount: 2,
      },
      unsafe_action_states: {},
      domains,
      recommended_maintenance_queue: domains,
      blockers: [
        {
          blocker_key: 'public_launch_no_go',
          title: 'Public launch remains NO-GO',
          severity: 'critical',
          public_launch_no_go: true,
          approval_required: true,
          affected_domains: ['security', 'quota_cost'],
          evidence_refs: ['mocked_playwright_evidence'],
          next_action: 'Collect real operator evidence.',
        },
      ],
      safe_next_actions: ['Collect real operator evidence before launch.'],
      limitations: ['mocked_browser_harness'],
      priority_summary: { p0: 2 },
    },
    metadata: {
      read_only: true,
      no_external_calls: true,
      live_enforcement: false,
      runtime_behavior_changed: false,
    },
  };
}

function scannerReadinessPayload(market: 'us' | 'cn') {
  return {
    contract_version: 'scanner_universe_readiness_v1',
    status: 'manual_action_required',
    scanner_universe_status: 'stale',
    market,
    profile: market === 'us' ? 'us_premarket_v1' : 'cn_preopen_v1',
    universe_version: null,
    generated_at: timestamp,
    as_of: timestamp,
    source_class: 'mocked_playwright',
    symbol_count: 0,
    freshness_state: 'stale',
    age: null,
    minimum_coverage_threshold: 1,
    coverage_state: 'insufficient',
    usable: false,
    blocking_reasons: ['mocked_browser_harness'],
    downstream_impact: {},
    last_successful_activation: null,
    last_rejected_import_reason: null,
    last_updated_at: timestamp,
    universe_size: 0,
    affected_product_surfaces: ['Research Radar'],
    next_operator_action: 'Collect approved scanner universe evidence.',
    scanner_universe_readiness: {},
    candidate_generation_blockers: [],
    read_only: true,
    no_external_calls: true,
    mutation_enabled: false,
    provider_calls_enabled: false,
    consumer_visible: false,
  };
}

function userActivityPayload() {
  return {
    items: [
      {
        id: 'activity-mock-1',
        timestamp,
        actor: {
          type: 'admin',
          user_id: 'admin-1',
          label: 'Mock Admin',
          role: 'admin',
          session_id_hash: 'session-hash-01',
          request_id_hash: 'request-hash-01',
        },
        target_user: {
          id: 'user-123',
          label: 'Alice',
        },
        family: 'auth',
        action: 'session_review',
        entity: {
          type: 'session',
          id_hash: 'session-hash-01',
          label: 'Session review',
        },
        status: 'success',
        outcome: 'ok',
        request_id_hash: 'request-hash-01',
        session_id_hash: 'session-hash-01',
        source: {
          kind: 'admin_audit',
          table: 'admin_activity',
          confidence: 'confirmed',
        },
        redacted_metadata: {
          read_only: true,
          raw_payload_omitted: true,
        },
        log_links: [
          {
            kind: 'audit',
            id_hash: 'activity-log-hash-01',
          },
        ],
      },
    ],
    total: 1,
    limit: 50,
    offset: 0,
    has_more: false,
    window: {
      from: timestamp,
      to: timestamp,
      max_days: 30,
    },
    limitations: ['mocked_browser_harness_no_raw_session_values'],
  };
}

async function installAdminLayoutMocks(page: Page) {
  await page.route('**/api/v1/admin/ops/status', (route) => fulfillJson(route, launchCockpitStatusPayload()));
  await page.route('**/api/v1/admin/ops/scanner-universe-readiness?**', async (route) => {
    const url = new URL(route.request().url());
    const market = url.searchParams.get('market') === 'cn' ? 'cn' : 'us';
    await fulfillJson(route, scannerReadinessPayload(market));
  });
  await page.route('**/api/v1/admin/users/user-123/activity?**', (route) => fulfillJson(route, userActivityPayload()));
}

async function collectLayoutMetrics(page: Page) {
  return page.evaluate(async () => {
    const isVisible = (element: Element) => {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
    };
    const isFocusable = (element: Element) => {
      if (!(element instanceof HTMLElement)) return false;
      if (element.hasAttribute('disabled') || element.getAttribute('aria-disabled') === 'true') return false;
      if (element.tabIndex >= 0) return true;
      return /^(A|BUTTON|INPUT|SELECT|TEXTAREA|SUMMARY)$/.test(element.tagName);
    };
    const nodes = Array.from(document.querySelectorAll<HTMLElement>('a,button,input,select,textarea,summary,[tabindex]'))
      .filter((element) => isFocusable(element) && isVisible(element))
      .filter((element) => element.getAttribute('data-testid') !== 'shell-skip-link')
      .slice(0, 140);
    const focusClips: string[] = [];

    for (const element of nodes) {
      element.focus({ preventScroll: false });
      await new Promise((resolve) => requestAnimationFrame(resolve));
      const active = document.activeElement instanceof HTMLElement ? document.activeElement : element;
      const rect = active.getBoundingClientRect();
      let ancestor = active.parentElement;
      while (ancestor && ancestor !== document.body && ancestor !== document.documentElement) {
        const style = window.getComputedStyle(ancestor);
        const clipsX = /(hidden|clip|auto|scroll)/.test(style.overflowX);
        const clipsY = /(hidden|clip|auto|scroll)/.test(style.overflowY);
        if (clipsX || clipsY) {
          const ancestorRect = ancestor.getBoundingClientRect();
          const clipped =
            rect.left - 3 < ancestorRect.left ||
            rect.right + 3 > ancestorRect.right ||
            rect.top - 3 < ancestorRect.top ||
            rect.bottom + 3 > ancestorRect.bottom;
          if (clipped) {
            const label = (active.getAttribute('aria-label') || active.textContent || active.tagName).replace(/\s+/g, ' ').trim().slice(0, 90);
            const ancestorLabel = [
              ancestor.getAttribute('data-testid'),
              ancestor.getAttribute('data-terminal-primitive'),
              ancestor.className,
            ].filter(Boolean).join(' | ').slice(0, 180);
            focusClips.push(`${label} -> ${ancestorLabel}`);
            break;
          }
        }
        ancestor = ancestor.parentElement;
      }
    }

    const pageRootOverflow = Array.from(document.querySelectorAll<HTMLElement>('[data-testid$="page"], [data-testid$="page-shell"], [data-terminal-primitive="page-shell"]'))
      .filter(isVisible)
      .map((element) => ({
        testId: element.getAttribute('data-testid') || element.getAttribute('data-terminal-primitive') || element.tagName,
        scrollDelta: Math.max(0, Math.round(element.scrollWidth - element.clientWidth)),
      }))
      .filter((entry) => entry.scrollDelta > 0);

    return {
      documentOverflow: Math.max(0, Math.round(document.documentElement.scrollWidth - document.documentElement.clientWidth)),
      focusClips,
      pageRootOverflow,
    };
  });
}

test.describe('admin shared focus and layout closure', () => {
  for (const viewport of viewports) {
    for (const route of adminRoutes) {
      test(`${route.key} has no focus clipping or page overflow at ${viewport.width}px`, async ({ page }) => {
        await page.setViewportSize(viewport);
        await installAdminAuthHarness(page);
        await installAdminLayoutMocks(page);
        await page.goto(route.path);
        await page.waitForLoadState('domcontentloaded');
        await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
        await expect(page.getByTestId(route.ready)).toBeVisible({ timeout: 15_000 });

        const metrics = await collectLayoutMetrics(page);
        expect(metrics.documentOverflow, `${route.key} ${viewport.width}px document overflow`).toBe(0);
        expect(metrics.pageRootOverflow, `${route.key} ${viewport.width}px page root overflow`).toEqual([]);
        expect(metrics.focusClips, `${route.key} ${viewport.width}px focus clipping`).toEqual([]);
      });
    }
  }
});
