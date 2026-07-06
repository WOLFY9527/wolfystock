import { expect, test } from '@playwright/test';
import { installPortfolioSmokeHarness } from './fixtures/portfolioSmoke';

const viewports = [
  { name: 'desktop', width: 1440, height: 1000 },
  { name: 'mobile', width: 390, height: 844 },
];

const forbiddenLaunchLabels = ['交易工作台', '股票买卖', '提交交易', '下单', '订单执行', '买入', '卖出'];
const requiredLedgerLabels = ['当前持仓', '历史记录', '组合数据接入', '持仓流水'];
const forbiddenInternalLeakagePattern =
  /\braw\b|\bdebug\b|\bschema\b|\btrace\b|\bprompt\b|\btoken\b|\bcookie\b|\bauthorization\b|provider_timeout|MarketCache|local_db|fixture|mock|synthetic|generatedCandidates|failedCandidates/i;
const forbiddenSnakeCaseTokenPattern = /\b[a-z]+(?:_[a-z0-9]+)+\b/;

async function expectNoHorizontalOverflow(page: import('@playwright/test').Page) {
  const overflow = await page.evaluate(() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth));
  expect(overflow).toBeLessThanOrEqual(1);
}

async function classifyWideVisibleElements(page: import('@playwright/test').Page) {
  return page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth;
    const isVisible = (element: Element) => {
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== 'none'
        && style.visibility !== 'hidden'
        && Number.parseFloat(style.opacity || '1') > 0
        && rect.width > 0
        && rect.height > 0;
    };
    const hasScrollableAncestor = (element: Element) => {
      let current: Element | null = element;
      while (current && current !== document.body) {
        const style = window.getComputedStyle(current);
        if (/(auto|scroll)/.test(style.overflowX) && current.scrollWidth > current.clientWidth + 1) {
          return true;
        }
        current = current.parentElement;
      }
      return false;
    };
    return Array.from(document.querySelectorAll('body *'))
      .filter(isVisible)
      .map((element) => {
        const rect = element.getBoundingClientRect();
        const scrollDelta = Math.max(0, (element as HTMLElement).scrollWidth - (element as HTMLElement).clientWidth);
        const isWideBox = rect.width > viewportWidth + 1;
        const isInternalScrollable = scrollDelta > 1;
        if (!isWideBox && !isInternalScrollable) return null;
        const testId = element.getAttribute('data-testid') || element.closest('[data-testid]')?.getAttribute('data-testid') || '';
        const primitive = element.getAttribute('data-terminal-primitive') || element.closest('[data-terminal-primitive]')?.getAttribute('data-terminal-primitive') || '';
        const tag = element.tagName.toLowerCase();
        const className = typeof (element as HTMLElement).className === 'string' ? (element as HTMLElement).className : '';
        const classification = primitive === 'dense-table' || element.closest('[data-terminal-primitive="dense-table"]')
          ? 'INTENTIONAL_INTERNAL_SCROLL'
          : className.includes('inset-[-40px]') && className.includes('linear-gradient')
            ? 'FALSE_POSITIVE'
          : tag === 'canvas' || tag === 'svg' || element.closest('[data-chart-surface="true"]')
            ? 'SAFE_CHART_CANVAS'
            : isWideBox && !hasScrollableAncestor(element)
              ? 'ACTUAL_LAYOUT_ESCAPE'
              : 'FALSE_POSITIVE';
        return {
          tag,
          testId,
          primitive,
          className,
          width: Math.round(rect.width),
          scrollDelta: Math.round(scrollDelta),
          classification,
        };
      })
      .filter(Boolean);
  });
}

async function expectVisibleTextAbsent(page: import('@playwright/test').Page, labels: string[]) {
  const bodyText = await page.locator('body').innerText();
  const visibleLines = bodyText.split(/\s+/).map((line) => line.trim()).filter(Boolean);
  for (const label of labels) {
    expect(visibleLines).not.toContain(label);
  }
}

async function expectVisibleTextPresent(page: import('@playwright/test').Page, labels: string[]) {
  const bodyText = await page.locator('body').innerText();
  for (const label of labels) {
    expect(bodyText).toContain(label);
  }
}

function walkKeys(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.flatMap(walkKeys);
  }
  if (value && typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>).flatMap(([key, entry]) => [key, ...walkKeys(entry)]);
  }
  return [];
}

async function waitForPortfolioSurface(page: import('@playwright/test').Page) {
  const surface = page.getByTestId('portfolio-bento-page');
  await expect(surface).toBeVisible({ timeout: 15_000 });
  await page.waitForFunction(() => {
    const element = document.querySelector('[data-testid="portfolio-bento-page"]');
    return Boolean(
      element &&
      element.classList.contains('opacity-100') &&
      element.classList.contains('pointer-events-auto'),
    );
  });
}

