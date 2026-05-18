import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { analysisApi } from '../../api/analysis';
import { createApiError, createParsedApiError } from '../../api/error';
import { historyApi } from '../../api/history';
import { normalizeFrontendReportContract } from '../../api/reportNormalizer';
import { UiPreferencesProvider } from '../../contexts/UiPreferencesContext';
import { stocksApi } from '../../api/stocks';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { useStockPoolStore } from '../../stores';
import { resolveHomeCandlestickTooltipPosition } from '../../components/home-bento/HomeCandlestickChart';
import { buildInstitutionalReportMarkdown, getCompanyWithTicker } from '../../utils/homeReportIdentity';
import HomeSurfacePage from '../HomeSurfacePage';

const { useProductSurfaceMock } = vi.hoisted(() => ({
  useProductSurfaceMock: vi.fn(),
}));

vi.mock('../../hooks/useProductSurface', () => ({
  useProductSurface: () => useProductSurfaceMock(),
}));

vi.mock('../../api/history', () => ({
  historyApi: {
    getList: vi.fn(),
    getDetail: vi.fn(),
    getNews: vi.fn(),
    getMarkdown: vi.fn(),
    deleteRecords: vi.fn(),
  },
}));

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    verifyTickerExists: vi.fn(),
    getHistory: vi.fn(),
  },
}));

vi.mock('../../api/analysis', async () => {
  const actual = await vi.importActual<typeof import('../../api/analysis')>('../../api/analysis');
  return {
    ...actual,
    analysisApi: {
      ...actual.analysisApi,
      analyzeAsync: vi.fn(),
      getTasks: vi.fn(),
      getTaskProgress: vi.fn(),
    },
  };
});

vi.mock('../../hooks/useTaskStream', () => ({
  useTaskStream: vi.fn(() => ({
    isConnected: false,
    reconnect: vi.fn(),
    disconnect: vi.fn(),
  })),
}));

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const defaultHistoryReport = {
  meta: {
    queryId: 'q3',
    stockCode: 'ORCL',
    stockName: 'Oracle',
    reportType: 'detailed' as const,
    createdAt: '2026-04-27T08:00:00Z',
    reportGeneratedAt: '2026-04-27T08:03:00Z',
  },
  summary: {
    analysisSummary: 'Oracle is holding its post-earnings platform.',
    operationAdvice: 'Wait for a controlled pullback before adding.',
    trendPrediction: 'Constructive for the next 72 hours.',
    sentimentScore: 78,
    sentimentLabel: 'Bullish',
  },
  strategy: {
    idealBuy: '121.80 - 124.60',
    stopLoss: '117.40',
    takeProfit: '133.50',
  },
  details: {
    dataQualityReport: {
      dataQualityTier: 'analysis_grade',
      dataQualityScore: 68,
      requiredAvailable: true,
      importantMissing: ['fundamentals.eps'],
      optionalMissing: ['optional_enrichment_pending'],
      staleSources: [],
      providerTimeouts: ['gnews:news'],
      providerCooldowns: ['fmp:fundamentals'],
      confidenceCap: 70,
      reasonCodes: ['important_data_missing', 'optional_enrichment_missing'],
      freshness: { marketSessionDate: '2026-05-05' },
      enrichmentStatus: 'pending',
      enrichmentSources: ['news', 'sentiment', 'detailed_fundamentals'],
      completedSources: ['sentiment'],
      pendingSources: ['news'],
      failedSources: [],
      skippedSources: ['detailed_fundamentals'],
      enrichmentReasons: { news: ['optional_news_timeout'] },
      enrichmentUpdatedAt: '2026-05-06T01:01:00Z',
      enrichmentAsOf: '2026-05-06T01:00:00Z',
    },
    standardReport: {
      summaryPanel: {
        stock: 'Oracle',
        ticker: 'ORCL',
        oneSentence: 'Cloud backlog keeps the medium-term floor intact.',
      },
      decisionContext: {
        shortTermView: 'Post-earnings strength still holds the upper rail',
      },
      decisionPanel: {
        idealEntry: '121.80 - 124.60',
        target: '133.50',
        stopLoss: '117.40',
        buildStrategy: 'Start light, then add only after the pullback stays orderly.',
      },
      reasonLayer: {
        coreReasons: ['Institutional sponsorship remains intact after earnings.'],
      },
      technicalFields: [
        { label: 'MACD', value: 'Second expansion above zero' },
        { label: 'Moving Averages', value: 'MA20 lifting MA60' },
      ],
      fundamentalFields: [
        { label: 'Revenue Growth', value: '+9.4%' },
        { label: 'Free Cash Flow', value: '$12.1B' },
      ],
    },
  },
  dataQualityReport: {
    dataQualityTier: 'analysis_grade',
    dataQualityScore: 68,
    requiredAvailable: true,
    importantMissing: ['fundamentals.eps'],
    optionalMissing: ['optional_enrichment_pending'],
    staleSources: [],
    providerTimeouts: ['gnews:news'],
    providerCooldowns: ['fmp:fundamentals'],
    confidenceCap: 70,
    reasonCodes: ['important_data_missing', 'optional_enrichment_missing'],
    freshness: { marketSessionDate: '2026-05-05' },
    enrichmentStatus: 'pending',
    enrichmentSources: ['news', 'sentiment', 'detailed_fundamentals'],
    completedSources: ['sentiment'],
    pendingSources: ['news'],
    failedSources: [],
    skippedSources: ['detailed_fundamentals'],
    enrichmentReasons: { news: ['optional_news_timeout'] },
    enrichmentUpdatedAt: '2026-05-06T01:01:00Z',
    enrichmentAsOf: '2026-05-06T01:00:00Z',
  },
  decisionTrace: {
    engineVersion: 'analysis_decision_trace_v1',
    mode: 'rule_scoring_with_llm_explanation',
    endpoint: '/api/v1/analysis/analyze',
    taskId: 'q3',
    symbol: 'ORCL',
    market: 'US',
    decisionFields: {
      action: { value: 'hold', source: 'rule', confidence: 0.78, notes: 'stabilized score path' },
      score: { value: 78, source: 'rule', scale: '0-100' },
      confidence: { value: '高', source: 'llm' },
      entry: { value: '121.80 - 124.60', source: 'llm' },
      target: { value: '133.50', source: 'llm' },
      stop: { value: '117.40', source: 'llm' },
    },
    dataSources: [
      { name: 'quote', status: 'used', provider: 'Yahoo Finance' },
      { name: 'fundamental', status: 'fallback', provider: 'FMP' },
      { name: 'news', status: 'missing', provider: null },
    ],
    signals: [
      { name: 'MA alignment', value: 'bullish', impact: 'positive', source: 'technical_rule' },
    ],
    llm: {
      used: true,
      provider: 'openai',
      model: 'openai/gpt-4.1-mini',
      template: 'decision_dashboard_v2',
      structuredOutput: true,
      schemaValidated: true,
      promptExposed: false,
    },
    conflicts: [
      {
        type: 'action_plan_mismatch',
        severity: 'warning',
        message: 'Action says sell but plan includes entry/accumulation.',
      },
    ],
    limitations: ['fundamental data partial'],
  },
};

const homeDailyCandles = Array.from({ length: 24 }, (_, index) => {
  const day = String(index + 1).padStart(2, '0');
  const open = 120 + index * 0.45;
  const close = open + (index % 3 === 0 ? -0.35 : 0.72);
  return {
    date: `2026-04-${day}`,
    open: Number(open.toFixed(2)),
    high: Number((Math.max(open, close) + 1.1).toFixed(2)),
    low: Number((Math.min(open, close) - 0.9).toFixed(2)),
    close: Number(close.toFixed(2)),
    volume: 8_000_000 + index * 120_000,
  };
});

