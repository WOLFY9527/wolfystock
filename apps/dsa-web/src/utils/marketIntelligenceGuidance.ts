export type MarketIntelligenceGuidanceLocale = 'zh' | 'en';

const ZH_REASON_LABELS: Record<string, string> = {
  allocation_or_suitability_guidance: '适配边界',
  bounded_etf_authority_active: 'Bounded ETF authority active',
  cache_required: '需要缓存与时效门槛',
  counter_evidence_present: '反证已出现',
  credential_missing: '凭证未配置',
  data_insufficient: '数据不足',
  dependency_missing: '依赖未就绪',
  direction_ready: '方向可用',
  fallback_or_proxy_evidence: '备用或代理证据',
  fallback_proxy_or_observation_only_evidence_present: '存在备用、代理或观察级证据',
  freshness_floor_required: '需要满足时效下限',
  ineligible_bounded_etf: 'Bounded ETF set is not eligible',
  insufficient_score_grade_evidence: '评分级证据不足',
  market_direction_readiness_context: '方向可用性边界',
  missing_provider_configuration: '提供方运行契约未配置',
  missing_required_windows: 'Required ETF windows are missing',
  missing_scoring_evidence: '评分级证据缺口',
  missing_scoring_pillars: '评分支柱缺失',
  no_meaningful_score_grade_pillars: '没有足够的评分级支柱',
  not_investment_advice: '非投资建议',
  observation_only: '仅观察态',
  observation_only_discount: '仅观察证据',
  observation_only_evidence: '观察级证据',
  official_fed_liquidity_contract_not_configured: 'Fed 流动性官方契约未配置',
  partial_coverage: '覆盖不完整',
  provider_absent: '所需提供方未配置',
  provider_forbidden_for_use_case: '当前用途不允许该来源',
  provider_observation_only: '提供方仅允许观察',
  proxy_context_only: '代理数据仅作上下文',
  proxy_only_missing_real_source: '缺少真实数据源',
  proxy_or_observation_only_evidence: '代理或观察级证据',
  score_contribution_not_allowed: '不满足评分级要求',
  score_grade_evidence: '评分级证据',
  source_authority_router_rejected: '来源权限未通过',
  trade_instruction: '操作边界',
  trust_gate_blocked: '信任门禁阻断',
  unavailable_source: '来源不可用',
  watch_only_language: '仅观察语言',
};

const EN_REASON_LABELS: Record<string, string> = {
  allocation_or_suitability_guidance: 'Suitability boundary',
  bounded_etf_authority_active: 'Bounded ETF authority active',
  cache_required: 'Cache and freshness gate required',
  counter_evidence_present: 'Counter-evidence present',
  credential_missing: 'Credential missing',
  data_insufficient: 'Data insufficient',
  dependency_missing: 'Dependency not ready',
  direction_ready: 'Direction-ready',
  fallback_or_proxy_evidence: 'Fallback or proxy evidence',
  fallback_proxy_or_observation_only_evidence_present: 'Fallback, proxy, or observation-only evidence present',
  freshness_floor_required: 'Freshness floor required',
  ineligible_bounded_etf: 'Bounded ETF set is not eligible',
  insufficient_score_grade_evidence: 'Score-grade evidence insufficient',
  market_direction_readiness_context: 'Direction readiness boundary',
  missing_provider_configuration: 'Provider/runtime contract not configured',
  missing_required_windows: 'Required ETF windows are missing',
  missing_scoring_evidence: 'Score-grade evidence missing',
  missing_scoring_pillars: 'Scoring pillars missing',
  no_meaningful_score_grade_pillars: 'No meaningful score-grade pillars',
  not_investment_advice: 'Not investment advice',
  observation_only: 'Observation-only',
  observation_only_discount: 'Observation-only evidence',
  observation_only_evidence: 'Observation-only evidence',
  official_fed_liquidity_contract_not_configured: 'Fed liquidity official contract not configured',
  partial_coverage: 'Partial coverage',
  provider_absent: 'Required provider not configured',
  provider_forbidden_for_use_case: 'Source not allowed for this use case',
  provider_observation_only: 'Provider is observation-only',
  proxy_context_only: 'Proxy data is context-only',
  proxy_only_missing_real_source: 'Real source missing',
  proxy_or_observation_only_evidence: 'Proxy or observation-only evidence',
  score_contribution_not_allowed: 'Not score-grade eligible',
  score_grade_evidence: 'Score-grade evidence',
  source_authority_router_rejected: 'Source authority gate did not pass',
  trade_instruction: 'Execution boundary',
  trust_gate_blocked: 'Trust gate blocked',
  unavailable_source: 'Source unavailable',
  watch_only_language: 'Observation-only language',
};

function normalizeReason(value?: string | null): string {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function titleCaseFromCode(value: string): string {
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function marketIntelligenceReasonLabel(
  value?: string | null,
  locale: MarketIntelligenceGuidanceLocale = 'zh',
): string {
  const normalized = normalizeReason(value);
  if (!normalized) {
    return locale === 'en' ? 'Data availability unconfirmed' : '数据状态待确认';
  }
  const labels = locale === 'en' ? EN_REASON_LABELS : ZH_REASON_LABELS;
  return labels[normalized] || titleCaseFromCode(normalized);
}

export function marketIntelligenceReasonLabels(
  values: Array<string | null | undefined>,
  locale: MarketIntelligenceGuidanceLocale = 'zh',
  limit = 3,
): string[] {
  const seen = new Set<string>();
  const labels: string[] = [];
  values.forEach((value) => {
    const label = marketIntelligenceReasonLabel(value, locale);
    if (seen.has(label)) return;
    seen.add(label);
    labels.push(label);
  });
  return labels.slice(0, limit);
}

export function sanitizeMarketGuidanceCopy(value?: string | null, fallback = '仅供研究观察。'): string {
  const text = String(value || fallback).trim() || fallback;
  return text
    .replaceAll('非买卖建议', '非投资建议')
    .replaceAll('买入', '投资动作')
    .replaceAll('卖出', '投资动作')
    .replaceAll('加仓', '调整动作')
    .replaceAll('减仓', '调整动作')
    .replaceAll('仓位', '执行尺度')
    .replace(/\bbuy\b/gi, 'investment action')
    .replace(/\bsell\b/gi, 'investment action')
    .replace(/\badd\b/gi, 'adjust')
    .replace(/\breduce\b/gi, 'adjust')
    .replace(/position[-\s]?size/gi, 'execution sizing');
}
