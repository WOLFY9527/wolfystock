import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { ReportMarkdown } from '../ReportMarkdown';
import { historyApi } from '../../../api/history';
import type { StandardReport } from '../../../types/analysis';

vi.mock('../../../api/history', () => ({
  historyApi: {
    getMarkdown: vi.fn(),
  },
}));

vi.mock('../../common/Drawer', () => ({
  Drawer: ({ children }: { children: ReactNode }) => <div data-testid="drawer-shell">{children}</div>,
}));

describe('ReportMarkdown', () => {
  it('renders coverage audit categories while preserving markdown content', async () => {
    const standardReport: StandardReport = {
      tableSections: {
        technical: {
          title: '技术面',
          fields: [
            { label: 'VWAP', value: 'NA（字段待接入）' },
            { label: 'Beta', value: 'NA（接口未返回）' },
          ],
        },
      },
      coverageNotes: {
        missingFieldNotes: ['盘后成交量：当前数据源未提供'],
      },
    };

    vi.mocked(historyApi.getMarkdown).mockResolvedValueOnce(`## Decision Summary\n### Execution Plan\n#### Current Action\n- **Bullish Factors**: 数据中心需求回暖\n- 扩展交易数据：NA（当前市场不支持）\n| Field | Value | Basis |\n| --- | --- | --- |\n| 盘前成交额 | NA（会话不适用） | Session |`);

    render(
      <ReportMarkdown
        recordId={1}
        stockName="贵州茅台"
        stockCode="600519"
        onClose={() => undefined}
        standardReport={standardReport}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('缺失字段')).toBeInTheDocument();
    });

    expect(screen.getByText(/缺失字段总数[:：]\s*5/)).toBeInTheDocument();
    expect(screen.getAllByText(/字段待接入/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/已接入但本次记录未返回/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/当前数据源未提供/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/当前市场\/会话不适用/).length).toBeGreaterThan(0);
    expect(screen.getByText('决策摘要')).toBeInTheDocument();
    expect(screen.getByText('执行计划')).toBeInTheDocument();
    expect(screen.getByText('当前动作')).toBeInTheDocument();
    expect(screen.getByText(/看多因素/)).toBeInTheDocument();
  });

  it('shows no-missing message when markdown and report have no NA fields', async () => {
    vi.mocked(historyApi.getMarkdown).mockResolvedValueOnce('## Full Markdown\n- 所有字段均已返回');

    render(
      <ReportMarkdown
        recordId={2}
        stockName="NVIDIA"
        stockCode="NVDA"
        onClose={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('未识别缺失字段。')).toBeInTheDocument();
    });
  });

  it('leads with an executive summary and keeps technical evidence collapsed', async () => {
    const standardReport: StandardReport = {
      summaryPanel: {
        oneSentence: '只读证据显示仍处观察状态。',
        operationAdvice: '仅观察',
        score: 68,
      },
      decisionPanel: {
        confidence: '中等',
        riskControlStrategy: '跌破关键支撑则观察假设失效。',
      },
      reasonLayer: {
        topRisk: '财报后波动仍未收敛。',
      },
      technicalFields: [
        { label: 'RSI-14', value: '54' },
        { label: 'MACD', value: '拐点初现' },
      ],
      fundamentalFields: [
        { label: 'Revenue', value: '+9.4%' },
      ],
      coverageNotes: {
        dataSources: ['quote: used', 'fundamental: partial'],
      },
    };

    render(
      <ReportMarkdown
        recordId={3}
        stockName="Oracle"
        stockCode="ORCL"
        onClose={() => undefined}
        standardReport={standardReport}
        initialContent="## Raw Technical Detail\n| Field | Value |\n| --- | --- |\n| RSI-14 | 54 |"
      />,
    );

    const executiveSummary = await screen.findByTestId('report-executive-summary');
    const evidenceDetails = screen.getByTestId('report-technical-evidence-details');
    const readingSurface = screen.getByTestId('full-report-reading-surface');

    expect(executiveSummary).toHaveTextContent('执行摘要');
    expect(executiveSummary).toHaveTextContent('只读证据显示仍处观察状态。');
    expect(executiveSummary).toHaveTextContent('结论');
    expect(executiveSummary).toHaveTextContent('置信度');
    expect(executiveSummary).toHaveTextContent('关键风险');
    expect(evidenceDetails).not.toHaveAttribute('open');
    expect(readingSurface.firstElementChild).toBe(executiveSummary);
  });
});
