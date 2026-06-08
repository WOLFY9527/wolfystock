import type React from 'react';
import { Suspense, lazy, useEffect, useReducer } from 'react';
import { historyApi } from '../../api/history';
import { Drawer } from '../common/Drawer';
import { SupportPanel } from '../common/SupportSurface';
import { consumerSafeReportText } from '../../utils/homeReportIdentity';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';
import { localizeReportHeadingLabel, localizeReportTermLabel } from '../../utils/reportTerminology';
import type { ReportLanguage, StandardReport } from '../../types/analysis';
import {
  buildMissingFieldAudit,
  collectMissingFieldEntriesFromMarkdown,
  collectMissingFieldEntriesFromStandardReport,
  type MissingFieldCategory,
} from './missingFieldAudit';

interface ReportMarkdownProps {
  recordId: number;
  stockName: string;
  stockCode: string;
  onClose: () => void;
  reportLanguage?: ReportLanguage;
  standardReport?: StandardReport;
  initialContent?: string;
}

interface ReportMarkdownState {
  fetchedContent: string;
  loadedRecordId: number | null;
  isLoading: boolean;
  error: string | null;
  isOpen: boolean;
  hasOpenedTechnicalDetails: boolean;
}

type ReportMarkdownAction =
  | { type: 'loadStarted' }
  | { type: 'loadSucceeded'; content: string; recordId: number }
  | { type: 'loadFailed'; error: string; recordId: number }
  | { type: 'close' }
  | { type: 'openTechnicalDetails' };

const createInitialReportMarkdownState = (initialContent: string | undefined): ReportMarkdownState => ({
  fetchedContent: '',
  loadedRecordId: null,
  isLoading: initialContent === undefined,
  error: null,
  isOpen: true,
  hasOpenedTechnicalDetails: false,
});

function reportMarkdownReducer(state: ReportMarkdownState, action: ReportMarkdownAction): ReportMarkdownState {
  switch (action.type) {
    case 'loadStarted':
      return {
        ...state,
        isLoading: true,
        error: null,
      };
    case 'loadSucceeded':
      return {
        ...state,
        fetchedContent: action.content,
        loadedRecordId: action.recordId,
        isLoading: false,
        error: null,
      };
    case 'loadFailed':
      return {
        ...state,
        fetchedContent: '',
        loadedRecordId: action.recordId,
        isLoading: false,
        error: action.error,
      };
    case 'close':
      return {
        ...state,
        isOpen: false,
      };
    case 'openTechnicalDetails':
      if (state.hasOpenedTechnicalDetails) {
        return state;
      }
      return {
        ...state,
        hasOpenedTechnicalDetails: true,
      };
    default:
      return state;
  }
}

const LazyReportMarkdownTechnicalDetailsRenderer = lazy(async () => {
  const module = await import('./ReportMarkdownTechnicalDetailsRenderer');
  return { default: module.ReportMarkdownTechnicalDetailsRenderer };
});

const REPORT_MARKDOWN_INTERNAL_COPY_PATTERN =
  /reasonCode|reasonCodes|reason_code|reason_codes|reasonFamilies|sourceTier|sourceType|source_tier|source_type|provider|trace|raw[_\s-]*(?:json|result|payload|ai[_\s-]*response)|backend|snake_case|cache|debug|runtime|diagnostic|diagnostics|fallback_cache|provider_timeout|\b[a-z]+(?:_[a-z0-9]+)+\b/i;

const getObservationFallback = (language: ReportLanguage): string =>
  language === 'en' ? 'Continue tracking' : '继续跟踪';

const getSummaryFallback = (language: ReportLanguage): string =>
  language === 'en' ? 'Report content is available for review.' : '报告内容已生成，可继续复核。';

const getRiskBoundaryFallback = (language: ReportLanguage): string =>
  language === 'en'
    ? 'Risk boundary describes uncertainty only.'
    : '风险边界用于说明不确定性。';

const getUnstatedFallback = (language: ReportLanguage): string =>
  language === 'en' ? 'Unstated' : '未标注';

const getCoverageBoundaryText = (totalMissingFields: number, language: ReportLanguage): string => {
  if (totalMissingFields > 0) {
    return language === 'en'
      ? 'Some data is temporarily unavailable; read the current view as observation only.'
      : '部分数据暂不可用，当前解读仅供观察。';
  }
  return language === 'en'
    ? 'No obvious coverage gaps were detected.'
    : '数据覆盖未发现明显缺口。';
};

