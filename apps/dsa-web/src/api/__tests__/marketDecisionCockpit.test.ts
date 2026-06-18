import { beforeEach, describe, expect, it, vi } from 'vitest';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
  },
}));

describe('marketDecisionCockpitApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads and normalizes the market decision cockpit payload', async () => {
    const { marketDecisionCockpitApi } = await import('../marketDecisionCockpit');

    get.mockResolvedValueOnce({
      data: {
        schema_version: 'market_decision_cockpit.v1',
        generated_at: '2026-06-15T00:00:00Z',
        market_regime_decision: {
          regime: 'riskOn',
          confidence: 'medium',
          confidence_score: 0.68,
          driver_scores: {
            breadth_participation: {
              score: 62,
              evidence_state: 'partial',
              reasons: ['Breadth still needs confirmation.'],
            },
          },
          explanation: {
            why_this_regime: ['Breadth stabilized.'],
            what_confirms_it: ['Cross-asset pressure eased.'],
            what_invalidates_it: ['Breadth falls back quickly.'],
          },
          invalidation_conditions: ['Breadth falls back quickly.'],
          research_priorities: {
            watch_today: ['Confirm breadth participation.'],
            needs_more_evidence: ['Options data unavailable.'],
            investigate_next: ['Review research queue.'],
          },
        },
        research_queue_preview: {
          top_candidates: [
            {
              ticker: 'ALFA',
              priority: 'high',
              research_bias: 'strengthContinuation',
            },
          ],
          queue_quality: 'mixed',
          evidence_gaps: ['research_candidates_unavailable'],
          preview_only: true,
          degraded_state: {
            status: 'partial',
            reason_codes: ['research_candidates_unavailable'],
          },
        },
        options_structure_status: {
          gamma_evidence_status: 'unavailable',
          observation_only: true,
          decision_grade: false,
          missing_evidence: [{ code: 'missing_contracts' }],
          blocked_reason_codes: ['option_chain_unavailable'],
        },
        cockpit_summary: {
          what_changed: ['Breadth improved.'],
          why_it_matters: ['Queue triage changed.'],
          what_to_watch: ['Watch breadth participation.'],
          confidence_limits: ['Gamma evidence is unavailable.'],
        },
        no_advice_disclosure: 'Research context only.',
        data_quality: {
          status: 'degraded',
          reason_codes: ['option_chain_unavailable'],
        },
      },
    });

    const payload = await marketDecisionCockpitApi.getDecisionCockpit();

    expect(get).toHaveBeenCalledWith('/api/v1/market/decision-cockpit');
    expect(payload.schemaVersion).toBe('market_decision_cockpit.v1');
    expect(payload.marketRegimeDecision.confidenceScore).toBe(0.68);
    expect(payload.marketRegimeDecision.driverScores?.breadthParticipation?.score).toBe(62);
    expect(payload.researchQueuePreview.topCandidates[0]?.researchBias).toBe('strengthContinuation');
    expect(payload.optionsStructureStatus.blockedReasonCodes).toEqual(['option_chain_unavailable']);
    expect(payload.cockpitSummary.whatToWatch).toEqual(['Watch breadth participation.']);
  });

  it('composes a plain-language narrative for a healthy driver set', async () => {
    const { buildMarketDecisionCockpitNarrative } = await import('../../utils/marketDecisionCockpitNarrative');

    const narrative = buildMarketDecisionCockpitNarrative({
      schemaVersion: 'market_decision_cockpit.v1',
      generatedAt: '2026-06-15T00:00:00Z',
      marketRegimeDecision: {
        regime: 'riskOn',
        confidence: 'medium',
        confidenceScore: 0.68,
        driverScores: {
          breadthParticipation: { score: 72, evidenceState: 'score_grade' },
          volatilityStructure: { score: 76, evidenceState: 'score_grade' },
          liquidityCredit: { score: 64, evidenceState: 'score_grade' },
          ratesDollar: { score: 58, evidenceState: 'partial' },
        },
        researchPriorities: {
          watchToday: ['Confirm breadth participation.'],
          needsMoreEvidence: [],
          investigateNext: ['Review whether breadth and volatility stay aligned.'],
        },
      },
      researchQueuePreview: {
        topCandidates: [],
        queueQuality: 'mixed',
        evidenceGaps: [],
        previewOnly: true,
      },
      optionsStructureStatus: {
        gammaEvidenceStatus: 'ready_observation',
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
      dataQuality: { status: 'available' },
    }, 'en');

    expect(narrative.sentences).toHaveLength(4);
    expect(narrative.sentences[0]).toContain('Risk-on observation');
    expect(narrative.sentences[1]).toContain('Volatility structure, breadth participation, and liquidity and credit');
    expect(narrative.sentences.join(' ')).toContain('research priority signal');
    expect(narrative.sentences.join(' ')).not.toMatch(/\b(buy|sell|hold|recommend|target|stop|position)\b/i);
    expect(narrative.sentences.join(' ')).not.toMatch(/score-grade|score_grade/i);
  });

  it('explains mostly unavailable drivers and low confidence without raw enums', async () => {
    const { buildMarketDecisionCockpitNarrative, getDriverEvidenceStateLabel } = await import('../../utils/marketDecisionCockpitNarrative');

    const narrative = buildMarketDecisionCockpitNarrative({
      schemaVersion: 'market_decision_cockpit.v1',
      marketRegimeDecision: {
        regime: 'lowConfidence',
        confidence: 'low',
        confidenceScore: 0.18,
        driverScores: {
          dealerGamma: { score: 0, evidenceState: 'unavailable' },
          breadthParticipation: { score: 0, evidenceState: 'blocked' },
          volatilityStructure: { score: 0, evidenceState: 'provider_timeout' },
          liquidityCredit: { score: 22, evidenceState: 'partial' },
          eventCatalyst: { score: 0, evidenceState: 'raw_backend_reason_code' },
        },
        researchPriorities: {
          watchToday: [],
          needsMoreEvidence: ['provider_timeout', 'raw_backend_reason_code'],
          investigateNext: [],
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
        whatToWatch: [],
        confidenceLimits: ['provider_timeout'],
      },
      noAdviceDisclosure: 'Research context only.',
      dataQuality: { status: 'degraded', reasonCodes: ['provider_timeout'] },
    }, 'zh');

    expect(narrative.sentences[0]).toContain('低置信观察区间');
    expect(narrative.sentences[0]).toContain('多数驱动项缺少可评分证据');
    expect(narrative.sentences[2]).toContain('Gamma 观察、广度参与、波动结构');
    expect(narrative.sentences.join(' ')).toContain('研究优先级线索');
    expect(narrative.sentences.join(' ')).not.toMatch(/provider_timeout|raw_backend_reason_code|score_grade|schema|debug|trace/i);
    expect(getDriverEvidenceStateLabel('score_grade', 'zh')).toBe('可评分证据');
    expect(getDriverEvidenceStateLabel('provider_timeout', 'zh')).toBe('证据暂不可用');
  });

  it('maps cockpit raw status tokens into consumer-safe Chinese labels', async () => {
    const { getDriverEvidenceStateLabel } = await import('../../utils/marketDecisionCockpitNarrative');

    expect(getDriverEvidenceStateLabel('unavailable', 'zh')).toBe('数据暂不可用');
    expect(getDriverEvidenceStateLabel('stale', 'zh')).toBe('数据可能已过期');
    expect(getDriverEvidenceStateLabel('proxy', 'zh')).toBe('间接参考，证据强度受限');
    expect(getDriverEvidenceStateLabel('proxy-only', 'zh')).toBe('间接参考，证据强度受限');
    expect(getDriverEvidenceStateLabel('pending', 'zh')).toBe('正在等待数据确认');
    expect(getDriverEvidenceStateLabel('blocked', 'zh')).toBe('当前无法分析');
    expect(getDriverEvidenceStateLabel('lowConfidence', 'zh')).toBe('置信度较低');
    expect(getDriverEvidenceStateLabel('score-grade', 'zh')).toBe('可评分证据');
    expect(getDriverEvidenceStateLabel('freshness=unavailable', 'zh')).toBe('数据新鲜度暂不可用');
  });

  it('suppresses mixed-language internal tokens and no-advice vocabulary', async () => {
    const { buildMarketDecisionCockpitNarrative } = await import('../../utils/marketDecisionCockpitNarrative');

    const narrative = buildMarketDecisionCockpitNarrative({
      schemaVersion: 'market_decision_cockpit.v1',
      marketRegimeDecision: {
        regime: 'mixed',
        confidence: 'low',
        confidenceScore: 0.34,
        driverScores: {
          ratesDollar: { score: 61, evidenceState: 'score_grade' },
          crossAssetRisk: { score: 57, evidenceState: 'partial' },
          sectorThemeRotation: { score: 0, evidenceState: 'provider_runtime_debug' },
        },
        researchPriorities: {
          watchToday: ['buy now if score improves'],
          needsMoreEvidence: ['schemaVersion mismatch'],
          investigateNext: ['sell stop target should never render'],
        },
      },
      researchQueuePreview: {
        topCandidates: [],
        queueQuality: 'thin',
        evidenceGaps: ['schemaVersion mismatch'],
        previewOnly: true,
      },
      optionsStructureStatus: {
        gammaEvidenceStatus: 'unavailable',
        observationOnly: true,
        decisionGrade: false,
        missingEvidence: [],
        blockedReasonCodes: ['provider_runtime_debug'],
      },
      cockpitSummary: {
        whatChanged: [],
        whyItMatters: [],
        whatToWatch: ['buy now if score improves'],
        confidenceLimits: ['schemaVersion mismatch'],
      },
      noAdviceDisclosure: 'Research context only.',
      dataQuality: { status: 'degraded' },
    }, 'en');

    const joined = narrative.sentences.join(' ');
    expect(joined).toContain('Mixed-regime observation');
    expect(joined).toMatch(/rates and USD/i);
    expect(joined).not.toMatch(/schemaVersion|provider_runtime_debug|score[-_]grade|raw|debug|trace/i);
    expect(joined).not.toMatch(/\b(buy|sell|hold|recommend|target|stop|position)\b/i);
  });
});
