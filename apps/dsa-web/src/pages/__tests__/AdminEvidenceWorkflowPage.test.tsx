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
  ['Dry-run 交接', 'docs/audits/operator-evidence-dry-run-handoff.md', '合成演练材料'],
  ['脱敏清单', 'docs/audits/operator-evidence-redaction-checklist.md', '交接前检查'],
  ['Schema 参考', 'docs/audits/operator-evidence-schema-reference-guide.md', '本地字段说明'],
  ['归档包', 'docs/audits/operator-evidence-archive-pack-guide.md', '复核目录索引'],
  ['CLI 合约 / 预检', 'docs/audits/operator-evidence-workflow-runner-guide.md', '离线 runner'],
];

function openEvidenceDisclosure(title: string) {
  fireEvent.click(screen.getByRole('button', { name: `展开 ${title}` }));
}

describe('AdminEvidenceWorkflowPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders the offline evidence workflow sequence and static review states', () => {
    render(<AdminEvidenceWorkflowPage />);

    const page = screen.getByTestId('admin-evidence-workflow-page');
    expect(within(page).getByTestId('mock-admin-evidence-diagnostics-console')).toBeInTheDocument();
    expect(within(page).getByTestId('mock-admin-evidence-dry-run-preview')).toBeInTheDocument();
    const workflowGrid = screen.getByTestId('admin-evidence-workflow-grid');
    const statusGrid = screen.getByTestId('admin-evidence-status-grid');
    workflowSteps.forEach((step) => {
      expect(within(workflowGrid).getByText(step)).toBeInTheDocument();
    });
    expect(within(statusGrid).getByText('GO-REVIEW-REQUIRED')).toBeInTheDocument();
    expect(within(statusGrid).getByText('NO-GO when evidence missing')).toBeInTheDocument();
    expect(within(statusGrid).getByText('manual review required')).toBeInTheDocument();
    expect(within(statusGrid).getByText('releaseApproved=false')).toBeInTheDocument();
    expect(page).toHaveTextContent('缺证据时保持 NO-GO');
  });

  it('renders the diagnostics console and dry-run preview before the offline workflow reference blocks', () => {
    render(<AdminEvidenceWorkflowPage />);

    const consoleBlock = screen.getByTestId('mock-admin-evidence-diagnostics-console');
    const dryRunPreview = screen.getByTestId('mock-admin-evidence-dry-run-preview');
    const workflowGrid = screen.getByTestId('admin-evidence-workflow-grid');

    expect(Boolean(consoleBlock.compareDocumentPosition(workflowGrid) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(dryRunPreview.compareDocumentPosition(workflowGrid) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it('surfaces purpose, current state, and next operator action in the hero', () => {
    render(<AdminEvidenceWorkflowPage />);

    const page = screen.getByTestId('admin-evidence-workflow-page');
    expect(within(page).getByText('页面用途')).toBeInTheDocument();
    expect(within(page).getByText('当前状态')).toBeInTheDocument();
    expect(within(page).getByText('下一步')).toBeInTheDocument();
    expect(within(page).getByText('复核脱敏证据路径')).toBeInTheDocument();
    expect(within(page).getByText('等待人工复核')).toBeInTheDocument();
    expect(within(page).getByText('按本地操作手册生成复核材料')).toBeInTheDocument();
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
    expect(within(guardPanel).getByRole('heading', { name: '本地目录保护' })).toBeInTheDocument();
    localWorkspaceLabels.forEach((label) => {
      expect(within(guardPanel).getByText(label)).toBeInTheDocument();
    });
    expect(guardPanel.textContent || '').not.toMatch(/^\/|\/Users\/|file:|https?:|\.env/i);
  });

  it('does not render upload, mutation, or launch approval actions', () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);

    render(<AdminEvidenceWorkflowPage />);

    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(document.querySelector('form')).not.toBeInTheDocument();
    expect(document.querySelector('input[type="file"]')).not.toBeInTheDocument();
    expect(document.querySelector('input, textarea, select, form, [contenteditable="true"]')).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/upload|上传|file|文件/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /upload|上传|write|写入|提交|保存|approve|approval|批准/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /upload|上传|write|写入|提交|保存|approve|approval|批准/i })).not.toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('renders static local runbook reference cards for the operator workflow', () => {
    render(<AdminEvidenceWorkflowPage />);

    openEvidenceDisclosure('二级细节：Runbook 参考');
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

    openEvidenceDisclosure('二级细节：Runbook 参考');
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

    openEvidenceDisclosure('二级细节：Schema 与字段参考');
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

    openEvidenceDisclosure('二级细节：Schema 与字段参考');
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

    openEvidenceDisclosure('二级细节：离线命令与空状态说明');
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

    openEvidenceDisclosure('二级细节：离线命令与空状态说明');
    const commandSnippets = screen.getAllByRole('group', { name: /可复制命令/ });
    expect(commandSnippets).toHaveLength(3);
    commandSnippets.forEach((snippet) => {
      expect(snippet).toHaveAttribute('tabIndex', '0');
      snippet.focus();
      expect(snippet).toHaveFocus();
      expect(snippet).toHaveClass('focus-visible:ring-2');
    });

    const disclosure = screen.getByTestId('admin-evidence-raw-disclosure');
    const toggle = within(disclosure).getByRole('button', { name: '展开 原始 / 数据结构 / 数据源 / 调试字段' });
    toggle.focus();
    expect(toggle).toHaveFocus();
    expect(toggle).toHaveClass('rounded-lg');
  });

  it('keeps review status language constrained to manual and missing-evidence states', () => {
    render(<AdminEvidenceWorkflowPage />);

    const statusGrid = screen.getByTestId('admin-evidence-status-grid');
    expect(within(statusGrid).getByRole('article', { name: '复核入口：GO-REVIEW-REQUIRED' })).toBeInTheDocument();
    expect(within(statusGrid).getByRole('article', { name: '缺证据状态：NO-GO when evidence missing' })).toBeInTheDocument();
    expect(within(statusGrid).getByRole('article', { name: '人工门禁：manual review required' })).toBeInTheDocument();
    expect(within(statusGrid).getByRole('article', { name: '发布字段：releaseApproved=false' })).toBeInTheDocument();
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
    expect(within(disclosure).getByText('原始 / 数据结构 / 数据源 / 调试字段')).toBeInTheDocument();

    openEvidenceDisclosure('二级细节：Schema 与字段参考');
    const schemaNotes = screen.getByTestId('admin-evidence-schema-notes');
    expect(schemaNotes).not.toHaveAttribute('open');
    expect(within(schemaNotes).getByText('字段细节与脱敏规则')).toBeInTheDocument();
  });

  it('uses terminal operator primitives and responsive grid layouts', () => {
    render(<AdminEvidenceWorkflowPage />);

    openEvidenceDisclosure('二级细节：Runbook 参考');
    openEvidenceDisclosure('二级细节：离线命令与空状态说明');
    const page = screen.getByTestId('admin-evidence-workflow-page');
    const workflowGrid = screen.getByTestId('admin-evidence-workflow-grid');
    const statusGrid = screen.getByTestId('admin-evidence-status-grid');
    const commandGrid = screen.getByTestId('admin-evidence-command-snippets').querySelector('.grid');
    const runbookGrid = screen.getByTestId('admin-evidence-runbook-references').querySelector('.grid');

    expect(page).toHaveClass('overflow-y-auto', 'overflow-x-hidden', 'no-scrollbar');
    expect(page.className).not.toContain('bg-[#050505]');
    expect(page.querySelector('[data-terminal-primitive="page-shell"]')).not.toBeNull();
    expect(page.querySelectorAll('[data-terminal-primitive="panel"]').length).toBeGreaterThan(5);
    expect(page.querySelectorAll('[data-terminal-primitive="chip"]').length).toBeGreaterThan(5);
    expect(page.querySelectorAll('[data-terminal-primitive="disclosure"]').length).toBeGreaterThan(3);
    expect(page.querySelectorAll('[data-terminal-primitive="nested-block"]').length).toBeGreaterThan(10);
    expect(workflowGrid).toHaveClass('grid-cols-1', 'xl:grid-cols-6');
    expect(statusGrid).toHaveClass('grid-cols-1', 'md:grid-cols-2', 'xl:grid-cols-4');
    expect(commandGrid).toHaveClass('grid-cols-1', 'xl:grid-cols-3');
    expect(runbookGrid).toHaveClass('grid-cols-1', 'md:grid-cols-2', 'xl:grid-cols-5');
  });

  it('keeps vertical shell spacing on TerminalPageShell instead of the route scroll wrapper', () => {
    render(<AdminEvidenceWorkflowPage />);

    const page = screen.getByTestId('admin-evidence-workflow-page');
    const shell = page.querySelector('[data-terminal-primitive="page-shell"]');

    expect(page).not.toHaveClass('py-5', 'md:py-6');
    expect(shell).toHaveClass('py-5', 'md:py-6');
  });
});
