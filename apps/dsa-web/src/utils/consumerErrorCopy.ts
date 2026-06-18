import type { ParsedApiError } from '../api/error';

type UiLanguage = 'zh' | 'en';

type ConsumerSafeApiErrorCopyOptions = {
  language: UiLanguage;
  fallbackTitle: string;
  fallbackMessage: string;
};

export type ConsumerSafeApiErrorCopy = {
  title: string;
  message: string;
  rawMessage: string;
  hasHiddenDetails: boolean;
};

const FORBIDDEN_TEXT_RE = /\b(stack|traceback|provider|source|runtime|debug|token|session|cookie|requestid|traceid|schemaversion|policyversion|reasoncodes|raw|internal|local_db|fallback_source|fixture|adapter|cache|bearer)\b/i;
const ERROR_PREFIX_RE = /^\s*error\s*:/i;

function normalizeText(value: string): string {
  return value.trim().replace(/\s+/g, ' ');
}

function isUnsafeConsumerText(value: string): boolean {
  const normalized = normalizeText(value);
  if (!normalized) {
    return false;
  }
  return ERROR_PREFIX_RE.test(normalized) || FORBIDDEN_TEXT_RE.test(normalized);
}

export function getConsumerSafeApiErrorCopy(
  error: ParsedApiError,
  options: ConsumerSafeApiErrorCopyOptions,
): ConsumerSafeApiErrorCopy {
  const normalizedTitle = normalizeText(error.title);
  const normalizedMessage = normalizeText(error.message);
  const normalizedRawMessage = normalizeText(error.rawMessage);

  const unsafeTitle = isUnsafeConsumerText(normalizedTitle);
  const unsafeMessage = isUnsafeConsumerText(normalizedMessage);
  const unsafeRawMessage = isUnsafeConsumerText(normalizedRawMessage);

  const title = unsafeTitle || !normalizedTitle ? options.fallbackTitle : normalizedTitle;
  const message = unsafeMessage || !normalizedMessage ? options.fallbackMessage : normalizedMessage;
  const rawMessage = unsafeRawMessage || normalizedRawMessage === message ? '' : normalizedRawMessage;

  return {
    title,
    message,
    rawMessage,
    hasHiddenDetails: unsafeTitle || unsafeMessage || unsafeRawMessage || rawMessage.length > 0,
  };
}
