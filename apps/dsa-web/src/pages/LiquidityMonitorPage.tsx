import type React from 'react';
import { useEffect, useState } from 'react';
import { Activity, Gauge, Waves } from 'lucide-react';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import {
  liquidityMonitorApi,
  type LiquidityMonitorFreshness,
  type LiquidityMonitorIndicator,
  type LiquidityMonitorRegime,
  type LiquidityMonitorResponse,
} from '../api/liquidityMonitor';
import { ApiErrorAlert } from '../components/common';
import {
  TerminalButton,
  TerminalChip,
  TerminalDenseTable,
  TerminalGrid,
  TerminalMetric,
  TerminalNotice,
  TerminalPageHeading,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal';
import { WideWorkspacePageShell } from '../components/layout/WideWorkspaceShell';
import { formatDateTime } from '../utils/format';
import { cn } from '../utils/cn';

const REGIME_LABELS: Record<LiquidityMonitorRegime, string> = {
  abundant: '充裕',
  supportive: '支撑',
  neutral: '中性',
  tight: '偏紧',
  stress: '紧张',
  unavailable: '不可用',
};

const REGIME_TONE: Record<LiquidityMonitorRegime, string> = {
  abundant: 'text-emerald-300',
  supportive: 'text-cyan-200',
  neutral: 'text-white/78',
  tight: 'text-amber-200',
  stress: 'text-rose-300',
  unavailable: 'text-white/38',
};

const FRESHNESS_LABELS: Record<LiquidityMonitorFreshness, string> = {
  live: '实时',
  cached: '缓存',
  delayed: '延迟',
  stale: '过期',
  fallback: '备用',
  mock: '备用',
  error: '异常',
  unavailable: '不可用',
};

const INDICATOR_LABEL_OVERRIDES: Record<string, string> = {
  crypto_funding: 'Crypto 资金费率',
};

function statusLabel(status: LiquidityMonitorIndicator['status']): string {
  if (status === 'live') return '实时';
  if (status === 'partial') return '部分可用';
  return '暂不可用';
}

function chipVariantForStatus(status: LiquidityMonitorIndicator['status']): 'neutral' | 'success' | 'caution' | 'info' {
  if (status === 'live') return 'success';
  if (status === 'partial') return 'info';
  return 'neutral';
}

function chipVariantForFreshness(freshness: LiquidityMonitorFreshness): 'neutral' | 'success' | 'caution' | 'danger' | 'info' {
  if (freshness === 'live') return 'success';
  if (freshness === 'cached' || freshness === 'delayed') return 'info';
  if (freshness === 'stale' || freshness === 'fallback' || freshness === 'mock') return 'caution';
  if (freshness === 'error') return 'danger';
  return 'neutral';
}

function scoreLabel(value: number): string {
  return Number.isFinite(value) ? String(Math.round(value)) : '--';
}

function confidenceLabel(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return '0%';
  return `${Math.round(value * 100)}%`;
}

function contributionLabel(indicator: LiquidityMonitorIndicator): string {
  const value = Number(indicator.scoreContribution || 0);
  if (!indicator.includedInScore) {
    return '不计分';
  }
  if (value === 0) {
    return '0';
  }
  return value > 0 ? `+${value}` : String(value);
}

function detailReason(indicator: LiquidityMonitorIndicator): string {
  return indicator.summary || '当前没有额外说明。';
}

function displayLabel(indicator: LiquidityMonitorIndicator): string {
  return INDICATOR_LABEL_OVERRIDES[indicator.key] || indicator.label;
}

const LiquidityMonitorPage: React.FC = () => {
  const [data, setData] = useState<LiquidityMonitorResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [sourceDetailsOpen, setSourceDetailsOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const payload = await liquidityMonitorApi.getLiquidityMonitor();
        if (cancelled) return;
        setData(payload);
        const preferred = payload.indicators.find((item) => item.includedInScore) || payload.indicators[0] || null;
        setSelectedKey(preferred?.key || null);
      } catch (loadError) {
        if (cancelled) return;
        setError(getParsedApiError(loadError));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  const indicators = data?.indicators || [];
  const selectedIndicator = indicators.find((item) => item.key === selectedKey) || indicators[0] || null;

  return (
    <WideWorkspacePageShell className="flex min-h-0 flex-1 py-5 md:py-6">
      <TerminalPageHeading
        eyebrow="市场流动性观察"
        title="流动性监测"
        action={
          <TerminalChip variant={data ? chipVariantForFreshness(data.freshness.status) : 'neutral'}>
            {data ? FRESHNESS_LABELS[data.freshness.status] : '加载中'}
          </TerminalChip>
        }
      />

      <TerminalNotice variant="info">
        {data?.advisoryDisclosure || '仅用于观察市场流动性环境，非买卖建议，不触发扫描、回测或组合动作。'}
      </TerminalNotice>

      {error ? <ApiErrorAlert error={error} /> : null}

      {loading && !data ? (
        <TerminalPanel>
          <TerminalSectionHeader eyebrow="只读监测" title="正在读取缓存 / 快照" />
          <p className="mt-3 text-sm text-white/55">当前页面只读取已有市场缓存与持久快照，不会触发额外行情调用。</p>
        </TerminalPanel>
      ) : null}

      {data ? (
        <TerminalGrid>
          <div className="flex flex-col gap-4 xl:col-span-8">
            <TerminalPanel>
              <TerminalSectionHeader
                eyebrow="环境刻度"
                title="流动性环境分数"
                action={<TerminalChip variant={chipVariantForStatus(data.score.regime === 'unavailable' ? 'unavailable' : 'live')}>{REGIME_LABELS[data.score.regime]}</TerminalChip>}
              />
              <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-white/[0.04] bg-black/20 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[10px] uppercase tracking-widest text-white/35">分数</p>
                      <p className={cn('mt-2 font-mono text-5xl tracking-tight', REGIME_TONE[data.score.regime])}>{scoreLabel(data.score.value)}</p>
                      <p className="mt-2 text-sm text-white/48">{REGIME_LABELS[data.score.regime]} · 仅观察</p>
                    </div>
                    <Gauge className="h-8 w-8 text-white/28" aria-hidden="true" />
                  </div>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <TerminalMetric label="置信度" value={confidenceLabel(data.score.confidence)} valueClassName="text-2xl" />
                  <TerminalMetric label="最弱时效" value={FRESHNESS_LABELS[data.freshness.weakestIndicatorFreshness]} valueClassName="text-lg font-sans" />
                  <TerminalMetric label="计分指标" value={data.score.includedIndicatorCount} valueClassName="text-2xl" />
                  <TerminalMetric label="计分权重" value={`${data.score.includedIndicatorWeight} / ${data.score.possibleIndicatorWeight}`} valueClassName="text-lg font-sans" />
                </div>
              </div>
            </TerminalPanel>

            <TerminalPanel>
              <TerminalSectionHeader eyebrow="核心引擎" title="判断框架" />
              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                <TerminalMetric label="风险偏好" value={data.score.value >= 56 ? '改善' : data.score.value <= 44 ? '受压' : '中性'} valueClassName="text-lg font-sans" />
                <TerminalMetric label="最新时间" value={formatDateTime(data.freshness.latestAsOf) || '待确认'} valueClassName="text-sm font-sans" />
                <TerminalMetric label="评分状态" value={data.score.regime === 'unavailable' ? '数据不足' : '已输出'} valueClassName="text-lg font-sans" />
              </div>
            </TerminalPanel>

            <TerminalPanel>
              <TerminalSectionHeader eyebrow="指标矩阵" title="Phase 1 监测条目" />
              <TerminalDenseTable className="mt-4">
                <table className="w-full min-w-[760px] border-collapse text-left">
                  <thead className="border-b border-white/5 text-[10px] uppercase tracking-widest text-white/35">
                    <tr>
                      <th className="px-3 py-2">指标</th>
                      <th className="px-3 py-2">状态</th>
                      <th className="px-3 py-2">时效</th>
                      <th className="px-3 py-2">贡献</th>
                      <th className="px-3 py-2">说明</th>
                    </tr>
                  </thead>
                  <tbody>
                    {indicators.map((indicator) => {
                      const active = indicator.key === selectedIndicator?.key;
                      return (
                        <tr
                          key={indicator.key}
                          className={cn(
                            'cursor-pointer border-b border-white/[0.04] align-top transition-colors hover:bg-white/[0.02]',
                            active ? 'bg-white/[0.03]' : '',
                          )}
                          onClick={() => setSelectedKey(indicator.key)}
                        >
                          <td className="px-3 py-2.5 text-sm text-white/80">{displayLabel(indicator)}</td>
                          <td className="px-3 py-2.5">
                            <TerminalChip variant={chipVariantForStatus(indicator.status)}>
                              {statusLabel(indicator.status)}
                            </TerminalChip>
                          </td>
                          <td className="px-3 py-2.5">
                            <TerminalChip variant={chipVariantForFreshness(indicator.freshness)}>
                              {FRESHNESS_LABELS[indicator.freshness]}
                            </TerminalChip>
                          </td>
                          <td className="px-3 py-2.5 font-mono text-white/72">{contributionLabel(indicator)}</td>
                          <td className="px-3 py-2.5 text-xs leading-5 text-white/48">{indicator.summary || '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </TerminalDenseTable>
            </TerminalPanel>
          </div>

          <div className="flex flex-col gap-4 xl:col-span-4">
            <TerminalPanel>
              <TerminalSectionHeader eyebrow="选中指标" title="指标细节" action={<Waves className="h-4 w-4 text-white/28" aria-hidden="true" />} />
              {selectedIndicator ? (
                <div className="mt-4 grid grid-cols-1 gap-3">
                  <TerminalMetric label="当前指标" value={displayLabel(selectedIndicator)} valueClassName="text-sm font-sans leading-6" />
                  <TerminalMetric label="状态" value={statusLabel(selectedIndicator.status)} valueClassName="text-lg font-sans" />
                  <TerminalMetric label="评分贡献" value={contributionLabel(selectedIndicator)} valueClassName="text-lg font-sans" />
                  <TerminalMetric label="更新时间" value={formatDateTime(selectedIndicator.updatedAt) || '待确认'} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="观测备注" value={detailReason(selectedIndicator)} valueClassName="text-sm font-sans leading-6" />
                </div>
              ) : (
                <p className="mt-4 text-sm text-white/45">当前没有可展示的指标。</p>
              )}
            </TerminalPanel>

            <TerminalPanel
              data-testid="liquidity-monitor-source-disclosure"
            >
              <TerminalSectionHeader
                eyebrow="数据源细节"
                title="缓存 / 快照说明"
                action={(
                  <TerminalButton
                    variant="compact"
                    aria-label={`${sourceDetailsOpen ? '收起' : '展开'} 数据源细节`}
                    onClick={() => setSourceDetailsOpen((current) => !current)}
                  >
                    {sourceDetailsOpen ? '收起' : '展开'}
                  </TerminalButton>
                )}
              />
              {sourceDetailsOpen ? (
                <div className="mt-4 grid grid-cols-1 gap-3">
                  <TerminalMetric label="外部行情调用" value={data.sourceMetadata.externalProviderCalls ? '已发生' : '未发生'} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="运行顺序变更" value={data.sourceMetadata.providerRuntimeChanged ? '已发生' : '未发生'} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="缓存写入" value={data.sourceMetadata.marketCacheMutation ? '已发生' : '未发生'} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="最弱时效" value={FRESHNESS_LABELS[data.freshness.weakestIndicatorFreshness]} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="最新时间" value={formatDateTime(data.freshness.latestAsOf) || '待确认'} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="当前判断" value={data.score.regime === 'unavailable' ? '数据不足，禁止扩展解释' : '仅观察市场流动性环境'} valueClassName="text-sm font-sans leading-6" />
                </div>
              ) : null}
            </TerminalPanel>

            <TerminalPanel>
              <TerminalSectionHeader eyebrow="边界确认" title="模块约束" action={<Activity className="h-4 w-4 text-white/28" aria-hidden="true" />} />
              <p className="mt-3 text-sm leading-6 text-white/52">
                当前模块只读取已有缓存 / 快照，不触发扫描、回测或组合动作，也不会把 fallback 数据包装成实时结论。
              </p>
            </TerminalPanel>
          </div>
        </TerminalGrid>
      ) : null}
    </WideWorkspacePageShell>
  );
};

export default LiquidityMonitorPage;
