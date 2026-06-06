import type {
  AnalysisEvidenceCitationDomain,
  AnalysisEvidenceCitationDomainCoverageEntry,
  AnalysisEvidenceCitationFrame,
  AnalysisEvidenceCitationItem,
  AnalysisEvidenceCoverageDomain,
  AnalysisEvidenceCoverageEntry,
  AnalysisEvidenceCoverageFrame,
  AnalysisReport,
  DataQualityReport,
  ReportMeta,
  SourceProvenanceEntry,
  SourceProvenanceSummary,
} from '../types/analysis';
import type { MarketDirectionReadiness, MarketTemperatureResponse } from './market';
import type { OptionsDecisionResponse } from './optionsLab';
import type {
  ConsumerReadinessChip,
  ConsumerReadinessTone,
  ConsumerResearchReadinessView,
  OptionsResearchReadiness,
  ResearchFreshnessFloor,
  ResearchReadinessState,
  ResearchReadinessV1,
  ResearchSourceAuthority,
  ScannerContextFrame,
  ScannerContextSignalFrame,
} from '../types/researchReadiness';
import type { ScannerRunDetail } from '../types/scanner';

type ReadinessLocale = 'zh' | 'en';

type UnknownRecord = Record<string, unknown>;

export type ScannerTopDownContextPosture =
  | 'supportive'
  | 'mixed'
  | 'observe_only'
  | 'insufficient'
  | 'blocked'
  | 'waiting';

export interface ScannerTopDownContextView {
  posture: ScannerTopDownContextPosture;
  postureLabel: string;
  tone: ConsumerReadinessTone;
  summaryLine: string;
  chips: ConsumerReadinessChip[];
}

const EVIDENCE_LABELS: Record<string, { zh: string; en: string }> = {
  technical: { zh: '技术证据', en: 'technical evidence' },
  fundamentals: { zh: '基本面证据', en: 'fundamental evidence' },
  news: { zh: '新闻证据', en: 'news evidence' },
  catalyst: { zh: '催化证据', en: 'catalyst evidence' },
  macro: { zh: '宏观证据', en: 'macro evidence' },
  liquidity: { zh: '流动性证据', en: 'liquidity evidence' },
  source_authority: { zh: '来源授权', en: 'source authority' },
  freshness: { zh: '时效证据', en: 'freshness' },
};

const BLOCKING_REASON_LABELS: Record<string, { zh: string; en: string }> = {
  missing_required_evidence: { zh: '关键证据缺失', en: 'required evidence missing' },
  important_data_missing: { zh: '关键信息缺失', en: 'important data missing' },
  optional_enrichment_missing: { zh: '补充证据待完成', en: 'enrichment still pending' },
  source_authority_router_rejected: { zh: '来源授权不足', en: 'source authority limited' },
  provider_fixture_not_decision_grade: { zh: '演示数据', en: 'fixture data only' },
  provider_synthetic_not_decision_grade: { zh: '合成数据', en: 'synthetic data only' },
  provider_live_disabled: { zh: '实时链未启用', en: 'live chain disabled' },
  provider_tradeable_data_false: { zh: '来源非判断级', en: 'provider not decision grade' },
  provider_authority_tier_observation_only: { zh: '来源仅观察', en: 'observation-only authority' },
  provider_authority_tier_analysis_only: { zh: '来源仅分析', en: 'analysis-only authority' },
  synthetic_or_fixture_data_not_decision_grade: { zh: '非判断级数据', en: 'not decision-grade data' },
  missing_iv: { zh: '缺少 IV', en: 'IV missing' },
  missing_greeks: { zh: '缺少 Greeks', en: 'Greeks missing' },
  low_or_missing_volume: { zh: '成交量不足', en: 'volume limited' },
  low_or_missing_open_interest: { zh: '持仓量不足', en: 'open interest limited' },
  expected_move_unavailable: { zh: '预期波动缺失', en: 'expected move missing' },
  iv_rank_unavailable: { zh: 'IV 分位缺失', en: 'IV rank missing' },
};

function isRecord(value: unknown): value is UnknownRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (typeof item !== 'string') return [];
    const text = item.trim();
    return text ? [text] : [];
  });
}

function uniqueStrings(values: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const ordered: string[] = [];
  values.forEach((value) => {
    const text = value?.trim();
    if (!text || seen.has(text)) return;
    seen.add(text);
    ordered.push(text);
  });
  return ordered;
}

function localizedStateLabel(state: ResearchReadinessState, locale: ReadinessLocale): string {
  const labels: Record<string, { zh: string; en: string }> = {
    ready: { zh: '研究证据可用', en: 'Research-ready' },
    observe_only: { zh: '仅观察', en: 'Observe only' },
    insufficient: { zh: '证据不足', en: 'Evidence insufficient' },
    blocked: { zh: '研究结论受限', en: 'Blocked' },
    waiting: { zh: '等待证据更新', en: 'Waiting' },
  };
  return labels[state]?.[locale] || labels.observe_only[locale];
}

function toneForState(state: ResearchReadinessState): ConsumerReadinessTone {
  if (state === 'ready') return 'success';
  if (state === 'blocked') return 'danger';
  if (state === 'insufficient') return 'caution';
  if (state === 'waiting') return 'neutral';
  return 'info';
}

function localizedSourceAuthorityLabel(
  authority: ResearchSourceAuthority | undefined,
  locale: ReadinessLocale,
): string | null {
  const labels: Record<string, { zh: string; en: string }> = {
    scoreGradeAllowed: { zh: '来源：评分级', en: 'Authority: score-grade' },
    observationOnly: { zh: '来源：仅观察', en: 'Authority: observation-only' },
    unavailable: { zh: '来源：未确认', en: 'Authority: unavailable' },
  };
  return authority ? labels[authority]?.[locale] || null : null;
}

