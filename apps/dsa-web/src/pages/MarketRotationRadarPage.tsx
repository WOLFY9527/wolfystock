import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Gauge, RefreshCcw, Signal, Waves } from 'lucide-react';
import { ApiErrorAlert, GlassCard } from '../components/common';
import { DataFreshnessBadge } from '../components/market-overview/marketOverviewPrimitives';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { marketRotationApi, type MarketRotationRadarResponse, type MarketRotationRiskLabel, type MarketRotationStage, type MarketRotationSummaryItem, type MarketRotationTheme, type MarketRotationTimeWindow } from '../api/marketRotation';
import { cn } from '../utils/cn';

const STAGE_LABELS: Record<MarketRotationStage, string> = {
  early_rotation: '早期扩散',
  confirmed_rotation: '确认轮动',
  crowded_or_extended: '拥挤/延展',
  cooling: '降温',
  weak_or_no_signal: '信号较弱',
};

const RISK_LABELS: Record<MarketRotationRiskLabel, string> = {
  gap_fade_risk: '高开回落风险',
  thin_breadth: '广度偏薄',
  single_name_driven: '单一龙头驱动',
  stale_data: '数据过期',
  fallback_data: '备用数据',
};

function scoreTone(score: number): string {
  if (score >= 75) {
    return 'text-emerald-300 drop-shadow-[0_0_10px_rgba(52,211,153,0.34)]';
  }
  if (score >= 60) {
    return 'text-cyan-200 drop-shadow-[0_0_10px_rgba(103,232,249,0.24)]';
  }
  if (score >= 45) {
    return 'text-amber-200';
  }
  return 'text-white/45';
}

function percent(value?: number | null, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return 'N/A';
  }
  return `${value.toFixed(digits)}%`;
}

function signedPercent(value?: number | null, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return 'N/A';
  }
  return `${value >= 0 ? '+' : ''}${value.toFixed(digits)}%`;
}

function ratio(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return 'N/A';
  }
  return `${value.toFixed(2)}x`;
}

function compactConfidence(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '0%';
  }
  return `${Math.round(value * 100)}%`;
}

function summaryTitle(items: MarketRotationSummaryItem[], fallback: string): string {
  return items.length ? items.map((item) => item.name).join(' / ') : fallback;
}

const SummaryCell: React.FC<{
  title: string;
  value: string;
  accent?: string;
  children?: React.ReactNode;
}> = ({ title, value, accent = 'text-white', children }) => (
  <div className="min-w-0 rounded-xl border border-white/5 bg-white/[0.025] px-3 py-3">
    <p className="truncate text-[10px] font-bold uppercase tracking-widest text-white/38">{title}</p>
    <p className={cn('mt-2 truncate text-sm font-semibold', accent)}>{value}</p>
    {children ? <div className="mt-2 min-w-0 text-[11px] leading-5 text-white/45">{children}</div> : null}
  </div>
);

const ThemeMetric: React.FC<{ label: string; value: string; tone?: string }> = ({ label, value, tone = 'text-white/78' }) => (
  <div className="min-w-0 rounded-lg border border-white/[0.04] bg-black/20 px-3 py-2">
    <p className="truncate text-[10px] font-semibold text-white/38">{label}</p>
    <p className={cn('mt-1 truncate font-mono text-sm font-semibold tabular-nums', tone)}>{value}</p>
  </div>
);

const WindowChip: React.FC<{ window: MarketRotationTimeWindow }> = ({ window }) => (
  <div className="min-w-0 rounded-lg border border-white/[0.04] bg-black/20 px-3 py-2">
    <p className="truncate text-[10px] font-semibold text-white/38">{window.label}</p>
    <p className={cn('mt-1 truncate text-[11px] font-semibold', window.available ? 'text-cyan-100' : 'text-white/35')}>
      {window.available ? signedPercent(window.changePercent, 1) : '数据待补齐'}
    </p>
    <p className="mt-1 truncate text-[10px] text-white/35">{window.sourceLabel || window.freshness}</p>
  </div>
);

