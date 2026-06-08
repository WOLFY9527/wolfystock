import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AnalysisReport } from '../../../types/analysis';
import FullDecisionReportDrawer from '../FullDecisionReportDrawer';

vi.mock('../../common/Drawer', () => ({
  Drawer: ({ children, isOpen }: { children: ReactNode; isOpen: boolean }) => (
    isOpen ? <div role="dialog">{children}</div> : null
  ),
}));

const forbiddenConsumerReportPattern =
  /投资结论|买入|卖出|理想买点|次级买点|止损|止盈|目标价|目标位|目标区间|仓位建议|\bAction\b|Ideal buy|Secondary entry|Stop loss|Take profit|Target 1|Target 2|Target zone|Position sizing|holding advice|empty-position advice|reasonCode|sourceRefId|raw_result|raw_ai_response|context_snapshot|raw_result_marker|raw_ai_response_marker|context_snapshot_marker|provider_timeout|fallback_cache|Yahoo Finance|Finnhub|backend snake_case/i;

function buildUnsafeReportFixture(): AnalysisReport {
  return {
    meta: {
      queryId: 't1162',
      stockCode: 'ORCL',
      stockName: 'Oracle',
      companyName: 'Oracle',
      reportType: 'full',
      createdAt: '2026-06-07T08:00:00Z',
      reportGeneratedAt: '2026-06-07T08:01:00Z',
    },
    summary: {
      analysisSummary: '建议买入，目标价看 133.50。',
      operationAdvice: '买入',
      trendPrediction: '上行后卖出',
      sentimentScore: 74,
      sentimentLabel: 'Bullish',
    },
    strategy: {
      idealBuy: '121.80 - 124.60（理想买点）',
      secondaryBuy: '119.50（次级买点）',
      stopLoss: '117.40（止损）',
      takeProfit: '133.50（目标价）',
    },
    details: {
      rawResult: {
        raw_result_marker: 'raw_result_marker must not render',
        dashboard: {
          data_perspective: {
            alpha_vantage: {
              backend_snake_case: 'backend snake_case must not render',
            },
          },
        },
        items: [
          {
            stockEvidencePacket: {
              notInvestmentAdvice: true,
              confidenceCap: {
                value: 40,
                reasonCodes: ['provider_timeout'],
              },
              sourceRefs: [
                {
                  sourceRefId: 'quote:fallback_cache',
                  provider: 'Yahoo Finance',
                  status: 'fallback',
                },
              ],
              rawPayload: 'raw_ai_response_marker',
            },
          },
        ],
      },
      rawAiResponse: 'raw_ai_response_marker',
      contextSnapshot: { context_snapshot_marker: true },
      standardReport: {
        summaryPanel: {
          stock: 'Oracle',
          ticker: 'ORCL',
          score: 74,
          operationAdvice: '买入',
          trendPrediction: '卖出',
          oneSentence: '目标价 133.50，建议买入。',
        },
        decisionPanel: {
          confidence: '中',
          marketStructure: '短线',
          idealEntry: '121.80 - 124.60（理想买点）',
          backupEntry: '119.50（次级买点）',
          stopLoss: '117.40（止损）',
          target: '133.50（目标价）',
          positionSizing: '仓位建议 20%',
          buildStrategy: '回踩后买入并加仓。',
          riskControlStrategy: '跌破后止损。',
          noPositionAdvice: '空仓建议等待理想买点。',
          holderAdvice: '持仓建议继续加仓。',
          executionReminders: ['不要把 provider_timeout 暴露给消费者。'],
        },
        reasonLayer: {
          coreReasons: ['价格仍需继续跟踪。'],
          topRisk: '止损线 117.40。',
        },
        technicalFields: [
          { label: '理想买点', value: '121.80 - 124.60' },
          { label: 'MACD', value: '二次扩张' },
        ],
        battleFields: [
          { label: '止损', value: '117.40（止损）' },
          { label: '目标价', value: '133.50（目标价）' },
        ],
        battlePlanCompact: {
          cards: [
            { label: '仓位建议', value: '20%' },
          ],
          notes: [
            { label: 'entry', value: '买入后持有。' },
          ],
        },
        coverageNotes: {
          dataSources: ['Yahoo Finance provider detail'],
          coverageGaps: ['provider_timeout'],
          conflictNotes: ['reasonCode=provider_timeout'],
          methodNotes: ['raw_result_marker'],
        },
        checklistItems: [
          { status: 'pass', icon: 'ok', text: '买入动作已确认' },
        ],
      },
    },
    decisionTrace: {
      symbol: 'ORCL',
      market: 'US',
      dataSources: [
        { name: 'quote', status: 'fallback', provider: 'Finnhub' },
      ],
    },
    dataQualityReport: {
      confidenceCap: 40,
      reasonCodes: ['provider_timeout'],
    },
  };
}

