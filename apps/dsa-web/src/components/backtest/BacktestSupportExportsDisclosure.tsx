import type React from 'react';
import { useCallback, useEffect, useState } from 'react';
import { backtestApi } from '../../api/backtest';
import { getApiErrorMessage } from '../../api/error';
import { useI18n } from '../../contexts/UiLanguageContext';
import type { RuleBacktestSupportExportIndexItem } from '../../types/backtest';
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

const SupportExportsDisclosureBody: React.FC<BacktestSupportExportsDisclosureProps> = ({ runId, code }) => {
  const { language, t } = useI18n();
  const [items, setItems] = useState<RuleBacktestSupportExportIndexItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<SupportExportDefinition['id'] | null>(null);

  const loadIndex = useCallback(async () => {
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
  }, [runId, t]);

  useEffect(() => {
    void loadIndex();
  }, [loadIndex]);

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
          <TerminalButton variant="compact" onClick={() => void loadIndex()}>
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
      <SupportExportsDisclosureBody runId={runId} code={code} />
    </TerminalDisclosure>
  );
};

export default BacktestSupportExportsDisclosure;
