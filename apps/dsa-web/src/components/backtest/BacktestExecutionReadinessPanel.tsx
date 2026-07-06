import type React from 'react';
import { AlertTriangle, CheckCircle2, CircleDashed, ShieldCheck, XCircle } from 'lucide-react';
import type { BacktestExecutionReadiness, BacktestHistoricalOhlcvReadiness } from '../../types/backtest';
import type { ProductReadModel } from '../../types/productReadModel';
import ProductReadModelStatusStrip from '../common/ProductReadModelStatusStrip';
import { productReadModelIsBlocking, productReadStateLabel } from '../../utils/productReadModelView';

type BacktestLanguage = 'zh' | 'en';

type BacktestExecutionReadinessPanelProps = {
  language: BacktestLanguage;
  readiness?: BacktestExecutionReadiness | null;
  historicalOhlcvReadiness?: BacktestHistoricalOhlcvReadiness | null;
  productReadModel?: ProductReadModel | null;
  noAdviceDisclosure?: string | null;
  attempted?: boolean;
  isLoading?: boolean;
  className?: string;
  testId?: string;
};

type ReadinessTone = 'ready' | 'warning' | 'blocked' | 'neutral';

const STATE_LABELS: Record<string, { zh: string; en: string; tone: ReadinessTone }> = {
  engine_disabled: { zh: '回测引擎已关闭', en: 'Backtest engine disabled', tone: 'blocked' },
  data_disabled: { zh: '数据访问不可用', en: 'Data access unavailable', tone: 'blocked' },
  no_samples: { zh: '暂无可用样本', en: 'No usable samples', tone: 'blocked' },
  data_insufficient: { zh: '历史数据不足', en: 'Insufficient history', tone: 'blocked' },
  initializing: { zh: '正在准备历史样本', en: 'Preparing historical samples', tone: 'neutral' },
  samples_initializing: { zh: '正在准备历史样本', en: 'Preparing historical samples', tone: 'neutral' },
  degraded: { zh: '可执行，证据降级', en: 'Executable with degraded evidence', tone: 'warning' },
  executable: { zh: '可执行', en: 'Executable', tone: 'ready' },
  calculation_unavailable: { zh: '等待执行回执', en: 'Waiting for execution receipt', tone: 'neutral' },
  unknown: { zh: '等待就绪度', en: 'Waiting for readiness', tone: 'neutral' },
};

const REASON_LABELS: Record<string, { zh: string; en: string }> = {
  engine_disabled: { zh: '引擎开关关闭，未产生结果契约。', en: 'Engine switch is disabled, so no result contract was produced.' },
  provider_missing: { zh: '数据源未就绪，无法读取所需行情。', en: 'Data source is not ready for the required market data.' },
  entitlement_required: { zh: '数据授权不足，无法读取所需行情。', en: 'Data entitlement is missing for the required market data.' },
  samples_missing: { zh: '缺少已准备的分析样本。', en: 'Prepared analysis samples are missing.' },
  no_samples: { zh: '缺少已准备的分析样本。', en: 'Prepared analysis samples are missing.' },
  no_analysis_history: { zh: '没有可用于评估的历史分析记录。', en: 'No historical analysis records are available for evaluation.' },
  no_samples_prepared: { zh: '尚未准备历史评估样本。', en: 'Historical evaluation samples have not been prepared.' },
  samples_initializing: { zh: '历史样本正在准备，尚不能确认结果可用。', en: 'Historical samples are being prepared; result availability is not confirmed yet.' },
  insufficient_history: { zh: '历史价格数据窗口不足，无法计算安全结果。', en: 'The historical price window is too short to calculate a safe result.' },
  insufficient_data: { zh: '可用数据不足，未生成收益、回撤、胜率或基准相对指标。', en: 'Usable data is insufficient, so return, drawdown, win-rate, and benchmark-relative metrics are not ready.' },
  missing_benchmark: { zh: '缺少基准，基准相对指标不可用。', en: 'Benchmark is missing, so benchmark-relative metrics are unavailable.' },
  missing_adjustments: { zh: '复权/公司行动证据不足，结果只能观察。', en: 'Adjustment or corporate-action evidence is incomplete; result is observation-only.' },
  stale_data: { zh: '数据可能过期，结果只能观察。', en: 'Data may be stale; result is observation-only.' },
  missing_factor_inputs: { zh: '因子输入缺失，相关诊断不可用。', en: 'Factor inputs are missing; related diagnostics are unavailable.' },
  historical_ohlcv_not_configured: { zh: '历史价格数据运行时未配置。', en: 'Historical price data runtime is not configured.' },
  historical_ohlcv_stale: { zh: '历史价格数据覆盖可能过期。', en: 'Historical price data coverage may be stale.' },
  historical_ohlcv_insufficient_coverage: { zh: '请求区间的历史价格数据覆盖不足。', en: 'Historical price data coverage is insufficient for the requested range.' },
  historical_ohlcv_missing: { zh: '缺少必需的历史价格数据输入。', en: 'Required historical price data inputs are missing.' },
  historical_ohlcv_unavailable: { zh: '历史价格数据运行时不可用。', en: 'Historical price data runtime is unavailable.' },
};

