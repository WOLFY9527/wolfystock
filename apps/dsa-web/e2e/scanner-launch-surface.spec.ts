import type { Page } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

const forbiddenTradingAction = /买入按钮|建议买入|建议卖出|立即交易|下单|提交订单|订单载荷|开仓|平仓|加仓|减仓|place order|submit order|buy now|sell now/i;
const rawPayloadPattern = /raw\s+(payload|response)|provider\s+payload|debug\s+payload|payload_json|raw_provider_payload/i;
const retryNoCandidateRun = {
  id: 11,
  market: 'cn',
  profile: 'cn_preopen_v1',
  profile_label: 'A-share Pre-open v1',
  status: 'empty',
  run_at: '2026-05-02T09:00:00Z',
  completed_at: '2026-05-02T09:00:00Z',
  watchlist_date: '2026-05-02',
  trigger_mode: 'manual',
  universe_name: 'cn_a_liquid_watchlist_v1',
  shortlist_size: 0,
  universe_size: 320,
  preselected_size: 72,
  evaluated_size: 48,
  source_summary: 'Mocked scanner payload',
  headline: 'Mock scanner empty result for retry verification',
  universe_notes: [],
  scoring_notes: [],
  universe_type: 'default',
  theme_id: null,
  theme_label: null,
  requested_symbols_count: 0,
  accepted_symbols_count: 0,
  rejected_symbols: [],
  diagnostics: {
    coverage_summary: {
      input_universe_size: 320,
      eligible_after_universe_fetch: 300,
      eligible_after_liquidity_filter: 244,
      eligible_after_data_availability_filter: 192,
      ranked_candidate_count: 48,
      shortlisted_count: 0,
      excluded_total: 48,
      excluded_by_reason: [{ reason: 'below_threshold', label: 'Screening condition not met', count: 48 }],
      likely_bottleneck: 'screening_threshold',
      likely_bottleneck_label: 'Screening threshold',
    },
    universe_selection: {
      universe_type: 'default',
      theme_id: null,
      theme_label: null,
      requested_symbols_count: 0,
      accepted_symbols_count: 0,
      rejected_symbols: [],
      universe_notes: [],
    },
  },
  notification: {
    attempted: false,
    status: 'not_attempted',
    success: null,
    channels: [],
    message: null,
    report_path: null,
    sent_at: null,
  },
  failure_reason: null,
  summary: {
    universe_count: 320,
    submitted_count: 320,
    evaluated_count: 48,
    selected_count: 0,
    rejected_count: 48,
    data_failed_count: 0,
    skipped_count: 0,
    error_count: 0,
    limited_by_result_cap: false,
  },
  shortlist: [],
  selected: [],
  candidates: [],
};
const previewNoCandidateRun = {
  ...retryNoCandidateRun,
  headline: 'Mock scanner no-candidate result with preview row',
  summary: {
    ...retryNoCandidateRun.summary,
    evaluated_count: 3,
    rejected_count: 3,
  },
  candidates: [
    {
      symbol: 'MARA',
      name: 'MARA Holdings',
      rank: 1,
      status: 'rejected',
      score: 61,
      provider: 'mock',
      reason: 'below liquidity threshold',
      failed_rules: ['below_liquidity_threshold'],
      missing_fields: [],
      metrics: { return20d: 3.1, trend: 8 },
    },
  ],
};

