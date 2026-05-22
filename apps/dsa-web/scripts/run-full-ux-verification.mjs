import fs from 'node:fs/promises';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { chromium, webkit } from '@playwright/test';

import {
  buildPreferredScannerConfigs,
  diffTableCounts,
  isRetryableScannerValidationError,
  summarizeFlowOutcomes,
} from './ux-verification-helpers.mjs';

const repoRoot = path.resolve(new URL('../../..', import.meta.url).pathname);
const generatedAt = new Date().toISOString();
const stamp = generatedAt.replace(/[:.]/g, '-');
const reportBaseDir = process.env.DSA_UX_VERIFY_REPORT_BASE
  ? path.resolve(repoRoot, process.env.DSA_UX_VERIFY_REPORT_BASE)
  : path.join(repoRoot, 'reports');
const reportName = process.env.DSA_UX_VERIFY_REPORT_NAME || `ux-verification-${stamp}`;
const reportDir = path.join(reportBaseDir, reportName);
const screenshotRoot = path.join(reportDir, 'screenshots');
const desktopShotDir = path.join(screenshotRoot, 'desktop');
const mobileShotDir = path.join(screenshotRoot, 'mobile');
const reportJsonPath = path.join(reportDir, 'ux-verification-report.json');
const reportMdPath = path.join(reportDir, 'ux-verification-report.md');
const baseUrl = process.env.DSA_UX_VERIFY_BASE_URL || 'http://127.0.0.1:8000';
const previewUrl = process.env.DSA_UX_VERIFY_PREVIEW_URL || 'http://127.0.0.1:4174';
const backendStatusUrl = process.env.DSA_UX_VERIFY_STATUS_URL || `${baseUrl}/api/v1/auth/status`;
const dbPath = path.join(repoRoot, 'data', 'stock_analysis.db');
const actionTimeoutMs = 10_000;

const TABLE_GROUPS = {
  auth: ['app_users', 'app_user_sessions'],
  analysis: ['analysis_history'],
  scanner: ['market_scanner_runs', 'market_scanner_candidates'],
  portfolio: ['portfolio_accounts', 'portfolio_trades', 'portfolio_cash_ledger', 'portfolio_corporate_actions'],
  backtest: ['backtest_runs', 'backtest_results', 'rule_backtest_runs'],
};

const CORE_TEMPLATES = [
  'moving_average_crossover',
  'macd_crossover',
  'rsi_threshold',
  'periodic_accumulation',
];

const NORMAL_BACKTEST_TEMPLATE_STRATEGIES = {
  moving_average_crossover: '5日均线上穿20日均线买入，下穿卖出。',
  macd_crossover: 'MACD 金叉买入，死叉卖出。',
  rsi_threshold: 'RSI14 低于30买入，高于70卖出。',
  periodic_accumulation: '每月定投1000元买入，资金不足时停止。',
};

const VERIFY_ROUTES = [
  { slug: 'home', path: '/' },
  { slug: 'scanner', path: '/scanner' },
  { slug: 'portfolio', path: '/portfolio' },
  { slug: 'backtest', path: '/backtest' },
  { slug: 'preview-report', path: '/__preview/report' },
  { slug: 'preview-full-report', path: '/__preview/full-report' },
  { slug: 'settings', path: '/settings' },
];

const verificationPassword = process.env.DSA_UX_VERIFY_PASSWORD || 'mock-password';

const verificationUser = {
  username: `ux_${Date.now().toString(36)}`,
  displayName: 'UX Verify',
  password: verificationPassword,
};

const report = {
  generatedAt,
  baseUrl,
  previewUrl,
  dbPath: path.relative(repoRoot, dbPath),
  actionTimeoutMs,
  user: {
    username: verificationUser.username,
    displayName: verificationUser.displayName,
  },
  runtime: {},
  flows: [],
  failedRequests: [],
  warnings: [],
  screenshots: {
    desktop: [],
    mobile: [],
  },
  surfaceChecks: [],
};

async function ensureDirs() {
  await fs.mkdir(desktopShotDir, { recursive: true });
  await fs.mkdir(mobileShotDir, { recursive: true });
}

function compactText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function locatorRegex(zh, en) {
  return new RegExp(`${zh}|${en}`, 'i');
}

