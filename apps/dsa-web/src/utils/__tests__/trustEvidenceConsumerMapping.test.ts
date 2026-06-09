import { describe, expect, it } from 'vitest';

import {
  TRUST_EVIDENCE_CONSUMER_BADGE_COPY,
  TRUST_EVIDENCE_CONSUMER_COPY,
  createTrustEvidenceConsumerViewModel,
} from '../trustEvidenceConsumerMapping';

const BASE_SNAPSHOT = {
  contractVersion: 'trust_evidence_snapshot_v1',
  surfaceKey: 'market_overview',
  entityKey: 'AAPL',
  generatedAt: '2026-06-09T09:30:00.000Z',
  asOf: '2026-06-09T09:00:00.000Z',
  availabilityState: 'available',
  freshnessState: 'fresh',
  sourceClass: 'official_public',
  hasFallback: false,
  isStale: false,
  isPartial: false,
  isSynthetic: false,
  isAdminOnlyDetail: false,
  consumerState: 'AVAILABLE',
  consumerMessageKey: 'trust_evidence.available',
  consumerBadgeKeys: ['source_current'],
  adminDiagnosticRefs: [],
} as const;

const STATE_EXPECTATIONS = [
  ['AVAILABLE', 'available', 'trust_evidence.available', '可用'],
  ['UPDATING', 'updating', 'trust_evidence.updating', '正在更新'],
  ['DELAYED', 'delayed', 'trust_evidence.delayed', '延迟可用'],
  ['PARTIAL', 'partial', 'trust_evidence.partial', '部分可用'],
  ['INSUFFICIENT', 'insufficient', 'trust_evidence.insufficient', '证据不足'],
  ['OBSERVATION_ONLY', 'observation_only', 'trust_evidence.observation_only', '仅供观察'],
  ['UNAVAILABLE', 'unavailable', 'trust_evidence.unavailable', '暂不可用'],
] as const;

const FORBIDDEN_RAW_TOKENS = [
  'stale_official_row',
  'cache_stale',
  'fallback_source',
  'proxy_only_missing_real_source',
  'official_overlay_stale_using_proxy',
  'routeRejected',
  'fallback_used',
  'yfinance_proxy',
  'fred',
  'polygon',
  'tushare',
  'MarketCache',
  'providerRuntime',
  'scoreContributionAllowed',
  'sourceAuthorityAllowed',
  '/api/v1/market/',
  '/api/v1/admin/',
  'source-provenance:',
  'market:liquidity',
  'market:marketregime',
] as const;

function outputText(value: unknown): string {
  return JSON.stringify(value);
}

