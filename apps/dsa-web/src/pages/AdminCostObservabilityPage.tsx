import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, BarChart3, Coins, DatabaseZap, Gauge, Radar, ShieldCheck, Tags } from 'lucide-react';
import {
  adminCostApi,
  type AdminCostArea,
  type AdminCostBucket,
  type AdminCostCacheEfficiency,
  type AdminCostRollup,
  type AdminCostSummaryParams,
  type AdminCostSummaryResponse,
  type AdminCostWindowKey,
  type LlmLedgerSummaryResponse,
  type LlmLedgerSummaryRollup,
  type ModelPricingPoliciesResponse,
  type ModelPricingPolicyItem,
  type QuotaDryRunOperation,
  type QuotaDryRunResponse,
  type QuotaEnforcementMode,
} from '../api/adminCost';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ApiErrorAlert, Select } from '../components/common';
import {
  TerminalButton,
  TerminalChip,
  TerminalDenseList,
  TerminalDisclosure,
  TerminalEmptyState,
  TerminalMetric,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPageHeading,
  TerminalPageShell,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal';
import AdminDrillThroughStrip from '../components/admin/AdminDrillThroughStrip';
import AdminOpsL0OverviewStrip from '../components/admin/AdminOpsL0OverviewStrip';
import AdminOpsSectionHeading from '../components/admin/AdminOpsSectionHeading';
import { useProductSurface } from '../hooks/useProductSurface';
import { cn } from '../utils/cn';
import { formatDateTime, formatNumber, formatPercent } from '../utils/format';

type LoadState = {
  loading: boolean;
  error: ParsedApiError | null;
  data: AdminCostSummaryResponse | null;
};

type QuotaDryRunState = {
  loading: boolean;
  error: ParsedApiError | null;
  data: QuotaDryRunResponse | null;
};

type LedgerState = {
  loading: boolean;
  error: ParsedApiError | null;
  data: LlmLedgerSummaryResponse | null;
};

type PricingPolicyState = {
  loading: boolean;
  error: ParsedApiError | null;
  data: ModelPricingPoliciesResponse | null;
};

const WINDOW_OPTIONS: Array<{ value: AdminCostWindowKey; label: string }> = [
  { value: '15m', label: '15 分钟' },
  { value: '1h', label: '1 小时' },
  { value: '24h', label: '24 小时' },
  { value: '7d', label: '7 天' },
];

const BUCKET_OPTIONS: Array<{ value: AdminCostBucket; label: string }> = [
  { value: 'hour', label: '小时' },
  { value: 'day', label: '天' },
];

const AREA_OPTIONS: Array<{ value: AdminCostArea; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'llm', label: 'AI 调用' },
  { value: 'provider', label: '数据源状态' },
  { value: 'market-cache', label: '市场缓存' },
  { value: 'scanner-ai', label: 'Scanner AI' },
];

const LIMIT_OPTIONS = [25, 50, 100, 200];

function readCostFilters(): Required<AdminCostSummaryParams> {
  if (typeof window === 'undefined') {
    return { window: '24h', bucket: 'hour', area: 'all', limit: 50 };
  }
  const query = new URLSearchParams(window.location.search);
  const windowValue = String(query.get('window') || '');
  const bucketValue = String(query.get('bucket') || '');
  const areaValue = String(query.get('area') || '');
  const limitValue = Number(query.get('limit') || 50);
  return {
    window: WINDOW_OPTIONS.some((item) => item.value === windowValue) ? windowValue as AdminCostWindowKey : '24h',
    bucket: BUCKET_OPTIONS.some((item) => item.value === bucketValue) ? bucketValue as AdminCostBucket : 'hour',
    area: AREA_OPTIONS.some((item) => item.value === areaValue) ? areaValue as AdminCostArea : 'all',
    limit: Number.isFinite(limitValue) ? Math.min(Math.max(Math.trunc(limitValue), 1), 200) : 50,
  };
}

const ROUTE_FAMILY_OPTIONS = [
  { value: 'analysis', label: '分析' },
  { value: 'guest_preview', label: '游客预览' },
  { value: 'scanner_ai', label: 'Scanner AI' },
  { value: 'agent_chat', label: 'Agent Chat' },
  { value: 'provider_market_data', label: '数据源数据' },
];

const QUOTA_OPERATION_OPTIONS: Array<{ value: QuotaDryRunOperation; label: string }> = [
  { value: 'estimate', label: '估算' },
  { value: 'reserve', label: '预占' },
  { value: 'consume', label: '消耗' },
  { value: 'release', label: '释放' },
];

const ENFORCEMENT_OPTIONS: Array<{ value: QuotaEnforcementMode; label: string }> = [
  { value: 'disabled', label: '关闭' },
  { value: 'dry_run', label: '试运行' },
  { value: 'enabled', label: '启用策略模拟' },
];

const UNSAFE_VISIBLE_TEXT_PATTERN = /(https?:\/\/|www\.|\?|=|token|secret|cookie|session|password|bearer|apikey|api_key|stack|trace|payload|prompt|credential)/i;

function formatDate(value?: string | null): string {
  return value ? formatDateTime(value) : '--';
}

function compactNumber(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return formatNumber(value, 0);
}

function moneyUsd(value?: string | number | null): string {
  if (value === null || value === undefined || value === '') return '--';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '--';
  if (Math.abs(numeric) > 0 && Math.abs(numeric) < 0.01) return `$${numeric.toFixed(6)}`;
  return `$${numeric.toFixed(2)}`;
}

function percent(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return formatPercent(value, { digits: 1, mode: 'ratio' });
}

function limitationLabel(value: string): string {
  if (value === 'observational_not_billing') return '观测值非账单';
  if (value === 'process_local_counters_reset_on_restart') return '进程内计数器会随重启清零';
  if (value === 'counter_snapshot_not_timestamped') return '计数器快照不含历史时间戳';
  if (value === 'llm_usage_unavailable') return 'LLM 用量账务摘要不可用';
  return safeVisibleText(value.replace(/_/g, ' '));
}

function exactnessLabel(value?: string | null): string {
  if (value === 'observational_not_billing') return '观测值非账单';
  if (value === 'estimated') return '估算';
  if (value === 'exact') return '精确';
  return '精确性待确认';
}