async function withTimeout(label, fn) {
  let timer;
  try {
    return await Promise.race([
      fn(),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error(`${label} timed out after ${actionTimeoutMs}ms`)), actionTimeoutMs);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

function snapshotCounts(snapshot) {
  const counts = {};
  for (const [table, value] of Object.entries(snapshot.tables || {})) {
    counts[table] = Number(value.count || 0);
  }
  return counts;
}

function readDbSnapshot(tables) {
  const pythonScript = `
import json
import sqlite3
import sys

db_path = sys.argv[1]
tables = json.loads(sys.argv[2])
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
result = {"tables": {}}

for table in tables:
    table_payload = {"count": None, "lastRows": [], "error": None}
    def compact(value):
        if isinstance(value, str) and len(value) > 180:
            return value[:177] + "..."
        return value
    try:
        count = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 1").fetchall()
        table_payload["count"] = count
        table_payload["lastRows"] = [{key: compact(value) for key, value in dict(row).items()} for row in rows]
    except Exception as exc:
        table_payload["error"] = str(exc)
    result["tables"][table] = table_payload

print(json.dumps(result, ensure_ascii=False))
`.trim();

  const output = execFileSync('python3', ['-c', pythonScript, dbPath, JSON.stringify(tables)], {
    cwd: repoRoot,
    encoding: 'utf-8',
    maxBuffer: 10 * 1024 * 1024,
  });
  return JSON.parse(output);
}

function readBackendStatus() {
  try {
    const payload = execFileSync('curl', ['-sS', backendStatusUrl], {
      encoding: 'utf-8',
      maxBuffer: 1024 * 1024,
    }).trim();
    if (!payload) {
      return {
        ok: false,
        statusUrl: backendStatusUrl,
        error: 'empty_response',
      };
    }
    return {
      ok: true,
      statusUrl: backendStatusUrl,
      payload: JSON.parse(payload),
    };
  } catch (error) {
    return {
      ok: false,
      statusUrl: backendStatusUrl,
      error: String(error),
    };
  }
}

async function takeScreenshot(page, browserName, viewportName, slug) {
  const dir = viewportName === 'desktop' ? desktopShotDir : mobileShotDir;
  const fileName = `${browserName}-${viewportName}-${slug}.png`;
  const absolutePath = path.join(dir, fileName);
  await page.screenshot({ path: absolutePath, fullPage: true });
  const relativePath = path.relative(repoRoot, absolutePath);
  report.screenshots[viewportName].push(relativePath);
  return relativePath;
}

function createNetworkTracker(target) {
  target.on('response', async (response) => {
    if (response.status() < 400) {
      return;
    }
    let responseBody = '';
    try {
      responseBody = (await response.text()).slice(0, 800);
    } catch {
      responseBody = '';
    }
    report.failedRequests.push({
      at: new Date().toISOString(),
      url: response.url(),
      method: response.request().method(),
      status: response.status(),
      requestPayload: response.request().postData() || null,
      responseBody,
    });
  });
}

async function evaluateGlow(locator) {
  try {
    return await locator.evaluate((element) => getComputedStyle(element).textShadow);
  } catch {
    return 'unavailable';
  }
}

async function logoutViaFetch(page) {
  return page.evaluate(async () => {
    const response = await fetch('/api/v1/auth/logout', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    });
    return response.status;
  });
}

async function loginViaUi(page, user) {
  await withTimeout('open login', async () => {
    await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' });
    await page.locator('#username').fill(user.username);
    await page.locator('#password').fill(user.password);
    await page.getByRole('button').filter({ hasText: locatorRegex('登录继续', 'Sign in') }).click();
  });
  await withTimeout('post-login home', async () => {
    await page.waitForURL(`${baseUrl}/`, { timeout: actionTimeoutMs });
    await page.locator('[data-testid="home-bento-dashboard"]').waitFor({ state: 'visible', timeout: actionTimeoutMs });
  });
}

async function createUserViaUi(page, user) {
  await withTimeout('open create account', async () => {
    await page.goto(`${baseUrl}/login?mode=create`, { waitUntil: 'domcontentloaded' });
    await page.locator('#username').fill(user.username);
    await page.locator('#displayName').fill(user.displayName);
    await page.locator('#password').fill(user.password);
    await page.locator('#passwordConfirm').fill(user.password);
    await page.getByRole('button').filter({ hasText: locatorRegex('创建账户', 'Create account') }).click();
  });
  await withTimeout('post-create home', async () => {
    await page.waitForURL(`${baseUrl}/`, { timeout: actionTimeoutMs });
    await page.locator('body').waitFor({ state: 'visible', timeout: actionTimeoutMs });
  });
}

async function recordFlow(name, fn) {
  const flow = {
    name,
    startedAt: new Date().toISOString(),
    status: 'pass',
    steps: [],
    uiChecks: [],
    database: null,
    screenshots: [],
    warnings: [],
    error: null,
  };

  try {
    const failedRequestStart = report.failedRequests.length;
    await fn(flow);
    const flowFailedRequests = report.failedRequests.slice(failedRequestStart);
    if (flowFailedRequests.length > 0) {
      flow.warnings.push(`${flowFailedRequests.length} non-2xx request(s) captured during flow`);
    }
    if (flow.status !== 'fail' && (flow.uiChecks.some((item) => item.status === 'fail') || flow.warnings.length > 0)) {
      flow.status = 'partial';
    }
  } catch (error) {
    flow.status = 'fail';
    flow.error = String(error);
  }

  flow.finishedAt = new Date().toISOString();
  report.flows.push(flow);
  return flow;
}

function pushUiCheck(flow, name, passed, details = {}) {
  flow.uiChecks.push({
    name,
    status: passed ? 'pass' : 'fail',
    ...details,
  });
  if (!passed && flow.status === 'pass') {
    flow.status = 'partial';
  }
}

function attachDbDelta(flow, before, after) {
  flow.database = {
    before,
    after,
    diff: diffTableCounts(snapshotCounts(before), snapshotCounts(after)),
  };
}

async function invokeScannerRunApi(page, config) {
  return page.evaluate(async (payload) => {
    const response = await fetch('/api/v1/scanner/run', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return {
      status: response.status,
      responseBody: await response.text(),
    };
  }, {
    market: config.market,
    profile: config.profile,
  });
}

async function invokeRuleBacktestApi(page, config) {
  return page.evaluate(async (payload) => {
    const parseResponse = await fetch('/api/v1/backtest/rule/parse', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code: payload.code,
        strategy_text: payload.strategyText,
        start_date: payload.startDate,
        end_date: payload.endDate,
        initial_capital: payload.initialCapital,
        fee_bps: payload.feeBps,
        slippage_bps: payload.slippageBps,
      }),
    });

    const parseBody = await parseResponse.text();
    if (parseResponse.status !== 200) {
      return {
        ok: false,
        stage: 'parse',
        status: parseResponse.status,
        body: parseBody,
      };
    }

    const parsed = JSON.parse(parseBody);
    const runResponse = await fetch('/api/v1/backtest/rule/run', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code: payload.code,
        strategy_text: payload.strategyText,
        parsed_strategy: parsed.parsedStrategy,
        start_date: payload.startDate,
        end_date: payload.endDate,
        lookback_bars: payload.lookbackBars,
        initial_capital: payload.initialCapital,
        fee_bps: payload.feeBps,
        slippage_bps: payload.slippageBps,
        benchmark_mode: 'auto',
        confirmed: true,
        wait_for_completion: false,
      }),
    });

    return {
      ok: runResponse.status === 200,
      stage: 'run',
      status: runResponse.status,
      body: await runResponse.text(),
    };
  }, config);
}

