import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminCostObservabilityPage from '../AdminCostObservabilityPage';

const { getDuplicateSummary } = vi.hoisted(() => ({
  getDuplicateSummary: vi.fn(),
}));

const { getLlmLedgerSummary, getModelPricingPolicies, runQuotaDryRun, capabilityState } = vi.hoisted(() => ({
  getLlmLedgerSummary: vi.fn(),
  getModelPricingPolicies: vi.fn(),
  runQuotaDryRun: vi.fn(),
  capabilityState: { canReadCostObservability: true },
}));

vi.mock('../../api/adminCost', () => ({
  adminCostApi: {
    getDuplicateSummary,
    getLlmLedgerSummary,
    getModelPricingPolicies,
    runQuotaDryRun,
  },
}));

vi.mock('../../hooks/useProductSurface', () => ({
  useProductSurface: () => capabilityState,
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
      redactionSentinel: 'KEY_SHOULD_NOT_RENDER',
      providerPayload: 'SHOULD_NOT_RENDER_PAYLOAD',
      rawUrl: 'https://provider.example/path?token=secret',
    },
  },
};

const quotaAllowedPayload = {
  allowed: true,
  wouldBlock: false,
  status: 'allowed',
  reasonCode: null,
  routeFamily: 'analysis',
  estimatedUnits: 4,
  enforcementMode: 'dry_run',
  operation: 'estimate',
  reservationId: null,
  metadata: {
    diagnosticOnly: true,
    liveEnforcement: false,
    noExternalCalls: true,
    dataSources: ['quota_policy_definitions'],
    redaction: ['credentials', 'stack_details'],
    rawPrompt: 'SHOULD_NOT_RENDER_QUOTA',
    redactionSentinel: 'QUOTA_KEY_SHOULD_NOT_RENDER',
  },
};

const ledgerPayload = {
  generatedAt: '2026-05-06T10:35:00+08:00',
  window: {
    key: '24h',
    from: '2026-05-05T10:35:00+08:00',
    to: '2026-05-06T10:35:00+08:00',
    bucket: 'day',
    historical: true,
  },
  total: {
    calls: 5,
    promptTokens: 8000,
    cachedInputTokens: 1200,
    completionTokens: 3000,
    totalTokens: 11000,
    totalCostUsd: '0.123456',
  },
  byUser: [
    {
      group: 'user-a',
      calls: 3,
      totalTokens: 7000,
      totalCostUsd: '0.090000',
      dimensions: { owner_user_id: 'user-a' },
    },
    {
      group: 'user-b',
      calls: 2,
      totalTokens: 4000,
      totalCostUsd: '0.033456',
      dimensions: { owner_user_id: 'user-b' },
    },
  ],
  byProviderModel: [
    {
      group: 'openai|gpt-4o-mini',
      calls: 4,
      totalTokens: 9000,
      totalCostUsd: '0.100000',
      dimensions: { provider: 'openai', model: 'gpt-4o-mini' },
    },
  ],
  byRouteFamily: [
    {
      group: 'analysis',
      calls: 5,
      totalTokens: 11000,
      totalCostUsd: '0.123456',
      dimensions: { route_family: 'analysis' },
    },
  ],
  metadata: {
    readOnly: true,
    noExternalCalls: true,
    liveEnforcement: false,
    dataSources: ['llm_cost_ledger', 'model_pricing_policies'],
    redaction: ['prompts_omitted', 'provider_payloads_omitted', 'credentials_omitted'],
    resultStatusCounts: {
      pricing_unknown: 1,
      pricing_inactive: 2,
    },
    rawPrompt: 'LEDGER_PROMPT_SHOULD_NOT_RENDER',
    providerPayload: 'LEDGER_PAYLOAD_SHOULD_NOT_RENDER',
    redactionSentinel: 'LEDGER_KEY_SHOULD_NOT_RENDER',
    stackTrace: 'LEDGER_STACK_SHOULD_NOT_RENDER',
  },
};

