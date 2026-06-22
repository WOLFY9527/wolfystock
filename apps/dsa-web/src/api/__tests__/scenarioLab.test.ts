import { beforeEach, describe, expect, it, vi } from 'vitest';

const { post } = vi.hoisted(() => ({
  post: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    post,
  },
}));

describe('scenarioLabApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('posts a scenario request and normalizes the response payload', async () => {
    const { scenarioLabApi } = await import('../scenarioLab');

    post.mockResolvedValueOnce({
      data: {
        schema_version: 'market_scenario_lab_engine.v1',
        base_regime: {
          regime: 'riskOn',
          confidence: 'medium',
          confidence_score: 0.68,
        },
        scenario_regime: {
          regime: 'mixed',
          confidence: 'low',
          confidence_score: 0.43,
          status: 'partial',
        },
        contract_status: {
          state: 'degraded',
          label: 'Scenario constrained by evidence gaps',
          message: 'Scenario comparison is available, but incomplete evidence keeps the result observation-only.',
        },
        selected_scenario: {
          preset_id: 'volatilitySpike',
          name: 'volatilitySpike',
          label: 'Volatility stress observation',
          category: 'Volatility stress',
          description: 'Stress volatility and breadth inputs to compare research-context sensitivity.',
          input_assumptions: [
            'Uses market context supplied with the request.',
            'Compares deterministic driver changes without fetching fresh market data.',
          ],
          expected_driver_impacts: [
            { driver: 'Volatility structure', direction: 'pressure', magnitude: 'high' },
            { driver: 'Breadth participation', direction: 'pressure', magnitude: 'medium' },
          ],
          evidence_limits: ['Breadth and volatility observations need fresh confirmation.'],
          raw_payload: { debug: true },
        },
        base_market_context: {
          label: 'Decision Cockpit market context',
          message: 'Base regime context was supplied by the request and is treated as observation-only evidence.',
          evidence_state: 'degraded',
          scoring_driver_count: 6,
        },
        baseline_readiness: {
          status: 'blocked',
          baseline_snapshot: {
            state: 'missing',
            available: false,
            affected_components: ['baselineSnapshot'],
          },
          market_frame: {
            state: 'available',
            available: true,
            last_updated: '2026-06-15T09:30:00Z',
            affected_components: [],
          },
          driver_inputs: {
            state: 'partial',
            available_driver_keys: ['breadthParticipation', 'volatilityStructure'],
            partial_driver_keys: [],
            missing_driver_keys: ['dealerGamma'],
            affected_driver_keys: ['dealerGamma'],
          },
          evidence_completeness: {
            state: 'blocked',
            gaps: ['baselineSnapshot', 'dealerGamma', 'scoreAuthority'],
          },
          data_state: 'request_supplied',
          sample_state: 'none',
          score_authority: 'observation_only',
          source_authority_allowed: false,
          authoritative: false,
          observation_only: true,
          ready: false,
          partial: false,
          blocked: true,
          affected_baseline_components: ['baselineSnapshot'],
          affected_driver_keys: ['dealerGamma'],
          evidence_gaps: ['baselineSnapshot', 'dealerGamma', 'scoreAuthority'],
          last_updated: '2026-06-15T09:30:00Z',
        },
        confidence_delta: -0.25,
        driver_deltas: {
          breadth_participation: -75,
          volatility_structure: -145,
          cross_asset_risk: -40,
        },
        changed_drivers: ['breadthParticipation', 'volatilityStructure', 'crossAssetRisk'],
        scenario_summary: ['Breadth weakens.'],
        what_would_confirm: ['Need score-grade confirmation.'],
        what_would_invalidate: ['Drivers do not move together.'],
        evidence_limits: ['Gamma evidence remains capped.'],
        no_advice_disclosure: 'Research planning only; not a personalized decision basis.',
      },
    });

    const payload = await scenarioLabApi.runScenarioLab({
      baseRegime: {
        regime: 'riskOn',
        confidence: 'medium',
        confidenceScore: 0.68,
      },
      scenarioName: 'volatilitySpike',
    });

    expect(post).toHaveBeenCalledWith('/api/v1/market/scenario-lab', {
      baseRegime: {
        regime: 'riskOn',
        confidence: 'medium',
        confidenceScore: 0.68,
      },
      scenarioName: 'volatilitySpike',
    });
    expect(payload.schemaVersion).toBe('market_scenario_lab_engine.v1');
    expect(payload.contractStatus?.state).toBe('degraded');
    expect(payload.selectedScenario).toMatchObject({
      presetId: 'volatilitySpike',
      name: 'volatilitySpike',
      label: 'Volatility stress observation',
      inputAssumptions: [
        'Uses market context supplied with the request.',
        'Compares deterministic driver changes without fetching fresh market data.',
      ],
      expectedDriverImpacts: [
        { driver: 'Volatility structure', direction: 'pressure', magnitude: 'high' },
        { driver: 'Breadth participation', direction: 'pressure', magnitude: 'medium' },
      ],
    });
    expect(JSON.stringify(payload.selectedScenario)).not.toMatch(/raw_payload|debug/i);
    expect(payload.baseMarketContext).toMatchObject({
      label: 'Decision Cockpit market context',
      evidenceState: 'degraded',
      scoringDriverCount: 6,
    });
    expect(payload.baseRegime.confidenceScore).toBe(0.68);
    expect(payload.scenarioRegime.status).toBe('partial');
    expect(payload.baselineReadiness?.status).toBe('blocked');
    expect(payload.baselineReadiness?.baselineSnapshot?.state).toBe('missing');
    expect(payload.baselineReadiness?.driverInputs?.affectedDriverKeys).toEqual(['dealerGamma']);
    expect(payload.baselineReadinessSummary).toEqual({
      baselineSnapshot: '基线快照待补齐',
      marketFrame: '当前框架可用',
      driverInputs: '驱动证据部分可用',
      boundary: '仅观察 / 非决策级',
    });
    expect(payload.readinessLabels).toEqual(['基线证据待补齐', '当前框架可用', '驱动证据部分可用', '证据边界', '情景待更新', '仅观察']);
    expect(payload.driverDeltas.breadthParticipation).toBe(-75);
    expect(payload.driverDeltas.volatilityStructure).toBe(-145);
    expect(payload.evidenceLimits).toEqual(['Gamma evidence remains capped.']);
  });

  it('supplies safe defaults for unavailable scenario payloads', async () => {
    const { scenarioLabApi } = await import('../scenarioLab');

    post.mockResolvedValueOnce({
      data: {
        schema_version: 'market_scenario_lab_engine.v1',
        base_regime: {
          regime: 'lowConfidence',
          confidence: 'low',
          confidence_score: 0,
        },
        scenario_regime: {
          regime: 'lowConfidence',
          confidence: 'low',
          confidence_score: 0,
          status: 'unavailable',
        },
        confidence_delta: 0,
        driver_deltas: null,
        changed_drivers: null,
        scenario_summary: null,
        what_would_confirm: null,
        what_would_invalidate: null,
        evidence_limits: ['Base regime evidence is missing.'],
        no_advice_disclosure: null,
      },
    });

    const payload = await scenarioLabApi.runScenarioLab({
      driverScores: {
        breadthParticipation: 0,
      },
      scenarioName: 'gammaUnavailable',
    });

    expect(payload.driverDeltas).toEqual({});
    expect(payload.changedDrivers).toEqual([]);
    expect(payload.scenarioSummary).toEqual([]);
    expect(payload.whatWouldConfirm).toEqual([]);
    expect(payload.whatWouldInvalidate).toEqual([]);
    expect(payload.noAdviceDisclosure).toBeNull();
    expect(payload.evidenceLimits).toEqual(['Base regime evidence is missing.']);
    expect(payload.baselineReadiness).toBeNull();
    expect(payload.baselineReadinessSummary).toEqual({
      baselineSnapshot: '基线证据待补齐',
      marketFrame: '市场框架待补齐',
      driverInputs: '驱动证据待补齐',
      boundary: '仅观察 / 非决策级',
    });
    expect(payload.readinessLabels).toEqual(['基线证据待补齐', '仅观察']);
  });

  it('maps demo or sample readiness into consumer-safe labels only', async () => {
    const { scenarioLabApi } = await import('../scenarioLab');

    post.mockResolvedValueOnce({
      data: {
        schema_version: 'market_scenario_lab_engine.v1',
        base_regime: {
          regime: 'riskOn',
          confidence: 'medium',
          confidence_score: 0.62,
        },
        scenario_regime: {
          regime: 'mixed',
          confidence: 'low',
          confidence_score: 0.42,
        },
        baseline_readiness: {
          status: 'partial',
          baseline_snapshot: {
            state: 'partial',
            available: false,
            affected_components: ['baselineSnapshot'],
          },
          market_frame: {
            state: 'available',
            available: true,
            affected_components: [],
          },
          driver_inputs: {
            state: 'partial',
            available_driver_keys: ['breadthParticipation'],
            partial_driver_keys: [],
            missing_driver_keys: ['eventCatalyst'],
            affected_driver_keys: ['eventCatalyst'],
          },
          evidence_completeness: {
            state: 'partial',
            gaps: ['scenarioDataBoundary', 'eventCatalyst'],
          },
          data_state: 'demo_static_sample',
          sample_state: 'sample',
          score_authority: 'observation_only',
          source_authority_allowed: false,
          authoritative: false,
          observation_only: true,
          ready: false,
          partial: true,
          blocked: false,
          affected_baseline_components: ['baselineSnapshot'],
          affected_driver_keys: ['eventCatalyst'],
          evidence_gaps: ['scenarioDataBoundary', 'eventCatalyst'],
        },
        confidence_delta: -0.2,
        driver_deltas: {},
        changed_drivers: [],
        scenario_summary: [],
        what_would_confirm: [],
        what_would_invalidate: [],
        evidence_limits: [],
        no_advice_disclosure: 'Research planning only; not a personalized decision basis.',
      },
    });

    const payload = await scenarioLabApi.runScenarioLab({ scenarioName: 'volatilitySpike' });

    expect(payload.readinessLabels).toEqual([
      '基准部分可用',
      '当前框架可用',
      '驱动证据部分可用',
      '证据边界',
      '演示样本',
      '仅观察',
      '情景摘要可用',
    ]);
    expect(payload.baselineReadinessSummary).toEqual({
      baselineSnapshot: '基线快照部分可用',
      marketFrame: '当前框架可用',
      driverInputs: '驱动证据部分可用',
      boundary: '仅观察 / 非决策级',
    });
    expect(payload.readinessLabels.join(' ')).not.toMatch(/sourceAuthority|observation_only|demo_static_sample|sample/i);
  });
});
