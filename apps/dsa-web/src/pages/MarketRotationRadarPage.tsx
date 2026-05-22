import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Gauge, RefreshCcw, Search, Signal, SlidersHorizontal, Waves } from 'lucide-react';
import { ApiErrorAlert } from '../components/common';
import { EvidenceChips } from '../components/evidence/EvidenceChips';
import {
  ConsoleContextRail,
  DataWorkbenchFrame,
  DenseRows,
  WolfyCommandBar,
} from '../components/linear';
import { DataFreshnessBadge } from '../components/market-overview/marketOverviewPrimitives';
import {
  TerminalButton,
  TerminalChip,
  TerminalDisclosure,
  TerminalEmptyState,
  TerminalGrid,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPageHeading,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal/TerminalPrimitives';
import { WideWorkspacePageShell } from '../components/layout/WideWorkspaceShell';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import {
  marketRotationApi,
  type MarketRotationEvidenceQuality,
  type MarketRotationEtfLeadershipDiagnostics,
  type MarketRotationRadarResponse,
  type MarketRotationRiskLabel,
  type MarketRotationSignalType,
  type MarketRotationStage,
  type MarketRotationSummaryItem,
  type MarketRotationTheme,
  type MarketRotationTimeWindow,
} from '../api/marketRotation';
import { formatDateTime } from '../utils/format';
import { cn } from '../utils/cn';
import { normalizeRotationEvidence } from '../utils/evidenceDisplay';
import { sanitizeUserFacingDataIssue } from '../utils/userFacingDataIssues';
import { marketIntelligenceReasonLabel, sanitizeMarketGuidanceCopy } from '../utils/marketIntelligenceGuidance';

const TOP_THEME_LIMIT = 10;
const MARKET_OPTIONS = [
  { id: 'US', label: 'US' },
  { id: 'CN', label: 'A股' },
  { id: 'HK', label: 'HK' },
  { id: 'CRYPTO', label: 'Crypto' },
] as const;

const STAGE_LABELS: Record<MarketRotationStage, string> = {
  early_watch: '早期观察',
  confirmed_rotation: '确认轮动',
  extended_watch: '延展观察',
  cooling_watch: '降温观察',
  weak_or_no_signal: '信号较弱',
};

const RISK_LABELS: Record<MarketRotationRiskLabel, string> = {
  gap_fade_risk: '高开回落风险',
  thin_breadth: '广度偏薄',
  single_name_driven: '单一龙头驱动',
  stale_or_incomplete_windows: '时窗缺失/过期',
};

const TAXONOMY_PLACEHOLDERS = ['主题', '行业', '概念', 'ETF代理'];
const REAL_FLOW_EVIDENCE_TYPES = new Set(['real_flow', 'mixed_real_and_proxy']);
const BOUNDED_ETF_SYMBOLS = ['SPY', 'QQQ', 'IWM', 'SMH', 'SOXX', 'IGV'] as const;

type SignalLaneMeta = {
  label: string;
  description: string;
  variant: 'success' | 'info' | 'caution' | 'neutral' | 'danger';
  tone: string;
};

const SIGNAL_LANE_META: Record<MarketRotationSignalType, SignalLaneMeta> = {
  real_flow: {
    label: '真实流向确认',
    description: '具备真实资金流证据，可使用资金流向语言。',
    variant: 'success',
    tone: 'text-emerald-200',
  },
  relative_strength: {
    label: '相对强弱',
    description: '报价支持的相对强弱，不等同于真实资金流。',
    variant: 'info',
    tone: 'text-cyan-100',
  },
  momentum_proxy: {
    label: '动量代理',
    description: '量能、广度与同步性等代理强度，不等同于真实资金流。',
    variant: 'info',
    tone: 'text-cyan-100',
  },
  observation_only: {
    label: '仅观察',
    description: '仅保留观察信号，不能放大为流向结论。',
    variant: 'neutral',
    tone: 'text-white/72',
  },
  taxonomy_fallback: {
    label: '主题库模式',
    description: '当前仅有主题分类，缺少可排名的行情证据。',
    variant: 'caution',
    tone: 'text-amber-200',
  },
  insufficient_evidence: {
    label: '证据不足',
    description: '证据不足，不能放大解释为轮动或流向。',
    variant: 'danger',
    tone: 'text-rose-200',
  },
};

const EVIDENCE_QUALITY_META: Record<MarketRotationEvidenceQuality, { label: string; variant: SignalLaneMeta['variant'] }> = {
  score_grade_real_flow: { label: '真实流向级', variant: 'success' },
  score_grade_proxy: { label: '报价代理级', variant: 'info' },
  degraded_proxy: { label: '受限代理级', variant: 'caution' },
  observation_only: { label: '观察级', variant: 'neutral' },
  taxonomy_only: { label: '主题库', variant: 'caution' },
  insufficient: { label: '不足', variant: 'danger' },
};

const DATA_GAP_LABELS: Record<string, string> = {
  true_flow_data_missing: '缺少真实资金流数据',
  flow_methodology_missing: '缺少流向方法学',
  source_authority_rejected: '来源权威性不足',
  stale_quote_window: '行情窗口过期',
  benchmark_proxy_missing: '基准代理缺失',
  proxy_coverage_incomplete: '代理覆盖不完整',
  taxonomy_only: '仅有分类主题',
};

type Bucket = {
  id: string;
  title: string;
  tone: string;
  items: MarketRotationTheme[];
  fallback: string;
};

type DataStateFields = {
  freshness?: MarketRotationTheme['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
};

function scoreTone(score: number): string {
  if (score >= 75) {
    return 'text-emerald-300 drop-shadow-[0_0_10px_rgba(52,211,153,0.34)]';
  }
  if (score >= 60) {
    return 'text-cyan-200 drop-shadow-[0_0_10px_rgba(103,232,249,0.24)]';
  }
  if (score >= 45) {
    return 'text-amber-200';
  }
  return 'text-white/45';
}

function percent(value?: number | null, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '待确认';
  }
  return `${value.toFixed(digits)}%`;
}

function signedPercent(value?: number | null, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '待确认';
  }
  return `${value >= 0 ? '+' : ''}${value.toFixed(digits)}%`;
}

function ratio(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '待确认';
  }
  return `${value.toFixed(2)}x`;
}

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

function laneMeta(theme: MarketRotationTheme): SignalLaneMeta {
  return SIGNAL_LANE_META[resolveSignalType(theme)];
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

function qualityMeta(theme: MarketRotationTheme) {
  return EVIDENCE_QUALITY_META[resolveEvidenceQuality(theme)];
}

function formatGapLabel(value?: string | null): string {
  const normalized = String(value || '').trim();
  if (!normalized) {
    return '数据缺口待补齐';
  }
  return DATA_GAP_LABELS[normalized] || sanitizeRotationText(normalized.replaceAll('_', ' '), '数据缺口待补齐');
}

function themeDataGaps(theme: MarketRotationTheme): string[] {
  const gaps = Array.isArray(theme.dataGaps) ? theme.dataGaps : [];
  return gaps
    .map((gap) => String(gap || '').trim())
    .filter((gap, index, array) => gap && array.indexOf(gap) === index);
}

function summarizeLane(themes: MarketRotationTheme[]): SignalLaneMeta {
  if (!themes.length) {
    return SIGNAL_LANE_META.insufficient_evidence;
  }
  const counts = themes.reduce<Record<MarketRotationSignalType, number>>((acc, theme) => {
    const key = resolveSignalType(theme);
    acc[key] += 1;
    return acc;
  }, {
    real_flow: 0,
    relative_strength: 0,
    momentum_proxy: 0,
    observation_only: 0,
    taxonomy_fallback: 0,
    insufficient_evidence: 0,
  });
  const dominant = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] as MarketRotationSignalType | undefined;
  return dominant ? SIGNAL_LANE_META[dominant] : SIGNAL_LANE_META.insufficient_evidence;
}

function summarizeEvidenceQuality(themes: MarketRotationTheme[]): string {
  if (!themes.length) {
    return '待补齐';
  }
  const counts = themes.reduce<Record<string, number>>((acc, theme) => {
    const key = resolveEvidenceQuality(theme);
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const dominant = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0];
  return dominant ? EVIDENCE_QUALITY_META[dominant as MarketRotationEvidenceQuality].label : '待补齐';
}

function summarizeGap(themes: MarketRotationTheme[]): string {
  const counts = themes.reduce<Record<string, number>>((acc, theme) => {
    themeDataGaps(theme).forEach((gap) => {
      acc[gap] = (acc[gap] || 0) + 1;
    });
    return acc;
  }, {});
  const dominant = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0];
  return dominant ? formatGapLabel(dominant) : '暂无高亮缺口';
}

