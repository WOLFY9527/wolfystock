import { describe, expect, it } from 'vitest';
import {
  confidenceMeetsThreshold,
  formatLiquidityScoreConfidence,
  isLowOrMissingConfidence,
  maxKnownConfidence,
  parseNullableConfidence,
} from '../liquidityConfidenceSemantics';

describe('liquidityConfidenceSemantics', () => {
  it('formats observed zero confidence as 0% and keeps it distinct from unavailable', () => {
    expect(formatLiquidityScoreConfidence(0)).toBe('0%');
    expect(formatLiquidityScoreConfidence(null)).toBe('待确认');
    expect(formatLiquidityScoreConfidence(undefined)).toBe('待确认');
    expect(formatLiquidityScoreConfidence(Number.NaN)).toBe('待确认');
  });

  it('formats known confidence ratios as percentages without inventing values', () => {
    expect(formatLiquidityScoreConfidence(0.44)).toBe('44%');
    expect(formatLiquidityScoreConfidence(1)).toBe('100%');
  });

  it('parses nullable confidence without coercing missing to zero', () => {
    expect(parseNullableConfidence(0)).toBe(0);
    expect(parseNullableConfidence(0.5)).toBe(0.5);
    expect(parseNullableConfidence(null)).toBeNull();
    expect(parseNullableConfidence(undefined)).toBeNull();
  });

  it('uses only known confidences for max and readiness thresholds', () => {
    expect(maxKnownConfidence(null, undefined)).toBeNull();
    expect(maxKnownConfidence(null, 0.2, 0.71)).toBe(0.71);
    expect(maxKnownConfidence(0, null)).toBe(0);

    expect(confidenceMeetsThreshold(null, 0.45)).toBe(false);
    expect(confidenceMeetsThreshold(0, 0.45)).toBe(false);
    expect(confidenceMeetsThreshold(0.45, 0.45)).toBe(true);
    expect(isLowOrMissingConfidence(null)).toBe(true);
    expect(isLowOrMissingConfidence(0)).toBe(true);
    expect(isLowOrMissingConfidence(0.5)).toBe(false);
  });
});