function hasCounters(data: AdminCostSummaryResponse): boolean {
  const summary = data.summary;
  return [
    summary.llmCalls,
    summary.llmUsageCalls,
    summary.estimatedDuplicateCandidates,
    summary.providerCalls,
    summary.providerCacheHits,
    summary.providerCacheMisses,
    summary.marketCacheHits,
    summary.marketCacheMisses,
    summary.scannerAiAttempts,
  ].some((value) => value > 0);
}

function safeDimensionText(dimensions?: Record<string, string>): string {
  const entries = Object.entries(dimensions || {}).slice(0, 4);
  if (entries.length === 0) return '--';
  const labelForKey = (key: string) => {
    if (key === 'owner_user_id' || key === 'ownerUserId') return '用户';
    if (key === 'route_family' || key === 'routeFamily') return '功能';
    if (key === 'provider') return '数据源';
    if (key === 'model') return '模型';
    if (key === 'call_type' || key === 'callType') return '调用';
    return safeVisibleText(key.replace(/_/g, ' '));
  };
  return entries.map(([key, value]) => `${labelForKey(key)}: ${safeVisibleText(value)}`).join(' · ');
}

function sanitizedError(error: unknown): ParsedApiError {
  const parsed = getParsedApiError(error);
  return {
    ...parsed,
    title: '读取成本观测失败',
    message: parsed.message || '成本观测快照暂不可用。',
    rawMessage: '',
  };
}

function sanitizedQuotaError(error: unknown): ParsedApiError {
  const parsed = getParsedApiError(error);
  return {
    ...parsed,
    title: '读取配额诊断失败',
    message: parsed.status === 403
      ? '当前账号没有成本观测权限。'
      : parsed.isTimeoutError
        ? '配额诊断请求超时，请稍后重试。'
        : parsed.message || '配额诊断暂不可用。',
    rawMessage: '',
    details: undefined,
  };
}

function sanitizedLedgerError(error: unknown): ParsedApiError {
  const parsed = getParsedApiError(error);
  return {
    ...parsed,
    title: '读取 AI 调用账本失败',
    message: parsed.status === 403
      ? '当前账号没有成本观测权限。'
      : parsed.isTimeoutError
        ? 'AI 调用账本请求超时，请稍后重试。'
        : parsed.message || 'AI 调用账本暂不可用。',
    rawMessage: '',
    details: undefined,
  };
}

function sanitizedPricingPolicyError(error: unknown): ParsedApiError {
  const parsed = getParsedApiError(error);
  return {
    ...parsed,
    title: '读取模型价格策略失败',
    message: parsed.status === 403
      ? '当前账号没有成本观测权限。'
      : parsed.isTimeoutError
        ? '模型价格策略请求超时，请稍后重试。'
        : parsed.message || '模型价格策略暂不可用。',
    rawMessage: '',
    details: undefined,
  };
}

function clampTokenEstimate(value: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 0;
  return Math.min(Math.max(Math.trunc(parsed), 0), 2_000_000);
}

function enforcementLabel(value?: QuotaEnforcementMode | string): string {
  if (value === 'disabled') return '关闭';
  if (value === 'enabled') return '启用策略模拟';
  return '试运行';
}

function reasonLabel(value?: string | null): string {
  if (!value?.trim()) return '无';
  if (value === 'within_budget') return '预算内';
  if (value === 'budget_exceeded') return '预算超限';
  if (value === 'quota_policy_block') return '配额策略会阻断';
  if (value === 'missing_api_key' || value === 'auth_or_key_invalid') return '凭证不可用';
  return safeVisibleText(value.replace(/_/g, ' ')).slice(0, 96);
}

function quotaStatusLabel(value?: string | null): string {
  if (value === 'allowed') return '允许';
  if (value === 'blocked') return '会阻断';
  if (value === 'denied') return '拒绝';
  return value ? safeVisibleText(value.replace(/_/g, ' ')) : '--';
}

function safeVisibleText(value?: string | null): string {
  const text = String(value ?? '').trim();
  if (!text) return '--';
  return UNSAFE_VISIBLE_TEXT_PATTERN.test(text) ? '已脱敏' : text.slice(0, 96);
}

function metricValueClass(tone: 'neutral' | 'info' | 'good' | 'warn' = 'neutral'): string {
  if (tone === 'info') return 'text-lg font-semibold text-cyan-100';
  if (tone === 'good') return 'text-lg font-semibold text-emerald-200';
  if (tone === 'warn') return 'text-lg font-semibold text-amber-100';
  return 'text-lg font-semibold text-white';
}

function iconTitle(icon: React.ReactNode, title: string) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="text-cyan-200">{icon}</span>
      <span>{title}</span>
    </span>
  );
}

const ReadOnlyBadges: React.FC<{ data?: AdminCostSummaryResponse | null }> = ({ data }) => {
  const metadata = data?.metadata;
  return (
    <div className="flex flex-wrap gap-2">
      <TerminalChip variant="info">
        {metadata?.readOnly === false ? '只读未确认' : '只读'}
      </TerminalChip>
      <TerminalChip variant="success">
        {metadata?.noExternalCalls === false ? '外部调用未确认' : '外部调用关闭'}
      </TerminalChip>
      <TerminalChip variant="neutral">{exactnessLabel(metadata?.exactness)}</TerminalChip>
    </div>
  );
};

const FilterRail: React.FC<{
  filters: Required<AdminCostSummaryParams>;
  onChange: (filters: Required<AdminCostSummaryParams>) => void;
}> = ({ filters, onChange }) => (
  <TerminalPanel as="aside">
    <TerminalSectionHeader
      eyebrow="L2 配额 / 成本运维"
      title={iconTitle(<ShieldCheck className="h-4 w-4" />, '窗口与范围')}
      action={<TerminalChip variant="neutral">只读筛选</TerminalChip>}
    />
    <div className="mt-5 grid gap-4">
      <Select
        label="窗口"
        value={filters.window}
        options={WINDOW_OPTIONS.map((option) => ({ ...option, value: option.value }))}
        placeholder=""
        onChange={(window) => onChange({ ...filters, window: window as AdminCostWindowKey })}
      />
      <Select
        label="粒度"
        value={filters.bucket}
        options={BUCKET_OPTIONS.map((option) => ({ ...option, value: option.value }))}
        placeholder=""
        onChange={(bucket) => onChange({ ...filters, bucket: bucket as AdminCostBucket })}
      />
      <Select
        label="区域"
        value={filters.area}
        options={AREA_OPTIONS.map((option) => ({ ...option, value: option.value }))}
        placeholder=""
        onChange={(area) => onChange({ ...filters, area: area as AdminCostArea })}
      />
      <Select
        label="数量上限"
        value={filters.limit}
        options={LIMIT_OPTIONS.map((limit) => ({ value: String(limit), label: String(limit) }))}
        placeholder=""
        onChange={(limit) => onChange({ ...filters, limit: Number(limit) })}
      />
    </div>
    <TerminalNotice variant="info" className="mt-4">
      仅使用窗口、粒度、区域和数量上限；不会按用户、凭证、地址或原始供应商内容搜索。
    </TerminalNotice>
  </TerminalPanel>
);

