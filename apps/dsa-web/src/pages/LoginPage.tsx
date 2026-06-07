import type React from 'react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../components/common/Button';
import { Input } from '../components/common/Input';
import type { ParsedApiError } from '../api/error';
import { isParsedApiError } from '../api/error';
import { SettingsAlert } from '../components/settings/SettingsAlert';
import { useAuth } from '../hooks/useAuth';
import { translate, type UiLanguage } from '../i18n/core';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';

type LoginLanguage = UiLanguage;

type LoginCopy = {
  documentTitle: string;
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
    forgotPassword: auth(language, 'forgotPassword'),
  };
}

const LoginPage: React.FC = () => {
  const { authEnabled, login, setupState } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const createModeRequested = searchParams.get('mode') === 'create';
  const routeLanguage = parseLocaleFromPathname(window.location.pathname);
  const language: LoginLanguage = routeLanguage === 'en' ? 'en' : 'zh';
  const copy = buildLoginCopy(language);
  const homePath = routeLanguage ? buildLocalizedPath('/', routeLanguage) : '/';
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
      navigate(homePath, { replace: true });
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
          <div className="auth-panel__header">
            <p className="label-uppercase text-secondary-text">{copy.heroEyebrow}</p>
            <h1 className="auth-panel__title">
              <span>{isAdminBootstrap ? copy.heroTitleSetup : isCreateUserMode ? copy.heroTitleCreate : copy.heroTitleLogin}</span>
            </h1>
            <p className="auth-panel__body">{isAdminBootstrap ? copy.heroBodySetup : isCreateUserMode ? copy.heroBodyCreate : copy.heroBodyLogin}</p>
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

            <button
              type="button"
              className="mt-6 text-xs text-white/30 hover:text-white/60 transition-colors cursor-pointer"
              onClick={() => navigate(guestPath, { replace: true })}
              disabled={isSubmitting}
            >
              {copy.returnToGuest}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
};

export default LoginPage;
