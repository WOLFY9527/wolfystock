import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Activity } from 'lucide-react';
import {
  adminProviderCircuitsApi,
  type ProviderCircuitDiagnosticsBundle,
  type ProviderCircuitEventItem,
  type ProviderCircuitStateItem,
  type ProviderProbeEventItem,
  type ProviderQuotaWindowItem,
  type ProviderSlaReadinessItem,
} from '../api/adminProviderCircuits';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ApiErrorAlert } from '../components/common';
import {
  TerminalButton,
  TerminalChip,
  TerminalGrid,
  TerminalMetric,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPageHeading,
  TerminalPageShell,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal';
import { useProductSurface } from '../hooks/useProductSurface';
import { cn } from '../utils/cn';
import { formatDateTime, formatNumber } from '../utils/format';

type Tone = 'neutral' | 'good' | 'warn' | 'danger' | 'info';

const UNSAFE_VALUE_PATTERN = /(https?:\/\/|www\.|\?|=|token|secret|cookie|session|password|bearer|apikey|api_key|stack|trace)/i;

function safeText(value?: string | number | null, fallback = '--'): string {
  if (value === null || value === undefined || value === '') return fallback;
  const text = String(value).trim();
  if (!text || UNSAFE_VALUE_PATTERN.test(text)) return '已脱敏';
  return text.slice(0, 80);
}

function safeDate(value?: string | null): string {
  if (!value) return '--';
  const text = safeText(value);
  return text === '已脱敏' ? text : formatDateTime(text);
}

function stateLabel(state?: string | null): string {
  const labels: Record<string, string> = {
    closed: '闭合',
    open: '打开',
    half_open: '半开',
    degraded_cache_only: '仅缓存降级',
    disabled_by_operator: '人工禁用',
    provider_quota_depleted: '配额耗尽',
  };
  return labels[String(state || '').toLowerCase()] || safeText(state, '未知');
}

function bucketLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    timeout: '超时',
    provider_429: 'Provider 429',
    provider_403: 'Provider 403',
    provider_5xx: 'Provider 5xx',
    network_error: '网络错误',
    malformed_payload: '载荷异常',
    auth_or_key_invalid: '鉴权或密钥异常',
    quota_policy_block: '配额策略阻断',
    operator_disabled: '人工禁用',
    success: '成功',
    unknown: '未知',
  };
  return labels[String(value || '').toLowerCase()] || safeText(value, '未知');
}

function stateTone(state?: string | null): Tone {
  const normalized = String(state || '').toLowerCase();
  if (normalized === 'closed') return 'good';
  if (normalized === 'half_open' || normalized === 'degraded_cache_only') return 'warn';
  if (normalized === 'open' || normalized === 'disabled_by_operator' || normalized === 'provider_quota_depleted') return 'danger';
  return 'neutral';
}

function readinessTone(state?: string | null): Tone {
  const normalized = String(state || '').toLowerCase();
  if (normalized === 'dry_run_enabled' || normalized === 'observed') return 'good';
  if (normalized === 'missing_credentials' || normalized === 'live_credentials_present_live_calls_disabled') return 'warn';
  if (normalized === 'disabled' || normalized === 'sanitized_provider_error' || normalized === 'malformed_provider_payload') return 'danger';
  return 'neutral';
}

function freshnessLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    fresh: '新鲜',
    stale: '滞后',
    expired: '过期',
    unknown: '未知',
  };
  return labels[String(value || '').toLowerCase()] || safeText(value, '未知');
}

function latencyLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    normal: '正常',
    slow: '慢',
    critical: '严重',
    unknown: '未知',
  };
  return labels[String(value || '').toLowerCase()] || safeText(value, '未知');
}

function credentialLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    disabled: '禁用',
    missing_credentials: '缺少凭证',
    live_credentials_present_live_calls_disabled: '有凭证 / 外呼关闭',
    dry_run_enabled: 'Dry-run',
    configured: '已配置',
    credentials_present: '有凭证',
    unknown: '未知',
  };
  return labels[String(value || '').toLowerCase()] || safeText(value, '未知');
}

function boolLabel(value?: boolean | null): string {
  return value ? '是' : '否';
}

const METRIC_VALUE_CLASS_BY_TONE: Record<Tone, string> = {
  neutral: 'text-white',
  good: 'text-emerald-300',
  warn: 'text-amber-300',
  danger: 'text-rose-300',
  info: 'text-cyan-300',
};

