export type ApiErrorCategory =
  | 'auth_required'
  | 'access_denied'
  | 'admin_unlock_required'
  | 'agent_disabled'
  | 'missing_params'
  | 'validation_error'
  | 'analysis_conflict'
  | 'llm_not_configured'
  | 'model_tool_incompatible'
  | 'invalid_tool_call'
  | 'portfolio_oversell'
  | 'portfolio_busy'
  | 'upstream_forbidden'
  | 'upstream_unavailable'
  | 'upstream_llm_400'
  | 'upstream_timeout'
  | 'upstream_network'
  | 'local_connection_failed'
  | 'http_error'
  | 'unknown';

export interface ParsedApiError {
  title: string;
  message: string;
  rawMessage: string;
  status?: number;
  code?: string;
  details?: unknown;
  category: ApiErrorCategory;
  isAuthError?: boolean;
  isNetworkError?: boolean;
  isTimeoutError?: boolean;
  isValidationError?: boolean;
}

type ResponseLike = {
  status?: number;
  data?: unknown;
  statusText?: string;
  url?: string;
  body?: unknown;
  detail?: unknown;
  details?: unknown;
  message?: unknown;
  error?: unknown;
};

type ErrorCarrier = {
  response?: ResponseLike;
  status?: number;
  statusText?: string;
  data?: unknown;
  body?: unknown;
  detail?: unknown;
  details?: unknown;
  code?: string;
  message?: string;
  url?: string;
  error?: unknown;
  parsedError?: ParsedApiError;
  cause?: unknown;
};

type CreateParsedApiErrorOptions = {
  title: string;
  message: string;
  rawMessage?: string;
  status?: number;
  code?: string;
  details?: unknown;
  category?: ApiErrorCategory;
  isAuthError?: boolean;
  isNetworkError?: boolean;
  isTimeoutError?: boolean;
  isValidationError?: boolean;
};

const DEFAULT_FALLBACK_MESSAGE = '请求未成功完成，请稍后重试。';
const NETWORK_FALLBACK_MESSAGE = '网络连接失败，请检查后端服务是否运行。';
const AUTH_FALLBACK_MESSAGE = '登录已失效，请重新登录。';
const ACCESS_DENIED_FALLBACK_MESSAGE = '没有权限执行该操作。';
const NOT_FOUND_FALLBACK_MESSAGE = '请求的资源不存在。';
const VALIDATION_FALLBACK_MESSAGE = '请求参数无效。';
const SERVER_UNAVAILABLE_FALLBACK_MESSAGE = '服务器暂时不可用，请稍后重试。';
const TIMEOUT_FALLBACK_MESSAGE = '请求超时，请稍后重试。';

const SENSITIVE_KEY_RE = /(api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|token|authorization|bearer|credential|private[_-]?key|secret|password|passwd|session[_-]?token)/i;
const SENSITIVE_URL_PARAM_RE = /(api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|token|authorization|bearer|credential|private[_-]?key|secret|password|passwd|session[_-]?token)/i;
const URL_PATTERN_RE = /https?:\/\/[^\s"'<>]+/gi;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isPlainResponseLike(value: unknown): value is ResponseLike {
  return isRecord(value) && (
    typeof value.status === 'number'
    || typeof value.statusText === 'string'
    || 'data' in value
    || 'body' in value
    || 'detail' in value
    || 'details' in value
    || 'url' in value
  );
}

function pickString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return sanitizeText(value.trim());
    }
  }
  return null;
}

