import type { BentoHeroItem } from '../home-bento';
import type { SystemConfigItem } from '../../types/systemConfig';
import {
  describeSettingsEnabledState,
  type SettingsEnabledState,
  type SettingsSystemHealthStatus,
} from '../../utils/displayStatus';

export type SystemHealthStatusCard = {
  key: string;
  label: string;
  status: SettingsSystemHealthStatus;
  reason: string;
  nextAction?: string;
  checkedAt?: string;
  optional?: boolean;
};

export type SystemHealthSummaryCard = {
  key: string;
  label: string;
  value: string | number;
  detail: string;
  status?: SettingsSystemHealthStatus;
};

export type DeveloperDetailGroup = {
  key: string;
  label: string;
  detail: string;
};

export type SystemControlPlaneDerivedState = {
  globalAdminStats: Array<{
    key: string;
    label: string;
    value: string;
    detail: string;
  }>;
  heroItems: BentoHeroItem[];
  systemStatusCards: SystemHealthStatusCard[];
  systemHealthSummaryCards: SystemHealthSummaryCard[];
  developerDetailGroups: DeveloperDetailGroup[];
  duckdbConfigEnabledState: SettingsEnabledState;
};

type TranslateFn = (key: string, vars?: Record<string, string | number | undefined>) => string;

type AiSummaryForSystemPanel = {
  configuredProviders: Array<[string, number]>;
  primaryChannel: string;
  primaryModel: string;
  routeStatus: 'fully_configured' | 'partially_configured' | 'credentials_only' | 'not_configured';
};

type DataSourceForSystemPanel = {
  label: string;
  usable: boolean;
  configured: boolean;
};

type NotificationSummaryForSystemPanel = {
  configuredChannels: string[];
  enabledChannels: string[];
};

type BuildSystemControlPlaneStateParams = {
  allItems: SystemConfigItem[];
  allItemMap: ReadonlyMap<string, string>;
  aiSummary: AiSummaryForSystemPanel;
  activeDomainTitle: string;
  dataSourceLibrary: DataSourceForSystemPanel[];
  dataSummary: { market: string[] };
  dirtyCount: number;
  workspaceDomainCount: number;
  notificationSummary: NotificationSummaryForSystemPanel;
  providerLabel: (value: string) => string;
  prettySourceLabel: (value: string) => string;
  formatRouteLine: (gateway: string, model: string) => string;
  t: TranslateFn;
};

export type RawSettingsPanelState = {
  activeItems: SystemConfigItem[];
  rawFieldsSummaryText: string;
};

const RAW_VISIBILITY_ALLOWED = new Set(['raw', 'advanced']);
const RAW_DRAWER_SUPPRESSED_KEYS = new Set([
  'ADMIN_AUTH_ENABLED',
  'ADMIN_PASSWORD',
  'ADMIN_PASSWORD_HASH',
  'DEBUG',
  'HTTP_PROXY',
  'HTTPS_PROXY',
  'WEBUI_PORT',
  'WEBHOOK_VERIFY_SSL',
  'LITELLM_CONFIG',
  'AGENT_SKILL_DIR',
  'AGENT_STRATEGY_DIR',
  'CUSTOM_DATA_SOURCE_LIBRARY',
]);
const RAW_DRAWER_SECRET_PATTERN = /(API_KEYS?|TOKEN|SECRET|PASSWORD|WEBHOOK|BEARER)/i;
const RAW_DRAWER_NOTIFICATION_PREFIX_PATTERN = /^(DINGTALK|DISCORD|SLACK|PUSHOVER)_/i;
const FALSE_VALUES = new Set(['', '0', 'false', 'no', 'off']);
const AI_MODEL_HIDDEN_KEYS = new Set([
  'AI_PRIMARY_GATEWAY',
  'AI_PRIMARY_MODEL',
  'AI_BACKUP_GATEWAY',
  'AI_BACKUP_MODEL',
  'LLM_CHANNELS',
  'LLM_TEMPERATURE',
  'LITELLM_MODEL',
  'AGENT_LITELLM_MODEL',
  'BACKTEST_LITELLM_MODEL',
  'LITELLM_FALLBACK_MODELS',
  'AIHUBMIX_KEY',
  'DEEPSEEK_API_KEY',
  'DEEPSEEK_API_KEYS',
  'GEMINI_API_KEY',
  'GEMINI_API_KEYS',
  'GEMINI_MODEL',
  'GEMINI_MODEL_FALLBACK',
  'GEMINI_TEMPERATURE',
  'ANTHROPIC_API_KEY',
  'ANTHROPIC_API_KEYS',
  'ANTHROPIC_MODEL',
  'ANTHROPIC_TEMPERATURE',
  'ANTHROPIC_MAX_TOKENS',
  'OPENAI_API_KEY',
  'OPENAI_API_KEYS',
  'OPENAI_BASE_URL',
  'OPENAI_MODEL',
  'OPENAI_VISION_MODEL',
  'OPENAI_TEMPERATURE',
  'VISION_MODEL',
  'ZHIPU_API_KEY',
  'ZHIPU_API_KEYS',
]);
const SYSTEM_HIDDEN_KEYS = new Set([
  'ADMIN_AUTH_ENABLED',
  'SHOW_RUNTIME_EXECUTION_SUMMARY',
]);
const AGENT_HIDDEN_KEYS = new Set([
  'AGENT_DEEP_RESEARCH_BUDGET',
  'AGENT_DEEP_RESEARCH_TIMEOUT',
  'AGENT_EVENT_MONITOR_ENABLED',
  'AGENT_EVENT_MONITOR_INTERVAL_MINUTES',
  'AGENT_EVENT_ALERT_RULES_JSON',
]);

