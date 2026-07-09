import { describe, expect, it } from 'vitest';
import {
  getAuthBootstrapRouteKind,
  isProtectedProductPath,
  isPublicSafePath,
  shouldPreservePublicRouteOnAuthFailure,
} from '../appRouteGuards';

describe('appRouteGuards public market boundary', () => {
  it.each([
    '/market-overview',
    '/zh/market-overview',
    '/en/market-overview',
    '/market/decision-cockpit',
    '/zh/market/liquidity-monitor',
    '/',
    '/guest',
    '/stocks/structure-decision',
  ])('classifies %s as a public guest-safe research path', (path) => {
    expect(isPublicSafePath(path)).toBe(true);
    expect(getAuthBootstrapRouteKind(path)).toBe('public');
    expect(shouldPreservePublicRouteOnAuthFailure(path)).toBe(true);
  });

  it.each([
    '/watchlist',
    '/zh/watchlist',
    '/scanner',
    '/en/scanner',
    '/portfolio',
    '/zh/portfolio',
    '/backtest',
    '/scenario-lab',
    '/research/radar',
    '/options-lab',
    '/settings',
    '/stocks/AAPL/structure-decision',
  ])('classifies %s as protected product path', (path) => {
    expect(isProtectedProductPath(path)).toBe(true);
    expect(getAuthBootstrapRouteKind(path)).toBe('protected');
    expect(shouldPreservePublicRouteOnAuthFailure(path)).toBe(false);
  });

  it.each([
    '/admin/logs',
    '/zh/admin/users',
    '/settings/system',
    '/en/settings/system',
  ])('classifies %s as admin surface path', (path) => {
    expect(getAuthBootstrapRouteKind(path)).toBe('admin');
    expect(shouldPreservePublicRouteOnAuthFailure(path)).toBe(false);
  });

  it.each([
    '/login',
    '/zh/login',
    '/register',
    '/en/reset-password',
  ])('classifies %s as auth-entry path', (path) => {
    expect(getAuthBootstrapRouteKind(path)).toBe('auth-entry');
    expect(shouldPreservePublicRouteOnAuthFailure(path)).toBe(false);
  });
});
