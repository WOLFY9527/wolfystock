import { expect, test, type Browser, type Locator, type Page } from '@playwright/test';
import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { closeSync, existsSync, mkdtempSync, openSync, rmSync, writeFileSync } from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

type Rgba = { r: number; g: number; b: number; a: number };
type TextKind = 'ordinary-text' | 'large-text';
type ContrastEvidence = {
  owner: string;
  route: string;
  kind: TextKind | 'non-text-boundary';
  theme: 'light' | 'dark';
  viewport: string;
  computedForeground?: string;
  renderedForeground: string;
  computedBackground?: string;
  renderedBackground: string;
  opacity?: number;
  fontSize?: string;
  fontWeight?: string;
  backgroundLayers: Array<{ element: string; color: string; image: string; opacity: string }>;
  ratio: number;
  requiredRatio: number;
};

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
let memberUsername = '';
let memberPassword = '';
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
    throw new Error('Unable to reserve a T559 browser port');
  }
  await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  return address.port;
}

async function waitForRuntime(): Promise<void> {
  const deadline = Date.now() + 90_000;
  while (Date.now() < deadline) {
    if (runtime?.exitCode !== null) {
      throw new Error(`T559 runtime exited before readiness (code ${runtime?.exitCode})`);
    }
    try {
      const response = await fetch(`${baseUrl}/api/health/live`);
      if (response.ok) return;
    } catch {
      // The task-owned disposable runtime is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error('T559 runtime did not become live');
}

async function login(page: Page, redirect: string): Promise<void> {
  await page.goto(`${baseUrl}/zh/login?redirect=${encodeURIComponent(redirect)}`);
  await expect(page.locator('#username')).toBeVisible({ timeout: 30_000 });
  await page.locator('#username').fill(memberUsername);
  await page.locator('#password').fill(memberPassword);
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(new RegExp(`${redirect.replaceAll('/', '\\/')}$`), { timeout: 30_000 });
}

function channelToSrgb(value: number): number {
  const normalized = value / 255;
  return normalized <= 0.04045
    ? normalized / 12.92
    : ((normalized + 0.055) / 1.055) ** 2.4;
}

function luminance(color: Rgba): number {
  return 0.2126 * channelToSrgb(color.r)
    + 0.7152 * channelToSrgb(color.g)
    + 0.0722 * channelToSrgb(color.b);
}

function contrastRatio(first: Rgba, second: Rgba): number {
  const lighter = Math.max(luminance(first), luminance(second));
  const darker = Math.min(luminance(first), luminance(second));
  return (lighter + 0.05) / (darker + 0.05);
}

function composite(foreground: Rgba, background: Rgba): Rgba {
  const alpha = foreground.a + background.a * (1 - foreground.a);
  if (alpha === 0) return { r: 0, g: 0, b: 0, a: 0 };
  return {
    r: Math.round((foreground.r * foreground.a + background.r * background.a * (1 - foreground.a)) / alpha),
    g: Math.round((foreground.g * foreground.a + background.g * background.a * (1 - foreground.a)) / alpha),
    b: Math.round((foreground.b * foreground.a + background.b * background.a * (1 - foreground.a)) / alpha),
    a: alpha,
  };
}

function formatColor(color: Rgba): string {
  return color.a === 1
    ? `rgb(${color.r} ${color.g} ${color.b})`
    : `rgb(${color.r} ${color.g} ${color.b} / ${color.a.toFixed(3)})`;
}

async function parseCssColor(page: Page, color: string): Promise<Rgba> {
  return page.evaluate((cssColor) => {
    const canvas = document.createElement('canvas');
    canvas.width = 1;
    canvas.height = 1;
    const context = canvas.getContext('2d', { willReadFrequently: true });
    if (!context) throw new Error('Unable to create a color parsing canvas');
    context.clearRect(0, 0, 1, 1);
    context.fillStyle = cssColor;
    context.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = context.getImageData(0, 0, 1, 1).data;
    return { r, g, b, a: a / 255 };
  }, color);
}

async function readPngPixel(page: Page, buffer: Buffer, xFraction: number, yFraction: number): Promise<Rgba> {
  const base64 = buffer.toString('base64');
  return page.evaluate(async ({ png, x, y }) => {
    const image = new Image();
    image.src = `data:image/png;base64,${png}`;
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    const context = canvas.getContext('2d', { willReadFrequently: true });
    if (!context) throw new Error('Unable to create a PNG sampling canvas');
    context.drawImage(image, 0, 0);
    const pixelX = Math.min(image.naturalWidth - 1, Math.max(0, Math.floor(image.naturalWidth * x)));
    const pixelY = Math.min(image.naturalHeight - 1, Math.max(0, Math.floor(image.naturalHeight * y)));
    const [r, g, b, a] = context.getImageData(pixelX, pixelY, 1, 1).data;
    return { r, g, b, a: a / 255 };
  }, { png: base64, x: xFraction, y: yFraction });
}

async function inspectElement(locator: Locator) {
  await expect(locator).toHaveCount(1);
  await expect(locator).toBeVisible();
  await expect.poll(
    () => locator.evaluate((element) => {
      let opacity = 1;
      for (let current: HTMLElement | null = element as HTMLElement; current; current = current.parentElement) {
        opacity *= Number.parseFloat(getComputedStyle(current).opacity);
      }
      return opacity;
    }),
    { message: 'Contrast target must reach stable rendered opacity', timeout: 30_000 },
  ).toBeGreaterThanOrEqual(0.999);
  return locator.evaluate((element) => {
    const node = element as HTMLElement;
    const rect = node.getBoundingClientRect();
    if (!node.isConnected || rect.width <= 0 || rect.height <= 0) {
      throw new Error('Contrast target is detached or has no rendered box');
    }
    const style = getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden') {
      throw new Error('Contrast target is hidden');
    }
    let opacity = 1;
    const backgroundLayers: Array<{ element: string; color: string; image: string; opacity: string }> = [];
    for (let current: HTMLElement | null = node; current; current = current.parentElement) {
      const currentStyle = getComputedStyle(current);
      opacity *= Number.parseFloat(currentStyle.opacity);
      if (currentStyle.backgroundColor !== 'rgba(0, 0, 0, 0)' || currentStyle.backgroundImage !== 'none') {
        backgroundLayers.push({
          element: current.dataset.testid || current.tagName.toLowerCase(),
          color: currentStyle.backgroundColor,
          image: currentStyle.backgroundImage,
          opacity: currentStyle.opacity,
        });
      }
    }
    return {
      color: style.color,
      backgroundColor: style.backgroundColor,
      fontSize: style.fontSize,
      fontWeight: style.fontWeight,
      opacity,
      backgroundLayers,
      theme: document.documentElement.dataset.theme,
      themeStyle: document.documentElement.dataset.themeStyle,
    };
  });
}

async function sampleTextBackground(page: Page, locator: Locator): Promise<Rgba> {
  const originalStyle = await locator.evaluate((element) => {
    const node = element as HTMLElement;
    const value = node.getAttribute('style');
    node.style.setProperty('color', 'transparent', 'important');
    node.style.setProperty('text-shadow', 'none', 'important');
    return value;
  });
  try {
    const screenshot = await locator.screenshot({ animations: 'disabled' });
    const background = await readPngPixel(page, screenshot, 0.5, 0.5);
    if (background.a !== 1) {
      throw new Error(`Unresolved transparent background: ${formatColor(background)}`);
    }
    return background;
  } finally {
    await locator.evaluate((element, style) => {
      if (style === null) element.removeAttribute('style');
      else element.setAttribute('style', style);
    }, originalStyle);
  }
}

async function measureText(
  page: Page,
  locator: Locator,
  owner: string,
  viewport: string,
): Promise<ContrastEvidence> {
  const inspected = await inspectElement(locator);
  expect(inspected.themeStyle).toBe('paper');
  expect(inspected.theme === 'light' || inspected.theme === 'dark').toBe(true);
  const background = await sampleTextBackground(page, locator);
  const computedForeground = await parseCssColor(page, inspected.color);
  const foregroundWithOpacity = { ...computedForeground, a: computedForeground.a * inspected.opacity };
  const renderedForeground = composite(foregroundWithOpacity, background);
  const fontSize = Number.parseFloat(inspected.fontSize);
  const fontWeight = Number.parseInt(inspected.fontWeight, 10);
  const kind: TextKind = fontSize >= 24 || (fontSize >= 18.66 && fontWeight >= 700)
    ? 'large-text'
    : 'ordinary-text';
  const requiredRatio = kind === 'large-text' ? 3 : 4.5;
  return {
    owner,
    route: new URL(page.url()).pathname,
    kind,
    theme: inspected.theme as 'light' | 'dark',
    viewport,
    computedForeground: inspected.color,
    renderedForeground: formatColor(renderedForeground),
    computedBackground: inspected.backgroundColor,
    renderedBackground: formatColor(background),
    opacity: inspected.opacity,
    fontSize: inspected.fontSize,
    fontWeight: inspected.fontWeight,
    backgroundLayers: inspected.backgroundLayers,
    ratio: Number(contrastRatio(renderedForeground, background).toFixed(3)),
    requiredRatio,
  };
}

async function measureFilledBoundary(
  page: Page,
  locator: Locator,
  owner: string,
  viewport: string,
): Promise<ContrastEvidence> {
  const inspected = await inspectElement(locator);
  const box = await locator.boundingBox();
  if (!box) throw new Error('Non-text boundary target has no rendered box');
  const filled = await locator.screenshot({ animations: 'disabled' });
  const fill = await readPngPixel(page, filled, 0.5, Math.min(0.24, 6 / box.height));
  const originalStyle = await locator.evaluate((element) => {
    const value = element.getAttribute('style');
    (element as HTMLElement).style.setProperty('visibility', 'hidden', 'important');
    return value;
  });
  let adjacent: Rgba;
  try {
    const surrounding = await page.screenshot({
      animations: 'disabled',
      clip: { x: box.x, y: box.y, width: box.width, height: box.height },
    });
    adjacent = await readPngPixel(page, surrounding, 0.5, 0.5);
  } finally {
    await locator.evaluate((element, style) => {
      if (style === null) element.removeAttribute('style');
      else element.setAttribute('style', style);
    }, originalStyle);
  }
  if (fill.a !== 1 || adjacent.a !== 1) {
    throw new Error(`Unresolved transparent non-text boundary: ${formatColor(fill)} / ${formatColor(adjacent)}`);
  }
  return {
    owner,
    route: new URL(page.url()).pathname,
    kind: 'non-text-boundary',
    theme: inspected.theme as 'light' | 'dark',
    viewport,
    renderedForeground: formatColor(fill),
    computedBackground: inspected.backgroundColor,
    renderedBackground: formatColor(adjacent),
    backgroundLayers: inspected.backgroundLayers,
    ratio: Number(contrastRatio(fill, adjacent).toFixed(3)),
    requiredRatio: 3,
  };
}

async function measureRouteSurfaces(page: Page, viewport: string): Promise<ContrastEvidence[]> {
  const evidence: ContrastEvidence[] = [];
  await page.goto(`${baseUrl}/zh/guest`);
  const guest = page.getByTestId('guest-home-command-surface');
  await expect(guest).toBeVisible({ timeout: 30_000 });
  evidence.push(await measureText(page, guest.locator('p').first(), 'guest/home muted eyebrow', viewport));
  evidence.push(await measureText(page, guest.getByRole('heading', { level: 1 }), 'guest/home heading', viewport));
  evidence.push(await measureText(page, guest.locator('p').nth(1), 'guest/home secondary subtitle', viewport));
  evidence.push(await measureFilledBoundary(
    page,
    page.getByTestId('home-bento-analyze-button'),
    'guest/home primary action fill boundary',
    viewport,
  ));

  await login(page, '/zh/watchlist');
  const watchlistEmpty = page.getByTestId('watchlist-compact-empty-state');
  await expect(watchlistEmpty).toBeVisible({ timeout: 30_000 });
  evidence.push(await measureText(page, watchlistEmpty.locator('p').nth(1), 'Watchlist empty muted body', viewport));
  evidence.push(await measureText(
    page,
    page.getByTestId('watchlist-empty-onboarding-cta').locator('[data-terminal-primitive="chip"]'),
    'Watchlist empty info chip',
    viewport,
  ));

  await page.goto(`${baseUrl}/zh/scanner`);
  const scannerStatus = page.getByTestId('scanner-status-strip');
  await expect(scannerStatus).toBeVisible({ timeout: 30_000 });
  evidence.push(await measureText(
    page,
    scannerStatus.locator(':scope > div').first().locator('span').first(),
    'Scanner status muted label',
    viewport,
  ));

  await page.goto(`${baseUrl}/zh/portfolio`);
  await expect(page.getByTestId('portfolio-start-card')).toBeVisible({ timeout: 30_000 });
  evidence.push(await measureText(
    page,
    page.getByTestId('portfolio-empty-workflow-column').getByTestId('portfolio-empty-help'),
    'Portfolio readiness muted help',
    viewport,
  ));

  await page.goto(`${baseUrl}/zh/settings`);
  const settingsRow = page.getByTestId('personal-settings-account-row');
  await expect(settingsRow).toBeVisible({ timeout: 30_000 });
  evidence.push(await measureText(page, settingsRow.locator('p').nth(1), 'Settings account muted detail', viewport));
  evidence.push(await measureText(
    page,
    settingsRow.locator('[data-terminal-primitive="chip"]').first(),
    'Settings signed-in info chip',
    viewport,
  ));

  await page.goto(`${baseUrl}/zh/market/liquidity-monitor`);
  const liquidityOverview = page.getByTestId('liquidity-section-overview');
  await expect(liquidityOverview).toBeVisible({ timeout: 30_000 });
  evidence.push(await measureText(
    page,
    liquidityOverview.locator('[data-terminal-primitive="chip"]').first(),
    'Liquidity availability label',
    viewport,
  ));

  await page.goto(`${baseUrl}/zh/settings/system`);
  const accessPill = page.getByTestId('access-gate-status-pill');
  await expect(accessPill).toBeVisible({ timeout: 30_000 });
  evidence.push(await measureText(page, accessPill.locator('span').nth(1), 'Admin access warning label', viewport));
  return evidence;
}

async function runContrastCase(
  browser: Browser,
  theme: 'light' | 'dark',
  viewport: { width: number; height: number },
): Promise<void> {
  const context = await browser.newContext({ viewport, colorScheme: theme });
  await context.addInitScript((selectedTheme) => {
    window.localStorage.setItem('dsa-theme-style', 'paper');
    window.localStorage.setItem('dsa-theme-mode', selectedTheme);
  }, theme);
  const page = await context.newPage();
  const viewportLabel = `${viewport.width}x${viewport.height}`;
  try {
    const evidence = await measureRouteSurfaces(page, viewportLabel);
    for (const item of evidence) {
      console.log(`T559_CONTRAST ${JSON.stringify(item)}`);
    }
    await test.info().attach('t559-contrast-evidence', {
      body: Buffer.from(JSON.stringify(evidence, null, 2)),
      contentType: 'application/json',
    });
    for (const item of evidence) {
      expect.soft(
        item.ratio,
        `${item.owner}: ${item.renderedForeground} on ${item.renderedBackground}`,
      ).toBeGreaterThanOrEqual(item.requiredRatio);
    }
  } finally {
    await context.close();
  }
}

test.describe('T559 consumer label contrast', () => {
  test.describe.configure({ mode: 'default', retries: 0, timeout: 180_000 });

  test.beforeAll(async () => {
    test.setTimeout(180_000);
    const staticRoot = path.join(repoRoot, 'static');
    if (existsSync(staticRoot)) {
      throw new Error('T559 requires an absent canonical static directory before its task-owned build');
    }
    execFileSync('npm', ['exec', '--', 'vite', 'build', '--outDir', '../../static', '--emptyOutDir'], {
      cwd: path.join(repoRoot, 'apps/dsa-web'),
      stdio: ['ignore', 'ignore', 'inherit'],
    });
    taskBuiltStatic = true;
    runtimeDir = mkdtempSync(path.join(os.tmpdir(), 'wolfystock-t559-browser-'));
    const port = await reservePort();
    baseUrl = `http://127.0.0.1:${port}`;
    const suffix = randomBytes(6).toString('hex');
    const adminPassword = randomBytes(24).toString('base64url');
    memberUsername = `t559_member_${suffix}`;
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
      DATABASE_PATH: path.join(runtimeDir, 't559-browser.sqlite'),
      ENV_FILE: envPath,
      LOG_DIR: path.join(runtimeDir, 'logs'),
      POSTGRES_PHASE_A_URL: '',
      WOLFYSTOCK_RELEASE_ADMIN_USERNAME: 'admin',
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

  for (const viewport of [{ width: 390, height: 844 }, { width: 1440, height: 1000 }]) {
    for (const theme of ['light', 'dark'] as const) {
      test(`${theme} ${viewport.width}x${viewport.height}`, async ({ browser }) => {
        await runContrastCase(browser, theme, viewport);
      });
    }
  }
});