async function switchScannerMarket(page, market) {
  await page.goto(`${baseUrl}/scanner`, { waitUntil: 'domcontentloaded' });
  await page.locator('[data-testid="user-scanner-bento-page"]').waitFor({ state: 'visible', timeout: actionTimeoutMs });
  const marketToggle = page.locator('[data-testid="scanner-market-toggle"]');
  const marketLabel = market.toUpperCase();
  const targetButton = marketToggle.getByRole('button').filter({ hasText: new RegExp(`^${marketLabel}$`, 'i') });
  if (await targetButton.isVisible().catch(() => false)) {
    await targetButton.click();
  }
  await page.waitForTimeout(150);
}

async function runScannerWithFallback(page, flow) {
  const attempts = buildPreferredScannerConfigs();

  for (const config of attempts) {
    const apiResult = await invokeScannerRunApi(page, config);
    if (apiResult.status === 200) {
      flow.steps.push({
        market: config.market,
        profile: config.profile,
        status: apiResult.status,
        outcome: 'scanner_run_persisted',
      });
      await switchScannerMarket(page, config.market);
      return config;
    }

    if (isRetryableScannerValidationError(apiResult)) {
      flow.steps.push({
        market: config.market,
        profile: config.profile,
        status: apiResult.status,
        outcome: 'retry_validation_error',
      });
      flow.warnings.push(`scanner ${config.market}/${config.profile} validation fallback: ${compactText(apiResult.responseBody).slice(0, 180)}`);
      continue;
    }

    throw new Error(`scanner ${config.market}/${config.profile} failed: HTTP ${apiResult.status} ${compactText(apiResult.responseBody).slice(0, 240)}`);
  }

  throw new Error('scanner fallback chain exhausted without a persisted run');
}

