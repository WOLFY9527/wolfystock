import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import NormalBacktestWorkspace from '../NormalBacktestWorkspace';

vi.mock('../NormalBacktestTemplateInsights', () => new Promise(() => {}));

describe('NormalBacktestWorkspace', () => {
  it('keeps the launch form usable while template insights lazy-load', () => {
    const onLaunch = vi.fn().mockResolvedValue(undefined);

    render(
      <NormalBacktestWorkspace
        language="zh"
        code="AAPL"
        onCodeChange={() => {}}
        startDate="2025-01-01"
        onStartDateChange={() => {}}
        endDate="2025-12-31"
        onEndDateChange={() => {}}
        initialCapital="100000"
        onInitialCapitalChange={() => {}}
        feeBps="0"
        onFeeBpsChange={() => {}}
        slippageBps="0"
        onSlippageBpsChange={() => {}}
        benchmarkMode="auto"
        onBenchmarkModeChange={() => {}}
        benchmarkCode=""
        onBenchmarkCodeChange={() => {}}
        strategyTemplate="moving_average_crossover"
        onStrategyTemplateChange={() => {}}
        onLaunch={onLaunch}
        isLaunching={false}
        parseError={null}
        runError={null}
      />,
    );

    expect(screen.getByTestId('normal-backtest-form-grid')).toBeInTheDocument();
    expect(screen.getByLabelText('标的代码')).toHaveValue('AAPL');
    expect(screen.getByLabelText('策略模板')).toBeInTheDocument();
    expect(screen.getByTestId('normal-backtest-template-insights-loading')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '运行回测研究' }));

    expect(onLaunch).toHaveBeenCalledTimes(1);
  });
});