function shouldAllowMoneyFlowLanguage(theme?: MarketRotationTheme | null): boolean {
  if (!theme) return false;
  return resolveSignalType(theme) === 'real_flow' && Boolean(theme.flowLanguageAllowed);
}

function conservativeFlowCopy(value?: string | null, allowMoneyFlowLanguage = false): string {
  const fallback = '仅用于观察主题轮动与相对强弱，非投资建议。';
  const text = String(value || '').trim();
  if (!text) return fallback;
  if (allowMoneyFlowLanguage) {
    return sanitizeMarketGuidanceCopy(sanitizeRotationText(text, fallback), fallback);
  }
  return sanitizeMarketGuidanceCopy(sanitizeRotationText(
    text
      .replaceAll('资金流向', '主题强弱')
      .replaceAll('资金轮动', '主题轮动')
      .replaceAll('资金流', '流向'),
    fallback,
  ), fallback);
}

function compactConfidence(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '0%';
  }
  return `${Math.round(value * 100)}%`;
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
    return '备用/静态';
  }
  if (theme.isStale || theme.freshness === 'stale') {
    return '过期待复核';
  }
  if (theme.freshness === 'delayed') {
    return '延迟可用';
  }
  if (theme.freshness === 'live') {
    return '实时';
  }
  return '缓存/部分';
}

function proxyMissingReasonLabel(reason?: string | null): string {
  const labels: Record<string, string> = {
    proxy_quote_missing: '代理行情待补齐',
    proxy_stale: '代理行情过期',
    proxy_windows_missing: '代理时窗待补齐',
  };
  return reason ? labels[reason] || '代理证据待复核' : '代理可用';
}

function isInternalRotationIssue(value?: string | null): boolean {
  const normalized = String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  return /provider|timeout|schema|debug|raw|trace|cache|not_enough|unavailable|missing|insufficient|technical_indicators|fundamentals|earnings|optional_news/.test(normalized);
}

function sanitizeRotationText(value?: string | null, fallback = '数据不足，结论仅供观察'): string {
  const text = String(value || '').trim();
  if (!text) return fallback;
  return sanitizeMarketGuidanceCopy(isInternalRotationIssue(text) ? sanitizeUserFacingDataIssue(text, 'zh') : text, fallback);
}

function sanitizeRotationNotes(notes?: string[]): string[] {
  return (notes || [])
    .map((note) => sanitizeRotationText(note, ''))
    .filter((note, index, array) => Boolean(note) && array.indexOf(note) === index);
}

function proxyQualityState(theme: MarketRotationTheme): string {
  if (theme.proxyQuality?.hasMissingRequiredProxy) {
    return '代理缺口';
  }
  if (theme.proxyQuality?.hasStaleProxy) {
    return '代理过期';
  }
  const total = theme.proxyQuality?.totalProxyCount ?? Object.keys(theme.benchmarkProxies || {}).length;
  const available = theme.proxyQuality?.availableProxyCount ?? total;
  return available < total ? '部分可用' : '代理完整';
}

function isThemeStale(theme: DataStateFields): boolean {
  return Boolean(theme.isStale || theme.freshness === 'stale');
}

function summaryTitle(items: MarketRotationSummaryItem[], fallback: string): string {
  return items.length ? items.map((item) => item.name).join(' / ') : fallback;
}

function deriveTopThemes(themes: MarketRotationTheme[], limit = TOP_THEME_LIMIT): MarketRotationTheme[] {
  return [...themes]
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

function deriveParticipationBuckets(themes: MarketRotationTheme[]): Bucket[] {
  const sorted = deriveTopThemes(themes, themes.length);
  const rising = sorted
    .filter((theme) => theme.rotationScore >= 62 && Number(theme.volume?.averageRelativeVolume) >= 1.05 && Number(theme.relativeStrength?.averageRelativeStrengthPercent) > 0)
    .slice(0, 4);
  const broad = sorted
    .filter((theme) => Number(theme.breadth?.percentUp) >= 70 || Number(theme.leadership?.broadParticipationPercent) >= 55)
    .slice(0, 4);
  const narrow = sorted
    .filter((theme) => Number(theme.leadership?.leadershipConcentrationPercent) >= 50 || theme.riskLabels.includes('single_name_driven') || theme.riskLabels.includes('thin_breadth'))
    .slice(0, 4);

  return [
    { id: 'rising', title: '新近走强', tone: 'text-emerald-200', items: rising, fallback: '暂无扩张确认' },
    { id: 'weakening', title: '走弱降温', tone: 'text-amber-200', items: deriveWeakeningThemes(themes), fallback: '暂无降温列表' },
    { id: 'broad', title: '广泛参与', tone: 'text-cyan-200', items: broad, fallback: '广度待补齐' },
    { id: 'narrow', title: '窄幅龙头', tone: 'text-rose-200', items: narrow, fallback: '未见明显集中' },
  ];
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

function rotationEvidenceSummary(theme: MarketRotationTheme) {
  if (!theme.rotationStateEvidence) return null;
  return normalizeRotationEvidence({ rotationStateEvidence: theme.rotationStateEvidence });
}

function marketLabel(market: string): string {
  return MARKET_OPTIONS.find((option) => option.id === market)?.label || market;
}

function compactSymbols(symbols?: string[], fallback = '待补齐'): string {
  return Array.isArray(symbols) && symbols.length ? symbols.join(' / ') : fallback;
}

function leadershipSpreadLabel(value?: number | null): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) : '未启用';
}

function summarizeEtfEvidence(diagnostics: MarketRotationEtfLeadershipDiagnostics) {
  const evidence = Array.isArray(diagnostics.evidence) ? diagnostics.evidence : [];
  const authorityAllowed = evidence.filter((row) => row.sourceAuthorityAllowed === true).length;
  const scoreEligible = evidence.filter((row) => row.scoreContributionAllowed === true).length;
  const freshness =
    evidence.find((row) => row.freshness && row.freshness !== 'fallback')?.freshness
    || evidence[0]?.freshness
    || 'fallback';
  const sourceLabel = String(evidence.find((row) => row.sourceLabel)?.sourceLabel || diagnostics.source || '待确认');
  const reasonCodes = evidence.flatMap((row) => row.reasonCodes || []);
  const uniqueReasons = Array.from(new Set(reasonCodes.filter(Boolean)));
  return {
    authorityAllowed,
    scoreEligible,
    total: evidence.length,
    freshness,
    sourceLabel,
    uniqueReasons,
  };
}

const ThemeMetric: React.FC<{ label: string; value: string; tone?: string }> = ({ label, value, tone = 'text-white/78' }) => (
  <div className="min-w-0 rounded-md border border-white/[0.05] bg-black/15 px-3 py-2">
    <p className="truncate text-[10px] font-semibold text-white/38">{label}</p>
    <p className={cn('mt-1 truncate font-mono text-sm font-semibold tabular-nums', tone)}>{value}</p>
  </div>
);

