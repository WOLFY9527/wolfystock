export type SystemConfigCategory =
  | 'base'
  | 'data_source'
  | 'ai_model'
  | 'notification'
  | 'system'
  | 'agent'
  | 'backtest'
  | 'uncategorized';

export type SystemConfigDataType =
  | 'string'
  | 'integer'
  | 'number'
  | 'boolean'
  | 'array'
  | 'json'
  | 'time';

export type SystemConfigUIControl =
  | 'text'
  | 'password'
  | 'number'
  | 'select'
  | 'textarea'
  | 'switch'
  | 'time';

export interface SystemConfigOption {
  label: string;
  value: string;
}

export interface SystemConfigFieldSchema {
  key: string;
  title?: string;
  description?: string;
  category: SystemConfigCategory;
  dataType: SystemConfigDataType;
  uiControl: SystemConfigUIControl;
  isSensitive: boolean;
  isRequired: boolean;
  isEditable: boolean;
  defaultValue?: string | null;
  options: Array<string | SystemConfigOption>;
  validation: Record<string, unknown>;
  displayOrder: number;
  rawEditable?: boolean;
  uiVisibility?: 'raw' | 'curated' | 'hidden' | 'advanced';
  managedBy?: string | null;
}

export interface SystemConfigCategorySchema {
  category: SystemConfigCategory;
  title: string;
  description?: string;
  displayOrder: number;
  fields: SystemConfigFieldSchema[];
}

export interface SystemConfigSchemaResponse {
  schemaVersion: string;
  categories: SystemConfigCategorySchema[];
}

export interface SystemConfigItem {
  key: string;
  value: string;
  rawValueExists: boolean;
  isMasked: boolean;
  rawEditable?: boolean;
  uiVisibility?: 'raw' | 'curated' | 'hidden' | 'advanced';
  managedBy?: string | null;
  schema?: SystemConfigFieldSchema;
}

export interface SystemConfigResponse {
  configVersion: string;
  maskToken: string;
  items: SystemConfigItem[];
  updatedAt?: string;
}

export interface SystemConfigUpdateItem {
  key: string;
  value: string;
}

export interface UpdateSystemConfigRequest {
  configVersion: string;
  maskToken?: string;
  reloadNow?: boolean;
  items: SystemConfigUpdateItem[];
}

export interface UpdateSystemConfigResponse {
  success: boolean;
  configVersion: string;
  appliedCount: number;
  skippedMaskedCount: number;
  reloadTriggered: boolean;
  updatedKeys: string[];
  warnings: string[];
}

export interface ValidateSystemConfigRequest {
  items: SystemConfigUpdateItem[];
}

export interface ConfigValidationIssue {
  key: string;
  code: string;
  message: string;
  severity: 'error' | 'warning';
  expected?: string;
  actual?: string;
}

export interface ValidateSystemConfigResponse {
  valid: boolean;
  issues: ConfigValidationIssue[];
}

export interface TestLLMChannelRequest {
  name: string;
  protocol: string;
  baseUrl?: string;
  apiKey?: string;
  models: string[];
  enabled?: boolean;
  timeoutSeconds?: number;
}

export interface TestLLMChannelResponse {
  success: boolean;
  message: string;
  error?: string | null;
  resolvedProtocol?: string | null;
  resolvedModel?: string | null;
  latencyMs?: number | null;
}

export interface TestCustomDataSourceRequest {
  name: string;
  baseUrl: string;
  credentialSchema: 'single_key' | 'key_secret';
  credential?: string;
  secret?: string;
  timeoutSeconds?: number;
}

export interface TestCustomDataSourceResponse {
  success: boolean;
  message: string;
  error?: string | null;
  statusCode?: number | null;
  checkedUrl?: string | null;
  latencyMs?: number | null;
}

export type BuiltinDataSourceValidationStatus = 'success' | 'partial' | 'failed' | 'missing_key' | 'unsupported';

export interface BuiltinDataSourceEndpointCheck {
  name: string;
  endpoint: string;
  ok: boolean;
  httpStatus?: number | null;
  durationMs?: number | null;
  errorType?: string | null;
  message: string;
}

export interface TestBuiltinDataSourceRequest {
  provider: string;
  symbol?: string;
  credential?: string;
  secret?: string;
  timeoutSeconds?: number;
}

export interface TestBuiltinDataSourceResponse {
  provider: string;
  ok: boolean;
  status: BuiltinDataSourceValidationStatus;
  checkedAt: string;
  durationMs: number;
  keyMasked?: string | null;
  checks: BuiltinDataSourceEndpointCheck[];
  summary: string;
  suggestion: string;
}

export interface SystemAdminActionResponse {
  success: boolean;
  action: string;
  message: string;
  cleared: string[];
  preserved: string[];
  counts: Record<string, number>;
}

export interface FactoryResetSystemRequest {
  confirmationPhrase: string;
}

export interface SystemConfigValidationErrorResponse {
  error: string;
  message: string;
  issues: ConfigValidationIssue[];
}

export interface SystemConfigConflictResponse {
  error: string;
  message: string;
  currentConfigVersion: string;
}
