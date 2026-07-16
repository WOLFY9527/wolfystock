import { expect, type Page, type Route } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { test as appSmokeTest } from './fixtures/appSmoke';
import { openAdminRouteWithHarness, test as adminAuthTest } from './fixtures/adminAuth';

const phase = process.env.T448_EVIDENCE_PHASE || 'after';
const evidenceRoot = path.resolve(process.cwd(), '../../output/t448', phase);
const screenshotRoot = path.join(evidenceRoot, 'screenshots');

const viewports = [
  { width: 1440, height: 900 },
  { width: 1280, height: 720 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
] as const;

type RouteKey = 'home' | 'guest' | 'market-overview' | 'stock-structure';

type Measurement = {
  phase: string;
  route: RouteKey;
  locale: 'zh' | 'en';
  viewport: string;
  path: string;
  finalUrl: string;
  domNodes: number;
  borderedContainers: number;
  marketModules: number;
  visibleStatusBadges: number;
  primaryBlocks: number;
  mainLandmarks: number;
  h1Count: number;
  emptyHeadingCount: number;
  horizontalOverflow: number;
  rightRailGroups: number;
  invalidDisclosureCount: number;
  logoColdBytes: number;
  googleFontStylesheetRequests: number;
  rawDiagnosticHits: string[];
  localeLeakHits: string[];
};

const measurements: Measurement[] = [];

function fulfillJson(route: Route, payload: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

function dashboardPayload() {
  const asOf = '2026-07-07T09:30:00Z';
  return {
    status: 'ready',
    asOf,
    marketPulse: {
      sp500: { label: 'S&P 500', value: '5,430', change: '+0.3%', status: 'ready' },
      nasdaq: { label: 'Nasdaq', value: '19,880', change: '+0.6%', status: 'ready' },
      russell2000: { label: 'Russell 2000', value: '2,240', change: '+0.1%', status: 'ready' },
      vix: { label: 'VIX', value: '13.8', change: '-0.4', status: 'ready' },
      tenYearYield: { label: '10Y', value: '4.12%', change: '-0.02', status: 'ready' },
      dollarIndex: { label: 'DXY', value: '103.6', change: '-0.2', status: 'ready' },
      marketBreadth: { summary: 'Participation is broadening across returned market groups.', status: 'ready' },
      liquidityState: 'stable',
    },
    marketBrief: {
      headline: 'Breadth leads the morning research map',
      summary: 'Participation improved while volatility cooled; verify that follow-through remains broad.',
      status: 'ready',
    },
    moneyFlow: {
      topInflows: ['Semiconductors', 'Software'],
      topOutflows: ['Defensives'],
      styleBias: 'Growth leadership broadening',
      offensiveDefensiveBias: 'Offensive groups leading',
      sourceStatus: 'ready',
      status: 'ready',
    },
    liquidityRisk: {
      summary: 'Liquidity pressure remains contained',
      volatilityTone: 'calm',
      fundingStress: 'low',
      dollarRatePressure: 'easing',
      status: 'ready',
    },
    sectorThemeRotation: {
      leadingThemes: ['AI infrastructure', 'Cloud software'],
      laggingThemes: ['Utilities'],
      diffusion: 'broadening',
      summary: 'Theme participation is expanding beyond the first leaders.',
      status: 'ready',
    },
    researchQueue: {
      status: 'ready',
      items: [{
        title: 'Review semiconductor breadth follow-through',
        summary: 'Returned market evidence shows broader participation.',
        action: 'Open Research Radar to compare breadth evidence',
        priority: 'High',
      }],
    },
    dataQuality: {
      state: 'ready',
      label: 'Research-ready evidence',
      summary: 'Returned market facts are complete enough for observation and freshness review.',
      sections: { marketPulse: 'ready', queue: 'ready', marketBrief: 'ready' },
    },
    productReadModel: {
      contractVersion: 'product_read_model_v1',
      surface: 'Dashboard',
      state: 'available',
      ready: true,
      blockingChildren: [],
      freshness: { state: 'available', asOf },
      provenance: { sourceClass: 'dashboard_read_models', asOf, freshness: 'available', quality: 'available' },
    },
    noAdviceDisclosure: 'Research observation only.',
  };
}

async function installHomeFixture(page: Page) {
  await page.route('**/api/v1/dashboard/market-intelligence-overview**', (route) => fulfillJson(route, dashboardPayload()));
}

function symbolFromPath(route: Route) {
  const parts = new URL(route.request().url()).pathname.split('/');
  const index = parts.indexOf('stocks');
  return decodeURIComponent(parts[index + 1] || 'AAPL').toUpperCase();
}

async function installStockFixture(page: Page) {
  const asOf = '2026-07-06T13:30:00Z';
  await page.route('**/api/v1/stocks/*/validate', (route) => fulfillJson(route, {
    stock_code: symbolFromPath(route), normalized_symbol: symbolFromPath(route), market: 'us', status: 'valid', valid: true, exists: true, stock_name: 'Apple',
  }));
  await page.route('**/api/v1/stocks/*/quote', (route) => fulfillJson(route, {
    stock_code: symbolFromPath(route), stock_name: 'Apple', current_price: 211.32, change: 1.24, change_percent: 0.59,
    update_time: asOf, freshness: 'delayed',
    source_confidence: { source_label: 'Playwright Fixture', as_of: asOf, freshness: 'delayed', is_stale: false, is_partial: false, is_synthetic: false, is_unavailable: false },
  }));
  await page.route('**/api/v1/stocks/*/research-packet', (route) => fulfillJson(route, {
    symbol: symbolFromPath(route), market: 'us', identity: { name: 'Apple', exchange: 'NASDAQ', sector: 'Technology', industry: 'Hardware' },
    quote: { state: 'available', price: 211.32, change_percent: 0.59, as_of: asOf },
    history: { state: 'available', bars: 90, period: 'daily', as_of: '2026-07-06' },
    structure: { state: 'available', label: 'Range-bound', confidence: 'medium', as_of: '2026-07-06' },
    fundamentals: { state: 'not_integrated', fields_available: [] },
    events: { state: 'missing', latest: [] },
    peer: { state: 'insufficient', benchmark: 'QQQ' },
    missing_data: ['peer evidence'], research_status: 'partial',
    next_data_action: 'Review comparable evidence before drawing conclusions.', observation_only: true, decision_grade: false,
    no_advice_disclosure: 'Research observation only.',
  }));
  await page.route('**/api/v1/stocks/*/structure-decision', (route) => fulfillJson(route, {
    schema_version: 't448_stock_structure_fixture_v1', ticker: symbolFromPath(route), structure_state: 'range', confidence: 'medium',
    confidence_cap: { value: 55, label: 'Medium', reasons: ['Fixture route evidence is bounded.'] },
    confidence_state: { status: 'partial', label: 'Evidence limited', reasons: ['Peer evidence remains incomplete.'] },
    component_scores: { trend: 58, relativeStrength: 52, evidenceQuality: 45, volatilityCompression: 41, breakoutQuality: 39 },
    explanation: {
      why_this_structure: 'Price evidence remains range-bound in the browser qualification fixture.',
      what_confirms_it: ['Fresh price evidence remains available.'], what_invalidates_it: ['Evidence falls out of date.'],
      key_levels: [{ kind: 'support', value: 198.5, description: 'Fixture support level.' }],
    },
    research_notes: { watch_next: ['Refresh quote evidence before deeper review.'], needs_more_evidence: ['Comparable peer evidence.'], risk_flags: ['Evidence is partial.'] },
    data_quality: { status: 'partial', period: 'daily', requested_days: 120, observed_bars: 90, usable_bars: 90, reason: 'Fixture route smoke coverage.' },
    missing_evidence: [{ kind: 'peer', message: 'Comparable evidence pending.' }],
    no_advice_disclosure: 'Research observation only.',
  }));
  await page.route('**/api/v1/stocks/*/history**', (route) => fulfillJson(route, {
    stock_code: symbolFromPath(route), stock_name: 'Apple', period: 'daily', source: 'playwright_fixture',
    source_confidence: { source_label: 'Playwright Fixture', as_of: asOf, freshness: 'delayed', is_stale: false, is_partial: false, is_synthetic: false, is_unavailable: false },
    data: [
      { date: '2026-07-01', open: 207.1, high: 211.2, low: 205.8, close: 209.6, volume: 21200000, change_percent: 0.8 },
      { date: '2026-07-02', open: 209.8, high: 213.1, low: 208.7, close: 211.4, volume: 23800000, change_percent: 0.86 },
      { date: '2026-07-03', open: 211.1, high: 214.5, low: 210.2, close: 213.8, volume: 22100000, change_percent: 1.14 },
    ],
  }));
  await page.route('**/api/v1/stocks/*/technical-indicators', (route) => fulfillJson(route, {
    symbol: symbolFromPath(route), as_of: asOf, summary: { trend: 'range', momentum: 'neutral', volatility: 'normal' },
    indicators: { rsi: 54, macd: { value: 0.12, signal: 0.08, histogram: 0.04 }, moving_averages: { ma20: 208.4, ma50: 205.2 } },
    source_confidence: { source_label: 'Playwright Fixture', as_of: asOf, freshness: 'delayed', is_stale: false, is_partial: false, is_synthetic: false, is_unavailable: false },
  }));
  await page.route('**/api/v1/options/underlyings/*/structure', (route) => fulfillJson(route, {
    contract_version: 'options-structure-summary-v1', symbol: symbolFromPath(route), status: 'not_available', calculation_state: 'not_available',
    observation_only: true, decision_grade: false, provider_configured: false, spot_price: null, as_of: null, freshness: 'unknown',
    snapshot: { contract_version: 'option-chain-snapshot-v1', symbol: symbolFromPath(route), spot_price: null, as_of: null, freshness: 'unknown', contracts: [], missing_inputs: ['authorized_options_structure_source'] },
    strike_summaries: [], expiration_summaries: [], nearest_expirations: [],
    zero_dte: { state: 'not_available', expiration: null, dte: null, contract_count: 0, call_open_interest: 0, put_open_interest: 0, call_volume: 0, put_volume: 0, open_interest_share: null, volume_share: null },
    gamma_flip_level: { state: 'not_available', level: null, reason: 'authorized_structure_source_needed' }, total_dealer_gamma_exposure: null,
    blocking_reasons: ['options_structure_unavailable'], warnings: [], next_evidence_needed: ['authorized_structure_source_needed'],
  }));
  await page.route('**/api/v1/stocks/*/evidence**', (route) => fulfillJson(route, {
    symbol: symbolFromPath(route), items: [], evidence_items: [], summary: { state: 'partial' }, data_quality: { state: 'partial' },
  }));
}

async function signIn(page: Page, redirectPath: string) {
  await page.goto(`/login?redirect=${encodeURIComponent(redirectPath)}`);
  await page.locator('#username').fill('wolfy-user');
  await page.locator('#password').fill('mock-password');
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/v1/auth/login') && response.status() === 200),
    page.getByRole('button', { name: /sign in|登录继续|授权进入工作台|完成设置并登录/i }).click(),
  ]);
}

