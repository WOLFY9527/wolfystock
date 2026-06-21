import type React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ScenarioLabPage from '../ScenarioLabPage';
import { findConsumerRawLeakage } from '../../test-utils/consumerRawLeakageGuard';

const {
  languageState,
  getDecisionCockpitMock,
  runScenarioLabMock,
} = vi.hoisted(() => ({
  languageState: { value: 'zh' as 'zh' | 'en' },
  getDecisionCockpitMock: vi.fn(),
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

vi.mock('../../api/scenarioLab', () => ({
  scenarioLabApi: {
    runScenarioLab: (...args: unknown[]) => runScenarioLabMock(...args),
  },
}));

function renderRoute(ui: React.ReactElement, path = '/zh/scenario-lab') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      {ui}
    </MemoryRouter>,
  );
}

function mockDecisionCockpit(overrides: Record<string, unknown> = {}) {
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
        crossAssetRisk: { score: 28, evidenceState: 'score_grade' },
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
    ...overrides,
  });
}

describe('ScenarioLabPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    languageState.value = 'zh';
  });

  it('leads the first viewport with a concise scenario summary while preserving selector and output', async () => {
    mockDecisionCockpit();
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
      readinessLabels: ['基准部分可用', '当前框架可用', '驱动待补', '证据边界', '仅观察'],
      confidenceDelta: -0.25,
      driverDeltas: {
        dealerGamma: 0,
        breadthParticipation: -75,
        volatilityStructure: -145,
        crossAssetRisk: -40,
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

    renderRoute(<ScenarioLabPage />);

    const page = await screen.findByTestId('scenario-lab-page');
    const firstRead = await screen.findByTestId('scenario-lab-first-read-summary');

    expect(firstRead).toHaveTextContent('情景摘要');
    expect(firstRead).toHaveTextContent('当前框架');
    expect(firstRead).toHaveTextContent('风险偏好观察');
    expect(firstRead).toHaveTextContent('波动冲击');
    expect(firstRead).toHaveTextContent('驱动变化');
    expect(firstRead).toHaveTextContent('波动结构 -145');
    expect(firstRead).toHaveTextContent('证据边界');
    expect(firstRead).toHaveTextContent('中 -> 低');
    expect(firstRead).toHaveTextContent('基准部分可用');
    expect(firstRead).toHaveTextContent('当前框架可用');
    expect(firstRead).toHaveTextContent('驱动待补');
    expect(firstRead).toHaveTextContent('待补证据');
    expect(firstRead).toHaveTextContent('需要更高质量证据共同确认受压驱动是否同向变化。');
    expect(screen.getByRole('button', { name: '波动冲击' })).toBeInTheDocument();
    expect(page).toHaveTextContent('情景后的研究框架');
    expect(page).toHaveTextContent('所选压力情景下，市场广度会较快转弱。');
    expect(page).toHaveTextContent('波动结构会转入偏防御状态。');

    await waitFor(() => expect(runScenarioLabMock).toHaveBeenCalledWith(expect.objectContaining({
      scenarioName: 'volatilitySpike',
      baseRegime: expect.objectContaining({
        regime: 'riskOn',
        confidence: 'medium',
      }),
    })));
  });

  it('keeps unavailable or gated output secondary and compact without raw labels', async () => {
    mockDecisionCockpit({
      marketRegimeDecision: {
        regime: 'lowConfidence',
        confidence: 'low',
        confidenceScore: 0,
        driverScores: {
          breadthParticipation: { score: 0, evidenceState: 'unavailable' },
          volatilityStructure: { score: 0, evidenceState: 'unavailable' },
        },
      },
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
      readinessLabels: ['基准待确认', '驱动待补', '证据边界', '情景待更新', '仅观察'],
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
    const firstRead = await screen.findByTestId('scenario-lab-first-read-summary');
    const secondaryState = await screen.findByTestId('scenario-lab-unavailable-state');

    expect(firstRead).toHaveTextContent('情景摘要');
    expect(firstRead).toHaveTextContent('当前框架');
    expect(firstRead).toHaveTextContent('低置信观察');
    expect(firstRead).toHaveTextContent('Gamma 缺口');
    expect(firstRead).toHaveTextContent('驱动变化');
    expect(firstRead).toHaveTextContent('情景待更新');
    expect(firstRead).toHaveTextContent('证据边界');
    expect(firstRead).toHaveTextContent('基准待确认');
    expect(firstRead).toHaveTextContent('驱动待补');
    expect(firstRead).toHaveTextContent('证据边界');
    expect(firstRead).toHaveTextContent('待补证据');
    expect(firstRead).toHaveTextContent('市场框架、驱动证据、数据新鲜度');
    expect(Boolean(firstRead.compareDocumentPosition(secondaryState) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(secondaryState).toHaveTextContent('情景待更新');
    expect(secondaryState).toHaveTextContent('基准待确认，暂不展开输出。');
    expect(secondaryState).toHaveTextContent('待补证据：市场框架、驱动证据、数据新鲜度。');
    expect(within(secondaryState).getByRole('link', { name: '查看市场概览' })).toHaveAttribute('href', '/zh/market-overview');
    expect(within(secondaryState).getByRole('link', { name: '返回研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(screen.getByRole('button', { name: 'Gamma 缺口' })).toBeInTheDocument();

    const visibleText = page.textContent || '';
    expect(visibleText).not.toMatch(/unavailable|degraded|insufficient|provider|runtime|credential|sourceAuthority|debug/i);
    expect(visibleText).not.toMatch(/not personalized financial advice|not an instruction|buy|sell|hold|target price|stop-loss|position sizing|买入|卖出|持有|目标价|止损|仓位|建仓|加仓|减仓/i);
    expect(findConsumerRawLeakage(visibleText)).toEqual([]);
  });
});
