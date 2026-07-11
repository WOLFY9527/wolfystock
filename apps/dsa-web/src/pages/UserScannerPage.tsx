import React, { Suspense, lazy } from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowDownUp,
  BookmarkPlus,
  ChevronDown,
  Copy,
  Download,
  History,
  LineChart,
  MoreHorizontal,
  Play,
  Sparkles,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import {
  buildConsumerResearchReadinessView,
  buildScannerTopDownContextView,
  inferScannerResearchReadiness,
} from '../api/researchReadiness';
import {
  scannerApi,
  type ScannerDataReadiness,
  type ScannerOperationalStatusWithDataReadiness,
} from '../api/scanner';
import { watchlistApi } from '../api/watchlist';
import ConsumerResearchReadinessStrip from '../components/common/ConsumerResearchReadinessStrip';
import ObservationOnlyBoundary from '../components/common/ObservationOnlyBoundary';
import { SupportBanner } from '../components/common/SupportSurface';
import ResearchWorkspaceFlowPanel from '../components/research/ResearchWorkspaceFlowPanel';
import { ScannerActionButton as ActionButton } from '../components/scanner/ScannerActionButton';
import ScannerTopDownContextStrip from '../components/scanner/ScannerTopDownContextStrip';
import {
  ScannerCandidateDetailPanel,
  ScannerCandidateDiagnosticRow,
} from '../components/scanner/ScannerCandidatePresenters';
import { ScannerCandidateEvidenceStrip } from '../components/scanner/ScannerCandidateEvidenceStrip';
import ScannerCandidateResearchSummary, {
  type ScannerCandidateResearchSummaryFrame,
} from '../components/scanner/ScannerCandidateResearchSummary';
import ScannerCandidateResearchPacket from '../components/scanner/ScannerCandidateResearchPacket';
import {
  AdvancedDisclosure,
  FieldChip,
} from '../components/scanner/ScannerDisplayAtoms';
import {
  PillTagGroup,
  ScannerConclusionBand,
  ScannerHistoryFallbackPanel,
  ScannerResultHistorySummary,
  ScannerVisualEvidenceSummaryPanel,
  ScannerWorkflowSummaryPanel,
} from '../components/scanner/ScannerDisplayPanels';
import { ScannerStrategySimulationPanelFallback } from '../components/scanner/ScannerStrategySimulationPanelFallback';
import {
  ScannerHistoryDrawer,
  type ScannerHistoryDrawerItem,
} from '../components/scanner/ScannerHistoryDrawer';
import {
  ScannerDiagnosticsPanel,
} from '../components/scanner/ScannerDiagnosticsPanel';
import {
  useScannerBacktestLab,
} from '../components/scanner/useScannerBacktestLab';
import type { ScannerBacktestItem } from '../components/scanner/scannerBacktestShared';
import {
  TerminalButton,
} from '../components/terminal/TerminalPrimitives';
import {
  CompactEmptyRow,
  DenseCommandBar,
  DensePageHeader,
  DenseStatusStrip,
  DenseTableShell,
} from '../components/terminal/DenseWorkbenchPrimitives';
import { WolfyShellSurface } from '../components/linear/LinearPrimitives';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import { useI18n } from '../contexts/UiLanguageContext';
import {
  getSafariReadySurfaceClassName,
  shouldApplySafariA11yGuard,
  useSafariRenderReady,
  useSafariWarmActivation,
} from '../hooks/useSafariInteractionReady';
import { useProductSurface } from '../hooks/useProductSurface';
import type { SourceProvenanceSummary } from '../types/analysis';
import type {
  ScannerCandidate,
  ScannerCandidateResearchPacket as ScannerCandidateResearchPacketModel,
  ScannerCandidateDiagnostic,
  ScannerCandidateDiagnosticStatus,
  ScannerCoverageSummary,
  ScannerCandidateOutcome,
  ScannerLabeledValue,
  ScannerReviewSummary,
  ScannerRunDetail,
  ScannerRunHistoryItem,
  ScannerRunRequest,
  ScannerStrategySimulationResult,
  ScannerThemeSuggestion,
  ScannerTheme,
  ScannerWatchlistComparison,
} from '../types/scanner';
import type { ResearchReadinessV1 } from '../types/researchReadiness';
import type { WatchlistItem } from '../types/watchlist';
import { buildLocalizedPath } from '../utils/localeRouting';
import { buildResearchWorkspacePath } from '../utils/researchWorkspaceRoute';
import { serializeCsvCell } from '../utils/csvExport';
import { normalizeScannerEvidence } from '../utils/evidenceDisplay';
import type { TrustDisclosureBucket } from '../utils/trustDisclosure';
import { sanitizeUserFacingDataIssue } from '../utils/userFacingDataIssues';
import { getConsumerSafeApiErrorCopy } from '../utils/consumerErrorCopy';
import {
  consumerSafeOperatorAction,
  getConsumerDataStateEntry,
  sanitizeConsumerDataStateText,
} from '../utils/consumerDataStateVocabulary';
import {
  getScannerDetailOptions,
  getScannerProfileOptions,
  getScannerUniverseOptions,
  SCANNER_PROFILE_DEFAULTS,
} from './scannerPageShared';
import type { CandidateEvidenceFrame } from '../components/scanner/ScannerCandidateEvidenceStrip';

const LazyScannerStrategySimulationPanel = lazy(async () => {
  const module = await import('../components/scanner/ScannerStrategySimulationPanel');
  return { default: module.ScannerStrategySimulationPanel };
});

const LazyScannerBacktestLab = lazy(async () => {
  const module = await import('../components/scanner/ScannerBacktestLab');
  return { default: module.ScannerBacktestLab };
});

const {
  getRunCoverageSummary,
  getRunProviderDiagnostics,
  hasRunDiagnosticsContent,
} = ScannerDiagnosticsPanel;

const HISTORY_PAGE_SIZE = 8;

type CandidateFilter = 'selected' | 'pool' | 'rejected' | 'data_failed' | 'all';
type SortKey = 'score' | 'symbol' | 'target' | 'risk';
type SortDirection = 'asc' | 'desc';
type ScanScope = 'default' | 'theme' | 'symbols';
type ActionNotice = { tone: 'success' | 'warning' | 'danger'; message: string } | null;
type ScannerComparisonState = {
  previousRun: ScannerRunDetail | null;
  bySymbol: Map<string, CandidateComparison>;
  chips: string[];
};
type CandidateComparison = {
  scoreDelta: number | null;
  rankDelta: number | null;
  previousStatus: ScannerCandidateDiagnosticStatus | null;
  currentStatus: ScannerCandidateDiagnosticStatus;
  label: string;
};
type ScannerRunSummary = {
  title: string;
  statusLabel: string;
  bestCandidate: string;
  candidateCount: number;
  rejectedCount: number;
  failedCount: number;
  dataStatusLabel: string;
  durationLabel: string;
  runTimeLabel: string;
  errorSummary: string | null;
  unavailable?: boolean;
  unavailableTitle?: string;
  unavailableBody?: string;
};
type ScannerHistoryResolution = {
  hasLoaded: boolean;
  latestRun: ScannerRunHistoryItem | null;
};
type ScannerTrustSummary = {
  cappedCount: number;
  fallbackCount: number;
  proxyCount: number;
  staleCount: number;
  partialCount: number;
  limitedCount: number;
  buckets: TrustDisclosureBucket[];
  terms: string[];
};
type ScannerConclusionModel = {
  state: 'waiting' | 'top-candidate' | 'no-candidate' | 'insufficient';
  title: string;
  detail: string;
  candidateCount: number;
  trustSummary: ScannerTrustSummary;
  tone: 'neutral' | 'success' | 'caution' | 'danger';
};
type ScannerWorkbenchEmptyState = {
  title: string;
  body: string;
};
type ScannerWorkspaceState = 'idle' | 'loading' | 'blocked' | 'empty' | 'error' | 'ready';
type ScannerSafeEmptyReason = {
  label: string;
  body: string;
};
type ScannerDataReadinessView = {
  stateLabel: string;
  blockerLabel: string | null;
  nextDataLabel: string | null;
  coverageChips: ScannerLabeledValue[];
  readinessLayers: ScannerLabeledValue[];
  isMeaningful: boolean;
};
type ScannerVisualSummaryBarSegment = {
  key: string;
  label: string;
  count: number;
  toneClassName: string;
};
type ScannerVisualEvidenceSummaryModel = {
  totalRows: number;
  scoreBands: ScannerVisualSummaryBarSegment[];
  candidateCoverageSegments: ScannerVisualSummaryBarSegment[];
  marketCoverageSegments: ScannerVisualSummaryBarSegment[];
  candidateReadinessItems: ScannerLabeledValue[];
  nextEvidenceLabel: string | null;
};
type ScannerValidationErrors = {
  run?: string;
  customSymbols?: string;
  theme?: string;
  customThemeLabel?: string;
  customThemePrompt?: string;
  customThemeManualSymbols?: string;
};

type ScannerCandidateWithEvidence = ScannerCandidate & {
  candidateEvidenceFrame?: CandidateEvidenceFrame | null;
  candidateResearchReadiness?: ResearchReadinessV1 | null;
  candidateResearchSummaryFrame?: ScannerCandidateResearchSummaryFrame | null;
  candidateResearchPacket?: ScannerCandidateResearchPacketModel | null;
  candidateSourceProvenanceFrame?: SourceProvenanceSummary | null;
};

type ScannerRunFeedback = {
  tone: 'default' | 'warning' | 'success' | 'danger';
  title: string;
  body: string;
};

function normalizeCandidateSymbol(symbol?: string | null): string | null {
  const normalized = String(symbol || '').trim().toUpperCase();
  return normalized || null;
}

function withCandidateEvidence(candidate: ScannerCandidate): ScannerCandidateWithEvidence {
  return candidate as ScannerCandidateWithEvidence;
}

function getCandidateIdentity(candidate: ScannerCandidate): string {
  return normalizeCandidateSymbol(candidate.symbol) || `no-symbol-${candidate.rank}`;
}

function normalizeScannerMarket(market?: string | null): string | null {
  const normalized = String(market || '').trim().toUpperCase();
  return normalized === 'CN' || normalized === 'US' || normalized === 'HK' ? normalized : null;
}

function sanitizeScannerProfileLabel(label?: string | null): string {
  const raw = String(label || '').trim();
  if (!raw) return '';
  if (raw === 'cn_preopen_v1') return 'A股盘前扫描';
  if (raw === 'us_preopen_v1') return 'US Pre-open Scanner';
  if (raw === 'hk_preopen_v1') return 'HK Pre-open Scanner';
  return raw
    .replace(/^[A-Z]{2}\s*[·-]\s*/u, '')
    .replace(/\s+v\d+$/iu, '')
    .trim();
}

function getWatchlistIdentity(market?: string | null, symbol?: string | null): string {
  const normalizedMarket = normalizeScannerMarket(market);
  const normalizedSymbol = normalizeCandidateSymbol(symbol);
  return normalizedMarket && normalizedSymbol ? `${normalizedMarket}:${normalizedSymbol}` : normalizedSymbol || '';
}

function buildWatchlistNotes(candidate: ScannerCandidate, runDetail: ScannerRunDetail | null, language: 'zh' | 'en'): string | null {
  const notes = [
    getKeyReason(candidate, runDetail, language),
    getRiskSummary(candidate, language),
    candidate.aiInterpretation?.watchPlan,
  ].filter((item): item is string => Boolean(item));
  return notes.length ? notes.slice(0, 3).join(language === 'en' ? ' | ' : ' ｜ ') : null;
}

function getWatchlistActionLabel(
  isTracked: boolean,
  isPending: boolean,
  isAuthBlocked: boolean,
  language: 'zh' | 'en',
): string {
  if (isPending) {
    return language === 'en' ? 'Saving...' : '保存中...';
  }
  if (isTracked) {
    return language === 'en' ? 'Tracked' : '已追踪';
  }
  if (isAuthBlocked) {
    return language === 'en' ? 'Sign in to track' : '登录后可追踪';
  }
  return language === 'en' ? 'Track' : '追踪';
}

function getWatchlistActionTitle(
  isTracked: boolean,
  isAuthBlocked: boolean,
  language: 'zh' | 'en',
): string | undefined {
  if (isTracked) {
    return language === 'en' ? 'This candidate is already tracked.' : '该候选已在观察名单中。';
  }
  if (isAuthBlocked) {
    return language === 'en' ? 'Sign in to save candidates to your watchlist.' : '请登录后再保存候选到你的观察名单。';
  }
  return language === 'en' ? 'Save this candidate to your watchlist.' : '保存到你的观察名单。';
}

function normalizeLabel(label?: string | null): string {
  return (label || '').trim().toLowerCase();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function getNestedRecord(parent: Record<string, unknown> | null, ...keys: string[]): Record<string, unknown> | null {
  for (const key of keys) {
    const value = parent?.[key];
    if (isRecord(value)) return value;
  }
  return null;
}

function getNestedString(parent: Record<string, unknown> | null, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = parent?.[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}

function getNestedNumber(parent: Record<string, unknown> | null, ...keys: string[]): number | null {
  for (const key of keys) {
    const value = parent?.[key];
    if (typeof value === 'number' && Number.isFinite(value)) return value;
  }
  return null;
}

function getNestedBoolean(parent: Record<string, unknown> | null, ...keys: string[]): boolean | null {
  for (const key of keys) {
    const value = parent?.[key];
    if (typeof value === 'boolean') return value;
  }
  return null;
}

function getNestedStringArray(parent: Record<string, unknown> | null, ...keys: string[]): string[] {
  for (const key of keys) {
    const value = parent?.[key];
    if (Array.isArray(value)) {
      return value.flatMap((item) => {
        const normalized = typeof item === 'string' ? item.trim() : '';
        return normalized ? [normalized] : [];
      });
    }
  }
  return [];
}

function addUniqueBucket(buckets: TrustDisclosureBucket[], bucket: TrustDisclosureBucket) {
  if (!buckets.includes(bucket)) buckets.push(bucket);
}

function normalizeScannerDataReadinessState(value?: string | null): string {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

const SCANNER_DATA_READINESS_STATE_LABELS: Record<string, { zh: string; en: string }> = {
  ready: { zh: '可扫描', en: 'Ready to scan' },
  partial: { zh: '部分可用', en: 'Partially ready' },
  blocked: { zh: '数据待补', en: 'Data blocked' },
  unknown: { zh: '待确认', en: 'To confirm' },
  not_run: { zh: '未运行', en: 'Not run' },
};

const SCANNER_DATA_READINESS_BLOCKER_LABELS: Record<string, { zh: string; en: string }> = {
  missing_universe: { zh: '标的池待补', en: 'Scope pending' },
  universe_missing: { zh: '标的池缺失', en: 'Scope missing' },
  universe_not_configured: { zh: '标的池未配置', en: 'Scope not configured' },
  stale_universe: { zh: '标的池待更新', en: 'Scope stale' },
  empty_universe: { zh: '标的池为空', en: 'Scope empty' },
  insufficient_coverage: { zh: '覆盖不足', en: 'Coverage insufficient' },
  missing_quote_snapshot: { zh: '报价信息待补', en: 'Quote input pending' },
  missing_history: { zh: '历史数据待补', en: 'History pending' },
  stale_history: { zh: '历史数据待更新', en: 'History refresh pending' },
  profile_filters_rejected_all: { zh: '条件过窄', en: 'Filters too narrow' },
  source_quality_capped: { zh: '来源质量受限', en: 'Source quality limited' },
  scanner_runtime_unavailable: { zh: '扫描服务待恢复', en: 'Scanner service pending' },
  unknown: { zh: '待确认', en: 'To confirm' },
};

const SCANNER_DATA_CLASS_LABELS: Record<string, { zh: string; en: string }> = {
  universe: { zh: '标的池行情', en: 'Scope quotes' },
  historical_ohlcv: { zh: '历史日线', en: 'Price history' },
  quote_snapshot: { zh: '实时报价', en: 'Realtime quotes' },
};

const SCANNER_DATA_READINESS_COVERAGE_LABELS: Record<string, { zh: string; en: string }> = {
  available: { zh: '可用', en: 'Available' },
  partial: { zh: '部分可用', en: 'Partial' },
  unknown: { zh: '待确认', en: 'Unknown' },
  stale: { zh: '待更新', en: 'Stale' },
  missing: { zh: '待补', en: 'Missing' },
  not_configured: { zh: '未配置', en: 'Not configured' },
  insufficient_coverage: { zh: '覆盖不足', en: 'Insufficient coverage' },
  unavailable: { zh: '不可用', en: 'Unavailable' },
};

function localizedDataReadinessLabel(
  value: string | null | undefined,
  mapping: Record<string, { zh: string; en: string }>,
  language: 'zh' | 'en',
): string | null {
  const normalized = normalizeScannerDataReadinessState(value);
  if (!normalized) return null;
  return mapping[normalized]?.[language] || null;
}

function sanitizeScannerDataReadinessText(value: string | null | undefined, language: 'zh' | 'en'): string | null {
  const text = String(value || '').trim();
  if (!text) return null;
  if (/provider|debug|trace|schema|raw|request|cache|runtime|sourceauthority|blockerbucket|pipeline|dry[-_\s]?run|\bscanner\b/i.test(text)) {
    return sanitizeConsumerDataStateText(text, 'partial');
  }
  return sanitizeUserFacingDataIssue(text, language);
}

function scannerDataClassLabel(value: string, language: 'zh' | 'en'): string {
  const normalized = normalizeScannerDataReadinessState(value);
  return SCANNER_DATA_CLASS_LABELS[normalized]?.[language]
    || getConsumerDataStateEntry(normalized).label;
}

function buildScannerDataReadinessView(
  readiness: ScannerDataReadiness | null | undefined,
  language: 'zh' | 'en',
): ScannerDataReadinessView | null {
  if (!readiness) return null;
  const state = normalizeScannerDataReadinessState(readiness.state);
  const universeReadiness = readiness.scannerUniverseReadiness || null;
  const universeStatus = normalizeScannerDataReadinessState(universeReadiness?.status);
  const blockerBucket = normalizeScannerDataReadinessState(readiness.blockerBucket);
  const stateLabel = localizedDataReadinessLabel(state, SCANNER_DATA_READINESS_STATE_LABELS, language)
    || (language === 'en' ? 'To confirm' : '待确认');
  const universeBlockerLabel = universeStatus && universeStatus !== 'available'
    ? localizedDataReadinessLabel(
      universeStatus === 'stale' ? 'stale_universe' : universeStatus,
      SCANNER_DATA_READINESS_BLOCKER_LABELS,
      language,
    ) || localizedDataReadinessLabel(universeStatus, SCANNER_DATA_READINESS_COVERAGE_LABELS, language)
    : null;
  const blockerLabel = universeBlockerLabel || (blockerBucket && blockerBucket !== 'unknown'
    ? localizedDataReadinessLabel(blockerBucket, SCANNER_DATA_READINESS_BLOCKER_LABELS, language)
      || (language === 'en' ? 'To confirm' : '待确认')
    : null);
  const operatorAction = universeReadiness?.operatorNextAction;
  const nextDataLabel = sanitizeScannerDataReadinessText(universeReadiness?.consumerSafeMessage, language)
    || sanitizeScannerDataReadinessText(readiness.nextDataAction, language)
    || sanitizeScannerDataReadinessText(readiness.consumerSummary, language)
    || (operatorAction ? consumerSafeOperatorAction(operatorAction, universeStatus || state) : null)
    || blockerLabel;
  const coverageChips = [
    universeStatus ? {
      label: language === 'en' ? 'Scope readiness' : '标的池状态',
      value: localizedDataReadinessLabel(universeStatus, SCANNER_DATA_READINESS_COVERAGE_LABELS, language)
        || (language === 'en' ? 'To confirm' : '待确认'),
    } : null,
    readiness.quoteCoverage ? { label: language === 'en' ? 'Quote' : '报价', value: localizedDataReadinessLabel(readiness.quoteCoverage, SCANNER_DATA_READINESS_COVERAGE_LABELS, language) || (language === 'en' ? 'To confirm' : '待确认') } : null,
    readiness.historyCoverage ? { label: language === 'en' ? 'History' : '历史', value: localizedDataReadinessLabel(readiness.historyCoverage, SCANNER_DATA_READINESS_COVERAGE_LABELS, language) || (language === 'en' ? 'To confirm' : '待确认') } : null,
    readiness.universeSize != null ? { label: language === 'en' ? 'Scope' : '标的池', value: String(readiness.universeSize) } : null,
    universeReadiness?.missingDataClasses?.length ? {
      label: language === 'en' ? 'Missing' : '缺口',
      value: universeReadiness.missingDataClasses.slice(0, 3)
        .map((item) => scannerDataClassLabel(String(item), language))
        .join(' / '),
    } : null,
  ].filter((item): item is ScannerLabeledValue => Boolean(item));
  const quoteLabel = readiness.quoteCoverage
    ? localizedDataReadinessLabel(readiness.quoteCoverage, SCANNER_DATA_READINESS_COVERAGE_LABELS, language)
      || (language === 'en' ? 'To confirm' : '待确认')
    : null;
  const historyLabel = readiness.historyCoverage
    ? localizedDataReadinessLabel(readiness.historyCoverage, SCANNER_DATA_READINESS_COVERAGE_LABELS, language)
      || (language === 'en' ? 'To confirm' : '待确认')
    : null;
  const membershipLabel = universeBlockerLabel
    || (universeStatus
      ? localizedDataReadinessLabel(universeStatus, SCANNER_DATA_READINESS_COVERAGE_LABELS, language)
        || (language === 'en' ? 'To confirm' : '待确认')
      : readiness.universeSize != null
        ? (language === 'en' ? `${readiness.universeSize} symbols` : `${readiness.universeSize} 个标的`)
        : stateLabel);
  const marketDataParts = [quoteLabel, historyLabel].filter(Boolean);
  const marketDataLabel = marketDataParts.length
    ? marketDataParts.join(language === 'en' ? ' / ' : ' / ')
    : (readiness.freshness
      ? localizedDataReadinessLabel(readiness.freshness, SCANNER_DATA_READINESS_COVERAGE_LABELS, language)
        || stateLabel
      : stateLabel);
  const candidateGenerationLabel = readiness.selectedCount != null
    ? (language === 'en'
      ? `${readiness.selectedCount} selected${readiness.rejectedCount != null ? ` / ${readiness.rejectedCount} filtered` : ''}`
      : `产出 ${readiness.selectedCount} 个${readiness.rejectedCount != null ? ` / 过滤 ${readiness.rejectedCount} 个` : ''}`)
    : blockerLabel || stateLabel;
  const readinessLayers = [
    {
      label: language === 'en' ? 'Universe membership' : '标的池成员',
      value: membershipLabel,
    },
    {
      label: language === 'en' ? 'Market data' : '市场数据',
      value: marketDataLabel,
    },
    {
      label: language === 'en' ? 'Candidate generation' : '候选生成',
      value: candidateGenerationLabel,
    },
  ];

  return {
    stateLabel,
    blockerLabel,
    nextDataLabel,
    coverageChips,
    readinessLayers,
    isMeaningful: ['ready', 'partial', 'blocked'].includes(state) || Boolean(blockerLabel) || Boolean(universeStatus),
  };
}

function firstScannerValidationMessage(errors: ScannerValidationErrors): string | null {
  return errors.run
    || errors.customSymbols
    || errors.theme
    || errors.customThemeLabel
    || errors.customThemePrompt
    || errors.customThemeManualSymbols
    || null;
}

function getRunDetailDataReadiness(runDetail: ScannerRunDetail | null): ScannerDataReadiness | null {
  const diagnostics = runDetail?.diagnostics as (ScannerRunDetail['diagnostics'] & {
    dataReadiness?: ScannerDataReadiness;
  }) | undefined;
  return diagnostics?.dataReadiness || null;
}

function getScannerEvidencePayload(candidate: ScannerCandidate | ScannerCandidateDiagnostic): Record<string, unknown> | null {
  const containers = [
    isRecord((candidate as ScannerCandidate).diagnostics) ? (candidate as ScannerCandidate).diagnostics : null,
    isRecord((candidate as ScannerCandidateDiagnostic).metadata) ? (candidate as ScannerCandidateDiagnostic).metadata : null,
  ].filter((value): value is Record<string, unknown> => Boolean(value));

  for (const container of containers) {
    if (isRecord(container.evidence_packet) || isRecord(container.evidencePacket)) {
      return container;
    }
  }

  return null;
}

function getScannerEvidenceSummary(candidate: ScannerCandidate | ScannerCandidateDiagnostic) {
  const payload = getScannerEvidencePayload(candidate);
  return payload ? normalizeScannerEvidence(payload) : null;
}

function stripScannerConsumerTrustSource(source: ScannerCandidate | ScannerCandidateDiagnostic): ScannerCandidate | ScannerCandidateDiagnostic {
  if ('metadata' in source) {
    return {
      ...source,
      metadata: {},
    };
  }
  return {
    ...source,
    diagnostics: {},
  };
}

function consumerTrustNoticeFromBuckets(buckets: TrustDisclosureBucket[], language: 'zh' | 'en'): string | null {
  if (buckets.includes('stale') || buckets.includes('fallback')) {
    return language === 'en'
      ? 'Some results use the latest available data.'
      : '部分结果使用最近一次可用数据。';
  }
  if (buckets.includes('partial') || buckets.includes('proxy')) {
    return language === 'en'
      ? 'Some scan data is temporarily unavailable; current results are for observation.'
      : '部分扫描数据暂不可用，当前结果仅供观察。';
  }
  if (buckets.includes('confidence') || buckets.includes('observe-only')) {
    return language === 'en'
      ? 'Current candidate confidence is low.'
      : '当前候选信号置信度较低。';
  }
  return null;
}

function getScannerConsumerQualityNotice(source: ScannerCandidate | ScannerCandidateDiagnostic, language: 'zh' | 'en'): string | null {
  return consumerTrustNoticeFromBuckets(scannerTrustBucketsForSource(source).buckets, language);
}

function parseFirstNumericValue(value?: string | null): number | null {
  if (!value) return null;
  const match = value.match(/-?\d+(?:\.\d+)?/);
  if (!match) return null;
  const parsed = Number.parseFloat(match[0]);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatPercent(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return '--';
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
}

const SCANNER_DATE_TIME_FORMATTERS = {
  en: new Intl.DateTimeFormat('en-US', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }),
  zh: new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }),
} as const;

const SCANNER_DATE_ONLY_FORMATTERS = {
  en: new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }),
  zh: new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }),
} as const;

function formatTimestamp(value?: string | null, language: 'zh' | 'en' = 'zh'): string {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return SCANNER_DATE_TIME_FORMATTERS[language].format(date);
}

