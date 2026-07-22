import { expect, test, type Page } from '@playwright/test';
import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { closeSync, existsSync, mkdtempSync, openSync, rmSync, writeFileSync } from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

type CurrentUserPayload = {
  id: string;
  username: string;
  role: string;
  isAdmin: boolean;
  isAuthenticated: boolean;
  adminCapabilities: string[];
};

type AuthStatusPayload = {
  authEnabled: boolean;
  loggedIn: boolean;
  passwordSet: boolean;
  setupState: string;
  currentUser: CurrentUserPayload | null;
};

type AuthContracts = {
  statusHttpStatus: number;
  status: AuthStatusPayload;
  meHttpStatus: number;
  me: CurrentUserPayload;
};

type BrowserDiagnostics = {
  consoleErrors: string[];
  pageErrors: string[];
  failedRequests: string[];
  observedEndpoints: Set<string>;
};

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const webRoot = path.join(repoRoot, 'apps/dsa-web');
const staticRoot = path.join(repoRoot, 'static');
const python = process.env.PYTHON || path.join(
  repoRoot,
  '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
);

let runtime: ChildProcess | undefined;
let runtimeDir = '';
let runtimeLogFd: number | undefined;
let databasePath = '';
let baseUrl = '';
let bootstrapPassword = '';
let canonicalSuperAdminCapabilities: string[] = [];
let taskBuiltStatic = false;

async function reservePort(): Promise<number> {
  const server = net.createServer();
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const address = server.address();
  if (!address || typeof address === 'string') {
    server.close();
    throw new Error('Unable to reserve a bootstrap-admin browser-test port');
  }
  await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  return address.port;
}

