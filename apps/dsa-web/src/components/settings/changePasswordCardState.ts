import type { ParsedApiError } from '../../api/error';

export type ChangePasswordCardState = {
  currentPassword: string;
  newPassword: string;
  newPasswordConfirm: string;
  isSubmitting: boolean;
  error: string | ParsedApiError | null;
  success: boolean;
};

type ChangePasswordCardAction =
  | { type: 'current-password-changed'; value: string }
  | { type: 'new-password-changed'; value: string }
  | { type: 'new-password-confirm-changed'; value: string }
  | { type: 'submit-started' }
  | { type: 'submit-succeeded' }
  | { type: 'submit-failed'; error: string | ParsedApiError }
  | { type: 'submit-aborted' }
  | { type: 'success-reset' };

const EMPTY_CHANGE_PASSWORD_CARD_STATE: ChangePasswordCardState = {
  currentPassword: '',
  newPassword: '',
  newPasswordConfirm: '',
  isSubmitting: false,
  error: null,
  success: false,
};

export function createInitialChangePasswordCardState(): ChangePasswordCardState {
  return EMPTY_CHANGE_PASSWORD_CARD_STATE;
}

export function changePasswordCardReducer(
  state: ChangePasswordCardState,
  action: ChangePasswordCardAction,
): ChangePasswordCardState {
  switch (action.type) {
    case 'current-password-changed':
      return {
        ...state,
        currentPassword: action.value,
      };
    case 'new-password-changed':
      return {
        ...state,
        newPassword: action.value,
      };
    case 'new-password-confirm-changed':
      return {
        ...state,
        newPasswordConfirm: action.value,
      };
    case 'submit-started':
      return {
        ...state,
        isSubmitting: true,
        error: null,
        success: false,
      };
    case 'submit-succeeded':
      return {
        ...EMPTY_CHANGE_PASSWORD_CARD_STATE,
        success: true,
      };
    case 'submit-failed':
      return {
        ...state,
        isSubmitting: false,
        error: action.error,
        success: false,
      };
    case 'submit-aborted':
      return {
        ...state,
        isSubmitting: false,
      };
    case 'success-reset':
      return {
        ...state,
        success: false,
      };
    default:
      return state;
  }
}

export function validateChangePasswordForm({
  currentPassword,
  newPassword,
  newPasswordConfirm,
  t,
}: {
  currentPassword: string;
  newPassword: string;
  newPasswordConfirm: string;
  t: (key: string) => string;
}) {
  if (!currentPassword.trim()) {
    return t('settings.passwordErrorCurrentRequired');
  }
  if (!newPassword.trim()) {
    return t('settings.passwordErrorNewRequired');
  }
  if (newPassword.length < 6) {
    return t('settings.passwordErrorTooShort');
  }
  if (newPassword !== newPasswordConfirm) {
    return t('settings.passwordErrorMismatch');
  }
  return null;
}
