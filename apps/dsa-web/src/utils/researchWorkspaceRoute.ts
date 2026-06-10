import type { UiLanguage } from '../i18n/core';
import { buildLocalizedPath } from './localeRouting';

export type ResearchWorkspaceSurface = 'scanner' | 'watchlist' | 'portfolio' | 'backtest' | 'options';
export type ResearchWorkspaceSource = ResearchWorkspaceSurface | 'manual';

export type ResearchWorkspaceRouteContext = {
  symbol?: string | null;
  market?: string | null;
  source?: ResearchWorkspaceSource | null;
  origin?: ResearchWorkspaceSource | null;
  scannerRunId?: string | number | null;
  scannerRank?: string | number | null;
  scannerProfile?: string | null;
  themeId?: string | null;
  universeType?: string | null;
  watchlistItemId?: string | number | null;
};

const SOURCE_VALUES = new Set<ResearchWorkspaceSource>([
  'scanner',
  'watchlist',
  'portfolio',
  'backtest',
  'options',
  'manual',
]);

const SURFACE_PATHS: Record<ResearchWorkspaceSurface, string> = {
  scanner: '/scanner',
  watchlist: '/watchlist',
  portfolio: '/portfolio',
  backtest: '/backtest',
  options: '/options-lab',
};

export function normalizeResearchWorkspaceSymbol(value: unknown): string | null {
  const symbol = String(value || '').trim().toUpperCase();
  if (!symbol || symbol.length > 32) return null;
  return /^[A-Z0-9._-]+$/.test(symbol) ? symbol : null;
}

export function normalizeResearchWorkspaceMarket(value: unknown): string | null {
  const market = String(value || '').trim().toUpperCase();
  if (!market || market.length > 16) return null;
  return /^[A-Z0-9_-]+$/.test(market) ? market : null;
}

export function normalizeResearchWorkspaceSource(value: unknown): ResearchWorkspaceSource | null {
  const source = String(value || '').trim().toLowerCase();
  return SOURCE_VALUES.has(source as ResearchWorkspaceSource) ? source as ResearchWorkspaceSource : null;
}

function normalizeQueryText(value: unknown, maxLength = 64): string | null {
  const text = String(value || '').trim();
  if (!text || text.length > maxLength) return null;
  return text;
}

export function parseResearchWorkspaceSearch(search: string): ResearchWorkspaceRouteContext {
  const params = new URLSearchParams(search);
  return {
    symbol: normalizeResearchWorkspaceSymbol(params.get('symbol')),
    market: normalizeResearchWorkspaceMarket(params.get('market')),
    source: normalizeResearchWorkspaceSource(params.get('source')),
    origin: normalizeResearchWorkspaceSource(params.get('origin')),
    scannerRunId: normalizeQueryText(params.get('scannerRunId')),
    scannerRank: normalizeQueryText(params.get('scannerRank'), 12),
    scannerProfile: normalizeQueryText(params.get('scannerProfile')),
    themeId: normalizeQueryText(params.get('themeId')),
    universeType: normalizeQueryText(params.get('universeType')),
    watchlistItemId: normalizeQueryText(params.get('watchlistItemId'), 24),
  };
}

function setIfPresent(params: URLSearchParams, key: string, value: unknown): void {
  const text = normalizeQueryText(value);
  if (text) params.set(key, text);
}

export function buildResearchWorkspacePath(
  surface: ResearchWorkspaceSurface,
  language: UiLanguage,
  context: ResearchWorkspaceRouteContext = {},
): string {
  const params = new URLSearchParams();
  const symbol = normalizeResearchWorkspaceSymbol(context.symbol);
  const market = normalizeResearchWorkspaceMarket(context.market);
  const source = normalizeResearchWorkspaceSource(context.source);
  const origin = normalizeResearchWorkspaceSource(context.origin);

  if (symbol) params.set('symbol', symbol);
  if (market) params.set('market', market);
  if (source) params.set('source', source);
  if (origin) params.set('origin', origin);
  setIfPresent(params, 'scannerRunId', context.scannerRunId);
  setIfPresent(params, 'scannerRank', context.scannerRank);
  setIfPresent(params, 'scannerProfile', context.scannerProfile);
  setIfPresent(params, 'themeId', context.themeId);
  setIfPresent(params, 'universeType', context.universeType);
  setIfPresent(params, 'watchlistItemId', context.watchlistItemId);

  const query = params.toString();
  const path = query ? `${SURFACE_PATHS[surface]}?${query}` : SURFACE_PATHS[surface];
  return buildLocalizedPath(path, language);
}
