import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import WatchlistPage from '../WatchlistPage';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import type { WatchlistItem } from '../../types/watchlist';

const { listWatchlistItems, removeWatchlistItem, refreshScores, getRefreshStatus, analyzeAsync, useProductSurfaceMock } = vi.hoisted(() => ({
  listWatchlistItems: vi.fn(),
  removeWatchlistItem: vi.fn(),
  refreshScores: vi.fn(),
  getRefreshStatus: vi.fn(),
  analyzeAsync: vi.fn(),
  useProductSurfaceMock: vi.fn(),
}));

vi.mock('../../api/watchlist', () => ({
  watchlistApi: {
    listWatchlistItems,
    addWatchlistItem: vi.fn(),
    removeWatchlistItem,
    refreshScores,
    getRefreshStatus,
  },
}));

vi.mock('../../api/analysis', () => ({
  analysisApi: {
    analyzeAsync,
  },
  DuplicateTaskError: class DuplicateTaskError extends Error {},
}));

vi.mock('../../hooks/useProductSurface', () => ({
  useProductSurface: () => useProductSurfaceMock(),
}));

vi.mock('../../components/auth/AuthGuardOverlay', () => ({
  AuthGuardOverlay: ({ moduleName }: { moduleName: string }) => <div>{`auth-guard:${moduleName}`}</div>,
}));

const writeTextMock = vi.fn();

function makeItem(overrides: Partial<WatchlistItem>): WatchlistItem {
  return {
    id: 1,
    symbol: 'NVDA',
    market: 'us',
    name: 'NVIDIA',
    source: 'scanner',
    scannerRunId: 42,
    scannerRank: 1,
    scannerScore: 94,
    lastScoredAt: '2026-05-01T12:30:00',
    scoreSource: 'scanner_run',
    scoreProfile: 'us_preopen_v1',
    scoreReason: 'Latest scanner score.',
    scoreStatus: 'fresh',
    scoreError: null,
    themeId: 'ai-momentum',
    universeType: 'theme',
    notes: null,
    createdAt: '2026-04-30T08:00:00',
    updatedAt: '2026-04-30T09:00:00',
    ...overrides,
  };
}

const watchlistItems: WatchlistItem[] = [
  makeItem({
    id: 1,
    symbol: 'NVDA',
    market: 'us',
    name: 'NVIDIA',
    scannerRunId: 42,
    scannerRank: 1,
    scannerScore: 94,
    themeId: 'ai-momentum',
    universeType: 'theme',
    createdAt: '2026-04-30T08:00:00',
    updatedAt: '2026-04-30T09:00:00',
  }),
  makeItem({
    id: 2,
    symbol: 'TSM',
    market: 'hk',
    name: 'TSMC',
    scannerRunId: 41,
    scannerRank: 3,
    scannerScore: 88,
    themeId: 'semis',
    universeType: 'theme',
    createdAt: '2026-04-25T08:00:00',
    updatedAt: '2026-04-25T09:00:00',
  }),
  makeItem({
    id: 3,
    symbol: '600519',
    market: 'cn',
    name: '贵州茅台',
    scannerRunId: 39,
    scannerRank: 8,
    scannerScore: 77,
    themeId: null,
    universeType: 'default',
    createdAt: '2026-04-10T08:00:00',
    updatedAt: '2026-04-10T09:00:00',
  }),
];

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>;
}

function renderWatchlist(path = '/watchlist') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <UiLanguageProvider>
        <Routes>
          <Route path="/watchlist" element={<><WatchlistPage /><LocationProbe /></>} />
          <Route path="/zh" element={<><div>home</div><LocationProbe /></>} />
          <Route path="/zh/scanner" element={<div>scanner</div>} />
          <Route path="/zh/backtest" element={<div>backtest</div>} />
          <Route path="/zh/login" element={<div>login</div>} />
        </Routes>
      </UiLanguageProvider>
    </MemoryRouter>,
  );
}

