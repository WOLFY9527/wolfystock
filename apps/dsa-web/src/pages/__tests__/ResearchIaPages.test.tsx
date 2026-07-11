import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApiError, createParsedApiError } from '../../api/error';
import MarketDecisionCockpitPage from '../MarketDecisionCockpitPage';
import ResearchRadarPage from '../ResearchRadarPage';
import ScenarioLabPage from '../ScenarioLabPage';
import StockStructureDecisionPage from '../StockStructureDecisionPage';
import StockStructureDecisionEntryPage from '../StockStructureDecisionEntryPage';
import { findConsumerRawLeakage, textContentWithoutObservationBoundary } from '../../test-utils/consumerRawLeakageGuard';
import { getDocumentTitle } from '../../utils/documentTitle';

const {
  languageState,
  getDecisionCockpitMock,
  getDailyIntelligenceMock,
  getResearchRadarMock,
  getResearchQueueMock,
  getQuoteMock,
  getResearchPacketMock,
  verifyTickerExistsMock,
  getStructureDecisionMock,
  getStructureDecisionsBatchMock,
  getHistoryMock,
  getTechnicalIndicatorsMock,
  getOptionsStructureMock,
  runScenarioLabMock,
} = vi.hoisted(() => ({
  languageState: { value: 'zh' as 'zh' | 'en' },
  getDecisionCockpitMock: vi.fn(),
  getDailyIntelligenceMock: vi.fn(),
  getResearchRadarMock: vi.fn(),
  getResearchQueueMock: vi.fn(),
  getQuoteMock: vi.fn(),
  getResearchPacketMock: vi.fn(),
  verifyTickerExistsMock: vi.fn(),
  getStructureDecisionMock: vi.fn(),
  getStructureDecisionsBatchMock: vi.fn(),
  getHistoryMock: vi.fn(),
  getTechnicalIndicatorsMock: vi.fn(),
  getOptionsStructureMock: vi.fn(),
  runScenarioLabMock: vi.fn(),
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: languageState.value,
    t: (key: string) => key,
  }),
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    authEnabled: true,
    loggedIn: true,
    passwordSet: true,
    passwordChangeable: true,
    setupState: 'enabled',
    currentUser: {
      id: 1,
      username: 'consumer',
      displayName: 'Consumer Tester',
      isAuthenticated: true,
      isAdmin: false,
    },
    isLoading: false,
    loadError: null,
    login: vi.fn(),
    changePassword: vi.fn(),
    logout: vi.fn(),
    refreshStatus: vi.fn(),
  }),
}));

vi.mock('../../api/marketDecisionCockpit', () => ({
  marketDecisionCockpitApi: {
    getDecisionCockpit: (...args: unknown[]) => getDecisionCockpitMock(...args),
  },
}));

vi.mock('../../api/dailyIntelligence', () => ({
  dailyIntelligenceApi: {
    getDailyIntelligence: (...args: unknown[]) => getDailyIntelligenceMock(...args),
  },
}));

vi.mock('../../api/researchRadar', () => ({
  researchRadarApi: {
    getResearchRadar: (...args: unknown[]) => getResearchRadarMock(...args),
    getResearchQueue: (...args: unknown[]) => getResearchQueueMock(...args),
  },
}));

vi.mock('../../api/scenarioLab', () => ({
  scenarioLabApi: {
    runScenarioLab: (...args: unknown[]) => runScenarioLabMock(...args),
  },
}));

vi.mock('../../api/optionsLab', () => ({
  optionsLabApi: {
    getOptionsStructure: (...args: unknown[]) => getOptionsStructureMock(...args),
  },
}));

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    getQuote: (...args: unknown[]) => getQuoteMock(...args),
    getResearchPacket: (...args: unknown[]) => getResearchPacketMock(...args),
    verifyTickerExists: (...args: unknown[]) => verifyTickerExistsMock(...args),
    getStructureDecision: (...args: unknown[]) => getStructureDecisionMock(...args),
    getStructureDecisionsBatch: (...args: unknown[]) => getStructureDecisionsBatchMock(...args),
    getHistory: (...args: unknown[]) => getHistoryMock(...args),
    getTechnicalIndicators: (...args: unknown[]) => getTechnicalIndicatorsMock(...args),
  },
}));

const renderRoute = (ui: React.ReactElement, path: string) => render(
  <MemoryRouter initialEntries={[path]}>
    {ui}
  </MemoryRouter>,
);

const renderRoutePattern = (ui: React.ReactElement, path: string, pattern: string) => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes>
      <Route path={pattern} element={ui} />
    </Routes>
  </MemoryRouter>,
);

function makeEmptyUnifiedResearchQueue() {
  return {
    schemaVersion: 'research_queue_v1',
    researchQueue: [],
    aggregateSummary: {
      itemCount: 0,
      limit: 10,
      bounded: false,
      bySourceSurface: {},
      byPriorityTier: { urgent_review: 0, follow_up: 0, monitor: 0 },
    },
    sourceSurfacesAggregated: [],
    evidenceGaps: [],
    dataQuality: {
      state: 'no_evidence',
      itemCount: 0,
      sourceSurfacesAvailable: [],
      sourceSurfacesExpected: ['scanner', 'watchlist', 'market', 'manual_gap'],
      failClosed: true,
    },
    noAdviceDisclosure: 'Research-only queue.',
    observationOnly: true,
    decisionGrade: false,
  };
}