const WatchlistMemberRow: React.FC<{ member: {
  symbol?: string;
  name?: string;
  roleLabel?: string;
  freshnessLabel?: string;
  changePercent?: number | null;
  relativeStrengthVsBenchmark?: number | null;
  observed?: boolean;
}; }> = ({ member }) => (
  <div className="flex min-w-0 items-center justify-between gap-3 rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2">
    <span className="min-w-0">
      <span className="block truncate text-sm font-semibold text-white/82">{member.symbol || '--'}</span>
      <span className="block truncate text-[11px] text-white/38">{member.roleLabel || '观察成员'} · {member.freshnessLabel || '待补齐'}</span>
    </span>
    <span className="shrink-0 text-right text-[11px] text-white/50">
      <span className="block font-mono text-sm text-cyan-100">{signedPercent(member.relativeStrengthVsBenchmark ?? member.changePercent)}</span>
      <span className="block">{member.observed ? '已观察' : '待补齐'}</span>
    </span>
  </div>
);

const RiskChip: React.FC<{ risk: MarketRotationRiskLabel }> = ({ risk }) => (
  <span
    className="inline-flex items-center rounded-full border border-amber-300/20 bg-amber-300/10 px-2 py-0.5 text-[10px] font-semibold text-amber-100"
    title={risk}
  >
    {RISK_LABELS[risk] || '风险待识别'}
  </span>
);

