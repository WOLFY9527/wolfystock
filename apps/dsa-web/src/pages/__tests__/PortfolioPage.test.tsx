import type React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApiError, createParsedApiError } from '../../api/error';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { translate } from '../../i18n/core';
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
};

function makeAccounts(items: AccountItem[] = [{ id: 1, name: 'Main' }]) {
  return {
    accounts: items.map((item) => ({
      id: item.id,
      name: item.name,
      broker: 'Demo',
      market: item.market ?? 'us',
      baseCurrency: item.baseCurrency ?? 'CNY',
      isActive: true,
      ownerId: null,
      createdAt: '2026-03-19T00:00:00Z',
      updatedAt: '2026-03-19T00:00:00Z',
    })),
  };
}

function makeSnapshot(options: { accountId?: number; fxStale?: boolean; accountCount?: number } = {}) {
  const accountId = options.accountId ?? 1;
  return {
    asOf: '2026-03-19',
    costMethod: 'fifo' as const,
    currency: 'CNY',
    accountCount: options.accountCount ?? 1,
    totalCash: 1000,
    totalMarketValue: 2000,
    totalEquity: 3000,
    realizedPnl: 0,
    unrealizedPnl: 0,
    feeTotal: 0,
    taxTotal: 0,
    fxStale: options.fxStale ?? true,
    fxRates: [
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
        totalCash: 1000,
        totalMarketValue: 2000,
        totalEquity: 3000,
        realizedPnl: 0,
        unrealizedPnl: 0,
        feeTotal: 0,
        taxTotal: 0,
        fxStale: options.fxStale ?? true,
        positions: [],
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
  return screen.getByRole('button', { name: translate(language, 'portfolio.refreshFx') });
}

describe('PortfolioPage FX refresh', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

    expect(screen.getByTestId('portfolio-bento-page')).toHaveAttribute('data-bento-surface', 'true');
    expect(screen.getByTestId('portfolio-bento-page')).toHaveClass('w-full', 'flex-1', 'min-w-0', 'flex', 'flex-col', 'gap-6', 'min-h-0');
    expect(screen.getByTestId('portfolio-bento-page')).not.toHaveClass('px-6', 'md:px-8', 'xl:px-12', 'pt-6', 'pb-12', 'overflow-y-auto', 'no-scrollbar');
    expect(screen.getByTestId('portfolio-bento-page')).not.toHaveClass('max-w-[1920px]', 'mx-auto', 'px-4', 'py-2');
    expect(screen.queryByTestId('portfolio-bento-hero')).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-total-assets-card')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '总资产 Total Assets' })).toBeInTheDocument();
    expect(screen.getByTestId('portfolio-total-assets-value')).toHaveStyle({ textShadow: '0 0 30px rgba(52, 211, 153, 0.4)' });
    expect(await screen.findByText(translate('zh', 'portfolio.fxStale'))).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: translate('zh', 'portfolio.refreshFx') })).not.toBeInTheDocument();
    const submitTradeButton = screen.getByRole('button', { name: translate('zh', 'portfolio.submitTrade') });
    expect(submitTradeButton).toHaveAttribute('type', 'submit');
    expect(submitTradeButton).not.toHaveAttribute('data-variant');
    expect(submitTradeButton.className).toContain('from-blue-600');
    expect(submitTradeButton.className).toContain('to-purple-600');
    expect(submitTradeButton.className).toContain('text-white');
    expect(submitTradeButton.className).toContain('font-medium');
    expect(submitTradeButton.className).toContain('py-3');
    expect(submitTradeButton.className).toContain('shadow-[0_0_15px_rgba(139,92,246,0.3)]');
    expect(screen.queryByText(translate('zh', 'portfolio.scopeHint'))).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '交易' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '账户' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '同步' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '汇率' })).toBeInTheDocument();
    expect(screen.getByTestId('portfolio-left-tab-switcher').className).toContain('bg-white/[0.05]');
    expect(screen.getByRole('button', { name: '交易' }).className).toContain('bg-white/10');
    expect(screen.getByRole('button', { name: '账户' }).className).not.toContain('border-white');
    expect(screen.getByRole('heading', { name: /Current Holdings/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '历史记录 ↗' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: translate('zh', 'portfolio.costFutuDiluted') })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: translate('zh', 'portfolio.costThsPnl') })).toBeInTheDocument();
    expect(screen.getByLabelText('ACCOUNT')).toHaveClass('pr-10', 'ui-control-value');
    expect(screen.getByLabelText('COST METHOD')).toHaveClass('pr-10', 'ui-control-value');
    const totalAssetsCard = screen.getByTestId('portfolio-total-assets-card');
    const tradeStationSection = screen.getByRole('heading', { name: 'Trade Station' }).closest('section');
    expect(Boolean(totalAssetsCard.compareDocumentPosition(tradeStationSection as Element) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it('renders the mobile portfolio order as assets, holdings, trade station, history', async () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 390 });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const totalAssetsCard = screen.getByTestId('portfolio-total-assets-card');
    const holdingsPanel = screen.getByTestId('portfolio-current-holdings-panel');
    const tradeStationSection = screen.getByRole('heading', { name: 'Trade Station' }).closest('section') as HTMLElement;
    const mobileHistoryPanel = screen.getByTestId('portfolio-mobile-history-panel');

    expect(Boolean(totalAssetsCard.compareDocumentPosition(holdingsPanel) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(holdingsPanel.compareDocumentPosition(tradeStationSection) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(tradeStationSection.compareDocumentPosition(mobileHistoryPanel) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(within(mobileHistoryPanel).getByRole('heading', { name: '历史记录' })).toBeInTheDocument();
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

    const accountSelect = screen.getAllByRole('combobox')[0] as HTMLSelectElement;
    fireEvent.change(accountSelect, { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: '账户' }));
    fireEvent.click(screen.getByRole('button', { name: '删除 Main' }));

    expect(await screen.findByText(translate('zh', 'portfolio.accountDeleteMessage'))).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'portfolio.deleteConfirm') }));

    await waitFor(() => expect(deleteAccount).toHaveBeenCalledWith(1));
    await waitFor(() => expect((screen.getAllByRole('combobox')[0] as HTMLSelectElement).value).toBe('2'));
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

    const accountSelect = screen.getByLabelText('ACCOUNT');
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

    const accountSelect = screen.getAllByRole('combobox')[0];
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

    const accountSelect = screen.getAllByRole('combobox')[0];
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

    const accountSelect = screen.getAllByRole('combobox')[0];
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
    expect(screen.getByText(translate('zh', 'portfolio.fxFresh'))).toBeInTheDocument();
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

    const accountSelect = screen.getAllByRole('combobox')[0];
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

    const costMethodSelect = screen.getAllByRole('combobox')[1];

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
    expect(screen.getByRole('button', { name: 'History ↗' })).toBeInTheDocument();
    expect(screen.getByText(translate('en', 'portfolio.noPositions'))).toBeInTheDocument();
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

    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: '1' } });
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

    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: '1' } });
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
    expect(screen.getByRole('heading', { name: /Current Holdings/i })).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'portfolio.manualTrade'))).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'portfolio.noPositions'))).toBeInTheDocument();
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
    expect(screen.getByRole('button', { name: '公司行为' })).toBeInTheDocument();
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
    expect(cashAmountCurrencyGrid.className).toContain('gap-y-6');

    const cashCurrencySelect = screen.getByTestId('portfolio-cash-currency-select');
    expect(cashCurrencySelect.tagName).toBe('SELECT');
    expect(cashCurrencySelect.className).toContain('select-surface');

    const amountInput = screen.getByLabelText('AMOUNT');
    expect(amountInput.className).toContain('input-surface');
    expect(amountInput.className).toContain('rounded-lg');

    fireEvent.click(screen.getByRole('button', { name: '公司行为' }));
    expect(screen.getByText(translate('zh', 'portfolio.manualCorporate'))).toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.manualTrade'))).not.toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.manualCash'))).not.toBeInTheDocument();
  });

  it('opens the order history drawer and shows event filters', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.click(screen.getByRole('button', { name: '历史记录 ↗' }));

    expect(screen.getByTestId('portfolio-history-drawer')).toBeInTheDocument();
    expect(screen.getByRole('dialog', { name: '历史记录' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('zh', 'portfolio.tradeLedger') })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('zh', 'portfolio.cashLedger') })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: translate('zh', 'portfolio.corporateLedger') }).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: translate('zh', 'portfolio.refreshLedger') })).toBeInTheDocument();
  });

  it('switches order-history event type filters inside the drawer without restoring the old attribution surface', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.click(screen.getByRole('button', { name: '历史记录 ↗' }));
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'portfolio.cashLedger') }));
    await waitFor(() => expect(listCashLedger).toHaveBeenCalled());

    const corporateLedgerButtons = screen.getAllByRole('button', { name: translate('zh', 'portfolio.corporateLedger') });
    fireEvent.click(corporateLedgerButtons[corporateLedgerButtons.length - 1]);
    await waitFor(() => expect(listCorporateActions).toHaveBeenCalled());

    expect(screen.queryByTestId('portfolio-attribution-dashboard')).not.toBeInTheDocument();
  });

  it('keeps current holdings in the main panel while the history drawer opens and closes independently', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();

    const holdingsPanel = screen.getByTestId('portfolio-current-holdings-panel');
    expect(within(holdingsPanel).getByRole('heading', { name: /Current Holdings/i })).toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-history-drawer')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '历史记录 ↗' }));

    expect(screen.getByTestId('portfolio-history-drawer')).toBeInTheDocument();
    expect(within(holdingsPanel).getByRole('heading', { name: /Current Holdings/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '关闭历史记录' }));
    await waitFor(() => expect(screen.queryByTestId('portfolio-history-drawer')).not.toBeInTheDocument());
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
