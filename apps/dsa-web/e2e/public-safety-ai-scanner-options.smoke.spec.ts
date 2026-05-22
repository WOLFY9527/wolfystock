import type { Page } from '@playwright/test';
import { expect, test as appTest } from './fixtures/appSmoke';
import {
  expectForbiddenTradingWordingAbsent,
  expectNoHorizontalOverflow,
  expectRootNonEmpty,
  openProductRouteWithHarness,
  test as productTest,
} from './fixtures/productAuth';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
] as const;

const rawInternalArtifactPattern = /raw\s+(payload|response|schema|prompt|trace)|debug\s+(payload|response|schema|prompt|panel)|provider\s+payload|stack\s+(trace|details)|traceback|internal\s+reasoning|api[_\s-]?key\s*[=:]|password\s*[=:]|session[_\s-]?id\s*[=:]|secret\s*[=:]|bearer\s+[a-z0-9._-]+|sk-[a-z0-9_-]{12,}|ghp_[a-z0-9_]{12,}|xox[baprs]-[a-z0-9-]{12,}/i;

async function signIn(page: Page, redirectPath: string) {
  await page.goto(`/login?redirect=${encodeURIComponent(redirectPath)}`);
  const username = page.locator('#username');
  if (await username.waitFor({ state: 'visible', timeout: 10_000 }).then(() => true).catch(() => false)) {
    await username.fill('wolfy-user');
    await page.locator('#password').fill('mock-password');
    await Promise.all([
      page.waitForResponse((response) => response.url().includes('/api/v1/auth/login') && response.status() === 200),
      page.getByRole('button', { name: /sign in|登录继续|授权进入工作台|完成设置并登录/i }).click(),
    ]);
    await page.waitForURL(/\/$/);
  }
  await page.goto(redirectPath);
  await page.waitForLoadState('domcontentloaded');
}

async function expectNoRawInternalArtifacts(page: Page) {
  await expect(page.locator('body')).not.toContainText(rawInternalArtifactPattern);
  await expect(page.locator('details[open]')).toHaveCount(0);
}

async function expectSurfaceSafety(page: Page) {
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);
  await expectForbiddenTradingWordingAbsent(page);
  await expectNoRawInternalArtifacts(page);
}

appTest.describe('AI and scanner public safety surfaces', () => {
  appTest('scanner exposes limited-data states while keeping diagnostics collapsed by default', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await signIn(page, '/scanner');

      await expect(page.getByTestId('user-scanner-bento-page')).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('scanner-result-card-NVDA')).toBeVisible();
      await expect(page.getByTestId('scanner-result-history-summary')).toContainText(/数据源异常|降级|数据不足|Provider issue|Fallback data|Insufficient data/);
      await expect(page.getByTestId('scanner-diagnostics-summary')).toBeVisible();
      await expect(page.getByTestId('scanner-diagnostics-panel')).toHaveCount(0);
      await expectSurfaceSafety(page);
    }
  });
});

productTest.describe('options public safety surface', () => {
  productTest('Options Lab labels synthetic data as non-decision-grade and keeps developer details collapsed', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openProductRouteWithHarness(page, '/zh/options-lab');

      await expect(page.getByRole('heading', { name: '期权实验室' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('options-lab-decision-engine')).toBeVisible();
      await expect(page.getByTestId('options-lab-decision-engine')).toContainText('数据不足，禁止判断');
      await expect(page.getByTestId('options-lab-decision-engine')).toContainText('演示数据');
      await expect(page.getByTestId('options-lab-decision-engine')).toContainText('不可用于真实交易判断');
      await expect(page.getByTestId('options-lab-developer-details')).not.toHaveAttribute('open');
      await expect(page.getByTestId('options-lab-strategy-developer-details')).not.toHaveAttribute('open');
      await expect(page.getByTestId('options-lab-decision-developer-details')).not.toHaveAttribute('open');
      await expectSurfaceSafety(page);

      expect(harness.requests.count('POST', '/api/v1/options/decision/evaluate')).toBeGreaterThan(0);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});
