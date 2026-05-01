import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Button, GlassCard, Input } from '../common';
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

export const NotificationChannelsConfig: React.FC<NotificationChannelsConfigProps> = ({
  items,
  disabled,
  isSaving,
  onSaveItems,
}) => {
  const itemByKey = useMemo(() => new Map(items.map((item) => [item.key, item])), [items]);
  const initialDraft = useMemo(() => {
    const next: Record<string, string> = {};
    CHANNELS.forEach((channel) => {
      channel.fields.forEach((field) => {
        next[field.key] = String(itemByKey.get(field.key)?.value ?? '');
      });
    });
    return next;
  }, [itemByKey]);
  const [draft, setDraft] = useState<Record<string, string>>(initialDraft);
  const [savingChannelId, setSavingChannelId] = useState<string | null>(null);

  useEffect(() => {
    setDraft(initialDraft);
  }, [initialDraft]);

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
      await onSaveItems(changedItems, `${channel.label} notification channel saved`);
    } finally {
      setSavingChannelId(null);
    }
  };

  return (
    <SettingsSectionCard
      title="Notification Channels"
      description="Notification credentials are managed here and kept out of raw system settings."
      className="border-white/6 bg-white/[0.025]"
    >
      <div className="rounded-2xl border border-white/5 bg-black/20 px-4 py-3">
        <p className="text-sm font-semibold text-foreground">Curated credential surface</p>
        <p className="mt-1 text-xs leading-5 text-secondary-text">
          Notification credentials are managed here and kept out of raw system settings.
        </p>
        <p className="mt-1 text-xs leading-5 text-secondary-text">
          Secrets stay masked in the UI. Leaving a masked value unchanged preserves the existing backend secret.
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
          const statusText = configuredCount > 0 ? 'Configured' : 'Not configured';
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
                    <p className="mt-1 text-xs leading-5 text-secondary-text">{channel.description}</p>
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
                          <label htmlFor={fieldId} className="theme-field-label mb-2 block">{field.label}</label>
                          <textarea
                            id={fieldId}
                            className="input-surface input-focus-glow min-h-[84px] w-full resize-y rounded-xl border px-4 py-3 text-sm text-foreground transition-all placeholder:text-muted-text focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
                            value={fieldValue}
                            disabled={disabled || isSaving}
                            onChange={(event) => setFieldValue(field.key, event.target.value)}
                          />
                          {field.hint ? <span className="mt-2 block text-xs leading-5 text-secondary-text">{field.hint}</span> : null}
                        </div>
                      );
                    }
                    if (field.kind === 'switch') {
                      const checked = fieldValue.trim().toLowerCase() !== 'false';
                      return (
                        <label key={field.key} className="inline-flex items-center justify-between gap-3 rounded-xl border border-white/5 bg-black/20 px-3 py-2">
                          <span className="text-xs font-medium text-secondary-text">{field.label}</span>
                          <input
                            id={fieldId}
                            type="checkbox"
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
                        label={field.label}
                        type={field.kind === 'secret' ? 'password' : 'text'}
                        iconType={field.kind === 'secret' ? 'key' : 'none'}
                        allowTogglePassword={field.kind === 'secret'}
                        value={fieldValue}
                        disabled={disabled || isSaving}
                        hint={field.hint}
                        placeholder={field.kind === 'secret' ? 'Masked when configured' : undefined}
                        onChange={(event) => setFieldValue(field.key, event.target.value)}
                      />
                    );
                  })}
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/5 pt-3">
                <span className="text-xs text-muted-text">Test send not available yet</span>
                <Button
                  type="button"
                  size="sm"
                  variant="settings-primary"
                  className="rounded-lg px-3 py-1.5 text-xs"
                  disabled={!canSave}
                  isLoading={savingChannelId === channel.id}
                  loadingText="Saving"
                  onClick={() => void saveChannel(channel)}
                >
                  Save
                </Button>
              </div>
            </GlassCard>
          );
        })}
      </div>
    </SettingsSectionCard>
  );
};
