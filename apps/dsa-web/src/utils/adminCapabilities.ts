import type { CurrentUser } from '../api/auth';

export type AdminCapabilityFlags = {
  canReadUsers: boolean;
  canReadUserActivity: boolean;
  canReadUserPortfolio: boolean;
  canWriteUserSecurity: boolean;
  canReadCostObservability: boolean;
  canReadOpsLogs: boolean;
  canReadProviders: boolean;
  canReadNotifications: boolean;
  canReadSystemConfig: boolean;
};

const capabilityByFlag: Record<keyof AdminCapabilityFlags, string> = {
  canReadUsers: 'users:read',
  canReadUserActivity: 'users:activity:read',
  canReadUserPortfolio: 'users:portfolio:read',
  canWriteUserSecurity: 'users:security:write',
  canReadCostObservability: 'cost:observability:read',
  canReadOpsLogs: 'ops:logs:read',
  canReadProviders: 'ops:providers:read',
  canReadNotifications: 'ops:notifications:read',
  canReadSystemConfig: 'ops:system_config:read',
};

const emptyFlags: AdminCapabilityFlags = {
  canReadUsers: false,
  canReadUserActivity: false,
  canReadUserPortfolio: false,
  canWriteUserSecurity: false,
  canReadCostObservability: false,
  canReadOpsLogs: false,
  canReadProviders: false,
  canReadNotifications: false,
  canReadSystemConfig: false,
};

const ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED_VALUES = new Set(['1', 'true', 'yes', 'on', 'enabled']);

export function isAdminMissionControlPrototypeEnabled(): boolean {
  const rawValue = import.meta.env.VITE_WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED || '';
  return ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED_VALUES.has(rawValue.trim().toLowerCase());
}

export function isAdminMissionControlPath(pathname: string): boolean {
  return pathname === '/admin/mission-control' || pathname.startsWith('/admin/mission-control/');
}

export function isAdminLaunchCockpitPath(pathname: string): boolean {
  return pathname === '/admin/launch-cockpit' || pathname.startsWith('/admin/launch-cockpit/');
}

export function resolveAdminCapabilityFlags(currentUser: CurrentUser | null | undefined): AdminCapabilityFlags {
  if (!currentUser?.isAdmin) {
    return emptyFlags;
  }

  const capabilitySet = new Set(Array.isArray(currentUser.adminCapabilities) ? currentUser.adminCapabilities : []);
  return Object.fromEntries(
    Object.entries(capabilityByFlag).map(([flag, capability]) => [
      flag,
      currentUser[flag as keyof AdminCapabilityFlags] === true || capabilitySet.has(capability),
    ]),
  ) as AdminCapabilityFlags;
}

export function canAccessAdminPath(pathname: string, flags: AdminCapabilityFlags | null | undefined): boolean {
  const capabilityFlags = flags || emptyFlags;
  if (pathname === '/settings/system' || pathname.startsWith('/settings/system/')) {
    return capabilityFlags.canReadSystemConfig;
  }
  if (pathname === '/admin/logs' || pathname.startsWith('/admin/logs/')) {
    return capabilityFlags.canReadOpsLogs;
  }
  if (isAdminLaunchCockpitPath(pathname)) {
    return capabilityFlags.canReadOpsLogs;
  }
  if (isAdminMissionControlPath(pathname)) {
    return isAdminMissionControlPrototypeEnabled() && capabilityFlags.canReadOpsLogs;
  }
  if (pathname === '/admin/evidence-workflow' || pathname.startsWith('/admin/evidence-workflow/')) {
    return capabilityFlags.canReadOpsLogs;
  }
  if (pathname === '/admin/notifications' || pathname.startsWith('/admin/notifications/')) {
    return capabilityFlags.canReadNotifications;
  }
  if (pathname === '/admin/market-providers' || pathname.startsWith('/admin/market-providers/')) {
    return capabilityFlags.canReadProviders;
  }
  if (pathname === '/admin/provider-circuits' || pathname.startsWith('/admin/provider-circuits/')) {
    return capabilityFlags.canReadProviders;
  }
  if (pathname === '/admin/cost-observability' || pathname.startsWith('/admin/cost-observability/')) {
    return capabilityFlags.canReadCostObservability;
  }
  if (pathname === '/admin/users' || pathname.startsWith('/admin/users/')) {
    return pathname.endsWith('/activity') ? capabilityFlags.canReadUserActivity : capabilityFlags.canReadUsers;
  }
  return false;
}
