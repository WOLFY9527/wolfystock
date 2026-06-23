import { afterEach, describe, expect, it, vi } from 'vitest';
import apiClient, { invalidateApiShortWindowCache } from '../index';
import { getParsedApiError, isTimeoutError } from '../error';

function createDeferredResponse(data: Record<string, unknown> = {}) {
  let resolve!: (value: {
    config: unknown;
    data: Record<string, unknown>;
    headers: Record<string, unknown>;
    status: number;
    statusText: string;
  }) => void;
  const promise = new Promise<{
    config: unknown;
    data: Record<string, unknown>;
    headers: Record<string, unknown>;
    status: number;
    statusText: string;
  }>((innerResolve) => {
    resolve = innerResolve;
  });
  return {
    promise,
    resolve: (config: unknown) => resolve({
      config,
      data,
      headers: {},
      status: 200,
      statusText: 'OK',
    }),
  };
}

async function waitForAdapterDispatch() {
  await new Promise((resolve) => {
    setTimeout(resolve, 0);
  });
}

afterEach(() => {
  invalidateApiShortWindowCache();
  vi.useRealTimers();
});

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

  it('shares duplicate concurrent GET requests for the same URL while in flight', async () => {
    const deferred = createDeferredResponse({ ok: true });
    const adapter = vi.fn((config) => deferred.promise.then(() => ({
      config,
      data: { ok: true },
      headers: {},
      status: 200,
      statusText: 'OK',
    })));

    const first = apiClient.get('/api/v1/ping', { params: { market: 'US' }, adapter });
    const second = apiClient.get('/api/v1/ping', { params: { market: 'US' }, adapter });

    await waitForAdapterDispatch();
    expect(adapter).toHaveBeenCalledTimes(1);

    deferred.resolve({});
    const [firstResponse, secondResponse] = await Promise.all([first, second]);

    expect(firstResponse.data).toEqual({ ok: true });
    expect(secondResponse.data).toEqual({ ok: true });
    expect(firstResponse).toBe(secondResponse);
  });

  it('clears GET dedupe entries after the shared request settles', async () => {
    const adapter = vi.fn(async (config) => ({
      config,
      data: { call: adapter.mock.calls.length },
      headers: {},
      status: 200,
      statusText: 'OK',
    }));

    const first = await apiClient.get('/api/v1/ping', { params: { market: 'US' }, adapter });
    const second = await apiClient.get('/api/v1/ping', { params: { market: 'US' }, adapter });

    expect(adapter).toHaveBeenCalledTimes(2);
    expect(first.data).toEqual({ call: 1 });
    expect(second.data).toEqual({ call: 2 });
  });

  it('reuses a settled auth status response inside the short stampede window', async () => {
    const adapter = vi.fn(async (config) => ({
      config,
      data: { call: adapter.mock.calls.length, loggedIn: false },
      headers: {},
      status: 200,
      statusText: 'OK',
    }));

    const first = await apiClient.get('/api/v1/auth/status', { adapter });
    const second = await apiClient.get('/api/v1/auth/status', { adapter });

    expect(adapter).toHaveBeenCalledTimes(1);
    expect(first.data).toEqual({ call: 1, loggedIn: false });
    expect(second.data).toEqual({ call: 1, loggedIn: false });
  });

  it('reuses a settled market briefing response inside the short stampede window', async () => {
    const adapter = vi.fn(async (config) => ({
      config,
      data: { call: adapter.mock.calls.length, summary: 'briefing' },
      headers: {},
      status: 200,
      statusText: 'OK',
    }));

    const first = await apiClient.get('/api/v1/market/market-briefing', { adapter });
    const second = await apiClient.get('/api/v1/market/market-briefing', { adapter });

    expect(adapter).toHaveBeenCalledTimes(1);
    expect(first.data).toEqual({ call: 1, summary: 'briefing' });
    expect(second.data).toEqual({ call: 1, summary: 'briefing' });
  });

  it('does not reuse settled responses for non-stampede GET paths', async () => {
    const adapter = vi.fn(async (config) => ({
      config,
      data: { call: adapter.mock.calls.length },
      headers: {},
      status: 200,
      statusText: 'OK',
    }));

    const first = await apiClient.get('/api/v1/market/temperature', { adapter });
    const second = await apiClient.get('/api/v1/market/temperature', { adapter });

    expect(adapter).toHaveBeenCalledTimes(2);
    expect(first.data).toEqual({ call: 1 });
    expect(second.data).toEqual({ call: 2 });
  });

  it('expires the short stampede window quickly for auth status', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-06-23T00:00:00.000Z'));
    const adapter = vi.fn(async (config) => ({
      config,
      data: { call: adapter.mock.calls.length },
      headers: {},
      status: 200,
      statusText: 'OK',
    }));

    const first = await apiClient.get('/api/v1/auth/status', { adapter });
    vi.setSystemTime(new Date('2026-06-23T00:00:00.800Z'));
    const second = await apiClient.get('/api/v1/auth/status', { adapter });

    expect(adapter).toHaveBeenCalledTimes(2);
    expect(first.data).toEqual({ call: 1 });
    expect(second.data).toEqual({ call: 2 });
  });

  it('never dedupes POST requests', async () => {
    const deferred = createDeferredResponse({ ok: true });
    const adapter = vi.fn((config) => deferred.promise.then(() => ({
      config,
      data: { ok: true },
      headers: {},
      status: 200,
      statusText: 'OK',
    })));

    const first = apiClient.post('/api/v1/ping', { value: 1 }, { adapter });
    const second = apiClient.post('/api/v1/ping', { value: 1 }, { adapter });

    await waitForAdapterDispatch();
    expect(adapter).toHaveBeenCalledTimes(2);

    deferred.resolve({});
    await Promise.all([first, second]);
  });

  it('does not dedupe streaming GET requests', async () => {
    const deferred = createDeferredResponse({ ok: true });
    const adapter = vi.fn((config) => deferred.promise.then(() => ({
      config,
      data: { ok: true },
      headers: {},
      status: 200,
      statusText: 'OK',
    })));

    const first = apiClient.get('/api/v1/analysis/tasks/stream', { adapter });
    const second = apiClient.get('/api/v1/analysis/tasks/stream', { adapter });

    await waitForAdapterDispatch();
    expect(adapter).toHaveBeenCalledTimes(2);

    deferred.resolve({});
    await Promise.all([first, second]);
  });

  it('does not reuse settled streaming GET responses inside the short stampede window', async () => {
    const adapter = vi.fn(async (config) => ({
      config,
      data: { call: adapter.mock.calls.length },
      headers: {},
      status: 200,
      statusText: 'OK',
    }));

    const first = await apiClient.get('/api/v1/analysis/tasks/stream', { adapter });
    const second = await apiClient.get('/api/v1/analysis/tasks/stream', { adapter });

    expect(adapter).toHaveBeenCalledTimes(2);
    expect(first.data).toEqual({ call: 1 });
    expect(second.data).toEqual({ call: 2 });
  });

  it('applies timeout tiers without changing the default timeout', async () => {
    const seenTimeouts: Array<number | undefined> = [];
    const adapter = vi.fn(async (config) => {
      seenTimeouts.push(config.timeout);
      return {
        config,
        data: {},
        headers: {},
        status: 200,
        statusText: 'OK',
      };
    });

    await apiClient.get('/api/v1/quick', { timeoutTier: 'quick', adapter });
    await apiClient.get('/api/v1/standard', { timeoutTier: 'standard', adapter });
    await apiClient.get('/api/v1/analysis', { timeoutTier: 'analysis', adapter });
    await apiClient.get('/api/v1/default', { adapter });

    expect(seenTimeouts).toEqual([5000, 15000, 30000, 30000]);
  });

  it('keeps timeout errors parsed as user-facing fail-closed messages', async () => {
    const error = {
      code: 'ECONNABORTED',
      message: 'timeout of 5000ms exceeded',
    };

    await expect(apiClient.get('/api/v1/quick', {
      timeoutTier: 'quick',
      adapter: async () => Promise.reject(error),
    })).rejects.toBe(error);

    const parsed = getParsedApiError(error);
    expect(parsed.category).toBe('upstream_timeout');
    expect(parsed.message).toBe('请求超时，请稍后重试。');
    expect(isTimeoutError(parsed)).toBe(true);
  });

  it('does not introduce advice or internal diagnostic wording in API client errors', async () => {
    const error = {
      code: 'ECONNABORTED',
      message: 'timeout of 5000ms exceeded',
    };

    await expect(apiClient.get('/api/v1/quick', {
      timeoutTier: 'quick',
      adapter: async () => Promise.reject(error),
    })).rejects.toBe(error);

    const parsed = getParsedApiError(error);
    expect(`${parsed.title} ${parsed.message}`).not.toMatch(
      /买入|卖出|加仓|减仓|建仓|调仓|止损|止盈|目标价|仓位|buy|sell|target|stop loss|position sizing|provider_timeout|fallback_cache|raw|trace|debug|backend|runtime/i,
    );
  });
});
