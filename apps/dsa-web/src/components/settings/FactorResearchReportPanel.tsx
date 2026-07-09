import type React from 'react';
import { useMemo, useState } from 'react';
import { Play, Trash2 } from 'lucide-react';
import { getApiErrorMessage } from '../../api/error';
import {
  quantApi,
  type QuantFactorResearchDecayPoint,
  type QuantFactorResearchExposureSummary,
  type QuantFactorResearchMetricEstimate,
  type QuantFactorResearchMissingDataReason,
  type QuantFactorResearchNeutralizationSummary,
  type QuantFactorResearchReportResponse,
  type QuantFactorResearchRegistryMetadata,
} from '../../api/quant';
import { useI18n } from '../../contexts/UiLanguageContext';
import { cn } from '../../utils/cn';
import { formatNumber, formatPercent, formatSignedNumber } from '../../utils/format';
import { Button } from '../common/Button';
import { TerminalChip, TerminalEmptyState, TerminalMetric } from '../terminal/TerminalPrimitives';

type ReportStatus = 'blocked' | 'partial' | 'ready' | 'idle' | 'error';

const DEFAULT_BLOCKED_MESSAGE = {
  zh: '研究输入缺失，当前保持阻断。',
  en: 'Research input is missing; the panel stays blocked.',
} as const;

const VALID_JSON_MESSAGE = {
  zh: '输入必须是有效 JSON。',
  en: 'Input must be valid JSON.',
} as const;

const UPDATED_MESSAGE = {
  zh: '报表已更新。',
  en: 'Report updated.',
} as const;

function statusLabel(status: ReportStatus, language: 'zh' | 'en'): string {
  const labels: Record<ReportStatus, Record<'zh' | 'en', string>> = {
    blocked: { zh: '已阻断', en: 'Blocked' },
    partial: { zh: '部分完成', en: 'Partial' },
    ready: { zh: '已就绪', en: 'Ready' },
    idle: { zh: '待提交', en: 'Awaiting input' },
    error: { zh: '错误', en: 'Error' },
  };
  return labels[status][language];
}

function statusVariant(status: ReportStatus): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (status === 'ready') return 'success';
  if (status === 'partial') return 'caution';
  if (status === 'error' || status === 'blocked') return 'danger';
  return 'neutral';
}

function maybeText(value?: string | null, fallback = '--'): string {
  const text = String(value || '').trim();
  return text || fallback;
}

function maybeCount(value?: number | null): string {
  return typeof value === 'number' && Number.isFinite(value) ? formatNumber(value, 0) : '--';
}

function maybeNumber(value?: number | null, digits = 4): string {
  return typeof value === 'number' && Number.isFinite(value) ? formatNumber(value, digits) : '--';
}

function maybePercent(value?: number | null, digits = 1): string {
  return typeof value === 'number' && Number.isFinite(value) ? formatPercent(value, { mode: 'ratio', digits }) : '--';
}

function maybeSignedNumber(value?: number | null, digits = 4): string {
  return typeof value === 'number' && Number.isFinite(value) ? formatSignedNumber(value, digits) : '--';
}

function compactHash(value?: string | null): string {
  const text = String(value || '').trim();
  if (!text) return '--';
  if (text.length <= 18) return text;
  return `${text.slice(0, 10)}…${text.slice(-8)}`;
}

function groupByFactor<T extends { factorId: string }>(items: T[] | undefined): Map<string, T[]> {
  const grouped = new Map<string, T[]>();
  for (const item of items ?? []) {
    const current = grouped.get(item.factorId) ?? [];
    current.push(item);
    grouped.set(item.factorId, current);
  }
  return grouped;
}