describe('WatchlistPage', () => {
  beforeEach(() => {
    vi.spyOn(Date, 'now').mockReturnValue(new Date('2026-05-01T12:00:00Z').getTime());
    vi.clearAllMocks();
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    listWatchlistItems.mockResolvedValue({ items: watchlistItems });
    removeWatchlistItem.mockResolvedValue({ deleted: 1 });
    refreshScores.mockResolvedValue({
      ok: true,
      updatedCount: 3,
      failedCount: 0,
      skippedCount: 0,
      startedAt: '2026-05-01T12:00:00Z',
      completedAt: '2026-05-01T12:00:01Z',
      markets: ['cn', 'hk', 'us'],
      results: [],
    });
    getRefreshStatus.mockResolvedValue({
      enabled: true,
      usTime: '08:45',
      cnTime: '09:00',
      hkTime: '09:00',
      maxSymbols: 250,
      running: false,
    });
    analyzeAsync.mockResolvedValue({ taskId: 'task-1' });
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: writeTextMock,
      },
    });
    writeTextMock.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders tracked candidates from the watchlist API', async () => {
    renderWatchlist();

    expect(await screen.findByTestId('watchlist-row-NVDA')).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-TSM')).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-600519')).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-filter-grid')).toHaveClass('min-w-0', 'grid-cols-1', 'md:grid-cols-2', 'xl:grid-cols-5');
    expect(screen.getByLabelText('市场')).toHaveClass('pr-10', 'ui-control-value');
    expect(screen.getByLabelText('主题 / 候选范围')).toHaveClass('pr-10', 'ui-control-value');
    expect(listWatchlistItems).toHaveBeenCalledTimes(1);
  });

  it('shows summary totals for total, markets, scanner source, and recently added candidates', async () => {
    renderWatchlist();

    await screen.findByTestId('watchlist-row-NVDA');
    expect(screen.getByText('追踪总数').nextElementSibling).toHaveTextContent('3');
    expect(screen.getByText('覆盖市场').nextElementSibling).toHaveTextContent('3');
    expect(screen.getByText('扫描来源').nextElementSibling).toHaveTextContent('3');
    expect(screen.getByText('近期新增').nextElementSibling).toHaveTextContent('2');
  });

  it('filters rows by symbol or name search', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('搜索'), { target: { value: 'tsm' } });

    expect(screen.queryByTestId('watchlist-row-NVDA')).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-TSM')).toBeInTheDocument();
  });

  it('filters rows by market', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('市场'), { target: { value: 'hk' } });

    expect(screen.queryByTestId('watchlist-row-NVDA')).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-TSM')).toBeInTheDocument();
  });

  it('filters rows by source and theme or universe context', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('来源'), { target: { value: 'scanner' } });
    fireEvent.change(screen.getByLabelText('主题 / 候选范围'), { target: { value: 'theme:semis' } });

    expect(screen.queryByTestId('watchlist-row-NVDA')).not.toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-TSM')).toBeInTheDocument();
  });

  it('sorts rows by scanner score', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.change(screen.getByLabelText('排序'), { target: { value: 'scannerScore' } });

    const rows = Array.from(document.querySelectorAll('tbody tr'));
    expect(within(rows[0] as HTMLElement).getByText('NVDA')).toBeInTheDocument();
    expect(within(rows[1] as HTMLElement).getByText('TSM')).toBeInTheDocument();
    expect(within(rows[2] as HTMLElement).getByText('600519')).toBeInTheDocument();
  });

  it('keeps the filter controls overflow-safe with long labels', async () => {
    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    const searchInput = screen.getByLabelText('搜索');
    expect(searchInput).toHaveClass('pr-12');
    expect(screen.getByTestId('watchlist-filter-grid').className).not.toContain('overflow-hidden');
  });

  it('starts analysis for a candidate and navigates to the workspace', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.click(within(row).getByRole('button', { name: /分析/ }));

    await waitFor(() => expect(analyzeAsync).toHaveBeenCalledWith(expect.objectContaining({
      stockCode: 'NVDA',
      reportType: 'detailed',
      stockName: 'NVIDIA',
      originalQuery: 'NVDA',
      selectionSource: 'manual',
    })));
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/zh?symbol=NVDA&task_id=task-1&source=watchlist&market=US'));
    expect(screen.getByText('home')).toBeInTheDocument();
  });

  it('renders score freshness and manually refreshes scores', async () => {
    const refreshedItems = [
      makeItem({
        id: 1,
        symbol: 'NVDA',
        scannerScore: 96,
        scannerRank: 1,
        lastScoredAt: '2026-05-01T13:00:00',
        scoreStatus: 'fresh',
      }),
    ];
    listWatchlistItems
      .mockResolvedValueOnce({ items: watchlistItems })
      .mockResolvedValueOnce({ items: refreshedItems });

    renderWatchlist();
    await screen.findByTestId('watchlist-row-NVDA');

    expect(screen.getByText('开盘前自动更新')).toBeInTheDocument();
    expect(screen.getAllByText('最新').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: /刷新评分/ }));

    await waitFor(() => expect(refreshScores).toHaveBeenCalledWith({ force: true }));
    expect(await screen.findByText(/评分已刷新/)).toBeInTheDocument();
    expect(screen.getByTestId('watchlist-row-NVDA')).toHaveTextContent('96.0');
  });

  it('links backtest with scanner and watchlist metadata', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    const link = within(row).getByRole('link', { name: /回测/ });
    expect(link).toHaveAttribute('href', expect.stringContaining('/zh/backtest?'));
    expect(link).toHaveAttribute('href', expect.stringContaining('symbol=NVDA'));
    expect(link).toHaveAttribute('href', expect.stringContaining('source=scanner'));
    expect(link).toHaveAttribute('href', expect.stringContaining('origin=watchlist'));
    expect(link).toHaveAttribute('href', expect.stringContaining('watchlistItemId=1'));
    expect(link).toHaveAttribute('href', expect.stringContaining('scannerRunId=42'));
    expect(link).toHaveAttribute('href', expect.stringContaining('themeId=ai-momentum'));
  });

  it('removes a candidate through the delete API and drops the row', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.click(within(row).getByRole('button', { name: '移除 NVDA' }));

    await waitFor(() => expect(removeWatchlistItem).toHaveBeenCalledWith(1));
    expect(screen.queryByTestId('watchlist-row-NVDA')).not.toBeInTheDocument();
  });

  it('copies the symbol to the clipboard', async () => {
    renderWatchlist();
    const row = await screen.findByTestId('watchlist-row-NVDA');

    fireEvent.click(within(row).getByRole('button', { name: '复制代码 NVDA' }));

    await waitFor(() => expect(writeTextMock).toHaveBeenCalledWith('NVDA'));
    expect(await screen.findByText('NVDA 已复制')).toBeInTheDocument();
  });

  it('renders an empty state with a scanner link', async () => {
    listWatchlistItems.mockResolvedValue({ items: [] });

    renderWatchlist();

    expect(await screen.findByText('暂无追踪候选。')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /打开扫描器/ })[1]).toHaveAttribute('href', '/zh/scanner');
  });

  it('renders the authentication guard for guests', () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: true });

    renderWatchlist();

    expect(screen.getByText('auth-guard:观察列表')).toBeInTheDocument();
    expect(listWatchlistItems).not.toHaveBeenCalled();
  });
});
