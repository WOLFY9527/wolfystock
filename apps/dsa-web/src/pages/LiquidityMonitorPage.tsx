import type React from 'react';
import { useEffect, useState } from 'react';
import { Activity, Gauge, Waves } from 'lucide-react';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import {
  liquidityMonitorApi,
  type LiquidityCapitalFlowSignal,
  type LiquidityMonitorFreshness,
  type LiquidityMonitorIndicator,
  type LiquidityImpulseSynthesis,
  type LiquidityImpulseSynthesisEvidenceItem,
  type LiquidityMonitorRegime,
  type LiquidityMonitorResponse,
} from '../api/liquidityMonitor';
import {
  buildOfficialRiskSourceReadinessView,
  marketApi,
  type OfficialRiskSourceReadiness,
} from '../api/market';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import {
  LiquidityImpulseSynthesisHeader,
  type LiquidityImpulseHeaderEvidenceView,
  type LiquidityImpulseSynthesisHeaderView,
} from '../components/liquidity-monitor/LiquidityImpulseSynthesisHeader';
import {
  TerminalChip,
  TerminalDenseTable,
  TerminalDisclosure,
  TerminalGrid,
  TerminalMetric,
  TerminalPageHeading,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal/TerminalPrimitives';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import { OfficialMacroAuthorityDiagnostics } from '../components/common/OfficialMacroAuthorityDiagnostics';
import { buildOfficialMacroAuthorityDiagnosticsView } from '../components/common/officialMacroAuthorityDiagnosticsData';
import { formatDateTime, formatPercent, formatSignedNumber } from '../utils/format';
import { cn } from '../utils/cn';
import { buildDataSourcesSetupHref, buildProviderOpsSetupHref } from '../utils/productSetupSurface';
import {
  MARKET_DECISION_NOT_READY_NOTICE,
  buildLiquidityRegimeGaugeSummary,
  decisionReadinessStateLabel,
  decisionReadinessVariant,
  type DecisionReadinessState,
  type DecisionReadinessSummary,
  type LiquidityRegimeGaugeSummary,
} from '../utils/marketIntelligenceGuidance';
import { useProductSurface } from '../hooks/useProductSurface';

const REGIME_LABELS: Record<LiquidityMonitorRegime, string> = {
  abundant: '充裕',
  supportive: '支撑',
  neutral: '中性',
  tight: '偏紧',
  stress: '紧张',
  unavailable: '不可用',
};

const REGIME_TONE: Record<LiquidityMonitorRegime, string> = {
  abundant: 'text-emerald-300',
  supportive: 'text-cyan-200',
  neutral: 'text-white/78',
  tight: 'text-amber-200',
  stress: 'text-rose-300',
  unavailable: 'text-white/38',
};

const FRESHNESS_LABELS: Record<LiquidityMonitorFreshness, string> = {
  live: '实时',
  cached: '缓存',
  delayed: '延迟',
  stale: '过期',
  fallback: '备用',
  mock: '备用',
  error: '异常',
  unavailable: '不可用',
};

const INDICATOR_LABEL_OVERRIDES: Record<string, string> = {
  credit_spread: '信用利差',
  crypto_funding: 'Crypto 资金费率',
  crypto_spot_momentum: 'Crypto 现货动量',
  us_etf_flow_proxy: '美股资金流',
  us_breadth_proxy: '美国市场广度',
  us_rates_pressure: '美国利率压力',
  usd_pressure: '美元压力',
  vix_pressure: '波动率压力',
};

const EVIDENCE_ITEM_LABEL_OVERRIDES: Record<string, string> = {
  'liquidity_monitor:btc': 'BTC 流动性代理',
  'liquidity_monitor:btc_momentum': 'BTC 动量',
  'liquidity_monitor:crypto_spot_momentum': 'Crypto 现货动量',
  'liquidity_monitor:cn_hk_flows': '中港资金流',
  'liquidity_monitor:funding': '资金费率',
  'liquidity_monitor:usd_pressure': '美元压力',
  'liquidity_monitor:us_rates_pressure': '美国利率压力',
  'BTC': 'BTC 动量',
  'CN/HK Flows': '中港资金流',
  'Funding': '资金费率',
  'US Rates / 利率压力': '美国利率压力',
  'USD / 美元压力': '美元压力',
};

function statusLabel(status: LiquidityMonitorIndicator['status']): string {
  if (status === 'live') return '实时';
  if (status === 'partial') return '部分可用';
  return '暂不可用';
}

function chipVariantForStatus(status: LiquidityMonitorIndicator['status']): 'neutral' | 'success' | 'caution' | 'info' {
  if (status === 'live') return 'success';
  if (status === 'partial') return 'info';
  return 'neutral';
}

function chipVariantForFreshness(freshness: LiquidityMonitorFreshness): 'neutral' | 'success' | 'caution' | 'danger' | 'info' {
  if (freshness === 'live') return 'success';
  if (freshness === 'cached' || freshness === 'delayed') return 'info';
  if (freshness === 'stale' || freshness === 'fallback' || freshness === 'mock') return 'caution';
  if (freshness === 'error') return 'danger';
  return 'neutral';
}

function scoreLabel(value: number): string {
  return Number.isFinite(value) ? String(Math.round(value)) : '--';
}

function confidenceLabel(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return '0%';
  return `${Math.round(value * 100)}%`;
}

function liquidityCoverageInputLabel(data: LiquidityMonitorResponse): string {
  const contract = data.coverageContract;
  if (!contract) {
    return '待确认';
  }
  return `${contract.fulfilledInputCount} / ${contract.requiredInputCount}`;
}

function contributionLabel(indicator: LiquidityMonitorIndicator): string {
  const value = Number(indicator.scoreContribution || 0);
  if (!indicator.includedInScore) {
    return '不计分';
  }
  if (value === 0) {
    return '0';
  }
  return value > 0 ? `+${value}` : String(value);
}

function detailReason(indicator: LiquidityMonitorIndicator): string {
  return indicator.summary || '当前没有额外说明。';
}

function displayLabel(indicator: LiquidityMonitorIndicator): string {
  return INDICATOR_LABEL_OVERRIDES[indicator.key] || indicator.label;
}

function evidenceProductLabel(item: LiquidityImpulseSynthesisEvidenceItem): string {
  const rawLabel = item.label || '';
  return EVIDENCE_ITEM_LABEL_OVERRIDES[item.key]
    || EVIDENCE_ITEM_LABEL_OVERRIDES[rawLabel]
    || rawLabel
    || pillarLabel(item.pillar)
    || '流动性线索待确认';
}

const IMPULSE_LABELS: Record<string, string> = {
  expanding_liquidity: '流动性扩张',
  contracting_liquidity: '流动性收缩',
  balanced_liquidity: '流动性均衡',
  data_insufficient: '数据不足',
};

const SUBTYPE_LABELS: Record<string, string> = {
  broad_liquidity_expansion: '广谱流动性扩张',
  crypto_beta_expansion: 'Crypto Beta 扩张',
  rates_driven_tightening: '利率驱动收紧',
  dollar_driven_tightening: '美元驱动收紧',
  risk_deleveraging: '风险去杠杆',
  data_insufficient: '数据不足',
};

const CONFIDENCE_LABELS: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
  insufficient: '不足',
};

const CAPITAL_FLOW_CONTRADICTION_LABELS: Record<string, string> = {
  btc_not_confirming_growth_absorption: 'BTC 未确认当前吸纳',
  rates_not_easing_broadly: '利率线索尚未同步转松',
  gold_not_confirming_growth_absorption: '黄金未确认当前吸纳',
  cross_asset_rotation_split: '跨资产轮动暂未同向',
};

const PILLAR_LABELS: Record<string, string> = {
  rates_pressure: '利率压力',
  dollar_pressure: '美元压力',
  volatility_stress: '波动率压力',
  crypto_liquidity_beta: '资金面',
  risk_asset_demand: '风险资产需求',
  funding_stress: '资金面',
  equity_flow_proxy: '资金面',
  breadth_confirmation: '市场宽度确认',
  china_liquidity_context: '中港资金面',
};

const EVIDENCE_DIRECTION_LABELS: Record<string, string> = {
  supports_expansion: '支持扩张',
  supports_contraction: '支持收缩',
  positive: '正向',
  negative: '负向',
  contradicts_expansion: '反向于扩张',
  contradicts_contraction: '反向于收缩',
};

const EVIDENCE_REASON_LABELS: Record<string, string> = {
  conflicts_with_primary_regime: '与主结论冲突',
  missing_direction_or_magnitude: '缺少方向或幅度',
  score_contribution_not_allowed: '当前不允许计分',
  observation_only_discount: '仅观察，不升格结论',
  freshness_discount: '时效折价',
  source_tier_discount: '来源层级折价',
  provider_unavailable: '数据源不可用',
  fallback_source: '仅备用来源',
};

const LIQUIDITY_BLOCKING_REASON_LABELS: Record<string, string> = {
  partial_coverage: '部分数据暂不可用',
  observation_only: '观察线索',
  proxy_only_missing_real_source: '待补充指标',
  proxy_context_only: '观察线索',
  source_authority_router_rejected: '待补充指标',
  provider_forbidden_for_use_case: '待补充指标',
  provider_observation_only: '观察线索',
  provider_unavailable: '部分数据暂不可用',
  trust_gate_blocked: '信任门禁阻断',
  provider_absent: '部分数据暂不可用',
  unavailable_source: '部分数据暂不可用',
  indicator_unavailable: '指标不可用',
};
const LIQUIDITY_UNKNOWN_BLOCKING_REASON_LABEL = '关键来源仍待确认';
const LIQUIDITY_UNKNOWN_EVIDENCE_REASON_LABEL = '数据边界待确认';

type LiquidityCoverageReadinessSummary = {
  state: 'ready' | 'insufficient' | 'missing';
  stateLabel: string;
  stateChipVariant: 'neutral' | 'success' | 'caution';
  directionLabel: '可参考' | '部分可参考' | '不可判断';
  directionExplanation: string;
  scoreGradeCount: number;
  observationOnlyCount: number;
  missingOrUnavailableCount: number;
  summaryLine: string;
  blockingReasonsLine: string;
  blockingReasons: string[];
};

type LiquidityIndicatorBucketSummary = {
  count: number;
  namesLine: string;
};

type LiquidityBreadthTruthStripView = {
  stateLabel: string;
  stateVariant: 'neutral' | 'success' | 'caution' | 'info';
  sourceLabel: string;
  sourceVariant: 'neutral' | 'success' | 'caution' | 'info';
  freshnessLabel: string;
  freshnessVariant: 'neutral' | 'success' | 'caution' | 'danger' | 'info';
  coverageLabel: string;
  coverageVariant: 'neutral' | 'success' | 'caution' | 'info';
  summary: string;
  sourceDetail: string | null;
  missingSummary: string | null;
  limitationSummary: string | null;
};

const BREADTH_INPUT_LABELS: Record<string, string> = {
  ADVANCERS: '上涨家数',
  DECLINERS: '下跌家数',
  UNCHANGED: '平盘家数',
  ADVANCE_DECLINE_RATIO: '上涨/下跌比',
  NEW_HIGHS: '新高家数',
  NEW_LOWS: '新低家数',
  HIGH_LOW_RATIO: '新高/新低比',
  SECTORS_UP: '行业上涨',
  SECTORS_DOWN: '行业下跌',
  RSP_SPY: 'RSP/SPY',
  IWM_SPY: 'IWM/SPY',
  QQQ_SPY: 'QQQ/SPY',
};

const BREADTH_LIMITATION_LABELS: Record<string, string> = {
  representative_sample_not_full_market_breadth: '代表性样本，不等于全市场宽度',
  proxy_only_missing_real_source: '缺少官方/授权宽度主源',
  partial_coverage: '覆盖不完整',
  proxy_or_placeholder_not_authorized_breadth: '来源层级未达到官方/授权宽度',
  source_authority_router_rejected: '来源权限未通过',
  'requires_official_or_authorized.us_market_breadth': '缺少官方/授权宽度提供方',
};

const CAPITAL_FLOW_REGIME_LABELS: Record<string, string> = {
  inflow: '资金净流入观察',
  outflow: '资金净流出观察',
  balanced: '资金均衡观察',
  mixed: '资金分化观察',
  unavailable: '资金方向待确认',
};

const CAPITAL_FLOW_CONFIDENCE_LABELS: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
  insufficient: '不足',
};

const CAPITAL_FLOW_PRESSURE_LABELS: Record<string, string> = {
  absorbing: '吸纳',
  lagging: '滞后',
  outflow: '流出',
  inflow: '流入',
  defensive: '防御',
  rotating_out: '轮动流出',
  rotating_in: '轮动流入',
  neutral: '中性',
};

