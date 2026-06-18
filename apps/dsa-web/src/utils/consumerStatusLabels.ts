export type ConsumerStatusLocale = 'zh' | 'en';

const TOKEN_LABELS: Record<string, Record<ConsumerStatusLocale, string>> = {
  unavailable: { zh: '数据暂不可用', en: 'Data temporarily unavailable' },
  stale: { zh: '数据可能已过期', en: 'Data may be stale' },
  degraded: { zh: '数据质量受限', en: 'Data quality limited' },
  partial: { zh: '部分证据可用', en: 'Partial evidence available' },
  pending: { zh: '正在等待数据确认', en: 'Waiting for data confirmation' },
  pending_heavy: { zh: '多项数据仍待确认', en: 'Several data points still await confirmation' },
  blocked: { zh: '当前无法分析', en: 'Analysis currently unavailable' },
  proxy: { zh: '间接参考', en: 'Proxy reference' },
  proxy_only: { zh: '仅有间接参考，证据强度受限', en: 'Proxy-only evidence with limited strength' },
  mixed: { zh: '状态不一致', en: 'State not aligned' },
  low_confidence: { zh: '置信度较低', en: 'Confidence limited' },
  score_grade: { zh: '评分等级', en: 'Scoring tier' },
  freshness_unavailable: { zh: '数据新鲜度暂不可用', en: 'Freshness currently unavailable' },
  insufficient_evidence: { zh: '证据不足', en: 'Evidence insufficient' },
  no_data: { zh: '暂无可用数据', en: 'No usable data available' },
  empty: { zh: '暂无可用数据', en: 'No usable data available' },
  unknown: { zh: '状态暂不明确', en: 'State not yet clear' },
  evidence_partial: { zh: '部分证据可用', en: 'Partial evidence available' },
  thin: { zh: '部分证据可用', en: 'Partial evidence available' },
  high: { zh: '高优先', en: 'High priority' },
  medium: { zh: '中优先', en: 'Medium priority' },
  low: { zh: '低优先', en: 'Low priority' },
  strength_continuation: { zh: '强势延续观察', en: 'Strength continuation watch' },
  breakout_watch: { zh: '突破观察', en: 'Breakout watch' },
  event_driven: { zh: '事件驱动观察', en: 'Event-driven watch' },
};

const PHRASE_LABELS: Record<string, Record<ConsumerStatusLocale, string>> = {
  'evidence missing': { zh: '证据不足', en: 'Evidence insufficient' },
  'evidence quality is acceptable': { zh: '证据质量可供继续观察', en: 'Evidence quality is acceptable for observation' },
  'low-evidence filter active': { zh: '当前按低证据条件整理', en: 'Low-evidence filter is active' },
  'relative strength is above the research threshold': { zh: '相对强弱已达到研究阈值', en: 'Relative strength is above the research threshold' },
  'missing evidence needs review': { zh: '证据缺口仍需复核。', en: 'Evidence gaps still need review.' },
  'technicals available': { zh: '技术面证据已整理', en: 'Technical evidence summarized' },
  'scenario lab is unavailable because base score-grade regime evidence is missing': { zh: '基准情景证据不足，当前无法生成情景结果。', en: 'Scenario output is unavailable because the base evidence is insufficient.' },
  'base regime evidence is missing or below the minimum driver coverage for scenario analysis': { zh: '基准情景证据不足，暂不满足情景分析所需的最低驱动覆盖。', en: 'Base regime evidence is below the minimum coverage required for scenario analysis.' },
  'score-grade evidence would need to show the stressed drivers moving together in the scenario direction': { zh: '需要更高质量证据共同确认受压驱动是否同向变化。', en: 'Higher-quality evidence is still needed to confirm whether the stressed drivers move together.' },
  'the scenario frame weakens if score-grade evidence does not move with the selected shocks': { zh: '如果关键证据未随所选冲击同步变化，该情景框架会减弱。', en: 'The scenario frame weakens if the key evidence does not move with the selected shocks.' },
  'gamma evidence status is unavailable, so gamma-sensitive conclusions remain capped': { zh: 'Gamma 相关证据暂不可用，因此相关结论需保持保守。', en: 'Gamma-related evidence is unavailable, so conclusions remain capped.' },
};

function normalizePhraseKey(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/[.。!?]+$/g, '');
}

export function normalizeConsumerStatusToken(value: string | null | undefined): string {
  return String(value || '')
    .trim()
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .toLowerCase()
    .replace(/[:=./\\\s-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
}

export function getConsumerStatusLabel(
  value: string | null | undefined,
  locale: ConsumerStatusLocale = 'zh',
): string | null {
  const token = normalizeConsumerStatusToken(value);
  if (!token) {
    return null;
  }
  return TOKEN_LABELS[token]?.[locale] ?? null;
}

export function mapConsumerStatusText(
  value: string | null | undefined,
  locale: ConsumerStatusLocale = 'zh',
): string {
  const raw = String(value || '').trim();
  if (!raw) {
    return '';
  }

  const exact = PHRASE_LABELS[normalizePhraseKey(raw)];
  if (exact) {
    return exact[locale];
  }

  const tokenLabel = getConsumerStatusLabel(raw, locale);
  if (tokenLabel) {
    return tokenLabel;
  }

  return raw;
}
