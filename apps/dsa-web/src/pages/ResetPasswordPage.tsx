import type React from 'react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Button, Input } from '../components/common/Button';
import { SettingsAlert } from '../components/settings';
import { authApi } from '../api/auth';
import { getParsedApiError } from '../api/error';
import { translate, type UiLanguage } from '../i18n/core';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';

type ResetLanguage = UiLanguage;

function resetCopy(language: ResetLanguage, key: string, vars?: Record<string, string | number | undefined>): string {
  return translate(language, `auth.reset.${key}`, vars);
}

const ResetPasswordPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const routeLanguage = parseLocaleFromPathname(window.location.pathname);
  const language: ResetLanguage = routeLanguage === 'en' ? 'en' : 'zh';
  const loginPath = routeLanguage ? buildLocalizedPath('/login', routeLanguage) : '/login';
  const loginPathWithRedirect = (() => {
    const redirect = searchParams.get('redirect');
    if (!redirect) {
      return loginPath;
    }
    const suffix = `?redirect=${encodeURIComponent(redirect)}`;
    return routeLanguage ? buildLocalizedPath(`/login${suffix}`, routeLanguage) : `/login${suffix}`;
  })();

  const [identifier, setIdentifier] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = resetCopy(language, 'documentTitle');
  }, [language]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = identifier.trim();
    setError(null);
    setSuccess(null);

    if (!trimmed) {
      setError(resetCopy(language, 'validationRequired'));
      return;
    }

    setSubmitting(true);
    try {
      const response = await authApi.requestPasswordReset({ identifier: trimmed });
      setSuccess(response.message || resetCopy(language, 'successBody'));
    } catch (requestError: unknown) {
      setError(getParsedApiError(requestError).message || resetCopy(language, 'validationRequired'));
    }
    setSubmitting(false);
  };

  return (
    <main className="auth-screen">
      <div className="auth-screen__backdrop" aria-hidden="true" />
      <div className="auth-screen__grid" aria-hidden="true" />

      <div className="auth-shell">
        <section className="auth-hero">
          <p className="auth-hero__eyebrow">{resetCopy(language, 'eyebrow')}</p>
          <h1 className="auth-hero__title">{resetCopy(language, 'title')}</h1>
          <p className="auth-hero__body">{resetCopy(language, 'body')}</p>
        </section>

        <section className="auth-panel theme-panel-glass">
          <form onSubmit={handleSubmit} className="auth-form">
            <Input
              id="identifier"
              type="text"
              label={resetCopy(language, 'identifierLabel')}
              placeholder={resetCopy(language, 'identifierPlaceholder')}
              value={identifier}
              onChange={(event) => setIdentifier(event.target.value)}
              disabled={submitting}
              autoFocus
              autoComplete="username"
            />

            {success ? (
              <SettingsAlert
                title={resetCopy(language, 'successTitle')}
                message={success}
                variant="success"
              />
            ) : null}

            {error ? (
              <SettingsAlert
                title={resetCopy(language, 'title')}
                message={error}
                variant="error"
              />
            ) : null}

            <Button
              type="submit"
              variant="primary"
              size="xl"
              className="w-full justify-center"
              disabled={submitting}
              isLoading={submitting}
              loadingText={resetCopy(language, 'submitting')}
            >
              {resetCopy(language, 'submit')}
            </Button>

            <div className="flex justify-center">
              <Link className="text-sm font-medium text-[var(--brand-primary)] hover:underline" to={loginPathWithRedirect}>
                {resetCopy(language, 'backToLogin')}
              </Link>
            </div>
          </form>

          <div className="auth-panel__foot">
            <button
              type="button"
              className="btn-ghost w-full justify-center"
              onClick={() => navigate(loginPathWithRedirect, { replace: true })}
              disabled={submitting}
            >
              {resetCopy(language, 'backToLogin')}
            </button>
          </div>
        </section>
      </div>
    </main>
  );
};

export default ResetPasswordPage;
