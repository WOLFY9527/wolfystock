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

      const rawDisclosure = page.getByTestId('admin-evidence-raw-disclosure');
      await expect(rawDisclosure).toBeVisible();
      await expect(rawDisclosure).not.toHaveAttribute('open', '');
      await expect(rawDisclosure.getByText('默认折叠')).toBeVisible();

      const commandPanel = page.getByTestId('admin-evidence-command-snippets');
      await expect(commandPanel.getByText('python3 scripts/operator_evidence_workflow_run.py init --output-dir <templates-dir>')).toBeVisible();
      await expect(commandPanel.getByText('python3 scripts/operator_evidence_workflow_run.py check --artifact-dir <sanitized-evidence-dir> --output-dir <review-output-dir>')).toBeVisible();
      await expect(commandPanel.getByText('python3 scripts/operator_evidence_workflow_run.py report --bundle-summary <review-output-dir>/bundle-summary.json --output <review-output-dir>/release-review-report.md')).toBeVisible();
      await expect(commandPanel.getByRole('group', { name: /可复制命令/ })).toHaveCount(3);
      await expect(commandPanel.getByRole('button')).toHaveCount(0);

      const bodyText = await page.locator('body').innerText();
      expect(bodyText).not.toMatch(forbiddenApprovalPattern);
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
