/**
 * Chart accessibility semantic helpers for CoreMarketChart and related hosts.
 * Keeps names/descriptions bounded — never dumps full series or raw provider metadata.
 */

export const CHART_GRAPHIC_ROLE = 'img' as const;

export type CoreMarketChartAccessibleSemantics = {
  /** Concise accessible name for the graphic. */
  ariaLabel: string;
  /** Bounded textual alternative / summary associated via aria-describedby. */
  description: string;
  /** Stable DOM id for aria-describedby. */
  descriptionId: string;
  /** Keyboard exploration hint for the interactive chart frame. */
  exploreLabel: string;
};

function formatDateLabel(value: string | null | undefined): string {
  if (!value) return '--';
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  return `${match[1]}-${match[2]}-${match[3]}`;
}

function joinBoundedParts(parts: Array<string | null | undefined>, separator = ' · '): string {
  return parts
    .map((part) => (typeof part === 'string' ? part.trim() : ''))
    .filter(Boolean)
    .join(separator);
}

/**
 * Build role/name/description semantics for an informational market chart graphic.
 * Does not embed full OHLCV arrays or debug/provider payload fields.
 */
export function buildCoreMarketChartAccessibleSemantics(input: {
  testId: string;
  title: string;
  language: 'zh' | 'en';
  hasChart: boolean;
  emptyTitle: string;
  barCount: number;
  startDate?: string | null;
  endDate?: string | null;
  renderMode: 'candlestick' | 'line';
  latestLabel?: string | null;
  changeLabel?: string | null;
  rangeLabel?: string | null;
  sourceLabel?: string | null;
  statusLabel?: string | null;
  coverageLabel?: string | null;
}): CoreMarketChartAccessibleSemantics {
  const isEn = input.language === 'en';
  const descriptionId = `${input.testId}-chart-text-alternative`;

  if (!input.hasChart) {
    return {
      ariaLabel: joinBoundedParts([input.title, input.emptyTitle], ': '),
      description: joinBoundedParts([
        input.statusLabel,
        input.sourceLabel,
        input.emptyTitle,
      ]),
      descriptionId,
      exploreLabel: isEn ? 'Chart unavailable' : '图表暂不可用',
    };
  }

  const modeLabel = input.renderMode === 'candlestick'
    ? (isEn ? 'candlestick' : 'K 线')
    : (isEn ? 'line' : '折线');

  const barPhrase = isEn
    ? `${input.barCount} returned bars`
    : `${input.barCount} 根返回 K 线`;

  const dateSpan = joinBoundedParts([
    formatDateLabel(input.startDate),
    isEn ? 'to' : '至',
    formatDateLabel(input.endDate),
  ], ' ');

  const ariaLabel = joinBoundedParts([
    input.title,
    modeLabel,
    barPhrase,
    dateSpan,
  ], ': ');

  // Bounded summary — critical facts without hover or full series dump.
  const description = joinBoundedParts([
    input.statusLabel,
    input.rangeLabel
      ? (isEn ? `Range ${input.rangeLabel}` : `区间 ${input.rangeLabel}`)
      : null,
    input.latestLabel
      ? (isEn ? `Latest ${input.latestLabel}` : `最新 ${input.latestLabel}`)
      : null,
    input.changeLabel,
    input.coverageLabel
      ? (isEn ? `Coverage ${input.coverageLabel}` : `覆盖 ${input.coverageLabel}`)
      : null,
    input.sourceLabel
      ? (isEn ? `Source ${input.sourceLabel}` : `来源 ${input.sourceLabel}`)
      : null,
  ]);

  const exploreLabel = isEn
    ? `${input.title}. Use left and right arrow keys to inspect returned bars.`
    : `${input.title}。使用左右方向键检查返回的 K 线。`;

  return {
    ariaLabel,
    description,
    descriptionId,
    exploreLabel,
  };
}
