import type { CSSProperties } from 'react';
import { getToneColor, type MarketColorConvention } from '../../utils/marketColors';

export type SignalTone = 'bullish' | 'bearish' | 'neutral';

export const CARD_KICKER_CLASS = 'block truncate text-[10px] font-semibold uppercase tracking-widest text-white/40';
export const CARD_BUTTON_CLASS = 'pointer-events-auto inline-flex items-center gap-1.5 text-xs text-white/40 transition-colors duration-150 hover:text-white';
export const PANEL_METRIC_CLASS = 'rounded-[8px] border border-[#23252a] bg-[#141516] p-4';
export const BENTO_SURFACE_ROOT_CLASS = 'bento-surface-root';
export const BENTO_GRID_ROOT_CLASS = 'bento-grid-root';
export const SYSTEM_ACCENT_TEXT_CLASS = 'text-[#5e6ad2]';
export const SYSTEM_ACCENT_BORDER_CLASS = 'border-[#5e6ad2]/35 bg-[#5e6ad2]/12 text-[#d0d6e0]';
export const SYSTEM_ACCENT_GLOW_CLASS = 'bg-[#5e6ad2]/10';

export function getToneTextClass(
  tone: SignalTone,
  convention: MarketColorConvention = 'redDownGreenUp',
): string {
  return getToneColor(tone, convention).textClass;
}

export function getToneBorderClass(
  tone: SignalTone,
  convention: MarketColorConvention = 'redDownGreenUp',
): string {
  if (tone === 'neutral') {
    return 'border-[#34343a] bg-[#18191a] text-[#d0d6e0]';
  }
  const textClass = getToneTextClass(tone, convention);
  if (textClass.includes('text-emerald-400')) {
    return 'border-emerald-400/22 bg-emerald-400/10 text-emerald-400';
  }
  if (textClass.includes('text-rose-400')) {
    return 'border-rose-400/22 bg-rose-400/10 text-rose-400';
  }
  return 'border-[#34343a] bg-[#18191a] text-[#d0d6e0]';
}

export function getCardGlowClass(
  tone: SignalTone,
  convention: MarketColorConvention = 'redDownGreenUp',
): string {
  if (tone === 'neutral') {
    return 'bg-transparent';
  }
  return getToneTextClass(tone, convention).includes('text-emerald-400')
    ? 'bg-emerald-400/14'
    : 'bg-rose-400/14';
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
