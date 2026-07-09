/**
 * WolfyStock shell navigation: workflow-grouped research workbench IA.
 * Major research capabilities live in named groups (Market / Research /
 * Validate), not a generic More bucket. Archive, language, and logout
 * controls remain on the shared paper shell tokens.
 */
import React, { useEffect, useRef, useState } from 'react';
import {
  Archive,
  Activity,
  ArrowRight,
  BellRing,
  BriefcaseBusiness,
  BarChart3,
  CircuitBoard,
  ChevronDown,
  DatabaseZap,
  FlaskConical,
  FileCheck2,
  Gauge,
  Globe,
  LogIn,
  LogOut,
  Moon,
  Radar,
  Search,
  ListChecks,
  Settings2,
  ShieldCheck,
  Sun,
  UsersRound,
} from 'lucide-react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useI18n } from '../../contexts/UiLanguageContext';
import { buildLoginPath, useProductSurface } from '../../hooks/useProductSurface';
import { cn } from '../../utils/cn';
import { isAdminMissionControlPrototypeEnabled } from '../../utils/adminCapabilities';
import { buildLocalizedPath, parseLocaleFromPathname, stripLocalePrefix } from '../../utils/localeRouting';
import { validateStockCode } from '../../utils/validation';
import { BrandLogo, BRAND_WORDMARK_CLASSNAME } from '../common/BrandLogo';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { useThemeStyle } from '../theme/themeState';
import {
  CONSUMER_NAV_ARCHITECTURE,
  CONSUMER_NAV_GROUPS,
  getConsumerNavGroupRoutes,
  getCoreProductRouteByKey,
  resolveCurrentConsumerRoute,
  type ConsumerNavGroupKey,
  type CoreProductRoute,
  type CoreProductRouteKey,
} from './coreProductRoutes';

type SidebarNavProps = {
  layout?: 'header' | 'drawer';
  onNavigate?: () => void;
  onOpenArchive?: () => void;
  hasArchive?: boolean;
};

type NavItem = {
  key: CoreProductRouteKey;
  labelKey?: string;
  label?: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
};

type AdminNavGroupKey = 'trust' | 'evidence' | 'dataOps' | 'support';

type AdminNavItem = {
  key: string;
  label: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  group: AdminNavGroupKey;
};

type AdminNavGroup = {
  key: AdminNavGroupKey;
  label: string;
  items: AdminNavItem[];
};

type AdminNavCopy = {
  menuLabel: string;
  launchCockpit: string;
  missionControl: string;
  system: string;
  marketProviders: string;
  providerCircuits: string;
  logs: string;
  cost: string;
  users: string;
  evidence: string;
  notifications: string;
};

const BrandWordmark: React.FC<{
  onNavigate?: () => void;
  className?: string;
}> = ({ onNavigate, className }) => (
  <Link
    to="/"
    onClick={onNavigate}
    aria-label="WolfyStock"
    className={cn('shell-brand-link', className || '')}
  >
    <span className="inline-flex min-w-0 items-center gap-3">
      <BrandLogo className="size-8" />
      <span className={`shell-wordmark ${BRAND_WORDMARK_CLASSNAME}`}>WolfyStock</span>
    </span>
  </Link>
);

const ROUTE_ICON_BY_KEY: Record<CoreProductRouteKey, React.ComponentType<{ className?: string }>> = {
  home: Activity,
  'decision-cockpit': Gauge,
  'market-overview': Activity,
  'research-radar': Radar,
  'stock-structure': BarChart3,
  scanner: Radar,
  watchlist: ListChecks,
  portfolio: BriefcaseBusiness,
  backtest: FileCheck2,
  'scenario-lab': FlaskConical,
  'options-lab': FlaskConical,
};

function routeToNavItem(route: CoreProductRoute): NavItem {
  return {
    key: route.key,
    labelKey: route.labelKey,
    to: route.path,
    icon: ROUTE_ICON_BY_KEY[route.key],
  };
}

const HEADER_UTILITY_TEXT_CLASS = 'shell-header-action px-2.5 py-1 text-[11px] font-medium text-[color:var(--wolfy-text-muted)] transition-colors hover:text-[color:var(--wolfy-text-primary)]';
const HEADER_UTILITY_DANGER_TEXT_CLASS = 'shell-header-action px-2.5 py-1 text-[11px] font-medium text-[color:var(--state-danger-text)] transition-colors hover:text-[color:var(--wolfy-text-primary)]';
const ADMIN_NAV_GROUP_ORDER: AdminNavGroupKey[] = ['trust', 'evidence', 'dataOps', 'support'];

function isAdminOpsRoute(pathname: string): boolean {
  const routePathname = stripLocalePrefix(pathname);
  return routePathname.startsWith('/settings/system')
    || routePathname.startsWith('/admin/launch-cockpit')
    || routePathname.startsWith('/admin/mission-control')
    || routePathname.startsWith('/admin/logs')
    || routePathname.startsWith('/admin/evidence-workflow')
    || routePathname.startsWith('/admin/notifications')
    || routePathname.startsWith('/admin/market-providers')
    || routePathname.startsWith('/admin/provider-circuits')
    || routePathname.startsWith('/admin/users')
    || routePathname.startsWith('/admin/cost-observability');
}

