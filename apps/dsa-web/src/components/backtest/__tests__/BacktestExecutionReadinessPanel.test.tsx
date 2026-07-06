import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import BacktestExecutionReadinessPanel from '../BacktestExecutionReadinessPanel';

describe('BacktestExecutionReadinessPanel', () => {
  it('does not expose OHLCV in consumer-visible historical data readiness', () => {
    render(
      <BacktestExecutionReadinessPanel
        language="zh"
        readiness={{
          state: 'data_insufficient',
          resultContractAvailable: false,
          benchmarkState: 'missing',
          reasonCodes: [
            'insufficient_history',
            'historical_ohlcv_insufficient_coverage',
            'missing_benchmark',
          ],
        }}
        historicalOhlcvReadiness={{
          contractVersion: 'backtest_historical_ohlcv_readiness_v1',
          status: 'insufficient_coverage',
          executable: false,
          requiredBarCount: 120,
          availableBarCount: 30,
          missingDataClasses: ['historical_ohlcv', 'benchmark_ohlcv'],
          consumerSafeMessage: 'Backtest cannot run because the requested date range does not have enough historical OHLCV bars.',
          operatorNextAction: 'Seed or refresh the local historical OHLCV cache for the requested symbol and date range.',
        }}
      />,
    );

    const panel = screen.getByTestId('backtest-execution-readiness-panel');
    expect(panel).toHaveTextContent('历史价格数据窗口不足，无法计算安全结果。');
    expect(panel).toHaveTextContent('历史价格数据覆盖不足');
    expect(panel).toHaveTextContent('历史价格数据 / 基准历史价格数据');
    expect(panel).toHaveTextContent('请刷新或补齐本次区间的历史价格数据后，再复核就绪度。');
    expect(panel.textContent || '').not.toMatch(/OHLCV|cache|Seed/i);
  });

  it('renders initializing readiness as bounded sample preparation without implying success', () => {
    render(
      <BacktestExecutionReadinessPanel
        language="zh"
        readiness={{
          state: 'samples_initializing',
          resultContractAvailable: false,
          reasonCodes: ['samples_initializing'],
        }}
        productReadModel={{
          contractVersion: 'product_read_model_v1',
          surface: 'Backtest readiness',
          state: 'pending',
          ready: false,
          quality: {
            state: 'pending',
            missingDataClasses: ['samples_initializing'],
          },
        }}
      />,
    );

    const panel = screen.getByTestId('backtest-execution-readiness-panel');
    expect(panel).toHaveAttribute('data-readiness-state', 'samples_initializing');
    expect(panel).toHaveTextContent('正在准备历史样本');
    expect(panel).toHaveTextContent('历史样本仍在准备中；这不代表结果一定可用。');
    expect(panel).toHaveTextContent('历史样本正在准备，尚不能确认结果可用。');
    expect(panel).not.toHaveTextContent(/被阻塞|不可用|等待就绪度|OHLCV/i);
  });
});