function renderSeriesRows(
  rows: QuantFactorResearchMetricEstimate[] | QuantFactorResearchDecayPoint[],
  kind: 'ic' | 'rankIc' | 'decay',
) {
  if (!rows.length) {
    return <p className="mt-2 text-xs text-[color:var(--wolfy-text-muted)]">--</p>;
  }

  return (
    <div className="mt-2 overflow-hidden rounded-lg border border-[color:var(--wolfy-border-subtle)]">
      <table className="w-full border-collapse text-xs">
        <thead className="bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-muted)]">
          <tr>
            <th className="px-2 py-1.5 text-left font-medium">Horizon</th>
            <th className="px-2 py-1.5 text-right font-medium">{kind === 'decay' ? 'IC' : 'Value'}</th>
            <th className="px-2 py-1.5 text-right font-medium">Samples</th>
            <th className="px-2 py-1.5 text-left font-medium">Reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const key = kind === 'decay' ? `${row.horizon}-${row.sampleSize}-${row.insufficientReason || ''}` : `${row.horizon || 'overall'}-${row.sampleSize}-${row.insufficientReason || ''}`;
            const value = kind === 'decay'
              ? maybeNumber((row as QuantFactorResearchDecayPoint).icValue, 4)
              : maybeNumber((row as QuantFactorResearchMetricEstimate).value, 4);
            const secondary = kind === 'decay'
              ? maybeSignedNumber((row as QuantFactorResearchDecayPoint).decayRatio, 4)
              : row.insufficientReason ? row.insufficientReason : '--';
            return (
              <tr key={key} className="border-t border-[color:var(--wolfy-border-subtle)]">
                <td className="px-2 py-1.5 font-mono text-[11px] text-[color:var(--wolfy-text-secondary)]">{row.horizon || '--'}</td>
                <td className="px-2 py-1.5 text-right font-mono text-[color:var(--wolfy-text-primary)]">{kind === 'decay' ? value : maybeNumber((row as QuantFactorResearchMetricEstimate).value, 4)}</td>
                <td className="px-2 py-1.5 text-right font-mono text-[color:var(--wolfy-text-secondary)]">{maybeCount(row.sampleSize)}</td>
                <td className="px-2 py-1.5 text-[11px] text-[color:var(--wolfy-text-muted)]">{kind === 'decay' ? secondary : maybeText(row.insufficientReason, '--')}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function MetricSummaryCard({
  title,
  rows,
}: {
  title: string;
  rows: QuantFactorResearchMetricEstimate[];
}) {
  return (
    <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[color:var(--wolfy-text-muted)]">{title}</p>
      {renderSeriesRows(rows, 'ic')}
    </div>
  );
}

function renderFactorMetadata(items: QuantFactorResearchRegistryMetadata[], language: 'zh' | 'en') {
  if (!items.length) {
    return <TerminalEmptyState className="mt-2" title={language === 'en' ? 'No factor registry metadata' : '暂无因子注册表元数据'} />;
  }

  return (
    <div className="mt-2 grid gap-2 md:grid-cols-2">
      {items.map((item) => (
        <article key={item.factorId} className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="break-words text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{item.label || item.factorId}</p>
              <p className="mt-1 break-words font-mono text-[11px] text-[color:var(--wolfy-text-muted)]">{item.factorId}</p>
            </div>
            <TerminalChip variant={item.registryState === 'registered' ? 'success' : 'caution'}>
              {item.registryState}
            </TerminalChip>
          </div>
          <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{item.description || (language === 'en' ? 'Registry metadata only.' : '仅展示注册表元数据。')}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {item.family ? <TerminalChip variant="neutral">{item.family}</TerminalChip> : null}
            {item.direction ? <TerminalChip variant="info">{item.direction}</TerminalChip> : null}
            {item.unit ? <TerminalChip variant="neutral">{item.unit}</TerminalChip> : null}
            {item.defaultLookbackDays != null ? <TerminalChip variant="neutral">{maybeCount(item.defaultLookbackDays)}d</TerminalChip> : null}
          </div>
        </article>
      ))}
    </div>
  );
}

function renderCoverageItems(items: QuantFactorResearchReportResponse['report']['factorCoverage'], language: 'zh' | 'en') {
  if (!items.length) {
    return <TerminalEmptyState className="mt-2" title={language === 'en' ? 'No factor coverage rows' : '暂无因子覆盖行'} />;
  }

  return (
    <div className="mt-2 grid gap-2 md:grid-cols-2">
      {items.map((item) => (
        <article key={item.factorId} className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
          <p className="break-words text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{item.factorId}</p>
          <p className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">
            {language === 'en'
              ? `Observations ${maybeCount(item.observationCount)} · Symbols ${maybeCount(item.symbolCount)}`
              : `观测 ${maybeCount(item.observationCount)} · 标的 ${maybeCount(item.symbolCount)}`}
          </p>
          <p className="mt-1 font-mono text-[11px] text-[color:var(--wolfy-text-muted)]">
            {maybeText(item.window.asOfStart, '--')} → {maybeText(item.window.asOfEnd, '--')} · {maybeCount(item.window.asOfCount)} {language === 'en' ? 'dates' : '期'}
          </p>
        </article>
      ))}
    </div>
  );
}

function renderNeutralizationSummary(items: QuantFactorResearchNeutralizationSummary[], language: 'zh' | 'en') {
  if (!items.length) {
    return <TerminalEmptyState className="mt-2" title={language === 'en' ? 'No neutralization summary' : '暂无中性化摘要'} />;
  }

  return (
    <div className="mt-2 grid gap-2 md:grid-cols-2">
      {items.map((item) => (
        <article key={`${item.factorId}-${item.axis}`} className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
            <p className="break-words text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{item.factorId}</p>
            <TerminalChip variant={item.warnings.length ? 'caution' : 'success'}>{item.axis}</TerminalChip>
          </div>
          <p className="mt-2 text-xs text-[color:var(--wolfy-text-muted)]">
            {language === 'en'
              ? `Method ${item.neutralizationMethod} · Sample ${maybeCount(item.sampleSize)}`
              : `方法 ${item.neutralizationMethod} · 样本 ${maybeCount(item.sampleSize)}`}
          </p>
          <p className="mt-1 text-[11px] text-[color:var(--wolfy-text-muted)]">
            {language === 'en'
              ? `Neutralized ${maybeCount(item.neutralizedObservations)} / ${maybeCount(item.totalObservations)} · Missing metadata ${maybeCount(item.missingGroupMetadata)} · Insufficient groups ${maybeCount(item.insufficientGroupObservations)}`
              : `已中性化 ${maybeCount(item.neutralizedObservations)} / ${maybeCount(item.totalObservations)} · 缺失分组元数据 ${maybeCount(item.missingGroupMetadata)} · 分组不足 ${maybeCount(item.insufficientGroupObservations)}`}
          </p>
        </article>
      ))}
    </div>
  );
}

function renderExposureSummary(items: QuantFactorResearchExposureSummary[], language: 'zh' | 'en') {
  if (!items.length) {
    return <TerminalEmptyState className="mt-2" title={language === 'en' ? 'No exposure summary' : '暂无敞口摘要'} />;
  }

  return (
    <div className="mt-2 grid gap-2 md:grid-cols-2">
      {items.map((item) => (
        <article key={`${item.scope}-${item.factorId}`} className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
            <p className="break-words text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{item.factorId}</p>
            <TerminalChip variant={item.warnings.length ? 'caution' : 'info'}>{item.scope}</TerminalChip>
          </div>
          <p className="mt-2 text-xs text-[color:var(--wolfy-text-muted)]">
            {language === 'en'
              ? `Exposure ${maybeSignedNumber(item.exposure, 4)} · Weighted ${maybeSignedNumber(item.weightedExposure, 4)}`
              : `敞口 ${maybeSignedNumber(item.exposure, 4)} · 加权 ${maybeSignedNumber(item.weightedExposure, 4)}`}
          </p>
          <p className="mt-1 text-[11px] text-[color:var(--wolfy-text-muted)]">
            {language === 'en'
              ? `Gross ${maybeSignedNumber(item.grossExposure, 4)} · Net ${maybeSignedNumber(item.netExposure, 4)} · Coverage ${maybePercent(item.coverage, 1)}`
              : `总敞口 ${maybeSignedNumber(item.grossExposure, 4)} · 净敞口 ${maybeSignedNumber(item.netExposure, 4)} · 覆盖率 ${maybePercent(item.coverage, 1)}`}
          </p>
          {item.longExposure != null || item.shortExposure != null ? (
            <p className="mt-1 text-[11px] text-[color:var(--wolfy-text-muted)]">
              {language === 'en'
                ? `Long ${maybeSignedNumber(item.longExposure, 4)} · Short ${maybeSignedNumber(item.shortExposure, 4)}`
                : `多头 ${maybeSignedNumber(item.longExposure, 4)} · 空头 ${maybeSignedNumber(item.shortExposure, 4)}`}
            </p>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function renderDiagnostics(items: QuantFactorResearchMissingDataReason[], warnings: string[], language: 'zh' | 'en') {
  if (!items.length && !warnings.length) {
    return <TerminalEmptyState className="mt-2" title={language === 'en' ? 'No diagnostics' : '暂无诊断'} />;
  }

  return (
    <div className="mt-2 grid gap-2">
      {items.map((item, index) => (
        <article key={`${item.section}-${item.reason}-${item.factorId || 'global'}-${index}`} className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] px-3 py-2.5">
          <p className="text-xs font-semibold text-[color:var(--wolfy-text-secondary)]">
            {item.section}
            {item.factorId ? ` · ${item.factorId}` : ''}
          </p>
          <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
            {item.reason}
            {item.context ? ` · ${item.context}` : ''}
          </p>
        </article>
      ))}
      {warnings.length ? (
        <article className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] px-3 py-2.5">
          <p className="text-xs font-semibold text-[color:var(--wolfy-text-secondary)]">{language === 'en' ? 'Warnings' : '警告'}</p>
          <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{warnings.join(' · ')}</p>
        </article>
      ) : null}
    </div>
  );
}

const FactorResearchReportPanel: React.FC = () => {
  const { language } = useI18n();
  const [requestText, setRequestText] = useState('');
  const [response, setResponse] = useState<QuantFactorResearchReportResponse | null>(null);
  const [status, setStatus] = useState<ReportStatus>('blocked');
  const [message, setMessage] = useState<string>(DEFAULT_BLOCKED_MESSAGE[language]);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const trimmedRequest = requestText.trim();
  const canSubmit = trimmedRequest.length > 0 && !isSubmitting;

  const factorMetadata = response?.factorMetadata ?? [];
  const factorCoverage = response?.report.factorCoverage ?? [];
  const metricsSummary = response?.report.metricsSummary ?? [];
  const neutralizationSummary = useMemo(() => response?.report.neutralizationSummary ?? [], [response]);
  const exposureSummary = useMemo(() => response?.report.exposureSummary ?? [], [response]);
  const diagnostics = useMemo(() => {
    if (!response) return [];
    const seen = new Set<string>();
    return [...response.missingDataReasons, ...response.report.missingDataReasons].filter((item) => {
      const key = `${item.section}|${item.reason}|${item.factorId || ''}|${item.context || ''}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [response]);
  const warnings = useMemo(() => {
    if (!response) return [];
    const seen = new Set<string>();
    return [...response.warnings, ...response.report.warnings].filter((item) => {
      const key = String(item || '');
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [response]);

  const neutralizationByFactor = useMemo(() => groupByFactor(neutralizationSummary), [neutralizationSummary]);
  const exposureByFactor = useMemo(() => groupByFactor(exposureSummary), [exposureSummary]);

  const handleTextChange = (value: string) => {
    setRequestText(value);
    if (response) {
      setResponse(null);
    }
    if (!value.trim()) {
      setStatus('blocked');
      setMessage(DEFAULT_BLOCKED_MESSAGE[language]);
      setError(null);
      return;
    }
    setStatus('idle');
    setMessage('');
    setError(null);
  };

  const handleSubmit = async () => {
    if (!trimmedRequest) {
      setStatus('blocked');
      setMessage(DEFAULT_BLOCKED_MESSAGE[language]);
      setError(null);
      return;
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(trimmedRequest);
    } catch {
      setStatus('blocked');
      setMessage(VALID_JSON_MESSAGE[language]);
      setError(VALID_JSON_MESSAGE[language]);
      return;
    }

    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      setStatus('blocked');
      setMessage(VALID_JSON_MESSAGE[language]);
      setError(VALID_JSON_MESSAGE[language]);
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const next = await quantApi.buildFactorResearchReport(parsed as Parameters<typeof quantApi.buildFactorResearchReport>[0]);
      setResponse(next);
      setStatus(next.status === 'ready' ? 'ready' : next.status === 'partial' ? 'partial' : 'blocked');
      setMessage(UPDATED_MESSAGE[language]);
    } catch (submitError) {
      setResponse(null);
      setStatus('error');
      const nextMessage = `${language === 'en' ? 'Report generation failed' : '报表生成失败'}：${getApiErrorMessage(submitError)}`;
      setMessage(nextMessage);
      setError(nextMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClear = () => {
    setRequestText('');
    setResponse(null);
    setStatus('blocked');
    setMessage(DEFAULT_BLOCKED_MESSAGE[language]);
    setError(null);
  };

  const summaryWindow = response?.report.window;
  const inputShape = response?.inputShape;

  return (
    <section className="mt-4 space-y-4 border-t border-[color:var(--wolfy-border-subtle)] pt-4" data-testid="factor-research-report-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[color:var(--state-info-text)]/60">
            {language === 'en' ? 'Factor Research' : '因子研究'}
          </p>
          <h3 className="mt-1 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
            {language === 'en' ? 'Factor research report' : '因子研究报表'}
          </h3>
          <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
            {language === 'en'
              ? 'Observation-only and supplied-input boundaries stay visible.'
              : '仅供观察、仅用显式输入，边界保持可见。'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <TerminalChip variant="info">{language === 'en' ? 'Research only' : '仅供研究'}</TerminalChip>
          <TerminalChip variant="neutral">{language === 'en' ? 'Observation only' : '仅供观察'}</TerminalChip>
          <TerminalChip variant="neutral">{language === 'en' ? 'Explicit input' : '显式输入'}</TerminalChip>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
          <label htmlFor="factor-research-request" className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">
            {language === 'en' ? 'Request JSON' : '输入 JSON'}
          </label>
          <textarea
            id="factor-research-request"
            value={requestText}
            onChange={(event) => handleTextChange(event.target.value)}
            className={cn(
              'min-h-[180px] w-full rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-black/20 p-3 text-sm leading-6 text-[color:var(--wolfy-text-primary)] outline-none transition-colors',
              'placeholder:text-[color:var(--wolfy-text-muted)] focus:border-cyan-300/30 focus:bg-[var(--wolfy-surface-input)]',
            )}
            spellCheck={false}
          />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button
              type="button"
              size="sm"
              variant="settings-primary"
              onClick={() => void handleSubmit()}
              disabled={!canSubmit}
              isLoading={isSubmitting}
            >
              <Play className="size-4" />
              {language === 'en' ? 'Build report' : '生成报表'}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="settings-secondary"
              onClick={handleClear}
              disabled={!trimmedRequest && !response && !error && status === 'blocked'}
            >
              <Trash2 className="size-4" />
              {language === 'en' ? 'Clear' : '清空'}
            </Button>
          </div>
          <p className={cn('mt-2 text-[11px] leading-5', error ? 'text-rose-200' : 'text-[color:var(--wolfy-text-muted)]')} role="status">
            {message || DEFAULT_BLOCKED_MESSAGE[language]}
          </p>
        </div>

        <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">
                {language === 'en' ? 'Result state' : '结果状态'}
              </p>
              <p className="mt-1 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{response ? statusLabel(status, language) : statusLabel('blocked', language)}</p>
            </div>
            <TerminalChip variant={statusVariant(response ? status : 'blocked')}>
              {statusLabel(response ? status : 'blocked', language)}
            </TerminalChip>
          </div>

          {response ? (
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <TerminalMetric
                label={language === 'en' ? 'Observations' : '观测数'}
                value={maybeCount(inputShape?.observationCount)}
                subvalue={language === 'en' ? 'Submitted inputs' : '显式输入'}
              />
              <TerminalMetric
                label={language === 'en' ? 'Metrics inputs' : '指标输入'}
                value={maybeCount(inputShape?.metricObservationCount)}
                subvalue={language === 'en' ? 'Forward returns included' : '含前向收益'}
              />
              <TerminalMetric
                label={language === 'en' ? 'Factor count' : '因子数量'}
                value={maybeCount(inputShape?.factorCount)}
                subvalue={language === 'en' ? 'Registry metadata' : '注册表元数据'}
              />
              <TerminalMetric
                label={language === 'en' ? 'Input hash' : '输入哈希'}
                value={compactHash(inputShape?.inputContentHash)}
                subvalue={inputShape?.hashAlgorithm || '--'}
                valueClassName="break-all text-xs"
              />
              <TerminalMetric
                label={language === 'en' ? 'Report window' : '报表时间窗'}
                value={`${maybeText(summaryWindow?.asOfStart)} → ${maybeText(summaryWindow?.asOfEnd)}`}
                subvalue={`${maybeCount(summaryWindow?.asOfCount)} ${language === 'en' ? 'dates' : '期'}`}
              />
            </div>
          ) : (
            <TerminalEmptyState
              className="mt-3"
              title={language === 'en' ? 'Blocked research state' : '研究阻断状态'}
            >
              {DEFAULT_BLOCKED_MESSAGE[language]}
            </TerminalEmptyState>
          )}

          {response ? (
            <div className="mt-3 flex flex-wrap gap-2">
              <TerminalChip variant="neutral">{language === 'en' ? 'Purpose' : '用途'}: {response.boundary.purpose}</TerminalChip>
              <TerminalChip variant={response.boundary.researchOnly ? 'success' : 'danger'}>{language === 'en' ? 'Research only' : '仅供研究'}: {response.boundary.researchOnly ? 'true' : 'false'}</TerminalChip>
              <TerminalChip variant={response.boundary.diagnosticOnly ? 'success' : 'danger'}>{language === 'en' ? 'Diagnostic only' : '仅诊断'}: {response.boundary.diagnosticOnly ? 'true' : 'false'}</TerminalChip>
              <TerminalChip variant={response.boundary.suppliedObservationsOnly ? 'success' : 'danger'}>{language === 'en' ? 'Supplied inputs' : '显式输入'}: {response.boundary.suppliedObservationsOnly ? 'true' : 'false'}</TerminalChip>
            </div>
          ) : null}
        </div>
      </div>

      {response ? (
        <div className="grid gap-4">
          <section className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
            <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">
                  {language === 'en' ? 'Input shape' : '输入形状'}
                </p>
                <p className="mt-1 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
                  {language === 'en'
                    ? 'Shape, coverage, and hash stay visible.'
                    : '形状、覆盖和哈希保持可见。'}
                </p>
              </div>
              <TerminalChip variant="neutral">{maybeCount(inputShape?.symbolCount)} {language === 'en' ? 'symbols' : '标的'}</TerminalChip>
            </div>
            <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
              <TerminalMetric label={language === 'en' ? 'As-of window' : '时间窗'} value={`${maybeText(inputShape?.asOfStart)} → ${maybeText(inputShape?.asOfEnd)}`} subvalue={`${maybeCount(inputShape?.asOfCount)} ${language === 'en' ? 'dates' : '期'}`} />
              <TerminalMetric label={language === 'en' ? 'Forward horizons' : '前向周期'} value={inputShape?.forwardReturnHorizons?.length ? inputShape.forwardReturnHorizons.join(' · ') : '--'} subvalue={language === 'en' ? 'Performance inputs' : '绩效输入'} />
              <TerminalMetric label={language === 'en' ? 'Neutralization axes' : '中性化轴'} value={inputShape?.neutralizationAxes?.length ? inputShape.neutralizationAxes.join(' · ') : '--'} subvalue={`${maybeCount(inputShape?.minGroupSize)} / ${maybeCount(inputShape?.marketCapBucketCount)}`} />
              <TerminalMetric label={language === 'en' ? 'Hash' : '哈希'} value={compactHash(inputShape?.inputContentHash)} subvalue={inputShape?.hashAlgorithm || '--'} valueClassName="break-all text-xs" />
            </div>
          </section>

          <section className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
            <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">
                  {language === 'en' ? 'Factor registry metadata' : '因子注册表元数据'}
                </p>
                <p className="mt-1 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
                  {language === 'en'
                    ? 'Registry labels and factor directions only.'
                    : '仅展示注册表标签和因子方向。'}
                </p>
              </div>
              <TerminalChip variant="neutral">{maybeCount(factorMetadata.length)} {language === 'en' ? 'entries' : '条'}</TerminalChip>
            </div>
            {renderFactorMetadata(factorMetadata, language)}
          </section>

          <section className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
            <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">
                  {language === 'en' ? 'Factor coverage' : '因子覆盖'}
                </p>
                <p className="mt-1 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
                  {language === 'en'
                    ? 'Observation coverage remains explicit.'
                    : '观测覆盖保持显式。'}
                </p>
              </div>
              <TerminalChip variant="neutral">{maybeCount(factorCoverage.length)} {language === 'en' ? 'factors' : '个因子'}</TerminalChip>
            </div>
            {renderCoverageItems(factorCoverage, language)}
          </section>

          <section className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
            <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">
                  {language === 'en' ? 'Metrics' : '指标'}
                </p>
                <p className="mt-1 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
                  {language === 'en'
                    ? 'IC, Rank IC, decay, turnover, and peer correlation.'
                    : 'IC、Rank IC、衰减、换手率与同类相关性。'}
                </p>
              </div>
              <TerminalChip variant={metricsSummary.length ? 'success' : 'neutral'}>{maybeCount(metricsSummary.length)} {language === 'en' ? 'summaries' : '个摘要'}</TerminalChip>
            </div>
            <div className="mt-3 grid gap-3">
              {metricsSummary.length ? metricsSummary.map((item) => {
                const meta = factorMetadata.find((entry) => entry.factorId === item.factorId);
                const coverageItem = factorCoverage.find((entry) => entry.factorId === item.factorId);
                const neutralizationRows = neutralizationByFactor.get(item.factorId) ?? [];
                const exposureRows = exposureByFactor.get(item.factorId) ?? [];
                return (
                  <article key={item.factorId} className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
                    <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="break-words text-sm font-semibold text-[color:var(--wolfy-text-primary)]">{meta?.label || item.factorId}</p>
                        <p className="mt-1 break-words font-mono text-[11px] text-[color:var(--wolfy-text-muted)]">{item.factorId}</p>
                      </div>
                      <TerminalChip variant="neutral">
                        {maybeText(item.window.asOfStart)} → {maybeText(item.window.asOfEnd)}
                      </TerminalChip>
                    </div>

                    {coverageItem ? (
                      <p className="mt-2 text-xs text-[color:var(--wolfy-text-muted)]">
                        {language === 'en'
                          ? `Coverage ${maybeCount(coverageItem.observationCount)} observations · ${maybeCount(coverageItem.symbolCount)} symbols`
                          : `覆盖 ${maybeCount(coverageItem.observationCount)} 条观测 · ${maybeCount(coverageItem.symbolCount)} 个标的`}
                      </p>
                    ) : null}

                    <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                      <MetricSummaryCard title={language === 'en' ? 'IC' : 'IC'} rows={item.ic} />
                      <MetricSummaryCard title={language === 'en' ? 'Rank IC' : 'Rank IC'} rows={item.rankIc} />
                      <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[color:var(--wolfy-text-muted)]">
                          {language === 'en' ? 'Decay' : '衰减'}
                        </p>
                        {renderSeriesRows(item.decay, 'decay')}
                      </div>
                      <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[color:var(--wolfy-text-muted)]">
                          {language === 'en' ? 'Turnover' : '换手率'}
                        </p>
                        <div className="mt-2 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-black/20 p-3">
                          <p className="font-mono text-sm text-[color:var(--wolfy-text-primary)]">{maybeNumber(item.turnover.value, 4)}</p>
                          <p className="mt-1 text-[11px] text-[color:var(--wolfy-text-muted)]">
                            {language === 'en'
                              ? `Samples ${maybeCount(item.turnover.sampleSize)} · ${item.turnover.insufficientReason || '--'}`
                              : `样本 ${maybeCount(item.turnover.sampleSize)} · ${item.turnover.insufficientReason || '--'}`}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="mt-3 grid gap-2 md:grid-cols-2">
                      <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[color:var(--wolfy-text-muted)]">
                          {language === 'en' ? 'Peer correlation' : '同类相关性'}
                        </p>
                        {item.factorCorrelation.length ? (
                          <div className="mt-2 grid gap-1.5 text-xs">
                            {item.factorCorrelation.map((peer) => (
                              <div key={peer.peerFactorId} className="flex min-w-0 items-center justify-between gap-3 rounded-md bg-black/20 px-2 py-1.5">
                                <span className="min-w-0 break-words text-[color:var(--wolfy-text-secondary)]">{peer.peerFactorId}</span>
                                <span className="shrink-0 font-mono text-[color:var(--wolfy-text-primary)]">{maybeNumber(peer.value, 4)}</span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <TerminalEmptyState className="mt-2" title={language === 'en' ? 'No peer correlation' : '暂无同类相关性'} />
                        )}
                      </div>

                      <div className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[color:var(--wolfy-text-muted)]">
                          {language === 'en' ? 'Window' : '时间窗'}
                        </p>
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                          <TerminalMetric label={language === 'en' ? 'As-of count' : '时间点'} value={maybeCount(item.window.asOfCount)} valueClassName="text-sm" />
                          <TerminalMetric label={language === 'en' ? 'Observation count' : '观测数'} value={maybeCount(item.window.observationCount)} valueClassName="text-sm" />
                        </div>
                      </div>
                    </div>

                    {neutralizationRows.length ? (
                      <div className="mt-3 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[color:var(--wolfy-text-muted)]">
                          {language === 'en' ? 'Neutralization' : '中性化'}
                        </p>
                        {renderNeutralizationSummary(neutralizationRows, language)}
                      </div>
                    ) : null}

                    {exposureRows.length ? (
                      <div className="mt-3 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[color:var(--wolfy-text-muted)]">
                          {language === 'en' ? 'Exposure' : '敞口'}
                        </p>
                        {renderExposureSummary(exposureRows, language)}
                      </div>
                    ) : null}
                  </article>
                );
              }) : (
                <TerminalEmptyState className="mt-2" title={language === 'en' ? 'No metrics summary' : '暂无指标摘要'} />
              )}
            </div>
          </section>

          <section className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-3">
            <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">
                  {language === 'en' ? 'Diagnostics' : '诊断'}
                </p>
                <p className="mt-1 text-sm font-semibold text-[color:var(--wolfy-text-primary)]">
                  {language === 'en'
                    ? 'Missing data reasons and warnings stay explicit.'
                    : '缺失原因和警告保持显式。'}
                </p>
              </div>
              <TerminalChip variant={diagnostics.length || warnings.length ? 'caution' : 'success'}>
                {maybeCount(diagnostics.length)} {language === 'en' ? 'reasons' : '条原因'}
              </TerminalChip>
            </div>
            {renderDiagnostics(diagnostics, warnings, language)}
          </section>

          <p className="text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
            {language === 'en'
              ? 'Research output remains observation-only and creates no external action instruction.'
              : '研究输出仅用于观察，不形成外部动作指令。'}
          </p>
        </div>
      ) : null}
    </section>
  );
};

export default FactorResearchReportPanel;
