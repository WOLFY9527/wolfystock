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

export interface AdminDataMissingDrilldownItem {
  affectedSurface: string;
  symbol?: string | null;
  market?: string | null;
  missingDomain: string;
  provider?: string | null;
  source?: string | null;
  freshnessStatus: string;
  fallbackUsed: boolean;
  stale: boolean;
  partial: boolean;
  reasonCode: string;
  latestSeenAt?: string | null;
  count: number;
  sampleEventIds: string[];
  sampleSessionIds: string[];
  sampleBusinessEventIds: string[];
}

export interface AdminDataMissingDrilldownResponse {
  total: number;
  items: AdminDataMissingDrilldownItem[];
}

export interface AdminOperatorIssueRollupItem {
  issueId: string;
  issueClass: string;
  issueTitle: string;
  severity: string;
  count: number;
  latestTimestamp?: string | null;
  firstTimestamp?: string | null;
  sampleEventIds: string[];
  affectedSurfaces: string[];
  affectedDomains: string[];
  provider?: string | null;
  source?: string | null;
  model?: string | null;
  channel?: string | null;
  reasonCode: string;
  eventType?: string | null;
  freshnessStatus?: string | null;
  status?: string | null;
  operatorGuidance: string;
}

export interface AdminOperatorIssueRollupResponse {
  total: number;
  items: AdminOperatorIssueRollupItem[];
}

export interface AdminIncidentTimelineLookup {
  sessionId?: string | null;
  requestId?: string | null;
  queryId?: string | null;
  symbol?: string | null;
  dateFrom?: string | null;
  dateTo?: string | null;
  limit: number;
}

export interface AdminIncidentTimelineNavigation {
  sessionId?: string | null;
  businessEventId?: string | null;
  queryId?: string | null;
  analysisHistoryId?: number | null;
  eventId?: string | null;
}

export interface AdminIncidentTimelineItem {
  id: string;
  kind: string;
  timestamp?: string | null;
  status: string;
  severity: string;
  title: string;
  summary?: string | null;
  sessionId?: string | null;
  businessEventId?: string | null;
  queryId?: string | null;
  requestId?: string | null;
  symbol?: string | null;
  phase?: string | null;
  category?: string | null;
  provider?: string | null;
  model?: string | null;
  channel?: string | null;
  reasonCode?: string | null;
  navigation: AdminIncidentTimelineNavigation;
}

export interface AdminIncidentTimelineHook {
  kind: string;
  status: string;
  summary: string;
  count: number;
  latestAt?: string | null;
  provider?: string | null;
  model?: string | null;
  channel?: string | null;
  reasonCode?: string | null;
  sampleSessionIds: string[];
  sampleBusinessEventIds: string[];
}

export interface AdminIncidentTimelineEmptyState {
  reason?: string | null;
  readOnly: boolean;
  message?: string | null;
}

export interface AdminIncidentTimelineResponse {
  lookup: AdminIncidentTimelineLookup;
  total: number;
  items: AdminIncidentTimelineItem[];
  hooks: AdminIncidentTimelineHook[];
  emptyState: AdminIncidentTimelineEmptyState;
  metadata: Record<string, unknown>;
}

export interface AdminLogStorageSummary {
  totalLogCount: number;
  eventCount?: number;
  sessionCount?: number;
  totalEventCount: number;
  oldestLogTimestamp?: string | null;
  oldestEventAt?: string | null;
  newestLogTimestamp?: string | null;
  newestEventAt?: string | null;
  retentionDays: number;
  minimumRetentionDays: number;
  retentionCutoff?: string | null;
  logsOlderThanRetentionCount: number;
  estimatedStorageBytes?: number | null;
  sizeBytes?: number | null;
  storageSizeBytes?: number | null;
  sizeLabel?: string | null;
  storageSizeLabel?: string | null;
  storageSizeAvailable: boolean;
  measurementScope?: 'postgres_tables' | 'sqlite_database_file' | 'unavailable' | string;
  measurementStatus?: 'available' | 'unavailable' | string;
  measurementReason?: string | null;
  softLimitBytes?: number | null;
  storageSoftLimitBytes: number;
  hardLimitBytes?: number | null;
  storageHardLimitBytes: number;
  usedPercentageOfSoftLimit?: number | null;
  usedPercentageOfHardLimit?: number | null;
  capacityCleanupRecommended: boolean;
  autoCleanupEnabled: boolean;
  autoCleanupPerformed: boolean;
  autoCleanupMessage?: string | null;
  capacityCleanupPlan?: Record<string, unknown>;
  postgresVacuumNote?: string | null;
  warningThresholdCount: number;
  criticalThresholdCount: number;
  warningThresholdStorageBytes?: number | null;
  status: 'ok' | 'warning' | 'critical' | string;
  statusReasons: string[];
  recommendedCleanupAction: string;
  lastCleanupTimestamp?: string | null;
}

