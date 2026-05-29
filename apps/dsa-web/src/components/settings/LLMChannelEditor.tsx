import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type React from 'react';
import type { ParsedApiError } from '../../api/error';
import { getParsedApiError } from '../../api/error';
import { systemConfigApi } from '../../api/systemConfig';
import { useI18n } from '../../contexts/UiLanguageContext';
import type { SystemConfigUpdateItem } from '../../types/systemConfig';
import { ApiErrorAlert } from '../common/ApiErrorAlert';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { Input } from '../common/Input';
import { Select } from '../common/Select';
import { SupportBanner, SupportPanel } from '../common/SupportSurface';

type ChannelProtocol = 'openai' | 'deepseek' | 'gemini' | 'anthropic' | 'vertex_ai' | 'ollama';

const CONTROL_GHOST_BUTTON_CLASS = 'px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/10 hover:bg-white/10 text-xs transition-colors';
const GHOST_TAG_CLASS = 'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] uppercase tracking-widest font-bold bg-white/5 text-white/40 border border-white/5';
const DRAWER_LABEL_CLASS = 'text-[10px] uppercase tracking-widest text-white/40 mb-1.5 font-bold block';
const DRAWER_ADVANCED_SUMMARY_CLASS = 'mt-4 flex cursor-pointer list-none items-center gap-1.5 border-t border-white/5 pt-4 text-xs text-white/30 transition-colors hover:text-white [&::-webkit-details-marker]:hidden';

interface ChannelPreset {
  label: string;
  protocol: ChannelProtocol;
  baseUrl: string;
  placeholder: string;
}

const CHANNEL_PRESETS: Record<string, ChannelPreset> = {
  aihubmix: {
    label: 'AIHubmix（聚合平台）',
    protocol: 'openai',
    baseUrl: 'https://aihubmix.com/v1',
    placeholder: 'gpt-4o-mini,claude-3-5-sonnet,qwen-plus',
  },
  deepseek: {
    label: 'DeepSeek 官方',
    protocol: 'deepseek',
    baseUrl: 'https://api.deepseek.com/v1',
    placeholder: 'deepseek-chat,deepseek-v4-pro,deepseek-v4-flash,deepseek-reasoner',
  },
  dashscope: {
    label: '通义千问（Dashscope）',
    protocol: 'openai',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    placeholder: 'qwen-plus,qwen-turbo',
  },
  zhipu: {
    label: '智谱 GLM',
    protocol: 'openai',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    placeholder: 'glm-4-flash,glm-4-plus',
  },
  moonshot: {
    label: 'Moonshot（月之暗面）',
    protocol: 'openai',
    baseUrl: 'https://api.moonshot.cn/v1',
    placeholder: 'moonshot-v1-8k',
  },
  siliconflow: {
    label: '硅基流动（SiliconFlow）',
    protocol: 'openai',
    baseUrl: 'https://api.siliconflow.cn/v1',
    placeholder: 'Qwen/Qwen3-8B,deepseek-ai/DeepSeek-V3',
  },
  openrouter: {
    label: 'OpenRouter',
    protocol: 'openai',
    baseUrl: 'https://openrouter.ai/api/v1',
    placeholder: 'openai/gpt-4o,anthropic/claude-3-5-sonnet',
  },
  gemini: {
    label: 'Gemini 官方',
    protocol: 'gemini',
    baseUrl: '',
    placeholder: 'gemini-2.5-flash,gemini-2.5-pro',
  },
  anthropic: {
    label: 'Anthropic 官方',
    protocol: 'anthropic',
    baseUrl: '',
    placeholder: 'claude-3-5-sonnet-20241022',
  },
  openai: {
    label: 'OpenAI 官方',
    protocol: 'openai',
    baseUrl: 'https://api.openai.com/v1',
    placeholder: 'gpt-4o,gpt-4o-mini',
  },
  ollama: {
    label: 'Ollama（本地）',
    protocol: 'ollama',
    baseUrl: 'http://127.0.0.1:11434',
    placeholder: 'llama3.2,qwen2.5',
  },
  custom: {
    label: '自定义渠道',
    protocol: 'openai',
    baseUrl: '',
    placeholder: 'model-name-1,model-name-2',
  },
};

const PROTOCOL_OPTIONS: Array<{ value: ChannelProtocol; label: string }> = [
  { value: 'openai', label: 'OpenAI Compatible' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'vertex_ai', label: 'Vertex AI' },
  { value: 'ollama', label: 'Ollama' },
];

const MODEL_PLACEHOLDERS: Record<ChannelProtocol, string> = {
  openai: 'gpt-4o-mini,deepseek-chat,qwen-plus',
  deepseek: 'deepseek-chat,deepseek-v4-pro,deepseek-v4-flash,deepseek-reasoner',
  gemini: 'gemini-2.5-flash,gemini-2.5-pro',
  anthropic: 'claude-3-5-sonnet-20241022',
  vertex_ai: 'gemini-2.5-flash',
  ollama: 'llama3.2,qwen2.5',
};

const KNOWN_MODEL_PREFIXES = new Set([
  'openai',
  'anthropic',
  'gemini',
  'vertex_ai',
  'deepseek',
  'ollama',
  'cohere',
  'huggingface',
  'bedrock',
  'sagemaker',
  'azure',
  'replicate',
  'together_ai',
  'palm',
  'text-completion-openai',
  'command-r',
  'groq',
  'cerebras',
  'fireworks_ai',
  'friendliai',
]);

const FALSEY_VALUES = new Set(['0', 'false', 'no', 'off']);

interface ChannelConfig {
  name: string;
  protocol: ChannelProtocol;
  baseUrl: string;
  apiKey: string;
  models: string;
  extraHeaders: string;
  enabled: boolean;
}

interface ChannelTestState {
  status: 'idle' | 'loading' | 'success' | 'error';
  text?: string;
}

interface RuntimeConfig {
  primaryModel: string;
  agentPrimaryModel: string;
  fallbackModels: string[];
  visionModel: string;
  temperature: string;
}

interface LLMChannelEditorProps {
  items: Array<{ key: string; value: string }>;
  onSaveItems: (
    updatedItems: SystemConfigUpdateItem[],
    successMessage: string
  ) => void | Promise<void>;
  adminUnlockToken?: string | null;
  disabled?: boolean;
  providerScopeName?: string;
  focusChannelName?: string;
  externalCreatePreset?: string | null;
  onExternalCreateHandled?: () => void;
}

