import type { BuiltinDataSourceEndpointCheck, TestBuiltinDataSourceResponse } from '../../types/systemConfig';
import { formatDurationMs } from '../../utils/format';

export type TranslateFn = (key: string, vars?: Record<string, string | number | undefined>) => string;
export type DataRouteKey = 'market' | 'fundamentals' | 'news' | 'sentiment';
export type DataSourceCapability = DataRouteKey | 'local';
export type DataSourceCredentialSchema =
  | 'none'
  | 'single_key'
  | 'key_secret';
export type DataSourceValidationState =
  | 'not_configured'
  | 'configured_pending'
  | 'validated'
  | 'failed'
  | 'builtin'
  | 'loading'
  | 'partial'
  | 'missing_key'
  | 'unsupported';
export type CustomDataSourceValidation = {
  status: 'pending' | 'validated' | 'failed';
  message?: string;
  checkedAt?: string;
};
export type DataSourceCredentialFieldName = 'credential' | 'secret';
export type DataSourceCredentialFieldDefinition = {
  name: DataSourceCredentialFieldName;
  labelKey: string;
  hintKey: string;
  placeholder?: string;
};
export type DataSourceBuiltinExtraFieldDefinition = {
  key: string;
  envKey: string;
  labelKey: string;
  hintKey: string;
  defaultValue: string;
  options: Array<{ label: string; value: string }>;
};
export type DataSourceBuiltinManagementDefinition = {
  credentialSchema: DataSourceCredentialSchema;
  credentialEnvKey?: string;
  pluralCredentialEnvKey?: string;
  secretEnvKey?: string;
  fields: DataSourceCredentialFieldDefinition[];
  extraField?: DataSourceBuiltinExtraFieldDefinition;
};
export type CustomDataSourceRecord = {
  id: string;
  name: string;
  credentialSchema: Exclude<DataSourceCredentialSchema, 'none'>;
  credential: string;
  secret: string;
  baseUrl: string;
  description: string;
  capabilities: DataSourceCapability[];
  validation?: CustomDataSourceValidation;
};
export type DataSourceEditorMode = 'create' | 'edit' | 'view' | 'manage_builtin';
export type DataSourceLibraryEntry = {
  key: string;
  label: string;
  kind: 'builtin' | 'custom';
  builtin: boolean;
  baseUrl: string;
  configured: boolean;
  usable: boolean;
  validationState: DataSourceValidationState;
  validationMessage: string;
  routeUsage: DataRouteKey[];
  capabilityKeys: DataSourceCapability[];
  capabilityLabels: string[];
  description: string;
  credentialRequired: boolean;
  credentialValue: string;
  credentialSchema: DataSourceCredentialSchema;
  management?: DataSourceBuiltinManagementDefinition;
  customRecord?: CustomDataSourceRecord;
};
export type BuiltinDataSourceValidationResult = TestBuiltinDataSourceResponse;

export const CUSTOM_DATA_SOURCE_LIBRARY_KEY = 'CUSTOM_DATA_SOURCE_LIBRARY';

const envKey = (...parts: string[]): string => parts.join('_');

function createSingleKeyDataSourceManagement(params: {
  credentialEnvKey: string;
  pluralCredentialEnvKey?: string;
  hintKey?: string;
}): DataSourceBuiltinManagementDefinition {
  return {
    credentialSchema: 'single_key',
    credentialEnvKey: params.credentialEnvKey,
    pluralCredentialEnvKey: params.pluralCredentialEnvKey,
    fields: [
      {
        name: 'credential',
        labelKey: 'settings.dataSourceFieldApiKey',
        hintKey: params.hintKey || 'settings.dataSourceFieldApiKeyHint',
      },
    ],
  };
}