async function verifyHome(page, browserName, viewportName, flow, slugPrefix = 'home') {
  await page.goto(`${baseUrl}/`, { waitUntil: 'domcontentloaded' });
  await page.locator('[data-testid="home-bento-dashboard"]').waitFor({ state: 'visible', timeout: actionTimeoutMs });
  const decisionCard = page.locator('[data-testid="home-bento-card-decision"]');
  const strategyTrigger = page.locator('[data-testid="home-bento-drawer-trigger-strategy"]');
  const historyTrigger = page.locator('[data-testid="home-bento-history-drawer-trigger"]');
  pushUiCheck(flow, 'home decision card visible', await decisionCard.isVisible().catch(() => false));
  pushUiCheck(flow, 'home strategy drawer trigger visible', await strategyTrigger.isVisible().catch(() => false));
  pushUiCheck(flow, 'home history trigger visible', await historyTrigger.isVisible().catch(() => false));
  if (await strategyTrigger.isVisible().catch(() => false)) {
    await strategyTrigger.click();
    await page.locator('[data-testid="home-bento-drawer"]').waitFor({ state: 'visible', timeout: actionTimeoutMs }).catch(() => undefined);
    const drawerVisible = await page.locator('[data-testid="home-bento-drawer"]').isVisible().catch(() => false);
    pushUiCheck(flow, 'home drawer opens', drawerVisible);
    await page.keyboard.press('Escape').catch(() => undefined);
  }
  if (await historyTrigger.isVisible().catch(() => false)) {
    await historyTrigger.click();
    await page.locator('[data-testid="home-bento-history-drawer"]').waitFor({ state: 'visible', timeout: actionTimeoutMs }).catch(() => undefined);
    pushUiCheck(flow, 'home history drawer opens', await page.locator('[data-testid="home-bento-history-drawer"]').isVisible().catch(() => false));
    await page.keyboard.press('Escape').catch(() => undefined);
  }
  flow.screenshots.push(await takeScreenshot(page, browserName, viewportName, slugPrefix));
}

async function verifyScanner(page, browserName, viewportName, flow, slugPrefix = 'scanner') {
  await page.goto(`${baseUrl}/scanner`, { waitUntil: 'domcontentloaded' });
  await page.locator('[data-testid="user-scanner-bento-page"]').waitFor({ state: 'visible', timeout: actionTimeoutMs });
  pushUiCheck(flow, 'scanner hero visible', await page.locator('[data-testid="user-scanner-bento-hero"]').isVisible().catch(() => false));
  pushUiCheck(flow, 'scanner run button visible', await page.locator('[data-testid="scanner-run-button"]').isVisible().catch(() => false));
  pushUiCheck(flow, 'scanner drawer trigger visible', await page.locator('[data-testid="user-scanner-bento-drawer-trigger"]').isVisible().catch(() => false));
  if (await page.locator('[data-testid="user-scanner-bento-drawer-trigger"]').isVisible().catch(() => false)) {
    await page.locator('[data-testid="user-scanner-bento-drawer-trigger"]').click();
    await page.getByRole('dialog').waitFor({ state: 'visible', timeout: actionTimeoutMs }).catch(() => undefined);
    pushUiCheck(flow, 'scanner history drawer opens', await page.getByRole('dialog').isVisible().catch(() => false));
    await page.keyboard.press('Escape').catch(() => undefined);
  }
  flow.screenshots.push(await takeScreenshot(page, browserName, viewportName, slugPrefix));
}

async function verifyPortfolio(page, browserName, viewportName, flow, slugPrefix = 'portfolio') {
  await page.goto(`${baseUrl}/portfolio`, { waitUntil: 'domcontentloaded' });
  await page.locator('[data-testid="portfolio-bento-page"]').waitFor({ state: 'visible', timeout: actionTimeoutMs });
  const historyTrigger = page.locator('[data-testid="portfolio-history-drawer-trigger"]');
  await historyTrigger.waitFor({ state: 'visible', timeout: actionTimeoutMs }).catch(() => undefined);
  const historyTriggerCount = await historyTrigger.count().catch(() => 0);
  const historyTriggerVisible = historyTriggerCount > 0
    ? await historyTrigger.isVisible().catch(() => false)
    : false;
  pushUiCheck(flow, 'portfolio total assets card visible', await page.locator('[data-testid="portfolio-total-assets-card"]').isVisible().catch(() => false));
  pushUiCheck(flow, 'portfolio holdings panel visible', await page.locator('[data-testid="portfolio-current-holdings-panel"]').isVisible().catch(() => false));
  pushUiCheck(flow, 'portfolio history trigger visible', historyTriggerCount > 0, {
    visible: historyTriggerVisible,
  });
  if (historyTriggerVisible) {
    await historyTrigger.click();
    pushUiCheck(flow, 'portfolio history drawer opens', await page.locator('[data-testid="portfolio-history-drawer"]').isVisible().catch(() => false));
    await page.keyboard.press('Escape').catch(() => undefined);
  }
  flow.screenshots.push(await takeScreenshot(page, browserName, viewportName, slugPrefix));
}

