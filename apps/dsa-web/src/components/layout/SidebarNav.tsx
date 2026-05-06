/**
 * WolfyStock shell phase 1 preserves routing, archive access, language
 * toggling, completion badge, and logout confirmation while aligning nav
 * controls to the shared glass tokens.
 */
import React, { useState } from 'react';
import {
  Archive,
  Activity,
  BellRing,
  BriefcaseBusiness,
  BarChart3,
  DatabaseZap,
  FlaskConical,
  Globe,
  Home,
  LogIn,
  LogOut,
  MessageSquareText,
  Radar,
  ListChecks,
  Settings2,
  ShieldCheck,
  TestTubeDiagonal,
  UsersRound,
} from 'lucide-react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useI18n } from '../../contexts/UiLanguageContext';
import { buildLoginPath, useProductSurface } from '../../hooks/useProductSurface';
import { useAgentChatStore } from '../../stores/agentChatStore';
import { cn } from '../../utils/cn';
import { buildLocalizedPath, parseLocaleFromPathname } from '../../utils/localeRouting';
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
  labelKey: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: 'completion';
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
      <BrandLogo className="h-8 w-8" />
      <span className={`shell-wordmark ${BRAND_WORDMARK_CLASSNAME}`}>WolfyStock</span>
    </span>
  </NavLink>
);

const NAV_ITEMS: NavItem[] = [
  { key: 'home', labelKey: 'nav.home', to: '/', icon: Home },
  { key: 'scanner', labelKey: 'nav.scanner', to: '/scanner', icon: Radar },
  { key: 'chat', labelKey: 'nav.chat', to: '/chat', icon: MessageSquareText, badge: 'completion' },
  { key: 'portfolio', labelKey: 'nav.portfolio', to: '/portfolio', icon: BriefcaseBusiness },
  { key: 'market-overview', labelKey: 'nav.marketOverview', to: '/market-overview', icon: Activity },
  { key: 'watchlist', labelKey: 'nav.watchlist', to: '/watchlist', icon: ListChecks },
  { key: 'backtest', labelKey: 'nav.backtest', to: '/backtest', icon: TestTubeDiagonal },
  { key: 'options-lab', labelKey: 'nav.optionsLab', to: '/options-lab', icon: FlaskConical },
];

const HEADER_UTILITY_TEXT_CLASS = 'px-3 py-1 text-xs font-medium text-white/50 transition-colors hover:text-white';
const HEADER_UTILITY_DANGER_TEXT_CLASS = 'px-3 py-1 text-xs font-medium text-white/50 transition-colors hover:text-red-400';

