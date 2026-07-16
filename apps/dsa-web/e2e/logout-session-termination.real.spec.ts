import { expect, test, type Browser, type BrowserContext, type Page, type Response } from '@playwright/test';
import { randomBytes } from 'node:crypto';
import { spawn, type ChildProcess } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const python = process.env.PYTHON || path.join(
  repoRoot,
  '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
);

let runtime: ChildProcess | undefined;
let runtimeDir = '';
let baseUrl = '';

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

async function waitForRuntime(url: string): Promise<void> {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    if (runtime?.exitCode !== null) {
      throw new Error(`Local auth runtime exited before readiness (code ${runtime?.exitCode})`);
    }
    try {
      const response = await fetch(`${url}/api/health/live`);
      if (response.ok) return;
    } catch {
      // The local-only runtime is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error('Local auth runtime did not become ready');
}

async function installPrivateFlashRecorder(context: BrowserContext): Promise<void> {
  await context.addInitScript(() => {
    const state = window as typeof window & { __logoutPrivateFlash?: boolean };
    state.__logoutPrivateFlash = false;
    const record = () => {
      if (document.querySelector('[data-testid="admin-logs-workspace"]')) {
        state.__logoutPrivateFlash = true;
      }
    };
    new MutationObserver(record).observe(document, { childList: true, subtree: true });
    document.addEventListener('DOMContentLoaded', record, { once: true });
  });
}

async function authStatus(page: Page): Promise<{ httpStatus: number; loggedIn: boolean }> {
  return page.evaluate(async () => {
    const response = await fetch('/api/v1/auth/status');
    const payload = await response.json();
    return { httpStatus: response.status, loggedIn: Boolean(payload.loggedIn) };
  });
}

async function protectedStatus(page: Page): Promise<number> {
  return page.evaluate(async () => (await fetch('/api/v1/admin/users')).status);
}

async function login(page: Page, password: string): Promise<void> {
  await page.goto(`${baseUrl}/zh/login?redirect=%2Fzh%2Fadmin%2Flogs`);
  await expect(page.locator('#password')).toBeVisible({ timeout: 30_000 });
  const username = page.locator('#username');
  if (await username.isVisible().catch(() => false)) {
    await username.fill('admin');
  }
  await page.locator('#password').fill(password);
  const confirmation = page.locator('#passwordConfirm');
  if (await confirmation.isVisible().catch(() => false)) {
    await confirmation.fill(password);
  }
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(/\/zh\/admin\/logs$/, { timeout: 30_000 });
  await expect(page.getByTestId('admin-logs-workspace')).toBeVisible({ timeout: 30_000 });
  await expect.poll(() => authStatus(page)).toEqual({ httpStatus: 200, loggedIn: true });
  expect(await protectedStatus(page)).toBe(200);

  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.getByTestId('admin-logs-workspace')).toBeVisible({ timeout: 30_000 });
  await expect.poll(() => authStatus(page)).toEqual({ httpStatus: 200, loggedIn: true });
}

async function logoutFromShell(page: Page): Promise<Response> {
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

async function verifyLoggedOutRouteBoundary(page: Page): Promise<void> {
  await expect.poll(() => authStatus(page)).toEqual({ httpStatus: 200, loggedIn: false });
  expect(await protectedStatus(page)).toBe(401);

  await page.goto(`${baseUrl}/zh/admin/logs`);
  await expect(page.getByRole('heading', { name: '请使用管理员账户登录后查看日志' })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('admin-logs-workspace')).toHaveCount(0);
  expect(await page.evaluate(() => Boolean(
    (window as typeof window & { __logoutPrivateFlash?: boolean }).__logoutPrivateFlash,
  ))).toBe(false);

  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: '请使用管理员账户登录后查看日志' })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('admin-logs-workspace')).toHaveCount(0);

  await page.goto(`${baseUrl}/zh/guest`);
  await page.goBack({ waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: '请使用管理员账户登录后查看日志' })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('admin-logs-workspace')).toHaveCount(0);
  await page.goForward({ waitUntil: 'domcontentloaded' });
  await expect(page).toHaveURL(/\/zh\/guest$/);
}

test.beforeAll(async () => {
  runtimeDir = await mkdtemp(path.join(os.tmpdir(), 'wolfystock-logout-browser-'));
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

  const port = await reservePort();
  baseUrl = `http://127.0.0.1:${port}`;
  runtime = spawn(python, [
    '-m',
    'uvicorn',
    'api.app:app',
    '--host',
    '127.0.0.1',
    '--port',
    String(port),
    '--log-level',
    'warning',
  ], {
    cwd: repoRoot,
    env: {
      ...process.env,
      ADMIN_AUTH_ENABLED: 'false',
      APP_ENV: 'test',
      CRYPTO_REALTIME_ENABLED: 'false',
      DATABASE_PATH: path.join(runtimeDir, 'auth-browser.sqlite'),
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
  await waitForRuntime(baseUrl);
});

test.afterAll(async () => {
  if (runtime && runtime.exitCode === null) {
    runtime.kill();
    await new Promise<void>((resolve) => {
      runtime?.once('exit', () => resolve());
      setTimeout(resolve, 5_000);
    });
  }
  if (runtimeDir) {
    await rm(runtimeDir, { recursive: true, force: true, maxRetries: 10, retryDelay: 250 });
  }
});

test('terminates v2 sessions in two isolated browser contexts without private-content flash', async ({ browser }: { browser: Browser }) => {
  test.setTimeout(180_000);
  const password = randomBytes(24).toString('base64url');
  const contextA = await browser.newContext();
  const contextB = await browser.newContext();
  await installPrivateFlashRecorder(contextA);
  await installPrivateFlashRecorder(contextB);
  const pageA = await contextA.newPage();
  const pageB = await contextB.newPage();

  try {
    await login(pageA, password);
    await login(pageB, password);

    const logoutA = await logoutFromShell(pageA);
    expect(logoutA.status()).toBe(204);
    const logoutAHeaders = await logoutA.allHeaders();
    expect(logoutAHeaders['set-cookie']).toContain('Max-Age=0');
    expect(logoutAHeaders['set-cookie']).toContain('HttpOnly');
    expect(logoutAHeaders['set-cookie']).toContain('SameSite=lax');
    expect(logoutAHeaders['set-cookie']).toContain('Path=/');
    expect((await contextA.cookies(baseUrl)).some((cookie) => cookie.name === 'dsa_session')).toBe(false);
    await verifyLoggedOutRouteBoundary(pageA);

    expect(await authStatus(pageB)).toEqual({ httpStatus: 200, loggedIn: true });
    expect(await protectedStatus(pageB)).toBe(200);

    const logoutB = await logoutFromShell(pageB);
    expect(logoutB.status()).toBe(204);
    const logoutBHeaders = await logoutB.allHeaders();
    expect(logoutBHeaders['set-cookie']).toContain('Max-Age=0');
    expect(logoutBHeaders['set-cookie']).toContain('Path=/');
    expect((await contextB.cookies(baseUrl)).some((cookie) => cookie.name === 'dsa_session')).toBe(false);
    await verifyLoggedOutRouteBoundary(pageB);
  } finally {
    await contextA.close();
    await contextB.close();
  }
});
