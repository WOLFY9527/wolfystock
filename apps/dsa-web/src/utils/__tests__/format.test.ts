import { describe, expect, it } from 'vitest';
import {
  formatCurrency,
  formatDateTime,
  formatDurationMs,
  formatNumber,
  formatPercent,
} from '../format';

describe('format utilities', () => {
  it('returns missing placeholder for nullish and invalid numeric inputs', () => {
    expect(formatNumber(undefined)).toBe('--');
    expect(formatPercent(null)).toBe('--');
    expect(formatCurrency(Number.NaN, { currency: 'CNY' })).toBe('--');
  });

  it('returns missing placeholder for invalid dates', () => {
    expect(formatDateTime('not-a-date')).toBe('--');
  });

  it('formats date time in the current Chinese UI style', () => {
    expect(formatDateTime('2026-04-30T00:00:00Z')).toBe('2026/04/30 08:00');
  });

  it('formats regular numbers', () => {
    expect(formatNumber(1234.567)).toBe('1,234.57');
  });

  it('formats percent values in percent and ratio modes', () => {
    expect(formatPercent(12.3)).toBe('12.3%');
    expect(formatPercent(0.123, { mode: 'ratio' })).toBe('12.3%');
  });

  it('formats currency values', () => {
    expect(formatCurrency(1234.5, { currency: 'CNY' })).toBe('¥1,234.50');
  });

  it('formats durations with ms, seconds, and minute-second buckets', () => {
    expect(formatDurationMs(320)).toBe('320ms');
    expect(formatDurationMs(1200)).toBe('1.2s');
    expect(formatDurationMs(12300)).toBe('12.3s');
    expect(formatDurationMs(65000)).toBe('1m 5s');
  });
});
