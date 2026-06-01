import type React from 'react';
import { useReducer } from 'react';
import { isParsedApiError } from '../../api/error';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useAuth } from '../../hooks/useAuth';
import { Input } from '../common/Input';
import { SettingsAlert } from './SettingsAlert';
import { TerminalButton } from '../terminal/TerminalPrimitives';
import {
  changePasswordCardReducer,
  createInitialChangePasswordCardState,
  validateChangePasswordForm,
} from './changePasswordCardState';

export const ChangePasswordCard: React.FC = () => {
  const { language, t } = useI18n();
  const { changePassword } = useAuth();
  const [state, dispatch] = useReducer(
    changePasswordCardReducer,
    undefined,
    createInitialChangePasswordCardState,
  );
  const {
    currentPassword,
    newPassword,
    newPasswordConfirm,
    isSubmitting,
    error,
    success,
  } = state;

  const successMessage = language === 'en'
    ? 'Your account password has been updated.'
    : '当前账户密码已更新。';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validationError = validateChangePasswordForm({
      currentPassword,
      newPassword,
      newPasswordConfirm,
      t,
    });

    if (validationError) {
      dispatch({ type: 'submit-failed', error: validationError });
      return;
    }

    dispatch({ type: 'submit-started' });

    let result;
    try {
      result = await changePassword(currentPassword, newPassword, newPasswordConfirm);
    } catch (requestError) {
      dispatch({ type: 'submit-aborted' });
      throw requestError;
    }

    if (result.success) {
      dispatch({ type: 'submit-succeeded' });
      window.setTimeout(() => dispatch({ type: 'success-reset' }), 4000);
      return;
    }

    dispatch({
      type: 'submit-failed',
      error: result.error ?? t('settings.passwordErrorGeneric'),
    });
  };

  return (
    <div data-testid="change-password-card" className="grid gap-3 p-4 md:grid-cols-[180px_minmax(0,1fr)] xl:grid-cols-[220px_minmax(0,1fr)]">
      <div className="min-w-0">
        <p className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">{t('settings.passwordTitle')}</p>
        <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
          {language === 'en' ? 'Rotate your account password without leaving personal settings.' : '在个人设置内直接完成账户密码轮换。'}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="min-w-0 space-y-3 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
        <div className="grid gap-3 lg:grid-cols-2">
          <Input
            id="change-pass-current"
            type="password"
            allowTogglePassword
            iconType="password"
            label={t('settings.passwordCurrent')}
            placeholder={t('settings.passwordCurrentPlaceholder')}
            value={currentPassword}
            onChange={(e) => dispatch({ type: 'current-password-changed', value: e.target.value })}
            disabled={isSubmitting}
            autoComplete="current-password"
          />

          <Input
            id="change-pass-new"
            type="password"
            allowTogglePassword
            iconType="password"
            label={t('settings.passwordNew')}
            placeholder={t('settings.passwordNewPlaceholder')}
            value={newPassword}
            onChange={(e) => dispatch({ type: 'new-password-changed', value: e.target.value })}
            disabled={isSubmitting}
            autoComplete="new-password"
          />
        </div>

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <Input
            id="change-pass-confirm"
            type="password"
            allowTogglePassword
            iconType="password"
            label={t('settings.passwordConfirm')}
            placeholder={t('settings.passwordConfirmPlaceholder')}
            value={newPasswordConfirm}
            onChange={(e) => dispatch({ type: 'new-password-confirm-changed', value: e.target.value })}
            disabled={isSubmitting}
            autoComplete="new-password"
          />

          <TerminalButton type="submit" variant="primary" disabled={isSubmitting} className="w-full lg:w-auto">
            {isSubmitting ? t('common.processing') : t('settings.passwordSave')}
          </TerminalButton>
        </div>

        {error
          ? isParsedApiError(error)
            ? <SettingsAlert title={t('settings.passwordErrorTitle')} message={error.message} variant="error" className="!mt-3" />
            : <SettingsAlert title={t('settings.passwordErrorTitle')} message={error} variant="error" className="!mt-3" />
          : null}
        {success ? (
          <SettingsAlert title={t('settings.passwordSuccessTitle')} message={successMessage} variant="success" />
        ) : null}
      </form>
    </div>
  );
};
