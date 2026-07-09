import type React from 'react';
import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { BrowserRouter as Router, Navigate, Outlet, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { AppErrorBoundary } from './components/common/AppErrorBoundary';
import { BrandedLoadingScreen } from './components/common/BrandedLoadingScreen';
import { ConsumerProtectedFrame } from './components/layout/ConsumerWorkspaceShell';
import { Shell } from './components/layout/Shell';
import { PreviewShell } from './components/layout/PreviewShell';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { useI18n } from './contexts/UiLanguageContext';
import { useProductSurface } from './hooks/useProductSurface';
import type { UiLanguage } from './i18n/core';
import { buildLocalizedPath, parseLocaleFromPathname, stripLocalePrefix } from './utils/localeRouting';
import {
  getAuthBootstrapRouteKind,
  isAuthEntryPath,
  isPreviewRoutePath,
  isStockStructureDecisionDetailPath,
  type AuthBootstrapRouteKind,
} from './utils/appRouteGuards';
import { canAccessAdminPath, isAdminMissionControlPath, isAdminMissionControlPrototypeEnabled } from './utils/adminCapabilities';

const APP_BOOT_SPLASH_MIN_MS = 320;
const APP_BOOT_SPLASH_FADE_MS = 180;

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
const MarketDecisionCockpitPage = lazy(() => import('./pages/MarketDecisionCockpitPage'));
const LiquidityMonitorPage = lazy(() => import('./pages/LiquidityMonitorPage'));
const MarketRotationRadarPage = lazy(() => import('./pages/MarketRotationRadarPage'));
const StockStructureDecisionPage = lazy(() => import('./pages/StockStructureDecisionPage'));
const StockStructureDecisionEntryPage = lazy(() => import('./pages/StockStructureDecisionEntryPage'));
const ResearchRadarPage = lazy(() => import('./pages/ResearchRadarPage'));
const ScenarioLabPage = lazy(() => import('./pages/ScenarioLabPage'));
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
const AdminMissionControlPage = lazy(() => import('./pages/AdminMissionControlPage'));
const AdminLaunchCockpitPage = lazy(() => import('./pages/AdminLaunchCockpitPage'));

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

type AuthBootstrapSurfaceCopy = {
  ariaLabel: string;
  title: string;
  description: string;
  actionLabel: string;
};

const ROUTE_LOADING_COPY: Record<UiLanguage, {
  ariaLabel: string;
  title: string;
  description: string;
}> = {
  zh: {
    ariaLabel: '正在打开研究页面',
    title: '正在打开研究页面',
    description: '导航和账户状态会保持不变。',
  },
  en: {
    ariaLabel: 'Opening research page',
    title: 'Opening research page',
    description: 'Navigation and account state stay in place.',
  },
};

export const RouteLoadingFallback: React.FC<{ language: UiLanguage }> = ({ language }) => {
  const copy = ROUTE_LOADING_COPY[language];

  return (
    <section
      role="status"
      aria-live="polite"
      aria-label={copy.ariaLabel}
      data-testid="route-loading-fallback"
      className="flex min-h-[min(420px,calc(100vh-9rem))] w-full min-w-0 items-center justify-center px-4 py-8"
    >
      <div className="theme-panel-glass w-full max-w-xl rounded-[14px] border border-[color:var(--wolfy-divider)] bg-[var(--wolfy-surface-panel)] p-5 shadow-none">
        <div className="flex min-w-0 items-start gap-4">
          <span
            className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-[var(--sage)] motion-safe:animate-pulse"
            aria-hidden="true"
          />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{copy.title}</p>
            <p className="mt-1 text-sm leading-6 text-[color:var(--wolfy-text-muted)]">{copy.description}</p>
            <div className="mt-4 grid gap-2" aria-hidden="true">
              <span className="h-2.5 w-11/12 rounded-full bg-[color:var(--wolfy-divider)]" />
              <span className="h-2.5 w-8/12 rounded-full bg-[color:var(--wolfy-divider)]" />
              <span className="h-2.5 w-5/12 rounded-full bg-[color:var(--wolfy-divider)]" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

function getAdminSurfaceCopy(pathname: string, language: UiLanguage, isGuest: boolean): GateCopy {
  const isEnglish = language === 'en';

  if (pathname.startsWith('/admin/launch-cockpit') || pathname.startsWith('/admin/mission-control') || pathname.startsWith('/admin/logs') || pathname.startsWith('/admin/evidence-workflow') || pathname.startsWith('/admin/notifications') || pathname.startsWith('/admin/market-providers') || pathname.startsWith('/admin/provider-operations') || pathname.startsWith('/admin/provider-circuits') || pathname.startsWith('/admin/users') || pathname.startsWith('/admin/cost-observability')) {
    const surfaceName = pathname.startsWith('/admin/cost-observability')
      ? (isEnglish ? 'cost observability' : '成本观测')
      : pathname.startsWith('/admin/launch-cockpit')
      ? (isEnglish ? 'launch cockpit' : 'Launch Cockpit')
      : pathname.startsWith('/admin/mission-control')
      ? (isEnglish ? 'mission control' : 'Mission Control')
      : pathname.startsWith('/admin/evidence-workflow')
      ? (isEnglish ? 'evidence workflow' : '证据工作流')
      : pathname.startsWith('/admin/provider-circuits')
      ? (isEnglish ? 'provider circuit diagnostics' : 'Provider 熔断诊断')
      : pathname.startsWith('/admin/market-providers') || pathname.startsWith('/admin/provider-operations')
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
      title: isEnglish ? 'Sign in with an admin account to open system settings' : '请使用管理员账户登录后打开系统设置',
      description: isEnglish
        ? 'This admin-only system settings surface is separate from personal settings, even though its canonical route lives under /settings/system.'
        : '这个仅限管理员的系统设置页面与个人设置分离，即使它的规范路由位于 /settings/system。',
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

function getMissionControlPrototypeGateCopy(language: UiLanguage): GateCopy {
  const isEnglish = language === 'en';
  return {
    eyebrow: isEnglish ? 'Prototype Gated' : 'Prototype Gate',
    statusLabel: isEnglish ? 'Prototype Disabled' : 'Prototype 未启用',
    title: isEnglish ? 'Admin Mission Control prototype is disabled' : 'Admin Mission Control prototype 未启用',
    description: isEnglish
      ? 'This cockpit is hidden by default and only opens when the explicit prototype flag is enabled for admin review.'
      : '这个 cockpit 默认隐藏，只有显式启用 prototype flag 后才会进入管理员复核界面。',
    bullets: isEnglish
      ? [
        'Default navigation does not advertise this cockpit.',
        'The backend disabled response does not aggregate ops summaries.',
        'Enabling the prototype still keeps the route admin-only and advisory.',
      ]
      : [
        '默认导航不会展示这个 cockpit。',
        '后端 disabled 响应不会聚合 ops 摘要。',
        '显式启用 prototype 后仍然只限管理员、只读且仅供参考。',
      ],
    note: isEnglish
      ? 'Set VITE_WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED=true only for bounded prototype review.'
      : '仅在有边界的 prototype 复核中设置 VITE_WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED=true。',
    secondaryAction: {
      label: isEnglish ? 'Open system settings' : '打开系统设置',
      to: '/settings/system',
    },
  };
}

function getPostAuthRedirectTarget(search: string, fallbackPath: string): string {
  const redirect = new URLSearchParams(search).get('redirect');
  if (!redirect || !redirect.startsWith('/') || redirect.startsWith('//')) {
    return fallbackPath;
  }

  try {
    const redirectUrl = new URL(redirect, 'http://wolfystock.local');
    if (redirectUrl.origin !== 'http://wolfystock.local') {
      return fallbackPath;
    }

    const routePathname = stripLocalePrefix(redirectUrl.pathname);
    if (isAuthEntryPath(routePathname)) {
      return fallbackPath;
    }

    return `${redirectUrl.pathname}${redirectUrl.search}${redirectUrl.hash}`;
  } catch {
    return fallbackPath;
  }
}

function getAuthBootstrapSurfaceCopy(kind: AuthBootstrapRouteKind, language: UiLanguage): AuthBootstrapSurfaceCopy {
  const isEnglish = language === 'en';

  switch (kind) {
    case 'public':
      return {
        ariaLabel: isEnglish ? 'Authentication status notice' : '认证状态提示',
        title: isEnglish ? 'Account status is temporarily unavailable' : '账户状态暂时不可用',
        description: isEnglish
          ? 'Only guest-safe content is shown until account status is confirmed.'
          : '在确认账户状态前，仅显示游客安全内容。',
        actionLabel: isEnglish ? 'Retry' : '重试',
      };
    case 'protected':
      return {
        ariaLabel: isEnglish ? 'Protected route locked' : '受保护路由已锁定',
        title: isEnglish ? 'Protected pages stay locked' : '受保护页面保持锁定',
        description: isEnglish
          ? 'Protected pages stay locked until account status is confirmed.'
          : '在确认账户状态前，受保护页面保持锁定。',
        actionLabel: isEnglish ? 'Retry' : '重试',
      };
    case 'admin':
      return {
        ariaLabel: isEnglish ? 'Admin route locked' : '管理员路由已锁定',
        title: isEnglish ? 'Admin pages stay locked' : '管理员页面保持锁定',
        description: isEnglish
          ? 'Admin pages stay locked until account and capability status are confirmed.'
          : '在确认账户和能力状态前，管理员页面保持锁定。',
        actionLabel: isEnglish ? 'Retry' : '重试',
      };
    case 'auth-entry':
      return {
        ariaLabel: isEnglish ? 'Authentication entry paused' : '认证入口已暂停',
        title: isEnglish ? 'Sign-in and setup entry points stay paused' : '登录和入口设置保持暂停',
        description: isEnglish
          ? 'Sign-in and account setup entry points stay paused until account status is confirmed.'
          : '在确认账户状态前，登录和账户入口设置保持暂停。',
        actionLabel: isEnglish ? 'Retry' : '重试',
      };
    default:
      return {
        ariaLabel: isEnglish ? 'Authentication status unavailable' : '认证状态不可用',
        title: isEnglish ? 'Authentication status is unavailable' : '认证状态不可用',
        description: isEnglish
          ? 'Please retry after the account status service responds again.'
          : '请在账户状态服务恢复后重试。',
        actionLabel: isEnglish ? 'Retry' : '重试',
      };
  }
}

const AuthBootstrapStatusPanel: React.FC<{
  kind: AuthBootstrapRouteKind;
  language: UiLanguage;
  onRetry: () => void;
  compact?: boolean;
}> = ({ kind, language, onRetry, compact = false }) => {
  const copy = getAuthBootstrapSurfaceCopy(kind, language);
  const isPublic = kind === 'public';

  return (
    <section
      role={isPublic ? 'status' : 'alert'}
      aria-label={copy.ariaLabel}
      aria-live={isPublic ? 'polite' : 'assertive'}
      className={compact ? 'theme-panel-glass w-full max-w-xl p-4' : 'theme-panel-glass w-full max-w-xl p-5'}
    >
      <div className="flex min-w-0 flex-col gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <p className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{copy.title}</p>
          <p className="text-sm leading-6 text-[color:var(--wolfy-text-muted)]">{copy.description}</p>
        </div>
        <div className="flex justify-end">
          <button type="button" className="btn-primary" onClick={onRetry}>
            {copy.actionLabel}
          </button>
        </div>
      </div>
    </section>
  );
};

const RegisteredSurfaceRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const { language } = useI18n();
  const { isGuest } = useProductSurface();
  const routePathname = stripLocalePrefix(location.pathname);
  let moduleName = language === 'en' ? 'Premium module' : '高级模块';

  if (routePathname.startsWith('/portfolio')) {
    moduleName = language === 'en' ? 'Portfolio' : '持仓管理';
  } else if (routePathname.startsWith('/scanner')) {
    moduleName = language === 'en' ? 'Scanner' : '扫描器';
  } else if (routePathname.startsWith('/market-overview')) {
    moduleName = language === 'en' ? 'Market Overview' : '市场总览';
  } else if (routePathname.startsWith('/research/radar')) {
    moduleName = language === 'en' ? 'Research Radar' : '研究雷达';
  } else if (isStockStructureDecisionDetailPath(routePathname)) {
    moduleName = language === 'en' ? 'Stock Research' : '个股研究';
  } else if (routePathname.startsWith('/scenario-lab')) {
    moduleName = language === 'en' ? 'Scenario Lab' : '情景实验室';
  } else if (routePathname.startsWith('/watchlist')) {
    moduleName = language === 'en' ? 'Watchlist' : '观察列表';
  } else if (routePathname.startsWith('/backtest')) {
    moduleName = language === 'en' ? 'Backtest' : '回测';
  } else if (routePathname.startsWith('/options-lab')) {
    moduleName = language === 'en' ? 'Options Lab' : '期权实验室';
  } else if (routePathname.startsWith('/settings')) {
    moduleName = language === 'en' ? 'Personal settings' : '个人设置';
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
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const currentRoute = `${location.pathname}${location.search}${location.hash}`;
  const loginPath = routeLocale
    ? buildLocalizedPath(`/login?redirect=${encodeURIComponent(currentRoute)}`, routeLocale)
    : `/login?redirect=${encodeURIComponent(currentRoute)}`;
  const missionControlPrototypeDisabled = isAdminMissionControlPath(routePathname) && !isAdminMissionControlPrototypeEnabled();
  const baseGateCopy = isAdminAccount && missionControlPrototypeDisabled
    ? getMissionControlPrototypeGateCopy(language)
    : getAdminSurfaceCopy(routePathname, language, isGuest);
  const gateCopy = isAdminAccount && !missionControlPrototypeDisabled
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
        to: isGuest ? loginPath : '/settings',
      }}
      secondaryAction={gateCopy.secondaryAction}
    />
  );
};

const StockStructureDecisionLegacyRedirect: React.FC = () => {
  const location = useLocation();
  const { stockCode = '' } = useParams<{ stockCode: string }>();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const canonicalPath = `/stocks/${encodeURIComponent(stockCode)}/structure-decision${location.search}${location.hash}`;
  const to = routeLocale ? buildLocalizedPath(canonicalPath, routeLocale) : canonicalPath;

  return <Navigate to={to} replace />;
};

const AppShellRoute: React.FC = () => {
  const { language } = useI18n();

  return (
    <Shell>
      <Suspense fallback={<RouteLoadingFallback language={language} />}>
        <Outlet />
      </Suspense>
    </Shell>
  );
};

export const AppContent: React.FC = () => {
  const location = useLocation();
  const { authEnabled, loggedIn, isLoading, loadError, refreshStatus, setupState } = useAuth();
  const { language, setLanguage, t } = useI18n();
  const bootStartedAt = useRef<number>(0);
  const [showBootSplash, setShowBootSplash] = useState(true);
  const [bootSplashFading, setBootSplashFading] = useState(false);
  const splashDismissed = useRef(false);
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const routePathname = stripLocalePrefix(location.pathname);
  const authBootstrapRouteKind = getAuthBootstrapRouteKind(routePathname);
  const localizedHomePath = routeLocale ? buildLocalizedPath('/', routeLocale) : '/';
  const postAuthRedirectPath = getPostAuthRedirectTarget(location.search, localizedHomePath);
  const guestHomeElement = loggedIn ? <Navigate to={localizedHomePath} replace /> : <GuestHomePage />;

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

  const routeTree = (
    <Suspense fallback={<RouteLoadingFallback language={language} />}>
      <Routes>
        <Route path="/guest/scanner" element={<Navigate to="/scanner" replace />} />
        <Route path="/user/scanner" element={<Navigate to="/scanner" replace />} />
        <Route path="/:locale/guest/scanner" element={<Navigate to="../scanner" replace />} />
        <Route path="/:locale/user/scanner" element={<Navigate to="../scanner" replace />} />
        <Route path="/stock/:stockCode" element={<StockStructureDecisionLegacyRedirect />} />
        <Route path="/stock/:stockCode/structure-decision" element={<StockStructureDecisionLegacyRedirect />} />
        <Route path="/:locale/stock/:stockCode" element={<StockStructureDecisionLegacyRedirect />} />
        <Route path="/:locale/stock/:stockCode/structure-decision" element={<StockStructureDecisionLegacyRedirect />} />
        <Route element={<AppShellRoute />}>
          <Route path="/market" element={<Navigate to="/market-overview" replace />} />
          {/* /settings/system is the canonical admin system settings surface; /admin aliases remain intentional deep links. */}
          <Route path="/admin" element={<Navigate to="/settings/system" replace />} />
          <Route path="/admin/system" element={<Navigate to="/settings/system" replace />} />
          <Route path="/admin/provider" element={<Navigate to="/admin/market-providers" replace />} />
          <Route path="/admin/providers" element={<Navigate to="/admin/market-providers" replace />} />
          <Route path="/admin/provider-operations" element={<Navigate to="/admin/market-providers" replace />} />
        <Route path="/admin/evidence" element={<Navigate to="/admin/evidence-workflow" replace />} />
        <Route path="/admin/costs" element={<Navigate to="/admin/cost-observability" replace />} />
        <Route path="/admin/ai" element={<Navigate to="/settings/system" replace />} />
        <Route path="/admin/system-logs" element={<Navigate to="/admin/logs" replace />} />
        <Route path="/cockpit" element={<Navigate to="/market/decision-cockpit" replace />} />
        <Route path="/decision-cockpit" element={<Navigate to="/market/decision-cockpit" replace />} />
        <Route path="/radar" element={<Navigate to="/research/radar" replace />} />
        <Route path="/research" element={<Navigate to="/research/radar" replace />} />
        <Route path="/research-radar" element={<Navigate to="/research/radar" replace />} />
        <Route path="/holdings" element={<Navigate to="/portfolio" replace />} />
        <Route path="/liquidity" element={<Navigate to="/market/liquidity-monitor" replace />} />
        <Route path="/rotation" element={<Navigate to="/market/rotation-radar" replace />} />
        <Route path="/options" element={<Navigate to="/options-lab" replace />} />
          <Route path="/" element={<HomeSurfacePage />} />
          <Route path="/guest" element={guestHomeElement} />
          <Route path="/scanner" element={<RegisteredSurfaceRoute><ScannerSurfacePage /></RegisteredSurfaceRoute>} />
          <Route path="/chat" element={<Navigate to="/market-overview" replace />} />
          <Route path="/portfolio" element={<RegisteredSurfaceRoute><PortfolioPage /></RegisteredSurfaceRoute>} />
          <Route path="/market-overview" element={<MarketOverviewPage />} />
          <Route path="/market/decision-cockpit" element={<MarketDecisionCockpitPage />} />
          <Route path="/market/liquidity-monitor" element={<LiquidityMonitorPage />} />
          <Route path="/market/rotation-radar" element={<MarketRotationRadarPage />} />
          <Route path="/stocks/structure-decision" element={<StockStructureDecisionEntryPage />} />
          <Route path="/stocks/:stockCode/structure-decision" element={<RegisteredSurfaceRoute><StockStructureDecisionPage /></RegisteredSurfaceRoute>} />
          <Route path="/research/radar" element={<RegisteredSurfaceRoute><ResearchRadarPage /></RegisteredSurfaceRoute>} />
          <Route path="/scenario-lab" element={<RegisteredSurfaceRoute><ScenarioLabPage /></RegisteredSurfaceRoute>} />
          <Route path="/watchlist" element={<RegisteredSurfaceRoute><WatchlistPage /></RegisteredSurfaceRoute>} />
          <Route path="/backtest" element={<RegisteredSurfaceRoute><BacktestPage /></RegisteredSurfaceRoute>} />
          <Route path="/options-lab" element={<RegisteredSurfaceRoute><OptionsLabPage /></RegisteredSurfaceRoute>} />
          <Route path="/backtest/compare" element={<RegisteredSurfaceRoute><RuleBacktestComparePage /></RegisteredSurfaceRoute>} />
          <Route path="/backtest/results/:runId" element={<RegisteredSurfaceRoute><DeterministicBacktestResultPage /></RegisteredSurfaceRoute>} />
          <Route path="/settings" element={<RegisteredSurfaceRoute><PersonalSettingsPage /></RegisteredSurfaceRoute>} />
          <Route path="/settings/system" element={<AdminSurfaceRoute><SystemSettingsPage /></AdminSurfaceRoute>} />
          <Route path="/admin/launch-cockpit" element={<AdminSurfaceRoute><AdminLaunchCockpitPage /></AdminSurfaceRoute>} />
          <Route path="/admin/mission-control" element={<AdminSurfaceRoute><AdminMissionControlPage /></AdminSurfaceRoute>} />
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
        <Route path="/:locale" element={<LocalizedShellRoute />}>
          <Route path="market" element={<Navigate to="../market-overview" replace />} />
          {/* /:locale/settings/system is the canonical localized admin system settings surface. */}
          <Route path="admin" element={<Navigate to="../settings/system" replace />} />
          <Route path="admin/system" element={<Navigate to="../settings/system" replace />} />
          <Route path="admin/provider" element={<Navigate to="../admin/market-providers" replace />} />
          <Route path="admin/providers" element={<Navigate to="../admin/market-providers" replace />} />
          <Route path="admin/provider-operations" element={<Navigate to="../admin/market-providers" replace />} />
          <Route path="admin/evidence" element={<Navigate to="../admin/evidence-workflow" replace />} />
          <Route path="admin/costs" element={<Navigate to="../admin/cost-observability" replace />} />
          <Route path="admin/ai" element={<Navigate to="../settings/system" replace />} />
          <Route path="admin/system-logs" element={<Navigate to="../admin/logs" replace />} />
          <Route path="cockpit" element={<Navigate to="../market/decision-cockpit" replace />} />
          <Route path="decision-cockpit" element={<Navigate to="../market/decision-cockpit" replace />} />
          <Route path="radar" element={<Navigate to="../research/radar" replace />} />
          <Route path="research" element={<Navigate to="../research/radar" replace />} />
          <Route path="research-radar" element={<Navigate to="../research/radar" replace />} />
          <Route path="holdings" element={<Navigate to="../portfolio" replace />} />
          <Route path="liquidity" element={<Navigate to="../market/liquidity-monitor" replace />} />
          <Route path="rotation" element={<Navigate to="../market/rotation-radar" replace />} />
          <Route path="options" element={<Navigate to="../options-lab" replace />} />
          <Route index element={<HomeSurfacePage />} />
          <Route path="guest" element={guestHomeElement} />
          <Route path="scanner" element={<RegisteredSurfaceRoute><ScannerSurfacePage /></RegisteredSurfaceRoute>} />
          <Route path="chat" element={<Navigate to="../market-overview" replace />} />
          <Route path="portfolio" element={<RegisteredSurfaceRoute><PortfolioPage /></RegisteredSurfaceRoute>} />
          <Route path="market-overview" element={<MarketOverviewPage />} />
          <Route path="market/decision-cockpit" element={<MarketDecisionCockpitPage />} />
          <Route path="market/liquidity-monitor" element={<LiquidityMonitorPage />} />
          <Route path="market/rotation-radar" element={<MarketRotationRadarPage />} />
          <Route path="stocks/structure-decision" element={<StockStructureDecisionEntryPage />} />
          <Route path="stocks/:stockCode/structure-decision" element={<RegisteredSurfaceRoute><StockStructureDecisionPage /></RegisteredSurfaceRoute>} />
          <Route path="research/radar" element={<RegisteredSurfaceRoute><ResearchRadarPage /></RegisteredSurfaceRoute>} />
          <Route path="scenario-lab" element={<RegisteredSurfaceRoute><ScenarioLabPage /></RegisteredSurfaceRoute>} />
          <Route path="watchlist" element={<RegisteredSurfaceRoute><WatchlistPage /></RegisteredSurfaceRoute>} />
          <Route path="backtest" element={<RegisteredSurfaceRoute><BacktestPage /></RegisteredSurfaceRoute>} />
          <Route path="options-lab" element={<RegisteredSurfaceRoute><OptionsLabPage /></RegisteredSurfaceRoute>} />
          <Route path="backtest/compare" element={<RegisteredSurfaceRoute><RuleBacktestComparePage /></RegisteredSurfaceRoute>} />
          <Route path="backtest/results/:runId" element={<RegisteredSurfaceRoute><DeterministicBacktestResultPage /></RegisteredSurfaceRoute>} />
          <Route path="settings" element={<RegisteredSurfaceRoute><PersonalSettingsPage /></RegisteredSurfaceRoute>} />
          <Route path="settings/system" element={<AdminSurfaceRoute><SystemSettingsPage /></AdminSurfaceRoute>} />
          <Route path="admin/launch-cockpit" element={<AdminSurfaceRoute><AdminLaunchCockpitPage /></AdminSurfaceRoute>} />
          <Route path="admin/mission-control" element={<AdminSurfaceRoute><AdminMissionControlPage /></AdminSurfaceRoute>} />
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
        <Route path="/register" element={<LoginPage />} />
        <Route path="/:locale/register" element={<LoginPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/:locale/reset-password" element={<ResetPasswordPage />} />
      </Routes>
    </Suspense>
  );

  let content: React.ReactNode = null;

  if (loadError) {
    const retryAuthStatus = () => {
      void refreshStatus();
    };

    content = authBootstrapRouteKind === 'public' ? (
      <div className="flex min-h-screen flex-col gap-4 bg-base px-4 py-4">
        <AuthBootstrapStatusPanel
          kind="public"
          language={language}
          onRetry={retryAuthStatus}
          compact
        />
        {routeTree}
      </div>
    ) : (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-base px-4 py-8">
        <AuthBootstrapStatusPanel
          kind={authBootstrapRouteKind}
          language={language}
          onRetry={retryAuthStatus}
        />
      </div>
    );
  } else if (!isLoading) {
    if (routePathname === '/login' || routePathname === '/register') {
      const canRenderLogin = authEnabled || setupState === 'no_password' || setupState === 'password_retained';
      if (loggedIn) {
        content = <Navigate to={postAuthRedirectPath} replace />;
      } else if (!canRenderLogin) {
        content = <Navigate to={localizedHomePath} replace />;
      } else {
        content = (
          <Suspense fallback={<RouteLoadingFallback language={language} />}>
            <LoginPage />
          </Suspense>
        );
      }
    } else if (routePathname === '/reset-password') {
      if (!authEnabled || loggedIn) {
        content = <Navigate to={localizedHomePath} replace />;
      } else {
        content = (
          <Suspense fallback={<RouteLoadingFallback language={language} />}>
            <ResetPasswordPage />
          </Suspense>
        );
      }
    } else {
      content = routeTree;
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
  const { setLanguage } = useI18n();
  const routeLocale = parseLocaleFromPathname(location.pathname);

  useEffect(() => {
    if (routeLocale) {
      setLanguage(routeLocale);
    }
  }, [routeLocale, setLanguage]);

  return (
    <PreviewShell>
      <Suspense fallback={<RouteLoadingFallback language={routeLocale || 'zh'} />}>
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

const LocalizedShellRoute: React.FC = () => {
  const location = useLocation();
  const { language } = useI18n();
  const routeLocale = parseLocaleFromPathname(location.pathname);

  if (!routeLocale) {
    return <NotFoundPage />;
  }

  return (
    <Shell>
      <Suspense fallback={<RouteLoadingFallback language={language} />}>
        <Outlet />
      </Suspense>
    </Shell>
  );
};

const AppBody: React.FC = () => {
  const location = useLocation();
  const isPreviewRoute = isPreviewRoutePath(location.pathname);

  if (isPreviewRoute) {
    return (
      <AppErrorBoundary>
        <PreviewRoutes />
      </AppErrorBoundary>
    );
  }

  return (
    <AppErrorBoundary>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </AppErrorBoundary>
  );
};

const App: React.FC = () => (
  <Router>
    <AppBody />
  </Router>
);

export default App;
