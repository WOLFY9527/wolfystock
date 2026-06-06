import type React from 'react';
import { useReducer, useState, type SetStateAction } from 'react';
import { authApi } from '../../api/auth';
import { getParsedApiError, isParsedApiError, type ParsedApiError } from '../../api/error';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useAuth } from '../../hooks/useAuth';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { Input } from '../common/Input';
import { Checkbox } from '../common/Checkbox';
import { SettingsAlert } from './SettingsAlert';
import { SettingsSectionCard } from './SettingsSectionCard';

function createNextModeLabel(
  authEnabled: boolean,
  desiredEnabled: boolean,
  t: (key: string, vars?: Record<string, string | number | undefined>) => string,
) {
  if (authEnabled && !desiredEnabled) {
    return t('settings.authTurnOff');
  }
  if (!authEnabled && desiredEnabled) {
    return t('settings.authTurnOn');
  }
  return authEnabled ? t('settings.authKeepOn') : t('settings.authKeepOff');
}

type AuthFormState = {
  currentPassword: string;
  password: string;
  passwordConfirm: string;
  isSubmitting: boolean;
  error: string | ParsedApiError | null;
  successMessage: string | null;
};

type AuthFormAction =
  | { type: 'setCurrentPassword'; value: string }
  | { type: 'setPassword'; value: string }
  | { type: 'setPasswordConfirm'; value: string }
  | { type: 'setError'; error: string | ParsedApiError | null }
  | { type: 'submitStarted' }
  | { type: 'submitSucceeded'; message: string }
  | { type: 'submitFailed'; error: ParsedApiError }
  | { type: 'clearMessagesAndResetForm' };

const INITIAL_AUTH_FORM_STATE: AuthFormState = {
  currentPassword: '',
  password: '',
  passwordConfirm: '',
  isSubmitting: false,
  error: null,
  successMessage: null,
};

function resetAuthFormFields(state: AuthFormState): AuthFormState {
  return {
    ...state,
    currentPassword: '',
    password: '',
    passwordConfirm: '',
  };
}

function authFormReducer(state: AuthFormState, action: AuthFormAction): AuthFormState {
  switch (action.type) {
    case 'setCurrentPassword':
      return { ...state, currentPassword: action.value };
    case 'setPassword':
      return { ...state, password: action.value };
    case 'setPasswordConfirm':
      return { ...state, passwordConfirm: action.value };
    case 'setError':
      return { ...state, error: action.error };
    case 'submitStarted':
      return { ...state, isSubmitting: true, error: null, successMessage: null };
    case 'submitSucceeded':
      return resetAuthFormFields({
        ...state,
        isSubmitting: false,
        error: null,
        successMessage: action.message,
      });
    case 'submitFailed':
      return { ...state, isSubmitting: false, error: action.error };
    case 'clearMessagesAndResetForm':
      return resetAuthFormFields({ ...state, error: null, successMessage: null });
    default:
      return state;
  }
}

