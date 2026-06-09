import { describe, expect, it } from 'vitest';
import {
  buildLiquidityRegimeGaugeSummary,
  marketIntelligenceReasonLabel,
  sanitizeMarketGuidanceCopy,
} from '../marketIntelligenceGuidance';

const FORBIDDEN_VISIBLE_COPY = /买入|卖出|止损|止盈|目标价|加仓|减仓|\bREAL\b|\bMIXED\b|\bFALLBACK\b|\bREGIME\b|\bregime\b|\bprovider\b|\bruntime\b|\bcache\b|\bproxy\b|\bfallback\b|\bbuy\b|\bsell\b|stop.?loss|take.?profit|target price|position sizing/i;

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
    expect(marketIntelligenceReasonLabel('fallback_or_proxy_evidence', 'zh')).toBe('部分可用');
    expect(marketIntelligenceReasonLabel('fallback_proxy_or_observation_only_evidence_present', 'en')).toBe('Background only');
    expect(marketIntelligenceReasonLabel('score_contribution_not_allowed', 'zh')).toBe('暂不纳入评分');

    const labels = [
      marketIntelligenceReasonLabel('fallback_or_proxy_evidence', 'zh'),
      marketIntelligenceReasonLabel('proxy_only_missing_real_source', 'zh'),
      marketIntelligenceReasonLabel('fallback_proxy_or_observation_only_evidence_present', 'en'),
    ].join(' ');

    expect(labels).not.toMatch(/\bREAL\b|\bMIXED\b|\bFALLBACK\b|fallback|proxy/i);
  });

  it('does not title-case unknown internal reason codes into visible copy', () => {
    const labels = [
      marketIntelligenceReasonLabel('market_regime_synthesis', 'en'),
      marketIntelligenceReasonLabel('source_authority_router_rejected', 'en'),
      marketIntelligenceReasonLabel('provider_observation_only', 'en'),
      marketIntelligenceReasonLabel('cache_required', 'en'),
      marketIntelligenceReasonLabel('proxy_context_only', 'en'),
    ].join(' ');

    expect(labels).not.toMatch(FORBIDDEN_VISIBLE_COPY);
  });

  it('uses investor-readable liquidity product-state labels instead of raw regime wording', () => {
    const summary = buildLiquidityRegimeGaugeSummary({
      data: {
        score: {
          value: 67,
          regime: 'supportive',
          confidence: 0.78,
        },
        liquidityImpulseSynthesis: {
          liquidityImpulse: 'expanding_liquidity',
        },
      } as never,
      synthesisPromotable: true,
      usableEvidenceCount: 3,
      missingOrBlockedCount: 0,
    });

    expect(summary.title).toBe('资金面状态');
    expect(JSON.stringify(summary)).not.toMatch(FORBIDDEN_VISIBLE_COPY);
  });
});
