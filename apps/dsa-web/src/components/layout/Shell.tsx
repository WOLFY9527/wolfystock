/**
 * WolfyStock shell keeps routing, drawer orchestration, and rail injection
 * unchanged while the shared frame owns the Linear OS canvas and rhythm.
 */
import type React from 'react';
import { useEffect, useEffectEvent, useReducer, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
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
    return t('nav.rotationRadar');
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

function sanitizeAccountDisplayName(
  rawDisplayName: string | null | undefined,
  options: { isAdmin: boolean; language: UiLanguage },
): string {
  const trimmed = rawDisplayName?.trim();
  if (!trimmed) {
    return options.isAdmin
      ? (options.language === 'en' ? 'Admin account' : '管理员账户')
      : (options.language === 'en' ? 'Account' : '账户');
  }

  if (options.isAdmin && /bootstrap\s*admin/i.test(trimmed)) {
    return options.language === 'en' ? 'Admin account' : '管理员账户';
  }

  return trimmed;
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

type OverlayState = {
  mobileNavOpen: boolean;
  railOpen: boolean;
  accountMenuOpen: boolean;
};

type OverlayAction =
  | { type: 'close_all' }
  | { type: 'open_mobile_nav' }
  | { type: 'close_mobile_nav' }
  | { type: 'open_rail' }
  | { type: 'close_rail' }
  | { type: 'open_account_menu' }
  | { type: 'close_account_menu' };

function overlayReducer(state: OverlayState, action: OverlayAction): OverlayState {
  switch (action.type) {
    case 'close_all':
      return state.mobileNavOpen || state.railOpen || state.accountMenuOpen
        ? { mobileNavOpen: false, railOpen: false, accountMenuOpen: false }
        : state;
    case 'open_mobile_nav':
      return { mobileNavOpen: true, railOpen: false, accountMenuOpen: false };
    case 'close_mobile_nav':
      return state.mobileNavOpen ? { ...state, mobileNavOpen: false } : state;
    case 'open_rail':
      return { mobileNavOpen: false, railOpen: true, accountMenuOpen: false };
    case 'close_rail':
      return state.railOpen ? { ...state, railOpen: false } : state;
    case 'open_account_menu':
      return state.accountMenuOpen ? state : { ...state, accountMenuOpen: true };
    case 'close_account_menu':
      return state.accountMenuOpen ? { ...state, accountMenuOpen: false } : state;
    default:
      return state;
  }
}

function buildAccountPath(routeLocale: UiLanguage | null, target: string): string {
  return routeLocale ? buildLocalizedPath(target, routeLocale) : target;
}

export const Shell: React.FC<ShellProps> = ({ children }) => {
  const { t, language } = useI18n();
  const { loggedIn, currentUser, logout } = useAuth();
  const { pathname } = useLocation();
  const routeLocale = parseLocaleFromPathname(pathname);
  const surfacePathname = stripLocalePrefix(pathname);
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
  const previousPathnameRef = useRef(pathname);
  const didInitializeViewportRef = useRef(false);
  const accountTriggerRef = useRef<HTMLButtonElement | null>(null);
  const accountMenuRef = useRef<HTMLDivElement | null>(null);
  const accountMenuItemRefs = useRef<Array<HTMLAnchorElement | HTMLButtonElement | null>>([]);
  const accountMenuFocusIndexRef = useRef<number | null>(null);
  const [overlayState, dispatchOverlay] = useReducer(overlayReducer, {
    mobileNavOpen: false,
    railOpen: false,
    accountMenuOpen: false,
  });
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [railContent, setRailContent] = useState<React.ReactNode | null>(null);
  const [headerUtilityIsland, setHeaderUtilityIsland] = useState<HTMLDivElement | null>(null);
  const { mobileNavOpen, railOpen, accountMenuOpen } = overlayState;
  const hasRailContent = Boolean(railContent);
  const isMobileNavVisible = mobileNavOpen;
  const isRailVisible = hasRailContent && railOpen;
  const mobileRouteLabel = resolveMobileRouteLabel(surfacePathname, t, language);
  const accountDisplayName = sanitizeAccountDisplayName(
    currentUser?.displayName || currentUser?.username,
    {
      isAdmin: Boolean(currentUser?.isAdmin),
      language,
    },
  );
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

  const closeMobileNav = () => {
    dispatchOverlay({ type: 'close_mobile_nav' });
  };

  const openMobileNav = () => {
    dispatchOverlay({ type: 'open_mobile_nav' });
  };

  const closeRail = () => {
    dispatchOverlay({ type: 'close_rail' });
  };

  const closeAccountMenu = (options?: { returnFocus?: boolean }) => {
    accountMenuFocusIndexRef.current = null;
    dispatchOverlay({ type: 'close_account_menu' });
    if (options?.returnFocus) {
      window.setTimeout(() => {
        accountTriggerRef.current?.focus();
      }, 0);
    }
  };

  const openAccountMenu = (focusIndex = 0) => {
    accountMenuFocusIndexRef.current = focusIndex;
    dispatchOverlay({ type: 'open_account_menu' });
  };

  const openRail = () => {
    dispatchOverlay({ type: 'open_rail' });
  };

  const closeAccountMenuForEffect = useEffectEvent((options?: { returnFocus?: boolean }) => {
    closeAccountMenu(options);
  });

  const shellMastheadInnerRef = (node: HTMLDivElement | null) => {
    setHeaderUtilityIsland(node?.querySelector<HTMLDivElement>('[data-testid="shell-header-utility-island"]') ?? null);
  };

  const railContextValue = {
    setRailContent,
    closeMobileRail: closeRail,
    openRail,
    isConnected: true,
  };

  useEffect(() => {
    if (pathname === previousPathnameRef.current) {
      return;
    }

    previousPathnameRef.current = pathname;
    const timer = window.setTimeout(() => {
      accountMenuFocusIndexRef.current = null;
      dispatchOverlay({ type: 'close_all' });
    }, 0);

    return () => window.clearTimeout(timer);
  }, [pathname]);

  useEffect(() => {
    if (!didInitializeViewportRef.current) {
      didInitializeViewportRef.current = true;
      return;
    }

    const timer = window.setTimeout(() => {
      accountMenuFocusIndexRef.current = null;
      dispatchOverlay({ type: 'close_all' });
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
      closeAccountMenuForEffect({ returnFocus: true });
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeAccountMenuForEffect({ returnFocus: true });
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
    if (!accountMenuOpen || accountMenuFocusIndexRef.current === null) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      const focusIndex = accountMenuFocusIndexRef.current;
      if (focusIndex === null) {
        return;
      }
      accountMenuItemRefs.current[focusIndex]?.focus();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [accountMenuOpen]);

  const handleAccountTriggerKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'Enter' || event.key === ' ' || event.key === 'ArrowDown') {
      event.preventDefault();
      openAccountMenu(0);
    }
  };

  const handleAccountMenuKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const items = accountMenuItemRefs.current.filter(Boolean) as Array<HTMLAnchorElement | HTMLButtonElement>;
    if (!items.length) {
      return;
    }

    const activeIndex = items.findIndex((item) => item === document.activeElement);
    const resolvedIndex = activeIndex >= 0 ? activeIndex : 0;

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      items[(resolvedIndex + 1) % items.length]?.focus();
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      items[(resolvedIndex - 1 + items.length) % items.length]?.focus();
      return;
    }
    if (event.key === 'Home') {
      event.preventDefault();
      items[0]?.focus();
      return;
    }
    if (event.key === 'End') {
      event.preventDefault();
      items[items.length - 1]?.focus();
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      closeAccountMenu({ returnFocus: true });
    }
  };

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
          <div ref={shellMastheadInnerRef} className="shell-masthead__inner w-full">
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
                    <BrandLogo className="size-8" />
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
                  <Menu className="size-4" />
                </button>
              </div>
            )}
          </div>
        </header>

        <div
          className={`shell-content-frame relative flex flex-1 min-h-0 min-w-0 w-full${shellFrameOverflowClass}${isPageScrollRoute ? ' shell-content-frame--page-scroll' : ''}${isHomeRoute ? ' shell-content-frame--home' : ''}${isBacktestRoute ? ' shell-content-frame--backtest' : ''}${isScannerRoute ? ' shell-content-frame--scanner' : ''}${isWideRoute ? ' shell-content-frame--wide' : ''}${isSystemControlRoute ? ' shell-content-frame--system-control' : ''}`}
        >
          <main className={`theme-main-lane shell-main-column relative flex flex-1 flex-col min-h-0 min-w-0 w-full${isSystemControlRoute ? ' p-0 shell-main-column--system-control' : isHomeRoute ? ' px-4 pt-3 pb-8 md:px-6 lg:pt-4 xl:px-8 shell-main-column--home' : ' px-6 pt-6 pb-12 md:px-8 xl:px-12'}${shellFrameOverflowClass}${isPageScrollRoute ? ' shell-main-column--page-scroll' : ''}${isScannerRoute ? ' shell-main-column--scanner' : ''}`}>
            <div key={pathname} className={`theme-page-transition flex min-h-0 min-w-0 w-full flex-col${isScannerRoute || isHomeRoute ? '' : ' h-full'}${isPageScrollRoute ? ' theme-page-transition--page-scroll' : ''}${isSystemControlRoute ? ' theme-page-transition--system-control' : ''}`}>
              {children ?? <Outlet />}
            </div>
          </main>
        </div>
        {isDesktop && loggedIn && headerUtilityIsland ? createPortal(
          <div
            ref={accountMenuRef}
            data-testid="shell-account-center-entry"
            className="relative"
          >
            <button
              ref={accountTriggerRef}
              type="button"
              className={cn(
                'flex h-9 min-w-0 max-w-[11rem] items-center gap-2 rounded-lg border border-transparent bg-white/[0.03] px-2.5 text-left text-[11px] font-medium text-white/70 transition-colors hover:bg-white/[0.05] hover:text-white',
                accountMenuOpen ? 'border-[color:var(--wolfy-accent)] bg-white/[0.06] text-white shadow-[0_0_0_1px_rgba(118,109,219,0.14)]' : '',
              )}
              aria-label={accountCopy.accountCenter}
              aria-haspopup="menu"
              aria-expanded={accountMenuOpen}
              aria-controls="shell-account-center-menu"
              onClick={() => {
                if (accountMenuOpen) {
                  closeAccountMenu({ returnFocus: true });
                  return;
                }
                openAccountMenu(0);
              }}
              onKeyDown={handleAccountTriggerKeyDown}
            >
              <span
                className="flex size-5 shrink-0 items-center justify-center rounded-full border border-white/[0.08] bg-white/[0.06] text-[10px] font-semibold text-white/82"
                aria-hidden="true"
              >
                {accountDisplayName.slice(0, 1)}
              </span>
              <span className="min-w-0 truncate">{accountDisplayName}</span>
              <ChevronDown className={cn('size-3.5 shrink-0 text-white/44 transition-transform', accountMenuOpen ? 'rotate-180 text-white/70' : '')} />
            </button>

            {accountMenuOpen ? (
              <div
                id="shell-account-center-menu"
                role="menu"
                tabIndex={-1}
                aria-label={accountCopy.menuLabel}
                aria-orientation="vertical"
                data-testid="shell-account-center-menu"
                className="absolute right-0 top-full z-20 mt-2 flex min-w-[15rem] max-w-[min(22rem,calc(100vw-2rem))] flex-col gap-1 rounded-2xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-2 shadow-[0_20px_48px_rgba(0,0,0,0.28)]"
                onKeyDown={handleAccountMenuKeyDown}
              >
                {accountMenuItems.map(({ label, to, icon: Icon }, index) => (
                  <NavLink
                    key={label}
                    to={to}
                    ref={(node) => {
                      accountMenuItemRefs.current[index] = node;
                    }}
                    role="menuitem"
                    tabIndex={-1}
                    className={({ isActive }) => cn(
                      'flex min-w-0 items-center gap-3 rounded-xl px-3 py-2 text-left text-sm text-white/72 transition-colors hover:bg-white/[0.04] hover:text-white',
                      isActive ? 'bg-white/[0.05] text-white' : '',
                    )}
                    onClick={() => closeAccountMenu()}
                  >
                    <Icon className="size-4 shrink-0 text-white/56" />
                    <span className="truncate">{label}</span>
                  </NavLink>
                ))}
                <div className="my-1 h-px bg-[var(--wolfy-divider)]" />
                <button
                  type="button"
                  ref={(node) => {
                    accountMenuItemRefs.current[accountMenuItems.length] = node;
                  }}
                  role="menuitem"
                  tabIndex={-1}
                  className="flex min-w-0 items-center gap-3 rounded-xl px-3 py-2 text-left text-sm text-red-200/80 transition-colors hover:bg-red-500/10 hover:text-red-100"
                  onClick={() => {
                    closeAccountMenu();
                    setShowLogoutConfirm(true);
                  }}
                >
                  <LogOut className="size-4 shrink-0 text-red-200/70" />
                  <span className="truncate">{accountCopy.logout}</span>
                </button>
              </div>
            ) : null}
          </div>,
          headerUtilityIsland,
        ) : null}

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
                        <Icon className="size-4" />
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
                      <LogOut className="size-4" />
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
