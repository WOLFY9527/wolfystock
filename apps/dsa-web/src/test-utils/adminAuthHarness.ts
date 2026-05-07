import type { AuthStatusResponse, CurrentUser } from '../api/auth';

export type AdminCapability =
  | 'users:read'
  | 'users:activity:read'
  | 'users:portfolio:read'
  | 'users:security:write'
  | 'cost:observability:read'
  | 'ops:logs:read'
  | 'ops:providers:read'
  | 'ops:notifications:read'
  | 'ops:system_config:read';

export type MockAdminUserOptions = {
  capabilities?: AdminCapability[];
  injectRawAuthCanaries?: boolean;
  legacyAdmin?: boolean;
  rbacFallbackDisabledRehearsal?: boolean;
  includeCapabilityFields?: boolean;
  id?: string;
  username?: string;
  displayName?: string;
};

const capabilityFlagMap: Record<AdminCapability, keyof Pick<
  CurrentUser,
  | 'canReadUsers'
  | 'canReadUserActivity'
  | 'canReadUserPortfolio'
  | 'canWriteUserSecurity'
  | 'canReadCostObservability'
  | 'canReadOpsLogs'
  | 'canReadProviders'
  | 'canReadNotifications'
  | 'canReadSystemConfig'
>> = {
  'users:read': 'canReadUsers',
  'users:activity:read': 'canReadUserActivity',
  'users:portfolio:read': 'canReadUserPortfolio',
  'users:security:write': 'canWriteUserSecurity',
  'cost:observability:read': 'canReadCostObservability',
  'ops:logs:read': 'canReadOpsLogs',
  'ops:providers:read': 'canReadProviders',
  'ops:notifications:read': 'canReadNotifications',
  'ops:system_config:read': 'canReadSystemConfig',
};

export const fullAdminCapabilities: AdminCapability[] = Object.keys(capabilityFlagMap) as AdminCapability[];

export function createMockAdminUser(options: MockAdminUserOptions = {}): CurrentUser {
  const capabilities = options.capabilities ?? fullAdminCapabilities;
  const capabilitySet = new Set(capabilities);
  const user: CurrentUser = {
    id: options.id ?? 'pw-admin-user',
    username: options.username ?? 'playwright-admin',
    displayName: options.displayName ?? 'Playwright Admin',
    role: 'admin',
    isAdmin: true,
    isAuthenticated: true,
    transitional: false,
    authEnabled: true,
    legacyAdmin: options.legacyAdmin,
  };

  if (options.includeCapabilityFields !== false) {
    user.adminCapabilities = capabilities;
    for (const [capability, flag] of Object.entries(capabilityFlagMap) as Array<[AdminCapability, keyof CurrentUser]>) {
      user[flag] = capabilitySet.has(capability) as never;
    }
  }

  const userWithHarnessMetadata = user as CurrentUser & Record<string, unknown>;
  if (options.rbacFallbackDisabledRehearsal) {
    userWithHarnessMetadata.rbacFallbackRehearsal = {
      coarseFallbackEnabled: false,
      stagingOnly: true,
    };
  }
  if (options.injectRawAuthCanaries) {
    userWithHarnessMetadata.sessionId = 'raw-session-canary-should-not-render';
    userWithHarnessMetadata.cookie = 'cookie_canary_should_not_render';
    userWithHarnessMetadata.totpCode = '123456';
    userWithHarnessMetadata.recoveryCodes = ['RECOVERY-CODE-CANARY-0001'];
    userWithHarnessMetadata.rawRbacCapabilityDump = 'adminCapabilities: users:security:write ops:system_config:read';
  }

  return user;
}
export function createMockAuthStatus(currentUser: CurrentUser | null): AuthStatusResponse {
  return {
    authEnabled: true,
    loggedIn: Boolean(currentUser?.isAuthenticated),
    passwordSet: true,
    passwordChangeable: true,
    setupState: 'enabled',
    currentUser,
  };
}
