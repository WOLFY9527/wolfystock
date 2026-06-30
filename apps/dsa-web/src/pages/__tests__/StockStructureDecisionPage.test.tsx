import type React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StockStructureDecisionEntryPage from '../StockStructureDecisionEntryPage';
import StockStructureDecisionPage from '../StockStructureDecisionPage';
import { findConsumerRawLeakage, textContentWithoutObservationBoundary } from '../../test-utils/consumerRawLeakageGuard';

const {
  languageState,
  productSurfaceState,
  verifyTickerExistsMock,
  getQuoteMock,
  getHistoryMock,
  getTechnicalIndicatorsMock,
  getStructureDecisionMock,
  getResearchPacketMock,
  getOptionsStructureMock,
  getStructureDecisionsBatchMock,
} = vi.hoisted(() => ({
  languageState: { value: 'zh' as 'zh' | 'en' },
  productSurfaceState: { isAdmin: false },
  verifyTickerExistsMock: vi.fn(),
  getQuoteMock: vi.fn(),
  getHistoryMock: vi.fn(),
  getTechnicalIndicatorsMock: vi.fn(),
  getStructureDecisionMock: vi.fn(),
  getResearchPacketMock: vi.fn(),
  getOptionsStructureMock: vi.fn(),
  getStructureDecisionsBatchMock: vi.fn(),
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: languageState.value,
    t: (key: string) => key,
  }),
}));

vi.mock('../../hooks/useProductSurface', () => ({
  useProductSurface: () => ({
    isAdmin: productSurfaceState.isAdmin,
    isAdminAccount: productSurfaceState.isAdmin,
  }),
}));

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    verifyTickerExists: (...args: unknown[]) => verifyTickerExistsMock(...args),
    getQuote: (...args: unknown[]) => getQuoteMock(...args),
    getHistory: (...args: unknown[]) => getHistoryMock(...args),
    getTechnicalIndicators: (...args: unknown[]) => getTechnicalIndicatorsMock(...args),
    getStructureDecision: (...args: unknown[]) => getStructureDecisionMock(...args),
    getResearchPacket: (...args: unknown[]) => getResearchPacketMock(...args),
    getStructureDecisionsBatch: (...args: unknown[]) => getStructureDecisionsBatchMock(...args),
  },
}));

vi.mock('../../api/optionsLab', () => ({
  optionsLabApi: {
    getOptionsStructure: (...args: unknown[]) => getOptionsStructureMock(...args),
  },
}));

const renderRoutePattern = (ui: React.ReactElement, path: string, pattern: string) => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes>
      <Route path={pattern} element={ui} />
    </Routes>
  </MemoryRouter>,
);

function StockStructureDetailRouteProbe() {
  const { stockCode = '' } = useParams();
  return <div data-testid="stock-structure-detail-route">{stockCode}</div>;
}

const renderStockStructureEntryRoute = (path = '/zh/stock-structure') => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes>
      <Route path="/zh/stock-structure" element={<StockStructureDecisionEntryPage />} />
      <Route path="/zh/research/radar" element={<div data-testid="research-radar-route">research radar</div>} />
      <Route path="/zh/stocks/:stockCode/structure-decision" element={<StockStructureDetailRouteProbe />} />
    </Routes>
  </MemoryRouter>,
);

const cockpitStageIds = [
  'stock-cockpit-stage-quote',
  'stock-cockpit-stage-history-technical',
  'stock-cockpit-stage-earnings',
  'stock-cockpit-stage-options',
  'stock-cockpit-stage-evidence',
  'stock-cockpit-stage-next-steps',
] as const;

