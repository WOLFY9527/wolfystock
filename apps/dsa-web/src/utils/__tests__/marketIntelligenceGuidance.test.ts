import { describe, expect, it } from 'vitest';
import {
  marketIntelligenceReasonLabel,
  sanitizeMarketGuidanceCopy,
} from '../marketIntelligenceGuidance';

const FORBIDDEN_VISIBLE_COPY = /买入|卖出|止损|止盈|目标价|加仓|减仓|\bREAL\b|\bMIXED\b|\bFALLBACK\b|\bbuy\b|\bsell\b|stop.?loss|take.?profit|target price|position sizing/i;

describe('marketIntelligenceGuidance', () => {
  it('maps raw state labels and Chinese action wording into product-safe observation copy', () => {
    const copy = sanitizeMarketGuidanceCopy('REAL MIXED FALLBACK 买入 卖出 止损 止盈 目标价 加仓 减仓 仓位');

    expect(copy).toContain('AVAILABLE');
    expect(copy).toContain('PARTIAL');
    expect(copy).toContain('DELAYED');
    expect(copy).toContain('正向信号');
    expect(copy).toContain('反向信号');
    expect(copy).toContain('风险退出参考');
    expect(copy).toContain('上方参考');
    expect(copy).toContain('假设价格');
    expect(copy).toContain('暴露增加');
    expect(copy).toContain('暴露减少');
    expect(copy).toContain('观察状态');
    expect(copy).not.toMatch(FORBIDDEN_VISIBLE_COPY);
  });

  it('maps English advice wording into research language', () => {
    const copy = sanitizeMarketGuidanceCopy('buy sell stop-loss take-profit target price position sizing');

    expect(copy).toBe('positive signal reverse signal fixed-exit reference target-exit reference assumed price exposure assumption');
    expect(copy).not.toMatch(FORBIDDEN_VISIBLE_COPY);
  });

  it('uses consumer-safe reason labels for partial market data states', () => {
    expect(marketIntelligenceReasonLabel('fallback_or_proxy_evidence', 'zh')).toBe('部分数据暂不可用');
    expect(marketIntelligenceReasonLabel('fallback_proxy_or_observation_only_evidence_present', 'en')).toBe('Limited confidence evidence');

    const labels = [
      marketIntelligenceReasonLabel('fallback_or_proxy_evidence', 'zh'),
      marketIntelligenceReasonLabel('proxy_only_missing_real_source', 'zh'),
      marketIntelligenceReasonLabel('fallback_proxy_or_observation_only_evidence_present', 'en'),
    ].join(' ');

    expect(labels).not.toMatch(/\bREAL\b|\bMIXED\b|\bFALLBACK\b|fallback|proxy/i);
  });
});
