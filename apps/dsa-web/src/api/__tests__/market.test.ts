import { describe, expect, it } from 'vitest';
import * as marketModule from '../market';

describe('market API path join hygiene', () => {
  it('normalizes market endpoint joins without introducing double slashes', () => {
    const buildMarketApiPath = (marketModule as { buildMarketApiPath?: (path: string) => string }).buildMarketApiPath;

    expect(buildMarketApiPath?.('/crypto')).toBe('/api/v1/market/crypto');
    expect(buildMarketApiPath?.('crypto')).toBe('/api/v1/market/crypto');
  });

  it('normalizes absolute market stream URLs without double slashes after /api/v1', () => {
    const buildMarketApiUrl = (marketModule as {
      buildMarketApiUrl?: (baseUrl: string, path: string) => string;
    }).buildMarketApiUrl;

    expect(buildMarketApiUrl?.('https://example.com/api/v1/', '/market/crypto/stream'))
      .toBe('https://example.com/api/v1/market/crypto/stream');
    expect(buildMarketApiUrl?.('https://example.com/api/v1', 'market/crypto/stream'))
      .toBe('https://example.com/api/v1/market/crypto/stream');
  });
});

describe('market temperature evidence normalization', () => {
  it('preserves source-confidence fields without accepting unlabeled market evidence', () => {
    const payload = marketModule.normalizeMarketTemperatureResponse({
      source: 'computed',
      updatedAt: '2026-05-20T10:00:00+08:00',
      marketRegimeSynthesis: {
        primaryRegime: 'risk_on',
        secondaryRegimes: ['liquidity_support'],
        regimeScores: { risk_on: 0.7 },
        topDrivers: [
          {
            key: 'market:liquidity',
            label: 'Liquidity support',
            source: 'liquidity_monitor',
            sourceTier: 'official_public',
            trustLevel: 'reliable',
            freshness: 'delayed',
            observationOnly: false,
            scoreContributionAllowed: true,
            discountReasons: ['stale', ''],
            degradationReason: 'delayed_source',
          },
          {
            key: 'market:missing_label',
            reason: 'missing label should still be rejected for market synthesis',
          } as never,
        ],
        counterEvidence: [],
        dataGaps: [],
        narrativeBullets: ['Liquidity support is the top driver.'],
      },
      scores: {
        overall: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        usRiskAppetite: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        cnMoneyEffect: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        macroPressure: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        liquidity: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
      },
    });

    expect(payload.marketRegimeSynthesis?.topDrivers).toHaveLength(1);
    expect(payload.marketRegimeSynthesis?.topDrivers[0]).toMatchObject({
      key: 'market:liquidity',
      label: 'Liquidity support',
      source: 'liquidity_monitor',
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      freshness: 'delayed',
      observationOnly: false,
      scoreContributionAllowed: true,
      discountReasons: ['stale'],
      degradationReason: 'delayed_source',
    });
  });

  it('preserves market decision semantics without dropping boundaries or gaps', () => {
    const payload = marketModule.normalizeMarketTemperatureResponse({
      source: 'computed',
      updatedAt: '2026-05-21T10:00:00+08:00',
      marketDecisionSemantics: {
        version: 'market_decision_semantics_v1',
        posture: 'offensive',
        postureConfidence: {
          value: 62,
          label: 'medium',
          capReasons: ['counter_evidence_present'],
        },
        exposureBias: 'risk_on_watch',
        styleTilts: [{ tilt: 'liquidity_beta_watch', label: 'Liquidity beta watch', detail: 'Watch-only.' }],
        confirmationSignals: [{ signal: 'liquidity_alignment', detail: 'Liquidity should remain expanding.' }],
        invalidationTriggers: [{ trigger: 'liquidity_stops_expanding', detail: 'Liquidity turns mixed.' }],
        counterEvidence: [{ surface: 'market_regime_synthesis', key: 'rates:US10Y', label: 'US10Y' }],
        dataGaps: [{ surface: 'liquidity_impulse_synthesis', key: 'official:fed_liquidity', label: 'Fed liquidity' }],
        claimBoundaries: [{ claim: 'direct_trade_action', allowed: false, reasonCode: 'not_investment_advice' }],
        notInvestmentAdvice: true,
      },
      scores: {
        overall: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        usRiskAppetite: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        cnMoneyEffect: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        macroPressure: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
        liquidity: { value: 55, label: 'neutral', trend: 'stable', description: 'neutral' },
      },
    } as never);

    const semantics = (payload as { marketDecisionSemantics?: Record<string, unknown> }).marketDecisionSemantics;

    expect(semantics).toMatchObject({
      posture: 'offensive',
      exposureBias: 'risk_on_watch',
      notInvestmentAdvice: true,
    });
    expect(semantics?.postureConfidence).toMatchObject({
      value: 62,
      label: 'medium',
      capReasons: ['counter_evidence_present'],
    });
    expect(semantics?.dataGaps).toEqual([
      expect.objectContaining({ key: 'official:fed_liquidity', label: 'Fed liquidity' }),
    ]);
    expect(semantics?.claimBoundaries).toEqual([
      expect.objectContaining({ claim: 'direct_trade_action', allowed: false }),
    ]);
  });
});
