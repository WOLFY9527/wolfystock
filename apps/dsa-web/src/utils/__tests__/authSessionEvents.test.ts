import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  AUTH_SESSION_EVENT_STORAGE_KEY,
  publishAuthSessionInvalidated,
  readAuthSessionEvent,
} from '../authSessionEvents';

describe('authSessionEvents', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('publishes only an invalidation signal without identity or credential fields', () => {
    vi.spyOn(Date, 'now').mockReturnValue(42);

    publishAuthSessionInvalidated();

    const raw = window.localStorage.getItem(AUTH_SESSION_EVENT_STORAGE_KEY);
    expect(raw).toBeTruthy();
    expect(JSON.parse(raw || '{}')).toEqual({
      kind: 'session-invalidated',
      at: 42,
    });
    expect(raw).not.toMatch(/user|identity|credential|password|token|sessionId|cookie/i);
  });

  it('ignores malformed and non-invalidation auth session events', () => {
    expect(readAuthSessionEvent(null)).toBeNull();
    expect(readAuthSessionEvent('not-json')).toBeNull();
    expect(readAuthSessionEvent(JSON.stringify({ kind: 'login-confirmed', at: 42 }))).toBeNull();
    expect(readAuthSessionEvent(JSON.stringify({ kind: 'session-invalidated', at: '42' }))).toBeNull();
    expect(readAuthSessionEvent(JSON.stringify({ kind: 'session-invalidated', at: 42 }))).toEqual({
      kind: 'session-invalidated',
      at: 42,
    });
  });

  it('does not throw when browser storage rejects the invalidation signal', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('blocked', 'QuotaExceededError');
    });

    expect(() => publishAuthSessionInvalidated()).not.toThrow();
  });
});
