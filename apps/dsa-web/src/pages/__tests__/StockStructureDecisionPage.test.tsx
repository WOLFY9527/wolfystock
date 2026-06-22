import type React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StockStructureDecisionPage from '../StockStructureDecisionPage';
import { findConsumerRawLeakage } from '../../test-utils/consumerRawLeakageGuard';

const {
  languageState,
  verifyTickerExistsMock,
  getQuoteMock,
  getStructureDecisionMock,
  getResearchPacketMock,
  getStructureDecisionsBatchMock,
} = vi.hoisted(() => ({
  languageState: { value: 'zh' as 'zh' | 'en' },
  verifyTickerExistsMock: vi.fn(),
  getQuoteMock: vi.fn(),
  getStructureDecisionMock: vi.fn(),
  getResearchPacketMock: vi.fn(),
  getStructureDecisionsBatchMock: vi.fn(),
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: languageState.value,
    t: (key: string) => key,
  }),
}));

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    verifyTickerExists: (...args: unknown[]) => verifyTickerExistsMock(...args),
    getQuote: (...args: unknown[]) => getQuoteMock(...args),
    getStructureDecision: (...args: unknown[]) => getStructureDecisionMock(...args),
    getResearchPacket: (...args: unknown[]) => getResearchPacketMock(...args),
    getStructureDecisionsBatch: (...args: unknown[]) => getStructureDecisionsBatchMock(...args),
  },
}));

const renderRoutePattern = (ui: React.ReactElement, path: string, pattern: string) => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes>
      <Route path={pattern} element={ui} />
    </Routes>
  </MemoryRouter>,
);

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
    state: 'not_integrated',
    fieldsAvailable: [],
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

describe('StockStructureDecisionPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
    languageState.value = 'zh';
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
  });

  it('requests and renders the symbol research packet as a professional evidence stack', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const panel = await within(page).findByTestId('stock-research-packet-panel');
    const quotePanel = await within(page).findByTestId('stock-quote-boundary-panel');

    expect(getQuoteMock).toHaveBeenCalledWith('AAPL');
    expect(getResearchPacketMock).toHaveBeenCalledWith('AAPL');
    expect(quotePanel).toHaveTextContent('报价来源与新鲜度');
    expect(quotePanel).toHaveTextContent('报价可用');
    expect(quotePanel).toHaveTextContent('来源已确认');
    expect(quotePanel).toHaveTextContent('最新可用');
    expect(quotePanel).toHaveTextContent('更新');
    expect(quotePanel).toHaveTextContent('05/28');
    expect(quotePanel).toHaveTextContent('17:30');
    expect(panel).toHaveTextContent('证据栈');
    expect(panel).toHaveTextContent('AAPL');
    expect(panel).toHaveTextContent('Apple');
    expect(panel).toHaveTextContent('证据部分可用');
    expect(panel).toHaveTextContent('仅观察');
    expect(panel).toHaveTextContent('评分待确认');
    expect(panel).toHaveTextContent('可用 3');
    expect(panel).toHaveTextContent('待补 3');
    expect(panel).toHaveTextContent('部分 2');
    expect(panel).toHaveTextContent('报价可用');
    expect(panel).toHaveTextContent('历史可用');
    expect(panel).toHaveTextContent('标的上下文可用');
    expect(panel).toHaveTextContent('基本面待补');
    expect(panel).toHaveTextContent('新闻线索待补');
    expect(panel).toHaveTextContent('风险来源待补');
    expect(panel).toHaveTextContent('市场线索待补');
    expect(panel).toHaveTextContent('研究包可用');
    expect(panel).toHaveTextContent('下一证据缺口');
    expect(panel).toHaveTextContent('基本面待补');
    expect(panel).toHaveTextContent('新闻线索待补');
    expect(panel).toHaveTextContent('市场线索待补');
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
    expect(page.textContent || '').not.toMatch(/available|not_integrated|insufficient|blocked|observationOnly|not personalized financial advice/i);
    expect(page.textContent || '').not.toMatch(/buy|sell|hold|target price|stop-loss|position sizing|买入|卖出|持有|目标价|止损|仓位|建仓|加仓|减仓/i);
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
    expect(page.textContent || '').not.toMatch(/alpaca|provider_runtime|source_confidence|requestId|traceId|cache|debug/i);
    expect(page.textContent || '').not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
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
    expect(page.textContent || '').not.toMatch(/provider|cache|debug|trace|sourceAuthority|raw|fallback/i);
    expect(page.textContent || '').not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
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
    expect(page.textContent || '').not.toMatch(/provider|cache|debug|trace|sourceAuthority|raw|fallback/i);
    expect(page.textContent || '').not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
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
    expect(page.textContent || '').not.toMatch(/provider|cache|debug|trace|sourceAuthority|raw|fallback/i);
    expect(page.textContent || '').not.toMatch(/买入|卖出|持有|目标价|止损|仓位|buy|sell|hold|target price|stop loss|position sizing/i);
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
    expect(panel).toHaveTextContent('报价可用');
    expect(panel).toHaveTextContent('基本面可用');
    expect(panel).toHaveTextContent('新闻线索可用');
    expect(panel).toHaveTextContent('风险来源可用');
    expect(panel).toHaveTextContent('市场线索可用');
    expect(panel).toHaveTextContent('研究包可用');
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
    expect(panel).toHaveTextContent('报价可能延迟');
    expect(panel).toHaveTextContent('历史待补');
    expect(panel).toHaveTextContent('基本面待补');
    expect(panel).toHaveTextContent('新闻线索待补');
    expect(panel).toHaveTextContent('风险来源待补');
    expect(panel).toHaveTextContent('市场线索待补');
    expect(panel).toHaveTextContent('延迟 1');
    expect(panel).toHaveTextContent('下一证据缺口');
    expect(panel).toHaveTextContent('报价待补');
    expect(panel).toHaveTextContent('历史待补');
    expect(page.textContent || '').not.toMatch(/provider|runtime|fallback|sourceAuthority|debug|buy now|target price/i);
    expect(page.textContent || '').not.toMatch(/买入建议|卖出建议|持有建议|目标价|止损|仓位建议|交易建议|操作建议/);
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
    expect(page.textContent || '').not.toMatch(/sorry|apology|available|not_integrated|observationOnly/i);
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
    expect(page.textContent || '').not.toMatch(/insufficient_evidence|freshness=unavailable|\bbreakdown\b|\bavailable\b|\bdaily\b|\blow\b|observation-only/i);
    expect(page.textContent || '').not.toMatch(/provider|cache|runtime|schema|requestId|traceId|fallback|proxy|sourceAuthority|score-grade|raw|debug/i);
    expect(page.textContent || '').not.toMatch(/买入|卖出|持有|目标价|止损|仓位|建仓|加仓|减仓|buy|sell|hold|target price|stop loss|position sizing/i);
  });
});
