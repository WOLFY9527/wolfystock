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
  sourceTier?: string | null;
  trustLevel?: string | null;
  freshness?: string | null;
  observationOnly?: boolean;
  scoreContributionAllowed?: boolean;
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
    sourceTier: item.sourceTier,
    trustLevel: item.trustLevel,
    freshness: item.freshness,
    observationOnly: item.observationOnly,
    scoreContributionAllowed: item.scoreContributionAllowed,
    ...additionalFields,
    discountReasons: Array.isArray(item.discountReasons) ? item.discountReasons.filter(Boolean) : [],
    degradationReason: item.degradationReason,
  } as TItem;
}
