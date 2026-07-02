export type UserFacingIssueLocale = 'zh' | 'en';

function normalizeIssue(value?: string | null): string {
  return String(value || '')
    .trim()
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .toLowerCase()
    .replace(/[:=./\\\s-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
}

const EXACT_REASON_LABELS: Record<string, { zh: string; en: string }> = {
  freshness_blocked_fallback: {
    zh: '当前以延迟或替代数据为主，先保持观察。',
    en: 'Delayed or fallback data is currently in use. Observe only for now.',
  },
  proxy_or_sample_evidence_blocked: {
    zh: '当前证据以替代或样例数据为主，先保持观察。',
    en: 'Current evidence is based on proxy or sample inputs. Observe only for now.',
  },
  source_authority_or_score_gate_blocked: {
    zh: '当前来源授权或评分条件未满足，暂不形成进一步判断。',
    en: 'Source authority or scoring conditions are not yet met. No further judgment for now.',
  },
  live_gex_not_implemented_v1: {
    zh: '实时 Gamma 观察暂未提供。',
    en: 'Live gamma observation is not available yet.',
  },
  option_chain_unavailable: {
    zh: '期权链数据暂不可用。',
    en: 'Options chain data is temporarily unavailable.',
  },
  observation_only_not_decision_grade: {
    zh: '当前仅达到观察级，暂不形成判断。',
    en: 'Current evidence is observation-only and not decision-grade.',
  },
  missing_spot_reference: {
    zh: '缺少标的现价参考，暂不形成判断。',
    en: 'A spot reference is missing, so no judgment is formed for now.',
  },
  insufficient_usable_contracts: {
    zh: '可用合约不足，暂不形成判断。',
    en: 'There are not enough usable contracts to form a judgment.',
  },
  methodology_approval_missing: {
    zh: '当前方法学确认未完成，先保持观察。',
    en: 'Methodology approval is still pending. Observe only for now.',
  },
  provider_authority_missing: {
    zh: '当前来源授权信息不足，先保持观察。',
    en: 'Source authority details are incomplete. Observe only for now.',
  },
  redistribution_rights_missing: {
    zh: '当前数据使用权限未确认，先保持观察。',
    en: 'Data usage rights are not yet confirmed. Observe only for now.',
  },
  freshness_unavailable: {
    zh: '当前时效状态未确认，数据暂不可用。',
    en: 'Freshness status is unconfirmed and the data is temporarily unavailable.',
  },
  avoid_low_evidence: {
    zh: '当前证据质量偏弱，先保持观察。',
    en: 'Evidence quality is currently limited. Observe only for now.',
  },
  source_refs: {
    zh: '部分来源细节已折叠。',
    en: 'Some source details are collapsed.',
  },
  sourcerefs: {
    zh: '部分来源细节已折叠。',
    en: 'Some source details are collapsed.',
  },
  reason_codes: {
    zh: '部分诊断细节已折叠。',
    en: 'Some diagnostic details are collapsed.',
  },
  reasoncodes: {
    zh: '部分诊断细节已折叠。',
    en: 'Some diagnostic details are collapsed.',
  },
  fx_fallback_1_to_1: {
    zh: '汇率数据暂不可用',
    en: 'FX data unavailable',
  },
  price_fallback: {
    zh: '价格数据暂不可完整确认',
    en: 'Price data incomplete',
  },
};

function exactReasonLabel(normalized: string, locale: UserFacingIssueLocale): string | null {
  return EXACT_REASON_LABELS[normalized]?.[locale] || null;
}

function looksLikeInternalIssue(value?: string | null): boolean {
  const raw = String(value || '').trim();
  if (!raw) return false;
  const lowered = raw.toLowerCase();
  const normalized = normalizeIssue(raw);
  return /[.:=]/.test(raw)
    || /\b[a-z0-9]+_[a-z0-9_]+\b/.test(lowered)
    || /\b(?:provider|authority|freshness|schema|debug|trace|diagnostic|runtime|cache|raw|reason|score|observationonly|decisiongrade|contract|gamma|gex|methodology|redistribution|fallback|proxy|unavailable|insufficient|missing|quote|realtime|snapshot|data|failed|error|news|fundamental|fundamentals|fx|price)\b/.test(lowered)
    || /(?:source_?refs?|reason_?codes?)/.test(normalized);
}

function mapInternalReasonToUserMessage(
  value?: string | null,
  locale: UserFacingIssueLocale = 'zh',
): string {
  const normalized = normalizeIssue(value);
  const isEnglish = locale === 'en';
  const raw = String(value || '').trim();

  if (!normalized) {
    return isEnglish ? 'Data availability unconfirmed' : '数据不足';
  }
  const exactLabel = exactReasonLabel(normalized, locale);
  if (exactLabel) {
    return exactLabel;
  }
  if (!looksLikeInternalIssue(raw)) {
    return raw;
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
  if (normalized.includes('fx_fallback') || (normalized.includes('fx') && (normalized.includes('unavailable') || normalized.includes('missing') || normalized.includes('fallback')))) {
    return isEnglish ? 'FX data unavailable' : '汇率数据暂不可用';
  }
  if (normalized.includes('price_fallback') || (normalized.includes('price') && normalized.includes('fallback'))) {
    return isEnglish ? 'Price data incomplete' : '价格数据暂不可完整确认';
  }
  if (normalized.includes('quote') || normalized.includes('realtime') || normalized.includes('snapshot')) {
    return isEnglish ? 'Realtime missing' : '实时缺失';
  }
  if (normalized.includes('freshness') || normalized.includes('fallback') || normalized.includes('proxy')) {
    return isEnglish ? 'Delayed or proxy data in use' : '当前以延迟或替代数据为主，先保持观察。';
  }
  if (normalized.includes('authority') || normalized.includes('approval') || normalized.includes('rights')) {
    return isEnglish ? 'Required authority checks are still pending' : '当前授权或方法学确认未完成，先保持观察。';
  }
  if (normalized.includes('observation_only') || normalized.includes('decision_grade')) {
    return isEnglish ? 'Observation-only for now' : '当前仅达到观察级，暂不形成判断。';
  }
  if (normalized.includes('option_chain')) {
    return isEnglish ? 'Options chain data temporarily unavailable' : '期权链数据暂不可用。';
  }
  if (normalized.includes('contract')) {
    return isEnglish ? 'Contracts available are still insufficient' : '可用合约不足，暂不形成判断。';
  }
  if (normalized.includes('spot_reference')) {
    return isEnglish ? 'Spot reference is still missing' : '缺少标的现价参考，暂不形成判断。';
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

export function sanitizeUserFacingDataIssues(
  values: Array<string | null | undefined>,
  locale: UserFacingIssueLocale = 'zh',
): string[] {
  const seen = new Set<string>();
  const labels: string[] = [];

  values.forEach((value) => {
    const label = sanitizeUserFacingDataIssue(value, locale).trim();
    if (!label || seen.has(label)) return;
    seen.add(label);
    labels.push(label);
  });

  return labels;
}
