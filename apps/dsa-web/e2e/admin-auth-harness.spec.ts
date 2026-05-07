import {
  expect,
  expectNoHorizontalOverflow,
  expectNoRawSecretLikeText,
  openAdminRouteWithHarness,
  test,
} from './fixtures/adminAuth';
import type { AdminCapability } from './fixtures/adminAuth';
import type { Request } from '@playwright/test';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

const costApiPaths = [
  ['GET', '/api/v1/admin/cost/duplicate-summary'],
  ['POST', '/api/v1/admin/cost/quota-dry-run'],
  ['GET', '/api/v1/admin/cost/llm-ledger-summary'],
  ['GET', '/api/v1/admin/cost/model-pricing-policies'],
] as const;

const providerCircuitApiPaths = [
  ['GET', '/api/v1/admin/providers/circuits'],
  ['GET', '/api/v1/admin/providers/circuits/events'],
  ['GET', '/api/v1/admin/providers/quota-windows'],
  ['GET', '/api/v1/admin/providers/probe-events'],
  ['GET', '/api/v1/admin/providers/sla-readiness'],
] as const;

async function expectAdminRouteShellClean(page: Parameters<typeof expectNoHorizontalOverflow>[0]) {
  await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
  await expectNoHorizontalOverflow(page);
  await expectNoRawSecretLikeText(page);
}

async function expectProviderSlaReadinessSmoke(page: Parameters<typeof expectNoHorizontalOverflow>[0]) {
  const slaPanel = page.getByRole('heading', { name: 'Provider SLA / 凭证就绪' }).locator('xpath=ancestor::section[1]');
  await expect(slaPanel).toBeVisible();
  await expect(slaPanel.getByText('只读 · 无 live call')).toBeVisible();
  await expect(slaPanel.getByText('mock-provider · llm · analysis')).toBeVisible();
  await expect(slaPanel.getByText('缺少凭证')).toBeVisible();
  await expect(slaPanel.getByText('Latency')).toBeVisible();
  await expect(slaPanel.getByText('正常 · 120 ms')).toBeVisible();
  await expect(slaPanel.getByText('Freshness')).toBeVisible();
  await expect(slaPanel.getByText('新鲜 · 60 s')).toBeVisible();
  await expect(slaPanel.getByText('Credentials')).toBeVisible();
  await expect(slaPanel.getByText('否 · dry-run 是')).toBeVisible();
  await expect(slaPanel.getByText('Live calls')).toBeVisible();
  await expect(slaPanel.getByText('Would block')).toBeVisible();
  await expect(slaPanel.getByText('最近错误 buckets')).toBeVisible();
  await expect(slaPanel.locator('details[open]')).toHaveCount(0);

  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(/raw\s+(payload|response)|debug\s+(payload|response)|provider\s+payload|token|api[_\s-]?key|secret|password|bearer/i);
}

function installUnexpectedExternalRequestTracker(page: Parameters<typeof expectNoHorizontalOverflow>[0]) {
  const unexpectedExternalRequests: string[] = [];
  const onRequest = (request: Request) => {
    const url = new URL(request.url());
    const isHttp = url.protocol === 'http:' || url.protocol === 'https:';
    const isLocal =
      url.hostname === 'localhost' ||
      url.hostname === '127.0.0.1' ||
      url.hostname === '[::1]' ||
      url.hostname === '::1';
    const isStaticFontAsset = url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com';
    if (isHttp && !isLocal && !isStaticFontAsset) {
      unexpectedExternalRequests.push(request.url());
    }
  };
  page.on('request', onRequest);
  return {
    expectNone: () => expect(unexpectedExternalRequests).toEqual([]),
    dispose: () => page.off('request', onRequest),
  };
}

