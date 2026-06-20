import { describe, expect, it } from 'vitest';
import { getResearchQueueConsumerCopy, getResearchQueueConsumerText } from '../researchQueueConsumerCopy';

describe('researchQueueConsumerCopy', () => {
  it('maps known English research queue phrases into consumer-safe Chinese copy', () => {
    const copy = getResearchQueueConsumerCopy({
      priorityTier: 'attention',
      priorityReason: 'Missing evidence needs review.',
      evidenceState: 'no_evidence',
      missingEvidence: ['Price-history evidence'],
      suggestedResearchPath: [
        {
          label: 'Stock Structure',
          route: '/stocks/MSFT/structure-decision',
          reason: 'Open symbol structure detail.',
        },
      ],
    }, 'zh');

    expect(copy).toEqual({
      priorityTierLabel: '建议复核',
      priorityVariant: 'caution',
      evidenceStateLabel: '缺少关键证据',
      priorityReason: '当前条目的证据覆盖不足，需补充同业、基本面或市场背景后再判断。',
      missingEvidence: ['价格历史数据待补充'],
      suggestedResearchPath: [
        {
          label: '查看个股结构',
          reason: '先核对结构与资料完整性。',
        },
      ],
    });
  });

  it('fails closed for unknown raw queue copy and diagnostic tokens', () => {
    const copy = getResearchQueueConsumerCopy({
      priorityTier: 'monitor',
      priorityReason: 'Queue review pending from backend memo',
      evidenceState: 'provider_trace_pending',
      missingEvidence: ['provider_runtime_trace', 'custom upstream phrase'],
      suggestedResearchPath: [
        {
          label: 'queue_debug_path',
          route: '/stocks/BABA/structure-decision',
          reason: 'provider_runtime_trace',
        },
      ],
    }, 'zh');

    expect(copy.priorityTierLabel).toBe('继续观察');
    expect(copy.evidenceStateLabel).toBe('证据待确认');
    expect(copy.priorityReason).toBe('当前条目的证据覆盖仍需复核。');
    expect(copy.missingEvidence).toEqual(['部分外部数据暂不可用', '部分关键资料待补充']);
    expect(copy.suggestedResearchPath).toEqual([
      {
        label: '查看个股结构',
        reason: '部分外部数据暂不可用',
      },
    ]);
  });

  it('suppresses advice wording instead of rendering it to consumers', () => {
    expect(getResearchQueueConsumerText('Buy before breakout with stop loss', 'zh', '当前条目的证据覆盖仍需复核。')).toBe('当前条目的证据覆盖仍需复核。');
    expect(getResearchQueueConsumerText('目标价 150，建议加仓', 'zh', '部分关键资料待补充')).toBe('部分关键资料待补充');
  });
});
