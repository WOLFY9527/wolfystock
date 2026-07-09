import { expect, test, type ConsoleMessage, type Page, type Request, type Route } from '@playwright/test';

const backendBaseUrl = process.env.DSA_WEB_SMOKE_BACKEND_URL || 'http://127.0.0.1:8000';
const liveSmokeEnabled = process.env.DSA_WEB_LIVE_SMOKE === '1';
const routeApiRequests = process.env.DSA_WEB_SMOKE_ROUTE_API === '1';
const smokeUsername = process.env.DSA_WEB_SMOKE_USERNAME;
const smokePassword = process.env.DSA_WEB_SMOKE_PASSWORD;

const MARKET_OVERVIEW_ROUTE = '/zh/market-overview';
const VOLATILITY_PATH = '/api/v1/market-overview/volatility';
const LATE_STAGE_PATH = '/api/v1/market/cn-short-sentiment';
const REGIME_READ_MODEL_PATH = '/api/v1/market/regime-read-model';
const MARKET_OVERVIEW_POLLING_DELAYS = new Set([45_000, 120_000, 300_000]);
const OPERATOR_ONLY_READINESS_PATHS = [
  '/api/v1/market/data-readiness',
  '/api/v1/market/professional-data-capabilities',
] as const;
const MARKET_OVERVIEW_PANEL_PATHS = [
  '/api/v1/market-overview/indices',
  '/api/v1/market-overview/volatility',
  '/api/v1/market-overview/funds-flow',
  '/api/v1/market-overview/macro',
  '/api/v1/market/crypto',
  '/api/v1/market/sentiment',
  '/api/v1/market/cn-indices',
  '/api/v1/market/cn-breadth',
  '/api/v1/market/cn-flows',
  '/api/v1/market/sector-rotation',
  '/api/v1/market/us-breadth',
  '/api/v1/market/rates',
  '/api/v1/market/fx-commodities',
  '/api/v1/market/temperature',
  '/api/v1/market/market-briefing',
  '/api/v1/market/futures',
  '/api/v1/market/cn-short-sentiment',
] as const;

type AuthStatusPayload = {
  authEnabled: boolean;
  loggedIn?: boolean;
};

type ApiRequestRecord = {
  method: string;
  path: string;
  status: number | null;
  failureText: string | null;
  startedAt: number;
  finishedAt: number | null;
};

type IntervalProbeRecord = {
  id: number;
  delay: number;
  active: boolean;
  fired: number;
  createdAt: number;
  clearedAt: number | null;
  createdPath: string;
};

type RuntimeObserver = {
  apiRequests: ApiRequestRecord[];
  consoleErrors: string[];
  pageErrors: string[];
  cleanup: () => void;
  count: (path: string) => number;
  snapshot: (paths: readonly string[]) => Record<string, number>;
  failedRequests: () => ApiRequestRecord[];
  unexpectedFailedRequests: () => ApiRequestRecord[];
  httpErrors: () => ApiRequestRecord[];
};

function isExpectedCryptoStreamAbort(entry: ApiRequestRecord): boolean {
  return entry.path === '/api/v1/market/crypto/stream' && entry.failureText === 'net::ERR_ABORTED';
}