function chipVariant(tone: Tone): 'neutral' | 'success' | 'caution' | 'danger' | 'info' {
  return ({
    neutral: 'neutral',
    good: 'success',
    warn: 'caution',
    danger: 'danger',
    info: 'info',
  } as const)[tone];
}

function dimensionText(providerCategory?: string | null, routeFamily?: string | null): string {
  return `分类 ${safeText(providerCategory, '未分组')} · 路由 ${safeText(routeFamily, '全路由')}`;
}

function readinessNotice(item: ProviderSlaReadinessItem): string {
  if (item.liveHttpCallsEnabled === false) return '当前只读观测外部调用门禁，不会触发 provider 实际请求。';
  if (item.credentialsPresent === false) return '凭证未就绪，先核对凭证配置与开关。';
  if (item.wouldBlockCall) return '当前门禁判断会阻断调用，需先查看熔断与最近错误。';
  return '当前仅展示就绪信号与趋势，不改变排序、fallback 或配额语义。';
}

const CurrentStatesPanel: React.FC<{ items: ProviderCircuitStateItem[] }> = ({ items }) => (
  <TerminalPanel as="section" className="h-full">
    <TerminalSectionHeader
      eyebrow="当前熔断"
      title="当前熔断状态"
      action={<TerminalChip variant="neutral">只读快照</TerminalChip>}
    />
    {items.length === 0 ? (
      <TerminalNotice variant="neutral" className="mt-4">
        暂无 provider 熔断状态
      </TerminalNotice>
    ) : (
      <div className="mt-4 grid grid-cols-1 gap-3 2xl:grid-cols-2">
        {items.map((item, index) => (
          <TerminalNestedBlock key={`${item.provider}-${item.providerCategory || 'all'}-${item.routeFamily || 'all'}-${index}`} className="min-w-0">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{safeText(item.provider)}</p>
                <p className="mt-1 truncate font-mono text-[11px] text-white/42">
                  {dimensionText(item.providerCategory, item.routeFamily)}
                </p>
              </div>
              <TerminalChip variant={chipVariant(stateTone(item.state))} className="shrink-0 font-semibold">
                {stateLabel(item.state)}
              </TerminalChip>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-2 text-[11px] text-white/44 sm:grid-cols-3">
              <p className="min-w-0">
                原因 bucket
                <span className="block truncate font-mono text-white/68">{bucketLabel(item.reasonBucket)}</span>
              </p>
              <p className="min-w-0">
                冷却至
                <span className="block truncate font-mono text-white/68">{safeDate(item.cooldownUntil)}</span>
              </p>
              <p className="min-w-0">
                更新时间
                <span className="block truncate font-mono text-white/68">{safeDate(item.updatedAt)}</span>
              </p>
            </div>
          </TerminalNestedBlock>
        ))}
      </div>
    )}
  </TerminalPanel>
);

const EventsPanel: React.FC<{ items: ProviderCircuitEventItem[] }> = ({ items }) => (
  <TerminalPanel as="section" dense>
    <TerminalSectionHeader eyebrow="事件" title="最近熔断事件" />
    {items.length === 0 ? (
      <TerminalNotice variant="neutral" className="mt-4">
        暂无熔断事件
      </TerminalNotice>
    ) : (
      <div className="mt-4 space-y-3">
        {items.map((item, index) => (
          <TerminalNestedBlock key={`${item.provider}-${item.eventType}-${item.createdAt || index}`} className="min-w-0">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{safeText(item.eventType)}</p>
                <p className="mt-1 truncate font-mono text-[11px] text-white/42">
                  {dimensionText(item.providerCategory, item.routeFamily)}
                </p>
              </div>
              <span className="shrink-0 font-mono text-[11px] text-white/42">{safeDate(item.createdAt)}</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-4">
              <p>
                状态变化
                <span className="block truncate font-mono text-white/68">
                  {stateLabel(item.fromState)} {'->'} {stateLabel(item.toState)}
                </span>
              </p>
              <p>
                原因 bucket
                <span className="block truncate font-mono text-white/68">{bucketLabel(item.reasonBucket)}</span>
              </p>
              <p>
                请求 bucket
                <span className="block truncate font-mono text-white/68">{safeText(item.requestCountBucket)}</span>
              </p>
              <p>
                持续时间
                <span className="block truncate font-mono text-white/68">{safeText(item.durationBucketMs)} ms</span>
              </p>
            </div>
          </TerminalNestedBlock>
        ))}
      </div>
    )}
  </TerminalPanel>
);

