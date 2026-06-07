import { expect, test } from './fixtures/appSmoke';
import { expectNoHorizontalOverflow, installSignedInSessionRoutes } from './fixtures/authenticatedRouteSmoke';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

const forbiddenDiagnosticPattern = /provider|cache|runtime|debug|schema|reasonCode/i;

test.describe('rotation radar loading polish', () => {
  test('keeps loading copy consumer-safe before the route payload arrives on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await installSignedInSessionRoutes(page);
      await page.route('**/api/v1/market/rotation-radar**', async (route) => {
        await page.waitForTimeout(1_200);
        await route.fallback();
      });

      await page.goto('/zh/market/rotation-radar');
      await page.waitForLoadState('domcontentloaded');

      const loadingPanel = page.getByRole('status', { name: '正在读取主题轮动 / 相对强弱雷达' });
      await expect(loadingPanel).toBeVisible();
      await expect(loadingPanel).toContainText('正在整理主题强弱、轮动线索与最近更新时间。');
      await expect(loadingPanel).toContainText('准备好后会自动显示当前市场、头部主题和观察重点。');
      await expect(loadingPanel).toContainText('结果出来前不会补写临时轮动方向。');
      await expect(loadingPanel).not.toContainText(forbiddenDiagnosticPattern);
      await expectNoHorizontalOverflow(page);

      await expect(page.getByTestId('rotation-radar-guidance')).toBeVisible({ timeout: 15_000 });
      await expect(page.getByRole('status', { name: '正在读取主题轮动 / 相对强弱雷达' })).toHaveCount(0);
      await expectNoHorizontalOverflow(page);

      await page.unroute('**/api/v1/market/rotation-radar**');
    }
  });
});