export const DATA_SOURCE_LIBRARY_ITEMS: Array<{
  key: string;
  routeKeys: DataRouteKey[];
  capabilityKeys: DataSourceCapability[];
  credentialPatterns: RegExp[];
  builtin?: boolean;
  requireCredential?: boolean;
  credentialSchema?: DataSourceCredentialSchema;
  management?: DataSourceBuiltinManagementDefinition;
}> = [
  {
    key: 'alpha_vantage',
    routeKeys: ['market'],
    capabilityKeys: ['market'],
    credentialPatterns: [/^ALPHA_VANTAGE_API_KEYS?$/i, /^ALPHAVANTAGE_API_KEYS?$/i],
    requireCredential: true,
    credentialSchema: 'single_key',
    management: createSingleKeyDataSourceManagement({
      credentialEnvKey: envKey('ALPHA', 'VANTAGE', 'API', 'KEY'),
      pluralCredentialEnvKey: envKey('ALPHA', 'VANTAGE', 'API', 'KEYS'),
    }),
  },
  {
    key: 'finnhub',
    routeKeys: ['market', 'fundamentals', 'news'],
    capabilityKeys: ['market', 'fundamentals', 'news'],
    credentialPatterns: [/^FINNHUB_API_KEYS?$/i],
    requireCredential: true,
    credentialSchema: 'single_key',
    management: createSingleKeyDataSourceManagement({
      credentialEnvKey: envKey('FINNHUB', 'API', 'KEY'),
      pluralCredentialEnvKey: envKey('FINNHUB', 'API', 'KEYS'),
    }),
  },
  {
    key: 'yahoo',
    routeKeys: ['market', 'fundamentals'],
    capabilityKeys: ['market', 'fundamentals'],
    credentialPatterns: [],
    builtin: true,
    credentialSchema: 'none',
    management: {
      credentialSchema: 'none',
      fields: [],
      extraField: {
        key: 'priority',
        envKey: 'YFINANCE_PRIORITY',
        labelKey: 'settings.dataSourceFieldYahooPriority',
        hintKey: 'settings.dataSourceFieldYahooPriorityHint',
        defaultValue: '4',
        options: [
          { label: '0', value: '0' },
          { label: '1', value: '1' },
          { label: '2', value: '2' },
          { label: '3', value: '3' },
          { label: '4', value: '4' },
          { label: '5', value: '5' },
        ],
      },
    },
  },
  {
    key: 'fmp',
    routeKeys: ['fundamentals'],
    capabilityKeys: ['fundamentals'],
    credentialPatterns: [/^FMP_API_KEYS?$/i],
    requireCredential: true,
    credentialSchema: 'single_key',
    management: createSingleKeyDataSourceManagement({
      credentialEnvKey: 'FMP_API_KEY',
      pluralCredentialEnvKey: 'FMP_API_KEYS',
    }),
  },
  {
    key: 'gnews',
    routeKeys: ['news'],
    capabilityKeys: ['news'],
    credentialPatterns: [/^GNEWS_API_KEYS?$/i],
    requireCredential: true,
    credentialSchema: 'single_key',
    management: createSingleKeyDataSourceManagement({
      credentialEnvKey: 'GNEWS_API_KEY',
      pluralCredentialEnvKey: 'GNEWS_API_KEYS',
    }),
  },
  {
    key: 'tavily',
    routeKeys: ['news', 'sentiment'],
    capabilityKeys: ['news', 'sentiment'],
    credentialPatterns: [/^TAVILY_API_KEYS?$/i],
    requireCredential: true,
    credentialSchema: 'single_key',
    management: createSingleKeyDataSourceManagement({
      credentialEnvKey: 'TAVILY_API_KEY',
      pluralCredentialEnvKey: 'TAVILY_API_KEYS',
    }),
  },
  {
    key: 'social_sentiment_service',
    routeKeys: ['sentiment'],
    capabilityKeys: ['sentiment'],
    credentialPatterns: [/^SOCIAL_SENTIMENT_API_KEYS?$/i],
    requireCredential: true,
  },
  {
    key: 'alpaca',
    routeKeys: ['market'],
    capabilityKeys: ['market'],
    credentialPatterns: [/^ALPACA_API_KEY_ID$/i, /^ALPACA_API_SECRET_KEY$/i],
    requireCredential: true,
    credentialSchema: 'key_secret',
    management: {
      credentialSchema: 'key_secret',
      credentialEnvKey: envKey('ALPACA', 'API', 'KEY', 'ID'),
      secretEnvKey: envKey('ALPACA', 'API', 'SECRET', 'KEY'),
      fields: [
        {
          name: 'credential',
          labelKey: 'settings.dataSourceFieldAlpacaKeyId',
          hintKey: 'settings.dataSourceFieldAlpacaKeyIdHint',
        },
        {
          name: 'secret',
          labelKey: 'settings.dataSourceFieldSecretKey',
          hintKey: 'settings.dataSourceFieldAlpacaSecretHint',
        },
      ],
      extraField: {
        key: 'feed',
        envKey: 'ALPACA_DATA_FEED',
        labelKey: 'settings.dataSourceFieldAlpacaFeed',
        hintKey: 'settings.dataSourceFieldAlpacaFeedHint',
        defaultValue: 'iex',
        options: [
          { label: 'IEX', value: 'iex' },
          { label: 'SIP', value: 'sip' },
        ],
      },
    },
  },
  {
    key: 'twelve_data',
    routeKeys: ['market'],
    capabilityKeys: ['market'],
    credentialPatterns: [/^TWELVE_DATA_API_KEY$/i, /^TWELVE_DATA_API_KEYS$/i, /^TWELVEDATA_API_KEY$/i, /^TWELVEDATA_API_KEYS$/i],
    requireCredential: true,
    credentialSchema: 'single_key',
    management: {
      credentialSchema: 'single_key',
      credentialEnvKey: envKey('TWELVE', 'DATA', 'API', 'KEY'),
      pluralCredentialEnvKey: envKey('TWELVE', 'DATA', 'API', 'KEYS'),
      fields: [
        {
          name: 'credential',
          labelKey: 'settings.dataSourceFieldApiKey',
          hintKey: 'settings.dataSourceFieldTwelveDataKeyHint',
        },
      ],
    },
  },
  {
    key: 'local_inference',
    routeKeys: ['sentiment'],
    capabilityKeys: ['sentiment', 'local'],
    credentialPatterns: [],
    builtin: true,
  },
];

