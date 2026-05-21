import type React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { translate } from '../../i18n/core';
import SettingsPage from '../SettingsPage';

const zh = (key: string, vars?: Record<string, string | number | undefined>) => translate('zh', key, vars);

const {
  load,
  clearToast,
  setActiveCategory,
  save,
  saveExternalItems,
  resetDraft,
  setDraftValue,
  applyPartialUpdate,
  setAdminUnlockSession,
  clearAdminUnlockSession,
  refreshStatus,
  setThemeStyle,
  testLLMChannel,
  testCustomDataSource,
  testBuiltinDataSource,
  resetRuntimeCaches,
  factoryResetSystem,
  getDuckDBHealth,
  getDuckDBCoverage,
  initDuckDB,
  runDuckDBBenchmark,
  getDuckDBFactorSnapshot,
  validateDuckDBFactorPath,
  compareDuckDBRuntimeContext,
  buildDuckDBFactors,
  useAuthMock,
  useSystemConfigMock,
  llmEditorModuleLoad,
  dataSourceDrawerModuleLoad,
} = vi.hoisted(() => ({
  load: vi.fn(),
  clearToast: vi.fn(),
  setActiveCategory: vi.fn(),
  save: vi.fn(),
  saveExternalItems: vi.fn(),
  resetDraft: vi.fn(),
  setDraftValue: vi.fn(),
  applyPartialUpdate: vi.fn(),
  setAdminUnlockSession: vi.fn(),
  clearAdminUnlockSession: vi.fn(),
  refreshStatus: vi.fn(),
  setThemeStyle: vi.fn(),
  testLLMChannel: vi.fn(),
  testCustomDataSource: vi.fn(),
  testBuiltinDataSource: vi.fn(),
  resetRuntimeCaches: vi.fn(),
  factoryResetSystem: vi.fn(),
  getDuckDBHealth: vi.fn(),
  getDuckDBCoverage: vi.fn(),
  initDuckDB: vi.fn(),
  runDuckDBBenchmark: vi.fn(),
  getDuckDBFactorSnapshot: vi.fn(),
  validateDuckDBFactorPath: vi.fn(),
  compareDuckDBRuntimeContext: vi.fn(),
  buildDuckDBFactors: vi.fn(),
  useAuthMock: vi.fn(),
  useSystemConfigMock: vi.fn(),
  dataSourceDrawerModuleLoad: (() => {
    let resolve: (() => void) | null = null;
    const state = {
      loadCount: 0,
      promise: Promise.resolve(),
      reset() {
        state.loadCount = 0;
        state.promise = Promise.resolve();
        resolve = null;
      },
      defer() {
        state.loadCount = 0;
        state.promise = new Promise<void>((nextResolve) => {
          resolve = nextResolve;
        });
      },
      resolve() {
        resolve?.();
      },
    };
    return state;
  })(),
  llmEditorModuleLoad: (() => {
    let resolve: (() => void) | null = null;
    const state = {
      loadCount: 0,
      promise: Promise.resolve(),
      reset() {
        state.loadCount = 0;
        state.promise = new Promise<void>((nextResolve) => {
          resolve = nextResolve;
        });
      },
      resolve() {
        resolve?.();
      },
    };
    state.reset();
    return state;
  })(),
}));

vi.mock('../../api/systemConfig', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/systemConfig')>();
    return {
      ...actual,
      systemConfigApi: {
        ...actual.systemConfigApi,
        testLLMChannel,
        testCustomDataSource,
        testBuiltinDataSource,
        resetRuntimeCaches,
        factoryResetSystem,
      },
    };
});

vi.mock('../../api/quant', () => ({
  quantApi: {
    getDuckDBHealth,
    getDuckDBCoverage,
    initDuckDB,
    runDuckDBBenchmark,
    getDuckDBFactorSnapshot,
    validateDuckDBFactorPath,
    compareDuckDBRuntimeContext,
    buildDuckDBFactors,
  },
}));

vi.mock('../../hooks', () => ({
  useAuth: () => useAuthMock(),
  useSystemConfig: () => useSystemConfigMock(),
}));

vi.mock('../../components/theme/ThemeProvider', () => ({
  useThemeStyle: () => ({
    themeStyle: 'spacex',
    setThemeStyle,
  }),
}));

vi.mock('../../components/settings/LLMChannelEditor', async () => {
  llmEditorModuleLoad.loadCount += 1;
  await llmEditorModuleLoad.promise;
  return {
    LLMChannelEditor: ({
      onSaveItems,
      providerScopeName,
      focusChannelName,
      externalCreatePreset,
      onExternalCreateHandled,
    }: {
      onSaveItems: (items: Array<{ key: string; value: string }>, successMessage: string) => void;
      providerScopeName?: string;
      focusChannelName?: string;
      externalCreatePreset?: string | null;
      onExternalCreateHandled?: () => void;
    }) => (
      <div>
        <button
          type="button"
          onClick={() => onSaveItems([{ key: 'LLM_CHANNELS', value: 'primary,backup' }], '渠道配置已保存')}
        >
          save llm channels
        </button>
        <p data-testid="llm-provider-scope">{providerScopeName || ''}</p>
        <p data-testid="llm-focus-channel">{focusChannelName || ''}</p>
        {externalCreatePreset ? (
          <button type="button" onClick={() => onExternalCreateHandled?.()}>
            external create {externalCreatePreset}
          </button>
        ) : null}
      </div>
    ),
  };
});

vi.mock('../../components/settings/DataSourceLibraryDrawer', async (importOriginal) => {
  dataSourceDrawerModuleLoad.loadCount += 1;
  await dataSourceDrawerModuleLoad.promise;
  return importOriginal<typeof import('../../components/settings/DataSourceLibraryDrawer')>();
});

vi.mock('../../components/settings', () => ({
  AuthSettingsCard: () => <div>认证与登录保护</div>,
  ChangePasswordCard: () => <div>修改密码</div>,
  IntelligentImport: ({ onMergeStockList }: { onMergeStockList: (value: string) => void }) => (
    <button type="button" onClick={() => onMergeStockList('SZ000001,SZ000002')}>
      merge stock list
    </button>
  ),
  FontSizeSettingsCard: () => <div>字体大小</div>,
  LLMChannelEditor: ({
    onSaveItems,
    providerScopeName,
    focusChannelName,
    externalCreatePreset,
    onExternalCreateHandled,
  }: {
    onSaveItems: (items: Array<{ key: string; value: string }>, successMessage: string) => void;
    providerScopeName?: string;
    focusChannelName?: string;
    externalCreatePreset?: string | null;
    onExternalCreateHandled?: () => void;
  }) => (
    <div>
      <button
        type="button"
        onClick={() => onSaveItems([{ key: 'LLM_CHANNELS', value: 'primary,backup' }], '渠道配置已保存')}
      >
        save llm channels
      </button>
      <p data-testid="llm-provider-scope">{providerScopeName || ''}</p>
      <p data-testid="llm-focus-channel">{focusChannelName || ''}</p>
      {externalCreatePreset ? (
        <button type="button" onClick={() => onExternalCreateHandled?.()}>
          external create {externalCreatePreset}
        </button>
      ) : null}
    </div>
  ),
  SettingsAlert: ({ title, message }: { title: string; message: string }) => (
    <div>
      {title}:{message}
    </div>
  ),
  SettingsCategoryNav: ({
    categories,
    activeCategory,
    onSelect,
  }: {
    categories: Array<{ category: string; title: string }>;
    activeCategory: string;
    onSelect: (value: string) => void;
  }) => (
    <nav>
      {categories.map((category) => (
        <button
          key={category.category}
          type="button"
          aria-pressed={activeCategory === category.category}
          onClick={() => onSelect(category.category)}
        >
          {category.title}
        </button>
      ))}
    </nav>
  ),
  SettingsField: ({ item }: { item: { key: string } }) => <div>{item.key}</div>,
  SettingsLoading: () => <div>loading</div>,
  SettingsSectionCard: ({
    title,
    description,
    children,
  }: {
    title: string;
    description?: string;
    children: React.ReactNode;
  }) => (
    <section>
      <h2>{title}</h2>
      {description ? <p>{description}</p> : null}
      {children}
    </section>
  ),
}));

const baseCategories = [
  { category: 'system', title: 'System', description: '系统设置', displayOrder: 1, fields: [] },
  { category: 'base', title: 'Base', description: '基础配置', displayOrder: 2, fields: [] },
  { category: 'ai_model', title: 'AI', description: '模型配置', displayOrder: 3, fields: [] },
  { category: 'data_source', title: 'Data', description: '数据源配置', displayOrder: 4, fields: [] },
  { category: 'notification', title: 'Notification', description: '通知配置', displayOrder: 5, fields: [] },
  { category: 'agent', title: 'Agent', description: 'Agent 配置', displayOrder: 6, fields: [] },
  { category: 'quant', title: 'Quant', description: '量化引擎', displayOrder: 7, fields: [] },
];

type ConfigState = {
  categories: Array<{ category: string; title: string; description: string; displayOrder: number; fields: [] }>;
  itemsByCategory: Record<string, Array<Record<string, unknown>>>;
  issueByKey: Record<string, unknown[]>;
  activeCategory: string;
  setActiveCategory: typeof setActiveCategory;
  hasDirty: boolean;
  dirtyCount: number;
  toast: null;
  clearToast: typeof clearToast;
  isLoading: boolean;
  isSaving: boolean;
  loadError: null;
  saveError: null;
  retryAction: null;
  load: typeof load;
  retry: ReturnType<typeof vi.fn>;
  save: typeof save;
  saveExternalItems: typeof saveExternalItems;
  resetDraft: typeof resetDraft;
  setDraftValue: typeof setDraftValue;
  applyPartialUpdate: typeof applyPartialUpdate;
  adminUnlockToken: string | null;
  adminUnlockExpiresAt: number | null;
  isAdminUnlocked: boolean;
  setAdminUnlockSession: typeof setAdminUnlockSession;
  clearAdminUnlockSession: typeof clearAdminUnlockSession;
};

type ConfigOverride = Partial<ConfigState>;

