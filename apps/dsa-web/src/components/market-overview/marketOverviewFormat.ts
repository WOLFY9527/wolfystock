const MARKET_OVERVIEW_TIMESTAMP_FORMATTER = new Intl.DateTimeFormat('sv-SE', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
});

export function formatMarketOverviewTimestamp(value?: string): string {
  const text = String(value || '').trim();
  if (!text) {
    return '';
  }
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return text;
  }
  const parts = MARKET_OVERVIEW_TIMESTAMP_FORMATTER.formatToParts(date);
  const get = (type: string) => parts.find((part) => part.type === type)?.value || '';
  return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')}`;
}
