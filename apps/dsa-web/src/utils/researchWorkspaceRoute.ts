import type { UiLanguage } from '../i18n/core';
import { buildLocalizedPath } from './localeRouting';

export type ResearchWorkspaceSurface = 'scanner' | 'watchlist' | 'portfolio' | 'backtest' | 'options';
export type ResearchWorkspaceSource = ResearchWorkspaceSurface | 'manual';

export type ResearchWorkspaceRouteContext = {
  symbol?: string | null;
  market?: string | null;
  source?: ResearchWorkspaceSource | null;
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

export function parseResearchWorkspaceSearch(search: string): ResearchWorkspaceRouteContext {
  const params = new URLSearchParams(search);
  return {
    symbol: normalizeResearchWorkspaceSymbol(params.get('symbol')),
    market: normalizeResearchWorkspaceMarket(params.get('market')),
    source: normalizeResearchWorkspaceSource(params.get('source')),
  };
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

  if (symbol) params.set('symbol', symbol);
  if (market) params.set('market', market);
  if (source) params.set('source', source);

  const query = params.toString();
  const path = query ? `${SURFACE_PATHS[surface]}?${query}` : SURFACE_PATHS[surface];
  return buildLocalizedPath(path, language);
}
