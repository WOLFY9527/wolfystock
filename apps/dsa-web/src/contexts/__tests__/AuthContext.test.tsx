import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApiError, createParsedApiError } from '../../api/error';
import { AuthProvider, useAuth } from '../AuthContext';

const {
  getStatus,
  login,
  updateSettings,
  changePassword,
  logout,
  invalidateApiShortWindowCache,
  resetDashboardState,
  resetAdminSurfaceMode,
} = vi.hoisted(() => ({
  getStatus: vi.fn(),
  login: vi.fn(),
  updateSettings: vi.fn(),
  changePassword: vi.fn(),
  logout: vi.fn(),
  invalidateApiShortWindowCache: vi.fn(),
  resetDashboardState: vi.fn(),
  resetAdminSurfaceMode: vi.fn(),
}));

const { hardRedirectMock } = vi.hoisted(() => ({
  hardRedirectMock: vi.fn(),
}));

const PROBE_PASSWORD = 'unit-test-passwd6';

vi.mock('../../api/auth', () => ({
  authApi: {
    getStatus,
    login,
    updateSettings,
    changePassword,
    logout,
  },
}));

vi.mock('../../api', () => ({
  invalidateApiShortWindowCache,
}));

vi.mock('../../stores/stockPoolStore', () => ({
  useStockPoolStore: {
    getState: () => ({
      resetDashboardState,
    }),
  },
}));

vi.mock('../../hooks/productSurfaceMode', () => ({
  ADMIN_SURFACE_MODE_STORAGE_KEY: 'dsa-admin-surface-mode',
  resetAdminSurfaceMode,
}));

vi.mock('../../utils/browserRedirect', () => ({
  hardRedirect: (path: string) => hardRedirectMock(path),
}));

