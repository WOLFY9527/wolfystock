import { useContext, useEffect } from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { translate } from '../../../i18n/core';
import { ThemeProvider } from '../../theme/ThemeProvider';
import { expectNoRawI18nKeys } from '../../../test-utils/i18nRawKeySentinel';
import { Shell } from '../Shell';
import { ShellRailContext } from '../ShellRailContext';
import { setAdminSurfaceMode } from '../../../hooks/useProductSurface';
import { useStockPoolStore } from '../../../stores';

const { mockLogout, mockHardRedirect, useAuthMock } = vi.hoisted(() => ({
  mockLogout: vi.fn().mockResolvedValue(undefined),
  mockHardRedirect: vi.fn(),
  useAuthMock: vi.fn(),
}));

vi.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('../../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: 'zh',
    toggleLanguage: vi.fn(),
    t: (key: string, vars?: Record<string, string | number | undefined>) => translate('zh', key, vars),
  }),
}));

vi.mock('../../../utils/browserRedirect', () => ({
  hardRedirect: (...args: unknown[]) => mockHardRedirect(...args),
}));

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-color-scheme: dark)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

afterEach(() => {
  window.innerWidth = 1024;
  window.dispatchEvent(new Event('resize'));
  document.body.style.overflow = '';
});

const ShellRailFixture = () => {
  const { setRailContent } = useContext(ShellRailContext);

  useEffect(() => {
    setRailContent(<div>archive content</div>);
    return () => {
      setRailContent(null);
    };
  }, [setRailContent]);

  return <div>page content</div>;
};

