import type React from 'react';
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { PanelRightOpen } from 'lucide-react';
import { getParsedApiError } from '../api/error';
import { systemConfigApi, SystemConfigValidationError } from '../api/systemConfig';
import { ApiErrorAlert, Button, ConfirmDialog, Disclosure, Drawer, GlassCard, Input, Select } from '../components/common';
import { PageBriefDrawer } from '../components/home-bento';
import { useIsDesktopViewport } from '../components/layout/useIsDesktopViewport';
import AIProviderConfig from '../components/settings/AIProviderConfig';
import DataSourceConfig from '../components/settings/DataSourceConfig';
import DataSourceLibraryDrawer from '../components/settings/DataSourceLibraryDrawer';
import { NotificationChannelsConfig } from '../components/settings/NotificationChannelsConfig';
import SystemControlPlane from '../components/settings/SystemControlPlane';
import SystemLogsConfig from '../components/settings/SystemLogsConfig';
import {
  type DataRouteKey,
} from '../components/settings/dataSourceLibraryShared';
import { useDataSourceLibraryController } from '../components/settings/useDataSourceLibraryController';
import { useI18n } from '../contexts/UiLanguageContext';
import { useAuth, useSystemConfig } from '../hooks';
import type { SystemConfigCategory } from '../types/systemConfig';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';
import {
  GATEWAY_READINESS_NOTES,
  getGatewayModelOptions,
  isGatewayModelCompatible,
  KNOWN_GATEWAY_MODEL_PRESETS,
  parseGatewayFromModel as parseGatewayFromModelId,
  supportsCustomModelId,
} from '../utils/aiRouting';
import { getCategoryDescription, getCategoryTitle } from '../utils/systemConfigI18n';
import {
  buildRawSettingsPanelState,
  buildSystemControlPlaneState,
  isRawEditableConfigItem,
} from '../components/settings/settingsDerivedState';
import {
  AuthSettingsCard,
  ChangePasswordCard,
  IntelligentImport,
  SettingsAlert,
  SettingsCategoryNav,
  SettingsField,
  SettingsLoading,
  SettingsSectionCard,
} from '../components/settings';

type SettingsDomain = 'ai_models' | 'data_sources' | 'notifications' | 'advanced';
type SettingsWorkspacePanel = 'overview' | SettingsDomain;
type RoutingTier = 'primary' | 'backup' | 'fallback';
type RouteModelMode = 'provider_default' | 'explicit';
type ModelInputMode = 'preset' | 'custom';
type AiRoutingScope = 'analysis' | 'ask_stock' | 'both';
type OverrideTaskKey = 'stock_chat' | 'backtest';
type QuickProviderKey = 'aihubmix' | 'gemini' | 'openai' | 'anthropic' | 'deepseek' | 'zhipu';
type QuickProviderTestStatus = 'idle' | 'loading' | 'success' | 'error';
type QuickProviderTestState = {
  status: QuickProviderTestStatus;
  text: string;
};
type AdvancedNavigationContext = {
  provider: QuickProviderKey;
  channelName?: string;
  hasChannel: boolean;
};

const LazyLLMChannelEditor = lazy(async () => {
  const module = await import('../components/settings/LLMChannelEditor');
  return { default: module.LLMChannelEditor };
});

const SEGMENT_WRAPPER_CLASS = 'inline-flex rounded-xl border border-white/10 bg-white/[0.02] p-1';
const SEGMENT_BUTTON_CLASS = 'rounded-lg px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] transition-colors';
const CONSOLE_NAV_BUTTON_CLASS = 'w-full rounded-xl px-3 py-2 text-left text-sm transition-colors';
const CONTROL_GHOST_BUTTON_CLASS = 'px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/10 hover:bg-white/10 text-xs transition-colors';
const GHOST_TAG_CLASS = 'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] uppercase tracking-widest font-bold bg-white/5 text-white/40 border border-white/5';
const DRAWER_PANEL_CLASS = 'rounded-xl border border-white/5 bg-white/[0.02] px-4 py-3';
const DRAWER_SECTION_CLASS = 'rounded-xl border border-white/5 bg-white/[0.015] px-4 py-4';
const DRAWER_ADVANCED_SUMMARY_CLASS = 'mt-6 flex cursor-pointer list-none items-center gap-1.5 border-t border-white/5 pt-4 text-xs text-white/30 transition-colors hover:text-white [&::-webkit-details-marker]:hidden';
const SETTINGS_DRAWER_GHOST_FORM_SCOPE_CLASS = '[&_.input-surface]:!rounded-lg [&_.input-surface]:!border-white/5 [&_.input-surface]:!bg-white/[0.02] [&_.input-surface]:!py-2 [&_.input-surface]:!text-sm [&_.input-surface]:!text-white [&_.input-surface]:!transition-all [&_.input-surface]:placeholder:!text-white/20 [&_.input-surface]:focus:!border-indigo-500/50 [&_.input-surface]:focus:!bg-white/[0.05] [&_.input-surface]:focus:!outline-none [&_.input-surface]:focus:!ring-1 [&_.input-surface]:focus:!ring-indigo-500/50 [&_.theme-field-label]:!mb-1.5 [&_.theme-field-label]:!block [&_.theme-field-label]:!text-[10px] [&_.theme-field-label]:!font-bold [&_.theme-field-label]:!uppercase [&_.theme-field-label]:!tracking-widest [&_.theme-field-label]:!text-white/40';

type RoutingDraftState = {
  ai: {
    primaryChannel: string;
    backupChannel: string;
    primaryModel: string;
    backupModel: string;
  };
  market: {
    primary: string;
    backup: string;
    fallback: string;
  };
  fundamentals: {
    primary: string;
    backup: string;
    fallback: string;
  };
  news: {
    primary: string;
    backup: string;
  };
  sentiment: {
    primary: string;
    backup: string;
  };
  notification: {
    primary: string;
    backup: string;
  };
};

const DOMAIN_ORDER: SettingsDomain[] = ['ai_models', 'data_sources', 'notifications', 'advanced'];

const CATEGORY_TO_DOMAIN: Partial<Record<SystemConfigCategory, SettingsDomain>> = {
  ai_model: 'ai_models',
  data_source: 'data_sources',
  notification: 'notifications',
  system: 'advanced',
  agent: 'advanced',
  backtest: 'advanced',
  quant: 'advanced',
  base: 'advanced',
  uncategorized: 'advanced',
};

const FALSE_VALUES = new Set(['', '0', 'false', 'no', 'off']);
const PROVIDER_LABEL_MAP: Record<string, string> = {
  aihubmix: 'AIHubMix',
  gemini: 'Gemini',
  openai: 'OpenAI',
  deepseek: 'DeepSeek',
  anthropic: 'Anthropic',
  zhipu: 'GLM / Zhipu',
};

const splitCsv = (value?: string): string[] => (value || '')
  .split(',')
  .map((entry) => entry.trim())
  .filter(Boolean);

