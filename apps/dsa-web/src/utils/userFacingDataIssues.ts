export type DiagnosticAudience = 'user' | 'admin';
export type UserFacingIssueLocale = 'zh' | 'en';

function normalizeIssue(value?: string | null): string {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

export function isDeveloperDiagnosticAllowed(audience: DiagnosticAudience = 'user'): boolean {
  return audience === 'admin';
}

export function mapInternalReasonToUserMessage(
  value?: string | null,
  locale: UserFacingIssueLocale = 'zh',
): string {
  const normalized = normalizeIssue(value);
  const isEnglish = locale === 'en';

  if (!normalized) {
    return isEnglish ? 'Data availability unconfirmed' : '数据不足';
  }
  if (normalized.includes('optional_news_timeout') || normalized.includes('news')) {
    return isEnglish ? 'News data temporarily unavailable' : '新闻数据暂缺';
  }
  if (normalized.includes('fundamentals_unavailable') || normalized.includes('fundamental')) {
    return isEnglish ? 'Fundamental data missing' : '基本面数据缺失';
  }
  if (normalized.includes('earnings_unavailable') || normalized.includes('earning')) {
    return isEnglish ? 'Earnings data temporarily unavailable' : '财报数据暂缺';
  }
  if (normalized.includes('technical_indicators_unavailable') || normalized.includes('technical')) {
    return isEnglish ? 'Technical indicator data insufficient' : '技术指标数据不足';
  }
  if (normalized.includes('not_enough_history') || normalized.includes('history')) {
    return isEnglish ? 'Historical data insufficient' : '历史数据不足';
  }
  if (normalized.includes('provider_timeout') || normalized.includes('timeout') || normalized.includes('provider')) {
    return isEnglish ? 'Some external data is temporarily unavailable' : '部分外部数据暂不可用';
  }
  if (
    normalized.includes('unavailable')
    || normalized.includes('missing')
    || normalized.includes('insufficient')
    || normalized.includes('not_enough')
    || normalized.includes('data_failed')
  ) {
    return isEnglish ? 'Data insufficient, observe only' : '数据不足，结论仅供观察';
  }

  return isEnglish ? 'Data insufficient, observe only' : '数据不足，结论仅供观察';
}

export function sanitizeUserFacingDataIssue(
  value?: string | null,
  locale: UserFacingIssueLocale = 'zh',
): string {
  return mapInternalReasonToUserMessage(value, locale);
}
