import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AdminEvidenceDryRunPreview } from '../AdminEvidenceDryRunPreview';

describe('AdminEvidenceDryRunPreview', () => {
  it('renders compact dry-run cards with cautious Chinese summaries', () => {
    render(<AdminEvidenceDryRunPreview />);

    const panel = screen.getByTestId('admin-evidence-dry-run-preview');
    expect(within(panel).getByText('AI 证据解释预览')).toBeInTheDocument();
    expect(within(panel).getByText(/不影响实时 AI 决策/)).toBeInTheDocument();
    expect(within(panel).getByText('当前证据链已校验，可用于观察，不提升任何判断强度。')).toBeInTheDocument();
    expect(within(panel).getByText('当前为轮动代理证据，真实资金流暂缺，仅供观察。')).toBeInTheDocument();
    expect(within(panel).getByText('当前期权证据不足，数据不足，禁止判断，仅保留观察与人工复核。')).toBeInTheDocument();
    expect(within(panel).getByText('当前仅为研究级回测证据，仅供观察，不构成机构级验证结论。')).toBeInTheDocument();
    expect(within(panel).getByText('当前组合风险证据链不完整，仅供风险观察，不输出确定性风险结论。')).toBeInTheDocument();
  });

  it('keeps representative diagnostics collapsed by default and expands safe disabled-claim details on demand', () => {
    render(<AdminEvidenceDryRunPreview />);

    const optionsDisclosure = screen.getByTestId('admin-evidence-dry-run-disclosure-options');
    expect(optionsDisclosure).not.toHaveAttribute('open');
    expect(within(optionsDisclosure).queryByText('策略推荐已禁用')).not.toBeInTheDocument();
    expect(screen.queryByText(/^\s*\{/)).not.toBeInTheDocument();

    fireEvent.click(within(optionsDisclosure).getByRole('button', { name: /展开 代表样本诊断/i }));

    expect(optionsDisclosure).toHaveAttribute('open');
    expect(within(optionsDisclosure).getByText('策略推荐已禁用')).toBeInTheDocument();
    expect(within(optionsDisclosure).getByText('可交易性判断已禁用')).toBeInTheDocument();
    expect(within(optionsDisclosure).getByText('packet version')).toBeInTheDocument();
    expect(within(optionsDisclosure).queryByText(/prompt|payload|raw json/i)).not.toBeInTheDocument();
  });

  it('uses a narrow-safe grid without horizontal overflow helpers or solid gray slabs', () => {
    render(<AdminEvidenceDryRunPreview />);

    const grid = screen.getByTestId('admin-evidence-dry-run-preview-grid');
    const optionsCard = screen.getByTestId('admin-evidence-dry-run-card-options');

    expect(grid).toHaveClass('grid-cols-1', 'md:grid-cols-2', 'xl:grid-cols-5');
    expect(optionsCard.className).not.toMatch(/bg-(gray|zinc|slate|neutral)-/);
    expect(screen.getByTestId('admin-evidence-dry-run-cap-options')).toHaveTextContent('≤35');
    expect(screen.getByTestId('admin-evidence-dry-run-validation-options')).toHaveTextContent('已校验');
  });
});
