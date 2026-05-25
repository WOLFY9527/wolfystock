import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import BacktestPage from '../BacktestPage';

const {
  getResults,
  getOverallPerformance,
  getStockPerformance,
  getHistory,
  getSampleStatus,
  getRuleBacktestRuns,
} = vi.hoisted(() => ({
  getResults: vi.fn(),
  getOverallPerformance: vi.fn(),
  getStockPerformance: vi.fn(),
  getHistory: vi.fn(),
  getSampleStatus: vi.fn(),
  getRuleBacktestRuns: vi.fn(),
}));

vi.mock('../../components/backtest/NormalBacktestWorkspace', () => new Promise(() => {}));

vi.mock('motion/react', async () => {
  const React = await import('react');
  type StaticMotionDivProps = React.HTMLAttributes<HTMLDivElement> & {
    children?: React.ReactNode;
    animate?: unknown;
    exit?: unknown;
    initial?: unknown;
    layout?: unknown;
    transition?: unknown;
    variants?: unknown;
    whileHover?: unknown;
    whileTap?: unknown;
  };

  const StaticDiv = React.forwardRef<HTMLDivElement, StaticMotionDivProps>(
    ({ children, ...props }, ref) => {
      const rest = { ...props } as Record<string, unknown>;
      delete rest.animate;
      delete rest.exit;
      delete rest.initial;
      delete rest.layout;
      delete rest.transition;
      delete rest.variants;
      delete rest.whileHover;
      delete rest.whileTap;
      return React.createElement('div', { ...rest, ref }, children);
    },
  );
  StaticDiv.displayName = 'StaticMotionDiv';

  return {
    LazyMotion: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
    AnimatePresence: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
    domAnimation: {},
    m: {
      div: StaticDiv,
      section: StaticDiv,
    },
  };
});

vi.mock('../../api/backtest', () => ({
  backtestApi: {
    run: vi.fn(),
    getResults,
    getOverallPerformance,
    getStockPerformance,
    prepareSamples: vi.fn(),
    getHistory,
    getSampleStatus,
    clearSamples: vi.fn(),
    clearResults: vi.fn(),
    parseRuleStrategy: vi.fn(),
    runRuleBacktest: vi.fn(),
    getRuleBacktestRuns,
    getRuleBacktestRun: vi.fn(),
    getRuleBacktestRunStatus: vi.fn(),
    cancelRuleBacktestRun: vi.fn(),
  },
}));

describe('BacktestPage lazy normal workspace', () => {
  it('keeps the page shell available while the default workspace chunk loads', async () => {
    getResults.mockResolvedValue({ items: [], total: 0 });
    getOverallPerformance.mockResolvedValue(null);
    getStockPerformance.mockResolvedValue(null);
    getHistory.mockResolvedValue({ items: [], total: 0 });
    getSampleStatus.mockResolvedValue(null);
    getRuleBacktestRuns.mockResolvedValue({ items: [], total: 0 });

    render(
      <MemoryRouter initialEntries={['/backtest']}>
        <UiLanguageProvider>
          <Routes>
            <Route path="/backtest" element={<BacktestPage />} />
          </Routes>
        </UiLanguageProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('backtest-workspace-loading')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '普通' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: '专业' })).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByTestId('backtest-page-heading')).toBeInTheDocument();
  });
});
