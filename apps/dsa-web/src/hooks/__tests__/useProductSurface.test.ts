import { afterEach, describe, expect, it } from 'vitest';
import { buildLoginPath, buildRegistrationPath, resolveProductSurfaceRole } from '../useProductSurface';

describe('resolveProductSurfaceRole', () => {
  it('treats any logged-out session as guest even when auth is disabled', () => {
    expect(resolveProductSurfaceRole({
      authEnabled: false,
      loggedIn: false,
      currentUser: null,
    })).toBe('guest');
  });

  it('treats an unauthenticated bootstrap admin payload as guest', () => {
    expect(resolveProductSurfaceRole({
      authEnabled: false,
      loggedIn: false,
      currentUser: { isAdmin: true },
    })).toBe('guest');
  });

  it('keeps authenticated admin accounts on the admin surface', () => {
    expect(resolveProductSurfaceRole({
      authEnabled: true,
      loggedIn: true,
      currentUser: { isAdmin: true },
    })).toBe('admin');
  });

  it('recognizes authenticated current-user payloads even when the top-level loggedIn flag is stale', () => {
    expect(resolveProductSurfaceRole({
      authEnabled: true,
      loggedIn: false,
      currentUser: { isAdmin: true, isAuthenticated: true },
    })).toBe('admin');

    expect(resolveProductSurfaceRole({
      authEnabled: true,
      loggedIn: false,
      currentUser: { isAdmin: false, isAuthenticated: true },
    })).toBe('user');
  });
});

describe('useProductSurface locale-aware auth paths', () => {
  afterEach(() => {
    window.history.replaceState(window.history.state, '', '/');
    window.localStorage.clear();
  });

  it('builds locale-prefixed login paths from the active route surface', () => {
    window.history.replaceState(window.history.state, '', '/en/market-overview');

    expect(buildLoginPath('/market-overview')).toBe('/en/login?redirect=%2Fen%2Fmarket-overview');
  });

  it('builds locale-prefixed registration paths from the stored locale when the route is unprefixed', () => {
    window.localStorage.setItem('dsa-ui-language', 'zh');
    window.history.replaceState(window.history.state, '', '/settings');

    expect(buildRegistrationPath('/settings')).toBe('/zh/login?mode=create&redirect=%2Fzh%2Fsettings');
  });
});
