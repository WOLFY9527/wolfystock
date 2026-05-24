/**
 * WolfyStock shell keeps routing, drawer orchestration, and rail injection
 * unchanged while the shared frame owns the Linear OS canvas and rhythm.
 */
import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, LockKeyhole, LogOut, Menu, ShieldCheck, SlidersHorizontal } from 'lucide-react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { BrandLogo, BRAND_WORDMARK_CLASSNAME } from '../common/BrandLogo';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { Drawer } from '../common/Drawer';
import { SidebarNav } from './SidebarNav';
import { ShellRailContext } from './ShellRailContext';
import { useAuth } from '../../contexts/AuthContext';
import { useI18n } from '../../contexts/UiLanguageContext';
import type { UiLanguage } from '../../i18n/core';
import { cn } from '../../utils/cn';
import { buildLocalizedPath, parseLocaleFromPathname, stripLocalePrefix } from '../../utils/localeRouting';
import { useIsDesktopViewport } from './useIsDesktopViewport';

type ShellProps = {
  children?: React.ReactNode;
};

function resolveRailTitle(t: (key: string) => string): string {
  return t('shell.archiveTitle');
}

function resolveRailDescription(t: (key: string) => string): string {
  return t('shell.archiveDesc');
}

function resolveMobileRouteLabel(pathname: string, t: (key: string) => string, language: string): string {
  if (pathname === '/' || pathname === '') {
    return t('nav.home');
  }
  if (pathname.startsWith('/settings') && !pathname.startsWith('/settings/system')) {
    return language === 'en' ? 'Account Center' : '账户中心';
  }
  if (pathname.startsWith('/settings/system')) {
    return t('nav.independentConsole');
  }
  if (pathname.startsWith('/scanner')) {
    return t('nav.scanner');
  }
  if (pathname.startsWith('/portfolio')) {
    return t('nav.portfolio');
  }
  if (pathname.startsWith('/market-overview')) {
    return t('nav.marketOverview');
  }
  if (pathname.startsWith('/market/rotation-radar')) {
    return '轮动雷达';
  }
  if (pathname.startsWith('/watchlist')) {
    return t('nav.watchlist');
  }
  if (pathname.startsWith('/backtest')) {
    return t('nav.backtest');
  }
  if (pathname.startsWith('/options-lab')) {
    return t('nav.optionsLab');
  }
  if (pathname.startsWith('/settings')) {
    return t('nav.settings');
  }
  if (pathname.startsWith('/admin/notifications')) {
    return t('nav.notifications');
  }
  if (pathname.startsWith('/admin/logs')) {
    return t('adminNav.logs');
  }
  if (pathname.startsWith('/admin/evidence-workflow')) {
    return language === 'en' ? 'Evidence Review' : '证据复核';
  }
  if (pathname.startsWith('/admin/market-providers')) {
    return t('nav.marketProviders');
  }
  if (pathname.startsWith('/admin/provider-circuits')) {
    return t('nav.providerCircuits');
  }
  if (pathname.startsWith('/admin/users')) {
    return t('nav.userGovernance');
  }
  if (pathname.startsWith('/admin/cost-observability')) {
    return t('nav.costObservability');
  }
  return t('nav.terminal');
}

const ShellRailPanel: React.FC<{
  railContent: React.ReactNode;
}> = ({ railContent }) => {
  const { t } = useI18n();

  return (
    <section className="shell-context-panel">
      <div className="shell-context-panel__header">
        <p className="shell-context-panel__eyebrow">{t('shell.archiveEyebrow')}</p>
        <h2 className="shell-context-panel__title">{resolveRailTitle(t)}</h2>
        <p className="shell-context-panel__body">{resolveRailDescription(t)}</p>
      </div>
      <div className="shell-context-panel__content">
        {railContent}
      </div>
    </section>
  );
};

type AccountMenuCopy = {
  accountCenter: string;
  security: string;
  securityResetLabel: string;
  privacy: string;
  preferences: string;
  logout: string;
  menuLabel: string;
  drawerLabel: string;
  overviewHint: string;
};

type AccountMenuItem = {
  label: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
};

function buildAccountPath(routeLocale: UiLanguage | null, target: string): string {
  return routeLocale ? buildLocalizedPath(target, routeLocale) : target;
}

