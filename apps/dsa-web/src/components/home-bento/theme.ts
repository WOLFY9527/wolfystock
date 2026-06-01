import type { CSSProperties } from 'react';
import { getToneColor, type MarketColorConvention } from '../../utils/marketColors';

export type SignalTone = 'bullish' | 'bearish' | 'neutral';

export function getToneTextClass(
  tone: SignalTone,
  convention: MarketColorConvention = 'redDownGreenUp',
): string {
  return getToneColor(tone, convention).textClass;
}

export function getToneTextStyle(
  tone: SignalTone,
  conventionOrGlow: MarketColorConvention | boolean = 'redDownGreenUp',
  maybeGlow = false,
): CSSProperties {
  const convention = typeof conventionOrGlow === 'string' ? conventionOrGlow : 'redDownGreenUp';
  const glow = typeof conventionOrGlow === 'boolean' ? conventionOrGlow : maybeGlow;
  const color = getToneColor(tone, convention);
  return {
    color: color.colorHex,
    textShadow: glow ? color.glowShadow : 'none',
  };
}
