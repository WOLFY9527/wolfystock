import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';
import { expectNoHorizontalOverflow, fulfillJson } from './fixtures/authenticatedRouteSmoke';
import {
  expectNoRawSecretLikeText,
  installAdminAuthHarness,
  openAdminRouteWithHarness,
  test as adminTest,
} from './fixtures/adminAuth';
import {
  forbiddenPortfolioCredentialSentinels,
  forbiddenPortfolioOwnerSentinels,
  installPortfolioSmokeHarness,
  visibleOwnerPortfolioSentinels,
} from './fixtures/portfolioSmoke';
import { captureShellVisualEvidence } from './fixtures/shellVisualEvidence';

const productAuthFixture = await import('./fixtures/productAuth').catch(() => null);

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

const rawLaunchArtifactPattern = /raw\s+(payload|response|trace)|debug\s+(payload|response|schema|panel)|provider\s+(payload|credential)|stack\s+(trace|details)|traceback|bearer\s+[a-z0-9._-]+|api[_\s-]?key\s*[=:]|password\s*[=:]|session[_\s-]?id\s*[=:]|cookie\s*[=:]|secret\s*[=:]|sk-[a-z0-9_-]{12,}|ghp_[a-z0-9_]{12,}|xox[baprs]-[a-z0-9-]{12,}/i;
const brokerCredentialOrOrderPattern = /broker[_\s-]?credentials?|broker[_\s-]?order|order[_\s-]?payload|place[_\s-]?order|submit[_\s-]?order|execute[_\s-]?order|payload_json|sync_metadata_json|raw[_\s-]?provider[_\s-]?payload|provider[_\s-]?credential|api[_\s-]?key|access[_\s-]?token|refresh[_\s-]?token|session[_\s-]?token|cookie\s*[=:]|debug[_\s-]?schema|stack[_\s-]?trace/i;
const rotationRadarTradingActionPattern = /买入按钮|建议买入|建议卖出|卖出指令|立即交易|下单|提交订单|订单载荷|开仓|平仓|加仓|减仓|持仓建议|仓位建议|决策级|decision[-\s]?grade|buy now|sell now|place order|submit order|best contract|guaranteed/i;
const rotationRadarDiagnosticLeakPattern =
  /alpaca|alpaca_etf_authority_spine|Alpaca SIP|bounded_etf_authority_active|missing_required_windows|ineligible_bounded_etf|entitlement|reasonCodes?|reasonFamilies|sourceAuthorityAllowed|scoreContributionAllowed|observationOnly|local_taxonomy|taxonomy-only|fallback_static|synthetic_fixture|official_public|authorized_licensed_feed|public_proxy|unofficial_proxy|provider|quote provider|提供方运维|数据源设置|原始来源|原因代码|ETF 权威|ETF 代理|权威来源|权威检查|权威可计分|可计分证据|代理缺口|代理过期|代理完整|proxy_quote_missing|proxy_stale|backend|raw_payload|provider_payload|debug|trace/i;
const providerCircuitSecondaryDisclosureLabel = 'L2 分组诊断：熔断状态 / 事件 / 配额 / 探测 / SLA（已脱敏摘要）';
const forbiddenPortfolioLaunchLanguage = ['交易工作台', '股票买卖', '提交交易', '下单', '订单执行', '买入', '卖出'];
const requiredPortfolioLedgerLanguage = ['手工记账台', '手工记账入口', '持仓流水', '保存记录'];

async function installAuthenticatedAppSmokeSession(page: Page) {
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
        currentUser: {
          id: 'user-1',
          username: 'wolfy-user',
          displayName: 'Wolfy User',
          role: 'user',
          isAdmin: false,
          isAuthenticated: true,
          transitional: false,
          authEnabled: true,
        },
      }),
    });
  });
}

async function expectNoRawLaunchArtifacts(page: Page) {
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(rawLaunchArtifactPattern);
}

async function expectNoBrokerCredentialOrOrderPayloads(page: Page) {
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(brokerCredentialOrOrderPattern);
}

async function expectVisibleTextPresent(page: Page, sentinels: string[]) {
  const bodyText = await page.locator('body').innerText();
  for (const sentinel of sentinels) {
    expect(bodyText).toContain(sentinel);
  }
}

