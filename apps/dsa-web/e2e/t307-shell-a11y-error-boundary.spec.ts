import { expect, test, type Page, type Route } from '@playwright/test';

const currentUser = {
  id: 't307-user',
  username: 't307-user',
  displayName: 'T307 User',
  role: 'user',
  isAdmin: false,
  isAuthenticated: true,
  transitional: false,
  authEnabled: true,
};

const now = '2026-07-10T08:00:00Z';

const watchlistItem = {
  id: 1,
  symbol: 'AAPL',
  market: 'US',
  identity: {
    canonicalSymbol: 'AAPL',
    displaySymbol: 'AAPL',
    market: 'US',
    exchange: 'NASDAQ',
    displayName: 'Apple Inc.',
    identityState: 'available',
  },
  name: 'Apple Inc.',
  source: 'scanner',
  scannerRunId: 307,
  scannerRank: 1,
  scannerScore: 90,
  lastScoredAt: now,
  scoreSource: 'scanner_run',
  scoreProfile: 't307',
  scoreReason: 'Saved scanner candidate.',
  scoreStatus: 'fresh',
  researchReadiness: {
    state: 'partial',
    freshnessState: 'available',
    identityState: 'available',
    lastReviewedAt: now,
    scoreFreshnessImplied: false,
    sourceAuthorityImplied: false,
  },
  notes: 'Observation-only accessibility fixture.',
  intelligence: {
    scanner: {
      lastScore: 90,
      lastRank: 1,
      status: 'selected',
      reason: 'Saved scanner candidate.',
      lastScannedAt: now,
    },
  },
  rowResearchPacket: {
    symbol: 'AAPL',
    market: 'us',
    identity: {
      canonicalSymbol: 'AAPL',
      displaySymbol: 'AAPL',
      displayName: 'Apple Inc.',
      exchange: 'NASDAQ',
      identityState: 'available',
    },
    savedItemSource: 'scanner',
    quote: {
      state: 'available',
      price: 210,
      changePercent: 0.5,
      asOf: now,
    },
    scannerLineage: {
      runId: 307,
      rank: 1,
      score: 90,
      status: 'selected',
      lastScoredAt: now,
    },
    researchStatus: 'partial',
    researchReadiness: {
      state: 'partial',
      freshnessState: 'available',
      identityState: 'available',
      lastReviewedAt: now,
      scoreFreshnessImplied: false,
      sourceAuthorityImplied: false,
    },
    missingData: ['Additional evidence review is pending.'],
    nextDataAction: 'Review stock research context.',
    observationOnly: true,
    noAdviceDisclosure: 'Research observation only.',
  },
  createdAt: now,
  updatedAt: now,
};