function localizedFreshnessLabel(
  freshness: ResearchFreshnessFloor | undefined,
  locale: ReadinessLocale,
): string | null {
  const labels: Record<string, { zh: string; en: string }> = {
    live: { zh: '时效：实时', en: 'Freshness: live' },
    fresh: { zh: '时效：新鲜', en: 'Freshness: fresh' },
    delayed: { zh: '时效：延迟', en: 'Freshness: delayed' },
    cached: { zh: '时效：缓存', en: 'Freshness: cached' },
    stale: { zh: '时效：陈旧', en: 'Freshness: stale' },
    fallback: { zh: '时效：回退', en: 'Freshness: fallback' },
    synthetic: { zh: '时效：演示', en: 'Freshness: synthetic' },
    unknown: { zh: '时效：未确认', en: 'Freshness: unknown' },
  };
  return freshness ? labels[freshness]?.[locale] || null : null;
}

function localizedCoverageLabel(
  readiness: ResearchReadinessV1 | null | undefined,
  locale: ReadinessLocale,
): string | null {
  const coverage = readiness?.evidenceCoverage;
  if (!coverage) return null;
  const scoreGradeCount = coverage.scoreGradeCount ?? 0;
  const observationOnlyCount = coverage.observationOnlyCount ?? 0;
  const missingCount = coverage.missingCount ?? 0;
  if (scoreGradeCount === 0 && observationOnlyCount === 0 && missingCount === 0) return null;
  return locale === 'en'
    ? `Coverage ${scoreGradeCount}/${observationOnlyCount}/${missingCount}`
    : `覆盖 ${scoreGradeCount}/${observationOnlyCount}/${missingCount}`;
}

function labelFromMap(
  code: string,
  mapping: Record<string, { zh: string; en: string }>,
  locale: ReadinessLocale,
): string | null {
  return mapping[code]?.[locale] || null;
}

function localizedEvidenceLabel(code: string, locale: ReadinessLocale): string | null {
  return labelFromMap(code, EVIDENCE_LABELS, locale);
}

function localizedBlockingReasonLabel(code: string, locale: ReadinessLocale): string | null {
  return labelFromMap(code, BLOCKING_REASON_LABELS, locale);
}

function sanitizeHumanReason(value: string | null | undefined): string | null {
  const text = value?.trim();
  if (!text) return null;
  if (/[A-Za-z]/.test(text) && /_/.test(text)) return null;
  return text;
}

function summarizeReadiness(
  readiness: ResearchReadinessV1 | null | undefined,
  locale: ReadinessLocale,
): string {
  const blockingReasons = uniqueStrings(
    asStringArray(readiness?.blockingReasons).map((item) => localizedBlockingReasonLabel(item, locale)),
  );
  if (blockingReasons.length) {
    return blockingReasons.slice(0, 2).join(' · ');
  }

  const missingEvidence = uniqueStrings(
    asStringArray(readiness?.missingEvidence).map((item) => localizedEvidenceLabel(item, locale)),
  );
  if (missingEvidence.length) {
    return locale === 'en'
      ? `Missing ${missingEvidence.slice(0, 2).join(' / ')}.`
      : `待补：${missingEvidence.slice(0, 2).join(' / ')}`;
  }

  const nextEvidence = uniqueStrings(asStringArray(readiness?.nextEvidenceNeeded).map((item) => sanitizeHumanReason(item)));
  if (nextEvidence.length) {
    return nextEvidence[0];
  }

  const state = readiness?.readinessState || 'observe_only';
  if (state === 'ready') {
    return locale === 'en' ? 'Evidence and boundaries are available.' : '证据与边界已齐备。';
  }
  if (state === 'blocked') {
    return locale === 'en' ? 'A blocking condition still limits the conclusion.' : '仍有阻断条件限制当前结论。';
  }
  if (state === 'insufficient') {
    return locale === 'en' ? 'Required evidence is still incomplete.' : '关键证据仍未补齐。';
  }
  if (state === 'waiting') {
    return locale === 'en' ? 'Waiting for the next evidence refresh.' : '等待下一次证据更新。';
  }
  return locale === 'en' ? 'Keep this result in observe-only mode.' : '当前结果先按仅观察处理。';
}

function localizedScannerContextPostureLabel(
  posture: ScannerTopDownContextPosture,
  locale: ReadinessLocale,
): string {
  const labels: Record<ScannerTopDownContextPosture, { zh: string; en: string }> = {
    supportive: { zh: '支持性', en: 'Supportive' },
    mixed: { zh: '混合', en: 'Mixed' },
    observe_only: { zh: '仅观察', en: 'Observe only' },
    insufficient: { zh: '证据不足', en: 'Evidence insufficient' },
    blocked: { zh: '阻断', en: 'Blocked' },
    waiting: { zh: '等待中', en: 'Waiting' },
  };
  return labels[posture][locale];
}

function scannerContextTone(
  posture: ScannerTopDownContextPosture,
): ConsumerReadinessTone {
  if (posture === 'supportive') return 'success';
  if (posture === 'blocked') return 'danger';
  if (posture === 'insufficient') return 'caution';
  if (posture === 'waiting') return 'neutral';
  return 'info';
}

function normalizeScannerContextPosture(state: string | null | undefined): ScannerTopDownContextPosture {
  const normalized = String(state || '').trim().toLowerCase();
  if (!normalized) return 'insufficient';
  if (normalized === 'ready' || normalized === 'supportive') return 'supportive';
  if (normalized === 'mixed' || normalized === 'partial') return 'mixed';
  if (normalized === 'observe_only' || normalized === 'observation_only') return 'observe_only';
  if (normalized === 'blocked') return 'blocked';
  if (normalized === 'waiting') return 'waiting';
  if (normalized === 'insufficient' || normalized === 'data_insufficient' || normalized === 'missing' || normalized === 'unavailable') {
    return 'insufficient';
  }
  return 'observe_only';
}