const pricingPoliciesPayload = {
  generatedAt: '2026-05-06T10:40:00+08:00',
  activeCount: 1,
  policies: [
    {
      provider: 'openai',
      model: 'openai/gpt-4o-mini',
      inputPricePer1m: '0.10000000',
      cachedInputPricePer1m: '0.05000000',
      outputPricePer1m: '0.40000000',
      currency: 'USD',
      effectiveFrom: '2026-01-01T00:00:00',
      effectiveUntil: null,
      active: true,
      sourceLabel: 'OpenAI pricing page',
      sourceUrl: 'https://openai.com/api/pricing/',
      updatedAt: '2026-05-06T10:00:00',
      metadata: { redactionSentinel: 'SHOULD_NOT_RENDER_POLICY_KEY' },
    },
    {
      provider: 'deepseek',
      model: 'deepseek/deepseek-chat',
      inputPricePer1m: '0.05000000',
      cachedInputPricePer1m: null,
      outputPricePer1m: '0.20000000',
      currency: 'USD',
      effectiveFrom: '2025-01-01T00:00:00',
      effectiveUntil: '2026-01-01T00:00:00',
      active: false,
      sourceLabel: 'DeepSeek pricing page',
      sourceUrl: 'https://api-docs.deepseek.com/quick_start/pricing?token=SHOULD_NOT_RENDER',
      updatedAt: '2026-05-05T10:00:00',
      rawMetadata: 'SHOULD_NOT_RENDER_RAW_POLICY_METADATA',
    },
  ],
  metadata: {
    readOnly: true,
    noExternalCalls: true,
    liveEnforcement: false,
    manualMaintenance: true,
    dataSources: ['model_pricing_policies'],
    redaction: ['metadata_omitted'],
    stackTrace: 'SHOULD_NOT_RENDER_POLICY_STACK',
  },
};

async function openCostSecondaryDisclosure() {
  const toggle = await screen.findByRole('button', { name: '展开 二级细节：窗口筛选、账本、价格、Provider / 缓存' });
  fireEvent.click(toggle);
}

