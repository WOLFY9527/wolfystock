import { describe, expect, it } from 'vitest';
import {
  normalizeBacktestReadiness,
  normalizeOptionsEvidence,
  normalizePortfolioRiskEvidence,
  normalizeRotationEvidence,
  normalizeScannerEvidence,
} from '../evidenceDisplay';

describe('evidenceDisplay', () => {
  it('maps scanner user-facing labels into compact Chinese user labels', () => {
    const normalized = normalizeScannerEvidence({
      evidencePacket: {
        userFacingLabels: ['仅观察', 'fallback 数据', 'provider_timeout', 'mock', 'MarketCache'],
        adminReasonCodes: ['provider_timeout', 'raw'],
        freshnessState: 'fallback',
        sourceRefs: [{ id: 's1' }, { id: 's2' }],
      },
    });

    expect(normalized.engine).toBe('scanner');
    expect(normalized.posture).toBe('observe_only');
    expect(normalized.displayLabel).toBe('仅供观察');
    expect(normalized.sourceRefCount).toBe(2);
    expect(normalized.limitationLabels).toContain('备用数据');
    expect(normalized.adminReasonCodes).toEqual([]);
    expect(normalized.limitationLabels.join(' ')).not.toMatch(/provider_timeout|MarketCache|mock|raw/i);
  });

  it('keeps rotation proxy-only evidence in observation wording without real fund-flow claims', () => {
    const normalized = normalizeRotationEvidence({
      rotationStateEvidence: {
        state: 'insufficient_evidence',
        stateLabel: '轮动代理证据',
        flowEvidenceType: 'proxy_only',
        flowLanguageAllowed: false,
        requiredDataStatus: {
          hasSufficientEvidence: false,
          summaryLabel: '分类观察',
        },
        riskLabels: ['gap_fade_risk', 'provider_timeout'],
      },
    });

    expect(normalized.engine).toBe('rotation');
    expect(normalized.posture).toBe('observe_only');
    expect(normalized.displayLabel).toBe('仅供观察');
    expect(normalized.limitationLabels).toEqual(expect.arrayContaining(['轮动代理证据', '分类观察']));
    expect(normalized.limitationLabels).toContain('真实资金流暂缺');
    expect(normalized.limitationLabels.join(' ')).not.toContain('真实资金流确认');
    expect(normalized.limitationLabels.join(' ')).not.toMatch(/gap_fade_risk|provider_timeout/i);
  });

  it('maps options blocked gate decisions to blocked posture', () => {
    const normalized = normalizeOptionsEvidence({
      gateDecision: '数据不足，禁止判断',
      gateIssues: ['fallback', 'dry-run', 'fixture'],
      failClosedReasonCodes: ['provider_timeout'],
    });

    expect(normalized.engine).toBe('options');
    expect(normalized.posture).toBe('blocked');
    expect(normalized.displayLabel).toBe('数据不足，禁止判断');
    expect(normalized.limitationLabels.join(' ')).not.toMatch(/fallback|dry-run|fixture|provider_timeout/i);
  });

  it('maps backtest research prototype readiness to non-success posture', () => {
    const normalized = normalizeBacktestReadiness({
      adjustedDataState: 'unknown_or_mixed',
      corporateActionState: 'not_ready',
      tradingCalendarState: 'available_bars_only',
      costModelState: 'baseline_bps_only',
      reproducibilityState: 'partial_without_dataset_lineage',
      professionalReadiness: {
        overall_state: 'research_prototype',
        professional_quant_ready: false,
      },
    });

    expect(normalized.engine).toBe('backtest');
    expect(['observe_only', 'review_required']).toContain(normalized.posture);
    expect(normalized.displayLabel).toBe('仅供观察');
    expect(normalized.tone).not.toBe('success');
    expect(normalized.limitationLabels).toEqual(expect.arrayContaining([
      '研究级回测',
      '专业级条件未满足',
      '数据口径需复核',
      '交易日历待确认',
      '复权/公司行动待确认',
    ]));
    expect(normalized.limitationLabels.join(' ')).not.toMatch(/debug|trace|raw|schema/i);
    expect(normalized.limitationLabels.join(' ')).not.toMatch(/research_prototype|unknown_or_mixed|available_bars_only|professional_quant_ready/i);
  });

  it('maps portfolio stale FX and mapping gaps to compact labels', () => {
    const normalized = normalizePortfolioRiskEvidence({
      fxFreshnessState: 'stale',
      holdingsLineageState: 'missing',
      benchmarkMappingState: 'missing',
      factorMappingState: 'missing',
      confidenceCap: {
        value: 60,
        reasonCodes: ['fx_rate_stale', 'benchmark_mapping_missing', 'factor_mapping_missing'],
        limitation_labels: ['仅供风险观察', '持仓来源待核验'],
      },
      portfolioRiskEvidence: {
        limitationLabels: ['FX 汇率已过期', '基准映射暂缺', '因子映射暂缺'],
        adminDiagnostics: { raw: true },
      },
    });

    expect(normalized.engine).toBe('portfolio_risk');
    expect(normalized.confidenceCap).toBe(60);
    expect(normalized.limitationLabels).toEqual(expect.arrayContaining([
      '仅供风险观察',
      'FX 汇率已过期',
      '持仓来源待核验',
      '基准映射暂缺',
      '因子映射暂缺',
    ]));
    expect(normalized.diagnostics).toBeUndefined();
  });

  it('preserves reason codes and diagnostics in admin mode when requested', () => {
    const normalized = normalizeScannerEvidence({
      evidencePacket: {
        userFacingLabels: ['仅观察'],
        adminReasonCodes: ['provider_timeout', 'not_enough_history'],
        diagnostics: { trace: 'collapsed-admin-only' },
      },
    }, {
      audience: 'admin',
      includeDiagnostics: true,
    });

    expect(normalized.adminReasonCodes).toEqual(['provider_timeout', 'not_enough_history']);
    expect(normalized.diagnostics).toEqual({ trace: 'collapsed-admin-only' });
  });

});
