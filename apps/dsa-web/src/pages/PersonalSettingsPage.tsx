import type React from 'react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BellRing, ShieldCheck } from 'lucide-react';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import {
  ConsoleBoard,
  ConsoleContextRail,
  ConsoleDisclosure,
  ConsoleStatusStrip,
  WolfyShellSurface,
} from '../components/linear';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import { TerminalButton, TerminalChip, TerminalPageHeading } from '../components/terminal';
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

const SETTINGS_ROW_CLASS = 'grid gap-3 p-4 md:grid-cols-[180px_minmax(0,1fr)] xl:grid-cols-[220px_minmax(0,1fr)]';
const SETTINGS_TEXT_INPUT_CLASS = 'h-10 w-full rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 text-sm text-[color:var(--wolfy-text-primary)] outline-none transition-colors placeholder:text-[color:var(--wolfy-text-muted)] focus:border-[color:var(--wolfy-accent)] focus:shadow-[0_0_0_1px_var(--wolfy-accent)]';
const SETTINGS_CHECKBOX_CLASS = 'size-4 rounded border border-[color:var(--wolfy-border-subtle)] bg-transparent accent-[var(--wolfy-accent)]';
const SETTINGS_LINK_CLASS = 'inline-flex min-h-9 items-center justify-center rounded-md border px-3 text-xs font-medium transition-colors';
const SETTINGS_PANEL_CLASS = 'rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3';

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
      <div className="p-4 md:px-5">
        <h2 className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{title}</h2>
        <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{description}</p>
      </div>
      <div className="divide-y divide-[color:var(--wolfy-divider)] border-t border-[color:var(--wolfy-divider)]">
        {children}
      </div>
    </section>
  );
}

