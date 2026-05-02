import apiClient from './index';
import { toCamelCase } from './utils';

export interface ExecutionLogEvent {
  id: number;
  eventAt?: string | null;
  level?: string | null;
  phase: string;
  category?: string | null;
  eventName?: string | null;
  step?: string | null;
  action?: string | null;
  outcome?: string | null;
  reason?: string | null;
  target?: string | null;
  status: string;
  truthLevel: string;
  message?: string | null;
  errorCode?: string | null;
  detail?: Record<string, unknown>;
}

export interface ExecutionLogSessionSummary {
  sessionId: string;
  taskId?: string | null;
  queryId?: string | null;
  analysisHistoryId?: number | null;
  code?: string | null;
  name?: string | null;
  overallStatus: string;
  truthLevel: string;
  startedAt?: string | null;
  endedAt?: string | null;
  summary?: Record<string, unknown>;
  readableSummary?: {
    actorUserId?: string | null;
    actorUsername?: string | null;
    actorDisplay?: string | null;
    actorRole?: string | null;
    actorType?: string | null;
    actorSessionId?: string | null;
    actorRequestId?: string | null;
    sessionKind?: string | null;
    subsystem?: string | null;
    actionName?: string | null;
    destructive?: boolean;
    finalAiModel?: string | null;
    aiAttemptsCount?: number;
    aiFallbackUsed?: boolean;
    finalMarketSource?: string | null;
    finalFundamentalSource?: string | null;
    finalNewsSource?: string | null;
    finalSentimentSource?: string | null;
    dataFallbackUsed?: boolean;
    notificationClassification?: string | null;
    topFailureReason?: string | null;
    scannerRunId?: number | null;
    scannerMarket?: string | null;
    scannerProfile?: string | null;
    scannerProfileLabel?: string | null;
    scannerShortlistCount?: number | null;
    scannerFallbackCount?: number | null;
    scannerProviderFailureCount?: number | null;
    scannerProvidersUsed?: string[];
    scannerCoverageSummary?: string | null;
    summaryParagraph?: string | null;
    status?: string;
    operationCategory?: string | null;
    operationType?: string | null;
    operationTarget?: string | null;
    operationStatus?: string | null;
    keyMetric?: string | null;
    logLevel?: string | null;
    logCategory?: string | null;
    eventName?: string | null;
    eventMessage?: string | null;
    requestId?: string | null;
    traceId?: string | null;
    reason?: string | null;
    errorSummary?: string | null;
    contextLabel?: string | null;
    provider?: string | null;
    endpoint?: string | null;
    component?: string | null;
    source?: string | null;
  };
}

export interface ExecutionLogSessionDetail extends ExecutionLogSessionSummary {
  events: ExecutionLogEvent[];
  operationDetail?: {
    operationCategory?: string | null;
    operationType?: string | null;
    target?: string | null;
    status?: string | null;
    keyMetric?: string | null;
    durationMs?: number | null;
    aiCalls?: Array<Record<string, unknown>>;
    dataSourceCalls?: Array<Record<string, unknown>>;
    systemFallbacks?: Array<string | Record<string, unknown>>;
    systemOperation?: Record<string, unknown>;
    finalResult?: string | null;
    timeline?: Array<Record<string, unknown>>;
    diagnostics?: Array<Record<string, unknown>>;
  };
}

export interface ExecutionLogSessionListResponse {
  total: number;
  items: ExecutionLogSessionSummary[];
  summary?: {
    errorCount?: number;
    warningCount?: number;
    dataSourceFailureCount?: number;
    slowRequestCount?: number;
    latestCriticalAt?: string | null;
    healthSummary?: AdminLogHealthSummary | null;
  };
}

export interface AdminLogHealthBucket {
  key: string;
  label: string;
  count: number;
}

export interface AdminLogTopError {
  id: string;
  event?: string | null;
  category?: string | null;
  provider?: string | null;
  source?: string | null;
  reason?: string | null;
  errorSummary?: string | null;
  startedAt?: string | null;
  status?: string | null;
}

export interface AdminLogHealthSummary {
  totalEvents: number;
  failedEvents: number;
  warningEvents: number;
  slowEvents: number;
  failureRate: number;
  status: 'healthy' | 'degraded' | 'failing' | string;
  failuresByCategory: AdminLogHealthBucket[];
  failuresByProvider: AdminLogHealthBucket[];
  failuresByReason: AdminLogHealthBucket[];
  topRecentErrors: AdminLogTopError[];
  actorBreakdown: AdminLogHealthBucket[];
  latestCriticalError?: AdminLogTopError | null;
}

