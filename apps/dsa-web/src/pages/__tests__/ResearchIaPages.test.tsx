import type React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import MarketDecisionCockpitPage from '../MarketDecisionCockpitPage';
import ResearchRadarPage from '../ResearchRadarPage';
import ScenarioLabPage from '../ScenarioLabPage';
import StockStructureDecisionEntryPage from '../StockStructureDecisionEntryPage';

const { languageState, getDecisionCockpitMock, getResearchRadarMock } = vi.hoisted(() => ({
  languageState: { value: 'zh' as 'zh' | 'en' },
  getDecisionCockpitMock: vi.fn(),
  getResearchRadarMock: vi.fn(),
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

vi.mock('../../api/researchRadar', () => ({
  researchRadarApi: {
    getResearchRadar: (...args: unknown[]) => getResearchRadarMock(...args),
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

  it('renders the market decision cockpit as the primary market-structure entry with Options/Gamma observation boundaries', async () => {
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

    renderRoute(<MarketDecisionCockpitPage />, '/zh/market/decision-cockpit');

    const page = await screen.findByTestId('market-decision-cockpit-page');
    expect(page).toHaveTextContent('市场结构、定位语境与研究队列');
    expect(page).toHaveTextContent('observationOnly');
    expect(page).toHaveTextContent('true');
    expect(page).toHaveTextContent('decisionGrade');
    expect(page).toHaveTextContent('false');
    expect(page).toHaveTextContent('missing_contracts');
    expect(screen.getByRole('link', { name: '研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(screen.getByRole('link', { name: '情景实验室' })).toHaveAttribute('href', '/zh/scenario-lab');
    expect(page.textContent || '').not.toMatch(/买入|卖出|下单|目标价|止损|仓位建议/);
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
    expect(page).toHaveTextContent('ALFA');
    expect(page).toHaveTextContent('相对强弱改善');
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

  it('renders Scenario Lab as a static placeholder with explicit non-decision-grade state', () => {
    renderRoute(<ScenarioLabPage />, '/zh/scenario-lab');

    const page = screen.getByTestId('scenario-lab-page');
    expect(page).toHaveTextContent('只读情景工作台占位入口');
    expect(page).toHaveTextContent('decisionGrade=false');
    expect(page).toHaveTextContent('observationOnly=true');
    expect(screen.getByText('预留给只读情景对照；当前占位页不调用后端契约。')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '决策驾驶舱' })).toHaveAttribute('href', '/zh/market/decision-cockpit');
    expect(page.textContent || '').not.toMatch(/买入|卖出|下单|目标价|止损|仓位建议/);
  });
});
