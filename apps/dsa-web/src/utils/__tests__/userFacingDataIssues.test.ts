import { describe, expect, it } from 'vitest';
import { sanitizeUserFacingDataIssue } from '../userFacingDataIssues';

describe('userFacingDataIssues', () => {
  it('maps common internal consumer-facing status and reason codes into calm Chinese copy', () => {
    expect(sanitizeUserFacingDataIssue('freshness_blocked:fallback', 'zh')).toBe('当前以延迟或替代数据为主，先保持观察。');
    expect(sanitizeUserFacingDataIssue('proxy_or_sample_evidence_blocked', 'zh')).toBe('当前证据以替代或样例数据为主，先保持观察。');
    expect(sanitizeUserFacingDataIssue('source_authority_or_score_gate_blocked', 'zh')).toBe('当前来源授权或评分条件未满足，暂不形成进一步判断。');
    expect(sanitizeUserFacingDataIssue('live_gex_not_implemented_v1', 'zh')).toBe('实时 Gamma 观察暂未提供。');
    expect(sanitizeUserFacingDataIssue('option_chain_unavailable', 'zh')).toBe('期权链数据暂不可用。');
    expect(sanitizeUserFacingDataIssue('observation_only_not_decision_grade', 'zh')).toBe('当前仅达到观察级，暂不形成判断。');
    expect(sanitizeUserFacingDataIssue('missing_spot_reference', 'zh')).toBe('缺少标的现价参考，暂不形成判断。');
    expect(sanitizeUserFacingDataIssue('insufficient_usable_contracts', 'zh')).toBe('可用合约不足，暂不形成判断。');
    expect(sanitizeUserFacingDataIssue('methodology_approval_missing', 'zh')).toBe('当前方法学确认未完成，先保持观察。');
    expect(sanitizeUserFacingDataIssue('provider_authority_missing', 'zh')).toBe('当前来源授权信息不足，先保持观察。');
    expect(sanitizeUserFacingDataIssue('redistribution_rights_missing', 'zh')).toBe('当前数据使用权限未确认，先保持观察。');
    expect(sanitizeUserFacingDataIssue('freshness=unavailable', 'zh')).toBe('当前时效状态未确认，数据暂不可用。');
    expect(sanitizeUserFacingDataIssue('avoidLowEvidence', 'zh')).toBe('当前证据质量偏弱，先保持观察。');
  });

  it('uses a generic fallback for unknown internal-looking codes without echoing the raw token', () => {
    const text = sanitizeUserFacingDataIssue('alpha_router_rejected:missing_v2', 'zh');

    expect(text).toBe('数据不足，结论仅供观察');
    expect(text).not.toContain('alpha_router_rejected:missing_v2');
  });

  it('maps consumer evidence internals without echoing raw source or diagnostic tokens', () => {
    expect(sanitizeUserFacingDataIssue('news', 'zh')).toBe('新闻数据暂缺');
    expect(sanitizeUserFacingDataIssue('fundamentals.eps', 'zh')).toBe('基本面数据缺失');
    expect(sanitizeUserFacingDataIssue('sourceRefs', 'zh')).toBe('部分来源细节已折叠。');
    expect(sanitizeUserFacingDataIssue('reason_codes', 'zh')).toBe('部分诊断细节已折叠。');
    expect(sanitizeUserFacingDataIssue('fx_fallback_1_to_1', 'zh')).toBe('汇率数据暂不可用');
    expect(sanitizeUserFacingDataIssue('price_fallback', 'zh')).toBe('价格数据暂不可完整确认');
    expect(sanitizeUserFacingDataIssue('error quote', 'zh')).toBe('实时缺失');
    expect(sanitizeUserFacingDataIssue('quote', 'en')).toBe('Realtime missing');
  });

  it('preserves already human-readable consumer copy', () => {
    expect(sanitizeUserFacingDataIssue('研究结论仍在补证，请稍后再看。', 'zh')).toBe('研究结论仍在补证，请稍后再看。');
  });
});
