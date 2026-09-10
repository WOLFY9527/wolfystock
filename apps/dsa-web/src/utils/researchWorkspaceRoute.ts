import type { UiLanguage } from '../i18n/core';
import { buildLocalizedPath } from './localeRouting';
import {
  getCoreProductRouteByKey,
  type CoreProductRoute,
  type CoreProductRouteKey,
} from '../components/layout/coreProductRoutes';

export type ResearchWorkspaceSurface = 'scanner' | 'stock-structure' | 'watchlist' | 'portfolio' | 'backtest' | 'options';
export type ResearchWorkspaceSource = ResearchWorkspaceSurface | 'manual';

export type ResearchWorkspaceRouteContext = {
  symbol?: string | null;
  market?: string | null;
  source?: ResearchWorkspaceSource | null;
  scannerRunId?: number | null;
};

const SOURCE_VALUES = new Set<ResearchWorkspaceSource>([
  'scanner',
  'stock-structure',
  'watchlist',
  'portfolio',
  'backtest',
  'options',
  'manual',
]);

const SURFACE_ROUTE_KEYS: Record<ResearchWorkspaceSurface, CoreProductRouteKey> = {
  scanner: 'scanner',
  'stock-structure': 'stock-structure',
  watchlist: 'watchlist',
  portfolio: 'portfolio',
  backtest: 'backtest',
  options: 'options-lab',
};

export function getResearchWorkspaceRoute(surface: ResearchWorkspaceSurface): CoreProductRoute {
  return getCoreProductRouteByKey(SURFACE_ROUTE_KEYS[surface]);
}

function routeTransportValue(value: unknown, maxLength: number): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed && trimmed.length <= maxLength ? trimmed : null;
}

export function normalizeResearchWorkspaceSymbol(value: unknown): string | null {
  return routeTransportValue(value, 32);
}

export function normalizeResearchWorkspaceMarket(value: unknown): string | null {
  return routeTransportValue(value, 16);
}

export function normalizeResearchWorkspaceSource(value: unknown): ResearchWorkspaceSource | null {
  const source = String(value || '').trim().toLowerCase();
  return SOURCE_VALUES.has(source as ResearchWorkspaceSource) ? source as ResearchWorkspaceSource : null;
}

export function normalizeResearchWorkspaceScannerRunId(value: unknown): number | null {
  if (typeof value === 'number') {
    return Number.isSafeInteger(value) && value > 0 ? value : null;
  }
  if (typeof value !== 'string' || !/^\d+$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}

export function parseResearchWorkspaceSearch(search: string): ResearchWorkspaceRouteContext {
  const params = new URLSearchParams(search);
  return {
    symbol: normalizeResearchWorkspaceSymbol(params.get('symbol')),
    market: normalizeResearchWorkspaceMarket(params.get('market')),
    source: normalizeResearchWorkspaceSource(params.get('source')),
    scannerRunId: normalizeResearchWorkspaceScannerRunId(params.get('scannerRunId')),
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
  const scannerRunId = normalizeResearchWorkspaceScannerRunId(context.scannerRunId);

  if (symbol) params.set('symbol', symbol);
  if (market) params.set('market', market);
  if (source) params.set('source', source);
  if (scannerRunId) params.set('scannerRunId', String(scannerRunId));

  const basePath = surface === 'stock-structure' && symbol
    ? `/stocks/${encodeURIComponent(symbol)}/structure-decision`
    : getResearchWorkspaceRoute(surface).path;
  const query = params.toString();
  const path = query ? `${basePath}?${query}` : basePath;
  return buildLocalizedPath(path, language);
}
