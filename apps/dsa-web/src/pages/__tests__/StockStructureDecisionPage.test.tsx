import type React from 'react';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import StockStructureDecisionPage from '../StockStructureDecisionPage';
import { findConsumerRawLeakage } from '../../test-utils/consumerRawLeakageGuard';

const {
  languageState,
  verifyTickerExistsMock,
  getStructureDecisionMock,
  getResearchPacketMock,
  getStructureDecisionsBatchMock,
} = vi.hoisted(() => ({
  languageState: { value: 'zh' as 'zh' | 'en' },
  verifyTickerExistsMock: vi.fn(),
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

describe('StockStructureDecisionPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
  });

  it('requests and renders the symbol research packet with compact consumer labels', async () => {
    getStructureDecisionMock.mockResolvedValue(baseStructureDecision());

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const panel = await within(page).findByTestId('stock-research-packet-panel');

    expect(getResearchPacketMock).toHaveBeenCalledWith('AAPL');
    expect(panel).toHaveTextContent('研究就绪快照');
    expect(panel).toHaveTextContent('AAPL');
    expect(panel).toHaveTextContent('Apple');
    expect(panel).toHaveTextContent('部分可用');
    expect(panel).toHaveTextContent('报价可用');
    expect(panel).toHaveTextContent('历史可用');
    expect(panel).toHaveTextContent('结构待补');
    expect(panel).toHaveTextContent('基本面待接入');
    expect(panel).toHaveTextContent('事件待补');
    expect(panel).toHaveTextContent('同业待补');
    expect(panel).toHaveTextContent('待补：基本面、事件、同业');
    expect(panel).toHaveTextContent('补基本面、事件、同业');
    expect(panel).toHaveTextContent('研究记录');
    expect(panel).toHaveTextContent('非交易指令');
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
