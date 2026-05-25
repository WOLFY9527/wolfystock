import type React from 'react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BellRing, LockKeyhole, ShieldCheck } from 'lucide-react';
import { ApiErrorAlert } from '../components/common';
import {
  ConsoleBoard,
  ConsoleContextRail,
  ConsoleDisclosure,
  ConsoleStatusStrip,
  WolfyShellSurface,
} from '../components/linear';
import { TerminalButton, TerminalChip, TerminalPageHeading, TerminalPageShell } from '../components/terminal';
import { authApi } from '../api/auth';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ChangePasswordCard } from '../components/settings/ChangePasswordCard';
import { FontSizeSettingsCard } from '../components/settings/FontSizeSettingsCard';
import { useI18n } from '../contexts/UiLanguageContext';
import { useUiPreferences } from '../contexts/UiPreferencesContext';
import { useAuth } from '../contexts/AuthContext';
import { buildLoginPath, buildRegistrationPath, useProductSurface } from '../hooks/useProductSurface';
import type { MarketColorConvention } from '../utils/marketColors';
import {
  PORTFOLIO_DISPLAY_CURRENCY_OPTIONS,
  readPortfolioDisplayCurrency,
  savePortfolioDisplayCurrency,
  type PortfolioDisplayCurrency,
} from '../utils/portfolioPreferences';
import { cn } from '../utils/cn';

const SETTINGS_ROW_CLASS = 'grid gap-3 px-4 py-4 md:grid-cols-[180px_minmax(0,1fr)] xl:grid-cols-[220px_minmax(0,1fr)]';
const SETTINGS_TEXT_INPUT_CLASS = 'h-10 w-full rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 text-sm text-[color:var(--wolfy-text-primary)] outline-none transition-colors placeholder:text-[color:var(--wolfy-text-muted)] focus:border-[color:var(--wolfy-accent)] focus:shadow-[0_0_0_1px_var(--wolfy-accent)]';
const SETTINGS_CHECKBOX_CLASS = 'h-4 w-4 rounded border border-[color:var(--wolfy-border-subtle)] bg-transparent accent-[var(--wolfy-accent)]';
const SETTINGS_LINK_CLASS = 'inline-flex min-h-9 items-center justify-center rounded-md border px-3 text-xs font-medium transition-colors';

const buildChoiceButtonClass = (active: boolean, compact = false) => cn(
  'rounded-md border px-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent)]',
  compact ? 'min-h-9 py-1.5 text-xs font-medium' : 'min-h-10 py-2 text-sm font-medium',
  active
    ? 'border-[color:var(--wolfy-accent)] bg-[var(--wolfy-surface-console)] text-[color:var(--wolfy-text-primary)] shadow-[inset_0_0_0_1px_var(--wolfy-accent)]'
    : 'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-secondary)] hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)]',
);

const MARKET_COLOR_OPTIONS: Array<{
  value: MarketColorConvention;
  labelKey: string;
}> = [
  {
    value: 'redDownGreenUp',
    labelKey: 'settings.marketColorConventional',
  },
  {
    value: 'redUpGreenDown',
    labelKey: 'settings.marketColorCn',
  },
];

const DATA_DENSITY_OPTIONS = [
  { value: 'compact', labelKey: 'settings.dataDensityCompact' },
  { value: 'comfortable', labelKey: 'settings.dataDensityComfortable' },
  { value: 'relaxed', labelKey: 'settings.dataDensityRelaxed' },
] as const;

const NUMBER_FORMAT_OPTIONS = [
  { value: 'international', labelKey: 'settings.numberFormatInternational' },
  { value: 'zh', labelKey: 'settings.numberFormatZh' },
  { value: 'full', labelKey: 'settings.numberFormatFull' },
] as const;

function SettingsConsoleSection({
  id,
  title,
  description,
  children,
  'data-testid': dataTestId,
}: {
  id?: string;
  title: string;
  description: string;
  children: React.ReactNode;
  'data-testid'?: string;
}) {
  return (
    <section id={id} data-testid={dataTestId} className="min-w-0 scroll-mt-28">
      <div className="px-4 py-4 md:px-5">
        <h2 className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{title}</h2>
        <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{description}</p>
      </div>
      <div className="divide-y divide-[color:var(--wolfy-divider)] border-t border-[color:var(--wolfy-divider)]">
        {children}
      </div>
    </section>
  );
}

