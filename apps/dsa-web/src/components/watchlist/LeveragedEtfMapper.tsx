import { useMemo, useState } from 'react';
import { Calculator } from 'lucide-react';
import { Input } from '../common/Input';
import { DenseSecondaryDisclosure } from '../terminal/DenseWorkbenchPrimitives';
import {
  TerminalChip,
  TerminalNotice,
} from '../terminal/TerminalPrimitives';
import {
  calculateImpliedUnderlying,
  calculateLeveragedEtfEstimate,
} from './leveragedEtfMapperMath';

type LeveragedEtfMapperProps = {
  defaultUnderlyingSymbol?: string | null;
  defaultEtfSymbol?: string | null;
  language?: 'zh' | 'en';
  className?: string;
};

type NumericFieldKey =
  | 'leverage'
  | 'underlyingReference'
  | 'etfReference'
  | 'underlyingTarget'
  | 'etfTarget'
  | 'etfEntry'
  | 'etfStop'
  | 'etfTakeProfit';

type NumericFields = Record<NumericFieldKey, string>;
type FieldErrors = Partial<Record<NumericFieldKey, string>>;
type OptionalMark = {
  key: 'etfEntry' | 'etfStop' | 'etfTakeProfit';
  label: string;
  value: number | null;
};

const INITIAL_NUMERIC_FIELDS: NumericFields = {
  leverage: '2',
  underlyingReference: '',
  etfReference: '',
  underlyingTarget: '',
  etfTarget: '',
  etfEntry: '',
  etfStop: '',
  etfTakeProfit: '',
};

const zhCopy = {
  title: '杠杆 ETF 映射',
  summary: '手动输入 · 同日线性近似 · 默认收起',
  symbolGroup: '标的',
  referenceGroup: '参考价',
  targetGroup: '目标情景',
  optionalGroup: '可选 ETF 观察价位',
  underlyingSymbol: '正股/指数代码',
  etfSymbol: 'ETF 代码',
  leverage: '杠杆倍数 / 方向',
  underlyingReference: '正股/指数参考价',
  etfReference: 'ETF 参考价',
  underlyingTarget: '正股/指数目标价',
  etfTarget: 'ETF 目标价',
  etfEntry: 'ETF 入场观察价',
  etfStop: 'ETF 止损观察价',
  etfTakeProfit: 'ETF 止盈观察价',
  forwardTitle: 'ETF 线性估算',
  reverseTitle: '反推正股/指数',
  marksTitle: '观察价位反推',
  missingTargets: '输入参考价和任一目标价后显示线性映射结果。',
  warningOne: '近似 / 手动输入 / 同日线性情景；不是 NAV 预测，不是投资建议，也不是可执行或保证价格。',
  warningTwo: '每日重置、路径依赖、费用/融资、跟踪误差、溢折价、流动性都可能造成偏离。',
  formulaHint: 'ETF 估算 = ETF 参考价 x (1 + 杠杆 x (正股目标 / 正股参考 - 1))',
  resultPrefix: '估算',
  impliedPrefix: '隐含',
  helper: '方向可输入负数，例如 -2 表示反向 2 倍。',
};

const enCopy: typeof zhCopy = {
  title: 'Leveraged ETF Mapper',
  summary: 'Manual input · same-day linear approximation · collapsed',
  symbolGroup: 'Symbols',
  referenceGroup: 'Reference prices',
  targetGroup: 'Target scenario',
  optionalGroup: 'Optional ETF marks',
  underlyingSymbol: 'Underlying symbol',
  etfSymbol: 'ETF symbol',
  leverage: 'Leverage multiple / direction',
  underlyingReference: 'Underlying reference price',
  etfReference: 'ETF reference price',
  underlyingTarget: 'Underlying target price',
  etfTarget: 'ETF target price',
  etfEntry: 'ETF entry mark',
  etfStop: 'ETF stop mark',
  etfTakeProfit: 'ETF take-profit mark',
  forwardTitle: 'ETF linear estimate',
  reverseTitle: 'Implied underlying',
  marksTitle: 'Optional marks',
  missingTargets: 'Enter reference prices and at least one target to show a linear mapping.',
  warningOne: 'Approximate / manual input / same-day linear scenario; not a NAV prediction, not investment advice, and not an executable or assured price.',
  warningTwo: 'Daily reset, path dependency, fees/financing, tracking error, premium-discount, and liquidity can cause drift.',
  formulaHint: 'ETF estimate = ETF reference x (1 + leverage x (underlying target / underlying reference - 1))',
  resultPrefix: 'Estimate',
  impliedPrefix: 'Implied',
  helper: 'Use a negative value for inverse exposure, for example -2.',
};