function localizedSignalStateLabel(
  posture: ScannerTopDownContextPosture,
  locale: ReadinessLocale,
): string {
  return localizedScannerContextPostureLabel(posture, locale);
}

function localizedUniversePolicyLabel(
  type: string | null | undefined,
  locale: ReadinessLocale,
): string {
  const labels: Record<string, { zh: string; en: string }> = {
    default: { zh: '默认池', en: 'Default universe' },
    theme: { zh: '主题池', en: 'Theme universe' },
    symbols: { zh: '自选池', en: 'Custom symbols' },
  };
  return labels[String(type || '').trim().toLowerCase()]?.[locale] || (locale === 'en' ? 'Universe pending' : '标的池待确认');
}

function themeLabels(frame: ScannerContextFrame | null | undefined): string[] {
  const labels = (frame?.themeFrame?.themes || [])
    .map((item) => sanitizeHumanReason(item?.label || null))
    .filter((item): item is string => Boolean(item));
  return uniqueStrings(labels);
}

function collectScannerContextBlockers(frame: ScannerContextFrame | null | undefined): string[] {
  return uniqueStrings([
    ...asStringArray(frame?.macroRegime?.blockers),
    ...asStringArray(frame?.liquidityFrame?.blockers),
    ...asStringArray(frame?.assetClassBias?.blockers),
    ...asStringArray(frame?.themeFrame?.blockers),
    ...asStringArray(frame?.universePolicy?.blockers),
    ...asStringArray(frame?.marketReadiness?.blockingReasons),
  ]);
}

function hasMeaningfulScannerContext(frame: ScannerContextFrame | null | undefined): boolean {
  return Boolean(
    frame?.marketReadiness
    || frame?.macroRegime
    || frame?.liquidityFrame
    || frame?.assetClassBias
    || frame?.themeFrame
    || frame?.universePolicy
    || frame?.noAdviceBoundary === true,
  );
}

function deriveScannerContextPosture(
  frame: ScannerContextFrame | null | undefined,
): ScannerTopDownContextPosture {
  if (!hasMeaningfulScannerContext(frame)) return 'insufficient';

  const postures: ScannerTopDownContextPosture[] = [
    frame?.marketReadiness ? normalizeScannerContextPosture(frame.marketReadiness.readinessState) : 'insufficient',
    frame?.macroRegime ? normalizeScannerContextPosture(frame.macroRegime.state) : 'insufficient',
    frame?.liquidityFrame ? normalizeScannerContextPosture(frame.liquidityFrame.state) : 'insufficient',
    frame?.assetClassBias ? normalizeScannerContextPosture(frame.assetClassBias.state) : 'insufficient',
    frame?.themeFrame ? normalizeScannerContextPosture(frame.themeFrame.state) : 'insufficient',
  ];

  if (postures.includes('blocked')) return 'blocked';
  if (postures.includes('insufficient')) return 'insufficient';
  if (postures.includes('mixed')) return 'mixed';

  const hasSupportive = postures.includes('supportive');
  const hasObserveOnly = postures.includes('observe_only');
  if (hasSupportive && hasObserveOnly) return 'mixed';
  if (hasSupportive) return 'supportive';
  if (postures.includes('waiting')) return 'waiting';
  return 'observe_only';
}

function buildScannerContextSummaryLine(
  posture: ScannerTopDownContextPosture,
  frame: ScannerContextFrame | null | undefined,
  locale: ReadinessLocale,
): string {
  const themes = themeLabels(frame);
  const themeText = themes.length ? themes.slice(0, 2).join(locale === 'en' ? ' / ' : ' / ') : null;
  const blockers = collectScannerContextBlockers(frame);
  const cnUnavailable = blockers.includes('cn_context_unavailable');

  if (posture === 'supportive') {
    return locale === 'en'
      ? 'Candidates are framed by supportive macro, liquidity, and theme context.'
      : '宏观、流动性与主题框架一致，当前候选来自支持性市场环境。';
  }
  if (posture === 'mixed') {
    if (themeText) {
      return locale === 'en'
        ? `Candidates sit inside a mixed context; ${themeText} remains observe-only.`
        : `当前候选来自支持与观察并存的市场框架，${themeText} 线索先按观察级处理。`;
    }
    return locale === 'en'
      ? 'Candidates sit inside a mix of supportive and observe-only context.'
      : '当前候选来自支持与观察并存的市场框架。';
  }
  if (posture === 'observe_only') {
    if (themeText) {
      return locale === 'en'
        ? `${themeText} remains observe-only, so the context stays non-upgraded.`
        : `当前候选主要来自观察级市场框架，${themeText} 线索不升级为更强研究结论。`;
    }
    return locale === 'en'
      ? 'Context remains observe-only, so candidates stay in a bounded research mode.'
      : '当前候选主要来自观察级市场框架，不升级为更强研究结论。';
  }
  if (posture === 'blocked') {
    return cnUnavailable
      ? (locale === 'en'
          ? 'CN market context is currently unavailable, so candidates stay blocked from a stronger conclusion.'
          : '当前市场上下文暂不可用，当前候选不升级为更强研究结论。')
      : (locale === 'en'
          ? 'A blocking market condition still limits the scanner context.'
          : '当前市场上下文存在阻断条件，当前候选不升级为更强研究结论。');
  }
  if (posture === 'waiting') {
    return locale === 'en'
      ? 'Waiting for the next market and scanner context refresh.'
      : '等待下一次市场与扫描上下文刷新。';
  }
  return locale === 'en'
    ? 'Market, liquidity, or theme context is still incomplete, so candidates stay fail-closed.'
    : '市场、流动性或主题上下文仍有缺口，当前候选先按证据不足处理。';
}

