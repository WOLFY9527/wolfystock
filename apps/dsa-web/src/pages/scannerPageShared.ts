import type { ScannerDataReadiness } from '../api/scanner';
import type { UiLanguage } from '../i18n/core';
import type { ScannerRunDetail } from '../types/scanner';

export type ScannerMarket = 'cn' | 'us' | 'hk';

export type ScannerSelectOption = {
  value: string;
  label: string;
};

export const SCANNER_HISTORICAL_PROFILE = 'us_historical_research_v1';
export const SCANNER_HISTORICAL_EVALUATION_MODE = 'historical_development' as const;

export type ScannerPersistedHistoricalRunPresentation = {
  outcomeSentence: string;
  runStateLabel: string;
  freshnessSummary: string;
  nextAction: string;
};

const SCANNER_SHARED_DATE_ONLY_FORMATTERS = {
  en: new Intl.DateTimeFormat('en-US', { year: 'numeric', month: '2-digit', day: '2-digit' }),
  zh: new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }),
} as const;

function normalizeScannerSharedState(value: string | null | undefined): string {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function scannerSharedDateOnly(value: string, language: UiLanguage): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : SCANNER_SHARED_DATE_ONLY_FORMATTERS[language].format(date);
}

function scannerRunSummaryCount(
  runDetail: ScannerRunDetail,
  key: keyof NonNullable<ScannerRunDetail['summary']>,
  fallback = 0,
): number {
  const value = runDetail.summary?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

export function historicalScannerRunPresentation(
  runDetail: ScannerRunDetail | null,
  readiness: ScannerDataReadiness | null,
  language: UiLanguage,
): ScannerPersistedHistoricalRunPresentation | null {
  if (!runDetail) return null;
  const isHistoricalRun = runDetail.evaluationMode === SCANNER_HISTORICAL_EVALUATION_MODE
    || isHistoricalScannerProfile(runDetail.profile);
  if (!isHistoricalRun) return null;

  const runState = normalizeScannerSharedState(runDetail.status);
  const isCompletedRun = ['completed', 'complete', 'success', 'succeeded'].includes(runState);
  const selectedCount = scannerRunSummaryCount(runDetail, 'selectedCount', runDetail.shortlist?.length || 0);
  const rejectedCount = scannerRunSummaryCount(runDetail, 'rejectedCount', 0);
  const dataFailedCount = scannerRunSummaryCount(runDetail, 'dataFailedCount', 0)
    + scannerRunSummaryCount(runDetail, 'errorCount', 0);
  const isDataFailedOutcome = isCompletedRun
    && selectedCount === 0
    && rejectedCount === 0
    && dataFailedCount > 0;
  const isFailedRun = ['failed', 'failure', 'error', 'data_failed'].includes(runState)
    || isDataFailedOutcome;
  const isPartialRun = ['partial', 'partial_data', 'partial_success', 'incomplete'].includes(runState);
  if (!isCompletedRun && !isFailedRun && !isPartialRun) return null;
  const hasCompletedOutcome = isCompletedRun && !isDataFailedOutcome;

  const outcomeSentence = isFailedRun
    ? (language === 'en'
      ? 'Historical development replay failed; no completed result is available.'
      : '历史开发回放失败；没有可用的完整结果。')
    : isPartialRun
      ? (language === 'en'
        ? `Historical development replay remains partial with ${selectedCount} retained candidate${selectedCount === 1 ? '' : 's'}; it is not a completed run.`
        : `历史开发回放仍为部分完成，保留 ${selectedCount} 个候选；不得将其视为完整运行。`)
      : selectedCount > 0
        ? (language === 'en'
          ? `Historical development replay completed with ${selectedCount} candidate${selectedCount === 1 ? '' : 's'}; the persisted result remains available for research review.`
          : `历史开发回放已完成，形成 ${selectedCount} 个候选；该持久化结果仍可用于研究复核。`)
        : (language === 'en'
          ? 'Historical development replay completed with no selected candidates; this is an empty completed result, not a failed run.'
          : '历史开发回放已完成，但未形成入选候选；这是已完成的空结果，不是运行失败。');
  const runStateLabel = isFailedRun
    ? (language === 'en' ? 'Historical replay failed' : '历史回放失败')
    : isPartialRun
      ? (language === 'en' ? 'Historical replay partial' : '历史回放部分完成')
      : (language === 'en' ? 'Historical replay completed' : '历史回放已完成');

  const universeReadiness = readiness?.scannerUniverseReadiness || null;
  const universeStatus = normalizeScannerSharedState(universeReadiness?.status);
  const freshness = normalizeScannerSharedState(readiness?.freshness);
  const snapshotDate = universeReadiness?.lastUpdatedAt
    ? scannerSharedDateOnly(universeReadiness.lastUpdatedAt, language)
    : null;
  const cutoffDate = runDetail.evaluationCutoff
    ? scannerSharedDateOnly(runDetail.evaluationCutoff, language)
    : null;
  const timingPrefix = snapshotDate
    ? (language === 'en' ? `Universe snapshot ${snapshotDate}` : `标的池快照 ${snapshotDate}`)
    : cutoffDate
      ? (language === 'en'
        ? `Evaluation cutoff ${cutoffDate}; universe snapshot freshness`
        : `评估截止日 ${cutoffDate}；标的池快照新鲜度`)
      : (language === 'en' ? 'Universe snapshot freshness' : '标的池快照新鲜度');

  if (universeStatus === 'stale' || freshness === 'stale') {
    return {
      outcomeSentence,
      runStateLabel,
      freshnessSummary: language === 'en'
        ? `${timingPrefix} is stale${hasCompletedOutcome ? ' for a new current-market run' : ''}.`
        : `${timingPrefix}${hasCompletedOutcome ? '对新一轮当前市场扫描' : ''}已过期。`,
      nextAction: hasCompletedOutcome
        ? (language === 'en'
          ? 'Refresh the universe before a new current-market run. This completed historical result remains available for review.'
          : '新一轮当前市场扫描前更新标的池；本次已完成的历史结果仍可继续复核。')
        : (language === 'en'
          ? 'Review this run\'s incomplete evidence, then refresh the universe before retrying.'
          : '先复核本次运行的不完整证据，再更新标的池后重试。'),
    };
  }

  if (['fresh', 'current'].includes(freshness)) {
    return {
      outcomeSentence,
      runStateLabel,
      freshnessSummary: language === 'en'
        ? `${timingPrefix} is current for a new run.`
        : `${timingPrefix}对新一轮扫描仍为当前状态。`,
      nextAction: hasCompletedOutcome
        ? (language === 'en'
          ? 'Keep this replay historical and observation-only; start a new run for current-market discovery.'
          : '本次回放仍仅作历史观察；如需当前市场发现，请启动新一轮扫描。')
        : (language === 'en'
          ? 'Review the failed or partial run evidence before retrying; current universe freshness does not make the run complete.'
          : '重试前先复核运行失败或部分完成的证据；标的池当前新鲜也不会使该运行变为完整。'),
    };
  }

  const freshnessUnavailable = ['missing', 'unavailable', 'not_configured'].includes(universeStatus)
    || ['missing', 'unavailable', 'not_configured'].includes(freshness);
  return {
    outcomeSentence,
    runStateLabel,
      freshnessSummary: language === 'en'
      ? `${timingPrefix} is ${freshnessUnavailable ? 'unavailable' : 'not confirmed'}. No current state is assumed.`
      : `${timingPrefix}${freshnessUnavailable ? '不可用' : '尚未确认'}；不据此假定为当前状态。`,
    nextAction: hasCompletedOutcome
      ? (language === 'en'
        ? 'Confirm universe freshness before starting a future current-market run; keep this persisted replay historical and observation-only.'
        : '启动未来的新一轮当前市场扫描前先确认标的池新鲜度；本次持久化回放仍仅作历史观察。')
      : (language === 'en'
        ? 'Review the failed or partial run evidence and confirm universe freshness before retrying.'
        : '先复核运行失败或部分完成的证据，并在重试前确认标的池新鲜度。'),
  };
}

export function isHistoricalScannerProfile(profile: string): boolean {
  return profile === SCANNER_HISTORICAL_PROFILE;
}

export const SCANNER_PROFILE_DEFAULTS: Record<ScannerMarket, {
  profile: string;
  shortlistSize: string;
  universeLimit: string;
  detailLimit: string;
}> = {
  cn: {
    profile: 'cn_preopen_v1',
    shortlistSize: '5',
    universeLimit: '300',
    detailLimit: '60',
  },
  us: {
    profile: 'us_preopen_v1',
    shortlistSize: '5',
    universeLimit: '180',
    detailLimit: '40',
  },
  hk: {
    profile: 'hk_preopen_v1',
    shortlistSize: '5',
    universeLimit: '120',
    detailLimit: '30',
  },
};

export function getScannerProfileOptions(
  market: ScannerMarket,
  t: (key: string) => string,
): ScannerSelectOption[] {
  if (market === 'us') {
    return [
      { value: 'us_preopen_v1', label: t('scanner.profileOptionUs') },
      { value: SCANNER_HISTORICAL_PROFILE, label: t('scanner.profileOptionUsHistorical') },
    ];
  }
  if (market === 'hk') {
    return [{ value: 'hk_preopen_v1', label: t('scanner.profileOptionHk') }];
  }
  return [{ value: 'cn_preopen_v1', label: t('scanner.profileOptionCn') }];
}

export function getScannerUniverseOptions(
  market: ScannerMarket,
  language: UiLanguage,
): ScannerSelectOption[] {
  if (market === 'us') {
    return [
      { value: '120', label: '120' },
      { value: '180', label: '180' },
      { value: '240', label: '240' },
    ];
  }
  if (market === 'hk') {
    return [
      { value: '80', label: '80' },
      { value: '120', label: '120' },
      { value: '180', label: '180' },
    ];
  }
  return [
    { value: '200', label: language === 'en' ? '200' : '200 只' },
    { value: '300', label: language === 'en' ? '300' : '300 只' },
    { value: '500', label: language === 'en' ? '500' : '500 只' },
  ];
}

export function getScannerDetailOptions(
  market: ScannerMarket,
  language: UiLanguage,
): ScannerSelectOption[] {
  if (market === 'us') {
    return [
      { value: '30', label: '30' },
      { value: '40', label: '40' },
      { value: '60', label: '60' },
    ];
  }
  if (market === 'hk') {
    return [
      { value: '20', label: '20' },
      { value: '30', label: '30' },
      { value: '40', label: '40' },
    ];
  }
  return [
    { value: '40', label: language === 'en' ? '40' : '40 只' },
    { value: '60', label: language === 'en' ? '60' : '60 只' },
    { value: '80', label: language === 'en' ? '80' : '80 只' },
  ];
}
