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
const expectedStaticCommands = [
  'python3 scripts/operator_evidence_workflow_run.py init --output-dir <templates-dir>',
  'python3 scripts/operator_evidence_workflow_run.py check --artifact-dir <sanitized-evidence-dir> --output-dir <review-output-dir>',
  'python3 scripts/operator_evidence_workflow_run.py report --bundle-summary <review-output-dir>/bundle-summary.json --output <review-output-dir>/release-review-report.md',
];
const schemaReferenceGroups = [
  ['数据源 Provider', 'provider_operator_evidence.json', 'provider_operator_evidence_check.py'],
  ['恢复 / PITR', 'restore_pitr_operator_evidence.json', 'restore_pitr_operator_evidence_check.py'],
  ['安全验收', 'security_operator_acceptance.json', 'security_operator_acceptance_check.py'],
  ['配额预算', 'quota_budget_operator_evidence.json', 'quota_operator_evidence_check.py'],
  ['预发入口', 'staging_ingress_operator_evidence.json', 'staging_ingress_operator_evidence_check.py'],
  ['WS2 SSE 决策', 'ws2_sse_operator_decision_evidence.json', 'ws2_sse_operator_decision_check.py'],
  ['配置快照', 'config_snapshot_evidence.json', 'config_snapshot_evidence_check.py'],
  ['人工发布复核', 'manual_release_approval_review_record.json', 'manual_release_approval_evidence_check.py'],
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
      await expect(rawDisclosure).not.toHaveAttribute('open', '');
      await expect(rawDisclosure.getByText('默认折叠')).toBeVisible();
      const rawSummary = rawDisclosure.locator('summary');
      await expect(rawSummary).toHaveAccessibleName(/原始\/Schema 字段/);
      await expect(rawSummary).toHaveClass(/focus-visible:ring-2/);
      const rawDetails = rawDisclosure.getByText('原始诊断、provider 载荷、schema 字段和 debug 内容不在本视图展开');
      await expect(rawDetails).toBeHidden();
      await rawSummary.click();
      await expect(rawDisclosure).toHaveAttribute('open', '');
      await expect(rawDetails).toBeVisible();
      await expectNoHorizontalOverflow(page);
      await rawSummary.click();
      await expect(rawDisclosure).not.toHaveAttribute('open', '');

      const commandPanel = page.getByTestId('admin-evidence-command-snippets');
      await expect(commandPanel.locator('pre')).toHaveCount(3);
      await expect(commandPanel.locator('pre').first()).toHaveClass(/no-scrollbar/);
      await expect(commandPanel.locator('pre code')).toHaveText(expectedStaticCommands);
      for (const command of expectedStaticCommands) {
        await expect(commandPanel.getByText(command)).toBeVisible();
        expect(command).toMatch(/<[^>]+>/);
        expect(command).not.toMatch(/\/Users\/|\.env|token|secret|password|api[_-]?key|cookie|session|bearer|sk-[a-z0-9_-]{12,}/i);
        expect(command).not.toMatch(/--approve|--approval|--upload|--write|--launch|releaseApproved=true/i);
      }
      await expect(commandPanel.getByRole('group', { name: /可复制命令/ })).toHaveCount(3);
      await expect(commandPanel.getByRole('button')).toHaveCount(0);
      for (const snippet of await commandPanel.getByRole('group', { name: /可复制命令/ }).all()) {
        await expect(snippet).toHaveAttribute('tabindex', '0');
        await expect(snippet).toHaveClass(/focus-visible:ring-2/);
        await snippet.focus();
        await expect(snippet).toBeFocused();
      }

      const bodyText = await page.locator('body').innerText();
      expect(bodyText).not.toMatch(forbiddenApprovalPattern);

      const schemaReference = page.getByTestId('admin-evidence-schema-reference');
      await expect(schemaReference).toBeVisible();
      await expect(schemaReference.getByRole('heading', { name: '离线证据 Schema 参考' })).toBeVisible();
      await expect(schemaReference.getByText('人工复核必需')).toBeVisible();
      for (const [label, artifact, validator] of schemaReferenceGroups) {
        const group = schemaReference.getByRole('article', { name: `${label}：${artifact}` });
        await expect(group).toBeVisible();
        await expect(group.getByRole('heading', { name: label })).toBeVisible();
        await expect(group.getByText(artifact)).toBeVisible();
        await expect(group.getByText(validator)).toBeVisible();
        await expect(group.getByText('manual review required')).toBeVisible();
        await expect(group.getByText('releaseApproved=false')).toBeVisible();
      }
      await expect(schemaReference.getByRole('button')).toHaveCount(0);
      await expect(schemaReference.getByRole('link')).toHaveCount(0);
      await expect(schemaReference.locator('input, textarea, select, form, [contenteditable="true"]')).toHaveCount(0);
      const schemaNotes = page.getByTestId('admin-evidence-schema-notes');
      await expect(schemaNotes).toBeVisible();
      await expect(schemaNotes).not.toHaveAttribute('open', '');
      await expect(schemaNotes.getByText('字段细节与脱敏规则')).toBeVisible();
      await expect(schemaNotes.getByText('字段清单、原始 schema、provider 载荷和 debug 细节不在页面默认展开')).toBeHidden();

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
