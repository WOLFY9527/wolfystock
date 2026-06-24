import type React from 'react';
import { Suspense, lazy } from 'react';
import { Play } from 'lucide-react';
import { ApiErrorAlert } from '../common/ApiErrorAlert';
import { GlassCard } from '../common/GlassCard';
import type { ParsedApiError } from '../../api/error';
import type { BacktestExecutionReadiness } from '../../types/backtest';
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
  noAdviceDisclosure,
  hasRunAttempt = false,
  runFeedback = null,
}) => {
  const templateName = getPointAndShootTemplateName(strategyTemplate, language);

  return (
    <section
      data-testid="normal-backtest-workspace"
      className="w-full min-w-0"
    >
      <GlassCard
        data-testid="normal-backtest-consolidated-card"
        className="w-full min-w-0 rounded-[32px] border border-white/5 bg-white/[0.02] p-6 shadow-[0_30px_80px_rgba(0,0,0,0.28)] xl:p-8"
      >
        <div className="flex min-w-0 flex-col gap-6">
          <div className="flex min-w-0 flex-col gap-2">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-white/40">
              {language === 'en' ? 'Quick-start research lane' : '研究快速模式'}
            </p>
            <div className="flex min-w-0 flex-col gap-2 xl:flex-row xl:items-end xl:justify-between">
              <div className="min-w-0">
                <h2 className="text-2xl font-semibold text-white">
                  {language === 'en' ? 'Quick research setup' : '快速研究回测表单'}
                </h2>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-white/58">
                  {language === 'en'
                    ? 'Keep symbol, benchmark, time range, capital, friction, and the selected template in one dense research surface.'
                    : '把标的、基准、区间、资金、摩擦成本与模板收束到同一块高密度研究面板里。'}
                </p>
              </div>
              <div className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-white/50">
                {templateName || '--'}
              </div>
            </div>
          </div>

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

          <Suspense
            fallback={(
              <div
                data-testid="normal-backtest-template-insights-loading"
                aria-busy="true"
                className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]"
              >
                <div className="min-w-0 rounded-[24px] border border-white/5 bg-black/20 p-5">
                  <p className={LABEL_CLASS}>{language === 'en' ? 'Loading template insights' : '正在加载模板信息'}</p>
                  <div className="mt-4 h-5 w-40 rounded-full bg-white/10" aria-hidden="true" />
                  <div className="mt-3 space-y-2" aria-hidden="true">
                    <div className="h-4 rounded-full bg-white/10" />
                    <div className="size-4/5 rounded-full bg-white/10" />
                    <div className="h-4 w-3/5 rounded-full bg-white/10" />
                  </div>
                </div>
                <div className="min-w-0 rounded-[24px] border border-white/5 bg-black/20 p-5">
                  <p className={LABEL_CLASS}>{language === 'en' ? 'Preparing backtest rule preview' : '正在准备回测规则预览'}</p>
                  <div className="mt-4 space-y-2" aria-hidden="true">
                    <div className="h-4 rounded-full bg-white/10" />
                    <div className="h-4 rounded-full bg-white/10" />
                    <div className="h-4 w-2/3 rounded-full bg-white/10" />
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

          <BacktestExecutionReadinessPanel
            language={language}
            readiness={runReadiness}
            noAdviceDisclosure={noAdviceDisclosure}
            attempted={hasRunAttempt}
            isLoading={isLaunching}
            testId="normal-backtest-execution-readiness"
          />
          <BacktestRunFeedbackBanner feedback={runFeedback} className="mt-4" />

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
                  ? (language === 'en' ? 'Submitting...' : '提交中...')
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
