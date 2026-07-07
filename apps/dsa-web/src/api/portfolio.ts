import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  PortfolioAccountItem,
  PortfolioAccountCreateRequest,
  PortfolioAccountDeleteResponse,
  PortfolioAccountListResponse,
  PortfolioBrokerConnectionListResponse,
  PortfolioCashLedgerCreateRequest,
  PortfolioCashLedgerListResponse,
  PortfolioCorporateActionCreateRequest,
  PortfolioCorporateActionListResponse,
  PortfolioCostMethod,
  PortfolioDeleteResponse,
  PortfolioEventCreatedResponse,
  PortfolioExposureResearchContext,
  PortfolioFxRefreshResponse,
  PortfolioLiveFxRateResponse,
  PortfolioImportBrokerListResponse,
  PortfolioImportCommitResponse,
  PortfolioImportParseResponse,
  PortfolioIbkrSyncRequest,
  PortfolioIbkrSyncResponse,
  PortfolioRiskExposureReadiness,
  PortfolioRiskExposureReadinessItem,
  PortfolioRiskExposureReadinessState,
  PortfolioRiskResponse,
  PortfolioScenarioRiskAppliedShock,
  PortfolioScenarioRiskBucketContribution,
  PortfolioScenarioRiskCoverage,
  PortfolioScenarioRiskMetadata,
  PortfolioScenarioRiskMissingCoverage,
  PortfolioScenarioRiskPositionContribution,
  PortfolioScenarioRiskRequest,
  PortfolioScenarioRiskResponse,
  PortfolioScenarioRiskScenarioInput,
  PortfolioScenarioRiskScenarioResult,
  PortfolioScenarioRiskShockValueInput,
  PortfolioSnapshotResponse,
  PortfolioStructureReviewDataQuality,
  PortfolioStructureReviewDegradedLinkage,
  PortfolioStructureReviewEvidenceLinkage,
  PortfolioStructureReviewHolding,
  PortfolioStructureReviewHoldingDrilldown,
  PortfolioStructureReviewLinkTarget,
  PortfolioStructureReviewMissingEvidenceItem,
  PortfolioStructureReviewResearchLinkage,
  PortfolioStructureReviewResearchNotes,
  PortfolioStructureReviewResponse,
  PortfolioTradeCreateRequest,
  PortfolioTradeListResponse,
  PortfolioTradeListItem,
  PortfolioTradeUpdateRequest,
} from '../types/portfolio';

type SnapshotQuery = {
  accountId?: number;
  asOf?: string;
  costMethod?: PortfolioCostMethod;
};

type FxRefreshQuery = {
  accountId?: number;
  asOf?: string;
};

type StructureReviewQuery = SnapshotQuery & {
  benchmark?: string;
  maxItems?: number;
};

type FxRateQuery = {
  base: string;
  quote: string;
};

type EventQuery = {
  accountId?: number;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
};

type TradeListQuery = EventQuery & {
  symbol?: string;
  side?: 'buy' | 'sell';
  includeVoided?: boolean;
};

type CashListQuery = EventQuery & {
  direction?: 'in' | 'out';
};

type CorporateListQuery = EventQuery & {
  symbol?: string;
  actionType?: 'cash_dividend' | 'split_adjustment';
};

type LineageChipVariant = 'neutral' | 'success' | 'caution' | 'danger' | 'info';

const LINEAGE_RECOVERY_KEY = ['fall', 'back'].join('');
const LINEAGE_LIST_KEYS = ['available', 'missing', 'stale', 'delayed', LINEAGE_RECOVERY_KEY] as const;
const FX_LINEAGE_LIST_KEYS = ['available', 'missing', 'stale', LINEAGE_RECOVERY_KEY, 'identity'] as const;

export type PortfolioLineageCounts = Record<string, number>;
export type PortfolioLineageListMap = Record<string, string[]>;

export interface PortfolioPriceLineage {
  status?: string;
  scoreAuthority?: string;
  counts: PortfolioLineageCounts;
  affectedSymbols: PortfolioLineageListMap;
  lastUpdatedAt?: string | null;
}

export interface PortfolioFxLineage {
  status?: string;
  scoreAuthority?: string;
  counts: PortfolioLineageCounts;
  affectedCurrencies: PortfolioLineageListMap;
  affectedPairs: PortfolioLineageListMap;
  lastUpdatedAt?: string | null;
}

export interface PortfolioValuationSnapshotLineage {
  status?: string;
  scoreAuthority?: string;
  snapshotState?: string;
  metricsReady?: boolean;
  positionCount?: number;
  completePositionCount?: number;
  partialPositionCount?: number;
  blockedPositionCount?: number;
  blockedBy: {
    priceSymbols: string[];
    fxPairs: string[];
    fxCurrencies: string[];
  };
  lastUpdatedAt?: string | null;
}

export interface PortfolioAnalyticsReadiness {
  valuation?: string;
  risk?: string;
  scoreAuthority?: string;
  observationOnly?: boolean;
  affectedSymbols: string[];
  affectedCurrencies: string[];
}

export interface PortfolioLineageStatusSummary {
  label: string;
  variant: LineageChipVariant;
  detail: string;
  count: number;
  total: number;
  affectedSymbols: string[];
  affectedCurrencies: string[];
  affectedPairs: string[];
  lastUpdatedAt?: string | null;
}

export interface PortfolioLineageSummary {
  hasLineage: boolean;
  authoritative: boolean;
  observationOnly: boolean;
  price: PortfolioLineageStatusSummary;
  fx: PortfolioLineageStatusSummary;
  snapshot: PortfolioLineageStatusSummary;
  analytics: PortfolioLineageStatusSummary;
}

export type PortfolioSnapshotWithLineage = PortfolioSnapshotResponse & {
  priceLineage?: PortfolioPriceLineage;
  fxLineage?: PortfolioFxLineage;
  valuationSnapshotLineage?: PortfolioValuationSnapshotLineage;
  analyticsReadiness?: PortfolioAnalyticsReadiness;
  portfolioLineageSummary: PortfolioLineageSummary;
};

function buildSnapshotParams(query: SnapshotQuery): Record<string, string | number> {
  const params: Record<string, string | number> = {};
  if (query.accountId != null) {
    params.account_id = query.accountId;
  }
  if (query.asOf) {
    params.as_of = query.asOf;
  }
  if (query.costMethod) {
    params.cost_method = query.costMethod;
  }
  return params;
}

function buildFxRefreshParams(query: FxRefreshQuery): Record<string, string | number> {
  const params: Record<string, string | number> = {};
  if (query.accountId != null) {
    params.account_id = query.accountId;
  }
  if (query.asOf) {
    params.as_of = query.asOf;
  }
  return params;
}

function buildStructureReviewParams(query: StructureReviewQuery): Record<string, string | number> {
  const params = buildSnapshotParams(query);
  if (query.benchmark) {
    params.benchmark = query.benchmark;
  }
  if (query.maxItems != null) {
    params.max_items = query.maxItems;
  }
  return params;
}

function buildEventParams(query: EventQuery): Record<string, string | number> {
  const params: Record<string, string | number> = {};
  if (query.accountId != null) {
    params.account_id = query.accountId;
  }
  if (query.dateFrom) {
    params.date_from = query.dateFrom;
  }
  if (query.dateTo) {
    params.date_to = query.dateTo;
  }
  if (query.page != null) {
    params.page = query.page;
  }
  if (query.pageSize != null) {
    params.page_size = query.pageSize;
  }
  return params;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function pickString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value === 'string') {
      return value;
    }
  }
  return undefined;
}

function pickNumber(...values: unknown[]): number | undefined {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
  }
  return undefined;
}

