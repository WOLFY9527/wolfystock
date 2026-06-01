export type UserAlertRuleType = 'watchlist_price_threshold';
export type UserAlertDirection = 'above' | 'below';
export type UserAlertDeliveryMode = 'in_app';

export interface UserAlertRule {
  id: number;
  contractVersion: string;
  ruleType: UserAlertRuleType;
  symbol: string;
  direction: UserAlertDirection;
  thresholdPrice: number;
  enabled: boolean;
  note?: string | null;
  deliveryMode: UserAlertDeliveryMode;
  inAppOnly: boolean;
  ownerScoped: boolean;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface UserAlertRuleListResponse {
  contractVersion: string;
  deliveryMode: UserAlertDeliveryMode;
  inAppOnly: boolean;
  ownerScoped: boolean;
  items: UserAlertRule[];
}

export interface UserAlertRuleCreateRequest {
  symbol: string;
  direction: UserAlertDirection;
  thresholdPrice: number;
  enabled?: boolean;
  note?: string | null;
}

export interface UserAlertRuleUpdateRequest {
  symbol?: string;
  direction?: UserAlertDirection;
  thresholdPrice?: number;
  enabled?: boolean;
  note?: string | null;
}

export interface UserAlertRuleDeleteResponse {
  deleted: number;
}

export interface UserAlertEvent {
  id: number;
  contractVersion: string;
  eventType: string;
  ruleId?: number | null;
  symbol?: string | null;
  direction?: UserAlertDirection | null;
  thresholdPrice?: number | null;
  title: string;
  message: string;
  deliveryMode: UserAlertDeliveryMode;
  inAppOnly: boolean;
  ownerScoped: boolean;
  readAt?: string | null;
  createdAt?: string | null;
}

export interface UserAlertEventListRequest {
  limit?: number;
  offset?: number;
}

export interface UserAlertEventListResponse {
  contractVersion: string;
  deliveryMode: UserAlertDeliveryMode;
  inAppOnly: boolean;
  ownerScoped: boolean;
  total: number;
  limit: number;
  offset: number;
  items: UserAlertEvent[];
}
