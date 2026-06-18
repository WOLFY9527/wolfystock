import { describe, expect, it } from 'vitest';
import type { ParsedApiError } from '../../api/error';
import { getConsumerSafeApiErrorCopy } from '../consumerErrorCopy';

function buildError(overrides: Partial<ParsedApiError> = {}): ParsedApiError {
  return {
    title: '请求失败',
    message: '请稍后重试。',
    rawMessage: 'request failed',
    category: 'unknown',
    ...overrides,
  };
}

describe('getConsumerSafeApiErrorCopy', () => {
  it('replaces unsafe title and message fields with localized fallback copy', () => {
    const safe = getConsumerSafeApiErrorCopy(
      buildError({
        title: 'provider runtime failure',
        message: 'requestId=req-123 traceId=trace-999 token=bearer-abc cache adapter internal raw debug',
        rawMessage: 'provider stack trace requestId=req-123 traceId=trace-999 token=bearer-abc',
      }),
      {
        language: 'en',
        fallbackTitle: 'This request is temporarily unavailable.',
        fallbackMessage: 'Please try again shortly.',
      },
    );

    expect(safe.title).toBe('This request is temporarily unavailable.');
    expect(safe.message).toBe('Please try again shortly.');
    expect(safe.rawMessage).toBe('');
    expect(safe.hasHiddenDetails).toBe(true);
  });

  it('keeps consumer-safe copy when no forbidden diagnostic markers are present', () => {
    const safe = getConsumerSafeApiErrorCopy(
      buildError({
        title: '请求超时',
        message: '请稍后重试。',
        rawMessage: '请稍后重试。',
        category: 'upstream_timeout',
      }),
      {
        language: 'zh',
        fallbackTitle: '请求暂不可用',
        fallbackMessage: '请稍后重试。',
      },
    );

    expect(safe.title).toBe('请求超时');
    expect(safe.message).toBe('请稍后重试。');
    expect(safe.rawMessage).toBe('');
    expect(safe.hasHiddenDetails).toBe(false);
  });

  it('drops raw details when only the raw payload is unsafe', () => {
    const safe = getConsumerSafeApiErrorCopy(
      buildError({
        title: 'Authentication required',
        message: 'Sign in to continue.',
        rawMessage: 'session expired traceId=trace-123',
        category: 'auth_required',
      }),
      {
        language: 'en',
        fallbackTitle: 'Authentication required',
        fallbackMessage: 'Sign in to continue.',
      },
    );

    expect(safe.title).toBe('Authentication required');
    expect(safe.message).toBe('Sign in to continue.');
    expect(safe.rawMessage).toBe('');
    expect(safe.hasHiddenDetails).toBe(true);
  });
});