const consumerSafeMarkdownCopy = (
  value: unknown,
  fallback: string,
): string => {
  const text = String(value ?? '').trim();
  if (!text || text === '-' || /^n\/?a$/i.test(text)) {
    return fallback;
  }
  if (REPORT_MARKDOWN_INTERNAL_COPY_PATTERN.test(text)) {
    return fallback;
  }
  const safeText = consumerSafeReportText(text, fallback).trim();
  if (!safeText || safeText === '--' || REPORT_MARKDOWN_INTERNAL_COPY_PATTERN.test(safeText)) {
    return fallback;
  }
  return safeText;
};

const coverageCategoryConsumerLabel = (category: MissingFieldCategory, language: ReportLanguage): string => {
  if (category === 'integrated_unavailable') {
    return language === 'en' ? 'Temporarily unavailable' : '本次暂未返回';
  }
  if (category === 'not_integrated_yet') {
    return language === 'en' ? 'Not covered yet' : '暂不覆盖';
  }
  if (category === 'source_not_provided') {
    return language === 'en' ? 'Partially unavailable' : '部分数据暂不可用';
  }
  if (category === 'not_applicable') {
    return language === 'en' ? 'Not applicable now' : '本次不适用';
  }
  return language === 'en' ? 'Other data gaps' : '其他数据缺口';
};

const ReportMarkdownHeaderPanel: React.FC<{
  body: string;
  stockCode: string;
  stockName: string;
}> = ({ body, stockCode, stockName }) => (
  <SupportPanel
    className="mb-1 px-5 py-4 md:px-6"
    title={stockName || stockCode}
    body={body}
    icon={(
      <div className="flex size-8 items-center justify-center rounded-lg bg-[var(--home-action-report-bg)] text-[var(--home-action-report-text)]">
        <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
    )}
    titleClassName="mt-0 text-base font-semibold"
    bodyClassName="text-sm"
  />
);

const ReportMarkdownStatusPanel: React.FC<{
  error: string | null;
  handleClose: () => void;
  isLoading: boolean;
  text: ReturnType<typeof getReportText>;
}> = ({ error, handleClose, isLoading, text }) => {
  if (isLoading) {
    return (
      <SupportPanel
        centered
        className="flex h-64 flex-col items-center justify-center p-6"
        icon={<div className="home-spinner size-10 animate-spin border-[3px]" />}
        title={text.loadingReport}
        body={text.markdownLoadingBody}
      />
    );
  }

  if (!error) {
    return null;
  }

  return (
    <SupportPanel
      centered
      className="flex h-64 flex-col items-center justify-center p-6"
      icon={(
        <div className="flex size-12 items-center justify-center rounded-xl bg-danger/10">
          <svg className="size-6 text-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
      )}
      title={error}
      body={text.markdownErrorBody}
      titleClassName="text-danger"
      actions={(
        <button
          type="button"
          onClick={handleClose}
          className="home-surface-button rounded-lg px-4 py-2 text-sm text-secondary-text"
        >
          {text.dismiss}
        </button>
      )}
    />
  );
};

type ReportMarkdownLoadedContentProps = {
  captionClassName: string;
  colon: string;
  coverageAudit: ReturnType<typeof buildMissingFieldAudit>;
  coverageBuckets: Array<ReturnType<typeof buildMissingFieldAudit>['buckets'][number]>;
  dispatch: React.Dispatch<ReportMarkdownAction>;
  executiveSummary: {
    coverageBoundary: string;
    confidence: string;
    firstLine: string;
    keyRisk: string;
    observation: string;
  };
  headingClassName: string;
  localizedMarkdownContent: string;
  normalizedLanguage: ReportLanguage;
  state: ReportMarkdownState;
  text: ReturnType<typeof getReportText>;
};

