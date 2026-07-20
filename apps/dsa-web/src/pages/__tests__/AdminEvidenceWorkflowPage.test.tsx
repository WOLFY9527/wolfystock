import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AdminEvidenceWorkflowPage from '../AdminEvidenceWorkflowPage';

vi.mock('../../components/evidence/AdminEvidenceDiagnosticsConsole', () => ({
  AdminEvidenceDiagnosticsConsole: () => (
    <section data-testid="mock-admin-evidence-diagnostics-console">
      live diagnostics console
    </section>
  ),
}));

vi.mock('../../components/evidence/AdminEvidenceDryRunPreview', () => ({
  AdminEvidenceDryRunPreview: () => (
    <section data-testid="mock-admin-evidence-dry-run-preview">
      dry-run preview
    </section>
  ),
}));

const workflowSteps = [
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

const runbookReferences = [
  ['Dry-run 交接', 'docs/operations/operator-evidence.md#dry-run-handoff', '合成演练材料'],
  ['脱敏清单', 'docs/operations/operator-evidence.md#redaction', '交接前检查'],
  ['Schema 参考', 'docs/operations/operator-evidence.md#schema-reference', '本地字段说明'],
  ['归档包', 'docs/operations/operator-evidence.md#review-package', '复核目录索引'],
  ['CLI 合约 / 预检', 'docs/operations/operator-evidence.md#cli-contract', '离线 runner'],
];

const disclosureTitles = {
  diagnostics: 'L4 已脱敏诊断与试运行预览：2 个只读模块',
  runbook: 'L3 Runbook 参考：5 份本地手册 / 静态只读',
  schema: 'L3 Schema 参考：8 类离线证据 / 字段规则另见脱敏说明',
  offline: 'L3 离线命令与 NO-GO 说明：4 个静态片段 / 只读',
} as const;

function openEvidenceDisclosure(title: string) {
  fireEvent.click(screen.getByRole('button', { name: `展开 ${title}` }));
}

describe('AdminEvidenceWorkflowPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders one operational verdict, bounded module status, and the offline evidence workflow sequence', () => {
    render(<AdminEvidenceWorkflowPage />);

    const page = screen.getByTestId('admin-evidence-workflow-page');
    const overviewStrip = screen.getByTestId('admin-evidence-l0-overview-strip');
    const verdict = within(page).getByTestId('admin-evidence-operational-verdict');
    expect(screen.getByText('证据复核总览')).toBeInTheDocument();
    expect(page).not.toHaveTextContent('ADMIN EVIDENCE REVIEW');
    expect(within(overviewStrip).getByText('信任状态')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('影响范围')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('建议动作')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('证据参考')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('最近更新')).toBeInTheDocument();
    expect(within(verdict).getByText('等待人工复核')).toBeInTheDocument();
    expect(within(verdict).getByText('先生成空白模板并脱敏填写，再运行 preflight。')).toBeInTheDocument();

    const workflowGrid = screen.getByTestId('admin-evidence-workflow-grid');
    const statusGrid = screen.getByTestId('admin-evidence-status-grid');
    workflowSteps.forEach((step) => {
      expect(within(workflowGrid).getByText(step)).toBeInTheDocument();
    });
    expect(within(statusGrid).getAllByTestId('admin-evidence-module-status')).toHaveLength(4);
    expect(within(statusGrid).getByText('NO-GO when evidence missing')).toBeInTheDocument();
    expect(within(statusGrid).getByText('manual review required')).toBeInTheDocument();
    expect(within(statusGrid).getByText('releaseApproved=false')).toBeInTheDocument();
    expect(page).toHaveTextContent('缺证据时保持 NO-GO');
  });

  it('keeps diagnostics and dry-run preview collapsed after the operator workflow by default', () => {
    render(<AdminEvidenceWorkflowPage />);

    const workflowGrid = screen.getByTestId('admin-evidence-workflow-grid');
    const diagnosticsDisclosure = screen.getByTestId('admin-evidence-diagnostics-disclosure');

    expect(within(screen.getByTestId('admin-evidence-workflow-page')).queryByTestId('mock-admin-evidence-diagnostics-console')).not.toBeInTheDocument();
    expect(within(screen.getByTestId('admin-evidence-workflow-page')).queryByTestId('mock-admin-evidence-dry-run-preview')).not.toBeInTheDocument();
    expect(Boolean(workflowGrid.compareDocumentPosition(diagnosticsDisclosure) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);

    openEvidenceDisclosure(disclosureTitles.diagnostics);
    expect(within(diagnosticsDisclosure).getByTestId('mock-admin-evidence-diagnostics-console')).toBeInTheDocument();
    expect(within(diagnosticsDisclosure).getByTestId('mock-admin-evidence-dry-run-preview')).toBeInTheDocument();
  });

  it('surfaces the L0 verdict and action hint before the L2 operator path', () => {
    render(<AdminEvidenceWorkflowPage />);

    const page = screen.getByTestId('admin-evidence-workflow-page');
    const verdict = screen.getByTestId('admin-evidence-operational-verdict');
    const statusGrid = screen.getByTestId('admin-evidence-status-grid');
    const workflowGrid = screen.getByTestId('admin-evidence-workflow-grid');

    expect(within(verdict).getByText('L0 运维结论')).toBeInTheDocument();
    expect(within(verdict).getByText('等待人工复核')).toBeInTheDocument();
    expect(within(verdict).getByText('缺证据时保持 NO-GO；本页只展示复核路径，不提供审批动作。')).toBeInTheDocument();
    expect(within(verdict).getByText('先生成空白模板并脱敏填写，再运行 preflight。')).toBeInTheDocument();
    expect(Boolean(verdict.compareDocumentPosition(statusGrid) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(statusGrid.compareDocumentPosition(workflowGrid) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(page.querySelectorAll('[data-testid="admin-evidence-operational-verdict"]')).toHaveLength(1);
  });

  it('renders the preflight and manual review sequence in order', () => {
    render(<AdminEvidenceWorkflowPage />);

    const workflowGrid = screen.getByTestId('admin-evidence-workflow-grid');
    const renderedLabels = workflowSteps.map((step) => within(workflowGrid).getByText(step));
    renderedLabels.reduce((previous, current) => {
      expect(previous.compareDocumentPosition(current) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      return current;
    });
  });

  it('renders local workspace guard labels without absolute paths', () => {
    render(<AdminEvidenceWorkflowPage />);

    const guardPanel = screen.getByTestId('admin-evidence-local-workspace-guard');
    expect(within(guardPanel).getByRole('heading', { name: '本地目录边界' })).toBeInTheDocument();
    expect(guardPanel).not.toHaveTextContent('LOCAL GUARD');
    localWorkspaceLabels.forEach((label) => {
      expect(within(guardPanel).getByText(label)).toBeInTheDocument();
    });
    expect(guardPanel.textContent || '').not.toMatch(/^\/|\/Users\/|file:|https?:|\.env/i);
  });

  it('does not render upload, mutation, or launch approval actions', () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);

    render(<AdminEvidenceWorkflowPage />);

    const drillLinks = screen.getAllByRole('link');
    expect(drillLinks.length).toBeGreaterThan(0);
    drillLinks.forEach((link) => {
      expect(link.getAttribute('href') || '').toMatch(/^\/zh\/admin\/(logs|evidence-workflow|market-providers|provider-circuits|cost-observability)(\?|#|$)/);
    });
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(document.querySelector('form')).not.toBeInTheDocument();
    expect(document.querySelector('input[type="file"]')).not.toBeInTheDocument();
    expect(document.querySelector('input, textarea, select, form, [contenteditable="true"]')).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/upload|上传|file|文件/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /upload|上传|提交|保存|approve|approval|批准/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /upload|上传|write|写入|提交|保存|approve|approval|批准/i })).not.toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('renders sanitized drill-through links for logs, provider ops, circuits, and cost follow-up', () => {
    render(<AdminEvidenceWorkflowPage />);

    const page = screen.getByTestId('admin-evidence-workflow-page');
    expect(within(page).getByText('已脱敏引用')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /查看相关日志/i })).toHaveAttribute('href', '/zh/admin/logs?tab=business&query=evidence&since=24h');
    expect(screen.getByRole('link', { name: /查看数据源维护/i })).toHaveAttribute('href', '/zh/admin/market-providers?surface=market_overview');
    expect(screen.getByRole('link', { name: /查看熔断与配额/i })).toHaveAttribute('href', '/zh/admin/provider-circuits?provider=provider&since=24h');
    expect(screen.getByRole('link', { name: /查看成本观测/i })).toHaveAttribute('href', '/zh/admin/cost-observability?window=24h&area=llm');
    expect(page).not.toHaveTextContent('token');
    expect(page).not.toHaveTextContent('secret');
    expect(page).not.toHaveTextContent('payload');
  });

  it('renders static local runbook reference cards for the operator workflow', () => {
    render(<AdminEvidenceWorkflowPage />);

    openEvidenceDisclosure(disclosureTitles.runbook);
    const runbookPanel = screen.getByTestId('admin-evidence-runbook-references');
    expect(within(runbookPanel).getByRole('heading', { name: '操作员工作流参考' })).toBeInTheDocument();
    expect(within(runbookPanel).getByText('静态标签')).toBeInTheDocument();

    runbookReferences.forEach(([label, docLabel, stage]) => {
      const card = within(runbookPanel).getByRole('article', { name: `${label}：${docLabel}` });
      expect(within(card).getByText(label)).toBeInTheDocument();
      expect(within(card).getByText(docLabel)).toBeInTheDocument();
      expect(within(card).getByText(stage)).toBeInTheDocument();
      expect(docLabel).not.toMatch(/^\/|\/Users\/|file:|https?:/i);
    });
  });

  it('keeps runbook reference cards static and read-only', () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);

    render(<AdminEvidenceWorkflowPage />);

    openEvidenceDisclosure(disclosureTitles.runbook);
    const runbookPanel = screen.getByTestId('admin-evidence-runbook-references');
    expect(within(runbookPanel).queryByRole('button')).not.toBeInTheDocument();
    expect(within(runbookPanel).queryByRole('link')).not.toBeInTheDocument();
    expect(within(runbookPanel).queryByRole('textbox')).not.toBeInTheDocument();
    expect(runbookPanel.querySelector('input, textarea, select, form, [contenteditable="true"]')).not.toBeInTheDocument();
    expect(runbookPanel.textContent || '').not.toMatch(/上传|写入|提交|保存|批准上线|批准发布|launch[- ]?approved|production[- ]?ready|automatic[- ]?go/i);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('renders a static schema reference panel for all offline evidence categories', () => {
    render(<AdminEvidenceWorkflowPage />);

    openEvidenceDisclosure(disclosureTitles.schema);
    const referencePanel = screen.getByTestId('admin-evidence-schema-reference');
    expect(within(referencePanel).getByRole('heading', { name: '离线证据数据结构参考' })).toBeInTheDocument();
    expect(within(referencePanel).getByText('人工复核必需')).toBeInTheDocument();
    expect(within(referencePanel).getAllByText('manual review required')).toHaveLength(schemaReferenceGroups.length);
    expect(within(referencePanel).getAllByText('releaseApproved=false')).toHaveLength(schemaReferenceGroups.length);

    schemaReferenceGroups.forEach(([label, artifact, validator]) => {
      const group = within(referencePanel).getByRole('article', { name: `${label}：${artifact}` });
      expect(within(group).getByText(label)).toBeInTheDocument();
      expect(within(group).getByText(artifact)).toBeInTheDocument();
      expect(within(group).getByText(validator)).toBeInTheDocument();
      expect(within(group).getByText('本地校验')).toBeInTheDocument();
    });
  });

  it('keeps the schema reference panel static and read-only', () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);

    render(<AdminEvidenceWorkflowPage />);

    openEvidenceDisclosure(disclosureTitles.schema);
    const referencePanel = screen.getByTestId('admin-evidence-schema-reference');
    expect(within(referencePanel).queryByRole('button', { name: /upload|上传|write|写入|提交|保存|approve|approval|批准/i })).not.toBeInTheDocument();
    expect(within(referencePanel).queryByRole('link')).not.toBeInTheDocument();
    expect(within(referencePanel).queryByRole('textbox')).not.toBeInTheDocument();
    expect(referencePanel.querySelector('input, textarea, select, form, [contenteditable="true"]')).not.toBeInTheDocument();
    expect(referencePanel.textContent || '').not.toMatch(/上传|写入|提交|保存|批准上线|批准发布|launch[- ]?approved|production[- ]?ready|automatic[- ]?go/i);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('renders static copy-safe offline command snippets without secrets or real paths', () => {
    render(<AdminEvidenceWorkflowPage />);

    openEvidenceDisclosure(disclosureTitles.offline);
    const commandPanel = screen.getByTestId('admin-evidence-command-snippets');
    const commandText = commandPanel.textContent || '';

    expect(commandText).toContain('python3 scripts/operator_evidence_workflow_run.py init --output-dir <templates-dir>');
    expect(commandText).toContain('python3 scripts/operator_evidence_workflow_run.py check --artifact-dir <sanitized-evidence-dir> --output-dir <review-output-dir>');
    expect(commandText).toContain('python3 scripts/operator_evidence_workflow_run.py report --bundle-summary <review-output-dir>/bundle-summary.json --output <review-output-dir>/release-review-report.md');
    expect(commandText).not.toMatch(/\/Users\/|\.env|token|secret|password|api[_-]?key|cookie|session|bearer|sk-[a-z0-9_-]{12,}/i);
    expect(within(commandPanel).queryByRole('button')).not.toBeInTheDocument();
    expect(within(commandPanel).queryByRole('link')).not.toBeInTheDocument();
    expect(within(commandPanel).queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('keeps command snippets and raw details keyboard-focusable without adding write controls', () => {
    render(<AdminEvidenceWorkflowPage />);

    openEvidenceDisclosure(disclosureTitles.offline);
    const commandSnippets = screen.getAllByRole('group', { name: /可复制命令/ });
    expect(commandSnippets).toHaveLength(3);
    commandSnippets.forEach((snippet) => {
      expect(snippet).toHaveAttribute('tabIndex', '0');
      snippet.focus();
      expect(snippet).toHaveFocus();
      expect(snippet).toHaveClass('focus-visible:ring-2');
    });

    const disclosure = screen.getByTestId('admin-evidence-raw-disclosure');
    const toggle = within(disclosure).getByRole('button', { name: '展开 L4 原始内容边界：已排除数据结构 / 数据源 / 调试字段' });
    toggle.focus();
    expect(toggle).toHaveFocus();
    expect(toggle.closest('[data-terminal-primitive="disclosure"]')).not.toBeNull();
  });

  it('keeps review status language constrained to manual and missing-evidence states', () => {
    render(<AdminEvidenceWorkflowPage />);

    const statusGrid = screen.getByTestId('admin-evidence-status-grid');
    expect(within(statusGrid).getAllByTestId('admin-evidence-module-status')).toHaveLength(4);
    expect(within(statusGrid).getByText('复核入口')).toBeInTheDocument();
    expect(within(statusGrid).getByText('NO-GO when evidence missing')).toBeInTheDocument();
    expect(within(statusGrid).getByText('manual review required')).toBeInTheDocument();
    expect(within(statusGrid).getByText('releaseApproved=false')).toBeInTheDocument();
    expect(statusGrid.textContent || '').not.toMatch(/automatic[- ]?go|production[- ]?ready|launch[- ]?approved/i);
  });

  it('keeps launch approval wording out of the rendered review view', () => {
    render(<AdminEvidenceWorkflowPage />);

    const pageText = screen.getByTestId('admin-evidence-workflow-page').textContent || '';
    expect(pageText).not.toMatch(/launch-approved|launch\s+approved|production-ready|production\s+ready|automatic[- ]?go|自动\s*go|上线批准|生产就绪|批准上线|批准发布/i);
  });

  it('keeps raw and schema review notes collapsed by default', () => {
    render(<AdminEvidenceWorkflowPage />);

    const disclosure = screen.getByTestId('admin-evidence-raw-disclosure');
    expect(disclosure).not.toHaveAttribute('open');
    expect(within(disclosure).getByText('L4 原始内容边界：已排除数据结构 / 数据源 / 调试字段')).toBeInTheDocument();

    openEvidenceDisclosure(disclosureTitles.schema);
    const schemaNotes = screen.getByTestId('admin-evidence-schema-notes');
    expect(schemaNotes).not.toHaveAttribute('open');
    expect(within(schemaNotes).getByText('L4 字段与脱敏规则：仅类别 / 文件名 / 校验脚本')).toBeInTheDocument();
  });

  it('uses terminal operator primitives and responsive grid layouts', () => {
    render(<AdminEvidenceWorkflowPage />);

    const page = screen.getByTestId('admin-evidence-workflow-page');
    const workflowGrid = screen.getByTestId('admin-evidence-workflow-grid');
    const statusGrid = screen.getByTestId('admin-evidence-status-grid');
    const workflowList = workflowGrid.closest('[data-terminal-primitive="dense-list"]') ?? workflowGrid;

    expect(page).toHaveClass('overflow-y-auto', 'overflow-x-hidden', 'no-scrollbar');
    expect(page.className).not.toContain('bg-[#050505]');
    expect(page.querySelector('[data-terminal-primitive="page-shell"]')).not.toBeNull();
    expect(page.querySelectorAll('[data-terminal-primitive="chip"]').length).toBeLessThanOrEqual(8);
    expect(page.querySelectorAll('[data-terminal-primitive="nested-block"]').length).toBeLessThanOrEqual(12);
    expect(page.querySelectorAll('[data-terminal-primitive="disclosure"]').length).toBeGreaterThanOrEqual(4);
    expect(workflowList).toHaveAttribute('data-terminal-primitive', 'dense-list');
    expect(statusGrid).toHaveClass('grid-cols-1', 'md:grid-cols-2', 'xl:grid-cols-4');
  });

  it('keeps vertical shell spacing on TerminalPageShell instead of the route scroll wrapper', () => {
    render(<AdminEvidenceWorkflowPage />);

    const page = screen.getByTestId('admin-evidence-workflow-page');
    const shell = page.querySelector('[data-terminal-primitive="page-shell"]');

    expect(page).not.toHaveClass('py-5', 'md:py-6');
    expect(shell).toHaveClass('py-5', 'md:py-6');
  });
});
