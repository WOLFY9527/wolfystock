import { describe, expect, it } from 'vitest';

import {
  createConsumerDataQualityViewModel,
} from '../consumerDataQualityViewModel';

const FORBIDDEN_KEYS = [
  'source',
  'sourceLabel',
  'sourceType',
  'sourceTier',
  'trustLevel',
  'providerName',
  'providerId',
  'providerDiagnostics',
  'reasonCodes',
  'reasonFamilies',
  'raw_code',
  'sourceAuthorityAllowed',
  'scoreContributionAllowed',
  'observationOnly',
  'sourceAuthorityReason',
  'routeRejectedReasonCodes',
  'diagnostics',
  'payload',
] as const;

const FORBIDDEN_TOKENS = [
  'sourceAuthorityAllowed',
  'scoreContributionAllowed',
  'observationOnly',
  'reasonCodes',
  'reasonFamilies',
  'providerDiagnostics',
  'raw_code',
  'sourceAuthorityReason',
  'routeRejectedReasonCodes',
  'fallback_static',
  'synthetic_fixture',
  'official_public',
  'authorized_licensed_feed',
  'public_proxy',
  'unofficial_proxy',
  'Polygon',
  'Tushare',
] as const;

const SAFE_OUTPUT_KEYS = [
  'status',
  'confidenceCategory',
  'freshnessCategory',
  'messageKey',
  'message',
  'asOf',
  'updatedAt',
  'isActionableForUser',
] as const;

function collectKeys(value: unknown): string[] {
  if (!value || typeof value !== 'object') return [];
  if (Array.isArray(value)) return value.flatMap((item) => collectKeys(item));

  return Object.entries(value).flatMap(([key, nested]) => [key, ...collectKeys(nested)]);
}

function expectConsumerSafe(value: unknown): void {
  const keys = collectKeys(value);
  for (const key of keys) {
    expect(FORBIDDEN_KEYS).not.toContain(key as (typeof FORBIDDEN_KEYS)[number]);
    expect(SAFE_OUTPUT_KEYS).toContain(key as (typeof SAFE_OUTPUT_KEYS)[number]);
  }

  const serialized = JSON.stringify(value);
  for (const token of FORBIDDEN_TOKENS) {
    expect(serialized).not.toContain(token);
  }
}