function pickBoolean(...values: unknown[]): boolean | undefined {
  for (const value of values) {
    if (typeof value === 'boolean') {
      return value;
    }
  }
  return undefined;
}

function pickStringArray(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  return value.filter((item): item is string => typeof item === 'string');
}

function normalizeNumberMap(value: unknown, keys: readonly string[]): PortfolioLineageCounts {
  const data = isRecord(value) ? value : {};
  return Object.fromEntries(
    keys.flatMap((key) => {
      const item = pickNumber(data[key]);
      return item === undefined ? [] : [[key, item]];
    }),
  );
}

function normalizeStringListMap(value: unknown, keys: readonly string[]): PortfolioLineageListMap {
  const data = isRecord(value) ? value : {};
  return Object.fromEntries(
    keys.map((key) => [key, pickStringArray(data[key]) ?? []]),
  );
}

function listUnion(...values: Array<string[] | undefined>): string[] {
  return Array.from(new Set(values.flatMap((items) => items ?? []).filter(Boolean))).sort();
}

function sumCounts(counts: PortfolioLineageCounts, keys: readonly string[]): number {
  return keys.reduce((sum, key) => sum + (counts[key] ?? 0), 0);
}

function normalizePriceLineage(value: unknown): PortfolioPriceLineage | undefined {
  if (!isRecord(value)) {
    return undefined;
  }
  return {
    status: pickString(value.status),
    scoreAuthority: pickString(value.scoreAuthority),
    counts: normalizeNumberMap(value.counts, ['total', ...LINEAGE_LIST_KEYS]),
    affectedSymbols: normalizeStringListMap(value.affectedSymbols, LINEAGE_LIST_KEYS),
    lastUpdatedAt: normalizeNullableString(value.lastUpdatedAt) ?? undefined,
  };
}

function normalizeFxLineage(value: unknown): PortfolioFxLineage | undefined {
  if (!isRecord(value)) {
    return undefined;
  }
  return {
    status: pickString(value.status),
    scoreAuthority: pickString(value.scoreAuthority),
    counts: normalizeNumberMap(value.counts, ['total', ...FX_LINEAGE_LIST_KEYS]),
    affectedCurrencies: normalizeStringListMap(value.affectedCurrencies, FX_LINEAGE_LIST_KEYS),
    affectedPairs: normalizeStringListMap(value.affectedPairs, FX_LINEAGE_LIST_KEYS),
    lastUpdatedAt: normalizeNullableString(value.lastUpdatedAt) ?? undefined,
  };
}

function normalizeValuationSnapshotLineage(value: unknown): PortfolioValuationSnapshotLineage | undefined {
  if (!isRecord(value)) {
    return undefined;
  }
  const blockedBy = normalizeStringRecord(value.blockedBy);
  return {
    status: pickString(value.status),
    scoreAuthority: pickString(value.scoreAuthority),
    snapshotState: pickString(value.snapshotState),
    metricsReady: pickBoolean(value.metricsReady),
    positionCount: pickNumber(value.positionCount),
    completePositionCount: pickNumber(value.completePositionCount),
    partialPositionCount: pickNumber(value.partialPositionCount),
    blockedPositionCount: pickNumber(value.blockedPositionCount),
    blockedBy: {
      priceSymbols: pickStringArray(blockedBy.priceSymbols) ?? [],
      fxPairs: pickStringArray(blockedBy.fxPairs) ?? [],
      fxCurrencies: pickStringArray(blockedBy.fxCurrencies) ?? [],
    },
    lastUpdatedAt: normalizeNullableString(value.lastUpdatedAt) ?? undefined,
  };
}

function normalizeAnalyticsReadiness(value: unknown): PortfolioAnalyticsReadiness | undefined {
  if (!isRecord(value)) {
    return undefined;
  }
  return {
    valuation: pickString(value.valuation),
    risk: pickString(value.risk),
    scoreAuthority: pickString(value.scoreAuthority),
    observationOnly: pickBoolean(value.observationOnly),
    affectedSymbols: pickStringArray(value.affectedSymbols) ?? [],
    affectedCurrencies: pickStringArray(value.affectedCurrencies) ?? [],
  };
}

function lineageDetail(parts: string[], count: number, total: number): string {
  const visibleParts = parts.slice(0, 3).join(', ');
  const countText = total > 0 ? `${count}/${total}` : `${count}`;
  return visibleParts ? `${visibleParts} · ${countText}` : countText;
}

function buildDefaultLineageStatus(label: string, variant: LineageChipVariant = 'neutral'): PortfolioLineageStatusSummary {
  return {
    label,
    variant,
    detail: '0',
    count: 0,
    total: 0,
    affectedSymbols: [],
    affectedCurrencies: [],
    affectedPairs: [],
  };
}

