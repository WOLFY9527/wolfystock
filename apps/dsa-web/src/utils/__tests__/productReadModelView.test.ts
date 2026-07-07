import { describe, expect, it } from 'vitest';

import {
  productReadBlockingSummary,
  productReadModelIsBlocking,
  productReadModelTone,
  productReadStateLabel,
} from '../productReadModelView';

describe('productReadModelView', () => {
  it('labels and tones blocked, initializing, and error states explicitly', () => {
    expect(productReadStateLabel('blocked', 'zh')).toBe('已阻断');
    expect(productReadModelTone('blocked')).toBe('error');

    expect(productReadStateLabel('initializing', 'zh')).toBe('初始化中');
    expect(productReadModelTone('initializing')).toBe('info');
    expect(productReadStateLabel('refreshing', 'zh')).toBe('初始化中');

    expect(productReadStateLabel('error', 'zh')).toBe('读取异常');
    expect(productReadModelTone('error')).toBe('error');
  });

  it('does not treat initializing or pending states as blocking without explicit blockers', () => {
    expect(productReadModelIsBlocking({ state: 'initializing', ready: false })).toBe(false);
    expect(productReadModelIsBlocking({ state: 'pending', ready: false })).toBe(false);
    expect(productReadModelIsBlocking({ state: 'blocked', ready: false })).toBe(true);
    expect(productReadModelIsBlocking({ state: 'error', ready: false })).toBe(true);
    expect(productReadModelIsBlocking({ state: 'initializing', ready: false, blockingChildren: ['market_evidence'] })).toBe(true);
  });

  it('surfaces explicit blocking summaries when the state token itself is blocking', () => {
    expect(productReadBlockingSummary({ state: 'blocked' }, 'zh')).toBe('关键证据已阻断，暂不形成结论。');
    expect(productReadBlockingSummary({ state: 'error' }, 'zh')).toBe('关键证据读取异常，暂不形成结论。');
    expect(productReadBlockingSummary({ state: 'initializing', ready: false }, 'zh')).toBeNull();
  });
});