const settleDrawerMotion = () => new Promise((resolve) => window.setTimeout(resolve, 260));
const settleDrawerStability = () => new Promise((resolve) => window.setTimeout(resolve, 480));
const fullCapabilityAdminUser = {
  isAdmin: true,
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

describe('Shell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setAdminSurfaceMode('user');
    window.sessionStorage.clear();
    window.localStorage.clear();
    useStockPoolStore.getState().resetDashboardState();
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      currentUser: { isAdmin: false },
      logout: mockLogout,
    });
  });

  it('renders the streamlined navigation without the old theme control', () => {
    render(
      <MemoryRouter initialEntries={['/market-overview']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(screen.queryByRole('button', { name: '切换主题' })).not.toBeInTheDocument();
    const brandLink = screen.getByRole('link', { name: 'WolfyStock' });
    expect(brandLink).toHaveAttribute('href', '/');
    const logo = within(brandLink).getByRole('img', { name: 'WolfyStock logo' });
    expect(logo).toHaveAttribute('src', '/wolfystock-logo-mark.png');
    expect(logo).not.toHaveClass('invert');
    const scannerLink = screen.getByRole('link', { name: '扫描器' });
    expect(scannerLink).toHaveClass('text-sm', 'font-medium', 'text-white/50');
    expect(screen.getByRole('link', { name: translate('zh', 'nav.marketOverview') })).toHaveClass('text-sm', 'font-bold', 'text-white');
    expect(screen.queryByTestId('chat-completion-badge')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '账户中心' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: translate('zh', 'nav.independentConsole') })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '退出' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '决策台' })).not.toBeInTheDocument();
    expect(document.querySelector('.shell-content-frame')).toHaveClass('shell-content-frame--wide');
    expect(document.querySelector('.shell-content-frame--chat')).toBeNull();
    expect(document.querySelector('.shell-main-column')).toHaveClass('px-6', 'pt-6', 'pb-12', 'md:px-8', 'xl:px-12');
    expect(document.querySelector('.shell-main-column--chat')).toBeNull();
    expect(document.querySelector('.theme-page-transition')).toHaveClass('h-full', 'min-h-0');
    expect(document.querySelector('.theme-page-transition--chat')).toBeNull();
  });

  it('renders the complete primary navigation on desktop', async () => {
    render(
      <MemoryRouter initialEntries={['/watchlist']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const primaryNav = screen.getByRole('navigation', { name: translate('zh', 'shell.drawerTitle') });
    expectNoRawI18nKeys(primaryNav);
    expect(within(primaryNav).getByRole('link', { name: translate('zh', 'nav.home') })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: translate('zh', 'nav.scanner') })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: translate('zh', 'nav.portfolio') })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: translate('zh', 'nav.marketOverview') })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: '流动性监测' })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: '轮动雷达' })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: translate('zh', 'nav.watchlist') })).toHaveClass('is-active');
    expect(within(primaryNav).getByRole('link', { name: translate('zh', 'nav.backtest') })).toBeInTheDocument();
    expect(within(primaryNav).queryByRole('link', { name: '决策台' })).not.toBeInTheDocument();
    expect(within(primaryNav).queryByRole('link', { name: 'Decision Desk' })).not.toBeInTheDocument();
  });

  it('highlights the localized liquidity monitor nav item independently from market overview', async () => {
    render(
      <MemoryRouter initialEntries={['/zh/market/liquidity-monitor']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const primaryNav = screen.getByRole('navigation', { name: translate('zh', 'shell.drawerTitle') });
    const liquidityLink = within(primaryNav).getByRole('link', { name: '流动性监测' });
    const overviewLink = within(primaryNav).getByRole('link', { name: translate('zh', 'nav.marketOverview') });

    expect(liquidityLink).toHaveAttribute('href', '/zh/market/liquidity-monitor');
    expect(liquidityLink).toHaveClass('is-active');
    expect(overviewLink).toHaveAttribute('href', '/zh/market-overview');
    expect(overviewLink).not.toHaveClass('is-active');
    expect(document.querySelector('.theme-shell--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
  });

  it('highlights the localized rotation radar nav item independently from market overview', async () => {
    render(
      <MemoryRouter initialEntries={['/zh/market/rotation-radar']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const primaryNav = screen.getByRole('navigation', { name: translate('zh', 'shell.drawerTitle') });
    const rotationLink = within(primaryNav).getByRole('link', { name: '轮动雷达' });
    const overviewLink = within(primaryNav).getByRole('link', { name: translate('zh', 'nav.marketOverview') });

    expect(rotationLink).toHaveAttribute('href', '/zh/market/rotation-radar');
    expect(rotationLink).toHaveClass('is-active');
    expect(overviewLink).toHaveAttribute('href', '/zh/market-overview');
    expect(overviewLink).not.toHaveClass('is-active');
    expect(document.querySelector('.theme-shell--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
  });

  it('shows the guest navigation routes without member-only account controls', () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: false,
      currentUser: null,
      logout: mockLogout,
    });

    render(
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: translate('zh', 'nav.home') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.scanner') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.portfolio') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.marketOverview') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.backtest') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.signIn') })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '账户中心' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: translate('zh', 'nav.settings') })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: translate('zh', 'nav.logout') })).not.toBeInTheDocument();
  });

  it('falls back to the guest-safe shell when auth is disabled and no user is logged in', () => {
    useAuthMock.mockReturnValue({
      authEnabled: false,
      loggedIn: false,
      currentUser: null,
      logout: mockLogout,
    });

    render(
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(screen.queryByRole('link', { name: '登录' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '退出' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: '首页' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '扫描器' })).toBeInTheDocument();
  });

  it('shows a confirmation dialog before logout', async () => {
    render(
      <MemoryRouter initialEntries={['/market-overview']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: '账户中心' }));
    fireEvent.click(await screen.findByRole('button', { name: '退出登录' }));

    expect(await screen.findByRole('heading', { name: translate('zh', 'nav.logoutTitle') })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'nav.logoutConfirm') }));

    await waitFor(() => expect(mockLogout).toHaveBeenCalled());
    expect(mockHardRedirect).not.toHaveBeenCalled();
  });

  it('keeps language/logout controls inside the mobile drawer instead of duplicating them in the top bar', async () => {
    window.innerWidth = 375;

    render(
      <MemoryRouter initialEntries={['/market-overview']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(screen.queryByRole('button', { name: '切换主题' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '切换语言' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '打开导航菜单' }));

    expect(await screen.findByRole('button', { name: '切换语言' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '退出' })).toBeInTheDocument();
  });

  it('renders a compact mobile header with the active route label', () => {
    window.innerWidth = 390;

    render(
      <MemoryRouter initialEntries={['/watchlist']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(screen.getByRole('button', { name: '打开导航菜单' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'WolfyStock' })).toBeInTheDocument();
    expect(screen.getByTestId('shell-mobile-active-route')).toHaveTextContent(translate('zh', 'nav.watchlist'));
    expect(screen.queryByRole('navigation', { name: translate('zh', 'shell.drawerTitle') })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '账户中心' })).not.toBeInTheDocument();
  });

  it('opens a mobile admin menu with all primary routes and account actions', async () => {
    window.innerWidth = 390;
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      currentUser: fullCapabilityAdminUser,
      logout: mockLogout,
    });

    render(
      <MemoryRouter initialEntries={['/watchlist']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: '打开导航菜单' }));

    expect(await screen.findByRole('heading', { name: translate('zh', 'shell.drawerTitle') })).toBeInTheDocument();
    const drawerNav = screen.getByRole('navigation', { name: translate('zh', 'shell.drawerTitle') });
    expect(within(drawerNav).getByRole('link', { name: translate('zh', 'nav.home') })).toBeInTheDocument();
    expect(within(drawerNav).getByRole('link', { name: translate('zh', 'nav.scanner') })).toBeInTheDocument();
    expect(within(drawerNav).getByRole('link', { name: translate('zh', 'nav.portfolio') })).toBeInTheDocument();
    expect(within(drawerNav).getByRole('link', { name: translate('zh', 'nav.marketOverview') })).toBeInTheDocument();
    expect(within(drawerNav).getByRole('link', { name: '轮动雷达' })).toBeInTheDocument();
    expect(within(drawerNav).getByRole('link', { name: translate('zh', 'nav.watchlist') })).toHaveClass('is-active');
    expect(within(drawerNav).getByRole('link', { name: translate('zh', 'nav.backtest') })).toBeInTheDocument();
    const accountPanel = screen.getByTestId('shell-mobile-account-center');
    expect(accountPanel).toBeInTheDocument();
    expect(within(accountPanel).getByRole('link', { name: '账户中心' })).toBeInTheDocument();
    expect(within(accountPanel).getByRole('link', { name: '账户与安全' })).toBeInTheDocument();
    expect(within(accountPanel).getByRole('link', { name: '修改密码' })).toBeInTheDocument();
    expect(within(accountPanel).getByRole('link', { name: '隐私设置' })).toBeInTheDocument();
    expect(within(accountPanel).getByRole('link', { name: '显示偏好' })).toBeInTheDocument();
    expect(within(accountPanel).getByRole('button', { name: '退出登录' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('zh', 'language.toggle') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.settings') })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'nav.independentConsole') }));
    expect(await screen.findByTestId('shell-admin-utility-menu')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.independentConsole') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'adminNav.logs') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '证据复核' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.notifications') })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('zh', 'nav.logout') })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    await act(async () => {
      await settleDrawerMotion();
    });
  });

  it('keeps the mobile navigation drawer open until the user closes it or navigates away', async () => {
    window.innerWidth = 375;

    render(
      <MemoryRouter initialEntries={['/market-overview']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: '打开导航菜单' }));
    expect(await screen.findByRole('heading', { name: '导航菜单' })).toBeInTheDocument();

    await act(async () => {
      await settleDrawerStability();
    });

    expect(screen.getByRole('heading', { name: '导航菜单' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '切换语言' })).toBeInTheDocument();
  });

  it('adds dedicated shell modifiers for the scanner route', () => {
    render(
      <MemoryRouter initialEntries={['/scanner']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(document.querySelector('.theme-shell--scanner')).not.toBeNull();
    expect(document.querySelector('.theme-shell--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--scanner')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame')).toHaveClass('flex', 'w-full', 'min-w-0');
    expect(document.querySelector('.shell-main-column--scanner')).not.toBeNull();
    expect(document.querySelector('.shell-main-column')).toHaveClass('relative', 'w-full', 'min-w-0', 'px-6', 'md:px-8', 'xl:px-12', 'pt-6', 'pb-12');
    expect(document.documentElement.dataset.scannerShell).toBe('true');
    expect(document.body.dataset.scannerShell).toBe('true');
  });

  it('adds wide-shell modifiers for the home route without enabling backtest mode', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(document.querySelector('.theme-shell--wide')).not.toBeNull();
    expect(document.querySelector('.theme-shell--home')).not.toBeNull();
    expect(document.querySelector('.theme-shell--page-scroll')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--home')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--page-scroll')).not.toBeNull();
    expect(document.querySelector('.shell-main-column--home')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--backtest')).toBeNull();
  });

  it('uses the full-width workspace lane for the market overview route', () => {
    render(
      <MemoryRouter initialEntries={['/market-overview']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(document.querySelector('.theme-shell--market-overview')).not.toBeNull();
    expect(document.querySelector('.theme-shell--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
    expect(document.querySelector('.shell-main-column')).toHaveClass('w-full', 'flex-1', 'px-6', 'md:px-8', 'xl:px-12', 'pt-6', 'pb-12');
    expect(document.querySelector('.shell-main-column')).not.toHaveClass('mx-auto', 'max-w-[1600px]');
    expect(document.documentElement.dataset.marketOverviewShell).toBe('true');
    expect(document.body.dataset.marketOverviewShell).toBe('true');
  });

  it('uses the full-width workspace lane for the localized watchlist route', () => {
    render(
      <MemoryRouter initialEntries={['/zh/watchlist']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const primaryNav = screen.getByRole('navigation', { name: translate('zh', 'shell.drawerTitle') });
    expect(within(primaryNav).getByRole('link', { name: translate('zh', 'nav.watchlist') })).toHaveClass('is-active');
    expect(document.querySelector('.theme-shell--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
    expect(document.querySelector('.shell-main-column')).toHaveClass('w-full', 'flex-1', 'px-6', 'md:px-8', 'xl:px-12', 'pt-6', 'pb-12');
    expect(document.querySelector('.shell-content-frame--scanner')).toBeNull();
    expect(document.querySelector('.theme-shell--market-overview')).toBeNull();
    expect(document.querySelector('.shell-content-frame--backtest')).toBeNull();
  });

  it('treats the system settings route as a wide workspace surface', () => {
    render(
      <MemoryRouter initialEntries={['/settings/system']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(document.querySelector('.theme-shell--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
  });

  it('keeps admin logs on the system-control shell with a localized mobile route label', () => {
    window.innerWidth = 390;

    render(
      <MemoryRouter initialEntries={['/admin/logs']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(screen.getByTestId('shell-mobile-active-route')).toHaveTextContent(translate('zh', 'adminNav.logs'));
    expect(document.querySelector('.theme-shell--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--system-control')).not.toBeNull();
    expect(document.querySelector('.shell-main-column')).toHaveClass('shell-main-column--system-control', 'p-0');
    expect(document.querySelector('.theme-page-transition')).toHaveClass('theme-page-transition--system-control');
  });

  it('uses the wide workspace lane for the backtest route', () => {
    render(
      <MemoryRouter initialEntries={['/backtest']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(document.querySelector('.theme-shell--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--backtest')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame')).toHaveClass('flex', 'w-full', 'min-w-0');
    expect(document.querySelector('.shell-main-column')).toHaveClass('w-full', 'flex-1', 'px-6', 'md:px-8', 'xl:px-12', 'pt-6', 'pb-12');
    expect(document.querySelector('.shell-main-column')).not.toHaveClass('mx-auto', 'max-w-[1600px]');
  });

  it('keeps the masthead and route frame on full-width shell tokens', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(document.querySelector('.shell-masthead')).toHaveClass('w-full');
    expect(document.querySelector('.shell-masthead__inner')).toHaveClass('w-full');
    expect(document.querySelector('.theme-shell')).toHaveClass('min-h-screen');
    expect(document.querySelector('.shell-main-column')).toHaveClass('w-full', 'flex-1', 'flex', 'flex-col', 'px-4', 'md:px-6', 'xl:px-8', 'pt-3', 'pb-8', 'min-h-0', 'min-w-0', 'shell-main-column--home', 'shell-main-column--page-scroll');
    expect(document.querySelector('.theme-page-transition')).toHaveClass('w-full', 'min-w-0', 'theme-page-transition--page-scroll');
    expect(document.querySelector('.theme-page-transition')).not.toHaveClass('h-full');
    expect(document.documentElement).toHaveAttribute('data-page-scroll-shell', 'true');
    expect(document.body).toHaveAttribute('data-page-scroll-shell', 'true');
  });

  it('shows a compact admin utility entry in the desktop masthead for authorized admins', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      currentUser: fullCapabilityAdminUser,
      logout: mockLogout,
    });

    render(
      <MemoryRouter initialEntries={['/settings']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const actionIsland = await screen.findByTestId('shell-header-utility-island');
    expect(screen.getByRole('button', { name: '账户中心' })).toBeInTheDocument();
    expect(within(actionIsland).getByRole('button', { name: translate('zh', 'nav.independentConsole') })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /管理员模式/ })).not.toBeInTheDocument();
  });

  it('groups header utilities inside a compact Linear OS action island', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      currentUser: fullCapabilityAdminUser,
      logout: mockLogout,
    });

    render(
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const actionIsland = await screen.findByTestId('shell-header-utility-island');
    expect(screen.getByRole('button', { name: '账户中心' })).toBeInTheDocument();
    expect(actionIsland).toHaveClass(
      'flex',
      'items-center',
      'gap-0.5',
      'rounded-lg',
      'bg-[var(--wolfy-surface-rail)]',
      'border',
      'border-[color:var(--wolfy-border-subtle)]',
      'px-1.5',
      'py-1',
    );
    expect(within(actionIsland).getByRole('button', { name: translate('zh', 'language.toggle') })).toHaveTextContent('EN');
    expect(within(actionIsland).getByRole('link', { name: translate('zh', 'nav.settings') })).toBeInTheDocument();
    const adminMenuButton = within(actionIsland).getByRole('button', { name: translate('zh', 'nav.independentConsole') });
    expect(adminMenuButton).toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: '证据复核' })).not.toBeInTheDocument();
    fireEvent.click(adminMenuButton);
    expect(await screen.findByTestId('shell-admin-utility-menu')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.marketProviders') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'adminNav.logs') })).toBeInTheDocument();
    expect(within(actionIsland).getByRole('button', { name: translate('zh', 'nav.logout') })).toBeInTheDocument();
    expect(actionIsland.querySelectorAll('[data-testid="shell-header-utility-divider"]')).toHaveLength(2);
  });

  it('shows only capability-authorized admin entries inside the compact control menu', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      currentUser: {
        isAdmin: true,
        canReadUsers: true,
        canReadCostObservability: true,
        canReadOpsLogs: false,
        canReadProviders: false,
        canReadNotifications: false,
        canReadSystemConfig: false,
      },
      logout: mockLogout,
    });

    render(
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const actionIsland = await screen.findByTestId('shell-header-utility-island');
    fireEvent.click(within(actionIsland).getByRole('button', { name: translate('zh', 'nav.independentConsole') }));
    expect(await screen.findByRole('link', { name: translate('zh', 'nav.userGovernance') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.costObservability') })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '证据复核' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: translate('zh', 'adminNav.logs') })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: translate('zh', 'nav.notifications') })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: translate('zh', 'nav.marketProviders') })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: translate('zh', 'nav.providerCircuits') })).not.toBeInTheDocument();
  });

  it('shows only ops-log destinations when the admin account has only log capability', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      currentUser: {
        isAdmin: true,
        canReadUsers: false,
        canReadCostObservability: false,
        canReadOpsLogs: true,
        canReadProviders: false,
        canReadNotifications: false,
        canReadSystemConfig: false,
      },
      logout: mockLogout,
    });

    render(
      <MemoryRouter initialEntries={['/zh/admin/logs']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const actionIsland = await screen.findByTestId('shell-header-utility-island');
    fireEvent.click(within(actionIsland).getByRole('button', { name: translate('zh', 'nav.independentConsole') }));
    expect(await screen.findByRole('link', { name: '证据复核' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'adminNav.logs') })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Evidence Review' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: translate('zh', 'nav.userGovernance') })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: translate('zh', 'nav.costObservability') })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: translate('zh', 'nav.notifications') })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: translate('zh', 'nav.marketProviders') })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: translate('zh', 'nav.providerCircuits') })).not.toBeInTheDocument();
  });

  it('does not show evidence workflow nav for adjacent admin capabilities without ops-log read', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      currentUser: {
        isAdmin: true,
        canReadUsers: true,
        canReadCostObservability: true,
        canReadOpsLogs: false,
        canReadProviders: true,
        canReadNotifications: true,
        canReadSystemConfig: true,
      },
      logout: mockLogout,
    });

    render(
      <MemoryRouter initialEntries={['/zh/admin/market-providers']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const actionIsland = await screen.findByTestId('shell-header-utility-island');
    fireEvent.click(within(actionIsland).getByRole('button', { name: translate('zh', 'nav.independentConsole') }));
    expect(await screen.findByRole('link', { name: translate('zh', 'nav.independentConsole') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.userGovernance') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.costObservability') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.notifications') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.marketProviders') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.providerCircuits') })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '证据复核' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: translate('zh', 'adminNav.logs') })).not.toBeInTheDocument();
  });

  it('fails closed for sensitive admin nav when capability fields are absent', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      currentUser: { isAdmin: true },
      logout: mockLogout,
    });

    render(
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const actionIsland = await screen.findByTestId('shell-header-utility-island');
    expect(within(actionIsland).queryByRole('button', { name: translate('zh', 'nav.independentConsole') })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: '证据复核' })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.userGovernance') })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.costObservability') })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.notifications') })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.marketProviders') })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.providerCircuits') })).not.toBeInTheDocument();
  });

  it('resets mobile drawer and archive rail state when crossing back to desktop', async () => {
    window.innerWidth = 390;

    render(
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider>
          <Shell>
            <ShellRailFixture />
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '打开导航菜单' }));
      await settleDrawerMotion();
    });
    expect(await screen.findByRole('heading', { name: '导航菜单' })).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getAllByRole('button', { name: '分析档案' })[0]);
      await settleDrawerMotion();
    });
    await waitFor(() => {
      expect(screen.getAllByRole('dialog')).toHaveLength(1);
    });
    expect(document.body.style.overflow).toBe('hidden');

    window.innerWidth = 1280;
    await act(async () => {
      fireEvent(window, new Event('resize'));
      await settleDrawerMotion();
    });

    await waitFor(() => {
      expect(screen.queryAllByRole('dialog')).toHaveLength(0);
      expect(document.body.style.overflow).toBe('');
    });

    window.innerWidth = 390;
    await act(async () => {
      fireEvent(window, new Event('resize'));
      await settleDrawerMotion();
    });

    await waitFor(() => {
      expect(screen.queryAllByRole('dialog')).toHaveLength(0);
    });
    expect(screen.getByRole('button', { name: '打开导航菜单' })).toBeInTheDocument();
  });
});
