import { expect, type ConsoleMessage, type Page, type Request, type Route } from '@playwright/test';
import {
  createMockAdminUser,
  createMockAuthStatus,
  type MockAdminUserOptions,
} from '../../src/test-utils/adminAuthHarness';
import type { AuthStatusResponse, CurrentUser } from '../../src/api/auth';

export type MockProductUserOptions = {
  id?: string;
  username?: string;
  displayName?: string;
  injectRawAuthCanaries?: boolean;
};

export type AuthenticatedRouteSmokeAuth = 'user' | 'admin';

export type ApiRequestLog = {
  calls: string[];
  count: (method: string, path: string) => number;
  wasFetched: (method: string, path: string) => boolean;
};

export type AuthenticatedRouteSmokeOptions = {
  auth?: AuthenticatedRouteSmokeAuth;
  user?: MockProductUserOptions;
  admin?: MockAdminUserOptions;
};

export type AuthenticatedRouteSmokeHarness = {
  auth: AuthenticatedRouteSmokeAuth;
  currentUser: CurrentUser;
  requests: ApiRequestLog;
  consolePageErrors: string[];
  openRoute: (path: string) => Promise<void>;
  expectNoConsolePageErrors: () => void;
  cleanup: () => Promise<void>;
};

export async function fulfillJson(route: Route, payload: unknown, status = 200) {
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

function createCurrentUser(options: AuthenticatedRouteSmokeOptions): CurrentUser {
  if (options.auth === 'admin') {
    return createMockAdminUser(options.admin);
  }
  return createMockProductUser(options.user);
}

function createMockProductUser(options: MockProductUserOptions = {}): CurrentUser {
  const user: CurrentUser = {
    id: options.id ?? 'user-1',
    username: options.username ?? 'wolfy-user',
    displayName: options.displayName ?? 'Wolfy User',
    role: 'user',
    isAdmin: false,
    isAuthenticated: true,
    transitional: false,
    authEnabled: true,
  };

  if (options.injectRawAuthCanaries) {
    const userWithHarnessMetadata = user as CurrentUser & Record<string, unknown>;
    userWithHarnessMetadata.sessionId = 'raw-session-canary-should-not-render';
    userWithHarnessMetadata.cookie = 'cookie-canary-should-not-render';
  }

  return user;
}

function createMockProductAuthStatus(currentUser: CurrentUser | null): AuthStatusResponse {
  return {
    authEnabled: true,
    loggedIn: Boolean(currentUser?.isAuthenticated),
    passwordSet: true,
    passwordChangeable: true,
    setupState: 'enabled',
    currentUser,
  };
}

function createAuthStatus(auth: AuthenticatedRouteSmokeAuth, currentUser: CurrentUser) {
  return auth === 'admin'
    ? createMockAuthStatus(currentUser)
    : createMockProductAuthStatus(currentUser);
}

export async function expectNoHorizontalOverflow(page: Page) {
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

export async function expectRouteRootNonEmpty(page: Page) {
  await expect.poll(async () => page.locator('#root').evaluate((root) => root.textContent?.trim().length ?? 0)).toBeGreaterThan(0);
}

export async function installSignedInSessionRoutes(
  page: Page,
  options: AuthenticatedRouteSmokeOptions = {},
): Promise<{ auth: AuthenticatedRouteSmokeAuth; currentUser: CurrentUser }> {
  const auth = options.auth ?? 'user';
  const currentUser = createCurrentUser({ ...options, auth });

  await page.route('**/api/v1/auth/status**', async (route) => {
    await fulfillJson(route, createAuthStatus(auth, currentUser));
  });
  await page.route('**/api/v1/auth/me**', async (route) => {
    await fulfillJson(route, currentUser);
  });

  return { auth, currentUser };
}

export async function openSignedInRoute(page: Page, path: string) {
  await page.goto(path);
  await page.waitForLoadState('domcontentloaded');
}

export async function installAuthenticatedRouteSmoke(
  page: Page,
  options: AuthenticatedRouteSmokeOptions = {},
): Promise<AuthenticatedRouteSmokeHarness> {
  const { auth, currentUser } = await installSignedInSessionRoutes(page, options);
  const calls: string[] = [];
  const requests = createRequestLog(calls);
  const consolePageErrors: string[] = [];

  const onRequest = (request: Request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/v1/')) {
      calls.push(`${request.method()} ${url.pathname}`);
    }
  };
  const onConsole = (message: ConsoleMessage) => {
    if (message.type() === 'error' && !message.text().includes('favicon.ico')) {
      consolePageErrors.push(message.text());
    }
  };
  const onPageError = (error: Error) => {
    consolePageErrors.push(error.message);
  };
  page.on('request', onRequest);
  page.on('console', onConsole);
  page.on('pageerror', onPageError);

  return {
    auth,
    currentUser,
    requests,
    consolePageErrors,
    openRoute: async (path: string) => {
      await openSignedInRoute(page, path);
      await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
      await expectRouteRootNonEmpty(page);
    },
    expectNoConsolePageErrors: () => {
      expect(consolePageErrors).toEqual([]);
    },
    cleanup: async () => {
      page.off('request', onRequest);
      page.off('console', onConsole);
      page.off('pageerror', onPageError);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    },
  };
}

export async function openAuthenticatedRouteSmoke(
  page: Page,
  path: string,
  options: AuthenticatedRouteSmokeOptions = {},
): Promise<AuthenticatedRouteSmokeHarness> {
  const harness = await installAuthenticatedRouteSmoke(page, options);
  await harness.openRoute(path);
  return harness;
}