const QuotaWindowsPanel: React.FC<{ items: ProviderQuotaWindowItem[] }> = ({ items }) => (
  <TerminalPanel as="section" dense>
    <TerminalSectionHeader eyebrow="配额" title="配额窗口" />
    {items.length === 0 ? (
      <TerminalNotice variant="neutral" className="mt-4">
        暂无配额窗口
      </TerminalNotice>
    ) : (
      <div className="mt-4 grid grid-cols-1 gap-3">
        {items.map((item, index) => (
          <TerminalNestedBlock key={`${item.provider}-${item.windowStart}-${index}`} className="min-w-0">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{safeText(item.provider)}</p>
                <p className="mt-1 truncate font-mono text-[11px] text-white/42">
                  {dimensionText(item.providerCategory, item.routeFamily)}
                </p>
              </div>
              <TerminalChip variant="info" className="shrink-0 font-mono">
                {safeText(item.windowType)}
              </TerminalChip>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-4">
              <p>
                请求数
                <span className="block font-mono text-white/68">{formatNumber(item.requestCount, 0)}</span>
              </p>
              <p>
                拒绝数
                <span className="block font-mono text-rose-100/80">{formatNumber(item.rejectedCount, 0)}</span>
              </p>
              <p>
                成功 / 失败
                <span className="block font-mono text-white/68">
                  {formatNumber(item.successCount, 0)} / {formatNumber(item.failureCount, 0)}
                </span>
              </p>
              <p>
                探测数
                <span className="block font-mono text-white/68">{formatNumber(item.probeCount, 0)}</span>
              </p>
              <p>
                预留 / 消耗
                <span className="block font-mono text-white/68">
                  {formatNumber(item.reservedUnits, 0)} / {formatNumber(item.consumedUnits, 0)}
                </span>
              </p>
              <p>
                429 / 403
                <span className="block font-mono text-white/68">
                  {formatNumber(item.provider429Count, 0)} / {formatNumber(item.provider403Count, 0)}
                </span>
              </p>
              <p>
                Cache / stale
                <span className="block font-mono text-white/68">
                  {formatNumber(item.cacheOnlyCount, 0)} / {formatNumber(item.staleServedCount, 0)}
                </span>
              </p>
              <p>
                窗口起点
                <span className="block truncate font-mono text-white/68">{safeDate(item.windowStart)}</span>
              </p>
            </div>
          </TerminalNestedBlock>
        ))}
      </div>
    )}
  </TerminalPanel>
);

const ProbeEventsPanel: React.FC<{ items: ProviderProbeEventItem[] }> = ({ items }) => (
  <TerminalPanel as="section" dense>
    <TerminalSectionHeader eyebrow="探测" title="探测事件" />
    {items.length === 0 ? (
      <TerminalNotice variant="neutral" className="mt-4">
        暂无探测事件
      </TerminalNotice>
    ) : (
      <div className="mt-4 space-y-3">
        {items.map((item, index) => (
          <TerminalNestedBlock key={`${item.provider}-${item.probeType}-${item.createdAt || index}`} className="min-w-0">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{safeText(item.probeType)}</p>
                <p className="mt-1 truncate font-mono text-[11px] text-white/42">
                  {dimensionText(item.providerCategory, item.routeFamily)}
                </p>
              </div>
              <TerminalChip variant="success" className="shrink-0 font-semibold">
                {bucketLabel(item.resultBucket)}
              </TerminalChip>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-3">
              <p>
                来源
                <span className="block truncate font-mono text-white/68">{safeText(item.probeSource)}</span>
              </p>
              <p>
                持续时间
                <span className="block truncate font-mono text-white/68">{safeText(item.durationBucketMs)} ms</span>
              </p>
              <p>
                创建时间
                <span className="block truncate font-mono text-white/68">{safeDate(item.createdAt)}</span>
              </p>
            </div>
          </TerminalNestedBlock>
        ))}
      </div>
    )}
  </TerminalPanel>
);

