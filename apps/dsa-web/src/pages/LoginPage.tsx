import type React from 'react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../components/common/Button';
import { Input } from '../components/common/Input';
import type { ParsedApiError } from '../api/error';
import { isParsedApiError } from '../api/error';
import { SettingsAlert } from '../components/settings/SettingsAlert';
import { useAuth } from '../hooks/useAuth';
import { resolveAuthRedirect } from '../hooks/useProductSurface';
import { translate, type UiLanguage } from '../i18n/core';
import { buildLocalizedPath, parseLocaleFromPathname, stripLocalePrefix } from '../utils/localeRouting';

type LoginLanguage = UiLanguage;

type LoginCopy = {
  documentTitle: string;
  shellProductName: string;
  shellProductTagline: string;
  shellGuestStatus: string;
  shellGuestHintLogin: string;
  shellGuestHintCreate: string;
  shellGuestHintSetup: string;
  shellReturnHint: string;
  heroEyebrow: string;
  heroTitleSetup: string;
  heroTitleCreate: string;
  heroTitleLogin: string;
  heroBodySetup: string;
  heroBodyCreate: string;
  heroBodyLogin: string;
  panelEyebrowSetup: string;
  panelEyebrowCreate: string;
  panelEyebrowLogin: string;
  panelTitleSetup: string;
  panelTitleCreate: string;
  panelTitleLogin: string;
  panelBodySetup: string;
  panelBodyCreate: string;
  panelBodyLogin: string;
  usernameLabel: string;
  usernamePlaceholderCreate: string;
  usernamePlaceholderLogin: string;
  displayNameLabel: string;
  displayNamePlaceholder: string;
  passwordLabelSetup: string;
  passwordLabelLogin: string;
  passwordPlaceholderSetup: string;
  passwordPlaceholderLogin: string;
  passwordConfirmLabel: string;
  passwordConfirmPlaceholderSetup: string;
  passwordConfirmPlaceholderLogin: string;
  errorUsernameRequired: string;
  errorPasswordMismatch: string;
  errorLoginFailed: string;
  errorTitleSetup: string;
  errorTitleDefault: string;
  loadingTextSetup: string;
  loadingTextCreate: string;
  loadingTextLogin: string;
  submitSetup: string;
  submitCreate: string;
  submitLogin: string;
  returnToGuest: string;
  toggleToLogin: string;
  toggleToCreate: string;
  forgotPassword: string;
};

function auth(language: LoginLanguage, key: string, vars?: Record<string, string | number | undefined>): string {
  return translate(language, `auth.login.${key}`, vars);
}