export const DATA_SOURCE_CAPABILITY_LABEL_KEYS: Record<DataSourceCapability, string> = {
  market: 'settings.dataSourceCapability.market',
  fundamentals: 'settings.dataSourceCapability.fundamentals',
  news: 'settings.dataSourceCapability.news',
  sentiment: 'settings.dataSourceCapability.sentiment',
  local: 'settings.dataSourceCapability.local',
};

export const DATA_SOURCE_CAPABILITY_OPTIONS: DataSourceCapability[] = ['market', 'fundamentals', 'news', 'sentiment', 'local'];

export const DATA_SOURCE_CUSTOM_SCHEMA_OPTIONS: Array<{
  value: Exclude<DataSourceCredentialSchema, 'none'>;
  labelKey: string;
  descriptionKey: string;
}> = [
  {
    value: 'single_key',
    labelKey: 'settings.dataSourceSchemaSingleKey',
    descriptionKey: 'settings.dataSourceSchemaSingleKeyDesc',
  },
  {
    value: 'key_secret',
    labelKey: 'settings.dataSourceSchemaKeySecret',
    descriptionKey: 'settings.dataSourceSchemaKeySecretDesc',
  },
];

export const DATA_SOURCE_ROUTING_CAPABILITY_MAP: Record<DataSourceCapability, DataRouteKey | null> = {
  market: 'market',
  fundamentals: 'fundamentals',
  news: 'news',
  sentiment: 'sentiment',
  local: null,
};

const slugifyDataSourceId = (value: string): string => {
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
  return normalized || 'custom_source';
};

const normalizeDataSourceCredentialSchema = (value: unknown): Exclude<DataSourceCredentialSchema, 'none'> => {
  const normalized = String(value || '').trim().toLowerCase();
  return normalized === 'key_secret' ? 'key_secret' : 'single_key';
};

const parseDataSourceCapabilities = (value: unknown): DataSourceCapability[] => {
  const arrayValue = Array.isArray(value)
    ? value
    : typeof value === 'string'
      ? value.split(',')
      : [];
  const seen = new Set<DataSourceCapability>();
  const result: DataSourceCapability[] = [];
  arrayValue.forEach((item) => {
    const capability = String(item || '').trim().toLowerCase() as DataSourceCapability;
    if (!capability || !Object.prototype.hasOwnProperty.call(DATA_SOURCE_CAPABILITY_LABEL_KEYS, capability) || seen.has(capability)) {
      return;
    }
    seen.add(capability);
    result.push(capability);
  });
  return result;
};

