import type { MarketOverviewPanel } from '../api/marketOverview';
import type { MarketBriefingResponse, MarketDecisionSemantics, MarketRegimeSynthesis, MarketTemperatureResponse } from '../api/market';
import type { LiquidityMonitorResponse } from '../api/liquidityMonitor';

export type MarketIntelligenceGuidanceLocale = 'zh' | 'en';

export type DirectionSummaryVariant = 'neutral' | 'success' | 'caution' | 'danger' | 'info';

export type MarketDirectionalSummary = {
  title: string;
  currentLabel: string;
  confidenceLabel: string;
  regimePhrase: string;
  actionFrame: string;
  biasVariant: DirectionSummaryVariant;
  confidenceVariant: DirectionSummaryVariant;
  supportingTitle: string;
  supportingDrivers: string[];
  blockingTitle: string;
  blockingDrivers: string[];
  watchTitle: string;
  watchItems: string[];
};

export type LiquidityRegimeGaugeSummary = {
  title: string;
  stateLabel: string;
  degreeLabel: string;
  trendLabel: string;
  usableEvidenceLabel: string;
  blockedEvidenceLabel: string;
  implicationLines: string[];
  stateVariant: DirectionSummaryVariant;
};

type MarketDirectionalPanels = {
  sectorRotation?: MarketOverviewPanel;
  fundsFlow?: MarketOverviewPanel;
  crypto?: MarketOverviewPanel;
};

const ZH_REASON_LABELS: Record<string, string> = {
  allocation_or_suitability_guidance: '适配边界',
  bounded_etf_authority_active: 'ETF authority 已启用',
  cache_required: '需要缓存与时效门槛',
  counter_evidence_present: '反证已出现',
  credential_missing: '凭证未配置',
  data_insufficient: '数据不足',
  dependency_missing: '依赖未就绪',
  direction_ready: '可形成方向判断',
  fallback_or_proxy_evidence: '仅有备用或代理证据',
  fallback_proxy_or_observation_only_evidence_present: '仅有备用、代理或观察证据',
  freshness_floor_required: '需要满足时效下限',
  ineligible_bounded_etf: 'ETF authority 未满足可用条件',
  insufficient_score_grade_evidence: '缺少评分级证据',
  market_direction_readiness_context: '方向判断边界',
  missing_provider_configuration: '提供方运行契约未配置',
  missing_required_windows: 'ETF 必要时窗缺失',
  missing_scoring_evidence: '缺少评分级证据',
  missing_scoring_pillars: '缺少评分级证据',
  no_meaningful_score_grade_pillars: '缺少评分级证据',
  not_investment_advice: '非投资建议',
  observation_only: '仅作观察',
  observation_only_discount: '仅作观察',
  observation_only_evidence: '观察证据',
  official_fed_liquidity_contract_not_configured: 'Fed 流动性官方契约未配置',
  partial_coverage: '覆盖不完整',
  provider_absent: '所需提供方未配置',
  provider_forbidden_for_use_case: '当前来源不适用于该判断',
  provider_observation_only: '当前来源仅作观察',
  proxy_context_only: '代理数据仅作观察',
  proxy_only_missing_real_source: '需要权威来源',
  proxy_or_observation_only_evidence: '仅有代理或观察证据',
  score_contribution_not_allowed: '不参与方向判断',
  score_grade_evidence: '评分级证据',
  source_authority_router_rejected: '需要权威来源',
  trade_instruction: '操作边界',
  trust_gate_blocked: '信任门禁阻断',
  unavailable_source: '来源不可用',
  watch_only_language: '仅观察语言',
  true_flow_data_missing: '缺少真实流向确认',
  flow_methodology_missing: '缺少流向方法学确认',
  benchmark_proxy_missing: '基准代理覆盖不足',
  proxy_quote_missing: '代理行情缺失',
  proxy_stale: '代理行情过期',
  proxy_windows_missing: '代理时窗缺失',
  provider_unavailable: '数据源当前不可用',
  tickflow_permission_unavailable: '权限未覆盖所需数据',
  fail_closed: '未满足升级条件',
  runtime_metadata: '运行契约已存在',
  not_required: '当前不需要',
  present: '已就绪',
  installed: '已安装',
  missing: '缺失',
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

export function joinMarketReasonLabels(
  values: Array<string | null | undefined>,
  locale: MarketIntelligenceGuidanceLocale = 'zh',
  limit = 3,
  fallback = locale === 'en' ? 'Data boundary pending confirmation' : '数据边界待确认',
): string {
  const labels = marketIntelligenceReasonLabels(values, locale, limit);
  return labels.length ? labels.join('、') : fallback;
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

function uniqueLimited(items: Array<string | null | undefined>, limit: number, fallback: string): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  items.forEach((item) => {
    const value = String(item || '').trim();
    if (!value || seen.has(value)) return;
    seen.add(value);
    result.push(value);
  });
  return result.length ? result.slice(0, limit) : [fallback];
}

function confidenceBand(
  label?: string | null,
  value?: number | null,
): 'high' | 'medium' | 'low' | 'unavailable' {
  if (label === 'high' || label === 'medium' || label === 'low') {
    return label;
  }
  if (label === 'insufficient') {
    return 'low';
  }
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'unavailable';
  }
  if (value >= 0.75) return 'high';
  if (value >= 0.45) return 'medium';
  if (value > 0) return 'low';
  return 'unavailable';
}