function titleCaseFromSnake(value?: string | null): string {
  if (!value) return '待确认';
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function capitalFlowRegimeLabel(signal?: LiquidityCapitalFlowSignal | null): string {
  if (!signal) return '待确认';
  return signal.capitalFlowLabel
    || (signal.capitalFlowRegime ? CAPITAL_FLOW_REGIME_LABELS[signal.capitalFlowRegime] || titleCaseFromSnake(signal.capitalFlowRegime) : '待确认');
}

function capitalFlowConfidenceLabel(signal?: LiquidityCapitalFlowSignal | null): string {
  if (!signal) return '待确认';
  if (signal.confidenceText) return signal.confidenceText;
  if (signal.confidenceLabel && CAPITAL_FLOW_CONFIDENCE_LABELS[signal.confidenceLabel]) {
    return CAPITAL_FLOW_CONFIDENCE_LABELS[signal.confidenceLabel];
  }
  if (typeof signal.confidence === 'string' && CAPITAL_FLOW_CONFIDENCE_LABELS[signal.confidence]) {
    return CAPITAL_FLOW_CONFIDENCE_LABELS[signal.confidence];
  }
  if (typeof signal.confidence === 'number') {
    if (signal.confidence >= 0.75) return '高';
    if (signal.confidence >= 0.45) return '中';
    if (signal.confidence > 0) return '低';
    return '不足';
  }
  return '待确认';
}

function capitalFlowPressureLabel(value?: string | null): string {
  if (!value) return '待确认';
  return CAPITAL_FLOW_PRESSURE_LABELS[value] || titleCaseFromSnake(value);
}

function capitalFlowAssetLabel(value?: string | null): string {
  if (!value) return '待确认';
  if (!value.includes('_') && /^[a-z]{2,5}$/.test(value)) {
    return value.toUpperCase();
  }
  return titleCaseFromSnake(value);
}

function capitalFlowContradictionLabel(value?: string | null): string {
  if (!value) return '待确认';
  return CAPITAL_FLOW_CONTRADICTION_LABELS[value] || '线索暂未同向';
}

function capitalFlowFlagLabels(signal?: LiquidityCapitalFlowSignal | null): string[] {
  if (!signal) return [];
  return uniqueCompactValues([
    signal.isPartial ? '部分' : null,
    signal.isStale ? '最近可用' : null,
    signal.isFallback ? '最近可用' : null,
  ], 3);
}

function impulseCodeLabel(value?: string | null): string {
  if (!value) return '待确认';
  const normalized = value.trim().toLowerCase().replace(/[\s-]+/g, '_');
  if (normalized === 'no_clear_edge' || normalized === 'neutral_edge') return '方向不明确';
  return IMPULSE_LABELS[value] || titleCaseFromSnake(value);
}

function subtypeLabel(value?: string | null): string {
  if (!value) return '待确认';
  return SUBTYPE_LABELS[value] || titleCaseFromSnake(value);
}

function synthesisConfidenceLabel(label?: string | null, confidence?: number | null): string {
  if (label && CONFIDENCE_LABELS[label]) {
    return CONFIDENCE_LABELS[label];
  }
  if (typeof confidence === 'number') {
    if (confidence >= 0.75) return '高';
    if (confidence >= 0.45) return '中';
    if (confidence > 0) return '低';
  }
  return '未返回';
}

function pillarLabel(value?: string | null): string {
  if (!value) return '待确认';
  return PILLAR_LABELS[value] || '流动性支柱待确认';
}

function evidenceDirectionLabel(value?: string | null): string | null {
  if (!value) return null;
  return EVIDENCE_DIRECTION_LABELS[value] || '方向待确认';
}

function evidenceReasonLabel(value?: string | null): string | null {
  if (!value) return null;
  return EVIDENCE_REASON_LABELS[value] || LIQUIDITY_UNKNOWN_EVIDENCE_REASON_LABEL;
}

function evidenceItemDisplayLabel(item: LiquidityImpulseSynthesisEvidenceItem): string {
  return evidenceProductLabel(item);
}

function buildEvidenceMeta(
  item: LiquidityImpulseSynthesisEvidenceItem,
  kind: 'driver' | 'counter' | 'gap',
): string {
  const parts: string[] = [];
  parts.push(pillarLabel(item.pillar));

  if (kind === 'driver') {
    const direction = evidenceDirectionLabel(item.direction);
    if (direction) parts.push(direction);
    if (typeof item.impact === 'number') parts.push(`影响 ${formatSignedNumber(item.impact, 2)}`);
    if (typeof item.signal === 'number') parts.push(`信号 ${formatSignedNumber(item.signal, 2)}`);
  } else if (kind === 'counter') {
    const reason = evidenceReasonLabel(item.reason);
    if (reason) parts.push(reason);
    if (typeof item.signal === 'number') parts.push(`信号 ${formatSignedNumber(item.signal, 2)}`);
  } else {
    const reason = evidenceReasonLabel(item.reason);
    if (reason) parts.push(reason);
    if (item.degradationReason) parts.push(
      LIQUIDITY_BLOCKING_REASON_LABELS[item.degradationReason] || LIQUIDITY_UNKNOWN_EVIDENCE_REASON_LABEL,
    );
  }

  if (item.source) parts.push(item.source);
  if (item.observationOnly) parts.push('仅观察');
  if (item.proxyOnly) parts.push('代理证据');
  if (item.scoreContributionAllowed === false) parts.push('不计分');

  return parts.filter(Boolean).join(' · ');
}

function buildEvidenceView(
  items: LiquidityImpulseSynthesisEvidenceItem[],
  kind: 'driver' | 'counter' | 'gap',
  limit: number,
): LiquidityImpulseHeaderEvidenceView[] {
  return items.slice(0, limit).map((item) => ({
    key: item.key,
    label: evidenceItemDisplayLabel(item),
    meta: buildEvidenceMeta(item, kind),
  }));
}

function buildLiquidityImpulseSynthesisView(
  synthesis: LiquidityImpulseSynthesis | undefined,
): LiquidityImpulseSynthesisHeaderView {
  if (!synthesis) {
    return {
      state: 'missing',
      title: '流动性方向待返回',
      summary: '当前流动性脉冲摘要未返回，不推断扩张或收缩。',
      stateChipLabel: '载荷缺失',
      stateChipVariant: 'neutral',
      confidenceLabel: '未返回',
      confidenceValueText: '',
      dominantDrivers: [],
      counterEvidence: [],
      dataGaps: [],
      notInvestmentAdvice: false,
    };
  }

  const evidenceQuality = synthesis.evidenceQuality || {};
  const scoringEvidenceCount = typeof evidenceQuality.scoringEvidenceCount === 'number'
    ? evidenceQuality.scoringEvidenceCount
    : synthesis.dominantDrivers.length;
  const scoringPillarCount = typeof evidenceQuality.scoringPillarCount === 'number'
    ? evidenceQuality.scoringPillarCount
    : undefined;
  const discountedEvidenceCount = typeof evidenceQuality.discountedEvidenceCount === 'number'
    ? evidenceQuality.discountedEvidenceCount
    : undefined;
  const dataGapCount = typeof evidenceQuality.dataGapCount === 'number'
    ? evidenceQuality.dataGapCount
    : synthesis.dataGaps.length;
  const realScoringEvidenceCount = typeof evidenceQuality.realScoringEvidenceCount === 'number'
    ? evidenceQuality.realScoringEvidenceCount
    : undefined;
  const allScoringEvidenceProxyOnly = evidenceQuality.allScoringEvidenceProxyOnly === true;
  const proxyOnlyScoringCount = typeof evidenceQuality.proxyOnlyScoringCount === 'number'
    ? evidenceQuality.proxyOnlyScoringCount
    : 0;
  const lowConfidence = (
    synthesis.liquidityImpulse === 'data_insufficient'
    || synthesis.confidenceLabel === 'insufficient'
    || synthesis.confidenceLabel === 'low'
    || synthesis.confidence < 0.45
  );
  const proxyOnlyDecision = Boolean(
    allScoringEvidenceProxyOnly
    || (proxyOnlyScoringCount > 0 && (realScoringEvidenceCount == null || realScoringEvidenceCount <= 0))
  );
  const promotable = !lowConfidence && !proxyOnlyDecision;
  const qualityFlags = [
    `证据 ${scoringEvidenceCount}`,
    scoringPillarCount != null ? `支柱 ${scoringPillarCount}` : '',
    discountedEvidenceCount != null ? `折价 ${discountedEvidenceCount}` : '',
    `缺口 ${dataGapCount}`,
    proxyOnlyDecision ? '仅代理' : '',
  ].filter(Boolean).join(' · ');
  const contradictionCount = Math.min(synthesis.counterEvidence.length, 3);
  const gapCount = Math.min(dataGapCount, 3);
  const impulseLabel = impulseCodeLabel(synthesis.liquidityImpulse);

  return {
    state: promotable ? 'ready' : 'insufficient',
    title: promotable
      ? impulseCodeLabel(synthesis.liquidityImpulse)
      : synthesis.liquidityImpulse === 'data_insufficient'
        ? '流动性方向数据不足'
        : '流动性方向待确认',
    summary: promotable
      ? `${impulseLabel}：主驱动 ${Math.min(synthesis.dominantDrivers.length, 3)} 项，反证 ${contradictionCount} 项，缺口 ${gapCount} 项。`
      : proxyOnlyDecision
        ? `返回方向为“${impulseLabel}”，但当前可计分证据仅来自代理或观察项，不升级为真实扩张或收缩结论。`
        : synthesis.liquidityImpulse === 'data_insufficient'
          ? '当前可用证据不足，只展示缺口与残余信号。'
          : `返回方向为“${impulseLabel}”，但当前置信度不足，只展示支持证据、反证与数据缺口。`,
    stateChipLabel: promotable
      ? '主结论'
      : synthesis.liquidityImpulse === 'data_insufficient'
        ? '数据不足'
        : proxyOnlyDecision
          ? '代理证据'
          : '低置信度',
    stateChipVariant: promotable ? 'success' : 'caution',
    impulseLabel,
    subtypeLabel: subtypeLabel(synthesis.subtype),
    confidenceLabel: synthesisConfidenceLabel(synthesis.confidenceLabel, synthesis.confidence),
    confidenceValueText: formatPercent(synthesis.confidence, { mode: 'ratio' }),
    directionScoreText: formatSignedNumber(synthesis.directionScore, 2, { showZeroSign: true }),
    qualityLine: qualityFlags,
    dominantDrivers: buildEvidenceView(synthesis.dominantDrivers, 'driver', 3),
    counterEvidence: buildEvidenceView(synthesis.counterEvidence, 'counter', 3),
    dataGaps: buildEvidenceView(synthesis.dataGaps, 'gap', 3),
    notInvestmentAdvice: Boolean(synthesis.notInvestmentAdvice),
  };
}

function scoreGradeEvidenceCount(indicators: LiquidityMonitorIndicator[]): number {
  return indicators.filter((indicator) => (
    indicator.coverageDiagnostics?.scoreContributionAllowed === true || indicator.includedInScore
  )).length;
}

function isObservationOnlyIndicator(indicator: LiquidityMonitorIndicator | null | undefined): boolean {
  if (!indicator) {
    return false;
  }
  if (indicator.coverageDiagnostics?.observationOnly === true) {
    return true;
  }

  const inputs = indicator.evidence?.inputs || [];
  return inputs.length > 0
    && inputs.some((input) => input.observationOnly)
    && !inputs.some((input) => input.scoreContributionAllowed);
}

function isMissingOrUnavailableIndicator(indicator: LiquidityMonitorIndicator | null | undefined): boolean {
  if (!indicator) {
    return false;
  }
  if (indicator.status === 'unavailable') {
    return true;
  }

  const diagnostics = indicator.coverageDiagnostics;
  if (!diagnostics) {
    return false;
  }

  return diagnostics.configuredProviderAvailable === false
    || diagnostics.realSourceAvailable === false
    || diagnostics.sourceAuthorityRouteRejected === true
    || diagnostics.missingInputs.length > 0;
}

function pushUniqueReason(target: string[], value?: string | null): void {
  if (!value || target.includes(value)) {
    return;
  }
  target.push(value);
}

function humanizeBlockingReason(reason: string): string {
  if (reason === '仅在真实 funding 快照存在时显示') {
    return '需要真实资金费率快照';
  }
  if (LIQUIDITY_BLOCKING_REASON_LABELS[reason]) {
    return LIQUIDITY_BLOCKING_REASON_LABELS[reason];
  }
  if (reason.startsWith('requires_')) {
    return '所需提供方未配置';
  }
  return LIQUIDITY_UNKNOWN_BLOCKING_REASON_LABEL;
}

function indicatorBlockingReasons(indicator: LiquidityMonitorIndicator): string[] {
  const diagnostics = indicator.coverageDiagnostics;
  const reasons: string[] = [];

  if (diagnostics) {
    pushUniqueReason(reasons, diagnostics.scoreExclusionReason);
    pushUniqueReason(reasons, diagnostics.capReason);
    pushUniqueReason(reasons, diagnostics.degradationReason);
    pushUniqueReason(reasons, diagnostics.proxyObservationOnlyReason);
    pushUniqueReason(reasons, diagnostics.sourceAuthorityReason);
    (diagnostics.routeRejectedReasonCodes || []).forEach((reason) => pushUniqueReason(reasons, reason));
    if (reasons.length === 0 && diagnostics.observationOnly) {
      pushUniqueReason(reasons, 'observation_only');
    }
  }

  if (reasons.length === 0 && indicator.status === 'unavailable') {
    return [indicator.summary || LIQUIDITY_BLOCKING_REASON_LABELS.indicator_unavailable];
  }

  return reasons.map(humanizeBlockingReason);
}

function buildCoverageReadinessSummary(
  data: LiquidityMonitorResponse | null,
  synthesisView: LiquidityImpulseSynthesisHeaderView,
): LiquidityCoverageReadinessSummary {
  const indicators = data?.indicators || [];
  const scoreGradeCount = scoreGradeEvidenceCount(indicators);
  const observationOnlyCount = indicators.filter(isObservationOnlyIndicator).length;
  const missingOrUnavailableCount = indicators.filter(isMissingOrUnavailableIndicator).length;
  const blockedIndicators = indicators.filter((indicator) => (
    indicator.coverageDiagnostics?.scoreContributionAllowed === false || isMissingOrUnavailableIndicator(indicator)
  ));
  const blockingReasons = new Map<string, number>();

  blockedIndicators.forEach((indicator) => {
    indicatorBlockingReasons(indicator).forEach((reason) => {
      blockingReasons.set(reason, (blockingReasons.get(reason) || 0) + 1);
    });
  });

  const topBlockingReasons = Array.from(blockingReasons.entries())
    .sort((left, right) => right[1] - left[1])
    .slice(0, 3)
    .map(([reason]) => reason);

  const state = synthesisView.state === 'ready'
    ? 'ready'
    : synthesisView.state === 'missing'
      ? 'missing'
      : 'insufficient';
  const directionLabel = state === 'ready'
    ? '可参考'
    : scoreGradeCount > 0 || observationOnlyCount > 0
      ? '部分可参考'
      : '不可判断';
  const stateLabel = state === 'ready'
    ? '方向可用'
    : state === 'missing'
      ? '数据待返回'
      : '方向证据不足';
  const blockingLead = topBlockingReasons.length > 0 ? topBlockingReasons.join('、') : '关键来源仍待补齐';
  const directionExplanation = directionLabel === '可参考'
    ? '可计分证据已具备，当前可以把流动性方向作为研究背景继续跟踪。'
    : directionLabel === '部分可参考'
      ? `已有部分可计分证据，但仍受${blockingLead}限制。`
      : `当前不能判断流动性方向，主要因为${blockingLead}。`;
  const summaryLead = directionLabel === '可参考'
    ? '当前流动性方向可参考'
    : directionLabel === '部分可参考'
      ? '当前流动性方向仅部分可参考'
      : '当前流动性方向不可判断';
  const summaryLine = `${summaryLead}：可计分证据 ${scoreGradeCount}，观察证据 ${observationOnlyCount}，缺失证据 ${missingOrUnavailableCount}。`;

  return {
    state,
    stateLabel,
    stateChipVariant: state === 'ready' ? 'success' : state === 'insufficient' ? 'caution' : 'neutral',
    directionLabel,
    directionExplanation,
    scoreGradeCount,
    observationOnlyCount,
    missingOrUnavailableCount,
    summaryLine,
    blockingReasonsLine: `为什么不是完整方向结论：${topBlockingReasons.length > 0 ? topBlockingReasons.join('；') : '当前没有额外阻塞。'}`,
    blockingReasons: topBlockingReasons,
  };
}

function topIndicatorNames(
  indicators: LiquidityMonitorIndicator[],
  predicate: (indicator: LiquidityMonitorIndicator) => boolean,
  limit = 3,
): string[] {
  return indicators.reduce<string[]>((acc, indicator) => {
    if (acc.length >= limit) return acc;
    if (!indicator || !predicate(indicator)) return acc;
    const label = displayLabel(indicator);
    if (label && acc.indexOf(label) === -1) acc.push(label);
    return acc;
  }, []);
}

function summarizeIndicatorBucket(
  indicators: LiquidityMonitorIndicator[],
  predicate: (indicator: LiquidityMonitorIndicator) => boolean,
  fallback: string,
): LiquidityIndicatorBucketSummary {
  const names = topIndicatorNames(indicators, predicate);
  return {
    count: indicators.filter(predicate).length,
    namesLine: names.length ? names.join('、') : fallback,
  };
}

function isUsBreadthIndicator(indicator: LiquidityMonitorIndicator | null | undefined): indicator is LiquidityMonitorIndicator {
  return indicator?.key === 'us_breadth_proxy';
}

function formatBreadthInputLabel(value?: string | null): string {
  if (!value) return '待确认';
  return BREADTH_INPUT_LABELS[value] || value;
}

function breadthLimitationLabel(value?: string | null): string | null {
  if (!value) return null;
  return BREADTH_LIMITATION_LABELS[value] || humanizeBlockingReason(value);
}

function uniqueCompactValues(values: Array<string | null | undefined>, limit: number): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  values.forEach((value) => {
    const normalized = String(value || '').trim();
    if (!normalized || seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    result.push(normalized);
  });
  return result.slice(0, limit);
}

function buildBreadthTruthStripView(indicator: LiquidityMonitorIndicator): LiquidityBreadthTruthStripView | null {
  if (!isUsBreadthIndicator(indicator)) {
    return null;
  }

  const diagnostics = indicator.coverageDiagnostics;
  const evidence = indicator.evidence;
  const inputs = evidence?.inputs || [];
  const scoreGrade = diagnostics?.scoreContributionAllowed === true || indicator.includedInScore;
  const staleOrFallback = indicator.freshness === 'stale' || indicator.freshness === 'fallback' || indicator.freshness === 'mock';
  const degraded = !scoreGrade || staleOrFallback || evidence?.isPartial || diagnostics?.missingInputs.length;
  const proxyOnly = diagnostics?.proxyOnly === true
    || inputs.some((input) => input.observationOnly || input.scoreContributionAllowed === false || input.sourceAuthorityAllowed === false);
  const sourceTier = diagnostics?.sourceTier
    || inputs.find((input) => input.sourceTier)?.sourceTier
    || evidence?.inputs.find((input) => input.sourceType)?.sourceType
    || null;
  const rawSourceDetail = evidence?.sourceLabel
    || inputs.find((input) => input.sourceLabel)?.sourceLabel
    || null;
  const requiredCount = diagnostics?.requiredInputs.length || 0;
  const fulfilledCount = diagnostics?.fulfilledInputs.length || 0;
  const missingInputs = diagnostics?.missingInputs || [];
  const coverageRatio = requiredCount > 0 ? `${fulfilledCount}/${requiredCount}` : null;
  const limitationSummary = uniqueCompactValues([
    breadthLimitationLabel(diagnostics?.scoreExclusionReason),
    breadthLimitationLabel(diagnostics?.sourceAuthorityReason),
    ...((diagnostics?.routeRejectedReasonCodes || []).map((reason) => breadthLimitationLabel(reason))),
    breadthLimitationLabel(diagnostics?.degradationReason),
    breadthLimitationLabel(diagnostics?.capReason),
  ], 2).join('；') || null;
  const sourceLabel = sourceTier === 'official_public'
    ? '官方宽度'
    : sourceTier === 'authorized_licensed_feed'
      ? '授权宽度'
      : sourceTier === 'official_or_authorized_licensed_feed'
        ? '官方/授权宽度'
        : proxyOnly || /proxy|unofficial/i.test(String(sourceTier || ''))
          ? '观察宽度'
          : staleOrFallback || evidence?.isFallback || inputs.some((input) => input.isFallback)
            ? '最近一次可用宽度'
            : sourceTier
              ? '宽度来源待核实'
              : '来源待确认';
  const stateLabel = scoreGrade
    ? '可支撑判断'
    : indicator.status === 'unavailable'
      ? '证据不足'
      : proxyOnly || degraded
        ? '仅观察'
        : '参考受限';
  const stateVariant = scoreGrade
    ? 'success'
    : indicator.status === 'unavailable'
      ? 'neutral'
      : proxyOnly
        ? 'info'
        : 'caution';
  const coverageLabel = coverageRatio ? `覆盖 ${coverageRatio}` : '覆盖待确认';
  const coverageVariant = coverageRatio
    ? missingInputs.length === 0 && scoreGrade
      ? 'success'
      : missingInputs.length > 0
        ? 'caution'
        : 'info'
    : 'neutral';
  const missingSummary = missingInputs.length > 0
    ? `缺口：${missingInputs.map((value) => formatBreadthInputLabel(value)).join('、')}`
    : null;
  const summary = scoreGrade
    ? `当前以${sourceLabel}支撑主要判断。`
    : indicator.status === 'unavailable'
      ? `当前宽度证据不足，仅展示当前覆盖与缺口。`
      : sourceLabel === '观察宽度'
        ? '当前仅保留宽度观察，不支撑主要判断。'
        : `当前仅保留${sourceLabel}观察，不支撑主要判断。`;
  const sourceDetail = scoreGrade
    ? '官方市场宽度快照'
    : proxyOnly
      ? '公开市场宽度观察快照'
      : staleOrFallback || evidence?.isFallback || inputs.some((input) => input.isFallback)
        ? '最近一次可用宽度快照'
        : sourceTier === 'authorized_licensed_feed'
          ? '授权市场宽度快照'
          : sourceTier === 'official_or_authorized_licensed_feed'
            ? '官方/授权市场宽度快照'
            : sourceLabel === '来源待确认'
              ? rawSourceDetail
              : `${sourceLabel}快照`;

  return {
    stateLabel,
    stateVariant,
    sourceLabel,
    sourceVariant: scoreGrade ? 'success' : proxyOnly || staleOrFallback ? 'caution' : 'info',
    freshnessLabel: FRESHNESS_LABELS[indicator.freshness],
    freshnessVariant: chipVariantForFreshness(indicator.freshness),
    coverageLabel,
    coverageVariant,
    summary,
    sourceDetail,
    missingSummary,
    limitationSummary,
  };
}

const LiquidityBreadthTruthStrip: React.FC<{
  indicator: LiquidityMonitorIndicator;
  testId: string;
}> = ({ indicator, testId }) => {
  const view = buildBreadthTruthStripView(indicator);
  if (!view) {
    return null;
  }

  return (
    <div
      data-testid={testId}
      className="rounded-lg border border-white/[0.06] bg-black/10 px-3 py-2.5"
    >
      <div className="flex min-w-0 flex-wrap gap-1.5">
        <TerminalChip variant={view.stateVariant}>{view.stateLabel}</TerminalChip>
        <TerminalChip variant={view.sourceVariant}>{view.sourceLabel}</TerminalChip>
        <TerminalChip variant={view.freshnessVariant}>{view.freshnessLabel}</TerminalChip>
        <TerminalChip variant={view.coverageVariant}>{view.coverageLabel}</TerminalChip>
      </div>
      <p className="mt-2 text-xs leading-5 text-white/68">{view.summary}</p>
      {view.sourceDetail ? (
        <p className="mt-1 text-xs leading-5 text-white/52">依据：{view.sourceDetail}</p>
      ) : null}
      {view.missingSummary ? (
        <p className="mt-1 text-xs leading-5 text-white/52">{view.missingSummary}</p>
      ) : null}
      {view.limitationSummary ? (
        <p className="mt-1 text-xs leading-5 text-white/52">限制：{view.limitationSummary}</p>
      ) : null}
    </div>
  );
}

function buildLiquidityNextWatch(
  coverageSummary: LiquidityCoverageReadinessSummary,
  indicators: LiquidityMonitorIndicator[],
): string {
  const missing = topIndicatorNames(indicators, isMissingOrUnavailableIndicator, 2);
  const observation = topIndicatorNames(indicators, isObservationOnlyIndicator, 1);
  const parts = [
    missing.length ? `优先恢复 ${missing.join('、')}` : '',
    observation.length ? `继续观察 ${observation.join('、')}` : '',
    coverageSummary.directionLabel === '可参考' ? '确认新增反向线索是否改变压力方向' : '',
    '等待刷新后确认主线是否一致',
  ].filter(Boolean);
  return parts.length ? parts.join('；') : '等待新的关键指标恢复。';
}

function uniqueReadinessItems(items: Array<string | null | undefined>, limit: number, fallback: string): string[] {
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

function evidenceQualityNumber(data: LiquidityMonitorResponse, key: string): number {
  const value = data.liquidityImpulseSynthesis?.evidenceQuality?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function buildLiquidityDecisionReadiness(
  data: LiquidityMonitorResponse,
  coverageSummary: LiquidityCoverageReadinessSummary,
  synthesisView: LiquidityImpulseSynthesisHeaderView,
  indicators: LiquidityMonitorIndicator[],
): DecisionReadinessSummary {
  const scoringEvidenceCount = Math.max(
    coverageSummary.scoreGradeCount,
    data.score.includedIndicatorCount || 0,
    evidenceQualityNumber(data, 'scoringEvidenceCount'),
  );
  const confidence = Math.max(data.score.confidence || 0, data.liquidityImpulseSynthesis?.confidence || 0);
  const state: DecisionReadinessState = synthesisView.state === 'ready'
    && scoringEvidenceCount >= 2
    && confidence >= 0.45
    && data.score.regime !== 'unavailable'
    ? 'ready'
    : scoringEvidenceCount <= 0 && data.score.regime === 'unavailable'
      ? 'unavailable'
      : scoringEvidenceCount > 0 || coverageSummary.observationOnlyCount > 0 || synthesisView.state === 'insufficient'
        ? 'observe'
      : 'unavailable';
  const missingIndicators = topIndicatorNames(indicators, isMissingOrUnavailableIndicator, 3);
  const synthesisGaps = data.liquidityImpulseSynthesis?.dataGaps.map((item) => evidenceItemDisplayLabel(item)) || [];
  const proxyOnly = synthesisView.state !== 'ready' && synthesisView.stateChipLabel === '代理证据';
  const blockers = [
    ...coverageSummary.blockingReasons,
    proxyOnly ? '代理证据不能升级方向' : '',
    synthesisView.state === 'missing' ? '流动性脉冲载荷缺失' : '',
    data.score.regime === 'unavailable' ? '流动性分数不可用' : '',
    data.freshness.weakestIndicatorFreshness === 'fallback' || data.freshness.weakestIndicatorFreshness === 'stale'
      ? '存在备用或过期负担'
      : '',
  ];
  const nextEvidence = [
    ...missingIndicators.map((name) => `补齐 ${name}`),
    ...synthesisGaps,
    state === 'ready' ? '继续确认反证是否进入评分级' : '',
  ];

  return {
    state,
    stateLabel: decisionReadinessStateLabel(state),
    stateVariant: decisionReadinessVariant(state),
    qualityLabel: `证据质量：可计分 ${scoringEvidenceCount}/${Math.max(indicators.length, 1)} · 观察 ${coverageSummary.observationOnlyCount} · 缺失 ${coverageSummary.missingOrUnavailableCount}`,
    blockers: uniqueReadinessItems(blockers, 4, state === 'ready' ? '暂无关键阻塞' : '关键来源仍待补齐'),
    nextEvidence: uniqueReadinessItems(nextEvidence, 3, '等待新的评分级证据'),
    conclusion: state === 'ready'
      ? '当前证据可支持流动性方向的研究判断。'
      : MARKET_DECISION_NOT_READY_NOTICE,
  };
}

type LiquidityBiasSummary = {
  label: '偏宽松' | '偏收紧' | '无明显方向' | '仅观察' | '不可判断';
  variant: 'neutral' | 'success' | 'caution' | 'danger' | 'info';
  toneClassName: string;
  detail: string;
};

function buildLiquidityBiasSummary(
  data: LiquidityMonitorResponse,
  readinessSummary: DecisionReadinessSummary,
  synthesisView: LiquidityImpulseSynthesisHeaderView,
): LiquidityBiasSummary {
  if (readinessSummary.state === 'unavailable' || data.score.regime === 'unavailable') {
    return {
      label: '仅观察',
      variant: 'info',
      toneClassName: 'text-cyan-100',
      detail: '关键线索不足，当前不判断偏宽松或偏收紧。',
    };
  }

  if (readinessSummary.state === 'observe' || synthesisView.state !== 'ready') {
    return {
      label: '仅观察',
      variant: 'info',
      toneClassName: 'text-cyan-100',
      detail: '已有部分线索，但仍受时效或状态限制。',
    };
  }

  const impulse = data.liquidityImpulseSynthesis?.liquidityImpulse;
  if (impulse === 'expanding_liquidity') {
    return {
      label: '偏宽松',
      variant: 'success',
      toneClassName: 'text-emerald-200',
      detail: '流动性背景偏宽松，仍只作为研究背景。',
    };
  }
  if (impulse === 'contracting_liquidity') {
    return {
      label: '偏收紧',
      variant: 'caution',
      toneClassName: 'text-amber-200',
      detail: '流动性压力更强，继续观察反向线索是否改善。',
    };
  }
  if (impulse !== 'balanced_liquidity' && (data.score.regime === 'abundant' || data.score.regime === 'supportive')) {
    return {
      label: '偏宽松',
      variant: 'success',
      toneClassName: 'text-emerald-200',
      detail: '流动性背景偏宽松，仍只作为研究背景。',
    };
  }
  if (impulse !== 'balanced_liquidity' && (data.score.regime === 'tight' || data.score.regime === 'stress')) {
    return {
      label: '偏收紧',
      variant: 'caution',
      toneClassName: 'text-amber-200',
      detail: '流动性压力更强，继续观察反向线索是否改善。',
    };
  }

  return {
    label: '无明显方向',
    variant: 'neutral',
    toneClassName: 'text-white/78',
    detail: '方向未明，继续观察',
  };
}

function buildLiquidityMainGapLine(
  readinessSummary: DecisionReadinessSummary,
  coverageSummary: LiquidityCoverageReadinessSummary,
  missing: LiquidityIndicatorBucketSummary,
): string {
  const blockers = readinessSummary.blockers.filter((item) => item !== '暂无关键阻塞');
  if (blockers.length > 0) {
    return blockers.slice(0, 3).join('；');
  }
  if (coverageSummary.blockingReasons.length > 0) {
    return coverageSummary.blockingReasons.slice(0, 3).join('；');
  }
  if (missing.count > 0) {
    return missing.namesLine;
  }
  return readinessSummary.state === 'ready'
    ? '暂无关键阻塞，继续确认新增反证是否进入评分级。'
    : '关键来源仍待补齐。';
}

type ConsumerLiquidityStatusView = {
  availabilityLabel: '正常' | '观察中' | '暂不可用';
  availabilityVariant: 'success' | 'info' | 'neutral';
  regimeLabel: LiquidityBiasSummary['label'];
  heroTitle: string;
  observableCount: number;
  observableChipLabel: string;
  freshnessChipLabel: string;
  freshnessVariant: 'neutral' | 'success' | 'caution' | 'danger' | 'info';
  headline: string;
  availabilityDetail: string;
  scoringDetail: string;
  freshnessSummary: string;
  freshnessDetail: string;
};

type ConsumerLiquiditySummaryFact = {
  key: string;
  label: string;
  value: string;
  detail?: string | null;
};

type ConsumerLiquidityEvidenceRowView = {
  key: string;
  label: string;
  statusLabel: '可用' | '观察中' | '待补充';
  statusVariant: 'success' | 'info' | 'neutral';
  scoreLabel: '主要线索' | '观察线索' | '待补充';
  scoreVariant: 'success' | 'info' | 'caution';
  note: string;
  detail: string;
};

type ConsumerLiquidityVisualDriver = {
  key: string;
  label: string;
  detail: string;
  emphasisPct: number;
  valueLabel?: string;
  toneClassName: string;
  barClassName: string;
};

type ConsumerLiquidityCoverageSegment = {
  key: string;
  label: string;
  count: number;
  widthPct: number;
  chipVariant: 'neutral' | 'success' | 'caution' | 'info';
  barClassName: string;
};

const CONSUMER_FORBIDDEN_COPY_PATTERN = /provider|proxy|fallback|stale|mock|synthetic|reason|source|authority|cache|runtime|raw|json|diagnostic|official_or_authorized|marketcache|scorecontributionallowed|sourceauthorityallowed|yfinance|fred|binance|polygon|tushare|bucket|backend|snake_case|routeRejected|计分|评分|证据|覆盖|缺口|代理|提供方|数据源|官方|授权|来源|置信度|就绪/i;

function consumerFreshnessLabel(freshness: LiquidityMonitorFreshness): string {
  if (freshness === 'live') return '已更新';
  if (freshness === 'delayed') return '更新中';
  if (freshness === 'cached' || freshness === 'stale' || freshness === 'fallback' || freshness === 'mock') {
    return '最近可用';
  }
  return '暂不可用';
}

function topConsumerSignalLabel(
  data: LiquidityMonitorResponse,
  indicators: LiquidityMonitorIndicator[],
): string | null {
  const driver = data.liquidityImpulseSynthesis?.dominantDrivers[0];
  if (driver) {
    return evidenceItemDisplayLabel(driver);
  }
  const scoreReadyIndicator = indicators.find((indicator) => (
    indicator.coverageDiagnostics?.scoreContributionAllowed === true || indicator.includedInScore
  ));
  return scoreReadyIndicator ? displayLabel(scoreReadyIndicator) : null;
}

function consumerSafeIndicatorSummary(value?: string | null): string | null {
  const normalized = String(value || '').trim();
  if (!normalized) {
    return null;
  }
  if (CONSUMER_FORBIDDEN_COPY_PATTERN.test(normalized) || /[a-z]+_[a-z]+/.test(normalized)) {
    return null;
  }
  return normalized;
}

function pickConsumerEvidenceIndicators(indicators: LiquidityMonitorIndicator[]): LiquidityMonitorIndicator[] {
  const picked: LiquidityMonitorIndicator[] = [];
  const seen = new Set<string>();

  const append = (list: LiquidityMonitorIndicator[]) => {
    list.forEach((indicator) => {
      if (picked.length >= 4 || seen.has(indicator.key)) {
        return;
      }
      seen.add(indicator.key);
      picked.push(indicator);
    });
  };

  append(indicators.filter((indicator) => indicator.coverageDiagnostics?.scoreContributionAllowed === true || indicator.includedInScore).slice(0, 2));
  append(indicators.filter((indicator) => isObservationOnlyIndicator(indicator)).slice(0, 1));
  append(indicators.filter((indicator) => isMissingOrUnavailableIndicator(indicator)).slice(0, 1));
  append(indicators);

  return picked.slice(0, 4);
}

function buildConsumerEvidenceNote(indicator: LiquidityMonitorIndicator): string {
  const safeSummary = consumerSafeIndicatorSummary(indicator.summary);
  if (safeSummary) {
    return safeSummary;
  }

  const scoreReady = indicator.coverageDiagnostics?.scoreContributionAllowed === true || indicator.includedInScore;
  if (scoreReady) {
    return indicator.freshness === 'live'
      ? '当前作为可参考的资金面线索。'
      : '当前作为可参考的资金面线索，页面会继续自动刷新。';
  }
  if (indicator.status === 'unavailable') {
    return '待补充指标恢复后再看方向。';
  }
  if (isObservationOnlyIndicator(indicator)) {
    return '当前方向仅供观察，先作为资金面线索跟踪。';
  }
  if (isMissingOrUnavailableIndicator(indicator) || indicator.status === 'partial') {
    return '数据覆盖有限，先关注状态恢复。';
  }
  return '当前资金面线索可继续观察。';
}

function buildConsumerEvidenceDetail(indicator: LiquidityMonitorIndicator): string {
  const pieces = [
    `最近更新：${formatDateTime(indicator.updatedAt) || '待确认'}`,
  ];
  const diagnostics = indicator.coverageDiagnostics;
  if (diagnostics?.missingInputs.length) {
    pieces.push('待补信息见下方数据状态说明');
  } else if (indicator.coverageDiagnostics?.scoreContributionAllowed === true || indicator.includedInScore) {
    pieces.push('纳入当前状态观察');
  } else if (isObservationOnlyIndicator(indicator)) {
    pieces.push('保留为资金面线索');
  }
  return pieces.join(' · ');
}

function buildConsumerEvidenceRows(indicators: LiquidityMonitorIndicator[]): ConsumerLiquidityEvidenceRowView[] {
  return pickConsumerEvidenceIndicators(indicators).map((indicator) => {
    const scoreReady = indicator.coverageDiagnostics?.scoreContributionAllowed === true || indicator.includedInScore;
    const statusLabel = indicator.status === 'unavailable'
      ? '待补充'
      : scoreReady
        ? '可用'
        : '观察中';
    return {
      key: indicator.key,
      label: displayLabel(indicator),
      statusLabel,
      statusVariant: statusLabel === '可用' ? 'success' : statusLabel === '观察中' ? 'info' : 'neutral',
      scoreLabel: scoreReady ? '主要线索' : indicator.status === 'unavailable' ? '待补充' : '观察线索',
      scoreVariant: scoreReady ? 'success' : indicator.status === 'unavailable' ? 'caution' : 'info',
      note: buildConsumerEvidenceNote(indicator),
      detail: buildConsumerEvidenceDetail(indicator),
    };
  });
}

function buildConsumerSummaryFacts(
  data: LiquidityMonitorResponse,
  coverageSummary: LiquidityCoverageReadinessSummary,
  indicators: LiquidityMonitorIndicator[],
): ConsumerLiquiditySummaryFact[] {
  const topSignal = topConsumerSignalLabel(data, indicators);
  const observableNames = topIndicatorNames(indicators, (indicator) => indicator.status !== 'unavailable', 3);
  const observableCount = indicators.filter((indicator) => indicator.status !== 'unavailable').length;
  const observableValue = topSignal || observableNames[0] || '等待关键信号恢复';
  return [
    {
      key: 'observable',
      label: '仍可观察',
      value: observableValue,
      detail: topSignal ? '当前最先影响状态的资金面线索' : observableNames.length ? observableNames.join('、') : '当前没有稳定线索',
    },
    {
      key: 'dimensions',
      label: '可观察维度',
      value: observableCount > 0 ? `${observableCount} 项` : '等待恢复',
      detail: observableNames.length
        ? `${observableNames.join('、')} 等线索已返回`
        : coverageSummary.directionLabel === '可参考'
          ? '当前主要线索已返回'
          : '等待更多线索返回',
    },
    {
      key: 'updated',
      label: '最近更新',
      value: formatDateTime(data.freshness.latestAsOf) || '待确认',
      detail: consumerFreshnessLabel(data.freshness.status),
    },
  ];
}

function buildConsumerGapSummary(
  missing: LiquidityIndicatorBucketSummary,
  observation: LiquidityIndicatorBucketSummary,
  consumerView: ConsumerLiquidityStatusView,
): string {
  const observableLead = consumerView.observableCount > 0
    ? `当前仍有 ${consumerView.observableCount} 项线索可观察`
    : '当前没有稳定线索';
  if (missing.count > 0) {
    return `${observableLead}，其余 ${missing.count} 项待补信息已折叠。`;
  }
  if (observation.count > 0) {
    return `${observableLead}，其中部分资金面线索暂只保留观察。`;
  }
  if (consumerView.availabilityLabel === '暂不可用') {
    return `${observableLead}，等待更多资金面线索恢复。`;
  }
  return '当前主要线索已返回，继续跟踪后续变化。';
}

function clampPercent(value: number, min = 8, max = 100): number {
  if (!Number.isFinite(value)) {
    return min;
  }
  return Math.max(min, Math.min(max, value));
}

function evidenceIndicatorKey(item: LiquidityImpulseSynthesisEvidenceItem): string {
  return item.key.replace(/^liquidity_monitor:/, '');
}

function isCryptoSpotMomentumKey(value?: string | null): boolean {
  return value === 'crypto_spot_momentum' || value === 'liquidity_monitor:crypto_spot_momentum';
}

function cryptoSpotMomentumEvidenceLine(
  item: LiquidityImpulseSynthesisEvidenceItem,
  indicators: LiquidityMonitorIndicator[],
): string {
  const indicatorKey = evidenceIndicatorKey(item);
  const indicator = indicators.find((candidate) => candidate.key === indicatorKey);
  const candidates = [
    indicator?.summary,
    item.label,
  ];

  for (const candidate of candidates) {
    const value = String(candidate || '').trim();
    const match = value.match(/(\d+)\s*\/\s*(\d+)\s*上涨(?:\s*\|\s*)?均值\s*([+-]?\d+(?:\.\d+)?%?)/);
    if (match) {
      const [, upCount, totalCount, average] = match;
      const averageLabel = average.endsWith('%') ? average : `${average}%`;
      return `${upCount}/${totalCount} 上涨 | 均值 ${averageLabel}`;
    }
  }

  return '证据不足';
}

function buildConsumerCoverageSegments(
  coverageSummary: LiquidityCoverageReadinessSummary,
  indicatorCount: number,
): ConsumerLiquidityCoverageSegment[] {
  void indicatorCount;
  const rawSegments: Array<Omit<ConsumerLiquidityCoverageSegment, 'widthPct'>> = [
    {
      key: 'scoring',
      label: '可参考',
      count: coverageSummary.scoreGradeCount,
      chipVariant: 'success',
      barClassName: 'bg-emerald-300/80',
    },
    {
      key: 'observation',
      label: '观察中',
      count: coverageSummary.observationOnlyCount,
      chipVariant: 'info',
      barClassName: 'bg-cyan-300/75',
    },
    {
      key: 'missing',
      label: '待补充',
      count: coverageSummary.missingOrUnavailableCount,
      chipVariant: 'caution',
      barClassName: 'bg-amber-300/80',
    },
  ];

  const activeCount = rawSegments.filter((segment) => segment.count > 0).length;
  const reserved = activeCount > 0 ? activeCount * 8 : 0;
  const proportionalPool = Math.max(100 - reserved, 0);
  const proportionalTotal = rawSegments.reduce((sum, segment) => sum + Math.max(segment.count, 0), 0);

  return rawSegments.reduce<ConsumerLiquidityCoverageSegment[]>((segments, segment) => {
    const proportionalWidth = proportionalTotal > 0
      ? (Math.max(segment.count, 0) / proportionalTotal) * proportionalPool
      : 0;
    const widthPct = segment.count > 0 ? clampPercent(proportionalWidth + 8) : 0;
    if (segment.count > 0) {
      segments.push({
        ...segment,
        widthPct,
      });
    }
    return segments;
  }, []);
}

function buildConsumerVisualDrivers(
  data: LiquidityMonitorResponse,
  indicators: LiquidityMonitorIndicator[],
): ConsumerLiquidityVisualDriver[] {
  const dominantDrivers = data.liquidityImpulseSynthesis?.dominantDrivers || [];
  if (dominantDrivers.length > 0) {
    const emphasisBase = dominantDrivers.reduce((maxValue, item) => {
      const rawValue = Math.max(Math.abs(item.impact || 0), Math.abs(item.signal || 0), 0.12);
      return Math.max(maxValue, rawValue);
    }, 0.12);

    return dominantDrivers.slice(0, 3).map((item) => {
      const rawValue = Math.max(Math.abs(item.impact || 0), Math.abs(item.signal || 0), 0.12);
      const emphasisPct = clampPercent((rawValue / emphasisBase) * 100, 18, 100);
      const direction = evidenceDirectionLabel(item.direction);
      const isCryptoSpotMomentum = isCryptoSpotMomentumKey(evidenceIndicatorKey(item));
      const cryptoSpotMomentumEvidence = isCryptoSpotMomentum
        ? cryptoSpotMomentumEvidenceLine(item, indicators)
        : null;
      const detailParts = [
        direction,
        item.observationOnly ? '资金面线索' : '可参考线索',
      ].filter(Boolean);
      const contractionLike = item.direction === 'supports_contraction' || item.direction === 'negative';
      const expansionLike = item.direction === 'supports_expansion' || item.direction === 'positive';

      return {
        key: item.key,
        label: evidenceItemDisplayLabel(item),
        detail: cryptoSpotMomentumEvidence || detailParts.join(' · ') || '当前线索',
        emphasisPct,
        valueLabel: cryptoSpotMomentumEvidence || undefined,
        toneClassName: contractionLike
          ? 'text-amber-100'
          : expansionLike
            ? 'text-emerald-100'
            : 'text-cyan-100',
        barClassName: contractionLike
          ? 'from-amber-300/85 via-amber-200/70 to-transparent'
          : expansionLike
            ? 'from-emerald-300/85 via-emerald-200/70 to-transparent'
            : 'from-cyan-300/80 via-sky-200/65 to-transparent',
      };
    });
  }

  const scoreReadyIndicators = indicators.filter((indicator) => (
    indicator.coverageDiagnostics?.scoreContributionAllowed === true || indicator.includedInScore
  ));
  const rankedIndicators = (scoreReadyIndicators.length > 0 ? scoreReadyIndicators : indicators)
    .slice()
    .sort((left, right) => Math.abs(right.scoreContribution || 0) - Math.abs(left.scoreContribution || 0));
  const emphasisBase = rankedIndicators.reduce((maxValue, indicator) => {
    return Math.max(maxValue, Math.abs(indicator.scoreContribution || 0), 1);
  }, 1);

  return rankedIndicators.slice(0, 3).map((indicator) => ({
    key: indicator.key,
    label: displayLabel(indicator),
    detail: indicator.includedInScore || indicator.coverageDiagnostics?.scoreContributionAllowed
      ? '当前可参考线索'
      : '当前资金面线索',
    emphasisPct: clampPercent((Math.abs(indicator.scoreContribution || 0) / emphasisBase) * 100, 18, 100),
    toneClassName: 'text-cyan-100',
    barClassName: 'from-cyan-300/80 via-sky-200/65 to-transparent',
  }));
}

function buildConsumerLiquidityStatusView(
  data: LiquidityMonitorResponse,
  coverageSummary: LiquidityCoverageReadinessSummary,
  readinessSummary: DecisionReadinessSummary,
  synthesisView: LiquidityImpulseSynthesisHeaderView,
  indicators: LiquidityMonitorIndicator[],
): ConsumerLiquidityStatusView {
  const unavailableModules = topIndicatorNames(indicators, isMissingOrUnavailableIndicator, 2);
  const bias = buildLiquidityBiasSummary(data, readinessSummary, synthesisView);
  const limitedConfidence = readinessSummary.state !== 'ready'
    || synthesisView.state !== 'ready'
    || (data.score.confidence || 0) < 0.45;
  const topSignal = topConsumerSignalLabel(data, indicators);
  const observableCount = indicators.filter((indicator) => indicator.status !== 'unavailable').length;
  const scoringPaused = limitedConfidence
    || coverageSummary.missingOrUnavailableCount > 0
    || coverageSummary.observationOnlyCount > 0
    || data.score.regime === 'unavailable';
  const availabilityLabel = data.score.regime === 'unavailable'
    || coverageSummary.missingOrUnavailableCount >= Math.max(2, Math.ceil(indicators.length * 0.75))
    ? '暂不可用'
    : coverageSummary.missingOrUnavailableCount > 0 || limitedConfidence || coverageSummary.observationOnlyCount > 0
      ? '观察中'
      : '正常';
  const freshnessSummary = data.freshness.status === 'live'
    ? '已更新'
    : data.freshness.status === 'delayed'
      ? '数据更新中'
      : data.freshness.status === 'cached'
        ? '已使用最近一次可用数据'
        : data.freshness.status === 'stale' || data.freshness.status === 'fallback' || data.freshness.status === 'mock'
          ? '已使用最近一次可用数据'
          : '暂不可用';
  const heroTitle = availabilityLabel === '正常'
    ? bias.label
    : topSignal
      ? `先看${topSignal}`
      : '仍可观察的资金面线索';

  return {
    availabilityLabel,
    availabilityVariant: availabilityLabel === '正常' ? 'success' : availabilityLabel === '观察中' ? 'info' : 'neutral',
    regimeLabel: bias.label,
    heroTitle,
    observableCount,
    observableChipLabel: observableCount > 0 ? `${observableCount} 项可观察` : '等待线索恢复',
    freshnessChipLabel: consumerFreshnessLabel(data.freshness.status),
    freshnessVariant: chipVariantForFreshness(data.freshness.status),
    headline: availabilityLabel === '暂不可用'
      ? '数据不足'
      : availabilityLabel === '观察中'
        ? topSignal
          ? `当前方向仅供观察，先看${topSignal}等资金面线索。`
          : '当前方向仅供观察，先等待更多资金面线索恢复。'
        : topSignal
          ? `流动性格局${bias.label}，当前先看${topSignal}。`
          : `流动性格局${bias.label}，当前资金面线索可继续跟踪。`,
    availabilityDetail: availabilityLabel === '暂不可用'
      ? '当前关键资金面线索不足，页面会继续自动刷新。'
      : availabilityLabel === '观察中'
        ? unavailableModules.length > 0
          ? `数据覆盖有限，待补充指标：${unavailableModules.join('、')}。`
          : '数据覆盖有限，当前方向仅供观察。'
        : '当前主要资金面线索已返回，可继续观察。',
    scoringDetail: availabilityLabel === '暂不可用'
      ? '数据不足，等待刷新'
      : limitedConfidence
        ? '数据覆盖有限，当前方向仅供观察；待补充指标恢复后再判断。'
        : scoringPaused
          ? '数据覆盖有限，先等待更多资金面线索恢复。'
          : '当前流动性状态可继续参考。',
    freshnessSummary,
    freshnessDetail: `最近更新：${formatDateTime(data.freshness.latestAsOf) || '待确认'}`,
  };
}

const ConsumerLiquidityVisualEvidence: React.FC<{
  data: LiquidityMonitorResponse;
  coverageSummary: LiquidityCoverageReadinessSummary;
  readinessSummary: DecisionReadinessSummary;
  synthesisView: LiquidityImpulseSynthesisHeaderView;
  indicators: LiquidityMonitorIndicator[];
}> = ({ data, coverageSummary, readinessSummary, synthesisView, indicators }) => {
  const bias = buildLiquidityBiasSummary(data, readinessSummary, synthesisView);
  const coverageSegments = buildConsumerCoverageSegments(coverageSummary, indicators.length);
  const visualDrivers = buildConsumerVisualDrivers(data, indicators);
  const postureFillPct = data.score.regime === 'unavailable'
    ? 0
    : clampPercent(Math.max(data.score.value || 0, 0), 0, 100);
  const postureScoreLabel = data.score.regime === 'unavailable' || readinessSummary.state === 'unavailable'
    ? '--'
    : scoreLabel(data.score.value);

  return (
    <section data-testid="liquidity-visual-evidence" className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
      <div
        data-testid="liquidity-visual-posture"
        className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] p-3"
      >
        <div className="flex min-w-0 flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <p className="text-[11px] font-medium text-white/48">流动性格局</p>
            <p className={cn('mt-1 text-sm font-semibold', bias.toneClassName)}>{bias.label}</p>
            <p className="mt-1 text-[11px] leading-5 text-white/56">{bias.detail}</p>
          </div>
          <div className="flex min-w-0 flex-wrap gap-1.5 md:justify-end">
            <TerminalChip variant={bias.variant}>{REGIME_LABELS[data.score.regime]}</TerminalChip>
            <TerminalChip variant={readinessSummary.stateVariant}>{readinessSummary.stateLabel}</TerminalChip>
          </div>
        </div>
        <div className="mt-3 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
          <div className="flex items-end justify-between gap-3">
            <div>
              <p className="text-[10px] font-medium text-white/34">当前格局</p>
              <p className="mt-2 font-mono text-3xl font-semibold text-white/86">{postureScoreLabel}</p>
            </div>
            <p className="text-[11px] leading-5 text-white/48">
              {coverageSummary.directionLabel === '可参考' ? '当前格局可继续跟踪' : '当前格局先保持观察'}
            </p>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/[0.06]">
            <div
              className={cn(
                'h-full rounded-full transition-[width]',
                data.score.regime === 'stress' || data.score.regime === 'tight'
                  ? 'bg-gradient-to-r from-amber-300/85 to-amber-100/65'
                  : data.score.regime === 'supportive' || data.score.regime === 'abundant'
                    ? 'bg-gradient-to-r from-emerald-300/85 to-cyan-200/65'
                    : 'bg-gradient-to-r from-white/45 to-cyan-200/45',
              )}
              style={{ width: `${postureFillPct}%` }}
            />
          </div>
        </div>
      </div>

      <div
        data-testid="liquidity-visual-coverage"
        className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] p-3"
      >
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-medium text-white/48">资金面线索</p>
            <p className="mt-1 text-sm font-semibold text-white/84">
              {coverageSummary.scoreGradeCount}/{Math.max(indicators.length, 1)} 项线索可参考
            </p>
            <p className="mt-1 text-[11px] leading-5 text-white/56">
              观察线索 {coverageSummary.observationOnlyCount} 项；其余待补信息按需展开查看。
            </p>
          </div>
          <TerminalChip variant={coverageSummary.stateChipVariant}>{coverageSummary.directionLabel}</TerminalChip>
        </div>
        <div className="mt-3 flex h-2 overflow-hidden rounded-full bg-white/[0.06]">
          {coverageSegments.map((segment) => (
            <div
              key={segment.key}
              className={segment.barClassName}
              style={{ width: `${segment.widthPct}%` }}
            />
          ))}
        </div>
        <div className="mt-3 flex min-w-0 flex-wrap gap-1.5">
          {coverageSegments.map((segment) => (
            <TerminalChip key={segment.key} variant={segment.chipVariant}>
              {segment.label} {segment.count}
            </TerminalChip>
          ))}
        </div>
      </div>

      <div
        data-testid="liquidity-visual-drivers"
        className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] p-3"
      >
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-medium text-white/48">压力来源</p>
            <p className="mt-1 text-sm font-semibold text-white/84">美元、利率、波动等主要压力线索</p>
          </div>
          <TerminalChip variant="neutral">最多 3 项</TerminalChip>
        </div>
        <div className="mt-3 grid gap-2">
          {visualDrivers.map((driver) => (
            <div key={driver.key} className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-2.5">
              <div className="flex min-w-0 items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className={cn('truncate text-sm font-semibold', driver.toneClassName)}>{driver.label}</p>
                  <p className="mt-1 text-[11px] leading-5 text-white/52">{driver.detail}</p>
                </div>
                <span className="shrink-0 text-[11px] font-medium text-white/40">{driver.valueLabel || `${driver.emphasisPct}%`}</span>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                <div
                  className={cn('h-full rounded-full bg-gradient-to-r', driver.barClassName)}
                  style={{ width: `${driver.emphasisPct}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div
        data-testid="liquidity-visual-trend"
        className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] p-3"
      >
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-medium text-white/48">压力走势</p>
            <p className="mt-1 text-sm font-semibold text-white/84">连续走势暂未返回，当前保持观察</p>
            <p className="mt-1 text-[11px] leading-5 text-white/56">
              当前页面没有连续走势数据，先对照读数、线索状态与压力来源继续观察。
            </p>
          </div>
          <TerminalChip variant="neutral">未返回走势</TerminalChip>
        </div>
        <div className="mt-3 rounded-lg border border-dashed border-white/[0.08] bg-black/10 px-3 py-4">
          <div className="grid grid-cols-12 gap-1 opacity-60" aria-hidden="true">
            {Array.from({ length: 12 }).map((_, index) => (
              <div
                key={`trend-placeholder-${index}`}
                className="h-10 rounded-sm bg-white/[0.03]"
                style={{ marginTop: `${(index % 3) * 6}px` }}
              />
            ))}
          </div>
          <p className="mt-3 text-[11px] leading-5 text-white/48">
            需要连续时间序列后才展示走势；当前不推断上升、下降或拐点。
          </p>
        </div>
      </div>
    </section>
  );
};

const LiquiditySetupPath: React.FC<{ testId: string }> = ({ testId }) => (
  <div
    data-testid={testId}
    className="mt-4 rounded-lg border border-cyan-200/12 bg-cyan-300/[0.035] p-3"
  >
    <div className="flex min-w-0 flex-col gap-3 md:flex-row md:items-start md:justify-between">
      <div className="min-w-0">
        <p className="text-[11px] font-semibold text-cyan-100/82">补齐阻塞判断的证据</p>
        <p className="mt-1 max-w-3xl text-[11px] leading-5 text-white/52">
          优先核对覆盖是否完整、更新时间与缺失项；是否进入判断仍以现有证据门槛为准。
        </p>
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        <a
          className="inline-flex min-h-8 items-center rounded-md border border-white/[0.08] bg-white/[0.035] px-2.5 py-1 text-[11px] font-semibold text-white/72 transition-colors hover:border-cyan-200/25 hover:bg-white/[0.06] hover:text-white"
          href={buildProviderOpsSetupHref('liquidity_monitor')}
        >
          查看覆盖状态
        </a>
        <a
          className="inline-flex min-h-8 items-center rounded-md border border-white/[0.08] bg-white/[0.035] px-2.5 py-1 text-[11px] font-semibold text-white/72 transition-colors hover:border-cyan-200/25 hover:bg-white/[0.06] hover:text-white"
          href={buildDataSourcesSetupHref('liquidity_monitor')}
        >
          前往数据设置
        </a>
      </div>
    </div>
  </div>
);

const ConsumerDisclosure: React.FC<{
  testId: string;
  title: string;
  summary: string;
  className?: string;
  children: React.ReactNode;
}> = ({ testId, title, summary, className, children }) => {
  const [open, setOpen] = useState(false);

  return (
    <div
      data-testid={testId}
      data-terminal-primitive="disclosure"
      className={cn(
        'rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-2.5 py-2 text-xs transition-colors hover:border-[color:var(--wolfy-divider)]',
        className,
      )}
    >
      <div className="flex min-w-0 items-center justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate text-xs font-medium text-[color:var(--wolfy-text-secondary)]">{title}</h3>
          <p className="mt-0.5 truncate text-[11px] text-[color:var(--wolfy-text-muted)]">{summary}</p>
        </div>
        <button
          type="button"
          aria-expanded={open}
          aria-label={`${open ? '收起' : '展开'} ${title}`}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-transparent px-2 py-1 text-[11px] text-[color:var(--wolfy-text-secondary)] hover:text-[color:var(--wolfy-text-primary)]"
          onClick={() => setOpen((current) => !current)}
        >
          <span>{open ? '收起' : '展开'}</span>
        </button>
      </div>
      {open ? <div className="mt-2">{children}</div> : null}
    </div>
  );
};

const OfficialRiskSourceReadinessStrip: React.FC<{
  readiness?: OfficialRiskSourceReadiness | null;
}> = ({ readiness }) => {
  const view = buildOfficialRiskSourceReadinessView(readiness);

  return (
    <section
      data-testid="liquidity-official-risk-readiness"
      className="rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-2.5"
    >
      <div className="flex min-w-0 flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-white/48">官方风险源</p>
          <p className="mt-1 text-sm font-semibold text-white/84">{view.bundleLabel}</p>
        </div>
        <div className="flex min-w-0 flex-wrap gap-1.5 md:justify-end">
          <TerminalChip variant={view.bundleVariant}>{view.bundleLabel}</TerminalChip>
          {view.chips.map((chip) => (
            <TerminalChip key={chip.key} variant={chip.variant}>{chip.label}</TerminalChip>
          ))}
        </div>
      </div>
    </section>
  );
};

const CapitalFlowSignalPanel: React.FC<{
  signal?: LiquidityCapitalFlowSignal;
}> = ({ signal }) => {
  if (!signal) {
    return null;
  }

  const pressureRows = (signal.sourceAssetPressure || []).filter((item) => item.asset || item.pressure);
  const visiblePressureRows = pressureRows.slice(0, 2);
  const flagLabels = capitalFlowFlagLabels(signal);
  const hasExpandableDetails = pressureRows.length > 2 || (signal.contradictionSignals?.length || 0) > 0 || Boolean(signal.explanation);

  return (
    <div
      data-testid="liquidity-capital-flow-signal"
      className="mt-4 rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-3"
    >
      <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-white/48">资金面</p>
          <p className="mt-1 text-sm font-semibold text-white/84">{capitalFlowRegimeLabel(signal)}</p>
          <p className="mt-1 text-[11px] leading-5 text-white/56">
            作为流动性背景观察，不触发交易或主要方向判断。
          </p>
        </div>
        <div className="flex min-w-0 flex-wrap gap-1.5 lg:justify-end">
          <TerminalChip variant="info">仅观察</TerminalChip>
          <TerminalChip variant="neutral">资金面线索</TerminalChip>
          {flagLabels.map((label) => (
            <TerminalChip key={label} variant="caution">{label}</TerminalChip>
          ))}
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
          <p className="text-[11px] font-medium text-white/48">资金方向</p>
          <p className="mt-2 text-sm font-semibold text-white/82">{capitalFlowRegimeLabel(signal)}</p>
        </div>
        <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
          <p className="text-[11px] font-medium text-white/48">可能去向</p>
          <p className="mt-2 text-sm font-semibold text-white/82">{capitalFlowAssetLabel(signal.likelyDestination)}</p>
        </div>
        <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
          <p className="text-[11px] font-medium text-white/48">状态强弱</p>
          <p className="mt-2 text-sm font-semibold text-white/82">{capitalFlowConfidenceLabel(signal)}</p>
        </div>
      </div>

      {pressureRows.length || signal.contradictionSignals?.length ? (
        <div className="mt-3 flex min-w-0 flex-wrap gap-1.5">
          {pressureRows.length ? <TerminalChip variant="neutral">资产压力 {pressureRows.length} 项</TerminalChip> : null}
          {signal.contradictionSignals?.length ? <TerminalChip variant="caution">反向线索 {signal.contradictionSignals.length} 项</TerminalChip> : null}
        </div>
      ) : null}

      {visiblePressureRows.length ? (
        <div className="mt-3 grid gap-2">
          {visiblePressureRows.map((item) => (
            <div
              key={[
                item.asset || 'asset',
                item.pressure || 'unknown',
                item.freshness || 'unspecified',
                item.isFallback ? 'fallback' : '',
                item.isStale ? 'stale' : '',
                item.isPartial ? 'partial' : '',
              ].join('|')}
              className="flex min-w-0 flex-col gap-2 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-2.5 lg:flex-row lg:items-center lg:justify-between"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white/82">{capitalFlowAssetLabel(item.asset)}</p>
                <p className="mt-1 text-[11px] leading-5 text-white/56">资产压力观察</p>
              </div>
              <div className="flex min-w-0 flex-wrap gap-1.5 lg:justify-end">
                <TerminalChip variant="info">{capitalFlowPressureLabel(item.pressure)}</TerminalChip>
                {item.isPartial ? <TerminalChip variant="caution">部分</TerminalChip> : null}
                {item.isStale ? <TerminalChip variant="caution">最近可用</TerminalChip> : null}
                {item.isFallback ? <TerminalChip variant="caution">最近可用</TerminalChip> : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {hasExpandableDetails ? (
        <ConsumerDisclosure
          testId="liquidity-capital-flow-details"
          title="观察细节"
          summary="资产压力、反向线索与说明默认折叠"
          className="mt-3 bg-black/10"
        >
          <div className="grid gap-3 text-[11px] leading-5 text-white/58">
            {pressureRows.length ? (
              <div className="grid gap-2">
                <p className="text-[11px] font-medium text-white/48">资产压力</p>
                {pressureRows.map((item) => (
                  <div
                    key={[
                      item.asset || 'detail-asset',
                      item.pressure || 'unknown',
                      item.freshness || 'unspecified',
                      item.isFallback ? 'fallback' : '',
                      item.isStale ? 'stale' : '',
                      item.isPartial ? 'partial' : '',
                    ].join('|')}
                    className="flex min-w-0 flex-col gap-2 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-2 lg:flex-row lg:items-center lg:justify-between"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-white/82">{capitalFlowAssetLabel(item.asset)}</p>
                      <p className="mt-1 text-[11px] leading-5 text-white/56">{capitalFlowPressureLabel(item.pressure)}</p>
                    </div>
                    <div className="flex min-w-0 flex-wrap gap-1.5 lg:justify-end">
                      {item.isPartial ? <TerminalChip variant="caution">部分</TerminalChip> : null}
                      {item.isStale ? <TerminalChip variant="caution">最近可用</TerminalChip> : null}
                      {item.isFallback ? <TerminalChip variant="caution">最近可用</TerminalChip> : null}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
            {signal.contradictionSignals?.length ? (
              <div className="grid gap-2">
                <p className="text-[11px] font-medium text-white/48">反向线索</p>
                <div className="flex min-w-0 flex-wrap gap-1.5">
                  {signal.contradictionSignals.map((item) => (
                    <TerminalChip key={item} variant="neutral">{capitalFlowContradictionLabel(item)}</TerminalChip>
                  ))}
                </div>
              </div>
            ) : null}
            {signal.explanation ? (
              <div className="grid gap-1">
                <p className="text-[11px] font-medium text-white/48">说明</p>
                <p>{signal.explanation}</p>
              </div>
            ) : null}
          </div>
        </ConsumerDisclosure>
      ) : null}
    </div>
  );
};

const DecisionReadinessBand: React.FC<{
  summary: DecisionReadinessSummary;
  coverageSummary: LiquidityCoverageReadinessSummary;
  regimeGauge: LiquidityRegimeGaugeSummary;
  scoring: LiquidityIndicatorBucketSummary;
  observation: LiquidityIndicatorBucketSummary;
  missing: LiquidityIndicatorBucketSummary;
  nextWatch: string;
  data: LiquidityMonitorResponse;
  indicators: LiquidityMonitorIndicator[];
  synthesisView: LiquidityImpulseSynthesisHeaderView;
  showAdminDiagnostics: boolean;
}> = ({ summary, coverageSummary, regimeGauge, scoring, observation, missing, nextWatch, data, indicators, synthesisView, showAdminDiagnostics }) => {
  const bias = buildLiquidityBiasSummary(data, summary, synthesisView);
  const mainGapLine = buildLiquidityMainGapLine(summary, coverageSummary, missing);
  const evidenceColumns = [
    { key: 'scoring', label: '哪些证据在计分', count: scoring.count, detail: scoring.namesLine, tone: 'text-emerald-200' },
    { key: 'observation', label: '哪些只观察', count: observation.count, detail: observation.namesLine, tone: 'text-cyan-100' },
    { key: 'missing', label: '阻塞/缺失证据', count: missing.count, detail: missing.namesLine, tone: 'text-amber-200' },
  ];
  const consumerView = buildConsumerLiquidityStatusView(data, coverageSummary, summary, synthesisView, indicators);
  const consumerEvidenceRows = buildConsumerEvidenceRows(indicators);
  const consumerSummaryFacts = buildConsumerSummaryFacts(data, coverageSummary, indicators);
  const consumerGapSummary = buildConsumerGapSummary(missing, observation, consumerView);

  if (!showAdminDiagnostics) {
    return (
      <section
        data-testid="liquidity-decision-readiness"
        className="min-w-0 space-y-5 border-b border-white/[0.06] pb-5"
      >
        <div data-testid="liquidity-section-overview" className="min-w-0">
          <div className="mb-3 flex min-w-0 items-center gap-3">
            <div className="h-px flex-1 bg-white/[0.08]" aria-hidden="true" />
            <p className="shrink-0 text-[11px] font-semibold text-white/54">流动性格局</p>
            <div className="h-px flex-1 bg-white/[0.08]" aria-hidden="true" />
          </div>

          <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.18fr)_minmax(300px,0.82fr)]">
            <div className="min-w-0 rounded-xl border border-cyan-200/14 bg-[radial-gradient(circle_at_top_left,rgba(103,232,249,0.10),transparent_34%),rgba(255,255,255,0.035)] p-4 shadow-[0_18px_60px_rgba(3,7,18,0.22)] md:p-5">
              <div className="flex min-w-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold text-cyan-100/70">当前观察 · 流动性格局</p>
                  <h2 className="mt-2 text-[26px] font-semibold leading-tight text-white/94 md:text-3xl">
                    {consumerView.heroTitle}
                  </h2>
                  <p className="mt-3 max-w-3xl text-sm leading-6 text-white/68">{consumerView.headline}</p>
                </div>
                <div className="flex min-w-0 flex-wrap gap-2 lg:justify-end">
                  <TerminalChip variant={consumerView.availabilityVariant}>{consumerView.availabilityLabel}</TerminalChip>
                  <TerminalChip variant={consumerView.freshnessVariant}>{consumerView.freshnessChipLabel}</TerminalChip>
                  <TerminalChip variant="neutral">{consumerView.observableChipLabel}</TerminalChip>
                </div>
              </div>
            </div>

            <div
              data-testid="liquidity-summary-strip"
              className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-3 xl:grid-cols-1"
            >
              {consumerSummaryFacts.map((fact) => (
                <div key={fact.key} className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 p-3">
                  <p className="text-[11px] font-medium text-white/48">{fact.label}</p>
                  <p className="mt-2 break-words text-sm font-semibold text-white/84">{fact.value}</p>
                  {fact.detail ? (
                    <p className="mt-1 text-[11px] leading-5 text-white/56">{fact.detail}</p>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div data-testid="liquidity-section-metrics" className="min-w-0 rounded-xl border border-white/[0.055] bg-black/10 p-3 md:p-4">
          <div className="flex min-w-0 flex-col gap-2 border-b border-white/[0.06] pb-3 md:flex-row md:items-end md:justify-between">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold text-white/54">关键指标</p>
              <p className="mt-1 text-sm leading-6 text-white/62">先看已返回的资金面线索、更新时间和仍在变化的压力维度，再判断当前状态。</p>
            </div>
            <TerminalChip variant={coverageSummary.stateChipVariant}>{coverageSummary.directionLabel}</TerminalChip>
          </div>

          {consumerEvidenceRows.length ? (
            <div
              data-testid="liquidity-consumer-evidence"
              className="mt-4 rounded-lg border border-white/[0.06] bg-white/[0.025] p-3"
            >
              <div className="flex min-w-0 items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[11px] font-medium text-white/48">仍可观察的线索</p>
                  <p className="mt-1 text-[11px] leading-5 text-white/56">优先看已返回的资金面线索、最近更新时间，以及哪些维度还在持续更新。</p>
                </div>
              </div>
              <div className="mt-3 grid gap-2">
                {consumerEvidenceRows.map((row) => (
                  <div key={row.key} className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 p-3">
                    <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <p className="break-words text-sm font-semibold text-white/84">{row.label}</p>
                        <p className="mt-1 text-[11px] leading-5 text-white/60">{row.note}</p>
                      </div>
                      <div className="flex min-w-0 flex-wrap gap-1.5 lg:justify-end">
                        <TerminalChip variant={row.statusVariant}>{row.statusLabel}</TerminalChip>
                        <TerminalChip variant={row.scoreVariant}>{row.scoreLabel}</TerminalChip>
                      </div>
                    </div>
                    <p className="mt-2 text-[11px] leading-5 text-white/48">{row.detail}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <ConsumerLiquidityVisualEvidence
            data={data}
            coverageSummary={coverageSummary}
            readinessSummary={summary}
            synthesisView={synthesisView}
            indicators={indicators}
          />
        </div>

        <div data-testid="liquidity-section-observation" className="min-w-0">
          <div className="mb-3 flex min-w-0 items-center gap-3">
            <div className="h-px flex-1 bg-white/[0.08]" aria-hidden="true" />
            <p className="shrink-0 text-[11px] font-semibold text-white/54">资金面与说明</p>
            <div className="h-px flex-1 bg-white/[0.08]" aria-hidden="true" />
          </div>

          <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.12fr)_minmax(300px,0.88fr)]">
            <div className="min-w-0">
              <CapitalFlowSignalPanel signal={data.capitalFlowSignal} />

              <ConsumerDisclosure
                testId="liquidity-monitor-consumer-details"
                title="数据状态说明"
                summary="更新时间、观察边界与待补充指标默认折叠"
                className="mt-4 bg-black/10"
              >
                <div className="grid gap-2 text-[11px] leading-5 text-white/56">
                  <p>{consumerView.availabilityDetail}</p>
                  <p>{consumerView.scoringDetail}</p>
                  <p>{consumerView.freshnessDetail}</p>
                  {observation.count > 0 ? <p>仍在观察：{observation.namesLine}</p> : null}
                  {missing.count > 0 ? <p>待补充指标：{missing.namesLine}</p> : null}
                  <p>本页把流动性作为研究背景展示；当关键信号缺失、延迟或暂不可用时，状态会自动降级。</p>
                </div>
              </ConsumerDisclosure>
            </div>

            <aside
              data-testid="liquidity-context-rail"
              className="grid min-w-0 gap-3 self-start"
            >
              <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 p-3">
                <p className="text-[11px] font-medium text-white/48">当前边界</p>
                <p className="mt-2 text-sm leading-6 text-white/76">{consumerGapSummary}</p>
                <p className="mt-2 text-[11px] leading-5 text-white/48">
                  {missing.count > 0 ? `待补充指标：${missing.namesLine}` : '当前没有新增限制，继续观察后续变化。'}
                </p>
              </div>
              <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 p-3">
                <p className="text-[11px] font-medium text-white/48">下一步观察</p>
                <p className="mt-2 text-sm leading-6 text-white/76">{nextWatch}</p>
                <p className="mt-2 text-[11px] leading-5 text-white/48">
                  {consumerView.freshnessSummary}；页面会在后续刷新中继续更新状态。
                </p>
              </div>
            </aside>
          </div>
        </div>
      </section>
    );
  }

  return (
  <section
    data-testid="liquidity-decision-readiness"
    className="min-w-0 border-b border-white/[0.06] pb-4"
  >
    <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,1.15fr)]">
      <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 p-4">
        <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold text-white/45">流动性判断摘要</p>
            <h2 className="mt-1 text-lg font-semibold leading-7 text-white/92 md:text-xl">
              能否判断：{summary.stateLabel}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/60">{summary.conclusion}</p>
            <p
              className="mt-2 text-xs leading-5 text-white/52"
              data-testid="liquidity-monitor-coverage-summary"
            >
              {coverageSummary.summaryLine}
            </p>
          </div>
          <div className="flex min-w-0 flex-wrap gap-2 lg:justify-end">
            <TerminalChip variant={summary.stateVariant}>{summary.stateLabel}</TerminalChip>
            <TerminalChip variant={bias.variant}>{bias.label}</TerminalChip>
            <TerminalChip variant="neutral">{FRESHNESS_LABELS[data.freshness.status]}</TerminalChip>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] p-3">
            <p className="text-[11px] font-medium text-white/48">当前方向</p>
            <p className={cn('mt-2 text-sm font-semibold', bias.toneClassName)}>{bias.label}</p>
            <p className="mt-1 text-[11px] leading-5 text-white/56">{bias.detail}</p>
          </div>
          <div className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] p-3">
            <p className="text-[11px] font-medium text-white/48">主要缺口</p>
            <p className="mt-2 text-[11px] leading-5 text-white/60">{mainGapLine}</p>
          </div>
          <div className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] p-3">
            <p className="text-[11px] font-medium text-white/48">下一步观察</p>
            <p className="mt-2 text-[11px] leading-5 text-white/60">{nextWatch}</p>
          </div>
        </div>
      </div>

      <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 p-4">
        <div className="mb-3 min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-2.5">
          <p className="text-[11px] font-medium text-white/48">证据质量</p>
          <p className="mt-1 text-[11px] leading-5 text-white/62">{summary.qualityLabel}</p>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {evidenceColumns.map((column) => (
            <div key={column.key} className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] p-3">
              <p className="text-[11px] font-medium text-white/48">{column.label}</p>
              <p className={cn('mt-2 font-mono text-2xl font-semibold', column.tone)}>{column.count}</p>
              <p className="mt-2 text-[11px] leading-5 text-white/58">{column.detail}</p>
            </div>
          ))}
        </div>

        <section data-testid="liquidity-regime-gauge" className="mt-3 rounded-lg border border-white/[0.06] bg-white/[0.025] p-3">
          <div className="flex min-w-0 flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <p className="text-[11px] font-medium text-white/48">流动性刻度</p>
              <p className="mt-1 text-sm font-semibold text-white/84">{regimeGauge.stateLabel}</p>
            </div>
            <div className="flex min-w-0 flex-wrap gap-1.5 md:justify-end">
              <TerminalChip variant={regimeGauge.stateVariant}>{regimeGauge.degreeLabel}</TerminalChip>
              <TerminalChip variant="neutral">{regimeGauge.trendLabel}</TerminalChip>
              <TerminalChip variant="info">{regimeGauge.usableEvidenceLabel}</TerminalChip>
              <TerminalChip variant="caution">{regimeGauge.blockedEvidenceLabel}</TerminalChip>
            </div>
          </div>
          <div className="mt-3 flex min-w-0 flex-wrap gap-1.5">
            {regimeGauge.implicationLines.map((line) => (
              <TerminalChip key={line} variant={regimeGauge.stateVariant}>{line}</TerminalChip>
            ))}
          </div>
        </section>
      </div>
    </div>

    <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-2">
      <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 p-3">
        <p className="text-[11px] font-medium text-white/48">阻塞项</p>
        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
          {summary.blockers.map((item) => (
            <TerminalChip key={item} variant={summary.state === 'ready' ? 'neutral' : 'caution'}>{item}</TerminalChip>
          ))}
        </div>
      </div>
      <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 p-3">
        <p className="text-[11px] font-medium text-white/48">提升证据</p>
        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
          {summary.nextEvidence.map((item) => (
            <TerminalChip key={item} variant="info">{item}</TerminalChip>
          ))}
        </div>
      </div>
    </div>
    {summary.state !== 'ready' ? (
      <LiquiditySetupPath testId="liquidity-setup-path" />
    ) : null}
  </section>
  );
};

const LiquidityGuidancePanel: React.FC<{
  coverageSummary: LiquidityCoverageReadinessSummary;
  synthesisView: LiquidityImpulseSynthesisHeaderView;
  regimeGauge: LiquidityRegimeGaugeSummary;
  readinessSummary: DecisionReadinessSummary;
  indicators: LiquidityMonitorIndicator[];
  data: LiquidityMonitorResponse;
  selectedIndicator: LiquidityMonitorIndicator | null;
  officialMacroDiagnostics: ReturnType<typeof buildOfficialMacroAuthorityDiagnosticsView>;
  onSelectIndicator: (key: string) => void;
  showAdminDiagnostics: boolean;
}> = ({ coverageSummary, synthesisView, regimeGauge, readinessSummary, indicators, data, selectedIndicator, officialMacroDiagnostics, onSelectIndicator, showAdminDiagnostics }) => {
  const scoring = summarizeIndicatorBucket(
    indicators,
    (indicator) => indicator.coverageDiagnostics?.scoreContributionAllowed === true || indicator.includedInScore,
    '暂无评分级证据',
  );
  const observation = summarizeIndicatorBucket(
    indicators,
    isObservationOnlyIndicator,
    '暂无仅观察证据',
  );
  const missing = summarizeIndicatorBucket(
    indicators,
    isMissingOrUnavailableIndicator,
    '暂无显式缺口',
  );
  const nextWatch = buildLiquidityNextWatch(coverageSummary, indicators);

  return (
    <TerminalPanel data-testid="liquidity-monitor-guidance-panel" className="relative overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-300/0 via-cyan-200/40 to-sky-300/0" aria-hidden="true" />
      <DecisionReadinessBand
        summary={readinessSummary}
        coverageSummary={coverageSummary}
        regimeGauge={regimeGauge}
        scoring={scoring}
        observation={observation}
        missing={missing}
        nextWatch={nextWatch}
        data={data}
        indicators={indicators}
        synthesisView={synthesisView}
        showAdminDiagnostics={showAdminDiagnostics}
      />

      {showAdminDiagnostics ? (
        <TerminalDisclosure
          data-testid="liquidity-monitor-admin-details"
          title="技术细节"
          summary="流动性脉冲、完整指标矩阵、来源覆盖与运行边界默认折叠"
          className="mt-4 bg-black/10"
        >
          <div className="grid gap-4">
            <LiquidityImpulseSynthesisHeader view={synthesisView} />

            <TerminalPanel>
              <TerminalSectionHeader
                eyebrow="环境刻度"
                title="流动性环境分数"
                action={<TerminalChip variant={chipVariantForStatus(data.score.regime === 'unavailable' ? 'unavailable' : 'live')}>{REGIME_LABELS[data.score.regime]}</TerminalChip>}
              />
              <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-white/[0.04] bg-black/20 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[10px] uppercase tracking-widest text-white/35">分数</p>
                      <p className={cn('mt-2 font-mono text-5xl tracking-tight', REGIME_TONE[data.score.regime])}>{scoreLabel(data.score.value)}</p>
                      <p className="mt-2 text-sm text-white/48">{REGIME_LABELS[data.score.regime]}</p>
                    </div>
                    <Gauge className="size-8 text-white/28" aria-hidden="true" />
                  </div>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <TerminalMetric label="置信度" value={confidenceLabel(data.score.confidence)} valueClassName="text-2xl" />
                  <TerminalMetric label="最弱时效" value={FRESHNESS_LABELS[data.freshness.weakestIndicatorFreshness]} valueClassName="text-lg font-sans" />
                  <TerminalMetric label="输入覆盖" value={liquidityCoverageInputLabel(data)} valueClassName="text-lg font-sans" />
                  <TerminalMetric label="计分指标" value={data.score.includedIndicatorCount} valueClassName="text-2xl" />
                  <TerminalMetric label="权重预算" value={`${data.score.includedIndicatorWeight} / ${data.score.possibleIndicatorWeight}`} valueClassName="text-lg font-sans" />
                </div>
              </div>
            </TerminalPanel>

            <div data-testid="liquidity-indicator-mobile-list" className="grid gap-2 md:hidden">
              {indicators.map((indicator) => {
                const active = indicator.key === selectedIndicator?.key;
                return (
                  <button
                    key={indicator.key}
                    type="button"
                    data-testid={`liquidity-indicator-mobile-card-${indicator.key}`}
                    className={cn(
                      'min-w-0 rounded-lg border border-white/[0.06] bg-black/10 p-3 text-left transition-colors',
                      active ? 'border-cyan-200/22 bg-cyan-200/[0.055]' : 'hover:border-white/12 hover:bg-white/[0.03]',
                    )}
                    onClick={() => onSelectIndicator(indicator.key)}
                  >
                    <div className="flex min-w-0 items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-white/82">{displayLabel(indicator)}</p>
                        <p className="mt-1 text-sm leading-6 text-white/56">{indicator.summary || '—'}</p>
                      </div>
                      <span className="shrink-0 font-mono text-sm text-white/70">{contributionLabel(indicator)}</span>
                    </div>
                    <div className="mt-3 flex min-w-0 flex-wrap gap-1.5">
                      <TerminalChip variant={chipVariantForStatus(indicator.status)}>
                        {statusLabel(indicator.status)}
                      </TerminalChip>
                      <TerminalChip variant={chipVariantForFreshness(indicator.freshness)}>
                        {FRESHNESS_LABELS[indicator.freshness]}
                      </TerminalChip>
                    </div>
                    {isUsBreadthIndicator(indicator) ? (
                      <div className="mt-3">
                        <LiquidityBreadthTruthStrip
                          indicator={indicator}
                          testId="liquidity-breadth-truth-strip-mobile"
                        />
                      </div>
                    ) : null}
                  </button>
                );
              })}
            </div>

            <TerminalDenseTable data-testid="liquidity-indicator-table-shell" className="hidden md:block">
              <table className="w-full min-w-[760px] border-collapse text-left">
              <thead className="border-b border-white/5 text-[10px] uppercase tracking-widest text-white/35">
                <tr>
                  <th className="px-3 py-2">指标</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2">时效</th>
                  <th className="px-3 py-2">贡献</th>
                  <th className="px-3 py-2">说明</th>
                </tr>
              </thead>
              <tbody>
                {indicators.map((indicator) => {
                  const active = indicator.key === selectedIndicator?.key;
                  return (
                    <tr
                      key={indicator.key}
                      className={cn(
                        'cursor-pointer border-b border-white/[0.04] align-top transition-colors hover:bg-white/[0.02]',
                        active ? 'bg-white/[0.03]' : '',
                      )}
                      onClick={() => onSelectIndicator(indicator.key)}
                    >
                      <td className="px-3 py-2.5 text-sm text-white/80">{displayLabel(indicator)}</td>
                      <td className="px-3 py-2.5">
                        <TerminalChip variant={chipVariantForStatus(indicator.status)}>
                          {statusLabel(indicator.status)}
                        </TerminalChip>
                      </td>
                      <td className="px-3 py-2.5">
                        <TerminalChip variant={chipVariantForFreshness(indicator.freshness)}>
                          {FRESHNESS_LABELS[indicator.freshness]}
                        </TerminalChip>
                      </td>
                      <td className="px-3 py-2.5 font-mono text-white/72">{contributionLabel(indicator)}</td>
                      <td className="px-3 py-2.5 text-xs leading-5 text-white/48">
                        <div className="space-y-2">
                          <p>{indicator.summary || '—'}</p>
                          {isUsBreadthIndicator(indicator) ? (
                            <LiquidityBreadthTruthStrip
                              indicator={indicator}
                              testId="liquidity-breadth-truth-strip-row"
                            />
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              </table>
            </TerminalDenseTable>

            <OfficialMacroAuthorityDiagnostics
              testId="liquidity-monitor-official-macro-diagnostics"
              title="来源覆盖诊断"
              view={officialMacroDiagnostics}
            />

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <TerminalPanel>
                <TerminalSectionHeader eyebrow="选中指标" title="指标细节" action={<Waves className="size-4 text-white/28" aria-hidden="true" />} />
                {selectedIndicator ? (
                  <div className="mt-4 grid grid-cols-1 gap-3">
                    <TerminalMetric label="当前指标" value={displayLabel(selectedIndicator)} valueClassName="text-sm font-sans leading-6" />
                    <TerminalMetric label="状态" value={statusLabel(selectedIndicator.status)} valueClassName="text-lg font-sans" />
                    <TerminalMetric label="评分贡献" value={contributionLabel(selectedIndicator)} valueClassName="text-lg font-sans" />
                    <TerminalMetric label="更新时间" value={formatDateTime(selectedIndicator.updatedAt) || '待确认'} valueClassName="text-sm font-sans" />
                    <TerminalMetric label="备注" value={detailReason(selectedIndicator)} valueClassName="text-sm font-sans leading-6" />
                    {isUsBreadthIndicator(selectedIndicator) ? (
                      <LiquidityBreadthTruthStrip
                        indicator={selectedIndicator}
                        testId="liquidity-breadth-truth-strip-detail"
                      />
                    ) : null}
                  </div>
                ) : (
                  <p className="mt-4 text-sm text-white/45">当前没有可展示的指标。</p>
                )}
              </TerminalPanel>

              <TerminalPanel data-testid="liquidity-monitor-source-disclosure">
                <TerminalSectionHeader eyebrow="运行边界" title="来源与约束" action={<Activity className="size-4 text-white/28" aria-hidden="true" />} />
                <div className="mt-4 grid grid-cols-1 gap-3">
                  <TerminalMetric label="外部调用" value={data.sourceMetadata.externalProviderCalls ? '已发生' : '未发生'} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="运行顺序" value={data.sourceMetadata.providerRuntimeChanged ? '已变更' : '未变更'} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="缓存写入" value={data.sourceMetadata.marketCacheMutation ? '已发生' : '未发生'} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="最弱时效" value={FRESHNESS_LABELS[data.freshness.weakestIndicatorFreshness]} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="最新时间" value={formatDateTime(data.freshness.latestAsOf) || '待确认'} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="当前判断" value={data.score.regime === 'unavailable' ? '数据不足' : '仅供研究观察'} valueClassName="text-sm font-sans leading-6" />
                </div>
                <p className="mt-4 text-sm leading-6 text-white/52">
                  只读快照，不触发扫描、回测或组合动作，也不把 fallback 包装成实时结论。
                </p>
              </TerminalPanel>
            </div>
          </div>
        </TerminalDisclosure>
      ) : null}
    </TerminalPanel>
  );
};

const LiquidityMonitorPage: React.FC = () => {
  const { isAdminMode, canReadProviders } = useProductSurface();
  const [data, setData] = useState<LiquidityMonitorResponse | null>(null);
  const [officialRiskSourceReadiness, setOfficialRiskSourceReadiness] = useState<OfficialRiskSourceReadiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const payload = await liquidityMonitorApi.getLiquidityMonitor();
        if (cancelled) return;
        setData(payload);
        const preferred = payload.indicators.find((item) => item.includedInScore) || payload.indicators[0] || null;
        setSelectedKey(preferred?.key || null);
      } catch (loadError) {
        if (cancelled) return;
        setError(getParsedApiError(loadError));
      }
      if (!cancelled) {
        setLoading(false);
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadSourceReadiness() {
      try {
        const payload = await marketApi.getDataReadiness();
        if (!cancelled) {
          setOfficialRiskSourceReadiness(payload?.officialRiskSourceReadiness || null);
        }
      } catch {
        if (!cancelled) {
          setOfficialRiskSourceReadiness(null);
        }
      }
    }

    void loadSourceReadiness();

    return () => {
      cancelled = true;
    };
  }, []);

  const indicators = data?.indicators || [];
  const selectedIndicator = indicators.find((item) => item.key === selectedKey) || indicators[0] || null;
  const synthesisView = buildLiquidityImpulseSynthesisView(data?.liquidityImpulseSynthesis);
  const coverageSummary = buildCoverageReadinessSummary(data, synthesisView);
  const readinessSummary = data ? buildLiquidityDecisionReadiness(data, coverageSummary, synthesisView, indicators) : null;
  const regimeGauge = data ? buildLiquidityRegimeGaugeSummary({
    data,
    synthesisPromotable: synthesisView.state === 'ready',
    usableEvidenceCount: coverageSummary.scoreGradeCount,
    missingOrBlockedCount: coverageSummary.missingOrUnavailableCount,
  }) : null;
  const officialMacroDiagnostics = buildOfficialMacroAuthorityDiagnosticsView(
    indicators.flatMap((indicator) => (
      indicator.evidence?.inputs?.map((input) => ({
        key: `${indicator.key}:${input.officialSeriesId || input.key}`,
        label: input.label,
        sourceLabel: input.sourceLabel,
        sourceTier: input.sourceTier,
        trustLevel: input.trustLevel,
        freshness: input.freshness,
        asOf: input.asOf,
        isFallback: input.isFallback,
        isUnavailable: input.isUnavailable,
        isPartial: input.isPartial,
        observationOnly: input.observationOnly,
        sourceAuthorityAllowed: input.sourceAuthorityAllowed,
        scoreContributionAllowed: input.scoreContributionAllowed,
        sourceAuthorityReason: input.sourceAuthorityReason,
        sourceAuthorityRouteRejected: input.sourceAuthorityRouteRejected,
        routeRejectedReasonCodes: input.routeRejectedReasonCodes,
        officialSeriesId: input.officialSeriesId,
        officialObservationDate: input.officialObservationDate,
        officialAsOf: input.officialAsOf,
      })) || []
    )),
  );

  return (
    <ConsumerWorkspaceScope className="min-h-0 flex-1">
    <ConsumerWorkspacePageShell className="flex min-h-0 flex-1">
      <TerminalPageHeading
        eyebrow="流动性"
        title="流动性监测"
      />

      {error ? <ApiErrorAlert error={error} /> : null}

      {loading && !data ? (
        <TerminalPanel>
          <TerminalSectionHeader eyebrow="快照" title="读取中" />
          <div data-testid="liquidity-decision-readiness" className="mt-3 text-sm text-white/58">
            判断可用性：{decisionReadinessStateLabel('waiting')}
          </div>
        </TerminalPanel>
      ) : null}

      {data && regimeGauge && readinessSummary ? (
        <TerminalGrid>
          <div className="flex flex-col gap-4 xl:col-span-12">
            <OfficialRiskSourceReadinessStrip readiness={officialRiskSourceReadiness} />
            <LiquidityGuidancePanel
              coverageSummary={coverageSummary}
              synthesisView={synthesisView}
              regimeGauge={regimeGauge}
              readinessSummary={readinessSummary}
              indicators={indicators}
              data={data}
              selectedIndicator={selectedIndicator}
              officialMacroDiagnostics={officialMacroDiagnostics}
              onSelectIndicator={setSelectedKey}
              showAdminDiagnostics={isAdminMode && canReadProviders}
            />
          </div>
        </TerminalGrid>
      ) : null}
    </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
};

export default LiquidityMonitorPage;