function createRuntimeObserver(page: Page): RuntimeObserver {
  const apiRequests: ApiRequestRecord[] = [];
  const pendingRequests = new Map<Request, ApiRequestRecord>();
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];

  const onRequest = (request: Request) => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/')) {
      return;
    }
    const entry: ApiRequestRecord = {
      method: request.method(),
      path: url.pathname,
      status: null,
      failureText: null,
      startedAt: Date.now(),
      finishedAt: null,
    };
    apiRequests.push(entry);
    pendingRequests.set(request, entry);
  };

  const onResponse = (response: { request: () => Request; status: () => number }) => {
    const request = response.request();
    const entry = pendingRequests.get(request);
    if (!entry) {
      return;
    }
    entry.status = response.status();
    entry.finishedAt = Date.now();
    pendingRequests.delete(request);
  };

  const onRequestFailed = (request: Request) => {
    const entry = pendingRequests.get(request);
    if (!entry) {
      return;
    }
    entry.failureText = request.failure()?.errorText || 'request_failed';
    entry.finishedAt = Date.now();
    pendingRequests.delete(request);
  };

  const onConsole = (message: ConsoleMessage) => {
    if (message.type() === 'error' && !message.text().includes('favicon.ico')) {
      consoleErrors.push(message.text());
    }
  };

  const onPageError = (error: Error) => {
    pageErrors.push(error.message);
  };

  page.on('request', onRequest);
  page.on('response', onResponse);
  page.on('requestfailed', onRequestFailed);
  page.on('console', onConsole);
  page.on('pageerror', onPageError);

  return {
    apiRequests,
    consoleErrors,
    pageErrors,
    cleanup: () => {
      page.off('request', onRequest);
      page.off('response', onResponse);
      page.off('requestfailed', onRequestFailed);
      page.off('console', onConsole);
      page.off('pageerror', onPageError);
    },
    count: (path: string) => apiRequests.filter((entry) => entry.path === path).length,
    snapshot: (paths: readonly string[]) => Object.fromEntries(paths.map((path) => [path, apiRequests.filter((entry) => entry.path === path).length])),
    failedRequests: () => apiRequests.filter((entry) => entry.failureText !== null),
    unexpectedFailedRequests: () => apiRequests.filter((entry) => entry.failureText !== null && !isExpectedCryptoStreamAbort(entry)),
    httpErrors: () => apiRequests.filter((entry) => entry.status !== null && entry.status >= 400),
  };
}

async function installApiProxy(page: Page): Promise<void> {
  await page.route('**/api/**', async (route: Route) => {
    const requestUrl = new URL(route.request().url());
    const response = await route.fetch({
      url: `${backendBaseUrl}${requestUrl.pathname}${requestUrl.search}`,
    });
    await route.fulfill({ response });
  });
}

async function installIntervalProbe(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const globalWindow = window as Window & {
      __t270MarketOverviewIntervalProbe?: {
        reset: () => void;
        snapshot: () => Array<{
          id: number;
          delay: number;
          active: boolean;
          fired: number;
          createdAt: number;
          clearedAt: number | null;
          createdPath: string;
        }>;
      };
    };

    if (globalWindow.__t270MarketOverviewIntervalProbe) {
      return;
    }

    const originalSetInterval = window.setInterval.bind(window);
    const originalClearInterval = window.clearInterval.bind(window);
    const records: Array<{
      id: number;
      delay: number;
      active: boolean;
      fired: number;
      createdAt: number;
      clearedAt: number | null;
      createdPath: string;
    }> = [];
    const recordIndexById = new Map<number, number>();

    globalWindow.__t270MarketOverviewIntervalProbe = {
      reset: () => {
        records.length = 0;
        recordIndexById.clear();
      },
      snapshot: () => records.map((record) => ({ ...record })),
    };

    window.setInterval = ((handler: TimerHandler, timeout?: number, ...args: unknown[]) => {
      const record = {
        id: 0,
        delay: Number(timeout ?? 0),
        active: true,
        fired: 0,
        createdAt: Date.now(),
        clearedAt: null,
        createdPath: window.location.pathname,
      };

      const wrappedHandler = (...handlerArgs: unknown[]) => {
        record.fired += 1;
        if (typeof handler === 'function') {
          return handler(...handlerArgs);
        }
        return undefined;
      };

      const intervalId = Number(originalSetInterval(wrappedHandler as TimerHandler, timeout, ...args));
      record.id = intervalId;
      recordIndexById.set(intervalId, records.push(record) - 1);
      return intervalId;
    }) as typeof window.setInterval;

    window.clearInterval = ((handle?: number) => {
      const intervalId = Number(handle ?? 0);
      const recordIndex = recordIndexById.get(intervalId);
      if (recordIndex !== undefined) {
        const record = records[recordIndex];
        record.active = false;
        record.clearedAt = Date.now();
        recordIndexById.delete(intervalId);
      }
      return originalClearInterval(handle);
    }) as typeof window.clearInterval;
  });
}

async function readIntervalProbe(page: Page): Promise<IntervalProbeRecord[]> {
  return page.evaluate(() => {
    const probe = (window as Window & {
      __t270MarketOverviewIntervalProbe?: { snapshot: () => IntervalProbeRecord[] };
    }).__t270MarketOverviewIntervalProbe;
    return probe ? probe.snapshot() : [];
  });
}