function buildLoginCopy(language: LoginLanguage): LoginCopy {
  return {
    documentTitle: auth(language, 'documentTitle'),
    shellProductName: language === 'en' ? 'WolfyStock Research OS' : 'WolfyStock 研究工作台',
    shellProductTagline: language === 'en' ? 'Guest preview remains available while you sign in.' : '登录前仍可回到游客预览继续观察。',
    shellGuestStatus: language === 'en' ? 'Guest preview ready' : '游客预览已就绪',
    shellGuestHintLogin: language === 'en' ? 'Sign in to reopen saved research context and personal settings.' : '登录后可继续上次研究现场，并恢复个人偏好。',
    shellGuestHintCreate: language === 'en' ? 'Create an account to save research context, alerts, and delivery targets.' : '注册后可保存研究上下文、提醒与通知目标。',
    shellGuestHintSetup: language === 'en' ? 'Finish the initial setup, or return to the guest route to keep exploring public-safe previews.' : '完成初始化后即可启用账号，也可以先返回游客路由继续查看公开预览。',
    shellReturnHint: language === 'en' ? 'Need the read-only route first?' : '需要先回到只读游客路由？',
    heroEyebrow: auth(language, 'heroEyebrow'),
    heroTitleSetup: auth(language, 'heroTitleSetup'),
    heroTitleCreate: auth(language, 'heroTitleCreate'),
    heroTitleLogin: auth(language, 'heroTitleLogin'),
    heroBodySetup: auth(language, 'heroBodySetup'),
    heroBodyCreate: auth(language, 'heroBodyCreate'),
    heroBodyLogin: auth(language, 'heroBodyLogin'),
    panelEyebrowSetup: auth(language, 'panelEyebrowSetup'),
    panelEyebrowCreate: auth(language, 'panelEyebrowCreate'),
    panelEyebrowLogin: auth(language, 'panelEyebrowLogin'),
    panelTitleSetup: auth(language, 'panelTitleSetup'),
    panelTitleCreate: auth(language, 'panelTitleCreate'),
    panelTitleLogin: auth(language, 'panelTitleLogin'),
    panelBodySetup: auth(language, 'panelBodySetup'),
    panelBodyCreate: auth(language, 'panelBodyCreate'),
    panelBodyLogin: auth(language, 'panelBodyLogin'),
    usernameLabel: auth(language, 'usernameLabel'),
    usernamePlaceholderCreate: auth(language, 'usernamePlaceholderCreate'),
    usernamePlaceholderLogin: auth(language, 'usernamePlaceholderLogin'),
    displayNameLabel: auth(language, 'displayNameLabel'),
    displayNamePlaceholder: auth(language, 'displayNamePlaceholder'),
    passwordLabelSetup: auth(language, 'passwordLabelSetup'),
    passwordLabelLogin: auth(language, 'passwordLabelLogin'),
    passwordPlaceholderSetup: auth(language, 'passwordPlaceholderSetup'),
    passwordPlaceholderLogin: auth(language, 'passwordPlaceholderLogin'),
    passwordConfirmLabel: auth(language, 'passwordConfirmLabel'),
    passwordConfirmPlaceholderSetup: auth(language, 'passwordConfirmPlaceholderSetup'),
    passwordConfirmPlaceholderLogin: auth(language, 'passwordConfirmPlaceholderLogin'),
    errorUsernameRequired: auth(language, 'errorUsernameRequired'),
    errorPasswordMismatch: auth(language, 'errorPasswordMismatch'),
    errorLoginFailed: auth(language, 'errorLoginFailed'),
    errorTitleSetup: auth(language, 'errorTitleSetup'),
    errorTitleDefault: auth(language, 'errorTitleDefault'),
    loadingTextSetup: auth(language, 'loadingTextSetup'),
    loadingTextCreate: auth(language, 'loadingTextCreate'),
    loadingTextLogin: auth(language, 'loadingTextLogin'),
    submitSetup: auth(language, 'submitSetup'),
    submitCreate: auth(language, 'submitCreate'),
    submitLogin: auth(language, 'submitLogin'),
    returnToGuest: auth(language, 'returnToGuest'),
    toggleToLogin: auth(language, 'toggleToLogin'),
    toggleToCreate: auth(language, 'toggleToCreate'),
    forgotPassword: language === 'en' ? 'Forgot password?' : '忘记密码？',
  };
}

