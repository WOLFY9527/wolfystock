import type React from 'react';
import { useEffect, useState } from 'react';
import { Activity, Gauge, Waves } from 'lucide-react';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import {
  liquidityMonitorApi,
  type LiquidityMonitorFreshness,
  type LiquidityMonitorIndicator,
  type LiquidityImpulseSynthesis,
  type LiquidityImpulseSynthesisEvidenceItem,
  type LiquidityMonitorRegime,
  type LiquidityMonitorResponse,
} from '../api/liquidityMonitor';
import { ApiErrorAlert } from '../components/common';
import {
  LiquidityImpulseSynthesisHeader,
  type LiquidityImpulseHeaderEvidenceView,
  type LiquidityImpulseSynthesisHeaderView,
} from '../components/liquidity-monitor/LiquidityImpulseSynthesisHeader';
import { ProductSetupPath } from '../components/market-intelligence/ProductSetupPath';
import {
  TerminalChip,
  TerminalDenseTable,
  TerminalDisclosure,
  TerminalGrid,
  TerminalMetric,
  TerminalNotice,
  TerminalPageHeading,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal';
import { WideWorkspacePageShell } from '../components/layout/WideWorkspaceShell';
import { OfficialMacroAuthorityDiagnostics } from '../components/common/OfficialMacroAuthorityDiagnostics';
import { buildOfficialMacroAuthorityDiagnosticsView } from '../components/common/officialMacroAuthorityDiagnosticsData';
import { formatDateTime, formatPercent, formatSignedNumber } from '../utils/format';
import { cn } from '../utils/cn';
import {
  MARKET_DECISION_NOT_READY_NOTICE,
  buildLiquidityRegimeGaugeSummary,
  decisionReadinessStateLabel,
  decisionReadinessVariant,
  sanitizeMarketGuidanceCopy,
  type DecisionReadinessState,
  type DecisionReadinessSummary,
  type LiquidityRegimeGaugeSummary,
} from '../utils/marketIntelligenceGuidance';

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
  crypto_funding: 'Crypto 资金费率',
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

const PILLAR_LABELS: Record<string, string> = {
  rates_pressure: '利率压力',
  dollar_pressure: '美元压力',
  volatility_stress: '波动率压力',
  crypto_liquidity_beta: 'Crypto Beta',
  risk_asset_demand: '风险资产需求',
  funding_stress: '资金费率压力',
  equity_flow_proxy: '权益流向代理',
  breadth_confirmation: '市场宽度确认',
  china_liquidity_context: '中国流动性环境',
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
  partial_coverage: '覆盖不完整',
  observation_only: '仅观察态',
  proxy_only_missing_real_source: '缺少真实数据源',
  proxy_context_only: '代理上下文仅观察',
  source_authority_router_rejected: '来源权限未通过',
  provider_forbidden_for_use_case: '当前用例禁止该来源',
  provider_observation_only: '提供方仅允许观察',
  provider_unavailable: '数据源不可用',
  trust_gate_blocked: '信任门禁阻断',
  provider_absent: '所需提供方未配置',
  unavailable_source: '来源不可用',
  indicator_unavailable: '指标不可用',
};

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

function titleCaseFromSnake(value?: string | null): string {
  if (!value) return '待确认';
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function impulseCodeLabel(value?: string | null): string {
  if (!value) return '待确认';
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
  return PILLAR_LABELS[value] || titleCaseFromSnake(value);
}

function evidenceDirectionLabel(value?: string | null): string | null {
  if (!value) return null;
  return EVIDENCE_DIRECTION_LABELS[value] || titleCaseFromSnake(value);
}

function evidenceReasonLabel(value?: string | null): string | null {
  if (!value) return null;
  return EVIDENCE_REASON_LABELS[value] || titleCaseFromSnake(value);
}

function evidenceItemDisplayLabel(item: LiquidityImpulseSynthesisEvidenceItem): string {
  return item.label || pillarLabel(item.pillar) || titleCaseFromSnake(item.key);
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
    if (item.degradationReason) parts.push(titleCaseFromSnake(item.degradationReason));
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
      summary: '当前流动性监测载荷未返回 liquidityImpulseSynthesis，不推断扩张或收缩。',
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
    proxyOnlyDecision ? 'proxy-only' : '',
  ].filter(Boolean).join(' · ');
  const contradictionCount = Math.min(synthesis.counterEvidence.length, 3);
  const gapCount = Math.min(dataGapCount, 3);

  return {
    state: promotable ? 'ready' : 'insufficient',
    title: promotable
      ? impulseCodeLabel(synthesis.liquidityImpulse)
      : synthesis.liquidityImpulse === 'data_insufficient'
        ? '流动性方向数据不足'
        : '流动性方向待确认',
    summary: promotable
      ? (synthesis.narrativeBullets[0]
        || `主驱动 ${Math.min(synthesis.dominantDrivers.length, 3)} 项 · 反证 ${contradictionCount} 项 · 缺口 ${gapCount} 项`)
      : proxyOnlyDecision
        ? `后端返回“${synthesis.impulseLabel}”，但当前可计分证据为 proxy-only，前端不升级为真实扩张或收缩结论。`
        : synthesis.liquidityImpulse === 'data_insufficient'
          ? (synthesis.narrativeBullets[0] || '当前可用证据不足，只展示缺口与残余信号。')
          : `后端返回“${synthesis.impulseLabel}”，但当前置信度不足，只展示支持证据、反证与数据缺口。`,
    stateChipLabel: promotable
      ? '主结论'
      : synthesis.liquidityImpulse === 'data_insufficient'
        ? '数据不足'
        : proxyOnlyDecision
          ? 'Proxy-only'
          : '低置信度',
    stateChipVariant: promotable ? 'success' : 'caution',
    impulseLabel: synthesis.impulseLabel,
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

function isObservationOnlyIndicator(indicator: LiquidityMonitorIndicator): boolean {
  if (indicator.coverageDiagnostics?.observationOnly === true) {
    return true;
  }

  const inputs = indicator.evidence?.inputs || [];
  return inputs.length > 0
    && inputs.some((input) => input.observationOnly)
    && !inputs.some((input) => input.scoreContributionAllowed);
}

function isMissingOrUnavailableIndicator(indicator: LiquidityMonitorIndicator): boolean {
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
  return titleCaseFromSnake(reason);
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

  const topBlockingReasons = [...blockingReasons.entries()]
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
  return indicators
    .filter(predicate)
    .map((indicator) => displayLabel(indicator))
    .filter((label, index, array) => array.indexOf(label) === index)
    .slice(0, limit);
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

function buildLiquidityNextWatch(
  coverageSummary: LiquidityCoverageReadinessSummary,
  indicators: LiquidityMonitorIndicator[],
): string {
  const missing = topIndicatorNames(indicators, isMissingOrUnavailableIndicator, 2);
  const observation = topIndicatorNames(indicators, isObservationOnlyIndicator, 1);
  const parts = [
    missing.length ? `优先补齐 ${missing.join('、')}` : '',
    observation.length ? `继续观察 ${observation.join('、')}` : '',
    coverageSummary.directionLabel === '可参考' ? '确认新增反证是否进入可计分范围' : '',
  ].filter(Boolean);
  return parts.length ? parts.join('；') : '等待新的评分级证据进入可计分范围。';
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
  const proxyOnly = synthesisView.state !== 'ready' && /proxy/i.test(synthesisView.stateChipLabel);
  const blockers = [
    ...coverageSummary.blockingReasons,
    proxyOnly ? 'Proxy-only 证据不能升级方向' : '',
    synthesisView.state === 'missing' ? '流动性脉冲载荷缺失' : '',
    data.score.regime === 'unavailable' ? '流动性分数不可用' : '',
    data.freshness.weakestIndicatorFreshness === 'fallback' || data.freshness.weakestIndicatorFreshness === 'stale'
      ? '存在 fallback/stale 负担'
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

const DecisionReadinessBand: React.FC<{
  summary: DecisionReadinessSummary;
}> = ({ summary }) => (
  <section
    data-testid="liquidity-decision-readiness"
    className="min-w-0 border-b border-white/[0.06] pb-4"
  >
    <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0">
        <p className="text-[11px] font-semibold text-white/45">判断可用性</p>
        <h2 className="mt-1 text-base font-semibold leading-6 text-white/92 md:text-lg">{summary.stateLabel}</h2>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-white/58">{summary.conclusion}</p>
      </div>
      <div className="flex min-w-0 flex-wrap gap-2 lg:justify-end">
        <TerminalChip variant={summary.stateVariant}>{summary.stateLabel}</TerminalChip>
        <TerminalChip variant="neutral">{summary.qualityLabel}</TerminalChip>
      </div>
    </div>
    <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
      <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
        <p className="text-[11px] font-medium text-white/48">阻塞项</p>
        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
          {summary.blockers.map((item) => (
            <TerminalChip key={item} variant={summary.state === 'ready' ? 'neutral' : 'caution'}>{item}</TerminalChip>
          ))}
        </div>
      </div>
      <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
        <p className="text-[11px] font-medium text-white/48">提升证据</p>
        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
          {summary.nextEvidence.map((item) => (
            <TerminalChip key={item} variant="info">{item}</TerminalChip>
          ))}
        </div>
      </div>
    </div>
    {summary.state !== 'ready' ? (
      <ProductSetupPath surface="liquidity_monitor" testId="liquidity-setup-path" />
    ) : null}
  </section>
);

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
}> = ({ coverageSummary, synthesisView, regimeGauge, readinessSummary, indicators, data, selectedIndicator, officialMacroDiagnostics, onSelectIndicator }) => {
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
      <DecisionReadinessBand summary={readinessSummary} />
      <section data-testid="liquidity-regime-gauge" className="min-w-0 border-b border-white/[0.06] py-4">
        <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="text-[10px] font-medium tracking-[0.24em] text-white/38">{regimeGauge.title}</p>
            <h2 className="mt-2 text-base font-semibold leading-6 text-white/90 md:text-lg">{regimeGauge.stateLabel}</h2>
          </div>
          <div className="flex min-w-0 flex-wrap gap-2 lg:justify-end">
            <TerminalChip variant={regimeGauge.stateVariant}>{regimeGauge.degreeLabel}</TerminalChip>
            <TerminalChip variant="neutral">{regimeGauge.trendLabel}</TerminalChip>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-[1.15fr_1fr_1fr]">
          <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
            <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
              <div
                className={cn(
                  'h-full rounded-full',
                  regimeGauge.stateVariant === 'success'
                    ? 'bg-emerald-300/70'
                    : regimeGauge.stateVariant === 'danger'
                      ? 'bg-rose-300/70'
                      : regimeGauge.stateVariant === 'caution'
                        ? 'bg-amber-300/70'
                        : 'bg-cyan-200/70',
                )}
                style={{ width: `${Math.max(0, Math.min(100, Number(regimeGauge.degreeLabel.match(/\d+/)?.[0] || 0)))}%` }}
                aria-hidden="true"
              />
            </div>
            <p className="mt-2 text-[11px] leading-5 text-white/58">{regimeGauge.degreeLabel}</p>
          </div>
          <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
            <p className="text-[11px] font-medium text-white/48">证据覆盖</p>
            <p className="mt-2 text-sm font-semibold text-white/84">{regimeGauge.usableEvidenceLabel}</p>
            <p className="mt-1 text-sm font-semibold text-amber-200">{regimeGauge.blockedEvidenceLabel}</p>
          </div>
          <div className="min-w-0 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
            <p className="text-[11px] font-medium text-white/48">使用边界</p>
            <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
              {regimeGauge.implicationLines.map((line) => (
                <TerminalChip key={line} variant={regimeGauge.stateVariant}>{line}</TerminalChip>
              ))}
            </div>
          </div>
        </div>
      </section>
      <TerminalSectionHeader
        eyebrow="流动性判断摘要"
        title={`流动性方向：${coverageSummary.directionLabel}`}
        action={<TerminalChip variant={coverageSummary.stateChipVariant}>{coverageSummary.stateLabel}</TerminalChip>}
      />
      <p className="mt-3 text-sm font-medium text-white/84">{coverageSummary.directionExplanation}</p>
      <p
        className="mt-1 text-xs leading-5 text-white/52"
        data-testid="liquidity-monitor-coverage-summary"
      >
        {coverageSummary.summaryLine}
      </p>

      <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-3">
        {[
          { key: 'scoring', label: '可计分证据', summary: scoring, tone: 'text-emerald-200' },
          { key: 'observation', label: '观察证据', summary: observation, tone: 'text-cyan-100' },
          { key: 'missing', label: '缺失证据', summary: missing, tone: 'text-amber-200' },
        ].map((column) => (
          <div key={column.key} className="rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
            <p className="text-[11px] font-medium text-white/48">{column.label}</p>
            <p className={cn('mt-2 font-mono text-2xl font-semibold', column.tone)}>{column.summary.count}</p>
            <p className="mt-2 text-[11px] leading-5 text-white/58">{column.summary.namesLine}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
        <p className="text-[11px] font-medium text-white/48">下一步观察</p>
        <p className="mt-2 text-[11px] leading-5 text-white/60">{nextWatch}</p>
      </div>

      <TerminalDisclosure
        data-testid="liquidity-monitor-indicator-disclosure"
        title="技术细节 / Details"
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
                  <Gauge className="h-8 w-8 text-white/28" aria-hidden="true" />
                </div>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <TerminalMetric label="置信度" value={confidenceLabel(data.score.confidence)} valueClassName="text-2xl" />
                <TerminalMetric label="最弱时效" value={FRESHNESS_LABELS[data.freshness.weakestIndicatorFreshness]} valueClassName="text-lg font-sans" />
                <TerminalMetric label="计分指标" value={data.score.includedIndicatorCount} valueClassName="text-2xl" />
                <TerminalMetric label="计分权重" value={`${data.score.includedIndicatorWeight} / ${data.score.possibleIndicatorWeight}`} valueClassName="text-lg font-sans" />
              </div>
            </div>
          </TerminalPanel>

          <TerminalDenseTable>
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
                      <td className="px-3 py-2.5 text-xs leading-5 text-white/48">{indicator.summary || '—'}</td>
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
              <TerminalSectionHeader eyebrow="选中指标" title="指标细节" action={<Waves className="h-4 w-4 text-white/28" aria-hidden="true" />} />
              {selectedIndicator ? (
                <div className="mt-4 grid grid-cols-1 gap-3">
                  <TerminalMetric label="当前指标" value={displayLabel(selectedIndicator)} valueClassName="text-sm font-sans leading-6" />
                  <TerminalMetric label="状态" value={statusLabel(selectedIndicator.status)} valueClassName="text-lg font-sans" />
                  <TerminalMetric label="评分贡献" value={contributionLabel(selectedIndicator)} valueClassName="text-lg font-sans" />
                  <TerminalMetric label="更新时间" value={formatDateTime(selectedIndicator.updatedAt) || '待确认'} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="备注" value={detailReason(selectedIndicator)} valueClassName="text-sm font-sans leading-6" />
                </div>
              ) : (
                <p className="mt-4 text-sm text-white/45">当前没有可展示的指标。</p>
              )}
            </TerminalPanel>

            <TerminalPanel data-testid="liquidity-monitor-source-disclosure">
              <TerminalSectionHeader eyebrow="运行边界" title="来源与约束" action={<Activity className="h-4 w-4 text-white/28" aria-hidden="true" />} />
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
    </TerminalPanel>
  );
};

const LiquidityMonitorPage: React.FC = () => {
  const [data, setData] = useState<LiquidityMonitorResponse | null>(null);
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
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();

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
    <WideWorkspacePageShell className="flex min-h-0 flex-1 py-5 md:py-6">
      <TerminalPageHeading
        eyebrow="流动性"
        title="流动性监测"
        action={
          <TerminalChip variant={data ? chipVariantForFreshness(data.freshness.status) : 'neutral'}>
            {data ? FRESHNESS_LABELS[data.freshness.status] : '加载中'}
          </TerminalChip>
        }
      />

      <TerminalNotice variant="info">
        {sanitizeMarketGuidanceCopy(data?.advisoryDisclosure, '仅用于观察市场流动性环境，非投资建议，不触发扫描、回测或组合动作。')}
      </TerminalNotice>

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
            />
          </div>
        </TerminalGrid>
      ) : null}
    </WideWorkspacePageShell>
  );
};

export default LiquidityMonitorPage;
