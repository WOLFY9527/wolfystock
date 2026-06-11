import { describe, expect, it } from 'vitest';
import {
  TRUST_DISCLOSURE_LABELS,
  resolveTrustDisclosureBuckets,
} from '../trustDisclosure';

describe('trustDisclosure', () => {
  it('keeps private-beta boundary buckets in a stable product order', () => {
    expect(resolveTrustDisclosureBuckets({
      buckets: [
        'non-advice',
        'no-provider-blocking',
        'fixture-demo',
        'read-only',
        'no-send',
        'no-live-quota',
        'dry-run',
        'advisory-only',
      ],
    })).toEqual([
      'read-only',
      'advisory-only',
      'dry-run',
      'no-send',
      'no-live-quota',
      'no-provider-blocking',
      'fixture-demo',
      'non-advice',
    ]);
  });

  it('maps backend and operator terms to consumer-safe labels', () => {
    const buckets = resolveTrustDisclosureBuckets({
      terms: [
        'read_only_projection',
        'advisory_only_contract',
        'quota_dry_run',
        'delivery_disabled',
        'liveEnforcement=false',
        'wouldBlockCall=false',
        'synthetic_or_fixture_data_not_decision_grade',
        'not_investment_advice',
      ],
    });
    const labels = buckets.map((bucket) => TRUST_DISCLOSURE_LABELS[bucket]);

    expect(labels).toEqual([
      '只读',
      '仅提示',
      '试运行',
      '不发送',
      '保持观察边界',
      '不改变数据通路',
      '演示数据',
      '不构成投资建议',
    ]);
    expect(labels.join(' ')).not.toMatch(/read_only|quota|provider|liveEnforcement|wouldBlockCall|synthetic_or_fixture/i);
  });
});
