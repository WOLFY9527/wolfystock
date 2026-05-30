import type React from 'react';
import { useEffect, useEffectEvent, useState } from 'react';
import { backtestApi } from '../../api/backtest';
import { getApiErrorMessage } from '../../api/error';
import { useI18n } from '../../contexts/UiLanguageContext';
import type {
  RuleBacktestRobustnessEvidenceExportResponse,
  RuleBacktestSupportExportIndexItem,
} from '../../types/backtest';
import {
  TerminalButton,
  TerminalChip,
  TerminalDisclosure,
  TerminalEmptyState,
  TerminalNestedBlock,
  TerminalNotice,
} from '../terminal/TerminalPrimitives';

type BacktestSupportExportsDisclosureProps = {
  runId: number;
  code: string;
};

type LocalizedCopy = {
  zh: string;
  en: string;
};

type RobustnessEvidencePreviewState =
  | { status: 'idle' | 'loading' }
  | { status: 'ready'; payload: RuleBacktestRobustnessEvidenceExportResponse }
  | { status: 'error'; message: string };

type SupportExportDefinition = {
  id: 'supportBundleManifest' | 'supportBundleReproducibilityManifest' | 'robustnessEvidenceJson' | 'executionTraceJson' | 'executionTraceCsv';
  keys: string[];
  labelKey?: string;
  descriptionKey?: string;
  actionKey?: string;
  label?: LocalizedCopy;
  description?: LocalizedCopy;
  action?: LocalizedCopy;
  onlyRenderWhenAvailable?: boolean;
  fileName: (code: string, runId: number) => string;
  mimeType: string;
  loadContent: (runId: number) => Promise<string>;
};

const SUPPORT_EXPORT_DEFINITIONS: SupportExportDefinition[] = [
  {
    id: 'supportBundleManifest',
    keys: ['support_bundle_manifest_json', 'support_bundle_manifest'],
    labelKey: 'backtest.resultPage.supportExports.items.supportBundleManifest.label',
    descriptionKey: 'backtest.resultPage.supportExports.items.supportBundleManifest.description',
    actionKey: 'backtest.resultPage.supportExports.items.supportBundleManifest.action',
    fileName: (code, runId) => `backtest-support-bundle-manifest-${code}-${runId}.json`,
    mimeType: 'application/json;charset=utf-8',
    loadContent: async (runId) => JSON.stringify(
      await backtestApi.getRuleBacktestSupportBundleManifest(runId),
      null,
      2,
    ),
  },
  {
    id: 'supportBundleReproducibilityManifest',
    keys: ['support_bundle_reproducibility_manifest_json', 'support_bundle_reproducibility_manifest'],
    labelKey: 'backtest.resultPage.supportExports.items.supportBundleReproducibilityManifest.label',
    descriptionKey: 'backtest.resultPage.supportExports.items.supportBundleReproducibilityManifest.description',
    actionKey: 'backtest.resultPage.supportExports.items.supportBundleReproducibilityManifest.action',
    fileName: (code, runId) => `backtest-support-bundle-reproducibility-${code}-${runId}.json`,
    mimeType: 'application/json;charset=utf-8',
    loadContent: async (runId) => JSON.stringify(
      await backtestApi.getRuleBacktestSupportBundleReproducibilityManifest(runId),
      null,
      2,
    ),
  },
  {
    id: 'executionTraceJson',
    keys: ['execution_trace_json'],
    labelKey: 'backtest.resultPage.supportExports.items.executionTraceJson.label',
    descriptionKey: 'backtest.resultPage.supportExports.items.executionTraceJson.description',
    actionKey: 'backtest.resultPage.supportExports.items.executionTraceJson.action',
    fileName: (code, runId) => `backtest-support-execution-trace-${code}-${runId}.json`,
    mimeType: 'application/json;charset=utf-8',
    loadContent: async (runId) => JSON.stringify(
      await backtestApi.getRuleBacktestExecutionTraceJson(runId),
      null,
      2,
    ),
  },
  {
    id: 'robustnessEvidenceJson',
    keys: ['robustness_evidence_json'],
    label: {
      zh: '稳健性证据',
      en: 'Robustness evidence',
    },
    description: {
      zh: '仅导出已存储的稳健性分析证据，用于技术支持 / 复现证据，不作为结果摘要、图表或指标的主要结论口径。',
      en: 'Exports stored robustness-analysis evidence only for technical support / reproducibility evidence, not as the primary authority for summaries, charts, or metrics.',
    },
    action: {
      zh: '下载稳健性证据 JSON',
      en: 'Download robustness evidence JSON',
    },
    onlyRenderWhenAvailable: true,
    fileName: (code, runId) => `backtest-robustness-evidence-${code}-${runId}.json`,
    mimeType: 'application/json;charset=utf-8',
    loadContent: async (runId) => JSON.stringify(
      await backtestApi.getRuleBacktestRobustnessEvidenceJson(runId),
      null,
      2,
    ),
  },
  {
    id: 'executionTraceCsv',
    keys: ['execution_trace_csv'],
    labelKey: 'backtest.resultPage.supportExports.items.executionTraceCsv.label',
    descriptionKey: 'backtest.resultPage.supportExports.items.executionTraceCsv.description',
    actionKey: 'backtest.resultPage.supportExports.items.executionTraceCsv.action',
    fileName: (code, runId) => `backtest-support-execution-trace-${code}-${runId}.csv`,
    mimeType: 'text/csv;charset=utf-8',
    loadContent: (runId) => backtestApi.getRuleBacktestExecutionTraceCsv(runId),
  },
];