function buildLineageSummary(
  priceLineage?: PortfolioPriceLineage,
  fxLineage?: PortfolioFxLineage,
  valuationSnapshotLineage?: PortfolioValuationSnapshotLineage,
  analyticsReadiness?: PortfolioAnalyticsReadiness,
): PortfolioLineageSummary {
  const hasLineage = Boolean(priceLineage || fxLineage || valuationSnapshotLineage || analyticsReadiness);
  const priceToken = String(priceLineage?.status || '').toLowerCase();
  const fxToken = String(fxLineage?.status || '').toLowerCase();
  const snapshotToken = String(valuationSnapshotLineage?.status || '').toLowerCase();
  const analyticsRiskToken = String(analyticsReadiness?.risk || '').toLowerCase();
  const authoritative = Boolean(
    hasLineage
      && priceLineage?.scoreAuthority === 'authoritative'
      && fxLineage?.scoreAuthority === 'authoritative'
      && valuationSnapshotLineage?.scoreAuthority === 'authoritative'
      && analyticsReadiness?.scoreAuthority === 'authoritative',
  );
  const observationOnly = hasLineage ? !authoritative || analyticsReadiness?.observationOnly === true : true;

  const priceAffected = priceLineage
    ? listUnion(
      priceLineage.affectedSymbols.missing,
      priceLineage.affectedSymbols.stale,
      priceLineage.affectedSymbols.delayed,
      priceLineage.affectedSymbols[LINEAGE_RECOVERY_KEY],
      priceToken === 'available' ? priceLineage.affectedSymbols.available : [],
    )
    : [];
  const priceCount = priceLineage
    ? (priceToken === 'available'
      ? priceLineage.counts.available ?? priceAffected.length
      : sumCounts(priceLineage.counts, ['missing', 'stale', 'delayed', LINEAGE_RECOVERY_KEY]) || priceAffected.length)
    : 0;
  const priceTotal = priceLineage?.counts.total ?? priceAffected.length;
  const priceLabel = priceToken === 'available'
    ? '价格可用'
    : priceToken === 'stale'
      ? '价格延迟'
      : '价格缺失';
  const price = priceLineage
    ? {
      label: priceLabel,
      variant: (priceToken === 'available' ? 'success' : priceToken === 'stale' ? 'caution' : 'danger') as LineageChipVariant,
      detail: lineageDetail(priceAffected, priceCount, priceTotal),
      count: priceCount,
      total: priceTotal,
      affectedSymbols: priceAffected,
      affectedCurrencies: [],
      affectedPairs: [],
      lastUpdatedAt: priceLineage.lastUpdatedAt,
    }
    : buildDefaultLineageStatus('价格缺失', 'danger');

  const fxAffectedCurrencies = fxLineage
    ? listUnion(
      fxLineage.affectedCurrencies.missing,
      fxLineage.affectedCurrencies.stale,
      fxLineage.affectedCurrencies[LINEAGE_RECOVERY_KEY],
      fxToken === 'available' ? fxLineage.affectedCurrencies.available : [],
    )
    : [];
  const fxAffectedPairs = fxLineage
    ? listUnion(
      fxLineage.affectedPairs.missing,
      fxLineage.affectedPairs.stale,
      fxLineage.affectedPairs[LINEAGE_RECOVERY_KEY],
      fxToken === 'available' ? fxLineage.affectedPairs.available : [],
    )
    : [];
  const fxCount = fxLineage
    ? (fxToken === 'available'
      ? fxLineage.counts.available ?? fxAffectedCurrencies.length
      : sumCounts(fxLineage.counts, ['missing', 'stale', LINEAGE_RECOVERY_KEY]) || fxAffectedCurrencies.length)
    : 0;
  const fxTotal = fxLineage?.counts.total ?? fxAffectedCurrencies.length;
  const fx = fxLineage
    ? {
      label: fxToken === 'available' ? '汇率已确认' : fxToken === 'stale' ? '汇率待确认' : '汇率缺失',
      variant: (fxToken === 'available' ? 'success' : fxToken === 'stale' ? 'caution' : 'danger') as LineageChipVariant,
      detail: lineageDetail(fxAffectedCurrencies, fxCount, fxTotal),
      count: fxCount,
      total: fxTotal,
      affectedSymbols: [],
      affectedCurrencies: fxAffectedCurrencies,
      affectedPairs: fxAffectedPairs,
      lastUpdatedAt: fxLineage.lastUpdatedAt,
    }
    : buildDefaultLineageStatus('汇率缺失', 'danger');

  const snapshotAffectedSymbols = valuationSnapshotLineage?.blockedBy.priceSymbols ?? [];
  const snapshotAffectedCurrencies = valuationSnapshotLineage?.blockedBy.fxCurrencies ?? [];
  const snapshotAffectedPairs = valuationSnapshotLineage?.blockedBy.fxPairs ?? [];
  const snapshotCount = valuationSnapshotLineage
    ? (valuationSnapshotLineage.completePositionCount ?? 0)
      + (valuationSnapshotLineage.partialPositionCount ?? 0)
      + (valuationSnapshotLineage.blockedPositionCount ?? 0)
    : 0;
  const snapshotTotal = valuationSnapshotLineage?.positionCount ?? snapshotCount;
  const snapshotLabel = snapshotToken === 'complete'
    ? '估值完整'
    : snapshotToken === 'partial'
      ? '估值部分可用'
      : '估值不可用';
  const snapshot = valuationSnapshotLineage
    ? {
      label: snapshotLabel,
      variant: (snapshotToken === 'complete' ? 'success' : snapshotToken === 'partial' ? 'caution' : 'danger') as LineageChipVariant,
      detail: lineageDetail(listUnion(snapshotAffectedSymbols, snapshotAffectedCurrencies), snapshotCount, snapshotTotal),
      count: snapshotCount,
      total: snapshotTotal,
      affectedSymbols: snapshotAffectedSymbols,
      affectedCurrencies: snapshotAffectedCurrencies,
      affectedPairs: snapshotAffectedPairs,
      lastUpdatedAt: valuationSnapshotLineage.lastUpdatedAt,
    }
    : buildDefaultLineageStatus('估值不可用', 'danger');

  const analyticsCount = analyticsReadiness
    ? Math.max(analyticsReadiness.affectedSymbols.length, analyticsReadiness.affectedCurrencies.length, snapshotTotal)
    : 0;
  const analyticsTotal = snapshotTotal || analyticsCount;
  const analyticsLabel = !analyticsReadiness || analyticsRiskToken === 'blocked'
    ? '风险视图待生成'
    : observationOnly
      ? '仅观察'
      : '风险视图可用';
  const analytics = analyticsReadiness
    ? {
      label: analyticsLabel,
      variant: (analyticsLabel === '风险视图可用' ? 'success' : analyticsLabel === '仅观察' ? 'info' : 'neutral') as LineageChipVariant,
      detail: lineageDetail(listUnion(analyticsReadiness.affectedSymbols, analyticsReadiness.affectedCurrencies), analyticsCount, analyticsTotal),
      count: analyticsCount,
      total: analyticsTotal,
      affectedSymbols: analyticsReadiness.affectedSymbols,
      affectedCurrencies: analyticsReadiness.affectedCurrencies,
      affectedPairs: [],
    }
    : buildDefaultLineageStatus('风险视图待生成');

  return {
    hasLineage,
    authoritative,
    observationOnly,
    price,
    fx,
    snapshot,
    analytics,
  };
}

const STRUCTURE_REVIEW_FORBIDDEN_KEYS = new Set(['provider', 'debugTrace', 'structureDecisionRoute']);

function stripStructureReviewUnsafeKeys<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((entry) => stripStructureReviewUnsafeKeys(entry)) as T;
  }
  if (!isRecord(value)) {
    return value;
  }

  return Object.fromEntries(
    Object.entries(value).flatMap(([key, entry]) => {
      if (STRUCTURE_REVIEW_FORBIDDEN_KEYS.has(key)) {
        return [];
      }
      return [[key, stripStructureReviewUnsafeKeys(entry)]];
    }),
  ) as T;
}

function normalizeStructureReviewResearchNotes(value: unknown): PortfolioStructureReviewResearchNotes {
  const data = isRecord(value) ? value : {};
  return {
    watchNext: pickStringArray(data.watchNext) ?? [],
    needsMoreEvidence: pickStringArray(data.needsMoreEvidence) ?? [],
    riskFlags: pickStringArray(data.riskFlags) ?? [],
  };
}

function normalizeStructureReviewMissingEvidence(value: unknown): PortfolioStructureReviewMissingEvidenceItem[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((entry) => {
    if (!isRecord(entry)) {
      return [];
    }

    const kind = pickString(entry.kind);
    const message = pickString(entry.message);
    if (!kind || !message) {
      return [];
    }

    return [{ kind, message }];
  });
}

function normalizeStructureReviewLinkageStatus(value: unknown): 'available' | 'degraded' | 'unavailable' | undefined {
  return value === 'available' || value === 'degraded' || value === 'unavailable' ? value : undefined;
}

function normalizeStructureReviewLinkTargets(value: unknown): PortfolioStructureReviewLinkTarget[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((entry) => {
    if (!isRecord(entry)) {
      return [];
    }

    const label = pickString(entry.label);
    const route = pickString(entry.route);
    const section = pickString(entry.section);
    const reason = pickString(entry.reason);
    if (!label || !route || !section || !reason) {
      return [];
    }

    return [{ label, route, section, reason }];
  });
}

function normalizeStructureReviewDegradedLinkage(value: unknown): PortfolioStructureReviewDegradedLinkage[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((entry) => {
    if (!isRecord(entry)) {
      return [];
    }

    const surface = pickString(entry.surface);
    const status = normalizeStructureReviewLinkageStatus(entry.status);
    const reason = pickString(entry.reason);
    const message = pickString(entry.message);
    if (!surface || !status || status === 'available' || !reason || !message) {
      return [];
    }

    return [{ surface, status, reason, message }];
  });
}

function normalizeStructureReviewEvidenceLinkage(value: unknown): PortfolioStructureReviewEvidenceLinkage | undefined {
  const data = isRecord(value) ? value : {};
  const status = normalizeStructureReviewLinkageStatus(data.status);
  if (!status) {
    return undefined;
  }

  return {
    status,
    availableHoldings: pickNumber(data.availableHoldings) ?? 0,
    degradedHoldings: pickNumber(data.degradedHoldings) ?? 0,
    unavailableHoldings: pickNumber(data.unavailableHoldings) ?? 0,
  };
}