const EtfLeadershipDiagnosticsPanel: React.FC<{
  diagnostics: MarketRotationEtfLeadershipDiagnostics;
}> = ({ diagnostics }) => {
  const enabled = diagnostics.enabled;
  const evidence = summarizeEtfEvidence(diagnostics);
  const reasonCodes = diagnostics.reasonCodes.length ? diagnostics.reasonCodes : ['fail_closed'];
  const reasonLabels = marketIntelligenceReasonLabelsForRotation(reasonCodes);
  const rawReasonCodes = Array.from(new Set([...reasonCodes, ...evidence.uniqueReasons].filter(Boolean)));
  return (
    <div data-testid="rotation-radar-etf-leadership-panel" className="min-w-0 px-1 py-3">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <TerminalSectionHeader eyebrow="Bounded ETF Authority" title="ETF Leadership diagnostics" />
        <TerminalChip variant={enabled ? 'success' : 'caution'}>{enabled ? 'Enabled' : 'Disabled'}</TerminalChip>
      </div>

      <p className="mt-2 text-[11px] leading-5 text-white/48">
        仅覆盖 {BOUNDED_ETF_SYMBOLS.join(' / ')}。这是 display-only 的 bounded ETF authority diagnostics，
        不扩展主题排名、headline eligibility 或任何交易含义。
      </p>

      <div className="mt-3 flex min-w-0 flex-wrap items-center gap-1.5">
        <TerminalChip>{`Confidence ${diagnostics.confidenceLabel || '未返回'}`}</TerminalChip>
        <TerminalChip>{`As Of ${formatDateTime(diagnostics.asOf) || '待确认'}`}</TerminalChip>
        <TerminalChip>{`Source ${diagnostics.source || evidence.sourceLabel}`}</TerminalChip>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <ThemeMetric label="Eligible ETFs" value={`${diagnostics.eligibleSymbols.length}/6`} />
        <ThemeMetric label="Leadership Spread" value={leadershipSpreadLabel(diagnostics.leadershipSpread)} tone={enabled ? 'text-cyan-100' : 'text-white/52'} />
        <ThemeMetric label="Authority Evidence" value={`${evidence.authorityAllowed}/${evidence.total || diagnostics.eligibleSymbols.length || 0}`} tone={enabled ? 'text-emerald-200' : 'text-amber-200'} />
        <ThemeMetric label="Score-Eligible" value={`${evidence.scoreEligible}/${evidence.total || diagnostics.eligibleSymbols.length || 0}`} tone={enabled ? 'text-emerald-200' : 'text-amber-200'} />
      </div>

      <div className="mt-3 grid gap-2">
        <TerminalNestedBlock className="min-w-0 px-3 py-2">
          <p className="text-[10px] font-semibold uppercase text-white/35">Eligible</p>
          <p className="mt-1 text-xs text-white/72">{compactSymbols(diagnostics.eligibleSymbols)}</p>
        </TerminalNestedBlock>
        <TerminalNestedBlock className="min-w-0 px-3 py-2">
          <p className="text-[10px] font-semibold uppercase text-white/35">Leading</p>
          <p className="mt-1 text-xs text-white/72">{enabled ? compactSymbols(diagnostics.leadingSymbols, '待补齐') : 'Disabled / fail-closed'}</p>
        </TerminalNestedBlock>
        <TerminalNestedBlock className="min-w-0 px-3 py-2">
          <p className="text-[10px] font-semibold uppercase text-white/35">Lagging</p>
          <p className="mt-1 text-xs text-white/72">{enabled ? compactSymbols(diagnostics.laggingSymbols, '待补齐') : 'Disabled / fail-closed'}</p>
        </TerminalNestedBlock>
      </div>

      <div className="mt-3 flex min-w-0 flex-wrap gap-1.5">
        {reasonLabels.map((label) => (
          <TerminalChip key={label} variant={enabled ? 'info' : 'caution'}>{label}</TerminalChip>
        ))}
      </div>

      <TerminalNotice variant={enabled ? 'info' : 'caution'} className="mt-3 text-[11px] leading-5 text-white/56">
        {enabled
          ? `Evidence summary: Authority ${evidence.authorityAllowed}/${evidence.total}, Score-Eligible ${evidence.scoreEligible}/${evidence.total}, Source ${evidence.sourceLabel}.`
          : `Fail-closed until ETF windows and authority checks pass. Authority ${evidence.authorityAllowed}/${evidence.total || 0}，Score-Eligible ${evidence.scoreEligible}/${evidence.total || 0}。`}
      </TerminalNotice>
      <TerminalDisclosure
        data-testid="rotation-etf-raw-reason-codes"
        title="原始 reason codes"
        summary="默认折叠"
        className="mt-3 bg-black/10"
      >
        <div className="flex min-w-0 flex-wrap gap-1.5">
          {rawReasonCodes.map((code) => (
            <TerminalChip key={code} variant="neutral">{code}</TerminalChip>
          ))}
        </div>
      </TerminalDisclosure>
    </div>
  );
};

function marketIntelligenceReasonLabelsForRotation(values: string[]): string[] {
  const seen = new Set<string>();
  return values
    .map((value) => marketIntelligenceReasonLabel(value, 'zh'))
    .filter((label) => {
      if (seen.has(label)) return false;
      seen.add(label);
      return true;
    });
}

function rotationScoreEligibleCount(payload: MarketRotationRadarResponse): number {
  return (payload.etfLeadershipDiagnostics?.evidence || []).filter((row) => row.scoreContributionAllowed === true).length;
}

function isRotationLibraryMode(payload: MarketRotationRadarResponse): boolean {
  const themes = payload.themes || [];
  const taxonomyOnly = themes.length > 0 && themes.every(isTaxonomyOnlyTheme);
  return taxonomyOnly || payload.etfLeadershipDiagnostics?.enabled === false || rotationScoreEligibleCount(payload) === 0;
}

function rotationGuidance(payload: MarketRotationRadarResponse): {
  title: string;
  detail: string;
  variant: 'neutral' | 'info' | 'caution' | 'danger';
} {
  const themes = payload.themes || [];
  const hasRealFlowSignal = themes.some((theme) => resolveSignalType(theme) === 'real_flow' && theme.flowLanguageAllowed);
  const libraryMode = isRotationLibraryMode(payload);

  if (libraryMode) {
    return {
      title: '主题库模式：当前不是实时轮动信号',
      detail: '当前仅展示主题分类与观察线索，缺少 ETF authority / flow / breadth confirmation。',
      variant: 'caution',
    };
  }

  if (!hasRealFlowSignal) {
    return {
      title: '当前不能判断主题轮动',
      detail: '当前仅展示主题分类与观察线索，缺少 ETF authority / flow / breadth confirmation。',
      variant: 'info',
    };
  }

  return {
    title: '主题轮动可继续观察',
    detail: '已出现可用证据，但页面仍只提供研究观察，不放大为交易含义。',
    variant: 'info',
  };
}

const RotationGuidancePanel: React.FC<{ payload: MarketRotationRadarResponse }> = ({ payload }) => {
  const guidance = rotationGuidance(payload);
  const libraryMode = isRotationLibraryMode(payload);
  const scopeThemes = resolveSummaryThemes(payload.themes || [], payload.summary.strongestThemes || []);
  const summaryThemes = scopeThemes.length ? scopeThemes : payload.themes || [];
  const dominantLane = summarizeLane(summaryThemes);
  const topThemeTitle = summaryTitle(payload.summary.strongestThemes, libraryMode ? '按主题分类浏览' : '等待真实行情');
  const upgradeLine = '需要 ETF authority / flow / breadth confirmation 才能升级为实时轮动信号。';
  const nextWatch = libraryMode
    ? `优先补齐 ${summarizeGap(summaryThemes)}，再确认 ETF authority、流向与广度是否同时过关。`
    : payload.summary.watchlistSignals?.length
      ? `${payload.summary.watchlistSignals[0].themeName} · ${payload.summary.watchlistSignals[0].signalLabel || payload.summary.watchlistSignals[0].label || '观察线索'}`
      : '继续核对是否有新的实时轮动确认。';

  return (
    <TerminalPanel
      data-testid="rotation-radar-guidance"
      className="relative overflow-hidden"
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-cyan-400/0 via-cyan-200/42 to-sky-400/0" aria-hidden="true" />
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-medium tracking-[0.24em] text-white/38">轮动判断摘要</p>
          <p className="mt-2 text-base font-semibold leading-6 text-white/90 md:text-lg">{guidance.title}</p>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-white/58">{guidance.detail}</p>
        </div>
        <div className="flex min-w-0 flex-wrap justify-end gap-2">
          <TerminalChip variant={guidance.variant}>{libraryMode ? '主题库模式' : '仅供研究观察'}</TerminalChip>
          <TerminalChip variant={libraryMode ? 'caution' : 'info'}>{dominantLane.label}</TerminalChip>
          <TerminalChip variant={rotationScoreEligibleCount(payload) > 0 ? 'success' : 'caution'}>
            可计分证据 {rotationScoreEligibleCount(payload)}
          </TerminalChip>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-3">
        <div data-testid="rotation-radar-summary-band" data-terminal-primitive="panel" className="contents">
        <div className="rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
          <p className="text-[11px] font-medium text-white/48">当前状态</p>
          <p className="mt-2 text-sm font-semibold text-white/82">{libraryMode ? '当前不是实时轮动信号' : '当前可继续观察主题轮动'}</p>
          <p className="mt-2 text-[11px] leading-5 text-white/58">
            {libraryMode ? '主题库不是机会榜，不是实时排名，只保留分类浏览与观察线索。' : '页面只解释研究证据，不放大为交易含义。'}
          </p>
        </div>
        <div className="rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
          <p className="text-[11px] font-medium text-white/48">当前可用 / 观察信号</p>
          <p className="mt-2 text-sm font-semibold text-white/82">{topThemeTitle}</p>
          <p className="mt-2 text-[11px] leading-5 text-white/58">
            证据边界：{dominantLane.label}。证据质量：{summarizeEvidenceQuality(summaryThemes)}。
          </p>
        </div>
        <div className="rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
          <p className="text-[11px] font-medium text-white/48">主要缺口 / 升级条件</p>
          <p className="mt-2 text-sm font-semibold text-white/82">{summarizeGap(summaryThemes)}</p>
          <p className="mt-2 text-[11px] leading-5 text-white/58">{upgradeLine}</p>
        </div>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-white/[0.06] bg-black/10 px-3 py-3">
        <p className="text-[11px] font-medium text-white/48">下一步观察</p>
        <p className="mt-2 text-[11px] leading-5 text-white/60">{nextWatch}</p>
      </div>

      <TerminalDisclosure
        title="技术细节 / Details"
        summary="证据分层、主题摘要与升级边界默认折叠"
        className="mt-4 bg-black/10"
      >
        <div className="grid gap-4">
          <SummaryBand payload={payload} />
          <LaneBand themes={payload.themes || []} libraryMode={libraryMode} />
        </div>
      </TerminalDisclosure>
    </TerminalPanel>
  );
};

