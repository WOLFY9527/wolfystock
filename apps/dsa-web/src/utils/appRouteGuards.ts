import { stripLocalePrefix } from './localeRouting';

export type AuthBootstrapRouteKind = 'public' | 'protected' | 'admin' | 'auth-entry' | 'other';

function isPathMatch(pathname: string, target: string): boolean {
  return pathname === target || pathname.startsWith(`${target}/`);
}

export function isPreviewRoutePath(pathname: string): boolean {
  return stripLocalePrefix(pathname).startsWith('/__preview/');
}

export function isAuthEntryPath(pathname: string): boolean {
  const routePathname = stripLocalePrefix(pathname);
  return routePathname === '/login'
    || routePathname === '/register'
    || routePathname === '/reset-password';
}

export function isAdminSurfacePath(pathname: string): boolean {
  const routePathname = stripLocalePrefix(pathname);
  return isPathMatch(routePathname, '/settings/system') || isPathMatch(routePathname, '/admin');
}

export function isStockStructureDecisionEntryPath(pathname: string): boolean {
  return stripLocalePrefix(pathname) === '/stocks/structure-decision';
}

export function isStockStructureDecisionDetailPath(pathname: string): boolean {
  return /^\/stocks\/[^/]+\/structure-decision(?:\/)?$/i.test(stripLocalePrefix(pathname));
}

export function isStockStructureDecisionLegacyPath(pathname: string): boolean {
  return /^\/stock\/[^/]+(?:\/structure-decision)?(?:\/)?$/i.test(stripLocalePrefix(pathname));
}

/**
 * Product routes that require an authenticated session (or show an in-shell paywall).
 * Paths may be locale-prefixed; classification always uses the stripped route.
 */
export function isProtectedProductPath(pathname: string): boolean {
  const routePathname = stripLocalePrefix(pathname);
  return routePathname === '/settings'
    || routePathname === '/options'
    || routePathname === '/scanner'
    || routePathname === '/holdings'
    || routePathname === '/radar'
    || routePathname === '/research'
    || routePathname === '/research-radar'
    || isPathMatch(routePathname, '/portfolio')
    || isPathMatch(routePathname, '/radar')
    || isPathMatch(routePathname, '/research/radar')
    || isPathMatch(routePathname, '/scenario-lab')
    || isPathMatch(routePathname, '/watchlist')
    || isPathMatch(routePathname, '/backtest')
    || isPathMatch(routePathname, '/options-lab')
    || isStockStructureDecisionDetailPath(routePathname);
}

/**
 * Guest-readable research routes that must remain reachable without auth bootstrap.
 * Includes public Market Overview and other public market research surfaces.
 */
export function isPublicSafePath(pathname: string): boolean {
  const routePathname = stripLocalePrefix(pathname);
  return routePathname === '/'
    || routePathname === '/guest'
    || routePathname === '/market'
    || routePathname === '/cockpit'
    || routePathname === '/decision-cockpit'
    || routePathname === '/market-overview'
    || routePathname === '/liquidity'
    || routePathname === '/rotation'
    || routePathname === '/chat'
    || routePathname === '/market/decision-cockpit'
    || routePathname === '/market/liquidity-monitor'
    || routePathname === '/market/rotation-radar'
    || isStockStructureDecisionEntryPath(routePathname)
    || isStockStructureDecisionLegacyPath(routePathname);
}

export function getAuthBootstrapRouteKind(pathname: string): AuthBootstrapRouteKind {
  const routePathname = stripLocalePrefix(pathname);
  if (isAuthEntryPath(routePathname)) {
    return 'auth-entry';
  }
  if (isAdminSurfacePath(routePathname)) {
    return 'admin';
  }
  if (isProtectedProductPath(routePathname)) {
    return 'protected';
  }
  if (isPublicSafePath(routePathname)) {
    return 'public';
  }
  return 'other';
}

/**
 * Public guest research surfaces must stay on-route when a secondary API returns 401.
 * Hard redirect to login/bootstrap is reserved for protected and admin ownership paths.
 */
export function shouldPreservePublicRouteOnAuthFailure(pathname: string): boolean {
  return getAuthBootstrapRouteKind(pathname) === 'public';
}
