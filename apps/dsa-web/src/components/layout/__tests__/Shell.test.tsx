import { useContext, useEffect } from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { translate } from '../../../i18n/core';
import { ThemeProvider } from '../../theme/ThemeProvider';
import { Shell } from '../Shell';
import { ShellRailContext } from '../ShellRailContext';
import { setAdminSurfaceMode } from '../../../hooks/useProductSurface';
import { useStockPoolStore } from '../../../stores';

const { mockLogout, mockGetAgentStatus, mockHardRedirect, useAuthMock } = vi.hoisted(() => ({
  mockLogout: vi.fn().mockResolvedValue(undefined),
  mockGetAgentStatus: vi.fn().mockResolvedValue({ enabled: true }),
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

vi.mock('../../../stores/agentChatStore', () => ({
  useAgentChatStore: (selector: (state: { completionBadge: boolean }) => unknown) =>
    selector({ completionBadge: true }),
}));

vi.mock('../../../api/agent', () => ({
  agentApi: {
    getStatus: (...args: unknown[]) => mockGetAgentStatus(...args),
  },
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

  it('renders the streamlined navigation and completion badge without the old theme control', () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
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
    expect(screen.getByRole('link', { name: translate('zh', 'nav.chat') })).toBeInTheDocument();
    const scannerLink = screen.getByRole('link', { name: '扫描器' });
    expect(scannerLink).toHaveClass('text-sm', 'font-medium', 'text-[#8a8f98]');
    expect(screen.getByRole('link', { name: translate('zh', 'nav.chat') })).toHaveClass('text-sm', 'font-semibold', 'text-[#f7f8f8]');
    expect(screen.getByTestId('chat-completion-badge')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '退出' })).toBeInTheDocument();
    expect(document.querySelector('.shell-content-frame')).toHaveClass('shell-content-frame--chat', 'shell-content-frame--wide');
    expect(document.querySelector('.shell-main-column')).toHaveClass('shell-main-column--chat', 'p-0');
    expect(document.querySelector('.shell-main-column')).not.toHaveClass('px-6', 'pt-6', 'pb-12', 'md:px-8', 'xl:px-12');
    expect(document.querySelector('.theme-page-transition')).toHaveClass('theme-page-transition--chat', 'h-full', 'min-h-0');
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
    expect(within(primaryNav).getByRole('link', { name: translate('zh', 'nav.home') })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: translate('zh', 'nav.scanner') })).toBeInTheDocument();
    expect(await within(primaryNav).findByRole('link', { name: translate('zh', 'nav.chat') })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: translate('zh', 'nav.portfolio') })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: translate('zh', 'nav.marketOverview') })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: '流动性监测' })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: '轮动雷达' })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: translate('zh', 'nav.watchlist') })).toHaveClass('is-active');
    expect(within(primaryNav).getByRole('link', { name: translate('zh', 'nav.backtest') })).toBeInTheDocument();
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
    expect(screen.getByRole('link', { name: translate('zh', 'nav.chat') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.portfolio') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.backtest') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.signIn') })).toBeInTheDocument();
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

  it('keeps the Ask Stock navigation entry accessible when the agent runtime is unavailable', async () => {
    mockGetAgentStatus.mockResolvedValueOnce({ enabled: false });

    render(
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: translate('zh', 'nav.chat') })).toBeInTheDocument();
  });

  it('shows a confirmation dialog before logout', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'nav.logout') }));

    expect(await screen.findByRole('heading', { name: translate('zh', 'nav.logoutTitle') })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'nav.logoutConfirm') }));

    await waitFor(() => expect(mockLogout).toHaveBeenCalled());
    expect(mockHardRedirect).not.toHaveBeenCalled();
  });

  it('keeps language/logout controls inside the mobile drawer instead of duplicating them in the top bar', async () => {
    window.innerWidth = 375;

    render(
      <MemoryRouter initialEntries={['/chat']}>
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
    expect(await within(drawerNav).findByRole('link', { name: translate('zh', 'nav.chat') })).toBeInTheDocument();
    expect(within(drawerNav).getByRole('link', { name: translate('zh', 'nav.portfolio') })).toBeInTheDocument();
    expect(within(drawerNav).getByRole('link', { name: translate('zh', 'nav.marketOverview') })).toBeInTheDocument();
    expect(within(drawerNav).getByRole('link', { name: '轮动雷达' })).toBeInTheDocument();
    expect(within(drawerNav).getByRole('link', { name: translate('zh', 'nav.watchlist') })).toHaveClass('is-active');
    expect(within(drawerNav).getByRole('link', { name: translate('zh', 'nav.backtest') })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('zh', 'language.toggle') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.settings') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('zh', 'nav.independentConsole') })).toBeInTheDocument();
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
      <MemoryRouter initialEntries={['/chat']}>
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
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
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

  it('adds a dedicated content-frame modifier for the backtest route', () => {
    render(
      <MemoryRouter initialEntries={['/backtest']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(document.querySelector('.shell-content-frame--backtest')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame')).toHaveClass('flex', 'w-full', 'min-w-0');
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
    expect(document.querySelector('.shell-main-column')).toHaveClass('w-full', 'flex-1', 'flex', 'flex-col', 'px-6', 'md:px-8', 'xl:px-12', 'pt-6', 'pb-12', 'min-h-0', 'min-w-0');
    expect(document.querySelector('.theme-page-transition')).toHaveClass('w-full', 'min-w-0');
  });

  it('shows the console entry for admin accounts without an admin-mode switch', async () => {
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

    expect(await screen.findByRole('link', { name: translate('zh', 'nav.independentConsole') })).toHaveAttribute('href', '/settings/system');
    expect(screen.queryByRole('button', { name: /管理员模式/ })).not.toBeInTheDocument();
  });

  it('groups header utilities inside a shared glass action island', async () => {
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
    expect(actionIsland).toHaveClass(
      'flex',
      'items-center',
      'gap-0.5',
      'rounded-lg',
      'bg-[#0f1011]',
      'border',
      'border-[#23252a]',
      'px-1',
      'py-0.5',
      'shadow-none',
    );
    expect(within(actionIsland).getByRole('button', { name: translate('zh', 'language.toggle') })).toHaveTextContent('EN');
    expect(within(actionIsland).getByRole('link', { name: translate('zh', 'nav.settings') })).toBeInTheDocument();
    expect(within(actionIsland).getByRole('link', { name: translate('zh', 'nav.independentConsole') })).toBeInTheDocument();
    expect(within(actionIsland).getByRole('link', { name: '证据复核' })).toBeInTheDocument();
    expect(within(actionIsland).getByRole('button', { name: translate('zh', 'nav.logout') })).toBeInTheDocument();
    expect(actionIsland.querySelectorAll('[data-testid="shell-header-utility-divider"]')).toHaveLength(2);
  });

  it('hides capability-specific admin nav entries when current user lacks them', async () => {
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
    expect(within(actionIsland).getByRole('link', { name: translate('zh', 'nav.userGovernance') })).toBeInTheDocument();
    expect(within(actionIsland).getByRole('link', { name: translate('zh', 'nav.costObservability') })).toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.independentConsole') })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: '证据复核' })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.notifications') })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.marketProviders') })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.providerCircuits') })).not.toBeInTheDocument();
  });

  it('shows only the Chinese-first evidence workflow nav entry for ops-log admins', async () => {
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
    const evidenceLink = within(actionIsland).getByRole('link', { name: '证据复核' });
    expect(evidenceLink).toHaveAttribute('href', '/zh/admin/evidence-workflow');
    expect(within(actionIsland).queryByRole('link', { name: 'Evidence Review' })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.independentConsole') })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.userGovernance') })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.costObservability') })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.notifications') })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.marketProviders') })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.providerCircuits') })).not.toBeInTheDocument();
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
    expect(within(actionIsland).queryByRole('link', { name: '证据复核' })).not.toBeInTheDocument();
    expect(within(actionIsland).getByRole('link', { name: translate('zh', 'nav.independentConsole') })).toBeInTheDocument();
    expect(within(actionIsland).getByRole('link', { name: translate('zh', 'nav.userGovernance') })).toBeInTheDocument();
    expect(within(actionIsland).getByRole('link', { name: translate('zh', 'nav.costObservability') })).toBeInTheDocument();
    expect(within(actionIsland).getByRole('link', { name: translate('zh', 'nav.notifications') })).toBeInTheDocument();
    expect(within(actionIsland).getByRole('link', { name: translate('zh', 'nav.marketProviders') })).toBeInTheDocument();
    expect(within(actionIsland).getByRole('link', { name: translate('zh', 'nav.providerCircuits') })).toBeInTheDocument();
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
    expect(within(actionIsland).queryByRole('link', { name: translate('zh', 'nav.independentConsole') })).not.toBeInTheDocument();
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
