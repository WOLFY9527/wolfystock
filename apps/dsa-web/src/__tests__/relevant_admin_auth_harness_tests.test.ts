import { describe, expect, it } from 'vitest';
import {
  createMockAdminUser,
  createMockAuthStatus,
  fullAdminCapabilities,
} from '../test-utils/adminAuthHarness';
import { canAccessAdminPath, resolveAdminCapabilityFlags } from '../utils/adminCapabilities';

describe('admin auth browser harness payloads', () => {
  it('creates fake admin auth/status payloads with selected capability fields', () => {
    const user = createMockAdminUser({ capabilities: ['cost:observability:read', 'users:read'] });
    const status = createMockAuthStatus(user);

    expect(status.authEnabled).toBe(true);
    expect(status.loggedIn).toBe(true);
    expect(status.currentUser?.username).toBe('playwright-admin');
    expect(status.currentUser?.canReadCostObservability).toBe(true);
    expect(status.currentUser?.canReadUsers).toBe(true);
    expect(status.currentUser?.canReadSystemConfig).toBe(false);
    expect(status.currentUser?.adminCapabilities).toEqual(['cost:observability:read', 'users:read']);
  });

  it('fails closed when capability fields and adminCapabilities are missing', () => {
    const user = createMockAdminUser({ capabilities: ['ops:system_config:read'], includeCapabilityFields: false });

    expect(resolveAdminCapabilityFlags(user)).toEqual({
      canReadUsers: false,
      canReadUserActivity: false,
      canReadUserPortfolio: false,
      canWriteUserSecurity: false,
      canReadCostObservability: false,
      canReadOpsLogs: false,
      canReadProviders: false,
      canReadNotifications: false,
      canReadSystemConfig: false,
    });
  });

  it('uses only static fake users and no secret-bearing fields', () => {
    const serialized = JSON.stringify(createMockAdminUser({ capabilities: fullAdminCapabilities }));

    expect(serialized).toContain('playwright-admin');
    expect(serialized).not.toMatch(/cookie|session_id|token|password|secret|api[_-]?key|webhook/i);
  });

  it('does not classify the reserved admin users activity segment as a user activity route', () => {
    const userReadOnly = {
      canReadUsers: true,
      canReadUserActivity: false,
      canReadUserPortfolio: false,
      canWriteUserSecurity: false,
      canReadCostObservability: false,
      canReadOpsLogs: false,
      canReadProviders: false,
      canReadNotifications: false,
      canReadSystemConfig: false,
    };
    const activityReadOnly = {
      ...userReadOnly,
      canReadUsers: false,
      canReadUserActivity: true,
    };

    expect(canAccessAdminPath('/admin/users/activity', activityReadOnly)).toBe(false);
    expect(canAccessAdminPath('/admin/users/activity', userReadOnly)).toBe(true);
    expect(canAccessAdminPath('/admin/users/user-1/activity', activityReadOnly)).toBe(true);
    expect(canAccessAdminPath('/admin/users/user-1', userReadOnly)).toBe(true);
  });
});
