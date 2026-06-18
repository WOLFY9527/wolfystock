import { describe, expect, it } from 'vitest';
import {
  getApiErrorMessage,
  isAuthError,
  isNetworkError,
  isTimeoutError,
  parseApiError,
} from '../error';

describe('parseApiError', () => {
  it('parses { error, message } payloads', () => {
    const parsed = parseApiError({
      response: {
        status: 400,
        data: {
          error: 'bad_request',
          message: '请求参数格式不正确。',
        },
      },
    });

    expect(parsed.message).toBe('请求参数格式不正确。');
    expect(parsed.rawMessage).toBe('请求参数格式不正确。');
  });

  it('parses { detail: "..." } payloads', () => {
    const parsed = parseApiError({
      response: {
        status: 400,
        data: {
          detail: '后端返回了 detail 字段文本。',
        },
      },
    });

    expect(parsed.message).toBe('后端返回了 detail 字段文本。');
    expect(parsed.rawMessage).toBe('后端返回了 detail 字段文本。');
  });

  it('parses FastAPI validation detail lists', () => {
    const parsed = parseApiError({
      response: {
        status: 422,
        data: {
          detail: [
            {
              loc: ['body', 'api_key'],
              msg: 'field required',
              type: 'missing',
            },
            {
              loc: ['body', 'base_url'],
              msg: 'must be a valid URL',
              type: 'value_error.url',
            },
          ],
        },
      },
    });

    expect(parsed.status).toBe(422);
    expect(parsed.category).toBe('validation_error');
    expect(parsed.isValidationError).toBe(true);
    expect(parsed.message).toContain('请求参数无效');
    expect(parsed.details).toEqual({
      detail: [
        { loc: ['body', 'api_key'], msg: 'field required', type: 'missing' },
        { loc: ['body', 'base_url'], msg: 'must be a valid URL', type: 'value_error.url' },
      ],
    });
  });

  it('maps 401 responses to auth guidance', () => {
    const parsed = parseApiError({
      response: {
        status: 401,
        data: {
          detail: {
            error: 'unauthorized',
            message: 'Login required',
          },
        },
      },
    });

    expect(parsed.category).toBe('auth_required');
    expect(parsed.message).toBe('登录已失效，请重新登录。');
    expect(parsed.isAuthError).toBe(true);
    expect(isAuthError(parsed)).toBe(true);
  });

  it('maps 403 responses to permission guidance', () => {
    const parsed = parseApiError({
      response: {
        status: 403,
        data: {
          detail: {
            error: 'forbidden',
            message: 'Forbidden',
          },
        },
      },
    });

    expect(parsed.category).toBe('access_denied');
    expect(parsed.message).toBe('没有权限执行该操作。');
    expect(isAuthError(parsed)).toBe(false);
  });

  it('maps 404 responses to not-found guidance', () => {
    const parsed = parseApiError({
      response: {
        status: 404,
        data: {
          message: 'Not Found',
        },
      },
    });

    expect(parsed.category).toBe('http_error');
    expect(parsed.message).toBe('请求的资源不存在。');
  });

  it('maps 422 responses to validation guidance', () => {
    const parsed = parseApiError({
      response: {
        status: 422,
        data: {
          message: 'unprocessable entity',
        },
      },
    });

    expect(parsed.category).toBe('validation_error');
    expect(parsed.message).toContain('请求参数无效');
    expect(parsed.isValidationError).toBe(true);
  });

  it('maps 500 responses to server-unavailable guidance', () => {
    const parsed = parseApiError({
      response: {
        status: 500,
        data: {
          message: 'Internal Server Error',
        },
      },
    });

    expect(parsed.category).toBe('upstream_unavailable');
    expect(parsed.message).toBe('服务器暂时不可用，请稍后重试。');
  });

  it('maps network failures to the network guidance', () => {
    const parsed = parseApiError({
      code: 'ERR_NETWORK',
      message: 'Network Error',
    });

    expect(parsed.category).toBe('local_connection_failed');
    expect(parsed.message).toBe('网络连接失败，请检查后端服务是否运行。');
    expect(parsed.isNetworkError).toBe(true);
    expect(isNetworkError(parsed)).toBe(true);
  });

  it('maps timeout failures to timeout guidance', () => {
    const parsed = parseApiError({
      code: 'ECONNABORTED',
      message: 'timeout of 30000ms exceeded',
    });

    expect(parsed.category).toBe('upstream_timeout');
    expect(parsed.message).toBe('请求超时，请稍后重试。');
    expect(parsed.isTimeoutError).toBe(true);
    expect(isTimeoutError(parsed)).toBe(true);
  });

  it('redacts api keys, tokens, and secrets from message text and details', () => {
    const parsed = parseApiError({
      response: {
        status: 400,
        data: {
          message: 'request failed for https://example.com/callback?api_key=abc123&token=secret-token&foo=bar',
          details: {
            callbackUrl: 'https://example.com/next?secret=top-secret&safe=1',
            nested: {
              authorization: 'Bearer super-secret',
              note: 'token=another-secret',
            },
          },
        },
      },
    });

    expect(parsed.rawMessage).toContain('api_key=***');
    expect(parsed.rawMessage).toContain('token=***');
    expect(parsed.rawMessage).not.toContain('abc123');
    expect(parsed.rawMessage).not.toContain('secret-token');
    expect(parsed.details).toEqual({
      message: 'request failed for https://example.com/callback?api_key=***&token=***&foo=bar',
      details: {
        callbackUrl: 'https://example.com/next?secret=***&safe=1',
        nested: {
          authorization: '***',
          note: 'token=***',
        },
      },
    });
  });

  it('preserves parsed error shape while masking token-like values in raw text', () => {
    const parsed = parseApiError({
      response: {
        status: 502,
        data: {
          title: 'provider runtime failure',
          message: 'requestId=req-123 token=secret-value',
          raw: 'traceId=trace-999 bearer secret-value',
        },
      },
    });

    expect(parsed.title).toBe('服务器暂时不可用');
    expect(parsed.message).toBe('服务器暂时不可用，请稍后重试。');
    expect(parsed.rawMessage).not.toContain('secret-value');
    expect(parsed.rawMessage).toContain('token=***');
  });

  it('uses fallbackMessage when no useful error payload exists', () => {
    expect(getApiErrorMessage(undefined, '自定义兜底')).toBe('自定义兜底');
    expect(parseApiError(undefined, '自定义兜底').message).toBe('自定义兜底');
  });

  it('keeps existing IBKR-specific guidance intact', () => {
    const parsed = parseApiError({
      response: {
        status: 409,
        data: {
          detail: {
            error: 'ibkr_account_mapping_conflict',
            message: '该 broker account ref 已绑定到当前用户的另一持仓账户。',
          },
        },
      },
    });

    expect(parsed.category).toBe('validation_error');
    expect(parsed.title).toBe('IBKR 账户映射冲突');
  });
});