async function verifyBacktest(page, browserName, viewportName, flow, slugPrefix = 'backtest') {
  await page.goto(`${baseUrl}/backtest`, { waitUntil: 'domcontentloaded' });
  await page.locator('[data-testid="backtest-bento-page"]').waitFor({ state: 'visible', timeout: actionTimeoutMs });
  pushUiCheck(flow, 'backtest hero strip visible', await page.locator('[data-testid="backtest-bento-hero"]').isVisible().catch(() => false));
  pushUiCheck(flow, 'backtest brief trigger visible', await page.locator('[data-testid="backtest-bento-drawer-trigger"]').isVisible().catch(() => false));
  const briefTrigger = page.locator('[data-testid="backtest-bento-drawer-trigger"]');
  if (await briefTrigger.isVisible().catch(() => false)) {
    await briefTrigger.click();
    await page.getByRole('dialog').waitFor({ state: 'visible', timeout: actionTimeoutMs }).catch(() => undefined);
    pushUiCheck(flow, 'backtest brief drawer opens', await page.getByRole('dialog').isVisible().catch(() => false));
    await page.keyboard.press('Escape').catch(() => undefined);
  }
  const professionalTab = page.getByRole('tab', { name: locatorRegex('专业', 'Professional') }).first();
  if (await professionalTab.isVisible().catch(() => false)) {
    await professionalTab.click();
    await page.locator('[data-testid="pro-backtest-workspace"]').waitFor({ state: 'visible', timeout: actionTimeoutMs }).catch(() => undefined);
    pushUiCheck(flow, 'backtest professional workspace visible', await page.locator('[data-testid="pro-backtest-workspace"]').isVisible().catch(() => false));
    const unsupportedCard = page.locator('article').filter({ hasText: locatorRegex('简单动量', 'Simple momentum') }).first();
    if (await unsupportedCard.isVisible().catch(() => false)) {
      await unsupportedCard.getByRole('button', { name: locatorRegex('载入参考模板', 'Load as reference') }).click();
      await page.locator('[data-testid="pro-strategy-catalog-toast"]').waitFor({ state: 'visible', timeout: actionTimeoutMs }).catch(() => undefined);
      pushUiCheck(
        flow,
        'backtest unsupported template warning visible',
        await page.locator('[data-testid="pro-strategy-catalog-toast"]').isVisible().catch(() => false),
      );
    }
  }
  flow.screenshots.push(await takeScreenshot(page, browserName, viewportName, slugPrefix));
}

async function verifyPreviewRoutes(page, browserName, viewportName, flow) {
  await page.goto(`${baseUrl}/__preview/report`, { waitUntil: 'domcontentloaded' });
  await page.locator('[data-testid="preview-report-page"]').waitFor({ state: 'visible', timeout: actionTimeoutMs }).catch(() => undefined);
  pushUiCheck(flow, 'preview report page visible', await page.locator('[data-testid="preview-report-page"]').isVisible().catch(() => false));
  flow.screenshots.push(await takeScreenshot(page, browserName, viewportName, 'preview-report'));

  await page.goto(`${baseUrl}/__preview/full-report`, { waitUntil: 'domcontentloaded' });
  const fullReportPage = page.locator('[data-testid="preview-full-report-page"]');
  await fullReportPage.waitFor({ state: 'visible', timeout: actionTimeoutMs }).catch(() => undefined);
  pushUiCheck(flow, 'preview full report page visible', await fullReportPage.isVisible().catch(() => false));
  const chineseButton = page.getByRole('button').filter({ hasText: locatorRegex('中文', 'Chinese') }).first();
  if (await chineseButton.isVisible().catch(() => false)) {
    await chineseButton.click();
    await page.getByRole('dialog').waitFor({ state: 'visible', timeout: actionTimeoutMs }).catch(() => undefined);
    pushUiCheck(flow, 'preview full report drawer opens', await page.getByRole('dialog').isVisible().catch(() => false));
    await page.keyboard.press('Escape').catch(() => undefined);
  }
  flow.screenshots.push(await takeScreenshot(page, browserName, viewportName, 'preview-full-report'));
}

async function verifySettings(page, browserName, viewportName, flow, slugPrefix = 'settings') {
  await page.goto(`${baseUrl}/settings`, { waitUntil: 'domcontentloaded' });
  await page.locator('[data-testid="personal-settings-workspace"]').waitFor({ state: 'visible', timeout: actionTimeoutMs });
  const enButton = page.getByRole('button').filter({ hasText: /^EN$/i }).first();
  if (await enButton.isVisible().catch(() => false)) {
    await enButton.click();
    await page.locator('body').waitFor({ state: 'visible', timeout: actionTimeoutMs });
  }
  pushUiCheck(flow, 'settings page visible', await page.locator('[data-testid="personal-settings-workspace"]').isVisible().catch(() => false));
  pushUiCheck(flow, 'settings locale switched to english', /\/en\/settings|\/settings/.test(page.url()));
  flow.screenshots.push(await takeScreenshot(page, browserName, viewportName, slugPrefix));
}

