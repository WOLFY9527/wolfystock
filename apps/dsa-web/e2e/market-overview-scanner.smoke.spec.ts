import type { Locator, Page } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';
import { captureShellVisualEvidence } from './fixtures/shellVisualEvidence';

const marketOverviewRequestPathPattern = /^\/api\/v1\/(?:market-overview\/|market\/(?:temperature|briefing|futures|cn-short-sentiment|professional-data-capabilities|regime-read-model|decision-cockpit))/;

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
  await page.waitForURL((url) => url.pathname === '/' || url.pathname === redirectPath);
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
        regimeSummary: {
          headline: '风险偏好改善但仍需确认',
          detail: '主线仍可观察，但缺少足够评分级确认。',
          riskLevel: 'medium',
        },
        marketRegimeSynthesis: {
          regime: 'risk_on_liquidity_expansion',
          summary: '流动性改善，风险偏好修复。',
          confidence: 0.34,
          confidenceLabel: 'low',
          topDrivers: [
            { key: 'indices:SPX', label: '标普500' },
          ],
          counterEvidence: [
            { key: 'rates:US10Y', label: 'US10Y' },
          ],
          dataGaps: [
            { key: 'breadth_health', label: 'Breadth health' },
          ],
        },
        marketDecisionSemantics: {
          version: 'market_decision_semantics_v1',
          posture: 'neutral',
          postureConfidence: {
            value: 42,
            label: 'low',
            capReasons: ['insufficient_score_grade_evidence'],
          },
          exposureBias: 'risk_on_watch',
          directionReadiness: {
            status: 'partial_context_only',
            confidenceLabel: 'low',
            scoreGradePillars: {
              count: 1,
              items: [
                { pillar: 'official_macro_rates_volatility', label: 'Official macro/rates/volatility', reasonCode: 'score_grade_evidence' },
              ],
            },
            observationOnlyPillars: {
              count: 2,
              items: [
                { pillar: 'rotation_or_risk_participation', label: 'Rotation/risk participation', reasonCode: 'observation_only_evidence' },
                { pillar: 'liquidity_conditions', label: 'Liquidity/conditions', reasonCode: 'fallback_or_proxy_evidence' },
              ],
            },
            missingPillars: {
              count: 1,
              items: [
                { pillar: 'breadth_health', label: 'Breadth health', reasonCode: 'missing_scoring_evidence' },
              ],
            },
            blockingReasons: ['insufficient_score_grade_evidence'],
            claimBoundaries: [
              { claim: 'market_direction_readiness_context', allowed: false, reasonCode: 'partial_context_only' },
            ],
            notInvestmentAdvice: true,
          },
          styleTilts: [
            { tilt: 'liquidity_beta_watch', label: 'Liquidity beta watch', detail: 'Risk-on regime is still only a watch.' },
          ],
          confirmationSignals: [
            { signal: 'regime_alignment', detail: 'Primary regime remains observation-only.' },
          ],
          invalidationTriggers: [
            { trigger: 'breadth_stays_thin', detail: 'Breadth must improve before a stronger direction call.' },
          ],
          counterEvidence: [
            { surface: 'market_regime_synthesis', key: 'rates:US10Y', label: 'US10Y', detail: 'Rates pressure remains a contradiction.' },
          ],
          dataGaps: [
            { surface: 'market_regime_synthesis', key: 'breadth_health', label: 'Breadth health', reason: 'missing_scoring_evidence' },
          ],
          claimBoundaries: [
            { claim: 'observational_posture_watch', allowed: true, reasonCode: 'watch_only_language', detail: 'Only observational posture watch language is allowed.' },
            { claim: 'direct_trade_action', allowed: false, reasonCode: 'not_investment_advice', detail: 'No execution language.' },
          ],
          notInvestmentAdvice: true,
        },
        scores: {
          overall: {
            value: 49,
            label: '中性',
            trend: 'stable',
            description: '主线可观察，但当前仍缺少足够评分级确认。',
          },
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

async function expectWatchlistLaunchSurface(page: Page) {
  await expect(page.getByTestId('watchlist-page')).toBeVisible();
  await expect(page.locator('[data-testid="watchlist-filter-grid"], [data-testid="watchlist-compact-empty-state"]')).toBeVisible();
}

async function expectMarketOverviewDenseQuotesFit(page: Page) {
  const overflowingRows = await page.evaluate(() => {
    const rows = Array.from(document.querySelectorAll('[data-testid="market-overview-dense-quote-item"]')) as HTMLElement[];
    return rows.map((row, index) => {
      const rowRect = row.getBoundingClientRect();
      const childSpill = Array.from(row.querySelectorAll<HTMLElement>(
        [
          '[data-testid="market-overview-quote-metadata"]',
          '[data-testid="market-overview-dense-quote-sparkline"]',
          '[data-testid="market-overview-quote-value"]',
          '[data-testid="market-overview-quote-change"]',
        ].join(','),
      )).filter((child) => {
        const childRect = child.getBoundingClientRect();
        if (childRect.width === 0 && childRect.height === 0) {
          return false;
        }
        return childRect.left < rowRect.left - 1 || childRect.right > rowRect.right + 1;
      }).map((child) => child.getAttribute('data-testid'));
      return {
        index,
        rowWidth: Math.round(rowRect.width),
        scrollDelta: Math.round(row.scrollWidth - row.clientWidth),
        childSpill,
      };
    }).filter((row) => row.scrollDelta > 1 || row.childSpill.length > 0);
  });

  expect(overflowingRows).toEqual([]);
}

async function expectNoMarketOverviewProxyLabelLeaks(page: Page) {
  const consumerText = await page.evaluate(() => {
    const visibleText = document.body.innerText || '';
    const attributeText = Array.from(document.querySelectorAll<HTMLElement>('[title], [aria-label], [alt]'))
      .map((element) => [
        element.getAttribute('title'),
        element.getAttribute('aria-label'),
        element.getAttribute('alt'),
      ].filter(Boolean).join(' '))
      .join(' ');
    return `${visibleText} ${attributeText}`;
  });

  expect(consumerText).toContain('ETF 资金流指标');
  expect(consumerText).toContain('机构压力指标');
  expect(consumerText).toContain('行业广度指标');
  expect(consumerText).not.toMatch(/ETF flow proxy|Institutional pressure proxy|Industry breadth proxy|\bproxy\b/i);
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
    await expectWatchlistLaunchSurface(page);
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await captureShellVisualEvidence(page, 'watchlist', { width: 1440, height: 1000 });
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
    await expectWatchlistLaunchSurface(page);
    await expect(page.getByRole('heading', { name: /观察列表|watchlist/i })).toBeVisible();
    await expect(page.getByTestId('watchlist-page')).toContainText(/观察列表|watchlist/i);
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await captureShellVisualEvidence(page, 'watchlist', { width: 390, height: 844 });
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
  test('market overview request fan-out stays bounded across initial load, idle, and reload', async ({ page }) => {
    const apiRequests: string[] = [];
    page.on('request', (request) => {
      const url = new URL(request.url());
      if (url.pathname.startsWith('/api/v1/')) {
        apiRequests.push(`${request.method()} ${url.pathname}`);
      }
    });

    await page.setViewportSize({ width: 1440, height: 1000 });
    await signIn(page, '/zh/market-overview');
    apiRequests.length = 0;

    await page.goto('/zh/market-overview');
    await expect(page.getByTestId('market-overview-shell')).toBeVisible();
    await expect(page.getByTestId('market-overview-card-indices')).toBeVisible();
    await expect(page.getByTestId('market-overview-decision-readiness')).toBeVisible();
    await expect.poll(() => apiRequests.filter((entry) => (
      entry === 'GET /api/v1/market-overview/macro'
      || entry === 'GET /api/v1/market/futures'
      || entry === 'GET /api/v1/market/cn-short-sentiment'
    )).length).toBeGreaterThanOrEqual(3);

    const initialMarketRequests = apiRequests.filter((entry) => {
      const [, path] = entry.split(' ');
      return entry.startsWith('GET ') && marketOverviewRequestPathPattern.test(path);
    });
    expect(initialMarketRequests.length).toBeGreaterThanOrEqual(8);
    expect(initialMarketRequests.length).toBeLessThanOrEqual(16);
    expect(initialMarketRequests).toEqual(expect.arrayContaining([
      'GET /api/v1/market-overview/indices',
      'GET /api/v1/market-overview/volatility',
      'GET /api/v1/market-overview/funds-flow',
      'GET /api/v1/market/temperature',
      'GET /api/v1/market/regime-read-model',
      'GET /api/v1/market-overview/macro',
      'GET /api/v1/market/futures',
      'GET /api/v1/market/cn-short-sentiment',
    ]));

    const afterInitialCount = apiRequests.length;
    await page.waitForTimeout(1200);
    const idleMarketRequests = apiRequests.slice(afterInitialCount).filter((entry) => {
      const [, path] = entry.split(' ');
      return entry.startsWith('GET ') && marketOverviewRequestPathPattern.test(path);
    });
    expect(idleMarketRequests).toEqual([]);

    apiRequests.length = 0;
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.getByTestId('market-overview-shell')).toBeVisible();
    await expect(page.getByTestId('market-overview-card-indices')).toBeVisible();
    const reloadMarketRequests = apiRequests.filter((entry) => {
      const [, path] = entry.split(' ');
      return entry.startsWith('GET ') && marketOverviewRequestPathPattern.test(path);
    });
    expect(reloadMarketRequests.length).toBeLessThanOrEqual(initialMarketRequests.length + 2);
  });

  test('market overview keeps top metrics visible with no ghost vertical overflow', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await signIn(page, '/zh/market-overview');

    await expect(page.getByTestId('market-overview-shell')).toBeVisible();
    await expect(page.getByTestId('market-overview-category-tabs')).toBeVisible();
    await expect(page.getByTestId('market-overview-hero-ribbon')).toBeVisible();
    await expect(page.getByTestId('market-decision-semantics-strip')).toBeVisible();
    await expect(page.getByTestId('market-overview-decision-readiness')).toBeVisible();
    await expect(page.getByTestId('market-overview-research-readiness-strip')).toHaveCount(0);
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
    const mainGridBox = await page.getByTestId('market-overview-main-grid').boundingBox();
    const visualEvidenceBox = await page.getByTestId('market-overview-visual-evidence-strip').boundingBox();
    expect(verdictBox).not.toBeNull();
    expect(mainGridBox).not.toBeNull();
    expect(visualEvidenceBox).not.toBeNull();
    expect((verdictBox?.y ?? Number.POSITIVE_INFINITY) < (mainGridBox?.y ?? Number.NEGATIVE_INFINITY)).toBe(true);
    expect((mainGridBox?.y ?? Number.POSITIVE_INFINITY) < (visualEvidenceBox?.y ?? Number.NEGATIVE_INFINITY)).toBe(true);
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

    const shellLayout = await page.evaluate(() => {
      const shell = document.querySelector('[data-testid="market-overview-shell"]') as HTMLElement | null;
      const mainGrid = document.querySelector('[data-testid="market-overview-main-grid"]') as HTMLElement | null;
      const visualEvidence = document.querySelector('[data-testid="market-overview-visual-evidence-strip"]') as HTMLElement | null;
      if (!shell || !mainGrid || !visualEvidence) {
        return null;
      }

      return {
        shellScrollHeight: shell.scrollHeight,
        shellClientHeight: shell.clientHeight,
        visualEvidenceTop: visualEvidence.offsetTop,
        mainGridBottom: mainGrid.offsetTop + mainGrid.offsetHeight,
        trailingGap: shell.scrollHeight - (visualEvidence.offsetTop + visualEvidence.offsetHeight),
      };
    });
    expect(shellLayout).not.toBeNull();
    expect(shellLayout?.shellScrollHeight ?? 0).toBeGreaterThanOrEqual(shellLayout?.shellClientHeight ?? 0);
    expect(shellLayout?.visualEvidenceTop ?? 0).toBeGreaterThanOrEqual(shellLayout?.mainGridBottom ?? Number.POSITIVE_INFINITY);
    expect(shellLayout?.trailingGap ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(96);
    await expect(await page.locator('body').innerText()).not.toMatch(
      /sourceAuthorityAllowed|scoreContributionAllowed|observationOnly|reasonCodes?|reasonFamilies|schemaVersion|fallback_static|synthetic_fixture|rotation_non_scoring_or_taxonomy_only|Rotation Non Scoring Or Taxonomy Only|研究就绪度|市场研判可用性|证据覆盖\s*\d+\/\d+|来源级别|高授权|观察级|评分级|缺口\s*\d+|更高授权|限制因素|回退|缓存|仅供界面演示|保持界面结构|等待真实行情源/i,
    );

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
  });

  test('market overview keeps the top summary cards wide and balanced across desktop viewports', async ({ page }) => {
    const desktopViewports = [
      { width: 1440, height: 1000 },
      { width: 1728, height: 1117 },
    ];

    for (const [index, viewport] of desktopViewports.entries()) {
      await page.setViewportSize(viewport);
      if (index === 0) {
        await signIn(page, '/zh/market-overview');
      } else {
        await page.goto('/zh/market-overview');
        await page.waitForLoadState('domcontentloaded');
      }

      await expect(page.getByTestId('market-overview-shell')).toBeVisible();
      await expect(page.getByTestId('market-overview-card-indices')).toBeVisible();
      await expect(page.getByTestId('market-overview-card-volatility')).toBeVisible();
      await expect(page.getByTestId('market-overview-card-fundsFlow')).toBeVisible();
      await expectNoMarketOverviewProxyLabelLeaks(page);

      const heroRowLayout = await page.evaluate(() => {
        const row = document.querySelector('[data-row-id="all-hero"]') as HTMLElement | null;
        const cards = [
          document.querySelector('[data-testid="market-overview-card-indices"]') as HTMLElement | null,
          document.querySelector('[data-testid="market-overview-card-volatility"]') as HTMLElement | null,
          document.querySelector('[data-testid="market-overview-card-fundsFlow"]') as HTMLElement | null,
        ];
        if (!row || cards.some((card) => !card)) {
          return null;
        }

        const rowRect = row.getBoundingClientRect();
        const cardRects = cards.map((card) => (card as HTMLElement).getBoundingClientRect());
        const widths = cardRects.map((rect) => rect.width);
        return {
          rowTop: rowRect.top,
          widths,
          topOffsets: cardRects.map((rect) => Math.round(rect.top - rowRect.top)),
          leftGap: Math.round(cardRects[0].left - rowRect.left),
          rightGap: Math.round(rowRect.right - cardRects[2].right),
        };
      });

      expect(heroRowLayout).not.toBeNull();
      const widths = heroRowLayout?.widths || [];
      expect(widths).toHaveLength(3);
      expect(Math.max(...widths) - Math.min(...widths)).toBeLessThanOrEqual(6);
      expect(heroRowLayout?.topOffsets.every((offset) => Math.abs(offset) <= 2)).toBe(true);
      expect(heroRowLayout?.leftGap ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(2);
      expect(heroRowLayout?.rightGap ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(2);
      await expectMarketOverviewDenseQuotesFit(page);
      await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    }
  });

  test('market overview keeps the default mobile viewport single-column with no overflow', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await signIn(page, '/zh/market-overview');

    await expect(page.getByTestId('market-overview-shell')).toBeVisible();
    await expect(page.getByTestId('market-overview-decision-readiness')).toBeVisible();
    await expect(page.getByTestId('market-overview-card-indices')).toBeVisible();
    await expect(page.getByTestId('market-overview-card-volatility')).toBeVisible();
    await expect(page.getByTestId('market-overview-card-fundsFlow')).toBeVisible();
    await expectNoMarketOverviewProxyLabelLeaks(page);

    const mobileLayout = await page.evaluate(() => {
      const row = document.querySelector('[data-row-id="all-hero"]') as HTMLElement | null;
      const cards = Array.from(document.querySelectorAll('[data-row-id="all-hero"] [data-testid^="market-overview-card-"]')) as HTMLElement[];
      if (!row || cards.length < 3) {
        return null;
      }

      const rowRect = row.getBoundingClientRect();
      const cardRects = cards.slice(0, 3).map((card) => card.getBoundingClientRect());
      return {
        rowWidth: Math.round(rowRect.width),
        widths: cardRects.map((rect) => Math.round(rect.width)),
        topOffsets: cardRects.map((rect) => Math.round(rect.top - rowRect.top)),
      };
    });

    expect(mobileLayout).not.toBeNull();
    expect(mobileLayout?.topOffsets[1] ?? 0).toBeGreaterThan(mobileLayout?.topOffsets[0] ?? 0);
    expect(mobileLayout?.topOffsets[2] ?? 0).toBeGreaterThan(mobileLayout?.topOffsets[1] ?? 0);
    mobileLayout?.widths.forEach((width) => {
      expect(Math.abs(width - (mobileLayout?.rowWidth ?? width))).toBeLessThanOrEqual(2);
    });
    await expectMarketOverviewDenseQuotesFit(page);
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
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
      await expect(page.getByTestId('market-overview-decision-readiness')).toContainText(/偏强观察|中性观察|偏弱观察|数据不足/);
      await expect(page.getByTestId('market-overview-decision-readiness')).toContainText('现在市场发生了什么');
      await expect(page.getByTestId('market-overview-decision-readiness')).toContainText('为什么');
      await expect(page.getByTestId('market-overview-decision-readiness')).toContainText('证据覆盖 / 置信度');
      await expect(page.getByTestId('market-overview-decision-readiness')).toContainText('接下来观察什么');
      await expect(page.getByTestId('market-overview-decision-readiness')).toContainText('有限');
      await expect(page.getByTestId('market-overview-key-drivers')).toContainText(/指数 \/ 宽度|波动率|利率 \/ 宏观|流动性|行业 \/ 轮动/);
      await expect(page.getByTestId('market-overview-next-observation')).toContainText(/下一观察/);
      await expect(page.getByTestId('market-overview-decision-readiness')).toContainText(/缺少充分证据|待补/);
      await expect(page.getByTestId('market-overview-research-readiness-strip')).toHaveCount(0);
      await expect(page.getByTestId('market-decision-semantics-advice-boundary')).toContainText(/偏强观察|中性观察|偏弱观察|数据不足/);
      const verdictBox = await page.getByTestId('market-overview-decision-readiness').boundingBox();
      const mainGridBox = await page.getByTestId('market-overview-main-grid').boundingBox();
      expect(verdictBox).not.toBeNull();
      expect(mainGridBox).not.toBeNull();
      expect((verdictBox?.y ?? Number.POSITIVE_INFINITY) < (mainGridBox?.y ?? Number.NEGATIVE_INFINITY)).toBe(true);
      const evidenceDetails = await openMarketOverviewEvidenceDetails(page);
      await expect(evidenceDetails).toContainText(/当前市场：证据不足|Current market: Evidence insufficient/);
      await expect(evidenceDetails).toContainText(/支持证据|反证 \/ 风险|下一步观察/);
      await expect(evidenceDetails).not.toContainText('N/A');
      await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
      await expect(await page.locator('body').innerText()).not.toMatch(/raw|payload|partial_context_only|reasonCode|sourceAuthorityAllowed|scoreContributionAllowed|rotation_non_scoring_or_taxonomy_only|Rotation Non Scoring Or Taxonomy Only/i);
    }
  });
});
