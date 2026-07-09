/**
 * Liquidity Monitor confidence evidence semantics.
 * unavailable / missing confidence must never present as measured 0%.
 */

export function isFiniteConfidence(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function parseNullableConfidence(value?: number | null): number | null {
  return isFiniteConfidence(value) ? value : null;
}

/**
 * Format score.confidence for consumer display.
 * Observed 0 remains "0%"; missing/null/NaN uses product vocabulary.
 */
export function formatLiquidityScoreConfidence(value?: number | null): string {
  if (!isFiniteConfidence(value)) {
    return '待确认';
  }
  return `${Math.round(value * 100)}%`;
}

/** Max among known confidences only; null when every input is unavailable. */
export function maxKnownConfidence(...values: Array<number | null | undefined>): number | null {
  const known = values.filter(isFiniteConfidence);
  if (!known.length) {
    return null;
  }
  return Math.max(...known);
}

/** Readiness / limited-confidence gates: missing never satisfies a positive threshold. */
export function confidenceMeetsThreshold(
  value: number | null | undefined,
  threshold: number,
): boolean {
  return isFiniteConfidence(value) && value >= threshold;
}

export function isLowOrMissingConfidence(
  value: number | null | undefined,
  threshold = 0.45,
): boolean {
  return !confidenceMeetsThreshold(value, threshold);
}
