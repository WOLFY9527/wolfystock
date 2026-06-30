import type React from 'react';
import { Suspense, lazy } from 'react';
import { Play } from 'lucide-react';
import { ApiErrorAlert } from '../common/ApiErrorAlert';
import { GlassCard } from '../common/GlassCard';
import type { ParsedApiError } from '../../api/error';
import type { BacktestExecutionReadiness, BacktestHistoricalOhlcvReadiness } from '../../types/backtest';
import BacktestExecutionReadinessPanel from './BacktestExecutionReadinessPanel';
import BacktestRunFeedbackBanner, { type BacktestRunFeedback } from './BacktestRunFeedbackBanner';
import {
  RULE_BENCHMARK_OPTIONS,
  getBenchmarkModeLabel,
  type RuleBenchmarkMode,
} from './shared';
import {
  POINT_AND_SHOOT_TEMPLATE_OPTIONS,
  getPointAndShootTemplateName,
  type NormalStrategyTemplate,
} from './pointAndShootTemplateOptions';
import type { BacktestLanguage } from './strategyCatalog';

const NormalBacktestTemplateInsights = lazy(() => import('./NormalBacktestTemplateInsights'));

type NormalBacktestWorkspaceProps = {
  language: BacktestLanguage;
  code: string;
  onCodeChange: (value: string) => void;
  startDate: string;
  onStartDateChange: (value: string) => void;
  endDate: string;
  onEndDateChange: (value: string) => void;
  initialCapital: string;
  onInitialCapitalChange: (value: string) => void;
  feeBps: string;
  onFeeBpsChange: (value: string) => void;
  slippageBps: string;
  onSlippageBpsChange: (value: string) => void;
  benchmarkMode: RuleBenchmarkMode;
  onBenchmarkModeChange: (value: RuleBenchmarkMode) => void;
  benchmarkCode: string;
  onBenchmarkCodeChange: (value: string) => void;
  strategyTemplate: NormalStrategyTemplate;
  onStrategyTemplateChange: (value: NormalStrategyTemplate) => void;
  onLaunch: () => Promise<void>;
  isLaunching: boolean;
  parseError: ParsedApiError | null;
  runError: ParsedApiError | null;
  runReadiness?: BacktestExecutionReadiness | null;
  historicalOhlcvReadiness?: BacktestHistoricalOhlcvReadiness | null;
  noAdviceDisclosure?: string | null;
  hasRunAttempt?: boolean;
  runFeedback?: BacktestRunFeedback | null;
};

const FIELD_CLASS = 'w-full min-w-0 min-h-[44px] rounded-lg border border-white/10 bg-white/[0.02] px-3 py-2.5 text-sm leading-6 text-white outline-none transition-all focus:border-emerald-500/50 focus:bg-white/[0.05]';
const LABEL_CLASS = 'mb-2 text-[10px] font-bold uppercase tracking-widest text-white/40';
const PRIMARY_CTA_CLASS = 'inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-5 py-2 text-sm font-medium text-emerald-400 transition-all hover:border-emerald-500/50 hover:bg-emerald-500/20 hover:shadow-[0_0_15px_rgba(16,185,129,0.2)] active:scale-95 disabled:cursor-not-allowed disabled:opacity-70';