function expectCockpitStageOrder(page: HTMLElement) {
  const stages = cockpitStageIds.map((id) => within(page).getByTestId(id));
  expect(stages.map((stage) => stage.getAttribute('data-cockpit-order'))).toEqual(['1', '2', '3', '4', '5', '6']);
  for (let index = 0; index < stages.length - 1; index += 1) {
    expect(stages[index].compareDocumentPosition(stages[index + 1]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  }
}

const baseStructureDecision = () => ({
  schemaVersion: 'stock_structure_decision_api_v1',
  ticker: 'AAPL',
  structureState: 'breakout',
  confidence: 'medium',
  componentScores: {
    trend: 78,
    relativeStrength: 71,
  },
  explanation: {
    whyThisStructure: 'Price stayed above the recent range.',
    whatConfirmsIt: ['Volume remained constructive.'],
    whatInvalidatesIt: ['Closes fall back into the prior range.'],
    keyLevels: [],
  },
  researchNotes: {
    watchNext: ['Review the next close.'],
    needsMoreEvidence: ['Need broader peer evidence.'],
    riskFlags: [],
  },
  dataQuality: {
    status: 'available',
    source: 'local_db',
    period: 'daily',
    requestedDays: 90,
    observedBars: 60,
    usableBars: 60,
    reason: 'history_available',
  },
  missingEvidence: [
    { kind: 'peer_evidence_missing', message: 'Need broader peer evidence.' },
  ],
  noAdviceDisclosure: 'Observation-only research context.',
});

const baseQuote = () => ({
  stockCode: 'AAPL',
  stockName: 'Apple',
  currentPrice: 214.55,
  change: 2.35,
  changePercent: 1.11,
  open: 213,
  high: 215,
  low: 212.5,
  prevClose: 212.2,
  volume: 1000,
  amount: 214550,
  updateTime: '2026-05-28T09:31:00Z',
  source: 'alpaca',
  sourceType: 'provider_runtime',
  marketTimestamp: '2026-05-28T09:30:00Z',
  observedAt: '2026-05-28T09:31:00Z',
  freshness: 'live',
  isFallback: false,
  isStale: false,
  isPartial: false,
  isSynthetic: false,
  sourceConfidence: {
    source: 'alpaca',
    sourceLabel: 'Alpaca',
    asOf: '2026-05-28T09:30:00Z',
    freshness: 'live',
    isFallback: false,
    isStale: false,
    isPartial: false,
    isSynthetic: false,
    isUnavailable: false,
    confidenceWeight: 1,
    coverage: 1,
    degradationReason: null,
    capReason: null,
  },
});

const baseHistory = (symbol = 'AAPL', bars = 60) => ({
  stockCode: symbol,
  stockName: symbol === 'ORCL' ? 'Oracle' : symbol,
  period: 'daily',
  source: 'local_db',
  diagnostics: {
    status: 'available',
    reason: 'history_available',
    requestedDays: 90,
    rows: bars,
  },
  sourceConfidence: {
    source: 'local_db',
    sourceLabel: 'Local history',
    asOf: '2026-05-28',
    freshness: 'fresh',
    isFallback: false,
    isStale: false,
    isPartial: bars < 90,
    isSynthetic: false,
    isUnavailable: false,
    confidenceWeight: 1,
    coverage: bars / 90,
    degradationReason: null,
    capReason: bars < 90 ? 'short_history' : null,
  },
  data: Array.from({ length: bars }, (_, index) => ({
    date: `2026-03-${String((index % 28) + 1).padStart(2, '0')}`,
    open: 100 + index,
    high: 101 + index,
    low: 99 + index,
    close: 100.5 + index,
    volume: 1000 + index * 10,
  })),
});

const technicalIndicatorsAvailable = () => ({
  contractVersion: 'stock_technical_indicators_v1',
  symbol: 'AAPL',
  status: 'available',
  timeframe: 'daily',
  asOf: '2026-05-28T09:30:00Z',
  freshness: 'fresh',
  sourceLabel: 'Local OHLCV boundary',
  dataQuality: {
    status: 'available',
    requiredBars: 200,
    observedBars: 240,
    usableBars: 240,
    missingBars: 0,
    freshness: 'fresh',
  },
  indicators: {
    sma20: { value: 210.12 },
    sma50: { value: 205.34 },
    sma200: { value: 190.56 },
    ema12: { value: 212.45 },
    ema26: { value: 207.89 },
    rsi14: { value: 58.42 },
    macd: { value: 1.234 },
    macdSignal: { value: 0.987 },
    macdHistogram: { value: 0.247 },
    bollingerUpper: { value: 221.45 },
    bollingerMiddle: { value: 210.12 },
    bollingerLower: { value: 198.79 },
  },
  noAdviceDisclosure: 'Research-only technical indicator context.',
});

const technicalIndicatorsMissingCache = () => ({
  contractVersion: 'stock_technical_indicators_v1',
  symbol: 'AAPL',
  status: 'missing_cache',
  timeframe: 'daily',
  asOf: null,
  freshness: 'unknown',
  dataQuality: {
    status: 'missing_cache',
    requiredBars: 200,
    observedBars: 0,
    usableBars: 0,
    missingBars: 200,
    reason: 'missing_cache',
  },
  indicators: {},
  message: 'missing_cache cacheKey provider rawPayload requestId traceId',
});

const technicalIndicatorsInsufficientHistory = () => ({
  contractVersion: 'stock_technical_indicators_v1',
  symbol: 'AAPL',
  status: 'insufficient_history',
  timeframe: 'daily',
  asOf: '2026-05-28',
  freshness: 'fresh',
  dataQuality: {
    status: 'insufficient_history',
    requiredBars: 200,
    observedBars: 60,
    usableBars: 60,
    missingBars: 140,
    reason: 'insufficient_history',
  },
  indicators: {},
});

const partialResearchPacket = () => ({
  symbol: 'AAPL',
  market: 'us',
  identity: {
    name: 'Apple',
    exchange: null,
    sector: null,
    industry: null,
  },
  quote: {
    state: 'available',
    price: 214.55,
    changePercent: 1.11,
    asOf: '2026-05-28T09:30:00Z',
  },
  history: {
    state: 'available',
    bars: 60,
    period: 'daily',
    asOf: '2026-05-28',
  },
  structure: {
    state: 'insufficient',
    label: 'breakout',
    confidence: 'medium',
    asOf: null,
  },
  fundamentals: {
    state: 'stale',
    readinessState: 'stale',
    fieldsAvailable: [],
    supportedFields: {
      companyProfile: ['companyName', 'sector'],
      financialStatements: ['revenueTtm', 'netIncomeTtm', 'fcfTtm'],
      valuation: ['marketCap', 'peTtm'],
      earnings: ['earningsDate'],
    },
    availableFields: {
      valuation: ['marketCap', 'peTtm'],
    },
    missingFields: {
      companyProfile: ['companyName', 'sector'],
      financialStatements: ['revenueTtm', 'netIncomeTtm', 'fcfTtm'],
      earnings: ['earningsDate'],
    },
    staleFields: {
      valuation: ['marketCap', 'peTtm'],
    },
    blockedFields: {},
    categories: {
      companyProfile: {
        state: 'missing',
        supportedFields: ['companyName', 'sector'],
        availableFields: [],
        missingFields: ['companyName', 'sector'],
        staleFields: [],
        blockedFields: [],
      },
      financialStatements: {
        state: 'missing',
        supportedFields: ['revenueTtm', 'netIncomeTtm', 'fcfTtm'],
        availableFields: [],
        missingFields: ['revenueTtm', 'netIncomeTtm', 'fcfTtm'],
        staleFields: [],
        blockedFields: [],
      },
      valuation: {
        state: 'stale',
        supportedFields: ['marketCap', 'peTtm'],
        availableFields: ['marketCap', 'peTtm'],
        missingFields: [],
        staleFields: ['marketCap', 'peTtm'],
        blockedFields: [],
      },
      earnings: {
        state: 'missing',
        supportedFields: ['earningsDate'],
        availableFields: [],
        missingFields: ['earningsDate'],
        staleFields: [],
        blockedFields: [],
      },
    },
    providerNeutralNextDataAction: 'Connect a fundamentals data path for company profile, financial statements, valuation, earnings, and ownership or flow fields.',
    consumerSafeCopy: '基本面数据缺失或更新不完整，已标记为研究观察边界。',
  },
  events: {
    state: 'missing',
    latest: [],
  },
  peer: {
    state: 'insufficient',
    benchmark: null,
  },
  missingData: ['fundamentals', 'filing_event_catalyst', 'peer_benchmark'],
  researchStatus: 'partial',
  nextDataAction: 'Add fundamentals, filing/event/catalyst, and peer evidence before marking the packet ready.',
  observationOnly: true,
  decisionGrade: false,
  noAdviceDisclosure: 'Observation-only research packet; not personalized financial advice and not an instruction.',
});

const completeResearchPacket = () => ({
  ...partialResearchPacket(),
  identity: {
    name: 'Apple',
    exchange: 'NASDAQ',
    sector: 'Technology',
    industry: 'Consumer electronics',
  },
  structure: {
    state: 'available',
    label: 'breakout',
    confidence: 'medium',
    asOf: '2026-05-28',
  },
  fundamentals: {
    state: 'available',
    fieldsAvailable: ['revenue', 'margin'],
  },
  events: {
    state: 'available',
    latest: [
      { title: 'Earnings update', asOf: '2026-05-28' },
    ],
  },
  peer: {
    state: 'available',
    benchmark: 'QQQ',
  },
  missingData: [],
  researchStatus: 'ready',
  nextDataAction: 'Review the next data refresh.',
});

const optionsStructureNotAvailable = () => ({
  contractVersion: 'options-structure-summary-v1',
  symbol: 'AAPL',
  status: 'not_available',
  calculationState: 'not_available',
  observationOnly: true,
  decisionGrade: false,
  providerConfigured: false,
  spotPrice: null,
  asOf: null,
  freshness: 'unknown',
  snapshot: {
    contractVersion: 'option-chain-snapshot-v1',
    symbol: 'AAPL',
    spotPrice: null,
    asOf: null,
    freshness: 'unknown',
    contracts: [],
    missingInputs: ['providerClass', 'apiKeyPresent', 'requestId'],
  },
  strikeSummaries: [],
  expirationSummaries: [],
  nearestExpirations: [],
  zeroDte: {
    state: 'not_available',
    expiration: null,
    dte: null,
    contractCount: 0,
    callOpenInterest: 0,
    putOpenInterest: 0,
    callVolume: 0,
    putVolume: 0,
    openInterestShare: null,
    volumeShare: null,
  },
  gammaFlipLevel: {
    state: 'not_available',
    level: null,
    reason: 'requiredProviderClass',
  },
  totalDealerGammaExposure: null,
  blockingReasons: ['options_structure_provider_missing', 'providerName', 'traceId'],
  warnings: ['endpointHost', 'rawPayload'],
  nextEvidenceNeeded: ['configure_authorized_options_structure_provider', 'credential'],
});

const optionsStructurePopulated = () => ({
  ...optionsStructureNotAvailable(),
  status: 'available',
  calculationState: 'available',
  providerConfigured: true,
  spotPrice: 214.55,
  asOf: '2026-06-19T13:30:00Z',
  freshness: 'live',
  snapshot: {
    contractVersion: 'option-chain-snapshot-v1',
    symbol: 'AAPL',
    spotPrice: 214.55,
    asOf: '2026-06-19T13:30:00Z',
    freshness: 'live',
    contracts: [
      {
        contractSymbol: 'AAPL260619C00215000',
        side: 'call',
        expiration: '2026-06-19',
        strike: 215,
        openInterest: 1200,
        volume: 320,
        charm: -0.12,
        vanna: 0.34,
        dealerGammaExposure: 125000,
        missingInputs: [],
      },
      {
        contractSymbol: 'AAPL260619P00210000',
        side: 'put',
        expiration: '2026-06-19',
        strike: 210,
        openInterest: 800,
        volume: 240,
        charm: 0.02,
        vanna: -0.04,
        dealerGammaExposure: 75000,
        missingInputs: [],
      },
    ],
    missingInputs: [],
  },
  expirationSummaries: [
    {
      expiration: '2026-06-19',
      dte: 0,
      isZeroDte: true,
      strikeCount: 2,
      contractCount: 2,
      callOpenInterest: 1200,
      putOpenInterest: 800,
      callVolume: 320,
      putVolume: 240,
      netDealerGammaExposure: 200000,
      calculationState: 'available',
      missingInputs: [],
    },
  ],
  nearestExpirations: [
    { expiration: '2026-06-19', dte: 0, contractCount: 2 },
  ],
  zeroDte: {
    state: 'available',
    expiration: '2026-06-19',
    dte: 0,
    contractCount: 2,
    callOpenInterest: 1200,
    putOpenInterest: 800,
    callVolume: 320,
    putVolume: 240,
    openInterestShare: 0.42,
    volumeShare: 0.35,
  },
  gammaFlipLevel: {
    state: 'available',
    level: 212.5,
    reason: 'methodology_available',
  },
  totalDealerGammaExposure: 200000,
  blockingReasons: [],
  warnings: [],
  nextEvidenceNeeded: [],
});

describe('StockStructureDecisionPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
    languageState.value = 'zh';
    productSurfaceState.isAdmin = false;
    verifyTickerExistsMock.mockResolvedValue({
      stockCode: 'ORCL',
      normalizedSymbol: 'ORCL',
      market: 'us',
      status: 'valid',
      valid: true,
      exists: true,
      stockName: 'Oracle',
      message: 'Symbol verified.',
    });
    getResearchPacketMock.mockImplementation((symbol: string) => Promise.resolve({
      ...partialResearchPacket(),
      symbol,
    }));
    getQuoteMock.mockResolvedValue({
      ...baseQuote(),
    });
    getHistoryMock.mockImplementation((symbol: string) => Promise.resolve(baseHistory(symbol, 60)));
    getTechnicalIndicatorsMock.mockResolvedValue(technicalIndicatorsAvailable());
    getOptionsStructureMock.mockResolvedValue(optionsStructureNotAvailable());
  });

  it('renders direct symbol input on the stock-structure entry empty state while preserving queue links', () => {
    renderStockStructureEntryRoute();

    const page = screen.getByTestId('stock-structure-entry-page');
    expect(page).toHaveTextContent('直接输入标的');
    expect(screen.getByLabelText('股票代码')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '查看结构' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(screen.getByRole('link', { name: '观察列表上下文' })).toHaveAttribute('href', '/zh/watchlist');
    expect(page).toHaveTextContent('可以直接输入标的，也可以从 Scanner、观察列表或研究雷达选择标的后进入。');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it('shows a validation error for empty direct symbol submit', () => {
    renderStockStructureEntryRoute();

    fireEvent.click(screen.getByRole('button', { name: '查看结构' }));

    expect(screen.getByRole('alert')).toHaveTextContent('请输入股票代码。');
    expect(screen.queryByTestId('stock-structure-detail-route')).not.toBeInTheDocument();
  });

  it('shows a consumer-safe validation error for malformed direct symbols', () => {
    renderStockStructureEntryRoute();

    fireEvent.change(screen.getByLabelText('股票代码'), { target: { value: 'AAPL<script>' } });
    fireEvent.click(screen.getByRole('button', { name: '查看结构' }));

    expect(screen.getByRole('alert')).toHaveTextContent('仅支持字母、数字、点号或短横线组成的股票代码。');
    expect(screen.getByRole('alert').textContent || '').not.toMatch(/provider|requestId|traceId|cache|raw|debug|apiKey|token/i);
    expect(screen.queryByTestId('stock-structure-detail-route')).not.toBeInTheDocument();
  });

  it('navigates a valid direct symbol into the existing structure detail route', () => {
    renderStockStructureEntryRoute();

    fireEvent.change(screen.getByLabelText('股票代码'), { target: { value: ' aapl ' } });
    fireEvent.click(screen.getByRole('button', { name: '查看结构' }));

    expect(screen.getByTestId('stock-structure-detail-route')).toHaveTextContent('AAPL');
  });

  it('keeps carried symbol state visible and deep-links common market formats', () => {
    renderStockStructureEntryRoute('/zh/stock-structure?symbols=0700.HK');

    expect(screen.getByLabelText('股票代码')).toHaveValue('0700.HK');

    fireEvent.click(screen.getByRole('button', { name: '查看结构' }));

    expect(screen.getByTestId('stock-structure-detail-route')).toHaveTextContent('0700.HK');
  });

  it('requests and renders the symbol research packet as a professional evidence stack', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    expectCockpitStageOrder(page);
    expect(within(page).queryByTestId('observation-only-boundary')).not.toBeInTheDocument();
    for (const stageId of cockpitStageIds) {
      expect(within(page).getByTestId(stageId).className).toContain('min-w-0');
    }
    const panel = await within(page).findByTestId('stock-research-packet-panel');
    const quotePanel = await within(page).findByTestId('stock-quote-boundary-panel');
    const historyPanel = await within(page).findByTestId('stock-history-readiness-panel');
    const catalystPanel = await within(page).findByTestId('stock-earnings-catalyst-readiness-panel');
    const optionsStage = await within(page).findByTestId('stock-cockpit-stage-options');
    const nextStepsPanel = await within(page).findByTestId('stock-missing-data-next-steps-panel');

    expect(getQuoteMock).toHaveBeenCalledWith('AAPL');
    expect(getHistoryMock).toHaveBeenCalledWith('AAPL', { period: 'daily', days: 180 });
    expect(getResearchPacketMock).toHaveBeenCalledWith('AAPL');
    expect(within(page).getByTestId('stock-cockpit-stage-quote')).toHaveTextContent('安全基线');
    expect(within(page).getByTestId('stock-cockpit-stage-history-technical')).toHaveTextContent('历史与指标就绪度');
    expect(within(page).getByTestId('stock-cockpit-stage-earnings')).toHaveTextContent('先看就绪度');
    expect(optionsStage).toHaveTextContent('期权就绪度');
    expect(within(page).getByTestId('stock-cockpit-stage-evidence')).toHaveTextContent('研究证据就绪度');
    expect(within(page).getByTestId('stock-cockpit-stage-next-steps')).toHaveTextContent('下一步缺什么');
    expect(quotePanel).toHaveTextContent('报价来源与新鲜度');
    expect(quotePanel).toHaveTextContent('报价可用');
    expect(quotePanel).toHaveTextContent('来源已确认');
    expect(quotePanel).toHaveTextContent('最新可用');
    expect(quotePanel).toHaveTextContent('更新');
    expect(quotePanel).toHaveTextContent('05/28');
    expect(quotePanel).toHaveTextContent('17:30');
    const summary = within(page).getByTestId('stock-consumer-research-summary');
    expect(summary).toHaveTextContent('AAPL');
    expect(summary).toHaveTextContent('Apple');
    expect(summary).toHaveTextContent('US');
    expect(summary).toHaveTextContent('$214.6');
    expect(summary).toHaveTextContent('+1.11%');
    expect(summary).toHaveTextContent('更新 05/28 17:30');
    expect(summary).toHaveTextContent('突破观察');
    expect(summary).toHaveTextContent('置信度：中');
    expect(summary).toHaveTextContent('置信度为中：报价、历史与结构证据可用，但基本面、事件或同业证据仍限制结论强度。');
    expect(summary).toHaveTextContent('AAPL 当前呈现突破观察，报价最新可用，历史 K 线可用于查看走势。');
    expect(summary).toHaveTextContent('当前观察');
    expect(summary).toHaveTextContent('关键证据');
    expect(summary).toHaveTextContent('关键限制');
    expect(summary).toHaveTextContent('下一步检查');
    expect(summary).toHaveTextContent('研究观察，不构成投资建议。');
    expect(summary).toHaveTextContent('查看研究雷达');
    expect(summary).toHaveTextContent('打开回测');
    expect(summary).toHaveTextContent('复制证据');
    const firstViewportPanel = within(page).getByTestId('stock-first-viewport-summary-panel');
    expect(firstViewportPanel).toHaveTextContent('研究状态：中');
    expect(firstViewportPanel).toHaveTextContent('历史数据可用');
    const trustRow = within(page).getByTestId('stock-data-trust-row');
    expect(trustRow).toHaveTextContent('报价');
    expect(trustRow).toHaveTextContent('最新可用');
    expect(trustRow).toHaveTextContent('历史');
    expect(trustRow).toHaveTextContent('60 / 90 根');
    expect(trustRow).toHaveTextContent('技术指标');
    expect(trustRow).toHaveTextContent('指标可用');
    expect(trustRow).toHaveTextContent('证据');
    expect(trustRow).toHaveTextContent('可用');
    const stockCoreChart = within(page).getByTestId('stock-history-core-chart');
    expect(within(page).getByTestId('stock-price-history-visual-block')).toContainElement(stockCoreChart);
    expect(stockCoreChart.compareDocumentPosition(within(page).getByTestId('stock-cockpit-stage-quote')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(page).getByTestId('stock-detail-collapsed-evidence-boundary')).not.toHaveAttribute('open');
    expect(within(page).getByTestId('stock-detail-collapsed-history-technical')).not.toHaveAttribute('open');
    expect(within(page).getByTestId('stock-detail-collapsed-secondary-details')).not.toHaveAttribute('open');
    expect(stockCoreChart).toHaveAttribute('data-chart-kind', 'stock-history');
    expect(stockCoreChart).toHaveTextContent('价格趋势');
    expect(stockCoreChart).toHaveTextContent('成交量');
    expect(stockCoreChart).toHaveTextContent('历史数据可用');
    expect(stockCoreChart).toHaveTextContent('历史样本不足');
    expect(stockCoreChart).toHaveTextContent('60 / 90');
    expect(stockCoreChart).toHaveTextContent('本地历史数据');
    expect(stockCoreChart).toHaveAttribute('data-chart-engine', 'echarts');
    expect(stockCoreChart).toHaveAttribute('data-render-mode', 'candlestick');
    expect(stockCoreChart).toHaveAttribute('data-volume-panel', 'true');
    expect(stockCoreChart).toHaveAttribute('data-enabled-overlays', 'MA5,MA20');
    expect(within(stockCoreChart).getByTestId('core-market-chart-frame')).toBeInTheDocument();
    expect(within(stockCoreChart).getByTestId('core-market-echarts-node')).toHaveAttribute(
      'aria-label',
      expect.stringContaining('AAPL 价格与成交量历史'),
    );
    expect(within(stockCoreChart).getByTestId('core-market-chart-volume-context')).toHaveTextContent('成交量');
    expect(within(stockCoreChart).getByTestId('core-market-chart-range-controls')).toHaveTextContent('1D');
    expect(within(stockCoreChart).getByTestId('core-market-chart-range-controls')).toHaveTextContent('全部');
    expect(within(stockCoreChart).getByTestId('core-market-chart-overlay-legend')).toHaveTextContent('MA5');
    expect(within(stockCoreChart).getByTestId('core-market-chart-overlay-legend')).toHaveTextContent('MA20');
    fireEvent.click(within(stockCoreChart).getByRole('button', { name: /1M/ }));
    expect(stockCoreChart).toHaveAttribute('data-active-range', '1M');
    fireEvent.mouseMove(within(stockCoreChart).getByTestId('core-market-chart-frame'), { clientX: 640 });
    const chartTooltip = within(stockCoreChart).getByTestId('core-market-hover-tooltip');
    expect(chartTooltip).toHaveTextContent('开盘');
    expect(chartTooltip).toHaveTextContent('最高');
    expect(chartTooltip).toHaveTextContent('最低');
    expect(chartTooltip).toHaveTextContent('收盘');
    expect(chartTooltip).toHaveTextContent('成交量');
    expect(panel).toHaveTextContent('证据栈');
    expect(panel).toHaveTextContent('AAPL');
    expect(panel).toHaveTextContent('Apple');
    expect(panel).toHaveTextContent('证据部分可用');
    expect(panel).toHaveTextContent('仅观察');
    expect(panel).toHaveTextContent('评分待确认');
    expect(panel).toHaveTextContent('可用 1');
    expect(panel).toHaveTextContent('待补 2');
    expect(panel).toHaveTextContent('部分 2');
    expect(panel).not.toHaveTextContent('报价可用');
    expect(panel).not.toHaveTextContent('历史可用');
    expect(panel).toHaveTextContent('标的上下文可用');
    expect(panel).toHaveTextContent('基本面待补');
    expect(panel).toHaveTextContent('财报 / 催化证据待补');
    expect(panel).toHaveTextContent('延迟 1');
    expect(panel).toHaveTextContent('基本面数据缺失');
    expect(panel).toHaveTextContent('公司画像待补');
    expect(panel).toHaveTextContent('财报主字段待补');
    expect(panel).toHaveTextContent('估值字段延迟');
    expect(panel).toHaveTextContent('财报日期待补');
    expect(panel).toHaveTextContent('companyName');
    expect(panel).toHaveTextContent('revenueTtm');
    expect(panel).toHaveTextContent('earningsDate');
    expect(panel).toHaveTextContent('Connect a fundamentals data path');
    expect(panel).toHaveTextContent('新闻线索待补');
    expect(panel).toHaveTextContent('风险来源待补');
    expect(panel).toHaveTextContent('市场线索待补');
    expect(panel).toHaveTextContent('研究包可用');
    expect(panel).toHaveTextContent('下一证据缺口');
    expect(panel).toHaveTextContent('基本面待补');
    expect(panel).toHaveTextContent('新闻线索待补');
    expect(panel).toHaveTextContent('市场线索待补');
    expect(catalystPanel).toHaveTextContent('财报 / 催化证据待补');
    expect(catalystPanel).toHaveTextContent('仍需补齐公告、财报或催化证据。');
    expect(nextStepsPanel).toHaveTextContent('下一步补齐资料');
    expect(nextStepsPanel).toHaveTextContent('基本面待补');
    expect(nextStepsPanel).toHaveTextContent('新闻线索待补');
    expect(nextStepsPanel).toHaveTextContent('结构来源待配置');
    expect(historyPanel).toHaveTextContent('AAPL 历史数据就绪度');
    expect(historyPanel).toHaveTextContent('历史数据可用');
    expect(historyPanel).toHaveTextContent('结构样本不足');
    expect(historyPanel).toHaveTextContent('可用 K 线');
    expect(historyPanel).toHaveTextContent('60');
    expect(historyPanel).toHaveTextContent('所需 K 线');
    expect(historyPanel).toHaveTextContent('90');
    expect(historyPanel).toHaveTextContent('缺口 K 线');
    expect(historyPanel).toHaveTextContent('30');
    expect(within(historyPanel).queryByTestId('stock-history-core-chart')).not.toBeInTheDocument();
    expect(findConsumerRawLeakage(page.textContent || '', {
      extraForbiddenPatterns: [
        /\bavailable\b/i,
        /\bnot_integrated\b/i,
        /\binsufficient\b/i,
        /\bblocked\b/i,
        /\bobservationOnly\b/i,
        /not personalized financial advice/i,
      ],
    })).toEqual([]);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/available|not_integrated|insufficient|blocked|observationOnly|not personalized financial advice/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/buy|sell|hold|target price|stop-loss|position sizing|买入|卖出|持有|目标价|止损|仓位|建仓|加仓|减仓/i);
  });

  it('renders ORCL-specific history readiness instead of a default symbol', async () => {
    getResearchPacketMock.mockResolvedValue({
      ...completeResearchPacket(),
      symbol: 'ORCL',
      identity: {
        name: 'Oracle',
        exchange: 'NYSE',
        sector: 'Technology',
        industry: 'Enterprise software',
      },
      history: {
        state: 'available',
        bars: 120,
        period: 'daily',
        asOf: '2026-05-28',
      },
    });
    getStructureDecisionMock.mockResolvedValue({
      ...baseStructureDecision(),
      ticker: 'ORCL',
      dataQuality: {
        ...baseStructureDecision().dataQuality,
        requestedDays: 90,
        observedBars: 120,
        usableBars: 120,
      },
    });
    getHistoryMock.mockResolvedValue(baseHistory('ORCL', 120));

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/ORCL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const historyPanel = await within(page).findByTestId('stock-history-readiness-panel');

    expect(getStructureDecisionMock).toHaveBeenCalledWith('ORCL');
    expect(getResearchPacketMock).toHaveBeenCalledWith('ORCL');
    expect(getHistoryMock).toHaveBeenCalledWith('ORCL', { period: 'daily', days: 180 });
    expect(page).toHaveTextContent('ORCL 结构工作区');
    expect(historyPanel).toHaveTextContent('ORCL 历史数据就绪度');
    expect(historyPanel).toHaveTextContent('可用 K 线');
    expect(historyPanel).toHaveTextContent('120');
    expect(historyPanel).toHaveTextContent('缺口 K 线');
    expect(historyPanel).toHaveTextContent('0');
    expect(historyPanel).toHaveTextContent('结构计算已返回');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/\bAAPL\b/);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it('renders a 600519 history-disabled or missing state without chart inference', async () => {
    verifyTickerExistsMock.mockResolvedValueOnce({
      stockCode: '600519',
      normalizedSymbol: '600519',
      market: 'cn',
      status: 'valid',
      valid: true,
      exists: true,
      stockName: '贵州茅台',
      message: 'Symbol verified.',
    });
    getResearchPacketMock.mockResolvedValue({
      ...partialResearchPacket(),
      symbol: '600519',
      market: 'cn',
      identity: {
        name: '贵州茅台',
        exchange: 'SSE',
        sector: null,
        industry: null,
      },
      history: {
        state: 'missing',
        bars: 0,
        period: 'daily',
        asOf: null,
      },
      structure: {
        state: 'insufficient',
        label: null,
        confidence: 'low',
        asOf: null,
      },
    });
    getStructureDecisionMock.mockResolvedValue({
      ...baseStructureDecision(),
      ticker: '600519',
      structureState: 'low_confidence',
      confidence: 'low',
      componentScores: {},
      explanation: {
        whyThisStructure: null,
        whatConfirmsIt: [],
        whatInvalidatesIt: [],
        keyLevels: [],
      },
      researchNotes: {
        watchNext: [],
        needsMoreEvidence: ['Need local historical bars.'],
        riskFlags: [],
      },
      dataQuality: {
        status: 'partial',
        source: null,
        period: 'daily',
        requestedDays: 90,
        observedBars: 0,
        usableBars: 0,
        reason: 'history_source_disabled',
      },
      missingEvidence: [
        { kind: 'daily_ohlcv', message: 'Need local historical bars.' },
      ],
    });
    getHistoryMock.mockResolvedValue({
      ...baseHistory('600519', 0),
      diagnostics: {
        status: 'unavailable',
        reason: 'provider_disabled cache_miss',
        requestedDays: 90,
        rows: 0,
      },
      sourceConfidence: {
        ...baseHistory('600519', 0).sourceConfidence,
        isUnavailable: true,
        confidenceWeight: 0,
        coverage: 0,
        degradationReason: 'history_source_disabled',
      },
      data: [],
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/600519/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const historyPanel = await within(page).findByTestId('stock-history-readiness-panel');

    expect(getHistoryMock).toHaveBeenCalledWith('600519', { period: 'daily', days: 180 });
    expect(page).toHaveTextContent('600519 结构工作区');
    expect(historyPanel).toHaveTextContent('600519 历史数据就绪度');
    expect(historyPanel).toHaveTextContent('历史来源未启用');
    expect(historyPanel).toHaveTextContent('结构样本不足');
    expect(historyPanel).toHaveTextContent('可用 K 线');
    expect(historyPanel).toHaveTextContent('0');
    expect(historyPanel).toHaveTextContent('缺口 K 线');
    expect(historyPanel).toHaveTextContent('90');
    const summary = within(page).getByTestId('stock-consumer-research-summary');
    expect(summary).toHaveTextContent('历史数据暂缺，价格走势图暂不可用。');
    expect(summary).toHaveTextContent('置信度为低：关键价格、历史或结构证据不足，页面只保留可核验事实。');
    const emptyChart = within(page).getByTestId('stock-history-empty-chart-state');
    expect(within(page).getByTestId('stock-price-history-visual-block')).toContainElement(
      emptyChart,
    );
    expect(emptyChart).toHaveTextContent('图表暂不可用');
    expect(emptyChart).toHaveTextContent('历史数据待补');
    expect(within(page).queryByText('组件评分')).not.toBeInTheDocument();
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/provider_disabled|cache_miss|provider|cache|raw|debug|trace/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it('distinguishes a timed-out structure computation from available history', async () => {
    getStructureDecisionMock.mockResolvedValue({
      ...baseStructureDecision(),
      ticker: 'ORCL',
      structureState: 'low_confidence',
      confidence: 'low',
      dataQuality: {
        ...baseStructureDecision().dataQuality,
        status: 'degraded',
        requestedDays: 90,
        observedBars: 90,
        usableBars: 90,
        reason: 'computation_timed_out',
      },
    });
    getHistoryMock.mockResolvedValue(baseHistory('ORCL', 90));

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/ORCL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const historyPanel = await within(page).findByTestId('stock-history-readiness-panel');

    expect(historyPanel).toHaveTextContent('历史数据可用');
    expect(historyPanel).toHaveTextContent('结构计算超时');
    expect(historyPanel).toHaveTextContent('结构服务返回超时或部分计算状态。');
  });

  it('renders provider-backed quote lineage without leaking raw provider internals', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const quotePanel = await within(page).findByTestId('stock-quote-boundary-panel');

    expect(quotePanel).toHaveTextContent('报价来源与新鲜度');
    expect(quotePanel).toHaveTextContent('报价可用');
    expect(quotePanel).toHaveTextContent('来源已确认');
    expect(quotePanel).toHaveTextContent('最新可用');
    expect(quotePanel).toHaveTextContent('更新');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/alpaca|provider_runtime|source_confidence|requestId|traceId|cache|debug/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it('renders cached OHLCV technical indicator values as research-only context', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());
    getTechnicalIndicatorsMock.mockResolvedValue(technicalIndicatorsAvailable());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const panel = await within(page).findByTestId('stock-technical-indicators-panel');

    expect(getTechnicalIndicatorsMock).toHaveBeenCalledWith('AAPL');
    expect(panel).toHaveTextContent('本地 OHLCV 技术指标');
    expect(panel).toHaveTextContent('指标可用');
    expect(panel).toHaveTextContent('本地 OHLCV 边界');
    expect(panel).toHaveTextContent('最新可用');
    expect(panel).toHaveTextContent('SMA 20');
    expect(panel).toHaveTextContent('210.12');
    expect(panel).toHaveTextContent('SMA 50');
    expect(panel).toHaveTextContent('205.34');
    expect(panel).toHaveTextContent('SMA 200');
    expect(panel).toHaveTextContent('190.56');
    expect(panel).toHaveTextContent('EMA 12');
    expect(panel).toHaveTextContent('212.45');
    expect(panel).toHaveTextContent('EMA 26');
    expect(panel).toHaveTextContent('207.89');
    expect(panel).toHaveTextContent('RSI 14');
    expect(panel).toHaveTextContent('58.42');
    expect(panel).toHaveTextContent('MACD');
    expect(panel).toHaveTextContent('1.234');
    expect(panel).toHaveTextContent('MACD 信号线');
    expect(panel).toHaveTextContent('0.987');
    expect(panel).toHaveTextContent('MACD 柱');
    expect(panel).toHaveTextContent('0.247');
    expect(panel).toHaveTextContent('布林带上轨');
    expect(panel).toHaveTextContent('221.45');
    expect(panel).toHaveTextContent('布林带中轨');
    expect(panel).toHaveTextContent('210.12');
    expect(panel).toHaveTextContent('布林带下轨');
    expect(panel).toHaveTextContent('198.79');
    expect(panel).toHaveTextContent('仅作研究观察上下文');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it('renders missing-cache technical indicators without fabricating values', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());
    getTechnicalIndicatorsMock.mockResolvedValue(technicalIndicatorsMissingCache());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const panel = await within(page).findByTestId('stock-technical-indicators-panel');

    expect(panel).toHaveTextContent('本地 OHLCV 数据暂不可用');
    expect(panel).toHaveTextContent('本地数据待补');
    expect(panel).toHaveTextContent('所需历史');
    expect(panel).toHaveTextContent('200');
    expect(panel).toHaveTextContent('已观察历史');
    expect(panel).toHaveTextContent('0');
    expect(panel).toHaveTextContent('历史缺口');
    expect(panel).toHaveTextContent('200');
    expect(panel).toHaveTextContent('不推断指标');
    expect(panel).not.toHaveTextContent('210.12');
    expect(panel).not.toHaveTextContent('SMA 20');
    expect(findConsumerRawLeakage(panel.textContent || '', {
      extraForbiddenPatterns: [/cacheKey|provider|rawPayload|requestId|traceId|missing_cache/i],
    })).toEqual([]);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it('renders insufficient-history technical indicators with required versus observed history', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());
    getTechnicalIndicatorsMock.mockResolvedValue(technicalIndicatorsInsufficientHistory());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const panel = await screen.findByTestId('stock-technical-indicators-panel');

    expect(panel).toHaveTextContent('历史样本不足，暂不计算指标');
    expect(panel).toHaveTextContent('所需历史');
    expect(panel).toHaveTextContent('200');
    expect(panel).toHaveTextContent('已观察历史');
    expect(panel).toHaveTextContent('60');
    expect(panel).toHaveTextContent('历史缺口');
    expect(panel).toHaveTextContent('140');
    expect(panel).toHaveTextContent('页面不会计算部分或替代指标值。');
    expect(panel).not.toHaveTextContent('SMA 200');
    expect(panel).not.toHaveTextContent('MACD 信号线');
    expect(panel).not.toHaveTextContent('布林带上轨');
  });

  it('renders a technical-indicators API error without raw diagnostics', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());
    getTechnicalIndicatorsMock.mockRejectedValue(new Error('provider cacheKey requestId traceId rawPayload token env stack'));

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const panel = await within(page).findByTestId('stock-technical-indicators-panel');

    expect(panel).toHaveTextContent('技术指标暂不可用');
    expect(panel).toHaveTextContent('接口暂不可用');
    expect(panel).toHaveTextContent('不展示原始诊断，也不推断指标');
    expect(panel.textContent || '').not.toMatch(/provider|cacheKey|requestId|traceId|rawPayload|token|env|stack/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it('copies a single stock evidence pack JSON with quote lineage, readiness, warnings, and visible research state', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const registry = await within(page).findByTestId('single-stock-evidence-pack-registry');

    expect(registry).toHaveTextContent('个股证据包');
    expect(registry).toHaveTextContent('复制个股证据包');
    expect(registry).toHaveTextContent('导出个股证据包');
    expect(registry).toHaveTextContent('报价');
    expect(registry).toHaveTextContent('新鲜度');
    expect(registry).toHaveTextContent('证据状态');

    fireEvent.click(within(registry).getByTestId('single-stock-evidence-pack-copy'));

    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    const copied = String((navigator.clipboard.writeText as ReturnType<typeof vi.fn>).mock.calls.at(-1)?.[0] || '');
    const pack = JSON.parse(copied);

    expect(pack.schemaVersion).toBe('single-stock-evidence-pack.v1');
    expect(pack.generatedAt).toEqual(expect.any(String));
    expect(pack.appSurface).toBe('Single Stock / Structure');
    expect(pack.symbol).toBe('AAPL');
    expect(pack.quoteLineage).toMatchObject({
      asOf: '2026-05-28T09:30:00Z',
      sourceLabel: 'Alpaca',
      freshness: 'live',
      confidenceWeight: 1,
      coverage: 1,
    });
    expect(pack.dataReadiness).toMatchObject({
      quoteState: '报价可用',
      researchState: '证据部分可用',
      observationOnly: true,
      decisionGrade: false,
    });
    expect(pack.warnings).toEqual(expect.arrayContaining(['基本面待补', '新闻线索待补', '市场线索待补']));
    expect(pack.visibleResearchSummary).toEqual(expect.arrayContaining([
      expect.objectContaining({ label: '标的', value: 'AAPL' }),
      expect.objectContaining({ label: '技术状态', value: '突破观察' }),
    ]));
    expect(copied).not.toMatch(/recommend|winner|best|optimal|buy|sell|hold|target price|stop loss|position sizing/i);
    expect(copied).not.toMatch(/requestId|traceId|debug|rawPayload|providerPayload|credential|sourceType|provider_runtime/i);
    expect(copied).not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位|最优|赢家/);
  });

  it('exports unknown fields as 待补证 instead of inferring quote lineage', async () => {
    getQuoteMock.mockResolvedValue({
      ...baseQuote(),
      updateTime: null,
      marketTimestamp: null,
      observedAt: null,
      freshness: null,
      source: null,
      sourceType: null,
      sourceConfidence: {
        source: null,
        sourceLabel: null,
        asOf: null,
        freshness: null,
        isFallback: false,
        isStale: false,
        isPartial: false,
        isSynthetic: false,
        isUnavailable: false,
        confidenceWeight: null,
        coverage: null,
        degradationReason: null,
        capReason: null,
      },
    });
    getResearchPacketMock.mockResolvedValue({
      ...partialResearchPacket(),
      quote: {
        state: 'unknown',
        price: null,
        changePercent: null,
        asOf: null,
      },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const registry = await screen.findByTestId('single-stock-evidence-pack-registry');
    fireEvent.click(within(registry).getByTestId('single-stock-evidence-pack-copy'));

    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    const copied = String((navigator.clipboard.writeText as ReturnType<typeof vi.fn>).mock.calls.at(-1)?.[0] || '');
    const pack = JSON.parse(copied);

    expect(pack.quoteLineage).toMatchObject({
      asOf: '待补证',
      sourceLabel: '待补证',
      freshness: '待补证',
      confidenceWeight: '待补证',
      coverage: '待补证',
    });
    expect(pack.dataReadiness.quoteState).toBe('报价待补');
  });

  it('does not export fake evidence when quote evidence is unavailable', async () => {
    getQuoteMock.mockRejectedValueOnce(new Error('quote unavailable'));
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const registry = await within(page).findByTestId('single-stock-evidence-pack-registry');

    expect(registry).toHaveTextContent('待补证');
    expect(within(registry).getByTestId('single-stock-evidence-pack-copy-blocked')).toBeDisabled();
    expect(within(registry).queryByTestId('single-stock-evidence-pack-copy')).not.toBeInTheDocument();
    expect(within(registry).queryByTestId('single-stock-evidence-pack-download')).not.toBeInTheDocument();
    expect(navigator.clipboard.writeText).not.toHaveBeenCalled();
  });

  it('does not show evidence pack export controls when the stock result is unsupported', async () => {
    verifyTickerExistsMock.mockResolvedValueOnce({
      stockCode: 'BAD',
      normalizedSymbol: 'BAD',
      market: 'unknown',
      status: 'unsupported_market',
      valid: false,
      exists: false,
      stockName: null,
      message: 'unsupported',
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/BAD/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');

    expect(await within(page).findByTestId('stock-structure-symbol-not-found-state')).toBeInTheDocument();
    expect(within(page).queryByTestId('single-stock-evidence-pack-registry')).not.toBeInTheDocument();
    expect(navigator.clipboard.writeText).not.toHaveBeenCalled();
  });

  it('renders sample, stale, and missing lineage states as observation only', async () => {
    getQuoteMock.mockResolvedValue({
      ...baseQuote(),
      freshness: 'stale',
      isStale: true,
      sourceConfidence: null,
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const quotePanel = await within(page).findByTestId('stock-quote-boundary-panel');

    expect(quotePanel).toHaveTextContent('报价可能延迟');
    expect(quotePanel).toHaveTextContent('来源待确认');
    expect(quotePanel).toHaveTextContent('可能延迟');
    expect(quotePanel).toHaveTextContent('报价已返回，但来源边界未提供。');
    expect(quotePanel).not.toHaveTextContent('来源已确认');
    expect(quotePanel).not.toHaveTextContent('最新可用');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/provider|cache|debug|trace|sourceAuthority|raw|fallback/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it('renders sample quote lineage as observation only', async () => {
    getQuoteMock.mockResolvedValue({
      ...baseQuote(),
      currentPrice: 0,
      freshness: 'synthetic',
      isSynthetic: true,
      isPartial: true,
      source: 'fixture',
      sourceType: 'synthetic_placeholder',
      sourceConfidence: {
        ...baseQuote().sourceConfidence,
        source: 'fixture',
        sourceLabel: 'Fixture',
        asOf: null,
        freshness: 'synthetic',
        isFallback: false,
        isStale: false,
        isPartial: true,
        isSynthetic: true,
        isUnavailable: false,
        confidenceWeight: 0,
        coverage: null,
        degradationReason: 'synthetic_source',
        capReason: null,
      },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const quotePanel = await within(page).findByTestId('stock-quote-boundary-panel');

    expect(quotePanel).toHaveTextContent('样本报价');
    expect(quotePanel).toHaveTextContent('样本 / 演示');
    expect(quotePanel).toHaveTextContent('当前为样本/演示数据，仅供观察。');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/provider|cache|debug|trace|sourceAuthority|raw|fallback/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it('renders a compact fail-closed boundary when the quote call is unavailable', async () => {
    getQuoteMock.mockRejectedValueOnce(new Error('quote unavailable'));
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const quotePanel = await within(page).findByTestId('stock-quote-boundary-panel');

    expect(quotePanel).toHaveTextContent('报价边界暂不可用');
    expect(quotePanel).toHaveTextContent('仅观察');
    expect(quotePanel).toHaveTextContent('来源待确认');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/provider|cache|debug|trace|sourceAuthority|raw|fallback/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it('shows the options structure provider-missing state without fake analytics', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());
    getOptionsStructureMock.mockResolvedValue(optionsStructureNotAvailable());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const surface = await within(page).findByTestId('stock-options-structure-surface');
    const metrics = within(surface).getByTestId('stock-options-structure-metrics');

    expect(getOptionsStructureMock).toHaveBeenCalledWith('AAPL');
    expect(surface).toHaveTextContent('专业结构指标');
    expect(surface).toHaveTextContent('结构暂不可用');
    expect(surface).toHaveTextContent('结构来源待配置');
    expect(surface).toHaveTextContent('新鲜度待确认');
    expect(surface).toHaveTextContent('仍需配置授权期权结构来源后才会填充指标。');
    expect(surface).toHaveTextContent('待配置授权结构来源');
    expect(metrics).toHaveTextContent('GEX');
    expect(metrics).toHaveTextContent('Gamma flip');
    expect(metrics).toHaveTextContent('Vanna');
    expect(metrics).toHaveTextContent('Charm');
    expect(metrics).toHaveTextContent('0DTE 集中度');
    expect(metrics).toHaveTextContent('OI / 成交');
    expect(metrics.textContent?.match(/待补证/g) ?? []).toHaveLength(6);
    expect(findConsumerRawLeakage(surface.textContent || '', {
      extraForbiddenPatterns: [
        /providerClass|providerName|providerAttempted|requiredProviderClass|sourceAuthorityRouter/i,
        /endpointHost|apiKeyPresent|exceptionClass|exceptionChain|requestId|traceId|cacheKey|rawPayload/i,
        /credential|token|env/i,
        /options_structure_provider_missing|configure_authorized_options_structure_provider/i,
      ],
    })).toEqual([]);
  });

  it('renders populated options structure metrics from fixture data', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());
    getOptionsStructureMock.mockResolvedValue(optionsStructurePopulated());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const surface = await screen.findByTestId('stock-options-structure-surface');
    const metrics = within(surface).getByTestId('stock-options-structure-metrics');

    expect(surface).toHaveTextContent('结构可用');
    expect(surface).toHaveTextContent('结构来源已配置');
    expect(surface).toHaveTextContent('更新');
    expect(surface).toHaveTextContent('06/19');
    expect(metrics).toHaveTextContent('200,000');
    expect(metrics).toHaveTextContent('212.5');
    expect(metrics).toHaveTextContent('0.3');
    expect(metrics).toHaveTextContent('-0.1');
    expect(metrics).toHaveTextContent('OI 42%');
    expect(metrics).toHaveTextContent('成交 35%');
    expect(metrics).toHaveTextContent('2,000 / 560');
    expect(metrics).not.toHaveTextContent('待补证');
  });

  it('renders an options structure endpoint failure state without raw diagnostics', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());
    getOptionsStructureMock.mockRejectedValue(new Error('providerClass requiredProviderClass requestId traceId rawPayload credential token env'));

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const surface = await within(page).findByTestId('stock-options-structure-surface');

    expect(surface).toHaveTextContent('期权结构暂不可用');
    expect(surface).toHaveTextContent('接口暂不可用');
    expect(surface).toHaveTextContent('不推断指标');
    expect(page).toHaveTextContent('突破观察');
    expect(surface.textContent || '').not.toMatch(/providerClass|requiredProviderClass|requestId|traceId|rawPayload|credential|token|env/i);
  });

  it('renders a complete evidence stack when all existing packet families are available', async () => {
    getResearchPacketMock.mockResolvedValue(completeResearchPacket());
    getStructureDecisionMock.mockResolvedValue({
      ...baseStructureDecision(),
      researchNotes: {
        watchNext: ['Review the next close.'],
        needsMoreEvidence: [],
        riskFlags: ['Volatility remains elevated.'],
      },
      missingEvidence: [],
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const panel = await within(page).findByTestId('stock-research-packet-panel');

    expect(panel).toHaveTextContent('证据完整');
    expect(panel).toHaveTextContent('基本面可用');
    expect(panel).toHaveTextContent('催化线索可用');
    expect(panel).toHaveTextContent('风险来源可用');
    expect(panel).toHaveTextContent('市场线索可用');
    expect(panel).toHaveTextContent('研究包可用');
    expect(panel).not.toHaveTextContent('报价可用');
    expect(panel).not.toHaveTextContent('历史可用');
    expect(panel).not.toHaveTextContent('下一证据缺口');
    expect(findConsumerRawLeakage(page.textContent || '', {
      extraForbiddenPatterns: [
        /\bavailable\b/i,
        /\bobservationOnly\b/i,
      ],
    })).toEqual([]);
  });

  it('renders delayed, missing, and partial evidence with consumer-safe labels', async () => {
    getResearchPacketMock.mockResolvedValue({
      ...partialResearchPacket(),
      quote: {
        state: 'stale',
        price: null,
        changePercent: null,
        asOf: null,
      },
      history: {
        state: 'missing',
        bars: null,
        period: 'daily',
        asOf: null,
      },
      nextDataAction: 'provider runtime fallback sourceAuthority debug buy now target price',
      missingData: ['quote', 'price_history', 'fundamentals', 'filing_event_catalyst', 'peer_benchmark'],
    });
    getStructureDecisionMock.mockResolvedValue({
      ...baseStructureDecision(),
      dataQuality: {
        ...baseStructureDecision().dataQuality,
        status: 'partial',
        usableBars: 0,
      },
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const panel = await within(page).findByTestId('stock-research-packet-panel');

    expect(panel).toHaveTextContent('证据部分可用');
    expect(panel).toHaveTextContent('基本面待补');
    expect(panel).toHaveTextContent('财报 / 催化证据待补');
    expect(panel).toHaveTextContent('风险来源待补');
    expect(panel).toHaveTextContent('市场线索待补');
    expect(panel).toHaveTextContent('延迟 1');
    expect(panel).toHaveTextContent('下一证据缺口');
    expect(panel).toHaveTextContent('报价待补');
    expect(panel).toHaveTextContent('历史待补');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/provider|runtime|fallback|sourceAuthority|debug|buy now|target price/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入建议|卖出建议|持有建议|目标价|止损|仓位建议|交易建议|操作建议/);
  });

  it('shows a safe admin-only data readiness cue when stock evidence is missing', async () => {
    productSurfaceState.isAdmin = true;
    getResearchPacketMock.mockResolvedValue({
      ...partialResearchPacket(),
      missingData: ['fundamentals', 'filing_event_catalyst', 'peer_benchmark'],
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const nextStepsPanel = await within(page).findByTestId('stock-missing-data-next-steps-panel');
    const adminLink = within(nextStepsPanel).getByRole('link', { name: '打开数据就绪诊断' });

    expect(adminLink).toHaveAttribute('href', '/zh/admin/market-providers?surface=stock_structure&symbol=AAPL');
    expect(nextStepsPanel).toHaveTextContent('仅管理员可见');
    expect(nextStepsPanel.textContent || '').not.toMatch(/provider|requestId|traceId|cacheKey|raw|debug|apiKey|token/i);
  });

  it('does not show the data readiness admin cue to non-admin consumers', async () => {
    getResearchPacketMock.mockResolvedValue({
      ...partialResearchPacket(),
      missingData: ['fundamentals', 'filing_event_catalyst', 'peer_benchmark'],
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const nextStepsPanel = await within(page).findByTestId('stock-missing-data-next-steps-panel');

    expect(within(nextStepsPanel).queryByRole('link', { name: '打开数据就绪诊断' })).not.toBeInTheDocument();
    expect(nextStepsPanel.textContent || '').not.toMatch(/provider|requestId|traceId|cacheKey|raw|debug|apiKey|token/i);
  });

  it('shows a compact packet fallback without hiding existing structure facts', async () => {
    getResearchPacketMock.mockRejectedValue(new Error('packet unavailable'));
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const panel = await within(page).findByTestId('stock-research-packet-panel');

    expect(panel).toHaveTextContent('研究包待更新');
    expect(page).toHaveTextContent('突破观察');
    expect(page).toHaveTextContent('主要结构线索');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/sorry|apology|available|not_integrated|observationOnly/i);
  });

  it('maps internal stock structure and peer evidence terms to consumer-safe labels', async () => {
    getStructureDecisionMock.mockResolvedValue({
      schemaVersion: 'stock_structure_decision_api_v1',
      ticker: 'ORCL',
      structureState: 'breakdown',
      confidence: 'low',
      componentScores: {
        trend: 58,
        relativeStrength: 52,
      },
      explanation: {
        whyThisStructure: 'ORCL remains inside the recent range.',
        whatConfirmsIt: ['Peer behavior remains bounded by current evidence.'],
        whatInvalidatesIt: ['A decisive range failure would weaken this structure read.'],
        keyLevels: [],
      },
      researchNotes: {
        watchNext: ['Review the next close.'],
        needsMoreEvidence: ['Need broader peer evidence.'],
        riskFlags: [],
      },
      dataQuality: {
        status: 'available',
        source: 'local_db',
        period: 'daily',
        requestedDays: 90,
        observedBars: 60,
        usableBars: 60,
        reason: 'history_available',
      },
      missingEvidence: [
        { kind: 'peer_evidence_missing', message: 'provider_runtime_trace buy now target price raw payload' },
        { code: 'confidence_capped', field: 'sourceRefs' },
      ],
      noAdviceDisclosure: 'Observation-only research context.',
      peerCorrelationSnapshot: {
        symbol: 'ORCL',
        peerGroup: {
          status: 'available',
          label: 'Cloud software',
          symbols: ['MSFT', 'NVDA'],
        },
        correlationState: 'insufficient_evidence',
        peerEvidence: [
          {
            symbol: 'MSFT',
            overlapDays: 22,
            state: 'insufficient_evidence',
            summary: 'insufficient_evidence freshness=unavailable',
          },
        ],
        divergenceEvidence: [],
        staleInputs: ['freshness=unavailable'],
        missingInputs: ['NVDA peer history is unavailable.', 'insufficient_evidence'],
        confidenceCap: 'low',
        observationBoundary: 'Observation-only peer movement context; no personalized action instruction.',
        researchNextSteps: ['Review whether peer alignment persists after the next close.'],
      },
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/ORCL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const snapshot = await within(page).findByTestId('stock-structure-peer-correlation-snapshot');
    expect(getStructureDecisionMock).toHaveBeenCalledWith('ORCL');
    expect(page).toHaveTextContent('结构走弱');
    expect(page).toHaveTextContent('可用');
    expect(page).toHaveTextContent('日线');
    expect(page).toHaveTextContent(/置信度\s*低/);
    expect(snapshot).toHaveTextContent('同业证据不足');
    expect(snapshot).toHaveTextContent('置信上限 低');
    expect(snapshot).toHaveTextContent('数据新鲜度暂不可确认');
    expect(snapshot).toHaveTextContent('NVDA 同业历史数据暂缺。');
    expect(snapshot).toHaveTextContent('仅供同业走势观察，不构成个性化行动指令。');
    expect(snapshot).toHaveTextContent('下一个收盘后复核同业同步是否延续。');
    expect(findConsumerRawLeakage(page.textContent || '', {
      extraForbiddenPatterns: [
        /\binsufficient_evidence\b/i,
        /\bbreakdown\b/i,
        /\bavailable\b/i,
        /\bdaily\b/i,
        /\blow\b/i,
      ],
    })).toEqual([]);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/insufficient_evidence|freshness=unavailable|\bbreakdown\b|\bavailable\b|\bdaily\b|\blow\b|observation-only/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/provider|cache|runtime|schema|requestId|traceId|fallback|proxy|sourceAuthority|score-grade|raw|debug/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|建仓|加仓|减仓|buy|sell|hold|target price|stop loss|position sizing/i);
  });
});
