/**
 * WolfyStock shell phase 1 preserves routing, archive access, language
 * toggling and logout confirmation while aligning nav
 * controls to the shared Linear OS tokens.
 */
import React, { useEffect, useRef, useState } from 'react';
import {
  Archive,
  Activity,
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
  Home,
  LogIn,
  LogOut,
  Radar,
  ListChecks,
  Settings2,
  ShieldCheck,
  TestTubeDiagonal,
  UsersRound,
  Waves,
} from 'lucide-react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useI18n } from '../../contexts/UiLanguageContext';
import { buildLoginPath, useProductSurface } from '../../hooks/useProductSurface';
import { cn } from '../../utils/cn';
import { buildLocalizedPath, parseLocaleFromPathname, stripLocalePrefix } from '../../utils/localeRouting';
import { BrandLogo, BRAND_WORDMARK_CLASSNAME } from '../common/BrandLogo';
import { ConfirmDialog } from '../common/ConfirmDialog';

type SidebarNavProps = {
  layout?: 'header' | 'drawer';
  onNavigate?: () => void;
  onOpenArchive?: () => void;
  hasArchive?: boolean;
};

type NavItem = {
  key: string;
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
  <NavLink
    to="/"
    end
    onClick={onNavigate}
    aria-label="WolfyStock"
    className={({ isActive }) => cn('shell-brand-link', className || '', isActive ? 'is-active' : '')}
  >
    <span className="inline-flex min-w-0 items-center gap-3">
      <BrandLogo className="size-8" />
      <span className={`shell-wordmark ${BRAND_WORDMARK_CLASSNAME}`}>WolfyStock</span>
    </span>
  </NavLink>
);

const NAV_ITEMS: NavItem[] = [
  { key: 'home', labelKey: 'nav.home', to: '/', icon: Home },
  { key: 'scanner', labelKey: 'nav.scanner', to: '/scanner', icon: Radar },
  { key: 'portfolio', labelKey: 'nav.portfolio', to: '/portfolio', icon: BriefcaseBusiness },
  { key: 'market-overview', labelKey: 'nav.marketOverview', to: '/market-overview', icon: Activity },
  { key: 'liquidity-monitor', labelKey: 'nav.liquidityMonitor', to: '/market/liquidity-monitor', icon: Gauge },
  { key: 'rotation-radar', labelKey: 'nav.rotationRadar', to: '/market/rotation-radar', icon: Waves },
  { key: 'watchlist', labelKey: 'nav.watchlist', to: '/watchlist', icon: ListChecks },
  { key: 'backtest', labelKey: 'nav.backtest', to: '/backtest', icon: TestTubeDiagonal },
  { key: 'options-lab', labelKey: 'nav.optionsLab', to: '/options-lab', icon: FlaskConical },
];

const HEADER_UTILITY_TEXT_CLASS = 'px-2.5 py-1 text-[11px] font-medium text-white/42 transition-colors hover:text-white/78';
const HEADER_UTILITY_DANGER_TEXT_CLASS = 'px-2.5 py-1 text-[11px] font-medium text-white/38 transition-colors hover:text-red-300/90';
const ADMIN_NAV_GROUP_ORDER: AdminNavGroupKey[] = ['trust', 'evidence', 'dataOps', 'support'];

function isAdminOpsRoute(pathname: string): boolean {
  const routePathname = stripLocalePrefix(pathname);
  return routePathname.startsWith('/settings/system')
    || routePathname.startsWith('/admin/logs')
    || routePathname.startsWith('/admin/evidence-workflow')
    || routePathname.startsWith('/admin/notifications')
    || routePathname.startsWith('/admin/market-providers')
    || routePathname.startsWith('/admin/provider-circuits')
    || routePathname.startsWith('/admin/users')
    || routePathname.startsWith('/admin/cost-observability');
}

