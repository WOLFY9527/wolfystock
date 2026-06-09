import { expect as baseExpect } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';
import { captureShellVisualEvidence } from './fixtures/shellVisualEvidence';

const GUEST_PRICE_ZONE_FORBIDDEN_COPY_PATTERN =
  /理想买入|入场|止损|止盈|目标价|买入|卖出|加仓|建仓|target price|entry|stop loss|take profit/i;

appTest('guest entry routes use research branding instead of AI persona copy', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });

  await page.goto('/');
  await appExpect(page).not.toHaveURL(/\/login(?:\?|$)/);
  await appExpect(page.getByTestId('guest-home-clean-search')).toBeVisible({ timeout: 15_000 });
  await appExpect(page.getByRole('heading', { name: /WolfyStock 研究控制台|WolfyStock Research Console/ })).toBeVisible();
  await appExpect(page.getByTestId('guest-home-market-preview-strip')).toContainText(/当前市场观察|Current market observation/);
  await appExpect(page.locator('body')).not.toContainText(/WOLFY AI|wake the AI|INITIALIZING WOLFY AI CORE|terminal boot/i);
  await appExpect(page.getByTestId('guest-home-clean-search')).not.toContainText(/\bNVDA\b|NVIDIA|TSLA|Tesla/i);
  await baseExpect
    .poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
    .toBe(true);

  await page.goto('/guest');
  await appExpect(page).not.toHaveURL(/\/login(?:\?|$)/);
  await appExpect(page.getByTestId('guest-home-clean-search')).toBeVisible({ timeout: 15_000 });
  await appExpect(page.getByRole('heading', { name: /WolfyStock 研究控制台|WolfyStock Research Console/ })).toBeVisible();
  await captureShellVisualEvidence(page, 'guest', { width: 1440, height: 1000 });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/zh/guest');
  await appExpect(page.getByTestId('guest-home-clean-search')).toBeVisible({ timeout: 15_000 });
  await appExpect(page.getByTestId('guest-home-market-preview-strip')).toContainText('当前市场观察');
  await appExpect(page.getByTestId('home-bento-omnibar-input')).toHaveAttribute('placeholder', '输入代码开始研究 (如 ORCL)...');
  await appExpect(page.locator('body')).not.toContainText(/WOLFY AI|唤醒 AI|INITIALIZING|terminal boot/i);
  await appExpect(page.getByTestId('guest-home-clean-search')).not.toContainText(/\bNVDA\b|NVIDIA|TSLA|Tesla/i);
  await baseExpect
    .poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
    .toBe(true);
  await captureShellVisualEvidence(page, 'guest', { width: 390, height: 844 });

  await page.goto('/zh/login');
  await appExpect(page.getByRole('heading', { name: 'WolfyStock 账户登录' })).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: '返回游客模式' }).click();
  await appExpect(page).toHaveURL(/\/zh\/guest$/);
  await appExpect(page.getByTestId('guest-home-clean-search')).toBeVisible({ timeout: 15_000 });
  await appExpect(page.locator('body')).not.toContainText(/WOLFY AI|INITIALIZING|terminal boot/i);
  await baseExpect
    .poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
    .toBe(true);

  await page.goto('/zh/register?redirect=%2Fzh%2Fmarket-overview');
  await appExpect(page).not.toHaveURL(/\/login(?:\?|$)/);
  await appExpect(page.getByRole('heading', { name: '创建账户' })).toBeVisible({ timeout: 15_000 });
  await appExpect(page.getByRole('button', { name: '返回游客模式' })).toBeVisible();

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/market-overview');
  await appExpect(page).not.toHaveURL(/\/login(?:\?|$)/);
  await appExpect(page.getByTestId('market-overview-shell')).toBeVisible({ timeout: 15_000 });
  await appExpect(page.getByTestId('auth-guard-overlay')).toHaveCount(0);
});

appTest('guest first fold stays honest when the public market snapshot is unavailable', async ({ page }) => {
  await page.route('**/api/v1/market/market-briefing', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        source: 'fallback',
        sourceLabel: 'Latest available data',
        updatedAt: '2026-06-08T00:00:00Z',
        asOf: '2026-06-08T00:00:00Z',
        freshness: 'fallback',
        isFallback: true,
        isReliable: false,
        warning: 'Sign in to open Market Overview, Scanner, and saved research history once the public snapshot comes back.',
        items: [],
      }),
    });
  });

  await page.goto('/en/guest');
  await appExpect(page.getByTestId('guest-home-clean-search')).toBeVisible({ timeout: 15_000 });
  await appExpect(page.getByTestId('guest-home-market-preview-strip')).toContainText('Public market observation unavailable right now');
  await appExpect(page.getByTestId('guest-home-market-preview-strip')).toContainText('Sign in to open Market Overview, Scanner, and saved research history once the public snapshot comes back.');
  await appExpect(page.getByTestId('guest-home-clean-search')).not.toContainText(/\bNVDA\b|NVIDIA|TSLA|Tesla/i);
  await baseExpect
    .poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
    .toBe(true);
});

appTest('guest search falls back to a bounded research snapshot when preview stalls', async ({ page }) => {
  await page.route('**/api/v1/analysis/preview', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 5_000));
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        query_id: 'preview-tsla',
        stock_code: 'TSLA',
        stock_name: 'Tesla',
        preview_scope: 'guest',
        report: {
          meta: {
            query_id: 'preview-tsla',
            stock_code: 'TSLA',
            stock_name: 'Tesla',
            report_type: 'brief',
            created_at: '2026-06-08T00:00:00Z',
          },
          summary: {
            analysis_summary: 'This delayed preview should never replace the bounded fallback snapshot.',
            operation_advice: 'Wait',
            trend_prediction: 'Neutral',
            sentiment_score: 51,
          },
        },
      }),
    });
  });

  await page.goto('/zh/guest');
  await appExpect(page.getByTestId('guest-home-clean-search')).toBeVisible({ timeout: 15_000 });

  await page.getByTestId('home-bento-omnibar-input').fill('TSLA');
  await page.getByRole('button', { name: '分析' }).click();

  await appExpect(page.getByText('实时预览当前不可用，已切换到本地研究快照。')).toBeVisible({ timeout: 8_000 });
  await appExpect(page.getByTestId('home-research-console')).toBeVisible();
  await appExpect(page.getByTestId('home-research-score-strip')).toContainText('6.3');
  await appExpect(page.getByTestId('home-research-key-levels')).toContainText('价格观察');
  await appExpect(page.getByTestId('home-research-key-levels')).toContainText('风险边界');
  await appExpect(page.getByTestId('home-research-key-levels')).toContainText('上行情景');
  await appExpect(page.getByTestId('home-research-key-levels')).toContainText('需要确认');
  await appExpect(page.locator('body')).not.toContainText(/实时诱饵|WOLFY AI|唤醒 AI/i);
  await appExpect(page.getByTestId('home-bento-dashboard')).not.toContainText(GUEST_PRICE_ZONE_FORBIDDEN_COPY_PATTERN);
  await baseExpect
    .poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
    .toBe(true);
});
