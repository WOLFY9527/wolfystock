import { useEffect, useSyncExternalStore } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { getStoredUiLanguage } from '../i18n/core';
import { buildLocalizedPath, parseLocaleFromPathname, shouldLocalizePath } from '../utils/localeRouting';
import { resolveAdminCapabilityFlags } from '../utils/adminCapabilities';
import {
  ADMIN_SURFACE_MODE_STORAGE_KEY,
  getAdminSurfaceModeServerSnapshot,
  getAdminSurfaceModeSnapshot,
  setAdminSurfaceMode,
  subscribeAdminSurfaceMode,
  syncAdminSurfaceModeFromStorage,
  type AdminSurfaceMode,
} from './productSurfaceMode';

export type ProductSurfaceRole = 'guest' | 'user' | 'admin';
export { setAdminSurfaceMode };
export type { AdminSurfaceMode };

export function resolveProductSurfaceRole(params: {
  authEnabled: boolean;
  loggedIn: boolean;
  currentUser: { isAdmin?: boolean } | null;
}): ProductSurfaceRole {
  if (!params.loggedIn) {
    return 'guest';
  }
  if (params.currentUser?.isAdmin) {
    return 'admin';
  }
  return 'user';
}

export function normalizeRedirectPath(
  redirectTo: string | null | undefined,
  fallback = '/',
): string {
  const normalized = typeof redirectTo === 'string' && redirectTo.startsWith('/') && !redirectTo.startsWith('//')
    ? redirectTo
    : fallback;
  return normalized.startsWith('/') && !normalized.startsWith('//') ? normalized : fallback;
}

export function resolveAuthRedirect(search: string, fallback = '/'): string {
  return normalizeRedirectPath(new URLSearchParams(search).get('redirect'), fallback);
}

function resolveActiveLocale() {
  if (typeof window === 'undefined') {
    return getStoredUiLanguage();
  }
  const routeLocale = parseLocaleFromPathname(window.location.pathname);
  return routeLocale || getStoredUiLanguage();
}

export function buildLoginPath(redirectTo: string): string {
  const normalizedRedirect = normalizeRedirectPath(redirectTo);
  const activeLocale = resolveActiveLocale();
  const localizedRedirect = buildLocalizedPath(normalizedRedirect, activeLocale);
  const path = `/login?redirect=${encodeURIComponent(localizedRedirect)}`;
  if (typeof window !== 'undefined' && shouldLocalizePath(window.location.pathname)) {
    return buildLocalizedPath(path, activeLocale);
  }
  return path;
}

export function buildRegistrationPath(redirectTo: string): string {
  const normalizedRedirect = normalizeRedirectPath(redirectTo);
  const activeLocale = resolveActiveLocale();
  const localizedRedirect = buildLocalizedPath(normalizedRedirect, activeLocale);
  const path = `/login?mode=create&redirect=${encodeURIComponent(localizedRedirect)}`;
  if (typeof window !== 'undefined' && shouldLocalizePath(window.location.pathname)) {
    return buildLocalizedPath(path, activeLocale);
  }
  return path;
}

export function useProductSurface() {
  const { authEnabled, loggedIn, currentUser } = useAuth();
  const storedAdminSurfaceMode = useSyncExternalStore(
    subscribeAdminSurfaceMode,
    getAdminSurfaceModeSnapshot,
    getAdminSurfaceModeServerSnapshot,
  );
  const role = resolveProductSurfaceRole({ authEnabled, loggedIn, currentUser });
  const isAdminAccount = role === 'admin';
  const adminCapabilities = resolveAdminCapabilityFlags(currentUser);

  useEffect(() => {
    if (!isAdminAccount && storedAdminSurfaceMode !== 'user') {
      setAdminSurfaceMode('user');
    }
  }, [isAdminAccount, storedAdminSurfaceMode]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const handleStorage = (event: StorageEvent) => {
      if (event.key !== ADMIN_SURFACE_MODE_STORAGE_KEY) {
        return;
      }
      syncAdminSurfaceModeFromStorage(event.newValue);
    };
    window.addEventListener('storage', handleStorage);
    return () => {
      window.removeEventListener('storage', handleStorage);
    };
  }, []);

  const surfaceMode: AdminSurfaceMode = isAdminAccount ? storedAdminSurfaceMode : 'user';
  const isAdminMode = isAdminAccount && surfaceMode === 'admin';
  const isUserMode = !isAdminMode;

  return {
    role,
    authEnabled,
    loggedIn,
    currentUser,
    isGuest: role === 'guest',
    isUser: role === 'user',
    isAdmin: role === 'admin',
    isAdminAccount,
    adminCapabilities,
    ...adminCapabilities,
    surfaceMode,
    isAdminMode,
    isUserMode,
    isAuthenticated: role !== 'guest',
    setAdminSurfaceMode,
    toggleAdminSurfaceMode: () => setAdminSurfaceMode(isAdminMode ? 'user' : 'admin'),
  };
}