async function expectVisibleTextAbsent(page: Page, sentinels: string[]) {
  const bodyText = await page.locator('body').innerText();
  for (const sentinel of sentinels) {
    expect(bodyText).not.toContain(sentinel);
  }
}

async function expectRootNonEmpty(page: Page) {
  await expect.poll(async () => page.locator('#root').evaluate((root) => root.textContent?.trim().length ?? 0)).toBeGreaterThan(0);
}

async function expectForbiddenTradingWordingAbsent(page: Page) {
  const consumerText = await page.locator('body').innerText();
  const noAdviceNormalizedText = consumerText
    .replace(/不构成交易或下单指令/g, '不构成交易指令')
    .replace(/不会提交订单、不会连接券商或改动组合持仓/g, '不会连接券商或改动组合持仓');
  expect(noAdviceNormalizedText).not.toMatch(
    /买入按钮|下单|立即交易|必买|稳赚|保证收益|guaranteed|best contract|AI recommends you buy|must buy|must sell|buy now|sell now|place order|you should buy|you should sell/i,
  );
}

async function assertRotationRadarConsumerShell(page: Page) {
  const bodyText = await page.locator('body').innerText();
  await appExpect(page.getByTestId('rotation-radar-guidance')).toBeVisible();
  await appExpect(page.getByTestId('rotation-radar-summary-band')).toBeVisible();
  await appExpect(page.getByTestId('rotation-radar-leader-list')).toBeVisible();
  await appExpect(page.getByTestId('rotation-radar-universe-list')).toBeVisible();
  await appExpect(page.getByTestId('rotation-theme-detail-panel')).toBeVisible();
  const mechanicsDisclosure = page.getByTestId('rotation-radar-mechanics-details');
  await appExpect(mechanicsDisclosure).toBeAttached();
  await appExpect(mechanicsDisclosure.getByText('轮动方向说明')).toBeHidden();
  const visualMatrix = page.getByTestId('rotation-radar-visual-matrix');
  const visualUnavailable = page.getByTestId('rotation-radar-visual-unavailable');
  if ((await visualMatrix.count()) > 0) {
    await appExpect(visualMatrix).toBeVisible();
    await appExpect(visualUnavailable).toHaveCount(0);
  } else {
    await appExpect(visualUnavailable).toBeVisible();
  }

  expect(bodyText).not.toContain('资金轮动雷达');
  expect(bodyText).not.toContain('下一观察 / 风险');
  expect(bodyText).not.toContain('只读证据');
  expect(bodyText).not.toContain('非交易指令');
  expect(bodyText).not.toMatch(rotationRadarTradingActionPattern);
  expect(bodyText).not.toMatch(rotationRadarDiagnosticLeakPattern);
  await appExpect(page.getByTestId('rotation-theme-proxy-details-ai_applications')).toHaveCount(0);
  await appExpect(page.getByTestId('rotation-radar-developer-details')).toHaveCount(0);
  await appExpect(page.getByTestId('rotation-capital-summary')).toHaveCount(0);
  await appExpect(page.getByTestId('rotation-decision-readiness')).toHaveCount(0);
  await appExpect(page.getByTestId('rotation-radar-buckets')).toHaveCount(0);
  await appExpect(page.getByTestId('rotation-etf-diagnostics-disclosure')).toHaveCount(0);
}

async function assertPublicShell(page: Page) {
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);
  await expectForbiddenTradingWordingAbsent(page);
  await expectNoRawLaunchArtifacts(page);
}

async function assertProductShell(page: Page) {
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);
  await expectForbiddenTradingWordingAbsent(page);
  await expectNoRawLaunchArtifacts(page);
  await expectNoBrokerCredentialOrOrderPayloads(page);
}

async function assertAdminShell(page: Page) {
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);
  await expectNoRawSecretLikeText(page);
  await expectNoRawLaunchArtifacts(page);
  await expectNoBrokerCredentialOrOrderPayloads(page);
}

function notificationChannelsPayload() {
  return {
    items: [
      {
        id: 7,
        name: 'Route smoke in-app channel',
        type: 'in_app',
        enabled: true,
        severity_min: 'warning',
        event_types: ['admin_logs'],
        route_scope: 'log_notification_association',
        coverage_summary: 'Admin Logs route smoke binding',
        target_summary: 'in-app operator queue',
        config: {},
        created_at: '2026-05-06T10:30:00+08:00',
        updated_at: '2026-05-06T10:30:00+08:00',
        last_tested_at: null,
        last_triggered_at: null,
        last_sent_at: null,
        last_status: 'dry_run',
        last_error: null,
        last_error_summary: null,
        last_error_code: null,
        last_error_diagnostics: {},
      },
    ],
    available_system_channels: ['email'],
  };
}