function downloadTextFile(filename: string, content: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function getSupportExportItem(
  definition: SupportExportDefinition,
  items: RuleBacktestSupportExportIndexItem[],
): RuleBacktestSupportExportIndexItem | null {
  return items.find((item) => definition.keys.includes(item.key)) || null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function getRecord(value: unknown, keys: string[]): Record<string, unknown> | null {
  if (!isRecord(value)) {
    return null;
  }
  for (const key of keys) {
    const candidate = value[key];
    if (isRecord(candidate)) {
      return candidate;
    }
  }
  return null;
}

function getList(value: unknown, keys: string[]): Record<string, unknown>[] {
  if (!isRecord(value)) {
    return [];
  }
  for (const key of keys) {
    const candidate = value[key];
    if (Array.isArray(candidate)) {
      return candidate.filter(isRecord);
    }
  }
  return [];
}

function getString(value: unknown, keys: string[]): string | null {
  if (!isRecord(value)) {
    return null;
  }
  for (const key of keys) {
    const candidate = value[key];
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate;
    }
  }
  return null;
}

function getBoolean(value: unknown, keys: string[]): boolean | null {
  if (!isRecord(value)) {
    return null;
  }
  for (const key of keys) {
    const candidate = value[key];
    if (typeof candidate === 'boolean') {
      return candidate;
    }
  }
  return null;
}

function getNumber(value: unknown, keys: string[]): number | null {
  if (!isRecord(value)) {
    return null;
  }
  for (const key of keys) {
    const candidate = value[key];
    if (typeof candidate === 'number' && Number.isFinite(candidate)) {
      return candidate;
    }
  }
  return null;
}

function formatWindowRange(start: string | null, end: string | null): string {
  if (start && end) {
    return `${start} -> ${end}`;
  }
  return start || end || '--';
}

function getDiagnosticWindowLabel(language: 'zh' | 'en', foldIndex: number | null): string {
  if (language === 'en') {
    return foldIndex != null ? `Stored diagnostic window ${foldIndex}` : 'Stored diagnostic window';
  }
  return foldIndex != null ? `已存储诊断窗口 ${foldIndex}` : '已存储诊断窗口';
}

function renderRobustnessEvidencePreview(
  payload: RuleBacktestRobustnessEvidenceExportResponse,
  language: 'zh' | 'en',
): React.ReactNode {
  const oosEvidence = getRecord(payload, ['walkForwardOosEvidence', 'walk_forward_oos_evidence']);
  if (!oosEvidence) {
    return (
      <TerminalNotice variant="neutral">
        {language === 'en'
          ? 'This export does not include stored OOS diagnostic evidence.'
          : '当前导出未包含已存储的 OOS 诊断证据。'}
      </TerminalNotice>
    );
  }

  const diagnosticOnly = getBoolean(oosEvidence, ['diagnosticOnly', 'diagnostic_only']);
  const decisionGrade = getBoolean(oosEvidence, ['decisionGrade', 'decision_grade']);
  const coverage = getRecord(oosEvidence, ['coverage']);
  const authority = getRecord(oosEvidence, ['authority']);
  const configuration = getRecord(oosEvidence, ['configuration']);
  const folds = getList(oosEvidence, ['folds', 'fold_results']);
  const periodStart = getString(oosEvidence, ['periodStart', 'period_start']);
  const periodEnd = getString(oosEvidence, ['periodEnd', 'period_end']);
  const availableFoldCount = getNumber(coverage, ['availableFoldCount', 'available_fold_count']);
  const missingFoldCount = getNumber(coverage, ['missingFoldCount', 'missing_fold_count']);
  const skippedFoldCount = getNumber(coverage, ['skippedFoldCount', 'skipped_fold_count']);
  const configuredMaxFolds = getNumber(configuration, ['maxFolds', 'max_folds']);
  const configuredTrainWindow = getNumber(configuration, ['trainWindow', 'train_window']);
  const configuredTestWindow = getNumber(configuration, ['testWindow', 'test_window']);
  const configuredStep = getNumber(configuration, ['step']);
  const configuredWindowUnit = getString(configuration, ['windowUnit', 'window_unit']);
  const authorityFlags = [
    { label: 'provider_calls_executed', value: getBoolean(authority, ['providerCallsExecuted', 'provider_calls_executed']) },
    { label: 'engine_math_changed', value: getBoolean(authority, ['engineMathChanged', 'engine_math_changed']) },
    { label: 'optimizer_executed', value: getBoolean(authority, ['optimizerExecuted', 'optimizer_executed']) },
    { label: 'parameter_sweep_executed', value: getBoolean(authority, ['parameterSweepExecuted', 'parameter_sweep_executed']) },
    { label: 'strategy_parameters_mutated', value: getBoolean(authority, ['strategyParametersMutated', 'strategy_parameters_mutated']) },
  ].filter((item) => item.value !== null);

  return (
    <div className="flex flex-col gap-3" data-testid="backtest-oos-diagnostic-preview">
      <TerminalNotice variant="neutral">
        {language === 'en'
          ? 'Stored diagnostic windows below are replay evidence only. They do not indicate pass/fail validation.'
          : '下列窗口仅为已存储的诊断回放证据，不表示通过/未通过验证。'}
      </TerminalNotice>
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        <TerminalNestedBlock>
          <p className="text-[11px] text-white/35">diagnosticOnly</p>
          <p className="mt-1 font-mono text-sm text-white/82">{String(diagnosticOnly ?? '--')}</p>
        </TerminalNestedBlock>
        <TerminalNestedBlock>
          <p className="text-[11px] text-white/35">decisionGrade</p>
          <p className="mt-1 font-mono text-sm text-white/82">{String(decisionGrade ?? '--')}</p>
        </TerminalNestedBlock>
        <TerminalNestedBlock>
          <p className="text-[11px] text-white/35">{language === 'en' ? 'Coverage' : '覆盖计数'}</p>
          <p className="mt-1 font-mono text-sm text-white/82">
            {language === 'en'
              ? `available ${availableFoldCount ?? '--'} · missing ${missingFoldCount ?? '--'} · skipped ${skippedFoldCount ?? '--'}`
              : `可用 ${availableFoldCount ?? '--'} · 缺失 ${missingFoldCount ?? '--'} · 跳过 ${skippedFoldCount ?? '--'}`}
          </p>
        </TerminalNestedBlock>
        <TerminalNestedBlock>
          <p className="text-[11px] text-white/35">{language === 'en' ? 'Stored window span' : '存储窗口范围'}</p>
          <p className="mt-1 font-mono text-sm text-white/82">{formatWindowRange(periodStart, periodEnd)}</p>
          <p className="mt-1 text-[11px] leading-5 text-white/35">
            {language === 'en'
              ? `folds ${folds.length}${configuredMaxFolds != null ? ` / ${configuredMaxFolds}` : ''}`
              : `fold ${folds.length}${configuredMaxFolds != null ? ` / ${configuredMaxFolds}` : ''}`}
            {configuredTrainWindow != null && configuredTestWindow != null
              ? ` · train ${configuredTrainWindow} · test ${configuredTestWindow}${configuredStep != null ? ` · step ${configuredStep}` : ''}${configuredWindowUnit ? ` · ${configuredWindowUnit}` : ''}`
              : ''}
          </p>
        </TerminalNestedBlock>
      </div>
      <TerminalNestedBlock>
        <p className="text-[11px] text-white/35">{language === 'en' ? 'Authority no-execution flags' : 'authority 未执行标记'}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {authorityFlags.length > 0 ? authorityFlags.map((flag) => (
            <TerminalChip
              key={flag.label}
              variant={flag.value === false ? 'info' : 'neutral'}
              className="font-mono"
            >
              {flag.label}={String(flag.value)}
            </TerminalChip>
          )) : (
            <span className="font-mono text-xs text-white/55">--</span>
          )}
        </div>
      </TerminalNestedBlock>
      <div className="flex flex-col gap-2">
        {folds.length > 0 ? folds.map((fold, index) => {
          const foldIndex = getNumber(fold, ['foldIndex', 'fold_index']) ?? index + 1;
          const trainWindow = getRecord(fold, ['trainWindow', 'train_window']);
          const testWindow = getRecord(fold, ['testWindow', 'test_window']);
          return (
            <TerminalNestedBlock key={getString(fold, ['foldId', 'fold_id']) || `stored-oos-fold-${index}`}>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-medium text-white/88">{getDiagnosticWindowLabel(language, foldIndex)}</p>
                <TerminalChip variant="neutral" className="font-mono">
                  {getString(fold, ['state']) || '--'}
                </TerminalChip>
              </div>
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                <div>
                  <p className="text-[11px] text-white/35">{language === 'en' ? 'Train window' : '训练窗口'}</p>
                  <p className="mt-1 font-mono text-xs leading-5 text-white/68">
                    {formatWindowRange(
                      getString(trainWindow, ['startDate', 'start_date']),
                      getString(trainWindow, ['endDate', 'end_date']),
                    )}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] text-white/35">{language === 'en' ? 'Test window' : '测试窗口'}</p>
                  <p className="mt-1 font-mono text-xs leading-5 text-white/68">
                    {formatWindowRange(
                      getString(testWindow, ['startDate', 'start_date']),
                      getString(testWindow, ['endDate', 'end_date']),
                    )}
                  </p>
                </div>
              </div>
            </TerminalNestedBlock>
          );
        }) : (
          <TerminalNotice variant="neutral">
            {language === 'en'
              ? 'Stored OOS diagnostic windows are not present in this export.'
              : '当前导出未包含已存储的 OOS 诊断窗口。'}
          </TerminalNotice>
        )}
      </div>
    </div>
  );
}