function confidenceDisplay(
  band: 'high' | 'medium' | 'low' | 'unavailable',
  locale: MarketIntelligenceGuidanceLocale,
): string {
  const labels = locale === 'en'
    ? { high: 'high', medium: 'medium', low: 'low', unavailable: 'unavailable' }
    : { high: '高', medium: '中', low: '低', unavailable: '不可用' };
  return labels[band];
}

function marketDirectionalPhrase(
  bias: 'bullish' | 'bearish' | 'neutral' | 'mixed' | 'insufficient_evidence',
  locale: MarketIntelligenceGuidanceLocale,
): string {
  const labels = locale === 'en'
    ? {
      bullish: 'bullish watch',
      bearish: 'bearish watch',
      neutral: 'neutral',
      mixed: 'mixed, cautious',
      insufficient_evidence: 'insufficient evidence',
    }
    : {
      bullish: '偏多观察',
      bearish: '偏弱观察',
      neutral: '中性',
      mixed: '中性偏谨慎',
      insufficient_evidence: '证据不足',
    };
  return labels[bias];
}

function marketActionFrame(
  bias: 'bullish' | 'bearish' | 'neutral' | 'mixed' | 'insufficient_evidence',
  locale: MarketIntelligenceGuidanceLocale,
): string {
  if (locale === 'en') {
    if (bias === 'insufficient_evidence') return 'No strong directional call';
    if (bias === 'mixed') return 'Wait for confirmation';
    return 'Observe mainlines';
  }
  if (bias === 'insufficient_evidence') return '不支持强方向判断';
  if (bias === 'mixed') return '等待确认';
  return '观察主线';
}

function localizedEvidenceLabel(value: string | null | undefined, locale: MarketIntelligenceGuidanceLocale): string {
  const label = String(value || '').trim();
  if (locale !== 'en') {
    return label;
  }
  const labels: Record<string, string> = {
    标普500: 'S&P 500',
    比特币: 'Bitcoin',
    美国10年期国债收益率: 'US 10Y',
    美元指数: 'US Dollar Index',
    A股宽度: 'CN breadth',
    小盘股轮动: 'Small-cap rotation',
    备用或代理证据偏多: 'Fallback/proxy evidence present',
    简报置信度不足: 'Briefing confidence unavailable',
  };
  return labels[label] || label;
}