function isEnabledValue(value: string | undefined): boolean {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return false;
  return !FALSE_VALUES.has(normalized);
}

export function statusFromBooleanConfig(value: string | undefined): SettingsEnabledState {
  if (typeof value === 'undefined') return 'unknown';
  return isEnabledValue(value) ? 'enabled' : 'disabled';
}

export function isRawEditableConfigItem(item: SystemConfigItem): boolean {
  const key = item.key.toUpperCase();
  const visibility = item.uiVisibility || item.schema?.uiVisibility || 'raw';

  if (item.rawEditable === false || item.schema?.rawEditable === false) {
    return false;
  }
  if (!RAW_VISIBILITY_ALLOWED.has(visibility)) {
    return false;
  }
  if (RAW_DRAWER_SUPPRESSED_KEYS.has(key)) {
    return false;
  }
  if (
    /^(ADMIN|AUTH|BOOTSTRAP|SESSION)_/.test(key)
    && /(AUTH|PASSWORD|SECRET|TOKEN)/i.test(key)
  ) {
    return false;
  }
  if (RAW_DRAWER_NOTIFICATION_PREFIX_PATTERN.test(key)) {
    return false;
  }
  if (RAW_DRAWER_SECRET_PATTERN.test(key)) {
    return false;
  }
  return true;
}

function summarizeSafeConfigValue(item: SystemConfigItem): string {
  const value = String(item.value ?? '').trim();
  if (item.isMasked || item.schema?.isSensitive || /(?:API_KEYS?|TOKEN|SECRET|PASSWORD|WEBHOOK|BEARER)/i.test(item.key)) {
    return item.rawValueExists || value ? '已遮蔽' : '未配置';
  }
  if (item.schema?.dataType === 'boolean') {
    if (!value) return '未配置';
    return describeSettingsEnabledState(isEnabledValue(value) ? 'enabled' : 'disabled').label;
  }
  if (!value) return '未配置';
  if (/^(true|false)$/i.test(value)) return describeSettingsEnabledState(isEnabledValue(value) ? 'enabled' : 'disabled').label;
  if (value.length > 24) return `${value.slice(0, 24)}...`;
  return value;
}

