import { expect, request as apiRequest, test, type Page, type Response } from '@playwright/test';
import { randomBytes } from 'node:crypto';
import { spawn, execFileSync, type ChildProcess } from 'node:child_process';
import { closeSync, mkdtempSync, openSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs';
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

function requiredEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required for release qualification`);
  return value;
}

let expectedCandidateSha = '';
let environmentFingerprint = '';
let runtimeCwd = '';
let assetFingerprint = '';

let runtime: ChildProcess | undefined;
let runtimeDir = '';
let runtimeLogFd: number | undefined;
let baseUrl = '';
let adminUsername = '';
let adminPassword = '';
let memberUsername = '';
let memberPassword = '';

async function reservePort(): Promise<number> {
  const server = net.createServer();
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const address = server.address();
  if (!address || typeof address === 'string') {
    server.close();
    throw new Error('Unable to reserve a release-browser port');
  }
  const port = address.port;
  await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  return port;
}

async function waitForRuntime(): Promise<void> {
  const deadline = Date.now() + 90_000;
  while (Date.now() < deadline) {
    if (runtime?.exitCode !== null) {
      throw new Error(`Release runtime exited before readiness (code ${runtime?.exitCode})`);
    }
    try {
      const response = await fetch(`${baseUrl}/api/health/live`);
      if (response.ok) return;
    } catch {
      // The task-owned local runtime is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error('Release runtime did not become live');
}

async function login(page: Page, username: string, password: string, redirect: string): Promise<void> {
  await page.goto(`${baseUrl}/zh/login?redirect=${encodeURIComponent(redirect)}`);
  await expect(page.locator('#username')).toBeVisible({ timeout: 30_000 });
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(password);
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(new RegExp(`${redirect.replaceAll('/', '\\/')}$`), { timeout: 30_000 });
}

async function logoutFromShell(page: Page): Promise<Response> {
  const accountEntry = page.locator('[data-testid="shell-account-center-entry"]:visible');
  await expect(accountEntry).toHaveCount(1);
  await accountEntry.getByRole('button', { name: '账户中心' }).click();
  const menu = page.locator('[data-testid="shell-account-center-menu"]:visible');
  await menu.getByRole('menuitem', { name: '退出登录' }).click();
  const dialog = page.getByRole('dialog', { name: '退出登录' });
  const responsePromise = page.waitForResponse(
    (response) => response.url().endsWith('/api/v1/auth/logout') && response.request().method() === 'POST',
  );
  await dialog.getByRole('button', { name: '确认退出' }).click();
  return responsePromise;
}

test.describe.serial('qualified release real runtime', () => {
  test.beforeAll(async () => {
    expectedCandidateSha = requiredEnv('WOLFYSTOCK_RELEASE_CANDIDATE_SHA');
    environmentFingerprint = requiredEnv('WOLFYSTOCK_ENV_FINGERPRINT');
    runtimeCwd = realpathSync(repoRoot);
    const webArtifact = JSON.parse(
      readFileSync(path.join(repoRoot, 'static/.wolfystock-web-build-artifact.json'), 'utf8'),
    ) as { fingerprint?: string };
    assetFingerprint = webArtifact.fingerprint ?? '';
    const observedSha = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: repoRoot, encoding: 'utf8' }).trim();
    expect(observedSha).toBe(expectedCandidateSha);
    expect(runtimeCwd).toBe(repoRoot);
    expect(environmentFingerprint).toMatch(/^[0-9a-f]{64}$/);
    expect(assetFingerprint).toMatch(/^[0-9a-f]{64}$/);
    runtimeDir = mkdtempSync(path.join(os.tmpdir(), 'wolfystock-release-browser-'));
    const port = await reservePort();
    baseUrl = `http://127.0.0.1:${port}`;
    const suffix = randomBytes(6).toString('hex');
    adminUsername = 'admin';
    memberUsername = `release_member_${suffix}`;
    adminPassword = randomBytes(24).toString('base64url');
    memberPassword = randomBytes(24).toString('base64url');
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
      DATABASE_PATH: path.join(runtimeDir, 'release-browser.sqlite'),
      ENV_FILE: envPath,
      LOG_DIR: path.join(runtimeDir, 'logs'),
      POSTGRES_PHASE_A_URL: '',
      WOLFYSTOCK_RELEASE_ADMIN_USERNAME: adminUsername,
      WOLFYSTOCK_RELEASE_ADMIN_PASSWORD: adminPassword,
      WOLFYSTOCK_RELEASE_MEMBER_USERNAME: memberUsername,
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
      {
        cwd: repoRoot,
        env: runtimeEnv,
        stdio: ['ignore', runtimeLogFd, runtimeLogFd],
        windowsHide: true,
      },
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
  });

  test('production startup readiness and static assets', async ({ page }) => {
    const live = await page.request.get(`${baseUrl}/api/health/live`);
    const readiness = await page.request.get(`${baseUrl}/api/health/ready`);
    const root = await page.request.get(`${baseUrl}/`);
    expect(live.status()).toBe(200);
    expect(readiness.status()).toBe(200);
    expect(root.status()).toBe(200);
    expect(runtime?.spawnargs).toContain(path.join(repoRoot, 'main.py'));
    expect(runtime?.spawnargs).toContain('--serve-only');
    const html = await root.text();
    const assetPath = html.match(/(?:src|href)="(\/assets\/[^"]+)"/)?.[1];
    expect(assetPath).toBeTruthy();
    const asset = await page.request.get(`${baseUrl}${assetPath}`);
    expect(asset.status()).toBe(200);
    expect((await asset.body()).byteLength).toBeGreaterThan(0);
  });

  test('login logout and revoked session', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    try {
      await login(page, adminUsername, adminPassword, '/zh/admin/logs');
      const session = (await context.cookies(baseUrl)).find((cookie) => cookie.name === 'dsa_session');
      expect(session).toBeTruthy();
      const logout = await logoutFromShell(page);
      expect(logout.status()).toBe(204);
      await expect(page).toHaveURL(/\/zh\/guest$/, { timeout: 30_000 });
      const replay = await apiRequest.newContext({
        baseURL: baseUrl,
        extraHTTPHeaders: { Cookie: `dsa_session=${session!.value}` },
      });
      try {
        expect((await replay.get('/api/v1/admin/users')).status()).toBe(401);
      } finally {
        await replay.dispose();
      }
    } finally {
      await context.close();
    }
  });

  test('member admin boundary and portfolio read', async ({ browser }) => {
    const memberContext = await browser.newContext();
    const memberPage = await memberContext.newPage();
    const adminContext = await browser.newContext();
    const adminPage = await adminContext.newPage();
    try {
      await login(memberPage, memberUsername, memberPassword, '/zh/portfolio');
      expect((await memberPage.request.get(`${baseUrl}/api/v1/admin/users`)).status()).toBe(403);
      const portfolio = await memberPage.request.get(`${baseUrl}/api/v1/portfolio/accounts`);
      expect(portfolio.status()).toBe(200);
      expect((await portfolio.json()).accounts).toEqual([]);

      await login(adminPage, adminUsername, adminPassword, '/zh/admin/logs');
      expect((await adminPage.request.get(`${baseUrl}/api/v1/admin/users`)).status()).toBe(200);
      const ops = await adminPage.request.get(`${baseUrl}/api/v1/admin/ops/status`);
      expect(ops.status()).toBe(200);
      expect((await ops.json()).buildProvenance.backendGitSha).toBe(expectedCandidateSha);
    } finally {
      await memberContext.close();
      await adminContext.close();
    }
  });

  test('rollback error preserves portfolio state and exposes unavailable data', async ({ page }) => {
    await login(page, memberUsername, memberPassword, '/zh/portfolio');
    const before = await page.evaluate(async () => (await fetch('/api/v1/portfolio/accounts')).json());
    const rejected = await page.evaluate(async () => {
      const response = await fetch('/api/v1/portfolio/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'Rejected release account',
          market: 'us',
          base_currency: 'USD',
          owner_id: 'different-owner',
        }),
      });
      return { status: response.status, body: await response.json() };
    });
    const after = await page.evaluate(async () => (await fetch('/api/v1/portfolio/accounts')).json());
    expect(rejected.status).toBe(400);
    expect(JSON.stringify(rejected.body)).not.toMatch(/traceback|token|password|private key/i);
    expect(after).toEqual(before);

    const capabilityResponse = await page.request.get(`${baseUrl}/api/v1/market/professional-data-capabilities`);
    expect(capabilityResponse.status()).toBe(200);
    expect(JSON.stringify(await capabilityResponse.json())).toMatch(/unavailable|stale/i);
  });
});
