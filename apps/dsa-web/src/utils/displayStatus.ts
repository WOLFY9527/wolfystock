export type DisplayStatusTone = 'success' | 'warning' | 'danger' | 'info' | 'muted' | 'neutral';

export type DisplayStatusDescriptor = {
  label: string;
  tone: DisplayStatusTone;
  description?: string;
};

type DisplayStatusLanguage = 'zh' | 'en';

type DisplayStatusOptions = {
  language?: DisplayStatusLanguage;
};

export type SettingsEnabledState = 'enabled' | 'disabled' | 'unknown';
export type SettingsSystemHealthStatus = 'available' | 'attention' | 'not_configured' | 'unavailable' | 'disabled' | 'unknown';

const UNKNOWN_LABELS: Record<DisplayStatusLanguage, string> = {
  zh: '未确认',
  en: 'Unknown',
};

function languageFromOptions(options?: DisplayStatusOptions): DisplayStatusLanguage {
  return options?.language === 'en' ? 'en' : 'zh';
}

function labels(zh: string, en: string, language: DisplayStatusLanguage): string {
  return language === 'en' ? en : zh;
}

export function normalizeDisplayStatus(value: unknown): string {
  return String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/[-\s]+/g, '_');
}

export function describeDisplayStatus(
  value: unknown,
  fallbackLabel?: string,
  options?: DisplayStatusOptions,
): DisplayStatusDescriptor {
  const language = languageFromOptions(options);
  const normalized = normalizeDisplayStatus(value);

  if (normalized === 'success') {
    return { label: labels('成功', 'Success', language), tone: 'success' };
  }
  if (normalized === 'failed' || normalized === 'failure' || normalized === 'error') {
    return { label: labels('失败', 'Failed', language), tone: 'danger' };
  }
  if (normalized === 'partial') {
    return { label: labels('部分成功', 'Partial', language), tone: 'warning' };
  }
  if (normalized === 'pending') {
    return { label: labels('等待中', 'Pending', language), tone: 'warning' };
  }
  if (normalized === 'disabled') {
    return { label: labels('已停用', 'Disabled', language), tone: 'muted' };
  }
  if (normalized === 'info') {
    return { label: labels('信息', 'Info', language), tone: 'info' };
  }
  if (normalized === 'warning') {
    return { label: labels('警告', 'Warning', language), tone: 'warning' };
  }

  return {
    label: fallbackLabel || UNKNOWN_LABELS[language],
    tone: 'info',
  };
}

export function describeBooleanEnabled(
  enabled: boolean | null | undefined,
  options?: DisplayStatusOptions,
): DisplayStatusDescriptor {
  const language = languageFromOptions(options);
  if (enabled === true) {
    return { label: labels('已启用', 'Active', language), tone: 'success' };
  }
  if (enabled === false) {
    return { label: labels('已停用', 'Disabled', language), tone: 'muted' };
  }
  return { label: UNKNOWN_LABELS[language], tone: 'info' };
}

export function describeAdminNotificationStatus(
  value: unknown,
  options?: DisplayStatusOptions,
): DisplayStatusDescriptor {
  const language = languageFromOptions(options);
  const normalized = normalizeDisplayStatus(value);

  if (normalized === 'delivered') {
    return { label: labels('成功', 'Success', language), tone: 'success' };
  }
  if (normalized === 'no_channels') {
    return { label: labels('未配置', 'Unconfigured', language), tone: 'muted' };
  }
  if (normalized === 'provider_down') {
    return { label: labels('服务异常', 'Provider down', language), tone: 'danger' };
  }
  if (normalized === 'provider_error') {
    return { label: labels('通道异常', 'Channel error', language), tone: 'danger' };
  }

  return describeDisplayStatus(value, undefined, { language });
}