const normalizeDataSourceValidationState = (value: unknown): CustomDataSourceValidation | undefined => {
  if (!value || typeof value !== 'object') {
    return undefined;
  }
  const raw = value as Record<string, unknown>;
  const status = String(raw.status || '').trim().toLowerCase();
  if (!['pending', 'validated', 'failed'].includes(status)) {
    return undefined;
  }
  return {
    status: status as CustomDataSourceValidation['status'],
    message: String(raw.message || '').trim() || undefined,
    checkedAt: String(raw.checkedAt || '').trim() || undefined,
  };
};

export const parseCustomDataSourceLibrary = (rawValue: string): CustomDataSourceRecord[] => {
  const text = String(rawValue || '').trim();
  if (!text) {
    return [];
  }
  try {
    const parsed = JSON.parse(text);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.flatMap((item) => {
      if (!item || typeof item !== 'object') {
        return [];
      }
      const source = item as Record<string, unknown>;
      const name = String(source.name || '').trim();
      const id = slugifyDataSourceId(String(source.id || name));
      if (!name) {
        return [];
      }
      return [{
        id,
        name,
        credentialSchema: normalizeDataSourceCredentialSchema(source.credentialSchema || source.credential_schema),
        credential: String(source.credential || '').trim(),
        secret: String(source.secret || source.secretKey || source.secret_key || '').trim(),
        baseUrl: String(source.baseUrl || source.base_url || '').trim(),
        description: String(source.description || '').trim(),
        capabilities: parseDataSourceCapabilities(source.capabilities),
        validation: normalizeDataSourceValidationState(source.validation),
      }];
    });
  } catch {
    return [];
  }
};

export const serializeCustomDataSourceLibrary = (items: CustomDataSourceRecord[]): string => JSON.stringify(items.map((item) => ({
  id: item.id,
  name: item.name,
  credentialSchema: item.credentialSchema,
  credential: item.credential,
  secret: item.secret,
  baseUrl: item.baseUrl,
  description: item.description,
  capabilities: item.capabilities,
  validation: item.validation,
})));

export const createEmptyCustomDataSource = (): CustomDataSourceRecord => ({
  id: '',
  name: '',
  credentialSchema: 'single_key',
  credential: '',
  secret: '',
  baseUrl: '',
  description: '',
  capabilities: [],
  validation: { status: 'pending' },
});

export const validateCustomDataSource = (
  record: CustomDataSourceRecord,
): { valid: boolean; issue?: 'name' | 'credential' | 'secret' | 'capabilities' | 'baseUrl' } => {
  if (!record.name.trim()) {
    return { valid: false, issue: 'name' };
  }
  if (!record.credential.trim()) {
    return { valid: false, issue: 'credential' };
  }
  if (record.credentialSchema === 'key_secret' && !record.secret.trim()) {
    return { valid: false, issue: 'secret' };
  }
  if (!record.capabilities.length) {
    return { valid: false, issue: 'capabilities' };
  }
  if (record.baseUrl && !/^https?:\/\/[^\s]+$/i.test(record.baseUrl.trim())) {
    return { valid: false, issue: 'baseUrl' };
  }
  return { valid: true };
};

export const formatDataSourceCheckLine = (check: BuiltinDataSourceEndpointCheck): string => {
  const httpStatus = check.httpStatus ? `HTTP ${check.httpStatus}` : check.errorType || '--';
  const duration = formatDurationMs(check.durationMs);
  return `${check.name}: ${check.ok ? 'OK' : httpStatus} · ${duration}`;
};

export const makeUniqueDataSourceId = (baseId: string, existingIds: string[]): string => {
  const normalized = slugifyDataSourceId(baseId || '');
  const taken = new Set(existingIds.map((value) => slugifyDataSourceId(value)));
  if (!taken.has(normalized)) {
    return normalized;
  }
  let index = 2;
  while (taken.has(`${normalized}_${index}`)) {
    index += 1;
  }
  return `${normalized}_${index}`;
};

export const sourceToneClass = (index: number): string => {
  if (index === 0) return 'text-[var(--accent-primary)]';
  if (index === 1) return 'text-[var(--accent-positive)]';
  if (index === 2) return 'text-[var(--accent-warning)]';
  return 'text-muted-text';
};