async function resetIntervalProbe(page: Page): Promise<void> {
  await page.evaluate(() => {
    (window as Window & {
      __t270MarketOverviewIntervalProbe?: { reset: () => void };
    }).__t270MarketOverviewIntervalProbe?.reset();
  });
}

function activeMarketOverviewPollingOwners(records: IntervalProbeRecord[]): IntervalProbeRecord[] {
  return records.filter((record) => (
    record.active
    && record.createdPath.includes('/market-overview')
    && MARKET_OVERVIEW_POLLING_DELAYS.has(record.delay)
  ));
}

function clearedMarketOverviewPollingOwners(records: IntervalProbeRecord[]): IntervalProbeRecord[] {
  return records.filter((record) => (
    !record.active
    && record.createdPath.includes('/market-overview')
    && MARKET_OVERVIEW_POLLING_DELAYS.has(record.delay)
  ));
}

async function getAuthStatus(page: Page): Promise<AuthStatusPayload> {
  const response = await page.request.get(`${backendBaseUrl}/api/v1/auth/status`);
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function signIn(page: Page, redirectPath: string): Promise<void> {
  if (!smokeUsername || !smokePassword) {
    throw new Error('Set DSA_WEB_SMOKE_USERNAME and DSA_WEB_SMOKE_PASSWORD for auth-enabled live probes.');
  }

  await page.goto(`/login?redirect=${encodeURIComponent(redirectPath)}`);
  await page.locator('#username').fill(smokeUsername);
  await page.locator('#password').fill(smokePassword);
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/v1/auth/login') && response.status() === 200),
    page.getByRole('button', { name: /sign in|登录继续|授权进入工作台|完成设置并登录/i }).click(),
  ]);
}

async function openConsumerMarketOverview(page: Page): Promise<void> {
  const authStatus = await getAuthStatus(page);
  if (authStatus.authEnabled) {
    await signIn(page, MARKET_OVERVIEW_ROUTE);
  }
  await page.goto(MARKET_OVERVIEW_ROUTE);
  await page.waitForLoadState('domcontentloaded');
  await expect(page.getByTestId('market-overview-shell')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId('market-overview-card-volatility')).toBeVisible({ timeout: 15_000 });
}

async function waitForInitialMarketOverviewBaseline(page: Page, observer: RuntimeObserver): Promise<void> {
  await expect.poll(() => observer.count(VOLATILITY_PATH)).toBeGreaterThanOrEqual(1);
  await expect.poll(() => observer.count(LATE_STAGE_PATH)).toBeGreaterThanOrEqual(1);
  await expect.poll(async () => activeMarketOverviewPollingOwners(await readIntervalProbe(page)).length).toBe(3);
}

async function clickConsumerNav(page: Page, name: string | RegExp): Promise<void> {
  const desktopLink = page.getByTestId('shell-consumer-primary-nav').getByRole('link', { name }).first();
  if (await desktopLink.isVisible().catch(() => false)) {
    await desktopLink.click();
    return;
  }

  const moreButton = page.getByTestId('shell-consumer-primary-nav').getByRole('button', { name: '更多' }).first();
  if (await moreButton.isVisible().catch(() => false)) {
    await moreButton.click();
    const moreLink = page.getByTestId('shell-more-menu').getByRole('link', { name }).first();
    if (await moreLink.isVisible().catch(() => false)) {
      await moreLink.click();
      return;
    }
  }

  const mobileMenuButton = page.getByRole('button', { name: '打开导航菜单' });
  if (await mobileMenuButton.isVisible().catch(() => false)) {
    await mobileMenuButton.click();
    const drawerLink = page.getByRole('dialog', { name: '导航菜单' }).getByRole('link', { name }).first();
    if (await drawerLink.isVisible().catch(() => false)) {
      await drawerLink.click();
      return;
    }
  }

  throw new Error(`Consumer navigation link not reachable: ${String(name)}`);
}

function getVolatilityRefreshButton(page: Page) {
  return page.getByTestId('market-overview-card-volatility').getByRole('button', {
    name: /(?:刷新\s*波动率与风险压力|refresh.*volatility)/i,
  });
}