function normalizeStructureReviewHoldingDrilldowns(value: unknown): PortfolioStructureReviewHoldingDrilldown[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((entry) => {
    if (!isRecord(entry)) {
      return [];
    }

    const ticker = pickString(entry.ticker);
    const evidenceLinkage = normalizeStructureReviewLinkageStatus(entry.evidenceLinkage);
    if (!ticker || !evidenceLinkage) {
      return [];
    }

    return [{
      ticker,
      structureLinks: normalizeStructureReviewLinkTargets(entry.structureLinks),
      radarLinks: normalizeStructureReviewLinkTargets(entry.radarLinks),
      watchlistLinks: normalizeStructureReviewLinkTargets(entry.watchlistLinks),
      scenarioLinks: normalizeStructureReviewLinkTargets(entry.scenarioLinks),
      evidenceLinkage,
      degradedLinkage: normalizeStructureReviewDegradedLinkage(entry.degradedLinkage),
    }];
  });
}

function normalizeStructureReviewResearchLinkage(value: unknown): PortfolioStructureReviewResearchLinkage | undefined {
  if (!isRecord(value)) {
    return undefined;
  }

  const status = normalizeStructureReviewLinkageStatus(value.status);
  const evidenceLinkage = normalizeStructureReviewEvidenceLinkage(value.evidenceLinkage);
  if (!status || !evidenceLinkage) {
    return undefined;
  }

  return {
    status,
    holdingDrilldowns: normalizeStructureReviewHoldingDrilldowns(value.holdingDrilldowns),
    structureLinks: normalizeStructureReviewLinkTargets(value.structureLinks),
    radarLinks: normalizeStructureReviewLinkTargets(value.radarLinks),
    watchlistLinks: normalizeStructureReviewLinkTargets(value.watchlistLinks),
    scenarioLinks: normalizeStructureReviewLinkTargets(value.scenarioLinks),
    evidenceLinkage,
    degradedLinkage: normalizeStructureReviewDegradedLinkage(value.degradedLinkage),
  };
}

function normalizeStructureReviewConsumerIssues(value: unknown): PortfolioStructureReviewResponse['consumerIssues'] {
  if (!Array.isArray(value)) {
    return undefined;
  }

  const issues = value.flatMap((entry) => {
    if (!isRecord(entry)) {
      return [];
    }

    const label = pickString(entry.label);
    const message = pickString(entry.message);
    const severity = pickString(entry.severity);
    const category = pickString(entry.category);
    if (!label || !message || !severity || !category) {
      return [];
    }

    return [{ label, message, severity, category }];
  });

  return issues.length ? issues : [];
}

function normalizeStructureReviewHolding(value: unknown): PortfolioStructureReviewHolding[] {
  if (!isRecord(value)) {
    return [];
  }

  const ticker = pickString(value.ticker);
  const structureState = pickString(value.structureState);
  const confidence = pickString(value.confidence);
  if (!ticker || !structureState || !confidence) {
    return [];
  }

  return [{
    ticker,
    structureState,
    confidence: confidence === 'high' || confidence === 'medium' || confidence === 'low' ? confidence : 'low',
    evidenceQuality: isRecord(value.evidenceQuality)
      ? stripStructureReviewUnsafeKeys(value.evidenceQuality)
      : {},
    riskFlags: pickStringArray(value.riskFlags) ?? [],
    researchNotes: normalizeStructureReviewResearchNotes(value.researchNotes),
    missingEvidence: normalizeStructureReviewMissingEvidence(value.missingEvidence),
  }];
}

function normalizeStructureReviewDataQuality(value: unknown): PortfolioStructureReviewDataQuality {
  const data = isRecord(value) ? value : {};
  return Object.fromEntries(
    Object.entries({
      status: pickString(data.status),
      holdingMetadataStatus: pickString(data.holdingMetadataStatus),
      structureEvidenceStatus: pickString(data.structureEvidenceStatus),
      readOnly: pickBoolean(data.readOnly),
      failClosed: pickBoolean(data.failClosed),
    }).filter(([, entry]) => entry !== undefined),
  ) as PortfolioStructureReviewDataQuality;
}

function normalizeStringRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function normalizeNullableString(value: unknown): string | null | undefined {
  return typeof value === 'string' ? value : value === null ? null : undefined;
}

function normalizeNullableNumber(value: unknown): number | null | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : value === null ? null : undefined;
}

function normalizeExposureResearchDominantExposure(value: unknown): PortfolioExposureResearchContext['dominantExposure'] {
  const data = normalizeStringRecord(value);
  const type = pickString(data.type);
  const normalized: PortfolioExposureResearchContext['dominantExposure'] = {
    type: type === 'position' || type === 'currency' || type === 'market' || type === 'none' ? type : 'none',
  };
  const symbol = normalizeNullableString(data.symbol);
  const label = normalizeNullableString(data.label);
  const market = normalizeNullableString(data.market);
  const currency = normalizeNullableString(data.currency);
  const marketValue = normalizeNullableNumber(data.marketValue);
  const weightPct = normalizeNullableNumber(data.weightPct);
  const fxStatus = normalizeNullableString(data.fxStatus);
  if (symbol !== undefined) normalized.symbol = symbol;
  if (label !== undefined) normalized.label = label;
  if (market !== undefined) normalized.market = market;
  if (currency !== undefined) normalized.currency = currency;
  if (marketValue !== undefined) normalized.marketValue = marketValue;
  if (weightPct !== undefined) normalized.weightPct = weightPct;
  if (fxStatus !== undefined) normalized.fxStatus = fxStatus;
  return normalized;
}

function normalizeExposureResearchConcentrationContext(value: unknown): PortfolioExposureResearchContext['concentrationContext'] {
  const data = normalizeStringRecord(value);
  return Object.fromEntries(
    Object.entries({
      state: normalizeNullableString(data.state),
      topWeightPct: normalizeNullableNumber(data.topWeightPct),
      alert: pickBoolean(data.alert),
      holdingCount: normalizeNullableNumber(data.holdingCount),
      accountCount: normalizeNullableNumber(data.accountCount),
      dominantType: normalizeNullableString(data.dominantType),
      dominantLabel: normalizeNullableString(data.dominantLabel),
    }).filter(([, entry]) => entry !== undefined),
  ) as PortfolioExposureResearchContext['concentrationContext'];
}

function normalizeExposureResearchCurrencyContext(value: unknown): PortfolioExposureResearchContext['currencyContext'] {
  const data = normalizeStringRecord(value);
  const largestCurrency = normalizeStringRecord(data.largestCurrency);
  return Object.fromEntries(
    Object.entries({
      state: normalizeNullableString(data.state),
      baseCurrency: normalizeNullableString(data.baseCurrency),
      fxFreshnessState: normalizeNullableString(data.fxFreshnessState),
      largestCurrency: Object.keys(largestCurrency).length
        ? Object.fromEntries(
          Object.entries({
            currency: normalizeNullableString(largestCurrency.currency),
            label: normalizeNullableString(largestCurrency.label),
            weightPct: normalizeNullableNumber(largestCurrency.weightPct),
            fxStatus: normalizeNullableString(largestCurrency.fxStatus),
          }).filter(([, entry]) => entry !== undefined),
        )
        : null,
      stalePairs: pickStringArray(data.stalePairs) ?? [],
    }).filter(([, entry]) => entry !== undefined),
  ) as PortfolioExposureResearchContext['currencyContext'];
}

