import apiClient from './index';
import { API_BASE_URL } from '../utils/constants';
import { createApiError, createParsedApiError, isApiRequestError, parseApiError } from './error';

export interface ChatStreamOptions {
  signal?: AbortSignal;
}

export interface ChatRequest {
  message: string;
  skills?: string[];
}

export interface ChatStreamRequest extends ChatRequest {
  session_id?: string;
  context?: unknown;
}

export interface ChatResponse {
  success: boolean;
  content: string;
  session_id: string;
  error?: string;
}

export interface SkillInfo {
  id: string;
  name: string;
  description: string;
}

export interface AgentStatusResponse {
  enabled: boolean;
}

export interface AgentModelDeployment {
  deployment_id: string;
  model: string;
  provider: string;
  source: string;
  api_base?: string | null;
  deployment_name?: string | null;
  is_primary?: boolean;
  is_fallback?: boolean;
}

export interface AgentModelsResponse {
  models: AgentModelDeployment[];
}

export type AgentProviderHealthStatus = 'available' | 'not_configured' | 'disabled' | 'offline' | 'unknown';

export interface AgentProviderHealthItem {
  id: string;
  label: string;
  status: AgentProviderHealthStatus;
  model?: string | null;
  selected?: boolean;
  reason?: string | null;
}

export interface AgentProviderHealthResponse {
  routingMode: 'AUTO' | 'MANUAL' | string;
  currentProvider?: string | null;
  currentModel?: string | null;
  providers: AgentProviderHealthItem[];
}

export type StockEvidenceStatus = 'available' | 'partial' | 'missing' | 'stale' | 'fallback' | 'unknown' | 'error';

export interface AgentStockEvidenceItem {
  symbol: string;
  market?: string;
  quote?: {
    status: StockEvidenceStatus;
    price?: number | null;
    changePct?: number | null;
    currency?: string | null;
    provider?: string | null;
    updatedAt?: string | null;
  };
  technical?: {
    status: StockEvidenceStatus;
    trend?: string | null;
    ma5?: number | null;
    ma10?: number | null;
    ma20?: number | null;
    ma60?: number | null;
    rsi14?: number | null;
    support?: number | null;
    resistance?: number | null;
    provider?: string | null;
    updatedAt?: string | null;
  };
  fundamental?: {
    status: StockEvidenceStatus;
    marketCap?: number | null;
    peTtm?: number | null;
    pb?: number | null;
    beta?: number | null;
    revenueTtm?: number | null;
    netIncomeTtm?: number | null;
    fcfTtm?: number | null;
    provider?: string | null;
    updatedAt?: string | null;
    missingFields?: string[];
  };
  news?: {
    status: StockEvidenceStatus;
    latestHeadline?: string | null;
    provider?: string | null;
  };
}

export interface AgentStockEvidenceResponse {
  symbols: string[];
  items: AgentStockEvidenceItem[];
  meta?: {
    generatedAt?: string | null;
    source?: string;
  };
}

export interface SkillsResponse {
  skills: SkillInfo[];
  default_skill_id: string;
}

export interface ChatSessionItem {
  session_id: string;
  title: string;
  message_count: number;
  created_at: string | null;
  last_active: string | null;
}

export interface ChatSessionMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string | null;
}

export const agentApi = {
  async chat(payload: ChatStreamRequest): Promise<ChatResponse> {
    const response = await apiClient.post<ChatResponse>('/api/v1/agent/chat', payload, {
      timeout: 120000,
    });
    return response.data;
  },
  async getSkills(): Promise<SkillsResponse> {
    const response = await apiClient.get<SkillsResponse>('/api/v1/agent/skills');
    return response.data;
  },
  async getStatus(): Promise<AgentStatusResponse> {
    const response = await apiClient.get<AgentStatusResponse>('/api/v1/agent/status');
    return response.data;
  },
  async getModels(): Promise<AgentModelsResponse> {
    const response = await apiClient.get<AgentModelsResponse>('/api/v1/agent/models');
    return response.data;
  },
  async getProviderHealth(): Promise<AgentProviderHealthResponse> {
    const response = await apiClient.get<AgentProviderHealthResponse>('/api/v1/agent/provider-health');
    return response.data;
  },
  async getStockEvidence(symbols: string[]): Promise<AgentStockEvidenceResponse> {
    const response = await apiClient.get<AgentStockEvidenceResponse>('/api/v1/agent/stock-evidence', {
      params: { symbols: symbols.slice(0, 3).join(',') },
      timeout: 15000,
    });
    return response.data;
  },
  async getChatSessions(limit = 50): Promise<ChatSessionItem[]> {
    const response = await apiClient.get<{ sessions: ChatSessionItem[] }>('/api/v1/agent/chat/sessions', { params: { limit } });
    return response.data.sessions;
  },
  async getChatSessionMessages(sessionId: string): Promise<ChatSessionMessage[]> {
    const response = await apiClient.get<{ messages: ChatSessionMessage[] }>(`/api/v1/agent/chat/sessions/${sessionId}`);
    return response.data.messages;
  },
  async deleteChatSession(sessionId: string): Promise<void> {
    await apiClient.delete(`/api/v1/agent/chat/sessions/${sessionId}`);
  },
  async sendChat(content: string): Promise<{ success: boolean }> {
    const response = await apiClient.post<{
      success: boolean;
      error?: string;
      message?: string;
    }>('/api/v1/agent/chat/send', { content });
    const data = response.data;
    if (data.success === false) {
      throw new Error(data.message || '发送失败');
    }
    return { success: true };
  },
  async chatStream(
    payload: ChatStreamRequest,
    options?: ChatStreamOptions,
  ): Promise<Response> {
    const base = API_BASE_URL || '';
    const url = `${base}/api/v1/agent/chat/stream`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          'X-Requested-With': 'fetch',
        },
        body: JSON.stringify(payload),
        credentials: 'include',
        cache: 'no-store',
        signal: options?.signal,
      });

      if (response.ok) {
        if (!response.body || typeof response.body.getReader !== 'function') {
          const parsed = createParsedApiError({
            title: '流式响应不可用',
            message: '当前环境不支持流式响应，已准备回退到标准响应模式。',
            category: 'unknown',
          });
          throw createApiError(parsed, {
            response: {
              status: 200,
              statusText: 'OK',
            },
          });
        }
        return response;
      }

      if (response.status === 401) {
        const path = window.location.pathname + window.location.search;
        if (!path.startsWith('/login')) {
          const redirect = encodeURIComponent(path);
          window.location.assign(`/login?redirect=${redirect}`);
        }
      }

      const contentType = response.headers.get('content-type') || '';
      let responseData: unknown = null;
      if (contentType.includes('application/json')) {
        responseData = await response.json().catch(() => null);
      } else {
        responseData = await response.text().catch(() => null);
      }

      const parsed = parseApiError({
        response: {
          status: response.status,
          statusText: response.statusText,
          data: responseData,
        },
      });
      throw createApiError(parsed, {
        response: {
          status: response.status,
          statusText: response.statusText,
          data: responseData,
        },
      });
    } catch (error: unknown) {
      if (isApiRequestError(error)) {
        throw error;
      }
      if (error instanceof Error && error.name === 'AbortError') {
        throw error;
      }

      const parsed = parseApiError(error);
      throw createApiError(parsed, { cause: error });
    }
  },
};