export interface AdminLogCleanupResponse {
  mode: string;
  dryRun: boolean;
  cutoff?: string | null;
  matchedLogCount: number;
  matchedEventCount: number;
  deletedLogCount: number;
  deletedEventCount: number;
  statusFilter?: string | null;
  categoryFilter?: string | null;
  additionalCleanupNeeded: boolean;
  message?: string | null;
  postgresVacuumNote?: string | null;
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

function normalizeDataMissingDrilldownItem(payload: Record<string, unknown>): AdminDataMissingDrilldownItem {
  const normalized = toCamelCase<AdminDataMissingDrilldownItem>(payload);
  return {
    affectedSurface: normalized.affectedSurface || 'unknown',
    symbol: normalized.symbol || null,
    market: normalized.market || null,
    missingDomain: normalized.missingDomain || 'unknown',
    provider: normalized.provider || null,
    source: normalized.source || null,
    freshnessStatus: normalized.freshnessStatus || 'unknown',
    fallbackUsed: Boolean(normalized.fallbackUsed),
    stale: Boolean(normalized.stale),
    partial: Boolean(normalized.partial),
    reasonCode: normalized.reasonCode || 'unknown',
    latestSeenAt: normalized.latestSeenAt || null,
    count: Number(normalized.count || 0),
    sampleEventIds: Array.isArray(normalized.sampleEventIds) ? normalized.sampleEventIds : [],
    sampleSessionIds: Array.isArray(normalized.sampleSessionIds) ? normalized.sampleSessionIds : [],
    sampleBusinessEventIds: Array.isArray(normalized.sampleBusinessEventIds) ? normalized.sampleBusinessEventIds : [],
  };
}

function normalizeOperatorIssueRollupItem(payload: Record<string, unknown>): AdminOperatorIssueRollupItem {
  const normalized = toCamelCase<AdminOperatorIssueRollupItem>(payload);
  return {
    issueId: normalized.issueId || 'operator-issue',
    issueClass: normalized.issueClass || 'operator_issue',
    issueTitle: normalized.issueTitle || 'Operator issue',
    severity: normalized.severity || 'warning',
    count: Number(normalized.count || 0),
    latestTimestamp: normalized.latestTimestamp || null,
    firstTimestamp: normalized.firstTimestamp || null,
    sampleEventIds: Array.isArray(normalized.sampleEventIds) ? normalized.sampleEventIds : [],
    affectedSurfaces: Array.isArray(normalized.affectedSurfaces) ? normalized.affectedSurfaces : [],
    affectedDomains: Array.isArray(normalized.affectedDomains) ? normalized.affectedDomains : [],
    provider: normalized.provider || null,
    source: normalized.source || null,
    model: normalized.model || null,
    channel: normalized.channel || null,
    reasonCode: normalized.reasonCode || 'unknown',
    eventType: normalized.eventType || null,
    freshnessStatus: normalized.freshnessStatus || null,
    status: normalized.status || null,
    operatorGuidance: normalized.operatorGuidance || '',
  };
}

function normalizeIncidentTimelineResponse(payload: Record<string, unknown>): AdminIncidentTimelineResponse {
  const normalized = toCamelCase<AdminIncidentTimelineResponse>(payload);
  return {
    lookup: {
      sessionId: normalized.lookup?.sessionId || null,
      requestId: normalized.lookup?.requestId || null,
      queryId: normalized.lookup?.queryId || null,
      symbol: normalized.lookup?.symbol || null,
      dateFrom: normalized.lookup?.dateFrom || null,
      dateTo: normalized.lookup?.dateTo || null,
      limit: Number(normalized.lookup?.limit || 0),
    },
    total: Number(normalized.total || 0),
    items: Array.isArray(normalized.items)
      ? normalized.items.map((item) => {
        const entry = toCamelCase<AdminIncidentTimelineItem>(item as unknown as Record<string, unknown>);
        return {
          ...entry,
          navigation: entry.navigation && typeof entry.navigation === 'object'
            ? entry.navigation
            : {},
        };
      })
      : [],
    hooks: Array.isArray(normalized.hooks)
      ? normalized.hooks.map((hook) => {
        const entry = toCamelCase<AdminIncidentTimelineHook>(hook as unknown as Record<string, unknown>);
        return {
          ...entry,
          count: Number(entry.count || 0),
          sampleSessionIds: Array.isArray(entry.sampleSessionIds) ? entry.sampleSessionIds : [],
          sampleBusinessEventIds: Array.isArray(entry.sampleBusinessEventIds) ? entry.sampleBusinessEventIds : [],
        };
      })
      : [],
    emptyState: {
      reason: normalized.emptyState?.reason || null,
      readOnly: normalized.emptyState?.readOnly !== false,
      message: normalized.emptyState?.message || null,
    },
    metadata: normalized.metadata && typeof normalized.metadata === 'object'
      ? normalized.metadata
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
      minLevel?: string;
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
          min_level: params.minLevel,
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
      eventCount: Number(normalized.eventCount || normalized.totalEventCount || 0),
      sessionCount: Number(normalized.sessionCount || normalized.totalLogCount || 0),
      totalEventCount: Number(normalized.totalEventCount || 0),
      oldestLogTimestamp: normalized.oldestLogTimestamp || null,
      oldestEventAt: normalized.oldestEventAt || normalized.oldestLogTimestamp || null,
      newestLogTimestamp: normalized.newestLogTimestamp || null,
      newestEventAt: normalized.newestEventAt || normalized.newestLogTimestamp || null,
      retentionDays: Number(normalized.retentionDays || 90),
      minimumRetentionDays: Number(normalized.minimumRetentionDays || 7),
      retentionCutoff: normalized.retentionCutoff || null,
      logsOlderThanRetentionCount: Number(normalized.logsOlderThanRetentionCount || 0),
      estimatedStorageBytes: typeof normalized.estimatedStorageBytes === 'number' ? normalized.estimatedStorageBytes : null,
      sizeBytes: typeof normalized.sizeBytes === 'number' ? normalized.sizeBytes : (typeof normalized.storageSizeBytes === 'number' ? normalized.storageSizeBytes : null),
      storageSizeBytes: typeof normalized.storageSizeBytes === 'number' ? normalized.storageSizeBytes : (typeof normalized.sizeBytes === 'number' ? normalized.sizeBytes : null),
      sizeLabel: normalized.sizeLabel || normalized.storageSizeLabel || null,
      storageSizeLabel: normalized.storageSizeLabel || normalized.sizeLabel || null,
      storageSizeAvailable: Boolean(normalized.storageSizeAvailable || normalized.measurementStatus === 'available'),
      measurementScope: normalized.measurementScope || 'unavailable',
      measurementStatus: normalized.measurementStatus || (normalized.storageSizeAvailable ? 'available' : 'unavailable'),
      measurementReason: normalized.measurementReason || null,
      softLimitBytes: typeof normalized.softLimitBytes === 'number' ? normalized.softLimitBytes : null,
      storageSoftLimitBytes: Number(normalized.storageSoftLimitBytes || normalized.softLimitBytes || 512 * 1024 * 1024),
      hardLimitBytes: typeof normalized.hardLimitBytes === 'number' ? normalized.hardLimitBytes : null,
      storageHardLimitBytes: Number(normalized.storageHardLimitBytes || normalized.hardLimitBytes || 1024 * 1024 * 1024),
      usedPercentageOfSoftLimit: typeof normalized.usedPercentageOfSoftLimit === 'number' ? normalized.usedPercentageOfSoftLimit : null,
      usedPercentageOfHardLimit: typeof normalized.usedPercentageOfHardLimit === 'number' ? normalized.usedPercentageOfHardLimit : null,
      capacityCleanupRecommended: Boolean(normalized.capacityCleanupRecommended),
      autoCleanupEnabled: Boolean(normalized.autoCleanupEnabled),
      autoCleanupPerformed: Boolean(normalized.autoCleanupPerformed),
      autoCleanupMessage: normalized.autoCleanupMessage || null,
      capacityCleanupPlan: normalized.capacityCleanupPlan && typeof normalized.capacityCleanupPlan === 'object'
        ? normalized.capacityCleanupPlan as Record<string, unknown>
        : {},
      postgresVacuumNote: normalized.postgresVacuumNote || null,
      warningThresholdCount: Number(normalized.warningThresholdCount || 50000),
      criticalThresholdCount: Number(normalized.criticalThresholdCount || 100000),
      warningThresholdStorageBytes: typeof normalized.warningThresholdStorageBytes === 'number' ? normalized.warningThresholdStorageBytes : null,
      status: normalized.status || 'ok',
      statusReasons: Array.isArray(normalized.statusReasons) ? normalized.statusReasons : [],
      recommendedCleanupAction: normalized.recommendedCleanupAction || '',
      lastCleanupTimestamp: normalized.lastCleanupTimestamp || null,
    };
  },

