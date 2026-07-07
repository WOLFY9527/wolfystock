import { describe, expect, it } from 'vitest';

import {
  consumerSafeOperatorAction,
  getConsumerDataStateEntry,
  getConsumerDataStateLabel,
  isRawConsumerDataStateText,
  normalizeConsumerStateToken,
  sanitizeConsumerDataStateText,
} from '../consumerDataStateVocabulary';

const RAW_PATTERN = /universe|historical ohlcv|quote snapshot|provider|debug|dry-run|pipeline|operatorAction|failed_closed|packet|handoff|evidence families/i;

describe('consumerDataStateVocabulary', () => {
  it('defines the unified consumer data-state vocabulary with Chinese labels and next steps', () => {
    const cases = [
      ['ready', '数据可用', '继续观察关键证据是否保持一致。'],
      ['partial', '部分证据可用', '先查看已返回的模块，再等待缺口补齐。'],
      ['stale', '数据可能已过期', '等待下一次数据刷新后再扩大解读。'],
      ['missing', '证据待补', '等待数据补齐，或先查看已有历史记录。'],
      ['disabled', '暂未启用', '查看其他已启用模块，或等待功能开放。'],
      ['unavailable', '数据暂不可用', '稍后刷新，或查看其他仍可用的观察模块。'],
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

  it('is the zh/en owner for page-facing state labels', () => {
    expect(normalizeConsumerStateToken('freshness=unavailable')).toBe('freshness_unavailable');
    expect(getConsumerDataStateLabel('available', 'zh')).toBe('数据可用');
    expect(getConsumerDataStateLabel('available', 'en')).toBe('Data available');
    expect(getConsumerDataStateLabel('available', 'zh', 'short')).toBe('可用');
    expect(getConsumerDataStateLabel('available', 'en', 'short')).toBe('Available');
    expect(getConsumerDataStateEntry('ready', 'en')).toMatchObject({
      state: 'available',
      label: 'Data available',
      shortLabel: 'Available',
      severity: 'success',
      tone: 'positive',
    });
  });

  it('maps T146 readiness and operator text into consumer-safe Chinese copy', () => {
    expect(getConsumerDataStateEntry('failed-closed').label).toBe('已安全关闭');
    expect(getConsumerDataStateEntry('insufficient_coverage').label).toBe('部分证据可用');
    expect(getConsumerDataStateEntry('not_configured').label).toBe('证据待补');
    expect(isRawConsumerDataStateText('historical ohlcv provider debug pipeline')).toBe(true);
    expect(isRawConsumerDataStateText('research packet handoff evidence families')).toBe(true);
    expect(sanitizeConsumerDataStateText('quote snapshot provider error', 'missing')).toBe('关键输入暂缺，当前不形成候选或强结论。');
    expect(sanitizeConsumerDataStateText('No verified local peer group metadata', 'partial')).toBe('已返回部分真实数据，但仍有证据缺口，结论强度需要降低。');
    expect(consumerSafeOperatorAction('Refresh the scanner local universe and rerun readiness checks.', 'stale')).toBe('等待数据刷新后再查看。');
    expect(consumerSafeOperatorAction('Load recent local daily OHLCV before handoff', 'missing')).toBe('等待数据刷新后再查看。');
    expect(consumerSafeOperatorAction('pipeline repair required', 'maintenance')).toBe('数据管道维护中。');
  });

  it('keeps insufficient, blocked, initializing, and error semantics distinct when consumer behavior differs', () => {
    const available = getConsumerDataStateEntry('available');
    const insufficient = getConsumerDataStateEntry('insufficient');
    const insufficientHistory = getConsumerDataStateEntry('insufficient_history');
    const blocked = getConsumerDataStateEntry('blocked');
    const initializing = getConsumerDataStateEntry('initializing');
    const refreshing = getConsumerDataStateEntry('refreshing');
    const pending = getConsumerDataStateEntry('pending');
    const pendingHeavy = getConsumerDataStateEntry('pending-heavy');
    const unknown = getConsumerDataStateEntry('unknown');
    const error = getConsumerDataStateEntry('error');
    const failed = getConsumerDataStateEntry('failed');

    expect(available.state).toBe('available');
    expect(available.label).toBe('数据可用');

    expect(insufficient.state).toBe('insufficient');
    expect(insufficient.label).toBe('证据不足');
    expect(`${insufficient.label} ${insufficient.explanation} ${insufficient.nextStep}`).not.toMatch(RAW_PATTERN);

    expect(insufficientHistory.state).toBe('insufficient_history');
    expect(insufficientHistory.label).toBe('历史样本不足');

    expect(blocked.state).toBe('blocked');
    expect(blocked.label).toBe('当前无法分析');
    expect(blocked.shortLabel).toBe('已阻断');

    expect(initializing.state).toBe('initializing');
    expect(initializing.label).toBe('初始化中');
    expect(refreshing.state).toBe('refreshing');
    expect(refreshing.label).toBe('更新中');
    expect(pending.state).toBe('pending');
    expect(pending.label).toBe('正在等待数据确认');
    expect(pendingHeavy.state).toBe('pending_heavy');
    expect(pendingHeavy.label).toBe('多项数据仍待确认');
    expect(unknown.state).toBe('unknown');
    expect(unknown.label).toBe('状态暂不明确');

    expect(error.state).toBe('error');
    expect(error.label).toBe('数据读取异常');
    expect(error.shortLabel).toBe('读取异常');
    expect(failed.state).toBe('failed');
    expect(failed.label).toBe('数据读取异常');
  });
});
