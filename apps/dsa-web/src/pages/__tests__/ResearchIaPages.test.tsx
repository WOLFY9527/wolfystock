import type React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import MarketDecisionCockpitPage from '../MarketDecisionCockpitPage';
import ResearchRadarPage from '../ResearchRadarPage';
import ScenarioLabPage from '../ScenarioLabPage';
import StockStructureDecisionPage from '../StockStructureDecisionPage';
import StockStructureDecisionEntryPage from '../StockStructureDecisionEntryPage';
import { findConsumerRawLeakage } from '../../test-utils/consumerRawLeakageGuard';

const {
  languageState,
  getDecisionCockpitMock,
  getDailyIntelligenceMock,
  getResearchRadarMock,
  getStructureDecisionMock,
  getStructureDecisionsBatchMock,
  runScenarioLabMock,
} = vi.hoisted(() => ({
  languageState: { value: 'zh' as 'zh' | 'en' },
  getDecisionCockpitMock: vi.fn(),
  getDailyIntelligenceMock: vi.fn(),
  getResearchRadarMock: vi.fn(),
  getStructureDecisionMock: vi.fn(),
  getStructureDecisionsBatchMock: vi.fn(),
  runScenarioLabMock: vi.fn(),
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: languageState.value,
    t: (key: string) => key,
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
  },
}));

vi.mock('../../api/scenarioLab', () => ({
  scenarioLabApi: {
    runScenarioLab: (...args: unknown[]) => runScenarioLabMock(...args),
  },
}));

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    getStructureDecision: (...args: unknown[]) => getStructureDecisionMock(...args),
    getStructureDecisionsBatch: (...args: unknown[]) => getStructureDecisionsBatchMock(...args),
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