export function buildConsumerResearchReadinessView(
  readiness: ResearchReadinessV1 | null | undefined,
  locale: ReadinessLocale,
): ConsumerResearchReadinessView {
  const state = readiness?.readinessState || 'observe_only';
  return {
    state,
    verdictLabel: sanitizeHumanReason(readiness?.verdictLabel) || localizedStateLabel(state, locale),
    tone: toneForState(state),
    summaryLine: summarizeReadiness(readiness, locale),
    chips: uniqueStrings([
      localizedSourceAuthorityLabel(readiness?.sourceAuthority, locale),
      localizedFreshnessLabel(readiness?.freshnessFloor, locale),
      localizedCoverageLabel(readiness, locale),
    ]).map((label) => ({ key: label, label })),
  };
}

function readNestedResearchReadiness(value: unknown): ResearchReadinessV1 | null {
  if (!isRecord(value)) return null;
  const state = typeof value.readinessState === 'string' ? value.readinessState : null;
  if (!state) return null;
  return {
    contractVersion: typeof value.contractVersion === 'string' ? value.contractVersion : undefined,
    researchReady: value.researchReady === true,
    readinessState: state,
    verdictLabel: typeof value.verdictLabel === 'string' ? value.verdictLabel : undefined,
    blockingReasons: asStringArray(value.blockingReasons),
    missingEvidence: asStringArray(value.missingEvidence),
    evidenceCoverage: isRecord(value.evidenceCoverage) ? value.evidenceCoverage : null,
    sourceAuthority: typeof value.sourceAuthority === 'string' ? value.sourceAuthority : undefined,
    freshnessFloor: typeof value.freshnessFloor === 'string' ? value.freshnessFloor : undefined,
    consumerActionBoundary: typeof value.consumerActionBoundary === 'string' ? value.consumerActionBoundary : undefined,
    nextEvidenceNeeded: asStringArray(value.nextEvidenceNeeded),
    debugRef: typeof value.debugRef === 'string' ? value.debugRef : undefined,
  };
}

const ANALYSIS_EVIDENCE_COVERAGE_DOMAINS: AnalysisEvidenceCoverageDomain[] = [
  'priceHistory',
  'technicals',
  'fundamentals',
  'earnings',
  'news',
  'catalysts',
  'sentiment',
  'valuation',
  'liquidityContext',
  'macroContext',
];

const ANALYSIS_EVIDENCE_CITATION_DOMAINS: AnalysisEvidenceCitationDomain[] = [
  'priceHistory',
  'technicals',
  'fundamentals',
  'earnings',
  'filings',
  'news',
  'catalysts',
  'sentiment',
  'valuation',
  'sectorTheme',
  'macroLiquidity',
];

const ANALYSIS_EVIDENCE_CITATION_STATUSES = new Set(['available', 'degraded', 'missing', 'blocked', 'pending']);
const ANALYSIS_EVIDENCE_CITATION_FORBIDDEN_TEXT = /provider|authority|freshness|debug|analysis:|router|cache|credential|token|prompt|request[\s_-]*body|raw[\s_-]*payload|article[\s_-]*body|sourceid|source_id|internal|env/i;
const SOURCE_PROVENANCE_AUTHORITY_TIERS = new Set(['score_grade', 'trusted_public', 'stored_snapshot', 'observation_only', 'fixture', 'unknown']);
const SOURCE_PROVENANCE_FRESHNESS_STATES = new Set(['fresh', 'cached', 'delayed', 'partial', 'stale', 'fallback', 'synthetic', 'unavailable', 'unknown']);
const SOURCE_PROVENANCE_SOURCE_TIERS = new Set(['authorized_feed', 'official_public', 'proxy', 'stored_snapshot', 'fallback', 'fixture', 'unknown']);
const SOURCE_PROVENANCE_EVIDENCE_DOMAINS = new Set(['general', 'market_data', 'fundamentals', 'macro', 'news', 'research', 'derivatives', 'portfolio']);
const SOURCE_PROVENANCE_FORBIDDEN_TEXT = /provider|router|cache|credential|token|prompt|request[\s_-]*body|raw[\s_-]*payload|article[\s_-]*body|internal|env|trace|stack|debug/i;

function readEvidenceCoverageEntry(value: unknown): AnalysisEvidenceCoverageEntry | null {
  if (!isRecord(value)) return null;
  const status = typeof value.status === 'string' ? value.status : null;
  if (!status) return null;
  return {
    status,
    sourceTier: typeof value.sourceTier === 'string' ? value.sourceTier : null,
    sourceAuthority: typeof value.sourceAuthority === 'string' ? value.sourceAuthority : null,
    freshness: typeof value.freshness === 'string' ? value.freshness : null,
    fallbackOrProxy: value.fallbackOrProxy === true,
    missingReasons: asStringArray(value.missingReasons),
    nextEvidenceNeeded: asStringArray(value.nextEvidenceNeeded),
  };
}

function readEvidenceCoverageFrame(value: unknown): AnalysisEvidenceCoverageFrame | null {
  if (!isRecord(value)) return null;
  const frame = ANALYSIS_EVIDENCE_COVERAGE_DOMAINS.reduce<AnalysisEvidenceCoverageFrame>((acc, domain) => {
    const entry = readEvidenceCoverageEntry(value[domain]);
    if (entry) {
      acc[domain] = entry;
    }
    return acc;
  }, {});
  return Object.keys(frame).length ? frame : null;
}

function readEvidenceCitationDomain(value: unknown): AnalysisEvidenceCitationDomain | null {
  const domain = typeof value === 'string' ? value.trim() : '';
  return ANALYSIS_EVIDENCE_CITATION_DOMAINS.includes(domain as AnalysisEvidenceCitationDomain)
    ? domain as AnalysisEvidenceCitationDomain
    : null;
}

