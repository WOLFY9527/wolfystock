import type React from 'react';
import { useState } from 'react';
import type { ParsedApiError } from '../../api/error';
import { isParsedApiError } from '../../api/error';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useAuth } from '../../hooks';
import { Input } from '../common';
import { SettingsAlert } from './SettingsAlert';
import { TerminalButton } from '../terminal';

export const ChangePasswordCard: React.FC = () => {
  const { language, t } = useI18n();
  const { changePassword } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('');
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | ParsedApiError | null>(null);
  const [success, setSuccess] = useState(false);

  const successMessage = language === 'en'
    ? 'Your account password has been updated.'
    : '当前账户密码已更新。';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (!currentPassword.trim()) {
      setError(t('settings.passwordErrorCurrentRequired'));
      return;
    }
    if (!newPassword.trim()) {
      setError(t('settings.passwordErrorNewRequired'));
      return;
    }
    if (newPassword.length < 6) {
      setError(t('settings.passwordErrorTooShort'));
      return;
    }
    if (newPassword !== newPasswordConfirm) {
      setError(t('settings.passwordErrorMismatch'));
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await changePassword(currentPassword, newPassword, newPasswordConfirm);
      if (result.success) {
        setSuccess(true);
        setCurrentPassword('');
        setNewPassword('');
        setNewPasswordConfirm('');
        setTimeout(() => setSuccess(false), 4000);
      } else {
        setError(result.error ?? t('settings.passwordErrorGeneric'));
      }
    } finally {
      setIsSubmitting(false);
    }
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
            onChange={(e) => setCurrentPassword(e.target.value)}
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
            onChange={(e) => setNewPassword(e.target.value)}
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
            onChange={(e) => setNewPasswordConfirm(e.target.value)}
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