const Probe = () => {
  const auth = useAuth();

  return (
    <div>
      <span data-testid="status">{auth.loggedIn ? 'logged-in' : 'logged-out'}</span>
      <span data-testid="password-set">{auth.passwordSet ? 'set' : 'unset'}</span>
      <button
        type="button"
        onClick={() => void auth.login({ username: 'admin', password: PROBE_PASSWORD, passwordConfirm: PROBE_PASSWORD })}
      >
        trigger-login
      </button>
      <button type="button" onClick={() => void auth.logout()}>
        trigger-logout
      </button>
    </div>
  );
};

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it('refreshes auth state after a successful login', async () => {
    getStatus
      .mockResolvedValueOnce({
        authEnabled: true,
        loggedIn: false,
        passwordSet: false,
        passwordChangeable: true,
      })
      .mockResolvedValueOnce({
        authEnabled: true,
        loggedIn: true,
        passwordSet: true,
        passwordChangeable: true,
      });
    login.mockResolvedValue(undefined);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await screen.findByTestId('status');
    fireEvent.click(screen.getByRole('button', { name: 'trigger-login' }));

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('logged-in'));
    expect(screen.getByTestId('password-set')).toHaveTextContent('set');
    expect(invalidateApiShortWindowCache).toHaveBeenCalledWith('/api/v1/auth/status');
  });

  it('recognizes an authenticated current user when the top-level loggedIn flag is stale', async () => {
    getStatus.mockResolvedValueOnce({
      authEnabled: true,
      loggedIn: false,
      passwordSet: true,
      passwordChangeable: true,
      setupState: 'enabled',
      currentUser: {
        username: 'admin',
        displayName: 'Admin',
        isAdmin: true,
        isAuthenticated: true,
      },
    });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('logged-in'));
    expect(resetDashboardState).not.toHaveBeenCalled();
  });

  it('keeps an unauthenticated bootstrap admin payload fail-closed', async () => {
    getStatus.mockResolvedValueOnce({
      authEnabled: true,
      loggedIn: true,
      passwordSet: true,
      passwordChangeable: true,
      setupState: 'enabled',
      currentUser: {
        username: 'admin',
        displayName: 'Admin',
        isAdmin: true,
        isAuthenticated: false,
      },
    });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await screen.findByTestId('status');
    expect(screen.getByTestId('status')).toHaveTextContent('logged-out');
    expect(resetDashboardState).toHaveBeenCalled();
  });

  it('enables auth through settings when bootstrap setup starts with auth disabled', async () => {
    getStatus
      .mockResolvedValueOnce({
        authEnabled: false,
        loggedIn: false,
        passwordSet: false,
        passwordChangeable: false,
        setupState: 'no_password',
      })
      .mockResolvedValueOnce({
        authEnabled: true,
        loggedIn: true,
        passwordSet: true,
        passwordChangeable: true,
        setupState: 'enabled',
      });
    updateSettings.mockResolvedValue(undefined);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await screen.findByTestId('status');
    fireEvent.click(screen.getByRole('button', { name: 'trigger-login' }));

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('logged-in'));
    expect(updateSettings).toHaveBeenCalledWith(true, PROBE_PASSWORD, PROBE_PASSWORD);
    expect(login).not.toHaveBeenCalled();
  });

  it('uses login endpoint when auth is enabled but first-run password is missing', async () => {
    getStatus
      .mockResolvedValueOnce({
        authEnabled: true,
        loggedIn: false,
        passwordSet: false,
        passwordChangeable: true,
        setupState: 'no_password',
      })
      .mockResolvedValueOnce({
        authEnabled: true,
        loggedIn: true,
        passwordSet: true,
        passwordChangeable: true,
        setupState: 'enabled',
      });
    login.mockResolvedValue(undefined);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await screen.findByTestId('status');
    fireEvent.click(screen.getByRole('button', { name: 'trigger-login' }));

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('logged-in'));
    expect(login).toHaveBeenCalledWith({
      username: 'admin',
      password: PROBE_PASSWORD,
      passwordConfirm: PROBE_PASSWORD,
    });
    expect(updateSettings).not.toHaveBeenCalled();
  });

  it('wipes browser and in-memory state after logout', async () => {
    window.localStorage.setItem('dsa_chat_session_id', 'chat-session-1');
    window.localStorage.setItem('dsa-selected-history-id', '42');
    window.localStorage.setItem('dsa-task-queue-v1', '[{"taskId":"task-1"}]');
    window.localStorage.setItem('wolfystock.ruleBacktestPresets.v1', '[{"id":"preset-1"}]');
    window.localStorage.setItem('dsa-ui-language', 'en');
    window.localStorage.setItem('dsa-theme-style', 'spacex');
    window.sessionStorage.setItem('dsa-admin-surface-mode', 'admin');

    getStatus.mockResolvedValueOnce({
      authEnabled: true,
      loggedIn: true,
      passwordSet: true,
      passwordChangeable: true,
    });
    logout.mockResolvedValue(undefined);

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await screen.findByTestId('status');
    fireEvent.click(screen.getByRole('button', { name: 'trigger-logout' }));

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('logged-out'));
    expect(resetDashboardState).toHaveBeenCalled();
    expect(resetAdminSurfaceMode).toHaveBeenCalled();
    expect(logout).toHaveBeenCalledTimes(1);
    expect(getStatus).toHaveBeenCalledTimes(1);
    expect(window.localStorage.getItem('dsa_chat_session_id')).toBeNull();
    expect(window.localStorage.getItem('dsa-selected-history-id')).toBeNull();
    expect(window.localStorage.getItem('dsa-task-queue-v1')).toBeNull();
    expect(window.localStorage.getItem('wolfystock.ruleBacktestPresets.v1')).toBeNull();
    expect(window.localStorage.getItem('dsa-ui-language')).toBe('en');
    expect(window.localStorage.getItem('dsa-theme-style')).toBe('spacex');
    expect(window.sessionStorage.getItem('dsa-admin-surface-mode')).toBeNull();
    expect(hardRedirectMock).not.toHaveBeenCalled();
    await new Promise((resolve) => window.setTimeout(resolve, 120));
    expect(hardRedirectMock).toHaveBeenCalledWith('/guest');
    expect(invalidateApiShortWindowCache).toHaveBeenCalledWith('/api/v1/auth/status');
  });

  it('does not reset dashboard state when auth is disabled', async () => {
    getStatus.mockResolvedValueOnce({
      authEnabled: false,
      loggedIn: false,
      passwordSet: false,
      passwordChangeable: false,
      setupState: 'no_password',
    });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await screen.findByTestId('status');
    expect(resetDashboardState).not.toHaveBeenCalled();
  });

  it('treats a 401 logout as already signed out after status refresh', async () => {
    getStatus.mockResolvedValueOnce({
      authEnabled: true,
      loggedIn: true,
      passwordSet: true,
      passwordChangeable: true,
      setupState: 'enabled',
    });
    logout.mockRejectedValue(
      createApiError(
        createParsedApiError({
          title: '未登录',
          message: 'Login required',
          rawMessage: 'Login required',
          status: 401,
          category: 'http_error',
        }),
        { response: { status: 401, data: { error: 'unauthorized' } } }
      )
    );

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await screen.findByTestId('status');
    fireEvent.click(screen.getByRole('button', { name: 'trigger-logout' }));

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('logged-out'));
    expect(resetDashboardState).toHaveBeenCalled();
    expect(resetAdminSurfaceMode).toHaveBeenCalled();
    expect(getStatus).toHaveBeenCalledTimes(1);
    await new Promise((resolve) => window.setTimeout(resolve, 120));
    expect(hardRedirectMock).toHaveBeenCalledWith('/guest');
    expect(invalidateApiShortWindowCache).toHaveBeenCalledWith('/api/v1/auth/status');
  });
});