describe('HomeSurfacePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    useStockPoolStore.getState().resetDashboardState();
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 3,
      page: 1,
      limit: 20,
      items: [
        { id: 3, queryId: 'q3', stockCode: 'ORCL', stockName: 'Oracle', companyName: 'Oracle', createdAt: '2026-04-27T08:00:00Z', generatedAt: '2026-04-27T08:03:00Z', isTest: false },
        { id: 2, queryId: 'q2', stockCode: 'TSLA', stockName: 'Tesla', companyName: 'Tesla', createdAt: '2026-04-27T07:00:00Z', generatedAt: '2026-04-27T07:05:00Z', isTest: false },
        { id: 1, queryId: 'q1', stockCode: 'NVDA', stockName: 'NVIDIA', companyName: 'NVIDIA', createdAt: '2026-04-27T06:00:00Z', generatedAt: '2026-04-27T06:04:00Z', isTest: false },
      ],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValue(defaultHistoryReport);
    vi.mocked(stocksApi.verifyTickerExists).mockResolvedValue({
      stockCode: 'TSLA',
      exists: true,
      stockName: 'Tesla',
    });
    vi.mocked(stocksApi.getHistory).mockResolvedValue({
      stockCode: 'ORCL',
      stockName: 'Oracle',
      period: 'daily',
      data: homeDailyCandles,
    });
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValue({
      taskId: 'task-1',
      status: 'pending',
      message: 'submitted',
    });
    vi.mocked(analysisApi.getTaskProgress).mockResolvedValue({
      taskId: 'task-1',
      stockCode: 'ORCL',
      stockName: 'Oracle',
      status: 'processing',
      progress: 18,
      modules: [],
    });
  });

  const renderSurface = (initialPath = '/') => render(
    <MemoryRouter initialEntries={[initialPath]}>
      <UiPreferencesProvider>
        <UiLanguageProvider>
          <HomeSurfacePage />
        </UiLanguageProvider>
      </UiPreferencesProvider>
    </MemoryRouter>,
  );

  it('renders the guest homepage when the current surface role is guest', () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: true });
    renderSurface();
    expect(screen.getByTestId('home-bento-dashboard')).toBeInTheDocument();
    expect(screen.getByTestId('guest-home-clean-search')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'WolfyStock 分析面板' })).toBeInTheDocument();
  });

  it('renders the signed-in ResearchConsole route for authenticated users', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    renderSurface();
    await screen.findByText('Oracle Corporation');
    const root = screen.getByTestId('home-bento-dashboard');
    const main = screen.getByTestId('home-bento-main');
    const stage = screen.getByTestId('home-research-stage');
    const researchConsole = screen.getByTestId('home-research-console');
    const commandBar = screen.getByTestId('home-research-command-bar');
    const board = screen.getByTestId('home-research-board');
    const rail = screen.getByTestId('home-research-context-rail');
    const headerStrip = screen.getByTestId('home-research-header-strip');
    const primaryWorkspace = screen.getByTestId('home-research-primary-workspace');
    const chartWorkspace = screen.getByTestId('home-research-chart-workspace');
    const secondaryDeck = screen.getByTestId('home-research-secondary-deck');
    const catalysts = screen.getByTestId('home-linear-events');
    const eventTable = screen.getByTestId('home-linear-events-table');
    const homeSearch = screen.getByTestId('home-bento-omnibar-input');
    const entryMetric = screen.getByTestId('home-bento-strategy-metric-观察区间');
    const targetMetric = screen.getByTestId('home-bento-strategy-metric-上方观察区');
    const stopLossMetric = screen.getByTestId('home-bento-strategy-metric-风险失效线');

    expect(root).toHaveAttribute('data-route-surface', 'ResearchConsole');
    expect(root).toHaveClass('w-full', 'flex', 'flex-1', 'min-h-0', 'min-w-0', 'flex-col', 'overflow-x-hidden');
    expect(root).toHaveClass('bg-transparent');
    expect(root.getAttribute('style') || '').not.toContain('radial-gradient');
    expect(main).toHaveClass('w-full', 'flex-1', 'min-w-0', 'flex', 'flex-col', 'min-h-0');
    expect(main.firstElementChild).toBe(stage);
    expect(stage).toHaveClass('home-research-stage', 'w-full', 'max-w-[1920px]', 'min-w-0', 'px-3');
    expect(stage).not.toHaveClass('lg:w-[96vw]', 'lg:max-w-[1840px]');
    expect(stage.contains(commandBar)).toBe(true);
    expect(stage.contains(researchConsole)).toBe(true);

    expect(researchConsole).toHaveAttribute('data-linear-primitive', 'research-console-shell');
    expect(researchConsole).toHaveAttribute('data-layout-zone', 'RouteConsole');
    expect(researchConsole).toHaveAttribute('data-visual-tier', 'dominant');
    expect(researchConsole).toHaveAttribute('data-surface-system', 'reflect-linear-console');
    expect(researchConsole).toHaveClass('w-full', 'max-w-full', 'rounded-none', 'border', 'border-transparent', 'bg-transparent', 'shadow-none');
    expect(researchConsole).not.toHaveClass('bg-[var(--wolfy-surface-console)]', 'shadow-[var(--wolfy-shadow-console)]');
    expect(researchConsole.contains(commandBar)).toBe(false);
    expect(researchConsole.contains(board)).toBe(true);
    expect(researchConsole.contains(rail)).toBe(true);
    expect(rail.closest('[data-testid="home-research-console"]')).toBe(researchConsole);
    expect(board.contains(rail)).toBe(true);
    expect(board.contains(secondaryDeck)).toBe(true);
    expect(commandBar.compareDocumentPosition(researchConsole) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    expect(commandBar).toHaveAttribute('data-linear-primitive', 'compact-filter-bar');
    expect(commandBar).toHaveAttribute('data-layout-zone', 'CommandBar');
    expect(commandBar).toHaveAttribute('data-surface-system', 'reflect-linear-console');
    expect(commandBar).toHaveClass('home-research-command-bar', 'rounded-xl', 'bg-[var(--wolfy-surface-input)]', 'border-[color:var(--wolfy-border-subtle)]');
    expect(headerStrip.closest('[data-layout-zone="HeaderStrip"]')).toBeInTheDocument();
    expect(primaryWorkspace.closest('[data-layout-zone="PrimaryWorkRegion"]')).toBeInTheDocument();
    expect(primaryWorkspace).toHaveClass('rounded-none', 'border-0', 'bg-transparent', 'px-0', 'py-0');
    expect(secondaryDeck).toHaveAttribute('data-linear-primitive', 'secondary-deck');
    expect(secondaryDeck).toHaveAttribute('data-layout-zone', 'SecondaryDeck');
    expect(secondaryDeck).toHaveClass('home-research-secondary-deck');
    expect(primaryWorkspace).toContainElement(secondaryDeck);
    expect(chartWorkspace.compareDocumentPosition(secondaryDeck) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    expect(board).toHaveAttribute('data-linear-primitive', 'console-board');
    expect(board).toHaveAttribute('data-surface-system', 'reflect-linear-console');
    expect(board).toHaveClass('relative', 'z-10', 'overflow-visible');
    expect(screen.getByTestId('home-research-board').firstElementChild).toHaveClass('home-research-fixed-grid', 'w-full', 'min-w-0');
    expect(rail).toHaveAttribute('data-linear-primitive', 'context-rail');
    expect(rail).toHaveAttribute('data-layout-zone', 'ContextRail');
    expect(rail).toHaveClass('home-research-context-rail', 'bg-transparent', 'divide-y-0', 'lg:border-l-0');

    expect(homeSearch).toHaveAttribute('placeholder', '输入代码唤醒 AI (如 ORCL)...');
    expect(homeSearch).toHaveValue('');
    expect(screen.getByTestId('home-bento-omnibar-input-shell')).toHaveClass('overflow-hidden', 'rounded-lg', 'border', 'border-[color:var(--wolfy-border-subtle)]', 'bg-[var(--wolfy-surface-console)]');
    expect(homeSearch).toHaveClass('bg-transparent', 'text-sm', 'leading-none', 'pl-11', 'caret-[#93C5FD]');
    expect(screen.getByTestId('home-bento-analyze-button')).toHaveTextContent('分析');
    expect(screen.getByTestId('home-bento-analyze-button')).toHaveClass('rounded-lg', 'bg-[var(--wolfy-accent)]');
    expect(within(commandBar).getByTestId('home-bento-history-drawer-trigger')).toBeInTheDocument();
    expect(within(commandBar).getByRole('button', { name: '历史记录' })).toBeInTheDocument();

    const decisionCard = screen.getByTestId('home-bento-card-decision');
    const heroRow = screen.getByTestId('home-bento-decision-hero-row');
    const keyLevels = screen.getByTestId('home-research-key-levels');
    expect(within(decisionCard).getByText('投资立场')).toBeInTheDocument();
    expect(within(decisionCard).getByText('综合评分')).toBeInTheDocument();
    expect(within(decisionCard).getByText('核心观点')).toBeInTheDocument();
    expect(within(decisionCard).getByText('价格触发')).toBeInTheDocument();
    expect(within(decisionCard).getByText('失效位')).toBeInTheDocument();
    expect(within(decisionCard).getByText('下一关注区间')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-header-actions')).toHaveTextContent('完整报告');
    expect(screen.getByTestId('home-bento-drawer-trigger-strategy')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-drawer-trigger-tech')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-drawer-trigger-fundamentals')).toBeInTheDocument();

    expect(screen.getByTestId('home-bento-decision-signal-hero')).toHaveTextContent('仅观察');
    expect(screen.getByTestId('home-bento-decision-score-value')).toHaveTextContent('78');
    expect(screen.getByTestId('home-bento-decision-conviction-value')).toHaveTextContent('高');
    expect(screen.getByTestId('home-bento-decision-core-metrics')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-insight')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-company-header')).toHaveTextContent('Oracle Corporation');
    expect(screen.getByTestId('home-bento-decision-ticker')).toHaveTextContent('ORCL');
    expect(screen.getByTestId('home-bento-decision-sector')).toHaveTextContent('科技');
    expect(screen.getByTestId('home-research-company-mark')).toHaveTextContent('OR');
    expect(screen.getByTestId('home-research-company-mark')).toHaveAttribute('data-company-mark', 'oracle-logo');
    expect(screen.getByTestId('home-research-company-mark')).toHaveClass('h-[72px]', 'w-[72px]', 'rounded-[14px]');
    expect(heroRow).toHaveAttribute('data-visual-role', 'hero-matrix');
    expect(heroRow).toHaveClass('home-research-hero-matrix', 'rounded-[8px]', 'border', 'bg-[var(--wolfy-surface-input)]');
    expect(screen.getByTestId('home-bento-decision-confidence-indicator')).toBeInTheDocument();

    expect(keyLevels).toHaveAttribute('data-linear-primitive', 'key-level-strip');
    expect(keyLevels).toHaveClass('rounded-[12px]', 'border', 'border-[color:var(--wolfy-divider)]');
    expect(primaryWorkspace.closest('[data-layout-zone="PrimaryWorkRegion"]')).toContainElement(keyLevels);
    expect(entryMetric.closest('[data-linear-primitive="key-level-strip"]')).toBe(keyLevels);
    expect(entryMetric).toHaveAttribute('data-key-level-order', '1');
    expect(stopLossMetric).toHaveAttribute('data-key-level-order', '2');
    expect(targetMetric).toHaveAttribute('data-key-level-order', '3');
    expect(entryMetric).not.toHaveClass('bg-white/[0.02]', 'border-white/[0.08]', 'p-6', 'col-span-2');
    expect(within(entryMetric).getByText('121.80 - 124.60')).toHaveClass('text-sm', 'font-semibold');
    expect(within(targetMetric).getByText('133.50')).toHaveClass('text-sm', 'font-semibold', 'text-emerald-400');
    expect(within(stopLossMetric).getByText('117.40')).toHaveClass('text-sm', 'font-semibold', 'text-rose-400');

    expect(chartWorkspace).toContainElement(await screen.findByTestId('home-candlestick-chart-frame'));
    expect(primaryWorkspace.closest('[data-layout-zone="PrimaryWorkRegion"]')).toContainElement(chartWorkspace);
    expect(screen.getByTestId('home-bento-decision-support-grid')).toBeInTheDocument();
    expect(screen.getByText('技术结构')).toBeInTheDocument();
    expect(screen.getByTestId('home-linear-technical-chart')).toHaveAttribute('data-chart-engine', 'echarts');
    expect(screen.getByTestId('home-linear-technical-chart')).toHaveAttribute('data-chart-source', 'stocks-history-daily');
    expect(screen.getByTestId('home-linear-technical-chart')).toHaveAttribute('data-visual-role', 'primary-chart');
    expect(screen.getByTestId('home-linear-technical-chart')).toHaveAttribute('data-surface-system', 'reflect-linear-console');
    expect(screen.getByTestId('home-linear-technical-chart')).toHaveClass('home-chart-well', 'rounded-none', 'border-0', 'bg-transparent');
    expect(screen.getByTestId('home-linear-technical-chart').getAttribute('style') || '').toContain('background: transparent');
    expect(screen.getByTestId('home-linear-technical-chart').getAttribute('style') || '').toContain('border-color: transparent');
    expect(screen.getByTestId('home-linear-technical-chart').getAttribute('style') || '').toContain('box-shadow: none');
    expect(screen.getByTestId('home-bento-decision-support-grid')).toHaveAttribute('data-visual-role', 'chart-adjacent-metrics');
    expect(screen.getByTestId('home-bento-decision-support-grid')).toHaveClass('home-research-signal-rail', 'xl:border-l');
    const macdSignal = screen.getByTestId('home-bento-tech-signal-MACD');
    const macdSignalValue = within(macdSignal).getByText('二次扩张');
    expect(macdSignal).toHaveClass('flex', 'min-w-0', 'flex-col', 'gap-1');
    expect(macdSignalValue).toHaveClass('text-xs', 'font-semibold', 'text-emerald-400', 'drop-shadow-[0_0_8px_rgba(52,211,153,0.4)]');
    expect(screen.getByTestId('home-bento-tech-signal-detail-MACD')).toHaveClass('block', 'w-full', 'overflow-hidden', 'text-ellipsis', 'whitespace-nowrap', 'text-xs', 'text-white/38');
    expect(screen.getByTestId('home-bento-tech-signal-detail-MACD')).toHaveAttribute('title', '零轴上方，动能再扩张。');

    expect(within(rail).getByText('研究框架')).toBeInTheDocument();
    expect(within(rail).getByText('数据质量与说明')).toBeInTheDocument();
    expect(within(rail).getByText('量化信号快照')).toBeInTheDocument();
    expect(screen.getByTestId('home-linear-quant-snapshot')).toHaveAttribute('data-research-card', 'quant-signal');
    expect(within(rail).getByText('覆盖状态')).toBeInTheDocument();
    expect(within(rail).getByText('关键缺口')).toBeInTheDocument();
    expect(within(rail).getByText('待补信息')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-strategy')).toHaveAttribute('data-research-card', 'opportunity');
    expect(screen.getByTestId('home-bento-card-fundamentals')).toHaveAttribute('data-research-card', 'data-context');
    const railSections = Array.from(rail.querySelectorAll('[data-rail-section]'))
      .map((node) => node.getAttribute('data-rail-section'));
    expect(railSections).toEqual(['research-framework', 'data-quality', 'quant-snapshot']);
    expect(rail.querySelectorAll('.home-research-rail-card')).toHaveLength(3);
    expect(rail.querySelector('[class*="bg-black"]')).toBeNull();

    expect(secondaryDeck).toContainElement(catalysts);
    expect(catalysts).toHaveAttribute('data-visual-role', 'attached-event-deck');
    expect(within(catalysts).getByText('近期催化剂 / 事件')).toBeInTheDocument();
    expect(eventTable).toHaveTextContent('事件');
    expect(eventTable).toHaveTextContent('类型');
    expect(eventTable).toHaveTextContent('影响方向');
    expect(eventTable).toHaveTextContent('重要性');
    expect(eventTable).toHaveTextContent('时间');
    expect(eventTable).toHaveTextContent('剩余');
    expect(eventTable).toHaveTextContent('备注');
    expect(screen.getByTestId('home-linear-events-empty')).toHaveTextContent('待补充数据');
    expect(screen.getAllByTestId(/home-linear-event-placeholder-row-/)).toHaveLength(3);
    expect(screen.getByTestId('home-linear-event-placeholder-row-0')).toHaveTextContent('待补充');
    expect(catalysts).not.toHaveTextContent('报告主线');
    expect(catalysts).not.toHaveTextContent('技术触发');
    expect(catalysts).not.toHaveTextContent('财报跟踪');
    expect(screen.getAllByText('RSI-14').length).toBeGreaterThan(0);
    expect(screen.getAllByText('MACD').length).toBeGreaterThan(0);
    expect(screen.queryByText('AI 信号方向')).not.toBeInTheDocument();
    expect(screen.queryByText('最近报告归因')).not.toBeInTheDocument();
    [
      '可信度较高',
      '决策依据可查看',
      '结果已整理',
      '摘要可读',
      '部分数据可用',
      '未发现主要证据冲突',
      '数据已整理',
      '结果可查看',
      '分析已完成',
      '可用于观察',
      '当前结论仅供参考',
    ].forEach((phrase) => {
      expect(screen.queryByText(phrase)).not.toBeInTheDocument();
    });

    expect(screen.getByTestId('home-bento-card-decision')).toHaveClass('min-w-0');
    expect(screen.getByTestId('home-bento-card-tech')).toHaveAttribute('data-research-card', 'risk-context');
    expect(screen.getByTestId('home-bento-card-decision')).not.toHaveClass('rounded-[24px]');
    expect(screen.getByTestId('home-bento-card-strategy').compareDocumentPosition(screen.getByTestId('home-bento-card-fundamentals')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByTestId('home-bento-card-tech').compareDocumentPosition(secondaryDeck) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByTestId('home-bento-secondary-grid')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-research-chart-section')).toContainElement(chartWorkspace);
    expect(within(root).queryAllByRole('button', { name: /设置|系统|管理员|Settings|Admin/i })).toHaveLength(0);

    expect(researchConsole.querySelector('[data-research-card] [data-research-card]')).toBeNull();
    const cardZones = Array.from(researchConsole.querySelectorAll('[data-research-card]'))
      .map((node) => node.closest('[data-layout-zone]')?.getAttribute('data-layout-zone'));
    expect(researchConsole.querySelectorAll('[data-research-card]').length).toBeLessThanOrEqual(5);
    expect(cardZones.every((zone) => zone === 'PrimaryWorkRegion' || zone === 'ContextRail')).toBe(true);
    expect(cardZones.filter((zone) => zone === 'PrimaryWorkRegion')).toHaveLength(2);
    expect(cardZones.filter((zone) => zone === 'ContextRail')).toHaveLength(3);
  });

  it('shows only verified catalyst-like events when report event data exists', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getDetail).mockResolvedValueOnce({
      ...defaultHistoryReport,
      details: {
        ...defaultHistoryReport.details,
        standardReport: {
          ...defaultHistoryReport.details.standardReport,
          reasonLayer: {
            ...defaultHistoryReport.details.standardReport.reasonLayer,
            topCatalyst: '均线结构修复',
            latestKeyUpdate: '公司发布云基础设施更新并扩大客户合作',
          },
          highlights: {
            latestNews: ['Oracle 公告 2026-06-12 举行业绩电话会'],
            positiveCatalysts: ['数据状态可用'],
            earningsOutlook: '财报跟踪',
          },
          earningsFields: [
            { label: '下一次财报', value: '2026-06-12' },
          ],
        },
      },
    } as never);

    renderSurface();
    await screen.findByText('Oracle Corporation');

    const events = screen.getByTestId('home-linear-events');
    expect(events).toHaveTextContent('Oracle 公告 2026-06-12 举行业绩电话会');
    expect(events).toHaveTextContent('公司发布云基础设施更新并扩大客户合作');
    expect(events).toHaveTextContent('下一次财报');
    expect(events).not.toHaveTextContent('均线结构修复');
    expect(events).not.toHaveTextContent('数据状态可用');
    expect(events).not.toHaveTextContent('财报跟踪');
    expect(screen.queryByTestId('home-linear-events-empty')).not.toBeInTheDocument();
  });

  it('keeps source diagnostics out of the main flow and shows source gaps in the decision drawer', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    renderSurface();
    await screen.findByText('Oracle Corporation');

    expect(screen.queryByTestId('home-bento-analysis-diagnostics')).not.toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-analysis-diagnostics-toggle')).not.toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-analysis-diagnostics-panel')).not.toBeInTheDocument();
    expect(screen.queryByText('数据状态')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '决策来源' }));

    const expanded = await screen.findByTestId('home-bento-analysis-diagnostics-panel');
    const sourceDetails = screen.getByTestId('home-bento-decision-source-details');
    expect(sourceDetails).toHaveTextContent('来源与缺口');
    expect(sourceDetails).toHaveTextContent('关键缺口');
    expect(expanded).toHaveTextContent('来源');
    expect(expanded).toHaveTextContent('报价 / 基本面');
    expect(expanded).toHaveTextContent('关键数据：可用');
    expect(expanded).toHaveTextContent('基本面数据缺失');
    expect(expanded).toHaveTextContent('新闻数据暂缺');
    expect(expanded).toHaveTextContent('外部数据源暂时降级');
    expect(expanded).toHaveTextContent('待补缺口：新闻数据暂缺、基本面数据缺失');
    expect(expanded).toHaveTextContent('新闻数据暂缺');
    expect(expanded).not.toHaveTextContent('fundamentals.eps');
    expect(expanded).not.toHaveTextContent('optional_news_timeout');
    expect(expanded).not.toHaveTextContent('gnews:news');
    expect(expanded).not.toHaveTextContent('fmp:fundamentals');
    expect(expanded).not.toHaveTextContent(/开发者|Developer|reason codes|原因码/i);
    expect(expanded).not.toHaveTextContent(/api[_-]?key|token|secret|stack trace|sk-/i);
  });

  it('switches decision and strategy tones when the user prefers CN market colors', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    window.localStorage.setItem('dsa-market-color-convention', 'redUpGreenDown');

    renderSurface();

    await screen.findByText('Oracle Corporation');
    expect(screen.getByTestId('home-bento-decision-signal-hero')).toHaveClass('text-white');
    expect(within(screen.getByTestId('home-bento-strategy-metric-上方观察区')).getByText('133.50')).toHaveClass('text-rose-400');
    expect(within(screen.getByTestId('home-bento-strategy-metric-风险失效线')).getByText('117.40')).toHaveClass('text-emerald-400');
  });

  it('lazy-loads the full decision report drawer only after the trigger is opened', async () => {
    vi.resetModules();
    const moduleLoadSpy = vi.fn();

    vi.doMock('../../components/home-bento/FullDecisionReportDrawer', () => {
      moduleLoadSpy();
      return {
        default: ({ isOpen }: { isOpen: boolean }) => (isOpen ? <div data-testid="home-bento-full-report-drawer">lazy drawer mock</div> : null),
      };
    });

    try {
      const { default: LazyHomeSurfacePage } = await import('../HomeSurfacePage');
      useProductSurfaceMock.mockReturnValue({ isGuest: false });

      render(
        <MemoryRouter initialEntries={['/']}>
          <UiPreferencesProvider>
            <UiLanguageProvider>
              <LazyHomeSurfacePage />
            </UiLanguageProvider>
          </UiPreferencesProvider>
        </MemoryRouter>,
      );

      await screen.findByText('Oracle Corporation');
      expect(moduleLoadSpy).not.toHaveBeenCalled();
      expect(screen.queryByTestId('home-bento-full-report-drawer')).not.toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: '完整报告' }));

      await waitFor(() => expect(moduleLoadSpy).toHaveBeenCalledTimes(1));
      expect(await screen.findByTestId('home-bento-full-report-drawer')).toHaveTextContent('lazy drawer mock');
    } finally {
      vi.doUnmock('../../components/home-bento/FullDecisionReportDrawer');
      vi.resetModules();
    }
  });

  it('opens the full decision report drawer with structured report sections and copy support', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    renderSurface();
    await screen.findByText('Oracle Corporation');

    expect(screen.getByRole('button', { name: '完整报告' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '决策来源' })).toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-decision-trace-panel')).not.toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-decision-actions')).not.toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-decision-action-row')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-header-actions')).toHaveTextContent('完整报告');
    expect(screen.getByTestId('home-bento-decision-header-actions')).toHaveTextContent('决策来源');
    expect(screen.getByTestId('home-research-header-strip')).toHaveTextContent('完整报告');
    expect(screen.getByTestId('home-research-header-strip')).toHaveTextContent('决策来源');
    expect(screen.getByTestId('home-research-header-strip')).toHaveTextContent('复制报告');
    expect(screen.getByTestId('home-research-header-strip')).toHaveTextContent('重新分析');
    expect(screen.queryByText('查看完整判断')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '完整报告' }));

    const report = await screen.findByTestId('home-bento-full-report-drawer');
    [
      '投资结论',
      '重要信息速览',
      '风险警报',
      '利好催化',
      '当日行情',
      '数据透视',
      '技术透视',
      '基本面摘要',
      '观察计划',
      '检查清单',
      '来源',
    ].forEach((sectionTitle) => {
      expect(within(report).getAllByText(sectionTitle).length).toBeGreaterThan(0);
    });
    expect(within(report).getByText('WOLFY AI EQUITY RESEARCH')).toBeInTheDocument();
    expect(within(report).getByText('AI 洞察仅供参考，不构成投资建议。')).toBeInTheDocument();
    expect(within(report).getByRole('button', { name: '导出 Markdown' })).toBeInTheDocument();
    expect(within(report).getByRole('button', { name: /导出 PDF|打印\/PDF/ })).toBeInTheDocument();
    expect(within(report).getAllByText('--').length).toBeGreaterThan(0);

    fireEvent.click(within(report).getByRole('button', { name: '复制报告' }));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    expect(String(writeText.mock.calls[0][0])).toContain('投资结论');
  });

  it('builds markdown export with company identity and disclaimer', () => {
    const reportWithDuplicateProviders = {
      ...defaultHistoryReport,
      decisionTrace: {
        ...defaultHistoryReport.decisionTrace,
        dataSources: [
          ...defaultHistoryReport.decisionTrace.dataSources,
          { name: 'news-duplicate', status: 'used', provider: 'Finnhub' },
          { name: 'news-duplicate-2', status: 'used', provider: 'Finnhub' },
        ],
      },
    };
    const markdown = buildInstitutionalReportMarkdown(reportWithDuplicateProviders, {
      companyName: 'Tempus AI',
      ticker: 'TEM',
      generatedAt: '2026-05-04T02:02:00+08:00',
    });

    expect(markdown).toContain('# Wolfy AI Equity Research: Tempus AI (TEM)');
    expect(markdown).toContain('AI 洞察仅供参考，不构成投资建议。');
    expect(markdown).toContain('## 投资结论 / Investment Thesis');
    expect(markdown).toContain('## 重要信息速览 / Important Brief');
    expect(markdown).toContain('## 当日行情 / Market Snapshot');
    expect(markdown).toContain('## 数据透视 / Data Lens');
    expect(markdown).toContain('## 观察计划 / Observation Plan');
    expect(markdown).toContain('## 数据说明 / Data Notes');
    expect(markdown).toContain('- Data status: used / fallback / missing');
    expect(markdown).not.toContain('- Data providers:');
    expect(markdown).not.toContain('Finnhub, Finnhub');
  });

  it('uses ticker-only fallback for placeholder or duplicated company identities', () => {
    expect(getCompanyWithTicker({ companyName: 'Robinhood Markets', symbol: 'HOOD' })).toBe('Robinhood Markets (HOOD)');
    expect(getCompanyWithTicker({ companyName: 'HOOD', symbol: 'HOOD' })).toBe('HOOD');
    expect(getCompanyWithTicker({ stockName: '待确认股票', symbol: 'HOOD' })).toBe('HOOD');
    expect(getCompanyWithTicker({ companyName: 'HOOD (HOOD)', symbol: 'HOOD' })).toBe('HOOD');
    expect(getCompanyWithTicker({ companyName: 'Tempus AI', symbol: 'TEM' })).toBe('Tempus AI (TEM)');
  });

  it('opens the compact decision source drawer without developer details', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    renderSurface();
    await screen.findByText('Oracle Corporation');

    const trigger = screen.getByRole('button', { name: '决策来源' });
    expect(trigger).toBeInTheDocument();
    fireEvent.click(trigger);

    const panel = await screen.findByTestId('home-bento-decision-trace-panel');
    expect(within(panel).getByText('决策字段')).toBeInTheDocument();
    expect(within(panel).getByText('分析状态')).toBeInTheDocument();
    expect(within(panel).getByText('评分')).toBeInTheDocument();
    expect(within(panel).getByText('置信度')).toBeInTheDocument();
    expect(within(panel).getByText('观察区')).toBeInTheDocument();
    expect(within(panel).getByText('上方观察')).toBeInTheDocument();
    expect(within(panel).getByText('风险线')).toBeInTheDocument();
    expect(within(panel).getAllByText('系统依据').length).toBeGreaterThan(0);
    expect(within(panel).getByText('使用的数据')).toBeInTheDocument();
    expect(within(panel).getByText('报价')).toBeInTheDocument();
    expect(within(panel).getByText('备用')).toBeInTheDocument();
    expect(within(panel).getByText('冲突与限制')).toBeInTheDocument();
    expect(within(panel).getByText('分析状态与后续计划存在不一致，已在决策来源中标注。')).toBeInTheDocument();
    expect(within(panel).queryByTestId('home-bento-decision-trace-developer')).not.toBeInTheDocument();
    expect(panel).not.toHaveTextContent(/开发者|Developer|provider|schema_validated|engine_version|endpoint|decision_dashboard_v2|规则 \+ LLM|结构确认|溯源完整|摘要完整/i);
    expect(panel).not.toHaveTextContent('openai');
    expect(panel).not.toHaveTextContent('openai/gpt-4.1-mini');
    expect(panel).not.toHaveTextContent('sk-');
    expect(panel).not.toHaveTextContent('SYSTEM_PROMPT');
    expect(panel).not.toHaveTextContent('raw_prompt');
    expect(panel).not.toHaveTextContent('api_key');
  });

  it('normalizes Home summary fields from decision trace when legacy dashboard fields are missing', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValueOnce({
      total: 1,
      page: 1,
      limit: 20,
      items: [
        { id: 68, queryId: 'q-amd-trace', stockCode: 'AMD', stockName: 'AMD', companyName: 'AMD', createdAt: '2026-05-04T08:00:00Z', generatedAt: '2026-05-04T08:03:00Z', isTest: false },
      ],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValueOnce({
      ...defaultHistoryReport,
      meta: {
        ...defaultHistoryReport.meta,
        queryId: 'q-amd-trace',
        stockCode: 'AMD',
        stockName: 'AMD',
        companyName: 'AMD',
      },
      summary: {
        analysisSummary: 'AMD 完整报告正文仍然保留专业章节。',
        operationAdvice: '',
        trendPrediction: '',
        sentimentScore: undefined,
        sentimentLabel: undefined,
      },
      strategy: {},
      details: {
        standardReport: {
          summaryPanel: {
            stock: 'AMD',
            ticker: 'AMD',
            oneSentence: 'AMD 完整报告正文仍然保留专业章节。',
          },
          reasonLayer: {
            coreReasons: ['AI 加速卡需求仍是主要支撑。'],
          },
          technicalFields: [
            { label: 'Moving Averages', value: 'MA20 above MA60' },
            { label: 'RSI-14', value: '56.8' },
            { label: 'MACD', value: 'Bullish crossover' },
          ],
          fundamentalFields: [
            { label: 'ROE', value: '4.8%' },
            { label: 'Revenue', value: '$25.8B' },
            { label: 'LATEST EPS', value: '$0.92' },
            { label: 'Forward P/E', value: '31.6' },
            { label: 'PEG Ratio', value: '1.42' },
            { label: 'EBITDA Margin', value: '24.1%' },
          ],
        },
      },
      decisionTrace: {
        engineVersion: 'analysis_decision_trace_v1',
        mode: 'rule_scoring_with_llm_explanation',
        endpoint: '/api/v1/analysis/analyze',
        taskId: 'q-amd-trace',
        symbol: 'AMD',
        market: 'US',
        decisionFields: {
          action: { value: 'hold', source: 'rule' },
          score: { value: 68, source: 'rule', scale: '0-100' },
          confidence: { value: '中', source: 'llm' },
          entry: { value: '152.00 - 155.00', source: 'llm' },
          target: { value: '168.40', source: 'llm' },
          stop: { value: '147.80', source: 'llm' },
        },
        dataSources: [
          { name: 'quote', status: 'used', provider: 'Yahoo Finance' },
          { name: 'fundamentals', status: 'partial', provider: 'FMP' },
        ],
        llm: { used: true, provider: 'openai', model: 'openai/gpt-4.1-mini', template: 'decision_dashboard_v2', schemaValidated: true, promptExposed: false },
      },
    } as unknown as typeof defaultHistoryReport);

    renderSurface();

    expect(await screen.findByText('Advanced Micro Devices, Inc.')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-company-header')).toHaveTextContent('AMD');
    expect(document.body.textContent).not.toContain('AMD (AMD) (AMD)');
    expect(screen.queryByText('待确认股票')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-signal-hero')).toHaveTextContent('仅观察');
    expect(screen.getByTestId('home-bento-decision-score-value')).toHaveTextContent('68');
    expect(screen.getByTestId('home-bento-decision-conviction-value')).toHaveTextContent('中');
    expect(screen.getByTestId('home-bento-decision-conviction-value')).not.toHaveTextContent('0%');
    expect(screen.getByTestId('home-bento-card-strategy')).toHaveTextContent('152.00 - 155.00');
    expect(screen.getByTestId('home-bento-card-strategy')).toHaveTextContent('168.40');
    expect(screen.getByTestId('home-bento-card-strategy')).toHaveTextContent('147.80');
    expect(screen.getByTestId('home-bento-card-tech')).toHaveTextContent('56.8');
    expect(screen.getByTestId('home-bento-card-fundamentals')).not.toHaveTextContent('4.8%');
    expect(screen.getByTestId('home-bento-card-fundamentals')).not.toHaveTextContent('$25.8B');

    fireEvent.click(screen.getByRole('button', { name: '完整报告' }));
    const report = await screen.findByTestId('home-bento-full-report-drawer');
    expect(within(report).getAllByText('投资结论').length).toBeGreaterThan(0);
    expect(within(report).getByText('AMD 完整报告正文仍然保留专业章节。')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /关闭|Close/i }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: '决策来源' }));
    const panel = await screen.findByTestId('home-bento-decision-trace-panel');
    expect(within(panel).getByText('分析状态')).toBeInTheDocument();
    expect(within(panel).getByText('报价')).toBeInTheDocument();
    expect(within(panel).getByText('基本面')).toBeInTheDocument();
    expect(within(panel).getByText('部分可用')).toBeInTheDocument();
    expect(within(panel).queryByText('action')).not.toBeInTheDocument();
    expect(within(panel).queryByText('confidence')).not.toBeInTheDocument();
  });

  it('normalizes a HOOD-style live payload without collapsing to placeholder cards', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValueOnce({
      total: 1,
      page: 1,
      limit: 20,
      items: [
        { id: 88, queryId: 'task-hood-live', stockCode: 'HOOD', stockName: '待确认股票', companyName: '待确认股票', createdAt: '2026-05-04T12:04:19Z', generatedAt: '2026-05-04T12:05:11Z', isTest: false },
      ],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValueOnce(normalizeFrontendReportContract({
      meta: {
        id: 88,
        queryId: 'task-hood-live',
        stockCode: 'HOOD',
        stockName: '待确认股票',
        companyName: '待确认股票',
        reportType: 'full',
        createdAt: '2026-05-04T12:05:11Z',
      },
      summary: {
        analysisSummary: '',
        operationAdvice: '',
        trendPrediction: '',
        sentimentScore: 52,
        sentimentLabel: '中性',
      },
      strategy: {},
      details: {
        standard_report: {
          title: {
            stock: '待确认股票 (HOOD)',
            score: 52,
            signal_text: '观望',
            operation_advice: '观望',
            trend_prediction: '看空',
            one_sentence: '短线技术偏弱，但基本面仍有支撑，综合建议以观望为主。',
          },
          summary_panel: {
            stock: '待确认股票 (HOOD)',
            ticker: 'HOOD',
            score: 52,
            current_price: '73.67',
            operation_advice: '观望',
            trend_prediction: '看空',
            one_sentence: '短线技术偏弱，但基本面仍有支撑，综合建议以观望为主。',
          },
          decision_panel: {
            confidence: '低',
          },
          technical_fields: [
            { label: 'Moving Averages', value: 'MA20 below MA60' },
            { label: 'RSI-14', value: '43.5' },
            { label: 'MACD', value: 'Below zero' },
          ],
          fundamental_fields: [
            { label: 'ROE', value: '4.17%' },
            { label: 'Revenue Growth', value: '15.10%' },
          ],
          battle_plan_compact: {
            cards: [
              { label: '理想买入点', value: '74.23-75.18（回踩支撑确认）' },
              { label: '目标位', value: '75.27（更强压力 / 高位目标）' },
              { label: '止损位', value: '73.10（趋势破位止损位）' },
            ],
          },
        },
        analysis_result: {
          action: '观望',
          score: 52,
          confidence: '中',
          entry_price: '74.23-75.18（回踩支撑确认）',
          stop_loss: '73.10（趋势破位止损位）',
          take_profit: '75.27（更强压力 / 高位目标）',
          summary: 'HOOD 当前处于弱势空头趋势，建议保持观望。',
        },
      } as unknown as typeof defaultHistoryReport.details,
      decision_trace: {
        symbol: 'HOOD',
        market: 'US',
        decision_fields: {
          action: { value: 'hold', source: 'rule' },
          score: { value: 52, source: 'rule', scale: '0-100' },
          confidence: { value: '低', source: 'llm' },
        },
        data_sources: [
          { name: 'quote', status: 'used', provider: 'alpaca' },
          { name: 'fundamentals', status: 'partial', provider: 'fmp' },
        ],
        llm: {
          used: true,
          provider: 'gemini',
          model: 'gemini/gemini-2.5-flash',
          template: 'decision_dashboard_v2',
          schema_validated: false,
          prompt_exposed: false,
        },
      },
    } as never));

    renderSurface();

    await waitFor(() => expect(screen.getByTestId('home-bento-decision-score-value')).toHaveTextContent('52'));
    expect(screen.getByTestId('home-bento-decision-signal-hero')).toHaveTextContent('仅观察');
    expect(screen.getByTestId('home-bento-decision-conviction-value')).toHaveTextContent('低');
    expect(screen.getByTestId('home-bento-decision-conviction-value')).not.toHaveTextContent('0%');
    expect(screen.getByTestId('home-bento-card-strategy')).toHaveTextContent('74.23-75.18');
    expect(screen.getByTestId('home-bento-card-strategy')).toHaveTextContent('75.27');
    expect(screen.getByTestId('home-bento-card-strategy')).toHaveTextContent('73.10');
    expect(screen.getByTestId('home-bento-card-tech')).toHaveTextContent('43.5');
    expect(screen.getByTestId('home-bento-card-fundamentals')).not.toHaveTextContent('4.17%');

    fireEvent.click(screen.getByRole('button', { name: '完整报告' }));
    const report = await screen.findByTestId('home-bento-full-report-drawer');
    expect(within(report).getAllByText('投资结论').length).toBeGreaterThan(0);
    expect(within(report).getByText('短线技术偏弱，但基本面仍有支撑，综合建议以观望为主。')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /关闭|Close/i }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: '决策来源' }));
    const panel = await screen.findByTestId('home-bento-decision-trace-panel');
    expect(within(panel).queryByTestId('home-bento-decision-trace-developer')).not.toBeInTheDocument();
    const sourceDetails = screen.getByTestId('home-bento-decision-source-details');
    expect(sourceDetails).toHaveTextContent('来源与缺口');
    expect(sourceDetails).toHaveTextContent('报价 / 基本面');
    expect(sourceDetails).not.toHaveTextContent('结构未确认');
    expect(sourceDetails).not.toHaveTextContent('规则 + LLM');
    expect(within(panel).getByText('报价')).toBeInTheDocument();
    expect(within(panel).getByText('部分可用')).toBeInTheDocument();
  });

  it('loads the dev/test decision trace fixture without submitting analysis', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValueOnce({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    renderSurface('/zh?fixture=analysis-trace');

    expect(await screen.findByText('Tempus AI')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-company-header')).toHaveTextContent('Tempus AI');
    expect(screen.getByTestId('home-bento-decision-ticker')).toHaveTextContent('TEM');
    expect(document.body.textContent).not.toContain('TEM (TEM) (TEM)');
    expect((await screen.findAllByText(/Fixture result only; not investment advice/i)).length).toBeGreaterThan(0);
    expect(screen.getByTestId('home-bento-card-decision')).toHaveTextContent('Fixture result only; not investment advice.');
    expect(screen.queryByTestId('home-bento-decision-actions')).not.toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-decision-action-row')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-header-actions')).toHaveTextContent('完整报告');
    expect(screen.getByTestId('home-bento-decision-header-actions')).toHaveTextContent('决策来源');
    expect(screen.getByTestId('home-research-header-strip')).toHaveTextContent('完整报告');
    expect(screen.getByTestId('home-research-header-strip')).toHaveTextContent('决策来源');
    expect(screen.getByTestId('home-research-header-strip')).toHaveTextContent('复制报告');
    expect(screen.getByTestId('home-research-header-strip')).toHaveTextContent('重新分析');
    expect(screen.queryByText('查看完整判断')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-strategy')).toHaveTextContent('128.5');
    expect(screen.getByTestId('home-bento-card-strategy')).toHaveTextContent('136.00-138.00');

    fireEvent.click(screen.getByRole('button', { name: '决策来源' }));

    const panel = await screen.findByTestId('home-bento-decision-trace-panel');
    expect(within(panel).getByText('决策字段')).toBeInTheDocument();
    expect(within(panel).getByText('wait_pullback')).toBeInTheDocument();
    expect(within(panel).getAllByText('系统依据').length).toBeGreaterThan(0);
    expect(within(panel).getByText('使用的数据')).toBeInTheDocument();
    expect(within(panel).getByText('可用')).toBeInTheDocument();
    expect(within(panel).getByText('缺失')).toBeInTheDocument();
    expect(within(panel).getByText('未知')).toBeInTheDocument();
    expect(within(panel).queryByTestId('home-bento-decision-trace-developer')).not.toBeInTheDocument();
    expect(panel).not.toHaveTextContent('fixture-provider');
    expect(panel).not.toHaveTextContent('fixture-model');
    expect(panel).not.toHaveTextContent('stock_analysis_trace_fixture_v1');
    expect(within(panel).getByText('分析状态与后续计划存在不一致，已在决策来源中标注。')).toBeInTheDocument();
    expect(within(panel).getByText('基本面数据缺失')).toBeInTheDocument();
    expect(panel).not.toHaveTextContent('当前分析未包含决策溯源');
    expect(document.body.textContent).not.toContain('raw_prompt');
    expect(document.body.textContent).not.toContain('SYSTEM_PROMPT');
    expect(document.body.textContent).not.toContain('api_key');
    expect(document.body.textContent).not.toContain('sk-');
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
  });

  it('reads decision trace from persisted history detail raw payloads', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getDetail).mockResolvedValueOnce(normalizeFrontendReportContract({
      meta: defaultHistoryReport.meta,
      summary: defaultHistoryReport.summary,
      strategy: defaultHistoryReport.strategy,
      details: {
        standard_report: defaultHistoryReport.details.standardReport,
        analysis_result: {
          action: '持有',
          score: 78,
          confidence: '高',
          entry_price: '121.80 - 124.60',
          stop_loss: '117.40',
          take_profit: '133.50',
          summary: 'Cloud backlog keeps the medium-term floor intact.',
        },
        raw_result: {
          persisted_report: {
            decision_trace: {
              engine_version: 'analysis_decision_trace_v1',
              symbol: 'ORCL',
              market: 'US',
              decision_fields: {
                action: { value: 'hold', source: 'rule' },
                score: { value: 78, source: 'rule', scale: '0-100' },
                confidence: { value: '高', source: 'llm' },
              },
              data_sources: [
                { name: 'quote', status: 'used', provider: 'Yahoo Finance' },
                { name: 'fundamental', status: 'partial', provider: 'FMP' },
              ],
              llm: {
                used: true,
                provider: 'openai',
                model: 'openai/gpt-4.1-mini',
                template: 'decision_dashboard_v2',
                schema_validated: false,
                prompt_exposed: false,
              },
            },
          },
        },
      },
    } as never));

    renderSurface();
    await screen.findByText('Oracle Corporation');

    expect(screen.queryByTestId('home-bento-analysis-diagnostics')).not.toBeInTheDocument();
    expect(screen.queryByText('未包含决策溯源')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-conviction-value')).not.toHaveTextContent('0%');

    fireEvent.click(screen.getByRole('button', { name: '决策来源' }));
    const panel = await screen.findByTestId('home-bento-decision-trace-panel');
    expect(panel).not.toHaveTextContent('当前分析未包含决策溯源');
    expect(screen.getByTestId('home-bento-decision-source-details')).toHaveTextContent('报价 / 基本面');
    expect(within(panel).getByText('报价')).toBeInTheDocument();
    expect(within(panel).queryByTestId('home-bento-decision-trace-developer')).not.toBeInTheDocument();
  });

  it('opens the decision trace fixture drawer in a narrow viewport', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValueOnce({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    window.innerWidth = 390;
    window.innerHeight = 844;
    window.dispatchEvent(new Event('resize'));

    renderSurface('/zh?fixture=analysis-trace');

    fireEvent.click(await screen.findByRole('button', { name: '决策来源' }));
    const panel = await screen.findByTestId('home-bento-decision-trace-panel');
    expect(panel).toHaveClass('min-w-0');
    expect(within(panel).getByText('决策字段')).toBeInTheDocument();
    expect(within(panel).getByText('冲突与限制')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toHaveTextContent('决策来源');

    fireEvent.click(screen.getByRole('button', { name: /关闭|Close/i }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('can auto-open the dev/test decision trace fixture drawer for browser smoke', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValueOnce({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    renderSurface('/zh?fixture=analysis-trace&trace=open');

    const panel = await screen.findByTestId('home-bento-decision-trace-panel');
    expect(screen.getByRole('dialog')).toHaveTextContent('决策来源');
    expect(within(panel).queryByTestId('home-bento-decision-trace-developer')).not.toBeInTheDocument();
    expect(panel).not.toHaveTextContent('fixture-provider');
    expect(within(panel).getByText('AI 洞察仅供参考，不构成投资建议。')).toBeInTheDocument();
  });

  it('can auto-open the dev/test full report fixture drawer for browser smoke', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValueOnce({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    renderSurface('/zh?fixture=analysis-trace&report=open');

    const report = await screen.findByTestId('home-bento-full-report-drawer');
    expect(screen.getByRole('dialog')).toHaveTextContent('完整报告');
    expect(within(report).getAllByText('投资结论').length).toBeGreaterThan(0);
    expect(within(report).getByText('Tempus AI (TEM)')).toBeInTheDocument();
    expect(within(report).getByText('AI 洞察仅供参考，不构成投资建议。')).toBeInTheDocument();
  });

  it('renders history titles with company plus ticker without duplicate ticker strings', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValueOnce({
      total: 4,
      page: 1,
      limit: 20,
      items: [
        { id: 11, queryId: 'tem-1', stockCode: 'TEM', stockName: 'Tempus AI', companyName: 'Tempus AI', createdAt: '2026-05-04T02:02:00Z', generatedAt: '2026-05-04T02:02:00Z', isTest: false },
        { id: 12, queryId: 'tem-2', stockCode: 'TEM', stockName: 'TEM', createdAt: '2026-05-04T02:00:00Z', generatedAt: '2026-05-04T02:00:00Z', isTest: false },
        { id: 13, queryId: 'tem-3', stockCode: 'TEM', stockName: 'Tempus AI (TEM)', createdAt: '2026-05-04T01:58:00Z', generatedAt: '2026-05-04T01:58:00Z', isTest: false },
        { id: 14, queryId: 'tem-4', stockCode: 'TEM', stockName: 'TEM (TEM) (TEM)', createdAt: '2026-05-04T01:55:00Z', generatedAt: '2026-05-04T01:55:00Z', isTest: false },
      ],
    });

    renderSurface();
    fireEvent.click(await screen.findByTestId('home-bento-history-drawer-trigger'));
    const drawer = await screen.findByTestId('home-bento-history-drawer');

    expect(within(drawer).getAllByText('Tempus AI (TEM)').length).toBeGreaterThanOrEqual(2);
    expect(within(drawer).getByTestId('home-bento-history-item-12')).toHaveTextContent(/^TEM最近分析/);
    expect(drawer).not.toHaveTextContent('TEM (TEM) (TEM)');
  });

  it('shows a safe unavailable trace state for old analysis reports without trace metadata', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getDetail).mockResolvedValueOnce({
      ...defaultHistoryReport,
      decisionTrace: undefined,
    });

    renderSurface();
    await screen.findByText('Oracle Corporation');
    fireEvent.click(screen.getByRole('button', { name: '决策来源' }));

    expect(await screen.findByTestId('home-bento-decision-trace-panel')).toHaveTextContent('当前分析未包含决策溯源');
    expect(await screen.findByTestId('home-bento-analysis-diagnostics-panel')).toHaveTextContent('来源');
    expect(screen.getByTestId('home-bento-decision-source-details')).toHaveTextContent('结构：待复核');
    expect(screen.queryByTestId('home-bento-decision-trace-developer')).not.toBeInTheDocument();
  });

  it('shows compact report quality chips for complete, usable, legacy, and failed history records', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValueOnce({
      total: 4,
      page: 1,
      limit: 20,
      items: [
        {
          id: 41,
          queryId: 'q41',
          stockCode: 'ORCL',
          stockName: 'Oracle',
          companyName: 'Oracle',
          createdAt: '2026-05-04T08:00:00Z',
          generatedAt: '2026-05-04T08:03:00Z',
          isTest: false,
          reportQuality: {
            level: 'complete',
            schemaStatus: 'ok',
            traceStatus: 'present',
            summaryStatus: 'complete',
            reportStatus: 'complete',
            hasDecisionTrace: true,
            hasStandardReport: true,
            hasAnalysisResult: true,
            hasAction: true,
            hasScore: true,
            hasConfidence: true,
            hasTradingPlan: true,
            missingFields: [],
            userLabel: '完整',
            userHint: '结构化摘要与决策溯源完整。',
          },
        },
        {
          id: 42,
          queryId: 'q42',
          stockCode: 'AMD',
          stockName: 'AMD',
          companyName: 'AMD',
          createdAt: '2026-05-04T07:00:00Z',
          generatedAt: '2026-05-04T07:03:00Z',
          isTest: false,
          reportQuality: {
            level: 'usable',
            schemaStatus: 'unconfirmed',
            traceStatus: 'missing',
            summaryStatus: 'partial',
            reportStatus: 'complete',
            hasDecisionTrace: false,
            hasStandardReport: true,
            hasAnalysisResult: true,
            hasAction: true,
            hasScore: true,
            hasConfidence: false,
            hasTradingPlan: true,
            missingFields: ['决策溯源', '置信度'],
            userLabel: '可用',
            userHint: '报告内容可用，但部分溯源或结构字段缺失。',
          },
        },
        {
          id: 43,
          queryId: 'q43',
          stockCode: 'IBM',
          stockName: 'IBM',
          companyName: 'IBM',
          createdAt: '2026-05-04T06:00:00Z',
          generatedAt: '2026-05-04T06:03:00Z',
          isTest: false,
          reportQuality: {
            level: 'legacy',
            schemaStatus: 'unknown',
            traceStatus: 'missing',
            summaryStatus: 'partial',
            reportStatus: 'partial',
            hasDecisionTrace: false,
            hasStandardReport: false,
            hasAnalysisResult: false,
            hasAction: true,
            hasScore: false,
            hasConfidence: false,
            hasTradingPlan: false,
            missingFields: ['决策溯源', '标准报告'],
            userLabel: '旧版记录',
            userHint: '旧版历史记录可阅读，但结构化字段不完整。',
          },
        },
        {
          id: 44,
          queryId: 'q44',
          stockCode: 'SNOW',
          stockName: 'Snowflake',
          companyName: 'Snowflake',
          createdAt: '2026-05-04T05:00:00Z',
          generatedAt: '2026-05-04T05:03:00Z',
          isTest: false,
          reportQuality: {
            level: 'failed',
            schemaStatus: 'missing',
            traceStatus: 'missing',
            summaryStatus: 'missing',
            reportStatus: 'missing',
            hasDecisionTrace: false,
            hasStandardReport: false,
            hasAnalysisResult: true,
            hasAction: false,
            hasScore: false,
            hasConfidence: false,
            hasTradingPlan: false,
            missingFields: ['决策溯源', '标准报告', '摘要'],
            userLabel: '分析失败',
            userHint: '本次分析未完整生成，可重新分析。',
          },
        },
      ],
    });

    renderSurface();
    fireEvent.click(await screen.findByTestId('home-bento-history-drawer-trigger'));

    const complete = await screen.findByTestId('home-bento-history-quality-41');
    expect(within(complete).getByText('数据：完整')).toBeInTheDocument();
    expect(within(complete).getByText('来源：已附')).toBeInTheDocument();
    expect(within(complete).getByText('报告：完整')).toBeInTheDocument();
    expect(within(complete).getByText('结构：完整')).toBeInTheDocument();
    expect(complete).not.toHaveTextContent('溯源完整');
    expect(complete).not.toHaveTextContent('结构确认');
    const usable = screen.getByTestId('home-bento-history-quality-42');
    expect(within(usable).getByText('数据：可用')).toBeInTheDocument();
    expect(within(usable).getByText('来源：缺失')).toBeInTheDocument();
    expect(within(usable).getByText('结构：待复核')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-history-quality-43')).toHaveTextContent('数据：旧版');
    expect(screen.getByTestId('home-bento-history-quality-44')).toHaveTextContent('数据：失败');
  });

  it('keeps incomplete reports readable and offers explicit re-analysis without fabricating confidence', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getDetail).mockResolvedValueOnce({
      ...defaultHistoryReport,
      decisionTrace: undefined,
      summary: {
        ...defaultHistoryReport.summary,
        sentimentScore: 61,
      },
      details: {
        ...defaultHistoryReport.details,
        standardReport: {
          ...defaultHistoryReport.details.standardReport,
          decisionPanel: {
            ...defaultHistoryReport.details.standardReport.decisionPanel,
            confidence: undefined,
          },
        },
      },
    });

    renderSurface();

    await screen.findByText('Oracle Corporation');
    fireEvent.click(screen.getByRole('button', { name: '决策来源' }));
    const diagnosticsPanel = await screen.findByTestId('home-bento-analysis-diagnostics-panel');
    expect(diagnosticsPanel).toHaveTextContent('关键数据：可用');
    expect(screen.getByTestId('home-bento-decision-source-details')).toHaveTextContent('结构：待复核');
    expect(diagnosticsPanel).not.toHaveTextContent('结构未确认');
    expect(screen.getByTestId('home-bento-decision-conviction-value')).toHaveTextContent('待补充');
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重新分析' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: /关闭|Close/i }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: '完整报告' }));
    const report = await screen.findByTestId('home-bento-full-report-drawer');
    expect(within(report).getAllByText('投资结论').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: /关闭|Close/i }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: '决策来源' }));
    const panel = await screen.findByTestId('home-bento-decision-trace-panel');
    expect(panel).toHaveTextContent('当前分析未包含决策溯源');
    expect(within(panel).queryByTestId('home-bento-decision-trace-developer')).not.toBeInTheDocument();
    expect(panel).toHaveTextContent('数据不足');
  });

  it('disables safe re-analysis when the selected report has no symbol', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValueOnce({
      total: 1,
      page: 1,
      limit: 20,
      items: [
        { id: 55, queryId: 'q55', stockCode: '', stockName: '', companyName: '', createdAt: '2026-05-04T04:00:00Z', generatedAt: '2026-05-04T04:03:00Z', isTest: false },
      ],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValueOnce({
      ...defaultHistoryReport,
      meta: {
        ...defaultHistoryReport.meta,
        id: 55,
        queryId: 'q55',
        stockCode: '',
        stockName: '',
        companyName: '',
      },
      decisionTrace: undefined,
    });

    renderSurface();

    const disabledRerun = await screen.findByRole('button', { name: '缺少股票代码' });
    expect(disabledRerun).toBeDisabled();
    expect(disabledRerun).toHaveAttribute('title', '缺少股票代码');
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
  });

  it('keeps the Linear-style Home shell when there is no non-test history', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValueOnce({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    renderSurface();

    const researchConsole = await screen.findByTestId('home-research-console');
    const board = screen.getByTestId('home-research-board');
    const rail = screen.getByTestId('home-research-context-rail');
    const commandBar = screen.getByTestId('home-research-command-bar');
    expect(screen.getByTestId('home-bento-omnibar')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-history-drawer-trigger')).toBeInTheDocument();
    expect(researchConsole).toHaveAttribute('data-linear-primitive', 'research-console-shell');
    expect(commandBar).toHaveAttribute('data-layout-zone', 'CommandBar');
    expect(screen.getByTestId('home-research-header-strip').closest('[data-layout-zone="HeaderStrip"]')).toBeInTheDocument();
    expect(screen.getByTestId('home-research-primary-workspace').closest('[data-layout-zone="PrimaryWorkRegion"]')).toBeInTheDocument();
    expect(screen.getByTestId('home-research-secondary-deck')).toHaveAttribute('data-layout-zone', 'SecondaryDeck');
    expect(rail).toHaveAttribute('data-layout-zone', 'ContextRail');
    expect(rail).toHaveAttribute('data-linear-primitive', 'context-rail');
    expect(board.contains(rail)).toBe(true);
    expect(board.contains(screen.getByTestId('home-research-secondary-deck'))).toBe(true);
    expect(researchConsole.contains(board)).toBe(true);
    expect(researchConsole.contains(rail)).toBe(true);
    expect(researchConsole).toHaveAttribute('data-visual-tier', 'dominant');
    expect(researchConsole).toHaveAttribute('data-surface-system', 'reflect-linear-console');
    expect(researchConsole).toHaveClass('rounded-none', 'border-transparent', 'bg-transparent', 'shadow-none');
    expect(board).toHaveClass('relative', 'z-10', 'overflow-visible');
    expect(rail).toHaveClass('home-research-context-rail', 'bg-transparent', 'divide-y-0');
    expect(screen.queryByTestId('home-bento-zero-state')).not.toBeInTheDocument();
    expect(screen.queryByText('Ghost dashboard 承接中')).not.toBeInTheDocument();
    expect(screen.queryByText('待分析')).not.toBeInTheDocument();
    expect(screen.queryByText('等待输入')).not.toBeInTheDocument();
    expect(screen.queryByText('等待分析')).not.toBeInTheDocument();
    expect(screen.queryByText('输入股票代码后将在此原位刷新 AI 判断。')).not.toBeInTheDocument();
    expect(screen.queryByText('首页卡片会始终保留在这里，未分析字段先保持中性占位，等待你提交股票代码或打开完成历史。')).not.toBeInTheDocument();
    expect(screen.getAllByText('价格触发').length).toBeGreaterThan(0);
    expect(screen.getAllByText('-').length).toBeGreaterThan(0);
  });

  it('keeps analysis loading inside the compact Linear workspace', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    const deferred = createDeferred<{ taskId: string; status: 'pending'; message: string }>();
    vi.mocked(analysisApi.analyzeAsync).mockReturnValueOnce(deferred.promise);

    renderSurface();

    await screen.findByTestId('home-research-console');
    const input = screen.getByTestId('home-bento-omnibar-input');
    fireEvent.change(input, { target: { value: 'NVDA' } });
    fireEvent.submit(screen.getByTestId('home-bento-omnibar'));

    expect(await screen.findByTestId('home-bento-inplace-loading-decision')).toBeInTheDocument();
    expect(screen.getByTestId('home-research-console')).toHaveAttribute('data-linear-primitive', 'research-console-shell');
    expect(screen.getByTestId('home-research-board')).toHaveAttribute('data-linear-primitive', 'console-board');
    expect(screen.getByTestId('home-research-command-bar')).toHaveAttribute('data-layout-zone', 'CommandBar');
    expect(screen.getByTestId('home-research-context-rail')).toHaveAttribute('data-layout-zone', 'ContextRail');
    expect(screen.getByTestId('home-research-rail-loading-stack')).toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-secondary-grid')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-decision')).toHaveClass('min-w-0');
    expect(screen.getByTestId('home-bento-card-strategy')).toHaveClass('min-w-0');
    expect(screen.queryByRole('img', { name: 'WolfyStock analyzing' })).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-inplace-loading-tech')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-inplace-loading-fundamentals')).toBeInTheDocument();
    expect(screen.getByText('分析中')).toBeInTheDocument();
    const timeline = screen.getByTestId('home-bento-progress-timeline');
    expect(timeline).toHaveTextContent('市场识别');
    expect(timeline).toHaveTextContent('行情/技术面');
    expect(timeline).toHaveTextContent('基本面');
    expect(timeline).toHaveTextContent('新闻/风险');
    expect(timeline).toHaveTextContent('AI 综合');
    expect(timeline).toHaveTextContent('报告生成');
    expect(screen.queryByTestId('home-bento-progress-summary')).not.toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-runtime-panel')).not.toBeInTheDocument();
    expect(screen.queryByText('LLM')).not.toBeInTheDocument();
    expect(screen.queryByText('Technical')).not.toBeInTheDocument();

    await act(async () => {
      deferred.resolve({ taskId: 'task-1', status: 'pending', message: 'submitted' });
      await deferred.promise;
    });
  });

  it('renders localized English copy for the signed-in dashboard', async () => {
    window.localStorage.setItem('dsa-ui-language', 'en');
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    renderSurface();
    expect(screen.queryByText('WolfyStock Command Center')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'History' })).toBeInTheDocument();
    expect(await screen.findByText('Research Framework')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-omnibar-input')).toHaveAttribute('placeholder', 'Enter a ticker to wake the AI (for example ORCL)...');
    expect(screen.getByText('Technical Structure')).toBeInTheDocument();
    expect(screen.getByText('Data Quality & Notes')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /scanner/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /portfolio/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /backtest/i })).not.toBeInTheDocument();
    expect(screen.queryByText('Lock the range first, then decide the pace.')).not.toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-decision-chart-workspace')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-signal-hero')).toHaveTextContent('Observe');
    expect(screen.getByText('Stance')).toBeInTheDocument();
    expect(screen.getByText('Score')).toBeInTheDocument();
    expect(screen.queryByText('DIRECTION')).not.toBeInTheDocument();
    expect(screen.getAllByText('Thesis').length).toBeGreaterThan(0);
    expect(screen.getAllByText('MA ALIGNMENT').length).toBeGreaterThan(0);
    expect(screen.getAllByText('2nd Expansion').length).toBeGreaterThan(0);
    expect(screen.getAllByText('RSI-14').length).toBeGreaterThan(0);
    expect(screen.getAllByText('VOLUME DYNAMICS').length).toBeGreaterThan(0);
    expect(screen.queryByText('EBITDA MARGIN')).not.toBeInTheDocument();
    expect(screen.queryByText('LATEST EPS')).not.toBeInTheDocument();
    expect(screen.queryByText('FORWARD PE')).not.toBeInTheDocument();
    expect(screen.queryByText('PEG RATIO')).not.toBeInTheDocument();
    expect(screen.queryByText('AI SIGNAL DIRECTION')).not.toBeInTheDocument();
    expect(screen.queryByText('Latest Report Context')).not.toBeInTheDocument();
  });

  it('neutralizes stale failed reports when the dashboard is viewed in English', async () => {
    window.localStorage.setItem('dsa-ui-language', 'en');
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getDetail).mockImplementation((recordId) => {
      if (recordId !== 3) {
        return Promise.resolve(defaultHistoryReport);
      }

      return Promise.resolve({
        ...defaultHistoryReport,
        meta: {
          ...defaultHistoryReport.meta,
          id: 3,
          queryId: 'q3',
          stockCode: 'ORCL',
          stockName: '待确认股票',
        },
        summary: {
          ...defaultHistoryReport.summary,
          analysisSummary: '分析过程出错: All LLM models failed (tried 2 model(s)). Last error: litellm.RateLimitError: litellm.RateLimitError',
          operationAdvice: '理想做法是回踩支撑簇小仓试错，若站回 MA5/MA10 再做第二笔。',
          trendPrediction: '短线技术偏强，均线结构偏强、价格位于 MA20 上方、价格位于 MA60 上方。',
          sentimentLabel: '乐观',
          sentimentScore: 60,
        },
        strategy: {
          idealBuy: '172.92-178.04（回踩支撑确认）',
          stopLoss: '164.39（技术失效位）',
          takeProfit: '180.45-189.17（目标区间）',
        },
        details: {
          standardReport: {
            ...defaultHistoryReport.details.standardReport,
            summaryPanel: {
              ...defaultHistoryReport.details.standardReport.summaryPanel,
              stock: '待确认股票',
            },
            decisionContext: {
              shortTermView: '短线技术偏强，均线结构偏强、价格位于 MA20 上方、价格位于 MA60 上方。',
            },
            reasonLayer: {
              coreReasons: ['技术面与基本面相互印证，综合建议以持有为主。'],
            },
            decisionPanel: {
              ...defaultHistoryReport.details.standardReport.decisionPanel,
              idealEntry: '172.92-178.04（回踩支撑确认）',
              target: '180.45-189.17（目标区间）',
              stopLoss: '164.39（技术失效位）',
              buildStrategy: '理想做法是回踩支撑簇小仓试错，若站回 MA5/MA10 再做第二笔。',
            },
            technicalFields: [
              { label: 'MA5', value: '178.19' },
              { label: 'MA10', value: '175.48' },
              { label: 'MA20', value: '159.63' },
              { label: 'MA60', value: '154.05' },
              { label: 'RSI14', value: '67.97' },
            ],
            fundamentalFields: [
              { label: '总市值(最新值)', value: '4983.61亿' },
              { label: '流通市值(最新值)', value: 'NA（字段待接入）' },
              { label: '总股本(最新值)', value: '28.76亿' },
              { label: '流通股(最新值)', value: '17.09亿' },
              { label: '市盈率(TTM)', value: '31.17' },
              { label: '预期市盈率(一致预期)', value: '21.58' },
            ],
          },
        },
      });
    });

    renderSurface();
    fireEvent.click(await screen.findByTestId('home-bento-history-drawer-trigger'));
    fireEvent.click(await screen.findByTestId('home-bento-history-item-3'));

    await waitFor(() => expect(screen.queryByTestId('home-bento-loading-decision-card')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId('home-bento-decision-ticker')).toHaveTextContent('ORCL'));
    expect(screen.getByTestId('home-bento-card-decision')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-strategy')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-tech')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-fundamentals')).toBeInTheDocument();
    expect(screen.getAllByText('Pending data').length).toBeGreaterThan(0);
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
    expect(screen.queryByText('N/A')).not.toBeInTheDocument();
    expect(screen.queryByText('Bullish')).not.toBeInTheDocument();
    expect(screen.queryByText('172.92-178.04 (Pullback support confirmed)')).not.toBeInTheDocument();
    expect(screen.queryByText('180.45-189.17 (Target zone)')).not.toBeInTheDocument();
    expect(screen.queryByText('164.39 (Technical invalidation)')).not.toBeInTheDocument();
    expect(screen.queryByText('Market Cap (Latest)')).not.toBeInTheDocument();
    expect(screen.queryByText('N/A (field pending)')).not.toBeInTheDocument();
    expect(screen.queryByText('回踩支撑确认')).not.toBeInTheDocument();
    expect(screen.queryByText('总市值(最新值)')).not.toBeInTheDocument();
    expect(screen.queryByText('待确认股票')).not.toBeInTheDocument();
  });

  it('opens and closes the progressive-disclosure drawer from the strategy card', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    renderSurface();
    expect(document.body.style.overflow).toBe('');
    fireEvent.click(await screen.findByTestId('home-bento-drawer-trigger-strategy'));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-drawer')).toBeInTheDocument();
    expect(screen.getByText('观察约束')).toBeInTheDocument();
    expect(screen.getAllByText('观察区间').length).toBeGreaterThan(0);
    expect(screen.getAllByText('跟踪节奏').length).toBeGreaterThan(0);
    fireEvent.keyDown(document, { key: 'Escape' });
    await new Promise((resolve) => window.setTimeout(resolve, 220));
    expect(await screen.findByTestId('home-bento-dashboard')).toBeInTheDocument();
  });

  it('loads the clicked history record from the database instead of re-analyzing', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    const deferred = createDeferred<typeof defaultHistoryReport>();
    vi.mocked(historyApi.getDetail).mockImplementation((recordId) => (
      recordId === 2 ? deferred.promise : Promise.resolve(defaultHistoryReport)
    ));
    renderSurface();
    fireEvent.click(await screen.findByTestId('home-bento-history-drawer-trigger'));
    expect(await screen.findByTestId('home-bento-history-drawer')).toBeInTheDocument();
    fireEvent.click(await screen.findByTestId('home-bento-history-item-2'));

    expect(await screen.findByTestId('home-bento-card-decision')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-strategy')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-tech')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-fundamentals')).toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-loading-decision-card')).not.toBeInTheDocument();
    expect(historyApi.getDetail).toHaveBeenCalledWith(2);
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();

    deferred.resolve({
      ...defaultHistoryReport,
      meta: {
        ...defaultHistoryReport.meta,
        id: 2,
        queryId: 'q2',
        stockCode: 'TSLA',
        stockName: 'Tesla',
      },
    });
  });

  it('does not neutralize a successful saved report just because fallback diagnostics mention failed model attempts', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getDetail).mockResolvedValue({
      ...defaultHistoryReport,
      meta: {
        ...defaultHistoryReport.meta,
        id: 6,
        queryId: 'q6',
        stockCode: 'BMNR',
        stockName: 'Bitmine Immersion Technologies（BMNR）',
      },
      summary: {
        ...defaultHistoryReport.summary,
        analysisSummary: 'The saved report succeeded after a fallback model attempt.',
        operationAdvice: 'Reduce into strength, then reassess on support.',
        trendPrediction: 'Volatile but still recoverable.',
        sentimentScore: 36,
        sentimentLabel: 'Bearish',
      },
      details: {
        rawResult: {
          dashboard: {
            dataPerspective: {
              trendStatus: {
                maAlignment: 'MA5 下穿 MA10，均线缠绕。',
              },
              volumeAnalysis: {
                volumeMeaning: '缩量，追价意愿偏弱。',
              },
            },
            structuredAnalysis: {
              technicals: {
                macd: 0.2934,
                rsi14: 49.83,
              },
            },
          },
          runtimeExecution: {
            ai: {
              attemptChain: [
                { model: 'deepseek/deepseek-v4-pro', status: 'success' },
                {
                  model: 'gemini/gemini-2.5-flash',
                  status: 'failed',
                  reason: 'litellm.ServiceUnavailableError: GeminiException - high demand',
                },
              ],
            },
          },
        },
        contextSnapshot: {
          enhancedContext: {
            dataQuality: {
              providerNotes: {
                diagnostics: {
                  aiAttemptChain: [
                    { model: 'deepseek/deepseek-v4-pro', status: 'success' },
                    {
                      model: 'gemini/gemini-2.5-flash',
                      status: 'failed',
                      message: 'AI model gemini/gemini-2.5-flash failed: high demand',
                    },
                  ],
                },
              },
            },
          },
        },
        standardReport: {
          ...defaultHistoryReport.details.standardReport,
          summaryPanel: {
            ...defaultHistoryReport.details.standardReport.summaryPanel,
            stock: 'Bitmine Immersion Technologies（BMNR）',
            ticker: 'BMNR',
            oneSentence: 'The saved report succeeded after a fallback model attempt.',
          },
          decisionContext: {
            shortTermView: 'Volatile but still recoverable.',
          },
          decisionPanel: {
            ...defaultHistoryReport.details.standardReport.decisionPanel,
            idealEntry: '20.80',
            target: '24.00',
            stopLoss: '19.00',
            buildStrategy: 'Reduce into strength, then reassess on support.',
          },
          reasonLayer: {
            coreReasons: ['综合建议为减仓，结合技术、基本面与情绪继续跟踪。'],
          },
          technicalFields: [
            { label: '多头/空头排列', value: 'MA5 下穿 MA10，均线缠绕。' },
            { label: 'RSI14', value: '49.83' },
            { label: '量价判断', value: '缩量，追价意愿偏弱。' },
          ],
          fundamentalFields: [
            { label: 'ROE', value: '-97.33%' },
            { label: 'Forward PE', value: '22.85x' },
          ],
        },
      },
    });

    renderSurface();

    await waitFor(() => {
      expect(screen.getByTestId('home-bento-decision-insight-copy').textContent).toContain('The saved report succeeded after a fallback model attempt.');
      expect(screen.getByTestId('home-bento-tech-signal-MACD')).toHaveTextContent('0.2934');
      expect(screen.getByTestId('home-bento-tech-signal-均线结构')).toHaveTextContent('MA5 下穿 MA10，均线缠绕。');
      expect(screen.getByTestId('home-bento-tech-signal-量价动态')).toHaveTextContent('缩量，追价意愿偏弱。');
      expect(screen.getByTestId('home-bento-strategy-metric-观察区间')).toHaveTextContent('20.80');
    });
  });

  it('prefers the explicitly opened history detail over a stale completed-task snapshot for the same ticker', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    useStockPoolStore.setState({
      activeTasks: [
        {
          taskId: 'task-tsla-stale',
          stockCode: 'TSLA',
          stockName: 'Tesla',
          status: 'completed',
          progress: 100,
          reportType: 'detailed',
          createdAt: '2026-04-27T07:00:00Z',
          updatedAt: '2026-04-27T07:06:00Z',
          completedAt: '2026-04-27T07:06:00Z',
          result: {
            queryId: 'task-tsla-stale',
            stockCode: 'TSLA',
            stockName: 'Tesla',
            createdAt: '2026-04-27T07:06:00Z',
            report: {
              meta: {
                id: 22,
                queryId: 'task-tsla-stale',
                stockCode: 'TSLA',
                stockName: 'Tesla',
                reportType: 'detailed',
                createdAt: '2026-04-27T07:06:00Z',
              },
              summary: {
                analysisSummary: 'Stale task snapshot should not win over history detail.',
                operationAdvice: 'Wait',
                trendPrediction: 'Pending',
                sentimentScore: 50,
                sentimentLabel: 'Neutral',
              },
              strategy: {
                idealBuy: '-',
                stopLoss: '-',
                takeProfit: '-',
              },
              details: {
                standardReport: {
                  summaryPanel: {
                    stock: 'Tesla',
                    ticker: 'TSLA',
                    oneSentence: 'Stale task snapshot should not win over history detail.',
                  },
                  decisionContext: {
                    shortTermView: 'Task snapshot pending replacement.',
                  },
                  decisionPanel: {
                    idealEntry: '-',
                    target: '-',
                    stopLoss: '-',
                    buildStrategy: 'Task snapshot pending replacement.',
                  },
                  reasonLayer: {
                    coreReasons: ['Task snapshot pending replacement.'],
                  },
                  technicalFields: [],
                  fundamentalFields: [],
                },
              },
            },
          },
        },
      ],
    });

    vi.mocked(historyApi.getDetail).mockImplementation((recordId) => {
      if (recordId !== 2) {
        return Promise.resolve(defaultHistoryReport);
      }
      return Promise.resolve({
        ...defaultHistoryReport,
        meta: {
          ...defaultHistoryReport.meta,
          id: 2,
          queryId: 'q2',
          stockCode: 'TSLA',
          stockName: 'Tesla',
        },
        summary: {
          ...defaultHistoryReport.summary,
          analysisSummary: 'Persisted history detail must override the stale task snapshot.',
          operationAdvice: 'Trust persisted history detail.',
          trendPrediction: 'Recovered from saved record.',
          sentimentScore: 64,
          sentimentLabel: 'Bullish',
        },
        strategy: {
          idealBuy: '168.40 - 170.20',
          stopLoss: '162.80',
          takeProfit: '184.20',
        },
        details: {
          standardReport: {
            ...defaultHistoryReport.details.standardReport,
            summaryPanel: {
              ...defaultHistoryReport.details.standardReport.summaryPanel,
              stock: 'Tesla',
              ticker: 'TSLA',
              oneSentence: 'Persisted history detail must override the stale task snapshot.',
            },
            decisionContext: {
              shortTermView: 'Recovered from saved record.',
            },
            decisionPanel: {
              ...defaultHistoryReport.details.standardReport.decisionPanel,
              idealEntry: '168.40 - 170.20',
              target: '184.20',
              stopLoss: '162.80',
              buildStrategy: 'Trust persisted history detail.',
            },
            reasonLayer: {
              coreReasons: ['Persisted history detail must override the stale task snapshot.'],
            },
            technicalFields: [
              { label: 'MACD', value: '金叉后继续放大' },
              { label: '均线结构', value: 'MA20 重新走平' },
              { label: '量价配合', value: '回踩缩量，反弹放量' },
            ],
            fundamentalFields: [
              { label: '收入增速', value: '+8.6%' },
              { label: 'ROE', value: '18.2%' },
            ],
          },
        },
      });
    });

    renderSurface();
    fireEvent.click(await screen.findByTestId('home-bento-history-drawer-trigger'));
    fireEvent.click(await screen.findByTestId('home-bento-history-item-2'));

    await waitFor(() => {
      expect(screen.getByTestId('home-bento-decision-insight-copy').textContent).toContain('Persisted history detail must override the stale task snapshot.');
      expect(screen.getByTestId('home-bento-decision-insight-copy').textContent).not.toContain('Stale task snapshot should not win over history detail.');
    });
  });

  it('shows canonical generated timestamps in the history drawer', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    renderSurface();

    fireEvent.click(await screen.findByTestId('home-bento-history-drawer-trigger'));

    expect(await screen.findByText('Oracle (ORCL)')).toBeInTheDocument();
    expect(screen.getByText('Tesla (TSLA)')).toBeInTheDocument();
    expect(screen.getByText('NVIDIA (NVDA)')).toBeInTheDocument();
    expect(screen.getByText('04/27 16:03')).toBeInTheDocument();
    expect(screen.getByText('04/27 15:05')).toBeInTheDocument();
  });

  it('hides test history rows and falls back to ticker when company name is missing', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValueOnce({
      total: 3,
      page: 1,
      limit: 20,
      items: [
        { id: 31, queryId: 'q31', stockCode: 'ORCL', stockName: 'Oracle', companyName: 'Oracle', createdAt: '2026-04-27T08:00:00Z', generatedAt: '2026-04-27T08:03:00Z', isTest: false },
        { id: 32, queryId: 'q32', stockCode: 'BCHK', stockName: 'Oracle Browser Check', companyName: 'Oracle Browser Check', createdAt: '2026-04-27T07:00:00Z', generatedAt: '2026-04-27T07:05:00Z', isTest: true },
        { id: 33, queryId: 'q33', stockCode: 'NVDA', stockName: '', companyName: '', createdAt: '2026-04-27T06:00:00Z', generatedAt: '2026-04-27T06:04:00Z', isTest: false },
      ],
    });
    renderSurface();

    fireEvent.click(await screen.findByTestId('home-bento-history-drawer-trigger'));

    expect(await screen.findByText('Oracle (ORCL)')).toBeInTheDocument();
    expect(screen.getByText('NVDA')).toBeInTheDocument();
    expect(screen.queryByText('Oracle Browser Check (BCHK)')).not.toBeInTheDocument();
  });

  it('deletes a single history row from the drawer after confirmation', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.deleteRecords).mockResolvedValueOnce({ deleted: 1 });
    vi.mocked(historyApi.getList)
      .mockResolvedValueOnce({
        total: 3,
        page: 1,
        limit: 20,
        items: [
          { id: 3, queryId: 'q3', stockCode: 'ORCL', stockName: 'Oracle', companyName: 'Oracle', createdAt: '2026-04-27T08:00:00Z', generatedAt: '2026-04-27T08:03:00Z', isTest: false },
          { id: 2, queryId: 'q2', stockCode: 'TSLA', stockName: 'Tesla', companyName: 'Tesla', createdAt: '2026-04-27T07:00:00Z', generatedAt: '2026-04-27T07:05:00Z', isTest: false },
          { id: 1, queryId: 'q1', stockCode: 'NVDA', stockName: 'NVIDIA', companyName: 'NVIDIA', createdAt: '2026-04-27T06:00:00Z', generatedAt: '2026-04-27T06:04:00Z', isTest: false },
        ],
      })
      .mockResolvedValueOnce({
        total: 2,
        page: 1,
        limit: 20,
        items: [
          { id: 3, queryId: 'q3', stockCode: 'ORCL', stockName: 'Oracle', companyName: 'Oracle', createdAt: '2026-04-27T08:00:00Z', generatedAt: '2026-04-27T08:03:00Z', isTest: false },
          { id: 1, queryId: 'q1', stockCode: 'NVDA', stockName: 'NVIDIA', companyName: 'NVIDIA', createdAt: '2026-04-27T06:00:00Z', generatedAt: '2026-04-27T06:04:00Z', isTest: false },
        ],
      });
    vi.mocked(historyApi.getDetail).mockResolvedValue({
      ...defaultHistoryReport,
      meta: {
        ...defaultHistoryReport.meta,
        id: 3,
        queryId: 'q3',
      },
    });

    renderSurface();

    fireEvent.click(await screen.findByTestId('home-bento-history-drawer-trigger'));
    fireEvent.click(await screen.findByTestId('home-bento-history-delete-2'));

    expect(await screen.findByText('删除历史记录')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '确认删除' }));

    await waitFor(() => expect(historyApi.deleteRecords).toHaveBeenCalledWith([2], undefined));
    await waitFor(() => expect(screen.queryByTestId('home-bento-history-item-2')).not.toBeInTheDocument());
    expect(screen.getByTestId('home-bento-history-item-3')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-history-item-1')).toBeInTheDocument();
  });

  it('deletes all visible drawer rows after confirmation', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.deleteRecords).mockResolvedValueOnce({ deleted: 3 });
    vi.mocked(historyApi.getList)
      .mockResolvedValueOnce({
        total: 3,
        page: 1,
        limit: 20,
        items: [
          { id: 3, queryId: 'q3', stockCode: 'ORCL', stockName: 'Oracle', companyName: 'Oracle', createdAt: '2026-04-27T08:00:00Z', generatedAt: '2026-04-27T08:03:00Z', isTest: false },
          { id: 2, queryId: 'q2', stockCode: 'TSLA', stockName: 'Tesla', companyName: 'Tesla', createdAt: '2026-04-27T07:00:00Z', generatedAt: '2026-04-27T07:05:00Z', isTest: false },
          { id: 1, queryId: 'q1', stockCode: 'NVDA', stockName: 'NVIDIA', companyName: 'NVIDIA', createdAt: '2026-04-27T06:00:00Z', generatedAt: '2026-04-27T06:04:00Z', isTest: false },
        ],
      })
      .mockResolvedValueOnce({
        total: 0,
        page: 1,
        limit: 20,
        items: [],
      });

    renderSurface();

    fireEvent.click(await screen.findByTestId('home-bento-history-drawer-trigger'));
    fireEvent.click(await screen.findByTestId('home-bento-history-delete-all'));

    expect(await screen.findByText('确认删除选中的 3 条历史记录吗？删除后将不可恢复。')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '确认删除' }));

    await waitFor(() => expect(historyApi.deleteRecords).toHaveBeenCalledWith([3, 2, 1], { deleteAll: true }));
    await waitFor(() => expect(screen.getByText('历史分析尚未同步。')).toBeInTheDocument());
    expect(screen.getByTestId('home-bento-card-decision')).toBeInTheDocument();
    expect(screen.queryByText('甲骨文')).not.toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-zero-state')).not.toBeInTheDocument();
  });

  it('renders a cached history snapshot immediately and then replaces it with database detail', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    renderSurface();
    const deferred = createDeferred<typeof defaultHistoryReport>();

    useStockPoolStore.setState({
      reportSnapshotsByStockCode: {
        TSLA: {
          ...defaultHistoryReport,
          meta: {
            ...defaultHistoryReport.meta,
            id: 2,
            queryId: 'q2',
            stockCode: 'TSLA',
            stockName: 'Tesla',
          },
          summary: {
            ...defaultHistoryReport.summary,
            analysisSummary: 'Tesla cached snapshot should render immediately.',
            operationAdvice: 'Cached report only.',
            trendPrediction: 'No re-analyze should happen.',
            sentimentScore: 56,
            sentimentLabel: 'Neutral',
          },
          strategy: {
            idealBuy: '166.00 - 171.50',
            stopLoss: '159.20',
            takeProfit: '183.00',
          },
          details: {
            standardReport: {
              ...defaultHistoryReport.details.standardReport,
              summaryPanel: {
                ...defaultHistoryReport.details.standardReport.summaryPanel,
                stock: 'Tesla',
                ticker: 'TSLA',
                oneSentence: 'Cached snapshot only.',
              },
              decisionPanel: {
                ...defaultHistoryReport.details.standardReport.decisionPanel,
                idealEntry: '166.00 - 171.50',
                target: '183.00',
                stopLoss: '159.20',
              },
              reasonLayer: {
                coreReasons: ['Cached snapshot only.'],
              },
              technicalFields: [
                { label: 'MACD', value: '零轴下方收敛' },
                { label: 'MA20', value: '167.80' },
                { label: 'MA60', value: '161.20' },
              ],
              fundamentalFields: [
                { label: '收入增速', value: '+2.7%' },
                { label: '自由现金流', value: '$4.0B' },
                { label: '毛利率', value: '17.4%' },
              ],
            },
          },
        },
      },
    });

    vi.mocked(historyApi.getDetail).mockImplementation((recordId) => (
      recordId === 2 ? deferred.promise : Promise.resolve(defaultHistoryReport)
    ));
    vi.mocked(analysisApi.analyzeAsync).mockClear();

    fireEvent.click(await screen.findByTestId('home-bento-history-drawer-trigger'));
    fireEvent.click(await screen.findByTestId('home-bento-history-item-2'));

    expect(await screen.findByText('Tesla, Inc.')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-insight-copy').textContent).toContain('Cached snapshot only.');
    expect(historyApi.getDetail).toHaveBeenCalledWith(2);
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();

    deferred.resolve({
      ...defaultHistoryReport,
      meta: {
        ...defaultHistoryReport.meta,
        id: 2,
        queryId: 'q2',
        stockCode: 'TSLA',
        stockName: 'Tesla',
      },
      summary: {
        ...defaultHistoryReport.summary,
        analysisSummary: 'Database detail must replace the cached snapshot.',
        operationAdvice: 'Trust the persisted detail.',
        trendPrediction: 'History detail is the source of truth.',
        sentimentScore: 62,
        sentimentLabel: 'Bullish',
      },
      strategy: {
        idealBuy: '168.40 - 170.20',
        stopLoss: '162.80',
        takeProfit: '184.20',
      },
      details: {
        standardReport: {
          ...defaultHistoryReport.details.standardReport,
          summaryPanel: {
            ...defaultHistoryReport.details.standardReport.summaryPanel,
            stock: 'Tesla',
            ticker: 'TSLA',
            oneSentence: 'Persisted database detail replaced the cached snapshot.',
          },
          decisionPanel: {
            ...defaultHistoryReport.details.standardReport.decisionPanel,
            idealEntry: '168.40 - 170.20',
            target: '184.20',
            stopLoss: '162.80',
          },
          reasonLayer: {
            coreReasons: ['Persisted database detail replaced the cached snapshot.'],
          },
          technicalFields: [
            { label: 'MACD', value: '金叉后继续放大' },
            { label: 'MA20', value: '168.20' },
            { label: 'MA60', value: '163.10' },
          ],
        },
      },
    });

    await waitFor(() => {
      expect(screen.getByTestId('home-bento-decision-insight-copy').textContent).toContain('Persisted database detail replaced the cached snapshot.');
      expect(screen.getByTestId('home-bento-decision-insight-copy').textContent).not.toContain('Cached snapshot only.');
    });
  });

  it('keeps TSLA drill-down content synchronized with the active dashboard payload', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getDetail).mockImplementation((recordId) => {
      if (recordId === 2) {
        return Promise.resolve({
          ...defaultHistoryReport,
          meta: {
            ...defaultHistoryReport.meta,
            id: 2,
            queryId: 'q2',
            stockCode: 'TSLA',
            stockName: 'Tesla',
          },
          summary: {
            ...defaultHistoryReport.summary,
            analysisSummary: 'Tesla remains in a bounce validation zone.',
            operationAdvice: 'Add only after a second confirmation.',
            trendPrediction: 'High-beta rebound still needs follow-through volume.',
            sentimentScore: 56,
            sentimentLabel: 'Neutral',
          },
          strategy: {
            idealBuy: '166.00 - 171.50',
            stopLoss: '159.20',
            takeProfit: '183.00',
          },
          details: {
            standardReport: {
              ...defaultHistoryReport.details.standardReport,
              summaryPanel: {
                ...defaultHistoryReport.details.standardReport.summaryPanel,
                stock: 'Tesla',
                ticker: 'TSLA',
                oneSentence: 'Tesla is still inside a bounce validation zone after the initial squeeze.',
              },
              decisionContext: {
                shortTermView: 'High-beta rebound still needs follow-through volume.',
              },
              decisionPanel: {
                ...defaultHistoryReport.details.standardReport.decisionPanel,
                idealEntry: '166.00 - 171.50',
                target: '183.00',
                stopLoss: '159.20',
                buildStrategy: 'Add only after the second confirmation stays orderly.',
              },
              reasonLayer: {
                coreReasons: ['The bounce is still event-driven and has not converted into a clean trend continuation yet.'],
              },
              technicalFields: [
                { label: 'MACD', value: '零轴下方收敛' },
                { label: '均线结构', value: 'MA20 仍在下压' },
                { label: '量价配合', value: '反弹放量，续航待定' },
              ],
              fundamentalFields: [
                { label: '收入增速', value: '+2.7%' },
                { label: '自由现金流', value: '$4.0B' },
                { label: '毛利率', value: '17.4%' },
              ],
            },
          },
        });
      }
      return Promise.resolve(defaultHistoryReport);
    });

    renderSurface();
    fireEvent.click(await screen.findByTestId('home-bento-history-drawer-trigger'));
    fireEvent.click(await screen.findByTestId('home-bento-history-item-2'));

    expect(await screen.findByText('Tesla, Inc.')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-tech-signal-MACD')).toHaveTextContent('零轴下收敛');

    fireEvent.click(screen.getByTestId('home-bento-drawer-trigger-tech'));
    expect(await screen.findByText('TSLA 技术下钻')).toBeInTheDocument();
    expect(screen.getAllByText('零轴下收敛').length).toBeGreaterThan(1);
    expect(screen.getAllByText('零轴下方，空头动能衰减。').length).toBeGreaterThan(1);
    expect(screen.queryByText(/聚焦 MACD/)).not.toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    await new Promise((resolve) => window.setTimeout(resolve, 220));

    fireEvent.click(screen.getByTestId('home-bento-drawer-trigger-fundamentals'));
    expect(await screen.findByText('TSLA 基本面下钻')).toBeInTheDocument();
    expect(screen.getAllByText('+2.7%').length).toBeGreaterThan(0);
    expect(screen.getByText('营收 当前为 +2.7%，支撑说明需要继续绑定在这条基本面观测本身。')).toBeInTheDocument();
    expect(screen.queryByText(/将接入盈利质量与估值弹性描述卡/)).not.toBeInTheDocument();
  });

  it('enters loading state immediately when the analyze button is pressed and clears the local search query', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    const deferred = createDeferred<{ taskId: string; status: 'pending'; message: string }>();
    vi.mocked(analysisApi.analyzeAsync).mockImplementationOnce(() => deferred.promise);
    renderSurface();
    fireEvent.change(screen.getByTestId('home-bento-omnibar-input'), { target: { value: 'tsla' } });
    fireEvent.click(screen.getByTestId('home-bento-analyze-button'));
    expect(screen.getByTestId('home-bento-card-decision')).toBeInTheDocument();
    expect(screen.queryByText('深度分析请求已发出')).not.toBeInTheDocument();
    expect(screen.queryByText('WolfyStock 已接受该股票代码，首份完整报告生成期间会继续保留当前卡片骨架。')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-inplace-loading-decision')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-inplace-loading-strategy')).toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-progress-summary')).not.toBeInTheDocument();
    deferred.resolve({
      taskId: 'task-loading-state',
      status: 'pending',
      message: 'submitted',
    });
    await waitFor(() => expect(screen.getByTestId('home-bento-omnibar-input')).toHaveValue(''));
    expect(stocksApi.verifyTickerExists).not.toHaveBeenCalled();
    expect(analysisApi.analyzeAsync).toHaveBeenCalled();
  });

  it('rejects malformed ticker input before calling ticker validation or analysis', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    renderSurface();

    fireEvent.change(screen.getByTestId('home-bento-omnibar-input'), { target: { value: 'tsla!!!' } });
    fireEvent.click(screen.getByTestId('home-bento-analyze-button'));

    expect(await screen.findByText('请输入格式正确的股票代码')).toBeInTheDocument();
    expect(stocksApi.verifyTickerExists).not.toHaveBeenCalled();
    expect(analysisApi.analyzeAsync).not.toHaveBeenCalled();
  });

  it('submits analysis immediately for a valid ticker even when no local history exists', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    renderSurface();

    fireEvent.change(screen.getByTestId('home-bento-omnibar-input'), { target: { value: 'msft' } });
    fireEvent.click(screen.getByTestId('home-bento-analyze-button'));

    expect(screen.getByTestId('home-bento-card-decision')).toBeInTheDocument();
    await waitFor(() => expect(analysisApi.analyzeAsync).toHaveBeenCalledWith({
      stockCode: 'MSFT',
      reportType: 'detailed',
      stockName: undefined,
      originalQuery: 'MSFT',
      selectionSource: 'manual',
    }));
    expect(screen.queryByText('深度分析请求已发出')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-inplace-loading-decision')).toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-progress-summary')).not.toBeInTheDocument();
    expect(stocksApi.verifyTickerExists).not.toHaveBeenCalled();
    expect(screen.queryByText('未找到股票代码 MSFT，请检查是否退市或输入有误')).not.toBeInTheDocument();
  });

  it('renders sparse completed reports with neutral values instead of local demo presets', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValueOnce({
      total: 1,
      page: 1,
      limit: 20,
      items: [
        { id: 8, queryId: 'q8', stockCode: 'TSLA', stockName: 'Tesla', companyName: 'Tesla', createdAt: '2026-04-27T10:00:00Z', generatedAt: '2026-04-27T10:02:00Z', isTest: false },
      ],
    });
    vi.mocked(historyApi.getDetail).mockResolvedValueOnce({
      ...defaultHistoryReport,
      meta: {
        ...defaultHistoryReport.meta,
        id: 8,
        queryId: 'q8',
        stockCode: 'TSLA',
        stockName: 'Tesla',
      },
      summary: {
        analysisSummary: '',
        operationAdvice: '',
        trendPrediction: '',
        sentimentScore: undefined,
        sentimentLabel: '',
      },
      strategy: {},
      details: {
        standardReport: {
          summaryPanel: {
            stock: 'Tesla',
            ticker: 'TSLA',
            oneSentence: '',
          },
          decisionPanel: {},
          decisionContext: {},
          reasonLayer: {},
          technicalFields: [],
          fundamentalFields: [],
        },
      },
    });

    renderSurface();

    await screen.findByTestId('home-bento-card-decision');
    const quantSnapshot = screen.getByTestId('home-linear-quant-snapshot');
    expect(screen.getByTestId('home-bento-decision-ticker')).toHaveTextContent('TSLA');
    expect(screen.getByTestId('home-bento-card-strategy')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-tech')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-fundamentals')).toBeInTheDocument();
    expect(screen.getAllByText('待补充数据').length).toBeGreaterThan(2);
    expect(within(quantSnapshot).getByText('RSI-14')).toBeInTheDocument();
    expect(within(quantSnapshot).getByText('MACD')).toBeInTheDocument();
    expect(within(quantSnapshot).getByText('趋势强度')).toBeInTheDocument();
    expect(within(quantSnapshot).getByText('相对强度 (vs. SPY)')).toBeInTheDocument();
    expect(within(quantSnapshot).getAllByText('字段待接入').length).toBeGreaterThan(0);
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
    expect(screen.queryByText('N/A')).not.toBeInTheDocument();
    expect(screen.queryByText('反弹验证')).not.toBeInTheDocument();
    expect(screen.queryByText('事件驱动后仍需量能确认')).not.toBeInTheDocument();
    expect(screen.queryByText('166.00 - 171.50')).not.toBeInTheDocument();
    expect(screen.queryByText('首波反弹已有量能，但续航还需二次确认')).not.toBeInTheDocument();
  });

  it('updates pending analysis cards in place when the async task completes', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValueOnce({
      taskId: 'task-nflx',
      status: 'pending',
      message: 'submitted',
    });

    renderSurface();
    fireEvent.change(screen.getByTestId('home-bento-omnibar-input'), { target: { value: 'nflx' } });
    fireEvent.click(screen.getByTestId('home-bento-analyze-button'));

    await waitFor(() => expect(analysisApi.analyzeAsync).toHaveBeenCalled());
    await waitFor(() => expect(useStockPoolStore.getState().activeTasks.some((task) => task.taskId === 'task-nflx')).toBe(true));
    expect(screen.getByTestId('home-bento-card-decision')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-inplace-loading-decision')).toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-progress-summary')).not.toBeInTheDocument();

    act(() => {
      useStockPoolStore.getState().syncTaskUpdated({
        taskId: 'task-nflx',
        stockCode: 'NFLX',
        stockName: 'Netflix',
        status: 'completed',
        progress: 100,
        message: 'completed',
        reportType: 'detailed',
        createdAt: '2026-04-27T09:00:00Z',
        updatedAt: '2026-04-27T09:03:00Z',
        result: {
          report: {
            ...defaultHistoryReport,
            meta: {
              ...defaultHistoryReport.meta,
              id: 9,
              queryId: 'q9',
              stockCode: 'NFLX',
              stockName: 'Netflix',
            },
            summary: {
              ...defaultHistoryReport.summary,
              analysisSummary: 'Netflix completion replaced neutral cards.',
              trendPrediction: 'Streaming margin recovery is confirmed.',
              sentimentScore: 74,
              sentimentLabel: 'Bullish',
            },
            strategy: {
              idealBuy: '92.20 - 95.10',
              stopLoss: '88.40',
              takeProfit: '104.80',
            },
            details: {
              standardReport: {
                ...defaultHistoryReport.details.standardReport,
                summaryPanel: {
                  stock: 'Netflix',
                  ticker: 'NFLX',
                  oneSentence: 'Netflix completion replaced neutral cards.',
                },
                decisionContext: {
                  shortTermView: 'Streaming margin recovery is confirmed.',
                },
                decisionPanel: {
                  idealEntry: '92.20 - 95.10',
                  target: '104.80',
                  stopLoss: '88.40',
                  buildStrategy: 'Add only after the completed report confirms margin recovery.',
                },
                reasonLayer: {
                  coreReasons: ['Completed LLM report confirmed the refreshed thesis.'],
                },
                technicalFields: [
                  { label: 'MACD', value: 'Second expansion above zero' },
                  { label: 'Moving Averages', value: 'MA20 lifting MA60' },
                ],
                fundamentalFields: [
                  { label: 'Revenue Growth', value: '+12.4%' },
                  { label: 'Free Cash Flow', value: '$7.7B' },
                ],
              },
            },
          },
        },
      });
    });

    await waitFor(() => {
      const finalCard = screen.getByTestId('home-bento-analysis-result-card');
      expect(screen.getByTestId('home-research-header-strip')).toHaveTextContent('Netflix Inc.');
      expect(screen.getByTestId('home-research-header-strip')).toHaveTextContent('通信服务');
      expect(finalCard).toHaveTextContent('Netflix completion replaced neutral cards.');
      expect(screen.getByTestId('home-bento-decision-signal-hero')).toHaveTextContent('有条件观察');
      expect(screen.getByTestId('home-bento-decision-score-value')).toHaveTextContent('74');
      expect(screen.queryByTestId('home-bento-decision-direction')).not.toBeInTheDocument();
      expect(screen.getByTestId('home-bento-decision-insight-copy').textContent).toBe('Netflix completion replaced neutral cards.');
      expect(screen.getByTestId('home-bento-decision-support-grid')).toBeInTheDocument();
    });
    expect(screen.getAllByText('104.80').length).toBeGreaterThan(0);
    expect(screen.getByTestId('home-bento-dashboard')).toBeInTheDocument();
    expect(screen.queryByText('深度分析请求已发出')).not.toBeInTheDocument();
  });

  it('renders real Home candlesticks from daily OHLC history and exposes hover OHLC values', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    renderSurface();

    const chartFrame = await screen.findByTestId('home-candlestick-chart-frame');
    expect(stocksApi.getHistory).toHaveBeenLastCalledWith('ORCL', { period: 'daily', days: 365 });
    const chartRoot = screen.getByTestId('home-linear-technical-chart');
    expect(chartRoot).toHaveAttribute('data-chart-engine', 'echarts');
    expect(chartRoot).toHaveAttribute('data-tooltip-container', 'body');
    expect(chartRoot).toHaveAttribute('data-tooltip-bounds', 'viewport');
    expect(chartRoot).toHaveAttribute('data-axis-layout', 'split-price-volume');
    expect(chartRoot).toHaveAttribute('data-x-axis-density', 'sampled');
    expect(chartRoot).toHaveAttribute('data-chart-timeframe', '1D');
    expect(chartRoot).toHaveAttribute('data-chart-source', 'stocks-history-daily');
    expect(chartRoot).toHaveAttribute('data-visual-role', 'primary-chart');
    expect(chartRoot).toHaveClass(
      'home-chart-well',
      'rounded-none',
      'border-0',
      'bg-transparent',
    );

    fireEvent.mouseMove(chartFrame, { clientX: 0 });

    const tooltip = await screen.findByTestId('home-candlestick-hover-tooltip');
    expect(tooltip).toHaveTextContent('日期');
    expect(tooltip).toHaveTextContent('开盘 120.00');
    expect(tooltip).toHaveTextContent('最高 121.10');
    expect(tooltip).toHaveTextContent('最低 118.75');
    expect(tooltip).toHaveTextContent('收盘 119.65');
    expect(tooltip).toHaveTextContent('成交量 8.00M');
    expect(tooltip).not.toHaveTextContent('Open');

    fireEvent.mouseMove(chartFrame, { clientX: 280 });
    await waitFor(() => {
      expect(tooltip).toHaveTextContent('MA5');
      expect(tooltip).toHaveTextContent('MA10');
      expect(tooltip).toHaveTextContent('MA20');
    });
  });

  it('renders timeframe controls, hides intraday controls, and aggregates 1W/1M from daily candles', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    renderSurface();

    const chartRoot = await screen.findByTestId('home-linear-technical-chart');
    const timeframe1D = screen.getByRole('button', { name: '1D' });
    const timeframe1W = screen.getByRole('button', { name: '1W' });
    const timeframe1M = screen.getByRole('button', { name: '1M' });

    expect(timeframe1D).toHaveAttribute('aria-pressed', 'true');
    expect(timeframe1W).toHaveAttribute('aria-pressed', 'false');
    expect(timeframe1M).toHaveAttribute('aria-pressed', 'false');
    expect(timeframe1D).toHaveClass('rounded-full', 'bg-[var(--wolfy-accent-soft)]', 'text-white/86');
    expect(timeframe1W).toHaveClass('rounded-full', 'text-white/42');
    expect(screen.queryByRole('button', { name: '1m' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '5m' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '15m' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '1H' })).not.toBeInTheDocument();
    await waitFor(() => {
      expect(chartRoot).toHaveAttribute('data-chart-timeframe', '1D');
      expect(chartRoot).toHaveAttribute('data-chart-source', 'stocks-history-daily');
      expect(chartRoot).toHaveAttribute('data-chart-points', String(homeDailyCandles.length));
    });

    fireEvent.click(timeframe1W);
    await waitFor(() => {
      expect(chartRoot).toHaveAttribute('data-chart-timeframe', '1W');
      expect(chartRoot).toHaveAttribute('data-chart-source', 'stocks-history-daily-aggregated');
      expect(chartRoot).toHaveAttribute('data-chart-points', '4');
      expect(screen.getByTestId('home-bento-tech-signal-当前周期')).toHaveTextContent('1W');
    });

    fireEvent.click(timeframe1M);
    await waitFor(() => {
      expect(chartRoot).toHaveAttribute('data-chart-timeframe', '1M');
      expect(chartRoot).toHaveAttribute('data-chart-source', 'stocks-history-daily-aggregated');
      expect(chartRoot).toHaveAttribute('data-chart-points', '1');
      expect(screen.getByTestId('home-bento-tech-signal-当前周期')).toHaveTextContent('1M');
    });
  });

  it('toggles moving-average indicators without leaving the Home page', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    renderSurface();

    const chartRoot = await screen.findByTestId('home-linear-technical-chart');
    const chartFrame = await screen.findByTestId('home-candlestick-chart-frame');
    const ma20Toggle = screen.getByRole('button', { name: 'MA20' });
    const ma60Toggle = screen.getByRole('button', { name: 'MA60' });

    expect(chartRoot).toHaveAttribute('data-enabled-indicators', 'MA5,MA10,MA20');
    expect(ma20Toggle).toHaveAttribute('aria-pressed', 'true');
    expect(ma60Toggle).toBeDisabled();
    expect(ma20Toggle).toHaveClass('rounded-full', 'bg-white/[0.07]', 'text-white/84');
    expect(ma60Toggle).toHaveClass('rounded-full', 'opacity-40');

    fireEvent.click(ma20Toggle);

    await waitFor(() => {
      expect(ma20Toggle).toHaveAttribute('aria-pressed', 'false');
      expect(chartRoot).toHaveAttribute('data-enabled-indicators', 'MA5,MA10');
    });

    fireEvent.mouseMove(chartFrame, { clientX: 280 });
    const tooltip = await screen.findByTestId('home-candlestick-hover-tooltip');
    await waitFor(() => {
      expect(tooltip).toHaveTextContent('MA5');
      expect(tooltip).toHaveTextContent('MA10');
      expect(tooltip).not.toHaveTextContent('MA20');
    });
  });

  it('keeps the Home candlestick tooltip inside viewport bounds near chart edges', () => {
    const size = {
      contentSize: [210, 118] as [number, number],
      viewSize: [320, 246] as [number, number],
    };
    const chartRect = { left: 58, top: 140 };
    const viewport = { width: 390, height: 844 };

    const leftEdge = resolveHomeCandlestickTooltipPosition([0, 24], size, chartRect, viewport);
    expect(leftEdge[0] + chartRect.left).toBeGreaterThanOrEqual(10);
    expect(leftEdge[1] + chartRect.top).toBeGreaterThanOrEqual(10);

    const rightEdge = resolveHomeCandlestickTooltipPosition([318, 156], size, chartRect, viewport);
    expect(rightEdge[0] + chartRect.left + size.contentSize[0]).toBeLessThanOrEqual(viewport.width - 10);
    expect(rightEdge[1] + chartRect.top + size.contentSize[1]).toBeLessThanOrEqual(viewport.height - 10);
  });

  it('shows compact Home history diagnostics when daily OHLC is unavailable', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(stocksApi.getHistory).mockResolvedValue({
      stockCode: 'ORCL',
      stockName: 'Oracle',
      period: 'daily',
      source: 'unavailable',
      diagnostics: {
        status: 'unavailable',
        reason: 'us_daily_history_unavailable',
        providerTrace: [
          { provider: 'AlpacaFetcher', status: 'failed' },
          { provider: 'YfinanceFetcher', status: 'empty_result' },
        ],
      },
      sourceConfidence: {
        source: 'unavailable',
        freshness: 'unavailable',
        isUnavailable: true,
      },
      data: [],
    });

    renderSurface();

    await waitFor(() => {
      expect(screen.getByTestId('home-candlestick-unavailable')).toHaveTextContent('该周期行情暂不可用');
    });
    expect(screen.getByTestId('home-candlestick-unavailable')).toHaveTextContent('主数据源失败');
    expect(screen.getByTestId('home-candlestick-unavailable')).toHaveTextContent('本地回补不可用');
    expect(screen.getByTestId('home-candlestick-unavailable')).toHaveTextContent('可信度 不可用');
    expect(screen.queryByTestId('home-candlestick-chart-frame')).not.toBeInTheDocument();
    expect(screen.queryByTestId('home-candlestick-echarts-node')).not.toBeInTheDocument();
  });

  it('labels local fallback history metadata without fabricating Home candles', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(stocksApi.getHistory).mockResolvedValue({
      stockCode: 'ORCL',
      stockName: 'Oracle',
      period: 'daily',
      source: 'local_db',
      diagnostics: {
        status: 'degraded',
        reason: 'provider_failed_local_db_fallback',
        localFallback: {
          source: 'local_db',
          rows: 2,
        },
        providerTrace: [
          { provider: 'AlpacaFetcher', status: 'failed' },
        ],
      },
      sourceConfidence: {
        source: 'local_db',
        freshness: 'cached',
        isFallback: true,
        confidenceWeight: 0.75,
      },
      data: [],
    });

    renderSurface();

    const unavailable = await screen.findByTestId('home-candlestick-unavailable');
    expect(unavailable).toHaveTextContent('主数据源失败');
    expect(unavailable).toHaveTextContent('本地回补');
    expect(unavailable).toHaveTextContent('可信度 备用');
    expect(screen.getByTestId('home-linear-technical-chart')).toHaveAttribute('data-history-source', 'local_db');
    expect(screen.getByTestId('home-linear-technical-chart')).toHaveAttribute('data-history-confidence', 'cached');
    expect(screen.queryByTestId('home-candlestick-chart-frame')).not.toBeInTheDocument();
  });

  it('disables VWAP when volume support is unavailable', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(stocksApi.getHistory).mockResolvedValue({
      stockCode: 'ORCL',
      stockName: 'Oracle',
      period: 'daily',
      data: homeDailyCandles.map((item) => ({ ...item, volume: 0 })),
    });

    renderSurface();

    const chartRoot = await screen.findByTestId('home-linear-technical-chart');
    const vwapToggle = screen.getByRole('button', { name: 'VWAP' });

    expect(vwapToggle).toBeDisabled();
    expect(chartRoot).toHaveAttribute('data-vwap-available', 'false');
    expect(screen.getByText('VWAP 暂不可用')).toBeInTheDocument();
  });

  it('updates pending analysis cards in place when completed task payload only exposes snake_case standard_report', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    vi.mocked(analysisApi.analyzeAsync).mockResolvedValueOnce({
      taskId: 'task-amd',
      status: 'pending',
      message: 'submitted',
    });

    renderSurface();
    fireEvent.change(screen.getByTestId('home-bento-omnibar-input'), { target: { value: 'amd' } });
    fireEvent.click(screen.getByTestId('home-bento-analyze-button'));

    await waitFor(() => expect(useStockPoolStore.getState().activeTasks.some((task) => task.taskId === 'task-amd')).toBe(true));

    act(() => {
      useStockPoolStore.getState().syncTaskUpdated({
        taskId: 'task-amd',
        stockCode: 'AMD',
        stockName: 'AMD',
        status: 'completed',
        progress: 100,
        message: 'completed',
        reportType: 'detailed',
        createdAt: '2026-04-27T09:00:00Z',
        updatedAt: '2026-04-27T09:03:00Z',
        result: {
          queryId: 'q-amd',
          stockCode: 'AMD',
          stockName: 'AMD',
          createdAt: '2026-04-27T09:03:00Z',
          report: {
            ...defaultHistoryReport,
            meta: {
              ...defaultHistoryReport.meta,
              id: 10,
              queryId: 'q-amd',
              stockCode: 'AMD',
              stockName: 'AMD',
            },
            summary: {
              ...defaultHistoryReport.summary,
              analysisSummary: 'AMD task payload normalized from snake_case report blocks.',
              trendPrediction: 'Accelerator demand remains firm.',
              sentimentScore: 76,
              sentimentLabel: 'Bullish',
            },
            strategy: {
              idealBuy: '152.00 - 155.00',
              stopLoss: '147.80',
              takeProfit: '168.40',
            },
            details: {
              standard_report: {
                summary_panel: {
                  stock: 'AMD',
                  ticker: 'AMD',
                  one_sentence: 'AMD task payload normalized from snake_case report blocks.',
                },
                decision_context: {
                  short_term_view: 'Accelerator demand remains firm.',
                },
                decision_panel: {
                  ideal_entry: '152.00 - 155.00',
                  target: '168.40',
                  stop_loss: '147.80',
                  build_strategy: 'Only add after the completed task confirms sustained demand.',
                },
                reason_layer: {
                  core_reasons: ['Snake case task payload still populated the in-place dashboard.'],
                },
                technical_fields: [
                  { label: 'MACD', value: 'Positive spread widening' },
                  { label: 'Moving Averages', value: 'MA20 above MA60' },
                ],
                fundamental_fields: [
                  { label: 'Revenue Growth', value: '+18.2%' },
                  { label: 'Free Cash Flow', value: '$2.4B' },
                ],
              },
            },
          },
        },
      });
    });

    await waitFor(() => {
      expect(screen.getByTestId('home-bento-analysis-result-card')).toHaveTextContent('AMD task payload normalized from snake_case report blocks.');
    });
    expect(screen.getAllByText('168.40').length).toBeGreaterThan(0);
    expect(screen.getAllByText('147.80').length).toBeGreaterThan(0);
  });

  it('does not expose task progress internals on the home surface', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    renderSurface();

    act(() => {
      useStockPoolStore.getState().syncTaskCreated({
        taskId: 'task-tsla-runtime',
        stockCode: 'TSLA',
        stockName: 'Tesla',
        status: 'processing',
        progress: 62,
        message: '正在分析价格信号、基本面与新闻证据...',
        reportType: 'detailed',
        createdAt: '2026-04-27T09:00:00Z',
        updatedAt: '2026-04-27T09:02:00Z',
        execution: {
          ai: {
            model: 'deepseek/deepseek-chat',
            provider: 'deepseek',
            gateway: 'deepseek-primary',
            modelTruth: 'actual',
            providerTruth: 'actual',
            gatewayTruth: 'actual',
            fallbackOccurred: false,
            fallbackTruth: 'actual',
            configuredPrimaryModel: 'deepseek/deepseek-chat',
          },
          data: {
            market: {
              source: 'alpaca',
              truth: 'actual',
              fallbackOccurred: false,
              status: 'ok',
              finalReason: '行情请求成功。',
            },
            fundamentals: {
              source: 'fmp',
              truth: 'actual',
              fallbackOccurred: true,
              status: 'partial',
              finalReason: 'finnhub 限流后已切换到 FMP。',
            },
            news: {
              source: 'gnews',
              truth: 'actual',
              fallbackOccurred: false,
              status: 'failed',
              finalReason: '429 Too Many Requests',
            },
            sentiment: {
              source: 'tavily_filtered',
              truth: 'inferred',
              fallbackOccurred: false,
              status: 'configured_not_used',
              finalReason: '新闻源失败，情绪聚合未执行。',
            },
          },
          report: {
            standardReport: {
              status: 'failed',
              present: false,
              truth: 'actual',
              path: 'task.result.report.details.standard_report',
              finalReason: 'standard_report 尚未生成，首页卡片仍在等待结构化结果。',
            },
          },
          steps: [
            { key: 'data_fetch', status: 'partial' },
            { key: 'ai_analysis', status: 'partial' },
            { key: 'standard_report', status: 'failed' },
          ],
        },
      });
    });

    expect(screen.queryByTestId('home-bento-task-progress-card')).not.toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-progress-summary')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-decision')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-strategy')).toBeInTheDocument();
    expect(screen.queryByText('LLM')).not.toBeInTheDocument();
    expect(screen.queryByText('Technical')).not.toBeInTheDocument();
    expect(screen.queryByText('Fundamental')).not.toBeInTheDocument();
    expect(screen.queryByText('News')).not.toBeInTheDocument();
    expect(screen.queryByText('Sentiment')).not.toBeInTheDocument();
    expect(screen.queryByText(/deepseek\/deepseek-chat/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/alpaca/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/gnews/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/429 Too Many Requests/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/standard_report/i)).not.toBeInTheDocument();
  });

  it('hydrates final analysis in place without auto-scrolling', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoView,
    });

    renderSurface();

    await act(async () => {
      useStockPoolStore.getState().syncTaskCreated({
        taskId: 'task-complete',
        stockCode: 'ORCL',
        stockName: 'Oracle',
        status: 'processing',
        progress: 72,
        reportType: 'detailed',
        createdAt: '2026-04-29T10:00:00Z',
        updatedAt: '2026-04-29T10:00:00Z',
        message: 'assembling report',
      });
    });

    await act(async () => {
      useStockPoolStore.getState().syncTaskUpdated({
        taskId: 'task-complete',
        stockCode: 'ORCL',
        stockName: 'Oracle',
        status: 'completed',
        progress: 100,
        reportType: 'detailed',
        createdAt: '2026-04-29T10:00:00Z',
        updatedAt: '2026-04-29T10:00:02Z',
        result: {
          queryId: 'q-nflx',
          stockCode: 'ORCL',
          stockName: 'Oracle',
          createdAt: '2026-04-29T10:00:02Z',
          report: {
            meta: {
              queryId: 'q-nflx',
              stockCode: 'ORCL',
              stockName: 'Oracle',
              reportType: 'detailed',
              createdAt: '2026-04-29T10:00:02Z',
            },
            summary: {
              analysisSummary: 'Netflix completion replaced neutral cards.',
              operationAdvice: 'Buy',
              trendPrediction: 'Momentum continues.',
              sentimentScore: 81,
            },
            strategy: {
              takeProfit: '104.80',
              stopLoss: '94.20',
            },
            details: {
              standardReport: {
                decisionPanel: {
                  target: '104.80',
                  stopLoss: '94.20',
                },
              },
            },
          },
        },
      });
    });

    expect(await screen.findByTestId('home-bento-analysis-result-card')).toHaveTextContent('Netflix completion replaced neutral cards.');
    expect(scrollIntoView).not.toHaveBeenCalled();
  });

  it('keeps neutral cards instead of demo data when the analysis API fails', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    const deferred = createDeferred<never>();
    vi.mocked(analysisApi.analyzeAsync).mockImplementationOnce(() => deferred.promise);
    renderSurface();
    fireEvent.change(screen.getByTestId('home-bento-omnibar-input'), { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByTestId('home-bento-analyze-button'));

    expect(screen.getByTestId('home-bento-card-decision')).toBeInTheDocument();
    deferred.reject(createApiError(createParsedApiError({
        title: '请求过于频繁',
        message: '请求过于频繁，请稍后再试。',
        status: 429,
        category: 'upstream_unavailable',
      })));

    await waitFor(() => expect(screen.getByTestId('home-bento-omnibar-input')).toHaveValue(''));
    expect(await screen.findByText('请求过于频繁，请稍后再试。')).toBeInTheDocument();
    expect(screen.queryByText('AI 引擎调用过载，已加载本地快照数据')).not.toBeInTheDocument();
    expect(screen.queryByText('Oracle Corporation')).not.toBeInTheDocument();
    expect(screen.queryByText('Oracle')).not.toBeInTheDocument();
    expect(screen.queryByText('待确认股票')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-ticker')).toHaveTextContent('AAPL');
    expect(screen.getAllByText('-').length).toBeGreaterThan(0);
    expect(screen.queryByText('偏多')).not.toBeInTheDocument();
    expect(screen.queryByText('短线技术偏强，均线结构偏多')).not.toBeInTheDocument();
    expect(screen.queryByText('持有。技术结构：价格位于 MA20 上方，防守位在近期支撑带；若回踩企稳，趋势延续概率更高。')).not.toBeInTheDocument();
    expect(screen.queryByText('技术面与基本面相互印证，资金承接良好，综合建议以持有为主。')).not.toBeInTheDocument();
    expect(screen.queryByText('短线动能充沛，价格沿五日线攀升')).not.toBeInTheDocument();
    expect(screen.queryByText('趋势支撑确认，回踩不破可视作介入点')).not.toBeInTheDocument();
    expect(screen.queryByText('总市值体量充足，流动性承接极强')).not.toBeInTheDocument();
    expect(screen.queryByText('估值仍在成长溢价区，需业绩继续兑现')).not.toBeInTheDocument();
    expect(screen.queryByText(/RateLimitError/i)).not.toBeInTheDocument();
  });

  it('keeps the existing card shell and pending placeholders after manual submit without a persisted report', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValue({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });
    const deferred = createDeferred<{ taskId: string; status: 'pending'; message: string }>();
    vi.mocked(analysisApi.analyzeAsync).mockImplementationOnce(() => deferred.promise);
    vi.mocked(analysisApi.getTaskProgress).mockResolvedValue({
      taskId: 'task-orcl',
      stockCode: 'ORCL',
      stockName: 'Oracle',
      status: 'processing',
      progress: 34,
      message: '正在并行加载行情、基本面、技术与财报数据...',
      modules: [
        { key: 'market', name: '市场识别', status: 'completed', detail: 'Detecting market' },
        { key: 'quote', name: '行情', status: 'running', detail: 'Loading quote' },
        { key: 'fundamental', name: '基本面', status: 'running', detail: 'Loading fundamentals' },
      ],
    });

    renderSurface();
    fireEvent.change(screen.getByTestId('home-bento-omnibar-input'), { target: { value: 'ORCL' } });
    fireEvent.click(screen.getByTestId('home-bento-analyze-button'));

    expect(screen.getByTestId('home-bento-card-decision')).toBeInTheDocument();
    expect(screen.queryByText('Oracle Corporation')).not.toBeInTheDocument();

    deferred.resolve({
      taskId: 'task-orcl',
      status: 'pending',
      message: 'submitted',
    });

    await waitFor(() => expect(screen.getByTestId('home-bento-omnibar-input')).toHaveValue(''));
    expect(screen.queryByText('深度分析请求已发出')).not.toBeInTheDocument();
    expect(screen.queryByText('输入股票代码后将在此原位刷新 AI 判断。')).not.toBeInTheDocument();
    expect(screen.queryByText('WolfyStock 已接受该股票代码，首份完整报告生成期间会继续保留当前卡片骨架。')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-inplace-loading-decision')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-inplace-loading-strategy')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('home-bento-progress-timeline')).toHaveTextContent('行情/技术面'));
    expect(screen.getByTestId('home-bento-progress-timeline')).toHaveTextContent('基本面');
    expect(screen.queryByTestId('home-bento-progress-summary')).not.toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-zero-state')).not.toBeInTheDocument();
    expect(screen.queryByText('Oracle Corporation')).not.toBeInTheDocument();
  });

  it('shows sanitized actionable model diagnostics when Home analysis rejects an unusable model config', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(analysisApi.analyzeAsync).mockRejectedValueOnce(createApiError(createParsedApiError({
      title: '配置的模型不可用',
      message: '配置的模型不可用。当前可用模型：openai/gpt-4.1-free, openai/gpt-4o-free',
      status: 500,
      category: 'llm_not_configured',
      rawMessage: '配置的模型不可用。当前可用模型：openai/gpt-4.1-free, openai/gpt-4o-free',
      details: {
        configuredModel: 'openai/gpt-5-ghost',
        availableModels: ['openai/gpt-4.1-free', 'openai/gpt-4o-free'],
        stackTrace: 'Traceback: should not be shown',
        apiKey: 'sk-secret-123',
      },
    })));

    renderSurface();
    fireEvent.change(screen.getByTestId('home-bento-omnibar-input'), { target: { value: 'AAPL' } });
    fireEvent.click(screen.getByTestId('home-bento-analyze-button'));

    expect(await screen.findByText('配置的模型不可用。当前可用模型：openai/gpt-4.1-free, openai/gpt-4o-free')).toBeInTheDocument();
    expect(screen.queryByText(/Traceback/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/sk-secret-123/i)).not.toBeInTheDocument();
  });

  it('uses watchlist task query params as the active analysis instead of stale history', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(analysisApi.getTaskProgress).mockResolvedValue({
      taskId: 'task-wulf',
      stockCode: 'WULF',
      stockName: 'WULF',
      status: 'processing',
      progress: 42,
      message: 'Running AI analysis',
      modules: [
        { key: 'market', name: 'Detecting market', status: 'completed' },
        { key: 'ai', name: 'Running AI analysis', status: 'running' },
      ],
    });

    renderSurface('/?symbol=WULF&task_id=task-wulf&source=watchlist&market=US');

    expect(await screen.findByTestId('home-bento-inplace-loading-decision')).toHaveTextContent('WULF');
    await waitFor(() => expect(screen.getByTestId('home-bento-progress-timeline')).toHaveTextContent('Running AI analysis'));
    expect(screen.queryByText('Oracle Corporation')).not.toBeInTheDocument();
  });

  it('keeps the watchlist running state mounted when task progress omits modules', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(analysisApi.getTasks).mockResolvedValue({
      total: 1,
      pending: 0,
      processing: 1,
      tasks: [{
        taskId: 'task-wulf',
        stockCode: 'WULF',
        stockName: 'WULF',
        status: 'processing',
        progress: 12,
        message: 'Running AI analysis',
        reportType: 'detailed',
        createdAt: '2026-05-03T10:00:00Z',
        progressModules: null,
      } as unknown as Awaited<ReturnType<typeof analysisApi.getTasks>>['tasks'][number]],
    });
    vi.mocked(analysisApi.getTaskProgress).mockResolvedValue({
      taskId: 'task-wulf',
      stockCode: 'WULF',
      stockName: 'WULF',
      status: 'processing',
      progress: 12,
      message: 'Running AI analysis',
      modules: null,
    } as unknown as Awaited<ReturnType<typeof analysisApi.getTaskProgress>>);

    renderSurface('/?symbol=WULF&task_id=task-wulf&source=watchlist&market=US');

    expect(await screen.findByTestId('home-bento-inplace-loading-decision')).toHaveTextContent('WULF');
    expect(screen.getByTestId('home-bento-inplace-loading-decision')).toHaveTextContent('Running AI analysis');
    expect(screen.queryByText('Oracle Corporation')).not.toBeInTheDocument();
  });

  it('loads the completed watchlist task report for the routed task id', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(analysisApi.getTaskProgress).mockResolvedValue({
      taskId: 'task-wulf',
      stockCode: 'WULF',
      stockName: 'WULF',
      status: 'completed',
      progress: 100,
      message: 'completed',
      modules: [],
      finalResult: {
        queryId: 'q-wulf',
        stockCode: 'WULF',
        stockName: 'WULF',
        createdAt: '2026-05-02T12:00:00Z',
        report: {
          ...defaultHistoryReport,
          meta: {
            ...defaultHistoryReport.meta,
            id: 11,
            queryId: 'q-wulf',
            stockCode: 'WULF',
            stockName: 'WULF',
          },
          summary: {
            ...defaultHistoryReport.summary,
            analysisSummary: 'WULF completed from watchlist task handoff.',
            sentimentScore: 60,
          },
          details: {
            standardReport: {
              ...defaultHistoryReport.details.standardReport,
              summaryPanel: {
                stock: 'WULF',
                ticker: 'WULF',
                oneSentence: 'WULF completed from watchlist task handoff.',
              },
            },
          },
        },
      },
    });

    renderSurface('/?symbol=WULF&task_id=task-wulf&source=watchlist&market=US');

    await waitFor(() => expect(screen.getByTestId('home-bento-analysis-result-card')).toHaveTextContent('WULF completed from watchlist task handoff.'));
    expect(screen.queryByText('Oracle Corporation')).not.toBeInTheDocument();
  });
});
