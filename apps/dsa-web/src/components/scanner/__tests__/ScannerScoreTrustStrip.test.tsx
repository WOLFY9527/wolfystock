import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ScannerScoreTrustStrip } from '../ScannerScoreTrustStrip';
import { findConsumerRawLeakage } from '../../../test-utils/consumerRawLeakageGuard';
import type { ScannerCandidate } from '../../../types/scanner';

function candidateWithTrustDiagnostics(): ScannerCandidate {
  return {
    symbol: 'MARA',
    name: 'MARA Holdings',
    companyName: 'MARA Holdings',
    rank: 1,
    score: 61,
    qualityHint: 'partial evidence',
    reasonSummary: 'Research-only candidate.',
    reasons: [],
    keyMetrics: [],
    featureSignals: [],
    riskNotes: [],
    watchContext: [],
    boards: [],
    tags: [],
    appearedInRecentRuns: 0,
    lastTradeDate: '2026-06-10',
    scanTimestamp: '2026-06-10T08:30:00Z',
    diagnostics: {
      scoreExplainability: {
        scoreConfidence: 0.36,
        capReason: 'fallback_source',
        degradationReason: 'provider_timeout',
        scoreGradeAllowed: false,
      },
      evidencePacket: {
        dataQualityState: 'partial',
        freshnessState: 'stale',
        warningFlags: ['raw_provider_debug', 'sourceAuthorityAllowed'],
      },
    },
    metadata: {
      evidencePacket: {
        sourceConfidence: {
          source: 'fallback_snapshot',
          sourceLabel: 'Fallback snapshot',
          freshness: 'fallback',
          isFallback: true,
          isStale: true,
          isPartial: true,
          confidenceWeight: 0.36,
          scoreContributionAllowed: false,
          observationOnly: true,
        },
        providerObservation: {
          scoreContributionAllowed: false,
          observationOnly: true,
        },
      },
    },
  };
}

describe('ScannerScoreTrustStrip', () => {
  it('renders shared data-trust evidence chips from bounded scanner metadata', () => {
    render(
      <ScannerScoreTrustStrip
        sources={[candidateWithTrustDiagnostics()]}
        language="zh"
        testId="scanner-score-trust-MARA"
      />,
    );

    const strip = screen.getByTestId('scanner-score-trust-MARA');
    expect(strip).toHaveTextContent('证据不完整');
    expect(strip).toHaveTextContent('数据过期');
    expect(strip).toHaveTextContent('备用数据');
    expect(strip).toHaveTextContent('仅供观察');
    expect(strip).toHaveTextContent('不构成投资建议');
    expect(strip).not.toHaveTextContent(/fallback_source|provider_timeout|fallback_snapshot|raw_provider_debug|sourceAuthorityAllowed|scoreContributionAllowed/i);
    expect(findConsumerRawLeakage(strip.textContent || '')).toEqual([]);
  });
});
