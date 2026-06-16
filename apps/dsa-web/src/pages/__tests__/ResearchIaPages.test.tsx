import type React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import MarketDecisionCockpitPage from '../MarketDecisionCockpitPage';
import ResearchRadarPage from '../ResearchRadarPage';
import ScenarioLabPage from '../ScenarioLabPage';
import StockStructureDecisionEntryPage from '../StockStructureDecisionEntryPage';

const { languageState, getDecisionCockpitMock, getDailyIntelligenceMock, getResearchRadarMock, runScenarioLabMock } = vi.hoisted(() => ({
  languageState: { value: 'zh' as 'zh' | 'en' },
  getDecisionCockpitMock: vi.fn(),
  getDailyIntelligenceMock: vi.fn(),
  getResearchRadarMock: vi.fn(),
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

const renderRoute = (ui: React.ReactElement, path: string) => render(
  <MemoryRouter initialEntries={[path]}>
    {ui}
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
        gammaEvidenceStatus: 'unavailable',
        observationOnly: true,
        decisionGrade: false,
        missingEvidence: [{ code: 'missing_contracts' }],
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
    expect(page).toHaveTextContent('observationOnly');
    expect(page).toHaveTextContent('true');
    expect(page).toHaveTextContent('decisionGrade');
    expect(page).toHaveTextContent('false');
    expect(page).toHaveTextContent('missing_contracts');
    expect(screen.getByRole('link', { name: '研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(screen.getAllByRole('link', { name: '查看证据：研究雷达' }).some((link) => link.getAttribute('href') === '/zh/research/radar')).toBe(true);
    expect(screen.getByRole('link', { name: '查看证据：扫描器' })).toHaveAttribute('href', '/zh/scanner');
    expect(screen.getAllByRole('link', { name: '查看证据：结构详情' })[0]).toHaveAttribute('href', '/zh/stocks/ALFA/structure-decision');
    expect(screen.getByRole('link', { name: '情景实验室' })).toHaveAttribute('href', '/zh/scenario-lab');
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

  it('renders the Stock Structure entry as an empty state without calling a stock API', () => {
    renderRoute(<StockStructureDecisionEntryPage />, '/zh/stocks/structure-decision');

    const page = screen.getByTestId('stock-structure-entry-page');
    expect(page).toHaveTextContent('个股结构从研究队列进入');
    expect(page).toHaveTextContent('入口不调用');
    expect(page).toHaveTextContent('不展示原始载荷');
    expect(screen.getByRole('link', { name: '研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(page.textContent || '').not.toMatch(/买入|卖出|下单|目标价|止损|仓位建议/);
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
