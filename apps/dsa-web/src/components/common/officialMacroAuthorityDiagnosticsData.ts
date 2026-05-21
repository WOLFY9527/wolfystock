type ChipVariant = 'neutral' | 'success' | 'caution' | 'danger' | 'info';

export const OFFICIAL_MACRO_SCOPE_SERIES = [
  'VIXCLS',
  'SOFR',
  'DFF',
  'DGS2',
  'DGS10',
  'DGS30',
  'BAMLH0A0HYM2',
] as const;

const OFFICIAL_MACRO_SCOPE_LABELS: Record<(typeof OFFICIAL_MACRO_SCOPE_SERIES)[number], string> = {
  VIXCLS: 'VIX',
  SOFR: 'SOFR',
  DFF: 'Fed Funds',
  DGS2: 'US 2Y',
  DGS10: 'US 10Y',
  DGS30: 'US 30Y',
  BAMLH0A0HYM2: 'Credit spreads',
};

export type OfficialMacroAuthorityRecord = {
  key: string;
  label?: string | null;
  sourceLabel?: string | null;
  sourceTier?: string | null;
  trustLevel?: string | null;
  freshness?: string | null;
  asOf?: string | null;
  isFallback?: boolean;
  isUnavailable?: boolean;
  isPartial?: boolean;
  observationOnly?: boolean;
  sourceAuthorityAllowed?: boolean;
  scoreContributionAllowed?: boolean;
  sourceAuthorityReason?: string | null;
  sourceAuthorityRouteRejected?: boolean;
  routeRejectedReasonCodes?: string[] | null;
  officialSeriesId?: string | null;
  officialObservationDate?: string | null;
  officialAsOf?: string | null;
};

type OfficialMacroAuthorityRowView = {
  key: string;
  label: string;
  seriesId: string;
  chips: Array<{ label: string; variant: ChipVariant }>;
  meta: string;
  reasonText?: string;
  missing?: boolean;
};

export type OfficialMacroAuthorityDiagnosticsView = {
  rows: OfficialMacroAuthorityRowView[];
  scopeSeries: string[];
};

function isScopeSeries(value?: string | null): value is (typeof OFFICIAL_MACRO_SCOPE_SERIES)[number] {
  return Boolean(value && OFFICIAL_MACRO_SCOPE_SERIES.includes(value as (typeof OFFICIAL_MACRO_SCOPE_SERIES)[number]));
}

function resolveSeriesId(record: OfficialMacroAuthorityRecord): string | null {
  if (isScopeSeries(record.officialSeriesId)) {
    return record.officialSeriesId;
  }
  return null;
}

function recordRank(record: OfficialMacroAuthorityRecord): number {
  return [
    record.sourceAuthorityAllowed ? 40 : 0,
    record.scoreContributionAllowed ? 25 : 0,
    record.sourceAuthorityRouteRejected ? -28 : 0,
    record.isUnavailable ? -24 : 0,
    record.isFallback ? -18 : 0,
    record.isPartial ? -8 : 0,
    record.observationOnly ? -6 : 0,
    record.routeRejectedReasonCodes?.length ? 2 : 0,
    record.officialObservationDate || record.officialAsOf ? 3 : 0,
  ].reduce((sum, value) => sum + value, 0);
}

function chooseBetterRecord(current: OfficialMacroAuthorityRecord, candidate: OfficialMacroAuthorityRecord): OfficialMacroAuthorityRecord {
  return recordRank(candidate) > recordRank(current) ? candidate : current;
}

function statusChips(record: OfficialMacroAuthorityRecord, missing = false): Array<{ label: string; variant: ChipVariant }> {
  const chips: Array<{ label: string; variant: ChipVariant }> = [];

  if (record.sourceAuthorityRouteRejected) {
    chips.push({ label: 'Rejected', variant: 'danger' });
  }

  if (missing || record.isUnavailable || record.freshness === 'unavailable') {
    chips.push({ label: 'Unavailable', variant: 'caution' });
  } else if (record.sourceAuthorityAllowed) {
    chips.push({ label: 'Official', variant: 'success' });
  } else if (record.sourceAuthorityReason === 'proxy_context_only') {
    chips.push({ label: 'Proxy-only', variant: 'caution' });
  }

  if (record.isFallback || record.freshness === 'fallback' || record.freshness === 'mock') {
    chips.push({ label: 'Fallback', variant: 'caution' });
  } else if (record.isPartial || record.freshness === 'partial') {
    chips.push({ label: 'Partial', variant: 'info' });
  }

  if (record.scoreContributionAllowed) {
    chips.push({ label: 'Score-eligible', variant: 'success' });
  } else if (record.observationOnly) {
    chips.push({ label: 'Observation-only', variant: 'info' });
  }

  return chips.length > 0 ? chips : [{ label: 'Unavailable', variant: 'caution' }];
}

function buildMeta(record: OfficialMacroAuthorityRecord, missing = false): string {
  if (missing) {
    return 'API did not return this bounded official series.';
  }

  const asOf = record.officialObservationDate || record.officialAsOf || record.asOf;
  const parts = [
    record.sourceLabel || '',
    record.sourceTier || '',
    record.trustLevel || '',
    record.freshness || '',
    asOf ? `As-of ${asOf}` : '',
  ].filter(Boolean);

  return parts.join(' · ') || 'No authority metadata returned.';
}

function buildReasonText(record: OfficialMacroAuthorityRecord): string | undefined {
  const codes = Array.isArray(record.routeRejectedReasonCodes) ? record.routeRejectedReasonCodes.filter(Boolean) : [];
  const reasons = [
    record.sourceAuthorityReason || '',
    ...codes,
  ].filter(Boolean);

  return reasons.length > 0 ? reasons.join(' · ') : undefined;
}

export function buildOfficialMacroAuthorityDiagnosticsView(
  records: OfficialMacroAuthorityRecord[],
): OfficialMacroAuthorityDiagnosticsView {
  const bySeries = new Map<string, OfficialMacroAuthorityRecord>();

  records.forEach((record) => {
    const seriesId = resolveSeriesId(record);
    if (!seriesId) {
      return;
    }
    const current = bySeries.get(seriesId);
    bySeries.set(seriesId, current ? chooseBetterRecord(current, record) : record);
  });

  return {
    scopeSeries: [...OFFICIAL_MACRO_SCOPE_SERIES],
    rows: OFFICIAL_MACRO_SCOPE_SERIES.map((seriesId) => {
      const record = bySeries.get(seriesId);
      const missing = !record;
      const fallbackRecord: OfficialMacroAuthorityRecord = { key: `missing:${seriesId}` };
      const resolvedRecord = record || fallbackRecord;

      return {
        key: resolvedRecord.key,
        label: record?.label || OFFICIAL_MACRO_SCOPE_LABELS[seriesId],
        seriesId,
        chips: statusChips(resolvedRecord, missing),
        meta: buildMeta(resolvedRecord, missing),
        reasonText: record ? buildReasonText(record) : undefined,
        missing,
      };
    }),
  };
}
