import { fireEvent, render, screen, waitFor, waitForElementToBeRemoved, within } from '@testing-library/react';
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

const forbiddenDefaultVisiblePattern =
  /买入|卖出|建仓|调仓|止损|止盈|目标价|仓位建议|\bbuy\b|\bsell\b|\bstop(?: loss)?\b|\btarget\b|position[- ]?sizing|reasonCode|sourceTier|sourceType|raw_ai_response|provider_timeout|fallback_cache|backend snake_case/i;

const openTechnicalDetails = async (label: string) => {
  const technicalDetails = await screen.findByTestId('report-technical-evidence-details');
  fireEvent.click(within(technicalDetails).getByText(label));

  const loading = screen.queryByTestId('report-technical-details-loading');
  if (loading) {
    await waitForElementToBeRemoved(loading, { timeout: 5000 });
  }

  await screen.findByTestId('report-technical-details-renderer', {}, { timeout: 5000 });
};

describe('ReportMarkdown', () => {
  it('keeps coverage audit behind disclosure while preserving markdown content', async () => {
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
      expect(screen.getByTestId('report-executive-summary')).toBeInTheDocument();
    });

    expect(screen.getByTestId('report-executive-summary')).toHaveTextContent('部分数据暂不可用，当前解读仅供观察。');
    expect(screen.queryByTestId('report-coverage-audit-panel')).not.toBeInTheDocument();
    expect(screen.queryByText(/缺失字段总数[:：]\s*5/)).not.toBeInTheDocument();
    expect(screen.queryByText('数据覆盖说明')).not.toBeInTheDocument();
    await openTechnicalDetails('数据覆盖与证据明细');

    const coverageAudit = screen.getByTestId('report-coverage-audit-panel');
    expect(coverageAudit).toHaveTextContent(/缺失字段总数[:：]\s*5/);
    expect(coverageAudit).toHaveTextContent(/暂不覆盖/);
    expect(coverageAudit).toHaveTextContent(/本次暂未返回/);
    expect(coverageAudit).toHaveTextContent(/部分数据暂不可用/);
    expect(coverageAudit).toHaveTextContent(/本次不适用/);
    await waitFor(() => {
      expect(screen.getByText('研究摘要')).toBeInTheDocument();
    });
    expect(screen.getByText('研究摘要')).toBeInTheDocument();
    expect(screen.getByText('观察计划')).toBeInTheDocument();
    expect(screen.getByText('当前观察')).toBeInTheDocument();
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

    expect(await screen.findByTestId('report-executive-summary')).toHaveTextContent('数据覆盖未发现明显缺口。');
    expect(screen.queryByText('未识别缺失字段。')).not.toBeInTheDocument();

    await openTechnicalDetails('数据覆盖与证据明细');

    expect(screen.getByTestId('report-coverage-audit-panel')).toHaveTextContent('未识别缺失字段。');
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

  it('keeps executive summary and coverage audit synchronous without mounting technical details before disclosure opens', async () => {
    render(
      <ReportMarkdown
        recordId={4}
        stockName="Oracle"
        stockCode="ORCL"
        onClose={() => undefined}
        standardReport={{
          coverageNotes: {
            missingFieldNotes: ['VWAP：字段待接入'],
          },
        }}
        initialContent={'## Decision Summary\n| Field | Value |\n| --- | --- |\n| VWAP | NA（字段待接入） |'}
      />,
    );

    expect(await screen.findByTestId('report-executive-summary')).toHaveTextContent('执行摘要');
    expect(screen.queryByTestId('report-coverage-audit-panel')).not.toBeInTheDocument();
    expect(screen.queryByText('数据覆盖说明')).not.toBeInTheDocument();
    expect(screen.queryByText('研究摘要')).not.toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: '字段' })).not.toBeInTheDocument();
  });

  it('renders technical markdown headings and tables after opening the disclosure', async () => {
    render(
      <ReportMarkdown
        recordId={5}
        stockName="Oracle"
        stockCode="ORCL"
        onClose={() => undefined}
        initialContent={'## Decision Summary\n### Execution Plan\n| Field | Value |\n| --- | --- |\n| VWAP | Ready |'}
      />,
    );

    await openTechnicalDetails('数据覆盖与证据明细');

    await waitFor(() => {
      expect(screen.getByText('研究摘要')).toBeInTheDocument();
    });
    expect(screen.getByText('观察计划')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: '字段' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Ready' })).toBeInTheDocument();
  });

  it('keeps default summary copy consumer-safe when upstream report text is diagnostic or action-oriented', async () => {
    render(
      <ReportMarkdown
        recordId={6}
        stockName="Oracle"
        stockCode="ORCL"
        onClose={() => undefined}
        standardReport={{
          summaryPanel: {
            oneSentence: 'reasonCode=provider_timeout sourceTier=raw_ai_response',
            operationAdvice: '买入',
          },
          decisionPanel: {
            confidence: 'sourceType=official_public',
            riskControlStrategy: '止损 117.40',
          },
        }}
        initialContent="## Raw Technical Detail\nreasonCode=provider_timeout"
      />,
    );

    const executiveSummary = await screen.findByTestId('report-executive-summary');
    expect(executiveSummary).toHaveTextContent('报告内容已生成，可继续复核。');
    expect(executiveSummary).toHaveTextContent('继续跟踪');
    expect(executiveSummary).toHaveTextContent('未标注');
    expect(executiveSummary).toHaveTextContent('风险边界用于说明不确定性。');
    expect(executiveSummary).not.toHaveTextContent(forbiddenDefaultVisiblePattern);
  });

  it('does not surface backend diagnostic errors as default visible copy', async () => {
    vi.mocked(historyApi.getMarkdown).mockRejectedValueOnce(
      new Error('provider_timeout fallback_cache sourceTier raw_ai_response'),
    );

    render(
      <ReportMarkdown
        recordId={7}
        stockName="Oracle"
        stockCode="ORCL"
        onClose={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('加载报告失败')).toBeInTheDocument();
    });
    expect(screen.getByTestId('drawer-shell')).not.toHaveTextContent(forbiddenDefaultVisiblePattern);
  });
});
