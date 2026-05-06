import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, BarChart3, DatabaseZap, Radar, ShieldCheck } from 'lucide-react';
import {
  adminCostApi,
  type AdminCostArea,
  type AdminCostBucket,
  type AdminCostCacheEfficiency,
  type AdminCostRollup,
  type AdminCostSummaryParams,
  type AdminCostSummaryResponse,
  type AdminCostWindowKey,
} from '../api/adminCost';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ApiErrorAlert, Badge, Disclosure, GlassCard, Select } from '../components/common';
import { cn } from '../utils/cn';
import { formatDateTime, formatNumber, formatPercent } from '../utils/format';

type LoadState = {
  loading: boolean;
  error: ParsedApiError | null;
  data: AdminCostSummaryResponse | null;
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

function formatDate(value?: string | null): string {
  return value ? formatDateTime(value) : '--';
}

function compactNumber(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return formatNumber(value, 0);
}

function percent(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return formatPercent(value, { digits: 1, mode: 'ratio' });
}

function limitationLabel(value: string): string {
  if (value === 'observational_not_billing') return '观测值非账单';
  if (value === 'process_local_counters_reset_on_restart') return '进程内计数器会随重启清零';
  if (value === 'counter_snapshot_not_timestamped') return '计数器快照不含历史时间戳';
  if (value === 'llm_usage_unavailable') return 'LLM usage 账务摘要不可用';
  return value;
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
  return entries.map(([key, value]) => `${key}: ${value}`).join(' · ');
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
        {metadata?.exactness === 'observational_not_billing' ? '观测值非账单' : '精确性待确认'}
      </Badge>
    </div>
  );
};

const SummaryTile: React.FC<{
  label: string;
  value: React.ReactNode;
  tone?: 'neutral' | 'info' | 'good' | 'warn';
}> = ({ label, value, tone = 'neutral' }) => {
  const toneClass = {
    neutral: 'text-white',
    info: 'text-cyan-200',
    good: 'text-emerald-300',
    warn: 'text-amber-200',
  }[tone];
  return (
    <div className="min-w-0 rounded-2xl border border-white/5 bg-black/20 px-4 py-3">
      <p className="truncate text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">{label}</p>
      <p className={cn('mt-2 font-mono text-2xl font-semibold leading-none', toneClass)}>{value}</p>
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
      仅使用 window、bucket、area、limit。没有 prompt、用户、token、URL 或 provider payload 搜索。
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
              {item.code}
            </Badge>
            <span className="text-xs text-white/58">{limitationLabel(item.code)}</span>
          </div>
          <p className="mt-2 text-xs leading-5 text-white/50">{item.message}</p>
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

  return (
    <div className="min-h-0 flex-1 overflow-y-auto no-scrollbar bg-[#050505] px-4 py-4 text-white md:px-6 md:py-6">
      <div className="mx-auto flex w-full max-w-[1680px] flex-col gap-5">
        <GlassCard as="section" className="p-5 md:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-100/55">Cost Observability</p>
              <h1 className="mt-2 text-2xl font-semibold text-white md:text-3xl">成本观测</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-white/55">
                管理员只读查看 duplicate-cost、LLM、Provider、MarketCache 与 Scanner AI 计数器快照；不触发外部调用、刷新或运行任务。
              </p>
            </div>
            <ReadOnlyBadges data={data} />
          </div>
          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            <SummaryTile label="Generated" value={formatDate(data?.generatedAt)} tone="info" />
            <SummaryTile label="Window" value={data?.window?.key || filters.window} />
            <SummaryTile label="Bucket" value={data?.window?.bucket || filters.bucket} />
            <SummaryTile label="Exactness" value={data?.metadata.exactness === 'observational_not_billing' ? 'observational_not_billing' : '--'} tone="warn" />
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
                  <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
                    <SummaryTile label="重复候选" value={compactNumber(data.summary.estimatedDuplicateCandidates)} tone="warn" />
                    <SummaryTile label="LLM Calls" value={compactNumber(data.summary.llmCalls)} tone="info" />
                    <SummaryTile label="Provider Calls" value={compactNumber(data.summary.providerCalls)} />
                    <SummaryTile label="Fallback" value={compactNumber(data.summary.fallbackAttempts)} tone="warn" />
                    <SummaryTile label="Provider Hit" value={percent(data.summary.providerCacheHitRate)} tone="good" />
                    <SummaryTile label="MarketCache Hit" value={percent(data.summary.marketCacheHitRate)} tone="good" />
                    <SummaryTile label="Integrity Retry" value={compactNumber(data.summary.integrityRetries)} tone="warn" />
                    <SummaryTile label="Scanner AI" value={`${compactNumber(data.summary.scannerAiCompleted)} / ${compactNumber(data.summary.scannerAiAttempts)}`} tone="info" />
                  </div>
                </GlassCard>

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
