/**
 * Rotation Radar score / relative-strength evidence semantics.
 * Missing metrics must not coerce to observed zero for ordering, badges, or labels.
 * Geometry fallbacks stay display-only and never rewrite evidence text.
 */

export function parseRotationMetric(value?: number | string | null): number | null {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

export function formatRotationScore(value?: number | string | null): string {
  const numeric = parseRotationMetric(value);
  if (numeric === null) {
    return '待确认';
  }
  return String(Math.round(numeric));
}

export function formatRelativeStrengthValue(value?: number | string | null): string {
  const numeric = parseRotationMetric(value);
  if (numeric === null) {
    return '待补齐';
  }
  return `${numeric >= 0 ? '+' : ''}${numeric.toFixed(1)}%`;
}

export function formatConfidenceValue(confidence?: number | string | null): string {
  const numeric = parseRotationMetric(confidence);
  if (numeric === null) {
    return '待确认';
  }
  return `${Math.round(numeric * 100)}%`;
}

/**
 * Known evidence ranks ahead of unknown.
 * Among known values: higher first (desc).
 * Among unknown: stable 0 (caller adds deterministic tie-breakers).
 */
export function compareNullableDesc(a: number | null, b: number | null): number {
  const aKnown = a !== null;
  const bKnown = b !== null;
  if (aKnown !== bKnown) {
    return aKnown ? -1 : 1;
  }
  if (!aKnown || a === null || b === null) {
    return 0;
  }
  return b - a;
}

/** Known first; among known lower first (asc). */
export function compareNullableAsc(a: number | null, b: number | null): number {
  const aKnown = a !== null;
  const bKnown = b !== null;
  if (aKnown !== bKnown) {
    return aKnown ? -1 : 1;
  }
  if (!aKnown || a === null || b === null) {
    return 0;
  }
  return a - b;
}

export type SortableThemeEvidence = {
  id?: string;
  name?: string;
  rotationScore?: number | string | null;
  confidence?: number | string | null;
};

export function compareThemesByEvidenceDesc(
  a: SortableThemeEvidence,
  b: SortableThemeEvidence,
): number {
  const scoreCmp = compareNullableDesc(
    parseRotationMetric(a.rotationScore),
    parseRotationMetric(b.rotationScore),
  );
  if (scoreCmp !== 0) {
    return scoreCmp;
  }
  const confidenceCmp = compareNullableDesc(
    parseRotationMetric(a.confidence),
    parseRotationMetric(b.confidence),
  );
  if (confidenceCmp !== 0) {
    return confidenceCmp;
  }
  const nameCmp = String(a.name || '').localeCompare(String(b.name || ''), 'zh-Hans-CN');
  if (nameCmp !== 0) {
    return nameCmp;
  }
  return String(a.id || '').localeCompare(String(b.id || ''));
}

export function sortThemesByEvidenceDesc<T extends SortableThemeEvidence>(themes: T[]): T[] {
  return themes.slice().sort(compareThemesByEvidenceDesc);
}

/**
 * Positive known signal only. Missing is not weakest; observed 0 is not "useful" signal.
 */
export function hasPositiveKnownMetric(...values: Array<number | string | null | undefined>): boolean {
  return values.some((value) => {
    const numeric = parseRotationMetric(value);
    return numeric !== null && numeric > 0;
  });
}

/**
 * Partial evidence: some metrics known, others missing.
 * Does not collapse to fully unavailable or fully complete.
 */
export function describePartialMetricState(metrics: {
  rotationScore?: number | string | null;
  confidence?: number | string | null;
  relativeStrength?: number | string | null;
}): 'complete' | 'partial' | 'unavailable' {
  const known = [
    parseRotationMetric(metrics.rotationScore),
    parseRotationMetric(metrics.confidence),
    parseRotationMetric(metrics.relativeStrength),
  ].filter((value): value is number => value !== null);
  if (known.length === 0) {
    return 'unavailable';
  }
  if (known.length === 3) {
    return 'complete';
  }
  return 'partial';
}

/**
 * Ranking bar geometry width. Null evidence → null geometry (caller renders empty/min track).
 * Does not coerce missing score to 0 evidence.
 */
export function scoreBarGeometryWidth(
  score?: number | string | null,
  minPct = 8,
  maxPct = 100,
): number | null {
  const numeric = parseRotationMetric(score);
  if (numeric === null) {
    return null;
  }
  return Math.max(minPct, Math.min(maxPct, numeric));
}

/**
 * Matrix x-position. Evidence value stays separate from geometry fallback.
 * Label/tooltip consumers must use evidenceValue / formatRelativeStrengthValue(evidenceValue).
 */
export function matrixGeometryPosition(params: {
  evidenceValue: number | null;
  domain: { min: number; max: number };
  /** Display-only fallback coordinate when evidence is missing (default: domain midpoint). */
  geometryFallback?: number | null;
}): {
  leftPct: number;
  usesGeometryFallback: boolean;
  evidenceValue: number | null;
} {
  const range = params.domain.max - params.domain.min || 1;
  if (params.evidenceValue !== null) {
    return {
      leftPct: ((params.evidenceValue - params.domain.min) / range) * 100,
      usesGeometryFallback: false,
      evidenceValue: params.evidenceValue,
    };
  }
  const fallback = params.geometryFallback ?? (params.domain.min + params.domain.max) / 2;
  return {
    leftPct: ((fallback - params.domain.min) / range) * 100,
    usesGeometryFallback: true,
    evidenceValue: null,
  };
}