function buildSystemConfigState(overrides: ConfigOverride = {}) {
  return {
    categories: baseCategories,
    itemsByCategory: {
      system: [
        {
          key: 'ADMIN_AUTH_ENABLED',
          value: 'true',
          rawValueExists: true,
          isMasked: false,
          rawEditable: false,
          uiVisibility: 'hidden',
          schema: {
            key: 'ADMIN_AUTH_ENABLED',
            category: 'system',
            dataType: 'boolean',
            uiControl: 'switch',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            rawEditable: false,
            uiVisibility: 'hidden',
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
        {
          key: 'SCHEDULE_ENABLED',
          value: 'true',
          rawValueExists: true,
          isMasked: false,
          rawEditable: true,
          uiVisibility: 'raw',
          schema: {
            key: 'SCHEDULE_ENABLED',
            category: 'system',
            dataType: 'boolean',
            uiControl: 'switch',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            rawEditable: true,
            uiVisibility: 'raw',
            options: [],
            validation: {},
            displayOrder: 2,
          },
        },
        {
          key: 'DEBUG',
          value: 'true',
          rawValueExists: true,
          isMasked: false,
          rawEditable: true,
          uiVisibility: 'raw',
          schema: {
            key: 'DEBUG',
            category: 'system',
            dataType: 'boolean',
            uiControl: 'switch',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            rawEditable: true,
            uiVisibility: 'raw',
            options: [],
            validation: {},
            displayOrder: 3,
          },
        },
        {
          key: 'HTTP_PROXY',
          value: 'http://proxy.example.com:8080',
          rawValueExists: true,
          isMasked: false,
          rawEditable: true,
          uiVisibility: 'raw',
          schema: {
            key: 'HTTP_PROXY',
            category: 'system',
            dataType: 'string',
            uiControl: 'text',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            rawEditable: true,
            uiVisibility: 'raw',
            options: [],
            validation: {},
            displayOrder: 4,
          },
        },
        {
          key: 'WEBUI_PORT',
          value: '5173',
          rawValueExists: true,
          isMasked: false,
          rawEditable: true,
          uiVisibility: 'raw',
          schema: {
            key: 'WEBUI_PORT',
            category: 'system',
            dataType: 'integer',
            uiControl: 'number',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            rawEditable: true,
            uiVisibility: 'raw',
            options: [],
            validation: {},
            displayOrder: 5,
          },
        },
        {
          key: 'WEBHOOK_VERIFY_SSL',
          value: 'false',
          rawValueExists: true,
          isMasked: false,
          rawEditable: true,
          uiVisibility: 'raw',
          schema: {
            key: 'WEBHOOK_VERIFY_SSL',
            category: 'system',
            dataType: 'boolean',
            uiControl: 'switch',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            rawEditable: true,
            uiVisibility: 'raw',
            options: [],
            validation: {},
            displayOrder: 6,
          },
        },
        {
          key: 'UNREGISTERED_VENDOR_API_KEY',
          value: 'masked-vendor-key',
          rawValueExists: true,
          isMasked: true,
          rawEditable: true,
          uiVisibility: 'raw',
          schema: {
            key: 'UNREGISTERED_VENDOR_API_KEY',
            category: 'uncategorized',
            dataType: 'string',
            uiControl: 'password',
            isSensitive: true,
            isRequired: false,
            isEditable: true,
            rawEditable: true,
            uiVisibility: 'raw',
            options: [],
            validation: {},
            displayOrder: 7,
          },
        },
      ],
      base: [
        {
          key: 'STOCK_LIST',
          value: 'SH600000',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'STOCK_LIST',
            category: 'base',
            dataType: 'string',
            uiControl: 'textarea',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
      ],
      ai_model: [
        {
          key: 'LLM_CHANNELS',
          value: 'primary',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'LLM_CHANNELS',
            category: 'ai_model',
            dataType: 'string',
            uiControl: 'textarea',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
      ],
      data_source: [
        {
          key: 'REALTIME_SOURCE_PRIORITY',
          value: 'finnhub,yahoo',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'REALTIME_SOURCE_PRIORITY',
            category: 'data_source',
            dataType: 'string',
            uiControl: 'text',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
        {
          key: 'FINNHUB_API_KEY',
          value: 'masked-finnhub-token',
          rawValueExists: true,
          isMasked: false,
          rawEditable: false,
          uiVisibility: 'curated',
          schema: {
            key: 'FINNHUB_API_KEY',
            category: 'data_source',
            dataType: 'string',
            uiControl: 'text',
            isSensitive: true,
            isRequired: false,
            isEditable: true,
            rawEditable: false,
            uiVisibility: 'curated',
            options: [],
            validation: {},
            displayOrder: 2,
          },
        },
      ],
      notification: [
        {
          key: 'WECHAT_WEBHOOK_URL',
          value: 'wechat-webhook-token',
          rawValueExists: true,
          isMasked: true,
          rawEditable: false,
          uiVisibility: 'hidden',
          schema: {
            key: 'WECHAT_WEBHOOK_URL',
            category: 'notification',
            dataType: 'string',
            uiControl: 'password',
            isSensitive: true,
            isRequired: false,
            isEditable: true,
            rawEditable: false,
            uiVisibility: 'hidden',
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
        {
          key: 'PUSHOVER_USER_KEY',
          value: 'pushover-key',
          rawValueExists: true,
          isMasked: true,
          rawEditable: false,
          uiVisibility: 'hidden',
          schema: {
            key: 'PUSHOVER_USER_KEY',
            category: 'notification',
            dataType: 'string',
            uiControl: 'password',
            isSensitive: true,
            isRequired: false,
            isEditable: true,
            rawEditable: false,
            uiVisibility: 'hidden',
            options: [],
            validation: {},
            displayOrder: 2,
          },
        },
        {
          key: 'NOTIFICATION_BATCH_SIZE',
          value: '10',
          rawValueExists: true,
          isMasked: false,
          rawEditable: true,
          uiVisibility: 'raw',
          schema: {
            key: 'NOTIFICATION_BATCH_SIZE',
            category: 'notification',
            dataType: 'integer',
            uiControl: 'number',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            rawEditable: true,
            uiVisibility: 'raw',
            options: [],
            validation: {},
            displayOrder: 3,
          },
        },
        {
          key: 'SLACK_CHANNEL_ID',
          value: 'ops-alerts',
          rawValueExists: true,
          isMasked: false,
          rawEditable: true,
          uiVisibility: 'raw',
          schema: {
            key: 'SLACK_CHANNEL_ID',
            category: 'notification',
            dataType: 'string',
            uiControl: 'text',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            rawEditable: true,
            uiVisibility: 'raw',
            options: [],
            validation: {},
            displayOrder: 4,
          },
        },
        {
          key: 'EMAIL_RECEIVERS',
          value: '',
          rawValueExists: false,
          isMasked: false,
          rawEditable: false,
          uiVisibility: 'curated',
          schema: {
            key: 'EMAIL_RECEIVERS',
            category: 'notification',
            dataType: 'array',
            uiControl: 'textarea',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            rawEditable: false,
            uiVisibility: 'curated',
            managedBy: 'notifications',
            options: [],
            validation: { multiValue: true },
            displayOrder: 5,
          },
        },
      ],
      agent: [
        {
          key: 'AGENT_ORCHESTRATOR_TIMEOUT_S',
          value: '600',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'AGENT_ORCHESTRATOR_TIMEOUT_S',
            category: 'agent',
            dataType: 'integer',
            uiControl: 'number',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
      ],
      quant: [
        {
          key: 'QUANT_DUCKDB_ENABLED',
          value: 'false',
          rawValueExists: true,
          isMasked: false,
          rawEditable: true,
          uiVisibility: 'advanced',
          schema: {
            key: 'QUANT_DUCKDB_ENABLED',
            category: 'quant',
            dataType: 'boolean',
            uiControl: 'switch',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            rawEditable: true,
            uiVisibility: 'advanced',
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
        {
          key: 'FLAKE8_INSTALLED',
          value: 'false',
          rawValueExists: true,
          isMasked: false,
          rawEditable: true,
          uiVisibility: 'advanced',
          schema: {
            key: 'FLAKE8_INSTALLED',
            category: 'quant',
            dataType: 'boolean',
            uiControl: 'switch',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            rawEditable: true,
            uiVisibility: 'advanced',
            options: [],
            validation: {},
            displayOrder: 2,
          },
        },
        {
          key: 'AKSHARE_INSTALLED',
          value: 'false',
          rawValueExists: true,
          isMasked: false,
          rawEditable: true,
          uiVisibility: 'advanced',
          schema: {
            key: 'AKSHARE_INSTALLED',
            category: 'quant',
            dataType: 'boolean',
            uiControl: 'switch',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            rawEditable: true,
            uiVisibility: 'advanced',
            options: [],
            validation: {},
            displayOrder: 3,
          },
        },
      ],
    },
    issueByKey: {},
    activeCategory: 'system',
    setActiveCategory,
    hasDirty: false,
    dirtyCount: 0,
    toast: null,
    clearToast,
    isLoading: false,
    isSaving: false,
    loadError: null,
    saveError: null,
    retryAction: null,
    load,
    retry: vi.fn(),
    save,
    saveExternalItems,
    resetDraft,
    setDraftValue,
    applyPartialUpdate,
    adminUnlockToken: 'unit-test-token',
    adminUnlockExpiresAt: Date.now() + 60_000,
    isAdminUnlocked: true,
    setAdminUnlockSession,
    clearAdminUnlockSession,
    ...overrides,
  };
}

async function withSystemSettingsPath(run: () => Promise<void> | void) {
  const previousPath = window.location.pathname;
  window.history.replaceState({}, '', '/settings/system');
  try {
    await run();
  } finally {
    window.history.replaceState({}, '', previousPath);
  }
}

async function openAiRoutingDrawer() {
  fireEvent.click(screen.getByRole('button', { name: '编辑任务路由' }));
  await waitFor(() => {
    expect(screen.getByRole('dialog', { name: '任务路由编辑' })).toBeInTheDocument();
  });
}

async function openAdvancedConfigDrawer() {
  fireEvent.click(screen.getByRole('button', { name: '打开高级设置' }));
  await waitFor(() => {
    expect(screen.getByRole('dialog', { name: '高级服务商 / 渠道编辑' })).toBeInTheDocument();
  });
  expect(screen.getByTestId('llm-provider-scope')).toHaveTextContent('');
}

function openMaintenancePanel(summaryLabel = '展开维护操作与日志入口') {
  const summary = screen.getByText(summaryLabel);
  const details = summary.closest('details');
  expect(details).not.toBeNull();
  expect(details).not.toHaveAttribute('open');
  fireEvent.click(summary.closest('summary') ?? summary);
  expect(details).toHaveAttribute('open');
}

function getMaintenancePanel(summaryLabel = '展开维护操作与日志入口') {
  const summary = screen.getByText(summaryLabel);
  return summary.closest('details');
}

function defaultVisibleText(element: HTMLElement) {
  const clone = element.cloneNode(true) as HTMLElement;
  clone.querySelectorAll('details:not([open])').forEach((details) => details.remove());
  return clone.textContent || '';
}

function expectNoDuckDBDefaultLeakage(element: HTMLElement) {
  const visibleText = defaultVisibleText(element);
  expect(visibleText).not.toContain('/Users/');
  expect(visibleText).not.toMatch(/\b(?:schema|token|api_key|webhook|authorization|bearer)\b/i);
  expect(visibleText).not.toMatch(/\b(?:Traceback|Stack trace|at\s+\S+\s+\(|File ".+", line \d+)\b/i);
}

async function openQuickProviderDrawer(providerName: string) {
  const providerKey = providerName === 'AIHubMix'
    ? 'aihubmix'
    : providerName === 'OpenAI'
      ? 'openai'
      : providerName === 'GLM / Zhipu'
        ? 'zhipu'
        : providerName.toLowerCase();
  const providerSection = screen.getByTestId('ai-provider-quick-section');
  const providerCard = within(providerSection).getByTestId(`ai-provider-card-${providerKey}`);
  fireEvent.click(within(providerCard as HTMLElement).getByRole('button', { name: '打开快速配置' }));
  await waitFor(() => {
    expect(screen.getByRole('dialog', { name: `${providerName} 快速配置` })).toBeInTheDocument();
  });
  return providerCard as HTMLElement;
}

function buildAiConfigItem(key: string, value: string) {
  return {
    key,
    value,
    rawValueExists: value.trim().length > 0,
    isMasked: false,
    schema: {
      key,
      category: 'ai_model',
      dataType: 'string',
      uiControl: 'text',
      isSensitive: /KEY/i.test(key),
      isRequired: false,
      isEditable: true,
      options: [],
      validation: {},
      displayOrder: 1,
    },
  };
}

function buildDataSourceConfigItem(key: string, value: string) {
  return {
    key,
    value,
    rawValueExists: value.trim().length > 0,
    isMasked: /KEY/i.test(key),
    schema: {
      key,
      category: 'data_source',
      dataType: 'string',
      uiControl: 'text',
      isSensitive: /KEY/i.test(key),
      isRequired: false,
      isEditable: true,
      options: [],
      validation: {},
      displayOrder: 1,
    },
  };
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    llmEditorModuleLoad.reset();
    dataSourceDrawerModuleLoad.reset();
    window.history.replaceState({}, '', '/');
    window.innerWidth = 1280;
    window.dispatchEvent(new Event('resize'));
    window.sessionStorage.clear();
    useAuthMock.mockReturnValue({
      authEnabled: true,
      passwordChangeable: true,
      setupState: 'enabled',
      refreshStatus,
    });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState());
    testLLMChannel.mockResolvedValue({
      success: true,
      message: 'ok',
      resolvedModel: 'gemini/gemini-2.5-flash',
      latencyMs: 123,
    });
    testCustomDataSource.mockResolvedValue({
      success: true,
      message: 'ok',
      error: null,
      statusCode: 200,
      checkedUrl: 'https://demo.example.com/v1',
      latencyMs: 120,
    });
    testBuiltinDataSource.mockResolvedValue({
      provider: 'fmp',
      ok: true,
      status: 'success',
      checkedAt: '2026-04-30T00:00:00Z',
      durationMs: 128,
      keyMasked: 'fmp-...-key',
      checks: [
        {
          name: 'quote',
          endpoint: '/api/v3/quote/MSFT',
          ok: true,
          httpStatus: 200,
          durationMs: 60,
          errorType: null,
          message: 'quote endpoint 可用。',
        },
      ],
      summary: 'FMP 连接成功：quote endpoint 可用。',
      suggestion: '无需处理。',
    });
    resetRuntimeCaches.mockResolvedValue({
      success: true,
      action: 'reset_runtime_caches',
      message: '运行时 provider/search 缓存已重置。',
      cleared: ['data_fetcher_manager', 'search_service'],
    });
    factoryResetSystem.mockResolvedValue({
      success: true,
      action: 'factory_reset_system',
      message: 'Factory reset completed',
      cleared: ['non_bootstrap_users', 'user_sessions', 'analysis_history'],
      preserved: ['bootstrap_admin_access', 'system_configuration', 'execution_logs'],
      counts: {
        users: 2,
        sessions: 3,
        analysisHistory: 4,
      },
      confirmationPhrase: 'FACTORY RESET',
    });
    getDuckDBHealth.mockResolvedValue({
      enabled: false,
      available: true,
      databasePath: 'wolfystock.duckdb',
      parquetRoot: 'parquet',
      version: '1.2.0',
      error: null,
      schemaInitialized: false,
      status: 'disabled',
      engine: 'duckdb',
    });
    getDuckDBCoverage.mockResolvedValue({
      status: 'disabled',
      engine: 'duckdb',
      enabled: false,
      databasePath: 'wolfystock.duckdb',
      totalOhlcvRows: 0,
      totalFactorRows: 0,
      symbolCount: 0,
      minTradeDate: null,
      maxTradeDate: null,
      latestFactorDate: null,
      symbols: [],
      emptyReason: 'DuckDB quant engine is disabled',
      error: null,
    });
    initDuckDB.mockResolvedValue({
      status: 'disabled',
      engine: 'duckdb',
      schemaInitialized: false,
      error: 'DuckDB quant engine is disabled',
    });
    runDuckDBBenchmark.mockResolvedValue({
      status: 'disabled',
      engine: 'duckdb',
      elapsedMs: 0,
      durationMs: 0,
      ohlcvRows: 0,
      factorRows: 0,
      rowsScanned: 0,
      symbolsScanned: 0,
      symbolCount: 0,
      dateCount: 0,
      factorCount: 0,
      queryType: 'factor_daily_top_scores',
      dataMode: 'disabled',
      startDate: null,
      endDate: null,
      topResults: [],
      error: null,
    });
    getDuckDBFactorSnapshot.mockResolvedValue({
      status: 'disabled',
      engine: 'duckdb',
      dataMode: 'disabled',
      durationMs: 0,
      rowCount: 0,
      coverage: {
        requestedSymbols: 2,
        coveredSymbols: 0,
        missingSymbols: 2,
        sufficientSymbols: 0,
        rowCount: 0,
        minFactorDate: null,
        maxFactorDate: null,
      },
      factorDates: [],
      missingSymbols: ['AAPL', 'MSFT'],
      factors: ['return_1d', 'factor_score'],
      snapshots: [],
      warnings: ['DuckDB quant engine is disabled'],
      error: null,
    });
    validateDuckDBFactorPath.mockResolvedValue({
      status: 'disabled',
      engine: 'duckdb',
      dataMode: 'disabled',
      durationMs: 0,
      rowCount: 0,
      coverage: {
        requestedSymbols: 2,
        coveredSymbols: 0,
        missingSymbols: 2,
        sufficientSymbols: 0,
        rowCount: 0,
        minFactorDate: null,
        maxFactorDate: null,
      },
      factorDates: [],
      missingSymbols: ['AAPL', 'MSFT'],
      insufficientSymbols: [],
      warnings: ['DuckDB quant engine is disabled'],
      error: null,
    });
    compareDuckDBRuntimeContext.mockResolvedValue({
      status: 'disabled',
      engine: 'duckdb',
      dataMode: 'disabled',
      durationMs: 0,
      runtimeContexts: ['scanner'],
      coverage: {
        requestedSymbols: 2,
        coveredSymbols: 0,
        missingSymbols: 2,
        sufficientSymbols: 0,
        rowCount: 0,
        minFactorDate: null,
        maxFactorDate: null,
      },
      diagnostics: {
        productionRuntimeChanged: false,
        diagnosticOnly: true,
        missingSymbols: ['AAPL', 'MSFT'],
        insufficientSymbols: [],
        scannerSymbols: ['AAPL', 'MSFT'],
        backtestSymbols: [],
      },
      snapshots: [],
      warnings: [],
      error: null,
    });
    buildDuckDBFactors.mockResolvedValue({
      status: 'disabled',
      engine: 'duckdb',
      ohlcvRows: 0,
      factorRows: 0,
      factorCount: 0,
      durationMs: 0,
      error: 'DuckDB quant engine is disabled',
    });
  });

  it('renders category navigation and auth settings modules', async () => {
    const { container } = render(<SettingsPage />);

    expect(screen.getByTestId('settings-bento-page')).toHaveAttribute('data-bento-surface', 'true');
    expect(screen.getByTestId('settings-bento-page')).toHaveClass('flex-1', 'flex', 'w-full', 'h-full', 'min-h-0', 'overflow-hidden');
    expect(screen.queryByTestId('settings-bento-hero')).not.toBeInTheDocument();
    expect(screen.getByTestId('settings-workspace')).toHaveClass('w-full', 'max-w-none', 'flex-1', 'min-h-0', 'gap-8', 'px-6', 'md:px-8', 'xl:px-12');
    expect(screen.getByTestId('settings-workspace')).not.toHaveClass('max-w-[1600px]', 'mx-auto', 'px-4');
    expect(container.querySelectorAll('main')).toHaveLength(0);
    expect(screen.queryByRole('heading', { name: '系统控制面' })).not.toBeInTheDocument();
    expect(screen.queryByText('这里是系统级设置，不是个人偏好页。保存会影响当前实例的全局运行路径。')).not.toBeInTheDocument();
    expect(await screen.findByText('认证与登录保护')).toBeInTheDocument();
    expect(await screen.findByText('修改密码')).toBeInTheDocument();
    expect(load).toHaveBeenCalled();

    fireEvent.click(screen.getByTestId('settings-bento-drawer-trigger'));
    expect(await screen.findByTestId('settings-bento-drawer')).toBeInTheDocument();
    expect(screen.getByRole('dialog', { name: '系统控制面' })).toBeInTheDocument();
  });

  it('uses non-green semantic toggles for runtime visibility controls', async () => {
    render(<SettingsPage />);

    const runtimeSection = await screen.findByRole('heading', { name: zh('settings.runtimeSummaryVisibilityTitle') });
    fireEvent.click(within(runtimeSection.closest('section') as HTMLElement).getByRole('button', { name: zh('settings.dataSourceManageAction') }));

    const offButton = await screen.findByRole('button', { name: zh('settings.runtimeSummaryVisibleOff') });
    expect(offButton).toHaveClass('bg-white', 'text-black');
    expect(offButton).not.toHaveClass('bg-emerald-500');
  });

  it('renders the admin control plane directly without a second unlock wall', async () => {
    window.sessionStorage.clear();
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'system',
      hasDirty: false,
      adminUnlockToken: null,
      adminUnlockExpiresAt: null,
    }));

    await withSystemSettingsPath(async () => {
      render(<SettingsPage />);

      expect(await screen.findByRole('heading', { name: '全局控制面概览' })).toBeInTheDocument();
      expect(screen.getByTestId('settings-bento-hero')).toBeInTheDocument();
      expect(screen.getByTestId('settings-bento-hero-dirty-value')).toBeInTheDocument();
      expect(screen.getAllByText(zh('settings.controlPlaneStatProviders'))).toHaveLength(1);
      expect(screen.getAllByText(zh('settings.controlPlaneStatDataSources'))).toHaveLength(1);
      expect(screen.getAllByText('当前已进入全局系统控制面').length).toBeGreaterThan(0);
      expect(screen.getByText('展开维护操作与日志入口')).toBeInTheDocument();
      expect(getMaintenancePanel()).not.toHaveAttribute('open');
      expect(screen.queryByText('认证与登录保护')).not.toBeInTheDocument();
      expect(screen.queryByText('修改密码')).not.toBeInTheDocument();
      expect(screen.queryByText('锁定状态下仅可浏览，无法修改系统级配置。')).not.toBeInTheDocument();
    });
  });

  it('renders a compact Chinese system health summary with optional disabled states', async () => {
    await withSystemSettingsPath(async () => {
      render(<SettingsPage />);

      expect(await screen.findByTestId('system-health-summary')).toHaveTextContent('系统健康');
      expect(screen.getByTestId('system-health-summary')).toHaveTextContent('可用');
      expect(screen.getByTestId('system-health-summary')).toHaveTextContent('需关注');
      expect(screen.getByTestId('system-health-summary')).toHaveTextContent('未配置');
      expect(screen.getByTestId('system-health-summary')).toHaveTextContent('暂不可用');
      expect(screen.getByTestId('system-health-summary')).toHaveTextContent('最近检查');
      expect(screen.getByTestId('system-health-summary')).toHaveTextContent('环境状态');

      const subsystemCards = screen.getByTestId('system-subsystem-cards');
      expect(subsystemCards).toHaveTextContent('数据源');
      expect(subsystemCards).toHaveTextContent('市场总览');
      expect(subsystemCards).toHaveTextContent('扫描器');
      expect(subsystemCards).toHaveTextContent('回测');
      expect(subsystemCards).toHaveTextContent('投资组合');
      expect(subsystemCards).toHaveTextContent('AI 决策');
      expect(subsystemCards).toHaveTextContent('通知');
      expect(subsystemCards).toHaveTextContent('DuckDB 量化引擎');
      expect(subsystemCards).toHaveTextContent('日志中心');
      expect(subsystemCards).toHaveTextContent('量化加速未启用；默认 Python 路径继续可用');
      expect(subsystemCards).toHaveTextContent('可选代码检查');
      expect(subsystemCards).toHaveTextContent('flake8 未安装；不影响运行时分析');
      expect(subsystemCards).toHaveTextContent('A股扩展数据源');
      expect(subsystemCards).toHaveTextContent('akshare 未安装；外部数据源与回退路径继续可用');
      expect(subsystemCards).not.toHaveTextContent('failed');
      expect(subsystemCards).not.toHaveTextContent('false');
    });
  });

  it('lays out the system overview as a wide operator dashboard with secondary technical zones collapsed', async () => {
    await withSystemSettingsPath(async () => {
      render(<SettingsPage />);

      expect(await screen.findByTestId('system-operator-dashboard')).toHaveClass(
        'xl:grid-cols-[minmax(0,1.38fr)_minmax(20rem,0.62fr)]',
      );
      expect(screen.getByTestId('settings-main-content')).toHaveClass('max-w-none');
      expect(screen.getByTestId('system-operator-dashboard')).toHaveTextContent('系统当前能否安全运行');
      expect(screen.getByTestId('system-priority-settings')).toHaveTextContent('重要设置组');

      const duckdbDisclosure = screen.getByTestId('system-duckdb-disclosure');
      const dangerZone = screen.getByTestId('system-danger-zone');
      expect(duckdbDisclosure).not.toHaveAttribute('open');
      expect(dangerZone).not.toHaveAttribute('open');
      expect(dangerZone).toHaveTextContent('危险系统动作');
      expect(dangerZone).toHaveTextContent('确认后才执行');
    });
  });

  it('renders the DuckDB panel as optional and blocks write actions while disabled', async () => {
    await withSystemSettingsPath(async () => {
      render(<SettingsPage />);

      const panel = await screen.findByTestId('duckdb-quant-panel');
      expect(panel).toHaveTextContent('DuckDB 诊断');
      expect(panel).toHaveTextContent('未启用');
      expect(panel).toHaveTextContent('可选能力');
      expect(panel).toHaveTextContent('未写入文件');
      expect(panel).toHaveTextContent('诊断用途，不影响生产运行路径');
      expect(panel).toHaveTextContent('OHLCV 行');
      expect(panel).toHaveTextContent('因子行');
      expect(panel).toHaveTextContent('productionRuntimeChanged=false · 诊断专用');
      expect(within(panel).getByRole('button', { name: '初始化' })).toBeDisabled();
      expect(within(panel).getByRole('button', { name: '显式构建因子' })).toBeDisabled();
      expect(within(panel).getByText('开发者细节').closest('details')).not.toHaveAttribute('open');
      expectNoDuckDBDefaultLeakage(panel);
      expect(getDuckDBHealth).toHaveBeenCalledTimes(1);
      expect(getDuckDBCoverage).toHaveBeenCalledTimes(1);
      expect(initDuckDB).not.toHaveBeenCalled();
      expect(runDuckDBBenchmark).not.toHaveBeenCalled();
      expect(getDuckDBFactorSnapshot).not.toHaveBeenCalled();
      expect(validateDuckDBFactorPath).not.toHaveBeenCalled();
      expect(compareDuckDBRuntimeContext).not.toHaveBeenCalled();
      expect(buildDuckDBFactors).not.toHaveBeenCalled();
    });
  });

  it('renders DuckDB coverage, benchmark, snapshot, and validation summaries after explicit clicks', async () => {
    getDuckDBHealth.mockResolvedValue({
      enabled: true,
      available: true,
      databasePath: '/Users/tester/private/quant/wolfystock.duckdb',
      parquetRoot: '/Users/tester/private/quant/parquet',
      version: '1.2.0',
      error: null,
      schemaInitialized: true,
      status: 'ok',
      engine: 'duckdb',
    });
    getDuckDBCoverage.mockResolvedValue({
      status: 'ok',
      engine: 'duckdb',
      enabled: true,
      databasePath: '/Users/tester/private/quant/wolfystock.duckdb',
      totalOhlcvRows: 44,
      totalFactorRows: 22,
      symbolCount: 2,
      minTradeDate: '2026-01-01',
      maxTradeDate: '2026-01-22',
      latestFactorDate: '2026-01-22',
      symbols: [
        { symbol: 'AAPL', ohlcvRows: 22, minTradeDate: '2026-01-01', maxTradeDate: '2026-01-22', factorRows: 11, latestFactorDate: '2026-01-22' },
        { symbol: 'MSFT', ohlcvRows: 22, minTradeDate: '2026-01-01', maxTradeDate: '2026-01-22', factorRows: 11, latestFactorDate: '2026-01-22' },
      ],
      emptyReason: null,
      error: null,
    });
    runDuckDBBenchmark.mockResolvedValue({
      status: 'ok',
      engine: 'duckdb',
      elapsedMs: 8,
      durationMs: 8,
      ohlcvRows: 44,
      factorRows: 22,
      rowsScanned: 22,
      symbolsScanned: 2,
      symbolCount: 2,
      dateCount: 22,
      factorCount: 11,
      queryType: 'factor_daily_top_scores',
      dataMode: 'real',
      startDate: '2026-01-01',
      endDate: '2026-01-22',
      topResults: [{ symbol: 'AAPL', tradeDate: '2026-01-22', factorScore: 0.88 }],
      error: null,
    });
    getDuckDBFactorSnapshot.mockResolvedValue({
      status: 'ok',
      engine: 'duckdb',
      dataMode: 'real',
      durationMs: 4,
      rowCount: 4,
      coverage: { requestedSymbols: 2, coveredSymbols: 2, missingSymbols: 0, sufficientSymbols: 2, rowCount: 4, minFactorDate: '2026-01-01', maxFactorDate: '2026-01-02' },
      factorDates: ['2026-01-01', '2026-01-02'],
      missingSymbols: [],
      factors: ['return_1d', 'factor_score'],
      snapshots: [],
      warnings: [],
      error: null,
    });
    validateDuckDBFactorPath.mockResolvedValue({
      status: 'ok',
      engine: 'duckdb',
      dataMode: 'real',
      durationMs: 3,
      rowCount: 4,
      coverage: { requestedSymbols: 2, coveredSymbols: 2, missingSymbols: 0, sufficientSymbols: 2, rowCount: 4, minFactorDate: '2026-01-01', maxFactorDate: '2026-01-02' },
      factorDates: ['2026-01-01', '2026-01-02'],
      missingSymbols: [],
      insufficientSymbols: [],
      warnings: [],
      error: null,
    });
    compareDuckDBRuntimeContext.mockResolvedValue({
      status: 'ok',
      engine: 'duckdb',
      dataMode: 'real',
      durationMs: 5,
      runtimeContexts: ['scanner'],
      coverage: { requestedSymbols: 2, coveredSymbols: 2, missingSymbols: 0, sufficientSymbols: 2, rowCount: 4, minFactorDate: '2026-01-01', maxFactorDate: '2026-01-02' },
      diagnostics: { productionRuntimeChanged: false, diagnosticOnly: true, scannerSymbols: ['AAPL', 'MSFT'], backtestSymbols: [] },
      snapshots: [],
      warnings: [],
      error: null,
    });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        quant: buildSystemConfigState().itemsByCategory.quant.map((item) => (
          item.key === 'QUANT_DUCKDB_ENABLED' ? { ...item, value: 'true' } : item
        )),
      },
    }));

    await withSystemSettingsPath(async () => {
      render(<SettingsPage />);

      const panel = await screen.findByTestId('duckdb-quant-panel');
      expect(panel).toHaveTextContent('已启用');
      expect(panel).toHaveTextContent('写入需显式点击');
      await waitFor(() => expect(panel).toHaveTextContent('44'));
      expect(panel).toHaveTextContent('44');
      expect(panel).toHaveTextContent('22');
      expect(panel).toHaveTextContent('标的 2');
      expect(panel).toHaveTextContent('2026-01-01 -> 2026-01-22');
      expect(panel).toHaveTextContent('最新 2026-01-22');
      expect(panel).toHaveTextContent('AAPL:22/11');
      expect(panel).toHaveTextContent('已脱敏 / 截断');
      expectNoDuckDBDefaultLeakage(panel);
      expect(within(panel).getByRole('button', { name: '初始化' })).not.toBeDisabled();
      expect(initDuckDB).not.toHaveBeenCalled();
      expect(buildDuckDBFactors).not.toHaveBeenCalled();
      expect(runDuckDBBenchmark).not.toHaveBeenCalled();
      expect(getDuckDBFactorSnapshot).not.toHaveBeenCalled();
      expect(validateDuckDBFactorPath).not.toHaveBeenCalled();
      expect(compareDuckDBRuntimeContext).not.toHaveBeenCalled();

      fireEvent.click(within(panel).getByRole('button', { name: '小样本基准' }));
      await waitFor(() => expect(runDuckDBBenchmark).toHaveBeenCalledWith({ symbolLimit: 2 }));
      expect(await within(panel).findByText(/22 行 · 2 标的/)).toBeInTheDocument();
      expect(initDuckDB).not.toHaveBeenCalled();
      expect(buildDuckDBFactors).not.toHaveBeenCalled();

      fireEvent.click(within(panel).getByRole('button', { name: '因子快照' }));
      await waitFor(() => expect(getDuckDBFactorSnapshot).toHaveBeenCalledWith({
        symbols: ['AAPL', 'MSFT'],
        lookbackDays: 5,
        factors: ['return_1d', 'factor_score'],
      }));
      expect(await within(panel).findByText(/正常 · 4 行 · 缺失 0/)).toBeInTheDocument();
      expect(initDuckDB).not.toHaveBeenCalled();
      expect(buildDuckDBFactors).not.toHaveBeenCalled();

      fireEvent.click(within(panel).getByRole('button', { name: '路径校验' }));
      await waitFor(() => expect(validateDuckDBFactorPath).toHaveBeenCalledWith({
        symbols: ['AAPL', 'MSFT'],
        minFactorRows: 1,
      }));
      expect(await within(panel).findByText(/正常 · 覆盖 2\/2 · 不足 0/)).toBeInTheDocument();
      expect(initDuckDB).not.toHaveBeenCalled();
      expect(buildDuckDBFactors).not.toHaveBeenCalled();

      fireEvent.click(within(panel).getByRole('button', { name: '运行比较' }));
      await waitFor(() => expect(compareDuckDBRuntimeContext).toHaveBeenCalledWith({
        symbols: ['AAPL', 'MSFT'],
        scannerSnapshot: { AAPL: { score: 0 }, MSFT: { score: 0 } },
      }));
      expect(await within(panel).findByText('productionRuntimeChanged=false · 诊断专用')).toBeInTheDocument();
      expect(initDuckDB).not.toHaveBeenCalled();
      expect(buildDuckDBFactors).not.toHaveBeenCalled();
    });
  });

  it('keeps DuckDB developer details collapsed and does not leak raw absolute paths by default', async () => {
    getDuckDBHealth.mockResolvedValue({
      enabled: false,
      available: true,
      databasePath: '/Users/tester/private/wolfystock.duckdb',
      parquetRoot: '/Users/tester/private/parquet',
      version: '1.2.0',
      error: null,
      schemaInitialized: false,
      status: 'disabled',
      engine: 'duckdb',
    });
    getDuckDBCoverage.mockResolvedValue({
      status: 'disabled',
      engine: 'duckdb',
      enabled: false,
      databasePath: '/Users/tester/private/wolfystock.duckdb',
      totalOhlcvRows: 0,
      totalFactorRows: 0,
      symbolCount: 0,
      minTradeDate: null,
      maxTradeDate: null,
      latestFactorDate: null,
      symbols: [],
      emptyReason: 'DuckDB quant engine is disabled',
      error: null,
    });

    await withSystemSettingsPath(async () => {
      render(<SettingsPage />);

      const panel = await screen.findByTestId('duckdb-quant-panel');
      const duckdbDetails = within(panel).getByText('开发者细节').closest('details');
      expect(duckdbDetails).not.toBeNull();
      expect(duckdbDetails).not.toHaveAttribute('open');
      expectNoDuckDBDefaultLeakage(panel);
    });
  });

  it('renders unavailable DuckDB diagnostics without exposing raw stack or path text by default', async () => {
    getDuckDBHealth.mockResolvedValue({
      enabled: true,
      available: false,
      databasePath: '/Users/tester/private/quant/wolfystock.duckdb',
      parquetRoot: '/Users/tester/private/quant/parquet',
      version: null,
      error: 'Traceback: token api_key schema webhook authorization bearer at /Users/tester/private/service.py:42',
      schemaInitialized: false,
      status: 'unavailable',
      engine: 'duckdb',
    });
    getDuckDBCoverage.mockResolvedValue({
      status: 'unavailable',
      engine: 'duckdb',
      enabled: true,
      databasePath: '/Users/tester/private/quant/wolfystock.duckdb',
      totalOhlcvRows: 0,
      totalFactorRows: 0,
      symbolCount: 0,
      minTradeDate: null,
      maxTradeDate: null,
      latestFactorDate: null,
      symbols: [],
      emptyReason: 'DuckDB 暂不可用，请查看开发者细节',
      error: 'Stack trace: File "/Users/tester/private/service.py", line 42, in token_handler',
    });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        quant: buildSystemConfigState().itemsByCategory.quant.map((item) => (
          item.key === 'QUANT_DUCKDB_ENABLED' ? { ...item, value: 'true' } : item
        )),
      },
    }));

    await withSystemSettingsPath(async () => {
      render(<SettingsPage />);

      const panel = await screen.findByTestId('duckdb-quant-panel');
      expect(panel).toHaveTextContent('暂不可用');
      expect(panel).toHaveTextContent('DuckDB 暂不可用，请查看开发者细节');
      const duckdbDetails = within(panel).getByText('开发者细节').closest('details');
      expect(duckdbDetails).not.toBeNull();
      expect(duckdbDetails).not.toHaveAttribute('open');
      expectNoDuckDBDefaultLeakage(panel);
      expect(runDuckDBBenchmark).not.toHaveBeenCalled();
      expect(getDuckDBFactorSnapshot).not.toHaveBeenCalled();
      expect(validateDuckDBFactorPath).not.toHaveBeenCalled();
      expect(compareDuckDBRuntimeContext).not.toHaveBeenCalled();
      expect(initDuckDB).not.toHaveBeenCalled();
      expect(buildDuckDBFactors).not.toHaveBeenCalled();
    });
  });

  it('does not auto-run DuckDB init or factor build on render and keeps writes explicit when enabled', async () => {
    getDuckDBHealth.mockResolvedValue({
      enabled: true,
      available: true,
      databasePath: 'wolfystock.duckdb',
      parquetRoot: 'parquet',
      version: '1.2.0',
      error: null,
      schemaInitialized: true,
      status: 'ok',
      engine: 'duckdb',
    });
    getDuckDBCoverage.mockResolvedValue({
      status: 'empty',
      engine: 'duckdb',
      enabled: true,
      databasePath: 'wolfystock.duckdb',
      totalOhlcvRows: 0,
      totalFactorRows: 0,
      symbolCount: 0,
      minTradeDate: null,
      maxTradeDate: null,
      latestFactorDate: null,
      symbols: [],
      emptyReason: 'No OHLCV or factor rows have been ingested',
      error: null,
    });
    initDuckDB.mockResolvedValue({ status: 'ok', engine: 'duckdb', schemaInitialized: true, error: null });
    buildDuckDBFactors.mockResolvedValue({ status: 'ok', engine: 'duckdb', ohlcvRows: 4, factorRows: 4, factorCount: 11, durationMs: 3, error: null });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        quant: buildSystemConfigState().itemsByCategory.quant.map((item) => (
          item.key === 'QUANT_DUCKDB_ENABLED' ? { ...item, value: 'true' } : item
        )),
      },
    }));

    await withSystemSettingsPath(async () => {
      render(<SettingsPage />);

      const panel = await screen.findByTestId('duckdb-quant-panel');
      expect(initDuckDB).not.toHaveBeenCalled();
      expect(buildDuckDBFactors).not.toHaveBeenCalled();

      fireEvent.click(within(panel).getByRole('button', { name: '初始化' }));
      await waitFor(() => expect(initDuckDB).toHaveBeenCalledTimes(1));

      fireEvent.click(within(panel).getByRole('button', { name: '显式构建因子' }));
      await waitFor(() => expect(buildDuckDBFactors).toHaveBeenCalledWith({ symbols: ['AAPL', 'MSFT'] }));
    });
  });

  it('keeps secrets and raw diagnostics collapsed in the system health overview', async () => {
    await withSystemSettingsPath(async () => {
      render(<SettingsPage />);

      expect(await screen.findByText('原始诊断')).toBeInTheDocument();
      const developerDetails = screen.getAllByText('开发者细节')
        .map((item) => item.closest('details'))
        .find((details) => details?.textContent?.includes('原始诊断'));
      expect(developerDetails).not.toBeNull();
      expect(developerDetails).not.toHaveAttribute('open');
      expect(screen.queryByText('masked-vendor-key')).not.toBeInTheDocument();
      expect(screen.queryByText('wechat-webhook-token')).not.toBeInTheDocument();
      expect(screen.queryByText('pushover-key')).not.toBeInTheDocument();
    });
  });

  it('mounts only one primary panel at a time and keeps the system overview isolated by default', async () => {
    const previousPath = window.location.pathname;
    window.history.replaceState({}, '', '/settings/system');

    try {
      render(<SettingsPage />);

      expect(await screen.findByRole('heading', { name: zh('settings.controlPlaneTitle') })).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: zh('settings.runtimeSummaryVisibilityTitle') })).not.toBeInTheDocument();
      expect(screen.getByTestId('settings-main-panel')).toHaveClass(
        'overflow-y-auto',
        '[&::-webkit-scrollbar]:hidden',
        '[-ms-overflow-style:none]',
        '[scrollbar-width:none]',
      );

      fireEvent.click(screen.getByRole('button', { name: /数据源/ }));

      expect(await screen.findByRole('heading', { name: '数据源配置' })).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: zh('settings.controlPlaneTitle') })).not.toBeInTheDocument();
    } finally {
      window.history.replaceState({}, '', previousPath);
    }
  });

  it('keeps the admin control plane focused on global domains without personal notification settings', async () => {
    render(<SettingsPage />);

    expect(await screen.findByText('全局控制面概览')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '通知与告警' })).not.toBeInTheDocument();
    expect(screen.queryByText('个人通知渠道')).not.toBeInTheDocument();
  });

  it('confirms and runs bounded admin maintenance actions at action level', async () => {
    await withSystemSettingsPath(async () => {
      render(<SettingsPage />);

      openMaintenancePanel();
      fireEvent.click(screen.getByRole('button', { name: '重置运行时缓存' }));

      expect(await screen.findByText('确认重置运行时缓存')).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: '确认执行' }));

      await waitFor(() => {
        expect(resetRuntimeCaches).toHaveBeenCalledTimes(1);
      });
      await waitFor(() => {
        expect(screen.getByText(/成功:运行时 provider\/search 缓存已重置。/)).toBeInTheDocument();
      });
    });
  });

  it('separates safe maintenance from factory reset and requires a typed phrase before destructive execution', async () => {
    await withSystemSettingsPath(async () => {
      render(<SettingsPage />);

      openMaintenancePanel();
      expect(screen.getByText('维护操作')).toBeInTheDocument();
      expect(screen.getByText('工厂重置 / 系统初始化')).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: '执行工厂重置' }));

      expect(await screen.findByText('确认工厂重置')).toBeInTheDocument();
      const confirmButton = screen.getByRole('button', { name: '确认执行' });
      expect(confirmButton).toBeDisabled();

      fireEvent.change(screen.getByLabelText('输入确认短语'), { target: { value: 'WRONG' } });
      expect(confirmButton).toBeDisabled();

      fireEvent.change(screen.getByLabelText('输入确认短语'), { target: { value: 'FACTORY RESET' } });
      expect(confirmButton).not.toBeDisabled();

      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(factoryResetSystem).toHaveBeenCalledWith({ confirmationPhrase: 'FACTORY RESET' });
      });
    });
  });

  it('keeps maintenance and destructive actions out of the primary control-plane surface until expanded', async () => {
    await withSystemSettingsPath(async () => {
      render(<SettingsPage />);

      expect(await screen.findByRole('heading', { name: '全局控制面概览' })).toBeInTheDocument();
      expect(screen.getByText('展开维护操作与日志入口')).toBeInTheDocument();
      expect(getMaintenancePanel()).not.toHaveAttribute('open');

      openMaintenancePanel();

      expect(getMaintenancePanel()).toHaveAttribute('open');
      expect(screen.getByRole('button', { name: '查看系统执行日志' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '重置运行时缓存' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '执行工厂重置' })).toBeInTheDocument();
    });
  });

  it('resets local drafts from the page header button', () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ hasDirty: true, dirtyCount: 2 }));

    render(<SettingsPage />);

    // Clear the initial load call from useEffect
    vi.clearAllMocks();

    fireEvent.click(screen.getByRole('button', { name: '重置' }));

    // Reset should call resetDraft and NOT call load
    expect(resetDraft).toHaveBeenCalledTimes(1);
    expect(load).not.toHaveBeenCalled();
  });

  it('hides unavailable deep research and event monitor fields from the agent category', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'agent',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        agent: [
          {
            key: 'AGENT_ORCHESTRATOR_TIMEOUT_S',
            value: '600',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'AGENT_ORCHESTRATOR_TIMEOUT_S',
              category: 'agent',
              dataType: 'integer',
              uiControl: 'number',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 1,
            },
          },
          {
            key: 'AGENT_DEEP_RESEARCH_BUDGET',
            value: '30000',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'AGENT_DEEP_RESEARCH_BUDGET',
              category: 'agent',
              dataType: 'integer',
              uiControl: 'number',
              isSensitive: false,
              isRequired: false,
              isEditable: false,
              options: [],
              validation: {},
              displayOrder: 2,
            },
          },
          {
            key: 'AGENT_EVENT_MONITOR_ENABLED',
            value: 'false',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'AGENT_EVENT_MONITOR_ENABLED',
              category: 'agent',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: false,
              options: [],
              validation: {},
              displayOrder: 3,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    fireEvent.click(screen.getByTestId('raw-fields-drawer-trigger'));
    const drawer = await screen.findByRole('dialog', { name: zh('settings.currentCategory') });
    expect(within(drawer).getByText('AGENT_ORCHESTRATOR_TIMEOUT_S')).toBeInTheDocument();
    expect(within(drawer).queryByText('AGENT_DEEP_RESEARCH_BUDGET')).not.toBeInTheDocument();
    expect(within(drawer).queryByText('AGENT_EVENT_MONITOR_ENABLED')).not.toBeInTheDocument();
  });

  it('reset button semantic: discards local changes without network request', () => {
    // Simulate user has unsaved drafts
    const dirtyState = buildSystemConfigState({
      hasDirty: true,
      dirtyCount: 2,
    });

    useSystemConfigMock.mockReturnValue(dirtyState);

    render(<SettingsPage />);

    // Clear initial useEffect load call
    vi.clearAllMocks();

    // Click reset button
    fireEvent.click(screen.getByRole('button', { name: '重置' }));

    // Verify semantic: reset should only discard local changes
    // It should NOT trigger a network load
    expect(resetDraft).toHaveBeenCalledTimes(1);
    expect(load).not.toHaveBeenCalled();
    expect(save).not.toHaveBeenCalled();
  });

  it('keeps base raw fields behind a drawer trigger while keeping smart import visible', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'base' }));

    render(<SettingsPage />);

    expect(screen.getByRole('button', { name: 'merge stock list' })).toBeInTheDocument();
    expect(screen.queryByText('STOCK_LIST')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('raw-fields-drawer-trigger'));
    expect(await screen.findByText('STOCK_LIST')).toBeInTheDocument();
  });

  it('keeps auth-owned keys out of the system raw drawer while safe runtime keys remain editable', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'system' }));

    render(<SettingsPage />);

    expect(await screen.findByText('认证与登录保护')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('raw-fields-drawer-trigger'));

    const drawer = await screen.findByRole('dialog', { name: zh('settings.rawFieldsSectionTitle') });
    expect(within(drawer).queryByText('ADMIN_AUTH_ENABLED')).not.toBeInTheDocument();
    expect(within(drawer).queryByText('DEBUG')).not.toBeInTheDocument();
    expect(within(drawer).queryByText('HTTP_PROXY')).not.toBeInTheDocument();
    expect(within(drawer).queryByText('WEBUI_PORT')).not.toBeInTheDocument();
    expect(within(drawer).queryByText('WEBHOOK_VERIFY_SSL')).not.toBeInTheDocument();
    expect(within(drawer).queryByText('UNREGISTERED_VENDOR_API_KEY')).not.toBeInTheDocument();
    expect(within(drawer).getByText('SCHEDULE_ENABLED')).toBeInTheDocument();
  });

  it('keeps AI provider secrets out of the generic raw drawer', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          {
            key: 'OPENAI_API_KEY',
            value: 'masked-openai-key',
            rawValueExists: true,
            isMasked: true,
            rawEditable: false,
            uiVisibility: 'curated',
            schema: {
              key: 'OPENAI_API_KEY',
              category: 'ai_model',
              dataType: 'string',
              uiControl: 'password',
              isSensitive: true,
              isRequired: false,
              isEditable: true,
              rawEditable: false,
              uiVisibility: 'curated',
              options: [],
              validation: {},
              displayOrder: 1,
            },
          },
          {
            key: 'AI_PROVIDER_TIMEOUT_SECONDS',
            value: '20',
            rawValueExists: true,
            isMasked: false,
            rawEditable: true,
            uiVisibility: 'raw',
            schema: {
              key: 'AI_PROVIDER_TIMEOUT_SECONDS',
              category: 'ai_model',
              dataType: 'integer',
              uiControl: 'number',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              rawEditable: true,
              uiVisibility: 'raw',
              options: [],
              validation: {},
              displayOrder: 2,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    expect(await screen.findByText('服务商快速配置')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('raw-fields-drawer-trigger'));

    const drawer = await screen.findByRole('dialog', { name: zh('settings.rawFieldsSectionTitle') });
    expect(within(drawer).queryByText('OPENAI_API_KEY')).not.toBeInTheDocument();
    expect(within(drawer).getByText('AI_PROVIDER_TIMEOUT_SECONDS')).toBeInTheDocument();
  });

  it('keeps data provider secrets out of the generic raw drawer', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'data_source' }));

    render(<SettingsPage />);

    expect(await screen.findByRole('heading', { name: '数据源配置' })).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('raw-fields-drawer-trigger'));

    const drawer = await screen.findByRole('dialog', { name: zh('settings.rawFieldsSectionTitle') });
    expect(within(drawer).queryByText('FINNHUB_API_KEY')).not.toBeInTheDocument();
    expect(within(drawer).getByText('REALTIME_SOURCE_PRIORITY')).toBeInTheDocument();
  });

  it('keeps notification secrets out of the generic raw drawer', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'notification' }));

    render(<SettingsPage />);

    fireEvent.click(screen.getByTestId('raw-fields-drawer-trigger'));
    const drawer = await screen.findByRole('dialog', { name: zh('settings.rawFieldsSectionTitle') });
    expect(within(drawer).queryByText('WECHAT_WEBHOOK_URL')).not.toBeInTheDocument();
    expect(within(drawer).queryByText('PUSHOVER_USER_KEY')).not.toBeInTheDocument();
    expect(within(drawer).queryByText('SLACK_CHANNEL_ID')).not.toBeInTheDocument();
    expect(within(drawer).getByText('NOTIFICATION_BATCH_SIZE')).toBeInTheDocument();
  });

  it('renders notification channels as a curated settings surface with masked secret fields', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'notification' }));

    render(<SettingsPage />);

    expect(await screen.findByRole('heading', { name: '通知通道' })).toBeInTheDocument();
    expect(screen.getAllByText('通知凭据在这里专用管理，并从原始系统设置中隐藏。').length).toBeGreaterThan(0);

    const wechatCard = screen.getByTestId('notification-channel-card-wechat');
    expect(within(wechatCard).getByText('已配置')).toBeInTheDocument();
    const webhookInput = within(wechatCard).getByLabelText('Webhook URL') as HTMLInputElement;
    expect(webhookInput.type).toBe('password');
    expect(webhookInput.value).toBe('wechat-webhook-token');
    expect(within(wechatCard).getByText('测试发送暂不可用')).toBeInTheDocument();
  });

  it('saves notification channel fields through the existing masked config update flow', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'notification' }));

    render(<SettingsPage />);

    const emailCard = await screen.findByTestId('notification-channel-card-email');
    fireEvent.change(within(emailCard).getByLabelText('收件人'), {
      target: { value: 'alerts@example.com' },
    });
    fireEvent.click(within(emailCard).getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(
        [{ key: 'EMAIL_RECEIVERS', value: 'alerts@example.com' }],
        'Email 通知通道已保存',
      );
    });
  });

  it('renders unconfigured notification channels without enabling no-op saves', async () => {
    const emptyNotificationItems = buildSystemConfigState().itemsByCategory.notification.map((item) => ({
      ...item,
      value: '',
      rawValueExists: false,
      isMasked: false,
    }));
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'notification',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        notification: emptyNotificationItems,
      },
    }));

    render(<SettingsPage />);

    const pushplusCard = await screen.findByTestId('notification-channel-card-pushplus');
    expect(within(pushplusCard).getByText('未配置')).toBeInTheDocument();
    expect(within(pushplusCard).getByRole('button', { name: '保存' })).toBeDisabled();
  });

  it('refreshes server state after intelligent import merges stock list', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'base' }));

    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'merge stock list' }));

    expect(saveExternalItems).toHaveBeenCalledWith([{ key: 'STOCK_LIST', value: 'SZ000001,SZ000002' }], '操作成功');
    expect(load).toHaveBeenCalledTimes(1);
  });

  it('lazy loads the advanced llm editor only after the drawer opens', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'ai_model' }));

    render(<SettingsPage />);

    expect(llmEditorModuleLoad.loadCount).toBe(0);
    expect(screen.queryByRole('button', { name: 'save llm channels' })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: '打开高级设置' }));

    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: '高级服务商 / 渠道编辑' })).toBeInTheDocument();
    });
    expect(llmEditorModuleLoad.loadCount).toBe(1);
    expect(screen.getByText('正在按需加载高级渠道终端…')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'save llm channels' })).toBeNull();

    llmEditorModuleLoad.resolve();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'save llm channels' })).toBeInTheDocument();
    });
  });

  it('lazy loads the data source library drawer only after it opens', async () => {
    dataSourceDrawerModuleLoad.defer();
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'data_source' }));

    render(<SettingsPage />);

    expect(dataSourceDrawerModuleLoad.loadCount).toBe(0);
    expect(screen.queryByTestId('data-source-library-drawer-loading')).toBeNull();

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    expect(dataSection).not.toBeNull();

    fireEvent.click(within(dataSection as HTMLElement).getByRole('button', { name: '添加数据源' }));

    expect(await screen.findByTestId('data-source-library-drawer-loading')).toBeInTheDocument();
    expect(dataSourceDrawerModuleLoad.loadCount).toBe(1);
    expect(screen.getByRole('dialog', { name: '注册数据源' })).toBeInTheDocument();
    expect(screen.queryByLabelText('显示名称')).toBeNull();

    dataSourceDrawerModuleLoad.resolve();

    await waitFor(() => {
      expect(screen.getByLabelText('显示名称')).toBeInTheDocument();
    });
  });

  it('refreshes server state after llm channel editor saves', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'ai_model' }));

    render(<SettingsPage />);

    expect(screen.queryByRole('button', { name: 'save llm channels' })).toBeNull();
    await openAdvancedConfigDrawer();
    fireEvent.click(screen.getByRole('button', { name: 'save llm channels' }));

    expect(saveExternalItems).toHaveBeenCalledWith([{ key: 'LLM_CHANNELS', value: 'primary,backup' }], '渠道配置已保存');
    expect(load).toHaveBeenCalledTimes(1);
  });

  it('enables primary AI gateway selector when one configured provider is detected', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', ''),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');

    const primaryGateway = combos[0] as HTMLSelectElement;
    const backupGateway = combos[1] as HTMLSelectElement;

    expect(primaryGateway).not.toBeDisabled();
    expect(primaryGateway.querySelector('option[value="aihubmix"]')).not.toBeNull();
    expect(backupGateway).toBeDisabled();
    expect(screen.getByText('备用路由需要至少两个已配置 AI 服务商。')).toBeInTheDocument();
  });

  it('treats AIHUBMIX_API_KEY as credential-ready for gateway selection', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');
    const primaryGateway = combos[0] as HTMLSelectElement;

    expect(primaryGateway).not.toBeDisabled();
    expect(primaryGateway.querySelector('option[value="aihubmix"]')).not.toBeNull();
  });

  it('enables primary selector for GLM/Zhipu when direct API key is configured', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('ZHIPU_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');

    const primaryGateway = combos[0] as HTMLSelectElement;
    const backupGateway = combos[1] as HTMLSelectElement;

    expect(primaryGateway).not.toBeDisabled();
    expect(primaryGateway.querySelector('option[value="zhipu"]')).not.toBeNull();
    expect(backupGateway).toBeDisabled();
  });

  it('uses configured providers as the source of truth for gateway selector options', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', ''),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');

    const primaryGateway = combos[0] as HTMLSelectElement;
    const backupGateway = combos[1] as HTMLSelectElement;

    expect(primaryGateway).not.toBeDisabled();
    expect(backupGateway).not.toBeDisabled();
    expect(primaryGateway.querySelector('option[value="aihubmix"]')).not.toBeNull();
    expect(primaryGateway.querySelector('option[value="gemini"]')).not.toBeNull();
    expect(backupGateway.querySelector('option[value="aihubmix"]')).not.toBeNull();
    expect(backupGateway.querySelector('option[value="gemini"]')).not.toBeNull();
    expect(screen.getAllByRole('option', { name: 'AIHubMix' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('option', { name: 'Gemini' }).length).toBeGreaterThan(0);
  });

  it('does not backfill phantom Zhipu glm-5 from stale saved models when only glm-4 is declared', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('LLM_CHANNELS', 'zhipu'),
          buildAiConfigItem('LLM_ZHIPU_API_KEY', 'masked-zhipu-key'),
          buildAiConfigItem('LLM_ZHIPU_ENABLED', 'true'),
          buildAiConfigItem('LLM_ZHIPU_MODELS', 'glm-4'),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', 'zhipu/glm-5'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'zhipu'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'zhipu/glm-5'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });

    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[0] as HTMLButtonElement);
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '预设选择' })[0] as HTMLButtonElement);

    const combos = within(aiSection).getAllByRole('combobox');
    const primaryModel = combos[1] as HTMLSelectElement;
    expect(primaryModel.querySelector('option[value="glm-4"]')).not.toBeNull();
    expect(primaryModel.querySelector('option[value="zhipu/glm-5"]')).toBeNull();
  });

  it('saves GLM/Zhipu main route with bare glm-4 when advanced channel explicitly declares glm-4', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('LLM_CHANNELS', 'zhipu'),
          buildAiConfigItem('LLM_ZHIPU_API_KEY', 'masked-zhipu-key'),
          buildAiConfigItem('LLM_ZHIPU_ENABLED', 'true'),
          buildAiConfigItem('LLM_ZHIPU_MODELS', 'glm-4'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
          buildAiConfigItem('LITELLM_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });

    let combos = within(aiSection).getAllByRole('combobox');
    fireEvent.change(combos[0] as HTMLSelectElement, { target: { value: 'zhipu' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[0] as HTMLButtonElement);
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '预设选择' })[0] as HTMLButtonElement);
    combos = within(aiSection).getAllByRole('combobox');
    fireEvent.change(combos[1] as HTMLSelectElement, { target: { value: 'glm-4' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(expect.arrayContaining([
        { key: 'AI_PRIMARY_GATEWAY', value: 'zhipu' },
        { key: 'AI_PRIMARY_MODEL', value: 'glm-4' },
        { key: 'LITELLM_MODEL', value: 'glm-4' },
      ]), expect.stringContaining('主路由'));
    });
  });

  it('does not enable AI gateway selectors from legacy LLM_CHANNELS alone', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('LLM_CHANNELS', 'gemini,aihubmix'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');

    const primaryGateway = combos[0] as HTMLSelectElement;
    const backupGateway = combos[1] as HTMLSelectElement;

    expect(primaryGateway).toBeDisabled();
    expect(backupGateway).toBeDisabled();
    expect(within(aiSection).getByText('无主路由网关。请先配置 AI 服务商凭据。')).toBeInTheDocument();
    expect(within(aiSection).getByText('备用路由需要至少两个已配置 AI 服务商。')).toBeInTheDocument();
  });

  it('saves primary-only AI route and keeps legacy channel list stable', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'legacy'),
          buildAiConfigItem('LITELLM_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', 'legacy/fallback'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');
    const primaryGateway = combos[0] as HTMLSelectElement;

    fireEvent.change(primaryGateway, { target: { value: 'gemini' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith([
        { key: 'AI_PRIMARY_GATEWAY', value: 'gemini' },
        { key: 'AI_PRIMARY_MODEL', value: 'gemini/gemini-2.5-flash' },
        { key: 'AI_BACKUP_GATEWAY', value: '' },
        { key: 'AI_BACKUP_MODEL', value: '' },
        { key: 'LLM_CHANNELS', value: 'legacy' },
        { key: 'LITELLM_MODEL', value: 'gemini/gemini-2.5-flash' },
        { key: 'LITELLM_FALLBACK_MODELS', value: '' },
      ], expect.stringContaining('主路由'));
    });
  });

  it('saves primary AIHubMix route with a manual model id', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'legacy'),
          buildAiConfigItem('LITELLM_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', ''),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');
    const primaryGateway = combos[0] as HTMLSelectElement;

    fireEvent.change(primaryGateway, { target: { value: 'aihubmix' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[0] as HTMLButtonElement);
    const customButtons = within(aiSection).getAllByRole('button', { name: '自定义 ID' });
    fireEvent.click(customButtons[0] as HTMLButtonElement);
    const primaryCustomModelInput = within(aiSection).getByLabelText('自定义模型 ID') as HTMLInputElement;
    fireEvent.change(primaryCustomModelInput, { target: { value: 'openai/gpt-4.1-free' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith([
        { key: 'AI_PRIMARY_GATEWAY', value: 'aihubmix' },
        { key: 'AI_PRIMARY_MODEL', value: 'openai/gpt-4.1-free' },
        { key: 'AI_BACKUP_GATEWAY', value: '' },
        { key: 'AI_BACKUP_MODEL', value: '' },
        { key: 'LLM_CHANNELS', value: 'legacy' },
        { key: 'LITELLM_MODEL', value: 'openai/gpt-4.1-free' },
        { key: 'LITELLM_FALLBACK_MODELS', value: '' },
      ], expect.stringContaining('主路由'));
    });
  });

  it('does not require preset coverage for AIHubMix manual model ids', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'legacy'),
          buildAiConfigItem('LITELLM_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', ''),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');
    const primaryGateway = combos[0] as HTMLSelectElement;

    fireEvent.change(primaryGateway, { target: { value: 'aihubmix' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[0] as HTMLButtonElement);
    const customButtons = within(aiSection).getAllByRole('button', { name: '自定义 ID' });
    fireEvent.click(customButtons[0] as HTMLButtonElement);
    const primaryCustomModelInput = within(aiSection).getByLabelText('自定义模型 ID') as HTMLInputElement;
    fireEvent.change(primaryCustomModelInput, { target: { value: 'openai/gpt-4.1-future' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(expect.arrayContaining([
        { key: 'AI_PRIMARY_GATEWAY', value: 'aihubmix' },
        { key: 'AI_PRIMARY_MODEL', value: 'openai/gpt-4.1-future' },
      ]), expect.stringContaining('主路由'));
    });
  });

  it('clears backup gateway/model draft state via visible clear action', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'aihubmix'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    let combos = within(aiSection).getAllByRole('combobox');
    const backupGateway = combos[1] as HTMLSelectElement;
    fireEvent.change(backupGateway, { target: { value: 'gemini' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[1] as HTMLButtonElement);
    combos = within(aiSection).getAllByRole('combobox');
    const backupModel = combos[2] as HTMLSelectElement;
    fireEvent.change(backupModel, { target: { value: 'gemini/gemini-2.5-flash' } });

    fireEvent.click(within(aiSection).getByRole('button', { name: '清空备用路由' }));

    expect((within(aiSection).getAllByRole('combobox')[1] as HTMLSelectElement).value).toBe('');
  });

  it('saves primary-only route after clearing backup and clears legacy fallback models', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'legacy'),
          buildAiConfigItem('LITELLM_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', 'aihubmix'),
          buildAiConfigItem('AI_BACKUP_MODEL', 'openai/gpt-4.1-mini'),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });

    fireEvent.click(within(aiSection).getByRole('button', { name: '清空备用路由' }));
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(expect.arrayContaining([
        { key: 'AI_PRIMARY_GATEWAY', value: 'gemini' },
        { key: 'AI_PRIMARY_MODEL', value: 'gemini/gemini-2.5-flash' },
        { key: 'AI_BACKUP_GATEWAY', value: '' },
        { key: 'AI_BACKUP_MODEL', value: '' },
        { key: 'LITELLM_FALLBACK_MODELS', value: '' },
      ]), expect.stringContaining('主路由'));
    });
  });

  it('shows inline pre-save guidance when backup model is not declared by enabled channels', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('LLM_GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'gemini,aihubmix'),
          buildAiConfigItem('LLM_GEMINI_ENABLED', 'true'),
          buildAiConfigItem('LLM_GEMINI_MODELS', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('LLM_AIHUBMIX_ENABLED', 'true'),
          buildAiConfigItem('LLM_AIHUBMIX_MODELS', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'aihubmix'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    let combos = within(aiSection).getAllByRole('combobox');
    const backupGateway = combos[1] as HTMLSelectElement;
    fireEvent.change(backupGateway, { target: { value: 'gemini' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[1] as HTMLButtonElement);
    combos = within(aiSection).getAllByRole('combobox');
    const backupModel = combos[2] as HTMLSelectElement;
    fireEvent.change(backupModel, { target: { value: 'gemini/gemini-3-flash-preview' } });

    expect(screen.getByText(/未在已启用的 Gemini 渠道模型声明中找到/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '前往配置渠道模型' })).toBeInTheDocument();
    expect(within(aiSection).getByRole('button', { name: '保存优先顺序' })).toBeDisabled();
  });

  it('allows Gemini backup compatibility with direct Gemini API key only', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'aihubmix'),
          buildAiConfigItem('LLM_AIHUBMIX_ENABLED', 'true'),
          buildAiConfigItem('LLM_AIHUBMIX_MODELS', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'aihubmix'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    let combos = within(aiSection).getAllByRole('combobox');
    const backupGateway = combos[1] as HTMLSelectElement;
    fireEvent.change(backupGateway, { target: { value: 'gemini' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[1] as HTMLButtonElement);
    combos = within(aiSection).getAllByRole('combobox');
    const backupModel = combos[2] as HTMLSelectElement;
    fireEvent.change(backupModel, { target: { value: 'gemini/gemini-3-flash-preview' } });

    expect(screen.queryByText(/未在已启用的 Gemini 渠道模型声明中找到/)).toBeNull();
    expect(within(aiSection).getByRole('button', { name: '保存优先顺序' })).not.toBeDisabled();
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(expect.arrayContaining([
        { key: 'AI_BACKUP_GATEWAY', value: 'gemini' },
        { key: 'AI_BACKUP_MODEL', value: 'gemini/gemini-3-flash-preview' },
      ]), expect.stringContaining('备用路由'));
    });
  });

  it('saves backup route when backup model is declared by enabled channels', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'gemini,aihubmix'),
          buildAiConfigItem('LLM_GEMINI_ENABLED', 'true'),
          buildAiConfigItem('LLM_GEMINI_MODELS', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('LLM_AIHUBMIX_ENABLED', 'true'),
          buildAiConfigItem('LLM_AIHUBMIX_MODELS', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'aihubmix'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    let combos = within(aiSection).getAllByRole('combobox');
    const backupGateway = combos[1] as HTMLSelectElement;
    fireEvent.change(backupGateway, { target: { value: 'gemini' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[1] as HTMLButtonElement);
    combos = within(aiSection).getAllByRole('combobox');
    const backupModel = combos[2] as HTMLSelectElement;
    fireEvent.change(backupModel, { target: { value: 'gemini/gemini-2.5-flash' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(expect.arrayContaining([
        { key: 'AI_BACKUP_GATEWAY', value: 'gemini' },
        { key: 'AI_BACKUP_MODEL', value: 'gemini/gemini-2.5-flash' },
        { key: 'LITELLM_FALLBACK_MODELS', value: 'gemini/gemini-2.5-flash' },
      ]), expect.stringContaining('备用路由'));
    });
  });

  it('overwrites stale legacy fallback models when saving a new backup route', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'legacy'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'aihubmix'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', 'legacy/invalid,legacy/old'),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    let combos = within(aiSection).getAllByRole('combobox');
    const backupGateway = combos[1] as HTMLSelectElement;
    fireEvent.change(backupGateway, { target: { value: 'gemini' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[1] as HTMLButtonElement);
    combos = within(aiSection).getAllByRole('combobox');
    const backupModel = combos[2] as HTMLSelectElement;
    fireEvent.change(backupModel, { target: { value: 'gemini/gemini-2.5-flash' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(expect.arrayContaining([
        { key: 'LITELLM_FALLBACK_MODELS', value: 'gemini/gemini-2.5-flash' },
      ]), expect.stringContaining('备用路由'));
    });
  });

  it('shows visible route-to-channel configuration entry in AI routing section', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'ai_model' }));
    render(<SettingsPage />);
    await openAiRoutingDrawer();
    expect(screen.getByRole('dialog', { name: '任务路由编辑' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '编辑任务路由' })).toBeInTheDocument();
    expect(screen.getByText('服务商快速配置')).toBeInTheDocument();
    expect(screen.getByText('1. 任务路由')).toBeInTheDocument();
    expect(screen.getByText('2. 服务商库')).toBeInTheDocument();
    expect(screen.getByText('3. 高级配置（可选）')).toBeInTheDocument();
    expect(screen.getByText('模型供应商')).toBeInTheDocument();
    expect(screen.getByText('高级渠道配置')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '打开高级设置' })).toBeInTheDocument();
    expect(screen.getByTestId('ai-task-row-analysis')).toBeInTheDocument();
    expect(screen.getByTestId('ai-task-row-stock_chat')).toBeInTheDocument();
    expect(screen.getByTestId('ai-task-row-backtest')).toBeInTheDocument();
    expect(screen.getByTestId('ai-provider-card-gemini')).toHaveAttribute('data-layout', 'row');
    expect(screen.getAllByText('GLM / Zhipu').length).toBeGreaterThan(0);
  });

  it('renders a compact effective AI summary and removes the duplicate task-model recap section', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    expect(screen.queryByRole('heading', { name: '当前生效 AI 配置' })).toBeNull();
    const aiSection = screen.getByRole('heading', { name: '任务路由' }).closest('section');
    expect(aiSection).not.toBeNull();
    const aiSummary = within(aiSection as HTMLElement).getByTestId('ai-effective-summary');
    expect(within(aiSummary).getByTestId('ai-task-row-analysis')).toBeInTheDocument();
    expect(within(aiSummary).getByTestId('ai-task-row-stock_chat')).toBeInTheDocument();
    expect(within(aiSummary).getByTestId('ai-task-row-backtest')).toBeInTheDocument();
    expect(within(aiSummary).getAllByText('股票分析').length).toBeGreaterThan(0);
    expect(within(aiSummary).getByText('问股')).toBeInTheDocument();
    expect(within(aiSummary).getByText('回测')).toBeInTheDocument();
    expect(within(aiSummary).getAllByText(/Gemini \/ gemini\/gemini-2\.5-flash/).length).toBeGreaterThan(0);
    expect(screen.queryByText('按任务配置模型')).toBeNull();
  });

  it('shows the inherited backtest route summary only once in the compact AI summary', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
          buildAiConfigItem('BACKTEST_LITELLM_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    const aiSection = screen.getByRole('heading', { name: '任务路由' }).closest('section');
    expect(aiSection).not.toBeNull();

    expect(
      within(aiSection as HTMLElement).getAllByText(/回测路由：当前继承分析路由/).length,
    ).toBe(1);
  });

  it('splits data settings into Data Routing and Data Source Library', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        data_source: [
          {
            key: 'REALTIME_SOURCE_PRIORITY',
            value: 'finnhub,yahoo',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'REALTIME_SOURCE_PRIORITY',
              category: 'data_source',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 1,
            },
          },
          {
            key: 'FINNHUB_API_KEY',
            value: 'masked-finnhub-token',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'FINNHUB_API_KEY',
              category: 'data_source',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: true,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 2,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    expect(dataSection).not.toBeNull();
    expect(within(dataSection as HTMLElement).getByText('1. 数据路由')).toBeInTheDocument();
    expect(within(dataSection as HTMLElement).getByText('2. 数据源库')).toBeInTheDocument();
    expect(within(dataSection as HTMLElement).getByText('MARKET DATA')).toBeInTheDocument();
    expect(within(dataSection as HTMLElement).getByText('FUNDAMENTALS')).toBeInTheDocument();
    expect(within(dataSection as HTMLElement).getByText('NEWS & SENTIMENT')).toBeInTheDocument();
    expect(within(dataSection as HTMLElement).getByText('行情数据')).toBeInTheDocument();
    expect(within(dataSection as HTMLElement).getByText(/Finnhub -> Yahoo/)).toBeInTheDocument();
    const finnhubCard = within(dataSection as HTMLElement).getByTestId('data-source-card-finnhub');
    expect(finnhubCard).toHaveAttribute('data-layout', 'row');
    expect(within(finnhubCard).getByText('Finnhub')).toBeInTheDocument();
    expect(within(finnhubCard).getByText('行情')).toBeInTheDocument();
    expect(within(finnhubCard).getByText('基本面')).toBeInTheDocument();
    expect(within(finnhubCard).getByText('新闻')).toBeInTheDocument();
    expect(within(finnhubCard).getByText('已配置待验证')).toBeInTheDocument();
    expect(within(finnhubCard).getByText('状态检查：已配置，未做连通性验证')).toBeInTheDocument();
    const yahooCard = within(dataSection as HTMLElement).getByTestId('data-source-card-yahoo');
    expect(within(yahooCard).getByText('内置源')).toBeInTheDocument();
    expect(within(yahooCard).getByText('行情')).toBeInTheDocument();
    expect(within(yahooCard).getByText('基本面')).toBeInTheDocument();
    expect(within(yahooCard).getAllByText('状态检查：内置源无需验证').length).toBeGreaterThan(0);
    expect(within(dataSection as HTMLElement).queryAllByRole('combobox').length).toBe(0);
    fireEvent.click(within(dataSection as HTMLElement).getByTestId('data-routing-manage-news'));
    const routingDrawer = await screen.findByRole('dialog', { name: '新闻数据' });
    expect(within(routingDrawer).getAllByRole('combobox').length).toBeGreaterThan(0);
    expect(within(routingDrawer).getByRole('button', { name: '保存优先顺序' })).toBeInTheDocument();
  });

  it('shows read-only endpoint and internal metadata on api source cards', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        data_source: [
          buildDataSourceConfigItem('REALTIME_SOURCE_PRIORITY', 'finnhub,yahoo'),
          buildDataSourceConfigItem('FINNHUB_API_KEY', 'masked-finnhub-token'),
          buildDataSourceConfigItem('CUSTOM_DATA_SOURCE_LIBRARY', JSON.stringify([
            {
              id: 'demo_news_api',
              name: 'Demo News API',
              credentialSchema: 'single_key',
              credential: 'demo-key',
              secret: '',
              baseUrl: 'https://demo.example.com/v1',
              description: 'Custom news endpoint',
              capabilities: ['news'],
              validation: { status: 'validated' },
            },
          ])),
        ],
      },
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    expect(dataSection).not.toBeNull();

    const finnhubCard = within(dataSection as HTMLElement).getByTestId('data-source-card-finnhub');
    expect(within(finnhubCard).getByText(`${translate('zh', 'settings.dataSourceEndpointNameLabel')}: finnhub`)).toBeInTheDocument();
    expect(within(finnhubCard).getByText(`${translate('zh', 'settings.dataSourceInternalFlagLabel')}: ${translate('zh', 'settings.dataSourceInternalFlagBuiltin')}`)).toBeInTheDocument();

    const yahooCard = within(dataSection as HTMLElement).getByTestId('data-source-card-yahoo');
    expect(within(yahooCard).getByText(`${translate('zh', 'settings.dataSourceEndpointNameLabel')}: yahoo`)).toBeInTheDocument();
    expect(within(yahooCard).getByText(`${translate('zh', 'settings.dataSourceInternalFlagLabel')}: ${translate('zh', 'settings.dataSourceInternalFlagBuiltin')}`)).toBeInTheDocument();

    const customCard = within(dataSection as HTMLElement).getByTestId('data-source-card-demo_news_api');
    expect(within(customCard).getByText(`${translate('zh', 'settings.dataSourceEndpointNameLabel')}: demo_news_api`)).toBeInTheDocument();
    expect(within(customCard).getByText(`${translate('zh', 'settings.dataSourceInternalFlagLabel')}: ${translate('zh', 'settings.dataSourceInternalFlagExternal')}`)).toBeInTheDocument();
  });

  it('shows the runtime summary visibility title only once in the advanced domain section', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'system',
    }));

    render(<SettingsPage />);

    expect(await screen.findByRole('heading', { name: '首页运行时执行摘要可见性' })).toBeInTheDocument();
    expect(screen.getAllByText('首页运行时执行摘要可见性').length).toBe(1);
  });

  it('keeps personal-only basic settings out of the system control plane', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'system',
    }));

    await withSystemSettingsPath(async () => {
      render(<SettingsPage />);

      expect(await screen.findByRole('heading', { name: zh('settings.controlPlaneTitle') })).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: zh('settings.basicTitle') })).not.toBeInTheDocument();
      expect(screen.queryByText(zh('settings.basicDesc'))).not.toBeInTheDocument();
    });
  });

  it('creates a custom data source and exposes it only in the matching routing selector', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    expect(dataSection).not.toBeNull();

    fireEvent.click(within(dataSection as HTMLElement).getByRole('button', { name: '添加数据源' }));
    const drawer = await screen.findByRole('dialog', { name: '注册数据源' });

    fireEvent.change(within(drawer).getByLabelText('显示名称'), { target: { value: 'Demo News API' } });
    fireEvent.change(within(drawer).getByLabelText('API Key / 凭据'), { target: { value: 'demo-news-key' } });
    fireEvent.change(within(drawer).getByLabelText('Base URL'), { target: { value: 'https://demo.example.com/v1' } });
    fireEvent.click(within(drawer).getByRole('button', { name: '新闻' }));
    fireEvent.click(within(drawer).getByRole('button', { name: '创建并保存' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({
            key: 'CUSTOM_DATA_SOURCE_LIBRARY',
            value: expect.stringContaining('"name":"Demo News API"'),
          }),
        ]),
        expect.stringContaining('数据源库已更新'),
      );
    });
    expect(saveExternalItems).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          key: 'CUSTOM_DATA_SOURCE_LIBRARY',
          value: expect.stringContaining('"credentialSchema":"single_key"'),
        }),
      ]),
      expect.any(String),
    );

    const customCard = within(dataSection as HTMLElement).getByTestId('data-source-card-demo_news_api');
    expect(within(customCard).getByText('自定义源')).toBeInTheDocument();
    expect(within(customCard).getByText('新闻')).toBeInTheDocument();
    expect(within(customCard).getByText('已配置待验证')).toBeInTheDocument();

    fireEvent.click(within(dataSection as HTMLElement).getByTestId('data-routing-manage-news'));
    const newsDrawer = await screen.findByRole('dialog', { name: '新闻数据' });
    expect(within(newsDrawer).getAllByRole('option', { name: /Demo News Api/i }).length).toBeGreaterThan(0);

    fireEvent.click(within(newsDrawer).getByLabelText('关闭抽屉'));
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: '新闻数据' })).not.toBeInTheDocument();
    });
    fireEvent.click(within(dataSection as HTMLElement).getByTestId('data-routing-manage-market'));
    const marketDrawer = await screen.findByRole('dialog', { name: '行情数据' });
    expect(within(marketDrawer).queryAllByRole('option', { name: /Demo News Api/i }).length).toBe(0);
  });

  it('supports custom key-secret data sources and persists both credentials', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    expect(dataSection).not.toBeNull();

    fireEvent.click(within(dataSection as HTMLElement).getByRole('button', { name: '添加数据源' }));
    const drawer = await screen.findByRole('dialog', { name: '注册数据源' });

    fireEvent.click(within(drawer).getByRole('button', { name: /Key \+ Secret/ }));
    fireEvent.change(within(drawer).getByLabelText('显示名称'), { target: { value: 'Demo Market Broker' } });
    fireEvent.change(within(drawer).getByLabelText('API Key / 凭据'), { target: { value: 'demo-market-key' } });
    fireEvent.change(within(drawer).getByLabelText('Secret Key'), { target: { value: 'demo-market-secret' } });
    fireEvent.click(within(drawer).getByRole('button', { name: '行情' }));
    fireEvent.click(within(drawer).getByRole('button', { name: '创建并保存' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({
            key: 'CUSTOM_DATA_SOURCE_LIBRARY',
            value: expect.stringContaining('"credentialSchema":"key_secret"'),
          }),
        ]),
        expect.stringContaining('数据源库已更新'),
      );
    });
    expect(saveExternalItems).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          key: 'CUSTOM_DATA_SOURCE_LIBRARY',
          value: expect.stringContaining('"secret":"demo-market-secret"'),
        }),
      ]),
      expect.any(String),
    );
  });

  it('deletes a custom data source and scrubs it from saved route priorities', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        data_source: [
          buildDataSourceConfigItem('NEWS_SOURCE_PRIORITY', 'demo_news_api,tavily'),
          buildDataSourceConfigItem('TAVILY_API_KEY', 'masked-tavily-token'),
          buildDataSourceConfigItem('CUSTOM_DATA_SOURCE_LIBRARY', JSON.stringify([
            {
              id: 'demo_news_api',
              name: 'Demo News API',
              credentialSchema: 'single_key',
              credential: 'demo-key',
              secret: '',
              baseUrl: 'https://demo.example.com/v1',
              description: 'Custom news endpoint',
              capabilities: ['news'],
              validation: { status: 'validated' },
            },
          ])),
        ],
      },
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: zh('settings.dataEffectiveTitle') }).closest('section');
    expect(dataSection).not.toBeNull();
    const customCard = within(dataSection as HTMLElement).getByTestId('data-source-card-demo_news_api');

    fireEvent.click(within(customCard).getByRole('button', { name: zh('settings.dataSourceEditAction') }));

    const drawer = await screen.findByRole('dialog', {
      name: zh('settings.dataSourceDrawerTitleEdit', { source: 'Demo News API' }),
    });
    fireEvent.click(within(drawer).getByRole('button', { name: zh('settings.dataSourceDeleteAction') }));

    const confirmTitle = await screen.findByText(zh('settings.dataSourceDeleteConfirmTitle', { source: 'Demo News API' }));
    const confirmDialog = confirmTitle.closest('.confirm-dialog__surface');
    expect(confirmDialog).not.toBeNull();
    fireEvent.click(within(confirmDialog as HTMLElement).getByRole('button', { name: zh('settings.dataSourceDeleteAction') }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(
        expect.arrayContaining([
          {
            key: 'CUSTOM_DATA_SOURCE_LIBRARY',
            value: '[]',
          },
          {
            key: 'NEWS_SOURCE_PRIORITY',
            value: 'tavily',
          },
        ]),
        zh('settings.dataSourceDeleted'),
      );
    });

    expect(within(dataSection as HTMLElement).queryByTestId('data-source-card-demo_news_api')).not.toBeInTheDocument();
  });

  it('manages Alpaca built-in credentials with key-secret plus feed fields', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        data_source: [
          buildDataSourceConfigItem('REALTIME_SOURCE_PRIORITY', 'alpaca,yahoo'),
          buildDataSourceConfigItem('ALPACA_API_KEY_ID', ''),
          buildDataSourceConfigItem('ALPACA_API_SECRET_KEY', ''),
          buildDataSourceConfigItem('ALPACA_DATA_FEED', 'iex'),
        ],
      },
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    expect(dataSection).not.toBeNull();
    const alpacaCard = within(dataSection as HTMLElement).getByTestId('data-source-card-alpaca');

    fireEvent.click(within(alpacaCard).getByRole('button', { name: '管理' }));
    const drawer = await screen.findByRole('dialog', { name: 'Alpaca 数据源管理' });

    fireEvent.change(within(drawer).getByLabelText(/Alpaca Key ID/i), { target: { value: 'alpaca-key-id' } });
    fireEvent.change(within(drawer).getByLabelText(/Secret Key/i), { target: { value: 'alpaca-secret-key' } });
    fireEvent.change(within(drawer).getByLabelText(/数据通道/i), { target: { value: 'sip' } });
    fireEvent.click(within(drawer).getByRole('button', { name: '保存更改' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith([
        { key: 'ALPACA_API_KEY_ID', value: 'alpaca-key-id' },
        { key: 'ALPACA_API_SECRET_KEY', value: 'alpaca-secret-key' },
        { key: 'ALPACA_DATA_FEED', value: 'sip' },
      ], '数据源库已更新');
    });
  });

  it('stores Twelve Data credentials in the singular key when one token is provided', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        data_source: [
          buildDataSourceConfigItem('REALTIME_SOURCE_PRIORITY', 'twelve_data,yahoo'),
          buildDataSourceConfigItem('TWELVE_DATA_API_KEY', ''),
          buildDataSourceConfigItem('TWELVE_DATA_API_KEYS', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    expect(dataSection).not.toBeNull();
    const twelveDataCard = within(dataSection as HTMLElement).getByTestId('data-source-card-twelve_data');

    fireEvent.click(within(twelveDataCard).getByRole('button', { name: '管理' }));
    const drawer = await screen.findByRole('dialog', { name: 'Twelve Data 数据源管理' });

    fireEvent.change(within(drawer).getByLabelText('API Key / 凭据'), { target: { value: 'twelve-single-key' } });
    fireEvent.click(within(drawer).getByRole('button', { name: '保存更改' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith([
        { key: 'TWELVE_DATA_API_KEY', value: 'twelve-single-key' },
        { key: 'TWELVE_DATA_API_KEYS', value: '' },
      ], '数据源库已更新');
    });
  });

  it('stores Twelve Data credentials in the plural key when multiple tokens are provided', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        data_source: [
          buildDataSourceConfigItem('REALTIME_SOURCE_PRIORITY', 'twelve_data,yahoo'),
          buildDataSourceConfigItem('TWELVE_DATA_API_KEY', ''),
          buildDataSourceConfigItem('TWELVE_DATA_API_KEYS', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    expect(dataSection).not.toBeNull();
    const twelveDataCard = within(dataSection as HTMLElement).getByTestId('data-source-card-twelve_data');

    fireEvent.click(within(twelveDataCard).getByRole('button', { name: '管理' }));
    const drawer = await screen.findByRole('dialog', { name: 'Twelve Data 数据源管理' });

    fireEvent.change(within(drawer).getByLabelText('API Key / 凭据'), { target: { value: 'key-one,key-two' } });
    fireEvent.click(within(drawer).getByRole('button', { name: '保存更改' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith([
        { key: 'TWELVE_DATA_API_KEY', value: '' },
        { key: 'TWELVE_DATA_API_KEYS', value: 'key-one,key-two' },
      ], '数据源库已更新');
    });
  });

  it('shows built-in provider remote validation success details', async () => {
    testBuiltinDataSource.mockResolvedValueOnce({
      provider: 'fmp',
      ok: true,
      status: 'success',
      checkedAt: '2026-04-30T00:00:00Z',
      durationMs: 150,
      keyMasked: 'abcd...wxyz',
      checks: [
        {
          name: 'quote',
          endpoint: '/api/v3/quote/MSFT',
          ok: true,
          httpStatus: 200,
          durationMs: 70,
          errorType: null,
          message: 'quote endpoint 可用。',
        },
        {
          name: 'historical',
          endpoint: '/api/v3/historical-price-full/MSFT',
          ok: true,
          httpStatus: 200,
          durationMs: 80,
          errorType: null,
          message: 'historical endpoint 可用。',
        },
      ],
      summary: 'FMP 连接成功：quote 和 historical endpoint 均可用。',
      suggestion: '无需处理。',
    });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        data_source: [
          buildDataSourceConfigItem('FMP_API_KEY', 'fmp-secret-key'),
        ],
      },
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    const fmpCard = within(dataSection as HTMLElement).getByTestId('data-source-card-fmp');
    fireEvent.click(within(fmpCard).getByRole('button', { name: '管理' }));
    const drawer = await screen.findByRole('dialog');
    fireEvent.click(within(drawer).getByRole('button', { name: '校验' }));

    await waitFor(() => {
      expect(testBuiltinDataSource).toHaveBeenCalledWith({
        provider: 'fmp',
        symbol: 'MSFT',
        credential: 'fmp-secret-key',
        secret: '',
        timeoutSeconds: 5,
      });
    });
    expect(await within(drawer).findByTestId('builtin-data-source-validation-result')).toHaveTextContent('abcd...wxyz');
    expect(within(drawer).getByText(/校验时间:/)).toHaveTextContent('2026/04/30');
    expect(within(drawer).getByText(/quote: OK/)).toBeInTheDocument();
    expect(within(drawer).getByText(/historical: OK/)).toBeInTheDocument();
    expect(screen.queryByText('配置本地校验通过')).not.toBeInTheDocument();
    expect(within(fmpCard).getByText('已验证')).toHaveAttribute('data-status', 'success');
  });

  it('shows built-in provider partial validation failures and suggestions', async () => {
    testBuiltinDataSource.mockResolvedValueOnce({
      provider: 'fmp',
      ok: false,
      status: 'partial',
      checkedAt: '2026-04-30T00:00:00Z',
      durationMs: 155,
      keyMasked: 'abcd...wxyz',
      checks: [
        {
          name: 'quote',
          endpoint: '/api/v3/quote/MSFT',
          ok: true,
          httpStatus: 200,
          durationMs: 65,
          errorType: null,
          message: 'quote endpoint 可用。',
        },
        {
          name: 'historical',
          endpoint: '/api/v3/historical-price-full/MSFT',
          ok: false,
          httpStatus: 403,
          durationMs: 90,
          errorType: 'Forbidden',
          message: 'historical endpoint 返回 403，可能是 API key 无效、额度不足或当前套餐不支持该 endpoint。',
        },
      ],
      summary: 'FMP 部分可用：historical endpoint 失败。',
      suggestion: '检查套餐权限或重置 API key。',
    });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        data_source: [
          buildDataSourceConfigItem('FMP_API_KEY', 'fmp-secret-key'),
        ],
      },
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    const fmpCard = within(dataSection as HTMLElement).getByTestId('data-source-card-fmp');
    fireEvent.click(within(fmpCard).getByRole('button', { name: '管理' }));
    const drawer = await screen.findByRole('dialog');
    fireEvent.click(within(drawer).getByRole('button', { name: '校验' }));

    await waitFor(() => {
      expect(within(drawer).getAllByText(/FMP 部分可用/).length).toBeGreaterThan(0);
    });
    expect(within(drawer).getByText(/校验时间:/)).toHaveTextContent('2026/04/30');
    expect(within(drawer).getByText(/historical: HTTP 403/)).toBeInTheDocument();
    expect(within(drawer).getByText(/检查套餐权限或重置 API key/)).toBeInTheDocument();
    expect(within(drawer).queryByText('fmp-secret-key')).not.toBeInTheDocument();
    expect(within(fmpCard).getByText('部分可用')).toHaveAttribute('data-status', 'partial');
  });

  it('shows unified copy when custom data source validation fails', async () => {
    testCustomDataSource.mockResolvedValueOnce({
      success: false,
      message: 'temporarily unavailable',
      error: 'Upstream error',
      statusCode: 503,
      checkedUrl: 'https://demo.example.com/v1/callback?api_key=demo-secret&token=demo-token',
      latencyMs: 120,
    });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        data_source: [
          buildDataSourceConfigItem('REALTIME_SOURCE_PRIORITY', 'demo_news_api'),
          buildDataSourceConfigItem('CUSTOM_DATA_SOURCE_LIBRARY', JSON.stringify([
            {
              id: 'demo_news_api',
              name: 'Demo News API',
              credentialSchema: 'single_key',
              credential: 'demo-secret',
              secret: '',
              baseUrl: 'https://demo.example.com/v1',
              description: 'Custom news endpoint',
              capabilities: ['news'],
              validation: { status: 'validated' },
            },
          ])),
        ],
      },
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    expect(dataSection).not.toBeNull();
    const customCard = within(dataSection as HTMLElement).getByTestId('data-source-card-demo_news_api');

    fireEvent.click(within(customCard).getByRole('button', { name: '校验' }));

    await waitFor(() => {
      expect(testCustomDataSource).toHaveBeenCalledWith({
        name: 'Demo News API',
        baseUrl: 'https://demo.example.com/v1',
        credentialSchema: 'single_key',
        credential: 'demo-secret',
        secret: '',
        timeoutSeconds: 5,
      });
    });
    expect(await within(customCard).findByText('服务器暂时不可用，请稍后重试。')).toBeInTheDocument();
    expect(within(customCard).queryByText('demo-secret')).not.toBeInTheDocument();
    expect(within(customCard).queryByText('demo-token')).not.toBeInTheDocument();
  });

  it('shows quick-api status and advanced-channel count on provider cards', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'aihubmix'),
          buildAiConfigItem('LLM_AIHUBMIX_PROTOCOL', 'openai'),
          buildAiConfigItem('LLM_AIHUBMIX_MODELS', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    const providerSection = screen.getByTestId('ai-provider-quick-section');
    const geminiCard = within(providerSection).getByTestId('ai-provider-card-gemini');
    expect(within(geminiCard as HTMLElement).getByText(/快速接口/)).toBeInTheDocument();
    expect(within(geminiCard as HTMLElement).getByText(/高级渠道数: 0/)).toBeInTheDocument();

    const aihubmixCard = within(providerSection).getByTestId('ai-provider-card-aihubmix');
    expect(within(aihubmixCard as HTMLElement).getByText(/高级渠道数: 1/)).toBeInTheDocument();
  });

  it('shows provider-aware empty-state guidance when no advanced channel exists', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('ZHIPU_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'aihubmix'),
          buildAiConfigItem('LLM_AIHUBMIX_PROTOCOL', 'openai'),
          buildAiConfigItem('LLM_AIHUBMIX_MODELS', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'zhipu'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'zhipu/glm-5'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);
    fireEvent.click(screen.getByRole('button', { name: '管理 GLM / Zhipu 高级配置' }));

    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: '高级服务商 / 渠道编辑' })).toBeInTheDocument();
    });
    const advancedDrawer = screen.getByRole('dialog', { name: '高级服务商 / 渠道编辑' });
    expect(within(advancedDrawer).getByText('GLM / Zhipu 的快速接口已配置，但尚未创建独立高级渠道。')).toBeInTheDocument();
    expect(within(advancedDrawer).getByRole('button', { name: '创建 GLM / Zhipu 高级渠道' })).toBeInTheDocument();
    expect(screen.getByTestId('llm-provider-scope')).toHaveTextContent('zhipu');
  });

  it('focuses provider advanced channel when it already exists', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'gemini,aihubmix'),
          buildAiConfigItem('LLM_GEMINI_PROTOCOL', 'gemini'),
          buildAiConfigItem('LLM_GEMINI_MODELS', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('LLM_AIHUBMIX_PROTOCOL', 'openai'),
          buildAiConfigItem('LLM_AIHUBMIX_MODELS', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);
    fireEvent.click(screen.getByRole('button', { name: '管理 Gemini 高级配置' }));

    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: '高级服务商 / 渠道编辑' })).toBeInTheDocument();
    });
    expect(screen.getAllByText('已定位到 Gemini 的高级渠道：gemini。').length).toBeGreaterThan(0);
    expect(screen.getByTestId('llm-provider-scope')).toHaveTextContent('gemini');
    expect(screen.getByTestId('llm-focus-channel')).toHaveTextContent('gemini');
  });

  it('renders provider quick test action and reports success', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'valid-gemini-key'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));
    testLLMChannel.mockResolvedValue({
      success: true,
      message: 'ok',
      resolvedModel: 'gemini/gemini-2.5-flash',
      latencyMs: 86,
    });

    render(<SettingsPage />);

    await openQuickProviderDrawer('Gemini');
    const providerDrawer = screen.getByRole('dialog', { name: 'Gemini 快速配置' });
    fireEvent.click(within(providerDrawer).getByRole('button', { name: '测试连接' }));

    await waitFor(() => {
      expect(testLLMChannel).toHaveBeenCalledWith(expect.objectContaining({
        protocol: 'gemini',
        name: 'quick_gemini',
      }), expect.any(Object));
    });
    await waitFor(() => {
      expect(within(providerDrawer).getByText(/连接成功/)).toBeInTheDocument();
    });
    expect(within(providerDrawer).getByText(/86 ms/)).toBeInTheDocument();
  });

  it('does not use masked provider placeholders as real API keys', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          { ...buildAiConfigItem('GEMINI_API_KEY', 'sk-...1234'), isMasked: true },
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
        ],
      },
    }));

    render(<SettingsPage />);

    await openQuickProviderDrawer('Gemini');
    const providerDrawer = screen.getByRole('dialog', { name: 'Gemini 快速配置' });
    expect(within(providerDrawer).getByDisplayValue('sk-...1234')).toBeInTheDocument();
    fireEvent.click(within(providerDrawer).getByRole('button', { name: '测试连接' }));

    expect(testLLMChannel).not.toHaveBeenCalled();
    expect(screen.queryByText(/valid-gemini-key/)).not.toBeInTheDocument();
  });

  it('shows provider quick test failure message when test fails', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('OPENAI_API_KEY', 'valid-openai-key'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'openai'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));
    testLLMChannel.mockResolvedValue({
      success: false,
      message: 'model is not available',
      error: 'model is not available',
      resolvedModel: null,
      latencyMs: null,
    });

    render(<SettingsPage />);

    await openQuickProviderDrawer('OpenAI');
    const providerDrawer = screen.getByRole('dialog', { name: 'OpenAI 快速配置' });
    fireEvent.click(within(providerDrawer).getByRole('button', { name: '测试连接' }));

    await waitFor(() => {
      expect(within(providerDrawer).getByText(/model is not available/)).toBeInTheDocument();
    });
  });

  it('prefers advanced channel model/protocol for Zhipu quick test when channel exists', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('ZHIPU_API_KEY', 'valid-zhipu-key'),
          buildAiConfigItem('LLM_CHANNELS', 'zhipu'),
          buildAiConfigItem('LLM_ZHIPU_PROTOCOL', 'openai'),
          buildAiConfigItem('LLM_ZHIPU_BASE_URL', 'https://open.bigmodel.cn/api/paas/v4'),
          buildAiConfigItem('LLM_ZHIPU_MODELS', 'glm-4-flash,glm-5'),
          buildAiConfigItem('LLM_ZHIPU_API_KEY', 'valid-zhipu-key'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'zhipu'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'zhipu/glm-5'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));
    testLLMChannel.mockResolvedValue({
      success: true,
      message: 'ok',
      resolvedModel: 'openai/glm-4-flash',
      latencyMs: 90,
    });

    render(<SettingsPage />);

    await openQuickProviderDrawer('GLM / Zhipu');
    const providerDrawer = screen.getByRole('dialog', { name: 'GLM / Zhipu 快速配置' });
    fireEvent.click(within(providerDrawer).getByRole('button', { name: '测试连接' }));

    await waitFor(() => {
      expect(testLLMChannel).toHaveBeenCalledWith(expect.objectContaining({
        name: 'zhipu',
        protocol: 'openai',
        baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
        models: ['glm-4-flash'],
      }), expect.any(Object));
    });
  });

  it('adds advanced-testing guidance for Zhipu quick test failure without advanced channel', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('ZHIPU_API_KEY', 'valid-zhipu-key'),
          buildAiConfigItem('LLM_CHANNELS', ''),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'zhipu'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'zhipu/glm-5'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));
    testLLMChannel.mockResolvedValue({
      success: false,
      message: 'LLM channel returned empty content',
      error: 'Provider returned an empty response body',
      resolvedModel: 'openai/glm-5',
      latencyMs: 300,
    });

    render(<SettingsPage />);
    await openQuickProviderDrawer('GLM / Zhipu');
    const providerDrawer = screen.getByRole('dialog', { name: 'GLM / Zhipu 快速配置' });
    fireEvent.click(within(providerDrawer).getByRole('button', { name: '测试连接' }));

    await waitFor(() => {
      expect(within(providerDrawer).getByText(/自定义协议测试需经高级渠道/)).toBeInTheDocument();
    });
  });

  it('shows Stock Chat as shared when AGENT_LITELLM_MODEL is not set', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
        agent: [
          {
            ...buildAiConfigItem('AGENT_MODE', 'true'),
            schema: {
              ...buildAiConfigItem('AGENT_MODE', 'true').schema,
              category: 'agent',
            },
          },
          {
            ...buildAiConfigItem('AGENT_LITELLM_MODEL', ''),
            schema: {
              ...buildAiConfigItem('AGENT_LITELLM_MODEL', '').schema,
              category: 'agent',
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const stockTaskRow = screen.getByTestId('ai-task-row-stock_chat');
    expect(within(stockTaskRow).getByText('问股')).toBeInTheDocument();
    expect(within(stockTaskRow).getByText('与分析共用')).toBeInTheDocument();
    expect(within(stockTaskRow).getByText('Gemini / gemini/gemini-2.5-flash')).toBeInTheDocument();
    expect(within(stockTaskRow).getByText(/问股路由：继承分析主路由/)).toBeInTheDocument();
  });

  it('shows Stock Chat as dedicated when AGENT_LITELLM_MODEL is set', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
        agent: [
          {
            ...buildAiConfigItem('AGENT_MODE', 'true'),
            schema: {
              ...buildAiConfigItem('AGENT_MODE', 'true').schema,
              category: 'agent',
            },
          },
          {
            ...buildAiConfigItem('AGENT_LITELLM_MODEL', 'openai/gpt-4.1-mini'),
            schema: {
              ...buildAiConfigItem('AGENT_LITELLM_MODEL', 'openai/gpt-4.1-mini').schema,
              category: 'agent',
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const stockTaskRow = screen.getByTestId('ai-task-row-stock_chat');
    expect(within(stockTaskRow).getByText('问股')).toBeInTheDocument();
    expect(within(stockTaskRow).getByText('独立模型')).toBeInTheDocument();
    expect(within(stockTaskRow).getByText('OpenAI / openai/gpt-4.1-mini')).toBeInTheDocument();
    expect(within(stockTaskRow).getByText(/问股路由：使用独立模型（openai\/gpt-4\.1-mini）/)).toBeInTheDocument();
  });

  it('saves Stock Chat task override route independently', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('OPENAI_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
        agent: [
          {
            ...buildAiConfigItem('AGENT_MODE', 'true'),
            schema: {
              ...buildAiConfigItem('AGENT_MODE', 'true').schema,
              category: 'agent',
            },
          },
          {
            ...buildAiConfigItem('AGENT_LITELLM_MODEL', ''),
            schema: {
              ...buildAiConfigItem('AGENT_LITELLM_MODEL', '').schema,
              category: 'agent',
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const stockTaskCard = within(aiSection).getByTestId('ai-task-card-stock_chat');

    fireEvent.click(within(stockTaskCard as HTMLElement).getByRole('button', { name: '独立覆盖' }));
    fireEvent.click(within(stockTaskCard as HTMLElement).getByRole('button', { name: '显式模型 ID' }));
    const taskCombos = within(stockTaskCard as HTMLElement).getAllByRole('combobox');
    fireEvent.change(taskCombos[0] as HTMLSelectElement, { target: { value: 'openai' } });
    fireEvent.change(taskCombos[1] as HTMLSelectElement, { target: { value: 'openai/gpt-4.1-mini' } });
    fireEvent.click(within(stockTaskCard as HTMLElement).getByRole('button', { name: '保存任务模型' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith([
        { key: 'AGENT_LITELLM_MODEL', value: 'openai/gpt-4.1-mini' },
      ], expect.stringContaining('OpenAI / openai/gpt-4.1-mini'));
    });
  });

  it('supports Backtesting inherit vs override save', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
          buildAiConfigItem('BACKTEST_LITELLM_MODEL', 'openai/gpt-4.1-mini'),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const backtestTaskCard = within(aiSection).getByTestId('ai-task-card-backtest');

    fireEvent.click(within(backtestTaskCard as HTMLElement).getByRole('button', { name: '继承分析路由' }));
    fireEvent.click(within(backtestTaskCard as HTMLElement).getByRole('button', { name: '保存任务模型' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith([
        { key: 'BACKTEST_LITELLM_MODEL', value: '' },
      ], '已恢复继承分析主路由');
    });
  });

  it('blocks save with clear error when primary model is missing', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', ''),
          buildAiConfigItem('LITELLM_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', ''),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');

    fireEvent.change(combos[0] as HTMLSelectElement, { target: { value: 'gemini' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[0] as HTMLButtonElement);
    const customButtons = within(aiSection).getAllByRole('button', { name: '自定义 ID' });
    fireEvent.click(customButtons[0] as HTMLButtonElement);
    const primaryCustomModelInput = within(aiSection).getByLabelText('自定义模型 ID') as HTMLInputElement;
    fireEvent.change(primaryCustomModelInput, { target: { value: '' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    expect(saveExternalItems).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.getByText('主路由必须同时配置网关和模型。')).toBeInTheDocument();
    });
  });

  it('blocks save when backup route is partially filled', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', ''),
          buildAiConfigItem('LITELLM_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', ''),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');
    const primaryGateway = combos[0] as HTMLSelectElement;
    const backupGateway = combos[1] as HTMLSelectElement;
    fireEvent.change(primaryGateway, { target: { value: 'aihubmix' } });
    fireEvent.change(backupGateway, { target: { value: 'gemini' } });

    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[1] as HTMLButtonElement);
    const customButtons = within(aiSection).getAllByRole('button', { name: '自定义 ID' });
    fireEvent.click(customButtons[0] as HTMLButtonElement);
    const backupCustomModelInput = within(aiSection).getByLabelText('自定义模型 ID') as HTMLInputElement;
    fireEvent.change(backupCustomModelInput, { target: { value: '' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    expect(saveExternalItems).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.getByText('备用路由配置缺失：需同时设置网关与模型，或全部清空。')).toBeInTheDocument();
    });
  });
});
