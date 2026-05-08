import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppContent } from '../App';
import { isPreviewRoutePath } from '../utils/appRouteGuards';
import type { AdminCapabilityFlags } from '../utils/adminCapabilities';

const { useAuthMock, useProductSurfaceMock, setCurrentRouteMock, setLanguageMock, languageState } = vi.hoisted(() => ({
  useAuthMock: vi.fn(),
  useProductSurfaceMock: vi.fn(),
  setCurrentRouteMock: vi.fn(),
  setLanguageMock: vi.fn(),
  languageState: { value: 'zh' as 'zh' | 'en' },
}));

const noCapabilities: AdminCapabilityFlags = {
  canReadUsers: false,
  canReadUserActivity: false,
  canReadUserPortfolio: false,
  canWriteUserSecurity: false,
  canReadCostObservability: false,
  canReadOpsLogs: false,
  canReadProviders: false,
  canReadNotifications: false,
  canReadSystemConfig: false,
};

const fullCapabilities: AdminCapabilityFlags = {
  canReadUsers: true,
  canReadUserActivity: true,
  canReadUserPortfolio: true,
  canWriteUserSecurity: true,
  canReadCostObservability: true,
  canReadOpsLogs: true,
  canReadProviders: true,
  canReadNotifications: true,
  canReadSystemConfig: true,
};

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('../hooks/useProductSurface', () => ({
  buildLoginPath: (path: string) => `/login?redirect=${encodeURIComponent(path)}`,
  buildRegistrationPath: (path: string) => `/login?mode=create&redirect=${encodeURIComponent(path)}`,
  resolveAuthRedirect: (search: string, fallback = '/') => new URLSearchParams(search).get('redirect') || fallback,
  useProductSurface: () => useProductSurfaceMock(),
}));

vi.mock('../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: languageState.value,
    setLanguage: (language: 'zh' | 'en') => {
      languageState.value = language;
      setLanguageMock(language);
    },
    t: (key: string) => key,
  }),
}));

vi.mock('../stores/agentChatStore', () => ({
  useAgentChatStore: Object.assign(
    (selector?: (state: Record<string, unknown>) => unknown) => (selector ? selector({}) : {}),
    { getState: () => ({ setCurrentRoute: setCurrentRouteMock }) },
  ),
}));

vi.mock('../components/common', async () => {
  const React = await vi.importActual<typeof import('react')>('react');
  const actual = await vi.importActual<typeof import('../components/common')>('../components/common');
  const router = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    Shell: () => React.createElement('div', { 'data-testid': 'shell-frame' }, React.createElement(router.Outlet)),
    BrandedLoadingScreen: () => null,
    ApiErrorAlert: () => React.createElement('div', {}, 'api-error'),
  };
});

vi.mock('../pages/HomeSurfacePage', () => ({
  default: () => (
    <div>
      {languageState.value === 'en' ? 'Home Workspace' : '首页工作区'}
    </div>
  ),
}));

vi.mock('../pages/GuestHomePage', () => ({
  default: () => (
    <div>
      {languageState.value === 'en' ? 'Guest Preview Mode' : '游客预览模式'}
    </div>
  ),
}));

vi.mock('../pages/ScannerSurfacePage', () => ({
  default: () => <div>scanner-surface-page</div>,
}));

vi.mock('../pages/ChatPage', () => ({
  default: () => <div>chat-page</div>,
}));

vi.mock('../pages/PortfolioPage', () => ({
  default: () => <div>portfolio-page</div>,
}));

vi.mock('../pages/MarketRotationRadarPage', () => ({
  default: () => <div>market-rotation-radar-page</div>,
}));

vi.mock('../pages/BacktestPage', () => ({
  default: () => <div>backtest-page</div>,
}));

vi.mock('../pages/OptionsLabPage', () => ({
  default: () => <div>options-lab-page</div>,
}));

vi.mock('../pages/DeterministicBacktestResultPage', () => ({
  default: () => <div>backtest-result-page</div>,
}));

vi.mock('../pages/RuleBacktestComparePage', () => ({
  default: () => <div>backtest-compare-page</div>,
}));

vi.mock('../pages/PersonalSettingsPage', () => ({
  default: () => <div>personal-settings-page</div>,
}));

vi.mock('../pages/SystemSettingsPage', () => ({
  default: () => <div>system-settings-page</div>,
}));

vi.mock('../pages/AdminLogsPage', () => ({
  default: () => <div>admin-logs-page</div>,
}));