describe('FullDecisionReportDrawer no-advice guard', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('maps action fields to observation language and hides raw diagnostic fields', () => {
    render(
      <FullDecisionReportDrawer
        dashboard={{
          ticker: 'ORCL',
          decision: {
            company: 'Oracle',
            heroValue: '74',
            confidenceValue: '中',
            signalLabel: '买入',
            scoreValue: '上行后卖出',
            summary: '建议买入，目标价看 133.50。',
            reasonBody: '价格仍需继续跟踪。',
          },
        }}
        isOpen
        onClose={() => undefined}
        report={buildUnsafeReportFixture()}
      />,
    );

    const report = screen.getByTestId('home-bento-full-report-drawer');

    expect(within(report).getAllByText('研究包完整度').length).toBeGreaterThan(0);
    expect(within(report).getAllByText('继续跟踪').length).toBeGreaterThan(0);
    expect(within(report).getAllByText('数据不足').length).toBeGreaterThan(0);
    expect(within(report).getAllByText('参考区间').length).toBeGreaterThan(0);
    expect(within(report).getAllByText('上方观察区').length).toBeGreaterThan(0);
    expect(within(report).getAllByText('风险边界').length).toBeGreaterThan(0);
    expect(within(report).getAllByText('关键价格区间').length).toBeGreaterThan(0);
    expect(report).toHaveTextContent('121.80 - 124.60');
    expect(report).toHaveTextContent('117.40');
    expect(report).toHaveTextContent('133.50');
    expect(report).not.toHaveTextContent(forbiddenConsumerReportPattern);
  });

  it('copies consumer-safe markdown when exporting the report text', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });

    render(
      <FullDecisionReportDrawer
        dashboard={{
          ticker: 'ORCL',
          decision: {
            company: 'Oracle',
            heroValue: '74',
            confidenceValue: '中',
            signalLabel: '买入',
            scoreValue: '上行后卖出',
            summary: '建议买入，目标价看 133.50。',
            reasonBody: '价格仍需继续跟踪。',
          },
        }}
        isOpen
        onClose={() => undefined}
        report={buildUnsafeReportFixture()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '复制报告' }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledTimes(1);
    });
    expect(writeText.mock.calls[0]?.[0]).toContain('研究包完整度');
    expect(writeText.mock.calls[0]?.[0]).toContain('参考区间');
    expect(writeText.mock.calls[0]?.[0]).toContain('上方观察区');
    expect(writeText.mock.calls[0]?.[0]).toContain('风险边界');
    expect(writeText.mock.calls[0]?.[0]).toContain('关键价格区间');
    expect(writeText.mock.calls[0]?.[0]).not.toMatch(forbiddenConsumerReportPattern);
  });

  it('downloads the same consumer-safe no-advice markdown report text', async () => {
    let exportedBlob: Blob | undefined;
    const createObjectURL = vi.fn((blob: Blob) => {
      exportedBlob = blob;
      return 'blob:full-report-markdown';
    });
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL,
      revokeObjectURL,
    });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);

    render(
      <FullDecisionReportDrawer
        dashboard={{
          ticker: 'ORCL',
          decision: {
            company: 'Oracle',
            heroValue: '74',
            confidenceValue: '中',
            signalLabel: '买入',
            scoreValue: '上行后卖出',
            summary: '建议买入，目标价看 133.50。',
            reasonBody: '价格仍需继续跟踪。',
          },
        }}
        isOpen
        onClose={() => undefined}
        report={buildUnsafeReportFixture()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '导出 Markdown' }));

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(exportedBlob).toBeInstanceOf(Blob);

    const markdown = await exportedBlob?.text();

    expect(markdown).toContain('研究包完整度');
    expect(markdown).toContain('参考区间');
    expect(markdown).toContain('上方观察区');
    expect(markdown).toContain('风险边界');
    expect(markdown).toContain('关键价格区间');
    expect(markdown).not.toMatch(forbiddenConsumerReportPattern);
    expect(markdown).not.toMatch(/raw evidence|raw payload|provider|debug|cache|buy|sell|target|stop|position[- ]?sizing/i);
  });
});