  listDataMissingDrilldown: async (
    params: {
      since?: string;
      dateFrom?: string;
      dateTo?: string;
      limit?: number;
    } = {},
  ): Promise<AdminDataMissingDrilldownResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/admin/logs/data-missing-drilldown',
      {
        params: {
          since: params.since,
          date_from: params.dateFrom,
          date_to: params.dateTo,
          limit: params.limit,
        },
      },
    );
    const normalized = toCamelCase<AdminDataMissingDrilldownResponse>(response.data);
    return {
      total: Number(normalized.total || 0),
      items: Array.isArray(normalized.items)
        ? normalized.items.map((item) => normalizeDataMissingDrilldownItem(item as unknown as Record<string, unknown>))
        : [],
    };
  },

  listOperatorIssueRollup: async (
    params: {
      since?: string;
      dateFrom?: string;
      dateTo?: string;
      limit?: number;
    } = {},
  ): Promise<AdminOperatorIssueRollupResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/admin/logs/operator-issue-rollup',
      {
        params: {
          since: params.since,
          date_from: params.dateFrom,
          date_to: params.dateTo,
          limit: params.limit,
        },
      },
    );
    const normalized = toCamelCase<AdminOperatorIssueRollupResponse>(response.data);
    return {
      total: Number(normalized.total || 0),
      items: Array.isArray(normalized.items)
        ? normalized.items.map((item) => normalizeOperatorIssueRollupItem(item as unknown as Record<string, unknown>))
        : [],
    };
  },

  getIncidentTimeline: async (
    params: {
      sessionId?: string;
      requestId?: string;
      queryId?: string;
      symbol?: string;
      since?: string;
      dateFrom?: string;
      dateTo?: string;
      limit?: number;
    } = {},
  ): Promise<AdminIncidentTimelineResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/admin/logs/incident-timeline',
      {
        params: {
          session_id: params.sessionId,
          request_id: params.requestId,
          query_id: params.queryId,
          symbol: params.symbol,
          since: params.since,
          date_from: params.dateFrom,
          date_to: params.dateTo,
          limit: params.limit,
        },
      },
    );
    return normalizeIncidentTimelineResponse(response.data);
  },

  cleanupLogs: async (
    params: {
      mode?: 'retention' | 'before_date' | 'capacity' | string;
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
      mode: normalized.mode || params.mode || 'retention',
      dryRun: Boolean(normalized.dryRun),
      cutoff: normalized.cutoff || null,
      matchedLogCount: Number(normalized.matchedLogCount || 0),
      matchedEventCount: Number(normalized.matchedEventCount || 0),
      deletedLogCount: Number(normalized.deletedLogCount || 0),
      deletedEventCount: Number(normalized.deletedEventCount || 0),
      statusFilter: normalized.statusFilter || null,
      categoryFilter: normalized.categoryFilter || null,
      additionalCleanupNeeded: Boolean(normalized.additionalCleanupNeeded),
      message: normalized.message || null,
      postgresVacuumNote: normalized.postgresVacuumNote || null,
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