function notificationEventsPayload() {
  return {
    total: 1,
    limit: 100,
    offset: 0,
    items: [
      {
        id: 11,
        event_type: 'admin_logs',
        severity: 'warning',
        title: 'Admin Logs route smoke',
        message: 'Operator notification routed to a controlled in-app record.',
        payload: {
          route_scope: 'log_notification_association',
          redacted: true,
        },
        fingerprint: 'route-smoke-notification',
        created_at: '2026-05-06T10:30:00+08:00',
        acknowledged_at: null,
        acknowledged_by: null,
        delivery_status: 'queued',
      },
    ],
  };
}

async function openAdminNotificationsRouteWithHarness(page: Page) {
  const requests: string[] = [];
  const harness = await installAdminAuthHarness(page, {
    capabilities: ['ops:notifications:read'],
  });

  await page.route('**/api/v1/admin/notification-channels**', (route) => {
    requests.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
    return fulfillJson(route, notificationChannelsPayload());
  });
  await page.route('**/api/v1/admin/notifications**', (route) => {
    requests.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
    return fulfillJson(route, notificationEventsPayload());
  });

  await page.goto('/zh/admin/notifications');
  await page.waitForLoadState('domcontentloaded');
  await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);

  return { harness, requests };
}

async function expectProviderCircuitSecondaryDisclosure(page: Page) {
  const expandButton = page.getByRole('button', { name: `展开 ${providerCircuitSecondaryDisclosureLabel}` });

  await appExpect(page.getByText(providerCircuitSecondaryDisclosureLabel, { exact: true })).toBeVisible();
  await appExpect(page.getByText(/已脱敏 bucket\/边界默认折叠/)).toBeVisible();
  await appExpect(expandButton).toBeVisible();
  await appExpect(expandButton).toHaveAttribute('aria-expanded', 'false');
  await appExpect(page.getByRole('heading', { name: '最近熔断事件' })).toHaveCount(0);
  await expandButton.click();
  await appExpect(page.getByRole('button', { name: `收起 ${providerCircuitSecondaryDisclosureLabel}` })).toHaveAttribute('aria-expanded', 'true');
  await appExpect(page.getByRole('heading', { name: '最近熔断事件', exact: true })).toBeVisible();
  await appExpect(page.getByRole('heading', { name: '配额窗口', exact: true })).toBeVisible();
  await appExpect(page.getByRole('heading', { name: '探测事件', exact: true })).toBeVisible();
}

