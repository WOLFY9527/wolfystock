import { describe, expect, it } from 'vitest';
import {
  getConsumerStatusLabel,
  mapConsumerStatusText,
  normalizeConsumerStatusToken,
} from '../consumerStatusLabels';

describe('consumerStatusLabels', () => {
  it('maps required raw status tokens into consumer-safe Chinese labels', () => {
    expect(getConsumerStatusLabel('available', 'zh')).toBe('数据可用');
    expect(getConsumerStatusLabel('ready', 'zh')).toBe('数据可用');
    expect(getConsumerStatusLabel('unavailable', 'zh')).toBe('数据暂不可用');
    expect(getConsumerStatusLabel('stale', 'zh')).toBe('数据可能已过期');
    expect(getConsumerStatusLabel('degraded', 'zh')).toBe('数据质量受限');
    expect(getConsumerStatusLabel('partial', 'zh')).toBe('部分证据可用');
    expect(getConsumerStatusLabel('pending', 'zh')).toBe('正在等待数据确认');
    expect(getConsumerStatusLabel('initializing', 'zh')).toBe('初始化中');
    expect(getConsumerStatusLabel('refreshing', 'zh')).toBe('更新中');
    expect(getConsumerStatusLabel('pending-heavy', 'zh')).toBe('多项数据仍待确认');
    expect(getConsumerStatusLabel('blocked', 'zh')).toBe('当前无法分析');
    expect(getConsumerStatusLabel('insufficient', 'zh')).toBe('证据不足');
    expect(getConsumerStatusLabel('insufficient_history', 'zh')).toBe('历史样本不足');
    expect(getConsumerStatusLabel('error', 'zh')).toBe('数据读取异常');
    expect(getConsumerStatusLabel('failed', 'zh')).toBe('数据读取异常');
    expect(getConsumerStatusLabel('proxy', 'zh')).toBe('间接参考');
    expect(getConsumerStatusLabel('proxy-only', 'zh')).toBe('仅有间接参考，证据强度受限');
    expect(getConsumerStatusLabel('mixed', 'zh')).toBe('状态不一致');
    expect(getConsumerStatusLabel('lowConfidence', 'zh')).toBe('置信度较低');
    expect(getConsumerStatusLabel('low_confidence', 'zh')).toBe('置信度较低');
    expect(getConsumerStatusLabel('score-grade', 'zh')).toBe('评分等级');
    expect(getConsumerStatusLabel('score_grade', 'zh')).toBe('评分等级');
    expect(getConsumerStatusLabel('freshness=unavailable', 'zh')).toBe('数据新鲜度暂不可用');
    expect(getConsumerStatusLabel('freshness unavailable', 'zh')).toBe('数据新鲜度暂不可用');
    expect(getConsumerStatusLabel('insufficient_evidence', 'zh')).toBe('证据不足');
    expect(getConsumerStatusLabel('no_data', 'zh')).toBe('暂无可用数据');
    expect(getConsumerStatusLabel('empty', 'zh')).toBe('暂无可用数据');
    expect(getConsumerStatusLabel('unknown', 'zh')).toBe('状态暂不明确');
  });

  it('normalizes camelCase, snake_case, and key=value tokens consistently', () => {
    expect(normalizeConsumerStatusToken('lowConfidence')).toBe('low_confidence');
    expect(normalizeConsumerStatusToken('score-grade')).toBe('score_grade');
    expect(normalizeConsumerStatusToken('freshness=unavailable')).toBe('freshness_unavailable');
  });

  it('maps common research status phrases into consumer-safe Chinese copy', () => {
    expect(mapConsumerStatusText('Evidence missing', 'zh')).toBe('证据不足');
    expect(mapConsumerStatusText('Evidence quality is acceptable', 'zh')).toBe('证据质量可供继续观察');
    expect(mapConsumerStatusText('Low-evidence filter active', 'zh')).toBe('当前按低证据条件整理');
    expect(mapConsumerStatusText('Relative strength is above the research threshold', 'zh')).toBe('相对强弱已达到研究阈值');
    expect(mapConsumerStatusText('Scenario lab is unavailable because base score-grade regime evidence is missing.', 'zh')).toBe('基准情景证据不足，当前无法生成情景结果。');
    expect(mapConsumerStatusText('Gamma evidence status is unavailable, so gamma-sensitive conclusions remain capped.', 'zh')).toBe('Gamma 相关证据暂不可用，因此相关结论需保持保守。');
    expect(mapConsumerStatusText('Breadth participation weakens quickly under the selected stress.', 'zh')).toBe('所选压力情景下，市场广度会较快转弱。');
    expect(mapConsumerStatusText('Volatility structure flips into a defensive posture.', 'zh')).toBe('波动结构会转入偏防御状态。');
    expect(mapConsumerStatusText('Research planning only; not a personalized decision basis.', 'zh')).toBe('仅供研究规划观察，不构成个性化判断依据。');
  });
});
