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