function formatDurationMs(startedAt?: string | null, completedAt?: string | null): string {
  const durationMs = getElapsedDurationMs(startedAt, completedAt);
  if (durationMs == null || durationMs <= 0) return '--';
  if (durationMs < 1000) return `${durationMs}ms`;
  const seconds = Math.round(durationMs / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}

function getElapsedDurationMs(startedAt?: string | null, completedAt?: string | null): number | null {
  if (!startedAt || !completedAt) return null;
  const started = new Date(startedAt).getTime();
  const completed = new Date(completedAt).getTime();
  if (!Number.isFinite(started) || !Number.isFinite(completed) || completed < started) return null;
  return completed - started;
}

function getScannerRunDurationMs(runDetail: ScannerRunDetail | null): number | null {
  return getElapsedDurationMs(runDetail?.runAt, runDetail?.completedAt);
}

function isScannerPseudoEmptyRun(runDetail: ScannerRunDetail | null): boolean {
  if (!runDetail) return false;
  const selectedCount = getFiniteCount(runDetail.summary?.selectedCount) ?? runDetail.shortlist?.length ?? runDetail.selected?.length ?? 0;
  const rejectedCount = getFiniteCount(runDetail.summary?.rejectedCount) ?? 0;
  const dataFailedCount = getFiniteCount(runDetail.summary?.dataFailedCount) ?? 0;
  const errorCount = getFiniteCount(runDetail.summary?.errorCount) ?? 0;
  const evaluatedCount = getFiniteCount(runDetail.summary?.evaluatedCount) ?? getFiniteCount(runDetail.evaluatedSize) ?? 0;
  const durationMs = getScannerRunDurationMs(runDetail);
  const hasRows = Boolean(runDetail.shortlist?.length || runDetail.selected?.length || getCandidateDiagnostics(runDetail).length);
  const noOutcomeCounts = selectedCount === 0 && rejectedCount === 0 && dataFailedCount === 0 && errorCount === 0 && evaluatedCount === 0;
  const lacksRunEvidence = durationMs == null || durationMs <= 50;
  return normalizeRunState(runDetail.status) !== 'failed'
    && noOutcomeCounts
    && !hasRows
    && lacksRunEvidence;
}

function normalizeRunState(value?: string | null): string {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function compactScannerStateLabel(value?: string | null, language: 'zh' | 'en' = 'zh'): string {
  const normalized = normalizeRunState(value);
  if (['success', 'succeeded', 'completed', 'complete', 'ready'].includes(normalized)) return language === 'en' ? 'Completed' : '完成';
  if (['failed', 'failure', 'error', 'data_failed'].includes(normalized)) return language === 'en' ? 'Failed' : '失败';
  if (normalized === 'timeout' || normalized === 'timed_out' || normalized.includes('timeout')) return language === 'en' ? 'Timeout' : '超时';
  if (['empty', 'no_candidates', 'no_candidate', 'no_shortlist'].includes(normalized)) return language === 'en' ? 'No candidates' : '无候选';
  if (['insufficient_data', 'data_insufficient', 'not_enough_history', 'missing_history'].includes(normalized)) return language === 'en' ? 'Insufficient data' : '数据不足';
  if (['provider_down', 'provider_error', 'provider_failed', 'data_source_error'].includes(normalized)) return language === 'en' ? 'Data unavailable' : '数据暂不可用';
  if (['local_data', 'local', 'local_cache', 'local_snapshot'].includes(normalized)) return language === 'en' ? 'Recent available data' : '最近可用数据';
  if (['fallback', 'fallback_data', 'degraded'].includes(normalized)) return language === 'en' ? 'Recent available data' : '最近可用数据';
  if (['partial', 'partial_data', 'partial_success'].includes(normalized)) return language === 'en' ? 'Partial data' : '部分数据';
  if (!normalized || normalized === 'unknown') return language === 'en' ? 'Unconfirmed' : '未确认';
  return language === 'en' ? 'Unconfirmed' : '未确认';
}

function sanitizeScannerErrorSummary(value?: string | null, language: 'zh' | 'en' = 'zh'): string | null {
  const normalized = normalizeRunState(value);
  if (!normalized) return null;
  if (normalized.includes('timeout')) return language === 'en' ? 'Timeout' : '超时';
  if (String(value || '').includes('超时')) return language === 'en' ? 'Timeout' : '超时';
  if (normalized.includes('provider')) return language === 'en' ? 'Data unavailable' : '数据暂不可用';
  if (normalized.includes('history') || normalized.includes('missing') || normalized.includes('insufficient') || normalized.includes('not_enough')) {
    return language === 'en' ? 'Insufficient data' : '数据不足';
  }
  if (String(value || '').includes('不可用') || String(value || '').includes('缺失') || String(value || '').includes('不足')) {
    return language === 'en' ? 'Insufficient data' : '数据不足';
  }
  if (normalized.includes('candidate') || normalized.includes('shortlist') || normalized === 'empty') return language === 'en' ? 'No candidates' : '无候选';
  if (normalized.includes('fallback')) return language === 'en' ? 'Recent available data' : '最近可用数据';
  if (normalized.includes('local')) return language === 'en' ? 'Recent available data' : '最近可用数据';
  if (normalized.includes('partial')) return language === 'en' ? 'Partial data' : '部分数据';
  if (normalized.includes('failed') || normalized.includes('error')) return language === 'en' ? 'Failed' : '失败';
  return compactScannerStateLabel(value, language);
}

function formatDateOnly(value?: string | null, language: 'zh' | 'en' = 'zh'): string {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return SCANNER_DATE_ONLY_FORMATTERS[language].format(date);
}

function findCandidateValue(
  candidate: ScannerCandidate,
  keywords: string[],
): string | null {
  const entries = [
    ...(candidate.keyMetrics || []),
    ...(candidate.watchContext || []),
    ...(candidate.featureSignals || []),
  ];
  const match = entries.find((entry) => keywords.some((keyword) => normalizeLabel(entry.label).includes(keyword)));
  return match?.value?.trim() || null;
}

function getEntryRange(candidate: ScannerCandidate): string | null {
  return findCandidateValue(candidate, ['建仓', '入场', 'entry', 'buy', 'support']);
}

function getTargetPrice(candidate: ScannerCandidate): string | null {
  return findCandidateValue(candidate, ['目标', 'target', 'tp', 'resistance']);
}

function getStopLoss(candidate: ScannerCandidate): string | null {
  return findCandidateValue(candidate, ['止损', 'stop', 'invalid']);
}

function getRiskScore(candidate: ScannerCandidate): number | null {
  const riskValue = findCandidateValue(candidate, ['risk score', 'risk/score', '风险评分', '风险分']);
  return parseFirstNumericValue(riskValue);
}

function isInternalScannerIssue(value?: string | null): boolean {
  const raw = String(value || '').trim();
  const lowered = raw.toLowerCase();
  const normalized = normalizeRunState(value);
  if (!normalized) return false;
  return /provider|timeout|schema|debug|raw|trace|cache|not_enough|unavailable|missing|insufficient|data_failed|technical_indicators|fundamentals|earnings|optional_news|universe|historical|ohlcv|quote|snapshot|packet|handoff|evidence|famil(?:y|ies)|peer/.test(normalized)
    || /\buniverse\s*\/\s*historical\s+ohlcv\s*\/\s*quote\s+snapshot\b/i.test(lowered);
}

function sanitizeScannerUserText(value: string | null | undefined, language: 'zh' | 'en', fallback: string): string {
  const text = String(value || '').trim();
  if (!text) return fallback;
  return isInternalScannerIssue(text) ? sanitizeUserFacingDataIssue(text, language) : text;
}

function sanitizeScannerNotes(notes: Array<string | null | undefined>, language: 'zh' | 'en'): string[] {
  return notes.reduce<string[]>((items, item) => {
    if (!String(item || '').trim()) {
      return items;
    }
    const sanitized = sanitizeScannerUserText(item, language, '');
    if (sanitized && !items.includes(sanitized)) {
      items.push(sanitized);
    }
    return items;
  }, []);
}

function sanitizeScannerFieldLabel(label: string, language: 'zh' | 'en'): string {
  const normalized = normalizeLabel(label);
  if (['entry', 'entry range', '建仓', '入场', 'buy'].includes(normalized)) {
    return language === 'en' ? 'Observation zone' : '观察区';
  }
  if (['target', 'target price', '目标', '目标价'].includes(normalized)) {
    return language === 'en' ? 'Reference range' : '参考区间';
  }
  if (['stop', 'stop loss', '止损', '止损位'].includes(normalized)) {
    return language === 'en' ? 'Risk boundary' : '风险边界';
  }
  return label;
}

function sanitizeScannerLabeledValues(items: ScannerLabeledValue[] | undefined, language: 'zh' | 'en'): ScannerLabeledValue[] {
  return (items || []).map((item) => {
    const labelHasInternalDetail = isInternalScannerIssue(item.label);
    const valueHasInternalDetail = isInternalScannerIssue(item.value);
    if (!labelHasInternalDetail && !valueHasInternalDetail) {
      return {
        ...item,
        label: sanitizeScannerFieldLabel(item.label, language),
      };
    }
    return {
      label: language === 'en' ? 'Data note' : '数据说明',
      value: sanitizeUserFacingDataIssue(`${item.label} ${item.value}`, language),
    };
  });
}

function getRiskSummary(candidate: ScannerCandidate, language: 'zh' | 'en'): string {
  return sanitizeScannerUserText(
    candidate.riskNotes?.[0] || candidate.aiInterpretation?.riskInterpretation,
    language,
    language === 'en' ? 'No risk note provided' : '未提供风险说明',
  );
}

function getKeyReason(candidate: ScannerCandidate, runDetail: ScannerRunDetail | null, language: 'zh' | 'en'): string {
  return sanitizeScannerUserText(
    candidate.reasonSummary
    || candidate.reasons?.[0]
    || candidate.featureSignals?.[0]?.value
    || runDetail?.scoringNotes?.[0],
    language,
    language === 'en' ? 'No selection note provided' : '未提供入选说明',
  );
}

function getRunSummaryCount(runDetail: ScannerRunDetail, key: keyof NonNullable<ScannerRunDetail['summary']>, fallback = 0): number {
  const value = runDetail.summary?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function getRunBestCandidate(runDetail: ScannerRunDetail, language: 'zh' | 'en'): string {
  const best = runDetail.shortlist?.[0] || runDetail.selected?.[0] || null;
  if (!best) return language === 'en' ? 'None' : '暂无';
  const score = best.score != null && Number.isFinite(best.score) ? ` · ${best.score}/100` : '';
  return `${normalizeCandidateSymbol(best.symbol) || best.symbol || '--'}${score}`;
}

function getRunDataStatusLabel(runDetail: ScannerRunDetail, language: 'zh' | 'en'): string {
  const provider = getRunProviderDiagnostics(runDetail);
  const status = normalizeRunState(runDetail.status);
  const failureReason = normalizeRunState(runDetail.failureReason);
  const failedCount = getRunSummaryCount(runDetail, 'dataFailedCount', 0) + getRunSummaryCount(runDetail, 'errorCount', 0);
  const selectedCount = getRunSummaryCount(runDetail, 'selectedCount', runDetail.shortlist?.length || 0);
  const rejectedCount = getRunSummaryCount(runDetail, 'rejectedCount', 0);
  const providerText = [
    provider?.fallbackOccurred ? 'fallback' : null,
    provider?.providerFailureCount ? 'provider_error' : null,
    provider?.missingDataSymbolCount ? 'partial' : null,
    provider?.quoteSourceUsed,
    provider?.snapshotSourceUsed,
    provider?.historySourceUsed,
  ].filter(Boolean).join(' ');
  const text = normalizeRunState([status, failureReason, providerText].join(' '));
  if (status === 'empty' || selectedCount === 0 && runDetail.status === 'empty') return compactScannerStateLabel('no_candidates', language);
  if (selectedCount === 0 && rejectedCount > 0) return compactScannerStateLabel('no_candidates', language);
  if (failedCount > 0 && provider?.providerFailureCount) return compactScannerStateLabel('provider_error', language);
  if (failedCount > 0) return compactScannerStateLabel('insufficient_data', language);
  if (text.includes('provider_error') || text.includes('provider_down')) return compactScannerStateLabel('provider_error', language);
  if (text.includes('fallback')) return compactScannerStateLabel('fallback', language);
  if (text.includes('local')) return compactScannerStateLabel('local_data', language);
  if (text.includes('partial')) return compactScannerStateLabel('partial', language);
  if (status === 'failed' || status === 'error') return compactScannerStateLabel('failed', language);
  if (status === 'completed' || status === 'success') return language === 'en' ? 'Verified' : '已验证';
  return compactScannerStateLabel('unknown', language);
}

function buildScannerRunSummary(
  title: string,
  runDetail: ScannerRunDetail | null,
  language: 'zh' | 'en',
): ScannerRunSummary | null {
  if (!runDetail) return null;
  if (isScannerPseudoEmptyRun(runDetail)) {
    return buildUnavailableScannerRunSummary(title, runDetail.runAt || runDetail.completedAt, language);
  }
  const selectedCount = getRunSummaryCount(runDetail, 'selectedCount', runDetail.shortlist?.length || 0);
  const rejectedCount = getRunSummaryCount(runDetail, 'rejectedCount', Math.max(0, (runDetail.evaluatedSize || 0) - selectedCount));
  const failedCount = getRunSummaryCount(runDetail, 'dataFailedCount', 0) + getRunSummaryCount(runDetail, 'errorCount', 0);
  return {
    title,
    statusLabel: compactScannerStateLabel(runDetail.status, language),
    bestCandidate: getRunBestCandidate(runDetail, language),
    candidateCount: selectedCount,
    rejectedCount,
    failedCount,
    dataStatusLabel: getRunDataStatusLabel(runDetail, language),
    durationLabel: formatDurationMs(runDetail.runAt, runDetail.completedAt),
    runTimeLabel: formatTimestamp(runDetail.runAt || runDetail.completedAt, language),
    errorSummary: sanitizeScannerErrorSummary(runDetail.failureReason, language),
  };
}

function buildUnavailableScannerRunSummary(
  title: string,
  runTime: string | null | undefined,
  language: 'zh' | 'en',
): ScannerRunSummary {
  return {
    title,
    statusLabel: language === 'en' ? 'Unavailable' : '暂不可用',
    bestCandidate: language === 'en' ? 'Not produced yet' : '尚未产出',
    candidateCount: 0,
    rejectedCount: 0,
    failedCount: 0,
    dataStatusLabel: language === 'en' ? 'Run data unavailable' : '运行数据暂不可用',
    durationLabel: '--',
    runTimeLabel: formatTimestamp(runTime, language),
    errorSummary: null,
    unavailable: true,
    unavailableTitle: language === 'en' ? 'Candidate set has not been produced yet' : '候选集尚未产出',
    unavailableBody: language === 'en'
      ? 'Run data insufficient. Retry scan, check history, or open Watchlist / Market Overview.'
      : '数据不足，可重试、查看历史或打开市场概览。',
  };
}

function getHistorySelectedCount(item: ScannerRunHistoryItem): number {
  const shortlistSize = getFiniteCount(item.shortlistSize);
  if (shortlistSize != null) return shortlistSize;
  return Array.isArray(item.topSymbols) ? item.topSymbols.length : 0;
}

function isCompletedEmptyHistoryRun(item: ScannerRunHistoryItem | null): boolean {
  if (!item) return false;
  if (isScannerPseudoEmptyHistoryRun(item)) return false;
  const runState = normalizeRunState(item.status);
  return (runState === 'completed' || runState === 'empty') && getHistorySelectedCount(item) === 0;
}

function isScannerPseudoEmptyHistoryRun(item: ScannerRunHistoryItem | null): boolean {
  if (!item) return false;
  const runState = normalizeRunState(item.status);
  if (runState === 'failed' || runState === 'failure' || runState === 'error') return false;
  const selectedCount = getHistorySelectedCount(item);
  const evaluatedCount = getFiniteCount(item.evaluatedSize) ?? 0;
  const rejectedCount = Math.max(0, evaluatedCount - selectedCount);
  const failedCount = runState === 'failed' ? 1 : 0;
  const durationMs = getElapsedDurationMs(item.runAt, item.completedAt);
  const hasSymbols = Boolean(item.topSymbols?.some((symbol) => String(symbol || '').trim()));
  return selectedCount === 0
    && rejectedCount === 0
    && failedCount === 0
    && !hasSymbols
    && (durationMs == null || durationMs <= 50);
}

function buildHistoryItemSummary(
  title: string,
  item: ScannerRunHistoryItem | null,
  language: 'zh' | 'en',
): ScannerRunSummary | null {
  if (!item) return null;
  if (isScannerPseudoEmptyHistoryRun(item)) {
    return buildUnavailableScannerRunSummary(title, item.runAt || item.completedAt, language);
  }
  const failedCount = item.status === 'failed' ? 1 : 0;
  return {
    title,
    statusLabel: compactScannerStateLabel(item.status, language),
    bestCandidate: item.topSymbols?.[0] || (language === 'en' ? 'None' : '暂无'),
    candidateCount: item.shortlistSize || item.topSymbols?.length || 0,
    rejectedCount: Math.max(0, (item.evaluatedSize || 0) - (item.shortlistSize || item.topSymbols?.length || 0)),
    failedCount,
    dataStatusLabel: sanitizeScannerErrorSummary(item.failureReason, language) || compactScannerStateLabel(item.status === 'empty' ? 'no_candidates' : item.status, language),
    durationLabel: formatDurationMs(item.runAt, item.completedAt),
    runTimeLabel: formatTimestamp(item.runAt || item.completedAt, language),
    errorSummary: sanitizeScannerErrorSummary(item.failureReason, language),
  };
}

function getFiniteCount(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
}

function formatScannerCount(value: number | null): string {
  return value == null ? '--' : String(value);
}

function getRunCoverageCount(
  coverage: ScannerCoverageSummary | null,
  key: keyof ScannerCoverageSummary,
): number | null {
  return getFiniteCount(coverage?.[key]);
}

function getScannerRunFactCounts(runDetail: ScannerRunDetail | null): {
  universe: number | null;
  preselected: number | null;
  evaluated: number | null;
  selected: number | null;
} {
  if (!runDetail) {
    return {
      universe: null,
      preselected: null,
      evaluated: null,
      selected: null,
    };
  }
  const coverage = getRunCoverageSummary(runDetail);
  return {
    universe: getFiniteCount(runDetail.universeSize)
      ?? getRunCoverageCount(coverage, 'inputUniverseSize')
      ?? getFiniteCount(runDetail.summary?.universeCount),
    preselected: getFiniteCount(runDetail.preselectedSize)
      ?? getRunCoverageCount(coverage, 'eligibleAfterUniverseFetch')
      ?? getRunCoverageCount(coverage, 'eligibleAfterLiquidityFilter'),
    evaluated: getFiniteCount(runDetail.summary?.evaluatedCount)
      ?? getFiniteCount(runDetail.evaluatedSize)
      ?? getRunCoverageCount(coverage, 'rankedCandidateCount'),
    selected: getFiniteCount(runDetail.summary?.selectedCount)
      ?? getFiniteCount(runDetail.shortlist?.length),
  };
}

function getRunMarketDisplayLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  const normalized = normalizeScannerRunMarket(value);
  return normalized ? getScannerMarketLabel(normalized, language) : String(value || '--').toUpperCase();
}

function buildScannerRunFactItems(runDetail: ScannerRunDetail | null, language: 'zh' | 'en'): ScannerLabeledValue[] {
  if (!runDetail) return [];
  const counts = getScannerRunFactCounts(runDetail);
  const profileLabel = sanitizeScannerProfileLabel(runDetail.profileLabel || runDetail.profile);
  const items: ScannerLabeledValue[] = [
    {
      label: language === 'en' ? 'Market' : '市场',
      value: getRunMarketDisplayLabel(runDetail.market, language),
    },
    {
      label: language === 'en' ? 'Profile' : '策略',
      value: profileLabel || '--',
    },
  ];

  if (runDetail.runAt) {
    items.push({
      label: language === 'en' ? 'Run time' : '运行时间',
      value: formatTimestamp(runDetail.runAt, language),
    });
  }
  if (runDetail.completedAt) {
    items.push({
      label: language === 'en' ? 'Completed' : '完成时间',
      value: formatTimestamp(runDetail.completedAt, language),
    });
  }
  if (runDetail.watchlistDate) {
    items.push({
      label: language === 'en' ? 'Watchlist date' : '观察日期',
      value: formatDateOnly(runDetail.watchlistDate, language),
    });
  }

  [
    { label: language === 'en' ? 'Scope' : '标的池', value: counts.universe },
    { label: language === 'en' ? 'Preselected' : '预筛', value: counts.preselected },
    { label: language === 'en' ? 'Evaluated' : '评估', value: counts.evaluated },
    { label: language === 'en' ? 'Selected' : '入选', value: counts.selected },
  ].forEach((item) => {
    if (item.value != null) {
      items.push({
        label: item.label,
        value: formatScannerCount(item.value),
      });
    }
  });

  return items;
}

function buildScannerHistoryScopeHint(
  runDetail: ScannerRunDetail | null,
  market: 'cn' | 'us' | 'hk',
  profile: string,
  language: 'zh' | 'en',
): string {
  const runMarket = normalizeScannerRunMarket(runDetail?.market) || market;
  const runProfile = sanitizeScannerProfileLabel(runDetail?.profileLabel || runDetail?.profile || profile);
  return language === 'en'
    ? `Personal history is scoped to scanner runs available to this account; this view is loaded around ${getScannerMarketLabel(runMarket, language)} · ${runProfile || '--'}.`
    : `个人历史仅基于当前账号可访问的扫描记录；本视图按 ${getScannerMarketLabel(runMarket, language)} · ${runProfile || '--'} 加载。`;
}

function getCandidateDiagnostics(runDetail: ScannerRunDetail | null): ScannerCandidateDiagnostic[] {
  return Array.isArray(runDetail?.candidates) ? runDetail.candidates : [];
}

function getDiagnosticReason(candidate: ScannerCandidateDiagnostic, language: 'zh' | 'en'): string {
  return candidate.reason
    || candidate.failedRules?.[0]?.replace(/_/g, ' ')
    || candidate.missingFields?.[0]
    || (language === 'en' ? 'No data note' : '未提供数据说明');
}

function normalizeDiagnosticText(value?: string | null): string {
  return String(value || '').trim().toLowerCase().replace(/[_-]+/g, ' ');
}

function formatFriendlyProvider(value?: string | null, language: 'zh' | 'en' = 'zh'): string {
  const normalized = normalizeDiagnosticText(value);
  if (!normalized) return '--';
  if (normalized.includes('provider down') || normalized.includes('provider error') || normalized.includes('provider failed')) return compactScannerStateLabel('provider_error', language);
  if (normalized === 'unknown') return compactScannerStateLabel('unknown', language);
  if (normalized.includes('fallback')) return compactScannerStateLabel('fallback', language);
  if (normalized.includes('local db') || normalized.includes('local')) return language === 'en' ? 'Recent available data' : '最近可用数据';
  return language === 'en' ? 'Available' : '可用';
}

function formatFriendlyDiagnosticReason(candidate: ScannerCandidateDiagnostic, language: 'zh' | 'en'): string {
  const rawReason = getDiagnosticReason(candidate, language);
  const text = [
    candidate.status,
    candidate.reason,
    ...(candidate.failedRules || []),
    ...(candidate.missingFields || []),
  ].map(normalizeDiagnosticText).join(' ');
  if (normalizeDiagnosticStatus(candidate.status) === 'selected') {
    return language === 'en' ? 'Passed screening' : '通过筛选';
  }
  if (candidate.status === 'data_failed' || candidate.status === 'error') return sanitizeUserFacingDataIssue(text || rawReason, language);
  if (/provider|timeout|missing|history|quote|data|field|not enough|unavailable/.test(text)) return sanitizeUserFacingDataIssue(text || rawReason, language);
  if (/liquidity|volume|turnover|amount/.test(text)) return language === 'en' ? 'Liquidity weak' : '流动性不足';
  if (/price/.test(text)) return language === 'en' ? 'Price below threshold' : '价格低于阈值';
  if (/momentum|relative strength|strength|return/.test(text)) return language === 'en' ? 'Momentum weak' : '动量不足';
  if (/trend|moving average|breakout|\bma\b/.test(text)) return language === 'en' ? 'Trend weak' : '趋势不足';
  if (/score|threshold|rank/.test(text)) return language === 'en' ? 'Score below threshold' : '分数低于阈值';
  if (/passed/.test(normalizeDiagnosticText(rawReason))) return language === 'en' ? 'Passed screening' : '通过筛选';
  return language === 'en' ? 'Screening condition not met' : '未达到筛选条件';
}

function formatCandidateDataQuality(candidate: ScannerCandidateDiagnostic, language: 'zh' | 'en'): string {
  const trustNotice = getScannerConsumerQualityNotice(candidate, language);
  if (trustNotice) return trustNotice;
  const status = normalizeDiagnosticStatus(candidate.status);
  const text = [
    candidate.reason,
    ...(candidate.failedRules || []),
    ...(candidate.missingFields || []),
  ].map(normalizeDiagnosticText).join(' ');
  if (/quote|realtime|snapshot/.test(text)) return sanitizeUserFacingDataIssue(text || 'data_missing', language);
  if (status === 'data_failed' || status === 'error' || /provider|timeout|missing|history|data|field|not enough|unavailable/.test(text)) {
    return sanitizeUserFacingDataIssue(text || candidate.reason, language);
  }
  const provider = formatFriendlyProvider(candidate.provider, language);
  if (provider === (language === 'en' ? 'Recent available data' : '最近可用数据')) return provider;
  return language === 'en' ? 'Verified' : '已验证';
}

function normalizeDiagnosticStatus(status: ScannerCandidateDiagnostic['status']): ScannerCandidateDiagnosticStatus {
  return status || 'skipped';
}

function diagnosticStatusLabel(status: ScannerCandidateDiagnostic['status'], language: 'zh' | 'en'): string {
  const labels: Record<ScannerCandidateDiagnosticStatus, { zh: string; en: string }> = {
    selected: { zh: '入选', en: 'Selected' },
    rejected: { zh: '淘汰', en: 'Rejected' },
    data_failed: { zh: '数据受限', en: 'Limited data' },
    skipped: { zh: '跳过', en: 'Skipped' },
    error: { zh: '数据暂不可用', en: 'Data unavailable' },
    evaluated: { zh: '已评估', en: 'Evaluated' },
  };
  const normalizedStatus = normalizeDiagnosticStatus(status);
  return labels[normalizedStatus]?.[language] || normalizedStatus;
}

function isOfficialSelected(candidate: ScannerCandidateDiagnostic): boolean {
  return normalizeDiagnosticStatus(candidate.status) === 'selected';
}

function isDataUnavailable(candidate: ScannerCandidateDiagnostic): boolean {
  const status = normalizeDiagnosticStatus(candidate.status);
  return status === 'data_failed' || status === 'error' || status === 'skipped';
}

function scannerTrustBucketsForSource(source: ScannerCandidate | ScannerCandidateDiagnostic): { buckets: TrustDisclosureBucket[]; terms: string[] } {
  const root = isRecord(source) ? source : null;
  const containers = [
    getNestedRecord(root, 'diagnostics'),
    getNestedRecord(root, 'metadata'),
  ].filter((value): value is Record<string, unknown> => Boolean(value));
  const buckets: TrustDisclosureBucket[] = [];
  const terms: string[] = [];

  containers.forEach((container) => {
    const explainability = getNestedRecord(container, 'scoreExplainability', 'score_explainability');
    const evidencePacket = getNestedRecord(container, 'evidencePacket', 'evidence_packet');
    const sourceConfidence = getNestedRecord(explainability, 'sourceConfidence', 'source_confidence')
      || getNestedRecord(evidencePacket, 'sourceConfidence', 'source_confidence');
    const providerObservation = getNestedRecord(evidencePacket, 'providerObservation', 'provider_observation');
    const freshnessDetail = getNestedRecord(evidencePacket, 'freshnessDetail', 'freshness_detail');
    const capReason = getNestedString(explainability, 'capReason', 'cap_reason')
      || getNestedString(evidencePacket, 'capReason', 'cap_reason')
      || getNestedString(sourceConfidence, 'capReason', 'cap_reason');
    const degradationReason = getNestedString(explainability, 'degradationReason', 'degradation_reason')
      || getNestedString(evidencePacket, 'degradationReason', 'degradation_reason')
      || getNestedString(sourceConfidence, 'degradationReason', 'degradation_reason');
    const scoreConfidence = getNestedNumber(explainability, 'scoreConfidence', 'score_confidence')
      ?? getNestedNumber(evidencePacket, 'scoreConfidence', 'score_confidence')
      ?? getNestedNumber(sourceConfidence, 'confidenceWeight', 'confidence_weight');
    const scoreGradeAllowed = getNestedBoolean(explainability, 'scoreGradeAllowed', 'score_grade_allowed');
    const scoreContributionAllowed = getNestedBoolean(sourceConfidence, 'scoreContributionAllowed', 'score_contribution_allowed')
      ?? getNestedBoolean(providerObservation, 'scoreContributionAllowed', 'score_contribution_allowed');
    const observationOnly = getNestedBoolean(sourceConfidence, 'observationOnly', 'observation_only')
      ?? getNestedBoolean(providerObservation, 'observationOnly', 'observation_only')
      ?? (scoreGradeAllowed === false || scoreContributionAllowed === false ? true : null);
    const fallbackFlag = getNestedBoolean(sourceConfidence, 'isFallback', 'is_fallback')
      ?? (normalizeRunState(getNestedString(sourceConfidence, 'freshness')) === 'fallback'
        || normalizeRunState(getNestedString(evidencePacket, 'freshnessState', 'freshness_state')) === 'fallback');
    const staleFlag = getNestedBoolean(sourceConfidence, 'isStale', 'is_stale')
      ?? (normalizeRunState(getNestedString(evidencePacket, 'freshnessState', 'freshness_state')) === 'stale');
    const partialFlag = getNestedBoolean(sourceConfidence, 'isPartial', 'is_partial')
      ?? (normalizeRunState(getNestedString(evidencePacket, 'dataQualityState', 'data_quality_state')) === 'partial');
    const sourceLabel = getNestedString(sourceConfidence, 'sourceLabel', 'source_label', 'source');
    const proxyFlag = getNestedBoolean(sourceConfidence, 'proxyOnly', 'proxy_only')
      ?? /proxy/.test(normalizeRunState([capReason, degradationReason, sourceLabel].filter(Boolean).join(' ')));
    const quoteFreshness = getNestedString(freshnessDetail, 'quoteState', 'quote_state');
    const historyFreshness = getNestedString(freshnessDetail, 'historyState', 'history_state');

    [
      capReason,
      degradationReason,
      sourceLabel,
      getNestedString(sourceConfidence, 'freshness'),
      getNestedString(evidencePacket, 'freshnessState', 'freshness_state'),
      getNestedString(evidencePacket, 'dataQualityState', 'data_quality_state'),
      quoteFreshness,
      historyFreshness,
      ...getNestedStringArray(evidencePacket, 'userFacingLabels', 'warningFlags'),
    ].forEach((term) => {
      if (term) terms.push(term);
    });

    if (capReason || scoreGradeAllowed === false || (scoreConfidence != null && scoreConfidence < 0.7)) addUniqueBucket(buckets, 'confidence');
    if (fallbackFlag) addUniqueBucket(buckets, 'fallback');
    if (proxyFlag) addUniqueBucket(buckets, 'proxy');
    if (staleFlag || normalizeRunState(quoteFreshness) === 'stale' || normalizeRunState(historyFreshness) === 'stale') addUniqueBucket(buckets, 'stale');
    if (partialFlag) addUniqueBucket(buckets, 'partial');
    if (observationOnly) addUniqueBucket(buckets, 'observe-only');
    if (scoreGradeAllowed === false || scoreContributionAllowed === false) addUniqueBucket(buckets, 'observe-only');
  });

  return { buckets, terms };
}

function buildScannerTrustSummary(runDetail: ScannerRunDetail | null): ScannerTrustSummary {
  const empty: ScannerTrustSummary = {
    cappedCount: 0,
    fallbackCount: 0,
    proxyCount: 0,
    staleCount: 0,
    partialCount: 0,
    limitedCount: 0,
    buckets: [],
    terms: [],
  };
  if (!runDetail) return empty;

  const sources = getCandidateDiagnostics(runDetail).length
    ? getCandidateDiagnostics(runDetail)
    : runDetail.shortlist || [];

  const summary = sources.reduce<ScannerTrustSummary>((current, source) => {
    const { buckets, terms } = scannerTrustBucketsForSource(source);
    const hasCapped = buckets.includes('confidence');
    const hasFallback = buckets.includes('fallback');
    const hasProxy = buckets.includes('proxy');
    const hasStale = buckets.includes('stale');
    const hasPartial = buckets.includes('partial');
    const hasLimited = hasCapped || hasFallback || hasProxy || hasStale;
    buckets.forEach((bucket) => addUniqueBucket(current.buckets, bucket));
    terms.forEach((term) => {
      if (!current.terms.includes(term)) current.terms.push(term);
    });
    return {
      cappedCount: current.cappedCount + Number(hasCapped),
      fallbackCount: current.fallbackCount + Number(hasFallback),
      proxyCount: current.proxyCount + Number(hasProxy),
      staleCount: current.staleCount + Number(hasStale),
      partialCount: current.partialCount + Number(hasPartial),
      limitedCount: current.limitedCount + Number(hasLimited),
      buckets: current.buckets,
      terms: current.terms,
    };
  }, { ...empty, buckets: [], terms: [] });

  if (runDetail.summary?.limitedByResultCap) {
    addUniqueBucket(summary.buckets, 'confidence');
    summary.cappedCount += 1;
    summary.limitedCount = Math.max(summary.limitedCount, 1);
    summary.terms.push('result capped');
  }

  return summary;
}

function buildScannerConclusion(
  runDetail: ScannerRunDetail | null,
  language: 'zh' | 'en',
  firstRunSetupLabel: string,
  historyResolution: ScannerHistoryResolution,
  dataReadinessView: ScannerDataReadinessView | null,
): ScannerConclusionModel {
  const trustSummary = buildScannerTrustSummary(runDetail);
  if (!runDetail && dataReadinessView?.isMeaningful && dataReadinessView.stateLabel !== (language === 'en' ? 'Ready to scan' : '可扫描')) {
    return {
      state: dataReadinessView.stateLabel === (language === 'en' ? 'Not run' : '未运行') ? 'waiting' : 'insufficient',
      title: dataReadinessView.blockerLabel || dataReadinessView.stateLabel,
      detail: dataReadinessView.nextDataLabel || dataReadinessView.stateLabel,
      candidateCount: 0,
      trustSummary,
      tone: dataReadinessView.stateLabel === (language === 'en' ? 'Data blocked' : '数据待补') ? 'caution' : 'neutral',
    };
  }
  if (!runDetail) {
    if (!historyResolution.hasLoaded) {
      return {
        state: 'waiting',
        title: language === 'en' ? 'Loading recent scans' : '正在读取最近扫描',
        detail: language === 'en'
          ? 'Loading recent scanner history before deciding whether this is a first-use state or a completed run.'
          : '正在读取最近扫描记录，以区分这是首次使用还是已有完成的扫描结果。',
        candidateCount: 0,
        trustSummary,
        tone: 'neutral',
      };
    }

    if (isCompletedEmptyHistoryRun(historyResolution.latestRun)) {
      return {
        state: 'no-candidate',
        title: language === 'en' ? 'No selected candidate in this run' : '本次未形成入选候选',
        detail: language === 'en'
          ? 'Review coverage and rejection mix before adjusting scope.'
          : '查看覆盖与淘汰分布，再决定是否调整范围。',
        candidateCount: 0,
        trustSummary,
        tone: 'caution',
      };
    }

    if (historyResolution.latestRun) {
      return {
        state: 'waiting',
        title: language === 'en' ? 'Loading recent scan detail' : '正在载入最近扫描详情',
        detail: language === 'en'
          ? 'Recent run facts are available. Loading the full run detail before presenting the candidate conclusion.'
          : '已读取最近扫描事实，正在载入完整结果详情后再展示候选结论。',
        candidateCount: getHistorySelectedCount(historyResolution.latestRun),
        trustSummary,
        tone: 'neutral',
      };
    }

    return {
      state: 'waiting',
      title: language === 'en' ? 'First run: start a scan' : '首次使用：先运行一次扫描',
      detail: language === 'en'
        ? `Scanner reviews the current scope and surfaces observation candidates. Starting setup: ${firstRunSetupLabel}. Run one scan first, then adjust market, scope, or review depth if needed.`
        : `扫描器会先按当前范围筛出可继续观察的候选。当前起始范围：${firstRunSetupLabel}。先直接启动一次扫描，再按结果决定是否切换市场、范围或评估深度。`,
      candidateCount: 0,
      trustSummary,
      tone: 'neutral',
    };
  }

  if (isScannerPseudoEmptyRun(runDetail)) {
    return {
      state: 'insufficient',
      title: dataReadinessView?.blockerLabel || (language === 'en' ? 'Scanner has not produced a candidate set yet' : '扫描器尚未产出候选集'),
      detail: dataReadinessView?.nextDataLabel || (language === 'en'
        ? 'No candidates produced. Retry or check Market Overview.'
        : '无候选产出，可稍后重试或查看市场概览。'),
      candidateCount: 0,
      trustSummary,
      tone: 'caution',
    };
  }

  const selectedCount = getRunSummaryCount(runDetail, 'selectedCount', runDetail.shortlist?.length || 0);
  const rejectedCount = getRunSummaryCount(runDetail, 'rejectedCount', 0);
  const failedCount = getRunSummaryCount(runDetail, 'dataFailedCount', 0) + getRunSummaryCount(runDetail, 'errorCount', 0);
  const diagnostics = getCandidateDiagnostics(runDetail);
  const allDiagnosticsUnavailable = diagnostics.length > 0 && diagnostics.every(isDataUnavailable);
  const runState = normalizeRunState(runDetail.status);
  const evidenceInsufficient = selectedCount === 0
    && (runState === 'failed'
      || runState === 'error'
      || allDiagnosticsUnavailable
      || (failedCount > 0 && rejectedCount === 0));

  if (evidenceInsufficient) {
    return {
      state: 'insufficient',
      title: dataReadinessView?.blockerLabel || (language === 'en' ? 'Research evidence pending' : '证据不足'),
      detail: dataReadinessView?.nextDataLabel || (language === 'en'
        ? 'Refresh quotes or history evidence before treating this scan as evidence.'
        : '补齐行情或历史证据后，再将本次扫描视为证据。'),
      candidateCount: selectedCount,
      trustSummary,
      tone: 'danger',
    };
  }

  const topCandidate = runDetail.shortlist?.[0]
    || diagnostics.find(isOfficialSelected)
    || null;
  if (selectedCount <= 0 || !topCandidate) {
    return {
      state: 'no-candidate',
      title: dataReadinessView?.blockerLabel || (language === 'en' ? 'No selected candidate in this run' : '本次未形成入选候选'),
      detail: dataReadinessView?.nextDataLabel || (language === 'en'
        ? 'Review data coverage, history coverage, and the rejection mix before changing scope; this does not describe the whole market.'
        : '查看覆盖与淘汰分布，再决定是否调整范围。'),
      candidateCount: selectedCount,
      trustSummary,
      tone: 'caution',
    };
  }

  const symbol = normalizeCandidateSymbol(topCandidate.symbol) || topCandidate.symbol || '--';
  return {
    state: 'top-candidate',
    title: language === 'en' ? `Current candidate ${symbol}` : `当前候选 ${symbol}`,
    detail: language === 'en'
      ? `Observe ${symbol}'s next update against the observation zone, reference range, and risk boundary before treating it as evidence.`
      : `观察 ${symbol} 的下一次更新，并对照观察区、参考区间与风险边界后再作为证据。`,
    candidateCount: selectedCount,
    trustSummary,
    tone: trustSummary.limitedCount > 0 ? 'caution' : 'success',
  };
}

function buildScannerSafeEmptyReason({
  diagnosticCandidates,
  language,
  runDetail,
}: {
  diagnosticCandidates: ScannerCandidateDiagnostic[];
  language: 'zh' | 'en';
  runDetail: ScannerRunDetail;
}): ScannerSafeEmptyReason {
  const counts = getScannerRunFactCounts(runDetail);
  const coverage = getRunCoverageSummary(runDetail);
  const stateText = [
    runDetail.status,
    runDetail.failureReason,
    coverage?.likelyBottleneck,
    coverage?.likelyBottleneckLabel,
    ...diagnosticCandidates.flatMap((candidate) => [
      candidate.status,
      candidate.reason,
      ...(candidate.failedRules || []),
      ...(candidate.missingFields || []),
    ]),
  ].map(normalizeRunState).join(' ');
  const hasCoverageGap = /history|quote|data|missing|insufficient|unavailable|limited|provider|snapshot/.test(stateText)
    || counts.evaluated === 0
    || (counts.universe != null && counts.evaluated != null && counts.evaluated < counts.universe);
  const hasRunScopeGap = runDetail.universeType === 'theme'
    || runDetail.universeType === 'symbols'
    || runDetail.universeType === 'custom'
    || (runDetail.acceptedSymbolsCount > 0 && runDetail.acceptedSymbolsCount < runDetail.requestedSymbolsCount);
  const countSummary = language === 'en'
    ? `Scope ${formatScannerCount(counts.universe)} · preselected ${formatScannerCount(counts.preselected)} · evaluated ${formatScannerCount(counts.evaluated)} · selected ${formatScannerCount(counts.selected)}.`
    : `标的池 ${formatScannerCount(counts.universe)} · 预筛 ${formatScannerCount(counts.preselected)} · 评估 ${formatScannerCount(counts.evaluated)} · 入选 ${formatScannerCount(counts.selected)}。`;

  if (hasCoverageGap) {
    return {
      label: language === 'en' ? 'Data/history coverage limited' : '数据/历史覆盖不足',
      body: language === 'en'
        ? `${countSummary} No candidates formed. Retry, check limited-data rows, or try another market/profile.`
        : `${countSummary} 未形成入选候选，可重试、查看数据受限行或切换市场/策略。`,
    };
  }

  if (hasRunScopeGap) {
    return {
      label: language === 'en' ? 'Current run settings produced no selection' : '当前运行设置未形成候选',
      body: language === 'en'
        ? `${countSummary} No candidates selected. Review rejection mix, retry, or switch market/profile.`
        : `${countSummary} 未形成入选候选。查看淘汰分布，可重试或切换市场/策略。`,
    };
  }

  return {
    label: language === 'en' ? 'Evidence insufficient for review' : '证据不足，未形成复核候选',
    body: language === 'en'
      ? `${countSummary} No review-ready candidate. Use history, retry, or adjust settings.`
      : `${countSummary} 未形成可复核候选，可查看历史、重试或调整设置。`,
  };
}

function resolveScannerWorkspaceState({
  isRunning,
  pageErrorSummary,
  runDetail,
  historyResolution,
  dataReadinessView,
  selectedCount,
  language,
}: {
  isRunning: boolean;
  pageErrorSummary: string | null;
  runDetail: ScannerRunDetail | null;
  historyResolution: ScannerHistoryResolution;
  dataReadinessView: ScannerDataReadinessView | null;
  selectedCount: number;
  language: 'zh' | 'en';
}): ScannerWorkspaceState {
  if (pageErrorSummary) return 'error';
  if (isRunning) return 'loading';
  if (!runDetail && !historyResolution.hasLoaded) return 'loading';

  const readinessBlocked = Boolean(
    dataReadinessView?.isMeaningful
    && dataReadinessView.stateLabel !== (language === 'en' ? 'Ready to scan' : '可扫描')
    && (
      dataReadinessView.stateLabel === (language === 'en' ? 'Data blocked' : '数据待补')
      || Boolean(dataReadinessView.blockerLabel)
    )
    && selectedCount === 0,
  );
  if (readinessBlocked && !runDetail) return 'blocked';
  if (readinessBlocked && runDetail && selectedCount === 0) return 'blocked';

  if (runDetail) {
    if (selectedCount > 0) return 'ready';
    const runState = normalizeRunState(runDetail.status);
    if (['failed', 'failure', 'error'].includes(runState)) return 'error';
    return 'empty';
  }

  if (isCompletedEmptyHistoryRun(historyResolution.latestRun)) return 'empty';
  if (historyResolution.latestRun) return 'loading';
  return 'idle';
}

function buildScannerWorkbenchEmptyState({
  candidateFilter,
  diagnosticCandidates,
  firstRunSetupLabel,
  historyResolution,
  language,
  pageErrorSummary,
  runDetail,
  dataReadinessView,
}: {
  candidateFilter: CandidateFilter;
  diagnosticCandidates: ScannerCandidateDiagnostic[];
  firstRunSetupLabel: string;
  historyResolution: ScannerHistoryResolution;
  language: 'zh' | 'en';
  pageErrorSummary: string | null;
  runDetail: ScannerRunDetail | null;
  dataReadinessView: ScannerDataReadinessView | null;
}): ScannerWorkbenchEmptyState {
  if (pageErrorSummary) {
    return {
      title: language === 'en' ? 'Scanner fetch failed' : '扫描读取失败',
      body: language === 'en'
        ? `${pageErrorSummary}. Retry later or open history.`
        : `${pageErrorSummary}。可稍后重试或打开历史记录。`,
    };
  }

  if (!runDetail) {
    if (dataReadinessView?.isMeaningful && dataReadinessView.stateLabel !== (language === 'en' ? 'Ready to scan' : '可扫描')) {
      return {
        title: dataReadinessView.blockerLabel || dataReadinessView.stateLabel,
        body: dataReadinessView.nextDataLabel || dataReadinessView.stateLabel,
      };
    }
    if (!historyResolution.hasLoaded) {
      return {
        title: language === 'en' ? 'Loading recent scans' : '正在读取最近扫描',
        body: language === 'en'
          ? 'Scanner history is loading before deciding whether this route is truly unused or a completed run is being restored.'
          : '正在读取扫描历史，以区分当前页面是首次使用，还是正在恢复已有完成的扫描结果。',
      };
    }

    if (isCompletedEmptyHistoryRun(historyResolution.latestRun)) {
      return {
        title: language === 'en' ? 'No selected candidates in this run' : '本次未形成入选候选',
        body: language === 'en'
          ? 'No candidates in latest run. Open history or wait for full detail.'
          : '本次无入选候选，可查看历史或等待完整详情。',
      };
    }

    if (historyResolution.latestRun) {
      return {
        title: language === 'en' ? 'Loading recent scan detail' : '正在载入最近扫描详情',
        body: language === 'en'
          ? 'Recent run facts are available. Full run detail is still loading before the candidate workspace is restored.'
          : '已读取最近扫描事实，候选工作台正在载入完整结果详情。',
      };
    }

    return {
      title: language === 'en' ? 'No scan has run yet' : '尚未运行扫描',
      body: language === 'en'
        ? `Scanner organizes observation candidates from the current scope. Starting setup: ${firstRunSetupLabel}. Run one scan first; if you want earlier results, open history.`
        : `扫描器会先按当前范围整理候选与观察线索。当前起始范围：${firstRunSetupLabel}。先直接启动一次扫描；如需查看已有结果，可打开历史记录。`,
    };
  }

  if (isScannerPseudoEmptyRun(runDetail)) {
    return {
      title: dataReadinessView?.blockerLabel || (language === 'en' ? 'Candidate table paused' : '候选表暂不展示'),
      body: dataReadinessView?.nextDataLabel || (language === 'en'
        ? 'The page is waiting for a usable candidate set before showing rows here.'
        : '等待可用候选集后再展示表格行。'),
    };
  }

  const selectedCount = getRunSummaryCount(runDetail, 'selectedCount', runDetail.shortlist?.length || 0);
  const rejectedCount = getRunSummaryCount(runDetail, 'rejectedCount', 0);
  const failedCount = getRunSummaryCount(runDetail, 'dataFailedCount', 0) + getRunSummaryCount(runDetail, 'errorCount', 0);
  const runState = normalizeRunState(runDetail.status);
  const allDiagnosticsUnavailable = diagnosticCandidates.length > 0 && diagnosticCandidates.every(isDataUnavailable);
  const evidenceInsufficient = selectedCount === 0
    && (runState === 'failed'
      || runState === 'error'
      || allDiagnosticsUnavailable
      || (failedCount > 0 && rejectedCount === 0));

  if (evidenceInsufficient) {
    const safeReason = buildScannerSafeEmptyReason({ diagnosticCandidates, language, runDetail });
    return {
      title: dataReadinessView?.blockerLabel || safeReason.label,
      body: dataReadinessView?.nextDataLabel || safeReason.body,
    };
  }

  if (selectedCount === 0 && diagnosticCandidates.length > 0) {
    const safeReason = buildScannerSafeEmptyReason({ diagnosticCandidates, language, runDetail });
    return {
      title: dataReadinessView?.blockerLabel || (language === 'en' ? 'No selected candidates in this run' : '本次未形成入选候选'),
      body: dataReadinessView?.nextDataLabel || safeReason.body,
    };
  }

  if (candidateFilter === 'data_failed') {
    return {
      title: language === 'en' ? 'No limited-data rows in this view' : '当前无数据受限行',
      body: language === 'en'
        ? 'Switch the candidate view to Candidate pool or All, or retry later if data availability changed.'
        : '切换候选视图到候选池或全部；如数据可用性变化，可稍后重试。',
    };
  }

  return {
    title: language === 'en' ? 'No rows in the current filter' : '当前过滤无候选行',
    body: language === 'en'
      ? 'Switch the candidate view, inspect limited-data rows, or adjust market, scope, detailed review, and candidate limit controls in the top command bar.'
      : '切换候选视图、查看数据受限行，或在顶部命令栏调整市场、范围、评估深度与候选上限。',
  };
}

function buildScannerPendingFeedback(language: 'zh' | 'en'): ScannerRunFeedback {
  return {
    tone: 'default',
    title: language === 'en' ? 'Scanner request submitted' : '扫描请求提交中',
    body: language === 'en'
      ? 'Checking the current market, scope, and data readiness before rendering the next candidate state.'
      : '正在按当前市场、范围和数据就绪度检查下一步候选状态。',
  };
}

function buildScannerValidationFeedback(
  message: string,
  language: 'zh' | 'en',
): ScannerRunFeedback {
  return {
    tone: 'warning',
    title: language === 'en' ? 'Scanner request not submitted' : '扫描请求未提交',
    body: message,
  };
}

function isScannerAuthOrAccessError(error: ParsedApiError): boolean {
  return Boolean(
    error.isAuthError
    || error.status === 401
    || error.status === 403
    || error.category === 'auth_required'
    || error.category === 'access_denied',
  );
}

function getScannerSafeApiErrorMessage(error: ParsedApiError, language: 'zh' | 'en'): string {
  return getConsumerSafeApiErrorCopy(error, {
    language,
    fallbackTitle: language === 'en' ? 'Scanner unavailable' : '扫描暂不可用',
    fallbackMessage: language === 'en' ? 'Please sign in or check access.' : '请重新登录或确认权限。',
  }).message;
}

function buildScannerErrorFeedback(
  error: ParsedApiError,
  language: 'zh' | 'en',
): ScannerRunFeedback {
  const safeCopy = getConsumerSafeApiErrorCopy(error, {
    language,
    fallbackTitle: language === 'en' ? 'Scanner unavailable' : '扫描暂不可用',
    fallbackMessage: language === 'en' ? 'Please try again shortly.' : '请稍后重试。',
  });
  const compactSummary = sanitizeScannerErrorSummary(error.message, language)
    || sanitizeScannerErrorSummary(error.title, language);
  return {
    tone: 'danger',
    title: language === 'en' ? 'Scan did not complete' : '扫描未完成',
    body: isScannerAuthOrAccessError(error)
      ? getScannerSafeApiErrorMessage(error, language)
      : compactSummary
      ? (language === 'en'
        ? `${compactSummary}. Retry later or adjust the current scope.`
        : `${compactSummary}。可稍后重试，或调整当前范围。`)
      : safeCopy.message,
  };
}

function buildScannerSuccessFeedback(
  runDetail: ScannerRunDetail,
  language: 'zh' | 'en',
  firstRunSetupLabel: string,
): ScannerRunFeedback {
  const dataReadinessView = buildScannerDataReadinessView(getRunDetailDataReadiness(runDetail), language);
  const conclusion = buildScannerConclusion(
    runDetail,
    language,
    firstRunSetupLabel,
    { hasLoaded: true, latestRun: null },
    dataReadinessView,
  );
  const selectedCount = getRunSummaryCount(runDetail, 'selectedCount', runDetail.shortlist?.length || 0);
  if (conclusion.state === 'top-candidate' && selectedCount > 0) {
    return {
      tone: 'success',
      title: language === 'en'
        ? `Scan completed with ${selectedCount} candidates`
        : `扫描已完成：形成 ${selectedCount} 个候选`,
      body: language === 'en'
        ? 'Candidate evidence stays research-only. Ranked rows and labels are observation-only and do not imply an execution instruction.'
        : '候选证据仅供研究参考，排序行与标签仅供观察，不构成执行指令。',
    };
  }
  return {
    tone: conclusion.state === 'insufficient' ? 'danger' : 'warning',
    title: conclusion.title,
    body: dataReadinessView?.nextDataLabel || conclusion.detail,
  };
}

function buildVisualSummarySegments(
  items: Array<{ key: string; label: string; count: number; toneClassName: string }>,
): ScannerVisualSummaryBarSegment[] {
  return items.filter((item) => item.count > 0);
}

function buildCoverageSegments(
  coverage: {
    availableCount?: number | null;
    partialCount?: number | null;
    observeOnlyCount?: number | null;
    missingCount?: number | null;
  } | null | undefined,
  language: 'zh' | 'en',
): ScannerVisualSummaryBarSegment[] {
  if (!coverage) return [];
  return buildVisualSummarySegments([
    {
      key: 'available',
      label: language === 'en' ? 'Available' : '可用',
      count: coverage.availableCount ?? 0,
      toneClassName: 'bg-[color:var(--state-success-text)]',
    },
    {
      key: 'partial',
      label: language === 'en' ? 'Partial' : '部分',
      count: coverage.partialCount ?? 0,
      toneClassName: 'bg-sky-300/85',
    },
    {
      key: 'observe_only',
      label: language === 'en' ? 'Observe only' : '仅观察',
      count: coverage.observeOnlyCount ?? 0,
      toneClassName: 'bg-blue-300/85',
    },
    {
      key: 'missing',
      label: language === 'en' ? 'Missing' : '待补',
      count: coverage.missingCount ?? 0,
      toneClassName: 'bg-[color:var(--wolfy-text-muted)]',
    },
  ]);
}

function buildMarketCoverageSegments(
  coverage: ResearchReadinessV1['evidenceCoverage'],
  language: 'zh' | 'en',
): ScannerVisualSummaryBarSegment[] {
  if (!coverage) return [];
  return buildVisualSummarySegments([
    {
      key: 'score_grade',
      label: language === 'en' ? 'Score-grade' : '评分可用',
      count: coverage.scoreGradeCount ?? 0,
      toneClassName: 'bg-[color:var(--state-success-text)]',
    },
    {
      key: 'observe_only',
      label: language === 'en' ? 'Observe only' : '仅观察',
      count: coverage.observationOnlyCount ?? 0,
      toneClassName: 'bg-blue-300/85',
    },
    {
      key: 'missing',
      label: language === 'en' ? 'Missing' : '待补',
      count: coverage.missingCount ?? 0,
      toneClassName: 'bg-[color:var(--wolfy-text-muted)]',
    },
  ]);
}

function buildScannerVisualEvidenceSummary(
  candidates: ScannerCandidateWithEvidence[],
  diagnostics: ScannerCandidateDiagnostic[],
  runDetail: ScannerRunDetail | null,
  language: 'zh' | 'en',
): ScannerVisualEvidenceSummaryModel | null {
  if (!diagnostics.length) return null;

  const scoreBands = {
    strong: 0,
    building: 0,
    watch: 0,
    limited: 0,
  };
  const candidateCoverage = {
    availableCount: 0,
    partialCount: 0,
    observeOnlyCount: 0,
    missingCount: 0,
  };
  const readinessStates = {
    ready: 0,
    observe_only: 0,
    insufficient: 0,
    blocked: 0,
    waiting: 0,
  };

  diagnostics.forEach((candidate) => {
    const score = candidate.score;
    if (score == null || !Number.isFinite(score)) {
      scoreBands.limited += 1;
    } else if (score >= 80) {
      scoreBands.strong += 1;
    } else if (score >= 60) {
      scoreBands.building += 1;
    } else if (score >= 40) {
      scoreBands.watch += 1;
    } else {
      scoreBands.limited += 1;
    }
  });

  candidates.forEach((candidate) => {
    const frameCoverage = candidate.candidateEvidenceFrame?.coverage;
    if (frameCoverage) {
      candidateCoverage.availableCount += frameCoverage.availableCount ?? 0;
      candidateCoverage.partialCount += frameCoverage.partialCount ?? 0;
      candidateCoverage.observeOnlyCount += frameCoverage.observeOnlyCount ?? 0;
      candidateCoverage.missingCount += frameCoverage.missingCount ?? 0;
    } else if (candidate.candidateResearchReadiness?.evidenceCoverage) {
      candidateCoverage.availableCount += candidate.candidateResearchReadiness.evidenceCoverage.scoreGradeCount ?? 0;
      candidateCoverage.observeOnlyCount += candidate.candidateResearchReadiness.evidenceCoverage.observationOnlyCount ?? 0;
      candidateCoverage.missingCount += candidate.candidateResearchReadiness.evidenceCoverage.missingCount ?? 0;
    }

    const normalizedState = String(candidate.candidateResearchReadiness?.readinessState || '').trim().toLowerCase();
    if (normalizedState === 'ready') readinessStates.ready += 1;
    else if (normalizedState === 'observe_only') readinessStates.observe_only += 1;
    else if (normalizedState === 'insufficient') readinessStates.insufficient += 1;
    else if (normalizedState === 'blocked') readinessStates.blocked += 1;
    else if (normalizedState === 'waiting') readinessStates.waiting += 1;
  });

  const candidateReadinessItems = [
    readinessStates.ready ? { label: language === 'en' ? 'Ready' : '可研究', value: String(readinessStates.ready) } : null,
    readinessStates.observe_only ? { label: language === 'en' ? 'Observe only' : '仅观察', value: String(readinessStates.observe_only) } : null,
    readinessStates.insufficient ? { label: language === 'en' ? 'Insufficient' : '证据不足', value: String(readinessStates.insufficient) } : null,
    readinessStates.blocked ? { label: language === 'en' ? 'Blocked' : '阻断', value: String(readinessStates.blocked) } : null,
    readinessStates.waiting ? { label: language === 'en' ? 'Waiting' : '等待', value: String(readinessStates.waiting) } : null,
  ].filter((item): item is ScannerLabeledValue => Boolean(item));

  return {
    totalRows: diagnostics.length,
    scoreBands: buildVisualSummarySegments([
      {
        key: 'strong',
        label: language === 'en' ? '80+' : '80+',
        count: scoreBands.strong,
        toneClassName: 'bg-[color:var(--state-success-text)]',
      },
      {
        key: 'building',
        label: language === 'en' ? '60-79' : '60-79',
        count: scoreBands.building,
        toneClassName: 'bg-sky-300/85',
      },
      {
        key: 'watch',
        label: language === 'en' ? '40-59' : '40-59',
        count: scoreBands.watch,
        toneClassName: 'bg-[color:var(--wolfy-market-warn)]',
      },
      {
        key: 'limited',
        label: language === 'en' ? '<40 / n.a.' : '<40 / 无',
        count: scoreBands.limited,
        toneClassName: 'bg-[color:var(--wolfy-text-muted)]',
      },
    ]),
    candidateCoverageSegments: buildCoverageSegments(candidateCoverage, language),
    marketCoverageSegments: buildMarketCoverageSegments(runDetail?.scannerContextFrame?.marketReadiness?.evidenceCoverage, language),
    candidateReadinessItems,
    nextEvidenceLabel: runDetail?.scannerContextFrame?.marketReadiness?.nextEvidenceNeeded?.[0] || null,
  };
}

function isPreviewSelected(candidate: ScannerCandidateDiagnostic, threshold: number): boolean {
  return candidate.score != null && Number.isFinite(candidate.score) && candidate.score >= threshold && !isDataUnavailable(candidate);
}

function inferPreviewThreshold(runDetail: ScannerRunDetail | null, diagnostics: ScannerCandidateDiagnostic[]): number {
  const selectedScores = diagnostics
    .filter(isOfficialSelected)
    .map((candidate) => candidate.score)
    .filter((score): score is number => score != null && Number.isFinite(score));
  if (selectedScores.length) {
    const floor = Math.floor(Math.min(...selectedScores) / 10) * 10 - 10;
    return Math.max(40, Math.min(60, floor || 50));
  }
  const summarySelected = runDetail?.summary?.selectedCount ?? runDetail?.shortlist?.length ?? 0;
  return summarySelected > 0 ? 50 : 60;
}

function previewDecisionLabel(
  candidate: ScannerCandidateDiagnostic,
  threshold: number,
  language: 'zh' | 'en',
): string {
  if (isOfficialSelected(candidate)) return language === 'en' ? 'Official' : '官方';
  if (isDataUnavailable(candidate)) return language === 'en' ? 'Limited data' : '数据受限';
  if (isPreviewSelected(candidate, threshold)) return language === 'en' ? 'Preview' : '预览';
  return language === 'en' ? 'Rejected' : '淘汰';
}

function previewDecisionClass(candidate: ScannerCandidateDiagnostic, threshold: number): string {
  if (isOfficialSelected(candidate)) return 'border-[color:var(--wolfy-accent)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_10%,var(--wolfy-surface-input))] text-[color:var(--wolfy-text-primary)]';
  if (isDataUnavailable(candidate)) return 'border-[color:var(--wolfy-market-down)] bg-[color:color-mix(in_srgb,var(--wolfy-market-down)_10%,var(--wolfy-surface-input))] text-[color:var(--wolfy-text-primary)]';
  if (isPreviewSelected(candidate, threshold)) return 'border-[color:var(--blue)] bg-[color:color-mix(in_srgb,var(--blue)_10%,var(--wolfy-surface-input))] text-[color:var(--wolfy-text-primary)]';
  return 'border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-muted)]';
}

function sortDiagnosticsForDecision(
  candidates: ScannerCandidateDiagnostic[],
  threshold: number,
): ScannerCandidateDiagnostic[] {
  return [...candidates].sort((left, right) => {
    const leftOfficial = isOfficialSelected(left) ? 1 : 0;
    const rightOfficial = isOfficialSelected(right) ? 1 : 0;
    if (leftOfficial !== rightOfficial) return rightOfficial - leftOfficial;
    const leftPreview = isPreviewSelected(left, threshold) ? 1 : 0;
    const rightPreview = isPreviewSelected(right, threshold) ? 1 : 0;
    if (leftPreview !== rightPreview) return rightPreview - leftPreview;
    const scoreCompare = (right.score ?? Number.NEGATIVE_INFINITY) - (left.score ?? Number.NEGATIVE_INFINITY);
    if (scoreCompare !== 0) return scoreCompare;
    return (left.rank ?? Number.MAX_SAFE_INTEGER) - (right.rank ?? Number.MAX_SAFE_INTEGER);
  });
}

function formatScoreDelta(delta: number | null): string | null {
  if (delta == null || !Number.isFinite(delta)) return null;
  if (delta === 0) return '0';
  return `${delta > 0 ? '+' : ''}${delta}`;
}

type RejectionBucketKey = 'trend' | 'momentum' | 'liquidity' | 'risk' | 'data' | 'score' | 'other';

function rejectionBucketLabel(key: RejectionBucketKey, language: 'zh' | 'en'): string {
  const labels: Record<RejectionBucketKey, { zh: string; en: string }> = {
    trend: { zh: '趋势不足', en: 'Trend weak' },
    momentum: { zh: '动量不足', en: 'Momentum weak' },
    liquidity: { zh: '流动性不足', en: 'Liquidity weak' },
    risk: { zh: '风险过高', en: 'Risk high' },
    data: { zh: '数据不足', en: 'Data thin' },
    score: { zh: '分数不足', en: 'Score low' },
    other: { zh: '其他', en: 'Other' },
  };
  return labels[key][language];
}

function normalizeRejectionBucket(candidate: ScannerCandidateDiagnostic): RejectionBucketKey {
  const text = [
    candidate.status,
    candidate.reason,
    ...(candidate.failedRules || []),
    ...(candidate.missingFields || []),
  ].filter(Boolean).join(' ').toLowerCase();
  if (candidate.status === 'data_failed' || candidate.status === 'error') return 'data';
  if (/missing|history|quote|data|field|not_enough|unavailable/.test(text)) return 'data';
  if (/liquidity|volume|turnover|amount/.test(text)) return 'liquidity';
  if (/risk|volatility|drawdown|stop/.test(text)) return 'risk';
  if (/momentum|relative_strength|strength|return/.test(text)) return 'momentum';
  if (/trend|ma|moving_average|breakout/.test(text)) return 'trend';
  if (/score|threshold|rank/.test(text)) return 'score';
  return 'other';
}

function buildRejectionBuckets(candidates: ScannerCandidateDiagnostic[], language: 'zh' | 'en'): ScannerLabeledValue[] {
  const counts = candidates.reduce<Map<RejectionBucketKey, number>>((bucketCounts, candidate) => {
    if (candidate.status === 'selected') {
      return bucketCounts;
    }
    const bucket = normalizeRejectionBucket(candidate);
    bucketCounts.set(bucket, (bucketCounts.get(bucket) || 0) + 1);
    return bucketCounts;
  }, new Map<RejectionBucketKey, number>());
  const order: RejectionBucketKey[] = ['trend', 'momentum', 'liquidity', 'risk', 'data', 'score', 'other'];
  return order.reduce<ScannerLabeledValue[]>((items, key) => {
    const count = counts.get(key) || 0;
    if (count > 0) {
      items.push({ label: rejectionBucketLabel(key, language), value: String(count) });
    }
    return items;
  }, []);
}

function diagnosticToCandidate(candidate: ScannerCandidateDiagnostic): ScannerCandidate {
  return {
    symbol: candidate.symbol,
    name: candidate.name || candidate.symbol,
    companyName: candidate.name || candidate.symbol,
    rank: candidate.rank || 0,
    score: Number(candidate.score || 0),
    qualityHint: null,
    reasonSummary: candidate.reason || candidate.failedRules?.[0] || '',
    reasons: [candidate.reason, ...(candidate.failedRules || [])].filter((item): item is string => Boolean(item)),
    keyMetrics: Object.entries(candidate.metrics || {}).slice(0, 6).map(([label, value]) => ({ label, value: String(value ?? '--') })),
    featureSignals: [],
    riskNotes: [],
    watchContext: [],
    boards: [],
    appearedInRecentRuns: 0,
    lastTradeDate: null,
    scanTimestamp: null,
    aiInterpretation: {
      available: false,
      status: 'skipped',
      summary: null,
      opportunityType: null,
      riskInterpretation: null,
      watchPlan: null,
      reviewCommentary: null,
      provider: null,
      model: null,
      generatedAt: null,
      message: null,
    },
    realizedOutcome: {
      reviewStatus: 'pending',
      outcomeLabel: 'pending',
      thesisMatch: 'pending',
      reviewWindowDays: 3,
    },
    diagnostics: {},
  };
}

function fallbackDiagnosticFromCandidate(candidate: ScannerCandidate): ScannerCandidateDiagnostic {
  return {
    symbol: candidate.symbol,
    name: candidate.companyName || candidate.name,
    rank: candidate.rank,
    status: 'selected',
    score: candidate.score,
    provider: null,
    reason: candidate.reasonSummary,
    failedRules: [],
    missingFields: [],
    metrics: Object.fromEntries((candidate.keyMetrics || []).map((item) => [item.label, item.value])),
    metadata: {},
  };
}

function officialDiagnosticHandoffCandidates(
  candidates: ScannerCandidateDiagnostic[],
  shortlistCandidateBySymbol: Map<string | null, ScannerCandidate>,
): ScannerCandidate[] {
  return candidates.reduce<ScannerCandidate[]>((items, candidate) => {
    if (!isOfficialSelected(candidate)) return items;
    items.push(shortlistCandidateBySymbol.get(normalizeCandidateSymbol(candidate.symbol)) || diagnosticToCandidate(candidate));
    return items;
  }, []);
}

function normalizeScannerRunMarket(value?: string | null): ScannerRunRequest['market'] | null {
  const normalized = normalizeScannerMarket(value);
  if (normalized === 'US') return 'us';
  if (normalized === 'HK') return 'hk';
  if (normalized === 'CN') return 'cn';
  return null;
}

function normalizeScannerRunUniverseType(value?: string | null): ScannerRunRequest['universeType'] | null {
  const normalized = normalizeRunState(value);
  if (normalized === 'theme') return 'theme';
  if (normalized === 'symbols' || normalized === 'custom') return 'symbols';
  if (normalized === 'default') return 'default';
  return null;
}

function getRunAcceptedSymbols(runDetail: ScannerRunDetail): string[] {
  const diagnostics = isRecord(runDetail.diagnostics) ? runDetail.diagnostics : null;
  const universeSelection = getNestedRecord(diagnostics, 'universeSelection', 'universe_selection');
  const acceptedSymbols = getNestedStringArray(universeSelection, 'acceptedSymbols', 'accepted_symbols');
  const themeSymbols = Array.isArray(runDetail.theme?.symbols) ? runDetail.theme.symbols : [];
  return Array.from(new Set([...acceptedSymbols, ...themeSymbols].map((symbol) => symbol.trim().toUpperCase()).filter(Boolean)));
}

function buildScannerRetryRequest(runDetail: ScannerRunDetail | null): ScannerRunRequest | null {
  if (!runDetail) return null;
  const retryMarket = normalizeScannerRunMarket(runDetail.market);
  if (!retryMarket) return null;
  const defaults = SCANNER_PROFILE_DEFAULTS[retryMarket];
  const defaultShortlistSize = Number.parseInt(defaults.shortlistSize, 10);
  const defaultUniverseLimit = Number.parseInt(defaults.universeLimit, 10);
  const defaultDetailLimit = Number.parseInt(defaults.detailLimit, 10);
  const request: ScannerRunRequest = {
    market: retryMarket,
    profile: runDetail.profile || defaults.profile,
    shortlistSize: runDetail.shortlistSize > 0 ? runDetail.shortlistSize : defaultShortlistSize,
    universeLimit: runDetail.universeSize >= 50 ? runDetail.universeSize : defaultUniverseLimit,
    detailLimit: runDetail.preselectedSize >= 10 ? runDetail.preselectedSize : defaultDetailLimit,
  };
  const universeType = normalizeScannerRunUniverseType(runDetail.universeType);
  if (universeType === 'theme' && runDetail.themeId) {
    request.universeType = 'theme';
    request.themeId = runDetail.themeId;
  } else if (universeType === 'symbols') {
    const symbols = getRunAcceptedSymbols(runDetail);
    if (!symbols.length) return null;
    request.universeType = 'symbols';
    request.symbols = symbols;
  }
  return request;
}

function formatWorkbenchWatchSummary(
  candidate: ScannerCandidate,
  language: 'zh' | 'en',
): string {
  const entryRange = getEntryRange(candidate);
  const targetPrice = getTargetPrice(candidate);
  if (!entryRange && !targetPrice) {
    return language === 'en' ? 'No explicit observation band' : '未提供明确观察区';
  }
  return [
    entryRange ? `${language === 'en' ? 'Observation zone' : '观察区'} ${entryRange}` : null,
    targetPrice ? `${language === 'en' ? 'Reference range' : '参考区间'} ${targetPrice}` : null,
  ].filter(Boolean).join(' · ');
}

function formatWorkbenchRangeSummary(
  candidate: ScannerCandidate,
  language: 'zh' | 'en',
): string {
  const stopLoss = getStopLoss(candidate);
  const riskSummary = getRiskSummary(candidate, language);
  if (!stopLoss && !riskSummary) {
    return language === 'en' ? 'No explicit risk boundary' : '未提供明确风险边界';
  }
  return [
    stopLoss ? `${language === 'en' ? 'Risk boundary' : '风险边界'} ${stopLoss}` : null,
    riskSummary || null,
  ].filter(Boolean).join(' · ');
}

function buildRunComparison(
  currentRun: ScannerRunDetail | null,
  previousRun: ScannerRunDetail | null,
  threshold: number,
  language: 'zh' | 'en',
): ScannerComparisonState {
  if (!currentRun || !previousRun) {
    return { previousRun: previousRun || null, bySymbol: new Map(), chips: [] };
  }
  const previousBySymbol = new Map(
    getCandidateDiagnostics(previousRun).map((candidate) => [normalizeCandidateSymbol(candidate.symbol), candidate] as const),
  );
  const currentCandidates = getCandidateDiagnostics(currentRun);
  const bySymbol = new Map<string, CandidateComparison>();
  const chips: string[] = [];

  currentCandidates.forEach((candidate) => {
    const symbol = normalizeCandidateSymbol(candidate.symbol);
    if (!symbol) return;
    const previous = previousBySymbol.get(symbol);
    const currentStatus = normalizeDiagnosticStatus(candidate.status);
    const previousStatus = previous ? normalizeDiagnosticStatus(previous.status) : null;
    const scoreDelta = previous?.score != null && candidate.score != null ? Math.round(candidate.score - previous.score) : null;
    const rankDelta = previous?.rank != null && candidate.rank != null ? previous.rank - candidate.rank : null;
    let label = previous
      ? (language === 'en' ? 'Still a candidate' : '连续候选')
      : (language === 'en' ? 'First seen' : '首次出现');
    if (!previous) {
      label = isOfficialSelected(candidate)
        ? (language === 'en' ? 'New candidate' : '新晋候选')
        : (language === 'en' ? 'First seen' : '首次出现');
    } else if (previousStatus === 'selected' && currentStatus === 'selected') {
      label = language === 'en' ? 'Retained selected' : '连续入选';
    } else if (previousStatus === 'selected' && currentStatus !== 'selected') {
      label = language === 'en' ? 'Selected last run' : '上次入选';
    } else if (previousStatus !== 'selected' && currentStatus === 'selected') {
      label = language === 'en' ? 'Failed last run' : '上次未通过';
    } else if (rankDelta != null && rankDelta > 0) {
      label = language === 'en' ? 'Rank up' : '排名上升';
    } else if (rankDelta != null && rankDelta < 0) {
      label = language === 'en' ? 'Rank down' : '排名下降';
    } else if (scoreDelta != null && scoreDelta > 0) {
      label = language === 'en' ? 'Score up' : '评分上升';
    } else if (scoreDelta != null && scoreDelta < 0) {
      label = language === 'en' ? 'Score down' : '评分下降';
    } else if (isPreviewSelected(candidate, threshold) && !isPreviewSelected(previous, threshold)) {
      label = language === 'en' ? 'New preview selected' : '新预览入选';
    } else if (!isPreviewSelected(candidate, threshold) && isPreviewSelected(previous, threshold)) {
      label = language === 'en' ? 'Preview dropped' : '预览转淘汰';
    }
    bySymbol.set(symbol, { scoreDelta, rankDelta, previousStatus, currentStatus, label });
  });

  currentCandidates.slice(0, 8).forEach((candidate) => {
    const symbol = normalizeCandidateSymbol(candidate.symbol);
    const comparison = symbol ? bySymbol.get(symbol) : null;
    if (!symbol || !comparison) return;
    const delta = formatScoreDelta(comparison.scoreDelta);
    chips.push([symbol, comparison.label, delta ? (language === 'en' ? `score ${delta}` : `分数 ${delta}`) : null].filter(Boolean).join(' · '));
  });
  previousBySymbol.forEach((_previous, symbol) => {
    if (!symbol || currentCandidates.some((candidate) => normalizeCandidateSymbol(candidate.symbol) === symbol)) return;
    chips.push(`${symbol} · ${language === 'en' ? 'Dropped candidate' : '移出候选'}`);
  });

  return { previousRun, bySymbol, chips: chips.slice(0, 8) };
}

function buildRunComparisonHighlights(
  currentRun: ScannerRunDetail | null,
  previousRun: ScannerRunDetail | null,
  comparisonState: ScannerComparisonState,
  language: 'zh' | 'en',
): ScannerLabeledValue[] {
  if (!currentRun || !previousRun) return [];
  const currentCount = getRunSummaryCount(currentRun, 'selectedCount', currentRun.shortlist?.length || 0);
  const previousCount = getRunSummaryCount(previousRun, 'selectedCount', previousRun.shortlist?.length || 0);
  const currentBest = normalizeCandidateSymbol(currentRun.shortlist?.[0]?.symbol);
  const previousBest = normalizeCandidateSymbol(previousRun.shortlist?.[0]?.symbol);
  const currentScore = currentRun.shortlist?.[0]?.score;
  const previousScore = previousRun.shortlist?.[0]?.score;
  const scoreDelta = currentScore != null && previousScore != null ? Math.round(currentScore - previousScore) : null;
  const currentDataStatus = getRunDataStatusLabel(currentRun, language);
  const previousDataStatus = getRunDataStatusLabel(previousRun, language);
  const items: ScannerLabeledValue[] = [];

  const countDelta = currentCount - previousCount;
  if (countDelta > 0) {
    items.push({ label: language === 'en' ? 'Candidates' : '候选增加', value: `+${countDelta}` });
  } else if (countDelta < 0) {
    items.push({ label: language === 'en' ? 'Candidates' : '候选减少', value: String(countDelta) });
  }
  if (currentBest && previousBest && currentBest !== previousBest) {
    items.push({ label: language === 'en' ? 'Top-ranked row changed' : '排序首位（观察）变化', value: `${previousBest} -> ${currentBest}` });
  }
  if (scoreDelta != null && scoreDelta !== 0) {
    items.push({ label: language === 'en' ? 'Score' : '分数变化', value: formatScoreDelta(scoreDelta) || '0' });
  }
  if (currentDataStatus !== previousDataStatus) {
    items.push({ label: language === 'en' ? 'Data status' : '数据状态变化', value: `${previousDataStatus} -> ${currentDataStatus}` });
  }
  if (normalizeRunState(currentRun.status) === 'failed') {
    items.push({ label: language === 'en' ? 'Run state' : '运行状态', value: language === 'en' ? 'Run failed' : '运行失败' });
  } else if (currentCount === 0) {
    items.push({ label: language === 'en' ? 'Run state' : '运行状态', value: language === 'en' ? 'No candidates' : '无候选' });
  } else if (currentDataStatus === (language === 'en' ? 'Insufficient data' : '数据不足')) {
    items.push({ label: language === 'en' ? 'Run state' : '运行状态', value: language === 'en' ? 'Insufficient data' : '数据不足' });
  }
  comparisonState.chips.slice(0, 3).forEach((chip) => {
    items.push({ label: language === 'en' ? 'Candidate' : '候选变化', value: chip });
  });
  return items.slice(0, 8);
}

function findPreviousComparableRunId(
  currentRun: ScannerRunDetail | null,
  historyItems: ScannerRunHistoryItem[],
): number | null {
  if (!currentRun) return null;
  const currentMarket = String(currentRun.market || '').toLowerCase();
  const currentProfile = currentRun.profile || '';
  const currentThemeId = currentRun.themeId || null;
  const currentUniverseType = currentRun.universeType || '';
  const match = historyItems.find((item) => {
    if (item.id === currentRun.id) return false;
    if (String(item.market || '').toLowerCase() !== currentMarket) return false;
    if ((item.profile || '') !== currentProfile) return false;
    if ((item.universeType || '') !== currentUniverseType) return false;
    return (item.themeId || null) === currentThemeId;
  });
  return match?.id || null;
}

function parseCustomSymbols(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/[\s,，;；]+/)
        .flatMap((symbol) => {
          const normalized = symbol.trim().toUpperCase();
          return normalized ? [normalized] : [];
        }),
    ),
  );
}

