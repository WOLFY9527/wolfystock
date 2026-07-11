import type { UserNotificationPreferences } from '../api/auth';
import type { ParsedApiError } from '../api/error';

export type NotificationPreferencesState = {
  email: string;
  emailEnabled: boolean;
  discordEnabled: boolean;
  discordWebhook: string;
  savedDiscordWebhookConfigured: boolean;
  loading: boolean;
  saving: boolean;
  error: ParsedApiError | null;
  notice: string | null;
  hasLoaded: boolean;
};

type NotificationPreferencesAction =
  | { type: 'load-succeeded'; prefs: UserNotificationPreferences }
  | { type: 'load-failed'; error: ParsedApiError }
  | { type: 'email-changed'; value: string }
  | { type: 'email-enabled-changed'; value: boolean }
  | { type: 'discord-enabled-changed'; value: boolean }
  | { type: 'discord-webhook-changed'; value: string }
  | { type: 'save-started' }
  | { type: 'save-succeeded'; prefs: UserNotificationPreferences; notice: string }
  | { type: 'save-failed'; error: ParsedApiError }
  | { type: 'reset-transient-feedback' };

const EMPTY_NOTIFICATION_PREFERENCES_STATE: NotificationPreferencesState = {
  email: '',
  emailEnabled: false,
  discordEnabled: false,
  discordWebhook: '',
  savedDiscordWebhookConfigured: false,
  loading: false,
  saving: false,
  error: null,
  notice: null,
  hasLoaded: false,
};

function normalizeNotificationPreferences(
  prefs: Pick<UserNotificationPreferences, 'email' | 'emailEnabled' | 'discordEnabled' | 'discordWebhook'>,
) {
  return {
    email: prefs.email || '',
    emailEnabled: Boolean(prefs.emailEnabled),
    discordEnabled: Boolean(prefs.discordEnabled),
    discordWebhook: '',
    savedDiscordWebhookConfigured: Boolean(prefs.discordWebhook),
  };
}

export function createInitialNotificationPreferencesState(loading = false): NotificationPreferencesState {
  return {
    ...EMPTY_NOTIFICATION_PREFERENCES_STATE,
    loading,
  };
}

export function notificationPreferencesReducer(
  state: NotificationPreferencesState,
  action: NotificationPreferencesAction,
): NotificationPreferencesState {
  switch (action.type) {
    case 'load-succeeded':
      return {
        ...state,
        ...normalizeNotificationPreferences(action.prefs),
        loading: false,
        saving: false,
        error: null,
        notice: null,
        hasLoaded: true,
      };
    case 'load-failed':
      return {
        ...state,
        loading: false,
        saving: false,
        error: action.error,
      };
    case 'email-changed':
      return {
        ...state,
        email: action.value,
      };
    case 'email-enabled-changed':
      return {
        ...state,
        emailEnabled: action.value,
      };
    case 'discord-enabled-changed':
      return {
        ...state,
        discordEnabled: action.value,
      };
    case 'discord-webhook-changed':
      return {
        ...state,
        discordWebhook: action.value,
      };
    case 'save-started':
      return {
        ...state,
        saving: true,
        error: null,
        notice: null,
      };
    case 'save-succeeded':
      return {
        ...state,
        ...normalizeNotificationPreferences(action.prefs),
        loading: false,
        saving: false,
        error: null,
        notice: action.notice,
        hasLoaded: true,
      };
    case 'save-failed':
      return {
        ...state,
        saving: false,
        error: action.error,
      };
    case 'reset-transient-feedback':
      return {
        ...state,
        loading: false,
        saving: false,
        error: null,
        notice: null,
      };
    default:
      return state;
  }
}

export function toNotificationPreferenceUpdatePayload(state: NotificationPreferencesState) {
  const trimmedDiscordWebhook = state.discordWebhook.trim();
  return {
    emailEnabled: state.emailEnabled,
    email: state.email.trim() || null,
    discordEnabled: state.discordEnabled,
    ...(trimmedDiscordWebhook ? { discordWebhook: trimmedDiscordWebhook } : {}),
  };
}