test.describe('T270 market overview deterministic probe', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!liveSmokeEnabled, 'Set DSA_WEB_LIVE_SMOKE=1 to run live market overview ownership probes.');
    test.skip(!routeApiRequests, 'Set DSA_WEB_SMOKE_ROUTE_API=1 so the preview app proxies /api to the local runtime.');

    await installIntervalProbe(page);
    await installApiProxy(page);
  });

  test.afterEach(async ({ page }) => {
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });

  test('one consumer manual refresh action produces exactly one logical refresh sequence', async ({ page }) => {
    const observer = createRuntimeObserver(page);

    try {
      await page.goto('/zh/login');
      await page.waitForLoadState('domcontentloaded');
      await resetIntervalProbe(page);

      await openConsumerMarketOverview(page);
      await waitForInitialMarketOverviewBaseline(page, observer);

      const refreshButton = getVolatilityRefreshButton(page);
      await expect(refreshButton).toBeVisible();

      const baselineCounts = observer.snapshot([
        ...MARKET_OVERVIEW_PANEL_PATHS,
        REGIME_READ_MODEL_PATH,
        ...OPERATOR_ONLY_READINESS_PATHS,
      ]);
      const baselinePollingOwners = activeMarketOverviewPollingOwners(await readIntervalProbe(page)).length;

      await Promise.all([
        page.waitForResponse((response) => (
          new URL(response.url()).pathname === VOLATILITY_PATH
          && response.request().method() === 'GET'
          && response.status() === 200
        )),
        refreshButton.click(),
      ]);

      await expect.poll(() => observer.count(VOLATILITY_PATH)).toBe(baselineCounts[VOLATILITY_PATH] + 1);
      await expect(refreshButton).toBeEnabled();

      expect(observer.count(VOLATILITY_PATH) - baselineCounts[VOLATILITY_PATH]).toBe(1);
      expect(observer.count(REGIME_READ_MODEL_PATH) - baselineCounts[REGIME_READ_MODEL_PATH]).toBe(0);

      OPERATOR_ONLY_READINESS_PATHS.forEach((path) => {
        expect(observer.count(path)).toBe(0);
      });
      expect(activeMarketOverviewPollingOwners(await readIntervalProbe(page)).length).toBe(baselinePollingOwners);

      expect(observer.unexpectedFailedRequests()).toEqual([]);
      expect(observer.httpErrors()).toEqual([]);
      expect(observer.consoleErrors).toEqual([]);
      expect(observer.pageErrors).toEqual([]);
    } finally {
      observer.cleanup();
    }
  });

  test('leaving and returning to the route does not create a duplicate polling owner', async ({ page }) => {
    const observer = createRuntimeObserver(page);

    try {
      await page.goto('/zh/login');
      await page.waitForLoadState('domcontentloaded');
      await resetIntervalProbe(page);

      await openConsumerMarketOverview(page);
      await waitForInitialMarketOverviewBaseline(page, observer);

      const firstEntryProbe = await readIntervalProbe(page);
      expect(activeMarketOverviewPollingOwners(firstEntryProbe).length).toBe(3);

      await clickConsumerNav(page, '首页');
      await expect(page).toHaveURL(/\/zh$/);
      await expect(page.getByTestId('home-bento-dashboard')).toBeVisible({ timeout: 15_000 });
      await expect.poll(async () => activeMarketOverviewPollingOwners(await readIntervalProbe(page)).length).toBe(0);

      const afterLeaveProbe = await readIntervalProbe(page);
      expect(clearedMarketOverviewPollingOwners(afterLeaveProbe).length).toBeGreaterThanOrEqual(3);

      await clickConsumerNav(page, '市场总览');
      await expect(page).toHaveURL(/\/zh\/market-overview$/);
      await waitForInitialMarketOverviewBaseline(page, observer);

      const secondEntryProbe = await readIntervalProbe(page);
      expect(activeMarketOverviewPollingOwners(secondEntryProbe).length).toBe(3);
      expect(clearedMarketOverviewPollingOwners(secondEntryProbe).length).toBeGreaterThanOrEqual(3);

      OPERATOR_ONLY_READINESS_PATHS.forEach((path) => {
        expect(observer.count(path)).toBe(0);
      });

      expect(observer.unexpectedFailedRequests()).toEqual([]);
      expect(observer.httpErrors()).toEqual([]);
      expect(observer.consoleErrors).toEqual([]);
      expect(observer.pageErrors).toEqual([]);
    } finally {
      observer.cleanup();
    }
  });
});
