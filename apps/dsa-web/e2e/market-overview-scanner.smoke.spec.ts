import type { Locator, Page } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

async function expectMinTapHeight(locator: Locator, minHeight: number) {
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(minHeight);
}

async function signIn(page: Page, redirectPath: string) {
  await page.goto(`/login?redirect=${encodeURIComponent(redirectPath)}`);
  await page.locator('#username').fill('wolfy-user');
  await page.locator('#password').fill('mock-password');
  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/v1/auth/login') && response.status() === 200),
    page.getByRole('button', { name: /sign in|登录继续|授权进入工作台|完成设置并登录/i }).click(),
  ]);
  await page.waitForURL(/\/$/);
  await page.goto(redirectPath);
}

async function installPartialTemperaturePayload(page: Page) {
  await page.route('**/api/v1/market/temperature', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        source: 'computed',
        sourceLabel: 'Mock model',
        updatedAt: '2026-05-02T09:00:00Z',
        asOf: '2026-05-02T09:00:00Z',
        freshness: 'mock',
        isFallback: false,
        confidence: 0.18,
        reliableInputCount: 1,
        fallbackInputCount: 3,
        excludedInputCount: 2,
        isReliable: false,
        scores: {
          liquidity: {
            value: 51,
            label: '中性',
            trend: 'stable',
            description: '流动性输入部分可用。',
          },
        },
      }),
    });
  });
}

async function openMarketOverviewEvidenceDetails(page: Page) {
  const disclosure = page.getByTestId('market-overview-evidence-disclosure');
  await expect(disclosure).toBeVisible();
  const toggle = disclosure.locator('button, [role="button"]').first();
  await expect(toggle).toHaveCount(1);
  await toggle.evaluate((element) => {
    (element as HTMLButtonElement).click();
  });
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(disclosure).toContainText(/市场方向摘要|支持证据|反证 \/ 风险/);
  return disclosure;
}

test.describe('scanner smoke', () => {
  test('scanner keeps controls visible without horizontal overflow', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await signIn(page, '/scanner');

    await expect(page.getByTestId('user-scanner-workspace')).toBeVisible();
    await expect(page.getByTestId('scanner-launch-bar')).toBeVisible();
    await expect(page.getByTestId('scanner-control-rail')).toHaveCount(0);
    await expect(page.getByTestId('scanner-sidebar')).toHaveCount(0);
    await page.getByTestId('scanner-scope-selector').getByRole('button', { name: /主题标的池|theme universe/i }).click();
    await page.getByRole('button', { name: /展开 高级参数|expand advanced controls/i }).click();
    await expect(page.getByTestId('scanner-theme-control')).toBeVisible();
    await expect(page.getByTestId('scanner-theme-select')).toBeVisible();
    await expect(page.getByTestId('scanner-run-button')).toBeVisible();
    await page.getByRole('button', { name: /更多扫描操作|more scanner actions/i }).click();
    const moreActions = page.getByTestId('scanner-more-actions-panel');
    await expect(moreActions).toBeVisible();
    await expect(moreActions.getByRole('button', { name: /导出 csv|export csv/i })).toBeVisible();
    await expect(moreActions.getByRole('button', { name: /复制全部代码|copy all symbols/i })).toBeVisible();
    await page.getByRole('button', { name: /更多扫描操作|more scanner actions/i }).click();
    await expect(moreActions).toHaveCount(0);

    await expect(page.getByTestId('scanner-result-table')).toBeVisible();
    const firstRow = page.getByTestId('scanner-ranked-row-NVDA');
    await expect(firstRow).toBeVisible();
    await expect(page.getByRole('button', { name: /^分析$|^analyze$/i }).first()).toBeVisible();
    await firstRow.getByRole('button', { name: /更多|more/i }).click();
    await expect(page.getByTestId('scanner-candidate-row-more-NVDA').getByRole('button', { name: /^复制$|^copy$/i })).toBeVisible();
    await firstRow.getByRole('button', { name: /详情|detail/i }).click();
    await expect(page.getByTestId('scanner-result-detail-NVDA').getByRole('button', { name: /^导出$|^export$/i })).toBeVisible();

    const candidateScrollRegion = page.getByTestId('scanner-candidate-scroll-region');
    await expect(candidateScrollRegion).toBeVisible();
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

    await expect(page.getByTestId('scanner-launch-bar')).toBeVisible();

    await page.goto('/watchlist');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('watchlist-page')).toBeVisible();
    await expect(page.getByTestId('watchlist-filter-grid')).toBeVisible();
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  });

  test('scanner and watchlist stay usable on mobile launch viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await signIn(page, '/scanner');

    await expect(page.getByTestId('user-scanner-workspace')).toBeVisible();
    await expect(page.getByTestId('scanner-ranked-list')).toBeVisible();
    await expect(page.getByTestId('scanner-candidate-scroll-region')).toBeVisible();
    await expectMinTapHeight(page.getByTestId('scanner-run-button'), 40);
    await expectMinTapHeight(page.getByRole('button', { name: /更多扫描操作|more scanner actions/i }), 40);
    await expectMinTapHeight(page.getByTestId('scanner-market-toggle').getByRole('button').first(), 40);
    await page.getByTestId('scanner-scope-selector').getByRole('button', { name: /主题标的池|theme universe/i }).click();
    await page.getByRole('button', { name: /展开 高级参数|expand advanced controls/i }).click();
    await expectMinTapHeight(page.getByTestId('scanner-theme-control').locator('.select-field__overlay'), 40);
    const firstRow = page.getByTestId('scanner-ranked-row-NVDA');
    await firstRow.getByRole('button', { name: /更多|more/i }).click();
    const morePanel = page.getByTestId('scanner-candidate-row-more-NVDA');
    await expectMinTapHeight(morePanel.getByRole('button', { name: /^分析$|^analyze$/i }), 40);
    await expectMinTapHeight(morePanel.getByRole('button', { name: /^复制$|^copy$/i }), 40);
    await expectMinTapHeight(morePanel.getByRole('button', { name: /导出|export/i }), 40);
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

    await page.goto('/watchlist');
    await page.waitForLoadState('domcontentloaded');
    await expect(page.getByTestId('watchlist-page')).toBeVisible();
    await expect(page.getByRole('heading', { name: /观察列表|watchlist/i })).toBeVisible();
    await expect(page.getByTestId('watchlist-filter-grid')).toBeVisible();
    await expect(page.getByTestId('watchlist-page')).toContainText(/观察列表|watchlist/i);
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  });

  test('scanner copy and export actions are clickable without console errors', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await signIn(page, '/scanner');

    const firstRow = page.getByTestId('scanner-ranked-row-NVDA');
    await firstRow.getByRole('button', { name: /更多|more/i }).click();
    const morePanel = page.getByTestId('scanner-candidate-row-more-NVDA');
    await morePanel.getByRole('button', { name: /^复制$|^copy$/i }).click();
    await expect(morePanel.getByRole('button', { name: /^已复制$|^copied$/i })).toBeVisible();

    await firstRow.getByRole('button', { name: /详情|detail/i }).click();
    const downloadPromise = page.waitForEvent('download');
    await page.getByTestId('scanner-result-detail-NVDA').getByRole('button', { name: /^导出$|^export$/i }).click();
    const download = await downloadPromise;
    expect(await download.suggestedFilename()).toContain('scanner_cn_');
  });
});

