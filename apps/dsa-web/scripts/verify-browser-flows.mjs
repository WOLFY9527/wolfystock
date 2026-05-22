import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium, webkit } from '@playwright/test';

const repoRoot = path.resolve(new URL('../../..', import.meta.url).pathname);
const reportDir = path.join(repoRoot, 'reports', 'ux-test-2026-04-26');
const screenshotsDir = path.join(reportDir, 'verification-screenshots');
const baseUrl = process.env.DSA_WEB_VERIFY_BASE_URL || 'http://127.0.0.1:4173';

const routes = [
  { path: '/', slug: 'home', expected: [/WolfyStock/, /Command Center|决策面板|Guest Preview Mode|游客预览模式/] },
  { path: '/login', slug: 'login', expected: [/WolfyStock/, /账户|account|Sign in|登录/] },
  { path: '/scanner', slug: 'scanner', expected: [/市场扫描|Market Scanner|我的候选|My candidates/] },
  { path: '/portfolio', slug: 'portfolio', expected: [/Trade Station|总资产|Total Assets|Current Holdings/] },
  { path: '/backtest', slug: 'backtest', expected: [/回测|Backtest|基础参数|Basic parameters/] },
  { path: '/__preview/report', slug: 'preview-report', expected: [/报告预览|Report Preview|回测报告|Backtest Report/] },
  { path: '/__preview/full-report', slug: 'preview-full-report', expected: [/报告抽屉|Full Report|报告预览|Report Preview/] },
  { path: '/guest', slug: 'guest', expected: [/Guest Preview Mode|游客预览模式/] },
];

const profiles = [
  {
    browserName: 'chromium',
    launcher: chromium,
    runs: [
      { name: 'desktop', viewport: { width: 1440, height: 900 } },
      { name: 'mobile', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
    ],
  },
  {
    browserName: 'webkit',
    launcher: webkit,
    runs: [
      { name: 'desktop', viewport: { width: 1440, height: 900 } },
      { name: 'mobile', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
    ],
  },
];

function toAbsoluteUrl(routePath) {
  return new URL(routePath, `${baseUrl}/`).toString();
}

function compactText(value) {
  return (value || '').replace(/\s+/g, ' ').trim();
}

async function ensureDirs() {
  await fs.mkdir(screenshotsDir, { recursive: true });
}

async function runRouteCheck(page, profile, route) {
  const url = toAbsoluteUrl(route.path);
  const errors = [];
  const consoleErrors = [];

  const onPageError = (error) => errors.push(String(error));
  const onConsole = (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  };

  page.on('pageerror', onPageError);
  page.on('console', onConsole);

  let status = 'pass';
  let bodyText = '';
  try {
    const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    await page.waitForTimeout(400);
    bodyText = compactText(await page.locator('body').innerText());
    const matched = route.expected.some((pattern) => pattern.test(bodyText));
    if (!response || !response.ok() || !matched || /页面未找到|Page not found/i.test(bodyText)) {
      status = 'fail';
    }
  } catch (error) {
    status = 'fail';
    errors.push(String(error));
  }

  const screenshotName = `${profile.browserName}-${profile.name}-${route.slug}.png`;
  const screenshotPath = path.join(screenshotsDir, screenshotName);
  await page.screenshot({ path: screenshotPath, fullPage: true });

  page.off('pageerror', onPageError);
  page.off('console', onConsole);

  return {
    browser: profile.browserName,
    viewport: profile.name,
    path: route.path,
    url,
    status,
    screenshot: path.relative(repoRoot, screenshotPath),
    consoleErrors,
    pageErrors: errors,
    bodySnippet: bodyText.slice(0, 240),
  };
}

async function runSpaReplay(page, browserName) {
  const steps = ['/', '/scanner', '/portfolio', '/__preview/report'];
  const errors = [];

  page.on('pageerror', (error) => errors.push(String(error)));

  for (const step of steps) {
    await page.goto(toAbsoluteUrl(step), { waitUntil: 'domcontentloaded', timeout: 30_000 });
    await page.waitForTimeout(250);
  }

  const bodyText = compactText(await page.locator('body').innerText());
  const blank = bodyText.length === 0;

  return {
    browser: browserName,
    pathSequence: steps,
    blankViewportDetected: blank,
    bodySnippet: bodyText.slice(0, 240),
    pageErrors: errors,
    status: blank ? 'fail' : 'pass',
  };
}

function buildMarkdown(results, spaChecks) {
  const lines = [
    '# Browser Verification Summary',
    '',
    `- Base URL: \`${baseUrl}\``,
    `- Generated at: \`${new Date().toISOString()}\``,
    '',
    '## Route Checks',
    '',
    '| Browser | Viewport | Route | Status | Screenshot | Notes |',
    '| --- | --- | --- | --- | --- | --- |',
  ];

  for (const result of results) {
    const notes = [
      result.consoleErrors[0],
      result.pageErrors[0],
      result.status === 'fail' ? result.bodySnippet : '',
    ].filter(Boolean).join(' | ');
    lines.push(`| ${result.browser} | ${result.viewport} | \`${result.path}\` | ${result.status.toUpperCase()} | \`${result.screenshot}\` | ${notes || '-'} |`);
  }

  lines.push('', '## SPA Replay', '', '| Browser | Status | Blank Viewport | Notes |', '| --- | --- | --- | --- |');
  for (const result of spaChecks) {
    const notes = [result.pageErrors[0], result.bodySnippet].filter(Boolean).join(' | ');
    lines.push(`| ${result.browser} | ${result.status.toUpperCase()} | ${result.blankViewportDetected ? 'YES' : 'NO'} | ${notes || '-'} |`);
  }

  return `${lines.join('\n')}\n`;
}

async function main() {
  await ensureDirs();

  const routeResults = [];
  const spaResults = [];

  for (const browserProfile of profiles) {
    for (const runProfile of browserProfile.runs) {
      const browser = await browserProfile.launcher.launch({ headless: true });
      const context = await browser.newContext({
        viewport: runProfile.viewport,
        isMobile: runProfile.isMobile || false,
        hasTouch: runProfile.hasTouch || false,
      });
      const page = await context.newPage();

      for (const route of routes) {
        routeResults.push(await runRouteCheck(page, { ...browserProfile, ...runProfile }, route));
      }

      if (runProfile.name === 'desktop') {
        spaResults.push(await runSpaReplay(page, browserProfile.browserName));
      }

      await context.close();
      await browser.close();
    }
  }

  const summary = {
    generatedAt: new Date().toISOString(),
    baseUrl,
    routeResults,
    spaResults,
  };

  await fs.writeFile(path.join(reportDir, 'browser-verification-summary.json'), JSON.stringify(summary, null, 2));
  await fs.writeFile(path.join(reportDir, 'browser-verification-summary.md'), buildMarkdown(routeResults, spaResults));
}

await main();
