import { expect, expectNoHorizontalOverflow, openAdminRouteWithHarness, test } from './fixtures/adminAuth';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

const expectedSummaries = [
  '当前证据链已校验，可用于观察，不提升任何判断强度。',
  '当前为轮动代理证据，真实资金流暂缺，仅供观察。',
  '当前期权证据不足，数据不足，禁止判断，仅保留观察与人工复核。',
  '当前仅为研究级回测证据，仅供观察，不构成机构级验证结论。',
  '当前组合风险证据链不完整，仅供风险观察，不输出确定性风险结论。',
];

test.describe('admin evidence dry-run preview', () => {
  test('renders deterministic display-only preview cards without overflow or raw-json leakage', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openAdminRouteWithHarness(page, '/zh/admin/evidence-workflow', {
        capabilities: ['ops:logs:read'],
      });

      const preview = page.getByTestId('admin-evidence-dry-run-preview');
      await expect(preview).toBeVisible({ timeout: 15_000 });
      await expect(preview.getByRole('heading', { name: 'AI 证据解释预览' })).toBeVisible();
      await expect(preview.getByText('display-only')).toBeVisible();
      await expect(preview.getByText('no live influence')).toBeVisible();
      await expect(preview.getByText(/不影响实时 AI 决策/)).toBeVisible();

      for (const summary of expectedSummaries) {
        await expect(preview.getByText(summary)).toBeVisible();
      }

      const optionsCard = page.getByTestId('admin-evidence-dry-run-card-options');
      await expect(optionsCard.getByText('禁止判断', { exact: true }).first()).toBeVisible();
      await expect(optionsCard.getByText('≤35')).toBeVisible();
      await expect(optionsCard.getByText('样本标的 · WULF · bull_call_spread')).toBeVisible();

      const rotationCard = page.getByTestId('admin-evidence-dry-run-card-rotation');
      await expect(rotationCard.getByText('真实资金流暂缺', { exact: true })).toBeVisible();

      const optionsDisclosure = page.getByTestId('admin-evidence-dry-run-disclosure-options');
      await expect(optionsDisclosure).not.toHaveAttribute('open', '');
      await expect(optionsDisclosure).toContainText('已禁用 2 项结论');

      const bodyText = await page.locator('body').innerText();
      expect(bodyText).not.toMatch(/prompt fragment|raw json|provider payload/i);
      expect(bodyText).not.toMatch(/warning wall/i);

      await expectNoHorizontalOverflow(page);
      expect(harness.requests.count('GET', '/api/v1/scanner/watchlists/recent')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/market/rotation-radar')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/backtest/rule/runs')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/portfolio/snapshot')).toBeGreaterThan(0);
      expect(harness.requests.count('POST', '/api/v1/options/decision/evaluate')).toBe(0);

      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});