function readEvidenceCitationText(value: unknown): string | null {
  const text = typeof value === 'string' ? value.trim() : '';
  if (!text || ANALYSIS_EVIDENCE_CITATION_FORBIDDEN_TEXT.test(text)) {
    return null;
  }
  return text;
}

function readEvidenceCitationItem(value: unknown): AnalysisEvidenceCitationItem | null {
  if (!isRecord(value)) return null;
  const id = readEvidenceCitationText(value.id);
  const domain = readEvidenceCitationDomain(value.domain);
  const summary = readEvidenceCitationText(value.summary);
  if (!id || !domain || !summary) return null;
  return { id, domain, summary };
}

function readEvidenceCitationCoverageEntry(value: unknown): AnalysisEvidenceCitationDomainCoverageEntry | null {
  if (!isRecord(value)) return null;
  const domain = readEvidenceCitationDomain(value.domain);
  const status = typeof value.status === 'string' ? value.status.trim().toLowerCase() : '';
  if (!domain || !ANALYSIS_EVIDENCE_CITATION_STATUSES.has(status)) {
    return null;
  }
  return {
    domain,
    status,
    evidenceRefIds: asStringArray(value.evidenceRefIds).filter((item) => !ANALYSIS_EVIDENCE_CITATION_FORBIDDEN_TEXT.test(item)),
  };
}

function readEvidenceCitationFrame(value: unknown): AnalysisEvidenceCitationFrame | null {
  if (!isRecord(value)) return null;
  const frameState = typeof value.frameState === 'string' ? value.frameState.trim().toLowerCase() : '';
  if (!frameState || !['ready', 'observe_only', 'blocked'].includes(frameState)) {
    return null;
  }

  const citedEvidence = Array.isArray(value.citedEvidence)
    ? value.citedEvidence.map(readEvidenceCitationItem).filter((item): item is AnalysisEvidenceCitationItem => Boolean(item))
    : [];
  const domainCoverage = Array.isArray(value.domainCoverage)
    ? value.domainCoverage.map(readEvidenceCitationCoverageEntry).filter((item): item is AnalysisEvidenceCitationDomainCoverageEntry => Boolean(item))
    : [];
  const missingEvidence = asStringArray(value.missingEvidence)
    .map(readEvidenceCitationText)
    .filter((item): item is string => Boolean(item));
  const nextEvidenceNeeded = asStringArray(value.nextEvidenceNeeded)
    .map(readEvidenceCitationText)
    .filter((item): item is string => Boolean(item));
  const noAdviceBoundary = value.noAdviceBoundary === true;

  if (!noAdviceBoundary) return null;
  if (!citedEvidence.length && !domainCoverage.length && !missingEvidence.length && !nextEvidenceNeeded.length) {
    return null;
  }

  return {
    frameState,
    citedEvidence,
    domainCoverage,
    missingEvidence,
    nextEvidenceNeeded,
    noAdviceBoundary,
  };
}

function normalizeSourceProvenanceChoice(
  value: unknown,
  allowed: Set<string>,
  fallback: string,
): string {
  const normalized = typeof value === 'string'
    ? value.trim().toLowerCase().replace(/[\s-]+/g, '_')
    : '';
  return allowed.has(normalized) ? normalized : fallback;
}

function readNonNegativeNumber(value: unknown): number | null {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return null;
  return Math.floor(value);
}

function readSourceProvenanceText(value: unknown, fallback = ''): string {
  const text = typeof value === 'string' ? value.trim() : '';
  if (!text || SOURCE_PROVENANCE_FORBIDDEN_TEXT.test(text)) {
    return fallback;
  }
  return text;
}

function readSourceProvenanceCodeList(value: unknown): string[] {
  return asStringArray(value).filter((item) => !SOURCE_PROVENANCE_FORBIDDEN_TEXT.test(item));
}

function readSourceProvenanceCountMap(value: unknown): Record<string, number> | null {
  if (!isRecord(value)) return null;
  const entries = Object.entries(value).reduce<Record<string, number>>((acc, [key, raw]) => {
    const count = readNonNegativeNumber(raw);
    if (count == null) return acc;
    acc[key] = count;
    return acc;
  }, {});
  return Object.keys(entries).length ? entries : null;
}

function readSourceProvenanceEntry(value: unknown): SourceProvenanceEntry | null {
  if (!isRecord(value)) return null;
  const evidenceDomain = normalizeSourceProvenanceChoice(value.evidenceDomain, SOURCE_PROVENANCE_EVIDENCE_DOMAINS, 'general');
  return {
    contractVersion: typeof value.contractVersion === 'string' ? value.contractVersion : null,
    sourceId: readSourceProvenanceText(value.sourceId, 'unknown_source') || 'unknown_source',
    sourceLabel: readSourceProvenanceText(value.sourceLabel, '未知来源') || '未知来源',
    evidenceDomain,
    authorityTier: normalizeSourceProvenanceChoice(value.authorityTier, SOURCE_PROVENANCE_AUTHORITY_TIERS, 'unknown'),
    freshnessState: normalizeSourceProvenanceChoice(value.freshnessState, SOURCE_PROVENANCE_FRESHNESS_STATES, 'unknown'),
    sourceTier: normalizeSourceProvenanceChoice(value.sourceTier, SOURCE_PROVENANCE_SOURCE_TIERS, 'unknown'),
    fallbackOrProxy: value.fallbackOrProxy === true,
    observationOnly: value.observationOnly === true,
    scoreContributionAllowed: value.scoreContributionAllowed === true,
    limitations: readSourceProvenanceCodeList(value.limitations),
    nextEvidenceNeeded: readSourceProvenanceCodeList(value.nextEvidenceNeeded),
  };
}