const LoginPage: React.FC = () => {
  const { authEnabled, login, setupState } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const routeLanguage = parseLocaleFromPathname(window.location.pathname);
  const routePathname = stripLocalePrefix(window.location.pathname);
  const createModeRequested = routePathname === '/register' || searchParams.get('mode') === 'create';
  const language: LoginLanguage = routeLanguage === 'en' ? 'en' : 'zh';
  const copy = buildLoginCopy(language);
  const homePath = routeLanguage ? buildLocalizedPath('/', routeLanguage) : '/';
  const postAuthPath = resolveAuthRedirect(`?${searchParams.toString()}`, homePath);
  const guestPath = routeLanguage ? buildLocalizedPath('/guest', routeLanguage) : '/guest';
  const resetPasswordPath = routeLanguage ? buildLocalizedPath('/reset-password', routeLanguage) : '/reset-password';

  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [{ createUser, routeCreateMode }, setCreateModeState] = useState(() => ({
    createUser: createModeRequested,
    routeCreateMode: createModeRequested,
  }));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | ParsedApiError | null>(null);

  const isAdminBootstrap = setupState === 'no_password';
  const isAuthReenable = !authEnabled && setupState === 'password_retained';

  if (!isAdminBootstrap && createModeRequested !== routeCreateMode) {
    setCreateModeState({
      createUser: createModeRequested,
      routeCreateMode: createModeRequested,
    });
  }

  const isCreateUserMode = authEnabled && !isAdminBootstrap && !isAuthReenable && createUser;
  const guestHint = isAdminBootstrap
    ? copy.shellGuestHintSetup
    : isCreateUserMode
      ? copy.shellGuestHintCreate
      : copy.shellGuestHintLogin;

  useEffect(() => {
    document.title = copy.documentTitle;
  }, [copy.documentTitle]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    if (!isAdminBootstrap && isCreateUserMode && !username.trim()) {
      setError(copy.errorUsernameRequired);
      return;
    }

    if ((isAdminBootstrap || isCreateUserMode) && password !== passwordConfirm) {
      setError(copy.errorPasswordMismatch);
      return;
    }

    setIsSubmitting(true);
    const [result, submitError] = await login({
      username: isAdminBootstrap || isAuthReenable ? 'admin' : (username.trim() || 'admin'),
      displayName: isCreateUserMode ? displayName.trim() : undefined,
      password,
      passwordConfirm: isAdminBootstrap || isCreateUserMode ? passwordConfirm : undefined,
      createUser: isCreateUserMode,
    }).then(
      (value) => [value, null] as const,
      (submitFailure: unknown) => [null, submitFailure] as const,
    );
    setIsSubmitting(false);

    if (result == null) {
      throw submitError;
    }

    if (result.success) {
      navigate(postAuthPath, { replace: true });
    } else {
      setError(result.error ?? copy.errorLoginFailed);
    }
  };

  return (
    <main className="auth-screen">
      <div className="auth-screen__backdrop" aria-hidden="true" />
      <div className="auth-screen__grid" aria-hidden="true" />

      <div className="auth-shell auth-shell--panel-only">
        <section className="auth-panel theme-panel-glass">
          <div className="flex items-start justify-between gap-4 rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-3">
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-[0.24em] text-white/40">{copy.heroEyebrow}</p>
              <p className="mt-2 text-sm font-semibold text-white/92">{copy.shellProductName}</p>
              <p className="mt-1 text-xs leading-6 text-white/55">{copy.shellProductTagline}</p>
            </div>
            <span className="inline-flex shrink-0 items-center rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.22em] text-emerald-100/85">
              {copy.shellGuestStatus}
            </span>
          </div>

          <div className="auth-panel__header">
            <p className="label-uppercase text-secondary-text">{copy.heroEyebrow}</p>
            <h1 className="auth-panel__title">
              <span>{isAdminBootstrap ? copy.heroTitleSetup : isCreateUserMode ? copy.heroTitleCreate : copy.heroTitleLogin}</span>
            </h1>
            <p className="auth-panel__body">{isAdminBootstrap ? copy.heroBodySetup : isCreateUserMode ? copy.heroBodyCreate : copy.heroBodyLogin}</p>
            <div className="mt-4 rounded-[18px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] px-4 py-3">
              <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-white/42">{copy.shellReturnHint}</p>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  className="inline-flex min-h-[44px] items-center justify-center rounded-full border border-white/16 bg-white/[0.06] px-4 text-sm font-semibold text-white transition hover:border-white/24 hover:bg-white/[0.1] disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={() => navigate(guestPath, { replace: true })}
                  disabled={isSubmitting}
                >
                  {copy.returnToGuest}
                </button>
                <p className="flex-1 text-xs leading-6 text-white/52">{guestHint}</p>
              </div>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            {!isAdminBootstrap && !isAuthReenable ? (
              <Input
                id="username"
                type="text"
                className="h-auto w-full bg-white/[0.03] border border-white/10 rounded-xl !px-4 py-3 text-white text-sm focus:border-white/20 outline-none transition-colors"
                label={copy.usernameLabel}
                placeholder={isCreateUserMode ? copy.usernamePlaceholderCreate : copy.usernamePlaceholderLogin}
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                disabled={isSubmitting}
                autoFocus
                autoComplete="username"
              />
            ) : null}

            {isCreateUserMode ? (
              <Input
                id="displayName"
                type="text"
                className="h-auto w-full bg-white/[0.03] border border-white/10 rounded-xl !px-4 py-3 text-white text-sm focus:border-white/20 outline-none transition-colors"
                label={copy.displayNameLabel}
                placeholder={copy.displayNamePlaceholder}
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                disabled={isSubmitting}
                autoComplete="nickname"
              />
            ) : null}

            <Input
              id="password"
              type="password"
              allowTogglePassword
              className="h-auto w-full bg-white/[0.03] border border-white/10 rounded-xl !pl-4 !pr-12 py-3 text-white text-sm focus:border-white/20 outline-none transition-colors"
              label={isAdminBootstrap ? copy.passwordLabelSetup : copy.passwordLabelLogin}
              placeholder={isAdminBootstrap ? copy.passwordPlaceholderSetup : copy.passwordPlaceholderLogin}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={isSubmitting}
              autoComplete={isAdminBootstrap || isCreateUserMode ? 'new-password' : 'current-password'}
            />

            {isAdminBootstrap || isCreateUserMode ? (
              <Input
                id="passwordConfirm"
                type="password"
                allowTogglePassword
                className="h-auto w-full bg-white/[0.03] border border-white/10 rounded-xl !pl-4 !pr-12 py-3 text-white text-sm focus:border-white/20 outline-none transition-colors"
                label={copy.passwordConfirmLabel}
                placeholder={isAdminBootstrap ? copy.passwordConfirmPlaceholderSetup : copy.passwordConfirmPlaceholderLogin}
                value={passwordConfirm}
                onChange={(event) => setPasswordConfirm(event.target.value)}
                disabled={isSubmitting}
                autoComplete="new-password"
              />
            ) : null}

            {!isAdminBootstrap && !isCreateUserMode ? (
              <div className="flex justify-end">
                <Link className="text-sm font-medium text-[var(--brand-primary)] hover:underline" to={resetPasswordPath}>
                  {copy.forgotPassword}
                </Link>
              </div>
            ) : null}

            {error ? (
              <SettingsAlert
                title={isAdminBootstrap ? copy.errorTitleSetup : copy.errorTitleDefault}
                message={isParsedApiError(error) ? error.message : error}
                variant="error"
              />
            ) : null}

            <Button
              type="submit"
              variant="primary"
              size="xl"
              className="w-full mt-2 py-3 bg-white text-black font-bold text-sm rounded-xl hover:bg-white/90 active:scale-95 transition-all justify-center"
              disabled={isSubmitting}
              isLoading={isSubmitting}
              loadingText={isAdminBootstrap ? copy.loadingTextSetup : isCreateUserMode ? copy.loadingTextCreate : copy.loadingTextLogin}
            >
              {isAdminBootstrap ? copy.submitSetup : isCreateUserMode ? copy.submitCreate : copy.submitLogin}
            </Button>

            {!isAdminBootstrap ? (
              <button
                type="button"
                className="btn-ghost w-full justify-center"
                onClick={() => {
                  setCreateModeState((current) => ({
                    ...current,
                    createUser: !current.createUser,
                  }));
                  setPasswordConfirm('');
                  setError(null);
                }}
                disabled={isSubmitting}
              >
                {isCreateUserMode ? copy.toggleToLogin : copy.toggleToCreate}
              </button>
            ) : null}

          </form>
        </section>
      </div>
    </main>
  );
};

export default LoginPage;
