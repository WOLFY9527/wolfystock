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
import { ApiErrorAlert, Badge, Disclosure, GlassCard, Select } from '../components/common';
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
  { value: 'llm', label: 'LLM' },
  { value: 'provider', label: 'Provider' },
  { value: 'market-cache', label: 'MarketCache' },
  { value: 'scanner-ai', label: 'Scanner AI' },
];

const LIMIT_OPTIONS = [25, 50, 100, 200];

const ROUTE_FAMILY_OPTIONS = [
  { value: 'analysis', label: '分析' },
  { value: 'guest_preview', label: '游客预览' },
  { value: 'scanner_ai', label: 'Scanner AI' },
  { value: 'agent_chat', label: 'Agent Chat' },
  { value: 'provider_market_data', label: 'Provider 数据' },
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
    if (key === 'provider') return 'Provider';
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
    title: '读取 LLM 成本账本失败',
    message: parsed.status === 403
      ? '当前账号没有成本观测权限。'
      : parsed.isTimeoutError
      ? 'LLM 成本账本请求超时，请稍后重试。'
      : parsed.message || 'LLM 成本账本暂不可用。',
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

const ReadOnlyBadges: React.FC<{ data?: AdminCostSummaryResponse | null }> = ({ data }) => {
  const metadata = data?.metadata;
  return (
    <div className="flex flex-wrap gap-2">
      <Badge variant="info" className="border-cyan-300/25 bg-cyan-400/10 text-cyan-100">
        {metadata?.readOnly === false ? '只读未确认' : '只读'}
      </Badge>
      <Badge variant="success" className="border-emerald-300/25 bg-emerald-400/10 text-emerald-100">
        {metadata?.noExternalCalls === false ? '外部调用未确认' : '外部调用关闭'}
      </Badge>
      <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/62">
        {exactnessLabel(metadata?.exactness)}
      </Badge>
    </div>
  );
};

const SummaryTile: React.FC<{
  label: string;
  value: React.ReactNode;
  note?: React.ReactNode;
  tone?: 'neutral' | 'info' | 'good' | 'warn';
}> = ({ label, value, note, tone = 'neutral' }) => {
  const toneClass = {
    neutral: 'text-white',
    info: 'text-cyan-200',
    good: 'text-emerald-300',
    warn: 'text-amber-200',
  }[tone];
  return (
    <div className="min-w-0 rounded-2xl border border-white/5 bg-black/20 px-4 py-3">
      <p className="truncate text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">{label}</p>
      <p className={cn('mt-2 text-lg font-semibold leading-tight', toneClass)}>{value}</p>
      {note ? <p className="mt-1 text-xs leading-5 text-white/42">{note}</p> : null}
    </div>
  );
};

const FilterRail: React.FC<{
  filters: Required<AdminCostSummaryParams>;
  onChange: (filters: Required<AdminCostSummaryParams>) => void;
}> = ({ filters, onChange }) => (
  <GlassCard as="aside" className="p-4 md:p-5">
    <div className="flex items-start gap-3">
      <ShieldCheck className="mt-1 h-4 w-4 text-cyan-200" aria-hidden="true" />
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Filters</p>
        <h2 className="mt-1 text-base font-semibold text-white">安全过滤</h2>
      </div>
    </div>
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
    <p className="mt-4 rounded-xl border border-cyan-300/10 bg-cyan-400/8 px-3 py-2 text-[11px] leading-5 text-cyan-100/72">
      仅使用窗口、粒度、区域和数量上限；不会按用户、凭证、地址或原始供应商内容搜索。
    </p>
  </GlassCard>
);

const RollupList: React.FC<{
  items: AdminCostRollup[];
  empty: string;
}> = ({ items, empty }) => {
  if (items.length === 0) {
    return <p className="rounded-2xl border border-white/5 bg-black/20 px-4 py-5 text-sm text-white/45">{empty}</p>;
  }
  return (
    <div className="grid gap-3">
      {items.slice(0, 6).map((item) => (
        <article key={`${item.group}-${item.count}`} className="min-w-0 rounded-2xl border border-white/5 bg-black/20 p-3.5">
          <div className="flex items-start justify-between gap-3">
            <p className="min-w-0 truncate font-mono text-sm font-semibold text-white">{item.group}</p>
            <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/62">{compactNumber(item.count)}</Badge>
          </div>
          <p className="mt-2 truncate text-[11px] text-white/42">{safeDimensionText(item.dimensions)}</p>
        </article>
      ))}
    </div>
  );
};

const CacheEfficiencyList: React.FC<{ items: AdminCostCacheEfficiency[] }> = ({ items }) => {
  if (items.length === 0) {
    return <p className="rounded-2xl border border-white/5 bg-black/20 px-4 py-5 text-sm text-white/45">暂无 Provider cache 计数</p>;
  }
  return (
    <div className="grid gap-3">
      {items.slice(0, 6).map((item) => (
        <article key={item.group} className="min-w-0 rounded-2xl border border-white/5 bg-black/20 p-3.5">
          <div className="flex items-start justify-between gap-3">
            <p className="min-w-0 truncate font-mono text-sm font-semibold text-white">{item.group}</p>
            <Badge variant="success" className="border-emerald-300/20 bg-emerald-400/10 text-emerald-100">{percent(item.hitRate)}</Badge>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-[11px] text-white/44">
            <span>Hit <b className="font-mono text-white/70">{compactNumber(item.hits)}</b></span>
            <span>Miss <b className="font-mono text-white/70">{compactNumber(item.misses)}</b></span>
            <span>Join <b className="font-mono text-white/70">{compactNumber(item.inflightJoins)}</b></span>
          </div>
        </article>
      ))}
    </div>
  );
};

const SectionCard: React.FC<{
  icon: React.ReactNode;
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}> = ({ icon, eyebrow, title, children }) => (
  <GlassCard as="section" className="p-4 md:p-5">
    <div className="mb-4 flex items-start gap-3">
      <span className="mt-1 text-cyan-200">{icon}</span>
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">{eyebrow}</p>
        <h2 className="mt-1 text-base font-semibold text-white">{title}</h2>
      </div>
    </div>
    {children}
  </GlassCard>
);

const LimitationsPanel: React.FC<{ data: AdminCostSummaryResponse }> = ({ data }) => (
  <GlassCard as="section" className="p-4 md:p-5">
    <div className="flex items-start gap-3">
      <AlertTriangle className="mt-1 h-4 w-4 text-amber-200" aria-hidden="true" />
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Limitations</p>
        <h2 className="mt-1 text-base font-semibold text-white">限制与数据质量</h2>
      </div>
    </div>
    <div className="mt-4 grid gap-2">
      {data.limitations.length === 0 ? (
        <p className="rounded-2xl border border-white/5 bg-black/20 px-4 py-4 text-sm text-white/45">暂无限制项</p>
      ) : data.limitations.map((item) => (
        <div key={item.code} className="rounded-2xl border border-white/5 bg-black/20 px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant={item.severity === 'warning' ? 'warning' : 'info'}
              className={item.severity === 'warning' ? 'border-amber-300/25 bg-amber-400/10 text-amber-100' : 'border-cyan-300/20 bg-cyan-400/8 text-cyan-100'}
            >
              {limitationLabel(item.code)}
            </Badge>
            <span className="text-xs text-white/58">{item.severity === 'warning' ? '需关注' : '信息'}</span>
          </div>
          <p className="mt-2 text-xs leading-5 text-white/50">
            {safeVisibleText(item.message) === '已脱敏' ? limitationLabel(item.code) : safeVisibleText(item.message)}
          </p>
        </div>
      ))}
    </div>
    <p className="mt-4 text-xs leading-5 text-white/42">
      这些计数器是观测信号，不是精确账单；重复候选只提示重复模式，不能单独证明可避免浪费。
    </p>
  </GlassCard>
);

const DeveloperDetails: React.FC<{ data: AdminCostSummaryResponse }> = ({ data }) => (
  <Disclosure
    summary="开发者 / 响应形状"
    className="mt-4"
    bodyClassName="rounded-2xl border border-white/5 bg-black/20 p-4"
  >
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
  </Disclosure>
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
    return <p className="rounded-2xl border border-white/5 bg-black/20 px-4 py-4 text-sm text-white/45">{empty}</p>;
  }
  return (
    <div className="grid gap-2">
      {items.slice(0, 5).map((item) => (
        <article key={`${item.group}-${item.totalTokens}-${item.totalCostUsd}`} className="min-w-0 rounded-2xl border border-white/5 bg-black/20 px-3.5 py-3">
          <div className="flex items-start justify-between gap-3">
            <p className="min-w-0 truncate font-mono text-sm font-semibold text-white">{labelFor(item)}</p>
            <span className="shrink-0 font-mono text-sm text-cyan-100">{moneyUsd(item.totalCostUsd)}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-white/42">
            <span>用量 <b className="font-mono text-white/68">{compactNumber(item.totalTokens)}</b></span>
            <span>请求 <b className="font-mono text-white/68">{compactNumber(item.requestCount ?? item.ledgerCount ?? item.calls)}</b></span>
          </div>
        </article>
      ))}
    </div>
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
    <GlassCard as="section" className="p-4 md:p-5" data-testid="llm-ledger-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <Coins className="mt-1 h-4 w-4 shrink-0 text-cyan-200" aria-hidden="true" />
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">LLM Ledger</p>
            <h2 className="mt-1 text-lg font-semibold text-white">LLM 成本账本</h2>
          </div>
        </div>
        <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/62">
          估算值，不等同于供应商账单
        </Badge>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <SummaryTile label="当前窗口" value={data?.window.key || ledgerQueryFromFilters(filters).window} tone="info" />
        <SummaryTile label="总用量" value={compactNumber(data?.total.totalTokens)} tone="info" />
        <SummaryTile label="估算成本" value={moneyUsd(data?.total.totalCostUsd)} tone="warn" />
        <SummaryTile label="请求数" value={compactNumber(data ? ledgerCount(data) : undefined)} />
      </div>

      {data ? (
        <div className="mt-3 grid grid-cols-3 gap-2 text-[11px] text-white/44">
          <span className="min-w-0 rounded-xl border border-white/5 bg-black/20 px-3 py-2">输入 <b className="font-mono text-white/68">{compactNumber(data.total.promptTokens ?? data.total.inputTokens)}</b></span>
          <span className="min-w-0 rounded-xl border border-white/5 bg-black/20 px-3 py-2">缓存输入 <b className="font-mono text-white/68">{compactNumber(data.total.cachedInputTokens)}</b></span>
          <span className="min-w-0 rounded-xl border border-white/5 bg-black/20 px-3 py-2">输出 <b className="font-mono text-white/68">{compactNumber(data.total.completionTokens ?? data.total.outputTokens)}</b></span>
        </div>
      ) : null}

      {state.loading ? (
        <p className="mt-4 rounded-2xl border border-white/5 bg-black/20 px-4 py-4 text-sm text-white/50">正在读取 LLM 成本账本</p>
      ) : null}
      {state.error ? <div className="mt-4"><ApiErrorAlert error={state.error} /></div> : null}
      {empty ? (
        <p className="mt-4 rounded-2xl border border-white/5 bg-black/20 px-4 py-4 text-sm text-white/45">当前窗口暂无 LLM 成本账本记录</p>
      ) : null}

      {data ? (
        <>
          {pricingUnknown != null || pricingInactive != null ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {pricingUnknown != null ? (
                <Badge variant="warning" className="border-amber-300/25 bg-amber-400/10 text-amber-100">
                  价格未知 {compactNumber(pricingUnknown)}
                </Badge>
              ) : null}
              {pricingInactive != null ? (
                <Badge variant="warning" className="border-amber-300/25 bg-amber-400/10 text-amber-100">
                  价格未激活 {compactNumber(pricingInactive)}
                </Badge>
              ) : null}
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
          <Disclosure
            summary="开发者 / LLM 账本响应形状"
            className="mt-4"
            bodyClassName="rounded-2xl border border-white/5 bg-black/20 p-4"
          >
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
          </Disclosure>
        </>
      ) : null}
    </GlassCard>
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
    <GlassCard as="section" className="p-4 md:p-5" data-testid="model-pricing-policy-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <Tags className="mt-1 h-4 w-4 shrink-0 text-cyan-200" aria-hidden="true" />
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Pricing Policies</p>
            <h2 className="mt-1 text-lg font-semibold text-white">模型价格策略</h2>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="info" className="border-cyan-300/20 bg-cyan-400/8 text-cyan-100">
            激活 {compactNumber(state.data?.activeCount)}
          </Badge>
          <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/62">
            手动维护
          </Badge>
        </div>
      </div>

      <p className="mt-4 rounded-2xl border border-amber-300/16 bg-amber-400/8 px-4 py-3 text-xs leading-5 text-amber-100/86">
        价格由本地策略维护，需定期按供应商官网更新；估算值不等同于供应商账单。
      </p>

      {state.loading ? (
        <p className="mt-4 rounded-2xl border border-white/5 bg-black/20 px-4 py-4 text-sm text-white/50">正在读取模型价格策略</p>
      ) : null}
      {state.error ? <div className="mt-4"><ApiErrorAlert error={state.error} /></div> : null}
      {!state.loading && !state.error && policies.length === 0 ? (
        <p className="mt-4 rounded-2xl border border-white/5 bg-black/20 px-4 py-4 text-sm text-white/45">暂无模型价格策略</p>
      ) : null}

      {policies.length > 0 ? (
        <div className="mt-4 grid gap-3">
          {policies.map((policy) => (
            <article
              key={`${policy.provider}-${policy.model}-${policy.effectiveFrom || 'na'}`}
              className="min-w-0 rounded-2xl border border-white/5 bg-black/20 p-3.5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="break-words font-mono text-sm font-semibold text-white">
                    {policy.provider} / {policy.model}
                  </p>
                  <p className="mt-1 text-[11px] text-white/42">
                    {formatDate(policy.effectiveFrom)} - {formatDate(policy.effectiveUntil)}
                  </p>
                </div>
                <Badge
                  variant={policy.active ? 'success' : 'default'}
                  className={policy.active ? 'border-emerald-300/20 bg-emerald-400/10 text-emerald-100' : 'border-white/10 bg-white/[0.04] text-white/50'}
                >
                  {policy.active ? 'active' : 'inactive'}
                </Badge>
              </div>
              <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
                <div className="min-w-0 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2">
                  <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">Input / 1M</p>
                  <p className="mt-1 font-mono text-sm text-cyan-100">{pricePerMillion(policy.inputPricePer1m, policy.currency)}</p>
                </div>
                <div className="min-w-0 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2">
                  <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">Cached / 1M</p>
                  <p className="mt-1 font-mono text-sm text-cyan-100">{pricePerMillion(policy.cachedInputPricePer1m, policy.currency)}</p>
                </div>
                <div className="min-w-0 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2">
                  <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">Output / 1M</p>
                  <p className="mt-1 font-mono text-sm text-cyan-100">{pricePerMillion(policy.outputPricePer1m, policy.currency)}</p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-white/44">
                <span className="min-w-0 truncate rounded-full border border-white/5 bg-white/[0.02] px-2.5 py-1">{policy.currency}</span>
                {policy.sourceUrl ? (
                  <a
                    className="min-w-0 break-words rounded-full border border-cyan-300/15 bg-cyan-400/8 px-2.5 py-1 text-cyan-100 transition hover:border-cyan-200/35"
                    href={policy.sourceUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {sourceLabel(policy)}
                  </a>
                ) : (
                  <span className="min-w-0 break-words rounded-full border border-white/5 bg-white/[0.02] px-2.5 py-1">{sourceLabel(policy)}</span>
                )}
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {state.data ? (
        <Disclosure
          summary="开发者 / 价格策略响应形状"
          className="mt-4"
          bodyClassName="rounded-2xl border border-white/5 bg-black/20 p-4"
        >
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
        </Disclosure>
      ) : null}
    </GlassCard>
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
    <GlassCard as="section" className="p-4 md:p-5" data-testid="quota-dry-run-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <Gauge className="mt-1 h-4 w-4 shrink-0 text-cyan-200" aria-hidden="true" />
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Quota Pilot</p>
            <h2 className="mt-1 text-lg font-semibold text-white">配额试运行诊断</h2>
          </div>
        </div>
        <Badge variant="info" className="border-cyan-300/20 bg-cyan-400/8 text-cyan-100">
          当前为试运行/诊断，不会阻断真实请求
        </Badge>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-4">
        <SummaryTile label="状态" value={state.loading ? '检查中' : quotaStatusLabel(data?.status)} tone={data?.wouldBlock ? 'warn' : 'info'} />
        <SummaryTile label="模式" value={enforcementLabel(data?.enforcementMode || enforcementMode)} tone="warn" />
        <SummaryTile label="估算单位" value={compactNumber(data?.estimatedUnits)} tone="info" />
        <SummaryTile label="判定" value={data?.wouldBlock ? '会阻断' : data?.allowed ? '允许' : '--'} tone={data?.wouldBlock ? 'warn' : 'good'} />
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
            placeholder="dry-run reservation id"
          />
        </label>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 text-xs leading-5 text-white/48">
          <span className="text-white/64">原因：</span> <span className={cn('font-mono', data?.wouldBlock ? 'text-amber-200' : 'text-white/62')}>{reasonLabel(data?.reasonCode)}</span>
        </div>
        <button
          type="button"
          className="rounded-lg border border-cyan-300/20 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:border-cyan-200/35 hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:opacity-45"
          onClick={runDiagnostic}
          disabled={state.loading || !canSubmit}
        >
          {state.loading ? '诊断中' : '运行 dry-run'}
        </button>
      </div>

      {data?.wouldBlock ? (
        <div className="mt-4 rounded-2xl border border-amber-300/18 bg-amber-400/8 px-4 py-3 text-sm text-amber-100" role="status">
          dry-run 结果显示该策略会阻断；真实请求未被阻断。
        </div>
      ) : null}
      {state.error ? <div className="mt-4"><ApiErrorAlert error={state.error} /></div> : null}

      <Disclosure
        summary="开发者 / Quota 响应形状"
        className="mt-4"
        bodyClassName="rounded-2xl border border-white/5 bg-black/20 p-4"
      >
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
      </Disclosure>
    </GlassCard>
  );
};

const AdminCostObservabilityPage: React.FC = () => {
  const [filters, setFilters] = useState<Required<AdminCostSummaryParams>>({
    window: '24h',
    bucket: 'hour',
    area: 'all',
    limit: 50,
  });
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
    ? `${compactNumber(data.summary.llmCalls)} 次 LLM / ${compactNumber(data.summary.providerCalls)} 次 Provider`
    : state.loading
    ? '读取中'
    : '等待快照';

  return (
    <div className="min-h-0 flex-1 overflow-y-auto no-scrollbar bg-[#050505] px-4 py-4 text-white md:px-6 md:py-6">
      <div className="mx-auto flex w-full max-w-[1680px] flex-col gap-5">
        <GlassCard as="section" className="p-5 md:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-100/55">Cost Observability</p>
              <h1 className="mt-2 text-2xl font-semibold text-white md:text-3xl">成本观测</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-white/55">成本、配额与模型账本的只读运维视图。</p>
            </div>
            <ReadOnlyBadges data={data} />
          </div>
          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3">
            <SummaryTile label="页面用途" value="评估成本与配额风险" note={`窗口 ${data?.window?.key || filters.window} · ${data?.window?.bucket || filters.bucket}`} tone="info" />
            <SummaryTile label="当前状态" value={operatorState} note={`生成 ${formatDate(data?.generatedAt)} · ${exactnessLabel(data?.metadata.exactness)}`} tone={emptyCounters ? 'warn' : 'neutral'} />
            <SummaryTile label="下一步" value="优先查看配额试运行与账本摘要" note="开发者响应形状默认折叠" tone="warn" />
          </div>
        </GlassCard>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
          <div className="xl:col-span-3">
            <FilterRail filters={filters} onChange={updateFilters} />
          </div>
          <div className="min-w-0 xl:col-span-9">
            {state.error ? <ApiErrorAlert error={state.error} /> : null}
            {state.loading ? (
              <GlassCard as="section" className="p-5">
                <p className="text-sm text-white/55">正在读取成本观测快照</p>
              </GlassCard>
            ) : null}
            {data ? (
              <div className="grid gap-5">
                <GlassCard as="section" className="p-4 md:p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">Overview</p>
                      <h2 className="mt-1 text-lg font-semibold text-white">总览</h2>
                    </div>
                    {emptyCounters ? (
                      <Badge variant="warning" className="border-amber-300/25 bg-amber-400/10 text-amber-100">
                        计数器尚未接入或当前窗口暂无事件
                      </Badge>
                    ) : null}
                  </div>
                  <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <SummaryTile
                      label="成本压力"
                      value={`${compactNumber(data.summary.estimatedDuplicateCandidates)} 重复候选`}
                      note={`${compactNumber(data.summary.fallbackAttempts)} fallback · ${compactNumber(data.summary.integrityRetries)} integrity retry`}
                      tone={data.summary.estimatedDuplicateCandidates || data.summary.fallbackAttempts || data.summary.integrityRetries ? 'warn' : 'good'}
                    />
                    <SummaryTile
                      label="缓存效率"
                      value={`${percent(data.summary.providerCacheHitRate)} Provider`}
                      note={`${percent(data.summary.marketCacheHitRate)} MarketCache`}
                      tone="good"
                    />
                    <SummaryTile
                      label="模型账本"
                      value={`${compactNumber(data.summary.llmCalls)} LLM 调用`}
                      note={`${compactNumber(data.summary.llmUsageTokens)} tokens · ${compactNumber(data.summary.llmUsageCalls)} usage rows`}
                      tone="info"
                    />
                    <SummaryTile
                      label="Scanner AI"
                      value={`${compactNumber(data.summary.scannerAiCompleted)} / ${compactNumber(data.summary.scannerAiAttempts)}`}
                      note={`${compactNumber(data.summary.scannerAiSkipped)} skipped`}
                      tone="info"
                    />
                  </div>
                </GlassCard>
                <QuotaDryRunPanel />
                <LlmLedgerPanel key={`${filters.window}-${filters.bucket}-${filters.limit}`} filters={filters} />
                <PricingPolicyPanel />

                <div className="grid grid-cols-1 gap-5 2xl:grid-cols-2">
                  <SectionCard icon={<Activity className="h-4 w-4" />} eyebrow="LLM" title="LLM 调用">
                    <RollupList items={data.llm.byCallType} empty="暂无 LLM 调用计数" />
                  </SectionCard>
                  <SectionCard icon={<BarChart3 className="h-4 w-4" />} eyebrow="Duplicate" title="Guest Preview / Report duplicate candidates">
                    <RollupList items={[...data.llm.duplicateCandidates, ...data.providers.duplicateCandidates, ...data.scannerAi.duplicateCandidates]} empty="暂无重复候选" />
                  </SectionCard>
                  <SectionCard icon={<DatabaseZap className="h-4 w-4" />} eyebrow="Provider" title="Provider / 数据源 fallback">
                    <div className="grid gap-3">
                      <RollupList items={[...data.providers.byCategory, ...data.providers.fallbackDepth, ...data.llm.fallbacks]} empty="暂无 Provider fallback 计数" />
                      <CacheEfficiencyList items={data.providers.cacheEfficiency} />
                    </div>
                  </SectionCard>
                  <SectionCard icon={<DatabaseZap className="h-4 w-4" />} eyebrow="MarketCache" title="MarketCache 命中 / 过期 / 缺失">
                    <RollupList items={[...data.marketCache.byPanelKey, ...data.marketCache.staleServed, ...data.marketCache.coldFallbacks, ...data.marketCache.refreshes]} empty="暂无 MarketCache 计数" />
                  </SectionCard>
                  <SectionCard icon={<Radar className="h-4 w-4" />} eyebrow="Scanner AI" title="Scanner AI 解释">
                    <RollupList items={[...data.scannerAi.interpretations, ...data.scannerAi.skips]} empty="暂无 Scanner AI 计数" />
                  </SectionCard>
                  <LimitationsPanel data={data} />
                </div>
                <DeveloperDetails data={data} />
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminCostObservabilityPage;
