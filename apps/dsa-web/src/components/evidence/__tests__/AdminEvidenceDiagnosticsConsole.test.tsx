import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AdminEvidenceDiagnosticsConsole } from '../AdminEvidenceDiagnosticsConsole';

const {
  mockGetRecentWatchlists,
  mockGetRun,
  mockGetRotationRadar,
  mockGetRuleBacktestRuns,
  mockGetRuleBacktestRun,
  mockGetSnapshot,
  mockEvaluateDecision,
} = vi.hoisted(() => ({
  mockGetRecentWatchlists: vi.fn(),
  mockGetRun: vi.fn(),
  mockGetRotationRadar: vi.fn(),
  mockGetRuleBacktestRuns: vi.fn(),
  mockGetRuleBacktestRun: vi.fn(),
  mockGetSnapshot: vi.fn(),
  mockEvaluateDecision: vi.fn(),
}));

vi.mock('../../../api/scanner', () => ({
  scannerApi: {
    getRecentWatchlists: mockGetRecentWatchlists,
    getRun: mockGetRun,
  },
}));

vi.mock('../../../api/marketRotation', () => ({
  marketRotationApi: {
    getRotationRadar: mockGetRotationRadar,
  },
}));

vi.mock('../../../api/backtest', () => ({
  backtestApi: {
    getRuleBacktestRuns: mockGetRuleBacktestRuns,
    getRuleBacktestRun: mockGetRuleBacktestRun,
  },
}));

vi.mock('../../../api/portfolio', () => ({
  portfolioApi: {
    getSnapshot: mockGetSnapshot,
  },
}));

vi.mock('../../../api/optionsLab', () => ({
  optionsLabApi: {
    evaluateDecision: mockEvaluateDecision,
  },
}));

function primeRepresentativeFixtures() {
  mockGetRecentWatchlists.mockResolvedValue({
    total: 1,
    page: 1,
    limit: 10,
    items: [{ id: 42 }],
  });
  mockGetRun.mockResolvedValue({
    id: 42,
    market: 'us',
    profile: 'us_preopen_v1',
    shortlist: [
      {
        symbol: 'WULF',
        name: 'TeraWulf',
        rank: 1,
        score: 60,
        diagnostics: {
          evidence_packet: {
            userFacingLabels: ['仅观察', 'provider_timeout'],
            freshnessState: 'stale',
            adminReasonCodes: ['provider_timeout'],
          },
        },
      },
    ],
    selected: [],
    candidates: [],
  });
  mockGetRotationRadar.mockResolvedValue({
    generatedAt: '2026-05-10T08:00:00Z',
    themes: [
      {
        id: 'ai-app',
        name: 'AI 应用',
        englishName: 'AI Applications',
        rotationScore: 78,
        confidence: 0.72,
        stage: 'confirmed_rotation',
        freshness: 'delayed',
        isFallback: false,
        isStale: false,
        riskLabels: ['gap_fade_risk'],
        benchmark: 'QQQ',
        membersConfigured: ['APP'],
        newslessRotation: false,
        relativeStrength: {},
        volume: {},
        breadth: {},
        synchronization: {},
        leadership: {},
        members: [],
        evidence: [],
        noAdviceDisclosure: '仅用于观察资金轮动迹象，非买卖建议。',
        representativeSymbols: ['APP'],
        rotationStateEvidence: {
          state: 'insufficient_evidence',
          stateLabel: '轮动代理证据',
          flowEvidenceType: 'proxy_only',
          flowLanguageAllowed: false,
          requiredDataStatus: {
            hasSufficientEvidence: false,
            summaryLabel: '分类观察',
          },
          riskLabels: ['gap_fade_risk'],
          adminReasonCodes: ['proxy_windows_missing'],
        },
      },
    ],
  });
  mockGetRuleBacktestRuns.mockResolvedValue({
    total: 1,
    page: 1,
    limit: 20,
    items: [{ id: 7, code: 'ORCL' }],
  });
  mockGetRuleBacktestRun.mockResolvedValue({
    id: 7,
    code: 'ORCL',
    strategyText: 'demo',
    parsedStrategy: {
      version: 'v1',
      timeframe: 'daily',
      sourceText: 'demo',
      normalizedText: 'demo',
      entry: { type: 'group', op: 'and', rules: [] },
      exit: { type: 'group', op: 'or', rules: [] },
      confidence: 0.9,
      needsConfirmation: false,
      ambiguities: [],
      summary: {},
      maxLookback: 1,
    },
    strategyHash: 'hash',
    timeframe: 'daily',
    lookbackBars: 120,
    initialCapital: 100000,
    feeBps: 5,
    slippageBps: 10,
    needsConfirmation: false,
    warnings: [],
    status: 'completed',
    statusHistory: [],
    tradeCount: 0,
    winCount: 0,
    lossCount: 0,
    summary: {},
    executionAssumptions: {},
    benchmarkCurve: [],
    benchmarkSummary: {},
    dailyReturnSeries: [],
    exposureCurve: [],
    equityCurve: [],
    trades: [],
    professionalReadiness: {
      overallState: 'research_prototype',
      professionalQuantReady: false,
      adjustedDataState: 'unverified',
      corporateActionState: 'unverified',
      tradingCalendarState: 'available_bars_only',
    },
  });
  mockGetSnapshot.mockResolvedValue({
    asOf: '2026-05-10',
    costMethod: 'fifo',
    currency: 'USD',
    accountCount: 1,
    totalCash: 1000,
    totalMarketValue: 5000,
    totalEquity: 6000,
    realizedPnl: 0,
    unrealizedPnl: 100,
    feeTotal: 0,
    taxTotal: 0,
    fxStale: true,
    accounts: [
      {
        accountId: 1,
        accountName: 'Main',
        market: 'us',
        baseCurrency: 'USD',
        asOf: '2026-05-10',
        costMethod: 'fifo',
        totalCash: 1000,
        totalMarketValue: 5000,
        totalEquity: 6000,
        realizedPnl: 0,
        unrealizedPnl: 100,
        feeTotal: 0,
        taxTotal: 0,
        fxStale: true,
        positions: [
          {
            symbol: 'AAPL',
            market: 'us',
            currency: 'USD',
            quantity: 10,
            avgCost: 150,
            totalCost: 1500,
            lastPrice: 180,
            marketValueBase: 1800,
            unrealizedPnlBase: 300,
            valuationCurrency: 'USD',
          },
        ],
      },
    ],
    fxFreshnessState: 'stale',
    holdingsLineageState: 'missing',
    cashLedgerCompletenessState: 'missing',
    benchmarkMappingState: 'missing',
    factorMappingState: 'missing',
    confidenceCap: {
      value: 60,
      reasonCodes: ['fx_rate_stale', 'benchmark_mapping_missing'],
      limitationLabels: ['仅供风险观察', '持仓来源待核验', '现金流水不完整'],
    },
    portfolioRiskEvidence: {
      limitationLabels: ['FX 汇率已过期', '基准映射暂缺', '因子映射暂缺'],
    },
  });
  mockEvaluateDecision.mockResolvedValue({
    symbol: 'WULF',
    strategy: 'bull_call_spread',
    decisionLabel: '数据不足，禁止判断',
    gateDecision: 'blocked',
    gateIssues: ['synthetic_or_fixture_data_not_decision_grade', 'liquidity_below_threshold'],
    failClosedReasonCodes: ['synthetic_or_fixture_data_not_decision_grade', 'liquidity_below_threshold'],
    decisionGrade: false,
    dataQualityGates: { overall: 'synthetic_demo_only' },
    liquidityGates: { overall: 'weak' },
    freshness: {
      freshness: 'synthetic_delayed',
      asOf: '2026-05-10T08:00:00Z',
    },
  });
}