const OHLCV_STATUS_LABELS: Record<string, { zh: string; en: string }> = {
  available: { zh: '历史价格数据可执行', en: 'Historical price data ready' },
  missing: { zh: '历史价格数据输入缺失', en: 'Historical price data inputs missing' },
  stale: { zh: '历史价格数据可能过期', en: 'Historical price data may be stale' },
  not_configured: { zh: '历史价格数据未配置', en: 'Historical price data not configured' },
  insufficient_coverage: { zh: '历史价格数据覆盖不足', en: 'Historical price data coverage insufficient' },
  unavailable: { zh: '历史价格数据不可用', en: 'Historical price data unavailable' },
};

const DATA_CLASS_LABELS: Record<string, { zh: string; en: string }> = {
  historical_ohlcv: { zh: '历史价格数据', en: 'Historical price data' },
  date_coverage: { zh: '日期覆盖', en: 'Date coverage' },
  freshness: { zh: '新鲜度', en: 'Freshness' },
  adjusted_prices: { zh: '复权价格', en: 'Adjusted prices' },
  benchmark_ohlcv: { zh: '基准历史价格数据', en: 'Benchmark historical price data' },
};

function normalizeToken(value?: string | null): string {
  return String(value || '').trim().toLowerCase().replaceAll('-', '_').replace(/\s+/g, '_');
}

function uniqueStrings(values?: string[] | null): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values || []) {
    const normalized = normalizeToken(value);
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    result.push(normalized);
  }
  return result;
}

function getStateInfo(readiness?: BacktestExecutionReadiness | null) {
  const state = normalizeToken(readiness?.state) || 'unknown';
  return STATE_LABELS[state] || STATE_LABELS.unknown;
}

function getReasonLabels(readiness: BacktestExecutionReadiness | null | undefined, language: BacktestLanguage): string[] {
  const reasons = uniqueStrings(readiness?.reasonCodes);
  const labels = reasons.map((reason) => REASON_LABELS[reason]?.[language]).filter((value): value is string => Boolean(value));

  const benchmarkState = normalizeToken(readiness?.benchmarkState);
  if ((benchmarkState === 'missing' || reasons.includes('missing_benchmark')) && !labels.includes(REASON_LABELS.missing_benchmark[language])) {
    labels.push(REASON_LABELS.missing_benchmark[language]);
  }

  if (!labels.length && readiness?.resultContractAvailable === false) {
    labels.push(language === 'en'
      ? 'The backend did not mark a safe result contract as available.'
      : '后端未标记可用的安全结果契约。');
  }

  return labels;
}

