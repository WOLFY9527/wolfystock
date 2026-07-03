export type ConsumerDataQualityGlossarySeverity = 'info' | 'warning' | 'critical';

export interface ConsumerDataQualityGlossaryEntry {
  safeLabel: string;
  shortExplanation: string;
  severity: ConsumerDataQualityGlossarySeverity;
  observationOnly: boolean;
  nextStep?: string;
}

type GlossaryKey =
  | 'stale'
  | 'partial'
  | 'unavailable'
  | 'degraded'
  | 'fallback'
  | 'demo'
  | 'proxy_sample_evidence'
  | 'missing_evidence'
  | 'source_authority_limitation'
  | 'score_gate_limitation'
  | 'freshness_limitation'
  | 'unknown';

const GLOSSARY: Record<GlossaryKey, ConsumerDataQualityGlossaryEntry> = {
  stale: {
    safeLabel: '数据有延迟',
    shortExplanation: '当前展示的是最近一次可用信息，时效性需要复核。',
    severity: 'warning',
    observationOnly: true,
  },
  partial: {
    safeLabel: '证据不完整',
    shortExplanation: '部分信息暂缺，当前结论只能作为观察线索。',
    severity: 'warning',
    observationOnly: true,
  },
  unavailable: {
    safeLabel: '数据暂不可用',
    shortExplanation: '当前模块缺少足够信息，请稍后刷新后再查看。',
    severity: 'critical',
    observationOnly: true,
  },
  degraded: {
    safeLabel: '质量受限',
    shortExplanation: '当前信息完整度或稳定性不足，需要降低解读强度。',
    severity: 'warning',
    observationOnly: true,
  },
  fallback: {
    safeLabel: '使用替代信息',
    shortExplanation: '当前使用最近可用或替代来源的信息，不代表实时状态。',
    severity: 'warning',
    observationOnly: true,
  },
  demo: {
    safeLabel: '演示信息',
    shortExplanation: '当前内容仅用于功能展示，不能作为真实市场依据。',
    severity: 'info',
    observationOnly: true,
  },
  proxy_sample_evidence: {
    safeLabel: '替代证据',
    shortExplanation: '当前证据来自替代或样例信息，只适合做方向性观察。',
    severity: 'warning',
    observationOnly: true,
  },
  missing_evidence: {
    safeLabel: '证据缺口',
    shortExplanation: '关键证据仍在补齐，暂不形成进一步判断。',
    severity: 'critical',
    observationOnly: true,
  },
  source_authority_limitation: {
    safeLabel: '来源待确认',
    shortExplanation: '当前来源条件未完全确认，先保持观察。',
    severity: 'warning',
    observationOnly: true,
  },
  score_gate_limitation: {
    safeLabel: '评分暂不启用',
    shortExplanation: '当前信息未进入评分口径，不能提升结论强度。',
    severity: 'warning',
    observationOnly: true,
  },
  freshness_limitation: {
    safeLabel: '时效待确认',
    shortExplanation: '当前时效状态仍需确认，解读时请保留不确定性。',
    severity: 'warning',
    observationOnly: true,
  },
  unknown: {
    safeLabel: '证据待确认',
    shortExplanation: '当前信息仍需补充核验，先作为观察线索处理。',
    severity: 'warning',
    observationOnly: true,
  },
};

function normalizeGlossaryToken(value?: string | null): string {
  return String(value || '')
    .trim()
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .toLowerCase()
    .replace(/[:=./\\\s-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function resolveGlossaryKey(value?: string | null): GlossaryKey {
  const token = normalizeGlossaryToken(value);

  if (!token) return 'unknown';
  if (/(?:source_?refs?|reason_?codes?|raw|debug|diagnostic|trace|runtime|cache|payload)/.test(token)) return 'missing_evidence';
  if (token.includes('source_authority') || token.includes('authority_denied') || token.includes('authority_missing')) return 'source_authority_limitation';
  if (token.includes('score_contribution') || token.includes('score_gate') || token.includes('score_rights')) return 'score_gate_limitation';
  if (token.includes('freshness')) return token.includes('unavailable') ? 'unavailable' : 'freshness_limitation';
  if (token.includes('unavailable') || token.includes('provider_timeout') || token.includes('timeout')) return 'unavailable';
  if (token.includes('missing') || token.includes('insufficient') || token.includes('gap')) return 'missing_evidence';
  if (token.includes('proxy') || token.includes('sample')) return 'proxy_sample_evidence';
  if (token.includes('fallback')) return 'fallback';
  if (token.includes('demo') || token.includes('fixture') || token.includes('mock') || token.includes('synthetic')) return 'demo';
  if (token.includes('partial')) return 'partial';
  if (token.includes('degraded')) return 'degraded';
  if (token.includes('stale') || token.includes('delayed') || token.includes('expired')) return 'stale';

  return 'unknown';
}

export function createConsumerDataQualityGlossaryEntry(
  value?: string | null,
): ConsumerDataQualityGlossaryEntry {
  return { ...GLOSSARY[resolveGlossaryKey(value)] };
}