describe('createTrustEvidenceConsumerViewModel', () => {
  it.each(STATE_EXPECTATIONS)(
    'maps %s into bounded consumer state, label, and message copy',
    (consumerState, availabilityState, expectedMessageKey, expectedLabel) => {
      const viewModel = createTrustEvidenceConsumerViewModel({
        ...BASE_SNAPSHOT,
        availabilityState,
        consumerState,
        consumerMessageKey: `trust_evidence.providerRuntime.${availabilityState}`,
      });

      expect(viewModel.state).toBe(consumerState);
      expect(viewModel.statusLabel).toBe(expectedLabel);
      expect(viewModel.messageKey).toBe(expectedMessageKey);
      expect(viewModel.message).toBe(TRUST_EVIDENCE_CONSUMER_COPY[consumerState].message);
      expect(viewModel.isConsumerVisible).toBe(true);
    },
  );

  it('keeps source_stale badge only when the stale flag is true', () => {
    const withoutFlag = createTrustEvidenceConsumerViewModel({
      ...BASE_SNAPSHOT,
      consumerBadgeKeys: ['source_stale'],
      isStale: false,
    });
    const withFlag = createTrustEvidenceConsumerViewModel({
      ...BASE_SNAPSHOT,
      consumerBadgeKeys: [],
      freshnessState: 'stale',
      isStale: true,
    });

    expect(withoutFlag.badges.map((badge) => badge.key)).not.toContain('source_stale');
    expect(withFlag.badges).toEqual([TRUST_EVIDENCE_CONSUMER_BADGE_COPY.source_stale]);
  });

  it('keeps source_partial badge only when the partial flag is true', () => {
    const withoutFlag = createTrustEvidenceConsumerViewModel({
      ...BASE_SNAPSHOT,
      consumerBadgeKeys: ['source_partial'],
      isPartial: false,
    });
    const withFlag = createTrustEvidenceConsumerViewModel({
      ...BASE_SNAPSHOT,
      consumerBadgeKeys: [],
      isPartial: true,
    });

    expect(withoutFlag.badges.map((badge) => badge.key)).not.toContain('source_partial');
    expect(withFlag.badges).toEqual([TRUST_EVIDENCE_CONSUMER_BADGE_COPY.source_partial]);
  });

  it('keeps source_fallback badge only when the fallback flag is true', () => {
    const withoutFlag = createTrustEvidenceConsumerViewModel({
      ...BASE_SNAPSHOT,
      consumerBadgeKeys: ['source_fallback'],
      hasFallback: false,
    });
    const withFlag = createTrustEvidenceConsumerViewModel({
      ...BASE_SNAPSHOT,
      consumerBadgeKeys: [],
      hasFallback: true,
    });

    expect(withoutFlag.badges.map((badge) => badge.key)).not.toContain('source_fallback');
    expect(withFlag.badges).toEqual([TRUST_EVIDENCE_CONSUMER_BADGE_COPY.source_fallback]);
  });

  it('keeps observation_only badge only for observation-only state', () => {
    const withoutState = createTrustEvidenceConsumerViewModel({
      ...BASE_SNAPSHOT,
      consumerBadgeKeys: ['observation_only'],
      consumerState: 'AVAILABLE',
    });
    const withState = createTrustEvidenceConsumerViewModel({
      ...BASE_SNAPSHOT,
      consumerBadgeKeys: [],
      availabilityState: 'observation_only',
      consumerState: 'OBSERVATION_ONLY',
    });

    expect(withoutState.badges.map((badge) => badge.key)).not.toContain('observation_only');
    expect(withState.badges).toEqual([TRUST_EVIDENCE_CONSUMER_BADGE_COPY.observation_only]);
  });

  it('deduplicates bounded badges without exposing raw badge values', () => {
    const viewModel = createTrustEvidenceConsumerViewModel({
      ...BASE_SNAPSHOT,
      freshnessState: 'delayed',
      consumerBadgeKeys: ['source_delayed', 'source_delayed', 'polygon', 'cache_stale'],
      adminDiagnosticRefs: ['fallback_used', 'source-provenance:market'],
    });

    expect(viewModel.badges.map((badge) => badge.key)).toEqual(['source_delayed']);
    expect(viewModel.badges[0]).toEqual(TRUST_EVIDENCE_CONSUMER_BADGE_COPY.source_delayed);
  });

  it('does not leak raw provider, debug, reason-code, route, or admin details', () => {
    const viewModel = createTrustEvidenceConsumerViewModel({
      ...BASE_SNAPSHOT,
      freshnessState: 'stale',
      sourceClass: 'public_proxy',
      hasFallback: true,
      isStale: true,
      isPartial: true,
      isSynthetic: true,
      isAdminOnlyDetail: true,
      consumerState: 'PARTIAL',
      consumerMessageKey: 'trust_evidence.cache_stale.providerRuntime',
      consumerBadgeKeys: [
        'source_stale',
        'source_partial',
        'source_fallback',
        'providerRuntime',
        'routeRejected',
      ],
      adminDiagnosticRefs: FORBIDDEN_RAW_TOKENS,
      primarySourceLabel: 'polygon yfinance_proxy /api/v1/market/source-provenance:',
    });
    const serialized = outputText(viewModel).toLowerCase();

    for (const token of FORBIDDEN_RAW_TOKENS) {
      expect(serialized).not.toContain(token.toLowerCase());
    }
    expect(serialized).not.toContain('provider');
    expect(serialized).not.toContain('debug');
    expect(serialized).not.toContain('reason');
    expect(serialized).not.toContain('raw');
    expect(serialized).not.toContain('schema');
  });
});