const SupportExportsDisclosureBody: React.FC<BacktestSupportExportsDisclosureProps> = ({ runId, code }) => {
  const { language, t } = useI18n();
  const [items, setItems] = useState<RuleBacktestSupportExportIndexItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<SupportExportDefinition['id'] | null>(null);
  const [robustnessPreview, setRobustnessPreview] = useState<RobustnessEvidencePreviewState>({ status: 'idle' });

  const refreshIndex = async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const payload = await backtestApi.getRuleBacktestSupportExportIndex(runId);
      setItems(payload.exports || []);
    } catch (error) {
      setLoadError(getApiErrorMessage(error, t('backtest.resultPage.supportExports.loadFailed')));
    } finally {
      setIsLoading(false);
    }
  };

  const loadIndex = useEffectEvent(async () => {
    await refreshIndex();
  });

  useEffect(() => {
    void loadIndex();
  }, [runId, t]);

  const robustnessEvidenceItem = getSupportExportItem(
    SUPPORT_EXPORT_DEFINITIONS.find((definition) => definition.id === 'robustnessEvidenceJson')!,
    items,
  );

  useEffect(() => {
    if (robustnessEvidenceItem?.available !== true || robustnessPreview.status !== 'idle') {
      return;
    }
    let active = true;
    setRobustnessPreview({ status: 'loading' });
    void backtestApi.getRuleBacktestRobustnessEvidenceJson(runId)
      .then((payload) => {
        if (!active) {
          return;
        }
        setRobustnessPreview({ status: 'ready', payload });
      })
      .catch((error) => {
        if (!active) {
          return;
        }
        setRobustnessPreview({
          status: 'error',
          message: getApiErrorMessage(error, t('backtest.resultPage.supportExports.downloadFailed')),
        });
      });
    return () => {
      active = false;
    };
  }, [robustnessEvidenceItem?.available, robustnessPreview.status, runId, t]);

  const handleDownload = async (definition: SupportExportDefinition) => {
    setDownloadError(null);
    setDownloadingId(definition.id);
    try {
      const content = await definition.loadContent(runId);
      downloadTextFile(definition.fileName(code, runId), content, definition.mimeType);
    } catch (error) {
      setDownloadError(getApiErrorMessage(error, t('backtest.resultPage.supportExports.downloadFailed')));
    } finally {
      setDownloadingId(null);
    }
  };

  const getAvailabilityText = (item: RuleBacktestSupportExportIndexItem | null): string => {
    if (!item) {
      return t('backtest.resultPage.supportExports.availability.missingFromIndex');
    }
    if (item.availabilityReason === 'ready') {
      return t('backtest.resultPage.supportExports.availability.ready');
    }
    if (item.availabilityReason === 'execution_trace_rows_missing') {
      return t('backtest.resultPage.supportExports.availability.executionTraceRowsMissing');
    }
    return t('backtest.resultPage.supportExports.availability.fallback', {
      reason: item.availabilityReason || '--',
    });
  };

  const getDefinitionCopy = (
    definition: SupportExportDefinition,
    key: 'label' | 'description' | 'action',
  ): string => {
    const translationKey = definition[`${key}Key`];
    if (translationKey) {
      return t(translationKey);
    }
    const localizedCopy = definition[key];
    return localizedCopy?.[language] ?? localizedCopy?.zh ?? '';
  };

  const visibleDefinitions = SUPPORT_EXPORT_DEFINITIONS.filter((definition) => {
    if (!definition.onlyRenderWhenAvailable) {
      return true;
    }
    return getSupportExportItem(definition, items)?.available === true;
  });

  if (isLoading) {
    return <p className="text-xs leading-5 text-white/45">{t('backtest.resultPage.supportExports.loading')}</p>;
  }

  if (loadError) {
    return (
      <div className="flex flex-col gap-3">
        <TerminalNotice variant="danger">{loadError}</TerminalNotice>
        <div>
          <TerminalButton variant="compact" onClick={() => void refreshIndex()}>
            {t('backtest.resultPage.supportExports.retry')}
          </TerminalButton>
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <TerminalEmptyState title={t('backtest.resultPage.supportExports.title')}>
        {t('backtest.resultPage.supportExports.empty')}
      </TerminalEmptyState>
    );
  }

  if (visibleDefinitions.length === 0) {
    return (
      <TerminalEmptyState title={t('backtest.resultPage.supportExports.title')}>
        {t('backtest.resultPage.supportExports.empty')}
      </TerminalEmptyState>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <TerminalNotice variant="info">
        {t('backtest.resultPage.supportExports.intro')}
      </TerminalNotice>
      <p className="text-xs leading-5 text-white/35">{t('backtest.resultPage.supportExports.note')}</p>
      {downloadError ? <TerminalNotice variant="danger">{downloadError}</TerminalNotice> : null}
      {visibleDefinitions.map((definition) => {
        const item = getSupportExportItem(definition, items);
        const isAvailable = item?.available === true;
        const isDownloading = downloadingId === definition.id;
        return (
          <TerminalNestedBlock
            key={definition.id}
            className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between"
          >
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-medium text-white/88">{getDefinitionCopy(definition, 'label')}</p>
                <TerminalChip variant={isAvailable ? 'success' : 'neutral'}>
                  {isAvailable
                    ? t('backtest.resultPage.supportExports.available')
                    : t('backtest.resultPage.supportExports.unavailable')}
                </TerminalChip>
              </div>
              <p className="mt-2 text-xs leading-5 text-white/48">{getDefinitionCopy(definition, 'description')}</p>
              <p className="mt-2 text-[11px] leading-5 text-white/35">{getAvailabilityText(item)}</p>
              {definition.id === 'robustnessEvidenceJson' && isAvailable ? (
                <TerminalDisclosure
                  title="OOS diagnostic evidence"
                  summary={language === 'en' ? 'Stored diagnostic windows preview' : '已存储诊断窗口预览'}
                  className="mt-3"
                  data-testid="backtest-oos-diagnostic-evidence-disclosure"
                >
                  {robustnessPreview.status === 'loading' ? (
                    <p className="text-xs leading-5 text-white/45">
                      {language === 'en' ? 'Loading stored OOS diagnostic evidence…' : '正在加载已存储的 OOS 诊断证据…'}
                    </p>
                  ) : null}
                  {robustnessPreview.status === 'error' ? (
                    <TerminalNotice variant="danger">{robustnessPreview.message}</TerminalNotice>
                  ) : null}
                  {robustnessPreview.status === 'ready'
                    ? renderRobustnessEvidencePreview(robustnessPreview.payload, language)
                    : null}
                </TerminalDisclosure>
              ) : null}
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <TerminalButton
                variant="compact"
                onClick={() => void handleDownload(definition)}
                disabled={!isAvailable || isDownloading}
              >
                {isDownloading ? t('backtest.resultPage.supportExports.downloading') : getDefinitionCopy(definition, 'action')}
              </TerminalButton>
            </div>
          </TerminalNestedBlock>
        );
      })}
    </div>
  );
};

const BacktestSupportExportsDisclosure: React.FC<BacktestSupportExportsDisclosureProps> = ({ runId, code }) => {
  const { t } = useI18n();

  return (
    <TerminalDisclosure
      title={t('backtest.resultPage.supportExports.title')}
      summary={t('backtest.resultPage.supportExports.summary')}
      className="mt-4"
      data-testid="backtest-support-exports-disclosure"
    >
      <SupportExportsDisclosureBody key={runId} runId={runId} code={code} />
    </TerminalDisclosure>
  );
};

export default BacktestSupportExportsDisclosure;
