import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminCostObservabilityPage from '../AdminCostObservabilityPage';

const { getDuplicateSummary } = vi.hoisted(() => ({
  getDuplicateSummary: vi.fn(),
}));

vi.mock('../../api/adminCost', () => ({
  adminCostApi: {
    getDuplicateSummary,
  },
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: 'zh',
    t: (key: string) => key,
  }),
}));

const populatedPayload = {
  generatedAt: '2026-05-06T10:30:00+08:00',
  window: {
    key: '24h',
    from: '2026-05-05T10:30:00+08:00',
    to: '2026-05-06T10:30:00+08:00',
    bucket: 'hour',
    historical: false,
  },
  summary: {
    llmCalls: 12,
    llmUsageCalls: 8,
    llmUsageTokens: 42000,
    estimatedDuplicateCandidates: 3,
    providerCalls: 18,
    providerCacheHits: 9,
    providerCacheMisses: 6,
    providerInflightJoins: 2,
    providerCacheHitRate: 0.6,
    marketCacheHits: 15,
    marketCacheMisses: 4,
    marketCacheStaleServed: 2,
    marketCacheColdFallbacks: 1,
    marketCacheHitRate: 0.7895,
    fallbackAttempts: 5,
    integrityRetries: 1,
    scannerAiAttempts: 4,
    scannerAiCompleted: 3,
    scannerAiSkipped: 2,
  },
  llm: {
    byCallType: [
      {
        group: 'analysis',
        count: 9,
        eventCounts: { llm_call_started: 9, llm_call_completed: 8 },
        dimensions: { call_type: 'analysis', model_family: 'safe-family' },
      },
    ],
    duplicateCandidates: [
      {
        group: 'candidate-hash-a',
        count: 3,
        eventCounts: { llm_duplicate_candidate_observed: 3 },
        dimensions: { scope: 'symbol_report_language_freshness', freshness_bucket: 'fresh' },
      },
    ],
    fallbacks: [
      {
        group: 'fallback-depth-1',
        count: 2,
        eventCounts: { llm_fallback_attempt: 2 },
        dimensions: { fallback_depth: '1', retry_reason: 'timeout' },
      },
    ],
    integrityRetries: [
      {
        group: 'required_fields',
        count: 1,
        eventCounts: { llm_integrity_retry: 1 },
        dimensions: { retry_reason: 'missing_required_fields' },
      },
    ],
    usageByCallType: [],
    usageByModel: [],
  },
  providers: {
    byCategory: [
      {
        group: 'fundamentals',
        count: 10,
        eventCounts: { provider_call_started: 10 },
        dimensions: { provider_category: 'fundamentals', market: 'us' },
      },
    ],
    fallbackDepth: [],
    cacheEfficiency: [
      {
        group: 'safe-provider|fundamentals|us',
        hits: 9,
        misses: 6,
        inflightJoins: 2,
        hitRate: 0.6,
        dimensions: { provider: 'safe-provider', provider_category: 'fundamentals', market: 'us' },
      },
    ],
    duplicateCandidates: [],
  },
  marketCache: {
    byPanelKey: [
      {
        group: 'macro',
        count: 12,
        eventCounts: { market_cache_hit: 9, market_cache_miss: 3 },
        dimensions: { panel_key: 'macro', endpoint_family: 'market_overview' },
      },
    ],
    staleServed: [],
    coldFallbacks: [],
    refreshes: [],
  },
  scannerAi: {
    interpretations: [
      {
        group: 'cn|us_preopen_v1',
        count: 4,
        eventCounts: { scanner_ai_interpretation_started: 4, scanner_ai_interpretation_completed: 3 },
        dimensions: { market: 'cn', profile: 'us_preopen_v1', top_n: '5' },
      },
    ],
    duplicateCandidates: [],
    skips: [
      {
        group: 'disabled',
        count: 2,
        eventCounts: { scanner_ai_interpretation_skipped: 2 },
        dimensions: { skip_reason: 'disabled' },
      },
    ],
  },
  limitations: [
    {
      code: 'observational_not_billing',
      message: 'Counts indicate observed attempts and duplicate candidates, not invoice-grade billing.',
      severity: 'info',
    },
    {
      code: 'counter_snapshot_not_timestamped',
      message: 'Window parameters are contract-only for process-local counters.',
      severity: 'warning',
    },
  ],
  metadata: {
    readOnly: true,
    noExternalCalls: true,
    countersSource: 'process_local',
    exactness: 'observational_not_billing',
    dataSources: ['process_local_counters', 'llm_usage'],
    unsupportedSources: ['future_duplicate_cost_counters'],
    redaction: ['raw_prompt_omitted', 'raw_provider_payload_omitted', 'safe_hashes_only'],
    requestedArea: 'all',
    limit: 50,
    notes: {
      rawPrompt: 'SHOULD_NOT_RENDER',
      apiKey: 'sk-should-not-render',
      providerPayload: 'SHOULD_NOT_RENDER_PAYLOAD',
      rawUrl: 'https://provider.example/path?token=secret',
    },
  },
};

