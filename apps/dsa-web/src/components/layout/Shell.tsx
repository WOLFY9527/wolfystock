/**
 * WolfyStock shell phase 1 keeps routing, drawer orchestration, and rail
 * injection unchanged while moving the shared workspace frame to edge-to-edge
 * layout tokens and calmer glass navigation controls.
 */
import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Menu } from 'lucide-react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { BrandLogo, BRAND_WORDMARK_CLASSNAME } from '../common/BrandLogo';
import { Drawer } from '../common/Drawer';
import { SidebarNav } from './SidebarNav';
import { ShellRailContext } from './ShellRailContext';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useIsDesktopViewport } from './useIsDesktopViewport';
import { stripLocalePrefix } from '../../utils/localeRouting';

type ShellProps = {
  children?: React.ReactNode;
};

function resolveRailTitle(pathname: string, t: (key: string) => string): string {
  if (pathname.startsWith('/chat')) {
    return t('shell.chatArchiveTitle');
  }
  return t('shell.archiveTitle');
}

function resolveRailDescription(pathname: string, t: (key: string) => string): string {
  if (pathname.startsWith('/chat')) {
    return t('shell.chatArchiveDesc');
  }
  return t('shell.archiveDesc');
}

function resolveMobileRouteLabel(pathname: string, t: (key: string) => string): string {
  if (pathname === '/' || pathname === '') {
    return t('nav.home');
  }
  if (pathname.startsWith('/scanner')) {
    return t('nav.scanner');
  }
  if (pathname.startsWith('/chat')) {
    return t('nav.chat');
  }
  if (pathname.startsWith('/portfolio')) {
    return t('nav.portfolio');
  }
  if (pathname.startsWith('/market-overview')) {
    return t('nav.marketOverview');
  }
  if (pathname.startsWith('/watchlist')) {
    return t('nav.watchlist');
  }
  if (pathname.startsWith('/backtest')) {
    return t('nav.backtest');
  }
  if (pathname.startsWith('/settings')) {
    return t('nav.settings');
  }
  if (pathname.startsWith('/admin/notifications')) {
    return t('nav.notifications');
  }
  if (pathname.startsWith('/admin/market-providers')) {
    return t('nav.marketProviders');
  }
  if (pathname.startsWith('/admin/users')) {
    return t('nav.userGovernance');
  }
  return t('nav.terminal');
}

const ShellRailPanel: React.FC<{
  pathname: string;
  railContent: React.ReactNode;
}> = ({ pathname, railContent }) => {
  const { t } = useI18n();

  return (
    <section className="shell-context-panel">
      <div className="shell-context-panel__header">
        <p className="shell-context-panel__eyebrow">{t('shell.archiveEyebrow')}</p>
        <h2 className="shell-context-panel__title">{resolveRailTitle(pathname, t)}</h2>
        <p className="shell-context-panel__body">{resolveRailDescription(pathname, t)}</p>
      </div>
      <div className="shell-context-panel__content">
        {railContent}
      </div>
    </section>
  );
};

export const Shell: React.FC<ShellProps> = ({ children }) => {
  const { t } = useI18n();
  const location = useLocation();
  const surfacePathname = stripLocalePrefix(location.pathname);
  const isBacktestRoute = surfacePathname.startsWith('/backtest');
  const isChatRoute = surfacePathname.startsWith('/chat');
  const isMarketOverviewRoute = surfacePathname.startsWith('/market-overview');
  const isScannerRoute = surfacePathname.startsWith('/scanner');
  const isSystemControlRoute = surfacePathname.startsWith('/settings/system')
    || surfacePathname.startsWith('/admin/notifications')
    || surfacePathname.startsWith('/admin/market-providers')
    || surfacePathname.startsWith('/admin/users');
  const shellViewportClass = isScannerRoute ? 'min-h-screen' : 'h-full min-h-0';
  const shellFrameOverflowClass = '';
  const isWideRoute = surfacePathname === '/'
    || surfacePathname.startsWith('/scanner')
    || isChatRoute
    || surfacePathname.startsWith('/portfolio')
    || isMarketOverviewRoute
    || isSystemControlRoute;
  const isDesktop = useIsDesktopViewport();
  const previousPathnameRef = useRef(location.pathname);
  const didInitializeViewportRef = useRef(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const [railContent, setRailContent] = useState<React.ReactNode | null>(null);
  const hasRailContent = Boolean(railContent);
  const isMobileNavVisible = mobileNavOpen;
  const isRailVisible = hasRailContent && railOpen;
  const mobileRouteLabel = resolveMobileRouteLabel(surfacePathname, t);

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
    }, 0);

    return () => window.clearTimeout(timer);
  }, [isDesktop]);

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
        className={`theme-shell ${shellViewportClass} flex flex-col text-foreground${isScannerRoute ? ' theme-shell--scanner' : ''}${isWideRoute ? ' theme-shell--wide' : ''}${isMarketOverviewRoute ? ' theme-shell--market-overview' : ''}`}
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
          className={`shell-content-frame flex flex-1 min-h-0 min-w-0 w-full${shellFrameOverflowClass}${isBacktestRoute ? ' shell-content-frame--backtest' : ''}${isChatRoute ? ' shell-content-frame--chat' : ''}${isScannerRoute ? ' shell-content-frame--scanner' : ''}${isWideRoute ? ' shell-content-frame--wide' : ''}${isSystemControlRoute ? ' shell-content-frame--system-control' : ''}`}
        >
          <main className={`theme-main-lane shell-main-column relative flex flex-1 flex-col min-h-0 min-w-0 w-full${isChatRoute ? ' p-0 shell-main-column--chat' : isSystemControlRoute ? ' p-0 shell-main-column--system-control' : ' px-6 pt-6 pb-12 md:px-8 xl:px-12'}${shellFrameOverflowClass}${isScannerRoute ? ' shell-main-column--scanner' : ''}`}>
            <div key={location.pathname} className={`theme-page-transition flex min-h-0 min-w-0 w-full flex-col${isScannerRoute ? '' : ' h-full'}${isChatRoute ? ' theme-page-transition--chat' : ''}${isSystemControlRoute ? ' theme-page-transition--system-control' : ''}`}>
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
            title={resolveRailTitle(location.pathname, t)}
            width="max-w-[min(92vw,31rem)]"
            zIndex={95}
            side="right"
          >
            <ShellRailPanel pathname={location.pathname} railContent={railContent!} />
          </Drawer>
        ) : null}
      </div>
    </ShellRailContext.Provider>
  );
};
