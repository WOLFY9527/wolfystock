export type MarketColorConvention = 'redDownGreenUp' | 'redUpGreenDown';
export type SemanticSignalTone = 'bullish' | 'bearish' | 'neutral';

export const MARKET_COLOR_CONVENTION_STORAGE_KEY = 'dsa-market-color-convention';
export const DEFAULT_MARKET_COLOR_CONVENTION: MarketColorConvention = 'redDownGreenUp';

/** Paper-theme positive (gain) — matches --state-success-text / WCAG AA on surface. */
const PAPER_POSITIVE_HEX = '#466a4d';
/** Paper-theme negative (loss) — matches --state-danger-text / WCAG AA on surface. */
const PAPER_NEGATIVE_HEX = '#894a42';
/** Paper-theme neutral body text — matches --ink-soft. */
const PAPER_NEUTRAL_HEX = '#3d3831';

const PAPER_POSITIVE_TEXT_CLASS = 'text-[color:var(--state-success-text)]';
const PAPER_NEGATIVE_TEXT_CLASS = 'text-[color:var(--state-danger-text)]';
const PAPER_NEUTRAL_TEXT_CLASS = 'text-[color:var(--wolfy-text-secondary)]';

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
  // Paper ok/danger HSL (aligned with DESIGN --ok / --danger, not Tailwind emerald/rose).
  if (convention === 'redUpGreenDown') {
    return {
      upHsl: '8 32% 49%',
      downHsl: '127 18% 44%',
    };
  }

  return {
    upHsl: '127 18% 44%',
    downHsl: '8 32% 49%',
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
      colorHex: PAPER_NEUTRAL_HEX,
      glowShadow: 'none',
      textClass: PAPER_NEUTRAL_TEXT_CLASS,
    };
  }

  const usePositive = (tone === 'bullish' && convention === 'redDownGreenUp')
    || (tone === 'bearish' && convention === 'redUpGreenDown');

  if (usePositive) {
    return {
      colorHex: PAPER_POSITIVE_HEX,
      glowShadow: 'none',
      textClass: PAPER_POSITIVE_TEXT_CLASS,
    };
  }

  return {
    colorHex: PAPER_NEGATIVE_HEX,
    glowShadow: 'none',
    textClass: PAPER_NEGATIVE_TEXT_CLASS,
  };
}