const NormalBacktestWorkspace: React.FC<NormalBacktestWorkspaceProps> = ({
  language,
  code,
  onCodeChange,
  startDate,
  onStartDateChange,
  endDate,
  onEndDateChange,
  initialCapital,
  onInitialCapitalChange,
  feeBps,
  onFeeBpsChange,
  slippageBps,
  onSlippageBpsChange,
  benchmarkMode,
  onBenchmarkModeChange,
  benchmarkCode,
  onBenchmarkCodeChange,
  strategyTemplate,
  onStrategyTemplateChange,
  onLaunch,
  isLaunching,
  parseError,
  runError,
  runReadiness,
  historicalOhlcvReadiness,
  noAdviceDisclosure,
  hasRunAttempt = false,
  runFeedback = null,
}) => {
  const templateName = getPointAndShootTemplateName(strategyTemplate, language);
  const readinessState = String(runReadiness?.state || '').trim().toLowerCase().replaceAll('-', '_').replace(/\s+/g, '_');
  const historicalState = String(historicalOhlcvReadiness?.status || '').trim().toLowerCase().replaceAll('-', '_').replace(/\s+/g, '_');
  const resultPreviewTitle = hasRunAttempt && runReadiness?.resultContractAvailable === false
    ? (language === 'en' ? 'Result is not ready yet' : '结果暂未就绪')
    : hasRunAttempt && runReadiness?.resultContractAvailable === true
      ? (language === 'en' ? 'Result view is ready' : '结果结构已返回')
      : (language === 'en' ? 'No result yet' : '暂无结果');
  const resultPreviewBody = hasRunAttempt && runReadiness?.resultContractAvailable === false
    ? (language === 'en'
      ? 'The current symbol or date range does not yet have enough usable data for a result view. Adjust the range, check historical data, or retry after data coverage improves.'
      : '当前标的或日期区间尚未具备足够可用数据，暂不展示结果。可调整区间、核对历史数据，或待覆盖改善后重试。')
    : hasRunAttempt && runReadiness?.resultContractAvailable === true
      ? (language === 'en'
        ? 'Open the saved result page to inspect curve, drawdown, trades, win rate, and sample coverage returned by the backend.'
        : '可打开保存结果页，查看后端返回的收益曲线、回撤、交易次数、胜率与样本覆盖。')
      : (language === 'en'
        ? 'After running, this workspace will show return curve, drawdown, trade count, win rate, and sample range when the backend returns them.'
        : '运行后，这里会展示收益曲线、回撤、交易次数、胜率与样本区间等可用结果。');
  const dataLimitation = readinessState === 'data_insufficient' || historicalState === 'insufficient_coverage'
    ? (language === 'en'
      ? 'Current limitation: historical price coverage is not enough for the selected range.'
      : '当前限制：所选区间的历史行情覆盖不足。')
    : readinessState === 'data_disabled' || historicalState === 'unavailable'
      ? (language === 'en'
        ? 'Current limitation: historical data access is unavailable for this request.'
        : '当前限制：本次请求的历史数据访问暂不可用。')
      : readinessState === 'no_samples'
        ? (language === 'en'
          ? 'Current limitation: no prepared sample is available yet.'
          : '当前限制：尚无可用样本。')
        : null;

  return (
    <section
      data-testid="normal-backtest-workspace"
      className="w-full min-w-0"
    >
      <GlassCard
        data-testid="normal-backtest-consolidated-card"
        className="w-full min-w-0 rounded-[14px] border border-white/5 bg-white/[0.02] p-4 shadow-[0_30px_80px_rgba(0,0,0,0.28)] xl:p-5"
      >
        <div className="flex min-w-0 flex-col gap-6">
          <div className="flex min-w-0 flex-col gap-2">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-white/40">
              {language === 'en' ? 'Quick-start research lane' : '研究快速模式'}
            </p>
            <div className="flex min-w-0 flex-col gap-2 xl:flex-row xl:items-end xl:justify-between">
              <div className="min-w-0">
                <h2 className="text-2xl font-semibold text-white">
                  {language === 'en' ? 'Validation workspace' : '验证工作台'}
                </h2>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-white/58">
                  {language === 'en'
                    ? 'Set what will be tested on the left; read data readiness and the result preview on the right before launching.'
                    : '左侧配置要验证的策略；右侧先看数据就绪度与结果预览，再决定是否运行。'}
                </p>
              </div>
              <div className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-white/50">
                {templateName || '--'}
              </div>
            </div>
          </div>

          <div data-testid="normal-backtest-consumer-grid" className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.55fr)] xl:items-start">
            <div className="min-w-0">
              <div
                data-testid="normal-backtest-form-grid"
                className="grid grid-cols-1 gap-x-6 gap-y-4 md:grid-cols-4"
              >
            <label className="product-field min-w-0 gap-1.5 md:col-span-1">
              <span className={LABEL_CLASS}>{language === 'en' ? 'Ticker' : '标的代码'}</span>
              <input
                type="text"
                className={FIELD_CLASS}
                value={code}
                onChange={(event) => onCodeChange(event.target.value.toUpperCase())}
                placeholder={language === 'en' ? 'AAPL / TSLA / 600519' : 'AAPL / TSLA / 600519'}
                aria-label={language === 'en' ? 'Ticker' : '标的代码'}
              />
            </label>

            <div className="min-w-0 md:col-span-1">
              <label className="product-field min-w-0 gap-1.5">
                <span className={LABEL_CLASS}>{language === 'en' ? 'Benchmark' : '对比基准'}</span>
                <select
                  className={`${FIELD_CLASS} appearance-none pr-10 truncate`}
                  value={benchmarkMode}
                  onChange={(event) => onBenchmarkModeChange(event.target.value as RuleBenchmarkMode)}
                  aria-label={language === 'en' ? 'Benchmark' : '对比基准'}
                >
                  {RULE_BENCHMARK_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {getBenchmarkModeLabel(option.value, code, benchmarkCode, language)}
                    </option>
                  ))}
                </select>
              </label>
              {benchmarkMode === 'custom_code' ? (
                <label className="product-field mt-3 min-w-0 gap-1.5">
                  <span className="sr-only">{language === 'en' ? 'Custom benchmark code' : '自定义基准代码'}</span>
                  <input
                    type="text"
                    className={FIELD_CLASS}
                    value={benchmarkCode}
                    onChange={(event) => onBenchmarkCodeChange(event.target.value.toUpperCase())}
                    placeholder={language === 'en' ? 'QQQ / SPY / ^NDX / 000300' : 'QQQ / SPY / ^NDX / 000300'}
                    aria-label={language === 'en' ? 'Custom benchmark code' : '自定义基准代码'}
                  />
                </label>
              ) : null}
            </div>

            <div className="min-w-0 md:col-span-2">
              <span className={LABEL_CLASS}>{language === 'en' ? 'Date range' : '回测区间'}</span>
              <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2">
                <label className="product-field min-w-0 gap-1.5">
                  <span className="sr-only">{language === 'en' ? 'Range start' : '回测区间开始'}</span>
                  <input
                    type="date"
                    className={FIELD_CLASS}
                    value={startDate}
                    onChange={(event) => onStartDateChange(event.target.value)}
                    aria-label={language === 'en' ? 'Range start' : '回测区间开始'}
                  />
                </label>
                <label className="product-field min-w-0 gap-1.5">
                  <span className="sr-only">{language === 'en' ? 'Range end' : '回测区间结束'}</span>
                  <input
                    type="date"
                    className={FIELD_CLASS}
                    value={endDate}
                    onChange={(event) => onEndDateChange(event.target.value)}
                    aria-label={language === 'en' ? 'Range end' : '回测区间结束'}
                  />
                </label>
              </div>
            </div>

            <label className="product-field min-w-0 gap-1.5 md:col-span-1">
              <span className={LABEL_CLASS}>{language === 'en' ? 'Capital' : '初始资金'}</span>
              <input
                type="number"
                className={FIELD_CLASS}
                min={1}
                value={initialCapital}
                onChange={(event) => onInitialCapitalChange(event.target.value)}
                aria-label={language === 'en' ? 'Capital' : '初始资金'}
              />
            </label>

            <div className="min-w-0 md:col-span-1">
              <label className="product-field min-w-0 gap-1.5">
                <span className={LABEL_CLASS}>{language === 'en' ? 'Slippage' : '滑点'}</span>
                <input
                  type="number"
                  className={FIELD_CLASS}
                  min={0}
                  max={500}
                  value={slippageBps}
                  onChange={(event) => onSlippageBpsChange(event.target.value)}
                  aria-label={language === 'en' ? 'Slippage' : '滑点'}
                />
              </label>
              <label className="product-field mt-3 min-w-0 gap-1.5">
                <span className={LABEL_CLASS}>{language === 'en' ? 'Fees (bp)' : '手续费 (bp)'}</span>
                <input
                  type="number"
                  className={FIELD_CLASS}
                  min={0}
                  max={500}
                  value={feeBps}
                  onChange={(event) => onFeeBpsChange(event.target.value)}
                  aria-label={language === 'en' ? 'Fees (bp)' : '手续费 (bp)'}
                />
              </label>
            </div>

            <div className="min-w-0 md:col-span-2">
              <label className="product-field min-w-0 gap-1.5">
                <span className={LABEL_CLASS}>{language === 'en' ? 'Strategy template' : '策略模板'}</span>
                <select
                  className={`${FIELD_CLASS} appearance-none pr-10 truncate`}
                  value={strategyTemplate}
                  onChange={(event) => onStrategyTemplateChange(event.target.value as NormalStrategyTemplate)}
                  aria-label={language === 'en' ? 'Strategy template' : '策略模板'}
                >
                  {POINT_AND_SHOOT_TEMPLATE_OPTIONS.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name[language]}
                    </option>
                  ))}
                </select>
              </label>
              </div>
              </div>

              <div className="mt-5">
                <Suspense
                  fallback={(
                    <div
                      data-testid="normal-backtest-template-insights-loading"
                      aria-busy="true"
                      className="grid min-w-0 gap-4"
                    >
                      <div className="min-w-0 rounded-xl border border-white/5 bg-black/20 p-5">
                        <p className={LABEL_CLASS}>{language === 'en' ? 'Loading template insights' : '正在加载模板信息'}</p>
                        <div className="mt-4 h-5 w-40 rounded-full bg-white/10" aria-hidden="true" />
                        <div className="mt-3 space-y-2" aria-hidden="true">
                          <div className="h-4 rounded-full bg-white/10" />
                          <div className="size-4/5 rounded-full bg-white/10" />
                          <div className="h-4 w-3/5 rounded-full bg-white/10" />
                        </div>
                      </div>
                    </div>
                  )}
                >
                  <NormalBacktestTemplateInsights
                    language={language}
                    strategyTemplate={strategyTemplate}
                    code={code}
                    startDate={startDate}
                    endDate={endDate}
                    initialCapital={initialCapital}
                  />
                </Suspense>
              </div>
            </div>

            <aside data-testid="normal-backtest-preview-rail" className="grid min-w-0 gap-4">
              <BacktestExecutionReadinessPanel
                language={language}
                readiness={runReadiness}
                historicalOhlcvReadiness={historicalOhlcvReadiness}
                noAdviceDisclosure={noAdviceDisclosure}
                attempted={hasRunAttempt}
                isLoading={isLaunching}
                testId="normal-backtest-execution-readiness"
              />
              <section data-testid="backtest-result-preview-panel" className="rounded-xl border border-white/10 bg-black/20 p-4">
                <div className="flex min-w-0 items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className={LABEL_CLASS}>{language === 'en' ? 'Result preview' : '结果预览'}</p>
                    <h3 className="text-base font-semibold text-white">{resultPreviewTitle}</h3>
                  </div>
                  <span className="shrink-0 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] text-white/52">
                    {code || (language === 'en' ? 'No symbol' : '未选择标的')}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-white/62">{resultPreviewBody}</p>
                {dataLimitation ? (
                  <p data-testid="backtest-data-limitation" className="mt-3 rounded-lg border border-amber-300/20 bg-amber-300/10 px-3 py-2 text-xs leading-5 text-amber-50/82">
                    {dataLimitation}
                    {' '}
                    {language === 'en' ? 'Next: change the range or rerun after data coverage is refreshed.' : '下一步：调整区间，或等待数据覆盖刷新后重试。'}
                  </p>
                ) : null}
                <div data-testid="backtest-preview-output-list" className="mt-4 grid gap-2 text-xs sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                  {[
                    language === 'en' ? 'Return curve' : '收益曲线',
                    language === 'en' ? 'Drawdown' : '回撤',
                    language === 'en' ? 'Trade count' : '交易次数',
                    language === 'en' ? 'Win rate' : '胜率',
                    language === 'en' ? 'Sample range' : '样本区间',
                  ].map((item) => (
                    <span key={item} className="rounded-lg border border-white/8 bg-white/[0.025] px-3 py-2 text-white/62">
                      {item}
                    </span>
                  ))}
                </div>
              </section>
              <BacktestRunFeedbackBanner feedback={runFeedback} />
              <details data-testid="backtest-diagnostics-disclosure" className="rounded-xl border border-white/10 bg-white/[0.02] p-3 text-sm text-white/62">
                <summary className="cursor-pointer list-none font-semibold text-white/78">
                  {language === 'en' ? 'View backtest diagnostics' : '查看回测诊断'}
                </summary>
                <p className="mt-2 text-xs leading-5 text-white/48">
                  {language === 'en'
                    ? 'Detailed readiness fields stay collapsed by default. Use this only when checking a blocked run.'
                    : '详细就绪度字段默认折叠；仅在复核阻塞运行时展开。'}
                </p>
              </details>
            </aside>
          </div>

          <div
            data-testid="normal-backtest-cta-row"
            className="flex min-w-0 flex-col gap-4 border-t border-white/8 pt-5 xl:flex-row xl:items-center xl:justify-between"
          >
            <div className="min-w-0 text-sm text-white/46">
              {language === 'en'
                ? 'Quick-start mode first turns the selected template into a fixed-rule backtest flow, then opens the dedicated result page.'
                : '研究快速模式会先把模板整理为固定规则回测流程，再跳转到独立结果页。'}
            </div>
            <button
              type="button"
              className={PRIMARY_CTA_CLASS}
              onClick={() => void onLaunch()}
              disabled={isLaunching}
            >
              <Play className="size-4" />
              <span>
                {isLaunching
                  ? (language === 'en' ? 'Checking data readiness...' : '正在检查数据就绪度')
                  : (language === 'en' ? 'Execute backtest task' : '执行回测任务')}
              </span>
            </button>
          </div>

          {parseError ? <ApiErrorAlert error={parseError} /> : null}
          {runError ? <ApiErrorAlert error={runError} /> : null}
        </div>
      </GlassCard>
    </section>
  );
};

export default NormalBacktestWorkspace;