function toneClasses(tone: ReadinessTone): string {
  if (tone === 'ready') return 'border-emerald-400/20 bg-emerald-400/10 text-emerald-50';
  if (tone === 'warning') return 'border-amber-400/20 bg-amber-400/10 text-amber-50';
  if (tone === 'blocked') return 'border-rose-400/20 bg-rose-400/10 text-rose-50';
  return 'border-white/10 bg-white/[0.03] text-white/72';
}

function ToneIcon({ tone }: { tone: ReadinessTone }) {
  if (tone === 'ready') return <CheckCircle2 className="size-4 text-emerald-300" />;
  if (tone === 'warning') return <AlertTriangle className="size-4 text-amber-300" />;
  if (tone === 'blocked') return <XCircle className="size-4 text-rose-300" />;
  return <CircleDashed className="size-4 text-white/42" />;
}

function getHistoricalStatusLabel(readiness: BacktestHistoricalOhlcvReadiness | null | undefined, language: BacktestLanguage): string {
  const status = normalizeToken(readiness?.status) || 'unavailable';
  return OHLCV_STATUS_LABELS[status]?.[language] || OHLCV_STATUS_LABELS.unavailable[language];
}

function getHistoricalDataClassLabels(readiness: BacktestHistoricalOhlcvReadiness | null | undefined, language: BacktestLanguage): string {
  const labels = uniqueStrings(readiness?.missingDataClasses)
    .map((value) => DATA_CLASS_LABELS[value]?.[language])
    .filter((value): value is string => Boolean(value));
  return labels.length ? labels.join(' / ') : (language === 'en' ? 'None reported' : '未返回缺口');
}

function productReadModelShowsSampleInitialization(productReadModel?: ProductReadModel | null): boolean {
  const missingClasses = productReadModel?.quality?.missingDataClasses || [];
  const evidence = (productReadModel?.evidence || {}) as Record<string, unknown>;
  return missingClasses.some((value) => normalizeToken(value) === 'samples_initializing')
    || normalizeToken(String(evidence.transition || '')) === 'initializing';
}

function sanitizeHistoricalReadinessText(value: string | null | undefined, language: BacktestLanguage): string | null {
  const text = String(value || '').trim();
  if (!text) return null;
  if (/ohlcv|cache|seed|runtime/i.test(text)) {
    return language === 'en'
      ? 'Refresh or complete historical price data for this date range, then review readiness again.'
      : '请刷新或补齐本次区间的历史价格数据后，再复核就绪度。';
  }
  return text.replace(/OHLCV/g, language === 'en' ? 'historical price data' : '历史价格数据');
}

