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
const { useProductSurfaceMock } = vi.hoisted(() => ({
  useProductSurfaceMock: vi.fn(),
}));
const SAFE_IBKR_CONNECTION_HANDLE = 'conn_111111111111';
const SAFE_IBKR_ACCOUNT_HANDLE = 'acct_222222222222';
const SAFE_IBKR_URL_HANDLE = 'url_333333333333';
const SAFE_IBKR_SECONDARY_CONNECTION_HANDLE = 'conn_444444444444';
const SAFE_IBKR_SECONDARY_ACCOUNT_HANDLE = 'acct_555555555555';
const SAFE_IBKR_SECONDARY_URL_HANDLE = 'url_666666666666';
const SYNTHETIC_BROKER_IMPORT_RAW_MARKERS = [
  'synthetic_account_label_must_not_leak',
  'synthetic_provider_url_must_not_leak',
  'synthetic_import_fingerprint_must_not_leak',
  'synthetic_broker_connection_name_must_not_leak',
  'synthetic_raw_payload_label_must_not_leak',
  'synthetic_import_file_label_must_not_leak',
  'synthetic_request_id_must_not_leak',
];

const {
  getAccounts,
  getSnapshot,
  getRisk,
  getStructureReview,
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
  getStructureReview: vi.fn(),
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
    getStructureReview,
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

vi.mock('../../hooks/useProductSurface', () => ({
  useProductSurface: () => useProductSurfaceMock(),
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

function setAdminPortfolioSurface() {
  useProductSurfaceMock.mockReturnValue({
    isAdminMode: true,
    canReadProviders: true,
    isAdmin: true,
    isAdminAccount: true,
  });
}

function setConsumerPortfolioSurface() {
  useProductSurfaceMock.mockReturnValue({
    isAdminMode: false,
    canReadProviders: false,
    isAdmin: false,
    isAdminAccount: false,
  });
}

function makeSnapshot(options: {
  accountId?: number;
  fxStale?: boolean;
  accountCount?: number;
  includePosition?: boolean;
  exposureResearchContext?: Record<string, unknown> | null;
  portfolioLineageSummary?: Record<string, unknown> | null;
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
    ...(options.exposureResearchContext !== undefined ? { exposureResearchContext: options.exposureResearchContext } : {}),
    ...(options.portfolioLineageSummary !== undefined ? { portfolioLineageSummary: options.portfolioLineageSummary } : {}),
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

function makeExposureResearchContext(overrides: Record<string, unknown> = {}) {
  return {
    dominantExposure: {
      type: 'position',
      symbol: 'AAPL',
      label: 'AAPL',
      market: 'us',
      currency: 'USD',
      marketValue: 1600,
      weightPct: 42,
      fxStatus: 'live',
      source: 'snapshot_analytics',
    },
    concentrationContext: {
      state: 'elevated',
      topWeightPct: 42,
      alert: true,
      holdingCount: 1,
      accountCount: 1,
      dominantType: 'position',
      dominantLabel: 'AAPL',
      warningCodes: ['single_position_gt_30'],
    },
    currencyContext: {
      state: 'limited',
      baseCurrency: 'CNY',
      fxFreshnessState: 'stale',
      largestCurrency: {
        currency: 'USD',
        label: 'USD',
        weightPct: 66,
        fxStatus: 'stale',
        provider: 'hidden-provider',
      },
      stalePairs: ['USD/CNY'],
    },
    marketContext: {
      state: 'limited',
      largestMarket: {
        market: 'us',
        label: 'US',
        weightPct: 66,
      },
      marketBreakdown: [
        { market: 'us', weightPct: 66, positionCount: 1, rawPayload: 'hidden' },
      ],
      benchmarkMappingState: 'unmapped',
      factorMappingState: 'unmapped',
      sectorContextState: 'unavailable',
    },
    staleInputs: [
      { input: 'fx_freshness', status: 'stale', reason: 'aggregate_currency_context_limited' },
      { input: 'benchmark_mapping', status: 'limited', reason: 'mapping_unavailable' },
    ],
    evidenceGaps: ['fx_freshness', 'benchmark_mapping', 'factor_mapping'],
    observationBoundary: {
      observationOnly: true,
      decisionGrade: false,
      accountingMutation: false,
      portfolioMutation: false,
      providerRoutingChanged: false,
      externalProviderCallsAdded: false,
      adviceBoundary: 'no_advice',
      message: 'Observation-only portfolio research context; not personalized financial advice and not an instruction.',
    },
    researchNextSteps: [
      { topic: 'dominant_exposure', check: 'Review latest research evidence for AAPL and its market context.' },
      { topic: 'currency_context', check: 'Verify FX and valuation freshness before using aggregate currency context.' },
      { topic: 'comparative_context', check: 'Map benchmark and factor evidence before using comparative research context.' },
    ],
    ...overrides,
  };
}

function makePortfolioLineageSummary(overrides: Record<string, unknown> = {}) {
  return {
    hasLineage: true,
    authoritative: false,
    observationOnly: true,
    price: {
      label: '价格延迟',
      variant: 'caution',
      detail: 'AAPL, MSFT · 2/2',
      affectedSymbols: ['AAPL', 'MSFT'],
      count: 2,
      total: 2,
      lastUpdatedAt: '2026-03-19',
    },
    fx: {
      label: '汇率待确认',
      variant: 'danger',
      detail: 'USD · 1/1',
      affectedCurrencies: ['USD'],
      affectedPairs: ['USD/CNY'],
      count: 1,
      total: 1,
      lastUpdatedAt: null,
    },
    snapshot: {
      label: '估值部分可用',
      variant: 'caution',
      detail: 'AAPL, USD · 2/2',
      affectedSymbols: ['AAPL'],
      affectedCurrencies: ['USD'],
      affectedPairs: ['USD/CNY'],
      count: 2,
      total: 2,
      lastUpdatedAt: '2026-03-20',
    },
    analytics: {
      label: '仅观察',
      variant: 'info',
      detail: 'AAPL, USD · 2/2',
      affectedSymbols: ['AAPL'],
      affectedCurrencies: ['USD'],
      count: 2,
      total: 2,
    },
    ...overrides,
  };
}

function makeValuationEvidenceSnapshot(overrides: Record<string, unknown> = {}) {
  return {
    ...makeSnapshot({
      includePosition: true,
      fxStale: false,
      portfolioLineageSummary: makePortfolioLineageSummary(),
      positionOverrides: {
        provider: 'raw-provider-must-not-leak',
        requestId: 'request-id-must-not-leak',
        debugTrace: 'debug-trace-must-not-leak',
      },
    }),
    priceLineage: {
      status: 'stale',
      scoreAuthority: 'observation_only',
      counts: { total: 2, available: 0, missing: 1, stale: 1, delayed: 0 },
      affectedSymbols: {
        available: [],
        missing: ['MSFT'],
        stale: ['AAPL'],
        delayed: [],
        fallback: ['MSFT'],
      },
      lastUpdatedAt: '2026-03-19T10:00:00Z',
    },
    fxLineage: {
      status: 'stale',
      scoreAuthority: 'observation_only',
      counts: { total: 1, available: 0, missing: 0, stale: 1, fallback: 0, identity: 0 },
      affectedCurrencies: { available: [], missing: [], stale: ['USD'], fallback: [], identity: [] },
      affectedPairs: { available: [], missing: [], stale: ['USD/CNY'], fallback: [], identity: [] },
      lastUpdatedAt: null,
    },
    valuationSnapshotLineage: {
      status: 'partial',
      scoreAuthority: 'observation_only',
      snapshotState: 'ready',
      metricsReady: true,
      positionCount: 2,
      completePositionCount: 1,
      partialPositionCount: 1,
      blockedPositionCount: 0,
      blockedBy: {
        priceSymbols: ['MSFT'],
        fxPairs: ['USD/CNY'],
        fxCurrencies: ['USD'],
      },
      lastUpdatedAt: '2026-03-20T00:00:00Z',
    },
    analyticsReadiness: {
      valuation: 'partial',
      risk: 'partial',
      scoreAuthority: 'observation_only',
      observationOnly: true,
      affectedSymbols: ['AAPL', 'MSFT'],
      affectedCurrencies: ['USD'],
    },
    ...overrides,
  };
}

function makeStructureReview(options: {
  status?: 'available' | 'partial' | 'unavailable';
  holdingState?: string;
  includeSymbolLink?: boolean;
} = {}) {
  return {
    schemaVersion: 'portfolio_structure_review_v1',
    aggregateSummary: {
      asOf: '2026-06-15',
      accountCount: 1,
      holdingCount: 2,
      evaluatedCount: 2,
      largestHolding: { ticker: 'AAPL', percent: 60 },
    },
    exposureByThemeOrSector: [
      {
        key: 'ai_infrastructure',
        label: 'AI Infrastructure',
        marketValue: 1500,
        percent: 75,
        holdingCount: 2,
      },
    ],
    countsByStructureState: {
      [options.holdingState ?? 'mixed']: 1,
      lowConfidence: 1,
    },
    holdingsStructure: [
      {
        ticker: 'AAPL',
        structureState: options.holdingState ?? 'mixed',
        confidence: 'medium',
        evidenceQuality: { score: 74, status: options.status ?? 'partial' },
        riskFlags: ['Evidence still thin'],
        researchNotes: {
          watchNext: ['Wait for cleaner follow-through confirmation.'],
          needsMoreEvidence: ['Daily structure evidence needs more bars.'],
          riskFlags: ['Crowded theme sensitivity remains elevated.'],
        },
        missingEvidence: [
          { kind: 'daily_ohlcv', message: 'Daily structure evidence needs more bars.' },
        ],
        ...(options.includeSymbolLink === false ? {} : { structureDecisionRoute: '/stocks/AAPL/structure-decision' }),
      },
      {
        ticker: 'UNKNOWN',
        structureState: 'lowConfidence',
        confidence: 'low',
        evidenceQuality: { score: 0, status: 'unavailable' },
        riskFlags: ['Security metadata is unavailable for this cached holding.'],
        researchNotes: {
          watchNext: [],
          needsMoreEvidence: ['Security metadata is required before structure evidence can be reviewed.'],
          riskFlags: ['Security metadata is unavailable for this cached holding.'],
        },
        missingEvidence: [
          { kind: 'security_metadata', message: 'Ticker, market, or currency metadata is missing for this cached holding.' },
        ],
      },
    ],
    strongestStructures: [
      { ticker: 'AAPL', structureState: options.holdingState ?? 'mixed', score: 74 },
    ],
    weakestEvidence: [
      { ticker: 'UNKNOWN', status: 'unavailable', usableBars: 0, evidenceQuality: 0 },
    ],
    commonRiskFlags: [
      { flag: 'Evidence still thin', count: 1, tickers: ['AAPL'] },
    ],
    missingEvidence: [
      { kind: 'cached_portfolio_holdings', message: 'Cached holdings are partially available for structure review.' },
    ],
    dataQuality: {
      status: options.status ?? 'partial',
      holdingMetadataStatus: 'partial',
      structureEvidenceStatus: options.status ?? 'partial',
      readOnly: true,
      failClosed: options.status === 'unavailable',
    },
    noAdviceDisclosure: 'Observation-only research context; not personalized financial advice and not an instruction.',
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
    setAdminPortfolioSurface();

    getAccounts.mockResolvedValue(makeAccounts());
    getSnapshot.mockImplementation(async ({ accountId }: { accountId?: number } = {}) => makeSnapshot({ accountId, fxStale: true }));
    getRisk.mockResolvedValue(makeRisk());
    getStructureReview.mockResolvedValue(makeStructureReview());
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
      brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
      connectionName: SAFE_IBKR_CONNECTION_HANDLE,
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
      apiBaseUrl: SAFE_IBKR_URL_HANDLE,
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
    expect(screen.getByRole('heading', { name: /持仓与组合暴露|Holdings and portfolio exposure/ })).toBeInTheDocument();
    expect(screen.getByTestId('portfolio-account-status-strip')).toHaveTextContent(/总资产|Total Assets/);
    expect(screen.getByTestId('portfolio-total-assets-value')).toHaveClass('text-white');
    expect(screen.getByTestId('portfolio-command-strip')).toContainElement(screen.getByTestId('portfolio-display-currency-select'));
    expect(screen.queryByTestId('portfolio-row-macro')).not.toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-summary-strip')).not.toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-summary-core-row')).not.toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-summary-aux-row')).not.toBeInTheDocument();
    expect(screen.queryByTestId('portfolio-pnl-summary')).not.toBeInTheDocument();
    const onboardingRow = screen.getByTestId('portfolio-empty-onboarding-row');
    const onboardingWorkflow = screen.getByTestId('portfolio-empty-workflow-column');
    const researchStatePreview = screen.getByTestId('portfolio-research-state-preview');
    expect(onboardingRow).toHaveClass('grid', 'grid-cols-1', 'xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]');
    expect(onboardingWorkflow).toHaveTextContent('首次配置路径');
    expect(onboardingWorkflow).toHaveTextContent('创建或导入首个组合');
    expect(onboardingWorkflow).toHaveTextContent('真实数据接入前不生成示例收益');
    expect(onboardingWorkflow).toHaveTextContent('保存后会在下方自动展开真实持仓、风险摘要与近期活动。');
    const onboardingCta = within(onboardingWorkflow).getByTestId('portfolio-empty-onboarding-cta');
    expect(onboardingCta).toHaveTextContent('先看市场概览');
    expect(onboardingCta).toHaveTextContent('运行 Scanner');
    expect(onboardingCta).toHaveTextContent('选择观察标的');
    expect(onboardingCta).toHaveTextContent('查看研究雷达');
    expect(onboardingCta).toHaveTextContent('进入账户创建区');
    expect(onboardingCta).toHaveTextContent('不会自动创建账户。');
    expect(onboardingCta).toHaveTextContent('不会改写持仓、现金或外部同步状态。');
    expect(within(onboardingCta).getByRole('link', { name: '先看市场概览' })).toHaveAttribute('href', '/zh/market-overview');
    expect(within(onboardingCta).getByRole('link', { name: '运行 Scanner' })).toHaveAttribute('href', '/zh/scanner');
    expect(within(onboardingCta).getByRole('link', { name: '选择观察标的' })).toHaveAttribute('href', '/zh/watchlist');
    expect(within(onboardingCta).getByRole('link', { name: '查看研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(within(onboardingCta).getByRole('link', { name: '进入账户创建区' })).toHaveAttribute('href', '/zh/portfolio');
    expect(researchStatePreview).toHaveTextContent('组合研究状态');
    expect(researchStatePreview).toHaveTextContent('账户已设置');
    expect(researchStatePreview).toHaveTextContent('持仓待接入');
    expect(researchStatePreview).toHaveTextContent('估值不可用');
    expect(researchStatePreview).toHaveTextContent('汇率缺失');
    expect(researchStatePreview).toHaveTextContent('风险视图待生成');
    expect(researchStatePreview).toHaveTextContent('补持仓或导入流水');
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
    expect(createAccount).not.toHaveBeenCalled();
    expect(createTrade).not.toHaveBeenCalled();
    expect(commitCsvImport).not.toHaveBeenCalled();
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
    const researchStatePreview = screen.getByTestId('portfolio-research-state-preview');
    expect(researchStatePreview).toHaveTextContent('组合研究状态');
    expect(researchStatePreview).toHaveTextContent('持仓待接入');
    expect(researchStatePreview).toHaveTextContent('账户已设置');
    expect(researchStatePreview).toHaveTextContent('估值不可用');
    expect(researchStatePreview).toHaveTextContent('汇率缺失');
    expect(researchStatePreview).toHaveTextContent('风险视图待生成');
    expect(researchStatePreview).toHaveTextContent('补持仓或导入流水');
    expect(researchStatePreview).toHaveTextContent('接入后评估市值、盈亏与暴露。');
    expect(researchStatePreview.textContent || '').not.toMatch(/provider|runtime|credential|sourceAuthority|unavailable|missing|unknown|fallback|debug/i);
    expect(researchStatePreview.textContent || '').not.toMatch(/buy|sell|hold|target|stop|position[- ]?size|position sizing|买入|卖出|持有|目标价|止损|仓位|建仓|加仓|减仓/i);
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
    const researchStatePreview = screen.getByTestId('portfolio-research-state-preview');
    expect(researchStatePreview).toHaveTextContent('组合研究状态');
    expect(researchStatePreview).toHaveTextContent('可评估持仓');
    expect(researchStatePreview).toHaveTextContent('1 项');
    expect(researchStatePreview).toHaveTextContent('估值部分可用');
    expect(researchStatePreview).toHaveTextContent('汇率待确认');
    expect(researchStatePreview).toHaveTextContent('仅观察');
    expect(researchStatePreview.textContent || '').not.toMatch(/provider|runtime|credential|sourceAuthority|unavailable|missing|unknown|fallback|debug/i);
    expect(researchStatePreview.textContent || '').not.toMatch(/buy|sell|hold|target|stop|position[- ]?size|position sizing|买入|卖出|持有|目标价|止损|仓位|建仓|加仓|减仓/i);
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

  it('copies a consumer-safe portfolio valuation evidence pack for active valuation data', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    getSnapshot.mockResolvedValue(makeValuationEvidenceSnapshot());

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const panel = screen.getByTestId('portfolio-valuation-evidence-pack');
    expect(panel).toHaveTextContent('估值证据包');
    expect(within(panel).getByRole('button', { name: '复制估值证据包' })).toBeInTheDocument();
    expect(within(panel).getByRole('button', { name: '导出估值证据包' })).toBeInTheDocument();

    fireEvent.click(within(panel).getByRole('button', { name: '复制估值证据包' }));

    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    const exported = JSON.parse(writeText.mock.calls[0][0]);
    expect(exported).toMatchObject({
      schemaVersion: 'portfolio_valuation_evidence_pack_v1',
      appSurface: 'Portfolio valuation',
      holdingsCount: 1,
      valuationAsOf: '2026-03-19',
      account: {
        scope: 'all_accounts',
        label: '全部账户',
      },
      priceLineage: {
        label: '价格延迟',
        missingQuoteCount: 1,
        staleQuoteCount: 1,
        totalQuoteCount: 2,
        lastUpdatedAt: '2026-03-19T10:00:00Z',
      },
      fxLineage: {
        label: '汇率待确认',
        affectedCurrencies: ['USD'],
        affectedPairs: ['USD/CNY'],
        lastUpdatedAt: 'unknown/待补证',
      },
      valuationLineage: {
        label: '估值部分可用',
        positionCount: 2,
        completePositionCount: 1,
        partialPositionCount: 1,
        blockedPositionCount: 0,
      },
      valuationSummary: {
        totalMarketValue: 'CNY 2,000.00',
        totalEquity: 'CNY 3,000.00',
        totalCash: 'CNY 1,000.00',
        unrealizedPnl: 'CNY 100.00',
      },
    });
    expect(exported.generatedAt).toEqual(expect.any(String));
    expect(exported.warnings).toEqual(expect.arrayContaining([
      '单一标的占比较高',
      '单一币种占比较高',
      '单一市场占比较高',
      '价格延迟',
      '汇率待确认',
      '估值部分可用',
    ]));
    expect(JSON.stringify(exported)).toContain('unknown/待补证');
    expect(JSON.stringify(exported)).not.toMatch(/raw-provider-must-not-leak|request-id-must-not-leak|debug-trace-must-not-leak/i);
    expect(JSON.stringify(exported)).not.toMatch(/provider|runtime|credential|requestId|trace|debug|raw|cacheKey/i);
    expect(JSON.stringify(exported)).not.toMatch(/\b(buy|sell|hold|target|best|recommended|optimal|winner)\b|stop loss|position sizing|买入|卖出|持有|目标价|止损|仓位建议|最佳|推荐|赢家/i);
  });

  it('does not show valuation evidence export controls without portfolio valuation data', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: false }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(screen.queryByTestId('portfolio-valuation-evidence-pack')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '复制估值证据包' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '导出估值证据包' })).not.toBeInTheDocument();
  });

  it('fails closed instead of exporting fake valuation evidence for blocked valuation results', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    getSnapshot.mockResolvedValue(makeValuationEvidenceSnapshot({
      portfolioLineageSummary: makePortfolioLineageSummary({
        snapshot: {
          label: '估值不可用',
          variant: 'danger',
          detail: '0/1',
          affectedSymbols: ['MSFT'],
          affectedCurrencies: [],
          affectedPairs: [],
          count: 0,
          total: 1,
          lastUpdatedAt: null,
        },
      }),
      valuationSnapshotLineage: {
        status: 'blocked',
        scoreAuthority: 'observation_only',
        snapshotState: 'blocked',
        metricsReady: false,
        positionCount: 1,
        completePositionCount: 0,
        partialPositionCount: 0,
        blockedPositionCount: 1,
        blockedBy: { priceSymbols: ['MSFT'], fxPairs: [], fxCurrencies: [] },
        lastUpdatedAt: null,
      },
    }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const panel = screen.getByTestId('portfolio-valuation-evidence-pack');
    expect(panel).toHaveTextContent('估值证据包暂不可导出');
    expect(panel).toHaveTextContent('待补证');
    expect(within(panel).queryByRole('button', { name: '复制估值证据包' })).not.toBeInTheDocument();
    expect(within(panel).queryByRole('button', { name: '导出估值证据包' })).not.toBeInTheDocument();
    expect(writeText).not.toHaveBeenCalled();
    expect(panel.textContent || '').not.toMatch(/fake|sample|mock|placeholder|provider|request|trace|debug|推荐|赢家|目标价|止损|仓位建议/i);
  });

  it('renders a consumer-safe portfolio structure review section with evidence gaps and structure detail links', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true, fxStale: false }));
    getStructureReview.mockResolvedValue(makeStructureReview({ status: 'partial', holdingState: 'mixed' }));

    render(
      <UiLanguageProvider>
        <PortfolioPage />
      </UiLanguageProvider>,
    );

    await waitForInitialLoad();
    await waitFor(() => expect(getStructureReview).toHaveBeenCalledTimes(1));

    expect(getStructureReview).toHaveBeenCalledWith({
      accountId: undefined,
      costMethod: 'fifo',
    });

    const section = screen.getByTestId('portfolio-structure-review-panel');
    expect(section).toHaveTextContent('组合结构审查');
    expect(section).toHaveTextContent('研究工作流');
    expect(section).toHaveTextContent('AI Infrastructure');
    expect(section).toHaveTextContent('75.0%');
    expect(section).toHaveTextContent('mixed');
    expect(section).toHaveTextContent('需补证据');
    expect(section).toHaveTextContent('证据仍然偏薄');
    expect(section).toHaveTextContent('Daily structure evidence needs more bars.');
    expect(section).toHaveTextContent('该持仓的证券元数据暂不可用。');
    expect(section).toHaveTextContent('只读研究上下文');

    const detailLink = within(section).getByRole('link', { name: '查看结构详情' });
    expect(detailLink).toHaveAttribute('href', '/stocks/AAPL/structure-decision');

    expect(section.textContent || '').not.toMatch(/schemaVersion|readOnly|failClosed|provider|debug|raw|trace|structureDecisionRoute/i);
    expect(section.textContent || '').not.toMatch(/买入|卖出|下单|交易建议|投资建议|buy|sell|target price|stop loss|position sizing/i);
  });

  it('replaces internal-looking account labels with a consumer-safe fallback while preserving portfolio rendering', async () => {
    getAccounts.mockResolvedValue(makeAccounts([{ id: 1, name: 'audit-trace-acct' }]));
    const snapshot = makeSnapshot({
      includePosition: true,
      fxStale: false,
    });
    snapshot.accounts[0].accountName = 'audit-trace-acct';
    snapshot.analytics.exposure.byAccount[0].accountName = 'audit-trace-acct';
    snapshot.portfolioAttribution.accountAttribution.topAccounts[0].accountName = 'audit-trace-acct';
    getSnapshot.mockResolvedValue(snapshot);

    render(
      <UiLanguageProvider>
        <PortfolioPage />
      </UiLanguageProvider>,
    );

    await waitForInitialLoad();

    const holdings = screen.getByTestId('portfolio-current-holdings-panel');
    expect(holdings).toHaveTextContent('组合账户');
    expect(holdings.textContent || '').not.toMatch(/audit-trace-acct/i);
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

  it('renders bounded exposure research context only when the snapshot provides it', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({
      includePosition: true,
      fxStale: true,
      exposureResearchContext: makeExposureResearchContext(),
    }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const riskCard = screen.getByTestId('portfolio-risk-card');
    const context = within(riskCard).getByTestId('portfolio-exposure-research-context');
    expect(context).toHaveTextContent('暴露研究背景');
    expect(context).toHaveTextContent('仅供观察');
    expect(context).toHaveTextContent('主导暴露');
    expect(context).toHaveTextContent('AAPL');
    expect(context).toHaveTextContent('42.0%');
    expect(context).toHaveTextContent('集中度背景');
    expect(context).toHaveTextContent('集中度较高');
    expect(context).toHaveTextContent('币种背景');
    expect(context).toHaveTextContent('USD');
    expect(context).toHaveTextContent('汇率可能延迟');
    expect(context).toHaveTextContent('市场背景');
    expect(context).toHaveTextContent('美股');
    expect(context).toHaveTextContent('输入新鲜度');
    expect(within(context).getByTestId('portfolio-exposure-research-stale-inputs')).toHaveTextContent('汇率新鲜度');
    expect(within(context).getByTestId('portfolio-exposure-research-stale-inputs')).toHaveTextContent('比较参考');
    expect(within(context).getByTestId('portfolio-exposure-research-evidence-gaps')).toHaveTextContent('汇率新鲜度需复核');
    expect(within(context).getByTestId('portfolio-exposure-research-evidence-gaps')).toHaveTextContent('比较参考待映射');
    expect(within(context).getByTestId('portfolio-exposure-research-evidence-gaps')).toHaveTextContent('因子参考待映射');
    expect(within(context).getByTestId('portfolio-exposure-research-next-steps')).toHaveTextContent('AAPL：复核主导暴露对应的研究证据与市场背景');
    expect(within(context).getByTestId('portfolio-exposure-research-next-steps')).toHaveTextContent('核对汇率与估值新鲜度');
    expect(within(context).getByTestId('portfolio-exposure-research-boundary')).toHaveTextContent('仅供观察，不改动账务或组合数据');
    expect(riskCard).toContainElement(context);
    expect(Boolean(screen.getByTestId('portfolio-risk-exposure-summary').compareDocumentPosition(context) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(context.compareDocumentPosition(screen.getByTestId('portfolio-scenario-risk-disclosure')) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(context.textContent || '').not.toMatch(
      /sourceAuthority|warningCodes|providerRoutingChanged|externalProviderCallsAdded|provider|cache|debug|backend|raw|schema|trace|sourceRef|buy|sell|target|stop|position[- ]?sizing|买入|卖出|下单|仓位建议|持仓建议/i,
    );
  });

  it('renders DATA-018 valuation lineage status in the first viewport and research context without raw labels', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({
      includePosition: true,
      fxStale: false,
      exposureResearchContext: makeExposureResearchContext(),
      portfolioLineageSummary: makePortfolioLineageSummary(),
    }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const researchStatePreview = screen.getByTestId('portfolio-research-state-preview');
    expect(researchStatePreview).toHaveTextContent('价格延迟');
    expect(researchStatePreview).toHaveTextContent('汇率待确认');
    expect(researchStatePreview).toHaveTextContent('估值部分可用');
    expect(researchStatePreview).toHaveTextContent('仅观察');
    expect(researchStatePreview).toHaveTextContent('AAPL');
    expect(researchStatePreview).toHaveTextContent('USD');

    const riskCard = screen.getByTestId('portfolio-risk-card');
    const context = within(riskCard).getByTestId('portfolio-exposure-research-context');
    const lineageSummary = within(context).getByTestId('portfolio-exposure-lineage-summary');
    expect(lineageSummary).toHaveTextContent('价格延迟');
    expect(lineageSummary).toHaveTextContent('汇率待确认');
    expect(lineageSummary).toHaveTextContent('估值部分可用');
    expect(lineageSummary).toHaveTextContent('仅观察');
    expect(lineageSummary).toHaveTextContent('AAPL');
    expect(lineageSummary).toHaveTextContent('USD');

    const combinedText = `${researchStatePreview.textContent || ''} ${lineageSummary.textContent || ''}`;
    expect(combinedText).not.toMatch(
      /sourceAuthority|reasonCode|provider|cache|debug|backend|raw|sourceRefs|adminDiagnostics|riskDiagnostics|confidenceCap|fallback_1_to_1|provider_timeout|target price|stop-loss|position sizing|目标价|止损|仓位建议|建仓建议|加仓建议|减仓建议|买入建议|卖出建议|持有建议|交易建议|操作建议/i,
    );
  });

  it('fails closed when valuation lineage fields are absent', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({
      includePosition: true,
      fxStale: false,
    }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const researchStatePreview = screen.getByTestId('portfolio-research-state-preview');
    expect(researchStatePreview).toHaveTextContent('价格缺失');
    expect(researchStatePreview).toHaveTextContent('汇率待确认');
    expect(researchStatePreview).toHaveTextContent('估值部分可用');
    expect(researchStatePreview).toHaveTextContent('仅观察');
    expect(screen.getByTestId('portfolio-research-next-evidence')).toHaveTextContent('下一步：先确认价格与汇率，再补齐估值快照。');
    expect(screen.getByTestId('portfolio-valuation-next-evidence')).toHaveTextContent('下一步：先确认价格与汇率，再补齐估值快照。');
    expect(screen.getByTestId('portfolio-consumer-data-notice')).toHaveTextContent('价格、汇率与估值状态待确认。');
    expect(screen.getByTestId('portfolio-bento-page').textContent || '').not.toMatch(
      /priceLineage|fxLineage|valuationSnapshotLineage|analyticsReadiness|provider|cache|debug|backend|raw|sourceRefs|adminDiagnostics|riskDiagnostics|confidenceCap|fallback_1_to_1|provider_timeout|target price|stop-loss|position sizing|目标价|止损|仓位建议|建仓建议|加仓建议|减仓建议|买入建议|卖出建议|持有建议|交易建议|操作建议/i,
    );
  });

  it('gracefully skips exposure research context when the snapshot omits it', async () => {
    getSnapshot.mockResolvedValue(makeSnapshot({ includePosition: true, fxStale: false }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(screen.queryByTestId('portfolio-exposure-research-context')).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-summary-market-value-card')).toHaveTextContent('CNY 2,000.00');
    expect(screen.getByTestId('portfolio-pnl-summary')).toHaveTextContent('+CNY 220.00');
    expect(screen.getByTestId('portfolio-summary-cash-card')).toHaveTextContent('CNY 1,000.00');
    expect(screen.getByTestId('portfolio-current-holdings-panel')).toHaveTextContent('AAPL');
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
      portfolioLineageSummary: makePortfolioLineageSummary({
        authoritative: true,
        observationOnly: false,
        price: {
          label: '价格可用',
          variant: 'success',
          detail: '1/1',
          affectedSymbols: [],
          count: 1,
          total: 1,
          lastUpdatedAt: '2026-03-19',
        },
        fx: {
          label: '汇率已确认',
          variant: 'success',
          detail: '1/1',
          affectedCurrencies: [],
          affectedPairs: [],
          count: 1,
          total: 1,
          lastUpdatedAt: '2026-03-19',
        },
        snapshot: {
          label: '估值完整',
          variant: 'success',
          detail: '1/1',
          affectedSymbols: [],
          affectedCurrencies: [],
          affectedPairs: [],
          count: 1,
          total: 1,
          lastUpdatedAt: '2026-03-19',
        },
        analytics: {
          label: '风险视图可用',
          variant: 'success',
          detail: '1/1',
          affectedSymbols: [],
          affectedCurrencies: [],
          count: 1,
          total: 1,
        },
      }),
      valuationLineageState: 'current',
    }));

    render(<PortfolioPage />);

    await waitForInitialLoad();

    const valuationTrust = screen.getByTestId('portfolio-valuation-trust-strip');
    expect(valuationTrust).toHaveTextContent('估值完整');
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
    expect(screen.getByLabelText('券商')).toHaveValue('');
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
    expect(screen.getByLabelText('IBKR 连接端点')).toHaveValue('');
    expect(screen.getByLabelText('IBKR 账户映射')).toBeInTheDocument();
    expect(screen.getByLabelText('IBKR 临时授权')).toBeInTheDocument();
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
          connectionName: SAFE_IBKR_CONNECTION_HANDLE,
          brokerType: 'ibkr',
          brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
          importMode: 'file',
          status: 'active',
          syncMetadata: {
            rawPayloadLabel: 'synthetic_raw_payload_label_must_not_leak',
            importFileLabel: 'synthetic_import_file_label_must_not_leak',
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

    expect(screen.getByText(translate('zh', 'portfolio.ibkrImportHint'))).toBeInTheDocument();
    expect(screen.getByText(SAFE_IBKR_CONNECTION_HANDLE)).toBeInTheDocument();
    expect(screen.getByDisplayValue(SAFE_IBKR_ACCOUNT_HANDLE)).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'portfolio.currentImportAccount'))).toBeInTheDocument();
    const portfolioDom = screen.getByTestId('portfolio-bento-page').textContent || '';
    for (const marker of SYNTHETIC_BROKER_IMPORT_RAW_MARKERS) {
      expect(portfolioDom).not.toContain(marker);
    }
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
          connectionName: SAFE_IBKR_CONNECTION_HANDLE,
          brokerType: 'ibkr',
          brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
          importMode: 'file',
          status: 'active',
          syncMetadata: {
            ibkrApi: {
              apiBaseUrl: SAFE_IBKR_URL_HANDLE,
              verifySsl: false,
              brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
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
      brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
      sessionToken: 'unit-test-not-a-real-session',
      apiBaseUrl: SAFE_IBKR_URL_HANDLE,
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
            connectionName: SAFE_IBKR_CONNECTION_HANDLE,
            brokerType: 'ibkr',
            brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
            importMode: 'file',
            status: 'active',
            syncMetadata: {
              ibkrApi: {
                apiBaseUrl: SAFE_IBKR_URL_HANDLE,
                verifySsl: false,
                brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
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
            connectionName: SAFE_IBKR_CONNECTION_HANDLE,
            brokerType: 'ibkr',
            brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
            importMode: 'api',
            status: 'active',
            syncMetadata: {
              ibkrApi: {
                apiBaseUrl: SAFE_IBKR_URL_HANDLE,
                verifySsl: false,
                brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
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
      { target: { value: 'temporary-auth-123' } },
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
          connectionName: SAFE_IBKR_CONNECTION_HANDLE,
          brokerType: 'ibkr',
          brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
          importMode: 'api',
          status: 'active',
          syncMetadata: {
            ibkrApi: {
              apiBaseUrl: SAFE_IBKR_URL_HANDLE,
              verifySsl: false,
              brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
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
      target: { value: 'temporary-auth-123' },
    });
    fireEvent.click(screen.getByRole('button', { name: translate('en', 'portfolio.syncIbkr') }));

    await waitFor(() => expect(syncIbkrReadOnly).toHaveBeenCalled());
    expect(await screen.findByText(translate('en', 'portfolio.readOnlyBadge'))).toBeInTheDocument();
    expect(screen.getByText(translate('en', 'portfolio.ibkrImportHint'))).toBeInTheDocument();
    expect(screen.getByText(translate('en', 'portfolio.syncResult'))).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes(translate('en', 'portfolio.positionsCountLabel')))).toBeInTheDocument();
  });

  it('hides sync setup details and provider diagnostics for non-admin consumers', async () => {
    setConsumerPortfolioSurface();
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
          connectionName: SAFE_IBKR_CONNECTION_HANDLE,
          brokerType: 'ibkr',
          brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
          importMode: 'api',
          status: 'active',
          syncMetadata: {
            ibkrApi: {
              apiBaseUrl: SAFE_IBKR_URL_HANDLE,
              verifySsl: false,
              brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
            },
          },
        },
      ],
    });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    expect(listImportBrokers).not.toHaveBeenCalled();
    expect(listBrokerConnections).not.toHaveBeenCalled();
    expect(screen.queryByText(translate('zh', 'portfolio.dataSyncTitle'))).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '同步' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sync' })).not.toBeInTheDocument();
    expect(screen.queryByText('IBKR 连接端点')).not.toBeInTheDocument();
    expect(screen.queryByText('IBKR 账户映射')).not.toBeInTheDocument();
    expect(screen.queryByText('IBKR 临时授权')).not.toBeInTheDocument();
    expect(screen.queryByText(SAFE_IBKR_CONNECTION_HANDLE)).not.toBeInTheDocument();
    expect(screen.queryByText(SAFE_IBKR_ACCOUNT_HANDLE)).not.toBeInTheDocument();
    expect(screen.queryByText(SAFE_IBKR_URL_HANDLE)).not.toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.syncIbkr'))).not.toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.syncRequiresToken'))).not.toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.brokerFallbackEmpty'))).not.toBeInTheDocument();
    expect(screen.queryByText(translate('zh', 'portfolio.brokerFallbackUnavailable'))).not.toBeInTheDocument();
    expect(screen.queryByText('手工记账')).not.toBeInTheDocument();
    expect(screen.queryByText('编辑')).not.toBeInTheDocument();
    expect(screen.queryByText('作废')).not.toBeInTheDocument();
    expect(screen.getByTestId('portfolio-consumer-setup-boundary')).toHaveTextContent('当前视图仅展示已接入的组合、持仓与估值状态。');
    expect(screen.getByTestId('portfolio-consumer-setup-boundary')).not.toHaveTextContent(/IBKR|token|API|账户引用|会话令牌|连接地址|同步控件|sync controls|request|trace|cache|payload/i);
    expect(screen.getByTestId('portfolio-research-state-preview')).toHaveTextContent('账户已设置');
  });

  it('keeps new account broker blank instead of defaulting to Demo', async () => {
    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.click(getLeftTabButton('账户'));
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'portfolio.createAccount') }));

    expect(screen.getByLabelText('券商')).toHaveValue('');
    expect(screen.getByLabelText('账户名称')).toBeInTheDocument();
    expect(screen.getByLabelText('基准币种')).toHaveValue('CNY');
  });

  it('shows explicit broker unavailability instead of falling back to built-in broker options', async () => {
    listImportBrokers.mockResolvedValueOnce({ brokers: [] });

    render(<PortfolioPage />);

    await waitForInitialLoad();

    fireEvent.click(getLeftTabButton('同步'));

    expect(screen.getAllByText(translate('zh', 'portfolio.brokerFallbackUnavailable')).length).toBeGreaterThan(0);
    expect(screen.queryByRole('option', { name: /华泰|中信|招商|IBKR|Huatai|Citic|CMB/i })).not.toBeInTheDocument();
    expect(screen.getByLabelText('导入来源')).toHaveValue('');
    expect(screen.queryByText('Demo')).not.toBeInTheDocument();
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
          connectionName: SAFE_IBKR_CONNECTION_HANDLE,
          brokerType: 'ibkr',
          brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
          importMode: 'api',
          status: 'active',
          syncMetadata: {
            ibkrApi: {
              apiBaseUrl: SAFE_IBKR_URL_HANDLE,
              verifySsl: false,
              brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
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
      target: { value: 'temporary-auth-123' },
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

  it('resets IBKR connection-derived fields on trade-account changes while preserving the typed temporary authorization', async () => {
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
              connectionName: SAFE_IBKR_SECONDARY_CONNECTION_HANDLE,
              brokerType: 'ibkr',
              brokerAccountRef: SAFE_IBKR_SECONDARY_ACCOUNT_HANDLE,
              importMode: 'api',
              status: 'active',
              syncMetadata: {
                ibkrApi: {
                  apiBaseUrl: SAFE_IBKR_SECONDARY_URL_HANDLE,
                  verifySsl: true,
                  brokerAccountRef: SAFE_IBKR_SECONDARY_ACCOUNT_HANDLE,
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
            connectionName: SAFE_IBKR_CONNECTION_HANDLE,
            brokerType: 'ibkr',
            brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
            importMode: 'api',
            status: 'active',
            syncMetadata: {
              ibkrApi: {
                apiBaseUrl: SAFE_IBKR_URL_HANDLE,
                verifySsl: false,
                brokerAccountRef: SAFE_IBKR_ACCOUNT_HANDLE,
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

    expect(await screen.findByText(SAFE_IBKR_CONNECTION_HANDLE)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(translate('zh', 'portfolio.ibkrSessionTokenPlaceholder')), {
      target: { value: 'temporary-auth-123' },
    });
    fireEvent.change(screen.getByLabelText('IBKR 连接端点'), {
      target: { value: 'https://override.local/v1/api' },
    });
    fireEvent.change(screen.getByLabelText('IBKR 账户映射'), {
      target: { value: 'U0000000' },
    });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'portfolio.syncIbkr') }));

    await waitFor(() => expect(syncIbkrReadOnly).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(translate('zh', 'portfolio.syncResult'))).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('IBKR 临时授权'), {
      target: { value: 'temporary-auth-123' },
    });

    const tradeAccountSelect = screen.getByLabelText(/记账账户|ledger account/i) as HTMLSelectElement;
    fireEvent.change(tradeAccountSelect, { target: { value: '2' } });

    await waitFor(() => expect(listBrokerConnections).toHaveBeenCalledWith(2));
    await waitFor(() => expect(screen.getByText(SAFE_IBKR_SECONDARY_CONNECTION_HANDLE)).toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText(translate('zh', 'portfolio.syncResult'))).not.toBeInTheDocument());
    expect(screen.getByLabelText('IBKR 连接端点')).toHaveValue(SAFE_IBKR_SECONDARY_URL_HANDLE);
    expect(screen.getByLabelText('IBKR 账户映射')).toHaveValue(SAFE_IBKR_SECONDARY_ACCOUNT_HANDLE);
    expect(screen.getByLabelText('IBKR 临时授权')).toHaveValue('temporary-auth-123');
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
