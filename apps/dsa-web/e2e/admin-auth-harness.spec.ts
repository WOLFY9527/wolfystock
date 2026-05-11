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

const primaryCostApiPaths = [
  ['GET', '/api/v1/admin/cost/duplicate-summary'],
  ['POST', '/api/v1/admin/cost/quota-dry-run'],
] as const;

const secondaryCostApiPaths = [
  ['GET', '/api/v1/admin/cost/llm-ledger-summary'],
  ['GET', '/api/v1/admin/cost/model-pricing-policies'],
] as const;

const systemApiPaths = [
  ['GET', '/api/v1/system/config'],
  ['GET', '/api/v1/quant/duckdb/health'],
  ['GET', '/api/v1/quant/duckdb/coverage'],
] as const;

const adminSecurityActionApiPaths = [
  ['POST', '/api/v1/admin/users/user-123/disable'],
  ['POST', '/api/v1/admin/users/user-123/enable'],
  ['POST', '/api/v1/admin/users/user-123/revoke-sessions'],
] as const;

const rawAuthRehearsalLeakPattern =
  /raw-session-canary-should-not-render|cookie_canary_should_not_render|RECOVERY-CODE-CANARY-0001|rawRbacCapabilityDump|adminCapabilities:\s|coarseFallbackEnabled|stagingOnly/i;
const providerCircuitSecondaryDisclosureLabel = '二级细节：探测、事件、配额窗口、路由 bucket';

async function expectNoRawAuthRehearsalLeak(page: Parameters<typeof expectNoHorizontalOverflow>[0]) {
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(rawAuthRehearsalLeakPattern);
}

async function expectAdminRouteShellClean(page: Parameters<typeof expectNoHorizontalOverflow>[0]) {
  await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
  await expectNoHorizontalOverflow(page);
  await expectNoRawSecretLikeText(page);
  await expectNoRawAuthRehearsalLeak(page);
}

async function expectProviderSlaReadinessSmoke(page: Parameters<typeof expectNoHorizontalOverflow>[0]) {
  const slaPanel = page.getByRole('heading', { name: 'Provider SLA / 凭证就绪' }).locator('xpath=ancestor::section[1]');
  await expect(slaPanel).toBeVisible();
  await expect(slaPanel.getByText('只读 · 外部调用关闭')).toBeVisible();
  await expect(slaPanel.getByText('分类 llm · 路由 analysis')).toBeVisible();
  await expect(slaPanel.getByText('缺少凭证')).toBeVisible();
  await expect(slaPanel.getByText('延迟')).toBeVisible();
  await expect(slaPanel.getByText('正常 · 120 ms')).toBeVisible();
  await expect(slaPanel.getByText('新鲜度')).toBeVisible();
  await expect(slaPanel.getByText('新鲜 · 60 s')).toBeVisible();
  await expect(slaPanel.getByText('错误状态')).toBeVisible();
  await expect(slaPanel.getByText('阻断判断')).toBeVisible();
  await expect(slaPanel.getByText('趋势请求')).toBeVisible();
  await expect(slaPanel.getByText('6_20')).toBeVisible();
  await expect(slaPanel.getByText('最近错误 buckets')).toBeVisible();
  await expect(slaPanel.getByRole('button', { name: '展开 最近错误 buckets' })).toHaveAttribute('aria-expanded', 'false');
  await expect(slaPanel.getByRole('button', { name: '展开 技术边界' })).toHaveAttribute('aria-expanded', 'false');
  await expect(slaPanel.getByRole('button', { name: /^收起 / })).toHaveCount(0);

  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(/raw\s+(payload|response)|debug\s+(payload|response)|provider\s+payload|token|api[_\s-]?key|secret|password|bearer/i);
}