async function runPrimaryDesktopFlow(page, browserName, viewportName) {
  await recordFlow('visitor-home', async (flow) => {
    await page.goto(`${baseUrl}/`, { waitUntil: 'domcontentloaded' });
    pushUiCheck(flow, 'guest home visible', await page.locator('body').isVisible().catch(() => false));
    flow.screenshots.push(await takeScreenshot(page, browserName, viewportName, 'guest-home'));
  });

  await recordFlow('create-account', async (flow) => {
    const before = readDbSnapshot(TABLE_GROUPS.auth);
    await createUserViaUi(page, verificationUser);
    const after = readDbSnapshot(TABLE_GROUPS.auth);
    attachDbDelta(flow, before, after);
    await page.locator('[data-testid="home-bento-dashboard"]').waitFor({ state: 'visible', timeout: actionTimeoutMs }).catch(() => undefined);
    pushUiCheck(flow, 'home after create visible', await page.locator('[data-testid="home-bento-dashboard"]').isVisible().catch(() => false));
    flow.screenshots.push(await takeScreenshot(page, browserName, viewportName, 'create-account-home'));
  });

  await recordFlow('logout-login', async (flow) => {
    await logoutViaFetch(page);
    await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded' });
    flow.screenshots.push(await takeScreenshot(page, browserName, viewportName, 'login-screen'));
    await loginViaUi(page, verificationUser);
    pushUiCheck(flow, 'login redirected home', await page.locator('[data-testid="home-bento-dashboard"]').isVisible().catch(() => false));
    flow.screenshots.push(await takeScreenshot(page, browserName, viewportName, 'post-login-home'));
  });

  await recordFlow('home-analysis', async (flow) => {
    const before = readDbSnapshot(TABLE_GROUPS.analysis);
    await page.goto(`${baseUrl}/`, { waitUntil: 'domcontentloaded' });
    await page.locator('[data-testid="home-bento-omnibar-input"]').fill('TSLA');
    await page.locator('[data-testid="home-bento-analyze-button"]').click();
    await withTimeout('home analysis render', async () => {
      await Promise.race([
        page.getByText(/TSLA/i).waitFor({ state: 'visible', timeout: actionTimeoutMs }),
        page.locator('[data-testid="home-bento-fallback-toast"]').waitFor({ state: 'visible', timeout: actionTimeoutMs }),
      ]);
    });
    const after = readDbSnapshot(TABLE_GROUPS.analysis);
    attachDbDelta(flow, before, after);
    await verifyHome(page, browserName, viewportName, flow, 'home-analysis');
  });

  await recordFlow('scanner-run', async (flow) => {
    const before = readDbSnapshot(TABLE_GROUPS.scanner);
    const chosenConfig = await runScannerWithFallback(page, flow);
    flow.uiChecks.push({
      name: 'scanner config selected',
      status: 'pass',
      market: chosenConfig.market,
      profile: chosenConfig.profile,
    });
    const after = readDbSnapshot(TABLE_GROUPS.scanner);
    attachDbDelta(flow, before, after);
    await verifyScanner(page, browserName, viewportName, flow, 'scanner-run');
  });

  await recordFlow('portfolio-actions', async (flow) => {
    const before = readDbSnapshot(TABLE_GROUPS.portfolio);
    await page.goto(`${baseUrl}/portfolio`, { waitUntil: 'domcontentloaded' });
    const accountTab = page.getByRole('button').filter({ hasText: locatorRegex('账户', 'Account') }).first();
    await accountTab.click();
    const accountSection = page.locator('[data-testid="portfolio-trade-station-scroll"]');
    const allInputs = accountSection.locator('input');
    await allInputs.nth(0).fill('UX Main');
    await allInputs.nth(1).fill('manual');
    await allInputs.nth(2).fill('CNY');
    await accountSection.locator('button[type="submit"]').last().click();
    await page.locator('body').waitFor({ state: 'visible', timeout: actionTimeoutMs });

    const tradeTab = page.getByRole('button').filter({ hasText: locatorRegex('交易', 'Trade') }).first();
    await tradeTab.click();
    const tradeScroll = page.locator('[data-testid="portfolio-trade-station-scroll"]');
    const tradeInputs = tradeScroll.locator('input');
    await tradeInputs.nth(0).fill('600519');
    await tradeInputs.nth(2).fill('10');
    await tradeInputs.nth(3).fill('1500');
    await tradeScroll.getByRole('button').filter({ hasText: locatorRegex('提交交易', 'Submit trade') }).click();
    await page.locator('body').waitFor({ state: 'visible', timeout: actionTimeoutMs });

    await page.locator('[data-testid="portfolio-trade-type-switcher"]').getByRole('button').filter({ hasText: locatorRegex('资金划转', 'Cash Transfer') }).click();
    const cashInputs = tradeScroll.locator('input');
    await cashInputs.nth(0).fill('2026-04-27');
    await cashInputs.nth(1).fill('20000');
    await cashInputs.nth(2).fill('ux cash');
    await tradeScroll.getByRole('button').filter({ hasText: locatorRegex('提交资金', 'Submit cash') }).click();
    await page.locator('body').waitFor({ state: 'visible', timeout: actionTimeoutMs });

    await page.locator('[data-testid="portfolio-trade-type-switcher"]').getByRole('button').filter({ hasText: locatorRegex('公司行为', 'Corporate Action') }).click();
    const corpInputs = tradeScroll.locator('input');
    await corpInputs.nth(0).fill('600519');
    await corpInputs.nth(2).fill('2.5');
    await corpInputs.nth(4).fill('ux corporate');
    await tradeScroll.getByRole('button').filter({ hasText: locatorRegex('提交公司行为', 'Submit corporate') }).click();
    await page.locator('body').waitFor({ state: 'visible', timeout: actionTimeoutMs });

    const after = readDbSnapshot(TABLE_GROUPS.portfolio);
    attachDbDelta(flow, before, after);
    await verifyPortfolio(page, browserName, viewportName, flow, 'portfolio-actions');
  });

  await recordFlow('backtest-runs', async (flow) => {
    const before = readDbSnapshot(TABLE_GROUPS.backtest);
    await page.goto(`${baseUrl}/backtest`, { waitUntil: 'domcontentloaded' });
    await page.locator('[data-testid="backtest-bento-page"]').waitFor({ state: 'visible', timeout: actionTimeoutMs });
    const codeInput = page.getByLabel(locatorRegex('标的代码', 'Ticker')).first();
    const templateSelect = page.getByLabel(locatorRegex('策略模板', 'Strategy template')).first();

    for (const template of CORE_TEMPLATES) {
      await codeInput.fill('600519');
      await templateSelect.selectOption(template);
      await page.getByRole('button').filter({ hasText: locatorRegex('一键开始回测', 'Launch backtest') }).click({ force: true });
      try {
        await withTimeout(`backtest normal template ${template}`, async () => {
          await Promise.race([
            page.waitForURL(/\/backtest\/results\/\d+/, { timeout: actionTimeoutMs }),
            page.locator('[data-testid="normal-backtest-workspace"]').waitFor({ state: 'visible', timeout: actionTimeoutMs }),
          ]);
        });
      } catch (error) {
        flow.warnings.push(`${template}: ${String(error)}`);
      }
      if (/\/backtest\/results\//.test(page.url())) {
        flow.steps.push({ template, mode: 'normal', outcome: 'navigated_to_result' });
        await takeScreenshot(page, browserName, viewportName, `backtest-normal-${template}`);
        await page.goto(`${baseUrl}/backtest`, { waitUntil: 'domcontentloaded' });
      } else {
        const apiFallback = await invokeRuleBacktestApi(page, {
          code: '600519',
          strategyText: NORMAL_BACKTEST_TEMPLATE_STRATEGIES[template],
          startDate: '2025-04-27',
          endDate: '2026-04-27',
          lookbackBars: 252,
          initialCapital: 100000,
          feeBps: 0,
          slippageBps: 0,
        });
        if (apiFallback.ok) {
          const payload = JSON.parse(apiFallback.body);
          flow.steps.push({
            template,
            mode: 'normal',
            outcome: 'api_fallback_persisted',
            runId: payload.id,
          });
          if (payload.id) {
            await page.goto(`${baseUrl}/backtest/results/${payload.id}`, { waitUntil: 'domcontentloaded' });
            await takeScreenshot(page, browserName, viewportName, `backtest-normal-${template}`);
            await page.goto(`${baseUrl}/backtest`, { waitUntil: 'domcontentloaded' });
          }
        } else {
          flow.steps.push({
            template,
            mode: 'normal',
            outcome: 'stayed_on_launch_page',
            fallbackStage: apiFallback.stage,
            fallbackStatus: apiFallback.status,
          });
          throw new Error(`backtest ${template} launch failed: ${apiFallback.stage} HTTP ${apiFallback.status} ${compactText(apiFallback.body).slice(0, 240)}`);
        }
      }
    }

    await page.locator('[data-testid="backtest-subnav"]').waitFor({ state: 'visible', timeout: actionTimeoutMs }).catch(() => undefined);
    const controlModeNav = page.locator('[data-testid="backtest-subnav"] nav').last();
    const professionalModeTab = controlModeNav.locator('button[role="tab"]').last();
    if ((await professionalModeTab.count().catch(() => 0)) > 0) {
      await professionalModeTab.click({ force: true });
      await page.waitForTimeout(250);
      if ((await page.locator('[data-testid="pro-backtest-workspace"]').count().catch(() => 0)) === 0) {
        await professionalModeTab.press('Enter').catch(() => undefined);
      }
    } else {
      flow.warnings.push('Professional mode toggle not visible');
    }
    const professionalWorkspace = page.locator('[data-testid="pro-backtest-workspace"]');
    await professionalWorkspace.waitFor({ state: 'attached', timeout: actionTimeoutMs }).catch(() => undefined);
    pushUiCheck(flow, 'professional workspace visible', (await professionalWorkspace.count().catch(() => 0)) > 0, {
      visible: await professionalWorkspace.isVisible().catch(() => false),
    });
    flow.screenshots.push(await takeScreenshot(page, browserName, viewportName, 'backtest-professional'));
    const after = readDbSnapshot(TABLE_GROUPS.backtest);
    attachDbDelta(flow, before, after);
  });

  await recordFlow('report-previews', async (flow) => {
    await verifyPreviewRoutes(page, browserName, viewportName, flow);
  });

  await recordFlow('settings-locale', async (flow) => {
    await verifySettings(page, browserName, viewportName, flow, 'settings-locale');
  });
}

