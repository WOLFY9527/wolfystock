import { expect, test, type Page, type Response } from '@playwright/test';
import { randomBytes } from 'node:crypto';
import { spawn, type ChildProcess } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const webRoot = path.join(repoRoot, 'apps', 'dsa-web');
const python = process.env.PYTHON || path.join(
  repoRoot,
  '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
);
const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';

let backend: ChildProcess | undefined;
let frontend: ChildProcess | undefined;
let runtimeDir = '';
let appUrl = '';

test.skip(({ isMobile }) => Boolean(isMobile), 'T676 owns one isolated desktop browser journey.');

type CurrentUser = {
  id: string;
  username: string;
  displayName: string | null;
  role: string;
  isAdmin: boolean;
  isAuthenticated: boolean;
  transitional: boolean;
  authEnabled: boolean;
  adminCapabilities: string[];
  canReadUsers: boolean;
  canReadUserActivity: boolean;
  canReadUserPortfolio: boolean;
  canWriteUserSecurity: boolean;
  canReadCostObservability: boolean;
  canReadOpsLogs: boolean;
  canReadProviders: boolean;
  canReadNotifications: boolean;
  canReadSystemConfig: boolean;
};

type AuthStatus = {
  authEnabled: boolean;
  loggedIn: boolean;
  passwordSet: boolean;
  setupState: string;
  currentUser: CurrentUser | null;
};

async function reservePort(): Promise<number> {
  const server = net.createServer();
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const address = server.address();
  if (!address || typeof address === 'string') {
    server.close();
    throw new Error('Unable to reserve a local browser-test port');
  }
  const port = address.port;
  await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  return port;
}

async function waitForHttp(url: string, processes: ChildProcess[]): Promise<void> {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    const exited = processes.find((process) => process.exitCode !== null);
    if (exited) {
      throw new Error(`Local browser runtime exited before readiness (code ${exited.exitCode})`);
    }
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // The isolated local runtime is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Local browser runtime did not become ready: ${url}`);
}

async function stopProcess(child: ChildProcess | undefined): Promise<void> {
  if (!child || child.exitCode !== null) return;

  try {
    if (process.platform !== 'win32' && child.pid) {
      process.kill(-child.pid, 'SIGTERM');
    } else {
      child.kill('SIGTERM');
    }
  } catch {
    child.kill('SIGTERM');
  }

  await Promise.race([
    new Promise<void>((resolve) => child.once('exit', () => resolve())),
    new Promise<void>((resolve) => setTimeout(resolve, 5_000)),
  ]);
  if (child.exitCode === null) child.kill('SIGKILL');
}

async function readAuthStatus(page: Page): Promise<AuthStatus> {
  return page.evaluate(async () => {
    const response = await fetch('/api/v1/auth/status');
    if (!response.ok) throw new Error(`auth status failed with ${response.status}`);
    return response.json();
  });
}

async function readCurrentUser(page: Page): Promise<CurrentUser> {
  return page.evaluate(async () => {
    const response = await fetch('/api/v1/auth/me');
    if (!response.ok) throw new Error(`current user failed with ${response.status}`);
    return response.json();
  });
}

function expectOrdinaryIdentity(user: CurrentUser, username: string, displayName: string): void {
  expect(user).toMatchObject({
    username,
    displayName,
    role: 'user',
    isAdmin: false,
    isAuthenticated: true,
    transitional: false,
    authEnabled: true,
    adminCapabilities: [],
    canReadUsers: false,
    canReadUserActivity: false,
    canReadUserPortfolio: false,
    canWriteUserSecurity: false,
    canReadCostObservability: false,
    canReadOpsLogs: false,
    canReadProviders: false,
    canReadNotifications: false,
    canReadSystemConfig: false,
  });
}

