import { afterEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../index';

describe('apiClient auth redirect handling', () => {
  const originalLocation = window.location;

  afterEach(() => {
    vi.restoreAllMocks();
    window.history.replaceState({}, '', '/');
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
  });

  it('redirects to login with the current path when a request returns 401', async () => {
    const assignSpy = vi.fn();
    window.history.replaceState({}, '', '/portfolio?view=holdings');
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        ...window.location,
        assign: assignSpy,
      },
    });

    await expect(apiClient.get('/api/v1/protected', {
      adapter: async (config) => Promise.reject({
        config,
        response: {
          config,
          data: {
            detail: {
              error: 'unauthorized',
              message: 'Login required',
            },
          },
          headers: {},
          status: 401,
          statusText: 'Unauthorized',
        },
      }),
    })).rejects.toBeTruthy();

    expect(assignSpy).toHaveBeenCalledWith('/login?redirect=%2Fportfolio%3Fview%3Dholdings');
  });

  it('sends the selected ui language with outgoing requests', async () => {
    window.localStorage.setItem('dsa-ui-language', 'en');

    let headerValue = '';
    await expect(apiClient.get('/api/v1/ping', {
      adapter: async (config) => {
        const headers = config.headers as Record<string, unknown> & { get?: (name: string) => unknown };
        headerValue = String(headers.get?.('Accept-Language') ?? headers['Accept-Language'] ?? headers['accept-language'] ?? '');
        return {
          config,
          data: {},
          headers: {},
          status: 200,
          statusText: 'OK',
        };
      },
    })).resolves.toBeTruthy();

    expect(headerValue).toContain('en-US');
  });
});
