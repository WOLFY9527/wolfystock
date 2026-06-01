import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  UserAlertEvent,
  UserAlertEventListRequest,
  UserAlertEventListResponse,
  UserAlertRule,
  UserAlertRuleCreateRequest,
  UserAlertRuleDeleteResponse,
  UserAlertRuleListResponse,
  UserAlertRuleUpdateRequest,
} from '../types/userAlerts';

function normalizeRule(payload: Record<string, unknown>): UserAlertRule {
  const normalized = toCamelCase<UserAlertRule>(payload);
  return {
    ...normalized,
    note: normalized.note ?? null,
    inAppOnly: normalized.inAppOnly === true,
    ownerScoped: normalized.ownerScoped === true,
  };
}

function normalizeRuleList(payload: Record<string, unknown>): UserAlertRuleListResponse {
  const normalized = toCamelCase<UserAlertRuleListResponse>(payload);
  return {
    contractVersion: normalized.contractVersion || 'user_alert_contract_v1',
    deliveryMode: normalized.deliveryMode || 'in_app',
    inAppOnly: normalized.inAppOnly === true,
    ownerScoped: normalized.ownerScoped === true,
    items: Array.isArray(normalized.items)
      ? normalized.items.map((item) => normalizeRule(item as unknown as Record<string, unknown>))
      : [],
  };
}

function normalizeEvent(payload: Record<string, unknown>): UserAlertEvent {
  const normalized = toCamelCase<UserAlertEvent>(payload);
  return {
    ...normalized,
    message: normalized.message || '',
    inAppOnly: normalized.inAppOnly === true,
    ownerScoped: normalized.ownerScoped === true,
  };
}

function normalizeEventList(payload: Record<string, unknown>): UserAlertEventListResponse {
  const normalized = toCamelCase<UserAlertEventListResponse>(payload);
  return {
    contractVersion: normalized.contractVersion || 'user_alert_contract_v1',
    deliveryMode: normalized.deliveryMode || 'in_app',
    inAppOnly: normalized.inAppOnly === true,
    ownerScoped: normalized.ownerScoped === true,
    total: Number(normalized.total || 0),
    limit: Number(normalized.limit || 100),
    offset: Number(normalized.offset || 0),
    items: Array.isArray(normalized.items)
      ? normalized.items.map((item) => normalizeEvent(item as unknown as Record<string, unknown>))
      : [],
  };
}

function toRulePayload(payload: UserAlertRuleCreateRequest | UserAlertRuleUpdateRequest): Record<string, unknown> {
  const requestPayload: Record<string, unknown> = {};

  if ('symbol' in payload && payload.symbol !== undefined) {
    requestPayload.symbol = payload.symbol;
  }
  if ('direction' in payload && payload.direction !== undefined) {
    requestPayload.direction = payload.direction;
  }
  if ('thresholdPrice' in payload && payload.thresholdPrice !== undefined) {
    requestPayload.threshold_price = payload.thresholdPrice;
  }
  if ('enabled' in payload && payload.enabled !== undefined) {
    requestPayload.enabled = payload.enabled;
  }
  if ('note' in payload) {
    requestPayload.note = payload.note ?? null;
  }

  return requestPayload;
}

export const userAlertsApi = {
  async listRules(): Promise<UserAlertRuleListResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/user-alerts/rules');
    return normalizeRuleList(response.data);
  },

  async createRule(payload: UserAlertRuleCreateRequest): Promise<UserAlertRule> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/user-alerts/rules', toRulePayload(payload));
    return normalizeRule(response.data);
  },

  async updateRule(ruleId: number, payload: UserAlertRuleUpdateRequest): Promise<UserAlertRule> {
    const response = await apiClient.patch<Record<string, unknown>>(
      `/api/v1/user-alerts/rules/${encodeURIComponent(String(ruleId))}`,
      toRulePayload(payload),
    );
    return normalizeRule(response.data);
  },

  async deleteRule(ruleId: number): Promise<UserAlertRuleDeleteResponse> {
    const response = await apiClient.delete<Record<string, unknown>>(
      `/api/v1/user-alerts/rules/${encodeURIComponent(String(ruleId))}`,
    );
    return toCamelCase<UserAlertRuleDeleteResponse>(response.data);
  },

  async listEvents(options: UserAlertEventListRequest = {}): Promise<UserAlertEventListResponse> {
    const params: Record<string, number> = {};
    if (typeof options.limit === 'number') {
      params.limit = options.limit;
    }
    if (typeof options.offset === 'number') {
      params.offset = options.offset;
    }

    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/user-alerts/events',
      Object.keys(params).length > 0 ? { params } : undefined,
    );
    return normalizeEventList(response.data);
  },
};
