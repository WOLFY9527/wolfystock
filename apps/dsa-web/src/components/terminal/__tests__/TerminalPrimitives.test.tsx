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
  it('renders legacy panels with paper research material', () => {
    render(<TerminalPanel data-testid="panel">Panel</TerminalPanel>);

    const panel = screen.getByTestId('panel');
    expect(panel).toHaveAttribute('data-terminal-primitive', 'panel');
    expect(panel).toHaveClass(
      'bg-[var(--wolfy-surface-console)]',
      'border-[color:var(--wolfy-border-subtle)]',
      'text-[color:var(--wolfy-text-primary)]',
      'shadow-none',
    );
    expect(panel).not.toHaveClass('backdrop-blur-md', 'bg-white/[0.02]', 'rounded-[16px]');
  });

  it('renders button variants with paper research tokens', () => {
    render(
      <>
        <TerminalButton variant="primary">Run</TerminalButton>
        <TerminalButton variant="secondary">Cancel</TerminalButton>
        <TerminalButton variant="compact">More</TerminalButton>
        <TerminalButton variant="danger">Delete</TerminalButton>
      </>,
    );

    expect(screen.getByRole('button', { name: 'Run' })).toHaveClass('bg-[var(--theme-button-primary-bg)]', 'rounded-md');
    expect(screen.getByRole('button', { name: 'Run' })).toHaveAttribute('data-action-intent', 'write');
    expect(screen.getByRole('button', { name: 'Run' }).className).not.toContain('gradient');
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveClass('bg-[var(--wolfy-surface-input)]', 'border-[color:var(--wolfy-border-subtle)]');
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveAttribute('data-action-intent', 'passive');
    expect(screen.getByRole('button', { name: 'More' })).toHaveClass('bg-transparent', 'text-xs');
    expect(screen.getByRole('button', { name: 'Delete' })).toHaveClass('text-[color:var(--wolfy-market-down)]');
    expect(screen.getByRole('button', { name: 'Delete' })).toHaveAttribute('data-action-intent', 'write');
  });

  it('renders chip variants with quiet paper research materials', () => {
    render(
      <>
        <TerminalChip variant="neutral">Neutral</TerminalChip>
        <TerminalChip variant="success">Success</TerminalChip>
        <TerminalChip variant="caution">Caution</TerminalChip>
        <TerminalChip variant="danger">Danger</TerminalChip>
        <TerminalChip variant="info">Info</TerminalChip>
      </>,
    );

    expect(screen.getByText('Neutral')).toHaveClass('bg-[var(--wolfy-surface-input)]', 'text-[color:var(--wolfy-text-muted)]', 'font-medium');
    expect(screen.getByText('Neutral')).not.toHaveClass('font-mono');
    expect(screen.getByText('Success')).toHaveClass('text-[color:var(--wolfy-market-up)]');
    expect(screen.getByText('Caution')).toHaveClass('bg-[var(--state-warning-bg)]', 'text-[color:var(--state-warning-text)]');
    expect(screen.getByText('Danger')).toHaveClass('text-[color:var(--wolfy-market-down)]');
    expect(screen.getByText('Info')).toHaveClass('text-[color:var(--wolfy-accent)]');
  });

  it('renders compact empty states', () => {
    render(<TerminalEmptyState title="暂无数据" />);

    const empty = screen.getByTestId('terminal-empty-state');
    expect(empty).toHaveClass('min-h-[72px]', 'border-[color:var(--wolfy-border-subtle)]', 'text-xs', 'text-[color:var(--wolfy-text-muted)]');
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