function normalizeExposureResearchMarketContext(value: unknown): PortfolioExposureResearchContext['marketContext'] {
  const data = normalizeStringRecord(value);
  const largestMarket = normalizeStringRecord(data.largestMarket);
  const marketBreakdown = Array.isArray(data.marketBreakdown)
    ? data.marketBreakdown.flatMap((entry) => {
      if (!isRecord(entry)) {
        return [];
      }
      return [Object.fromEntries(
        Object.entries({
          market: normalizeNullableString(entry.market),
          weightPct: normalizeNullableNumber(entry.weightPct),
          positionCount: normalizeNullableNumber(entry.positionCount),
        }).filter(([, item]) => item !== undefined),
      )];
    })
    : [];

  return Object.fromEntries(
    Object.entries({
      state: normalizeNullableString(data.state),
      largestMarket: Object.keys(largestMarket).length
        ? Object.fromEntries(
          Object.entries({
            market: normalizeNullableString(largestMarket.market),
            label: normalizeNullableString(largestMarket.label),
            weightPct: normalizeNullableNumber(largestMarket.weightPct),
          }).filter(([, entry]) => entry !== undefined),
        )
        : null,
      marketBreakdown,
      benchmarkMappingState: normalizeNullableString(data.benchmarkMappingState),
      factorMappingState: normalizeNullableString(data.factorMappingState),
      sectorContextState: normalizeNullableString(data.sectorContextState),
    }).filter(([, entry]) => entry !== undefined),
  ) as PortfolioExposureResearchContext['marketContext'];
}

function normalizeExposureResearchStaleInputs(value: unknown): PortfolioExposureResearchContext['staleInputs'] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((entry) => {
    if (!isRecord(entry)) {
      return [];
    }
    const input = pickString(entry.input);
    if (!input) {
      return [];
    }
    const normalized: PortfolioExposureResearchContext['staleInputs'][number] = { input };
    const status = normalizeNullableString(entry.status);
    const reason = normalizeNullableString(entry.reason);
    if (status !== undefined) normalized.status = status;
    if (reason !== undefined) normalized.reason = reason;
    return [normalized];
  });
}

function normalizeExposureResearchNextSteps(value: unknown): PortfolioExposureResearchContext['researchNextSteps'] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((entry) => {
    if (!isRecord(entry)) {
      return [];
    }
    const topic = pickString(entry.topic);
    if (!topic) {
      return [];
    }
    const normalized: PortfolioExposureResearchContext['researchNextSteps'][number] = { topic };
    const check = normalizeNullableString(entry.check);
    if (check !== undefined) normalized.check = check;
    return [normalized];
  });
}

function normalizeExposureResearchObservationBoundary(value: unknown): PortfolioExposureResearchContext['observationBoundary'] {
  const data = normalizeStringRecord(value);
  return Object.fromEntries(
    Object.entries({
      observationOnly: pickBoolean(data.observationOnly),
      decisionGrade: pickBoolean(data.decisionGrade),
      accountingMutation: pickBoolean(data.accountingMutation),
      portfolioMutation: pickBoolean(data.portfolioMutation),
      adviceBoundary: normalizeNullableString(data.adviceBoundary),
      message: normalizeNullableString(data.message),
    }).filter(([, entry]) => entry !== undefined),
  ) as PortfolioExposureResearchContext['observationBoundary'];
}

function normalizeExposureResearchContext(value: unknown): PortfolioExposureResearchContext | undefined {
  if (value == null) {
    return undefined;
  }
  const data = toCamelCase<Record<string, unknown>>(value);
  if (!isRecord(data)) {
    return undefined;
  }

  return {
    dominantExposure: normalizeExposureResearchDominantExposure(data.dominantExposure),
    concentrationContext: normalizeExposureResearchConcentrationContext(data.concentrationContext),
    currencyContext: normalizeExposureResearchCurrencyContext(data.currencyContext),
    marketContext: normalizeExposureResearchMarketContext(data.marketContext),
    staleInputs: normalizeExposureResearchStaleInputs(data.staleInputs),
    evidenceGaps: pickStringArray(data.evidenceGaps) ?? [],
    observationBoundary: normalizeExposureResearchObservationBoundary(data.observationBoundary),
    researchNextSteps: normalizeExposureResearchNextSteps(data.researchNextSteps),
  };
}

const READINESS_STATES: PortfolioRiskExposureReadinessState[] = [
  'available',
  'missing',
  'stale',
  'not_configured',
  'broker_disabled',
  'manual_only',
];

const READINESS_BLOCKERS = new Set([
  'portfolio_account',
  'portfolio_positions',
  'portfolio_metrics',
  'valuation_inputs',
  'freshness',
  'fx_freshness',
  'position_lineage',
  'cash_ledger',
  'sector_exposure',
  'benchmark_mapping',
  'factor_mapping',
  'liquidity_volatility_window',
  'broker_disabled',
]);

function normalizeReadinessState(value: unknown): PortfolioRiskExposureReadinessState {
  const token = String(value || '').trim().toLowerCase();
  return READINESS_STATES.includes(token as PortfolioRiskExposureReadinessState)
    ? token as PortfolioRiskExposureReadinessState
    : 'missing';
}

function normalizeReadinessBlockers(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim().toLowerCase())
    .filter((item, index, items) => READINESS_BLOCKERS.has(item) && items.indexOf(item) === index);
}

function normalizeReadinessItem(value: unknown): PortfolioRiskExposureReadinessItem {
  const data = isRecord(value) ? value : {};
  return {
    state: normalizeReadinessState(data.state),
    reason: pickString(data.reason) ?? '',
    blockers: normalizeReadinessBlockers(data.blockers),
    asOf: normalizeNullableString(data.asOf),
  };
}

function normalizeRiskExposureReadiness(value: unknown): PortfolioRiskExposureReadiness | undefined {
  if (value == null) {
    return undefined;
  }
  const data = toCamelCase<Record<string, unknown>>(value);
  if (!isRecord(data)) {
    return undefined;
  }
  const categories = normalizeStringRecord(data.exposureCategories);
  return {
    contractVersion: 'portfolio_risk_exposure_readiness_v1',
    observationOnly: true,
    decisionGrade: false,
    noAdviceDisclosure: pickString(data.noAdviceDisclosure) ?? '',
    freshnessStatus: pickString(data.freshnessStatus) ?? '',
    holdings: normalizeReadinessItem(data.holdings),
    exposureCategories: {
      sectorExposure: normalizeReadinessItem(categories.sectorExposure),
      singleNameConcentration: normalizeReadinessItem(categories.singleNameConcentration),
      currencyExposure: normalizeReadinessItem(categories.currencyExposure),
      factorStyleExposure: normalizeReadinessItem(categories.factorStyleExposure),
      liquidityVolatilityExposure: normalizeReadinessItem(categories.liquidityVolatilityExposure),
      benchmarkComparison: normalizeReadinessItem(categories.benchmarkComparison),
    },
    benchmarkAvailability: normalizeReadinessItem(data.benchmarkAvailability),
    blockers: normalizeReadinessBlockers(data.blockers),
  };
}

