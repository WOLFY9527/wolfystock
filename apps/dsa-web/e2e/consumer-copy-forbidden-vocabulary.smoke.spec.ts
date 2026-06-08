import { expect, test, type Page, type Route } from '@playwright/test';
import { createMockAdminUser, createMockAuthStatus } from '../src/test-utils/adminAuthHarness';

const consumerRoutes = [
  { path: '/zh/market-overview' },
  { path: '/zh/market/liquidity-monitor' },
  { path: '/zh/market/rotation-radar' },
  { path: '/zh/scanner' },
  { path: '/zh/watchlist' },
  { path: '/zh/portfolio' },
  { path: '/zh/options-lab' },
] as const;

const forbiddenVocabularyPatterns = [
  /\bsourceAuthorityAllowed\b/i,
  /\bscoreContributionAllowed\b/i,
  /\bsourceTier\b/i,
  /\bsourceLabel\b/i,
  /\bauthorityGrant\b/i,
  /\bdiagnosticOnly\b/i,
  /\breasonCode\b/i,
  /\bmarket_regime_synthesis\b/i,
  /\bConflicts With Primary Regime\b/i,
  /\bALTERNATIVE\.?ME\b/i,
  /\bYFINANCE\b/i,
  /\bCBOE\b/i,
  /\bBINANCE\b/i,
  /\bYahoo Finance\b/i,
  /\bBinance Futures\b/i,
  /\bETF flow proxy\b/i,
  /\bInstitutional pressure proxy\b/i,
  /\bIndustry breadth proxy\b/i,
  /\b(?:REAL|MIXED|FALLBACK|REGIME)\b/,
  /(?:^|[\s:/(])(?:real|mixed|fallback)(?:$|[\s:)/])/i,
  /\braw\s+payload\b/i,
  /\braw\s+json\b/i,
  /\bprovider\s+trace\b/i,
  /\bprovider\b/i,
  /\bbackend\b/i,
  /\bruntime\b/i,
  /\bcache\b/i,
  /\bschema\b/i,
  /\braw\b/i,
  /\bdebug\b/i,
  /\bmock\b/i,
  /\bproxy\b/i,
  /\bsynthetic\b/i,
  /\bMarketCache\b/i,
  /\bsynthetic_fixture\b/i,
  /\bfallback_static\b/i,
  /\bofficial_public\b/i,
  /\b(?:[A-Z][A-Za-z0-9]+){1,3}Provider\b/,
  /\b(?:source|score|reason|provider|fallback|synthetic|official|cache|market_cache|runtime|schema|raw|debug)_[a-z0-9_]+\b/i,
] as const;

const adminUser = createMockAdminUser({ displayName: 'Playwright Admin' });

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installAdminAuth(page: Page) {
  let isLoggedIn = false;

  await page.route('**/api/v1/auth/status**', async (route) => {
    if (!isLoggedIn) {
      await fulfillJson(route, {
        authEnabled: true,
        loggedIn: false,
        passwordSet: true,
        passwordChangeable: false,
        setupState: 'enabled',
        currentUser: null,
      });
      return;
    }
    await fulfillJson(route, createMockAuthStatus(adminUser));
  });

  await page.route('**/api/v1/auth/me**', async (route) => {
    if (!isLoggedIn) {
      await fulfillJson(route, { error: 'not_authenticated' }, 401);
      return;
    }
    await fulfillJson(route, adminUser);
  });

  await page.route('**/api/v1/auth/login**', async (route) => {
    isLoggedIn = true;
    await fulfillJson(route, { ok: true, currentUser: adminUser });
  });

  await page.route('**/api/v1/auth/logout**', async (route) => {
    isLoggedIn = false;
    await fulfillJson(route, { ok: true });
  });

  await page.route('**/api/v1/auth/preferences/notifications**', async (route) => {
    await fulfillJson(route, {
      channel: 'multi',
      enabled: false,
      email: null,
      emailEnabled: false,
      discordEnabled: false,
      discordWebhook: null,
      deliveryAvailable: false,
      emailDeliveryAvailable: false,
      discordDeliveryAvailable: false,
      updatedAt: '2026-06-07T00:00:00+08:00',
    });
  });

  await page.route('**/api/v1/agent/status**', async (route) => {
    await fulfillJson(route, { enabled: false });
  });
}

async function signInAsAdmin(page: Page, redirectPath: string) {
  await page.goto(`/login?redirect=${encodeURIComponent(redirectPath)}`);
  await page.waitForLoadState('domcontentloaded');

  const username = page.locator('#username');
  if (await username.isVisible().catch(() => false)) {
    await username.fill('admin');
  }

  await expect(page.locator('#password')).toBeVisible({ timeout: 15_000 });
  await page.locator('#password').fill('mock-password');

  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/v1/auth/login') && response.status() === 200),
    page.getByRole('button', { name: /sign in|登录继续|授权进入工作台|完成设置并登录/i }).click(),
  ]);
}

async function collectVisibleAccessibleText(page: Page) {
  return page.evaluate(() => {
    const isVisible = (element: Element) => {
      const html = element as HTMLElement;
      if (html.hidden || element.getAttribute('aria-hidden') === 'true') {
        return false;
      }
      const style = window.getComputedStyle(html);
      if (style.display === 'none' || style.visibility === 'hidden') {
        return false;
      }
      const rect = html.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    };

    const texts = new Set<string>();
    for (const element of Array.from(document.querySelectorAll('body, body *'))) {
      if (!isVisible(element)) {
        continue;
      }
      for (const attribute of ['aria-label', 'title', 'alt', 'placeholder']) {
        const value = element.getAttribute(attribute)?.trim();
        if (value) {
          texts.add(value);
        }
      }
    }
    return Array.from(texts).join('\n');
  });
}

async function expectNoForbiddenVocabulary(page: Page, routePath: string) {
  const bodyText = await page.locator('body').innerText();
  const accessibleText = await collectVisibleAccessibleText(page);
  const combinedText = `${bodyText}\n${accessibleText}`;

  for (const pattern of forbiddenVocabularyPatterns) {
    expect(
      combinedText,
      `consumer route ${routePath} leaked forbidden vocabulary matching ${pattern}`,
    ).not.toMatch(pattern);
  }
}

test('consumer routes keep backend/provider/debug vocabulary out of default copy', async ({ page }) => {
  test.slow();
  await installAdminAuth(page);
  await signInAsAdmin(page, consumerRoutes[0].path);

  for (const route of consumerRoutes) {
    await test.step(route.path, async () => {
      await page.goto(route.path);
      await page.waitForLoadState('domcontentloaded');
      await expect(page).toHaveURL(new RegExp(`${route.path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?:$|[?#])`));
      await expect.poll(async () => page.locator('body').innerText().then((text) => text.trim().length)).toBeGreaterThan(0);
      await expectNoForbiddenVocabulary(page, route.path);
    });
  }
});