function adminNavItemMatchesPath(pathname: string, item: AdminNavItem): boolean {
  const routePathname = stripLocalePrefix(pathname);
  const targetPathname = stripLocalePrefix(item.to);

  if (item.key === 'system') {
    return routePathname === targetPathname || routePathname.startsWith(`${targetPathname}/`);
  }

  return routePathname === targetPathname || routePathname.startsWith(`${targetPathname}/`);
}

function resolveAdminNavCopy(language: string): AdminNavCopy {
  if (language === 'en') {
    return {
      menuLabel: 'Admin/Ops navigation',
      launchCockpit: 'Launch Cockpit',
      missionControl: 'Mission Control',
      system: 'Ops Overview / System Settings',
      marketProviders: 'Data Sources & Readiness',
      providerCircuits: 'Circuit Diagnostics',
      logs: 'System Logs',
      cost: 'Cost Observability',
      users: 'User Governance',
      evidence: 'Evidence Review',
      notifications: 'Notification Channels',
    };
  }

  return {
    menuLabel: 'Admin/Ops 运维导航',
    launchCockpit: 'Launch Cockpit',
    missionControl: 'Mission Control',
    system: '运维总览/系统设置',
    marketProviders: '数据源与就绪度',
    providerCircuits: '熔断诊断',
    logs: '系统日志',
    cost: '成本观测',
    users: '用户治理',
    evidence: '证据复核',
    notifications: '通知通道',
  };
}

function adminNavGroupLabel(group: AdminNavGroupKey, language: 'zh' | 'en'): string {
  const labels: Record<AdminNavGroupKey, { zh: string; en: string }> = {
    trust: { zh: '总览 / Trust', en: 'Overview / Trust' },
    evidence: { zh: '事件 / Evidence', en: 'Events / Evidence' },
    dataOps: { zh: '数据运行 / Data Ops', en: 'Data Ops' },
    support: { zh: '用户支持 / Support', en: 'Support' },
  };
  return labels[group][language];
}

function groupAdminNavItems(items: AdminNavItem[], language: 'zh' | 'en'): AdminNavGroup[] {
  return ADMIN_NAV_GROUP_ORDER
    .map((group) => ({
      key: group,
      label: adminNavGroupLabel(group, language),
      items: items.filter((item) => item.group === group),
    }))
    .filter((group) => group.items.length > 0);
}

function inferSymbolMarketContext(symbol: string, language: 'zh' | 'en'): string {
  const normalized = symbol.trim().toUpperCase();
  if (/^(SH|SZ|BJ)\d{6}$/.test(normalized) || /^\d{6}\.(SH|SZ|SS|BJ)$/.test(normalized) || /^\d{6}$/.test(normalized)) {
    return language === 'en' ? 'CN market context' : 'A 股语境';
  }
  if (/^HK\d{1,5}$/.test(normalized) || /^\d{1,5}\.HK$/.test(normalized) || /^\d{5}$/.test(normalized)) {
    return language === 'en' ? 'HK market context' : '港股语境';
  }
  return language === 'en' ? 'US ticker context' : '美股 ticker 语境';
}

function NavLabel({ label }: { label: string }) {
  return (
    <span className="relative inline-flex min-w-0 items-center gap-2">
      <span>{label}</span>
    </span>
  );
}

function DrawerUtilityLabel({
  label,
  value,
}: {
  label: string;
  value?: string;
}) {
  return (
    <span className="shell-nav-item__copy">
      <span className="shell-nav-item__label">{label}</span>
      {value ? <span className="shell-nav-item__value">{value}</span> : null}
    </span>
  );
}

