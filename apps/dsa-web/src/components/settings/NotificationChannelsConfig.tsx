import type React from 'react';
import { useEffect, useState } from 'react';
import { Button } from '../common/Button';
import { GlassCard } from '../common/GlassCard';
import { Input } from '../common/Input';
import type { SystemConfigItem, SystemConfigUpdateItem } from '../../types/systemConfig';
import { SettingsSectionCard } from './SettingsSectionCard';

type NotificationChannelField = {
  key: string;
  label: string;
  kind: 'text' | 'secret' | 'textarea' | 'switch';
  hint?: string;
};

type NotificationChannelDefinition = {
  id: string;
  label: string;
  description: string;
  fields: NotificationChannelField[];
};

type NotificationChannelsConfigProps = {
  items: SystemConfigItem[];
  disabled: boolean;
  isSaving: boolean;
  language?: 'zh' | 'en';
  onSaveItems: (items: SystemConfigUpdateItem[], successMessage: string) => Promise<void> | void;
};

const CHANNELS: NotificationChannelDefinition[] = [
  {
    id: 'feishu',
    label: 'Feishu',
    description: 'Lark/Feishu webhook or app bot credentials.',
    fields: [
      { key: 'FEISHU_WEBHOOK_URL', label: 'Webhook URL', kind: 'secret' },
      { key: 'FEISHU_APP_ID', label: 'App ID', kind: 'text' },
      { key: 'FEISHU_APP_SECRET', label: 'App Secret', kind: 'secret' },
    ],
  },
  {
    id: 'telegram',
    label: 'Telegram',
    description: 'Bot token, target chat, and optional topic thread.',
    fields: [
      { key: 'TELEGRAM_BOT_TOKEN', label: 'Bot Token', kind: 'secret' },
      { key: 'TELEGRAM_CHAT_ID', label: 'Chat ID', kind: 'text' },
      { key: 'TELEGRAM_MESSAGE_THREAD_ID', label: 'Thread ID', kind: 'text', hint: 'Optional for forum topics.' },
    ],
  },
  {
    id: 'dingtalk',
    label: 'DingTalk',
    description: 'DingTalk app credentials for bot delivery.',
    fields: [
      { key: 'DINGTALK_APP_KEY', label: 'App Key', kind: 'secret' },
      { key: 'DINGTALK_APP_SECRET', label: 'App Secret', kind: 'secret' },
    ],
  },
  {
    id: 'email',
    label: 'Email',
    description: 'SMTP sender credentials and recipient routing.',
    fields: [
      { key: 'EMAIL_SENDER', label: 'Sender', kind: 'text' },
      { key: 'EMAIL_PASSWORD', label: 'Password / App Code', kind: 'secret' },
      { key: 'EMAIL_RECEIVERS', label: 'Receivers', kind: 'textarea', hint: 'Comma-separated addresses. Empty keeps sender fallback behavior.' },
    ],
  },
  {
    id: 'discord',
    label: 'Discord',
    description: 'Webhook or bot token delivery into a channel.',
    fields: [
      { key: 'DISCORD_WEBHOOK_URL', label: 'Webhook URL', kind: 'secret' },
      { key: 'DISCORD_BOT_TOKEN', label: 'Bot Token', kind: 'secret' },
      { key: 'DISCORD_MAIN_CHANNEL_ID', label: 'Main Channel ID', kind: 'text' },
    ],
  },
  {
    id: 'slack',
    label: 'Slack',
    description: 'Slack bot token or incoming webhook settings.',
    fields: [
      { key: 'SLACK_BOT_TOKEN', label: 'Bot Token', kind: 'secret' },
      { key: 'SLACK_CHANNEL_ID', label: 'Channel ID', kind: 'text' },
      { key: 'SLACK_WEBHOOK_URL', label: 'Webhook URL', kind: 'secret' },
    ],
  },
  {
    id: 'wechat',
    label: 'WeChat webhook',
    description: 'Enterprise WeChat bot webhook.',
    fields: [
      { key: 'WECHAT_WEBHOOK_URL', label: 'Webhook URL', kind: 'secret' },
    ],
  },
  {
    id: 'pushplus',
    label: 'PushPlus',
    description: 'PushPlus token and optional topic routing.',
    fields: [
      { key: 'PUSHPLUS_TOKEN', label: 'Token', kind: 'secret' },
      { key: 'PUSHPLUS_TOPIC', label: 'Topic', kind: 'text' },
    ],
  },
  {
    id: 'pushover',
    label: 'Pushover',
    description: 'Pushover user key and application token.',
    fields: [
      { key: 'PUSHOVER_USER_KEY', label: 'User Key', kind: 'secret' },
      { key: 'PUSHOVER_API_TOKEN', label: 'API Token', kind: 'secret' },
    ],
  },
  {
    id: 'serverchan',
    label: 'ServerChan',
    description: 'ServerChan 3 SendKey delivery.',
    fields: [
      { key: 'SERVERCHAN3_SENDKEY', label: 'SendKey', kind: 'secret' },
    ],
  },
  {
    id: 'custom_webhook',
    label: 'Custom webhook',
    description: 'Generic webhook endpoints and optional bearer token.',
    fields: [
      { key: 'CUSTOM_WEBHOOK_URLS', label: 'Webhook URLs', kind: 'textarea', hint: 'Comma-separated URLs.' },
      { key: 'CUSTOM_WEBHOOK_BEARER_TOKEN', label: 'Bearer Token', kind: 'secret' },
      { key: 'WEBHOOK_VERIFY_SSL', label: 'Verify SSL', kind: 'switch' },
    ],
  },
];