function getSymbolTokenCount(value: string): number {
  return value.split(/[\s,，;；]+/).reduce((count, symbol) => count + (symbol.trim() ? 1 : 0), 0);
}

function getThemeLabel(theme: ScannerTheme, language: 'zh' | 'en'): string {
  return language === 'en' ? theme.labelEn : theme.labelZh;
}

function getScannerMarketLabel(market: 'cn' | 'us' | 'hk', language: 'zh' | 'en'): string {
  if (market === 'us') return language === 'en' ? 'US' : '美股';
  if (market === 'hk') return language === 'en' ? 'HK' : '港股';
  return language === 'en' ? 'CN' : 'A股';
}

function buildScannerFirstRunSetupLabel({
  market,
  scanScope,
  universeLimit,
  detailLimit,
  selectedTheme,
  customSymbolCount,
  language,
}: {
  market: 'cn' | 'us' | 'hk';
  scanScope: ScanScope;
  universeLimit: string;
  detailLimit: string;
  selectedTheme: ScannerTheme | null;
  customSymbolCount: number;
  language: 'zh' | 'en';
}): string {
  const parts = [getScannerMarketLabel(market, language)];

  if (scanScope === 'theme') {
    parts.push(language === 'en' ? 'Theme scope' : '主题标的池');
    parts.push(selectedTheme ? getThemeLabel(selectedTheme, language) : (language === 'en' ? 'Select a theme' : '选择主题'));
  } else if (scanScope === 'symbols') {
    parts.push(language === 'en' ? 'Custom symbols' : '自定义标的');
    parts.push(
      customSymbolCount > 0
        ? (language === 'en' ? `${customSymbolCount} symbols` : `${customSymbolCount} 个代码`)
        : (language === 'en' ? 'Add symbols' : '补充代码'),
    );
  } else {
    parts.push(language === 'en' ? 'Default market scope' : '默认市场池');
    parts.push(language === 'en' ? `${universeLimit} names` : `${universeLimit} 只`);
  }

  parts.push(language === 'en' ? `${detailLimit} detailed reviews` : `${detailLimit} 条详评`);
  return parts.join(' · ');
}