const ReportMarkdownCoverageAuditPanel: React.FC<{
  captionClassName: string;
  colon: string;
  coverageAudit: ReturnType<typeof buildMissingFieldAudit>;
  coverageBuckets: Array<ReturnType<typeof buildMissingFieldAudit>['buckets'][number]>;
  headingClassName: string;
  normalizedLanguage: ReportLanguage;
  text: ReturnType<typeof getReportText>;
}> = ({
  captionClassName,
  colon,
  coverageAudit,
  coverageBuckets,
  headingClassName,
  normalizedLanguage,
  text,
}) => (
  <SupportPanel
    className="px-0 py-0"
    title={normalizedLanguage === 'en' ? 'Data coverage notes' : '数据覆盖说明'}
    body={normalizedLanguage === 'en' ? 'Grouped as product-readable data gaps.' : '按用户可读的数据缺口归类。'}
    titleClassName={headingClassName}
    bodyClassName="text-sm leading-6"
    contentClassName="mt-3"
  >
    {coverageAudit.totalMissingFields > 0 ? (
      <div className="space-y-3 text-xs text-secondary-text">
        <p className={captionClassName}>
          {text.missingFieldsTotal}{colon}{coverageAudit.totalMissingFields}
        </p>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {coverageBuckets.map((bucket) => (
            <div key={bucket.category} className="rounded-xl border border-[var(--theme-panel-subtle-border)] bg-base/40 px-3 py-2.5">
              <p className={captionClassName}>
                {coverageCategoryConsumerLabel(bucket.category, normalizedLanguage)} ({bucket.entries.length})
              </p>
              <ul className="mt-2.5 space-y-1.5">
                {bucket.entries.slice(0, 5).map((entry, index) => (
                  <li key={`${entry.field}-${entry.reason}-${index}`}>
                    <span className="font-medium text-foreground">{localizeReportTermLabel(entry.field, normalizedLanguage)}</span>
                    <span className="text-muted-text">{colon}{localizeReportHeadingLabel(entry.reason, normalizedLanguage)}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    ) : (
      <p className="text-xs text-muted-text">{text.noMissingFields}</p>
    )}
  </SupportPanel>
);

const ReportMarkdownLoadedContent: React.FC<ReportMarkdownLoadedContentProps> = ({
  captionClassName,
  colon,
  coverageAudit,
  coverageBuckets,
  dispatch,
  executiveSummary,
  headingClassName,
  localizedMarkdownContent,
  normalizedLanguage,
  state,
  text,
}) => (
  <div className="space-y-5" data-testid="full-report-reading-surface">
    <div data-testid="report-executive-summary">
      <SupportPanel
        className="px-5 py-4 md:px-6"
        title={normalizedLanguage === 'en' ? 'Executive Summary' : '执行摘要'}
        body={executiveSummary.firstLine}
        titleClassName={headingClassName}
        bodyClassName="text-sm leading-6 text-secondary-text"
      >
        <div className="grid gap-2 text-xs text-secondary-text sm:grid-cols-3">
          {[
            { label: normalizedLanguage === 'en' ? 'Decision' : '结论', value: executiveSummary.observation },
            { label: normalizedLanguage === 'en' ? 'Confidence' : '置信度', value: executiveSummary.confidence },
            { label: normalizedLanguage === 'en' ? 'Key risk' : '关键风险', value: executiveSummary.keyRisk },
          ].map((item) => (
            <div key={item.label} className="rounded-xl border border-[var(--theme-panel-subtle-border)] bg-base/35 px-3 py-2.5">
              <p className={captionClassName}>{item.label}</p>
              <p className="mt-1.5 break-words leading-5 text-foreground/80">{item.value}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 rounded-xl border border-[var(--theme-panel-subtle-border)] bg-base/35 px-3 py-2 text-xs leading-5 text-secondary-text">
          {executiveSummary.coverageBoundary}
        </p>
      </SupportPanel>
    </div>

    <details
      data-testid="report-technical-evidence-details"
      className="theme-panel-subtle rounded-[var(--cohere-radius-medium)] px-5 py-4 md:px-6"
      onToggle={(event) => {
        if (event.currentTarget.open) {
          dispatch({ type: 'openTechnicalDetails' });
        }
      }}
    >
      <summary className="cursor-pointer list-none text-sm font-semibold tracking-[0.06em] text-foreground">
        {normalizedLanguage === 'en' ? 'Coverage and evidence details' : '数据覆盖与证据明细'}
      </summary>
      {state.hasOpenedTechnicalDetails ? (
        <div className="mt-4 space-y-4" data-testid="report-coverage-audit-panel">
          <ReportMarkdownCoverageAuditPanel
            captionClassName={captionClassName}
            colon={colon}
            coverageAudit={coverageAudit}
            coverageBuckets={coverageBuckets}
            headingClassName={headingClassName}
            normalizedLanguage={normalizedLanguage}
            text={text}
          />
          <div className="mx-auto w-full max-w-[86ch]">
            <Suspense
              fallback={(
                <output
                  aria-live="polite"
                  aria-busy="true"
                  data-testid="report-technical-details-loading"
                  className="block rounded-xl border border-[var(--theme-panel-subtle-border)] bg-base/35 p-3 text-sm text-secondary-text"
                >
                  {normalizedLanguage === 'en' ? 'Loading report details…' : '正在加载报告明细…'}
                </output>
              )}
            >
              <LazyReportMarkdownTechnicalDetailsRenderer markdown={localizedMarkdownContent} />
            </Suspense>
          </div>
        </div>
      ) : null}
    </details>
  </div>
);

/**
 * Markdown 报告抽屉组件
 * 使用通用 Drawer 组件，展示完整的 Markdown 格式分析报告
 */
export const ReportMarkdown: React.FC<ReportMarkdownProps> = ({
  recordId,
  stockName,
  stockCode,
  onClose,
  reportLanguage = 'zh',
  standardReport,
  initialContent,
}) => {
  const normalizedLanguage = normalizeReportLanguage(reportLanguage);
  const text = getReportText(normalizedLanguage);
  const headingClassName = normalizedLanguage === 'en'
    ? 'text-sm font-semibold uppercase tracking-[0.12em]'
    : 'text-sm font-semibold tracking-[0.06em]';
  const captionClassName = normalizedLanguage === 'en'
    ? 'text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-text'
    : 'text-xs font-semibold tracking-[0.08em] text-muted-text';
  const colon = normalizedLanguage === 'en' ? ': ' : '：';
  const loadReportFailedText = text.loadReportFailed;
  const [state, dispatch] = useReducer(reportMarkdownReducer, initialContent, createInitialReportMarkdownState);
  const content = initialContent ?? (state.loadedRecordId === recordId ? state.fetchedContent : '');
  const isLoading = initialContent === undefined && (state.isLoading || state.loadedRecordId !== recordId);
  const error = initialContent === undefined && state.loadedRecordId === recordId ? state.error : null;

  const coverageAudit = (() => {
    const mergedEntries = [
      ...collectMissingFieldEntriesFromStandardReport(standardReport),
      ...collectMissingFieldEntriesFromMarkdown(content),
    ];
    return buildMissingFieldAudit(mergedEntries);
  })();

  const localizedMarkdownContent = (() => {
    if (normalizedLanguage !== 'zh') {
      return content;
    }

    const translateTableHeaderLine = (line: string): string => {
      if (!line.trim().startsWith('|')) {
        return line;
      }
      return line
        .replace(/\bField\b/gi, '字段')
        .replace(/\bValue\b/gi, '数值')
        .replace(/\bBasis\b/gi, '口径')
        .replace(/\bSource\b/gi, '来源')
        .replace(/\bStatus\b/gi, '状态')
        .replace(/\bMissing Cause\b/gi, '缺失原因')
        .replace(/\bPriority\b/gi, '优先级');
    };

    return content
      .split('\n')
      .map((line) => {
        const headingMatch = line.match(/^(\s{0,3}#{1,6}\s+)(.+)$/);
        if (headingMatch?.[1] && headingMatch?.[2]) {
          const translatedHeading = localizeReportHeadingLabel(headingMatch[2], 'zh');
          return `${headingMatch[1]}${translatedHeading}`;
        }

        const bulletBoldMatch = line.match(/^(\s*[-*+]\s+\*\*)([^*]+)(\*\*\s*[:：]?\s*)(.*)$/);
        if (bulletBoldMatch?.[1] && bulletBoldMatch?.[2] && bulletBoldMatch?.[3]) {
          const translatedLabel = localizeReportHeadingLabel(bulletBoldMatch[2], 'zh');
          return `${bulletBoldMatch[1]}${translatedLabel}${bulletBoldMatch[3]}${bulletBoldMatch[4] || ''}`;
        }

        const bulletPlainMatch = line.match(/^(\s*[-*+]\s+)(.+)$/);
        if (bulletPlainMatch?.[1] && bulletPlainMatch?.[2]) {
          const translatedLabel = localizeReportHeadingLabel(bulletPlainMatch[2], 'zh');
          if (translatedLabel !== bulletPlainMatch[2]) {
            return `${bulletPlainMatch[1]}${translatedLabel}`;
          }
        }

        return translateTableHeaderLine(line);
      })
      .join('\n');
  })();

  const coverageBuckets = coverageAudit.buckets.filter((bucket) => bucket.entries.length > 0);
  const executiveSummary = (() => {
    const summaryPanel = standardReport?.summaryPanel;
    const decisionPanel = standardReport?.decisionPanel;
    const reasonLayer = standardReport?.reasonLayer;
    const highlights = standardReport?.highlights;
    const firstLine = String(
      summaryPanel?.oneSentence
      || reasonLayer?.latestKeyUpdate
      || content.split('\n').find((line) => line.trim() && !line.trim().startsWith('#'))
      || getSummaryFallback(normalizedLanguage),
    ).trim();
    const observation = String(
      summaryPanel?.operationAdvice
      || decisionPanel?.keyAction
      || getObservationFallback(normalizedLanguage),
    ).trim();
    const confidence = String(
      decisionPanel?.confidence
      || getUnstatedFallback(normalizedLanguage),
    ).trim();
    const keyRisk = String(
      reasonLayer?.topRisk
      || highlights?.riskAlerts?.[0]
      || decisionPanel?.riskControlStrategy
      || getRiskBoundaryFallback(normalizedLanguage),
    ).trim();
    return {
      coverageBoundary: getCoverageBoundaryText(coverageAudit.totalMissingFields, normalizedLanguage),
      firstLine: consumerSafeMarkdownCopy(firstLine, getSummaryFallback(normalizedLanguage)),
      observation: consumerSafeMarkdownCopy(observation, getObservationFallback(normalizedLanguage)),
      confidence: consumerSafeMarkdownCopy(confidence, getUnstatedFallback(normalizedLanguage)),
      keyRisk: consumerSafeMarkdownCopy(keyRisk, getRiskBoundaryFallback(normalizedLanguage)),
    };
  })();

  // Handle close with animation
  const handleClose = () => {
    dispatch({ type: 'close' });
    // Delay actual close to allow animation to complete
    setTimeout(onClose, 300);
  };

  useEffect(() => {
    if (initialContent !== undefined) {
      return;
    }

    let isCancelled = false;

    queueMicrotask(() => {
      if (isCancelled) {
        return;
      }

      dispatch({ type: 'loadStarted' });
      void historyApi.getMarkdown(recordId)
        .then((markdownContent) => ({ content: markdownContent, error: null as string | null }))
        .catch(() => ({
          content: '',
          error: loadReportFailedText,
        }))
        .then((result) => {
          if (isCancelled) {
            return;
          }

          if (result.error) {
            dispatch({ type: 'loadFailed', error: result.error, recordId });
            return;
          }

          dispatch({ type: 'loadSucceeded', content: result.content, recordId });
        });
    });

    return () => {
      isCancelled = true;
    };
  }, [initialContent, recordId, loadReportFailedText]);

  return (
    <Drawer isOpen={state.isOpen} onClose={handleClose} width="max-w-[min(96vw,112rem)]" zIndex={100}>
      <div className="mx-auto w-full max-w-[72rem] space-y-5 pb-1" data-testid="full-report-document-shell">
        <ReportMarkdownHeaderPanel body={text.fullReport} stockCode={stockCode} stockName={stockName} />
        <ReportMarkdownStatusPanel error={error} handleClose={handleClose} isLoading={isLoading} text={text} />
        {!isLoading && !error ? (
          <ReportMarkdownLoadedContent
            captionClassName={captionClassName}
            colon={colon}
            coverageAudit={coverageAudit}
            coverageBuckets={coverageBuckets}
            dispatch={dispatch}
            executiveSummary={executiveSummary}
            headingClassName={headingClassName}
            localizedMarkdownContent={localizedMarkdownContent}
            normalizedLanguage={normalizedLanguage}
            state={state}
            text={text}
          />
        ) : null}

        {/* Footer */}
        <div className="home-divider mt-6 flex justify-end border-t pt-4">
          <button
            type="button"
            onClick={handleClose}
            className="home-surface-button rounded-lg px-4 py-2 text-sm text-secondary-text hover:text-foreground"
          >
            {text.dismiss}
          </button>
        </div>
      </div>
    </Drawer>
  );
};