async function fulfillJson(route: Route, payload: unknown) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installApiHarness(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/status') {
      await fulfillJson(route, {
        authEnabled: true,
        loggedIn: true,
        passwordSet: true,
        passwordChangeable: true,
        setupState: 'enabled',
        currentUser,
      });
      return;
    }
    if (path === '/api/v1/auth/me') {
      await fulfillJson(route, currentUser);
      return;
    }
    if (path === '/api/v1/watchlist/items') {
      await fulfillJson(route, { items: [watchlistItem] });
      return;
    }
    if (path === '/api/v1/watchlist/research-overlay') {
      await fulfillJson(route, {
        schemaVersion: 'watchlist_research_overlay_v1',
        overlayState: 'partial',
        researchSummary: 'Saved symbols need evidence review.',
        researchPriorityQueue: [],
        observationOnly: true,
        decisionGrade: false,
      });
      return;
    }
    if (path === '/api/v1/watchlist/refresh-status') {
      await fulfillJson(route, {
        enabled: true,
        usTime: '08:45',
        cnTime: '09:00',
        hkTime: '09:00',
        status: 'idle',
        lastRunAt: null,
        nextRunAt: null,
      });
      return;
    }
    if (path === '/api/v1/user-alerts/rules') {
      await fulfillJson(route, {
        contract_version: 'user_alert_contract_v1',
        delivery_mode: 'in_app',
        in_app_only: true,
        owner_scoped: true,
        items: [],
      });
      return;
    }
    if (path === '/api/v1/user-alerts/events') {
      await fulfillJson(route, {
        contract_version: 'user_alert_contract_v1',
        delivery_mode: 'in_app',
        in_app_only: true,
        owner_scoped: true,
        total: 0,
        limit: 20,
        offset: 0,
        items: [],
      });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function waitForShellReady(page: Page) {
  await expect(page.getByRole('status', { name: 'WolfyStock research workspace loading' })).toBeHidden({
    timeout: 15_000,
  });
  await expect(page).not.toHaveURL(/\/login(?:$|[/?#])/);
}

async function openPrimaryNav(page: Page, isMobile: boolean) {
  if (isMobile) {
    await page.getByRole('button', { name: '打开导航菜单' }).click();
  }
  const nav = page.getByTestId('shell-consumer-primary-nav');
  await expect(nav).toBeVisible();
  return nav;
}

test.describe('T307 shell accessibility invariants', () => {
  for (const scenario of [
    { name: 'desktop', viewport: { width: 1440, height: 1000 }, isMobile: false },
    { name: 'tablet', viewport: { width: 768, height: 1024 }, isMobile: true },
    { name: 'mobile', viewport: { width: 390, height: 844 }, isMobile: true },
  ] as const) {
    test(`${scenario.name} Watchlist exposes one current page and one workflow step`, async ({ page }) => {
      await page.setViewportSize(scenario.viewport);
      await installApiHarness(page);
      await page.goto('/zh/watchlist?symbol=AAPL&market=us&source=watchlist');
      await page.waitForLoadState('domcontentloaded');
      await waitForShellReady(page);
      await expect(page.getByTestId('watchlist-page')).toBeVisible({ timeout: 30_000 });

      const primaryNav = await openPrimaryNav(page, scenario.isMobile);
      await expect(primaryNav.getByRole('link', { name: '观察列表' })).toHaveAttribute('aria-current', 'page');
      await expect(page.getByTestId('research-workspace-link-watchlist')).toHaveAttribute('aria-current', 'step');
      await expect(page.locator('[aria-current="page"]')).toHaveCount(1);
    });

    test(`${scenario.name} grouped child route keeps one active route owner`, async ({ page }) => {
      await page.setViewportSize(scenario.viewport);
      await installApiHarness(page);
      await page.goto('/zh/backtest');
      await page.waitForLoadState('domcontentloaded');
      await waitForShellReady(page);

      const primaryNav = await openPrimaryNav(page, scenario.isMobile);
      if (scenario.isMobile) {
        await expect(primaryNav.getByRole('link', { name: '回测' })).toHaveAttribute('aria-current', 'page');
      } else {
        const validateTrigger = primaryNav.getByRole('button', { name: '验证' });
        await expect(validateTrigger).toHaveAttribute('aria-current', 'page');
        await validateTrigger.click();
        await expect(primaryNav.getByRole('link', { name: '回测' })).toHaveAttribute('data-current-child', 'true');
        await expect(primaryNav.getByRole('link', { name: '回测' })).not.toHaveAttribute('aria-current');
      }
      await expect(page.locator('[aria-current="page"]')).toHaveCount(1);
    });
  }

  test('forced render crash retains shell landmarks and supports keyboard recovery', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await installApiHarness(page);
    await page.route('**/assets/MarketOverviewPage-*.js', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/javascript',
        body: 'export default function ForcedMarketOverviewCrash(){throw new Error("forced-render-crash raw-token");}',
      });
    });

    await page.goto('/en/market-overview');
    await page.waitForLoadState('domcontentloaded');

    const alert = page.getByTestId('app-error-boundary');
    await expect(alert).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('shell-skip-link')).toHaveAttribute('href', '#main-content');
    await expect(page.getByTestId('shell-consumer-primary-nav')).toBeVisible();
    await expect(page.locator('#main-content')).toContainText('This page is temporarily unavailable.');
    await expect(page.locator('#main-content [role="alert"]')).toHaveCount(1);
    await expect(alert).toBeFocused();
    await expect(page.locator('body')).not.toContainText('forced-render-crash');
    await expect(page.locator('body')).not.toContainText('raw-token');

    await page.keyboard.press('Tab');
    await expect(alert.getByRole('button', { name: 'Retry' })).toBeFocused();
    await page.keyboard.press('Tab');
    const homeButton = alert.getByRole('button', { name: 'Back to home' });
    await expect(homeButton).toBeFocused();
    await page.keyboard.press('Enter');

    await expect(page).toHaveURL(/\/en$/);
    await expect(page.getByTestId('shell-skip-link')).toBeVisible();
    await expect(page.getByTestId('shell-consumer-primary-nav')).toBeVisible();
  });
});