export const Shell: React.FC<ShellProps> = ({ children }) => {
  const { t, language } = useI18n();
  const { loggedIn, currentUser, logout } = useAuth();
  const location = useLocation();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const surfacePathname = stripLocalePrefix(location.pathname);
  const isHomeRoute = surfacePathname === '/' || surfacePathname === '';
  const isBacktestRoute = surfacePathname.startsWith('/backtest');
  const isMarketOverviewRoute = surfacePathname.startsWith('/market-overview');
  const isLiquidityMonitorRoute = surfacePathname.startsWith('/market/liquidity-monitor');
  const isRotationRadarRoute = surfacePathname.startsWith('/market/rotation-radar');
  const isScannerRoute = surfacePathname.startsWith('/scanner');
  const isSystemControlRoute = surfacePathname.startsWith('/settings/system')
    || surfacePathname.startsWith('/admin/logs')
    || surfacePathname.startsWith('/admin/evidence-workflow')
    || surfacePathname.startsWith('/admin/notifications')
    || surfacePathname.startsWith('/admin/market-providers')
    || surfacePathname.startsWith('/admin/provider-circuits')
    || surfacePathname.startsWith('/admin/users')
    || surfacePathname.startsWith('/admin/cost-observability');
  const isPageScrollRoute = isHomeRoute;
  const shellViewportClass = isScannerRoute || isHomeRoute ? 'min-h-screen' : 'h-full min-h-0';
  const shellFrameOverflowClass = '';
  const isWideRoute = surfacePathname === '/'
    || isBacktestRoute
    || surfacePathname.startsWith('/scanner')
    || surfacePathname.startsWith('/portfolio')
    || surfacePathname.startsWith('/watchlist')
    || isMarketOverviewRoute
    || isLiquidityMonitorRoute
    || isRotationRadarRoute
    || surfacePathname.startsWith('/options-lab')
    || isSystemControlRoute;
  const isDesktop = useIsDesktopViewport();
  const previousPathnameRef = useRef(location.pathname);
  const didInitializeViewportRef = useRef(false);
  const accountMenuRef = useRef<HTMLDivElement | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [railContent, setRailContent] = useState<React.ReactNode | null>(null);
  const hasRailContent = Boolean(railContent);
  const isMobileNavVisible = mobileNavOpen;
  const isRailVisible = hasRailContent && railOpen;
  const mobileRouteLabel = resolveMobileRouteLabel(surfacePathname, t, language);
  const accountDisplayName = currentUser?.displayName || currentUser?.username || (language === 'en' ? 'Account' : '账户');
  const accountCopy: AccountMenuCopy = language === 'en'
    ? {
      accountCenter: 'Account Center',
      security: 'Account & Security',
      securityResetLabel: 'Change Password',
      privacy: 'Privacy Settings',
      preferences: 'Display Preferences',
      logout: 'Log out',
      menuLabel: 'Account center menu',
      drawerLabel: 'Account center',
      overviewHint: 'Open personal profile, security, privacy, and display preferences.',
    }
    : {
      accountCenter: '账户中心',
      security: '账户与安全',
      securityResetLabel: '修改密码',
      privacy: '隐私设置',
      preferences: '显示偏好',
      logout: '退出登录',
      menuLabel: '账户中心菜单',
      drawerLabel: '账户中心',
      overviewHint: '统一进入个人资料、安全、隐私与显示偏好。',
    };
  const accountMenuItems: AccountMenuItem[] = [
    { label: accountCopy.accountCenter, to: buildAccountPath(routeLocale, '/settings'), icon: ShieldCheck },
    { label: accountCopy.security, to: buildAccountPath(routeLocale, '/settings#security'), icon: ShieldCheck },
    { label: accountCopy.securityResetLabel, to: buildAccountPath(routeLocale, '/settings#password'), icon: LockKeyhole },
    { label: accountCopy.privacy, to: buildAccountPath(routeLocale, '/settings#privacy'), icon: LockKeyhole },
    { label: accountCopy.preferences, to: buildAccountPath(routeLocale, '/settings#preferences'), icon: SlidersHorizontal },
  ];

  const closeMobileNav = useCallback(() => {
    setMobileNavOpen(false);
  }, [setMobileNavOpen]);

  const openMobileNav = useCallback(() => {
    setRailOpen(false);
    setMobileNavOpen(true);
  }, [setMobileNavOpen, setRailOpen]);

  const closeRail = useCallback(() => {
    setRailOpen(false);
  }, [setRailOpen]);

  const closeAccountMenu = useCallback(() => {
    setAccountMenuOpen(false);
  }, [setAccountMenuOpen]);

  const openRail = useCallback(() => {
    setMobileNavOpen(false);
    setRailOpen(true);
  }, [setMobileNavOpen, setRailOpen]);

  const railContextValue = useMemo(
    () => ({
      setRailContent,
      closeMobileRail: closeRail,
      openRail,
      isConnected: true,
    }),
    [closeRail, openRail, setRailContent],
  );

  useEffect(() => {
    if (location.pathname === previousPathnameRef.current) {
      return;
    }

    previousPathnameRef.current = location.pathname;
    const timer = window.setTimeout(() => {
      setMobileNavOpen(false);
      setRailOpen(false);
      setAccountMenuOpen(false);
    }, 0);

    return () => window.clearTimeout(timer);
  }, [location.pathname]);

  useEffect(() => {
    if (!didInitializeViewportRef.current) {
      didInitializeViewportRef.current = true;
      return;
    }

    const timer = window.setTimeout(() => {
      setMobileNavOpen(false);
      setRailOpen(false);
      setAccountMenuOpen(false);
    }, 0);

    return () => window.clearTimeout(timer);
  }, [isDesktop]);

  useEffect(() => {
    if (!accountMenuOpen) {
      return undefined;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (accountMenuRef.current?.contains(event.target as Node)) {
        return;
      }
      setAccountMenuOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setAccountMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [accountMenuOpen]);

  useEffect(() => {
    const root = document.documentElement;
    const body = document.body;
    const appRoot = document.getElementById('root');

    if (isScannerRoute) {
      root.dataset.scannerShell = 'true';
      body.dataset.scannerShell = 'true';
      appRoot?.setAttribute('data-scanner-shell', 'true');
    }
    return () => {
      delete root.dataset.scannerShell;
      delete body.dataset.scannerShell;
      appRoot?.removeAttribute('data-scanner-shell');
    };
  }, [isScannerRoute]);

  useEffect(() => {
    const root = document.documentElement;
    const body = document.body;
    const appRoot = document.getElementById('root');

    if (isPageScrollRoute) {
      root.dataset.pageScrollShell = 'true';
      body.dataset.pageScrollShell = 'true';
      appRoot?.setAttribute('data-page-scroll-shell', 'true');
    }
    return () => {
      delete root.dataset.pageScrollShell;
      delete body.dataset.pageScrollShell;
      appRoot?.removeAttribute('data-page-scroll-shell');
    };
  }, [isPageScrollRoute]);

  useEffect(() => {
    const root = document.documentElement;
    const body = document.body;
    const appRoot = document.getElementById('root');

    if (isMarketOverviewRoute) {
      root.dataset.marketOverviewShell = 'true';
      body.dataset.marketOverviewShell = 'true';
      appRoot?.setAttribute('data-market-overview-shell', 'true');
    }
    return () => {
      delete root.dataset.marketOverviewShell;
      delete body.dataset.marketOverviewShell;
      appRoot?.removeAttribute('data-market-overview-shell');
    };
  }, [isMarketOverviewRoute]);

  return (
    <ShellRailContext.Provider value={railContextValue}>
      <div
        className={`theme-shell ${shellViewportClass} flex flex-col text-foreground${isPageScrollRoute ? ' theme-shell--page-scroll' : ''}${isHomeRoute ? ' theme-shell--home' : ''}${isScannerRoute ? ' theme-shell--scanner' : ''}${isWideRoute ? ' theme-shell--wide' : ''}${isMarketOverviewRoute ? ' theme-shell--market-overview' : ''}`}
        data-layout={isDesktop ? 'desktop' : 'mobile'}
      >
        <header className="shell-masthead shrink-0 w-full">
          <div className="shell-masthead__inner w-full">
            {isDesktop ? (
              <SidebarNav
                layout="header"
                onNavigate={closeRail}
                hasArchive={hasRailContent}
                onOpenArchive={openRail}
              />
            ) : (
              <div className="shell-mobile-strip">
                <NavLink to="/" end className="shell-mobile-brand shell-brand-link" aria-label="WolfyStock">
                  <span className="inline-flex min-w-0 items-center gap-3">
                    <BrandLogo className="h-8 w-8" />
                    <span className={`shell-wordmark ${BRAND_WORDMARK_CLASSNAME}`}>WolfyStock</span>
                  </span>
                </NavLink>
                <span className="shell-mobile-active-route" data-testid="shell-mobile-active-route">
                  {mobileRouteLabel}
                </span>
                <button
                  type="button"
                  onClick={openMobileNav}
                  className="shell-mobile-button"
                  aria-label={t('shell.openMenu')}
                  title={t('shell.openMenu')}
                >
                  <Menu className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>
        </header>

        <div
          className={`shell-content-frame relative flex flex-1 min-h-0 min-w-0 w-full${shellFrameOverflowClass}${isPageScrollRoute ? ' shell-content-frame--page-scroll' : ''}${isHomeRoute ? ' shell-content-frame--home' : ''}${isBacktestRoute ? ' shell-content-frame--backtest' : ''}${isScannerRoute ? ' shell-content-frame--scanner' : ''}${isWideRoute ? ' shell-content-frame--wide' : ''}${isSystemControlRoute ? ' shell-content-frame--system-control' : ''}`}
        >
          {isDesktop && loggedIn ? (
            <div className="pointer-events-none absolute right-6 top-4 z-20 hidden md:flex xl:right-12">
              <div
                ref={accountMenuRef}
                data-testid="shell-account-center-entry"
                className="pointer-events-auto relative"
              >
                <button
                  type="button"
                  className={cn(
                    'flex min-w-[12.5rem] items-center justify-between gap-3 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)]/92 px-3 py-2 text-left shadow-[0_16px_40px_rgba(0,0,0,0.28)] backdrop-blur',
                    accountMenuOpen ? 'border-[color:var(--wolfy-accent)]' : '',
                  )}
                  aria-label={accountCopy.accountCenter}
                  aria-expanded={accountMenuOpen}
                  aria-controls="shell-account-center-menu"
                  onClick={() => setAccountMenuOpen((open) => !open)}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-[10px] uppercase tracking-[0.1em] text-[color:var(--wolfy-text-muted)]">
                      {accountDisplayName}
                    </span>
                    <span className="mt-1 block text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
                      {accountCopy.accountCenter}
                    </span>
                  </span>
                  <ChevronDown className={cn('h-4 w-4 shrink-0 text-[color:var(--wolfy-text-secondary)] transition-transform', accountMenuOpen ? 'rotate-180' : '')} />
                </button>

                {accountMenuOpen ? (
                  <div
                    id="shell-account-center-menu"
                    role="menu"
                    data-testid="shell-account-center-menu"
                    className="absolute right-0 top-full mt-2 flex min-w-[15rem] max-w-[min(22rem,calc(100vw-2rem))] flex-col gap-1 rounded-2xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-2 shadow-[0_20px_48px_rgba(0,0,0,0.28)]"
                  >
                    {accountMenuItems.map(({ label, to, icon: Icon }) => (
                      <NavLink
                        key={label}
                        to={to}
                        className={({ isActive }) => cn(
                          'flex min-w-0 items-center gap-3 rounded-xl px-3 py-2 text-left text-sm text-white/72 transition-colors hover:bg-white/[0.04] hover:text-white',
                          isActive ? 'bg-white/[0.05] text-white' : '',
                        )}
                        onClick={closeAccountMenu}
                      >
                        <Icon className="h-4 w-4 shrink-0 text-white/56" />
                        <span className="truncate">{label}</span>
                      </NavLink>
                    ))}
                    <div className="my-1 h-px bg-[var(--wolfy-divider)]" />
                    <button
                      type="button"
                      className="flex min-w-0 items-center gap-3 rounded-xl px-3 py-2 text-left text-sm text-red-200/80 transition-colors hover:bg-red-500/10 hover:text-red-100"
                      onClick={() => {
                        closeAccountMenu();
                        setShowLogoutConfirm(true);
                      }}
                    >
                      <LogOut className="h-4 w-4 shrink-0 text-red-200/70" />
                      <span className="truncate">{accountCopy.logout}</span>
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}
          <main className={`theme-main-lane shell-main-column relative flex flex-1 flex-col min-h-0 min-w-0 w-full${isSystemControlRoute ? ' p-0 shell-main-column--system-control' : isHomeRoute ? ' px-4 pt-3 pb-8 md:px-6 lg:pt-4 xl:px-8 shell-main-column--home' : ' px-6 pt-6 pb-12 md:px-8 xl:px-12'}${shellFrameOverflowClass}${isPageScrollRoute ? ' shell-main-column--page-scroll' : ''}${isScannerRoute ? ' shell-main-column--scanner' : ''}`}>
            <div key={location.pathname} className={`theme-page-transition flex min-h-0 min-w-0 w-full flex-col${isScannerRoute || isHomeRoute ? '' : ' h-full'}${isPageScrollRoute ? ' theme-page-transition--page-scroll' : ''}${isSystemControlRoute ? ' theme-page-transition--system-control' : ''}`}>
              {children ?? <Outlet />}
            </div>
          </main>
        </div>

        {!isDesktop ? (
          <Drawer
            isOpen={isMobileNavVisible}
            onClose={closeMobileNav}
            title={t('shell.drawerTitle')}
            width="max-w-xs"
            zIndex={90}
            side="left"
            closeOnBackdropClick={false}
          >
            {loggedIn ? (
              <section
                data-testid="shell-mobile-account-center"
                className="mb-4 rounded-2xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)]/72 p-3"
              >
                <div className="min-w-0">
                  <p className="text-[11px] uppercase tracking-[0.08em] text-[color:var(--wolfy-text-muted)]">
                    {accountDisplayName}
                  </p>
                  <p className="mt-1 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
                    {accountCopy.drawerLabel}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                    {accountCopy.overviewHint}
                  </p>
                </div>
                <nav aria-label={accountCopy.menuLabel} className="mt-3 space-y-1">
                  {accountMenuItems.map(({ label, to, icon: Icon }) => (
                    <NavLink
                      key={label}
                      to={to}
                      onClick={closeMobileNav}
                      className={({ isActive }) => cn('shell-drawer-action', isActive ? 'is-active' : '')}
                      aria-label={label}
                    >
                      <span className="shell-nav-item__icon" aria-hidden="true">
                        <Icon className="h-4 w-4" />
                      </span>
                      <span className="shell-nav-item__copy">
                        <span className="shell-nav-item__label">{label}</span>
                      </span>
                    </NavLink>
                  ))}
                  <button
                    type="button"
                    className="shell-nav-item shell-nav-item--utility shell-nav-item--danger w-full"
                    aria-label={accountCopy.logout}
                    onClick={() => {
                      closeMobileNav();
                      setShowLogoutConfirm(true);
                    }}
                  >
                    <span className="shell-nav-item__icon" aria-hidden="true">
                      <LogOut className="h-4 w-4" />
                    </span>
                    <span className="shell-nav-item__copy">
                      <span className="shell-nav-item__label">{accountCopy.logout}</span>
                    </span>
                  </button>
                </nav>
              </section>
            ) : null}
            <SidebarNav
              layout="drawer"
              onNavigate={closeMobileNav}
              hasArchive={hasRailContent}
              onOpenArchive={openRail}
            />
          </Drawer>
        ) : null}

        {hasRailContent ? (
        <Drawer
          isOpen={isRailVisible}
          onClose={closeRail}
          title={resolveRailTitle(t)}
          width="max-w-[min(92vw,31rem)]"
          zIndex={95}
          side="right"
        >
          <ShellRailPanel railContent={railContent!} />
        </Drawer>
      ) : null}
      </div>
      <ConfirmDialog
        isOpen={showLogoutConfirm}
        title={t('nav.logoutTitle')}
        message={t('nav.logoutMessage')}
        confirmText={t('nav.logoutConfirm')}
        cancelText={t('nav.logoutCancel')}
        isDanger
        onConfirm={() => {
          setShowLogoutConfirm(false);
          void (async () => {
            try {
              await logout();
            } catch {
              return;
            }
          })();
        }}
        onCancel={() => setShowLogoutConfirm(false)}
      />
    </ShellRailContext.Provider>
  );
};