function readSourceProvenanceEntries(value: unknown): SourceProvenanceEntry[] | null {
  if (!Array.isArray(value)) return null;
  const entries = value.map(readSourceProvenanceEntry).filter((item): item is SourceProvenanceEntry => Boolean(item));
  return entries.length ? entries : null;
}

export function readSourceProvenanceSummary(value: unknown): SourceProvenanceSummary | null {
  if (!isRecord(value)) return null;

  const entries = readSourceProvenanceEntries(value.entries);
  const derivedEntryCount = entries?.length ?? 0;
  const entryCount = readNonNegativeNumber(value.entryCount) ?? derivedEntryCount;
  const authorityTierCounts = readSourceProvenanceCountMap(value.authorityTierCounts);
  const freshnessStateCounts = readSourceProvenanceCountMap(value.freshnessStateCounts);
  const evidenceDomainCounts = readSourceProvenanceCountMap(value.evidenceDomainCounts);
  const fallbackOrProxyCount = readNonNegativeNumber(value.fallbackOrProxyCount)
    ?? (entries ? entries.filter((item) => item.fallbackOrProxy === true).length : 0);
  const observationOnlyCount = readNonNegativeNumber(value.observationOnlyCount)
    ?? (entries ? entries.filter((item) => item.observationOnly === true).length : 0);
  const scoreContributionAllowedCount = readNonNegativeNumber(value.scoreContributionAllowedCount)
    ?? (entries ? entries.filter((item) => item.scoreContributionAllowed === true).length : 0);

  if (
    entryCount === 0
    && !entries?.length
    && !authorityTierCounts
    && !freshnessStateCounts
    && !evidenceDomainCounts
    && fallbackOrProxyCount === 0
    && observationOnlyCount === 0
    && scoreContributionAllowedCount === 0
  ) {
    return null;
  }

  return {
    contractVersion: typeof value.contractVersion === 'string' ? value.contractVersion : null,
    entryCount,
    authorityTierCounts,
    freshnessStateCounts,
    evidenceDomainCounts,
    fallbackOrProxyCount,
    observationOnlyCount,
    scoreContributionAllowedCount,
    entries,
  };
}

export function extractAnalysisResearchReadiness(report: AnalysisReport | null | undefined): ResearchReadinessV1 | null {
  const direct = readNestedResearchReadiness((report as AnalysisReport & { researchReadiness?: unknown } | null)?.researchReadiness);
  if (direct) return direct;

  const meta = report?.meta as ReportMeta & { researchReadiness?: unknown } | undefined;
  const metaReadiness = readNestedResearchReadiness(meta?.researchReadiness);
  if (metaReadiness) return metaReadiness;

  const details = report?.details as { analysisResult?: UnknownRecord } | undefined;
  return readNestedResearchReadiness(details?.analysisResult?.researchReadiness);
}

export function extractAnalysisEvidenceCoverageFrame(
  report: AnalysisReport | null | undefined,
): AnalysisEvidenceCoverageFrame | null {
  const direct = readEvidenceCoverageFrame((report as AnalysisReport & { evidenceCoverageFrame?: unknown } | null)?.evidenceCoverageFrame);
  if (direct) return direct;

  const meta = report?.meta as ReportMeta & { evidenceCoverageFrame?: unknown } | undefined;
  const metaFrame = readEvidenceCoverageFrame(meta?.evidenceCoverageFrame);
  if (metaFrame) return metaFrame;

  const details = report?.details as { analysisResult?: UnknownRecord } | undefined;
  return readEvidenceCoverageFrame(details?.analysisResult?.evidenceCoverageFrame);
}

export function extractAnalysisEvidenceCitationFrame(
  report: AnalysisReport | null | undefined,
): AnalysisEvidenceCitationFrame | null {
  const direct = readEvidenceCitationFrame((report as AnalysisReport & { evidenceCitationFrame?: unknown } | null)?.evidenceCitationFrame);
  if (direct) return direct;

  const meta = report?.meta as ReportMeta & { evidenceCitationFrame?: unknown } | undefined;
  const metaFrame = readEvidenceCitationFrame(meta?.evidenceCitationFrame);
  if (metaFrame) return metaFrame;

  const details = report?.details as { analysisResult?: UnknownRecord } | undefined;
  return readEvidenceCitationFrame(details?.analysisResult?.evidenceCitationFrame);
}

export function extractAnalysisSourceProvenanceFrame(
  report: AnalysisReport | null | undefined,
): SourceProvenanceEntry[] | null {
  const direct = readSourceProvenanceEntries((report as AnalysisReport & { sourceProvenanceFrame?: unknown } | null)?.sourceProvenanceFrame);
  if (direct) return direct;

  const meta = report?.meta as ReportMeta & { sourceProvenanceFrame?: unknown } | undefined;
  const metaFrame = readSourceProvenanceEntries(meta?.sourceProvenanceFrame);
  if (metaFrame) return metaFrame;

  const details = report?.details as { analysisResult?: UnknownRecord } | undefined;
  return readSourceProvenanceEntries(details?.analysisResult?.sourceProvenanceFrame);
}

function inferEvidenceFromDataQuality(report: DataQualityReport | undefined): string[] {
  if (!report) return ['technical', 'fundamentals', 'news'];
  const evidence: string[] = [];
  if (report.importantMissing?.length) evidence.push('fundamentals');
  if (report.staleSources?.length) evidence.push('freshness');
  if (report.providerTimeouts?.length || report.pendingSources?.length) evidence.push('news');
  return evidence.length ? evidence : ['technical'];
}

