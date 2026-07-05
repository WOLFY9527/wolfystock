import axios, {
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios';
import { API_BASE_URL } from '../utils/constants';
import { getStoredUiLanguage } from '../i18n/core';
import { attachParsedApiError } from './error';

export type ApiTimeoutTier = 'quick' | 'standard' | 'analysis';

declare module 'axios' {
  export interface AxiosRequestConfig {
    timeoutTier?: ApiTimeoutTier;
    dedupe?: boolean;
  }
}

const DEFAULT_TIMEOUT_MS = 30000;
const TIMEOUT_TIER_MS: Record<ApiTimeoutTier, number> = {
  quick: 5000,
  standard: 15000,
  analysis: DEFAULT_TIMEOUT_MS,
};

const STREAMING_PATH_RE = /\/(stream|sse)(?:\/|$)|\/tasks\/stream(?:\/|$)/i;
const SHORT_WINDOW_GET_CACHE_TTL_MS = 750;
const SHORT_WINDOW_GET_CACHE_PATHS = new Set([
  '/api/v1/auth/status',
  '/api/v1/market/market-briefing',
]);
type InFlightGetRequest = {
  promise: Promise<AxiosResponse>;
  resolve: (response: AxiosResponse) => void;
  reject: (error: unknown) => void;
};
type ShortWindowGetCacheEntry = {
  path: string;
  expiresAt: number;
  response: AxiosResponse;
};

const inFlightGetRequests = new Map<string, InFlightGetRequest>();
const shortWindowGetResponses = new Map<string, ShortWindowGetCacheEntry>();

function resolveRequestLanguage(): string {
  if (typeof document !== 'undefined') {
    const language = document.documentElement.lang.toLowerCase();
    if (language.startsWith('zh')) {
      return 'zh-CN,zh;q=0.9,en;q=0.8';
    }
    if (language.startsWith('en')) {
      return 'en-US,en;q=0.9,zh;q=0.8';
    }
  }

  const storedLanguage = getStoredUiLanguage();
  return storedLanguage === 'en'
    ? 'en-US,en;q=0.9,zh;q=0.8'
    : 'zh-CN,zh;q=0.9,en;q=0.8';
}

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: DEFAULT_TIMEOUT_MS,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

function stableSerialize(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }

  if (typeof value !== 'object') {
    return JSON.stringify(value);
  }

  if (value instanceof URLSearchParams) {
    return stableSerialize(Array.from(value.entries()).sort(([a], [b]) => a.localeCompare(b)));
  }

  if (Array.isArray(value)) {
    return `[${value.map((item) => stableSerialize(item)).join(',')}]`;
  }

  const entries = Object.entries(value as Record<string, unknown>)
    .filter(([, entry]) => typeof entry !== 'undefined')
    .sort(([a], [b]) => a.localeCompare(b));

  return `{${entries.map(([key, entry]) => `${JSON.stringify(key)}:${stableSerialize(entry)}`).join(',')}}`;
}

function buildDedupeKey(config: InternalAxiosRequestConfig): string {
  return [
    'get',
    config.baseURL ?? '',
    config.url ?? '',
    stableSerialize(config.params),
    stableSerialize(config.data),
  ].join('|');
}

function resolveRequestPath(config: InternalAxiosRequestConfig): string {
  const requestUrl = config.url ?? '';
  const baseUrl = config.baseURL || 'https://wolfystock.invalid';

  try {
    return new URL(requestUrl, baseUrl).pathname;
  } catch {
    return requestUrl.split('?')[0] ?? requestUrl;
  }
}

function isStreamingRequest(config: InternalAxiosRequestConfig): boolean {
  if (config.responseType === 'stream') {
    return true;
  }

  return STREAMING_PATH_RE.test(config.url ?? '');
}

function shouldDedupeRequest(config: InternalAxiosRequestConfig): boolean {
  return config.dedupe !== false
    && (config.method ?? 'get').toLowerCase() === 'get'
    && !isStreamingRequest(config);
}

function shouldUseShortWindowCache(config: InternalAxiosRequestConfig): boolean {
  return shouldDedupeRequest(config) && SHORT_WINDOW_GET_CACHE_PATHS.has(resolveRequestPath(config));
}