function normalizePortfolioSnapshotResponse(data: unknown): PortfolioSnapshotWithLineage {
  const normalized = toCamelCase<Record<string, unknown>>(data);
  const priceLineage = normalizePriceLineage(isRecord(normalized) ? normalized.priceLineage : undefined);
  const fxLineage = normalizeFxLineage(isRecord(normalized) ? normalized.fxLineage : undefined);
  const valuationSnapshotLineage = normalizeValuationSnapshotLineage(
    isRecord(normalized) ? normalized.valuationSnapshotLineage : undefined,
  );
  const analyticsReadiness = normalizeAnalyticsReadiness(isRecord(normalized) ? normalized.analyticsReadiness : undefined);
  const snapshotFields = { ...normalized };
  delete snapshotFields.priceLineage;
  delete snapshotFields.fxLineage;
  delete snapshotFields.valuationSnapshotLineage;
  delete snapshotFields.analyticsReadiness;
  delete snapshotFields.portfolioLineageSummary;
  delete snapshotFields.riskExposureReadiness;
  return {
    ...snapshotFields,
    exposureResearchContext: normalizeExposureResearchContext(
      isRecord(normalized) ? normalized.exposureResearchContext : undefined,
    ),
    riskExposureReadiness: normalizeRiskExposureReadiness(
      isRecord(normalized) ? normalized.riskExposureReadiness : undefined,
    ),
    ...(priceLineage ? { priceLineage } : {}),
    ...(fxLineage ? { fxLineage } : {}),
    ...(valuationSnapshotLineage ? { valuationSnapshotLineage } : {}),
    ...(analyticsReadiness ? { analyticsReadiness } : {}),
    portfolioLineageSummary: buildLineageSummary(
      priceLineage,
      fxLineage,
      valuationSnapshotLineage,
      analyticsReadiness,
    ),
  } as PortfolioSnapshotWithLineage;
}

function normalizePortfolioRiskResponse(data: unknown): PortfolioRiskResponse {
  const normalized = toCamelCase<PortfolioRiskResponse>(data);
  return {
    ...normalized,
    exposureResearchContext: normalizeExposureResearchContext(
      isRecord(normalized) ? normalized.exposureResearchContext : undefined,
    ),
    riskExposureReadiness: normalizeRiskExposureReadiness(
      isRecord(normalized) ? normalized.riskExposureReadiness : undefined,
    ),
  };
}

function normalizeStructureReviewResponse(data: unknown): PortfolioStructureReviewResponse {
  const camelized = toCamelCase<Record<string, unknown>>(data);
  const normalized = isRecord(camelized)
    ? stripStructureReviewUnsafeKeys(camelized)
    : {};

  return {
    schemaVersion: pickString(normalized.schemaVersion) ?? '',
    aggregateSummary: isRecord(normalized.aggregateSummary)
      ? stripStructureReviewUnsafeKeys(normalized.aggregateSummary)
      : {},
    exposureByThemeOrSector: Array.isArray(normalized.exposureByThemeOrSector)
      ? normalized.exposureByThemeOrSector.filter(isRecord).map((entry) => stripStructureReviewUnsafeKeys(entry))
      : [],
    countsByStructureState: isRecord(normalized.countsByStructureState)
      ? Object.fromEntries(
        Object.entries(normalized.countsByStructureState).flatMap(([key, entry]) => (
          typeof entry === 'number' && Number.isFinite(entry) ? [[key, entry]] : []
        )),
      )
      : {},
    holdingsStructure: Array.isArray(normalized.holdingsStructure)
      ? normalized.holdingsStructure.flatMap((entry) => normalizeStructureReviewHolding(entry))
      : [],
    strongestStructures: Array.isArray(normalized.strongestStructures)
      ? normalized.strongestStructures.filter(isRecord).map((entry) => stripStructureReviewUnsafeKeys(entry))
      : [],
    weakestEvidence: Array.isArray(normalized.weakestEvidence)
      ? normalized.weakestEvidence.filter(isRecord).map((entry) => stripStructureReviewUnsafeKeys(entry))
      : [],
    commonRiskFlags: Array.isArray(normalized.commonRiskFlags)
      ? normalized.commonRiskFlags.filter(isRecord).map((entry) => stripStructureReviewUnsafeKeys(entry))
      : [],
    missingEvidence: normalizeStructureReviewMissingEvidence(normalized.missingEvidence),
    researchLinkage: normalizeStructureReviewResearchLinkage(normalized.researchLinkage),
    readOnly: pickBoolean(normalized.readOnly),
    failClosed: pickBoolean(normalized.failClosed),
    consumerState: normalized.consumerState === 'AVAILABLE' || normalized.consumerState === 'PARTIAL' || normalized.consumerState === 'UNAVAILABLE'
      ? normalized.consumerState
      : undefined,
    consumerSummary: pickString(normalized.consumerSummary),
    consumerMessage: pickString(normalized.consumerMessage),
    drilldownSymbols: pickStringArray(normalized.drilldownSymbols),
    dataQuality: normalizeStructureReviewDataQuality(normalized.dataQuality),
    consumerIssues: normalizeStructureReviewConsumerIssues(normalized.consumerIssues),
    noAdviceDisclosure: pickString(normalized.noAdviceDisclosure) ?? '',
  };
}

function normalizeScenarioRiskShockValue(value: unknown): number | PortfolioScenarioRiskShockValueInput | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (!isRecord(value)) {
    return undefined;
  }

  const normalized: PortfolioScenarioRiskShockValueInput = {};
  const shockPct = pickNumber(value.shockPct);
  const labelType = pickString(value.labelType);

  if (shockPct !== undefined) {
    normalized.shockPct = shockPct;
  }
  if (labelType !== undefined) {
    normalized.labelType = labelType;
  }

  return Object.keys(normalized).length > 0 ? normalized : undefined;
}

function normalizeScenarioRiskScenarioInputs(value: unknown): PortfolioScenarioRiskScenarioInput[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((entry) => {
    if (!isRecord(entry)) {
      return [];
    }

    const name = pickString(entry.name);
    const shocks = isRecord(entry.shocks) ? entry.shocks : null;
    if (!name || !shocks) {
      return [];
    }

    const normalizedShocks = Object.fromEntries(
      Object.entries(shocks).flatMap(([label, shockValue]) => {
        const normalizedValue = normalizeScenarioRiskShockValue(shockValue);
        return normalizedValue === undefined ? [] : [[label, normalizedValue]];
      }),
    );

    return [{
      name,
      shocks: normalizedShocks,
    }];
  });
}

function normalizeScenarioRiskRequest(payload: PortfolioScenarioRiskRequest): Record<string, unknown> {
  const rawPositions = Array.isArray(payload.positions) ? payload.positions : [];
  const rawExposures = Array.isArray(payload.exposures) ? payload.exposures : [];

  return {
    asOf: pickString(payload.asOf) ?? '',
    positions: rawPositions.flatMap((entry) => {
      if (!isRecord(entry)) {
        return [];
      }

      const normalized = {
        symbol: pickString(entry.symbol),
        weight: pickNumber(entry.weight),
        weightPct: pickNumber(entry.weightPct),
        marketValue: pickNumber(entry.marketValue),
        marketValueBase: pickNumber(entry.marketValueBase),
        bucket: pickString(entry.bucket),
        bucketLabel: pickString(entry.bucketLabel),
        theme: pickString(entry.theme),
        currency: pickString(entry.currency),
        factor: pickString(entry.factor),
      };

      return [Object.fromEntries(
        Object.entries(normalized).filter(([, value]) => value !== undefined),
      )];
    }),
    exposures: rawExposures.flatMap((entry) => {
      if (!isRecord(entry)) {
        return [];
      }

      const normalized = {
        symbol: pickString(entry.symbol),
        label: pickString(entry.label),
        labelType: pickString(entry.labelType),
        exposure: pickNumber(entry.exposure),
      };

      return [Object.fromEntries(
        Object.entries(normalized).filter(([, value]) => value !== undefined),
      )];
    }),
    scenarioShocks: normalizeScenarioRiskScenarioInputs(payload.scenarioShocks),
  };
}

