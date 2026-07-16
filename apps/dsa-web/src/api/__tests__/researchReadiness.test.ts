import { describe, expect, it } from 'vitest';
import { buildConsumerResearchReadinessView } from '../researchReadiness';

describe('buildConsumerResearchReadinessView', () => {
  it('derives the visible verdict from the canonical state in the active locale', () => {
    const readiness = {
      readinessState: 'insufficient',
      verdictLabel: '证据不足',
    };

    expect(buildConsumerResearchReadinessView(readiness, 'en').verdictLabel).toBe('Evidence insufficient');
    expect(buildConsumerResearchReadinessView({
      ...readiness,
      verdictLabel: 'Evidence insufficient',
    }, 'zh').verdictLabel).toBe('证据不足');
  });
});
