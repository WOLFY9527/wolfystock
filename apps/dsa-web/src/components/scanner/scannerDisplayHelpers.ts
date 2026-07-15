import type {
  ScannerCandidateDiagnostic,
  ScannerCandidateDiagnosticStatus,
} from '../../types/scanner';
import type { TrustDisclosureBucket } from '../../utils/trustDisclosure';

export function consumerTrustNoticeFromBuckets(buckets: TrustDisclosureBucket[], language: 'zh' | 'en'): string | null {
  if (buckets.includes('stale') || buckets.includes('fallback')) {
    return language === 'en'
      ? 'Some results use the latest available data.'
      : '部分结果使用最近一次可用数据。';
  }
  if (buckets.includes('partial') || buckets.includes('proxy')) {
    return language === 'en'
      ? 'Some scan data is temporarily unavailable; current results are for observation.'
      : '部分扫描数据暂不可用，当前结果仅供观察。';
  }
  if (buckets.includes('confidence') || buckets.includes('observe-only')) {
    return language === 'en'
      ? 'Current candidate confidence is low.'
      : '当前候选信号置信度较低。';
  }
  return null;
}

export function normalizeDiagnosticStatus(status: ScannerCandidateDiagnostic['status']): ScannerCandidateDiagnosticStatus {
  return status || 'skipped';
}

export function diagnosticStatusLabel(status: ScannerCandidateDiagnostic['status'], language: 'zh' | 'en'): string {
  const labels: Record<ScannerCandidateDiagnosticStatus, { zh: string; en: string }> = {
    selected: { zh: '入选', en: 'Selected' },
    rejected: { zh: '淘汰', en: 'Rejected' },
    data_failed: { zh: '数据受限', en: 'Limited data' },
    skipped: { zh: '跳过', en: 'Skipped' },
    error: { zh: '数据暂不可用', en: 'Data unavailable' },
    evaluated: { zh: '已评估', en: 'Evaluated' },
  };
  const normalizedStatus = normalizeDiagnosticStatus(status);
  return labels[normalizedStatus]?.[language] || normalizedStatus;
}