function resolveAdminNavCopy(language: string): AdminNavCopy {
  if (language === 'en') {
    return {
      menuLabel: 'Admin/Ops navigation',
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
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [showAdminMenu, setShowAdminMenu] = useState(false);
  const adminMenuRef = useRef<HTMLDivElement | null>(null);
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const adminNavCopy = resolveAdminNavCopy(language);
  const isAdminRoute = isAdminOpsRoute(location.pathname);
  const isDrawer = layout === 'drawer';
  const signInLabel = t('nav.signIn');
  const consoleLabel = t('nav.independentConsole');
  const signInPath = buildLoginPath(location.pathname + location.search);
  const consolePath = routeLocale ? buildLocalizedPath('/settings/system', routeLocale) : '/settings/system';
  const adminLogsPath = routeLocale ? buildLocalizedPath('/admin/logs', routeLocale) : '/admin/logs';
  const evidenceWorkflowPath = routeLocale ? buildLocalizedPath('/admin/evidence-workflow', routeLocale) : '/admin/evidence-workflow';
  const notificationsPath = routeLocale ? buildLocalizedPath('/admin/notifications', routeLocale) : '/admin/notifications';
  const marketProvidersPath = routeLocale ? buildLocalizedPath('/admin/market-providers', routeLocale) : '/admin/market-providers';
  const providerCircuitsPath = routeLocale ? buildLocalizedPath('/admin/provider-circuits', routeLocale) : '/admin/provider-circuits';
  const userGovernancePath = routeLocale ? buildLocalizedPath('/admin/users', routeLocale) : '/admin/users';
  const costObservabilityPath = routeLocale ? buildLocalizedPath('/admin/cost-observability', routeLocale) : '/admin/cost-observability';
  const adminNavItems: AdminNavItem[] = [];
  if (canReadSystemConfig) {
    adminNavItems.push({ key: 'system', label: adminNavCopy.system, to: consolePath, icon: ShieldCheck, group: 'trust' });
  }
  if (canReadOpsLogs) {
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
  const showAdminPrimaryNav = isAdminRoute;

  const handleAdminNavigate = () => {
    setShowAdminMenu(false);
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

  const navLinks = NAV_ITEMS.map(({ key, labelKey, label: fixedLabel, to, icon: Icon }) => {
    const label = fixedLabel ?? t(labelKey || key);
    const linkTarget = routeLocale ? buildLocalizedPath(to, routeLocale) : to;
    return (
      <NavLink
        key={key}
        to={linkTarget}
        end={to === '/'}
        onClick={onNavigate}
        aria-label={label}
        className={({ isActive }) => cn(
          isDrawer
            ? 'shell-drawer-link'
            : 'shell-header-link text-sm transition-colors',
          !isDrawer && (isActive
            ? 'font-bold text-white'
            : 'font-medium text-white/50 hover:text-white'),
          isActive ? 'is-active' : '',
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

  const adminNavLinks = adminNavItems.map(({ key, label, to, icon: Icon }) => (
    <NavLink
      key={key}
      to={to}
      end={key === 'system'}
      onClick={handleAdminNavigate}
      aria-label={label}
      className={({ isActive }) => cn(
        isDrawer
          ? 'shell-drawer-link'
          : 'shell-header-link text-sm transition-colors',
        !isDrawer && (isActive
          ? 'font-bold text-white'
          : 'font-medium text-white/50 hover:text-white'),
        isActive ? 'is-active' : '',
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
  ));
  const primaryNavLinks = showAdminPrimaryNav ? adminNavLinks : navLinks;
  const primaryNavLabel = showAdminPrimaryNav ? adminNavCopy.menuLabel : t('shell.drawerTitle');
  const primaryNavTestId = showAdminPrimaryNav ? 'shell-admin-primary-nav' : 'shell-consumer-primary-nav';

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

  const settingsAction = !isGuest ? (
    <NavLink
      to="/settings"
      onClick={onNavigate}
      className={({ isActive }) => cn(
        isDrawer ? 'shell-drawer-action' : HEADER_UTILITY_TEXT_CLASS,
        !isDrawer && isActive ? 'text-white' : '',
        isDrawer && isActive ? 'is-active' : '',
      )}
      aria-label={t('nav.settings')}
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
    </NavLink>
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
          <ChevronDown className={cn('ml-auto size-4 text-white/48 transition-transform', showAdminMenu ? 'rotate-180' : '')} />
        </button>
        {showAdminMenu ? (
          <div
            id="shell-admin-utility-menu"
            data-testid="shell-admin-utility-menu"
            className="space-y-2 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]/60 p-2"
          >
            {adminNavGroups.map((group) => (
              <div key={group.key} data-testid={`shell-admin-utility-group-${group.key}`} className="space-y-1">
                <p className="px-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/36">{group.label}</p>
                {group.items.map(({ key, label, to, icon: Icon }) => (
                  <NavLink
                    key={key}
                    to={to}
                    onClick={handleAdminNavigate}
                    className={({ isActive }) => cn('shell-drawer-action', isActive ? 'is-active' : '')}
                    aria-label={label}
                  >
                    <span className="shell-nav-item__icon" aria-hidden="true">
                      <Icon className="size-4" />
                    </span>
                    <DrawerUtilityLabel label={label} />
                  </NavLink>
                ))}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    ) : (
      <div ref={adminMenuRef} className="relative">
        <button
          type="button"
          className={cn(HEADER_UTILITY_TEXT_CLASS, showAdminMenu ? 'text-white' : '')}
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
            className="absolute right-0 top-full z-20 mt-2 flex min-w-[17rem] max-w-[min(24rem,calc(100vw-2rem))] flex-col gap-2 rounded-2xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-2 shadow-[0_20px_48px_rgba(0,0,0,0.28)]"
          >
            {adminNavGroups.map((group) => (
              <div key={group.key} data-testid={`shell-admin-utility-group-${group.key}`} className="space-y-1">
                <p className="px-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-white/34">{group.label}</p>
                {group.items.map(({ key, label, to, icon: Icon }) => (
                  <NavLink
                    key={key}
                    to={to}
                    onClick={handleAdminNavigate}
                    className={({ isActive }) => cn(
                      'flex min-w-0 items-center gap-3 rounded-xl px-3 py-2 text-left text-sm text-white/72 transition-colors hover:bg-white/[0.04] hover:text-white',
                      isActive ? 'bg-white/[0.05] text-white' : '',
                    )}
                    aria-label={label}
                  >
                    <Icon className="size-4 shrink-0 text-white/56" />
                    <span className="truncate">{label}</span>
                  </NavLink>
                ))}
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
        !isDrawer && isActive ? 'text-white' : '',
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
        {archiveAction}
        {languageAction}
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
      <nav className="shell-header-links" aria-label={primaryNavLabel} data-testid={primaryNavTestId}>
        {primaryNavLinks}
      </nav>
      <div className="shell-header-utilities">
        {archiveAction}
        <div
          data-testid="shell-header-utility-island"
          className="flex items-center gap-0.5 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-rail)] px-1.5 py-1"
        >
          {languageAction}
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