function normalizeScenarioRiskCoverage(value: unknown): PortfolioScenarioRiskCoverage {
  const data = isRecord(value) ? value : {};

  return Object.fromEntries(
    Object.entries({
      totalPositions: pickNumber(data.totalPositions),
      positionsWithUsableWeight: pickNumber(data.positionsWithUsableWeight),
      positionsWithMarketValue: pickNumber(data.positionsWithMarketValue),
      effectiveWeightSum: pickNumber(data.effectiveWeightSum),
      totalMarketValue: pickNumber(data.totalMarketValue),
      explicitExposureRows: pickNumber(data.explicitExposureRows),
      labelsWithExplicitCoverage: pickStringArray(data.labelsWithExplicitCoverage),
    }).filter(([, entry]) => entry !== undefined),
  ) as PortfolioScenarioRiskCoverage;
}

function normalizeScenarioRiskAppliedShocks(value: unknown): PortfolioScenarioRiskAppliedShock[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((entry) => {
    if (!isRecord(entry)) {
      return [];
    }

    const label = pickString(entry.label);
    if (!label) {
      return [];
    }

    return [{
      label,
      ...Object.fromEntries(
        Object.entries({
          labelType: pickString(entry.labelType),
          shockPct: pickNumber(entry.shockPct),
          exposure: pickNumber(entry.exposure),
          impactPct: pickNumber(entry.impactPct),
          impactAmount: pickNumber(entry.impactAmount),
        }).filter(([, item]) => item !== undefined),
      ),
    }];
  });
}

function normalizeScenarioRiskPositionContributions(value: unknown): PortfolioScenarioRiskPositionContribution[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((entry) => {
    if (!isRecord(entry)) {
      return [];
    }

    const symbol = pickString(entry.symbol);
    if (!symbol) {
      return [];
    }

    return [{
      symbol,
      ...Object.fromEntries(
        Object.entries({
          bucket: pickString(entry.bucket),
          weight: pickNumber(entry.weight),
          marketValue: pickNumber(entry.marketValue),
          impactPct: pickNumber(entry.impactPct),
          impactAmount: pickNumber(entry.impactAmount),
          contributionToScenarioLoss: pickNumber(entry.contributionToScenarioLoss),
          warnings: pickStringArray(entry.warnings),
          appliedShocks: normalizeScenarioRiskAppliedShocks(entry.appliedShocks),
        }).filter(([, item]) => item !== undefined),
      ),
    }];
  });
}

function normalizeScenarioRiskBucketContributions(value: unknown): PortfolioScenarioRiskBucketContribution[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((entry) => {
    if (!isRecord(entry)) {
      return [];
    }

    const bucket = pickString(entry.bucket);
    if (!bucket) {
      return [];
    }

    return [{
      bucket,
      ...Object.fromEntries(
        Object.entries({
          positionCount: pickNumber(entry.positionCount),
          impactPct: pickNumber(entry.impactPct),
          impactAmount: pickNumber(entry.impactAmount),
          contributionToScenarioLoss: pickNumber(entry.contributionToScenarioLoss),
        }).filter(([, item]) => item !== undefined),
      ),
    }];
  });
}

function normalizeScenarioRiskMissingCoverage(value: unknown): PortfolioScenarioRiskMissingCoverage[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((entry) => {
    if (!isRecord(entry)) {
      return [];
    }

    const label = pickString(entry.label);
    if (!label) {
      return [];
    }

    return [{
      label,
      ...Object.fromEntries(
        Object.entries({
          labelType: pickString(entry.labelType),
          missingSymbols: pickStringArray(entry.missingSymbols),
        }).filter(([, item]) => item !== undefined),
      ),
    }];
  });
}

function normalizeScenarioRiskScenarios(value: unknown): PortfolioScenarioRiskScenarioResult[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((entry) => {
    if (!isRecord(entry)) {
      return [];
    }

    const name = pickString(entry.name);
    if (!name) {
      return [];
    }

    return [{
      name,
      ...Object.fromEntries(
        Object.entries({
          portfolioImpactPct: pickNumber(entry.portfolioImpactPct),
          portfolioImpactAmount: pickNumber(entry.portfolioImpactAmount),
          coveredWeight: pickNumber(entry.coveredWeight),
          coveredMarketValue: pickNumber(entry.coveredMarketValue),
          warnings: pickStringArray(entry.warnings),
          missingCoverage: normalizeScenarioRiskMissingCoverage(entry.missingCoverage),
          positionContributions: normalizeScenarioRiskPositionContributions(entry.positionContributions),
          bucketContributions: normalizeScenarioRiskBucketContributions(entry.bucketContributions),
        }).filter(([, item]) => item !== undefined),
      ),
    }];
  });
}

function normalizeScenarioRiskMetadata(value: unknown): PortfolioScenarioRiskMetadata {
  const data = isRecord(value) ? value : {};

  return Object.fromEntries(
    Object.entries({
      sideEffectFree: pickBoolean(data.sideEffectFree),
      noBrokerSync: pickBoolean(data.noBrokerSync),
      noAccountingMutation: pickBoolean(data.noAccountingMutation),
      noOrderPlacement: pickBoolean(data.noOrderPlacement),
      notInvestmentAdvice: pickBoolean(data.notInvestmentAdvice),
    }).filter(([, item]) => item !== undefined),
  ) as PortfolioScenarioRiskMetadata;
}

function normalizeScenarioRiskResponse(data: unknown): PortfolioScenarioRiskResponse {
  const normalized = isRecord(toCamelCase<Record<string, unknown>>(data))
    ? toCamelCase<Record<string, unknown>>(data)
    : {};

  return {
    readModelType: pickString(normalized.readModelType) ?? '',
    advisoryOnly: pickBoolean(normalized.advisoryOnly) ?? false,
    accountingMutation: pickBoolean(normalized.accountingMutation),
    brokerIntegration: pickBoolean(normalized.brokerIntegration),
    tradeExecution: pickBoolean(normalized.tradeExecution),
    executionReadiness: pickString(normalized.executionReadiness),
    asOf: pickString(normalized.asOf),
    coverage: normalizeScenarioRiskCoverage(normalized.coverage),
    scenarios: normalizeScenarioRiskScenarios(normalized.scenarios),
    insufficientDataReasons: pickStringArray(normalized.insufficientDataReasons) ?? [],
    missingDataWarnings: pickStringArray(normalized.missingDataWarnings) ?? [],
    metadata: normalizeScenarioRiskMetadata(normalized.metadata),
  };
}

