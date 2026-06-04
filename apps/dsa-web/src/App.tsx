import type React from 'react';
import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { ApiErrorAlert } from './components/common/ApiErrorAlert';
import { BrandedLoadingScreen } from './components/common/BrandedLoadingScreen';
import { ConsumerProtectedFrame } from './components/layout/ConsumerWorkspaceShell';
import { Shell } from './components/layout/Shell';
import { PreviewShell } from './components/layout/PreviewShell';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { useI18n } from './contexts/UiLanguageContext';
import {
  buildRegistrationPath,
  useProductSurface,
} from './hooks/useProductSurface';
import type { UiLanguage } from './i18n/core';
import { buildLocalizedPath, parseLocaleFromPathname, stripLocalePrefix } from './utils/localeRouting';
import { isPreviewRoutePath } from './utils/appRouteGuards';
import { canAccessAdminPath } from './utils/adminCapabilities';

const APP_BOOT_SPLASH_MIN_MS = 950;
const APP_BOOT_SPLASH_FADE_MS = 380;

const AccessGatePage = lazy(() => import('./components/access/AccessGatePage').then((module) => ({
  default: module.AccessGatePage,
})));
const HomeSurfacePage = lazy(() => import('./pages/HomeSurfacePage'));
const GuestHomePage = lazy(() => import('./pages/GuestHomePage'));
const ScannerSurfacePage = lazy(() => import('./pages/ScannerSurfacePage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const PreviewReportPage = lazy(() => import('./pages/PreviewReportPage'));
const PreviewFullReportDrawerPage = lazy(() => import('./pages/PreviewFullReportDrawerPage'));
const PortfolioPage = lazy(() => import('./pages/PortfolioPage'));
const MarketOverviewPage = lazy(() => import('./pages/MarketOverviewPage'));
const LiquidityMonitorPage = lazy(() => import('./pages/LiquidityMonitorPage'));
const MarketRotationRadarPage = lazy(() => import('./pages/MarketRotationRadarPage'));
const WatchlistPage = lazy(() => import('./pages/WatchlistPage'));
const BacktestPage = lazy(() => import('./pages/BacktestPage'));
const OptionsLabPage = lazy(() => import('./pages/OptionsLabPage'));
const RuleBacktestComparePage = lazy(() => import('./pages/RuleBacktestComparePage'));
const DeterministicBacktestResultPage = lazy(() => import('./pages/DeterministicBacktestResultPage'));
const PersonalSettingsPage = lazy(() => import('./pages/PersonalSettingsPage'));
const SystemSettingsPage = lazy(() => import('./pages/SystemSettingsPage'));
const AdminLogsPage = lazy(() => import('./pages/AdminLogsPage'));
const AdminNotificationsPage = lazy(() => import('./pages/AdminNotificationsPage'));
const MarketProviderOperationsPage = lazy(() => import('./pages/MarketProviderOperationsPage'));
const AdminProviderCircuitDiagnosticsPage = lazy(() => import('./pages/AdminProviderCircuitDiagnosticsPage'));
const AdminUsersPage = lazy(() => import('./pages/AdminUsersPage'));
const AdminCostObservabilityPage = lazy(() => import('./pages/AdminCostObservabilityPage'));
const AdminEvidenceWorkflowPage = lazy(() => import('./pages/AdminEvidenceWorkflowPage'));

type GateCopy = {
  eyebrow: string;
  title: string;
  description: string;
  bullets: string[];
  statusLabel?: string;
  note?: string;
  secondaryAction?: { label: string; to: string };
  tertiaryAction?: { label: string; to: string };
};

function getAdminSurfaceCopy(pathname: string, language: UiLanguage, isGuest: boolean): GateCopy {
  const isEnglish = language === 'en';

  if (pathname.startsWith('/admin/logs') || pathname.startsWith('/admin/evidence-workflow') || pathname.startsWith('/admin/notifications') || pathname.startsWith('/admin/market-providers') || pathname.startsWith('/admin/provider-circuits') || pathname.startsWith('/admin/users') || pathname.startsWith('/admin/cost-observability')) {
    const surfaceName = pathname.startsWith('/admin/cost-observability')
      ? (isEnglish ? 'cost observability' : '成本观测')
      : pathname.startsWith('/admin/evidence-workflow')
      ? (isEnglish ? 'evidence workflow' : '证据工作流')
      : pathname.startsWith('/admin/provider-circuits')
      ? (isEnglish ? 'provider circuit diagnostics' : 'Provider 熔断诊断')
      : pathname.startsWith('/admin/market-providers')
      ? (isEnglish ? 'market provider operations' : '市场数据源运维')
      : pathname.startsWith('/admin/notifications')
      ? (isEnglish ? 'notification channels' : '通知通道')
      : pathname.startsWith('/admin/users')
      ? (isEnglish ? 'user governance' : '用户治理')
      : (isEnglish ? 'logs' : '日志');
    return isGuest
      ? {
        eyebrow: isEnglish ? 'Admin Only' : '仅限管理员',
        statusLabel: isEnglish ? 'Admin Sign-in Required' : '需要管理员登录',
        title: isEnglish ? `Sign in with an admin account to open ${surfaceName}` : `请使用管理员账户登录后查看${surfaceName}`,
        description: isEnglish
          ? 'Operational admin surfaces are reserved for admins and are not available in guest or regular user pages.'
          : '运维管理页面只对管理员开放，不属于游客或普通用户页面的一部分。',
        bullets: isEnglish
          ? [
            'Guest access never maps to setup or admin identities.',
            'System logs stay protected even when the route is known.',
            'Use an admin account if you need logs, schedules, or system controls.',
          ]
          : [
            '游客模式绝不会映射到初始设置账户或管理员身份。',
            '即使知道路由地址，系统日志仍然会被保护。',
            '如果你需要日志、调度或系统控制，请使用管理员账户。',
          ],
        secondaryAction: {
          label: isEnglish ? 'Back home' : '返回首页',
          to: '/',
        },
      }
      : {
        eyebrow: isEnglish ? 'Admin Only' : '仅限管理员',
        statusLabel: isEnglish ? 'Admin Account Required' : '需要管理员账户',
        title: isEnglish ? `This ${surfaceName} route requires an admin account` : `这个${surfaceName}页面需要管理员账户`,
        description: isEnglish
          ? 'Your current account can keep using the regular app, but the logs page stays reserved for admins.'
          : '你当前账户仍可继续使用普通页面，但日志页只对管理员开放。',
        bullets: isEnglish
          ? [
            'Regular users no longer see raw system logs in the default navigation.',
            'If you expected access, sign out and re-enter with an admin account.',
            'Personal preferences remain available in personal settings.',
          ]
        : [
            '普通用户不会再在默认导航里看到原始系统日志界面。',
            '如果你本应拥有权限，请先退出当前账户，再使用管理员账户重新进入。',
            '你的个人偏好仍然可以在个人设置页面继续使用。',
          ],
        note: isEnglish
          ? 'Need the regular app instead? Personal settings remain the right next stop.'
          : '如果你要继续使用普通页面，个人设置仍然是更合适的下一站。',
        secondaryAction: {
          label: isEnglish ? 'Back home' : '返回首页',
          to: '/',
        },
      };
  }

  return isGuest
    ? {
      eyebrow: isEnglish ? 'Admin Only' : '仅限管理员',
      statusLabel: isEnglish ? 'Admin Sign-in Required' : '需要管理员登录',
      title: isEnglish ? 'Sign in with an admin account to open admin settings' : '请使用管理员账户登录后打开管理设置',
      description: isEnglish
        ? 'System settings, data-source controls, schedules, channels, and admin logs are reserved for admin accounts.'
        : '系统设置、数据源控制、调度、通道和管理员日志只对管理员账户开放。',
      bullets: isEnglish
        ? [
          'Guest mode never maps to admin or initial-setup identities.',
          'Admin tools stay behind explicit admin-only entry points.',
          'Use an admin account if you need system settings rather than personal preferences.',
        ]
        : [
          '游客模式绝不会映射到管理员或初始设置身份。',
          '管理员工具仍然保留在显式的管理员入口之后。',
          '如果你需要系统设置而不是个人偏好，请使用管理员账户登录。',
        ],
      secondaryAction: {
        label: isEnglish ? 'Back home' : '返回首页',
        to: '/',
      },
    }
    : {
      eyebrow: isEnglish ? 'Admin Only' : '仅限管理员',
      statusLabel: isEnglish ? 'Admin Account Required' : '需要管理员账户',
      title: isEnglish ? 'This page requires an admin account' : '这个页面需要管理员账户',
      description: isEnglish
        ? 'System configuration, provider controls, schedules, channels, and admin logs stay outside the regular app.'
        : '系统配置、数据源控制、调度、通道和管理员日志仍然留在普通用户页面之外。',
      bullets: isEnglish
        ? [
          'Regular users no longer see raw system controls in the default navigation.',
          'If you expected access, sign out and re-enter with an admin account.',
          'Personal preferences remain available in personal settings.',
        ]
        : [
          '普通用户不会再在默认导航里看到原始系统控制项。',
          '如果你本应拥有权限，请先退出当前账户，再使用管理员账户重新进入。',
          '个人偏好仍然保留在标准设置页面。',
        ],
      note: isEnglish
        ? 'Need regular tools instead? Open personal settings or return home.'
        : '如果你要继续普通工具，请打开个人设置或返回首页。',
      secondaryAction: {
        label: isEnglish ? 'Back home' : '返回首页',
        to: '/',
      },
    };
}

const RegisteredSurfaceRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const { language } = useI18n();
  const { isGuest } = useProductSurface();
  const routePathname = stripLocalePrefix(location.pathname);
  let moduleName = language === 'en' ? 'Premium module' : '高级模块';

  if (routePathname.startsWith('/portfolio')) {
    moduleName = language === 'en' ? 'Portfolio' : '持仓管理';
  } else if (routePathname.startsWith('/market-overview')) {
    moduleName = language === 'en' ? 'Market Overview' : '市场总览';
  } else if (routePathname.startsWith('/watchlist')) {
    moduleName = language === 'en' ? 'Watchlist' : '观察列表';
  } else if (routePathname.startsWith('/backtest')) {
    moduleName = language === 'en' ? 'Backtest' : '回测';
  } else if (routePathname.startsWith('/options-lab')) {
    moduleName = language === 'en' ? 'Options Lab' : '期权实验室';
  }

  if (!isGuest) {
    return <>{children}</>;
  }

  return <ConsumerProtectedFrame moduleName={moduleName} />;
};

const AdminSurfaceRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const { language } = useI18n();
  const { adminCapabilities, isAdminAccount, isGuest } = useProductSurface();
  const routePathname = stripLocalePrefix(location.pathname);
  const baseGateCopy = getAdminSurfaceCopy(routePathname, language, isGuest);
  const gateCopy = isAdminAccount
    ? {
      ...baseGateCopy,
      statusLabel: language === 'en' ? 'Capability Required' : '需要管理员能力',
      title: language === 'en' ? 'This admin surface requires an additional capability' : '这个管理页面需要对应管理员能力',
      description: language === 'en'
        ? 'Your account is signed in as admin, but this frontend surface is hidden unless the current-user capability summary grants the matching read or write capability.'
        : '当前账号已是管理员，但该前端页面只在 current-user 能力摘要授予对应读写能力时开放。',
    }
    : baseGateCopy;

  if (canAccessAdminPath(routePathname, adminCapabilities)) {
    return <>{children}</>;
  }

  return (
    <AccessGatePage
      eyebrow={gateCopy.eyebrow}
      title={gateCopy.title}
      description={gateCopy.description}
      bullets={gateCopy.bullets}
      statusLabel={gateCopy.statusLabel}
      note={gateCopy.note}
      primaryAction={{
        label: isGuest ? (language === 'en' ? 'Sign in' : '登录') : (language === 'en' ? 'Open personal settings' : '打开个人设置'),
        to: isGuest ? '/login' : '/settings',
      }}
      secondaryAction={gateCopy.secondaryAction}
    />
  );
};

