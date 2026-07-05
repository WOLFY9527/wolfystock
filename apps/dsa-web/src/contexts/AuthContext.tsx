import type React from 'react';
import { createContext, use, useCallback, useEffect, useState } from 'react';
import { createParsedApiError, getParsedApiError, type ParsedApiError } from '../api/error';
import { invalidateApiShortWindowCache } from '../api';
import type { CurrentUser } from '../api/auth';
import { authApi } from '../api/auth';
import { resetAdminSurfaceMode } from '../hooks/productSurfaceMode';
import { useStockPoolStore } from '../stores/stockPoolStore';
import { hardRedirect } from '../utils/browserRedirect';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';

const AUTH_STATUS_PATH = '/api/v1/auth/status';

const LOCAL_STORAGE_KEYS_TO_CLEAR = [
  'dsa_chat_session_id',
  'dsa-selected-history-id',
  'dsa-task-queue-v1',
  'wolfystock.ruleBacktestPresets.v1',
] as const;

const SESSION_STORAGE_KEYS_TO_CLEAR = [
  'dsa-admin-surface-mode',
] as const;

const COOKIE_KEYS_TO_CLEAR = [
  'dsa_session',
  'wolfystock_guest_session',
] as const;

type AuthContextValue = {
  authEnabled: boolean;
  loggedIn: boolean;
  passwordSet: boolean;
  passwordChangeable: boolean;
  setupState: 'enabled' | 'password_retained' | 'no_password';
  currentUser: CurrentUser | null;
  isLoading: boolean;
  loadError: ParsedApiError | null;
  login: (params: {
    username?: string;
    displayName?: string;
    password: string;
    passwordConfirm?: string;
    createUser?: boolean;
  }) => Promise<{ success: boolean; error?: ParsedApiError }>;
  changePassword: (
    currentPassword: string,
    newPassword: string,
    newPasswordConfirm: string
  ) => Promise<{ success: boolean; error?: ParsedApiError }>;
  logout: () => Promise<void>;
  refreshStatus: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function clearAuthRelatedBrowserStorage(): Promise<void> {
  if (typeof window === 'undefined') {
    return;
  }

  LOCAL_STORAGE_KEYS_TO_CLEAR.forEach((key) => {
    window.localStorage.removeItem(key);
  });
  SESSION_STORAGE_KEYS_TO_CLEAR.forEach((key) => {
    window.sessionStorage.removeItem(key);
  });

  if (typeof document !== 'undefined') {
    COOKIE_KEYS_TO_CLEAR.forEach((key) => {
      document.cookie = `${key}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
    });
  }

  await Promise.resolve();
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function extractLoginError(err: unknown): ParsedApiError {
  const parsed = getParsedApiError(err);
  if (parsed.status === 429) {
    return createParsedApiError({
      title: '登录尝试过于频繁',
      message: '尝试次数过多，请稍后再试。',
      rawMessage: parsed.rawMessage,
      status: parsed.status,
      category: parsed.category,
    });
  }
  return parsed;
}

function buildUnconfirmedLoginError(): ParsedApiError {
  return createParsedApiError({
    title: '登录状态未确认',
    message: '登录响应已返回，但会话状态未恢复，请重试。',
    rawMessage: 'auth_status_not_authenticated_after_login',
    category: 'auth_required',
  });
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [authEnabled, setAuthEnabled] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [passwordSet, setPasswordSet] = useState(false);
  const [passwordChangeable, setPasswordChangeable] = useState(false);
  const [setupState, setSetupState] = useState<'enabled' | 'password_retained' | 'no_password'>('no_password');
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<ParsedApiError | null>(null);
  const clearSessionState = () => {
    setLoggedIn(false);
    setPasswordSet(false);
    setPasswordChangeable(false);
    setSetupState('no_password');
    setCurrentUser(null);
    setLoadError(null);
    useStockPoolStore.getState().resetDashboardState();
    resetAdminSurfaceMode();
  };

  const loadAuthStatus = useCallback(async ({ primeLoading }: { primeLoading: boolean }) => {
    if (primeLoading) {
      setIsLoading(true);
      setLoadError(null);
    }
    try {
      const status = await authApi.getStatus();
      const nextCurrentUser = status.currentUser ?? null;
      const nextLoggedIn = Boolean(nextCurrentUser?.isAuthenticated ?? status.loggedIn);
      setAuthEnabled(status.authEnabled);
      setLoggedIn(nextLoggedIn);
      setPasswordSet(status.passwordSet ?? false);
      setPasswordChangeable(status.passwordChangeable ?? false);
      setSetupState(status.setupState);
      setCurrentUser(nextCurrentUser);
      if (status.authEnabled && !nextLoggedIn) {
        useStockPoolStore.getState().resetDashboardState();
      }
      return status;
    } catch (err) {
      setLoadError(getParsedApiError(err));
      setAuthEnabled(false);
      setLoggedIn(false);
      setPasswordSet(false);
      setPasswordChangeable(false);
      setSetupState('no_password');
      setCurrentUser(null);
      useStockPoolStore.getState().resetDashboardState();
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchStatus = useCallback(async () => {
    await loadAuthStatus({ primeLoading: true });
  }, [loadAuthStatus]);

  useEffect(() => {
    void loadAuthStatus({ primeLoading: false });
  }, [loadAuthStatus]);

  const login = async (
    params: {
      username?: string;
      displayName?: string;
      password: string;
      passwordConfirm?: string;
      createUser?: boolean;
    }
  ): Promise<{ success: boolean; error?: ParsedApiError }> => {
    try {
      invalidateApiShortWindowCache(AUTH_STATUS_PATH);
      if (!authEnabled) {
        if (setupState === 'no_password') {
          await authApi.updateSettings(true, params.password, params.passwordConfirm);
        } else if (setupState === 'password_retained') {
          await authApi.updateSettings(true, undefined, undefined, params.password);
        } else {
          await authApi.login(params);
        }
      } else {
        await authApi.login(params);
      }
      invalidateApiShortWindowCache(AUTH_STATUS_PATH);
      const confirmedStatus = await loadAuthStatus({ primeLoading: true });
      if (!confirmedStatus) {
        return { success: false, error: buildUnconfirmedLoginError() };
      }
      const confirmedUser = confirmedStatus.currentUser ?? null;
      const confirmedLoggedIn = Boolean(confirmedUser?.isAuthenticated ?? confirmedStatus.loggedIn);
      if (!confirmedLoggedIn) {
        return {
          success: false,
          error: buildUnconfirmedLoginError(),
        };
      }
      return { success: true };
    } catch (err: unknown) {
      return { success: false, error: extractLoginError(err) };
    }
  };

  const changePassword = async (
    currentPassword: string,
    newPassword: string,
    newPasswordConfirm: string
  ): Promise<{ success: boolean; error?: ParsedApiError }> => {
    try {
      await authApi.changePassword(currentPassword, newPassword, newPasswordConfirm);
      return { success: true };
    } catch (err: unknown) {
      return { success: false, error: getParsedApiError(err) };
    }
  };

  const logout = async () => {
    let logoutError: unknown = null;

    invalidateApiShortWindowCache(AUTH_STATUS_PATH);
    try {
      await authApi.logout();
    } catch (err) {
      logoutError = err;
    }

    await clearAuthRelatedBrowserStorage();
    invalidateApiShortWindowCache(AUTH_STATUS_PATH);
    clearSessionState();
    await wait(100);
    const routeLocale = parseLocaleFromPathname(window.location.pathname);
    hardRedirect(routeLocale ? buildLocalizedPath('/guest', routeLocale) : '/guest');

    if (logoutError && getParsedApiError(logoutError).status !== 401) {
      throw logoutError;
    }
  };

  return (
    <AuthContext.Provider
      value={{
        authEnabled,
        loggedIn,
        passwordSet,
        passwordChangeable,
        setupState,
        currentUser,
        isLoading,
        loadError,
        login,
        changePassword,
        logout,
        refreshStatus: fetchStatus,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components -- useAuth is a hook, co-located for context access
export function useAuth(): AuthContextValue {
  const ctx = use(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}
