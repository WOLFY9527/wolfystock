import type { MarketOverviewItem, MarketRiskDirection } from '../../api/marketOverview';

const directionTone: Record<MarketRiskDirection, string> = {
  increasing: 'text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.36)]',
  decreasing: 'text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.36)]',
  neutral: 'text-white/45',
};

export function getDirectionTone(direction?: MarketRiskDirection): string {
  return directionTone[direction || 'neutral'];
}

export function isRenderableMarketOverviewItem(item: MarketOverviewItem): boolean {
  const value = item.value as unknown;
  if (value === null || value === undefined) {
    return false;
  }
  if (typeof value === 'string') {
    const normalized = value.trim().toUpperCase();
    return normalized !== 'N/A' && normalized !== '-';
  }
  return true;
}

export function formatMetricValue(
  item: Pick<MarketOverviewItem, 'value'>,
  digitsBelowHundred = 2,
): string {
  if (item.value === null || item.value === undefined) {
    return 'N/A';
  }
  return Math.abs(item.value) >= 100
    ? item.value.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : item.value.toFixed(digitsBelowHundred);
}

function estimateAbsoluteChange(item: Pick<MarketOverviewItem, 'value' | 'changePct'>): number | null {
  if (item.value === null || item.value === undefined || item.changePct === null || item.changePct === undefined) {
    return null;
  }
  const previous = item.value / (1 + item.changePct / 100);
  return item.value - previous;
}

function formatSignedNumber(value: number, digits = 2): string {
  const sign = value >= 0 ? '+' : '-';
  const magnitude = Math.abs(value);
  const rendered = magnitude >= 100
    ? magnitude.toLocaleString(undefined, { maximumFractionDigits: digits })
    : magnitude.toFixed(digits);
  return `${sign}${rendered}`;
}

function formatSignedPercent(value?: number | null): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

export function formatChangeSummary(
  item: Pick<MarketOverviewItem, 'value' | 'changePct' | 'changeText'>,
  neutralLabel = 'neutral',
): string {
  if (item.changeText) {
    return item.changeText;
  }
  const absoluteChange = estimateAbsoluteChange(item);
  const changePct = formatSignedPercent(item.changePct);
  if (absoluteChange === null && !changePct) {
    return neutralLabel;
  }
  if (absoluteChange === null) {
    return changePct!;
  }
  if (!changePct) {
    return formatSignedNumber(absoluteChange, 1);
  }
  return `${formatSignedNumber(absoluteChange, 1)} (${changePct})`;
}