appTest.describe('public launch route smoke', () => {
  appTest('home/dashboard stays clean on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);

      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page.getByTestId('home-bento-dashboard')).toBeVisible({ timeout: 15_000 });
      await assertPublicShell(page);
      await captureShellVisualEvidence(page, 'home', viewport);
    }
  });

  appTest('market overview stays clean on desktop and mobile', async ({ page }) => {
    await installAuthenticatedAppSmokeSession(page);

    for (const viewport of viewports) {
      await page.setViewportSize(viewport);

      await page.goto('/market-overview');
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page.getByTestId('market-overview-shell')).toBeVisible({ timeout: 15_000 });
      await assertPublicShell(page);
      await captureShellVisualEvidence(page, 'market-overview', viewport);
    }
  });

  appTest('consumer mobile menu closes on outside interaction and restores trigger focus', async ({ page }) => {
    await installAuthenticatedAppSmokeSession(page);
    await page.setViewportSize({ width: 390, height: 844 });

    await page.goto('/zh/market-overview');
    await page.waitForLoadState('domcontentloaded');
    await appExpect(page.getByTestId('market-overview-shell')).toBeVisible({ timeout: 15_000 });

    const menuTrigger = page.getByRole('button', { name: '打开导航菜单' });
    await menuTrigger.click();

    const drawer = page.getByRole('dialog', { name: '导航菜单' });
    await appExpect(drawer).toBeVisible();
    await appExpect(drawer).toHaveAttribute('aria-modal', 'true');
    const activeLink = drawer.getByRole('link', { name: '市场总览' });
    await activeLink.focus();
    await appExpect(activeLink).toBeFocused();

    const focusableInDrawer = drawer.locator(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    await focusableInDrawer.last().focus();
    await page.keyboard.press('Tab');
    await appExpect.poll(async () => (
      await drawer.evaluate((element) => element.contains(document.activeElement))
    )).toBe(true);

    await focusableInDrawer.first().focus();
    await page.keyboard.press('Shift+Tab');
    await appExpect.poll(async () => (
      await drawer.evaluate((element) => element.contains(document.activeElement))
    )).toBe(true);

    await page.waitForTimeout(500);
    await page.getByTestId('drawer-backdrop').dispatchEvent('pointerdown');

    await appExpect(drawer).toHaveCount(0);
    await appExpect(menuTrigger).toBeFocused();
  });

  appTest('market rotation radar stays clean on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);

      await installAuthenticatedAppSmokeSession(page);
      await page.goto('/zh/market-overview');
      await page.waitForLoadState('domcontentloaded');
      if (viewport.width >= 768) {
        const primaryNav = page.getByRole('navigation', { name: '导航菜单' });
        await appExpect(primaryNav.getByRole('link', { name: '市场总览' })).toHaveClass(/is-active/);
        const rotationNavLink = primaryNav.getByRole('link', { name: '轮动雷达' });
        await appExpect(rotationNavLink).toBeVisible();
        await appExpect(rotationNavLink).toHaveAttribute('href', '/zh/market/rotation-radar');
        await rotationNavLink.click();
      } else {
        await page.getByRole('button', { name: '打开导航菜单' }).click();
        const drawerNav = page.getByRole('navigation', { name: '导航菜单' });
        const rotationNavLink = drawerNav.getByRole('link', { name: '轮动雷达' });
        await appExpect(rotationNavLink).toBeVisible();
        await rotationNavLink.click();
      }

      await appExpect(page).toHaveURL(/\/zh\/market\/rotation-radar$/);
      await appExpect(page.getByTestId('market-rotation-radar-page')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByRole('heading', { name: '主题轮动雷达' })).toBeVisible();
      if (viewport.width >= 768) {
        const rotationNavLink = page.getByRole('navigation', { name: '导航菜单' }).getByRole('link', { name: '轮动雷达' });
        await appExpect(rotationNavLink).toBeVisible();
        await appExpect(rotationNavLink).toHaveAttribute('href', '/zh/market/rotation-radar');
        await appExpect(rotationNavLink).toHaveClass(/is-active/);
        await appExpect(page.getByRole('navigation', { name: '导航菜单' }).getByRole('link', { name: '市场总览' })).not.toHaveClass(/is-active/);
      } else {
        await appExpect(page.getByTestId('shell-mobile-active-route')).toHaveText('轮动雷达');
        await page.getByRole('button', { name: '打开导航菜单' }).click();
        await appExpect(page.getByRole('navigation', { name: '导航菜单' }).getByRole('link', { name: '轮动雷达' })).toBeVisible();
      }
      await assertRotationRadarConsumerShell(page);
      await assertPublicShell(page);
    }
  });

  appTest('scanner and backtest launch routes stay clean on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);

      await installAuthenticatedAppSmokeSession(page);
      await page.goto('/scanner');
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page.getByTestId('user-scanner-workspace')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('scanner-command-panel')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('scanner-results-panel')).toBeVisible({ timeout: 15_000 });
      await assertProductShell(page);
      await captureShellVisualEvidence(page, 'scanner', viewport);

      await page.setViewportSize(viewport);
      await installAuthenticatedAppSmokeSession(page);
      await page.goto('/backtest');
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page.getByTestId('backtest-bento-page')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('backtest-subnav')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('backtest-v1-page')).toBeVisible({ timeout: 15_000 });
      await assertProductShell(page);
      await captureShellVisualEvidence(page, 'backtest', viewport);

      await page.setViewportSize(viewport);
      await installAuthenticatedAppSmokeSession(page);
      await page.goto('/backtest/results/34');
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page.getByTestId('deterministic-backtest-result-page')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('backtest-result-report')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByRole('button', { name: '导出交易CSV' })).toBeVisible();
      await appExpect(page.getByTestId('backtest-report-advanced-details')).toBeAttached();
      await expectVisibleTextAbsent(page, [
        'mock-canary-place-order-payload',
        'mock-canary-broker-credentials',
        'mock-canary-raw-provider-payload',
      ]);
      await assertProductShell(page);
    }
  });
});