const RollupList: React.FC<{
  items: AdminCostRollup[];
  empty: string;
}> = ({ items, empty }) => {
  if (items.length === 0) {
    return <TerminalEmptyState title={empty} />;
  }
  return (
    <TerminalDenseList>
      {items.slice(0, 6).map((item) => (
        <article key={`${item.group}-${item.count}`} className="min-w-0">
          <TerminalNestedBlock className="min-w-0">
            <div className="flex items-start justify-between gap-3">
              <p className="min-w-0 truncate font-mono text-sm font-semibold text-white">{item.group}</p>
              <TerminalChip variant="neutral">{compactNumber(item.count)}</TerminalChip>
            </div>
            <p className="mt-2 truncate text-[11px] text-white/42">{safeDimensionText(item.dimensions)}</p>
          </TerminalNestedBlock>
        </article>
      ))}
    </TerminalDenseList>
  );
};

const CacheEfficiencyList: React.FC<{ items: AdminCostCacheEfficiency[] }> = ({ items }) => {
  if (items.length === 0) {
    return <TerminalEmptyState title="暂无数据源缓存计数" />;
  }
  return (
    <TerminalDenseList>
      {items.slice(0, 6).map((item) => (
        <article key={item.group} className="min-w-0">
          <TerminalNestedBlock className="min-w-0">
            <div className="flex items-start justify-between gap-3">
              <p className="min-w-0 truncate font-mono text-sm font-semibold text-white">{item.group}</p>
              <TerminalChip variant="success">{percent(item.hitRate)}</TerminalChip>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-[11px] text-white/44">
              <span>Hit <b className="font-mono text-white/70">{compactNumber(item.hits)}</b></span>
              <span>Miss <b className="font-mono text-white/70">{compactNumber(item.misses)}</b></span>
              <span>Join <b className="font-mono text-white/70">{compactNumber(item.inflightJoins)}</b></span>
            </div>
          </TerminalNestedBlock>
        </article>
      ))}
    </TerminalDenseList>
  );
};

const LimitationsPanel: React.FC<{ data: AdminCostSummaryResponse }> = ({ data }) => (
  <TerminalPanel as="section">
    <TerminalSectionHeader
      eyebrow="Limitations"
      title={iconTitle(<AlertTriangle className="h-4 w-4" />, '限制与数据质量')}
      action={(
        <TerminalChip variant={data.limitations.length ? 'caution' : 'neutral'}>
          {data.limitations.length ? `${data.limitations.length} 条限制` : '暂无限制'}
        </TerminalChip>
      )}
    />
    <div className="mt-4 grid gap-2">
      {data.limitations.length === 0 ? (
        <TerminalEmptyState title="暂无限制项" />
      ) : data.limitations.map((item) => (
        <TerminalNotice key={item.code} variant={item.severity === 'warning' ? 'caution' : 'info'}>
          <div className="flex flex-wrap items-center gap-2">
            <TerminalChip variant={item.severity === 'warning' ? 'caution' : 'info'}>
              {limitationLabel(item.code)}
            </TerminalChip>
            <span className="text-xs text-white/58">{item.severity === 'warning' ? '需关注' : '信息'}</span>
          </div>
          <p className="mt-2">
            {safeVisibleText(item.message) === '已脱敏' ? limitationLabel(item.code) : safeVisibleText(item.message)}
          </p>
        </TerminalNotice>
      ))}
    </div>
    <TerminalNotice variant="neutral" className="mt-4">
      这些计数器是观测信号，不是精确账单；重复候选只提示重复模式，不能单独证明可避免浪费。
    </TerminalNotice>
  </TerminalPanel>
);

const DeveloperDetails: React.FC<{ data: AdminCostSummaryResponse }> = ({ data }) => (
  <TerminalDisclosure title="开发者 / 响应形状（已脱敏）" summary="默认折叠，仅显示 redaction 后字段" className="mt-4">
    <dl className="grid gap-3 text-[11px] leading-5 text-white/48 sm:grid-cols-2">
      <div className="min-w-0">
        <dt className="text-white/32">countersSource</dt>
        <dd className="break-words font-mono text-white/64">{data.metadata.countersSource}</dd>
      </div>
      <div className="min-w-0">
        <dt className="text-white/32">exactness</dt>
        <dd className="break-words font-mono text-white/64">{data.metadata.exactness}</dd>
      </div>
      <div className="min-w-0">
        <dt className="text-white/32">dataSources</dt>
        <dd className="break-words font-mono text-white/64">{data.metadata.dataSources.join(', ') || '--'}</dd>
      </div>
      <div className="min-w-0">
        <dt className="text-white/32">redaction</dt>
        <dd className="break-words font-mono text-white/64">{data.metadata.redaction.join(', ') || '--'}</dd>
      </div>
    </dl>
  </TerminalDisclosure>
);

function ledgerQueryFromFilters(filters: Required<AdminCostSummaryParams>) {
  return {
    window: filters.window === '7d' ? '7d' as const : '24h' as const,
    bucket: filters.bucket,
    limit: filters.limit,
  };
}

function ledgerCount(data?: LlmLedgerSummaryResponse | null): number {
  return Number(data?.total.requestCount ?? data?.total.ledgerCount ?? data?.total.calls ?? 0);
}