async function waitForRuntime(): Promise<void> {
  const deadline = Date.now() + 90_000;
  while (Date.now() < deadline) {
    if (runtime?.exitCode !== null) {
      throw new Error(`Bootstrap-admin runtime exited before readiness (code ${runtime?.exitCode})`);
    }
    try {
      const response = await fetch(`${baseUrl}/api/health/live`);
      if (response.ok) return;
    } catch {
      // The disposable local runtime is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error('Bootstrap-admin runtime did not become live');
}

function readCanonicalSuperAdminCapabilities(): string[] {
  const output = execFileSync(python, [
    '-c',
    [
      'import json',
      'from src.admin_rbac import ADMIN_RBAC_ROLE_CAPABILITIES, SUPER_ADMIN_ROLE',
      'print(json.dumps(sorted(ADMIN_RBAC_ROLE_CAPABILITIES[SUPER_ADMIN_ROLE])))',
    ].join('; '),
  ], { cwd: repoRoot, encoding: 'utf8' });
  const capabilities = JSON.parse(output) as unknown;
  if (!Array.isArray(capabilities) || capabilities.some((value) => typeof value !== 'string')) {
    throw new Error('Canonical super-admin capability contract is invalid');
  }
  return [...capabilities].sort();
}

function captureBrowserDiagnostics(page: Page): BrowserDiagnostics {
  const diagnostics: BrowserDiagnostics = {
    consoleErrors: [],
    pageErrors: [],
    failedRequests: [],
    observedEndpoints: new Set<string>(),
  };
  page.on('console', (message) => {
    if (message.type() === 'error') diagnostics.consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => diagnostics.pageErrors.push(error.message));
  page.on('requestfailed', (request) => {
    const url = new URL(request.url());
    diagnostics.failedRequests.push(`${request.method()} ${url.pathname}: ${request.failure()?.errorText || 'failed'}`);
  });
  page.on('response', (response) => {
    const url = new URL(response.url());
    if (url.origin === baseUrl && url.pathname.startsWith('/api/')) {
      diagnostics.observedEndpoints.add(`${response.request().method()} ${url.pathname} ${response.status()}`);
    }
  });
  return diagnostics;
}

async function readAuthContracts(page: Page): Promise<AuthContracts> {
  return page.evaluate(async () => {
    const statusResponse = await fetch('/api/v1/auth/status', { cache: 'no-store' });
    const meResponse = await fetch('/api/v1/auth/me', { cache: 'no-store' });
    return {
      statusHttpStatus: statusResponse.status,
      status: await statusResponse.json(),
      meHttpStatus: meResponse.status,
      me: await meResponse.json(),
    };
  });
}

function expectCanonicalCapabilities(contracts: AuthContracts): void {
  expect(contracts.statusHttpStatus).toBe(200);
  expect(contracts.meHttpStatus).toBe(200);
  expect(contracts.status.loggedIn).toBe(true);
  expect(contracts.status.currentUser?.isAuthenticated).toBe(true);
  expect(contracts.status.currentUser?.isAdmin).toBe(true);
  expect(contracts.me.isAuthenticated).toBe(true);
  expect(contracts.me.isAdmin).toBe(true);
  expect(canonicalSuperAdminCapabilities.length).toBeGreaterThan(0);
  expect([...(contracts.status.currentUser?.adminCapabilities || [])].sort()).toEqual(canonicalSuperAdminCapabilities);
  expect([...contracts.me.adminCapabilities].sort()).toEqual(canonicalSuperAdminCapabilities);
}

test.describe('bootstrap-admin real-browser regression', () => {
  test.describe.configure({ mode: 'serial', retries: 0, timeout: 240_000 });
  test.skip(({ isMobile }) => isMobile, 'The bootstrap-admin persistence journey runs once in desktop Chromium.');

  test.beforeAll(async () => {
    test.setTimeout(180_000);
    if (existsSync(staticRoot)) {
      throw new Error('Bootstrap-admin browser regression requires an absent canonical static directory');
    }
    execFileSync('npm', ['exec', '--', 'vite', 'build', '--outDir', '../../static', '--emptyOutDir'], {
      cwd: webRoot,
      stdio: ['ignore', 'ignore', 'inherit'],
    });
    taskBuiltStatic = true;

    runtimeDir = mkdtempSync(path.join(os.tmpdir(), 'wolfystock-bootstrap-admin-browser-'));
    databasePath = path.join(runtimeDir, 'bootstrap-admin-browser.sqlite');
    bootstrapPassword = randomBytes(24).toString('base64url');
    canonicalSuperAdminCapabilities = readCanonicalSuperAdminCapabilities();
    expect(existsSync(databasePath)).toBe(false);
    expect(existsSync(path.join(runtimeDir, '.admin_password_hash'))).toBe(false);

    const port = await reservePort();
    baseUrl = `http://127.0.0.1:${port}`;
    const envPath = path.join(runtimeDir, '.env');
    writeFileSync(envPath, [
      'ADMIN_AUTH_ENABLED=true',
      'APP_ENV=test',
      'CRYPTO_REALTIME_ENABLED=false',
      'PREFETCH_REALTIME_QUOTES=false',
      'WEBUI_AUTO_BUILD=false',
      'WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED=false',
      'WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED=false',
      'WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED=false',
      'WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS=true',
      'WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED=false',
      'STOCK_LIST=AAPL',
    ].join('\n'), 'utf8');
    const runtimeEnv = {
      ...process.env,
      ADMIN_AUTH_ENABLED: 'true',
      APP_ENV: 'test',
      CRYPTO_REALTIME_ENABLED: 'false',
      DATABASE_PATH: databasePath,
      ENV_FILE: envPath,
      LOG_DIR: path.join(runtimeDir, 'logs'),
      POSTGRES_PHASE_A_URL: '',
      PREFETCH_REALTIME_QUOTES: 'false',
      WEBUI_AUTO_BUILD: 'false',
      WOLFYSTOCK_ADMIN_RBAC_COARSE_FALLBACK_ENABLED: 'false',
      WOLFYSTOCK_HISTORICAL_OHLCV_CACHE_SEED_ENABLED: 'false',
      WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED: 'false',
      WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS: 'true',
      WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED: 'false',
    };
    runtimeLogFd = openSync(path.join(runtimeDir, 'runtime.log'), 'a');
    runtime = spawn(
      python,
      [path.join(repoRoot, 'main.py'), '--serve-only', '--host', '127.0.0.1', '--port', String(port)],
      { cwd: repoRoot, env: runtimeEnv, stdio: ['ignore', runtimeLogFd, runtimeLogFd], windowsHide: true },
    );
    await waitForRuntime();
    expect(existsSync(databasePath)).toBe(true);
  });

  test.afterAll(async () => {
    if (runtime && runtime.exitCode === null) {
      runtime.kill();
      await new Promise<void>((resolve) => {
        runtime?.once('exit', () => resolve());
        setTimeout(resolve, 5_000);
      });
    }
    if (runtimeLogFd !== undefined) closeSync(runtimeLogFd);
    if (runtimeDir) rmSync(runtimeDir, { recursive: true, force: true, maxRetries: 10, retryDelay: 250 });
    if (taskBuiltStatic) rmSync(staticRoot, { recursive: true, force: true });
  });

  test('persists canonical capabilities from first setup through admin navigation, reload, and logout', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    const diagnostics = captureBrowserDiagnostics(page);
    page.setDefaultTimeout(30_000);

    try {
      const initialStatusResponse = await page.request.get(`${baseUrl}/api/v1/auth/status`);
      expect(initialStatusResponse.status()).toBe(200);
      const initialStatus = await initialStatusResponse.json() as AuthStatusPayload;
      expect(initialStatus).toMatchObject({
        authEnabled: true,
        loggedIn: false,
        passwordSet: false,
        setupState: 'no_password',
        currentUser: null,
      });

      await page.goto(`${baseUrl}/en/login?redirect=%2Fen%2Fsettings`);
      await expect(page.locator('#username')).toHaveCount(0);
      await expect(page.locator('#passwordConfirm')).toBeVisible();
      await page.locator('#password').fill(bootstrapPassword);
      await page.locator('#passwordConfirm').fill(bootstrapPassword);
      const loginResponsePromise = page.waitForResponse((response) => (
        response.url().endsWith('/api/v1/auth/login') && response.request().method() === 'POST'
      ));
      await page.locator('button[type="submit"]').click();
      const loginResponse = await loginResponsePromise;
      expect(loginResponse.status()).toBe(200);
      const loginPayload = await loginResponse.json() as { currentUser: CurrentUserPayload };
      expect([...loginPayload.currentUser.adminCapabilities].sort()).toEqual(canonicalSuperAdminCapabilities);
      await expect(page).toHaveURL(/\/en\/settings$/, { timeout: 30_000 });

      const sessionCookies = (await context.cookies(baseUrl)).filter((cookie) => cookie.name === 'dsa_session');
      expect(sessionCookies).toHaveLength(1);
      expect(sessionCookies[0]).toMatchObject({ httpOnly: true, path: '/', sameSite: 'Lax' });

      const initialContracts = await readAuthContracts(page);
      expectCanonicalCapabilities(initialContracts);
      expect(initialContracts.status.setupState).toBe('enabled');
      expect(initialContracts.status.currentUser).toEqual(initialContracts.me);

      const systemEntry = page.getByRole('button', { name: 'System', exact: true });
      await expect(systemEntry).toBeVisible();
      await systemEntry.click();
      const adminMenu = page.getByTestId('shell-admin-utility-menu');
      const systemLink = adminMenu.getByRole('link', { name: 'Ops Overview / System Settings' });
      await expect(systemLink).toBeVisible();
      await expect(adminMenu.getByRole('link', { name: 'System Logs' })).toBeVisible();
      await systemLink.click();
      await expect(page).toHaveURL(/\/en\/settings\/system$/);
      await expect(page.getByTestId('system-settings-page')).toBeVisible();

      const adminNav = page.getByTestId('shell-admin-primary-nav');
      await expect(adminNav).toBeVisible();
      await adminNav.getByRole('link', { name: 'System Logs' }).click();
      await expect(page).toHaveURL(/\/en\/admin\/logs$/);
      await expect(page.getByTestId('admin-logs-workspace')).toBeVisible();

      await page.reload({ waitUntil: 'domcontentloaded' });
      await expect(page.getByTestId('admin-logs-workspace')).toBeVisible();
      const reloadedContracts = await readAuthContracts(page);
      expectCanonicalCapabilities(reloadedContracts);
      expect(reloadedContracts.status.currentUser).toEqual(reloadedContracts.me);

      const accountEntry = page.locator('[data-testid="shell-account-center-entry"]:visible');
      await accountEntry.getByRole('button', { name: 'Account Center' }).click();
      const accountMenu = page.locator('[data-testid="shell-account-center-menu"]:visible');
      await accountMenu.getByRole('menuitem', { name: 'Log out' }).click();
      const logoutDialog = page.getByRole('dialog', { name: 'Log out' });
      const logoutResponsePromise = page.waitForResponse((response) => (
        response.url().endsWith('/api/v1/auth/logout') && response.request().method() === 'POST'
      ));
      await logoutDialog.getByRole('button', { name: 'Log out' }).click();
      expect((await logoutResponsePromise).status()).toBe(204);
      await expect(page).toHaveURL(/\/en\/guest$/, { timeout: 30_000 });
      await expect(page.getByRole('button', { name: 'System', exact: true })).toHaveCount(0);
      await expect(page.getByTestId('shell-admin-utility-menu')).toHaveCount(0);
      await expect(page.getByTestId('shell-admin-primary-nav')).toHaveCount(0);
      expect((await context.cookies(baseUrl)).some((cookie) => cookie.name === 'dsa_session')).toBe(false);

      const loggedOutStatusResponse = await page.request.get(`${baseUrl}/api/v1/auth/status`);
      expect(loggedOutStatusResponse.status()).toBe(200);
      expect(await loggedOutStatusResponse.json()).toMatchObject({
        loggedIn: false,
        setupState: 'enabled',
        currentUser: null,
      });

      for (const endpoint of [
        'POST /api/v1/auth/login 200',
        'GET /api/v1/auth/status 200',
        'GET /api/v1/auth/me 200',
        'POST /api/v1/auth/logout 204',
      ]) {
        expect(diagnostics.observedEndpoints).toContain(endpoint);
      }
      expect(diagnostics.consoleErrors).toEqual([]);
      expect(diagnostics.pageErrors).toEqual([]);
      const unexpectedFailedRequests = diagnostics.failedRequests.filter((entry) => (
        !entry.includes('GET /api/v1/admin/logs/storage/summary: net::ERR_ABORTED')
      ));
      expect(unexpectedFailedRequests).toEqual([]);
    } finally {
      await context.close();
    }
  });
});
