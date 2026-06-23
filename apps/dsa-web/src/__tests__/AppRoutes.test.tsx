import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App, { AppContent } from '../App';
import { expectNoRawI18nKeys } from '../test-utils/i18nRawKeySentinel';
import { isPreviewRoutePath } from '../utils/appRouteGuards';
import type { AdminCapabilityFlags } from '../utils/adminCapabilities';

const { useAuthMock, useProductSurfaceMock, setLanguageMock, languageState, previewReportPanelImportSpy, routeCrashState } = vi.hoisted(() => ({
  useAuthMock: vi.fn(),
  useProductSurfaceMock: vi.fn(),
  setLanguageMock: vi.fn(),
  languageState: { value: 'zh' as 'zh' | 'en' },
  previewReportPanelImportSpy: vi.fn(),
  routeCrashState: {
    marketOverview: false,
  },
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
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock('../hooks/useProductSurface', () => ({
  buildLoginPath: (path: string) => `/login?redirect=${encodeURIComponent(path)}`,
  buildRegistrationPath: (path: string) => `/login?mode=create&redirect=${encodeURIComponent(path)}`,
  resolveAuthRedirect: (search: string, fallback = '/') => new URLSearchParams(search).get('redirect') || fallback,
  useProductSurface: () => useProductSurfaceMock(),
}));

vi.mock('../contexts/UiLanguageContext', async () => {
  const { translate } = await vi.importActual<typeof import('../i18n/core')>('../i18n/core');
  return {
    useI18n: () => ({
      language: languageState.value,
      setLanguage: (language: 'zh' | 'en') => {
        languageState.value = language;
        setLanguageMock(language);
      },
      t: (key: string, vars?: Record<string, string | number | undefined>) => translate(languageState.value, key, vars),
    }),
  };
});

vi.mock('../components/common/ApiErrorAlert', () => ({
  ApiErrorAlert: () => <div>api-error</div>,
}));

vi.mock('../components/common/BrandedLoadingScreen', () => ({
  BrandedLoadingScreen: () => null,
}));

vi.mock('../components/report/StandardReportPanel', async () => {
  previewReportPanelImportSpy();
  await new Promise((resolve) => {
    setTimeout(resolve, 100);
  });

  return {
    StandardReportPanel: ({ report }: { report: { summary?: { analysisSummary?: string } } }) => (
      <div data-testid="route-preview-standard-report">{report.summary?.analysisSummary}</div>
    ),
  };
});

vi.mock('../pages/HomeSurfacePage', () => {
  const MockHomeSurfacePage = () => (
    <div>
      {useProductSurfaceMock().isGuest
        ? (languageState.value === 'en' ? 'Guest Preview Mode' : '游客预览模式')
        : (languageState.value === 'en' ? 'Home Workspace' : '首页工作区')}
    </div>
  );

  return {
    default: MockHomeSurfacePage,
  };
});

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

vi.mock('../components/auth/AuthGuardOverlay', () => ({
  AuthGuardOverlay: ({ moduleName }: { moduleName: string }) => <div>{`auth-guard:${moduleName}`}</div>,
}));

vi.mock('../pages/PortfolioPage', () => ({
  default: () => <div>portfolio-page</div>,
}));

vi.mock('../pages/MarketOverviewPage', () => ({
  default: () => {
    if (routeCrashState.marketOverview) {
      throw new Error('provider runtime failure requestId=req-123 token=bearer-abc stack trace');
    }
    return <div>market-overview-page</div>;
  },
}));

vi.mock('../pages/MarketDecisionCockpitPage', () => ({
  default: () => <div>market-decision-cockpit-page</div>,
}));

vi.mock('../pages/MarketRotationRadarPage', () => ({
  default: () => <div>market-rotation-radar-page</div>,
}));

vi.mock('../pages/LiquidityMonitorPage', () => ({
  default: () => <div>liquidity-monitor-page</div>,
}));

vi.mock('../pages/StockStructureDecisionPage', () => ({
  default: () => <div>stock-structure-decision-page</div>,
}));

vi.mock('../pages/StockStructureDecisionEntryPage', () => ({
  default: () => <div>stock-structure-entry-page</div>,
}));

vi.mock('../pages/ResearchRadarPage', () => ({
  default: () => <div>research-radar-page</div>,
}));

vi.mock('../pages/ScenarioLabPage', () => ({
  default: () => <div>scenario-lab-page</div>,
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

vi.mock('../pages/AdminMissionControlPage', () => ({
  default: () => <div>admin-mission-control-page</div>,
}));

vi.mock('../pages/AdminLaunchCockpitPage', () => ({
  default: () => <div>admin-launch-cockpit-page</div>,
}));

vi.mock('../pages/LoginPage', () => ({
  default: () => <div>login-page</div>,
}));

vi.mock('../pages/ResetPasswordPage', () => ({
  default: () => <div>reset-password-page</div>,
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

function renderBrowserAppAt(path: string) {
  window.history.replaceState(window.history.state, '', path);
  return render(<App />);
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

const publicMarketRouteSafetyPattern = /admin-|system-settings-page|personal-settings-page|portfolio-page|watchlist-page|provider|diagnostic|debug|raw|schemaVersion|requestId|traceId|token|cookie|bearer|\b(buy|sell|hold|recommend|target|stop|position size)\b|买入|卖出|持有|推荐|目标价|止损|仓位建议|加仓|减仓/i;

function mockSignedInConsumer() {
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
    ...noCapabilities,
  });
}

function mockSignedInAdminWithCapabilities(adminCapabilities: AdminCapabilityFlags) {
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
    adminCapabilities,
    ...adminCapabilities,
  });
}

function mockAuthBootstrapLoadError(refreshStatus = vi.fn()) {
  useAuthMock.mockReturnValue({
    authEnabled: false,
    loggedIn: false,
    isLoading: false,
    loadError: {
      title: '请求超时',
      message: 'raw auth/status timeout detail',
      rawMessage: 'stack trace should not render',
    },
    refreshStatus,
    setupState: 'no_password',
  });
  return refreshStatus;
}

describe('AppContent route flows', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv('VITE_WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED', '');
    routeCrashState.marketOverview = false;
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
      ...noCapabilities,
    });
    languageState.value = 'en';
  });

  it('renders the Chinese guest preview on the root route for anonymous sessions', async () => {
    languageState.value = 'zh';
    renderAt('/');
    expect(await screen.findByText('游客预览模式')).toBeInTheDocument();
    expect(screen.queryByText('login-page')).not.toBeInTheDocument();
  });

  it('renders the English guest preview on the /en route for anonymous sessions', async () => {
    languageState.value = 'en';
    renderAt('/en');
    expect(await screen.findByText('Guest Preview Mode')).toBeInTheDocument();
    expect(screen.queryByText('login-page')).not.toBeInTheDocument();
  });

  it('renders the member home workspace on the root route for signed-in sessions', async () => {
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
    renderAt('/');

    expect(await screen.findByText('Home Workspace')).toBeInTheDocument();
    expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
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

  it('keeps the public home shell renderable when auth bootstrap status cannot be loaded', async () => {
    const refreshStatus = mockAuthBootstrapLoadError();

    languageState.value = 'en';
    renderAt('/');

    expect(await screen.findByText('Guest Preview Mode')).toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Authentication status notice' })).toHaveTextContent(
      'Only guest-safe content is shown until account status is confirmed.',
    );
    expect(screen.queryByText('api-error')).not.toBeInTheDocument();
    expect(screen.queryByText('raw auth/status timeout detail')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(refreshStatus).toHaveBeenCalledTimes(1);
  });

  it('keeps the localized public guest shell renderable when auth bootstrap status cannot be loaded', async () => {
    mockAuthBootstrapLoadError();

    languageState.value = 'zh';
    renderAt('/zh/guest');

    expect(await screen.findByText('游客预览模式')).toBeInTheDocument();
    expect(screen.getByRole('status', { name: '认证状态提示' })).toHaveTextContent(
      '在确认账户状态前，仅显示游客安全内容。',
    );
    expect(screen.queryByText('api-error')).not.toBeInTheDocument();
  });

  it.each(['/options-lab', '/options'])(
    'keeps protected product route %s fail-closed while auth bootstrap status is unavailable',
    async (path) => {
      mockAuthBootstrapLoadError();

      languageState.value = 'en';
      renderAt(path);

      expect(await screen.findByRole('alert', { name: 'Protected route locked' })).toHaveTextContent(
        'Protected pages stay locked until account status is confirmed.',
      );
      expect(screen.queryByText('options-lab-page')).not.toBeInTheDocument();
      expect(screen.queryByText('api-error')).not.toBeInTheDocument();
    },
  );

  it('keeps admin routes fail-closed while auth bootstrap status is unavailable', async () => {
    mockAuthBootstrapLoadError();

    languageState.value = 'en';
    renderAt('/settings/system');

    expect(await screen.findByRole('alert', { name: 'Admin route locked' })).toHaveTextContent(
      'Admin pages stay locked until account and capability status are confirmed.',
    );
    expect(screen.queryByText('system-settings-page')).not.toBeInTheDocument();
    expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
    expect(screen.queryByText('api-error')).not.toBeInTheDocument();
  });

  it.each(['/login', '/register'])(
    'keeps auth entry %s from opening setup-capable forms when bootstrap status is unavailable',
    async (path) => {
      mockAuthBootstrapLoadError();

      languageState.value = 'en';
      renderAt(path);

      expect(await screen.findByRole('alert', { name: 'Authentication entry paused' })).toHaveTextContent(
        'Sign-in and account setup entry points stay paused until account status is confirmed.',
      );
      expect(screen.queryByText('login-page')).not.toBeInTheDocument();
      expect(screen.queryByText('api-error')).not.toBeInTheDocument();
    },
  );

  it('renders the preview report route and resolves the deferred report panel', async () => {
    languageState.value = 'zh';
    renderBrowserAppAt('/__preview/report');

    expect(await screen.findByTestId('preview-report-page')).toBeInTheDocument();
    expect(await screen.findByTestId('route-preview-standard-report')).toHaveTextContent('等待回踩确认');
    expect(previewReportPanelImportSpy).toHaveBeenCalledTimes(1);
  });

  it('renders a consumer-safe global error boundary on real route crashes', async () => {
    languageState.value = 'en';
    routeCrashState.marketOverview = true;
    vi.spyOn(console, 'error').mockImplementation(() => undefined);

    renderBrowserAppAt('/en/market-overview');

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('This page is temporarily unavailable. Refresh or try again shortly.');
    expect(alert).toHaveTextContent('A rendering error interrupted this screen. Technical details are hidden. Retry or return home to continue with other research.');
    expect(within(alert).getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    expect(within(alert).getByRole('button', { name: 'Back to home' })).toBeInTheDocument();
    expect(alert.textContent || '').not.toMatch(/provider|runtime|requestId|token|bearer|stack|trace|error:/i);

    fireEvent.click(within(alert).getByRole('button', { name: 'Back to home' }));
    expect(await screen.findByText('Guest Preview Mode')).toBeInTheDocument();
  });

  it('does not eagerly import the preview report panel on unrelated home routes', async () => {
    languageState.value = 'en';
    renderAt('/en');

    expect(await screen.findByText('Guest Preview Mode')).toBeInTheDocument();
    expect(previewReportPanelImportSpy).not.toHaveBeenCalled();
  });

  it('redirects guest access from /settings to the dedicated guest page', async () => {
    renderAtWithLocationProbe('/settings');

    expect(await screen.findByText('auth-guard:Personal settings')).toBeInTheDocument();
    expect(screen.getByTestId('location-path')).toHaveTextContent('/settings');
    expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
    expect(screen.queryByText('personal-settings-page')).not.toBeInTheDocument();
    expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
  });

  it('keeps guest access on /settings/system fail-closed with an admin sign-in requirement', async () => {
    renderAtWithLocationProbe('/settings/system');

    expect(await screen.findByText('Admin Sign-in Required')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Sign in with an admin account to open system settings' })).toBeInTheDocument();
    expect(screen.getAllByText('This admin-only system settings surface is separate from personal settings, even though its canonical route lives under /settings/system.').length).toBeGreaterThan(0);
    expect(screen.getByTestId('location-path')).toHaveTextContent('/settings/system');
    expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
    expect(screen.queryByText('system-settings-page')).not.toBeInTheDocument();
  });

  it.each([
    ['/portfolio', 'auth-guard:Portfolio'],
    ['/research/radar', 'auth-guard:Research Radar'],
    ['/scenario-lab', 'auth-guard:Scenario Lab'],
    ['/watchlist', 'auth-guard:Watchlist'],
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

  it.each([
    ['/market-overview', 'market-overview-page'],
    ['/market/decision-cockpit', 'market-decision-cockpit-page'],
    ['/market/liquidity-monitor', 'liquidity-monitor-page'],
    ['/market/rotation-radar', 'market-rotation-radar-page'],
  ])('opens public market route %s for guest sessions without private/admin content', async (path, pageText) => {
    renderAtWithLocationProbe(path);

    expect(await screen.findByText(pageText)).toBeInTheDocument();
    expect(screen.getByTestId('location-path')).toHaveTextContent(path);
    expect(screen.queryByText(/auth-guard:/)).not.toBeInTheDocument();
    expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
    expect(document.body.textContent || '').not.toMatch(publicMarketRouteSafetyPattern);
  });

  it.each([
    ['/zh/market-overview', 'market-overview-page'],
    ['/en/market-overview', 'market-overview-page'],
    ['/zh/market/decision-cockpit', 'market-decision-cockpit-page'],
    ['/en/market/decision-cockpit', 'market-decision-cockpit-page'],
    ['/zh/market/liquidity-monitor', 'liquidity-monitor-page'],
    ['/en/market/liquidity-monitor', 'liquidity-monitor-page'],
    ['/zh/market/rotation-radar', 'market-rotation-radar-page'],
    ['/en/market/rotation-radar', 'market-rotation-radar-page'],
  ])('opens localized public market route %s for guest sessions', async (path, pageText) => {
    renderAtWithLocationProbe(path);

    expect(await screen.findByText(pageText)).toBeInTheDocument();
    expect(screen.getByTestId('location-path')).toHaveTextContent(path);
    expect(screen.queryByText(/auth-guard:/)).not.toBeInTheDocument();
    expect(document.body.textContent || '').not.toMatch(publicMarketRouteSafetyPattern);
  });

  it.each([
    ['/zh/market/decision-cockpit', 'market-decision-cockpit-page'],
    ['/en/market/decision-cockpit', 'market-decision-cockpit-page'],
    ['/zh/research/radar', 'research-radar-page'],
    ['/en/research/radar', 'research-radar-page'],
    ['/zh/portfolio', 'portfolio-page'],
    ['/en/portfolio', 'portfolio-page'],
    ['/zh/scenario-lab', 'scenario-lab-page'],
    ['/en/scenario-lab', 'scenario-lab-page'],
  ])('renders the localized core research IA route %s for signed-in users', async (path, expectedText) => {
    mockSignedInConsumer();

    renderAtWithLocationProbe(path);

    expect(await screen.findByText(expectedText)).toBeInTheDocument();
    expect(screen.getByTestId('location-path')).toHaveTextContent(path);
    expect(screen.queryByText(/auth-guard:/)).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Decision Desk' })).not.toBeInTheDocument();
    if (path.includes('/scanner') || path.includes('/portfolio')) {
      expect(screen.queryByText('scenario-lab-page')).not.toBeInTheDocument();
    }
  });

  it.each([
    ['/cockpit', '/market/decision-cockpit', 'market-decision-cockpit-page'],
    ['/zh/cockpit', '/zh/market/decision-cockpit', 'market-decision-cockpit-page'],
    ['/en/cockpit', '/en/market/decision-cockpit', 'market-decision-cockpit-page'],
    ['/decision-cockpit', '/market/decision-cockpit', 'market-decision-cockpit-page'],
    ['/zh/decision-cockpit', '/zh/market/decision-cockpit', 'market-decision-cockpit-page'],
    ['/en/decision-cockpit', '/en/market/decision-cockpit', 'market-decision-cockpit-page'],
    ['/research-radar', '/research/radar', 'auth-guard:Research Radar'],
    ['/zh/research-radar', '/zh/research/radar', 'auth-guard:研究雷达'],
    ['/en/research-radar', '/en/research/radar', 'auth-guard:Research Radar'],
    ['/radar', '/research/radar', 'auth-guard:Research Radar'],
    ['/zh/radar', '/zh/research/radar', 'auth-guard:研究雷达'],
    ['/en/radar', '/en/research/radar', 'auth-guard:Research Radar'],
  ])('redirects legacy research IA alias %s to canonical route %s', async (path, expectedPath, expectedText) => {
    renderAtWithLocationProbe(path);

    expect(await screen.findByText(expectedText)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent(expectedPath));
    expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
  });

  it.each([
    ['/holdings', '/portfolio', 'auth-guard:Portfolio'],
    ['/zh/holdings', '/zh/portfolio', 'auth-guard:持仓管理'],
    ['/en/holdings', '/en/portfolio', 'auth-guard:Portfolio'],
  ])('redirects holdings alias %s to canonical portfolio route %s', async (path, expectedPath, expectedText) => {
    renderAtWithLocationProbe(path);

    expect(await screen.findByText(expectedText)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent(expectedPath));
    expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
  });

  it.each([
    ['/holdings', '/portfolio'],
    ['/zh/holdings', '/zh/portfolio'],
    ['/en/holdings', '/en/portfolio'],
  ])('renders holdings alias %s through canonical portfolio route %s for signed-in users', async (path, expectedPath) => {
    mockSignedInConsumer();

    renderAtWithLocationProbe(path);

    expect(await screen.findByText('portfolio-page')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent(expectedPath));
    expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
    expect(screen.queryByText(/auth-guard:/)).not.toBeInTheDocument();
  });

  it('keeps guest access on the stock structure route protected with a stock-specific gate', async () => {
    renderAtWithLocationProbe('/stocks/AAPL/structure-decision');

    expect(await screen.findByText('auth-guard:Stock Structure Panel')).toBeInTheDocument();
    expect(screen.getByTestId('location-path')).toHaveTextContent('/stocks/AAPL/structure-decision');
    expect(screen.queryByText('stock-structure-decision-page')).not.toBeInTheDocument();
    expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
  });

  it.each([
    ['/stock/AAPL', '/stocks/AAPL/structure-decision'],
    ['/zh/stock/AAPL', '/zh/stocks/AAPL/structure-decision'],
    ['/en/stock/AAPL', '/en/stocks/AAPL/structure-decision'],
  ])('redirects legacy stock route %s to the stock research surface', async (path, expectedPath) => {
    renderAtWithLocationProbe(path);

    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent(expectedPath));
    expect(await screen.findByText(path.startsWith('/zh/') ? 'auth-guard:个股结构面板' : 'auth-guard:Stock Structure Panel')).toBeInTheDocument();
    expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
    expect(screen.queryByText('stock-structure-decision-page')).not.toBeInTheDocument();
  });

  it('redirects the browser legacy stock route before the catch-all can render NotFound', async () => {
    renderBrowserAppAt('/stock/AAPL?source=bookmark#snapshot');

    await waitFor(() => {
      expect(window.location.pathname).toBe('/stocks/AAPL/structure-decision');
      expect(window.location.search).toBe('?source=bookmark');
      expect(window.location.hash).toBe('#snapshot');
    });
    expect(await screen.findByText('auth-guard:Stock Structure Panel')).toBeInTheDocument();
    expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
    expect(screen.queryByText('stock-structure-decision-page')).not.toBeInTheDocument();
  });

  it('opens the stock structure entry route for guest sessions without a paywall', async () => {
    renderAtWithLocationProbe('/stocks/structure-decision');

    expect(await screen.findByText('stock-structure-entry-page')).toBeInTheDocument();
    expect(screen.getByTestId('location-path')).toHaveTextContent('/stocks/structure-decision');
    expect(screen.queryByText('auth-guard:Stock Structure Panel')).not.toBeInTheDocument();
  });

  it.each([
    ['/zh/stocks/structure-decision', 'stock-structure-entry-page'],
    ['/en/stocks/structure-decision', 'stock-structure-entry-page'],
    ['/zh/stocks/AAPL/structure-decision', 'auth-guard:个股结构面板'],
    ['/en/stocks/AAPL/structure-decision', 'auth-guard:Stock Structure Panel'],
  ])('renders localized Stock Structure Decision route %s without exposing a legacy decision desk', async (path, expectedText) => {
    renderAtWithLocationProbe(path);

    expect(await screen.findByText(expectedText)).toBeInTheDocument();
    expect(screen.getByTestId('location-path')).toHaveTextContent(path);
    if (path.includes('/AAPL/')) {
      expect(screen.queryByText('stock-structure-decision-page')).not.toBeInTheDocument();
    }
    expect(screen.queryByRole('link', { name: 'Decision Desk' })).not.toBeInTheDocument();
  });

  it('redirects /market to the market overview surface instead of silently falling back to Home', async () => {
    renderAtWithLocationProbe('/market');

    expect(await screen.findByText('market-overview-page')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent('/market-overview'));
    expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
    expect(screen.queryByText('auth-guard:Market Overview')).not.toBeInTheDocument();
  });

  it('redirects /admin to the canonical protected system settings surface instead of silently falling back to Home', async () => {
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

    renderAtWithLocationProbe('/admin');

    expect(await screen.findByRole('heading', { name: 'This page requires an admin account' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent('/settings/system'));
    expect(screen.queryByText('Home Workspace')).not.toBeInTheDocument();
  });

  it('treats /admin/system as an intentional alias for the canonical admin system settings route', async () => {
    renderAtWithLocationProbe('/admin/system');

    expect(await screen.findByText('Admin Sign-in Required')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Sign in with an admin account to open system settings' })).toBeInTheDocument();
    expect(screen.getAllByText('This admin-only system settings surface is separate from personal settings, even though its canonical route lives under /settings/system.').length).toBeGreaterThan(0);
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent('/settings/system'));
    expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
    expect(screen.queryByText('system-settings-page')).not.toBeInTheDocument();
  });

  it.each([
    ['/admin/system', '/settings/system', { ...noCapabilities, canReadSystemConfig: true }, 'system-settings-page'],
    ['/admin/system-logs', '/admin/logs', { ...noCapabilities, canReadOpsLogs: true }, 'admin-logs-page'],
    ['/admin/providers', '/admin/market-providers', { ...noCapabilities, canReadProviders: true }, 'market-provider-operations-page'],
    ['/admin/provider', '/admin/market-providers', { ...noCapabilities, canReadProviders: true }, 'market-provider-operations-page'],
    ['/admin/evidence', '/admin/evidence-workflow', { ...noCapabilities, canReadOpsLogs: true }, 'admin-evidence-workflow-page'],
    ['/admin/costs', '/admin/cost-observability', { ...noCapabilities, canReadCostObservability: true }, 'admin-cost-observability-page'],
    ['/admin/ai', '/settings/system', { ...noCapabilities, canReadSystemConfig: true }, 'system-settings-page'],
    ['/zh/admin/system', '/zh/settings/system', { ...noCapabilities, canReadSystemConfig: true }, 'system-settings-page'],
    ['/zh/admin/system-logs', '/zh/admin/logs', { ...noCapabilities, canReadOpsLogs: true }, 'admin-logs-page'],
    ['/zh/admin/providers', '/zh/admin/market-providers', { ...noCapabilities, canReadProviders: true }, 'market-provider-operations-page'],
    ['/zh/admin/provider', '/zh/admin/market-providers', { ...noCapabilities, canReadProviders: true }, 'market-provider-operations-page'],
    ['/zh/admin/evidence', '/zh/admin/evidence-workflow', { ...noCapabilities, canReadOpsLogs: true }, 'admin-evidence-workflow-page'],
    ['/zh/admin/costs', '/zh/admin/cost-observability', { ...noCapabilities, canReadCostObservability: true }, 'admin-cost-observability-page'],
    ['/zh/admin/ai', '/zh/settings/system', { ...noCapabilities, canReadSystemConfig: true }, 'system-settings-page'],
    ['/en/admin/system', '/en/settings/system', { ...noCapabilities, canReadSystemConfig: true }, 'system-settings-page'],
    ['/en/admin/system-logs', '/en/admin/logs', { ...noCapabilities, canReadOpsLogs: true }, 'admin-logs-page'],
    ['/en/admin/providers', '/en/admin/market-providers', { ...noCapabilities, canReadProviders: true }, 'market-provider-operations-page'],
    ['/en/admin/provider', '/en/admin/market-providers', { ...noCapabilities, canReadProviders: true }, 'market-provider-operations-page'],
    ['/en/admin/evidence', '/en/admin/evidence-workflow', { ...noCapabilities, canReadOpsLogs: true }, 'admin-evidence-workflow-page'],
    ['/en/admin/costs', '/en/admin/cost-observability', { ...noCapabilities, canReadCostObservability: true }, 'admin-cost-observability-page'],
    ['/en/admin/ai', '/en/settings/system', { ...noCapabilities, canReadSystemConfig: true }, 'system-settings-page'],
  ])(
    'redirects legacy admin alias %s to canonical route %s',
    async (path, expectedPath, adminCapabilities, pageText) => {
      mockSignedInAdminWithCapabilities(adminCapabilities);

      renderAtWithLocationProbe(path);

      await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent(expectedPath));
      expect(await screen.findByText(pageText)).toBeInTheDocument();
      expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
    },
  );

  it.each([
    ['/admin', '/settings/system', { ...noCapabilities, canReadSystemConfig: true }, 'system-settings-page'],
    ['/admin/users', '/admin/users', { ...noCapabilities, canReadUsers: true }, 'admin-users-page'],
    ['/admin/logs', '/admin/logs', { ...noCapabilities, canReadOpsLogs: true }, 'admin-logs-page'],
    ['/admin/system', '/settings/system', { ...noCapabilities, canReadSystemConfig: true }, 'system-settings-page'],
    ['/admin/provider', '/admin/market-providers', { ...noCapabilities, canReadProviders: true }, 'market-provider-operations-page'],
    ['/admin/market-providers', '/admin/market-providers', { ...noCapabilities, canReadProviders: true }, 'market-provider-operations-page'],
  ])('renders admin route %s for admins without exposing the guest preview', async (path, expectedPath, adminCapabilities, pageText) => {
    mockSignedInAdminWithCapabilities(adminCapabilities);

    renderAtWithLocationProbe(path);

    expect(await screen.findByText(pageText)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent(expectedPath));
    expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
    expect(screen.queryByText('游客预览模式')).not.toBeInTheDocument();
  });

  it.each([
    ['/zh/admin/system', '/zh/settings/system', '需要管理员登录', '/zh/login?redirect=%2Fzh%2Fsettings%2Fsystem'],
    ['/zh/admin/providers', '/zh/admin/market-providers', '需要管理员登录', '/zh/login?redirect=%2Fzh%2Fadmin%2Fmarket-providers'],
    ['/zh/admin/provider', '/zh/admin/market-providers', '需要管理员登录', '/zh/login?redirect=%2Fzh%2Fadmin%2Fmarket-providers'],
    ['/zh/admin/market-providers?surface=market_overview', '/zh/admin/market-providers', '需要管理员登录', '/zh/login?redirect=%2Fzh%2Fadmin%2Fmarket-providers%3Fsurface%3Dmarket_overview'],
    ['/zh/admin/evidence', '/zh/admin/evidence-workflow', '需要管理员登录', '/zh/login?redirect=%2Fzh%2Fadmin%2Fevidence-workflow'],
    ['/zh/admin/costs', '/zh/admin/cost-observability', '需要管理员登录', '/zh/login?redirect=%2Fzh%2Fadmin%2Fcost-observability'],
    ['/zh/admin/ai', '/zh/settings/system', '需要管理员登录', '/zh/login?redirect=%2Fzh%2Fsettings%2Fsystem'],
    ['/en/admin/system', '/en/settings/system', 'Admin Sign-in Required', '/en/login?redirect=%2Fen%2Fsettings%2Fsystem'],
    ['/en/admin/providers', '/en/admin/market-providers', 'Admin Sign-in Required', '/en/login?redirect=%2Fen%2Fadmin%2Fmarket-providers'],
    ['/en/admin/provider', '/en/admin/market-providers', 'Admin Sign-in Required', '/en/login?redirect=%2Fen%2Fadmin%2Fmarket-providers'],
    ['/en/admin/evidence', '/en/admin/evidence-workflow', 'Admin Sign-in Required', '/en/login?redirect=%2Fen%2Fadmin%2Fevidence-workflow'],
    ['/en/admin/costs', '/en/admin/cost-observability', 'Admin Sign-in Required', '/en/login?redirect=%2Fen%2Fadmin%2Fcost-observability'],
    ['/en/admin/ai', '/en/settings/system', 'Admin Sign-in Required', '/en/login?redirect=%2Fen%2Fsettings%2Fsystem'],
  ])('keeps anonymous admin alias %s fail-closed with a sign-in path', async (path, expectedPath, statusLabel, loginHref) => {
    renderAtWithLocationProbe(path);

    expect(await screen.findByText(statusLabel)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent(expectedPath));
    expect(screen.getAllByRole('link', { name: /Sign in|登录/ }).some((link) => link.getAttribute('href') === loginHref)).toBe(true);
    expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
    expect(screen.queryByText('游客预览模式')).not.toBeInTheDocument();
  });

  it.each([
    ['/admin', '/settings/system', 'Admin Sign-in Required', '/login?redirect=%2Fsettings%2Fsystem'],
    ['/admin/users', '/admin/users', 'Admin Sign-in Required', '/login?redirect=%2Fadmin%2Fusers'],
    ['/admin/logs', '/admin/logs', 'Admin Sign-in Required', '/login?redirect=%2Fadmin%2Flogs'],
    ['/admin/system', '/settings/system', 'Admin Sign-in Required', '/login?redirect=%2Fsettings%2Fsystem'],
    ['/admin/provider', '/admin/market-providers', 'Admin Sign-in Required', '/login?redirect=%2Fadmin%2Fmarket-providers'],
    ['/admin/market-providers', '/admin/market-providers', 'Admin Sign-in Required', '/login?redirect=%2Fadmin%2Fmarket-providers'],
    ['/admin/market-providers?surface=market_overview', '/admin/market-providers', 'Admin Sign-in Required', '/login?redirect=%2Fadmin%2Fmarket-providers%3Fsurface%3Dmarket_overview'],
  ])('keeps anonymous admin route %s fail-closed without rendering guest', async (path, expectedPath, statusLabel, loginHref) => {
    languageState.value = 'en';
    renderAtWithLocationProbe(path);

    expect(await screen.findByText(statusLabel)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent(expectedPath));
    expect(screen.getAllByRole('link', { name: 'Sign in' }).some((link) => link.getAttribute('href') === loginHref)).toBe(true);
    expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
    expect(screen.queryByText('游客预览模式')).not.toBeInTheDocument();
    expect(screen.queryByText('admin-users-page')).not.toBeInTheDocument();
    expect(screen.queryByText('admin-logs-page')).not.toBeInTheDocument();
    expect(screen.queryByText('system-settings-page')).not.toBeInTheDocument();
    expect(screen.queryByText('market-provider-operations-page')).not.toBeInTheDocument();
  });

  it.each([
    ['/zh/admin/system', '/zh/settings/system'],
    ['/zh/admin/system-logs', '/zh/admin/logs'],
    ['/zh/admin/providers', '/zh/admin/market-providers'],
    ['/zh/admin/provider', '/zh/admin/market-providers'],
    ['/zh/admin/evidence', '/zh/admin/evidence-workflow'],
    ['/zh/admin/costs', '/zh/admin/cost-observability'],
    ['/zh/admin/ai', '/zh/settings/system'],
  ])('keeps non-admin account gating unchanged for admin alias %s', async (path, expectedPath) => {
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

    renderAtWithLocationProbe(path);

    expect(await screen.findByRole('heading', { name: '这个页面需要管理员账户' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent(expectedPath));
  });

  it.each([
    ['/admin', '/settings/system'],
    ['/admin/users', '/admin/users'],
    ['/admin/logs', '/admin/logs'],
    ['/admin/system', '/settings/system'],
    ['/admin/provider', '/admin/market-providers'],
    ['/admin/market-providers', '/admin/market-providers'],
  ])('keeps non-admin account gating unchanged for admin route %s', async (path, expectedPath) => {
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

    renderAtWithLocationProbe(path);

    expect(await screen.findByRole('heading', { name: /requires an admin account/ })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent(expectedPath));
    expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
  });

  it.each([
    ['/scanner', 'auth-guard:Scanner'],
    ['/zh/scanner', 'auth-guard:扫描器'],
    ['/en/scanner', 'auth-guard:Scanner'],
  ])('keeps guest access on scanner workspace route %s protected', async (path, expectedGateText) => {
    renderAtWithLocationProbe(path);

    expect(await screen.findByText(expectedGateText)).toBeInTheDocument();
    expect(screen.getByTestId('location-path')).toHaveTextContent(path);
    expect(screen.queryByText('scanner-surface-page')).not.toBeInTheDocument();
  });

  it.each([
    ['/options-lab', 'options-lab-page'],
    ['/scenario-lab', 'scenario-lab-page'],
    ['/backtest', 'backtest-page'],
    ['/research/radar', 'research-radar-page'],
    ['/radar', 'research-radar-page'],
  ])('renders UAT-072 core research route %s first viewport for signed-in users', async (path, expectedText) => {
    mockSignedInConsumer();

    renderAtWithLocationProbe(path);

    expect(await screen.findByText(expectedText)).toBeInTheDocument();
    expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
    expect(screen.queryByText(/auth-guard:/)).not.toBeInTheDocument();
    expect(screen.queryByTestId('shell-admin-primary-nav')).not.toBeInTheDocument();
    expect(screen.queryByTestId('shell-admin-utility-menu')).not.toBeInTheDocument();
    expect(document.body.textContent || '').not.toMatch(/provider|runtime|credential|sourceAuthority|debug|requestId|traceId|token|bearer|\b(buy|sell|hold|recommend|winner|target price|stop-loss|position sizing)\b|买入|卖出|持有|推荐|赢家|目标价|止损|仓位|建仓|加仓|减仓/i);
  });

  it('redirects legacy /chat guest access to the market overview surface', async () => {
    renderAtWithLocationProbe('/chat');

    expect(await screen.findByText('market-overview-page')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent('/market-overview'));
    expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
    expect(screen.queryByText('auth-guard:Market Overview')).not.toBeInTheDocument();
  });

  it('redirects locale-prefixed /chat access to the localized market overview surface', async () => {
    languageState.value = 'en';
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

    renderAtWithLocationProbe('/en/chat');

    expect(await screen.findByText('market-overview-page')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent('/en/market-overview'));
  });

  it.each([
    ['/options', '/options-lab', 'auth-guard:Options Lab'],
    ['/zh/options', '/zh/options-lab', 'auth-guard:期权实验室'],
    ['/en/options', '/en/options-lab', 'auth-guard:Options Lab'],
  ])(
    'redirects %s to the canonical protected Options Lab surface without changing guest gating',
    async (path, expectedPath, expectedGateText) => {
      renderAtWithLocationProbe(path);

      expect(await screen.findByText(expectedGateText)).toBeInTheDocument();
      await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent(expectedPath));
      expect(screen.queryByText('options-lab-page')).not.toBeInTheDocument();
    },
  );

  it.each([
    ['/liquidity', '/market/liquidity-monitor'],
    ['/zh/liquidity', '/zh/market/liquidity-monitor'],
    ['/en/liquidity', '/en/market/liquidity-monitor'],
  ])(
    'redirects %s to the canonical Liquidity Monitor surface',
    async (path, expectedPath) => {
      renderAtWithLocationProbe(path);

      expect(await screen.findByText('liquidity-monitor-page')).toBeInTheDocument();
      await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent(expectedPath));
      expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
    },
  );

  it.each([
    ['/rotation', '/market/rotation-radar'],
    ['/zh/rotation', '/zh/market/rotation-radar'],
    ['/en/rotation', '/en/market/rotation-radar'],
  ])(
    'redirects %s to the canonical Rotation Radar surface',
    async (path, expectedPath) => {
      renderAtWithLocationProbe(path);

      expect(await screen.findByText('market-rotation-radar-page')).toBeInTheDocument();
      await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent(expectedPath));
      expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
    },
  );

  it.each([
    ['/options-lab', 'options-lab-page'],
    ['/scanner', 'scanner-surface-page'],
    ['/market/liquidity-monitor', 'liquidity-monitor-page'],
    ['/market/rotation-radar', 'market-rotation-radar-page'],
  ])(
    'keeps the canonical route %s working for a signed-in user',
    async (path, expectedText) => {
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

      renderAtWithLocationProbe(path);

      expect(await screen.findByText(expectedText)).toBeInTheDocument();
      expect(screen.getByTestId('location-path')).toHaveTextContent(path);
    },
  );

  it.each(['/logs', '/users', '/system', '/provider'])(
    'renders NotFound for naked unknown route %s instead of silently falling back to Home',
    async (path) => {
      renderAtWithLocationProbe(path);

      expect(await screen.findByText('not-found-page')).toBeInTheDocument();
      expect(screen.getByTestId('location-path')).toHaveTextContent(path);
      expect(screen.queryByText('Home Workspace')).not.toBeInTheDocument();
      expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
      expect(screen.queryByText('游客预览模式')).not.toBeInTheDocument();
    },
  );

  it.each(['/prototype/scanner-board', '/zh/prototype/scanner-board'])(
    'falls through to NotFound for the removed scanner board prototype route at %s',
    async (path) => {
      renderAtWithLocationProbe(path);

      expect(await screen.findByText('not-found-page')).toBeInTheDocument();
      expect(screen.getByTestId('location-path')).toHaveTextContent(path);
      expect(screen.queryByText('scanner-surface-page')).not.toBeInTheDocument();
    },
  );

  it.each([
    ['/en/settings/system', 'Admin Sign-in Required', '/en/login?redirect=%2Fen%2Fsettings%2Fsystem'],
    ['/en/admin/mission-control', 'Admin Sign-in Required', '/en/login?redirect=%2Fen%2Fadmin%2Fmission-control'],
  ])(
    'keeps locale-prefixed guest admin access %s fail-closed without redirecting to guest',
    async (path, statusLabel, loginHref) => {
      languageState.value = 'en';
      renderAtWithLocationProbe(path);

      expect(await screen.findByText(statusLabel)).toBeInTheDocument();
      expect(screen.getAllByRole('link', { name: 'Sign in' }).some((link) => link.getAttribute('href') === loginHref)).toBe(true);
      expect(screen.getByTestId('location-path')).toHaveTextContent(path);
      expect(screen.queryByText('Guest Preview Mode')).not.toBeInTheDocument();
    },
  );

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
    renderAtWithLocationProbe('/register?redirect=%2Fscanner');

    expect(await screen.findByText('login-page')).toBeInTheDocument();
    expect(screen.getByTestId('location-path')).toHaveTextContent('/register');
  });

  it('supports the locale-prefixed register route as an account-creation entry', async () => {
    renderAtWithLocationProbe('/en/register?redirect=%2Fscanner');

    expect(await screen.findByText('login-page')).toBeInTheDocument();
    expect(screen.getByTestId('location-path')).toHaveTextContent('/en/register');
  });

  it.each(['/reset-password', '/zh/reset-password'])(
    'renders the reset password route outside protected gates at %s',
    async (path) => {
      renderAt(path);

      expect(await screen.findByText('reset-password-page')).toBeInTheDocument();
      expect(screen.queryByText('login-page')).not.toBeInTheDocument();
      expect(screen.queryByText(/auth-guard:/)).not.toBeInTheDocument();
    },
  );

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
      ...fullCapabilities,
    });

    renderAt('/settings/system');

    await waitFor(() => expect(screen.getByText('system-settings-page')).toBeInTheDocument());
  });

  it('renders shell route labels without raw i18n keys or Decision Desk navigation', async () => {
    languageState.value = 'en';
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
      ...fullCapabilities,
    });

    const { container } = renderAt('/en/settings/system');

    await waitFor(() => expect(screen.getByText('system-settings-page')).toBeInTheDocument());
    const primaryNav = screen.getByRole('navigation', { name: 'Admin/Ops navigation' });
    expectNoRawI18nKeys(container);
    expect(within(primaryNav).getByRole('link', { name: 'Ops Overview / System Settings' })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: 'Data Sources & Readiness' })).toBeInTheDocument();
    expect(screen.queryByTestId('shell-consumer-primary-nav')).not.toBeInTheDocument();
    expect(within(primaryNav).queryByRole('link', { name: 'Decision Desk' })).not.toBeInTheDocument();
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
    ['/zh/admin/launch-cockpit', { ...noCapabilities, canReadOpsLogs: true }, 'admin-launch-cockpit-page'],
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
    mockSignedInAdminWithCapabilities(noCapabilities);

    renderAt('/zh/admin/evidence-workflow');

    expect(await screen.findByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeInTheDocument();
    expect(screen.queryByText('admin-evidence-workflow-page')).not.toBeInTheDocument();
  });

  it('blocks launch cockpit access when admin ops-log capability is absent', async () => {
    mockSignedInAdminWithCapabilities(noCapabilities);

    renderAt('/zh/admin/launch-cockpit');

    expect(await screen.findByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeInTheDocument();
    expect(screen.queryByText('admin-launch-cockpit-page')).not.toBeInTheDocument();
  });

  it('blocks mission control access when admin ops-log capability is absent', async () => {
    vi.stubEnv('VITE_WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED', 'true');
    mockSignedInAdminWithCapabilities(noCapabilities);

    renderAt('/zh/admin/mission-control');

    expect(await screen.findByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeInTheDocument();
    expect(screen.queryByText('admin-mission-control-page')).not.toBeInTheDocument();
  });

  it('keeps mission control prototype route disabled by default even for ops-log admins', async () => {
    mockSignedInAdminWithCapabilities({ ...noCapabilities, canReadOpsLogs: true });

    renderAt('/en/admin/mission-control');

    expect(await screen.findByRole('heading', { name: 'Admin Mission Control prototype is disabled' })).toBeInTheDocument();
    expect(screen.queryByText('admin-mission-control-page')).not.toBeInTheDocument();
  });

  it.each([
    ['system config', { ...noCapabilities, canReadSystemConfig: true }],
    ['provider operations', { ...noCapabilities, canReadProviders: true }],
    ['notifications', { ...noCapabilities, canReadNotifications: true }],
    ['cost observability', { ...noCapabilities, canReadCostObservability: true }],
    ['user governance', { ...noCapabilities, canReadUsers: true }],
    ['user activity', { ...noCapabilities, canReadUserActivity: true }],
    ['user portfolio', { ...noCapabilities, canReadUserPortfolio: true }],
    ['user security write', { ...noCapabilities, canWriteUserSecurity: true }],
  ])('does not unlock evidence workflow with adjacent %s capability only', async (_label, adminCapabilities) => {
    mockSignedInAdminWithCapabilities(adminCapabilities);

    renderAt('/zh/admin/evidence-workflow');

    expect(await screen.findByRole('heading', { name: '这个管理页面需要对应管理员能力' })).toBeInTheDocument();
    expect(screen.queryByText('admin-evidence-workflow-page')).not.toBeInTheDocument();
  });

  it('renders evidence workflow with ops logs read as the only admin capability', async () => {
    mockSignedInAdminWithCapabilities({ ...noCapabilities, canReadOpsLogs: true });

    renderAt('/zh/admin/evidence-workflow');

    await waitFor(() => expect(screen.getByText('admin-evidence-workflow-page')).toBeInTheDocument());
    expect(screen.queryByRole('heading', { name: '这个管理页面需要对应管理员能力' })).not.toBeInTheDocument();
  });

  it('renders launch cockpit with ops logs read as the only admin capability', async () => {
    mockSignedInAdminWithCapabilities({ ...noCapabilities, canReadOpsLogs: true });

    renderAt('/zh/admin/launch-cockpit');

    await waitFor(() => expect(screen.getByText('admin-launch-cockpit-page')).toBeInTheDocument());
    expect(screen.queryByRole('heading', { name: '这个管理页面需要对应管理员能力' })).not.toBeInTheDocument();
  });

  it('renders mission control with ops logs read as the only admin capability', async () => {
    vi.stubEnv('VITE_WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED', 'true');
    mockSignedInAdminWithCapabilities({ ...noCapabilities, canReadOpsLogs: true });

    renderAt('/zh/admin/mission-control');

    await waitFor(() => expect(screen.getByText('admin-mission-control-page')).toBeInTheDocument());
    expect(screen.queryByRole('heading', { name: '这个管理页面需要对应管理员能力' })).not.toBeInTheDocument();
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

    expect(await screen.findByRole('heading', { name: '这个页面需要管理员账户' })).toBeInTheDocument();
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
    expect(screen.queryByRole('link', { name: '轮动雷达' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: '市场总览' })).toHaveAttribute('href', '/zh/market-overview');
  });

  it('renders the localized liquidity monitor route', async () => {
    languageState.value = 'zh';

    renderAt('/zh/market/liquidity-monitor');

    expect(await screen.findByText('liquidity-monitor-page')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '流动性监测' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: '市场总览' })).toHaveAttribute('href', '/zh/market-overview');
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

    expect(await screen.findByText('auth-guard:Scanner')).toBeInTheDocument();
    expect(screen.queryByText('scanner-surface-page')).not.toBeInTheDocument();
    expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
  });

  it('redirects legacy locale user scanner path to the guest surface for guests', async () => {
    renderAt('/zh/user/scanner');

    expect(await screen.findByText('auth-guard:扫描器')).toBeInTheDocument();
    expect(screen.queryByText('scanner-surface-page')).not.toBeInTheDocument();
    expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
  });
});