const WindowChip: React.FC<{ window: MarketRotationTimeWindow }> = ({ window }) => (
  <TerminalNestedBlock className="min-w-0 px-3 py-2">
    <p className="truncate text-[10px] font-semibold text-white/38">{window.label}</p>
    <p className={cn('mt-1 truncate text-[11px] font-semibold', window.available ? 'text-cyan-100' : 'text-white/35')}>
      {window.available ? signedPercent(window.changePercent, 1) : '待补齐'}
    </p>
  </TerminalNestedBlock>
);

const RiskChip: React.FC<{ risk: MarketRotationRiskLabel }> = ({ risk }) => (
  <TerminalChip variant="caution" className="px-2 py-0.5 text-[10px] font-semibold">
    {RISK_LABELS[risk] || '风险待识别'}
  </TerminalChip>
);

const SignalLaneChip: React.FC<{ theme: MarketRotationTheme; className?: string }> = ({ theme, className }) => (
  <TerminalChip variant={laneMeta(theme).variant} className={className}>
    {laneMeta(theme).label}
  </TerminalChip>
);

const EvidenceQualityChip: React.FC<{ theme: MarketRotationTheme; className?: string }> = ({ theme, className }) => (
  <TerminalChip variant={qualityMeta(theme).variant} className={className}>
    {qualityMeta(theme).label}
  </TerminalChip>
);

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
    className="min-h-[132px] gap-y-3 sm:min-h-[118px] lg:min-h-11"
    leading={(
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <div className="inline-flex items-center gap-2 text-[10px] font-bold uppercase text-white/35">
          <SlidersHorizontal className="h-3.5 w-3.5 text-cyan-200/70" aria-hidden="true" />
          市场
        </div>
        <div className="flex min-w-0 gap-2 overflow-x-auto no-scrollbar">
          {MARKET_OPTIONS.filter((market) => !supportedMarkets.length || supportedMarkets.includes(market.id)).map((market) => (
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
            </TerminalButton>
          ))}
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
          className="h-10 w-10 rounded-xl px-0 py-0 text-white/50 disabled:cursor-wait disabled:text-white/30"
          onClick={onRefresh}
          disabled={loading}
          aria-label="刷新主题轮动雷达"
        >
          <RefreshCcw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} aria-hidden="true" />
        </TerminalButton>
      </div>
    )}
  >
    <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-center lg:gap-3">
      <label className="relative min-w-0 flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/35" aria-hidden="true" />
        <input
          className="h-10 w-full rounded-lg border border-white/10 bg-black/25 py-2 pl-9 pr-3 text-sm text-white/78 outline-none transition-all placeholder:text-white/30 focus:border-cyan-200/30 focus:bg-white/[0.035]"
          value={searchQuery}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="搜索主题、英文名或成员"
        />
      </label>
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <div className="inline-flex items-center gap-2 text-[10px] font-bold uppercase text-white/35">
          <Gauge className="h-3.5 w-3.5 text-cyan-200/70" aria-hidden="true" />
          分类层级
        </div>
        {TAXONOMY_PLACEHOLDERS.map((mode, index) => (
          <TerminalButton
            key={mode}
            type="button"
            variant="compact"
            className={cn(
              'shrink-0',
              index === 0
                ? 'border-white/10 bg-white/[0.055] text-white/75 hover:bg-white/[0.055] hover:text-white/75'
                : 'cursor-default text-white/35 hover:border-white/10 hover:bg-white/[0.03] hover:text-white/35',
            )}
            disabled
          >
            {mode}
          </TerminalButton>
        ))}
      </div>
    </div>
  </WolfyCommandBar>
);

const SummaryBand: React.FC<{
  payload: MarketRotationRadarResponse;
}> = ({ payload }) => {
  const libraryMode = isRotationLibraryMode(payload);
  const scopeThemes = resolveSummaryThemes(payload.themes || [], payload.summary.strongestThemes || []);
  const summaryThemes = scopeThemes.length ? scopeThemes : payload.themes || [];
  const dominantLane = summarizeLane(summaryThemes);
  const items = [
    { key: 'market', label: '市场', value: marketLabel(payload.market || 'US') },
    { key: 'source', label: '来源', value: payload.sourceLabel || '待确认' },
    { key: 'mode', label: '模式', value: libraryMode ? '主题库模式' : '轮动观察' },
    { key: 'top', label: libraryMode ? '分类浏览' : '重点主题', value: summaryTitle(payload.summary.strongestThemes, libraryMode ? '按主题分类浏览' : '等待真实行情') },
    { key: 'lane', label: '证据边界', value: dominantLane.label },
    { key: 'quality', label: '证据质量', value: summarizeEvidenceQuality(summaryThemes) },
    { key: 'gaps', label: '主要缺口', value: summarizeGap(summaryThemes) },
    { key: 'watch', label: '观察信号', value: String(payload.summary.watchlistSignals?.length ?? 0) },
  ];

  return (
    <TerminalPanel data-testid="rotation-radar-summary-band" dense className="min-h-[104px] gap-0 overflow-visible p-0 sm:min-h-[76px]">
      <div className="flex min-w-0 items-center gap-2 border-b border-[color:var(--wolfy-divider)] px-3 py-2 text-[10px] font-bold uppercase text-white/35">
        <Signal className="h-3.5 w-3.5 text-cyan-200/70" aria-hidden="true" />
        {libraryMode ? '主题分类与观察线索' : '主题分层'}
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2 text-xs">
        {items.map((item, index) => (
          <div
            key={item.key}
            className={cn(
              'flex min-w-0 items-baseline gap-1.5 pr-4',
              index < items.length - 1 && 'border-r border-[color:var(--wolfy-divider)]',
            )}
          >
            <span className="shrink-0 text-[11px] text-[color:var(--wolfy-text-muted)]">{item.label}</span>
            <span className="truncate font-mono text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{item.value}</span>
          </div>
        ))}
      </div>
    </TerminalPanel>
  );
};

const LaneBand: React.FC<{ themes: MarketRotationTheme[]; libraryMode: boolean }> = ({ themes, libraryMode }) => {
  const counts = themes.reduce<Record<MarketRotationSignalType, number>>((acc, theme) => {
    const key = resolveSignalType(theme);
    acc[key] += 1;
    return acc;
  }, {
    real_flow: 0,
    relative_strength: 0,
    momentum_proxy: 0,
    observation_only: 0,
    taxonomy_fallback: 0,
    insufficient_evidence: 0,
  });
  const dominant = summarizeLane(themes);

  return (
    <DataWorkbenchFrame data-testid="rotation-radar-lane-band">
      <div className="flex min-w-0 flex-col gap-3 px-3 py-3">
        <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
          <TerminalSectionHeader eyebrow="证据分层" title={libraryMode ? '当前仅展示分类与观察线索' : '真实流向与代理强度边界'} />
          <span className={cn('text-xs font-semibold', dominant.tone)}>{dominant.label}</span>
        </div>
        <div className="flex min-w-0 flex-wrap gap-2">
          {(Object.keys(SIGNAL_LANE_META) as MarketRotationSignalType[]).map((key) => (
            <TerminalChip key={key} variant={SIGNAL_LANE_META[key].variant} className="px-2 py-1 text-[11px]">
              {SIGNAL_LANE_META[key].label} · {counts[key]}
            </TerminalChip>
          ))}
        </div>
        <p className="text-[11px] leading-5 text-white/52">{dominant.description}</p>
      </div>
    </DataWorkbenchFrame>
  );
};