const ThemeCard: React.FC<{
  theme: MarketRotationTheme;
  selected: boolean;
  onSelect: () => void;
}> = ({ theme, selected, onSelect }) => {
  const relativeStrength = theme.relativeStrength?.averageRelativeStrengthPercent;
  const volumeRatio = theme.volume?.averageRelativeVolume;
  return (
    <article
      data-testid={`rotation-theme-card-${theme.id}`}
      className={cn(
        'rounded-2xl border bg-white/[0.02] p-4 backdrop-blur-md transition-all hover:border-white/12 hover:bg-white/[0.035]',
        selected ? 'border-cyan-200/24 shadow-[0_0_24px_rgba(103,232,249,0.10)]' : 'border-white/5',
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        className="group flex w-full min-w-0 items-start justify-between gap-3 text-left"
      >
        <span className="min-w-0">
          <span className="flex min-w-0 items-center gap-2">
            <span className="truncate text-base font-semibold text-white">{theme.name}</span>
            <DataFreshnessBadge freshness={theme.freshness} />
          </span>
          <span className="mt-1 block truncate text-[11px] text-white/42">{theme.englishName} · {theme.focus || theme.benchmark}</span>
        </span>
        <span className="shrink-0 text-right">
          <span className={cn('block font-mono text-3xl font-semibold leading-none tabular-nums', scoreTone(theme.rotationScore))}>
            {theme.rotationScore}
          </span>
          <span className="mt-1 block text-[10px] font-bold uppercase tracking-widest text-white/35">轮动强度</span>
        </span>
      </button>

      <div className="mt-4 grid min-w-0 grid-cols-2 gap-2 md:grid-cols-4">
        <ThemeMetric label="相对强弱" value={signedPercent(relativeStrength)} tone={Number(relativeStrength) >= 0 ? 'text-emerald-200' : 'text-rose-300'} />
        <ThemeMetric label="成交额扩张" value={ratio(volumeRatio)} tone={Number(volumeRatio) >= 1.1 ? 'text-cyan-200' : 'text-white/58'} />
        <ThemeMetric label="上涨广度" value={percent(theme.breadth?.percentUp)} />
        <ThemeMetric label="同步性" value={percent(theme.synchronization?.sameDirectionPercent)} />
      </div>

      <div className="mt-3 flex min-w-0 flex-wrap items-center gap-2 text-[11px] text-white/45">
        <span className="rounded-full border border-white/8 bg-white/[0.03] px-2 py-0.5">{STAGE_LABELS[theme.stage] || theme.stage}</span>
        <span className="rounded-full border border-white/8 bg-white/[0.03] px-2 py-0.5">置信度 {compactConfidence(theme.confidence)}</span>
        {theme.newslessRotation ? (
          <span className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-2 py-0.5 text-cyan-100">无明显新闻的同步异动</span>
        ) : null}
      </div>

      <div className="mt-3 flex min-w-0 flex-wrap items-center gap-1.5" aria-label="风险标签">
        <span className="text-[10px] font-bold uppercase tracking-widest text-white/35">风险标签</span>
        {theme.riskLabels.length ? theme.riskLabels.map((risk) => <RiskChip key={risk} risk={risk} />) : (
          <span className="inline-flex rounded-full border border-emerald-300/20 bg-emerald-300/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-100">风险标签：暂无高亮</span>
        )}
      </div>

      {theme.evidence.length ? (
        <div className="mt-3 grid gap-1 text-[11px] leading-5 text-white/48">
          {theme.evidence.slice(0, 3).map((item) => (
            <p key={item} className="truncate">· {item}</p>
          ))}
        </div>
      ) : null}

      {theme.stageExplanation ? (
        <p className="mt-3 rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2 text-[11px] leading-5 text-white/50">
          {theme.stageExplanation}
        </p>
      ) : null}

      {theme.riskExplanations?.length ? (
        <div className="mt-2 grid gap-1 text-[11px] leading-5 text-white/44">
          {theme.riskExplanations.slice(0, 2).map((item) => (
            <p key={item} className="truncate">· {item}</p>
          ))}
        </div>
      ) : null}

      {theme.timeWindows ? (
        <div className="mt-4">
          <p className="text-[10px] font-bold uppercase tracking-widest text-white/35">时窗证据</p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {(['5m', '15m', '60m', '1d'] as const).map((window) => (
              <WindowChip key={window} window={theme.timeWindows?.[window] || {
                window,
                label: window,
                available: false,
                freshness: 'fallback',
                isFallback: true,
                isStale: false,
                sourceLabel: '窗口数据待补齐',
                reason: 'window_unavailable',
              }} />
            ))}
          </div>
        </div>
      ) : null}

      {theme.benchmarkProxies ? (
        <div className="mt-4">
          <p className="text-[10px] font-bold uppercase tracking-widest text-white/35">代理基准</p>
          <div className="mt-2 grid gap-2">
            {Object.values(theme.benchmarkProxies).map((proxy) => (
              <div key={proxy.symbol} className="flex min-w-0 items-center justify-between gap-3 rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2">
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-white/82">{proxy.symbol}</span>
                  <span className="block truncate text-[11px] text-white/38">{proxy.role === 'sector_proxy' ? '行业代理' : '市场代理'} · {proxy.sourceLabel || '备用数据'}</span>
                </span>
                <span className="shrink-0 text-right text-[11px] text-white/50">
                  <span className="block font-mono text-sm text-cyan-100">{signedPercent(proxy.relativeStrength)}</span>
                  <span className="block">{proxy.freshness || 'fallback'}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </article>
  );
};

const ThemeDetailPanel: React.FC<{ theme?: MarketRotationTheme }> = ({ theme }) => {
  if (!theme) {
    return null;
  }
  const vsBenchmarks = theme.relativeStrength?.vsBenchmarks || {};
  const leaders = theme.leadership?.topMembers || [];
  return (
    <GlassCard as="aside" data-testid="rotation-theme-detail-panel" className="p-4 md:p-5">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-widest text-white/35">主题详情</p>
          <h2 className="mt-1 truncate text-lg font-semibold text-white">{theme.name}</h2>
        </div>
        <DataFreshnessBadge freshness={theme.freshness} />
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        {['QQQ', 'SPY', 'IWM'].map((symbol) => (
          <ThemeMetric
            key={symbol}
            label={`相对 ${symbol}`}
            value={signedPercent(vsBenchmarks[symbol])}
            tone={Number(vsBenchmarks[symbol]) >= 0 ? 'text-emerald-200' : 'text-rose-300'}
          />
        ))}
      </div>

      <div className="mt-5">
        <p className="text-[10px] font-bold uppercase tracking-widest text-white/35">主导股票</p>
        <div className="mt-2 grid gap-2">
          {leaders.length ? leaders.map((leader) => (
            <div key={leader.symbol} className="flex min-w-0 items-center justify-between gap-3 rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2">
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold text-white/82">{leader.symbol}</span>
                <span className="block truncate text-[11px] text-white/38">{leader.name || leader.symbol}</span>
              </span>
              <span className="shrink-0 text-right font-mono text-sm text-emerald-200">{signedPercent(leader.changePercent)}</span>
            </div>
          )) : (
            <p className="rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2 text-sm text-white/45">主导股票待实时快照补齐</p>
          )}
        </div>
      </div>

      <div className="mt-5">
        <p className="text-[10px] font-bold uppercase tracking-widest text-white/35">扩散结构</p>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <ThemeMetric label="覆盖率" value={percent(theme.breadth?.coveragePercent)} />
          <ThemeMetric label="跑赢基准" value={percent(theme.breadth?.percentOutperformingBenchmark)} />
          <ThemeMetric label="VWAP 强度" value={percent(theme.synchronization?.aboveVwapPercent)} />
          <ThemeMetric label="龙头集中度" value={percent(theme.leadership?.leadershipConcentrationPercent)} />
        </div>
      </div>

      <div className="mt-5">
        <p className="text-[10px] font-bold uppercase tracking-widest text-white/35">数据新鲜度</p>
        <p className="mt-2 rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2 text-[11px] leading-5 text-white/50">
          {theme.sourceLabel || theme.source || '主题篮子计算'} · {theme.asOf || theme.updatedAt || '时间待补齐'}
        </p>
      </div>

      {theme.themeDetail ? (
        <div className="mt-5">
          <p className="text-[10px] font-bold uppercase tracking-widest text-white/35">{theme.themeDetail.watchlistLabel || '观察清单'}</p>
          <p className="mt-2 rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2 text-[11px] leading-5 text-white/50">
            {theme.themeDetail.safeActionLabel || '仅观察，不构成买卖建议'}
          </p>
          <div className="mt-3 grid gap-2">
            {(theme.themeDetail.leadershipMembers || []).map((member) => (
              <WatchlistMemberRow key={`${member.symbol || 'leader'}-${member.roleLabel || 'leader'}`} member={member} />
            ))}
            {(theme.themeDetail.laggardMembers || []).length ? (
              <div className="rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2">
                <p className="text-[10px] font-bold uppercase tracking-widest text-white/35">落后成员</p>
                <div className="mt-2 grid gap-2">
                  {(theme.themeDetail.laggardMembers || []).map((member) => (
                    <WatchlistMemberRow key={`${member.symbol || 'laggard'}-${member.roleLabel || 'laggard'}`} member={member} />
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </GlassCard>
  );
};

const LoadingPanel: React.FC = () => (
  <GlassCard as="section" className="p-5" role="status" aria-label="正在读取资金轮动雷达">
    <div className="flex items-center gap-3 text-white/60">
      <RefreshCcw className="h-4 w-4 animate-spin" aria-hidden="true" />
      <span className="text-sm">正在读取资金轮动雷达...</span>
    </div>
  </GlassCard>
);

const MarketRotationRadarPage: React.FC = () => {
  const [payload, setPayload] = useState<MarketRotationRadarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [selectedThemeId, setSelectedThemeId] = useState<string>('');

  const loadRadar = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const nextPayload = await marketRotationApi.getRotationRadar();
      setPayload(nextPayload);
      setSelectedThemeId((current) => current || nextPayload.themes[0]?.id || '');
    } catch (nextError) {
      setError({ ...getParsedApiError(nextError), title: '读取资金轮动雷达失败' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRadar();
  }, [loadRadar]);

  const selectedTheme = useMemo(
    () => payload?.themes.find((theme) => theme.id === selectedThemeId) || payload?.themes[0],
    [payload, selectedThemeId],
  );

  const developerSnapshot = useMemo(() => {
    if (!payload) {
      return '{}';
    }
    return JSON.stringify({
      endpoint: payload.endpoint,
      generatedAt: payload.generatedAt,
      source: payload.source,
      freshness: payload.freshness,
      metadata: payload.metadata,
      themeIds: payload.themes.map((theme) => theme.id),
      noAdviceDisclosure: payload.noAdviceDisclosure,
    }, null, 2);
  }, [payload]);

  return (
    <div
      data-testid="market-rotation-radar-page"
      className="bento-surface-root flex min-h-0 w-full flex-1 flex-col overflow-y-auto no-scrollbar bg-[#050505] px-4 py-5 text-white md:px-6 xl:px-8"
    >
      <GlassCard as="section" className="relative shrink-0 overflow-hidden p-5 md:p-6">
        <div className="relative z-10 flex min-w-0 flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-cyan-200/55">Market Rotation Radar</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-normal text-white md:text-3xl">资金轮动雷达</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/50">
              观察主题级资金轮动迹象、成交额扩张、相对强势扩散与板块同步性增强。{payload?.noAdviceDisclosure || '非买卖建议。'}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <div data-testid="rotation-radar-freshness" className="inline-flex items-center gap-2 rounded-xl border border-white/8 bg-black/20 px-3 py-2">
              <span className="text-[10px] font-bold uppercase tracking-widest text-white/35">数据新鲜度</span>
              <DataFreshnessBadge freshness={payload?.freshness || 'fallback'} />
            </div>
            <button
              type="button"
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-white/50 transition-all hover:bg-white/10 hover:text-white disabled:cursor-wait disabled:text-white/30"
              onClick={() => void loadRadar()}
              disabled={loading}
              aria-label="刷新资金轮动雷达"
            >
              <RefreshCcw className={cn('h-4 w-4', loading ? 'animate-spin' : '')} aria-hidden="true" />
            </button>
          </div>
        </div>
      </GlassCard>

      {error ? (
        <GlassCard as="section" className="mt-4 p-5">
          <ApiErrorAlert error={error} />
        </GlassCard>
      ) : null}

      {loading && !payload ? (
        <div className="mt-4">
          <LoadingPanel />
        </div>
      ) : null}

      {payload ? (
        <>
          {payload.warning ? (
            <div className="mt-4 flex items-start gap-2 rounded-xl border border-amber-300/15 bg-amber-300/10 px-4 py-3 text-sm leading-6 text-amber-100/80">
              <AlertTriangle className="mt-1 h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{payload.warning}</span>
            </div>
          ) : null}

          <section data-testid="rotation-radar-summary-band" className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
            <SummaryCell
              title="今日轮动主题"
              value={summaryTitle(payload.summary.strongestThemes, '等待真实行情')}
              accent="text-emerald-200"
            >
              <span>最强主题按轮动强度和置信度排序。</span>
            </SummaryCell>
            <SummaryCell
              title="扩张主题"
              value={summaryTitle(payload.summary.acceleratingThemes, '暂无扩张确认')}
              accent="text-cyan-200"
            >
              <span>成交额扩张与相对强势扩散同时出现时列入。</span>
            </SummaryCell>
            <SummaryCell
              title="降温/弱信号"
              value={summaryTitle(payload.summary.fadingThemes, '暂无降温列表')}
              accent="text-amber-200"
            >
              <span>备用、过期、薄广度或低同步性会降低置信度。</span>
            </SummaryCell>
          </section>

          <div className="mt-4 grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-12 xl:items-start">
            <section className="min-w-0 space-y-3 xl:col-span-8" aria-label="今日轮动主题 Top list">
              <div className="grid grid-cols-1 gap-3">
                {payload.themes.map((theme) => (
                  <ThemeCard
                    key={theme.id}
                    theme={theme}
                    selected={selectedTheme?.id === theme.id}
                    onSelect={() => setSelectedThemeId(theme.id)}
                  />
                ))}
              </div>
            </section>

            <div className="min-w-0 xl:col-span-4">
              <ThemeDetailPanel theme={selectedTheme} />
            </div>
          </div>

          <GlassCard as="section" className="mt-4 p-4 md:p-5">
            <div className="flex min-w-0 flex-wrap items-center gap-2 text-[11px] text-white/46">
              <Gauge className="h-4 w-4 text-cyan-200/70" aria-hidden="true" />
              <span>轮动强度 = 相对强弱 + 成交额/相对量 + 广度 + 同步性 + VWAP + 持续性，并对备用、过期、薄广度降权。</span>
              <Signal className="ml-2 h-4 w-4 text-emerald-200/70" aria-hidden="true" />
              <span>无新闻轮动旗标是保守证据，不代表因果确认。</span>
              <Waves className="ml-2 h-4 w-4 text-white/40" aria-hidden="true" />
              <span>{payload.noAdviceDisclosure}</span>
            </div>
          </GlassCard>

          <details
            data-testid="rotation-radar-developer-details"
            className="mt-4 rounded-2xl border border-white/5 bg-white/[0.02] p-4 text-sm text-white/55"
          >
            <summary className="cursor-pointer list-none text-[11px] font-bold uppercase tracking-widest text-white/42">
              开发者详情
            </summary>
            <pre className="mt-3 max-h-72 overflow-y-auto no-scrollbar whitespace-pre-wrap break-words rounded-xl border border-white/[0.04] bg-black/20 p-3 text-[11px] leading-5 text-white/45">
              {developerSnapshot}
            </pre>
          </details>
        </>
      ) : null}
    </div>
  );
};

export default MarketRotationRadarPage;
