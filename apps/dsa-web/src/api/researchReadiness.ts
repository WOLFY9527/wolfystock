import type {
  AnalysisEvidenceCoverageDomain,
  AnalysisEvidenceCoverageEntry,
  AnalysisEvidenceCoverageFrame,
  AnalysisReport,
  DataQualityReport,
  ReportMeta,
} from '../types/analysis';
import type { MarketDirectionReadiness, MarketTemperatureResponse } from './market';
import type { OptionsDecisionResponse } from './optionsLab';
import type {
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
  return value
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter(Boolean);
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