export function buildRawSettingsPanelState(params: {
  activeCategory: string;
  rawEditableActiveItems: SystemConfigItem[];
  hasConfiguredChannels: boolean;
  hasLitellmConfig: boolean;
  t: TranslateFn;
}): RawSettingsPanelState {
  const { activeCategory, rawEditableActiveItems, hasConfiguredChannels, hasLitellmConfig, t } = params;
  const LLM_CHANNEL_KEY_RE = /^LLM_[A-Z0-9]+_(PROTOCOL|BASE_URL|API_KEY|API_KEYS|MODELS|EXTRA_HEADERS|ENABLED)$/;
  const activeItems =
    activeCategory === 'ai_model'
      ? rawEditableActiveItems.filter((item) => {
        if (hasConfiguredChannels && LLM_CHANNEL_KEY_RE.test(item.key)) {
          return false;
        }
        if (hasConfiguredChannels && !hasLitellmConfig && AI_MODEL_HIDDEN_KEYS.has(item.key)) {
          return false;
        }
        return true;
      })
      : activeCategory === 'data_source'
        ? rawEditableActiveItems.filter((item) => item.key !== 'CUSTOM_DATA_SOURCE_LIBRARY')
      : activeCategory === 'system'
        ? rawEditableActiveItems.filter((item) => !SYSTEM_HIDDEN_KEYS.has(item.key))
      : activeCategory === 'agent'
        ? rawEditableActiveItems.filter((item) => !AGENT_HIDDEN_KEYS.has(item.key))
      : rawEditableActiveItems;

  return {
    activeItems,
    rawFieldsSummaryText: activeItems.length ? t('settings.currentCategory') : t('settings.noItems'),
  };
}

