import type React from 'react';
import { useEffect, useState } from 'react';
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
import { getParsedApiError, type ParsedApiError } from '../api/error';
import {
  marketRotationApi,
  type MarketRotationEvidenceQuality,
  type MarketRotationRadarResponse,
  type MarketRotationSignalType,
  type MarketRotationStage,
  type MarketRotationSummaryItem,
  type MarketRotationTheme,
} from '../api/marketRotation';
import { formatDateTime } from '../utils/format';
import { cn } from '../utils/cn';
import { decisionReadinessVariant, sanitizeMarketGuidanceCopy, type DecisionReadinessState, type DecisionReadinessSummary } from '../utils/marketIntelligenceGuidance';

const TOP_THEME_LIMIT = 10;
const DEFAULT_MARKET = 'US';
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
  true_flow_data_missing: '关键输入不足',
  flow_methodology_missing: '信号确认不足',
  source_authority_rejected: '信号确认不足',
  stale_quote_window: '最近数据不足',
  benchmark_proxy_missing: '对比样本不足',
  proxy_coverage_incomplete: '对比样本不足',
  taxonomy_only: '仅可分类浏览',
  missing_required_windows: '观察时窗不足',
  no_headline_theme: '可比较样本不足',
};

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
  return Boolean(theme?.staticThemeOnly || theme?.dataQuality === 'taxonomy_only');
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
  if (Number.isFinite(Number(theme.relativeStrength?.averageRelativeStrengthPercent))) {
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
  const normalized = String(raw).trim();
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

function consumerFreshnessLabel(freshness?: string | null, isFallback?: boolean, isStale?: boolean): string {
  if (isFallback || freshness === 'fallback' || isStale || freshness === 'stale') {
    return '已使用最近一次可用数据。';
  }
  if (freshness === 'delayed') {
    return '数据略有延迟。';
  }
  if (freshness === 'live') {
    return '数据已更新。';
  }
  return '数据更新中，稍后将自动刷新。';
}

function consumerConfidenceLabel(state: DecisionReadinessState): string {
  if (state === 'ready') {
    return '当前轮动信号置信度可用，仍需持续观察。';
  }
  if (state === 'observe') {
    return '当前信号置信度较低，仅供观察。';
  }
  return '当前轮动信号数据不足，暂不生成评分。';
}

function consumerSufficiencyLabel(state: DecisionReadinessState): string {
  if (state === 'ready') {
    return '信号充分性可用。';
  }
  if (state === 'observe') {
    return '部分轮动数据暂不可用。';
  }
  return '当前轮动信号数据不足，暂不生成评分。';
}

function consumerStatusLabel(state: DecisionReadinessState, payload: MarketRotationRadarResponse): string {
  if (!payload.themes.length) {
    return '信号不可用';
  }
  if (state === 'ready') {
    return payload.freshness === 'delayed' ? '信号延迟可用' : '信号可用';
  }
  if (state === 'observe') {
    return payload.isFallback || payload.isStale ? '信号延迟观察' : '信号部分可用';
  }
  if (isRotationLibraryMode(payload)) {
    return '信号不足';
  }
  if (payload.isFallback || payload.isStale) {
    return '信号延迟';
  }
  return payload.themes.length ? '信号不足' : '信号不可用';
}

function formatThemeStage(stage?: MarketRotationStage): string {
  return stage ? STAGE_LABELS[stage] || stage : '待识别';
}

function mapDataStateLabel(theme: DataStateFields): string {
  const candidate = theme as MarketRotationTheme;
  if (isTaxonomyOnlyTheme(candidate)) {
    return candidate.confidenceLabel || '待行情确认';
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
  return '缓存/部分';
}

function formatConfidenceValue(confidence?: number | null): string {
  if (!Number.isFinite(Number(confidence))) {
    return '待确认';
  }
  return `${Math.round(Number(confidence) * 100)}%`;
}

function themeConfidenceSummary(theme?: MarketRotationTheme): string {
  if (!theme) {
    return '待确认';
  }
  if (isTaxonomyOnlyTheme(theme)) {
    return '分类观察';
  }
  return `置信 ${formatConfidenceValue(theme.confidence)}`;
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
  const text = String(value || '').trim();
  if (!text) return fallback;
  if (isInternalRotationIssue(text)) {
    return '部分轮动数据暂不可用。';
  }
  const consumerText = text
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

function summaryTitle(items: MarketRotationSummaryItem[], fallback: string): string {
  return items.length ? items.map((item) => item.name).join(' / ') : fallback;
}

function deriveTopThemes(themes: MarketRotationTheme[], limit = TOP_THEME_LIMIT): MarketRotationTheme[] {
  return themes.slice()
    .sort((a, b) => {
      if (b.rotationScore !== a.rotationScore) {
        return b.rotationScore - a.rotationScore;
      }
      return b.confidence - a.confidence;
    })
    .slice(0, limit);
}

function resolveSummaryThemes(themes: MarketRotationTheme[], summaryItems: MarketRotationSummaryItem[]): MarketRotationTheme[] {
  const themeById = new Map(themes.map((theme) => [theme.id, theme]));
  return summaryItems
    .map((item) => themeById.get(item.id))
    .filter((theme): theme is MarketRotationTheme => Boolean(theme));
}

function deriveWeakeningThemes(themes: MarketRotationTheme[]): MarketRotationTheme[] {
  return [...themes]
    .filter((theme) => theme.stage === 'cooling_watch' || theme.stage === 'weak_or_no_signal' || theme.rotationScore < 50)
    .sort((a, b) => a.rotationScore - b.rotationScore)
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
  return {
    libraryMode: isRotationLibraryMode(payload),
    confirmedLeaders,
    candidateThemes: deriveTopThemes(themes.filter((theme) => isCandidateWatchTheme(theme, confirmedIds)), 3),
    coolingThemes: deriveWeakeningThemes(themes).filter((theme) => !isTaxonomyOnlyTheme(theme)).slice(0, 3),
    taxonomyThemes: themes.filter(isTaxonomyOnlyTheme).slice(0, 3),
  };
}

function derivePrimaryDisplayThemes(
  payload: MarketRotationRadarResponse,
  tiers = deriveRotationTiers(payload),
): MarketRotationTheme[] {
  if (tiers.libraryMode) {
    return resolveSummaryThemes(payload.themes || [], payload.summary.strongestThemes || []);
  }
  if (tiers.confirmedLeaders.length) {
    return tiers.confirmedLeaders;
  }
  if (tiers.candidateThemes.length) {
    return tiers.candidateThemes;
  }
  return resolveSummaryThemes(payload.themes || [], payload.summary.strongestThemes || []);
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
    tiers.confirmedLeaders.length ? '暂无关键限制，继续复核风险与新鲜度' : '确认信号、广度与观察时窗仍待补齐',
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
      title: '可判断',
      detail: '当前轮动信号较完整，可形成主题轮动方向的研究观察；仍需持续复核反证、风险与新鲜度。',
      whyNotConclusion: '当前已具备研究判断所需的核心证据，但页面仍只输出观察结论，不扩展为交易动作。',
      missingEvidence,
      nextStep: '继续观察退潮主题、风险标签与数据新鲜度；若反证增加，应降级为仅观察。',
      variant: 'success',
    };
  }

  if (state === 'observe') {
    return {
      state,
      title: '仅观察',
      detail: '已有候选线索，但确认度或广度仍不足，暂不能判断轮动方向。',
      whyNotConclusion: `${themeScope}主要依赖相对强弱、观察项或局部样本，尚不能证明扩散与连续性同时成立。`,
      missingEvidence,
      nextStep: '等待新的多时窗与成员广度快照；确认信号不足时保持观察。',
      variant: 'info',
    };
  }

  return {
    state,
    title: '当前无法判断轮动方向',
    detail: '当前证据不足，不能把主题、行业或概念列表解释为轮动方向。',
    whyNotConclusion: tiers.libraryMode || payload.themes.length === 0
      ? `${themeScope}，没有足够的可比较行情时窗、成员广度或确认信号。`
      : `${themeScope}缺少足够的新鲜行情、广度扩散和确认信号，不能形成方向结论。`,
    missingEvidence,
    nextStep: '数据更新中，稍后将自动刷新；若仍不足，等待新的多时窗快照再复核。',
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
      ? '当前轮动信号可用于研究观察，仍需结合风险与新鲜度复核。'
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
        label: '确认信号',
        value: themeNamesSummary(confirmedLeaders, '暂无确认信号'),
        detail: confirmedLeaders.length ? '当前信号较完整，仍仅作研究观察。' : '当前轮动信号数据不足，暂不生成评分。',
        variant: confirmedLeaders.length ? 'success' : 'caution',
      },
      {
        key: 'candidate',
        label: taxonomyThemes.length && !candidateThemes.length ? '分类浏览' : '观察信号',
        value: themeNamesSummary(observationThemes, taxonomyThemes.length ? '暂无分类条目' : '暂无观察信号'),
        detail: observationThemes.length ? '当前信号置信度较低，仅供观察。' : '部分轮动数据暂不可用。',
        variant: observationThemes.length ? 'info' : 'neutral',
      },
      {
        key: 'cooling',
        label: '降温 / 分歧',
        value: themeNamesSummary(coolingThemes, '暂无降温主题'),
        detail: coolingThemes.length ? '走弱或分歧主题继续作为反证观察。' : '未见明显退潮列表。',
        variant: coolingThemes.length ? 'caution' : 'neutral',
      },
    ],
  };
}

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