const LeaderRow: React.FC<{
  theme: MarketRotationTheme;
  rank: number;
  libraryMode: boolean;
  selected: boolean;
  onSelect: () => void;
}> = ({ theme, rank, libraryMode, selected, onSelect }) => {
  const taxonomyOnly = isTaxonomyOnlyTheme(theme);
  const displayAsLibrary = libraryMode || taxonomyOnly;
  const evidenceSummary = rotationEvidenceSummary(theme);
  const gaps = themeDataGaps(theme);
  return (
    <button
      type="button"
      data-testid={`rotation-radar-leader-row-${theme.id}`}
      onClick={onSelect}
      className={cn(
        'grid w-full min-w-0 grid-cols-[2.25rem_minmax(0,1.5fr)_4.5rem_4rem] items-center gap-2 px-3 py-3 text-left transition-colors md:grid-cols-[2.25rem_minmax(0,1.55fr)_4.75rem_4.75rem_4.5rem]',
        selected ? 'bg-cyan-200/[0.06]' : 'hover:bg-white/[0.025]',
      )}
    >
      <span className="font-mono text-xs text-white/38 tabular-nums">{displayAsLibrary ? '目录' : rank.toString().padStart(2, '0')}</span>
      <span className="min-w-0">
        <span className="flex min-w-0 items-center gap-2">
          <span className="truncate text-sm font-semibold text-white/84">{theme.name}</span>
          <DataFreshnessBadge freshness={theme.freshness} className="hidden px-1.5 text-[9px] sm:inline-flex" />
        </span>
        <span className="mt-1 block truncate text-[11px] text-white/38">
          {displayAsLibrary ? '主题库条目，仅供分类浏览与观察' : `${laneMeta(theme).label} · ${mapDataStateLabel(theme)}`}
        </span>
        <span className="mt-1 flex min-w-0 flex-wrap items-center gap-1.5">
          <SignalLaneChip theme={theme} className="px-1.5 py-0.5 text-[10px]" />
          <EvidenceQualityChip theme={theme} className="px-1.5 py-0.5 text-[10px]" />
          {gaps.length ? <TerminalChip className="px-1.5 py-0.5 text-[10px]">{`缺口 ${gaps.length}`}</TerminalChip> : null}
        </span>
        {evidenceSummary ? (
          <EvidenceChips summary={evidenceSummary} maxLabels={2} className="mt-1 hidden sm:flex" />
        ) : null}
      </span>
      <span className={cn('text-right font-mono text-lg font-semibold tabular-nums', displayAsLibrary ? 'text-white/46' : scoreTone(theme.rotationScore))}>
        {displayAsLibrary ? '主题库' : theme.rotationScore}
      </span>
      <span className="hidden text-right font-mono text-xs text-emerald-200 tabular-nums md:block">
        {displayAsLibrary ? '分类' : signedPercent(theme.relativeStrength?.averageRelativeStrengthPercent)}
      </span>
      <span className="hidden text-right font-mono text-xs text-cyan-100 tabular-nums md:block">
        {displayAsLibrary ? '观察' : ratio(theme.volume?.averageRelativeVolume)}
      </span>
      <span className="text-right font-mono text-xs text-white/58 tabular-nums">{displayAsLibrary ? '待升级' : percent(theme.breadth?.percentUp, 0)}</span>
    </button>
  );
};

const LaggardRow: React.FC<{
  theme: MarketRotationTheme;
  libraryMode: boolean;
  selected: boolean;
  onSelect: () => void;
}> = ({ theme, libraryMode, selected, onSelect }) => (
  <button
    type="button"
    data-testid={`rotation-radar-laggard-row-${theme.id}`}
    onClick={onSelect}
    className={cn(
      'grid w-full min-w-0 grid-cols-[minmax(0,1fr)_3.5rem] gap-2 px-3 py-3 text-left transition-colors',
      selected ? 'bg-amber-300/[0.07]' : 'hover:bg-white/[0.025]',
    )}
    >
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold text-white/78">{theme.name}</span>
        <span className="mt-1 block truncate text-[11px] text-white/38">
        {libraryMode || isTaxonomyOnlyTheme(theme) ? '主题库观察线索' : `${laneMeta(theme).label} · ${mapDataStateLabel(theme)}`}
        </span>
      </span>
    <span className={cn('text-right font-mono text-sm font-semibold tabular-nums', libraryMode || isTaxonomyOnlyTheme(theme) ? 'text-white/44' : scoreTone(theme.rotationScore))}>
      {libraryMode || isTaxonomyOnlyTheme(theme) ? '主题库' : theme.rotationScore}
    </span>
  </button>
);

const CompactThemeRow: React.FC<{
  theme: MarketRotationTheme;
  libraryMode: boolean;
  selected: boolean;
  onSelect: () => void;
}> = ({ theme, libraryMode, selected, onSelect }) => (
  <button
    type="button"
    data-testid={`rotation-radar-universe-row-${theme.id}`}
    onClick={onSelect}
    className={cn(
      'grid w-full min-w-0 grid-cols-[minmax(0,1fr)_4rem_4.5rem] items-center gap-2 px-3 py-2.5 text-left text-xs transition-colors',
      selected ? 'bg-cyan-200/[0.06]' : 'hover:bg-white/[0.025]',
    )}
  >
    <span className="min-w-0">
      <span className="block truncate font-semibold text-white/76">{theme.name}</span>
      <span className="block truncate text-[10px] text-white/35">{theme.englishName || theme.focus || theme.benchmark}</span>
    </span>
    <span className={cn('text-right font-mono font-semibold tabular-nums', libraryMode || isTaxonomyOnlyTheme(theme) ? 'text-white/44' : scoreTone(theme.rotationScore))}>
      {libraryMode || isTaxonomyOnlyTheme(theme) ? '主题库' : theme.rotationScore}
    </span>
    <span className="text-right text-[11px] text-white/42">{laneMeta(theme).label}</span>
  </button>
);

const BucketPanel: React.FC<{ buckets: Bucket[] }> = ({ buckets }) => (
  <section data-testid="rotation-radar-buckets">
    <DataWorkbenchFrame>
      <div className="grid min-w-0 gap-0 md:grid-cols-2 xl:grid-cols-4">
        {buckets.map((bucket, index) => (
          <div
            key={bucket.id}
            className={cn(
              'min-w-0 px-3 py-3',
              index > 0 && 'border-t border-white/[0.05] md:border-t-0',
              index % 2 === 1 && 'md:border-l md:border-white/[0.05] xl:border-l-0',
              index > 1 && 'xl:border-l xl:border-white/[0.05]',
            )}
          >
            <p className={cn('text-[10px] font-bold uppercase', bucket.tone)}>{bucket.title}</p>
            <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
              {bucket.items.length ? bucket.items.map((theme) => (
                <TerminalChip key={theme.id} className="max-w-full truncate border-white/8 bg-black/20 px-2 py-1 text-[11px] text-white/62">
                  {theme.name}
                </TerminalChip>
              )) : (
                <TerminalChip className="truncate border-white/8 bg-black/20 px-2 py-1 text-[11px] text-white/36">{bucket.fallback}</TerminalChip>
              )}
            </div>
          </div>
        ))}
      </div>
    </DataWorkbenchFrame>
  </section>
);

const WatchlistMemberRow: React.FC<{ member: {
  symbol?: string;
  name?: string;
  roleLabel?: string;
  freshnessLabel?: string;
  changePercent?: number | null;
  relativeStrengthVsBenchmark?: number | null;
  observed?: boolean;
}; }> = ({ member }) => (
  <div className="flex min-w-0 items-center justify-between gap-3 rounded-md border border-white/[0.04] bg-black/15 px-3 py-2">
    <span className="min-w-0">
      <span className="block truncate text-sm font-semibold text-white/82">{member.symbol || '--'}</span>
      <span className="block truncate text-[11px] text-white/38">{member.roleLabel || member.name || '观察成员'} · {member.freshnessLabel || '待补齐'}</span>
    </span>
    <span className="shrink-0 text-right text-[11px] text-white/50">
      <span className="block font-mono text-sm text-cyan-100">{signedPercent(member.relativeStrengthVsBenchmark ?? member.changePercent)}</span>
      <span className="block">{member.observed ? '已观察' : '待补齐'}</span>
    </span>
  </div>
);