export const AuthSettingsCard: React.FC = () => {
  const { t } = useI18n();
  const { authEnabled, setupState, refreshStatus } = useAuth();
  const desiredEnabledSource = authEnabled ? 'enabled' : 'disabled';
  const [desiredEnabledState, setDesiredEnabledState] = useState(() => ({
    source: desiredEnabledSource,
    value: authEnabled,
  }));
  const desiredEnabled = desiredEnabledState.source === desiredEnabledSource
    ? desiredEnabledState.value
    : authEnabled;
  const setDesiredEnabled = (updater: SetStateAction<boolean>) => {
    setDesiredEnabledState((previousState) => {
      const baseValue = previousState.source === desiredEnabledSource
        ? previousState.value
        : authEnabled;
      const nextValue = typeof updater === 'function'
        ? (updater as (previousValue: boolean) => boolean)(baseValue)
        : updater;
      return {
        source: desiredEnabledSource,
        value: nextValue,
      };
    });
  };
  const [formState, dispatchForm] = useReducer(authFormReducer, INITIAL_AUTH_FORM_STATE);
  const {
    currentPassword,
    password,
    passwordConfirm,
    isSubmitting,
    error,
    successMessage,
  } = formState;

  const isDirty = desiredEnabled !== authEnabled || currentPassword || password || passwordConfirm;
  const targetActionLabel = createNextModeLabel(authEnabled, desiredEnabled, t);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    // Initial setup validation
    if (setupState === 'no_password' && desiredEnabled) {
      if (!password) {
        dispatchForm({ type: 'setError', error: t('settings.authErrorPasswordRequired') });
        return;
      }
      if (password !== passwordConfirm) {
        dispatchForm({ type: 'setError', error: t('settings.authErrorPasswordMismatch') });
        return;
      }
    }

    dispatchForm({ type: 'submitStarted' });
    try {
      await authApi.updateSettings(
        desiredEnabled,
        password.trim() || undefined,
        passwordConfirm.trim() || undefined,
        currentPassword.trim() || undefined,
      );
      await refreshStatus();
      dispatchForm({
        type: 'submitSucceeded',
        message: desiredEnabled ? t('settings.authUpdateSuccess') : t('settings.authDisabledSuccess'),
      });
    } catch (err: unknown) {
      dispatchForm({ type: 'submitFailed', error: getParsedApiError(err) });
    }
  };

  return (
    <SettingsSectionCard
      title={t('settings.authTitle')}
      actions={
        <Badge variant={authEnabled ? 'success' : 'default'} size="sm">
          {authEnabled ? t('settings.authEnabled') : t('settings.authDisabled')}
        </Badge>
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="rounded-xl border border-border/50 bg-muted/20 p-4 shadow-soft-card-strong transition-all hover:bg-muted/30">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-semibold text-foreground">{t('settings.authMode')}</p>
            </div>
            <Checkbox
              checked={desiredEnabled}
              disabled={isSubmitting}
              label={desiredEnabled ? t('settings.authTurnOn') : t('settings.authTurnOff')}
              onChange={(event) => setDesiredEnabled(event.target.checked)}
              containerClassName="bg-muted/30 border border-border/50 rounded-full px-4 py-2 shadow-soft-card-strong transition-all hover:bg-muted/40"
            />
          </div>
        </div>

        {/* Password input fields logic based on setupState and desiredEnabled */}
        {(desiredEnabled || (authEnabled && !desiredEnabled)) && (
          <div className="grid gap-4 md:grid-cols-2">
            {/* Show Current Password if we have one and we're either re-enabling or turning off */}
            {(setupState === 'password_retained' && desiredEnabled) || 
             (setupState === 'enabled' && !desiredEnabled) ? (
              <div className="space-y-3">
                <Input
                  label={t('settings.authCurrentPassword')}
                  type="password"
                  allowTogglePassword
                  iconType="password"
                  value={currentPassword}
                  onChange={(event) => dispatchForm({ type: 'setCurrentPassword', value: event.target.value })}
                  autoComplete="current-password"
                  disabled={isSubmitting}
                  placeholder={t('settings.authCurrentPasswordPlaceholder')}
                />
              </div>
            ) : null}

            {/* Show New Password fields only during initial setup */}
            {setupState === 'no_password' && desiredEnabled ? (
              <>
                <div className="space-y-3">
                  <Input
                    label={t('settings.authNewPassword')}
                    type="password"
                    allowTogglePassword
                    iconType="password"
                    value={password}
                    onChange={(event) => dispatchForm({ type: 'setPassword', value: event.target.value })}
                    autoComplete="new-password"
                    disabled={isSubmitting}
                    placeholder={t('settings.authNewPasswordPlaceholder')}
                  />
                </div>
                <div className="space-y-3">
                  <Input
                    label={t('settings.authConfirmPassword')}
                    type="password"
                    allowTogglePassword
                    iconType="password"
                    value={passwordConfirm}
                    onChange={(event) => dispatchForm({ type: 'setPasswordConfirm', value: event.target.value })}
                    autoComplete="new-password"
                    disabled={isSubmitting}
                    placeholder={t('settings.authConfirmPasswordPlaceholder')}
                  />
                </div>
              </>
            ) : null}
          </div>
        )}

        {error ? (
          isParsedApiError(error) ? (
            <SettingsAlert
              title={t('settings.authErrorTitle')}
              message={error.message}
              variant="error"
            />
          ) : (
            <SettingsAlert title={t('settings.authErrorTitle')} message={error} variant="error" />
          )
        ) : null}

        {successMessage ? (
          <SettingsAlert title={t('settings.success')} message={successMessage} variant="success" />
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" variant="settings-primary" isLoading={isSubmitting} disabled={!isDirty}>
            {targetActionLabel}
          </Button>
          <Button
            type="button"
            variant="settings-secondary"
            onClick={() => {
              setDesiredEnabled(authEnabled);
              dispatchForm({ type: 'clearMessagesAndResetForm' });
            }}
            disabled={isSubmitting || !isDirty}
          >
            {t('settings.authReset')}
          </Button>
        </div>
      </form>
    </SettingsSectionCard>
  );
};