test.describe('market overview smoke', () => {
  test('market overview keeps top metrics visible with no ghost vertical overflow', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await signIn(page, '/zh/market-overview');

    await expect(page.getByTestId('market-overview-shell')).toBeVisible();
    await expect(page.getByTestId('market-overview-category-tabs')).toBeVisible();
    await expect(page.getByTestId('market-overview-hero-ribbon')).toBeVisible();
    await expect(page.getByTestId('market-decision-semantics-strip')).toBeVisible();
    await expect(page.getByTestId('market-overview-decision-readiness')).toBeVisible();
    await expect(page.getByTestId('market-overview-research-readiness-strip')).toBeVisible();
    await expect(page.getByTestId('market-decision-semantics-advice-boundary')).toBeVisible();
    await expect(page.getByTestId('market-overview-side-rail')).toBeVisible();
    await expect(page.getByTestId('market-overview-card-indices')).toBeVisible();
    await expect(page.getByTestId('market-overview-card-volatility')).toBeVisible();
    await expect(page.getByTestId('market-overview-card-fundsFlow')).toBeVisible();

    const viewport = page.viewportSize();
    expect(viewport).not.toBeNull();
    const criticalTopSurfaces = await Promise.all([
      page.getByTestId('market-overview-decision-readiness').boundingBox(),
      page.getByTestId('market-overview-category-tabs').boundingBox(),
      page.getByTestId('market-overview-hero-ribbon').boundingBox(),
    ]);
    criticalTopSurfaces.forEach((box) => {
      expect(box).not.toBeNull();
      expect(box?.y ?? 0).toBeLessThan((viewport?.height ?? 0));
      expect((box?.y ?? 0) + Math.min(box?.height ?? 0, 48)).toBeLessThanOrEqual((viewport?.height ?? 0) - 8);
    });
    const verdictBox = await page.getByTestId('market-overview-decision-readiness').boundingBox();
    const readinessStripBox = await page.getByTestId('market-overview-research-readiness-strip').boundingBox();
    expect(verdictBox).not.toBeNull();
    expect(readinessStripBox).not.toBeNull();
    expect((verdictBox?.y ?? Number.POSITIVE_INFINITY) < (readinessStripBox?.y ?? Number.NEGATIVE_INFINITY)).toBe(true);
    const actionabilityStrip = page.getByTestId('market-intelligence-actionability-strip');
    if (await actionabilityStrip.count()) {
      const actionabilityStripBox = await actionabilityStrip.boundingBox();
      expect(actionabilityStripBox).not.toBeNull();
      expect((verdictBox?.y ?? Number.POSITIVE_INFINITY) < (actionabilityStripBox?.y ?? Number.NEGATIVE_INFINITY)).toBe(true);
    }
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

    const shellLayout = await page.evaluate(() => {
      const shell = document.querySelector('[data-testid="market-overview-shell"]') as HTMLElement | null;
      const mainGrid = document.querySelector('[data-testid="market-overview-main-grid"]') as HTMLElement | null;
      if (!shell || !mainGrid) {
        return null;
      }

      return {
        shellScrollHeight: shell.scrollHeight,
        shellClientHeight: shell.clientHeight,
        trailingGap: shell.scrollHeight - (mainGrid.offsetTop + mainGrid.offsetHeight),
      };
    });
    expect(shellLayout).not.toBeNull();
    expect(shellLayout?.shellScrollHeight ?? 0).toBeGreaterThanOrEqual(shellLayout?.shellClientHeight ?? 0);
    expect(shellLayout?.trailingGap ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(96);

    const evidenceDetails = await openMarketOverviewEvidenceDetails(page);
    await expect(evidenceDetails).toContainText(/市场方向摘要/);
    await expect(evidenceDetails).toContainText(/支持证据/);
    await expect(evidenceDetails).toContainText(/反证 \/ 风险/);

    const rails = await Promise.all([
      page.getByTestId('market-overview-primary-rail').boundingBox(),
      page.getByTestId('market-overview-side-rail').boundingBox(),
    ]);
    expect(rails[0]).not.toBeNull();
    expect(rails[1]).not.toBeNull();
    expect((rails[1]?.width ?? 0) < (rails[0]?.width ?? 0)).toBe(true);

    const exportSummaryButton = page.getByTestId('market-overview-export-summary');
    await expect(exportSummaryButton).toBeVisible();
    await expect(exportSummaryButton).toBeEnabled();
    await exportSummaryButton.click();
    await expect(exportSummaryButton).toContainText(/已复制摘要|summary copied/i);

    const copiedSummary = await page.evaluate(() => (window as Window & { __pwClipboardText?: string }).__pwClipboardText || '');
    expect(copiedSummary).toContain('市场总览');
    expect(copiedSummary).toContain('市场温度');
    expect(copiedSummary).toContain('市场解读');
    await expect(await page.locator('body').innerText()).not.toMatch(
      /sourceAuthorityAllowed|scoreContributionAllowed|observationOnly|reasonCodes?|reasonFamilies|schemaVersion|fallback_static|synthetic_fixture|rotation_non_scoring_or_taxonomy_only|Rotation Non Scoring Or Taxonomy Only/i,
    );
  });

  test('market overview degrades partial temperature payload without blanking', async ({ page }) => {
    await installPartialTemperaturePayload(page);

    const viewports = [
      { width: 1440, height: 1000 },
      { width: 390, height: 844 },
    ];

    for (const [index, viewport] of viewports.entries()) {
      await page.setViewportSize(viewport);
      if (index === 0) {
        await signIn(page, '/zh/market-overview');
      } else {
        await page.goto('/zh/market-overview');
        await page.waitForLoadState('domcontentloaded');
      }

      await expect(page.getByTestId('market-overview-shell')).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('market-overview-decision-readiness')).toContainText(/暂不形成方向结论|等待数据完成后再判断|仅观察/);
      await expect(page.getByTestId('market-overview-decision-readiness')).toContainText(/当前信号置信度较低，仅供观察。|部分数据暂不可用，当前评分已暂停。|数据更新中，稍后将自动刷新。/);
      await expect(page.getByTestId('market-overview-research-readiness-strip')).toBeVisible();
      await expect(page.getByTestId('market-decision-semantics-advice-boundary')).toContainText(/暂不形成方向结论|等待数据完成后再判断/);
      const verdictBox = await page.getByTestId('market-overview-decision-readiness').boundingBox();
      const readinessStripBox = await page.getByTestId('market-overview-research-readiness-strip').boundingBox();
      expect(verdictBox).not.toBeNull();
      expect(readinessStripBox).not.toBeNull();
      expect((verdictBox?.y ?? Number.POSITIVE_INFINITY) < (readinessStripBox?.y ?? Number.NEGATIVE_INFINITY)).toBe(true);
      const actionabilityStrip = page.getByTestId('market-intelligence-actionability-strip');
      if (await actionabilityStrip.count()) {
        const actionabilityStripBox = await actionabilityStrip.boundingBox();
        expect(actionabilityStripBox).not.toBeNull();
        expect((verdictBox?.y ?? Number.POSITIVE_INFINITY) < (actionabilityStripBox?.y ?? Number.NEGATIVE_INFINITY)).toBe(true);
      }
      const evidenceDetails = await openMarketOverviewEvidenceDetails(page);
      await expect(evidenceDetails).toContainText(/当前市场：证据不足|Current market: Evidence insufficient/);
      await expect(evidenceDetails).toContainText(/不支持强方向判断/);
      await expect(evidenceDetails).toContainText(/备用或代理证据偏多/);
      await expect(evidenceDetails).not.toContainText('N/A');
      await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
      await expect(await page.locator('body').innerText()).not.toMatch(/raw|payload|rotation_non_scoring_or_taxonomy_only|Rotation Non Scoring Or Taxonomy Only/i);
    }
  });
});