test.describe('mocked admin auth browser harness', () => {
  test('renders admin pages for a full admin with all mocked capabilities', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);

      let harness = await openAdminRouteWithHarness(page, '/zh/admin/cost-observability');
      await expect(page.getByRole('heading', { name: '成本观测' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('quota-dry-run-panel')).toBeVisible();
      await expect(page.getByTestId('llm-ledger-panel')).toBeVisible();
      await expect(page.getByTestId('model-pricing-policy-panel')).toBeVisible();
      await expect(page.getByText('LLM 成本账本')).toBeVisible();
      await expect(page.getByText('模型价格策略')).toBeVisible();
      await expect(page.getByText('配额试运行诊断')).toBeVisible();
      await expect(page.getByText('用户成本排行')).toBeVisible();
      await expect(page.getByText('模型成本分布')).toBeVisible();
      await expect(page.getByText('功能成本分布')).toBeVisible();
      expect(harness.requests.count('GET', '/api/v1/admin/cost/duplicate-summary')).toBeGreaterThan(0);
      expect(harness.requests.count('POST', '/api/v1/admin/cost/quota-dry-run')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/cost/llm-ledger-summary')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/cost/model-pricing-policies')).toBe(1);
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });

      harness = await openAdminRouteWithHarness(page, '/zh/admin/provider-circuits');
      await expect(page.getByRole('heading', { name: 'Provider 熔断诊断' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText('当前熔断状态', { exact: true })).toBeVisible();
      await expect(page.getByRole('heading', { name: '最近熔断事件' })).toBeVisible();
      await expect(page.getByRole('heading', { name: '配额窗口' })).toBeVisible();
      await expect(page.getByRole('heading', { name: '探测事件' })).toBeVisible();
      await expectProviderSlaReadinessSmoke(page);
      for (const [method, path] of providerCircuitApiPaths) {
        expect(harness.requests.count(method, path)).toBe(1);
      }
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });

      harness = await openAdminRouteWithHarness(page, '/zh/admin/users');
      await expect(page.getByRole('heading', { name: '用户目录' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText('alice')).toBeVisible();
      expect(harness.requests.count('GET', '/api/v1/admin/users')).toBeGreaterThan(0);
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });

      harness = await openAdminRouteWithHarness(page, '/zh/settings/system');
      await expect(page.getByTestId('settings-bento-page')).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('system-health-summary')).toBeVisible();
      await expect(page.getByTestId('duckdb-quant-panel')).toBeVisible();
      expect(harness.requests.count('GET', '/api/v1/system/config')).toBeGreaterThan(0);
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  test('renders cost observability for cost-only admins and blocks provider diagnostics', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);

      let harness = await openAdminRouteWithHarness(page, '/zh/admin/cost-observability', {
        capabilities: ['cost:observability:read'],
      });
      await expect(page.getByRole('heading', { name: '成本观测' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('quota-dry-run-panel')).toBeVisible();
      await expect(page.getByTestId('llm-ledger-panel')).toBeVisible();
      await expect(page.getByTestId('model-pricing-policy-panel')).toBeVisible();
      await expect(page.getByText('模型价格策略')).toBeVisible();
      await expect(page.getByText('配额试运行诊断')).toBeVisible();
      for (const [method, path] of costApiPaths) {
        expect(harness.requests.count(method, path)).toBeGreaterThan(0);
      }
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });

      harness = await openAdminRouteWithHarness(page, '/zh/admin/provider-circuits', {
        capabilities: ['cost:observability:read'],
      });
      await expect(page.getByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByRole('heading', { name: 'Provider 熔断诊断' })).toHaveCount(0);
      for (const [method, path] of providerCircuitApiPaths) {
        expect(harness.requests.wasFetched(method, path)).toBe(false);
      }
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  test('renders provider diagnostics for providers-only admins and blocks cost panels', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);

      const externalRequestTracker = installUnexpectedExternalRequestTracker(page);
      let harness = await openAdminRouteWithHarness(page, '/zh/admin/provider-circuits', {
        capabilities: ['ops:providers:read'],
      });
      await expect(page.getByRole('heading', { name: 'Provider 熔断诊断' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText('当前熔断状态', { exact: true })).toBeVisible();
      await expect(page.getByRole('heading', { name: '最近熔断事件' })).toBeVisible();
      await expect(page.getByRole('heading', { name: '配额窗口' })).toBeVisible();
      await expect(page.getByRole('heading', { name: '探测事件' })).toBeVisible();
      await expectProviderSlaReadinessSmoke(page);
      for (const [method, path] of providerCircuitApiPaths) {
        expect(harness.requests.count(method, path)).toBe(1);
      }
      externalRequestTracker.expectNone();
      await expectAdminRouteShellClean(page);
      externalRequestTracker.dispose();
      await page.unrouteAll({ behavior: 'ignoreErrors' });

      harness = await openAdminRouteWithHarness(page, '/zh/admin/cost-observability', {
        capabilities: ['ops:providers:read'],
      });
      await expect(page.getByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('quota-dry-run-panel')).toHaveCount(0);
      await expect(page.getByTestId('llm-ledger-panel')).toHaveCount(0);
      await expect(page.getByTestId('model-pricing-policy-panel')).toHaveCount(0);
      for (const [method, path] of costApiPaths) {
        expect(harness.requests.wasFetched(method, path)).toBe(false);
      }
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  test('does not render or fetch cost panels without cost observability capability', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openAdminRouteWithHarness(page, '/zh/admin/cost-observability', {
        capabilities: ['users:read'],
      });

      await expect(page.getByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('quota-dry-run-panel')).toHaveCount(0);
      await expect(page.getByTestId('llm-ledger-panel')).toHaveCount(0);
      await expect(page.getByTestId('model-pricing-policy-panel')).toHaveCount(0);
      for (const [method, path] of costApiPaths) {
        expect(harness.requests.wasFetched(method, path)).toBe(false);
      }
      await expectAdminRouteShellClean(page);
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
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });

      const costHarness = await openAdminRouteWithHarness(page, '/zh/admin/cost-observability', {
        capabilities: ['cost:observability:read' as AdminCapability],
        includeCapabilityFields: false,
      });
      await expect(page.getByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('quota-dry-run-panel')).toHaveCount(0);
      await expect(page.getByTestId('llm-ledger-panel')).toHaveCount(0);
      await expect(page.getByTestId('model-pricing-policy-panel')).toHaveCount(0);
      for (const [method, path] of costApiPaths) {
        expect(costHarness.requests.wasFetched(method, path)).toBe(false);
      }
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });

      const providersHarness = await openAdminRouteWithHarness(page, '/zh/admin/provider-circuits', {
        capabilities: ['ops:providers:read' as AdminCapability],
        includeCapabilityFields: false,
      });
      await expect(page.getByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByRole('heading', { name: 'Provider 熔断诊断' })).toHaveCount(0);
      for (const [method, path] of providerCircuitApiPaths) {
        expect(providersHarness.requests.wasFetched(method, path)).toBe(false);
      }
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});
