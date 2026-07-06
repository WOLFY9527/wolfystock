import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  CatalystRows,
  CompactFilterBar,
  ConsoleBoard,
  ConsoleContextRail,
  ConsoleDisclosure,
  ConsoleStatusStrip,
  DataWorkbenchFrame,
  DataRows,
  DenseRows,
  FixedRegionGrid,
  FloatingDetailPanel,
  MetricStrip,
  KeyLevelStrip,
  PrimaryWorkRegion,
  ResearchConsoleShell,
  ScrollPanel,
  SecondaryDeck,
  WolfyCommandBar,
  WolfyShellSurface,
} from '../LinearPrimitives';

describe('LinearPrimitives', () => {
  it('renders shell surfaces with the paper token ladder', () => {
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

    expect(screen.getByText('Search').closest('[data-linear-primitive="research-console-shell"]')).toHaveClass(
      'bg-[var(--wolfy-surface-console)]',
      'border-[color:var(--wolfy-border-subtle)]',
      'rounded-[var(--theme-panel-radius-lg)]',
    );
    expect(screen.getByText('Search').closest('[data-linear-primitive="research-console-shell"]')).toHaveAttribute('data-route-console', 'ResearchConsole');
    expect(screen.getByText('Search').closest('[data-linear-primitive="research-console-shell"]')).toHaveAttribute('data-visual-tier', 'dominant');
    expect(screen.getByText('Search').closest('[data-linear-primitive="command-bar"]')).toHaveClass(
      'bg-[var(--wolfy-surface-input)]',
      'rounded-xl',
    );
    expect(screen.getByText('Board').closest('[data-linear-primitive="console-board"]')).toHaveClass('overflow-hidden');
    expect(screen.getByText('Rail').closest('[data-linear-primitive="context-rail"]')).toHaveClass(
      'divide-y',
      'divide-[color:var(--wolfy-divider)]',
    );
  });

  it('renders fixed regions, command bars, rails, scroll panels, and secondary decks', () => {
    render(
      <>
        <CompactFilterBar leading={<span>Lead</span>} trailing={<button type="button">Run</button>}>Search</CompactFilterBar>
        <FixedRegionGrid
          header={<div>Header</div>}
          primary={(
            <ScrollPanel maxHeight={320}>
              <ConsoleBoard>Board</ConsoleBoard>
            </ScrollPanel>
          )}
          rail={<div>Rail</div>}
          railTestId="fixed-grid-rail"
          secondary={<div>Deck</div>}
          secondaryTestId="fixed-grid-deck"
        />
        <PrimaryWorkRegion data-testid="named-primary">Named primary</PrimaryWorkRegion>
        <SecondaryDeck data-testid="named-deck">Named deck</SecondaryDeck>
      </>,
    );

    expect(screen.getByText('Search').closest('[data-linear-primitive="compact-filter-bar"]')).toHaveAttribute('data-layout-zone', 'CommandBar');
    expect(screen.getByText('Header').closest('[data-layout-zone="HeaderStrip"]')).toBeInTheDocument();
    expect(screen.getByText('Board').closest('[data-layout-zone="PrimaryWorkRegion"]')).toBeInTheDocument();
    expect(screen.getByText('Board').closest('[data-linear-primitive="scroll-panel"]')).toHaveClass('overflow-y-auto', 'no-scrollbar');
    expect(screen.getByTestId('fixed-grid-rail')).toHaveAttribute('data-linear-primitive', 'context-rail');
    expect(screen.getByTestId('fixed-grid-rail')).toHaveAttribute('data-layout-zone', 'ContextRail');
    expect(screen.getByTestId('fixed-grid-rail')).toHaveClass('overflow-hidden', 'bg-[var(--wolfy-surface-rail)]');
    expect(screen.getByTestId('fixed-grid-deck')).toHaveAttribute('data-linear-primitive', 'secondary-deck');
    expect(screen.getByTestId('fixed-grid-deck')).toHaveAttribute('data-layout-zone', 'SecondaryDeck');
    expect(screen.getByTestId('named-primary')).toHaveAttribute('data-linear-primitive', 'primary-work-region');
    expect(screen.getByTestId('named-deck')).toHaveAttribute('data-linear-primitive', 'secondary-deck');
  });

  it('renders status, key-level, catalyst, metric strip, workbench, and dense row helpers', () => {
    render(
      <>
        <ConsoleStatusStrip items={[{ label: 'Score', value: '78' }]} />
        <MetricStrip items={[{ label: 'Score', value: '78' }]} />
        <KeyLevelStrip levels={[{ label: 'Target', value: '133.50', tone: 'up' }]} />
        <CatalystRows items={[{ title: 'Earnings call', meta: '2026-06-12', status: 'verified' }]} />
        <DataWorkbenchFrame><table><tbody><tr><td>Row</td></tr></tbody></table></DataWorkbenchFrame>
        <DataRows><div>Data row</div></DataRows>
        <DenseRows><div>Dense row</div></DenseRows>
        <FloatingDetailPanel>Floating detail</FloatingDetailPanel>
      </>,
    );

    const scoreValues = screen.getAllByText('78');
    expect(scoreValues.length).toBeGreaterThan(1);
    scoreValues.forEach((value) => expect(value).toHaveClass('text-[color:var(--wolfy-text-primary)]'));
    expect(screen.getByText('133.50')).toHaveClass('text-[color:var(--wolfy-market-up)]');
    expect(screen.getByText('Earnings call')).toBeInTheDocument();
    expect(screen.getByText('Row').closest('[data-linear-primitive="data-workbench-frame"]')).toHaveClass('overflow-hidden');
    expect(screen.getByText('Data row').closest('[data-linear-primitive="data-rows"]')).toHaveClass('divide-y');
    expect(screen.getByText('Dense row').closest('[data-linear-primitive="dense-rows"]')).toHaveClass('divide-y');
    expect(screen.getByText('Floating detail').closest('[data-linear-primitive="floating-detail-panel"]')).toHaveClass('overflow-y-auto', 'no-scrollbar');
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