export interface ExecutionStep {
  id?: string | null;
  executionId?: string | null;
  name: string;
  label: string;
  category?: string | null;
  provider?: string | null;
  model?: string | null;
  endpoint?: string | null;
  apiPath?: string | null;
  status: string;
  reason?: string | null;
  message?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
  durationMs?: number | null;
  errorType?: string | null;
  errorMessage?: string | null;
  recordId?: string | null;
  metadata?: Record<string, unknown>;
}

export interface BusinessEvent {
  id: string;
  event: string;
  category: string;
  type?: string | null;
  eventType?: string | null;
  status: string;
  summary: string;
  subject?: string | null;
  symbol?: string | null;
  market?: string | null;
  actorType?: string | null;
  actorLabel?: string | null;
  contextLabel?: string | null;
  route?: string | null;
  endpoint?: string | null;
  provider?: string | null;
  source?: string | null;
  component?: string | null;
  feature?: string | null;
  reason?: string | null;
  errorSummary?: string | null;
  traceId?: string | null;
  rootCauseSummary?: string | null;
  stepTraceAvailable?: boolean | null;
  analysisType?: string | null;
  strategyId?: string | null;
  scannerId?: string | null;
  backtestId?: string | null;
  userId?: string | null;
  requestId?: string | null;
  recordId?: string | null;
  startedAt?: string | null;
  finishedAt?: string | null;
  durationMs?: number | null;
  stepCount: number;
  successStepCount: number;
  failedStepCount: number;
  skippedStepCount?: number;
  unknownStepCount?: number;
  metadata?: Record<string, unknown>;
}

export interface BusinessEventDetail extends BusinessEvent {
  steps: ExecutionStep[];
}

export interface BusinessEventListResponse {
  total: number;
  limit: number;
  offset: number;
  hasMore: boolean;
  items: BusinessEvent[];
  healthSummary?: AdminLogHealthSummary | null;
}

export interface AdminLogStorageSummary {
  totalLogCount: number;
  totalEventCount: number;
  oldestLogTimestamp?: string | null;
  newestLogTimestamp?: string | null;
  retentionDays: number;
  retentionCutoff?: string | null;
  logsOlderThanRetentionCount: number;
  estimatedStorageBytes?: number | null;
  warningThresholdCount: number;
  criticalThresholdCount: number;
  warningThresholdStorageBytes?: number | null;
  status: 'ok' | 'warning' | 'critical' | string;
  statusReasons: string[];
  recommendedCleanupAction: string;
  lastCleanupTimestamp?: string | null;
}

export interface AdminLogCleanupResponse {
  dryRun: boolean;
  cutoff?: string | null;
  matchedLogCount: number;
  matchedEventCount: number;
  deletedLogCount: number;
  deletedEventCount: number;
  statusFilter?: string | null;
  categoryFilter?: string | null;
}

function normalizeSessionSummary(payload: Record<string, unknown>): ExecutionLogSessionSummary {
  const normalized = toCamelCase<ExecutionLogSessionSummary>(payload);
  return {
    ...normalized,
    readableSummary: normalized.readableSummary && typeof normalized.readableSummary === 'object'
      ? normalized.readableSummary
      : {},
  };
}

function normalizeSessionDetail(payload: Record<string, unknown>): ExecutionLogSessionDetail {
  const normalized = toCamelCase<ExecutionLogSessionDetail>(payload);
  return {
    ...normalized,
    readableSummary: normalized.readableSummary && typeof normalized.readableSummary === 'object'
      ? normalized.readableSummary
      : {},
    events: Array.isArray(normalized.events) ? normalized.events : [],
    operationDetail: normalized.operationDetail && typeof normalized.operationDetail === 'object'
      ? normalized.operationDetail
      : {},
  };
}