if (productAuthFixture) {
  const { openProductRouteWithHarness, test: productTest } = productAuthFixture;

  productTest.describe('product launch route smoke', () => {
    productTest('options lab stays clean on desktop and mobile', async ({ page }) => {
      for (const viewport of viewports) {
        await page.setViewportSize(viewport);
        const harness = await openProductRouteWithHarness(page, '/zh/options-lab');

        await appExpect(page.getByRole('heading', { name: '期权实验室' })).toBeVisible({ timeout: 15_000 });
        await appExpect(page.getByTestId('options-lab-decision-engine')).toBeVisible();
        await appExpect(page.getByTestId('options-lab-decision-summary')).toBeVisible();
        const analysisDetails = page.getByTestId('options-lab-analysis-details');
        const analysisToggle = analysisDetails.getByRole('button', { name: /展开/ });
        await appExpect(analysisToggle).toHaveAttribute('aria-expanded', 'false');
        await analysisToggle.click();
        await appExpect(analysisDetails.getByText('方法边界')).toBeVisible();
        await appExpect(page.getByTestId('options-lab-chain-panel')).toHaveCount(2);
        await appExpect(page.getByText('Call 链').first()).toBeVisible();
        await appExpect(page.getByText('Put 链').first()).toBeVisible();
        await appExpect(page.getByTestId('options-lab-calls-table')).toBeVisible();
        await appExpect(page.getByTestId('options-lab-strategy-comparison')).toBeVisible();
        await expectForbiddenTradingWordingAbsent(page);
        await assertProductShell(page);
        await captureShellVisualEvidence(page, 'options-lab', viewport);

        expect(harness.requests.count('GET', '/api/v1/auth/status')).toBeGreaterThan(0);
        expect(harness.requests.count('GET', '/api/v1/options/underlyings/TEM/summary')).toBeGreaterThan(0);
        expect(harness.requests.count('POST', '/api/v1/options/strategies/compare')).toBeGreaterThan(0);
        expect(harness.requests.count('POST', '/api/v1/options/decision/evaluate')).toBeGreaterThan(0);
        await page.unrouteAll({ behavior: 'ignoreErrors' });
      }
    });

    productTest('portfolio route stays clean on desktop and mobile when mocked', async ({ page }) => {
      for (const viewport of viewports) {
        await page.setViewportSize(viewport);
        const harness = await installPortfolioSmokeHarness(page);

        await page.goto('/portfolio');
        await page.waitForLoadState('domcontentloaded');
        await appExpect(page.getByTestId('portfolio-bento-page')).toBeVisible({ timeout: 15_000 });
        await appExpect(page.getByRole('heading', { name: '总资产' })).toBeVisible({ timeout: 15_000 });
        await appExpect(page.getByTestId('portfolio-workspace-lanes')).toBeVisible({ timeout: 15_000 });
        await appExpect(page.getByRole('heading', { name: /当前持仓/ })).toBeVisible({ timeout: 15_000 });
        await expectVisibleTextPresent(page, visibleOwnerPortfolioSentinels);
        await expectVisibleTextPresent(page, requiredPortfolioLedgerLanguage);
        await expectVisibleTextAbsent(page, [
          ...forbiddenPortfolioOwnerSentinels,
          ...forbiddenPortfolioCredentialSentinels,
          ...forbiddenPortfolioLaunchLanguage,
        ]);
        await assertProductShell(page);
        await captureShellVisualEvidence(page, 'portfolio', viewport);

        expect(harness.requests.count('GET', '/api/v1/auth/status')).toBeGreaterThan(0);
        expect(harness.requests.count('GET', '/api/v1/portfolio/snapshot')).toBeGreaterThan(0);
        expect(harness.requests.count('GET', '/api/v1/portfolio/risk')).toBeGreaterThan(0);
        expect(harness.requests.calls.filter((entry) => entry.startsWith('POST '))).toEqual([]);
        await page.unrouteAll({ behavior: 'ignoreErrors' });
      }
    });
  });
}