export type DataSourceImpactSurface =
  | 'market_overview'
  | 'liquidity_monitor'
  | 'rotation_radar'
  | 'scanner'
  | 'portfolio'
  | 'watchlist'
  | 'options_lab'
  | 'backtest'
  | 'provider_ops';

export type DataSourceImpactCapability =
  | 'quotes'
  | 'fundamentals'
  | 'news'
  | 'macro'
  | 'crypto'
  | 'futures'
  | 'breadth'
  | 'fund_flow'
  | 'cn_hk_flow'
  | 'money_market_rates'
  | 'fed_liquidity'
  | 'diagnostics';

type DataSourceImpactState =
  | 'configured'
  | 'auth_needed'
  | 'disabled_by_default'
  | 'cache_required'
  | 'paid_likely'
  | 'observation_only'
  | 'score_gates';

type DataSourceImpactEvidence = 'score_when_gates_pass' | 'observation_only' | 'diagnostics_only';

export type DataSourceImpactView = {
  known: boolean;
  surfaces: string[];
  capabilities: string[];
  states: string[];
  evidence: string;
  summary: string;
  unlock: string;
};

export type DataCoverageGapView = {
  key: string;
  surfaces: string[];
  missing: string;
  impact: string;
};

type DataSourceImpactProfile = {
  aliases: string[];
  surfaces: DataSourceImpactSurface[];
  capabilities: DataSourceImpactCapability[];
  states: DataSourceImpactState[];
  evidence: DataSourceImpactEvidence;
  summaryKey: string;
  unlockKey: string;
};

type DataSourceImpactInput = {
  key?: string;
  label?: string;
  name?: string;
  configured?: boolean;
  credentialRequired?: boolean;
  capabilityKeys?: DataSourceCapability[];
  capabilities?: DataSourceCapability[];
};

const DATA_SOURCE_IMPACT_SURFACE_LABEL_KEYS: Record<DataSourceImpactSurface, string> = {
  market_overview: 'settings.dataSourceImpactSurface.marketOverview',
  liquidity_monitor: 'settings.dataSourceImpactSurface.liquidityMonitor',
  rotation_radar: 'settings.dataSourceImpactSurface.rotationRadar',
  scanner: 'settings.dataSourceImpactSurface.scanner',
  portfolio: 'settings.dataSourceImpactSurface.portfolio',
  watchlist: 'settings.dataSourceImpactSurface.watchlist',
  options_lab: 'settings.dataSourceImpactSurface.optionsLab',
  backtest: 'settings.dataSourceImpactSurface.backtest',
  provider_ops: 'settings.dataSourceImpactSurface.providerOps',
};

const DATA_SOURCE_IMPACT_CAPABILITY_LABEL_KEYS: Record<DataSourceImpactCapability, string> = {
  quotes: 'settings.dataSourceImpactCapability.quotes',
  fundamentals: 'settings.dataSourceImpactCapability.fundamentals',
  news: 'settings.dataSourceImpactCapability.news',
  macro: 'settings.dataSourceImpactCapability.macro',
  crypto: 'settings.dataSourceImpactCapability.crypto',
  futures: 'settings.dataSourceImpactCapability.futures',
  breadth: 'settings.dataSourceImpactCapability.breadth',
  fund_flow: 'settings.dataSourceImpactCapability.fundFlow',
  cn_hk_flow: 'settings.dataSourceImpactCapability.cnHkFlow',
  money_market_rates: 'settings.dataSourceImpactCapability.moneyMarketRates',
  fed_liquidity: 'settings.dataSourceImpactCapability.fedLiquidity',
  diagnostics: 'settings.dataSourceImpactCapability.diagnostics',
};

const DATA_SOURCE_IMPACT_STATE_LABEL_KEYS: Record<DataSourceImpactState, string> = {
  configured: 'settings.dataSourceImpactState.configured',
  auth_needed: 'settings.dataSourceImpactState.missingCredential',
  disabled_by_default: 'settings.dataSourceImpactState.disabledByDefault',
  cache_required: 'settings.dataSourceImpactState.cacheRequired',
  paid_likely: 'settings.dataSourceImpactState.paidLikely',
  observation_only: 'settings.dataSourceImpactState.observationOnly',
  score_gates: 'settings.dataSourceImpactState.scoreGates',
};