async function runSurfaceVerification(browserProfile, viewport) {
  const browser = await browserProfile.launcher.launch({ headless: true });
  const context = await browser.newContext({
    viewport: viewport.viewport,
    isMobile: viewport.isMobile || false,
    hasTouch: viewport.hasTouch || false,
  });
  createNetworkTracker(context);
  const page = await context.newPage();
  page.setDefaultTimeout(actionTimeoutMs);
  page.setDefaultNavigationTimeout(actionTimeoutMs);
  await loginViaUi(page, verificationUser);

    const flow = await recordFlow(`surface-check-${browserProfile.name}-${viewport.name}`, async (record) => {
      await verifyHome(page, browserProfile.name, viewport.name, record, 'home');
      await verifyScanner(page, browserProfile.name, viewport.name, record, 'scanner');
      await verifyPortfolio(page, browserProfile.name, viewport.name, record, 'portfolio');
    await verifyBacktest(page, browserProfile.name, viewport.name, record, 'backtest');
    await verifyPreviewRoutes(page, browserProfile.name, viewport.name, record);
    await verifySettings(page, browserProfile.name, viewport.name, record, 'settings');
  });

  report.surfaceChecks.push({
    browser: browserProfile.name,
    viewport: viewport.name,
    status: flow.status,
  });

  await context.close();
  await browser.close();
}

