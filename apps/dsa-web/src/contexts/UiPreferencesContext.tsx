/* eslint-disable react-refresh/only-export-components */
import type React from 'react';
import { createContext, useContext, useEffect, useState } from 'react';
import {
  DEFAULT_MARKET_COLOR_CONVENTION,
  getMarketColorPalette,
  MARKET_COLOR_CONVENTION_STORAGE_KEY,
  normalizeMarketColorConvention,
  type MarketColorConvention,
} from '../utils/marketColors';

export type UiFontSize = 'xs' | 's' | 'm' | 'l' | 'xl';
export type UiDataDensity = 'compact' | 'comfortable' | 'relaxed';
export type UiNumberFormat = 'international' | 'zh' | 'full';

const UI_FONT_SIZE_STORAGE_KEY = 'dsa-ui-font-size';
const UI_DATA_DENSITY_STORAGE_KEY = 'dsa-ui-data-density';
const UI_NUMBER_FORMAT_STORAGE_KEY = 'dsa-ui-number-format';

const FONT_SCALE_DESKTOP_MAP: Record<UiFontSize, number> = {
  xs: 0.625,
  s: 0.75,
  m: 0.875,
  l: 1,
  xl: 1.125,
};

const FONT_SCALE_MOBILE_MAP: Record<UiFontSize, number> = {
  xs: 10 / 15,
  s: 12 / 15,
  m: 14 / 15,
  l: 16 / 15,
  xl: 18 / 15,
};

type UiPreferencesContextValue = {
  fontSize: UiFontSize;
  setFontSize: (size: UiFontSize) => void;
  dataDensity: UiDataDensity;
  setDataDensity: (value: UiDataDensity) => void;
  numberFormat: UiNumberFormat;
  setNumberFormat: (value: UiNumberFormat) => void;
  marketColorConvention: MarketColorConvention;
  setMarketColorConvention: (value: MarketColorConvention) => void;
};

function normalizeFontSize(value?: string | null): UiFontSize {
  if (value === 'xs' || value === 's' || value === 'm' || value === 'l' || value === 'xl') {
    return value;
  }
  // Backward compatibility for old persisted options.
  if (value === 'small') {
    return 's';
  }
  if (value === 'large') {
    return 'l';
  }
  return 'm';
}

function normalizeDataDensity(value?: string | null): UiDataDensity {
  if (value === 'compact' || value === 'comfortable' || value === 'relaxed') {
    return value;
  }
  if (value === 'dense') {
    return 'compact';
  }
  return 'comfortable';
}

function normalizeNumberFormat(value?: string | null): UiNumberFormat {
  if (value === 'international' || value === 'zh' || value === 'full') {
    return value;
  }
  if (value === 'cn') {
    return 'zh';
  }
  return 'international';
}

function getStoredFontSize(): UiFontSize {
  if (typeof window === 'undefined') {
    return 'm';
  }
  return normalizeFontSize(window.localStorage.getItem(UI_FONT_SIZE_STORAGE_KEY));
}

function getStoredDataDensity(): UiDataDensity {
  if (typeof window === 'undefined') {
    return 'comfortable';
  }
  return normalizeDataDensity(window.localStorage.getItem(UI_DATA_DENSITY_STORAGE_KEY));
}

function getStoredNumberFormat(): UiNumberFormat {
  if (typeof window === 'undefined') {
    return 'international';
  }
  return normalizeNumberFormat(window.localStorage.getItem(UI_NUMBER_FORMAT_STORAGE_KEY));
}

function getStoredMarketColorConvention(): MarketColorConvention {
  if (typeof window === 'undefined') {
    return DEFAULT_MARKET_COLOR_CONVENTION;
  }
  return normalizeMarketColorConvention(
    window.localStorage.getItem(MARKET_COLOR_CONVENTION_STORAGE_KEY),
  );
}

const defaultContext: UiPreferencesContextValue = {
  fontSize: getStoredFontSize(),
  setFontSize: () => undefined,
  dataDensity: getStoredDataDensity(),
  setDataDensity: () => undefined,
  numberFormat: getStoredNumberFormat(),
  setNumberFormat: () => undefined,
  marketColorConvention: getStoredMarketColorConvention(),
  setMarketColorConvention: () => undefined,
};

const UiPreferencesContext = createContext<UiPreferencesContextValue>(defaultContext);

export const UiPreferencesProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [fontSize, setFontSizeState] = useState<UiFontSize>(() => getStoredFontSize());
  const [dataDensity, setDataDensityState] = useState<UiDataDensity>(() => getStoredDataDensity());
  const [numberFormat, setNumberFormatState] = useState<UiNumberFormat>(() => getStoredNumberFormat());
  const [marketColorConvention, setMarketColorConventionState] = useState<MarketColorConvention>(
    () => getStoredMarketColorConvention(),
  );

  useEffect(() => {
    const normalized = normalizeFontSize(fontSize);
    const desktopScale = FONT_SCALE_DESKTOP_MAP[normalized];
    const mobileScale = FONT_SCALE_MOBILE_MAP[normalized];
    document.documentElement.style.setProperty('--ui-font-scale-desktop', String(desktopScale));
    document.documentElement.style.setProperty('--ui-font-scale-mobile', String(mobileScale));
    document.documentElement.setAttribute('data-ui-font-size', normalized);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(UI_FONT_SIZE_STORAGE_KEY, normalized);
    }
  }, [fontSize]);

  useEffect(() => {
    const normalized = normalizeDataDensity(dataDensity);
    document.documentElement.setAttribute('data-ui-density', normalized);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(UI_DATA_DENSITY_STORAGE_KEY, normalized);
    }
  }, [dataDensity]);

  useEffect(() => {
    const normalized = normalizeNumberFormat(numberFormat);
    document.documentElement.setAttribute('data-ui-number-format', normalized);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(UI_NUMBER_FORMAT_STORAGE_KEY, normalized);
    }
  }, [numberFormat]);

  useEffect(() => {
    const normalized = normalizeMarketColorConvention(marketColorConvention);
    const palette = getMarketColorPalette(normalized);
    document.documentElement.style.setProperty('--market-up-hsl', palette.upHsl);
    document.documentElement.style.setProperty('--market-down-hsl', palette.downHsl);
    document.documentElement.setAttribute('data-market-color-convention', normalized);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(MARKET_COLOR_CONVENTION_STORAGE_KEY, normalized);
    }
  }, [marketColorConvention]);

  const value: UiPreferencesContextValue = {
    fontSize,
    setFontSize: (size) => setFontSizeState(normalizeFontSize(size)),
    dataDensity,
    setDataDensity: (value) => setDataDensityState(normalizeDataDensity(value)),
    numberFormat,
    setNumberFormat: (value) => setNumberFormatState(normalizeNumberFormat(value)),
    marketColorConvention,
    setMarketColorConvention: (value) => {
      setMarketColorConventionState(normalizeMarketColorConvention(value));
    },
  };

  return (
    <UiPreferencesContext.Provider value={value}>
      {children}
    </UiPreferencesContext.Provider>
  );
};

export function useUiPreferences(): UiPreferencesContextValue {
  return useContext(UiPreferencesContext);
}
