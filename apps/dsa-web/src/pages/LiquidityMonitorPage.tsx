import type React from 'react';
import { useEffect, useState } from 'react';
import { Activity, Gauge, Waves } from 'lucide-react';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import {
  liquidityMonitorApi,
  type LiquidityMonitorFreshness,
  type LiquidityMonitorIndicator,
  type LiquidityImpulseSynthesis,
  type LiquidityImpulseSynthesisEvidenceItem,
  type LiquidityMonitorRegime,
  type LiquidityMonitorResponse,
} from '../api/liquidityMonitor';
import { ApiErrorAlert } from '../components/common';
import {
  LiquidityImpulseSynthesisHeader,
  type LiquidityImpulseHeaderEvidenceView,
  type LiquidityImpulseSynthesisHeaderView,
} from '../components/liquidity-monitor/LiquidityImpulseSynthesisHeader';
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
import {
  OfficialMacroAuthorityDiagnostics,
  buildOfficialMacroAuthorityDiagnosticsView,
} from '../components/common/OfficialMacroAuthorityDiagnostics';
import { formatDateTime, formatPercent, formatSignedNumber } from '../utils/format';
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

const IMPULSE_LABELS: Record<string, string> = {
  expanding_liquidity: '流动性扩张',
  contracting_liquidity: '流动性收缩',
  balanced_liquidity: '流动性均衡',
  data_insufficient: '数据不足',
};

const SUBTYPE_LABELS: Record<string, string> = {
  broad_liquidity_expansion: '广谱流动性扩张',
  crypto_beta_expansion: 'Crypto Beta 扩张',
  rates_driven_tightening: '利率驱动收紧',
  dollar_driven_tightening: '美元驱动收紧',
  risk_deleveraging: '风险去杠杆',
  data_insufficient: '数据不足',
};

const CONFIDENCE_LABELS: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
  insufficient: '不足',
};

const PILLAR_LABELS: Record<string, string> = {
  rates_pressure: '利率压力',
  dollar_pressure: '美元压力',
  volatility_stress: '波动率压力',
  crypto_liquidity_beta: 'Crypto Beta',
  risk_asset_demand: '风险资产需求',
  funding_stress: '资金费率压力',
  equity_flow_proxy: '权益流向代理',
  breadth_confirmation: '市场宽度确认',
  china_liquidity_context: '中国流动性环境',
};

const EVIDENCE_DIRECTION_LABELS: Record<string, string> = {
  supports_expansion: '支持扩张',
  supports_contraction: '支持收缩',
  positive: '正向',
  negative: '负向',
  contradicts_expansion: '反向于扩张',
  contradicts_contraction: '反向于收缩',
};

const EVIDENCE_REASON_LABELS: Record<string, string> = {
  conflicts_with_primary_regime: '与主结论冲突',
  missing_direction_or_magnitude: '缺少方向或幅度',
  score_contribution_not_allowed: '当前不允许计分',
  observation_only_discount: '仅观察，不升格结论',
  freshness_discount: '时效折价',
  source_tier_discount: '来源层级折价',
  provider_unavailable: '数据源不可用',
  fallback_source: '仅备用来源',
};