export function describeAdminLogLevel(
  value: unknown,
  options?: DisplayStatusOptions,
): DisplayStatusDescriptor {
  const language = languageFromOptions(options);
  const normalized = normalizeDisplayStatus(value);

  if (normalized === 'debug') {
    return { label: labels('调试', 'Debug', language), tone: 'muted' };
  }
  if (normalized === 'info' || normalized === 'notice') {
    return { label: labels(normalized === 'notice' ? '通知' : '信息', normalized === 'notice' ? 'Notice' : 'Info', language), tone: 'info' };
  }
  if (normalized === 'warning' || normalized === 'warn') {
    return { label: labels('警告', 'Warning', language), tone: 'warning' };
  }
  if (normalized === 'error' || normalized === 'failed' || normalized === 'failure') {
    return { label: labels('错误', 'Error', language), tone: 'danger' };
  }
  if (normalized === 'critical' || normalized === 'critical_error' || normalized === 'fatal') {
    return { label: labels('严重', 'Critical', language), tone: 'danger' };
  }

  return { label: UNKNOWN_LABELS[language], tone: 'info' };
}

export function describeSettingsEnabledState(
  state: SettingsEnabledState,
  options?: DisplayStatusOptions,
): DisplayStatusDescriptor {
  const language = languageFromOptions(options);

  if (state === 'enabled') {
    return { label: labels('已启用', 'Enabled', language), tone: 'success' };
  }
  if (state === 'disabled') {
    return { label: labels('未启用', 'Not enabled', language), tone: 'muted' };
  }
  return { label: labels('状态未知', 'Unknown', language), tone: 'info' };
}

export function describeSettingsSystemHealthStatus(
  status: SettingsSystemHealthStatus,
  options?: DisplayStatusOptions,
): DisplayStatusDescriptor {
  const language = languageFromOptions(options);

  if (status === 'available') {
    return { label: labels('正常', 'Available', language), tone: 'success' };
  }
  if (status === 'attention') {
    return { label: labels('需关注', 'Needs attention', language), tone: 'warning' };
  }
  if (status === 'not_configured') {
    return { label: labels('未配置', 'Not configured', language), tone: 'muted' };
  }
  if (status === 'unavailable') {
    return { label: labels('暂不可用', 'Unavailable', language), tone: 'danger' };
  }
  if (status === 'disabled') {
    return { label: labels('未启用', 'Not enabled', language), tone: 'info' };
  }
  return { label: labels('状态未知', 'Unknown', language), tone: 'muted' };
}

export function describeSettingsDuckDBDiagnosticStatus(
  value: unknown,
  options?: DisplayStatusOptions,
): DisplayStatusDescriptor {
  const language = languageFromOptions(options);
  const normalized = normalizeDisplayStatus(value);

  if (normalized === 'ok') {
    return { label: labels('正常', 'OK', language), tone: 'success' };
  }
  if (normalized === 'disabled') {
    return { label: labels('未启用', 'Not enabled', language), tone: 'info' };
  }
  if (normalized === 'empty') {
    return { label: labels('暂无数据', 'No data', language), tone: 'muted' };
  }
  if (normalized === 'dry_run') {
    return { label: labels('预检', 'Dry run', language), tone: 'info' };
  }
  if (normalized === 'invalid_request') {
    return { label: labels('请求需调整', 'Request needs adjustment', language), tone: 'warning' };
  }
  if (normalized === 'unavailable') {
    return { label: labels('暂不可用', 'Unavailable', language), tone: 'danger' };
  }
  if (!normalized) {
    return { label: UNKNOWN_LABELS[language], tone: 'info' };
  }
  return { label: labels('诊断态', 'Diagnostic state', language), tone: 'info' };
}

export function describeSettingsDuckDBDataMode(
  value: unknown,
  options?: DisplayStatusOptions,
): DisplayStatusDescriptor {
  const language = languageFromOptions(options);
  const normalized = normalizeDisplayStatus(value);

  if (normalized === 'real') {
    return { label: labels('真实样本', 'Real sample', language), tone: 'success' };
  }
  if (normalized === 'disabled') {
    return { label: labels('未启用', 'Not enabled', language), tone: 'info' };
  }
  if (normalized === 'unavailable') {
    return { label: labels('暂不可用', 'Unavailable', language), tone: 'danger' };
  }
  if (normalized === 'empty') {
    return { label: labels('空样本', 'Empty sample', language), tone: 'muted' };
  }
  if (!normalized) {
    return { label: '--', tone: 'muted' };
  }
  return { label: labels('诊断样本', 'Diagnostic sample', language), tone: 'info' };
}