vi.mock('../pages/AdminNotificationsPage', () => ({
  default: () => <div>admin-notifications-page</div>,
}));

vi.mock('../pages/MarketProviderOperationsPage', () => ({
  default: () => <div>market-provider-operations-page</div>,
}));

vi.mock('../pages/AdminProviderCircuitDiagnosticsPage', () => ({
  default: () => <div>admin-provider-circuit-diagnostics-page</div>,
}));

vi.mock('../pages/AdminUsersPage', () => ({
  default: () => <div>admin-users-page</div>,
}));

vi.mock('../pages/AdminCostObservabilityPage', () => ({
  default: () => <div>admin-cost-observability-page</div>,
}));

vi.mock('../pages/AdminEvidenceWorkflowPage', () => ({
  default: () => <div>admin-evidence-workflow-page</div>,
}));

vi.mock('../pages/LoginPage', () => ({
  default: () => <div>login-page</div>,
}));

vi.mock('../components/auth/AuthGuardOverlay', () => ({
  AuthGuardOverlay: ({ moduleName }: { moduleName: string }) => <div>{`auth-guard:${moduleName}`}</div>,
}));

vi.mock('../pages/NotFoundPage', () => ({
  default: () => <div>not-found-page</div>,
}));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppContent />
    </MemoryRouter>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location-path">{location.pathname}</div>;
}

function renderAtWithLocationProbe(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LocationProbe />
      <AppContent />
    </MemoryRouter>,
  );
}

