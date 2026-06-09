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

const p = (key: string) => translate('zh', `portfolio.${key}`);

const {
  getAccounts,
  getSnapshot,
  getRisk,
  projectScenarioRisk,
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
  projectScenarioRisk: vi.fn(),
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
    projectScenarioRisk,
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
  valuationLineageState?: string | null;
  positionOverrides?: Record<string, unknown>;
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
      costBasisNative: 1500,
      marketValueNative: 1600,
      unrealizedPnlNative: 100,
      unrealizedPnlPct: 6.6667,
      displayMarketValue: 1600,
      displayUnrealizedPnl: 100,
      displayCurrency: 'USD',
      displayFxStatus: 'live' as const,
      priceSource: 'daily_close_quote',
      priceSourceLabel: 'Daily close quote',
      priceAsOf: '2026-03-19',
      isPriceFallback: false,
      priceFallbackReason: null,
      valuationConfidence: 1,
      ...options.positionOverrides,
    },
  ] : [];
  const analytics = {
    pnl: {
      displayCurrency: 'CNY',
      realized: { amount: 120, amountDisplay: 'CNY 120.00', percent: 4, currency: 'CNY', fxStatus: 'live' as const },
      unrealized: { amount: options.includePosition ? 100 : 0, amountDisplay: 'CNY 100.00', percent: 3.3, currency: 'CNY', fxStatus: options.fxStale ? 'unavailable' as const : 'live' as const },
      total: { amount: options.includePosition ? 220 : 120, amountDisplay: 'CNY 220.00', percent: 7.3, currency: 'CNY', fxStatus: options.fxStale ? 'unavailable' as const : 'live' as const },
    },
    exposure: {
      byAccount: options.includePosition ? [
        { key: String(accountId), label: `Account ${accountId}`, marketValue: 2000, displayValue: 2000, displayCurrency: 'CNY', percent: 100, fxStatus: 'live' as const, accountId, accountName: `Account ${accountId}`, baseCurrency: 'CNY', holdingCount: 1 },
      ] : [],
      byCurrency: options.includePosition ? [
        { key: 'USD', label: 'USD', marketValue: 1600, displayValue: 1600, displayCurrency: 'USD', percent: 100, fxStatus: options.fxStale ? 'unavailable' as const : 'live' as const, nativeValue: 1600, nativeCurrency: 'USD', currency: 'USD', holdingCount: 1 },
      ] : [],
      byMarket: options.includePosition ? [
        { key: 'us', label: 'US', marketValue: 2000, displayValue: 2000, displayCurrency: 'CNY', percent: 100, fxStatus: 'live' as const, market: 'us', holdingCount: 1 },
      ] : [],
      bySymbol: options.includePosition ? [
        { key: 'AAPL', label: 'AAPL', marketValue: 1600, displayValue: 1600, displayCurrency: 'USD', percent: 100, fxStatus: options.fxStale ? 'unavailable' as const : 'live' as const, symbol: 'AAPL', market: 'us', currency: 'USD', unrealizedPnl: 100, unrealizedPnlPct: 6.6667, holdingCount: 1 },
      ] : [],
      bySector: [],
      sectorStatus: 'unavailable' as const,
    },
    risk: {
      largestPosition: options.includePosition ? { key: 'AAPL', label: 'AAPL', marketValue: 1600, displayValue: 1600, displayCurrency: 'USD', percent: 100, fxStatus: 'live' as const, symbol: 'AAPL' } : null,
      largestCurrency: options.includePosition ? { key: 'USD', label: 'USD', marketValue: 1600, displayValue: 1600, displayCurrency: 'USD', percent: 100, fxStatus: 'live' as const, currency: 'USD' } : null,
      largestMarket: options.includePosition ? { key: 'us', label: 'US', marketValue: 2000, displayValue: 2000, displayCurrency: 'CNY', percent: 100, fxStatus: 'live' as const, market: 'us' } : null,
      holdingCount: options.includePosition ? 1 : 0,
      accountCount: options.accountCount ?? 1,
      cashPercent: options.includePosition ? 33.3333 : null,
      fxUnavailable: options.fxStale ?? true,
      warnings: options.includePosition ? ['single_position_gt_30', 'single_currency_gt_80', 'single_market_gt_80'] : ['no_holdings'],
    },
  };
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
    ...(options.valuationLineageState !== undefined ? { valuationLineageState: options.valuationLineageState } : {}),
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
    analytics,
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

function openPortfolioDataNotes(language: 'zh' | 'en' = 'zh') {
  const dataNotes = screen.getByTestId('portfolio-data-notes');
  if (!dataNotes.hasAttribute('open')) {
    fireEvent.click(
      within(dataNotes).getByText(language === 'en' ? 'View data notes and allocation detail' : '查看数据说明与配置细节'),
    );
  }
  return dataNotes;
}

function getLeftTabButton(name: string) {
  return within(screen.getByTestId('portfolio-left-tab-switcher')).getByRole('button', { name });
}

