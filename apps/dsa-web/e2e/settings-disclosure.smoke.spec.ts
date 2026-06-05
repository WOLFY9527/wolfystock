import { expect, openAdminRouteWithHarness, test } from './fixtures/adminAuth';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
] as const;

const forbiddenDefaultDisclosurePattern =
  /provider route|cache router|raw config|Bootstrap Admin|\bdebug\b|\btoken\b|\/api\/v1\/|DEFAULT_LLM_PROVIDER|SCHEDULE_ENABLED|DUCKDB_ENABLED/i;

async function expectNoHorizontalOverflow(page: Parameters<typeof test>[0]['page']) {
  await expect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function expectDefaultVisibleTextSafe(page: Parameters<typeof test>[0]['page']) {
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(forbiddenDefaultDisclosurePattern);
}

test.describe('settings disclosure browser smoke', () => {
  test('keeps /zh/settings operator-safe on the default visible surface', async ({ page }) => {
    for (const viewport of viewports) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await page.setViewportSize(viewport);

      const harness = await openAdminRouteWithHarness(page, '/zh/settings');

      await expect(page).toHaveURL(/\/zh\/settings$/);
      await expect(page.getByRole('heading', { name: '账户中心' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('personal-settings-notifications-section')).toContainText('通知');
      await expect(page.getByTestId('personal-settings-privacy-section')).toContainText('隐私与会话');
      await expect(page.getByText('在个人设置内统一保存邮件与 Discord 目标。')).toBeVisible();
      await expect(page.getByText('明确账户边界，并说明哪些设置仍然只保存在当前浏览器。')).toBeVisible();
      await expect(page.getByTestId('personal-settings-boundary-disclosure').getByRole('button')).toHaveAttribute('aria-expanded', 'false');
      await expect(page.getByTestId('personal-settings-help-disclosure').getByRole('button')).toHaveAttribute('aria-expanded', 'false');

      expect(harness.requests.count('GET', '/api/v1/auth/status')).toBeGreaterThan(0);
      await expectNoHorizontalOverflow(page);
      await expectDefaultVisibleTextSafe(page);
    }
  });

  test('keeps /zh/settings/system operator-safe on the default visible surface', async ({ page }) => {
    for (const viewport of viewports) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await page.setViewportSize(viewport);

      const harness = await openAdminRouteWithHarness(page, '/zh/settings/system');

      await expect(page).toHaveURL(/\/zh\/settings\/system$/);
      await expect(page.getByRole('heading', { name: '系统设置' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText('系统风险总览')).toBeVisible();
      await expect(page.getByRole('heading', { name: '数据源状态' })).toBeVisible();
      await expect(page.getByRole('button', { name: 'AI 模型' })).toBeVisible();
      await expect(page.getByRole('heading', { name: '运维总览' })).toBeVisible();
      await expect(page.getByText('当前已进入系统运维中心')).toBeVisible();
      await expect(page.getByText('技术细节：配置键、诊断摘要和环境上下文默认收起，仅供管理员排障时展开。')).toBeVisible();
      await expect(page.getByText('只展示凭证就绪状态；不显示密钥、访问凭证、Webhook 或未遮蔽原值。')).toBeVisible();
      await expect(page.getByText('展开缓存维护与初始化动作')).toBeVisible();
      await expect(page.getByTestId('system-duckdb-disclosure').getByText('配置兼容摘要')).toBeVisible();
      await expect(page.getByRole('button', { name: /^收起 / })).toHaveCount(0);
      await expect(page.getByTestId('system-health-summary')).toBeVisible();
      await expect(page.getByTestId('duckdb-quant-panel')).toBeAttached();

      expect(harness.requests.count('GET', '/api/v1/system/config')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/quant/duckdb/health')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/quant/duckdb/coverage')).toBeGreaterThan(0);
      await expectNoHorizontalOverflow(page);
      await expectDefaultVisibleTextSafe(page);
    }
  });
});
