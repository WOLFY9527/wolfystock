export const PORTFOLIO_DISPLAY_CURRENCY_OPTIONS = ['CNY', 'USD', 'HKD', 'EUR', 'JPY'] as const;
export type PortfolioDisplayCurrency = typeof PORTFOLIO_DISPLAY_CURRENCY_OPTIONS[number];

export const PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY = 'wolfystock.portfolio.displayCurrency';
export const LEGACY_PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY = 'wolfystock.portfolio.displayCurrency.v1';
export const PORTFOLIO_DISPLAY_CURRENCY_CHANGED_EVENT = 'wolfystock:portfolio-display-currency-changed';

export function normalizePortfolioDisplayCurrency(value: unknown): PortfolioDisplayCurrency {
  const normalized = typeof value === 'string' ? value.toUpperCase() : '';
  return PORTFOLIO_DISPLAY_CURRENCY_OPTIONS.includes(normalized as PortfolioDisplayCurrency)
    ? (normalized as PortfolioDisplayCurrency)
    : 'CNY';
}

export function readPortfolioDisplayCurrency(): PortfolioDisplayCurrency {
  if (typeof window === 'undefined') {
    return 'CNY';
  }

  const current = window.localStorage.getItem(PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY);
  if (current) {
    return normalizePortfolioDisplayCurrency(current);
  }

  const legacy = window.localStorage.getItem(LEGACY_PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY);
  if (legacy) {
    const migrated = normalizePortfolioDisplayCurrency(legacy);
    window.localStorage.setItem(PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY, migrated);
    return migrated;
  }

  return 'CNY';
}

export function savePortfolioDisplayCurrency(value: unknown): PortfolioDisplayCurrency {
  const normalized = normalizePortfolioDisplayCurrency(value);
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY, normalized);
    window.dispatchEvent(new CustomEvent(PORTFOLIO_DISPLAY_CURRENCY_CHANGED_EVENT, {
      detail: { currency: normalized },
    }));
  }
  return normalized;
}

export function inferSettlementCurrency(
  rawSymbol: string,
  accountBaseCurrency?: string | null,
): PortfolioDisplayCurrency {
  const symbol = rawSymbol.trim().toUpperCase();
  const accountCurrency = normalizePortfolioDisplayCurrency(accountBaseCurrency);

  if (!symbol) {
    return accountCurrency;
  }
  if (/^\d{4,5}\.HK$/.test(symbol) || /^HK:\d{4,5}$/.test(symbol)) {
    return 'HKD';
  }
  if (/^\d{6}(\.(SH|SZ))?$/.test(symbol) || /^(SH|SZ):\d{6}$/.test(symbol)) {
    return 'CNY';
  }
  if (/^(BTC|ETH|BTCUSDT|ETHUSDT)$/.test(symbol)) {
    return 'USD';
  }
  if (/^[A-Z]{1,6}([.-][A-Z])?$/.test(symbol)) {
    return 'USD';
  }
  return accountCurrency;
}
