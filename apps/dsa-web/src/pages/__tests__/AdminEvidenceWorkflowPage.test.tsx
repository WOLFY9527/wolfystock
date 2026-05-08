import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import AdminEvidenceWorkflowPage from '../AdminEvidenceWorkflowPage';

const workflowSteps = [
  '模板生成',
  '人工填写脱敏证据',
  '分类校验',
  'manifest 校验',
  'bundle 聚合',
  'review report 渲染',
  '人工复核',
];

describe('AdminEvidenceWorkflowPage', () => {
  it('renders the offline evidence workflow sequence and static review states', () => {
    render(<AdminEvidenceWorkflowPage />);

    const page = screen.getByTestId('admin-evidence-workflow-page');
    const workflowGrid = screen.getByTestId('admin-evidence-workflow-grid');
    workflowSteps.forEach((step) => {
      expect(within(workflowGrid).getByText(step)).toBeInTheDocument();
    });
    expect(within(page).getByText('GO-REVIEW-REQUIRED')).toBeInTheDocument();
    expect(within(page).getByText('NO-GO when evidence missing')).toBeInTheDocument();
    expect(within(page).getByText('manual review required')).toBeInTheDocument();
    expect(within(page).getByText('releaseApproved=false')).toBeInTheDocument();
    expect(within(page).getByText('缺少证据时保持 NO-GO')).toBeInTheDocument();
  });

  it('does not render upload, mutation, or launch approval actions', () => {
    render(<AdminEvidenceWorkflowPage />);

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(document.querySelector('input[type="file"]')).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/upload|上传|file|文件/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /upload|上传|write|写入|提交|保存|approve|approval|批准/i })).not.toBeInTheDocument();
  });

  it('renders static copy-safe offline command snippets without secrets or real paths', () => {
    render(<AdminEvidenceWorkflowPage />);

    const commandPanel = screen.getByTestId('admin-evidence-command-snippets');
    const commandText = commandPanel.textContent || '';

    expect(commandText).toContain('python3 scripts/operator_evidence_workflow_run.py init --output-dir <templates-dir>');
    expect(commandText).toContain('python3 scripts/operator_evidence_workflow_run.py check --artifact-dir <sanitized-evidence-dir> --output-dir <review-output-dir>');
    expect(commandText).toContain('python3 scripts/operator_evidence_workflow_run.py report --bundle-summary <review-output-dir>/bundle-summary.json --output <review-output-dir>/release-review-report.md');
    expect(commandText).not.toMatch(/\/Users\/|\.env|token|secret|password|api[_-]?key|cookie|session/i);
  });

  it('keeps launch approval wording out of the rendered review view', () => {
    render(<AdminEvidenceWorkflowPage />);

    const pageText = screen.getByTestId('admin-evidence-workflow-page').textContent || '';
    expect(pageText).not.toMatch(/launch-approved|production-ready|automatic[- ]?go|自动\s*go|上线批准|生产就绪|批准上线|批准发布/i);
  });

  it('keeps raw and schema review notes collapsed by default', () => {
    render(<AdminEvidenceWorkflowPage />);

    const disclosure = screen.getByTestId('admin-evidence-raw-disclosure');
    expect(disclosure).not.toHaveAttribute('open');
    expect(within(disclosure).getByText('原始/Schema 字段')).toBeInTheDocument();
  });

  it('uses responsive ghost-glass layout classes for desktop and narrow screens', () => {
    render(<AdminEvidenceWorkflowPage />);

    const page = screen.getByTestId('admin-evidence-workflow-page');
    const workflowGrid = screen.getByTestId('admin-evidence-workflow-grid');
    const statusGrid = screen.getByTestId('admin-evidence-status-grid');
    const commandGrid = screen.getByTestId('admin-evidence-command-snippets');

    expect(page).toHaveClass('overflow-y-auto', 'overflow-x-hidden', 'no-scrollbar', 'bg-[#050505]');
    expect(workflowGrid).toHaveClass('grid-cols-1', 'lg:grid-cols-7');
    expect(statusGrid).toHaveClass('grid-cols-1', 'md:grid-cols-2', 'xl:grid-cols-4');
    expect(commandGrid).toHaveClass('grid-cols-1', 'xl:grid-cols-3');
  });
});