test.describe('portfolio launch surface', () => {
  for (const viewport of viewports) {
    test(`keeps portfolio workspace lanes usable on ${viewport.name}`, async ({ page }) => {
      const consoleErrors: string[] = [];
      const pageErrors: string[] = [];
      page.on('console', (message) => {
        if (message.type() === 'error') {
          consoleErrors.push(message.text());
        }
      });
      page.on('pageerror', (error) => pageErrors.push(error.message));

      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      const harness = await installPortfolioSmokeHarness(page);
      await page.goto('/zh/portfolio', { waitUntil: 'domcontentloaded' });
      await waitForPortfolioSurface(page);

      const accountHero = page.getByTestId('portfolio-total-assets-card');
      const summaryCoreRow = page.getByTestId('portfolio-summary-core-row');
      const summaryAuxRow = page.getByTestId('portfolio-summary-aux-row');
      const workspaceLanes = page.getByTestId('portfolio-workspace-lanes');
      const primaryLane = page.getByTestId('portfolio-primary-lane');
      const secondaryLane = page.getByTestId('portfolio-secondary-lane');
      const activityLane = page.getByTestId('portfolio-activity-lane');
      const manualLane = page.getByTestId('portfolio-manual-lane');
      const holdingsPanel = page.getByTestId('portfolio-current-holdings-panel');
      const riskPanel = page.getByTestId('portfolio-risk-card');
      const activityPanel = page.getByTestId('portfolio-history-full');
      const setupBoundary = page.getByTestId('portfolio-consumer-setup-boundary');

      await expect(workspaceLanes).toBeVisible({ timeout: 15_000 });
      await expect(summaryCoreRow).toBeVisible({ timeout: 15_000 });
      await expect(summaryAuxRow).toBeVisible({ timeout: 15_000 });
      await expect(summaryCoreRow).toContainText('总市值');
      await expect(summaryCoreRow).toContainText('总盈亏');
      await expect(summaryAuxRow).toContainText('总现金');
      await expect(summaryAuxRow).toContainText('持仓');
      await expect(summaryAuxRow).toContainText('风险状态');
      await expect(summaryAuxRow).toContainText('状态快照');
      await expect(primaryLane).toBeVisible({ timeout: 15_000 });
      await expect(secondaryLane).toBeVisible({ timeout: 15_000 });
      await expect(activityLane).toBeVisible({ timeout: 15_000 });
      await expect(manualLane).toBeVisible({ timeout: 15_000 });
      await expect(holdingsPanel).toBeVisible({ timeout: 15_000 });
      await expect(riskPanel).toBeVisible({ timeout: 15_000 });
      await expect(activityPanel).toBeVisible({ timeout: 15_000 });
      await expect(setupBoundary).toContainText('组合数据接入');
      await expect(setupBoundary).not.toContainText(/IBKR|token|API|同步控件|request|trace|cache|payload/i);
      await expect(activityPanel).toContainText('历史记录');
      await expect(page.getByTestId('portfolio-bento-page')).not.toHaveAttribute('data-portfolio-paper-surface');

      const heroBox = await accountHero.boundingBox();
      const summaryCoreBox = await summaryCoreRow.boundingBox();
      const summaryAuxBox = await summaryAuxRow.boundingBox();
      const primaryBox = await primaryLane.boundingBox();
      const secondaryBox = await secondaryLane.boundingBox();
      const activityBox = await activityLane.boundingBox();
      const manualLaneBox = await manualLane.boundingBox();
      expect(heroBox?.y ?? Infinity).toBeLessThan(viewport.name === 'mobile' ? viewport.height * 0.38 : 280);
      expect(summaryCoreBox?.y ?? Infinity).toBeLessThan(summaryAuxBox?.y ?? 0);
      const summaryTypeScale = await page.evaluate(() => {
        const readFontSize = (testId: string) => {
          const element = document.querySelector(`[data-testid="${testId}"]`);
          return element ? Number.parseFloat(window.getComputedStyle(element).fontSize) : 0;
        };
        return {
          marketValue: readFontSize('portfolio-summary-market-value'),
          pnlValue: readFontSize('portfolio-summary-pnl-value'),
          cashValue: readFontSize('portfolio-summary-cash-value'),
        };
      });
      expect(summaryTypeScale.marketValue).toBeGreaterThan(summaryTypeScale.cashValue);
      expect(summaryTypeScale.pnlValue).toBeGreaterThan(summaryTypeScale.cashValue);
      const titleTypeScale = await page.evaluate(() => {
        const pageTitle = document.querySelector('[data-testid="portfolio-total-assets-card"] h1');
        const visibleSectionHeadings = Array.from(document.querySelectorAll('h2')).filter((element) => {
          const rect = element.getBoundingClientRect();
          return rect.width > 0 && rect.height > 0;
        });
        const pageTitleFontSize = pageTitle ? Number.parseFloat(window.getComputedStyle(pageTitle).fontSize) : 0;
        const maxSectionHeadingFontSize = Math.max(
          0,
          ...visibleSectionHeadings.map((element) => Number.parseFloat(window.getComputedStyle(element).fontSize)),
        );

        return { pageTitleFontSize, maxSectionHeadingFontSize };
      });
      expect(titleTypeScale.pageTitleFontSize).toBeGreaterThan(titleTypeScale.maxSectionHeadingFontSize);

      if (viewport.name === 'desktop') {
        const holdingsTable = page.getByRole('table', { name: '持仓研究账本' });
        const holdingsTableShell = holdingsTable.locator('xpath=ancestor::*[@data-terminal-primitive="dense-table"][1]');
        await expect(holdingsTable).toBeVisible();
        await expect(holdingsTable.getByText('持仓研究账本')).toHaveClass(/sr-only/);
        await expect(holdingsTableShell).toBeVisible();
        await expect(holdingsTableShell).toHaveCSS('overflow-x', 'auto');
        expect(primaryBox).not.toBeNull();
        expect(secondaryBox).not.toBeNull();
        expect(activityBox).not.toBeNull();
        expect(manualLaneBox).not.toBeNull();

        expect((primaryBox?.width ?? 0) / Math.max(1, secondaryBox?.width ?? 0)).toBeGreaterThan(1.35);
        expect((activityBox?.width ?? 0) / Math.max(1, manualLaneBox?.width ?? 0)).toBeGreaterThan(1.35);
        expect(Math.abs((primaryBox?.x ?? 0) - (activityBox?.x ?? 0))).toBeLessThanOrEqual(12);
        expect(Math.abs((secondaryBox?.x ?? 0) - (manualLaneBox?.x ?? 0))).toBeLessThanOrEqual(12);
        expect(Math.abs((primaryBox?.y ?? 0) - (secondaryBox?.y ?? 0))).toBeLessThanOrEqual(20);
        expect((manualLaneBox?.y ?? 0) - (secondaryBox?.y ?? 0)).toBeGreaterThan(40);
      } else {
        const holdingsBox = await holdingsPanel.boundingBox();
        const riskBox = await riskPanel.boundingBox();
        const activityPanelBox = await activityPanel.boundingBox();
        const manualBox = await setupBoundary.boundingBox();
        const wideElements = await classifyWideVisibleElements(page);
        const actualEscapes = wideElements.filter((entry) => entry?.classification === 'ACTUAL_LAYOUT_ESCAPE');

        expect(holdingsBox?.y ?? Infinity).toBeLessThan(riskBox?.y ?? 0);
        expect(riskBox?.y ?? Infinity).toBeLessThan(activityPanelBox?.y ?? 0);
        expect(activityPanelBox?.y ?? Infinity).toBeLessThan(manualBox?.y ?? 0);
        expect(actualEscapes).toEqual([]);
      }

      await expectVisibleTextPresent(page, requiredLedgerLabels);
      await expectVisibleTextAbsent(page, forbiddenLaunchLabels);
      const bodyText = await page.locator('body').innerText();
      expect(bodyText).not.toMatch(forbiddenInternalLeakagePattern);
      await expectNoHorizontalOverflow(page);
      expect(consoleErrors.filter((entry) => !entry.includes('500 (Internal Server Error)'))).toEqual([]);
      expect(pageErrors).toEqual([]);
      expect(harness.requests.count('GET', '/api/v1/portfolio/snapshot')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/portfolio/risk')).toBeGreaterThan(0);
      expect(harness.requests.calls.filter((entry) => entry.startsWith('POST '))).toEqual([]);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    });
  }

  test('keeps holdings ledger contained across the 768px breakpoint seam', async ({ page }) => {
    const breakpoints = [
      { width: 390, height: 844, denseTable: false },
      { width: 767, height: 900, denseTable: false },
      { width: 768, height: 900, denseTable: false },
      { width: 769, height: 900, denseTable: false },
      { width: 1024, height: 900, denseTable: true },
    ];

    for (const viewport of breakpoints) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await installPortfolioSmokeHarness(page);
      await page.goto('/zh/portfolio', { waitUntil: 'domcontentloaded' });
      await waitForPortfolioSurface(page);

      const holdingsPanel = page.getByTestId('portfolio-current-holdings-panel');
      await expect(holdingsPanel).toBeVisible({ timeout: 15_000 });

      const mobileLedger = page.getByTestId('portfolio-holdings-mobile-list');
      const holdingsTable = page.getByRole('table', { name: '持仓研究账本' });
      if (viewport.denseTable) {
        await expect(mobileLedger).toBeHidden();
        await expect(holdingsTable).toBeVisible();
        await expect(holdingsTable.locator('xpath=ancestor::*[@data-terminal-primitive="dense-table"][1]')).toHaveCSS('overflow-x', 'auto');
      } else {
        await expect(mobileLedger).toBeVisible();
        await expect(holdingsTable).toBeHidden();
      }

      const wideElements = await classifyWideVisibleElements(page);
      expect(wideElements.filter((entry) => entry?.classification === 'ACTUAL_LAYOUT_ESCAPE')).toEqual([]);
      await expectNoHorizontalOverflow(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  test('runs bounded portfolio scenario risk smoke inside the risk rail', async ({ page }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => pageErrors.push(error.message));

    await page.setViewportSize({ width: 1440, height: 1000 });
    const harness = await installPortfolioSmokeHarness(page);
    await page.goto('/zh/portfolio', { waitUntil: 'domcontentloaded' });
    await waitForPortfolioSurface(page);

    const riskPanel = page.getByTestId('portfolio-risk-card');
    const disclosure = page.getByTestId('portfolio-scenario-risk-disclosure');
    await expect(riskPanel).toContainText('查看压力情景');
    await expect(riskPanel).toContainText('默认折叠，只使用当前页面可见持仓。');
    await expect(disclosure).not.toHaveAttribute('open');

    const riskBox = await riskPanel.boundingBox();
    const disclosureBox = await disclosure.boundingBox();
    expect(riskBox).not.toBeNull();
    expect(disclosureBox).not.toBeNull();
    expect((disclosureBox?.x ?? 0) + 1).toBeGreaterThanOrEqual(riskBox?.x ?? Infinity);
    expect((disclosureBox?.y ?? 0) + 1).toBeGreaterThanOrEqual(riskBox?.y ?? Infinity);
    expect((disclosureBox?.x ?? 0) + (disclosureBox?.width ?? 0)).toBeLessThanOrEqual((riskBox?.x ?? 0) + (riskBox?.width ?? 0) + 1);

    const trigger = disclosure.locator('button').first();
    await expect(trigger).toHaveAttribute('aria-label', '展开 查看压力情景');
    await disclosure.scrollIntoViewIfNeeded();
    await trigger.evaluate((element: HTMLButtonElement) => element.click());
    await expect(disclosure).toHaveAttribute('open', '');

    await page.getByLabel('冲击幅度（%）').fill('-8');
    await page.getByRole('button', { name: '运行压力情景' }).click();

    const resultPanel = page.getByTestId('portfolio-scenario-risk-result');
    await expect(resultPanel).toBeVisible({ timeout: 10_000 });
    await expect(resultPanel).toContainText('预估影响');
    await expect(resultPanel).toContainText('覆盖范围与缺口会显式展示，不会替你推断缺失暴露。');
    await expect(resultPanel).toContainText('数据不足 / 需补充映射');
    await expect(resultPanel).toContainText('现金缓冲');
    await expect(resultPanel).toContainText('USD cash');
    await expect(resultPanel).toContainText('部分输入缺失');
    await expect(resultPanel).not.toContainText('theme_mapping_pending');
    await expect(resultPanel).not.toContainText('scenario_coverage_incomplete');
    expect(await resultPanel.innerText()).not.toMatch(forbiddenSnakeCaseTokenPattern);
    await expect(resultPanel).toContainText('仅做观察性推演，不改变当前组合状态。');
    await expect(resultPanel).toContainText('模型结果仅供观察，不作为行动依据。');
    await expect(resultPanel).not.toContainText(/不触发经纪商同步|不改动账务结果|不触发任何下单|模型结果不可作为仓位建议/);

    expect(harness.requests.count('POST', '/api/v1/portfolio/scenario-risk')).toBe(1);
    expect(harness.scenarioRiskPayloads).toHaveLength(1);
    expect(harness.scenarioRiskPayloads[0]).toEqual({
      asOf: '2026-04-15',
      positions: [
        {
          symbol: 'AAPL',
          weightPct: 100,
          marketValue: 1600,
          marketValueBase: 1600,
          bucketLabel: 'Launch Owner Main',
          currency: 'USD',
        },
      ],
      exposures: [],
      scenarioShocks: [
        {
          name: 'symbol_aapl_down_-8',
          shocks: {
            AAPL: {
              shockPct: -8,
            },
          },
        },
      ],
    });

    const sentPayloadText = JSON.stringify(harness.scenarioRiskPayloads[0]);
    expect(sentPayloadText).not.toMatch(/accountId|broker|providerRefresh|syncToken|order|trade|portfolioMutation/i);
    expect(walkKeys(harness.scenarioRiskPayloads[0])).not.toEqual(
      expect.arrayContaining(['accountId', 'broker', 'providerRefresh', 'syncToken', 'orderId', 'tradeId', 'portfolioMutation']),
    );

    const resultBox = await resultPanel.boundingBox();
    expect(resultBox).not.toBeNull();
    expect((resultBox?.x ?? 0) + 1).toBeGreaterThanOrEqual(riskBox?.x ?? Infinity);
    expect((resultBox?.x ?? 0) + (resultBox?.width ?? 0)).toBeLessThanOrEqual((riskBox?.x ?? 0) + (riskBox?.width ?? 0) + 1);

    await expectNoHorizontalOverflow(page);
    expect(consoleErrors.filter((entry) => !entry.includes('500 (Internal Server Error)'))).toEqual([]);
    expect(pageErrors).toEqual([]);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });

  test('qualifies operator import preview before explicit confirmation', async ({ page }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });
    page.on('pageerror', (error) => pageErrors.push(error.message));

    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.addInitScript(() => {
      window.sessionStorage.setItem('dsa-admin-surface-mode', 'admin');
    });
    const harness = await installPortfolioSmokeHarness(page, { operatorMode: true });
    await page.goto('/zh/portfolio', { waitUntil: 'domcontentloaded' });
    await waitForPortfolioSurface(page);

    await page.getByTestId('portfolio-next-action-panel').getByRole('button', { name: '同步数据' }).click();
    const tradeStation = page.getByTestId('portfolio-trade-station-card');
    await expect(tradeStation).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('portfolio-import-workflow-panel')).toBeVisible({ timeout: 15_000 });

    const importFile = {
      name: 'portfolio.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('symbol,market,trade_date,side,quantity,price,currency\nAAPL,us,2026-03-18,buy,2,101,USD\n'),
    };
    await page.getByLabel('选择导入文件').setInputFiles(importFile);
    await page.getByRole('button', { name: '预览导入' }).click();

    const previewCard = page.getByTestId('portfolio-import-preview-card');
    await expect(previewCard).toBeVisible({ timeout: 10_000 });
    await expect(previewCard).toContainText('导入预览');
    await expect(previewCard).toContainText('确认后会写入当前账户的真实流水');
    await expect(previewCard).toContainText('可导入');
    await expect(previewCard).toContainText('需修正');
    await expect(previewCard).toContainText('疑似重复');
    await expect(previewCard).toContainText('币种待确认');
    await expect(previewCard).toContainText('标的待确认');
    await expect(previewCard).toContainText('补充成交价格后重新预览');

    expect(harness.requests.count('POST', '/api/v1/portfolio/imports/parse')).toBe(1);
    expect(harness.requests.count('POST', '/api/v1/portfolio/imports/commit')).toBe(1);
    expect(harness.importCommitPayloads).toHaveLength(1);
    expect(harness.importCommitPayloads[0]).toMatchObject({ dryRun: true });

    await page.getByRole('button', { name: '确认导入' }).click();
    const commitCard = page.getByTestId('portfolio-import-preview-card');
    await expect(commitCard).toContainText('提交结果', { timeout: 10_000 });
    await expect(commitCard).toContainText('确认后会写入当前账户的真实流水');
    expect(harness.requests.count('POST', '/api/v1/portfolio/imports/commit')).toBe(2);
    expect(harness.importCommitPayloads.map((payload) => (payload as { dryRun?: boolean } | null)?.dryRun)).toEqual([true, false]);
    expect(harness.requests.count('GET', '/api/v1/portfolio/broker-connections')).toBeGreaterThan(0);
    expect(harness.requests.count('GET', '/api/v1/portfolio/snapshot')).toBeGreaterThan(0);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).not.toMatch(/mock-canary|synthetic_import|raw provider|broker-order|place-order/i);
    await expectNoHorizontalOverflow(page);
    expect(consoleErrors.filter((entry) => !entry.includes('500 (Internal Server Error)'))).toEqual([]);
    expect(pageErrors).toEqual([]);
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });
});