const BacktestExecutionReadinessPanel: React.FC<BacktestExecutionReadinessPanelProps> = ({
  language,
  readiness,
  historicalOhlcvReadiness,
  productReadModel,
  attempted = false,
  isLoading = false,
  className = '',
  testId = 'backtest-execution-readiness-panel',
}) => {
  const readinessState = normalizeToken(readiness?.state);
  const samplesInitializing = readinessState === 'initializing'
    || readinessState === 'samples_initializing'
    || productReadModelShowsSampleInitialization(productReadModel);
  const productBlocked = productReadModelIsBlocking(productReadModel) && !samplesInitializing;
  const stateInfo = samplesInitializing
    ? STATE_LABELS.samples_initializing
    : productBlocked && productReadModel?.state
    ? {
      zh: productReadStateLabel(productReadModel.state, 'zh'),
      en: productReadStateLabel(productReadModel.state, 'en'),
      tone: 'blocked' as ReadinessTone,
    }
    : getStateInfo(readiness);
  const reasonLabels = getReasonLabels(readiness, language);
  const hasReadiness = Boolean(readiness?.state);
  const resultAvailable = readiness?.resultContractAvailable === true;
  const benchmarkMissing = normalizeToken(readiness?.benchmarkState) === 'missing'
    || uniqueStrings(readiness?.reasonCodes).includes('missing_benchmark');
  const hasHistoricalReadiness = Boolean(historicalOhlcvReadiness?.contractVersion || historicalOhlcvReadiness?.status);
  const historicalExecutable = historicalOhlcvReadiness?.executable === true;
  const benchmarkReadiness = historicalOhlcvReadiness?.benchmarkReadiness;
  const adjustedRequirement = historicalOhlcvReadiness?.adjustedDataRequirement;
  const title = language === 'en' ? 'Data readiness' : '数据就绪度';
  const subtitle = productBlocked && productReadModel?.state
    ? productReadStateLabel(productReadModel.state, language)
    : !hasReadiness
    ? (language === 'en'
      ? 'Waiting for sample status or a run receipt.'
      : '等待样本状态或运行回执。')
    : stateInfo[language];
  const body = isLoading
    ? (language === 'en' ? 'Checking data and result conditions...' : '正在检查数据与结果条件…')
    : samplesInitializing
      ? (language === 'en'
        ? 'Historical samples are still being prepared. This does not guarantee a successful result.'
        : '历史样本仍在准备中；这不代表结果一定可用。')
    : productBlocked
      ? (language === 'en'
        ? 'Read-only readiness is not execution-ready because coverage, freshness, or quality evidence is blocking.'
        : '只读就绪度未达到可执行状态：覆盖、新鲜度或质量证据仍阻塞。')
    : resultAvailable
      ? (language === 'en'
        ? 'A consumer-safe result view is ready. Metrics are shown only when returned by the backend.'
        : '已返回消费者安全结果契约；只展示后端明确返回的指标。')
      : attempted
        ? (language === 'en'
          ? 'The run attempt is blocked or not yet result-ready. Metrics stay hidden until the result view is ready.'
          : '本次运行被阻塞或尚未具备结果条件；指标在契约确认前保持不可用。')
        : (language === 'en'
          ? 'Review this state before running. It does not trigger any trade or portfolio change.'
          : '运行前先核对该状态；这里不会触发交易，也不会改动组合。');

  return (
    <section
      data-testid={testId}
      data-readiness-state={samplesInitializing ? 'samples_initializing' : productReadModel?.state || normalizeToken(readiness?.state) || 'unknown'}
      data-result-contract-available={String(!productBlocked && resultAvailable)}
      data-product-read-ready={String(productReadModel?.ready === true)}
      className={`rounded-xl border p-4 ${toneClasses(stateInfo.tone)} ${className}`}
    >
      <div className="flex min-w-0 items-start gap-3">
        <ToneIcon tone={stateInfo.tone} />
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] opacity-70">{title}</p>
            {hasReadiness ? (
              <span className="rounded-full border border-current/20 px-2 py-0.5 text-[11px] font-semibold">
                {stateInfo[language]}
              </span>
            ) : null}
          </div>
          <h3 className="mt-2 text-sm font-semibold">{subtitle}</h3>
          <p className="mt-2 text-sm leading-6 opacity-[0.78]">{body}</p>
          <ProductReadModelStatusStrip
            model={productReadModel}
            language={language}
            title={language === 'en' ? 'Backtest readiness read model' : '回测只读就绪度'}
            testId={`${testId}-product-read-model`}
            className="mt-3"
          />

          <div className="mt-3 grid gap-2 text-xs md:grid-cols-3">
            <div className="rounded-lg border border-current/10 bg-black/10 px-3 py-2">
              <p className="opacity-55">{language === 'en' ? 'Result view' : '结果结构'}</p>
              <p className="mt-1 font-semibold">
                {resultAvailable
                  ? (language === 'en' ? 'Ready' : '可用')
                  : samplesInitializing
                    ? (language === 'en' ? 'Preparing' : '准备中')
                    : (language === 'en' ? 'Not ready' : '不可用')}
              </p>
            </div>
            <div className="rounded-lg border border-current/10 bg-black/10 px-3 py-2">
              <p className="opacity-55">{language === 'en' ? 'Benchmark-relative metrics' : '基准相对指标'}</p>
              <p className="mt-1 font-semibold">{benchmarkMissing ? (language === 'en' ? 'Not ready' : '不可用') : (language === 'en' ? 'As returned' : '按回执展示')}</p>
            </div>
            <div className="rounded-lg border border-current/10 bg-black/10 px-3 py-2">
              <p className="opacity-55">{language === 'en' ? 'Boundary' : '边界'}</p>
              <p className="mt-1 flex items-center gap-1 font-semibold">
                <ShieldCheck className="size-3.5" />
                {language === 'en' ? 'Research only' : '仅供研究'}
              </p>
            </div>
          </div>

          {hasHistoricalReadiness ? (
            <div
              data-testid={`${testId}-historical-ohlcv`}
              data-historical-ohlcv-status={normalizeToken(historicalOhlcvReadiness?.status) || 'unknown'}
              className="mt-3 rounded-lg border border-current/10 bg-black/10 px-3 py-3 text-xs"
            >
              <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                <p className="font-semibold">{language === 'en' ? 'Historical data readiness' : '历史数据就绪度'}</p>
                <span className="rounded-full border border-current/20 px-2 py-0.5 font-semibold">
                  {getHistoricalStatusLabel(historicalOhlcvReadiness, language)}
                </span>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                <p>
                  <span className="opacity-55">{language === 'en' ? 'Bars' : 'Bars'}: </span>
                  <span className="font-semibold">
                    {historicalOhlcvReadiness?.availableBarCount ?? 0}/{historicalOhlcvReadiness?.requiredBarCount ?? 0}
                  </span>
                </p>
                <p>
                  <span className="opacity-55">{language === 'en' ? 'Missing classes' : '缺失数据'}: </span>
                  <span className="font-semibold">{getHistoricalDataClassLabels(historicalOhlcvReadiness, language)}</span>
                </p>
                <p>
                  <span className="opacity-55">{language === 'en' ? 'Adjusted prices' : '复权价格'}: </span>
                  <span className="font-semibold">{adjustedRequirement?.required ? (adjustedRequirement.state || 'unknown') : (language === 'en' ? 'Not required' : '未要求')}</span>
                </p>
                <p>
                  <span className="opacity-55">{language === 'en' ? 'Benchmark' : '基准'}: </span>
                  <span className="font-semibold">{benchmarkReadiness?.required ? (benchmarkReadiness.status || 'unknown') : (language === 'en' ? 'Not requested' : '未请求')}</span>
                </p>
              </div>
              <p className="mt-3 leading-5 opacity-80">
                {sanitizeHistoricalReadinessText(historicalOhlcvReadiness?.consumerSafeMessage, language) || (historicalExecutable
                  ? (language === 'en' ? 'Historical price data coverage is available for this request.' : '当前请求具备历史价格数据覆盖。')
                  : (language === 'en' ? 'Historical price data readiness blocks execution.' : '历史价格数据就绪度阻止执行。'))}
              </p>
              {historicalOhlcvReadiness?.operatorNextAction ? (
                <p className="mt-2 leading-5 opacity-70">
                  {language === 'en' ? 'Next action: ' : '下一步：'}{sanitizeHistoricalReadinessText(historicalOhlcvReadiness.operatorNextAction, language)}
                </p>
              ) : null}
            </div>
          ) : null}

          {reasonLabels.length ? (
            <ul className="mt-3 grid gap-2 text-xs leading-5">
              {reasonLabels.map((label) => (
                <li key={label} className="rounded-lg border border-current/10 bg-black/10 px-3 py-2">
                  {label}
                </li>
              ))}
            </ul>
          ) : null}

        </div>
      </div>
    </section>
  );
};

export default BacktestExecutionReadinessPanel;
