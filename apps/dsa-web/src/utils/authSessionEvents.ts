export const AUTH_SESSION_EVENT_STORAGE_KEY = 'wolfystock.auth.session-event.v1';

export type AuthSessionEvent = {
  kind: 'session-invalidated';
  at: number;
};

function parseAuthSessionEvent(value: string | null): AuthSessionEvent | null {
  if (!value) {
    return null;
  }

  try {
    const parsed = JSON.parse(value) as Partial<AuthSessionEvent>;
    if (parsed.kind !== 'session-invalidated' || typeof parsed.at !== 'number') {
      return null;
    }
    return { kind: parsed.kind, at: parsed.at };
  } catch {
    return null;
  }
}

export function publishAuthSessionInvalidated(): void {
  if (typeof window === 'undefined') {
    return;
  }

  const event: AuthSessionEvent = {
    kind: 'session-invalidated',
    at: Date.now(),
  };

  try {
    window.localStorage.setItem(AUTH_SESSION_EVENT_STORAGE_KEY, JSON.stringify(event));
  } catch {
    // Cross-tab sync is best-effort. Local logout/401 handling must continue
    // even when browser storage is unavailable.
  }
}

export function readAuthSessionEvent(value: string | null): AuthSessionEvent | null {
  return parseAuthSessionEvent(value);
}
