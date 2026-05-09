import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  TerminalButton,
  TerminalChip,
  TerminalDisclosure,
  TerminalEmptyState,
  TerminalPanel,
} from '../TerminalPrimitives';

describe('TerminalPrimitives', () => {
  it('renders the standard ghost panel material', () => {
    render(<TerminalPanel data-testid="panel">Panel</TerminalPanel>);

    const panel = screen.getByTestId('panel');
    expect(panel).toHaveAttribute('data-terminal-primitive', 'panel');
    expect(panel).toHaveClass('bg-white/[0.02]', 'border', 'border-white/5', 'backdrop-blur-md', 'rounded-[16px]', 'p-5');
  });

  it('renders button variants with terminal tokens', () => {
    render(
      <>
        <TerminalButton variant="primary">Run</TerminalButton>
        <TerminalButton variant="secondary">Cancel</TerminalButton>
        <TerminalButton variant="compact">More</TerminalButton>
        <TerminalButton variant="danger">Delete</TerminalButton>
      </>,
    );

    expect(screen.getByRole('button', { name: 'Run' })).toHaveClass('from-blue-600', 'to-purple-600');
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveClass('bg-white/5', 'border-white/10');
    expect(screen.getByRole('button', { name: 'More' })).toHaveClass('bg-white/[0.03]', 'text-xs');
    expect(screen.getByRole('button', { name: 'Delete' })).toHaveClass('bg-rose-500/5', 'border-rose-400/20');
  });

  it('renders chip variants with quiet terminal materials', () => {
    render(
      <>
        <TerminalChip variant="neutral">Neutral</TerminalChip>
        <TerminalChip variant="success">Success</TerminalChip>
        <TerminalChip variant="caution">Caution</TerminalChip>
        <TerminalChip variant="danger">Danger</TerminalChip>
        <TerminalChip variant="info">Info</TerminalChip>
      </>,
    );

    expect(screen.getByText('Neutral')).toHaveClass('bg-white/5', 'text-white/50');
    expect(screen.getByText('Success')).toHaveClass('bg-emerald-400/5', 'text-emerald-300');
    expect(screen.getByText('Caution')).toHaveClass('bg-amber-300/5', 'text-amber-300');
    expect(screen.getByText('Danger')).toHaveClass('bg-rose-500/5', 'text-rose-300');
    expect(screen.getByText('Info')).toHaveClass('bg-cyan-400/5', 'text-cyan-300');
  });

  it('renders compact empty states', () => {
    render(<TerminalEmptyState title="暂无数据" />);

    const empty = screen.getByTestId('terminal-empty-state');
    expect(empty).toHaveClass('min-h-[88px]', 'border-white/[0.03]', 'text-xs', 'text-white/30');
    expect(empty).toHaveTextContent('暂无数据');
  });

  it('starts disclosures collapsed and opens on interaction', () => {
    render(
      <TerminalDisclosure title="高级详情" summary="默认收起">
        <p>内部详情</p>
      </TerminalDisclosure>,
    );

    const disclosure = screen.getByTestId('terminal-disclosure');
    expect(disclosure).not.toHaveAttribute('open');
    expect(screen.queryByText('内部详情')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /展开 高级详情/ }));

    expect(disclosure).toHaveAttribute('open');
    expect(screen.getByText('内部详情')).toBeInTheDocument();
  });
});