async function logoutFromAccountMenu(page: Page): Promise<Response> {
  const accountEntry = page.locator('[data-testid="shell-account-center-entry"]:visible');
  await expect(accountEntry).toHaveCount(1);
  await accountEntry.getByRole('button', { name: '账户中心' }).click();

  const accountMenu = page.locator('[data-testid="shell-account-center-menu"]:visible');
  await expect(accountMenu).toHaveCount(1);
  await accountMenu.getByRole('menuitem', { name: '退出登录' }).click();

  const dialog = page.getByRole('dialog', { name: '退出登录' });
  await expect(dialog).toBeVisible();
  const responsePromise = page.waitForResponse(
    (response) => response.url().endsWith('/api/v1/auth/logout') && response.request().method() === 'POST',
  );
  await dialog.getByRole('button', { name: '确认退出' }).click();
  const response = await responsePromise;
  await expect(page).toHaveURL(/\/zh\/guest$/, { timeout: 30_000 });
  return response;
}

function visibleConsumerNav(page: Page) {
  return page.locator('[data-testid="shell-consumer-primary-nav"]:visible');
}

function expectNoAdminNavigation(page: Page): Promise<void> {
  return expect(page.locator([
    '[data-testid="shell-admin-primary-nav"]:visible',
    '[data-testid="shell-admin-utility-menu"]:visible',
    '[aria-controls="shell-admin-utility-menu"]:visible',
    'a[href*="/admin/"]:visible',
    'a[href$="/settings/system"]:visible',
  ].join(','))).toHaveCount(0);
}

function isExpectedNavigationAbort(method: string, errorText: string): boolean {
  return method === 'GET' && errorText === 'net::ERR_ABORTED';
}

test.beforeAll(async () => {
  test.setTimeout(120_000);
  runtimeDir = await mkdtemp(path.join(os.tmpdir(), 'wolfystock-t676-browser-'));
  const envPath = path.join(runtimeDir, '.env');
  await writeFile(envPath, [
    'ADMIN_AUTH_ENABLED=false',
    'APP_ENV=test',
    'CRYPTO_REALTIME_ENABLED=false',
    'WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS=true',
    'WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED=false',
    'WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED=false',
    'STOCK_LIST=AAPL',
  ].join('\n'), 'utf8');

  const backendPort = await reservePort();
  let frontendPort = await reservePort();
  while (frontendPort === backendPort) frontendPort = await reservePort();
  const backendUrl = `http://127.0.0.1:${backendPort}`;
  appUrl = `http://127.0.0.1:${frontendPort}`;

  const viteConfigPath = path.join(runtimeDir, 'vite.t676.config.ts');
  await writeFile(viteConfigPath, [
    `import base from ${JSON.stringify(path.join(webRoot, 'vite.config.ts'))}`,
    'export default {',
    '  ...base,',
    `  cacheDir: ${JSON.stringify(path.join(runtimeDir, 'vite-cache'))},`,
    '  server: {',
    '    ...(base.server || {}),',
    "    host: '127.0.0.1',",
    `    port: ${frontendPort},`,
    '    strictPort: true,',
    `    proxy: { '/api': { target: ${JSON.stringify(backendUrl)}, changeOrigin: true } },`,
    '  },',
    '}',
  ].join('\n'), 'utf8');

  backend = spawn(python, [
    '-m',
    'uvicorn',
    'api.app:app',
    '--host',
    '127.0.0.1',
    '--port',
    String(backendPort),
    '--log-level',
    'warning',
  ], {
    cwd: repoRoot,
    detached: process.platform !== 'win32',
    env: {
      ...process.env,
      ADMIN_AUTH_ENABLED: 'false',
      APP_ENV: 'test',
      CRYPTO_REALTIME_ENABLED: 'false',
      DATABASE_PATH: path.join(runtimeDir, 't676-auth-browser.sqlite'),
      ENV_FILE: envPath,
      LOG_DIR: path.join(runtimeDir, 'logs'),
      POSTGRES_PHASE_A_URL: '',
      WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS: 'true',
      WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED: 'false',
      WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED: 'false',
    },
    stdio: 'ignore',
    windowsHide: true,
  });
  await waitForHttp(`${backendUrl}/api/health/live`, [backend]);

  frontend = spawn(npm, [
    '--prefix',
    webRoot,
    'run',
    'dev',
    '--',
    '--config',
    viteConfigPath,
  ], {
    cwd: repoRoot,
    detached: process.platform !== 'win32',
    env: process.env,
    stdio: 'ignore',
    windowsHide: true,
  });
  await waitForHttp(appUrl, [backend, frontend]);
});

