import { describe, expect, it } from 'vitest';

import {
  DATA_TRUST_EVIDENCE_COPY,
  DATA_TRUST_EVIDENCE_STATE_ORDER,
  createDataTrustEvidenceViewModel,
  type DataTrustEvidenceState,
} from '../dataTrustEvidenceDisplay';
import type { NormalizedEvidenceSummary } from '../evidenceDisplay';

const EXPECTED_STATES: DataTrustEvidenceState[] = [
  'authoritative',
  'partial',
  'stale',
  'fallback',
  'fixture-demo',
  'synthetic',
  'unavailable',
  'insufficient',
  'observation-only',
  'not-investment-advice',
];

const FORBIDDEN_RAW_TOKENS = [
  'providerRuntime',
  'sourceAuthorityAllowed',
  'scoreContributionAllowed',
  'routeRejected',
  'fallback_used',
  'cache_stale',
  'yfinance_proxy',
  '/api/v1/admin',
  'source-provenance:',
  'MarketCache',
] as const;

function serialized(value: unknown): string {
  return JSON.stringify(value);
}

describe('dataTrustEvidenceDisplay', () => {
  it('defines the full v1 consumer vocabulary with bounded zh/en copy', () => {
    expect(DATA_TRUST_EVIDENCE_STATE_ORDER).toEqual(EXPECTED_STATES);

    for (const state of EXPECTED_STATES) {
      expect(DATA_TRUST_EVIDENCE_COPY[state].zh.label).toBeTruthy();
      expect(DATA_TRUST_EVIDENCE_COPY[state].zh.message).toBeTruthy();
      expect(DATA_TRUST_EVIDENCE_COPY[state].en.label).toBeTruthy();
      expect(DATA_TRUST_EVIDENCE_COPY[state].en.message).toBeTruthy();
    }
  });

  it('maps a clean TrustEvidence snapshot to authoritative plus safety copy', () => {
    const viewModel = createDataTrustEvidenceViewModel({
      locale: 'zh',
      trustEvidence: {
        contractVersion: 'trust_evidence_snapshot_v1',
        surfaceKey: 'market_overview',
        entityKey: 'SPY',
        generatedAt: '2026-06-11T09:30:00.000Z',
        asOf: '2026-06-11T09:00:00.000Z',
        availabilityState: 'available',
        freshnessState: 'fresh',
        sourceClass: 'official_public',
        hasFallback: false,
        isStale: false,
        isPartial: false,
        isSynthetic: false,
        consumerState: 'AVAILABLE',
        consumerBadgeKeys: ['source_current'],
      },
    });

    expect(viewModel.primaryState).toBe('authoritative');
    expect(viewModel.states).toEqual(['authoritative', 'not-investment-advice']);
    expect(viewModel.chips.map((chip) => chip.label)).toEqual(['证据可用', '不构成投资建议']);
    expect(viewModel.message).toContain('观察边界');
    expect(viewModel.asOf).toBe('2026-06-11T09:00:00.000Z');
  });

  it('derives degraded canonical states without leaking raw provider/debug terms', () => {
    const viewModel = createDataTrustEvidenceViewModel({
      locale: 'en',
      trustEvidence: {
        contractVersion: 'trust_evidence_snapshot_v1',
        surfaceKey: 'scanner',
        availabilityState: 'partial',
        freshnessState: 'stale',
        sourceClass: 'synthetic',
        hasFallback: true,
        isStale: true,
        isPartial: true,
        isSynthetic: true,
        consumerState: 'PARTIAL',
        consumerMessageKey: 'trust_evidence.providerRuntime.cache_stale',
        consumerBadgeKeys: ['source_stale', 'source_fallback', 'providerRuntime'],
        adminDiagnosticRefs: FORBIDDEN_RAW_TOKENS,
      },
      terms: ['synthetic_fixture', 'routeRejected', 'providerRuntime', '/api/v1/admin/evidence'],
      confidenceCap: 55,
    });

    expect(viewModel.states).toEqual([
      'partial',
      'stale',
      'fallback',
      'fixture-demo',
      'synthetic',
      'not-investment-advice',
    ]);
    expect(viewModel.primaryState).toBe('partial');
    expect(viewModel.confidenceCapLabel).toBe('Confidence cap 55');
    expect(viewModel.chips.map((chip) => chip.label)).toEqual([
      'Partial evidence',
      'Stale',
      'Fallback',
      'Demo',
      'Synthetic',
      'Not investment advice',
    ]);

    const output = serialized(viewModel);
    for (const token of FORBIDDEN_RAW_TOKENS) {
      expect(output).not.toContain(token);
    }
  });

  it('bridges existing NormalizedEvidenceSummary into canonical states', () => {
    const summary: NormalizedEvidenceSummary = {
      engine: 'scanner',
      posture: 'observe_only',
      displayLabel: '仅供观察',
      tone: 'info',
      confidenceCap: 60,
      freshnessLabel: '备用数据',
      limitationLabels: ['演示数据', '数据已过期', 'provider_timeout', 'MarketCache'],
      adminReasonCodes: ['provider_timeout'],
      diagnostics: { rawProviderPayload: true },
    };

    const viewModel = createDataTrustEvidenceViewModel({
      locale: 'zh',
      normalizedEvidence: summary,
    });

    expect(viewModel.states).toEqual([
      'stale',
      'fallback',
      'fixture-demo',
      'observation-only',
      'not-investment-advice',
    ]);
    expect(viewModel.primaryState).toBe('stale');
    expect(viewModel.confidenceCapLabel).toBe('置信上限 60');
    expect(viewModel.chips.map((chip) => chip.label)).toEqual([
      '数据过期',
      '备用数据',
      '演示数据',
      '仅供观察',
      '不构成投资建议',
    ]);
    expect(serialized(viewModel)).not.toMatch(/provider_timeout|MarketCache|rawProviderPayload/i);
  });

  it('can suppress the safety state for admin-only bounded diagnostics', () => {
    const viewModel = createDataTrustEvidenceViewModel({
      locale: 'zh',
      states: ['partial', 'not-investment-advice'],
      includeSafetyState: false,
    });

    expect(viewModel.states).toEqual(['partial']);
    expect(viewModel.chips.map((chip) => chip.label)).toEqual(['证据不完整']);
  });

  it('drops unsafe asOf values rather than echoing raw endpoint or diagnostic ids', () => {
    const viewModel = createDataTrustEvidenceViewModel({
      locale: 'zh',
      states: ['authoritative'],
      asOf: '/api/v1/admin/providers?debugRef=providerRuntime',
      trustEvidence: {
        asOf: 'source-provenance:market:liquidity:cache_stale',
      },
    });

    expect(viewModel.asOf).toBeUndefined();
    expect(serialized(viewModel)).not.toMatch(/api\/v1|debugRef|providerRuntime|source-provenance|cache_stale/i);
  });
});