async function expandProviderCircuitSecondaryDiagnostics(page: Parameters<typeof expectNoHorizontalOverflow>[0]) {
  const expandButton = page.getByRole('button', { name: `展开 ${providerCircuitSecondaryDisclosureLabel}` });
  await expect(expandButton).toBeVisible();
  await expect(expandButton).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByRole('heading', { name: '最近熔断事件' })).toHaveCount(0);
  await expandButton.click();
  await expect(page.getByRole('button', { name: `收起 ${providerCircuitSecondaryDisclosureLabel}` })).toHaveAttribute('aria-expanded', 'true');
  await expect(page.getByRole('heading', { name: '最近熔断事件', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '配额窗口', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '探测事件', exact: true })).toBeVisible();
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
      await expect(page.getByTestId('llm-ledger-panel')).toHaveCount(0);
      await expect(page.getByTestId('model-pricing-policy-panel')).toHaveCount(0);
      await expect(page.getByText('LLM 成本账本')).toHaveCount(0);
      await expect(page.getByText('模型价格策略')).toHaveCount(0);
      await expect(page.getByText('配额试运行诊断')).toBeVisible();
      await expect(page.getByText('用户成本排行')).toHaveCount(0);
      await expect(page.getByText('模型成本分布')).toHaveCount(0);
      await expect(page.getByText('功能成本分布')).toHaveCount(0);
      for (const [method, path] of primaryCostApiPaths) {
        expect(harness.requests.count(method, path)).toBeGreaterThan(0);
      }
      for (const [method, path] of secondaryCostApiPaths) {
        expect(harness.requests.count(method, path)).toBe(0);
      }
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });

      harness = await openAdminRouteWithHarness(page, '/zh/admin/provider-circuits');
      await expect(page.getByRole('heading', { name: 'Provider 熔断诊断' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText('当前熔断状态', { exact: true })).toBeVisible();
      await expandProviderCircuitSecondaryDiagnostics(page);
      await expectProviderSlaReadinessSmoke(page);
      for (const [method, path] of providerCircuitApiPaths) {
        expect(harness.requests.count(method, path)).toBe(1);
      }
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });

      harness = await openAdminRouteWithHarness(page, '/zh/admin/users');
      await expect(page.getByRole('heading', { name: '用户目录', level: 1 })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText('alice')).toBeVisible();
      expect(harness.requests.count('GET', '/api/v1/admin/users')).toBeGreaterThan(0);
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });

      harness = await openAdminRouteWithHarness(page, '/zh/admin/users/user-123?tab=security');
      await expect(page.getByRole('heading', { name: '安全控制 S1' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('security-action-disable')).toBeVisible();
      await expect(page.getByTestId('security-action-revoke-sessions')).toBeVisible();
      await expect(page.getByRole('button', { name: '禁用账户' })).toBeDisabled();
      await expect(page.getByRole('button', { name: '撤销全部会话' })).toBeDisabled();
      expect(harness.requests.count('GET', '/api/v1/admin/users/user-123')).toBeGreaterThan(0);
      for (const [method, path] of adminSecurityActionApiPaths) {
        expect(harness.requests.wasFetched(method, path)).toBe(false);
      }
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });

      harness = await openAdminRouteWithHarness(page, '/zh/settings/system');
      await expect(page.getByTestId('settings-bento-page')).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('system-health-summary')).toBeVisible();
      await expect(page.getByTestId('duckdb-quant-panel')).toBeAttached();
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
      await expect(page.getByTestId('llm-ledger-panel')).toHaveCount(0);
      await expect(page.getByTestId('model-pricing-policy-panel')).toHaveCount(0);
      await expect(page.getByText('模型价格策略')).toHaveCount(0);
      await expect(page.getByText('配额试运行诊断')).toBeVisible();
      for (const [method, path] of primaryCostApiPaths) {
        expect(harness.requests.count(method, path)).toBeGreaterThan(0);
      }
      for (const [method, path] of secondaryCostApiPaths) {
        expect(harness.requests.count(method, path)).toBe(0);
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

      harness = await openAdminRouteWithHarness(page, '/zh/settings/system', {
        capabilities: ['cost:observability:read'],
      });
      await expect(page.getByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('settings-bento-page')).toHaveCount(0);
      for (const [method, path] of systemApiPaths) {
        expect(harness.requests.wasFetched(method, path)).toBe(false);
      }
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });

      harness = await openAdminRouteWithHarness(page, '/zh/admin/users/user-123?tab=security', {
        capabilities: ['cost:observability:read'],
      });
      await expect(page.getByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByRole('heading', { name: '安全控制 S1' })).toHaveCount(0);
      await expect(page.getByTestId('security-action-disable')).toHaveCount(0);
      expect(harness.requests.wasFetched('GET', '/api/v1/admin/users/user-123')).toBe(false);
      for (const [method, path] of adminSecurityActionApiPaths) {
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
      await expandProviderCircuitSecondaryDiagnostics(page);
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

      harness = await openAdminRouteWithHarness(page, '/zh/settings/system', {
        capabilities: ['ops:providers:read'],
      });
      await expect(page.getByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('settings-bento-page')).toHaveCount(0);
      for (const [method, path] of systemApiPaths) {
        expect(harness.requests.wasFetched(method, path)).toBe(false);
      }
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });

      harness = await openAdminRouteWithHarness(page, '/zh/admin/users/user-123?tab=security', {
        capabilities: ['ops:providers:read'],
      });
      await expect(page.getByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByRole('heading', { name: '安全控制 S1' })).toHaveCount(0);
      await expect(page.getByTestId('security-action-disable')).toHaveCount(0);
      expect(harness.requests.wasFetched('GET', '/api/v1/admin/users/user-123')).toBe(false);
      for (const [method, path] of adminSecurityActionApiPaths) {
        expect(harness.requests.wasFetched(method, path)).toBe(false);
      }
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  test('renders user security denial for read-only user admins without calling security actions', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openAdminRouteWithHarness(page, '/zh/admin/users/user-123?tab=security', {
        capabilities: ['users:read'],
      });

      await expect(page.getByRole('heading', { name: '不可执行安全操作' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText('当前账号缺少用户安全写入权限，前端不会渲染禁用、启用或撤销会话按钮。')).toBeVisible();
      await expect(page.getByRole('button', { name: '禁用账户' })).toHaveCount(0);
      await expect(page.getByRole('button', { name: '撤销全部会话' })).toHaveCount(0);
      expect(harness.requests.count('GET', '/api/v1/admin/users/user-123')).toBeGreaterThan(0);
      for (const [method, path] of adminSecurityActionApiPaths) {
        expect(harness.requests.wasFetched(method, path)).toBe(false);
      }
      await expectAdminRouteShellClean(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  test('keeps fallback-disabled legacy admin rehearsal least-privilege and redacted', async ({ page }) => {
    const deniedRoutes = [
      {
        path: '/zh/admin/cost-observability',
        hidden: page.getByTestId('quota-dry-run-panel'),
        blockedApis: costApiPaths,
      },
      {
        path: '/zh/admin/provider-circuits',
        hidden: page.getByRole('heading', { name: 'Provider 熔断诊断' }),
        blockedApis: providerCircuitApiPaths,
      },
      {
        path: '/zh/settings/system',
        hidden: page.getByTestId('settings-bento-page'),
        blockedApis: systemApiPaths,
      },
      {
        path: '/zh/admin/users/user-123?tab=security',
        hidden: page.getByRole('heading', { name: '安全控制 S1' }),
        blockedApis: [
          ['GET', '/api/v1/admin/users/user-123'],
          ...adminSecurityActionApiPaths,
        ] as const,
      },
    ];

    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      for (const route of deniedRoutes) {
        const harness = await openAdminRouteWithHarness(page, route.path, {
          capabilities: [],
          injectRawAuthCanaries: true,
          legacyAdmin: true,
          rbacFallbackDisabledRehearsal: true,
        });

        await expect(page.getByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeVisible({ timeout: 15_000 });
        await expect(route.hidden).toHaveCount(0);
        for (const [method, path] of route.blockedApis) {
          expect(harness.requests.wasFetched(method, path)).toBe(false);
        }
        await expectAdminRouteShellClean(page);
        await page.unrouteAll({ behavior: 'ignoreErrors' });
      }
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
