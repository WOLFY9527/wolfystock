import { describe, expect, it } from 'vitest';

import {
  buildMarketIntelligenceEvidenceMarkdown,
  type MarketIntelligenceEvidenceExportInput,
} from '../marketIntelligenceEvidenceExport';

const FORBIDDEN_EXPORT_PATTERN =
  /sourceAuthorityAllowed|scoreContributionAllowed|reasonCodes?|sourceRefId|provider(State|Trace|Diagnostics|Route|Payload)?|raw[_ -]?(payload|diagnostics|result|ai_response)|context_snapshot|debug|trace|schemaVersion|MarketCache|fallback_static|synthetic_fixture|official_public|authorized_licensed_feed|public_proxy|unofficial_proxy|provider_timeout|provider_runtime|backend snake_case|buy|sell|hold|recommend|target|stop|position[- ]?sizing|买入|卖出|持有|推荐|建议(买入|卖出|加仓|减仓|持有)|目标价|止损|仓位/i;

const exportInput: MarketIntelligenceEvidenceExportInput = {
  title: 'Market Intelligence Evidence Snapshot',
  generatedAt: '2026-06-17T09:30:00.000Z',
  locale: 'en',
  regimeObservation: {
    title: 'Risk-on observation',
    summary: 'Liquidity and breadth remain constructive, but the signal is observation-only.',
    confidenceLabel: 'Evidence strength: medium',
  },
  evidenceUsed: [
    {
      label: 'US breadth',
      meta: 'Score-grade evidence',
    },
    {
      label: 'Funding stress',
      meta: 'provider_timeout debug trace MarketCache raw payload should not export',
    },
    {
      label: 'Raw authority marker',
      meta: 'sourceAuthorityAllowed official_public provider_runtime',
    },
    {
      label: 'Late extra item',
      meta: 'Should be clipped by maxEvidenceItems.',
    },
  ],
  evidenceGaps: [
    'Need updated options breadth',
    'provider_timeout raw diagnostics should not export',
  ],
  dataFreshness: {
    label: 'Delayed data',
    asOf: '2026-06-17T09:00:00.000Z',
    notes: [
      'Fallback inputs are present.',
      'cache trace schemaVersion rawPayload',
    ],
  },
  researchNextSteps: [
    'Verify breadth persistence after cash open.',
    'Buy SPY if it breaks out.',
    'Check whether defensive flows invalidate the observation.',
  ],
  noAdviceDisclosure: 'This snapshot is not investment advice and does not include buy/sell/hold recommendations, targets, stops, or position sizing.',
  maxEvidenceItems: 3,
};

describe('marketIntelligenceEvidenceExport', () => {
  it('builds a bounded professional markdown snapshot with the required sections', () => {
    const markdown = buildMarketIntelligenceEvidenceMarkdown(exportInput);

    expect(markdown).toContain('# Market Intelligence Evidence Snapshot');
    expect(markdown).toContain('## Market regime observation');
    expect(markdown).toContain('## Evidence used');
    expect(markdown).toContain('## Evidence gaps');
    expect(markdown).toContain('## Data freshness');
    expect(markdown).toContain('## Research next steps');
    expect(markdown).toContain('## No-advice disclosure');
    expect(markdown).toContain('## Generated timestamp');
    expect(markdown).toContain('Risk-on observation');
    expect(markdown).toContain('- US breadth: Score-grade evidence');
    expect(markdown).toContain('- Funding stress: Evidence detail withheld.');
    expect(markdown).not.toContain('Late extra item');
    expect(markdown).toContain('- 1 item omitted by export limit.');
    expect(markdown).toContain('- As of: 2026-06-17T09:00:00.000Z');
    expect(markdown).toContain('- Generated at: 2026-06-17T09:30:00.000Z');
  });

  it('redacts raw diagnostics and replaces advice wording in exported markdown', () => {
    const markdown = buildMarketIntelligenceEvidenceMarkdown(exportInput);

    expect(markdown).not.toMatch(FORBIDDEN_EXPORT_PATTERN);
    expect(markdown).toContain('This snapshot is for research observation only.');
    expect(markdown).toContain('Check whether defensive flows invalidate the observation.');
    expect(markdown).not.toContain('Buy SPY');
  });

  it('uses safe fallbacks for sparse payloads without exporting raw JSON', () => {
    const markdown = buildMarketIntelligenceEvidenceMarkdown({
      locale: 'en',
      generatedAt: '2026-06-17T09:30:00.000Z',
      dataFreshness: {
        label: 'provider_runtime_debug',
        asOf: '/api/v1/admin/providers?trace=MarketCache',
      },
    });

    expect(markdown).toContain('Market Intelligence Evidence Snapshot');
    expect(markdown).toContain('- Evidence detail not available.');
    expect(markdown).toContain('- Freshness: Data freshness pending confirmation.');
    expect(markdown).toContain('- As of: Data timestamp pending confirmation.');
    expect(markdown).not.toMatch(FORBIDDEN_EXPORT_PATTERN);
    expect(markdown).not.toContain('{');
    expect(markdown).not.toContain('}');
  });
});