function SettingsInfoPanel({
  title,
  body,
  chips,
  tone = 'default',
  children,
}: {
  title: string;
  body: string;
  chips?: React.ReactNode;
  tone?: 'default' | 'accent';
  children?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        SETTINGS_PANEL_CLASS,
        tone === 'accent'
          ? 'border-amber-300/20 bg-amber-300/5'
          : null,
      )}
    >
      <div className="space-y-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{title}</p>
          <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{body}</p>
        </div>
        {chips ? (
          <div className="flex flex-wrap gap-2">
            {chips}
          </div>
        ) : null}
        {children}
      </div>
    </div>
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
      heroSummarySignedIn: 'Manage sign-in security, delivery targets, and local reading defaults from one account page.',
      heroSummaryGuest: 'Sign in to unlock password and delivery controls. Local reading defaults are still available now.',
      guestTitle: 'Guest session',
      accountSectionTitle: 'Account',
      accountSectionDescription: 'Who is using this account center and where personal controls apply.',
      securityTitle: 'Security',
      securityDescription: 'Password access stays on this page and follows the current auth policy.',
      notificationsTitle: 'Notifications',
      notificationsDescription: 'Choose how this account receives personal delivery updates.',
      privacyTitle: 'Privacy & session',
      privacyDescription: 'Keep account-level boundaries clear and explain what remains local to this browser.',
      preferencesTitle: 'Local preferences',
      preferencesDescription: 'Reading density, number formatting, fonts, and portfolio display currency stay local to this device.',
      accountLabel: 'Identity',
      securityLabel: 'Security',
      notificationLabel: 'Notifications',
      localLabel: 'Saved in',
      signedInStatus: 'Signed in',
      guestStatus: 'Guest',
      authReadyState: 'Change available',
      authLimitedState: 'No password changes',
      signInRequired: 'Sign in required',
      localOnlyState: 'This browser',
      loadingTargets: 'Loading targets',
      targetsReady: 'Ready',
      notificationsPaused: 'Connect after sign-in',
      accountCardTitle: 'Current account',
      accountCardBody: 'Your personal delivery targets and security actions stay attached to this account only.',
      guestCardTitle: 'Guest preferences',
      guestCardBody: 'Sign in before saving delivery targets or changing your password.',
      securityCardTitle: 'Password access',
      securityCardBodyReady: 'You can change the password for this signed-in account here.',
      securityCardBodyLocked: 'Password controls stay unavailable until the current auth policy allows changes.',
      securityGuestBody: 'Password management appears after sign-in when account security is available.',
      sessionCardTitle: 'Session behavior',
      sessionCardBody: 'Signing out closes the current authenticated session. Local display defaults stay in this browser until you change them again.',
      boundaryDisclosureTitle: 'What this page covers',
      boundaryDisclosureSummary: 'Account, privacy, notifications, and local reading defaults only.',
      boundaryDisclosureBody: 'Workspace-wide controls, system operations, and shared management stay outside this account center by design.',
      preferenceDisclosureTitle: 'Where local preferences live',
      preferenceDisclosureSummary: 'Display density, number format, fonts, and portfolio currency remain device-local.',
      preferenceDisclosureBody: 'These options change how this consumer workspace reads on this browser. They do not change sign-in behavior or other people’s experience.',
      guestNotificationHint: 'Sign in before editing email and Discord delivery targets.',
      notificationHelper: 'Save both delivery channels together from personal settings.',
      signedInHint: 'Review your account state, update notifications, and keep local reading defaults tidy here.',
      railEyebrow: 'Next action',
      railTitle: 'Unlock account controls',
      railBody: 'Sign in to save delivery targets and use account-level security actions.',
      railLinkPrimary: 'Sign in',
      railLinkSecondary: 'Create account',
    }
    : {
      consoleEyebrow: '账户中心',
      pageTitle: '账户中心',
      heroSummarySignedIn: '在一个账户中心内管理登录安全、通知方式和本地阅读偏好。',
      heroSummaryGuest: '登录后即可启用密码与通知控制；本地阅读偏好现在就能调整。',
      guestTitle: '访客会话',
      accountSectionTitle: '账户',
      accountSectionDescription: '说明当前是谁在使用这个账户中心，以及个人控制项归属到哪里。',
      securityTitle: '安全',
      securityDescription: '密码相关操作只留在这里，并遵循当前认证策略。',
      notificationsTitle: '通知',
      notificationsDescription: '选择这个账户接收个人通知更新的方式。',
      privacyTitle: '隐私与会话',
      privacyDescription: '明确账户边界，并说明哪些设置仍然只保存在当前浏览器。',
      preferencesTitle: '本地偏好',
      preferencesDescription: '阅读密度、数字格式、字体和组合显示货币都只保存在当前设备。',
      accountLabel: '身份',
      securityLabel: '安全',
      notificationLabel: '通知',
      localLabel: '保存位置',
      signedInStatus: '已登录',
      guestStatus: '访客',
      authReadyState: '可修改',
      authLimitedState: '暂不可改',
      signInRequired: '登录后可用',
      localOnlyState: '当前浏览器',
      loadingTargets: '正在加载',
      targetsReady: '可编辑',
      notificationsPaused: '登录后连接',
      accountCardTitle: '当前账户',
      accountCardBody: '你的通知目标和安全操作只绑定到这个账户，不会扩散到更大的工作区设置。',
      guestCardTitle: '访客偏好',
      guestCardBody: '登录前只能调整本地阅读偏好，通知目标和密码操作会保持关闭。',
      securityCardTitle: '密码访问',
      securityCardBodyReady: '当前已登录账户可在这里修改密码。',
      securityCardBodyLocked: '当前认证策略暂未开放密码修改，这里不会显示额外系统控制。',
      securityGuestBody: '登录后如果认证策略允许，就会在这里启用密码管理。',
      sessionCardTitle: '会话行为',
      sessionCardBody: '退出登录只会结束当前认证会话。本地显示默认项会继续保存在这个浏览器，直到你再次修改。',
      boundaryDisclosureTitle: '这页负责什么',
      boundaryDisclosureSummary: '只处理账户、隐私、通知和本地阅读偏好。',
      boundaryDisclosureBody: '更广的工作区控制、系统操作和共享管理故意不放在这个账户中心里。',
      preferenceDisclosureTitle: '本地偏好保存在哪里',
      preferenceDisclosureSummary: '显示密度、数字格式、字体和组合显示货币都保存在当前设备。',
      preferenceDisclosureBody: '这些选项只改变当前浏览器里的消费端阅读体验，不会修改登录行为，也不会影响其他人的界面。',
      guestNotificationHint: '登录后才能编辑邮件和 Discord 通知目标。',
      notificationHelper: '在个人设置内统一保存邮件与 Discord 目标。',
      signedInHint: '在这里检查账户状态、更新通知方式，并整理你的本地阅读默认项。',
      railEyebrow: '下一步',
      railTitle: '登录后启用账户控制',
      railBody: '登录后可保存通知目标，并使用账户级安全操作。',
      railLinkPrimary: '去登录',
      railLinkSecondary: '创建账户',
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
  const showGuestRail = !loggedIn && authEnabled;
  const statusItems = [
    {
      label: copy.accountLabel,
      value: loggedIn ? copy.signedInStatus : copy.guestStatus,
    },
    {
      label: copy.notificationLabel,
      value: loggedIn
        ? (notificationLoading ? copy.loadingTargets : copy.targetsReady)
        : copy.notificationsPaused,
    },
    {
      label: copy.localLabel,
      value: copy.localOnlyState,
    },
  ];

  return (
    <ConsumerWorkspaceScope className="flex-1">
    <ConsumerWorkspacePageShell
      data-testid="personal-settings-workspace"
      className="flex-1 min-h-0 min-w-0"
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
          <div className="flex flex-col gap-4">
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
              <p className="mt-2 max-w-3xl text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                {loggedIn ? copy.heroSummarySignedIn : copy.heroSummaryGuest}
              </p>
            </div>
          </div>

          <ConsoleStatusStrip data-testid="personal-settings-summary-strip" items={statusItems} className="mt-4" />
        </WolfyShellSurface>

        <div
          data-testid="personal-settings-console"
          className={cn(
            'grid gap-4',
            showGuestRail ? 'xl:grid-cols-[minmax(0,1fr)_320px]' : null,
          )}
        >
          <ConsoleBoard data-testid="personal-settings-primary-board">
            <SettingsConsoleSection
              id="account"
              data-testid="personal-settings-account-section"
              title={copy.accountSectionTitle}
              description={copy.accountSectionDescription}
            >
              <div data-testid="personal-settings-account-row" className={SETTINGS_ROW_CLASS}>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                    {loggedIn ? copy.accountCardTitle : copy.guestCardTitle}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                    {loggedIn ? copy.accountCardBody : copy.guestCardBody}
                  </p>
                </div>
                {loggedIn ? (
                  <SettingsInfoPanel
                    title={signedInName}
                    body={t('settings.personalSignedInAs', { name: signedInName })}
                    chips={(
                      <>
                        <TerminalChip variant="info">{copy.signedInStatus}</TerminalChip>
                        <TerminalChip variant={passwordChangeable ? 'success' : 'neutral'}>
                          {passwordChangeable ? copy.authReadyState : copy.authLimitedState}
                        </TerminalChip>
                      </>
                    )}
                  />
                ) : (
                  <SettingsInfoPanel
                    title={t('settings.personalGuestPreferencesTitle')}
                    body={copy.guestNotificationHint}
                    tone="accent"
                  />
                )}
              </div>
            </SettingsConsoleSection>

            <SettingsConsoleSection
              id="security"
              data-testid="personal-settings-security-section"
              title={copy.securityTitle}
              description={copy.securityDescription}
            >
              <div className={SETTINGS_ROW_CLASS}>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                    {copy.securityCardTitle}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                    {loggedIn ? copy.signedInHint : copy.securityGuestBody}
                  </p>
                </div>
                <SettingsInfoPanel
                  title={loggedIn
                    ? (passwordChangeable ? copy.authReadyState : copy.authLimitedState)
                    : copy.signInRequired}
                  body={loggedIn
                    ? (passwordChangeable ? copy.securityCardBodyReady : copy.securityCardBodyLocked)
                    : copy.securityGuestBody}
                  chips={(
                    <>
                      <TerminalChip variant={loggedIn ? 'info' : 'neutral'}>
                        {loggedIn ? copy.signedInStatus : copy.guestStatus}
                      </TerminalChip>
                      <TerminalChip variant={passwordChangeable ? 'success' : 'neutral'}>
                        {loggedIn
                          ? (passwordChangeable ? copy.authReadyState : copy.authLimitedState)
                          : copy.signInRequired}
                      </TerminalChip>
                    </>
                  )}
                >
                  {loggedIn && passwordChangeable ? (
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] text-[color:var(--wolfy-text-primary)]">
                        <ShieldCheck className="size-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <ChangePasswordCard />
                      </div>
                    </div>
                  ) : null}
                </SettingsInfoPanel>
              </div>
            </SettingsConsoleSection>

            <SettingsConsoleSection
              id="notifications"
              data-testid="personal-settings-notifications-section"
              title={copy.notificationsTitle}
              description={copy.notificationsDescription}
            >
              <div data-testid="personal-settings-notification-row" className={SETTINGS_ROW_CLASS}>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <BellRing className="size-4 text-[color:var(--wolfy-text-secondary)]" />
                    <p className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                      {t('settings.personalNotificationScopeTitle')}
                    </p>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                    {loggedIn ? copy.notificationHelper : copy.guestNotificationHint}
                  </p>
                </div>

                {loggedIn ? (
                  <div className={cn(SETTINGS_PANEL_CLASS, 'min-w-0 space-y-3')}>
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
                  <div className={cn(SETTINGS_PANEL_CLASS, 'text-sm text-[color:var(--wolfy-text-secondary)]')}>
                    {copy.guestNotificationHint}
                  </div>
                )}
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
                    {copy.sessionCardTitle}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                    {copy.sessionCardBody}
                  </p>
                </div>
                <div className="min-w-0 space-y-3">
                  <SettingsInfoPanel
                    title={copy.boundaryDisclosureSummary}
                    body={copy.sessionCardBody}
                    chips={<TerminalChip variant="neutral">{copy.localOnlyState}</TerminalChip>}
                  />
                  <ConsoleDisclosure
                    data-testid="personal-settings-boundary-disclosure"
                    title={copy.boundaryDisclosureTitle}
                    summary={copy.boundaryDisclosureSummary}
                  >
                    <p className="text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                      {copy.boundaryDisclosureBody}
                    </p>
                  </ConsoleDisclosure>
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

              <div className={SETTINGS_ROW_CLASS}>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                    {copy.preferenceDisclosureTitle}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                    {copy.preferenceDisclosureSummary}
                  </p>
                </div>
                <ConsoleDisclosure
                  data-testid="personal-settings-help-disclosure"
                  title={copy.preferenceDisclosureTitle}
                  summary={copy.preferenceDisclosureSummary}
                >
                  <p className="text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                    {copy.preferenceDisclosureBody}
                  </p>
                </ConsoleDisclosure>
              </div>
            </SettingsConsoleSection>
          </ConsoleBoard>

          {showGuestRail ? (
            <ConsoleContextRail data-testid="personal-settings-help-rail">
              <div className="p-1">
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

              <div className="flex flex-wrap gap-2">
                <Link
                  to={loginPath}
                  className={cn(
                    SETTINGS_LINK_CLASS,
                    'border-[color:var(--wolfy-accent)] bg-[var(--wolfy-accent)] text-[#f7f8ff] hover:bg-[#6f79dc]',
                  )}
                >
                  {copy.railLinkPrimary}
                </Link>
                <Link
                  to={registrationPath}
                  className={cn(
                    SETTINGS_LINK_CLASS,
                    'border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-secondary)] hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)]',
                  )}
                >
                  {copy.railLinkSecondary}
                </Link>
              </div>
            </ConsoleContextRail>
          ) : null}
        </div>
      </section>
    </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
};

export default PersonalSettingsPage;
