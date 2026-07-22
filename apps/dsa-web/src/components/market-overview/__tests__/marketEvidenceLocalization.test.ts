import { describe, expect, it } from 'vitest';
import type {
  MarketBriefingResponse,
  MarketDecisionSemantics,
  MarketRegimeSynthesis,
  MarketTemperatureResponse,
} from '../../../api/market';
import { resolveMarketIntelligenceConsumerView } from '../../../utils/marketIntelligenceGuidance';

function semanticsFixture(): MarketDecisionSemantics {
  return {
    posture: 'data_insufficient',
    postureConfidence: { value: null, label: 'insufficient', capReasons: [] },
    exposureBias: 'no_bias_data_insufficient',
    styleTilts: [],
    confirmationSignals: [],
    invalidationTriggers: [],
    counterEvidence: [],
    dataGaps: [
      {
        key: 'missing:volatility_stress',
        label: 'Missing scoring evidence for volatility_stress',
        pillar: 'volatility_stress',
        reason: 'missing_scoring_evidence',
      },
    ],
    directionReadiness: {
      status: 'data_insufficient',
      confidenceLabel: 'insufficient',
      scoreGradePillars: { count: 0, items: [] },
      observationOnlyPillars: { count: 0, items: [] },
      missingPillars: {
        count: 1,
        items: [
          {
            pillar: 'volatility_stress',
            label: 'Volatility stress',
            reasonCode: 'missing_scoring_evidence',
          },
        ],
      },
      blockingReasons: ['no_meaningful_score_grade_pillars'],
      claimBoundaries: [],
      notInvestmentAdvice: true,
    },
    claimBoundaries: [],
    notInvestmentAdvice: true,
  } as MarketDecisionSemantics;
}

function consumerView(
  semantics: MarketDecisionSemantics,
  locale: 'zh' | 'en',
) {
  const regimeSynthesis = {
    primaryRegime: 'data_insufficient',
    topDrivers: [],
    counterEvidence: [],
    dataGaps: [semantics.dataGaps[0]],
  } as unknown as MarketRegimeSynthesis;
  return resolveMarketIntelligenceConsumerView({
    temperature: {
      scores: {},
      marketRegimeSynthesis: regimeSynthesis,
      marketDecisionSemantics: semantics,
    } as unknown as MarketTemperatureResponse,
    briefing: {} as MarketBriefingResponse,
    panels: {},
    decisionReliable: false,
    locale,
  });
}

describe('market evidence localization', () => {
  it('localizes missing known evidence in Chinese without leaking the raw key', () => {
    const semantics = semanticsFixture();
    const view = consumerView(semantics, 'zh');
    const dataGap = view.decisionSemantics!.dataGaps[0];
    const readiness = view.decisionSemantics!.directionReadiness!;
    const regimeGap = view.regimeSynthesis!.dataGaps[0];
    const rendered = `${regimeGap.label} · ${dataGap.label} · ${readiness.missingPillars.items[0].label}`;

    expect(rendered).toContain('波动压力');
    expect(rendered).toContain('缺少评分级证据');
    expect(rendered).not.toContain('Missing scoring evidence');
    expect(rendered).not.toContain('volatility_stress');
    expect(dataGap.key).toBe('missing:volatility_stress');
    expect(dataGap.reason).toBe('missing_scoring_evidence');
    expect(readiness.status).toBe('data_insufficient');
    expect(view.decisionSemantics!.notInvestmentAdvice).toBe(true);
    expect(readiness.notInvestmentAdvice).toBe(true);
  });

  it('keeps English evidence complete and localizes unknown future keys generically', () => {
    const semantics = semanticsFixture();
    const view = consumerView(semantics, 'en');
    const dataGap = view.decisionSemantics!.dataGaps[0];
    const readiness = view.decisionSemantics!.directionReadiness!;
    const rendered = `${view.regimeSynthesis!.dataGaps[0].label} · ${dataGap.label} · ${readiness.missingPillars.items[0].label}`;

    expect(rendered).toContain('Volatility stress');
    expect(rendered).toContain('Score-grade evidence missing');
    expect(rendered).not.toContain('volatility_stress');

    semantics.dataGaps[0] = {
      key: 'missing:future_signal',
      label: 'Missing scoring evidence for future_signal',
      pillar: 'future_signal',
      reason: 'missing_scoring_evidence',
    };
    const unknown = consumerView(semantics, 'zh').decisionSemantics!.dataGaps[0].label;
    expect(unknown).toBe('证据项：缺少评分级证据');
    expect(unknown).not.toContain('future_signal');
    expect(unknown).not.toContain('Missing scoring evidence');
  });
});
