import type React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApiError, createParsedApiError } from '../../api/error';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { translate } from '../../i18n/core';
import {
  LEGACY_PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY,
  PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY,
} from '../../utils/portfolioPreferences';
import PortfolioPage from '../PortfolioPage';

const {
  getAccounts,
  getSnapshot,
  getRisk,
  refreshFx,
  refreshFxRate,
  listBrokerConnections,
  listImportBrokers,
  syncIbkrReadOnly,
  listTrades,
  listCashLedger,
  listCorporateActions,
  createTrade,
  updateTrade,
  deleteTrade,
  createCashLedger,
  deleteCashLedger,
  createCorporateAction,
  deleteCorporateAction,
  parseCsvImport,
  commitCsvImport,
  createAccount,
  deleteAccount,
} = vi.hoisted(() => ({
  getAccounts: vi.fn(),
  getSnapshot: vi.fn(),
  getRisk: vi.fn(),
  refreshFx: vi.fn(),
  refreshFxRate: vi.fn(),
  listBrokerConnections: vi.fn(),
  listImportBrokers: vi.fn(),
  syncIbkrReadOnly: vi.fn(),
  listTrades: vi.fn(),
  listCashLedger: vi.fn(),
  listCorporateActions: vi.fn(),
  createTrade: vi.fn(),
  updateTrade: vi.fn(),
  deleteTrade: vi.fn(),
  createCashLedger: vi.fn(),
  deleteCashLedger: vi.fn(),
  createCorporateAction: vi.fn(),
  deleteCorporateAction: vi.fn(),
  parseCsvImport: vi.fn(),
  commitCsvImport: vi.fn(),
  createAccount: vi.fn(),
  deleteAccount: vi.fn(),
}));

vi.mock('../../api/portfolio', () => ({
  portfolioApi: {
    getAccounts,
    getSnapshot,
    getRisk,
    refreshFx,
    refreshFxRate,
    listBrokerConnections,
    listImportBrokers,
    syncIbkrReadOnly,
    listTrades,
    listCashLedger,
    listCorporateActions,
    createTrade,
    updateTrade,
    deleteTrade,
    createCashLedger,
    deleteCashLedger,
    createCorporateAction,
    deleteCorporateAction,
    parseCsvImport,
    commitCsvImport,
    createAccount,
    deleteAccount,
  },
}));

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PieChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Pie: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Tooltip: () => null,
  Legend: () => null,
  Cell: () => null,
}));

type AccountItem = {
  id: number;
  name: string;
  market?: 'cn' | 'hk' | 'us' | 'global';
  baseCurrency?: string;
  isActive?: boolean;
};

function makeAccounts(items: AccountItem[] = [{ id: 1, name: 'Main' }]) {
  return {
    accounts: items.map((item) => ({
      id: item.id,
      name: item.name,
      broker: 'Demo',
      market: item.market ?? 'us',
      baseCurrency: item.baseCurrency ?? 'CNY',
      isActive: item.isActive ?? true,
      ownerId: null,
      createdAt: '2026-03-19T00:00:00Z',
      updatedAt: '2026-03-19T00:00:00Z',
    })),
  };
}

function makeSnapshot(options: {
  accountId?: number;
  fxStale?: boolean;
  accountCount?: number;
  includePosition?: boolean;
  fxRates?: Array<{
    fromCurrency: string;
    toCurrency: string;
    rate: number | null;
    rateDate?: string | null;
    source: string;
    isStale: boolean;
    updatedAt?: string | null;
    sourceDirection: string;
  }>;
} = {}) {
  const accountId = options.accountId ?? 1;
  const positions = options.includePosition ? [
    {
      symbol: 'AAPL',
      market: 'us',
      currency: 'USD',
      quantity: 10,
      avgCost: 150,
      totalCost: 1500,
      lastPrice: 160,
      marketValueBase: 1600,
      unrealizedPnlBase: 100,
      valuationCurrency: 'USD',
    },
  ] : [];
  return {
    asOf: '2026-03-19',
    costMethod: 'fifo' as const,
    currency: 'CNY',
    accountCount: options.accountCount ?? 1,
    totalCash: options.includePosition ? 1000 : 0,
    totalMarketValue: options.includePosition ? 2000 : 0,
    totalEquity: options.includePosition ? 3000 : 0,
    realizedPnl: 0,
    unrealizedPnl: 0,
    feeTotal: 0,
    taxTotal: 0,
    fxStale: options.fxStale ?? true,
    fxRates: options.fxRates ?? [
      {
        fromCurrency: 'USD',
        toCurrency: 'CNY',
        rate: 7.245,
        rateDate: '2026-03-19',
        source: 'manual',
        isStale: false,
        updatedAt: '2026-03-19T10:00:00',
        sourceDirection: 'direct',
      },
      {
        fromCurrency: 'HKD',
        toCurrency: 'CNY',
        rate: 0.921,
        rateDate: '2026-03-19',
        source: 'manual',
        isStale: false,
        updatedAt: '2026-03-19T10:00:00',
        sourceDirection: 'direct',
      },
    ],
    portfolioAttribution: {
      accountAttribution: {
        topAccounts: [
          {
            accountId,
            accountName: `Account ${accountId}`,
            equityWeightPct: 100,
          },
        ],
      },
      industryAttribution: {
        topIndustries: [
          {
            industry: '半导体',
            weightPct: 61.2,
            symbolCount: 2,
          },
        ],
      },
    },
    accounts: [
      {
        accountId,
        accountName: `Account ${accountId}`,
        ownerId: null,
        broker: 'Demo',
        market: 'us',
        baseCurrency: 'CNY',
        asOf: '2026-03-19',
        costMethod: 'fifo' as const,
        totalCash: options.includePosition ? 1000 : 0,
        totalMarketValue: options.includePosition ? 2000 : 0,
        totalEquity: options.includePosition ? 3000 : 0,
        realizedPnl: 0,
        unrealizedPnl: 0,
        feeTotal: 0,
        taxTotal: 0,
        fxStale: options.fxStale ?? true,
        positions,
      },
    ],
  };
}

function makeRisk() {
  return {
    asOf: '2026-03-19',
    accountId: null,
    costMethod: 'fifo' as const,
    currency: 'CNY',
    thresholds: {},
    concentration: {
      totalMarketValue: 0,
      topWeightPct: 0,
      alert: false,
      topPositions: [],
    },
    sectorConcentration: {
      totalMarketValue: 0,
      topWeightPct: 0,
      alert: false,
      topSectors: [],
      coverage: {},
      errors: [],
    },
    industryAttribution: {
      topIndustries: [
        {
          industry: '半导体',
          weightPct: 61.2,
          symbolCount: 2,
        },
      ],
    },
    accountAttribution: {
      topAccounts: [
        {
          accountId: 1,
          accountName: 'Main',
          equityWeightPct: 100,
        },
      ],
    },
    drawdown: {
      seriesPoints: 0,
      maxDrawdownPct: 0,
      currentDrawdownPct: 0,
      alert: false,
      fxStale: false,
    },
    stopLoss: {
      nearAlert: false,
      triggeredCount: 0,
      nearCount: 0,
      items: [],
    },
  };
}

function deferredPromise<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

async function waitForInitialLoad() {
  await waitFor(() => expect(getAccounts).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(getSnapshot).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(getRisk).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(listTrades).toHaveBeenCalledTimes(1));
}

function openFxPanel(language: 'zh' | 'en' = 'zh') {
  fireEvent.click(screen.getByRole('button', { name: language === 'en' ? 'FX' : '汇率' }));
  return within(screen.getByTestId('portfolio-fx-panel')).getByRole('button', { name: translate(language, 'portfolio.refreshFx') });
}

