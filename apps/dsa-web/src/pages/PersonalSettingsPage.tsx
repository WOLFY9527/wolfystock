import type React from 'react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BellRing, LockKeyhole, ShieldCheck } from 'lucide-react';
import { ApiErrorAlert, GlassCard, WorkspacePageHeader } from '../components/common';
import { authApi, type UserNotificationPreferences } from '../api/auth';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ChangePasswordCard } from '../components/settings/ChangePasswordCard';
import { FontSizeSettingsCard } from '../components/settings/FontSizeSettingsCard';
import { useI18n } from '../contexts/UiLanguageContext';
import { useUiPreferences } from '../contexts/UiPreferencesContext';
import { useAuth } from '../contexts/AuthContext';
import { buildLoginPath, buildRegistrationPath, useProductSurface } from '../hooks/useProductSurface';
import type { MarketColorConvention } from '../utils/marketColors';

const GLASS_INPUT_CLASS = 'w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2 text-sm text-white outline-none transition-[border-color,box-shadow] focus:border-white/24 focus:shadow-[0_0_20px_rgba(99,102,241,0.12)]';
const SETTINGS_PRIMARY_BUTTON_CLASS = 'bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white shadow-[0_0_15px_rgba(139,92,246,0.3)] rounded-lg px-6 py-2.5 text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50';
const SETTINGS_GHOST_BUTTON_CLASS = 'bg-white/5 border border-white/10 text-white/70 hover:bg-white/10 hover:text-white rounded-lg px-5 py-2.5 text-sm font-medium transition-all';
const SEGMENT_WRAPPER_CLASS = 'inline-flex rounded-xl border border-white/10 bg-white/[0.02] p-1';
const SEGMENT_BUTTON_CLASS = 'min-w-[4.5rem] rounded-lg px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] transition-colors';
const OPTION_GROUP_WRAPPER_CLASS = 'mt-3 grid gap-2 sm:grid-cols-3';

const buildOptionButtonClass = (active: boolean) => (
  active
    ? 'w-full rounded-lg border border-white/10 bg-white/10 px-3 py-3 text-left text-white transition-all'
    : `w-full text-left ${SETTINGS_GHOST_BUTTON_CLASS}`
);

const MARKET_COLOR_OPTIONS: Array<{
  value: MarketColorConvention;
  labelKey: string;
  descriptionKey: string;
}> = [
  {
    value: 'redDownGreenUp',
    labelKey: 'settings.marketColorConventional',
    descriptionKey: 'settings.marketColorConventionalDesc',
  },
  {
    value: 'redUpGreenDown',
    labelKey: 'settings.marketColorCn',
    descriptionKey: 'settings.marketColorCnDesc',
  },
];

const DATA_DENSITY_OPTIONS = [
  { value: 'compact', labelKey: 'settings.dataDensityCompact', descriptionKey: 'settings.dataDensityCompactDesc' },
  { value: 'comfortable', labelKey: 'settings.dataDensityComfortable', descriptionKey: 'settings.dataDensityComfortableDesc' },
  { value: 'relaxed', labelKey: 'settings.dataDensityRelaxed', descriptionKey: 'settings.dataDensityRelaxedDesc' },
] as const;

const NUMBER_FORMAT_OPTIONS = [
  { value: 'international', labelKey: 'settings.numberFormatInternational', descriptionKey: 'settings.numberFormatInternationalDesc' },
  { value: 'zh', labelKey: 'settings.numberFormatZh', descriptionKey: 'settings.numberFormatZhDesc' },
  { value: 'full', labelKey: 'settings.numberFormatFull', descriptionKey: 'settings.numberFormatFullDesc' },
] as const;

