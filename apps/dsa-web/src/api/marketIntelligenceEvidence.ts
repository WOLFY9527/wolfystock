export type MarketIntelligenceEvidenceFields = {
  key: string;
  label?: string | null;
  pillar?: string | null;
  direction?: string | null;
  signal?: number | null;
  weight?: number | null;
  impact?: number | null;
  expectedDirection?: string | null;
  reason?: string | null;
  source?: string | null;
  sourceLabel?: string | null;
  sourceTier?: string | null;
  trustLevel?: string | null;
  asOf?: string | null;
  freshness?: string | null;
  isFallback?: boolean;
  isPartial?: boolean;
  isUnavailable?: boolean;
  observationOnly?: boolean;
  sourceAuthorityAllowed?: boolean;
  scoreContributionAllowed?: boolean;
  sourceAuthorityReason?: string | null;
  sourceAuthorityRouteRejected?: boolean;
  routeRejectedReasonCodes?: string[];
  officialSeriesId?: string | null;
  officialObservationDate?: string | null;
  officialAsOf?: string | null;
  discountReasons?: string[];
  degradationReason?: string | null;
};

export function normalizeMarketIntelligenceEvidenceItem<TItem extends MarketIntelligenceEvidenceFields>(
  item?: Partial<TItem> | null,
  options: {
    requireLabel?: boolean;
    additionalFields?: (item: Partial<TItem>) => Partial<TItem>;
  } = {},
): TItem | null {
  if (!item?.key || (options.requireLabel && !item.label)) {
    return null;
  }

  const additionalFields = options.additionalFields?.(item) || {};

  return {
    key: item.key,
    label: item.label,
    pillar: item.pillar,
    direction: item.direction,
    signal: item.signal,
    weight: item.weight,
    impact: item.impact,
    expectedDirection: item.expectedDirection,
    reason: item.reason,
    source: item.source,
    sourceLabel: item.sourceLabel,
    sourceTier: item.sourceTier,
    trustLevel: item.trustLevel,
    asOf: item.asOf,
    freshness: item.freshness,
    isFallback: item.isFallback,
    isPartial: item.isPartial,
    isUnavailable: item.isUnavailable,
    observationOnly: item.observationOnly,
    sourceAuthorityAllowed: item.sourceAuthorityAllowed,
    scoreContributionAllowed: item.scoreContributionAllowed,
    sourceAuthorityReason: item.sourceAuthorityReason,
    sourceAuthorityRouteRejected: item.sourceAuthorityRouteRejected,
    routeRejectedReasonCodes: Array.isArray(item.routeRejectedReasonCodes) ? item.routeRejectedReasonCodes.filter(Boolean) : [],
    officialSeriesId: item.officialSeriesId,
    officialObservationDate: item.officialObservationDate,
    officialAsOf: item.officialAsOf,
    ...additionalFields,
    discountReasons: Array.isArray(item.discountReasons) ? item.discountReasons.filter(Boolean) : [],
    degradationReason: item.degradationReason,
  } as TItem;
}