const RotationGuidancePanel: React.FC<{ payload: MarketRotationRadarResponse }> = ({ payload }) => {
  const tiers = deriveRotationTiers(payload);
  const guidance = rotationGuidance(payload);
  const conclusion = deriveRotationConclusion(payload, tiers);
  const decisionSummary = buildRotationDecisionReadiness(payload);
  const capitalSummary = deriveCapitalRotationSummary(payload);
  const primaryThemes = derivePrimaryDisplayThemes(payload, tiers);
  const selectedTheme = primaryThemes[0] || payload.themes[0];
  const topThemeTitle = tiers.libraryMode
    ? summaryTitle(payload.summary.strongestThemes, '按主题分类浏览')
    : themeNamesSummary(primaryThemes, '等待主题更新');
  const surfaceState = decisionSummary.state === 'ready'
    ? '正常'
    : decisionSummary.state === 'observe'
      ? '观察中'
      : '证据不足';
  const heroTitle = selectedTheme?.name || topThemeTitle;
  const heroSummary = selectedTheme
    ? sanitizeRotationText(
      selectedTheme.stageExplanation,
      decisionSummary.state === 'ready'
        ? `${selectedTheme.name} 当前信号较完整，继续观察节奏与回落风险。`
        : decisionSummary.state === 'observe'
          ? `${selectedTheme.name} 仍在观察阶段，先看持续性、广度与量能是否继续同步。`
          : `${selectedTheme.name} 当前证据不足，先保留分类与观察结论。`,
    )
    : guidance.detail;
  const heroCards = [
    {
      key: 'market',
      label: '当前市场',
      value: marketLabel(payload.market || 'US'),
      detail: tiers.libraryMode ? '当前以主题分类浏览为主。' : '当前市场下按主题与信号强弱组织内容。',
    },
    {
      key: 'signal',
      label: '当前信号',
      value: selectedTheme ? themeConsumerStateLabel(selectedTheme) : surfaceState,
      detail: selectedTheme
        ? (selectedTheme.riskExplanations?.length ? '已保留主要弱点与风险提示。' : '当前仅保留对用户有用的信号层结论。')
        : guidance.detail,
    },
    {
      key: 'confidence',
      label: '置信 / 更新',
      value: selectedTheme
        ? `${themeConfidenceSummary(selectedTheme)} · ${mapDataStateLabel(selectedTheme)}`
        : formatDateTime(payload.generatedAt) || '待确认',
      detail: selectedTheme
        ? consumerFreshnessLabel(selectedTheme.freshness, selectedTheme.isFallback, isThemeStale(selectedTheme))
        : consumerFreshnessLabel(payload.freshness, payload.isFallback, payload.isStale),
    },
  ];

  return (
    <TerminalPanel
      data-testid="rotation-radar-guidance"
      className="relative overflow-hidden"
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/0 via-cyan-200/42 to-sky-400/0" aria-hidden="true" />
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-medium tracking-[0.24em] text-white/38">轮动状态</p>
          <p className="mt-2 text-base font-semibold leading-6 text-white/90 md:text-lg">{surfaceState}</p>
          <h2 className="mt-3 break-words text-xl font-semibold leading-7 text-white md:text-2xl">{heroTitle}</h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-white/58">{heroSummary}</p>
        </div>
        <div className="flex min-w-0 flex-wrap gap-2 lg:justify-end">
          <TerminalChip variant={decisionSummary.state === 'ready' ? 'success' : decisionSummary.state === 'observe' ? 'info' : 'caution'}>
            {surfaceState}
          </TerminalChip>
          <TerminalChip variant="neutral">{marketLabel(payload.market || 'US')}</TerminalChip>
          <TerminalChip variant={payload.isFallback || payload.isStale ? 'caution' : payload.freshness === 'delayed' ? 'info' : 'success'}>
            {consumerFreshnessLabel(payload.freshness, payload.isFallback, payload.isStale).replace('。', '')}
          </TerminalChip>
        </div>
      </div>

      <div data-testid="rotation-radar-summary-band" data-terminal-primitive="panel" className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-3">
        {heroCards.map((card) => (
          <div key={card.key} className="rounded-lg border border-white/[0.06] bg-black/10 p-3">
            <p className="text-[11px] font-medium text-white/48">{card.label}</p>
            <p className="mt-2 break-words text-sm font-semibold leading-5 text-white/84">{card.value}</p>
            <p className="mt-2 text-[11px] leading-5 text-white/58">{card.detail}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 rounded-lg border border-white/[0.06] bg-black/10 p-3">
        <p className="text-[11px] font-medium text-white/48">下一步</p>
        <p className="mt-2 text-[11px] leading-5 text-white/60">{conclusion.nextStep}</p>
      </div>

      <ConsumerDisclosure
        testId="rotation-radar-mechanics-details"
        title="查看轮动说明"
        summary="默认折叠"
        className="mt-4 bg-black/10"
      >
        <div className="grid gap-3 text-[11px] leading-5 text-white/56">
          <div>
            <p className="font-semibold text-white/74">当前状态说明</p>
            <p className="mt-1">{conclusion.whyNotConclusion}</p>
          </div>
          <div>
            <p className="font-semibold text-white/74">默认可见范围</p>
            <p className="mt-1">{capitalSummary.cards.map((card) => `${card.label}：${card.value}`).join(' · ')}</p>
          </div>
          <div>
            <p className="font-semibold text-white/74">继续观察</p>
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
        <div className="inline-flex items-center gap-2 text-[10px] font-bold uppercase text-white/35">
          <SlidersHorizontal className="size-3.5 text-cyan-200/70" aria-hidden="true" />
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
                      ? 'border-cyan-200/24 bg-cyan-200/[0.08] text-cyan-50 hover:bg-cyan-200/[0.1] hover:text-cyan-50'
                      : 'text-white/48 hover:border-white/10 hover:bg-white/[0.04] hover:text-white/75',
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
          <span className="text-[10px] font-bold uppercase text-white/35">新鲜度</span>
          <DataFreshnessBadge freshness={freshness || 'fallback'} />
        </TerminalNestedBlock>
        <TerminalButton
          variant="compact"
          className="size-10 rounded-xl p-0 text-white/50 disabled:cursor-wait disabled:text-white/30"
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
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-white/35" aria-hidden="true" />
        <input
          className="h-10 w-full rounded-lg border border-white/10 bg-black/25 py-2 pl-9 pr-3 text-sm text-white/78 outline-none transition-all placeholder:text-white/30 focus:border-cyan-200/30 focus:bg-white/[0.035]"
          value={searchQuery}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="搜索主题、英文名或成员"
          aria-label="搜索主题、英文名或成员"
        />
      </label>
      <div
        data-testid="rotation-taxonomy-mode-note"
        className="inline-flex min-h-8 shrink-0 items-center gap-2 rounded-md border border-white/[0.06] bg-white/[0.025] px-2.5 text-[11px] text-white/46"
      >
        <div className="inline-flex items-center gap-2 text-[10px] font-bold uppercase text-white/35">
          <Gauge className="size-3.5 text-cyan-200/70" aria-hidden="true" />
          分类
        </div>
        <span>主题优先，行业/概念随结果展开</span>
      </div>
    </div>
  </WolfyCommandBar>
);

function themeConsumerStateLabel(theme: MarketRotationTheme): string {
  if (isTaxonomyOnlyTheme(theme)) {
    return '分类浏览';
  }
  return formatThemeStage(theme.stage);
}

const LeaderRow: React.FC<{
  theme: MarketRotationTheme;
  marketLabelText: string;
  selected: boolean;
  onSelect: () => void;
}> = ({ theme, marketLabelText, selected, onSelect }) => (
  <button
    type="button"
    data-testid={`rotation-radar-leader-row-${theme.id}`}
    onClick={onSelect}
    className={cn(
      'grid w-full min-w-0 grid-cols-[minmax(0,1fr)_5.5rem_6.25rem] items-center gap-2 p-3 text-left transition-colors',
      selected ? 'bg-cyan-200/[0.06]' : 'hover:bg-white/[0.025]',
    )}
  >
    <span className="min-w-0">
      <span className="block truncate text-sm font-semibold text-white/84">{theme.name}</span>
      <span className="mt-1 block truncate text-[11px] text-white/38">{consumerThemeSubtitle(theme)}</span>
    </span>
    <span className="truncate text-right text-[11px] font-semibold text-white/62">{themeConsumerStateLabel(theme)}</span>
    <span className="text-right">
      <span className="block truncate text-[11px] font-semibold text-white/70">{themeConfidenceSummary(theme)}</span>
      <span className="block truncate text-[10px] text-white/38">{marketLabelText} · {mapDataStateLabel(theme)}</span>
    </span>
  </button>
);

const CompactThemeRow: React.FC<{
  theme: MarketRotationTheme;
  marketLabelText: string;
  selected: boolean;
  onSelect: () => void;
}> = ({ theme, marketLabelText, selected, onSelect }) => (
  <button
    type="button"
    data-testid={`rotation-radar-universe-row-${theme.id}`}
    onClick={onSelect}
    className={cn(
      'grid w-full min-w-0 grid-cols-[minmax(0,1fr)_5.5rem_6.25rem] items-center gap-2 px-3 py-2.5 text-left text-xs transition-colors',
      selected ? 'bg-cyan-200/[0.06]' : 'hover:bg-white/[0.025]',
    )}
  >
    <span className="min-w-0">
      <span className="block truncate font-semibold text-white/76">{theme.name}</span>
      <span className="block truncate text-[10px] text-white/35">{consumerThemeSubtitle(theme)}</span>
    </span>
    <span className="truncate text-right text-[11px] text-white/58">{themeConsumerStateLabel(theme)}</span>
    <span className="text-right">
      <span className="block truncate text-[10px] font-semibold text-white/62">{themeConfidenceSummary(theme)}</span>
      <span className="block truncate text-[10px] text-white/35">{marketLabelText} · {mapDataStateLabel(theme)}</span>
    </span>
  </button>
);

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
  const evidenceNotes = sanitizeRotationNotes(theme.evidence);
  const riskExplanationNotes = sanitizeRotationNotes(theme.riskExplanations);
  const weaknessNotes = uniqueReadinessItems(
    [
      ...riskExplanationNotes,
      ...themeDataGaps(theme).map(formatGapLabel),
      taxonomyOnly ? '当前仍以分类与观察为主。' : '',
      dataWarning ? '当前数据略有延迟，先看节奏是否继续保持。' : '',
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
      : dataWarning
        ? `${theme.name} 当前使用最近一次可用数据，仅供观察。`
        : `${theme.name} 当前以主题强弱与广度变化为主，适合继续观察。`,
  );
  const nextStep = nextWatch?.symbol
    ? `继续观察 ${nextWatch.symbol} 与 ${theme.name} 的延续性，再决定是否升级判断。`
    : taxonomyOnly
      ? '等待新的多时窗行情后，再确认主题是否形成稳定强弱。'
      : '继续观察广度、量能与持续性变化，避免过早放大结论。';

  return (
    <ConsoleContextRail data-testid="rotation-theme-detail-panel" className="xl:sticky xl:top-4">
      <div className="min-w-0 px-1 py-3">
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase text-white/35">当前主题</p>
            <h2 className="mt-1 truncate text-lg font-semibold text-white">{theme.name}</h2>
            <p className="mt-1 truncate text-[11px] text-white/38">{consumerThemeSubtitle(theme)}</p>
          </div>
        </div>

        <div className="mt-3 flex min-w-0 flex-wrap items-center gap-1.5">
          <TerminalChip variant={taxonomyOnly ? 'neutral' : dataWarning ? 'caution' : 'info'}>{themeConsumerStateLabel(theme)}</TerminalChip>
          <TerminalChip variant="neutral">{marketLabelText}</TerminalChip>
          <TerminalChip variant={taxonomyOnly ? 'neutral' : theme.confidence != null && theme.confidence >= 0.65 ? 'success' : 'info'}>
            {themeConfidenceSummary(theme)}
          </TerminalChip>
          <TerminalChip variant={dataWarning ? 'caution' : 'success'}>{mapDataStateLabel(theme)}</TerminalChip>
          {!taxonomyOnly ? <DataFreshnessBadge freshness={theme.freshness} className="px-1.5 text-[9px]" /> : null}
        </div>
      </div>

      <div className="min-w-0 px-1 py-3">
        <p className="text-[10px] font-bold uppercase text-white/35">当前结论</p>
        <TerminalNotice variant={taxonomyOnly ? 'info' : dataWarning ? 'caution' : 'neutral'} className="mt-2 text-[12px] leading-5 text-white/58">
          {shortReason}
        </TerminalNotice>
      </div>

      <div className="min-w-0 px-1 py-3">
        <p className="text-[10px] font-bold uppercase text-white/35">风险 / 弱点</p>
        <div className="mt-2 grid gap-1 text-[11px] leading-5 text-white/58">
          {weaknessNotes.map((item) => <p key={item}>· {item}</p>)}
        </div>
      </div>

      <div className="min-w-0 px-1 py-3">
        <p className="text-[10px] font-bold uppercase text-white/35">下一步</p>
        <p className="mt-2 text-[11px] leading-5 text-white/58">{nextStep}</p>
      </div>

      <div className="min-w-0 px-1 py-3">
        <p className="text-[10px] font-bold uppercase text-white/35">观察标的</p>
        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
          {representativeItems.length
            ? representativeItems.map((item) => <TerminalChip key={item}>{item}</TerminalChip>)
            : <TerminalChip>待补齐</TerminalChip>}
        </div>
      </div>

      <div className="min-w-0 px-1 py-3">
        <ConsumerDisclosure
          testId="rotation-theme-data-notes"
          title="查看数据说明"
          summary="支持证据与方法默认折叠"
        >
          <div className="grid gap-3 text-[11px] leading-5 text-white/56">
            <div>
              <p className="font-semibold text-white/74">支持证据</p>
              <div className="mt-1 grid gap-1">
                {supportNotes.map((item) => <p key={item}>· {item}</p>)}
              </div>
            </div>
            <div>
              <p className="font-semibold text-white/74">方法口径</p>
              <p className="mt-1">
                {taxonomyOnly
                  ? '当前页面先保留分类、观察范围与后续跟踪方向，等待更多行情覆盖后再确认强弱。'
                  : '默认先展示主题、当前信号、置信与新鲜度，再把更深一层的支持证据与方法说明折叠起来。'}
              </p>
            </div>
          </div>
        </ConsumerDisclosure>
      </div>
    </ConsoleContextRail>
  );
};

const LoadingPanel: React.FC = () => (
  <TerminalPanel as="section" role="status" aria-label="正在读取主题轮动 / 相对强弱雷达">
    <div className="flex items-center gap-3 text-white/60">
      <RefreshCcw className="size-4 animate-spin" aria-hidden="true" />
      <span className="text-sm">正在读取主题轮动 / 相对强弱雷达...</span>
    </div>
  </TerminalPanel>
);

const MarketRotationRadarPage: React.FC = () => {
  const [payload, setPayload] = useState<MarketRotationRadarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [selectedMarket, setSelectedMarket] = useState(DEFAULT_MARKET);
  const [selectedThemeId, setSelectedThemeId] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');

  const loadRadar = async (market: string) => {
    setLoading(true);
    setError(null);
    try {
      const nextPayload = await marketRotationApi.getRotationRadar(market);
      setPayload(nextPayload);
      setSelectedThemeId(nextPayload.themes[0]?.id || '');
      setSearchQuery('');
    } catch (nextError) {
      setError({ ...getParsedApiError(nextError), title: '读取主题轮动雷达失败' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadRadar(DEFAULT_MARKET);
  }, []);

  const handleMarketChange = (market: string) => {
    if (market === selectedMarket) {
      return;
    }
    setSelectedMarket(market);
    void loadRadar(market);
  };

  const handleRefresh = () => {
    void loadRadar(selectedMarket);
  };

  const rotationTiers = payload ? deriveRotationTiers(payload) : null;
  const headlineThemes = payload && rotationTiers ? derivePrimaryDisplayThemes(payload, rotationTiers) : [];
  const filteredThemes = (payload?.themes || []).filter((theme) => matchesSearch(theme, searchQuery));

  const selectedTheme = payload?.themes.find((theme) => theme.id === selectedThemeId) || payload?.themes[0];
  const libraryMode = rotationTiers?.libraryMode || false;
  const rotationConclusion = payload && rotationTiers ? deriveRotationConclusion(payload, rotationTiers) : null;
  const primaryTierLabel = libraryMode ? '分类浏览' : rotationTiers?.confirmedLeaders.length ? '确认信号' : '观察信号';
  const marketLabelText = marketLabel(payload?.market || selectedMarket);

  return (
    <div
      data-testid="market-rotation-radar-page"
      data-bento-surface="true"
      className="bento-surface-root flex min-h-0 w-full min-w-0 flex-1 flex-col gap-6 overflow-y-auto overflow-x-hidden no-scrollbar text-white"
    >
      <ConsumerWorkspaceScope className="min-h-0 flex-1">
      <ConsumerWorkspacePageShell className="flex min-h-0 flex-1">
        <TerminalPanel as="section" dense className="relative shrink-0 overflow-hidden">
          <TerminalPageHeading
            eyebrow="主题轮动"
            title="主题轮动雷达"
          />
        </TerminalPanel>

        {error ? (
          <TerminalPanel as="section">
            <ApiErrorAlert error={error} />
          </TerminalPanel>
        ) : null}

        {loading && !payload ? <LoadingPanel /> : null}

        {payload ? (
          <>
            <CommandBar
              selectedMarket={selectedMarket}
              supportedMarkets={payload.supportedMarkets || ['US', 'CN', 'HK', 'CRYPTO']}
              searchQuery={searchQuery}
              onMarketChange={handleMarketChange}
              onSearchChange={setSearchQuery}
              loading={loading}
              freshness={payload.freshness}
              onRefresh={handleRefresh}
            />

            <RotationGuidancePanel payload={payload} />

            <TerminalGrid className="gap-4" data-workbench-split="8:4">
              <section className="min-w-0 space-y-4 xl:col-span-8" aria-label={libraryMode ? '分类浏览与观察线索' : primaryTierLabel}>
                <DataWorkbenchFrame data-testid="rotation-radar-universe-list">
                  <div className="border-b border-white/[0.05] p-3">
                    <TerminalSectionHeader
                      eyebrow="主题 / 分类"
                      title={libraryMode ? `${filteredThemes.length}/${payload.themes.length} 个分类条目` : `${filteredThemes.length}/${payload.themes.length} 个条目，先看主题再看信号。`}
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
                            onSelect={() => setSelectedThemeId(theme.id)}
                          />
                        ))}
                      </DenseRows>
                    ) : (
                      <div className="p-3">
                        <TerminalEmptyState className="min-h-[72px] justify-start text-sm text-white/42">没有匹配主题。</TerminalEmptyState>
                      </div>
                    )}
                  </div>
                </DataWorkbenchFrame>

                <DataWorkbenchFrame data-testid="rotation-radar-leader-list">
                  <div className="border-b border-white/[0.05] p-3">
                    <TerminalSectionHeader
                      eyebrow={primaryTierLabel}
                      title={headlineThemes.length
                        ? (libraryMode
                          ? `${headlineThemes.length} 个分类焦点`
                          : rotationTiers?.confirmedLeaders.length
                            ? `前 ${headlineThemes.length} 个确认信号`
                            : `前 ${headlineThemes.length} 个观察信号`)
                        : (rotationConclusion?.title || (libraryMode ? '暂无可展示主题' : '暂无头部排名'))}
                    />
                  </div>
                  {headlineThemes.length ? (
                    <DenseRows>
                      {headlineThemes.map((theme) => (
                        <LeaderRow
                          key={theme.id}
                          theme={theme}
                          marketLabelText={marketLabelText}
                          selected={selectedTheme?.id === theme.id}
                          onSelect={() => setSelectedThemeId(theme.id)}
                        />
                      ))}
                    </DenseRows>
                  ) : (
                    <div className="p-3">
                      <TerminalEmptyState
                        data-testid="rotation-radar-insufficient-empty"
                        className="min-h-[104px] items-start justify-start p-3 text-left text-sm text-white/52"
                      >
                        <span className="block font-semibold text-white/82">
                          {rotationConclusion?.title || '当前无法判断轮动方向'}
                        </span>
                        <span className="mt-2 block leading-5">
                          {rotationConclusion?.whyNotConclusion || '当前轮动信号数据不足，暂不生成评分。'}
                        </span>
                        <span className="mt-3 block leading-5 text-white/60">
                          {rotationConclusion?.nextStep || '等待新的多时窗行情和成员广度快照后再复核。'}
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
          </>
        ) : null}
      </ConsumerWorkspacePageShell>
      </ConsumerWorkspaceScope>
    </div>
  );
};

export default MarketRotationRadarPage;
