export type ProductSetupSurfaceKey =
  | 'market_overview'
  | 'liquidity_monitor'
  | 'rotation_radar'
  | 'portfolio'
  | 'watchlist'
  | 'options_lab';

export type ProductSetupSurface = {
  key: ProductSetupSurfaceKey;
  label: string;
};

export const PRODUCT_SETUP_SURFACE_PARAM = 'surface';

export const PRODUCT_SETUP_SURFACES: Record<ProductSetupSurfaceKey, ProductSetupSurface> = {
  market_overview: {
    key: 'market_overview',
    label: 'Market Overview',
  },
  liquidity_monitor: {
    key: 'liquidity_monitor',
    label: 'Liquidity Monitor',
  },
  rotation_radar: {
    key: 'rotation_radar',
    label: 'Rotation Radar',
  },
  portfolio: {
    key: 'portfolio',
    label: 'Portfolio',
  },
  watchlist: {
    key: 'watchlist',
    label: 'Watchlist',
  },
  options_lab: {
    key: 'options_lab',
    label: 'Options Lab',
  },
};

export function resolveProductSetupSurface(value: unknown): ProductSetupSurface | null {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized || !(normalized in PRODUCT_SETUP_SURFACES)) {
    return null;
  }
  return PRODUCT_SETUP_SURFACES[normalized as ProductSetupSurfaceKey];
}

export function productSetupSurfaceFromCurrentQuery(): ProductSetupSurface | null {
  if (typeof window === 'undefined') {
    return null;
  }
  return resolveProductSetupSurface(new URLSearchParams(window.location.search).get(PRODUCT_SETUP_SURFACE_PARAM));
}

export function buildProviderOpsSetupHref(surface: ProductSetupSurfaceKey): string {
  return `/admin/market-providers?${PRODUCT_SETUP_SURFACE_PARAM}=${encodeURIComponent(surface)}`;
}

export function buildDataSourcesSetupHref(surface: ProductSetupSurfaceKey): string {
  const query = new URLSearchParams({
    panel: 'data_sources',
    [PRODUCT_SETUP_SURFACE_PARAM]: surface,
  });
  return `/settings/system?${query.toString()}`;
}