describe('PortfolioPage FX refresh', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 1024 });

    getAccounts.mockResolvedValue(makeAccounts());
    getSnapshot.mockImplementation(async ({ accountId }: { accountId?: number } = {}) => makeSnapshot({ accountId, fxStale: true }));
    getRisk.mockResolvedValue(makeRisk());
    projectScenarioRisk.mockResolvedValue({
      readModelType: 'portfolio_scenario_risk_advisory_v1',
      advisoryOnly: true,
      executionReadiness: 'advisory_only_not_trade_execution',
      asOf: '2026-03-19T00:00:00Z',
      coverage: {
        totalPositions: 1,
        positionsWithUsableWeight: 1,
        positionsWithMarketValue: 1,
        effectiveWeightSum: 1,
        totalMarketValue: 1600,
        explicitExposureRows: 0,
        labelsWithExplicitCoverage: [],
      },
      scenarios: [
        {
          name: 'symbol_aapl_down_-8',
          portfolioImpactPct: -8,
          portfolioImpactAmount: -128,
          coveredWeight: 1,
          coveredMarketValue: 1600,
          warnings: [],
          missingCoverage: [],
          positionContributions: [
            {
              symbol: 'AAPL',
              bucket: 'Main',
              weight: 1,
              marketValue: 1600,
              impactPct: -8,
              impactAmount: -128,
              contributionToScenarioLoss: 1,
              warnings: [],
              appliedShocks: [
                {
                  label: 'AAPL',
                  shockPct: -8,
                  exposure: 1,
                  impactPct: -8,
                  impactAmount: -128,
                },
              ],
            },
          ],
          bucketContributions: [
            {
              bucket: 'Main',
              positionCount: 1,
              impactPct: -8,
              impactAmount: -128,
              contributionToScenarioLoss: 1,
            },
          ],
        },
      ],
      insufficientDataReasons: [],
      missingDataWarnings: [],
      metadata: {
        sideEffectFree: true,
        noBrokerSync: true,
        noAccountingMutation: true,
        noOrderPlacement: true,
        notInvestmentAdvice: true,
      },
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
    expect(workspace.parentElement).toHaveClass('w-full', 'max-w-[var(--wolfy-consumer-shell-max,1880px)]', 'mx-auto', 'px-4', 'xl:px-8', 'flex', 'flex-col', 'gap-5', 'flex-1', 'min-w-0', 'min-h-0');
    expect(workspace.parentElement).not.toHaveClass('max-w-[1600px]');
    expect(workspace.parentElement?.parentElement).toHaveAttribute('data-workspace-width', 'near-full');
    expect(workspace).toHaveAttribute('data-terminal-primitive', 'grid');
    expect(workspace).toHaveClass('grid', 'grid-cols-1', 'xl:grid-cols-12', 'gap-6', 'items-start');
    expect(screen.getByTestId('portfolio-bento-page')).toHaveAttribute('data-bento-surface', 'true');
    expect(screen.getByTestId('portfolio-bento-page')).toHaveClass('w-full', 'flex-1', 'min-w-0', 'flex', 'flex-col', 'min-h-0');
    expect(screen.getByTestId('portfolio-bento-page')).not.toHaveClass('gap-5', 'px-6', 'md:px-8', 'xl:px-12', 'pt-6', 'pb-12', 'overflow-y-auto', 'no-scrollbar');
    expect(screen.getByTestId('portfolio-bento-page')).not.toHaveClass('max-w-[1920px]', 'mx-auto', 'px-4', 'py-2');
    expect(screen.queryByTestId('portfolio-bento-hero')).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-row-status')).toHaveClass('col-span-12', 'min-w-0');
    expect(screen.getByTestId('portfolio-account-status-strip')).toHaveClass('grid', 'xl:grid-cols-[minmax(0,1.6fr)_minmax(360px,1fr)]');
    expect(screen.getByTestId('portfolio-account-status-strip')).toHaveAttribute('data-terminal-primitive', 'panel');
    expect(screen.getByTestId('portfolio-total-assets-card')).toHaveClass('min-w-0');
    expect(screen.getByTestId('portfolio-account-status-strip')).toHaveTextContent('先创建或选择账户，再添加第一笔持仓或导入历史记录。');
    const commandStrip = screen.getByTestId('portfolio-command-strip');
    expect(within(commandStrip).queryByRole('button', { name: '添加持仓' })).not.toBeInTheDocument();
    expect(within(commandStrip).queryByRole('button', { name: '导入记录' })).not.toBeInTheDocument();
    expect(within(commandStrip).queryByRole('button', { name: '同步数据' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /总资产|Total Assets/ })).toBeInTheDocument();
    expect(screen.getByTestId('portfolio-total-assets-value')).toHaveClass('text-white');
    expect(screen.getByTestId('portfolio-command-strip')).toContainElement(screen.getByTestId('portfolio-display-currency-select'));
    expect(screen.queryByTestId('portfolio-row-macro')).not.toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-summary-strip')).not.toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-summary-core-row')).not.toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-summary-aux-row')).not.toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-pnl-summary')).not.toBeInTheDocument();
    const onboardingRow = screen.getByTestId('portfolio-empty-onboarding-row');
    const onboardingWorkflow = screen.getByTestId('portfolio-empty-workflow-column');
    const onboardingPreview = screen.getByTestId('portfolio-preview-card');
    expect(onboardingRow).toHaveClass('grid', 'grid-cols-1', 'xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]');
    expect(onboardingWorkflow).toHaveTextContent('首次配置路径');
    expect(onboardingWorkflow).toHaveTextContent('创建或导入首个组合');
    expect(onboardingWorkflow).toHaveTextContent('真实数据接入前不生成示例收益');
    expect(onboardingWorkflow).toHaveTextContent('保存后会在下方自动展开真实持仓、风险摘要与近期活动。');
    expect(onboardingPreview).toHaveTextContent('功能预览 / 示例结构');
    expect(onboardingPreview).toHaveTextContent('非持久预览');
    expect(onboardingPreview).toHaveTextContent('持仓台账');
    expect(onboardingPreview).toHaveTextContent('风险摘要');
    expect(onboardingPreview).toHaveTextContent('近期活动');
    expect(screen.getByTestId('portfolio-exposure-card')).toHaveTextContent('暂无持仓，保存持仓流水后生成盈亏与资产配置。');
    expect(screen.getByTestId('portfolio-risk-card')).toHaveTextContent('待生成');
    expect(screen.getByTestId('portfolio-risk-card')).toHaveTextContent('压力情景入口会在持仓出现后启用');
    expect((await screen.findAllByText(translate('zh', 'portfolio.fxStale'))).length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: '手工记账台' })).toBeInTheDocument();
    expect(screen.getAllByText('手工记账入口').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: '持仓流水' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /交易工作台|Trade Station/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '股票买卖' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '提交交易' })).not.toBeInTheDocument();
    expect(screen.queryByText('买入')).not.toBeInTheDocument();
    expect(screen.queryByText('卖出')).not.toBeInTheDocument();
    const submitTradeButton = screen.getByRole('button', { name: translate('zh', 'portfolio.submitTrade') });
    expect(submitTradeButton).toHaveAttribute('type', 'submit');
    expect(submitTradeButton).toHaveAttribute('data-variant', 'primary');
    expect(submitTradeButton).toHaveAttribute('data-size', 'md');
    expect(submitTradeButton.className).toContain('border-[color:var(--wolfy-accent)]');
    expect(submitTradeButton.className).toContain('bg-[var(--wolfy-accent)]');
    expect(submitTradeButton.className).toContain('text-[#f7f8ff]');
    expect(submitTradeButton.className).toContain('font-medium');
    expect(submitTradeButton.className).toContain('py-2.5');
    expect(submitTradeButton.className).toContain('rounded-md');
    expect(screen.queryByText(translate('zh', 'portfolio.scopeHint'))).not.toBeInTheDocument();
    expect(getLeftTabButton('记账')).toBeInTheDocument();
    expect(getLeftTabButton('账户')).toBeInTheDocument();
    expect(getLeftTabButton('同步')).toBeInTheDocument();
    expect(getLeftTabButton('汇率')).toBeInTheDocument();
    expect(screen.getByTestId('portfolio-left-tab-switcher')).toHaveAttribute('data-terminal-primitive', 'nested-block');
    expect(getLeftTabButton('记账').className).toContain('bg-white/10');
    expect(getLeftTabButton('账户').className).not.toContain('border-white');
    expect(screen.queryByRole('heading', { name: /^Current Holdings(?: \(|$)/i })).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-start-card')).toHaveAttribute('data-terminal-primitive', 'empty-state');
    expect(screen.queryByRole('button', { name: '历史记录 ↗' })).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-recent-activity')).toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-history-full')).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: translate('zh', 'portfolio.costFutuDiluted') })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: translate('zh', 'portfolio.costThsPnl') })).toBeInTheDocument();
    const accountSelect = screen.getByLabelText(/记账账户|ledger account/i) as HTMLSelectElement;
    const costMethodSelect = screen.getByLabelText(/成本方法|COST METHOD/) as HTMLSelectElement;
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
    const holdingsPanel = screen.getByTestId('portfolio-empty-ledger-preview');
    const tradeStationSection = screen.getByRole('heading', { name: /手工记账台|Trade Station/ }).closest('section');
    expect(Boolean(totalAssetsCard.compareDocumentPosition(onboardingRow) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(onboardingRow.compareDocumentPosition(holdingsPanel) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(totalAssetsCard.compareDocumentPosition(tradeStationSection as Element) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(holdingsPanel.compareDocumentPosition(tradeStationSection as Element) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it('renders the mobile empty portfolio order as hero, onboarding, holdings, risk, notes, recent activity, trade station', async () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 390 });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const totalAssetsCard = screen.getByTestId('portfolio-total-assets-card');
    const onboardingRow = screen.getByTestId('portfolio-empty-onboarding-row');
    const startCard = screen.getByTestId('portfolio-start-card');
    const riskCard = screen.getByTestId('portfolio-risk-card');
    const dataNotes = screen.getByTestId('portfolio-data-notes');
    const tradeStationSection = screen.getByRole('heading', { name: /手工记账台|Trade Station/ }).closest('section') as HTMLElement;
    const recentActivity = screen.getByTestId('portfolio-recent-activity');

    expect(Boolean(totalAssetsCard.compareDocumentPosition(onboardingRow) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(onboardingRow.compareDocumentPosition(startCard) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(startCard.compareDocumentPosition(riskCard) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(riskCard.compareDocumentPosition(dataNotes) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(dataNotes.compareDocumentPosition(recentActivity) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(recentActivity.compareDocumentPosition(tradeStationSection) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(screen.queryByTestId('portfolio-history-full')).not.toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-pnl-summary')).not.toBeInTheDocument();
  });

  it('renders the main RiskConsole as a two-column holdings and risk workspace on desktop', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(screen.getByTestId('portfolio-row-routing')).toHaveClass(
      'grid',
      'grid-cols-1',
      'xl:grid-cols-[minmax(0,7fr)_minmax(340px,5fr)]',
    );
    expect(screen.getByTestId('portfolio-primary-lane')).toHaveClass(
      'min-w-0',
      'flex',
      'flex-col',
      'gap-4',
    );
    expect(screen.getByTestId('portfolio-secondary-lane')).toHaveClass(
      'min-w-0',
      'flex',
      'flex-col',
      'gap-4',
    );
  });

  it('renders empty portfolio start card and recent activity after analytics for small history', async () => {
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

    expect(screen.getByTestId('portfolio-current-holdings-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-history-full')).not.toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-history-panel')).not.toBeInTheDocument();
    const workflowColumn = screen.getByTestId('portfolio-empty-workflow-column');
    const startCard = screen.getByTestId('portfolio-start-card');
    const recentActivity = screen.getByTestId('portfolio-recent-activity');
    expect(workflowColumn).toContainElement(startCard);
    expect(workflowColumn).not.toContainElement(recentActivity);
    expect(workflowColumn).toHaveClass('min-w-0');
    expect(startCard).not.toHaveClass('xl:min-h-[300px]', 'min-h-[520px]');
    expect(within(startCard).getByText('创建或导入首个组合')).toBeInTheDocument();
    expect(within(startCard).getByText('先创建或选择账户，再添加第一笔持仓或导入历史记录。')).toBeInTheDocument();
    expect(within(startCard).getByText('历史记录存在，当前无持仓')).toBeInTheDocument();
    expect(within(startCard).queryByText('活跃账户')).not.toBeInTheDocument();
    expect(within(startCard).queryByText('可写账户')).not.toBeInTheDocument();
    expect(within(startCard).queryByText(/active accounts|writable accounts/i)).not.toBeInTheDocument();
    expect(workflowColumn).toHaveTextContent('保存后会在下方自动展开真实持仓、风险摘要与近期活动。');
    expect(within(recentActivity).getByText('历史记录存在，当前无持仓')).toBeInTheDocument();
    expect(within(recentActivity).getByText('AAPL')).toBeInTheDocument();
    expect(within(recentActivity).getByText(/2026-03-18/)).toBeInTheDocument();

    const tradeStation = screen.getByTestId('portfolio-trade-station-card');
    expect(within(tradeStation).getByRole('button', { name: '记账' }).className).toContain('bg-white/10');
    expect(screen.getByLabelText(/记账账户|ledger account/i)).toHaveValue('1');
    expect(screen.getByTestId('portfolio-trade-station-card')).toHaveClass('gap-4', 'xl:min-h-0');
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

  it('renders a compact account strip, compact empty holdings, and primary portfolio actions', async () => {
    const { container } = render(<PortfolioPage />);

    await waitForInitialLoad();

    const workspace = screen.getByTestId('portfolio-workspace-grid');
    expect(workspace.parentElement).toHaveClass('w-full', 'max-w-[var(--wolfy-consumer-shell-max,1880px)]', 'mx-auto', 'px-4', 'xl:px-8', 'flex-1', 'min-w-0', 'min-h-0');
    expect(workspace.parentElement).not.toHaveClass('max-w-[1600px]');
    expect(workspace.parentElement?.parentElement).toHaveAttribute('data-workspace-width', 'near-full');
    expect(workspace).toHaveClass('grid', 'grid-cols-1', 'xl:grid-cols-12', 'gap-6', 'items-start');
    expect(screen.getByTestId('portfolio-bento-page').className).not.toMatch(/\bbg-(black|\[#050505\]|gray-|zinc-|slate-|neutral-)/);
    expect(screen.getByTestId('portfolio-account-status-strip')).toHaveClass('grid', 'xl:grid-cols-[minmax(0,1.6fr)_minmax(360px,1fr)]');
    const commandStrip = screen.getByTestId('portfolio-command-strip');
    expect(within(commandStrip).queryByRole('button', { name: '添加持仓' })).not.toBeInTheDocument();
    expect(within(commandStrip).queryByRole('button', { name: '导入记录' })).not.toBeInTheDocument();
    expect(within(commandStrip).queryByRole('button', { name: '同步数据' })).not.toBeInTheDocument();
    expect(commandStrip).toContainElement(screen.getByTestId('portfolio-display-currency-select'));

    const startCard = screen.getByTestId('portfolio-start-card');
    expect(startCard).toHaveAttribute('data-terminal-primitive', 'empty-state');
    expect(startCard).toHaveClass('min-h-[72px]');
    expect(startCard).toHaveTextContent('创建或导入首个组合');
    expect(startCard).toHaveTextContent('先创建或选择账户，再添加第一笔持仓或导入历史记录。');
    const emptyWorkflowColumn = screen.getByTestId('portfolio-empty-workflow-column');
    expect(within(emptyWorkflowColumn).getByRole('button', { name: '添加持仓' })).toBeInTheDocument();
    expect(within(emptyWorkflowColumn).getByRole('button', { name: '导入记录' })).toBeInTheDocument();
    expect(emptyWorkflowColumn).toHaveTextContent('保存后会在下方自动展开真实持仓、风险摘要与近期活动。');
    expect(screen.getByTestId('portfolio-preview-card')).toHaveTextContent('功能预览 / 示例结构');
    expect(screen.getByTestId('portfolio-preview-card')).toHaveTextContent('非持久预览');
    expect(emptyWorkflowColumn).not.toHaveTextContent(/数据不足，禁止判断|买入|卖出|下单|券商|broker/i);
    expect(startCard).not.toHaveClass('min-h-[300px]', 'min-h-[520px]', 'xl:min-h-[300px]');
    expect(within(startCard).queryByText('活跃账户')).not.toBeInTheDocument();
    expect(within(startCard).queryByText('可写账户')).not.toBeInTheDocument();
    expect(within(startCard).queryByText('当前记账账户')).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-next-action-panel')).toHaveTextContent('数据不足，暂不形成结论。');

    const manualDisclosure = screen.getByTestId('portfolio-manual-record-disclosure');
    expect(manualDisclosure).not.toHaveAttribute('open');
    expect(container).not.toHaveTextContent(/developer|debug|raw|schema|trace|provider_timeout|not_enough_history|fallback|MarketCache/i);
    const workspaceLanes = screen.getByTestId('portfolio-workspace-lanes');
    const primaryLane = screen.getByTestId('portfolio-primary-lane');
    const secondaryLane = screen.getByTestId('portfolio-secondary-lane');
    const activityLane = screen.getByTestId('portfolio-activity-lane');
    const manualLane = screen.getByTestId('portfolio-manual-lane');
    expect(screen.getByTestId('portfolio-row-status')).toHaveClass('col-span-12', 'min-w-0');
    expect(screen.getByTestId('portfolio-row-routing')).toHaveClass('order-3', 'col-span-12', 'grid', 'grid-cols-1', 'xl:grid-cols-[minmax(0,7fr)_minmax(340px,5fr)]', 'items-start');
    expect(workspaceLanes).toHaveClass('order-5', 'col-span-12', 'grid', 'grid-cols-1', 'xl:grid-cols-[minmax(0,7fr)_minmax(320px,5fr)]', 'items-start');
    expect(primaryLane).toHaveClass('min-w-0', 'flex', 'flex-col', 'gap-4');
    expect(secondaryLane).toHaveClass('min-w-0', 'flex', 'flex-col', 'gap-4');
    expect(activityLane).toHaveClass('min-w-0', 'flex', 'flex-col', 'gap-4');
    expect(manualLane).toHaveClass('min-w-0', 'flex', 'flex-col', 'gap-4');
    expect(primaryLane).toContainElement(screen.getByTestId('portfolio-current-holdings-panel'));
    expect(secondaryLane).toContainElement(screen.getByTestId('portfolio-risk-card'));
    expect(screen.getByTestId('portfolio-row-notes')).toContainElement(screen.getByTestId('portfolio-data-notes'));
    expect(activityLane).toContainElement(screen.getByTestId('portfolio-recent-activity'));
    expect(manualLane).toContainElement(screen.getByTestId('portfolio-trade-station-card'));
    expect(
      Boolean(screen.getByTestId('portfolio-recent-activity').compareDocumentPosition(screen.getByTestId('portfolio-trade-station-card')) & Node.DOCUMENT_POSITION_FOLLOWING),
    ).toBe(true);
  });

  it('renders pnl, holding unrealized percent, exposure tabs, and risk summary for active holdings', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true, fxStale: false }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(screen.getByTestId('portfolio-pnl-realized')).toHaveTextContent('已实现盈亏');
    expect(screen.getByTestId('portfolio-pnl-unrealized')).toHaveTextContent('未实现盈亏');
    expect(screen.getByTestId('portfolio-pnl-total')).toHaveTextContent('总盈亏');
    expect(screen.getByTestId('portfolio-summary-core-row')).toContainElement(screen.getByTestId('portfolio-summary-market-value-card'));
    expect(screen.getByTestId('portfolio-summary-core-row')).toContainElement(screen.getByTestId('portfolio-pnl-summary'));
    expect(screen.getByTestId('portfolio-summary-aux-row')).toContainElement(screen.getByTestId('portfolio-summary-cash-card'));
    expect(screen.getByTestId('portfolio-summary-aux-row')).toContainElement(screen.getByTestId('portfolio-summary-holdings-card'));
    expect(screen.getByTestId('portfolio-summary-aux-row')).toContainElement(screen.getByTestId('portfolio-summary-risk-card'));
    expect(screen.getByTestId('portfolio-summary-aux-row')).toContainElement(screen.getByTestId('portfolio-summary-status-card'));
    expect(screen.getByTestId('portfolio-summary-market-value-card')).toHaveTextContent('CNY 2,000.00');
    expect(screen.getByTestId('portfolio-pnl-summary')).toHaveTextContent('+CNY 220.00');
    expect(screen.getByTestId('portfolio-summary-holdings-card')).toHaveTextContent('1 项持仓');
    expect(screen.getByTestId('portfolio-summary-risk-card')).toHaveTextContent('高度集中');
    expect(screen.getByTestId('portfolio-summary-status-card')).toHaveTextContent('2026-03-19');
    const commandStrip = screen.getByTestId('portfolio-command-strip');
    expect(within(commandStrip).getByRole('button', { name: '添加持仓' })).toBeInTheDocument();
    expect(within(commandStrip).getByRole('button', { name: '导入记录' })).toBeInTheDocument();
    expect(within(commandStrip).getByRole('button', { name: '同步数据' })).toBeInTheDocument();
    const holdings = screen.getByTestId('portfolio-current-holdings-panel');
    expect(within(holdings).getAllByText('AAPL').length).toBeGreaterThan(0);
    expect(within(holdings).getAllByText('6.7%').length).toBeGreaterThan(0);
    const exposure = screen.getByTestId('portfolio-exposure-card');
    expect(within(exposure).getByRole('button', { name: '账户' })).toBeInTheDocument();
    expect(within(exposure).getByRole('button', { name: '币种' })).toBeInTheDocument();
    expect(within(exposure).getByRole('button', { name: '市场' })).toBeInTheDocument();
    expect(within(exposure).getByRole('button', { name: '标的' })).toBeInTheDocument();
    fireEvent.click(within(exposure).getByRole('button', { name: '币种' }));
    expect(exposure).toHaveTextContent('USD');
    expect(exposure).toHaveTextContent('USD 1,600.00');
    fireEvent.click(within(exposure).getByRole('button', { name: '标的' }));
    expect(exposure).toHaveTextContent('AAPL');
    expect(exposure).toHaveTextContent('6.7%');
    const risk = screen.getByTestId('portfolio-risk-card');
    expect(risk).toHaveTextContent('最大持仓');
    expect(risk).toHaveTextContent('主币种');
    expect(risk).toHaveTextContent('主市场');
    expect(risk).toHaveTextContent('最大持仓偏高');
  });

  it('renders the bounded scenario risk panel and sends only advisory scenario payload fields', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true, fxStale: false }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(screen.getByTestId('portfolio-current-holdings-panel')).toBeInTheDocument();
    expect(screen.getByTestId('portfolio-risk-card')).toBeInTheDocument();

    const disclosure = screen.getByTestId('portfolio-scenario-risk-disclosure');
    expect(disclosure).not.toHaveAttribute('open');

    fireEvent.click(within(disclosure).getByRole('button', { name: '展开 查看压力情景' }));

    fireEvent.change(screen.getByLabelText('冲击幅度（%）'), { target: { value: '-8' } });
    fireEvent.click(screen.getByRole('button', { name: '运行压力情景' }));

    await waitFor(() => expect(projectScenarioRisk).toHaveBeenCalledTimes(1));

    expect(projectScenarioRisk).toHaveBeenCalledWith({
      asOf: '2026-03-19',
      positions: [
        {
          symbol: 'AAPL',
          weightPct: 100,
          marketValue: 1600,
          marketValueBase: 1600,
          bucketLabel: 'Account 1',
          currency: 'USD',
        },
      ],
      exposures: [],
      scenarioShocks: [
        {
          name: 'symbol_aapl_down_-8',
          shocks: {
            AAPL: {
              shockPct: -8,
            },
          },
        },
      ],
    });

    const sentPayload = projectScenarioRisk.mock.calls[0]?.[0];
    const payloadText = JSON.stringify(sentPayload);
    expect(payloadText).not.toMatch(/accountId|broker|provider|sync|order|tradeId|portfolioMutation/i);
    expect(createTrade).not.toHaveBeenCalled();
    expect(createCashLedger).not.toHaveBeenCalled();
    expect(createCorporateAction).not.toHaveBeenCalled();
    expect(syncIbkrReadOnly).not.toHaveBeenCalled();
    expect(screen.getByTestId('portfolio-scenario-risk-panel')).toHaveTextContent('预估影响');
    expect(screen.getByTestId('portfolio-scenario-risk-panel')).toHaveTextContent('不触发经纪商同步');
    expect(screen.getByTestId('portfolio-scenario-risk-panel')).toHaveTextContent('不改动账务结果');
    expect(screen.getByTestId('portfolio-scenario-risk-panel')).toHaveTextContent('不触发任何下单');
    expect(screen.getByTestId('portfolio-scenario-risk-panel')).toHaveTextContent('模型结果不可作为仓位建议');
  });

  it('retargets scenario projection to the current visible holdings after account scope changes', async () => {
    getAccounts.mockResolvedValue(makeAccounts([
      { id: 1, name: 'Main', baseCurrency: 'CNY', market: 'us' },
      { id: 2, name: 'HK Account', baseCurrency: 'HKD', market: 'hk' },
    ]));
    getSnapshot.mockImplementation(async ({ accountId }: { accountId?: number } = {}) => {
      if (accountId === 2) {
        const snapshot = makeSnapshot({
          accountId: 2,
          includePosition: true,
          fxStale: false,
          positionOverrides: {
            symbol: '00700.HK',
            market: 'hk',
            currency: 'HKD',
            valuationCurrency: 'HKD',
            costBasisNative: 1800,
            marketValueNative: 2000,
            unrealizedPnlNative: 200,
            displayMarketValue: 2000,
            displayUnrealizedPnl: 200,
            totalCost: 1800,
            avgCost: 180,
            lastPrice: 200,
            marketValueBase: 2000,
            unrealizedPnlBase: 200,
            quantity: 10,
            displayCurrency: 'HKD',
          },
        });
        return {
          ...snapshot,
          accounts: [
            {
              ...snapshot.accounts[0],
              accountId: 2,
              accountName: 'HK Account',
              market: 'hk',
              baseCurrency: 'HKD',
            },
          ],
        };
      }
      return makeSnapshot({ accountId, includePosition: true, fxStale: false });
    });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.change(screen.getByLabelText(translate('zh', 'portfolio.accountView')), { target: { value: '2' } });
    await waitFor(() => expect(getSnapshot).toHaveBeenCalledWith({ accountId: 2, costMethod: 'fifo' }));

    const disclosure = screen.getByTestId('portfolio-scenario-risk-disclosure');
    fireEvent.click(within(disclosure).getByRole('button', { name: '展开 查看压力情景' }));

    const visibleHoldingSelect = screen.getByLabelText('可见持仓') as HTMLSelectElement;
    expect(visibleHoldingSelect).toHaveValue('00700.HK');

    fireEvent.change(screen.getByLabelText('冲击幅度（%）'), { target: { value: '-5' } });
    fireEvent.click(screen.getByRole('button', { name: '运行压力情景' }));

    await waitFor(() => expect(projectScenarioRisk).toHaveBeenCalledTimes(1));
    expect(projectScenarioRisk).toHaveBeenCalledWith(expect.objectContaining({
      positions: [expect.objectContaining({ symbol: '00700.HK', currency: 'HKD' })],
      scenarioShocks: [expect.objectContaining({
        shocks: {
          '00700.HK': {
            shockPct: -5,
          },
        },
      })],
    }));
  });

  it('translates delayed fallback prices into consumer-safe valuation language', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({
      includePosition: true,
      fxStale: false,
      positionOverrides: {
        lastPrice: 150,
        marketValueBase: 1500,
        unrealizedPnlBase: 0,
        unrealizedPnlPct: 0,
        priceSource: 'avg_cost_fallback',
        priceSourceLabel: 'Average cost fallback',
        priceAsOf: null,
        isPriceFallback: true,
        priceFallbackReason: 'current_quote_unavailable',
        valuationConfidence: 0.25,
      },
    }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const holdings = screen.getByTestId('portfolio-current-holdings-panel');
    expect(holdings).toHaveTextContent('价格可能延迟');
    expect(holdings).toHaveTextContent('部分价格数据暂不可用，已使用最近一次可用数据。');
    expect(holdings).toHaveTextContent('置信度有限');
    expect(holdings).not.toHaveTextContent('Average cost fallback');
    expect(holdings).not.toHaveTextContent('均价回退');
    expect(holdings).not.toHaveTextContent('现价缺失');
    expect(holdings).not.toHaveTextContent(/现价快照|Live quote/);
    expect(holdings.textContent || '').not.toMatch(/avg_cost_fallback|current_quote_unavailable|fallback/i);
  });

  it('labels generic non-fallback position prices as neutral snapshots', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({
      includePosition: true,
      fxStale: false,
      positionOverrides: {
        priceSource: null,
        priceSourceLabel: null,
        isPriceFallback: false,
      },
    }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const holdings = screen.getByTestId('portfolio-current-holdings-panel');
    expect(holdings).toHaveTextContent('价格快照');
    expect(holdings).not.toHaveTextContent(/现价快照|Live quote/);
    expect(holdings).not.toHaveTextContent('估算价格');
    expect(holdings).not.toHaveTextContent('均价回退');
    expect(holdings).not.toHaveTextContent('价格来源待确认');
    expect(holdings.textContent || '').not.toMatch(/买入|卖出|下单|立即交易|必买|稳赚|保证收益|guaranteed|best contract|AI recommends you buy/i);
  });

  it('uses neutral English price snapshot wording on English routes', async () => {
    window.history.replaceState(window.history.state, '', '/en/portfolio');
    getSnapshot.mockResolvedValue(makeSnapshot({
      includePosition: true,
      fxStale: false,
      positionOverrides: {
        priceSource: null,
        priceSourceLabel: null,
        isPriceFallback: false,
      },
    }));

    render(
      <UiLanguageProvider>
        <PortfolioPage />
      </UiLanguageProvider>,
    );

    await waitForInitialLoad();

    const holdings = screen.getByTestId('portfolio-current-holdings-panel');
    expect(holdings).toHaveTextContent('Price snapshot');
    expect(holdings).not.toHaveTextContent(/Live quote|现价快照/);
    expect(holdings).not.toHaveTextContent('Price source pending');
  });

  it('compresses quote, sync, and fallback source states into safe freshness states', async () => {
    const snapshot = makeSnapshot({ includePosition: true, fxStale: false });
    const basePosition = snapshot.accounts[0].positions[0];
    snapshot.accounts[0].positions = [
      {
        ...basePosition,
        symbol: 'AAPL',
        priceSource: 'daily_close_quote',
        priceSourceLabel: 'Daily close quote',
        priceAsOf: '2026-03-19',
        isPriceFallback: false,
        priceFallbackReason: null,
        valuationConfidence: 1,
      },
      {
        ...basePosition,
        symbol: 'MSFT',
        priceSource: 'broker_sync_snapshot',
        priceSourceLabel: 'Synced snapshot',
        priceAsOf: '2026-03-19',
        isPriceFallback: false,
        priceFallbackReason: null,
        valuationConfidence: 1,
      },
      {
        ...basePosition,
        symbol: 'COST',
        lastPrice: 150,
        marketValueBase: 1500,
        unrealizedPnlBase: 0,
        unrealizedPnlPct: 0,
        priceSource: 'avg_cost_fallback',
        priceSourceLabel: 'Avg-cost fallback',
        priceAsOf: null,
        isPriceFallback: true,
        priceFallbackReason: 'current_quote_unavailable',
        valuationConfidence: 0.25,
      },
    ];
    getSnapshot.mockResolvedValue(snapshot);

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const holdings = screen.getByTestId('portfolio-current-holdings-panel');
    expect(holdings).toHaveTextContent('价格快照');
    expect(holdings).toHaveTextContent('价格可能延迟');
    expect(holdings).toHaveTextContent('部分价格数据暂不可用，已使用最近一次可用数据。');
    expect(holdings).not.toHaveTextContent('Daily close quote');
    expect(holdings).not.toHaveTextContent('Synced snapshot');
    expect(holdings).not.toHaveTextContent('Avg-cost fallback');
    expect(holdings).not.toHaveTextContent(/现价快照|Live quote/);
    expect(holdings.textContent || '').not.toMatch(/daily_close_quote|broker_sync_snapshot|avg_cost_fallback|current_quote_unavailable|fallback/i);

    expect(screen.getByTestId('portfolio-holding-trust-AAPL')).toHaveTextContent('价格快照');
    expect(screen.getByTestId('portfolio-holding-trust-MSFT')).toHaveTextContent('价格快照');

    const fallbackTrust = screen.getByTestId('portfolio-holding-trust-COST');
    expect(fallbackTrust).toHaveTextContent('价格可能延迟');
    expect(fallbackTrust).toHaveTextContent('置信度有限');
  });

  it('renders portfolio risk drilldown explainability without raw debug labels', async () => {
    const snapshot = makeSnapshot({ includePosition: true, fxStale: false });
    snapshot.analytics.exposure.bySymbol = [
      {
        key: 'AAPL',
        label: 'AAPL',
        marketValue: 1600,
        displayValue: 1600,
        displayCurrency: 'USD',
        percent: 42,
        fxStatus: 'live' as const,
        symbol: 'AAPL',
        market: 'us',
        currency: 'USD',
        unrealizedPnl: 180,
        unrealizedPnlPct: 12.5,
        holdingCount: 1,
      },
      {
        key: 'MSFT',
        label: 'MSFT',
        marketValue: 900,
        displayValue: 900,
        displayCurrency: 'USD',
        percent: 24,
        fxStatus: 'live' as const,
        symbol: 'MSFT',
        market: 'us',
        currency: 'USD',
        unrealizedPnl: 60,
        unrealizedPnlPct: 4.2,
        holdingCount: 1,
      },
      {
        key: '00700',
        label: '00700',
        marketValue: 700,
        displayValue: 700,
        displayCurrency: 'HKD',
        percent: 18,
        fxStatus: 'live' as const,
        symbol: '00700',
        market: 'hk',
        currency: 'HKD',
        unrealizedPnl: -45,
        unrealizedPnlPct: -3.1,
        holdingCount: 1,
      },
    ];
    snapshot.analytics.exposure.byCurrency = [
      {
        key: 'USD',
        label: 'USD',
        marketValue: 2500,
        displayValue: 2500,
        displayCurrency: 'USD',
        percent: 66,
        fxStatus: 'live' as const,
        nativeValue: 2500,
        nativeCurrency: 'USD',
        currency: 'USD',
        holdingCount: 2,
      },
      {
        key: 'HKD',
        label: 'HKD',
        marketValue: 700,
        displayValue: 700,
        displayCurrency: 'HKD',
        percent: 18,
        fxStatus: 'live' as const,
        nativeValue: 700,
        nativeCurrency: 'HKD',
        currency: 'HKD',
        holdingCount: 1,
      },
    ];
    snapshot.analytics.exposure.byMarket = [
      {
        key: 'us',
        label: 'US',
        marketValue: 2500,
        displayValue: 2500,
        displayCurrency: 'USD',
        percent: 66,
        fxStatus: 'live' as const,
        market: 'us',
        holdingCount: 2,
      },
      {
        key: 'hk',
        label: 'HK',
        marketValue: 700,
        displayValue: 700,
        displayCurrency: 'HKD',
        percent: 18,
        fxStatus: 'live' as const,
        market: 'hk',
        holdingCount: 1,
      },
    ];
    snapshot.analytics.risk = {
      ...snapshot.analytics.risk,
      largestPosition: snapshot.analytics.exposure.bySymbol[0],
      largestCurrency: snapshot.analytics.exposure.byCurrency[0],
      largestMarket: snapshot.analytics.exposure.byMarket[0],
      holdingCount: 3,
      warnings: ['single_position_gt_30', 'provider_debug_payload'],
    };
    getSnapshot.mockResolvedValue(snapshot);

    render(<PortfolioPage />);

    await waitForInitialLoad();
    openPortfolioDataNotes();

    const risk = screen.getByTestId('portfolio-risk-card');
    expect(within(risk).getByTestId('portfolio-concentration-label')).toHaveTextContent('集中');
    expect(within(risk).getByTestId('portfolio-concentration-drilldown')).toHaveTextContent('持仓集中度');
    expect(within(risk).getByTestId('portfolio-concentration-drilldown')).toHaveTextContent('42.0%');
    expect(within(risk).getByTestId('portfolio-risk-overview')).toHaveTextContent('主币种');
    expect(within(risk).getByTestId('portfolio-risk-overview')).toHaveTextContent('AAPL');
    expect(within(risk).getByTestId('portfolio-risk-overview')).toHaveTextContent('USD');
    expect(within(risk).getByTestId('portfolio-risk-overview')).toHaveTextContent('主市场');
    expect(within(risk).getByTestId('portfolio-risk-overview')).toHaveTextContent('美股');
    expect(within(risk).getByTestId('portfolio-risk-hints')).toHaveTextContent('最大持仓偏高');
    const exposure = screen.getByTestId('portfolio-exposure-card');
    fireEvent.click(within(exposure).getByRole('button', { name: '标的' }));
    expect(exposure).toHaveTextContent('AAPL');
    expect(exposure).toHaveTextContent('00700');
    expect(exposure).toHaveTextContent('12.5%');
    expect(exposure).toHaveTextContent('-3.1%');
    expect(risk).not.toHaveTextContent('provider_debug_payload');
  });

  it('renders a collapsed consumer-safe risk exposure summary from the current snapshot only', async () => {
    const snapshot = makeSnapshot({ includePosition: true, fxStale: true }) as ReturnType<typeof makeSnapshot> & Record<string, unknown>;
    snapshot.analytics.exposure.byAccount = [
      {
        key: '1',
        label: 'Account 1',
        marketValue: 2200,
        displayValue: 2200,
        displayCurrency: 'CNY',
        percent: 58,
        fxStatus: 'live' as const,
        accountId: 1,
        accountName: 'Account 1',
        baseCurrency: 'CNY',
        holdingCount: 2,
      },
      {
        key: '2',
        label: 'Account 2',
        marketValue: 1600,
        displayValue: 1600,
        displayCurrency: 'CNY',
        percent: 42,
        fxStatus: 'live' as const,
        accountId: 2,
        accountName: 'Account 2',
        baseCurrency: 'CNY',
        holdingCount: 1,
      },
    ];
    snapshot.analytics.exposure.bySymbol = [
      {
        key: 'AAPL',
        label: 'AAPL',
        marketValue: 1600,
        displayValue: 1600,
        displayCurrency: 'USD',
        percent: 42,
        fxStatus: 'live' as const,
        symbol: 'AAPL',
        market: 'us',
        currency: 'USD',
        holdingCount: 1,
      },
    ];
    snapshot.analytics.exposure.byCurrency = [
      {
        key: 'USD',
        label: 'USD',
        marketValue: 2500,
        displayValue: 2500,
        displayCurrency: 'USD',
        percent: 66,
        fxStatus: 'unavailable' as const,
        nativeValue: 2500,
        nativeCurrency: 'USD',
        currency: 'USD',
        holdingCount: 2,
      },
    ];
    snapshot.analytics.exposure.byMarket = [
      {
        key: 'us',
        label: 'US',
        marketValue: 2500,
        displayValue: 2500,
        displayCurrency: 'USD',
        percent: 66,
        fxStatus: 'live' as const,
        market: 'us',
        holdingCount: 2,
      },
    ];
    snapshot.analytics.risk = {
      ...snapshot.analytics.risk,
      largestPosition: snapshot.analytics.exposure.bySymbol[0],
      largestCurrency: snapshot.analytics.exposure.byCurrency[0],
      largestMarket: snapshot.analytics.exposure.byMarket[0],
      cashPercent: 33.3333,
      warnings: ['single_position_gt_30', 'reasonCode_backend_debug'],
    };
    snapshot.fxFreshnessState = 'stale';
    snapshot.benchmarkMappingState = 'missing';
    snapshot.portfolioRiskEvidence = {
      limitationLabels: ['sourceAuthorityAllowed', 'reasonCode backend debug', '仅供风险观察'],
      sourceRefs: [
        { id: 'raw-provider-ref', provider: 'provider-a', sourceClass: 'cache_snapshot' },
      ],
      adminDiagnostics: {
        provider: 'provider-a',
        cache: 'portfolio_cache',
        reasonCode: 'backend_debug_reason',
      },
    };
    getSnapshot.mockResolvedValue(snapshot);

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const summary = screen.getByTestId('portfolio-risk-exposure-summary');
    expect(summary).not.toHaveAttribute('open');
    expect(summary).toHaveTextContent('风险暴露摘要');
    expect(summary).toHaveTextContent('最大持仓 42.0%');
    expect(screen.queryByTestId('portfolio-risk-exposure-summary-body')).not.toBeInTheDocument();

    fireEvent.click(within(summary).getByRole('button', { name: '展开 风险暴露摘要' }));

    const body = screen.getByTestId('portfolio-risk-exposure-summary-body');
    expect(body).toHaveTextContent('最大持仓');
    expect(body).toHaveTextContent('AAPL');
    expect(body).toHaveTextContent('42.0%');
    expect(body).toHaveTextContent('主币种');
    expect(body).toHaveTextContent('USD');
    expect(body).toHaveTextContent('66.0%');
    expect(body).toHaveTextContent('主市场 / 账户');
    expect(body).toHaveTextContent('美股 / Account 1');
    expect(body).toHaveTextContent('66.0% / 58.0%');
    expect(body).toHaveTextContent('现金占比');
    expect(body).toHaveTextContent('33.3%');
    expect(body).toHaveTextContent('仅基于当前页面快照汇总');
    expect(body).toHaveTextContent('汇率可能延迟');
    expect(body).toHaveTextContent('部分风险参考暂不可用');
    expect(body.textContent || '').not.toMatch(
      /sourceAuthority|reasonCode|provider|cache|debug|backend|raw|sourceRefs|execution|readiness|rebalance|reduce|increase|position[- ]?sizing|stop|target|买入|卖出|下单|调仓/i,
    );
  });

  it('renders compact portfolio evidence chips without exposing raw sync or authority internals', async () => {
    const snapshot = makeSnapshot({
      includePosition: true,
      fxStale: true,
      positionOverrides: {
        priceSource: 'daily_close_quote',
        priceSourceLabel: 'Daily close quote',
        priceAsOf: '2026-03-18',
        isPriceFallback: true,
        priceFallbackReason: 'current_quote_unavailable',
        valuationConfidence: 0.62,
      },
    }) as ReturnType<typeof makeSnapshot> & Record<string, unknown>;
    snapshot.fxFreshnessState = 'stale';
    snapshot.holdingsLineageState = 'missing';
    snapshot.cashLedgerCompletenessState = 'missing';
    snapshot.benchmarkMappingState = 'missing';
    snapshot.factorMappingState = 'missing';
    snapshot.sourceAuthorityState = 'observation_only';
    snapshot.confidenceCap = {
      value: 60,
      reason_codes: ['stale_fx', 'manual_replay_complete'],
      limitation_labels: ['仅供风险观察', '持仓来源待核验', '现金流水不完整'],
    };
    snapshot.portfolioRiskEvidence = {
      limitationLabels: ['FX 汇率已过期', '基准映射暂缺', '因子映射暂缺'],
      adminDiagnostics: {
        sourceAuthority: 'manual_replay_authoritative',
        syncImportStatus: 'manual_replay_complete',
      },
    };

    getSnapshot.mockResolvedValue(snapshot);

    render(<PortfolioPage />);

    await waitForInitialLoad();
    openPortfolioDataNotes();

    const valuationPanel = screen.getByTestId('portfolio-valuation-panel');
    const valuationTrust = within(valuationPanel).getByTestId('portfolio-valuation-trust-strip');
    expect(valuationTrust.textContent || '').toMatch(/仅供.*观察/);
    expect(valuationTrust).toHaveTextContent('价格可能延迟');
    expect(valuationTrust).toHaveTextContent('截至 2026-03-18');
    expect(screen.getByTestId('portfolio-consumer-data-notice')).toHaveTextContent('当前估值可能存在延迟，仅供参考。');
    expect(screen.queryByTestId('portfolio-snapshot-evidence-chips')).not.toBeInTheDocument();
    expect(valuationTrust.textContent || '').not.toMatch(/Daily close quote|current_quote_unavailable|sourceAuthority|syncImportStatus|confidenceCap|stale_fx|FX 汇率|基准映射|因子映射/i);

    const riskTrust = screen.getByTestId('portfolio-risk-trust-strip');
    expect(riskTrust).toHaveTextContent('仅供风险观察');
    expect(riskTrust).toHaveTextContent('汇率可能延迟');
    expect(riskTrust).toHaveTextContent('持仓数据待核验');
    expect(riskTrust).toHaveTextContent('现金流水不完整');
    expect(riskTrust).toHaveTextContent('部分风险参考暂不可用');
    expect(riskTrust).toHaveTextContent('置信度有限');
    expect(riskTrust).not.toHaveTextContent(/manual_replay_complete|manual_replay_authoritative|sourceAuthority|syncImportStatus|confidenceCap|stale_fx|FX 汇率|基准映射|因子映射/i);

    const holdingTrust = screen.getByTestId('portfolio-holding-trust-AAPL');
    expect(holdingTrust).toHaveTextContent('价格可能延迟');
    expect(holdingTrust).toHaveTextContent('置信度有限');
    expect(screen.getByTestId('portfolio-current-holdings-panel')).toHaveTextContent('截至 2026-03-18');
  });

  it('shows consumer-safe data quality copy instead of provider setup remediation by default', async () => {
    const snapshot = makeSnapshot({
      includePosition: true,
      fxStale: true,
      positionOverrides: {
        isPriceFallback: true,
        valuationConfidence: 0.62,
      },
    }) as ReturnType<typeof makeSnapshot> & Record<string, unknown>;
    snapshot.fxFreshnessState = 'stale';
    snapshot.holdingsLineageState = 'missing';
    snapshot.cashLedgerCompletenessState = 'missing';
    snapshot.sourceAuthorityState = 'observation_only';
    snapshot.confidenceCap = {
      value: 60,
      limitation_labels: ['仅供风险观察'],
    };
    getSnapshot.mockResolvedValue(snapshot);

    render(<PortfolioPage />);

    await waitForInitialLoad();
    openPortfolioDataNotes();

    const valuationPanel = screen.getByTestId('portfolio-valuation-panel');
    expect(within(valuationPanel).getByTestId('portfolio-valuation-trust-strip')).toHaveTextContent('价格可能延迟');
    expect(screen.getByTestId('portfolio-consumer-data-notice')).toHaveTextContent('当前估值可能存在延迟，仅供参考。');
    expect(screen.queryByTestId('portfolio-setup-path')).not.toBeInTheDocument();
    expect(valuationPanel).not.toHaveTextContent('Provider Ops');
    expect(valuationPanel).not.toHaveTextContent('数据源设置');
    expect(screen.getByTestId('portfolio-bento-page').textContent || '').not.toMatch(/provider|api key|setup|remediation|sourceAuthority|confidenceCap|reason_codes|fallback/i);
  });

  it('maps current valuation lineage state to consumer-safe positive trust copy', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({
      includePosition: false,
      fxStale: false,
      valuationLineageState: 'current',
    }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const valuationTrust = screen.getByTestId('portfolio-valuation-trust-strip');
    expect(valuationTrust).toHaveTextContent('估值已更新');
    expect(screen.getByTestId('portfolio-bento-page').textContent || '').not.toMatch(/current|valuationLineageState/i);
    expect(screen.queryByTestId('portfolio-consumer-data-notice')).not.toBeInTheDocument();
  });

  it.each([
    ['price_fallback', '当前估值可能存在延迟，仅供参考。'],
    ['fx_stale', '当前估值可能存在延迟，仅供参考。'],
    ['fx_fallback_1_to_1', '部分汇率数据暂不可用，估值已暂停更新。'],
    ['partial_cash', '现金流水不完整，估值仅供参考。'],
  ])('maps valuation lineage state %s to consumer-safe notice copy', async (valuationLineageState, expectedNotice) => {
    getSnapshot.mockResolvedValue(makeSnapshot({
      includePosition: false,
      fxStale: false,
      valuationLineageState,
    }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const valuationTrust = screen.getByTestId('portfolio-valuation-trust-strip');
    expect(screen.getByTestId('portfolio-consumer-data-notice')).toHaveTextContent(expectedNotice);
    expect(valuationTrust.textContent || '').not.toContain(valuationLineageState);
    expect(screen.getByTestId('portfolio-bento-page').textContent || '').not.toContain(valuationLineageState);
  });

  it('does not leak nested valuation lineage diagnostics or raw provider fields into the consumer DOM', async () => {
    const snapshot = makeSnapshot({
      includePosition: false,
      fxStale: false,
      valuationLineageState: 'fx_fallback_1_to_1',
    }) as ReturnType<typeof makeSnapshot> & Record<string, unknown>;
    snapshot.riskDiagnostics = {
      valuationLineage: {
        state: 'price_fallback',
        summary: 'source_refs required_evidence admin_diagnostics provider cache raw source reason',
        details: {
          source_refs: ['provider_cache_source_reason'],
          required_evidence: ['provider_authority'],
          admin_diagnostics: {
            provider: 'raw_provider_name',
            cache: 'cache_layer',
            source: 'source_ref',
            reason_code: 'internal_reason_code',
            raw_payload: { valuationLineage: 'nested_raw_lineage' },
          },
        },
        issues: [
          {
            code: 'provider_cache_source_reason',
            label: 'raw provider cache source reason',
            detail: 'admin_diagnostics raw JSON',
          },
        ],
      },
    };
    snapshot.portfolioRiskEvidence = {
      limitationLabels: ['仅供风险观察'],
    };
    getSnapshot.mockResolvedValue(snapshot);

    const { container } = render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(screen.getByTestId('portfolio-consumer-data-notice')).toHaveTextContent('部分汇率数据暂不可用，估值已暂停更新。');
    expect(container.textContent || '').not.toMatch(
      /valuationLineage|source_refs|required_evidence|admin_diagnostics|provider|cache|raw|source|reason|fx_fallback_1_to_1|price_fallback/i,
    );
  });

  it('shows unavailable FX copy without surfacing raw evidence metadata in the default portfolio UI', async () => {
    const snapshot = makeSnapshot({
      includePosition: true,
      fxStale: true,
      fxRates: [
        {
          fromCurrency: 'USD',
          toCurrency: 'CNY',
          rate: null,
          rateDate: null,
          source: 'missing',
          isStale: true,
          updatedAt: null,
          sourceDirection: 'fallback_1_to_1',
        },
      ],
    }) as ReturnType<typeof makeSnapshot> & Record<string, unknown>;
    snapshot.fxFreshnessState = 'missing';
    snapshot.valuationLineageState = 'fx_fallback_1_to_1';
    snapshot.confidenceCap = {
      value: 55,
      reasonCodes: ['fx_fallback_1_to_1', 'price_fallback', 'provider_timeout'],
      limitation_labels: ['仅供风险观察'],
    };
    snapshot.portfolioRiskEvidence = {
      limitationLabels: ['FX 汇率缺失', 'sourceRefs', 'provider cache runtime debug'],
      sourceRefs: [
        { id: 'fx-source-1', provider: 'provider-a', sourceClass: 'cache_snapshot' },
      ],
      adminDiagnostics: {
        provider: 'provider-a',
        cache: 'portfolio_fx_cache',
        runtime: 'stale_refresh',
        debug: true,
      },
    };
    getSnapshot.mockResolvedValue(snapshot);

    const { container } = render(<PortfolioPage />);

    await waitForInitialLoad();
    openPortfolioDataNotes();
    fireEvent.click(getLeftTabButton('汇率'));

    expect(screen.getByTestId('portfolio-consumer-data-notice')).toHaveTextContent('部分汇率数据暂不可用，估值已暂停更新。');
    expect(screen.getByTestId('portfolio-valuation-panel')).toHaveTextContent('折算暂不可用');
    expect(screen.getByTestId('portfolio-risk-trust-strip')).toHaveTextContent('汇率暂不可用');
    expect(screen.getByTestId('portfolio-fx-panel')).toHaveTextContent('汇率待确认');
    expect(container.textContent || '').not.toMatch(
      /sourceRefs|source_refs|reasonCodes|reason_codes|provider|cache|runtime|debug|fx_fallback_1_to_1|price_fallback/i,
    );
  });

  it('keeps native exposure visible when FX conversion is unavailable', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true, fxStale: true }));

    render(<PortfolioPage />);

    await waitForInitialLoad();
    openPortfolioDataNotes();
    fireEvent.click(within(screen.getByTestId('portfolio-exposure-card')).getByRole('button', { name: '币种' }));

    const exposure = screen.getByTestId('portfolio-exposure-card');
    expect(exposure).toHaveTextContent('折算暂不可用');
    expect(exposure).toHaveTextContent('USD 1,600.00');
    expect(screen.getByTestId('portfolio-consumer-data-notice')).toHaveTextContent('当前估值可能存在延迟，仅供参考。');
    expect(screen.getByTestId('portfolio-risk-card')).toHaveTextContent('汇率数据暂不可用');
  });

  it('renders missing market category cleanly without raw unknown text', async () => {
    const snapshot = makeSnapshot({ includePosition: true, fxStale: false });
    snapshot.analytics.exposure.byMarket = [
      {
        key: 'unknown',
        label: 'UNKNOWN',
        marketValue: 1600,
        displayValue: 1600,
        displayCurrency: 'USD',
        percent: 100,
        fxStatus: 'live' as const,
        market: 'unknown',
        holdingCount: 1,
      },
    ];
    snapshot.analytics.risk = {
      ...snapshot.analytics.risk,
      largestMarket: snapshot.analytics.exposure.byMarket[0],
    };
    getSnapshot.mockResolvedValue(snapshot);

    render(<PortfolioPage />);

    await waitForInitialLoad();
    openPortfolioDataNotes();

    fireEvent.click(within(screen.getByTestId('portfolio-exposure-card')).getByRole('button', { name: '市场' }));
    const exposure = screen.getByTestId('portfolio-exposure-card');
    expect(exposure).toHaveTextContent('暂无市场分类');
    expect(exposure).not.toHaveTextContent('UNKNOWN');
    expect(screen.getByTestId('portfolio-risk-card')).toHaveTextContent('暂无市场分类');
  });

  it('shows the disabled trade reason if the trade account is all accounts', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.change(screen.getByLabelText(/记账账户|ledger account/i), { target: { value: 'all' } });

    const tradeStation = screen.getByTestId('portfolio-trade-station-card');
    expect(within(tradeStation).getByText('请选择具体账户后保存持仓流水')).toBeInTheDocument();
    expect(within(tradeStation).getByRole('button', { name: translate('zh', 'portfolio.submitTrade') })).toBeDisabled();
  });

  it('reads display currency from shared settings storage and converts totals and holdings without hiding original currency', async () => {
    window.localStorage.setItem(PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY, 'USD');
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true, fxStale: false }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(screen.getByTestId('portfolio-command-strip')).toContainElement(screen.getByTestId('portfolio-display-currency-select'));
    expect(screen.getByTestId('portfolio-total-assets-value')).toHaveTextContent('USD 414.08');
    expect(screen.getAllByText('USD 1,600.00').length).toBeGreaterThan(0);
    expect(screen.getAllByText('+USD 100.00').length).toBeGreaterThan(0);
    expect(screen.queryByTestId('portfolio-row-macro')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /手工记账台|Trade Station/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '汇率' })).toBeInTheDocument();
  });

  it('migrates the legacy portfolio display currency key to the shared settings key', async () => {
    window.localStorage.setItem(LEGACY_PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY, 'HKD');
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true, fxStale: false }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(window.localStorage.getItem(PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY)).toBe('HKD');
    expect(screen.queryByTestId('portfolio-row-macro')).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-total-assets-value')).toHaveTextContent('HKD 3,257.33');
  });

  it('shows an exchange-rate unavailable state instead of fake converted values when a display rate is missing', async () => {
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

    expect(screen.getAllByText('USD 1,600.00').length).toBeGreaterThan(0);
    expect(screen.getByTestId('portfolio-valuation-panel')).toHaveTextContent('折算暂不可用');
    expect(screen.getByTestId('portfolio-consumer-data-notice')).toHaveTextContent('部分汇率数据暂不可用，估值已暂停更新。');
    expect(screen.queryByText(/≈ CNY/)).not.toBeInTheDocument();
  });

  it('refreshes portfolio data after trade submit, disables duplicate submit, and shows compact feedback', async () => {
    const pendingTrade = deferredPromise<{ id: number }>();
    createTrade.mockImplementationOnce(() => pendingTrade.promise);
    getSnapshot
      .mockResolvedValueOnce(makeSnapshot({ includePosition: false }))
      .mockResolvedValueOnce(makeSnapshot({ includePosition: true }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.change(screen.getByLabelText(p('stockCode')), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText(p('quantity')), { target: { value: '10' } });
    fireEvent.change(screen.getByLabelText(p('price')), { target: { value: '160' } });

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
    expect(await screen.findByTestId('portfolio-trade-feedback')).toHaveTextContent('AAPL 暴露增加已保存 · 已刷新持仓');
    expect(screen.getByLabelText(p('stockCode'))).toHaveValue('');
  });

  it('infers settlement currency from US, HK, A-share, and crypto symbols with manual override', async () => {
    getAccounts.mockResolvedValueOnce(makeAccounts([
      { id: 1, name: 'US Account', market: 'us', baseCurrency: 'USD' },
      { id: 2, name: 'HK Account', market: 'hk', baseCurrency: 'HKD' },
      { id: 3, name: 'CN Account', market: 'cn', baseCurrency: 'CNY' },
    ]));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const symbolInput = screen.getByLabelText(p('stockCode'));
    const settlementSelect = screen.getByLabelText(p('currency')) as HTMLSelectElement;

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

    fireEvent.change(screen.getByLabelText(p('stockCode')), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText(p('quantity')), { target: { value: '10' } });
    fireEvent.change(screen.getByLabelText(p('price')), { target: { value: '160' } });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'portfolio.submitTrade') }));

    expect(await screen.findByTestId('portfolio-trade-feedback')).toHaveTextContent('余额不足');
    expect(screen.getByLabelText(p('stockCode'))).toHaveValue('AAPL');
  });

  it('switches left tabs between trade, account, sync, and fx surfaces', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(screen.getByText(translate('zh', 'portfolio.manualTrade'))).toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.createAccountTitle'))).not.toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.dataSyncTitle'))).not.toBeInTheDocument();

    fireEvent.click(getLeftTabButton('账户'));
    expect(screen.getAllByText(translate('zh', 'portfolio.createAccountTitle')).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: translate('zh', 'portfolio.createAccount') })).toBeInTheDocument();

    fireEvent.click(getLeftTabButton('同步'));
    expect(screen.getByText(translate('zh', 'portfolio.dataSyncTitle'))).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'portfolio.currentImportAccount'))).toBeInTheDocument();

    fireEvent.click(getLeftTabButton('汇率'));
    expect(screen.getByTestId('portfolio-fx-panel')).toBeInTheDocument();
    expect(screen.getByText('汇率参考')).toBeInTheDocument();
    expect(screen.getByLabelText('基准币种')).toHaveValue('USD');
    expect(screen.getByLabelText('报价币种')).toHaveValue('CNY');
    expect(screen.getByText('USD/CNY')).toBeInTheDocument();
    expect(screen.getByTestId('portfolio-fx-rate-value')).toHaveTextContent('1 USD = 7.2450 CNY');
    const refreshFxButton = openFxPanel();
    expect(refreshFxButton).toHaveAttribute('data-variant', 'primary');
    expect(refreshFxButton.className).toContain('border-[color:var(--wolfy-accent)]');
    expect(refreshFxButton.className).toContain('bg-[var(--wolfy-accent)]');
    expect(refreshFxButton).toHaveTextContent(translate('zh', 'portfolio.refreshFx'));
    expect(screen.getByText('汇率已更新')).toBeInTheDocument();
  });

  it('renders account and sync forms with Chinese-first drawer labels', async () => {
    listImportBrokers.mockResolvedValueOnce({
      brokers: [
        { broker: 'huatai', aliases: [], displayName: '华泰', fileExtensions: ['csv'] },
        { broker: 'ibkr', aliases: ['interactivebrokers'], displayName: 'Interactive Brokers', fileExtensions: ['xml'] },
      ],
    });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(screen.getByLabelText('记账账户')).toBeInTheDocument();
    expect(screen.getByLabelText('成本方法')).toBeInTheDocument();
    expect(screen.queryByText('LEDGER ACCOUNT')).not.toBeInTheDocument();
    expect(screen.queryByText('COST METHOD')).not.toBeInTheDocument();

    fireEvent.click(getLeftTabButton('账户'));
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'portfolio.createAccount') }));

    expect(screen.getByLabelText('账户名称')).toBeInTheDocument();
    expect(screen.getByLabelText('券商')).toHaveValue('Demo');
    expect(screen.getByLabelText('基准币种')).toHaveValue('CNY');
    expect(screen.getByLabelText('市场范围')).toHaveValue('cn');
    expect(screen.queryByText('ACCOUNT NAME')).not.toBeInTheDocument();
    expect(screen.queryByText('BROKER')).not.toBeInTheDocument();
    expect(screen.queryByText('BASE CCY')).not.toBeInTheDocument();
    expect(screen.queryByText('MARKET')).not.toBeInTheDocument();

    fireEvent.click(getLeftTabButton('同步'));

    const brokerSelect = screen.getByLabelText('导入来源') as HTMLSelectElement;
    expect(brokerSelect).toHaveValue('huatai');
    fireEvent.change(brokerSelect, { target: { value: 'ibkr' } });

    expect(brokerSelect).toHaveValue('ibkr');
    expect(Array.from(brokerSelect.options).map((option) => option.textContent).join(' ')).toContain('Interactive Brokers');
    expect(screen.getByLabelText('IBKR API 地址')).toHaveValue('https://localhost:5000/v1/api');
    expect(screen.getByLabelText('IBKR 账户引用')).toBeInTheDocument();
    expect(screen.getByLabelText('IBKR 会话令牌')).toBeInTheDocument();
    expect(screen.queryByText('API BASE')).not.toBeInTheDocument();
    expect(screen.queryByText('ACCOUNT REF')).not.toBeInTheDocument();
    expect(screen.queryByText('SESSION TOKEN')).not.toBeInTheDocument();
  });

  it('confirms account deletion and falls back to the next active account', async () => {
    getAccounts
      .mockResolvedValueOnce(makeAccounts([{ id: 1, name: 'Main' }, { id: 2, name: 'Alt' }]))
      .mockResolvedValueOnce(makeAccounts([{ id: 2, name: 'Alt' }]));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const accountSelect = screen.getByLabelText(/记账账户|ledger account/i) as HTMLSelectElement;
    fireEvent.change(accountSelect, { target: { value: '1' } });
    fireEvent.click(getLeftTabButton('账户'));
    fireEvent.click(screen.getByRole('button', { name: '删除 Main' }));

    expect(await screen.findByText(translate('zh', 'portfolio.accountDeleteMessage'))).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'portfolio.deleteConfirm') }));

    await waitFor(() => expect(deleteAccount).toHaveBeenCalledWith(1));
    await waitFor(() => expect((screen.getByLabelText(/记账账户|ledger account/i) as HTMLSelectElement).value).toBe('2'));
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

    await waitFor(() => expect(listBrokerConnections).toHaveBeenCalledWith(1));
    fireEvent.click(getLeftTabButton('同步'));

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

    await waitFor(() => expect(listBrokerConnections).toHaveBeenCalledWith(1));
    fireEvent.click(getLeftTabButton('同步'));

    const brokerSelect = screen.getAllByRole('combobox').find((element) =>
      (element as HTMLSelectElement).value === 'huatai'
    ) as HTMLSelectElement;
    fireEvent.change(brokerSelect, { target: { value: 'ibkr' } });

    fireEvent.change(
      screen.getByPlaceholderText(translate('zh', 'portfolio.ibkrSessionTokenPlaceholder')),
      { target: { value: 'unit-test-not-a-real-session' } },
    );
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'portfolio.syncIbkr') }));

    await waitFor(() => expect(syncIbkrReadOnly).toHaveBeenCalledWith({
      accountId: 1,
      brokerConnectionId: 9,
      brokerAccountRef: 'U1234567',
      sessionToken: 'unit-test-not-a-real-session',
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

    await waitFor(() => expect(listBrokerConnections).toHaveBeenCalledWith(1));
    fireEvent.click(getLeftTabButton('同步'));

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
    expect(brokerSelect.value).toBe('ibkr');
    const syncResultCard = screen.getByText(translate('zh', 'portfolio.syncResult')).closest('div');
    expect(syncResultCard?.textContent || '').toContain(`${translate('zh', 'portfolio.positionsCountLabel')} 1`);
    expect(syncResultCard?.textContent || '').toContain(`${translate('zh', 'portfolio.cashCurrenciesLabel')} 1`);
    expect(syncResultCard?.textContent || '').toContain('USD 6,600.00');
  });

  it('refreshes exchange rates from the visible exchange-rate surface and only reloads snapshot/risk', async () => {
    getSnapshot
      .mockResolvedValueOnce(makeSnapshot({ fxStale: true }))
      .mockResolvedValueOnce(makeSnapshot({ fxStale: false }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const snapshotCallsBeforeRefresh = getSnapshot.mock.calls.length;
    const riskCallsBeforeRefresh = getRisk.mock.calls.length;
    const tradeCallsBeforeRefresh = listTrades.mock.calls.length;

    const refreshFxButton = openFxPanel();
    await waitFor(() => expect(refreshFxButton).not.toBeDisabled());
    fireEvent.click(refreshFxButton);

    await waitFor(() => expect(refreshFxRate).toHaveBeenCalledWith({ base: 'USD', quote: 'CNY' }));
    expect(await screen.findByText('汇率数据已更新。')).toBeInTheDocument();
    await waitFor(() => expect(getSnapshot).toHaveBeenCalledTimes(snapshotCallsBeforeRefresh + 1));
    await waitFor(() => expect(getRisk).toHaveBeenCalledTimes(riskCallsBeforeRefresh + 1));
    expect(listTrades).toHaveBeenCalledTimes(tradeCallsBeforeRefresh);
    expect(listCashLedger).not.toHaveBeenCalled();
    expect(listCorporateActions).not.toHaveBeenCalled();
    expect(screen.getByTestId('portfolio-fx-rate-value')).toHaveTextContent('1 USD = 7.2468 CNY');
  });

  it('shows consumer-safe warning feedback when exchange-rate refresh remains stale', async () => {
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

    expect(await screen.findByText('部分汇率数据暂不可用，估值已暂停更新。')).toBeInTheDocument();
    expect(screen.queryByText('缓存')).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-fx-panel')).not.toHaveTextContent(/frankfurter|CACHE|fallback|cache/i);
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

    const costMethodSelect = screen.getByLabelText(/成本方法|COST METHOD/);

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

    expect(screen.getByRole('heading', { name: /总资产|Total Assets/ })).toBeInTheDocument();
    expect(getLeftTabButton('Ledger')).toBeInTheDocument();
    expect(getLeftTabButton('Account')).toBeInTheDocument();
    expect(getLeftTabButton('Sync')).toBeInTheDocument();
    expect(screen.getByTestId('portfolio-current-holdings-panel')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'History ↗' })).not.toBeInTheDocument();
    expect(within(screen.getByTestId('portfolio-start-card')).getByText('Create or import the first portfolio')).toBeInTheDocument();
    expect(openFxPanel('en')).toBeInTheDocument();

    fireEvent.click(getLeftTabButton('Sync'));
    expect(screen.getByText(translate('en', 'portfolio.dataSyncTitle'))).toBeInTheDocument();
  });

  it('renders localized English exchange-rate refresh feedback on /en routes', async () => {
    window.history.replaceState(window.history.state, '', '/en/portfolio');

    render(
      <UiLanguageProvider>
        <PortfolioPage />
      </UiLanguageProvider>,
    );

    await waitForInitialLoad();

    fireEvent.click(openFxPanel('en'));

    expect(await screen.findByText('Exchange-rate data updated.')).toBeInTheDocument();
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

    fireEvent.change(screen.getByLabelText(/记账账户|ledger account/i), { target: { value: '1' } });
    await waitFor(() => expect(listBrokerConnections).toHaveBeenCalledWith(1));
    fireEvent.click(getLeftTabButton('Sync'));
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

    fireEvent.change(screen.getByLabelText(/记账账户|ledger account/i), { target: { value: '1' } });
    await waitFor(() => expect(listBrokerConnections).toHaveBeenCalledWith(1));
    fireEvent.click(getLeftTabButton('同步'));
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
    expect(screen.getByRole('heading', { name: /手工记账台|Trade Station/ })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /Current Holdings/i })).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-start-card')).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'portfolio.manualTrade'))).toBeInTheDocument();
    expect(within(screen.getByTestId('portfolio-start-card')).getByText('创建或导入首个组合')).toBeInTheDocument();
  });

  it('frames the default portfolio editor as a manual ledger without trade or order wording', async () => {
    const { container } = render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(container).toHaveTextContent('手工记账台');
    expect(container).toHaveTextContent('手工记账入口');
    expect(container).toHaveTextContent('持仓流水');
    expect(container).toHaveTextContent('保存记录');
    expect(container).toHaveTextContent('记录日期');
    expect(container).toHaveTextContent('持仓变动');
    expect(container).toHaveTextContent('暴露增加');
    expect(container).toHaveTextContent('暴露减少');
    expect(container).not.toHaveTextContent('交易工作台');
    expect(container).not.toHaveTextContent('股票买卖');
    expect(container).not.toHaveTextContent('提交交易');
    expect(container).not.toHaveTextContent('下单');
    expect(container).not.toHaveTextContent('订单执行');
    expect(container).not.toHaveTextContent('买入');
    expect(container).not.toHaveTextContent('卖出');
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
    expect(totalAssetsCard.className).toContain('min-w-0');
    expect(screen.getByTestId('portfolio-account-status-strip').className).toContain('rounded-[14px]');
    expect(screen.getByTestId('portfolio-account-status-strip').className).toContain('bg-[var(--wolfy-surface-console)]');

    const summaryBlock = screen.getByTestId('portfolio-trade-station-summary');
    expect(summaryBlock.className).toContain('flex');
    expect(summaryBlock.className).toContain('flex-col');
    expect(summaryBlock.className).toContain('gap-1');
    expect(summaryBlock.className).toContain('py-2');

    expect(screen.getByRole('button', { name: '持仓流水' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '资金划转' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: '公司行为' }).length).toBeGreaterThan(0);
    expect(screen.getByText(translate('zh', 'portfolio.manualTrade'))).toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.manualCash'))).not.toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.manualCorporate'))).not.toBeInTheDocument();
    expect(screen.getByLabelText(p('stockCode'))).toHaveClass('rounded-lg');
    expect(screen.getByLabelText(p('tradeDate'))).toBeInTheDocument();
    expect(screen.getByLabelText(p('sideLabel'))).toBeInTheDocument();
    expect(screen.getByLabelText(p('quantity'))).toBeInTheDocument();
    expect(screen.getByLabelText(p('price'))).toBeInTheDocument();
    expect(screen.getByLabelText(p('currency'))).toBeInTheDocument();
    expect(screen.getByLabelText(p('feeOptional'))).toBeInTheDocument();
    expect(screen.getByLabelText(p('taxOptional'))).toBeInTheDocument();
    expect(screen.getByLabelText(p('reference'))).toBeInTheDocument();
    expect(screen.getByLabelText(p('note'))).toBeInTheDocument();

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

    const amountInput = screen.getByLabelText(p('amount'));
    expect(amountInput.className).toContain('input-surface');
    expect(amountInput.className).toContain('rounded-lg');
    expect(screen.getByLabelText(p('eventDate'))).toBeInTheDocument();
    expect(screen.getByLabelText(p('direction'))).toBeInTheDocument();
    expect(screen.getByLabelText(p('currency'))).toBeInTheDocument();
    expect(screen.getByLabelText(p('note'))).toBeInTheDocument();

    fireEvent.click(within(screen.getByTestId('portfolio-trade-type-switcher')).getByRole('button', { name: '公司行为' }));
    expect(screen.getByText(translate('zh', 'portfolio.manualCorporate'))).toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.manualTrade'))).not.toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.manualCash'))).not.toBeInTheDocument();
    expect(screen.getByLabelText(p('effectiveDate'))).toBeInTheDocument();
    expect(screen.getByLabelText(p('actionType'))).toBeInTheDocument();
    expect(screen.getByLabelText(p('stockCode'))).toBeInTheDocument();
    expect(screen.getByLabelText(p('note'))).toBeInTheDocument();
  });

  it('uses mobile holding cards at 390px while keeping the desktop holdings table from md up', async () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 390 });
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true, fxStale: false }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const primaryLane = screen.getByTestId('portfolio-primary-lane');
    const holdingsPanel = screen.getByTestId('portfolio-current-holdings-panel');
    const mobileList = within(holdingsPanel).getByTestId('portfolio-holdings-mobile-list');
    const mobileCard = within(mobileList).getByTestId('portfolio-holding-mobile-card-AAPL');
    const desktopTable = within(holdingsPanel).getByRole('table');
    const desktopShell = desktopTable.closest('[data-terminal-primitive="dense-table"]');

    expect(primaryLane).toHaveClass('min-w-0');
    expect(mobileList).toHaveClass('md:hidden');
    expect(mobileCard).toHaveTextContent('AAPL');
    expect(mobileCard).toHaveTextContent('市值');
    expect(mobileCard).toHaveTextContent('手工记账');
    expect(within(mobileCard).getByTestId('portfolio-holding-mobile-trust-AAPL')).toHaveTextContent('价格快照');
    expect(desktopTable).toHaveClass('min-w-[760px]');
    expect(desktopShell).toHaveClass('hidden', 'md:block');
  });

  it('renders the full-width order history panel and shows event filters', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const activityLane = screen.getByTestId('portfolio-activity-lane');
    const historyPanel = screen.getByTestId('portfolio-history-full');
    expect(activityLane).toContainElement(historyPanel);
    expect(within(historyPanel).getByRole('heading', { name: '历史记录' })).toBeInTheDocument();
    expect(within(historyPanel).getByRole('button', { name: translate('zh', 'portfolio.tradeLedger') })).toBeInTheDocument();
    expect(within(historyPanel).getByRole('button', { name: translate('zh', 'portfolio.cashLedger') })).toBeInTheDocument();
    expect(within(historyPanel).getByRole('button', { name: translate('zh', 'portfolio.corporateLedger') })).toBeInTheDocument();
    expect(within(historyPanel).getByRole('button', { name: translate('zh', 'portfolio.refreshLedger') })).toBeInTheDocument();
  });

  it('resets history to page 1 before retargeting account-scope queries', async () => {
    getAccounts.mockResolvedValue(makeAccounts([
      { id: 1, name: 'Main', baseCurrency: 'CNY', market: 'us' },
      { id: 2, name: 'Alt', baseCurrency: 'USD', market: 'us' },
    ]));
    getSnapshot.mockImplementation(async ({ accountId }: { accountId?: number } = {}) =>
      makeSnapshot({ accountId, includePosition: true, fxStale: false })
    );
    listTrades.mockImplementation(async ({ accountId, page }: { accountId?: number; page: number }) => ({
      items: Array.from({ length: 20 }, (_, index) => ({
        id: (accountId ?? 0) * 1000 + page * 100 + index,
        accountId: accountId ?? 1,
        symbol: `T${accountId ?? 'all'}-${page}-${index}`,
        market: 'us',
        tradeDate: '2026-03-18',
        side: 'buy',
        quantity: 1,
        price: 100 + index,
        fee: 0,
        tax: 0,
        currency: 'USD',
        note: null,
        isActive: true,
        voidedAt: null,
        createdAt: '2026-03-18T00:00:00Z',
        updatedAt: '2026-03-18T00:00:00Z',
      })),
      total: 40,
      page,
      pageSize: 20,
    }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const historyPanel = screen.getByTestId('portfolio-history-full');
    fireEvent.click(within(historyPanel).getByRole('button', { name: translate('zh', 'portfolio.nextPage') }));

    await waitFor(() => {
      expect(listTrades.mock.calls.map(([args]) => args)).toContainEqual(expect.objectContaining({
        accountId: undefined,
        page: 2,
      }));
    });

    const accountViewSelect = within(screen.getByTestId('portfolio-command-strip')).getByLabelText(
      translate('zh', 'portfolio.accountView'),
    ) as HTMLSelectElement;
    fireEvent.change(accountViewSelect, { target: { value: '2' } });

    await waitFor(() => {
      expect(accountViewSelect.value).toBe('2');
      const scopedCalls = listTrades.mock.calls.map(([args]) => ({ accountId: args.accountId, page: args.page }));
      expect(scopedCalls).toContainEqual({ accountId: 2, page: 1 });
    });

    const scopedCalls = listTrades.mock.calls.map(([args]) => ({ accountId: args.accountId, page: args.page }));
    expect(scopedCalls).not.toContainEqual({ accountId: 2, page: 2 });
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
    expect(within(dialog).getByLabelText(p('tradeDate'))).toBeInTheDocument();
    expect(within(dialog).getByLabelText(p('sideLabel'))).toBeInTheDocument();
    expect(within(dialog).getByLabelText(p('quantity'))).toBeInTheDocument();
    expect(within(dialog).getByLabelText(p('price'))).toBeInTheDocument();
    expect(within(dialog).getByLabelText(p('currency'))).toBeInTheDocument();
    expect(within(dialog).getByLabelText(p('feeOptional'))).toBeInTheDocument();
    expect(within(dialog).getByLabelText(p('taxOptional'))).toBeInTheDocument();
    expect(within(dialog).getByLabelText(p('note'))).toBeInTheDocument();

    fireEvent.change(within(dialog).getByLabelText(p('quantity')), { target: { value: '2' } });
    fireEvent.change(within(dialog).getByLabelText(p('price')), { target: { value: '101' } });
    fireEvent.click(within(dialog).getByRole('button', { name: '保存修改' }));

    await waitFor(() => expect(updateTrade).toHaveBeenCalledWith(7, expect.objectContaining({
      quantity: 2,
      price: 101,
    })));
    await waitFor(() => expect(getSnapshot).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('持仓流水已更新 · 持仓已刷新')).toBeInTheDocument();
  });

  it('re-derives edit currency from the current symbol scope until the user overrides it', async () => {
    getAccounts.mockResolvedValue(makeAccounts([
      { id: 1, name: 'Main', baseCurrency: 'CNY', market: 'cn' },
      { id: 2, name: 'HK Account', baseCurrency: 'HKD', market: 'hk' },
    ]));
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true }));
    listTrades.mockResolvedValue({
      items: [
        {
          id: 7,
          accountId: 1,
          symbol: '',
          market: 'cn',
          tradeDate: '2026-03-18',
          side: 'buy',
          quantity: 1,
          price: 100,
          fee: 0,
          tax: 0,
          currency: 'CNY',
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
    const accountSelect = within(dialog).getByLabelText('账户') as HTMLSelectElement;
    const currencySelect = within(dialog).getByLabelText(p('currency')) as HTMLSelectElement;

    expect(currencySelect).toHaveValue('CNY');

    fireEvent.change(accountSelect, { target: { value: '2' } });
    expect(currencySelect).toHaveValue('HKD');

    fireEvent.change(currencySelect, { target: { value: 'USD' } });
    fireEvent.change(accountSelect, { target: { value: '1' } });
    expect(currencySelect).toHaveValue('USD');
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
    fireEvent.change(within(dialog).getByLabelText(p('quantity')), { target: { value: '2' } });
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
    expect(await screen.findByText('确认作废持仓流水？')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '确认作废' }));

    await waitFor(() => expect(deleteTrade).toHaveBeenCalledWith(7));
    await waitFor(() => expect(getSnapshot).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('持仓流水已作废 · 持仓已刷新')).toBeInTheDocument();

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

  it('shows permanent non-recoverable copy before deleting cash and corporate records', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true }));
    listCashLedger.mockResolvedValueOnce({
      items: [
        { id: 3, accountId: 1, eventDate: '2026-03-17', direction: 'in', amount: 1000, currency: 'USD', note: 'seed', createdAt: '2026-03-17T00:00:00Z' },
      ],
      total: 1,
      page: 1,
      pageSize: 20,
    });
    listCorporateActions.mockResolvedValueOnce({
      items: [
        {
          id: 4,
          accountId: 1,
          symbol: 'AAPL',
          market: 'us',
          currency: 'USD',
          effectiveDate: '2026-03-16',
          actionType: 'cash_dividend',
          cashDividendPerShare: 0.5,
          splitRatio: null,
          note: 'seed',
          createdAt: '2026-03-16T00:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      pageSize: 20,
    });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    let historyPanel = screen.getByTestId('portfolio-history-full');
    fireEvent.click(within(historyPanel).getByRole('button', { name: translate('zh', 'portfolio.cashLedger') }));
    expect(await screen.findByText('2026-03-17 · USD 1,000.00')).toBeInTheDocument();
    fireEvent.click(within(screen.getByTestId('portfolio-history-full')).getByRole('button', { name: translate('zh', 'portfolio.deleteConfirm') }));

    expect(await screen.findByText('永久删除 2026-03-17 的资金流水（流入 1000 USD）吗？此操作不可恢复，仅删除这条记录，不会自动重建。')).toBeInTheDocument();
    expect(deleteCashLedger).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText(translate('zh', 'portfolio.deleteConfirm')));
    await waitFor(() => expect(deleteCashLedger).toHaveBeenCalledWith(3));

    historyPanel = screen.getByTestId('portfolio-history-full');
    fireEvent.click(within(historyPanel).getByRole('button', { name: translate('zh', 'portfolio.corporateLedger') }));
    expect(await screen.findByText('2026-03-16 · 每股分红 0.5')).toBeInTheDocument();
    fireEvent.click(within(screen.getByTestId('portfolio-history-full')).getByRole('button', { name: translate('zh', 'portfolio.deleteConfirm') }));

    expect(await screen.findByText('永久删除 2026-03-16 的公司行为 现金分红（AAPL）吗？此操作不可恢复，仅删除这条记录，不会自动重建。')).toBeInTheDocument();
    expect(deleteCorporateAction).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText(translate('zh', 'portfolio.deleteConfirm')));
    await waitFor(() => expect(deleteCorporateAction).toHaveBeenCalledWith(4));
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
    fireEvent.click(within(historyPanel).getByRole('button', { name: translate('zh', 'portfolio.cashLedger') }));
    await waitFor(() => expect(listCashLedger).toHaveBeenCalled());

    fireEvent.click(within(historyPanel).getByRole('button', { name: translate('zh', 'portfolio.corporateLedger') }));
    await waitFor(() => expect(listCorporateActions).toHaveBeenCalled());

    expect(screen.queryByTestId('portfolio-attribution-dashboard')).not.toBeInTheDocument();
  });

  it('keeps current holdings and history in the same workspace', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const holdingsPanel = screen.getByTestId('portfolio-current-holdings-panel');
    const primaryLane = screen.getByTestId('portfolio-primary-lane');
    const secondaryLane = screen.getByTestId('portfolio-secondary-lane');
    const activityLane = screen.getByTestId('portfolio-activity-lane');
    const manualLane = screen.getByTestId('portfolio-manual-lane');
    const tradeStation = screen.getByTestId('portfolio-trade-station-card');
    expect(within(holdingsPanel).getByRole('heading', { name: /当前持仓/ })).toBeInTheDocument();
    const historyPanel = screen.getByTestId('portfolio-history-full');
    expect(historyPanel).toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-history-drawer')).not.toBeInTheDocument();
    expect(primaryLane).toContainElement(holdingsPanel);
    expect(secondaryLane).toContainElement(screen.getByTestId('portfolio-risk-card'));
    expect(activityLane).toContainElement(historyPanel);
    expect(manualLane).toContainElement(tradeStation);
    expect(Boolean(holdingsPanel.compareDocumentPosition(historyPanel) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(screen.getByTestId('portfolio-risk-card').compareDocumentPosition(tradeStation) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it('resets IBKR connection-derived fields on trade-account changes while preserving the typed session token', async () => {
    getAccounts.mockResolvedValue(makeAccounts([
      { id: 1, name: 'Main', baseCurrency: 'USD', market: 'us' },
      { id: 2, name: 'Alt', baseCurrency: 'HKD', market: 'hk' },
    ]));
    listImportBrokers.mockResolvedValueOnce({
      brokers: [
        { broker: 'huatai', aliases: [], displayName: '华泰', fileExtensions: ['csv'] },
        { broker: 'ibkr', aliases: ['interactivebrokers'], displayName: 'Interactive Brokers', fileExtensions: ['xml'] },
      ],
    });
    listBrokerConnections.mockImplementation(async (accountId: number) => {
      if (accountId === 2) {
        return {
          connections: [
            {
              id: 12,
              portfolioAccountId: 2,
              connectionName: 'Secondary IBKR',
              brokerType: 'ibkr',
              brokerAccountRef: 'U7654321',
              importMode: 'api',
              status: 'active',
              syncMetadata: {
                ibkrApi: {
                  apiBaseUrl: 'https://localhost:6000/v1/api',
                  verifySsl: true,
                  brokerAccountRef: 'U7654321',
                },
              },
            },
          ],
        };
      }
      return {
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
      };
    });

    render(<PortfolioPage />);

    await waitForInitialLoad();
    fireEvent.click(getLeftTabButton('同步'));

    const brokerSelect = screen.getAllByRole('combobox').find((element) =>
      (element as HTMLSelectElement).value === 'huatai'
    ) as HTMLSelectElement;
    fireEvent.change(brokerSelect, { target: { value: 'ibkr' } });

    expect(await screen.findByText('Primary IBKR')).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(translate('zh', 'portfolio.ibkrSessionTokenPlaceholder')), {
      target: { value: 'session-token-123' },
    });
    fireEvent.change(screen.getByLabelText('IBKR API 地址'), {
      target: { value: 'https://override.local/v1/api' },
    });
    fireEvent.change(screen.getByLabelText('IBKR 账户引用'), {
      target: { value: 'U0000000' },
    });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'portfolio.syncIbkr') }));

    await waitFor(() => expect(syncIbkrReadOnly).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(translate('zh', 'portfolio.syncResult'))).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('IBKR 会话令牌'), {
      target: { value: 'session-token-123' },
    });

    const tradeAccountSelect = screen.getByLabelText(/记账账户|ledger account/i) as HTMLSelectElement;
    fireEvent.change(tradeAccountSelect, { target: { value: '2' } });

    await waitFor(() => expect(listBrokerConnections).toHaveBeenCalledWith(2));
    await waitFor(() => expect(screen.getByText('Secondary IBKR')).toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText(translate('zh', 'portfolio.syncResult'))).not.toBeInTheDocument());
    expect(screen.getByLabelText('IBKR API 地址')).toHaveValue('https://localhost:6000/v1/api');
    expect(screen.getByLabelText('IBKR 账户引用')).toHaveValue('U7654321');
    expect(screen.getByLabelText('IBKR 会话令牌')).toHaveValue('session-token-123');
    expect(screen.getByLabelText(translate('zh', 'portfolio.verifyIbkrSsl'))).toBeChecked();
  });

  it('keeps the rebuilt shell navigable by tabs instead of the removed attribution widgets', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.click(getLeftTabButton('账户'));
    expect(screen.getAllByText(translate('zh', 'portfolio.createAccountTitle')).length).toBeGreaterThan(0);
    expect(screen.queryByText(translate('zh', 'portfolio.manualTrade'))).not.toBeInTheDocument();

    fireEvent.click(getLeftTabButton('同步'));
    expect(screen.getByText(translate('zh', 'portfolio.dataSyncTitle'))).toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.createAccountTitle'))).not.toBeInTheDocument();

    fireEvent.click(getLeftTabButton('记账'));
    expect(screen.getByText(translate('zh', 'portfolio.manualTrade'))).toBeInTheDocument();
  });

  it('does not repeat bootstrap fetches when switching local PortfolioPage tabs', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();
    await waitFor(() => expect(listBrokerConnections).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(listImportBrokers).toHaveBeenCalledTimes(1));

    expect(getAccounts).toHaveBeenCalledTimes(1);
    expect(getSnapshot).toHaveBeenCalledTimes(1);
    expect(getRisk).toHaveBeenCalledTimes(1);
    expect(listTrades).toHaveBeenCalledTimes(1);

    fireEvent.click(getLeftTabButton('账户'));
    fireEvent.click(getLeftTabButton('同步'));
    fireEvent.click(getLeftTabButton('记账'));
    fireEvent.click(screen.getByRole('button', { name: '资金划转' }));
    fireEvent.click(within(screen.getByTestId('portfolio-trade-type-switcher')).getByRole('button', { name: '公司行为' }));
    fireEvent.click(screen.getByRole('button', { name: '持仓流水' }));

    expect(getAccounts).toHaveBeenCalledTimes(1);
    expect(listImportBrokers).toHaveBeenCalledTimes(1);
    expect(listBrokerConnections).toHaveBeenCalledTimes(1);
    expect(getSnapshot).toHaveBeenCalledTimes(1);
    expect(getRisk).toHaveBeenCalledTimes(1);
    expect(listTrades).toHaveBeenCalledTimes(1);
  });
});