function rootTestId(route: RouteKey) {
  if (route === 'home' || route === 'guest') return 'home-bento-dashboard';
  if (route === 'market-overview') return 'market-overview-shell';
  return 'stock-structure-decision-page';
}

async function collectMeasurement(
  page: Page,
  route: RouteKey,
  locale: 'zh' | 'en',
  pathname: string,
  googleFontStylesheetRequests: number,
): Promise<Measurement> {
  const root = page.getByTestId(rootTestId(route));
  await expect(root).toBeVisible({ timeout: 20_000 });
  await page.waitForLoadState('networkidle', { timeout: 4_000 }).catch(() => undefined);
  const metrics = await root.evaluate((owner, pageLocale) => {
    const visible = (element: Element, firstViewportOnly = false) => {
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0 || rect.width <= 0 || rect.height <= 0) return false;
      const closedDisclosure = element.closest('details:not([open])');
      const disclosureSummary = closedDisclosure?.querySelector(':scope > summary');
      if (closedDisclosure && !disclosureSummary?.contains(element)) return false;
      return !firstViewportOnly || (rect.bottom > 0 && rect.top < window.innerHeight && rect.right > 0 && rect.left < window.innerWidth);
    };
    const candidates = Array.from(owner.querySelectorAll<HTMLElement>('*'));
    const borderedContainers = candidates.filter((element) => {
      if (!visible(element, true) || ['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'].includes(element.tagName)) return false;
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      const hasBorder = [style.borderTopWidth, style.borderRightWidth, style.borderBottomWidth, style.borderLeftWidth]
        .some((width) => Number.parseFloat(width) > 0);
      return hasBorder && rect.width >= 80 && rect.height >= 28;
    });
    const moduleSelectors = [
      '[data-testid="market-decision-semantics-strip"]',
      '[data-testid="market-overview-observation-head"]',
      '[data-testid="market-overview-summary-strip"]',
      '[data-testid="market-overview-data-quality-composition"]',
      '[data-testid="market-overview-research-risk-limits"]',
      '[data-testid="market-overview-next-research-action"]',
      '[data-testid="market-overview-category-tabs"]',
      '[data-testid="market-overview-visual-evidence-strip"]',
      '[data-testid="market-overview-regime-summary"]',
      '[data-testid="market-overview-context-rail"]',
      '[data-evidence-group-role]',
      '[data-testid^="market-overview-card-"]',
    ].join(',');
    const statusSelectors = [
      '[data-testid*="badge"]', '[data-testid*="chip"]', '[class*="badge"]', '[class*="pill"]', '[data-status-badge]',
    ].join(',');
    const rawDiagnosticPattern = /volatility_stress|provider_missing|data_disabled|sourceClass|noExternalCalls|contractVersion|failClosed|readiness_blocked|Missing scoring evidence/gi;
    const rawDiagnosticHits = Array.from(new Set((owner.textContent || '').match(rawDiagnosticPattern) || []));
    const visibleLeafText = candidates
      .filter((element) => element.children.length === 0 && visible(element))
      .map((element) => (element.textContent || '').replace(/\s+/g, ' ').trim())
      .filter(Boolean);
    const localeLeakPattern = pageLocale === 'en'
      ? /[\u3400-\u9fff]/
      : /Playwright Fixture|Missing scoring evidence|provider_|sourceClass|contractVersion|failClosed|debug|raw evidence/i;
    const localeLeakHits = Array.from(new Set(visibleLeafText.filter((text) => localeLeakPattern.test(text)))).slice(0, 24);
    return {
      domNodes: candidates.length + 1,
      borderedContainers: borderedContainers.length,
      marketModules: Array.from(owner.querySelectorAll(moduleSelectors)).filter((element) => visible(element, true)).length,
      visibleStatusBadges: Array.from(owner.querySelectorAll(statusSelectors)).filter((element) => visible(element, true)).length,
      primaryBlocks: Array.from(owner.querySelectorAll('[data-primary-information-block]')).filter((element) => visible(element, true)).length,
      mainLandmarks: document.querySelectorAll('main, [role="main"]').length,
      h1Count: document.querySelectorAll('h1').length,
      emptyHeadingCount: Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')).filter((element) => !(element.textContent || '').trim()).length,
      horizontalOverflow: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
      rightRailGroups: Array.from(owner.querySelectorAll('[data-right-rail-group], [data-testid="market-overview-context-rail"] > *')).filter((element) => visible(element, true)).length,
      invalidDisclosureCount: Array.from(owner.querySelectorAll('details')).filter((element) => !element.querySelector(':scope > summary')).length,
      rawDiagnosticHits,
      localeLeakHits,
    };
  }, locale);
  const logoColdBytes = await page.evaluate(() => performance.getEntriesByType('resource')
    .filter((entry) => /wolfystock-logo-mark\.(?:png|svg)/.test(entry.name))
    .reduce((total, entry) => total + ((entry as PerformanceResourceTiming).transferSize || (entry as PerformanceResourceTiming).encodedBodySize || 0), 0));
  return {
    phase, route, locale, viewport: `${page.viewportSize()?.width}x${page.viewportSize()?.height}`, path: pathname, finalUrl: page.url(),
    ...metrics, logoColdBytes, googleFontStylesheetRequests,
  };
}

