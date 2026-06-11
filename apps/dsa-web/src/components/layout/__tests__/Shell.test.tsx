import { use, useEffect } from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { translate } from '../../../i18n/core';
import { ThemeProvider } from '../../theme/ThemeProvider';
import { expectNoRawI18nKeys } from '../../../test-utils/i18nRawKeySentinel';
import { Shell } from '../Shell';
import { ShellRailContext } from '../ShellRailContext';
import { setAdminSurfaceMode } from '../../../hooks/useProductSurface';
import { useStockPoolStore } from '../../../stores/stockPoolStore';

const { languageState, mockLogout, mockHardRedirect, useAuthMock } = vi.hoisted(() => ({
  languageState: { value: 'zh' as 'zh' | 'en' },
  mockLogout: vi.fn().mockResolvedValue(undefined),
  mockHardRedirect: vi.fn(),
  useAuthMock: vi.fn(),
}));

vi.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('../../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: languageState.value,
    toggleLanguage: vi.fn(),
    t: (key: string, vars?: Record<string, string | number | undefined>) => translate(languageState.value, key, vars),
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
  const { setRailContent } = use(ShellRailContext);

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
    languageState.value = 'zh';
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

  it('renders the streamlined navigation without the old theme control', async () => {
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
    const actionIsland = await screen.findByTestId('shell-header-utility-island');
    expect(await within(actionIsland).findByTestId('shell-account-center-entry')).toBeInTheDocument();
    expect(within(actionIsland).getByRole('button', { name: '账户中心' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: translate('zh', 'nav.independentConsole') })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '退出' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '决策台' })).not.toBeInTheDocument();
    expect(document.querySelector('.theme-shell')).toHaveClass('theme-shell--consumer', 'theme-shell--page-scroll');
    expect(document.querySelector('.shell-content-frame')).toHaveClass('shell-content-frame--wide', 'shell-content-frame--consumer', 'shell-content-frame--page-scroll');
    expect(document.querySelector('.shell-content-frame--chat')).toBeNull();
    expect(document.querySelector('.shell-main-column')).toHaveClass('p-0', 'shell-main-column--consumer', 'shell-main-column--page-scroll');
    expect(document.querySelector('.shell-main-column--chat')).toBeNull();
    expect(document.querySelector('.theme-page-transition')).toHaveClass('min-h-0', 'theme-page-transition--page-scroll');
    expect(document.querySelector('.theme-page-transition')).not.toHaveClass('h-full');
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

  it('groups the consumer navigation around the private-beta workflow', async () => {
    render(
      <MemoryRouter initialEntries={['/market-overview']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const primaryNav = screen.getByRole('navigation', { name: translate('zh', 'shell.drawerTitle') });
    expect(within(primaryNav).getByTestId('shell-consumer-nav-group-start')).toHaveTextContent('起点');
    expect(within(primaryNav).getByTestId('shell-consumer-nav-group-markets')).toHaveTextContent('市场');
    expect(within(primaryNav).getByTestId('shell-consumer-nav-group-research')).toHaveTextContent('研究');
    expect(within(primaryNav).getByTestId('shell-consumer-nav-group-account')).toHaveTextContent('账户');
    expect(within(primaryNav).getByTestId('shell-consumer-nav-group-validate')).toHaveTextContent('验证');

    const marketGroup = within(primaryNav).getByTestId('shell-consumer-nav-group-markets');
    expect(within(marketGroup).getByRole('link', { name: '市场总览' })).toHaveClass('is-active');
    expect(within(marketGroup).getByRole('link', { name: '流动性监测' })).toHaveAttribute('href', '/market/liquidity-monitor');
    expect(within(marketGroup).getByRole('link', { name: '轮动雷达' })).toHaveAttribute('href', '/market/rotation-radar');
  });

  it('marks member-only consumer links as locked for guests without hiding discovery routes', () => {
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

    const primaryNav = screen.getByRole('navigation', { name: translate('zh', 'shell.drawerTitle') });
    const researchGroup = within(primaryNav).getByTestId('shell-consumer-nav-group-research');
    const accountGroup = within(primaryNav).getByTestId('shell-consumer-nav-group-account');
    const validateGroup = within(primaryNav).getByTestId('shell-consumer-nav-group-validate');

    expect(within(researchGroup).getByRole('link', { name: '扫描器' })).toBeInTheDocument();
    expect(within(researchGroup).getByRole('link', { name: '观察列表' })).toBeInTheDocument();
    expect(within(accountGroup).getByRole('link', { name: '持仓' })).toBeInTheDocument();
    expect(within(validateGroup).getByRole('link', { name: '回测' })).toBeInTheDocument();
    expect(within(validateGroup).getByRole('link', { name: '期权实验室' })).toBeInTheDocument();
    expect(researchGroup).toHaveTextContent('需要登录');
    expect(accountGroup).toHaveTextContent('需要登录');
    expect(validateGroup).toHaveTextContent('需要登录');
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

  it('preserves locale for brand and settings utility links', async () => {
    render(
      <MemoryRouter initialEntries={['/zh/watchlist']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: 'WolfyStock' })).toHaveAttribute('href', '/zh');
    const actionIsland = await screen.findByTestId('shell-header-utility-island');
    expect(within(actionIsland).getByRole('link', { name: '设置' })).toHaveAttribute('href', '/zh/settings');
  });

  it('renders a shared consumer route story with evidence boundary and next-step links', () => {
    render(
      <MemoryRouter initialEntries={['/zh/market/rotation-radar']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const story = screen.getByTestId('consumer-route-story');
    expect(story).toHaveTextContent('市场');
    expect(story).toHaveTextContent('从主题扩散和退潮中找到下一批研究对象');
    expect(story).toHaveTextContent('证据边界');
    expect(story).toHaveTextContent('不产生外部动作');
    expect(within(story).getByRole('link', { name: /查看扫描器/ })).toHaveAttribute('href', '/zh/scanner');
    expect(within(story).getByRole('link', { name: '返回市场总览' })).toHaveAttribute('href', '/zh/market-overview');
  });

  it('localizes market navigation labels consistently in English mode', async () => {
    languageState.value = 'en';

    render(
      <MemoryRouter initialEntries={['/en/market/liquidity-monitor']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const primaryNav = screen.getByRole('navigation', { name: translate('en', 'shell.drawerTitle') });
    expect(within(primaryNav).getByRole('link', { name: 'Home' })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: 'Scanner' })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: 'Holdings' })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: 'Market Overview' })).toBeInTheDocument();
    expect(within(primaryNav).getByRole('link', { name: 'Liquidity Monitor' })).toHaveClass('is-active');
    expect(within(primaryNav).getByRole('link', { name: 'Rotation Radar' })).toBeInTheDocument();
    expect(within(primaryNav).queryByRole('link', { name: '市场总览' })).not.toBeInTheDocument();
    expect(within(primaryNav).queryByRole('link', { name: '流动性监测' })).not.toBeInTheDocument();
    expect(within(primaryNav).queryByRole('link', { name: '轮动雷达' })).not.toBeInTheDocument();
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

    fireEvent.click(await screen.findByRole('button', { name: '账户中心' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: '退出登录' }));

    expect(await screen.findByRole('heading', { name: translate('zh', 'nav.logoutTitle') })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'nav.logoutConfirm') }));

    await waitFor(() => expect(mockLogout).toHaveBeenCalled());
    expect(mockHardRedirect).not.toHaveBeenCalled();
  });

  it('supports keyboard menu navigation and restores focus to the account trigger', async () => {
    render(
      <MemoryRouter initialEntries={['/market-overview']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const trigger = await screen.findByRole('button', { name: '账户中心' });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });

    const menu = await screen.findByRole('menu', { name: '账户中心菜单' });
    const accountItem = within(menu).getByRole('menuitem', { name: '账户中心' });
    await waitFor(() => expect(accountItem).toHaveFocus());

    fireEvent.keyDown(menu, { key: 'ArrowDown' });
    await waitFor(() => expect(within(menu).getByRole('menuitem', { name: '账户与安全' })).toHaveFocus());

    fireEvent.keyDown(menu, { key: 'End' });
    await waitFor(() => expect(within(menu).getByRole('menuitem', { name: '退出登录' })).toHaveFocus());

    fireEvent.keyDown(menu, { key: 'Home' });
    await waitFor(() => expect(accountItem).toHaveFocus());

    fireEvent.keyDown(menu, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('menu', { name: '账户中心菜单' })).not.toBeInTheDocument());
    await waitFor(() => expect(trigger).toHaveFocus());
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

  it('keeps guest mobile drawer free of account center entries', async () => {
    window.innerWidth = 390;
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

    fireEvent.click(screen.getByRole('button', { name: '打开导航菜单' }));

    expect(await screen.findByRole('heading', { name: translate('zh', 'shell.drawerTitle') })).toBeInTheDocument();
    expect(screen.queryByTestId('shell-mobile-account-center')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: '登录' })).toBeInTheDocument();
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

  it('uses the liquidity monitor mobile header label and a 44px-safe menu target', async () => {
    window.innerWidth = 390;

    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/zh/market/liquidity-monitor']}>
          <ThemeProvider>
            <Shell>
              <div>page content</div>
            </Shell>
          </ThemeProvider>
        </MemoryRouter>
      );
    });

    expect(screen.getByTestId('shell-mobile-active-route')).toHaveTextContent('流动性监测');

    const menuButton = screen.getByRole('button', { name: '打开导航菜单' });
    expect(menuButton).toHaveStyle({
      width: '44px',
      minWidth: '44px',
      height: '44px',
      minHeight: '44px',
    });
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
    const adminMenu = await screen.findByTestId('shell-admin-utility-menu');
    expect(adminMenu).toBeInTheDocument();
    expect(within(adminMenu).getByTestId('shell-admin-utility-group-trust')).toHaveTextContent('总览 / Trust');
    expect(within(adminMenu).getByTestId('shell-admin-utility-group-evidence')).toHaveTextContent('事件 / Evidence');
    expect(within(adminMenu).getByTestId('shell-admin-utility-group-dataOps')).toHaveTextContent('数据运行 / Data Ops');
    expect(within(adminMenu).getByTestId('shell-admin-utility-group-support')).toHaveTextContent('用户支持 / Support');
    expect(screen.getByRole('link', { name: '运维总览/系统设置' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '系统日志' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '证据复核' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '通知通道' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('zh', 'nav.logout') })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    await act(async () => {
      await settleDrawerMotion();
    });
  });

  it('shows the mobile account drawer section for signed-in non-admin users without admin controls', async () => {
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

    fireEvent.click(screen.getByRole('button', { name: '打开导航菜单' }));

    expect(await screen.findByRole('heading', { name: translate('zh', 'shell.drawerTitle') })).toBeInTheDocument();
    const accountPanel = screen.getByTestId('shell-mobile-account-center');
    expect(accountPanel).toBeInTheDocument();
    expect(within(accountPanel).getByRole('link', { name: '账户中心' })).toBeInTheDocument();
    expect(within(accountPanel).getByRole('button', { name: '退出登录' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: translate('zh', 'nav.independentConsole') })).not.toBeInTheDocument();
  });

  it('hides the empty admin navigation container for non-admin users on admin-gated routes', async () => {
    render(
      <MemoryRouter initialEntries={['/settings/system']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(screen.queryByTestId('shell-admin-primary-nav')).not.toBeInTheDocument();
    expect(screen.getByTestId('shell-consumer-primary-nav')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: translate('zh', 'nav.independentConsole') })).not.toBeInTheDocument();
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
    expect(document.querySelector('.theme-shell--consumer')).not.toBeNull();
    expect(document.querySelector('.theme-shell--page-scroll')).not.toBeNull();
    expect(document.querySelector('.theme-shell--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--scanner')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--consumer')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--page-scroll')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame')).toHaveClass('flex', 'w-full', 'min-w-0');
    expect(document.querySelector('.shell-main-column--scanner')).not.toBeNull();
    expect(document.querySelector('.shell-main-column')).toHaveClass('relative', 'w-full', 'min-w-0', 'p-0', 'shell-main-column--consumer', 'shell-main-column--page-scroll');
    expect(document.documentElement.dataset.scannerShell).toBe('true');
    expect(document.body.dataset.scannerShell).toBe('true');
    expect(document.documentElement.dataset.pageScrollShell).toBe('true');
    expect(document.body.dataset.pageScrollShell).toBe('true');
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
    expect(document.querySelector('.theme-shell--consumer')).not.toBeNull();
    expect(document.querySelector('.theme-shell--home')).not.toBeNull();
    expect(document.querySelector('.theme-shell--page-scroll')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--consumer')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--home')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--page-scroll')).not.toBeNull();
    expect(document.querySelector('.shell-main-column--consumer')).not.toBeNull();
    expect(document.querySelector('.shell-main-column--home')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--backtest')).toBeNull();
  });

  it.each([
    { path: '/guest', language: 'zh' as const, title: '先确认市场背景', primaryHref: '/market-overview', secondaryHref: '/scanner' },
    { path: '/zh/guest', language: 'zh' as const, title: '先确认市场背景', primaryHref: '/zh/market-overview', secondaryHref: '/zh/scanner' },
    { path: '/en/guest', language: 'en' as const, title: 'Confirm market context', primaryHref: '/en/market-overview', secondaryHref: '/en/scanner' },
  ])('uses the Home shell and story treatment for %s', ({ path, language, title, primaryHref, secondaryHref }) => {
    languageState.value = language;

    render(
      <MemoryRouter initialEntries={[path]}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const story = screen.getByTestId('consumer-route-story');
    expect(story).toHaveTextContent(title);
    expect(story).toHaveTextContent(language === 'en' ? 'research observation' : '研究观察');
    expect(story.querySelectorAll('a')[0]).toHaveAttribute('href', primaryHref);
    expect(story.querySelectorAll('a')[1]).toHaveAttribute('href', secondaryHref);
    expect(document.querySelector('.theme-shell')).toHaveClass('theme-shell--wide', 'theme-shell--consumer', 'theme-shell--home', 'theme-shell--page-scroll', 'min-h-screen');
    expect(document.querySelector('.shell-content-frame')).toHaveClass('shell-content-frame--wide', 'shell-content-frame--consumer', 'shell-content-frame--home', 'shell-content-frame--page-scroll');
    expect(document.querySelector('.shell-main-column')).toHaveClass('shell-main-column--consumer', 'shell-main-column--home', 'shell-main-column--page-scroll', 'p-0');
    expect(document.querySelector('.theme-page-transition')).toHaveClass('theme-page-transition--page-scroll');
    expect(document.documentElement).toHaveAttribute('data-page-scroll-shell', 'true');
    expect(document.body).toHaveAttribute('data-page-scroll-shell', 'true');
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
    expect(document.querySelector('.theme-shell--consumer')).not.toBeNull();
    expect(document.querySelector('.theme-shell--page-scroll')).not.toBeNull();
    expect(document.querySelector('.theme-shell--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--consumer')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--page-scroll')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
    expect(document.querySelector('.shell-main-column')).toHaveClass('w-full', 'flex-1', 'p-0', 'shell-main-column--consumer', 'shell-main-column--page-scroll');
    expect(document.querySelector('.shell-main-column')).not.toHaveClass('mx-auto', 'max-w-[1600px]');
    expect(document.documentElement.dataset.marketOverviewShell).toBe('true');
    expect(document.body.dataset.marketOverviewShell).toBe('true');
    expect(document.documentElement.dataset.pageScrollShell).toBe('true');
    expect(document.body.dataset.pageScrollShell).toBe('true');
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
    expect(document.querySelector('.theme-shell--consumer')).not.toBeNull();
    expect(document.querySelector('.theme-shell--page-scroll')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--consumer')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--page-scroll')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
    expect(document.querySelector('.shell-main-column')).toHaveClass('w-full', 'flex-1', 'p-0', 'shell-main-column--consumer', 'shell-main-column--page-scroll');
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

    expect(screen.getByTestId('shell-mobile-active-route')).toHaveTextContent('系统日志');
    expect(document.querySelector('.theme-shell--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--system-control')).not.toBeNull();
    expect(document.querySelector('.shell-main-column')).toHaveClass('shell-main-column--system-control', 'p-0');
    expect(document.querySelector('.theme-page-transition')).toHaveClass('theme-page-transition--system-control');
  });

  it('uses an admin primary menu instead of consumer routes inside the mobile drawer on admin routes', async () => {
    window.innerWidth = 390;
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      currentUser: fullCapabilityAdminUser,
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

    expect(screen.getByTestId('shell-mobile-active-route')).toHaveTextContent('数据源与就绪度');

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '打开导航菜单' }));
      await settleDrawerMotion();
    });

    const adminNav = await screen.findByTestId('shell-admin-primary-nav');
    expect(within(adminNav).getByRole('link', { name: '运维总览/系统设置' })).toBeInTheDocument();
    expect(within(adminNav).getByRole('link', { name: '数据源与就绪度' })).toHaveClass('is-active');
    expect(within(adminNav).getByRole('link', { name: '熔断诊断' })).toBeInTheDocument();
    expect(within(adminNav).getByRole('link', { name: '系统日志' })).toBeInTheDocument();
    expect(within(adminNav).getByRole('link', { name: '成本观测' })).toBeInTheDocument();
    expect(within(adminNav).getByRole('link', { name: '用户治理' })).toBeInTheDocument();
    expect(within(adminNav).getByRole('link', { name: '证据复核' })).toBeInTheDocument();
    expect(within(adminNav).getByRole('link', { name: '通知通道' })).toBeInTheDocument();
    expect(within(adminNav).queryByRole('link', { name: translate('zh', 'nav.home') })).not.toBeInTheDocument();
    expect(within(adminNav).queryByRole('link', { name: translate('zh', 'nav.scanner') })).not.toBeInTheDocument();
    expect(screen.queryByTestId('shell-consumer-primary-nav')).not.toBeInTheDocument();
    expect(screen.queryByTestId('shell-admin-utility-menu')).not.toBeInTheDocument();
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
    expect(document.querySelector('.theme-shell--consumer')).not.toBeNull();
    expect(document.querySelector('.theme-shell--page-scroll')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--backtest')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--consumer')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--page-scroll')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame--wide')).not.toBeNull();
    expect(document.querySelector('.shell-content-frame')).toHaveClass('flex', 'w-full', 'min-w-0');
    expect(document.querySelector('.shell-main-column')).toHaveClass('w-full', 'flex-1', 'p-0', 'shell-main-column--consumer', 'shell-main-column--page-scroll');
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
    expect(document.querySelector('.theme-shell')).toHaveClass('theme-shell--consumer', 'theme-shell--page-scroll');
    expect(document.querySelector('.shell-content-frame')).toHaveClass('shell-content-frame--consumer', 'shell-content-frame--page-scroll');
    expect(document.querySelector('.shell-main-column')).toHaveClass('w-full', 'flex-1', 'flex', 'flex-col', 'p-0', 'min-h-0', 'min-w-0', 'shell-main-column--consumer', 'shell-main-column--home', 'shell-main-column--page-scroll');
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
    expect(await within(actionIsland).findByTestId('shell-account-center-entry')).toBeInTheDocument();
    expect(within(actionIsland).getByRole('button', { name: '账户中心' })).toBeInTheDocument();
    expect(within(actionIsland).getByRole('button', { name: translate('zh', 'nav.independentConsole') })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /管理员模式/ })).not.toBeInTheDocument();
  });

  it('replaces bootstrap-style admin names with a product-safe account label in the masthead', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      currentUser: {
        ...fullCapabilityAdminUser,
        displayName: 'Bootstrap Admin...',
      },
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
    const accountEntry = await within(actionIsland).findByTestId('shell-account-center-entry');
    expect(accountEntry).toHaveTextContent('管理员');
    expect(accountEntry).not.toHaveTextContent('管理员账户');
    expect(accountEntry).not.toHaveTextContent('Bootstrap Admin...');
  });

  it('uses product-safe English labels for the admin entry and fallback account name', async () => {
    languageState.value = 'en';
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      currentUser: {
        ...fullCapabilityAdminUser,
        displayName: 'Bootstrap Admin...',
      },
      logout: mockLogout,
    });

    render(
      <MemoryRouter initialEntries={['/en/settings']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    const actionIsland = await screen.findByTestId('shell-header-utility-island');
    expect(within(actionIsland).getByRole('button', { name: 'System' })).toBeInTheDocument();
    const accountEntry = await within(actionIsland).findByTestId('shell-account-center-entry');
    expect(accountEntry).toHaveTextContent('Admin');
    expect(accountEntry).not.toHaveTextContent('Admin account');
    expect(accountEntry).not.toHaveTextContent('Bootstrap Admin...');
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
    const compactAccountEntry = await within(actionIsland).findByTestId('shell-account-center-entry');
    expect(compactAccountEntry).toBeInTheDocument();
    expect(compactAccountEntry).toHaveClass('relative');
    expect(within(actionIsland).getByRole('button', { name: '账户中心' })).toHaveClass('h-9', 'rounded-lg');
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
    const adminMenuButton = within(actionIsland).getByRole('button', { name: '系统' });
    expect(adminMenuButton).toBeInTheDocument();
    expect(within(actionIsland).queryByRole('link', { name: '证据复核' })).not.toBeInTheDocument();
    expect(within(actionIsland).queryByRole('button', { name: '控制台' })).not.toBeInTheDocument();
    fireEvent.click(adminMenuButton);
    const adminMenu = await screen.findByTestId('shell-admin-utility-menu');
    expect(adminMenu).toBeInTheDocument();
    expect(within(adminMenu).getByTestId('shell-admin-utility-group-trust')).toHaveTextContent('总览 / Trust');
    expect(within(adminMenu).getByTestId('shell-admin-utility-group-evidence')).toHaveTextContent('事件 / Evidence');
    expect(within(adminMenu).getByTestId('shell-admin-utility-group-dataOps')).toHaveTextContent('数据运行 / Data Ops');
    expect(within(adminMenu).getByTestId('shell-admin-utility-group-support')).toHaveTextContent('用户支持 / Support');
    expect(screen.getByRole('link', { name: '数据源与就绪度' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '系统日志' })).toBeInTheDocument();
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
    const adminMenu = await screen.findByTestId('shell-admin-utility-menu');
    expect(within(adminMenu).queryByTestId('shell-admin-utility-group-trust')).not.toBeInTheDocument();
    expect(within(adminMenu).queryByTestId('shell-admin-utility-group-evidence')).not.toBeInTheDocument();
    expect(within(adminMenu).getByTestId('shell-admin-utility-group-dataOps')).toHaveTextContent('数据运行 / Data Ops');
    expect(within(adminMenu).getByTestId('shell-admin-utility-group-support')).toHaveTextContent('用户支持 / Support');
    expect(await screen.findByRole('link', { name: '用户治理' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '成本观测' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '证据复核' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '系统日志' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '通知通道' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '数据源与就绪度' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '熔断诊断' })).not.toBeInTheDocument();
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
    expect(within(actionIsland).queryByRole('button', { name: translate('zh', 'nav.independentConsole') })).not.toBeInTheDocument();
    const adminNav = await screen.findByTestId('shell-admin-primary-nav');
    expect(within(adminNav).getByRole('link', { name: '证据复核' })).toBeInTheDocument();
    expect(within(adminNav).getByRole('link', { name: '系统日志' })).toHaveClass('is-active');
    expect(within(adminNav).queryByRole('link', { name: 'Evidence Review' })).not.toBeInTheDocument();
    expect(within(adminNav).queryByRole('link', { name: '用户治理' })).not.toBeInTheDocument();
    expect(within(adminNav).queryByRole('link', { name: '成本观测' })).not.toBeInTheDocument();
    expect(within(adminNav).queryByRole('link', { name: '通知通道' })).not.toBeInTheDocument();
    expect(within(adminNav).queryByRole('link', { name: '数据源与就绪度' })).not.toBeInTheDocument();
    expect(within(adminNav).queryByRole('link', { name: '熔断诊断' })).not.toBeInTheDocument();
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
    expect(within(actionIsland).queryByRole('button', { name: translate('zh', 'nav.independentConsole') })).not.toBeInTheDocument();
    const adminNav = await screen.findByTestId('shell-admin-primary-nav');
    expect(within(adminNav).getByRole('link', { name: '运维总览/系统设置' })).toBeInTheDocument();
    expect(within(adminNav).getByRole('link', { name: '数据源与就绪度' })).toHaveClass('is-active');
    expect(within(adminNav).getByRole('link', { name: '熔断诊断' })).toBeInTheDocument();
    expect(within(adminNav).getByRole('link', { name: '成本观测' })).toBeInTheDocument();
    expect(within(adminNav).getByRole('link', { name: '用户治理' })).toBeInTheDocument();
    expect(within(adminNav).getByRole('link', { name: '通知通道' })).toBeInTheDocument();
    expect(within(adminNav).queryByRole('link', { name: '证据复核' })).not.toBeInTheDocument();
    expect(within(adminNav).queryByRole('link', { name: '系统日志' })).not.toBeInTheDocument();
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
    expect(await within(actionIsland).findByTestId('shell-account-center-entry')).toBeInTheDocument();
    expect(within(actionIsland).getByRole('button', { name: '账户中心' })).toBeInTheDocument();
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
