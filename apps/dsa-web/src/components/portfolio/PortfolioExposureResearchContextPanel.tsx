import { TerminalChip, TerminalNestedBlock } from '../terminal/TerminalPrimitives';
import type { PortfolioLineageSummary, PortfolioLineageStatusSummary } from '../../api/portfolio';
import type {
  PortfolioExposureResearchContext,
  PortfolioRiskExposureReadiness,
  PortfolioRiskExposureReadinessItem,
} from '../../types/portfolio';

type PortfolioExposureResearchContextPanelProps = {
  context?: PortfolioExposureResearchContext | null;
  lineageSummary?: PortfolioLineageSummary | null;
  language: 'zh' | 'en';
};

type ChipVariant = 'neutral' | 'success' | 'caution' | 'danger' | 'info';

const INTERNAL_TERM_PATTERN = /\b(provider|cache|debug|backend|raw|json|schema|trace|broker|admin)\b|sourceauthority|reasoncode/i;

function safeText(value: string | null | undefined, replacement: string): string {
  const trimmed = String(value || '').trim();
  if (!trimmed || INTERNAL_TERM_PATTERN.test(trimmed) || /[a-z]+_[a-z0-9_]+/i.test(trimmed)) {
    return replacement;
  }
  return trimmed;
}

function formatPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`;
}

function marketLabel(value: string | null | undefined, language: 'zh' | 'en'): string | null {
  const token = String(value || '').trim().toLowerCase();
  if (!token) return null;
  if (token === 'cn' || token === 'a' || token === 'ashare' || token === 'a-share') {
    return language === 'zh' ? 'A股' : 'China A-share';
  }
  if (token === 'hk' || token === 'hkg') {
    return language === 'zh' ? '港股' : 'Hong Kong';
  }
  if (token === 'us' || token === 'usa') {
    return language === 'zh' ? '美股' : 'United States';
  }
  if (token === 'global') {
    return language === 'zh' ? '全球' : 'Global';
  }
  return safeText(value, language === 'zh' ? '市场待确认' : 'Market pending');
}

function stateLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  const token = String(value || '').trim().toLowerCase();
  if (token === 'observable' || token === 'ready' || token === 'current') {
    return language === 'zh' ? '可用于观察' : 'Ready for observation';
  }
  if (token === 'elevated') {
    return language === 'zh' ? '集中度较高' : 'Elevated concentration';
  }
  if (token === 'limited' || token === 'partial' || token === 'stale') {
    return language === 'zh' ? '依据需复核' : 'Needs evidence review';
  }
  if (token === 'unavailable' || token === 'missing') {
    return language === 'zh' ? '数据暂不可用' : 'Data unavailable';
  }
  return language === 'zh' ? '证据待确认' : 'Evidence pending';
}

function chipVariantForState(value: string | null | undefined): ChipVariant {
  const token = String(value || '').trim().toLowerCase();
  if (token === 'observable' || token === 'ready' || token === 'current') return 'success';
  if (token === 'elevated' || token === 'limited' || token === 'partial' || token === 'stale') return 'caution';
  if (token === 'unavailable' || token === 'missing') return 'danger';
  return 'neutral';
}

function fxStateLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  const token = String(value || '').trim().toLowerCase();
  if (token === 'current' || token === 'fresh' || token === 'live' || token === 'ready') {
    return language === 'zh' ? '汇率已更新' : 'Exchange rates current';
  }
  if (token === 'stale' || token === 'expired') {
    return language === 'zh' ? '汇率可能延迟' : 'Exchange rates may be delayed';
  }
  if (token === 'unavailable' || token === 'missing') {
    return language === 'zh' ? '汇率暂不可用' : 'Exchange rates unavailable';
  }
  return language === 'zh' ? '汇率待确认' : 'Exchange rates pending';
}

function evidenceGapLabel(value: string, language: 'zh' | 'en'): string | null {
  const token = value.trim().toLowerCase();
  const labels: Record<string, { zh: string; en: string }> = {
    portfolio_account: { zh: '组合账户证据待补充', en: 'Portfolio account evidence pending' },
    portfolio_positions: { zh: '持仓证据待补充', en: 'Holding evidence pending' },
    valuation_inputs: { zh: '估值输入需复核', en: 'Valuation inputs need review' },
    freshness: { zh: '数据新鲜度需复核', en: 'Freshness needs review' },
    fx_freshness: { zh: '汇率新鲜度需复核', en: 'Exchange-rate freshness needs review' },
    position_lineage: { zh: '持仓来源待核验', en: 'Holding lineage pending' },
    cash_ledger: { zh: '资金流水待核验', en: 'Funding records pending' },
    benchmark_mapping: { zh: '比较参考待映射', en: 'Comparative reference pending' },
    factor_mapping: { zh: '因子参考待映射', en: 'Factor reference pending' },
    portfolio_metrics: { zh: '组合指标待补充', en: 'Portfolio metrics pending' },
  };
  const known = labels[token];
  if (known) return known[language];
  return safeText(value, '') || null;
}

function staleInputLabel(value: string, language: 'zh' | 'en'): string {
  const token = value.trim().toLowerCase();
  const labels: Record<string, { zh: string; en: string }> = {
    portfolio_snapshot: { zh: '组合快照', en: 'Portfolio snapshot' },
    portfolio_metrics: { zh: '组合指标', en: 'Portfolio metrics' },
    fx_freshness: { zh: '汇率新鲜度', en: 'Exchange-rate freshness' },
    portfolio_account: { zh: '组合账户', en: 'Portfolio account' },
    portfolio_positions: { zh: '持仓证据', en: 'Holding evidence' },
    valuation_inputs: { zh: '估值输入', en: 'Valuation inputs' },
    freshness: { zh: '数据新鲜度', en: 'Data freshness' },
    position_lineage: { zh: '持仓来源', en: 'Holding lineage' },
    cash_ledger: { zh: '资金流水', en: 'Funding records' },
    benchmark_mapping: { zh: '比较参考', en: 'Comparative reference' },
    factor_mapping: { zh: '因子参考', en: 'Factor reference' },
    calculation: { zh: '指标计算', en: 'Metric calculation' },
  };
  const known = labels[token];
  return known ? known[language] : safeText(value, language === 'zh' ? '输入待确认' : 'Input pending');
}

function nextStepLabel(topic: string, dominantSymbol: string | null | undefined, language: 'zh' | 'en'): string {
  const symbol = safeText(dominantSymbol, '').toUpperCase();
  const token = topic.trim().toLowerCase();
  if (token === 'dominant_exposure') {
    return language === 'zh'
      ? `${symbol ? `${symbol}：` : ''}复核主导暴露对应的研究证据与市场背景`
      : `${symbol ? `${symbol}: ` : ''}Review research evidence and market context for the dominant exposure`;
  }
  if (token === 'comparative_context') {
    return language === 'zh'
      ? '补齐比较参考与因子证据后，再扩展横向研究解释'
      : 'Map comparative references and factor evidence before expanding cross-market context';
  }
  if (token === 'currency_context') {
    return language === 'zh'
      ? '核对汇率与估值新鲜度，再阅读币种汇总背景'
      : 'Check exchange-rate and valuation freshness before interpreting currency context';
  }
  if (token === 'evidence_quality') {
    return language === 'zh'
      ? '先核对受限输入，再扩展研究结论'
      : 'Review limited inputs before expanding research conclusions';
  }
  return language === 'zh'
    ? '结合市场状态、行业背景和数据新鲜度阅读快照'
    : 'Read the snapshot alongside market state, sector context, and data freshness';
}

function statusDetail(item: PortfolioLineageStatusSummary): string {
  return item.total > 0 || item.count > 0 ? item.detail : '--';
}

function readinessStateLabel(item: PortfolioRiskExposureReadinessItem | undefined, language: 'zh' | 'en'): string {
  const token = String(item?.state || '').trim().toLowerCase();
  const labels: Record<string, { zh: string; en: string }> = {
    available: { zh: '可用', en: 'Available' },
    missing: { zh: '缺少证据', en: 'Missing evidence' },
    stale: { zh: '可能过期', en: 'May be stale' },
    not_configured: { zh: '未配置', en: 'Not configured' },
    broker_disabled: { zh: '连接已停用', en: 'Connection disabled' },
    manual_only: { zh: '仅手动记录', en: 'Manual records only' },
  };
  return labels[token]?.[language] ?? (language === 'zh' ? '待确认' : 'Pending');
}

function readinessVariant(item: PortfolioRiskExposureReadinessItem | undefined): ChipVariant {
  const token = String(item?.state || '').trim().toLowerCase();
  if (token === 'available') return 'success';
  if (token === 'manual_only') return 'info';
  if (token === 'stale' || token === 'not_configured') return 'caution';
  if (token === 'missing' || token === 'broker_disabled') return 'danger';
  return 'neutral';
}

function readinessCategoryLabel(key: string, language: 'zh' | 'en'): string {
  const labels: Record<string, { zh: string; en: string }> = {
    holdings: { zh: '持仓', en: 'Holdings' },
    sectorExposure: { zh: '行业暴露', en: 'Sector exposure' },
    singleNameConcentration: { zh: '单名集中度', en: 'Single-name concentration' },
    currencyExposure: { zh: '币种暴露', en: 'Currency exposure' },
    factorStyleExposure: { zh: '因子 / 风格', en: 'Factor / style' },
    liquidityVolatilityExposure: { zh: '流动性 / 波动', en: 'Liquidity / volatility' },
    benchmarkComparison: { zh: '基准比较', en: 'Benchmark comparison' },
  };
  return labels[key]?.[language] ?? key;
}

function readinessSummary(readiness: PortfolioRiskExposureReadiness, language: 'zh' | 'en'): string {
  if (readiness.benchmarkAvailability.state === 'not_configured') {
    return language === 'zh'
      ? '比较基准待配置，横向观察保持受限。'
      : 'Benchmark comparison is not configured, so cross-reference observation remains limited.';
  }
  if (readiness.holdings.state === 'missing') {
    return language === 'zh'
      ? '持仓证据缺失，暴露视图暂不生成。'
      : 'Holding evidence is missing, so exposure views are not generated.';
  }
  return language === 'zh'
    ? '只展示暴露就绪状态，不生成交易建议。'
    : 'Shows exposure readiness only; no trading guidance is generated.';
}

export function PortfolioRiskExposureReadinessPanel({
  readiness,
  language,
}: {
  readiness?: PortfolioRiskExposureReadiness | null;
  language: 'zh' | 'en';
}) {
  if (!readiness) {
    return null;
  }

  const rows = [
    { key: 'holdings', item: readiness.holdings },
    { key: 'sectorExposure', item: readiness.exposureCategories.sectorExposure },
    { key: 'singleNameConcentration', item: readiness.exposureCategories.singleNameConcentration },
    { key: 'currencyExposure', item: readiness.exposureCategories.currencyExposure },
    { key: 'factorStyleExposure', item: readiness.exposureCategories.factorStyleExposure },
    { key: 'liquidityVolatilityExposure', item: readiness.exposureCategories.liquidityVolatilityExposure },
    { key: 'benchmarkComparison', item: readiness.exposureCategories.benchmarkComparison },
  ];

  return (
    <TerminalNestedBlock data-testid="portfolio-risk-exposure-readiness" className="p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-white/40">
            {language === 'zh' ? '风险暴露就绪度' : 'Risk exposure readiness'}
          </h3>
          <p className="mt-1 text-xs leading-5 text-white/52">{readinessSummary(readiness, language)}</p>
        </div>
        <TerminalChip variant="info">{language === 'zh' ? '仅供观察' : 'Observation only'}</TerminalChip>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {rows.map(({ key, item }) => (
          <div key={key} className="min-w-0 rounded-lg border border-white/[0.03] bg-black/20 p-3">
            <div className="truncate text-[10px] font-bold uppercase tracking-widest text-white/35">
              {readinessCategoryLabel(key, language)}
            </div>
            <div className="mt-2">
              <TerminalChip variant={readinessVariant(item)}>{readinessStateLabel(item, language)}</TerminalChip>
            </div>
          </div>
        ))}
      </div>
    </TerminalNestedBlock>
  );
}

export function PortfolioExposureResearchContextPanel({
  context,
  lineageSummary,
  language,
}: PortfolioExposureResearchContextPanelProps) {
  if (!context) {
    return null;
  }

  const dominant = context.dominantExposure;
  const dominantLabel = safeText(
    dominant.label || dominant.symbol || dominant.currency || dominant.market,
    language === 'zh' ? '主导暴露待确认' : 'Dominant exposure pending',
  );
  const dominantMeta = [
    marketLabel(dominant.market, language),
    safeText(dominant.currency, ''),
  ].filter(Boolean).join(' / ');
  const concentrationState = stateLabel(context.concentrationContext.state, language);
  const currencyState = stateLabel(context.currencyContext.state, language);
  const marketState = stateLabel(context.marketContext.state, language);
  const largestCurrency = context.currencyContext.largestCurrency;
  const largestMarket = context.marketContext.largestMarket;
  const evidenceGaps = context.evidenceGaps
    .map((item) => evidenceGapLabel(item, language))
    .filter((item): item is string => Boolean(item))
    .slice(0, 4);
  const staleInputs = context.staleInputs.slice(0, 4);
  const researchNextSteps = context.researchNextSteps.slice(0, 3);
  const boundaryMessage = language === 'zh'
    ? '仅供观察，不改动账务或组合数据'
    : 'Observation only; no accounting or portfolio data is changed';

  const summaryText = language === 'zh'
    ? `${dominantLabel} · ${concentrationState}`
    : `${dominantLabel} · ${concentrationState}`;
  const lineageItems = lineageSummary?.hasLineage
    ? [
      { key: 'price', item: lineageSummary.price },
      { key: 'fx', item: lineageSummary.fx },
      { key: 'snapshot', item: lineageSummary.snapshot },
      { key: 'analytics', item: lineageSummary.analytics },
    ]
    : [];

  return (
    <TerminalNestedBlock data-testid="portfolio-exposure-research-context" className="p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-[10px] font-bold uppercase tracking-widest text-white/40">
            {language === 'zh' ? '暴露研究背景' : 'Exposure research context'}
          </h3>
          <p className="mt-1 text-xs leading-5 text-white/52">{summaryText}</p>
        </div>
        <TerminalChip variant="info">
          {language === 'zh' ? '仅供观察' : 'Observation only'}
        </TerminalChip>
      </div>

      {lineageItems.length ? (
        <div data-testid="portfolio-exposure-lineage-summary" className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {lineageItems.map(({ key, item }) => (
            <div key={key} className="min-w-0 rounded-lg border border-white/[0.03] bg-black/20 p-3">
              <div className="flex min-w-0 items-center justify-between gap-2">
                <div className="truncate text-[10px] font-bold uppercase tracking-widest text-white/35">{item.label}</div>
                <TerminalChip variant={item.variant}>{item.label}</TerminalChip>
              </div>
              <div className="mt-2 truncate text-xs text-white/48">{statusDetail(item)}</div>
            </div>
          ))}
        </div>
      ) : null}

      <div data-testid="portfolio-exposure-research-context-grid" className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div className="rounded-lg border border-white/[0.03] bg-black/20 p-3">
          <div className="text-[10px] font-bold uppercase tracking-widest text-white/35">
            {language === 'zh' ? '主导暴露' : 'Dominant exposure'}
          </div>
          <div className="mt-2 truncate text-sm text-white">{dominantLabel}</div>
          <div className="mt-1 text-xs text-white/45">
            {[dominantMeta, formatPercent(dominant.weightPct)].filter(Boolean).join(' · ')}
          </div>
        </div>
        <div className="rounded-lg border border-white/[0.03] bg-black/20 p-3">
          <div className="text-[10px] font-bold uppercase tracking-widest text-white/35">
            {language === 'zh' ? '集中度背景' : 'Concentration context'}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <TerminalChip variant={chipVariantForState(context.concentrationContext.state)}>{concentrationState}</TerminalChip>
          </div>
          <div className="mt-2 text-xs text-white/45">
            {language === 'zh' ? '最高权重' : 'Top weight'} {formatPercent(context.concentrationContext.topWeightPct)}
          </div>
        </div>
        <div className="rounded-lg border border-white/[0.03] bg-black/20 p-3">
          <div className="text-[10px] font-bold uppercase tracking-widest text-white/35">
            {language === 'zh' ? '币种背景' : 'Currency context'}
          </div>
          <div className="mt-2 text-sm text-white">
            {safeText(largestCurrency?.label || largestCurrency?.currency || context.currencyContext.baseCurrency, language === 'zh' ? '币种待确认' : 'Currency pending')}
          </div>
          <div className="mt-1 text-xs text-white/45">
            {fxStateLabel(context.currencyContext.fxFreshnessState, language)}
            {' · '}
            {currencyState}
          </div>
        </div>
        <div className="rounded-lg border border-white/[0.03] bg-black/20 p-3">
          <div className="text-[10px] font-bold uppercase tracking-widest text-white/35">
            {language === 'zh' ? '市场背景' : 'Market context'}
          </div>
          <div className="mt-2 text-sm text-white">
            {marketLabel(largestMarket?.market, language) || safeText(largestMarket?.label, '') || (language === 'zh' ? '市场待确认' : 'Market pending')}
          </div>
          <div className="mt-1 text-xs text-white/45">
            {marketState}
            {' · '}
            {formatPercent(largestMarket?.weightPct)}
          </div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2 lg:grid-cols-3">
        <div data-testid="portfolio-exposure-research-stale-inputs" className="rounded-lg border border-white/[0.03] bg-black/20 p-3">
          <div className="text-[10px] font-bold uppercase tracking-widest text-white/35">
            {language === 'zh' ? '输入新鲜度' : 'Input freshness'}
          </div>
          {staleInputs.length ? (
            <ul className="mt-2 space-y-1 text-xs leading-5 text-white/48">
              {staleInputs.map((item) => (
                <li key={`${item.input}-${item.status || 'pending'}`}>
                  {staleInputLabel(item.input, language)}
                  {' · '}
                  {stateLabel(item.status, language)}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-xs leading-5 text-white/48">
              {language === 'zh' ? '当前未返回陈旧输入。' : 'No stale inputs returned.'}
            </p>
          )}
        </div>
        <div data-testid="portfolio-exposure-research-evidence-gaps" className="rounded-lg border border-white/[0.03] bg-black/20 p-3">
          <div className="text-[10px] font-bold uppercase tracking-widest text-white/35">
            {language === 'zh' ? '证据缺口' : 'Evidence gaps'}
          </div>
          {evidenceGaps.length ? (
            <ul className="mt-2 space-y-1 text-xs leading-5 text-white/48">
              {evidenceGaps.map((item) => <li key={item}>{item}</li>)}
            </ul>
          ) : (
            <p className="mt-2 text-xs leading-5 text-white/48">
              {language === 'zh' ? '当前未返回额外证据缺口。' : 'No additional evidence gaps returned.'}
            </p>
          )}
        </div>
        <div data-testid="portfolio-exposure-research-next-steps" className="rounded-lg border border-white/[0.03] bg-black/20 p-3">
          <div className="text-[10px] font-bold uppercase tracking-widest text-white/35">
            {language === 'zh' ? '研究后续' : 'Research next steps'}
          </div>
          {researchNextSteps.length ? (
            <ul className="mt-2 space-y-1 text-xs leading-5 text-white/48">
              {researchNextSteps.map((item) => (
                <li key={item.topic}>{nextStepLabel(item.topic, dominant.symbol, language)}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-xs leading-5 text-white/48">
              {language === 'zh' ? '下一步研究线索待补充。' : 'Next research cues pending.'}
            </p>
          )}
        </div>
      </div>

      <div data-testid="portfolio-exposure-research-boundary" className="mt-3 rounded-lg border border-cyan-300/15 bg-cyan-300/[0.03] p-3 text-xs leading-5 text-cyan-100/75">
        {context.observationBoundary.observationOnly === false || context.observationBoundary.decisionGrade === true
          ? (language === 'zh' ? '观察边界待确认。' : 'Observation boundary pending.')
          : boundaryMessage}
      </div>
    </TerminalNestedBlock>
  );
}