async function captureRoute(
  page: Page,
  route: RouteKey,
  locale: 'zh' | 'en',
  pathname: string,
) {
  let fontRequests = 0;
  page.on('request', (request) => {
    if (request.url().startsWith('https://fonts.googleapis.com/')) fontRequests += 1;
  });
  if (route === 'home') {
    await installHomeFixture(page);
    await installStockFixture(page);
  }
  if (route === 'stock-structure') await installStockFixture(page);
  if (route !== 'guest') await signIn(page, pathname);
  await page.goto(pathname);
  const measurement = await collectMeasurement(page, route, locale, pathname, fontRequests);
  measurements.push(measurement);
  expect(measurement.localeLeakHits, `${route} ${locale} visible locale leaks`).toEqual([]);
  expect(measurement.invalidDisclosureCount, `${route} ${locale} labelled disclosures`).toBe(0);
  await expect(page.locator('html')).not.toHaveJSProperty('scrollWidth', 0);
  await expect(measurement.horizontalOverflow).toBe(0);
  fs.mkdirSync(screenshotRoot, { recursive: true });
  await page.screenshot({
    path: path.join(screenshotRoot, `${route}-${locale}-${measurement.viewport}.png`),
    fullPage: true,
    animations: 'disabled',
  });
}

for (const viewport of viewports) {
  for (const locale of ['zh', 'en'] as const) {
    appSmokeTest(`captures Home ${locale} ${viewport.width}x${viewport.height}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await captureRoute(page, 'home', locale, `/${locale}`);
    });
    appSmokeTest(`captures Market Overview ${locale} ${viewport.width}x${viewport.height}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await captureRoute(page, 'market-overview', locale, `/${locale}/market-overview`);
    });
    appSmokeTest(`captures Stock Structure ${locale} ${viewport.width}x${viewport.height}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await captureRoute(page, 'stock-structure', locale, `/${locale}/stocks/AAPL/structure-decision`);
    });
  }
}

for (const locale of ['zh', 'en'] as const) {
  for (const viewport of [viewports[0], viewports[3]]) {
    appSmokeTest(`captures Guest ${locale} ${viewport.width}x${viewport.height}`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await captureRoute(page, 'guest', locale, `/${locale}/guest`);
    });
  }
}

appSmokeTest('preserves direct route, refresh, query/hash and back/forward', async ({ page }) => {
  await page.setViewportSize(viewports[0]);
  await signIn(page, '/zh/market-overview?view=decision#evidence');
  await page.goto('/zh/market-overview?view=decision#evidence');
  await expect(page).toHaveURL(/\/zh\/market-overview\?view=decision#evidence$/);
  await page.reload();
  await expect(page).toHaveURL(/\/zh\/market-overview\?view=decision#evidence$/);
  await page.goto('/zh');
  await page.goBack();
  await expect(page).toHaveURL(/\/zh\/market-overview\?view=decision#evidence$/);
  await page.goForward();
  await expect(page).toHaveURL(/\/zh$/);
});

appSmokeTest('keeps the mobile drawer Escape and focus-return contract', async ({ page }) => {
  await page.setViewportSize(viewports[3]);
  await installHomeFixture(page);
  await installStockFixture(page);
  await signIn(page, '/zh');
  await page.goto('/zh');
  const trigger = page.getByRole('button', { name: /打开.*菜单|open.*menu|菜单/i }).last();
  await trigger.click();
  await expect(page.getByRole('dialog').first()).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog').first()).toBeHidden();
  await expect(trigger).toBeFocused();
});

appSmokeTest('keeps expanded Market Overview evidence reachable and localized in English', async ({ page }) => {
  await page.setViewportSize(viewports[2]);
  await signIn(page, '/en/market-overview');
  await page.goto('/en/market-overview');
  const disclosureIds = [
    'market-overview-trust-disclosure',
    'market-overview-evidence-disclosure',
    'market-overview-primary-evidence-disclosure',
    'market-overview-deep-evidence-disclosure',
    'market-overview-data-diagnostics-disclosure',
  ];
  const localeLeaks: Record<string, string[]> = {};
  for (const testId of disclosureIds) {
    const disclosure = page.getByTestId(testId);
    await disclosure.locator(':scope > summary').click();
    await expect(disclosure).toHaveAttribute('open', '');
    localeLeaks[testId] = await page.getByTestId('market-overview-shell').evaluate((owner) => {
      const visibleLeafText = Array.from(owner.querySelectorAll<HTMLElement>('*'))
        .filter((element) => {
          if (element.children.length > 0) return false;
          const style = window.getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          const closedDisclosure = element.closest('details:not([open])');
          const disclosureSummary = closedDisclosure?.querySelector(':scope > summary');
          if (closedDisclosure && !disclosureSummary?.contains(element)) return false;
          return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) !== 0 && rect.width > 0 && rect.height > 0;
        })
        .map((element) => ({
          element,
          text: (element.textContent || '').replace(/\s+/g, ' ').trim(),
        }))
        .filter(({ text }) => /[\u3400-\u9fff]/.test(text))
        .map(({ element, text }) => {
          const owner = element.closest<HTMLElement>('[data-testid]');
          return `${text} :: ${element.tagName.toLowerCase()}.${element.className} within ${owner?.dataset.testid || 'unlabelled'}`;
        });
      return Array.from(new Set(visibleLeafText)).slice(0, 24);
    });
    expect(localeLeaks[testId], `${testId} should use English presentation copy`).toEqual([]);
    await disclosure.locator(':scope > summary').click();
    await expect(disclosure).not.toHaveAttribute('open', '');
  }
  expect(localeLeaks).toEqual(Object.fromEntries(disclosureIds.map((testId) => [testId, []])));
});

appSmokeTest('keeps expanded Home and Stock Structure evidence localized in English', async ({ page }) => {
  await page.setViewportSize(viewports[0]);
  await installHomeFixture(page);
  await installStockFixture(page);
  await signIn(page, '/en');
  for (const entry of [
    { path: '/en', root: 'home-bento-dashboard' },
    { path: '/en/stocks/AAPL/structure-decision', root: 'stock-structure-decision-page' },
  ]) {
    await page.goto(entry.path);
    const root = page.getByTestId(entry.root);
    await expect(root).toBeVisible({ timeout: 20_000 });
    for (let index = 0; index < 24; index += 1) {
      const closedSummary = root.locator('details:not([open]) > summary:visible').first();
      if (await closedSummary.count() === 0) break;
      await closedSummary.click();
    }
    const localeLeaks = await root.evaluate((owner) => {
      const visibleLeafText = Array.from(owner.querySelectorAll<HTMLElement>('*'))
        .filter((element) => {
          if (element.children.length > 0) return false;
          const style = window.getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) !== 0 && rect.width > 0 && rect.height > 0;
        })
        .map((element) => ({ element, text: (element.textContent || '').replace(/\s+/g, ' ').trim() }))
        .filter(({ text }) => /[\u3400-\u9fff]/.test(text))
        .map(({ element, text }) => {
          const owner = element.closest<HTMLElement>('[data-testid]');
          return `${text} :: ${element.tagName.toLowerCase()}.${element.className} within ${owner?.dataset.testid || 'unlabelled'}`;
        });
      return Array.from(new Set(visibleLeafText)).slice(0, 32);
    });
    expect(localeLeaks, `${entry.path} expanded evidence should use English presentation copy`).toEqual([]);
  }
});

appSmokeTest('writes T448 browser measurements and enforces after-state limits', async () => {
  fs.mkdirSync(evidenceRoot, { recursive: true });
  const metricsPath = path.join(evidenceRoot, 'metrics.json');
  fs.writeFileSync(metricsPath, JSON.stringify({ phase, generatedAt: new Date().toISOString(), measurements }, null, 2));
  expect(measurements.length).toBe(28);
  if (phase !== 'after') return;

  for (const measurement of measurements) {
    expect(measurement.horizontalOverflow, `${measurement.route} ${measurement.locale} ${measurement.viewport} overflow`).toBe(0);
    expect(measurement.mainLandmarks, `${measurement.route} ${measurement.locale} ${measurement.viewport} main landmarks`).toBe(1);
    expect(measurement.h1Count, `${measurement.route} ${measurement.locale} ${measurement.viewport} h1 count`).toBe(1);
    expect(measurement.emptyHeadingCount, `${measurement.route} ${measurement.locale} ${measurement.viewport} empty headings`).toBe(0);
    expect(measurement.rawDiagnosticHits, `${measurement.route} ${measurement.locale} ${measurement.viewport} diagnostics`).toEqual([]);
    expect(measurement.localeLeakHits, `${measurement.route} ${measurement.locale} ${measurement.viewport} locale leaks`).toEqual([]);
    expect(measurement.invalidDisclosureCount, `${measurement.route} ${measurement.locale} ${measurement.viewport} labelled disclosures`).toBe(0);
    expect(measurement.primaryBlocks, `${measurement.route} ${measurement.locale} ${measurement.viewport} primary blocks`).toBeLessThanOrEqual(5);
    expect(measurement.visibleStatusBadges, `${measurement.route} ${measurement.locale} ${measurement.viewport} status badges`).toBeLessThanOrEqual(6);
    expect(measurement.rightRailGroups, `${measurement.route} ${measurement.locale} ${measurement.viewport} right rail groups`).toBeLessThanOrEqual(3);
  }

  const beforePath = path.resolve(process.cwd(), '../../output/t448/before/metrics.json');
  if (!fs.existsSync(beforePath)) return;
  const before = JSON.parse(fs.readFileSync(beforePath, 'utf8')) as { measurements: Measurement[] };
  const pick = (items: Measurement[], route: RouteKey, locale: 'zh' | 'en', viewport: string) =>
    items.find((item) => item.route === route && item.locale === locale && item.viewport === viewport);
  const homeBefore = pick(before.measurements, 'home', 'zh', '1440x900');
  const homeAfter = pick(measurements, 'home', 'zh', '1440x900');
  const homeBeforeEn = pick(before.measurements, 'home', 'en', '1440x900');
  const homeAfterEn = pick(measurements, 'home', 'en', '1440x900');
  const marketBefore = pick(before.measurements, 'market-overview', 'zh', '1440x900');
  const marketAfter = pick(measurements, 'market-overview', 'zh', '1440x900');
  expect(homeBefore && homeAfter && homeBeforeEn && homeAfterEn && marketBefore && marketAfter).toBeTruthy();
  expect(homeAfter!.domNodes).toBeLessThanOrEqual(Math.floor(homeBefore!.domNodes * 0.75));
  expect(homeAfter!.borderedContainers).toBeLessThanOrEqual(Math.floor(homeBefore!.borderedContainers * 0.65));
  expect(homeAfterEn!.borderedContainers).toBeLessThanOrEqual(Math.floor(homeBeforeEn!.borderedContainers * 0.65));
  expect(marketAfter!.marketModules).toBeLessThanOrEqual(Math.floor(marketBefore!.marketModules * 0.60));
  expect(Math.max(...measurements.map((item) => item.googleFontStylesheetRequests))).toBe(0);
  expect(Math.max(...measurements.map((item) => item.logoColdBytes))).toBeLessThanOrEqual(45_799);
  expect(
    Math.max(...before.measurements.map((item) => item.logoColdBytes))
      - Math.max(...measurements.map((item) => item.logoColdBytes)),
  ).toBeGreaterThanOrEqual(430_000);
});

adminAuthTest('keeps a capability-gated administrator route reachable', async ({ page }) => {
  await page.setViewportSize(viewports[0]);
  await openAdminRouteWithHarness(page, '/zh/settings/system', {
    capabilities: ['ops:system_config:read'],
  });
  await expect(page).toHaveURL(/\/zh\/settings\/system$/);
  await expect(page.getByTestId('system-settings-page')).toBeVisible({ timeout: 20_000 });
});