function useSidebarNavView({
  layout = 'header',
  onNavigate,
  onOpenArchive,
  hasArchive = false,
}: SidebarNavProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { authEnabled, logout } = useAuth();
  const {
    isGuest,
    canReadCostObservability,
    canReadNotifications,
    canReadOpsLogs,
    canReadProviders,
    canReadSystemConfig,
    canReadUsers,
  } = useProductSurface();
  const { language, t, toggleLanguage } = useI18n();
  const { colorMode, setColorMode } = useThemeStyle();
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [showAdminMenu, setShowAdminMenu] = useState(false);
  const [openNavGroup, setOpenNavGroup] = useState<ConsumerNavGroupKey | null>(null);
  const [stockSearchQuery, setStockSearchQuery] = useState('');
  const [stockSearchError, setStockSearchError] = useState('');
  const [stockSearchFocused, setStockSearchFocused] = useState(false);
  const adminMenuRef = useRef<HTMLDivElement | null>(null);
  const navGroupMenuRefs = useRef<Partial<Record<ConsumerNavGroupKey, HTMLDivElement | null>>>({});
  const navGroupButtonRefs = useRef<Partial<Record<ConsumerNavGroupKey, HTMLButtonElement | null>>>({});
  const navGroupItemRefs = useRef<Partial<Record<ConsumerNavGroupKey, Array<HTMLAnchorElement | null>>>>({});
  const navGroupFocusIndexRef = useRef<{ group: ConsumerNavGroupKey; index: number } | null>(null);
  const stockSearchRef = useRef<HTMLInputElement | null>(null);
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const currentConsumerRoute = resolveCurrentConsumerRoute(location.pathname);
  const adminNavCopy = resolveAdminNavCopy(language);
  const isAdminRoute = isAdminOpsRoute(location.pathname);
  const isDrawer = layout === 'drawer';
  const stockSearchId = isDrawer ? 'shell-stock-search-drawer' : 'shell-stock-search-header';
  const signInLabel = t('nav.signIn');
  const consoleLabel = t('nav.independentConsole');
  const signInPath = buildLoginPath(location.pathname + location.search);
  const consolePath = routeLocale ? buildLocalizedPath('/settings/system', routeLocale) : '/settings/system';
  const launchCockpitPath = routeLocale ? buildLocalizedPath('/admin/launch-cockpit', routeLocale) : '/admin/launch-cockpit';
  const missionControlPath = routeLocale ? buildLocalizedPath('/admin/mission-control', routeLocale) : '/admin/mission-control';
  const adminLogsPath = routeLocale ? buildLocalizedPath('/admin/logs', routeLocale) : '/admin/logs';
  const evidenceWorkflowPath = routeLocale ? buildLocalizedPath('/admin/evidence-workflow', routeLocale) : '/admin/evidence-workflow';
  const notificationsPath = routeLocale ? buildLocalizedPath('/admin/notifications', routeLocale) : '/admin/notifications';
  const marketProvidersPath = routeLocale ? buildLocalizedPath('/admin/market-providers', routeLocale) : '/admin/market-providers';
  const providerCircuitsPath = routeLocale ? buildLocalizedPath('/admin/provider-circuits', routeLocale) : '/admin/provider-circuits';
  const userGovernancePath = routeLocale ? buildLocalizedPath('/admin/users', routeLocale) : '/admin/users';
  const costObservabilityPath = routeLocale ? buildLocalizedPath('/admin/cost-observability', routeLocale) : '/admin/cost-observability';
  const missionControlPrototypeEnabled = isAdminMissionControlPrototypeEnabled();
  const adminNavItems: AdminNavItem[] = [];
  if (canReadSystemConfig) {
    adminNavItems.push({ key: 'system', label: adminNavCopy.system, to: consolePath, icon: ShieldCheck, group: 'trust' });
  }
  if (canReadOpsLogs) {
    adminNavItems.push({ key: 'launch-cockpit', label: adminNavCopy.launchCockpit, to: launchCockpitPath, icon: ShieldCheck, group: 'trust' });
    if (missionControlPrototypeEnabled) {
      adminNavItems.push({ key: 'mission-control', label: adminNavCopy.missionControl, to: missionControlPath, icon: Gauge, group: 'trust' });
    }
    adminNavItems.push({ key: 'logs', label: adminNavCopy.logs, to: adminLogsPath, icon: Activity, group: 'evidence' });
    adminNavItems.push({ key: 'evidence', label: adminNavCopy.evidence, to: evidenceWorkflowPath, icon: FileCheck2, group: 'evidence' });
  }
  if (canReadProviders) {
    adminNavItems.push({ key: 'providers', label: adminNavCopy.marketProviders, to: marketProvidersPath, icon: DatabaseZap, group: 'dataOps' });
    adminNavItems.push({ key: 'provider-circuits', label: adminNavCopy.providerCircuits, to: providerCircuitsPath, icon: CircuitBoard, group: 'dataOps' });
  }
  if (canReadCostObservability) {
    adminNavItems.push({ key: 'cost', label: adminNavCopy.cost, to: costObservabilityPath, icon: BarChart3, group: 'dataOps' });
  }
  if (canReadUsers) {
    adminNavItems.push({ key: 'users', label: adminNavCopy.users, to: userGovernancePath, icon: UsersRound, group: 'support' });
  }
  if (canReadNotifications) {
    adminNavItems.push({ key: 'notifications', label: adminNavCopy.notifications, to: notificationsPath, icon: BellRing, group: 'support' });
  }
  const hasAdminMenu = adminNavItems.length > 0;
  const adminNavGroups = groupAdminNavItems(adminNavItems, language);
  const showAdminPrimaryNav = isAdminRoute && hasAdminMenu;
  const activeNavGroup = currentConsumerRoute?.navGroup ?? null;

  const handleAdminNavigate = () => {
    setShowAdminMenu(false);
    setOpenNavGroup(null);
    onNavigate?.();
  };

  const handleConsumerNavigate = () => {
    navGroupFocusIndexRef.current = null;
    setOpenNavGroup(null);
    setStockSearchFocused(false);
    onNavigate?.();
  };

  const closeNavGroupMenu = (options?: { returnFocus?: boolean; group?: ConsumerNavGroupKey | null }) => {
    const groupToFocus = options?.group ?? openNavGroup;
    navGroupFocusIndexRef.current = null;
    setOpenNavGroup(null);
    if (options?.returnFocus && groupToFocus) {
      window.setTimeout(() => {
        navGroupButtonRefs.current[groupToFocus]?.focus();
      }, 0);
    }
  };

  const openNavGroupMenu = (groupKey: ConsumerNavGroupKey, focusIndex: number | null = null) => {
    if (focusIndex !== null) {
      navGroupFocusIndexRef.current = { group: groupKey, index: focusIndex };
    } else {
      navGroupFocusIndexRef.current = null;
    }
    setOpenNavGroup(groupKey);
  };

  const toggleNavGroupMenu = (groupKey: ConsumerNavGroupKey) => {
    if (openNavGroup === groupKey) {
      closeNavGroupMenu({ returnFocus: true, group: groupKey });
      return;
    }
    openNavGroupMenu(groupKey, null);
  };

  const handleNavGroupButtonKeyDown = (
    event: React.KeyboardEvent<HTMLButtonElement>,
    groupKey: ConsumerNavGroupKey,
    itemCount: number,
  ) => {
    if (event.key === 'Enter' || event.key === ' ' || event.key === 'ArrowDown') {
      event.preventDefault();
      openNavGroupMenu(groupKey, 0);
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      openNavGroupMenu(groupKey, Math.max(itemCount - 1, 0));
    }
  };

  const handleNavGroupMenuKeyDown = (
    event: React.KeyboardEvent<HTMLDivElement>,
    groupKey: ConsumerNavGroupKey,
  ) => {
    const items = (navGroupItemRefs.current[groupKey] || []).filter(Boolean) as HTMLAnchorElement[];
    if (!items.length) return;

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
      closeNavGroupMenu({ returnFocus: true, group: groupKey });
    }
  };

  const submitStockSearch = () => {
    const validation = validateStockCode(stockSearchQuery);
    if (!validation.valid) {
      setStockSearchError(language === 'en' ? 'No matching stock route for that symbol format.' : '未找到可打开的标的路由，请检查代码格式。');
      setStockSearchFocused(true);
      return;
    }
    const target = routeLocale
      ? buildLocalizedPath(`/stocks/${encodeURIComponent(validation.normalized)}/structure-decision`, routeLocale)
      : `/stocks/${encodeURIComponent(validation.normalized)}/structure-decision`;
    setStockSearchError('');
    setStockSearchQuery('');
    setStockSearchFocused(false);
    navigate(target);
    onNavigate?.();
  };

  useEffect(() => {
    if (!showAdminMenu) {
      return undefined;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (adminMenuRef.current?.contains(event.target as Node)) {
        return;
      }
      setShowAdminMenu(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setShowAdminMenu(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [showAdminMenu]);

  useEffect(() => {
    if (!openNavGroup) {
      return undefined;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const menuRoot = navGroupMenuRefs.current[openNavGroup];
      if (menuRoot?.contains(event.target as Node)) {
        return;
      }
      closeNavGroupMenu({ returnFocus: true, group: openNavGroup });
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeNavGroupMenu({ returnFocus: true, group: openNavGroup });
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [openNavGroup]);

  useEffect(() => {
    if (!openNavGroup || !navGroupFocusIndexRef.current || navGroupFocusIndexRef.current.group !== openNavGroup) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      const focusTarget = navGroupFocusIndexRef.current;
      if (!focusTarget || focusTarget.group !== openNavGroup) return;
      navGroupItemRefs.current[openNavGroup]?.[focusTarget.index]?.focus();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [openNavGroup]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        stockSearchRef.current?.focus();
        setStockSearchFocused(true);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const renderDirectNavLink = (routeKey: CoreProductRouteKey) => {
    const route = getCoreProductRouteByKey(routeKey);
    const { key, labelKey, to, icon: Icon } = routeToNavItem(route);
    const label = t(labelKey || key);
    const linkTarget = routeLocale ? buildLocalizedPath(to, routeLocale) : to;
    const routeActive = currentConsumerRoute?.key === key;
    return (
      <Link
        key={key}
        to={linkTarget}
        onClick={handleConsumerNavigate}
        aria-label={label}
        aria-current={routeActive ? 'page' : undefined}
        className={cn(
          isDrawer
            ? 'shell-drawer-link'
            : 'shell-header-link text-sm transition-colors',
          !isDrawer && (routeActive
            ? 'font-bold'
            : 'font-medium'),
          routeActive ? 'is-active' : '',
        )}
      >
        {isDrawer ? (
          <span className="shell-nav-item__icon" aria-hidden="true">
            <Icon className="size-4" />
          </span>
        ) : null}
        <span className={isDrawer ? 'shell-nav-item__label' : 'shell-header-link__label'}>
          <NavLabel label={label} />
        </span>
      </Link>
    );
  };

  const renderGroupChildLink = (
    route: CoreProductRoute,
    groupKey: ConsumerNavGroupKey,
    index: number,
    options: { menuOpen: boolean; showAsDrawerChild: boolean; ownsAriaCurrent?: boolean },
  ) => {
    const { key, labelKey, to, icon: Icon } = routeToNavItem(route);
    const label = t(labelKey || key);
    const linkTarget = routeLocale ? buildLocalizedPath(to, routeLocale) : to;
    const routeActive = currentConsumerRoute?.key === key;
    const { menuOpen, showAsDrawerChild, ownsAriaCurrent = false } = options;

    return (
      <Link
        key={key}
        to={linkTarget}
        ref={(node) => {
          if (!navGroupItemRefs.current[groupKey]) {
            navGroupItemRefs.current[groupKey] = [];
          }
          navGroupItemRefs.current[groupKey]![index] = node;
        }}
        tabIndex={menuOpen || showAsDrawerChild ? 0 : -1}
        onClick={handleConsumerNavigate}
        aria-label={label}
        aria-current={ownsAriaCurrent && routeActive ? 'page' : undefined}
        data-current-child={routeActive ? 'true' : undefined}
        className={cn(
          showAsDrawerChild
            ? 'shell-drawer-action'
            : 'flex min-w-0 items-center gap-3 rounded-xl px-3 py-2 text-left text-sm text-[color:var(--wolfy-text-secondary)] transition-colors hover:bg-[var(--overlay-hover)] hover:text-[color:var(--wolfy-text-primary)]',
          routeActive ? 'is-active text-[color:var(--wolfy-text-primary)]' : '',
        )}
      >
        <span className={showAsDrawerChild ? 'shell-nav-item__icon' : 'inline-flex size-7 shrink-0 items-center justify-center rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]'} aria-hidden="true">
          <Icon className="size-4" />
        </span>
        <span className={showAsDrawerChild ? 'shell-nav-item__copy' : 'min-w-0 truncate'}>
          <span className={showAsDrawerChild ? 'shell-nav-item__label' : 'truncate'}>{label}</span>
        </span>
      </Link>
    );
  };

  const renderNavGroup = (groupKey: ConsumerNavGroupKey) => {
    const groupDef = CONSUMER_NAV_GROUPS.find((item) => item.key === groupKey);
    if (!groupDef) return null;
    const groupRoutes = getConsumerNavGroupRoutes(groupKey);
    const groupLabel = t(groupDef.labelKey);
    const groupActive = activeNavGroup === groupKey;
    const isOpen = openNavGroup === groupKey;
    const menuId = isDrawer ? `shell-nav-group-drawer-${groupKey}` : `shell-nav-group-header-${groupKey}`;
    const menuTestId = `shell-nav-group-menu-${groupKey}`;

    if (isDrawer) {
      // Mobile drawer: always expose grouped children so major tools stay discoverable.
      return (
        <div
          key={groupKey}
          className="space-y-2"
          data-testid={`shell-nav-group-${groupKey}`}
        >
          <div
            className={cn(
              'px-2 pt-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]',
              groupActive ? 'text-[color:var(--sage-deep)]' : '',
            )}
            data-testid={`shell-nav-group-label-${groupKey}`}
          >
            {groupLabel}
          </div>
          <div
            id={menuId}
            role="group"
            aria-label={groupLabel}
            data-testid={menuTestId}
            className="space-y-2 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-2"
          >
            {groupRoutes.map((route, index) => renderGroupChildLink(route, groupKey, index, {
              menuOpen: true,
              showAsDrawerChild: true,
              // Drawer has no group trigger: active child owns aria-current.
              ownsAriaCurrent: true,
            }))}
          </div>
        </div>
      );
    }

    return (
      <div
        key={groupKey}
        ref={(node) => {
          navGroupMenuRefs.current[groupKey] = node;
        }}
        className="relative"
        data-testid={`shell-nav-group-${groupKey}`}
      >
        <button
          ref={(node) => {
            navGroupButtonRefs.current[groupKey] = node;
          }}
          type="button"
          className={cn(
            'shell-header-link text-sm font-medium transition-colors',
            (isOpen || groupActive) ? 'is-active font-bold' : '',
          )}
          onClick={() => toggleNavGroupMenu(groupKey)}
          onKeyDown={(event) => handleNavGroupButtonKeyDown(event, groupKey, groupRoutes.length)}
          aria-haspopup="menu"
          aria-expanded={isOpen}
          aria-controls={menuId}
          aria-label={groupLabel}
          aria-current={groupActive ? 'page' : undefined}
          data-testid={`shell-nav-group-trigger-${groupKey}`}
        >
          <span className="shell-header-link__label inline-flex items-center gap-1.5">
            <span>{groupLabel}</span>
            <ChevronDown className={cn('size-3.5 transition-transform', isOpen ? 'rotate-180' : '')} />
          </span>
        </button>
        {isOpen ? (
          <div
            id={menuId}
            role="menu"
            data-testid={menuTestId}
            className="absolute left-0 top-full z-20 mt-2 flex min-w-[17rem] max-w-[min(24rem,calc(100vw-2rem))] flex-col gap-1 rounded-2xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--theme-floating-bg)] p-2 shadow-[var(--shadow-tight)]"
            onKeyDown={(event) => handleNavGroupMenuKeyDown(event, groupKey)}
          >
            {groupRoutes.map((route, index) => renderGroupChildLink(route, groupKey, index, {
              menuOpen: isOpen,
              showAsDrawerChild: false,
              // Desktop: group trigger owns aria-current; child uses is-active only.
              ownsAriaCurrent: false,
            }))}
          </div>
        ) : null}
      </div>
    );
  };

  const consumerNavItems = CONSUMER_NAV_ARCHITECTURE.map((item) => {
    if (item.type === 'link') {
      return renderDirectNavLink(item.routeKey);
    }
    return renderNavGroup(item.groupKey);
  });

  const adminNavLinks = adminNavItems.map((item) => {
    const { key, label, to, icon: Icon } = item;
    const routeActive = adminNavItemMatchesPath(location.pathname, item);

    return (
      <NavLink
        key={key}
        to={to}
        onClick={handleAdminNavigate}
        onFocus={(event) => {
          if (!isDrawer) {
            event.currentTarget.scrollIntoView({ block: 'nearest', inline: 'center' });
          }
        }}
        aria-label={label}
        aria-current={routeActive ? 'page' : undefined}
        className={({ isActive }) => cn(
          isDrawer
            ? 'shell-drawer-link'
            : 'shell-header-link text-sm transition-colors',
          !isDrawer && ((isActive || routeActive)
            ? 'font-bold'
            : 'font-medium'),
          (isActive || routeActive) ? 'is-active' : '',
        )}
      >
        {isDrawer ? (
          <span className="shell-nav-item__icon" aria-hidden="true">
            <Icon className="size-4" />
          </span>
        ) : null}
        <span className={isDrawer ? 'shell-nav-item__label' : 'shell-header-link__label'}>
          <NavLabel label={label} />
        </span>
      </NavLink>
    );
  });
  const primaryNavLinks = showAdminPrimaryNav ? adminNavLinks : consumerNavItems;
  const primaryNavLabel = showAdminPrimaryNav ? adminNavCopy.menuLabel : t('shell.drawerTitle');
  const primaryNavTestId = showAdminPrimaryNav ? 'shell-admin-primary-nav' : 'shell-consumer-primary-nav';

  const trimmedStockSearchQuery = stockSearchQuery.trim();
  const stockSearchValidation = trimmedStockSearchQuery ? validateStockCode(trimmedStockSearchQuery) : null;
  const stockSearchHasResult = Boolean(stockSearchValidation?.valid);
  const stockSearchStatusText = !trimmedStockSearchQuery
    ? (language === 'en' ? 'Type a known symbol.' : '输入已知股票代码。')
    : stockSearchHasResult
      ? (language === 'en'
        ? `Open ${stockSearchValidation?.normalized} in Stock Research.`
        : `打开 ${stockSearchValidation?.normalized} 的个股研究。`)
      : stockSearchError || (language === 'en' ? 'No route-ready result for this symbol.' : '没有可打开的标的结果。');
  const stockSearchControl = (
    <form
      role="search"
      aria-label={language === 'en' ? 'Open stock research by symbol' : '按股票代码打开个股研究'}
      className={cn('shell-stock-search', isDrawer ? 'shell-stock-search--drawer' : 'shell-stock-search--header')}
      data-search-state={!trimmedStockSearchQuery ? 'idle' : stockSearchHasResult ? 'ready' : 'no-results'}
      onSubmit={(event) => {
        event.preventDefault();
        submitStockSearch();
      }}
      noValidate
    >
      <label htmlFor={stockSearchId} className="shell-stock-search__label">
        {language === 'en' ? 'Stock' : '个股'}
      </label>
      <div className="shell-stock-search__field">
        <Search className="shell-stock-search__icon" aria-hidden="true" />
        <input
          ref={stockSearchRef}
          id={stockSearchId}
          value={stockSearchQuery}
          className="shell-stock-search__input"
          onChange={(event) => {
            setStockSearchQuery(event.target.value);
            if (stockSearchError) setStockSearchError('');
            setStockSearchFocused(true);
          }}
          onFocus={() => setStockSearchFocused(true)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.preventDefault();
              setStockSearchFocused(false);
              setStockSearchError('');
              stockSearchRef.current?.blur();
            }
          }}
          placeholder={language === 'en' ? 'AAPL / 600519 / 0700.HK' : 'AAPL / 600519 / 0700.HK'}
          aria-describedby={`${stockSearchId}-status`}
          aria-invalid={Boolean(trimmedStockSearchQuery && !stockSearchHasResult)}
        />
      </div>
      <div id={`${stockSearchId}-status`} className="sr-only" aria-live="polite">
        {stockSearchStatusText}
      </div>
      {stockSearchFocused && trimmedStockSearchQuery ? (
        <div className="shell-stock-search__popover" data-testid="shell-stock-search-popover">
          {stockSearchHasResult && stockSearchValidation ? (
            <button
              type="button"
              className="shell-stock-search__result"
              onMouseDown={(event) => event.preventDefault()}
              onClick={submitStockSearch}
            >
              <span className="min-w-0">
                <span className="block truncate font-semibold">
                  {language === 'en' ? `Open ${stockSearchValidation.normalized}` : `打开 ${stockSearchValidation.normalized}`}
                </span>
                <span className="block truncate text-[11px] text-[color:var(--wolfy-text-muted)]">
                  {inferSymbolMarketContext(stockSearchValidation.normalized, language)}
                </span>
              </span>
              <ArrowRight className="size-4 shrink-0" aria-hidden="true" />
            </button>
          ) : (
            <p className="shell-stock-search__empty" role="status">
              {stockSearchStatusText}
            </p>
          )}
        </div>
      ) : null}
    </form>
  );

  const archiveAction = !isGuest && hasArchive ? (
    <button
      type="button"
      className={isDrawer ? 'shell-nav-item shell-nav-item--utility' : HEADER_UTILITY_TEXT_CLASS}
      onClick={() => {
        onOpenArchive?.();
        onNavigate?.();
      }}
      aria-label={t('shell.archiveTitle')}
    >
      {isDrawer ? (
        <>
          <span className="shell-nav-item__icon" aria-hidden="true">
            <Archive className="size-4" />
          </span>
          <DrawerUtilityLabel label={t('shell.archiveTitle')} />
        </>
      ) : (
        <span>{t('shell.archiveShort')}</span>
      )}
    </button>
  ) : null;

  const languageAction = (
    <button
      type="button"
      className={isDrawer ? 'shell-nav-item shell-nav-item--utility' : HEADER_UTILITY_TEXT_CLASS}
      onClick={() => {
        toggleLanguage();
        onNavigate?.();
      }}
      aria-label={t('language.toggle')}
    >
      {isDrawer ? (
        <>
          <span className="shell-nav-item__icon" aria-hidden="true">
            <Globe className="size-4" />
          </span>
          <DrawerUtilityLabel
            label={t('language.toggle')}
            value={language === 'zh' ? t('language.zh') : t('language.en')}
          />
        </>
      ) : (
        <span>{language === 'zh' ? 'EN' : 'ZH'}</span>
      )}
    </button>
  );

  const nextColorMode = colorMode === 'dark' ? 'light' : 'dark';
  const ThemeIcon = colorMode === 'dark' ? Sun : Moon;
  const currentThemeLabel = colorMode === 'light'
    ? t('theme.paper')
    : (language === 'en' ? 'Ink' : '墨色');
  const themeAction = (
    <button
      type="button"
      className={isDrawer ? 'shell-nav-item shell-nav-item--utility' : HEADER_UTILITY_TEXT_CLASS}
      onClick={() => setColorMode(nextColorMode)}
      aria-label={t('theme.label')}
      aria-pressed={colorMode === 'light'}
      data-theme-mode={colorMode}
      title={t('theme.label')}
    >
      {isDrawer ? (
        <>
          <span className="shell-nav-item__icon" aria-hidden="true">
            <ThemeIcon className="size-4" />
          </span>
          <DrawerUtilityLabel
            label={t('theme.label')}
            value={!isGuest ? currentThemeLabel : undefined}
          />
        </>
      ) : (
        <span className="inline-flex items-center gap-1.5">
          <ThemeIcon className="size-3.5" aria-hidden="true" />
          {!isGuest ? <span>{currentThemeLabel}</span> : null}
        </span>
      )}
    </button>
  );

  const settingsPath = routeLocale ? buildLocalizedPath('/settings', routeLocale) : '/settings';
  const personalSettingsActive = stripLocalePrefix(location.pathname) === '/settings';
  const settingsAction = !isGuest ? (
    <Link
      to={settingsPath}
      onClick={onNavigate}
      className={cn(
        isDrawer ? 'shell-drawer-action' : HEADER_UTILITY_TEXT_CLASS,
        !isDrawer && personalSettingsActive ? 'is-active' : '',
        isDrawer && personalSettingsActive ? 'is-active' : '',
      )}
      aria-label={t('nav.settings')}
      aria-current={personalSettingsActive ? 'page' : undefined}
    >
      {isDrawer ? (
        <>
          <span className="shell-nav-item__icon" aria-hidden="true">
            <Settings2 className="size-4" />
          </span>
          <DrawerUtilityLabel label={t('nav.settings')} />
        </>
      ) : (
        <span>{t('nav.settings')}</span>
      )}
    </Link>
  ) : null;

  const adminMenuAction = hasAdminMenu && !showAdminPrimaryNav ? (
    isDrawer ? (
      <div className="space-y-2">
        <button
          type="button"
          className="shell-nav-item shell-nav-item--utility w-full"
          onClick={() => setShowAdminMenu((open) => !open)}
          aria-expanded={showAdminMenu}
          aria-controls="shell-admin-utility-menu"
        >
          <span className="shell-nav-item__icon" aria-hidden="true">
            <ShieldCheck className="size-4" />
          </span>
          <DrawerUtilityLabel label={consoleLabel} />
          <ChevronDown className={cn('ml-auto size-4 text-[color:var(--wolfy-text-muted)] transition-transform', showAdminMenu ? 'rotate-180' : '')} />
        </button>
        {showAdminMenu ? (
          <div
            id="shell-admin-utility-menu"
            data-testid="shell-admin-utility-menu"
            className="space-y-2 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]/60 p-2"
          >
            {adminNavGroups.map((group) => (
              <div key={group.key} data-testid={`shell-admin-utility-group-${group.key}`} className="space-y-1">
                <p className="px-2 text-[10px] font-semibold uppercase tracking-normal text-[color:var(--wolfy-text-muted)]">{group.label}</p>
                {group.items.map((item) => {
                  const { key, label, to, icon: Icon } = item;
                  const routeActive = adminNavItemMatchesPath(location.pathname, item);
                  return (
                    <NavLink
                      key={key}
                      to={to}
                      onClick={handleAdminNavigate}
                      className={({ isActive }) => cn('shell-drawer-action', (isActive || routeActive) ? 'is-active' : '')}
                      aria-label={label}
                      aria-current={routeActive ? 'page' : undefined}
                    >
                      <span className="shell-nav-item__icon" aria-hidden="true">
                        <Icon className="size-4" />
                      </span>
                      <DrawerUtilityLabel label={label} />
                    </NavLink>
                  );
                })}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    ) : (
      <div ref={adminMenuRef} className="relative">
        <button
          type="button"
          className={cn(HEADER_UTILITY_TEXT_CLASS, showAdminMenu ? 'is-active' : '')}
          onClick={() => setShowAdminMenu((open) => !open)}
          aria-expanded={showAdminMenu}
          aria-controls="shell-admin-utility-menu"
        >
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheck className="size-3.5" />
            <span>{consoleLabel}</span>
            <ChevronDown className={cn('size-3.5 transition-transform', showAdminMenu ? 'rotate-180' : '')} />
          </span>
        </button>
        {showAdminMenu ? (
          <div
            id="shell-admin-utility-menu"
            role="menu"
            data-testid="shell-admin-utility-menu"
            className="absolute right-0 top-full z-20 mt-2 flex min-w-[17rem] max-w-[min(24rem,calc(100vw-2rem))] flex-col gap-2 rounded-2xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--theme-floating-bg)] p-2 shadow-[var(--shadow-tight)]"
          >
            {adminNavGroups.map((group) => (
              <div key={group.key} data-testid={`shell-admin-utility-group-${group.key}`} className="space-y-1">
                <p className="px-2 text-[10px] font-semibold uppercase tracking-normal text-[color:var(--wolfy-text-muted)]">{group.label}</p>
                {group.items.map((item) => {
                  const { key, label, to, icon: Icon } = item;
                  const routeActive = adminNavItemMatchesPath(location.pathname, item);
                  return (
                    <NavLink
                      key={key}
                      to={to}
                      onClick={handleAdminNavigate}
                      className={({ isActive }) => cn(
                        'flex min-w-0 items-center gap-3 rounded-xl px-3 py-2 text-left text-sm text-[color:var(--wolfy-text-secondary)] transition-colors hover:bg-[var(--overlay-hover)] hover:text-[color:var(--wolfy-text-primary)]',
                        (isActive || routeActive) ? 'bg-[var(--overlay-selected)] text-[color:var(--wolfy-text-primary)]' : '',
                      )}
                      aria-label={label}
                      aria-current={routeActive ? 'page' : undefined}
                    >
                      <Icon className="size-4 shrink-0 text-[color:var(--wolfy-text-muted)]" />
                      <span className="truncate">{label}</span>
                    </NavLink>
                  );
                })}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    )
  ) : null;

  const signInAction = authEnabled && isGuest ? (
    <NavLink
      to={signInPath}
      onClick={onNavigate}
      className={({ isActive }) => cn(
        isDrawer ? 'shell-drawer-action shell-drawer-action--primary' : HEADER_UTILITY_TEXT_CLASS,
        !isDrawer && isActive ? 'is-active' : '',
        isDrawer && isActive ? 'is-active' : '',
      )}
      aria-label={signInLabel}
    >
      {isDrawer ? (
        <>
          <span className="shell-nav-item__icon" aria-hidden="true">
            <LogIn className="size-4" />
          </span>
          <DrawerUtilityLabel label={signInLabel} />
        </>
      ) : (
        <span>{signInLabel}</span>
      )}
    </NavLink>
  ) : null;

  const logoutAction = !isGuest ? (
    <button
      type="button"
      className={isDrawer ? 'shell-nav-item shell-nav-item--utility shell-nav-item--danger' : HEADER_UTILITY_DANGER_TEXT_CLASS}
      onClick={() => setShowLogoutConfirm(true)}
      aria-label={t('nav.logout')}
    >
      {isDrawer ? (
        <>
          <span className="shell-nav-item__icon" aria-hidden="true">
            <LogOut className="size-4" />
          </span>
          <DrawerUtilityLabel label={t('nav.logout')} />
        </>
      ) : (
        <span>{t('nav.logout')}</span>
      )}
    </button>
  ) : null;

  const navBody = isDrawer ? (
    <div className="shell-drawer-nav">
      <div className="shell-drawer-brand">
        <BrandWordmark onNavigate={onNavigate} />
        <span className="shell-drawer-note">{t('nav.terminal')}</span>
      </div>
      <nav className="shell-drawer-links" aria-label={primaryNavLabel} data-testid={primaryNavTestId}>
        {primaryNavLinks}
      </nav>
      <div className="shell-drawer-footer">
        {stockSearchControl}
        {archiveAction}
        {languageAction}
        {themeAction}
        {settingsAction}
        {adminMenuAction}
        {signInAction}
        {logoutAction}
      </div>
    </div>
  ) : (
    <div className="shell-header-nav">
      <div className="shell-header-brand">
        <BrandWordmark />
      </div>
      <nav
        className="shell-header-links"
        aria-label={primaryNavLabel}
        data-testid={primaryNavTestId}
        tabIndex={showAdminPrimaryNav ? 0 : undefined}
      >
        {primaryNavLinks}
      </nav>
      <div className="shell-header-utilities">
        {archiveAction}
        <div
          data-testid="shell-header-utility-island"
          className="flex items-center gap-0.5 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-1.5 py-1"
        >
          {stockSearchControl}
          {languageAction}
          {themeAction}
          {(settingsAction || adminMenuAction || signInAction || logoutAction) ? (
            <div className="h-3 w-px bg-[var(--wolfy-divider)]" data-testid="shell-header-utility-divider" />
          ) : null}
          {settingsAction}
          {adminMenuAction}
          {signInAction}
          {logoutAction && (settingsAction || adminMenuAction || signInAction) ? (
            <div className="h-3 w-px bg-[var(--wolfy-divider)]" data-testid="shell-header-utility-divider" />
          ) : null}
          {logoutAction}
        </div>
      </div>
    </div>
  );

  const confirmDialog = (
    <ConfirmDialog
      isOpen={showLogoutConfirm}
      title={t('nav.logoutTitle')}
      message={t('nav.logoutMessage')}
      confirmText={t('nav.logoutConfirm')}
      cancelText={t('nav.logoutCancel')}
      isDanger
      onConfirm={() => {
        setShowLogoutConfirm(false);
        onNavigate?.();
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
  );

  return { navBody, confirmDialog };
}

export const SidebarNav: React.FC<SidebarNavProps> = (props) => {
  const { navBody, confirmDialog } = useSidebarNavView(props);

  return (
    <>
      {navBody}
      {confirmDialog}
    </>
  );
};
