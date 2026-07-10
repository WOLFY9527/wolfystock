import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import ResearchWorkspaceFlowPanel from '../ResearchWorkspaceFlowPanel';

describe('ResearchWorkspaceFlowPanel', () => {
  it('builds read-only research workspace links with symbol context', () => {
    render(
      <MemoryRouter>
        <ResearchWorkspaceFlowPanel
          language="en"
          current="scanner"
          symbol="nvda"
          market="us"
          source="scanner"
          knownEvidence={['Scanner candidate formed']}
          missingEvidence={['Portfolio exposure not reviewed']}
          nextSteps={['Review exposure before validation']}
        />
      </MemoryRouter>,
    );

    const watchlistLink = screen.getByTestId('research-workspace-link-watchlist');
    expect(watchlistLink).toHaveAttribute('href', expect.stringContaining('/en/watchlist?'));
    expect(watchlistLink).toHaveAttribute('href', expect.stringContaining('symbol=NVDA'));
    expect(watchlistLink).toHaveAttribute('href', expect.stringContaining('market=US'));
    expect(watchlistLink).toHaveAttribute('href', expect.stringContaining('source=scanner'));

    const stockStructureLink = screen.getByTestId('research-workspace-link-stock-structure');
    expect(stockStructureLink).toHaveAttribute('href', expect.stringContaining('/en/stocks/NVDA/structure-decision?'));
    expect(stockStructureLink).toHaveAttribute('href', expect.stringContaining('symbol=NVDA'));
    expect(stockStructureLink).toHaveAttribute('href', expect.stringContaining('market=US'));
    expect(stockStructureLink).toHaveAttribute('href', expect.stringContaining('source=scanner'));

    const backtestLink = screen.getByTestId('research-workspace-link-backtest');
    expect(backtestLink).toHaveAttribute('href', expect.stringContaining('/en/backtest?'));
    const scannerLink = screen.getByTestId('research-workspace-link-scanner');
    expect(scannerLink).toHaveAttribute('aria-current', 'step');
    expect(screen.getByTestId('research-workspace-flow').querySelectorAll('[aria-current="page"]')).toHaveLength(0);
    for (const link of screen.getAllByRole('link')) {
      expect(link).toHaveAttribute('href', expect.not.stringMatching(/scannerRunId|scannerRank|watchlistItemId|themeId|universeType|debug|runtime|cache|provider/i));
    }
  });

  it('sanitizes internal evidence vocabulary before rendering consumer copy', () => {
    render(
      <MemoryRouter>
        <ResearchWorkspaceFlowPanel
          language="en"
          current="watchlist"
          symbol="AAPL"
          knownEvidence={['provider raw json payload present']}
          missingEvidence={['fallback cache stale']}
          stateNotes={['fixture sample']}
          nextSteps={['confidence cap applied']}
        />
      </MemoryRouter>,
    );

    const panel = screen.getByTestId('research-workspace-flow');
    expect(within(panel).getByText('Technical details are hidden; consumer evidence only.')).toBeInTheDocument();
    expect(within(panel).getByText('Using latest available data; verify the timestamp.')).toBeInTheDocument();
    expect(within(panel).getByText('Local validation sample for interface verification only.')).toBeInTheDocument();
    expect(within(panel).getByText('Confidence is capped; observation only.')).toBeInTheDocument();
    expect(panel).not.toHaveTextContent(/provider|cache|fallback|raw|json|diagnostic|debug|runtime|internal/i);
  });
});
