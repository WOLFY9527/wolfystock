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
  PortfolioStructureReviewHolding,
  PortfolioStructureReviewMissingEvidenceItem,
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

function normalizePortfolioSnapshotResponse(data: unknown): PortfolioSnapshotResponse {
  const normalized = toCamelCase<PortfolioSnapshotResponse>(data);
  return {
    ...normalized,
    exposureResearchContext: normalizeExposureResearchContext(
      isRecord(normalized) ? normalized.exposureResearchContext : undefined,
    ),
  };
}

function normalizePortfolioRiskResponse(data: unknown): PortfolioRiskResponse {
  const normalized = toCamelCase<PortfolioRiskResponse>(data);
  return {
    ...normalized,
    exposureResearchContext: normalizeExposureResearchContext(
      isRecord(normalized) ? normalized.exposureResearchContext : undefined,
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
    dataQuality: normalizeStructureReviewDataQuality(normalized.dataQuality),
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
  const shockPct = pickNumber(value.shockPct, value.shock_pct, value.shock, value.return);
  const labelType = pickString(value.labelType, value.label_type, value.type);

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
  const source = payload as unknown as Record<string, unknown>;
  const rawPositions = Array.isArray(source.positions) ? source.positions : [];
  const rawExposures = Array.isArray(source.exposures) ? source.exposures : [];

  return {
    asOf: pickString(source.asOf, source.as_of) ?? '',
    positions: rawPositions.flatMap((entry) => {
      if (!isRecord(entry)) {
        return [];
      }

      const normalized = {
        symbol: pickString(entry.symbol),
        weight: pickNumber(entry.weight),
        weightPct: pickNumber(entry.weightPct, entry.weight_pct),
        marketValue: pickNumber(entry.marketValue, entry.market_value),
        marketValueBase: pickNumber(entry.marketValueBase, entry.market_value_base),
        bucket: pickString(entry.bucket),
        bucketLabel: pickString(entry.bucketLabel, entry.bucket_label),
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
        labelType: pickString(entry.labelType, entry.label_type),
        exposure: pickNumber(entry.exposure),
      };

      return [Object.fromEntries(
        Object.entries(normalized).filter(([, value]) => value !== undefined),
      )];
    }),
    scenarioShocks: normalizeScenarioRiskScenarioInputs(source.scenarioShocks ?? source.scenario_shocks),
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
    executionReadiness: pickString(normalized.executionReadiness) ?? '',
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

  async getSnapshot(query: SnapshotQuery = {}): Promise<PortfolioSnapshotResponse> {
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