function pricingCount(data: LlmLedgerSummaryResponse, key: 'pricing_unknown' | 'pricing_inactive'): number | null {
  const camelKey = key === 'pricing_unknown' ? 'pricingUnknown' : 'pricingInactive';
  const metadataValue = data.metadata[camelKey];
  if (typeof metadataValue === 'number') return metadataValue;
  const statusValue = data.metadata.resultStatusCounts?.[key] ?? data.metadata.resultStatusCounts?.[camelKey];
  if (typeof statusValue === 'number') return statusValue;
  const totalValue = data.total[camelKey];
  return typeof totalValue === 'number' ? totalValue : null;
}

function pricePerMillion(value?: string | null, currency = 'USD'): string {
  if (value === null || value === undefined || value === '') return '--';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '--';
  const formatted = Math.abs(numeric) > 0 && Math.abs(numeric) < 0.01 ? numeric.toFixed(6) : numeric.toFixed(4);
  return `${currency} ${formatted}`;
}

function sourceLabel(policy: ModelPricingPolicyItem): string {
  return policy.sourceLabel?.trim() || '本地策略';
}

const LedgerRollupList: React.FC<{
  items: LlmLedgerSummaryRollup[];
  empty: string;
  labelFor: (item: LlmLedgerSummaryRollup) => string;
}> = ({ items, empty, labelFor }) => {
  if (items.length === 0) {
    return <TerminalEmptyState title={empty} />;
  }
  return (
    <TerminalDenseList>
      {items.slice(0, 5).map((item) => (
        <article key={`${item.group}-${item.totalTokens}-${item.totalCostUsd}`} className="min-w-0">
          <TerminalNestedBlock className="min-w-0">
            <div className="flex items-start justify-between gap-3">
              <p className="min-w-0 truncate font-mono text-sm font-semibold text-white">{labelFor(item)}</p>
              <TerminalChip variant="info">{moneyUsd(item.totalCostUsd)}</TerminalChip>
            </div>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-white/42">
              <span>用量 <b className="font-mono text-white/68">{compactNumber(item.totalTokens)}</b></span>
              <span>请求 <b className="font-mono text-white/68">{compactNumber(item.requestCount ?? item.ledgerCount ?? item.calls)}</b></span>
            </div>
          </TerminalNestedBlock>
        </article>
      ))}
    </TerminalDenseList>
  );
};

const LlmLedgerPanel: React.FC<{ filters: Required<AdminCostSummaryParams> }> = ({ filters }) => {
  const { canReadCostObservability } = useProductSurface();
  const [state, setState] = useState<LedgerState>({ loading: true, error: null, data: null });

  useEffect(() => {
    if (!canReadCostObservability) {
      return;
    }
    let alive = true;
    void adminCostApi.getLlmLedgerSummary(ledgerQueryFromFilters(filters))
      .then((data) => {
        if (alive) setState({ loading: false, error: null, data });
      })
      .catch((error) => {
        if (alive) setState({ loading: false, error: sanitizedLedgerError(error), data: null });
      });
    return () => {
      alive = false;
    };
  }, [canReadCostObservability, filters]);

  if (!canReadCostObservability) {
    return null;
  }

  const data = state.data;
  const empty = data ? ledgerCount(data) === 0 : false;
  const pricingUnknown = data ? pricingCount(data, 'pricing_unknown') : null;
  const pricingInactive = data ? pricingCount(data, 'pricing_inactive') : null;

  return (
    <TerminalPanel as="section" data-testid="llm-ledger-panel">
      <TerminalSectionHeader
        eyebrow="AI 调用账本"
        title={iconTitle(<Coins className="h-4 w-4" />, 'AI 调用账本')}
        action={<TerminalChip variant="neutral">估算值，不等同于供应商账单</TerminalChip>}
      />

      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <TerminalMetric label="当前窗口" value={data?.window.key || ledgerQueryFromFilters(filters).window} valueClassName="text-sm font-semibold text-cyan-100" />
        <TerminalMetric label="总用量" value={compactNumber(data?.total.totalTokens)} valueClassName="text-lg font-semibold text-cyan-100" />
        <TerminalMetric label="估算成本" value={moneyUsd(data?.total.totalCostUsd)} valueClassName="text-lg font-semibold text-amber-100" />
        <TerminalMetric label="请求数" value={compactNumber(data ? ledgerCount(data) : undefined)} valueClassName="text-lg font-semibold text-white" />
      </div>

      {data ? (
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
          <TerminalMetric label="输入" value={compactNumber(data.total.promptTokens ?? data.total.inputTokens)} valueClassName="text-sm font-semibold text-white" />
          <TerminalMetric label="缓存输入" value={compactNumber(data.total.cachedInputTokens)} valueClassName="text-sm font-semibold text-white" />
          <TerminalMetric label="输出" value={compactNumber(data.total.completionTokens ?? data.total.outputTokens)} valueClassName="text-sm font-semibold text-white" />
        </div>
      ) : null}

      {state.loading ? <TerminalNotice variant="neutral" className="mt-4">正在读取 AI 调用账本</TerminalNotice> : null}
      {state.error ? <div className="mt-4"><ApiErrorAlert error={state.error} /></div> : null}
      {empty ? <div className="mt-4"><TerminalEmptyState title="当前窗口暂无 AI 调用账本记录" /></div> : null}

      {data ? (
        <>
          {pricingUnknown != null || pricingInactive != null ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {pricingUnknown != null ? <TerminalChip variant="caution">价格未知 {compactNumber(pricingUnknown)}</TerminalChip> : null}
              {pricingInactive != null ? <TerminalChip variant="caution">价格未激活 {compactNumber(pricingInactive)}</TerminalChip> : null}
            </div>
          ) : null}
          <div className="mt-4 grid grid-cols-1 gap-4 2xl:grid-cols-3">
            <section className="min-w-0">
              <h3 className="mb-3 text-sm font-semibold text-white/82">用户成本排行</h3>
              <LedgerRollupList
                items={data.byUser}
                empty="暂无用户成本记录"
                labelFor={(item) => item.dimensions.owner_user_id || item.dimensions.ownerUserId || item.group}
              />
            </section>
            <section className="min-w-0">
              <h3 className="mb-3 text-sm font-semibold text-white/82">模型成本分布</h3>
              <LedgerRollupList
                items={data.byProviderModel}
                empty="暂无模型成本记录"
                labelFor={(item) => `${item.dimensions.provider || 'unknown'} / ${item.dimensions.model || item.group}`}
              />
            </section>
            <section className="min-w-0">
              <h3 className="mb-3 text-sm font-semibold text-white/82">功能成本分布</h3>
              <LedgerRollupList
                items={data.byRouteFamily}
                empty="暂无功能成本记录"
                labelFor={(item) => item.dimensions.route_family || item.dimensions.routeFamily || item.group}
              />
            </section>
          </div>
          <TerminalDisclosure title="开发者 / LLM 账本响应形状（已脱敏）" summary="默认折叠，仅显示 redaction 后字段" className="mt-4">
            <dl className="grid gap-3 text-[11px] leading-5 text-white/48 sm:grid-cols-2">
              <div className="min-w-0">
                <dt className="text-white/32">readOnly</dt>
                <dd className="font-mono text-white/64">{String(data.metadata.readOnly)}</dd>
              </div>
              <div className="min-w-0">
                <dt className="text-white/32">liveEnforcement</dt>
                <dd className="font-mono text-white/64">{String(data.metadata.liveEnforcement)}</dd>
              </div>
              <div className="min-w-0">
                <dt className="text-white/32">dataSources</dt>
                <dd className="break-words font-mono text-white/64">{data.metadata.dataSources.join(', ') || '--'}</dd>
              </div>
              <div className="min-w-0">
                <dt className="text-white/32">redaction</dt>
                <dd className="break-words font-mono text-white/64">{data.metadata.redaction.join(', ') || '--'}</dd>
              </div>
            </dl>
          </TerminalDisclosure>
        </>
      ) : null}
    </TerminalPanel>
  );
};