describe('PortfolioPage FX refresh', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 1024 });

    getAccounts.mockResolvedValue(makeAccounts());
    getSnapshot.mockImplementation(async ({ accountId }: { accountId?: number } = {}) => makeSnapshot({ accountId, fxStale: true }));
    getRisk.mockResolvedValue(makeRisk());
    refreshFx.mockResolvedValue({
      asOf: '2026-03-19',
      accountCount: 1,
      refreshEnabled: true,
      disabledReason: null,
      pairCount: 1,
      updatedCount: 1,
      staleCount: 0,
      errorCount: 0,
    });
    refreshFxRate.mockResolvedValue({
      baseCurrency: 'USD',
      quoteCurrency: 'CNY',
      rate: 7.2468,
      provider: 'frankfurter',
      fetchedAt: '2026-03-19T10:05:00',
      cacheHit: false,
      stale: false,
      error: null,
    });
    listBrokerConnections.mockResolvedValue({ connections: [] });
    listImportBrokers.mockResolvedValue({
      brokers: [{ broker: 'huatai', aliases: [], displayName: '华泰', fileExtensions: ['csv'] }],
    });
    syncIbkrReadOnly.mockResolvedValue({
      accountId: 1,
      brokerConnectionId: 9,
      brokerAccountRef: 'U1234567',
      connectionName: 'Primary IBKR',
      snapshotDate: '2026-03-19',
      syncedAt: '2026-03-19T10:00:00',
      baseCurrency: 'USD',
      totalCash: 5000,
      totalMarketValue: 1600,
      totalEquity: 6600,
      realizedPnl: 0,
      unrealizedPnl: 100,
      positionCount: 1,
      cashBalanceCount: 1,
      fxStale: false,
      snapshotOverlayActive: true,
      usedExistingConnection: true,
      apiBaseUrl: 'https://localhost:5000/v1/api',
      verifySsl: false,
      warnings: [],
    });
    listTrades.mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20 });
    listCashLedger.mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20 });
    listCorporateActions.mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 20 });
    createTrade.mockResolvedValue({ id: 1 });
    updateTrade.mockResolvedValue({
      id: 1,
      accountId: 1,
      symbol: 'AAPL',
      market: 'us',
      currency: 'USD',
      tradeDate: '2026-03-18',
      side: 'buy',
      quantity: 2,
      price: 101,
      fee: 0,
      tax: 0,
      note: 'seed',
      isActive: true,
      voidedAt: null,
      createdAt: '2026-03-18T00:00:00Z',
      updatedAt: '2026-03-19T00:00:00Z',
    });
    deleteTrade.mockResolvedValue({ deleted: 1 });
    createCashLedger.mockResolvedValue({ id: 1 });
    deleteCashLedger.mockResolvedValue({ deleted: 1 });
    createCorporateAction.mockResolvedValue({ id: 1 });
    deleteCorporateAction.mockResolvedValue({ deleted: 1 });
    parseCsvImport.mockResolvedValue({
      broker: 'huatai',
      recordCount: 0,
      skippedCount: 0,
      errorCount: 0,
      records: [],
      cashRecordCount: 0,
      cashEntries: [],
      corporateActionCount: 0,
      corporateActions: [],
      warnings: [],
      metadata: {},
      errors: [],
    });
    commitCsvImport.mockResolvedValue({
      accountId: 1,
      recordCount: 0,
      insertedCount: 0,
      duplicateCount: 0,
      failedCount: 0,
      cashRecordCount: 0,
      cashInsertedCount: 0,
      cashFailedCount: 0,
      corporateActionCount: 0,
      corporateActionInsertedCount: 0,
      corporateActionFailedCount: 0,
      dryRun: true,
      duplicateImport: false,
      warnings: [],
      metadata: {},
      errors: [],
    });
    createAccount.mockResolvedValue({ id: 1 });
    deleteAccount.mockResolvedValue({
      ok: true,
      deletedAccountId: 1,
      deleteMode: 'soft',
      nextAccountId: 2,
    });
  });

  it('renders stale FX status with a manual refresh button', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();

    const workspace = screen.getByTestId('portfolio-workspace-grid');
    expect(workspace.parentElement).toHaveClass('max-w-[1880px]', 'px-4', 'sm:px-6', 'lg:px-8', '2xl:px-10');
    expect(workspace).toHaveClass('grid', 'grid-cols-12', 'items-start', 'gap-4', 'xl:gap-5');
    expect(screen.getByTestId('portfolio-bento-page')).toHaveAttribute('data-bento-surface', 'true');
    expect(screen.getByTestId('portfolio-bento-page')).toHaveClass('w-full', 'flex-1', 'min-w-0', 'flex', 'flex-col', 'gap-6', 'min-h-0');
    expect(screen.getByTestId('portfolio-bento-page')).not.toHaveClass('px-6', 'md:px-8', 'xl:px-12', 'pt-6', 'pb-12', 'overflow-y-auto', 'no-scrollbar');
    expect(screen.getByTestId('portfolio-bento-page')).not.toHaveClass('max-w-[1920px]', 'mx-auto', 'px-4', 'py-2');
    expect(screen.queryByTestId('portfolio-bento-hero')).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-total-assets-card')).toHaveClass('col-span-12');
    expect(screen.getByRole('heading', { name: '总资产 Total Assets' })).toBeInTheDocument();
    expect(screen.getByTestId('portfolio-total-assets-value')).toHaveStyle({ textShadow: '0 0 30px rgba(52, 211, 153, 0.4)' });
    expect(within(screen.getByTestId('portfolio-total-assets-card')).queryByLabelText('DISPLAY CURRENCY')).not.toBeInTheDocument();
    expect(within(screen.getByTestId('portfolio-total-assets-card')).getByTestId('portfolio-display-currency-status')).toHaveTextContent('显示货币 CNY');
    expect(within(screen.getByTestId('portfolio-total-assets-card')).getByRole('link', { name: /在设置中修改/ })).toHaveAttribute('href', '/zh/settings');
    expect(within(screen.getByTestId('portfolio-total-assets-card')).getByTestId('portfolio-currency-breakdown')).toHaveTextContent('按币种：暂无资产');
    expect(within(screen.getByTestId('portfolio-total-assets-card')).getByText(translate('zh', 'portfolio.totalCash'))).toBeInTheDocument();
    expect(within(screen.getByTestId('portfolio-total-assets-card')).getByText(translate('zh', 'portfolio.totalMarketValue'))).toBeInTheDocument();
    expect(within(screen.getByTestId('portfolio-total-assets-card')).getByText(translate('zh', 'portfolio.positionUnrealized'))).toBeInTheDocument();
    expect(await screen.findByText(translate('zh', 'portfolio.fxStale'))).toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('zh', 'portfolio.refreshFx') })).toBeInTheDocument();
    const submitTradeButton = screen.getByRole('button', { name: translate('zh', 'portfolio.submitTrade') });
    expect(submitTradeButton).toHaveAttribute('type', 'submit');
    expect(submitTradeButton).not.toHaveAttribute('data-variant');
    expect(submitTradeButton.className).toContain('from-blue-600');
    expect(submitTradeButton.className).toContain('to-purple-600');
    expect(submitTradeButton.className).toContain('text-white');
    expect(submitTradeButton.className).toContain('font-medium');
    expect(submitTradeButton.className).toContain('py-2.5');
    expect(submitTradeButton.className).toContain('shadow-[0_0_15px_rgba(139,92,246,0.3)]');
    expect(screen.queryByText(translate('zh', 'portfolio.scopeHint'))).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '交易' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '账户' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '同步' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '汇率' })).toBeInTheDocument();
    expect(screen.getByTestId('portfolio-left-tab-switcher').className).toContain('bg-white/[0.05]');
    expect(screen.getByRole('button', { name: '交易' }).className).toContain('bg-white/10');
    expect(screen.getByRole('button', { name: '账户' }).className).not.toContain('border-white');
    expect(screen.queryByRole('heading', { name: /Current Holdings/i })).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-start-card')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '历史记录 ↗' })).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-recent-activity')).toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-history-full')).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: translate('zh', 'portfolio.costFutuDiluted') })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: translate('zh', 'portfolio.costThsPnl') })).toBeInTheDocument();
    const accountSelect = screen.getByLabelText('TRADE ACCOUNT') as HTMLSelectElement;
    const costMethodSelect = screen.getByLabelText('COST METHOD') as HTMLSelectElement;
    expect(accountSelect).toHaveClass('select-surface', 'absolute', 'inset-0', 'opacity-0');
    expect(accountSelect.closest('.select-field__control')).toHaveClass('ui-control-shell', 'relative', 'min-w-0', 'w-full');
    expect(accountSelect.closest('.select-field__control')?.querySelector('.select-field__overlay')).toHaveAttribute('aria-hidden', 'true');
    expect(accountSelect.closest('.select-field__control')?.querySelector('.select-field__value')).toHaveTextContent('Main');
    expect(accountSelect.closest('.select-field__control')?.querySelector('.select-field__icon')).toHaveClass('ml-2', 'shrink-0');
    expect(within(accountSelect).getByRole('option', { name: translate('zh', 'portfolio.allAccounts') })).toBeInTheDocument();
    expect(costMethodSelect).toHaveClass('select-surface', 'absolute', 'inset-0', 'opacity-0');
    expect(costMethodSelect.closest('.select-field__control')).toHaveClass('ui-control-shell', 'relative', 'min-w-0', 'w-full');
    expect(costMethodSelect.closest('.select-field__control')?.querySelector('.select-field__overlay')).toHaveAttribute('aria-hidden', 'true');
    expect(costMethodSelect.closest('.select-field__control')?.querySelector('.select-field__value')).toHaveTextContent(translate('zh', 'portfolio.costFifo'));
    expect(within(costMethodSelect).getByRole('option', { name: translate('zh', 'portfolio.costFifo') })).toBeInTheDocument();
    const totalAssetsCard = screen.getByTestId('portfolio-total-assets-card');
    const holdingsPanel = screen.getByTestId('portfolio-empty-workflow-column');
    const tradeStationSection = screen.getByRole('heading', { name: 'Trade Station' }).closest('section');
    expect(Boolean(totalAssetsCard.compareDocumentPosition(tradeStationSection as Element) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(totalAssetsCard.compareDocumentPosition(holdingsPanel) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(holdingsPanel.compareDocumentPosition(tradeStationSection as Element) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it('renders the mobile empty portfolio order as hero, start, recent activity, trade station', async () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 390 });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const totalAssetsCard = screen.getByTestId('portfolio-total-assets-card');
    const startCard = screen.getByTestId('portfolio-start-card');
    const recentActivity = screen.getByTestId('portfolio-recent-activity');
    const tradeStationSection = screen.getByRole('heading', { name: 'Trade Station' }).closest('section') as HTMLElement;

    expect(Boolean(totalAssetsCard.compareDocumentPosition(startCard) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(startCard.compareDocumentPosition(recentActivity) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(recentActivity.compareDocumentPosition(tradeStationSection) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(screen.queryByTestId('portfolio-history-full')).not.toBeInTheDocument();
  });

  it('renders empty portfolio start card and recent activity in the same workflow column for small history', async () => {
    listTrades.mockResolvedValueOnce({
      items: [
        { id: 7, accountId: 1, symbol: 'AAPL', market: 'us', tradeDate: '2026-03-18', side: 'buy', quantity: 1, price: 100, fee: 0, tax: 0, currency: 'USD', createdAt: '2026-03-18T00:00:00Z' },
      ],
      total: 1,
      page: 1,
      pageSize: 20,
    });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(screen.queryByTestId('portfolio-current-holdings-panel')).not.toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-history-full')).not.toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-history-panel')).not.toBeInTheDocument();
    const workflowColumn = screen.getByTestId('portfolio-empty-workflow-column');
    const startCard = screen.getByTestId('portfolio-start-card');
    const recentActivity = screen.getByTestId('portfolio-recent-activity');
    expect(workflowColumn).toContainElement(startCard);
    expect(workflowColumn).toContainElement(recentActivity);
    expect(workflowColumn).toHaveClass('space-y-4');
    expect(startCard).toHaveClass('xl:col-span-7');
    expect(startCard).not.toHaveClass('xl:min-h-[300px]', 'min-h-[520px]');
    expect(within(startCard).getByText('当前无持仓')).toBeInTheDocument();
    expect(within(startCard).getByText('录入第一笔买入交易后自动生成持仓')).toBeInTheDocument();
    expect(within(startCard).getByText('历史记录存在，当前无持仓')).toBeInTheDocument();
    expect(within(startCard).getByText(/active accounts/i)).toBeInTheDocument();
    expect(within(startCard).getByText(/writable accounts/i)).toBeInTheDocument();
    expect(within(startCard).getByText(/Main/)).toBeInTheDocument();
    expect(within(recentActivity).getByText('历史记录存在，当前无持仓')).toBeInTheDocument();
    expect(within(recentActivity).getByText('AAPL')).toBeInTheDocument();
    expect(within(recentActivity).getByText(/2026-03-18/)).toBeInTheDocument();

    const tradeStation = screen.getByTestId('portfolio-trade-station-card');
    expect(within(tradeStation).getByRole('button', { name: '交易' }).className).toContain('bg-white/10');
    expect(screen.getByLabelText('TRADE ACCOUNT')).toHaveValue('1');
    expect(within(tradeStation).getByRole('button', { name: translate('zh', 'portfolio.submitTrade') })).not.toBeDisabled();
  });

  it('renders compact empty recent activity when the empty portfolio has no history', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();

    const recentActivity = screen.getByTestId('portfolio-recent-activity');
    expect(within(recentActivity).getByText('暂无历史记录')).toBeInTheDocument();
    expect(recentActivity).not.toHaveClass('min-h-[300px]', 'min-h-[520px]');
    expect(screen.queryByTestId('portfolio-history-full')).not.toBeInTheDocument();
  });

  it('shows the disabled trade reason if the trade account is all accounts', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.change(screen.getByLabelText('TRADE ACCOUNT'), { target: { value: 'all' } });

    const tradeStation = screen.getByTestId('portfolio-trade-station-card');
    expect(within(tradeStation).getByText('请选择具体账户后录入交易')).toBeInTheDocument();
    expect(within(tradeStation).getByRole('button', { name: translate('zh', 'portfolio.submitTrade') })).toBeDisabled();
  });

  it('reads display currency from shared settings storage and converts totals and holdings without hiding original currency', async () => {
    window.localStorage.setItem(PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY, 'USD');
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true, fxStale: false }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(screen.queryByLabelText('DISPLAY CURRENCY')).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-display-currency-status')).toHaveTextContent('显示货币 USD');
    expect(screen.getByRole('link', { name: /在设置中修改/ })).toHaveAttribute('href', '/zh/settings');
    expect(screen.getByTestId('portfolio-total-assets-value')).toHaveTextContent('USD 414.08');
    expect(screen.getByText('≈ CNY 3,000.00')).toBeInTheDocument();
    expect(screen.getByText('USD 1,600.00')).toBeInTheDocument();
    expect(screen.queryByText('≈ USD 1,600.00')).not.toBeInTheDocument();
    expect(screen.getByText('+USD 100.00')).toBeInTheDocument();
    expect(screen.queryByText('≈ USD 100.00')).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-currency-breakdown')).toHaveTextContent('CNY 3,000.00');
  });

  it('migrates the legacy portfolio display currency key to the shared settings key', async () => {
    window.localStorage.setItem(LEGACY_PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY, 'HKD');
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true, fxStale: false }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(window.localStorage.getItem(PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY)).toBe('HKD');
    expect(screen.getByTestId('portfolio-display-currency-status')).toHaveTextContent('显示货币 HKD');
    expect(screen.getByTestId('portfolio-total-assets-value')).toHaveTextContent('HKD 3,257.33');
  });

  it('shows an FX unavailable state instead of fake converted values when a display rate is missing', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({
      includePosition: true,
      fxRates: [
        {
          fromCurrency: 'USD',
          toCurrency: 'CNY',
          rate: null,
          rateDate: null,
          source: 'missing',
          isStale: true,
          updatedAt: null,
          sourceDirection: 'missing',
        },
      ],
    }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(screen.getByText('USD 1,600.00')).toBeInTheDocument();
    expect(within(screen.getByTestId('portfolio-total-assets-card')).getAllByText('折算不可用').length).toBeGreaterThan(0);
    expect(screen.queryByText(/≈ CNY/)).not.toBeInTheDocument();
  });

  it('refreshes display FX from the portfolio refresh endpoint and reloads display data', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'portfolio.refreshFx') }));

    await waitFor(() => expect(refreshFx).toHaveBeenCalledWith({ accountId: undefined }));
    await waitFor(() => expect(getSnapshot).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(translate('zh', 'portfolio.fxRefreshUpdated', { count: 1 }))).toBeInTheDocument();
  });

  it('refreshes portfolio data after trade submit, disables duplicate submit, and shows compact feedback', async () => {
    const pendingTrade = deferredPromise<{ id: number }>();
    createTrade.mockImplementationOnce(() => pendingTrade.promise);
    getSnapshot
      .mockResolvedValueOnce(makeSnapshot({ includePosition: false }))
      .mockResolvedValueOnce(makeSnapshot({ includePosition: true }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.change(screen.getByLabelText('SYMBOL'), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText('QUANTITY'), { target: { value: '10' } });
    fireEvent.change(screen.getByLabelText('PRICE'), { target: { value: '160' } });

    const snapshotCallsBeforeSubmit = getSnapshot.mock.calls.length;
    const tradeCallsBeforeSubmit = listTrades.mock.calls.length;
    const submitButton = screen.getByRole('button', { name: translate('zh', 'portfolio.submitTrade') });
    fireEvent.click(submitButton);

    await waitFor(() => expect(submitButton).toBeDisabled());

    await act(async () => {
      pendingTrade.resolve({ id: 1 });
      await pendingTrade.promise;
    });

    await waitFor(() => expect(createTrade).toHaveBeenCalledTimes(1));
    expect(createTrade).toHaveBeenCalledWith(expect.objectContaining({ currency: 'USD' }));
    await waitFor(() => expect(getSnapshot.mock.calls.length).toBeGreaterThan(snapshotCallsBeforeSubmit));
    await waitFor(() => expect(listTrades.mock.calls.length).toBeGreaterThan(tradeCallsBeforeSubmit));
    expect(await screen.findByTestId('portfolio-trade-feedback')).toHaveTextContent('AAPL 买入已记录 · 已刷新持仓');
    expect(screen.getByLabelText('SYMBOL')).toHaveValue('');
  });

  it('infers settlement currency from US, HK, A-share, and crypto symbols with manual override', async () => {
    getAccounts.mockResolvedValueOnce(makeAccounts([
      { id: 1, name: 'US Account', market: 'us', baseCurrency: 'USD' },
      { id: 2, name: 'HK Account', market: 'hk', baseCurrency: 'HKD' },
      { id: 3, name: 'CN Account', market: 'cn', baseCurrency: 'CNY' },
    ]));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const symbolInput = screen.getByLabelText('SYMBOL');
    const settlementSelect = screen.getByLabelText('结算货币') as HTMLSelectElement;

    for (const symbol of ['AAPL', 'NVDA', 'ORCL', 'WULF']) {
      fireEvent.change(symbolInput, { target: { value: symbol } });
      await waitFor(() => expect(settlementSelect).toHaveValue('USD'));
    }

    for (const symbol of ['00700.HK', '9988.HK', 'HK:00700']) {
      fireEvent.change(symbolInput, { target: { value: symbol } });
      await waitFor(() => expect(settlementSelect).toHaveValue('HKD'));
    }

    for (const symbol of ['600519', '000001.SZ', '600000.SH', 'SH:600519', 'SZ:000001']) {
      fireEvent.change(symbolInput, { target: { value: symbol } });
      await waitFor(() => expect(settlementSelect).toHaveValue('CNY'));
    }

    fireEvent.change(symbolInput, { target: { value: 'BTCUSDT' } });
    await waitFor(() => expect(settlementSelect).toHaveValue('USD'));

    fireEvent.change(settlementSelect, { target: { value: 'JPY' } });
    expect(settlementSelect).toHaveValue('JPY');
    expect(screen.getByText('标的结算货币与账户基准币种不同，将依赖汇率折算。')).toBeInTheDocument();
  });

  it('shows compact trade errors and preserves the form when submit fails', async () => {
    createTrade.mockRejectedValueOnce(
      createApiError(
        createParsedApiError({
          title: '交易失败',
          message: '余额不足',
        }),
      ),
    );

    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.change(screen.getByLabelText('SYMBOL'), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText('QUANTITY'), { target: { value: '10' } });
    fireEvent.change(screen.getByLabelText('PRICE'), { target: { value: '160' } });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'portfolio.submitTrade') }));

    expect(await screen.findByTestId('portfolio-trade-feedback')).toHaveTextContent('余额不足');
    expect(screen.getByLabelText('SYMBOL')).toHaveValue('AAPL');
  });

  it('switches left tabs between trade, account, sync, and fx surfaces', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(screen.getByText(translate('zh', 'portfolio.manualTrade'))).toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.createAccountTitle'))).not.toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.dataSyncTitle'))).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '账户' }));
    expect(screen.getAllByText(translate('zh', 'portfolio.createAccountTitle')).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: translate('zh', 'portfolio.createAccount') })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '同步' }));
    expect(screen.getByText(translate('zh', 'portfolio.dataSyncTitle'))).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'portfolio.currentImportAccount'))).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '汇率' }));
    expect(screen.getByTestId('portfolio-fx-panel')).toBeInTheDocument();
    expect(screen.getByText('LIVE EXCHANGE ENGINE')).toBeInTheDocument();
    expect(screen.getByLabelText('Base Currency')).toHaveValue('USD');
    expect(screen.getByLabelText('Quote Currency')).toHaveValue('CNY');
    expect(screen.getByText('USD/CNY')).toBeInTheDocument();
    expect(screen.getByTestId('portfolio-fx-rate-value')).toHaveTextContent('1 USD = 7.2450 CNY');
    const refreshFxButton = openFxPanel();
    expect(refreshFxButton).toHaveAttribute('data-variant', 'primary');
    expect(refreshFxButton.className).toContain('from-blue-600');
    expect(refreshFxButton.className).toContain('to-purple-600');
    expect(refreshFxButton).toHaveTextContent(translate('zh', 'portfolio.refreshFx'));
    expect(screen.getByText('manual')).toBeInTheDocument();
  });

  it('confirms account deletion and falls back to the next active account', async () => {
    getAccounts
      .mockResolvedValueOnce(makeAccounts([{ id: 1, name: 'Main' }, { id: 2, name: 'Alt' }]))
      .mockResolvedValueOnce(makeAccounts([{ id: 2, name: 'Alt' }]));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const accountSelect = screen.getByLabelText('TRADE ACCOUNT') as HTMLSelectElement;
    fireEvent.change(accountSelect, { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: '账户' }));
    fireEvent.click(screen.getByRole('button', { name: '删除 Main' }));

    expect(await screen.findByText(translate('zh', 'portfolio.accountDeleteMessage'))).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'portfolio.deleteConfirm') }));

    await waitFor(() => expect(deleteAccount).toHaveBeenCalledWith(1));
    await waitFor(() => expect((screen.getByLabelText('TRADE ACCOUNT') as HTMLSelectElement).value).toBe('2'));
    expect(await screen.findByText(translate('zh', 'portfolio.accountArchived'))).toBeInTheDocument();
  });

  it('shows IBKR as a broker import option and surfaces account-linked connection context', async () => {
    listImportBrokers.mockResolvedValueOnce({
      brokers: [
        { broker: 'huatai', aliases: [], displayName: '华泰', fileExtensions: ['csv'] },
        { broker: 'ibkr', aliases: ['interactivebrokers'], displayName: 'Interactive Brokers', fileExtensions: ['xml'] },
      ],
    });
    listBrokerConnections.mockResolvedValue({
      connections: [
        {
          id: 9,
          portfolioAccountId: 1,
          connectionName: 'Primary IBKR',
          brokerType: 'ibkr',
          brokerAccountRef: 'U1234567',
          importMode: 'file',
          status: 'active',
          syncMetadata: {},
        },
      ],
    });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const accountSelect = screen.getByLabelText('ASSET SCOPE');
    fireEvent.change(accountSelect, { target: { value: '1' } });
    await waitFor(() => expect(getSnapshot).toHaveBeenLastCalledWith({ accountId: 1, costMethod: 'fifo' }));
    await waitFor(() => expect(listBrokerConnections).toHaveBeenCalledWith(1));
    fireEvent.click(screen.getByRole('button', { name: '同步' }));

    const brokerSelect = screen.getAllByRole('combobox').find((element) =>
      (element as HTMLSelectElement).value === 'huatai'
    ) as HTMLSelectElement;
    fireEvent.change(brokerSelect, { target: { value: 'ibkr' } });

    expect(screen.getByText(translate('zh', 'portfolio.ibkrImportHint'))).toBeInTheDocument();
    expect(screen.getByText('Primary IBKR')).toBeInTheDocument();
    expect(screen.getByDisplayValue('U1234567')).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'portfolio.currentImportAccount'))).toBeInTheDocument();
  });

  it('triggers read-only IBKR sync from the existing data sync surface', async () => {
    listImportBrokers.mockResolvedValueOnce({
      brokers: [
        { broker: 'huatai', aliases: [], displayName: '华泰', fileExtensions: ['csv'] },
        { broker: 'ibkr', aliases: ['interactivebrokers'], displayName: 'Interactive Brokers', fileExtensions: ['xml'] },
      ],
    });
    listBrokerConnections.mockResolvedValue({
      connections: [
        {
          id: 9,
          portfolioAccountId: 1,
          connectionName: 'Primary IBKR',
          brokerType: 'ibkr',
          brokerAccountRef: 'U1234567',
          importMode: 'file',
          status: 'active',
          syncMetadata: {
            ibkrApi: {
              apiBaseUrl: 'https://localhost:5000/v1/api',
              verifySsl: false,
              brokerAccountRef: 'U1234567',
            },
          },
        },
      ],
    });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const accountSelect = screen.getByLabelText('ASSET SCOPE');
    fireEvent.change(accountSelect, { target: { value: '1' } });
    await waitFor(() => expect(listBrokerConnections).toHaveBeenCalledWith(1));
    fireEvent.click(screen.getByRole('button', { name: '同步' }));

    const brokerSelect = screen.getAllByRole('combobox').find((element) =>
      (element as HTMLSelectElement).value === 'huatai'
    ) as HTMLSelectElement;
    fireEvent.change(brokerSelect, { target: { value: 'ibkr' } });

    fireEvent.change(
      screen.getByPlaceholderText(translate('zh', 'portfolio.ibkrSessionTokenPlaceholder')),
      { target: { value: 'session-token-123' } },
    );
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'portfolio.syncIbkr') }));

    await waitFor(() => expect(syncIbkrReadOnly).toHaveBeenCalledWith({
      accountId: 1,
      brokerConnectionId: 9,
      brokerAccountRef: 'U1234567',
      sessionToken: 'session-token-123',
      apiBaseUrl: 'https://localhost:5000/v1/api',
      verifySsl: false,
    }));
    expect(await screen.findByText(translate('zh', 'portfolio.syncResult'))).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'portfolio.syncResult')).closest('div')).toHaveTextContent(`${translate('zh', 'portfolio.positionsCountLabel')} 1`);
  });

  it('keeps the IBKR sync result visible after metadata refresh and preserves the broker selector', async () => {
    const initialSnapshot = makeSnapshot({ accountId: 1, fxStale: true });
    const syncedSnapshot = {
      ...makeSnapshot({ accountId: 1, fxStale: false }),
      currency: 'USD',
      totalCash: 5000,
      totalMarketValue: 1600,
      totalEquity: 6600,
      unrealizedPnl: 100,
      fxStale: false,
      accounts: [
        {
          accountId: 1,
          accountName: 'Account 1',
          ownerId: null,
          broker: 'IBKR',
          market: 'us',
          baseCurrency: 'USD',
          asOf: '2026-03-19',
          costMethod: 'fifo' as const,
          totalCash: 5000,
          totalMarketValue: 1600,
          totalEquity: 6600,
          realizedPnl: 0,
          unrealizedPnl: 100,
          feeTotal: 0,
          taxTotal: 0,
          fxStale: false,
          positions: [
            {
              symbol: 'AAPL',
              market: 'us',
              currency: 'USD',
              quantity: 10,
              avgCost: 150,
              totalCost: 1500,
              lastPrice: 160,
              marketValueBase: 1600,
              unrealizedPnlBase: 100,
              valuationCurrency: 'USD',
            },
          ],
        },
      ],
    };

    getSnapshot
      .mockResolvedValueOnce(initialSnapshot)
      .mockResolvedValueOnce(initialSnapshot)
      .mockResolvedValueOnce(syncedSnapshot);
    listImportBrokers.mockResolvedValueOnce({
      brokers: [
        { broker: 'huatai', aliases: [], displayName: '华泰', fileExtensions: ['csv'] },
        { broker: 'ibkr', aliases: ['interactivebrokers'], displayName: 'Interactive Brokers', fileExtensions: ['xml'] },
      ],
    });
    listBrokerConnections
      .mockResolvedValueOnce({
        connections: [
          {
            id: 9,
            portfolioAccountId: 1,
            connectionName: 'Primary IBKR',
            brokerType: 'ibkr',
            brokerAccountRef: 'U1234567',
            importMode: 'file',
            status: 'active',
            syncMetadata: {
              ibkrApi: {
                apiBaseUrl: 'https://localhost:5000/v1/api',
                verifySsl: false,
                brokerAccountRef: 'U1234567',
              },
            },
          },
        ],
      })
      .mockResolvedValueOnce({
        connections: [
          {
            id: 9,
            portfolioAccountId: 1,
            connectionName: 'Primary IBKR',
            brokerType: 'ibkr',
            brokerAccountRef: 'U1234567',
            importMode: 'api',
            status: 'active',
            syncMetadata: {
              ibkrApi: {
                apiBaseUrl: 'https://localhost:5000/v1/api',
                verifySsl: false,
                brokerAccountRef: 'U1234567',
              },
              lastSyncAt: '2026-03-19T10:00:00',
            },
          },
        ],
      });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const accountSelect = screen.getByLabelText('ASSET SCOPE');
    fireEvent.change(accountSelect, { target: { value: '1' } });
    await waitFor(() => expect(listBrokerConnections).toHaveBeenCalledWith(1));
    fireEvent.click(screen.getByRole('button', { name: '同步' }));

    const brokerSelect = screen.getAllByRole('combobox').find((element) =>
      (element as HTMLSelectElement).value === 'huatai'
    ) as HTMLSelectElement;
    fireEvent.change(brokerSelect, { target: { value: 'ibkr' } });
    fireEvent.change(
      screen.getByPlaceholderText(translate('zh', 'portfolio.ibkrSessionTokenPlaceholder')),
      { target: { value: 'session-token-123' } },
    );

    const brokerConnectionCallCount = listBrokerConnections.mock.calls.length;
    const snapshotCallCount = getSnapshot.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'portfolio.syncIbkr') }));

    await waitFor(() => expect(syncIbkrReadOnly).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(listBrokerConnections.mock.calls.length).toBeGreaterThan(brokerConnectionCallCount));
    await waitFor(() => expect(getSnapshot.mock.calls.length).toBeGreaterThan(snapshotCallCount));

    expect(await screen.findByText(translate('zh', 'portfolio.syncResult'))).toBeInTheDocument();
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(brokerSelect.value).toBe('ibkr');
    const syncResultCard = screen.getByText(translate('zh', 'portfolio.syncResult')).closest('div');
    expect(syncResultCard?.textContent || '').toContain(`${translate('zh', 'portfolio.positionsCountLabel')} 1`);
    expect(syncResultCard?.textContent || '').toContain(`${translate('zh', 'portfolio.cashCurrenciesLabel')} 1`);
    expect(syncResultCard?.textContent || '').toContain('USD 6,600.00');
  });

  it('refreshes FX for a single selected account and only reloads snapshot/risk', async () => {
    getSnapshot
      .mockResolvedValueOnce(makeSnapshot({ fxStale: true }))
      .mockResolvedValueOnce(makeSnapshot({ accountId: 1, fxStale: true }))
      .mockResolvedValueOnce(makeSnapshot({ accountId: 1, fxStale: false }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const accountSelect = screen.getByLabelText('ASSET SCOPE');
    fireEvent.change(accountSelect, { target: { value: '1' } });

    await waitFor(() => {
      expect(getSnapshot).toHaveBeenLastCalledWith({ accountId: 1, costMethod: 'fifo' });
    });

    const snapshotCallsBeforeRefresh = getSnapshot.mock.calls.length;
    const riskCallsBeforeRefresh = getRisk.mock.calls.length;
    const tradeCallsBeforeRefresh = listTrades.mock.calls.length;

    const refreshFxButton = openFxPanel();
    await waitFor(() => expect(refreshFxButton).not.toBeDisabled());
    fireEvent.click(refreshFxButton);

    await waitFor(() => expect(refreshFxRate).toHaveBeenCalledWith({ base: 'USD', quote: 'CNY' }));
    expect(await screen.findByText(translate('zh', 'portfolio.fxRefreshUpdated', { count: 1 }))).toBeInTheDocument();
    await waitFor(() => expect(getSnapshot).toHaveBeenCalledTimes(snapshotCallsBeforeRefresh + 1));
    await waitFor(() => expect(getRisk).toHaveBeenCalledTimes(riskCallsBeforeRefresh + 1));
    expect(listTrades).toHaveBeenCalledTimes(tradeCallsBeforeRefresh);
    expect(listCashLedger).not.toHaveBeenCalled();
    expect(listCorporateActions).not.toHaveBeenCalled();
    expect(screen.getAllByText(translate('zh', 'portfolio.fxFresh')).length).toBeGreaterThan(0);
  });

  it('shows warning feedback when live FX refresh falls back to stale cache', async () => {
    refreshFxRate.mockResolvedValueOnce({
      baseCurrency: 'USD',
      quoteCurrency: 'CNY',
      rate: 7.2,
      provider: 'frankfurter',
      fetchedAt: '2026-03-19T10:05:00',
      cacheHit: true,
      stale: true,
      error: 'network down',
    });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.click(openFxPanel());

    expect(await screen.findByText(translate('zh', 'portfolio.fxRefreshFallbackWarning', {
      updatedCount: 0,
      staleCount: 1,
      errorCount: 1,
    }))).toBeInTheDocument();
    expect(screen.getByText('CACHE')).toBeInTheDocument();
  });

  it('restores the button state and shows the existing error alert when FX refresh fails', async () => {
    refreshFxRate.mockRejectedValueOnce(
      createApiError(
        createParsedApiError({
          title: '刷新失败',
          message: '汇率服务暂时不可用',
        }),
      ),
    );

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const refreshButton = openFxPanel();
    fireEvent.click(refreshButton);

    expect(await screen.findByRole('alert')).toHaveTextContent('刷新失败');
    expect(screen.getByRole('alert')).toHaveTextContent('汇率服务暂时不可用');
    await waitFor(() => expect(openFxPanel()).not.toBeDisabled());
  });

  it('does not keep success feedback when snapshot reload fails after FX refresh succeeds', async () => {
    getSnapshot
      .mockResolvedValueOnce(makeSnapshot({ fxStale: true }))
      .mockRejectedValueOnce(
        createApiError(
          createParsedApiError({
            title: '快照刷新失败',
            message: '无法加载最新持仓快照',
          }),
        ),
      );

    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.click(openFxPanel());

    expect(await screen.findByRole('alert')).toHaveTextContent('快照刷新失败');
    expect(screen.getByRole('alert')).toHaveTextContent('无法加载最新持仓快照');
    await waitFor(() => expect(screen.queryByText(translate('zh', 'portfolio.fxRefreshUpdated', { count: 1 }))).not.toBeInTheDocument());
    await waitFor(() => expect(openFxPanel()).not.toBeDisabled());
  });

  it('drops late FX refresh results after switching to another account scope', async () => {
    getAccounts.mockResolvedValueOnce(makeAccounts([{ id: 1, name: 'Main' }, { id: 2, name: 'Alt' }]));
    getSnapshot.mockImplementation(async ({ accountId }: { accountId?: number } = {}) => {
      if (accountId === 2) {
        return makeSnapshot({ accountId: 2, fxStale: false });
      }
      return makeSnapshot({ accountId: accountId ?? 1, fxStale: true, accountCount: accountId ? 1 : 2 });
    });

    const pendingRefresh = deferredPromise<{
      asOf: string;
      accountCount: number;
      pairCount: number;
      updatedCount: number;
      staleCount: number;
      errorCount: number;
    }>();
    refreshFxRate.mockImplementationOnce(() => pendingRefresh.promise);

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const accountSelect = screen.getByLabelText('ASSET SCOPE');
    fireEvent.change(accountSelect, { target: { value: '1' } });
    await waitFor(() => expect(getSnapshot).toHaveBeenLastCalledWith({ accountId: 1, costMethod: 'fifo' }));

    fireEvent.click(openFxPanel());
    await waitFor(() => {
      expect(refreshFxRate).toHaveBeenCalledWith({ base: 'USD', quote: 'CNY' });
    });

    fireEvent.change(accountSelect, { target: { value: '2' } });
    await waitFor(() => expect(getSnapshot).toHaveBeenLastCalledWith({ accountId: 2, costMethod: 'fifo' }));
    await waitFor(() => expect(openFxPanel()).not.toBeDisabled());

    const snapshotCallsAfterSwitch = getSnapshot.mock.calls.length;
    const riskCallsAfterSwitch = getRisk.mock.calls.length;

    await act(async () => {
      pendingRefresh.resolve({
        asOf: '2026-03-19',
        accountCount: 1,
        pairCount: 1,
        updatedCount: 1,
        staleCount: 0,
        errorCount: 0,
      });
      await pendingRefresh.promise;
    });

    expect(getSnapshot).toHaveBeenCalledTimes(snapshotCallsAfterSwitch);
    expect(getRisk).toHaveBeenCalledTimes(riskCallsAfterSwitch);
    expect(screen.queryByText(translate('zh', 'portfolio.fxRefreshUpdated', { count: 1 }))).not.toBeInTheDocument();
  });

  it('drops late FX refresh results after switching cost method', async () => {
    const pendingRefresh = deferredPromise<{
      asOf: string;
      accountCount: number;
      pairCount: number;
      updatedCount: number;
      staleCount: number;
      errorCount: number;
    }>();
    refreshFxRate.mockImplementationOnce(() => pendingRefresh.promise);

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const costMethodSelect = screen.getByLabelText('COST METHOD');

    fireEvent.click(openFxPanel());
    expect(await screen.findByRole('button', { name: translate('zh', 'portfolio.refreshingFx') })).toBeDisabled();

    fireEvent.change(costMethodSelect, { target: { value: 'avg' } });
    await waitFor(() => expect(getSnapshot).toHaveBeenLastCalledWith({ accountId: undefined, costMethod: 'avg' }));
    await waitFor(() => expect(openFxPanel()).not.toBeDisabled());

    const snapshotCallsAfterSwitch = getSnapshot.mock.calls.length;
    const riskCallsAfterSwitch = getRisk.mock.calls.length;

    await act(async () => {
      pendingRefresh.resolve({
        asOf: '2026-03-19',
        accountCount: 1,
        pairCount: 1,
        updatedCount: 1,
        staleCount: 0,
        errorCount: 0,
      });
      await pendingRefresh.promise;
    });

    expect(getSnapshot).toHaveBeenCalledTimes(snapshotCallsAfterSwitch);
    expect(getRisk).toHaveBeenCalledTimes(riskCallsAfterSwitch);
    expect(screen.queryByText(translate('zh', 'portfolio.fxRefreshUpdated', { count: 1 }))).not.toBeInTheDocument();
  });

  it('renders localized English portfolio shell copy on /en routes', async () => {
    window.history.replaceState(window.history.state, '', '/en/portfolio');

    render(
      <UiLanguageProvider>
        <PortfolioPage />
      </UiLanguageProvider>,
    );

    await waitForInitialLoad();

    expect(screen.getByRole('heading', { name: '总资产 Total Assets' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Trade' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Account' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sync' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Current Holdings/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'History ↗' })).not.toBeInTheDocument();
    expect(screen.getByText('No current holdings')).toBeInTheDocument();
    expect(openFxPanel('en')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Sync' }));
    expect(screen.getByText(translate('en', 'portfolio.dataSyncTitle'))).toBeInTheDocument();
  });

  it('renders localized English FX refresh feedback on /en routes', async () => {
    window.history.replaceState(window.history.state, '', '/en/portfolio');

    render(
      <UiLanguageProvider>
        <PortfolioPage />
      </UiLanguageProvider>,
    );

    await waitForInitialLoad();

    fireEvent.click(openFxPanel('en'));

    expect(await screen.findByText(translate('en', 'portfolio.fxRefreshUpdated', { count: 1 }))).toBeInTheDocument();
  });

  it('renders localized English IBKR sync detail and broker connection labels on /en routes', async () => {
    window.history.replaceState(window.history.state, '', '/en/portfolio');
    listImportBrokers.mockResolvedValueOnce({
      brokers: [
        { broker: 'huatai', aliases: [], displayName: 'Huatai', fileExtensions: ['csv'] },
        { broker: 'ibkr', aliases: ['interactivebrokers'], displayName: 'Interactive Brokers', fileExtensions: ['xml'] },
      ],
    });
    listBrokerConnections.mockResolvedValueOnce({
      connections: [
        {
          id: 9,
          portfolioAccountId: 1,
          connectionName: 'Primary IBKR',
          brokerType: 'ibkr',
          brokerAccountRef: 'U1234567',
          importMode: 'api',
          status: 'active',
          syncMetadata: {
            ibkrApi: {
              apiBaseUrl: 'https://localhost:5000/v1/api',
              verifySsl: false,
              brokerAccountRef: 'U1234567',
            },
          },
        },
      ],
    });

    render(
      <UiLanguageProvider>
        <PortfolioPage />
      </UiLanguageProvider>,
    );

    await waitForInitialLoad();

    fireEvent.change(screen.getByLabelText('TRADE ACCOUNT'), { target: { value: '1' } });
    await waitFor(() => expect(listBrokerConnections).toHaveBeenCalledWith(1));
    fireEvent.click(screen.getByRole('button', { name: 'Sync' }));
    fireEvent.change(
      screen.getAllByRole('combobox').find((element) => (element as HTMLSelectElement).value === 'huatai') as HTMLSelectElement,
      { target: { value: 'ibkr' } },
    );
    fireEvent.change(screen.getByPlaceholderText(translate('en', 'portfolio.ibkrSessionTokenPlaceholder')), {
      target: { value: 'session-token-123' },
    });
    fireEvent.click(screen.getByRole('button', { name: translate('en', 'portfolio.syncIbkr') }));

    await waitFor(() => expect(syncIbkrReadOnly).toHaveBeenCalled());
    expect(await screen.findByText(translate('en', 'portfolio.readOnlyBadge'))).toBeInTheDocument();
    expect(screen.getByText(translate('en', 'portfolio.ibkrImportHint'))).toBeInTheDocument();
    expect(screen.getByText(translate('en', 'portfolio.syncResult'))).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes(translate('en', 'portfolio.positionsCountLabel')))).toBeInTheDocument();
  });

  it('keeps zh IBKR sync detail labels localized on default routes', async () => {
    listImportBrokers.mockResolvedValueOnce({
      brokers: [
        { broker: 'huatai', aliases: [], displayName: '华泰', fileExtensions: ['csv'] },
        { broker: 'ibkr', aliases: ['interactivebrokers'], displayName: 'Interactive Brokers', fileExtensions: ['xml'] },
      ],
    });
    listBrokerConnections.mockResolvedValueOnce({
      connections: [
        {
          id: 9,
          portfolioAccountId: 1,
          connectionName: 'Primary IBKR',
          brokerType: 'ibkr',
          brokerAccountRef: 'U1234567',
          importMode: 'api',
          status: 'active',
          syncMetadata: {
            ibkrApi: {
              apiBaseUrl: 'https://localhost:5000/v1/api',
              verifySsl: false,
              brokerAccountRef: 'U1234567',
            },
          },
        },
      ],
    });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.change(screen.getByLabelText('TRADE ACCOUNT'), { target: { value: '1' } });
    await waitFor(() => expect(listBrokerConnections).toHaveBeenCalledWith(1));
    fireEvent.click(screen.getByRole('button', { name: '同步' }));
    fireEvent.change(
      screen.getAllByRole('combobox').find((element) => (element as HTMLSelectElement).value === 'huatai') as HTMLSelectElement,
      { target: { value: 'ibkr' } },
    );
    fireEvent.change(screen.getByPlaceholderText(translate('zh', 'portfolio.ibkrSessionTokenPlaceholder')), {
      target: { value: 'session-token-123' },
    });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'portfolio.syncIbkr') }));

    await waitFor(() => expect(syncIbkrReadOnly).toHaveBeenCalled());
    expect(await screen.findByText(translate('zh', 'portfolio.readOnlyBadge'))).toBeInTheDocument();
    expect(await screen.findByText(translate('zh', 'portfolio.syncResult'))).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'portfolio.syncResult')).closest('div')).toHaveTextContent(`${translate('zh', 'portfolio.positionsCountLabel')} 1`);
    expect(screen.queryByText(translate('en', 'portfolio.readOnlyBadge'))).not.toBeInTheDocument();
  });

  it('renders the rebuilt two-column portfolio shell without the legacy attribution dashboard', async () => {
    const { container } = render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(container.querySelectorAll('main')).toHaveLength(0);
    expect(screen.queryByTestId('portfolio-attribution-dashboard')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Trade Station' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /Current Holdings/i })).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-start-card')).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'portfolio.manualTrade'))).toBeInTheDocument();
    expect(screen.getByText('当前无持仓')).toBeInTheDocument();
  });

  it('locks the portfolio viewport and only renders one trade form at a time', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();

    const pageShell = screen.getByTestId('portfolio-bento-page');
    expect(pageShell.className).toContain('min-h-0');
    expect(pageShell.className).toContain('flex');
    expect(pageShell.className).toContain('flex-col');
    expect(pageShell.className).toContain('bg-transparent');
    expect(pageShell).not.toHaveClass('h-full', 'overflow-y-auto', 'px-6', 'pt-6', 'pb-12');

    const scrollContainer = screen.getByTestId('portfolio-trade-station-scroll');
    expect(scrollContainer.className).toContain('min-h-0');
    expect(scrollContainer.className).toContain('overflow-y-auto');
    expect(scrollContainer.className).toContain('no-scrollbar');
    expect(scrollContainer.className).toContain('pt-4');

    const totalAssetsCard = screen.getByTestId('portfolio-total-assets-card');
    expect(totalAssetsCard.className).toContain('shrink-0');
    expect(totalAssetsCard.className).toContain('rounded-xl');
    expect(totalAssetsCard.className).toContain('border-white/5');

    const summaryBlock = screen.getByTestId('portfolio-trade-station-summary');
    expect(summaryBlock.className).toContain('flex');
    expect(summaryBlock.className).toContain('flex-col');
    expect(summaryBlock.className).toContain('gap-1');
    expect(summaryBlock.className).toContain('py-2');

    expect(screen.getByRole('button', { name: '股票买卖' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '资金划转' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: '公司行为' }).length).toBeGreaterThan(0);
    expect(screen.getByText(translate('zh', 'portfolio.manualTrade'))).toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.manualCash'))).not.toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.manualCorporate'))).not.toBeInTheDocument();
    expect(screen.getByLabelText('SYMBOL')).toHaveClass('rounded-lg');

    fireEvent.click(screen.getByRole('button', { name: '资金划转' }));
    expect(screen.getByText(translate('zh', 'portfolio.manualCash'))).toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.manualTrade'))).not.toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.manualCorporate'))).not.toBeInTheDocument();

    const cashAmountCurrencyGrid = screen.getByTestId('portfolio-cash-amount-currency-grid');
    expect(cashAmountCurrencyGrid.className).toContain('grid');
    expect(cashAmountCurrencyGrid.className).toContain('grid-cols-1');
    expect(cashAmountCurrencyGrid.className).toContain('sm:grid-cols-2');
    expect(cashAmountCurrencyGrid.className).toContain('gap-x-4');
    expect(cashAmountCurrencyGrid.className).toContain('gap-y-4');

    const cashCurrencySelect = screen.getByTestId('portfolio-cash-currency-select');
    expect(cashCurrencySelect.tagName).toBe('SELECT');
    expect(cashCurrencySelect.className).toContain('select-surface');

    const amountInput = screen.getByLabelText('AMOUNT');
    expect(amountInput.className).toContain('input-surface');
    expect(amountInput.className).toContain('rounded-lg');

    fireEvent.click(within(screen.getByTestId('portfolio-trade-type-switcher')).getByRole('button', { name: '公司行为' }));
    expect(screen.getByText(translate('zh', 'portfolio.manualCorporate'))).toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.manualTrade'))).not.toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.manualCash'))).not.toBeInTheDocument();
  });

  it('renders the full-width order history panel and shows event filters', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const historyPanel = screen.getByTestId('portfolio-history-full');
    expect(historyPanel).toHaveClass('col-span-12');
    expect(within(historyPanel).getByRole('heading', { name: '历史记录' })).toBeInTheDocument();
    expect(within(historyPanel).getByRole('button', { name: translate('zh', 'portfolio.tradeLedger') })).toBeInTheDocument();
    expect(within(historyPanel).getByRole('button', { name: translate('zh', 'portfolio.cashLedger') })).toBeInTheDocument();
    expect(within(historyPanel).getByRole('button', { name: translate('zh', 'portfolio.corporateLedger') })).toBeInTheDocument();
    expect(within(historyPanel).getByRole('button', { name: translate('zh', 'portfolio.refreshLedger') })).toBeInTheDocument();
  });

  it('renders trade history actions while non-trade ledgers do not expose edit actions', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true }));
    listTrades.mockResolvedValueOnce({
      items: [
        {
          id: 7,
          accountId: 1,
          symbol: 'AAPL',
          market: 'us',
          tradeDate: '2026-03-18',
          side: 'buy',
          quantity: 1,
          price: 100,
          fee: 0,
          tax: 0,
          currency: 'USD',
          note: 'seed',
          isActive: true,
          voidedAt: null,
          createdAt: '2026-03-18T00:00:00Z',
          updatedAt: '2026-03-18T00:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      pageSize: 20,
    });
    listCashLedger.mockResolvedValueOnce({
      items: [
        { id: 3, accountId: 1, eventDate: '2026-03-17', direction: 'in', amount: 1000, currency: 'USD', note: 'seed', createdAt: '2026-03-17T00:00:00Z' },
      ],
      total: 1,
      page: 1,
      pageSize: 20,
    });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const historyPanel = screen.getByTestId('portfolio-history-full');
    expect(within(historyPanel).getByRole('button', { name: '编辑' })).toBeInTheDocument();
    expect(within(historyPanel).getByRole('button', { name: '作废' })).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: translate('zh', 'portfolio.cashLedger') })[0]);
    await waitFor(() => expect(listCashLedger).toHaveBeenCalled());
    expect(within(historyPanel).queryByRole('button', { name: '编辑' })).not.toBeInTheDocument();
  });

  it('opens the edit drawer with prefilled trade values and updates the trade successfully', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true }));
    listTrades.mockResolvedValue({
      items: [
        {
          id: 7,
          accountId: 1,
          symbol: 'AAPL',
          market: 'us',
          tradeDate: '2026-03-18',
          side: 'buy',
          quantity: 1,
          price: 100,
          fee: 0,
          tax: 0,
          currency: 'USD',
          note: 'seed',
          isActive: true,
          voidedAt: null,
          createdAt: '2026-03-18T00:00:00Z',
          updatedAt: '2026-03-18T00:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      pageSize: 20,
    });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.click(screen.getByRole('button', { name: '编辑' }));

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByDisplayValue('AAPL')).toBeInTheDocument();
    expect(within(dialog).getByDisplayValue('2026-03-18')).toBeInTheDocument();
    expect(within(dialog).getByDisplayValue('USD')).toBeInTheDocument();

    fireEvent.change(within(dialog).getByLabelText('QUANTITY'), { target: { value: '2' } });
    fireEvent.change(within(dialog).getByLabelText('PRICE'), { target: { value: '101' } });
    fireEvent.click(within(dialog).getByRole('button', { name: '保存修改' }));

    await waitFor(() => expect(updateTrade).toHaveBeenCalledWith(7, expect.objectContaining({
      quantity: 2,
      price: 101,
    })));
    await waitFor(() => expect(getSnapshot).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('交易已更新 · 持仓已刷新')).toBeInTheDocument();
  });

  it('keeps the edit drawer open when trade update fails', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true }));
    listTrades.mockResolvedValue({
      items: [
        {
          id: 7,
          accountId: 1,
          symbol: 'AAPL',
          market: 'us',
          tradeDate: '2026-03-18',
          side: 'buy',
          quantity: 1,
          price: 100,
          fee: 0,
          tax: 0,
          currency: 'USD',
          note: 'seed',
          isActive: true,
          voidedAt: null,
          createdAt: '2026-03-18T00:00:00Z',
          updatedAt: '2026-03-18T00:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      pageSize: 20,
    });
    updateTrade.mockRejectedValueOnce(
      createApiError(
        createParsedApiError({
          title: '更新失败',
          message: '无法保存修改',
        }),
      ),
    );

    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.click(screen.getByRole('button', { name: '编辑' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('QUANTITY'), { target: { value: '2' } });
    fireEvent.click(within(dialog).getByRole('button', { name: '保存修改' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('更新失败');
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(within(screen.getByRole('dialog')).getByDisplayValue('2')).toBeInTheDocument();
  });

  it('opens delete confirmation, refreshes after success, and reports delete failures', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true }));
    listTrades.mockResolvedValue({
      items: [
        {
          id: 7,
          accountId: 1,
          symbol: 'AAPL',
          market: 'us',
          tradeDate: '2026-03-18',
          side: 'buy',
          quantity: 1,
          price: 100,
          fee: 0,
          tax: 0,
          currency: 'USD',
          note: 'seed',
          isActive: true,
          voidedAt: null,
          createdAt: '2026-03-18T00:00:00Z',
          updatedAt: '2026-03-18T00:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      pageSize: 20,
    });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.click(screen.getByRole('button', { name: '作废' }));
    expect(await screen.findByText('确认作废交易？')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '确认作废' }));

    await waitFor(() => expect(deleteTrade).toHaveBeenCalledWith(7));
    await waitFor(() => expect(getSnapshot).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('交易已作废 · 持仓已刷新')).toBeInTheDocument();

    deleteTrade.mockRejectedValueOnce(
      createApiError(
        createParsedApiError({
          title: '作废失败',
          message: '该交易无法作废',
        }),
      ),
    );
    fireEvent.click(screen.getByRole('button', { name: '作废' }));
    fireEvent.click(screen.getByRole('button', { name: '确认作废' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('作废失败');
  });

  it('exposes compact recent-activity actions and mobile more-menu edit path', async () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 390 });
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: false }));
    listTrades.mockResolvedValue({
      items: [
        {
          id: 7,
          accountId: 1,
          symbol: 'AAPL',
          market: 'us',
          tradeDate: '2026-03-18',
          side: 'buy',
          quantity: 1,
          price: 100,
          fee: 0,
          tax: 0,
          currency: 'USD',
          note: 'seed',
          isActive: true,
          voidedAt: null,
          createdAt: '2026-03-18T00:00:00Z',
          updatedAt: '2026-03-18T00:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      pageSize: 20,
    });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const recentActivity = screen.getByTestId('portfolio-recent-activity');
    expect(within(recentActivity).getByRole('button', { name: '更多' })).toBeInTheDocument();
    fireEvent.click(within(recentActivity).getByRole('button', { name: '更多' }));
    fireEvent.click(screen.getByRole('button', { name: '编辑' }));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '保存修改' })).toBeInTheDocument();
  });

  it('switches order-history event type filters inside the drawer without restoring the old attribution surface', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const historyPanel = screen.getByTestId('portfolio-history-full');
    expect(historyPanel).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: translate('zh', 'portfolio.cashLedger') })[0]);
    await waitFor(() => expect(listCashLedger).toHaveBeenCalled());

    const corporateLedgerButtons = screen.getAllByRole('button', { name: translate('zh', 'portfolio.corporateLedger') });
    fireEvent.click(corporateLedgerButtons[corporateLedgerButtons.length - 1]);
    await waitFor(() => expect(listCorporateActions).toHaveBeenCalled());

    expect(screen.queryByTestId('portfolio-attribution-dashboard')).not.toBeInTheDocument();
  });

  it('keeps current holdings and history in the same workspace', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const holdingsPanel = screen.getByTestId('portfolio-current-holdings-panel');
    expect(within(holdingsPanel).getByRole('heading', { name: /Current Holdings/i })).toBeInTheDocument();
    const historyPanel = screen.getByTestId('portfolio-history-full');
    expect(historyPanel).toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-history-drawer')).not.toBeInTheDocument();
    expect(Boolean(holdingsPanel.compareDocumentPosition(historyPanel) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it('keeps the rebuilt shell navigable by tabs instead of the removed attribution widgets', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.click(screen.getByRole('button', { name: '账户' }));
    expect(screen.getAllByText(translate('zh', 'portfolio.createAccountTitle')).length).toBeGreaterThan(0);
    expect(screen.queryByText(translate('zh', 'portfolio.manualTrade'))).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '同步' }));
    expect(screen.getByText(translate('zh', 'portfolio.dataSyncTitle'))).toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.createAccountTitle'))).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '交易' }));
    expect(screen.getByText(translate('zh', 'portfolio.manualTrade'))).toBeInTheDocument();
  });
});
