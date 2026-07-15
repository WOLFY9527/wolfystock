import type React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Outlet, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppContent } from '../App';
import { translate } from '../i18n/core';

const { useAuthMock, useProductSurfaceMock, setLanguageMock, languageState } = vi.hoisted(() => ({
  useAuthMock: vi.fn(),
  useProductSurfaceMock: vi.fn(),
  setLanguageMock: vi.fn(),
  languageState: { value: 'zh' as 'zh' | 'en' },
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => useAuthMock(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock('../hooks/useProductSurface', () => ({
  useProductSurface: () => useProductSurfaceMock(),
}));

vi.mock('../contexts/UiLanguageContext', () => ({
  UiLanguageRouteSynchronizer: () => null,
  useI18n: () => ({
    language: languageState.value,
    setLanguage: (language: 'zh' | 'en') => {
      languageState.value = language;
      setLanguageMock(language);
    },
    t: (key: string, vars?: Record<string, string | number | undefined>) => translate(languageState.value, key, vars),
  }),
}));

vi.mock('../components/layout/Shell', () => ({
  Shell: () => <Outlet />,
}));

vi.mock('../components/common/BrandedLoadingScreen', () => ({
  BrandedLoadingScreen: () => null,
}));

vi.mock('../pages/HomeSurfacePage', () => ({
  default: () => <div>home-surface-page</div>,
}));

vi.mock('../pages/GuestHomePage', () => ({
  default: () => <div>guest-home-page</div>,
}));

vi.mock('../pages/ScannerSurfacePage', () => ({
  default: () => <div>scanner-surface-page</div>,
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

vi.mock('../pages/PersonalSettingsPage', () => ({
  default: () => <div>personal-settings-page</div>,
}));

vi.mock('../pages/SystemSettingsPage', () => ({
  default: () => <div>system-settings-page</div>,
}));

vi.mock('../pages/PortfolioPage', () => ({
  default: () => <div>portfolio-page</div>,
}));

vi.mock('../pages/MarketOverviewPage', () => ({
  default: () => <div>market-overview-page</div>,
}));

vi.mock('../pages/MarketDecisionCockpitPage', () => ({
  default: () => <div>market-decision-cockpit-page</div>,
}));

vi.mock('../pages/LiquidityMonitorPage', () => ({
  default: () => <div>liquidity-monitor-page</div>,
}));

vi.mock('../pages/MarketRotationRadarPage', () => ({
  default: () => <div>market-rotation-radar-page</div>,
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

vi.mock('../pages/WatchlistPage', () => ({
  default: () => <div>watchlist-page</div>,
}));

vi.mock('../pages/BacktestPage', () => ({
  default: () => <div>backtest-page</div>,
}));

vi.mock('../pages/OptionsLabPage', () => ({
  default: () => <div>options-lab-page</div>,
}));

vi.mock('../pages/RuleBacktestComparePage', () => ({
  default: () => <div>rule-backtest-compare-page</div>,
}));

vi.mock('../pages/DeterministicBacktestResultPage', () => ({
  default: () => <div>deterministic-backtest-result-page</div>,
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

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location-state">{`${location.pathname}${location.search}`}</div>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LocationProbe />
      <AppContent />
    </MemoryRouter>,
  );
}

describe('Protected route auth-required flows', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    languageState.value = 'zh';
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: false,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
      setupState: 'password_retained',
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: true,
      isAdmin: false,
      isAdminAccount: false,
      isAdminMode: false,
      adminCapabilities: {
        canReadUsers: false,
        canReadUserActivity: false,
        canReadUserPortfolio: false,
        canWriteUserSecurity: false,
        canReadCostObservability: false,
        canReadOpsLogs: false,
        canReadProviders: false,
        canReadNotifications: false,
        canReadSystemConfig: false,
      },
    });
  });

  it('shows a consumer-safe auth-required overlay for guest access to /settings and preserves the redirect target', async () => {
    renderAt('/settings');

    expect(await screen.findByRole('dialog', { name: '个人设置' })).toBeInTheDocument();
    expect(screen.getByTestId('auth-guard-capability')).toHaveTextContent('个人设置');
    expect(screen.getByTestId('auth-guard-status-pill')).toHaveTextContent('需要登录');
    expect(screen.getByText('请先登录后继续访问该页面。')).toBeInTheDocument();
    expect(screen.getByText('登录后可返回刚才的研究页面。')).toBeInTheDocument();
    expect(screen.getByTestId('auth-guard-preview-note')).toBeInTheDocument();
    expect(screen.getByTestId('location-state')).toHaveTextContent('/settings');
    expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
    expect(screen.queryByText('guest-home-page')).not.toBeInTheDocument();

    const overlayText = screen.getByTestId('auth-guard-card').textContent || '';
    expect(overlayText).not.toMatch(/token|session|cookie|bearer|auth header|debug|provider|runtime|stack|Error:|requestId|traceId|schemaVersion|policyVersion|raw|internal|local_db|fallback_source|fixture|adapter|cache/i);
    expect(overlayText).not.toMatch(/buy|sell|hold|recommend|target|stop|position size|买入|卖出|持有|推荐|目标价|止损|仓位建议|加仓|减仓/i);

    fireEvent.click(screen.getByRole('link', { name: '前往登录 个人设置' }));
    await waitFor(() => expect(screen.getByTestId('location-state')).toHaveTextContent('/login?redirect=%2Fsettings'));
    expect(screen.getByText('login-page')).toBeInTheDocument();
  });

  it('keeps representative research routes on the consumer protected boundary with sign-in primary action', async () => {
    renderAt('/portfolio');

    expect(await screen.findByRole('dialog', { name: '持仓管理' })).toBeInTheDocument();
    expect(screen.getByTestId('consumer-protected-frame')).toHaveAttribute(
      'data-boundary-family',
      'consumer-protected',
    );
    expect(screen.getByTestId('auth-guard-capability')).toHaveTextContent('持仓管理');
    expect(screen.getByTestId('auth-guard-primary-action')).toHaveAttribute(
      'href',
      '/login?redirect=%2Fportfolio',
    );
    expect(screen.getByTestId('auth-guard-secondary-action')).toHaveAttribute('href', '/market-overview');
    expect(screen.queryByText('portfolio-page')).not.toBeInTheDocument();
  });

  it('renders authenticated member product surface instead of the protected frame', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
      setupState: 'password_retained',
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: false,
      isAdminAccount: false,
      isAdminMode: false,
      adminCapabilities: {
        canReadUsers: false,
        canReadUserActivity: false,
        canReadUserPortfolio: false,
        canWriteUserSecurity: false,
        canReadCostObservability: false,
        canReadOpsLogs: false,
        canReadProviders: false,
        canReadNotifications: false,
        canReadSystemConfig: false,
      },
    });

    renderAt('/portfolio');

    expect(await screen.findByText('portfolio-page')).toBeInTheDocument();
    expect(screen.queryByTestId('auth-guard-overlay')).not.toBeInTheDocument();
    expect(screen.queryByTestId('consumer-protected-frame')).not.toBeInTheDocument();
  });


  it('keeps the admin settings route fail-closed with a sign-in link that preserves the localized target', async () => {
    renderAt('/zh/settings/system');

    expect(await screen.findByText('需要管理员登录')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '请使用管理员账户登录后打开系统设置' })).toBeInTheDocument();
    expect(screen.getByTestId('location-state')).toHaveTextContent('/zh/settings/system');
    expect(screen.queryByText('not-found-page')).not.toBeInTheDocument();
    expect(screen.queryByText('system-settings-page')).not.toBeInTheDocument();

    const signInLink = screen.getByRole('link', { name: '登录' });
    expect(signInLink).toHaveAttribute('href', '/zh/login?redirect=%2Fzh%2Fsettings%2Fsystem');

    const gateText = document.body.textContent || '';
    expect(gateText).not.toMatch(/token|session|cookie|bearer|auth header|debug|provider|runtime|stack|Error:|requestId|traceId|schemaVersion|policyVersion|raw|internal|local_db|fallback_source|fixture|adapter|cache/i);
    expect(gateText).not.toMatch(/buy|sell|hold|recommend|target|stop|position size|买入|卖出|持有|推荐|目标价|止损|仓位建议|加仓|减仓/i);
  });
});