function SettingsChoiceRow<T extends string>({
  title,
  description,
  options,
  value,
  onChange,
  compact = false,
}: {
  title: string;
  description?: string;
  options: Array<{ value: T; label: string }>;
  value: T;
  onChange: (nextValue: T) => void;
  compact?: boolean;
}) {
  return (
    <div className={SETTINGS_ROW_CLASS}>
      <div className="min-w-0">
        <p className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">{title}</p>
        {description ? <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{description}</p> : null}
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap gap-2" role="group" aria-label={title}>
          {options.map((option) => {
            const active = option.value === value;
            return (
              <button
                key={option.value}
                type="button"
                className={buildChoiceButtonClass(active, compact)}
                onClick={() => onChange(option.value)}
                aria-pressed={active}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

const PersonalSettingsPage: React.FC = () => {
  const { language, t } = useI18n();
  const {
    dataDensity,
    marketColorConvention,
    numberFormat,
    setDataDensity,
    setMarketColorConvention,
    setNumberFormat,
  } = useUiPreferences();
  const { authEnabled, passwordChangeable } = useAuth();
  const {
    loggedIn,
    currentUser,
  } = useProductSurface();
  const [notificationEmail, setNotificationEmail] = useState('');
  const [notificationEmailEnabled, setNotificationEmailEnabled] = useState(false);
  const [notificationDiscordEnabled, setNotificationDiscordEnabled] = useState(false);
  const [notificationDiscordWebhook, setNotificationDiscordWebhook] = useState('');
  const [notificationLoading, setNotificationLoading] = useState(false);
  const [notificationSaving, setNotificationSaving] = useState(false);
  const [notificationError, setNotificationError] = useState<ParsedApiError | null>(null);
  const [notificationNotice, setNotificationNotice] = useState<string | null>(null);
  const [portfolioDisplayCurrency, setPortfolioDisplayCurrency] = useState<PortfolioDisplayCurrency>(() => readPortfolioDisplayCurrency());
  const [portfolioDisplayCurrencySaved, setPortfolioDisplayCurrencySaved] = useState(false);
  const loginPath = buildLoginPath('/settings');
  const registrationPath = buildRegistrationPath('/settings');

  const copy = language === 'en'
    ? {
      consoleEyebrow: 'Account center',
      pageTitle: 'Account Center',
      guestTitle: 'Guest session',
      guestSubtitle: 'Sign in to sync notification targets and manage password changes.',
      securityTitle: 'Account & security',
      securityDescription: 'Access state, password changes, and delivery targets stay scoped to this account page.',
      privacyTitle: 'Privacy settings',
      privacyDescription: 'Personal notifications, saved preferences, and sign-out behavior stay scoped to your own account surface.',
      privacyBoundaryTitle: 'Account privacy boundary',
      privacyBoundaryBody: 'This account center keeps account details, notification targets, and local preferences separate from broader workspace management.',
      privacySessionTitle: 'Session and local defaults',
      privacySessionBody: 'Signing out closes the current authenticated session. Display density, number formatting, and font size remain local browser preferences until you change them again.',
      preferencesTitle: 'Display & preferences',
      preferencesDescription: 'Compact, local display defaults for density, number formatting, fonts, and portfolio currency.',
      accountLabel: 'Account',
      authLabel: 'Password',
      notificationLabel: 'Notifications',
      scopeLabel: 'Scope',
      signedInStatus: 'Signed in',
      guestStatus: 'Guest',
      authReadyState: 'Change available',
      guestOnly: 'Guest only',
      signInRequired: 'Sign in required',
      savedHere: 'Personal route only',
      loadingTargets: 'Loading targets',
      targetsReady: 'Ready',
      guestNotificationHint: 'Sign in before editing email and Discord delivery targets.',
      notificationHelper: 'Save both delivery channels together from personal settings.',
      signedInHint: 'Your password and notification targets stay tied to this account page.',
      railEyebrow: 'Secondary details',
      railTitle: 'Personal settings boundary',
      railBody: 'This route now focuses on your account, UI defaults, and notification targets only.',
      boundaryTitle: 'Account page scope',
      boundarySummary: 'Only account, privacy, notification, and local preference actions appear here.',
      boundaryBody: 'Broader workspace controls are managed separately. This page is intentionally limited to account-level choices and local display defaults.',
      preferenceTitle: 'Preference notes',
      preferenceSummary: 'Density, number formatting, font size, and portfolio display currency remain local UI preferences.',
      preferenceBody: 'These controls do not change sign-in behavior or affect other people in the workspace. They only adjust how this user-facing workspace renders data.',
      guestAccessTitle: 'Sign in for account controls',
    }
    : {
      consoleEyebrow: '账户中心',
      pageTitle: '账户中心',
      guestTitle: '访客会话',
      guestSubtitle: '登录后可同步通知目标并管理密码修改。',
      securityTitle: '账户与安全',
      securityDescription: '访问状态、密码变更和通知目标都只保留在个人设置内。',
      privacyTitle: '隐私设置',
      privacyDescription: '个人通知、本地偏好和退出登录行为都只保留在你自己的账户界面内。',
      privacyBoundaryTitle: '账户隐私边界',
      privacyBoundaryBody: '账户中心只承载账户资料、通知目标和本地偏好，与更广的工作区管理保持分离。',
      privacySessionTitle: '会话与本地默认项',
      privacySessionBody: '退出登录只会结束当前认证会话。显示密度、数字格式和字体大小仍然保存在当前浏览器，直到你再次修改。',
      preferencesTitle: '显示与偏好',
      preferencesDescription: '用紧凑的本地偏好统一控制密度、数字格式、字体和组合显示货币。',
      accountLabel: '账户',
      authLabel: '密码',
      notificationLabel: '通知',
      scopeLabel: '范围',
      signedInStatus: '已登录',
      guestStatus: '访客',
      authReadyState: '可修改',
      guestOnly: '仅访客偏好',
      signInRequired: '登录后可用',
      savedHere: '仅个人设置',
      loadingTargets: '正在加载',
      targetsReady: '可编辑',
      guestNotificationHint: '登录后才能编辑邮件和 Discord 通知目标。',
      notificationHelper: '在个人设置内统一保存邮件与 Discord 目标。',
      signedInHint: '当前密码与通知目标只绑定这个账户页面。',
      railEyebrow: '辅助说明',
      railTitle: '个人设置边界',
      railBody: '这个路由现在只承载你的账户、界面偏好与通知目标。',
      boundaryTitle: '账户页面范围',
      boundarySummary: '这里只显示账户、隐私、通知和本地偏好操作。',
      boundaryBody: '更广的工作区管理在单独页面处理。这里刻意只保留账户级选择和本地显示默认项。',
      preferenceTitle: '偏好说明',
      preferenceSummary: '密度、数字格式、字体大小和组合显示货币都还是本地 UI 偏好。',
      preferenceBody: '这些控件不会改变登录行为或其他用户体验，只会影响当前用户界面对数据的呈现方式。',
      guestAccessTitle: '登录后启用账户控制',
    };

  useEffect(() => {
    document.title = language === 'en' ? 'Account Center - WolfyStock' : '账户中心 - WolfyStock';
  }, [language]);

  useEffect(() => {
    if (!loggedIn) {
      setNotificationEmail('');
      setNotificationEmailEnabled(false);
      setNotificationDiscordEnabled(false);
      setNotificationDiscordWebhook('');
      setNotificationLoading(false);
      setNotificationSaving(false);
      setNotificationError(null);
      setNotificationNotice(null);
      return;
    }

    let cancelled = false;
    setNotificationLoading(true);
    setNotificationError(null);
    void authApi.getNotificationPreferences()
      .then((prefs) => {
        if (cancelled) {
          return;
        }
        setNotificationEmail(prefs.email || '');
        setNotificationEmailEnabled(Boolean(prefs.emailEnabled));
        setNotificationDiscordEnabled(Boolean(prefs.discordEnabled));
        setNotificationDiscordWebhook(prefs.discordWebhook || '');
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        setNotificationError(getParsedApiError(err));
      })
      .finally(() => {
        if (!cancelled) {
          setNotificationLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [loggedIn]);

  const handleSaveNotificationPreferences = async () => {
    setNotificationSaving(true);
    setNotificationError(null);
    setNotificationNotice(null);
    try {
      const prefs = await authApi.updateNotificationPreferences(
        {
          emailEnabled: notificationEmailEnabled,
          email: notificationEmail.trim() || null,
          discordEnabled: notificationDiscordEnabled,
          discordWebhook: notificationDiscordWebhook.trim() || null,
        },
      );
      setNotificationEmail(prefs.email || '');
      setNotificationEmailEnabled(Boolean(prefs.emailEnabled));
      setNotificationDiscordEnabled(Boolean(prefs.discordEnabled));
      setNotificationDiscordWebhook(prefs.discordWebhook || '');
      setNotificationNotice(t('settings.personalNotificationTargetsSaved'));
    } catch (err) {
      setNotificationError(getParsedApiError(err));
    } finally {
      setNotificationSaving(false);
    }
  };

  const handlePortfolioDisplayCurrencyChange = (currency: PortfolioDisplayCurrency) => {
    const saved = savePortfolioDisplayCurrency(currency);
    setPortfolioDisplayCurrency(saved);
    setPortfolioDisplayCurrencySaved(true);
    window.setTimeout(() => setPortfolioDisplayCurrencySaved(false), 1800);
  };

  const signedInName = currentUser?.displayName || currentUser?.username || t('settings.personalFallbackUser');
  const statusItems = [
    {
      label: copy.accountLabel,
      value: loggedIn ? copy.signedInStatus : copy.guestStatus,
    },
    {
      label: copy.authLabel,
      value: loggedIn
        ? (passwordChangeable ? copy.authReadyState : copy.guestOnly)
        : (authEnabled ? copy.signInRequired : copy.guestOnly),
    },
    {
      label: copy.notificationLabel,
      value: loggedIn
        ? (notificationLoading ? copy.loadingTargets : copy.targetsReady)
        : copy.signInRequired,
    },
    {
      label: copy.scopeLabel,
      value: copy.savedHere,
    },
  ];

  return (
    <TerminalPageShell
      data-testid="personal-settings-workspace"
      className="flex-1 min-h-0 min-w-0 py-5 md:py-6"
    >
      <section className="flex min-h-0 min-w-0 flex-col gap-4">
        <TerminalPageHeading
          data-testid="settings-page-heading"
          title={copy.pageTitle}
        />

        <WolfyShellSurface
          id="account-center"
          as="section"
          variant="console"
          padding="md"
          data-testid="personal-settings-profile-header"
          className="overflow-hidden"
        >
          <div className="flex flex-col gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-[11px] uppercase tracking-[0.12em] text-[color:var(--wolfy-text-muted)]">
                  {copy.consoleEyebrow}
                </p>
                <TerminalChip variant={loggedIn ? 'info' : 'neutral'}>
                  {loggedIn ? copy.signedInStatus : copy.guestStatus}
                </TerminalChip>
              </div>
              <h2 className="mt-2 text-lg font-semibold text-[color:var(--wolfy-text-primary)]">
                {loggedIn ? signedInName : copy.guestTitle}
              </h2>
              <p className="mt-1 max-w-3xl text-sm text-[color:var(--wolfy-text-secondary)]">
                {loggedIn
                  ? t('settings.personalSignedInAs', { name: signedInName })
                  : copy.guestSubtitle}
              </p>
            </div>
          </div>

          <ConsoleStatusStrip items={statusItems} className="mt-4" />
        </WolfyShellSurface>

        <div
          data-testid="personal-settings-console"
          className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]"
        >
          <ConsoleBoard data-testid="personal-settings-primary-board">
            <SettingsConsoleSection
              id="security"
              data-testid="personal-settings-security-section"
              title={copy.securityTitle}
              description={copy.securityDescription}
            >
              <div data-testid="personal-settings-account-row" className={SETTINGS_ROW_CLASS}>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                    {loggedIn ? copy.accountLabel : copy.guestAccessTitle}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                    {loggedIn ? copy.signedInHint : copy.guestSubtitle}
                  </p>
                </div>
                {loggedIn ? (
                  <div className="flex min-w-0 flex-col gap-3 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] text-[color:var(--wolfy-text-primary)]">
                        <ShieldCheck className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
                          {signedInName}
                        </p>
                        <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                          {t('settings.personalSignedInAs', { name: signedInName })}
                        </p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <TerminalChip variant="info">{copy.signedInStatus}</TerminalChip>
                      <TerminalChip variant={passwordChangeable ? 'success' : 'neutral'}>
                        {passwordChangeable ? copy.authReadyState : copy.guestOnly}
                      </TerminalChip>
                    </div>
                  </div>
                ) : (
                  <div className="flex min-w-0 flex-col gap-3 rounded-md border border-amber-300/20 bg-amber-300/5 p-3">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-amber-300/25 bg-amber-300/10 text-amber-100">
                        <LockKeyhole className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
                          {t('settings.personalGuestPreferencesTitle')}
                        </p>
                        <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                          {copy.guestNotificationHint}
                        </p>
                      </div>
                    </div>
                    {authEnabled ? (
                      <div className="flex flex-wrap gap-2">
                        <Link
                          to={loginPath}
                          className={cn(
                            SETTINGS_LINK_CLASS,
                            'border-[color:var(--wolfy-accent)] bg-[var(--wolfy-accent)] text-[#f7f8ff] hover:bg-[#6f79dc]',
                          )}
                        >
                          {t('settings.personalGuestSignInAction')}
                        </Link>
                        <Link
                          to={registrationPath}
                          className={cn(
                            SETTINGS_LINK_CLASS,
                            'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-secondary)] hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)]',
                          )}
                        >
                          {t('settings.personalGuestCreateAccountAction')}
                        </Link>
                      </div>
                    ) : null}
                  </div>
                )}
              </div>

              <div data-testid="personal-settings-notification-row" className={SETTINGS_ROW_CLASS}>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <BellRing className="h-4 w-4 text-[color:var(--wolfy-text-secondary)]" />
                    <p className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                      {t('settings.personalNotificationScopeTitle')}
                    </p>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                    {loggedIn ? copy.notificationHelper : copy.guestNotificationHint}
                  </p>
                </div>

                {loggedIn ? (
                  <div className="min-w-0 space-y-3 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                    <div className="grid gap-3 lg:grid-cols-2">
                      <div className="space-y-2">
                        <label className="flex items-center gap-3 text-xs text-[color:var(--wolfy-text-secondary)]">
                          <input
                            type="checkbox"
                            className={SETTINGS_CHECKBOX_CLASS}
                            checked={notificationEmailEnabled}
                            onChange={(event) => setNotificationEmailEnabled(event.target.checked)}
                            disabled={notificationLoading || notificationSaving}
                          />
                          <span>{t('settings.personalNotificationEmailToggle')}</span>
                        </label>
                        <label className="block">
                          <span className="block text-[11px] uppercase tracking-[0.08em] text-[color:var(--wolfy-text-muted)]">
                            {t('settings.personalNotificationEmailLabel')}
                          </span>
                          <input
                            type="email"
                            className={cn('mt-2', SETTINGS_TEXT_INPUT_CLASS)}
                            value={notificationEmail}
                            onChange={(event) => setNotificationEmail(event.target.value)}
                            placeholder={t('settings.personalNotificationEmailPlaceholder')}
                            disabled={notificationLoading || notificationSaving}
                            aria-label={t('settings.personalNotificationEmailLabel')}
                          />
                        </label>
                      </div>

                      <div className="space-y-2">
                        <label className="flex items-center gap-3 text-xs text-[color:var(--wolfy-text-secondary)]">
                          <input
                            type="checkbox"
                            className={SETTINGS_CHECKBOX_CLASS}
                            checked={notificationDiscordEnabled}
                            onChange={(event) => setNotificationDiscordEnabled(event.target.checked)}
                            disabled={notificationLoading || notificationSaving}
                          />
                          <span>{t('settings.personalNotificationDiscordToggle')}</span>
                        </label>
                        <label className="block">
                          <span className="block text-[11px] uppercase tracking-[0.08em] text-[color:var(--wolfy-text-muted)]">
                            {t('settings.personalNotificationDiscordLabel')}
                          </span>
                          <input
                            type="url"
                            className={cn('mt-2', SETTINGS_TEXT_INPUT_CLASS)}
                            value={notificationDiscordWebhook}
                            onChange={(event) => setNotificationDiscordWebhook(event.target.value)}
                            placeholder="https://discord.com/api/webhooks/..."
                            disabled={notificationLoading || notificationSaving}
                            aria-label={t('settings.personalNotificationDiscordLabel')}
                          />
                        </label>
                      </div>
                    </div>

                    {notificationLoading ? (
                      <p className="text-xs text-[color:var(--wolfy-text-muted)]">{copy.loadingTargets}</p>
                    ) : null}
                    {notificationNotice ? (
                      <p className="text-xs leading-5 text-[hsl(var(--accent-positive-hsl))]">{notificationNotice}</p>
                    ) : null}
                    {notificationError ? <ApiErrorAlert error={notificationError} /> : null}

                    <div className="flex flex-wrap items-center gap-3">
                      <TerminalButton
                        type="button"
                        variant="primary"
                        onClick={() => void handleSaveNotificationPreferences()}
                        disabled={notificationLoading || notificationSaving}
                      >
                        {notificationSaving ? t('settings.personalNotificationSaving') : t('settings.personalNotificationSaveAction')}
                      </TerminalButton>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3 text-sm text-[color:var(--wolfy-text-secondary)]">
                    {copy.guestNotificationHint}
                  </div>
                )}
              </div>

              <div id="password" className="scroll-mt-28">
                {loggedIn && passwordChangeable ? <ChangePasswordCard /> : null}
              </div>
            </SettingsConsoleSection>

            <SettingsConsoleSection
              id="privacy"
              data-testid="personal-settings-privacy-section"
              title={copy.privacyTitle}
              description={copy.privacyDescription}
            >
              <div className={SETTINGS_ROW_CLASS}>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                    {copy.privacyBoundaryTitle}
                  </p>
                </div>
                <div className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                  {copy.privacyBoundaryBody}
                </div>
              </div>

              <div className={SETTINGS_ROW_CLASS}>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                    {copy.privacySessionTitle}
                  </p>
                </div>
                <div className="rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                  {copy.privacySessionBody}
                </div>
              </div>
            </SettingsConsoleSection>

            <SettingsConsoleSection
              id="preferences"
              data-testid="personal-settings-preferences-section"
              title={copy.preferencesTitle}
              description={copy.preferencesDescription}
            >
              <SettingsChoiceRow
                title={t('settings.marketColorTitle')}
                options={MARKET_COLOR_OPTIONS.map((option) => ({ value: option.value, label: t(option.labelKey) }))}
                value={marketColorConvention}
                onChange={setMarketColorConvention}
              />
              <SettingsChoiceRow
                title={t('settings.dataDensityTitle')}
                options={DATA_DENSITY_OPTIONS.map((option) => ({ value: option.value, label: t(option.labelKey) }))}
                value={dataDensity}
                onChange={setDataDensity}
              />
              <SettingsChoiceRow
                title={t('settings.numberFormatTitle')}
                options={NUMBER_FORMAT_OPTIONS.map((option) => ({ value: option.value, label: t(option.labelKey) }))}
                value={numberFormat}
                onChange={setNumberFormat}
              />

              <div className={SETTINGS_ROW_CLASS}>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                    {t('settings.portfolioDisplayTitle')}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                    {t('settings.portfolioDisplayDesc')}
                  </p>
                  <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                    {t('settings.portfolioDisplayNativeSettlementHint')}
                  </p>
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-3">
                    <p className="text-[11px] uppercase tracking-[0.08em] text-[color:var(--wolfy-text-muted)]">
                      {t('settings.portfolioDisplayDefaultCurrency')}
                    </p>
                    {portfolioDisplayCurrencySaved ? (
                      <TerminalChip variant="success">{t('settings.portfolioDisplaySaved')}</TerminalChip>
                    ) : null}
                  </div>
                  <div
                    className="mt-2 flex flex-wrap gap-2"
                    role="group"
                    aria-label={t('settings.portfolioDisplayDefaultCurrency')}
                  >
                    {PORTFOLIO_DISPLAY_CURRENCY_OPTIONS.map((currency) => {
                      const active = portfolioDisplayCurrency === currency;
                      return (
                        <button
                          key={currency}
                          type="button"
                          className={buildChoiceButtonClass(active, true)}
                          onClick={() => handlePortfolioDisplayCurrencyChange(currency)}
                          aria-pressed={active}
                        >
                          {currency}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              <FontSizeSettingsCard />
            </SettingsConsoleSection>
          </ConsoleBoard>

          <ConsoleContextRail data-testid="personal-settings-help-rail">
            <div className="px-1 py-1">
              <p className="text-[11px] uppercase tracking-[0.08em] text-[color:var(--wolfy-text-muted)]">
                {copy.railEyebrow}
              </p>
              <p className="mt-1 text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                {copy.railTitle}
              </p>
              <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                {copy.railBody}
              </p>
            </div>

            <ConsoleDisclosure
              data-testid="personal-settings-boundary-disclosure"
              title={copy.boundaryTitle}
              summary={copy.boundarySummary}
            >
              <p className="text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                {copy.boundaryBody}
              </p>
            </ConsoleDisclosure>

            <ConsoleDisclosure
              data-testid="personal-settings-help-disclosure"
              title={copy.preferenceTitle}
              summary={copy.preferenceSummary}
            >
              <p className="text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                {copy.preferenceBody}
              </p>
            </ConsoleDisclosure>
          </ConsoleContextRail>
        </div>
      </section>
    </TerminalPageShell>
  );
};

export default PersonalSettingsPage;