adminTest.describe('admin launch route smoke', () => {
  adminTest('cost observability stays clean on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openAdminRouteWithHarness(page, '/zh/admin/cost-observability');

      await appExpect(page.getByRole('heading', { name: '成本观测' })).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('quota-dry-run-panel')).toBeVisible();
      await appExpect(page.getByTestId('llm-ledger-panel')).toHaveCount(0);
      await appExpect(page.getByTestId('model-pricing-policy-panel')).toHaveCount(0);
      await assertAdminShell(page);

      expect(harness.requests.count('GET', '/api/v1/admin/cost/duplicate-summary')).toBeGreaterThan(0);
      expect(harness.requests.count('POST', '/api/v1/admin/cost/quota-dry-run')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/cost/llm-ledger-summary')).toBe(0);
      expect(harness.requests.count('GET', '/api/v1/admin/cost/model-pricing-policies')).toBe(0);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  adminTest('provider diagnostics stays clean on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openAdminRouteWithHarness(page, '/zh/admin/provider-circuits');

      await appExpect(page.getByRole('heading', { name: '数据源熔断诊断' })).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByText('熔断状态', { exact: true })).toBeVisible();
      await expectProviderCircuitSecondaryDisclosure(page);
      await assertAdminShell(page);

      expect(harness.requests.count('GET', '/api/v1/admin/providers/circuits')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/circuits/events')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/quota-windows')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/probe-events')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/sla-readiness')).toBe(1);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  adminTest('system settings stays clean on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openAdminRouteWithHarness(page, '/zh/settings/system');

      await appExpect(page.getByTestId('settings-bento-page')).toBeAttached({ timeout: 15_000 });
      await appExpect(page.getByRole('heading', { name: '系统设置' })).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('system-health-summary')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('duckdb-quant-panel')).toBeAttached();
      await assertAdminShell(page);

      expect(harness.requests.count('GET', '/api/v1/system/config')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/quant/duckdb/health')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/quant/duckdb/coverage')).toBeGreaterThan(0);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  adminTest('admin notifications stays clean with notification capability on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const { harness, requests } = await openAdminNotificationsRouteWithHarness(page);

      await appExpect(page.getByRole('heading', { name: '管理员通知' })).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('admin-notifications-workspace')).toBeVisible();
      await appExpect(page.getByTestId('admin-notifications-rules-panel')).toBeVisible();
      await appExpect(page.getByTestId('admin-notifications-events-panel')).toBeVisible();
      await assertAdminShell(page);

      expect(harness.currentUser.canReadNotifications).toBe(true);
      expect(harness.currentUser.canReadOpsLogs).toBe(false);
      expect(requests.filter((entry) => entry === 'GET /api/v1/admin/notification-channels').length).toBeGreaterThan(0);
      expect(requests.filter((entry) => entry === 'GET /api/v1/admin/notifications').length).toBeGreaterThan(0);
      expect(requests.filter((entry) => entry.startsWith('POST '))).toEqual([]);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  adminTest('admin user portfolio projection stays read-only and owner-safe on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openAdminRouteWithHarness(page, '/zh/admin/users/user-123?tab=portfolio');

      await appExpect(page.getByRole('heading', { name: '组合只读总览' })).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByText('只读投影').first()).toBeVisible();
      await expectVisibleTextPresent(page, ['Alice Launch Portfolio', 'AAPL']);
      await expectVisibleTextAbsent(page, [
        'Bob Admin Portfolio',
        'MSFT-ADMIN-BOB-PRIVATE',
        'mock-canary-bob-admin-broker-account',
        'mock-canary-bob-admin-session-token',
        'mock-canary-admin-broker-account',
        'mock-canary-admin-api-key',
        'mock-canary-admin-access-token',
        'mock-canary-admin-broker-order-payload',
        'mock-canary-admin-place-order-payload',
        'mock-canary-admin-raw-provider-payload',
        'mock-canary-admin-execute-order-payload',
        'mock-canary-admin-broker-credentials',
      ]);
      await assertAdminShell(page);

      expect(harness.requests.count('GET', '/api/v1/admin/users/user-123/portfolio-summary')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/users/user-123/holdings')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/users/user-123/portfolio-activity')).toBe(1);
      expect(harness.requests.calls.filter((entry) => entry.startsWith('POST '))).toEqual([]);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});