function parseNumeric(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

function formatPrice(value: number): string {
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fieldError(label: string, value: string, required: boolean, allowNegative = false): string | null {
  const trimmed = value.trim();
  if (!trimmed) return required ? `${label}不能为空。` : null;
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) return `${label}必须是有效数字。`;
  if (allowNegative) {
    return parsed === 0 ? `${label}不能为 0。` : null;
  }
  return parsed <= 0 ? `${label}必须大于 0。` : null;
}

function hasValue(value: string): boolean {
  return value.trim().length > 0;
}

export default function LeveragedEtfMapper({
  defaultUnderlyingSymbol,
  defaultEtfSymbol,
  language = 'zh',
  className,
}: LeveragedEtfMapperProps) {
  const copy = language === 'en' ? enCopy : zhCopy;
  const [underlyingSymbolDraft, setUnderlyingSymbolDraft] = useState('');
  const [etfSymbol, setEtfSymbol] = useState(defaultEtfSymbol || '');
  const [underlyingSymbolEdited, setUnderlyingSymbolEdited] = useState(false);
  const [fields, setFields] = useState<NumericFields>(INITIAL_NUMERIC_FIELDS);
  const underlyingSymbol = underlyingSymbolEdited ? underlyingSymbolDraft : defaultUnderlyingSymbol || '';

  const result = useMemo(() => {
    const requested = hasValue(fields.underlyingTarget)
      || hasValue(fields.etfTarget)
      || hasValue(fields.etfEntry)
      || hasValue(fields.etfStop)
      || hasValue(fields.etfTakeProfit);
    const errors: FieldErrors = {};

    if (requested) {
      const leverageError = fieldError(language === 'zh' ? '杠杆倍数' : 'Leverage', fields.leverage, true, true);
      const underlyingReferenceError = fieldError(copy.underlyingReference, fields.underlyingReference, true);
      const etfReferenceError = fieldError(copy.etfReference, fields.etfReference, true);
      if (leverageError) errors.leverage = leverageError;
      if (underlyingReferenceError) errors.underlyingReference = underlyingReferenceError;
      if (etfReferenceError) errors.etfReference = etfReferenceError;
    }

    ([
      ['underlyingTarget', copy.underlyingTarget],
      ['etfTarget', copy.etfTarget],
      ['etfEntry', copy.etfEntry],
      ['etfStop', copy.etfStop],
      ['etfTakeProfit', copy.etfTakeProfit],
    ] as const).forEach(([key, label]) => {
      const error = fieldError(label, fields[key], false);
      if (error) errors[key] = error;
    });

    const hasErrors = Object.keys(errors).length > 0;
    const leverage = parseNumeric(fields.leverage);
    const underlyingReference = parseNumeric(fields.underlyingReference);
    const etfReference = parseNumeric(fields.etfReference);
    const underlyingTarget = parseNumeric(fields.underlyingTarget);
    const etfTarget = parseNumeric(fields.etfTarget);

    const canCalculate = requested
      && !hasErrors
      && leverage !== null
      && underlyingReference !== null
      && etfReference !== null
      && leverage !== 0;

    const forwardEstimate = canCalculate && underlyingTarget !== null
      ? calculateLeveragedEtfEstimate({
          leverage,
          underlyingReference,
          etfReference,
          underlyingTarget,
        })
      : null;
    const impliedUnderlying = canCalculate && etfTarget !== null
      ? calculateImpliedUnderlying({
          leverage,
          underlyingReference,
          etfReference,
          etfTarget,
        })
      : null;
    const optionalMarks: OptionalMark[] = ([
      ['etfEntry', copy.etfEntry],
      ['etfStop', copy.etfStop],
      ['etfTakeProfit', copy.etfTakeProfit],
    ] as const).flatMap(([key, label]) => {
      const parsed = parseNumeric(fields[key]);
      const mark = {
        key,
        label,
        value: canCalculate && parsed !== null
          ? calculateImpliedUnderlying({
              leverage,
              underlyingReference,
              etfReference,
              etfTarget: parsed,
            })
          : null,
      };
      return mark.value !== null || hasValue(fields[mark.key]) ? [mark] : [];
    });

    return {
      errors,
      forwardEstimate,
      impliedUnderlying,
      optionalMarks,
      hasRequestedOutput: requested,
    };
  }, [copy, fields, language]);

  const updateField = (key: NumericFieldKey, value: string) => {
    setFields((current) => ({ ...current, [key]: value }));
  };
  const hasOutput = result.forwardEstimate !== null
    || result.impliedUnderlying !== null
    || result.optionalMarks.some((item) => item.value !== null);
  const cleanEtfSymbol = etfSymbol.trim().toUpperCase() || 'ETF';
  const cleanUnderlyingSymbol = underlyingSymbol.trim().toUpperCase() || (language === 'zh' ? '正股/指数' : 'underlying');

  return (
    <DenseSecondaryDisclosure
      data-testid="leveraged-etf-mapper"
      variant="row"
      title={copy.title}
      summary={copy.summary}
      className={className}
    >
      <div className="space-y-3 text-xs leading-5 text-white/68">
        <div className="flex min-w-0 items-start gap-2 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2.5">
          <Calculator className="mt-0.5 h-4 w-4 shrink-0 text-cyan-100/75" aria-hidden="true" />
          <div className="min-w-0 space-y-1">
            <p className="text-white/75">{copy.warningOne}</p>
            <p className="text-white/55">{copy.warningTwo}</p>
            <p className="font-mono text-[11px] text-white/42">{copy.formulaHint}</p>
          </div>
        </div>

        <div className="grid min-w-0 gap-3">
          <section className="min-w-0 space-y-2">
            <div className="flex min-w-0 items-center justify-between gap-2">
              <p className="text-[11px] uppercase tracking-[0.18em] text-white/38">{copy.symbolGroup}</p>
              <TerminalChip variant="neutral" className="shrink-0">{language === 'zh' ? '手动' : 'Manual'}</TerminalChip>
            </div>
            <div className="grid min-w-0 gap-2 sm:grid-cols-2">
              <Input
                label={copy.underlyingSymbol}
                value={underlyingSymbol}
                onChange={(event) => {
                  setUnderlyingSymbolEdited(true);
                  setUnderlyingSymbolDraft(event.target.value);
                }}
                placeholder="NVDA"
              />
              <Input
                label={copy.etfSymbol}
                value={etfSymbol}
                onChange={(event) => setEtfSymbol(event.target.value)}
                placeholder="NVDL"
              />
            </div>
          </section>

          <section className="min-w-0 space-y-2">
            <p className="text-[11px] uppercase tracking-[0.18em] text-white/38">{copy.referenceGroup}</p>
            <div className="grid min-w-0 gap-2 sm:grid-cols-3">
              <Input
                label={copy.leverage}
                value={fields.leverage}
                onChange={(event) => updateField('leverage', event.target.value)}
                error={result.errors.leverage}
                hint={copy.helper}
                inputMode="decimal"
                type="number"
                step="any"
              />
              <Input
                label={copy.underlyingReference}
                value={fields.underlyingReference}
                onChange={(event) => updateField('underlyingReference', event.target.value)}
                error={result.errors.underlyingReference}
                inputMode="decimal"
                type="number"
                step="any"
              />
              <Input
                label={copy.etfReference}
                value={fields.etfReference}
                onChange={(event) => updateField('etfReference', event.target.value)}
                error={result.errors.etfReference}
                inputMode="decimal"
                type="number"
                step="any"
              />
            </div>
          </section>

          <section className="min-w-0 space-y-2">
            <p className="text-[11px] uppercase tracking-[0.18em] text-white/38">{copy.targetGroup}</p>
            <div className="grid min-w-0 gap-2 sm:grid-cols-2">
              <Input
                label={copy.underlyingTarget}
                value={fields.underlyingTarget}
                onChange={(event) => updateField('underlyingTarget', event.target.value)}
                error={result.errors.underlyingTarget}
                inputMode="decimal"
                type="number"
                step="any"
              />
              <Input
                label={copy.etfTarget}
                value={fields.etfTarget}
                onChange={(event) => updateField('etfTarget', event.target.value)}
                error={result.errors.etfTarget}
                inputMode="decimal"
                type="number"
                step="any"
              />
            </div>
          </section>

          <section className="min-w-0 space-y-2">
            <p className="text-[11px] uppercase tracking-[0.18em] text-white/38">{copy.optionalGroup}</p>
            <div className="grid min-w-0 gap-2 sm:grid-cols-3">
              <Input
                label={copy.etfEntry}
                value={fields.etfEntry}
                onChange={(event) => updateField('etfEntry', event.target.value)}
                error={result.errors.etfEntry}
                inputMode="decimal"
                type="number"
                step="any"
              />
              <Input
                label={copy.etfStop}
                value={fields.etfStop}
                onChange={(event) => updateField('etfStop', event.target.value)}
                error={result.errors.etfStop}
                inputMode="decimal"
                type="number"
                step="any"
              />
              <Input
                label={copy.etfTakeProfit}
                value={fields.etfTakeProfit}
                onChange={(event) => updateField('etfTakeProfit', event.target.value)}
                error={result.errors.etfTakeProfit}
                inputMode="decimal"
                type="number"
                step="any"
              />
            </div>
          </section>
        </div>

        {hasOutput ? (
          <div className="grid min-w-0 gap-2">
            {result.forwardEstimate !== null ? (
              <div
                data-testid="leveraged-etf-forward-output"
                className="rounded-lg border border-cyan-300/15 bg-cyan-300/[0.035] px-3 py-2"
              >
                <p className="text-[11px] text-cyan-100/60">{copy.forwardTitle}</p>
                <p className="mt-1 font-mono text-sm text-cyan-50">
                  {cleanEtfSymbol} {copy.resultPrefix} {formatPrice(result.forwardEstimate)}
                </p>
              </div>
            ) : null}
            {result.impliedUnderlying !== null ? (
              <div
                data-testid="leveraged-etf-reverse-output"
                className="rounded-lg border border-white/10 bg-white/[0.025] px-3 py-2"
              >
                <p className="text-[11px] text-white/46">{copy.reverseTitle}</p>
                <p className="mt-1 font-mono text-sm text-white/78">
                  {cleanUnderlyingSymbol} {copy.impliedPrefix} {formatPrice(result.impliedUnderlying)}
                </p>
              </div>
            ) : null}
            {result.optionalMarks.length ? (
              <div
                data-testid="leveraged-etf-optional-marks"
                className="divide-y divide-[color:var(--wolfy-divider)] rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-1"
              >
                <p className="py-2 text-[11px] text-white/42">{copy.marksTitle}</p>
                {result.optionalMarks.map((item) => (
                  <div key={item.key} className="flex min-w-0 items-center justify-between gap-3 py-2">
                    <span className="truncate text-white/50">{item.label}</span>
                    <span className="shrink-0 font-mono text-white/76">
                      {item.value !== null ? formatPrice(item.value) : '--'}
                    </span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <TerminalNotice variant="neutral">
            {result.hasRequestedOutput && Object.keys(result.errors).length > 0
              ? (language === 'zh' ? '修正上方输入后再显示映射结果。' : 'Fix the inputs above before showing mapped outputs.')
              : copy.missingTargets}
          </TerminalNotice>
        )}
      </div>
    </DenseSecondaryDisclosure>
  );
}
