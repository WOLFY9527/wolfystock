import { describe, expect, it } from 'vitest';
import {
  compareNullableDesc,
  describePartialMetricState,
  formatConfidenceValue,
  formatRelativeStrengthValue,
  formatRotationScore,
  hasPositiveKnownMetric,
  matrixGeometryPosition,
  parseRotationMetric,
  scoreBarGeometryWidth,
  sortThemesByEvidenceDesc,
} from '../rotationEvidenceSemantics';

describe('rotationEvidenceSemantics', () => {
  it('parses null and empty as unavailable without coercing to zero', () => {
    expect(parseRotationMetric(null)).toBeNull();
    expect(parseRotationMetric(undefined)).toBeNull();
    expect(parseRotationMetric('')).toBeNull();
    expect(parseRotationMetric(0)).toBe(0);
    expect(parseRotationMetric('0')).toBe(0);
    expect(parseRotationMetric(-1.5)).toBe(-1.5);
  });

  it('formats score and RS honestly for null vs observed zero', () => {
    expect(formatRotationScore(null)).toBe('待确认');
    expect(formatRotationScore(0)).toBe('0');
    expect(formatRotationScore(78.4)).toBe('78');

    expect(formatRelativeStrengthValue(null)).toBe('待补齐');
    expect(formatRelativeStrengthValue(0)).toBe('+0.0%');
    expect(formatRelativeStrengthValue(-2.4)).toBe('-2.4%');

    expect(formatConfidenceValue(null)).toBe('待确认');
    expect(formatConfidenceValue(0)).toBe('0%');
    expect(formatConfidenceValue(0.72)).toBe('72%');
  });

  it('orders known evidence before unknown and does not rank null as weakest', () => {
    const sorted = sortThemesByEvidenceDesc([
      { id: 'unknown-a', name: '未知A', rotationScore: null, confidence: null },
      { id: 'weak', name: '弱主题', rotationScore: 0, confidence: 0.1 },
      { id: 'unknown-b', name: '未知B', rotationScore: null, confidence: null },
      { id: 'strong', name: '强主题', rotationScore: 80, confidence: 0.7 },
      { id: 'mid', name: '中主题', rotationScore: 40, confidence: 0.4 },
    ]);

    expect(sorted.map((item) => item.id)).toEqual([
      'strong',
      'mid',
      'weak',
      'unknown-a',
      'unknown-b',
    ]);
  });

  it('keeps deterministic ordering inside the unknown group', () => {
    const sorted = sortThemesByEvidenceDesc([
      { id: 'b', name: '贝塔', rotationScore: null, confidence: null },
      { id: 'a', name: '阿尔法', rotationScore: null, confidence: null },
      { id: 'c', name: '阿尔法', rotationScore: null, confidence: null },
    ]);
    expect(sorted.map((item) => item.id)).toEqual(['a', 'c', 'b']);
  });

  it('compareNullableDesc never treats null as observed zero', () => {
    expect(compareNullableDesc(null, 0)).toBe(1);
    expect(compareNullableDesc(0, null)).toBe(-1);
    expect(compareNullableDesc(null, null)).toBe(0);
    expect(compareNullableDesc(10, 3)).toBeLessThan(0);
  });

  it('separates plot geometry fallback from evidence labels', () => {
    const known = matrixGeometryPosition({
      evidenceValue: 2,
      domain: { min: -2, max: 2 },
    });
    expect(known.usesGeometryFallback).toBe(false);
    expect(known.evidenceValue).toBe(2);
    expect(known.leftPct).toBe(100);

    const missing = matrixGeometryPosition({
      evidenceValue: null,
      domain: { min: -2, max: 2 },
    });
    expect(missing.usesGeometryFallback).toBe(true);
    expect(missing.evidenceValue).toBeNull();
    expect(formatRelativeStrengthValue(missing.evidenceValue)).toBe('待补齐');
    expect(missing.leftPct).toBe(50);

    expect(scoreBarGeometryWidth(null)).toBeNull();
    expect(scoreBarGeometryWidth(0)).toBe(8);
    expect(scoreBarGeometryWidth(50)).toBe(50);
  });

  it('preserves partial metric state without full collapse', () => {
    expect(describePartialMetricState({
      rotationScore: 70,
      confidence: null,
      relativeStrength: 1.2,
    })).toBe('partial');

    expect(describePartialMetricState({
      rotationScore: null,
      confidence: null,
      relativeStrength: null,
    })).toBe('unavailable');

    expect(describePartialMetricState({
      rotationScore: 70,
      confidence: 0.5,
      relativeStrength: 0,
    })).toBe('complete');

    expect(hasPositiveKnownMetric(null, 0, undefined)).toBe(false);
    expect(hasPositiveKnownMetric(null, 0.2)).toBe(true);
  });
});