const DATA_SOURCE_IMPACT_EVIDENCE_LABEL_KEYS: Record<DataSourceImpactEvidence, string> = {
  score_when_gates_pass: 'settings.dataSourceImpactEvidence.scoreWhenGatesPass',
  observation_only: 'settings.dataSourceImpactEvidence.observationOnly',
  diagnostics_only: 'settings.dataSourceImpactEvidence.diagnosticsOnly',
};

const DATA_SOURCE_IMPACT_PROFILES: Record<string, DataSourceImpactProfile> = {
  polygon: {
    aliases: ['polygon', 'polygon_io', 'polygon_us_grouped_daily'],
    surfaces: ['market_overview', 'liquidity_monitor', 'rotation_radar', 'scanner', 'provider_ops'],
    capabilities: ['quotes', 'breadth'],
    states: ['paid_likely', 'cache_required', 'score_gates'],
    evidence: 'score_when_gates_pass',
    summaryKey: 'settings.dataSourceImpactSummary.polygon',
    unlockKey: 'settings.dataSourceImpactUnlock.polygon',
  },
  fred: {
    aliases: ['fred', 'fed_liquidity', 'official_public_fed_liquidity'],
    surfaces: ['liquidity_monitor', 'market_overview', 'provider_ops'],
    capabilities: ['macro', 'fed_liquidity', 'money_market_rates'],
    states: ['cache_required', 'score_gates'],
    evidence: 'score_when_gates_pass',
    summaryKey: 'settings.dataSourceImpactSummary.fred',
    unlockKey: 'settings.dataSourceImpactUnlock.fred',
  },
  cn_cache: {
    aliases: [
      'tushare',
      'akshare',
      'baostock',
      'cn_cache',
      'a_share',
      'cn_hk_connect',
      'cache_cn_hk_connect_daily',
      'official_public_cn_money_market_cache',
      'cn_money_market_cache',
    ],
    surfaces: ['market_overview', 'liquidity_monitor', 'rotation_radar', 'scanner', 'portfolio', 'watchlist', 'backtest', 'provider_ops'],
    capabilities: ['quotes', 'fundamentals', 'fund_flow', 'cn_hk_flow', 'money_market_rates'],
    states: ['cache_required', 'paid_likely', 'observation_only', 'score_gates'],
    evidence: 'observation_only',
    summaryKey: 'settings.dataSourceImpactSummary.cnCache',
    unlockKey: 'settings.dataSourceImpactUnlock.cnCache',
  },
  binance: {
    aliases: ['binance'],
    surfaces: ['market_overview', 'watchlist', 'scanner', 'provider_ops'],
    capabilities: ['crypto', 'futures'],
    states: ['paid_likely', 'observation_only', 'score_gates'],
    evidence: 'observation_only',
    summaryKey: 'settings.dataSourceImpactSummary.binance',
    unlockKey: 'settings.dataSourceImpactUnlock.binance',
  },
  coinbase: {
    aliases: ['coinbase'],
    surfaces: ['market_overview', 'watchlist', 'scanner', 'provider_ops'],
    capabilities: ['crypto'],
    states: ['paid_likely', 'observation_only', 'score_gates'],
    evidence: 'observation_only',
    summaryKey: 'settings.dataSourceImpactSummary.coinbase',
    unlockKey: 'settings.dataSourceImpactUnlock.coinbase',
  },
  finnhub: {
    aliases: ['finnhub'],
    surfaces: ['market_overview', 'scanner', 'portfolio', 'watchlist', 'backtest', 'provider_ops'],
    capabilities: ['quotes', 'fundamentals', 'news'],
    states: ['paid_likely', 'score_gates'],
    evidence: 'score_when_gates_pass',
    summaryKey: 'settings.dataSourceImpactSummary.multiCapability',
    unlockKey: 'settings.dataSourceImpactUnlock.multiCapability',
  },
  alpha_vantage: {
    aliases: ['alpha_vantage', 'alphavantage'],
    surfaces: ['market_overview', 'scanner', 'watchlist', 'backtest', 'provider_ops'],
    capabilities: ['quotes', 'fundamentals', 'macro'],
    states: ['paid_likely', 'score_gates'],
    evidence: 'score_when_gates_pass',
    summaryKey: 'settings.dataSourceImpactSummary.multiCapability',
    unlockKey: 'settings.dataSourceImpactUnlock.multiCapability',
  },
  twelve_data: {
    aliases: ['twelve_data', 'twelvedata'],
    surfaces: ['market_overview', 'scanner', 'watchlist', 'backtest', 'provider_ops'],
    capabilities: ['quotes', 'futures'],
    states: ['paid_likely', 'score_gates'],
    evidence: 'score_when_gates_pass',
    summaryKey: 'settings.dataSourceImpactSummary.multiCapability',
    unlockKey: 'settings.dataSourceImpactUnlock.multiCapability',
  },
  yahoo: {
    aliases: ['yahoo', 'yfinance', 'yahoo_finance'],
    surfaces: ['market_overview', 'scanner', 'portfolio', 'watchlist', 'backtest', 'provider_ops'],
    capabilities: ['quotes', 'fundamentals'],
    states: ['observation_only', 'score_gates'],
    evidence: 'observation_only',
    summaryKey: 'settings.dataSourceImpactSummary.yahoo',
    unlockKey: 'settings.dataSourceImpactUnlock.yahoo',
  },
  fmp: {
    aliases: ['fmp', 'financial_modeling_prep'],
    surfaces: ['market_overview', 'scanner', 'portfolio', 'watchlist', 'backtest', 'provider_ops'],
    capabilities: ['quotes', 'fundamentals', 'news'],
    states: ['paid_likely', 'score_gates'],
    evidence: 'score_when_gates_pass',
    summaryKey: 'settings.dataSourceImpactSummary.multiCapability',
    unlockKey: 'settings.dataSourceImpactUnlock.multiCapability',
  },
  alpaca: {
    aliases: ['alpaca'],
    surfaces: ['market_overview', 'scanner', 'watchlist', 'backtest', 'provider_ops'],
    capabilities: ['quotes'],
    states: ['paid_likely', 'score_gates'],
    evidence: 'score_when_gates_pass',
    summaryKey: 'settings.dataSourceImpactSummary.multiCapability',
    unlockKey: 'settings.dataSourceImpactUnlock.multiCapability',
  },
  news: {
    aliases: ['gnews', 'tavily'],
    surfaces: ['market_overview', 'rotation_radar', 'scanner', 'watchlist', 'provider_ops'],
    capabilities: ['news'],
    states: ['paid_likely', 'score_gates'],
    evidence: 'score_when_gates_pass',
    summaryKey: 'settings.dataSourceImpactSummary.multiCapability',
    unlockKey: 'settings.dataSourceImpactUnlock.multiCapability',
  },
};