export const adminLogsApi = {
  listBusinessEvents: async (
    params: {
      category?: string;
      type?: string;
      subject?: string;
      symbol?: string;
      scannerId?: string;
      strategyId?: string;
      backtestId?: string;
      requestId?: string;
      userId?: string;
      status?: string;
      query?: string;
      since?: string;
      limit?: number;
      offset?: number;
    },
  ): Promise<BusinessEventListResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/admin/logs',
      {
        params: {
          ...params,
          scanner_id: params.scannerId,
          strategy_id: params.strategyId,
          backtest_id: params.backtestId,
          request_id: params.requestId,
          user_id: params.userId,
        },
      },
    );
    const normalized = toCamelCase<BusinessEventListResponse>(response.data);
    return {
      total: Number(normalized.total || 0),
      limit: Number(normalized.limit || params.limit || 50),
      offset: Number(normalized.offset || params.offset || 0),
      hasMore: Boolean(normalized.hasMore),
      healthSummary: normalized.healthSummary as AdminLogHealthSummary | null | undefined,
      items: Array.isArray(normalized.items)
        ? normalized.items.map((item) => toCamelCase<BusinessEvent>(item as unknown as Record<string, unknown>))
        : [],
    };
  },

  getBusinessEventDetail: async (eventId: string): Promise<BusinessEventDetail> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/admin/logs/${encodeURIComponent(eventId)}`,
    );
    const normalized = toCamelCase<BusinessEventDetail>(response.data);
    return {
      ...normalized,
      steps: Array.isArray(normalized.steps) ? normalized.steps : [],
    };
  },

  getStorageSummary: async (): Promise<AdminLogStorageSummary> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/logs/storage/summary');
    const normalized = toCamelCase<AdminLogStorageSummary>(response.data);
    return {
      totalLogCount: Number(normalized.totalLogCount || 0),
      totalEventCount: Number(normalized.totalEventCount || 0),
      oldestLogTimestamp: normalized.oldestLogTimestamp || null,
      newestLogTimestamp: normalized.newestLogTimestamp || null,
      retentionDays: Number(normalized.retentionDays || 90),
      retentionCutoff: normalized.retentionCutoff || null,
      logsOlderThanRetentionCount: Number(normalized.logsOlderThanRetentionCount || 0),
      estimatedStorageBytes: typeof normalized.estimatedStorageBytes === 'number' ? normalized.estimatedStorageBytes : null,
      warningThresholdCount: Number(normalized.warningThresholdCount || 50000),
      criticalThresholdCount: Number(normalized.criticalThresholdCount || 100000),
      warningThresholdStorageBytes: typeof normalized.warningThresholdStorageBytes === 'number' ? normalized.warningThresholdStorageBytes : null,
      status: normalized.status || 'ok',
      statusReasons: Array.isArray(normalized.statusReasons) ? normalized.statusReasons : [],
      recommendedCleanupAction: normalized.recommendedCleanupAction || '',
      lastCleanupTimestamp: normalized.lastCleanupTimestamp || null,
    };
  },

  cleanupLogs: async (
    params: {
      useRetention?: boolean;
      olderThan?: string;
      dryRun?: boolean;
      status?: string;
      category?: string;
      batchSize?: number;
    },
  ): Promise<AdminLogCleanupResponse> => {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/admin/logs/cleanup', params);
    const normalized = toCamelCase<AdminLogCleanupResponse>(response.data);
    return {
      dryRun: Boolean(normalized.dryRun),
      cutoff: normalized.cutoff || null,
      matchedLogCount: Number(normalized.matchedLogCount || 0),
      matchedEventCount: Number(normalized.matchedEventCount || 0),
      deletedLogCount: Number(normalized.deletedLogCount || 0),
      deletedEventCount: Number(normalized.deletedEventCount || 0),
      statusFilter: normalized.statusFilter || null,
      categoryFilter: normalized.categoryFilter || null,
    };
  },

  listSessions: async (
    params: {
      taskId?: string;
      stock?: string;
      status?: string;
      minLevel?: string;
      level?: string;
      category?: string;
      query?: string;
      provider?: string;
      model?: string;
      channel?: string;
      since?: string;
      limit?: number;
      offset?: number;
    },
  ): Promise<ExecutionLogSessionListResponse> => {
    const requestParams = {
      ...params,
      min_level: params.minLevel,
      task_id: params.taskId,
    };
    delete requestParams.minLevel;
    delete requestParams.taskId;
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/admin/logs/sessions',
      {
        params: requestParams,
      },
    );
    const normalized = toCamelCase<ExecutionLogSessionListResponse>(response.data);
    return {
      total: Number(normalized.total || 0),
      summary: normalized.summary,
      items: Array.isArray(normalized.items)
        ? normalized.items.map((item) => normalizeSessionSummary(item as unknown as Record<string, unknown>))
        : [],
    };
  },

  getSessionDetail: async (sessionId: string): Promise<ExecutionLogSessionDetail> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/admin/logs/sessions/${encodeURIComponent(sessionId)}`,
    );
    return normalizeSessionDetail(response.data);
  },
};
