import { describe, expect, it } from 'vitest';
import { consumerPresentationText } from '../consumerPresentationBoundary';
import { getConsumerStatusLabel } from '../consumerStatusLabels';
import { isConsumerDataStateToken } from '../consumerDataStateVocabulary';

describe('G026 evidence limitation presentation', () => {
  it('keeps free-text limitation phrases specific instead of generic unavailable', () => {
    expect(isConsumerDataStateToken('Growth proxy evidence is unavailable.')).toBe(false);
    expect(isConsumerDataStateToken('Breadth evidence is unavailable.')).toBe(false);
    expect(isConsumerDataStateToken('unavailable')).toBe(true);
    expect(isConsumerDataStateToken('quote_unavailable')).toBe(true);
    expect(getConsumerStatusLabel('Growth proxy evidence is unavailable.', 'zh')).toBeNull();
    expect(consumerPresentationText('Growth proxy evidence is unavailable.', 'zh')).toBe('成长风险观察证据暂不可用。');
    expect(consumerPresentationText('Breadth evidence is unavailable.', 'zh')).toBe('市场广度证据暂不可用。');
    expect(consumerPresentationText('Freshness is constrained for this observation.', 'zh')).toBe('数据新鲜度受限，当前仅供观察。');
  });

  it('keeps compact product tokens distinct from generic available', () => {
    expect(consumerPresentationText('product_ready', 'en')).toBe('Evidence ready for observation');
    expect(consumerPresentationText('risk_on_confirming', 'en')).toBe('Risk-on observation');
  });
});
