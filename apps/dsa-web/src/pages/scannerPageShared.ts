import type { UiLanguage } from '../i18n/core';

export type ScannerMarket = 'cn' | 'us' | 'hk';

export type ScannerSelectOption = {
  value: string;
  label: string;
};

export const SCANNER_HISTORICAL_PROFILE = 'us_historical_research_v1';
export const SCANNER_HISTORICAL_EVALUATION_MODE = 'historical_development' as const;

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