const isConfiguredValue = (value: string | undefined): boolean => Boolean(String(value || '').trim());

export const NOTIFICATION_CHANNEL_KEYS = new Set(CHANNELS.flatMap((channel) => channel.fields.map((field) => field.key)));

const ZH_CHANNEL_DESCRIPTIONS: Record<string, string> = {
  feishu: '飞书 Webhook 或应用机器人凭据。',
  telegram: '机器人 Token、目标聊天和可选话题线程。',
  dingtalk: '用于机器人投递的钉钉应用凭据。',
  email: 'SMTP 发件凭据和收件人路由。',
  discord: '面向频道投递的 Webhook 或机器人 Token。',
  slack: 'Slack 机器人 Token 或 incoming webhook 设置。',
  wechat: '企业微信机器人 Webhook。',
  pushplus: 'PushPlus Token 与可选主题路由。',
  pushover: 'Pushover 用户 Key 和应用 Token。',
  serverchan: 'ServerChan 3 SendKey 投递。',
  custom_webhook: '通用 Webhook 端点和可选 Bearer Token。',
};

const ZH_FIELD_LABELS: Record<string, string> = {
  Sender: '发件人',
  'Password / App Code': '密码 / 应用码',
  Receivers: '收件人',
  'Bot Token': '机器人 Token',
  'Thread ID': '话题线程 ID',
  'Main Channel ID': '主频道 ID',
  'Channel ID': '频道 ID',
  'Webhook URLs': 'Webhook 地址',
  'Verify SSL': '校验 SSL',
  'User Key': '用户 Key',
};

const ZH_FIELD_HINTS: Record<string, string> = {
  'Optional for forum topics.': '论坛话题可选。',
  'Comma-separated addresses. Empty keeps sender fallback behavior.': '多个地址用逗号分隔；留空则保留发件人回退行为。',
  'Comma-separated URLs.': '多个地址用逗号分隔。',
};