const CUSTOM_ROUTE_CAPABILITY_TO_IMPACT: Record<DataSourceCapability, DataSourceImpactCapability> = {
  market: 'quotes',
  fundamentals: 'fundamentals',
  news: 'news',
  sentiment: 'news',
  local: 'diagnostics',
};

const normalizeProviderLookupValue = (value: unknown): string => String(value || '')
  .trim()
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, '_')
  .replace(/^_+|_+$/g, '');

const uniqueOrdered = <T extends string>(items: T[]): T[] => {
  const seen = new Set<T>();
  const result: T[] = [];
  items.forEach((item) => {
    if (!item || seen.has(item)) {
      return;
    }
    seen.add(item);
    result.push(item);
  });
  return result;
};

function findDataSourceImpactProfile(source: DataSourceImpactInput): DataSourceImpactProfile | null {
  const candidates = [
    source.key,
    source.label,
    source.name,
  ]
    .map((value) => normalizeProviderLookupValue(value))
    .filter(Boolean);
  for (const profile of Object.values(DATA_SOURCE_IMPACT_PROFILES)) {
    const aliases = profile.aliases.map((alias) => normalizeProviderLookupValue(alias));
    if (candidates.some((candidate) => aliases.some((alias) => candidate === alias || candidate.includes(alias)))) {
      return profile;
    }
  }
  return null;
}

const translateList = <T extends string>(items: T[], keys: Record<T, string>, t: TranslateFn): string[] => (
  uniqueOrdered(items).map((item) => t(keys[item]))
);