export function inferAnalysisResearchReadiness(
  report: DataQualityReport | undefined,
): ResearchReadinessV1 {
  const missingEvidence = inferEvidenceFromDataQuality(report);
  const insufficient = !report || report.requiredAvailable === false || report.dataQualityTier === 'insufficient';
  return {
    researchReady: false,
    readinessState: insufficient ? 'insufficient' : 'observe_only',
    verdictLabel: insufficient ? '证据不足' : '仅观察',
    blockingReasons: insufficient ? ['missing_required_evidence'] : [],
    missingEvidence,
    sourceAuthority: 'unavailable',
    freshnessFloor: report?.staleSources?.length ? 'stale' : 'unknown',
    nextEvidenceNeeded: insufficient
      ? ['补齐关键研究证据后再判断']
      : ['等待明确研究就绪结论后再升级判断'],
  };
}

export function extractMarketResearchReadiness(
  payload: MarketTemperatureResponse | null | undefined,
): ResearchReadinessV1 | null {
  return readNestedResearchReadiness((payload as MarketTemperatureResponse & { researchReadiness?: unknown } | null)?.researchReadiness);
}

export function inferMarketResearchReadiness(
  payload: MarketTemperatureResponse | null | undefined,
): ResearchReadinessV1 {
  const direction = payload?.marketDecisionSemantics?.directionReadiness;
  if (direction) {
    return inferMarketDirectionReadiness(direction, payload);
  }

  const missingEvidence: string[] = [];
  if (payload?.temperatureAvailable === false || payload?.conclusionAllowed === false || payload?.isReliable === false) {
    missingEvidence.push('macro', 'liquidity');
  }
  if (payload?.freshness === 'fallback' || payload?.isFallback) {
    missingEvidence.push('freshness');
  }

  return {
    researchReady: false,
    readinessState: missingEvidence.length ? 'insufficient' : 'observe_only',
    verdictLabel: missingEvidence.length ? '证据不足' : '仅观察',
    blockingReasons: missingEvidence.length ? ['missing_required_evidence'] : [],
    missingEvidence,
    sourceAuthority: payload?.conclusionAllowed === true ? 'observationOnly' : 'unavailable',
    freshnessFloor: typeof payload?.freshness === 'string' ? payload.freshness : 'unknown',
    nextEvidenceNeeded: missingEvidence.length
      ? ['补齐宏观、流动性与时效证据']
      : ['等待研究就绪结论后再升级判断'],
  };
}

function inferMarketDirectionReadiness(
  readiness: MarketDirectionReadiness,
  payload: MarketTemperatureResponse | null | undefined,
): ResearchReadinessV1 {
  const missingEvidence: string[] = [];
  if ((readiness.missingPillars.count || 0) > 0) {
    missingEvidence.push('macro', 'liquidity');
  }
  if (payload?.freshness === 'fallback' || payload?.isFallback) {
    missingEvidence.push('freshness');
  }
  const insufficient = readiness.status === 'data_insufficient';
  return {
    researchReady: false,
    readinessState: insufficient ? 'insufficient' : 'observe_only',
    verdictLabel: insufficient ? '证据不足' : '仅观察',
    blockingReasons: readiness.blockingReasons,
    missingEvidence,
    evidenceCoverage: {
      scoreGradeCount: readiness.scoreGradePillars.count,
      observationOnlyCount: readiness.observationOnlyPillars.count,
      missingCount: readiness.missingPillars.count,
      totalCount:
        readiness.scoreGradePillars.count
        + readiness.observationOnlyPillars.count
        + readiness.missingPillars.count,
    },
    sourceAuthority: 'observationOnly',
    freshnessFloor: typeof payload?.freshness === 'string' ? payload.freshness : 'unknown',
    nextEvidenceNeeded: insufficient
      ? ['补齐方向缺口后再形成研究判断']
      : ['等待更高授权来源后再升级判断'],
  };
}

function deriveScannerSourceAuthority(frame: ScannerContextSignalFrame | null | undefined): ResearchSourceAuthority {
  if (frame?.sourceAuthorityAllowed === true && frame?.scoreContributionAllowed === true) return 'scoreGradeAllowed';
  if (frame?.observationOnly === true || frame?.scoreContributionAllowed === false) return 'observationOnly';
  return 'unavailable';
}

export function inferScannerResearchReadiness(
  runDetail: ScannerRunDetail | null | undefined,
): ResearchReadinessV1 {
  const frame = runDetail?.scannerContextFrame as ScannerContextFrame | undefined;
  const explicit = readNestedResearchReadiness(frame?.marketReadiness);
  if (explicit) return explicit;

  if (!runDetail) {
    return {
      researchReady: false,
      readinessState: 'waiting',
      verdictLabel: '等待证据更新',
      sourceAuthority: 'unavailable',
      freshnessFloor: 'unknown',
      nextEvidenceNeeded: ['先运行一次扫描，获取市场与候选上下文'],
    };
  }

  const selectedCount = runDetail.summary?.selectedCount ?? runDetail.shortlist?.length ?? 0;
  const failedCount = (runDetail.summary?.dataFailedCount ?? 0) + (runDetail.summary?.errorCount ?? 0);
  const insufficient = selectedCount <= 0 && failedCount > 0;
  return {
    researchReady: false,
    readinessState: insufficient ? 'insufficient' : 'observe_only',
    verdictLabel: insufficient ? '证据不足' : '仅观察',
    blockingReasons: insufficient ? ['missing_required_evidence'] : [],
    missingEvidence: insufficient ? ['liquidity', 'source_authority'] : [],
    sourceAuthority: deriveScannerSourceAuthority(frame?.liquidityFrame || frame?.macroRegime),
    freshnessFloor: (frame?.marketReadiness?.freshnessFloor || frame?.liquidityFrame?.freshness || frame?.macroRegime?.freshness || 'unknown') as ResearchFreshnessFloor,
    nextEvidenceNeeded: frame?.marketReadiness?.nextEvidenceNeeded?.length
      ? frame.marketReadiness.nextEvidenceNeeded
      : insufficient
        ? ['补齐市场框架与候选证据后再复核']
        : ['结合市场、流动性与主题框架继续观察'],
  };
}

