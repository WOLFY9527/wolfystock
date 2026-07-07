import { describe, expect, it, vi } from 'vitest';
import type { RuleBacktestRunResponse } from '../../../types/backtest';
import { downloadExecutionTraceCsv } from '../executionTraceUtils';

function makeTraceRun(): RuleBacktestRunResponse {
  return {
    id: 101,
    code: 'ORCL',
    status: 'completed',
    executionTrace: {
      source: 'storedExecutionTrace',
      rows: [
        {
          date: '=1+1',
          symbolClose: -12.5,
          benchmarkClose: 99,
          signalSummary: '+1+1',
          action: 'buy',
          actionDisplay: '-1+1',
          fillPrice: 101,
          shares: 100,
          cash: -2500,
          holdingsValue: 10100,
          totalPortfolioValue: 7600,
          dailyPnl: -123.45,
          dailyReturn: -0.12,
          cumulativeReturn: -0.34,
          benchmarkCumulativeReturn: 0.05,
          buyHoldCumulativeReturn: 0.04,
          position: 1,
          fees: 1.2,
          slippage: 0.3,
          notes: '@SUM(1,1)',
          assumptionsDefaults: '  =1+1',
          fallback: 'profit +1+1 later',
        },
        {
          date: '2026-03-02',
          symbolClose: 101,
          benchmarkClose: 100,
          signalSummary: '\t+1+1',
          action: 'hold',
          fillPrice: null,
          shares: 100,
          cash: 500,
          holdingsValue: 10100,
          totalPortfolioValue: 10600,
          dailyPnl: 500,
          dailyReturn: 0.5,
          cumulativeReturn: 0.16,
          benchmarkCumulativeReturn: 0.06,
          buyHoldCumulativeReturn: 0.05,
          position: 1,
          fees: 0,
          slippage: 0,
          notes: '\r-1+1',
          assumptionsDefaults: '\n@SUM(1,1)',
          fallback: '腾讯控股, quote "kept"\nmultiline',
        },
      ],
    },
  } as RuleBacktestRunResponse;
}

describe('executionTraceUtils', () => {
  it('exports formula-safe execution trace csv without changing numeric trace values', async () => {
    const createObjectUrlMock = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test');
    const revokeObjectUrlMock = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    const clickMock = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    downloadExecutionTraceCsv(makeTraceRun());

    const blob = createObjectUrlMock.mock.calls[0]?.[0] as Blob;
    const content = await blob.text();
    expect(content).toContain('"\'=1+1"');
    expect(content).toContain('"\'-1+1"');
    expect(content).toContain('"\'@SUM(1,1)"');
    expect(content).toContain('"\'  =1+1"');
    expect(content).toContain('"\'\t+1+1"');
    expect(content).toContain('"\'\r-1+1"');
    expect(content).toContain('"\'\n@SUM(1,1)"');
    expect(content).toContain('"profit +1+1 later"');
    expect(content).toContain('"腾讯控股, quote ""kept""\nmultiline"');
    expect(content).toContain('"-12.5"');
    expect(content).toContain('"-2500"');
    expect(content).toContain('"-123.45"');

    createObjectUrlMock.mockRestore();
    revokeObjectUrlMock.mockRestore();
    clickMock.mockRestore();
  });
});
