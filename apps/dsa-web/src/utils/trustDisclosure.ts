export type TrustDisclosureBucket =
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
  confidence: '置信度受限',
  fallback: '备用数据',
  stale: '数据过期',
  partial: '覆盖不完整',
  proxy: '代理证据',
  'observe-only': '仅观察',
  blocked: '证据不足',
  'non-advice': '不构成买卖建议',
};

export const TRUST_DISCLOSURE_VARIANTS: Record<CanonicalTrustDisclosureBucket, TrustDisclosureChipVariant> = {
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

function bucketsFromTerm(value?: string | null): CanonicalTrustDisclosureBucket[] {
  const normalized = normalizeTerm(value);
  if (!normalized) return [];

  const buckets: CanonicalTrustDisclosureBucket[] = [];
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

export function trustDisclosureLabel(bucket: TrustDisclosureBucket): string {
  return TRUST_DISCLOSURE_LABELS[canonicalBucket(bucket)];
}