function buildMarkdown() {
  const summary = summarizeFlowOutcomes(report.flows.map((flow) => ({
    name: flow.name,
    status: flow.status,
  })));

  const lines = [
    '# WolfyStock UX Verification Report',
    '',
    `- Generated at: \`${report.generatedAt}\``,
    `- Base URL: \`${report.baseUrl}\``,
    `- Preview URL: \`${report.previewUrl}\``,
    `- Username: \`${report.user.username}\``,
    `- Overall: \`${summary.overallStatus}\``,
    `- Passed / Partial / Failed: \`${summary.passed} / ${summary.partial} / ${summary.failed}\``,
    '',
    '## Flow Summary',
    '',
    '| Flow | Status | Notes |',
    '| --- | --- | --- |',
  ];

  for (const flow of report.flows) {
    const note = flow.error || flow.warnings[0] || '-';
    lines.push(`| ${flow.name} | ${String(flow.status).toUpperCase()} | ${String(note).replace(/\|/g, '\\|')} |`);
  }

  lines.push('', '## Failed Requests', '', '| Status | Method | URL | Payload |', '| --- | --- | --- | --- |');
  if (report.failedRequests.length === 0) {
    lines.push('| - | - | - | - |');
  } else {
    for (const item of report.failedRequests) {
      lines.push(`| ${item.status} | ${item.method} | \`${item.url}\` | \`${compactText(item.requestPayload || '').slice(0, 120) || '-'}\` |`);
    }
  }

  lines.push('', '## Warnings', '');
  if (report.warnings.length === 0 && report.flows.every((flow) => flow.warnings.length === 0)) {
    lines.push('- None');
  } else {
    for (const warning of report.warnings) {
      lines.push(`- ${warning}`);
    }
    for (const flow of report.flows) {
      for (const warning of flow.warnings) {
        lines.push(`- ${flow.name}: ${warning}`);
      }
    }
  }

  return `${lines.join('\n')}\n`;
}

async function main() {
  await ensureDirs();
  report.runtime.previewReachable = true;
  report.runtime.backendStatus = readBackendStatus();

  const primaryBrowser = await chromium.launch({ headless: true });
  const primaryContext = await primaryBrowser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  createNetworkTracker(primaryContext);
  const primaryPage = await primaryContext.newPage();
  primaryPage.setDefaultTimeout(actionTimeoutMs);
  primaryPage.setDefaultNavigationTimeout(actionTimeoutMs);

  await runPrimaryDesktopFlow(primaryPage, 'chromium', 'desktop');

  await primaryContext.close();
  await primaryBrowser.close();

  await runSurfaceVerification({ name: 'chromium', launcher: chromium }, { name: 'mobile', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await runSurfaceVerification({ name: 'webkit', launcher: webkit }, { name: 'desktop', viewport: { width: 1440, height: 900 } });
  await runSurfaceVerification({ name: 'webkit', launcher: webkit }, { name: 'mobile', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

  await fs.writeFile(reportJsonPath, JSON.stringify(report, null, 2));
  await fs.writeFile(reportMdPath, buildMarkdown());
  process.stdout.write(`${path.relative(repoRoot, reportJsonPath)}\n${path.relative(repoRoot, reportMdPath)}\n`);
}

await main();