async function assertScannerLaunchViewport(page: Page, viewport: { width: number; height: number }) {
  await page.setViewportSize(viewport);
  await page.route('**/api/v1/auth/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        authEnabled: true,
        loggedIn: true,
        passwordSet: true,
        passwordChangeable: true,
        setupState: 'enabled',
        currentUser: {
          id: 'user-1',
          username: 'wolfy-user',
          displayName: 'Wolfy User',
          role: 'user',
          isAdmin: false,
          isAuthenticated: true,
          transitional: false,
          authEnabled: true,
        },
      }),
    });
  });
  await page.goto('/zh/scanner');
  await page.waitForLoadState('domcontentloaded');

  const launchSummary = page.getByTestId('scanner-status-strip');
  const conclusionBand = page.getByTestId('scanner-conclusion-band');
  const candidateRegion = page.getByTestId('scanner-candidate-scroll-region');
  const firstCandidate = page.getByTestId('scanner-result-row-NVDA');
  const denseShell = page.getByTestId('scanner-launch-bar');
  const commandPanel = page.getByTestId('scanner-command-panel');
  const commandBar = page.getByTestId('scanner-command-bar');
  const resultsPanel = page.getByTestId('scanner-results-panel');
  const summaryRail = page.getByTestId('scanner-summary-rail');
  const resultTable = page.getByTestId('scanner-result-table');
  const inlineDetailPanel = page.getByTestId('scanner-inline-detail-panel');
  const detailRail = page.getByTestId('scanner-detail-rail');
  const focusCandidate = page.getByTestId('scanner-result-detail-NVDA');

  await expect(page.getByTestId('user-scanner-workspace')).toBeVisible({ timeout: 15_000 });
  await expect(denseShell).toBeVisible();
  await expect(commandPanel).toBeVisible();
  await expect(commandBar).toBeVisible();
  await expect(resultsPanel).toBeVisible();
  await expect(summaryRail).toBeVisible();
  await expect(conclusionBand).toBeVisible();
  await expect(launchSummary).toBeVisible();
  await expect(conclusionBand).toContainText(/当前候选|Current candidate|证据不足|Evidence insufficient|等待扫描|Waiting for a scan/);
  await expect(launchSummary).toContainText(/最佳候选|Best candidate/);
  await expect(launchSummary).toContainText(/候选分布|Candidate mix/);
  await expect(launchSummary).toContainText(/信号状态|Signal state/);
  await expect(candidateRegion).toBeVisible();
  await expect(resultTable).toBeVisible();
  await expect(firstCandidate).toBeVisible();
  await expect(firstCandidate).toContainText('NVDA');
  await expect(summaryRail).toContainText(/工作区摘要|Workspace summary/);
  await expect(summaryRail).toContainText(/候选|Candidates/);
  await expect(summaryRail).toContainText(/淘汰|Rejected/);
  await expect(summaryRail).toContainText(/数据受限|Limited/);
  if (await detailRail.count()) {
    await expect(detailRail).toBeVisible();
  } else {
    await expect(inlineDetailPanel).toBeVisible();
  }
  await expect(focusCandidate).toContainText(/当前信号|Why now/);
  await expect(focusCandidate).toContainText(/候选说明|Candidate notes/);
  await expect(page.getByTestId('scanner-control-rail')).toHaveCount(0);
  await expect(page.getByTestId('scanner-sidebar')).toHaveCount(0);
  await expect(page.getByTestId('scanner-bento-grid')).toHaveCount(0);
  await expect(page.getByTestId('scanner-card-wall')).toHaveCount(0);

  const launchBox = await commandBar.boundingBox();
  const commandPanelBox = await commandPanel.boundingBox();
  const conclusionBox = await conclusionBand.boundingBox();
  const summaryBox = await launchSummary.boundingBox();
  const candidateRegionBox = await candidateRegion.boundingBox();
  const resultBox = await denseShell.boundingBox();
  const resultsPanelBox = await resultsPanel.boundingBox();
  const summaryRailBox = await summaryRail.boundingBox();
  const viewportWidth = viewport.width;
  expect(launchBox).not.toBeNull();
  expect(commandPanelBox).not.toBeNull();
  expect(conclusionBox).not.toBeNull();
  expect(summaryBox).not.toBeNull();
  expect(candidateRegionBox).not.toBeNull();
  expect(resultBox).not.toBeNull();
  expect(resultsPanelBox).not.toBeNull();
  expect(summaryRailBox).not.toBeNull();
  expect(summaryBox?.y ?? 0).toBeGreaterThan(conclusionBox?.y ?? 0);
  expect(candidateRegionBox?.y ?? 0).toBeGreaterThan(summaryBox?.y ?? 0);
  expect(candidateRegionBox?.y ?? 0).toBeGreaterThan((launchBox?.y ?? 0) - 1);
  if (viewportWidth >= 768) {
    const firstRowLimit = viewportWidth >= 1024 ? 0.78 : 1.0;
    expect(candidateRegionBox?.y ?? 0).toBeLessThan(viewport.height * firstRowLimit);
  }
  if (viewportWidth >= 1024) {
    expect(resultBox?.width ?? 0).toBeGreaterThan(viewportWidth * 0.62);
    expect(summaryRailBox?.x ?? 0).toBeGreaterThan((resultBox?.x ?? 0) + (resultBox?.width ?? 0) - 1);
    expect(summaryRailBox?.width ?? 0).toBeGreaterThan(220);
  } else {
    expect(resultBox?.width ?? 0).toBeGreaterThan(viewportWidth * 0.72);
    expect(summaryRailBox?.y ?? 0).toBeGreaterThan((resultBox?.y ?? 0) + (resultBox?.height ?? 0) - 1);
  }

  const secondaryDisclosures = [
    page.getByTestId('scanner-diagnostics-disclosure'),
    page.getByTestId('scanner-run-comparison-strip'),
    page.getByTestId('scanner-strategy-experiment'),
  ];
  for (const disclosure of secondaryDisclosures) {
    if (await disclosure.count()) {
      await expect(disclosure).toBeVisible();
      await expect(disclosure).not.toHaveAttribute('open');
      const disclosureBox = await disclosure.boundingBox();
      expect(disclosureBox?.y ?? Number.POSITIVE_INFINITY).toBeGreaterThan(candidateRegionBox?.y ?? 0);
    }
  }
  await expect(page.getByTestId('scanner-diagnostics-panel')).toHaveCount(0);
  await expect(page.getByTestId('scanner-result-history-summary')).toHaveCount(0);
  await expect(page.getByTestId('scanner-strategy-preview')).toHaveCount(0);
  await expect(page.getByTestId('scanner-advanced-controls')).toHaveCount(0);

  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(forbiddenTradingAction);
  expect(bodyText).not.toMatch(rawPayloadPattern);
  expect(bodyText).not.toMatch(/Details|provider|fallback|proxy|raw|reasonCode|reasonFamilies|source-confidence|sourceConfidence|MarketCache|bucket|runtime|diagnostic|diagnostics/i);
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