describe('AdminCostObservabilityPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capabilityState.canReadCostObservability = true;
    runQuotaDryRun.mockResolvedValue(quotaAllowedPayload);
    getLlmLedgerSummary.mockResolvedValue(ledgerPayload);
    getModelPricingPolicies.mockResolvedValue(pricingPoliciesPayload);
  });

  it('renders mocked duplicate-cost summary with read-only, no-external-call, and observational badges', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);

    render(<AdminCostObservabilityPage />);

    expect(await screen.findByRole('heading', { name: '成本观测' })).toBeInTheDocument();
    expect(screen.getByText('页面用途')).toBeInTheDocument();
    expect(screen.getByText('当前状态')).toBeInTheDocument();
    expect(screen.getByText('下一步')).toBeInTheDocument();
    expect(screen.getByText('评估成本与配额风险')).toBeInTheDocument();
    expect(await screen.findByText('12 次 AI / 18 次数据源')).toBeInTheDocument();
    expect(screen.getByText('先做配额试运行，再定位归属')).toBeInTheDocument();
    expect(screen.getByText('成本压力')).toBeInTheDocument();
    expect(screen.getByText('缓存效率')).toBeInTheDocument();
    expect(screen.getByText('只读')).toBeInTheDocument();
    expect(screen.getByText('外部调用关闭')).toBeInTheDocument();
    expect(screen.getAllByText('观测值非账单').length).toBeGreaterThan(0);
    await openCostSecondaryDisclosure();
    expect(screen.getAllByText('LLM 调用').length).toBeGreaterThan(0);
    expect(screen.getByText('数据源状态 / 备用链路')).toBeInTheDocument();
    expect(screen.getByText('市场缓存命中 / 过期 / 缺失')).toBeInTheDocument();
    expect(screen.getByText('Scanner AI 解释')).toBeInTheDocument();
    expect(screen.getByText('Guest Preview / Report duplicate candidates')).toBeInTheDocument();
    expect(screen.getByText('限制与数据质量')).toBeInTheDocument();
    expect(screen.getByText('计数器快照不含历史时间戳')).toBeInTheDocument();
    expect(screen.getByText('配额试运行诊断')).toBeInTheDocument();
    expect(screen.getAllByText('AI 调用账本').length).toBeGreaterThan(0);
    expect(screen.getByText('模型价格策略')).toBeInTheDocument();
  });

  it('uses terminal operator primitives for the cost observability surface', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);

    render(<AdminCostObservabilityPage />);

    const page = screen.getByTestId('admin-cost-observability-page');
    expect(await screen.findByRole('heading', { name: '成本观测' })).toBeInTheDocument();
    await openCostSecondaryDisclosure();
    expect(page.querySelector('[data-terminal-primitive="page-shell"]')).not.toBeNull();
    expect(page.querySelectorAll('[data-terminal-primitive="panel"]').length).toBeGreaterThan(4);
    expect(page.querySelectorAll('[data-terminal-primitive="chip"]').length).toBeGreaterThan(4);
    expect(page.querySelectorAll('[data-terminal-primitive="notice"]').length).toBeGreaterThan(1);
    expect(page.querySelectorAll('[data-terminal-primitive="disclosure"]').length).toBeGreaterThanOrEqual(3);
    expect(page.querySelectorAll('[data-terminal-primitive="nested-block"]').length).toBeGreaterThan(8);
  });

  it('does not lock the page root to a pure-black local background slab', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);

    render(<AdminCostObservabilityPage />);

    const page = screen.getByTestId('admin-cost-observability-page');
    expect(await screen.findByRole('heading', { name: '成本观测' })).toBeInTheDocument();
    expect(page.className).not.toContain('bg-[#050505]');
    expect(page.className).not.toContain('bg-black');
  });

  it('keeps developer details collapsed and does not render secret-like strings in the DOM', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);

    render(<AdminCostObservabilityPage />);

    await openCostSecondaryDisclosure();
    expect(await screen.findByText('开发者 / 响应形状')).toBeInTheDocument();
    expect(screen.queryByText('SHOULD_NOT_RENDER')).not.toBeInTheDocument();
    expect(screen.queryByText('SHOULD_NOT_RENDER_PAYLOAD')).not.toBeInTheDocument();
    expect(screen.queryByText('KEY_SHOULD_NOT_RENDER')).not.toBeInTheDocument();
    expect(screen.queryByText('https://provider.example/path?token=secret')).not.toBeInTheDocument();
    expect(screen.queryByText('SHOULD_NOT_RENDER_QUOTA')).not.toBeInTheDocument();
    expect(screen.queryByText('QUOTA_KEY_SHOULD_NOT_RENDER')).not.toBeInTheDocument();
    expect(screen.queryByText('LEDGER_PROMPT_SHOULD_NOT_RENDER')).not.toBeInTheDocument();
    expect(screen.queryByText('LEDGER_PAYLOAD_SHOULD_NOT_RENDER')).not.toBeInTheDocument();
    expect(screen.queryByText('LEDGER_KEY_SHOULD_NOT_RENDER')).not.toBeInTheDocument();
    expect(screen.queryByText('LEDGER_STACK_SHOULD_NOT_RENDER')).not.toBeInTheDocument();
    expect(screen.queryByText('SHOULD_NOT_RENDER_POLICY_KEY')).not.toBeInTheDocument();
    expect(screen.queryByText('SHOULD_NOT_RENDER_RAW_POLICY_METADATA')).not.toBeInTheDocument();
    expect(screen.queryByText('SHOULD_NOT_RENDER_POLICY_STACK')).not.toBeInTheDocument();
    expect(screen.queryByText('SHOULD_NOT_RENDER')).not.toBeInTheDocument();
  });

  it('renders loading state without implying billing exactness', () => {
    getDuplicateSummary.mockReturnValue(new Promise(() => {}));

    render(<AdminCostObservabilityPage />);
    expect(screen.getByText('正在读取成本观测快照')).toBeInTheDocument();
    expect(screen.getAllByText('精确性待确认').length).toBeGreaterThan(0);
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

    expect((await screen.findAllByText('计数器尚未接入或当前窗口暂无事件')).length).toBeGreaterThan(0);
    await openCostSecondaryDisclosure();
    expect(screen.getByText('LLM 用量账务摘要不可用')).toBeInTheDocument();
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

    await openCostSecondaryDisclosure();

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

  it('runs quota dry-run estimate for users with cost observability capability', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);
    runQuotaDryRun.mockResolvedValue({
      ...quotaAllowedPayload,
      estimatedUnits: 17,
      reasonCode: 'within_budget',
    });

    render(<AdminCostObservabilityPage />);

    await openCostSecondaryDisclosure();
    expect(await screen.findByText('配额试运行诊断')).toBeInTheDocument();
    await waitFor(() => expect(runQuotaDryRun).toHaveBeenCalled());
    expect(screen.getByText('17')).toBeInTheDocument();
    expect(screen.getByText('预算内')).toBeInTheDocument();
    expect(runQuotaDryRun.mock.calls[0][0]).toMatchObject({
      routeFamily: 'analysis',
      tokenEstimate: 4000,
      operation: 'estimate',
      enforcementMode: 'dry_run',
    });
  });

  it('renders LLM ledger totals and cost summaries for users with cost observability capability', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);

    render(<AdminCostObservabilityPage />);

    await openCostSecondaryDisclosure();
    expect(await screen.findByTestId('llm-ledger-panel')).toBeInTheDocument();
    await waitFor(() => expect(getLlmLedgerSummary).toHaveBeenCalledWith({ window: '24h', bucket: 'hour', limit: 50 }));
    expect(screen.getByText('总用量')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('llm-ledger-panel')).toHaveTextContent('11,000'));
    expect(screen.getAllByText('$0.12').length).toBeGreaterThan(0);
    expect(screen.getByText('用户成本排行')).toBeInTheDocument();
    expect(screen.getByText('user-a')).toBeInTheDocument();
    expect(screen.getByText('user-b')).toBeInTheDocument();
    expect(screen.getByText('模型成本分布')).toBeInTheDocument();
    expect(screen.getByText('openai / gpt-4o-mini')).toBeInTheDocument();
    expect(screen.getByText('功能成本分布')).toBeInTheDocument();
    expect(screen.getAllByText('analysis').length).toBeGreaterThan(0);
    expect(screen.getByText('价格未知 1')).toBeInTheDocument();
    expect(screen.getByText('价格未激活 2')).toBeInTheDocument();
  });

  it('renders compact empty LLM ledger state', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);
    getLlmLedgerSummary.mockResolvedValue({
      ...ledgerPayload,
      total: {
        ...ledgerPayload.total,
        calls: 0,
        promptTokens: 0,
        cachedInputTokens: 0,
        completionTokens: 0,
        totalTokens: 0,
        totalCostUsd: '0',
      },
      byUser: [],
      byProviderModel: [],
      byRouteFamily: [],
      metadata: {
        ...ledgerPayload.metadata,
        resultStatusCounts: {},
      },
    });

    render(<AdminCostObservabilityPage />);

    await openCostSecondaryDisclosure();
    expect(await screen.findByText('当前窗口暂无 AI 调用账本记录')).toBeInTheDocument();
    expect(screen.getByText('暂无用户成本记录')).toBeInTheDocument();
    expect(screen.getByText('暂无模型成本记录')).toBeInTheDocument();
    expect(screen.getByText('暂无功能成本记录')).toBeInTheDocument();
  });

  it('renders model pricing policies for users with cost observability capability', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);

    render(<AdminCostObservabilityPage />);

    await openCostSecondaryDisclosure();
    const panel = await screen.findByTestId('model-pricing-policy-panel');
    expect(getModelPricingPolicies).toHaveBeenCalledTimes(1);
    expect(within(panel).getByText('模型价格策略')).toBeInTheDocument();
    expect(within(panel).getByText('价格由本地策略维护，需定期按供应商官网更新；估算值不等同于供应商账单。')).toBeInTheDocument();
    expect(await within(panel).findByText('激活 1')).toBeInTheDocument();
    expect(within(panel).getByText('openai / openai/gpt-4o-mini')).toBeInTheDocument();
    expect(within(panel).getByText('deepseek / deepseek/deepseek-chat')).toBeInTheDocument();
    expect(within(panel).getByText('USD 0.1000')).toBeInTheDocument();
    expect(within(panel).getAllByText('USD 0.0500').length).toBeGreaterThan(0);
    expect(within(panel).getByText('USD 0.4000')).toBeInTheDocument();
    expect(within(panel).getByRole('link', { name: 'OpenAI pricing page' })).toHaveAttribute('href', 'https://openai.com/api/pricing/');
    expect(within(panel).getByText('active')).toBeInTheDocument();
    expect(within(panel).getByText('inactive')).toBeInTheDocument();
  });

  it('renders compact empty model pricing policy state', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);
    getModelPricingPolicies.mockResolvedValue({
      ...pricingPoliciesPayload,
      activeCount: 0,
      policies: [],
    });

    render(<AdminCostObservabilityPage />);

    await openCostSecondaryDisclosure();
    expect(await screen.findByText('暂无模型价格策略')).toBeInTheDocument();
  });

  it('does not fetch or render LLM ledger without cost observability capability', async () => {
    capabilityState.canReadCostObservability = false;
    getDuplicateSummary.mockResolvedValue(populatedPayload);

    render(<AdminCostObservabilityPage />);

    expect(await screen.findByRole('heading', { name: '成本观测' })).toBeInTheDocument();
    expect(screen.queryByTestId('llm-ledger-panel')).not.toBeInTheDocument();
    expect(getLlmLedgerSummary).not.toHaveBeenCalled();
  });

  it('does not fetch or render pricing policies without cost observability capability', async () => {
    capabilityState.canReadCostObservability = false;
    getDuplicateSummary.mockResolvedValue(populatedPayload);

    render(<AdminCostObservabilityPage />);

    expect(await screen.findByRole('heading', { name: '成本观测' })).toBeInTheDocument();
    expect(screen.queryByTestId('model-pricing-policy-panel')).not.toBeInTheDocument();
    expect(getModelPricingPolicies).not.toHaveBeenCalled();
  });

  it('hides quota panel and does not fetch quota dry-run without cost observability capability', async () => {
    capabilityState.canReadCostObservability = false;
    getDuplicateSummary.mockResolvedValue(populatedPayload);

    render(<AdminCostObservabilityPage />);

    expect(await screen.findByRole('heading', { name: '成本观测' })).toBeInTheDocument();
    expect(screen.queryByTestId('quota-dry-run-panel')).not.toBeInTheDocument();
    expect(runQuotaDryRun).not.toHaveBeenCalled();
  });

  it('renders dry-run would-block as a compact warning without implying live blocking', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);
    runQuotaDryRun.mockResolvedValue({
      ...quotaAllowedPayload,
      allowed: false,
      wouldBlock: true,
      status: 'blocked',
      reasonCode: 'budget_exceeded',
      estimatedUnits: 3000,
    });

    render(<AdminCostObservabilityPage />);

    expect(await screen.findByText('预算超限')).toBeInTheDocument();
    expect(screen.getAllByText('会阻断').length).toBeGreaterThan(0);
    expect(screen.getByRole('status')).toHaveTextContent('真实请求未被阻断');
    expect(screen.queryByText('已阻止真实调用')).not.toBeInTheDocument();
  });

  it('renders sanitized quota 403 and 500 errors', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);
    runQuotaDryRun.mockRejectedValueOnce({ response: { status: 403, data: { detail: { message: 'token=secret raw stack' } } } });

    render(<AdminCostObservabilityPage />);

    expect(await screen.findByText('读取配额诊断失败')).toBeInTheDocument();
    expect(screen.getByText('当前账号没有成本观测权限。')).toBeInTheDocument();
    expect(screen.queryByText(/token=secret/)).not.toBeInTheDocument();

    runQuotaDryRun.mockRejectedValueOnce({ response: { status: 500, data: { detail: { message: 'stack trace apiKey=secret' } } } });
    fireEvent.click(screen.getByRole('button', { name: '运行试运行' }));

    await waitFor(() => expect(screen.getAllByText('读取配额诊断失败').length).toBeGreaterThan(0));
    expect(screen.getByText('服务器暂时不可用，请稍后重试。')).toBeInTheDocument();
    expect(screen.queryByText('apiKey=secret')).not.toBeInTheDocument();
  });

  it('renders sanitized LLM ledger 403 and 500 errors without breaking the cost page', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);
    getLlmLedgerSummary.mockRejectedValueOnce({ response: { status: 403, data: { detail: { message: 'token=secret raw prompt' } } } });

    render(<AdminCostObservabilityPage />);

    await openCostSecondaryDisclosure();
    expect(await screen.findByText('读取 AI 调用账本失败')).toBeInTheDocument();
    expect(screen.getByText('当前账号没有成本观测权限。')).toBeInTheDocument();
    expect(screen.getByText('配额试运行诊断')).toBeInTheDocument();
    expect(screen.queryByText(/token=secret/)).not.toBeInTheDocument();

    getLlmLedgerSummary.mockRejectedValueOnce({ response: { status: 500, data: { detail: { message: 'stack trace apiKey=secret' } } } });
    fireEvent.change(screen.getByLabelText('窗口'), { target: { value: '7d' } });

    await waitFor(() => expect(screen.getAllByText('读取 AI 调用账本失败').length).toBeGreaterThan(0));
    expect(screen.getByText('服务器暂时不可用，请稍后重试。')).toBeInTheDocument();
    expect(screen.queryByText('apiKey=secret')).not.toBeInTheDocument();
  });

  it('renders sanitized pricing policy 403 and 500 errors without leaking backend details', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);
    getModelPricingPolicies.mockRejectedValueOnce({ response: { status: 403, data: { detail: { message: 'token=secret raw metadata' } } } });

    render(<AdminCostObservabilityPage />);

    await openCostSecondaryDisclosure();
    expect(await screen.findByText('读取模型价格策略失败')).toBeInTheDocument();
    expect(screen.getByText('当前账号没有成本观测权限。')).toBeInTheDocument();
    expect(screen.queryByText(/token=secret/)).not.toBeInTheDocument();

    cleanup();
    getDuplicateSummary.mockResolvedValue(populatedPayload);
    getModelPricingPolicies.mockRejectedValueOnce({ response: { status: 500, data: { detail: { message: 'stack trace apiKey=secret' } } } });

    render(<AdminCostObservabilityPage />);

    await openCostSecondaryDisclosure();
    await waitFor(() => expect(screen.getAllByText('读取模型价格策略失败').length).toBeGreaterThan(0));
    expect(screen.getByText('服务器暂时不可用，请稍后重试。')).toBeInTheDocument();
    expect(screen.queryByText('apiKey=secret')).not.toBeInTheDocument();
  });

  it('keeps quota developer details collapsed by default', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);

    render(<AdminCostObservabilityPage />);

    await openCostSecondaryDisclosure();
    expect(await screen.findByText('开发者 / Quota 响应形状')).toBeInTheDocument();
    expect(screen.queryByText('diagnosticOnly')).not.toBeInTheDocument();
  });

  it('keeps LLM ledger developer details collapsed by default', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);

    render(<AdminCostObservabilityPage />);

    await openCostSecondaryDisclosure();
    const panel = await screen.findByTestId('llm-ledger-panel');
    await waitFor(() => expect(within(panel).getByText('开发者 / LLM 账本响应形状')).toBeInTheDocument());
    expect(within(panel).queryByText('liveEnforcement')).not.toBeInTheDocument();
  });

  it('keeps pricing policy developer details collapsed by default', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);

    render(<AdminCostObservabilityPage />);

    await openCostSecondaryDisclosure();
    const panel = await screen.findByTestId('model-pricing-policy-panel');
    await waitFor(() => expect(within(panel).getByText('开发者 / 价格策略响应形状')).toBeInTheDocument());
    expect(within(panel).queryByText('manualMaintenance')).not.toBeInTheDocument();
  });

  it('keeps the cost page within the viewport width in jsdom layout checks', async () => {
    getDuplicateSummary.mockResolvedValue(populatedPayload);
    Object.defineProperty(document.documentElement, 'clientWidth', { configurable: true, value: 390 });
    Object.defineProperty(document.documentElement, 'scrollWidth', { configurable: true, value: 390 });

    render(<AdminCostObservabilityPage />);

    await openCostSecondaryDisclosure();
    expect(await screen.findByTestId('llm-ledger-panel')).toBeInTheDocument();
    expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(document.documentElement.clientWidth);
  });
});