describe('research IA pages', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    languageState.value = 'zh';
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
    expect(page).toHaveTextContent('市场结构、定位语境与研究队列');
    const dailyBriefing = await screen.findByTestId('daily-intelligence-briefing');
    await within(dailyBriefing).findByText('仅观察简报');
    expect(dailyBriefing).toHaveTextContent('每日研究简报');
    expect(page).toHaveTextContent('仅观察简报');
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
    expect(screen.getByRole('link', { name: '情景实验室' })).toHaveAttribute('href', '/zh/scenario-lab');
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
    expect(page.textContent || '').not.toMatch(/买入|卖出|下单|目标价|止损|仓位建议/);
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
          whyOnRadar: ['相对强弱改善'],
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
    });

    renderRoute(<ResearchRadarPage />, '/zh/research/radar?market=us&limit=5');

    const page = await screen.findByTestId('research-radar-page');
    expect(page).toHaveTextContent('承接市场结构的研究队列');
    expect(await within(page).findByText('ALFA')).toBeInTheDocument();
    expect(await within(page).findByText('相对强弱改善')).toBeInTheDocument();
    expect(within(page).getByRole('link', { name: '打开结构面板' })).toHaveAttribute('href', '/zh/stocks/ALFA/structure-decision');
    await waitFor(() => expect(getResearchRadarMock).toHaveBeenCalledWith({ market: 'us', profile: undefined, limit: 5 }));
    expect(page.textContent || '').not.toMatch(/raw|debug|provider|schema/i);
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

    renderRoute(<ResearchRadarPage />, '/zh/research/radar');

    const page = await screen.findByTestId('research-radar-page');
    const onboardingPanel = within(page).getByTestId('research-radar-onboarding-cta');
    const queueEmptyState = within(page).getByTestId('research-radar-queue-empty-state');
    expect(onboardingPanel).toHaveTextContent('先完成研究循环，再回到雷达队列');
    expect(onboardingPanel).toHaveTextContent('先看市场概览');
    expect(onboardingPanel).toHaveTextContent('运行 Scanner');
    expect(onboardingPanel).toHaveTextContent('选择观察标的');
    expect(onboardingPanel).toHaveTextContent('回到研究雷达');
    expect(onboardingPanel).toHaveTextContent('Market context reviewed.');
    expect(onboardingPanel).toHaveTextContent('部分外部数据暂不可用');
    expect(onboardingPanel).toHaveTextContent('部分来源细节已折叠。');
    expect(onboardingPanel).toHaveTextContent('部分诊断细节已折叠。');
    expect(onboardingPanel).toHaveTextContent('基本面数据缺失');
    expect(onboardingPanel).toHaveTextContent('新闻数据暂缺');
    expect(within(onboardingPanel).getByRole('link', { name: '先看市场概览' })).toHaveAttribute('href', '/zh/market-overview');
    expect(within(onboardingPanel).getByRole('link', { name: '运行 Scanner' })).toHaveAttribute('href', '/zh/scanner');
    expect(within(onboardingPanel).getByRole('link', { name: '选择观察标的' })).toHaveAttribute('href', '/zh/watchlist');
    expect(within(onboardingPanel).getByRole('link', { name: '回到研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(queueEmptyState).toHaveTextContent('暂无研究队列');
    expect(queueEmptyState).toHaveTextContent('还没有进入队列的研究对象，先从上游研究入口整理线索。');
    expect(queueEmptyState).toHaveTextContent('下一步研究：从市场概览、扫描器或观察列表开始。');
    expect(queueEmptyState.textContent || '').not.toMatch(/request[_\s-]?id|trace[_\s-]?id|correlation[_\s-]?id|\breq-[a-z0-9-]{6,}\b/i);
    expect(findConsumerRawLeakage(queueEmptyState.textContent || '')).toEqual([]);
    expect(onboardingPanel.textContent || '').not.toMatch(/sourceRefs|reasonCodes|fundamentals\.eps|provider_timeout|\bnews\b/i);
    expect(page.textContent || '').not.toMatch(/undefined|null|NaN/);
    expect(page.textContent || '').not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位建议|buy|sell|hold|recommendation|target price|stop loss|position sizing/i);
  });

  it('renders the Stock Structure entry as an empty state without calling a stock API', () => {
    renderRoute(<StockStructureDecisionEntryPage />, '/zh/stocks/structure-decision');

    const page = screen.getByTestId('stock-structure-entry-page');
    expect(page).toHaveTextContent('个股结构从研究队列进入');
    expect(page).toHaveTextContent('入口不调用');
    expect(page).toHaveTextContent('不展示原始载荷');
    expect(screen.getByRole('link', { name: '研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(page.textContent || '').not.toMatch(/买入|卖出|下单|目标价|止损|仓位建议/);
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
      missingEvidence: [],
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
    expect(snapshot).toHaveTextContent('同业相关性');
    expect(snapshot).toHaveTextContent('aligned');
    expect(snapshot).toHaveTextContent('Cloud software');
    expect(snapshot).toHaveTextContent('MSFT moved with ORCL across the comparison window.');
    expect(snapshot).toHaveTextContent('NVDA peer history is unavailable.');
    expect(snapshot).toHaveTextContent('Observation-only peer movement context; no personalized action instruction.');
    expect(snapshot).toHaveTextContent('Review whether peer alignment persists after the next close.');
    expect(page.textContent || '').not.toMatch(/raw|debug|provider|trace|sourceRef|reasonCode|requestId/i);
    expect(page.textContent || '').not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位建议|buy|sell|hold|recommendation|target price|stop loss|position sizing/i);
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
      missingEvidence: [],
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
          MSFT: [{ kind: 'daily_ohlcv', message: 'Daily OHLCV history is unavailable.' }],
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
    expect(packet).toHaveTextContent('对比证据包');
    expect(packet).toHaveTextContent('MSFT');
    expect(packet).toHaveTextContent('AAPL');
    expect(packet).toHaveTextContent('共享证据');
    expect(packet).toHaveTextContent('日线数据');
    expect(packet).toHaveTextContent('55-60 根可用');
    expect(packet).toHaveTextContent('分歧证据');
    expect(packet).toHaveTextContent('结构状态');
    expect(packet).toHaveTextContent('MSFT: mixed');
    expect(packet).toHaveTextContent('AAPL: breakout');
    expect(packet).toHaveTextContent('缺失证据');
    expect(packet).toHaveTextContent('MSFT');
    expect(packet).toHaveTextContent('Daily OHLCV history is unavailable.');
    expect(packet).toHaveTextContent('AAPL');
    expect(packet).toHaveTextContent('暂无缺口');
    expect(packet).toHaveTextContent('新鲜度');
    expect(packet).toHaveTextContent('0 根');
    expect(packet).toHaveTextContent('60 根');
    expect(packet).toHaveTextContent('置信上限 35');
    expect(packet).toHaveTextContent('仅研究观察');
    expect(packet).toHaveTextContent('非判断等级');
    expect(packet).toHaveTextContent('不排序');
    expect(packet).toHaveTextContent('不生成行动指令');
    expect(packet).toHaveTextContent('后续研究');
    expect(packet).toHaveTextContent('Add daily OHLCV evidence for MSFT before using divergence observations.');
    expect(packet.textContent || '').not.toMatch(/reasonCodes|policyVersion|local_db|sourceRef|requestId|trace|raw|debug|provider|schemaVersion/i);
    expect(packet.textContent || '').not.toMatch(/买入|卖出|持有|推荐|目标价|止损|仓位建议|buy now|sell now|hold|target price|stop loss|position sizing/i);
  });

  it('hides the stock structure compare evidence packet for a single symbol response', async () => {
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
    expect(screen.queryByTestId('symbol-compare-evidence-packet')).not.toBeInTheDocument();
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
    expect(page).toHaveTextContent('研究情景工作台');
    expect(page).toHaveTextContent('波动冲击');
    expect(page).toHaveTextContent('基准状态');
    expect(page).toHaveTextContent('情景输出');
    expect(page).toHaveTextContent('Breadth participation weakens quickly under the selected stress.');
    expect(screen.getByText('Gamma evidence status is unavailable, so gamma-sensitive conclusions remain capped.')).toBeInTheDocument();
    expect(page).toHaveTextContent('仅观察');
    expect(page).toHaveTextContent('非决策级');
    expect(screen.getByRole('link', { name: '决策驾驶舱' })).toHaveAttribute('href', '/zh/market/decision-cockpit');
    expect(screen.getByRole('button', { name: '波动冲击' })).toBeInTheDocument();
    await waitFor(() => expect(runScenarioLabMock).toHaveBeenCalledWith(expect.objectContaining({
      scenarioName: 'volatilitySpike',
      baseRegime: expect.objectContaining({
        regime: 'riskOn',
        confidence: 'medium',
      }),
    })));
    expect(page.textContent || '').not.toMatch(/买入|卖出|下单|目标价|止损|仓位建议/);
    expect(page.textContent || '').not.toMatch(/raw|debug|provider|schema/i);
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
    expect(page).toHaveTextContent('当前情景暂不可生成');
    expect(page).toHaveTextContent('Base regime evidence is missing or below the minimum driver coverage for scenario analysis.');
    await waitFor(() => expect(runScenarioLabMock).toHaveBeenCalledWith(expect.objectContaining({
      scenarioName: 'gammaUnavailable',
    })));
    expect(page.textContent || '').not.toMatch(/买入|卖出|下单|目标价|止损|仓位建议/);
  });
});