describe('research IA pages', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    languageState.value = 'zh';
    getResearchQueueMock.mockResolvedValue(makeEmptyUnifiedResearchQueue());
    getQuoteMock.mockRejectedValue(new Error('quote optional in page test'));
    getResearchPacketMock.mockRejectedValue(new Error('research packet optional in page test'));
    getHistoryMock.mockRejectedValue(new Error('history optional in page test'));
    getTechnicalIndicatorsMock.mockRejectedValue(new Error('technicals optional in page test'));
    getOptionsStructureMock.mockRejectedValue(new Error('options structure optional in page test'));
    verifyTickerExistsMock.mockResolvedValue({
      stockCode: 'AAPL',
      normalizedSymbol: 'AAPL',
      market: 'us',
      status: 'valid',
      valid: true,
      exists: true,
      stockName: 'Apple',
      message: 'Symbol verified.',
    });
  });

  it('renders the market decision cockpit with a daily intelligence briefing and calm degraded notes', async () => {
    getDecisionCockpitMock.mockResolvedValue({
      schemaVersion: 'market_decision_cockpit.v1',
      generatedAt: '2026-06-15T09:30:00Z',
      marketRegimeDecision: {
        regime: 'risk_on',
        confidence: 'medium',
        driverScores: {
          breadthParticipation: {
            score: 62,
            evidenceState: 'partial',
            reasons: ['广度仍需确认'],
          },
        },
        explanation: {
          whyThisRegime: ['市场广度改善'],
          whatConfirmsIt: ['跨资产压力缓和'],
        },
        invalidationConditions: ['广度快速回落'],
        researchPriorities: {
          watchToday: ['观察广度参与'],
          needsMoreEvidence: ['期权链缺口'],
          investigateNext: ['查看研究队列'],
        },
      },
      researchQueuePreview: {
        topCandidates: [{ ticker: 'ALFA', priority: 'high', researchBias: 'strengthContinuation', whyOnRadar: ['相对强弱改善'] }],
        queueQuality: 'mixed',
        evidenceGaps: ['research_candidates_unavailable'],
        previewOnly: true,
      },
      optionsStructureStatus: {
        gammaEvidenceStatus: 'live_gex_not_implemented_v1',
        observationOnly: true,
        decisionGrade: false,
        missingEvidence: [{ code: 'insufficient_usable_contracts' }, { code: 'missing_spot_reference' }],
        blockedReasonCodes: ['option_chain_unavailable'],
      },
      cockpitSummary: {
        whatChanged: ['广度改善'],
        whatToWatch: ['观察广度参与'],
        confidenceLimits: ['Gamma 证据不可用'],
      },
      noAdviceDisclosure: '仅供研究语境参考。',
      dataQuality: { status: 'degraded' },
    });
    getDailyIntelligenceMock.mockResolvedValue({
      schemaVersion: 'daily_intelligence_briefing_v1',
      generatedAt: '2026-06-15T09:30:00Z',
      briefingDate: '2026-06-15',
      sessionLabel: 'pre-market',
      marketRegimeSummary: {
        regime: 'risk_on',
        confidence: 'medium',
        summary: '广度与流动性仍支撑当前风险偏好观察。',
        supportingObservations: ['广度参与维持稳定。'],
        invalidationObservations: ['若广度明显收窄，当前观察需要重估。'],
      },
      whatChanged: ['研究队列更偏向相对强弱延续。'],
      sectionLinks: [
        {
          label: 'Research Radar',
          route: '/research/radar',
          section: 'topResearchPriorities',
          reason: 'research_queue_origin',
        },
        {
          label: 'Scanner',
          route: '/scanner',
          section: 'scannerHighlights',
          reason: 'scanner_candidates_origin',
        },
        {
          label: 'Watchlist',
          route: '/watchlist',
          section: 'watchlistHighlights',
          reason: 'watchlist_research_context',
        },
      ],
      topResearchPriorities: [
        {
          label: 'ALFA research queue',
          source: 'research_radar',
          priority: 'high',
          ticker: 'ALFA',
          observations: ['相对强弱改善。'],
          whatToVerify: ['确认跟随性。'],
          evidenceGaps: ['themeBreadth'],
          evidenceLinks: [
            {
              label: 'Research Radar',
              route: '/research/radar',
              section: 'topResearchPriorities',
              reason: 'research_queue_origin',
            },
            {
              label: 'Stock Structure',
              route: '/stocks/ALFA/structure-decision',
              section: 'topResearchPriorities',
              reason: 'symbol_structure_detail',
            },
          ],
        },
      ],
      scannerHighlights: [
        {
          ticker: 'ALFA',
          priority: 'high',
          observations: ['相对强弱改善。'],
          whatToVerify: ['确认跟随性。'],
          evidenceGaps: ['themeBreadth'],
          riskFlags: ['evidence_partial'],
          evidenceLinks: [
            {
              label: 'Research Radar',
              route: '/research/radar',
              section: 'scannerHighlights',
              reason: 'research_queue_origin',
            },
            {
              label: 'Stock Structure',
              route: '/stocks/ALFA/structure-decision',
              section: 'scannerHighlights',
              reason: 'symbol_structure_detail',
            },
          ],
        },
      ],
      watchlistHighlights: [],
      portfolioStructureHighlights: [],
      scenarioRisks: [
        {
          label: 'Scenario risk section unavailable',
          source: 'degraded_state',
          observations: ['Stored scenario read model is unavailable.'],
          evidenceGaps: ['scenario_risk_read_model_unavailable'],
        },
      ],
      evidenceGaps: ['scenario_risk_read_model_unavailable'],
      degradedInputs: [
        {
          section: 'scenarioRisks',
          status: 'unavailable',
          reason: 'scenario_risk_read_model_unavailable',
        },
        {
          section: 'watchlistHighlights',
          status: 'degraded',
          reason: 'owner_context_missing',
        },
      ],
      onboardingGuidance: {
        title: 'Start a research loop',
        summary: 'Use Market Overview, Watchlist, Scanner, and Research Radar to build an observation-only research loop.',
        conditionsDetected: ['No watchlist items were found.', 'No portfolio holdings were found.'],
      },
      emptyStateActions: [
        {
          label: 'Start with Market Overview',
          route: '/market-overview',
          description: 'Read the market context first.',
        },
        {
          label: 'Run Scanner',
          route: '/scanner',
          description: 'Create a research candidate set.',
        },
        {
          label: 'Add Watchlist Symbol',
          route: '/watchlist',
          description: 'Choose one symbol to observe.',
        },
        {
          label: 'Review Research Radar',
          route: '/research/radar',
          description: 'Review the queue after scanner or watchlist activity.',
        },
      ],
      starterResearchWorkflow: [
        'Open Market Overview to set broad context.',
        'Run Scanner to create a candidate queue.',
        'Choose one watchlist symbol only when you want to observe it.',
      ],
      firstRunChecklist: [
        'Market Overview checked for context.',
        'Scanner run reviewed.',
        'Watchlist symbol chosen by the user.',
      ],
      suggestedResearchEntrypoints: [
        {
          surface: 'Market Overview',
          route: '/market-overview',
          description: 'Start with broad context.',
        },
        {
          surface: 'Research Radar',
          route: '/research/radar',
          description: 'Review after scanner/watchlist activity.',
        },
      ],
      observationOnly: true,
      decisionGrade: false,
    });


    renderRoute(<MarketDecisionCockpitPage />, '/zh/market/decision-cockpit');

    const page = await screen.findByTestId('market-decision-cockpit-page');
    expect(getDocumentTitle('/market/decision-cockpit', 'zh')).toBe('市场决策驾驶舱 - WolfyStock');
    expect(page).toHaveTextContent('市场结构、定位语境与研究队列');
    const dailyBriefing = await screen.findByTestId('daily-intelligence-briefing');
    await within(dailyBriefing).findByText('研究语境简报');
    expect(dailyBriefing).toHaveTextContent('每日研究简报');
    expect(page).toHaveTextContent('研究语境简报');
    expect(page).toHaveTextContent('非决策级');
    expect(page).toHaveTextContent('研究优先级');
    expect(page).toHaveTextContent('扫描重点');
    expect(page).toHaveTextContent('ALFA');
    expect(page).toHaveTextContent('查看证据');
    expect(page).toHaveTextContent('情景风险区块暂不可用');
    expect(page).toHaveTextContent('登录后可附加个人研究队列、观察列表和持仓语境');
    expect(page.textContent || '').not.toContain('scenario_risk_read_model_unavailable');
    expect(page.textContent || '').not.toContain('owner_context_missing');
    expect(page).toHaveTextContent('研究边界');
    expect(page).toHaveTextContent('仅供观察');
    expect(page).toHaveTextContent('判断等级');
    expect(page).toHaveTextContent('未达到可判断等级');
    expect(page).toHaveTextContent('实时 Gamma 观察暂未提供。');
    expect(page).toHaveTextContent('期权链数据暂不可用。');
    expect(page).toHaveTextContent('可用合约不足，暂不形成判断。');
    expect(page).toHaveTextContent('缺少标的现价参考，暂不形成判断。');
    expect(page.textContent || '').not.toContain('observationOnly');
    expect(page.textContent || '').not.toContain('decisionGrade');
    expect(page.textContent || '').not.toContain('live_gex_not_implemented_v1');
    expect(page.textContent || '').not.toContain('option_chain_unavailable');
    expect(page.textContent || '').not.toContain('insufficient_usable_contracts');
    expect(page.textContent || '').not.toContain('missing_spot_reference');
    expect(screen.getByRole('link', { name: '研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(screen.getAllByRole('link', { name: '查看证据：研究雷达' }).some((link) => link.getAttribute('href') === '/zh/research/radar')).toBe(true);
    expect(screen.getByRole('link', { name: '查看证据：扫描器' })).toHaveAttribute('href', '/zh/scanner');
    expect(screen.getAllByRole('link', { name: '查看证据：结构详情' })[0]).toHaveAttribute('href', '/zh/stocks/ALFA/structure-decision');
    expect(screen.getByRole('link', { name: '市场总览' })).toHaveAttribute('href', '/zh/market-overview');
    expect(screen.queryByRole('link', { name: '情景实验室' })).not.toBeInTheDocument();
    const onboardingPanel = within(page).getByTestId('daily-intelligence-onboarding-cta');
    expect(onboardingPanel).toHaveTextContent('首次研究路径');
    expect(onboardingPanel).toHaveTextContent('先看市场概览');
    expect(onboardingPanel).toHaveTextContent('运行 Scanner');
    expect(onboardingPanel).toHaveTextContent('选择观察标的');
    expect(onboardingPanel).toHaveTextContent('查看研究雷达');
    expect(onboardingPanel).toHaveTextContent('Market Overview checked for context.');
    expect(within(onboardingPanel).getByRole('link', { name: '先看市场概览' })).toHaveAttribute('href', '/zh/market-overview');
    expect(within(onboardingPanel).getByRole('link', { name: '运行 Scanner' })).toHaveAttribute('href', '/zh/scanner');
    expect(within(onboardingPanel).getByRole('link', { name: '选择观察标的' })).toHaveAttribute('href', '/zh/watchlist');
    expect(within(onboardingPanel).getByRole('link', { name: '查看研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|下单|目标价|止损|仓位建议/);
  });

  it('keeps the cockpit visible when the daily intelligence briefing is unavailable', async () => {
    getDecisionCockpitMock.mockResolvedValue({
      schemaVersion: 'market_decision_cockpit.v1',
      generatedAt: '2026-06-15T09:30:00Z',
      marketRegimeDecision: {
        regime: 'risk_on',
        confidence: 'medium',
        driverScores: {},
        explanation: {
          whyThisRegime: ['市场广度改善'],
          whatConfirmsIt: ['跨资产压力缓和'],
        },
        invalidationConditions: [],
        researchPriorities: null,
      },
      researchQueuePreview: {
        topCandidates: [],
        queueQuality: 'mixed',
        evidenceGaps: [],
        previewOnly: true,
      },
      optionsStructureStatus: {
        gammaEvidenceStatus: 'unavailable',
        observationOnly: true,
        decisionGrade: false,
        missingEvidence: [],
        blockedReasonCodes: [],
      },
      cockpitSummary: {
        whatChanged: ['广度改善'],
        whatToWatch: [],
        confidenceLimits: [],
      },
      noAdviceDisclosure: '仅供研究语境参考。',
      dataQuality: { status: 'degraded' },
    });
    getDailyIntelligenceMock.mockRejectedValue(new Error('briefing unavailable'));

    renderRoute(<MarketDecisionCockpitPage />, '/zh/market/decision-cockpit');

    const page = await screen.findByTestId('market-decision-cockpit-page');
    const dailyBriefing = await screen.findByTestId('daily-intelligence-briefing');
    await within(dailyBriefing).findByText('请求失败');
    expect(dailyBriefing).toHaveTextContent('请求未成功完成，请稍后重试。');
    expect(page).toHaveTextContent('市场结构、定位语境与研究队列');
    expect(page).toHaveTextContent('驱动评分');
  });

  it('uses product-ready read model as the first-viewport primary market context', async () => {
    getDecisionCockpitMock.mockResolvedValue({
      schemaVersion: 'market_decision_cockpit.v1',
      generatedAt: '2026-06-15T09:30:00Z',
      marketRegimeReadModel: {
        available: true,
        primaryContext: true,
        readinessLabel: 'product_ready',
        status: 'ok',
        regimeLabel: 'risk_off',
        summary: 'Risk-off evidence is currently dominant across the bounded read model.',
        evidenceCards: [
          { id: 'benchmark_trend', title: 'Benchmark Trend', status: 'negative', headline: 'Benchmark trend evidence is negative.' },
          { id: 'breadth', title: 'Breadth', status: 'negative', headline: 'Breadth evidence is weak.' },
        ],
      },
      marketRegimeDecision: {
        regime: 'risk_off',
        confidence: 'medium',
        driverScores: {},
        explanation: {
          whyThisRegime: ['Risk-off evidence is currently dominant across the bounded read model.'],
          whatConfirmsIt: ['Benchmark trend evidence is negative.'],
          whatInvalidatesIt: [],
        },
        invalidationConditions: [],
        researchPriorities: {
          watchToday: ['Monitor Market Regime Read Model evidence freshness.'],
          needsMoreEvidence: [],
          investigateNext: [],
        },
      },
      researchQueuePreview: {
        topCandidates: [],
        queueQuality: 'thin',
        evidenceGaps: [],
        previewOnly: true,
      },
      optionsStructureStatus: {
        gammaEvidenceStatus: 'unavailable',
        observationOnly: true,
        decisionGrade: false,
        missingEvidence: [],
        blockedReasonCodes: ['Secondary options structure evidence unavailable'],
      },
      cockpitSummary: {
        whatChanged: ['Market Regime Read Model is product-ready: Risk-off observation.'],
        whyItMatters: ['This cockpit keeps regime, research triage, and options observation in one read-only view.'],
        whatToWatch: ['Monitor Market Regime Read Model evidence freshness.'],
        confidenceLimits: ['Advanced evidence observation-only'],
      },
      degradedInputs: [
        {
          section: 'scenarioRisks',
          status: 'unavailable',
          reason: 'Secondary options structure evidence is unavailable.',
        },
      ],
      noAdviceDisclosure: '仅供研究语境参考。',
      dataQuality: {
        status: 'ready',
        reasonCodes: ['Secondary options structure evidence unavailable'],
        primaryReadModelReady: true,
        advancedEvidenceStatus: 'secondary_unavailable',
      },
    });
    getDailyIntelligenceMock.mockRejectedValue(new Error('briefing unavailable'));

    renderRoute(<MarketDecisionCockpitPage />, '/zh/market/decision-cockpit');

    const page = await screen.findByTestId('market-decision-cockpit-page');
    const firstViewport = await within(page).findByTestId('decision-cockpit-first-viewport-summary');

    expect(firstViewport).toHaveTextContent('当前状态');
    expect(firstViewport).toHaveTextContent('风险规避观察');
    expect(firstViewport).toHaveTextContent('信心等级 · 中');
    expect(firstViewport).toHaveTextContent('Risk-off evidence is currently dominant across the bounded read model.');
    expect(firstViewport).toHaveTextContent('主市场状态语境：风险规避观察 · 产品可用');
    const evidenceStrip = within(firstViewport).getByTestId('decision-cockpit-key-evidence-strip');
    expect(evidenceStrip).toHaveTextContent('趋势');
    expect(evidenceStrip).toHaveTextContent('广度');
    expect(evidenceStrip).toHaveTextContent('波动 / 风险');
    expect(firstViewport).toHaveTextContent('次级高级证据缺口');
    expect(firstViewport).toHaveTextContent('Secondary options structure evidence is unavailable.');
    expect(firstViewport).toHaveTextContent('研究观察，不构成投资建议。');
    expect((page.textContent || '').match(/不构成投资建议/g)?.length).toBe(1);
    const diagnostics = within(page).getByTestId('decision-cockpit-diagnostics-disclosure');
    expect(diagnostics).not.toHaveAttribute('open');
    expect(firstViewport).not.toHaveTextContent('低置信观察');
  });

  it('renders a compact consumer-safe cockpit narrative for blocked and low-confidence drivers', async () => {
    getDecisionCockpitMock.mockResolvedValue({
      schemaVersion: 'market_decision_cockpit.v1',
      generatedAt: '2026-06-15T09:30:00Z',
      marketRegimeDecision: {
        regime: 'lowConfidence',
        confidence: 'low',
        confidenceScore: 0.18,
        driverScores: {
          dealerGamma: { score: 0, evidenceState: 'unavailable' },
          breadthParticipation: { score: 0, evidenceState: 'blocked' },
          volatilityStructure: { score: 0, evidenceState: 'provider_timeout', reasons: ['provider_runtime_debug'] },
          ratesDollar: { score: 57, evidenceState: 'score_grade' },
          liquidityCredit: { score: 31, evidenceState: 'partial' },
          eventCatalyst: { score: 0, evidenceState: 'raw_backend_reason_code' },
        },
        explanation: {
          whyThisRegime: ['low_confidence_internal_reason'],
          whatConfirmsIt: ['ratesDollar score_grade evidence'],
          whatInvalidatesIt: ['provider_timeout'],
        },
        invalidationConditions: ['provider_runtime_debug'],
        researchPriorities: {
          watchToday: ['buy now if score improves'],
          needsMoreEvidence: ['provider_timeout', 'raw_backend_reason_code'],
          investigateNext: ['sell stop target should never render'],
        },
      },
      researchQueuePreview: {
        topCandidates: [],
        queueQuality: 'thin',
        evidenceGaps: ['provider_timeout'],
        previewOnly: true,
      },
      optionsStructureStatus: {
        gammaEvidenceStatus: 'unavailable',
        observationOnly: true,
        decisionGrade: false,
        missingEvidence: [{ code: 'missing_contracts' }],
        blockedReasonCodes: ['option_chain_unavailable'],
      },
      cockpitSummary: {
        whatChanged: [],
        whyItMatters: [],
        whatToWatch: ['buy now if score improves'],
        confidenceLimits: ['provider_timeout'],
      },
      noAdviceDisclosure: '仅供研究语境参考。',
      dataQuality: {
        status: 'failed_closed',
        reason: 'quote snapshot provider error',
        reasonCodes: ['provider_timeout'],
        freshness: 'stale',
        asOf: '2026-06-15T09:25:00Z',
        blockingModules: ['Decision Cockpit'],
        operatorAction: 'Refresh quote snapshot pipeline before rerun.',
        consumerSafeMessage: '关键市场证据暂不可用，驾驶舱保持关闭。',
      },
    });
    getDailyIntelligenceMock.mockRejectedValue(new Error('briefing unavailable'));

    renderRoute(<MarketDecisionCockpitPage />, '/zh/market/decision-cockpit');

    const page = await screen.findByTestId('market-decision-cockpit-page');
    const firstViewport = await within(page).findByTestId('decision-cockpit-first-viewport-summary');
    const readinessSummary = within(firstViewport).getByTestId('decision-cockpit-readiness-summary');
    expect(readinessSummary).toHaveTextContent('已安全关闭');
    expect(readinessSummary).toHaveTextContent('数据管道维护中');
    expect(firstViewport).toHaveTextContent('关键市场证据暂不可用，驾驶舱保持关闭。');
    expect(firstViewport.textContent || '').not.toMatch(/quote snapshot|provider error|pipeline|operatorAction|failed_closed/i);
    const narrative = await within(page).findByTestId('market-cockpit-narrative');
    expect(narrative).toHaveTextContent('当前市场状态仍处于低置信观察区间');
    expect(narrative).toHaveTextContent('多数驱动项缺少可评分证据');
    expect(narrative).toHaveTextContent('可用证据主要来自利率与美元');
    expect(narrative).toHaveTextContent('Gamma 观察、广度参与、波动结构');
    expect(narrative).toHaveTextContent('研究优先级线索');
    expect(page).toHaveTextContent('可评分证据');
    expect(page).toHaveTextContent('证据暂不可用');
    expect(narrative.textContent || '').not.toMatch(/provider_timeout|raw_backend_reason_code|score_grade|provider_runtime_debug|schema|debug|trace/i);
    expect(narrative.textContent || '').not.toMatch(/买入|卖出|下单|目标价|止损|仓位建议/);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/provider_timeout|raw_backend_reason_code|score_grade|provider_runtime_debug|low_confidence_internal_reason|schema|debug|trace/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/buy now|sell stop|买入|卖出|下单|目标价|止损|仓位建议/i);
    expect(findConsumerRawLeakage(narrative.textContent || '')).toEqual([]);
  });

  it('maps evidence limited cockpit status to consumer-safe wording', async () => {
    getDecisionCockpitMock.mockResolvedValue({
      schemaVersion: 'market_decision_cockpit.v1',
      generatedAt: '2026-06-15T09:30:00Z',
      marketRegimeDecision: {
        regime: 'neutral',
        confidence: 'medium',
        confidenceScore: 0.44,
        driverScores: {
          dealerGamma: { score: 41, evidenceState: 'evidence limited', reasons: [] },
          breadthParticipation: { score: 0, evidenceState: 'unavailable', reasons: [] },
          volatilityStructure: { score: 29, evidenceState: 'partial', reasons: [] },
          ratesDollar: { score: 26, evidenceState: 'score_grade', reasons: [] },
          liquidityCredit: { score: 14, evidenceState: 'partial', reasons: [] },
          crossAssetRisk: { score: 0, evidenceState: 'blocked', reasons: [] },
          sectorThemeRotation: { score: 0, evidenceState: 'evidence limited', reasons: [] },
          eventCatalyst: { score: 0, evidenceState: 'pending', reasons: [] },
        },
        explanation: {
          whyThisRegime: [],
          whatConfirmsIt: [],
          whatInvalidatesIt: [],
        },
        invalidationConditions: [],
        researchPriorities: {
          watchToday: [],
          needsMoreEvidence: [],
          investigateNext: [],
        },
      },
      researchQueuePreview: {
        topCandidates: [],
        queueQuality: 'thin',
        evidenceGaps: [],
        previewOnly: true,
      },
      optionsStructureStatus: {
        gammaEvidenceStatus: 'partial',
        observationOnly: true,
        decisionGrade: false,
        missingEvidence: [],
        blockedReasonCodes: [],
      },
      cockpitSummary: {
        whatChanged: [],
        whyItMatters: [],
        whatToWatch: [],
        confidenceLimits: [],
      },
      noAdviceDisclosure: '仅供研究语境参考。',
      dataQuality: {
        status: 'evidence limited',
        reason: 'evidence limited',
        reasonCodes: [],
        freshness: 'stale',
        asOf: '2026-06-15T09:25:00Z',
        blockingModules: [],
        operatorAction: '',
        consumerSafeMessage: '关键市场证据仍待补齐，驾驶舱保持观察边界。',
      },
    });
    getDailyIntelligenceMock.mockRejectedValue(new Error('briefing unavailable'));

    renderRoute(<MarketDecisionCockpitPage />, '/zh/market/decision-cockpit');

    const page = await screen.findByTestId('market-decision-cockpit-page');
    expect(page).toHaveTextContent('证据仍待补');
    expect(page).not.toHaveTextContent('evidence limited');
    expect(findConsumerRawLeakage(page.textContent || '')).toEqual([]);
  });

  it('keeps the cockpit first viewport mobile-safe at 390px with wrapped readiness and evidence copy', async () => {
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 390 });
    window.dispatchEvent(new Event('resize'));
    getDecisionCockpitMock.mockResolvedValue({
      schemaVersion: 'market_decision_cockpit.v1',
      generatedAt: '2026-06-15T09:30:00Z',
      marketRegimeDecision: {
        regime: 'neutral',
        confidence: 'medium',
        driverScores: {
          breadthParticipation: { score: 52, evidenceState: 'partial' },
        },
        explanation: {
          whyThisRegime: ['横向等待更多确认'],
        },
        invalidationConditions: ['广度明显收窄'],
        researchPriorities: {
          watchToday: ['先核对市场广度是否继续改善'],
          needsMoreEvidence: ['期权链观察仍待补齐'],
          investigateNext: ['确认跨资产压力是否同步缓和'],
        },
      },
      researchQueuePreview: {
        topCandidates: [],
        queueQuality: 'thin',
        evidenceGaps: ['research_candidates_unavailable'],
        previewOnly: true,
      },
      optionsStructureStatus: {
        gammaEvidenceStatus: 'unavailable',
        observationOnly: true,
        decisionGrade: false,
        missingEvidence: [{ code: 'missing_contracts' }],
        blockedReasonCodes: ['option_chain_unavailable'],
      },
      cockpitSummary: {
        whatChanged: ['市场仍在等待更完整确认。'],
        whyItMatters: ['当前更适合先看结构再继续深入。'],
        whatToWatch: ['确认广度、利率与美元是否同步改善。'],
        confidenceLimits: ['期权与更深层市场证据暂未补齐。'],
      },
      noAdviceDisclosure: '仅供研究语境参考。',
      dataQuality: {
        status: 'degraded',
        reasonCodes: ['delayed'],
        blockingModules: [],
        consumerSafeMessage: '当前市场证据部分待补，先按观察路径阅读。',
      },
    });
    getDailyIntelligenceMock.mockResolvedValue({
      schemaVersion: 'daily_intelligence_briefing_v1',
      generatedAt: '2026-06-15T09:30:00Z',
      briefingDate: '2026-06-15',
      sessionLabel: 'pre-market',
      marketRegimeSummary: {
        regime: 'neutral',
        confidence: 'medium',
        summary: '市场维持中性观察。',
        supportingObservations: ['广度与流动性仍需继续确认。'],
        invalidationObservations: [],
      },
      whatChanged: ['市场暂未形成更明确主线。'],
      sectionLinks: [],
      topResearchPriorities: [],
      scannerHighlights: [],
      watchlistHighlights: [],
      portfolioStructureHighlights: [],
      scenarioRisks: [],
      evidenceGaps: [],
      degradedInputs: [],
      firstRunChecklist: [],
      starterResearchWorkflow: [],
    });

    renderRoute(<MarketDecisionCockpitPage />, '/zh/market/decision-cockpit');

    const firstViewport = await screen.findByTestId('decision-cockpit-first-viewport-summary');
    expect(screen.getByTestId('decision-cockpit-readiness-summary')).toHaveClass('break-words');
    expect(screen.getByTestId('decision-cockpit-key-evidence-strip')).toHaveClass('grid-cols-1');
    expect(screen.getByTestId('decision-cockpit-missing-summary')).toHaveClass('break-words');
    expect(screen.getByTestId('decision-cockpit-summary-headline')).toHaveClass('break-words');
    expect(firstViewport).toHaveTextContent('研究观察，不构成投资建议。');
  });

  it('keeps partial cockpit evidence narrative visible instead of placeholder-only side rail copy', async () => {
    getDecisionCockpitMock.mockResolvedValue({
      schemaVersion: 'market_decision_cockpit.v1',
      generatedAt: '2026-06-15T09:30:00Z',
      marketRegimeDecision: {
        regime: 'neutral',
        confidence: 'lowConfidence',
        confidenceScore: 0.31,
        driverScores: {
          dealerGamma: { score: 0, evidenceState: 'proxy-only' },
          breadthParticipation: { score: 49, evidenceState: 'stale' },
          volatilityStructure: { score: 0, evidenceState: 'freshness=unavailable' },
          liquidityCredit: { score: 22, evidenceState: 'pending' },
        },
        explanation: {
          whyThisRegime: [],
          whatConfirmsIt: [],
          whatInvalidatesIt: [],
        },
        invalidationConditions: [],
        researchPriorities: {
          watchToday: [],
          needsMoreEvidence: [],
          investigateNext: [],
        },
      },
      researchQueuePreview: {
        topCandidates: [],
        queueQuality: 'pending-heavy',
        evidenceGaps: ['proxy-only', 'freshness=unavailable'],
        previewOnly: true,
      },
      optionsStructureStatus: {
        gammaEvidenceStatus: 'proxy-only',
        observationOnly: true,
        decisionGrade: false,
        missingEvidence: [],
        blockedReasonCodes: ['pending'],
      },
      cockpitSummary: {
        whatChanged: [],
        whyItMatters: [],
        whatToWatch: [],
        confidenceLimits: [],
      },
      noAdviceDisclosure: '仅供研究语境参考。',
      dataQuality: { status: 'stale', reasonCodes: ['freshness=unavailable'] },
    });
    getDailyIntelligenceMock.mockRejectedValue(new Error('briefing unavailable'));

    renderRoute(<MarketDecisionCockpitPage />, '/zh/market/decision-cockpit');

    const page = await screen.findByTestId('market-decision-cockpit-page');
    const narrative = await within(page).findByTestId('market-cockpit-narrative');

    expect(narrative).toHaveTextContent('当前市场状态');
    expect(page).toHaveTextContent('数据可能已过期');
    expect(page).toHaveTextContent('间接参考，证据强度受限');
    expect(page).toHaveTextContent('正在等待数据确认');
    expect(page).toHaveTextContent('数据新鲜度暂不可用');
    expect(page).not.toHaveTextContent('暂未整理变化摘要');
    expect(page).not.toHaveTextContent('暂未整理明确的置信边界');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/proxy-only|pending-heavy|freshness=unavailable|score-grade|score_grade|provider|runtime|debug|traceId|requestId|schemaVersion/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位建议|加仓|减仓/i);
  });

  it('renders Research Radar as the core queue and links queue rows to Stock Structure', async () => {
    getResearchRadarMock.mockResolvedValue({
      schemaVersion: 'research_radar_api_v1',
      generatedAt: '2026-06-15T09:30:00Z',
      researchQueue: [
        {
          ticker: 'ALFA',
          priority: 'medium',
          researchBias: 'strengthContinuation',
          driverScores: { relativeStrength: 70 },
          whyOnRadar: [
            'Relative strength is above the research threshold',
            'Evidence quality is acceptable',
            'Evidence missing',
          ],
          whatToVerify: ['观察延续性'],
          invalidationObservations: ['强弱回落'],
          riskFlags: [],
        },
      ],
      aggregateSummary: {
        queueQuality: 'mixed',
        priorityCounts: { medium: 1 },
      },
      evidenceGaps: [],
      marketContextFit: 'neutral',
      onboardingGuidance: {
        title: 'Start a research loop',
        summary: 'Use Market Overview, Watchlist, Scanner, and Research Radar to build an observation-only research loop.',
        conditionsDetected: ['Research Radar has no queue items yet.'],
      },
      emptyStateActions: [
        {
          label: 'Start with Market Overview',
          route: '/market-overview',
          description: 'Read market context first.',
        },
        {
          label: 'Run Scanner',
          route: '/scanner',
          description: 'Create candidates before reviewing the radar.',
        },
        {
          label: 'Add Watchlist Symbol',
          route: '/watchlist',
          description: 'Choose a symbol to observe.',
        },
      ],
      starterResearchWorkflow: ['Open Market Overview.', 'Run Scanner.', 'Return to Research Radar.'],
      firstRunChecklist: ['Market context reviewed.', 'Scanner activity reviewed.'],
      suggestedResearchEntrypoints: [
        { surface: 'Market Overview', route: '/market-overview', description: 'Start with broad context.' },
        { surface: 'Scanner', route: '/scanner', description: 'Build a candidate queue.' },
      ],
      noAdviceDisclosure: '仅供研究队列观察。',
      dataQuality: { status: 'partial' },
      evidenceHub: {
        scannerCandidates: {
          key: 'scanner',
          label: 'Scanner candidates',
          status: 'available',
          summary: 'Scanner candidate evidence is available for radar review.',
          nextDataAction: 'Refresh scanner when candidate evidence needs a newer observation window.',
          evidenceCount: 1,
          totalCount: 1,
          symbols: ['ALFA'],
          details: ['ALFA is available for radar review.'],
          observationOnly: true,
          decisionGrade: false,
        },
        backtestSamples: {
          key: 'backtest',
          label: 'Backtest samples',
          status: 'blocked',
          summary: 'Backtest samples are unavailable for radar symbols.',
          blocker: 'Backtest samples have not been prepared for the radar symbols.',
          nextDataAction: 'Open Backtest and prepare or refresh samples for the radar symbols.',
          evidenceCount: 0,
          totalCount: 1,
          symbols: ['ALFA'],
          details: ['ALFA has no prepared backtest samples.'],
          observationOnly: true,
          decisionGrade: false,
        },
        stockReadiness: {
          key: 'stock',
          label: 'Stock readiness',
          status: 'available',
          summary: 'Stock technical readiness is available for radar symbols.',
          nextDataAction: 'Refresh daily price history and technical evidence for radar symbols.',
          evidenceCount: 1,
          totalCount: 1,
          symbols: ['ALFA'],
          details: ['ALFA has technical readiness evidence.'],
          observationOnly: true,
          decisionGrade: false,
        },
        dataActivation: {
          key: 'data',
          label: 'Data activation',
          status: 'partial',
          summary: 'Research Radar evidence is partially activated.',
          blocker: 'Backtest samples have not been prepared for the radar symbols.',
          nextDataAction: 'Resolve blocked evidence slices, then refresh Research Radar.',
          evidenceCount: 2,
          totalCount: 3,
          details: [
            'Scanner candidates status available.',
            'Backtest samples status blocked.',
            'Stock readiness status available.',
          ],
          observationOnly: true,
          decisionGrade: false,
        },
        missingEvidenceStates: [
          {
            key: 'backtest',
            label: 'Backtest samples',
            status: 'blocked',
            summary: 'Backtest samples are unavailable for radar symbols.',
            blocker: 'Backtest samples have not been prepared for the radar symbols.',
            nextDataAction: 'Open Backtest and prepare or refresh samples for the radar symbols.',
            evidenceCount: 0,
            totalCount: 1,
            symbols: ['ALFA'],
            details: ['ALFA has no prepared backtest samples.'],
            observationOnly: true,
            decisionGrade: false,
          },
          {
            key: 'data',
            label: 'Data activation',
            status: 'partial',
            summary: 'Research Radar evidence is partially activated.',
            blocker: 'Backtest samples have not been prepared for the radar symbols.',
            nextDataAction: 'Resolve blocked evidence slices, then refresh Research Radar.',
            evidenceCount: 2,
            totalCount: 3,
            details: ['Backtest samples status blocked.'],
            observationOnly: true,
            decisionGrade: false,
          },
        ],
      },
      marketLevelFallback: {
        available: true,
        label: 'Market-level context',
        summary: 'Market-level evidence stays available while candidate rows are present.',
        candidateGenerationExecuted: false,
        regime: { label: 'neutral', status: 'partial' },
        productSummary: 'Market-level evidence is secondary when the candidate queue has rows.',
        evidenceCards: [
          {
            cardId: 'growth_risk_proxy',
            title: 'Growth Risk Proxy',
            status: 'unavailable',
            severity: 'warning',
            headline: 'Growth proxy evidence is unavailable.',
            reasons: ['growth proxy missing'],
          },
          {
            cardId: 'breadth',
            title: 'Breadth',
            status: 'unavailable',
            severity: 'warning',
            headline: 'Breadth evidence is unavailable.',
            reasons: ['breadth missing'],
          },
          {
            cardId: 'research_queue_freshness',
            title: 'Freshness',
            status: 'stale',
            severity: 'warning',
            headline: 'Freshness is constrained for this observation.',
            reasons: ['freshness constrained'],
          },
        ],
        missingDataFamilies: [],
        blockedProductSurfaces: [],
        nextOperatorAction: 'Use candidate rows first, then review market context if needed.',
        observationOnly: true,
        decisionGrade: false,
      },
    });
    getResearchQueueMock.mockResolvedValue({
      schemaVersion: 'research_queue_v1',
      researchQueue: [
        {
          queueItemId: 'watchlist-MSFT-item-1',
          sourceSurface: 'watchlist',
          symbol: 'MSFT',
          title: 'Watchlist evidence follow-up',
          priorityTier: 'urgent_review',
          whyQueued: ['Evidence missing', 'Low-evidence filter active', 'provider_timeout'],
          evidenceUsed: ['Evidence quality is acceptable', 'Relative strength is above the research threshold', 'sourceRefs'],
          evidenceGaps: ['benchmark_missing', 'reasonCodes'],
          freshness: { state: 'needs_review', lastReviewedAt: null },
          suggestedResearchPath: [
            {
              label: 'Stock Structure',
              route: '/stocks/MSFT/structure-decision',
              section: 'watchlistResearchOverlay',
              reason: 'Open symbol structure detail.',
            },
            {
              label: 'Admin Diagnostics',
              route: '/admin/provider-operations',
              section: 'adminDiagnostics',
              reason: 'provider_runtime_trace',
            },
          ],
          observationOnly: true,
        },
        {
          queueItemId: 'scanner-ALFA-run-42-rank-1-item-1',
          sourceSurface: 'scanner',
          symbol: 'ALFA',
          title: 'Scanner candidate review',
          priorityTier: 'follow_up',
          whyQueued: ['Scanner candidate is available for follow-up research review.'],
          evidenceUsed: ['Technicals available', 'Liquidity available'],
          evidenceGaps: [],
          freshness: { state: 'current', lastReviewedAt: '2026-06-15T09:30:00+00:00' },
          suggestedResearchPath: [
            {
              label: 'Stock Structure',
              route: '/stocks/ALFA/structure-decision',
              section: 'scannerResearchOverlay',
              reason: 'Open symbol structure detail.',
            },
          ],
          observationOnly: true,
        },
        {
          queueItemId: 'market-VIX-item-1',
          sourceSurface: 'market',
          symbol: 'VIX',
          title: 'Market volatility context',
          priorityTier: 'monitor',
          whyQueued: ['Cross-surface evidence should be reviewed before extending the queue.'],
          evidenceUsed: ['Market context available'],
          evidenceGaps: ['price_history_stale', 'provider_runtime_trace'],
          freshness: { state: 'unknown', lastReviewedAt: null },
          suggestedResearchPath: [],
          observationOnly: true,
        },
      ],
      aggregateSummary: {
        itemCount: 3,
        limit: 5,
        bounded: false,
        bySourceSurface: { watchlist: 1, scanner: 1, market: 1 },
        byPriorityTier: { urgent_review: 1, follow_up: 1, monitor: 1 },
      },
      sourceSurfacesAggregated: ['watchlist', 'scanner', 'market'],
      evidenceGaps: ['benchmark_missing', 'price_history_stale', 'provider_runtime_trace'],
      dataQuality: {
        state: 'ready',
        itemCount: 3,
        sourceSurfacesAvailable: ['watchlist', 'scanner', 'market'],
        sourceSurfacesExpected: ['scanner', 'watchlist', 'market', 'manual_gap'],
        failClosed: true,
      },
      noAdviceDisclosure: 'Research-only queue; verify evidence gaps before further review.',
      observationOnly: true,
      decisionGrade: false,
    });

    renderRoute(<ResearchRadarPage />, '/zh/research/radar?market=us&limit=5');

    const page = await screen.findByTestId('research-radar-page');
    expect(within(page).queryByTestId('observation-only-boundary')).not.toBeInTheDocument();
    expect(page).toHaveTextContent('今日观察队列');
    expect(page).not.toHaveTextContent('研究情景工作台');
    const overview = await within(page).findByTestId('research-radar-consumer-overview');
    expect(overview).toHaveAttribute(
      'data-discovery-sequence',
      'candidate-queue>selected-detail>factor>limitation>next-check>comparison-ledger',
    );
    expect(overview).toHaveTextContent('观察候选');
    expect(overview).toHaveTextContent('证据质量分布');
    expect(overview).toHaveTextContent('队列健康');
    expect(overview).toHaveTextContent('研究观察，不构成投资建议。');
    expect((overview.textContent || '').match(/不构成投资建议/g)?.length).toBe(1);
    expect(within(overview).getByTestId('research-radar-candidate-ledger')).toBeInTheDocument();
    expect(within(overview).getByTestId('research-radar-candidate-ledger').getAttribute('data-discovery-role') || '').toContain('comparison-ledger');
    const candidate = within(overview).getByTestId('research-radar-candidate-ALFA');
    expect(candidate).toHaveTextContent('ALFA');
    expect(candidate).toHaveTextContent('相对强弱已达到研究阈值');
    expect(candidate).toHaveTextContent('观察延续性');
    const ledger = within(overview).getByTestId('research-radar-candidate-ledger');
    expect(ledger).toHaveTextContent('限制');
    expect(ledger).toHaveTextContent('下一步检查');
    const selectedCandidate = within(overview).getByTestId('research-radar-selected-candidate-detail');
    expect(selectedCandidate).toHaveAttribute('data-discovery-role', 'selected-candidate-detail');
    expect(selectedCandidate).toHaveTextContent('当前研究观察');
    expect(selectedCandidate).toHaveTextContent('因子贡献');
    expect(selectedCandidate).toHaveTextContent('相对强弱');
    expect(selectedCandidate).toHaveTextContent('限制 / 风险');
    expect(selectedCandidate).toHaveTextContent('数据时效');
    expect(selectedCandidate).toHaveTextContent('下一步研究检查');
    expect(within(selectedCandidate).getByTestId('research-radar-factor-section')).toHaveAttribute('data-module-density', 'compact');
    expect(within(selectedCandidate).getByTestId('research-radar-factor-bars')).toHaveTextContent('70');
    expect(within(selectedCandidate).getByRole('link', { name: '查看个股研究' })).toHaveAttribute('href', expect.stringContaining('/zh/stocks/ALFA/structure-decision'));
    expect(within(selectedCandidate).getByRole('link', { name: '查看个股研究' })).toHaveAttribute('href', expect.stringContaining('source=scanner'));
    expect(within(selectedCandidate).getByRole('link', { name: '打开观察列表视图' })).toHaveAttribute('href', expect.stringContaining('/zh/watchlist?'));
    expect(within(selectedCandidate).getByRole('link', { name: '打开观察列表视图' })).toHaveAttribute('href', expect.stringContaining('symbol=ALFA'));
    expect(within(selectedCandidate).getByRole('link', { name: '打开观察列表视图' })).toHaveAttribute('href', expect.stringContaining('market=US'));
    expect(within(selectedCandidate).getByRole('link', { name: '打开观察列表视图' })).toHaveAttribute('href', expect.stringContaining('source=scanner'));
    const diagnostics = within(page).getByTestId('research-radar-diagnostics-disclosure');
    expect(diagnostics).not.toHaveAttribute('open');
    expect(diagnostics).toHaveTextContent('查看详细证据与数据就绪');
    const secondaryFallback = within(diagnostics).getByTestId('research-radar-market-level-fallback');
    expect(secondaryFallback).toHaveTextContent('Market-level evidence is secondary when the candidate queue has rows.');
    const evidenceHub = await within(page).findByTestId('research-radar-evidence-hub');
    expect(evidenceHub).toHaveTextContent('真实证据就绪状态');
    expect(evidenceHub).toHaveTextContent('扫描候选');
    expect(evidenceHub).toHaveTextContent('回测样本');
    expect(evidenceHub).toHaveTextContent('个股就绪');
    expect(evidenceHub).toHaveTextContent('数据激活');
    expect(evidenceHub).toHaveTextContent('Backtest samples have not been prepared for the radar symbols.');
    expect(evidenceHub).toHaveTextContent('Open Backtest and prepare or refresh samples for the radar symbols.');
    expect(evidenceHub).toHaveTextContent('缺失证据状态');
    expect(evidenceHub.textContent || '').not.toMatch(/provider|request[_\s-]?id|trace[_\s-]?id|raw|debug|runtime|cache|schemaVersion|token|stack/i);
    expect(evidenceHub.textContent || '').not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位建议|buy|sell|hold|recommend(?:ation)?|target price|stop loss|position sizing/i);
    const hub = await within(page).findByTestId('research-queue-hub');
    expect(hub).toHaveTextContent('跨页面研究队列');
    expect(hub).toHaveTextContent('观察列表');
    expect(hub).toHaveTextContent('扫描器');
    expect(hub).toHaveTextContent('市场背景');
    const watchlistGroup = within(hub).getByTestId('research-queue-source-watchlist');
    expect(watchlistGroup).toHaveTextContent('MSFT');
    expect(watchlistGroup).toHaveTextContent('Watchlist evidence follow-up');
    expect(watchlistGroup).toHaveTextContent('紧急复核');
    expect(watchlistGroup).toHaveTextContent('证据不足');
    expect(watchlistGroup).toHaveTextContent('当前按低证据条件整理');
    expect(watchlistGroup).toHaveTextContent('证据质量可供继续观察');
    expect(watchlistGroup).toHaveTextContent('相对强弱已达到研究阈值');
    expect(watchlistGroup).toHaveTextContent('基准证据缺失');
    expect(watchlistGroup).toHaveTextContent('缺少基准或指数参照时，相对强弱和结构延续性只能作为线索。');
    expect(watchlistGroup).toHaveTextContent('先补充同周期基准表现，再比较标的与市场的相对变化。');
    expect(watchlistGroup).toHaveTextContent('置信度受限：相对判断需要降级为观察线索。');
    expect(watchlistGroup).toHaveTextContent('仅作观察，不构成操作结论。');
    expect(watchlistGroup).toHaveTextContent('需复核');
    expect(watchlistGroup).toHaveTextContent('仅作观察');
    expect(within(watchlistGroup).getByRole('link', { name: /Stock Structure/i })).toHaveAttribute('href', '/zh/stocks/MSFT/structure-decision');
    expect(within(watchlistGroup).queryByRole('link', { name: /Admin Diagnostics/i })).not.toBeInTheDocument();
    expect(watchlistGroup.textContent || '').not.toMatch(/Admin Diagnostics|adminDiagnostics|provider_runtime_trace|\/admin/i);
    expect(within(hub).getByTestId('research-queue-source-scanner')).toHaveTextContent('ALFA');
    const marketGroup = within(hub).getByTestId('research-queue-source-market');
    expect(marketGroup).toHaveTextContent('VIX');
    expect(marketGroup).toHaveTextContent('价格历史时效有限');
    expect(marketGroup).toHaveTextContent('部分证据暂不可用，因此当前结论只适合作为观察线索。');
    expect((await within(page).findAllByText('ALFA')).length).toBeGreaterThan(0);
    await waitFor(() => expect(getResearchRadarMock).toHaveBeenCalledWith({ market: 'us', profile: undefined, limit: 5 }));
    await waitFor(() => expect(getResearchQueueMock).toHaveBeenCalledWith({ market: 'us', profile: undefined, queueLimit: 5 }));
    const healthSummary = within(page).getByTestId('research-radar-data-health-summary');
    expect(healthSummary).toHaveTextContent('数据健康');
    expect(healthSummary).toHaveTextContent('市场广度');
    expect(healthSummary).toHaveTextContent('个股证据');
    expect(healthSummary).toHaveTextContent('研究队列时效');
    expect(healthSummary).toHaveTextContent('部分可用');
    expect(healthSummary).toHaveTextContent('已延迟');
    expect(healthSummary).toHaveTextContent('队列时效影响后续复核顺序。');
    expect(healthSummary).not.toHaveTextContent('Growth proxy evidence is unavailable.');
    expect(healthSummary).not.toHaveTextContent('Breadth evidence is unavailable.');
    expect(healthSummary).not.toHaveTextContent('Freshness is constrained for this observation.');
    expect(healthSummary).toHaveTextContent('成长风险观察证据暂不可用。');
    expect(healthSummary).toHaveTextContent('市场广度证据暂不可用。');
    expect(healthSummary).toHaveTextContent('数据新鲜度受限，当前仅供观察。');
    expect(healthSummary.textContent || '').not.toMatch(/sourceRefs|reasonCodes|provider_timeout|optional_news_timeout|benchmark_missing|price_history_stale|provider_runtime_trace|queueItemId|request[_\s-]?id|trace[_\s-]?id|raw|debug|runtime|cache|schemaVersion/i);
    expect(findConsumerRawLeakage(healthSummary.textContent || '')).toEqual([]);
    expect(healthSummary.textContent || '').not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位建议|buy|sell|hold|recommend(?:ation)?|target price|stop loss|position sizing/i);
    expect(hub.textContent || '').not.toMatch(/sourceRefs|reasonCodes|provider_timeout|optional_news_timeout|benchmark_missing|price_history_stale|provider_runtime_trace|queueItemId|request[_\s-]?id|trace[_\s-]?id|raw|debug|runtime|cache|schemaVersion|Evidence missing|Evidence quality is acceptable|Low-evidence filter active|Relative strength is above the research threshold/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/Evidence missing|Evidence quality is acceptable|Low-evidence filter active|Relative strength is above the research threshold/i);
    expect(findConsumerRawLeakage(hub.textContent || '')).toEqual([]);
    expect(hub.textContent || '').not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位建议|buy|sell|hold|recommend(?:ation)?|target price|stop loss|position sizing/i);
  });

  it('fails closed when the unified queue contract is not observation-only', async () => {
    getResearchRadarMock.mockResolvedValue({
      schemaVersion: 'research_radar_api_v1',
      generatedAt: '2026-06-15T09:30:00Z',
      researchQueue: [],
      aggregateSummary: {
        queueQuality: 'thin',
        priorityCounts: {},
      },
      evidenceGaps: [],
      marketContextFit: 'neutral',
      onboardingGuidance: null,
      emptyStateActions: [],
      starterResearchWorkflow: [],
      firstRunChecklist: [],
      suggestedResearchEntrypoints: [],
      noAdviceDisclosure: '仅供研究队列观察。',
      dataQuality: { status: 'partial' },
    });
    getResearchQueueMock.mockResolvedValue({
      schemaVersion: 'research_queue_v1',
      researchQueue: [
        {
          queueItemId: 'unsafe-NVDA-item-1',
          sourceSurface: 'scanner',
          symbol: 'NVDA',
          title: 'Unsafe decision grade queue',
          priorityTier: 'urgent_review',
          whyQueued: ['Unsafe queue should not render.'],
          evidenceUsed: ['Technicals available'],
          evidenceGaps: [],
          freshness: { state: 'current', lastReviewedAt: null },
          suggestedResearchPath: [],
          observationOnly: false,
        },
      ],
      aggregateSummary: {
        itemCount: 1,
        limit: 5,
        bounded: false,
        bySourceSurface: { scanner: 1 },
        byPriorityTier: { urgent_review: 1, follow_up: 0, monitor: 0 },
      },
      sourceSurfacesAggregated: ['scanner'],
      evidenceGaps: [],
      dataQuality: {
        state: 'ready',
        itemCount: 1,
        sourceSurfacesAvailable: ['scanner'],
        sourceSurfacesExpected: ['scanner', 'watchlist', 'market', 'manual_gap'],
        failClosed: false,
      },
      noAdviceDisclosure: 'Research-only queue.',
      observationOnly: false,
      decisionGrade: true,
    });

    renderRoute(<ResearchRadarPage />, '/zh/research/radar');

    const page = await screen.findByTestId('research-radar-page');
    const hubEmptyState = await within(page).findByTestId('research-queue-hub-empty-state');
    expect(hubEmptyState).toHaveTextContent('数据暂不可用');
    expect(within(page).queryByTestId('observation-only-boundary')).not.toBeInTheDocument();
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/NVDA|Unsafe decision grade queue|Unsafe queue should not render/i);
  });

  it('renders Research Radar onboarding CTAs when the queue is empty', async () => {
    getResearchRadarMock.mockResolvedValue({
      schemaVersion: 'research_radar_api_v1',
      generatedAt: '2026-06-15T09:30:00Z',
      researchQueue: [],
      aggregateSummary: {
        queueQuality: 'thin',
        priorityCounts: {},
      },
      evidenceGaps: [],
      marketContextFit: 'neutral',
      onboardingGuidance: {
        title: 'Start a research loop',
        summary: 'provider_timeout',
        conditionsDetected: ['sourceRefs', 'reasonCodes'],
      },
      emptyStateActions: [
        { label: 'Start with Market Overview', route: '/market-overview', description: 'Read market context first.' },
        { label: 'Run Scanner', route: '/scanner', description: 'Create a candidate set.' },
        { label: 'Add Watchlist Symbol', route: '/watchlist', description: 'fundamentals.eps' },
        { label: 'Review Research Radar', route: '/research/radar', description: 'Return after activity.' },
      ],
      starterResearchWorkflow: ['Open Market Overview.', 'Run Scanner.', 'Choose one watchlist symbol.', 'Return to Research Radar.'],
      firstRunChecklist: ['Market context reviewed.', 'news'],
      suggestedResearchEntrypoints: [
        { surface: 'Market Overview', route: '/market-overview', description: 'Start with broad context.' },
        { surface: 'Scanner', route: '/scanner', description: 'Build a candidate queue.' },
      ],
      noAdviceDisclosure: '仅供研究队列观察。',
      dataQuality: { status: 'partial' },
    });
    getResearchQueueMock.mockResolvedValue(makeEmptyUnifiedResearchQueue());

    renderRoute(<ResearchRadarPage />, '/zh/research/radar');

    const page = await screen.findByTestId('research-radar-page');
    const onboardingPanel = await within(page).findByTestId('research-radar-onboarding-cta');
    const queueEmptyState = await within(page).findByTestId('research-radar-queue-empty-state');
    expect(onboardingPanel).toHaveTextContent('先完成研究循环，再回到雷达队列');
    expect(onboardingPanel).toHaveTextContent('先看市场概览');
    expect(onboardingPanel).toHaveTextContent('运行 Scanner');
    expect(onboardingPanel).toHaveTextContent('选择观察标的');
    expect(onboardingPanel).toHaveTextContent('查看研究雷达');
    expect(onboardingPanel).toHaveTextContent('Market context reviewed.');
    expect(onboardingPanel).toHaveTextContent('部分外部数据暂不可用');
    expect(onboardingPanel).toHaveTextContent('部分来源细节已折叠。');
    expect(onboardingPanel).toHaveTextContent('部分诊断细节已折叠。');
    expect(onboardingPanel).toHaveTextContent('基本面数据缺失');
    expect(onboardingPanel).toHaveTextContent('新闻数据暂缺');
    expect(within(onboardingPanel).getByRole('link', { name: '先看市场概览' })).toHaveAttribute('href', '/zh/market-overview');
    expect(within(onboardingPanel).getByRole('link', { name: '运行 Scanner' })).toHaveAttribute('href', '/zh/scanner');
    expect(within(onboardingPanel).getByRole('link', { name: '选择观察标的' })).toHaveAttribute('href', '/zh/watchlist');
    expect(within(onboardingPanel).getByRole('link', { name: '查看研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(queueEmptyState).toHaveTextContent('暂无研究队列');
    expect(queueEmptyState).toHaveTextContent('还没有进入队列的研究对象，先从上游研究入口整理线索。');
    expect(queueEmptyState).toHaveTextContent('下一步研究：从市场概览、扫描器或观察列表开始。');
    expect(queueEmptyState.textContent || '').not.toMatch(/request[_\s-]?id|trace[_\s-]?id|correlation[_\s-]?id|\breq-[a-z0-9-]{6,}\b/i);
    expect(findConsumerRawLeakage(queueEmptyState.textContent || '')).toEqual([]);
    expect(onboardingPanel.textContent || '').not.toMatch(/sourceRefs|reasonCodes|fundamentals\.eps|provider_timeout|\bnews\b/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/undefined|null|NaN/);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位建议|buy|sell|hold|recommendation|target price|stop loss|position sizing/i);
  });

  it('renders market-level read model fallback when Research Radar has no candidates', async () => {
    languageState.value = 'en';
    getResearchRadarMock.mockResolvedValue({
      schemaVersion: 'research_radar_api_v1',
      generatedAt: '2026-06-15T09:30:00Z',
      researchQueue: [],
      aggregateSummary: {
        queueQuality: 'degraded',
        priorityCounts: {},
      },
      evidenceGaps: ['Research candidates unavailable'],
      marketContextFit: 'unavailable',
      onboardingGuidance: null,
      emptyStateActions: [],
      starterResearchWorkflow: [],
      firstRunChecklist: [],
      suggestedResearchEntrypoints: [],
      noAdviceDisclosure: 'Research-only queue.',
      dataQuality: { status: 'degraded' },
      marketLevelFallback: {
        available: true,
        label: 'Market-level context',
        summary: 'Market-level evidence is available while candidate research is unavailable.',
        candidateGenerationExecuted: false,
        candidateUnavailableReason: 'scanner_candidates_unavailable',
        regime: { label: 'risk_on_confirming', status: 'ok' },
        productSummary: 'Risk-on confirming evidence is currently present because local evidence fields align.',
        evidenceCards: [
          {
            cardId: 'benchmark_trend',
            title: 'Benchmark Trend',
            status: 'positive',
            severity: 'info',
            headline: 'Benchmark trend evidence is positive.',
            reasons: ['Benchmark local trend fields are aligned.'],
          },
          {
            cardId: 'data_quality',
            title: 'Data Quality',
            status: 'positive',
            severity: 'info',
            headline: 'Data quality is product-ready.',
            reasons: ['No missing evidence families are present.'],
          },
        ],
        dataQuality: {
          adjustedCoverageState: 'available',
          missingDataFamilies: [],
          blockedProductSurfaces: [],
        },
        readiness: {
          label: 'product_ready',
          status: 'ok',
          missingDataFamilies: [],
          blockedProductSurfaces: [],
          nextOperatorAction: 'Market regime read model is available from local evidence inputs.',
        },
        missingDataFamilies: [],
        blockedProductSurfaces: [],
        nextOperatorAction: 'Market regime read model is available from local evidence inputs.',
        observationOnly: true,
        decisionGrade: false,
      },
    });
    getResearchQueueMock.mockResolvedValue(makeEmptyUnifiedResearchQueue());

    renderRoute(<ResearchRadarPage />, '/en/research/radar');

    const page = await screen.findByTestId('research-radar-page');
    const fallback = await within(page).findByTestId('research-radar-market-level-fallback');
    expect(fallback).toHaveTextContent('Market-level context');
    expect(fallback).toHaveTextContent('Candidate research is unavailable or has not executed.');
    expect(fallback).toHaveTextContent('Risk-on observation');
    expect(fallback).toHaveTextContent('Evidence ready for observation');
    expect(fallback).toHaveTextContent('Market state evidence currently supports a risk-on observation.');
    expect(fallback).toHaveTextContent('Benchmark trend');
    expect(fallback).toHaveTextContent('Data quality');
    expect(fallback).toHaveTextContent('Market state evidence is organized and ready for observation.');
    expect(within(page).getByTestId('research-radar-queue-empty-state')).toHaveTextContent('No research queue');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/\brank\s*1\b|target price|stop loss|position sizing|risk_on_confirming|product_ready|Market regime read model/i);
  });

  it('renders evidence remediation guidance and safe prerequisite copy for low-evidence research radar gaps', async () => {
    getResearchRadarMock.mockResolvedValue({
      schemaVersion: 'research_radar_api_v1',
      generatedAt: '2026-06-15T09:30:00Z',
      researchQueue: [],
      aggregateSummary: {
        queueQuality: 'low_evidence',
        priorityCounts: {},
      },
      evidenceGaps: ['fundamentals', 'news', 'catalyst', 'freshness'],
      marketContextFit: 'neutral',
      onboardingGuidance: {
        title: 'Research loop needs more context',
        summary: null,
        conditionsDetected: [],
      },
      emptyStateActions: [
        { label: 'Run Scanner', route: '/scanner', description: 'Create a candidate set.' },
        { label: 'Add Watchlist Symbol', route: '/watchlist', description: 'Add a user-chosen observation symbol.' },
      ],
      starterResearchWorkflow: ['Run Scanner.', 'Choose one watchlist symbol.', 'Return to Research Radar.'],
      firstRunChecklist: [],
      suggestedResearchEntrypoints: [
        { surface: 'Scanner', route: '/scanner', description: 'Build a candidate queue.' },
        { surface: 'Watchlist', route: '/watchlist', description: 'Keep one symbol under review.' },
      ],
      noAdviceDisclosure: '仅供研究队列观察。',
      dataQuality: { status: 'partial' },
    });
    getResearchQueueMock.mockResolvedValue({
      schemaVersion: 'research_queue_v1',
      researchQueue: [
        {
          queueItemId: 'manual-gap-TSLA-item-1',
          sourceSurface: 'manual_gap',
          symbol: 'TSLA',
          title: 'Evidence remediation follow-up',
          priorityTier: 'follow_up',
          whyQueued: ['Low-evidence filter active'],
          evidenceUsed: ['Evidence quality is acceptable'],
          evidenceGaps: ['fundamentals', 'news', 'catalyst', 'freshness'],
          freshness: { state: 'needs_review', lastReviewedAt: null },
          suggestedResearchPath: [
            {
              label: 'Stock Structure',
              route: '/stocks/TSLA/structure-decision',
              section: 'researchRadar',
              reason: 'Open symbol structure detail.',
            },
          ],
          observationOnly: true,
        },
      ],
      aggregateSummary: {
        itemCount: 1,
        limit: 5,
        bounded: false,
        bySourceSurface: { manual_gap: 1 },
        byPriorityTier: { urgent_review: 0, follow_up: 1, monitor: 0 },
      },
      sourceSurfacesAggregated: ['manual_gap'],
      evidenceGaps: ['fundamentals', 'news', 'catalyst', 'freshness'],
      dataQuality: {
        state: 'partial',
        itemCount: 1,
        sourceSurfacesAvailable: ['market'],
        sourceSurfacesExpected: ['scanner', 'watchlist', 'market', 'manual_gap'],
        failClosed: true,
      },
      noAdviceDisclosure: 'Research-only queue.',
      observationOnly: true,
      decisionGrade: false,
    });

    renderRoute(<ResearchRadarPage />, '/zh/research/radar');

    const page = await screen.findByTestId('research-radar-page');
    const onboardingPanel = await within(page).findByTestId('research-radar-onboarding-cta');
    const gapRail = within(page).getByTestId('evidence-gap-explanation-list');
    const hub = await within(page).findByTestId('research-queue-hub');
    const manualGapGroup = within(hub).getByTestId('research-queue-source-manual-gap');

    expect(onboardingPanel).toHaveTextContent('当前队列仍缺少公司资料、媒体语境、事件语境、时效复核，因此先保持观察边界。');
    expect(onboardingPanel).toHaveTextContent('扫描器候选尚未建立。');
    expect(onboardingPanel).toHaveTextContent('观察列表上下文尚未建立。');
    expect(onboardingPanel).toHaveTextContent('当前按低证据条件整理。');
    expect(within(onboardingPanel).getByRole('link', { name: '运行 Scanner' })).toHaveAttribute('href', '/zh/scanner');
    expect(within(onboardingPanel).getByRole('link', { name: '选择观察标的' })).toHaveAttribute('href', '/zh/watchlist');

    expect(gapRail).toHaveTextContent('公司证据缺失');
    expect(gapRail).toHaveTextContent('媒体语境缺失');
    expect(gapRail).toHaveTextContent('事件语境缺失');
    expect(gapRail).toHaveTextContent('时效复核缺失');
    expect(gapRail).toHaveTextContent('先补充主营业务、财务摘要或估值背景，再回来看当前线索是否仍成立。');
    expect(gapRail).toHaveTextContent('先补充公开报道或公告摘要，再复核当前线索是否仍需要跟进。');
    expect(gapRail).toHaveTextContent('先补充公告、财报、产品或行业事件，再复核当前线索是否延续。');
    expect(gapRail).toHaveTextContent('先补做近期价格、公告或报道的时效复核，再比较当前线索是否仍成立。');
    expect(gapRail).toHaveTextContent('仅作观察，不构成操作结论。');

    expect(manualGapGroup).toHaveTextContent('证据补缺');
    expect(manualGapGroup.textContent || '').not.toMatch(/Manual gap|manual_gap/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/provider|raw|debug|trace|requestId|schemaVersion|manual_gap/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位建议|buy|sell|hold|recommend(?:ation)?|target price|stop loss|position sizing/i);
    expect(getStructureDecisionMock).not.toHaveBeenCalled();
    expect(verifyTickerExistsMock).not.toHaveBeenCalled();
    await waitFor(() => expect(getResearchRadarMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(getResearchQueueMock).toHaveBeenCalledTimes(1));
  });

  it('sanitizes WorkBuddy raw research-radar queue wording before rendering', async () => {
    languageState.value = 'en';

    getResearchRadarMock.mockResolvedValue({
      schemaVersion: 'research_radar_api_v1',
      generatedAt: '2026-06-15T09:30:00Z',
      researchQueue: [],
      aggregateSummary: {
        queueQuality: 'low_evidence',
        priorityCounts: {},
      },
      evidenceGaps: ['fundamentals'],
      marketContextFit: 'neutral',
      onboardingGuidance: null,
      emptyStateActions: [],
      starterResearchWorkflow: [],
      firstRunChecklist: [],
      suggestedResearchEntrypoints: [],
      noAdviceDisclosure: 'Research-only queue.',
      dataQuality: { status: 'partial' },
    });
    getResearchQueueMock.mockResolvedValue({
      schemaVersion: 'research_queue_v1',
      researchQueue: [
        {
          queueItemId: 'raw-aapl-item-1',
          sourceSurface: 'manual_gap',
          symbol: 'AAPL',
          title: 'Some symbol evidence is present, but the packet is not complete enough for a clean research handoff.',
          priorityTier: 'follow_up',
          whyQueued: ['Missing or incomplete evidence families: quote, fundamental, news.'],
          evidenceUsed: ['Observation-only research readiness; not personalized financial advice or an instruction.'],
          evidenceGaps: ['fundamentals'],
          freshness: { state: 'needs_review', lastReviewedAt: null },
          suggestedResearchPath: [
            {
              label: 'Stock Structure',
              route: '/stocks/AAPL/structure-decision',
              section: 'researchRadar',
              reason: 'Add fundamental coverage before business-quality review.',
            },
          ],
          observationOnly: true,
        },
      ],
      aggregateSummary: {
        itemCount: 1,
        limit: 5,
        bounded: false,
        bySourceSurface: { manual_gap: 1 },
        byPriorityTier: { urgent_review: 0, follow_up: 1, monitor: 0 },
      },
      sourceSurfacesAggregated: ['manual_gap'],
      evidenceGaps: ['fundamentals'],
      dataQuality: {
        state: 'partial',
        itemCount: 1,
        sourceSurfacesAvailable: ['manual_gap'],
        sourceSurfacesExpected: ['scanner', 'watchlist', 'market', 'manual_gap'],
        failClosed: true,
      },
      noAdviceDisclosure: 'Research-only queue.',
      observationOnly: true,
      decisionGrade: false,
    });

    renderRoute(<ResearchRadarPage />, '/en/research/radar');

    const hub = await screen.findByTestId('research-queue-hub');
    expect(hub).toHaveTextContent('Supporting evidence still incomplete');
    expect(hub).toHaveTextContent('Observation-only for now');
    expect(hub).toHaveTextContent('Evidence still needed: market data, fundamentals, and news.');
    expect(hub.textContent || '').not.toMatch(/clean research handoff|evidence families|business-quality review|Observation-only research readiness|personalized financial advice/i);
    expect(findConsumerRawLeakage(hub.textContent || '')).toEqual([]);
  });

  it('keeps Research Radar visible when the unified research queue endpoint is unavailable', async () => {
    getResearchRadarMock.mockResolvedValue({
      schemaVersion: 'research_radar_api_v1',
      generatedAt: '2026-06-15T09:30:00Z',
      researchQueue: [],
      aggregateSummary: {
        queueQuality: 'thin',
        priorityCounts: {},
      },
      evidenceGaps: [],
      marketContextFit: 'neutral',
      onboardingGuidance: null,
      emptyStateActions: [],
      starterResearchWorkflow: [],
      firstRunChecklist: [],
      suggestedResearchEntrypoints: [],
      noAdviceDisclosure: '仅供研究队列观察。',
      dataQuality: { status: 'partial' },
    });
    getResearchQueueMock.mockRejectedValue(new Error('404 provider_runtime_trace req-queue-123 raw payload'));

    renderRoute(<ResearchRadarPage />, '/zh/research/radar');

    const page = await screen.findByTestId('research-radar-page');
    const hubEmptyState = await within(page).findByTestId('research-queue-hub-empty-state');
    expect(page).toHaveTextContent('今日观察队列');
    expect(page).not.toHaveTextContent('研究情景工作台');
    expect(hubEmptyState).toHaveTextContent('数据暂不可用');
    expect(hubEmptyState).toHaveTextContent('当前页面没有可展示的稳定研究资料，请稍后重试。');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/provider_runtime_trace|req-queue-123|raw payload|404/i);
  });

  it('renders consumer-safe API error copy on Research Radar and keeps retry available', async () => {
    languageState.value = 'en';
    getResearchRadarMock.mockRejectedValue(
      createApiError(createParsedApiError({
        title: 'provider runtime failure',
        message: 'requestId=req-123 traceId=trace-999 token=bearer-abc cache adapter internal raw debug',
        rawMessage: 'provider stack trace requestId=req-123 traceId=trace-999 token=bearer-abc cache adapter internal raw debug',
        category: 'unknown',
      })),
    );
    getResearchQueueMock.mockResolvedValue(makeEmptyUnifiedResearchQueue());

    renderRoute(<ResearchRadarPage />, '/en/research/radar');

    const page = await screen.findByTestId('research-radar-page');
    const alert = await within(page).findByRole('alert');
    expect(within(alert).getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    expect(alert.textContent || '').not.toMatch(/provider|runtime|requestId|traceId|token|bearer|cache|adapter|internal|raw|debug|stack/i);
    expect(alert).toHaveTextContent('This request is temporarily unavailable.');
    expect(alert).toHaveTextContent('Please try again shortly.');

    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
    await waitFor(() => expect(getResearchRadarMock).toHaveBeenCalledTimes(2));
  });

  it('renders the Stock Structure entry as an empty state without calling a stock API', () => {
    renderRoute(<StockStructureDecisionEntryPage />, '/zh/stocks/structure-decision?symbols=AAPL');

    const page = screen.getByTestId('stock-structure-entry-page');
    expect(page).toHaveTextContent('个股结构决策');
    expect(page).toHaveTextContent('输入标的进入结构视图');
    expect(page).toHaveTextContent('选择标的后再读取数据');
    expect(page).toHaveTextContent('内部数据细节已折叠');
    expect(page).toHaveTextContent('已带入 AAPL');
    expect(page).toHaveTextContent('输入或添加另一个标的后，可进行结构对比。');
    expect(page).toHaveTextContent('直接输入股票代码，或从 Scanner、观察列表、研究雷达继续进入。');
    expect(page).toHaveTextContent('报价、基本面、催化、同业或历史行情证据缺失时，会在详情页继续显示就绪边界。');
    expect(page).not.toHaveTextContent('OHLCV');
    expect(screen.getByRole('link', { name: '研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(findConsumerRawLeakage(page.textContent || '')).toEqual([]);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|下单|目标价|止损|仓位建议|优先于其他标的|投资偏好/);
  });

  it('renders a consumer-safe symbol-not-found state for an invalid single-symbol structure route', async () => {
    verifyTickerExistsMock.mockResolvedValue({
      stockCode: 'INVALID_SYMBOL_XXXX',
      normalizedSymbol: 'INVALID_SYMBOL_XXXX',
      market: null,
      status: 'invalid_format',
      valid: false,
      exists: false,
      stockName: null,
      message: 'Enter a supported stock symbol format.',
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/INVALID_SYMBOL_XXXX/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const emptyState = await within(page).findByTestId('stock-structure-symbol-not-found-state');
    expect(verifyTickerExistsMock).toHaveBeenCalledWith('INVALID_SYMBOL_XXXX');
    expect(getStructureDecisionMock).not.toHaveBeenCalled();
    expect(emptyState).toHaveTextContent('标的未找到');
    expect(emptyState).toHaveTextContent('未找到该标的，请检查代码是否正确，或返回搜索重新选择。');
    expect(emptyState).toHaveTextContent('当前无法确认该标的，不等同于数据暂时不可用。');
    expect(emptyState).toHaveTextContent('仅研究观察。');
    expect(within(emptyState).getByRole('link', { name: '返回研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(within(emptyState).getByRole('link', { name: '返回观察列表' })).toHaveAttribute('href', '/zh/watchlist');
    expect(within(emptyState).getByRole('link', { name: '返回首页' })).toHaveAttribute('href', '/zh');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/unavailable|lowConfidence|low_confidence|OHLCV|provider|runtime|debug|traceId|requestId|schemaVersion|policyVersion|raw|reasonCodes|internal|local_db|fallback_source|fixture|adapter/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/buy|sell|hold|recommend|target|stop|position size|买入|卖出|持有|推荐|目标价|止损|仓位建议|加仓|减仓/i);
  });

  it('renders the English symbol-not-found state without raw diagnostic labels', async () => {
    languageState.value = 'en';
    verifyTickerExistsMock.mockResolvedValue({
      stockCode: 'INVALID_SYMBOL_XXXX',
      normalizedSymbol: 'INVALID_SYMBOL_XXXX',
      market: null,
      status: 'invalid_format',
      valid: false,
      exists: false,
      stockName: null,
      message: 'Enter a supported stock symbol format.',
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/en/stocks/INVALID_SYMBOL_XXXX/structure-decision',
      '/en/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    const emptyState = await within(page).findByTestId('stock-structure-symbol-not-found-state');
    expect(emptyState).toHaveTextContent('Symbol not found');
    expect(emptyState).toHaveTextContent('INVALID_SYMBOL_XXXX was not found. Check the code, or return to search and choose again.');
    expect(emptyState).toHaveTextContent('INVALID_SYMBOL_XXXX cannot be confirmed; this differs from temporarily missing data.');
    expect(emptyState).toHaveTextContent('Research observation only.');
    expect(within(emptyState).getByRole('link', { name: 'Back to Research Radar' })).toHaveAttribute('href', '/en/research/radar');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/unavailable|lowConfidence|low_confidence|OHLCV|provider|runtime|debug|traceId|requestId|schemaVersion|policyVersion|raw|reasonCodes|internal|local_db|fallback_source|fixture|adapter/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/buy|sell|hold|recommend|target|stop|position size|买入|卖出|持有|推荐|目标价|止损|仓位建议|加仓|减仓/i);
  });

  it('keeps supported but unverified symbols on the normal insufficient-evidence structure page', async () => {
    verifyTickerExistsMock.mockResolvedValue({
      stockCode: 'AAPL',
      normalizedSymbol: 'AAPL',
      market: 'us',
      status: 'unknown',
      valid: false,
      exists: false,
      stockName: null,
      message: 'Symbol format is supported, but verification is not confirmed yet.',
    });
    getStructureDecisionMock.mockResolvedValue({
      schemaVersion: 'stock_structure_decision_api_v1',
      ticker: 'AAPL',
      structureState: 'lowConfidence',
      confidence: 'low',
      componentScores: {},
      explanation: {
        whyThisStructure: 'Evidence remains limited.',
        whatConfirmsIt: [],
        whatInvalidatesIt: [],
        keyLevels: [],
      },
      researchNotes: {
        watchNext: [],
        needsMoreEvidence: ['补齐更多有效日线数据后再复核。'],
        riskFlags: ['low_confidence'],
      },
      dataQuality: {
        status: 'unavailable',
        period: 'daily',
        usableBars: 0,
      },
      missingEvidence: [
        { kind: 'daily_ohlcv', message: 'Daily OHLCV history is unavailable.' },
      ],
      noAdviceDisclosure: 'Observation-only research context.',
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/AAPL/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    expect(verifyTickerExistsMock).toHaveBeenCalledWith('AAPL');
    expect(getStructureDecisionMock).toHaveBeenCalledWith('AAPL');
    expect(page).toHaveTextContent('AAPL 结构工作区');
    expect(page).toHaveTextContent('证据不足');
    expect(page).not.toHaveTextContent('标的未找到');
    expect(within(page).queryByTestId('stock-structure-symbol-not-found-state')).not.toBeInTheDocument();
  });

  it('shows a per-symbol safe missing explanation in multi-symbol structure routes', async () => {
    getStructureDecisionsBatchMock.mockResolvedValue({
      schemaVersion: 'stock_structure_decision_batch_api_v1',
      items: [
        {
          schemaVersion: 'stock_structure_decision_api_v1',
          ticker: 'AAPL',
          structureState: 'range',
          confidence: 'medium',
          componentScores: { trend: 58 },
          explanation: {
            whyThisStructure: 'AAPL remains range-bound.',
            whatConfirmsIt: [],
            whatInvalidatesIt: [],
            keyLevels: [],
          },
          researchNotes: {
            watchNext: [],
            needsMoreEvidence: [],
            riskFlags: [],
          },
          dataQuality: {
            status: 'available',
            period: 'daily',
            usableBars: 60,
          },
          missingEvidence: [],
          noAdviceDisclosure: 'Observation-only research context.',
        },
      ],
      aggregateSummary: {
        requestedCount: 2,
        evaluatedCount: 1,
        truncated: false,
      },
      missingEvidence: [],
      dataQuality: { status: 'partial' },
      symbolCompareEvidencePacket: {
        comparedSymbols: ['AAPL'],
        sharedEvidence: [],
        divergentEvidence: [],
        missingEvidenceBySymbol: {
          AAPL: [],
          INVALID_SYMBOL_XXXX: [
            {
              kind: 'symbol_validation',
              message: 'Enter a supported stock symbol format. provider_runtime_trace raw payload reasonCodes buy now target price',
            },
          ],
        },
        freshnessBySymbol: {
          AAPL: { status: 'available', period: 'daily', usableBars: 60 },
        },
        confidenceCap: { value: 25 },
        observationBoundary: {
          observationOnly: true,
          decisionGrade: false,
          rankingAllowed: false,
          adviceAllowed: false,
        },
        researchNextSteps: [],
      },
      noAdviceDisclosure: 'Observation-only research context.',
    });

    renderRoute(<StockStructureDecisionPage />, '/zh/stocks/INVALID_SYMBOL_XXXX,AAPL/structure-decision');

    const page = await screen.findByTestId('stock-structure-decision-page');
    const packet = await within(page).findByTestId('symbol-compare-evidence-packet');
    expect(getStructureDecisionsBatchMock).toHaveBeenCalledWith({
      stockCodes: ['INVALID_SYMBOL_XXXX', 'AAPL'],
      benchmark: undefined,
      maxItems: undefined,
    });
    expect(packet).toHaveTextContent('AAPL');
    expect(packet).toHaveTextContent('INVALID_SYMBOL_XXXX');
    expect(packet).toHaveTextContent('标的未找到');
    expect(packet).toHaveTextContent('未找到该标的，请检查代码是否正确，或返回搜索重新选择。');
    expect(packet).toHaveTextContent('证据暂不可用');
    expect(packet).toHaveTextContent('部分证据暂不可用，因此当前结论只适合作为观察线索。');
    expect(packet.textContent || '').not.toMatch(/provider|runtime|trace|raw|reasonCodes|target price|buy now|schemaVersion|local_db|fallback_source|fixture|adapter/i);
    expect(packet.textContent || '').not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位建议|加仓|减仓|buy|sell|hold|recommend|target|stop|position size/i);
  });

  it('renders Stock Structure peer-correlation context without raw diagnostics', async () => {
    getStructureDecisionMock.mockResolvedValue({
      schemaVersion: 'stock_structure_decision_api_v1',
      ticker: 'ORCL',
      structureState: 'range',
      confidence: 'medium',
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
        correlationState: 'aligned',
        peerEvidence: [
          {
            symbol: 'MSFT',
            overlapDays: 22,
            state: 'aligned',
            summary: 'MSFT moved with ORCL across the comparison window.',
          },
        ],
        divergenceEvidence: [],
        staleInputs: [],
        missingInputs: ['NVDA peer history is unavailable.'],
        confidenceCap: 'medium',
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
    expect(page).toHaveTextContent('需要补充同业对照证据。');
    expect(snapshot).toHaveTextContent('同业相关性');
    expect(snapshot).toHaveTextContent('同业走势同步');
    expect(snapshot).toHaveTextContent('Cloud software');
    expect(snapshot).toHaveTextContent('MSFT 与 ORCL 在当前对比窗口内走势同步。');
    expect(snapshot).toHaveTextContent('NVDA 同业历史数据暂缺。');
    expect(snapshot).toHaveTextContent('仅供同业走势观察，不构成个性化行动指令。');
    expect(snapshot).toHaveTextContent('下一个收盘后复核同业同步是否延续。');
    expect(within(page).getByRole('link', { name: '与 MSFT 对比证据' })).toHaveAttribute('href', '/zh/stocks/ORCL,MSFT/structure-decision');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/raw|debug|provider|trace|sourceRef|reasonCode|requestId/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位建议|buy|sell|hold|recommendation|target price|stop loss|position sizing/i);
  });

  it('renders a consumer-safe empty state when peer correlation evidence is missing', async () => {
    getStructureDecisionMock.mockResolvedValue({
      schemaVersion: 'stock_structure_decision_api_v1',
      ticker: 'ADBE',
      structureState: 'range',
      confidence: 'medium',
      componentScores: { trend: 52 },
      explanation: {
        whyThisStructure: 'ADBE remains range-bound.',
        whatConfirmsIt: ['Needs a broader evidence window.'],
        whatInvalidatesIt: ['A range failure would change the read.'],
        keyLevels: [],
      },
      researchNotes: {
        watchNext: ['Review the next close.'],
        needsMoreEvidence: ['Need comparable peer structure evidence.'],
        riskFlags: [],
      },
      dataQuality: {
        status: 'partial',
        period: 'daily',
        usableBars: 44,
      },
      missingEvidence: [],
      noAdviceDisclosure: 'Observation-only research context.',
    });

    renderRoutePattern(
      <StockStructureDecisionPage />,
      '/zh/stocks/ADBE/structure-decision',
      '/zh/stocks/:stockCode/structure-decision',
    );

    const page = await screen.findByTestId('stock-structure-decision-page');
    expect(within(page).queryByTestId('stock-structure-peer-correlation-snapshot')).not.toBeInTheDocument();
    expect(page).toHaveTextContent('需要补充同业对照证据。');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/raw|debug|provider|trace|sourceRef|reasonCode|requestId|schemaVersion/i);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位建议|buy|sell|hold|recommendation|target price|stop loss|position sizing/i);
  });

  it('renders a compact stock structure compare evidence packet for multiple symbols', async () => {
    getStructureDecisionsBatchMock.mockResolvedValue({
      schemaVersion: 'stock_structure_decision_batch_api_v1',
      items: [
        {
          schemaVersion: 'stock_structure_decision_api_v1',
          ticker: 'MSFT',
          structureState: 'mixed',
          confidence: 'low',
          componentScores: { trend: 45 },
          explanation: {
            whyThisStructure: 'Price action is mixed.',
            whatConfirmsIt: ['Needs follow-through.'],
            whatInvalidatesIt: ['Breaks below the range.'],
            keyLevels: [],
          },
          researchNotes: {
            watchNext: ['Observe the next close.'],
            needsMoreEvidence: [],
            riskFlags: [],
          },
          dataQuality: {
            status: 'partial',
            period: 'daily',
            usableBars: 20,
          },
          missingEvidence: [],
          noAdviceDisclosure: 'Observation-only research context.',
        },
      ],
      aggregateSummary: {
        requestedCount: 2,
        evaluatedCount: 2,
        truncated: false,
      },
      missingEvidence: [
        { kind: 'fundamentals_missing', message: 'fundamentals_missing sourceRefs' },
      ],
      dataQuality: { status: 'partial' },
      symbolCompareEvidencePacket: {
        comparedSymbols: ['MSFT', 'AAPL'],
        sharedEvidence: [
          {
            kind: 'daily_ohlcv',
            symbols: ['MSFT', 'AAPL'],
            status: 'available',
            period: 'daily',
            source: 'local_db',
            usableBarsMin: 55,
            usableBarsMax: 60,
          },
        ],
        divergentEvidence: [
          {
            kind: 'structure_state',
            symbols: ['MSFT', 'AAPL'],
            values: {
              MSFT: 'mixed',
              AAPL: 'breakout',
            },
          },
        ],
        missingEvidenceBySymbol: {
          MSFT: [{ kind: 'price_history_stale', message: 'provider_runtime_trace raw payload' }],
          AAPL: [],
        },
        freshnessBySymbol: {
          MSFT: { status: 'unavailable', source: 'local_db', period: 'daily', usableBars: 0 },
          AAPL: { status: 'available', source: 'local_db', period: 'daily', usableBars: 60 },
        },
          confidenceCap: {
            value: 35,
            reasonCodes: ['symbol_evidence_unavailable'],
            policyVersion: 'symbol_compare_evidence_packet_v1',
        },
        observationBoundary: {
          observationOnly: true,
          decisionGrade: false,
          rankingAllowed: false,
          adviceAllowed: false,
        },
        researchNextSteps: [
          'Add daily OHLCV evidence for MSFT before using divergence observations.',
        ],
      },
      noAdviceDisclosure: 'Observation-only research context.',
    });

    renderRoute(<StockStructureDecisionPage />, '/zh/stocks/MSFT,AAPL/structure-decision?benchmark=SPY');

    const page = await screen.findByTestId('stock-structure-decision-page');
    const packet = await within(page).findByTestId('symbol-compare-evidence-packet');
    expect(getStructureDecisionsBatchMock).toHaveBeenCalledWith({
      stockCodes: ['MSFT', 'AAPL'],
      benchmark: 'SPY',
      maxItems: undefined,
    });
    expect(packet).toHaveTextContent('对比支持证据');
    expect(packet).toHaveTextContent('MSFT');
    expect(packet).toHaveTextContent('AAPL');
    expect(packet).toHaveTextContent('共享证据');
    expect(packet).toHaveTextContent('日线数据');
    expect(packet).toHaveTextContent('55-60 根可用');
    expect(packet).toHaveTextContent('分歧证据');
    expect(packet).toHaveTextContent('结构状态');
    expect(packet).toHaveTextContent('MSFT: 结构分化');
    expect(packet).toHaveTextContent('AAPL: 突破观察');
    expect(packet).toHaveTextContent('缺失证据');
    expect(packet).toHaveTextContent('MSFT');
    expect(packet).toHaveTextContent('价格历史时效有限');
    expect(packet).toHaveTextContent('先刷新或补齐价格历史，再复核结构信号是否仍一致。');
    expect(packet).toHaveTextContent('AAPL');
    expect(packet).toHaveTextContent('新鲜度');
    expect(packet).toHaveTextContent('0 根');
    expect(packet).toHaveTextContent('60 根');
    expect(packet).toHaveTextContent('置信上限 35');
    expect(packet).toHaveTextContent('仅研究观察');
    expect(packet).toHaveTextContent('非判断等级');
    expect(packet).toHaveTextContent('不排序');
    expect(packet).toHaveTextContent('不生成行动指令');
    expect(packet).toHaveTextContent('置信度受到上限约束');
    expect(packet).toHaveTextContent('当前证据还不足以支撑更高置信度，只能作为研究观察。');
    expect(packet).toHaveTextContent('后续研究');
    expect(packet).toHaveTextContent('补齐可比较标的的基础证据后再复核。');
    expect(packet.textContent || '').not.toMatch(/daily OHLCV|divergence observations/i);
    expect(packet.textContent || '').not.toMatch(/reasonCodes|policyVersion|local_db|sourceRef|requestId|trace|raw|debug|provider|schemaVersion|price_history_stale|symbol_evidence_unavailable/i);
    expect(packet.textContent || '').not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位建议|buy now|sell now|hold|target price|stop loss|position sizing/i);
  });

  it('renders a stock structure compare empty state for a single symbol response', async () => {
    getStructureDecisionMock.mockResolvedValue({
      schemaVersion: 'stock_structure_decision_api_v1',
      ticker: 'AAPL',
      structureState: 'breakout',
      confidence: 'high',
      componentScores: { trend: 78 },
      explanation: {
        whyThisStructure: 'Price stayed above the recent range.',
        whatConfirmsIt: ['Volume remained constructive.'],
        whatInvalidatesIt: ['Closes fall back into the prior range.'],
        keyLevels: [],
      },
      researchNotes: {
        watchNext: ['Observe follow-through on the next close.'],
        needsMoreEvidence: [],
        riskFlags: [],
      },
      dataQuality: {
        status: 'available',
        period: 'daily',
        usableBars: 55,
      },
      missingEvidence: [],
      noAdviceDisclosure: 'Observation-only research context.',
    });

    renderRoute(<StockStructureDecisionPage />, '/zh/stocks/AAPL/structure-decision');

    const page = await screen.findByTestId('stock-structure-decision-page');
    expect(page).toHaveTextContent('AAPL 结构工作区');
    expect(getStructureDecisionMock).toHaveBeenCalledWith('AAPL');
    expect(within(page).queryByTestId('symbol-compare-evidence-packet')).not.toBeInTheDocument();
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位建议|buy|sell|hold|recommendation|target price|stop loss|position sizing/i);
  });

  it('redacts unsafe diagnostics from partially missing symbol compare evidence', async () => {
    getStructureDecisionsBatchMock.mockResolvedValue({
      schemaVersion: 'stock_structure_decision_batch_api_v1',
      items: [
        {
          schemaVersion: 'stock_structure_decision_api_v1',
          ticker: 'MSFT',
          structureState: 'mixed',
          confidence: 'low',
          componentScores: { trend: 45 },
          explanation: {
            whyThisStructure: 'Price action is mixed.',
            whatConfirmsIt: ['Needs follow-through.'],
            whatInvalidatesIt: ['Breaks below the range.'],
            keyLevels: [],
          },
          researchNotes: {
            watchNext: ['Observe the next close.'],
            needsMoreEvidence: [],
            riskFlags: [],
          },
          dataQuality: {
            status: 'partial',
            period: 'daily',
            usableBars: 20,
          },
          missingEvidence: [],
          noAdviceDisclosure: 'Observation-only research context.',
        },
      ],
      aggregateSummary: {
        requestedCount: 2,
        evaluatedCount: 2,
        truncated: false,
      },
      missingEvidence: [],
      dataQuality: { status: 'partial' },
      symbolCompareEvidencePacket: {
        comparedSymbols: ['MSFT', 'AAPL'],
        sharedEvidence: [],
        divergentEvidence: [],
        missingEvidenceBySymbol: {
          MSFT: [{ kind: 'provider_runtime', message: 'provider_timeout debugRef=req-raw-123 raw payload sourceRefId=src-1' }],
          AAPL: [],
        },
        freshnessBySymbol: {
          MSFT: { status: 'provider_timeout', period: 'daily', usableBars: 0 },
          AAPL: { status: 'available', period: 'daily', usableBars: 60 },
        },
        confidenceCap: { value: 20 },
        observationBoundary: {
          observationOnly: true,
          decisionGrade: false,
          rankingAllowed: false,
          adviceAllowed: false,
        },
        researchNextSteps: [
          'Retry provider_runtime route before buy now.',
        ],
      },
      noAdviceDisclosure: 'Observation-only research context.',
    });

    renderRoute(<StockStructureDecisionPage />, '/zh/stocks/MSFT,AAPL/structure-decision');

    const page = await screen.findByTestId('stock-structure-decision-page');
    const packet = await within(page).findByTestId('symbol-compare-evidence-packet');
    expect(packet).toHaveTextContent('MSFT');
    expect(packet).toHaveTextContent('AAPL');
    expect(packet).toHaveTextContent('MSFT 的部分对比证据暂未就绪。');
    expect(packet).toHaveTextContent('补齐可比较标的的基础证据后再复核。');
    expect(findConsumerRawLeakage(packet.textContent || '')).toEqual([]);
    expect(packet.textContent || '').not.toMatch(/provider|raw|debug|sourceRef|requestId|trace|schemaVersion|buy now|sell now|hold|target price|stop loss|position sizing/i);
  });

  it('renders Scenario Lab as a compact research workflow backed by the scenario contract', async () => {
    getDecisionCockpitMock.mockResolvedValue({
      schemaVersion: 'market_decision_cockpit.v1',
      generatedAt: '2026-06-15T09:30:00Z',
      marketRegimeDecision: {
        regime: 'riskOn',
        confidence: 'medium',
        confidenceScore: 0.68,
        driverScores: {
          dealerGamma: { score: 0, evidenceState: 'unavailable' },
          breadthParticipation: { score: 58, evidenceState: 'score_grade' },
          volatilityStructure: { score: 72, evidenceState: 'score_grade' },
          ratesDollar: { score: 34, evidenceState: 'score_grade' },
          liquidityCredit: { score: 65, evidenceState: 'score_grade' },
          crossAssetRisk: { score: 28, evidenceState: 'score_grade' },
          sectorThemeRotation: { score: 52, evidenceState: 'score_grade' },
          eventCatalyst: { score: 0, evidenceState: 'unavailable' },
        },
      },
      researchQueuePreview: {
        topCandidates: [],
        queueQuality: 'mixed',
        evidenceGaps: [],
        previewOnly: true,
      },
      optionsStructureStatus: {
        gammaEvidenceStatus: 'unavailable',
        observationOnly: true,
        decisionGrade: false,
        missingEvidence: [],
        blockedReasonCodes: [],
      },
      cockpitSummary: {
        whatChanged: [],
        whyItMatters: [],
        whatToWatch: [],
        confidenceLimits: [],
      },
      noAdviceDisclosure: 'Research context only.',
      dataQuality: { status: 'partial' },
    });
    runScenarioLabMock.mockResolvedValue({
      schemaVersion: 'market_scenario_lab_engine.v1',
      baseRegime: {
        regime: 'riskOn',
        confidence: 'medium',
        confidenceScore: 0.68,
      },
      scenarioRegime: {
        regime: 'mixed',
        confidence: 'low',
        confidenceScore: 0.43,
      },
      confidenceDelta: -0.25,
      driverDeltas: {
        dealerGamma: 0,
        breadthParticipation: -75,
        volatilityStructure: -145,
        ratesDollar: 0,
        liquidityCredit: 0,
        crossAssetRisk: -40,
        sectorThemeRotation: 0,
        eventCatalyst: 0,
      },
      changedDrivers: ['breadthParticipation', 'volatilityStructure', 'crossAssetRisk'],
      scenarioSummary: [
        'Breadth participation weakens quickly under the selected stress.',
        'Volatility structure flips into a defensive posture.',
      ],
      whatWouldConfirm: [
        'Score-grade evidence would need to show the stressed drivers moving together in the scenario direction.',
      ],
      whatWouldInvalidate: [
        'The scenario frame weakens if score-grade evidence does not move with the selected shocks.',
      ],
      evidenceLimits: [
        'Gamma evidence status is unavailable, so gamma-sensitive conclusions remain capped.',
      ],
      noAdviceDisclosure: 'Research planning only; not a personalized decision basis.',
    });

    renderRoute(<ScenarioLabPage />, '/zh/scenario-lab');

    const page = await screen.findByTestId('scenario-lab-page');
    expect(page).toHaveTextContent('情景实验室：假设推演工作台');
    expect(page).not.toHaveTextContent('今日观察队列');
    expect(page).toHaveTextContent('研究问题');
    expect(page).toHaveTextContent('波动冲击');
    expect(page).toHaveTextContent('评估前暂不可用');
    const setup = await within(page).findByTestId('scenario-lab-setup-idle');
    fireEvent.click(within(setup).getByRole('button', { name: '评估情景' }));
    await waitFor(() => expect(runScenarioLabMock).toHaveBeenCalledWith(expect.objectContaining({
      scenarioName: 'volatilitySpike',
      baseRegime: expect.objectContaining({
        regime: 'riskOn',
        confidence: 'medium',
      }),
    })));
    expect(await within(page).findByTestId('scenario-lab-first-read-summary')).toBeInTheDocument();
    expect(page).toHaveTextContent('基准状态');
    expect(page).toHaveTextContent('情景后的研究框架');
    expect(page).toHaveTextContent('所选压力情景下，市场广度会较快转弱。');
    expect(page).toHaveTextContent('波动结构会转入偏防御状态。');
    expect(page).toHaveTextContent('数据暂不可用');
    expect(page).toHaveTextContent('证据已整理');
    expect(page).toHaveTextContent('需要更高质量证据共同确认受压驱动是否同向变化。');
    expect(page).toHaveTextContent('如果关键证据未随所选冲击同步变化，该情景框架会减弱。');
    expect(page).toHaveTextContent('保持观察边界');
    expect(screen.getByText('Gamma 相关证据暂不可用，因此相关结论需保持保守。')).toBeInTheDocument();
    expect(screen.getByText('仅供研究规划观察，不构成个性化判断依据。')).toBeInTheDocument();
    expect(page).toHaveTextContent('仅观察');
    expect(page).toHaveTextContent('非决策级');
    expect(screen.getByRole('link', { name: '决策驾驶舱' })).toHaveAttribute('href', '/zh/market/decision-cockpit');
    expect(screen.getByRole('button', { name: '波动冲击' })).toBeInTheDocument();
    expect(page.textContent || '').not.toContain('评分等级');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|下单|目标价|止损|仓位建议/);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/raw|debug|provider|score-grade|score_grade|unavailable|Breadth participation weakens quickly under the selected stress|Volatility structure flips into a defensive posture|Research planning only; not a personalized decision basis/i);
    expect(findConsumerRawLeakage(page.textContent || '')).toEqual([]);
  });

  it('renders Scenario Lab with an unavailable scenario state when base evidence is insufficient', async () => {
    getDecisionCockpitMock.mockResolvedValue({
      schemaVersion: 'market_decision_cockpit.v1',
      generatedAt: '2026-06-15T09:30:00Z',
      marketRegimeDecision: {
        regime: 'lowConfidence',
        confidence: 'low',
        driverScores: {
          breadthParticipation: { score: 0, evidenceState: 'unavailable' },
          volatilityStructure: { score: 0, evidenceState: 'unavailable' },
        },
      },
      researchQueuePreview: {
        topCandidates: [],
        queueQuality: 'thin',
        evidenceGaps: [],
        previewOnly: true,
      },
      optionsStructureStatus: {
        gammaEvidenceStatus: 'unavailable',
        observationOnly: true,
        decisionGrade: false,
        missingEvidence: [],
        blockedReasonCodes: [],
      },
      cockpitSummary: {
        whatChanged: [],
        whyItMatters: [],
        whatToWatch: [],
        confidenceLimits: [],
      },
      noAdviceDisclosure: 'Research context only.',
      dataQuality: { status: 'degraded' },
    });
    runScenarioLabMock.mockResolvedValue({
      schemaVersion: 'market_scenario_lab_engine.v1',
      baseRegime: {
        regime: 'lowConfidence',
        confidence: 'low',
        confidenceScore: 0,
      },
      scenarioRegime: {
        regime: 'lowConfidence',
        confidence: 'low',
        confidenceScore: 0,
        status: 'unavailable',
      },
      confidenceDelta: 0,
      driverDeltas: {},
      changedDrivers: [],
      scenarioSummary: [
        'Scenario lab is unavailable because base score-grade regime evidence is missing.',
      ],
      whatWouldConfirm: [],
      whatWouldInvalidate: [],
      evidenceLimits: [
        'Base regime evidence is missing or below the minimum driver coverage for scenario analysis.',
      ],
      noAdviceDisclosure: 'Research planning only; not a personalized decision basis.',
    });

    renderRoute(<ScenarioLabPage />, '/zh/scenario-lab?scenario=gammaUnavailable');

    const page = await screen.findByTestId('scenario-lab-page');
    expect(page).toHaveTextContent('情景实验室：假设推演工作台');
    expect(page).toHaveTextContent('当前情景：Gamma 缺口。');
    const setup = await within(page).findByTestId('scenario-lab-setup-idle');
    fireEvent.click(within(setup).getByRole('button', { name: '评估情景' }));
    await waitFor(() => expect(runScenarioLabMock).toHaveBeenCalledWith(expect.objectContaining({
      scenarioName: 'gammaUnavailable',
    })));
    expect(await within(page).findByTestId('scenario-lab-unavailable-state')).toBeInTheDocument();
    expect(page).toHaveTextContent('情景待更新');
    expect(page).toHaveTextContent('基准待确认，暂不展开输出。');
    expect(page).toHaveTextContent('待补证据：市场框架、驱动证据、数据新鲜度。');
    expect(page).toHaveTextContent('研究观察');
    expect(within(page).getByRole('link', { name: '查看市场概览' })).toHaveAttribute('href', '/zh/market-overview');
    expect(within(page).getByRole('link', { name: '返回研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/blocked|unavailable|score-grade|score_grade|driver coverage|base regime evidence is missing|provider|runtime|debug|requestId|traceId|policyVersion|raw|internal|cache/i);
    expect(findConsumerRawLeakage(page.textContent || '')).toEqual([]);
    expect(textContentWithoutObservationBoundary(page)).not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位建议|加仓|减仓|buy|sell|hold|recommend|target|stop|position size/i);
  });
});
