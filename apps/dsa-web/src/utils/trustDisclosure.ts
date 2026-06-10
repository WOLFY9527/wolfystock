export type TrustDisclosureBucket =
  | 'read-only'
  | 'advisory-only'
  | 'dry-run'
  | 'no-send'
  | 'no-live-quota'
  | 'no-provider-blocking'
  | 'fixture-demo'
  | 'confidence'
  | 'fallback'
  | 'stale'
  | 'partial'
  | 'proxy'
  | 'observe-only'
  | 'blocked'
  | 'insufficient'
  | 'non-advice';

export type CanonicalTrustDisclosureBucket = Exclude<TrustDisclosureBucket, 'insufficient'>;

export type TrustDisclosureChipVariant = 'neutral' | 'success' | 'caution' | 'danger' | 'info';

const TRUST_DISCLOSURE_BUCKET_ORDER: CanonicalTrustDisclosureBucket[] = [
  'read-only',
  'advisory-only',
  'dry-run',
  'no-send',
  'no-live-quota',
  'no-provider-blocking',
  'fixture-demo',
  'confidence',
  'fallback',
  'stale',
  'partial',
  'proxy',
  'observe-only',
  'blocked',
  'non-advice',
];

export const TRUST_DISCLOSURE_LABELS: Record<CanonicalTrustDisclosureBucket, string> = {
  'read-only': '只读',
  'advisory-only': '仅提示',
  'dry-run': '试运行',
  'no-send': '不发送',
  'no-live-quota': '保持观察边界',
  'no-provider-blocking': '不改变数据通路',
  'fixture-demo': '演示数据',
  confidence: '置信度受限',
  fallback: '备用数据',
  stale: '数据过期',
  partial: '覆盖不完整',
  proxy: '代理证据',
  'observe-only': '仅观察',
  blocked: '证据不足',
  'non-advice': '不构成投资建议',
};

export const TRUST_DISCLOSURE_VARIANTS: Record<CanonicalTrustDisclosureBucket, TrustDisclosureChipVariant> = {
  'read-only': 'info',
  'advisory-only': 'info',
  'dry-run': 'info',
  'no-send': 'neutral',
  'no-live-quota': 'neutral',
  'no-provider-blocking': 'neutral',
  'fixture-demo': 'caution',
  confidence: 'caution',
  fallback: 'caution',
  stale: 'caution',
  partial: 'info',
  proxy: 'info',
  'observe-only': 'caution',
  blocked: 'danger',
  'non-advice': 'neutral',
};

function normalizeTerm(value?: string | null): string {
  return String(value || '').trim().toLowerCase().replace(/[\s/-]+/g, '_');
}

function canonicalBucket(bucket: TrustDisclosureBucket): CanonicalTrustDisclosureBucket {
  return bucket === 'insufficient' ? 'blocked' : bucket;
}

const PRIVATE_BETA_TERM_ALLOWLIST: Record<
  | 'read-only'
  | 'advisory-only'
  | 'dry-run'
  | 'no-send'
  | 'no-live-quota'
  | 'no-provider-blocking'
  | 'fixture-demo',
  string[]
> = {
  'read-only': [
    'read_only',
    'read_only_projection',
    'readonly',
    '只读',
  ],
  'advisory-only': [
    'advisory_only',
    'advisory_only_contract',
    'suggestion_only',
    '仅提示',
    '仅建议',
  ],
  'dry-run': [
    'dry_run',
    'dry_run_preview',
    'dryrun',
    'quota_dry_run',
    '试运行',
    '预演',
  ],
  'no-send': [
    'no_send',
    'nosend',
    'no_notification',
    'notification_disabled',
    'delivery_disabled',
    '不发送',
  ],
  'no-live-quota': [
    'no_live_quota',
    'nolivequota',
    'quota_dry_run',
    'live_enforcement_false',
    'liveenforcement=false',
  ],
  'no-provider-blocking': [
    'no_provider_blocking',
    'noproviderblocking',
    'no_provider_enforcement',
    'provider_blocking_false',
    'providerblocking=false',
    'would_block_call_false',
    'wouldblockcall=false',
  ],
  'fixture-demo': [
    'fixture',
    'demo',
    'mock',
    'synthetic',
    'demo_only',
    'provider_fixture_not_decision_grade',
    'synthetic_or_fixture_data_not_decision_grade',
    '演示数据',
  ],
};