const ThemeDetailPanel: React.FC<{
  theme?: MarketRotationTheme;
  diagnostics: MarketRotationEtfLeadershipDiagnostics;
  libraryMode: boolean;
  proxyResetKey: number;
}> = ({ theme, diagnostics, libraryMode, proxyResetKey }) => {
  if (!theme) {
    return null;
  }
  const leaders = theme.leadership?.topMembers || [];
  const laggards = theme.themeDetail?.laggardMembers || [];
  const alertCandidates = theme.alertCandidates || [];
  const detailMembers = theme.themeDetail?.leadershipMembers?.length ? theme.themeDetail.leadershipMembers : [];
  const proxyValues = Object.values(theme.benchmarkProxies || {});
  const nextWatch = alertCandidates[0];
  const taxonomyOnly = isTaxonomyOnlyTheme(theme);
  const dataWarning = Boolean(theme.isFallback || theme.freshness === 'fallback' || isThemeStale(theme));
  const evidenceNotes = sanitizeRotationNotes(theme.evidence);
  const riskExplanationNotes = sanitizeRotationNotes(theme.riskExplanations);
  const evidenceSummary = rotationEvidenceSummary(theme);
  const lane = resolveSignalType(theme);
  const laneDefinition = SIGNAL_LANE_META[lane];
  const gaps = themeDataGaps(theme);
  const explanation = sanitizeRotationText(
    theme.stageExplanation,
    lane === 'real_flow'
      ? `${theme.name} 当前具备真实资金流证据，但仍需结合风险与新鲜度解读。`
      : lane === 'relative_strength'
        ? `${theme.name} 当前以报价支持的相对强弱为主，不能等同于真实资金流。`
        : lane === 'momentum_proxy'
          ? `${theme.name} 当前以量能、广度与同步性等动量代理为主，不能等同于真实资金流。`
          : lane === 'observation_only'
            ? `${theme.name} 当前仅保留观察信号，不能放大为流向结论。`
            : lane === 'taxonomy_fallback'
              ? `${theme.name} 当前仍是主题分类观察，本地行情覆盖后才能形成强弱结论。`
              : `${theme.name} 当前证据不足，只能作为待补齐的观察线索。`,
  );

  return (
    <ConsoleContextRail data-testid="rotation-theme-detail-panel" className="xl:sticky xl:top-4">
      <div className="px-1 py-3">
        <TerminalDisclosure
          data-testid="rotation-etf-diagnostics-disclosure"
          title="ETF authority 技术细节"
          summary="默认折叠"
        >
          <EtfLeadershipDiagnosticsPanel diagnostics={diagnostics} />
        </TerminalDisclosure>
      </div>

      <div className="min-w-0 px-1 py-3">
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase text-white/35">选中主题</p>
            <h2 className="mt-1 truncate text-lg font-semibold text-white">{theme.name}</h2>
            <p className="mt-1 truncate text-[11px] text-white/38">{theme.englishName} · {theme.focus || theme.benchmark}</p>
          </div>
          <div className="shrink-0 text-right">
            <p className={cn('font-mono text-4xl font-semibold leading-none tabular-nums', taxonomyOnly || libraryMode ? 'text-white/44' : scoreTone(theme.rotationScore))}>
              {taxonomyOnly || libraryMode ? '主题库' : theme.rotationScore}
            </p>
            <p className="mt-1 text-[10px] font-bold uppercase text-white/35">{taxonomyOnly || libraryMode ? '当前模式' : '强弱评分'}</p>
          </div>
        </div>

        <div className="mt-3 flex min-w-0 flex-wrap items-center gap-1.5">
          <SignalLaneChip theme={theme} />
          <EvidenceQualityChip theme={theme} />
          <TerminalChip variant="info">{formatThemeStage(theme.stage)}</TerminalChip>
          <TerminalChip>{taxonomyOnly ? theme.confidenceLabel || '待行情确认' : `置信度 ${compactConfidence(theme.confidence)}`}</TerminalChip>
          <TerminalChip variant={dataWarning ? 'caution' : 'success'}>{mapDataStateLabel(theme)}</TerminalChip>
          <TerminalChip variant={theme.sourceAuthorityAllowed ? 'success' : 'neutral'}>
            {theme.sourceAuthorityAllowed ? '权威来源可用' : '需要权威来源'}
          </TerminalChip>
          {gaps.length ? <TerminalChip variant="caution">{`缺口 ${gaps.length}`}</TerminalChip> : null}
          {!taxonomyOnly ? <DataFreshnessBadge freshness={theme.freshness} className="px-1.5 text-[9px]" /> : null}
        </div>
        {evidenceSummary ? (
          <EvidenceChips summary={evidenceSummary} maxLabels={3} className="mt-2" />
        ) : null}
      </div>

      <div className="min-w-0 px-1 py-3">
        {taxonomyOnly || libraryMode ? (
          <TerminalNotice variant="info" className="grid gap-2 px-3 py-3 text-[11px] leading-5">
            <p>当前不能判断主题轮动，当前不是实时轮动信号。</p>
            <p>当前仅展示主题分类与观察线索，主题库不是机会榜，也不是实时排名。</p>
            <p>需要 ETF authority / flow / breadth confirmation 才能升级为实时轮动信号。</p>
          </TerminalNotice>
        ) : dataWarning ? (
          <TerminalNotice variant="caution" className="text-[11px] leading-5">
            当前主题包含备用、过期或部分数据，只能作为观察线索，不能标记为实时结论。
          </TerminalNotice>
        ) : null}

        <TerminalNotice
          variant={laneDefinition.variant === 'danger' ? 'caution' : laneDefinition.variant === 'success' ? 'info' : laneDefinition.variant}
          className="mt-3 text-[12px] leading-5 text-white/58"
        >
          {`${laneDefinition.label}: ${laneDefinition.description}`}
        </TerminalNotice>
        <TerminalNotice variant="neutral" className="mt-3 text-[12px] leading-5 text-white/58">
          {explanation}
        </TerminalNotice>
      </div>

      <div className="min-w-0 px-1 py-3">
        <p className="text-[10px] font-bold uppercase text-white/35">数据缺口</p>
        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
          {(gaps.length ? gaps : ['no_material_gap']).slice(0, 5).map((gap) => (
            <TerminalChip key={gap} variant={gap === 'no_material_gap' ? 'success' : 'caution'}>
              {gap === 'no_material_gap' ? '暂无高亮缺口' : formatGapLabel(gap)}
            </TerminalChip>
          ))}
        </div>
      </div>

      {taxonomyOnly || libraryMode ? (
        <div className="min-w-0 px-1 py-3">
          <div>
            <p className="text-[10px] font-bold uppercase text-white/35">分类映射</p>
            <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
              {(theme.themeDetail?.mappedConcepts || theme.mappedConcepts || []).slice(0, 8).map((concept) => (
                <TerminalChip key={concept} variant="info">{concept}</TerminalChip>
              ))}
              {!(theme.themeDetail?.mappedConcepts || theme.mappedConcepts || []).length ? <TerminalChip>待补齐</TerminalChip> : null}
            </div>
          </div>
          <div className="mt-4">
            <p className="text-[10px] font-bold uppercase text-white/35">代表标签 / 观察标的</p>
            <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
              {(theme.themeDetail?.representativeLabels || theme.representativeLabels || theme.membersConfigured || []).slice(0, 8).map((label) => (
                <TerminalChip key={label}>{label}</TerminalChip>
              ))}
            </div>
          </div>
        </div>
      ) : null}
      {!(taxonomyOnly || libraryMode) ? (
        <>
          <div className="min-w-0 px-1 py-3">
            <div className="grid grid-cols-2 gap-2">
              <ThemeMetric label="相对强弱" value={signedPercent(theme.relativeStrength?.averageRelativeStrengthPercent)} tone={Number(theme.relativeStrength?.averageRelativeStrengthPercent) >= 0 ? 'text-emerald-200' : 'text-rose-300'} />
              <ThemeMetric label="成交扩张" value={ratio(theme.volume?.averageRelativeVolume)} tone={Number(theme.volume?.averageRelativeVolume) >= 1.1 ? 'text-cyan-200' : 'text-white/58'} />
              <ThemeMetric label="上涨广度" value={percent(theme.breadth?.percentUp)} />
              <ThemeMetric label="跑赢基准" value={percent(theme.breadth?.percentOutperformingBenchmark)} />
              <ThemeMetric label="同步性" value={percent(theme.synchronization?.sameDirectionPercent)} />
              <ThemeMetric label="龙头集中" value={percent(theme.leadership?.leadershipConcentrationPercent)} />
            </div>
          </div>

          <div className="min-w-0 px-1 py-3">
            <p className="text-[10px] font-bold uppercase text-white/35">下一步观察 / 风险</p>
            <TerminalNotice variant="info" className="mt-2 text-[11px] leading-5 text-cyan-50/62">
              {nextWatch?.symbol
                ? `${nextWatch.symbol} · ${nextWatch.signalLabel || nextWatch.label || '观察信号'} · ${nextWatch.readOnly ? '只读证据' : '待确认'}`
                : '等待可靠候选补齐，保持只读观察'}
            </TerminalNotice>
            <div className="mt-2 flex min-w-0 flex-wrap items-center gap-1.5">
              {theme.riskLabels.length ? theme.riskLabels.map((risk) => <RiskChip key={risk} risk={risk} />) : (
                <TerminalChip variant="success">暂无高亮风险</TerminalChip>
              )}
              <TerminalChip>非交易指令</TerminalChip>
            </div>
          </div>

          <div className="min-w-0 px-1 py-3">
            <p className="text-[10px] font-bold uppercase text-white/35">领先 / 落后成员</p>
            <div className="mt-2 grid gap-3">
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase text-white/35">领先成员</p>
                <div className="grid gap-2">
                  {leaders.length ? leaders.slice(0, 4).map((leader) => (
                    <div key={leader.symbol} className="flex min-w-0 items-center justify-between gap-3 rounded-md border border-white/[0.04] bg-black/15 px-3 py-2">
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold text-white/82">{leader.symbol}</span>
                        <span className="block truncate text-[11px] text-white/38">{leader.name || leader.symbol}</span>
                      </span>
                      <span className="shrink-0 text-right font-mono text-sm text-emerald-200 tabular-nums">{signedPercent(leader.relativeStrengthVsBenchmark ?? leader.changePercent)}</span>
                    </div>
                  )) : detailMembers.length ? detailMembers.slice(0, 4).map((member) => (
                    <WatchlistMemberRow key={`${member.symbol || 'leader'}-${member.roleLabel || 'leader'}`} member={member} />
                  )) : (
                    <TerminalEmptyState className="min-h-[72px] justify-start px-3 py-2 text-sm text-white/45">代表成员待快照补齐</TerminalEmptyState>
                  )}
                </div>
              </div>
              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase text-white/35">落后 / 待验证成员</p>
                <div className="grid gap-2">
                  {laggards.length ? laggards.slice(0, 4).map((member) => (
                    <WatchlistMemberRow key={`${member.symbol || 'laggard'}-${member.roleLabel || 'laggard'}`} member={member} />
                  )) : (
                    <TerminalEmptyState className="min-h-[72px] justify-start px-3 py-2 text-sm text-white/45">暂无落后成员快照</TerminalEmptyState>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="min-w-0 px-1 py-3">
            <TerminalDisclosure
              key={`${theme.id}-${proxyResetKey}`}
              data-testid={`rotation-theme-proxy-details-${theme.id}`}
              title="数据诊断"
              summary={(
                <span data-testid={`rotation-proxy-quality-summary-${theme.id}`} className="inline-flex min-w-0 flex-wrap items-center gap-1.5">
                  <TerminalChip variant={theme.proxyQuality?.hasMissingRequiredProxy || theme.proxyQuality?.hasStaleProxy ? 'caution' : 'success'}>
                    {proxyQualityState(theme)}
                  </TerminalChip>
                  <TerminalChip>
                    覆盖 {theme.proxyQuality?.availableProxyCount ?? proxyValues.length}/{theme.proxyQuality?.totalProxyCount ?? proxyValues.length}
                  </TerminalChip>
                  <TerminalChip>{percent(theme.proxyQuality?.coveragePercent)}</TerminalChip>
                  <DataFreshnessBadge freshness={theme.proxyQuality?.freshness || theme.freshness} className="px-1.5 text-[9px]" />
                </span>
              )}
            >
              <div className="grid gap-2 text-[11px] text-white/48">
                {theme.proxyQuality?.explanation ? <p className="leading-5">{sanitizeRotationText(theme.proxyQuality.explanation)}</p> : null}
                {proxyValues.map((proxy) => (
                  <div
                    key={proxy.symbol}
                    data-testid={`rotation-proxy-row-${proxy.symbol}`}
                    className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold text-white/82">{proxy.symbol}</span>
                      <span className="block truncate text-[11px] text-white/38">{proxy.role === 'sector_proxy' ? '行业代理' : '市场代理'}</span>
                    </span>
                    <span className="shrink-0 text-right">
                      <span className="block font-mono text-sm text-cyan-100">{signedPercent(proxy.relativeStrength)}</span>
                      <span className="block text-[10px] text-white/42">{proxyMissingReasonLabel(proxy.quality?.missingReason)}</span>
                    </span>
                  </div>
                ))}
                {theme.timeWindows ? (
                  <div className="grid grid-cols-2 gap-2">
                    {(['5m', '15m', '60m', '1d'] as const).map((window) => (
                      <WindowChip key={window} window={theme.timeWindows?.[window] || {
                        window,
                        label: window,
                        available: false,
                        freshness: 'fallback',
                        isFallback: true,
                        isStale: false,
                        reason: 'window_unavailable',
                      }} />
                    ))}
                  </div>
                ) : null}
              </div>
            </TerminalDisclosure>
          </div>
        </>
      ) : null}

      <div className="min-w-0 px-1 py-3">
        <TerminalDisclosure
          data-testid={`rotation-theme-evidence-details-${theme.id}`}
          title="证据详情"
          summary={evidenceNotes.length || riskExplanationNotes.length ? '观察证据与风险说明默认折叠' : '暂无额外证据'}
        >
          <div className="grid gap-1 text-[11px] leading-5 text-white/48">
            {evidenceNotes.slice(0, 5).map((item) => <p key={item} className="truncate">· {item}</p>)}
            {riskExplanationNotes.slice(0, 3).map((item) => <p key={item} className="truncate">· {item}</p>)}
            {!evidenceNotes.length && !riskExplanationNotes.length ? <p>暂无额外证据。</p> : null}
          </div>
        </TerminalDisclosure>
      </div>
    </ConsoleContextRail>
  );
};

const LoadingPanel: React.FC = () => (
  <TerminalPanel as="section" role="status" aria-label="正在读取主题轮动 / 相对强弱雷达">
    <div className="flex items-center gap-3 text-white/60">
      <RefreshCcw className="h-4 w-4 animate-spin" aria-hidden="true" />
      <span className="text-sm">正在读取主题轮动 / 相对强弱雷达...</span>
    </div>
  </TerminalPanel>
);

const MarketRotationRadarPage: React.FC = () => {
  const [payload, setPayload] = useState<MarketRotationRadarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [selectedMarket, setSelectedMarket] = useState('US');
  const [selectedThemeId, setSelectedThemeId] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [proxyDisclosureSeed, setProxyDisclosureSeed] = useState(0);

  const loadRadar = useCallback(async (market = selectedMarket) => {
    setLoading(true);
    setError(null);
    try {
      const nextPayload = await marketRotationApi.getRotationRadar(market);
      setPayload(nextPayload);
      setSelectedThemeId(nextPayload.themes[0]?.id || '');
      setSearchQuery('');
      setProxyDisclosureSeed((seed) => seed + 1);
    } catch (nextError) {
      setError({ ...getParsedApiError(nextError), title: '读取主题轮动雷达失败' });
    } finally {
      setLoading(false);
    }
  }, [selectedMarket]);

  useEffect(() => {
    void loadRadar(selectedMarket);
  }, [loadRadar, selectedMarket]);

  const headlineThemes = useMemo(
    () => resolveSummaryThemes(payload?.themes || [], payload?.summary.strongestThemes || []),
    [payload?.themes, payload?.summary.strongestThemes],
  );
  const weakeningThemes = useMemo(() => deriveWeakeningThemes(payload?.themes || []), [payload?.themes]);
  const filteredThemes = useMemo(
    () => (payload?.themes || []).filter((theme) => matchesSearch(theme, searchQuery)),
    [payload?.themes, searchQuery],
  );
  const buckets = useMemo(() => deriveParticipationBuckets(payload?.themes || []), [payload?.themes]);

  const selectedTheme = useMemo(
    () => payload?.themes.find((theme) => theme.id === selectedThemeId) || payload?.themes[0],
    [payload, selectedThemeId],
  );
  const pageLane = useMemo(() => summarizeLane(payload?.themes || []), [payload?.themes]);
  const libraryMode = useMemo(() => (payload ? isRotationLibraryMode(payload) : false), [payload]);

  return (
    <div
      data-testid="market-rotation-radar-page"
      data-bento-surface="true"
      className="bento-surface-root flex min-h-0 w-full min-w-0 flex-1 flex-col gap-6 overflow-y-auto overflow-x-hidden no-scrollbar text-white"
    >
      <WideWorkspacePageShell className="flex min-h-0 flex-1 py-5 md:py-6">
        <TerminalPanel as="section" dense className="relative shrink-0 overflow-hidden">
          <TerminalPageHeading
            eyebrow="主题轮动"
            title="主题轮动雷达"
            action={<TerminalChip variant={pageLane.variant}>{pageLane.label}</TerminalChip>}
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
            {payload.warning ? (
              <TerminalNotice variant="caution" className="flex items-start gap-2 px-4 py-3 text-sm leading-6">
                <AlertTriangle className="mt-1 h-4 w-4 shrink-0" aria-hidden="true" />
                <span>{sanitizeRotationText(payload.warning)}</span>
              </TerminalNotice>
            ) : null}

            <CommandBar
              selectedMarket={selectedMarket}
              supportedMarkets={payload.supportedMarkets || ['US', 'CN', 'HK', 'CRYPTO']}
              searchQuery={searchQuery}
              onMarketChange={setSelectedMarket}
              onSearchChange={setSearchQuery}
              loading={loading}
              freshness={payload.freshness}
              onRefresh={() => void loadRadar()}
            />

            <RotationGuidancePanel payload={payload} />

            <TerminalGrid className="gap-4" data-workbench-split="8:4">
              <section className="min-w-0 space-y-4 xl:col-span-8" aria-label={libraryMode ? '主题分类与观察线索' : '今日主题强弱 Top-N'}>
                <DataWorkbenchFrame data-testid="rotation-radar-leader-list">
                  <div className="grid min-w-0 gap-0 md:grid-cols-[minmax(0,1.55fr)_minmax(260px,0.65fr)]">
                    <section className="min-w-0 border-b border-white/[0.05] md:border-b-0 md:border-r md:border-white/[0.05]">
                      <div className="flex min-w-0 items-start justify-between gap-3 border-b border-white/[0.05] px-3 py-3">
                        <TerminalSectionHeader eyebrow={libraryMode ? '主题库浏览' : '领先主题'} title={headlineThemes.length ? (libraryMode ? `${headlineThemes.length} 个主题分类条目` : `Top ${headlineThemes.length} 主题强弱`) : (libraryMode ? '暂无可展示主题' : '暂无头部排名')} />
                        <div className="hidden min-w-0 grid-cols-[4.75rem_4.75rem_4.5rem] gap-2 text-right text-[10px] font-semibold uppercase text-white/32 md:grid">
                          <span>相对</span>
                          <span>量能</span>
                          <span>广度</span>
                        </div>
                      </div>
                      {headlineThemes.length ? (
                        <DenseRows>
                          {headlineThemes.map((theme, index) => (
                            <LeaderRow
                              key={theme.id}
                              theme={theme}
                              rank={index + 1}
                              libraryMode={libraryMode}
                              selected={selectedTheme?.id === theme.id}
                              onSelect={() => {
                                setSelectedThemeId(theme.id);
                                setProxyDisclosureSeed((seed) => seed + 1);
                              }}
                            />
                          ))}
                        </DenseRows>
                      ) : (
                        <div className="p-3">
                          <TerminalEmptyState className="min-h-[104px] justify-start text-sm text-white/42">
                            {payload.summary.noHeadlineReason || '没有可用于头部排名'}
                          </TerminalEmptyState>
                        </div>
                      )}
                    </section>

                    <aside className="min-w-0">
                      <div className="border-b border-white/[0.05] px-3 py-3">
                        <TerminalSectionHeader eyebrow="待确认 / 分歧" title={libraryMode ? '升级前的缺口与分歧' : '观察退潮与分歧'} />
                      </div>
                      {weakeningThemes.length ? (
                        <DenseRows>
                          {weakeningThemes.map((theme) => (
                            <LaggardRow
                              key={theme.id}
                              theme={theme}
                              libraryMode={libraryMode}
                              selected={selectedTheme?.id === theme.id}
                              onSelect={() => {
                                setSelectedThemeId(theme.id);
                                setProxyDisclosureSeed((seed) => seed + 1);
                              }}
                            />
                          ))}
                        </DenseRows>
                      ) : (
                        <div className="p-3">
                          <TerminalEmptyState className="min-h-[72px] justify-start text-sm text-white/42">暂无降温主题。</TerminalEmptyState>
                        </div>
                      )}
                    </aside>
                  </div>
                </DataWorkbenchFrame>

                <BucketPanel buckets={buckets} />

                <DataWorkbenchFrame data-testid="rotation-radar-universe-list">
                  <div className="border-b border-white/[0.05] px-3 py-3">
                    <TerminalSectionHeader
                      eyebrow="主题 / 行业板"
                      title={libraryMode ? `${filteredThemes.length}/${payload.themes.length} 个主题库条目` : `${filteredThemes.length}/${payload.themes.length} 个条目，紧凑选择。`}
                    />
                  </div>
                  <div className="max-h-80 overflow-y-auto no-scrollbar">
                    {filteredThemes.length ? (
                      <DenseRows>
                        {filteredThemes.map((theme) => (
                          <CompactThemeRow
                            key={theme.id}
                            theme={theme}
                            libraryMode={libraryMode}
                            selected={selectedTheme?.id === theme.id}
                            onSelect={() => {
                              setSelectedThemeId(theme.id);
                              setProxyDisclosureSeed((seed) => seed + 1);
                            }}
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
              </section>

              <div className="min-w-0 xl:col-span-4">
                <ThemeDetailPanel
                  diagnostics={payload.etfLeadershipDiagnostics}
                  theme={selectedTheme}
                  libraryMode={libraryMode}
                  proxyResetKey={proxyDisclosureSeed}
                />
              </div>
            </TerminalGrid>

            <TerminalDisclosure
              data-testid="rotation-radar-mechanics-details"
              title="证据边界 / 来源说明"
              summary="默认折叠"
              className="rounded-2xl p-4 text-sm text-white/55"
            >
              <div className="grid gap-3 text-[11px] text-white/46">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <TerminalChip>{marketLabel(payload.market || selectedMarket)}</TerminalChip>
                  <TerminalChip>{payload.sourceLabel || '待确认'}</TerminalChip>
                  <DataFreshnessBadge freshness={payload.freshness || 'fallback'} className="px-1.5 text-[9px]" />
                  <TerminalChip>Top-N {headlineThemes.length}/{payload.themes.length}</TerminalChip>
                </div>
                <Gauge className="h-4 w-4 text-cyan-200/70" aria-hidden="true" />
                <span>当前页面优先解释主题轮动、相对强弱与代理证据边界，不自动放大为真实资金流结论。</span>
                <Signal className="ml-2 h-4 w-4 text-emerald-200/70" aria-hidden="true" />
                <span>不代表实时方向建议，不触发交易、通知、组合或新的外部数据请求。</span>
                <Waves className="ml-2 h-4 w-4 text-white/40" aria-hidden="true" />
                <span>{conservativeFlowCopy(payload.noAdviceDisclosure, shouldAllowMoneyFlowLanguage(selectedTheme))}</span>
              </div>
            </TerminalDisclosure>
          </>
        ) : null}
      </WideWorkspacePageShell>
    </div>
  );
};

export default MarketRotationRadarPage;