describe('AdminEvidenceDiagnosticsConsole', () => {
  it('renders a compact cross-engine summary strip and representative evidence chips', async () => {
    primeRepresentativeFixtures();

    render(<AdminEvidenceDiagnosticsConsole />);

    const summaryStrip = await screen.findByTestId('admin-evidence-diagnostics-summary-strip');
    await waitFor(() => {
      expect(within(summaryStrip).getByTestId('admin-evidence-diagnostic-summary-scanner')).toHaveTextContent('仅供观察');
      expect(within(summaryStrip).getByTestId('admin-evidence-diagnostic-summary-rotation')).toHaveTextContent('仅供观察');
      expect(within(summaryStrip).getByTestId('admin-evidence-diagnostic-summary-options')).toHaveTextContent('数据不足，禁止判断');
      expect(within(summaryStrip).getByTestId('admin-evidence-diagnostic-summary-backtest')).toHaveTextContent('仅供观察');
      expect(within(summaryStrip).getByTestId('admin-evidence-diagnostic-summary-portfolio_risk')).toHaveTextContent('仅供观察');
    });

    const scannerSection = await screen.findByTestId('admin-evidence-diagnostic-engine-scanner');
    expect(within(scannerSection).getByText('Scanner 候选证据')).toBeInTheDocument();
    expect(within(scannerSection).getByText('部分外部数据暂不可用')).toBeInTheDocument();
    expect(within(scannerSection).getByText('数据已过期')).toBeInTheDocument();
    expect(within(scannerSection).queryByText('provider_timeout')).not.toBeInTheDocument();

    const rotationSection = screen.getByTestId('admin-evidence-diagnostic-engine-rotation');
    expect(within(rotationSection).getByText('Rotation 状态证据')).toBeInTheDocument();
    expect(within(rotationSection).getByText('轮动代理证据')).toBeInTheDocument();
    expect(within(rotationSection).getByText('真实资金流暂缺')).toBeInTheDocument();

    const optionsSection = screen.getByTestId('admin-evidence-diagnostic-engine-options');
    expect(within(optionsSection).getByText('Options 门禁证据')).toBeInTheDocument();
    expect(within(optionsSection).getByText('演示数据')).toBeInTheDocument();

    const backtestSection = screen.getByTestId('admin-evidence-diagnostic-engine-backtest');
    expect(within(backtestSection).getByText('Backtest 就绪度')).toBeInTheDocument();
    expect(within(backtestSection).getByText('研究级回测')).toBeInTheDocument();
    expect(within(backtestSection).getByText('专业级条件未满足')).toBeInTheDocument();

    const portfolioSection = screen.getByTestId('admin-evidence-diagnostic-engine-portfolio_risk');
    expect(within(portfolioSection).getByText('Portfolio 风险证据')).toBeInTheDocument();
    expect(within(portfolioSection).getByText('仅供风险观察')).toBeInTheDocument();
    expect(within(portfolioSection).getByText('FX 汇率已过期')).toBeInTheDocument();
  });

  it('keeps operator reason codes collapsed until the admin disclosure is opened', async () => {
    primeRepresentativeFixtures();

    render(<AdminEvidenceDiagnosticsConsole />);

    const scannerSection = await screen.findByTestId('admin-evidence-diagnostic-engine-scanner');
    const disclosure = await within(scannerSection).findByTestId('admin-evidence-operator-details-scanner');

    expect(disclosure).not.toHaveAttribute('open');
    expect(within(scannerSection).queryByText('provider_timeout')).not.toBeInTheDocument();

    fireEvent.click(within(disclosure).getByRole('button', { name: /展开/i }));

    await waitFor(() => {
      expect(within(disclosure).getByText('provider_timeout')).toBeInTheDocument();
    });
  });
});