describe('createConsumerDataQualityViewModel', () => {
  it('projects representative consumer fragments into bounded product-safe states', () => {
    const cases = [
      {
        surface: 'Market Overview',
        fragment: {
          updatedAt: '2026-05-25T09:30:00+08:00',
          freshness: 'fallback',
          isFallback: true,
          source: 'fallback_static',
          sourceLabel: 'Polygon grouped daily',
          sourceType: 'public_proxy',
          sourceTier: 'official_public',
          trustLevel: 'unofficial_proxy',
          reasonCodes: ['source_confidence'],
        },
        status: 'DELAYED',
        freshnessCategory: 'STALE',
        confidenceCategory: 'LIMITED',
      },
      {
        surface: 'Liquidity Monitor',
        fragment: {
          asOf: '2026-05-25T10:00:00+08:00',
          freshness: 'cached',
          confidenceWeight: 0.35,
          sourceAuthorityAllowed: false,
          scoreContributionAllowed: false,
          observationOnly: true,
          sourceAuthorityReason: 'authorized_licensed_feed missing',
          routeRejectedReasonCodes: ['source_authority_denied'],
        },
        status: 'PAUSED',
        freshnessCategory: 'RECENT',
        confidenceCategory: 'LIMITED',
      },
      {
        surface: 'Scanner',
        fragment: {
          asOf: '2026-05-25',
          freshnessState: 'fresh',
          scoreConfidence: 0.52,
          coverage: 0.48,
          proxyOnly: true,
          providerObservation: {
            observationOnly: true,
            scoreContributionAllowed: false,
            entries: [{ providerName: 'Tushare', sourceType: 'public_proxy' }],
          },
          providerDiagnostics: {
            fallbackOccurred: true,
            providerWarnings: ['synthetic_fixture'],
          },
        },
        status: 'INSUFFICIENT',
        freshnessCategory: 'CURRENT',
        confidenceCategory: 'LIMITED',
      },
      {
        surface: 'Rotation',
        fragment: {
          asOf: '2026-05-25',
          freshnessState: 'fresh',
          scoreConfidence: 0.72,
          sourceAuthorityAllowed: true,
          scoreContributionAllowed: true,
          observationOnly: true,
          reasonCodes: ['observation_only'],
        },
        status: 'OBSERVATION_ONLY',
        freshnessCategory: 'CURRENT',
        confidenceCategory: 'LIMITED',
      },
      {
        surface: 'Watchlist',
        fragment: {
          updatedAt: '2026-05-24T15:00:00+08:00',
          freshness: 'stale',
          isStale: true,
          confidence: 0.76,
          providerId: 'authorized_licensed_feed.watchlist',
        },
        status: 'DELAYED',
        freshnessCategory: 'STALE',
        confidenceCategory: 'HIGH',
      },
      {
        surface: 'Portfolio',
        fragment: {
          asOf: '2026-05-24',
          freshnessLabel: 'delayed',
          isPartial: true,
          coverage: { ratio: 0.62 },
          confidenceWeight: 0.41,
          reasonFamilies: ['source_confidence', 'fx_rate_stale'],
          adminDiagnostics: { raw_code: 'fx_rate_stale' },
        },
        status: 'PARTIAL',
        freshnessCategory: 'DELAYED',
        confidenceCategory: 'LOW',
      },
      {
        surface: 'Backtest',
        fragment: {
          updatedAt: '2026-05-25T11:00:00+08:00',
          isUnavailable: true,
          freshness: 'unavailable',
          fallbackUsed: true,
          diagnostics: ['stored_execution_trace missing'],
          payload: { raw_code: 'support_bundle_reproducibility_manifest_json_missing' },
        },
        status: 'UNAVAILABLE',
        freshnessCategory: 'UNAVAILABLE',
        confidenceCategory: 'LIMITED',
      },
    ] as const;

    const projections = cases.map(({ fragment }) => createConsumerDataQualityViewModel(fragment));

    expect(projections.map((projection) => projection.status)).toEqual(cases.map((item) => item.status));
    expect(projections.map((projection) => projection.freshnessCategory)).toEqual(cases.map((item) => item.freshnessCategory));
    expect(projections.map((projection) => projection.confidenceCategory)).toEqual(cases.map((item) => item.confidenceCategory));

    for (const projection of projections) {
      expectConsumerSafe(projection);
    }
  });

  it('fails closed when source authority is missing instead of inferring from freshness or source labels', () => {
    const projection = createConsumerDataQualityViewModel({
      freshness: 'fresh',
      confidence: 0.91,
      source: 'polygon_live_feed',
      sourceType: 'official_public',
      sourceLabel: 'Polygon',
      providerName: 'Polygon',
      reasonCodes: ['unknown_reason_that_should_not_promote_authority'],
    });

    expect(projection).toMatchObject({
      status: 'INSUFFICIENT',
      freshnessCategory: 'CURRENT',
      confidenceCategory: 'LIMITED',
      messageKey: 'dataQuality.insufficient',
      isActionableForUser: false,
    });
    expectConsumerSafe(projection);
  });

  it('keeps score-blocked data in a safe consumer state without requiring raw diagnostics', () => {
    const projection = createConsumerDataQualityViewModel({
      freshness: 'fresh',
      confidenceWeight: 0.88,
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: false,
      reasonCodes: ['score_rights_missing'],
      providerDiagnostics: {
        routeRejectedReasonCodes: ['score_rights_missing'],
      },
    });

    expect(projection).toMatchObject({
      status: 'INSUFFICIENT',
      freshnessCategory: 'CURRENT',
      confidenceCategory: 'LIMITED',
      messageKey: 'dataQuality.insufficient',
      isActionableForUser: false,
    });
    expectConsumerSafe(projection);
  });

  it('treats synthetic and proxy fragments as degraded even when they are otherwise fresh', () => {
    const projection = createConsumerDataQualityViewModel({
      freshnessState: 'fresh',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      sourceType: 'unofficial_proxy',
      providerObservation: {
        sourceTier: 'synthetic_fixture',
        proxyOnly: true,
      },
    });

    expect(projection).toMatchObject({
      status: 'DELAYED',
      freshnessCategory: 'STALE',
      confidenceCategory: 'LIMITED',
      messageKey: 'dataQuality.delayed',
    });
    expectConsumerSafe(projection);
  });

  it('maps updating and unavailable states without exposing admin diagnostics', () => {
    const updatingProjection = createConsumerDataQualityViewModel({
      freshness: 'refreshing',
      isRefreshing: true,
      providerName: 'Polygon',
      providerDiagnostics: { sourceTier: 'official_public' },
    });
    const unavailableProjection = createConsumerDataQualityViewModel({
      status: 'missing',
      isUnavailable: true,
      raw_code: 'provider_timeout',
      diagnostics: { sourceAuthorityAllowed: false },
    });

    expect(updatingProjection).toMatchObject({
      status: 'UPDATING',
      messageKey: 'dataQuality.updating',
      isActionableForUser: false,
    });
    expect(unavailableProjection).toMatchObject({
      status: 'UNAVAILABLE',
      messageKey: 'dataQuality.unavailable',
      isActionableForUser: true,
    });
    expectConsumerSafe([updatingProjection, unavailableProjection]);
  });

  it('does not expose an admin diagnostics helper from the consumer module', async () => {
    const moduleExports = await import('../consumerDataQualityViewModel');

    expect(Object.keys(moduleExports).filter((key) => key.toLowerCase().includes('admin'))).toEqual([]);
  });
});
