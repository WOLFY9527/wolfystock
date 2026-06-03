import { describe, expect, it } from 'vitest';
import type { ParsedApiError } from '../../api/error';
import type { UserNotificationPreferences } from '../../api/auth';
import {
  createInitialNotificationPreferencesState,
  notificationPreferencesReducer,
  toNotificationPreferenceUpdatePayload,
} from '../personalSettingsPageState';

const basePreferences: UserNotificationPreferences = {
  channel: 'multi',
  enabled: true,
  email: 'alice@example.com',
  emailEnabled: true,
  discordEnabled: true,
  discordWebhook: 'https://discord.com/api/webhooks/123/token',
  deliveryAvailable: true,
  emailDeliveryAvailable: true,
  discordDeliveryAvailable: true,
  updatedAt: '2026-04-15T10:00:00Z',
};

const baseError: ParsedApiError = {
  title: 'Request failed',
  message: 'Could not save notification targets.',
  rawMessage: 'Could not save notification targets.',
  category: 'unknown',
};

describe('personalSettingsPageState', () => {
  it('normalizes notification preferences into reducer state on load success', () => {
    const state = notificationPreferencesReducer(
      createInitialNotificationPreferencesState(),
      {
        type: 'load-succeeded',
        prefs: basePreferences,
      },
    );

    expect(state).toMatchObject({
      email: 'alice@example.com',
      emailEnabled: true,
      discordEnabled: true,
      discordWebhook: 'https://discord.com/api/webhooks/123/token',
      loading: false,
      saving: false,
      error: null,
      notice: null,
      hasLoaded: true,
    });
  });

  it('keeps the latest saved values and success notice after save', () => {
    const loadingState = notificationPreferencesReducer(
      createInitialNotificationPreferencesState(),
      {
        type: 'load-succeeded',
        prefs: {
          ...basePreferences,
          email: 'old@example.com',
          discordWebhook: 'https://discord.com/api/webhooks/old/token',
        },
      },
    );

    const state = notificationPreferencesReducer(loadingState, {
      type: 'save-succeeded',
      prefs: basePreferences,
      notice: 'Saved',
    });

    expect(state).toMatchObject({
      email: 'alice@example.com',
      emailEnabled: true,
      discordEnabled: true,
      discordWebhook: 'https://discord.com/api/webhooks/123/token',
      loading: false,
      saving: false,
      error: null,
      notice: 'Saved',
      hasLoaded: true,
    });
  });

  it('builds the update payload from trimmed local draft values', () => {
    const state = notificationPreferencesReducer(
      createInitialNotificationPreferencesState(),
      {
        type: 'load-succeeded',
        prefs: {
          ...basePreferences,
          email: ' alice@example.com ',
          discordWebhook: ' https://discord.com/api/webhooks/123/token ',
        },
      },
    );

    expect(toNotificationPreferenceUpdatePayload(state)).toEqual({
      emailEnabled: true,
      email: 'alice@example.com',
      discordEnabled: true,
      discordWebhook: 'https://discord.com/api/webhooks/123/token',
    });
  });

  it('captures load failures without mutating the current draft values', () => {
    const readyState = notificationPreferencesReducer(
      createInitialNotificationPreferencesState(),
      {
        type: 'load-succeeded',
        prefs: basePreferences,
      },
    );

    const state = notificationPreferencesReducer(readyState, {
      type: 'load-failed',
      error: baseError,
    });

    expect(state).toMatchObject({
      email: 'alice@example.com',
      discordWebhook: 'https://discord.com/api/webhooks/123/token',
      loading: false,
      saving: false,
      error: baseError,
      hasLoaded: true,
    });
  });
});