export const portfolioApi = {
  async getAccounts(includeInactive = false): Promise<PortfolioAccountListResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/portfolio/accounts', {
      params: { include_inactive: includeInactive },
    });
    return toCamelCase<PortfolioAccountListResponse>(response.data);
  },

  async createAccount(payload: PortfolioAccountCreateRequest): Promise<PortfolioAccountItem> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/portfolio/accounts', {
      name: payload.name,
      broker: payload.broker,
      market: payload.market,
      base_currency: payload.baseCurrency,
      owner_id: payload.ownerId,
    });
    return toCamelCase<PortfolioAccountItem>(response.data);
  },

  async deleteAccount(accountId: number): Promise<PortfolioAccountDeleteResponse> {
    const response = await apiClient.delete<Record<string, unknown>>(`/api/v1/portfolio/accounts/${accountId}`);
    return toCamelCase<PortfolioAccountDeleteResponse>(response.data);
  },

  async listBrokerConnections(portfolioAccountId?: number): Promise<PortfolioBrokerConnectionListResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/portfolio/broker-connections', {
      params: portfolioAccountId != null ? { portfolio_account_id: portfolioAccountId } : undefined,
    });
    return toCamelCase<PortfolioBrokerConnectionListResponse>(response.data);
  },

  async getSnapshot(query: SnapshotQuery = {}): Promise<PortfolioSnapshotWithLineage> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/portfolio/snapshot', {
      params: buildSnapshotParams(query),
    });
    return normalizePortfolioSnapshotResponse(response.data);
  },

  async getStructureReview(query: StructureReviewQuery = {}): Promise<PortfolioStructureReviewResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/portfolio/structure-review', {
      params: buildStructureReviewParams(query),
    });
    return normalizeStructureReviewResponse(response.data);
  },

  async getRisk(query: SnapshotQuery = {}): Promise<PortfolioRiskResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/portfolio/risk', {
      params: buildSnapshotParams(query),
    });
    return normalizePortfolioRiskResponse(response.data);
  },

  async projectScenarioRisk(payload: PortfolioScenarioRiskRequest): Promise<PortfolioScenarioRiskResponse> {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/portfolio/scenario-risk',
      normalizeScenarioRiskRequest(payload),
    );
    return normalizeScenarioRiskResponse(response.data);
  },

  async refreshFx(query: FxRefreshQuery = {}): Promise<PortfolioFxRefreshResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/portfolio/fx/refresh', undefined, {
      params: buildFxRefreshParams(query),
    });
    return toCamelCase<PortfolioFxRefreshResponse>(response.data);
  },

  async getFxRate(query: FxRateQuery): Promise<PortfolioLiveFxRateResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/portfolio/fx-rate', {
      params: { base: query.base, quote: query.quote },
    });
    return toCamelCase<PortfolioLiveFxRateResponse>(response.data);
  },

  async refreshFxRate(query: FxRateQuery): Promise<PortfolioLiveFxRateResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/portfolio/fx-rate/refresh', undefined, {
      params: { base: query.base, quote: query.quote },
    });
    return toCamelCase<PortfolioLiveFxRateResponse>(response.data);
  },

  async createTrade(payload: PortfolioTradeCreateRequest): Promise<PortfolioEventCreatedResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/portfolio/trades', {
      account_id: payload.accountId,
      symbol: payload.symbol,
      trade_date: payload.tradeDate,
      side: payload.side,
      quantity: payload.quantity,
      price: payload.price,
      fee: payload.fee ?? 0,
      tax: payload.tax ?? 0,
      market: payload.market,
      currency: payload.currency,
      trade_uid: payload.tradeUid,
      note: payload.note,
    });
    return toCamelCase<PortfolioEventCreatedResponse>(response.data);
  },

  async deleteTrade(tradeId: number): Promise<PortfolioDeleteResponse> {
    const response = await apiClient.delete<Record<string, unknown>>(`/api/v1/portfolio/trades/${tradeId}`);
    return toCamelCase<PortfolioDeleteResponse>(response.data);
  },

  async updateTrade(tradeId: number, payload: PortfolioTradeUpdateRequest): Promise<PortfolioTradeListItem> {
    const response = await apiClient.patch<Record<string, unknown>>(`/api/v1/portfolio/trades/${tradeId}`, {
      account_id: payload.accountId,
      symbol: payload.symbol,
      trade_date: payload.tradeDate,
      side: payload.side,
      quantity: payload.quantity,
      price: payload.price,
      fee: payload.fee,
      tax: payload.tax,
      market: payload.market,
      currency: payload.currency,
      note: payload.note,
    });
    return toCamelCase<PortfolioTradeListItem>(response.data);
  },

  async createCashLedger(payload: PortfolioCashLedgerCreateRequest): Promise<PortfolioEventCreatedResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/portfolio/cash-ledger', {
      account_id: payload.accountId,
      event_date: payload.eventDate,
      direction: payload.direction,
      amount: payload.amount,
      currency: payload.currency,
      note: payload.note,
    });
    return toCamelCase<PortfolioEventCreatedResponse>(response.data);
  },

  async deleteCashLedger(entryId: number): Promise<PortfolioDeleteResponse> {
    const response = await apiClient.delete<Record<string, unknown>>(`/api/v1/portfolio/cash-ledger/${entryId}`);
    return toCamelCase<PortfolioDeleteResponse>(response.data);
  },

  async createCorporateAction(payload: PortfolioCorporateActionCreateRequest): Promise<PortfolioEventCreatedResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/portfolio/corporate-actions', {
      account_id: payload.accountId,
      symbol: payload.symbol,
      effective_date: payload.effectiveDate,
      action_type: payload.actionType,
      market: payload.market,
      currency: payload.currency,
      cash_dividend_per_share: payload.cashDividendPerShare,
      split_ratio: payload.splitRatio,
      note: payload.note,
    });
    return toCamelCase<PortfolioEventCreatedResponse>(response.data);
  },

  async deleteCorporateAction(actionId: number): Promise<PortfolioDeleteResponse> {
    const response = await apiClient.delete<Record<string, unknown>>(`/api/v1/portfolio/corporate-actions/${actionId}`);
    return toCamelCase<PortfolioDeleteResponse>(response.data);
  },

  async listTrades(query: TradeListQuery = {}): Promise<PortfolioTradeListResponse> {
    const params = buildEventParams(query);
    if (query.symbol) {
      params.symbol = query.symbol;
    }
    if (query.side) {
      params.side = query.side;
    }
    if (query.includeVoided != null) {
      params.include_voided = String(query.includeVoided);
    }
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/portfolio/trades', { params });
    return toCamelCase<PortfolioTradeListResponse>(response.data);
  },

  async listCashLedger(query: CashListQuery = {}): Promise<PortfolioCashLedgerListResponse> {
    const params = buildEventParams(query);
    if (query.direction) {
      params.direction = query.direction;
    }
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/portfolio/cash-ledger', { params });
    return toCamelCase<PortfolioCashLedgerListResponse>(response.data);
  },

  async listCorporateActions(query: CorporateListQuery = {}): Promise<PortfolioCorporateActionListResponse> {
    const params = buildEventParams(query);
    if (query.symbol) {
      params.symbol = query.symbol;
    }
    if (query.actionType) {
      params.action_type = query.actionType;
    }
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/portfolio/corporate-actions', { params });
    return toCamelCase<PortfolioCorporateActionListResponse>(response.data);
  },

  async listImportBrokers(): Promise<PortfolioImportBrokerListResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/portfolio/imports/brokers');
    return toCamelCase<PortfolioImportBrokerListResponse>(response.data);
  },

  async parseCsvImport(broker: string, file: File): Promise<PortfolioImportParseResponse> {
    const formData = new FormData();
    formData.append('broker', broker);
    formData.append('file', file);
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/portfolio/imports/parse', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return toCamelCase<PortfolioImportParseResponse>(response.data);
  },

  async commitCsvImport(
    accountId: number,
    broker: string,
    file: File,
    dryRun = false,
  ): Promise<PortfolioImportCommitResponse> {
    const formData = new FormData();
    formData.append('account_id', String(accountId));
    formData.append('broker', broker);
    formData.append('dry_run', dryRun ? 'true' : 'false');
    formData.append('file', file);
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/portfolio/imports/commit', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return toCamelCase<PortfolioImportCommitResponse>(response.data);
  },

  async syncIbkrReadOnly(payload: PortfolioIbkrSyncRequest): Promise<PortfolioIbkrSyncResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/portfolio/sync/ibkr', {
      account_id: payload.accountId,
      broker_connection_id: payload.brokerConnectionId,
      broker_account_ref: payload.brokerAccountRef,
      session_token: payload.sessionToken,
      api_base_url: payload.apiBaseUrl,
      verify_ssl: payload.verifySsl,
    });
    return toCamelCase<PortfolioIbkrSyncResponse>(response.data);
  },
};
