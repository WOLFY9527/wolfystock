import { describe, expect, it } from 'vitest';
import { getMarketColorPalette, getToneColor, normalizeMarketColorConvention } from '../marketColors';

describe('marketColors paper semantic tokens', () => {
  it('normalizes unknown conventions to redDownGreenUp', () => {
    expect(normalizeMarketColorConvention(undefined)).toBe('redDownGreenUp');
    expect(normalizeMarketColorConvention('unknown')).toBe('redDownGreenUp');
  });

  it('maps bullish/bearish to paper success/danger without neon glows', () => {
    const bullish = getToneColor('bullish', 'redDownGreenUp');
    const bearish = getToneColor('bearish', 'redDownGreenUp');
    const neutral = getToneColor('neutral', 'redDownGreenUp');

    expect(bullish.textClass).toBe('text-[color:var(--state-success-text)]');
    expect(bearish.textClass).toBe('text-[color:var(--state-danger-text)]');
    expect(neutral.textClass).toBe('text-[color:var(--wolfy-text-secondary)]');
    expect(bullish.glowShadow).toBe('none');
    expect(bearish.glowShadow).toBe('none');
    expect(bullish.textClass).not.toMatch(/emerald|rose|drop-shadow/);
    expect(bearish.textClass).not.toMatch(/emerald|rose|drop-shadow/);
  });

  it('swaps positive/negative when redUpGreenDown is selected', () => {
    const bullish = getToneColor('bullish', 'redUpGreenDown');
    const bearish = getToneColor('bearish', 'redUpGreenDown');
    expect(bullish.textClass).toBe('text-[color:var(--state-danger-text)]');
    expect(bearish.textClass).toBe('text-[color:var(--state-success-text)]');
  });

  it('returns paper-aligned HSL palette without neon saturation extremes', () => {
    const palette = getMarketColorPalette('redDownGreenUp');
    expect(palette.upHsl).toBe('127 18% 44%');
    expect(palette.downHsl).toBe('8 32% 49%');
  });
});