export function buildSystemControlPlaneState(params: BuildSystemControlPlaneStateParams): SystemControlPlaneDerivedState {
  const {
    allItems,
    allItemMap,
    aiSummary,
    activeDomainTitle,
    dataSourceLibrary,
    dataSummary,
    dirtyCount,
    workspaceDomainCount,
    notificationSummary,
    providerLabel,
    prettySourceLabel,
    formatRouteLine,
    t,
  } = params;
  const usableDataSources = dataSourceLibrary.filter((source) => source.usable);
  const configuredDataSources = dataSourceLibrary.filter((source) => source.configured);
  const configuredNotificationCount = notificationSummary.configuredChannels.length;
  const enabledNotificationCount = notificationSummary.enabledChannels.length;
  const duckdbState = statusFromBooleanConfig(allItemMap.get('QUANT_DUCKDB_ENABLED'));
  const backtestState = statusFromBooleanConfig(allItemMap.get('BACKTEST_ENABLED'));
  const scannerKey = [...allItemMap.keys()].find((key) => /^(MARKET_)?SCANNER(_AI)?_ENABLED$/i.test(key));
  const scannerState = statusFromBooleanConfig(scannerKey ? allItemMap.get(scannerKey) : undefined);
  const marketOverviewKey = [...allItemMap.keys()].find((key) => /^MARKET_OVERVIEW(_ENABLED)?$/i.test(key));
  const marketOverviewState = statusFromBooleanConfig(marketOverviewKey ? allItemMap.get(marketOverviewKey) : undefined);
  const portfolioKey = [...allItemMap.keys()].find((key) => /^PORTFOLIO(_ENABLED|_FX_UPDATE_ENABLED)?$/i.test(key));
  const portfolioState = statusFromBooleanConfig(portfolioKey ? allItemMap.get(portfolioKey) : undefined);

  const statusForToggle = (
    state: 'enabled' | 'disabled' | 'unknown',
    enabledReason: string,
    disabledReason: string,
    unknownReason: string,
    nextAction?: string,
  ): Pick<SystemHealthStatusCard, 'status' | 'reason' | 'nextAction'> => {
    if (state === 'enabled') return { status: 'available', reason: enabledReason };
    if (state === 'disabled') return { status: 'disabled', reason: disabledReason, nextAction };
    return { status: 'unknown', reason: unknownReason };
  };

  const cards: SystemHealthStatusCard[] = [
    {
      key: 'data_sources',
      label: '数据源',
      status: usableDataSources.length ? 'available' : configuredDataSources.length ? 'attention' : 'not_configured',
      reason: usableDataSources.length
        ? `${usableDataSources.length} 个可用 · ${usableDataSources.slice(0, 3).map((source) => source.label).join(' · ')}`
        : configuredDataSources.length
          ? '已配置凭据，等待连通性验证'
          : '未配置外部数据源；内置本地能力按需回退',
      nextAction: usableDataSources.length ? undefined : '进入数据源配置补齐凭据或验证连通性',
    },
    {
      key: 'market_overview',
      label: '市场总览',
      ...(
        dataSummary.market.length
          ? { status: 'available' as const, reason: `行情路径：${dataSummary.market.map(prettySourceLabel).join(' -> ')}` }
          : statusForToggle(
            marketOverviewState,
            '总览入口已启用，等待行情路径',
            '市场总览未启用',
            '未发现独立总览开关；跟随数据源可用性',
            '配置实时行情优先级',
          )
      ),
    },
    {
      key: 'scanner',
      label: '扫描器',
      ...statusForToggle(
        scannerState,
        '扫描器开关已启用',
        '扫描器未启用',
        '未发现扫描器健康字段',
        '在扫描器配置中启用后再验证',
      ),
    },
    {
      key: 'backtest',
      label: '回测',
      ...statusForToggle(
        backtestState,
        '回测服务已启用',
        '回测未启用',
        '未发现回测开关；保持按需能力',
        '需要回测时启用 BACKTEST_ENABLED',
      ),
    },
    {
      key: 'portfolio',
      label: '投资组合',
      ...statusForToggle(
        portfolioState,
        '组合相关同步已启用',
        '组合同步未启用',
        '未发现组合健康字段',
        '需要组合同步时再配置',
      ),
    },
    {
      key: 'ai',
      label: 'AI 决策',
      status: aiSummary.routeStatus === 'fully_configured'
        ? 'available'
        : aiSummary.routeStatus === 'not_configured'
          ? 'not_configured'
          : 'attention',
      reason: aiSummary.routeStatus === 'fully_configured'
        ? `主路由：${formatRouteLine(aiSummary.primaryChannel, aiSummary.primaryModel)}`
        : aiSummary.routeStatus === 'credentials_only'
          ? '已有密钥，尚未选择主路由'
          : aiSummary.routeStatus === 'partially_configured'
            ? '路由不完整，备用路径可能不可用'
            : '未配置 AI 服务商密钥',
      nextAction: aiSummary.routeStatus === 'fully_configured' ? undefined : '进入 AI 模型配置补齐主路由',
    },
    {
      key: 'notification',
      label: '通知',
      status: enabledNotificationCount ? 'available' : configuredNotificationCount ? 'attention' : 'not_configured',
      reason: enabledNotificationCount
        ? `${enabledNotificationCount} 个通道已启用`
        : configuredNotificationCount
          ? '已有通知凭据，启用状态需确认'
          : '未配置通知目标',
      nextAction: enabledNotificationCount ? undefined : '仅在通知通道页检查高层状态',
    },
    {
      key: 'duckdb',
      label: 'DuckDB 量化引擎',
      status: duckdbState === 'enabled' ? 'available' : duckdbState === 'disabled' ? 'disabled' : 'unknown',
      reason: duckdbState === 'enabled'
        ? '可选量化加速已启用'
        : duckdbState === 'disabled'
          ? '量化加速未启用；默认 Python 路径继续可用'
          : '未发现 DuckDB 健康字段',
      nextAction: duckdbState === 'disabled' ? '需要因子加速时再启用' : undefined,
      optional: true,
    },
    {
      key: 'logs',
      label: '日志中心',
      status: 'available',
      reason: '执行日志入口可用，原始诊断保持收起',
    },
  ];

  const optionalMissing: SystemHealthStatusCard[] = [];
  const flake8State = statusFromBooleanConfig(allItemMap.get('FLAKE8_AVAILABLE') ?? allItemMap.get('FLAKE8_INSTALLED'));
  if (flake8State === 'disabled') {
    optionalMissing.push({
      key: 'optional_flake8',
      label: '可选代码检查',
      status: 'attention',
      reason: 'flake8 未安装；不影响运行时分析',
      nextAction: '需要本地静态检查时安装 flake8',
      optional: true,
    });
  }
  const akshareState = statusFromBooleanConfig(allItemMap.get('AKSHARE_AVAILABLE') ?? allItemMap.get('AKSHARE_INSTALLED'));
  if (akshareState === 'disabled') {
    optionalMissing.push({
      key: 'optional_akshare',
      label: 'A股扩展数据源',
      status: 'attention',
      reason: 'akshare 未安装；外部数据源与回退路径继续可用',
      nextAction: '需要 A股扩展数据时安装 akshare',
      optional: true,
    });
  }
  const systemStatusCards = [...cards, ...optionalMissing];

  const countByStatus = (statuses: SettingsSystemHealthStatus[]) => systemStatusCards
    .filter((card) => statuses.includes(card.status))
    .length;
  const available = countByStatus(['available']);
  const attention = countByStatus(['attention']);
  const notConfigured = countByStatus(['not_configured', 'disabled']);
  const unavailable = countByStatus(['unavailable', 'unknown']);
  const systemHealthSummaryCards: SystemHealthSummaryCard[] = [
    {
      key: 'health',
      label: '系统健康',
      value: attention || unavailable ? '需关注' : '正常',
      detail: attention || unavailable ? '存在需确认项目' : '核心路径可用',
      status: attention || unavailable ? 'attention' : 'available',
    },
    {
      key: 'available',
      label: '可用',
      value: available,
      detail: '核心或已启用能力',
      status: 'available',
    },
    {
      key: 'attention',
      label: '需关注',
      value: attention,
      detail: '可选缺失或配置不完整',
      status: attention ? 'attention' : 'available',
    },
    {
      key: 'not_configured',
      label: '未配置',
      value: notConfigured,
      detail: '未启用不等于故障',
      status: 'not_configured',
    },
    {
      key: 'unavailable',
      label: '暂不可用',
      value: unavailable,
      detail: unavailable ? '缺少健康字段或不可达' : '暂无阻断',
      status: unavailable ? 'unknown' : 'available',
    },
    {
      key: 'checked',
      label: '最近检查',
      value: '当前快照',
      detail: '未写入或初始化运行时',
      status: 'unknown',
    },
    {
      key: 'environment',
      label: '环境状态',
      value: attention ? '可选需补齐' : '稳定',
      detail: '可选依赖按非阻断处理',
      status: attention ? 'attention' : 'available',
    },
  ];

  const rawEditableCount = allItems.filter(isRawEditableConfigItem).length;
  const hiddenCount = allItems.filter((item) => !isRawEditableConfigItem(item)).length;
  const safeSample = allItems
    .filter(isRawEditableConfigItem)
    .slice(0, 4)
    .map((item) => `${item.key}=${summarizeSafeConfigValue(item)}`)
    .join(' · ');
  const developerDetailGroups: DeveloperDetailGroup[] = [
    {
      key: 'raw_diagnostics',
      label: '原始诊断',
      detail: '未展开前不显示原始配置载荷。',
    },
    {
      key: 'config_keys',
      label: '配置键',
      detail: `${rawEditableCount} 个可安全编辑键；${hiddenCount} 个敏感/托管键已隐藏`,
    },
    {
      key: 'environment_summary',
      label: '环境摘要',
      detail: safeSample || '暂无可展示的安全摘要',
    },
  ];

  const globalAdminStats = [
    {
      key: 'providers',
      label: t('settings.controlPlaneStatProviders'),
      value: String(aiSummary.configuredProviders.length),
      detail: aiSummary.configuredProviders.length
        ? aiSummary.configuredProviders.map(([name]) => providerLabel(name)).join(' · ')
        : t('settings.notConfigured'),
    },
    {
      key: 'data',
      label: t('settings.controlPlaneStatDataSources'),
      value: String(usableDataSources.length),
      detail: usableDataSources.length
        ? usableDataSources.map((source) => source.label).slice(0, 4).join(' · ')
        : t('settings.dataSourceNoUsableSources'),
    },
  ];

  const heroItems: BentoHeroItem[] = [
    ...globalAdminStats.map((item) => ({
      label: item.label,
      value: item.value,
      detail: item.detail,
      tone: item.key === 'providers' && Number(item.value) > 0 ? 'bullish' as const : 'neutral' as const,
      testId: `settings-bento-hero-${item.key}`,
      valueTestId: item.key === 'providers' ? 'settings-bento-hero-providers-value' : undefined,
    })),
    {
      label: t('settings.domainTitle'),
      value: workspaceDomainCount,
      detail: activeDomainTitle,
      testId: 'settings-bento-hero-domains',
    },
    {
      label: t('settings.save'),
      value: dirtyCount || 0,
      detail: dirtyCount ? t('settings.saving') : t('settings.success'),
      tone: dirtyCount ? 'bearish' : 'bullish',
      testId: 'settings-bento-hero-dirty',
      valueTestId: 'settings-bento-hero-dirty-value',
    },
  ];

  return {
    globalAdminStats,
    heroItems,
    systemStatusCards,
    systemHealthSummaryCards,
    developerDetailGroups,
    duckdbConfigEnabledState: duckdbState,
  };
}