function evidenceQualityNumber(synthesis?: MarketRegimeSynthesis, key?: string): number | undefined {
  const value = key ? synthesis?.evidenceQuality?.[key] : undefined;
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function deriveMarketBias(
  temperature: MarketTemperatureResponse,
  decisionReliable: boolean,
  synthesis?: MarketRegimeSynthesis,
  semantics?: MarketDecisionSemantics,
): 'bullish' | 'bearish' | 'neutral' | 'mixed' | 'insufficient_evidence' {
  const confidence = temperature.confidence ?? synthesis?.confidence;
  const scoreGradeCount = semantics?.directionReadiness?.scoreGradePillars.count
    ?? evidenceQualityNumber(synthesis, 'scoringEvidenceCount')
    ?? 0;
  const missingCount = semantics?.directionReadiness?.missingPillars.count
    ?? evidenceQualityNumber(synthesis, 'dataGapCount')
    ?? synthesis?.dataGaps.length
    ?? 0;
  const insufficient = Boolean(
    !decisionReliable
    || temperature.conclusionAllowed === false
    || temperature.temperatureAvailable === false
    || temperature.isReliable === false
    || semantics?.posture === 'data_insufficient'
    || semantics?.directionReadiness?.status === 'data_insufficient'
    || synthesis?.primaryRegime === 'data_insufficient'
    || confidenceBand(synthesis?.confidenceLabel, confidence) === 'low'
    || confidenceBand(synthesis?.confidenceLabel, confidence) === 'unavailable'
    || scoreGradeCount < 3
  );
  if (insufficient) {
    return 'insufficient_evidence';
  }

  const primaryRegime = String(synthesis?.primaryRegime || '').toLowerCase();
  const posture = String(semantics?.posture || '').toLowerCase();
  const counterCount = synthesis?.counterEvidence.length ?? 0;
  const driverCount = synthesis?.topDrivers.length ?? 0;
  if (missingCount > 0 || counterCount >= Math.max(2, driverCount)) {
    return 'mixed';
  }
  if (/risk_on|liquidity_expansion|goldilocks|offensive/.test(`${primaryRegime} ${posture}`)) {
    return 'bullish';
  }
  if (/risk_off|stress|contraction|defensive|tight/.test(`${primaryRegime} ${posture}`)) {
    return 'bearish';
  }

  const overallScore = temperature.scores?.overall?.value;
  if (typeof overallScore === 'number' && Number.isFinite(overallScore)) {
    if (overallScore >= 60) return 'bullish';
    if (overallScore <= 40) return 'bearish';
  }
  return 'neutral';
}

export function buildMarketDirectionalSummary({
  temperature,
  briefing,
  panels,
  decisionReliable,
  locale,
}: {
  temperature: MarketTemperatureResponse;
  briefing: MarketBriefingResponse;
  panels: MarketDirectionalPanels;
  decisionReliable: boolean;
  locale: MarketIntelligenceGuidanceLocale;
}): MarketDirectionalSummary {
  const synthesis = temperature.marketRegimeSynthesis;
  const semantics = temperature.marketDecisionSemantics;
  const bias = deriveMarketBias(temperature, decisionReliable, synthesis, semantics);
  const confidence = confidenceBand(
    semantics?.postureConfidence.label || synthesis?.confidenceLabel,
    temperature.confidence ?? synthesis?.confidence,
  );
  const fallbackPressure = (temperature.fallbackInputCount ?? 0) + (temperature.excludedInputCount ?? 0);
  const supportFromSynthesis = synthesis?.topDrivers.map((item) => localizedEvidenceLabel(item.label, locale)) || [];
  const supportFromSemantics = [
    ...(semantics?.styleTilts || []).map((item) => item.label || item.detail),
    ...(semantics?.confirmationSignals || []).map((item) => item.label || item.detail || item.signal),
  ].map((item) => (typeof item === 'string' ? item : ''));
  const blockingDrivers = uniqueLimited([
    ...(synthesis?.counterEvidence || []).map((item) => localizedEvidenceLabel(item.label || item.key, locale)),
    ...(synthesis?.dataGaps || []).map((item) => localizedEvidenceLabel(item.label || item.key, locale)),
    ...(semantics?.dataGaps || []).map((item) => localizedEvidenceLabel(item.label || item.key, locale)),
    ...(semantics?.postureConfidence.capReasons || []).map((reason) => marketIntelligenceReasonLabel(reason, locale)),
    fallbackPressure > 0 ? (locale === 'en' ? 'fallback/proxy evidence present' : '备用或代理证据偏多') : '',
    briefing.isReliable === false || briefing.isFallback ? (locale === 'en' ? 'briefing confidence unavailable' : '简报置信度不足') : '',
  ], 3, locale === 'en' ? 'No major blocker returned' : '暂无高亮阻塞');
  const watchItems = uniqueLimited([
    ...(panels.sectorRotation?.items || []).map((item) => localizedEvidenceLabel(item.label || item.symbol, locale)),
    ...(panels.fundsFlow?.items || []).map((item) => localizedEvidenceLabel(item.label || item.symbol, locale)),
    ...(panels.crypto?.items || []).map((item) => localizedEvidenceLabel(item.label || item.symbol, locale)),
  ], 3, locale === 'en' ? 'Wait for confirmed themes' : '等待确认主线');

  return {
    title: 'Market Bias / Direction Summary',
    currentLabel: locale === 'en'
      ? `Current market: ${marketDirectionalPhrase(bias, locale)}`
      : `当前市场：${marketDirectionalPhrase(bias, locale)}`,
    confidenceLabel: locale === 'en'
      ? `Evidence strength: ${confidenceDisplay(confidence, locale)}`
      : `证据强度：${confidenceDisplay(confidence, locale)}`,
    regimePhrase: synthesis?.primaryRegime && bias !== 'insufficient_evidence'
      ? marketDirectionalPhrase(bias, locale)
      : marketDirectionalPhrase(bias, locale),
    actionFrame: marketActionFrame(bias, locale),
    biasVariant: bias === 'bullish' ? 'success' : bias === 'bearish' ? 'danger' : bias === 'insufficient_evidence' || bias === 'mixed' ? 'caution' : 'info',
    confidenceVariant: confidence === 'high' ? 'success' : confidence === 'medium' ? 'info' : 'caution',
    supportingTitle: locale === 'en' ? 'Supporting drivers' : '支持驱动',
    supportingDrivers: uniqueLimited([...supportFromSynthesis, ...supportFromSemantics], 3, locale === 'en' ? 'No score-grade driver returned' : '暂无评分级支持证据'),
    blockingTitle: locale === 'en' ? 'Blocking / risk drivers' : '主要拖累',
    blockingDrivers,
    watchTitle: locale === 'en' ? 'Observable directions' : '可观察方向',
    watchItems,
  };
}

export function buildLiquidityRegimeGaugeSummary({
  data,
  synthesisPromotable,
  usableEvidenceCount,
  missingOrBlockedCount,
}: {
  data: LiquidityMonitorResponse;
  synthesisPromotable: boolean;
  usableEvidenceCount: number;
  missingOrBlockedCount: number;
}): LiquidityRegimeGaugeSummary {
  const confidence = confidenceBand(undefined, data.score.confidence);
  const evidenceInsufficient = !synthesisPromotable
    || confidence === 'low'
    || confidence === 'unavailable'
    || usableEvidenceCount <= 0
    || data.score.regime === 'unavailable';
  const regime = data.score.regime;
  const state = evidenceInsufficient
    ? '证据不足'
    : regime === 'abundant' || regime === 'supportive'
      ? '宽松'
      : regime === 'tight'
        ? '偏紧'
        : regime === 'stress'
          ? '紧张'
          : '中性';
  const trend = evidenceInsufficient
    ? '未知'
    : data.liquidityImpulseSynthesis?.liquidityImpulse === 'expanding_liquidity'
      ? '改善'
      : data.liquidityImpulseSynthesis?.liquidityImpulse === 'contracting_liquidity'
        ? '走弱'
        : data.liquidityImpulseSynthesis?.liquidityImpulse === 'balanced_liquidity'
          ? '持平'
          : '未知';
  const implicationLines = evidenceInsufficient
    ? ['流动性证据不足', '仅可作为观察背景']
    : state === '宽松'
      ? ['流动性背景偏支持', '仍需等待价格与广度确认']
      : state === '偏紧' || state === '紧张'
        ? ['流动性不能作为风险增强理由', '优先观察压力是否缓和']
        : ['流动性仅可作为观察背景', '等待确认'];

  return {
    title: 'Liquidity Regime Gauge',
    stateLabel: `流动性状态：${state}`,
    degreeLabel: `刻度 ${Number.isFinite(data.score.value) ? Math.round(data.score.value) : 0} / 100`,
    trendLabel: `趋势：${trend}`,
    usableEvidenceLabel: `可用证据 ${usableEvidenceCount}`,
    blockedEvidenceLabel: `缺失或阻塞 ${missingOrBlockedCount}`,
    implicationLines,
    stateVariant: evidenceInsufficient ? 'caution' : state === '宽松' ? 'success' : state === '偏紧' || state === '紧张' ? 'danger' : 'info',
  };
}
