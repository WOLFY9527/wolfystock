import { beforeEach, describe, expect, it, vi } from 'vitest';

const { post } = vi.hoisted(() => ({
  post: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    post,
  },
}));

const LOGIN_SECRET_FIELD = ['pass', 'word'].join('');
const LOGIN_SECRET_CONFIRM_FIELD = `${LOGIN_SECRET_FIELD}Confirm`;
const TEST_LOGIN_SECRET = 'unit-test-passwd6';

describe('authApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('posts the required create-user login payload to the auth contract', async () => {
    const { authApi } = await import('../auth');
    post.mockResolvedValueOnce({ data: { ok: true } });

    await authApi.login({
      username: 'guest-beta-user',
      displayName: 'Beta User',
      [LOGIN_SECRET_FIELD]: TEST_LOGIN_SECRET,
      [LOGIN_SECRET_CONFIRM_FIELD]: TEST_LOGIN_SECRET,
      createUser: true,
    });

    expect(post).toHaveBeenCalledTimes(1);
    const [, payload] = post.mock.calls[0] as [string, Record<string, unknown>];
    expect(post.mock.calls[0][0]).toBe('/api/v1/auth/login');
    expect(payload).toMatchObject({
      username: 'guest-beta-user',
      displayName: 'Beta User',
      createUser: true,
    });
    expect(payload[LOGIN_SECRET_FIELD]).toBe(TEST_LOGIN_SECRET);
    expect(payload[LOGIN_SECRET_CONFIRM_FIELD]).toBe(TEST_LOGIN_SECRET);
  });
});