test.afterAll(async () => {
  await stopProcess(frontend);
  await stopProcess(backend);
  if (runtimeDir) {
    await rm(runtimeDir, { recursive: true, force: true, maxRetries: 10, retryDelay: 250 });
  }
});

test('creates and restores an ordinary-user session through the real browser journey', async ({ page }) => {
  test.setTimeout(240_000);
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedRequests: string[] = [];
  const httpErrors: string[] = [];

  page.on('console', (message) => {
    if (message.type() === 'error' && !message.text().includes('favicon.ico')) {
      consoleErrors.push(message.text());
    }
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('requestfailed', (request) => {
    const errorText = request.failure()?.errorText || 'unknown failure';
    if (!isExpectedNavigationAbort(request.method(), errorText)) {
      failedRequests.push(`${request.method()} ${request.url()} ${errorText}`);
    }
  });
  page.on('response', (response) => {
    if (response.status() >= 400 && !new URL(response.url()).pathname.endsWith('/favicon.ico')) {
      httpErrors.push(`${response.request().method()} ${response.status()} ${response.url()}`);
    }
  });

  const adminPassword = randomBytes(24).toString('base64url');
  await page.goto(`${appUrl}/zh/login?redirect=%2Fzh`, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#passwordConfirm')).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('#username')).toHaveCount(0);
  expect(await readAuthStatus(page)).toMatchObject({
    authEnabled: false,
    loggedIn: false,
    passwordSet: false,
    setupState: 'no_password',
    currentUser: null,
  });

  await page.locator('#password').fill(adminPassword);
  await page.locator('#passwordConfirm').fill(adminPassword);
  const initializeResponsePromise = page.waitForResponse(
    (response) => response.url().endsWith('/api/v1/auth/settings') && response.request().method() === 'POST',
  );
  await page.locator('button[type="submit"]').click();
  expect((await initializeResponsePromise).status()).toBe(200);
  await expect(page).toHaveURL(/\/zh\/?$/, { timeout: 30_000 });
  await expect(page.locator('[data-testid="shell-account-center-entry"]:visible')).toHaveCount(1);
  expect(await readAuthStatus(page)).toMatchObject({
    authEnabled: true,
    loggedIn: true,
    passwordSet: true,
    setupState: 'enabled',
    currentUser: { username: 'admin', role: 'admin', isAdmin: true, isAuthenticated: true },
  });

  expect((await logoutFromAccountMenu(page)).status()).toBe(204);
  expect(await readAuthStatus(page)).toMatchObject({
    authEnabled: true,
    loggedIn: false,
    setupState: 'enabled',
    currentUser: null,
  });

  const suffix = randomBytes(6).toString('hex');
  const username = `t676-${suffix}`;
  const displayName = `T676 Ordinary User ${suffix}`;
  const password = randomBytes(24).toString('base64url');
  await page.goto(`${appUrl}/zh/register?redirect=%2Fzh`, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#username')).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('#displayName')).toBeVisible();
  await expect(page.locator('#passwordConfirm')).toBeVisible();
  await page.locator('#username').fill(username);
  await page.locator('#displayName').fill(displayName);
  await page.locator('#password').fill(password);
  await page.locator('#passwordConfirm').fill(password);

  const registrationResponsePromise = page.waitForResponse(
    (response) => response.url().endsWith('/api/v1/auth/login') && response.request().method() === 'POST',
  );
  await page.locator('button[type="submit"]').click();
  const registrationResponse = await registrationResponsePromise;
  expect(registrationResponse.status()).toBe(200);
  const registrationPayload = await registrationResponse.json();
  expect(registrationPayload.createdUser).toBe(true);
  expectOrdinaryIdentity(registrationPayload.currentUser, username, displayName);

  await expect(page).toHaveURL(/\/zh\/?$/, { timeout: 30_000 });
  const createdIdentity = await readCurrentUser(page);
  expectOrdinaryIdentity(createdIdentity, username, displayName);
  expect(await readAuthStatus(page)).toMatchObject({
    authEnabled: true,
    loggedIn: true,
    setupState: 'enabled',
    currentUser: { id: createdIdentity.id, username, role: 'user', isAdmin: false },
  });
  await expectNoAdminNavigation(page);

  const watchlistLink = visibleConsumerNav(page).getByRole('link', { name: '观察列表', exact: true });
  await expect(watchlistLink).toBeVisible();
  await watchlistLink.click();
  await expect(page).toHaveURL(/\/zh\/watchlist$/);
  await expect(page.getByTestId('watchlist-page')).toBeVisible({ timeout: 30_000 });

  const portfolioLink = visibleConsumerNav(page).getByRole('link', { name: '持仓', exact: true });
  await expect(portfolioLink).toBeVisible();
  await portfolioLink.click();
  await expect(page).toHaveURL(/\/zh\/portfolio$/);
  await expect(page.getByTestId('portfolio-bento-page')).toBeVisible({ timeout: 30_000 });
  await expectNoAdminNavigation(page);

  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page).toHaveURL(/\/zh\/portfolio$/);
  await expect(page.getByTestId('portfolio-bento-page')).toBeVisible({ timeout: 30_000 });
  expectOrdinaryIdentity(await readCurrentUser(page), username, displayName);
  const sessionCookie = (await page.context().cookies(appUrl)).find((cookie) => cookie.name === 'dsa_session');
  expect(sessionCookie).toMatchObject({ httpOnly: true, sameSite: 'Lax' });

  expect((await logoutFromAccountMenu(page)).status()).toBe(204);
  expect((await page.context().cookies(appUrl)).some((cookie) => cookie.name === 'dsa_session')).toBe(false);
  expect(await readAuthStatus(page)).toMatchObject({ loggedIn: false, currentUser: null });

  const guestWatchlistLink = visibleConsumerNav(page).getByRole('link', { name: '观察列表', exact: true });
  await expect(guestWatchlistLink).toBeVisible();
  await guestWatchlistLink.click();
  await expect(page).toHaveURL(/\/zh\/watchlist$/);
  await expect(page.getByTestId('auth-guard-overlay')).toBeVisible();
  await expect(page.getByTestId('watchlist-page')).toHaveCount(0);

  await page.getByTestId('auth-guard-primary-action').click();
  await expect(page).toHaveURL(/\/zh\/login\?redirect=%2Fzh%2Fwatchlist$/);
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(password);
  const signInResponsePromise = page.waitForResponse(
    (response) => response.url().endsWith('/api/v1/auth/login') && response.request().method() === 'POST',
  );
  await page.locator('button[type="submit"]').click();
  expect((await signInResponsePromise).status()).toBe(200);
  await expect(page).toHaveURL(/\/zh\/watchlist$/, { timeout: 30_000 });
  await expect(page.getByTestId('watchlist-page')).toBeVisible({ timeout: 30_000 });

  const restoredIdentity = await readCurrentUser(page);
  expect(restoredIdentity.id).toBe(createdIdentity.id);
  expectOrdinaryIdentity(restoredIdentity, username, displayName);
  await expectNoAdminNavigation(page);

  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
  expect(httpErrors).toEqual([]);
});
