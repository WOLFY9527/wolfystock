import axios from 'axios';
import { API_BASE_URL } from '../utils/constants';
import { getStoredUiLanguage } from '../i18n/core';
import { attachParsedApiError } from './error';

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
  timeout: 30000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const path = window.location.pathname + window.location.search;
      if (!path.startsWith('/login')) {
        const redirect = encodeURIComponent(path);
        window.location.assign(`/login?redirect=${redirect}`);
      }
    }
    attachParsedApiError(error);
    return Promise.reject(error);
  }
);

apiClient.interceptors.request.use((config) => {
  config.headers = config.headers ?? {};
  config.headers['Accept-Language'] = resolveRequestLanguage();
  return config;
});

export default apiClient;