describe('AdminCostObservabilityPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders mocked duplicate-cost summary with read-only, no-external-call, and observational badges', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);

    render(<AdminCostObservabilityPage />);

    expect(await screen.findByRole('heading', { name: '成本观测' })).toBeInTheDocument();
    expect(screen.getByText('只读')).toBeInTheDocument();
    expect(screen.getByText('外部调用关闭')).toBeInTheDocument();
    expect(screen.getAllByText('观测值非账单').length).toBeGreaterThan(0);
    expect(screen.getByText('LLM 调用')).toBeInTheDocument();
    expect(screen.getByText('Provider / 数据源 fallback')).toBeInTheDocument();
    expect(screen.getByText('MarketCache 命中 / 过期 / 缺失')).toBeInTheDocument();
    expect(screen.getByText('Scanner AI 解释')).toBeInTheDocument();
    expect(screen.getByText('Guest Preview / Report duplicate candidates')).toBeInTheDocument();
    expect(screen.getByText('限制与数据质量')).toBeInTheDocument();
    expect(screen.getByText('counter_snapshot_not_timestamped')).toBeInTheDocument();
  });

  it('keeps developer details collapsed and does not render secret-like strings in the DOM', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);

    render(<AdminCostObservabilityPage />);

    expect(await screen.findByText('开发者 / 响应形状')).toBeInTheDocument();
    expect(screen.queryByText('SHOULD_NOT_RENDER')).not.toBeInTheDocument();
    expect(screen.queryByText('SHOULD_NOT_RENDER_PAYLOAD')).not.toBeInTheDocument();
    expect(screen.queryByText('sk-should-not-render')).not.toBeInTheDocument();
    expect(screen.queryByText('https://provider.example/path?token=secret')).not.toBeInTheDocument();
  });

  it('renders loading state without implying billing exactness', () => {
    getDuplicateSummary.mockReturnValue(new Promise(() => {}));

    render(<AdminCostObservabilityPage />);
    expect(screen.getByText('正在读取成本观测快照')).toBeInTheDocument();
    expect(screen.getByText('精确性待确认')).toBeInTheDocument();
  });

  it('renders empty and partial-counter states without implying billing exactness', async () => {
    getDuplicateSummary.mockResolvedValue({
      ...populatedPayload,
      summary: {
        ...populatedPayload.summary,
        llmCalls: 0,
        estimatedDuplicateCandidates: 0,
        providerCalls: 0,
        providerCacheHits: 0,
        providerCacheMisses: 0,
        providerInflightJoins: 0,
        providerCacheHitRate: null,
        marketCacheHits: 0,
        marketCacheMisses: 0,
        marketCacheStaleServed: 0,
        marketCacheColdFallbacks: 0,
        marketCacheHitRate: null,
        fallbackAttempts: 0,
        integrityRetries: 0,
        llmUsageCalls: 0,
        llmUsageTokens: 0,
        scannerAiAttempts: 0,
        scannerAiCompleted: 0,
        scannerAiSkipped: 0,
      },
      llm: { ...populatedPayload.llm, byCallType: [], duplicateCandidates: [], fallbacks: [], integrityRetries: [] },
      providers: { ...populatedPayload.providers, byCategory: [], fallbackDepth: [], cacheEfficiency: [], duplicateCandidates: [] },
      marketCache: { ...populatedPayload.marketCache, byPanelKey: [], staleServed: [], coldFallbacks: [], refreshes: [] },
      scannerAi: { ...populatedPayload.scannerAi, interpretations: [], duplicateCandidates: [], skips: [] },
      limitations: [
        ...populatedPayload.limitations,
        { code: 'llm_usage_unavailable', message: 'Persisted LLM usage summary was unavailable.', severity: 'warning' },
      ],
    });

    render(<AdminCostObservabilityPage />);

    expect(await screen.findByText('计数器尚未接入或当前窗口暂无事件')).toBeInTheDocument();
    expect(screen.getByText('llm_usage_unavailable')).toBeInTheDocument();
  });

  it('renders sanitized API errors', async () => {
    getDuplicateSummary.mockRejectedValue(new Error('stack trace token=secret raw_prompt=bad'));

    render(<AdminCostObservabilityPage />);

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(within(screen.getByRole('alert')).getByText('读取成本观测失败')).toBeInTheDocument();
    expect(screen.queryByText('raw_prompt=bad')).not.toBeInTheDocument();
  });

  it('calls the API with safe filter query params only', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);

    render(<AdminCostObservabilityPage />);
    await screen.findByRole('heading', { name: '成本观测' });

    fireEvent.change(screen.getByLabelText('窗口'), { target: { value: '7d' } });
    fireEvent.change(screen.getByLabelText('粒度'), { target: { value: 'day' } });
    fireEvent.change(screen.getByLabelText('区域'), { target: { value: 'scanner-ai' } });
    fireEvent.change(screen.getByLabelText('数量上限'), { target: { value: '25' } });

    await waitFor(() => {
      expect(getDuplicateSummary).toHaveBeenLastCalledWith({
        window: '7d',
        bucket: 'day',
        area: 'scanner-ai',
        limit: 25,
      });
    });
    const lastCall = getDuplicateSummary.mock.calls.at(-1)?.[0] || {};
    expect(Object.keys(lastCall).sort()).toEqual(['area', 'bucket', 'limit', 'window']);
  });
});