describe('AppContent route flows', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: false,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: true,
      isAdmin: false,
      isAdminMode: false,
      adminCapabilities: noCapabilities,
    });
    languageState.value = 'en';
  });

  it('renders the Chinese home surface on the root route', async () => {
    languageState.value = 'zh';
    renderAt('/');
    expect(await screen.findByText('首页工作区')).toBeInTheDocument();
  });

  it('renders the English home surface on the /en route', async () => {
    languageState.value = 'en';
    renderAt('/en');
    expect(await screen.findByText('Home Workspace')).toBeInTheDocument();
  });

  it('renders the dedicated guest route for an anonymous session', async () => {
    languageState.value = 'en';
    renderAt('/guest');
    expect(await screen.findByText('Guest Preview Mode')).toBeInTheDocument();
  });

  it('redirects signed-in sessions away from the dedicated guest route back to home', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: false,
      isAdminMode: false,
      adminCapabilities: noCapabilities,
    });

    languageState.value = 'en';
    renderAtWithLocationProbe('/guest');

    expect(await screen.findByText('Home Workspace')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent('/'));
    expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
  });

  it('renders the locale-prefixed dedicated guest route', async () => {
    languageState.value = 'en';
    renderAt('/en/guest');
    expect(await screen.findByText('Guest Preview Mode')).toBeInTheDocument();
  });

  it.each(['/settings', '/settings/system'])(
    'redirects guest access from %s to the dedicated guest page',
    async (path) => {
      renderAtWithLocationProbe(path);

      expect(await screen.findByText('Guest Preview Mode')).toBeInTheDocument();
      await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent('/guest'));
      expect(screen.queryByText('chat-page')).not.toBeInTheDocument();
      expect(screen.queryByText('portfolio-page')).not.toBeInTheDocument();
      expect(screen.queryByText('backtest-page')).not.toBeInTheDocument();
      expect(screen.queryByText('scanner-surface-page')).not.toBeInTheDocument();
      expect(screen.queryByText('personal-settings-page')).not.toBeInTheDocument();
      expect(screen.queryByText('system-settings-page')).not.toBeInTheDocument();
    },
  );

  it.each([
    ['/chat', 'auth-guard:Decision Desk'],
    ['/portfolio', 'auth-guard:Portfolio'],
    ['/backtest', 'auth-guard:Backtest'],
  ])(
    'keeps guest access on %s and renders the route-level paywall',
    async (path, expectedPaywallText) => {
      renderAtWithLocationProbe(path);

      expect(await screen.findByText(expectedPaywallText)).toBeInTheDocument();
      expect(screen.getByTestId('location-path')).toHaveTextContent(path);
      expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
    },
  );

  it('redirects locale-prefixed guest settings access to the locale guest page', async () => {
    languageState.value = 'en';
    renderAtWithLocationProbe('/en/settings/system');

    expect(await screen.findByText('Guest Preview Mode')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent('/en/guest'));
  });

  it('keeps locale-prefixed guest portfolio access on the same route and renders the paywall', async () => {
    languageState.value = 'en';
    renderAtWithLocationProbe('/en/portfolio');

    expect(await screen.findByText('auth-guard:Portfolio')).toBeInTheDocument();
    expect(screen.getByTestId('location-path')).toHaveTextContent('/en/portfolio');
  });

  it('redirects away from login to the home workspace after authentication succeeds', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: false,
      isAdminMode: false,
      adminCapabilities: noCapabilities,
    });

    renderAt('/login?redirect=%2Fportfolio');

    expect(await screen.findByText('Home Workspace')).toBeInTheDocument();
    expect(screen.queryByText('login-page')).not.toBeInTheDocument();
  });

  it('keeps the login route available for bootstrap setup when auth is disabled but no password exists', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: false,
      loggedIn: false,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
      passwordSet: false,
      setupState: 'no_password',
    });

    renderAt('/login');

    expect(await screen.findByText('login-page')).toBeInTheDocument();
    expect(screen.queryByText('首页工作区')).not.toBeInTheDocument();
  });

  it('supports the register route as an account-creation entry', async () => {
    renderAt('/register?redirect=%2Fscanner');

    expect(await screen.findByText('login-page')).toBeInTheDocument();
  });

  it('treats preview routes as preview pages outside dev-only mode checks', () => {
    expect(isPreviewRoutePath('/__preview/report')).toBe(true);
    expect(isPreviewRoutePath('/en/__preview/full-report')).toBe(true);
    expect(isPreviewRoutePath('/scanner')).toBe(false);
  });

  it('shows the admin-account gate when a normal user visits an admin route', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: false,
      isAdminMode: false,
    });

    renderAt('/settings/system');

    expect(await screen.findByRole('heading', { name: 'This page requires an admin account' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open personal settings' })).toHaveAttribute('href', '/settings');
  });

  it('shows the admin-tools gate when an admin account stays in regular mode', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: true,
      isAdminMode: false,
      adminCapabilities: fullCapabilities,
    });

    renderAt('/settings/system');

    await waitFor(() => expect(screen.getByText('system-settings-page')).toBeInTheDocument());
  });

  it('renders admin routes for admin accounts without a separate admin mode', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: true,
      isAdminMode: true,
      adminCapabilities: fullCapabilities,
    });

    renderAt('/settings/system');

    await waitFor(() => expect(screen.getByText('system-settings-page')).toBeInTheDocument());
  });

  it('renders the localized market provider operations route for admin accounts', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: true,
      isAdminMode: true,
      adminCapabilities: fullCapabilities,
    });

    renderAt('/zh/admin/market-providers');

    await waitFor(() => expect(screen.getByText('market-provider-operations-page')).toBeInTheDocument());
  });

  it('renders the localized provider circuit diagnostics route for admin accounts', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: true,
      isAdminMode: true,
      adminCapabilities: fullCapabilities,
    });

    renderAt('/zh/admin/provider-circuits');

    await waitFor(() => expect(screen.getByText('admin-provider-circuit-diagnostics-page')).toBeInTheDocument());
  });

  it('blocks an admin account from market providers when capability fields are absent', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: true,
      isAdminAccount: true,
      isAdminMode: true,
      adminCapabilities: noCapabilities,
    });

    renderAt('/zh/admin/market-providers');

    expect(await screen.findByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeInTheDocument();
    expect(screen.queryByText('market-provider-operations-page')).not.toBeInTheDocument();
  });

  it.each([
    ['/zh/admin/logs', { ...noCapabilities, canReadOpsLogs: true }, 'admin-logs-page'],
    ['/zh/admin/notifications', { ...noCapabilities, canReadNotifications: true }, 'admin-notifications-page'],
    ['/zh/admin/market-providers', { ...noCapabilities, canReadProviders: true }, 'market-provider-operations-page'],
    ['/zh/admin/provider-circuits', { ...noCapabilities, canReadProviders: true }, 'admin-provider-circuit-diagnostics-page'],
    ['/zh/admin/cost-observability', { ...noCapabilities, canReadCostObservability: true }, 'admin-cost-observability-page'],
    ['/zh/admin/evidence-workflow', { ...noCapabilities, canReadOpsLogs: true }, 'admin-evidence-workflow-page'],
    ['/zh/settings/system', { ...noCapabilities, canReadSystemConfig: true }, 'system-settings-page'],
  ])('renders %s only with its matching capability', async (path, adminCapabilities, pageText) => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: true,
      isAdminMode: true,
      adminCapabilities,
    });

    renderAt(path);

    await waitFor(() => expect(screen.getByText(pageText)).toBeInTheDocument());
  });

  it('blocks evidence workflow access when admin ops-log capability is absent', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: true,
      isAdminAccount: true,
      isAdminMode: true,
      adminCapabilities: noCapabilities,
    });

    renderAt('/zh/admin/evidence-workflow');

    expect(await screen.findByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeInTheDocument();
    expect(screen.queryByText('admin-evidence-workflow-page')).not.toBeInTheDocument();
  });

  it('renders the localized cost observability route for admin accounts', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: true,
      isAdminMode: true,
      adminCapabilities: fullCapabilities,
    });

    renderAt('/zh/admin/cost-observability');

    await waitFor(() => expect(screen.getByText('admin-cost-observability-page')).toBeInTheDocument());
  });

  it('shows the admin-account gate on the cost observability route for normal users', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: false,
      isAdminMode: false,
      adminCapabilities: noCapabilities,
    });

    renderAt('/zh/admin/cost-observability');

    expect(await screen.findByRole('heading', { name: '这个成本观测页面需要管理员账户' })).toBeInTheDocument();
    expect(screen.queryByText('admin-cost-observability-page')).not.toBeInTheDocument();
  });

  it.each(['/zh/admin/users', '/zh/admin/users/user-1', '/zh/admin/users/user-1/activity'])(
    'renders the localized admin user governance route for admin accounts at %s',
    async (path) => {
      useAuthMock.mockReturnValue({
        authEnabled: true,
        loggedIn: true,
        isLoading: false,
        loadError: null,
        refreshStatus: vi.fn(),
      });
      useProductSurfaceMock.mockReturnValue({
        isGuest: false,
        isAdmin: true,
        isAdminMode: true,
        adminCapabilities: fullCapabilities,
      });

      renderAt(path);

      await waitFor(() => expect(screen.getByText('admin-users-page')).toBeInTheDocument());
    },
  );

  it('keeps scanner reachable for signed-in users', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: false,
      isAdminMode: false,
      adminCapabilities: noCapabilities,
    });

    renderAt('/scanner');

    expect(await screen.findByText('scanner-surface-page')).toBeInTheDocument();
  });

  it('renders the localized market rotation radar route', async () => {
    languageState.value = 'zh';

    renderAt('/zh/market/rotation-radar');

    expect(await screen.findByText('market-rotation-radar-page')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '轮动雷达' })).toHaveAttribute('href', '/zh/market/rotation-radar');
  });

  it('renders the rule backtest compare workbench route for signed-in users', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: false,
      isAdminMode: false,
      adminCapabilities: noCapabilities,
    });

    renderAt('/backtest/compare?runIds=101,202');

    expect(await screen.findByText('backtest-compare-page')).toBeInTheDocument();
  });

  it('renders the localized options lab route for signed-in users', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: false,
      isAdminMode: false,
      adminCapabilities: noCapabilities,
    });

    renderAt('/zh/options-lab');

    expect(await screen.findByText('options-lab-page')).toBeInTheDocument();
  });

  it('renders an auth guard instead of an empty root for logged-out direct options lab entry', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: false,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: true,
      isAdmin: false,
      isAdminMode: false,
      adminCapabilities: noCapabilities,
    });

    renderAt('/zh/options-lab');

    expect(await screen.findByText('auth-guard:期权实验室')).toBeInTheDocument();
    expect(screen.queryByText('options-lab-page')).not.toBeInTheDocument();
  });

  it.each(['/backtest/results/123', '/zh/backtest/results/123'])(
    'renders the deterministic backtest result route for signed-in users at %s',
    async (path) => {
      useAuthMock.mockReturnValue({
        authEnabled: true,
        loggedIn: true,
        isLoading: false,
        loadError: null,
        refreshStatus: vi.fn(),
      });
      useProductSurfaceMock.mockReturnValue({
        isGuest: false,
        isAdmin: false,
        isAdminMode: false,
        adminCapabilities: noCapabilities,
      });

      renderAt(path);

      expect(await screen.findByText('backtest-result-page')).toBeInTheDocument();
    },
  );

  it('redirects legacy locale guest scanner path to the guest surface', async () => {
    renderAt('/en/guest/scanner');

    expect(await screen.findByText('scanner-surface-page')).toBeInTheDocument();
    expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
  });

  it('redirects legacy locale user scanner path to the guest surface for guests', async () => {
    renderAt('/zh/user/scanner');

    expect(await screen.findByText('scanner-surface-page')).toBeInTheDocument();
    expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
  });
});
