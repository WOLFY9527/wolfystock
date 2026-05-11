import { expect, expectNoHorizontalOverflow, openAdminRouteWithHarness, test } from './fixtures/adminAuth';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

const writeMethodPattern = /^(POST|PUT|PATCH|DELETE) /;
const forbiddenApprovalPattern =
  /launch[-\s]?approved|production[-\s]?ready|automatic[-\s]?go|自动\s*go|上线批准|生产就绪|批准上线|批准发布/i;
const launchApprovalAffordancePattern =
  /upload|上传|file|文件|write|写入|提交|保存|approve|approval|批准|launch[-\s]?approved|production[-\s]?ready|automatic[-\s]?go|上线批准|生产就绪|批准上线|批准发布/i;
const expectedWorkflowSteps = [
  '本地工作区',
  '生成模板',
  '脱敏填写',
  'preflight',
  'manifest / bundle / archive',
  '人工复核',
];
const localWorkspaceLabels = [
  '本地证据草稿',
  '脱敏输出目录',
  '复核归档目录',
  '本机忽略规则',
];
test.describe('admin evidence workflow read-only regression', () => {
  test('renders the read-only evidence workflow for ops-log admins on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openAdminRouteWithHarness(page, '/zh/admin/evidence-workflow', {
        capabilities: ['ops:logs:read'],
      });

      const workflowPage = page.getByTestId('admin-evidence-workflow-page');
      await expect(workflowPage).toBeVisible({ timeout: 15_000 });
      await expect(page.getByRole('heading', { name: '证据工作流复核' })).toBeVisible();
      await expect(page.getByText('只读视图')).toBeVisible();
      await expect(page.getByText('页面不执行动作')).toBeVisible();
      const workflowGrid = page.getByTestId('admin-evidence-workflow-grid');
      for (const step of expectedWorkflowSteps) {
        await expect(workflowGrid.getByText(step)).toBeVisible();
      }
      const workflowLabels = await workflowGrid.locator('h3').allInnerTexts();
      expect(workflowLabels).toEqual(expectedWorkflowSteps);
      const guardPanel = page.getByTestId('admin-evidence-local-workspace-guard');
      await expect(guardPanel.getByRole('heading', { name: '本地目录保护' })).toBeVisible();
      for (const label of localWorkspaceLabels) {
        await expect(guardPanel.getByText(label)).toBeVisible();
      }
      expect(await guardPanel.innerText()).not.toMatch(/^\/|\/Users\/|file:|https?:|\.env/i);
      const statusGrid = page.getByTestId('admin-evidence-status-grid');
      await expect(statusGrid.getByText('manual review required')).toBeVisible();
      await expect(statusGrid.getByText('releaseApproved=false')).toBeVisible();
      await expectNoHorizontalOverflow(page);
      if (viewport.width >= 1024) {
        await expect(page.getByRole('link', { name: '证据复核' })).toHaveAttribute('href', /\/zh\/admin\/evidence-workflow$/);
      } else {
        await expect(page.getByTestId('shell-mobile-active-route')).toHaveText('证据复核');
      }
      await expect(page.getByRole('link', { name: 'Evidence Review' })).toHaveCount(0);

      await expect(workflowPage.locator('input[type="file"]')).toHaveCount(0);
      await expect(workflowPage.locator('input, textarea, select, form')).toHaveCount(0);
      await expect(workflowPage.getByRole('button', { name: launchApprovalAffordancePattern })).toHaveCount(0);
      await expect(workflowPage.getByRole('link', { name: launchApprovalAffordancePattern })).toHaveCount(0);
      await expect(workflowPage.locator('[contenteditable="true"]')).toHaveCount(0);
      await expect(workflowPage.locator('[class*="bg-gray-"], [class*="bg-zinc-"], [class*="bg-slate-"], [class*="bg-neutral-"]')).toHaveCount(0);
      await expect(workflowPage).toHaveClass(/overflow-x-hidden/);
      await expect(workflowPage).toHaveClass(/no-scrollbar/);

      const rawDisclosure = page.getByTestId('admin-evidence-raw-disclosure');
      await expect(rawDisclosure).toBeVisible();
      const rawDetails = rawDisclosure.getByText('原始诊断、数据源载荷、数据结构字段和调试内容不在本视图展开');
      await expect(rawDetails).toBeHidden();

      const commandPanel = page.getByTestId('admin-evidence-command-snippets');
      await expect(commandPanel).toHaveCount(0);

      const bodyText = await page.locator('body').innerText();
      expect(bodyText).not.toMatch(forbiddenApprovalPattern);
      expect(bodyText).not.toMatch(/python3 scripts\/operator_evidence_workflow_run\.py|\/Users\/|\.env|token|secret|password|api[_-]?key|cookie|session|bearer|sk-[a-z0-9_-]{12,}/i);

      await expect(page.getByTestId('admin-evidence-runbook-references')).toHaveCount(0);
      expect(harness.requests.calls.filter((entry) => writeMethodPattern.test(entry))).toEqual([]);
      await expectNoHorizontalOverflow(page);

      await expect(page.getByTestId('admin-evidence-schema-reference')).toHaveCount(0);
      await expect(page.getByTestId('admin-evidence-schema-notes')).toHaveCount(0);

      expect(harness.requests.calls.filter((entry) => writeMethodPattern.test(entry))).toEqual([]);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  for (const capability of [
    'users:read',
    'users:activity:read',
    'users:portfolio:read',
    'users:security:write',
    'cost:observability:read',
    'ops:providers:read',
    'ops:notifications:read',
    'ops:system_config:read',
  ] as const) {
    test(`blocks the route and hides the nav affordance for adjacent ${capability}`, async ({ page }) => {
      const harness = await openAdminRouteWithHarness(page, '/zh/admin/evidence-workflow', {
        capabilities: [capability],
      });

      await expect(page.getByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('admin-evidence-workflow-page')).toHaveCount(0);
      await expect(page.getByRole('link', { name: '证据复核' })).toHaveCount(0);
      await expectNoHorizontalOverflow(page);

      const bodyText = await page.locator('body').innerText();
      expect(bodyText).not.toMatch(forbiddenApprovalPattern);
      expect(harness.requests.calls.filter((entry) => writeMethodPattern.test(entry))).toEqual([]);
    });
  }
});
