import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { EvidenceGapExplanationList } from '../EvidenceGapExplanation';
import { buildEvidenceGapExplanation, buildEvidenceGapExplanations } from '../evidenceGapCopy';
import { findConsumerRawLeakage } from '../../../test-utils/consumerRawLeakageGuard';

describe('EvidenceGapExplanation', () => {
  it('maps known gap families to consumer-safe research explanations', () => {
    const explanation = buildEvidenceGapExplanation('benchmark_missing', 'zh');

    expect(explanation.title).toBe('基准证据缺失');
    expect(explanation.explanation).toContain('缺少基准或指数参照');
    expect(explanation.whyItMatters).toContain('相对强弱');
    expect(explanation.suggestedResearchStep).toContain('补充同周期基准表现');
    expect(explanation.confidenceImpact).toContain('置信度受限');
    expect(explanation.observationBoundary).toBe('仅作观察，不构成操作结论。');
    expect(JSON.stringify(explanation)).not.toContain('benchmark_missing');
  });

  it('does not render raw enums, provider diagnostics, or advisory wording', () => {
    render(
      <EvidenceGapExplanationList
        locale="zh"
        gaps={[
          'provider_runtime_trace',
          'reasonCodes',
          'buy now target price raw payload',
          { kind: 'confidence_capped', message: 'sourceRefs sell now provider debug' },
          'unknown_gap_family_v42',
        ]}
      />,
    );

    const panel = screen.getByTestId('evidence-gap-explanation-list');
    expect(panel).toHaveTextContent('部分证据暂不可用，因此当前结论只适合作为观察线索。');
    expect(panel).toHaveTextContent('置信度受到上限约束');
    expect(panel).toHaveTextContent('仅作观察，不构成操作结论。');
    expect(panel.textContent || '').not.toMatch(/provider_runtime_trace|reasonCodes|sourceRefs|unknown_gap_family_v42|raw payload|debug|buy now|sell now|target price/i);
    expect(findConsumerRawLeakage(panel.textContent || '')).toEqual([]);
  });

  it('deduplicates repeated families and supports English copy', () => {
    const explanations = buildEvidenceGapExplanations([
      'fundamentals_missing',
      'fundamental data missing',
      'options_data_missing',
    ], 'en');

    expect(explanations).toHaveLength(2);
    expect(explanations[0]?.title).toBe('Fundamental evidence missing');
    expect(explanations[1]?.title).toBe('Options data missing');
    expect(JSON.stringify(explanations)).not.toMatch(/fundamentals_missing|options_data_missing/);
  });
});
