import { expect, test, type Locator, type Page } from '@playwright/test';
import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { closeSync, existsSync, mkdtempSync, openSync, rmSync, writeFileSync } from 'node:fs';
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
let runtimeLogFd: number | undefined;
let baseUrl = '';
let adminPassword = '';
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
    throw new Error('Unable to reserve a T560 browser port');
  }
  await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  return address.port;
}

async function waitForRuntime(): Promise<void> {
  const deadline = Date.now() + 90_000;
  while (Date.now() < deadline) {
    if (runtime?.exitCode !== null) {
      throw new Error(`T560 runtime exited before readiness (code ${runtime?.exitCode})`);
    }
    try {
      const response = await fetch(`${baseUrl}/api/health/live`);
      if (response.ok) return;
    } catch {
      // The task-owned disposable runtime is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error('T560 runtime did not become live');
}

async function login(page: Page, redirect: string): Promise<void> {
  await page.goto(`${baseUrl}/en/login?redirect=${encodeURIComponent(redirect)}`);
  await expect(page.locator('#username')).toBeVisible({ timeout: 30_000 });
  await page.locator('#username').fill('admin');
  await page.locator('#password').fill(adminPassword);
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(new RegExp(`${redirect.replaceAll('/', '\\/')}(?:\\?.*)?$`), { timeout: 30_000 });
}

async function expectFocusInside(container: Locator): Promise<void> {
  const readState = () => container.evaluate((element) => {
    const active = document.activeElement as HTMLElement | null;
    return {
      contains: Boolean(active && element.contains(active)),
      activeTag: active?.tagName ?? null,
      activeId: active?.id ?? null,
      activeLabel: active?.getAttribute('aria-label') ?? active?.textContent?.trim().slice(0, 80) ?? null,
      activeDialog: active?.closest('[role="dialog"], dialog')?.getAttribute('aria-labelledby') ?? null,
    };
  });
  await expect.poll(readState).toMatchObject({ contains: true });
}

async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  await expect.poll(() => page.evaluate(() => (
    Math.max(0, Math.round(document.documentElement.scrollWidth - document.documentElement.clientWidth))
  ))).toBe(0);
}

async function exerciseMobileShell(page: Page): Promise<void> {
  const trigger = page.getByRole('button', { name: /Open menu|Open navigation/i });
  await expect(trigger).toHaveAttribute('aria-controls', 'shell-mobile-navigation-menu');
  await expect(trigger).toHaveAttribute('aria-owns', 'shell-mobile-navigation-menu');

  await trigger.click();
  const menu = page.getByTestId('shell-mobile-navigation-menu');
  const drawer = menu.locator('xpath=ancestor::dialog');
  await expect(menu).toBeVisible();
  await expect.poll(() => page.locator('#main-content').evaluate((element) => Boolean(element.closest('[inert]')))).toBe(true);
  await expectFocusInside(drawer);
  for (const key of ['Tab', 'Tab', 'Shift+Tab', 'Shift+Tab']) {
    await page.keyboard.press(key);
    await expectFocusInside(drawer);
  }
  await page.keyboard.press('Escape');
  await expect(menu).toHaveCount(0);
  await expect(trigger).toBeFocused();

  await trigger.click();
  await menu.getByRole('link', { name: 'Account Center' }).click();
  await expect(page).toHaveURL(/\/en\/settings$/);
  await expect(menu).toHaveCount(0);
  await expect(page.locator('#main-content')).toBeFocused();

  await trigger.click();
  await menu.getByRole('link', { name: 'Account Center' }).focus();
  await expectNoHorizontalOverflow(page);
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(menu).toHaveCount(0);
  await expect(page.locator('#main-content')).toBeFocused();
}

async function exerciseWatchlistMenu(page: Page): Promise<void> {
  const response = await page.request.post(`${baseUrl}/api/v1/watchlist/items`, {
    data: { symbol: 'AAPL', market: 'us', name: 'Apple', source: 'scanner' },
  });
  expect(response.status()).toBe(200);
  await page.goto(`${baseUrl}/en/watchlist`);
  await expect(page.getByTestId('watchlist-row-AAPL')).toBeVisible({ timeout: 30_000 });

  const trigger = page.getByRole('button', { name: /More actions AAPL/i });
  await trigger.focus();
  await page.keyboard.press('ArrowDown');
  const menu = page.getByTestId('watchlist-row-secondary-menu-AAPL');
  await expect(menu).toBeVisible();
  await expectFocusInside(menu);
  const firstItem = menu.getByRole('menuitem').first();
  await expect(firstItem).toBeFocused();
  await expect.poll(() => firstItem.evaluate((element) => {
    const style = getComputedStyle(element);
    return element.matches(':focus-visible') || style.outlineStyle !== 'none' || style.boxShadow !== 'none';
  })).toBe(true);
  for (const key of ['ArrowDown', 'ArrowUp', 'Tab', 'Shift+Tab']) {
    await page.keyboard.press(key);
    await expectFocusInside(menu);
  }
  await page.keyboard.press('Escape');
  await expect(menu).toHaveCount(0);
  await expect(trigger).toBeFocused();
}

async function createNestedOverlay(page: Page): Promise<{
  drawer: Locator;
  editTrigger: Locator;
}> {
  await page.goto(`${baseUrl}/en/settings/system?panel=data_sources`);
  await expect(page.getByRole('heading', { name: 'Data Source Settings' })).toBeVisible({ timeout: 30_000 });
  const addTrigger = page.getByRole('button', { name: 'Add data source' });
  await addTrigger.click();
  const createDrawer = page.getByRole('dialog', { name: 'Register data source' });
  await expect(createDrawer).toBeVisible();
  await createDrawer.getByLabel('Display name').fill('T560 Overlay Source');
  await createDrawer.getByLabel('API key / credential').fill('t560-disposable-credential');
  await createDrawer.getByText('Advanced Settings', { exact: false }).click();
  await createDrawer.getByRole('button', { name: 'News', exact: true }).click();
  await createDrawer.getByRole('button', { name: 'Create and save' }).click();

  const card = page.getByTestId('data-source-card-t560_overlay_source');
  await expect(card).toBeVisible({ timeout: 30_000 });
  await page.keyboard.press('Escape');
  await expect(createDrawer).toHaveCount(0);
  await expect(addTrigger).toBeFocused();

  const editTrigger = card.getByRole('button', { name: 'Edit' });
  await editTrigger.click();
  const drawer = page.getByRole('dialog', { name: 'T560 Overlay Source data source management' });
  await expect(drawer).toBeVisible();
  return { drawer, editTrigger };
}

async function exerciseOverlayStack(page: Page): Promise<void> {
  const { drawer, editTrigger } = await createNestedOverlay(page);
  const deleteTrigger = drawer.getByRole('button', { name: 'Delete source' });
  await deleteTrigger.click();
  const confirmation = page.getByRole('dialog', { name: 'Delete T560 Overlay Source' });
  await expect(confirmation).toBeVisible();
  await expect(confirmation.getByRole('button', { name: 'Cancel' })).toBeFocused();
  await expect.poll(() => drawer.evaluate((element) => Boolean(element.closest('[inert]')))).toBe(true);
  for (const key of ['Tab', 'Shift+Tab', 'Tab']) {
    await page.keyboard.press(key);
    await expectFocusInside(confirmation);
  }
  await page.keyboard.press('Escape');
  await expect(confirmation).toHaveCount(0);
  await expect(drawer).toBeVisible();
  await expectFocusInside(drawer);
  await page.keyboard.press('Escape');
  await expect(drawer).toHaveCount(0);
  await expect(editTrigger).toBeFocused();

  await editTrigger.click();
  const reopened = page.getByRole('dialog', { name: 'T560 Overlay Source data source management' });
  await expect(reopened).toBeVisible();
  await editTrigger.evaluate((element) => {
    (element as HTMLButtonElement).disabled = true;
  });
  await page.keyboard.press('Escape');
  await expect(reopened).toHaveCount(0);
  await expect(editTrigger).not.toBeFocused();
}

async function exerciseDesktopAccountAndSessionLoss(page: Page): Promise<void> {
  const trigger = page.locator('#shell-account-center-trigger');
  for (let cycle = 0; cycle < 3; cycle += 1) {
    await trigger.focus();
    await trigger.click();
    const menu = page.getByTestId('shell-account-center-menu');
    await expect(menu.getByRole('menuitem').first()).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(menu).toHaveCount(0);
    await expect(trigger).toBeFocused();
  }

  await trigger.click();
  const menu = page.getByTestId('shell-account-center-menu');
  await menu.getByRole('menuitem', { name: 'Log out' }).click();
  const confirmation = page.getByRole('dialog', { name: 'Log out' });
  await expect(confirmation).toBeVisible();
  const logoutResponse = page.waitForResponse((response) => (
    response.url().endsWith('/api/v1/auth/logout') && response.request().method() === 'POST'
  ));
  await confirmation.getByRole('button', { name: 'Log out' }).click();
  expect((await logoutResponse).status()).toBe(204);
  await expect(page).toHaveURL(/\/en\/guest$/, { timeout: 30_000 });
  await expect(trigger).toHaveCount(0);
  await expect(page.getByTestId('shell-admin-primary-nav')).toHaveCount(0);
}

test.describe('T560 integrated real-runtime focus authority', () => {
  test.describe.configure({ mode: 'serial', retries: 0, timeout: 240_000 });

  test.beforeAll(async () => {
    test.setTimeout(180_000);
    const staticRoot = path.join(repoRoot, 'static');
    if (existsSync(staticRoot)) {
      throw new Error('T560 requires an absent canonical static directory before its task-owned build');
    }
    execFileSync('npm', ['exec', '--', 'vite', 'build', '--outDir', '../../static', '--emptyOutDir'], {
      cwd: path.join(repoRoot, 'apps/dsa-web'),
      stdio: ['ignore', 'ignore', 'inherit'],
    });
    taskBuiltStatic = true;
    runtimeDir = mkdtempSync(path.join(os.tmpdir(), 'wolfystock-t560-browser-'));
    const port = await reservePort();
    baseUrl = `http://127.0.0.1:${port}`;
    adminPassword = randomBytes(24).toString('base64url');
    const memberPassword = randomBytes(24).toString('base64url');
    const envPath = path.join(runtimeDir, '.env');
    writeFileSync(envPath, [
      'ADMIN_AUTH_ENABLED=true',
      'APP_ENV=test',
      'CRYPTO_REALTIME_ENABLED=false',
      'WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS=true',
      'WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED=false',
      'WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED=false',
      'STOCK_LIST=AAPL',
    ].join('\n'), 'utf8');
    const runtimeEnv = {
      ...process.env,
      ADMIN_AUTH_ENABLED: 'true',
      APP_ENV: 'test',
      CRYPTO_REALTIME_ENABLED: 'false',
      DATABASE_PATH: path.join(runtimeDir, 't560-browser.sqlite'),
      ENV_FILE: envPath,
      LOG_DIR: path.join(runtimeDir, 'logs'),
      POSTGRES_PHASE_A_URL: '',
      WOLFYSTOCK_RELEASE_ADMIN_USERNAME: 'admin',
      WOLFYSTOCK_RELEASE_ADMIN_PASSWORD: adminPassword,
      WOLFYSTOCK_RELEASE_MEMBER_USERNAME: `t560_member_${randomBytes(6).toString('hex')}`,
      WOLFYSTOCK_RELEASE_MEMBER_PASSWORD: memberPassword,
      WOLFYSTOCK_UAT_NO_LIVE_PROVIDERS: 'true',
      WOLFYSTOCK_HISTORICAL_OHLCV_RUNTIME_ENABLED: 'false',
      WOLFYSTOCK_YFINANCE_US_OHLCV_CACHE_ENABLED: 'false',
    };
    execFileSync(python, [path.join(repoRoot, 'scripts/release_runtime_fixture.py')], {
      cwd: repoRoot,
      env: runtimeEnv,
      stdio: ['ignore', 'ignore', 'inherit'],
    });
    runtimeLogFd = openSync(path.join(runtimeDir, 'runtime.log'), 'a');
    runtime = spawn(
      python,
      [path.join(repoRoot, 'main.py'), '--serve-only', '--host', '127.0.0.1', '--port', String(port)],
      { cwd: repoRoot, env: runtimeEnv, stdio: ['ignore', runtimeLogFd, runtimeLogFd], windowsHide: true },
    );
    await waitForRuntime();
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
    if (taskBuiltStatic) rmSync(path.join(repoRoot, 'static'), { recursive: true, force: true });
  });

  test('contains focus at 390x844 and restores it across integrated desktop overlays', async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: 'dark' });
    await context.addInitScript(() => {
      window.localStorage.setItem('dsa-theme-style', 'paper');
      window.localStorage.setItem('dsa-theme-mode', 'dark');
    });
    const externalRequests: string[] = [];
    const page = await context.newPage();
    page.setDefaultTimeout(30_000);
    page.on('request', (request) => {
      if (new URL(request.url()).origin !== baseUrl) externalRequests.push(request.url());
    });
    try {
      await login(page, '/en/settings/system');
      await exerciseMobileShell(page);
      await exerciseWatchlistMenu(page);
      await exerciseOverlayStack(page);
      await expectNoHorizontalOverflow(page);
      await exerciseDesktopAccountAndSessionLoss(page);
      expect(externalRequests).toEqual([]);
    } finally {
      await context.close();
    }
  });
});
