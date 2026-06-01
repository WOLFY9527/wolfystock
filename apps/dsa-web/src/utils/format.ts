const MISSING_VALUE = '--';

type DateFormatOptions = {
  locale?: string;
  timeZone?: string;
};

type NumberFormatOptions = {
  locale?: string;
  digits?: number;
};

type PercentFormatOptions = NumberFormatOptions & {
  mode?: 'percent' | 'ratio';
};

type CurrencyFormatOptions = {
  locale?: string;
  currency?: string;
  digits?: number;
};

type SignedFormatOptions = NumberFormatOptions & {
  showZeroSign?: boolean;
};

function dateTimeFormatCacheKey(locale: string, timeZone: string, opts: Intl.DateTimeFormatOptions): string {
  return `${locale}|${timeZone}|${JSON.stringify(opts)}`;
}

function numberFormatCacheKey(locale: string, opts: Intl.NumberFormatOptions): string {
  return `${locale}|${JSON.stringify(opts)}`;
}

const dateTimeFormatCache = new Map<string, Intl.DateTimeFormat>();
const numberFormatCache = new Map<string, Intl.NumberFormat>();

function getDateTimeFormat(locale: string, timeZone: string, opts: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = dateTimeFormatCacheKey(locale, timeZone, opts);
  let fmt = dateTimeFormatCache.get(key);
  if (!fmt) {
    fmt = Intl.DateTimeFormat(locale, { ...opts, timeZone });
    dateTimeFormatCache.set(key, fmt);
  }
  return fmt;
}

function getNumberFormat(locale: string, opts: Intl.NumberFormatOptions): Intl.NumberFormat {
  const key = numberFormatCacheKey(locale, opts);
  let fmt = numberFormatCache.get(key);
  if (!fmt) {
    fmt = Intl.NumberFormat(locale, opts);
    numberFormatCache.set(key, fmt);
  }
  return fmt;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function parseFiniteNumber(value: unknown): number | null {
  if (isFiniteNumber(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function parseDate(value: unknown): Date | null {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  if (typeof value === 'string' || typeof value === 'number') {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  return null;
}

function formatDateLike(
  value: unknown,
  options: DateFormatOptions,
  dateTimeFormatOptions: Intl.DateTimeFormatOptions,
): string {
  const date = parseDate(value);
  if (!date) return MISSING_VALUE;
  const locale = options.locale || 'zh-CN';
  const timeZone = options.timeZone || 'Asia/Shanghai';
  return getDateTimeFormat(locale, timeZone, dateTimeFormatOptions).format(date);
}

function formatNumberLike(value: unknown, options: NumberFormatOptions, extra: Intl.NumberFormatOptions): string {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return MISSING_VALUE;
  const locale = options.locale || 'zh-CN';
  const opts: Intl.NumberFormatOptions = {
    ...extra,
    minimumFractionDigits: options.digits ?? extra.minimumFractionDigits ?? 0,
    maximumFractionDigits: options.digits ?? extra.maximumFractionDigits ?? 2,
  };
  return getNumberFormat(locale, opts).format(numeric);
}

export const formatDateTime = (value?: unknown, options: DateFormatOptions = {}): string => formatDateLike(value, options, {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

export const formatNumber = (value?: unknown, digits = 2, options: NumberFormatOptions = {}): string =>
  formatNumberLike(value, { ...options, digits }, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

export const formatCompactNumber = (value?: unknown, options: NumberFormatOptions = {}): string => {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return MISSING_VALUE;
  const locale = options.locale || 'zh-CN';
  return getNumberFormat(locale, {
    notation: 'compact',
    compactDisplay: 'short',
    maximumFractionDigits: options.digits ?? 1,
  }).format(numeric);
};

export const formatPercent = (value?: unknown, options: PercentFormatOptions = {}): string => {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return MISSING_VALUE;
  const percentValue = options.mode === 'ratio' ? numeric * 100 : numeric;
  const locale = options.locale || 'zh-CN';
  return getNumberFormat(locale, {
    minimumFractionDigits: options.digits ?? 1,
    maximumFractionDigits: options.digits ?? 1,
  }).format(percentValue) + '%';
};

export const formatSignedNumber = (value?: unknown, digits = 2, options: SignedFormatOptions = {}): string => {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return MISSING_VALUE;
  const { showZeroSign, ...numberOptions } = options;
  const sign = numeric > 0 ? '+' : numeric < 0 ? '-' : showZeroSign ? '+' : '';
  return `${sign}${formatNumber(Math.abs(numeric), digits, numberOptions)}`;
};

export const formatSignedPercent = (value?: unknown, options: PercentFormatOptions & { showZeroSign?: boolean } = {}): string => {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return MISSING_VALUE;
  const { showZeroSign, ...percentOptions } = options;
  const sign = numeric > 0 ? '+' : numeric < 0 ? '-' : showZeroSign ? '+' : '';
  return `${sign}${formatPercent(Math.abs(numeric), percentOptions)}`;
};

export const formatCurrency = (value?: unknown, options: CurrencyFormatOptions = {}): string => {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return MISSING_VALUE;
  const locale = options.locale || 'zh-CN';
  return getNumberFormat(locale, {
    style: 'currency',
    currency: options.currency || 'USD',
    minimumFractionDigits: options.digits ?? 2,
    maximumFractionDigits: options.digits ?? 2,
  }).format(numeric);
};

export const formatDurationMs = (value?: unknown): string => {
  const numeric = parseFiniteNumber(value);
  if (numeric == null || numeric < 0) return MISSING_VALUE;
  if (numeric < 1000) return `${Math.round(numeric)}ms`;
  if (numeric < 60_000) return `${(numeric / 1000).toFixed(1)}s`;
  const totalSeconds = Math.round(numeric / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${seconds}s`;
};

export const toDateInputValue = (date: Date): string => {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
};