function NavLabel({
  label,
  showBadge,
}: {
  label: string;
  showBadge: boolean;
}) {
  return (
    <span className="relative inline-flex min-w-0 items-center gap-2">
      <span>{label}</span>
      {showBadge ? (
        <span
          data-testid="chat-completion-badge"
          className="shell-nav-dot"
          aria-label={label}
        />
      ) : null}
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

export const SidebarNav: React.FC<SidebarNavProps> = ({
  layout = 'header',
  onNavigate,
  onOpenArchive,
  hasArchive = false,
}) => {
  const location = useLocation();
  const { authEnabled, logout } = useAuth();
  const {
    isGuest,
    canReadCostObservability,
    canReadNotifications,
    canReadProviders,
    canReadSystemConfig,
    canReadUsers,
  } = useProductSurface();
  const { language, t, toggleLanguage } = useI18n();
  const completionBadge = useAgentChatStore((state) => state.completionBadge);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const isDrawer = layout === 'drawer';
  const signInLabel = t('nav.signIn');
  const consoleLabel = t('nav.independentConsole');
  const notificationsLabel = t('nav.notifications');
  const marketProvidersLabel = t('nav.marketProviders');
  const userGovernanceLabel = t('nav.userGovernance');
  const costObservabilityLabel = t('nav.costObservability');
  const signInPath = buildLoginPath(location.pathname + location.search);
  const consolePath = routeLocale ? buildLocalizedPath('/settings/system', routeLocale) : '/settings/system';
  const notificationsPath = routeLocale ? buildLocalizedPath('/admin/notifications', routeLocale) : '/admin/notifications';
  const marketProvidersPath = routeLocale ? buildLocalizedPath('/admin/market-providers', routeLocale) : '/admin/market-providers';
  const userGovernancePath = routeLocale ? buildLocalizedPath('/admin/users', routeLocale) : '/admin/users';
  const costObservabilityPath = routeLocale ? buildLocalizedPath('/admin/cost-observability', routeLocale) : '/admin/cost-observability';

  const navLinks = NAV_ITEMS.map(({ key, labelKey, to, icon: Icon, badge }) => {
    const label = t(labelKey);
    return (
      <NavLink
        key={key}
        to={to}
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
            <Icon className="h-4 w-4" />
          </span>
        ) : null}
        <span className={isDrawer ? 'shell-nav-item__label' : 'shell-header-link__label'}>
          <NavLabel label={label} showBadge={badge === 'completion' && completionBadge} />
        </span>
      </NavLink>
    );
  });

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
            <Archive className="h-4 w-4" />
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
            <Globe className="h-4 w-4" />
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
            <Settings2 className="h-4 w-4" />
          </span>
          <DrawerUtilityLabel label={t('nav.settings')} />
        </>
      ) : (
        <span>{t('nav.settings')}</span>
      )}
    </NavLink>
  ) : null;

  const systemAction = canReadSystemConfig ? (
    <NavLink
      to={consolePath}
      onClick={onNavigate}
      className={({ isActive }) => cn(
        isDrawer ? 'shell-drawer-action' : HEADER_UTILITY_TEXT_CLASS,
        !isDrawer && isActive ? 'text-white' : '',
        isDrawer && isActive ? 'is-active' : '',
      )}
      aria-label={consoleLabel}
    >
      {isDrawer ? (
        <>
          <span className="shell-nav-item__icon" aria-hidden="true">
            <ShieldCheck className="h-4 w-4" />
          </span>
          <DrawerUtilityLabel label={consoleLabel} />
        </>
      ) : (
        <span>{consoleLabel}</span>
      )}
    </NavLink>
  ) : null;

  const notificationAction = canReadNotifications ? (
    <NavLink
      to={notificationsPath}
      onClick={onNavigate}
      className={({ isActive }) => cn(
        isDrawer ? 'shell-drawer-action' : HEADER_UTILITY_TEXT_CLASS,
        !isDrawer && isActive ? 'text-white' : '',
        isDrawer && isActive ? 'is-active' : '',
      )}
      aria-label={notificationsLabel}
    >
      {isDrawer ? (
        <>
          <span className="shell-nav-item__icon" aria-hidden="true">
            <BellRing className="h-4 w-4" />
          </span>
          <DrawerUtilityLabel label={notificationsLabel} />
        </>
      ) : (
        <span>{notificationsLabel}</span>
      )}
    </NavLink>
  ) : null;

  const marketProviderAction = canReadProviders ? (
    <NavLink
      to={marketProvidersPath}
      onClick={onNavigate}
      className={({ isActive }) => cn(
        isDrawer ? 'shell-drawer-action' : HEADER_UTILITY_TEXT_CLASS,
        !isDrawer && isActive ? 'text-white' : '',
        isDrawer && isActive ? 'is-active' : '',
      )}
      aria-label={marketProvidersLabel}
    >
      {isDrawer ? (
        <>
          <span className="shell-nav-item__icon" aria-hidden="true">
            <DatabaseZap className="h-4 w-4" />
          </span>
          <DrawerUtilityLabel label={marketProvidersLabel} />
        </>
      ) : (
        <span>{marketProvidersLabel}</span>
      )}
    </NavLink>
  ) : null;

  const userGovernanceAction = canReadUsers ? (
    <NavLink
      to={userGovernancePath}
      onClick={onNavigate}
      className={({ isActive }) => cn(
        isDrawer ? 'shell-drawer-action' : HEADER_UTILITY_TEXT_CLASS,
        !isDrawer && isActive ? 'text-white' : '',
        isDrawer && isActive ? 'is-active' : '',
      )}
      aria-label={userGovernanceLabel}
    >
      {isDrawer ? (
        <>
          <span className="shell-nav-item__icon" aria-hidden="true">
            <UsersRound className="h-4 w-4" />
          </span>
          <DrawerUtilityLabel label={userGovernanceLabel} />
        </>
      ) : (
        <span>{userGovernanceLabel}</span>
      )}
    </NavLink>
  ) : null;

  const costObservabilityAction = canReadCostObservability ? (
    <NavLink
      to={costObservabilityPath}
      onClick={onNavigate}
      className={({ isActive }) => cn(
        isDrawer ? 'shell-drawer-action' : HEADER_UTILITY_TEXT_CLASS,
        !isDrawer && isActive ? 'text-white' : '',
        isDrawer && isActive ? 'is-active' : '',
      )}
      aria-label={costObservabilityLabel}
    >
      {isDrawer ? (
        <>
          <span className="shell-nav-item__icon" aria-hidden="true">
            <BarChart3 className="h-4 w-4" />
          </span>
          <DrawerUtilityLabel label={costObservabilityLabel} />
        </>
      ) : (
        <span>{costObservabilityLabel}</span>
      )}
    </NavLink>
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
            <LogIn className="h-4 w-4" />
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
            <LogOut className="h-4 w-4" />
          </span>
          <DrawerUtilityLabel label={t('nav.logout')} />
        </>
      ) : (
        <span>{t('nav.logout')}</span>
      )}
    </button>
  ) : null;

  return (
    <>
      {isDrawer ? (
        <div className="shell-drawer-nav">
          <div className="shell-drawer-brand">
            <BrandWordmark onNavigate={onNavigate} />
            <span className="shell-drawer-note">{t('nav.terminal')}</span>
          </div>
          <nav className="shell-drawer-links" aria-label={t('shell.drawerTitle')}>
            {navLinks}
          </nav>
          <div className="shell-drawer-footer">
            {archiveAction}
            {languageAction}
            {settingsAction}
            {systemAction}
            {userGovernanceAction}
            {costObservabilityAction}
            {notificationAction}
            {marketProviderAction}
            {signInAction}
            {logoutAction}
          </div>
        </div>
      ) : (
        <div className="shell-header-nav">
          <div className="shell-header-brand">
            <BrandWordmark />
          </div>
          <nav className="shell-header-links" aria-label={t('shell.drawerTitle')}>
            {navLinks}
          </nav>
          <div className="shell-header-utilities">
            {archiveAction}
            <div
              data-testid="shell-header-utility-island"
              className="flex items-center gap-1 rounded-full border border-white/5 bg-white/[0.02] px-2 py-1.5 backdrop-blur-md"
            >
              {languageAction}
              {(settingsAction || systemAction || signInAction || logoutAction) ? (
                <div className="h-3 w-px bg-white/10" data-testid="shell-header-utility-divider" />
              ) : null}
              {settingsAction}
              {systemAction}
              {userGovernanceAction}
              {costObservabilityAction}
              {notificationAction}
              {marketProviderAction}
              {signInAction}
              {logoutAction && (settingsAction || systemAction || signInAction) ? (
                <div className="h-3 w-px bg-white/10" data-testid="shell-header-utility-divider" />
              ) : null}
              {logoutAction}
            </div>
          </div>
        </div>
      )}

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
    </>
  );
};
