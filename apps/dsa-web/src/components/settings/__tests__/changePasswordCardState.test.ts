import { describe, expect, it } from 'vitest';
import type { ParsedApiError } from '../../../api/error';
import {
  changePasswordCardReducer,
  createInitialChangePasswordCardState,
  validateChangePasswordForm,
} from '../changePasswordCardState';

describe('changePasswordCardState', () => {
  const t = (key: string) => key;

  it('validates required password fields before submit', () => {
    expect(validateChangePasswordForm({
      currentPassword: '',
      newPassword: 'new-pass',
      newPasswordConfirm: 'new-pass',
      t,
    })).toBe('settings.passwordErrorCurrentRequired');

    expect(validateChangePasswordForm({
      currentPassword: 'current-pass',
      newPassword: '',
      newPasswordConfirm: 'new-pass',
      t,
    })).toBe('settings.passwordErrorNewRequired');

    expect(validateChangePasswordForm({
      currentPassword: 'current-pass',
      newPassword: '12345',
      newPasswordConfirm: '12345',
      t,
    })).toBe('settings.passwordErrorTooShort');

    expect(validateChangePasswordForm({
      currentPassword: 'current-pass',
      newPassword: 'new-pass',
      newPasswordConfirm: 'other-pass',
      t,
    })).toBe('settings.passwordErrorMismatch');
  });

  it('clears form fields and marks success after a successful submit', () => {
    const state = {
      ...createInitialChangePasswordCardState(),
      currentPassword: 'current-pass',
      newPassword: 'new-pass',
      newPasswordConfirm: 'new-pass',
      isSubmitting: true,
      error: 'previous-error',
    };

    expect(changePasswordCardReducer(state, { type: 'submit-succeeded' })).toEqual({
      ...createInitialChangePasswordCardState(),
      success: true,
    });
  });

  it('stores api errors and exits the submitting state', () => {
    const apiError = {
      message: 'Nope',
      status: 400,
      details: null,
    } as ParsedApiError;

    const state = {
      ...createInitialChangePasswordCardState(),
      isSubmitting: true,
    };

    expect(changePasswordCardReducer(state, {
      type: 'submit-failed',
      error: apiError,
    })).toEqual({
      ...createInitialChangePasswordCardState(),
      error: apiError,
    });
  });
});