const SlaReadinessPanel: React.FC<{ items: ProviderSlaReadinessItem[] }> = ({ items }) => {
  const [openErrorSections, setOpenErrorSections] = useState<Record<string, boolean>>({});
  const [openBoundarySections, setOpenBoundarySections] = useState<Record<string, boolean>>({});

  return (
    <TerminalPanel as="section" className="col-span-12">
      <TerminalSectionHeader
        eyebrow="就绪度"
        title="Provider SLA / 凭证就绪"
        action={<TerminalChip variant="neutral">只读 · 外部调用关闭</TerminalChip>}
      />
      {items.length === 0 ? (
        <TerminalNotice variant="neutral" className="mt-4">
          暂无 SLA / readiness 诊断
        </TerminalNotice>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
          {items.map((item, index) => {
            const itemKey = `${item.provider}-${item.providerCategory || 'all'}-${item.routeFamily || 'all'}-${index}`;
            const errorSectionOpen = openErrorSections[itemKey] === true;
            const boundarySectionOpen = openBoundarySections[itemKey] === true;

            return (
              <TerminalNestedBlock key={itemKey} className="min-w-0">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-white">{safeText(item.provider)}</p>
                    <p className="mt-1 truncate font-mono text-[11px] text-white/42">
                      {dimensionText(item.providerCategory, item.routeFamily)}
                    </p>
                  </div>
                  <TerminalChip variant={chipVariant(readinessTone(item.readinessState))} className="shrink-0 font-semibold">
                    {credentialLabel(item.credentialState)}
                  </TerminalChip>
                </div>

                <TerminalNotice
                  variant={item.wouldBlockCall ? 'caution' : item.credentialsPresent === false ? 'danger' : 'info'}
                  className="mt-3"
                >
                  {readinessNotice(item)}
                </TerminalNotice>

                <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-white/44 md:grid-cols-4">
                  <p>
                    延迟
                    <span className="block truncate font-mono text-white/68">
                      {latencyLabel(item.latencyState)} · {safeText(item.latencyBucketMs)} ms
                    </span>
                  </p>
                  <p>
                    新鲜度
                    <span className="block truncate font-mono text-white/68">
                      {freshnessLabel(item.freshnessState)} · {safeText(item.freshnessSeconds)} s
                    </span>
                  </p>
                  <p>
                    错误状态
                    <span className="block truncate font-mono text-white/68">
                      {safeText(item.errorState)} · {safeText(item.errorRate)}
                    </span>
                  </p>
                  <p>
                    阻断判断
                    <span className="block truncate font-mono text-white/68">{boolLabel(item.wouldBlockCall)}</span>
                  </p>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-3">
                  <TerminalMetric
                    label="趋势请求"
                    value={safeText(item.trendSummary?.requestCountBucket, '0')}
                    valueClassName="text-sm"
                  />
                  <TerminalMetric
                    label="趋势失败"
                    value={safeText(item.trendSummary?.failureCountBucket, '0')}
                    valueClassName="text-sm"
                  />
                  <TerminalMetric
                    label="429 / 403"
                    value={`${safeText(item.trendSummary?.provider429CountBucket, '0')} / ${safeText(item.trendSummary?.provider403CountBucket, '0')}`}
                    valueClassName="text-sm"
                  />
                  <TerminalMetric
                    label="最近观察"
                    value={safeDate(item.trendSummary?.latestObservationAt)}
                    valueClassName="text-sm"
                  />
                </div>

                <TerminalNestedBlock data-terminal-primitive="disclosure" className="mt-3 px-2.5 py-2">
                  <div className="flex min-w-0 items-center justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">最近错误 buckets</h3>
                      <p className="mt-0.5 truncate text-[11px] text-white/38">{`${(item.recentErrors || []).length} 项，默认收起`}</p>
                    </div>
                    <TerminalButton
                      variant="compact"
                      className="shrink-0 px-2 py-1 text-[11px] text-white/58 hover:text-white"
                      aria-expanded={errorSectionOpen}
                      aria-label={`${errorSectionOpen ? '收起' : '展开'} 最近错误 buckets`}
                      onClick={() => {
                        setOpenErrorSections((current) => ({ ...current, [itemKey]: !errorSectionOpen }));
                      }}
                    >
                      {errorSectionOpen ? '收起' : '展开'}
                    </TerminalButton>
                  </div>
                  {errorSectionOpen ? (
                    <div className="mt-2">
                      {(item.recentErrors || []).length === 0 ? (
                        <p className="text-white/48">暂无错误 bucket</p>
                      ) : (
                        <div className="space-y-2">
                          {(item.recentErrors || []).map((error) => (
                            <p key={`${error.reasonBucket}-${error.latestAt || 'none'}`} className="font-mono text-white/60">
                              {bucketLabel(error.reasonBucket)} · {safeText(error.countBucket)} · {safeDate(error.latestAt)}
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : null}
                </TerminalNestedBlock>

                <TerminalNestedBlock data-terminal-primitive="disclosure" className="mt-3 px-2.5 py-2">
                  <div className="flex min-w-0 items-center justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">技术边界</h3>
                      <p className="mt-0.5 truncate text-[11px] text-white/38">默认收起</p>
                    </div>
                    <TerminalButton
                      variant="compact"
                      className="shrink-0 px-2 py-1 text-[11px] text-white/58 hover:text-white"
                      aria-expanded={boundarySectionOpen}
                      aria-label={`${boundarySectionOpen ? '收起' : '展开'} 技术边界`}
                      onClick={() => {
                        setOpenBoundarySections((current) => ({ ...current, [itemKey]: !boundarySectionOpen }));
                      }}
                    >
                      {boundarySectionOpen ? '收起' : '展开'}
                    </TerminalButton>
                  </div>
                  {boundarySectionOpen ? (
                    <div className="mt-2 grid grid-cols-1 gap-2 text-[11px] text-white/50 md:grid-cols-2">
                      <p>
                        调用门禁
                        <span className="block font-mono text-white/68">{boolLabel(item.liveHttpCallsEnabled)}</span>
                      </p>
                      <p>
                        Dry-run
                        <span className="block font-mono text-white/68">{boolLabel(item.dryRunEnabled)}</span>
                      </p>
                      <p>
                        排序 / fallback 变化
                        <span className="block font-mono text-white/68">
                          {boolLabel(item.wouldChangeProviderOrder)} / {boolLabel(item.wouldChangeFallbackBehavior)}
                        </span>
                      </p>
                      <p>
                        熔断建议
                        <span className="block font-mono text-white/68">
                          {safeText(item.circuitAdvisoryState)} / {stateLabel(item.circuitStateCandidate)}
                        </span>
                      </p>
                    </div>
                  ) : null}
                </TerminalNestedBlock>
              </TerminalNestedBlock>
            );
          })}
        </div>
      )}
    </TerminalPanel>
  );
};

const BoundaryPanel: React.FC<{ data?: ProviderCircuitDiagnosticsBundle | null }> = ({ data }) => {
  const metadata = data?.states.metadata;
  const [boundaryOpen, setBoundaryOpen] = useState(false);

  return (
    <TerminalPanel as="aside" dense className="h-full">
      <TerminalSectionHeader eyebrow="边界" title="诊断观测" />
      <TerminalNotice variant="info" className="mt-4">
        当前为诊断观测，不会改变 provider fallback 或 MarketCache 行为。
      </TerminalNotice>
      <TerminalNestedBlock data-terminal-primitive="disclosure" className="mt-3 px-2.5 py-2">
        <div className="flex min-w-0 items-center justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">技术边界</h3>
            <p className="mt-0.5 truncate text-[11px] text-white/38">默认收起</p>
          </div>
          <TerminalButton
            variant="compact"
            className="shrink-0 px-2 py-1 text-[11px] text-white/58 hover:text-white"
            aria-expanded={boundaryOpen}
            aria-label={`${boundaryOpen ? '收起' : '展开'} 技术边界`}
            onClick={() => setBoundaryOpen((current) => !current)}
          >
            {boundaryOpen ? '收起' : '展开'}
          </TerminalButton>
        </div>
        {boundaryOpen ? (
          <div className="mt-2 grid grid-cols-1 gap-2 text-[11px] text-white/50">
            <p>
              读取边界
              <span className="block font-mono text-white/68">沿用既有 provider 读取门禁</span>
            </p>
            <p>
              只读 / 外呼 / 门禁
              <span className="block font-mono text-white/68">
                {metadata?.readOnly === true ? '只读' : '未确认'} / {metadata?.noExternalCalls === true ? '关闭' : '未确认'} / {metadata?.liveEnforcement === false ? '关闭' : '未确认'}
              </span>
            </p>
            <p>
              数据来源
              <span className="block font-mono text-white/68">{safeText(metadata?.dataSources?.join(', '), '未提供')}</span>
            </p>
            <p>
              Redaction
              <span className="block font-mono text-white/68">{safeText(metadata?.redaction?.join(', '), '未提供')}</span>
            </p>
          </div>
        ) : null}
      </TerminalNestedBlock>
    </TerminalPanel>
  );
};

const LoadingState: React.FC = () => (
  <TerminalPanel as="section" role="status" aria-label="正在读取 provider 熔断诊断">
    <div className="flex items-center gap-3">
      <Activity className="h-4 w-4 animate-pulse text-cyan-200" aria-hidden="true" />
      <div>
        <p className="text-sm font-semibold text-white">正在读取 provider 熔断诊断</p>
        <p className="mt-1 text-xs text-white/46">只读取现有诊断 API，不触发 provider 调用。</p>
      </div>
    </div>
  </TerminalPanel>
);

const AdminProviderCircuitDiagnosticsPage: React.FC = () => {
  const { canReadProviders } = useProductSurface();
  const [data, setData] = useState<ProviderCircuitDiagnosticsBundle | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [secondaryDetailsOpen, setSecondaryDetailsOpen] = useState(false);

  useEffect(() => {
    if (!canReadProviders) {
      return;
    }
    let cancelled = false;
    adminProviderCircuitsApi.getDiagnostics({ limit: 50 })
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((apiError) => {
        if (!cancelled) {
          const parsed = getParsedApiError(apiError);
          setError({ ...parsed, title: '读取 provider 熔断诊断失败' });
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [canReadProviders]);

  const summary = useMemo(() => {
    const states = data?.states.items || [];
    const openCount = states.filter((item) => stateTone(item.state) === 'danger').length;
    const warnCount = states.filter((item) => stateTone(item.state) === 'warn').length;
    return {
      states: states.length,
      open: openCount,
      warn: warnCount,
      events: data?.events.items.length || 0,
      quotaWindows: data?.quotaWindows.items.length || 0,
      probeEvents: data?.probeEvents.items.length || 0,
      slaReadiness: data?.slaReadiness.items.length || 0,
    };
  }, [data]);

  const operatorMetrics = useMemo(() => {
    const blockedState = summary.open
      ? `${summary.open} 个熔断打开`
      : summary.warn
        ? `${summary.warn} 个降级观察`
        : '未发现阻断';
    const productionCallState = isLoading && !data
      ? '读取中'
      : summary.open
        ? '部分生产调用应暂缓'
        : summary.warn
          ? '可继续但需观察降级'
          : '可继续观察';
    return [
      {
        label: '页面用途',
        value: '定位 provider 熔断风险',
        subvalue: 'SLA、熔断、配额与探测集中查看',
        tone: 'info' as Tone,
      },
      {
        label: '当前状态',
        value: productionCallState,
        subvalue: '只读判断，不改变 provider fallback 或 MarketCache',
        tone: summary.open ? 'danger' as Tone : summary.warn ? 'warn' as Tone : 'good' as Tone,
      },
      {
        label: '当前阻断',
        value: blockedState,
        subvalue: `${summary.warn} 个降级观察 · ${summary.states} 个状态快照`,
        tone: summary.open ? 'danger' as Tone : summary.warn ? 'warn' as Tone : 'good' as Tone,
      },
      {
        label: '下一步',
        value: summary.open || summary.warn ? '先核对凭证与当前熔断' : '保持观察，必要时展开诊断细节',
        subvalue: '事件、配额、探测细节默认后置',
        tone: summary.open || summary.warn ? 'warn' as Tone : 'neutral' as Tone,
      },
      {
        label: '需关注',
        value: `${summary.open} 打开 / ${summary.warn} 降级`,
        subvalue: '优先看熔断状态与凭证边界',
        tone: summary.open ? 'danger' as Tone : summary.warn ? 'warn' as Tone : 'good' as Tone,
      },
      {
        label: '就绪度',
        value: `${summary.slaReadiness} 个 SLA`,
        subvalue: `${summary.probeEvents} 个探测事件`,
        tone: 'info' as Tone,
      },
      {
        label: '诊断范围',
        value: `${summary.events} 事件 / ${summary.quotaWindows} 配额窗口`,
        subvalue: '二级细节默认折叠',
        tone: 'neutral' as Tone,
      },
    ];
  }, [data, isLoading, summary]);

  if (!canReadProviders) {
    return null;
  }

  return (
    <div data-testid="admin-provider-circuit-diagnostics-page" className="admin-provider-circuit-page flex min-h-0 w-full flex-1 overflow-y-auto no-scrollbar text-white">
      <TerminalPageShell className="flex min-h-0 flex-1 py-5 md:py-6">
        <TerminalPanel as="section" className="relative overflow-hidden">
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/50 to-transparent" />
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0 flex-1">
              <TerminalPageHeading eyebrow="生产调用门禁" title="Provider 熔断诊断" />
              <p className="mt-3 max-w-4xl text-sm leading-6 text-white/54">
                {isLoading
                  ? '正在读取只读诊断快照'
                  : `先判断生产调用是否可继续、哪里被阻断、是否缺凭证；事件、配额与探测细节默认折叠。生成 ${safeDate(data?.states.generatedAt)} · 只读观测`}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <TerminalChip variant="info">只读诊断</TerminalChip>
              <TerminalChip variant={data?.states.metadata?.noExternalCalls === true ? 'success' : 'caution'}>
                {data?.states.metadata?.noExternalCalls === true ? '不触发外部调用' : '外部调用状态待确认'}
              </TerminalChip>
              <TerminalChip variant={data?.states.metadata?.liveEnforcement === false ? 'success' : 'caution'}>
                {data?.states.metadata?.liveEnforcement === false ? '不执行熔断门禁' : '熔断门禁状态待确认'}
              </TerminalChip>
            </div>
          </div>
          {error ? <ApiErrorAlert error={error} className="mt-5" /> : null}
        </TerminalPanel>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7">
          {operatorMetrics.map((metric) => (
            <TerminalMetric
              key={metric.label}
              label={metric.label}
              value={metric.value}
              subvalue={metric.subvalue}
              valueClassName={cn('text-sm leading-5 md:text-base', METRIC_VALUE_CLASS_BY_TONE[metric.tone])}
            />
          ))}
        </div>

        <TerminalNotice variant="info">
          当前为诊断观测，不会改变 provider fallback 或 MarketCache 行为。
        </TerminalNotice>

        {isLoading && !data && !error ? <LoadingState /> : null}

        <TerminalGrid>
          <div className="col-span-12 xl:col-span-8">
            <CurrentStatesPanel items={data?.states.items || []} />
          </div>
          <div className="col-span-12 xl:col-span-4">
            <BoundaryPanel data={data} />
          </div>
          <SlaReadinessPanel items={data?.slaReadiness.items || []} />
        </TerminalGrid>

        <TerminalNestedBlock data-terminal-primitive="disclosure" className="px-2.5 py-2">
          <div className="flex min-w-0 items-center justify-between gap-2">
            <div className="min-w-0">
              <h2 className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">二级细节：探测、事件、配额窗口、路由 bucket</h2>
              <p className="mt-0.5 truncate text-[11px] text-white/38">默认折叠</p>
            </div>
            <TerminalButton
              variant="compact"
              className="shrink-0 px-2 py-1 text-[11px] text-white/58 hover:text-white"
              aria-expanded={secondaryDetailsOpen}
              aria-label={`${secondaryDetailsOpen ? '收起' : '展开'} 二级细节：探测、事件、配额窗口、路由 bucket`}
              onClick={() => setSecondaryDetailsOpen((current) => !current)}
            >
              {secondaryDetailsOpen ? '收起' : '展开'}
            </TerminalButton>
          </div>
          {secondaryDetailsOpen ? (
            <div className="mt-3 grid grid-cols-1 gap-5 xl:grid-cols-12">
              <div className="min-w-0 xl:col-span-4">
                <ProbeEventsPanel items={data?.probeEvents.items || []} />
              </div>
              <div className="min-w-0 xl:col-span-4">
                <EventsPanel items={data?.events.items || []} />
              </div>
              <div className="min-w-0 xl:col-span-4">
                <QuotaWindowsPanel items={data?.quotaWindows.items || []} />
              </div>
            </div>
          ) : null}
        </TerminalNestedBlock>
      </TerminalPageShell>
      <span className="sr-only">Provider 熔断诊断只读页面</span>
    </div>
  );
};

export default AdminProviderCircuitDiagnosticsPage;