export function buildScannerTopDownContextView(
  runDetail: ScannerRunDetail | null | undefined,
  locale: ReadinessLocale,
): ScannerTopDownContextView | null {
  if (!runDetail) return null;

  const frame = runDetail.scannerContextFrame as ScannerContextFrame | undefined;
  const posture = deriveScannerContextPosture(frame);
  const macroState = frame?.macroRegime ? normalizeScannerContextPosture(frame.macroRegime.state) : 'insufficient';
  const liquidityState = frame?.liquidityFrame ? normalizeScannerContextPosture(frame.liquidityFrame.state) : 'insufficient';
  const assetState = frame?.assetClassBias ? normalizeScannerContextPosture(frame.assetClassBias.state) : 'insufficient';
  const themeState = frame?.themeFrame ? normalizeScannerContextPosture(frame.themeFrame.state) : 'insufficient';

  return {
    posture,
    postureLabel: localizedScannerContextPostureLabel(posture, locale),
    tone: scannerContextTone(posture),
    summaryLine: buildScannerContextSummaryLine(posture, frame, locale),
    chips: [
      {
        key: 'market',
        label: `${locale === 'en' ? 'Market' : '市场'}：${frame?.marketReadiness
          ? (sanitizeHumanReason(frame.marketReadiness.verdictLabel) || localizedStateLabel(frame.marketReadiness.readinessState, locale))
          : localizedStateLabel('insufficient', locale)}`,
      },
      {
        key: 'macro',
        label: `${locale === 'en' ? 'Macro' : '宏观'}：${localizedSignalStateLabel(macroState, locale)}`,
      },
      {
        key: 'liquidity',
        label: `${locale === 'en' ? 'Liquidity' : '流动性'}：${localizedSignalStateLabel(liquidityState, locale)}`,
      },
      {
        key: 'asset-class',
        label: `${locale === 'en' ? 'Asset bias' : '资产'}：${localizedSignalStateLabel(assetState, locale)}`,
      },
      {
        key: 'theme',
        label: `${locale === 'en' ? 'Theme' : '主题'}：${localizedSignalStateLabel(themeState, locale)}`,
      },
      {
        key: 'universe',
        label: `${locale === 'en' ? 'Universe' : '标的池'}：${localizedUniversePolicyLabel(frame?.universePolicy?.type, locale)}`,
      },
      {
        key: 'boundary',
        label: locale === 'en' ? 'Boundary: research only' : '边界：仅研究观察',
      },
    ],
  };
}

export function extractOptionsResearchReadiness(
  ...payloads: Array<UnknownRecord | null | undefined>
): OptionsResearchReadiness | null {
  for (const payload of payloads) {
    if (!payload) continue;
    const direct = payload.optionsReadiness;
    if (isRecord(direct)) return direct as OptionsResearchReadiness;
    const alias = payload.optionsResearchReadiness;
    if (isRecord(alias)) return alias as OptionsResearchReadiness;
  }
  return null;
}

export function inferOptionsResearchReadiness(
  decision: OptionsDecisionResponse | null | undefined,
): ResearchReadinessV1 {
  if (!decision) {
    return {
      researchReady: false,
      readinessState: 'waiting',
      verdictLabel: '等待证据更新',
      sourceAuthority: 'unavailable',
      freshnessFloor: 'unknown',
      nextEvidenceNeeded: ['等待期权链与情景判断返回'],
    };
  }

  const blocked = decision.gateDecision === 'blocked' || decision.decisionGrade === false;
  return {
    researchReady: false,
    readinessState: blocked ? 'blocked' : 'observe_only',
    verdictLabel: blocked ? '研究结论受限' : '仅观察',
    blockingReasons: uniqueStrings([
      ...asStringArray(decision.failClosedReasonCodes),
      ...asStringArray(decision.gateIssues),
      ...asStringArray(decision.dataQuality?.blockingReasons),
    ]),
    missingEvidence: uniqueStrings([
      decision.ivGreeks?.ivRankStatus === 'unavailable' ? 'technical' : null,
      decision.dataQuality?.dataQualityTier === 'insufficient' ? 'source_authority' : null,
    ]),
    sourceAuthority: blocked ? 'observationOnly' : 'unavailable',
    freshnessFloor: typeof decision.freshness?.freshness === 'string'
      ? decision.freshness.freshness
      : 'unknown',
    nextEvidenceNeeded: blocked
      ? ['补齐 provider authority、Greeks 与流动性证据']
      : ['等待明确研究就绪结论后再升级判断'],
  };
}

export function convertOptionsReadiness(
  readiness: OptionsResearchReadiness | null | undefined,
): ResearchReadinessV1 | null {
  if (!readiness?.readinessState) return null;
  const normalizedState: ResearchReadinessState = readiness.optionsResearchReady === true
    ? 'ready'
    : readiness.readinessState === 'blocked'
      ? 'blocked'
      : readiness.readinessState === 'insufficient'
        ? 'insufficient'
        : readiness.readinessState === 'waiting'
          ? 'waiting'
          : 'observe_only';
  const freshnessFloor: ResearchFreshnessFloor = readiness.dataQualityTier === 'live_usable'
    ? 'live'
    : readiness.dataQualityTier === 'delayed_usable'
      ? 'delayed'
      : readiness.dataQualityTier === 'synthetic_demo_only'
        ? 'synthetic'
        : 'unknown';
  return {
    researchReady: readiness.optionsResearchReady === true,
    readinessState: normalizedState,
    verdictLabel: readiness.optionsResearchReady === true ? '研究证据可用' : undefined,
    blockingReasons: asStringArray(readiness.blockingReasons),
    missingEvidence: [],
    sourceAuthority: readiness.providerAuthority,
    freshnessFloor,
    nextEvidenceNeeded: asStringArray(readiness.nextEvidenceNeeded),
  };
}
