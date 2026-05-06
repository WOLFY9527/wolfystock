import {
  expect,
  expectNoHorizontalOverflow,
  openAdminRouteWithHarness,
  test,
} from './fixtures/adminAuth';
import type { AdminCapability } from './fixtures/adminAuth';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

test.describe('mocked admin auth browser harness', () => {
  test('renders core admin pages with matching mocked capabilities', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);

      let harness = await openAdminRouteWithHarness(page, '/zh/admin/cost-observability', {
        capabilities: ['cost:observability:read'],
      });
      await expect(page.getByRole('heading', { name: '成本观测' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('quota-dry-run-panel')).toBeVisible();
      await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
      expect(harness.requests.count('GET', '/api/v1/admin/cost/duplicate-summary')).toBeGreaterThan(0);
      expect(harness.requests.count('POST', '/api/v1/admin/cost/quota-dry-run')).toBe(1);
      await expectNoHorizontalOverflow(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });

      harness = await openAdminRouteWithHarness(page, '/zh/admin/users', {
        capabilities: ['users:read'],
      });
      await expect(page.getByRole('heading', { name: '用户目录' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText('alice')).toBeVisible();
      await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
      expect(harness.requests.count('GET', '/api/v1/admin/users')).toBeGreaterThan(0);
      await expectNoHorizontalOverflow(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });

      harness = await openAdminRouteWithHarness(page, '/zh/settings/system', {
        capabilities: ['ops:system_config:read'],
      });
      await expect(page.getByTestId('settings-bento-page')).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('system-health-summary')).toBeVisible();
      await expect(page.getByTestId('duckdb-quant-panel')).toBeVisible();
      await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
      expect(harness.requests.count('GET', '/api/v1/system/config')).toBeGreaterThan(0);
      await expectNoHorizontalOverflow(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  test('does not render or fetch quota dry-run without cost observability capability', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openAdminRouteWithHarness(page, '/zh/admin/cost-observability', {
        capabilities: ['users:read'],
      });

      await expect(page.getByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('quota-dry-run-panel')).toHaveCount(0);
      expect(harness.requests.wasFetched('GET', '/api/v1/admin/cost/duplicate-summary')).toBe(false);
      expect(harness.requests.wasFetched('POST', '/api/v1/admin/cost/quota-dry-run')).toBe(false);
      await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
      await expectNoHorizontalOverflow(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  test('fails closed when admin capability fields are absent', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openAdminRouteWithHarness(page, '/zh/settings/system', {
        capabilities: ['ops:system_config:read' as AdminCapability],
        includeCapabilityFields: false,
      });

      await expect(page.getByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('settings-bento-page')).toHaveCount(0);
      expect(harness.requests.wasFetched('GET', '/api/v1/system/config')).toBe(false);
      await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
      await expectNoHorizontalOverflow(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});