const PricingPolicyPanel: React.FC = () => {
  const { canReadCostObservability } = useProductSurface();
  const [state, setState] = useState<PricingPolicyState>({ loading: true, error: null, data: null });

  useEffect(() => {
    if (!canReadCostObservability) {
      return;
    }
    let alive = true;
    void adminCostApi.getModelPricingPolicies()
      .then((data) => {
        if (alive) setState({ loading: false, error: null, data });
      })
      .catch((error) => {
        if (alive) setState({ loading: false, error: sanitizedPricingPolicyError(error), data: null });
      });
    return () => {
      alive = false;
    };
  }, [canReadCostObservability]);

  if (!canReadCostObservability) {
    return null;
  }

  const policies = state.data?.policies || [];

  return (
    <TerminalPanel as="section" data-testid="model-pricing-policy-panel">
      <TerminalSectionHeader
        eyebrow="Pricing Policies"
        title={iconTitle(<Tags className="h-4 w-4" />, '模型价格策略')}
        action={(
          <div className="flex flex-wrap gap-2">
            <TerminalChip variant="info">激活 {compactNumber(state.data?.activeCount)}</TerminalChip>
            <TerminalChip variant="neutral">手动维护</TerminalChip>
          </div>
        )}
      />

      <TerminalNotice variant="caution" className="mt-4">
        价格由本地策略维护，需定期按供应商官网更新；估算值不等同于供应商账单。
      </TerminalNotice>

      {state.loading ? <TerminalNotice variant="neutral" className="mt-4">正在读取模型价格策略</TerminalNotice> : null}
      {state.error ? <div className="mt-4"><ApiErrorAlert error={state.error} /></div> : null}
      {!state.loading && !state.error && policies.length === 0 ? (
        <div className="mt-4"><TerminalEmptyState title="暂无模型价格策略" /></div>
      ) : null}

      {policies.length > 0 ? (
        <div className="mt-4 grid gap-3">
          {policies.map((policy) => (
            <article
              key={`${policy.provider}-${policy.model}-${policy.effectiveFrom || 'na'}`}
              className="min-w-0"
            >
              <TerminalNestedBlock className="min-w-0">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="break-words font-mono text-sm font-semibold text-white">
                      {policy.provider} / {policy.model}
                    </p>
                    <p className="mt-1 text-[11px] text-white/42">
                      {formatDate(policy.effectiveFrom)} - {formatDate(policy.effectiveUntil)}
                    </p>
                  </div>
                  <TerminalChip variant={policy.active ? 'success' : 'neutral'}>
                    {policy.active ? 'active' : 'inactive'}
                  </TerminalChip>
                </div>
                <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
                  <TerminalMetric label="Input / 1M" value={pricePerMillion(policy.inputPricePer1m, policy.currency)} valueClassName="text-sm font-semibold text-cyan-100" />
                  <TerminalMetric label="Cached / 1M" value={pricePerMillion(policy.cachedInputPricePer1m, policy.currency)} valueClassName="text-sm font-semibold text-cyan-100" />
                  <TerminalMetric label="Output / 1M" value={pricePerMillion(policy.outputPricePer1m, policy.currency)} valueClassName="text-sm font-semibold text-cyan-100" />
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-white/44">
                  <TerminalChip variant="neutral">{policy.currency}</TerminalChip>
                  {policy.sourceUrl ? (
                    <a
                      className="min-w-0 break-words rounded-md border border-cyan-300/15 bg-cyan-400/8 px-2.5 py-1 text-cyan-100 transition hover:border-cyan-200/35"
                      href={policy.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {sourceLabel(policy)}
                    </a>
                  ) : (
                    <TerminalChip variant="neutral">{sourceLabel(policy)}</TerminalChip>
                  )}
                </div>
              </TerminalNestedBlock>
            </article>
          ))}
        </div>
      ) : null}

      {state.data ? (
        <TerminalDisclosure title="开发者 / 价格策略响应形状（已脱敏）" summary="默认折叠，仅显示 redaction 后字段" className="mt-4">
          <dl className="grid gap-3 text-[11px] leading-5 text-white/48 sm:grid-cols-2">
            <div className="min-w-0">
              <dt className="text-white/32">readOnly</dt>
              <dd className="font-mono text-white/64">{String(state.data.metadata.readOnly)}</dd>
            </div>
            <div className="min-w-0">
              <dt className="text-white/32">manualMaintenance</dt>
              <dd className="font-mono text-white/64">{String(state.data.metadata.manualMaintenance)}</dd>
            </div>
            <div className="min-w-0">
              <dt className="text-white/32">dataSources</dt>
              <dd className="break-words font-mono text-white/64">{state.data.metadata.dataSources.join(', ') || '--'}</dd>
            </div>
            <div className="min-w-0">
              <dt className="text-white/32">redaction</dt>
              <dd className="break-words font-mono text-white/64">{state.data.metadata.redaction.join(', ') || '--'}</dd>
            </div>
          </dl>
        </TerminalDisclosure>
      ) : null}
    </TerminalPanel>
  );
};

const QuotaDryRunPanel: React.FC = () => {
  const { canReadCostObservability } = useProductSurface();
  const [routeFamily, setRouteFamily] = useState('analysis');
  const [tokenEstimateInput, setTokenEstimateInput] = useState('4000');
  const [operation, setOperation] = useState<QuotaDryRunOperation>('estimate');
  const [enforcementMode, setEnforcementMode] = useState<QuotaEnforcementMode>('dry_run');
  const [reservationId, setReservationId] = useState('');
  const [state, setState] = useState<QuotaDryRunState>({ loading: false, error: null, data: null });

  useEffect(() => {
    if (!canReadCostObservability) {
      return;
    }
    let alive = true;
    void adminCostApi.runQuotaDryRun({
      routeFamily,
      tokenEstimate: clampTokenEstimate(tokenEstimateInput),
      operation: 'estimate',
      enforcementMode,
    })
      .then((data) => {
        if (alive) setState({ loading: false, error: null, data });
      })
      .catch((error) => {
        if (alive) setState({ loading: false, error: sanitizedQuotaError(error), data: null });
      });
    return () => {
      alive = false;
    };
  }, [canReadCostObservability, enforcementMode, routeFamily, tokenEstimateInput]);

  if (!canReadCostObservability) {
    return null;
  }

  const tokenEstimate = clampTokenEstimate(tokenEstimateInput);
  const canSubmit = operation === 'estimate' || operation === 'reserve' || reservationId.trim().length > 0;
  const data = state.data;

  const runDiagnostic = () => {
    setState((current) => ({ ...current, loading: true, error: null }));
    void adminCostApi.runQuotaDryRun({
      routeFamily,
      tokenEstimate,
      operation,
      enforcementMode,
      reservationId: reservationId.trim() || undefined,
      actualUnits: operation === 'consume' ? tokenEstimate : undefined,
    })
      .then((next) => setState({ loading: false, error: null, data: next }))
      .catch((error) => setState({ loading: false, error: sanitizedQuotaError(error), data: null }));
  };

  return (
    <TerminalPanel as="section" data-testid="quota-dry-run-panel">
      <TerminalSectionHeader
        eyebrow="Quota Pilot"
        title={iconTitle(<Gauge className="h-4 w-4" />, 'L2 配额 / 成本运维：配额试运行')}
        action={<TerminalChip variant="info">只读诊断</TerminalChip>}
      />

      <TerminalNotice variant="info" className="mt-4">
        当前为试运行/诊断，不会阻断真实请求
      </TerminalNotice>

      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-4">
        <TerminalMetric label="状态" value={state.loading ? '检查中' : quotaStatusLabel(data?.status)} valueClassName={metricValueClass(data?.wouldBlock ? 'warn' : 'info')} />
        <TerminalMetric label="模式" value={enforcementLabel(data?.enforcementMode || enforcementMode)} valueClassName={metricValueClass('warn')} />
        <TerminalMetric label="估算单位" value={compactNumber(data?.estimatedUnits)} valueClassName={metricValueClass('info')} />
        <TerminalMetric label="判定" value={data?.wouldBlock ? '会阻断' : data?.allowed ? '允许' : '--'} valueClassName={metricValueClass(data?.wouldBlock ? 'warn' : data?.allowed ? 'good' : 'neutral')} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-12">
        <div className="min-w-0 xl:col-span-3">
          <Select
            label="功能族群"
            value={routeFamily}
            options={ROUTE_FAMILY_OPTIONS}
            placeholder=""
            onChange={setRouteFamily}
          />
        </div>
        <label className="min-w-0 xl:col-span-3">
          <span className="theme-field-label mb-2 block">用量估算</span>
          <input
            className="h-10 w-full min-w-0 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 font-mono text-sm text-white outline-none transition focus:border-emerald-500/50"
            inputMode="numeric"
            min={0}
            max={2_000_000}
            value={tokenEstimateInput}
            onChange={(event) => setTokenEstimateInput(String(clampTokenEstimate(event.target.value)))}
          />
        </label>
        <div className="min-w-0 xl:col-span-3">
          <Select
            label="策略模式"
            value={enforcementMode}
            options={ENFORCEMENT_OPTIONS}
            placeholder=""
            onChange={(value) => setEnforcementMode(value as QuotaEnforcementMode)}
          />
        </div>
        <div className="min-w-0 xl:col-span-3">
          <Select
            label="试运行操作"
            value={operation}
            options={QUOTA_OPERATION_OPTIONS}
            placeholder=""
            onChange={(value) => setOperation(value as QuotaDryRunOperation)}
          />
        </div>
      </div>

      {operation === 'consume' || operation === 'release' ? (
        <label className="mt-3 block min-w-0">
          <span className="theme-field-label mb-2 block">预占编号</span>
          <input
            className="h-10 w-full min-w-0 rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2 font-mono text-sm text-white outline-none transition focus:border-emerald-500/50"
            value={reservationId}
            onChange={(event) => setReservationId(event.target.value.slice(0, 128))}
            placeholder="试运行 reservation id"
          />
        </label>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 text-xs leading-5 text-white/48">
          <span className="text-white/64">原因：</span>{' '}
          <span className={cn('font-mono', data?.wouldBlock ? 'text-amber-200' : 'text-white/62')}>{reasonLabel(data?.reasonCode)}</span>
        </div>
        <TerminalButton
          variant="secondary"
          onClick={runDiagnostic}
          disabled={state.loading || !canSubmit}
        >
          {state.loading ? '诊断中' : '运行试运行'}
        </TerminalButton>
      </div>

      {data?.wouldBlock ? (
        <TerminalNotice variant="caution" className="mt-4" role="status">
          试运行结果显示该策略会阻断；真实请求未被阻断。
        </TerminalNotice>
      ) : null}
      {state.error ? <div className="mt-4"><ApiErrorAlert error={state.error} /></div> : null}

      <TerminalDisclosure title="开发者 / Quota 响应形状（已脱敏）" summary="默认折叠，仅显示 redaction 后字段" className="mt-4">
        <dl className="grid gap-3 text-[11px] leading-5 text-white/48 sm:grid-cols-2">
          <div className="min-w-0">
            <dt className="text-white/32">diagnosticOnly</dt>
            <dd className="font-mono text-white/64">{String(data?.metadata.diagnosticOnly ?? true)}</dd>
          </div>
          <div className="min-w-0">
            <dt className="text-white/32">liveEnforcement</dt>
            <dd className="font-mono text-white/64">{String(data?.metadata.liveEnforcement ?? false)}</dd>
          </div>
          <div className="min-w-0">
            <dt className="text-white/32">noExternalCalls</dt>
            <dd className="font-mono text-white/64">{String(data?.metadata.noExternalCalls ?? true)}</dd>
          </div>
          <div className="min-w-0">
            <dt className="text-white/32">redaction</dt>
            <dd className="break-words font-mono text-white/64">{data?.metadata.redaction.join(', ') || '--'}</dd>
          </div>
        </dl>
      </TerminalDisclosure>
    </TerminalPanel>
  );
};

const AdminCostObservabilityPage: React.FC = () => {
  const [filters, setFilters] = useState<Required<AdminCostSummaryParams>>(() => readCostFilters());
  const [state, setState] = useState<LoadState>({ loading: true, error: null, data: null });

  useEffect(() => {
    let alive = true;
    void adminCostApi.getDuplicateSummary(filters)
      .then((data) => {
        if (alive) setState({ loading: false, error: null, data });
      })
      .catch((error) => {
        if (alive) setState({ loading: false, error: sanitizedError(error), data: null });
      });
    return () => {
      alive = false;
    };
  }, [filters]);

  const updateFilters = (next: Required<AdminCostSummaryParams>) => {
    setState((current) => ({ ...current, loading: true, error: null }));
    setFilters(next);
  };

  const data = state.data;
  const emptyCounters = useMemo(() => data ? !hasCounters(data) : false, [data]);
  const operatorState = data
    ? `${compactNumber(data.summary.llmCalls)} 次 AI / ${compactNumber(data.summary.providerCalls)} 次数据源`
    : state.loading
      ? '读取中'
      : '等待快照';
  const needsAttentionCount = data
    ? data.summary.estimatedDuplicateCandidates + data.summary.fallbackAttempts + data.summary.integrityRetries
    : 0;
  const attentionLabel = emptyCounters
    ? '当前窗口暂无可用计数'
    : needsAttentionCount
      ? `${compactNumber(needsAttentionCount)} 个成本压力信号`
      : '暂无明显成本压力';
  const l0TrustState = state.error && !data
    ? 'blocked'
    : state.loading && !data
      ? 'unknown'
      : emptyCounters
        ? 'observe'
        : needsAttentionCount
          ? 'degraded'
          : 'healthy';

  return (
    <div
      data-testid="admin-cost-observability-page"
      className="min-h-0 w-full flex-1 overflow-x-hidden overflow-y-auto no-scrollbar text-white"
    >
      <TerminalPageShell className="py-5 md:py-6">
        <TerminalPanel as="section" className="relative overflow-hidden">
          <TerminalPageHeading
            eyebrow="成本压力台"
            title="成本观测"
            action={<ReadOnlyBadges data={data} />}
          />
          <p className="mt-3 max-w-4xl text-sm leading-6 text-white/54">
            先判断预算压力、异常归属和下一步处理；账本、价格策略、Provider 与缓存细节默认后置到二级区。
          </p>
          <AdminOpsL0OverviewStrip
            dataTestId="admin-cost-l0-overview-strip"
            className="mt-5"
            systemTrustState={l0TrustState}
            impact={emptyCounters ? '当前窗口缺少可用计数器，成本压力只能保持观察。' : `${operatorState} · ${attentionLabel}`}
            recommendedAction={needsAttentionCount ? '先做配额试运行，再定位归属。' : '保持观测，按需切换窗口与范围。'}
            evidenceRef="主诊断板 / 二级细节：账本、价格、Provider / 缓存"
            lastUpdated={formatDate(data?.generatedAt)}
          />
          <AdminDrillThroughStrip
            className="mt-4"
            items={[
              {
                label: '查看相关日志',
                target: 'logs',
                evidenceType: 'cost area',
                reason: '回看当前窗口内与成本/数据源相关的业务事件。',
                params: {
                  tab: 'data_source',
                  query: filters.area === 'provider' ? 'provider' : filters.area,
                  since: filters.window,
                },
              },
              {
                label: '查看熔断与配额',
                target: 'providerCircuits',
                evidenceType: 'window',
                reason: '继续核对 provider 配额、拒绝与探测窗口。',
                params: { since: filters.window },
              },
              {
                label: '查看数据源维护',
                target: 'marketProviders',
                evidenceType: 'surface focus',
                reason: '对照数据源运维矩阵、缓存与就绪线索。',
                params: { surface: 'market_overview' },
              },
            ]}
          />
          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            <TerminalMetric
              label="页面用途"
              value="评估成本与配额风险"
              subvalue={`窗口 ${data?.window?.key || filters.window} · ${data?.window?.bucket || filters.bucket}`}
              valueClassName="text-sm font-semibold text-cyan-100"
            />
            <TerminalMetric
              label="当前状态"
              value={operatorState}
              subvalue={`生成 ${formatDate(data?.generatedAt)} · ${exactnessLabel(data?.metadata.exactness)}`}
              valueClassName={metricValueClass(emptyCounters ? 'warn' : 'neutral')}
            />
            <TerminalMetric
              label="需关注"
              value={attentionLabel}
              subvalue="重复候选、备用链路、完整性重试汇总"
              valueClassName={metricValueClass(emptyCounters || needsAttentionCount ? 'warn' : 'good')}
            />
            <TerminalMetric
              label="下一步"
              value={needsAttentionCount ? '先做配额试运行，再定位归属' : '保持观测，按需切换窗口'}
              subvalue={`生成 ${formatDate(data?.generatedAt)} · ${exactnessLabel(data?.metadata.exactness)}`}
              valueClassName={metricValueClass(needsAttentionCount ? 'warn' : 'neutral')}
            />
          </div>
        </TerminalPanel>

        {state.error ? <ApiErrorAlert error={state.error} /> : null}
        {state.loading ? (
          <TerminalPanel as="section">
            <TerminalNotice variant="neutral">正在读取成本观测快照</TerminalNotice>
          </TerminalPanel>
        ) : null}
        {data ? (
          <>
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
              <div className="min-w-0 space-y-6 xl:col-span-8">
                <TerminalPanel as="section">
                  <TerminalSectionHeader
                    eyebrow="主诊断板"
                    title="压力、异常、归属"
                    action={emptyCounters ? <TerminalChip variant="caution">计数器尚未接入或当前窗口暂无事件</TerminalChip> : <TerminalChip variant="neutral">窗口 {data.window?.key || filters.window}</TerminalChip>}
                  />
                  <TerminalNotice variant={emptyCounters ? 'caution' : needsAttentionCount ? 'info' : 'neutral'} className="mt-4">
                    {emptyCounters ? '计数器尚未接入或当前窗口暂无事件' : needsAttentionCount ? '优先查看重复候选、备用链路和完整性重试，再进入配额试运行。' : '当前成本观测保持稳定，先维持只读观察。'}
                  </TerminalNotice>
                  <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                    <TerminalMetric
                      label="成本压力"
                      value={`${compactNumber(data.summary.estimatedDuplicateCandidates)} 重复候选`}
                      subvalue={`${compactNumber(data.summary.fallbackAttempts)} 备用链路 · ${compactNumber(data.summary.integrityRetries)} 完整性重试`}
                      valueClassName={metricValueClass(data.summary.estimatedDuplicateCandidates || data.summary.fallbackAttempts || data.summary.integrityRetries ? 'warn' : 'good')}
                    />
                    <TerminalMetric
                      label="缓存效率"
                      value={`${percent(data.summary.providerCacheHitRate)} 数据源`}
                      subvalue={`${percent(data.summary.marketCacheHitRate)} 市场缓存`}
                      valueClassName={metricValueClass('good')}
                    />
                    <TerminalMetric
                      label="模型归属"
                      value={`${compactNumber(data.summary.llmCalls)} AI 调用`}
                      subvalue={`${compactNumber(data.summary.llmUsageTokens)} tokens · ${compactNumber(data.summary.llmUsageCalls)} usage rows`}
                      valueClassName={metricValueClass('info')}
                    />
                    <TerminalMetric
                      label="功能归属"
                      value={`${compactNumber(data.summary.scannerAiCompleted)} / ${compactNumber(data.summary.scannerAiAttempts)}`}
                      subvalue={`${compactNumber(data.summary.scannerAiSkipped)} skipped`}
                      valueClassName={metricValueClass('info')}
                    />
                  </div>
                </TerminalPanel>
                <LimitationsPanel data={data} />
              </div>
              <div className="min-w-0 space-y-6 xl:col-span-4">
                <AdminOpsSectionHeading
                  eyebrow="L2 / Quota-Cost Ops"
                  title="L2 配额 / 成本运维"
                  description="保留窗口过滤、Quota dry-run、账本与价格策略，但把它们明确标成运维控制与观测，而不是产品行为开关。"
                  action={<TerminalChip variant="info">只读控制与下钻</TerminalChip>}
                />
                <FilterRail filters={filters} onChange={updateFilters} />
                <QuotaDryRunPanel />
              </div>
            </div>

            <TerminalDisclosure title="L2 配额 / 成本运维细节：账本、价格、Provider / 缓存" summary={`默认折叠 · ${compactNumber(needsAttentionCount)} 个压力线索 · 开发者形状保持已脱敏`}>
              <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
                <div className="min-w-0 space-y-6 xl:col-span-12">
                  <LlmLedgerPanel key={`${filters.window}-${filters.bucket}-${filters.limit}`} filters={filters} />
                  <PricingPolicyPanel />
                  <div className="grid grid-cols-1 gap-6 2xl:grid-cols-2">
                    <TerminalPanel as="section">
                      <TerminalSectionHeader eyebrow="LLM" title={iconTitle(<Activity className="h-4 w-4" />, 'LLM 调用')} />
                      <div className="mt-4">
                        <RollupList items={data.llm.byCallType} empty="暂无 LLM 调用计数" />
                      </div>
                    </TerminalPanel>
                    <TerminalPanel as="section">
                      <TerminalSectionHeader eyebrow="Duplicate" title={iconTitle(<BarChart3 className="h-4 w-4" />, 'Guest Preview / Report duplicate candidates')} />
                      <div className="mt-4">
                        <RollupList items={[...data.llm.duplicateCandidates, ...data.providers.duplicateCandidates, ...data.scannerAi.duplicateCandidates]} empty="暂无重复候选" />
                      </div>
                    </TerminalPanel>
                    <TerminalPanel as="section">
                      <TerminalSectionHeader eyebrow="数据源状态" title={iconTitle(<DatabaseZap className="h-4 w-4" />, '数据源状态 / 备用链路')} />
                      <div className="mt-4 grid gap-3">
                        <RollupList items={[...data.providers.byCategory, ...data.providers.fallbackDepth, ...data.llm.fallbacks]} empty="暂无数据源备用计数" />
                        <CacheEfficiencyList items={data.providers.cacheEfficiency} />
                      </div>
                    </TerminalPanel>
                    <TerminalPanel as="section">
                      <TerminalSectionHeader eyebrow="市场缓存" title={iconTitle(<DatabaseZap className="h-4 w-4" />, '市场缓存命中 / 过期 / 缺失')} />
                      <div className="mt-4">
                        <RollupList items={[...data.marketCache.byPanelKey, ...data.marketCache.staleServed, ...data.marketCache.coldFallbacks, ...data.marketCache.refreshes]} empty="暂无市场缓存计数" />
                      </div>
                    </TerminalPanel>
                    <TerminalPanel as="section">
                      <TerminalSectionHeader eyebrow="Scanner AI" title={iconTitle(<Radar className="h-4 w-4" />, 'Scanner AI 解释')} />
                      <div className="mt-4">
                        <RollupList items={[...data.scannerAi.interpretations, ...data.scannerAi.skips]} empty="暂无 Scanner AI 计数" />
                      </div>
                    </TerminalPanel>
                  </div>
                  <DeveloperDetails data={data} />
                </div>
              </div>
            </TerminalDisclosure>
          </>
        ) : null}
      </TerminalPageShell>
    </div>
  );
};

export default AdminCostObservabilityPage;
