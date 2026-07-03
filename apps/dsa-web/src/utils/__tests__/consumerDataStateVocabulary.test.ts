import { describe, expect, it } from 'vitest';

import {
  consumerSafeOperatorAction,
  getConsumerDataStateEntry,
  isRawConsumerDataStateText,
  sanitizeConsumerDataStateText,
} from '../consumerDataStateVocabulary';

const RAW_PATTERN = /universe|historical ohlcv|quote snapshot|provider|debug|dry-run|pipeline|operatorAction|failed_closed/i;

describe('consumerDataStateVocabulary', () => {
  it('defines the unified consumer data-state vocabulary with Chinese labels and next steps', () => {
    const cases = [
      ['ready', '数据可用', '继续观察关键证据是否保持一致。'],
      ['partial', '部分可用', '先查看已返回的模块，再等待缺口补齐。'],
      ['stale', '最近可用', '等待下一次数据刷新后再扩大解读。'],
      ['missing', '证据待补', '等待数据补齐，或先查看已有历史记录。'],
      ['disabled', '暂未启用', '查看其他已启用模块，或等待功能开放。'],
      ['unavailable', '暂不可用', '稍后刷新，或查看其他仍可用的观察模块。'],
      ['failed_closed', '已安全关闭', '等待证据恢复后再重新查看。'],
      ['maintenance', '维护中', '等待下一次数据刷新。'],
    ] as const;

    for (const [state, label, nextStep] of cases) {
      const entry = getConsumerDataStateEntry(state);
      expect(entry.label).toBe(label);
      expect(entry.nextStep).toBe(nextStep);
      expect(entry.explanation).toBeTruthy();
      expect(`${entry.label} ${entry.explanation} ${entry.nextStep}`).not.toMatch(RAW_PATTERN);
    }
  });

  it('maps T146 readiness and operator text into consumer-safe Chinese copy', () => {
    expect(getConsumerDataStateEntry('failed-closed').label).toBe('已安全关闭');
    expect(getConsumerDataStateEntry('insufficient_coverage').label).toBe('部分可用');
    expect(getConsumerDataStateEntry('not_configured').label).toBe('证据待补');
    expect(isRawConsumerDataStateText('historical ohlcv provider debug pipeline')).toBe(true);
    expect(sanitizeConsumerDataStateText('quote snapshot provider error', 'missing')).toBe('关键输入暂缺，当前不形成候选或强结论。');
    expect(consumerSafeOperatorAction('Refresh the scanner local universe and rerun readiness checks.', 'stale')).toBe('等待数据刷新后再查看。');
    expect(consumerSafeOperatorAction('pipeline repair required', 'maintenance')).toBe('数据管道维护中。');
  });
});