export const AppContent: React.FC = () => {
  const location = useLocation();
  const { authEnabled, loggedIn, isLoading, loadError, refreshStatus, setupState } = useAuth();
  const { isGuest } = useProductSurface();
  const { setLanguage, t } = useI18n();
  const bootStartedAt = useRef<number>(0);
  const [showBootSplash, setShowBootSplash] = useState(true);
  const [bootSplashFading, setBootSplashFading] = useState(false);
  const splashDismissed = useRef(false);
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const routePathname = stripLocalePrefix(location.pathname);
  const localizedHomePath = routeLocale ? buildLocalizedPath('/', routeLocale) : '/';
  const localizedGuestPath = routeLocale ? buildLocalizedPath('/guest', routeLocale) : '/guest';
  const guestHomeElement = loggedIn ? <Navigate to={localizedHomePath} replace /> : <GuestHomePage />;
  const isGuestRestrictedPath = (
    routePathname === '/settings'
    || routePathname.startsWith('/settings/')
    || routePathname === '/admin/logs'
    || routePathname.startsWith('/admin/logs/')
    || routePathname === '/admin/evidence-workflow'
    || routePathname.startsWith('/admin/evidence-workflow/')
    || routePathname === '/admin/notifications'
    || routePathname.startsWith('/admin/notifications/')
    || routePathname === '/admin/market-providers'
    || routePathname.startsWith('/admin/market-providers/')
    || routePathname === '/admin/provider-circuits'
    || routePathname.startsWith('/admin/provider-circuits/')
    || routePathname === '/admin/users'
    || routePathname.startsWith('/admin/users/')
    || routePathname === '/admin/cost-observability'
    || routePathname.startsWith('/admin/cost-observability/')
  );

  useEffect(() => {
    if (routeLocale) {
      setLanguage(routeLocale);
    }
  }, [routeLocale, setLanguage]);

  useEffect(() => {
    if (bootStartedAt.current === 0) {
      bootStartedAt.current = Date.now();
    }
  }, []);

  useEffect(() => {
    if (isLoading || splashDismissed.current) {
      return;
    }

    if (bootStartedAt.current === 0) {
      bootStartedAt.current = Date.now();
    }
    const elapsed = Date.now() - bootStartedAt.current;
    const waitMs = Math.max(0, APP_BOOT_SPLASH_MIN_MS - elapsed);
    let hideTimer: number | undefined;
    const fadeTimer = window.setTimeout(() => {
      splashDismissed.current = true;
      setBootSplashFading(true);
      hideTimer = window.setTimeout(() => {
        setShowBootSplash(false);
      }, APP_BOOT_SPLASH_FADE_MS);
    }, waitMs);

    return () => {
      window.clearTimeout(fadeTimer);
      if (hideTimer !== undefined) {
        window.clearTimeout(hideTimer);
      }
    };
  }, [isLoading]);

  let content: React.ReactNode = null;

  if (loadError) {
    content = (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-base px-4">
        <div className="theme-panel-glass w-full max-w-xl p-5">
          <ApiErrorAlert error={loadError} />
          <div className="mt-4 flex justify-end">
            <button
              type="button"
              className="btn-primary"
              onClick={() => void refreshStatus()}
            >
              {t('app.retry')}
            </button>
          </div>
        </div>
      </div>
    );
  } else if (!isLoading) {
    if (routePathname === '/login') {
      const canRenderLogin = authEnabled || setupState === 'no_password' || setupState === 'password_retained';
      if (loggedIn) {
        content = <Navigate to={localizedHomePath} replace />;
      } else if (!canRenderLogin) {
        content = <Navigate to={localizedHomePath} replace />;
      } else {
        content = (
          <Suspense fallback={<BrandedLoadingScreen text={t('app.loadingBrand')} subtext={t('app.loading')} />}>
            <LoginPage />
          </Suspense>
        );
      }
    } else if (routePathname === '/reset-password') {
      if (!authEnabled || loggedIn) {
        content = <Navigate to={localizedHomePath} replace />;
      } else {
        content = (
          <Suspense fallback={<BrandedLoadingScreen text={t('app.loadingBrand')} subtext={t('app.loading')} />}>
            <ResetPasswordPage />
          </Suspense>
        );
      }
    } else if (isGuest && isGuestRestrictedPath) {
      content = <Navigate to={localizedGuestPath} replace />;
    } else {
      content = (
        <Suspense fallback={<BrandedLoadingScreen text={t('app.loadingBrand')} subtext={t('app.loading')} />}>
          <Routes>
            <Route path="/guest/scanner" element={<Navigate to="/scanner" replace />} />
            <Route path="/user/scanner" element={<Navigate to="/scanner" replace />} />
            <Route path="/:locale/guest/scanner" element={<Navigate to="../scanner" replace />} />
            <Route path="/:locale/user/scanner" element={<Navigate to="../scanner" replace />} />
            <Route element={<Shell />}>
              <Route path="/market" element={<Navigate to="/market-overview" replace />} />
              <Route path="/admin" element={<Navigate to="/settings/system" replace />} />
              <Route path="/" element={<HomeSurfacePage />} />
              <Route path="/guest" element={guestHomeElement} />
              <Route path="/scanner" element={<ScannerSurfacePage />} />
              <Route path="/chat" element={<Navigate to="/market-overview" replace />} />
              <Route path="/portfolio" element={<RegisteredSurfaceRoute><PortfolioPage /></RegisteredSurfaceRoute>} />
              <Route path="/market-overview" element={<RegisteredSurfaceRoute><MarketOverviewPage /></RegisteredSurfaceRoute>} />
              <Route path="/market/liquidity-monitor" element={<LiquidityMonitorPage />} />
              <Route path="/market/rotation-radar" element={<MarketRotationRadarPage />} />
              <Route path="/watchlist" element={<RegisteredSurfaceRoute><WatchlistPage /></RegisteredSurfaceRoute>} />
              <Route path="/backtest" element={<RegisteredSurfaceRoute><BacktestPage /></RegisteredSurfaceRoute>} />
              <Route path="/options-lab" element={<RegisteredSurfaceRoute><OptionsLabPage /></RegisteredSurfaceRoute>} />
              <Route path="/backtest/compare" element={<RegisteredSurfaceRoute><RuleBacktestComparePage /></RegisteredSurfaceRoute>} />
              <Route path="/backtest/results/:runId" element={<RegisteredSurfaceRoute><DeterministicBacktestResultPage /></RegisteredSurfaceRoute>} />
              <Route path="/settings" element={<PersonalSettingsPage />} />
              <Route path="/settings/system" element={<AdminSurfaceRoute><SystemSettingsPage /></AdminSurfaceRoute>} />
              <Route path="/admin/logs" element={<AdminSurfaceRoute><AdminLogsPage /></AdminSurfaceRoute>} />
              <Route path="/admin/evidence-workflow" element={<AdminSurfaceRoute><AdminEvidenceWorkflowPage /></AdminSurfaceRoute>} />
              <Route path="/admin/notifications" element={<AdminSurfaceRoute><AdminNotificationsPage /></AdminSurfaceRoute>} />
              <Route path="/admin/market-providers" element={<AdminSurfaceRoute><MarketProviderOperationsPage /></AdminSurfaceRoute>} />
              <Route path="/admin/provider-circuits" element={<AdminSurfaceRoute><AdminProviderCircuitDiagnosticsPage /></AdminSurfaceRoute>} />
              <Route path="/admin/users" element={<AdminSurfaceRoute><AdminUsersPage /></AdminSurfaceRoute>} />
              <Route path="/admin/users/:userId" element={<AdminSurfaceRoute><AdminUsersPage /></AdminSurfaceRoute>} />
              <Route path="/admin/users/:userId/activity" element={<AdminSurfaceRoute><AdminUsersPage /></AdminSurfaceRoute>} />
              <Route path="/admin/cost-observability" element={<AdminSurfaceRoute><AdminCostObservabilityPage /></AdminSurfaceRoute>} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
            <Route path="/:locale" element={<Shell />}>
              <Route path="market" element={<Navigate to="../market-overview" replace />} />
              <Route path="admin" element={<Navigate to="../settings/system" replace />} />
              <Route index element={<HomeSurfacePage />} />
              <Route path="guest" element={guestHomeElement} />
              <Route path="scanner" element={<ScannerSurfacePage />} />
              <Route path="chat" element={<Navigate to="../market-overview" replace />} />
              <Route path="portfolio" element={<RegisteredSurfaceRoute><PortfolioPage /></RegisteredSurfaceRoute>} />
              <Route path="market-overview" element={<RegisteredSurfaceRoute><MarketOverviewPage /></RegisteredSurfaceRoute>} />
              <Route path="market/liquidity-monitor" element={<LiquidityMonitorPage />} />
              <Route path="market/rotation-radar" element={<MarketRotationRadarPage />} />
              <Route path="watchlist" element={<RegisteredSurfaceRoute><WatchlistPage /></RegisteredSurfaceRoute>} />
              <Route path="backtest" element={<RegisteredSurfaceRoute><BacktestPage /></RegisteredSurfaceRoute>} />
              <Route path="options-lab" element={<RegisteredSurfaceRoute><OptionsLabPage /></RegisteredSurfaceRoute>} />
              <Route path="backtest/compare" element={<RegisteredSurfaceRoute><RuleBacktestComparePage /></RegisteredSurfaceRoute>} />
              <Route path="backtest/results/:runId" element={<RegisteredSurfaceRoute><DeterministicBacktestResultPage /></RegisteredSurfaceRoute>} />
              <Route path="settings" element={<PersonalSettingsPage />} />
              <Route path="settings/system" element={<AdminSurfaceRoute><SystemSettingsPage /></AdminSurfaceRoute>} />
              <Route path="admin/logs" element={<AdminSurfaceRoute><AdminLogsPage /></AdminSurfaceRoute>} />
              <Route path="admin/evidence-workflow" element={<AdminSurfaceRoute><AdminEvidenceWorkflowPage /></AdminSurfaceRoute>} />
              <Route path="admin/notifications" element={<AdminSurfaceRoute><AdminNotificationsPage /></AdminSurfaceRoute>} />
              <Route path="admin/market-providers" element={<AdminSurfaceRoute><MarketProviderOperationsPage /></AdminSurfaceRoute>} />
              <Route path="admin/provider-circuits" element={<AdminSurfaceRoute><AdminProviderCircuitDiagnosticsPage /></AdminSurfaceRoute>} />
              <Route path="admin/users" element={<AdminSurfaceRoute><AdminUsersPage /></AdminSurfaceRoute>} />
              <Route path="admin/users/:userId" element={<AdminSurfaceRoute><AdminUsersPage /></AdminSurfaceRoute>} />
              <Route path="admin/users/:userId/activity" element={<AdminSurfaceRoute><AdminUsersPage /></AdminSurfaceRoute>} />
              <Route path="admin/cost-observability" element={<AdminSurfaceRoute><AdminCostObservabilityPage /></AdminSurfaceRoute>} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/:locale/login" element={<LoginPage />} />
            <Route path="/register" element={<Navigate to={buildRegistrationPath(localizedHomePath)} replace />} />
            <Route path="/:locale/register" element={<Navigate to={buildRegistrationPath(localizedHomePath)} replace />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/:locale/reset-password" element={<ResetPasswordPage />} />
          </Routes>
        </Suspense>
      );
    }
  }

  return (
    <>
      {content}
      {showBootSplash ? (
        <BrandedLoadingScreen
          fading={bootSplashFading}
          text={t('app.loadingBrand')}
          subtext={isLoading ? t('app.loading') : undefined}
        />
      ) : null}
    </>
  );
};

const PreviewRoutes: React.FC = () => {
  const location = useLocation();
  const { setLanguage, t } = useI18n();
  const routeLocale = parseLocaleFromPathname(location.pathname);

  useEffect(() => {
    if (routeLocale) {
      setLanguage(routeLocale);
    }
  }, [routeLocale, setLanguage]);

  return (
    <PreviewShell>
      <Suspense fallback={<BrandedLoadingScreen text={t('app.loadingBrand')} subtext={t('app.loading')} />}>
        <Routes>
          <Route path="/__preview/report" element={<PreviewReportPage />} />
          <Route path="/__preview/full-report" element={<PreviewFullReportDrawerPage />} />
          <Route path="/:locale/__preview/report" element={<PreviewReportPage />} />
          <Route path="/:locale/__preview/full-report" element={<PreviewFullReportDrawerPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </PreviewShell>
  );
};

const AppBody: React.FC = () => {
  const location = useLocation();
  const isPreviewRoute = isPreviewRoutePath(location.pathname);

  if (isPreviewRoute) {
    return <PreviewRoutes />;
  }

  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

const App: React.FC = () => (
  <Router>
    <AppBody />
  </Router>
);

export default App;
