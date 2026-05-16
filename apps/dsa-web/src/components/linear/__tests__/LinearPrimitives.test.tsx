import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  CatalystRows,
  ConsoleBoard,
  ConsoleContextRail,
  ConsoleDisclosure,
  ConsoleStatusStrip,
  DataWorkbenchFrame,
  DenseRows,
  KeyLevelStrip,
  ResearchConsoleShell,
  WolfyCommandBar,
  WolfyShellSurface,
} from '../LinearPrimitives';

describe('LinearPrimitives', () => {
  it('renders shell surfaces with the charcoal token ladder', () => {
    render(
      <WolfyShellSurface data-testid="surface">
        Surface
      </WolfyShellSurface>,
    );

    const surface = screen.getByTestId('surface');
    expect(surface).toHaveAttribute('data-linear-primitive', 'surface');
    expect(surface).toHaveClass(
      'bg-[var(--wolfy-surface-console)]',
      'border-[color:var(--wolfy-border-subtle)]',
      'text-[color:var(--wolfy-text-primary)]',
      'shadow-none',
    );
  });

  it('renders the command bar and research shell without card-first wrappers', () => {
    render(
      <ResearchConsoleShell
        command={<WolfyCommandBar trailing={<button type="button">Run</button>}>Search</WolfyCommandBar>}
        rail={<ConsoleContextRail>Rail</ConsoleContextRail>}
      >
        <ConsoleBoard>Board</ConsoleBoard>
      </ResearchConsoleShell>,
    );

    expect(screen.getByText('Search').closest('[data-linear-primitive="command-bar"]')).toHaveClass(
      'bg-[var(--wolfy-surface-input)]',
      'rounded-lg',
    );
    expect(screen.getByText('Board').closest('[data-linear-primitive="console-board"]')).toHaveClass('overflow-hidden');
    expect(screen.getByText('Rail').closest('[data-linear-primitive="context-rail"]')).toHaveClass(
      'divide-y',
      'divide-[color:var(--wolfy-divider)]',
    );
  });

  it('renders status, key-level, catalyst, workbench, and dense row helpers', () => {
    render(
      <>
        <ConsoleStatusStrip items={[{ label: 'Score', value: '78' }]} />
        <KeyLevelStrip levels={[{ label: 'Target', value: '133.50', tone: 'up' }]} />
        <CatalystRows items={[{ title: 'Earnings call', meta: '2026-06-12', status: 'verified' }]} />
        <DataWorkbenchFrame><table><tbody><tr><td>Row</td></tr></tbody></table></DataWorkbenchFrame>
        <DenseRows><div>Dense row</div></DenseRows>
      </>,
    );

    expect(screen.getByText('78')).toHaveClass('text-[color:var(--wolfy-text-primary)]');
    expect(screen.getByText('133.50')).toHaveClass('text-[color:var(--wolfy-market-up)]');
    expect(screen.getByText('Earnings call')).toBeInTheDocument();
    expect(screen.getByText('Row').closest('[data-linear-primitive="data-workbench-frame"]')).toHaveClass('overflow-hidden');
    expect(screen.getByText('Dense row').closest('[data-linear-primitive="dense-rows"]')).toHaveClass('divide-y');
  });

  it('keeps disclosures collapsed until opened', () => {
    render(
      <ConsoleDisclosure title="来源" summary="默认收起">
        <p>source detail</p>
      </ConsoleDisclosure>,
    );

    expect(screen.queryByText('source detail')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '展开 来源' }));
    expect(screen.getByText('source detail')).toBeInTheDocument();
  });
});