const PersonalSettingsPage: React.FC = () => {
  const { language, setLanguage, t } = useI18n();
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
    isGuest,
    loggedIn,
    currentUser,
  } = useProductSurface();
  const [notificationPrefs, setNotificationPrefs] = useState<UserNotificationPreferences | null>(null);
  const [notificationEmail, setNotificationEmail] = useState('');
  const [notificationEmailEnabled, setNotificationEmailEnabled] = useState(false);
  const [notificationDiscordEnabled, setNotificationDiscordEnabled] = useState(false);
  const [notificationDiscordWebhook, setNotificationDiscordWebhook] = useState('');
  const [notificationLoading, setNotificationLoading] = useState(false);
  const [notificationSaving, setNotificationSaving] = useState(false);
  const [notificationError, setNotificationError] = useState<ParsedApiError | null>(null);
  const [notificationNotice, setNotificationNotice] = useState<string | null>(null);
  const loginPath = buildLoginPath('/settings');
  const registrationPath = buildRegistrationPath('/settings');

  useEffect(() => {
    document.title = language === 'en' ? 'Settings - WolfyStock' : '设置 - WolfyStock';
  }, [language]);

  useEffect(() => {
    if (!loggedIn) {
      setNotificationPrefs(null);
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
        setNotificationPrefs(prefs);
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
      setNotificationPrefs(prefs);
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

  return (
    <section
      data-testid="personal-settings-workspace"
      className="flex w-full flex-1 min-h-0 min-w-0 flex-col gap-8"
    >
      <WorkspacePageHeader
        eyebrow={t('settings.personalEyebrow')}
        title={t('settings.personalTitle')}
        description={t('settings.personalDescription')}
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.08fr)_minmax(22rem,0.92fr)]">
        <GlassCard as="section" className="p-6 md:p-7">
          <div className="mb-5 space-y-1">
            <h2 className="text-[1.125rem] font-normal tracking-[-0.02em] text-foreground md:text-[1.25rem]">{t('settings.personalInterfaceTitle')}</h2>
            <p className="text-sm leading-6 text-muted-text">{t('settings.personalInterfaceSubtitle')}</p>
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <div className="rounded-2xl border border-white/5 bg-white/[0.02] px-4 py-4">
              <p className="text-[11px] uppercase tracking-[0.14em] font-semibold text-foreground">{t('settings.languageTitle')}</p>
              <p className="mt-1 text-xs leading-5 text-muted-text">{t('settings.languageDesc')}</p>
              <div className="mt-3">
                <div className={SEGMENT_WRAPPER_CLASS} role="tablist" aria-label={t('settings.languageTitle')}>
                <button
                  type="button"
                  onClick={() => setLanguage('zh')}
                  className={language === 'zh'
                    ? `${SEGMENT_BUTTON_CLASS} bg-white/10 text-white`
                    : `${SEGMENT_BUTTON_CLASS} text-white/70 hover:bg-white/10 hover:text-white`}
                  aria-pressed={language === 'zh'}
                >
                  {t('language.zh')}
                </button>
                <button
                  type="button"
                  onClick={() => setLanguage('en')}
                  className={language === 'en'
                    ? `${SEGMENT_BUTTON_CLASS} bg-white/10 text-white`
                    : `${SEGMENT_BUTTON_CLASS} text-white/70 hover:bg-white/10 hover:text-white`}
                  aria-pressed={language === 'en'}
                >
                  {t('language.en')}
                </button>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-white/5 bg-white/[0.02] px-4 py-4">
              <p className="text-[11px] uppercase tracking-[0.14em] font-semibold text-foreground">{t('settings.marketColorTitle')}</p>
              <p className="mt-1 text-xs leading-5 text-muted-text">{t('settings.marketColorDesc')}</p>
              <div className="mt-3 space-y-2">
                {MARKET_COLOR_OPTIONS.map((option) => {
                  const active = marketColorConvention === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setMarketColorConvention(option.value)}
                      className={buildOptionButtonClass(active)}
                      aria-pressed={active}
                    >
                      <p className="text-sm font-medium text-foreground">{t(option.labelKey)}</p>
                      <p className="mt-1 text-xs text-muted-text">{t(option.descriptionKey)}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="rounded-2xl border border-white/5 bg-white/[0.02] px-4 py-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-foreground">{t('settings.dataDensityTitle')}</p>
              <p className="mt-1 text-xs leading-5 text-muted-text">{t('settings.dataDensityDesc')}</p>
              <div className={OPTION_GROUP_WRAPPER_CLASS}>
                {DATA_DENSITY_OPTIONS.map((option) => {
                  const active = dataDensity === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setDataDensity(option.value)}
                      className={buildOptionButtonClass(active)}
                      aria-pressed={active}
                    >
                      <p className="text-sm font-medium text-foreground">{t(option.labelKey)}</p>
                      <p className="mt-1 text-xs text-muted-text">{t(option.descriptionKey)}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="rounded-2xl border border-white/5 bg-white/[0.02] px-4 py-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-foreground">{t('settings.numberFormatTitle')}</p>
              <p className="mt-1 text-xs leading-5 text-muted-text">{t('settings.numberFormatDesc')}</p>
              <div className={OPTION_GROUP_WRAPPER_CLASS}>
                {NUMBER_FORMAT_OPTIONS.map((option) => {
                  const active = numberFormat === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setNumberFormat(option.value)}
                      className={buildOptionButtonClass(active)}
                      aria-pressed={active}
                    >
                      <p className="text-sm font-medium text-foreground">{t(option.labelKey)}</p>
                      <p className="mt-1 text-xs text-muted-text">{t(option.descriptionKey)}</p>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="mt-4">
            <FontSizeSettingsCard />
          </div>
        </GlassCard>

        <GlassCard as="section" className="p-6 md:p-7">
          <div className="mb-5 space-y-1">
            <h2 className="text-[1.125rem] font-normal tracking-[-0.02em] text-foreground md:text-[1.25rem]">{t('settings.personalAccountAccessTitle')}</h2>
            <p className="text-sm leading-6 text-muted-text">{t('settings.personalAccountAccessSubtitle')}</p>
          </div>
          <div className="space-y-4">
            {isGuest && authEnabled ? (
              <div className="rounded-[var(--theme-panel-radius-md)] border border-[hsl(var(--accent-warning-hsl)/0.28)] bg-[hsl(var(--accent-warning-hsl)/0.12)] px-4 py-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[hsl(var(--accent-warning-hsl)/0.32)] bg-[hsl(var(--accent-warning-hsl)/0.18)] text-[hsl(var(--accent-warning-hsl))]">
                    <LockKeyhole className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {t('settings.personalGuestPreferencesTitle')}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-secondary-text">
                      {t('settings.personalGuestPreferencesBody')}
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  <Link
                    to={loginPath}
                    className="inline-flex min-h-[40px] items-center justify-center rounded-[var(--theme-button-radius)] border border-white/12 bg-white px-4 text-[0.75rem] text-black transition-colors hover:border-white/30 hover:bg-white/92"
                  >
                    {t('settings.personalGuestSignInAction')}
                  </Link>
                  <Link
                    to={registrationPath}
                    className="inline-flex min-h-[40px] items-center justify-center rounded-[var(--theme-button-radius)] border border-[var(--border-muted)] bg-[var(--pill-bg)] px-4 text-[0.75rem] text-secondary-text transition-colors hover:border-[var(--border-strong)] hover:text-foreground"
                  >
                    {t('settings.personalGuestCreateAccountAction')}
                  </Link>
                </div>
              </div>
            ) : null}

            {!isGuest ? (
              <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-4 py-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/6 text-foreground">
                    <ShieldCheck className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {t('settings.personalSignedInAs', {
                        name: currentUser?.displayName || currentUser?.username || t('settings.personalFallbackUser'),
                      })}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-secondary-text">
                      {t('settings.personalSignedInBody')}
                    </p>
                  </div>
                </div>
              </div>
            ) : null}

            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-4 py-4">
                <div className="flex items-center gap-3">
                  <BellRing className="h-4 w-4 text-foreground" />
                  <p className="text-sm font-semibold text-foreground">
                    {t('settings.personalNotificationScopeTitle')}
                  </p>
                </div>
                {loggedIn ? (
                  <div className="mt-3 space-y-3">
                    <p className="text-xs leading-5 text-secondary-text">
                      {t('settings.personalNotificationScopeBody')}
                    </p>
                    <label className="flex items-center gap-3 text-xs text-secondary-text">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border border-[var(--border-muted)] bg-transparent"
                        checked={notificationEmailEnabled}
                        onChange={(event) => setNotificationEmailEnabled(event.target.checked)}
                        disabled={notificationLoading || notificationSaving}
                      />
                      <span>{t('settings.personalNotificationEmailToggle')}</span>
                    </label>
                    <label className="block">
                      <span className="theme-field-label">{t('settings.personalNotificationEmailLabel')}</span>
                      <input
                        type="email"
                        value={notificationEmail}
                        onChange={(event) => setNotificationEmail(event.target.value)}
                        placeholder={t('settings.personalNotificationEmailPlaceholder')}
                        disabled={notificationLoading || notificationSaving}
                        className={`mt-2 ${GLASS_INPUT_CLASS}`}
                      />
                    </label>
                    {!notificationPrefs?.emailDeliveryAvailable ? (
                      <p className="text-xs leading-5 text-secondary-text">
                        {t('settings.personalNotificationEmailUnavailable')}
                      </p>
                    ) : null}
                    <label className="flex items-center gap-3 text-xs text-secondary-text">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border border-[var(--border-muted)] bg-transparent"
                        checked={notificationDiscordEnabled}
                        onChange={(event) => setNotificationDiscordEnabled(event.target.checked)}
                        disabled={notificationLoading || notificationSaving}
                      />
                      <span>{t('settings.personalNotificationDiscordToggle')}</span>
                    </label>
                    <label className="block">
                      <span className="theme-field-label">{t('settings.personalNotificationDiscordLabel')}</span>
                      <input
                        type="url"
                        value={notificationDiscordWebhook}
                        onChange={(event) => setNotificationDiscordWebhook(event.target.value)}
                        placeholder="https://discord.com/api/webhooks/..."
                        disabled={notificationLoading || notificationSaving}
                        className={`mt-2 ${GLASS_INPUT_CLASS}`}
                      />
                    </label>
                    <p className="text-xs leading-5 text-secondary-text">
                      {t('settings.personalNotificationDiscordHint')}
                    </p>
                    {notificationNotice ? (
                      <p className="text-xs leading-5 text-[hsl(var(--accent-positive-hsl))]">{notificationNotice}</p>
                    ) : null}
                    {notificationError ? <ApiErrorAlert error={notificationError} /> : null}
                    <button
                      type="button"
                      onClick={() => void handleSaveNotificationPreferences()}
                      disabled={notificationLoading || notificationSaving}
                      className={SETTINGS_PRIMARY_BUTTON_CLASS}
                    >
                      {notificationSaving ? t('settings.personalNotificationSaving') : t('settings.personalNotificationSaveAction')}
                    </button>
                  </div>
                ) : (
                  <p className="mt-2 text-xs leading-5 text-secondary-text">
                    {language === 'en'
                      ? 'Notification channels are still managed in admin settings. Personal preferences stay lightweight here.'
                      : '本阶段仍将通知通道内部配置保留在管理员控制面，个人偏好在这里保持轻量。'}
                  </p>
                )}
              </div>
              <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-4 py-4">
                <div className="flex items-center gap-3">
                  <ShieldCheck className="h-4 w-4 text-foreground" />
                  <p className="text-sm font-semibold text-foreground">
                    {language === 'en' ? 'System settings stay separate' : '系统分层保持清晰'}
                  </p>
                </div>
                <p className="mt-2 text-xs leading-5 text-secondary-text">
                  {language === 'en'
                    ? 'Normal users only see local preferences here. System controls stay out of the default settings page.'
                    : '普通用户在这里仅看到无害的本地偏好，系统级开关不会再出现在默认设置面。'}
                </p>
              </div>
            </div>
          </div>
        </GlassCard>
      </div>

      {loggedIn && passwordChangeable ? <ChangePasswordCard /> : null}
    </section>
  );
};

export default PersonalSettingsPage;