function sanitizeUrlString(value: string): string {
  try {
    const url = new URL(value);
    for (const key of [...url.searchParams.keys()]) {
      if (SENSITIVE_URL_PARAM_RE.test(key)) {
        url.searchParams.set(key, '***');
      }
    }
    return url.toString();
  } catch {
    return value.replace(/([?&](?:[^=&#\s]+)=)([^&#\s]+)/g, (prefix, rawValue) => {
      const key = prefix.replace(/^[?&]/, '').split('=')[0] || '';
      return SENSITIVE_URL_PARAM_RE.test(key) ? `${prefix}***` : `${prefix}${rawValue}`;
    });
  }
}

function sanitizeText(value: string): string {
  const maskedUrls = value.replace(URL_PATTERN_RE, (url) => sanitizeUrlString(url));
  return maskedUrls.replace(
    /((?:api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|token|authorization|bearer|credential|private[_-]?key|secret|password|passwd|session[_-]?token)\s*[:=]\s*)([^,\s"'&]+)/gi,
    (_match, prefix) => `${prefix}***`,
  );
}

function sanitizeUnknown(value: unknown, seen = new WeakSet<object>()): unknown {
  if (typeof value === 'string') {
    return sanitizeText(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeUnknown(item, seen));
  }
  if (!isRecord(value)) {
    return value;
  }
  if (seen.has(value)) {
    return '[Circular]';
  }
  seen.add(value);

  const next: Record<string, unknown> = {};
  for (const [key, entry] of Object.entries(value)) {
    if (SENSITIVE_KEY_RE.test(key)) {
      next[key] = entry == null ? entry : '***';
      continue;
    }
    next[key] = sanitizeUnknown(entry, seen);
  }
  return next;
}

function stringifyValue(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed ? sanitizeText(trimmed) : null;
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }

  try {
    return JSON.stringify(sanitizeUnknown(value));
  } catch {
    return String(value);
  }
}

function getResponse(error: unknown): ResponseLike | undefined {
  if (!isRecord(error)) {
    return undefined;
  }

  const response = (error as ErrorCarrier).response;
  if (isPlainResponseLike(response)) {
    return response;
  }

  if (isPlainResponseLike(error)) {
    return error;
  }

  return undefined;
}

function getErrorCode(error: unknown): string | undefined {
  return isRecord(error) && typeof (error as ErrorCarrier).code === 'string'
    ? (error as ErrorCarrier).code
    : undefined;
}

function getErrorMessage(error: unknown): string | null {
  if (typeof error === 'string') {
    const trimmed = error.trim();
    return trimmed ? sanitizeText(trimmed) : null;
  }

  if (error instanceof Error && error.message.trim()) {
    return sanitizeText(error.message.trim());
  }

  if (isRecord(error) && typeof (error as ErrorCarrier).message === 'string') {
    const message = (error as ErrorCarrier).message?.trim();
    return message ? sanitizeText(message) : null;
  }

  return null;
}

function getCauseMessage(error: unknown): string | null {
  if (!isRecord(error)) {
    return null;
  }

  return getErrorMessage((error as ErrorCarrier).cause);
}

function getErrorStatus(error: unknown): number | undefined {
  const response = getResponse(error);
  if (typeof response?.status === 'number') {
    return response.status;
  }

  if (isRecord(error) && typeof (error as ErrorCarrier).status === 'number') {
    return (error as ErrorCarrier).status;
  }

  return undefined;
}

function getErrorUrl(error: unknown): string | null {
  if (!isRecord(error)) {
    return null;
  }

  const response = getResponse(error);
  const url = pickString(
    response?.url,
    (error as ErrorCarrier).url,
    isRecord(error) && isRecord((error as { config?: unknown }).config)
      ? (error as { config?: { url?: unknown } }).config?.url
      : null,
  );
  return url ? sanitizeText(url) : null;
}

function buildMatchText(parts: Array<string | undefined | null>): string {
  return parts
    .filter((part): part is string => typeof part === 'string' && part.trim().length > 0)
    .join(' | ')
    .toLowerCase();
}

function includesAny(haystack: string, needles: string[]): boolean {
  return needles.some((needle) => haystack.includes(needle.toLowerCase()));
}

function extractValidationDetail(detail: unknown): string | null {
  if (!Array.isArray(detail)) {
    return null;
  }

  const parts = detail
    .map((item) => {
      if (!isRecord(item)) {
        return stringifyValue(item);
      }

      const location = Array.isArray(item.loc)
        ? item.loc.map((segment) => String(segment)).join('.')
        : null;
      const message = pickString(item.msg, item.message, item.error);
      if (!location && !message) {
        return stringifyValue(item);
      }
      return [location, message].filter(Boolean).join(': ');
    })
    .filter((entry): entry is string => Boolean(entry));

  return parts.length > 0 ? sanitizeText(parts.join('; ')) : null;
}

function extractErrorCode(data: unknown): string | null {
  if (!isRecord(data)) {
    return null;
  }

  const detail = data.detail;
  if (isRecord(detail)) {
    return pickString(detail.error, detail.code, data.error, data.code);
  }

  return pickString(data.error, data.code);
}

function extractErrorPayloadText(data: unknown): string | null {
  if (typeof data === 'string') {
    const trimmed = data.trim();
    return trimmed ? sanitizeText(trimmed) : null;
  }

  if (Array.isArray(data)) {
    return extractValidationDetail(data) ?? stringifyValue(data);
  }

  if (!isRecord(data)) {
    return stringifyValue(data);
  }

  const detail = data.detail;
  if (isRecord(detail)) {
    return (
      pickString(detail.message, detail.error)
      ?? extractValidationDetail(detail.detail)
      ?? stringifyValue(detail)
    );
  }

  return (
    pickString(
      detail,
      data.message,
      data.error,
      data.title,
      data.reason,
      data.description,
      data.msg,
    )
    ?? extractValidationDetail(detail)
    ?? stringifyValue(data)
  );
}

function inferParsedErrorFlags(
  status?: number,
  category?: ApiErrorCategory,
): Pick<ParsedApiError, 'isAuthError' | 'isNetworkError' | 'isTimeoutError' | 'isValidationError'> {
  return {
    isAuthError: category === 'auth_required' || category === 'admin_unlock_required' || status === 401,
    isNetworkError: category === 'local_connection_failed' || category === 'upstream_network' || category === 'upstream_unavailable',
    isTimeoutError: category === 'upstream_timeout',
    isValidationError: category === 'validation_error' || status === 422,
  };
}

export function createParsedApiError(options: CreateParsedApiErrorOptions): ParsedApiError {
  const status = options.status;
  const category = options.category ?? 'unknown';
  const flags = inferParsedErrorFlags(status, category);

  return {
    title: options.title,
    message: sanitizeText(options.message),
    rawMessage: sanitizeText(options.rawMessage?.trim() || options.message),
    status,
    code: options.code,
    details: sanitizeUnknown(options.details),
    category,
    isAuthError: options.isAuthError ?? flags.isAuthError,
    isNetworkError: options.isNetworkError ?? flags.isNetworkError,
    isTimeoutError: options.isTimeoutError ?? flags.isTimeoutError,
    isValidationError: options.isValidationError ?? flags.isValidationError,
  };
}

export function isParsedApiError(value: unknown): value is ParsedApiError {
  return isRecord(value)
    && typeof value.title === 'string'
    && typeof value.message === 'string'
    && typeof value.rawMessage === 'string'
    && typeof value.category === 'string';
}

function extractCommonParsedErrorMetadata(error: unknown): {
  status?: number;
  code?: string;
  details?: unknown;
  rawMessage: string;
  errorMessage: string | null;
  responseText: string | null;
  payloadText: string | null;
  responseData: unknown;
} {
  const response = getResponse(error);
  const responseData = response?.data
    ?? (isRecord(error) ? (error as ErrorCarrier).data : undefined)
    ?? (isRecord(error) ? (error as ErrorCarrier).body : undefined)
    ?? (isRecord(error) ? (error as ErrorCarrier).detail : undefined)
    ?? (isRecord(error) ? (error as ErrorCarrier).details : undefined);
  const payloadText = extractErrorPayloadText(responseData);
  const errorMessage = getErrorMessage(error);
  const responseText = pickString(response?.statusText, isRecord(error) ? (error as ErrorCarrier).statusText : undefined);
  const causeMessage = getCauseMessage(error);
  const code = getErrorCode(error) || extractErrorCode(responseData);
  const rawMessage = pickString(
    payloadText,
    responseText,
    errorMessage,
    causeMessage,
    code,
    getErrorUrl(error),
  ) ?? DEFAULT_FALLBACK_MESSAGE;

  return {
    status: getErrorStatus(error) ?? response?.status,
    code: code ?? undefined,
    details: sanitizeUnknown(responseData),
    rawMessage: sanitizeText(rawMessage),
    errorMessage,
    responseText,
    payloadText,
    responseData,
  };
}

export function isApiRequestError(
  value: unknown,
): value is Error & ErrorCarrier & { parsedError: ParsedApiError } {
  return value instanceof Error
    && isRecord(value)
    && isParsedApiError((value as ErrorCarrier).parsedError);
}

function formatParsedApiError(parsed: ParsedApiError): string {
  if (!parsed.title.trim()) {
    return parsed.message;
  }
  if (parsed.title === parsed.message) {
    return parsed.title;
  }
  return `${parsed.title}：${parsed.message}`;
}

export function getParsedApiError(error: unknown): ParsedApiError {
  if (isParsedApiError(error)) {
    return error;
  }
  if (isRecord(error) && isParsedApiError((error as ErrorCarrier).parsedError)) {
    return (error as ErrorCarrier).parsedError as ParsedApiError;
  }
  return parseApiError(error);
}

export function createApiError(
  parsed: ParsedApiError,
  extra: { response?: ResponseLike; code?: string; cause?: unknown } = {},
): Error & ErrorCarrier & { status?: number; category: ApiErrorCategory; rawMessage: string } {
  const apiError = new Error(formatParsedApiError(parsed)) as Error & ErrorCarrier & {
    status?: number;
    category: ApiErrorCategory;
    rawMessage: string;
  };
  apiError.name = 'ApiRequestError';
  apiError.parsedError = parsed;
  apiError.response = extra.response;
  apiError.code = extra.code ?? parsed.code;
  apiError.status = parsed.status;
  apiError.category = parsed.category;
  apiError.rawMessage = parsed.rawMessage;
  if (extra.cause !== undefined) {
    apiError.cause = extra.cause;
  }
  return apiError;
}

export function attachParsedApiError(error: unknown): ParsedApiError {
  const parsed = parseApiError(error);
  if (isRecord(error)) {
    const carrier = error as ErrorCarrier;
    carrier.parsedError = parsed;
  }
  if (error instanceof Error) {
    error.name = 'ApiRequestError';
    error.message = formatParsedApiError(parsed);
  }
  return parsed;
}

export function parseApiError(error: unknown, fallbackMessage?: string): ParsedApiError {
  if (isParsedApiError(error)) {
    return createParsedApiError({
      title: error.title,
      message: error.message,
      rawMessage: error.rawMessage,
      status: error.status,
      code: error.code,
      details: error.details,
      category: error.category,
      isAuthError: error.isAuthError,
      isNetworkError: error.isNetworkError,
      isTimeoutError: error.isTimeoutError,
      isValidationError: error.isValidationError,
    });
  }

  if (isRecord(error) && isParsedApiError((error as ErrorCarrier).parsedError)) {
    return parseApiError((error as ErrorCarrier).parsedError, fallbackMessage);
  }

  const {
    status,
    code,
    details,
    rawMessage,
    errorMessage,
    responseText,
    payloadText,
    responseData,
  } = extractCommonParsedErrorMetadata(error);

  const matchText = buildMatchText([
    rawMessage,
    errorMessage,
    getCauseMessage(error),
    code,
    responseText,
    payloadText,
    extractErrorCode(responseData) || undefined,
    getErrorUrl(error),
  ]);
  const parsedFallback = fallbackMessage ? sanitizeText(fallbackMessage.trim()) : null;

  const buildError = (
    title: string,
    message: string,
    category: ApiErrorCategory,
    overrides: Partial<CreateParsedApiErrorOptions> = {},
  ) => createParsedApiError({
    title,
    message,
    rawMessage,
    status,
    code,
    details,
    category,
    ...overrides,
  });

  if (includesAny(matchText, ['agent mode is not enabled', 'agent_mode'])) {
    return buildError(
      'Agent 模式未开启',
      '当前功能依赖 Agent 模式，请先开启后再重试。',
      'agent_disabled',
    );
  }

  const hasStockCodeField = includesAny(matchText, ['stock_code', 'stock_codes']);
  const hasMissingParamText = includesAny(matchText, ['必须提供 stock_code 或 stock_codes', 'missing', 'required']);
  if (hasStockCodeField && hasMissingParamText) {
    return buildError(
      '请求缺少必要参数',
      '请先补充股票代码或必要输入后再试。',
      'missing_params',
      { isValidationError: true },
    );
  }

  if (
    code === 'duplicate_task'
    || includesAny(matchText, ['正在分析中', 'duplicate task', 'duplicate_task'])
    || (status === 409 && !code)
  ) {
    return buildError(
      '分析任务已在进行中',
      '同一标的已有分析任务正在运行，请等待当前任务完成后再试。',
      'analysis_conflict',
    );
  }

  if (code === 'portfolio_oversell' || includesAny(matchText, ['oversell detected'])) {
    return buildError(
      '卖出数量超过可用持仓',
      '卖出数量超过当前可用持仓，请删除或修正对应卖出流水后重试。',
      'portfolio_oversell',
    );
  }

  if (code === 'ibkr_session_required' || code === 'ibkr_session_invalid' || code === 'ibkr_session_expired') {
    return buildError(
      'IBKR 会话不可用',
      '只读授权暂不可用，请由具备操作权限的人员确认连接状态后重试。',
      'validation_error',
      { isValidationError: true },
    );
  }

  if (code === 'ibkr_account_mapping_conflict') {
    return buildError(
      'IBKR 账户映射冲突',
      '该账户映射已绑定到另一持仓账户。请由具备操作权限的人员确认映射后重试。',
      'validation_error',
      { isValidationError: true },
    );
  }

  if (
    code === 'ibkr_account_ambiguous'
    || code === 'ibkr_account_not_found'
    || code === 'ibkr_account_identifier_invalid'
    || code === 'ibkr_empty_accounts'
    || code === 'ibkr_connection_not_found'
    || code === 'ibkr_connection_type_invalid'
  ) {
    return buildError(
      '无法确定要同步的 IBKR 账户',
      '请由具备操作权限的人员确认当前授权范围与账户映射后重试。',
      'validation_error',
      { isValidationError: true },
    );
  }

  if (code === 'ibkr_payload_unsupported') {
    return buildError(
      '当前 IBKR 返回结构暂不受支持',
      '本次只读同步没有拿到当前版本可安全解析的账户数据。请改用 Flex 导入，或等待后端适配后再试。',
      'validation_error',
      { isValidationError: true },
    );
  }

  if (code === 'ibkr_upstream_error' || code === 'ibkr_sync_internal_error') {
    return buildError(
      'IBKR 只读同步暂时失败',
      '本地工作台仍可用，但这次 IBKR 只读同步没有完成。请稍后重试，或先改用 Flex 导入。',
      'upstream_unavailable',
    );
  }

  if (status === 401 || code === 'unauthorized' || includesAny(matchText, ['login required', 'not authenticated'])) {
    return buildError(
      '登录已失效',
      AUTH_FALLBACK_MESSAGE,
      'auth_required',
      { isAuthError: true },
    );
  }

  if (
    code === 'admin_unlock_required'
    || includesAny(matchText, ['admin settings are locked', 'verify admin password'])
  ) {
    return buildError(
      '管理员验证已过期',
      '请先重新验证管理员密码，再继续访问系统设置或管理员日志。',
      'admin_unlock_required',
      { isAuthError: true },
    );
  }

  if (code === 'admin_required' || includesAny(matchText, ['admin access required'])) {
    return buildError(
      '需要管理员账户',
      '当前页面或操作仅对管理员开放，请切换到管理员账户后再试。',
      'access_denied',
      { isAuthError: true },
    );
  }

  if (code === 'owner_mismatch' || includesAny(matchText, ['owner_id does not match the current user'])) {
    return buildError(
      '无法访问其他用户的数据',
      '当前账户只能访问自己的数据，请返回允许的页面继续使用。',
      'access_denied',
    );
  }

  if (status === 403 || includesAny(matchText, ['403 forbidden', 'status code 403', 'forbidden for url'])) {
    if (includesAny(matchText, ['fmp', 'financialmodelingprep'])) {
      return buildError(
        '上游数据源拒绝访问',
        'FMP 返回了 403，可能是 API Key、额度或权限限制。请稍后重试或检查相关配置。',
        'upstream_forbidden',
      );
    }

    if (includesAny(matchText, ['gemini', 'generativelanguage', 'google'])) {
      return buildError(
        '上游模型拒绝访问',
        'Gemini 返回了 403，可能是模型权限、Key 配额或渠道配置问题。',
        'upstream_forbidden',
      );
    }

    return buildError(
      '没有权限',
      ACCESS_DENIED_FALLBACK_MESSAGE,
      'access_denied',
    );
  }

  if (code === 'portfolio_busy' || includesAny(matchText, ['portfolio ledger is busy'])) {
    return buildError(
      '持仓账本正忙',
      '持仓账本正在处理另一笔变更，请稍后重试。',
      'portfolio_busy',
    );
  }

  const noConfiguredLlm = (
    includesAny(matchText, ['all llm models failed']) && includesAny(matchText, ['last error: none'])
  ) || includesAny(matchText, [
    'no llm configured',
    'litellm_model not configured',
    'ai analysis will be unavailable',
  ]);
  if (noConfiguredLlm) {
    return buildError(
      '系统没有配置可用的 LLM 模型',
      '请先在系统设置中配置主模型、可用渠道或相关 API Key 后再重试。',
      'llm_not_configured',
    );
  }

  if (includesAny(matchText, [
    'tool call',
    'function call',
    'does not support tools',
    'tools is not supported',
    'reasoning',
  ])) {
    return buildError(
      '当前模型不兼容工具调用',
      '当前模型不适合 Agent / 工具调用场景，请更换支持工具调用的模型后重试。',
      'model_tool_incompatible',
    );
  }

  if (includesAny(matchText, [
    'thought_signature',
    'missing function',
    'missing tool',
    'invalid tool call',
    'invalid function call',
  ])) {
    return buildError(
      '上游模型返回的数据结构不完整',
      '上游模型返回的工具调用结构不符合要求，请更换模型或关闭相关推理模式后重试。',
      'invalid_tool_call',
    );
  }

  if (
    includesAny(matchText, ['timeout', 'timed out', 'read timeout', 'connect timeout'])
    || code === 'ECONNABORTED'
    || status === 408
    || status === 504
  ) {
    return buildError(
      '请求超时',
      TIMEOUT_FALLBACK_MESSAGE,
      'upstream_timeout',
      { isTimeoutError: true },
    );
  }

  if (
    status === 502
    || status === 503
    || status === 500
    || status === 501
    || status === 504
    || status === 505
    || status === 507
    || status === 508
    || status === 509
  ) {
    if (includesAny(matchText, ['gemini', 'generativelanguage', 'model overloaded', 'service unavailable'])) {
      return buildError(
        '上游模型暂时不可用',
        'Gemini 当前繁忙或临时不可用，系统会在下一次分析时继续重试，请稍后再试。',
        'upstream_unavailable',
      );
    }

    return buildError(
      '服务器暂时不可用',
      SERVER_UNAVAILABLE_FALLBACK_MESSAGE,
      'upstream_unavailable',
      { isNetworkError: true },
    );
  }

  if (includesAny(matchText, [
    'balance is insufficient',
    'account balance is insufficient',
    'insufficient balance',
    'please recharge your account',
    'quota exceeded',
    'credit balance',
  ])) {
    return buildError(
      '上游模型额度不足',
      '当前 LLM 渠道余额或额度不足，请充值、切换可用模型，或在系统设置中改用其他渠道后重试。',
      'upstream_forbidden',
    );
  }

  const hasLlmProviderHint = includesAny(matchText, [
    'chat/completions',
    'generativelanguage',
    'openai',
    'gemini',
  ]);
  if (status === 400 && hasLlmProviderHint) {
    return buildError(
      '上游模型接口拒绝了当前请求',
      '本地服务正常，但上游模型接口拒绝了请求，请检查模型名称、参数格式或工具调用兼容性。',
      'upstream_llm_400',
    );
  }

  const localConnectionFailed = !getResponse(error) && (
    includesAny(matchText, ['fetch failed', 'failed to fetch', 'network error', 'connection refused', 'econnrefused'])
    || code === 'ERR_NETWORK'
    || code === 'ECONNREFUSED'
    || code === 'ENOTFOUND'
    || code === 'ECONNRESET'
  );
  if (localConnectionFailed) {
    return buildError(
      '网络连接失败',
      NETWORK_FALLBACK_MESSAGE,
      'local_connection_failed',
      { isNetworkError: true },
    );
  }

  if (status === 404) {
    return buildError(
      '请求的资源不存在',
      NOT_FOUND_FALLBACK_MESSAGE,
      'http_error',
    );
  }

  if (status === 422 || Array.isArray(responseData) || includesAny(matchText, ['validation', 'invalid parameter', 'unprocessable'])) {
    const validationText = extractValidationDetail(responseData) || payloadText;
    return buildError(
      '请求参数无效',
      validationText ? `${VALIDATION_FALLBACK_MESSAGE} ${validationText}` : VALIDATION_FALLBACK_MESSAGE,
      'validation_error',
      { isValidationError: true },
    );
  }

  if (status === 401) {
    return buildError(
      '登录已失效，请重新登录。',
      AUTH_FALLBACK_MESSAGE,
      'auth_required',
      { isAuthError: true },
    );
  }

  if (status === 403) {
    return buildError(
      '没有权限执行该操作。',
      ACCESS_DENIED_FALLBACK_MESSAGE,
      'access_denied',
    );
  }

  if (payloadText || status) {
    return buildError(
      '请求失败',
      payloadText ?? (parsedFallback || `请求未成功完成（HTTP ${status}）。`),
      'http_error',
      { isValidationError: false },
    );
  }

  return buildError(
    '请求失败',
    parsedFallback || DEFAULT_FALLBACK_MESSAGE,
    'unknown',
  );
}

export function getApiErrorMessage(error: unknown, fallbackMessage?: string): string {
  return parseApiError(error, fallbackMessage).message;
}

export function isAuthError(error: unknown): boolean {
  const parsed = parseApiError(error);
  return Boolean(parsed.isAuthError || parsed.status === 401 || parsed.category === 'auth_required' || parsed.category === 'admin_unlock_required');
}

export function isNetworkError(error: unknown): boolean {
  const parsed = parseApiError(error);
  return Boolean(parsed.isNetworkError || parsed.category === 'local_connection_failed' || parsed.category === 'upstream_network' || parsed.category === 'upstream_unavailable');
}

export function isTimeoutError(error: unknown): boolean {
  const parsed = parseApiError(error);
  return Boolean(parsed.isTimeoutError || parsed.category === 'upstream_timeout');
}
