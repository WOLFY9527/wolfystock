import type React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useNavigate, useParams } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StockStructureDecisionEntryPage from '../StockStructureDecisionEntryPage';
import StockStructureDecisionPage from '../StockStructureDecisionPage';
import { findConsumerRawLeakage, textContentWithoutObservationBoundary } from '../../test-utils/consumerRawLeakageGuard';
import type { ScannerRunDetail } from '../../types/scanner';

const {
  languageState,
  productSurfaceState,
  verifyTickerExistsMock,
  getQuoteMock,
  getHistoryMock,
  getTechnicalIndicatorsMock,
  getStockEvidenceMock,
  getStructureDecisionMock,
  getResearchPacketMock,
  getOptionsStructureMock,
  getStructureDecisionsBatchMock,
  getScannerRunMock,
} = vi.hoisted(() => ({
  languageState: { value: 'zh' as 'zh' | 'en' },
  productSurfaceState: { isAdmin: false },
  verifyTickerExistsMock: vi.fn(),
  getQuoteMock: vi.fn(),
  getHistoryMock: vi.fn(),
  getTechnicalIndicatorsMock: vi.fn(),
  getStockEvidenceMock: vi.fn(),
  getStructureDecisionMock: vi.fn(),
  getResearchPacketMock: vi.fn(),
  getOptionsStructureMock: vi.fn(),
  getStructureDecisionsBatchMock: vi.fn(),
  getScannerRunMock: vi.fn(),
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

vi.mock('../../api/stocks', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/stocks')>();
  return {
    ...actual,
    stocksApi: {
      ...actual.stocksApi,
      verifyTickerExists: (...args: unknown[]) => verifyTickerExistsMock(...args),
      getQuote: (...args: unknown[]) => getQuoteMock(...args),
      getHistory: (...args: unknown[]) => getHistoryMock(...args),
      getTechnicalIndicators: (...args: unknown[]) => getTechnicalIndicatorsMock(...args),
      getStructureDecision: (...args: unknown[]) => getStructureDecisionMock(...args),
      getResearchPacket: (...args: unknown[]) => getResearchPacketMock(...args),
      getStructureDecisionsBatch: (...args: unknown[]) => getStructureDecisionsBatchMock(...args),
    },
  };
});

vi.mock('../../api/optionsLab', () => ({
  optionsLabApi: {
    getOptionsStructure: (...args: unknown[]) => getOptionsStructureMock(...args),
  },
}));

vi.mock('../../api/stockEvidence', () => ({
  stockEvidenceApi: {
    getStockEvidence: (...args: unknown[]) => getStockEvidenceMock(...args),
  },
}));

vi.mock('../../api/scanner', () => ({
  scannerApi: {
    getRun: (...args: unknown[]) => getScannerRunMock(...args),
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

function StockStructureRouteTransitionHarness() {
  const navigate = useNavigate();

  return (
    <>
      <button type="button" onClick={() => navigate('/zh/stocks/UNAVAILABLE/structure-decision')}>
        Navigate to unavailable stock
      </button>
      <Routes>
        <Route path="/zh/stocks/:stockCode/structure-decision" element={<StockStructureDecisionPage />} />
      </Routes>
    </>
  );
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

const legacyStockPresentationIds = [
  'stock-cockpit-stage-quote',
  'stock-cockpit-stage-history-technical',
  'stock-cockpit-stage-earnings',
  'stock-cockpit-stage-options',
  'stock-cockpit-stage-evidence',
  'stock-cockpit-stage-next-steps',
  'stock-detail-collapsed-evidence-boundary',
  'stock-detail-collapsed-history-technical',
  'stock-detail-collapsed-secondary-details',
] as const;

const baseStructureDecision = () => ({
  schemaVersion: 'stock_structure_decision_api_v1',
  ticker: 'AAPL',
  symbol: 'AAPL',
  structureState: 'breakout',
  confidence: 'medium',
  confidenceCap: {
    value: 60,
    label: 'medium',
    reasons: ['Need broader peer evidence.'],
  },
  confidenceState: {
    status: 'evidence incomplete',
    label: 'medium',
    reasons: ['Need broader peer evidence.'],
    freshnessConstrained: false,
    sourceQualityLimited: false,
    thesisBlocked: false,
  },
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
  keyLevels: [],
  evidenceNotes: ['Volume remained constructive.'],
  riskObservations: ['Closes fall back into the prior range.'],
  evidenceGaps: ['Need broader peer evidence.'],
  historicalOhlcvReadiness: {
    contractVersion: 'historical_ohlcv_readiness_v1',
    symbol: 'AAPL',
    market: 'unknown',
    timeframe: '1d',
    requestedRange: { start: null, end: null },
    lookbackBars: 90,
    requiredBars: 90,
    usableBars: 60,
    missingBars: 30,
    freshnessState: 'unknown',
    adjustmentState: 'not_required',
    benchmarkState: 'not_requested',
    providerState: 'available',
    overallState: 'degraded',
    missingRequirements: ['insufficient_history'],
    consumerSafe: true,
  },
  productReadModel: {
    contractVersion: 'product_read_model_v1',
    surface: 'Structure Decision',
    state: 'partial',
    ready: false,
    classification: {
      observedState: 'breakout',
      displayState: 'breakout',
      strongConclusionAllowed: true,
    },
    confidence: {
      label: 'medium',
      state: 'evidence incomplete',
      strongConclusionAllowed: true,
      reasons: ['Need broader peer evidence.'],
    },
    evidence: {
      missingEvidenceCount: 1,
      readinessState: 'partial',
      dataQualityState: 'available',
    },
    observationOnly: true,
    decisionGrade: false,
  },
  structureComputation: {
    status: 'degraded',
    stateReason: 'insufficient_history',
    message: 'Structure computation is constrained by available history.',
  },
  degradedInputs: [
    {
      section: 'peerEvidence',
      status: 'degraded',
      reason: 'peer_evidence_missing',
    },
  ],
  peerCorrelationSnapshot: {
    symbol: 'AAPL',
    peerGroup: {
      status: 'unavailable',
      label: null,
      symbols: [],
    },
    correlationState: 'insufficient_evidence',
    peerEvidence: [],
    divergenceEvidence: [],
    staleInputs: [],
    missingInputs: ['同业对比信息待确认。'],
    confidenceCap: 'low',
    observationBoundary: 'Observation-only peer movement context; no personalized action instruction.',
    researchNextSteps: ['补齐本地同业分组后再复核同业走势。'],
  },
  consumerIssues: [
    {
      label: 'Evidence gap',
      message: 'Need broader peer evidence.',
      severity: 'warning',
      category: 'evidence',
    },
  ],
  noAdviceDisclosure: 'Observation-only research context.',
  observationOnly: true,
  decisionGrade: false,
  drilldownLinks: [],
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

const historicalScannerRun = (overrides: Partial<ScannerRunDetail> = {}): ScannerRunDetail => ({
  id: 84,
  market: 'us',
  profile: 'us_historical_research_v1',
  profileLabel: 'US Historical Research Scanner v1',
  evaluationMode: 'historical_development',
  evaluationCutoff: '2024-12-31',
  status: 'completed',
  runAt: '2026-09-08T10:30:00Z',
  completedAt: '2026-09-08T10:31:00Z',
  watchlistDate: '2024-12-31',
  triggerMode: 'manual',
  universeName: 'us_historical_research_v1',
  shortlistSize: 1,
  universeSize: 1,
  preselectedSize: 1,
  evaluatedSize: 1,
  universeNotes: [],
  scoringNotes: [],
  universeType: 'default',
  requestedSymbolsCount: 0,
  acceptedSymbolsCount: 0,
  rejectedSymbols: [],
  diagnostics: {},
  notification: { attempted: false, status: 'not_attempted', channels: [] },
  comparisonToPrevious: {
    available: false,
    newCount: 0,
    retainedCount: 0,
    droppedCount: 0,
    newSymbols: [],
    retainedSymbols: [],
    droppedSymbols: [],
  },
  reviewSummary: {
    available: false,
    reviewWindowDays: 5,
    reviewStatus: 'pending',
    candidateCount: 1,
    reviewedCount: 0,
    pendingCount: 1,
    strongCount: 0,
    mixedCount: 0,
    weakCount: 0,
  },
  shortlist: [{
    symbol: 'AAPL',
    name: 'Apple',
    rank: 1,
    score: 74.3,
    reasons: [],
    keyMetrics: [],
    featureSignals: [],
    riskNotes: [],
    watchContext: [],
    boards: [],
    appearedInRecentRuns: 1,
    aiInterpretation: { available: false, status: 'unavailable' },
    realizedOutcome: {
      reviewStatus: 'pending',
      outcomeLabel: 'Pending',
      thesisMatch: 'unknown',
      reviewWindowDays: 5,
    },
    diagnostics: {},
    historicalOhlcvReadiness: {
      asOf: '2024-12-31',
      requiredBars: 180,
      usableBars: 180,
      missingBars: 0,
    },
  }],
  ...overrides,
});

const technicalIndicatorsAvailable = () => ({
  contractVersion: 'stock_technical_indicators_v1',
  symbol: 'AAPL',
  status: 'available',
  timeframe: 'daily',
  asOf: '2026-05-28T09:30:00Z',
  freshness: 'fresh',
  sourceLabel: '本地价格历史边界',
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

const stockEvidenceResponse = () => ({
  symbols: ['AAPL'],
  items: [
    {
      symbol: 'AAPL',
      market: 'US',
      productReadModel: {
        state: 'partial',
        ready: false,
        freshness: { state: 'stale', asOf: '2026-05-28T09:30:00Z' },
      },
      quote: { state: 'available' },
      technical: { state: 'available' },
      fundamental: { state: 'partial' },
      news: null,
      secFilingEvidence: null,
      stockEvidencePacket: {
        fundamentalsSummary: {
          marketCap: 3300000000000,
          peTtm: 31.2,
          period: '2026-Q1',
          freshness: 'stale',
          missingFields: ['revenueTtm', 'netIncomeTtm'],
          notInvestmentAdvice: true,
          observationOnly: true,
          scoreContributionAllowed: false,
          sourceAuthorityAllowed: false,
        },
      },
      symbolEvidenceReadiness: {
        symbolEvidenceReadiness: true,
        symbol: 'AAPL',
        readinessTier: 'partial',
        evidenceUsed: ['quote', 'technical'],
        evidenceMissing: ['fundamentals', 'events'],
        staleInputs: ['fundamentals'],
        conflictingEvidence: [],
        dataQualityNotes: ['Fundamental packet is partial.'],
        suggestedResearchPath: ['Refresh evidence packet.'],
        observationOnly: true,
        noAdviceDisclosure: 'Research observation only.',
      },
    },
  ],
  meta: { generatedAt: '2026-05-28T09:31:00Z', source: 'stock_evidence' },
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
    verifyTickerExistsMock.mockImplementation((stockCode: string) => Promise.resolve({
      stockCode,
      normalizedSymbol: stockCode,
      market: 'us',
      status: 'valid',
      valid: true,
      exists: true,
      stockName: null,
      message: 'Symbol verified.',
    }));
    getResearchPacketMock.mockImplementation((symbol: string) => Promise.resolve({
      ...partialResearchPacket(),
      symbol,
    }));
    getQuoteMock.mockResolvedValue({
      ...baseQuote(),
    });
    getHistoryMock.mockImplementation((symbol: string) => Promise.resolve(baseHistory(symbol, 60)));
    getTechnicalIndicatorsMock.mockResolvedValue(technicalIndicatorsAvailable());
    getStockEvidenceMock.mockResolvedValue(stockEvidenceResponse());
    getOptionsStructureMock.mockResolvedValue(optionsStructureNotAvailable());
  });

  it('re-reads Scanner historical evidence while current quote and history remain independently unavailable across refresh', async () => {
    languageState.value = 'en';
    getScannerRunMock.mockResolvedValue(historicalScannerRun());
    getQuoteMock.mockRejectedValue(new Error('current quote unavailable'));
    getHistoryMock.mockRejectedValue(new Error('current history unavailable'));
    getResearchPacketMock.mockResolvedValue({
      ...partialResearchPacket(),
      symbol: 'AAPL',
      quote: { state: 'unavailable', price: null, changePercent: null, asOf: null },
      history: { state: 'unavailable', bars: 0, period: 'daily', asOf: null },
    });
    getStructureDecisionMock.mockResolvedValue({
      ...baseStructureDecision(),
      structureState: 'low_confidence',
      confidence: 'low',
      dataQuality: {
        status: 'unavailable',
        source: null,
        period: 'daily',
        requestedDays: 90,
        observedBars: 0,
        usableBars: 0,
        reason: 'history_unavailable',
      },
      historicalOhlcvReadiness: {
        ...baseStructureDecision().historicalOhlcvReadiness,
        requiredBars: 90,
        usableBars: 0,
        missingBars: 90,
        providerState: 'unavailable',
        overallState: 'blocked',
      },
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/en/stocks/AAPL/structure-decision?symbol=AAPL&market=US&source=scanner&scannerRunId=84',
      '/en/stocks/:stockCode/structure-decision',
    );

    const scannerPanel = await screen.findByTestId('scanner-historical-evidence-panel');
    expect(getScannerRunMock).toHaveBeenCalledWith(84);
    expect(scannerPanel).toHaveTextContent('Scanner historical evidence');
    expect(scannerPanel).toHaveTextContent('2024-12-31');
    expect(scannerPanel).toHaveTextContent('74.3');
    expect(scannerPanel).toHaveTextContent(/Usable historical bars\s*180/);
    expect(scannerPanel).toHaveTextContent(/Missing historical bars\s*0/);
    expect(scannerPanel).toHaveTextContent('Development replay');
    expect(scannerPanel).toHaveTextContent('Not current data');
    expect(screen.getByTestId('scanner-historical-current-separation')).toHaveTextContent(/never filled from this replay/i);

    const currentHistoryPanel = screen.getByTestId('stock-history-readiness-panel');
    expect(currentHistoryPanel).toHaveTextContent(/Available bars\s*0/);
    expect(currentHistoryPanel).toHaveTextContent(/Required bars\s*90/);
    expect(currentHistoryPanel).toHaveTextContent(/Missing bars\s*90/);
    expect(screen.getByTestId('stock-history-empty-chart-state')).toHaveTextContent('Chart unavailable');
    expect(screen.getByTestId('stock-quote-boundary-panel')).toHaveTextContent(/unavailable/i);

    fireEvent.click(screen.getByRole('button', { name: 'Refresh stock research' }));
    await waitFor(() => expect(getScannerRunMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByTestId('scanner-historical-evidence-panel')).toHaveTextContent(/Usable historical bars\s*180/);
  });

  it('renders the Scanner historical evidence boundary in Chinese without raw lineage fields', async () => {
    languageState.value = 'zh';
    getScannerRunMock.mockResolvedValue(historicalScannerRun());
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision?symbol=AAPL&market=US&source=scanner&scannerRunId=84',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const scannerPanel = await screen.findByTestId('scanner-historical-evidence-panel');
    expect(scannerPanel).toHaveTextContent('Scanner 历史证据');
    expect(scannerPanel).toHaveTextContent('有历史证据的候选');
    expect(scannerPanel).toHaveTextContent(/可用历史 K 线\s*180/);
    expect(scannerPanel).toHaveTextContent('不是当前数据');
    expect(scannerPanel).not.toHaveTextContent(/historical_development|us_historical_research_v1|source_summary|provider/i);
  });

  it.each([
    ['returned run id', historicalScannerRun({ id: 85 })],
    ['run market', historicalScannerRun({ market: 'hk' })],
    ['candidate symbol', historicalScannerRun({ shortlist: [{ ...historicalScannerRun().shortlist[0], symbol: 'MSFT' }] })],
    ['evaluation mode', historicalScannerRun({ evaluationMode: 'current' })],
    ['cutoff', historicalScannerRun({ evaluationCutoff: '2024-02-30' })],
  ])('fails closed when Scanner lineage mismatches %s', async (_label, run) => {
    getScannerRunMock.mockResolvedValue(run);
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision?symbol=AAPL&market=US&source=scanner&scannerRunId=84',
      '/zh/stocks/:stockCode/structure-decision',
    );

    await screen.findByTestId('stock-structure-decision-page');
    await waitFor(() => expect(getScannerRunMock).toHaveBeenCalledWith(84));
    expect(screen.queryByTestId('scanner-historical-evidence-panel')).not.toBeInTheDocument();
  });

  it('fails closed for malformed or inaccessible Scanner lineage without blocking current Research', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    const malformed = renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision?symbol=AAPL&market=US&source=scanner&scannerRunId=not-a-run',
      '/zh/stocks/:stockCode/structure-decision',
    );
    await screen.findByTestId('stock-structure-decision-page');
    expect(getScannerRunMock).not.toHaveBeenCalled();
    expect(screen.queryByTestId('scanner-historical-evidence-panel')).not.toBeInTheDocument();
    malformed.unmount();

    getScannerRunMock.mockRejectedValue(new Error('not found'));
    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision?symbol=AAPL&market=US&source=scanner&scannerRunId=84',
      '/zh/stocks/:stockCode/structure-decision',
    );
    await waitFor(() => expect(getScannerRunMock).toHaveBeenCalledWith(84));
    expect(await screen.findByTestId('stock-structure-decision-page')).toBeInTheDocument();
    expect(screen.queryByTestId('scanner-historical-evidence-panel')).not.toBeInTheDocument();
  });

  it('rejects a route-market mismatch before exposing authorized Scanner evidence', async () => {
    getScannerRunMock.mockResolvedValue(historicalScannerRun());
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision?symbol=AAPL&market=HK&source=scanner&scannerRunId=84',
      '/zh/stocks/:stockCode/structure-decision',
    );

    await waitFor(() => expect(getScannerRunMock).toHaveBeenCalledWith(84));
    expect(await screen.findByTestId('stock-structure-decision-page')).toBeInTheDocument();
    expect(screen.queryByTestId('scanner-historical-evidence-panel')).not.toBeInTheDocument();
  });

  it('uses the API canonical HK symbol for the route, display, and every single-symbol request', async () => {
    verifyTickerExistsMock.mockResolvedValue({
      stockCode: 'HK00700',
      normalizedSymbol: 'HK00700',
      market: 'hk',
      status: 'unknown',
      valid: false,
      exists: false,
      stockName: null,
      message: 'Symbol format is supported, but verification is not confirmed yet.',
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/0700.HK/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    await waitFor(() => expect(getStructureDecisionMock).toHaveBeenCalledWith('HK00700'));
    expect(verifyTickerExistsMock).toHaveBeenNthCalledWith(1, '0700.HK');
    expect(verifyTickerExistsMock).toHaveBeenNthCalledWith(2, 'HK00700');
    expect(getQuoteMock).toHaveBeenCalledWith('HK00700');
    expect(getResearchPacketMock).toHaveBeenCalledWith('HK00700');
    expect(getHistoryMock).toHaveBeenCalledWith('HK00700', { period: 'daily', days: 180 });
    expect(getTechnicalIndicatorsMock).toHaveBeenCalledWith('HK00700');
    expect(getStockEvidenceMock).toHaveBeenCalledWith('HK00700');
    expect(getOptionsStructureMock).toHaveBeenCalledWith('HK00700');
    expect(screen.getByTestId('stock-structure-decision-page')).toHaveTextContent('HK00700 结构工作区');
  });

  it('resolves comparison aliases before canonical deduplication and batch loading', async () => {
    verifyTickerExistsMock.mockImplementation((stockCode: string) => Promise.resolve({
      stockCode,
      normalizedSymbol: stockCode === '0700.HK' || stockCode === 'HK00700' ? 'HK00700' : 'AAPL',
      market: stockCode === '0700.HK' || stockCode === 'HK00700' ? 'hk' : 'us',
      status: 'valid',
      valid: true,
      exists: true,
      stockName: null,
      message: 'Symbol verified.',
    }));
    getStructureDecisionsBatchMock.mockResolvedValue({
      items: [baseStructureDecision()],
      symbolCompareEvidencePacket: null,
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/0700.HK,HK00700,AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    await waitFor(() => expect(getStructureDecisionsBatchMock).toHaveBeenCalledWith({
      stockCodes: ['HK00700', 'AAPL'],
      benchmark: undefined,
      maxItems: undefined,
    }));
    expect(getResearchPacketMock).toHaveBeenCalledWith('HK00700');
    expect(getQuoteMock).not.toHaveBeenCalled();
    expect(getStructureDecisionMock).not.toHaveBeenCalled();
    expect(screen.getByTestId('stock-structure-decision-page')).toHaveTextContent('HK00700 / AAPL 结构工作区');
  });

  it('stops unresolved symbols before any downstream research request', async () => {
    verifyTickerExistsMock.mockResolvedValue({
      stockCode: 'BAD',
      normalizedSymbol: null,
      market: null,
      status: 'invalid_format',
      valid: false,
      exists: false,
      stockName: null,
      message: 'invalid',
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/BAD/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    await screen.findByTestId('stock-structure-symbol-not-found-state');
    expect(getQuoteMock).not.toHaveBeenCalled();
    expect(getResearchPacketMock).not.toHaveBeenCalled();
    expect(getStructureDecisionMock).not.toHaveBeenCalled();
    expect(getHistoryMock).not.toHaveBeenCalled();
    expect(getTechnicalIndicatorsMock).not.toHaveBeenCalled();
    expect(getStockEvidenceMock).not.toHaveBeenCalled();
    expect(getOptionsStructureMock).not.toHaveBeenCalled();
  });

  it('clears the prior canonical identity when a new route cannot be verified', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());
    verifyTickerExistsMock.mockImplementation((stockCode: string) => Promise.resolve(
      stockCode === 'AAPL'
        ? {
          stockCode,
          normalizedSymbol: 'AAPL',
          market: 'us',
          status: 'valid',
          valid: true,
          exists: true,
          stockName: null,
          message: 'Symbol verified.',
        }
        : {
          stockCode,
          normalizedSymbol: null,
          market: null,
          status: 'unavailable',
          valid: false,
          exists: false,
          stockName: null,
          message: 'Symbol verification is unavailable.',
        },
    ));

    render(
      <MemoryRouter initialEntries={['/zh/stocks/AAPL/structure-decision']}>
        <StockStructureRouteTransitionHarness />
      </MemoryRouter>,
    );

    await screen.findByRole('heading', { name: 'AAPL 研究工作区' });
    fireEvent.click(screen.getByRole('button', { name: 'Navigate to unavailable stock' }));

    await screen.findByText('标的身份暂不可用');
    const page = screen.getByTestId('stock-structure-decision-page');
    expect(page).not.toHaveTextContent('AAPL 研究工作区');
    expect(page).not.toHaveTextContent('AAPL 结构工作区');
    expect(getStructureDecisionMock).toHaveBeenCalledTimes(1);
  });

  it('renders direct symbol input on the stock-structure entry empty state while preserving queue links', () => {
    renderStockStructureEntryRoute();

    const page = screen.getByTestId('stock-structure-entry-page');
    expect(page).toHaveTextContent('直接输入标的');
    expect(screen.getByLabelText('股票代码')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '打开研究' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(screen.getByRole('link', { name: '观察列表上下文' })).toHaveAttribute('href', '/zh/watchlist');
    expect(screen.getByLabelText('股票代码')).toHaveClass('focus-visible:ring-2');
    expect(screen.getByRole('link', { name: '研究雷达' })).toHaveClass('focus-visible:ring-2');
    expect(screen.getByRole('link', { name: '观察列表上下文' })).toHaveClass('focus-visible:ring-2');
    expect(page).toHaveTextContent('直接输入已知股票代码，或从市场总览、研究雷达、观察列表与二级验证工具继续进入。');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it('shows a validation error for empty direct symbol submit', () => {
    renderStockStructureEntryRoute();

    fireEvent.click(screen.getByRole('button', { name: '打开研究' }));

    expect(screen.getByRole('alert')).toHaveTextContent('请输入股票代码。');
    expect(screen.queryByTestId('stock-structure-detail-route')).not.toBeInTheDocument();
  });

  it('shows a consumer-safe validation error for malformed direct symbols', async () => {
    verifyTickerExistsMock.mockResolvedValueOnce({
      stockCode: 'AAPL<script>',
      normalizedSymbol: null,
      market: null,
      status: 'invalid_format',
      valid: false,
      exists: false,
      stockName: null,
      message: 'invalid',
    });
    renderStockStructureEntryRoute();

    fireEvent.change(screen.getByLabelText('股票代码'), { target: { value: 'AAPL<script>' } });
    fireEvent.click(screen.getByRole('button', { name: '打开研究' }));

    const alert = await screen.findByRole('alert');
    expect(verifyTickerExistsMock).toHaveBeenCalledWith('AAPL<script>');
    expect(alert).toHaveTextContent('股票代码格式不正确');
    expect(alert.textContent || '').not.toMatch(/provider|requestId|traceId|cache|raw|debug|apiKey|token/i);
    expect(screen.queryByTestId('stock-structure-detail-route')).not.toBeInTheDocument();
  });

  it('navigates a valid direct symbol into the existing structure detail route', async () => {
    verifyTickerExistsMock.mockResolvedValueOnce({
      stockCode: 'AAPL',
      normalizedSymbol: 'AAPL',
      market: 'us',
      status: 'valid',
      valid: true,
      exists: true,
      stockName: 'Apple',
      message: 'Symbol verified.',
    });
    renderStockStructureEntryRoute();

    fireEvent.change(screen.getByLabelText('股票代码'), { target: { value: ' aapl ' } });
    fireEvent.click(screen.getByRole('button', { name: '打开研究' }));

    expect(verifyTickerExistsMock).toHaveBeenCalledWith('aapl');
    expect(await screen.findByTestId('stock-structure-detail-route')).toHaveTextContent('AAPL');
  });

  it('keeps carried symbol state visible and deep-links common market formats', async () => {
    verifyTickerExistsMock.mockResolvedValueOnce({
      stockCode: 'HK00700',
      normalizedSymbol: 'HK00700',
      market: 'hk',
      status: 'unknown',
      valid: false,
      exists: false,
      stockName: null,
      message: 'Symbol format is supported, but verification is not confirmed yet.',
    });
    renderStockStructureEntryRoute('/zh/stock-structure?symbols=0700.HK');

    expect(screen.getByLabelText('股票代码')).toHaveValue('0700.HK');

    fireEvent.click(screen.getByRole('button', { name: '打开研究' }));

    expect(verifyTickerExistsMock).toHaveBeenCalledWith('0700.HK');
    expect(await screen.findByTestId('stock-structure-detail-route')).toHaveTextContent('HK00700');
  });

  it('requests and renders the symbol research packet as a professional evidence stack', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const productFlow = within(page).getByTestId('stock-workspace-product-flow');
    expect(productFlow).toHaveAttribute(
      'data-product-flow',
      'identity-data-state-current-conclusion-price-evidence-path-analyst-memo-factor-evidence-risk-triggers-peer-theme-context-evidence-ledger-data-limitations',
    );
    expect(within(page).queryByTestId('observation-only-boundary')).not.toBeInTheDocument();
    for (const legacyId of legacyStockPresentationIds) {
      expect(within(page).queryByTestId(legacyId)).not.toBeInTheDocument();
    }
    const knownFacts = await within(page).findByTestId('stock-known-facts-panel');
    const identityWorkspace = await within(page).findByTestId('stock-identity-data-state-workspace');
    const evidenceWorkspace = await within(page).findByTestId('stock-evidence-workspace');
    const evidencePackage = await within(page).findByTestId('stock-evidence-package-workspace');
    const analystMemoWorkspace = await within(page).findByTestId('stock-analyst-memo-workspace');
    const structureWorkspace = await within(page).findByTestId('stock-structure-interpretation-workspace');
    const historyWorkspace = await within(page).findByTestId('stock-history-technical-workspace');
    const catalystOptionsWorkspace = await within(page).findByTestId('stock-catalyst-options-workspace');
    const factorEvidenceWorkspace = await within(page).findByTestId('stock-factor-evidence-workspace');
    const riskTriggersWorkspace = await within(page).findByTestId('stock-risk-triggers-workspace');
    const peerThemeWorkspace = await within(page).findByTestId('stock-peer-theme-context-workspace');
    const nextChecksWorkspace = await within(page).findByTestId('stock-next-research-checks');
    const panel = await within(page).findByTestId('stock-research-packet-panel');
    const quotePanel = await within(page).findByTestId('stock-quote-boundary-panel');
    const historyPanel = await within(page).findByTestId('stock-history-readiness-panel');
    const catalystPanel = await within(page).findByTestId('stock-earnings-catalyst-readiness-panel');
    const optionsSurface = await within(page).findByTestId('stock-options-structure-surface');
    const nextStepsPanel = await within(page).findByTestId('stock-missing-data-next-steps-panel');
    const workflowSection = await within(page).findByTestId('stock-workflow-continuity');
    const workflow = await within(page).findByTestId('stock-research-workspace-flow');

    expect(getQuoteMock).toHaveBeenCalledWith('AAPL');
    expect(getHistoryMock).toHaveBeenCalledWith('AAPL', { period: 'daily', days: 180 });
    expect(getResearchPacketMock).toHaveBeenCalledWith('AAPL');
    expect(getStockEvidenceMock).toHaveBeenCalledWith('AAPL');
    expect(workflow).toHaveTextContent('Beta 研究旅程');
    expect(workflow).toHaveTextContent('AAPL');
    expect(within(workflow).getByTestId('research-workspace-link-stock-structure')).toHaveAttribute('href', expect.stringContaining('/zh/stocks/AAPL/structure-decision?'));
    expect(within(workflow).getByTestId('research-workspace-link-watchlist')).toHaveAttribute('href', expect.stringContaining('/zh/watchlist?'));
    expect(within(workflow).getByTestId('research-workspace-link-backtest')).toHaveAttribute('href', expect.stringContaining('/zh/backtest?'));
    expect(workflow).toHaveTextContent('只有需要持续观察时，再加入观察列表。');
    expect(workflow).not.toHaveTextContent(/provider|cache|runtime|debug|scannerRunId|watchlistItemId|立即买入|立即卖出|下单|保证收益/i);
    expect(identityWorkspace).toHaveTextContent('标的身份与数据状态');
    expect(knownFacts).toHaveTextContent('当前标的与有边界的数据状态');
    expect(knownFacts).toHaveTextContent('基础研究包');
    expect(evidencePackage).toHaveTextContent('可复制的研究证据');
    expect(workflowSection).toHaveTextContent('研究流转');
    expect(historyWorkspace).toHaveTextContent('市场路径与技术证据');
    expect(catalystOptionsWorkspace).toHaveTextContent('支持证据就绪度');
    expect(optionsSurface).toHaveTextContent('专业结构指标');
    expect(analystMemoWorkspace).toHaveTextContent('研究叙事与证据栈');
    expect(factorEvidenceWorkspace).toHaveTextContent('按含义组织的因子证据');
    expect(riskTriggersWorkspace).toHaveTextContent('已观察风险与失效条件');
    expect(peerThemeWorkspace).toHaveTextContent('作为支持证据，而非零散组件');
    expect(nextChecksWorkspace).toHaveTextContent('明确限制与下一步检查');
    expect(quotePanel).toHaveTextContent('原子报价观察');
    expect(quotePanel).toHaveTextContent('报价可用');
    expect(quotePanel).toHaveTextContent('来源: Alpaca');
    expect(quotePanel).toHaveTextContent('新鲜度: 新鲜');
    expect(quotePanel).toHaveTextContent('市场截至');
    expect(quotePanel).toHaveTextContent('缓存: 否');
    expect(quotePanel).toHaveTextContent('替代路径: 否');
    expect(quotePanel).toHaveTextContent('05/28');
    expect(quotePanel).toHaveTextContent('17:30');
    const summary = within(page).getByTestId('stock-consumer-research-summary');
    expect(summary).toHaveAttribute('data-first-screen-priority', 'conclusion-first');
    expect(summary).toHaveAttribute('data-research-sequence', 'identity-price-path-memo-metrics-limitation-next');
    expect(summary).toHaveTextContent('AAPL');
    expect(summary).toHaveTextContent('Apple');
    expect(summary).toHaveTextContent('US');
    expect(summary).toHaveTextContent('$214.6');
    expect(summary).toHaveTextContent('+1.11%');
    expect(summary).toHaveTextContent('市场截至 05/28 17:30');
    const quoteObservation = within(summary).getByTestId('stock-quote-observation-strip');
    const historyObservation = within(summary).getByTestId('stock-history-observation-strip');
    expect(quoteObservation).toHaveTextContent('来源: Alpaca');
    expect(quoteObservation).toHaveTextContent('新鲜度: 新鲜');
    expect(quoteObservation).toHaveTextContent('缓存: 否');
    expect(quoteObservation).toHaveTextContent('替代路径: 否');
    expect(historyObservation).toHaveTextContent('来源: 本地历史数据');
    expect(historyObservation).toHaveTextContent('返回区间');
    expect(historyObservation).toHaveTextContent('可用 60');
    expect(historyObservation).toHaveTextContent('所需 90');
    expect(historyObservation).toHaveTextContent('缺口 30');
    expect(historyObservation).toHaveTextContent('缓存: 否');
    expect(historyObservation).toHaveTextContent('替代路径: 否');
    expect(within(page).getByTestId('stock-deep-evidence-disclosure')).not.toHaveAttribute('open');
    expect(summary).toHaveTextContent('突破观察');
    expect(summary).toHaveTextContent('置信度：中');
    expect(summary).toHaveTextContent('置信度为中：报价、历史与结构证据可用，但基本面、事件或同业证据仍限制结论强度。');
    expect(summary).toHaveTextContent('AAPL 当前呈现突破观察，报价新鲜，历史 K 线可用于查看走势。');
    const conclusion = within(summary).getByTestId('stock-current-research-conclusion');
    expect(conclusion).toHaveTextContent('当前研究结论');
    expect(conclusion).toHaveTextContent('AAPL 当前为突破观察；置信度为中。');
    expect(conclusion).toHaveTextContent('支持证据');
    expect(conclusion).toHaveTextContent('主要风险 / 限制');
    expect(conclusion).toHaveTextContent('下一步研究动作');
    expect(summary).toHaveTextContent('研究备忘');
    expect(summary).toHaveTextContent('当前观察');
    expect(summary).toHaveTextContent('为什么');
    expect(summary).toHaveTextContent('数据是否足够可靠');
    expect(summary).toHaveTextContent('下一步检查什么');
    expect(summary).toHaveTextContent('限制 / 证据缺口');
    expect(summary).toHaveTextContent('研究观察，不构成投资建议。');
    expect(summary).toHaveTextContent('前往研究雷达继续核对');
    expect(summary).toHaveTextContent('打开回测');
    expect(summary).toHaveTextContent('复制证据');
    const firstViewportPanel = within(page).getByTestId('stock-first-viewport-summary-panel');
    expect(firstViewportPanel).toHaveTextContent('置信度：中');
    expect(firstViewportPanel).toHaveTextContent('历史数据可用');
    const trustRow = within(page).getByTestId('stock-data-trust-row');
    expect(trustRow).toHaveTextContent('报价');
    expect(trustRow).toHaveTextContent('新鲜');
    expect(trustRow).toHaveTextContent('历史');
    expect(trustRow).toHaveTextContent('60 / 90 根');
    expect(trustRow).toHaveTextContent('技术指标');
    expect(trustRow).toHaveTextContent('指标可用');
    expect(trustRow).toHaveTextContent('证据');
    expect(trustRow).toHaveTextContent('可用');
    const ledger = within(page).getByTestId('stock-evidence-ledger');
    expect(ledger).toHaveTextContent('证据、新鲜度与限制');
    expect(ledger).toHaveTextContent('报价');
    expect(ledger).toHaveTextContent('价格历史');
    expect(ledger).toHaveTextContent('技术指标');
    expect(ledger).toHaveTextContent('结构观察');
    expect(ledger).toHaveTextContent('研究包');
    expect(ledger).toHaveTextContent('证据就绪度');
    expect(ledger).toHaveTextContent('部分可用');
    expect(ledger).toHaveTextContent('缺失字段');
    const ledgerRows = within(ledger).getAllByRole('row').slice(1);
    expect(ledgerRows).toHaveLength(8);
    expect(ledgerRows.map((row) => within(row).getByRole('rowheader').textContent)).toEqual([
      '报价',
      '价格历史',
      '技术指标',
      '结构观察',
      '研究包',
      '证据就绪度',
      '基本面',
      '事件 / 催化',
    ]);
    const ledgerScroll = within(ledger).getByTestId('stock-evidence-ledger-scroll');
    expect(ledgerScroll).toHaveClass('overflow-x-auto', 'overscroll-x-contain');
    expect(ledgerScroll).toHaveAttribute('role', 'region');
    expect(ledgerScroll).toHaveAttribute('tabIndex', '0');
    expect(ledgerScroll).toHaveAttribute('aria-label', '可横向滚动的个股证据账本');
    expect(ledgerScroll).toHaveAttribute('aria-describedby', 'stock-evidence-ledger-scroll-help');
    expect(document.getElementById('stock-evidence-ledger-scroll-help')).toHaveTextContent('此账本可横向滚动，以查看全部证据列。');
    expect(ledgerScroll.querySelector('table')).toHaveClass('stock-evidence-ledger__table', 'product-table');
    expect(within(ledger).getByRole('columnheader', { name: '来源边界' })).toBeInTheDocument();
    const stockCoreChart = within(page).getByTestId('stock-history-core-chart');
    expect(within(page).getByTestId('stock-price-history-visual-block')).toContainElement(stockCoreChart);
    // T448 first-screen sequence: identity → conclusion → price path (not equal-weight card wall).
    const identityHeader = within(summary).getByTestId('stock-research-identity-header');
    const pricePath = within(summary).getByTestId('stock-price-history-visual-block');
    expect(identityHeader.compareDocumentPosition(conclusion) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(conclusion.compareDocumentPosition(pricePath) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(stockCoreChart.compareDocumentPosition(knownFacts) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(knownFacts.compareDocumentPosition(historyWorkspace) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(historyWorkspace.compareDocumentPosition(analystMemoWorkspace) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(analystMemoWorkspace.compareDocumentPosition(structureWorkspace) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(structureWorkspace.compareDocumentPosition(evidenceWorkspace) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(evidenceWorkspace.compareDocumentPosition(workflowSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
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
    expect(panel).toHaveTextContent('研究资料可用');
    expect(panel).toHaveTextContent('下一证据缺口');
    expect(panel).toHaveTextContent('基本面待补');
    expect(panel).toHaveTextContent('新闻线索待补');
    expect(panel).toHaveTextContent('市场线索待补');
    const factorPanel = within(page).getByTestId('stock-factor-evidence-panel');
    expect(factorPanel).toHaveTextContent('因子证据');
    expect(factorPanel).toHaveTextContent('按相关性排列的组件证据');
    expect(factorPanel).toHaveTextContent('可用、部分、延迟、不可用');
    const riskPanel = within(page).getByTestId('stock-risk-triggers-panel');
    expect(riskPanel).toHaveTextContent('已观察风险证据');
    expect(riskPanel).toHaveTextContent('失效条件');
    expect(riskPanel).toHaveTextContent('未知 / 待补证据');
    expect(riskPanel).toHaveTextContent('Closes fall back into the prior range.');
    expect(riskPanel).toHaveTextContent('需要补充同业对照证据。');
    expect(catalystPanel).toHaveAttribute('data-module-density', 'compact');
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
    // G025: peer/theme empty state is a bounded empty line (not a giant empty panel).
    const peerEmpty = within(page).queryByTestId('stock-peer-theme-bounded-empty');
    if (peerEmpty) {
      expect(peerEmpty).toHaveTextContent('同业或主题证据暂不可用');
      expect(peerEmpty).toHaveAttribute('data-module-density', 'bounded-empty');
    } else {
      expect(within(page).getByTestId('stock-structure-peer-correlation-snapshot')).toBeInTheDocument();
    }
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

  it('keeps current stock research visible and announced during a background refresh', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    getStructureDecisionMock.mockImplementationOnce(() => new Promise(() => undefined));
    fireEvent.click(screen.getByRole('button', { name: '刷新个股研究' }));

    await waitFor(() => expect(page).toHaveAttribute('aria-busy', 'true'));
    expect(within(page).getByRole('status')).toHaveTextContent('正在刷新个股研究。当前研究内容保持可见。');
    expect(within(page).getByTestId('stock-workspace-product-flow')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '正在刷新个股研究' })).toBeDisabled();
  });

  it('keeps stock evidence-package headings semantic without changing compact typography', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.getByRole('heading', { level: 1, name: 'AAPL 研究工作区' })).toBeInTheDocument();

    expect(within(page).queryByTestId('stock-detail-collapsed-evidence-boundary')).not.toBeInTheDocument();
    const registry = await within(page).findByTestId('single-stock-evidence-pack-registry');
    expect(within(page).getByTestId('stock-evidence-package-workspace')).toContainElement(registry);
    const evidencePackHeading = within(registry).getByRole('heading', { level: 3, name: '个股证据包' });
    expect(evidencePackHeading.tagName).toBe('H3');
    expect(evidencePackHeading).toHaveClass('text-sm', 'font-semibold', 'text-[color:var(--wolfy-text-primary)]');
    expect(registry.querySelector('h4')).toBeNull();
    expect(within(registry).getByTestId('single-stock-evidence-pack-copy')).toBeEnabled();
    expect(within(registry).getByTestId('single-stock-evidence-pack-download')).toBeEnabled();
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
    expect(page).toHaveTextContent('ORCL 研究工作区');
    expect(historyPanel).toHaveTextContent('ORCL 历史数据就绪度');
    expect(historyPanel).toHaveTextContent('可用 K 线');
    expect(historyPanel).toHaveTextContent('120');
    expect(historyPanel).toHaveTextContent('缺口 K 线');
    expect(historyPanel).toHaveTextContent('0');
    expect(historyPanel).toHaveTextContent('结构计算已返回');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/\bAAPL\b/);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it('uses productReadModel to withhold strong structure conclusions and surface stale freshness', async () => {
    getResearchPacketMock.mockResolvedValue({
      ...completeResearchPacket(),
      productReadModel: {
        contractVersion: 'product_read_model_v1',
        surface: 'Stock Research',
        state: 'stale',
        ready: false,
        blockingChildren: ['historical_coverage'],
        freshness: { state: 'stale', asOf: '2026-05-20' },
        provenance: { sourceClass: 'historical_market_data', asOf: '2026-05-20', freshness: 'stale', quality: 'partial' },
      },
    });
    getStructureDecisionMock.mockResolvedValue({
      ...baseStructureDecision(),
      confidence: 'high',
      missingEvidence: [{ kind: 'historical_coverage', message: 'Historical coverage is stale.' }],
      productReadModel: {
        contractVersion: 'product_read_model_v1',
        surface: 'Structure Decision',
        state: 'insufficient',
        ready: false,
        classification: {
          observedState: 'breakout',
          displayState: 'withheld',
          strongConclusionAllowed: false,
        },
        confidence: {
          label: 'low',
          state: 'evidence incomplete',
          strongConclusionAllowed: false,
          reasons: ['critical_evidence_missing'],
        },
        evidence: {
          missingEvidenceCount: 1,
          readinessState: 'stale',
          dataQualityState: 'partial',
        },
        blockingChildren: ['historical_coverage'],
        freshness: { state: 'stale', asOf: '2026-05-20' },
        provenance: { sourceClass: 'historical_market_data', asOf: '2026-05-20', freshness: 'stale', quality: 'partial' },
      },
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const summary = within(page).getByTestId('stock-consumer-research-summary');
    const firstViewportPanel = within(page).getByTestId('stock-first-viewport-summary-panel');
    const boundaryDisclosure = within(summary).getByTestId('stock-research-boundary-disclosure');
    const productReadModel = await within(boundaryDisclosure).findByTestId('stock-structure-product-read-model');
    const freshness = within(boundaryDisclosure).getByTestId('stock-product-read-model-freshness');

    expect(summary).toHaveTextContent('暂不形成强结论');
    expect(summary).toHaveTextContent('置信度：低');
    expect(summary).not.toHaveTextContent('突破观察');
    expect(productReadModel).toHaveAttribute('data-product-read-state', 'insufficient');
    expect(productReadModel).toHaveAttribute('data-product-read-ready', 'false');
    expect(productReadModel).toHaveTextContent('关键证据阻塞：历史覆盖证据');
    expect(productReadModel).toHaveTextContent('历史行情证据');
    expect(freshness).toHaveTextContent('新鲜度：已过期');
    expect(freshness).toHaveTextContent('截至 2026-05-20');
    expect(boundaryDisclosure).not.toHaveAttribute('open');
    expect(textContentWithoutObservationBoundary(firstViewportPanel)).not.toMatch(/\bbreakout\b|provider|trace|raw|sourceAuthority|sourceConfidence/i);
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
        { kind: 'daily_ohlcv', message: 'OHLCV 证据缺失时，不形成结构结论。' },
      ],
      productReadModel: {
        ...baseStructureDecision().productReadModel,
        state: 'no_evidence',
        ready: false,
        classification: {
          observedState: 'low_confidence',
          displayState: 'withheld',
          strongConclusionAllowed: false,
        },
        confidence: {
          label: 'low',
          state: 'evidence incomplete',
          strongConclusionAllowed: false,
          reasons: ['Need local historical bars.'],
        },
      },
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
    expect(page).toHaveTextContent('600519 研究工作区');
    expect(historyPanel).toHaveTextContent('600519 历史数据就绪度');
    expect(historyPanel).toHaveTextContent('历史数据不可用');
    expect(historyPanel).toHaveTextContent('结构样本不足');
    expect(historyPanel).toHaveTextContent('可用 K 线');
    expect(historyPanel).toHaveTextContent('0');
    expect(historyPanel).toHaveTextContent('缺口 K 线');
    expect(historyPanel).toHaveTextContent('90');
    const summary = within(page).getByTestId('stock-consumer-research-summary');
    expect(summary).toHaveTextContent('历史数据暂缺，价格走势图暂不可用。');
    expect(summary).toHaveTextContent('置信度为低：关键价格、历史或结构证据不足，页面只保留可核验事实。');
    expect(page).toHaveTextContent('K线行情证据缺失时，页面仅展示已确认的就绪边界。');
    expect(page).not.toHaveTextContent('OHLCV 证据缺失时');
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
    getQuoteMock.mockResolvedValue({
      ...baseQuote(),
      isFallback: true,
      sourceConfidence: baseQuote().sourceConfidence,
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const quotePanel = await within(page).findByTestId('stock-quote-boundary-panel');

    expect(quotePanel).toHaveTextContent('原子报价观察');
    expect(quotePanel).toHaveTextContent('替代路径报价可用');
    expect(quotePanel).toHaveTextContent('来源: Alpaca');
    expect(quotePanel).toHaveTextContent('新鲜度: 新鲜');
    expect(quotePanel).toHaveTextContent('替代路径: 是');
    expect(quotePanel).toHaveTextContent('市场截至');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/provider_runtime|source_confidence|requestId|traceId|cache|debug/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it.each(['providerState', 'availabilityState', 'source', 'sourceConfidence'] as const)('preserves %s fallback provenance through the quote boundary and exported evidence pack', async (fallbackMarker) => {
    const quote = baseQuote();
    getQuoteMock.mockResolvedValue({
      ...quote,
      providerState: fallbackMarker === 'providerState' ? 'fallback' : quote.providerState,
      availabilityState: fallbackMarker === 'availabilityState' ? 'fallback' : quote.availabilityState,
      source: fallbackMarker === 'source' ? 'fallback' : quote.source,
      isFallback: false,
      sourceConfidence: {
        ...quote.sourceConfidence,
        source: fallbackMarker === 'sourceConfidence' ? 'fallback' : quote.sourceConfidence?.source,
        isFallback: false,
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
    const registry = await within(page).findByTestId('single-stock-evidence-pack-registry');
    expect(quotePanel).toHaveTextContent('替代路径报价可用');
    expect(quotePanel).toHaveTextContent('替代路径: 是');

    fireEvent.click(within(registry).getByTestId('single-stock-evidence-pack-copy'));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    const copied = String((navigator.clipboard.writeText as ReturnType<typeof vi.fn>).mock.calls.at(-1)?.[0] || '');
    expect(JSON.parse(copied).quoteLineage).toMatchObject({ fallback: true });
  });

  it('keeps cache provenance pending when only a quote source is known', async () => {
    const quote = baseQuote();
    getQuoteMock.mockResolvedValue({
      ...quote,
      freshness: null,
      availabilityState: null,
      providerState: null,
      sourceConfidence: {
        ...quote.sourceConfidence,
        freshness: null,
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
    const registry = await within(page).findByTestId('single-stock-evidence-pack-registry');
    expect(quotePanel).toHaveTextContent('缓存: 待确认');

    fireEvent.click(within(registry).getByTestId('single-stock-evidence-pack-copy'));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    const copied = String((navigator.clipboard.writeText as ReturnType<typeof vi.fn>).mock.calls.at(-1)?.[0] || '');
    expect(JSON.parse(copied).quoteLineage).toMatchObject({ cached: '待补证' });
  });

  it.each([
    ['isUnavailable', '报价标记为不可用', '新鲜度: 不可用'],
    ['isSynthetic', '样本报价', '新鲜度: 样本 / 演示'],
    ['isStale', '过期报价可用', '新鲜度: 已过期'],
    ['isPartial', '部分报价可用', '新鲜度: 部分可用'],
  ] as const)('lets top-level %s=true override a nested false quote flag', async (flag, stateCopy, freshnessCopy) => {
    const quote = baseQuote();
    getQuoteMock.mockResolvedValue({
      ...quote,
      [flag]: true,
      sourceConfidence: {
        ...quote.sourceConfidence,
        [flag]: false,
      },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const quotePanel = within(page).getByTestId('stock-quote-boundary-panel');
    expect(quotePanel).toHaveTextContent(stateCopy);
    expect(quotePanel).toHaveTextContent(freshnessCopy);
  });

  it('lets nested isUnavailable=true override a top-level false quote flag', async () => {
    const quote = baseQuote();
    getQuoteMock.mockResolvedValue({
      ...quote,
      isUnavailable: false,
      sourceConfidence: {
        ...quote.sourceConfidence,
        isUnavailable: true,
      },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const quotePanel = within(page).getByTestId('stock-quote-boundary-panel');
    const summary = within(page).getByTestId('stock-consumer-research-summary');
    const registry = within(page).getByTestId('single-stock-evidence-pack-registry');
    expect(quotePanel).toHaveTextContent('报价标记为不可用');
    expect(quotePanel).toHaveTextContent('新鲜度: 不可用');
    expect(summary).not.toHaveTextContent('$214.6');
    expect(summary).not.toHaveTextContent('+1.11%');
    expect(within(registry).getByTestId('single-stock-evidence-pack-copy-blocked')).toBeDisabled();
    expect(within(registry).queryByTestId('single-stock-evidence-pack-copy')).not.toBeInTheDocument();
    expect(within(registry).queryByTestId('single-stock-evidence-pack-download')).not.toBeInTheDocument();
  });

  it.each([
    ['unavailable', { isUnavailable: true, isSynthetic: true, isStale: true, freshness: 'fresh' }, '报价标记为不可用', '新鲜度: 不可用'],
    ['synthetic', { isSynthetic: true, isStale: true, freshness: 'fresh' }, '样本报价', '新鲜度: 样本 / 演示'],
    ['stale', { isStale: true, freshness: 'delayed' }, '过期报价可用', '新鲜度: 已过期'],
    ['delayed', { isPartial: true, freshness: 'delayed' }, '延迟报价可用', '新鲜度: 延迟'],
    ['partial', { isPartial: true, freshness: 'cached' }, '部分报价可用', '新鲜度: 部分可用'],
    ['cached', { freshness: 'cached' }, '缓存报价可用', '新鲜度: 缓存'],
  ] as const)('uses conservative %s quote freshness precedence when states conflict', async (_scenario, overrides, stateCopy, freshnessCopy) => {
    const quote = baseQuote();
    getQuoteMock.mockResolvedValue({
      ...quote,
      ...overrides,
      sourceConfidence: {
        ...quote.sourceConfidence,
        freshness: overrides.freshness,
      },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const quotePanel = await screen.findByTestId('stock-quote-boundary-panel');
    expect(quotePanel).toHaveTextContent(stateCopy);
    expect(quotePanel).toHaveTextContent(freshnessCopy);
  });

  it('renders cached price-history technical indicator values as research-only context', async () => {
    getQuoteMock.mockResolvedValue({
      ...baseQuote(),
      freshness: 'cached',
      sourceConfidence: {
        ...baseQuote().sourceConfidence,
        freshness: 'cached',
      },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());
    getTechnicalIndicatorsMock.mockResolvedValue({
      ...technicalIndicatorsAvailable(),
      freshness: 'fixture',
    });
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    try {
      renderRoutePattern(
        <StockStructureDecisionPage />,
        '/zh/stocks/AAPL/structure-decision',
        '/zh/stocks/:stockCode/structure-decision',
      );

      const page = await screen.findByTestId('stock-structure-decision-page');
      const panel = await within(page).findByTestId('stock-technical-indicators-panel');
      const quoteObservation = within(page).getByTestId('stock-quote-observation-strip');

      expect(quoteObservation).toHaveTextContent('新鲜度: 缓存');
      expect(quoteObservation).toHaveTextContent('缓存: 是');
      expect(quoteObservation).not.toHaveTextContent('新鲜度: 新鲜');
      expect(getTechnicalIndicatorsMock).toHaveBeenCalledWith('AAPL');
      expect(panel).toHaveTextContent('本地价格历史技术指标');
      expect(panel).toHaveTextContent('指标可用');
      expect(panel).toHaveTextContent('本地价格历史边界');
      expect(panel).toHaveTextContent('样本 / 演示');
      expect(panel).toHaveTextContent('指标输入截至 05/28');
      expect(panel).not.toHaveTextContent(/更新\s*05\/28/);
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
      expect(consoleError).not.toHaveBeenCalled();
      expect(panel.textContent || '').not.toMatch(/OHLCV|daily OHLCV|historical OHLCV/i);
      expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
    } finally {
      consoleError.mockRestore();
    }
  });

  it('does not promote history service success to freshness without freshness evidence', async () => {
    const history = baseHistory('AAPL', 60);
    getHistoryMock.mockResolvedValue({
      ...history,
      diagnostics: { ...history.diagnostics, status: 'success' },
      sourceConfidence: { ...history.sourceConfidence, freshness: null, isPartial: false },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const historyObservation = within(page).getByTestId('stock-history-observation-strip');
    expect(historyObservation).toHaveTextContent('新鲜度: 新鲜度待确认');
    expect(historyObservation).toHaveTextContent('可用 60');
    expect(historyObservation).toHaveTextContent('缺口 30');
    expect(within(historyObservation).queryByText('新鲜度: 新鲜')).not.toBeInTheDocument();
  });

  it('lets explicit stale history override optimistic freshness', async () => {
    const history = baseHistory('AAPL', 60);
    getHistoryMock.mockResolvedValue({
      ...history,
      sourceConfidence: { ...history.sourceConfidence, freshness: 'fresh', isStale: true },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const historyObservation = within(page).getByTestId('stock-history-observation-strip');
    expect(historyObservation).toHaveTextContent('新鲜度: 已过期');
    expect(historyObservation).not.toHaveTextContent('新鲜度: 新鲜');
  });

  it('lets explicit partial history override optimistic freshness', async () => {
    const history = baseHistory('AAPL', 60);
    getHistoryMock.mockResolvedValue({
      ...history,
      sourceConfidence: { ...history.sourceConfidence, freshness: 'fresh', isPartial: true },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const historyObservation = within(page).getByTestId('stock-history-observation-strip');
    expect(historyObservation).toHaveTextContent('新鲜度: 部分可用');
    expect(historyObservation).toHaveTextContent('可用 60');
    expect(historyObservation).toHaveTextContent('缺口 30');
    expect(historyObservation).not.toHaveTextContent('新鲜度: 新鲜');
  });

  it.each([
    ['isUnavailable', '历史数据不可用'],
    ['isSynthetic', '样本历史已返回'],
  ] as const)('excludes returned %s history bars from every consumer projection', async (flag, readinessCopy) => {
    const history = baseHistory('AAPL', 60);
    getHistoryMock.mockResolvedValue({
      ...history,
      sourceConfidence: { ...history.sourceConfidence, freshness: 'fresh', [flag]: true },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const observation = within(page).getByTestId('stock-history-observation-strip');
    const readiness = within(page).getByTestId('stock-history-readiness-panel');
    expect(observation).toHaveTextContent('可用 0');
    expect(observation).toHaveTextContent('缺口 90');
    const emptyChart = within(page).getByTestId('stock-history-empty-chart-state');
    expect(emptyChart).toBeInTheDocument();
    expect(within(page).queryByTestId('stock-history-core-chart')).not.toBeInTheDocument();
    expect(readiness).toHaveTextContent(readinessCopy);
    expect(readiness).toHaveTextContent('结构样本不足');
    expect(readiness).not.toHaveTextContent('结构计算已返回');
    if (flag === 'isSynthetic') {
      expect(emptyChart).toHaveTextContent('已返回的样本历史仅供观察，不绘制图表。');
    }
  });

  it('excludes source-only synthetic history from readiness counts and chart points', async () => {
    const history = baseHistory('AAPL', 60);
    getHistoryMock.mockResolvedValue({
      ...history,
      source: 'fixture',
      sourceConfidence: { ...history.sourceConfidence, freshness: 'fresh', isSynthetic: false },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const observation = within(page).getByTestId('stock-history-observation-strip');
    const readiness = within(page).getByTestId('stock-history-readiness-panel');
    expect(observation).toHaveTextContent('新鲜度: 样本 / 演示');
    expect(observation).toHaveTextContent('可用 0');
    expect(readiness).toHaveTextContent('样本历史已返回');
    expect(within(page).getByTestId('stock-history-empty-chart-state')).toHaveTextContent('已返回的样本历史仅供观察，不绘制图表。');
    expect(within(page).queryByTestId('stock-history-core-chart')).not.toBeInTheDocument();
  });

  it('keeps a stale technical snapshot stale when an as-of timestamp is present', async () => {
    const indicators = technicalIndicatorsAvailable();
    getTechnicalIndicatorsMock.mockResolvedValue({
      ...indicators,
      freshness: 'stale',
      dataQuality: { ...indicators.dataQuality, freshness: 'stale' },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const panel = await screen.findByTestId('stock-technical-indicators-panel');
    expect(panel).toHaveTextContent('已过期');
    expect(panel).toHaveTextContent('指标输入截至 05/28');
    expect(panel).not.toHaveTextContent('最新可用');
    expect(panel).not.toHaveTextContent(/更新\s*05\/28/);
  });

  it('does not borrow Structure Decision bar counts when the History request fails', async () => {
    getHistoryMock.mockRejectedValue(new Error('history unavailable'));
    getStructureDecisionMock.mockResolvedValue({
      ...baseStructureDecision(),
      dataQuality: {
        ...baseStructureDecision().dataQuality,
        requestedDays: 90,
        observedBars: 90,
        usableBars: 90,
      },
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const historyObservation = within(page).getByTestId('stock-history-observation-strip');
    const historyReadiness = within(page).getByTestId('stock-history-readiness-panel');
    expect(historyObservation).toHaveTextContent('历史数据不可用');
    expect(historyObservation).toHaveTextContent('可用 0');
    expect(historyObservation).toHaveTextContent('所需 90');
    expect(historyObservation).toHaveTextContent('缺口 90');
    expect(historyObservation).not.toHaveTextContent('可用 90');
    expect(historyReadiness).toHaveTextContent('历史数据不可用');
    expect(historyReadiness).not.toHaveTextContent('历史数据可用');
  });

  it('keeps an explicitly disabled history source distinct from unavailable history', async () => {
    const history = baseHistory('AAPL', 0);
    getHistoryMock.mockResolvedValue({
      ...history,
      diagnostics: {
        ...history.diagnostics,
        status: 'disabled',
        reason: 'not configured',
      },
      sourceConfidence: {
        ...history.sourceConfidence,
        freshness: 'unknown',
        isUnavailable: false,
      },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const readiness = within(page).getByTestId('stock-history-readiness-panel');
    expect(readiness).toHaveTextContent('历史来源未启用');
    expect(readiness).not.toHaveTextContent('历史数据不可用');
  });

  it.each(['missing', 'missing_cache'] as const)('keeps explicit %s history distinct from unavailable history', async (status) => {
    const history = baseHistory('AAPL', 0);
    getHistoryMock.mockResolvedValue({
      ...history,
      diagnostics: {
        ...history.diagnostics,
        status,
      },
      sourceConfidence: {
        ...history.sourceConfidence,
        freshness: 'fresh',
        isUnavailable: false,
      },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const observation = within(page).getByTestId('stock-history-observation-strip');
    const readiness = within(page).getByTestId('stock-history-readiness-panel');
    expect(observation).toHaveTextContent('新鲜度: 历史数据待补');
    expect(readiness).toHaveTextContent('历史数据待补');
    expect(readiness).not.toHaveTextContent('历史数据不可用');
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

    expect(panel).toHaveTextContent('本地价格历史暂不可用');
    expect(panel).toHaveTextContent('本地行情待补');
    expect(panel).toHaveTextContent('所需历史');
    expect(panel).toHaveTextContent('200');
    expect(panel).toHaveTextContent('已观察历史');
    expect(panel).toHaveTextContent('0');
    expect(panel).toHaveTextContent('历史缺口');
    expect(panel).toHaveTextContent('200');
    expect(panel).toHaveTextContent('不推断指标');
    expect(panel).not.toHaveTextContent('210.12');
    expect(panel).not.toHaveTextContent('SMA 20');
    expect(panel.textContent || '').not.toMatch(/OHLCV|daily OHLCV|historical OHLCV/i);
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
    expect(panel).toHaveTextContent('技术指标来源待确认');
    expect(panel).not.toHaveTextContent('本地价格历史边界');

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
      origin: 'providerQuote',
      price: 214.55,
      changePercent: 1.11,
      asOf: '2026-05-28T09:30:00Z',
      timestampScope: 'marketAsOf',
      sourceLabel: 'Alpaca',
      freshness: 'live',
      cached: false,
      fallback: false,
      stale: false,
      partial: false,
      synthetic: false,
      unavailable: false,
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
        state: 'available',
        price: 999,
        changePercent: 9.99,
        asOf: '2026-06-01T08:00:00Z',
      },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const summary = within(page).getByTestId('stock-consumer-research-summary');
    const registry = within(page).getByTestId('single-stock-evidence-pack-registry');
    const quoteLedgerRow = within(within(page).getByTestId('stock-evidence-ledger')).getByRole('row', { name: /^报价/ });
    expect(summary).toHaveTextContent('$214.6');
    expect(summary).not.toHaveTextContent('$999');
    expect(summary).toHaveTextContent('报价时间待确认');
    expect(summary).not.toHaveTextContent('06/01');
    expect(quoteLedgerRow).toHaveTextContent('报价时间待确认');
    expect(quoteLedgerRow).not.toHaveTextContent('06/01');
    fireEvent.click(within(registry).getByTestId('single-stock-evidence-pack-copy'));

    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    const copied = String((navigator.clipboard.writeText as ReturnType<typeof vi.fn>).mock.calls.at(-1)?.[0] || '');
    const pack = JSON.parse(copied);

    expect(pack.quoteLineage).toMatchObject({
      origin: 'providerQuote',
      price: 214.55,
      changePercent: 1.11,
      asOf: '待补证',
      timestampScope: 'none',
      sourceLabel: '待补证',
      freshness: '待补证',
      cached: '待补证',
      fallback: false,
      confidenceWeight: '待补证',
      coverage: '待补证',
    });
    expect(pack.dataReadiness.quoteState).toBe('报价新鲜度待确认');
  });

  it('does not mark quote evidence exportable when current price is absent', async () => {
    getQuoteMock.mockResolvedValue({
      ...baseQuote(),
      currentPrice: null,
      freshness: 'live',
      sourceConfidence: {
        ...baseQuote().sourceConfidence,
        freshness: 'live',
        isUnavailable: true,
      },
    });
    getResearchPacketMock.mockResolvedValue({
      ...partialResearchPacket(),
      quote: {
        state: 'available',
        price: 214.55,
        changePercent: 1.11,
        asOf: '2026-05-28T09:30:00Z',
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
    const registry = await within(page).findByTestId('single-stock-evidence-pack-registry');

    expect(quotePanel).toHaveTextContent('报价标记为不可用');
    expect(quotePanel).not.toHaveTextContent('报价可用');
    expect(quotePanel).not.toHaveTextContent('$214.6');
    expect(registry).toHaveTextContent('待补证');
    expect(within(registry).getByTestId('single-stock-evidence-pack-copy-blocked')).toBeDisabled();
    expect(within(registry).queryByTestId('single-stock-evidence-pack-copy')).not.toBeInTheDocument();
    expect(within(registry).queryByTestId('single-stock-evidence-pack-download')).not.toBeInTheDocument();
    expect(navigator.clipboard.writeText).not.toHaveBeenCalled();
  });

  it('does not export fake evidence when quote evidence is unavailable', async () => {
    getQuoteMock.mockRejectedValueOnce(new Error('quote unavailable'));
    getResearchPacketMock.mockResolvedValue({
      ...partialResearchPacket(),
      quote: { state: 'unknown', price: null, changePercent: null, asOf: null },
    });
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

    expect(quotePanel).toHaveTextContent('过期报价可用');
    expect(quotePanel).toHaveTextContent('来源: Alpaca');
    expect(quotePanel).toHaveTextContent('新鲜度: 已过期');
    expect(quotePanel).toHaveTextContent('该报价已经过期，不能视为当前状态。');
    expect(quotePanel).not.toHaveTextContent('新鲜度: 新鲜');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/provider|cache|debug|trace|sourceAuthority|raw|fallback/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it('renders sample quote lineage as observation only', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error');
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
    const stateChip = within(quotePanel).getByTestId('stock-quote-boundary-chip-state');
    const sourceChip = within(quotePanel).getByTestId('stock-quote-boundary-chip-source');
    const freshnessChip = within(quotePanel).getByTestId('stock-quote-boundary-chip-freshness');
    const duplicateKeyWarningSeen = consoleErrorSpy.mock.calls.some((call) => call.some((arg) => (
      typeof arg === 'string'
      && arg.includes('same key')
      && arg.includes('样本 / 演示')
    )));

    expect(stateChip).toHaveTextContent('样本报价');
    expect(sourceChip).toHaveTextContent('来源: Fixture');
    expect(freshnessChip).toHaveTextContent('样本 / 演示');
    expect(sourceChip.compareDocumentPosition(freshnessChip) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(quotePanel).toHaveTextContent('当前为样本或演示数据，仅供观察。');
    expect(duplicateKeyWarningSeen).toBe(false);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/provider|cache|debug|trace|sourceAuthority|raw|fallback/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it.each([
    ['source type', { sourceType: 'synthetic_placeholder' }, '样本报价'],
    ['fixture source type', { sourceType: 'synthetic_fixture' }, '样本报价'],
    ['source marker', { source: 'unavailable' }, '报价标记为不可用'],
  ] as const)('fails closed on a %s quote classification token without relying on boolean flags', async (_label, overrides, expectedState) => {
    const quote = baseQuote();
    getQuoteMock.mockResolvedValue({
      ...quote,
      ...overrides,
      freshness: 'live',
      isSynthetic: false,
      isUnavailable: false,
      sourceConfidence: {
        ...quote.sourceConfidence,
        freshness: 'live',
        isSynthetic: false,
        isUnavailable: false,
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
    const summary = within(page).getByTestId('stock-consumer-research-summary');
    const registry = within(page).getByTestId('single-stock-evidence-pack-registry');
    expect(quotePanel).toHaveTextContent(expectedState);
    expect(summary).not.toHaveTextContent('$214.6');
    expect(summary).not.toHaveTextContent('+1.11%');
    expect(within(registry).getByTestId('single-stock-evidence-pack-copy-blocked')).toBeDisabled();
    expect(within(registry).queryByTestId('single-stock-evidence-pack-copy')).not.toBeInTheDocument();
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
    const summary = within(page).getByTestId('stock-consumer-research-summary');
    const registry = within(page).getByTestId('single-stock-evidence-pack-registry');

    expect(quotePanel).toHaveTextContent('研究包报价可用');
    expect(quotePanel).toHaveTextContent('研究包投影；提供方待确认');
    expect(quotePanel).toHaveTextContent('研究包截至 05/28 17:30');
    expect(quotePanel).toHaveTextContent('新鲜度: 新鲜度待确认');
    expect(quotePanel).toHaveTextContent('缓存: 待确认');
    expect(quotePanel).toHaveTextContent('替代路径: 待确认');
    expect(quotePanel).toHaveTextContent('提供方、新鲜度、缓存与替代路径状态仍待确认');
    expect(summary).toHaveTextContent('$214.6');
    expect(summary).toHaveTextContent('+1.11%');
    expect(summary).toHaveTextContent('研究包截至 05/28 17:30');
    fireEvent.click(within(registry).getByTestId('single-stock-evidence-pack-copy'));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    const copied = String((navigator.clipboard.writeText as ReturnType<typeof vi.fn>).mock.calls.at(-1)?.[0] || '');
    const pack = JSON.parse(copied);
    expect(pack.quoteLineage).toMatchObject({
      origin: 'researchPacket',
      price: 214.55,
      changePercent: 1.11,
      asOf: '2026-05-28T09:30:00Z',
      timestampScope: 'packetAsOf',
      sourceLabel: '研究包投影；提供方待确认',
      freshness: '待补证',
      cached: '待补证',
      fallback: '待补证',
      stale: '待补证',
      partial: '待补证',
      synthetic: '待补证',
    });
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/provider|cache|debug|trace|sourceAuthority|raw|fallback/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
  });

  it('preserves stale research-packet quote state and lineage when the provider quote fails', async () => {
    getQuoteMock.mockRejectedValueOnce(new Error('quote unavailable'));
    getResearchPacketMock.mockResolvedValue({
      ...partialResearchPacket(),
      quote: {
        state: 'stale',
        price: 214.55,
        changePercent: 1.11,
        asOf: '2026-05-28T09:30:00Z',
      },
    });
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const quotePanel = within(page).getByTestId('stock-quote-boundary-panel');
    const registry = within(page).getByTestId('single-stock-evidence-pack-registry');
    expect(quotePanel).toHaveTextContent('过期研究包报价可用');
    expect(quotePanel).toHaveTextContent('新鲜度: 已过期');
    expect(quotePanel).toHaveTextContent('研究包截至 05/28 17:30');
    expect(quotePanel).not.toHaveTextContent('新鲜度: 新鲜度待确认');

    fireEvent.click(within(registry).getByTestId('single-stock-evidence-pack-copy'));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalled());
    const copied = String((navigator.clipboard.writeText as ReturnType<typeof vi.fn>).mock.calls.at(-1)?.[0] || '');
    const pack = JSON.parse(copied);
    expect(pack.quoteLineage).toMatchObject({
      origin: 'researchPacket',
      freshness: 'stale',
      stale: true,
      timestampScope: 'packetAsOf',
    });
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
    // G025: 0-field options metrics collapse to a bounded empty state (no 待补 cell wall).
    expect(surface).toHaveAttribute('data-module-density', 'bounded-empty');
    expect(metrics).toHaveAttribute('data-module-density', 'bounded-empty');
    expect(metrics).toHaveTextContent('尚未填充授权期权指标');
    expect(metrics).not.toHaveTextContent('GEX');
    expect(metrics).not.toHaveTextContent('待补证');
    expect(metrics.textContent?.match(/待补证/g) ?? []).toHaveLength(0);
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
    expect(surface).toHaveTextContent('结构来源身份待确认');
    expect(surface).not.toHaveTextContent('结构来源已配置');
    expect(within(surface).getByText('结构来源身份待确认')).toHaveAttribute('data-status', 'unknown');
    expect(surface).toHaveTextContent('新鲜');
    expect(surface).toHaveTextContent('期权快照截至 06/19');
    expect(surface).not.toHaveTextContent(/更新\s*06\/19/);
    expect(surface).toHaveAttribute('data-module-density', 'full');
    expect(metrics).toHaveAttribute('data-module-density', 'full');
    expect(metrics).toHaveTextContent('200,000');
    expect(metrics).toHaveTextContent('212.5');
    expect(metrics).toHaveTextContent('0.3');
    expect(metrics).toHaveTextContent('-0.1');
    expect(metrics).toHaveTextContent('OI 42%');
    expect(metrics).toHaveTextContent('成交 35%');
    expect(metrics).toHaveTextContent('2,000 / 560');
    expect(metrics).not.toHaveTextContent('待补证');
  });

  it('keeps a stale options snapshot stale when an as-of timestamp is present', async () => {
    const structure = optionsStructurePopulated();
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());
    getOptionsStructureMock.mockResolvedValue({
      ...structure,
      freshness: 'stale',
      snapshot: { ...structure.snapshot, freshness: 'stale' },
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const surface = await screen.findByTestId('stock-options-structure-surface');
    expect(surface).toHaveTextContent('已过期');
    expect(surface).toHaveTextContent('期权快照截至 06/19');
    expect(surface).not.toHaveTextContent('新鲜度待确认');
    expect(surface).not.toHaveTextContent(/更新\s*06\/19/);
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
    expect(panel).toHaveTextContent('研究资料可用');
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
    getQuoteMock.mockResolvedValue({
      ...baseQuote(),
      isPartial: true,
      sourceConfidence: {
        ...baseQuote().sourceConfidence,
        isPartial: true,
      },
    });
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
    const quoteObservation = within(page).getByTestId('stock-quote-observation-strip');

    expect(quoteObservation).toHaveTextContent('新鲜度: 部分可用');
    expect(quoteObservation).toHaveTextContent('该报价为部分可用，不能支持完整市场判断。');
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

    expect(panel).toHaveTextContent('研究资料待更新');
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

  it('sanitizes WorkBuddy peer metadata and history wording in the rendered peer snapshot', async () => {
    verifyTickerExistsMock.mockResolvedValue({
      stockCode: 'AAPL',
      normalizedSymbol: 'AAPL',
      market: 'us',
      status: 'valid',
      valid: true,
      exists: true,
      stockName: 'Apple',
      message: 'verified',
    });
    getQuoteMock.mockResolvedValue(baseQuote());
    getHistoryMock.mockResolvedValue(baseHistory('AAPL', 0));
    getTechnicalIndicatorsMock.mockResolvedValue(null);
    getOptionsStructureMock.mockResolvedValue(null);
    getResearchPacketMock.mockResolvedValue(null);
    getStructureDecisionMock.mockResolvedValue({
      ...baseStructureDecision(),
      peerCorrelationSnapshot: {
        symbol: 'AAPL',
        peerGroup: {
          status: 'unavailable',
          label: 'No verified local peer group metadata is available for AAPL.',
          symbols: [],
        },
        correlationState: 'insufficient_evidence',
        peerEvidence: [],
        divergenceEvidence: [],
        staleInputs: [],
        missingInputs: [
          'No verified local peer group metadata is available for AAPL.',
          'Load recent local daily OHLCV for the symbol and at least two verified peers.',
          'Peer correlation was not evaluated because structure evidence exceeded the latency boundary.',
        ],
        confidenceCap: 'low',
        observationBoundary: 'Observation-only peer movement context; no personalized action instruction.',
        researchNextSteps: [
          'Add verified local peer group metadata before interpreting peer movement.',
          'Load recent local daily OHLCV for the symbol and at least two verified peers.',
        ],
      },
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const snapshot = await within(page).findByTestId('stock-structure-peer-correlation-snapshot');
    expect(snapshot).toHaveTextContent('同业对比信息待确认');
    expect(snapshot).toHaveTextContent('历史行情待补');
    expect(snapshot).toHaveTextContent('因结构证据超过时效边界，未评估同业相关性。');
    expect(snapshot).toHaveTextContent('补齐本地同业分组后再复核同业走势。');
    expect(snapshot.textContent || '').not.toMatch(/No verified local peer group metadata|Add verified local peer group metadata|Load recent local daily OHLCV|Peer correlation was not evaluated because structure evidence exceeded the latency boundary/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/No verified local peer group metadata|Add verified local peer group metadata|Load recent local daily OHLCV|Peer correlation was not evaluated because structure evidence exceeded the latency boundary/i);
    expect(findConsumerRawLeakage(snapshot.textContent || '')).toEqual([]);
  });

  it('fail-closes sparse structure payloads without crashing on usableBars or fabricating scores', async () => {
    getStructureDecisionMock.mockResolvedValue({
      schemaVersion: 'stock_structure_decision_api_v1',
      ticker: 'AAPL',
      symbol: 'AAPL',
      structureState: 'unavailable',
      confidence: 'low',
      // Omit dataQuality, explanation, researchNotes, arrays (G031 crash shape)
      observationOnly: true,
      decisionGrade: false,
      noAdviceDisclosure: 'Observation only.',
    });
    getResearchPacketMock.mockRejectedValue(new Error('packet unavailable'));
    getHistoryMock.mockRejectedValue(new Error('history unavailable'));
    getQuoteMock.mockRejectedValue(new Error('quote unavailable'));
    getTechnicalIndicatorsMock.mockRejectedValue(new Error('indicators unavailable'));
    getStockEvidenceMock.mockRejectedValue(new Error('evidence unavailable'));
    getOptionsStructureMock.mockRejectedValue(new Error('options unavailable'));

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    // Must not hit error-boundary / crash shell
    expect(within(page).queryByText(/页面暂时无法加载/)).not.toBeInTheDocument();
    expect(page.textContent || '').not.toMatch(/usableBars|TypeError|Cannot read properties/i);
    // No fabricated neutral score or zero bars presented as evidence
    expect(page.textContent || '').not.toMatch(/Usable bars:\s*0|可用 K 线：0/);
    expect(page.textContent || '').not.toMatch(/\b50\b.*score|score.*\b50\b/i);
  });
});