function getShortWindowCachedResponse(dedupeKey: string): AxiosResponse | null {
  const cached = shortWindowGetResponses.get(dedupeKey);
  if (!cached) {
    return null;
  }

  if (Date.now() >= cached.expiresAt) {
    shortWindowGetResponses.delete(dedupeKey);
    return null;
  }

  return cached.response;
}

function storeShortWindowCachedResponse(
  config: InternalAxiosRequestConfig,
  dedupeKey: string,
  response: AxiosResponse
): void {
  if (!shouldUseShortWindowCache(config)) {
    return;
  }

  shortWindowGetResponses.set(dedupeKey, {
    path: resolveRequestPath(config),
    expiresAt: Date.now() + SHORT_WINDOW_GET_CACHE_TTL_MS,
    response,
  });
}

export function invalidateApiShortWindowCache(path?: string): void {
  if (!path) {
    shortWindowGetResponses.clear();
    return;
  }

  for (const [key, entry] of shortWindowGetResponses.entries()) {
    if (entry.path === path) {
      shortWindowGetResponses.delete(key);
    }
  }
}

function applyTimeoutTier(config: InternalAxiosRequestConfig): void {
  if (config.timeoutTier) {
    config.timeout = TIMEOUT_TIER_MS[config.timeoutTier];
  }
}

function wrapGetDedupeAdapter(config: InternalAxiosRequestConfig): void {
  if (!shouldDedupeRequest(config)) {
    return;
  }

  const dedupeKey = buildDedupeKey(config);
  const cachedResponse = getShortWindowCachedResponse(dedupeKey);
  if (cachedResponse) {
    config.adapter = async () => cachedResponse;
    return;
  }

  const existingRequest = inFlightGetRequests.get(dedupeKey);
  if (existingRequest) {
    config.adapter = () => existingRequest.promise;
    return;
  }

  const originalAdapter = axios.getAdapter(config.adapter ?? apiClient.defaults.adapter) as AxiosAdapter;
  let resolveRequest!: (response: AxiosResponse) => void;
  let rejectRequest!: (error: unknown) => void;
  const entry: InFlightGetRequest = {
    promise: new Promise<AxiosResponse>((resolve, reject) => {
      resolveRequest = resolve;
      rejectRequest = reject;
    }),
    resolve: resolveRequest,
    reject: rejectRequest,
  };
  inFlightGetRequests.set(dedupeKey, entry);

  config.adapter = (adapterConfig) => {
    try {
      originalAdapter(adapterConfig)
        .then((response) => {
          storeShortWindowCachedResponse(config, dedupeKey, response);
          entry.resolve(response);
        }, entry.reject)
        .finally(() => {
          if (inFlightGetRequests.get(dedupeKey) === entry) {
            inFlightGetRequests.delete(dedupeKey);
          }
        });
    } catch (error) {
      entry.reject(error);
      if (inFlightGetRequests.get(dedupeKey) === entry) {
        inFlightGetRequests.delete(dedupeKey);
      }
    }
    return entry.promise;
  };
}

function isAuthOwnershipRequest(config: InternalAxiosRequestConfig | undefined): boolean {
  const path = config ? resolveRequestPath(config) : '';
  return path === '/api/v1/auth/status' || path === '/api/v1/auth/me';
}

function shouldRedirectToLogin(error: unknown): boolean {
  const response = (error as { response?: { status?: number; config?: InternalAxiosRequestConfig } })?.response;
  if (response?.status !== 401) {
    return false;
  }
  if (isAuthOwnershipRequest(response.config)) {
    return false;
  }
  if (typeof window === 'undefined') {
    return false;
  }
  const path = window.location.pathname + window.location.search;
  return !path.startsWith('/login') && !path.startsWith('/register');
}

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (shouldRedirectToLogin(error)) {
      const path = window.location.pathname + window.location.search;
      const redirect = encodeURIComponent(path);
      window.location.assign(`/login?redirect=${redirect}`);
    }
    attachParsedApiError(error);
    return Promise.reject(error);
  }
);

apiClient.interceptors.request.use((config) => {
  config.headers = config.headers ?? {};
  config.headers['Accept-Language'] = resolveRequestLanguage();
  applyTimeoutTier(config);
  wrapGetDedupeAdapter(config);
  return config;
});

export default apiClient;
