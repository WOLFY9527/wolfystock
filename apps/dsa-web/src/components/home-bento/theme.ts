import type { CSSProperties } from 'react';
import { getToneColor, type MarketColorConvention } from '../../utils/marketColors';

export type SignalTone = 'bullish' | 'bearish' | 'neutral';

export const CARD_KICKER_CLASS = 'block truncate text-[10px] font-semibold uppercase tracking-widest text-white/40';
export const CARD_BUTTON_CLASS = 'pointer-events-auto inline-flex items-center gap-1.5 text-xs text-white/40 transition-colors duration-150 hover:text-white';
export const PANEL_METRIC_CLASS = 'rounded-[18px] border border-white/5 bg-white/[0.01] p-4 backdrop-blur-xl';
export const BENTO_SURFACE_ROOT_CLASS = 'bento-surface-root';
export const BENTO_GRID_ROOT_CLASS = 'bento-grid-root';
export const SYSTEM_ACCENT_TEXT_CLASS = 'text-[#60A5FA]';
export const SYSTEM_ACCENT_BORDER_CLASS = 'border-[#60A5FA]/24 bg-[#3B82F6]/10 text-[#60A5FA]';
export const SYSTEM_ACCENT_GLOW_CLASS = 'bg-[#3B82F6]/16';

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
    return 'border-white/12 bg-white/[0.06] text-white/78';
  }
  const textClass = getToneTextClass(tone, convention);
  if (textClass.includes('text-emerald-400')) {
    return 'border-emerald-400/22 bg-emerald-400/10 text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.4)]';
  }
  if (textClass.includes('text-rose-400')) {
    return 'border-rose-400/22 bg-rose-400/10 text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.4)]';
  }
  return 'border-white/12 bg-white/[0.06] text-white/78';
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
