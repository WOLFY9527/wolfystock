import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import NormalBacktestWorkspace from '../NormalBacktestWorkspace';

vi.mock('../NormalBacktestTemplateInsights', () => new Promise(() => {}));

describe('NormalBacktestWorkspace', () => {
  const resultReadyProps = {
    code: 'AAPL',
    onCodeChange: () => {},
    startDate: '2025-01-01',
    onStartDateChange: () => {},
    endDate: '2025-12-31',
    onEndDateChange: () => {},
    initialCapital: '100000',
    onInitialCapitalChange: () => {},
    feeBps: '0',
    onFeeBpsChange: () => {},
    slippageBps: '0',
    onSlippageBpsChange: () => {},
    benchmarkMode: 'auto' as const,
    onBenchmarkModeChange: () => {},
    benchmarkCode: '',
    onBenchmarkCodeChange: () => {},
    strategyTemplate: 'moving_average_crossover' as const,
    onStrategyTemplateChange: () => {},
    onLaunch: vi.fn().mockResolvedValue(undefined),
    isLaunching: false,
    parseError: null,
    runError: null,
    hasRunAttempt: true,
    runReadiness: { state: 'ready', resultContractAvailable: true },
  };

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

    fireEvent.click(screen.getByRole('button', { name: '执行回测任务' }));

    expect(onLaunch).toHaveBeenCalledTimes(1);
  });

  it('localizes the real-result composition through the consumer presentation boundary', () => {
    const { rerender } = render(<NormalBacktestWorkspace {...resultReadyProps} language="zh" />);

    const chinesePreview = screen.getByTestId('backtest-result-preview-panel');
    expect(chinesePreview).toHaveTextContent('失效条件');
    expect(chinesePreview).not.toHaveTextContent('Where It Breaks');

    rerender(<NormalBacktestWorkspace {...resultReadyProps} language="en" />);
    const englishPreview = screen.getByTestId('backtest-result-preview-panel');
    expect(englishPreview).toHaveTextContent('Where It Breaks');
  });
});
