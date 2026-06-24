import type React from 'react';
import { AlertTriangle, CheckCircle2, CircleDashed, ShieldCheck, XCircle } from 'lucide-react';
import type { BacktestExecutionReadiness } from '../../types/backtest';

type BacktestLanguage = 'zh' | 'en';

type BacktestExecutionReadinessPanelProps = {
  language: BacktestLanguage;
  readiness?: BacktestExecutionReadiness | null;
  noAdviceDisclosure?: string | null;
  attempted?: boolean;
  isLoading?: boolean;
  className?: string;
  testId?: string;
};

type ReadinessTone = 'ready' | 'warning' | 'blocked' | 'neutral';

const DEFAULT_DISCLOSURE = {
  zh: '仅供研究诊断，不构成投资建议，也不是可执行交易指令。',
  en: 'Research diagnostic only; not personalized financial advice and not an executable instruction.',
} as const;

const STATE_LABELS: Record<string, { zh: string; en: string; tone: ReadinessTone }> = {
  engine_disabled: { zh: '回测引擎已关闭', en: 'Backtest engine disabled', tone: 'blocked' },
  data_disabled: { zh: '数据访问不可用', en: 'Data access unavailable', tone: 'blocked' },
  no_samples: { zh: '暂无可用样本', en: 'No usable samples', tone: 'blocked' },
  data_insufficient: { zh: '历史数据不足', en: 'Insufficient history', tone: 'blocked' },
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
  insufficient_history: { zh: '历史 OHLCV 窗口不足，无法计算安全结果。', en: 'The OHLCV window is too short to calculate a safe result.' },
  insufficient_data: { zh: '可用数据不足，未生成收益、回撤、胜率或基准相对指标。', en: 'Available data is insufficient, so return, drawdown, win-rate, and benchmark-relative metrics are unavailable.' },
  missing_benchmark: { zh: '缺少基准，基准相对指标不可用。', en: 'Benchmark is missing, so benchmark-relative metrics are unavailable.' },
  missing_adjustments: { zh: '复权/公司行动证据不足，结果只能观察。', en: 'Adjustment or corporate-action evidence is incomplete; result is observation-only.' },
  stale_data: { zh: '数据可能过期，结果只能观察。', en: 'Data may be stale; result is observation-only.' },
  missing_factor_inputs: { zh: '因子输入缺失，相关诊断不可用。', en: 'Factor inputs are missing; related diagnostics are unavailable.' },
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

const BacktestExecutionReadinessPanel: React.FC<BacktestExecutionReadinessPanelProps> = ({
  language,
  readiness,
  noAdviceDisclosure,
  attempted = false,
  isLoading = false,
  className = '',
  testId = 'backtest-execution-readiness-panel',
}) => {
  const stateInfo = getStateInfo(readiness);
  const reasonLabels = getReasonLabels(readiness, language);
  const hasReadiness = Boolean(readiness?.state);
  const disclosure = noAdviceDisclosure || readiness?.noAdviceDisclosure || DEFAULT_DISCLOSURE[language];
  const resultAvailable = readiness?.resultContractAvailable === true;
  const benchmarkMissing = normalizeToken(readiness?.benchmarkState) === 'missing'
    || uniqueStrings(readiness?.reasonCodes).includes('missing_benchmark');
  const title = language === 'en' ? 'Execution readiness' : '执行就绪度';
  const subtitle = !hasReadiness
    ? (language === 'en'
      ? 'Waiting for DATA-110 readiness from sample status or a run attempt.'
      : '等待样本状态或运行回执返回 DATA-110 就绪度。')
    : stateInfo[language];
  const body = isLoading
    ? (language === 'en' ? 'Checking latest readiness...' : '正在检查最新就绪度…')
    : resultAvailable
      ? (language === 'en'
        ? 'A consumer-safe result contract is available. Metrics are shown only when returned by the backend.'
        : '已返回消费者安全结果契约；只展示后端明确返回的指标。')
      : attempted
        ? (language === 'en'
          ? 'The run attempt is blocked or not yet result-ready. Metrics stay unavailable until the contract says otherwise.'
          : '本次运行被阻塞或尚未具备结果条件；指标在契约确认前保持不可用。')
        : (language === 'en'
          ? 'Review this state before running. It does not trigger any trade or portfolio change.'
          : '运行前先核对该状态；这里不会触发交易，也不会改动组合。');

  return (
    <section
      data-testid={testId}
      data-readiness-state={normalizeToken(readiness?.state) || 'unknown'}
      data-result-contract-available={String(resultAvailable)}
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

          <div className="mt-3 grid gap-2 text-xs md:grid-cols-3">
            <div className="rounded-lg border border-current/10 bg-black/10 px-3 py-2">
              <p className="opacity-55">{language === 'en' ? 'Result contract' : '结果契约'}</p>
              <p className="mt-1 font-semibold">{resultAvailable ? (language === 'en' ? 'Available' : '可用') : (language === 'en' ? 'Unavailable' : '不可用')}</p>
            </div>
            <div className="rounded-lg border border-current/10 bg-black/10 px-3 py-2">
              <p className="opacity-55">{language === 'en' ? 'Benchmark-relative metrics' : '基准相对指标'}</p>
              <p className="mt-1 font-semibold">{benchmarkMissing ? (language === 'en' ? 'Unavailable' : '不可用') : (language === 'en' ? 'As returned' : '按回执展示')}</p>
            </div>
            <div className="rounded-lg border border-current/10 bg-black/10 px-3 py-2">
              <p className="opacity-55">{language === 'en' ? 'Boundary' : '边界'}</p>
              <p className="mt-1 flex items-center gap-1 font-semibold">
                <ShieldCheck className="size-3.5" />
                {language === 'en' ? 'Research only' : '仅供研究'}
              </p>
            </div>
          </div>

          {reasonLabels.length ? (
            <ul className="mt-3 grid gap-2 text-xs leading-5">
              {reasonLabels.map((label) => (
                <li key={label} className="rounded-lg border border-current/10 bg-black/10 px-3 py-2">
                  {label}
                </li>
              ))}
            </ul>
          ) : null}

          <p className="mt-3 text-xs leading-5 opacity-70">{disclosure}</p>
        </div>
      </div>
    </section>
  );
};

export default BacktestExecutionReadinessPanel;
