import type React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ScenarioLabPage from '../ScenarioLabPage';
import { findConsumerRawLeakage } from '../../test-utils/consumerRawLeakageGuard';

const {
  languageState,
  getDecisionCockpitMock,
  runScenarioLabMock,
  writeTextMock,
} = vi.hoisted(() => ({
  languageState: { value: 'zh' as 'zh' | 'en' },
  getDecisionCockpitMock: vi.fn(),
  runScenarioLabMock: vi.fn(),
  writeTextMock: vi.fn(),
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

async function evaluateScenarioFromIdle(expectedCalls = 0) {
  const setup = await screen.findByTestId('scenario-lab-setup-idle');
  expect(runScenarioLabMock).toHaveBeenCalledTimes(expectedCalls);
  fireEvent.click(within(setup).getByRole('button', { name: '评估情景' }));
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
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

function makeAvailableScenarioResult(overrides: Record<string, unknown> = {}) {
  return {
    schemaVersion: 'market_scenario_lab_engine.v1',
    contractStatus: {
      state: 'degraded',
      label: 'Scenario constrained by evidence gaps',
      message: 'Scenario comparison is available, but incomplete evidence keeps the result observation-only.',
      observationOnly: true,
      decisionGrade: false,
    },
    observationOnly: true,
    decisionGrade: false,
    selectedScenario: {
      presetId: 'volatilitySpike',
      name: 'volatilitySpike',
      label: 'Volatility stress observation',
      category: 'Volatility stress',
      description: 'Stress volatility and breadth inputs to compare research-context sensitivity.',
      inputAssumptions: [
        'Uses market context supplied with the request.',
        'Compares deterministic driver changes without fetching fresh market data.',
      ],
      expectedDriverImpacts: [
        { driver: 'Volatility structure', direction: 'pressure', magnitude: 'high' },
        { driver: 'Breadth participation', direction: 'pressure', magnitude: 'medium' },
      ],
      evidenceLimits: ['Breadth and volatility observations need fresh confirmation before the frame can strengthen.'],
      observationOnly: true,
      decisionGrade: false,
    },
    baseMarketContext: {
      label: 'Decision Cockpit market context',
      message: 'Base regime context was supplied by the request and is treated as observation-only evidence.',
      evidenceState: 'degraded',
      scoringDriverCount: 6,
    },
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
    baselineReadiness: {
      status: 'partial',
      baselineSnapshot: {
        state: 'partial',
        available: false,
        lastUpdated: '2026-06-15T09:30:00Z',
        affectedComponents: ['baselineSnapshot'],
      },
      marketFrame: {
        state: 'available',
        available: true,
        lastUpdated: '2026-06-15T09:30:00Z',
        affectedComponents: [],
      },
      driverInputs: {
        state: 'partial',
        availableDriverKeys: ['breadthParticipation', 'volatilityStructure'],
        partialDriverKeys: [],
        missingDriverKeys: ['dealerGamma'],
        affectedDriverKeys: ['dealerGamma'],
      },
      evidenceCompleteness: {
        state: 'partial',
        gaps: ['baselineSnapshot', 'dealerGamma'],
      },
      observationOnly: true,
      blocked: false,
      affectedBaselineComponents: ['baselineSnapshot'],
      affectedDriverKeys: ['dealerGamma'],
      evidenceGaps: ['baselineSnapshot', 'dealerGamma'],
      lastUpdated: '2026-06-15T09:30:00Z',
    },
    baselineReadinessSummary: {
      baselineSnapshot: '基线快照部分可用',
      marketFrame: '当前框架可用',
      driverInputs: '驱动证据部分可用',
      boundary: '仅观察 / 非决策级',
    },
    readinessLabels: ['基准部分可用', '当前框架可用', '驱动证据部分可用', '证据边界', '仅观察'],
    confidenceDelta: -0.25,
    driverDeltas: {
      breadthParticipation: -75,
      volatilityStructure: -145,
    },
    changedDrivers: ['breadthParticipation', 'volatilityStructure'],
    scenarioSummary: ['Breadth participation weakens quickly under the selected stress.'],
    whatWouldConfirm: ['Score-grade evidence would need to show the stressed drivers moving together in the scenario direction.'],
    whatWouldInvalidate: ['The scenario frame weakens if score-grade evidence does not move with the selected shocks.'],
    evidenceLimits: ['Gamma evidence status is unavailable, so gamma-sensitive conclusions remain capped.'],
    noAdviceDisclosure: 'Research planning only; not a personalized decision basis.',
    ...overrides,
  };
}

describe('ScenarioLabPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    languageState.value = 'zh';
    writeTextMock.mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: writeTextMock },
    });
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
      baselineReadiness: {
        status: 'insufficient_data',
        baselineSnapshot: {
          state: 'insufficient_data',
          available: false,
          lastUpdated: '2026-06-15T09:30:00Z',
          affectedComponents: ['baselineSnapshot'],
        },
        marketFrame: {
          state: 'available',
          available: true,
          lastUpdated: '2026-06-15T09:30:00Z',
          affectedComponents: [],
        },
        driverInputs: {
          state: 'partial',
          availableDriverKeys: ['breadthParticipation', 'volatilityStructure'],
          partialDriverKeys: [],
          missingDriverKeys: ['dealerGamma'],
          affectedDriverKeys: ['dealerGamma'],
        },
        evidenceCompleteness: {
          state: 'partial',
          gaps: ['baselineSnapshot', 'dealerGamma', 'scoreAuthority'],
        },
        dataState: 'request_supplied',
        sampleState: 'none',
        scoreAuthority: 'observation_only',
        sourceAuthorityAllowed: false,
        authoritative: false,
        observationOnly: true,
        ready: false,
        partial: true,
        blocked: false,
        affectedBaselineComponents: ['baselineSnapshot'],
        affectedDriverKeys: ['dealerGamma'],
        evidenceGaps: ['baselineSnapshot', 'dealerGamma', 'scoreAuthority'],
        lastUpdated: '2026-06-15T09:30:00Z',
      },
      baselineReadinessSummary: {
        baselineSnapshot: '基线快照部分可用',
        marketFrame: '当前框架可用',
        driverInputs: '驱动证据部分可用',
        boundary: '仅观察 / 非决策级',
      },
      readinessLabels: ['基准部分可用', '当前框架可用', '驱动证据部分可用', '证据边界', '仅观察'],
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
    const setupIdle = await screen.findByTestId('scenario-lab-setup-idle');
    const setupOrder = within(setupIdle).getByTestId('scenario-productization-order');
    expect(setupOrder).toHaveTextContent('情景配置');
    expect(setupOrder).toHaveTextContent('显式评估');
    expect(setupOrder).toHaveTextContent('冲击影响图');
    expect(setupOrder).toHaveTextContent('资产敏感度');
    expect(setupOrder).toHaveTextContent('Watchlist 映射');
    expect(setupOrder).toHaveTextContent('解释路径');
    expect(setupOrder).toHaveTextContent('限制');
    expect(within(setupIdle).getByTestId('scenario-evaluation-not-persistence')).toHaveTextContent('评估不等于持久化');
    await evaluateScenarioFromIdle();

    const page = await screen.findByTestId('scenario-lab-page');
    const firstRead = await screen.findByTestId('scenario-lab-first-read-summary');

    expect(firstRead).toHaveTextContent('情景摘要');
    expect(firstRead).toHaveTextContent('数据不足，先保持观察。');
    expect(firstRead).not.toHaveTextContent('insufficient_data');
    expect(firstRead).toHaveTextContent('当前框架');
    expect(firstRead).toHaveTextContent('风险偏好观察');
    expect(firstRead).toHaveTextContent('波动冲击');
    expect(firstRead).toHaveTextContent('驱动变化');
    expect(firstRead).toHaveTextContent('波动结构 -145');
    expect(firstRead).toHaveTextContent('证据边界');
    expect(firstRead).toHaveTextContent('中 -> 低');
    expect(firstRead).toHaveTextContent('基线快照部分可用');
    expect(firstRead).toHaveTextContent('当前框架可用');
    expect(firstRead).toHaveTextContent('驱动证据部分可用');
    expect(firstRead).toHaveTextContent('待补证据');
    expect(firstRead).toHaveTextContent('需要更高质量证据共同确认受压驱动是否同向变化。');
    expect(firstRead).toHaveTextContent('仅观察 / 非决策级');
    expect(screen.getByRole('button', { name: '波动冲击' })).toBeInTheDocument();
    expect(page).toHaveTextContent('情景后的研究框架');
    expect(page).toHaveTextContent('最敏感的证据族');
    expect(page).toHaveTextContent('所选压力情景下，市场广度会较快转弱。');
    expect(page).toHaveTextContent('波动结构会转入偏防御状态。');
    expect(screen.getByTestId('scenario-evaluation-ephemeral-notice')).toHaveTextContent('不是可复用的持久基线');
    expect(screen.getByTestId('scenario-impact-map')).toBeInTheDocument();
    expect(screen.getByTestId('scenario-asset-sensitivity')).toBeInTheDocument();
    expect(screen.getByTestId('scenario-watchlist-mapping')).toHaveTextContent('Watchlist');
    expect(screen.getByTestId('scenario-explanation-path')).toBeInTheDocument();
    const registry = screen.getByTestId('scenario-evidence-pack-registry');
    expect(registry).toHaveTextContent('研究记录');
    expect(registry).toHaveTextContent('情景研究记录');
    expect(registry).not.toHaveTextContent('scenario-evidence-pack.v1');
    expect(registry).toHaveTextContent('Scenario Lab');
    expect(registry).toHaveTextContent('情景、基线状态、驱动变化、证据边界与紧凑结果摘要');
    expect(registry).toHaveTextContent('记录类型');
    expect(registry).toHaveTextContent('来源页面');
    expect(registry).not.toHaveTextContent('Artifact key');
    expect(registry).not.toHaveTextContent('Schema version');
    expect(registry).not.toHaveTextContent('Source surface');
    expect(screen.getByTestId('scenario-evidence-pack-copy')).toHaveTextContent('复制情景记录');
    expect(screen.getByTestId('scenario-evidence-pack-download')).toHaveTextContent('保存情景记录');
    expect(page.textContent || '').not.toMatch(/Artifact key|Source surface|scenario contract|frontend contract/i);

    await waitFor(() => expect(runScenarioLabMock).toHaveBeenCalledWith(expect.objectContaining({
      scenarioName: 'volatilitySpike',
      baseRegime: expect.objectContaining({
        regime: 'riskOn',
        confidence: 'medium',
      }),
    })));
  });

  it('shows evidence pack controls only after exportable scenario and baseline data exists', async () => {
    mockDecisionCockpit();
    runScenarioLabMock.mockResolvedValue(makeAvailableScenarioResult());

    renderRoute(<ScenarioLabPage />);

    expect(screen.queryByTestId('scenario-evidence-pack-copy')).not.toBeInTheDocument();
    await evaluateScenarioFromIdle();
    expect(await screen.findByTestId('scenario-evidence-pack-registry')).toBeInTheDocument();
    expect(screen.getByTestId('scenario-evidence-pack-copy')).toHaveTextContent('复制情景记录');
    expect(screen.getByTestId('scenario-evidence-pack-download')).toHaveTextContent('保存情景记录');
  });

  it('clears stale scenario output when a different preset is selected before explicit reevaluation', async () => {
    mockDecisionCockpit();
    runScenarioLabMock
      .mockResolvedValueOnce(makeAvailableScenarioResult())
      .mockResolvedValueOnce(makeAvailableScenarioResult({
        selectedScenario: {
          presetId: 'liquidityStress',
          name: 'liquidityStress',
          label: 'Liquidity stress observation',
          category: 'Liquidity stress',
          description: 'Stress liquidity and cross-asset inputs to compare research-context sensitivity.',
          inputAssumptions: ['Uses market context supplied with the request.'],
          expectedDriverImpacts: [
            { driver: 'Liquidity and credit', direction: 'pressure', magnitude: 'medium' },
          ],
          evidenceLimits: ['Liquidity stress remains observation-only without fresh confirmation.'],
          observationOnly: true,
          decisionGrade: false,
        },
        scenarioSummary: ['Liquidity stress keeps the frame observation-only.'],
      }));

    renderRoute(<ScenarioLabPage />);
    await evaluateScenarioFromIdle();
    expect(await screen.findByTestId('scenario-lab-first-read-summary')).toHaveTextContent('波动冲击');

    fireEvent.click(screen.getByRole('button', { name: '流动性压力' }));

    const setup = await screen.findByTestId('scenario-lab-setup-idle');
    expect(setup).toHaveTextContent('当前情景：流动性压力。');
    expect(screen.queryByTestId('scenario-lab-first-read-summary')).not.toBeInTheDocument();

    await evaluateScenarioFromIdle(1);
    await waitFor(() => expect(runScenarioLabMock).toHaveBeenLastCalledWith(expect.objectContaining({
      scenarioName: 'liquidityStress',
    })));
    expect(await screen.findByTestId('scenario-lab-first-read-summary')).toHaveTextContent('流动性压力');
  });

  it('copies deterministic scenario evidence pack JSON without advice or internal fields', async () => {
    mockDecisionCockpit();
    runScenarioLabMock.mockResolvedValue(makeAvailableScenarioResult({
      requestId: 'req-123',
      traceId: 'trace-123',
      rawPayload: { recommendation: 'buy now', targetPrice: 999 },
      debugDump: { cacheKey: 'secret-cache-key' },
    }));

    renderRoute(<ScenarioLabPage />);
    await evaluateScenarioFromIdle();

    fireEvent.click(await screen.findByTestId('scenario-evidence-pack-copy'));

    await waitFor(() => expect(writeTextMock).toHaveBeenCalledTimes(1));
    const copied = String(writeTextMock.mock.calls[0]?.[0] || '');
    const pack = asRecord(JSON.parse(copied) as unknown);
    const suppliedInputs = asRecord(pack.suppliedInputs);
    const baselineReadiness = asRecord(pack.baselineReadiness);
    const scenarioReadiness = asRecord(pack.scenarioReadiness);
    const compactResultSummary = asRecord(pack.compactResultSummary);
    const changedDrivers = Array.isArray(compactResultSummary.changedDrivers) ? compactResultSummary.changedDrivers : [];

    expect(pack.schemaVersion).toBe('scenario-evidence-pack.v1');
    expect(pack.generatedAt).toEqual(expect.any(String));
    expect(pack.appSurface).toBe('Scenario Lab / Scenario Baseline');
    expect(suppliedInputs.scenario).toMatchObject({
      key: 'volatilitySpike',
      name: 'volatilitySpike',
      label: 'Volatility stress observation',
    });
    expect(suppliedInputs.assumptions).toContain('Uses market context supplied via the input.');
    const shocks = Array.isArray(suppliedInputs.shocks) ? suppliedInputs.shocks : [];
    expect(shocks[0]).toMatchObject({
      driver: 'Volatility structure',
      direction: 'pressure',
      magnitude: 'high',
    });
    expect(baselineReadiness.summary).toMatchObject({
      baselineSnapshot: '基线快照部分可用',
      marketFrame: '当前框架可用',
      driverInputs: '驱动证据部分可用',
      boundary: '仅观察 / 非决策级',
    });
    expect(scenarioReadiness.labels).toContain('证据边界');
    expect(pack.availabilityState).toMatchObject({
      blocked: false,
      degraded: true,
      observationState: '仅观察',
    });
    expect(pack.resultCounts).toMatchObject({
      changedDriverCount: 2,
      scenarioSummaryCount: 1,
      confirmCount: 1,
      invalidateCount: 1,
    });
    expect(changedDrivers[0]).toMatchObject({
      driver: '广度参与',
      delta: '-75',
    });
    expect(copied).not.toMatch(/requestId|traceId|debug|rawPayload|cacheKey|credential|providerPayload|sourceAuthority|scoreAuthority/i);
    expect(copied).not.toMatch(/recommend|buy|sell|hold|target price|stop loss|position sizing|winner|best|optimal|买入|卖出|持有|目标价|止损|仓位|最优|最佳/i);
  });

  it('downloads the same scenario evidence pack JSON by default', async () => {
    let exportedBlob: Blob | undefined;
    const createObjectURL = vi.fn((blob: Blob) => {
      exportedBlob = blob;
      return 'blob:scenario-evidence-pack';
    });
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL,
      revokeObjectURL,
    });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    mockDecisionCockpit();
    runScenarioLabMock.mockResolvedValue(makeAvailableScenarioResult());

    renderRoute(<ScenarioLabPage />);
    await evaluateScenarioFromIdle();

    fireEvent.click(await screen.findByTestId('scenario-evidence-pack-download'));

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(exportedBlob).toBeInstanceOf(Blob);
    const exported = asRecord(JSON.parse(String(await exportedBlob?.text())) as unknown);
    const exportedInputs = asRecord(exported.suppliedInputs);
    const exportedScenario = asRecord(exportedInputs.scenario);
    expect(exported.schemaVersion).toBe('scenario-evidence-pack.v1');
    expect(exportedScenario.key).toBe('volatilitySpike');
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:scenario-evidence-pack');
  });

  it('marks missing evidence pack fields as unknown instead of inferring values', async () => {
    mockDecisionCockpit();
    runScenarioLabMock.mockResolvedValue(makeAvailableScenarioResult({
      selectedScenario: null,
      baselineReadiness: null,
      baselineReadinessSummary: undefined,
      readinessLabels: undefined,
      whatWouldConfirm: [],
      whatWouldInvalidate: [],
      evidenceLimits: [],
      scenarioSummary: [],
    }));

    renderRoute(<ScenarioLabPage />);
    await evaluateScenarioFromIdle();

    fireEvent.click(await screen.findByTestId('scenario-evidence-pack-copy'));

    await waitFor(() => expect(writeTextMock).toHaveBeenCalledTimes(1));
    const pack = asRecord(JSON.parse(String(writeTextMock.mock.calls[0]?.[0] || '{}')) as unknown);
    const suppliedInputs = asRecord(pack.suppliedInputs);
    const baselineReadiness = asRecord(pack.baselineReadiness);
    const scenarioReadiness = asRecord(pack.scenarioReadiness);
    const compactResultSummary = asRecord(pack.compactResultSummary);

    expect(suppliedInputs.symbols).toBe('待补证');
    expect(suppliedInputs.universe).toBe('待补证');
    expect(suppliedInputs.dateRange).toBe('待补证');
    expect(suppliedInputs.assumptions).toEqual(['待补证']);
    expect(suppliedInputs.shocks).toEqual(['待补证']);
    expect(baselineReadiness.summary).toMatchObject({
      baselineSnapshot: '待补证',
      marketFrame: '待补证',
      driverInputs: '待补证',
      boundary: '待补证',
    });
    expect(scenarioReadiness.labels).toEqual(['待补证']);
    expect(compactResultSummary.summary).toEqual(['待补证']);
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
      readinessLabels: ['基线证据待补齐', '仅观察'],
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
    await evaluateScenarioFromIdle();

    const page = await screen.findByTestId('scenario-lab-page');
    const firstRead = await screen.findByTestId('scenario-lab-first-read-summary');
    const secondaryState = await screen.findByTestId('scenario-lab-unavailable-state');

    expect(screen.queryByTestId('scenario-evidence-pack-copy')).not.toBeInTheDocument();
    expect(screen.queryByTestId('scenario-evidence-pack-download')).not.toBeInTheDocument();
    expect(screen.getByTestId('scenario-evidence-pack-registry')).toHaveTextContent('待补证');
    expect(screen.getByTestId('scenario-evidence-pack-registry-copy-blocked')).toBeDisabled();
    expect(writeTextMock).not.toHaveBeenCalled();
    expect(firstRead).toHaveTextContent('情景摘要');
    expect(firstRead).toHaveTextContent('当前框架');
    expect(firstRead).toHaveTextContent('低置信观察');
    expect(firstRead).toHaveTextContent('Gamma 缺口');
    expect(firstRead).toHaveTextContent('驱动变化');
    expect(firstRead).toHaveTextContent('情景待更新');
    expect(firstRead).toHaveTextContent('证据边界');
    expect(firstRead).toHaveTextContent('基线证据待补齐');
    expect(firstRead).toHaveTextContent('市场框架待补齐');
    expect(firstRead).toHaveTextContent('驱动证据待补齐');
    expect(firstRead).toHaveTextContent('仅观察 / 非决策级');
    expect(Boolean(firstRead.compareDocumentPosition(secondaryState) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(secondaryState).toHaveTextContent('情景待更新');
    expect(secondaryState).toHaveTextContent('基准待确认，暂不展开输出。');
    expect(secondaryState).toHaveTextContent('待补证据：市场框架、驱动证据、数据新鲜度。');
    expect(within(secondaryState).getByRole('link', { name: '查看市场概览' })).toHaveAttribute('href', '/zh/market-overview');
    expect(within(secondaryState).getByRole('link', { name: '返回研究雷达' })).toHaveAttribute('href', '/zh/research/radar');
    expect(screen.getByRole('button', { name: 'Gamma 缺口' })).toBeInTheDocument();

    const visibleText = page.textContent || '';
    expect(visibleText).not.toMatch(/insufficient_data|unavailable|degraded|insufficient|provider|runtime|credential|sourceAuthority|debug/i);
    expect(visibleText).not.toMatch(/not personalized financial advice|not an instruction|buy|sell|hold|target price|stop-loss|position sizing|买入|卖出|持有|目标价|止损|仓位|建仓|加仓|减仓/i);
    expect(findConsumerRawLeakage(visibleText)).toEqual([]);
  });

  it('shows stale market frame and partial baseline copy without claiming a durable baseline', async () => {
    mockDecisionCockpit({
      marketRegimeDecision: {
        regime: 'mixed',
        confidence: 'medium',
        confidenceScore: 0.52,
        driverScores: {
          dealerGamma: { score: 0, evidenceState: 'unavailable' },
          breadthParticipation: { score: 44, evidenceState: 'score_grade' },
          volatilityStructure: { score: 48, evidenceState: 'score_grade' },
          ratesDollar: { score: 32, evidenceState: 'score_grade' },
          liquidityCredit: { score: 38, evidenceState: 'score_grade' },
          crossAssetRisk: { score: 34, evidenceState: 'score_grade' },
        },
      },
      dataQuality: { status: 'partial' },
    });
    runScenarioLabMock.mockResolvedValue({
      schemaVersion: 'market_scenario_lab_engine.v1',
      baseRegime: {
        regime: 'mixed',
        confidence: 'medium',
        confidenceScore: 0.52,
      },
      scenarioRegime: {
        regime: 'mixed',
        confidence: 'medium',
        confidenceScore: 0.41,
      },
      baselineReadiness: {
        status: 'partial',
        baselineSnapshot: {
          state: 'partial',
          available: false,
          affectedComponents: ['baselineSnapshot'],
        },
        marketFrame: {
          state: 'stale',
          available: false,
          affectedComponents: ['marketFrame'],
        },
        driverInputs: {
          state: 'partial',
          availableDriverKeys: ['breadthParticipation', 'volatilityStructure', 'ratesDollar'],
          partialDriverKeys: ['liquidityCredit'],
          missingDriverKeys: ['dealerGamma'],
          affectedDriverKeys: ['liquidityCredit', 'dealerGamma'],
        },
        evidenceCompleteness: {
          state: 'partial',
          gaps: ['baselineSnapshot', 'marketFrame', 'liquidityCredit'],
        },
        dataState: 'request_supplied',
        sampleState: 'none',
        scoreAuthority: 'observation_only',
        sourceAuthorityAllowed: false,
        authoritative: false,
        observationOnly: true,
        ready: false,
        partial: true,
        blocked: false,
        affectedBaselineComponents: ['baselineSnapshot', 'marketFrame'],
        affectedDriverKeys: ['liquidityCredit', 'dealerGamma'],
        evidenceGaps: ['baselineSnapshot', 'marketFrame', 'liquidityCredit', 'scoreAuthority'],
        lastUpdated: '2026-06-15T09:30:00Z',
      },
      baselineReadinessSummary: {
        baselineSnapshot: '基线快照部分可用',
        marketFrame: '市场框架已过期',
        driverInputs: '驱动证据部分可用',
        boundary: '仅观察 / 非决策级',
      },
      readinessLabels: ['基线快照部分可用', '市场框架已过期', '驱动证据部分可用', '证据边界', '仅观察'],
      confidenceDelta: -0.11,
      driverDeltas: {
        breadthParticipation: -12,
        volatilityStructure: -8,
        liquidityCredit: -24,
      },
      changedDrivers: ['breadthParticipation', 'volatilityStructure', 'liquidityCredit'],
      scenarioSummary: ['市场框架已过期，当前情景只能保留观察。'],
      whatWouldConfirm: ['补齐最新市场框架后，再复核基线是否可复用。'],
      whatWouldInvalidate: ['如果驱动证据继续缺失，情景仍保持观察级。'],
      evidenceLimits: ['市场框架已过期，需补充最新基准证据。'],
      noAdviceDisclosure: 'Research planning only; not a personalized decision basis.',
    });

    renderRoute(<ScenarioLabPage />);
    await evaluateScenarioFromIdle();

    const firstRead = await screen.findByTestId('scenario-lab-first-read-summary');

    expect(firstRead).toHaveTextContent('基线快照部分可用');
    expect(firstRead).toHaveTextContent('市场框架已过期');
    expect(firstRead).toHaveTextContent('驱动证据部分可用');
    expect(firstRead).toHaveTextContent('仅观察 / 非决策级');
    expect(firstRead).toHaveTextContent('待补证据');
    expect(firstRead).toHaveTextContent('补齐最新市场框架后，再复核基线是否可复用。');
  });

  it('renders authoritative baseline copy without observation-only overclaiming', async () => {
    mockDecisionCockpit({
      marketRegimeDecision: {
        regime: 'riskOn',
        confidence: 'high',
        confidenceScore: 0.84,
        driverScores: {
          dealerGamma: { score: 18, evidenceState: 'score_grade' },
          breadthParticipation: { score: 64, evidenceState: 'score_grade' },
          volatilityStructure: { score: 71, evidenceState: 'score_grade' },
          ratesDollar: { score: 53, evidenceState: 'score_grade' },
          liquidityCredit: { score: 61, evidenceState: 'score_grade' },
          crossAssetRisk: { score: 49, evidenceState: 'score_grade' },
          sectorThemeRotation: { score: 57, evidenceState: 'score_grade' },
          eventCatalyst: { score: 42, evidenceState: 'score_grade' },
        },
      },
      dataQuality: { status: 'ready' },
    });
    runScenarioLabMock.mockResolvedValue({
      schemaVersion: 'market_scenario_lab_engine.v1',
      baseRegime: {
        regime: 'riskOn',
        confidence: 'high',
        confidenceScore: 0.84,
      },
      scenarioRegime: {
        regime: 'riskOn',
        confidence: 'high',
        confidenceScore: 0.82,
      },
      baselineReadiness: {
        status: 'ready',
        baselineSnapshot: {
          state: 'available',
          available: true,
          lastUpdated: '2026-06-15T09:30:00Z',
          affectedComponents: [],
        },
        marketFrame: {
          state: 'available',
          available: true,
          lastUpdated: '2026-06-15T09:30:00Z',
          affectedComponents: [],
        },
        driverInputs: {
          state: 'available',
          availableDriverKeys: [
            'dealerGamma',
            'breadthParticipation',
            'volatilityStructure',
            'ratesDollar',
            'liquidityCredit',
            'crossAssetRisk',
            'sectorThemeRotation',
            'eventCatalyst',
          ],
          partialDriverKeys: [],
          missingDriverKeys: [],
          affectedDriverKeys: [],
        },
        evidenceCompleteness: {
          state: 'ready',
          gaps: [],
        },
        dataState: 'real_cached',
        sampleState: 'none',
        scoreAuthority: 'authoritative',
        sourceAuthorityAllowed: true,
        authoritative: true,
        observationOnly: false,
        ready: true,
        partial: false,
        blocked: false,
        affectedBaselineComponents: [],
        affectedDriverKeys: [],
        evidenceGaps: [],
        lastUpdated: '2026-06-15T09:30:00Z',
      },
      baselineReadinessSummary: {
        baselineSnapshot: '基准可用',
        marketFrame: '当前框架可用',
        driverInputs: '驱动证据可用',
        boundary: '可复用基线',
      },
      readinessLabels: ['基准可用', '当前框架可用', '驱动证据可用', '情景摘要可用'],
      confidenceDelta: -0.02,
      driverDeltas: {
        breadthParticipation: 4,
        volatilityStructure: 2,
      },
      changedDrivers: ['breadthParticipation', 'volatilityStructure'],
      scenarioSummary: ['基线可复用，情景仅做小幅观察。'],
      whatWouldConfirm: ['高质量证据持续保持完整。'],
      whatWouldInvalidate: ['若基线失去可复用性，则情景边界应回到观察级。'],
      evidenceLimits: ['暂无额外证据限制。'],
      noAdviceDisclosure: 'Research planning only; not a personalized decision basis.',
    });

    renderRoute(<ScenarioLabPage />);
    await evaluateScenarioFromIdle();

    const firstRead = await screen.findByTestId('scenario-lab-first-read-summary');

    expect(firstRead).toHaveTextContent('基准可用');
    expect(firstRead).toHaveTextContent('当前框架可用');
    expect(firstRead).toHaveTextContent('驱动证据可用');
    expect(firstRead).toHaveTextContent('可复用基线');
    expect(firstRead).not.toHaveTextContent('仅观察 / 非决策级');
  });
});
