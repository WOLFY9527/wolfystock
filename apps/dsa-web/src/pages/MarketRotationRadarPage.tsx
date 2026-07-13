import type React from 'react';
import { useEffect, useReducer, useRef, useState } from 'react';
import { Gauge, RefreshCcw, Search, SlidersHorizontal } from 'lucide-react';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import {
  ConsoleContextRail,
  DataWorkbenchFrame,
  DenseRows,
  WolfyCommandBar,
} from '../components/linear/LinearPrimitives';
import { DataFreshnessBadge } from '../components/market-overview/marketOverviewPrimitives';
import {
  TerminalButton,
  TerminalChip,
  TerminalEmptyState,
  TerminalGrid,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPageHeading,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal/TerminalPrimitives';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import { createParsedApiError, getParsedApiError, type ParsedApiError } from '../api/error';
import {
  buildAlpacaQuoteAuthorityReadinessView,
  buildMarketRotationEvidenceBoundaryView,
  marketRotationApi,
  type MarketRotationEvidenceQuality,
  type MarketRotationFamilyRollupItem,
  type MarketRotationRadarResponse,
  type MarketRotationSignalType,
  type MarketRotationStage,
  type MarketRotationSummaryItem,
  type MarketRotationTheme,
  type MarketRotationThemeCorrelationBreadthSnapshot,
} from '../api/marketRotation';
import {
  compareNullableAsc,
  compareNullableDesc,
  formatConfidenceValue as formatRotationConfidenceValue,
  formatRelativeStrengthValue as formatRotationRelativeStrengthValue,
  formatRotationScore,
  hasPositiveKnownMetric,
  matrixGeometryPosition,
  parseRotationMetric,
  scoreBarGeometryWidth,
  sortThemesByEvidenceDesc,
} from '../components/market-rotation/rotationEvidenceSemantics';
import { cn } from '../utils/cn';
import { decisionReadinessVariant, sanitizeMarketGuidanceCopy, type DecisionReadinessState, type DecisionReadinessSummary } from '../utils/marketIntelligenceGuidance';

const TOP_THEME_LIMIT = 10;
const DEFAULT_MARKET = 'US';
const ROTATION_RADAR_LOADING_FALLBACK_MS = 5000;
const ROTATION_RADAR_ROUTE_TIMEOUT_MS = 12000;
const MARKET_OPTIONS = [
  { id: 'US', label: '美股' },
  { id: 'CN', label: 'A股' },
  { id: 'HK', label: '港股' },
  { id: 'CRYPTO', label: '加密' },
] as const;

const STAGE_LABELS: Record<MarketRotationStage, string> = {
  early_watch: '早期观察',
  confirmed_rotation: '确认轮动',
  extended_watch: '延展观察',
  cooling_watch: '降温观察',
  weak_or_no_signal: '信号较弱',
};

const REAL_FLOW_EVIDENCE_TYPES = new Set(['real_flow', 'mixed_real_and_proxy']);
const DATA_GAP_LABELS: Record<string, string> = {
  true_flow_data_missing: '信号待确认',
  flow_methodology_missing: '信号待确认',
  source_authority_rejected: '信号待确认',
  stale_quote_window: '数据延迟',
  benchmark_proxy_missing: '走势分化',
  proxy_coverage_incomplete: '走势分化',
  taxonomy_only: '分类浏览',
  missing_required_windows: '信号待确认',
  no_headline_theme: '走势分化',
};
const THEME_FLOW_STATE_LABELS: Record<string, string> = {
  leading: '领涨观察',
  broadening: '扩散跟涨',
  rotating: '轮动切换',
  crowded: '拥挤观察',
  fading: '热度回落',
  mixed: '信号分化',
  insufficient_evidence: '数据不足',
};
const THEME_FLOW_REASON_LABELS: Record<string, string> = {
  fallback_source: '最近一次可用数据',
  stale_source: '数据延迟',
  partial_source: '走势分化',
  source_authority_missing: '信号待确认',
  conflicting_signal_inputs: '强弱与扩散信号分化',
};
const THEME_PARTICIPATION_LABELS: Record<string, string> = {
  broad_group: '广泛扩散',
  leader_concentrated: '少数龙头集中',
  mixed_or_partial: '分化观察',
  insufficient_evidence: '证据不足',
};
const THEME_LEADERSHIP_LABELS: Record<string, string> = {
  balanced: '分布均衡',
  moderate: '中度集中',
  concentrated: '龙头集中',
  unknown: '集中度待补齐',
};
const THEME_CORRELATION_LABELS: Record<string, string> = {
  aligned: '同步相关',
  mixed: '相关性分化',
  weak: '相关性偏弱',
  missing: '同步证据待补齐',
};
const THEME_BREADTH_LABELS: Record<string, string> = {
  broad: '广度扩散',
  mixed: '广度分化',
  thin: '广度偏窄',
  missing: '广度待补齐',
};
const SNAPSHOT_INPUT_LABELS: Record<string, string> = {
  fallback_source: '最近一次可用数据',
  stale_source: '数据延迟',
  partial_source: '部分样本待补齐',
  breadth_percent_up: '上涨广度待补齐',
  breadth_percent_outperforming_benchmark: '跑赢广度待补齐',
  correlation_same_direction_percent: '成员同步待补齐',
  correlation_above_vwap_percent: '均线同步待补齐',
  leadership_concentration_percent: '龙头集中度待补齐',
  market_runtime_evidence: '市场观察样本待补齐',
};
const SNAPSHOT_NEXT_STEP_LABELS: Record<string, string> = {
  'Watch whether broad participation persists across the next observation window.': '继续观察广泛参与能否延续到下一观察窗口。',
  'Compare top-member moves with the rest of the theme before drawing a group-level conclusion.': '先对比龙头成员与其余成员，再判断主题整体扩散。',
  'Collect member-level breadth and synchronization evidence before classifying participation.': '补齐成员广度与同步证据后，再分类参与状态。',
  'Refresh stale theme inputs before treating the snapshot as current.': '先等待数据更新，再把快照视为当前状态。',
  'Review whether breadth, synchronization, and leadership remain consistent in the next snapshot.': '下一次快照继续复核广度、同步与龙头分布是否一致。',
};
const ROTATION_ENGLISH_COPY_REPLACEMENTS: Array<[RegExp, string]> = [
  [/\bAI Applications?\b/g, 'AI 应用'],
  [/\bAI Observation Theme\b/g, 'AI 观察主题'],
  [/\bAI Proxy Candidate\b/g, 'AI 观察候选'],
  [/\bSemiconductor Real Flow\b/g, '半导体确认信号'],
  [/\bRobotics\b/g, '机器人'],
  [/\bTheme\b/g, '主题'],
  [/\bCluster\b/g, '主题簇'],
  [/\bObservation\b/g, '观察'],
  [/\bProxy Candidate\b/g, '观察候选'],
  [/\bReal Flow\b/g, '确认信号'],
];
const ROTATION_PAPER_PANEL_CLASS = 'rounded-xl border border-[color:var(--wolfy-divider)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-input)_84%,transparent)]';
const ROTATION_PAPER_SOFT_PANEL_CLASS = 'rounded-xl border border-[color:var(--wolfy-divider)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-input)_70%,transparent)]';
const ROTATION_PAPER_TEXT_PRIMARY_CLASS = 'text-[color:var(--wolfy-text-primary)]';
const ROTATION_PAPER_TEXT_SECONDARY_CLASS = 'text-[color:var(--wolfy-text-secondary)]';
const ROTATION_PAPER_TEXT_MUTED_CLASS = 'text-[color:var(--wolfy-text-muted)]';

type CapitalRotationSummaryCard = {
  key: string;
  label: string;
  value: string;
  detail: string;
  variant: 'success' | 'info' | 'caution' | 'neutral' | 'danger';
};

type CapitalRotationSummaryView = {
  modeLabel: string;
  modeDetail: string;
  cards: CapitalRotationSummaryCard[];
};

type RotationConclusionView = {
  state: DecisionReadinessState;
  title: string;
  detail: string;
  whyNotConclusion: string;
  missingEvidence: string[];
  nextStep: string;
  variant: 'neutral' | 'info' | 'caution' | 'danger' | 'success';
};

type DataStateFields = {
  freshness?: MarketRotationTheme['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
};

type RotationTierView = {
  libraryMode: boolean;
  confirmedLeaders: MarketRotationTheme[];
  candidateThemes: MarketRotationTheme[];
  coolingThemes: MarketRotationTheme[];
  taxonomyThemes: MarketRotationTheme[];
};

type RotationPrimaryDisplayMode = 'headline' | 'observation' | 'taxonomy' | 'unavailable';

type ThemeFlowSignalView = NonNullable<MarketRotationTheme['themeFlowSignal']>;
type RotationMatrixStageMeta = {
  key: MarketRotationStage;
  label: string;
};
type RotationFamilyView = {
  familyKey: string;
  familyName: string;
  item: MarketRotationFamilyRollupItem;
  themeCount: number;
  signalThemeCount: number;
  averageRotationScore: number | null;
  averageConfidence: number | null;
  reasonLabels: string[];
  preview: string;
  collapsedByDefault: boolean;
  hasUsefulSignal: boolean;
};

const ROTATION_MATRIX_STAGE_ORDER: RotationMatrixStageMeta[] = [
  { key: 'confirmed_rotation', label: '确认轮动' },
  { key: 'extended_watch', label: '延展观察' },
  { key: 'early_watch', label: '早期观察' },
  { key: 'cooling_watch', label: '降温观察' },
  { key: 'weak_or_no_signal', label: '信号较弱' },
];

function hasMomentumProxyInputs(theme: MarketRotationTheme): boolean {
  return [
    theme.volume?.averageRelativeVolume,
    theme.breadth?.percentUp,
    theme.breadth?.percentOutperformingBenchmark,
    theme.synchronization?.sameDirectionPercent,
    theme.synchronization?.aboveVwapPercent,
    theme.persistenceEvidence?.score,
    theme.leadership?.topMembers?.length,
  ].some((value) => value !== null && value !== undefined && Number.isFinite(Number(value)) && Number(value) > 0);
}

function isTaxonomyOnlyTheme(theme?: MarketRotationTheme): boolean {
  if (theme?.taxonomyOnly === false) {
    return false;
  }

  return Boolean(
    theme?.taxonomyOnly === true
    || theme?.dataQuality === 'taxonomy_only'
    || theme?.dataCoverage === 'taxonomy_only'
    || theme?.source === 'local_taxonomy'
    || theme?.sourceClass === 'local_taxonomy',
  );
}

function normalizeSignalType(value?: string | null): MarketRotationSignalType | null {
  switch (value) {
    case 'real_flow':
    case 'relative_strength':
    case 'momentum_proxy':
    case 'observation_only':
    case 'taxonomy_fallback':
    case 'insufficient_evidence':
      return value;
    default:
      return null;
  }
}

function resolveSignalType(theme: MarketRotationTheme): MarketRotationSignalType {
  const direct = normalizeSignalType(theme.signalType);
  if (direct) {
    return direct;
  }
  const flowEvidenceType = String(
    theme.flowEvidenceType
      || (theme.rotationStateEvidence as Record<string, unknown> | undefined)?.flowEvidenceType
      || 'none',
  ).trim();
  if (isTaxonomyOnlyTheme(theme) || theme.source === 'local_taxonomy' || theme.taxonomyOnly) {
    return 'taxonomy_fallback';
  }
  if (REAL_FLOW_EVIDENCE_TYPES.has(flowEvidenceType) && theme.flowLanguageAllowed) {
    return 'real_flow';
  }
  if (parseRotationMetric(theme.relativeStrength?.averageRelativeStrengthPercent) !== null) {
    return 'relative_strength';
  }
  if (hasMomentumProxyInputs(theme)) {
    return 'momentum_proxy';
  }
  if (theme.observationOnly) {
    return 'observation_only';
  }
  return 'insufficient_evidence';
}

function normalizeEvidenceQuality(value?: string | null): MarketRotationEvidenceQuality | null {
  switch (value) {
    case 'score_grade_real_flow':
    case 'score_grade_proxy':
    case 'degraded_proxy':
    case 'observation_only':
    case 'taxonomy_only':
    case 'insufficient':
      return value;
    default:
      return null;
  }
}

function resolveEvidenceQuality(theme: MarketRotationTheme): MarketRotationEvidenceQuality {
  const direct = normalizeEvidenceQuality(theme.evidenceQuality);
  if (direct) {
    return direct;
  }
  switch (resolveSignalType(theme)) {
    case 'real_flow':
      return 'score_grade_real_flow';
    case 'relative_strength':
    case 'momentum_proxy':
      return theme.sourceAuthorityAllowed ? 'score_grade_proxy' : 'degraded_proxy';
    case 'observation_only':
      return 'observation_only';
    case 'taxonomy_fallback':
      return 'taxonomy_only';
    default:
      return 'insufficient';
  }
}

function formatGapLabel(value?: string | null): string {
  const normalized = String(value || '').trim();
  if (!normalized) {
    return '信号仍待补齐';
  }
  return DATA_GAP_LABELS[normalized] || '信号仍待补齐';
}

function themeDataGaps(theme: MarketRotationTheme): string[] {
  const gaps = Array.isArray(theme.dataGaps) ? theme.dataGaps : [];
  return gaps.reduce<string[]>((acc, gap) => {
    const g = String(gap || '').trim();
    if (g && acc.indexOf(g) === -1) acc.push(g);
    return acc;
  }, []);
}

function consumerThemeSubtitle(theme: MarketRotationTheme): string {
  const raw = theme.focus || theme.englishName || theme.benchmark || '';
  const normalized = localizeRotationEnglishCopy(String(raw).trim());
  if (!normalized) {
    return '观察线索';
  }
  if (/^[\w\s/.:+-]+$/.test(normalized) && theme.focus) {
    return '观察线索';
  }
  if (/proxy|provider|source|debug|trace|raw|schema|代理|来源|提供方|诊断/i.test(normalized)) {
    return '观察线索';
  }
  return sanitizeRotationText(normalized, '观察线索');
}

function localizeRotationEnglishCopy(value: string): string {
  return ROTATION_ENGLISH_COPY_REPLACEMENTS.reduce(
    (current, [pattern, replacement]) => current.replace(pattern, replacement),
    value,
  );
}

function consumerFreshnessLabel(freshness?: string | null, isFallback?: boolean, isStale?: boolean): string {
  if (isFallback || freshness === 'fallback' || isStale || freshness === 'stale') {
    return '数据延迟，已使用最近一次可用数据。';
  }
  if (freshness === 'delayed') {
    return '数据延迟。';
  }
  if (freshness === 'live') {
    return '数据已更新。';
  }
  return '信号待确认，等待数据更新。';
}

function consumerConfidenceLabel(state: DecisionReadinessState): string {
  if (state === 'ready') {
    return '当前轮动信号可用，仍需持续观察走势分化。';
  }
  if (state === 'observe') {
    return '信号待确认，先看板块强弱与走势分化。';
  }
  return '轮动数据待确认';
}

function consumerSufficiencyLabel(state: DecisionReadinessState): string {
  if (state === 'ready') {
    return '板块强弱可读。';
  }
  if (state === 'observe') {
    return '部分数据延迟。';
  }
  return '信号待确认。';
}

function consumerStatusLabel(state: DecisionReadinessState, payload: MarketRotationRadarResponse): string {
  if (!payload.themes.length) {
    return '轮动方向待确认';
  }
  if (state === 'ready') {
    return payload.freshness === 'delayed' ? '数据延迟可读' : '板块强弱可读';
  }
  if (state === 'observe') {
    return payload.isFallback || payload.isStale ? '数据延迟' : '信号待确认';
  }
  if (isRotationLibraryMode(payload)) {
    return '信号待确认';
  }
  if (payload.isFallback || payload.isStale) {
    return '数据延迟';
  }
  return payload.themes.length ? '信号待确认' : '轮动方向待确认';
}

function formatThemeStage(stage?: MarketRotationStage): string {
  return stage ? STAGE_LABELS[stage] || stage : '待识别';
}

function formatThemeFlowState(state?: string | null): string {
  const normalized = String(state || '').trim();
  if (!normalized) {
    return '待确认';
  }
  return THEME_FLOW_STATE_LABELS[normalized] || sanitizeRotationText(normalized, '待确认');
}

function themeFlowChipVariant(state?: string | null): 'success' | 'info' | 'caution' | 'neutral' {
  switch (state) {
    case 'leading':
      return 'success';
    case 'broadening':
    case 'rotating':
      return 'info';
    case 'crowded':
    case 'fading':
    case 'mixed':
      return 'caution';
    default:
      return 'neutral';
  }
}

function formatThemeFlowConfidence(signal?: MarketRotationTheme['themeFlowSignal'] | null): string {
  const raw = signal?.confidence;
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    return `${Math.round(raw <= 1 ? raw * 100 : raw)}%`;
  }
  if (typeof raw === 'string') {
    const numeric = Number(raw);
    if (Number.isFinite(numeric)) {
      return `${Math.round(numeric <= 1 ? numeric * 100 : numeric)}%`;
    }
  }
  const label = String(signal?.confidenceLabel || signal?.confidenceText || '').trim();
  return label || '待确认';
}

function extractThemeFlowLeadershipEvidence(signal?: MarketRotationTheme['themeFlowSignal'] | null): string | null {
  const candidate = signal && typeof signal === 'object'
    ? (signal as ThemeFlowSignalView & { leadershipEvidence?: unknown }).leadershipEvidence
    : null;
  return typeof candidate === 'string' && candidate.trim()
    ? sanitizeRotationText(candidate, '龙头线索待补齐。')
    : null;
}

function themeFlowReasonLabels(signal?: MarketRotationTheme['themeFlowSignal'] | null): string[] {
  const codes = Array.isArray(signal?.reasonCodes) ? signal.reasonCodes : [];
  const labels: string[] = [];
  const seen = new Set<string>();
  for (const code of codes) {
    const label = THEME_FLOW_REASON_LABELS[String(code || '').trim()] || '';
    if (!label || seen.has(label)) continue;
    seen.add(label);
    labels.push(label);
    if (labels.length === 3) break;
  }
  return labels;
}

function themeFlowEvidenceLines(signal?: MarketRotationTheme['themeFlowSignal'] | null): string[] {
  return [
    extractThemeFlowLeadershipEvidence(signal) || '龙头线索待补齐。',
    sanitizeRotationText(signal?.breadthEvidence, '广度证据待补齐。'),
    sanitizeRotationText(signal?.relativeStrengthEvidence, '相对强弱证据待补齐。'),
  ];
}

function hasThemeCorrelationBreadthSnapshot(
  snapshot?: MarketRotationThemeCorrelationBreadthSnapshot | null,
): snapshot is MarketRotationThemeCorrelationBreadthSnapshot {
  if (!snapshot || typeof snapshot !== 'object') {
    return false;
  }
  return Boolean(
    snapshot.participationState
      || snapshot.leadershipConcentration
      || snapshot.correlationEvidence
      || snapshot.breadthEvidence,
  );
}

function formatSnapshotState(
  value: string | null | undefined,
  labels: Record<string, string>,
  fallback: string,
): string {
  const normalized = String(value || '').trim();
  if (!normalized) {
    return fallback;
  }
  return labels[normalized] || sanitizeRotationText(normalized, fallback);
}

function formatSnapshotPercent(value?: number | string | null): string {
  if (!Number.isFinite(Number(value))) {
    return '待补齐';
  }
  return `${Number(value).toFixed(1)}%`;
}

function formatSnapshotMemberCount(observed?: number | null, configured?: number | null): string {
  const observedNumber = Number(observed);
  const configuredNumber = Number(configured);
  if (!Number.isFinite(observedNumber) || !Number.isFinite(configuredNumber) || configuredNumber <= 0) {
    return '样本待补齐';
  }
  return `${Math.max(0, Math.round(observedNumber))}/${Math.max(0, Math.round(configuredNumber))} 个成员`;
}

function formatSnapshotInputLabel(value?: string | null): string {
  const normalized = String(value || '').trim();
  if (!normalized) {
    return '';
  }
  const fallbackWindow = normalized.match(/^fallback_window:(.+)$/);
  if (fallbackWindow?.[1]) {
    return `${sanitizeRotationText(fallbackWindow[1], '该时窗')} 时窗数据待更新`;
  }
  return SNAPSHOT_INPUT_LABELS[normalized] || sanitizeRotationText(normalized, '数据项待补齐');
}

function formatSnapshotInputLabels(values?: string[] | null, fallback = '暂无'): string[] {
  const seen = new Set<string>();
  const labels: string[] = [];
  for (const value of values || []) {
    const label = formatSnapshotInputLabel(value);
    if (!label || seen.has(label)) {
      continue;
    }
    seen.add(label);
    labels.push(label);
  }
  return labels.length ? labels : [fallback];
}

function formatSnapshotNextSteps(values?: string[] | null): string[] {
  const seen = new Set<string>();
  const labels: string[] = [];
  for (const value of values || []) {
    const raw = String(value || '').trim();
    const label = SNAPSHOT_NEXT_STEP_LABELS[raw] || sanitizeRotationText(raw, '');
    if (!label || seen.has(label)) {
      continue;
    }
    seen.add(label);
    labels.push(label);
  }
  return labels.length ? labels.slice(0, 3) : ['继续观察广度、同步与龙头分布是否发生变化。'];
}

function formatSnapshotBoundaryLabels(
  boundary?: MarketRotationThemeCorrelationBreadthSnapshot['observationBoundary'] | null,
): string[] {
  if (!boundary || typeof boundary !== 'object') {
    return ['仅作研究观察'];
  }
  const labels = [
    boundary.scope === 'existing_theme_fields' ? '仅使用已展示主题字段' : '观察口径受限',
    boundary.rankingImpact === 'none' ? '不改变排序' : null,
    boundary.dataMutation === 'none' ? '不改动数据' : null,
    boundary.dataFetches === 'none' ? '不新增取数' : null,
  ].filter((label): label is string => Boolean(label));
  return labels.length ? labels : ['仅作研究观察'];
}

function snapshotSummary(snapshot: MarketRotationThemeCorrelationBreadthSnapshot): string {
  const participation = formatSnapshotState(snapshot.participationState, THEME_PARTICIPATION_LABELS, '参与状态待补齐');
  const breadth = formatSnapshotState(snapshot.breadthEvidence?.state, THEME_BREADTH_LABELS, '广度待补齐');
  const correlation = formatSnapshotState(snapshot.correlationEvidence?.state, THEME_CORRELATION_LABELS, '同步证据待补齐');
  const staleCount = Array.isArray(snapshot.staleInputs) ? snapshot.staleInputs.length : 0;
  const missingCount = Array.isArray(snapshot.missingInputs) ? snapshot.missingInputs.length : 0;
  const dataState = missingCount > 0
    ? `${missingCount} 项待补齐`
    : staleCount > 0
      ? `${staleCount} 项待更新`
      : '输入完整';
  return `${participation} · ${breadth} · ${correlation} · ${dataState}`;
}

function resolveRotationFamilyRollup(payload: MarketRotationRadarResponse): MarketRotationFamilyRollupItem[] {
  const summaryRollup = Array.isArray(payload.summary.rotationFamilyRollup) ? payload.summary.rotationFamilyRollup : [];
  if (summaryRollup.length) {
    return summaryRollup;
  }
  return Array.isArray(payload.consumerEvidenceSnapshot?.rotationFamilyRollup)
    ? payload.consumerEvidenceSnapshot.rotationFamilyRollup
    : [];
}

function mapDataStateLabel(theme: DataStateFields): string {
  const candidate = theme as MarketRotationTheme;
  if (isTaxonomyOnlyTheme(candidate)) {
    return '观察资料不足';
  }
  if (
    resolveSignalType(candidate) === 'insufficient_evidence'
    || resolveEvidenceQuality(candidate) === 'insufficient'
  ) {
    return '观察资料不足';
  }
  if (theme.isFallback || theme.freshness === 'fallback') {
    return '最近一次可用';
  }
  if (theme.isStale || theme.freshness === 'stale') {
    return '最近一次可用';
  }
  if (theme.freshness === 'delayed') {
    return '延迟可用';
  }
  if (theme.freshness === 'live') {
    return '实时';
  }
  return '数据更新中';
}

function formatConfidenceValue(confidence?: number | null): string {
  return formatRotationConfidenceValue(confidence);
}

function formatRelativeStrengthValue(value?: number | null): string {
  return formatRotationRelativeStrengthValue(value);
}

function themeConfidenceSummary(theme?: MarketRotationTheme): string {
  if (!theme) {
    return '待确认';
  }
  if (isTaxonomyOnlyTheme(theme)) {
    return '信号待确认';
  }
  return `信号 ${formatConfidenceValue(theme.confidence)}`;
}

function themeRelativeStrengthValue(theme?: MarketRotationTheme): number | null {
  return parseRotationMetric(theme?.relativeStrength?.averageRelativeStrengthPercent);
}

function themeHasUsefulFamilySignal(theme?: MarketRotationTheme): boolean {
  if (!theme || isTaxonomyOnlyTheme(theme)) {
    return false;
  }
  return resolveSignalType(theme) !== 'insufficient_evidence'
    && resolveEvidenceQuality(theme) !== 'insufficient'
    && theme.stage !== 'weak_or_no_signal'
    && hasPositiveKnownMetric(theme.rotationScore, theme.confidence);
}

function resolveFamilyThemes(item: MarketRotationFamilyRollupItem, themes: MarketRotationTheme[]): MarketRotationTheme[] {
  const ids = [...(item.themeIds || []), ...(item.leaderThemeIds || [])];
  if (!ids.length) {
    return [];
  }
  const seen = new Set<string>();
  const themeById = new Map(themes.map((theme) => [theme.id, theme]));
  return ids.reduce<MarketRotationTheme[]>((acc, id) => {
    const normalizedId = String(id || '').trim();
    if (!normalizedId || seen.has(normalizedId)) {
      return acc;
    }
    const theme = themeById.get(normalizedId);
    if (!theme) {
      return acc;
    }
    seen.add(normalizedId);
    acc.push(theme);
    return acc;
  }, []);
}

function buildRotationFamilyViews(payload: MarketRotationRadarResponse): RotationFamilyView[] {
  const rollup = resolveRotationFamilyRollup(payload);
  const themes = payload.themes || [];

  return rollup
    .map((item, index) => {
      const familyThemes = resolveFamilyThemes(item, themes);
      const familyName = String(item.familyName || item.familyId || `家族 ${index + 1}`).trim();
      const familyKey = item.familyId
        || item.themeIds?.join('|')
        || item.leaderThemeIds?.join('|')
        || familyName;
      const signalThemeCount = parseRotationMetric(item.signalThemeCount) ?? familyThemes.filter(themeHasUsefulFamilySignal).length;
      const themeCount = parseRotationMetric(item.themeCount) ?? familyThemes.length;
      const averageRotationScore = parseRotationMetric(item.averageRotationScore);
      const averageConfidence = parseRotationMetric(item.averageConfidence);
      const hasUsefulSignal = familyThemes.some(themeHasUsefulFamilySignal)
        || signalThemeCount > 0
        || Boolean(
          item.themeFlowSignal?.themeFlowState
          && hasPositiveKnownMetric(averageRotationScore)
          && hasPositiveKnownMetric(averageConfidence),
        );
      const collapsedByDefault = !hasUsefulSignal && (
        familyThemes.length
          ? familyThemes.every((theme) => isTaxonomyOnlyTheme(theme) || resolveEvidenceQuality(theme) === 'insufficient' || theme.stage === 'weak_or_no_signal')
          : signalThemeCount <= 0
            && !hasPositiveKnownMetric(averageRotationScore)
            && !hasPositiveKnownMetric(averageConfidence)
      );
      return {
        familyKey,
        familyName,
        item,
        themeCount,
        signalThemeCount,
        averageRotationScore,
        averageConfidence,
        reasonLabels: themeFlowReasonLabels(item.themeFlowSignal),
        preview: sanitizeRotationText(
          item.themeFlowSignal?.explanation,
          collapsedByDefault
            ? `${familyName} 默认折叠`
            : `${familyName} 当前仅保留家族级观察。`,
        ),
        collapsedByDefault,
        hasUsefulSignal,
      };
    })
    .sort((a, b) => {
      if (a.collapsedByDefault !== b.collapsedByDefault) {
        return a.collapsedByDefault ? 1 : -1;
      }
      if (a.hasUsefulSignal !== b.hasUsefulSignal) {
        return a.hasUsefulSignal ? -1 : 1;
      }
      if (b.signalThemeCount !== a.signalThemeCount) {
        return b.signalThemeCount - a.signalThemeCount;
      }
      const scoreCmp = compareNullableDesc(a.averageRotationScore, b.averageRotationScore);
      if (scoreCmp !== 0) {
        return scoreCmp;
      }
      const confidenceCmp = compareNullableDesc(a.averageConfidence, b.averageConfidence);
      if (confidenceCmp !== 0) {
        return confidenceCmp;
      }
      if (b.themeCount !== a.themeCount) {
        return b.themeCount - a.themeCount;
      }
      return a.familyName.localeCompare(b.familyName, 'zh-Hans-CN');
    });
}

function isObservationTheme(theme?: MarketRotationTheme): theme is MarketRotationTheme {
  if (!theme || isTaxonomyOnlyTheme(theme)) {
    return false;
  }
  return theme.rankingLane === 'observation'
    || theme.observationOnly === true
    || theme.headlineEligible === false
    || resolveEvidenceQuality(theme) === 'degraded_proxy'
    || resolveEvidenceQuality(theme) === 'observation_only';
}

function observationStateLabel(theme?: MarketRotationTheme): string | null {
  if (!isObservationTheme(theme)) {
    return null;
  }
  const signalType = resolveSignalType(theme);
  if (signalType === 'relative_strength' || signalType === 'momentum_proxy' || resolveEvidenceQuality(theme) === 'degraded_proxy') {
    return '对比样本观察';
  }
  return '观察信号';
}

function observationDirectionCue(theme?: MarketRotationTheme): {
  indicator: '↑' | '↓' | '→';
  label: string;
  changeText: string;
} | null {
  if (!isObservationTheme(theme)) {
    return null;
  }

  const strength = themeRelativeStrengthValue(theme);
  const benchmark = String(theme?.relativeStrength?.benchmark || theme?.benchmark || '').trim();
  const benchmarkPrefix = benchmark ? `相对 ${benchmark} ` : '';

  if (strength !== null) {
    if (strength >= 0.5) {
      return { indicator: '↑', label: '升温观察', changeText: `${benchmarkPrefix}${formatRelativeStrengthValue(strength)}` };
    }
    if (strength <= -0.5) {
      return { indicator: '↓', label: '降温观察', changeText: `${benchmarkPrefix}${formatRelativeStrengthValue(strength)}` };
    }
    return { indicator: '→', label: '横向观察', changeText: `${benchmarkPrefix}${formatRelativeStrengthValue(strength)}` };
  }

  if (theme?.stage === 'cooling_watch' || theme?.stage === 'weak_or_no_signal') {
    return { indicator: '↓', label: '降温观察', changeText: '方向仍待更多样本确认' };
  }

  if (theme?.stage === 'early_watch' || theme?.stage === 'extended_watch' || theme?.stage === 'confirmed_rotation') {
    return { indicator: '↑', label: '升温观察', changeText: '方向仍待更多样本确认' };
  }

  return { indicator: '→', label: '横向观察', changeText: '方向仍待更多样本确认' };
}

function observationThemeSummary(theme?: MarketRotationTheme): string | null {
  const stateLabel = observationStateLabel(theme);
  const directionCue = observationDirectionCue(theme);
  const items = [stateLabel, directionCue?.label].filter(Boolean);
  return items.length ? items.join(' · ') : null;
}

function themeSupportsVisualMatrix(theme?: MarketRotationTheme): theme is MarketRotationTheme {
  if (!theme || isTaxonomyOnlyTheme(theme)) {
    return false;
  }
  return themeRelativeStrengthValue(theme) !== null && Boolean(theme.stage);
}

function deriveVisualMatrixThemes(themes: MarketRotationTheme[]): MarketRotationTheme[] {
  return themes.filter(themeSupportsVisualMatrix);
}

function deriveVisualStrengthDomain(themes: MarketRotationTheme[]): { min: number; max: number } {
  const values = themes
    .map((theme) => themeRelativeStrengthValue(theme))
    .filter((value): value is number => value !== null);

  if (!values.length) {
    return { min: -1, max: 1 };
  }

  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  if (min === max) {
    return { min: min - 1, max: max + 1 };
  }
  return { min, max };
}

function isInternalRotationIssue(value?: string | null): boolean {
  const normalized = String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  return /provider|timeout|schema|debug|raw|trace|cache|quote|source|proxy|fallback|static|taxonomy|not_enough|unavailable|missing|insufficient|technical_indicators|fundamentals|earnings|optional_news/.test(normalized);
}

function sanitizeTradingActionWords(value: string): string {
  return value
    .replaceAll('买卖信号', '方向结论')
    .replaceAll('买卖建议', '投资建议')
    .replaceAll('买卖', '投资动作')
    .replace(/\brecommendations?\b/gi, 'research framing')
    .replace(/\brecommended\b/gi, 'research-framed')
    .replace(/\brecommend\b/gi, 'research frame');
}

function sanitizeRotationText(value?: string | null, fallback = '数据不足，结论仅供观察'): string {
  const text = localizeRotationEnglishCopy(String(value || '').trim());
  if (!text) return fallback;
  if (isInternalRotationIssue(text)) {
    return '部分轮动数据暂不可用。';
  }
  const consumerText = text
    .replaceAll('备用篮子', '备选分类')
    .replaceAll('备用主题池', '备选分类')
    .replaceAll('缺少可用行情与时窗证据', '当前缺少足够行情与时间窗口数据，暂不能形成稳定轮动判断')
    .replaceAll('缺少可用行情和时窗证据', '当前缺少足够行情与时间窗口数据，暂不能形成稳定轮动判断')
    .replaceAll('新鲜度', '数据更新')
    .replaceAll('置信度', '信号确认')
    .replaceAll('结论状态', '轮动方向')
    .replaceAll('缺失证据', '信号待确认')
    .replaceAll('缺失', '待确认')
    .replaceAll('静态主题库', '分类浏览')
    .replaceAll('主题库', '分类浏览')
    .replaceAll('真实资金流', '确认信号')
    .replaceAll('真实流向', '确认信号')
    .replaceAll('权威来源', '确认信号')
    .replaceAll('ETF 代理', '对比样本')
    .replaceAll('代理证据', '观察信号');
  return sanitizeTradingActionWords(sanitizeMarketGuidanceCopy(consumerText, fallback));
}

function sanitizeRotationNotes(notes?: string[]): string[] {
  return (notes || []).reduce<string[]>((acc, note) => {
    const n = sanitizeRotationText(note, '');
    if (n && acc.indexOf(n) === -1) acc.push(n);
    return acc;
  }, []);
}

function isThemeStale(theme: DataStateFields): boolean {
  return Boolean(theme.isStale || theme.freshness === 'stale');
}

function deriveTopThemes(themes: MarketRotationTheme[], limit = TOP_THEME_LIMIT): MarketRotationTheme[] {
  return sortThemesByEvidenceDesc(themes).slice(0, limit);
}

function materializeSummaryTheme(item: MarketRotationSummaryItem, fullTheme?: MarketRotationTheme): MarketRotationTheme {
  const raw = item as Partial<MarketRotationTheme>;
  return {
    ...fullTheme,
    ...raw,
    id: item.id,
    name: item.name,
    rotationScore: item.rotationScore,
    confidence: item.confidence,
    stage: item.stage,
    riskLabels: item.riskLabels,
    riskExplanations: raw.riskExplanations || fullTheme?.riskExplanations || [],
    rankEligible: item.rankEligible,
    rankExclusionReason: item.rankExclusionReason,
    taxonomyOnly: item.taxonomyOnly,
    observationOnly: item.observationOnly,
    headlineEligible: item.headlineEligible,
    rankingLane: item.rankingLane,
    scoreContributionAllowed: item.scoreContributionAllowed,
    signalType: item.signalType,
    flowEvidenceType: item.flowEvidenceType,
    flowLanguageAllowed: item.flowLanguageAllowed,
    sourceAuthorityAllowed: item.sourceAuthorityAllowed,
    evidenceQuality: item.evidenceQuality,
    dataGaps: item.dataGaps,
    sourceTier: item.sourceTier,
    trustLevel: item.trustLevel,
    englishName: raw.englishName || fullTheme?.englishName || item.name,
    focus: raw.focus ?? fullTheme?.focus,
    benchmark: raw.benchmark || fullTheme?.benchmark || '',
    sectorBenchmark: raw.sectorBenchmark ?? fullTheme?.sectorBenchmark,
    membersConfigured: Array.isArray(raw.membersConfigured)
      ? raw.membersConfigured
      : fullTheme?.membersConfigured || [],
    newslessRotation: raw.newslessRotation ?? fullTheme?.newslessRotation ?? false,
    relativeStrength: raw.relativeStrength || fullTheme?.relativeStrength || {},
    volume: raw.volume || fullTheme?.volume || {},
    breadth: raw.breadth || fullTheme?.breadth || {},
    synchronization: raw.synchronization || fullTheme?.synchronization || {},
    leadership: raw.leadership || fullTheme?.leadership || {},
    themeDetail: raw.themeDetail || fullTheme?.themeDetail,
    freshness: item.freshness,
    isFallback: item.isFallback,
    source: raw.source || fullTheme?.source,
    sourceLabel: raw.sourceLabel ?? fullTheme?.sourceLabel,
    asOf: raw.asOf ?? fullTheme?.asOf,
    updatedAt: raw.updatedAt ?? fullTheme?.updatedAt,
    evidence: Array.isArray(raw.evidence) ? raw.evidence : fullTheme?.evidence || [],
    members: Array.isArray(raw.members) ? raw.members : fullTheme?.members || [],
    noAdviceDisclosure: raw.noAdviceDisclosure || fullTheme?.noAdviceDisclosure || '',
    themeFlowSignal: raw.themeFlowSignal || fullTheme?.themeFlowSignal,
  };
}

function resolveSummaryThemes(themes: MarketRotationTheme[], summaryItems: MarketRotationSummaryItem[]): MarketRotationTheme[] {
  const themeById = new Map(themes.map((theme) => [theme.id, theme]));
  const seen = new Set<string>();
  return summaryItems
    .map((item) => materializeSummaryTheme(item, themeById.get(item.id)))
    .filter((theme) => {
      if (!theme.id || seen.has(theme.id)) {
        return false;
      }
      seen.add(theme.id);
      return true;
    });
}

function hasObservationThemeData(theme: MarketRotationTheme): boolean {
  if (isTaxonomyOnlyTheme(theme)) {
    return false;
  }
  const hasMatrixFields = themeRelativeStrengthValue(theme) !== null && Boolean(theme.stage);
  const hasScoreOrConfidence = parseRotationMetric(theme.rotationScore) !== null
    || parseRotationMetric(theme.confidence) !== null;
  const hasUsableSignal = hasMatrixFields
    || hasScoreOrConfidence
    || Boolean(theme.themeFlowSignal?.breadthEvidence || theme.themeFlowSignal?.relativeStrengthEvidence);
  // Partial evidence is kept when any usable metric exists; missing score alone is not full unavailability.
  return hasUsableSignal
    && (theme.rankingLane === 'observation' || theme.observationOnly === true || theme.headlineEligible === false);
}

function resolveObservationSummaryThemes(payload: MarketRotationRadarResponse): MarketRotationTheme[] {
  const summaryThemes = resolveSummaryThemes(payload.themes || [], payload.summary.observationThemes || []);
  return summaryThemes.filter(hasObservationThemeData).slice(0, TOP_THEME_LIMIT);
}

function deriveWeakeningThemes(themes: MarketRotationTheme[]): MarketRotationTheme[] {
  return [...themes]
    .filter((theme) => {
      const score = parseRotationMetric(theme.rotationScore);
      return theme.stage === 'cooling_watch'
        || theme.stage === 'weak_or_no_signal'
        || (score !== null && score < 50);
    })
    .sort((a, b) => {
      const scoreCmp = compareNullableAsc(
        parseRotationMetric(a.rotationScore),
        parseRotationMetric(b.rotationScore),
      );
      if (scoreCmp !== 0) {
        return scoreCmp;
      }
      return String(a.name || '').localeCompare(String(b.name || ''), 'zh-Hans-CN')
        || String(a.id || '').localeCompare(String(b.id || ''));
    })
    .slice(0, 4);
}

function matchesSearch(theme: MarketRotationTheme, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  const haystack = [
    theme.name,
    theme.englishName,
    theme.focus,
    theme.benchmark,
    theme.sectorBenchmark,
    ...(theme.membersConfigured || []),
    ...(theme.mappedConcepts || []),
    ...(theme.representativeLabels || []),
    ...(theme.representativeSymbols || []),
    ...(theme.leadership?.topMembers || []).map((member) => `${member.symbol} ${member.name || ''}`),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return haystack.includes(normalized);
}

function marketLabel(market: string): string {
  return MARKET_OPTIONS.find((option) => option.id === market)?.label || market;
}

function rotationScoreEligibleCount(payload: MarketRotationRadarResponse): number {
  return (payload.etfLeadershipDiagnostics?.evidence || []).filter((row) => row.scoreContributionAllowed === true).length;
}

function isRotationLibraryMode(payload: MarketRotationRadarResponse): boolean {
  const themes = payload.themes || [];
  return themes.length > 0 && themes.every(isTaxonomyOnlyTheme);
}

function isConfirmedRealFlowLeader(theme: MarketRotationTheme): boolean {
  return !isTaxonomyOnlyTheme(theme)
    && resolveSignalType(theme) === 'real_flow'
    && theme.flowLanguageAllowed === true
    && resolveEvidenceQuality(theme) === 'score_grade_real_flow'
    && (theme.stage === 'confirmed_rotation' || theme.stage === 'extended_watch');
}

function isCandidateWatchTheme(theme: MarketRotationTheme, confirmedIds: Set<string>): boolean {
  const signalType = resolveSignalType(theme);
  return !isTaxonomyOnlyTheme(theme)
    && !confirmedIds.has(theme.id)
    && (theme.stage === 'confirmed_rotation' || theme.stage === 'early_watch' || theme.stage === 'extended_watch')
    && (signalType === 'relative_strength' || signalType === 'momentum_proxy')
    && resolveEvidenceQuality(theme) !== 'insufficient';
}

function deriveRotationTiers(payload: MarketRotationRadarResponse): RotationTierView {
  const themes = payload.themes || [];
  const confirmedLeaders = deriveTopThemes(themes.filter(isConfirmedRealFlowLeader), 3);
  const confirmedIds = new Set(confirmedLeaders.map((theme) => theme.id));
  const summaryObservationThemes = resolveObservationSummaryThemes(payload);
  return {
    libraryMode: isRotationLibraryMode(payload),
    confirmedLeaders,
    candidateThemes: summaryObservationThemes.length
      ? summaryObservationThemes.slice(0, 3)
      : deriveTopThemes(themes.filter((theme) => isCandidateWatchTheme(theme, confirmedIds)), 3),
    coolingThemes: deriveWeakeningThemes(themes).filter((theme) => !isTaxonomyOnlyTheme(theme)).slice(0, 3),
    taxonomyThemes: themes.filter(isTaxonomyOnlyTheme).slice(0, 3),
  };
}

function derivePrimaryDisplayThemes(
  payload: MarketRotationRadarResponse,
  tiers = deriveRotationTiers(payload),
): MarketRotationTheme[] {
  if (tiers.confirmedLeaders.length) {
    return tiers.confirmedLeaders;
  }
  if (tiers.candidateThemes.length) {
    return tiers.candidateThemes;
  }
  return [];
}

function primaryDisplayMode(tiers?: RotationTierView | null): RotationPrimaryDisplayMode {
  if (!tiers) {
    return 'unavailable';
  }
  if (tiers.libraryMode) {
    return 'taxonomy';
  }
  if (tiers.confirmedLeaders.length) {
    return 'headline';
  }
  if (tiers.candidateThemes.length) {
    return 'observation';
  }
  return 'unavailable';
}

function primaryDisplayLabel(mode: RotationPrimaryDisplayMode): string {
  switch (mode) {
    case 'headline':
      return '确认信号';
    case 'observation':
      return '观察数据';
    case 'taxonomy':
      return '分类浏览';
    default:
      return '信号待确认';
  }
}

function primaryDisplayDetail(mode: RotationPrimaryDisplayMode): string {
  if (mode === 'headline') {
    return '当前只展示已满足确认条件的头部主题，其他主题保留在下方观察列表。';
  }
  if (mode === 'observation') {
    return '当前为对比样本与观察数据，仅作走势观察，不形成强结论。';
  }
  if (mode === 'taxonomy') {
    return '当前以分类浏览为主，等待更多行情覆盖后再确认强弱。';
  }
  return '当前结构化强弱维度仍待确认，暂不展示主视图。';
}

function deriveRotationDecisionState(
  payload: MarketRotationRadarResponse,
  tiers = deriveRotationTiers(payload),
): DecisionReadinessState {
  const confirmedCount = tiers.confirmedLeaders.length;
  const candidateCount = tiers.candidateThemes.length;
  const scoreEligibleCount = rotationScoreEligibleCount(payload);

  if (confirmedCount > 0 && scoreEligibleCount > 0 && !payload.isFallback && !payload.isStale) {
    return 'ready';
  }
  if (tiers.libraryMode || payload.isFallback || payload.isStale || payload.themes.length === 0) {
    return 'unavailable';
  }
  if (candidateCount > 0 || scoreEligibleCount > 0) {
    return 'observe';
  }
  return 'unavailable';
}

function deriveConclusionScopeThemes(
  payload: MarketRotationRadarResponse,
  tiers = deriveRotationTiers(payload),
): MarketRotationTheme[] {
  const scopeThemes = resolveSummaryThemes(payload.themes || [], payload.summary.strongestThemes || []);
  const primaryThemes = derivePrimaryDisplayThemes(payload, tiers);
  return primaryThemes.length ? primaryThemes : scopeThemes.length ? scopeThemes : payload.themes || [];
}

function hasBreadthEvidence(themes: MarketRotationTheme[]): boolean {
  return themes.some((theme) => Number.isFinite(Number(theme.breadth?.percentUp)) && Number(theme.breadth?.percentUp) > 0);
}

function deriveMissingEvidence(
  payload: MarketRotationRadarResponse,
  tiers = deriveRotationTiers(payload),
  summaryThemes = deriveConclusionScopeThemes(payload, tiers),
): string[] {
  const missing = [
    payload.themes.length === 0 ? '可比较样本不足' : '',
    tiers.libraryMode ? '观察时窗不足' : '',
    tiers.libraryMode ? '成员覆盖不足' : '',
    tiers.confirmedLeaders.length === 0 ? '确认信号不足' : '',
    rotationScoreEligibleCount(payload) === 0 ? '评分条件不足' : '',
    !hasBreadthEvidence(summaryThemes) || tiers.confirmedLeaders.length === 0 ? '广度信息不足' : '',
    payload.isFallback ? '最近数据不足' : '',
    payload.isStale ? '最近数据不足' : '',
    ...summaryThemes.reduce<string[]>((acc, theme) => {
      for (const gap of themeDataGaps(theme).slice(0, 2)) {
        acc.push(formatGapLabel(gap));
      }
      return acc;
    }, []),
  ];
  return uniqueReadinessItems(
    missing,
    5,
    tiers.confirmedLeaders.length ? '暂无关键限制，继续复核风险与数据更新' : '确认信号、广度与观察时窗仍待补齐',
  );
}

function deriveRotationConclusion(
  payload: MarketRotationRadarResponse,
  tiers = deriveRotationTiers(payload),
): RotationConclusionView {
  const state = deriveRotationDecisionState(payload, tiers);
  const summaryThemes = deriveConclusionScopeThemes(payload, tiers);
  const missingEvidence = deriveMissingEvidence(payload, tiers, summaryThemes);
  const themeScope = tiers.libraryMode ? '当前主题/行业/概念仅可分类浏览' : '当前主题/行业/概念';

  if (state === 'ready') {
    return {
      state,
      title: '板块强弱可读',
      detail: '当前轮动信号较完整，可作为主题轮动方向观察；仍需持续复核走势分化、风险与数据更新。',
      whyNotConclusion: '当前板块强弱、广度和持续性较完整，但页面仍只呈现研究观察，不扩展为交易动作。',
      missingEvidence,
      nextStep: '继续观察退潮主题、风险标签与更新时间；若走势分化扩大，应降级为信号待确认。',
      variant: 'success',
    };
  }

  if (state === 'observe') {
    return {
      state,
      title: '信号待确认',
      detail: '已有候选线索，但轮动方向、扩散广度或持续性仍待确认。',
      whyNotConclusion: `${themeScope}主要依赖相对强弱、观察项或局部样本，扩散与连续性尚未同时成立。`,
      missingEvidence,
      nextStep: tiers.libraryMode
        ? '查看分类候选或切换市场对比'
        : '查看候选主题或切换市场对比',
      variant: 'info',
    };
  }

  return {
    state,
    title: '轮动方向待确认',
    detail: '当前缺少足够行情与时间窗口数据，轮动方向待确认。',
    whyNotConclusion: tiers.libraryMode || payload.themes.length === 0
      ? `${themeScope}，可比较行情、时间窗口、成员广度或确认信号仍待确认。`
      : `${themeScope}近期行情、广度扩散和确认信号仍待确认。`,
    missingEvidence,
    nextStep: tiers.libraryMode
      ? '查看分类候选或切换市场对比'
      : '切换市场对比或等待数据更新',
    variant: 'danger',
  };
}

function rotationGuidance(payload: MarketRotationRadarResponse): {
  title: string;
  detail: string;
  variant: 'neutral' | 'info' | 'caution' | 'danger' | 'success';
} {
  const tiers = deriveRotationTiers(payload);
  const conclusion = deriveRotationConclusion(payload, tiers);

  if (tiers.libraryMode) {
    return {
      title: conclusion.title,
      detail: conclusion.detail,
      variant: 'caution',
    };
  }

  if (tiers.confirmedLeaders.length) {
    return {
      title: conclusion.title,
      detail: conclusion.detail,
      variant: 'success',
    };
  }

  if (tiers.candidateThemes.length) {
    return {
      title: conclusion.title,
      detail: conclusion.detail,
      variant: 'info',
    };
  }

  return {
    title: conclusion.title,
    detail: conclusion.detail,
    variant: 'danger',
  };
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

function buildRotationDecisionReadiness(payload: MarketRotationRadarResponse): DecisionReadinessSummary {
  const tiers = deriveRotationTiers(payload);
  const conclusion = deriveRotationConclusion(payload, tiers);
  const state = conclusion.state;

  return {
    state,
    stateLabel: consumerStatusLabel(state, payload),
    stateVariant: decisionReadinessVariant(state),
    qualityLabel: consumerConfidenceLabel(state),
    blockers: [consumerFreshnessLabel(payload.freshness, payload.isFallback, payload.isStale)],
    nextEvidence: [consumerSufficiencyLabel(state)],
    conclusion: state === 'ready'
      ? '当前轮动信号可用于研究观察，仍需结合风险与数据更新复核。'
      : state === 'observe'
        ? consumerConfidenceLabel(state)
        : consumerSufficiencyLabel(state),
  };
}

function themeNamesSummary(themes: MarketRotationTheme[], fallback: string): string {
  return themes.length ? themes.map((theme) => theme.name).join(' / ') : fallback;
}

function deriveCapitalRotationSummary(payload: MarketRotationRadarResponse): CapitalRotationSummaryView {
  const {
    libraryMode,
    confirmedLeaders,
    candidateThemes,
    coolingThemes,
    taxonomyThemes,
  } = deriveRotationTiers(payload);
  const conclusion = deriveRotationConclusion(payload, {
    libraryMode,
    confirmedLeaders,
    candidateThemes,
    coolingThemes,
    taxonomyThemes,
  });
  const modeLabel = conclusion.title;
  const modeDetail = conclusion.whyNotConclusion;
  const observationThemes = candidateThemes.length ? candidateThemes : taxonomyThemes;

  return {
    modeLabel,
    modeDetail,
    cards: [
      {
        key: 'confirmed',
        label: '轮动方向',
        value: themeNamesSummary(confirmedLeaders, '暂无确认信号'),
        detail: confirmedLeaders.length ? '当前信号较完整，继续观察走势分化。' : '信号待确认。',
        variant: confirmedLeaders.length ? 'success' : 'caution',
      },
      {
        key: 'candidate',
        label: taxonomyThemes.length && !candidateThemes.length ? '分类浏览' : '观察信号',
        value: themeNamesSummary(observationThemes, taxonomyThemes.length ? '暂无分类条目' : '暂无观察信号'),
        detail: observationThemes.length ? '信号待确认，先看板块强弱与走势分化。' : '部分数据延迟。',
        variant: observationThemes.length ? 'info' : 'neutral',
      },
      {
        key: 'cooling',
        label: '降温 / 分歧',
        value: themeNamesSummary(coolingThemes, '暂无降温主题'),
        detail: coolingThemes.length ? '走弱或分歧主题继续作为分化观察。' : '未见明显退潮列表。',
        variant: coolingThemes.length ? 'caution' : 'neutral',
      },
    ],
  };
}

const RotationVisualPanel: React.FC<{
  themes: MarketRotationTheme[];
  selectedThemeId?: string;
  marketLabelText: string;
  displayMode: RotationPrimaryDisplayMode;
  unavailableReason: string;
  unavailableDetail: string;
  onSelectTheme: (themeId: string) => void;
}> = ({ themes, selectedThemeId, marketLabelText, displayMode, unavailableReason, unavailableDetail, onSelectTheme }) => {
  const visualThemes = deriveVisualMatrixThemes(themes);
  const modeLabel = primaryDisplayLabel(displayMode);
  const modeDetail = primaryDisplayDetail(displayMode);

  if (!visualThemes.length) {
    return (
      <TerminalPanel data-testid="rotation-radar-visual-unavailable" className="overflow-hidden">
        <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className={cn('text-[10px] font-medium tracking-[0.22em]', ROTATION_PAPER_TEXT_MUTED_CLASS)}>相对强弱矩阵</p>
            <h3 className={cn('mt-2 text-lg font-semibold', ROTATION_PAPER_TEXT_PRIMARY_CLASS)}>矩阵暂不可用</h3>
            <p className={cn('mt-2 max-w-3xl text-sm leading-6', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>{unavailableReason}</p>
            <p className={cn('mt-2 text-[11px] leading-5', ROTATION_PAPER_TEXT_MUTED_CLASS)}>{unavailableDetail}</p>
          </div>
          <span className="shrink-0 rounded-md border border-[color:var(--wolfy-divider)] px-2.5 py-1 text-[11px] text-[color:var(--wolfy-text-muted)]">信号待确认</span>
        </div>
      </TerminalPanel>
    );
  }

  const domain = deriveVisualStrengthDomain(visualThemes);
  const rankingThemes = deriveTopThemes(visualThemes, 6);

  return (
    <TerminalPanel data-testid="rotation-radar-visual-matrix" className="overflow-hidden">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className={cn('text-[10px] font-medium tracking-[0.22em]', ROTATION_PAPER_TEXT_MUTED_CLASS)}>相对强弱矩阵</p>
          <h3 className={cn('mt-2 text-lg font-semibold', ROTATION_PAPER_TEXT_PRIMARY_CLASS)}>主题排行与阶段分布</h3>
          <p className={cn('mt-2 max-w-4xl text-sm leading-6', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>
            {modeDetail}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
          <span className="rounded-md border border-[color:var(--wolfy-divider)] px-2.5 py-1 text-[11px] text-[color:var(--wolfy-text-muted)]">{modeLabel}</span>
          <span className="rounded-md border border-[color:var(--wolfy-divider)] px-2.5 py-1 text-[11px] text-[color:var(--wolfy-text-muted)]">{marketLabelText}</span>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(22rem,0.9fr)]">
        <div className={cn('min-w-0 p-3', ROTATION_PAPER_PANEL_CLASS)}>
          <div className="flex min-w-0 items-center justify-between gap-3">
            <div className="min-w-0">
              <p className={cn('text-[11px] font-medium', ROTATION_PAPER_TEXT_MUTED_CLASS)}>矩阵视图</p>
              <p className={cn('mt-1 text-[11px] leading-5', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>
                横轴按主题相对基准的强弱变化，纵轴按当前阶段分层。
              </p>
            </div>
            <span className={cn('shrink-0 text-[10px]', ROTATION_PAPER_TEXT_MUTED_CLASS)}>
              {formatRelativeStrengthValue(domain.min)} - {formatRelativeStrengthValue(domain.max)}
            </span>
          </div>
          <div className="mt-4 overflow-x-auto no-scrollbar">
            <div className="min-w-[17.5rem] sm:min-w-[20rem]">
              {ROTATION_MATRIX_STAGE_ORDER.map((stageMeta) => {
                const stageThemes = visualThemes.filter((theme) => theme.stage === stageMeta.key);
                return (
                  <div key={stageMeta.key} className="grid grid-cols-[3.75rem_minmax(0,1fr)] items-stretch gap-2 border-t border-[color:var(--wolfy-divider)] py-2 first:border-t-0 first:pt-0 last:pb-0 sm:grid-cols-[4.5rem_minmax(0,1fr)] sm:gap-3">
                    <div className={cn('flex items-center text-[11px] font-medium', ROTATION_PAPER_TEXT_MUTED_CLASS)}>{stageMeta.label}</div>
                    <div className="relative h-12 rounded-lg border border-[color:var(--wolfy-divider)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-rail)_70%,transparent)]">
                      <div className="absolute inset-y-2 left-1/2 w-px bg-[color:var(--wolfy-divider)]" aria-hidden="true" />
                      {stageThemes.map((theme) => {
                        const strength = themeRelativeStrengthValue(theme);
                        const geometry = matrixGeometryPosition({
                          evidenceValue: strength,
                          domain,
                        });
                        const directionCue = observationDirectionCue(theme);
                        const strengthLabel = formatRelativeStrengthValue(geometry.evidenceValue);
                        const bubbleVariant = selectedThemeId === theme.id
                          ? 'border-[color:color-mix(in_srgb,var(--wolfy-accent)_36%,transparent)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_12%,transparent)] text-[color:var(--wolfy-text-primary)]'
                          : 'border-[color:var(--wolfy-divider)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-console)_78%,transparent)] text-[color:var(--wolfy-text-secondary)] hover:bg-[color:color-mix(in_srgb,var(--wolfy-surface-console)_94%,transparent)]';
                        return (
                          <button
                            key={theme.id}
                            type="button"
                            data-testid={`rotation-radar-matrix-point-${theme.id}`}
                            data-geometry-fallback={geometry.usesGeometryFallback ? 'true' : 'false'}
                            className={cn(
                              'absolute top-1/2 inline-flex h-7 -translate-x-1/2 -translate-y-1/2 items-center gap-1 rounded-full border px-2 text-[10px] transition-colors',
                              bubbleVariant,
                            )}
                            style={{ left: `${geometry.leftPct}%` }}
                            onClick={() => onSelectTheme(theme.id)}
                            aria-label={`${theme.name} ${observationThemeSummary(theme) || formatThemeStage(theme.stage)} ${directionCue?.changeText || strengthLabel}`}
                          >
                            <span className="max-w-[5rem] truncate sm:max-w-[6.5rem]">{theme.name}</span>
                            <span className={ROTATION_PAPER_TEXT_MUTED_CLASS}>
                              {directionCue ? `${directionCue.indicator} ${strengthLabel}` : strengthLabel}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
              <div className={cn('mt-3 flex items-center justify-between px-[3.75rem] text-[10px] sm:px-[4.5rem]', ROTATION_PAPER_TEXT_MUTED_CLASS)}>
                <span>偏弱</span>
                <span>基准</span>
                <span>偏强</span>
              </div>
            </div>
          </div>
        </div>

        <div className={cn('min-w-0 p-3', ROTATION_PAPER_PANEL_CLASS)}>
          <div className="flex min-w-0 items-center justify-between gap-3">
            <div className="min-w-0">
              <p className={cn('text-[11px] font-medium', ROTATION_PAPER_TEXT_MUTED_CLASS)}>主题排行</p>
              <p className={cn('mt-1 text-[11px] leading-5', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>
                沿用现有排序字段，仅把头部主题转换为条带视图。
              </p>
            </div>
            <TerminalChip variant="neutral">Top {rankingThemes.length}</TerminalChip>
          </div>
          <div className="mt-4 space-y-2">
            {rankingThemes.map((theme, index) => {
              const geometryWidth = scoreBarGeometryWidth(theme.rotationScore);
              const scoreLabel = formatRotationScore(theme.rotationScore);
              const observationSummary = observationThemeSummary(theme);
              const selected = selectedThemeId === theme.id;
              return (
                <button
                  key={theme.id}
                  type="button"
                  data-testid={`rotation-radar-ranking-bar-${theme.id}`}
                  data-score-available={geometryWidth !== null ? 'true' : 'false'}
                  className={cn(
                    'block w-full rounded-lg border border-[color:var(--wolfy-divider)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-console)_82%,transparent)] p-2 text-left transition-colors',
                    selected ? 'bg-[color:color-mix(in_srgb,var(--wolfy-accent)_12%,transparent)]' : 'hover:bg-[color:color-mix(in_srgb,var(--wolfy-surface-console)_96%,transparent)]',
                  )}
                  onClick={() => onSelectTheme(theme.id)}
                >
                  <div className="flex min-w-0 items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex min-w-0 items-center gap-2">
                        <span className={cn('text-[10px] font-medium', ROTATION_PAPER_TEXT_MUTED_CLASS)}>{String(index + 1).padStart(2, '0')}</span>
                        <span className={cn('truncate text-sm font-semibold', ROTATION_PAPER_TEXT_PRIMARY_CLASS)}>{theme.name}</span>
                      </div>
                      <p className={cn('mt-1 truncate text-[10px]', ROTATION_PAPER_TEXT_MUTED_CLASS)}>
                        {observationSummary
                          ? `${observationSummary} · ${themeConfidenceSummary(theme)}`
                          : `${formatThemeStage(theme.stage)} · ${themeConfidenceSummary(theme)}`}
                      </p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className={cn('text-[11px] font-semibold', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>{scoreLabel}</p>
                      <p className={cn('text-[10px]', ROTATION_PAPER_TEXT_MUTED_CLASS)}>{formatRelativeStrengthValue(themeRelativeStrengthValue(theme))}</p>
                    </div>
                  </div>
                  <div className="mt-2 h-2 rounded-full bg-[color:var(--wolfy-divider)]">
                    {geometryWidth !== null ? (
                      <div
                        className={cn(
                          'h-full rounded-full',
                          selected ? 'bg-[color:var(--wolfy-accent)]' : 'bg-[color:color-mix(in_srgb,var(--wolfy-text-secondary)_78%,transparent)]',
                        )}
                        style={{ width: `${geometryWidth}%` }}
                      />
                    ) : (
                      <div
                        className="h-full w-2 rounded-full bg-[color:color-mix(in_srgb,var(--wolfy-text-muted)_35%,transparent)]"
                        data-testid={`rotation-radar-ranking-bar-unavailable-${theme.id}`}
                        aria-hidden="true"
                      />
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </TerminalPanel>
  );
};

const ConsumerDisclosure: React.FC<{
  testId: string;
  title: string;
  summary: string;
  defaultOpen?: boolean;
  className?: string;
  children: React.ReactNode;
}> = ({ testId, title, summary, defaultOpen = false, className, children }) => {
  const [open, setOpen] = useState(defaultOpen);

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

const ThemeCorrelationBreadthSnapshotPanel: React.FC<{
  snapshot?: MarketRotationThemeCorrelationBreadthSnapshot | null;
}> = ({ snapshot }) => {
  if (!hasThemeCorrelationBreadthSnapshot(snapshot)) {
    return null;
  }

  const participationLabel = formatSnapshotState(
    snapshot.participationState,
    THEME_PARTICIPATION_LABELS,
    '参与状态待补齐',
  );
  const leadershipLabel = formatSnapshotState(
    snapshot.leadershipConcentration?.state,
    THEME_LEADERSHIP_LABELS,
    '集中度待补齐',
  );
  const correlationLabel = formatSnapshotState(
    snapshot.correlationEvidence?.state,
    THEME_CORRELATION_LABELS,
    '同步证据待补齐',
  );
  const breadthLabel = formatSnapshotState(
    snapshot.breadthEvidence?.state,
    THEME_BREADTH_LABELS,
    '广度待补齐',
  );
  const staleLabels = formatSnapshotInputLabels(snapshot.staleInputs, '暂无延迟项');
  const missingLabels = formatSnapshotInputLabels(snapshot.missingInputs, '暂无缺口项');
  const boundaryLabels = formatSnapshotBoundaryLabels(snapshot.observationBoundary);
  const nextSteps = formatSnapshotNextSteps(snapshot.researchNextSteps);
  const topMembers = (snapshot.leadershipConcentration?.topMembers || [])
    .map((item) => sanitizeRotationText(item, '成员'))
    .filter(Boolean)
    .slice(0, 4);

  return (
    <ConsumerDisclosure
      testId="rotation-theme-correlation-breadth-snapshot"
      title="查看主题扩散快照"
      summary={snapshotSummary(snapshot)}
    >
      <div className="grid gap-3 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          <TerminalChip variant={snapshot.participationState === 'broad_group' ? 'success' : snapshot.participationState === 'insufficient_evidence' ? 'caution' : 'info'}>
            {participationLabel}
          </TerminalChip>
          <TerminalChip variant={snapshot.leadershipConcentration?.state === 'concentrated' ? 'caution' : 'neutral'}>
            {leadershipLabel}
          </TerminalChip>
          <TerminalChip variant={snapshot.correlationEvidence?.state === 'aligned' ? 'success' : 'neutral'}>
            {correlationLabel}
          </TerminalChip>
          <TerminalChip variant={snapshot.breadthEvidence?.state === 'broad' ? 'success' : 'neutral'}>
            {breadthLabel}
          </TerminalChip>
        </div>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-2.5 py-2">
            <p className="font-semibold text-[color:var(--wolfy-text-secondary)]">龙头集中度</p>
            <p className="mt-1">
              {leadershipLabel} · {formatSnapshotPercent(snapshot.leadershipConcentration?.percent)}
            </p>
            <p className="mt-1 text-[color:var(--wolfy-text-muted)]">
              广泛参与 {formatSnapshotPercent(snapshot.leadershipConcentration?.broadParticipationPercent)}
            </p>
            {topMembers.length ? (
              <p className="mt-1 text-[color:var(--wolfy-text-muted)]">代表成员：{topMembers.join('、')}</p>
            ) : null}
          </div>
          <div className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-2.5 py-2">
            <p className="font-semibold text-[color:var(--wolfy-text-secondary)]">同步相关</p>
            <p className="mt-1">
              成员同步 {formatSnapshotPercent(snapshot.correlationEvidence?.sameDirectionPercent)}
            </p>
            <p className="mt-1 text-[color:var(--wolfy-text-muted)]">
              均线同步 {formatSnapshotPercent(snapshot.correlationEvidence?.aboveVwapPercent)}
            </p>
            <p className="mt-1 text-[color:var(--wolfy-text-muted)]">
              持续性 {formatSnapshotPercent(snapshot.correlationEvidence?.persistencePercent)}
            </p>
          </div>
          <div className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-2.5 py-2">
            <p className="font-semibold text-[color:var(--wolfy-text-secondary)]">广度证据</p>
            <p className="mt-1">
              {formatSnapshotMemberCount(snapshot.breadthEvidence?.observedMembers, snapshot.breadthEvidence?.configuredMembers)}
            </p>
            <p className="mt-1 text-[color:var(--wolfy-text-muted)]">
              上涨广度 {formatSnapshotPercent(snapshot.breadthEvidence?.percentUp)}
            </p>
            <p className="mt-1 text-[color:var(--wolfy-text-muted)]">
              跑赢广度 {formatSnapshotPercent(snapshot.breadthEvidence?.percentOutperformingBenchmark)}
            </p>
          </div>
          <div className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-2.5 py-2">
            <p className="font-semibold text-[color:var(--wolfy-text-secondary)]">观察边界</p>
            <div className="mt-1 flex min-w-0 flex-wrap gap-1.5">
              {boundaryLabels.map((label) => <TerminalChip key={label}>{label}</TerminalChip>)}
            </div>
          </div>
        </div>

        <div className="grid gap-2">
          <div>
            <p className="font-semibold text-[color:var(--wolfy-text-secondary)]">数据更新</p>
            <p className="mt-1">{staleLabels.join('、')}</p>
          </div>
          <div>
            <p className="font-semibold text-[color:var(--wolfy-text-secondary)]">输入缺口</p>
            <p className="mt-1">{missingLabels.join('、')}</p>
          </div>
          <div>
            <p className="font-semibold text-[color:var(--wolfy-text-secondary)]">继续观察</p>
            <div className="mt-1 grid gap-1">
              {nextSteps.map((step, index) => (
                <p key={`snapshot-next-step-${index}`}>· {step}</p>
              ))}
            </div>
          </div>
        </div>
      </div>
    </ConsumerDisclosure>
  );
};

const RotationFamilyRow: React.FC<{ view: RotationFamilyView }> = ({ view }) => {
  const signal = view.item.themeFlowSignal;
  const stateLabel = formatThemeFlowState(signal?.themeFlowState);
  const summary = [
    stateLabel,
    `${Math.max(0, view.signalThemeCount)}/${Math.max(view.themeCount, 0)} 个有信号`,
    view.averageConfidence !== null ? `信号 ${formatThemeFlowConfidence(signal)}` : null,
    view.averageRotationScore !== null ? `均分 ${Math.round(view.averageRotationScore)}` : null,
  ].filter(Boolean).join(' · ');

  return (
    <ConsumerDisclosure
      testId={`rotation-family-rollup-row-${view.familyKey}`}
      title={view.familyName}
      summary={summary || '家族级观察'}
      className="bg-[var(--wolfy-surface-input)] px-3 py-2.5"
    >
      <div className="grid gap-3 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          <TerminalChip variant={themeFlowChipVariant(signal?.themeFlowState)}>
            {stateLabel}
          </TerminalChip>
          <TerminalChip variant={view.hasUsefulSignal ? 'info' : 'neutral'}>
            {view.hasUsefulSignal ? '优先观察' : '低信号'}
          </TerminalChip>
          {view.reasonLabels.map((label) => <TerminalChip key={`${view.familyKey}-${label}`}>{label}</TerminalChip>)}
        </div>
        <p>{view.preview}</p>
        <div className="grid gap-1 text-[10px] leading-5 text-[color:var(--wolfy-text-muted)]">
          {themeFlowEvidenceLines(signal).map((line, lineIndex) => (
            <p key={`${view.familyKey}-family-flow-evidence-${lineIndex}`}>{line}</p>
          ))}
        </div>
      </div>
    </ConsumerDisclosure>
  );
};

const RotationEvidenceBoundaryStrip: React.FC<{ payload: MarketRotationRadarResponse }> = ({ payload }) => {
  const view = buildMarketRotationEvidenceBoundaryView(payload);

  return (
    <div
      data-testid="rotation-evidence-boundary"
      className="mt-3 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-3 py-2.5"
    >
      <div className="flex min-w-0 flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-[color:var(--wolfy-text-muted)]">轮动证据边界</p>
          <p className="mt-1 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{view.label}</p>
          {view.note ? <p className="mt-1 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">{view.note}</p> : null}
        </div>
        <div className="flex min-w-0 flex-wrap gap-1.5 md:justify-end">
          <TerminalChip variant={view.variant}>{view.label}</TerminalChip>
          {view.chips.map((chip) => (
            <TerminalChip key={chip.key} variant={chip.variant}>{chip.label}</TerminalChip>
          ))}
        </div>
      </div>
      <p className="mt-2 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">{view.nextEvidence}</p>
    </div>
  );
};

const RotationGuidancePanel: React.FC<{ payload: MarketRotationRadarResponse }> = ({ payload }) => {
  const tiers = deriveRotationTiers(payload);
  const guidance = rotationGuidance(payload);
  const conclusion = deriveRotationConclusion(payload, tiers);
  const decisionSummary = buildRotationDecisionReadiness(payload);
  const alpacaReadiness = buildAlpacaQuoteAuthorityReadinessView(payload.alpacaQuoteAuthorityReadiness);
  const capitalSummary = deriveCapitalRotationSummary(payload);
  const primaryThemes = derivePrimaryDisplayThemes(payload, tiers);
  const selectedTheme = primaryThemes[0];
  const topThemeTitle = tiers.libraryMode
    ? '主题分类参考'
    : themeNamesSummary(primaryThemes, '观察资料不足');
  const surfaceState = decisionSummary.state === 'ready'
    ? '板块强弱可读'
    : decisionSummary.state === 'observe'
      ? '信号待确认'
      : '轮动方向待确认';
  const heroTitle = selectedTheme?.name || topThemeTitle;
  const heroSummary = selectedTheme
    ? sanitizeRotationText(
      selectedTheme.stageExplanation,
      decisionSummary.state === 'ready'
        ? `${selectedTheme.name} 当前信号较完整，继续观察节奏与回落风险。`
        : decisionSummary.state === 'observe'
          ? `${selectedTheme.name} 信号待确认`
          : `${selectedTheme.name} 数据待补`,
    )
    : guidance.detail;
  const heroCards = [
    {
      key: 'market',
      label: '当前市场',
      value: marketLabel(payload.market || 'US'),
      detail: tiers.libraryMode ? '当前以主题分类浏览为主。' : '当前市场下按主题与强弱变化组织内容。',
    },
    {
      key: 'signal',
      label: '轮动方向',
      value: selectedTheme ? themeConsumerStateLabel(selectedTheme) : surfaceState,
      detail: selectedTheme
        ? (selectedTheme.riskExplanations?.length ? '保留主要弱点与走势分化。' : '当前以主题强弱和阶段变化为主。')
        : '当前未发现可进入头部展示的确认主题。',
    },
    {
      key: 'confidence',
      label: '数据状态',
      value: selectedTheme
        ? mapDataStateLabel(selectedTheme)
        : '观察资料不足',
      detail: selectedTheme
        ? consumerFreshnessLabel(selectedTheme.freshness, selectedTheme.isFallback, isThemeStale(selectedTheme))
        : consumerFreshnessLabel(payload.freshness, payload.isFallback, payload.isStale),
    },
  ];
  const familyViews = buildRotationFamilyViews(payload);
  const spotlightFamilies = familyViews.filter((view) => !view.collapsedByDefault);
  const collapsedFamilies = familyViews.filter((view) => view.collapsedByDefault);

  return (
    <TerminalPanel
      data-testid="rotation-radar-guidance"
      className="relative overflow-hidden"
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[color:var(--wolfy-divider)] to-transparent" aria-hidden="true" />
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className={cn('text-[10px] font-medium tracking-[0.24em]', ROTATION_PAPER_TEXT_MUTED_CLASS)}>状态摘要</p>
          <h2
            data-testid="rotation-radar-hero-title"
            className={cn('mt-2 break-words text-base font-semibold leading-6 md:text-lg', ROTATION_PAPER_TEXT_PRIMARY_CLASS)}
          >
            板块强弱：{heroTitle}
          </h2>
          <p className={cn('mt-2 max-w-4xl text-sm leading-6', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>{heroSummary}</p>
        </div>
        <span className="shrink-0 rounded-md border border-[color:var(--wolfy-divider)] px-2.5 py-1 text-[11px] text-[color:var(--wolfy-text-muted)]">
          轮动方向：{surfaceState}
        </span>
      </div>

      <div data-testid="rotation-radar-summary-band" data-terminal-primitive="panel" className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-3">
        {heroCards.map((card) => (
          <div key={card.key} className={cn('p-3', ROTATION_PAPER_SOFT_PANEL_CLASS)}>
            <p className={cn('text-[11px] font-medium', ROTATION_PAPER_TEXT_MUTED_CLASS)}>{card.label}</p>
            <p className={cn('mt-2 break-words text-sm font-semibold leading-5', ROTATION_PAPER_TEXT_PRIMARY_CLASS)}>{card.value}</p>
            <p className={cn('mt-2 text-[11px] leading-5', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>{card.detail}</p>
          </div>
        ))}
      </div>

      <RotationEvidenceBoundaryStrip payload={payload} />

      <div
        data-testid="rotation-alpaca-quote-readiness"
        className={cn('mt-3 px-3 py-2.5', ROTATION_PAPER_SOFT_PANEL_CLASS)}
      >
        <div className="flex min-w-0 flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <p className={cn('text-[11px] font-medium', ROTATION_PAPER_TEXT_MUTED_CLASS)}>ETF 引用状态</p>
            <p className={cn('mt-1 text-sm font-semibold', ROTATION_PAPER_TEXT_PRIMARY_CLASS)}>{alpacaReadiness.label}</p>
            <p className={cn('mt-1 text-[11px] leading-5', ROTATION_PAPER_TEXT_MUTED_CLASS)}>{alpacaReadiness.detail}</p>
          </div>
          <div className="flex min-w-0 flex-wrap gap-1.5 md:justify-end">
            {alpacaReadiness.chips.map((chip) => (
              <TerminalChip key={chip.key} variant={chip.variant}>{chip.label}</TerminalChip>
            ))}
          </div>
        </div>
        {alpacaReadiness.summaryItems.length ? (
          <div className={cn('mt-3 flex min-w-0 flex-wrap gap-1.5 text-[11px] leading-5', ROTATION_PAPER_TEXT_MUTED_CLASS)}>
            {alpacaReadiness.summaryItems.map((item) => (
              <span key={item} className="rounded-md border border-[color:var(--wolfy-divider)] bg-[color:color-mix(in_srgb,var(--wolfy-surface-console)_78%,transparent)] px-2 py-0.5">
                {item}
              </span>
            ))}
          </div>
        ) : null}
        {alpacaReadiness.familyRows.length ? (
          <div className="mt-3 grid gap-2 lg:grid-cols-3">
            {alpacaReadiness.familyRows.map((family) => (
              <div key={family.key} className={cn('min-w-0 p-2', ROTATION_PAPER_PANEL_CLASS)}>
                <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                  <p className={cn('text-[11px] font-medium', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>{family.label}</p>
                  <TerminalChip variant={family.variant}>{family.statusLabel}</TerminalChip>
                </div>
                <p className={cn('mt-1 text-[11px] leading-5', ROTATION_PAPER_TEXT_MUTED_CLASS)}>{family.countsLabel}</p>
                <p className={cn('text-[11px] leading-5', ROTATION_PAPER_TEXT_MUTED_CLASS)}>{family.scoringLabel}</p>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      {familyViews.length ? (
        <div
          data-testid="rotation-family-flow-rollup"
          className={cn('mt-4 px-3 py-3', ROTATION_PAPER_PANEL_CLASS)}
        >
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className={cn('text-[11px] font-medium', ROTATION_PAPER_TEXT_MUTED_CLASS)}>家族流向观察</p>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              <span className="rounded-md border border-[color:var(--wolfy-divider)] px-2.5 py-1 text-[11px] text-[color:var(--wolfy-text-muted)]">摘要优先</span>
              <span className="rounded-md border border-[color:var(--wolfy-divider)] px-2.5 py-1 text-[11px] text-[color:var(--wolfy-text-muted)]">
                {spotlightFamilies.length} 个优先观察
              </span>
              {collapsedFamilies.length ? (
                <span className="rounded-md border border-[color:var(--wolfy-divider)] px-2.5 py-1 text-[11px] text-[color:var(--wolfy-text-muted)]">
                  {collapsedFamilies.length} 个默认折叠
                </span>
              ) : null}
            </div>
          </div>
          {spotlightFamilies.length ? (
            <div className="mt-3 max-h-72 overflow-y-auto no-scrollbar">
              <DenseRows>
                {spotlightFamilies.map((view) => (
                  <RotationFamilyRow key={view.familyKey} view={view} />
                ))}
              </DenseRows>
            </div>
          ) : (
            <div className={cn('mt-3 rounded-lg border border-dashed border-[color:var(--wolfy-divider)] px-3 py-3 text-[11px] leading-5', ROTATION_PAPER_TEXT_MUTED_CLASS)}>
              暂无优先展开家族
            </div>
          )}
          {collapsedFamilies.length ? (
            <ConsumerDisclosure
              testId="rotation-family-rollup-collapsed"
              title="查看低信号家族"
              summary={`${collapsedFamilies.length} 个默认折叠`}
              className="mt-3 bg-[var(--wolfy-surface-input)]"
            >
              <div className="grid gap-2">
                {collapsedFamilies.map((view) => (
                  <div
                    key={view.familyKey}
                    data-testid={`rotation-family-rollup-collapsed-row-${view.familyKey}`}
                    className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-3 py-2.5"
                  >
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <p className="min-w-0 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{view.familyName}</p>
                      <TerminalChip variant="neutral">{formatThemeFlowState(view.item.themeFlowSignal?.themeFlowState)}</TerminalChip>
                      <span className="text-[10px] text-[color:var(--wolfy-text-muted)]">{Math.max(0, view.signalThemeCount)}/{Math.max(view.themeCount, 0)} 个有信号</span>
                    </div>
                    <p className="mt-1 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">{view.preview}</p>
                  </div>
                ))}
              </div>
            </ConsumerDisclosure>
          ) : null}
        </div>
      ) : null}

      <ConsumerDisclosure
        testId="rotation-radar-mechanics-details"
        title="查看轮动说明"
        summary="默认折叠"
        className="mt-4 bg-[var(--wolfy-surface-input)]"
      >
        <div className="grid gap-3 text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
          <div>
            <p className="font-semibold text-[color:var(--wolfy-text-secondary)]">轮动方向说明</p>
            <p className="mt-1">{conclusion.whyNotConclusion}</p>
          </div>
          <div>
            <p className="font-semibold text-[color:var(--wolfy-text-secondary)]">默认可见范围</p>
            <p className="mt-1">{capitalSummary.cards.map((card) => `${card.label}：${card.value}`).join(' · ')}</p>
          </div>
          <div>
            <p className="font-semibold text-[color:var(--wolfy-text-secondary)]">继续观察</p>
            <p className="mt-1">{conclusion.missingEvidence.join('、')}</p>
          </div>
        </div>
      </ConsumerDisclosure>
    </TerminalPanel>
  );
};

const CommandBar: React.FC<{
  selectedMarket: string;
  supportedMarkets: string[];
  searchQuery: string;
  onMarketChange: (market: string) => void;
  onSearchChange: (value: string) => void;
  loading: boolean;
  freshness?: MarketRotationRadarResponse['freshness'];
  onRefresh: () => void;
}> = ({ selectedMarket, supportedMarkets, searchQuery, onMarketChange, onSearchChange, loading, freshness, onRefresh }) => (
  <WolfyCommandBar
    data-testid="rotation-radar-mode-controls"
    className="min-h-[104px] gap-y-2 sm:min-h-[88px] lg:min-h-11"
    leading={(
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <div className="inline-flex items-center gap-2 text-[10px] font-bold uppercase text-[color:var(--wolfy-text-muted)]">
          <SlidersHorizontal className="size-3.5 text-[color:var(--wolfy-text-muted)]" aria-hidden="true" />
          市场
        </div>
        <div className="flex min-w-0 gap-2 overflow-x-auto no-scrollbar">
          {MARKET_OPTIONS.reduce<React.ReactNode[]>((acc, market) => {
            if (!supportedMarkets.length || supportedMarkets.includes(market.id)) {
              acc.push(
                <TerminalButton
                  key={market.id}
                  type="button"
                  variant="compact"
                  data-testid={`rotation-market-tab-${market.id}`}
                  aria-pressed={selectedMarket === market.id}
                  className={cn(
                    'shrink-0',
                    selectedMarket === market.id
                      ? 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] text-[color:var(--wolfy-text-primary)] hover:bg-[var(--overlay-hover)] hover:text-[color:var(--wolfy-text-primary)]'
                      : 'text-[color:var(--wolfy-text-muted)] hover:border-[color:var(--wolfy-border-subtle)] hover:bg-[var(--wolfy-surface-rail)] hover:text-[color:var(--wolfy-text-secondary)]',
                  )}
                  onClick={() => onMarketChange(market.id)}
                >
                  {market.label}
                </TerminalButton>,
              );
            }
            return acc;
          }, [])}
        </div>
      </div>
    )}
    trailing={(
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <TerminalNestedBlock data-testid="rotation-radar-freshness" className="inline-flex items-center gap-2 px-3 py-2">
          <span className="text-[10px] font-bold uppercase text-[color:var(--wolfy-text-muted)]">更新时间</span>
          <DataFreshnessBadge freshness={freshness || 'fallback'} />
        </TerminalNestedBlock>
        <TerminalButton
          variant="compact"
          className="size-10 rounded-xl p-0 text-[color:var(--wolfy-text-muted)] disabled:cursor-wait disabled:text-[color:var(--wolfy-text-muted)]"
          onClick={onRefresh}
          disabled={loading}
          aria-label="刷新主题轮动雷达"
        >
          <RefreshCcw className={cn('size-4', loading ? 'animate-spin' : '')} aria-hidden="true" />
        </TerminalButton>
      </div>
    )}
  >
    <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-center lg:gap-2">
      <label className="relative min-w-0 flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[color:var(--wolfy-text-muted)]" aria-hidden="true" />
        <input
          className="h-10 w-full rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] py-2 pl-9 pr-3 text-sm text-[color:var(--wolfy-text-secondary)] outline-none transition-all placeholder:text-[color:var(--wolfy-text-muted)] focus:border-[color:var(--sage)] focus:bg-[var(--wolfy-surface-rail)]"
          value={searchQuery}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="搜索主题、英文名或成员"
          aria-label="搜索主题、英文名或成员"
        />
      </label>
      <div
        data-testid="rotation-taxonomy-mode-note"
        className="inline-flex min-h-8 shrink-0 items-center gap-2 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-2.5 text-[11px] text-[color:var(--wolfy-text-muted)]"
      >
        <div className="inline-flex items-center gap-2 text-[10px] font-bold uppercase text-[color:var(--wolfy-text-muted)]">
          <Gauge className="size-3.5 text-[color:var(--wolfy-text-muted)]" aria-hidden="true" />
          分类
        </div>
        <span>主题优先，行业/概念随结果展开</span>
      </div>
    </div>
  </WolfyCommandBar>
);

function themeConsumerStateLabel(theme: MarketRotationTheme): string {
  if (isTaxonomyOnlyTheme(theme)) {
    return '主题分类参考';
  }
  if (
    resolveSignalType(theme) === 'insufficient_evidence'
    || resolveEvidenceQuality(theme) === 'insufficient'
  ) {
    return '观察资料不足';
  }
  return formatThemeStage(theme.stage);
}

const LeaderRow: React.FC<{
  theme: MarketRotationTheme;
  marketLabelText: string;
  selected: boolean;
  onSelect: () => void;
}> = ({ theme, marketLabelText, selected, onSelect }) => {
  const listSummary = observationThemeSummary(theme) || consumerThemeSubtitle(theme);
  return (
    <button
      type="button"
      data-testid={`rotation-radar-leader-row-${theme.id}`}
      onClick={onSelect}
      className={cn(
        'grid w-full min-w-0 grid-cols-[minmax(0,1fr)_5.5rem_6.25rem] items-center gap-2 p-3 text-left transition-colors',
        selected ? 'bg-[var(--wolfy-surface-rail)]' : 'hover:bg-[var(--wolfy-surface-rail)]',
      )}
    >
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{theme.name}</span>
        <span className="mt-1 block truncate text-[11px] text-[color:var(--wolfy-text-muted)]">{listSummary}</span>
      </span>
      <span className="truncate text-right text-[11px] font-semibold text-[color:var(--wolfy-text-secondary)]">{themeConsumerStateLabel(theme)}</span>
      <span className="text-right">
        <span className="block truncate text-[11px] font-semibold text-[color:var(--wolfy-text-secondary)]">{themeConfidenceSummary(theme)}</span>
        <span className="block truncate text-[10px] text-[color:var(--wolfy-text-muted)]">{marketLabelText} · {mapDataStateLabel(theme)}</span>
      </span>
    </button>
  );
};

const CompactThemeRow: React.FC<{
  theme: MarketRotationTheme;
  marketLabelText: string;
  selected: boolean;
  onSelect: () => void;
}> = ({ theme, marketLabelText, selected, onSelect }) => {
  const listSummary = observationThemeSummary(theme) || consumerThemeSubtitle(theme);
  return (
    <button
      type="button"
      data-testid={`rotation-radar-universe-row-${theme.id}`}
      onClick={onSelect}
      className={cn(
        'grid w-full min-w-0 grid-cols-[minmax(0,1fr)_5.5rem_6.25rem] items-center gap-2 px-3 py-2.5 text-left text-xs transition-colors',
        selected ? 'bg-[var(--wolfy-surface-rail)]' : 'hover:bg-[var(--wolfy-surface-rail)]',
      )}
    >
      <span className="min-w-0">
        <span className="block truncate font-semibold text-[color:var(--wolfy-text-secondary)]">{theme.name}</span>
        <span className="block truncate text-[10px] text-[color:var(--wolfy-text-muted)]">{listSummary}</span>
      </span>
      <span className="truncate text-right text-[11px] text-[color:var(--wolfy-text-muted)]">{themeConsumerStateLabel(theme)}</span>
      <span className="text-right">
        <span className="block truncate text-[10px] font-semibold text-[color:var(--wolfy-text-secondary)]">{themeConfidenceSummary(theme)}</span>
        <span className="block truncate text-[10px] text-[color:var(--wolfy-text-muted)]">{marketLabelText} · {mapDataStateLabel(theme)}</span>
      </span>
    </button>
  );
};

const ThemeDetailPanel: React.FC<{
  theme?: MarketRotationTheme;
  marketLabelText: string;
  libraryMode: boolean;
}> = ({ theme, marketLabelText, libraryMode }) => {
  if (!theme) {
    return null;
  }

  const taxonomyOnly = isTaxonomyOnlyTheme(theme) || libraryMode;
  const dataWarning = Boolean(theme.isFallback || theme.freshness === 'fallback' || isThemeStale(theme));
  const observationState = observationStateLabel(theme);
  const directionCue = observationDirectionCue(theme);
  const evidenceNotes = sanitizeRotationNotes(theme.evidence);
  const riskExplanationNotes = sanitizeRotationNotes(theme.riskExplanations);
  const weaknessNotes = uniqueReadinessItems(
    [
      ...riskExplanationNotes,
      ...themeDataGaps(theme).map(formatGapLabel),
      taxonomyOnly ? '当前仍以分类与观察为主。' : '',
      dataWarning ? '数据延迟，先看节奏是否继续保持。' : '',
    ],
    3,
    taxonomyOnly ? '当前仍以分类与观察为主。' : '继续观察广度、量能与持续性是否继续同步。',
  );
  const supportNotes = uniqueReadinessItems(
    [
      ...evidenceNotes,
      sanitizeRotationText(theme.stageExplanation, ''),
      theme.persistenceEvidence?.label ? `${theme.persistenceEvidence.label}已纳入观察。` : '',
    ],
    3,
    taxonomyOnly ? '当前只保留分类与观察范围。' : '当前仅保留对用户有用的支持证据。',
  );
  const representativeItems = (theme.themeDetail?.representativeLabels || theme.representativeLabels || theme.membersConfigured || []).slice(0, 4);
  const nextWatch = theme.alertCandidates?.[0];
  const shortReason = sanitizeRotationText(
    theme.stageExplanation,
    taxonomyOnly
      ? `${theme.name} 当前仍是分类观察，等待更多行情覆盖后再确认强弱。`
      : observationState && directionCue
        ? `${observationState} · ${directionCue.label}，${directionCue.changeText}，当前仅作方向观察。`
      : dataWarning
        ? `${theme.name} 当前使用最近一次可用数据，仅供观察。`
        : `${theme.name} 当前以主题强弱与广度变化为主，适合继续观察。`,
  );
  const nextStep = nextWatch?.symbol
    ? `继续观察 ${nextWatch.symbol} 与 ${theme.name} 的延续性，先确认走势分化是否收敛。`
    : taxonomyOnly
      ? '等待新的多时窗行情后，再确认主题是否形成稳定强弱。'
      : '继续观察广度、量能与持续性变化，避免过早放大方向。';

  return (
    <ConsoleContextRail data-testid="rotation-theme-detail-panel" className="xl:sticky xl:top-4">
      <div className="min-w-0 px-1 py-3">
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="min-w-0">
            <p className={cn('text-[10px] font-bold uppercase', ROTATION_PAPER_TEXT_MUTED_CLASS)}>当前主题</p>
            <h2 className={cn('mt-1 truncate text-lg font-semibold', ROTATION_PAPER_TEXT_PRIMARY_CLASS)}>{theme.name}</h2>
            <p className={cn('mt-1 truncate text-[11px]', ROTATION_PAPER_TEXT_MUTED_CLASS)}>{consumerThemeSubtitle(theme)}</p>
          </div>
        </div>

        <div className="mt-3 flex min-w-0 flex-wrap items-center gap-1.5">
          <TerminalChip variant={taxonomyOnly ? 'neutral' : dataWarning ? 'caution' : 'info'}>{themeConsumerStateLabel(theme)}</TerminalChip>
          {observationState ? <TerminalChip variant="neutral">{observationState}</TerminalChip> : null}
          {directionCue ? <TerminalChip variant="info">{directionCue.label}</TerminalChip> : null}
          <TerminalChip variant="neutral">{marketLabelText}</TerminalChip>
          <TerminalChip variant={dataWarning ? 'caution' : 'success'}>{mapDataStateLabel(theme)}</TerminalChip>
        </div>
      </div>

      <div className="min-w-0 px-1 py-3">
        <p className={cn('text-[10px] font-bold uppercase', ROTATION_PAPER_TEXT_MUTED_CLASS)}>轮动方向</p>
        <TerminalNotice variant={taxonomyOnly ? 'info' : dataWarning ? 'caution' : 'neutral'} className={cn('mt-2 text-[12px] leading-5', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>
          {shortReason}
        </TerminalNotice>
        {directionCue ? (
          <p className={cn('mt-2 text-[11px] leading-5', ROTATION_PAPER_TEXT_MUTED_CLASS)}>
            方向线索：{directionCue.changeText}
          </p>
        ) : null}
      </div>

      <div className="min-w-0 px-1 py-3">
        <p className={cn('text-[10px] font-bold uppercase', ROTATION_PAPER_TEXT_MUTED_CLASS)}>走势分化</p>
        <div className={cn('mt-2 grid gap-1 text-[11px] leading-5', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>
          {weaknessNotes.map((item) => <p key={item}>· {item}</p>)}
        </div>
      </div>

      <div className="min-w-0 px-1 py-3">
        <p className={cn('text-[10px] font-bold uppercase', ROTATION_PAPER_TEXT_MUTED_CLASS)}>观察重点</p>
        <p className={cn('mt-2 text-[11px] leading-5', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>{nextStep}</p>
      </div>

      <div className="min-w-0 px-1 py-3">
        <p className={cn('text-[10px] font-bold uppercase', ROTATION_PAPER_TEXT_MUTED_CLASS)}>观察标的</p>
        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
          {representativeItems.length
            ? representativeItems.map((item) => <TerminalChip key={item}>{item}</TerminalChip>)
            : <TerminalChip>待补齐</TerminalChip>}
        </div>
      </div>

      {theme.themeFlowSignal ? (
        <div className="min-w-0 px-1 py-3">
          <ConsumerDisclosure
            testId="rotation-theme-flow-signal"
            title="查看主题流向观察"
            summary="家族摘要优先，主题级说明默认折叠"
          >
            <div className={cn('grid gap-3 text-[11px] leading-5', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>
              <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                <TerminalChip variant={themeFlowChipVariant(theme.themeFlowSignal.themeFlowState)}>
                  {formatThemeFlowState(theme.themeFlowSignal.themeFlowState)}
                </TerminalChip>
                <TerminalChip variant="neutral">信号 {formatThemeFlowConfidence(theme.themeFlowSignal)}</TerminalChip>
              </div>
              <div>
                <p className={cn('font-semibold', ROTATION_PAPER_TEXT_PRIMARY_CLASS)}>解释</p>
                <p className="mt-1">
                  {sanitizeRotationText(
                    theme.themeFlowSignal.explanation,
                    `${theme.name} 当前仅保留主题级观察说明。`,
                  )}
                </p>
              </div>
              <div>
                <p className={cn('font-semibold', ROTATION_PAPER_TEXT_PRIMARY_CLASS)}>支持证据</p>
                <div className="mt-1 grid gap-1">
                  {themeFlowEvidenceLines(theme.themeFlowSignal).map((line, lineIndex) => (
                    <p key={`${theme.id}-theme-flow-evidence-${lineIndex}`}>· {line}</p>
                  ))}
                </div>
              </div>
              {themeFlowReasonLabels(theme.themeFlowSignal).length ? (
                <div>
                  <p className="font-semibold text-[color:var(--wolfy-text-secondary)]">观察项</p>
                  <div className="mt-1 flex min-w-0 flex-wrap gap-1.5">
                    {themeFlowReasonLabels(theme.themeFlowSignal).map((label) => <TerminalChip key={`${theme.id}-${label}`}>{label}</TerminalChip>)}
                  </div>
                </div>
              ) : null}
            </div>
          </ConsumerDisclosure>
        </div>
      ) : null}

      {hasThemeCorrelationBreadthSnapshot(theme.themeCorrelationBreadthSnapshot) ? (
        <div className="min-w-0 px-1 py-3">
          <ThemeCorrelationBreadthSnapshotPanel snapshot={theme.themeCorrelationBreadthSnapshot} />
        </div>
      ) : null}

      <div className="min-w-0 px-1 py-3">
        <ConsumerDisclosure
          testId="rotation-theme-data-notes"
          title="查看数据说明"
          summary="支持证据与方法默认折叠"
        >
          <div className={cn('grid gap-3 text-[11px] leading-5', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>
            <div>
              <p className={cn('font-semibold', ROTATION_PAPER_TEXT_PRIMARY_CLASS)}>支持证据</p>
              <div className="mt-1 grid gap-1">
                {supportNotes.map((item) => <p key={item}>· {item}</p>)}
              </div>
            </div>
            <div>
              <p className={cn('font-semibold', ROTATION_PAPER_TEXT_PRIMARY_CLASS)}>方法口径</p>
              <p className="mt-1">
                {taxonomyOnly
                  ? '当前页面先保留分类、观察范围与后续跟踪方向，等待更多行情覆盖后再确认强弱。'
                  : '默认先展示板块强弱、轮动方向与数据更新，再把更深一层的支持证据与方法说明折叠起来。'}
              </p>
            </div>
          </div>
        </ConsumerDisclosure>
      </div>
    </ConsoleContextRail>
  );
};

const LoadingPanel: React.FC<{ showFallback: boolean; onRefresh: () => void }> = ({ showFallback, onRefresh }) => (
  <TerminalPanel as="section" role="status" aria-label="正在读取主题轮动 / 相对强弱雷达">
    <div className={cn('flex items-center gap-3', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>
      <RefreshCcw className="size-4 animate-spin" aria-hidden="true" />
      <span className="text-sm">正在读取主题轮动 / 相对强弱雷达...</span>
    </div>
    <div className={cn('mt-4 grid gap-3 text-sm', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>
      <p className="leading-6">正在整理主题强弱、轮动线索与最近更新时间。</p>
      <p className="leading-6">准备好后会自动显示当前市场、头部主题和观察重点。</p>
      <TerminalNotice variant="info" className={cn('text-[12px] leading-5', ROTATION_PAPER_TEXT_SECONDARY_CLASS)}>
        结果出来前不会补写临时轮动方向。
      </TerminalNotice>
    </div>
    {showFallback ? (
      <TerminalNestedBlock
        data-testid="rotation-radar-loading-fallback"
        className="mt-4 border-amber-300/20 bg-amber-300/[0.04] p-3 text-sm"
      >
        <div className="font-semibold text-amber-100">轮动数据暂未返回</div>
        <p className="mt-2 leading-5 text-[color:var(--wolfy-text-secondary)]">
          可稍后重试；当前不会补写临时轮动方向。
        </p>
        <TerminalButton
          variant="compact"
          className="mt-3 border-amber-200/25 text-amber-100 hover:border-amber-100/40 hover:text-amber-50"
          onClick={onRefresh}
        >
          <RefreshCcw className="size-3.5" aria-hidden="true" />
          重新读取
        </TerminalButton>
      </TerminalNestedBlock>
    ) : null}
  </TerminalPanel>
);

function createRotationRadarTimeoutError(): ParsedApiError {
  return createParsedApiError({
    title: '主题轮动暂时不可用',
    message: '页面未在预期时间内完成读取，当前无法判断轮动方向。请稍后刷新重试。',
    category: 'upstream_timeout',
  });
}

interface RadarPageState {
  payload: MarketRotationRadarResponse | null;
  loading: boolean;
  loadingRequestId: number;
  error: ParsedApiError | null;
  selectedMarket: string;
  selectedThemeId: string;
  searchQuery: string;
}

type RadarPageAction =
  | { type: 'loadStarted'; requestId: number }
  | { type: 'loadSucceeded'; payload: MarketRotationRadarResponse }
  | { type: 'loadFailed'; error: ParsedApiError }
  | { type: 'selectMarket'; market: string }
  | { type: 'selectTheme'; themeId: string }
  | { type: 'setSearchQuery'; searchQuery: string };

const initialRadarPageState: RadarPageState = {
  payload: null,
  loading: true,
  loadingRequestId: 0,
  error: null,
  selectedMarket: DEFAULT_MARKET,
  selectedThemeId: '',
  searchQuery: '',
};

function radarPageReducer(state: RadarPageState, action: RadarPageAction): RadarPageState {
  switch (action.type) {
    case 'loadStarted':
      return {
        ...state,
        payload: null,
        loading: true,
        loadingRequestId: action.requestId,
        error: null,
        selectedThemeId: '',
      };
    case 'loadSucceeded':
      return {
        ...state,
        payload: action.payload,
        loading: false,
        error: null,
        selectedThemeId: action.payload.themes[0]?.id || '',
        searchQuery: '',
      };
    case 'loadFailed':
      return {
        ...state,
        loading: false,
        error: action.error,
      };
    case 'selectMarket':
      return {
        ...state,
        selectedMarket: action.market,
      };
    case 'selectTheme':
      return {
        ...state,
        selectedThemeId: action.themeId,
      };
    case 'setSearchQuery':
      return {
        ...state,
        searchQuery: action.searchQuery,
      };
    default:
      return state;
  }
}

const MarketRotationRadarPage: React.FC = () => {
  const [state, dispatch] = useReducer(radarPageReducer, initialRadarPageState);
  const [showLoadingFallback, setShowLoadingFallback] = useState(false);
  const activeRequestIdRef = useRef(0);

  const loadRadar = async (market: string) => {
    const requestId = activeRequestIdRef.current + 1;
    activeRequestIdRef.current = requestId;
    dispatch({ type: 'loadStarted', requestId });
    let timeoutHandle: number | undefined;
    try {
      const payload = await Promise.race<MarketRotationRadarResponse>([
        marketRotationApi.getRotationRadar(market),
        new Promise<never>((_, reject) => {
          timeoutHandle = window.setTimeout(() => {
            reject(createRotationRadarTimeoutError());
          }, ROTATION_RADAR_ROUTE_TIMEOUT_MS);
        }),
      ]);
      if (requestId !== activeRequestIdRef.current) {
        return;
      }
      dispatch({ type: 'loadSucceeded', payload });
    } catch (nextError) {
      if (requestId !== activeRequestIdRef.current) {
        return;
      }
      const parsed = getParsedApiError(nextError);
      dispatch({
        type: 'loadFailed',
        error: parsed.title === '主题轮动暂时不可用'
          ? parsed
          : { ...parsed, title: '读取主题轮动雷达失败' },
      });
    } finally {
      if (timeoutHandle !== undefined) {
        window.clearTimeout(timeoutHandle);
      }
    }
  };

  useEffect(() => {
    queueMicrotask(() => {
      void loadRadar(DEFAULT_MARKET);
    });
    return () => {
      activeRequestIdRef.current += 1;
    };
  }, []);

  useEffect(() => {
    if (!state.loading || state.payload) {
      setShowLoadingFallback(false);
      return undefined;
    }
    setShowLoadingFallback(false);
    const fallbackHandle = window.setTimeout(() => {
      setShowLoadingFallback(true);
    }, ROTATION_RADAR_LOADING_FALLBACK_MS);
    return () => {
      window.clearTimeout(fallbackHandle);
    };
  }, [state.loading, state.loadingRequestId, state.payload]);

  const handleMarketChange = (market: string) => {
    if (market === state.selectedMarket) {
      return;
    }
    dispatch({ type: 'selectMarket', market });
    void loadRadar(market);
  };

  const handleRefresh = () => {
    void loadRadar(state.selectedMarket);
  };

  const rotationTiers = state.payload ? deriveRotationTiers(state.payload) : null;
  const displayMode = primaryDisplayMode(rotationTiers);
  const primaryThemes = state.payload && rotationTiers ? derivePrimaryDisplayThemes(state.payload, rotationTiers) : [];
  const filteredThemes = (state.payload?.themes || []).filter((theme) => matchesSearch(theme, state.searchQuery));
  const visualThemes = primaryThemes.length ? primaryThemes : filteredThemes;

  const primaryThemeById = new Map(primaryThemes.map((theme) => [theme.id, theme]));
  const selectedTheme = (state.selectedThemeId ? primaryThemeById.get(state.selectedThemeId) : undefined)
    || state.payload?.themes.find((theme) => theme.id === state.selectedThemeId)
    || primaryThemes[0]
    || state.payload?.themes[0];
  const libraryMode = rotationTiers?.libraryMode || false;
  const rotationConclusion = state.payload && rotationTiers ? deriveRotationConclusion(state.payload, rotationTiers) : null;
  const primaryTierLabel = primaryDisplayLabel(displayMode);
  const marketLabelText = marketLabel(state.payload?.market || state.selectedMarket);
  const visualUnavailableReason = rotationConclusion?.title || '矩阵暂不可用';
  const visualUnavailableDetail = libraryMode
    ? '当前仅有分类浏览条目，尚无可用于矩阵定位的相对强弱与阶段组合。'
    : rotationConclusion?.whyNotConclusion || '当前结构化强弱维度仍待确认，暂不展示矩阵。';

  return (
    <div
      data-testid="market-rotation-radar-page"
      data-bento-surface="true"
      className="bento-surface-root flex min-h-0 w-full min-w-0 flex-1 flex-col gap-6 overflow-y-auto no-scrollbar text-[color:var(--wolfy-text-primary)]"
      aria-busy={state.loading}
    >
      <ConsumerWorkspaceScope className="min-h-0 flex-1">
      <ConsumerWorkspacePageShell className="flex min-h-0 flex-1 flex-col gap-4 md:gap-6">
        <TerminalPanel as="section" dense className="relative shrink-0 overflow-hidden">
          <TerminalPageHeading
            eyebrow="主题轮动"
            title="主题轮动雷达"
          />
        </TerminalPanel>

        {state.error ? (
          <TerminalPanel as="section">
            <ApiErrorAlert
              error={state.error}
              actionLabel="重新读取"
              onAction={handleRefresh}
            />
          </TerminalPanel>
        ) : null}

        {state.loading && !state.payload ? (
          <LoadingPanel showFallback={showLoadingFallback} onRefresh={handleRefresh} />
        ) : null}

        {state.payload ? (
          <>
            <CommandBar
              selectedMarket={state.selectedMarket}
              supportedMarkets={state.payload.supportedMarkets || ['US', 'CN', 'HK', 'CRYPTO']}
              searchQuery={state.searchQuery}
              onMarketChange={handleMarketChange}
              onSearchChange={(searchQuery) => dispatch({ type: 'setSearchQuery', searchQuery })}
              loading={state.loading}
              freshness={state.payload.freshness}
              onRefresh={handleRefresh}
            />

            <RotationVisualPanel
              themes={visualThemes}
              selectedThemeId={selectedTheme?.id}
              marketLabelText={marketLabelText}
              displayMode={displayMode}
              unavailableReason={visualUnavailableReason}
              unavailableDetail={visualUnavailableDetail}
              onSelectTheme={(themeId) => dispatch({ type: 'selectTheme', themeId })}
            />

            <TerminalGrid className="gap-4" data-workbench-split="8:4">
              <section className="min-w-0 xl:col-span-8" aria-label={libraryMode ? '分类浏览与观察线索' : primaryTierLabel}>
                <DataWorkbenchFrame data-testid="rotation-radar-leader-list">
                  <div className="border-b border-[color:var(--wolfy-divider)] p-3">
                    <TerminalSectionHeader
                      eyebrow={primaryTierLabel}
                      title={primaryThemes.length
                        ? (libraryMode
                          ? `${primaryThemes.length} 个分类焦点`
                          : rotationTiers?.confirmedLeaders.length
                            ? `前 ${primaryThemes.length} 个确认信号`
                            : `前 ${primaryThemes.length} 个观察数据`)
                        : (rotationConclusion?.title || (libraryMode ? '暂无可展示主题' : '暂无头部排名'))}
                    />
                  </div>
                  {primaryThemes.length ? (
                    <DenseRows>
                      {primaryThemes.map((theme) => (
                        <LeaderRow
                          key={theme.id}
                          theme={theme}
                          marketLabelText={marketLabelText}
                          selected={selectedTheme?.id === theme.id}
                          onSelect={() => dispatch({ type: 'selectTheme', themeId: theme.id })}
                        />
                      ))}
                    </DenseRows>
                  ) : (
                    <div className="p-3">
                      <TerminalEmptyState
                        data-testid="rotation-radar-insufficient-empty"
                        className="min-h-[104px] items-start justify-start p-3 text-left text-sm text-[color:var(--wolfy-text-muted)]"
                      >
                        <span className="block font-semibold text-[color:var(--wolfy-text-primary)]">
                          {rotationConclusion?.title || '轮动方向待确认'}
                        </span>
                        <span className="mt-2 block leading-5">
                          {rotationConclusion?.detail || '轮动数据待确认'}
                        </span>
                        <span className="mt-3 block leading-5 text-[color:var(--wolfy-text-secondary)]">
                          {rotationConclusion?.nextStep || '切换市场对比或等待数据更新'}
                        </span>
                      </TerminalEmptyState>
                    </div>
                  )}
                </DataWorkbenchFrame>
              </section>

              <div className="min-w-0 xl:col-span-4">
                <ThemeDetailPanel
                  theme={selectedTheme}
                  marketLabelText={marketLabelText}
                  libraryMode={libraryMode}
                />
              </div>
            </TerminalGrid>

            <DataWorkbenchFrame data-testid="rotation-radar-universe-list">
              <div className="border-b border-[color:var(--wolfy-divider)] p-3">
                <TerminalSectionHeader
                  eyebrow="主题 / 分类"
                  title={libraryMode ? `${filteredThemes.length}/${state.payload.themes.length} 个分类条目` : `${filteredThemes.length}/${state.payload.themes.length} 个条目，先看主题再看信号。`}
                />
              </div>
              <div className="max-h-80 overflow-y-auto no-scrollbar">
                {filteredThemes.length ? (
                  <DenseRows>
                    {filteredThemes.map((theme) => (
                      <CompactThemeRow
                        key={theme.id}
                        theme={theme}
                        marketLabelText={marketLabelText}
                        selected={selectedTheme?.id === theme.id}
                        onSelect={() => dispatch({ type: 'selectTheme', themeId: theme.id })}
                      />
                    ))}
                  </DenseRows>
                ) : (
                  <div className="p-3">
                    <TerminalEmptyState className="min-h-[72px] justify-start text-sm text-[color:var(--wolfy-text-muted)]">没有匹配主题。</TerminalEmptyState>
                  </div>
                )}
              </div>
            </DataWorkbenchFrame>

            <RotationGuidancePanel payload={state.payload} />
          </>
        ) : null}
      </ConsumerWorkspacePageShell>
      </ConsumerWorkspaceScope>
    </div>
  );
};

export default MarketRotationRadarPage;