const uniqueValues = (values: Array<string | null | undefined>): string[] => {
  const seen = new Set<string>();
  const list: string[] = [];
  values.forEach((value) => {
    const normalized = String(value || '').trim();
    if (!normalized || seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    list.push(normalized);
  });
  return list;
};

const hasConfigValue = (value: string): boolean => String(value || '').trim().length > 0;
const isEnabledValue = (value: string | undefined): boolean => {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return false;
  return !FALSE_VALUES.has(normalized);
};
const normalizeGatewayKey = (value: string): string => String(value || '').trim().toLowerCase();
const parseGatewayFromModel = (value: string): string => parseGatewayFromModelId(value);

const normalizeLabel = (value: string): string => value
  .replace(/[_-]+/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

const titleCase = (value: string): string => normalizeLabel(value)
  .split(' ')
  .map((segment) => segment ? `${segment[0].toUpperCase()}${segment.slice(1).toLowerCase()}` : segment)
  .join(' ');

const prettySourceLabel = (value: string): string => {
  const normalized = normalizeLabel(value);
  if (!normalized) return '';
  if (/^[A-Z0-9_-]{2,}$/.test(normalized)) {
    return normalized;
  }
  return titleCase(normalized);
};
const providerLabel = (value: string): string => {
  const normalized = normalizeGatewayKey(value);
  if (!normalized) return '';
  return PROVIDER_LABEL_MAP[normalized] || prettySourceLabel(normalized);
};

const inferRouteModelMode = (
  gateway: string,
  model: string,
  options: string[],
): RouteModelMode => {
  const normalizedGateway = gateway.trim();
  const normalizedModel = model.trim();
  if (!normalizedGateway || !normalizedModel) {
    return 'provider_default';
  }
  if (!options.includes(normalizedModel)) {
    return 'provider_default';
  }
  return normalizedModel === (options[0] || '')
    ? 'provider_default'
    : 'explicit';
};

const parseNotificationChannel = (key: string): string => key
  .replace(/_(ENABLED|SWITCH|TOGGLE)$/i, '')
  .replace(/_(WEBHOOK|URL|TOKEN|CHAT_ID|EMAIL)$/i, '')
  .trim();

const buildAdminLogsPath = (): string => {
  if (typeof window === 'undefined') {
    return '/admin/logs';
  }
  const locale = parseLocaleFromPathname(window.location.pathname);
  return locale ? buildLocalizedPath('/admin/logs', locale) : '/admin/logs';
};

const findFirstKey = (keys: string[], patterns: RegExp[], fallbackKey: string): string => {
  const matched = keys.find((key) => patterns.some((pattern) => pattern.test(key)));
  return matched || fallbackKey;
};

const toRouteState = (values: string[], allowThird = true) => ({
  primary: values[0] || '',
  backup: values[1] || '',
  fallback: allowThird ? (values[2] || '') : '',
});

const AI_PROVIDER_CREDENTIAL_RULES: Array<{ gateway: string; patterns: RegExp[] }> = [
  {
    gateway: 'aihubmix',
    patterns: [/^AIHUBMIX_KEY$/i, /^AIHUBMIX_KEYS$/i, /^AIHUBMIX_API_KEYS?$/i, /^LLM_AIHUBMIX_API_KEYS?$/i],
  },
  {
    gateway: 'gemini',
    patterns: [/^GEMINI_API_KEYS?$/i, /^LLM_GEMINI_API_KEYS?$/i],
  },
  {
    gateway: 'openai',
    patterns: [/^OPENAI_API_KEYS?$/i, /^LLM_OPENAI_API_KEYS?$/i],
  },
  {
    gateway: 'deepseek',
    patterns: [/^DEEPSEEK_API_KEYS?$/i, /^LLM_DEEPSEEK_API_KEYS?$/i],
  },
  {
    gateway: 'anthropic',
    patterns: [/^ANTHROPIC_API_KEYS?$/i, /^LLM_ANTHROPIC_API_KEYS?$/i],
  },
  {
    gateway: 'zhipu',
    patterns: [/^ZHIPU_API_KEYS?$/i, /^LLM_ZHIPU_API_KEYS?$/i],
  },
];
const DIRECT_PROVIDER_KEY_CANDIDATES: Record<QuickProviderKey, string[]> = {
  aihubmix: ['AIHUBMIX_KEY', 'AIHUBMIX_KEYS', 'AIHUBMIX_API_KEY', 'AIHUBMIX_API_KEYS'],
  gemini: ['GEMINI_API_KEY', 'GEMINI_API_KEYS'],
  openai: ['OPENAI_API_KEY', 'OPENAI_API_KEYS'],
  anthropic: ['ANTHROPIC_API_KEY', 'ANTHROPIC_API_KEYS'],
  deepseek: ['DEEPSEEK_API_KEY', 'DEEPSEEK_API_KEYS'],
  zhipu: ['ZHIPU_API_KEY', 'ZHIPU_API_KEYS', 'LLM_ZHIPU_API_KEY', 'LLM_ZHIPU_API_KEYS'],
};

const PROVIDER_LIBRARY_ITEMS: Array<{
  key: QuickProviderKey;
  label: string;
  mode: 'direct' | 'advanced';
}> = [
  { key: 'gemini', label: 'Gemini', mode: 'direct' },
  { key: 'aihubmix', label: 'AIHubMix', mode: 'direct' },
  { key: 'openai', label: 'OpenAI', mode: 'direct' },
  { key: 'anthropic', label: 'Anthropic', mode: 'direct' },
  { key: 'deepseek', label: 'DeepSeek', mode: 'direct' },
  { key: 'zhipu', label: 'GLM / Zhipu', mode: 'direct' },
];
const QUICK_PROVIDER_PROTOCOL: Record<QuickProviderKey, string> = {
  aihubmix: 'openai',
  gemini: 'gemini',
  openai: 'openai',
  anthropic: 'anthropic',
  deepseek: 'deepseek',
  zhipu: 'openai',
};
const QUICK_PROVIDER_BASE_URL: Record<QuickProviderKey, string> = {
  aihubmix: 'https://aihubmix.com/v1',
  gemini: '',
  openai: 'https://api.openai.com/v1',
  anthropic: '',
  deepseek: 'https://api.deepseek.com/v1',
  zhipu: 'https://open.bigmodel.cn/api/paas/v4',
};
const QUICK_PROVIDER_DEFAULT_TEST_MODEL: Record<QuickProviderKey, string> = {
  aihubmix: 'openai/gpt-4.1-mini',
  gemini: 'gemini/gemini-2.5-flash',
  openai: 'openai/gpt-4.1-mini',
  anthropic: 'anthropic/claude-3-5-sonnet',
  deepseek: 'deepseek/deepseek-chat',
  zhipu: 'zhipu/glm-4-flash',
};

type TaskOverrideDraft = {
  inherit: boolean;
  gateway: string;
  model: string;
};

const credentialEntryCount = (value: string, rawValueExists: boolean): number => {
  const normalized = String(value || '').trim();
  if (normalized) {
    return splitCsv(normalized).length || 1;
  }
  return rawValueExists ? 1 : 0;
};

const SettingsPage: React.FC = () => {
  const isDesktopViewport = useIsDesktopViewport();
  const { language, t } = useI18n();
  const { passwordChangeable } = useAuth();
  const isSystemSettingsSurface = typeof window !== 'undefined' && window.location.pathname.includes('/settings/system');

  const {
    categories,
    itemsByCategory,
    issueByKey,
    activeCategory,
    setActiveCategory,
    hasDirty,
    dirtyCount,
    toast,
    clearToast,
    isLoading,
    isSaving,
    loadError,
    saveError,
    retryAction,
    load,
    retry,
    save,
    saveExternalItems,
    resetDraft,
    setDraftValue,
    adminUnlockToken,
  } = useSystemConfig();
  const [activeDomain, setActiveDomain] = useState<SettingsDomain>('advanced');
  const [activePanel, setActivePanel] = useState<SettingsWorkspacePanel>(isSystemSettingsSurface ? 'overview' : 'advanced');
  const [isBriefDrawerOpen, setIsBriefDrawerOpen] = useState(false);

  useEffect(() => {
    document.title = t('settings.documentTitle');
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timer = window.setTimeout(() => {
      clearToast();
    }, 3200);

    return () => {
      window.clearTimeout(timer);
    };
  }, [clearToast, toast]);

  const rawActiveItems = itemsByCategory[activeCategory] || [];
  const rawActiveItemMap = new Map(rawActiveItems.map((item) => [item.key, String(item.value ?? '')]));
  const allItems = useMemo(() => Object.values(itemsByCategory).flat(), [itemsByCategory]);
  const allItemMap = useMemo(
    () => new Map(allItems.map((item) => [item.key, String(item.value ?? '')])),
    [allItems],
  );
  const categoryDomainMap = useMemo(() => {
    const map = new Map<string, SettingsDomain>();
    categories.forEach((category) => {
      map.set(
        category.category,
        CATEGORY_TO_DOMAIN[category.category as SystemConfigCategory] || 'advanced',
      );
    });
    return map;
  }, [categories]);
  const domainCategories = useMemo(
    () => categories.filter((category) => (categoryDomainMap.get(category.category) || 'advanced') === activeDomain),
    [activeDomain, categories, categoryDomainMap],
  );
  const domainCategorySet = useMemo(
    () => new Set(domainCategories.map((category) => category.category)),
    [domainCategories],
  );
  const hasConfiguredChannels = Boolean((rawActiveItemMap.get('LLM_CHANNELS') || '').trim());
  const hasLitellmConfig = Boolean((rawActiveItemMap.get('LITELLM_CONFIG') || '').trim());
  const rawEditableActiveItems = useMemo(
    () => (itemsByCategory[activeCategory] || []).filter(isRawEditableConfigItem),
    [activeCategory, itemsByCategory],
  );
  const rawPanelState = useMemo(() => buildRawSettingsPanelState({
    activeCategory,
    rawEditableActiveItems,
    hasConfiguredChannels,
    hasLitellmConfig,
    t,
  }), [activeCategory, hasConfiguredChannels, hasLitellmConfig, rawEditableActiveItems, t]);
  const { activeItems, rawFieldsSummaryText } = rawPanelState;
  const activeCategoryDescription = getCategoryDescription(language, activeCategory as SystemConfigCategory, '') || t('settings.currentCategoryDesc');
  const activeCategoryLabel = getCategoryTitle(
    language,
    activeCategory as SystemConfigCategory,
    categories.find((category) => category.category === activeCategory)?.title || '',
  );
  const shouldCollapseRawFields = ['ai_model', 'data_source', 'notification', 'system', 'base'].includes(activeCategory);
  const rawFieldsSectionTitle = shouldCollapseRawFields
    ? t('settings.rawFieldsSectionTitle')
    : t('settings.currentCategory');
  const rawFieldsSectionDescription = shouldCollapseRawFields
    ? t('settings.rawFieldsSectionDesc')
    : activeCategoryDescription;
  const rawFieldsToggleLabel = activeCategory === 'ai_model'
    ? t('settings.aiRawFieldsToggle')
    : t('settings.rawFieldsToggle');

  useEffect(() => {
    const inferredDomain = categoryDomainMap.get(activeCategory) || 'advanced';
    setActiveDomain((previous) => (previous === inferredDomain ? previous : inferredDomain));
    setActivePanel((previous) => (previous === 'overview' ? previous : inferredDomain));
  }, [activeCategory, categoryDomainMap]);

  useEffect(() => {
    if (domainCategorySet.size === 0) {
      return;
    }
    if (domainCategorySet.has(activeCategory as SystemConfigCategory)) {
      return;
    }
    const firstCategory = domainCategories[0]?.category;
    if (firstCategory) {
      setActiveCategory(firstCategory);
    }
  }, [activeCategory, domainCategories, domainCategorySet, setActiveCategory]);

  const panelNavItems = useMemo(() => ([
    {
      domain: 'overview' as const,
      title: t('settings.controlPlaneTitle'),
      desc: t('settings.controlPlaneDesc'),
    },
    {
      domain: 'ai_models' as const,
      title: t('settings.domainAiTitle'),
      desc: t('settings.domainAiDesc'),
    },
    {
      domain: 'data_sources' as const,
      title: t('settings.domainDataTitle'),
      desc: t('settings.domainDataDesc'),
    },
    {
      domain: 'notifications' as const,
      title: language === 'zh' ? '通知通道' : 'Notification Channels',
      desc: language === 'zh' ? '专用通知凭据' : 'Curated notification credentials',
    },
    {
      domain: 'advanced' as const,
      title: t('settings.domainAdvancedTitle'),
      desc: t('settings.domainAdvancedDesc'),
    },
  ]), [language, t]);

  const aiRoutingKeys = useMemo(() => {
    const keys = [...allItemMap.keys()];
    return {
      primaryGateway: findFirstKey(keys, [/^AI_PRIMARY_GATEWAY$/i], 'AI_PRIMARY_GATEWAY'),
      primaryModel: findFirstKey(keys, [/^AI_PRIMARY_MODEL$/i], 'AI_PRIMARY_MODEL'),
      backupGateway: findFirstKey(keys, [/^AI_BACKUP_GATEWAY$/i], 'AI_BACKUP_GATEWAY'),
      backupModel: findFirstKey(keys, [/^AI_BACKUP_MODEL$/i], 'AI_BACKUP_MODEL'),
    };
  }, [allItemMap]);

  const aiGatewayModelMap = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const [key, value] of allItemMap.entries()) {
      const matched = key.match(/^LLM_([A-Z0-9]+)_MODELS$/i);
      if (!matched) continue;
      const gateway = normalizeGatewayKey(matched[1] || '');
      const models = splitCsv(value);
      if (!gateway || !models.length) continue;
      map.set(gateway, uniqueValues([...(map.get(gateway) || []), ...models]));
    }
    return map;
  }, [allItemMap]);

  const aiCredentialProviders = useMemo(() => {
    const counts = new Map<string, number>();
    const addProviderCount = (gateway: string, count: number) => {
      const normalizedGateway = normalizeGatewayKey(gateway);
      if (!normalizedGateway || count <= 0) return;
      counts.set(normalizedGateway, (counts.get(normalizedGateway) || 0) + count);
    };

    allItems.forEach((item) => {
      const key = item.key;
      let matchedGateway = '';
      const explicitRule = AI_PROVIDER_CREDENTIAL_RULES.find((rule) => rule.patterns.some((pattern) => pattern.test(key)));
      if (explicitRule) {
        matchedGateway = explicitRule.gateway;
      } else {
        const legacyMatch = key.match(/^LLM_([A-Z0-9]+)_API_KEYS?$/i);
        if (legacyMatch) {
          matchedGateway = normalizeGatewayKey(legacyMatch[1] || '');
        }
      }
      if (!matchedGateway) return;
      const count = credentialEntryCount(String(item.value || ''), Boolean(item.rawValueExists));
      if (count <= 0) return;
      addProviderCount(matchedGateway, count);
    });

    // Route editor availability should be derived from credential readiness only.
    // Do not depend on legacy LLM_CHANNELS, which is channel-editor-owned.
    const configuredChannels = [...counts.keys()];

    return {
      configuredProviderMap: counts,
      configuredProviders: [...counts.entries()],
      configuredChannels,
      configuredCount: [...counts.values()].reduce((total, count) => total + count, 0),
    };
  }, [allItems]);

  const aiSummary = useMemo(() => {
    const primaryModelLegacy = allItemMap.get('LITELLM_MODEL') || '';
    const fallbackModelsLegacy = splitCsv(allItemMap.get('LITELLM_FALLBACK_MODELS'));
    const channelsLegacy = splitCsv(allItemMap.get('LLM_CHANNELS'));

    const primaryChannel = allItemMap.get(aiRoutingKeys.primaryGateway) || channelsLegacy[0] || '';
    const backupChannel = allItemMap.get(aiRoutingKeys.backupGateway) || channelsLegacy[1] || '';
    const primaryModel = allItemMap.get(aiRoutingKeys.primaryModel) || primaryModelLegacy || '';
    const backupModel = allItemMap.get(aiRoutingKeys.backupModel) || fallbackModelsLegacy[0] || '';
    const provider = parseGatewayFromModel(primaryModel);
    const configuredApiCount = aiCredentialProviders.configuredCount;
    const hasPrimaryRoute = Boolean(primaryChannel && primaryModel);
    const hasBackupRoute = Boolean(backupChannel && backupModel);
    const routeConfigured = hasPrimaryRoute && hasBackupRoute;
    const routeMissingButApiConfigured = !routeConfigured && configuredApiCount > 0;
    const routeStatus: 'fully_configured' | 'partially_configured' | 'credentials_only' | 'not_configured' =
      routeConfigured
        ? 'fully_configured'
        : (hasPrimaryRoute || hasBackupRoute)
          ? 'partially_configured'
          : routeMissingButApiConfigured
            ? 'credentials_only'
            : 'not_configured';

    return {
      primaryModel,
      provider,
      primaryChannel,
      backupChannel,
      backupModel,
      fallbackModels: uniqueValues([backupModel, ...fallbackModelsLegacy]),
      modelRoute: [primaryModel, backupModel, ...fallbackModelsLegacy].filter(Boolean),
      configuredProviders: aiCredentialProviders.configuredProviders,
      configuredApiCount,
      hasPrimaryRoute,
      hasBackupRoute,
      routeConfigured,
      routeMissingButApiConfigured,
      routeStatus,
    };
  }, [aiCredentialProviders.configuredCount, aiCredentialProviders.configuredProviders, aiRoutingKeys.backupGateway, aiRoutingKeys.backupModel, aiRoutingKeys.primaryGateway, aiRoutingKeys.primaryModel, allItemMap]);

  const dataPriorityKeys = useMemo(() => {
    const keys = [...allItemMap.keys()];
    return {
      market: findFirstKey(keys, [/^REALTIME_SOURCE_PRIORITY$/i, /MARKET.*PRIORITY/i], 'REALTIME_SOURCE_PRIORITY'),
      fundamentals: findFirstKey(keys, [/(FUNDAMENTAL|FINANCIAL|EARNINGS).*PRIORITY/i], 'FUNDAMENTAL_SOURCE_PRIORITY'),
      news: findFirstKey(keys, [/NEWS.*PRIORITY/i], 'NEWS_SOURCE_PRIORITY'),
      sentiment: findFirstKey(keys, [/SENTIMENT.*PRIORITY/i], 'SENTIMENT_SOURCE_PRIORITY'),
      notification: findFirstKey(keys, [/NOTIFICATION.*PRIORITY/i, /CHANNEL.*PRIORITY/i], 'NOTIFICATION_CHANNEL_PRIORITY'),
    };
  }, [allItemMap]);
  const runtimeSummaryVisibilityKey = useMemo(() => {
    const keys = [...allItemMap.keys()];
    return findFirstKey(keys, [/^SHOW_RUNTIME_EXECUTION_SUMMARY$/i], 'SHOW_RUNTIME_EXECUTION_SUMMARY');
  }, [allItemMap]);

  const dataSummary = useMemo(() => {
    const market = allItemMap.get(dataPriorityKeys.market) || '';
    const fundamentals = allItemMap.get(dataPriorityKeys.fundamentals) || '';
    const news = allItemMap.get(dataPriorityKeys.news) || '';
    const sentiment = allItemMap.get(dataPriorityKeys.sentiment) || '';
    const sharedNewsSentiment = [...allItemMap.entries()].find(([key, value]) => {
      return value.trim().length > 0 && /(NEWS|SENTIMENT).*PRIORITY/i.test(key);
    })?.[1] || '';

    return {
      market: splitCsv(market),
      fundamentals: splitCsv(fundamentals),
      news: splitCsv(news || sharedNewsSentiment),
      sentiment: splitCsv(sentiment || sharedNewsSentiment),
    };
  }, [allItemMap, dataPriorityKeys]);

  const notificationSummary = useMemo(() => {
    const notificationItems = itemsByCategory.notification || [];
    const configuredChannels: string[] = [];
    const enabledChannels: string[] = [];
    const destinations: string[] = [];

    notificationItems.forEach((item) => {
      const value = String(item.value || '').trim();
      if (!value) {
        return;
      }
      const channel = parseNotificationChannel(item.key);
      if (channel) {
        configuredChannels.push(channel.toLowerCase());
      }
      if (/ENABLED|SWITCH|TOGGLE/i.test(item.key) && !FALSE_VALUES.has(value.toLowerCase())) {
        if (channel) {
          enabledChannels.push(channel.toLowerCase());
        }
      }
      if (/(WEBHOOK|EMAIL|TOKEN|CHAT|DINGTALK|DISCORD|WECHAT|PUSHPLUS)/i.test(item.key)) {
        destinations.push(item.key);
      }
    });

    return {
      configuredChannels: [...new Set(configuredChannels)],
      enabledChannels: [...new Set(enabledChannels)],
      destinations,
    };
  }, [itemsByCategory.notification]);
  const notificationRoute = useMemo(() => {
    const explicit = splitCsv(allItemMap.get(dataPriorityKeys.notification));
    if (explicit.length) {
      return explicit;
    }
    return notificationSummary.enabledChannels.length
      ? notificationSummary.enabledChannels
      : notificationSummary.configuredChannels;
  }, [allItemMap, dataPriorityKeys.notification, notificationSummary.configuredChannels, notificationSummary.enabledChannels]);

  const availableProviders = useMemo(() => {
    const hasAny = (...keys: string[]): boolean => keys.some((key) => hasConfigValue(allItemMap.get(key) || ''));
    const hasByPattern = (patterns: RegExp[]): boolean => {
      for (const [key, value] of allItemMap.entries()) {
        if (!hasConfigValue(value)) continue;
        if (patterns.some((pattern) => pattern.test(key))) return true;
      }
      return false;
    };

    const aiChannels = uniqueValues([
      aiSummary.primaryChannel,
      aiSummary.backupChannel,
      ...aiCredentialProviders.configuredChannels,
    ]);

    const modelSet = new Set<string>();
    splitCsv(allItemMap.get('LITELLM_MODEL')).forEach((model) => modelSet.add(model));
    splitCsv(allItemMap.get('LITELLM_FALLBACK_MODELS')).forEach((model) => modelSet.add(model));
    [...allItemMap.entries()].forEach(([key, value]) => {
      if (!/LLM_[A-Z0-9]+_MODELS$/i.test(key)) return;
      splitCsv(value).forEach((model) => modelSet.add(model));
    });
    if (aiSummary.primaryModel) modelSet.add(aiSummary.primaryModel);
    if (aiSummary.backupModel) modelSet.add(aiSummary.backupModel);

    const market = uniqueValues([
      hasByPattern([/^ALPHA_VANTAGE_API_KEYS?$/i, /^ALPHAVANTAGE_API_KEYS?$/i]) ? 'alpha_vantage' : '',
      hasByPattern([/^FINNHUB_API_KEYS?$/i]) ? 'finnhub' : '',
      'yahoo',
    ]);
    const fundamentals = uniqueValues([
      hasByPattern([/^FMP_API_KEYS?$/i]) ? 'fmp' : '',
      hasByPattern([/^FINNHUB_API_KEYS?$/i]) ? 'finnhub' : '',
      'yahoo',
    ]);
    const news = uniqueValues([
      hasByPattern([/^GNEWS_API_KEYS?$/i]) ? 'gnews' : '',
      hasByPattern([/^TAVILY_API_KEYS?$/i]) ? 'tavily' : '',
      hasByPattern([/^FINNHUB_API_KEYS?$/i]) ? 'finnhub' : '',
    ]);
    const sentiment = uniqueValues([
      hasAny('SOCIAL_SENTIMENT_API_KEY', 'SOCIAL_SENTIMENT_API_KEYS') ? 'social_sentiment_service' : '',
      hasByPattern([/^TAVILY_API_KEYS?$/i]) ? 'tavily' : '',
      'local_inference',
    ]);

    return {
      aiChannels,
      aiModels: [...modelSet].filter(Boolean),
      market,
      fundamentals,
      news,
      sentiment,
      notifications: notificationSummary.configuredChannels,
    };
  }, [aiCredentialProviders.configuredChannels, aiSummary.backupChannel, aiSummary.backupModel, aiSummary.primaryChannel, aiSummary.primaryModel, allItemMap, notificationSummary.configuredChannels]);

  const aiSavedModels = useMemo(
    () => uniqueValues([
      aiSummary.primaryModel,
      aiSummary.backupModel,
      ...aiSummary.fallbackModels,
      ...splitCsv(allItemMap.get('LITELLM_MODEL')),
      ...splitCsv(allItemMap.get('LITELLM_FALLBACK_MODELS')),
    ]),
    [aiSummary.backupModel, aiSummary.fallbackModels, aiSummary.primaryModel, allItemMap],
  );

  const [routingDraft, setRoutingDraft] = useState<RoutingDraftState>({
    ai: { primaryChannel: '', backupChannel: '', primaryModel: '', backupModel: '' },
    market: { primary: '', backup: '', fallback: '' },
    fundamentals: { primary: '', backup: '', fallback: '' },
    news: { primary: '', backup: '' },
    sentiment: { primary: '', backup: '' },
    notification: { primary: '', backup: '' },
  });
  const [aiModelMode, setAiModelMode] = useState<{ primary: ModelInputMode; backup: ModelInputMode }>({
    primary: 'preset',
    backup: 'preset',
  });
  const [aiRouteModelMode, setAiRouteModelMode] = useState<{ primary: RouteModelMode; backup: RouteModelMode }>({
    primary: 'provider_default',
    backup: 'provider_default',
  });
  const [taskModelMode, setTaskModelMode] = useState<Record<OverrideTaskKey, ModelInputMode>>({
    stock_chat: 'preset',
    backtest: 'preset',
  });
  const [taskRouteModelMode, setTaskRouteModelMode] = useState<Record<OverrideTaskKey, RouteModelMode>>({
    stock_chat: 'provider_default',
    backtest: 'provider_default',
  });
  const [taskRoutingDraft, setTaskRoutingDraft] = useState<Record<OverrideTaskKey, TaskOverrideDraft>>({
    stock_chat: { inherit: true, gateway: '', model: '' },
    backtest: { inherit: true, gateway: '', model: '' },
  });
  const [taskRoutingError, setTaskRoutingError] = useState<Record<OverrideTaskKey, string | null>>({
    stock_chat: null,
    backtest: null,
  });
  const [aiRoutingError, setAiRoutingError] = useState<string | null>(null);
  const [showRuntimeExecutionSummary, setShowRuntimeExecutionSummary] = useState(false);
  const aiChannelConfigRef = useRef<HTMLDivElement | null>(null);
  const [advancedFocusChannelName, setAdvancedFocusChannelName] = useState('');
  const [advancedNavigationContext, setAdvancedNavigationContext] = useState<AdvancedNavigationContext | null>(null);
  const [advancedCreatePreset, setAdvancedCreatePreset] = useState<string | null>(null);
  const [aiRoutingDrawerOpen, setAiRoutingDrawerOpen] = useState(false);
  const [quickProviderDrawerProvider, setQuickProviderDrawerProvider] = useState<QuickProviderKey | null>(null);
  const [aiAdvancedDrawerOpen, setAiAdvancedDrawerOpen] = useState(false);
  const [dataRoutingDrawerKey, setDataRoutingDrawerKey] = useState<DataRouteKey | null>(null);
  const [runtimeVisibilityDrawerOpen, setRuntimeVisibilityDrawerOpen] = useState(false);
  const [rawFieldsDrawerOpen, setRawFieldsDrawerOpen] = useState(false);
  const [adminActionDialog, setAdminActionDialog] = useState<'runtime_cache' | 'factory_reset' | null>(null);
  const [adminActionMessage, setAdminActionMessage] = useState<string | null>(null);
  const [adminActionTone, setAdminActionTone] = useState<'success' | 'error'>('success');
  const [isRunningAdminAction, setIsRunningAdminAction] = useState(false);
  const [factoryResetConfirmation, setFactoryResetConfirmation] = useState('');

  useEffect(() => {
    const primaryChannel = aiSummary.primaryChannel || '';
    const backupChannel = aiSummary.backupChannel || '';
    const primaryModel = primaryChannel ? (aiSummary.primaryModel || '') : '';
    const backupModel = backupChannel ? (aiSummary.backupModel || '') : '';

    const primaryModelOptions = getGatewayModelOptions(
      primaryChannel,
      aiGatewayModelMap,
      availableProviders.aiModels,
      aiSavedModels,
    );
    const backupModelOptions = getGatewayModelOptions(
      backupChannel,
      aiGatewayModelMap,
      availableProviders.aiModels,
      aiSavedModels,
    );

    setRoutingDraft({
      ai: {
        primaryChannel,
        backupChannel,
        primaryModel,
        backupModel,
      },
      market: toRouteState(dataSummary.market, true),
      fundamentals: toRouteState(dataSummary.fundamentals, true),
      news: {
        primary: dataSummary.news[0] || '',
        backup: dataSummary.news[1] || '',
      },
      sentiment: {
        primary: dataSummary.sentiment[0] || '',
        backup: dataSummary.sentiment[1] || '',
      },
      notification: {
        primary: notificationRoute[0] || '',
        backup: notificationRoute[1] || '',
      },
    });
    setAiModelMode({
      primary: primaryChannel && primaryModel && !primaryModelOptions.includes(primaryModel) ? 'custom' : 'preset',
      backup: backupChannel && backupModel && !backupModelOptions.includes(backupModel) ? 'custom' : 'preset',
    });
    setAiRouteModelMode({
      primary: inferRouteModelMode(primaryChannel, primaryModel, primaryModelOptions),
      backup: inferRouteModelMode(backupChannel, backupModel, backupModelOptions),
    });
  }, [
    aiGatewayModelMap,
    aiSavedModels,
    aiSummary.backupChannel,
    aiSummary.backupModel,
    aiSummary.primaryChannel,
    aiSummary.primaryModel,
    availableProviders.aiModels,
    dataSummary.fundamentals,
    dataSummary.market,
    dataSummary.news,
    dataSummary.sentiment,
    notificationRoute,
  ]);
  useEffect(() => {
    setShowRuntimeExecutionSummary(isEnabledValue(allItemMap.get(runtimeSummaryVisibilityKey)));
  }, [allItemMap, runtimeSummaryVisibilityKey]);

  const adminLocked = false;
  const adminSaveDisabled = !hasDirty || isSaving || isLoading;

  const handleSave = useCallback(() => {
    void save();
  }, [save]);

  const setRouteTier = useCallback((
    section: 'market' | 'fundamentals' | 'news' | 'sentiment' | 'notification',
    tier: RoutingTier,
    value: string,
  ) => {
    setRoutingDraft((prev) => {
      if (section === 'news' || section === 'sentiment' || section === 'notification') {
        const current = prev[section];
        if (tier === 'fallback') {
          return prev;
        }
        const next = { ...current, [tier]: value };
        if (tier === 'primary' && next.backup === value) {
          next.backup = '';
        }
        if (tier === 'backup' && next.primary === value) {
          next.primary = '';
        }
        return { ...prev, [section]: next };
      }

      const current = prev[section];
      const next = { ...current, [tier]: value };
      if (tier === 'primary') {
        if (next.backup === value) next.backup = '';
        if (next.fallback === value) next.fallback = '';
      }
      if (tier === 'backup') {
        if (next.primary === value) next.primary = '';
        if (next.fallback === value) next.fallback = '';
      }
      if (tier === 'fallback') {
        if (next.primary === value) next.primary = '';
        if (next.backup === value) next.backup = '';
      }
      return { ...prev, [section]: next };
    });
  }, []);

  const effectiveRoute = useCallback((values: Array<string | undefined | null>): string[] => uniqueValues(values), []);
  const removeDataSourceFromRoutingDraft = useCallback((sourceId: string) => {
    setRoutingDraft((prev) => ({
      ...prev,
      market: toRouteState(
        effectiveRoute([prev.market.primary, prev.market.backup, prev.market.fallback].filter((value) => value !== sourceId)),
        true,
      ),
      fundamentals: toRouteState(
        effectiveRoute([prev.fundamentals.primary, prev.fundamentals.backup, prev.fundamentals.fallback].filter((value) => value !== sourceId)),
        true,
      ),
      news: {
        primary: prev.news.primary === sourceId ? '' : prev.news.primary,
        backup: prev.news.backup === sourceId ? '' : prev.news.backup,
      },
      sentiment: {
        primary: prev.sentiment.primary === sourceId ? '' : prev.sentiment.primary,
        backup: prev.sentiment.backup === sourceId ? '' : prev.sentiment.backup,
      },
    }));
  }, [effectiveRoute]);
  const {
    dataSourceDeleteTarget,
    dataSourceEditorDraft,
    dataSourceEditorEntry,
    dataSourceEditorMode,
    dataSourceEditorValidationResult,
    dataSourceLibrary,
    dataSourceLibraryDrawerOpen,
    dataSourceRouteOptions,
    managedBuiltinDataSourceDraft,
    closeDataSourceDrawer,
    deleteDataSourceEntry,
    openCreateDataSourceDrawer,
    openEditDataSourceDrawer,
    saveDataSourceEditor,
    setDataSourceDeleteTargetId,
    setDataSourceEditorDraft,
    setManagedBuiltinDataSourceDraft,
    validateDataSourceEntry,
  } = useDataSourceLibraryController({
    allItemMap,
    dataSummary,
    dataPriorityKeys: {
      market: dataPriorityKeys.market,
      fundamentals: dataPriorityKeys.fundamentals,
      news: dataPriorityKeys.news,
      sentiment: dataPriorityKeys.sentiment,
    },
    saveExternalItems,
    onDeleteSourceFromRoutes: removeDataSourceFromRoutingDraft,
    prettySourceLabel,
    t,
  });

  const modelsForGateway = useCallback((gateway: string): string[] => (
    getGatewayModelOptions(
      gateway,
      aiGatewayModelMap,
      availableProviders.aiModels,
      aiSavedModels,
    )
  ), [aiGatewayModelMap, availableProviders.aiModels, aiSavedModels]);

  const resolveProviderDefaultModel = useCallback((gateway: string): string => {
    const options = modelsForGateway(gateway);
    return options[0] || '';
  }, [modelsForGateway]);

  const primaryGatewayModels = useMemo(
    () => modelsForGateway(routingDraft.ai.primaryChannel),
    [modelsForGateway, routingDraft.ai.primaryChannel],
  );

  const backupGatewayModels = useMemo(
    () => modelsForGateway(routingDraft.ai.backupChannel),
    [modelsForGateway, routingDraft.ai.backupChannel],
  );

  const aiGatewayReadiness = useMemo(() => {
    const configuredProviderMap = new Map(aiSummary.configuredProviders);
    const gateways = uniqueValues([
      ...availableProviders.aiChannels,
      ...[...aiGatewayModelMap.keys()],
      ...[...configuredProviderMap.keys()],
      routingDraft.ai.primaryChannel,
      routingDraft.ai.backupChannel,
    ]);
    return gateways.map((gateway) => {
      const normalized = normalizeGatewayKey(gateway);
      const presets = KNOWN_GATEWAY_MODEL_PRESETS[normalized] || [];
      const inferred = aiGatewayModelMap.get(normalized) || [];
      const credentialCount = configuredProviderMap.get(normalized) || 0;
      return {
        gateway: normalized,
        label: providerLabel(normalized),
        credentialCount,
        credentialReady: credentialCount > 0,
        presetCount: presets.length,
        inferredCount: inferred.length,
        supportsCustom: supportsCustomModelId(normalized),
        noteKey: GATEWAY_READINESS_NOTES[normalized] || 'generic',
      };
    });
  }, [
    aiSummary.configuredProviders,
    aiGatewayModelMap,
    availableProviders.aiChannels,
    routingDraft.ai.backupChannel,
    routingDraft.ai.primaryChannel,
  ]);
  const aiCredentialReadyGateways = useMemo(
    () => [...aiCredentialProviders.configuredProviderMap.keys()],
    [aiCredentialProviders.configuredProviderMap],
  );
  const aiGatewaySelectorOptions = useMemo(
    () => uniqueValues([
      ...aiCredentialReadyGateways,
      routingDraft.ai.primaryChannel,
      routingDraft.ai.backupChannel,
    ]).filter(Boolean),
    [aiCredentialReadyGateways, routingDraft.ai.backupChannel, routingDraft.ai.primaryChannel],
  );
  const aiConfiguredGatewayCount = aiCredentialReadyGateways.length;
  const canSelectPrimaryGateway = aiConfiguredGatewayCount >= 1;
  const canSelectBackupGateway = aiConfiguredGatewayCount >= 2;
  const aiSelectorReadinessMismatch = useMemo(() => {
    const readinessHasConfiguredProvider = aiGatewayReadiness.some((provider) => provider.credentialReady);
    return readinessHasConfiguredProvider && aiGatewaySelectorOptions.length === 0;
  }, [aiGatewayReadiness, aiGatewaySelectorOptions.length]);

  const primaryGatewayDisabledReason = useMemo(() => {
    if (adminLocked) return t('settings.adminSaveLocked');
    if (isSaving) return t('settings.saving');
    if (!canSelectPrimaryGateway) return t('settings.aiPrimaryGatewayDisabledReason');
    return '';
  }, [adminLocked, canSelectPrimaryGateway, isSaving, t]);

  const backupGatewayDisabledReason = useMemo(() => {
    if (adminLocked) return t('settings.adminSaveLocked');
    if (isSaving) return t('settings.saving');
    if (!canSelectBackupGateway) return t('settings.aiBackupGatewayDisabledReason');
    return '';
  }, [adminLocked, canSelectBackupGateway, isSaving, t]);

  const primaryModelCompatible = useMemo(
    () => isGatewayModelCompatible(routingDraft.ai.primaryChannel, routingDraft.ai.primaryModel, primaryGatewayModels),
    [primaryGatewayModels, routingDraft.ai.primaryChannel, routingDraft.ai.primaryModel],
  );
  const backupModelCompatible = useMemo(
    () => isGatewayModelCompatible(routingDraft.ai.backupChannel, routingDraft.ai.backupModel, backupGatewayModels),
    [backupGatewayModels, routingDraft.ai.backupChannel, routingDraft.ai.backupModel],
  );

  useEffect(() => {
    setRoutingDraft((prev) => {
      const next = { ...prev, ai: { ...prev.ai } };
      let changed = false;

      if (!next.ai.primaryChannel && next.ai.primaryModel) {
        next.ai.primaryModel = '';
        changed = true;
      }
      if (!next.ai.backupChannel && next.ai.backupModel) {
        next.ai.backupModel = '';
        changed = true;
      }

      if (next.ai.primaryChannel && aiRouteModelMode.primary === 'provider_default') {
        const defaultModel = resolveProviderDefaultModel(next.ai.primaryChannel);
        if (next.ai.primaryModel !== defaultModel) {
          next.ai.primaryModel = defaultModel;
          changed = true;
        }
      } else if (next.ai.primaryChannel && aiModelMode.primary === 'preset') {
        const primaryOptions = primaryGatewayModels;
        if (primaryOptions.length === 0) {
          if (next.ai.primaryModel) {
            next.ai.primaryModel = '';
            changed = true;
          }
        } else if (!primaryOptions.includes(next.ai.primaryModel)) {
          next.ai.primaryModel = primaryOptions[0];
          changed = true;
        }
      }

      if (next.ai.backupChannel && aiRouteModelMode.backup === 'provider_default') {
        const defaultModel = resolveProviderDefaultModel(next.ai.backupChannel);
        const backupCandidate = defaultModel && defaultModel !== next.ai.primaryModel
          ? defaultModel
          : backupGatewayModels.find((model) => model !== next.ai.primaryModel) || '';
        if (next.ai.backupModel !== backupCandidate) {
          next.ai.backupModel = backupCandidate;
          changed = true;
        }
      } else if (next.ai.backupChannel && aiModelMode.backup === 'preset') {
        const backupOptions = backupGatewayModels.filter((model) => model !== next.ai.primaryModel);
        if (backupOptions.length === 0) {
          if (next.ai.backupModel) {
            next.ai.backupModel = '';
            changed = true;
          }
        } else if (!backupOptions.includes(next.ai.backupModel)) {
          const candidate = backupOptions[0];
          if (candidate) {
            next.ai.backupModel = candidate;
            changed = true;
          }
        }
      } else if (next.ai.backupModel && next.ai.backupModel === next.ai.primaryModel) {
        if (backupGatewayModels.length > 0) {
          const candidate = backupGatewayModels.find((model) => model !== next.ai.primaryModel);
          next.ai.backupModel = candidate || '';
          changed = true;
        } else {
          next.ai.backupModel = '';
          changed = true;
        }
      }

      if (!changed) {
        return prev;
      }
      return next;
    });
  }, [
    aiModelMode.backup,
    aiModelMode.primary,
    aiRouteModelMode.backup,
    aiRouteModelMode.primary,
    backupGatewayModels,
    primaryGatewayModels,
    resolveProviderDefaultModel,
  ]);
  const agentMode = String(allItemMap.get('AGENT_MODE') || '').trim().toLowerCase();
  const agentDisabled = Boolean(agentMode) && FALSE_VALUES.has(agentMode);
  const agentOverrideModel = String(allItemMap.get('AGENT_LITELLM_MODEL') || '').trim();
  const backtestOverrideModel = String(allItemMap.get('BACKTEST_LITELLM_MODEL') || '').trim();
  const aiRoutingScope = useMemo<AiRoutingScope>(() => {
    if (agentDisabled) {
      return 'analysis';
    }
    const hasAgentOverrideModel = Boolean(agentOverrideModel);
    const hasAnalysisRoute = Boolean(
      aiSummary.primaryChannel.trim() && aiSummary.primaryModel.trim(),
    );
    if (hasAnalysisRoute && !hasAgentOverrideModel) {
      return 'both';
    }
    if (!hasAnalysisRoute && hasAgentOverrideModel) {
      return 'ask_stock';
    }
    return 'analysis';
  }, [agentDisabled, agentOverrideModel, aiSummary.primaryChannel, aiSummary.primaryModel]);

  const formatRouteLine = useCallback((gateway: string, model: string): string => {
    const normalizedGateway = gateway.trim();
    const normalizedModel = model.trim();
    if (!normalizedGateway || !normalizedModel) {
      return t('settings.notConfigured');
    }
    return `${providerLabel(normalizedGateway)} / ${normalizedModel}`;
  }, [t]);
  const askStockRouteSummary = useMemo(() => {
    if (agentDisabled) {
      return t('settings.aiAskStockRouteDisabled');
    }
    if (agentOverrideModel) {
      const overrideGateway = parseGatewayFromModel(agentOverrideModel) || aiSummary.primaryChannel;
      const route = overrideGateway ? formatRouteLine(overrideGateway, agentOverrideModel) : agentOverrideModel;
      return t('settings.aiAskStockRouteDedicated', { model: agentOverrideModel, route });
    }
    return t('settings.aiAskStockRouteShared', {
      route: formatRouteLine(aiSummary.primaryChannel, aiSummary.primaryModel),
    });
  }, [agentDisabled, agentOverrideModel, aiSummary.primaryChannel, aiSummary.primaryModel, formatRouteLine, t]);
  const askStockRouteMode = agentDisabled ? 'disabled' : (agentOverrideModel ? 'dedicated' : 'shared');
  const askStockEffectiveModel = agentDisabled ? '' : (agentOverrideModel || aiSummary.primaryModel);
  const askStockEffectiveGateway = agentDisabled
    ? ''
    : (agentOverrideModel
      ? (parseGatewayFromModel(agentOverrideModel) || aiSummary.primaryChannel)
      : aiSummary.primaryChannel);
  const backtestRouteMode = backtestOverrideModel ? 'dedicated' : 'shared';
  const backtestEffectiveModel = backtestOverrideModel || aiSummary.primaryModel;
  const backtestEffectiveGateway = backtestOverrideModel
    ? (parseGatewayFromModel(backtestOverrideModel) || aiSummary.primaryChannel)
    : aiSummary.primaryChannel;
  useEffect(() => {
    const defaultGateway = aiSummary.primaryChannel || '';
    const defaultModel = aiSummary.primaryModel || '';
    const stockChatGateway = parseGatewayFromModel(agentOverrideModel) || defaultGateway;
    const backtestGateway = parseGatewayFromModel(backtestOverrideModel) || defaultGateway;
    const nextTaskDraft: Record<OverrideTaskKey, TaskOverrideDraft> = {
      stock_chat: {
        inherit: !agentOverrideModel,
        gateway: stockChatGateway,
        model: agentOverrideModel || defaultModel,
      },
      backtest: {
        inherit: !backtestOverrideModel,
        gateway: backtestGateway,
        model: backtestOverrideModel || defaultModel,
      },
    };
    setTaskRoutingDraft(nextTaskDraft);

    const stockChatOptions = modelsForGateway(stockChatGateway);
    const backtestOptions = modelsForGateway(backtestGateway);
    setTaskModelMode({
      stock_chat: stockChatGateway && agentOverrideModel && !stockChatOptions.includes(agentOverrideModel)
        ? 'custom'
        : 'preset',
      backtest: backtestGateway && backtestOverrideModel && !backtestOptions.includes(backtestOverrideModel)
        ? 'custom'
        : 'preset',
    });
    setTaskRouteModelMode({
      stock_chat: inferRouteModelMode(stockChatGateway, agentOverrideModel || defaultModel, stockChatOptions),
      backtest: inferRouteModelMode(backtestGateway, backtestOverrideModel || defaultModel, backtestOptions),
    });
    setTaskRoutingError({ stock_chat: null, backtest: null });
  }, [
    agentOverrideModel,
    aiSummary.primaryChannel,
    aiSummary.primaryModel,
    backtestOverrideModel,
    modelsForGateway,
  ]);
  const hasDirectProviderCredential = useCallback((provider: string): boolean => {
    const normalized = normalizeGatewayKey(provider);
    if (!(normalized in DIRECT_PROVIDER_KEY_CANDIDATES)) {
      return false;
    }
    const keys = DIRECT_PROVIDER_KEY_CANDIDATES[normalized as QuickProviderKey] || [];
    return keys.some((key) => hasConfigValue(allItemMap.get(key) || ''));
  }, [allItemMap]);
  const backupRouteCompatibilityIssue = useMemo(() => {
    const backupGateway = routingDraft.ai.backupChannel.trim();
    const backupModel = routingDraft.ai.backupModel.trim();
    if (!backupGateway || !backupModel) return null;
    if (hasDirectProviderCredential(backupGateway)) return null;

    const channels = splitCsv(allItemMap.get('LLM_CHANNELS'));
    if (!channels.length) return null;

    const declaredModels = new Set<string>();
    channels.forEach((channel) => {
      const prefix = `LLM_${channel.toUpperCase()}`;
      const enabledRaw = String(allItemMap.get(`${prefix}_ENABLED`) || '').trim().toLowerCase();
      const enabled = !enabledRaw || !FALSE_VALUES.has(enabledRaw);
      if (!enabled) return;
      splitCsv(allItemMap.get(`${prefix}_MODELS`)).forEach((model) => declaredModels.add(model));
    });

    if (!declaredModels.size) {
      return t('settings.aiBackupCompatibilityNoDeclaredModels', { provider: providerLabel(backupGateway) });
    }

    const normalizedModel = backupModel.toLowerCase();
    const modelSuffix = normalizedModel.includes('/') ? normalizedModel.split('/').slice(1).join('/') : normalizedModel;
    const declaredMatch = [...declaredModels].some((declared) => {
      const normalizedDeclared = declared.toLowerCase();
      if (normalizedDeclared === normalizedModel) return true;
      if (normalizedDeclared === modelSuffix) return true;
      if (normalizedModel === normalizedDeclared.split('/').slice(1).join('/')) return true;
      return normalizedModel.endsWith(`/${normalizedDeclared}`);
    });
    if (declaredMatch) return null;

    return t('settings.aiBackupCompatibilityNotDeclared', {
      model: backupModel,
      provider: providerLabel(backupGateway),
    });
  }, [allItemMap, hasDirectProviderCredential, routingDraft.ai.backupChannel, routingDraft.ai.backupModel, t]);
  const taskGatewayOptions = useMemo(
    () => uniqueValues([
      ...aiGatewaySelectorOptions,
      taskRoutingDraft.stock_chat.gateway,
      taskRoutingDraft.backtest.gateway,
    ]),
    [aiGatewaySelectorOptions, taskRoutingDraft.backtest.gateway, taskRoutingDraft.stock_chat.gateway],
  );
  const taskModelOptions = useMemo(
    () => ({
      stock_chat: modelsForGateway(taskRoutingDraft.stock_chat.gateway),
      backtest: modelsForGateway(taskRoutingDraft.backtest.gateway),
    }),
    [modelsForGateway, taskRoutingDraft.backtest.gateway, taskRoutingDraft.stock_chat.gateway],
  );
  const taskModelCompatible = useMemo(
    () => ({
      stock_chat: isGatewayModelCompatible(
        taskRoutingDraft.stock_chat.gateway,
        taskRoutingDraft.stock_chat.model,
        taskModelOptions.stock_chat,
      ),
      backtest: isGatewayModelCompatible(
        taskRoutingDraft.backtest.gateway,
        taskRoutingDraft.backtest.model,
        taskModelOptions.backtest,
      ),
    }),
    [
      taskModelOptions.backtest,
      taskModelOptions.stock_chat,
      taskRoutingDraft.backtest.gateway,
      taskRoutingDraft.backtest.model,
      taskRoutingDraft.stock_chat.gateway,
      taskRoutingDraft.stock_chat.model,
    ],
  );
  useEffect(() => {
    setTaskRoutingDraft((prev) => {
      const next: Record<OverrideTaskKey, TaskOverrideDraft> = {
        stock_chat: { ...prev.stock_chat },
        backtest: { ...prev.backtest },
      };
      let changed = false;
      (['stock_chat', 'backtest'] as OverrideTaskKey[]).forEach((task) => {
        const draft = next[task];
        if (draft.inherit) return;
        if (!draft.gateway && draft.model) {
          draft.model = '';
          changed = true;
          return;
        }
        if (!draft.gateway) return;
        if (taskRouteModelMode[task] === 'provider_default') {
          const defaultModel = resolveProviderDefaultModel(draft.gateway);
          if (draft.model !== defaultModel) {
            draft.model = defaultModel;
            changed = true;
          }
          return;
        }
        if (taskModelMode[task] !== 'preset') return;
        const options = taskModelOptions[task];
        if (!options.length) {
          if (draft.model) {
            draft.model = '';
            changed = true;
          }
          return;
        }
        if (!options.includes(draft.model)) {
          draft.model = options[0] || '';
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [resolveProviderDefaultModel, taskModelMode, taskModelOptions, taskRouteModelMode]);
  const setTaskRouteInherit = useCallback((task: OverrideTaskKey, inherit: boolean) => {
    setTaskRoutingError((prev) => ({ ...prev, [task]: null }));
    setTaskRoutingDraft((prev) => {
      const current = prev[task];
      if (inherit) {
        return {
          ...prev,
          [task]: {
            inherit: true,
            gateway: aiSummary.primaryChannel || current.gateway,
            model: aiSummary.primaryModel || current.model,
          },
        };
      }
      const nextGateway = current.gateway || aiSummary.primaryChannel;
      const nextModel = current.model || aiSummary.primaryModel;
      return {
        ...prev,
        [task]: {
          inherit: false,
          gateway: nextGateway,
          model: nextModel,
        },
      };
    });
  }, [aiSummary.primaryChannel, aiSummary.primaryModel]);
  const setTaskRouteGateway = useCallback((task: OverrideTaskKey, gateway: string) => {
    setTaskRoutingError((prev) => ({ ...prev, [task]: null }));
    setTaskModelMode((prev) => ({ ...prev, [task]: 'preset' }));
    setTaskRoutingDraft((prev) => ({
      ...prev,
      [task]: {
        ...prev[task],
        inherit: false,
        gateway,
        model: gateway ? prev[task].model : '',
      },
    }));
  }, []);
  const setTaskRouteModel = useCallback((task: OverrideTaskKey, model: string) => {
    setTaskRoutingError((prev) => ({ ...prev, [task]: null }));
    setTaskRoutingDraft((prev) => ({
      ...prev,
      [task]: {
        ...prev[task],
        inherit: false,
        model,
      },
    }));
  }, []);
  const saveTaskRoute = useCallback(async (task: OverrideTaskKey) => {
    const draft = taskRoutingDraft[task];
    if (draft.inherit) {
      const key = task === 'stock_chat' ? 'AGENT_LITELLM_MODEL' : 'BACKTEST_LITELLM_MODEL';
      await saveExternalItems([{ key, value: '' }], t('settings.aiTaskRouteSavedShared', {
        task: t(`settings.aiTaskName.${task}`),
      }));
      setTaskRoutingError((prev) => ({ ...prev, [task]: null }));
      return;
    }
    const gateway = draft.gateway.trim();
    const model = draft.model.trim();
    if (!gateway || !model) {
      setTaskRoutingError((prev) => ({
        ...prev,
        [task]: t('settings.aiTaskRouteValidationRequired', { task: t(`settings.aiTaskName.${task}`) }),
      }));
      return;
    }
    const key = task === 'stock_chat' ? 'AGENT_LITELLM_MODEL' : 'BACKTEST_LITELLM_MODEL';
    await saveExternalItems([{ key, value: model }], t('settings.aiTaskRouteSaved', {
      task: t(`settings.aiTaskName.${task}`),
      route: formatRouteLine(gateway, model),
    }));
    setTaskRoutingError((prev) => ({ ...prev, [task]: null }));
  }, [formatRouteLine, saveExternalItems, t, taskRoutingDraft]);

  const saveAiRouting = useCallback(async () => {
    setAiRoutingError(null);
    const primaryGateway = routingDraft.ai.primaryChannel.trim();
    const backupGateway = routingDraft.ai.backupChannel.trim();
    const primaryModel = primaryGateway ? routingDraft.ai.primaryModel.trim() : '';
    const backupModel = backupGateway ? routingDraft.ai.backupModel.trim() : '';

    if (!primaryGateway || !primaryModel) {
      setAiRoutingError(t('settings.aiRouteValidationPrimaryRequired'));
      return;
    }
    if ((backupGateway && !backupModel) || (!backupGateway && backupModel)) {
      setAiRoutingError(t('settings.aiRouteValidationBackupIncomplete'));
      return;
    }
    if (backupRouteCompatibilityIssue) {
      setAiRoutingError(backupRouteCompatibilityIssue);
      return;
    }

    // Keep channel-editor-owned legacy route list stable to avoid introducing
    // incomplete channel definitions from gateway-only selection.
    const channelRoute = effectiveRoute(splitCsv(allItemMap.get('LLM_CHANNELS')));
    const fallbackRoute = backupModel ? [backupModel] : [];
    const confirmation = t('settings.aiRouteSavedDetail', {
      primary: formatRouteLine(primaryGateway, primaryModel),
      backup: formatRouteLine(backupGateway, backupModel),
      scope: t(`settings.aiRouteScope.${aiRoutingScope}`),
    });
    try {
      await saveExternalItems([
        { key: aiRoutingKeys.primaryGateway, value: primaryGateway },
        { key: aiRoutingKeys.primaryModel, value: primaryModel },
        { key: aiRoutingKeys.backupGateway, value: backupGateway },
        { key: aiRoutingKeys.backupModel, value: backupModel },
        { key: 'LLM_CHANNELS', value: channelRoute.join(',') },
        { key: 'LITELLM_MODEL', value: primaryModel },
        { key: 'LITELLM_FALLBACK_MODELS', value: fallbackRoute.join(',') },
      ], confirmation);
      setAiRoutingError(null);
    } catch (error: unknown) {
      if (error instanceof SystemConfigValidationError && error.issues.length > 0) {
        setAiRoutingError(error.issues[0]?.message || t('settings.aiRouteSaveFailed'));
        return;
      }
      const parsed = getParsedApiError(error);
      setAiRoutingError(parsed.message || t('settings.aiRouteSaveFailed'));
    }
  }, [aiRoutingScope, aiRoutingKeys.backupGateway, aiRoutingKeys.backupModel, aiRoutingKeys.primaryGateway, aiRoutingKeys.primaryModel, allItemMap, backupRouteCompatibilityIssue, effectiveRoute, formatRouteLine, routingDraft.ai.backupChannel, routingDraft.ai.backupModel, routingDraft.ai.primaryChannel, routingDraft.ai.primaryModel, saveExternalItems, t]);

  const saveDataRouting = useCallback(async (
    key: string,
    values: Array<string | undefined | null>,
  ) => {
    await saveExternalItems([{ key, value: effectiveRoute(values).join(',') }], t('settings.routeSaved'));
  }, [effectiveRoute, saveExternalItems, t]);
  const saveRuntimeSummaryVisibility = useCallback(async () => {
    await saveExternalItems([
      { key: runtimeSummaryVisibilityKey, value: showRuntimeExecutionSummary ? 'true' : 'false' },
    ], t('settings.routeSaved'));
  }, [runtimeSummaryVisibilityKey, saveExternalItems, showRuntimeExecutionSummary, t]);
  const directProviderKeyValues = useMemo(() => ({
    aihubmix: allItemMap.get('AIHUBMIX_KEY') || '',
    gemini: allItemMap.get('GEMINI_API_KEY') || '',
    openai: allItemMap.get('OPENAI_API_KEY') || '',
    anthropic: allItemMap.get('ANTHROPIC_API_KEY') || '',
    deepseek: allItemMap.get('DEEPSEEK_API_KEY') || '',
    zhipu: allItemMap.get('ZHIPU_API_KEY') || '',
  }), [allItemMap]);
  const [directProviderDraft, setDirectProviderDraft] = useState(directProviderKeyValues);
  const [quickProviderTestState, setQuickProviderTestState] = useState<Record<QuickProviderKey, QuickProviderTestState>>({
    aihubmix: { status: 'idle', text: '' },
    gemini: { status: 'idle', text: '' },
    openai: { status: 'idle', text: '' },
    anthropic: { status: 'idle', text: '' },
    deepseek: { status: 'idle', text: '' },
    zhipu: { status: 'idle', text: '' },
  });
  useEffect(() => {
    setDirectProviderDraft(directProviderKeyValues);
  }, [directProviderKeyValues]);
  const normalizeProviderCredential = useCallback((value: string): string => {
    const normalized = String(value || '').trim();
    if (!normalized || /^\*+$/.test(normalized) || normalized === '已配置' || normalized.includes('...')) {
      return '';
    }
    return normalized;
  }, []);
  const resolveQuickProviderCredential = useCallback((provider: QuickProviderKey): string => {
    const draftValue = normalizeProviderCredential(directProviderDraft[provider] || '');
    if (draftValue) return draftValue;
    const candidateKeys = DIRECT_PROVIDER_KEY_CANDIDATES[provider] || [];
    for (const key of candidateKeys) {
      const value = normalizeProviderCredential(allItemMap.get(key) || '');
      if (!value) continue;
      return splitCsv(value)[0] || value;
    }
    return '';
  }, [allItemMap, directProviderDraft, normalizeProviderCredential]);
  const resolveQuickProviderAdvancedTemplate = useCallback((provider: QuickProviderKey): {
    channelName: string;
    protocol: string;
    baseUrl: string;
    apiKey: string;
    model: string;
  } | null => {
    const resolveProviderFromChannel = (channelName: string): QuickProviderKey | '' => {
      const normalizedName = normalizeGatewayKey(channelName);
      if (!normalizedName) return '';
      if (PROVIDER_LIBRARY_ITEMS.some((item) => item.key === normalizedName)) {
        return normalizedName as QuickProviderKey;
      }
      const prefix = `LLM_${channelName.toUpperCase()}`;
      const protocol = normalizeGatewayKey(allItemMap.get(`${prefix}_PROTOCOL`) || '');
      if (protocol === 'gemini' || protocol === 'anthropic' || protocol === 'deepseek') {
        return protocol as QuickProviderKey;
      }
      const baseUrl = String(allItemMap.get(`${prefix}_BASE_URL`) || '').toLowerCase();
      if (baseUrl.includes('aihubmix')) return 'aihubmix';
      if (baseUrl.includes('open.bigmodel.cn') || baseUrl.includes('bigmodel')) return 'zhipu';
      if (baseUrl.includes('api.openai.com')) return 'openai';
      if (baseUrl.includes('api.deepseek.com')) return 'deepseek';
      if (baseUrl.includes('anthropic')) return 'anthropic';
      if (baseUrl.includes('generativelanguage') || baseUrl.includes('gemini')) return 'gemini';
      const models = splitCsv(allItemMap.get(`${prefix}_MODELS`));
      for (const model of models) {
        const modelGateway = normalizeGatewayKey(parseGatewayFromModel(model));
        if (!modelGateway) continue;
        if (PROVIDER_LIBRARY_ITEMS.some((item) => item.key === modelGateway)) {
          return modelGateway as QuickProviderKey;
        }
      }
      return '';
    };
    const channels = splitCsv(allItemMap.get('LLM_CHANNELS'));
    for (const channelName of channels) {
      if (resolveProviderFromChannel(channelName) !== provider) continue;
      const prefix = `LLM_${channelName.toUpperCase()}`;
      const rawModels = splitCsv(allItemMap.get(`${prefix}_MODELS`));
      const firstModel = rawModels[0] || '';
      return {
        channelName,
        protocol: String(allItemMap.get(`${prefix}_PROTOCOL`) || '').trim(),
        baseUrl: String(allItemMap.get(`${prefix}_BASE_URL`) || '').trim(),
        apiKey: String(allItemMap.get(`${prefix}_API_KEYS`) || allItemMap.get(`${prefix}_API_KEY`) || '').trim(),
        model: firstModel,
      };
    }
    return null;
  }, [allItemMap]);
  const resolveQuickProviderTestModel = useCallback((provider: QuickProviderKey, preferredModel = ''): string => {
    const normalizedPreferred = String(preferredModel || '').trim();
    if (normalizedPreferred) {
      return normalizedPreferred;
    }
    const defaultModel = QUICK_PROVIDER_DEFAULT_TEST_MODEL[provider] || '';
    if (defaultModel) {
      return defaultModel;
    }
    const options = modelsForGateway(provider);
    if (options.length > 0) {
      return options[0] || '';
    }
    const presets = KNOWN_GATEWAY_MODEL_PRESETS[provider] || [];
    return presets[0] || '';
  }, [modelsForGateway]);
  const normalizeQuickProviderTestModel = useCallback((provider: QuickProviderKey, model: string): string => {
    const normalizedModel = String(model || '').trim();
    if (!normalizedModel) return '';
    if (provider === 'aihubmix') return normalizedModel;
    if (!normalizedModel.includes('/')) return normalizedModel;
    return normalizedModel.split('/').slice(1).join('/') || normalizedModel;
  }, []);
  const testQuickProviderConnection = useCallback(async (provider: QuickProviderKey) => {
    const advancedTemplate = resolveQuickProviderAdvancedTemplate(provider);
    const apiKey = resolveQuickProviderCredential(provider)
      || normalizeProviderCredential(advancedTemplate?.apiKey || '');
    if (!apiKey) {
      setQuickProviderTestState((prev) => ({
        ...prev,
        [provider]: {
          status: 'error',
          text: t('settings.aiProviderTestMissingApiKey', { provider: providerLabel(provider) }),
        },
      }));
      return;
    }
    const suggestedModel = resolveQuickProviderTestModel(provider, advancedTemplate?.model || '');
    if (!suggestedModel) {
      setQuickProviderTestState((prev) => ({
        ...prev,
        [provider]: {
          status: 'error',
          text: t('settings.aiProviderTestMissingModel', { provider: providerLabel(provider) }),
        },
      }));
      return;
    }
    const testModel = normalizeQuickProviderTestModel(provider, suggestedModel);
    setQuickProviderTestState((prev) => ({
      ...prev,
      [provider]: {
        status: 'loading',
        text: t('settings.aiProviderTestLoading'),
      },
    }));
    try {
      const result = await systemConfigApi.testLLMChannel({
        name: advancedTemplate?.channelName || `quick_${provider}`,
        protocol: advancedTemplate?.protocol || QUICK_PROVIDER_PROTOCOL[provider],
        baseUrl: advancedTemplate?.baseUrl || QUICK_PROVIDER_BASE_URL[provider],
        apiKey,
        models: [testModel],
        enabled: true,
        timeoutSeconds: 15,
      }, { adminUnlockToken });
      const resolvedModel = String(result.resolvedModel || testModel).trim();
      if (result.success) {
        const latencyText = typeof result.latencyMs === 'number' && result.latencyMs > 0
          ? t('settings.aiProviderTestLatency', { latency: result.latencyMs })
          : '';
        const suffix = latencyText ? ` · ${latencyText}` : '';
        setQuickProviderTestState((prev) => ({
          ...prev,
          [provider]: {
            status: 'success',
            text: t('settings.aiProviderTestSuccess', { model: resolvedModel }) + suffix,
          },
        }));
        return;
      }
      setQuickProviderTestState((prev) => ({
        ...prev,
        [provider]: {
          status: 'error',
          text: [
            result.error || result.message || t('settings.aiProviderTestFailedGeneric'),
            provider === 'zhipu' && !advancedTemplate
              ? t('settings.aiProviderTestAdvancedGuidance', { provider: providerLabel(provider) })
              : '',
          ].filter(Boolean).join(' '),
        },
      }));
    } catch (error: unknown) {
      const parsed = getParsedApiError(error);
      setQuickProviderTestState((prev) => ({
        ...prev,
        [provider]: {
          status: 'error',
          text: [
            parsed.message || t('settings.aiProviderTestFailedGeneric'),
            provider === 'zhipu' && !advancedTemplate
              ? t('settings.aiProviderTestAdvancedGuidance', { provider: providerLabel(provider) })
              : '',
          ].filter(Boolean).join(' '),
        },
      }));
    }
  }, [
    adminUnlockToken,
    normalizeQuickProviderTestModel,
    normalizeProviderCredential,
    resolveQuickProviderAdvancedTemplate,
    resolveQuickProviderCredential,
    resolveQuickProviderTestModel,
    t,
  ]);
  const saveDirectProviderKeys = useCallback(async () => {
    await saveExternalItems([
      { key: 'AIHUBMIX_KEY', value: directProviderDraft.aihubmix.trim() },
      { key: 'GEMINI_API_KEY', value: directProviderDraft.gemini.trim() },
      { key: 'OPENAI_API_KEY', value: directProviderDraft.openai.trim() },
      { key: 'ANTHROPIC_API_KEY', value: directProviderDraft.anthropic.trim() },
      { key: 'DEEPSEEK_API_KEY', value: directProviderDraft.deepseek.trim() },
      { key: 'ZHIPU_API_KEY', value: directProviderDraft.zhipu.trim() },
    ], t('settings.aiDirectProviderSaved'));
  }, [directProviderDraft.aihubmix, directProviderDraft.anthropic, directProviderDraft.deepseek, directProviderDraft.gemini, directProviderDraft.openai, directProviderDraft.zhipu, saveExternalItems, t]);
  const jumpToAiChannelConfig = useCallback(() => {
    setActiveDomain('ai_models');
    setActiveCategory('ai_model');
    setAdvancedFocusChannelName('');
    setAdvancedNavigationContext(null);
    setAdvancedCreatePreset(null);
    setAiAdvancedDrawerOpen(true);
  }, [setActiveCategory]);
  const openAiRoutingDrawer = useCallback(() => {
    setActiveDomain('ai_models');
    setAiRoutingDrawerOpen(true);
  }, []);
  const openQuickProviderDrawer = useCallback((provider: QuickProviderKey) => {
    setActiveDomain('ai_models');
    setQuickProviderDrawerProvider(provider);
  }, []);
  const resolveAdvancedChannelProvider = useCallback((channelName: string): QuickProviderKey | '' => {
    const normalizedName = normalizeGatewayKey(channelName);
    if (!normalizedName) return '';
    if (PROVIDER_LIBRARY_ITEMS.some((item) => item.key === normalizedName)) {
      return normalizedName as QuickProviderKey;
    }

    const prefix = `LLM_${channelName.toUpperCase()}`;
    const protocol = normalizeGatewayKey(allItemMap.get(`${prefix}_PROTOCOL`) || '');
    if (protocol === 'gemini' || protocol === 'anthropic' || protocol === 'deepseek') {
      return protocol as QuickProviderKey;
    }

    const baseUrl = String(allItemMap.get(`${prefix}_BASE_URL`) || '').toLowerCase();
    if (baseUrl.includes('aihubmix')) return 'aihubmix';
    if (baseUrl.includes('open.bigmodel.cn') || baseUrl.includes('bigmodel')) return 'zhipu';
    if (baseUrl.includes('api.openai.com')) return 'openai';
    if (baseUrl.includes('api.deepseek.com')) return 'deepseek';
    if (baseUrl.includes('anthropic')) return 'anthropic';
    if (baseUrl.includes('generativelanguage') || baseUrl.includes('gemini')) return 'gemini';

    const models = splitCsv(allItemMap.get(`${prefix}_MODELS`));
    for (const model of models) {
      const modelGateway = normalizeGatewayKey(parseGatewayFromModel(model));
      if (!modelGateway) continue;
      if (PROVIDER_LIBRARY_ITEMS.some((item) => item.key === modelGateway)) {
        return modelGateway as QuickProviderKey;
      }
    }

    return '';
  }, [allItemMap]);
  const advancedChannelsByProvider = useMemo(() => {
    const result: Record<QuickProviderKey, string[]> = {
      aihubmix: [],
      gemini: [],
      openai: [],
      anthropic: [],
      deepseek: [],
      zhipu: [],
    };
    splitCsv(allItemMap.get('LLM_CHANNELS')).forEach((channelName) => {
      const provider = resolveAdvancedChannelProvider(channelName);
      if (!provider) return;
      if (!result[provider].includes(channelName)) {
        result[provider].push(channelName);
      }
    });
    return result;
  }, [allItemMap, resolveAdvancedChannelProvider]);
  const jumpToProviderAdvancedConfig = useCallback((provider: QuickProviderKey) => {
    const channels = advancedChannelsByProvider[provider] || [];
    const firstChannel = channels[0] || '';
    setActiveDomain('ai_models');
    setActiveCategory('ai_model');
    setAdvancedFocusChannelName(firstChannel);
    setAdvancedNavigationContext({
      provider,
      channelName: firstChannel || undefined,
      hasChannel: Boolean(firstChannel),
    });
    setAiAdvancedDrawerOpen(true);
  }, [advancedChannelsByProvider, setActiveCategory]);
  const handleCreateAdvancedProviderChannel = useCallback((provider: QuickProviderKey) => {
    setAdvancedCreatePreset(provider);
    setAdvancedFocusChannelName(provider);
    setAdvancedNavigationContext({
      provider,
      channelName: provider,
      hasChannel: true,
    });
    setAiAdvancedDrawerOpen(true);
  }, []);
  const runResetRuntimeCaches = useCallback(async () => {
    setIsRunningAdminAction(true);
    setAdminActionMessage(null);
    try {
      const payload = await systemConfigApi.resetRuntimeCaches();
      setAdminActionTone('success');
      setAdminActionMessage(payload.message || t('settings.adminActionResetRuntimeCachesSuccess'));
      setAdminActionDialog(null);
    } catch (error: unknown) {
      const parsed = getParsedApiError(error);
      setAdminActionTone('error');
      setAdminActionMessage(parsed.message || t('settings.adminActionResetRuntimeCachesFailed'));
    } finally {
      setIsRunningAdminAction(false);
    }
  }, [t]);
  const runFactoryResetSystem = useCallback(async () => {
    setIsRunningAdminAction(true);
    setAdminActionMessage(null);
    try {
      const payload = await systemConfigApi.factoryResetSystem({
        confirmationPhrase: factoryResetConfirmation,
      });
      setAdminActionTone('success');
      setAdminActionMessage(payload.message || t('settings.adminActionFactoryResetSuccess'));
      setFactoryResetConfirmation('');
      setAdminActionDialog(null);
    } catch (error: unknown) {
      const parsed = getParsedApiError(error);
      setAdminActionTone('error');
      setAdminActionMessage(parsed.message || t('settings.adminActionFactoryResetFailed'));
    } finally {
      setIsRunningAdminAction(false);
    }
  }, [factoryResetConfirmation, t]);
  const providerReadinessByGateway = useMemo(
    () => new Map(aiGatewayReadiness.map((provider) => [provider.gateway, provider])),
    [aiGatewayReadiness],
  );
  const quickProviderDrawerItem = useMemo(
    () => PROVIDER_LIBRARY_ITEMS.find((provider) => provider.key === quickProviderDrawerProvider) || null,
    [quickProviderDrawerProvider],
  );

  const primarySummaryModel = aiSummary.primaryChannel ? aiSummary.primaryModel : '';
  const backupSummaryModel = aiSummary.backupChannel ? aiSummary.backupModel : '';
  const primaryPresetOptions = primaryGatewayModels.slice(0, 12);
  const backupPresetOptions = backupGatewayModels
    .filter((model) => model !== routingDraft.ai.primaryModel)
    .slice(0, 12);
  const canUsePrimaryCustomModel = Boolean(routingDraft.ai.primaryChannel) && supportsCustomModelId(routingDraft.ai.primaryChannel);
  const canUseBackupCustomModel = Boolean(routingDraft.ai.backupChannel) && supportsCustomModelId(routingDraft.ai.backupChannel);
  const aiModelModeHint = useCallback((gateway: string, mode: ModelInputMode): string => {
    if (!gateway) return t('settings.aiModelModeRequiresGateway');
    if (mode === 'preset') {
      return gateway === 'aihubmix'
        ? t('settings.aiModelModePresetHintAihubmix')
        : gateway === 'zhipu'
          ? t('settings.aiModelModePresetHintZhipu')
        : t('settings.aiModelModePresetHint');
    }
    return gateway === 'aihubmix'
      ? t('settings.aiModelModeCustomHintAihubmix')
      : gateway === 'zhipu'
        ? t('settings.aiModelModeCustomHintZhipu')
      : t('settings.aiModelModeCustomHint', { gateway: providerLabel(gateway) || t('settings.notConfigured') });
  }, [t]);
  const aiCustomModelPlaceholder = useCallback((gateway: string): string => (
    gateway === 'aihubmix'
      ? t('settings.aiCustomModelPlaceholderAihubmix')
      : t('settings.aiCustomModelPlaceholder')
  ), [t]);
  const aiCustomModelHint = useCallback((gateway: string): string => (
    gateway === 'aihubmix'
      ? t('settings.aiCustomModelHintAihubmix')
      : t('settings.aiCustomModelHint')
  ), [t]);
  const aiProviderDefaultHint = useCallback((gateway: string, model: string): string => {
    if (!gateway) return t('settings.aiModelModeRequiresGateway');
    if (!model) return t('settings.aiRouteProviderDefaultUnavailable');
    return t('settings.aiRouteProviderDefaultHint', { model });
  }, [t]);
  const configuredProvidersText = aiSummary.configuredProviders.length
    ? aiSummary.configuredProviders.map(([name, count]) => `${providerLabel(name)} (${count})`).join(' · ')
    : t('settings.notConfigured');
  const aiRouteRows = useMemo(() => ([
    {
      key: 'analysis',
      title: t('settings.aiTaskName.analysis'),
      routeMode: t(`settings.aiRouteModelMode.${aiRouteModelMode.primary}`),
      route: formatRouteLine(aiSummary.primaryChannel, primarySummaryModel),
      backup: aiSummary.backupChannel
        ? formatRouteLine(aiSummary.backupChannel, backupSummaryModel)
        : '',
      summary: `${t('settings.aiRouteStatusLabel')}: ${t(`settings.aiRouteStatus.${aiSummary.routeStatus}`)}`,
      actionLabel: t('settings.aiTaskEditAction'),
      highlighted: true,
    },
    {
      key: 'stock_chat',
      title: t('settings.aiTaskName.stock_chat'),
      routeMode: t(`settings.aiAskStockRouteMode.${askStockRouteMode}`),
      route: formatRouteLine(askStockEffectiveGateway, askStockEffectiveModel),
      backup: '',
      summary: askStockRouteSummary,
      actionLabel: t('settings.aiTaskEditAction'),
      highlighted: false,
    },
    {
      key: 'backtest',
      title: t('settings.aiTaskName.backtest'),
      routeMode: t(`settings.aiTaskRouteMode.${backtestRouteMode}`),
      route: formatRouteLine(backtestEffectiveGateway, backtestEffectiveModel),
      backup: '',
      summary: backtestOverrideModel
        ? t('settings.aiBacktestRouteDedicatedSummary', {
          model: backtestOverrideModel,
          route: formatRouteLine(backtestEffectiveGateway, backtestOverrideModel),
        })
        : t('settings.aiBacktestRouteSharedSummary', {
          route: formatRouteLine(aiSummary.primaryChannel, aiSummary.primaryModel),
        }),
      actionLabel: t('settings.aiTaskEditAction'),
      highlighted: false,
    },
  ]), [
    aiRouteModelMode.primary,
    aiSummary.backupChannel,
    aiSummary.primaryChannel,
    aiSummary.primaryModel,
    aiSummary.routeStatus,
    askStockEffectiveGateway,
    askStockEffectiveModel,
    askStockRouteMode,
    askStockRouteSummary,
    backupSummaryModel,
    backtestEffectiveGateway,
    backtestEffectiveModel,
    backtestOverrideModel,
    backtestRouteMode,
    formatRouteLine,
    primarySummaryModel,
    t,
  ]);
  const quickProviderCards = useMemo(() => (
    PROVIDER_LIBRARY_ITEMS.map((provider) => {
      const providerState = providerReadinessByGateway.get(provider.key);
      const quickApiConfigured = hasConfigValue(resolveQuickProviderCredential(provider.key));
      const quickTestState = quickProviderTestState[provider.key];
      return {
        key: provider.key,
        label: provider.label,
        isReady: quickApiConfigured || Boolean(providerState?.credentialReady),
        presetCount: providerState?.presetCount || (KNOWN_GATEWAY_MODEL_PRESETS[provider.key] || []).length,
        quickApiConfigured,
        advancedChannelCount: (advancedChannelsByProvider[provider.key] || []).length,
        suggestedTestModel: resolveQuickProviderTestModel(provider.key),
        quickTestStatus: quickTestState.status,
        quickTestText: quickTestState.text,
      };
    })
  ), [
    advancedChannelsByProvider,
    providerReadinessByGateway,
    quickProviderTestState,
    resolveQuickProviderCredential,
    resolveQuickProviderTestModel,
  ]);
  const activeDomainTitle = panelNavItems.find((item) => item.domain === activePanel)?.title
    || panelNavItems.find((item) => item.domain === activeDomain)?.title
    || activeDomain;
  const {
    heroItems,
    systemHealthSummaryCards,
    systemStatusCards,
    developerDetailGroups,
    duckdbConfigEnabledState,
  } = useMemo(() => buildSystemControlPlaneState({
    allItems,
    allItemMap,
    aiSummary,
    activeDomainTitle,
    dataSourceLibrary,
    dataSummary,
    dirtyCount,
    workspaceDomainCount: DOMAIN_ORDER.length,
    notificationSummary,
    providerLabel,
    prettySourceLabel,
    formatRouteLine,
    t,
  }), [
    activeDomainTitle,
    aiSummary,
    allItemMap,
    allItems,
    dataSourceLibrary,
    dataSummary,
    dirtyCount,
    formatRouteLine,
    notificationSummary,
    t,
  ]);

  const handleSelectPanel = useCallback((panel: SettingsWorkspacePanel) => {
    setActivePanel(panel);
    if (panel === 'overview') {
      return;
    }
    setActiveDomain(panel);
    const firstCategory = categories.find(
      (category) => (categoryDomainMap.get(category.category) || 'advanced') === panel,
    )?.category;
    if (firstCategory) {
      setActiveCategory(firstCategory);
    }
  }, [categories, categoryDomainMap, setActiveCategory]);

  const handleSelectCategory = useCallback((category: string) => {
    setActiveCategory(category);
    const nextDomain = categoryDomainMap.get(category) || 'advanced';
    setActiveDomain(nextDomain);
    setActivePanel(nextDomain);
  }, [categoryDomainMap, setActiveCategory]);
  const dataRoutingGroups = [
    {
      key: 'market' as const,
      role: t('settings.marketDataRole'),
      values: effectiveRoute([routingDraft.market.primary, routingDraft.market.backup, routingDraft.market.fallback]),
      available: dataSourceRouteOptions.market,
      route: routingDraft.market,
      allowFallback: true,
      onSave: () => saveDataRouting(dataPriorityKeys.market, [
        routingDraft.market.primary,
        routingDraft.market.backup,
        routingDraft.market.fallback,
      ]),
    },
    {
      key: 'fundamentals' as const,
      role: t('settings.fundamentalDataRole'),
      values: effectiveRoute([routingDraft.fundamentals.primary, routingDraft.fundamentals.backup, routingDraft.fundamentals.fallback]),
      available: dataSourceRouteOptions.fundamentals,
      route: routingDraft.fundamentals,
      allowFallback: true,
      onSave: () => saveDataRouting(dataPriorityKeys.fundamentals, [
        routingDraft.fundamentals.primary,
        routingDraft.fundamentals.backup,
        routingDraft.fundamentals.fallback,
      ]),
    },
    {
      key: 'news' as const,
      role: t('settings.newsDataRole'),
      values: effectiveRoute([routingDraft.news.primary, routingDraft.news.backup]),
      available: dataSourceRouteOptions.news,
      route: routingDraft.news,
      allowFallback: false,
      onSave: () => saveDataRouting(dataPriorityKeys.news, [
        routingDraft.news.primary,
        routingDraft.news.backup,
      ]),
    },
    {
      key: 'sentiment' as const,
      role: t('settings.sentimentDataRole'),
      values: effectiveRoute([routingDraft.sentiment.primary, routingDraft.sentiment.backup]),
      available: dataSourceRouteOptions.sentiment,
      route: routingDraft.sentiment,
      allowFallback: false,
      onSave: () => saveDataRouting(dataPriorityKeys.sentiment, [
        routingDraft.sentiment.primary,
        routingDraft.sentiment.backup,
      ]),
    },
  ];
  const activeDataRoutingGroup = dataRoutingGroups.find((group) => group.key === dataRoutingDrawerKey) || null;
  return (
    <div
      data-testid="settings-bento-page"
      data-bento-surface="true"
      className="flex-1 flex w-full h-full min-h-0 overflow-hidden"
    >
      <div
        data-testid="settings-workspace"
        className={isSystemSettingsSurface
          ? 'flex h-full min-h-0 w-full max-w-none flex-1 flex-col gap-5 px-4 md:flex-row md:px-6 xl:px-8'
          : 'flex h-full min-h-0 w-full max-w-none flex-1 flex-col gap-8 px-6 md:flex-row md:px-8 xl:px-12'}
      >
        <aside className={isSystemSettingsSurface
          ? 'order-2 w-full shrink-0 self-start md:sticky md:top-8 md:order-1 md:w-60 xl:w-64'
          : 'w-full shrink-0 self-start md:sticky md:top-8 md:w-64'}
        >
          <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-1">
              <p className="mb-4 px-3 text-xs font-bold uppercase tracking-[0.22em] text-white/40">{t('settings.title')}</p>
              {panelNavItems.map((panel) => {
                const nav = panelNavItems.find((item) => item.domain === panel.domain);
                if (!nav) {
                  return null;
                }
                const isActive = activePanel === panel.domain;
                return (
                  <button
                    key={panel.domain}
                    type="button"
                    className={isActive
                      ? `${CONSOLE_NAV_BUTTON_CLASS} border border-white/10 bg-white/[0.08] font-medium text-white`
                      : `${CONSOLE_NAV_BUTTON_CLASS} border border-transparent text-white/60 hover:border-white/8 hover:bg-white/[0.02] hover:text-white`}
                    onClick={() => handleSelectPanel(panel.domain)}
                  >
                    <span className="block">{nav.title}</span>
                  </button>
                );
              })}
            </div>

            <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-3">
              <SettingsCategoryNav
                categories={domainCategories}
                itemsByCategory={itemsByCategory}
                activeCategory={activeCategory}
                onSelect={handleSelectCategory}
                disabled={adminLocked}
              />
            </div>
          </div>
        </aside>

        <section className={isSystemSettingsSurface
          ? 'order-1 flex min-h-0 min-w-0 flex-1 flex-col pr-0 md:order-2'
          : 'flex min-h-0 min-w-0 flex-1 flex-col pl-2 pr-0 md:pr-8'}
        >
          <div
            data-testid="settings-main-panel"
            className="min-w-0 flex-1 overflow-y-auto no-scrollbar pb-12 pr-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          >
            <div
              data-testid="settings-main-content"
              className={isSystemSettingsSurface ? 'w-full max-w-none space-y-5' : 'mx-auto w-full max-w-5xl space-y-4'}
            >
              <div className="mb-4 flex items-center justify-end gap-4">
                <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
                  <button
                    type="button"
                    className={CONTROL_GHOST_BUTTON_CLASS}
                    data-testid="settings-bento-drawer-trigger"
                    onClick={() => setIsBriefDrawerOpen(true)}
                  >
                    <PanelRightOpen className="h-4 w-4" />
                    <span>{language === 'en' ? 'Open brief' : '查看摘要'}</span>
                  </button>
                  <Button
                    type="button"
                    variant="settings-secondary"
                    className={CONTROL_GHOST_BUTTON_CLASS}
                    onClick={resetDraft}
                    disabled={isLoading || isSaving || adminLocked}
                  >
                    {t('settings.reset')}
                  </Button>
                  <Button
                    type="button"
                    variant="settings-primary"
                    className="rounded-lg px-3 py-1.5 text-xs"
                    onClick={handleSave}
                    disabled={adminSaveDisabled}
                    isLoading={isSaving}
                    loadingText={t('settings.saving')}
                  >
                    {isSaving ? t('settings.saving') : `${t('settings.save')}${dirtyCount ? ` (${dirtyCount})` : ''}`}
                  </Button>
                </div>
              </div>
              {loadError ? (
                <ApiErrorAlert
                  error={loadError}
                  actionLabel={retryAction === 'load' ? t('settings.retryLoad') : t('settings.reload')}
                  onAction={() => void retry()}
                  className="mb-4"
                />
              ) : null}

              {activePanel === 'overview' ? (
                <SystemControlPlane
                  t={t}
                  overviewStats={heroItems}
                  summaryCards={systemHealthSummaryCards}
                  statusCards={systemStatusCards}
                  developerDetails={developerDetailGroups}
                  isRunningAdminAction={isRunningAdminAction}
                  adminActionDialog={adminActionDialog}
                  adminActionMessage={adminActionMessage}
                  adminActionTone={adminActionTone}
                  duckdbConfigEnabledState={duckdbConfigEnabledState}
                  onOpenAdminLogs={() => window.location.assign(buildAdminLogsPath())}
                  onSetAdminActionDialog={setAdminActionDialog}
                />
              ) : isLoading ? (
                <SettingsLoading />
              ) : (
                <div className="space-y-4">
                  {activeDomain === 'ai_models' ? (
                    <AIProviderConfig
                      t={t}
                      aiRoutingScope={aiRoutingScope}
                      aiRouteRows={aiRouteRows}
                      configuredProvidersText={configuredProvidersText}
                      routeStatus={t(`settings.aiRouteStatus.${aiSummary.routeStatus}`)}
                      routeMissingButApiConfigured={aiSummary.routeMissingButApiConfigured}
                      selectorReadinessMismatch={aiSelectorReadinessMismatch}
                      aiRoutingError={aiRoutingError}
                      providerCards={quickProviderCards}
                      aiChannelConfigRef={aiChannelConfigRef}
                      adminLocked={adminLocked}
                      isSaving={isSaving}
                      onOpenAiRoutingDrawer={openAiRoutingDrawer}
                      onOpenQuickProviderDrawer={openQuickProviderDrawer}
                      onJumpToProviderAdvancedConfig={jumpToProviderAdvancedConfig}
                      onSaveDirectProviderKeys={() => void saveDirectProviderKeys()}
                      onJumpToAiChannelConfig={jumpToAiChannelConfig}
                    />
                  ) : null}

                  {activeDomain === 'data_sources' ? (
                    <DataSourceConfig
                      t={t}
                      dataRoutingGroups={dataRoutingGroups}
                      dataSourceLibrary={dataSourceLibrary}
                      adminLocked={adminLocked}
                      isSaving={isSaving}
                      prettySourceLabel={prettySourceLabel}
                      onOpenDataRoutingDrawer={setDataRoutingDrawerKey}
                      onOpenCreateDataSourceDrawer={openCreateDataSourceDrawer}
                      onOpenEditDataSourceDrawer={openEditDataSourceDrawer}
                      onValidateDataSource={(sourceId) => {
                        void validateDataSourceEntry(sourceId);
                      }}
                    />
                  ) : null}

                  {activeDomain === 'notifications' ? (
                    <NotificationChannelsConfig
                      items={itemsByCategory.notification || []}
                      disabled={adminLocked}
                      isSaving={isSaving}
                      language={language}
                      onSaveItems={saveExternalItems}
                    />
                  ) : null}

                  {activeDomain === 'advanced' ? (
                    <SystemLogsConfig
                      t={t}
                      showRuntimeExecutionSummary={showRuntimeExecutionSummary}
                      adminLocked={adminLocked}
                      isSaving={isSaving}
                      onOpenRuntimeVisibilityDrawer={() => setRuntimeVisibilityDrawerOpen(true)}
                    />
                  ) : null}

                  {!isDesktopViewport ? (
                    <Disclosure
                      summary={`${t('settings.categoriesTitle')} · ${activeCategoryLabel}`}
                      className="rounded-2xl border border-white/5 bg-white/[0.02]"
                      bodyClassName="space-y-3"
                    >
                      <SettingsCategoryNav
                        categories={domainCategories}
                        itemsByCategory={itemsByCategory}
                        activeCategory={activeCategory}
                        onSelect={handleSelectCategory}
                        disabled={adminLocked}
                        hideHeader
                      />
                    </Disclosure>
                  ) : null}

                  {saveError ? (
                    <ApiErrorAlert
                      className="mt-4"
                      error={saveError}
                      actionLabel={retryAction === 'save' ? t('settings.retrySave') : undefined}
                      onAction={retryAction === 'save' ? () => void retry() : undefined}
                    />
                  ) : null}

                  {activeCategory === 'system' ? <AuthSettingsCard /> : null}
                  {activeCategory === 'base' ? (
                    <SettingsSectionCard
                      title={t('settings.importTitle')}
                      description={t('settings.importDesc')}
                    >
                      <IntelligentImport
                        stockListValue={
                          (activeItems.find((i) => i.key === 'STOCK_LIST')?.value as string) ?? ''
                        }
                        onMergeStockList={async (value) => {
                          if (adminLocked) {
                            return;
                          }
                          await saveExternalItems([{ key: 'STOCK_LIST', value }], t('settings.success'));
                        }}
                        disabled={isSaving || isLoading || adminLocked}
                      />
                    </SettingsSectionCard>
                  ) : null}
                  {activeCategory === 'system' && passwordChangeable ? (
                    <ChangePasswordCard />
                  ) : null}

                  {activeItems.length ? (
                    <SettingsSectionCard
                      title={rawFieldsSectionTitle}
                      description={rawFieldsSectionDescription}
                    >
                      <GlassCard className="px-4 py-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-foreground">{activeCategoryLabel}</p>
                            <p className="mt-1 text-xs leading-5 text-secondary-text">
                              {activeItems.length
                                ? `${rawFieldsSummaryText} · ${activeItems.length}`
                                : activeCategoryDescription}
                            </p>
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            variant="settings-secondary"
                            className={CONTROL_GHOST_BUTTON_CLASS}
                            data-testid="raw-fields-drawer-trigger"
                            onClick={() => setRawFieldsDrawerOpen(true)}
                            disabled={adminLocked || isSaving}
                          >
                            {shouldCollapseRawFields ? rawFieldsToggleLabel : t('settings.dataSourceManageAction')}
                          </Button>
                        </div>
                      </GlassCard>
                    </SettingsSectionCard>
                  ) : (
                    <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-5">
                      <p className="settings-accent-text text-xs font-semibold uppercase tracking-[0.22em]">{rawFieldsSectionTitle}</p>
                      <p className="mt-2 text-sm font-semibold text-foreground">
                        {t('settings.noItems')}
                      </p>
                      <p className="mt-2 text-xs leading-6 text-muted-text">
                        {activeCategoryDescription}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </section>
      </div>

      <Drawer
        isOpen={Boolean(dataRoutingDrawerKey && activeDataRoutingGroup)}
        onClose={() => setDataRoutingDrawerKey(null)}
        title={activeDataRoutingGroup ? activeDataRoutingGroup.role : t('settings.dataRoutingCompactTitle')}
        width="max-w-[min(100vw,48rem)]"
        zIndex={77}
        bodyClassName={SETTINGS_DRAWER_GHOST_FORM_SCOPE_CLASS}
      >
        {activeDataRoutingGroup ? (
          <div className="space-y-3">
            <div className={DRAWER_PANEL_CLASS}>
              <p className="text-sm font-semibold text-foreground">{activeDataRoutingGroup.role}</p>
              <p className="mt-1 text-xs text-secondary-text">
                {activeDataRoutingGroup.values.length
                  ? activeDataRoutingGroup.values.map((source) => prettySourceLabel(source)).join(' -> ')
                  : t('settings.notConfigured')}
              </p>
            </div>

            <div className="grid gap-3">
              <Select
                label={t('settings.sourcePrimary')}
                value={activeDataRoutingGroup.route.primary}
                onChange={(value) => setRouteTier(activeDataRoutingGroup.key, 'primary', value)}
                options={activeDataRoutingGroup.available.map((source) => ({ value: source, label: prettySourceLabel(source) }))}
                placeholder={activeDataRoutingGroup.available.length ? t('settings.selectPlaceholder') : t('settings.notConfigured')}
                disabled={adminLocked || isSaving || activeDataRoutingGroup.available.length === 0}
              />
              <details>
                <summary className={DRAWER_ADVANCED_SUMMARY_CLASS}>
                  配置高级参数 (Advanced Settings) ▾
                </summary>
                <div className="mt-3 grid gap-3">
                  <Select
                    label={t('settings.sourceBackup')}
                    value={activeDataRoutingGroup.route.backup}
                    onChange={(value) => setRouteTier(activeDataRoutingGroup.key, 'backup', value)}
                    options={activeDataRoutingGroup.available
                      .filter((source) => source !== activeDataRoutingGroup.route.primary)
                      .map((source) => ({ value: source, label: prettySourceLabel(source) }))}
                    placeholder={activeDataRoutingGroup.available.length ? t('settings.selectPlaceholder') : t('settings.notConfigured')}
                    disabled={adminLocked || isSaving || activeDataRoutingGroup.available.length < 2}
                  />
                  {activeDataRoutingGroup.allowFallback ? (
                    <Select
                      label={t('settings.sourceSecondaryBackup')}
                      value={('fallback' in activeDataRoutingGroup.route ? activeDataRoutingGroup.route.fallback : '') || ''}
                      onChange={(value) => setRouteTier(activeDataRoutingGroup.key, 'fallback', value)}
                      options={activeDataRoutingGroup.available
                        .filter((source) => source !== activeDataRoutingGroup.route.primary && source !== activeDataRoutingGroup.route.backup)
                        .map((source) => ({ value: source, label: prettySourceLabel(source) }))}
                      placeholder={activeDataRoutingGroup.available.length ? t('settings.selectPlaceholder') : t('settings.notConfigured')}
                      disabled={adminLocked || isSaving || activeDataRoutingGroup.available.length < 3}
                    />
                  ) : null}
                </div>
              </details>
            </div>

            <div className="flex justify-end">
              <Button
                type="button"
                size="sm"
                variant="settings-primary"
                disabled={adminLocked || isSaving}
                onClick={() => void activeDataRoutingGroup.onSave()}
              >
                {t('settings.saveRoute')}
              </Button>
            </div>
          </div>
        ) : null}
      </Drawer>

      <Drawer
        isOpen={runtimeVisibilityDrawerOpen}
        onClose={() => setRuntimeVisibilityDrawerOpen(false)}
        title={t('settings.runtimeSummaryVisibilityTitle')}
        width="max-w-[min(100vw,36rem)]"
        zIndex={77}
        bodyClassName={SETTINGS_DRAWER_GHOST_FORM_SCOPE_CLASS}
      >
        <div className="space-y-4">
          <GlassCard className="px-4 py-4">
            <p className="text-sm font-semibold text-foreground">{t('settings.runtimeSummaryVisibilityDesc')}</p>
          </GlassCard>
          <div className={SEGMENT_WRAPPER_CLASS}>
            <button
              type="button"
              className={showRuntimeExecutionSummary
                ? `${SEGMENT_BUTTON_CLASS} bg-white text-black`
                : `${SEGMENT_BUTTON_CLASS} text-secondary-text hover:bg-white/[0.05] hover:text-white`}
              onClick={() => setShowRuntimeExecutionSummary(true)}
              disabled={adminLocked || isSaving}
            >
              {t('settings.runtimeSummaryVisibleOn')}
            </button>
            <button
              type="button"
              className={!showRuntimeExecutionSummary
                ? `${SEGMENT_BUTTON_CLASS} bg-white text-black`
                : `${SEGMENT_BUTTON_CLASS} text-secondary-text hover:bg-white/[0.05] hover:text-white`}
              onClick={() => setShowRuntimeExecutionSummary(false)}
              disabled={adminLocked || isSaving}
            >
              {t('settings.runtimeSummaryVisibleOff')}
            </button>
          </div>
          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              variant="settings-primary"
              onClick={() => void saveRuntimeSummaryVisibility()}
              disabled={adminLocked || isSaving}
            >
              {t('settings.runtimeSummaryVisibilitySave')}
            </Button>
          </div>
        </div>
      </Drawer>

      <Drawer
        isOpen={rawFieldsDrawerOpen}
        onClose={() => setRawFieldsDrawerOpen(false)}
        title={rawFieldsSectionTitle}
        width="max-w-[min(100vw,48rem)]"
        zIndex={77}
        bodyClassName={SETTINGS_DRAWER_GHOST_FORM_SCOPE_CLASS}
      >
        <div className="space-y-3">
          <div className={DRAWER_PANEL_CLASS}>
            <p className="text-sm font-semibold text-foreground">{t('settings.rawFieldsPolicyTitle')}</p>
            <p className="mt-1 text-xs leading-5 text-secondary-text">{t('settings.rawFieldsPolicyDesc')}</p>
          </div>
          {activeItems.map((item) => (
            <SettingsField
              key={item.key}
              item={item}
              value={item.value}
              disabled={isSaving || adminLocked}
              onChange={(key, value) => {
                if (adminLocked) {
                  return;
                }
                setDraftValue(key, value);
              }}
              issues={issueByKey[item.key] || []}
            />
          ))}
        </div>
      </Drawer>

      <Drawer
        isOpen={aiRoutingDrawerOpen}
        onClose={() => setAiRoutingDrawerOpen(false)}
        title={t('settings.aiRoutingDrawerTitle')}
        width="max-w-[min(100vw,54rem)]"
        zIndex={78}
        bodyClassName={SETTINGS_DRAWER_GHOST_FORM_SCOPE_CLASS}
      >
        <div className="space-y-4">
          <div className="rounded-[var(--theme-panel-radius-lg)] border border-border/50 bg-base/40 px-4 py-3">
            <p className="text-sm font-semibold text-foreground">{t('settings.aiAnalysisRouteTitle')}</p>
            <p className="mt-1 text-xs text-secondary-text">
              {t('settings.aiRouteScopeLabel')}: {t(`settings.aiRouteScope.${aiRoutingScope}`)}
            </p>
            <p className="mt-2 text-xs text-muted-text">{t('settings.aiTaskFirstDesc')}</p>
          </div>

          <div className="grid gap-3 xl:grid-cols-2">
            <div className="rounded-[var(--theme-panel-radius-lg)] border border-border/50 bg-base/40 px-4 py-4">
              <p className="text-sm font-semibold text-foreground">{t('settings.aiPrimaryRoute')}</p>
              <div className="mt-3 space-y-2">
                <Select
                  value={routingDraft.ai.primaryChannel}
                  onChange={(value) => {
                    if (!value) {
                      setAiModelMode((prev) => ({ ...prev, primary: 'preset' }));
                      setAiRouteModelMode((prev) => ({ ...prev, primary: 'provider_default' }));
                    }
                    if (value && routingDraft.ai.backupChannel === value) {
                      setAiModelMode((prev) => ({ ...prev, backup: 'preset' }));
                      setAiRouteModelMode((prev) => ({ ...prev, backup: 'provider_default' }));
                    }
                    setRoutingDraft((prev) => ({
                      ...prev,
                      ai: {
                        ...prev.ai,
                        primaryChannel: value,
                        primaryModel: value
                          ? (aiRouteModelMode.primary === 'provider_default'
                            ? resolveProviderDefaultModel(value)
                            : prev.ai.primaryModel)
                          : '',
                        backupChannel: prev.ai.backupChannel === value ? '' : prev.ai.backupChannel,
                        backupModel: prev.ai.backupChannel === value ? '' : prev.ai.backupModel,
                      },
                    }));
                  }}
                  options={aiGatewaySelectorOptions.map((channel) => ({ value: channel, label: providerLabel(channel) }))}
                  placeholder={aiGatewaySelectorOptions.length ? t('settings.selectPlaceholder') : t('settings.notConfigured')}
                  disabled={!canSelectPrimaryGateway || adminLocked || isSaving}
                />
                {primaryGatewayDisabledReason ? (
                  <p className="text-[11px] text-muted-text">{primaryGatewayDisabledReason}</p>
                ) : null}

                <p className="text-xs text-muted-text">{t('settings.aiRouteModelModeLabel')}</p>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className={aiRouteModelMode.primary === 'provider_default'
                      ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                      : 'rounded-[var(--theme-control-radius)] border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                    onClick={() => setAiRouteModelMode((prev) => ({ ...prev, primary: 'provider_default' }))}
                    disabled={adminLocked || isSaving || !routingDraft.ai.primaryChannel}
                  >
                    {t('settings.aiRouteModelModeProviderDefault')}
                  </button>
                  <button
                    type="button"
                    className={aiRouteModelMode.primary === 'explicit'
                      ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                      : 'rounded-[var(--theme-control-radius)] border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                    onClick={() => setAiRouteModelMode((prev) => ({ ...prev, primary: 'explicit' }))}
                    disabled={adminLocked || isSaving || !routingDraft.ai.primaryChannel}
                  >
                    {t('settings.aiRouteModelModeExplicit')}
                  </button>
                </div>

                {aiRouteModelMode.primary === 'provider_default' ? (
                  <p className="text-[11px] text-muted-text">
                    {aiProviderDefaultHint(routingDraft.ai.primaryChannel, routingDraft.ai.primaryModel)}
                  </p>
                ) : (
                  <>
                    <p className="text-xs text-muted-text">{t('settings.aiModelModeLabel')}</p>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className={aiModelMode.primary === 'preset'
                          ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                          : 'rounded-[var(--theme-control-radius)] border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                        onClick={() => setAiModelMode((prev) => ({ ...prev, primary: 'preset' }))}
                        disabled={adminLocked || isSaving || !routingDraft.ai.primaryChannel}
                      >
                        {t('settings.aiModelModePreset')}
                      </button>
                      <button
                        type="button"
                        className={aiModelMode.primary === 'custom'
                          ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                          : 'rounded-[var(--theme-control-radius)] border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                        onClick={() => setAiModelMode((prev) => ({ ...prev, primary: 'custom' }))}
                        disabled={adminLocked || isSaving || !routingDraft.ai.primaryChannel || !canUsePrimaryCustomModel}
                      >
                        {t('settings.aiModelModeCustom')}
                      </button>
                    </div>
                    <p className="text-[11px] text-muted-text">
                      {aiModelModeHint(routingDraft.ai.primaryChannel, aiModelMode.primary)}
                    </p>
                    {aiModelMode.primary === 'preset' ? (
                      <Select
                        value={primaryPresetOptions.includes(routingDraft.ai.primaryModel) ? routingDraft.ai.primaryModel : ''}
                        onChange={(value) => setRoutingDraft((prev) => ({
                          ...prev,
                          ai: {
                            ...prev.ai,
                            primaryModel: value,
                            backupModel: prev.ai.backupModel === value ? '' : prev.ai.backupModel,
                          },
                        }))}
                        options={primaryPresetOptions.map((model) => ({ value: model, label: model }))}
                        placeholder={primaryPresetOptions.length ? t('settings.aiPresetModels') : t('settings.notConfigured')}
                        disabled={adminLocked || isSaving || !routingDraft.ai.primaryChannel}
                      />
                    ) : (
                      <Input
                        type="text"
                        label={t('settings.aiCustomModelId')}
                        placeholder={aiCustomModelPlaceholder(routingDraft.ai.primaryChannel)}
                        value={routingDraft.ai.primaryModel}
                        onChange={(event) => {
                          const value = event.target.value;
                          setRoutingDraft((prev) => ({
                            ...prev,
                            ai: {
                              ...prev.ai,
                              primaryModel: value,
                              backupModel: prev.ai.backupModel === value ? '' : prev.ai.backupModel,
                            },
                          }));
                        }}
                        disabled={adminLocked || isSaving || !canUsePrimaryCustomModel}
                        hint={routingDraft.ai.primaryChannel ? aiCustomModelHint(routingDraft.ai.primaryChannel) : t('settings.aiModelModeRequiresGateway')}
                      />
                    )}
                  </>
                )}

                {!primaryModelCompatible && routingDraft.ai.primaryModel && aiRouteModelMode.primary === 'explicit' ? (
                  <p className="text-xs text-[hsl(var(--accent-warning-hsl))]">{t('settings.aiModelCompatibilityWarning')}</p>
                ) : null}
              </div>
            </div>

            <div className="rounded-[var(--theme-panel-radius-lg)] border border-border/50 bg-base/40 px-4 py-4">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-foreground">{t('settings.aiBackupRoute')}</p>
                <Button
                  type="button"
                  size="sm"
                  variant="settings-secondary"
                  className={CONTROL_GHOST_BUTTON_CLASS}
                  onClick={() => {
                    setAiRoutingError(null);
                    setAiModelMode((prev) => ({ ...prev, backup: 'preset' }));
                    setAiRouteModelMode((prev) => ({ ...prev, backup: 'provider_default' }));
                    setRoutingDraft((prev) => ({
                      ...prev,
                      ai: {
                        ...prev.ai,
                        backupChannel: '',
                        backupModel: '',
                      },
                    }));
                  }}
                  disabled={adminLocked || isSaving || (!routingDraft.ai.backupChannel && !routingDraft.ai.backupModel)}
                >
                  {t('settings.aiClearBackupRoute')}
                </Button>
              </div>
              <div className="mt-3 space-y-2">
                <Select
                  value={routingDraft.ai.backupChannel}
                  onChange={(value) => {
                    if (!value) {
                      setAiModelMode((prev) => ({ ...prev, backup: 'preset' }));
                      setAiRouteModelMode((prev) => ({ ...prev, backup: 'provider_default' }));
                    }
                    setRoutingDraft((prev) => ({
                      ...prev,
                      ai: {
                        ...prev.ai,
                        backupChannel: value,
                        backupModel: value
                          ? (aiRouteModelMode.backup === 'provider_default'
                            ? resolveProviderDefaultModel(value)
                            : prev.ai.backupModel)
                          : '',
                      },
                    }));
                  }}
                  options={aiGatewaySelectorOptions
                    .filter((channel) => channel !== routingDraft.ai.primaryChannel)
                    .map((channel) => ({ value: channel, label: providerLabel(channel) }))}
                  placeholder={aiGatewaySelectorOptions.length ? t('settings.selectPlaceholder') : t('settings.notConfigured')}
                  disabled={!canSelectBackupGateway || adminLocked || isSaving}
                />
                {backupGatewayDisabledReason ? (
                  <p className="text-[11px] text-muted-text">{backupGatewayDisabledReason}</p>
                ) : null}

                <p className="text-xs text-muted-text">{t('settings.aiRouteModelModeLabel')}</p>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className={aiRouteModelMode.backup === 'provider_default'
                      ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                      : 'rounded-[var(--theme-control-radius)] border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                    onClick={() => setAiRouteModelMode((prev) => ({ ...prev, backup: 'provider_default' }))}
                    disabled={adminLocked || isSaving || !routingDraft.ai.backupChannel}
                  >
                    {t('settings.aiRouteModelModeProviderDefault')}
                  </button>
                  <button
                    type="button"
                    className={aiRouteModelMode.backup === 'explicit'
                      ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                      : 'rounded-[var(--theme-control-radius)] border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                    onClick={() => setAiRouteModelMode((prev) => ({ ...prev, backup: 'explicit' }))}
                    disabled={adminLocked || isSaving || !routingDraft.ai.backupChannel}
                  >
                    {t('settings.aiRouteModelModeExplicit')}
                  </button>
                </div>

                {aiRouteModelMode.backup === 'provider_default' ? (
                  <p className="text-[11px] text-muted-text">
                    {aiProviderDefaultHint(routingDraft.ai.backupChannel, routingDraft.ai.backupModel)}
                  </p>
                ) : (
                  <>
                    <p className="text-xs text-muted-text">{t('settings.aiModelModeLabel')}</p>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className={aiModelMode.backup === 'preset'
                          ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                          : 'rounded-[var(--theme-control-radius)] border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                        onClick={() => setAiModelMode((prev) => ({ ...prev, backup: 'preset' }))}
                        disabled={adminLocked || isSaving || !routingDraft.ai.backupChannel}
                      >
                        {t('settings.aiModelModePreset')}
                      </button>
                      <button
                        type="button"
                        className={aiModelMode.backup === 'custom'
                          ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                          : 'rounded-[var(--theme-control-radius)] border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                        onClick={() => setAiModelMode((prev) => ({ ...prev, backup: 'custom' }))}
                        disabled={adminLocked || isSaving || !routingDraft.ai.backupChannel || !canUseBackupCustomModel}
                      >
                        {t('settings.aiModelModeCustom')}
                      </button>
                    </div>
                    <p className="text-[11px] text-muted-text">
                      {aiModelModeHint(routingDraft.ai.backupChannel, aiModelMode.backup)}
                    </p>
                    {aiModelMode.backup === 'preset' ? (
                      <Select
                        value={backupPresetOptions.includes(routingDraft.ai.backupModel) ? routingDraft.ai.backupModel : ''}
                        onChange={(value) => setRoutingDraft((prev) => ({
                          ...prev,
                          ai: {
                            ...prev.ai,
                            backupModel: value,
                          },
                        }))}
                        options={backupPresetOptions.map((model) => ({ value: model, label: model }))}
                        placeholder={backupPresetOptions.length ? t('settings.aiPresetModels') : t('settings.notConfigured')}
                        disabled={adminLocked || isSaving || !routingDraft.ai.backupChannel}
                      />
                    ) : (
                      <Input
                        type="text"
                        label={t('settings.aiCustomModelId')}
                        placeholder={aiCustomModelPlaceholder(routingDraft.ai.backupChannel)}
                        value={routingDraft.ai.backupModel}
                        onChange={(event) => setRoutingDraft((prev) => ({
                          ...prev,
                          ai: {
                            ...prev.ai,
                            backupModel: event.target.value,
                          },
                        }))}
                        disabled={adminLocked || isSaving || !canUseBackupCustomModel}
                        hint={routingDraft.ai.backupChannel ? aiCustomModelHint(routingDraft.ai.backupChannel) : t('settings.aiModelModeRequiresGateway')}
                      />
                    )}
                  </>
                )}

                {!backupModelCompatible && routingDraft.ai.backupModel && aiRouteModelMode.backup === 'explicit' ? (
                  <p className="text-xs text-[hsl(var(--accent-warning-hsl))]">{t('settings.aiModelCompatibilityWarning')}</p>
                ) : null}
                {backupRouteCompatibilityIssue ? (
                  <div className="rounded-lg border border-[hsl(var(--accent-warning-hsl)/0.4)] bg-[hsl(var(--accent-warning-hsl)/0.12)] px-3 py-2 text-xs text-[hsl(var(--accent-warning-hsl))]">
                    <p>{backupRouteCompatibilityIssue}</p>
                    <button
                      type="button"
                      className="mt-2 inline-flex items-center rounded-md border border-border/60 bg-base/60 px-2.5 py-1 text-[11px] text-secondary-text hover:text-foreground"
                      onClick={jumpToAiChannelConfig}
                    >
                      {t('settings.aiBackupCompatibilityAction')}
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              variant="settings-primary"
              onClick={() => void saveAiRouting()}
              disabled={adminLocked || isSaving || Boolean(backupRouteCompatibilityIssue)}
            >
              {t('settings.saveRoute')}
            </Button>
          </div>

          <div className="rounded-[var(--theme-panel-radius-lg)] border border-border/50 bg-base/40 px-4 py-4">
            <p className="text-sm font-semibold text-foreground">{t('settings.aiTaskModelTitle')}</p>
            <p className="mt-1 text-xs text-secondary-text">{t('settings.aiTaskModelDesc')}</p>
            <div className="mt-3 grid gap-3 xl:grid-cols-2">
              {([
                {
                  key: 'stock_chat' as const,
                  effectiveGateway: askStockEffectiveGateway,
                  effectiveModel: askStockEffectiveModel,
                },
                {
                  key: 'backtest' as const,
                  effectiveGateway: backtestEffectiveGateway,
                  effectiveModel: backtestEffectiveModel,
                },
              ]).map((task) => {
                const draft = taskRoutingDraft[task.key];
                const mode = taskModelMode[task.key];
                const routeMode = taskRouteModelMode[task.key];
                const options = taskModelOptions[task.key];
                const compatible = taskModelCompatible[task.key];
                const supportsCustom = Boolean(draft.gateway) && supportsCustomModelId(draft.gateway);
                const disabledTaskEditor = adminLocked || isSaving;
                return (
                  <div
                    key={task.key}
                    className="rounded-[var(--theme-panel-radius-md)] border border-border/50 bg-base/40 px-3.5 py-3"
                    data-testid={`ai-task-card-${task.key}`}
                  >
                    <p className="text-sm font-semibold text-foreground">{t(`settings.aiTaskName.${task.key}`)}</p>
                    <p className="mt-1 text-xs text-secondary-text">
                      {t('settings.aiTaskEffectiveRoute')}: {formatRouteLine(task.effectiveGateway, task.effectiveModel)}
                    </p>
                    <div className="mt-3 grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        className={draft.inherit
                          ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-3 py-2 text-xs text-foreground'
                          : 'rounded-[var(--theme-control-radius)] border border-[var(--border-muted)] bg-[var(--pill-bg)] px-3 py-2 text-xs text-secondary-text hover:border-[var(--border-strong)] hover:text-foreground'}
                        onClick={() => setTaskRouteInherit(task.key, true)}
                        disabled={disabledTaskEditor}
                      >
                        {t('settings.aiTaskInheritFromAnalysis')}
                      </button>
                      <button
                        type="button"
                        className={!draft.inherit
                          ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-3 py-2 text-xs text-foreground'
                          : 'rounded-[var(--theme-control-radius)] border border-[var(--border-muted)] bg-[var(--pill-bg)] px-3 py-2 text-xs text-secondary-text hover:border-[var(--border-strong)] hover:text-foreground'}
                        onClick={() => setTaskRouteInherit(task.key, false)}
                        disabled={disabledTaskEditor}
                      >
                        {t('settings.aiTaskOverride')}
                      </button>
                    </div>

                    {!draft.inherit ? (
                      <div className="mt-3 space-y-2">
                        <Select
                          value={draft.gateway}
                          onChange={(value) => setTaskRouteGateway(task.key, value)}
                          options={taskGatewayOptions.map((gateway) => ({ value: gateway, label: providerLabel(gateway) }))}
                          placeholder={taskGatewayOptions.length ? t('settings.selectPlaceholder') : t('settings.notConfigured')}
                          disabled={disabledTaskEditor || !canSelectPrimaryGateway}
                        />
                        {primaryGatewayDisabledReason ? (
                          <p className="text-[11px] text-muted-text">{primaryGatewayDisabledReason}</p>
                        ) : null}
                        <p className="text-xs text-muted-text">{t('settings.aiRouteModelModeLabel')}</p>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            className={routeMode === 'provider_default'
                              ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                              : 'rounded-[var(--theme-control-radius)] border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                            onClick={() => setTaskRouteModelMode((prev) => ({ ...prev, [task.key]: 'provider_default' }))}
                            disabled={disabledTaskEditor || !draft.gateway}
                          >
                            {t('settings.aiRouteModelModeProviderDefault')}
                          </button>
                          <button
                            type="button"
                            className={routeMode === 'explicit'
                              ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                              : 'rounded-[var(--theme-control-radius)] border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                            onClick={() => setTaskRouteModelMode((prev) => ({ ...prev, [task.key]: 'explicit' }))}
                            disabled={disabledTaskEditor || !draft.gateway}
                          >
                            {t('settings.aiRouteModelModeExplicit')}
                          </button>
                        </div>

                        {routeMode === 'provider_default' ? (
                          <p className="text-[11px] text-muted-text">
                            {aiProviderDefaultHint(draft.gateway, draft.model)}
                          </p>
                        ) : (
                          <>
                            <p className="text-xs text-muted-text">{t('settings.aiModelModeLabel')}</p>
                            <div className="flex flex-wrap gap-2">
                              <button
                                type="button"
                                className={mode === 'preset'
                                  ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                                  : 'rounded-[var(--theme-control-radius)] border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                                onClick={() => setTaskModelMode((prev) => ({ ...prev, [task.key]: 'preset' }))}
                                disabled={disabledTaskEditor || !draft.gateway}
                              >
                                {t('settings.aiModelModePreset')}
                              </button>
                              <button
                                type="button"
                                className={mode === 'custom'
                                  ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                                  : 'rounded-[var(--theme-control-radius)] border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                                onClick={() => setTaskModelMode((prev) => ({ ...prev, [task.key]: 'custom' }))}
                                disabled={disabledTaskEditor || !draft.gateway || !supportsCustom}
                              >
                                {t('settings.aiModelModeCustom')}
                              </button>
                            </div>
                            <p className="text-[11px] text-muted-text">
                              {aiModelModeHint(draft.gateway, mode)}
                            </p>
                            {mode === 'preset' ? (
                              <Select
                                value={options.includes(draft.model) ? draft.model : ''}
                                onChange={(value) => setTaskRouteModel(task.key, value)}
                                options={options.map((model) => ({ value: model, label: model }))}
                                placeholder={options.length ? t('settings.aiPresetModels') : t('settings.notConfigured')}
                                disabled={disabledTaskEditor || !draft.gateway}
                              />
                            ) : (
                              <Input
                                type="text"
                                label={t('settings.aiCustomModelId')}
                                placeholder={aiCustomModelPlaceholder(draft.gateway)}
                                value={draft.model}
                                onChange={(event) => setTaskRouteModel(task.key, event.target.value)}
                                disabled={disabledTaskEditor || !supportsCustom}
                                hint={draft.gateway ? aiCustomModelHint(draft.gateway) : t('settings.aiModelModeRequiresGateway')}
                              />
                            )}
                          </>
                        )}

                        {!compatible && draft.model && routeMode === 'explicit' ? (
                          <p className="text-xs text-[hsl(var(--accent-warning-hsl))]">{t('settings.aiModelCompatibilityWarning')}</p>
                        ) : null}
                      </div>
                    ) : (
                      <p className="mt-3 text-xs text-secondary-text">{t('settings.aiTaskInheritHint')}</p>
                    )}

                    <div className="mt-3 flex justify-end">
                      <Button
                        type="button"
                        size="sm"
                        variant="settings-secondary"
                        className={CONTROL_GHOST_BUTTON_CLASS}
                        onClick={() => void saveTaskRoute(task.key)}
                        disabled={disabledTaskEditor}
                      >
                        {t('settings.aiTaskSave')}
                      </Button>
                    </div>

                    {taskRoutingError[task.key] ? (
                      <p className="mt-2 rounded-lg border border-[hsl(var(--accent-warning-hsl)/0.4)] bg-[hsl(var(--accent-warning-hsl)/0.12)] px-3 py-2 text-xs text-[hsl(var(--accent-warning-hsl))]">
                        {taskRoutingError[task.key]}
                      </p>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </Drawer>

      <Drawer
        isOpen={Boolean(quickProviderDrawerProvider)}
        onClose={() => setQuickProviderDrawerProvider(null)}
        title={quickProviderDrawerItem
          ? t('settings.aiProviderDrawerTitle', { provider: quickProviderDrawerItem.label })
          : t('settings.aiProviderDrawerTitleFallback')}
        width="max-w-[min(100vw,34rem)]"
        zIndex={79}
        bodyClassName={SETTINGS_DRAWER_GHOST_FORM_SCOPE_CLASS}
      >
        {quickProviderDrawerItem ? (
          <div className="space-y-3">
            <div className={DRAWER_PANEL_CLASS}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-foreground">{quickProviderDrawerItem.label}</p>
                <span className={GHOST_TAG_CLASS}>
                  {resolveQuickProviderCredential(quickProviderDrawerItem.key)
                    ? t('settings.aiProviderReady')
                    : t('settings.aiProviderMissingCredential')}
                </span>
              </div>
              <p className="mt-2 text-xs text-secondary-text">
                {quickProviderDrawerItem.key === 'zhipu'
                  ? t('settings.aiProviderAdvancedHintZhipu')
                  : t('settings.aiProviderQuickHint')}
              </p>
              <p className="mt-2 text-xs text-muted-text">
                {quickProviderDrawerItem.key === 'zhipu'
                  ? t('settings.aiProviderQuickTestScopeHintZhipu')
                  : t('settings.aiProviderQuickTestScopeHint')}
              </p>
              <p className="mt-2 text-xs text-muted-text">
                {t('settings.aiProviderTestModelLabel')}: {resolveQuickProviderTestModel(quickProviderDrawerItem.key) || t('settings.aiProviderTestModelMissing')}
              </p>
            </div>

            <div className={DRAWER_SECTION_CLASS}>
              <Input
                type="password"
                allowTogglePassword
                iconType="password"
                label={t('settings.aiApiKeyLabel')}
                placeholder={t('settings.aiDirectProviderPlaceholder')}
                value={directProviderDraft[quickProviderDrawerItem.key]}
                onChange={(event) => setDirectProviderDraft((prev) => ({
                  ...prev,
                  [quickProviderDrawerItem.key]: event.target.value,
                }))}
                disabled={adminLocked || isSaving}
                hint={quickProviderDrawerItem.mode === 'advanced' ? t('settings.aiProviderAdvancedOnly') : undefined}
              />
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="settings-secondary"
                  className={CONTROL_GHOST_BUTTON_CLASS}
                  onClick={() => void testQuickProviderConnection(quickProviderDrawerItem.key)}
                  disabled={adminLocked || isSaving || quickProviderTestState[quickProviderDrawerItem.key].status === 'loading'}
                  isLoading={quickProviderTestState[quickProviderDrawerItem.key].status === 'loading'}
                  loadingText={t('settings.aiProviderTestLoading')}
                >
                  {t('settings.aiProviderTestAction')}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="settings-primary"
                  onClick={() => void saveDirectProviderKeys()}
                  disabled={adminLocked || isSaving}
                >
                  {t('settings.aiDirectProviderSave')}
                </Button>
              </div>
              {quickProviderTestState[quickProviderDrawerItem.key].status !== 'idle' ? (
                <p className={quickProviderTestState[quickProviderDrawerItem.key].status === 'success'
                  ? 'mt-2 text-xs text-[hsl(var(--accent-positive-hsl))]'
                  : quickProviderTestState[quickProviderDrawerItem.key].status === 'error'
                    ? 'mt-2 text-xs text-[hsl(var(--accent-warning-hsl))]'
                    : 'mt-2 text-xs text-muted-text'}
                >
                  {quickProviderTestState[quickProviderDrawerItem.key].text}
                </p>
              ) : null}
              <details>
                <summary className={DRAWER_ADVANCED_SUMMARY_CLASS}>
                  配置高级参数 (Advanced Settings) ▾
                </summary>
                <div className="mt-3 flex justify-end">
                  <Button
                    type="button"
                    size="sm"
                    variant="settings-secondary"
                    className={CONTROL_GHOST_BUTTON_CLASS}
                    onClick={() => {
                      jumpToProviderAdvancedConfig(quickProviderDrawerItem.key);
                      setQuickProviderDrawerProvider(null);
                    }}
                    disabled={adminLocked || isSaving}
                  >
                    {t('settings.aiDirectProviderAdvancedEntryForProvider', { provider: quickProviderDrawerItem.label })}
                  </Button>
                </div>
              </details>
            </div>
          </div>
        ) : null}
      </Drawer>

      <Drawer
        isOpen={aiAdvancedDrawerOpen}
        onClose={() => setAiAdvancedDrawerOpen(false)}
        title={t('settings.aiAdvancedDrawerTitle')}
        width="max-w-[min(100vw,56rem)]"
        zIndex={80}
        bodyClassName={SETTINGS_DRAWER_GHOST_FORM_SCOPE_CLASS}
      >
        <div className="space-y-4">
          <div className="rounded-[var(--theme-panel-radius-lg)] border border-border/50 bg-base/40 px-4 py-3">
            <p className="text-sm font-semibold text-foreground">{t('settings.aiAdvancedChannelLayerTitle')}</p>
            <p className="mt-1 text-xs text-secondary-text">{t('settings.aiAdvancedLayerDesc')}</p>
            {advancedNavigationContext ? (
              <div className="mt-3 rounded-xl border border-border/60 bg-base/40 px-3 py-2 text-xs">
                {advancedNavigationContext.hasChannel ? (
                  <p className="text-secondary-text">
                    {t('settings.aiAdvancedChannelFocusMessage', {
                      provider: providerLabel(advancedNavigationContext.provider),
                      channel: advancedNavigationContext.channelName || '',
                    })}
                  </p>
                ) : (
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-secondary-text">
                      {t('settings.aiAdvancedChannelMissingMessage', {
                        provider: providerLabel(advancedNavigationContext.provider),
                      })}
                    </p>
                    <Button
                      type="button"
                      size="sm"
                      variant="settings-secondary"
                      className={CONTROL_GHOST_BUTTON_CLASS}
                      onClick={() => handleCreateAdvancedProviderChannel(advancedNavigationContext.provider)}
                      disabled={adminLocked || isSaving}
                    >
                      {t('settings.aiAdvancedChannelCreateAction', {
                        provider: providerLabel(advancedNavigationContext.provider),
                      })}
                    </Button>
                  </div>
                )}
              </div>
            ) : null}
          </div>
          <Suspense
            fallback={(
              <div
                role="status"
                aria-live="polite"
                className="rounded-[var(--theme-panel-radius-lg)] border border-border/50 bg-base/40 px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <span aria-hidden="true" className="h-2 w-2 rounded-full bg-cyan-300/80 animate-pulse" />
                  <div className="space-y-1">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-200/80">
                      高级渠道终端
                    </p>
                    <p className="text-xs text-secondary-text">正在按需加载高级渠道终端…</p>
                  </div>
                </div>
              </div>
            )}
          >
            <LazyLLMChannelEditor
              items={rawActiveItems}
              adminUnlockToken={adminUnlockToken}
              providerScopeName={advancedNavigationContext?.provider || ''}
              focusChannelName={advancedFocusChannelName}
              externalCreatePreset={advancedCreatePreset}
              onExternalCreateHandled={() => setAdvancedCreatePreset(null)}
              onSaveItems={async (updatedItems, successMessage) => {
                if (adminLocked) {
                  return;
                }
                await saveExternalItems(updatedItems, successMessage);
              }}
              disabled={isSaving || isLoading || adminLocked}
            />
          </Suspense>
        </div>
      </Drawer>

      <DataSourceLibraryDrawer
        adminLocked={adminLocked}
        isOpen={dataSourceLibraryDrawerOpen}
        isSaving={isSaving}
        language={language}
        deleteTarget={dataSourceDeleteTarget}
        draft={dataSourceEditorDraft}
        entry={dataSourceEditorEntry}
        mode={dataSourceEditorMode}
        managedBuiltinDraft={managedBuiltinDataSourceDraft}
        bodyClassName={SETTINGS_DRAWER_GHOST_FORM_SCOPE_CLASS}
        onClose={closeDataSourceDrawer}
        onDeleteTargetChange={setDataSourceDeleteTargetId}
        onDraftChange={setDataSourceEditorDraft}
        onManagedBuiltinDraftChange={setManagedBuiltinDataSourceDraft}
        onSave={() => void saveDataSourceEditor()}
        onValidate={(sourceId) => {
          void validateDataSourceEntry(sourceId);
        }}
        onConfirmDelete={() => void deleteDataSourceEntry()}
        t={t}
        validationResult={dataSourceEditorValidationResult}
      />

      <ConfirmDialog
        isOpen={adminActionDialog !== null}
        title={adminActionDialog === 'factory_reset'
          ? t('settings.adminActionFactoryResetConfirmTitle')
          : t('settings.adminActionResetRuntimeCachesConfirmTitle')}
        message={adminActionDialog === 'factory_reset'
          ? t('settings.adminActionFactoryResetConfirmBody')
          : t('settings.adminActionResetRuntimeCachesConfirmBody')}
        confirmText={t('settings.adminActionConfirm')}
        isDanger
        confirmationLabel={adminActionDialog === 'factory_reset' ? t('settings.adminActionFactoryResetConfirmationLabel') : undefined}
        confirmationHint={adminActionDialog === 'factory_reset' ? t('settings.adminActionFactoryResetConfirmationHint') : undefined}
        confirmationPhrase={adminActionDialog === 'factory_reset' ? 'FACTORY RESET' : undefined}
        confirmationValue={factoryResetConfirmation}
        onConfirmationValueChange={setFactoryResetConfirmation}
        onConfirm={() => void (adminActionDialog === 'factory_reset' ? runFactoryResetSystem() : runResetRuntimeCaches())}
        onCancel={() => {
          if (isRunningAdminAction) {
            return;
          }
          setAdminActionDialog(null);
          setFactoryResetConfirmation('');
        }}
      />
      <PageBriefDrawer
        isOpen={isBriefDrawerOpen}
        onClose={() => setIsBriefDrawerOpen(false)}
        title={t('settings.title')}
        testId="settings-bento-drawer"
        summary={language === 'en'
          ? 'This control plane now shares the Bento shell with the rest of the product while preserving the same admin-only routing, save flow, and provider drawers.'
          : '这个控制面现在与产品其他页面共用 Bento 外壳，但管理员路由、保存流程和各类 provider 抽屉都保持不变。'}
        metrics={[
          {
            label: t('settings.globalSummaryProviders'),
            value: aiSummary.configuredProviders,
            tone: Number(aiSummary.configuredProviders) > 0 ? 'bullish' : 'neutral',
          },
          {
            label: t('settings.globalSummaryDataSources'),
            value: dataSourceLibrary.filter((source) => source.usable).length,
          },
          {
            label: t('settings.domainTitle'),
            value: activeDomainTitle,
          },
          {
            label: t('settings.save'),
            value: dirtyCount || 0,
            tone: dirtyCount ? 'bearish' : 'bullish',
          },
        ]}
        bullets={[
          language === 'en'
            ? 'The hero strip summarizes provider readiness, usable data sources, active domain, and dirty state before you scroll into the control plane.'
            : 'Hero strip 先总结 provider 就绪度、可用数据源、当前域和脏状态，再进入控制面细节。',
          language === 'en'
            ? 'All existing management drawers remain intact, so this pass does not rewrite admin workflows.'
            : '原有管理抽屉全部保留，因此这次改动没有重写管理员工作流。',
          language === 'en'
            ? 'This segment focuses on layout convergence, stable hooks, and browser-visible structure.'
            : '这一段聚焦布局收敛、稳定测试钩子和浏览器可见结构。',
        ]}
        footnote={language === 'en' ? 'Admin scope unchanged.' : '管理员边界不变。'}
      />

      {toast ? (
        <div className="fixed bottom-5 right-5 z-50 w-[320px] max-w-[calc(100vw-24px)]">
          {toast.type === 'success'
            ? <SettingsAlert title={t('settings.success')} message={toast.message} variant="success" />
            : <ApiErrorAlert error={toast.error} />}
        </div>
      ) : null}
    </div>
  );
};

export default SettingsPage;