test.describe('scanner launch surface', () => {
  test('candidate and evidence lead the zh scanner first fold', async ({ page }) => {
    await assertScannerLaunchViewport(page, { width: 1440, height: 1000 });
    await assertScannerLaunchViewport(page, { width: 1920, height: 1080 });
    await assertScannerLaunchViewport(page, { width: 768, height: 900 });
    await assertScannerLaunchViewport(page, { width: 390, height: 844 });
  });

  test('shows first-run guidance with one primary scan CTA when no scan history exists', async ({ page }) => {
    await page.route('**/api/v1/auth/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          authEnabled: true,
          loggedIn: true,
          passwordSet: true,
          passwordChangeable: true,
          setupState: 'enabled',
          currentUser: {
            id: 'user-1',
            username: 'wolfy-user',
            displayName: 'Wolfy User',
            role: 'user',
            isAdmin: false,
            isAuthenticated: true,
            transitional: false,
            authEnabled: true,
          },
        }),
      });
    });
    await page.route('**/api/v1/scanner/runs**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
        }),
      });
    });

    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('/zh/scanner');
    await page.waitForLoadState('domcontentloaded');

    const conclusionBand = page.getByTestId('scanner-conclusion-band');
    const emptyState = page.getByTestId('scanner-workbench-empty-state');
    const runButton = page.getByRole('button', { name: '启动扫描' });

    await expect(conclusionBand).toContainText('首次使用：先运行一次扫描');
    await expect(conclusionBand).toContainText('扫描器会先按当前范围筛出可继续观察的候选。');
    await expect(conclusionBand).toContainText('A股 · 默认市场池 · 300 只 · 60 条详评');
    await expect(emptyState).toContainText('尚未运行扫描');
    await expect(emptyState).toContainText('扫描器会先按当前范围整理候选与观察线索。');
    await expect(emptyState).toContainText('先直接启动一次扫描');
    await expect(emptyState).toContainText('打开历史记录');
    await expect(runButton).toHaveCount(1);
    await expect(page.getByRole('button', { name: '重新扫描' })).toHaveCount(0);
    await expect(page.locator('body')).not.toContainText(forbiddenTradingAction);
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  });

  test('retries loaded run params with a valid shortlist fallback in the workspace layout', async ({ page }) => {
    let postedRunRequest: unknown = null;

    await page.route('**/api/v1/auth/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          authEnabled: true,
          loggedIn: true,
          passwordSet: true,
          passwordChangeable: true,
          setupState: 'enabled',
          currentUser: {
            id: 'user-1',
            username: 'wolfy-user',
            displayName: 'Wolfy User',
            role: 'user',
            isAdmin: false,
            isAuthenticated: true,
            transitional: false,
            authEnabled: true,
          },
        }),
      });
    });
    await page.route('**/api/v1/scanner/runs/11', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(retryNoCandidateRun),
      });
    });
    await page.route('**/api/v1/scanner/run', async (route) => {
      postedRunRequest = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...retryNoCandidateRun, id: 12 }),
      });
    });

    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('/zh/scanner');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByTestId('scanner-summary-rail')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('scanner-command-panel')).toBeVisible();
    const runFacts = page.getByTestId('scanner-run-facts');
    await expect(runFacts).toBeVisible();
    await expect(runFacts).toContainText('运行事实');
    await expect(runFacts).toContainText('市场');
    await expect(runFacts).toContainText('A股');
    await expect(runFacts).toContainText('策略');
    await expect(runFacts).toContainText('A-share Pre-open');
    await expect(runFacts).toContainText('运行时间');
    await expect(runFacts).toContainText('完成时间');
    await expect(runFacts).toContainText('观察日期');
    await expect(runFacts).toContainText('标的池');
    await expect(runFacts).toContainText('320');
    await expect(runFacts).toContainText('预筛');
    await expect(runFacts).toContainText('72');
    await expect(runFacts).toContainText('评估');
    await expect(runFacts).toContainText('48');
    await expect(runFacts).toContainText('入选');
    await expect(runFacts).toContainText('0');
    await expect(runFacts).not.toContainText(/provider|reasonCode|below_threshold|raw/i);
    await expect(page.getByTestId('scanner-history-scope-hint')).toContainText('个人历史仅基于当前账号可访问的扫描记录');
    await expect(page.getByRole('button', { name: '重新扫描' })).toBeEnabled();
    await page.getByRole('button', { name: '重新扫描' }).click();

    await expect.poll(() => JSON.stringify(postedRunRequest)).toBe(JSON.stringify({
      market: 'cn',
      profile: 'cn_preopen_v1',
      shortlist_size: 5,
      universe_limit: 320,
      detail_limit: 72,
    }));
  });

  test('shows no-candidate next steps with preview and manual research handoff', async ({ page }) => {
    let watchlistRequest: unknown = null;
    let analysisRequest: unknown = null;

    await page.route('**/api/v1/auth/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          authEnabled: true,
          loggedIn: true,
          passwordSet: true,
          passwordChangeable: true,
          setupState: 'enabled',
          currentUser: {
            id: 'user-1',
            username: 'wolfy-user',
            displayName: 'Wolfy User',
            role: 'user',
            isAdmin: false,
            isAuthenticated: true,
            transitional: false,
            authEnabled: true,
          },
        }),
      });
    });
    await page.route(/\/api\/v1\/scanner\/runs(?:\?.*)?$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [{
            id: 11,
            market: 'cn',
            profile: 'cn_preopen_v1',
            profile_label: 'A-share Pre-open v1',
            status: 'empty',
            run_at: '2026-05-02T09:00:00Z',
            completed_at: '2026-05-02T09:00:00Z',
            watchlist_date: '2026-05-02',
            trigger_mode: 'manual',
            universe_name: 'cn_a_liquid_watchlist_v1',
            shortlist_size: 0,
            universe_size: 320,
            preselected_size: 72,
            evaluated_size: 48,
            source_summary: 'Mocked scanner payload',
            headline: 'Mock scanner no-candidate result with preview row',
            universe_type: 'default',
            theme_id: null,
            theme_label: null,
            requested_symbols_count: 0,
            accepted_symbols_count: 0,
            rejected_symbols: [],
            top_symbols: [],
            notification_status: 'not_attempted',
            failure_reason: null,
          }],
          total: 1,
          page: 1,
          page_size: 20,
        }),
      });
    });
    await page.route('**/api/v1/scanner/runs/11', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(previewNoCandidateRun),
      });
    });
    await page.route('**/api/v1/watchlist/items', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ items: [] }),
        });
        return;
      }
      watchlistRequest = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 2002,
          symbol: 'TSLA',
          market: 'cn',
          name: 'TSLA',
          source: 'scanner',
          created_at: '2026-05-02T09:00:00Z',
          updated_at: '2026-05-02T09:00:00Z',
        }),
      });
    });
    await page.route('**/api/v1/analysis/analyze', async (route) => {
      analysisRequest = route.request().postDataJSON();
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          taskId: 'task-manual-tsla',
          status: 'accepted',
          message: 'Accepted',
        }),
      });
    });

    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('/zh/scanner');
    await page.waitForLoadState('domcontentloaded');

    const nextSteps = page.getByTestId('scanner-workflow-next-steps');
    await expect(nextSteps).toBeVisible({ timeout: 15_000 });
    await expect(nextSteps).toContainText('下一步');
    await expect(nextSteps).toContainText('首选研究路径');
    await expect(nextSteps).toContainText('换市场或配置');
    await expect(nextSteps).toContainText('不代表市场没有机会');
    await expect(nextSteps).toContainText('查看历史');
    await expect(nextSteps).toContainText('可选保存路径');
    await expect(nextSteps).toContainText('预览候选 1');
    await expect(nextSteps).toContainText('预览不会改变官方入选或评分');
    await expect(nextSteps).toContainText('功能预览');
    await expect(nextSteps).toContainText('示例预览');
    await expect(nextSteps).toContainText('此演示样例不是实时扫描结果');
    await expect(nextSteps).toContainText('不会写入观察名单');
    await expect(nextSteps).toContainText('不会进入官方排名或导出数据');
    await expect(nextSteps.getByRole('link', { name: /打开 Watchlist/i })).toHaveAttribute('href', '/zh/watchlist');
    await expect(nextSteps.getByRole('link', { name: /打开 Market Overview/i })).toHaveAttribute('href', '/zh/market-overview');

    await nextSteps.getByRole('button', { name: /查看预览候选/ }).click();
    const previewRow = page.getByTestId('scanner-candidate-row-MARA');
    await expect(previewRow).toBeVisible();
    await expect(previewRow).toContainText('预览');

    await nextSteps.getByLabel(/手动补充研究代码/).fill('TSLA');
    await nextSteps.getByRole('button', { name: /加入观察名单 TSLA/ }).click();
    await expect.poll(() => JSON.stringify(watchlistRequest)).toContain('TSLA');
    await expect(nextSteps.getByRole('button', { name: /已在观察名单|Already in Watchlist/ })).toBeVisible();

    await nextSteps.getByLabel(/手动补充研究代码/).fill('TSLA');
    await nextSteps.getByRole('button', { name: /研究 TSLA/ }).click();
    await expect.poll(() => JSON.stringify(analysisRequest)).toContain('TSLA');

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).not.toMatch(/provider|reasonCode|fallback_source|below_liquidity_threshold|raw diagnostics|payload_json/i);
    await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  });
});