function buildCustomThemeId(label: string): string {
  const slug = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 48);
  return `custom_${slug || 'scanner_theme'}`;
}

function hasReviewSummary(review?: ScannerReviewSummary | null): boolean {
  return Boolean(review?.available || review?.reviewedCount || review?.candidateCount);
}

function hasComparison(comparison?: ScannerWatchlistComparison | null): boolean {
  return Boolean(comparison?.available || comparison?.newCount || comparison?.retainedCount || comparison?.droppedCount);
}

function hasOutcome(outcome?: ScannerCandidateOutcome | null): boolean {
  return Boolean(outcome && (outcome.reviewStatus !== 'pending' || outcome.outcomeLabel !== 'pending' || outcome.reviewWindowReturnPct != null));
}

function dedupeTickerSymbols(symbols: string[]): string[] {
  return Array.from(
    new Set(
      symbols.flatMap((symbol) => {
        const normalized = symbol.trim();
        return normalized ? [normalized] : [];
      }),
    ),
  );
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function formatHistoryHeadline(
  headline: string | null | undefined,
  topSymbols: string[],
  fallbackTitle: string,
): { title: string; detail: string | null; symbols: string[] } {
  const symbols = dedupeTickerSymbols(topSymbols);
  const trimmedHeadline = headline?.trim() || '';
  if (!trimmedHeadline) {
    return { title: fallbackTitle, detail: null, symbols };
  }

  if (!symbols.length) {
    return { title: trimmedHeadline, detail: null, symbols };
  }

  const symbolPattern = new RegExp(`\\b(?:${symbols.map(escapeRegExp).join('|')})\\b`, 'i');
  const explicitSplit = trimmedHeadline.match(/^(.*?)[：:]\s*(.+)$/);
  if (explicitSplit && symbolPattern.test(explicitSplit[2] || '')) {
    return {
      title: explicitSplit[1]?.trim() || fallbackTitle,
      detail: null,
      symbols,
    };
  }

  const firstSymbolIndex = trimmedHeadline.search(symbolPattern);
  if (firstSymbolIndex > 0) {
    const titleCandidate = trimmedHeadline.slice(0, firstSymbolIndex).replace(/[/,，:：\-\s]+$/, '').trim();
    if (titleCandidate) {
      return {
        title: titleCandidate,
        detail: null,
        symbols,
      };
    }
  }

  return { title: trimmedHeadline, detail: null, symbols };
}

function statusVariant(status?: string | null): 'success' | 'warning' | 'danger' | 'history' {
  if (status === 'completed') return 'success';
  if (status === 'empty') return 'warning';
  if (status === 'failed') return 'danger';
  return 'history';
}

function marketVariant(market?: string | null): 'success' | 'info' | 'warning' | 'history' {
  if (market === 'us') return 'success';
  if (market === 'hk') return 'warning';
  if (market === 'cn') return 'info';
  return 'history';
}

type ScannerExportRow = {
  rank: number;
  symbol: string;
  name: string;
  scannerScore: number;
  observationZone: string;
  referenceRange: string;
  riskBoundary: string;
  reason: string;
  risk: string;
  universeType: string;
  theme: string;
  generatedAt: string;
  runId: number | string;
};

function buildScannerExportRow(
  candidate: ScannerCandidate,
  runDetail: ScannerRunDetail,
  language: 'zh' | 'en',
): ScannerExportRow {
  return {
    rank: candidate.rank,
    symbol: candidate.symbol,
    name: candidate.companyName || candidate.name,
    scannerScore: candidate.score,
    observationZone: getEntryRange(candidate) || '',
    referenceRange: getTargetPrice(candidate) || '',
    riskBoundary: getStopLoss(candidate) || '',
    reason: getKeyReason(candidate, runDetail, language),
    risk: getRiskSummary(candidate, language),
    universeType: runDetail.universeType || '',
    theme: runDetail.themeLabel || runDetail.themeId || '',
    generatedAt: runDetail.completedAt || runDetail.runAt || '',
    runId: runDetail.id,
  };
}

function buildScannerCsv(rows: ScannerExportRow[]): string {
  const headers = ['rank', 'symbol', 'name', 'scannerScore', 'observationZone', 'referenceRange', 'riskBoundary', 'reason', 'risk', 'universeType', 'theme', 'generatedAt', 'runId'];
  return [
    headers.join(','),
    ...rows.map((row) => headers.map((header) => serializeCsvCell(row[header as keyof ScannerExportRow])).join(',')),
  ].join('\n');
}

function buildScannerExportFilename(runDetail: ScannerRunDetail, suffix = 'results'): string {
  const datePart = (runDetail.watchlistDate || runDetail.completedAt || runDetail.runAt || new Date().toISOString()).slice(0, 10);
  const safeDatePart = datePart.replace(/[^0-9-]/g, '') || 'unknown-date';
  const safeMarket = (runDetail.market || 'scanner').toLowerCase();
  return `scanner_${safeMarket}_${safeDatePart}_run-${runDetail.id}_${suffix}.csv`;
}

function downloadScannerCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(objectUrl);
}