interface ChannelRowProps {
  channel: ChannelConfig;
  index: number;
  busy: boolean;
  visibleKey: boolean;
  expanded: boolean;
  testState?: ChannelTestState;
  t: (key: string, vars?: Record<string, string | number | undefined>) => string;
  presetLabels: Record<string, string>;
  onUpdate: (index: number, field: keyof ChannelConfig, value: string | boolean) => void;
  onRemove: (index: number) => void;
  onToggleExpand: (index: number) => void;
  onToggleKeyVisibility: (index: number, nextVisible: boolean) => void;
  onTest: (channel: ChannelConfig, index: number) => void;
}

const ChannelRow: React.FC<ChannelRowProps> = ({
  channel,
  index,
  busy,
  visibleKey,
  expanded,
  testState,
  t,
  presetLabels,
  onUpdate,
  onRemove,
  onToggleExpand,
  onToggleKeyVisibility,
  onTest,
}) => {
  const preset = CHANNEL_PRESETS[channel.name];
  const displayName = presetLabels[channel.name] || preset?.label || channel.name;
  const modelCount = splitModels(channel.models).length;
  const hasKey = channel.apiKey.length > 0;
  const statusVariant = testState?.status === 'success'
    ? 'success'
    : testState?.status === 'error'
      ? 'danger'
      : testState?.status === 'loading'
        ? 'warning'
        : 'default';

  return (
    <div className="mb-2 overflow-hidden rounded-xl border settings-border settings-surface shadow-soft-card transition-all hover:settings-surface-hover">
      <div
        className="flex cursor-pointer select-none items-center gap-2.5 px-4 py-3 transition-colors hover:settings-surface-hover"
        onClick={() => onToggleExpand(index)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggleExpand(index);
          }
        }}
        role="button"
        tabIndex={0}
      >
        <span className={`w-4 shrink-0 text-[11px] text-muted-text transition-transform ${expanded ? 'rotate-90' : ''}`}>▶</span>

        <input
          type="checkbox"
          checked={channel.enabled}
          disabled={busy}
          aria-label={`${channel.name} enabled`}
          className="settings-input-checkbox size-4 shrink-0 rounded border-border/70 bg-base"
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => onUpdate(index, 'enabled', e.target.checked)}
        />

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-foreground">{displayName}</span>
            <Badge variant="info" className="hidden sm:inline-flex">
              {channel.protocol}
            </Badge>
          </div>
          <p className="mt-0.5 truncate text-[11px] text-secondary-text">
            {modelCount > 0 ? t('settings.llmEditor.statusModelCount', { count: modelCount }) : t('settings.llmEditor.statusModelEmpty')}
          </p>
        </div>

        <span className="flex shrink-0 items-center gap-2">
          {testState?.status === 'success' ? <span className="size-2 rounded-full bg-[var(--accent-positive)]" title={t('settings.llmEditor.statusSuccess')} /> : null}
          {testState?.status === 'error' ? <span className="size-2 rounded-full bg-[var(--accent-danger)]" title={t('settings.llmEditor.statusError')} /> : null}
          {testState?.status === 'loading' ? <span className="size-2 rounded-full bg-[var(--accent-warning)] animate-pulse" title={t('settings.llmEditor.statusLoading')} /> : null}
          {!hasKey && channel.protocol !== 'ollama' ? <Badge variant="warning">{t('settings.llmEditor.statusMissingKey')}</Badge> : null}
          {testState?.status !== 'idle' ? (
            <Badge variant={statusVariant}>
              {testState?.status === 'success'
                ? t('settings.llmEditor.statusSuccess')
                : testState?.status === 'error'
                  ? t('settings.llmEditor.statusError')
                  : t('settings.llmEditor.statusLoading')}
            </Badge>
          ) : null}
        </span>

        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 shrink-0 px-2 text-xs text-muted-text hover:text-danger"
          disabled={busy}
          onClick={(e) => {
            e.stopPropagation();
            onRemove(index);
          }}
          title={t('settings.llmEditor.deleteChannelTitle')}
          aria-label={t('settings.llmEditor.deleteChannelTitle')}
        >
          ✕
        </Button>
      </div>

      {expanded ? (
        <div className="space-y-3 bg-white/[0.01] p-4">
          <Input
            label={t('settings.llmEditor.fieldApiKey')}
            type="password"
            allowTogglePassword
            iconType="key"
            passwordVisible={visibleKey}
            onPasswordVisibleChange={(nextVisible) => onToggleKeyVisibility(index, nextVisible)}
            value={channel.apiKey}
            disabled={busy}
            onChange={(e) => onUpdate(index, 'apiKey', e.target.value)}
            placeholder={channel.protocol === 'ollama'
              ? t('settings.llmEditor.placeholderApiKeyLocal')
              : t('settings.llmEditor.placeholderApiKeyMulti')}
          />

          <Input
            label={t('settings.llmEditor.fieldModels')}
            value={channel.models}
            disabled={busy}
            onChange={(e) => onUpdate(index, 'models', e.target.value)}
            placeholder={preset?.placeholder || MODEL_PLACEHOLDERS[channel.protocol]}
          />

          <details>
            <summary className={DRAWER_ADVANCED_SUMMARY_CLASS}>
              配置高级参数 (Advanced Settings) ▾
            </summary>
            <div className="mt-3 space-y-3">
              <div className="grid gap-2 sm:grid-cols-2">
                <Input
                  label={t('settings.llmEditor.fieldName')}
                  value={channel.name}
                  disabled={busy}
                  onChange={(e) => onUpdate(index, 'name', e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                  placeholder={t('settings.llmEditor.placeholderName')}
                />
                <div>
                  <label className={DRAWER_LABEL_CLASS}>{t('settings.llmEditor.fieldProtocol')}</label>
                  <Select
                    value={channel.protocol}
                    onChange={(v) => onUpdate(index, 'protocol', normalizeProtocol(v))}
                    options={PROTOCOL_OPTIONS}
                    disabled={busy}
                    placeholder={t('settings.llmEditor.placeholderProtocol')}
                  />
                </div>
              </div>

              <Input
                label={t('settings.llmEditor.fieldBaseUrl')}
                value={channel.baseUrl}
                disabled={busy}
                onChange={(e) => onUpdate(index, 'baseUrl', e.target.value)}
                placeholder={
                  channel.protocol === 'gemini' || channel.protocol === 'anthropic'
                    ? t('settings.llmEditor.placeholderOfficialEmpty')
                    : preset?.baseUrl || t('settings.llmEditor.placeholderBaseUrl')
                }
              />

              <Input
                label={t('settings.llmEditor.fieldExtraHeaders')}
                value={channel.extraHeaders}
                disabled={busy}
                onChange={(e) => onUpdate(index, 'extraHeaders', e.target.value)}
                placeholder='{"x-env":"staging"}'
                hint={t('settings.llmEditor.extraHeadersHint')}
              />
            </div>
          </details>

          <div className="flex flex-wrap items-center gap-2 border-t settings-border-soft pt-3">
            <Button
              type="button"
              variant="settings-secondary"
              size="sm"
              className={CONTROL_GHOST_BUTTON_CLASS}
              disabled={busy}
              onClick={() => onTest(channel, index)}
            >
              {testState?.status === 'loading' ? t('settings.llmEditor.testingAction') : t('settings.llmEditor.testAction')}
            </Button>
            {testState?.text ? (
              <span
                className={GHOST_TAG_CLASS}
                data-status={testState.status}
              >
                {testState.text}
              </span>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
};

function normalizeProtocol(value: string): ChannelProtocol {
  const normalized = value.trim().toLowerCase().replace(/-/g, '_');
  if (normalized === 'vertex' || normalized === 'vertexai') {
    return 'vertex_ai';
  }
  if (normalized === 'claude') {
    return 'anthropic';
  }
  if (normalized === 'google') {
    return 'gemini';
  }
  if (normalized === 'deepseek') {
    return 'deepseek';
  }
  if (normalized === 'gemini') {
    return 'gemini';
  }
  if (normalized === 'anthropic') {
    return 'anthropic';
  }
  if (normalized === 'vertex_ai') {
    return 'vertex_ai';
  }
  if (normalized === 'ollama') {
    return 'ollama';
  }
  return 'openai';
}

function inferProtocol(protocol: string, baseUrl: string, models: string[]): ChannelProtocol {
  const explicit = normalizeProtocol(protocol);
  if (protocol.trim()) {
    return explicit;
  }

  const firstPrefixedModel = models.find((model) => model.includes('/'));
  if (firstPrefixedModel) {
    return normalizeProtocol(firstPrefixedModel.split('/', 1)[0]);
  }

  if (baseUrl.includes('127.0.0.1') || baseUrl.includes('localhost')) {
    return 'openai';
  }

  return 'openai';
}

function parseEnabled(value: string | undefined): boolean {
  if (!value) {
    return true;
  }
  return !FALSEY_VALUES.has(value.trim().toLowerCase());
}

function splitModels(models: string): string[] {
  return models
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean);
}

const PROTOCOL_ALIASES: Record<string, string> = {
  vertexai: 'vertex_ai',
  vertex: 'vertex_ai',
  claude: 'anthropic',
  google: 'gemini',
  openai_compatible: 'openai',
  openai_compat: 'openai',
};

function normalizeModelForRuntime(model: string, protocol: ChannelProtocol): string {
  const trimmedModel = model.trim();
  if (!trimmedModel) {
    return trimmedModel;
  }

  if (trimmedModel.includes('/')) {
    const rawPrefix = trimmedModel.split('/', 1)[0].trim();
    const lowerPrefix = rawPrefix.toLowerCase();
    const canonicalPrefix = PROTOCOL_ALIASES[lowerPrefix] || lowerPrefix;
    if (KNOWN_MODEL_PREFIXES.has(lowerPrefix) || KNOWN_MODEL_PREFIXES.has(canonicalPrefix)) {
      if (canonicalPrefix !== lowerPrefix && KNOWN_MODEL_PREFIXES.has(canonicalPrefix)) {
        return `${canonicalPrefix}/${trimmedModel.split('/').slice(1).join('/')}`;
      }
      return trimmedModel;
    }
    return `${protocol}/${trimmedModel}`;
  }

  return `${protocol}/${trimmedModel}`;
}

function resolveModelPreview(models: string, protocol: ChannelProtocol): string[] {
  return splitModels(models).map((model) => normalizeModelForRuntime(model, protocol));
}

function buildModelOptions(models: string[], selectedModel: string, autoLabel: string): Array<{ value: string; label: string }> {
  const options: Array<{ value: string; label: string }> = [{ value: '', label: autoLabel }];
  if (selectedModel && !models.includes(selectedModel)) {
    options.push({ value: selectedModel, label: `${selectedModel}（当前配置）` });
  }
  for (const model of models) {
    options.push({ value: model, label: model });
  }
  return options;
}

const MANAGED_PROVIDERS = new Set(['gemini', 'vertex_ai', 'anthropic', 'openai', 'deepseek']);

function usesDirectEnvProvider(model: string): boolean {
  if (!model || !model.includes('/')) return false;
  const provider = model.split('/', 1)[0].trim().toLowerCase();
  return Boolean(provider) && !MANAGED_PROVIDERS.has(provider);
}

function providerHasLegacyApiKey(provider: string, itemMap: Map<string, string>): boolean {
  const normalized = provider.trim().toLowerCase();
  if (!normalized) return false;
  const hasAny = (keys: string[]): boolean => keys.some((key) => Boolean((itemMap.get(key) || '').trim()));
  if (normalized === 'gemini' || normalized === 'vertex_ai') {
    return hasAny(['GEMINI_API_KEYS', 'GEMINI_API_KEY']);
  }
  if (normalized === 'anthropic') {
    return hasAny(['ANTHROPIC_API_KEYS', 'ANTHROPIC_API_KEY']);
  }
  if (normalized === 'deepseek') {
    return hasAny(['DEEPSEEK_API_KEYS', 'DEEPSEEK_API_KEY']);
  }
  if (normalized === 'openai') {
    return hasAny(['OPENAI_API_KEYS', 'OPENAI_API_KEY', 'AIHUBMIX_KEY', 'AIHUBMIX_KEYS']);
  }
  return false;
}

function hasRuntimeSourceForModel(model: string, availableModels: string[], itemMap: Map<string, string>): boolean {
  const normalized = (model || '').trim();
  if (!normalized) return true;
  if (availableModels.includes(normalized)) return true;
  if (usesDirectEnvProvider(normalized)) return true;
  const provider = normalized.includes('/') ? normalized.split('/', 1)[0].trim().toLowerCase() : 'openai';
  return providerHasLegacyApiKey(provider, itemMap);
}

function resolveTemperatureFromItems(itemMap: Map<string, string>): string {
  const unified = itemMap.get('LLM_TEMPERATURE');
  if (unified) return unified;

  const primaryModel = itemMap.get('LITELLM_MODEL') || '';
  const provider = primaryModel.includes('/') ? primaryModel.split('/')[0] : (primaryModel ? 'openai' : '');
  const providerTemperatureEnv: Record<string, string> = {
    gemini: 'GEMINI_TEMPERATURE',
    vertex_ai: 'GEMINI_TEMPERATURE',
    anthropic: 'ANTHROPIC_TEMPERATURE',
    openai: 'OPENAI_TEMPERATURE',
    deepseek: 'OPENAI_TEMPERATURE',
  };
  const preferredEnv = providerTemperatureEnv[provider];
  if (preferredEnv) {
    const val = itemMap.get(preferredEnv);
    if (val) return val;
  }

  for (const envName of ['GEMINI_TEMPERATURE', 'ANTHROPIC_TEMPERATURE', 'OPENAI_TEMPERATURE']) {
    const val = itemMap.get(envName);
    if (val) return val;
  }

  return '0.7';
}

function normalizeAgentPrimaryModel(model: string): string {
  const trimmedModel = model.trim();
  if (!trimmedModel) {
    return '';
  }
  if (trimmedModel.includes('/')) {
    return trimmedModel;
  }
  return `openai/${trimmedModel}`;
}

function parseRuntimeConfigFromItems(items: Array<{ key: string; value: string }>): RuntimeConfig {
  const itemMap = new Map(items.map((item) => [item.key, item.value]));
  return {
    primaryModel: itemMap.get('LITELLM_MODEL') || '',
    agentPrimaryModel: normalizeAgentPrimaryModel(itemMap.get('AGENT_LITELLM_MODEL') || ''),
    fallbackModels: splitModels(itemMap.get('LITELLM_FALLBACK_MODELS') || ''),
    visionModel: itemMap.get('VISION_MODEL') || '',
    temperature: resolveTemperatureFromItems(itemMap),
  };
}

function collectAvailableModels(channels: ChannelConfig[]): string[] {
  const seen = new Set<string>();
  const models: string[] = [];
  for (const channel of channels) {
    if (!channel.enabled || !channel.name.trim()) {
      continue;
    }
    for (const model of resolveModelPreview(channel.models, channel.protocol)) {
      if (!model || seen.has(model)) {
        continue;
      }
      seen.add(model);
      models.push(model);
    }
  }
  return models;
}

function parseChannelsFromItems(items: Array<{ key: string; value: string }>): ChannelConfig[] {
  const itemMap = new Map(items.map((item) => [item.key, item.value]));
  const channelNames = (itemMap.get('LLM_CHANNELS') || '')
    .split(',')
    .map((segment) => segment.trim())
    .filter(Boolean);

  return channelNames.map((name) => {
    const upperName = name.toUpperCase();
    const baseUrl = itemMap.get(`LLM_${upperName}_BASE_URL`) || '';
    const rawModels = itemMap.get(`LLM_${upperName}_MODELS`) || '';
    const models = splitModels(rawModels);

    return {
      name: name.toLowerCase(),
      protocol: inferProtocol(itemMap.get(`LLM_${upperName}_PROTOCOL`) || '', baseUrl, models),
      baseUrl,
      apiKey: itemMap.get(`LLM_${upperName}_API_KEYS`) || itemMap.get(`LLM_${upperName}_API_KEY`) || '',
      models: rawModels,
      extraHeaders: itemMap.get(`LLM_${upperName}_EXTRA_HEADERS`) || '',
      enabled: parseEnabled(itemMap.get(`LLM_${upperName}_ENABLED`)),
    };
  });
}

function channelsToUpdateItems(
  channels: ChannelConfig[],
  previousChannelNames: string[],
  runtimeConfig: RuntimeConfig,
  includeRuntimeConfig: boolean,
): Array<{ key: string; value: string }> {
  const updates: Array<{ key: string; value: string }> = [];
  const activeNames = new Set(channels.map((channel) => channel.name.toUpperCase()));

  updates.push({ key: 'LLM_CHANNELS', value: channels.map((channel) => channel.name).join(',') });
  if (includeRuntimeConfig) {
    updates.push({ key: 'LITELLM_MODEL', value: runtimeConfig.primaryModel });
    updates.push({ key: 'AGENT_LITELLM_MODEL', value: runtimeConfig.agentPrimaryModel });
    updates.push({ key: 'LITELLM_FALLBACK_MODELS', value: runtimeConfig.fallbackModels.join(',') });
    updates.push({ key: 'VISION_MODEL', value: runtimeConfig.visionModel });
    updates.push({ key: 'LLM_TEMPERATURE', value: runtimeConfig.temperature });
  }

  for (const channel of channels) {
    const prefix = `LLM_${channel.name.toUpperCase()}`;
    const isMultiKey = channel.apiKey.includes(',');
    updates.push({ key: `${prefix}_PROTOCOL`, value: channel.protocol });
    updates.push({ key: `${prefix}_BASE_URL`, value: channel.baseUrl });
    updates.push({ key: `${prefix}_ENABLED`, value: channel.enabled ? 'true' : 'false' });
    updates.push({ key: `${prefix}_API_KEY${isMultiKey ? 'S' : ''}`, value: channel.apiKey });
    updates.push({ key: `${prefix}_API_KEY${isMultiKey ? '' : 'S'}`, value: '' });
    updates.push({ key: `${prefix}_MODELS`, value: channel.models });
    updates.push({ key: `${prefix}_EXTRA_HEADERS`, value: channel.extraHeaders });
  }

  for (const oldName of previousChannelNames) {
    const upperName = oldName.toUpperCase();
    if (activeNames.has(upperName)) {
      continue;
    }

    const prefix = `LLM_${upperName}`;
    updates.push({ key: `${prefix}_PROTOCOL`, value: '' });
    updates.push({ key: `${prefix}_BASE_URL`, value: '' });
    updates.push({ key: `${prefix}_ENABLED`, value: '' });
    updates.push({ key: `${prefix}_API_KEY`, value: '' });
    updates.push({ key: `${prefix}_API_KEYS`, value: '' });
    updates.push({ key: `${prefix}_MODELS`, value: '' });
    updates.push({ key: `${prefix}_EXTRA_HEADERS`, value: '' });
  }

  return updates;
}

function channelsAreEqual(left: ChannelConfig, right: ChannelConfig): boolean {
  return (
    left.name === right.name
    && left.protocol === right.protocol
    && left.baseUrl === right.baseUrl
    && left.apiKey === right.apiKey
    && left.models === right.models
    && left.extraHeaders === right.extraHeaders
    && left.enabled === right.enabled
  );
}

function normalizeProviderScopeName(value?: string): string {
  return String(value || '').trim().toLowerCase();
}

function resolveChannelScopeName(channelName: string): string {
  const normalizedName = normalizeProviderScopeName(channelName);
  if (!normalizedName) {
    return '';
  }
  const baseName = normalizedName.replace(/\d+$/, '');
  return CHANNEL_PRESETS[baseName] ? baseName : normalizedName;
}

export const LLMChannelEditor: React.FC<LLMChannelEditorProps> = ({
  items,
  onSaveItems,
  adminUnlockToken,
  disabled = false,
  providerScopeName = '',
  focusChannelName = '',
  externalCreatePreset = null,
  onExternalCreateHandled,
}) => {
  const { t } = useI18n();
  const normalizedScopeName = normalizeProviderScopeName(providerScopeName);
  const scopedPreset = normalizedScopeName ? CHANNEL_PRESETS[normalizedScopeName] : null;
  const providerScopedMode = Boolean(normalizedScopeName && scopedPreset);
  const rawItemMap = useMemo(() => new Map(items.map((item) => [item.key, item.value])), [items]);
  const initialChannels = useMemo(() => parseChannelsFromItems(items), [items]);
  const initialNames = useMemo(() => initialChannels.map((channel) => channel.name), [initialChannels]);
  const initialRuntimeConfig = useMemo(() => parseRuntimeConfigFromItems(items), [items]);
  const hasLitellmConfig = useMemo(
    () => items.some((item) => item.key === 'LITELLM_CONFIG' && item.value.trim().length > 0),
    [items],
  );
  const managesRuntimeConfig = !hasLitellmConfig;

  const channelsFingerprint = useMemo(() => JSON.stringify(initialChannels), [initialChannels]);
  const runtimeFingerprint = useMemo(() => JSON.stringify(initialRuntimeConfig), [initialRuntimeConfig]);

  const [channels, setChannels] = useState<ChannelConfig[]>(initialChannels);
  const [runtimeConfig, setRuntimeConfig] = useState<RuntimeConfig>(initialRuntimeConfig);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<
    | { type: 'success'; text: string }
    | { type: 'error'; error: ParsedApiError }
    | { type: 'local-error'; text: string }
    | null
  >(null);
  const [visibleKeys, setVisibleKeys] = useState<Record<number, boolean>>({});
  const [testStates, setTestStates] = useState<Record<number, ChannelTestState>>({});
  const [expandedRows, setExpandedRows] = useState<Record<number, boolean>>({});
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [addPreset, setAddPreset] = useState(normalizedScopeName || 'aihubmix');
  const presetLabels = useMemo(
    () => Object.fromEntries(Object.keys(CHANNEL_PRESETS).map((key) => [key, t(`settings.llmEditor.channelPreset.${key}`)])),
    [t],
  );

  const prevChannelsRef = useRef(channelsFingerprint);
  const prevRuntimeRef = useRef(runtimeFingerprint);
  const channelRowRefs = useRef<Record<number, HTMLDivElement | null>>({});

  useEffect(() => {
    if (prevChannelsRef.current === channelsFingerprint && prevRuntimeRef.current === runtimeFingerprint) {
      return;
    }
    prevChannelsRef.current = channelsFingerprint;
    prevRuntimeRef.current = runtimeFingerprint;
    setChannels(initialChannels);
    setRuntimeConfig(initialRuntimeConfig);
    setVisibleKeys({});
    setTestStates({});
    setExpandedRows({});
    setSaveMessage(null);
    setIsCollapsed(false);
  }, [channelsFingerprint, runtimeFingerprint, initialChannels, initialRuntimeConfig]);

  useEffect(() => {
    if (!providerScopedMode) {
      return;
    }
    setAddPreset(normalizedScopeName);
  }, [normalizedScopeName, providerScopedMode]);

  const availableModels = useMemo(() => {
    if (!managesRuntimeConfig) {
      return [];
    }
    return collectAvailableModels(channels);
  }, [channels, managesRuntimeConfig]);

  const hasChanges = useMemo(() => {
    const runtimeChanged = (
      runtimeConfig.primaryModel !== initialRuntimeConfig.primaryModel
      || runtimeConfig.agentPrimaryModel !== initialRuntimeConfig.agentPrimaryModel
      || runtimeConfig.visionModel !== initialRuntimeConfig.visionModel
      || runtimeConfig.temperature !== initialRuntimeConfig.temperature
      || runtimeConfig.fallbackModels.join(',') !== initialRuntimeConfig.fallbackModels.join(',')
    );

    if (runtimeChanged || channels.length !== initialChannels.length) {
      return true;
    }
    return channels.some((channel, index) => !channelsAreEqual(channel, initialChannels[index]));
  }, [channels, initialChannels, initialRuntimeConfig, runtimeConfig]);

  const visibleChannelEntries = useMemo(() => {
    return channels
      .map((channel, index) => ({ channel, index }))
      .filter((entry) => {
        if (!providerScopedMode) {
          return true;
        }
        return resolveChannelScopeName(entry.channel.name) === normalizedScopeName;
      });
  }, [channels, normalizedScopeName, providerScopedMode]);

  const busy = disabled || isSaving;

  const updateChannel = (index: number, field: keyof ChannelConfig, value: string | boolean) => {
    setChannels((previous) => previous.map((channel, rowIndex) => {
      if (rowIndex !== index) return channel;
      const updated = { ...channel, [field]: value };

      if (field === 'name' && typeof value === 'string') {
        const newPreset = CHANNEL_PRESETS[value];
        if (newPreset) {
          const oldPreset = CHANNEL_PRESETS[channel.name];
          if (!updated.baseUrl || updated.baseUrl === (oldPreset?.baseUrl ?? '')) {
            updated.baseUrl = newPreset.baseUrl;
          }
          updated.protocol = newPreset.protocol;
          if (!updated.models || updated.models === (oldPreset?.placeholder ?? '')) {
            updated.models = newPreset.placeholder;
          }
        }
      }

      return updated;
    }));
    setTestStates((previous) => {
      if (!(index in previous)) {
        return previous;
      }
      const next = { ...previous };
      delete next[index];
      return next;
    });
  };

  const removeChannel = (index: number) => {
    setChannels((previous) => {
      const nextChannels = previous.filter((_, rowIndex) => rowIndex !== index);
      if (managesRuntimeConfig) {
        const nextAvailableModels = collectAvailableModels(nextChannels);
        setRuntimeConfig((previousRuntime) => ({
          ...previousRuntime,
          primaryModel: hasRuntimeSourceForModel(previousRuntime.primaryModel, nextAvailableModels, rawItemMap)
            ? previousRuntime.primaryModel
            : '',
          agentPrimaryModel: hasRuntimeSourceForModel(previousRuntime.agentPrimaryModel, nextAvailableModels, rawItemMap)
            ? previousRuntime.agentPrimaryModel
            : '',
          visionModel: hasRuntimeSourceForModel(previousRuntime.visionModel, nextAvailableModels, rawItemMap)
            ? previousRuntime.visionModel
            : '',
          fallbackModels: previousRuntime.fallbackModels.filter((model) => hasRuntimeSourceForModel(model, nextAvailableModels, rawItemMap)),
        }));
      }
      return nextChannels;
    });
    setVisibleKeys({});
    setTestStates({});
    setExpandedRows({});
  };

  const addChannel = useCallback((presetKey?: string) => {
    const nextPresetKey = presetKey || addPreset;
      const preset = CHANNEL_PRESETS[nextPresetKey] || CHANNEL_PRESETS.custom;
    const baseName = nextPresetKey === 'custom' ? 'custom' : nextPresetKey;
    let nextIndex = 0;
    setChannels((previous) => {
      const existingNames = new Set(previous.map((channel) => channel.name));
      let nextName = baseName;
      let counter = 2;
      while (existingNames.has(nextName)) {
        nextName = `${baseName}${counter}`;
        counter += 1;
      }
      nextIndex = previous.length;

      return [
        ...previous,
        {
          name: nextName,
          protocol: preset.protocol,
          baseUrl: preset.baseUrl,
          apiKey: '',
          models: preset.placeholder || '',
          extraHeaders: '',
          enabled: true,
        },
      ];
    });
    setTestStates({});
    setExpandedRows((prev) => ({ ...prev, [nextIndex]: true }));
    setIsCollapsed(false);
    window.setTimeout(() => {
      channelRowRefs.current[nextIndex]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 0);
  }, [addPreset]);
  useEffect(() => {
    const requestedPreset = String(externalCreatePreset || '').trim().toLowerCase();
    if (!requestedPreset) return;
    setAddPreset(requestedPreset);
    addChannel(requestedPreset);
    onExternalCreateHandled?.();
  }, [addChannel, externalCreatePreset, onExternalCreateHandled]);
  useEffect(() => {
    const targetName = String(focusChannelName || '').trim().toLowerCase();
    if (!targetName) return;
    const targetIndex = channels.findIndex((channel) => channel.name.trim().toLowerCase() === targetName);
    if (targetIndex < 0) return;
    setIsCollapsed(false);
    setExpandedRows((prev) => ({ ...prev, [targetIndex]: true }));
    window.setTimeout(() => {
      channelRowRefs.current[targetIndex]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 0);
  }, [channels, focusChannelName]);

  const handleSave = async () => {
    const hasEmptyName = channels.some((channel) => !channel.name.trim());
    if (hasEmptyName) {
      setSaveMessage({ type: 'local-error', text: t('settings.llmEditor.validationEmptyName') });
      return;
    }

    if (managesRuntimeConfig && availableModels.length > 0) {
      const invalidPrimaryModel = runtimeConfig.primaryModel
        && !hasRuntimeSourceForModel(runtimeConfig.primaryModel, availableModels, rawItemMap);
      if (invalidPrimaryModel) {
        setSaveMessage({ type: 'local-error', text: t('settings.llmEditor.validationPrimaryModel') });
        return;
      }

      const invalidAgentPrimaryModel = runtimeConfig.agentPrimaryModel
        && !hasRuntimeSourceForModel(runtimeConfig.agentPrimaryModel, availableModels, rawItemMap);
      if (invalidAgentPrimaryModel) {
        setSaveMessage({ type: 'local-error', text: t('settings.llmEditor.validationAgentModel') });
        return;
      }

      const invalidFallbackModel = runtimeConfig.fallbackModels.some(
        (model) => !hasRuntimeSourceForModel(model, availableModels, rawItemMap),
      );
      if (invalidFallbackModel) {
        setSaveMessage({
          type: 'local-error',
          text: t('settings.llmEditor.validationFallbackRuntimeOnly'),
        });
        return;
      }

      const invalidVisionModel = runtimeConfig.visionModel
        && !hasRuntimeSourceForModel(runtimeConfig.visionModel, availableModels, rawItemMap);
      if (invalidVisionModel) {
        setSaveMessage({ type: 'local-error', text: t('settings.llmEditor.validationVisionModel') });
        return;
      }
    }

    setIsSaving(true);
    setSaveMessage(null);

    try {
      const updateItems = channelsToUpdateItems(channels, initialNames, runtimeConfig, managesRuntimeConfig);
      const successMessage = managesRuntimeConfig
        ? t('settings.llmEditor.saveRuntimeSuccess')
        : t('settings.llmEditor.saveChannelsSuccess');
      await onSaveItems(updateItems, successMessage);
      setSaveMessage({ type: 'success', text: successMessage });
    } catch (error: unknown) {
      setSaveMessage({ type: 'error', error: getParsedApiError(error) });
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async (channel: ChannelConfig, index: number) => {
    setTestStates((previous) => ({
      ...previous,
      [index]: { status: 'loading', text: t('settings.llmEditor.testingAction') },
    }));

    try {
      const result = await systemConfigApi.testLLMChannel({
        name: channel.name,
        protocol: channel.protocol,
        baseUrl: channel.baseUrl,
        apiKey: channel.apiKey,
        models: splitModels(channel.models),
        enabled: channel.enabled,
      }, { adminUnlockToken });

      const text = result.success
        ? (result.resolvedModel && result.latencyMs
          ? t('settings.llmEditor.testSuccess', { model: result.resolvedModel, latency: result.latencyMs })
          : t('settings.llmEditor.testSuccessNoModel'))
        : (result.error || result.message || t('settings.llmEditor.statusError'));

      setTestStates((previous) => ({
        ...previous,
        [index]: {
          status: result.success ? 'success' : 'error',
          text,
        },
      }));
    } catch (error: unknown) {
      const parsed = getParsedApiError(error);
      setTestStates((previous) => ({
        ...previous,
        [index]: { status: 'error', text: parsed.message || t('settings.llmEditor.statusError') },
      }));
    }
  };

  const toggleKeyVisibility = (index: number, nextVisible: boolean) => {
    setVisibleKeys((previous) => ({ ...previous, [index]: nextVisible }));
  };

  const toggleExpand = (index: number) => {
    setExpandedRows((previous) => ({ ...previous, [index]: !previous[index] }));
  };

  const setPrimaryModel = (value: string) => {
    setRuntimeConfig((previous) => ({
      ...previous,
      primaryModel: value,
      fallbackModels: previous.fallbackModels.filter((model) => model !== value),
    }));
  };

  const toggleFallbackModel = (model: string) => {
    setRuntimeConfig((previous) => {
      const alreadySelected = previous.fallbackModels.includes(model);
      return {
        ...previous,
        fallbackModels: alreadySelected
          ? previous.fallbackModels.filter((item) => item !== model)
          : [...previous.fallbackModels, model],
      };
    });
  };

  return (
    <div className="space-y-4">
      <button
        type="button"
        className="flex w-full items-center justify-between rounded-[1.35rem] border settings-border settings-surface px-5 py-4 text-left shadow-soft-card transition-all duration-200 hover:settings-surface-hover"
        onClick={() => setIsCollapsed((previous) => !previous)}
      >
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-foreground">
              {providerScopedMode && scopedPreset
                ? t('settings.llmEditor.scopedTitle', { provider: presetLabels[normalizedScopeName] || normalizedScopeName })
                : t('settings.llmEditor.title')}
            </h3>
            <Badge variant="info" className="settings-accent-badge">{t('settings.llmEditor.managerBadge')}</Badge>
          </div>
          <p className="text-xs text-muted-text">
            {providerScopedMode && scopedPreset
              ? t('settings.llmEditor.scopedHint', { provider: presetLabels[normalizedScopeName] || normalizedScopeName })
              : t('settings.llmEditor.summary')}
          </p>
        </div>
        <span className="text-xs text-muted-text">{isCollapsed ? t('settings.llmEditor.collapseClosed') : t('settings.llmEditor.collapseOpen')}</span>
      </button>

      {!isCollapsed ? (
        <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="settings-surface rounded-[1.35rem] border settings-border p-4 shadow-soft-card">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h4 className="text-sm font-medium text-foreground">
                  {providerScopedMode ? t('settings.llmEditor.addScopedSectionTitle') : t('settings.llmEditor.addSectionTitle')}
                </h4>
                <p className="mt-1 text-xs text-secondary-text">
                  {providerScopedMode && scopedPreset
                    ? t('settings.llmEditor.addScopedSectionDesc')
                    : t('settings.llmEditor.addSectionDesc')}
                </p>
              </div>
              <Badge variant="default" className="settings-border settings-surface-hover text-muted-text">
                {t('settings.llmEditor.channelCount', { count: visibleChannelEntries.length })}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="gradient"
                className="whitespace-nowrap"
                disabled={busy}
                onClick={() => addChannel(providerScopedMode ? normalizedScopeName : undefined)}
              >
                {t('settings.llmEditor.addChannel')}
              </Button>
              {providerScopedMode && scopedPreset ? (
                <div className="flex-1 rounded-xl border border-border/50 bg-base/40 px-3 py-2 text-sm font-medium text-secondary-text">
                  {presetLabels[normalizedScopeName] || normalizedScopeName}
                </div>
              ) : (
                <Select
                  value={addPreset}
                  onChange={setAddPreset}
                  aria-label={t('settings.llmEditor.selectPreset')}
                  options={Object.entries(CHANNEL_PRESETS).map(([value, preset]) => ({
                    value,
                    label: presetLabels[value] || preset.label,
                  }))}
                  disabled={busy}
                  placeholder={t('settings.llmEditor.selectPreset')}
                  className="flex-1"
                />
              )}
            </div>
            {!providerScopedMode ? (
              <SupportPanel
                className="mt-3 rounded-xl border settings-border-soft settings-surface-overlay-soft px-3 py-2"
                body={t('settings.llmEditor.directHint')}
                bodyClassName="text-muted-text"
              />
            ) : null}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-text">{t('settings.llmEditor.listTitle')}</span>
              {visibleChannelEntries.length > 0 ? (
                <span className="text-[10px] text-muted-text">
                  {t('settings.llmEditor.listEnabledSummary', {
                    enabled: visibleChannelEntries.filter((entry) => entry.channel.enabled).length,
                    count: visibleChannelEntries.length,
                  })}
                </span>
              ) : null}
            </div>

            {visibleChannelEntries.length === 0 ? (
              <div className="settings-surface-overlay-muted rounded-[1.35rem] border border-dashed border-border/28 px-4 py-10 text-center">
                <p className="text-sm font-medium text-foreground">
                  {providerScopedMode && scopedPreset
                    ? t('settings.llmEditor.emptyScopedTitle', { provider: presetLabels[normalizedScopeName] || normalizedScopeName })
                    : t('settings.llmEditor.emptyTitle')}
                </p>
                <p className="mt-1 text-xs leading-5 text-muted-text">
                  {providerScopedMode
                    ? t('settings.llmEditor.emptyScopedBody')
                    : t('settings.llmEditor.emptyBody')}
                </p>
              </div>
            ) : visibleChannelEntries.map(({ channel, index }) => (
              <div
                key={index}
                ref={(node) => {
                  channelRowRefs.current[index] = node;
                }}
              >
                <ChannelRow
                  channel={channel}
                  index={index}
                  busy={busy}
                  visibleKey={Boolean(visibleKeys[index])}
                  expanded={Boolean(expandedRows[index])}
                  testState={testStates[index]}
                  t={t}
                  presetLabels={presetLabels}
                  onUpdate={updateChannel}
                  onRemove={removeChannel}
                  onToggleExpand={toggleExpand}
                  onToggleKeyVisibility={toggleKeyVisibility}
                  onTest={(ch, idx) => void handleTest(ch, idx)}
                />
              </div>
            ))}
          </div>

          {!providerScopedMode && managesRuntimeConfig ? (
            <details>
              <summary className={DRAWER_ADVANCED_SUMMARY_CLASS}>
                配置高级参数 (Advanced Settings) ▾
              </summary>
              <div className="mt-3 rounded-xl border border-white/5 bg-white/[0.015] p-4">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <span className="settings-accent-text text-xs font-medium uppercase tracking-wider">{t('settings.llmEditor.runtimeTitle')}</span>
                  <p className="mt-1 text-[11px] text-muted-text">{t('settings.llmEditor.runtimeDesc')}</p>
                </div>
                <Badge variant="default" className="settings-border settings-surface-hover text-muted-text">{t('settings.llmEditor.runtimeBadge')}</Badge>
              </div>
              <div className="mb-4">
                <label className={DRAWER_LABEL_CLASS}>{t('settings.llmEditor.temperatureLabel')}</label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    aria-label={t('settings.llmEditor.temperatureLabel')}
                    className="settings-input-checkbox h-1.5 flex-1 cursor-pointer rounded-full bg-border/60"
                    min="0"
                    max="2"
                    step="0.1"
                    value={runtimeConfig.temperature}
                    disabled={busy}
                    onChange={(event) => setRuntimeConfig((previous) => ({ ...previous, temperature: event.target.value }))}
                  />
                  <span className="w-8 text-right text-sm text-secondary-text">{runtimeConfig.temperature}</span>
                </div>
                <p className="mt-1 text-[11px] text-secondary-text">
                  {t('settings.llmEditor.temperatureHint')}
                </p>
              </div>

              {availableModels.length === 0 ? (
                <SupportPanel
                  className="rounded-xl border border-dashed settings-border-soft settings-surface-overlay-soft p-3"
                  title={t('settings.llmEditor.runtimeEmptyTitle')}
                  body={t('settings.llmEditor.runtimeEmptyBody')}
                />
              ) : (
                <div className="space-y-4">
                  <div>
                    <label className={DRAWER_LABEL_CLASS}>{t('settings.llmEditor.primaryModelLabel')}</label>
                    <Select
                      value={runtimeConfig.primaryModel}
                      onChange={setPrimaryModel}
                      options={buildModelOptions(availableModels, runtimeConfig.primaryModel, t('settings.llmEditor.primaryModelAuto'))}
                      disabled={busy}
                      placeholder=""
                    />
                  </div>

                  <div>
                    <label className={DRAWER_LABEL_CLASS}>{t('settings.llmEditor.agentModelLabel')}</label>
                    <Select
                      value={runtimeConfig.agentPrimaryModel}
                      onChange={(value) => setRuntimeConfig((previous) => ({
                        ...previous,
                        agentPrimaryModel: normalizeAgentPrimaryModel(value),
                      }))}
                      options={buildModelOptions(availableModels, runtimeConfig.agentPrimaryModel, t('settings.llmEditor.agentModelAuto'))}
                      disabled={busy}
                      placeholder=""
                    />
                  </div>

                  <div>
                    <label className={DRAWER_LABEL_CLASS}>{t('settings.llmEditor.fallbackLabel')}</label>
                    <div className="space-y-2 rounded-xl border border-border/30 bg-background/10 p-3">
                      {availableModels.map((model) => (
                        <label key={model} className="flex items-center gap-2 text-sm text-secondary-text">
                          <input
                            type="checkbox"
                            aria-label={model}
                            className="settings-input-checkbox size-4 rounded border-border/70 bg-base"
                            checked={runtimeConfig.fallbackModels.includes(model)}
                            disabled={busy || model === runtimeConfig.primaryModel}
                            onChange={() => toggleFallbackModel(model)}
                          />
                          <span>{model}</span>
                        </label>
                      ))}
                    </div>
                    <p className="mt-1 text-[11px] text-secondary-text">
                      {t('settings.llmEditor.fallbackHint')}
                    </p>
                  </div>

                  <div>
                    <label className={DRAWER_LABEL_CLASS}>{t('settings.llmEditor.visionModelLabel')}</label>
                    <Select
                      value={runtimeConfig.visionModel}
                      onChange={(value) => setRuntimeConfig((previous) => ({ ...previous, visionModel: value }))}
                      options={buildModelOptions(availableModels, runtimeConfig.visionModel, t('settings.llmEditor.visionModelAuto'))}
                      disabled={busy}
                      placeholder=""
                    />
                  </div>
                </div>
              )}
              </div>
            </details>
          ) : providerScopedMode ? null : (
            <SupportBanner
              tone="warning"
              title="当前由 `LITELLM_CONFIG` 接管运行时选择"
              body="主模型、Fallback、Vision 与 Temperature 继续在下方通用字段中管理；这里仅保存渠道条目，不会覆盖 YAML 运行时选择。"
              className="rounded-[1.35rem] px-4"
            />
          )}

          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              variant="settings-primary"
              glow
              disabled={busy || !hasChanges}
              onClick={() => void handleSave()}
            >
              {isSaving
                ? t('settings.llmEditor.saving')
                : providerScopedMode || !managesRuntimeConfig
                  ? t('settings.llmEditor.saveChannels')
                  : t('settings.llmEditor.saveRuntime')}
            </Button>
            {!hasChanges ? <span className="text-xs text-muted-text">{t('settings.llmEditor.noChanges')}</span> : null}
          </div>

          {saveMessage?.type === 'success' ? (
            <SupportBanner tone="success" title={saveMessage.text} role="status" className="py-2" />
          ) : null}

          {saveMessage?.type === 'local-error' ? (
            <SupportBanner tone="danger" title={saveMessage.text} role="alert" className="py-2" />
          ) : null}

          {saveMessage?.type === 'error' ? <ApiErrorAlert error={saveMessage.error} /> : null}
        </div>
      ) : null}
    </div>
  );
};
