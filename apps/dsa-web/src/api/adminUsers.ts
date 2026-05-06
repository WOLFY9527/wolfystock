import apiClient from './index';
import { toCamelCase } from './utils';

export type AdminPasswordState = 'set' | 'unset' | 'unknown';
export type AdminSessionStatus = 'active' | 'expired' | 'revoked';
export type AdminActivityStatus = 'success' | 'failed' | 'partial' | 'running' | 'skipped' | 'cancelled' | 'unknown';
export type AdminActivityOutcome = 'ok' | 'warning' | 'failed' | 'timeout' | 'partial' | 'unknown';

export interface AdminSessionSummaryCounts {
  activeCount: number;
  expiredCount: number;
  revokedCount: number;
  lastSeenAt?: string | null;
  nextExpiresAt?: string | null;
}

export interface AdminUserRiskBadge {
  code: string;
  label: string;
  severity: 'info' | 'warning' | 'critical';
  reason?: string | null;
  source: 'auth' | 'session' | 'future_activity' | 'future_security' | string;
}

export interface AdminDataLinks {
  self?: string | null;
  adminLogs?: string | null;
  activity?: string | null;
  portfolio?: string | null;
  analysis?: string | null;
  scanner?: string | null;
  backtest?: string | null;
}

export interface AdminUserListItem {
  id: string;
  username: string;
  displayName?: string | null;
  role: string;
  isActive: boolean;
  createdAt?: string | null;
  updatedAt?: string | null;
  passwordState: AdminPasswordState;
  lastSeenAt?: string | null;
  sessionSummary: AdminSessionSummaryCounts;
  riskBadges: AdminUserRiskBadge[];
  links: AdminDataLinks;
}

export interface AdminUserListResponse {
  items: AdminUserListItem[];
  total: number;
  limit: number;
  offset: number;
  hasMore: boolean;
}

export interface AdminSessionSummary {
  sessionHandle: string;
  status: AdminSessionStatus;
  createdAt?: string | null;
  lastSeenAt?: string | null;
  expiresAt?: string | null;
  revokedAt?: string | null;
}

export interface AdminUserDetailResponse {
  user: AdminUserListItem;
  sessions: AdminSessionSummary[];
  dataLinks: AdminDataLinks;
  limitations: string[];
}

export interface AdminActivityActor {
  type: 'admin' | 'user' | 'guest' | 'anonymous' | 'system' | 'unknown' | string;
  userId?: string | null;
  label?: string | null;
  role?: string | null;
  sessionIdHash?: string | null;
  requestIdHash?: string | null;
}

export interface AdminActivityEntity {
  type: string;
  idHash?: string | null;
  label?: string | null;
  symbol?: string | null;
  market?: string | null;
  sourceTable?: string | null;
}

export interface AdminActivitySource {
  kind: string;
  table?: string | null;
  confidence?: 'confirmed' | 'inferred' | 'unknown' | string;
}

export interface AdminActivityEvent {
  id: string;
  timestamp: string;
  actor: AdminActivityActor;
  targetUser: {
    id?: string | null;
    label?: string | null;
  };
  family: string;
  action: string;
  entity: AdminActivityEntity;
  status: AdminActivityStatus;
  outcome: AdminActivityOutcome;
  requestIdHash?: string | null;
  sessionIdHash?: string | null;
  source: AdminActivitySource;
  redactedMetadata: Record<string, unknown>;
  logLinks: Array<{
    kind: string;
    idHash?: string | null;
  }>;
}

export interface AdminActivityResponse {
  items: AdminActivityEvent[];
  total: number;
  limit: number;
  offset: number;
  hasMore: boolean;
  window: {
    from: string;
    to: string;
    maxDays: number;
  };
  limitations: string[];
}

export interface AdminUserListParams {
  q?: string;
  role?: string;
  status?: string;
  active?: boolean;
  createdFrom?: string;
  createdTo?: string;
  lastSeenFrom?: string;
  lastSeenTo?: string;
  limit?: number;
  offset?: number;
  sort?: string;
}

export interface AdminUserDetailParams {
  includeSessions?: boolean;
  sessionLimit?: number;
  sessionStatus?: string;
}

export interface AdminActivityParams {
  from?: string;
  to?: string;
  family?: string;
  category?: string;
  status?: string;
  entityType?: string;
  actorType?: string;
  targetUser?: string;
  q?: string;
  includeSystem?: boolean;
  includeAdmin?: boolean;
  limit?: number;
  offset?: number;
}

const PARAM_ALIASES: Record<string, string> = {
  createdFrom: 'created_from',
  createdTo: 'created_to',
  lastSeenFrom: 'last_seen_from',
  lastSeenTo: 'last_seen_to',
  includeSessions: 'include_sessions',
  sessionLimit: 'session_limit',
  sessionStatus: 'session_status',
  entityType: 'entity_type',
  actorType: 'actor_type',
  targetUser: 'target_user',
  includeSystem: 'include_system',
  includeAdmin: 'include_admin',
};

function toQueryParams(params: Record<string, unknown>): Record<string, unknown> {
  const query: Record<string, unknown> = {};
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    query[PARAM_ALIASES[key] || key] = value;
  });
  return query;
}

function normalizeList(payload: Record<string, unknown>): AdminUserListResponse {
  const normalized = toCamelCase<AdminUserListResponse>(payload);
  return {
    items: Array.isArray(normalized.items) ? normalized.items : [],
    total: Number(normalized.total || 0),
    limit: Number(normalized.limit || 50),
    offset: Number(normalized.offset || 0),
    hasMore: Boolean(normalized.hasMore),
  };
}

function normalizeDetail(payload: Record<string, unknown>): AdminUserDetailResponse {
  const normalized = toCamelCase<AdminUserDetailResponse>(payload);
  return {
    user: normalized.user,
    sessions: Array.isArray(normalized.sessions) ? normalized.sessions : [],
    dataLinks: normalized.dataLinks || {},
    limitations: Array.isArray(normalized.limitations) ? normalized.limitations : [],
  };
}

function normalizeActivity(payload: Record<string, unknown>): AdminActivityResponse {
  const normalized = toCamelCase<AdminActivityResponse>(payload);
  return {
    items: Array.isArray(normalized.items) ? normalized.items : [],
    total: Number(normalized.total || 0),
    limit: Number(normalized.limit || 50),
    offset: Number(normalized.offset || 0),
    hasMore: Boolean(normalized.hasMore),
    window: normalized.window || { from: '', to: '', maxDays: 0 },
    limitations: Array.isArray(normalized.limitations) ? normalized.limitations : [],
  };
}

export const adminUsersApi = {
  async listUsers(params: AdminUserListParams = {}): Promise<AdminUserListResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/users', {
      params: toQueryParams(params as Record<string, unknown>),
    });
    return normalizeList(response.data);
  },

  async getUserDetail(userId: string, params: AdminUserDetailParams = {}): Promise<AdminUserDetailResponse> {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/admin/users/${encodeURIComponent(userId)}`, {
      params: toQueryParams(params as Record<string, unknown>),
    });
    return normalizeDetail(response.data);
  },

  async listUserActivity(userId: string, params: AdminActivityParams = {}): Promise<AdminActivityResponse> {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/admin/users/${encodeURIComponent(userId)}/activity`, {
      params: toQueryParams(params as Record<string, unknown>),
    });
    return normalizeActivity(response.data);
  },

  async listActivity(params: AdminActivityParams = {}): Promise<AdminActivityResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/activity', {
      params: toQueryParams(params as Record<string, unknown>),
    });
    return normalizeActivity(response.data);
  },
};
