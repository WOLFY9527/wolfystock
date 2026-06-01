export type MarketColorConvention = 'redDownGreenUp' | 'redUpGreenDown';
export type SemanticSignalTone = 'bullish' | 'bearish' | 'neutral';

export const MARKET_COLOR_CONVENTION_STORAGE_KEY = 'dsa-market-color-convention';
export const DEFAULT_MARKET_COLOR_CONVENTION: MarketColorConvention = 'redDownGreenUp';

export function normalizeMarketColorConvention(
  value?: string | null,
): MarketColorConvention {
  if (value === 'redDownGreenUp' || value === 'redUpGreenDown') {
    return value;
  }
  return DEFAULT_MARKET_COLOR_CONVENTION;
}

export function getMarketColorPalette(convention: MarketColorConvention): {
  upHsl: string;
  downHsl: string;
} {
  if (convention === 'redUpGreenDown') {
    return {
      upHsl: '4 82% 62%',
      downHsl: '145 66% 52%',
    };
  }

  return {
    upHsl: '145 66% 52%',
    downHsl: '4 82% 62%',
  };
}

export function getToneColor(
  tone: SemanticSignalTone,
  convention: MarketColorConvention,
): {
  colorHex: string;
  glowShadow: string;
  textClass: string;
} {
  if (tone === 'neutral') {
    return {
      colorHex: '#F8FAFC',
      glowShadow: 'none',
      textClass: 'text-white',
    };
  }

  const useEmerald = (tone === 'bullish' && convention === 'redDownGreenUp')
    || (tone === 'bearish' && convention === 'redUpGreenDown');

  if (useEmerald) {
    return {
      colorHex: '#34D399',
      glowShadow: '0 0 8px rgba(52, 211, 153, 0.4)',
      textClass: 'text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.4)]',
    };
  }

  return {
    colorHex: '#FB7185',
    glowShadow: '0 0 8px rgba(251, 113, 133, 0.4)',
    textClass: 'text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.4)]',
  };
}
