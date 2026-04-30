import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { analysisApi } from '../../api/analysis';
import { createApiError, createParsedApiError } from '../../api/error';
import { historyApi } from '../../api/history';
import { UiPreferencesProvider } from '../../contexts/UiPreferencesContext';
import { stocksApi } from '../../api/stocks';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { useStockPoolStore } from '../../stores';
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
};

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

  const renderSurface = () => render(
    <MemoryRouter>
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
    expect(screen.queryByTestId('home-bento-grid')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'WolfyStock 决策面板' })).toBeInTheDocument();
  });

  it('renders the signed-in bento dashboard for authenticated users', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    renderSurface();
    await screen.findByText('Oracle Corporation');
    const root = screen.getByTestId('home-bento-dashboard');
    const grid = screen.getByTestId('home-bento-grid');
    const main = screen.getByTestId('home-bento-main');
    const omnibarShell = screen.getByTestId('home-bento-omnibar-shell');
    const omnibar = screen.getByTestId('home-bento-omnibar');
    const primaryStack = screen.getByTestId('home-bento-primary-stack');
    const secondaryStack = screen.getByTestId('home-bento-secondary-stack');
    const secondaryGrid = screen.getByTestId('home-bento-secondary-grid');
    const strategyCard = screen.getByTestId('home-bento-card-strategy');
    const techCard = screen.getByTestId('home-bento-card-tech');
    const fundamentalsCard = screen.getByTestId('home-bento-card-fundamentals');
    const homeSearch = screen.getByTestId('home-bento-omnibar-input');
    const entryMetric = screen.getByTestId('home-bento-strategy-metric-建仓区间');
    const targetMetric = screen.getByTestId('home-bento-strategy-metric-目标位');
    const stopLossMetric = screen.getByTestId('home-bento-strategy-metric-止损位');
    const strategyContent = entryMetric.parentElement;
    const targetMetricsGrid = targetMetric.parentElement;
    const techMetricTiles = Array.from(techCard.querySelectorAll('div')).filter((node) => node.className.includes('rounded-[32px]'));
    const fundamentalsMetricTiles = Array.from(fundamentalsCard.querySelectorAll('div')).filter((node) => node.className.includes('rounded-[32px]'));
    expect(root).toHaveAttribute('data-bento-surface', 'true');
    expect(root).toHaveClass('bento-surface-root');
    expect(screen.queryByTestId('home-bento-header-logo')).not.toBeInTheDocument();
    expect(root).toHaveClass('w-full', 'flex', 'flex-1', 'min-h-0', 'min-w-0', 'flex-col', 'gap-6');
    expect(root).not.toHaveClass('workspace-width-wide', 'overflow-x-hidden');
    expect(root.className).not.toContain('max-w-[1920px]');
    expect(root.className).not.toContain('md:h-[calc(100dvh-var(--shell-masthead-height)-var(--shell-masthead-height)-4.9rem)]');
    expect(root.className).not.toContain('overflow-hidden');
    expect(omnibarShell).toHaveClass('order-first', 'w-full', 'shrink-0', 'xl:order-none');
    expect(omnibarShell).not.toHaveClass('mb-8', 'max-w-4xl', 'absolute', 'fixed', 'z-10', '-mt-10');
    expect(omnibar).toHaveClass('flex', 'h-12', 'w-full', 'min-w-0', 'gap-3');
    expect(grid).toHaveAttribute('data-bento-grid', 'true');
    expect(main).toHaveClass('w-full', 'flex-1', 'min-w-0', 'flex', 'flex-col', 'min-h-0');
    expect(main).not.toHaveClass('px-6', 'md:px-8', 'xl:px-12', 'pt-6', 'pb-12', 'overflow-y-auto', 'no-scrollbar');
    expect(main.className).not.toContain('overflow-hidden');
    expect(main.firstElementChild).toBe(grid);
    expect(grid).toHaveClass('grid', 'w-full', 'grid-cols-1', 'items-start', 'gap-6', 'xl:grid-cols-12');
    expect(grid).not.toHaveClass('flex', 'xl:flex-row', 'items-stretch');
    expect(primaryStack).toHaveClass('col-span-1', 'flex', 'flex-col', 'h-auto', 'min-h-0', 'w-full', 'xl:h-full', 'xl:col-span-5');
    expect(grid.firstElementChild).toBe(primaryStack);
    expect(secondaryStack).toHaveClass('col-span-1', 'flex', 'flex-col', 'gap-6', 'w-full', 'min-h-0', 'min-w-0', 'xl:col-span-7');
    expect(secondaryStack.firstElementChild).toBe(omnibarShell);
    expect(secondaryGrid).toHaveClass('grid', 'grid-cols-1', 'md:grid-cols-2', 'gap-6', 'w-full', 'xl:flex-1', 'items-stretch');
    expect(homeSearch).toHaveAttribute('placeholder', '输入代码唤醒 AI (如 ORCL)...');
    expect(homeSearch).toHaveValue('');
    expect(screen.getByTestId('home-bento-omnibar-input-shell')).toHaveClass('overflow-hidden', 'rounded-2xl', 'border', 'border-white/5', 'bg-white/[0.02]', 'shadow-lg');
    expect(homeSearch).toHaveClass('bg-transparent', 'text-sm', 'leading-none', 'pl-11', 'caret-white');
    expect(screen.getByTestId('home-bento-analyze-button')).toHaveTextContent('分析');
    expect(screen.getByTestId('home-bento-analyze-button')).toHaveClass('rounded-2xl', 'bg-white/[0.05]', 'border', 'border-white/10', 'backdrop-blur-md');
    expect(within(omnibar).getByTestId('home-bento-history-drawer-trigger')).toBeInTheDocument();
    expect(within(omnibar).getByRole('button', { name: '历史记录' })).toBeInTheDocument();
    expect(screen.queryByText('SYSTEM VIEW')).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /扫描器/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /持仓/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /回测/i })).not.toBeInTheDocument();
    expect(screen.getByText('WOLFY AI 决策')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-drawer-trigger-decision')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-drawer-trigger-strategy')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-drawer-trigger-tech')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-drawer-trigger-fundamentals')).toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-decision-chart-workspace')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-hero-row')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-signal-hero')).toHaveTextContent('买');
    expect(screen.getByTestId('home-bento-decision-core-metrics')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-insight')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-support-grid')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-decision')).toHaveClass('w-full', 'overflow-visible', 'xl:h-full', 'xl:overflow-hidden');
    expect(screen.getByTestId('home-bento-card-decision')).not.toHaveClass('h-full', 'overflow-hidden');
    expect(screen.getByTestId('home-bento-decision-scroll-body')).toHaveClass('overflow-visible', 'xl:min-h-0', 'xl:flex-1', 'xl:overflow-y-auto', 'pr-2', 'pb-6');
    expect(screen.getByTestId('home-bento-decision-scroll-body')).not.toHaveClass('overflow-y-auto');
    expect(screen.getByTestId('home-bento-decision-hero-row')).toHaveClass('grid', 'grid-cols-2', 'xl:grid-cols-3', 'items-end', 'gap-8', 'mt-6', 'mb-10', 'w-full');
    expect(screen.getByTestId('home-bento-decision-action')).toHaveClass('col-span-1', 'min-w-0');
    expect(screen.getByTestId('home-bento-decision-score')).toHaveClass('col-span-1', 'min-w-0');
    expect(screen.getByTestId('home-bento-decision-conviction')).toHaveClass('col-span-2', 'xl:col-span-1', 'min-w-0', 'w-full');
    expect(screen.getByTestId('home-bento-decision-conviction-value')).toHaveTextContent('78%');
    expect(screen.getAllByTestId(/home-bento-decision-conviction-segment-/).filter((segment) => segment.className.includes('shadow-')).length).toBe(4);
    expect(screen.getByTestId('home-bento-decision-core-metrics').className).not.toContain('border');
    expect(screen.getByTestId('home-bento-decision-core-metrics').className).not.toContain('bg-');
    expect(screen.getByTestId('home-bento-decision-insight')).toHaveClass('max-w-3xl', 'text-sm', 'text-white/70', 'leading-relaxed', 'mb-10');
    expect(screen.getByTestId('home-bento-decision-insight').className).not.toContain('grid');
    expect(screen.getByText('AI 动作')).toBeInTheDocument();
    expect(screen.getByText('执行主线')).toBeInTheDocument();
    expect(screen.getByText('量化佐证指标')).toBeInTheDocument();
    expect(screen.getByText('均线排列')).toBeInTheDocument();
    expect(screen.getByText('资金承接')).toBeInTheDocument();
    expect(screen.getAllByText('RSI-14').length).toBeGreaterThan(1);
    expect(screen.getByText('MACD-12/26/9')).toBeInTheDocument();
    expect(screen.getByText('量能确认')).toBeInTheDocument();
    expect(screen.getByText('金叉')).toBeInTheDocument();
    expect(screen.queryByText('AI 信号方向')).not.toBeInTheDocument();
    expect(screen.queryByText('最近报告归因')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-signal-hero')).toHaveTextContent('买');
    expect(screen.getByTestId('home-bento-decision-company-header')).toHaveTextContent('Oracle Corporation');
    expect(screen.getByTestId('home-bento-decision-sector')).toHaveTextContent('TECHNOLOGY');
    expect(screen.getByTestId('home-bento-decision-score-value')).toHaveTextContent('7.8');
    expect(screen.queryByTestId('home-bento-decision-direction')).not.toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-sibling-row')).not.toBeInTheDocument();
    expect(strategyCard).toHaveClass('w-full', 'overflow-visible', 'rounded-[24px]');
    expect(strategyCard).not.toHaveClass('overflow-hidden', 'h-full');
    expect(strategyCard.className).not.toContain('xl:col-span-1');
    expect(techCard).toHaveClass('w-full', 'rounded-[24px]');
    expect(techCard).not.toHaveClass('h-full');
    expect(techCard.className).not.toContain('xl:col-span-1');
    expect(fundamentalsCard).toHaveClass('w-full', 'h-full', 'rounded-[24px]');
    expect(fundamentalsCard.className).not.toContain('xl:col-span-1');
    expect(screen.getByTestId('home-bento-card-decision')).toHaveClass('w-full', 'xl:h-full', 'rounded-[24px]');
    expect(screen.getByTestId('home-bento-card-decision').className).not.toContain('xl:col-span-2');
    expect(techCard).toHaveClass('bg-white/[0.02]', 'backdrop-blur-2xl', 'border-white/5');
    expect(fundamentalsCard).toHaveClass('bg-white/[0.02]', 'backdrop-blur-2xl', 'border-white/5');
    expect(screen.getByTestId('home-bento-card-decision')).toHaveClass('md:px-10', 'md:py-8');
    expect(entryMetric).not.toHaveClass('bg-white/[0.02]', 'border-white/[0.08]', 'p-6', 'col-span-2');
    expect(strategyContent).toHaveClass('mt-4', 'flex', 'w-full', 'min-w-0', 'flex-col');
    expect(strategyContent).not.toHaveClass('grid', 'md:grid-cols-2');
    expect(targetMetricsGrid).toHaveClass('mt-6', 'grid', 'grid-cols-2', 'gap-4', 'w-full');
    expect(entryMetric).toHaveClass('flex', 'flex-col', 'gap-1.5');
    expect(targetMetric).not.toHaveClass('col-span-2');
    expect(stopLossMetric).not.toHaveClass('col-span-2');
    const macdSignal = screen.getByTestId('home-bento-tech-signal-MACD');
    const macdSignalValue = macdSignal.querySelectorAll('span')[1];
    expect(screen.getByText('理想买入点')).toHaveClass('text-[10px]', 'tracking-widest', 'text-white/40', 'truncate');
    expect(screen.getByText('121.80 - 124.60')).toHaveClass('text-sm', 'font-medium', 'leading-relaxed');
    expect(screen.getByText('133.50')).toHaveClass('text-sm', 'font-medium', 'leading-relaxed', 'text-emerald-400');
    expect(screen.getByText('117.40')).toHaveClass('text-sm', 'font-medium', 'leading-relaxed', 'text-rose-400');
    expect(screen.getByTestId('home-bento-decision-signal-hero')).toHaveClass('text-emerald-400');
    expect(macdSignalValue).not.toBeUndefined();
    expect(macdSignal).toHaveClass('flex', 'flex-col', 'gap-1', 'py-2', 'border-b', 'border-white/5');
    expect(macdSignalValue).toHaveClass('text-xs', 'font-medium', 'text-right');
    expect(screen.getByTestId('home-bento-fundamental-metric-REVENUE')).toHaveTextContent('+9.4%');
    expect(screen.getByText('121.80 - 124.60').className).not.toContain('text-2xl');
    expect(screen.getByText('+9.4%').className).not.toContain('text-2xl');
    expect(screen.getByText('+9.4%').className).not.toContain('text-3xl');
    expect(techMetricTiles.length).toBe(0);
    expect(fundamentalsMetricTiles.length).toBe(0);
    expect(macdSignalValue).toHaveClass('text-emerald-400', 'drop-shadow-[0_0_8px_rgba(52,211,153,0.4)]');
    expect(macdSignalValue?.getAttribute('style') || '').toContain('text-shadow: 0 0 8px rgba(52, 211, 153, 0.4)');
    expect(screen.getByTestId('home-bento-tech-signal-detail-MACD')).toHaveClass('mt-1', 'block', 'w-full', 'overflow-hidden', 'text-ellipsis', 'whitespace-nowrap', 'text-xs', 'text-white/40');
    expect(screen.getByTestId('home-bento-tech-signal-detail-MACD')).toHaveAttribute('title', '零轴上方，动能再扩张。');
    expect(screen.getByTestId('home-bento-tech-signal-detail-MACD')).toHaveTextContent('零轴上方，动能再扩张。');
    expect(screen.queryByText('Second expansion above zero')).not.toBeInTheDocument();
    expect(screen.getByText('MA20 > MA60')).toBeInTheDocument();
    expect(screen.getByText('+9.4%').getAttribute('style') || '').toBe('');
    expect(screen.getByText('ROE')).toBeInTheDocument();
    expect(screen.getByText('EBITDA MARGIN')).toBeInTheDocument();
    expect(screen.queryByText('$12.1B')).not.toBeInTheDocument();
    expect(primaryStack.compareDocumentPosition(secondaryStack) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByTestId('home-bento-card-decision').compareDocumentPosition(omnibar) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(omnibar.parentElement).toBe(omnibarShell);
    expect(omnibarShell.parentElement).toBe(secondaryStack);
    expect(omnibar.compareDocumentPosition(strategyCard) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(strategyCard.compareDocumentPosition(secondaryGrid) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(techCard.compareDocumentPosition(fundamentalsCard) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByTestId('home-bento-card-workflow')).not.toBeInTheDocument();
    expect(screen.queryByText('先给出区间，再决定节奏。')).not.toBeInTheDocument();
    expect(screen.queryByText('最近没有基本面特征')).not.toBeInTheDocument();
  });

  it('switches decision and strategy tones when the user prefers CN market colors', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    window.localStorage.setItem('dsa-market-color-convention', 'redUpGreenDown');

    renderSurface();

    await screen.findByText('Oracle Corporation');
    expect(screen.getByTestId('home-bento-decision-signal-hero')).toHaveClass('text-rose-400');
    expect(screen.getByText('133.50')).toHaveClass('text-rose-400');
    expect(screen.getByText('117.40')).toHaveClass('text-emerald-400');
  });

  it('keeps the full bento card layout when there is no non-test history', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    vi.mocked(historyApi.getList).mockResolvedValueOnce({
      total: 0,
      page: 1,
      limit: 20,
      items: [],
    });

    renderSurface();

    const grid = await screen.findByTestId('home-bento-grid');
    const primaryStack = screen.getByTestId('home-bento-primary-stack');
    const secondaryStack = screen.getByTestId('home-bento-secondary-stack');
    const secondaryGrid = screen.getByTestId('home-bento-secondary-grid');
    const omnibar = screen.getByTestId('home-bento-omnibar');
    expect(omnibar).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-history-drawer-trigger')).toBeInTheDocument();
    expect(grid).toHaveClass('grid', 'w-full', 'grid-cols-1', 'gap-6', 'xl:grid-cols-12');
    expect(grid).toHaveAttribute('data-bento-grid', 'true');
    expect(primaryStack).toHaveClass('col-span-1', 'flex', 'flex-col', 'h-auto', 'min-h-0', 'w-full', 'xl:h-full', 'xl:col-span-5');
    expect(secondaryStack).toHaveClass('col-span-1', 'flex', 'flex-col', 'gap-6', 'w-full', 'min-h-0', 'min-w-0', 'xl:col-span-7');
    expect(secondaryStack.firstElementChild).toBe(screen.getByTestId('home-bento-omnibar-shell'));
    expect(secondaryGrid).toHaveClass('grid', 'grid-cols-1', 'md:grid-cols-2', 'gap-6', 'w-full', 'xl:flex-1');
    expect(screen.getByTestId('home-bento-card-decision')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-strategy')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-tech')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-fundamentals')).toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-zero-state')).not.toBeInTheDocument();
    expect(screen.queryByText('Ghost dashboard 承接中')).not.toBeInTheDocument();
    expect(screen.queryByText('待分析')).not.toBeInTheDocument();
    expect(screen.queryByText('等待输入')).not.toBeInTheDocument();
    expect(screen.queryByText('等待分析')).not.toBeInTheDocument();
    expect(screen.queryByText('输入股票代码后将在此原位刷新 AI 判断。')).not.toBeInTheDocument();
    expect(screen.queryByText('首页卡片会始终保留在这里，未分析字段先保持中性占位，等待你提交股票代码或打开完成历史。')).not.toBeInTheDocument();
    expect(screen.getByText('理想买入点')).toBeInTheDocument();
    expect(screen.getAllByText('-').length).toBeGreaterThan(0);
  });

  it('keeps analysis loading inside the existing bento cards', async () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    const deferred = createDeferred<{ taskId: string; status: 'pending'; message: string }>();
    vi.mocked(analysisApi.analyzeAsync).mockReturnValueOnce(deferred.promise);

    renderSurface();

    await screen.findByTestId('home-bento-grid');
    const input = screen.getByTestId('home-bento-omnibar-input');
    fireEvent.change(input, { target: { value: 'NVDA' } });
    fireEvent.submit(screen.getByTestId('home-bento-omnibar'));

    expect(await screen.findByTestId('home-bento-inplace-loading-decision')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-grid')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-secondary-grid')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-decision')).toHaveClass('animate-pulse', 'bg-white/[0.05]', 'border-indigo-500/20');
    expect(screen.getByTestId('home-bento-card-strategy')).toHaveClass('animate-pulse', 'bg-white/[0.05]', 'border-indigo-500/20');
    expect(screen.getByRole('img', { name: 'WolfyStock analyzing' })).toHaveAttribute('src', '/wolfystock-logo-mark.png');
    expect(screen.getByRole('img', { name: 'WolfyStock analyzing' })).toHaveClass('[animation:spin_2.8s_linear_infinite]', 'shadow-[0_0_22px_rgba(99,102,241,0.22)]');
    expect(screen.getByTestId('home-bento-inplace-loading-tech')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-inplace-loading-fundamentals')).toBeInTheDocument();
    expect(screen.getByText('Wolfy AI 引擎推理中...')).toBeInTheDocument();
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
    expect(await screen.findByText('Execution Strategy')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-omnibar-input')).toHaveAttribute('placeholder', 'Enter a ticker to wake the AI (for example ORCL)...');
    expect(screen.getByText('Technical Structure')).toBeInTheDocument();
    expect(screen.getByText('Fundamental Profile')).toBeInTheDocument();
    expect(screen.getByText('Execution Strategy')).toHaveClass('truncate');
    expect(screen.getByText('Fundamental Profile')).toHaveClass('truncate');
    expect(screen.queryByRole('link', { name: /scanner/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /portfolio/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /backtest/i })).not.toBeInTheDocument();
    expect(screen.queryByText('Lock the range first, then decide the pace.')).not.toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-decision-chart-workspace')).not.toBeInTheDocument();
    expect(screen.getByTestId('home-bento-decision-signal-hero')).toHaveTextContent('BUY');
    expect(screen.getByText('ACTION')).toBeInTheDocument();
    expect(screen.getByText('SCORE')).toBeInTheDocument();
    expect(screen.queryByText('DIRECTION')).not.toBeInTheDocument();
    expect(screen.getByText('AI INSIGHT')).toBeInTheDocument();
    expect(screen.getByText('SUPPORTING INDICATORS')).toBeInTheDocument();
    expect(screen.getAllByText('MA ALIGNMENT').length).toBeGreaterThan(1);
    expect(screen.getByText('LIQUIDITY AB.')).toBeInTheDocument();
    expect(screen.getByText('BULL CROSSOVER')).toBeInTheDocument();
    expect(screen.getAllByText('RSI-14').length).toBeGreaterThan(1);
    expect(screen.getByText('VOLUME DYNAMICS')).toBeInTheDocument();
    expect(screen.getByText('EBITDA MARGIN')).toBeInTheDocument();
    expect(screen.getByText('LATEST EPS')).toBeInTheDocument();
    expect(screen.getByText('FORWARD PE')).toBeInTheDocument();
    expect(screen.getByText('PEG RATIO')).toBeInTheDocument();
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
    await waitFor(() => expect(screen.getByText('(ORCL)')).toBeInTheDocument());
    expect(screen.getByTestId('home-bento-card-decision')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-strategy')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-tech')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-fundamentals')).toBeInTheDocument();
    expect(screen.getAllByText('-').length).toBeGreaterThan(8);
    expect(screen.getAllByText('N/A').length).toBeGreaterThan(0);
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
    expect(screen.getByText('执行约束')).toBeInTheDocument();
    expect(screen.getAllByText('建仓区间').length).toBeGreaterThan(0);
    expect(screen.getAllByText('仓位节奏').length).toBeGreaterThan(0);
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
      expect(screen.getByTestId('home-bento-tech-signal-MA ALIGNMENT')).toHaveTextContent('MA5 下穿 MA10，均线缠绕。');
      expect(screen.getByTestId('home-bento-tech-signal-VOLUME DYNAMICS')).toHaveTextContent('缩量，追价意愿偏弱。');
      expect(screen.getByTestId('home-bento-strategy-metric-建仓区间')).toHaveTextContent('20.80');
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
    expect(screen.getByText('REVENUE 当前为 +2.7%，支撑说明需要继续绑定在这条基本面观测本身。')).toBeInTheDocument();
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
    expect(screen.getByText('(TSLA)')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-strategy')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-tech')).toBeInTheDocument();
    expect(screen.getByTestId('home-bento-card-fundamentals')).toBeInTheDocument();
    expect(screen.getAllByText('-').length).toBeGreaterThan(8);
    expect(screen.getAllByText('N/A').length).toBeGreaterThan(0);
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
      expect(finalCard).toHaveTextContent('Netflix Inc.');
      expect(finalCard).toHaveTextContent('COMMUNICATION SERVICES');
      expect(screen.getByTestId('home-bento-decision-signal-hero')).toHaveTextContent('买');
      expect(screen.getByTestId('home-bento-decision-score-value')).toHaveTextContent('7.4');
      expect(screen.queryByTestId('home-bento-decision-direction')).not.toBeInTheDocument();
      expect(screen.getByTestId('home-bento-decision-insight-copy').textContent).toBe('Netflix completion replaced neutral cards.');
      expect(screen.getByTestId('home-bento-decision-support-grid')).toBeInTheDocument();
    });
    expect(screen.getAllByText('104.80').length).toBeGreaterThan(0);
    expect(screen.getByTestId('home-bento-dashboard')).toBeInTheDocument();
    expect(screen.queryByText('深度分析请求已发出')).not.toBeInTheDocument();
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
    expect(await screen.findByText('LLM 分析失败，请稍后重试')).toBeInTheDocument();
    expect(screen.queryByText('AI 引擎调用过载，已加载本地快照数据')).not.toBeInTheDocument();
    expect(screen.queryByText('Oracle Corporation')).not.toBeInTheDocument();
    expect(screen.queryByText('Oracle')).not.toBeInTheDocument();
    expect(screen.queryByText('待确认股票')).not.toBeInTheDocument();
    expect(screen.getByText('(AAPL)')).toBeInTheDocument();
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
    expect(screen.queryByTestId('home-bento-progress-summary')).not.toBeInTheDocument();
    expect(screen.queryByTestId('home-bento-zero-state')).not.toBeInTheDocument();
    expect(screen.queryByText('Oracle Corporation')).not.toBeInTheDocument();
  });
});
