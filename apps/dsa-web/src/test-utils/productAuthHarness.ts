import type { AuthStatusResponse, CurrentUser } from '../api/auth';

export type MockProductUserOptions = {
  id?: string;
  username?: string;
  displayName?: string;
};

export function createMockProductUser(options: MockProductUserOptions = {}): CurrentUser {
  return {
    id: options.id ?? 'pw-product-user',
    username: options.username ?? 'playwright-user',
    displayName: options.displayName ?? 'Playwright User',
    role: 'user',
    isAdmin: false,
    isAuthenticated: true,
    transitional: false,
    authEnabled: true,
  };
}

export function createMockProductAuthStatus(currentUser: CurrentUser | null): AuthStatusResponse {
  return {
    authEnabled: true,
    loggedIn: Boolean(currentUser?.isAuthenticated),
    passwordSet: true,
    passwordChangeable: true,
    setupState: 'enabled',
    currentUser,
  };
}
