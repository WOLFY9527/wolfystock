import { describe, expect, it } from 'vitest';

import {
  consumerTrustNoticeFromBuckets,
  diagnosticStatusLabel,
  normalizeDiagnosticStatus,
} from '../scannerDisplayHelpers';

describe('scannerDisplayHelpers', () => {
  it('preserves consumer trust notice priority and no-advice wording', () => {
    expect(consumerTrustNoticeFromBuckets([], 'zh')).toBeNull();
    expect(consumerTrustNoticeFromBuckets(['stale'], 'zh')).toBe('部分结果使用最近一次可用数据。');
    expect(consumerTrustNoticeFromBuckets(['fallback'], 'en')).toBe('Some results use the latest available data.');
    expect(consumerTrustNoticeFromBuckets(['proxy'], 'zh')).toBe('部分扫描数据暂不可用，当前结果仅供观察。');
    expect(consumerTrustNoticeFromBuckets(['partial'], 'en')).toBe('Some scan data is temporarily unavailable; current results are for observation.');
    expect(consumerTrustNoticeFromBuckets(['observe-only'], 'zh')).toBe('当前候选信号置信度较低。');
    expect(consumerTrustNoticeFromBuckets(['confidence'], 'en')).toBe('Current candidate confidence is low.');
    expect(consumerTrustNoticeFromBuckets(['proxy', 'stale'], 'zh')).toBe('部分结果使用最近一次可用数据。');
  });

  it('preserves scanner diagnostic labels for selected, rejected and data-failed states', () => {
    expect(diagnosticStatusLabel('selected', 'zh')).toBe('入选');
    expect(diagnosticStatusLabel('selected', 'en')).toBe('Selected');
    expect(diagnosticStatusLabel('rejected', 'zh')).toBe('淘汰');
    expect(diagnosticStatusLabel('rejected', 'en')).toBe('Rejected');
    expect(diagnosticStatusLabel('data_failed', 'zh')).toBe('数据受限');
    expect(diagnosticStatusLabel('data_failed', 'en')).toBe('Limited data');
    expect(diagnosticStatusLabel(undefined, 'zh')).toBe('跳过');
    expect(diagnosticStatusLabel('error', 'en')).toBe('Data unavailable');
    expect(normalizeDiagnosticStatus(undefined)).toBe('skipped');
    expect(normalizeDiagnosticStatus('selected')).toBe('selected');
  });
});