function matchesAllowedTerm(normalized: string, bucket: keyof typeof PRIVATE_BETA_TERM_ALLOWLIST): boolean {
  const terms = PRIVATE_BETA_TERM_ALLOWLIST[bucket];
  return terms.some((term) => normalized === term || (term === '演示数据' && normalized.includes(term)));
}

function bucketsFromTerm(value?: string | null): CanonicalTrustDisclosureBucket[] {
  const normalized = normalizeTerm(value);
  if (!normalized) return [];

  const buckets: CanonicalTrustDisclosureBucket[] = [];
  if (matchesAllowedTerm(normalized, 'read-only')) {
    buckets.push('read-only');
  }
  if (matchesAllowedTerm(normalized, 'advisory-only')) {
    buckets.push('advisory-only');
  }
  if (matchesAllowedTerm(normalized, 'dry-run')) {
    buckets.push('dry-run');
  }
  if (matchesAllowedTerm(normalized, 'no-send')) {
    buckets.push('no-send');
  }
  if (matchesAllowedTerm(normalized, 'no-live-quota')) {
    buckets.push('no-live-quota');
  }
  if (matchesAllowedTerm(normalized, 'no-provider-blocking')) {
    buckets.push('no-provider-blocking');
  }
  if (matchesAllowedTerm(normalized, 'fixture-demo')) {
    buckets.push('fixture-demo');
  }
  if (
    normalized.includes('confidence')
    || normalized.includes('cap')
    || normalized.includes('capped')
    || normalized.includes('limited')
    || normalized.includes('degradation')
    || normalized.includes('受限')
    || normalized.includes('低置信')
  ) {
    buckets.push('confidence');
  }
  if (normalized.includes('fallback') || normalized.includes('backup') || normalized.includes('备用')) {
    buckets.push('fallback');
  }
  if (normalized.includes('stale') || normalized.includes('expired') || normalized.includes('过期')) {
    buckets.push('stale');
  }
  if (normalized.includes('partial') || normalized.includes('incomplete') || normalized.includes('coverage') || normalized.includes('覆盖不完整')) {
    buckets.push('partial');
  }
  if (normalized.includes('proxy') || normalized.includes('代理')) {
    buckets.push('proxy');
  }
  if (
    normalized.includes('observe')
    || normalized.includes('observation')
    || normalized.includes('仅观察')
    || normalized.includes('仅供观察')
    || normalized.includes('观察级')
  ) {
    buckets.push('observe-only');
  }
  if (
    normalized.includes('blocked')
    || normalized.includes('insufficient')
    || normalized.includes('missing')
    || normalized.includes('unavailable')
    || normalized.includes('not_enough')
    || normalized.includes('数据不足')
    || normalized.includes('证据不足')
  ) {
    buckets.push('blocked');
  }
  if (
    normalized.includes('non_advice')
    || normalized.includes('not_investment_advice')
    || normalized.includes('not_trading_advice')
    || normalized.includes('不构成')
    || normalized.includes('非投资建议')
  ) {
    buckets.push('non-advice');
  }
  return buckets;
}

export function resolveTrustDisclosureBuckets({
  buckets = [],
  terms = [],
}: {
  buckets?: Array<TrustDisclosureBucket | null | undefined | false>;
  terms?: Array<string | null | undefined>;
}): CanonicalTrustDisclosureBucket[] {
  const resolved = new Set<CanonicalTrustDisclosureBucket>();

  buckets.forEach((bucket) => {
    if (!bucket) return;
    resolved.add(canonicalBucket(bucket));
  });
  terms.forEach((term) => {
    bucketsFromTerm(term).forEach((bucket) => resolved.add(bucket));
  });

  return TRUST_DISCLOSURE_BUCKET_ORDER.filter((bucket) => resolved.has(bucket));
}