function titleCaseFromSnake(value?: string | null): string {
  if (!value) return '待确认';
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function impulseCodeLabel(value?: string | null): string {
  if (!value) return '待确认';
  return IMPULSE_LABELS[value] || titleCaseFromSnake(value);
}

function subtypeLabel(value?: string | null): string {
  if (!value) return '待确认';
  return SUBTYPE_LABELS[value] || titleCaseFromSnake(value);
}

function synthesisConfidenceLabel(label?: string | null, confidence?: number | null): string {
  if (label && CONFIDENCE_LABELS[label]) {
    return CONFIDENCE_LABELS[label];
  }
  if (typeof confidence === 'number') {
    if (confidence >= 0.75) return '高';
    if (confidence >= 0.45) return '中';
    if (confidence > 0) return '低';
  }
  return '未返回';
}

function pillarLabel(value?: string | null): string {
  if (!value) return '待确认';
  return PILLAR_LABELS[value] || titleCaseFromSnake(value);
}

function evidenceDirectionLabel(value?: string | null): string | null {
  if (!value) return null;
  return EVIDENCE_DIRECTION_LABELS[value] || titleCaseFromSnake(value);
}

function evidenceReasonLabel(value?: string | null): string | null {
  if (!value) return null;
  return EVIDENCE_REASON_LABELS[value] || titleCaseFromSnake(value);
}

function evidenceItemDisplayLabel(item: LiquidityImpulseSynthesisEvidenceItem): string {
  return item.label || pillarLabel(item.pillar) || titleCaseFromSnake(item.key);
}

function buildEvidenceMeta(
  item: LiquidityImpulseSynthesisEvidenceItem,
  kind: 'driver' | 'counter' | 'gap',
): string {
  const parts: string[] = [];
  parts.push(pillarLabel(item.pillar));

  if (kind === 'driver') {
    const direction = evidenceDirectionLabel(item.direction);
    if (direction) parts.push(direction);
    if (typeof item.impact === 'number') parts.push(`影响 ${formatSignedNumber(item.impact, 2)}`);
    if (typeof item.signal === 'number') parts.push(`信号 ${formatSignedNumber(item.signal, 2)}`);
  } else if (kind === 'counter') {
    const reason = evidenceReasonLabel(item.reason);
    if (reason) parts.push(reason);
    if (typeof item.signal === 'number') parts.push(`信号 ${formatSignedNumber(item.signal, 2)}`);
  } else {
    const reason = evidenceReasonLabel(item.reason);
    if (reason) parts.push(reason);
    if (item.degradationReason) parts.push(titleCaseFromSnake(item.degradationReason));
  }

  if (item.source) parts.push(item.source);
  if (item.observationOnly) parts.push('观察-only');
  if (item.proxyOnly) parts.push('proxy-only');
  if (item.scoreContributionAllowed === false) parts.push('不计分');

  return parts.filter(Boolean).join(' · ');
}

function buildEvidenceView(
  items: LiquidityImpulseSynthesisEvidenceItem[],
  kind: 'driver' | 'counter' | 'gap',
  limit: number,
): LiquidityImpulseHeaderEvidenceView[] {
  return items.slice(0, limit).map((item) => ({
    key: item.key,
    label: evidenceItemDisplayLabel(item),
    meta: buildEvidenceMeta(item, kind),
  }));
}

function buildLiquidityImpulseSynthesisView(
  synthesis: LiquidityImpulseSynthesis | undefined,
): LiquidityImpulseSynthesisHeaderView {
  if (!synthesis) {
    return {
      state: 'missing',
      title: '流动性方向待返回',
      summary: '当前流动性监测载荷未返回 liquidityImpulseSynthesis，不推断扩张或收缩。',
      stateChipLabel: '载荷缺失',
      stateChipVariant: 'neutral',
      confidenceLabel: '未返回',
      confidenceValueText: '',
      dominantDrivers: [],
      counterEvidence: [],
      dataGaps: [],
      notInvestmentAdvice: false,
    };
  }

  const evidenceQuality = synthesis.evidenceQuality || {};
  const scoringEvidenceCount = typeof evidenceQuality.scoringEvidenceCount === 'number'
    ? evidenceQuality.scoringEvidenceCount
    : synthesis.dominantDrivers.length;
  const scoringPillarCount = typeof evidenceQuality.scoringPillarCount === 'number'
    ? evidenceQuality.scoringPillarCount
    : undefined;
  const discountedEvidenceCount = typeof evidenceQuality.discountedEvidenceCount === 'number'
    ? evidenceQuality.discountedEvidenceCount
    : undefined;
  const dataGapCount = typeof evidenceQuality.dataGapCount === 'number'
    ? evidenceQuality.dataGapCount
    : synthesis.dataGaps.length;
  const realScoringEvidenceCount = typeof evidenceQuality.realScoringEvidenceCount === 'number'
    ? evidenceQuality.realScoringEvidenceCount
    : undefined;
  const allScoringEvidenceProxyOnly = evidenceQuality.allScoringEvidenceProxyOnly === true;
  const proxyOnlyScoringCount = typeof evidenceQuality.proxyOnlyScoringCount === 'number'
    ? evidenceQuality.proxyOnlyScoringCount
    : 0;
  const lowConfidence = (
    synthesis.liquidityImpulse === 'data_insufficient'
    || synthesis.confidenceLabel === 'insufficient'
    || synthesis.confidenceLabel === 'low'
    || synthesis.confidence < 0.45
  );
  const proxyOnlyDecision = Boolean(
    allScoringEvidenceProxyOnly
    || (proxyOnlyScoringCount > 0 && (realScoringEvidenceCount == null || realScoringEvidenceCount <= 0))
  );
  const promotable = !lowConfidence && !proxyOnlyDecision;
  const qualityFlags = [
    `证据 ${scoringEvidenceCount}`,
    scoringPillarCount != null ? `支柱 ${scoringPillarCount}` : '',
    discountedEvidenceCount != null ? `折价 ${discountedEvidenceCount}` : '',
    `缺口 ${dataGapCount}`,
    proxyOnlyDecision ? 'proxy-only' : '',
  ].filter(Boolean).join(' · ');
  const contradictionCount = Math.min(synthesis.counterEvidence.length, 3);
  const gapCount = Math.min(dataGapCount, 3);

  return {
    state: promotable ? 'ready' : 'insufficient',
    title: promotable
      ? impulseCodeLabel(synthesis.liquidityImpulse)
      : synthesis.liquidityImpulse === 'data_insufficient'
        ? '流动性方向数据不足'
        : '流动性方向待确认',
    summary: promotable
      ? (synthesis.narrativeBullets[0]
        || `主驱动 ${Math.min(synthesis.dominantDrivers.length, 3)} 项 · 反证 ${contradictionCount} 项 · 缺口 ${gapCount} 项`)
      : proxyOnlyDecision
        ? `后端返回“${synthesis.impulseLabel}”，但当前可计分证据为 proxy-only，前端不升级为真实扩张或收缩结论。`
        : synthesis.liquidityImpulse === 'data_insufficient'
          ? (synthesis.narrativeBullets[0] || '当前可用证据不足，只展示缺口与残余信号。')
          : `后端返回“${synthesis.impulseLabel}”，但当前置信度不足，只展示支持证据、反证与数据缺口。`,
    stateChipLabel: promotable
      ? '主结论'
      : synthesis.liquidityImpulse === 'data_insufficient'
        ? '数据不足'
        : proxyOnlyDecision
          ? 'Proxy-only'
          : '低置信度',
    stateChipVariant: promotable ? 'success' : 'caution',
    impulseLabel: synthesis.impulseLabel,
    subtypeLabel: subtypeLabel(synthesis.subtype),
    confidenceLabel: synthesisConfidenceLabel(synthesis.confidenceLabel, synthesis.confidence),
    confidenceValueText: formatPercent(synthesis.confidence, { mode: 'ratio' }),
    directionScoreText: formatSignedNumber(synthesis.directionScore, 2, { showZeroSign: true }),
    qualityLine: qualityFlags,
    dominantDrivers: buildEvidenceView(synthesis.dominantDrivers, 'driver', 3),
    counterEvidence: buildEvidenceView(synthesis.counterEvidence, 'counter', 3),
    dataGaps: buildEvidenceView(synthesis.dataGaps, 'gap', 3),
    notInvestmentAdvice: Boolean(synthesis.notInvestmentAdvice),
  };
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
  const synthesisView = buildLiquidityImpulseSynthesisView(data?.liquidityImpulseSynthesis);
  const officialMacroDiagnostics = buildOfficialMacroAuthorityDiagnosticsView(
    indicators.flatMap((indicator) => (
      indicator.evidence?.inputs?.map((input) => ({
        key: `${indicator.key}:${input.officialSeriesId || input.key}`,
        label: input.label,
        sourceLabel: input.sourceLabel,
        sourceTier: input.sourceTier,
        trustLevel: input.trustLevel,
        freshness: input.freshness,
        asOf: input.asOf,
        isFallback: input.isFallback,
        isUnavailable: input.isUnavailable,
        isPartial: input.isPartial,
        observationOnly: input.observationOnly,
        sourceAuthorityAllowed: input.sourceAuthorityAllowed,
        scoreContributionAllowed: input.scoreContributionAllowed,
        sourceAuthorityReason: input.sourceAuthorityReason,
        sourceAuthorityRouteRejected: input.sourceAuthorityRouteRejected,
        routeRejectedReasonCodes: input.routeRejectedReasonCodes,
        officialSeriesId: input.officialSeriesId,
        officialObservationDate: input.officialObservationDate,
        officialAsOf: input.officialAsOf,
      })) || []
    )),
  );

  return (
    <WideWorkspacePageShell className="flex min-h-0 flex-1 py-5 md:py-6">
      <TerminalPageHeading
        eyebrow="流动性"
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
          <TerminalSectionHeader eyebrow="快照" title="读取中" />
        </TerminalPanel>
      ) : null}

      {data ? (
        <TerminalGrid>
          <div className="flex flex-col gap-4 xl:col-span-8">
            <LiquidityImpulseSynthesisHeader view={synthesisView} />

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
                      <p className="mt-2 text-sm text-white/48">{REGIME_LABELS[data.score.regime]}</p>
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
            <OfficialMacroAuthorityDiagnostics
              testId="liquidity-monitor-official-macro-diagnostics"
              title="Authority diagnostics"
              view={officialMacroDiagnostics}
            />

            <TerminalPanel>
              <TerminalSectionHeader eyebrow="选中指标" title="指标细节" action={<Waves className="h-4 w-4 text-white/28" aria-hidden="true" />} />
              {selectedIndicator ? (
                <div className="mt-4 grid grid-cols-1 gap-3">
                  <TerminalMetric label="当前指标" value={displayLabel(selectedIndicator)} valueClassName="text-sm font-sans leading-6" />
                  <TerminalMetric label="状态" value={statusLabel(selectedIndicator.status)} valueClassName="text-lg font-sans" />
                  <TerminalMetric label="评分贡献" value={contributionLabel(selectedIndicator)} valueClassName="text-lg font-sans" />
                  <TerminalMetric label="更新时间" value={formatDateTime(selectedIndicator.updatedAt) || '待确认'} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="备注" value={detailReason(selectedIndicator)} valueClassName="text-sm font-sans leading-6" />
                </div>
              ) : (
                <p className="mt-4 text-sm text-white/45">当前没有可展示的指标。</p>
              )}
            </TerminalPanel>

            <TerminalPanel
              data-testid="liquidity-monitor-source-disclosure"
            >
              <TerminalSectionHeader
                eyebrow="来源"
                title="数据状态"
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
                  <TerminalMetric label="外部调用" value={data.sourceMetadata.externalProviderCalls ? '已发生' : '未发生'} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="运行顺序" value={data.sourceMetadata.providerRuntimeChanged ? '已变更' : '未变更'} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="缓存写入" value={data.sourceMetadata.marketCacheMutation ? '已发生' : '未发生'} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="最弱时效" value={FRESHNESS_LABELS[data.freshness.weakestIndicatorFreshness]} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="最新时间" value={formatDateTime(data.freshness.latestAsOf) || '待确认'} valueClassName="text-sm font-sans" />
                  <TerminalMetric label="当前判断" value={data.score.regime === 'unavailable' ? '数据不足' : '仅观察'} valueClassName="text-sm font-sans leading-6" />
                </div>
              ) : null}
            </TerminalPanel>

            <TerminalPanel>
              <TerminalSectionHeader eyebrow="边界" title="约束" action={<Activity className="h-4 w-4 text-white/28" aria-hidden="true" />} />
              <p className="mt-3 text-sm leading-6 text-white/52">
                只读快照，不触发扫描、回测或组合动作，也不把 fallback 包装成实时结论。
              </p>
            </TerminalPanel>
          </div>
        </TerminalGrid>
      ) : null}
    </WideWorkspacePageShell>
  );
};

export default LiquidityMonitorPage;