export function buildDataSourceImpactView(source: DataSourceImpactInput, t: TranslateFn): DataSourceImpactView {
  const profile = findDataSourceImpactProfile(source);
  const capabilityKeys = profile
    ? profile.capabilities
    : uniqueOrdered((source.capabilityKeys || source.capabilities || [])
      .map((capability) => CUSTOM_ROUTE_CAPABILITY_TO_IMPACT[capability])
      .filter((capability): capability is DataSourceImpactCapability => Boolean(capability)));
  const baseState: DataSourceImpactState = source.configured === true
    ? 'configured'
    : source.credentialRequired === false
      ? 'configured'
      : 'auth_needed';
  const states = uniqueOrdered([
    baseState,
    ...(profile?.states || ['score_gates']),
  ]);

  return {
    known: Boolean(profile),
    surfaces: translateList(profile?.surfaces || ['provider_ops'], DATA_SOURCE_IMPACT_SURFACE_LABEL_KEYS, t),
    capabilities: translateList(
      capabilityKeys.length ? capabilityKeys : ['diagnostics'],
      DATA_SOURCE_IMPACT_CAPABILITY_LABEL_KEYS,
      t,
    ),
    states: translateList(states, DATA_SOURCE_IMPACT_STATE_LABEL_KEYS, t),
    evidence: t(DATA_SOURCE_IMPACT_EVIDENCE_LABEL_KEYS[profile?.evidence || 'diagnostics_only']),
    summary: t(profile?.summaryKey || 'settings.dataSourceImpactSummary.unknown'),
    unlock: t(profile?.unlockKey || 'settings.dataSourceImpactUnlock.unknown'),
  };
}

const dataSourceMatchesProfile = (source: DataSourceLibraryEntry, profileKey: string): boolean => {
  const profile = DATA_SOURCE_IMPACT_PROFILES[profileKey];
  if (!profile) return false;
  return findDataSourceImpactProfile({
    key: source.key,
    label: source.label,
    name: source.customRecord?.name,
  }) === profile;
};

const hasConfiguredProfile = (sources: DataSourceLibraryEntry[], profileKey: string): boolean => (
  sources.some((source) => source.configured && dataSourceMatchesProfile(source, profileKey))
);

export function buildDataCoverageGaps(sources: DataSourceLibraryEntry[], t: TranslateFn): DataCoverageGapView[] {
  return [
    {
      key: 'market_breadth',
      profiles: ['polygon'],
      surfaces: ['market_overview', 'rotation_radar', 'scanner'] as DataSourceImpactSurface[],
      missingKey: 'settings.dataCoverageGapMissing.marketBreadth',
      impactKey: 'settings.dataCoverageGapImpact.marketBreadth',
    },
    {
      key: 'liquidity_macro',
      profiles: ['fred', 'cn_cache'],
      surfaces: ['liquidity_monitor', 'market_overview'] as DataSourceImpactSurface[],
      missingKey: 'settings.dataCoverageGapMissing.liquidityMacro',
      impactKey: 'settings.dataCoverageGapImpact.liquidityMacro',
    },
    {
      key: 'portfolio_history',
      profiles: ['finnhub', 'fmp', 'twelve_data'],
      surfaces: ['portfolio', 'watchlist', 'backtest'] as DataSourceImpactSurface[],
      missingKey: 'settings.dataCoverageGapMissing.portfolioHistory',
      impactKey: 'settings.dataCoverageGapImpact.portfolioHistory',
    },
    {
      key: 'options_lab',
      profiles: ['polygon'],
      surfaces: ['options_lab', 'provider_ops'] as DataSourceImpactSurface[],
      missingKey: 'settings.dataCoverageGapMissing.optionsLab',
      impactKey: 'settings.dataCoverageGapImpact.optionsLab',
    },
  ]
    .filter((gap) => !gap.profiles.some((profileKey) => hasConfiguredProfile(sources, profileKey)))
    .map((gap) => ({
      key: gap.key,
      surfaces: translateList(gap.surfaces, DATA_SOURCE_IMPACT_SURFACE_LABEL_KEYS, t),
      missing: t(gap.missingKey),
      impact: t(gap.impactKey),
    }))
    .slice(0, 4);
}