const UserScannerPage: React.FC = () => {
  const { isReady: isSafariReady, surfaceRef } = useSafariRenderReady();
  const shouldGuardA11y = shouldApplySafariA11yGuard();
  const { t, language } = useI18n();
  const { isAdminAccount, canReadProviders } = useProductSurface();
  const navigate = useNavigate();
  const [market, setMarket] = useState<'cn' | 'us' | 'hk'>('cn');
  const [profile, setProfile] = useState('cn_preopen_v1');
  const [shortlistSize, setShortlistSize] = useState('5');
  const [universeLimit, setUniverseLimit] = useState('300');
  const [detailLimit, setDetailLimit] = useState('60');
  const [scanScope, setScanScope] = useState<ScanScope>('default');
  const [themes, setThemes] = useState<ScannerTheme[]>([]);
  const [themeId, setThemeId] = useState('');
  const [customThemeLabel, setCustomThemeLabel] = useState('');
  const [customThemePrompt, setCustomThemePrompt] = useState('');
  const [customThemeManualSymbols, setCustomThemeManualSymbols] = useState('');
  const [themeSuggestions, setThemeSuggestions] = useState<ScannerThemeSuggestion[]>([]);
  const [isGeneratingTheme, setIsGeneratingTheme] = useState(false);
  const [customSymbols, setCustomSymbols] = useState('');
  const [runDetail, setRunDetail] = useState<ScannerRunDetail | null>(null);
  const [scannerOperationalStatus, setScannerOperationalStatus] = useState<ScannerOperationalStatusWithDataReadiness | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [historyItems, setHistoryItems] = useState<ScannerRunHistoryItem[]>([]);
  const [hasLoadedHistory, setHasLoadedHistory] = useState(false);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [pageError, setPageError] = useState<ParsedApiError | null>(null);
  const [historyError, setHistoryError] = useState<ParsedApiError | null>(null);
  const [actionNotice, setActionNotice] = useState<ActionNotice>(null);
  const [scannerRunFeedback, setScannerRunFeedback] = useState<ScannerRunFeedback | null>(null);
  const [validationErrors, setValidationErrors] = useState<ScannerValidationErrors>({});
  const [isHistoryDrawerOpen, setIsHistoryDrawerOpen] = useState(false);
  const [watchlistItems, setWatchlistItems] = useState<WatchlistItem[]>([]);
  const [watchlistAuthBlocked, setWatchlistAuthBlocked] = useState(false);
  const [pendingWatchlistIdentity, setPendingWatchlistIdentity] = useState<string | null>(null);
  const [pendingBatchWatchlistAction, setPendingBatchWatchlistAction] = useState<string | null>(null);
  const [manualRecoverySymbol, setManualRecoverySymbol] = useState('');
  const [isMoreActionsOpen, setIsMoreActionsOpen] = useState(false);
  const [rowMoreSymbol, setRowMoreSymbol] = useState<string | null>(null);
  const [isRejectionSummaryOpen, setIsRejectionSummaryOpen] = useState(false);
  const [previousRunDetail, setPreviousRunDetail] = useState<ScannerRunDetail | null>(null);
  const [previewThreshold, setPreviewThreshold] = useState(50);
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [inspectorSymbol, setInspectorSymbol] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [candidateFilter, setCandidateFilter] = useState<CandidateFilter>('selected');
  const [simulationLookbackDays, setSimulationLookbackDays] = useState(90);
  const [simulationForwardDays, setSimulationForwardDays] = useState(5);
  const [strategySimulation, setStrategySimulation] = useState<ScannerStrategySimulationResult | null>(null);
  const [isStrategySimulationLoading, setIsStrategySimulationLoading] = useState(false);
  const [strategySimulationError, setStrategySimulationError] = useState<string | null>(null);
  const [viewportWidth, setViewportWidth] = useState(() => (typeof window === 'undefined' ? 1440 : window.innerWidth));
  const selectedRunIdRef = useRef<number | null>(null);
  const scannerRunInFlightRef = useRef(false);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const handleResize = () => setViewportWidth(window.innerWidth);
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const profileOptions = useMemo(
    () => getScannerProfileOptions(market, t).map((option) => ({
      ...option,
      label: sanitizeScannerProfileLabel(option.label),
    })),
    [market, t],
  );
  const universeOptions = useMemo(() => getScannerUniverseOptions(market, language), [language, market]);
  const detailOptions = useMemo(() => getScannerDetailOptions(market, language), [language, market]);
  const marketThemes = useMemo(
    () => themes.filter((theme) => theme.market === market),
    [market, themes],
  );
  const configuredMarketThemes = useMemo(
    () => marketThemes.filter((theme) => theme.symbols.length > 0),
    [marketThemes],
  );
  const unconfiguredMarketThemes = useMemo(
    () => marketThemes.filter((theme) => theme.symbols.length === 0),
    [marketThemes],
  );
  const selectedTheme = useMemo(
    () => marketThemes.find((theme) => theme.id === themeId) || null,
    [marketThemes, themeId],
  );
  const parsedCustomSymbols = useMemo(() => parseCustomSymbols(customSymbols), [customSymbols]);
  const parsedThemeManualSymbols = useMemo(() => parseCustomSymbols(customThemeManualSymbols), [customThemeManualSymbols]);
  const customSymbolTokenCount = useMemo(() => getSymbolTokenCount(customSymbols), [customSymbols]);
  const customThemeManualSymbolTokenCount = useMemo(() => getSymbolTokenCount(customThemeManualSymbols), [customThemeManualSymbols]);
  const scannerFirstRunSetupLabel = useMemo(
    () => buildScannerFirstRunSetupLabel({
      market,
      scanScope,
      universeLimit,
      detailLimit,
      selectedTheme,
      customSymbolCount: parsedCustomSymbols.length,
      language,
    }),
    [detailLimit, language, market, parsedCustomSymbols.length, scanScope, selectedTheme, universeLimit],
  );

  const handleMarketChange = useCallback((nextMarket: string) => {
    const normalizedMarket = nextMarket === 'us' ? 'us' : nextMarket === 'hk' ? 'hk' : 'cn';
    const defaults = SCANNER_PROFILE_DEFAULTS[normalizedMarket];
    setMarket(normalizedMarket);
    setProfile(defaults.profile);
    setShortlistSize(defaults.shortlistSize);
    setUniverseLimit(defaults.universeLimit);
    setDetailLimit(defaults.detailLimit);
    setThemeId('');
    setValidationErrors({});
  }, []);

  useEffect(() => {
    let isMounted = true;
    scannerApi.getThemes()
      .then((response) => {
        if (!isMounted) return;
        setThemes(response.items || []);
      })
      .catch((error) => {
        if (!isMounted) return;
        setPageError(getParsedApiError(error));
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    scannerApi.getStatus({ market, profile })
      .then((response) => {
        if (!isMounted) return;
        setScannerOperationalStatus(response);
      })
      .catch(() => {
        if (!isMounted) return;
        setScannerOperationalStatus(null);
      });
    return () => {
      isMounted = false;
    };
  }, [market, profile]);

  useEffect(() => {
    if (scanScope !== 'theme') return;
    if (selectedTheme?.market === market) return;
    const firstConfiguredTheme = marketThemes.find((theme) => theme.symbols.length > 0);
    setThemeId(firstConfiguredTheme?.id || '');
  }, [market, marketThemes, scanScope, selectedTheme?.market]);

  useEffect(() => {
    let isMounted = true;
    watchlistApi.listWatchlistItems()
      .then((response) => {
        if (!isMounted) return;
        setWatchlistItems(response.items || []);
        setWatchlistAuthBlocked(false);
      })
      .catch((error) => {
        if (!isMounted) return;
        const parsedError = getParsedApiError(error);
        if (parsedError.isAuthError || parsedError.status === 401 || parsedError.status === 403 || parsedError.status === 405) {
          setWatchlistAuthBlocked(true);
          return;
        }
        setWatchlistItems([]);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const loadRun = useCallback(async (runId: number) => {
    try {
      const response = await scannerApi.getRun(runId);
      setRunDetail(response);
      selectedRunIdRef.current = response.id;
      setSelectedRunId(response.id);
      setPageError(null);
    } catch (error) {
      setPageError(getParsedApiError(error));
    }
  }, []);

  const fetchHistory = useCallback(async (
    page = 1,
    preferredRunId?: number | null,
    scopeOverride?: { market?: string; profile?: string },
  ) => {
    setIsLoadingHistory(true);
    try {
      const response = await scannerApi.getRuns({
        market: scopeOverride?.market || market,
        profile: scopeOverride?.profile || profile,
        page,
        limit: HISTORY_PAGE_SIZE,
      });
      const historyItemsNext = Array.isArray(response.items) ? response.items : [];
      setHistoryItems(historyItemsNext);
      setHistoryTotal(typeof response.total === 'number' ? response.total : 0);
      setHistoryPage(typeof response.page === 'number' ? response.page : page);
      setHistoryError(null);

      const currentSelectedRunId = selectedRunIdRef.current;
      const targetRunId = preferredRunId
        || (currentSelectedRunId && historyItemsNext.some((item) => item.id === currentSelectedRunId) ? currentSelectedRunId : null)
        || historyItemsNext[0]?.id
        || null;
      if (targetRunId && targetRunId !== currentSelectedRunId) {
        void loadRun(targetRunId);
      }
      if (!targetRunId) {
        setRunDetail(null);
        selectedRunIdRef.current = null;
        setSelectedRunId(null);
      }
    } catch (error) {
      setHistoryError(getParsedApiError(error));
    } finally {
      setHasLoadedHistory(true);
      setIsLoadingHistory(false);
    }
  }, [loadRun, market, profile]);

  useEffect(() => {
    setHasLoadedHistory(false);
    setRunDetail(null);
    setScannerOperationalStatus(null);
    selectedRunIdRef.current = null;
    setSelectedRunId(null);
    setStrategySimulation(null);
    setStrategySimulationError(null);
  }, [market, profile]);

  useEffect(() => {
    void fetchHistory(1);
  }, [fetchHistory]);

  const executeScannerRun = useCallback(async (request: ScannerRunRequest) => {
    if (scannerRunInFlightRef.current) return;
    scannerRunInFlightRef.current = true;
    setIsRunning(true);
    setScannerRunFeedback(buildScannerPendingFeedback(language));
    try {
      const response = await scannerApi.run(request);
      setRunDetail(response);
      selectedRunIdRef.current = response.id;
      setSelectedRunId(response.id);
      setValidationErrors({});
      setPageError(null);
      setScannerRunFeedback(buildScannerSuccessFeedback(response, language, scannerFirstRunSetupLabel));
      await fetchHistory(1, response.id, { market: request.market, profile: request.profile });
    } catch (error) {
      const parsedError = getParsedApiError(error);
      setPageError(parsedError);
      setScannerRunFeedback(buildScannerErrorFeedback(parsedError, language));
    } finally {
      scannerRunInFlightRef.current = false;
      setIsRunning(false);
    }
  }, [fetchHistory, language, scannerFirstRunSetupLabel]);

  const handleRun = useCallback(async () => {
    const retryState = buildScannerConclusion(
      runDetail,
      language,
      scannerFirstRunSetupLabel,
      { hasLoaded: true, latestRun: null },
      null,
    ).state;
    const retryRequest = retryState === 'no-candidate' || retryState === 'insufficient'
      ? buildScannerRetryRequest(runDetail)
      : null;
    if (retryRequest) {
      await executeScannerRun(retryRequest);
      return;
    }

    const nextErrors: ScannerValidationErrors = {};
    const parsedShortlistSize = Number.parseInt(shortlistSize, 10);
    const parsedUniverseLimit = Number.parseInt(universeLimit, 10);
    const parsedDetailLimit = Number.parseInt(detailLimit, 10);
    if (!Number.isFinite(parsedShortlistSize) || parsedShortlistSize < 1) {
      nextErrors.run = language === 'en' ? 'Choose a valid shortlist size.' : '请选择有效的入选数量。';
    }
    if (!Number.isFinite(parsedUniverseLimit) || parsedUniverseLimit < 50) {
      nextErrors.run = language === 'en' ? 'Scope size must be at least 50.' : '候选池数量至少为 50。';
    }
    if (!Number.isFinite(parsedDetailLimit) || parsedDetailLimit < 10) {
      nextErrors.run = language === 'en' ? 'Detail evaluation count must be at least 10.' : '详细评估数量至少为 10。';
    }
    if (scanScope === 'theme' && (!selectedTheme || selectedTheme.symbols.length === 0)) {
      nextErrors.theme = language === 'en' ? 'Select a configured theme before running.' : '请先选择已配置成分股的主题。';
    }
    if (scanScope === 'symbols') {
      if (customSymbolTokenCount > 0 && parsedCustomSymbols.length === 0) {
        nextErrors.customSymbols = language === 'en' ? 'Enter at least one valid symbol.' : '请输入至少一个有效标的代码。';
      } else if (parsedCustomSymbols.length === 0) {
        nextErrors.customSymbols = language === 'en' ? 'Enter one or more symbols before running.' : '运行前请输入一个或多个标的代码。';
      } else if (parsedCustomSymbols.length > 80) {
        nextErrors.customSymbols = language === 'en' ? 'Use 80 symbols or fewer.' : '自定义标的最多 80 个。';
      }
    }
    if (Object.keys(nextErrors).length) {
      setValidationErrors(nextErrors);
      const message = firstScannerValidationMessage(nextErrors);
      if (message) {
        setScannerRunFeedback(buildScannerValidationFeedback(message, language));
      }
      return;
    }
    await executeScannerRun({
      market,
      profile,
      shortlistSize: parsedShortlistSize,
      universeLimit: parsedUniverseLimit,
      detailLimit: parsedDetailLimit,
      ...(scanScope !== 'default' ? { universeType: scanScope } : {}),
      ...(scanScope === 'theme' ? { themeId } : {}),
      ...(scanScope === 'symbols' ? { symbols: parsedCustomSymbols } : {}),
    });
  }, [customSymbolTokenCount, detailLimit, executeScannerRun, language, market, parsedCustomSymbols, profile, runDetail, scanScope, scannerFirstRunSetupLabel, selectedTheme, shortlistSize, themeId, universeLimit]);

  const handleRetryCurrentRun = useCallback(async () => {
    const retryRequest = buildScannerRetryRequest(runDetail);
    if (retryRequest) {
      await executeScannerRun(retryRequest);
      return;
    }
    await handleRun();
  }, [executeScannerRun, handleRun, runDetail]);

  const handleGenerateTheme = useCallback(async () => {
    const label = customThemeLabel.trim();
    const prompt = customThemePrompt.trim();
    const nextErrors: ScannerValidationErrors = {};
    if (label.length < 2) {
      nextErrors.customThemeLabel = language === 'en' ? 'Theme name must be at least 2 characters.' : '主题名称至少需要 2 个字符。';
    } else if (label.length > 80) {
      nextErrors.customThemeLabel = language === 'en' ? 'Theme name must be 80 characters or fewer.' : '主题名称最多 80 个字符。';
    }
    if (prompt.length < 12) {
      nextErrors.customThemePrompt = language === 'en' ? 'Criteria must be at least 12 characters.' : '筛选条件至少需要 12 个字符。';
    } else if (prompt.length > 600) {
      nextErrors.customThemePrompt = language === 'en' ? 'Criteria must be 600 characters or fewer.' : '筛选条件最多 600 个字符。';
    }
    if (parsedThemeManualSymbols.length > 50) {
      nextErrors.customThemeManualSymbols = language === 'en' ? 'Manual additions are limited to 50 symbols.' : '手动补充标的最多 50 个。';
    } else if (customThemeManualSymbolTokenCount > 0 && parsedThemeManualSymbols.length === 0) {
      nextErrors.customThemeManualSymbols = language === 'en' ? 'Enter valid symbols or leave this field empty.' : '请输入有效标的代码，或留空。';
    }
    if (Object.keys(nextErrors).length) {
      setValidationErrors(nextErrors);
      return;
    }
    setIsGeneratingTheme(true);
    try {
      const response = await scannerApi.createTheme({
        id: buildCustomThemeId(label),
        label,
        market,
        prompt,
        manualSymbols: parsedThemeManualSymbols,
      });
      setThemes((current) => [
        ...current.filter((theme) => theme.id !== response.theme.id),
        response.theme,
      ]);
      setThemeId(response.theme.id);
      setThemeSuggestions(response.suggestions || []);
      setValidationErrors({});
      setActionNotice({
        tone: 'success',
        message: language === 'en'
          ? `Generated ${response.theme.symbols.length} symbols for ${getThemeLabel(response.theme, language)}.`
          : `已为 ${getThemeLabel(response.theme, language)} 生成 ${response.theme.symbols.length} 个标的。`,
      });
      setPageError(null);
    } catch (error) {
      setPageError(getParsedApiError(error));
    } finally {
      setIsGeneratingTheme(false);
    }
  }, [customThemeLabel, customThemeManualSymbolTokenCount, customThemePrompt, language, market, parsedThemeManualSymbols]);

  const handleSortChange = useCallback((nextSortKey: SortKey) => {
    if (sortKey === nextSortKey) {
      setSortDirection((current) => current === 'asc' ? 'desc' : 'asc');
      return;
    }
    setSortKey(nextSortKey);
    setSortDirection(nextSortKey === 'symbol' ? 'asc' : 'desc');
  }, [sortKey]);

  const totalHistoryPages = useMemo(
    () => Math.max(1, Math.ceil(historyTotal / HISTORY_PAGE_SIZE)),
    [historyTotal],
  );
  const trackedWatchlistIdentitySet = useMemo(
    () => new Set(watchlistItems.map((item) => getWatchlistIdentity(item.market, item.symbol))),
    [watchlistItems],
  );
  const {
    ref: runScannerButtonRef,
    onClick: handleRunScannerClick,
    onPointerUp: handleRunScannerPointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(() => {
    void handleRun();
  });
  const {
    ref: generateThemeButtonRef,
    onClick: handleGenerateThemeClick,
    onPointerUp: handleGenerateThemePointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(() => {
    void handleGenerateTheme();
  });
  const {
    ref: openHistoryDrawerButtonRef,
    onClick: handleOpenHistoryDrawerClick,
    onPointerUp: handleOpenHistoryDrawerPointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(() => setIsHistoryDrawerOpen(true));
  const shortlistCount = runDetail?.shortlist?.length ?? 0;
  const currentSelectedCount = runDetail ? getRunSummaryCount(runDetail, 'selectedCount', shortlistCount) : 0;
  const generatedAt = runDetail?.completedAt || runDetail?.runAt || null;
  const runDisabled = isRunning;
  const generateThemeDisabled = isGeneratingTheme;

  const sortedCandidates = useMemo(() => {
    const candidates = [...(runDetail?.shortlist || [])];
    const directionMultiplier = sortDirection === 'asc' ? 1 : -1;
    return candidates.sort((left, right) => {
      let compare = 0;
      if (sortKey === 'symbol') {
        compare = left.symbol.localeCompare(right.symbol);
      } else if (sortKey === 'target') {
        const leftTarget = parseFirstNumericValue(getTargetPrice(left));
        const rightTarget = parseFirstNumericValue(getTargetPrice(right));
        compare = (leftTarget ?? Number.NEGATIVE_INFINITY) - (rightTarget ?? Number.NEGATIVE_INFINITY);
      } else if (sortKey === 'risk') {
        const leftRisk = getRiskScore(left);
        const rightRisk = getRiskScore(right);
        compare = (leftRisk ?? Number.NEGATIVE_INFINITY) - (rightRisk ?? Number.NEGATIVE_INFINITY);
      } else {
        compare = left.score - right.score;
      }
      if (compare === 0) return left.rank - right.rank;
      return compare * directionMultiplier;
    });
  }, [runDetail?.shortlist, sortDirection, sortKey]);
  const diagnosticCandidates = useMemo(() => getCandidateDiagnostics(runDetail), [runDetail]);
  const hasCandidateDiagnostics = diagnosticCandidates.length > 0;
  const inferredPreviewThreshold = useMemo(
    () => inferPreviewThreshold(runDetail, diagnosticCandidates),
    [diagnosticCandidates, runDetail],
  );
  useEffect(() => {
    if (!runDetail) return;
    setPreviewThreshold(inferredPreviewThreshold);
  }, [inferredPreviewThreshold, runDetail]);
  const previewSelectedDiagnostics = useMemo(
    () => diagnosticCandidates.filter((candidate) => isPreviewSelected(candidate, previewThreshold)),
    [diagnosticCandidates, previewThreshold],
  );
  const officialSelectedDiagnostics = useMemo(
    () => diagnosticCandidates.filter(isOfficialSelected),
    [diagnosticCandidates],
  );
  const rejectionBuckets = useMemo(
    () => buildRejectionBuckets(diagnosticCandidates, language),
    [diagnosticCandidates, language],
  );
  const comparisonState = useMemo(
    () => buildRunComparison(runDetail, previousRunDetail, previewThreshold, language),
    [language, previewThreshold, previousRunDetail, runDetail],
  );
  const scannerDataReadiness = getRunDetailDataReadiness(runDetail)
    || scannerOperationalStatus?.dataReadiness
    || null;
  const scannerDataReadinessView = useMemo(
    () => buildScannerDataReadinessView(scannerDataReadiness, language),
    [language, scannerDataReadiness],
  );
  const scannerOperatorReadinessHref = isAdminAccount && canReadProviders
    ? buildLocalizedPath('/admin/market-providers', language)
    : null;
  const currentRunSummary = useMemo(
    () => buildScannerRunSummary(language === 'en' ? 'Current scan' : '本次扫描', runDetail, language),
    [language, runDetail],
  );
  const scannerHasPseudoEmptyRun = isScannerPseudoEmptyRun(runDetail);
  const scannerHasReadinessBlockedEmptyRun = Boolean(
    runDetail
    && scannerDataReadinessView?.isMeaningful
    && currentSelectedCount === 0
    && !(runDetail.shortlist?.length)
    && !(runDetail.selected?.length)
    && diagnosticCandidates.length === 0
    && !['failed', 'failure', 'error'].includes(normalizeRunState(runDetail.status)),
  );
  const scannerShouldHideEmptyRunCounts = scannerHasPseudoEmptyRun || scannerHasReadinessBlockedEmptyRun;
  const scannerWorkspaceState = useMemo(
    () => resolveScannerWorkspaceState({
      isRunning,
      pageErrorSummary: pageError
        ? (isScannerAuthOrAccessError(pageError)
          ? getScannerSafeApiErrorMessage(pageError, language)
          : sanitizeScannerErrorSummary(pageError.message, language) || compactScannerStateLabel('failed', language))
        : null,
      runDetail,
      historyResolution: {
        hasLoaded: hasLoadedHistory,
        latestRun: historyItems[0] || null,
      },
      dataReadinessView: scannerDataReadinessView,
      selectedCount: currentSelectedCount,
      language,
    }),
    [
      currentSelectedCount,
      hasLoadedHistory,
      historyItems,
      isRunning,
      language,
      pageError,
      runDetail,
      scannerDataReadinessView,
    ],
  );
  const recentRunSummary = useMemo(
    () => buildHistoryItemSummary(language === 'en' ? 'Latest scan' : '最近扫描', historyItems[0] || null, language),
    [historyItems, language],
  );
  const previousRunSummary = useMemo(
    () => buildScannerRunSummary(language === 'en' ? 'Previous scan' : '上次扫描', previousRunDetail, language),
    [language, previousRunDetail],
  );
  const comparisonHighlights = useMemo(
    () => buildRunComparisonHighlights(runDetail, previousRunDetail, comparisonState, language),
    [comparisonState, language, previousRunDetail, runDetail],
  );
  const filteredDiagnosticCandidates = useMemo(() => {
    if (candidateFilter === 'selected') {
      return diagnosticCandidates.filter((candidate) => candidate.status === 'selected');
    }
    if (candidateFilter === 'pool') {
      return diagnosticCandidates;
    }
    if (candidateFilter === 'rejected') {
      return diagnosticCandidates.filter((candidate) => candidate.status === 'rejected');
    }
    if (candidateFilter === 'data_failed') {
      return diagnosticCandidates.filter((candidate) => candidate.status === 'data_failed' || candidate.status === 'error');
    }
    return diagnosticCandidates;
  }, [candidateFilter, diagnosticCandidates]);
  const decisionSortedDiagnosticCandidates = useMemo(
    () => sortDiagnosticsForDecision(filteredDiagnosticCandidates, previewThreshold),
    [filteredDiagnosticCandidates, previewThreshold],
  );
  const shortlistCandidateBySymbol = useMemo(
    () => new Map(sortedCandidates.map((candidate) => [normalizeCandidateSymbol(candidate.symbol), candidate] as const)),
    [sortedCandidates],
  );
  const workbenchDiagnostics = useMemo(
    () => (hasCandidateDiagnostics ? decisionSortedDiagnosticCandidates : sortedCandidates.map(fallbackDiagnosticFromCandidate)),
    [decisionSortedDiagnosticCandidates, hasCandidateDiagnostics, sortedCandidates],
  );
  const activeDetailDiagnostic = useMemo(() => {
    if (!workbenchDiagnostics.length) return null;
    const normalizedInspector = normalizeCandidateSymbol(inspectorSymbol);
    if (normalizedInspector) {
      const matched = workbenchDiagnostics.find((candidate) => normalizeCandidateSymbol(candidate.symbol) === normalizedInspector);
      if (matched) return matched;
    }
    return workbenchDiagnostics[0] || null;
  }, [inspectorSymbol, workbenchDiagnostics]);
  const activeDetailCandidate = useMemo(() => {
    if (!activeDetailDiagnostic) return null;
    return shortlistCandidateBySymbol.get(normalizeCandidateSymbol(activeDetailDiagnostic.symbol)) || diagnosticToCandidate(activeDetailDiagnostic);
  }, [activeDetailDiagnostic, shortlistCandidateBySymbol]);
  const topFiveDiagnostics = useMemo(
    () => sortDiagnosticsForDecision(diagnosticCandidates, previewThreshold).slice(0, 5),
    [diagnosticCandidates, previewThreshold],
  );
  const previewHandoffCandidates = useMemo(
    () => officialDiagnosticHandoffCandidates(previewSelectedDiagnostics, shortlistCandidateBySymbol),
    [previewSelectedDiagnostics, shortlistCandidateBySymbol],
  );
  const topFiveHandoffCandidates = useMemo(
    () => officialDiagnosticHandoffCandidates(topFiveDiagnostics, shortlistCandidateBySymbol),
    [topFiveDiagnostics, shortlistCandidateBySymbol],
  );
  const currentFilterHandoffCandidates = useMemo(
    () => officialDiagnosticHandoffCandidates(workbenchDiagnostics, shortlistCandidateBySymbol),
    [shortlistCandidateBySymbol, workbenchDiagnostics],
  );
  const {
    backtestCounts,
    backtestItems,
    backtestUnavailableLabel,
    getBacktestItem,
    handleBacktestBatch,
    handleBacktestCandidate,
    isBacktestBatchRunning,
  } = useScannerBacktestLab({
    language,
    batchCandidatesBySource: {
      official_selected: sortedCandidates,
      preview_selected: previewHandoffCandidates,
      top_5: topFiveHandoffCandidates,
      current_filter: currentFilterHandoffCandidates,
    },
  });
  const activeDetailBacktestItem = getBacktestItem(activeDetailCandidate?.symbol);
  const activeDetailWatchlistIdentity = activeDetailDiagnostic
    ? getWatchlistIdentity(runDetail?.market || market, activeDetailDiagnostic.symbol)
    : '';
  const activeDetailTracked = Boolean(activeDetailWatchlistIdentity && trackedWatchlistIdentitySet.has(activeDetailWatchlistIdentity));
  const activeDetailTrackPending = pendingWatchlistIdentity === activeDetailWatchlistIdentity;
  const activeSimulationTheme = runDetail?.themeId || (scanScope === 'theme' ? themeId : null);
  const strategySimulationDisabled = !runDetail || (runDetail.universeType === 'theme' && !runDetail.themeId);
  const showDetailRail = viewportWidth >= 1600 && Boolean(activeDetailCandidate);

  const handleStrategySimulation = useCallback(async () => {
    if (!runDetail) return;
    setIsStrategySimulationLoading(true);
    try {
      const response = await scannerApi.getStrategySimulation({
        theme: activeSimulationTheme || undefined,
        profile: runDetail.profile || profile,
        market: runDetail.market || market,
        lookbackDays: simulationLookbackDays,
        forwardDays: simulationForwardDays,
        limit: 50,
      });
      setStrategySimulation(response);
      setStrategySimulationError(null);
    } catch (error) {
      const parsed = getParsedApiError(error);
      setStrategySimulationError(parsed.message || (language === 'en' ? 'Simulation failed.' : '历史模拟失败。'));
    } finally {
      setIsStrategySimulationLoading(false);
    }
  }, [activeSimulationTheme, language, market, profile, runDetail, simulationForwardDays, simulationLookbackDays]);

  useEffect(() => {
    if (!hasCandidateDiagnostics && candidateFilter !== 'selected') {
      setCandidateFilter('selected');
    }
  }, [candidateFilter, hasCandidateDiagnostics]);

  useEffect(() => {
    if (!workbenchDiagnostics.length) {
      setInspectorSymbol(null);
      return;
    }
    const current = activeDetailDiagnostic;
    if (current && (!inspectorSymbol || normalizeCandidateSymbol(current.symbol) !== normalizeCandidateSymbol(inspectorSymbol))) {
      setInspectorSymbol(current.symbol);
    }
  }, [activeDetailDiagnostic, inspectorSymbol, workbenchDiagnostics]);

  useEffect(() => {
    let isMounted = true;
    const previousRunId = findPreviousComparableRunId(runDetail, historyItems);
    if (!runDetail || !previousRunId) {
      setPreviousRunDetail(null);
      return () => {
        isMounted = false;
      };
    }
    scannerApi.getRun(previousRunId)
      .then((response) => {
        if (!isMounted) return;
        setPreviousRunDetail(response);
      })
      .catch(() => {
        if (!isMounted) return;
        setPreviousRunDetail(null);
      });
    return () => {
      isMounted = false;
    };
  }, [historyItems, runDetail]);

  const historyCards = useMemo(() => historyItems.map((item) => {
    const fallbackTitle = item.market === 'us'
      ? t('scanner.currentRunFallbackUs')
      : item.market === 'hk'
        ? t('scanner.currentRunFallbackHk')
        : t('scanner.currentRunFallbackCn');
    const matchedSymbols = dedupeTickerSymbols(item.topSymbols);
    const historyHeadline = formatHistoryHeadline(item.headline, item.topSymbols, fallbackTitle);
    return {
      id: item.id,
      marketLabel: item.market === 'us' ? t('scanner.marketUs') : item.market === 'hk' ? t('scanner.marketHk') : t('scanner.marketCn'),
      marketVariant: marketVariant(item.market),
      statusLabel: compactScannerStateLabel(item.status, language),
      statusVariant: statusVariant(item.status),
      watchlistDateLabel: item.watchlistDate ? formatDateOnly(item.watchlistDate, language) : null,
      profileLabel: sanitizeScannerProfileLabel(item.profileLabel || item.profile),
      title: historyHeadline.title,
      detail: historyHeadline.detail,
      shortlistSize: item.shortlistSize,
      universeSize: item.universeSize,
      evaluatedSize: item.evaluatedSize,
      runAtLabel: formatTimestamp(item.runAt, language),
      comparisonLabel: hasComparison(item.changeSummary)
        ? (language === 'en'
          ? `new ${item.changeSummary.newCount} · retained ${item.changeSummary.retainedCount} · dropped ${item.changeSummary.droppedCount}`
          : `新增 ${item.changeSummary.newCount} · 保留 ${item.changeSummary.retainedCount} · 移出 ${item.changeSummary.droppedCount}`)
        : null,
      reviewLabel: hasReviewSummary(item.reviewSummary)
        ? (language === 'en'
          ? `reviewed ${item.reviewSummary.reviewedCount}/${item.reviewSummary.candidateCount}`
          : `复盘 ${item.reviewSummary.reviewedCount}/${item.reviewSummary.candidateCount}`)
        : null,
      matchedSymbols: matchedSymbols.slice(0, 10),
      overflowSymbolCount: Math.max(0, matchedSymbols.length - 10),
    } satisfies ScannerHistoryDrawerItem;
  }), [historyItems, language, t]);
  const emptyStateTitle = language === 'en' ? 'No scan has run yet' : '尚未运行扫描';
  const emptyStateBody = language === 'en'
    ? `Scanner organizes observation candidates from the current scope. Starting setup: ${scannerFirstRunSetupLabel}.`
    : `扫描器会先按当前范围整理候选与观察线索。当前起始范围：${scannerFirstRunSetupLabel}。`;
  const pageErrorSummary = pageError
    ? (isScannerAuthOrAccessError(pageError)
      ? getScannerSafeApiErrorMessage(pageError, language)
      : sanitizeScannerErrorSummary(pageError.message, language) || compactScannerStateLabel('failed', language))
    : null;
  const historyResolution = useMemo<ScannerHistoryResolution>(
    () => ({
      hasLoaded: hasLoadedHistory,
      latestRun: historyItems[0] || null,
    }),
    [hasLoadedHistory, historyItems],
  );
  const workbenchEmptyState = useMemo(
    () => buildScannerWorkbenchEmptyState({
      candidateFilter,
      diagnosticCandidates,
      dataReadinessView: scannerDataReadinessView,
      firstRunSetupLabel: scannerFirstRunSetupLabel,
      historyResolution,
      language,
      pageErrorSummary,
      runDetail,
    }),
    [candidateFilter, diagnosticCandidates, historyResolution, language, pageErrorSummary, runDetail, scannerDataReadinessView, scannerFirstRunSetupLabel],
  );
  const visibleHistorySummaries = useMemo(
    () => [scannerShouldHideEmptyRunCounts ? null : currentRunSummary, recentRunSummary, previousRunSummary]
      .filter((item, index, array): item is ScannerRunSummary => Boolean(item) && array.findIndex((other) => other?.title === item?.title) === index),
    [currentRunSummary, previousRunSummary, recentRunSummary, scannerShouldHideEmptyRunCounts],
  );
  const workbenchCandidatesWithEvidence = useMemo(
    () => workbenchDiagnostics.map((candidate) => withCandidateEvidence(
      shortlistCandidateBySymbol.get(normalizeCandidateSymbol(candidate.symbol)) || diagnosticToCandidate(candidate),
    )),
    [shortlistCandidateBySymbol, workbenchDiagnostics],
  );
  const visualEvidenceSummary = useMemo(
    () => buildScannerVisualEvidenceSummary(workbenchCandidatesWithEvidence, workbenchDiagnostics, runDetail, language),
    [language, runDetail, workbenchCandidatesWithEvidence, workbenchDiagnostics],
  );
  const manualRecoveryParsedSymbol = useMemo(
    () => parseCustomSymbols(manualRecoverySymbol)[0] || '',
    [manualRecoverySymbol],
  );
  const handleAnalyzeCandidate = useCallback(async (candidate: ScannerCandidate) => {
    const symbol = normalizeCandidateSymbol(candidate.symbol);
    if (!symbol) {
      setActionNotice({
        tone: 'warning',
        message: language === 'en' ? 'Candidate symbol is unavailable.' : '候选代码暂不可用。',
      });
      return;
    }
    setActionNotice(null);
    navigate(buildResearchWorkspacePath('stock-structure', language, {
      symbol,
      market: normalizeScannerMarket(runDetail?.market || market),
      source: 'scanner',
    }));
  }, [language, market, navigate, runDetail?.market]);

  const handleAnalyzeManualRecoverySymbol = useCallback(async () => {
    const symbol = manualRecoveryParsedSymbol;
    if (!symbol) {
      setActionNotice({
        tone: 'warning',
        message: language === 'en' ? 'Enter one symbol before starting research.' : '请先输入一个研究代码。',
      });
      return;
    }
    setActionNotice(null);
    navigate(buildResearchWorkspacePath('stock-structure', language, {
      symbol,
      market: normalizeScannerMarket(runDetail?.market || market) || market,
      source: 'scanner',
    }));
  }, [language, manualRecoveryParsedSymbol, market, navigate, runDetail?.market]);

  const handleCopyText = useCallback(async (text: string, nextCopiedKey: string) => {
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error(language === 'en' ? 'Clipboard is not available in this browser.' : '当前浏览器不支持剪贴板。');
      }
      await navigator.clipboard.writeText(text);
      setCopiedKey(nextCopiedKey);
      setActionNotice(null);
    } catch (error) {
      setActionNotice({
        tone: 'danger',
        message: error instanceof Error ? error.message : (language === 'en' ? 'Copy failed.' : '复制失败。'),
      });
    }
  }, [language]);

  const handleExportRows = useCallback((rows: ScannerExportRow[], filename: string) => {
    try {
      downloadScannerCsv(filename, buildScannerCsv(rows));
      setActionNotice(null);
    } catch (error) {
      setActionNotice({
        tone: 'danger',
        message: error instanceof Error ? error.message : (language === 'en' ? 'Export failed.' : '导出失败。'),
      });
    }
  }, [language]);

  const handleTrackCandidate = useCallback(async (candidate: ScannerCandidate) => {
    const candidateMarket = normalizeScannerMarket(runDetail?.market || market);
    if (!candidateMarket) return;
    const candidateIdentity = getWatchlistIdentity(candidateMarket, candidate.symbol);
    if (!candidateIdentity || trackedWatchlistIdentitySet.has(candidateIdentity)) {
      return;
    }

    setPendingWatchlistIdentity(candidateIdentity);
    setActionNotice(null);
    try {
      const savedItem = await watchlistApi.addWatchlistItem({
        symbol: candidate.symbol,
        market: candidateMarket.toLowerCase(),
        name: candidate.companyName || candidate.name,
        source: 'scanner',
        scannerRunId: runDetail?.id,
        scannerRank: candidate.rank,
        scannerScore: candidate.score,
        themeId: runDetail?.themeId || undefined,
        universeType: runDetail?.universeType || undefined,
        notes: buildWatchlistNotes(candidate, runDetail, language) || undefined,
      });
      setWatchlistItems((current) => {
        const nextIdentity = getWatchlistIdentity(savedItem.market, savedItem.symbol);
        const remaining = current.filter((item) => getWatchlistIdentity(item.market, item.symbol) !== nextIdentity);
        return [savedItem, ...remaining];
      });
      setWatchlistAuthBlocked(false);
      setActionNotice({
        tone: 'success',
        message: language === 'en' ? 'Saved to your watchlist.' : '已加入观察名单。',
      });
    } catch (error) {
      const parsedError = getParsedApiError(error);
      if (parsedError.isAuthError || parsedError.status === 401 || parsedError.status === 403 || parsedError.status === 405) {
        setWatchlistAuthBlocked(true);
        setActionNotice({
          tone: 'warning',
          message: language === 'en'
            ? 'Sign in to save candidates to your watchlist.'
            : '请登录后再保存候选到你的观察名单。',
        });
      } else {
        setActionNotice({
          tone: 'danger',
          message: parsedError.message,
        });
      }
    } finally {
      setPendingWatchlistIdentity((current) => (current === candidateIdentity ? null : current));
    }
  }, [language, market, runDetail, trackedWatchlistIdentitySet]);

  const handleBatchTrackCandidates = useCallback(async (batchKey: string, candidates: ScannerCandidate[]) => {
    const candidateMarket = normalizeScannerMarket(runDetail?.market || market);
    if (!candidateMarket || !candidates.length) return;
    const uniqueCandidates = candidates.reduce<ScannerCandidate[]>((items, candidate) => {
      const identity = getWatchlistIdentity(candidateMarket, candidate.symbol);
      if (!identity || items.some((item) => getWatchlistIdentity(candidateMarket, item.symbol) === identity)) return items;
      return [...items, candidate];
    }, []);
    let alreadyExists = 0;
    let added = 0;
    const toAdd = uniqueCandidates.filter((candidate) => {
      const identity = getWatchlistIdentity(candidateMarket, candidate.symbol);
      if (trackedWatchlistIdentitySet.has(identity)) {
        alreadyExists += 1;
        return false;
      }
      return true;
    });
    setPendingBatchWatchlistAction(batchKey);
    setActionNotice(null);
    try {
      const savedItems: WatchlistItem[] = [];
      for (const candidate of toAdd) {
        const savedItem = await watchlistApi.addWatchlistItem({
          symbol: candidate.symbol,
          market: candidateMarket.toLowerCase(),
          name: candidate.companyName || candidate.name,
          source: 'scanner',
          scannerRunId: runDetail?.id,
          scannerRank: candidate.rank,
          scannerScore: candidate.score,
          themeId: runDetail?.themeId || undefined,
          universeType: runDetail?.universeType || undefined,
          notes: buildWatchlistNotes(candidate, runDetail, language) || undefined,
        });
        savedItems.push(savedItem);
        added += 1;
      }
      if (savedItems.length) {
        setWatchlistItems((current) => {
          const savedIdentities = new Set(savedItems.map((item) => getWatchlistIdentity(item.market, item.symbol)));
          return [...savedItems, ...current.filter((item) => !savedIdentities.has(getWatchlistIdentity(item.market, item.symbol)))];
        });
      }
      setWatchlistAuthBlocked(false);
      setActionNotice({
        tone: 'success',
        message: language === 'en'
          ? `Added ${added} · already existed ${alreadyExists}`
          : `已加入 ${added} 个 · 已存在 ${alreadyExists} 个`,
      });
    } catch (error) {
      const parsedError = getParsedApiError(error);
      if (parsedError.isAuthError || parsedError.status === 401 || parsedError.status === 403 || parsedError.status === 405) {
        setWatchlistAuthBlocked(true);
        setActionNotice({
          tone: 'warning',
          message: language === 'en'
            ? 'Sign in to save candidates to your watchlist.'
            : '请登录后再保存候选到你的观察名单。',
        });
      } else {
        setActionNotice({ tone: 'danger', message: parsedError.message });
      }
    } finally {
      setPendingBatchWatchlistAction((current) => (current === batchKey ? null : current));
    }
  }, [language, market, runDetail, trackedWatchlistIdentitySet]);

  const handleTrackManualRecoverySymbol = useCallback(async () => {
    const symbol = manualRecoveryParsedSymbol;
    const candidateMarket = normalizeScannerRunMarket(runDetail?.market || market) || market;
    if (!symbol) {
      setActionNotice({
        tone: 'warning',
        message: language === 'en' ? 'Enter one symbol before adding it to the watchlist.' : '请先输入一个要加入观察名单的代码。',
      });
      return;
    }

    const candidateIdentity = getWatchlistIdentity(candidateMarket, symbol);
    if (!candidateIdentity || trackedWatchlistIdentitySet.has(candidateIdentity)) {
      setActionNotice({
        tone: 'warning',
        message: language === 'en' ? 'This symbol is already in your watchlist.' : '该代码已在观察名单中。',
      });
      return;
    }

    setPendingWatchlistIdentity(candidateIdentity);
    setActionNotice(null);
    try {
      const savedItem = await watchlistApi.addWatchlistItem({
        symbol,
        market: candidateMarket,
        name: symbol,
        source: 'scanner',
        themeId: runDetail?.themeId || undefined,
        universeType: runDetail?.universeType || 'manual_recovery',
        notes: language === 'en'
          ? 'Scanner recovery: manually added after an empty or insufficient scan.'
          : 'Scanner recovery 手动补充：扫描为空或证据不足后加入观察名单。',
      });
      setWatchlistItems((current) => {
        const nextIdentity = getWatchlistIdentity(savedItem.market, savedItem.symbol);
        const remaining = current.filter((item) => getWatchlistIdentity(item.market, item.symbol) !== nextIdentity);
        return [savedItem, ...remaining];
      });
      setWatchlistAuthBlocked(false);
      setActionNotice({
        tone: 'success',
        message: language === 'en' ? `${symbol} added to your watchlist.` : `${symbol} 已加入观察名单。`,
      });
    } catch (error) {
      const parsedError = getParsedApiError(error);
      if (parsedError.isAuthError || parsedError.status === 401 || parsedError.status === 403 || parsedError.status === 405) {
        setWatchlistAuthBlocked(true);
        setActionNotice({
          tone: 'warning',
          message: language === 'en'
            ? 'Sign in to save symbols to your watchlist.'
            : '请登录后再保存代码到你的观察名单。',
        });
      } else {
        setActionNotice({ tone: 'danger', message: parsedError.message });
      }
    } finally {
      setPendingWatchlistIdentity((current) => (current === candidateIdentity ? null : current));
    }
  }, [language, manualRecoveryParsedSymbol, market, runDetail, trackedWatchlistIdentitySet]);

  const getBacktestActionLabel = useCallback((item?: ScannerBacktestItem) => (
    item?.status === 'running' || item?.status === 'queued'
      ? (language === 'en' ? 'Running' : '运行中')
      : (language === 'en' ? 'Backtest' : '回测')
  ), [language]);

  const renderCandidateDetailPanel = useCallback((
    candidate: ScannerCandidate,
    isTracked: boolean,
    isTrackPending: boolean,
    summaryOverride?: string | null,
    backtestItem?: ScannerBacktestItem,
  ) => {
    if (!runDetail) return null;
    const candidateWithEvidence = withCandidateEvidence(candidate);
    const ai = candidate.aiInterpretation;
    const detailQualityNotice = getScannerConsumerQualityNotice(candidate, language);
    const outcomeItems = hasOutcome(candidate.realizedOutcome)
      ? [
        { label: language === 'en' ? 'Outcome' : '结果', value: candidate.realizedOutcome.outcomeLabel },
        { label: language === 'en' ? 'Thesis' : '验证', value: candidate.realizedOutcome.thesisMatch },
        ...(candidate.realizedOutcome.reviewWindowReturnPct != null
          ? [{ label: language === 'en' ? 'Window return' : '窗口收益', value: formatPercent(candidate.realizedOutcome.reviewWindowReturnPct) }]
          : []),
        ...(candidate.realizedOutcome.benchmarkCode
          ? [{ label: language === 'en' ? 'Benchmark' : '基准', value: candidate.realizedOutcome.benchmarkCode }]
          : []),
      ]
      : [];
    const compactNotes = sanitizeScannerNotes([
      candidate.reasonSummary,
      ...(candidate.reasons || []),
      ...(runDetail.scoringNotes || []),
    ], language);
    const compactRiskNotes = sanitizeScannerNotes(candidate.riskNotes || [], language);
    const compactMetricItems = sanitizeScannerLabeledValues(candidate.keyMetrics, language).slice(0, 3);
    const compactAiLines = [ai?.summary, ai?.watchPlan, ai?.riskInterpretation].filter((item): item is string => Boolean(item)).slice(0, 2);

    return (
      <div data-testid={`scanner-result-detail-${getCandidateIdentity(candidate)}`} className="space-y-3">
        <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3">
          <div className="flex min-w-0 items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex min-w-0 items-center gap-2">
                <span className="truncate font-mono text-lg font-semibold text-[color:var(--wolfy-text-primary)]">{candidate.symbol || '--'}</span>
                <span className="rounded border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-console)] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-[color:var(--wolfy-text-secondary)]">
                  {language === 'en' ? 'Focus candidate' : '当前候选'}
                </span>
              </div>
              <p className="mt-1 truncate text-xs text-[color:var(--wolfy-text-muted)]">{candidate.companyName || candidate.name || candidate.symbol || '--'}</p>
              {detailQualityNotice ? (
                <p className="mt-2 max-w-[32rem] text-[11px] leading-relaxed text-[color:var(--wolfy-text-secondary)]">
                  {detailQualityNotice}
                </p>
              ) : null}
            </div>
            <div className="shrink-0 text-right">
              <div className="flex flex-wrap justify-end gap-1.5">
                <FieldChip label={language === 'en' ? 'Score' : '评分'} value={candidate.score != null ? `${candidate.score}/100` : '--'} />
                <FieldChip label={language === 'en' ? 'Rank' : '排名'} value={candidate.rank ? `#${candidate.rank}` : '--'} />
              </div>
            </div>
          </div>
        </div>

        <div
          data-testid={`scanner-candidate-research-stack-${getCandidateIdentity(candidate)}`}
          data-discovery-role="inclusion-reason limitation next-research-handoff"
          className="grid gap-2 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3"
        >
          <div className="grid grid-cols-[56px_minmax(0,1fr)] gap-2 border-b border-[color:var(--wolfy-divider)] pb-2" data-discovery-role="inclusion-reason">
            <span className="text-[10px] uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Why now' : '当前信号'}</span>
            <p className="min-w-0 text-xs leading-relaxed text-[color:var(--wolfy-text-secondary)]">
              {summaryOverride || compactNotes[0] || candidate.reasonSummary || compactMetricItems[0]?.value || ai?.status || (language === 'en' ? 'Inclusion reason not reported' : '入选原因未报告')}
            </p>
          </div>
          <div className="grid grid-cols-[56px_minmax(0,1fr)] gap-2 border-b border-[color:var(--wolfy-divider)] pb-2" data-discovery-role="limitation">
            <span className="text-[10px] uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Limitation' : '限制'}</span>
            <p className="min-w-0 text-xs leading-relaxed text-[color:var(--wolfy-text-secondary)]">
              {detailQualityNotice
                || compactRiskNotes[0]
                || candidate.riskNotes?.[0]
                || (language === 'en' ? 'Limitation not reported' : '限制未报告')}
            </p>
          </div>
          <div className="grid grid-cols-[56px_minmax(0,1fr)] gap-2" data-discovery-role="next-research-handoff">
            <span className="text-[10px] uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Next research' : '下一步研究'}</span>
            <div className="flex min-w-0 flex-wrap gap-1.5">
              {getEntryRange(candidate) ? <FieldChip label={language === 'en' ? 'Observation zone' : '观察区'} value={getEntryRange(candidate) || '--'} /> : null}
              {getTargetPrice(candidate) ? <FieldChip label={language === 'en' ? 'Reference range' : '参考区间'} value={getTargetPrice(candidate) || '--'} /> : null}
              {getStopLoss(candidate) ? <FieldChip label={language === 'en' ? 'Risk boundary' : '风险边界'} value={getStopLoss(candidate) || '--'} /> : null}
              {!getEntryRange(candidate) && !getTargetPrice(candidate) && !getStopLoss(candidate) ? (
                <span className="text-xs text-[color:var(--wolfy-text-muted)]">
                  {language === 'en' ? 'Open stock research or Watchlist for the next check.' : '打开个股研究或观察列表继续下一步检查。'}
                </span>
              ) : null}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {compactMetricItems.slice(0, 2).map((item) => (
            <FieldChip key={`${item.label}-${item.value}`} label={item.label} value={item.value} />
          ))}
          {outcomeItems.slice(0, 2).map((item) => (
            <FieldChip key={`${item.label}-${item.value}`} label={item.label} value={item.value} />
          ))}
        </div>

        {candidateWithEvidence.candidateEvidenceFrame || candidateWithEvidence.candidateResearchReadiness ? (
          <div className="grid gap-2 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">
              {language === 'en' ? 'Evidence coverage' : '证据覆盖'}
            </p>
            <ScannerCandidateEvidenceStrip
              frame={candidateWithEvidence.candidateEvidenceFrame}
              provenanceFrame={candidateWithEvidence.candidateSourceProvenanceFrame}
              readiness={candidateWithEvidence.candidateResearchReadiness}
              language={language}
              variant="detail"
              testId={`scanner-inline-candidate-evidence-${getCandidateIdentity(candidate)}`}
            />
          </div>
        ) : null}

        {candidateWithEvidence.candidateResearchPacket ? (
          <ScannerCandidateResearchPacket
            packet={candidateWithEvidence.candidateResearchPacket}
            language={language}
            variant="detail"
            testId={`scanner-inline-candidate-research-packet-${getCandidateIdentity(candidate)}`}
          />
        ) : candidateWithEvidence.candidateResearchSummaryFrame ? (
          <ScannerCandidateResearchSummary
            frame={candidateWithEvidence.candidateResearchSummaryFrame}
            language={language}
            variant="detail"
            testId={`scanner-inline-candidate-summary-${getCandidateIdentity(candidate)}`}
          />
        ) : null}

        <div className="flex flex-wrap items-center gap-1.5">
          <ActionButton
            label={language === 'en' ? 'Open stock research' : '打开个股研究'}
            icon={<Play className="h-3.5 w-3.5" />}
            onClick={() => void handleAnalyzeCandidate(candidate)}
            variant="compact"
          />
          <ActionButton
            label={getWatchlistActionLabel(isTracked, isTrackPending, watchlistAuthBlocked, language)}
            icon={<BookmarkPlus className="h-3.5 w-3.5" />}
            onClick={() => void handleTrackCandidate(candidate)}
            disabled={isTrackPending || isTracked || watchlistAuthBlocked}
            variant="compact"
            title={getWatchlistActionTitle(isTracked, watchlistAuthBlocked, language)}
          />
          <ActionButton
            label={getBacktestActionLabel(backtestItem)}
            icon={<LineChart className="h-3.5 w-3.5" />}
            onClick={() => void handleBacktestCandidate(candidate)}
            disabled={!candidate.symbol || backtestItem?.status === 'running' || backtestItem?.status === 'queued'}
            title={!normalizeCandidateSymbol(candidate.symbol) ? backtestUnavailableLabel : undefined}
            variant="compact"
          />
          <ActionButton
            label={copiedKey === `candidate:${candidate.symbol}` ? (language === 'en' ? 'Copied' : '已复制') : (language === 'en' ? 'Copy symbol' : '复制代码')}
            icon={<Copy className="h-3.5 w-3.5" />}
            onClick={() => void handleCopyText(candidate.symbol, `candidate:${candidate.symbol}`)}
            variant="compact"
          />
          <ActionButton
            label={language === 'en' ? 'Export' : '导出'}
            icon={<Download className="h-3.5 w-3.5" />}
            onClick={() => handleExportRows(
              [buildScannerExportRow(candidate, runDetail, language)],
              buildScannerExportFilename(runDetail, `candidate-${candidate.symbol}`),
            )}
            variant="compact"
          />
        </div>

        <AdvancedDisclosure
          testId={`scanner-result-detail-more-${getCandidateIdentity(candidate)}`}
          title={language === 'en' ? 'Candidate notes' : '候选说明'}
          summary={language === 'en' ? 'Metrics, signals, realized outcome, supporting context' : '指标、信号、复盘结果与补充说明'}
          icon="more"
        >
          <div className="max-h-[min(34vh,20rem)] overflow-y-auto no-scrollbar ui-scroll-y-quiet">
            <ScannerCandidateDetailPanel
              candidate={candidate}
              candidateIdentity={getCandidateIdentity(candidate)}
              language={language}
              evidenceSummary={getScannerEvidenceSummary(candidate)}
              keyMetricItems={sanitizeScannerLabeledValues(candidate.keyMetrics, language)}
              featureSignalItems={sanitizeScannerLabeledValues(candidate.featureSignals, language)}
              riskNotes={sanitizeScannerNotes(candidate.riskNotes || [], language)}
              entryRange={getEntryRange(candidate)}
              targetPrice={getTargetPrice(candidate)}
              stopLoss={getStopLoss(candidate)}
              selectionNotes={sanitizeScannerNotes([
                candidate.reasonSummary,
                ...(candidate.reasons || []),
                ...(runDetail.scoringNotes || []),
              ], language)}
              aiLines={compactAiLines}
              aiUnavailableText={sanitizeScannerUserText(ai?.status, language, language === 'en' ? 'AI interpretation not available' : 'AI 解读不可用')}
              outcomeItems={outcomeItems}
              providerNotes={null}
              onAnalyze={() => void handleAnalyzeCandidate(candidate)}
              onCopy={() => void handleCopyText(candidate.symbol, `candidate:${candidate.symbol}`)}
              onExport={() => handleExportRows(
                [buildScannerExportRow(candidate, runDetail, language)],
                buildScannerExportFilename(runDetail, `candidate-${candidate.symbol}`),
              )}
              onTrack={() => void handleTrackCandidate(candidate)}
              onBacktest={() => void handleBacktestCandidate(candidate)}
              isAnalyzing={false}
              isCopied={copiedKey === `candidate:${candidate.symbol}`}
              isTracked={isTracked}
              isTrackPending={isTrackPending}
              isWatchlistAuthBlocked={watchlistAuthBlocked}
              watchlistActionLabel={getWatchlistActionLabel(isTracked, isTrackPending, watchlistAuthBlocked, language)}
              watchlistActionTitle={getWatchlistActionTitle(isTracked, watchlistAuthBlocked, language)}
              backtestLabel={getBacktestActionLabel(backtestItem)}
              backtestTitle={!normalizeCandidateSymbol(candidate.symbol) ? backtestUnavailableLabel : undefined}
              backtestItem={backtestItem}
            />
          </div>
        </AdvancedDisclosure>
      </div>
    );
  }, [
    backtestUnavailableLabel,
    copiedKey,
    getBacktestActionLabel,
    handleAnalyzeCandidate,
    handleBacktestCandidate,
    handleCopyText,
    handleExportRows,
    handleTrackCandidate,
    language,
    runDetail,
    watchlistAuthBlocked,
  ]);

  const scannerScopeLabel = runDetail
    ? `${runDetail.market.toUpperCase()} · ${runDetail.universeType === 'theme' ? (language === 'en' ? 'Theme scope' : '主题标的池') : runDetail.universeType === 'custom' || runDetail.universeType === 'symbols' ? (language === 'en' ? 'Custom symbols' : '自定义标的') : (language === 'en' ? 'Default scope' : '默认市场池')}`
    : `${market.toUpperCase()} · ${scanScope === 'theme' ? (language === 'en' ? 'Theme scope' : '主题标的池') : scanScope === 'symbols' ? (language === 'en' ? 'Custom symbols' : '自定义标的') : (language === 'en' ? 'Default scope' : '默认市场池')}`;
  const scannerThemeLabel = runDetail?.themeLabel || runDetail?.themeId || (selectedTheme ? getThemeLabel(selectedTheme, language) : (language === 'en' ? 'No theme' : '无主题'));
  const scannerDataStateLabel = runDetail
    ? (scannerDataReadinessView?.isMeaningful
      ? `${scannerDataReadinessView.stateLabel}${scannerDataReadinessView.blockerLabel ? ` · ${scannerDataReadinessView.blockerLabel}` : ''}`
      : (scannerHasPseudoEmptyRun
        ? (language === 'en' ? 'Waiting for usable data' : '等待可用数据')
        : `${normalizeRunState(runDetail.status) === 'failed' || normalizeRunState(runDetail.status) === 'error' ? `${currentRunSummary?.statusLabel || compactScannerStateLabel(runDetail.status, language)} · ` : ''}${getRunDataStatusLabel(runDetail, language)}`))
    : (scannerDataReadinessView?.isMeaningful
      ? `${scannerDataReadinessView.stateLabel}${scannerDataReadinessView.blockerLabel ? ` · ${scannerDataReadinessView.blockerLabel}` : ''}`
      : (language === 'en' ? 'Waiting' : '等待'));
  const scannerResearchReadinessView = useMemo(
    () => buildConsumerResearchReadinessView(inferScannerResearchReadiness(runDetail), language),
    [language, runDetail],
  );
  const scannerTopDownContextView = useMemo(
    () => buildScannerTopDownContextView(runDetail, language),
    [language, runDetail],
  );
  const scannerConclusion = useMemo(
    () => buildScannerConclusion(runDetail, language, scannerFirstRunSetupLabel, historyResolution, scannerDataReadinessView),
    [historyResolution, language, runDetail, scannerDataReadinessView, scannerFirstRunSetupLabel],
  );
  const scannerRetryRequest = useMemo(
    () => buildScannerRetryRequest(runDetail),
    [runDetail],
  );
  const isRetryScanState = scannerConclusion.state === 'no-candidate' || scannerConclusion.state === 'insufficient';
  const scannerRunButtonLabel = isRunning
    ? t('scanner.running')
    : language === 'en'
      ? (isRetryScanState ? 'Run again' : t('scanner.run'))
      : (isRetryScanState ? '重新扫描' : '启动扫描');
  const heroLatestLabel = `${language === 'en' ? 'Latest' : '最近'} ${generatedAt ? formatTimestamp(generatedAt, language) : '--'}`;
  const showWorkflowNextSteps = !scannerHasPseudoEmptyRun && (!runDetail
    || scannerConclusion.state === 'waiting'
    || scannerConclusion.state === 'no-candidate'
    || scannerConclusion.state === 'insufficient'
    || Boolean(pageErrorSummary));
  const scannerWorkflowDetail = scannerConclusion.state === 'waiting'
    ? (language === 'en'
      ? 'Run current setup. Use manual research path if candidates are not yet available.'
      : '先运行当前配置，无候选时可使用手动研究路径。')
    : scannerConclusion.state === 'insufficient'
      ? (language === 'en'
        ? 'Evidence insufficient for review. Use manual symbol research until coverage improves.'
        : '证据不足，暂不适合复核。先手动研究单个代码。')
      : scannerConclusion.state === 'no-candidate'
        ? (language === 'en'
          ? 'No official candidate formed. Use manual symbol research as next step.'
          : '未形成官方入选候选，可手动研究单个代码。')
        : (language === 'en'
          ? 'Some data is stale, partial, or limited. Keep the official candidate, but use history and Market Overview before treating it as research evidence.'
          : '部分数据可能过期、缺失或受限。可保留官方候选，但先结合历史与 Market Overview 再作为研究证据。');
  const scannerWorkflowStats = runDetail
    ? (scannerShouldHideEmptyRunCounts
      ? (scannerDataReadinessView?.blockerLabel || (language === 'en' ? 'Candidate set not produced' : '候选集未产出'))
      : (language === 'en'
      ? `Official ${currentSelectedCount} · rejected ${runDetail.summary?.rejectedCount ?? 0} · limited ${scannerConclusion.trustSummary.limitedCount}`
      : `官方入选 ${currentSelectedCount} · 淘汰 ${runDetail.summary?.rejectedCount ?? 0} · 数据受限 ${scannerConclusion.trustSummary.limitedCount}`))
    : (language === 'en' ? 'No run loaded yet' : '尚未载入扫描结果');
  const scannerMarketSwitchOptions = [
    { value: 'cn' as const, label: t('scanner.marketCn') },
    { value: 'us' as const, label: t('scanner.marketUs') },
    { value: 'hk' as const, label: t('scanner.marketHk') },
  ].filter((item) => item.value !== market);
  const manualRecoveryMarket = normalizeScannerRunMarket(runDetail?.market || market) || market;
  const manualRecoveryIdentity = getWatchlistIdentity(manualRecoveryMarket, manualRecoveryParsedSymbol);
  const manualRecoveryAlreadyTracked = Boolean(manualRecoveryIdentity && trackedWatchlistIdentitySet.has(manualRecoveryIdentity));
  const isManualRecoveryWatchlistPending = Boolean(manualRecoveryIdentity && pendingWatchlistIdentity === manualRecoveryIdentity);
  const scannerStatusItems = [
    {
      label: language === 'en' ? 'Top ranked row (observation)' : '排序首位（观察）',
      value: activeDetailCandidate
        ? `${activeDetailCandidate.symbol || '--'} · ${activeDetailCandidate.companyName || activeDetailCandidate.name || '--'}`
        : (scannerConclusion.state === 'waiting'
          ? (language === 'en' ? 'Waiting for a scan' : '等待扫描')
          : (language === 'en' ? 'No candidate yet' : '暂无候选')),
    },
    {
      label: language === 'en' ? 'Candidate mix' : '候选分布',
      value: scannerShouldHideEmptyRunCounts
        ? (language === 'en' ? 'No candidate set' : '候选集未产出')
        : `${shortlistCount} / ${runDetail?.summary?.rejectedCount ?? 0} / ${runDetail?.summary?.dataFailedCount ?? 0}`,
    },
    {
      label: language === 'en' ? 'Signal state' : '信号状态',
      value: generatedAt ? `${scannerDataStateLabel} · ${formatTimestamp(generatedAt, language)}` : scannerDataStateLabel,
    },
  ];
  const scannerConsumerStatusSentence = scannerConclusion.state === 'top-candidate'
    ? (language === 'en'
      ? `Current setup can inspect ${currentSelectedCount} scanner candidate${currentSelectedCount === 1 ? '' : 's'}; review data limits before downstream validation.`
      : `当前配置可查看 ${currentSelectedCount} 个扫描候选；进入下游验证前先核对数据限制。`)
    : scannerConclusion.state === 'waiting'
      ? (language === 'en'
        ? 'Choose market, strategy, and scope, then run the scanner when the setup is ready.'
        : '先选择市场、策略与标的池；配置确认后即可运行扫描。')
      : scannerConclusion.state === 'no-candidate'
        ? (language === 'en'
          ? 'This run did not produce selected candidates; adjust scope, retry, or research one symbol manually.'
          : '本次未形成入选候选；可调整范围、重新扫描，或手动研究单个代码。')
        : (language === 'en'
          ? 'Scanner output is limited by data coverage; use the next action before treating results as research evidence.'
          : '扫描输出受数据覆盖限制；先完成下一步动作，再把结果作为研究证据。');
  const scannerConsumerTrustItems = [
    {
      label: language === 'en' ? 'Scope' : '标的池',
      value: scannerDataReadinessView?.coverageChips.find((item) => item.label === (language === 'en' ? 'Scope readiness' : '标的池状态'))?.value
        || scannerScopeLabel,
    },
    {
      label: language === 'en' ? 'History' : '历史数据',
      value: scannerDataReadinessView?.coverageChips.find((item) => item.label === (language === 'en' ? 'History' : '历史'))?.value
        || (language === 'en' ? 'Check after scan' : '运行后确认'),
    },
    {
      label: language === 'en' ? 'Quote freshness' : '报价新鲜度',
      value: scannerDataReadinessView?.coverageChips.find((item) => item.label === (language === 'en' ? 'Quote' : '报价'))?.value
        || scannerDataStateLabel,
    },
    {
      label: language === 'en' ? 'Candidate output' : '候选输出',
      value: scannerShouldHideEmptyRunCounts
        ? (language === 'en' ? 'Not produced' : '未产出')
        : (runDetail
          ? `${currentSelectedCount}/${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize ?? 0}`
          : (language === 'en' ? 'Waiting for run' : '等待运行')),
    },
  ];
  const scannerRailProfileLabel = runDetail
    ? sanitizeScannerProfileLabel(runDetail.profileLabel || runDetail.profile)
    : sanitizeScannerProfileLabel(SCANNER_PROFILE_DEFAULTS[market]?.profile || profile);
  const scannerRailItems = [
    {
      label: language === 'en' ? 'Scope' : '范围',
      value: scannerScopeLabel,
    },
    {
      label: language === 'en' ? 'Profile' : '策略',
      value: scannerRailProfileLabel || '--',
    },
    {
      label: language === 'en' ? 'Theme' : '主题',
      value: scannerThemeLabel,
    },
    {
      label: language === 'en' ? 'Latest' : '最近更新',
      value: generatedAt ? formatTimestamp(generatedAt, language) : '--',
    },
  ];
  const scannerRailCounts = scannerShouldHideEmptyRunCounts
    ? [
      {
        label: language === 'en' ? 'Candidates' : '候选',
        value: language === 'en' ? 'Not produced' : '未产出',
      },
      {
        label: language === 'en' ? 'Rejected' : '淘汰',
        value: '--',
      },
      {
        label: language === 'en' ? 'Limited' : '数据受限',
        value: '--',
      },
    ]
    : [
      {
        label: language === 'en' ? 'Candidates' : '候选',
        value: currentRunSummary?.candidateCount ?? shortlistCount,
      },
      {
        label: language === 'en' ? 'Rejected' : '淘汰',
        value: currentRunSummary?.rejectedCount ?? runDetail?.summary?.rejectedCount ?? 0,
      },
      {
        label: language === 'en' ? 'Limited' : '数据受限',
        value: currentRunSummary?.failedCount ?? ((runDetail?.summary?.dataFailedCount ?? 0) + (runDetail?.summary?.errorCount ?? 0)),
      },
    ];
  const scannerRunFactItems = buildScannerRunFactItems(runDetail, language);
  const scannerHistoryScopeHint = buildScannerHistoryScopeHint(runDetail, market, profile, language);
  const researchWorkflowCandidate = activeDetailCandidate || sortedCandidates[0] || previewHandoffCandidates[0] || currentFilterHandoffCandidates[0] || null;
  const researchWorkflowSymbol = normalizeCandidateSymbol(researchWorkflowCandidate?.symbol) || manualRecoveryParsedSymbol;
  const researchWorkflowMarket = normalizeScannerMarket(runDetail?.market || market);
  const researchWorkflowKnownEvidence = [
    researchWorkflowSymbol
      ? (language === 'en' ? `Candidate in focus: ${researchWorkflowSymbol}` : `当前候选：${researchWorkflowSymbol}`)
      : null,
    runDetail && !scannerHasPseudoEmptyRun
      ? (language === 'en'
        ? `Scanner coverage loaded for ${scannerScopeLabel}`
        : `已载入扫描范围：${scannerScopeLabel}`)
      : null,
    currentSelectedCount > 0
      ? (language === 'en' ? `${currentSelectedCount} official candidates available` : `官方入选 ${currentSelectedCount} 个`)
      : null,
    scannerResearchReadinessView.summaryLine,
  ];
  const researchWorkflowMissingEvidence = [
    researchWorkflowSymbol
      ? (language === 'en' ? 'Watchlist observation record needs review' : '观察列表记录待核对')
      : (language === 'en' ? 'Select or enter a symbol before downstream review' : '先选择或输入一个代码再进入下游核验'),
    researchWorkflowSymbol ? (language === 'en' ? 'Portfolio exposure context needs review' : '组合暴露上下文待核对') : null,
    researchWorkflowSymbol ? (language === 'en' ? 'Backtest validation and options scenario context need review' : '回测验证与期权情景上下文待核验') : null,
  ];
  const researchWorkflowStateNotes = [
    scannerDataStateLabel,
    scannerConclusion.trustSummary.staleCount > 0
      ? (language === 'en' ? 'Latest available scanner context may need freshness review' : '扫描上下文使用最近一次可用数据，需复核时间')
      : null,
    scannerConclusion.trustSummary.partialCount > 0
      ? (language === 'en' ? 'Some candidate evidence is still incomplete' : '部分候选证据仍待补齐')
      : null,
    scannerConclusion.trustSummary.limitedCount > 0
      ? (language === 'en' ? 'Confidence is capped for observation' : '当前置信度受限，仅供观察')
      : null,
  ];
  const researchWorkflowNextSteps = [
    researchWorkflowSymbol
      ? (language === 'en' ? 'Open Watchlist to observe the existing record or empty state' : '打开观察列表，查看该代码的现有记录或空状态')
      : (language === 'en' ? 'Run scanner or use manual symbol research first' : '先运行扫描或使用手动代码研究'),
    researchWorkflowSymbol ? (language === 'en' ? 'Review portfolio exposure' : '查看组合暴露') : null,
    researchWorkflowSymbol ? (language === 'en' ? 'Use Backtest and Options only as read-only context' : '回测与期权仅作为只读上下文核验') : null,
  ];

  return (
    <>
      <div
        ref={surfaceRef}
        data-testid="scanner-ranking-board-page"
        data-product-surface="scanner"
        data-scanner-workspace-state={scannerWorkspaceState}
        data-discovery-sequence="configuration>readiness>run>results>inclusion-reason>limitation>next-research-handoff"
        aria-hidden={shouldGuardA11y && !isSafariReady ? true : undefined}
        aria-live={shouldGuardA11y ? (isSafariReady ? 'polite' : 'off') : undefined}
        className={getSafariReadySurfaceClassName(
          isSafariReady,
          'flex w-full flex-1 flex-col min-w-0 bg-transparent text-foreground',
        )}
      >
          <ConsumerWorkspaceScope data-testid="scanner-wide-workspace-scope" className="flex-1">
	        <ConsumerWorkspacePageShell
	          data-testid="user-scanner-workspace"
	          className="flex-1 gap-3"
	        >
            <div data-testid="scanner-header-strip" className="flex min-w-0 flex-col gap-3">
              <DensePageHeader
                data-testid="scanner-page-heading"
                eyebrow={(
                  <span data-testid="scanner-page-profile-label">
                    {runDetail ? sanitizeScannerProfileLabel(runDetail.profileLabel || runDetail.profile) : (language === 'en' ? 'Candidate workbench' : '候选工作台')}
                  </span>
                )}
                title={language === 'en' ? 'Discovery / Scanner' : '发现 / 扫描器'}
                action={(
                  <TerminalButton
                    ref={openHistoryDrawerButtonRef}
                    type="button"
                    variant="secondary"
                    data-testid="scanner-history-trigger"
                    onClick={handleOpenHistoryDrawerClick}
                    onPointerUp={handleOpenHistoryDrawerPointerUp}
                    className="h-9 px-3 text-xs"
                  >
                    <History className="h-3.5 w-3.5" aria-hidden="true" />
                    <span>{language === 'en' ? 'History' : '历史'}</span>
                  </TerminalButton>
                )}
              />
	            {pageError ? (
	              <div className="mx-3 mt-3 rounded-xl border border-[color:var(--state-danger-border)] bg-[var(--state-danger-bg)] px-3 py-2 text-sm text-[color:var(--state-danger-text)]" role="alert" data-testid="scanner-page-error-summary">
	                <div className="flex flex-wrap items-center gap-2">
	                  <span className="font-medium">{language === 'en' ? 'Scan did not complete' : '扫描未完成'}</span>
	                  <span className="rounded border border-[color:var(--state-danger-border)] bg-[var(--state-danger-bg)] px-1.5 py-0.5 text-[11px]">{pageErrorSummary}</span>
	                </div>
	                <p className="mt-2 text-xs text-[color:var(--state-danger-text)]">
	                  {language === 'en' ? 'Internal error details are hidden on this page.' : '内部错误详情已隐藏。'}
	                </p>
	              </div>
	            ) : null}
              {actionNotice ? (
                <div
                  role={actionNotice.tone === 'danger' ? 'alert' : 'status'}
                  className={`border-y px-3 py-2 text-sm ${
                    actionNotice.tone === 'danger'
                      ? 'border-red-400/20 bg-red-400/10 text-red-100'
                      : actionNotice.tone === 'warning'
                        ? 'border-amber-400/20 bg-amber-400/10 text-amber-100'
                        : 'border-[color:var(--state-success-border)] bg-[var(--state-success-bg)] text-[color:var(--state-success-text)]'
                  }`}
                >
                  {actionNotice.message}
                </div>
              ) : null}
              {scannerRunFeedback ? (
                <div data-testid="scanner-run-feedback" className="mx-3">
                  <SupportBanner
                    tone={scannerRunFeedback.tone}
                    role={scannerRunFeedback.tone === 'danger' ? 'alert' : 'status'}
                    title={scannerRunFeedback.title}
                    body={scannerRunFeedback.body}
                  />
                </div>
              ) : null}

              <section
                data-testid="scanner-consumer-first-viewport"
                data-discovery-role="readiness"
                data-scanner-workspace-state={scannerWorkspaceState}
                className="mx-3 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3 shadow-sm"
                aria-label={language === 'en' ? 'Scanner consumer summary' : '扫描器消费级摘要'}
              >
                <div className="flex min-w-0 flex-col gap-3">
                  <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <p data-testid="scanner-consumer-status-sentence" className="text-sm font-semibold leading-6 text-[color:var(--wolfy-text-primary)]">
                        {scannerConsumerStatusSentence}
                      </p>
                      <p data-testid="scanner-consumer-readiness-summary" className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                        {scannerDataStateLabel}
                        {scannerDataReadinessView?.nextDataLabel ? ` · ${scannerDataReadinessView.nextDataLabel}` : ''}
                      </p>
                    </div>
                    <div data-testid="scanner-consumer-control-summary" className="grid min-w-0 grid-cols-2 gap-1.5 text-xs sm:grid-cols-4 lg:min-w-[34rem]">
                      {[
                        { label: language === 'en' ? 'Market' : '市场', value: market.toUpperCase(), testId: 'scanner-consumer-control-value-market' },
                        { label: language === 'en' ? 'Strategy' : '策略', value: scannerRailProfileLabel || '--', testId: 'scanner-consumer-control-value-strategy' },
                        { label: language === 'en' ? 'Scope' : '标的池', value: scannerScopeLabel, testId: 'scanner-consumer-control-value-scope' },
                        {
                          label: language === 'en' ? 'Output' : '输出',
                          value: scannerShouldHideEmptyRunCounts ? (language === 'en' ? 'Pending' : '待产出') : String(currentSelectedCount),
                          testId: 'scanner-consumer-control-value-output',
                        },
                      ].map((item) => (
                        <div key={item.label} className="min-w-0 rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-rail)] px-2 py-2">
                          <p className="text-[10px] text-[color:var(--wolfy-text-muted)]">{item.label}</p>
                          <p
                            data-testid={item.testId}
                            className="mt-1 break-words whitespace-normal font-mono text-[color:var(--wolfy-text-primary)] md:truncate"
                          >
                            {item.value}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div
                    data-testid="scanner-primary-action"
                    data-discovery-role="explicit-scan-action"
                    className="flex min-w-0 flex-col gap-2 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_8%,var(--wolfy-surface-input))] px-2.5 py-2 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">
                        {language === 'en' ? 'Next research action' : '下一步研究动作'}
                      </p>
                      <p className="mt-0.5 text-xs leading-5 text-[color:var(--wolfy-text-primary)]">
                        {scannerDataReadinessView?.nextDataLabel || scannerWorkflowDetail}
                      </p>
                    </div>
                    <TerminalButton
                      ref={runScannerButtonRef}
                      type="button"
                      onClick={handleRunScannerClick}
                      onPointerUp={handleRunScannerPointerUp}
                      disabled={runDisabled}
                      aria-busy={isRunning}
                      data-testid="scanner-run-button"
                      className={`group h-10 w-full shrink-0 px-3 py-2 text-sm font-bold active:scale-95 disabled:pointer-events-none sm:w-auto sm:min-w-[132px] ${
                        isRetryScanState ? 'shadow-none text-[color:var(--wolfy-text-secondary)]' : ''
                      }`}
                      variant={isRetryScanState ? 'secondary' : 'primary'}
                    >
                      <Play className={`h-4 w-4 ${isRetryScanState ? '' : 'group-hover:animate-pulse'}`} />
                      <span>{scannerRunButtonLabel}</span>
                    </TerminalButton>
                  </div>
                  <div data-testid="scanner-data-trust-row" className="grid min-w-0 gap-1.5 text-xs sm:grid-cols-2 xl:grid-cols-4">
                    {scannerConsumerTrustItems.map((item) => (
                      <div key={item.label} className="min-w-0 rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-rail)] px-2.5 py-2">
                        <p className="text-[10px] text-[color:var(--wolfy-text-muted)]">{item.label}</p>
                        <p
                          data-testid={
                            item.label === (language === 'en' ? 'Scope' : '标的池')
                              ? 'scanner-consumer-trust-value-universe'
                              : undefined
                          }
                          className="mt-1 break-words whitespace-normal text-[color:var(--wolfy-text-primary)] md:truncate"
                        >
                          {item.value}
                        </p>
                      </div>
                    ))}
                  </div>
                  {scannerDataReadinessView?.readinessLayers?.length ? (
                    <div
                      data-testid="scanner-readiness-hierarchy"
                      className="grid min-w-0 gap-1.5 text-xs sm:grid-cols-3"
                      aria-label={language === 'en' ? 'Scanner readiness hierarchy' : '扫描器就绪层级'}
                    >
                      {scannerDataReadinessView.readinessLayers.map((item, index) => (
                        <div
                          key={item.label}
                          data-testid={`scanner-readiness-layer-${index}`}
                          className="min-w-0 rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-panel)] px-2.5 py-2"
                        >
                          <p className="text-[10px] font-semibold text-[color:var(--wolfy-text-muted)]">{item.label}</p>
                          <p className="mt-1 break-words whitespace-normal text-[color:var(--wolfy-text-primary)] md:truncate">{item.value}</p>
                        </div>
                      ))}
                    </div>
                  ) : null}
                  <p data-testid="scanner-consumer-next-action" className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_8%,var(--wolfy-surface-input))] px-2.5 py-2 text-xs leading-5 text-[color:var(--wolfy-text-primary)]">
                    {scannerDataReadinessView?.nextDataLabel || scannerWorkflowDetail}
                  </p>
                </div>
              </section>

              <ScannerConclusionBand
                model={scannerConclusion}
                scopeLabel={scannerScopeLabel}
                dataStateLabel={scannerDataStateLabel}
                latestLabel={heroLatestLabel}
                dataReadinessChips={scannerDataReadinessView?.coverageChips || []}
                nextDataLabel={scannerDataReadinessView?.nextDataLabel || null}
                language={language}
              />
              {scannerOperatorReadinessHref && scannerDataReadinessView?.isMeaningful ? (
                <div className="mx-3 -mt-1 flex justify-end">
                  <a
                    data-testid="scanner-operator-readiness-link"
                    href={scannerOperatorReadinessHref}
                    className="inline-flex min-h-9 items-center rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 text-xs font-semibold text-[color:var(--wolfy-text-secondary)] transition hover:border-[color:var(--wolfy-accent)] hover:text-[color:var(--wolfy-text-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--wolfy-accent)]"
                  >
                    {language === 'en' ? 'View data readiness' : '查看数据就绪'}
                  </a>
                </div>
              ) : null}
              {runDetail ? (
                <ObservationOnlyBoundary language={language} surface="scanner" className="mx-3" />
              ) : null}
              {showWorkflowNextSteps ? (
                <section
                  data-testid="scanner-workflow-next-steps"
                  className="mx-3 overflow-x-hidden rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3 text-sm shadow-sm"
                  aria-label={language === 'en' ? 'Scanner workflow next steps' : '扫描工作流下一步'}
                >
                  <div className="flex min-w-0 flex-col gap-3">
                    <div className="flex min-w-0 flex-col gap-1 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <span className="text-xs font-semibold text-[color:var(--wolfy-text-primary)]">
                            {language === 'en' ? 'Next steps' : '下一步'}
                          </span>
                          <span className="rounded-md border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-rail)] px-2 py-0.5 text-[11px] text-[color:var(--wolfy-text-secondary)]">
                            {scannerWorkflowStats}
                          </span>
                        </div>
                        <p className="mt-1 max-w-4xl text-xs leading-relaxed text-[color:var(--wolfy-text-secondary)]">
                          {scannerWorkflowDetail}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                        {runDetail ? (
                          <TerminalButton
                            type="button"
                            variant="secondary"
                            data-testid="scanner-next-step-retry"
                            disabled={isRunning || !scannerRetryRequest}
                            className="h-9 px-3 text-xs"
                            onClick={() => void handleRetryCurrentRun()}
                          >
                            <Play className="h-3.5 w-3.5" aria-hidden="true" />
                            <span>{language === 'en' ? 'Retry same params' : '重新运行同参数'}</span>
                          </TerminalButton>
                        ) : null}
                        <TerminalButton
                          type="button"
                          variant="secondary"
                          data-testid="scanner-next-step-history"
                          className="h-9 px-3 text-xs"
                          onClick={() => setIsHistoryDrawerOpen(true)}
                        >
                          <History className="h-3.5 w-3.5" aria-hidden="true" />
                          <span>{language === 'en' ? 'Inspect history' : '查看历史'}</span>
                        </TerminalButton>
                      </div>
                    </div>

                    <div className="grid gap-3 xl:grid-cols-[minmax(0,0.9fr)_minmax(260px,0.58fr)_minmax(260px,0.58fr)]">
                      <div
                        data-testid="scanner-primary-research-path"
                        className="min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_8%,var(--wolfy-surface-input))] p-3"
                      >
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <span className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-2 py-0.5 text-[11px] font-semibold text-[color:var(--wolfy-text-primary)]">
                            {language === 'en' ? 'Primary research path' : '首选研究路径'}
                          </span>
                          <span className="text-[11px] text-[color:var(--wolfy-text-muted)]">
                            {language === 'en'
                              ? 'Research one symbol, read-only.'
                              : '只读研究单个代码。'}
                          </span>
                        </div>
                        <label htmlFor="scanner-manual-recovery-symbol" className="mt-3 block text-[11px] font-semibold text-[color:var(--wolfy-text-primary)]">
                          {language === 'en' ? 'Manual research symbol' : '手动补充研究代码'}
                        </label>
                        <p className="mt-1 text-[11px] leading-relaxed text-[color:var(--wolfy-text-secondary)]">
                          {language === 'en'
                            ? 'Research a symbol when candidates are unavailable. Does not add to Watchlist unless saved.'
                            : '候选不可用时手动研究代码，不会自动写入观察名单。'}
                        </p>
                        <div className="mt-2 flex min-w-0 flex-col gap-2 sm:flex-row">
                          <input
                            id="scanner-manual-recovery-symbol"
                            data-testid="scanner-manual-recovery-symbol-input"
                            value={manualRecoverySymbol}
                            className="h-9 min-w-0 flex-1 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-panel)] px-3 text-sm font-mono text-[color:var(--wolfy-text-primary)] outline-none placeholder:text-[color:var(--wolfy-text-muted)] focus:border-[color:var(--wolfy-accent)]"
                            onChange={(event) => setManualRecoverySymbol(event.target.value)}
                            aria-label={language === 'en' ? 'Manual research symbol' : '手动补充研究代码'}
                            placeholder={language === 'en' ? 'TSLA' : 'TSLA'}
                          />
                          <TerminalButton
                            type="button"
                            variant="primary"
                            data-testid="scanner-manual-recovery-research"
                            className="h-9 px-3 text-xs"
                            disabled={!manualRecoveryParsedSymbol}
                            onClick={() => void handleAnalyzeManualRecoverySymbol()}
                          >
                            <Play className="h-3.5 w-3.5" aria-hidden="true" />
                            <span>{manualRecoveryParsedSymbol ? (language === 'en' ? `Open ${manualRecoveryParsedSymbol}` : `打开 ${manualRecoveryParsedSymbol}`) : (language === 'en' ? 'Open research' : '打开研究')}</span>
                          </TerminalButton>
                        </div>
                        <div className="mt-2 flex min-w-0 flex-wrap items-center gap-1.5">
                          <span className="text-[11px] text-[color:var(--wolfy-text-muted)]">
                            {language === 'en'
                              ? 'Optional save path: only keep it in Watchlist if you explicitly want to monitor it.'
                              : '可选保存路径：只有你明确需要继续跟踪时，再加入观察名单。'}
                          </span>
                          <TerminalButton
                            type="button"
                            variant="compact"
                            data-testid="scanner-manual-recovery-watchlist"
                            className="h-8 px-2.5 text-xs"
                            disabled={!manualRecoveryParsedSymbol || manualRecoveryAlreadyTracked || isManualRecoveryWatchlistPending || watchlistAuthBlocked}
                            title={watchlistAuthBlocked
                              ? (language === 'en' ? 'Sign in to save symbols.' : '登录后可保存代码。')
                              : undefined}
                            onClick={() => void handleTrackManualRecoverySymbol()}
                          >
                            <BookmarkPlus className="h-3.5 w-3.5" aria-hidden="true" />
                            <span>
                              {manualRecoveryAlreadyTracked
                                ? (language === 'en' ? 'Already in Watchlist' : '已在观察名单')
                                : manualRecoveryParsedSymbol
                                  ? (language === 'en' ? `Add to Watchlist ${manualRecoveryParsedSymbol}` : `加入观察名单 ${manualRecoveryParsedSymbol}`)
                                  : (language === 'en' ? 'Add to Watchlist' : '加入观察名单')}
                            </span>
                          </TerminalButton>
                        </div>
                      </div>

                      <div className="min-w-0 rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-rail)] p-3">
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <span className="text-[11px] font-semibold text-[color:var(--wolfy-text-primary)]">
                            {language === 'en' ? 'Switch market or setup' : '换市场或配置'}
                          </span>
                          <span className="text-[11px] text-[color:var(--wolfy-text-muted)]">
                            {language === 'en'
                              ? 'Market buttons reset the profile defaults; detailed setup stays in the command bar.'
                              : '市场按钮会切换到对应默认配置；更细的 profile 和范围设置在上方命令栏调整。'}
                          </span>
                        </div>
                        <div className="mt-2 flex min-w-0 flex-wrap items-center gap-1.5">
                          {scannerMarketSwitchOptions.map((option) => (
                            <TerminalButton
                              key={option.value}
                              type="button"
                              variant="compact"
                              data-testid={`scanner-next-step-market-${option.value}`}
                              className="h-8 px-2.5 text-xs"
                              onClick={() => handleMarketChange(option.value)}
                            >
                              <span>{language === 'en' ? `Switch to ${option.label}` : `切到${option.label}`}</span>
                            </TerminalButton>
                          ))}
                          <span data-testid="scanner-secondary-route-copy" className="text-[11px] text-[color:var(--wolfy-text-muted)] sm:ml-auto">
                            {language === 'en' ? 'Research routes:' : '研究入口：'}
                          </span>
                          <a
                            href={buildLocalizedPath('/watchlist', language)}
                            className="inline-flex h-8 items-center rounded-md px-2 text-xs font-medium text-[color:var(--wolfy-text-secondary)] underline decoration-[color:var(--wolfy-divider)] underline-offset-4 hover:text-[color:var(--wolfy-text-primary)]"
                          >
                            {language === 'en' ? 'Open Watchlist view' : '打开观察列表视图'}
                          </a>
                          <a
                            href={buildLocalizedPath('/market-overview', language)}
                            className="inline-flex h-8 items-center rounded-md px-2 text-xs font-medium text-[color:var(--wolfy-text-secondary)] underline decoration-[color:var(--wolfy-divider)] underline-offset-4 hover:text-[color:var(--wolfy-text-primary)]"
                          >
                            {language === 'en' ? 'Open Market Overview' : '打开 Market Overview'}
                          </a>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>
              ) : null}
              <ConsumerResearchReadinessStrip
                readiness={scannerResearchReadinessView}
                title={language === 'en' ? 'Research readiness' : '研究就绪度'}
                testId="scanner-research-readiness-strip"
                className="mx-3 hidden xl:block"
              />
              {scannerTopDownContextView ? (
                <ScannerTopDownContextStrip
                  context={scannerTopDownContextView}
                  title={language === 'en' ? 'Market drivers' : '市场驱动因素'}
                  testId="scanner-top-down-context-strip"
                  className="mx-3"
                />
              ) : null}
              <div data-testid="scanner-status-strip-scroll-frame" className="relative">
                <DenseStatusStrip
                  data-testid="scanner-status-strip"
                  ariaLabel={language === 'en' ? 'Scanner summary strip' : '扫描摘要条'}
                  items={scannerStatusItems}
                  className="ui-scroll-x-quiet flex-nowrap overflow-x-auto border-y border-[color:var(--wolfy-border-subtle)] bg-transparent px-2 py-1"
                />
                <span aria-hidden="true" className="pointer-events-none absolute inset-y-1 right-0 w-8 bg-gradient-to-l from-[var(--wolfy-surface-console)] to-transparent sm:hidden" />
              </div>
            </div>

		          <div data-testid="scanner-workspace-grid" className="grid w-full flex-1 min-w-0 gap-3 lg:grid-cols-[minmax(0,1fr)_clamp(16rem,18vw,18.5rem)]">
                <DenseTableShell
                  data-testid="scanner-launch-bar"
                  variant="board"
                  className="flex min-h-[520px] flex-1 flex-col gap-3 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-2 shadow-sm"
                >
                  <section
                    data-testid="scanner-command-panel"
                    data-layout-zone="CommandBar"
                    data-discovery-role="configuration run-action"
                    className="min-w-0 overflow-hidden rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]"
                  >
                  <DenseCommandBar
                    data-testid="scanner-command-bar"
                    className="border-0 bg-transparent px-3 py-3"
                  >
                    <div className="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-[minmax(112px,0.55fr)_minmax(150px,0.72fr)_minmax(106px,0.45fr)_minmax(156px,0.72fr)_minmax(118px,0.5fr)_minmax(118px,0.5fr)] xl:items-end [&_[data-testid='scanner-market-toggle']_button]:h-12 [&_[data-testid='scanner-market-toggle']_button]:px-3 [&_[data-testid='scanner-market-toggle']_button]:py-2 [&_[data-testid='scanner-scope-selector']_button]:h-12 [&_[data-testid='scanner-scope-selector']_button]:px-3 [&_[data-testid='scanner-scope-selector']_button]:py-2 md:[&_[data-testid='scanner-market-toggle']_button]:h-8 md:[&_[data-testid='scanner-market-toggle']_button]:py-1 md:[&_[data-testid='scanner-scope-selector']_button]:h-8 md:[&_[data-testid='scanner-scope-selector']_button]:py-1">
                      <PillTagGroup compact label={t('scanner.marketLabel')} value={market} onChange={(next) => handleMarketChange(next as 'cn' | 'us' | 'hk')} options={[{ value: 'cn', label: t('scanner.marketCn') }, { value: 'us', label: t('scanner.marketUs') }, { value: 'hk', label: t('scanner.marketHk') }]} variant="market" testId="scanner-market-toggle" />
                      <PillTagGroup compact label={t('scanner.profileLabel')} value={profile} onChange={setProfile} options={profileOptions} />
                      <PillTagGroup compact label={t('scanner.shortlistLabel')} value={shortlistSize} onChange={setShortlistSize} options={[{ value: '5', label: language === 'en' ? 'Top 5' : '前 5' }, { value: '8', label: language === 'en' ? 'Top 8' : '前 8' }, { value: '10', label: language === 'en' ? 'Top 10' : '前 10' }]} />
                      <div data-testid="scanner-launch-controls" className="contents">
                        <PillTagGroup
                          compact
                          label={language === 'en' ? 'Scope' : '标的池'}
                          value={scanScope}
                          onChange={(next) => setScanScope(next as ScanScope)}
                          options={[
                            { value: 'default', label: language === 'en' ? 'Default market scope' : '默认市场池' },
                            { value: 'theme', label: language === 'en' ? 'Theme scope' : '主题标的池' },
                            { value: 'symbols', label: language === 'en' ? 'Custom symbols' : '自定义标的' },
                          ]}
                          testId="scanner-scope-selector"
                        />
                        <PillTagGroup compact label={t('scanner.universeLabel')} value={universeLimit} onChange={setUniverseLimit} options={universeOptions} />
                        <PillTagGroup compact label={t('scanner.detailLabel')} value={detailLimit} onChange={setDetailLimit} options={detailOptions} />
                      </div>
                    </div>
                    {scanScope !== 'default' ? (
                      <AdvancedDisclosure
                        testId="scanner-advanced-controls"
                        title={language === 'en' ? 'Advanced controls' : '高级参数'}
                        summary={language === 'en' ? 'Theme or custom-symbol inputs only' : '仅主题或自定义标的输入'}
                        icon="more"
                      >
                        {scanScope === 'theme' ? (
                          <div className="flex min-w-0 flex-col gap-2" data-testid="scanner-theme-control">
                            <span className="text-[10px] uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Theme' : '主题'}</span>
                            <div className="select-field__control ui-control-shell group relative min-w-0 w-full max-w-full">
                              <select
                                data-testid="scanner-theme-select"
                                value={themeId}
                                className="select-surface absolute inset-0 z-10 h-full w-full min-w-0 cursor-pointer appearance-none truncate rounded-lg pr-10 opacity-0 outline-none"
                                onChange={(event) => setThemeId(event.target.value)}
                                aria-invalid={Boolean(validationErrors.theme)}
                                aria-describedby={validationErrors.theme ? 'scanner-theme-error' : undefined}
                              >
                                <option value="">{language === 'en' ? 'Select a theme' : '选择主题'}</option>
                                {configuredMarketThemes.length ? (
                                  <optgroup label={language === 'en' ? 'Ready seed lists' : '可用 seed 主题'}>
                                    {configuredMarketThemes.map((theme) => (
                                      <option key={theme.id} value={theme.id}>
                                        {getThemeLabel(theme, language)} · {theme.symbols.length}
                                      </option>
                                    ))}
                                  </optgroup>
                                ) : null}
                                {unconfiguredMarketThemes.length ? (
                                  <optgroup label={language === 'en' ? 'Unavailable / unconfigured' : '未配置'}>
                                    {unconfiguredMarketThemes.map((theme) => (
                                      <option key={theme.id} value={theme.id} disabled>
                                        {getThemeLabel(theme, language)} · {language === 'en' ? 'not configured' : '未配置'}
                                      </option>
                                    ))}
                                  </optgroup>
                                ) : null}
                              </select>
                              <div
                                aria-hidden="true"
                                className={`select-field__overlay pointer-events-none flex h-12 w-full min-w-0 items-center rounded-lg border bg-[var(--wolfy-surface-input)] px-3 py-2 text-sm text-[color:var(--wolfy-text-primary)] transition-all md:h-9 md:px-2.5 md:py-1.5 md:text-xs ${
                                  validationErrors.theme
                                    ? 'border-[color:var(--state-danger-border)] text-[color:var(--state-danger-text)]'
                                    : 'border-[color:var(--wolfy-divider)] group-focus-within:border-[color:var(--wolfy-accent)]'
                                }`}
                              >
                                <span className="select-field__value min-w-0 flex-1 truncate">
                                  {selectedTheme
                                    ? `${getThemeLabel(selectedTheme, language)} · ${selectedTheme.symbols.length}`
                                    : (language === 'en' ? 'Select a theme' : '选择主题')}
                                </span>
                                <ChevronDown className="select-field__icon ui-control-icon ml-2 h-4 w-4 shrink-0 text-[color:var(--wolfy-text-muted)]" aria-hidden="true" />
                              </div>
                            </div>
                            {selectedTheme && !selectedTheme.symbols.length ? (
                              <p className="text-[11px] leading-relaxed text-amber-100/72">
                                {language === 'en' ? 'This theme is not configured yet.' : '该主题尚未配置成分股。'}
                              </p>
                            ) : null}
                            {validationErrors.theme ? (
                              <p id="scanner-theme-error" role="alert" className="text-[11px] leading-relaxed text-[color:var(--state-danger-text)]">
                                {validationErrors.theme}
                              </p>
                            ) : null}
                            <div className="mt-2 flex flex-col gap-2 border-t border-[color:var(--wolfy-divider)] pt-2" data-testid="scanner-ai-theme-builder">
                              <div className="flex items-center gap-2 text-[11px] font-medium text-[color:var(--wolfy-text-secondary)]">
                                <Sparkles className="h-3.5 w-3.5 text-[color:var(--wolfy-accent)]" aria-hidden="true" />
                                <span>{language === 'en' ? 'AI custom theme' : 'AI 自定义主题'}</span>
                              </div>
                              <input
                                data-testid="scanner-ai-theme-label-input"
                                value={customThemeLabel}
                                className="w-full appearance-none rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-sm text-[color:var(--wolfy-text-primary)] outline-none placeholder:text-[color:var(--wolfy-text-muted)] focus:border-[color:var(--wolfy-accent)] md:px-2.5 md:py-1.5 md:text-xs"
                                onChange={(event) => setCustomThemeLabel(event.target.value)}
                                aria-label={language === 'en' ? 'AI theme name' : 'AI 主题名称'}
                                aria-invalid={Boolean(validationErrors.customThemeLabel)}
                                aria-describedby={validationErrors.customThemeLabel ? 'scanner-ai-theme-label-error' : undefined}
                                maxLength={80}
                                placeholder={language === 'en' ? 'White House Stocks' : 'White House Stocks'}
                              />
                              {validationErrors.customThemeLabel ? (
                                <p id="scanner-ai-theme-label-error" role="alert" className="text-[11px] leading-relaxed text-[color:var(--state-danger-text)]">
                                  {validationErrors.customThemeLabel}
                                </p>
                              ) : null}
                              <textarea
                                data-testid="scanner-ai-theme-prompt-input"
                                value={customThemePrompt}
                                onChange={(event) => setCustomThemePrompt(event.target.value)}
                                aria-label={language === 'en' ? 'AI theme criteria' : 'AI 主题筛选条件'}
                                aria-invalid={Boolean(validationErrors.customThemePrompt)}
                                aria-describedby={validationErrors.customThemePrompt ? 'scanner-ai-theme-prompt-error' : undefined}
                                maxLength={600}
                                rows={3}
                                placeholder={language === 'en' ? 'Stocks associated with White House policy, federal contracts, and government decisions.' : '例如：与白宫政策、联邦合同和政府决策相关的股票。'}
                                className="w-full resize-none rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-sm text-[color:var(--wolfy-text-primary)] outline-none placeholder:text-[color:var(--wolfy-text-muted)] focus:border-[color:var(--wolfy-accent)] md:px-2.5 md:py-1.5 md:text-xs"
                              />
                              {validationErrors.customThemePrompt ? (
                                <p id="scanner-ai-theme-prompt-error" role="alert" className="text-[11px] leading-relaxed text-[color:var(--state-danger-text)]">
                                  {validationErrors.customThemePrompt}
                                </p>
                              ) : null}
                              <input
                                data-testid="scanner-ai-theme-manual-symbols-input"
                                value={customThemeManualSymbols}
                                className="w-full appearance-none rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-sm text-[color:var(--wolfy-text-primary)] outline-none placeholder:text-[color:var(--wolfy-text-muted)] focus:border-[color:var(--wolfy-accent)] md:px-2.5 md:py-1.5 md:text-xs"
                                onChange={(event) => setCustomThemeManualSymbols(event.target.value)}
                                aria-label={language === 'en' ? 'Manual symbol additions' : '手动补充股票代码'}
                                aria-invalid={Boolean(validationErrors.customThemeManualSymbols)}
                                aria-describedby={validationErrors.customThemeManualSymbols ? 'scanner-ai-theme-manual-symbols-error' : undefined}
                                placeholder={language === 'en' ? 'Optional: add symbols, e.g. NVDA PLTR' : '可选：手动补充代码，例如 NVDA PLTR'}
                              />
                              {validationErrors.customThemeManualSymbols ? (
                                <p id="scanner-ai-theme-manual-symbols-error" role="alert" className="text-[11px] leading-relaxed text-[color:var(--state-danger-text)]">
                                  {validationErrors.customThemeManualSymbols}
                                </p>
                              ) : null}
                              <TerminalButton
                                ref={generateThemeButtonRef}
                                type="button"
                                variant="secondary"
                                disabled={generateThemeDisabled}
                                onPointerUp={handleGenerateThemePointerUp}
                                onClick={handleGenerateThemeClick}
                                className="h-12 px-3 py-2 text-sm md:h-8 md:py-1 md:text-xs"
                              >
                                <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                                <span>{isGeneratingTheme ? (language === 'en' ? 'Generating...' : '生成中...') : (language === 'en' ? 'Generate theme' : '生成主题')}</span>
                              </TerminalButton>
                              {themeSuggestions.length ? (
                                <div className="flex flex-col gap-1.5" data-testid="scanner-ai-theme-suggestions">
                                  {themeSuggestions.slice(0, 6).map((suggestion) => (
                                    <div key={suggestion.symbol} className="shrink-0 border-t border-[color:var(--wolfy-divider)] px-0 py-1.5">
                                      <div className="flex items-center justify-between gap-2 text-[11px] text-[color:var(--wolfy-text-secondary)]">
                                        <span className="font-semibold text-[color:var(--wolfy-text-primary)]">{suggestion.symbol}</span>
                                        <span>{Math.round(suggestion.confidence * 100)}%</span>
                                      </div>
                                      <p className="mt-1 text-[10px] leading-snug text-[color:var(--wolfy-text-muted)]">{suggestion.reason}</p>
                                    </div>
                                  ))}
                                </div>
                              ) : null}
                            </div>
                          </div>
                        ) : null}
                        {scanScope === 'symbols' ? (
                          <div className="flex flex-col gap-1.5" data-testid="scanner-custom-symbols-control">
                            <span className="text-[10px] uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Symbols' : '代码'}</span>
                            <textarea
                              data-testid="scanner-custom-symbols-input"
                              value={customSymbols}
                              onChange={(event) => setCustomSymbols(event.target.value)}
                              aria-label={language === 'en' ? 'Custom scanner symbols' : '自定义扫描标的'}
                              aria-invalid={Boolean(validationErrors.customSymbols)}
                              aria-describedby={validationErrors.customSymbols ? 'scanner-custom-symbols-error' : undefined}
                              rows={3}
                              placeholder={language === 'en' ? 'MARA RIOT CLSK' : 'MARA RIOT CLSK'}
                              className="w-full resize-none rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-sm text-[color:var(--wolfy-text-primary)] outline-none placeholder:text-[color:var(--wolfy-text-muted)] focus:border-[color:var(--wolfy-accent)] md:px-2.5 md:py-1.5 md:text-xs"
                            />
                            <p className="text-[11px] text-[color:var(--wolfy-text-muted)]">
                              {language === 'en' ? `Parsed ${parsedCustomSymbols.length}` : `已解析 ${parsedCustomSymbols.length}`}
                            </p>
                            {validationErrors.customSymbols ? (
                              <p id="scanner-custom-symbols-error" role="alert" className="text-[11px] leading-relaxed text-[color:var(--state-danger-text)]">
                                {validationErrors.customSymbols}
                              </p>
                            ) : null}
                          </div>
                        ) : null}
                      </AdvancedDisclosure>
                    ) : null}
                    {validationErrors.run ? (
                      <p role="alert" className="text-[11px] leading-relaxed text-[color:var(--state-danger-text)]">
                        {validationErrors.run}
                      </p>
                    ) : null}
                  </DenseCommandBar>
                  </section>

                  <section
                    data-testid="scanner-results-panel"
                    data-layout-zone="PrimaryWorkRegion"
                    data-discovery-role="result-workspace"
                    data-scanner-workspace-state={scannerWorkspaceState}
                    className="flex min-h-0 flex-1 min-w-0 flex-col overflow-hidden rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)]"
                  >
                  <div data-testid="scanner-ranked-workbench" className="flex min-h-0 flex-1 min-w-0 flex-col">
                    <div data-testid="scanner-primary-actions" className="flex shrink-0 flex-row flex-wrap items-center justify-between gap-3 px-2 py-2">
                      <div className="flex min-w-0 flex-row flex-wrap items-center gap-2">
                        {runDetail && hasCandidateDiagnostics ? (
                          <div data-testid="scanner-compact-filter-bar" className="min-w-0">
                            <div data-testid="scanner-candidate-filters" className="ui-scroll-x-quiet flex min-w-0 max-w-full gap-1.5 border-r border-[color:var(--wolfy-divider)] pr-2 [&_button]:h-9 [&_button]:px-2.5 [&_button]:py-1.5 md:[&_button]:h-7 md:[&_button]:py-0.5" role="group" aria-label={language === 'en' ? 'Candidate view' : '候选视图'}>
                              {([
                                ['selected', language === 'en' ? 'Selected' : '入选'],
                                ['pool', language === 'en' ? 'Candidate pool' : '候选池'],
                                ['rejected', language === 'en' ? 'Rejected' : '淘汰'],
                                ['data_failed', language === 'en' ? 'Limited data' : '数据受限'],
                                ['all', language === 'en' ? 'All' : '全部'],
                              ] as const).map(([key, label]) => (
                                <button
                                  key={key}
                                  type="button"
                                  className={`inline-flex shrink-0 items-center rounded-md border px-2 py-0.5 text-xs ${
                                    candidateFilter === key
                                      ? 'border-[color:var(--wolfy-accent)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_12%,transparent)] text-[color:var(--wolfy-text-primary)]'
                                      : 'border-transparent text-[color:var(--wolfy-text-muted)] hover:bg-[var(--wolfy-surface-input)] hover:text-[color:var(--wolfy-text-secondary)]'
                                  }`}
                                  onClick={() => setCandidateFilter(key)}
                                >
                                  <span className="ui-truncate block">{label}</span>
                                </button>
                              ))}
                            </div>
                          </div>
                        ) : null}
                        <div data-testid="scanner-ranked-sortbar" className="flex flex-wrap items-center gap-1.5 text-xs text-[color:var(--wolfy-text-muted)] [&_button]:h-9 [&_button]:px-2.5 [&_button]:py-1.5 md:[&_button]:h-7 md:[&_button]:py-0.5">
                          <span>{language === 'en' ? 'Sort by' : '排序'}</span>
                          {([
                            ['score', language === 'en' ? 'scanner score' : '扫描评分'],
                            ['symbol', language === 'en' ? 'symbol' : '代码'],
                            ['target', language === 'en' ? 'reference range' : '参考区间'],
                            ['risk', language === 'en' ? 'risk' : '风险'],
                          ] as const).map(([key, label]) => (
                            <button
                              key={key}
                              type="button"
                              className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 ${sortKey === key ? 'border-[color:var(--wolfy-accent)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_12%,transparent)] text-[color:var(--wolfy-text-primary)]' : 'border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-muted)] hover:text-[color:var(--wolfy-text-secondary)]'}`}
                              onClick={() => handleSortChange(key)}
                            >
                              {label}
                              {sortKey === key ? <ArrowDownUp className="h-3 w-3" /> : null}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="flex min-w-0 flex-row flex-wrap items-center justify-end gap-2">
                        {runDetail ? (
                          <div data-testid="scanner-summary-counters" className="flex flex-wrap items-center gap-1.5 text-[11px] text-[color:var(--wolfy-text-muted)]">
                            {scannerHasPseudoEmptyRun ? (
                              <span className="inline-flex items-baseline gap-1 rounded-md border border-amber-300/15 bg-amber-300/[0.045] px-2 py-0.5">
                                <span className="text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Candidate set' : '候选集'}</span>
                                <span className="font-mono text-amber-100/88">{language === 'en' ? 'Not produced' : '未产出'}</span>
                              </span>
                            ) : ([
                              [language === 'en' ? 'Evaluated' : '已评估', runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize],
                              [language === 'en' ? 'Selected' : '入选', runDetail.summary?.selectedCount ?? shortlistCount],
                              [language === 'en' ? 'Rejected' : '淘汰', runDetail.summary?.rejectedCount ?? 0],
                              [language === 'en' ? 'Limited data' : '数据受限', runDetail.summary?.dataFailedCount ?? 0],
                            ].map(([label, value]) => (
                              <span key={String(label)} className="inline-flex items-baseline gap-1 rounded-md border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-2 py-0.5">
                                <span className="text-[color:var(--wolfy-text-muted)]">{label}</span>
                                <span className="font-mono text-[color:var(--wolfy-text-primary)]">{value}</span>
                              </span>
                            )))}
                          </div>
                        ) : null}
                        <div data-testid="scanner-more-actions" className="relative min-w-0">
                          <TerminalButton
                            type="button"
                            variant="compact"
                            aria-expanded={isMoreActionsOpen}
                            aria-label={language === 'en' ? 'More scanner actions' : '更多扫描操作'}
                            className="h-12 px-3 py-2 text-sm md:h-8 md:px-2.5 md:py-1 md:text-xs"
                            onClick={() => setIsMoreActionsOpen((current) => !current)}
                          >
                            <MoreHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
                            <span>{language === 'en' ? 'More' : '更多'}</span>
                          </TerminalButton>
                          {isMoreActionsOpen ? (
                            <div data-testid="scanner-more-actions-panel" className="absolute right-0 z-20 mt-2 grid min-w-[220px] gap-1.5 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] p-2 shadow-[var(--wolfy-shadow-panel)]">
                              <ActionButton
                                label={language === 'en' ? 'Export CSV' : '导出 CSV'}
                                icon={<Download className="h-3.5 w-3.5" />}
                                onClick={() => runDetail && handleExportRows(
                                  sortedCandidates.map((candidate) => buildScannerExportRow(candidate, runDetail, language)),
                                  buildScannerExportFilename(runDetail),
                                )}
                                disabled={!runDetail || !sortedCandidates.length}
                              />
                              <ActionButton
                                label={language === 'en' ? 'Copy all symbols' : '复制全部代码'}
                                icon={<Copy className="h-3.5 w-3.5" />}
                                onClick={() => void handleCopyText(sortedCandidates.map((candidate) => candidate.symbol).join(', '), 'all-symbols')}
                                disabled={!sortedCandidates.length}
                              />
                              <ActionButton
                                label={language === 'en' ? 'Copy top 5' : '复制前 5'}
                                icon={<Copy className="h-3.5 w-3.5" />}
                                onClick={() => void handleCopyText(sortedCandidates.slice(0, 5).map((candidate) => candidate.symbol).join(', '), 'top-5-symbols')}
                                disabled={!sortedCandidates.length}
                              />
                              <ActionButton
                                label={language === 'en' ? 'Add official selected' : '加入全部入选'}
                                icon={<BookmarkPlus className="h-3.5 w-3.5" />}
                                onClick={() => void handleBatchTrackCandidates('official', sortedCandidates)}
                                disabled={Boolean(pendingBatchWatchlistAction) || watchlistAuthBlocked || !sortedCandidates.length}
                              />
                              <ActionButton
                                label={language === 'en' ? 'Add preview selected' : '加入预览入选'}
                                icon={<BookmarkPlus className="h-3.5 w-3.5" />}
                                onClick={() => void handleBatchTrackCandidates('preview', previewHandoffCandidates)}
                                disabled={Boolean(pendingBatchWatchlistAction) || watchlistAuthBlocked || !previewHandoffCandidates.length}
                              />
                              <ActionButton
                                label={language === 'en' ? 'Add filtered' : '加入当前筛选'}
                                icon={<BookmarkPlus className="h-3.5 w-3.5" />}
                                onClick={() => void handleBatchTrackCandidates('filtered', currentFilterHandoffCandidates)}
                                disabled={Boolean(pendingBatchWatchlistAction) || watchlistAuthBlocked || !currentFilterHandoffCandidates.length}
                              />
                              <ActionButton
                                label={language === 'en' ? 'Batch backtest' : '批量回测'}
                                icon={<LineChart className="h-3.5 w-3.5" />}
                                onClick={() => handleBacktestBatch('official_selected')}
                                disabled={isBacktestBatchRunning || backtestCounts.official_selected === 0}
                              />
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </div>

                    <div
                      data-testid="scanner-workbench-detail-layout"
                      className={`grid min-h-0 flex-1 min-w-0 gap-3 px-2 py-2 ${showDetailRail ? 'xl:grid-cols-[minmax(820px,1fr)_minmax(320px,340px)]' : 'grid-cols-1'}`}
                    >
                      <div data-testid="scanner-primary-work-region" className="min-w-0">
                        {!scannerHasPseudoEmptyRun && currentSelectedCount === 0 && candidateFilter === 'selected' && visibleHistorySummaries.length ? (
                          <ScannerHistoryFallbackPanel
                            summaries={visibleHistorySummaries}
                            emptyState={workbenchEmptyState}
                            language={language}
                          />
                        ) : workbenchDiagnostics.length ? (
                          <>
                            <div
                              data-testid="scanner-ranked-list"
                              className="overflow-x-auto overscroll-x-contain rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] [-webkit-overflow-scrolling:touch]"
                              aria-label={language === 'en' ? 'Ranked scanner results' : '扫描排名结果'}
                              role="table"
                              aria-colcount={8}
                              aria-rowcount={workbenchDiagnostics.length + 1}
                              tabIndex={0}
                            >
                              <div data-testid="scanner-result-table" className="contents md:block md:min-w-[1220px]">
                                <div role="row" aria-rowindex={1} className="hidden items-center gap-3 border-b border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-[10px] font-bold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)] md:grid md:grid-cols-[64px_minmax(180px,1fr)_minmax(120px,auto)_92px_110px_minmax(220px,1.3fr)_minmax(150px,0.9fr)_minmax(190px,1fr)]">
                                  <span role="columnheader" aria-colindex={1}>{language === 'en' ? 'Rank' : '排名'}</span>
                                  <span role="columnheader" aria-colindex={2}>{language === 'en' ? 'Symbol / name' : '代码 / 名称'}</span>
                                  <span role="columnheader" aria-colindex={3} className="text-right">{language === 'en' ? 'Actions' : '操作'}</span>
                                  <span role="columnheader" aria-colindex={4}>{language === 'en' ? 'Score' : '评分'}</span>
                                  <span role="columnheader" aria-colindex={5}>{language === 'en' ? 'Status' : '状态'}</span>
                                  <span role="columnheader" aria-colindex={6}>{language === 'en' ? 'Why now' : '当前信号'}</span>
                                  <span role="columnheader" aria-colindex={7}>{language === 'en' ? 'Data quality' : '数据质量'}</span>
                                  <span role="columnheader" aria-colindex={8}>{language === 'en' ? 'Next / risk' : '下一步 / 风险'}</span>
                                </div>
                                <div data-testid="scanner-candidate-scroll-region" role="rowgroup" className="min-w-0 max-h-[min(52vh,34rem)] overflow-y-auto overscroll-y-contain no-scrollbar ui-scroll-y-quiet [-webkit-overflow-scrolling:touch]">
                                  {workbenchDiagnostics.map((candidate, index) => {
                                    const activeRunDetail = runDetail;
                                    if (!activeRunDetail) return null;
                                    const sourceCandidate = shortlistCandidateBySymbol.get(normalizeCandidateSymbol(candidate.symbol)) || diagnosticToCandidate(candidate);
                                    const sourceCandidateWithEvidence = withCandidateEvidence(sourceCandidate);
                                    const candidateMarket = normalizeScannerMarket(activeRunDetail.market || market);
                                    const candidateIdentity = getWatchlistIdentity(candidateMarket, candidate.symbol);
                                    const isTracked = Boolean(candidateIdentity && trackedWatchlistIdentitySet.has(candidateIdentity));
                                    const isTrackPending = pendingWatchlistIdentity === candidateIdentity;
                                    const backtestItem = getBacktestItem(sourceCandidate.symbol);
                                    const comparison = comparisonState.bySymbol.get(normalizeCandidateSymbol(candidate.symbol) || '');
                                    return (
                                      <ScannerCandidateDiagnosticRow
                                        key={`ranked-${candidate.symbol}`}
                                        candidate={candidate}
                                        language={language}
                                        rowIndex={index + 2}
                                        isSelectedCandidate={normalizeCandidateSymbol(activeDetailDiagnostic?.symbol) === normalizeCandidateSymbol(candidate.symbol)}
                                        isExpanded={false}
                                        isMoreOpen={rowMoreSymbol === candidate.symbol}
                                        displayName={sourceCandidate.companyName || sourceCandidate.name || candidate.name || candidate.symbol || '--'}
                                        keyReason={isOfficialSelected(candidate) ? getKeyReason(sourceCandidate, runDetail, language) : formatFriendlyDiagnosticReason(candidate, language)}
                                        previewLabel={previewDecisionLabel(candidate, previewThreshold, language)}
                                        previewBadgeClassName={previewDecisionClass(candidate, previewThreshold)}
                                        dataQualityLabel={formatCandidateDataQuality(candidate, language)}
                                        watchSummary={formatWorkbenchWatchSummary(sourceCandidate, language)}
                                        rangeSummary={formatWorkbenchRangeSummary(sourceCandidate, language)}
                                        evidenceSummary={null}
                                        candidateEvidenceFrame={sourceCandidateWithEvidence.candidateEvidenceFrame}
                                        candidateResearchReadiness={sourceCandidateWithEvidence.candidateResearchReadiness}
                                        candidateResearchSummaryFrame={sourceCandidateWithEvidence.candidateResearchSummaryFrame}
                                        candidateResearchPacket={sourceCandidateWithEvidence.candidateResearchPacket}
                                        candidateSourceProvenanceFrame={sourceCandidateWithEvidence.candidateSourceProvenanceFrame}
                                        scoreLabel={candidate.score == null ? '--' : `${candidate.score}/100`}
                                        trustSources={[stripScannerConsumerTrustSource(sourceCandidate), stripScannerConsumerTrustSource(candidate)]}
                                        scoreDelta={formatScoreDelta(comparison?.scoreDelta ?? null)}
                                        comparisonLabel={comparison?.label || null}
                                        statusLabel={diagnosticStatusLabel(candidate.status, language)}
                                        watchlistActionLabel={getWatchlistActionLabel(isTracked, isTrackPending, watchlistAuthBlocked, language)}
                                        watchlistActionTitle={getWatchlistActionTitle(isTracked, watchlistAuthBlocked, language)}
                                        copyLabel={copiedKey === `candidate:${candidate.symbol}` ? (language === 'en' ? 'Copied' : '已复制') : (language === 'en' ? 'Copy' : '复制')}
                                        exportLabel={language === 'en' ? 'Export' : '导出'}
                                        isTracked={isTracked}
                                        isTrackPending={isTrackPending}
                                        isWatchlistAuthBlocked={watchlistAuthBlocked}
                                        isAnalyzing={false}
                                        backtestLabel={getBacktestActionLabel(backtestItem)}
                                        backtestTitle={!normalizeCandidateSymbol(sourceCandidate.symbol) ? backtestUnavailableLabel : undefined}
                                        backtestItem={backtestItem}
                                        onSelect={() => setInspectorSymbol(sourceCandidate.symbol)}
                                        onAnalyze={() => void handleAnalyzeCandidate(sourceCandidate)}
                                        onBacktest={() => void handleBacktestCandidate(sourceCandidate)}
                                        onTrack={() => void handleTrackCandidate(sourceCandidate)}
                                        onCopy={() => void handleCopyText(sourceCandidate.symbol, `candidate:${candidate.symbol}`)}
                                        onExport={() => handleExportRows(
                                          [buildScannerExportRow(sourceCandidate, activeRunDetail, language)],
                                          buildScannerExportFilename(activeRunDetail, `candidate-${candidate.symbol}`),
                                        )}
                                        onToggleMore={() => setRowMoreSymbol((current) => current === candidate.symbol ? null : candidate.symbol)}
                                      />
                                    );
                                  })}
                                </div>
                              </div>
                            </div>
                            <div data-testid="scanner-post-table-summaries" className="mt-3 grid gap-3">
                              {activeDetailCandidate ? (
                                <ScannerWorkflowSummaryPanel
                                  contextSummary={scannerTopDownContextView}
                                  candidate={activeDetailCandidate}
                                  diagnostic={activeDetailDiagnostic}
                                  rankedRowCount={workbenchDiagnostics.length}
                                  selectedCount={currentSelectedCount}
                                  language={language}
                                />
                              ) : null}
                              {visualEvidenceSummary ? (
                                <ScannerVisualEvidenceSummaryPanel model={visualEvidenceSummary} language={language} />
                              ) : null}
                            </div>
                          </>
                        ) : (
                          <CompactEmptyRow
                            data-testid="scanner-workbench-empty-state"
                            title={workbenchEmptyState.title}
                            className="m-0 min-h-[120px]"
                          >
                            <div className="grid min-w-0 gap-3">
                              <p>{workbenchEmptyState.body}</p>
                            </div>
                          </CompactEmptyRow>
                        )}

                      </div>

                      {activeDetailCandidate ? (
                        <div data-testid="scanner-context-rail" className="min-w-0">
                          {!showDetailRail ? (
                          <div data-testid="scanner-inline-detail-panel" className="max-h-[min(72vh,42rem)] overflow-y-auto rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3 no-scrollbar ui-scroll-y-quiet">
                            <div data-testid={`scanner-candidate-detail-${activeDetailCandidate.symbol || 'unknown'}`} className="contents">
                              <div data-testid="scanner-candidate-inspector" className="contents">
                                {renderCandidateDetailPanel(
                                  activeDetailCandidate,
                                  activeDetailTracked,
                                  activeDetailTrackPending,
                                  activeDetailDiagnostic
                                    ? (isOfficialSelected(activeDetailDiagnostic)
                                      ? getKeyReason(activeDetailCandidate, runDetail, language)
                                      : formatFriendlyDiagnosticReason(activeDetailDiagnostic, language))
                                    : null,
                                  activeDetailBacktestItem,
                                )}
                              </div>
                            </div>
                          </div>
                          ) : null}

                          {showDetailRail ? (
                          <aside data-testid="scanner-detail-rail" className="sticky top-4 self-start max-h-[min(72vh,42rem)] overflow-y-auto rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3 no-scrollbar ui-scroll-y-quiet">
                            <div data-testid={`scanner-candidate-detail-${activeDetailCandidate.symbol || 'unknown'}`} className="contents">
                              <div data-testid="scanner-candidate-inspector" className="contents">
                                {renderCandidateDetailPanel(
                                  activeDetailCandidate,
                                  activeDetailTracked,
                                  activeDetailTrackPending,
                                  activeDetailDiagnostic
                                    ? (isOfficialSelected(activeDetailDiagnostic)
                                      ? getKeyReason(activeDetailCandidate, runDetail, language)
                                      : formatFriendlyDiagnosticReason(activeDetailDiagnostic, language))
                                    : null,
                                  activeDetailBacktestItem,
                                )}
                              </div>
                            </div>
                          </aside>
                          ) : null}
                        </div>
                      ) : null}
                    </div>

                    {runDetail && hasCandidateDiagnostics ? (
                      <div data-testid="scanner-secondary-deck" className="border-t border-[color:var(--wolfy-divider)] px-2 py-0">
                        <div data-testid="scanner-secondary-sections" className="grid gap-2 xl:grid-cols-2 2xl:grid-cols-4">
                          <AdvancedDisclosure
                            testId="scanner-run-status-disclosure"
                            title={language === 'en' ? 'Run status' : '运行状态'}
                            summary={language === 'en'
                              ? `Evaluated ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize} · selected ${runDetail.summary?.selectedCount ?? shortlistCount}`
                              : `评估 ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize} · 入选 ${runDetail.summary?.selectedCount ?? shortlistCount}`}
                            icon="info"
                          >
                            <div className="max-h-[min(28vh,18rem)] overflow-y-auto no-scrollbar ui-scroll-y-quiet space-y-2">
                              <div className="grid gap-1.5 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3 text-xs">
                                <div className="flex items-center justify-between gap-2 border-b border-[color:var(--wolfy-divider)] pb-1.5">
                                  <span className="text-[10px] uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Data' : '数据'}</span>
                                  <span className="truncate font-mono text-[color:var(--wolfy-text-primary)]">{scannerDataStateLabel}</span>
                                </div>
                                <div className="flex items-center justify-between gap-2 border-b border-[color:var(--wolfy-divider)] pb-1.5">
                                  <span className="text-[10px] uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Latest' : '最近'}</span>
                                  <span className="truncate font-mono text-[color:var(--wolfy-text-primary)]">{generatedAt ? formatTimestamp(generatedAt, language) : '--'}</span>
                                </div>
                                <div className="flex items-center justify-between gap-2">
                                  <span className="text-[10px] uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">{language === 'en' ? 'Theme' : '主题'}</span>
                                  <span className="truncate font-mono text-[color:var(--wolfy-text-primary)]">{scannerThemeLabel}</span>
                                </div>
                              </div>
                            </div>
                          </AdvancedDisclosure>

                          {rejectionBuckets.length || hasRunDiagnosticsContent(runDetail) ? (
                            <AdvancedDisclosure
                              testId="scanner-diagnostics-disclosure"
                              title={language === 'en' ? 'View scanner diagnostics' : '查看扫描诊断'}
                              summary={language === 'en'
                                ? `Evaluated ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize} · main rejection ${rejectionBuckets[0]?.label || 'n/a'}`
                                : `评估 ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize} · 主要淘汰 ${rejectionBuckets[0]?.label || '暂无'}`}
                              icon="info"
                            >
                              <div className="max-h-[min(34vh,20rem)] overflow-y-auto no-scrollbar ui-scroll-y-quiet">
                                <div data-testid="scanner-diagnostics-summary" className="mb-2 border-t border-[color:var(--wolfy-divider)] py-2 text-xs">
                                  <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                                    <p className="min-w-0 text-[color:var(--wolfy-text-secondary)]">
                                      {language === 'en'
                                        ? `Evaluated ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize} · selected ${runDetail.summary?.selectedCount ?? shortlistCount} · main rejection ${rejectionBuckets[0]?.label || 'n/a'}`
                                        : `评估 ${runDetail.summary?.evaluatedCount ?? runDetail.evaluatedSize} · 入选 ${runDetail.summary?.selectedCount ?? shortlistCount} · 主要淘汰 ${rejectionBuckets[0]?.label || '暂无'}`}
                                    </p>
                                    <ActionButton
                                      label={language === 'en' ? 'Rejection mix' : '淘汰分布'}
                                      onClick={() => setIsRejectionSummaryOpen((current) => !current)}
                                    />
                                  </div>
                                  {isRejectionSummaryOpen && rejectionBuckets.length ? (
                                    <div data-testid="scanner-rejection-aggregate" className="mt-2 flex min-w-0 flex-wrap items-center gap-1.5">
                                      {rejectionBuckets.map((bucket) => (
                                        <button
                                          key={bucket.label}
                                          type="button"
                                          className="inline-flex max-w-full items-baseline gap-1 border-b border-[color:var(--wolfy-divider)] px-1.5 py-0.5 text-[10px] text-[color:var(--wolfy-text-secondary)] hover:text-[color:var(--wolfy-text-primary)]"
                                          onClick={() => setCandidateFilter(bucket.label === rejectionBucketLabel('data', language) ? 'data_failed' : 'rejected')}
                                        >
                                          <span className="truncate">{bucket.label}</span>
                                          <span className="font-mono text-[color:var(--wolfy-text-primary)]">{bucket.value}</span>
                                        </button>
                                      ))}
                                    </div>
                                  ) : null}
                                </div>
                                <ScannerDiagnosticsPanel runDetail={runDetail} language={language} />
                              </div>
                            </AdvancedDisclosure>
                          ) : null}

                          <AdvancedDisclosure
                            testId="scanner-run-comparison-strip"
                            title={language === 'en' ? 'Comparison records' : '比较记录'}
                            summary={comparisonState.previousRun && comparisonState.chips.length
                              ? `${language === 'en' ? 'Compared with previous run' : '上次对比'}：${comparisonState.chips[0]}`
                              : (language === 'en' ? 'No previous comparable run' : '暂无上次扫描对比')}
                            icon="history"
                          >
                            <div className="max-h-[min(28vh,18rem)] overflow-y-auto no-scrollbar ui-scroll-y-quiet space-y-2">
                              <ScannerResultHistorySummary
                                currentSummary={currentRunSummary}
                                recentSummary={recentRunSummary}
                                previousSummary={previousRunSummary}
                                comparisonItems={comparisonHighlights}
                                hasHistory={historyItems.length > 0}
                                language={language}
                              />
                              <div className="ui-scroll-x-quiet flex max-w-full items-center gap-1.5">
                                <span className="shrink-0 text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">
                                  {language === 'en' ? 'Compared with previous run' : '上次对比'}
                                </span>
                                {comparisonState.previousRun && comparisonState.chips.length ? (
                                  comparisonState.chips.map((chip) => (
                                    <span key={chip} className="shrink-0 border-b border-[color:var(--wolfy-divider)] px-1.5 py-0.5 text-[color:var(--wolfy-text-secondary)]">
                                      {chip}
                                    </span>
                                  ))
                                ) : (
                                  <span className="shrink-0 border-b border-[color:var(--wolfy-divider)] px-1.5 py-0.5 text-[color:var(--wolfy-text-muted)]">
                                    {language === 'en' ? 'No previous comparable run' : '暂无上次扫描对比'}
                                  </span>
                                )}
                              </div>
                            </div>
                          </AdvancedDisclosure>

                          <AdvancedDisclosure
                            testId="scanner-strategy-experiment"
                            title={language === 'en' ? 'Backtest setup' : '回测准备'}
                            summary={language === 'en' ? 'Simulation · batch backtest · recent results' : '模拟 · 批量回测 · 最近结果'}
                            icon="backtest"
                          >
                            <div className="max-h-[min(38vh,24rem)] overflow-y-auto no-scrollbar ui-scroll-y-quiet space-y-3">
                              <div
                                data-testid="scanner-strategy-preview"
                                className="border-t border-[color:var(--wolfy-divider)] py-2 text-xs"
                              >
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">
                                    <LineChart className="h-3.5 w-3.5" aria-hidden="true" />
                                    {language === 'en' ? 'Threshold preview' : '阈值预览'}
                                  </span>
                                  {[40, 50, 60].map((threshold) => (
                                    <button
                                      key={threshold}
                                      type="button"
                                      aria-pressed={previewThreshold === threshold}
                                      className={`rounded-md border px-2 py-0.5 font-mono text-[11px] ${previewThreshold === threshold ? 'border-[color:var(--wolfy-accent)] bg-[color:color-mix(in_srgb,var(--wolfy-accent)_12%,transparent)] text-[color:var(--wolfy-text-primary)]' : 'border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-muted)] hover:text-[color:var(--wolfy-text-secondary)]'}`}
                                      onClick={() => setPreviewThreshold(threshold)}
                                    >
                                      {threshold}
                                    </button>
                                  ))}
                                  <FieldChip label={language === 'en' ? 'Official' : '官方'} value={String(runDetail.summary?.selectedCount ?? officialSelectedDiagnostics.length)} />
                                  <FieldChip label={language === 'en' ? 'Preview' : '预览'} value={String(previewSelectedDiagnostics.length)} />
                                </div>
                              </div>
                              <Suspense fallback={<ScannerStrategySimulationPanelFallback language={language} />}>
                                <LazyScannerStrategySimulationPanel
                                  language={language}
                                  lookbackDays={simulationLookbackDays}
                                  forwardDays={simulationForwardDays}
                                  onLookbackDaysChange={setSimulationLookbackDays}
                                  onForwardDaysChange={setSimulationForwardDays}
                                  onRun={() => void handleStrategySimulation()}
                                  result={strategySimulation}
                                  isLoading={isStrategySimulationLoading}
                                  error={strategySimulationError}
                                  disabled={strategySimulationDisabled}
                                />
                              </Suspense>
                              <Suspense fallback={null}>
                                <LazyScannerBacktestLab
                                  language={language}
                                  items={backtestItems}
                                  isRunning={isBacktestBatchRunning}
                                  onRunBatch={handleBacktestBatch}
                                  onCopySymbol={(symbol) => void handleCopyText(symbol, `backtest:${symbol}`)}
                                  counts={backtestCounts}
                                />
                              </Suspense>
                            </div>
                          </AdvancedDisclosure>
                        </div>
                      </div>
                    ) : null}
                  </div>
                  </section>
                </DenseTableShell>

                <WolfyShellSurface
                  as="aside"
                  variant="rail"
                  padding="sm"
                  data-testid="scanner-summary-rail"
                  data-layout-zone="ContextRail"
                  className="min-w-0 self-start rounded-xl border-[color:var(--wolfy-border-subtle)] lg:sticky lg:top-4"
                  aria-label={language === 'en' ? 'Scanner workspace summary' : '扫描工作区摘要'}
                >
                  <div className="flex min-w-0 flex-col gap-4">
                    <div className="min-w-0 border-b border-[color:var(--wolfy-divider)] pb-3">
                      <p className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">
                        {language === 'en' ? 'Workspace summary' : '工作区摘要'}
                      </p>
                      <h2 className="mt-1 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
                        {scannerConclusion.title}
                      </h2>
                      <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                        {scannerConclusion.detail}
                      </p>
                    </div>

                    <div className="grid min-w-0 grid-cols-3 gap-2" data-testid="scanner-summary-rail-counts">
                      {scannerRailCounts.map((item) => (
                        <div key={item.label} className="min-w-0 rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-2 py-2">
                          <p className="truncate text-[10px] text-[color:var(--wolfy-text-muted)]">{item.label}</p>
                          <p className="mt-1 font-mono text-base font-semibold text-[color:var(--wolfy-text-primary)]">{item.value}</p>
                        </div>
                      ))}
                    </div>

                    {scannerRunFactItems.length ? (
                      <section data-testid="scanner-run-facts" className="grid min-w-0 gap-2 border-b border-[color:var(--wolfy-divider)] pb-3">
                        <p className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">
                          {language === 'en' ? 'Run facts' : '运行事实'}
                        </p>
                        <dl className="grid min-w-0 gap-1.5 text-xs">
                          {scannerRunFactItems.map((item) => (
                            <div key={`${item.label}-${item.value}`} className="grid min-w-0 grid-cols-[5rem_minmax(0,1fr)] gap-2">
                              <dt className="text-[color:var(--wolfy-text-muted)]">{item.label}</dt>
                              <dd className="truncate text-right font-mono text-[color:var(--wolfy-text-primary)]">{item.value}</dd>
                            </div>
                          ))}
                        </dl>
                      </section>
                    ) : null}

                    <dl className="grid min-w-0 gap-2 text-xs" data-testid="scanner-summary-rail-context">
                      {scannerRailItems.map((item) => (
                        <div key={item.label} className="grid min-w-0 grid-cols-[4.5rem_minmax(0,1fr)] gap-2 border-b border-[color:var(--wolfy-divider)] pb-2 last:border-b-0 last:pb-0">
                          <dt className="text-[color:var(--wolfy-text-muted)]">{item.label}</dt>
                          <dd className="truncate text-right font-mono text-[color:var(--wolfy-text-primary)]">{item.value}</dd>
                        </div>
                      ))}
                    </dl>
                    <p data-testid="scanner-history-scope-hint" className="rounded-lg border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-input)] px-2.5 py-2 text-[11px] leading-relaxed text-[color:var(--wolfy-text-secondary)]">
                      {scannerHistoryScopeHint}
                    </p>
                  </div>
                </WolfyShellSurface>
		          </div>
              <ResearchWorkspaceFlowPanel
                language={language}
                current="scanner"
                symbol={researchWorkflowSymbol}
                market={researchWorkflowMarket}
                source="scanner"
                knownEvidence={researchWorkflowKnownEvidence}
                missingEvidence={researchWorkflowMissingEvidence}
                stateNotes={researchWorkflowStateNotes}
                nextSteps={researchWorkflowNextSteps}
                className="mx-3"
                testId="scanner-research-workspace-flow"
              />
              <ConsumerResearchReadinessStrip
                readiness={scannerResearchReadinessView}
                title={language === 'en' ? 'Research readiness' : '研究就绪度'}
                testId="scanner-research-readiness-strip-secondary"
                className="mx-3 xl:hidden"
              />
	        </ConsumerWorkspacePageShell>
          </ConsumerWorkspaceScope>
      </div>

      <ScannerHistoryDrawer
        isOpen={isHistoryDrawerOpen}
        onClose={() => setIsHistoryDrawerOpen(false)}
        language={language}
        historyError={historyError}
        isLoadingHistory={isLoadingHistory}
        items={historyCards}
        selectedRunId={selectedRunId}
        emptyStateTitle={emptyStateTitle}
        emptyStateBody={emptyStateBody}
        loadingLabel={t('scanner.loadingHistory')}
        shortlistMetricLabel={t('scanner.metricShortlist')}
        universeMetricLabel={t('scanner.metricUniverse')}
        evaluatedMetricLabel={language === 'en' ? 'Evaluated' : '已评估'}
        historyPage={historyPage}
        totalHistoryPages={totalHistoryPages}
        onPageChange={(page) => void fetchHistory(page)}
        onSelectRun={(runId) => {
          void loadRun(runId);
          setIsHistoryDrawerOpen(false);
        }}
      />
    </>
  );
};

export default UserScannerPage;