export const NotificationChannelsConfig: React.FC<NotificationChannelsConfigProps> = ({
  items,
  disabled,
  isSaving,
  language = 'en',
  onSaveItems,
}) => {
  const itemByKey = new Map(items.map((item) => [item.key, item]));

  const [draft, setDraft] = useState<Record<string, string>>(() => {
    const next: Record<string, string> = {};
    CHANNELS.forEach((channel) => {
      channel.fields.forEach((field) => {
        next[field.key] = String(itemByKey.get(field.key)?.value ?? '');
      });
    });
    return next;
  });
  const [savingChannelId, setSavingChannelId] = useState<string | null>(null);

  useEffect(() => {
    const currentByKey = new Map(items.map((item) => [item.key, item]));
    const next: Record<string, string> = {};
    CHANNELS.forEach((channel) => {
      channel.fields.forEach((field) => {
        next[field.key] = String(currentByKey.get(field.key)?.value ?? '');
      });
    });
    setDraft(next);
  }, [items]);

  const setFieldValue = (key: string, value: string) => {
    setDraft((previous) => ({
      ...previous,
      [key]: value,
    }));
  };

  const saveChannel = async (channel: NotificationChannelDefinition) => {
    const changedItems = channel.fields
      .map((field) => {
        const current = String(itemByKey.get(field.key)?.value ?? '');
        const next = String(draft[field.key] ?? '');
        return current === next ? null : { key: field.key, value: next };
      })
      .filter((item): item is SystemConfigUpdateItem => Boolean(item));

    if (!changedItems.length) {
      return;
    }

    setSavingChannelId(channel.id);
    try {
      await onSaveItems(
        changedItems,
        language === 'zh' ? `${channel.label} 通知通道已保存` : `${channel.label} notification channel saved`,
      );
    } finally {
      setSavingChannelId(null);
    }
  };

  const copy = language === 'zh'
    ? {
      title: '通知通道',
      description: '通知凭据在这里专用管理，并从原始系统设置中隐藏。',
      surfaceTitle: '专用凭据面',
      body: '通知凭据在这里专用管理，并从原始系统设置中隐藏。',
      secretBody: '密钥在界面中保持脱敏。保留脱敏值不变会继续使用后端已有密钥。',
      configured: '已配置',
      notConfigured: '未配置',
      testUnavailable: '测试发送暂不可用',
      save: '保存',
      saving: '保存中',
      maskedPlaceholder: '已配置时显示脱敏值',
    }
    : {
      title: 'Notification Channels',
      description: 'Notification credentials are managed here and kept out of raw system settings.',
      surfaceTitle: 'Curated credential surface',
      body: 'Notification credentials are managed here and kept out of raw system settings.',
      secretBody: 'Secrets stay masked in the UI. Leaving a masked value unchanged preserves the existing backend secret.',
      configured: 'Configured',
      notConfigured: 'Not configured',
      testUnavailable: 'Test send not available yet',
      save: 'Save',
      saving: 'Saving',
      maskedPlaceholder: 'Masked when configured',
    };

  const channelDescription = (channel: NotificationChannelDefinition) => (
    language === 'zh' ? ZH_CHANNEL_DESCRIPTIONS[channel.id] || channel.description : channel.description
  );
  const fieldLabel = (field: NotificationChannelField) => (
    language === 'zh' ? ZH_FIELD_LABELS[field.label] || field.label : field.label
  );
  const fieldHint = (field: NotificationChannelField) => (
    language === 'zh' && field.hint ? ZH_FIELD_HINTS[field.hint] || field.hint : field.hint
  );

  return (
    <SettingsSectionCard
      title={copy.title}
      description={copy.description}
      className="border-white/6 bg-white/[0.025]"
    >
      <div className="rounded-2xl border border-white/5 bg-black/20 px-4 py-3">
        <p className="text-sm font-semibold text-foreground">{copy.surfaceTitle}</p>
        <p className="mt-1 text-xs leading-5 text-secondary-text">
          {copy.body}
        </p>
        <p className="mt-1 text-xs leading-5 text-secondary-text">
          {copy.secretBody}
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {CHANNELS.map((channel) => {
          const configuredCount = channel.fields.filter((field) => {
            const item = itemByKey.get(field.key);
            return Boolean(item?.rawValueExists) || isConfiguredValue(draft[field.key]);
          }).length;
          const changedCount = channel.fields.filter((field) => {
            const current = String(itemByKey.get(field.key)?.value ?? '');
            return String(draft[field.key] ?? '') !== current;
          }).length;
          const statusText = configuredCount > 0 ? copy.configured : copy.notConfigured;
          const canSave = changedCount > 0 && !disabled && !isSaving;

          return (
            <GlassCard
              key={channel.id}
              className="flex min-h-[280px] flex-col justify-between gap-4 border-white/5 bg-white/[0.018] p-4"
              data-testid={`notification-channel-card-${channel.id}`}
            >
              <div>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-foreground">{channel.label}</p>
                    <p className="mt-1 text-xs leading-5 text-secondary-text">{channelDescription(channel)}</p>
                  </div>
                  <span
                    className={configuredCount > 0
                      ? 'rounded-full border border-emerald-300/20 px-2 py-1 text-[11px] font-semibold text-emerald-200'
                      : 'rounded-full border border-white/10 px-2 py-1 text-[11px] font-semibold text-muted-text'}
                  >
                    {statusText}
                  </span>
                </div>

                <div className="mt-4 grid gap-3">
                  {channel.fields.map((field) => {
                    const fieldId = `notification-${channel.id}-${field.key.toLowerCase()}`;
                    const fieldValue = String(draft[field.key] ?? '');
                    if (field.kind === 'textarea') {
                      return (
                        <div key={field.key} className="block">
                          <label htmlFor={fieldId} className="theme-field-label mb-2 block">{fieldLabel(field)}</label>
                          <textarea
                            id={fieldId}
                            className="input-surface input-focus-glow min-h-[84px] w-full resize-y rounded-xl border px-4 py-3 text-sm text-foreground transition-all placeholder:text-muted-text focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
                            value={fieldValue}
                            disabled={disabled || isSaving}
                            onChange={(event) => setFieldValue(field.key, event.target.value)}
                          />
                          {fieldHint(field) ? <span className="mt-2 block text-xs leading-5 text-secondary-text">{fieldHint(field)}</span> : null}
                        </div>
                      );
                    }
                    if (field.kind === 'switch') {
                      const checked = fieldValue.trim().toLowerCase() !== 'false';
                      return (
                        <label key={field.key} className="inline-flex items-center justify-between gap-3 rounded-xl border border-white/5 bg-black/20 px-3 py-2">
                          <span className="text-xs font-medium text-secondary-text">{fieldLabel(field)}</span>
                          <input
                            id={fieldId}
                            type="checkbox"
                            className="settings-input-checkbox size-4 rounded border-border/70 bg-base"
                            checked={checked}
                            disabled={disabled || isSaving}
                            onChange={(event) => setFieldValue(field.key, event.target.checked ? 'true' : 'false')}
                          />
                        </label>
                      );
                    }
                    return (
                      <Input
                        key={field.key}
                        id={fieldId}
                        label={fieldLabel(field)}
                        type={field.kind === 'secret' ? 'password' : 'text'}
                        iconType={field.kind === 'secret' ? 'key' : 'none'}
                        allowTogglePassword={field.kind === 'secret'}
                        value={fieldValue}
                        disabled={disabled || isSaving}
                        hint={fieldHint(field)}
                        placeholder={field.kind === 'secret' ? copy.maskedPlaceholder : undefined}
                        onChange={(event) => setFieldValue(field.key, event.target.value)}
                      />
                    );
                  })}
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/5 pt-3">
                <span className="text-xs text-muted-text">{copy.testUnavailable}</span>
                <Button
                  type="button"
                  size="sm"
                  variant="settings-primary"
                  className="rounded-lg px-3 py-1.5 text-xs"
                  disabled={!canSave}
                  isLoading={savingChannelId === channel.id}
                  loadingText={copy.saving}
                  onClick={() => void saveChannel(channel)}
                >
                  {copy.save}
                </Button>
              </div>
            </GlassCard>
          );
        })}
      </div>
    </SettingsSectionCard>
  );
};
