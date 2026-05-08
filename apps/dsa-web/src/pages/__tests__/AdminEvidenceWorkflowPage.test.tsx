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
    workflowSteps.forEach((step) => {
      expect(within(page).getByText(step)).toBeInTheDocument();
    });
    expect(within(page).getByText('GO-REVIEW-REQUIRED')).toBeInTheDocument();
    expect(within(page).getByText('NO-GO if missing evidence')).toBeInTheDocument();
    expect(within(page).getByText('manual review required')).toBeInTheDocument();
    expect(within(page).getByText('releaseApproved=false')).toBeInTheDocument();
  });

  it('does not render upload, mutation, or launch approval actions', () => {
    render(<AdminEvidenceWorkflowPage />);

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/upload|上传|file|文件/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/launch-approved|production-ready|上线批准|生产就绪|批准上线|批准发布/i)).not.toBeInTheDocument();
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

    expect(page).toHaveClass('overflow-y-auto', 'no-scrollbar', 'bg-[#050505]');
    expect(workflowGrid).toHaveClass('grid-cols-1', 'lg:grid-cols-7');
    expect(statusGrid).toHaveClass('grid-cols-1', 'md:grid-cols-2', 'xl:grid-cols-4');
  });
});
