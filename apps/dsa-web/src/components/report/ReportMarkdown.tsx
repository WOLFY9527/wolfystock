import type React from 'react';
import { Suspense, lazy, useEffect, useReducer, useState } from 'react';
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

type ReportExportState = 'idle' | 'copied' | 'copyFailed' | 'downloaded' | 'printReady';

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

const getObservationTime = (standardReport?: StandardReport): string =>
  String(
    standardReport?.summaryPanel?.snapshotTime
    || standardReport?.summaryPanel?.marketTime
    || '',
  ).trim();

const getReportGeneratedTime = (standardReport?: StandardReport): string =>
  String(standardReport?.summaryPanel?.reportGeneratedAt || '').trim();

const getReportExportStatusText = (state: ReportExportState, language: ReportLanguage): string => {
  if (state === 'copied') {
    return language === 'en' ? 'Report copied.' : '报告已复制。';
  }
  if (state === 'copyFailed') {
    return language === 'en' ? 'Copy unavailable.' : '复制暂不可用。';
  }
  if (state === 'downloaded') {
    return language === 'en' ? 'Markdown download started.' : 'Markdown 下载已开始。';
  }
  if (state === 'printReady') {
    return language === 'en' ? 'Print/PDF flow opened.' : '打印 / PDF 流程已打开。';
  }
  return '';
};

const buildReportExportFileName = (stockCode: string, stockName: string, generatedAt: string): string => {
  const safeName = `${stockName || stockCode || 'Report'}`
    .replace(/[^a-z0-9\u4e00-\u9fff]+/gi, '-')
    .replace(/^-+|-+$/g, '')
    || 'Report';
  const safeTicker = (stockCode || 'preview').replace(/[^a-z0-9]+/gi, '-').replace(/^-+|-+$/g, '') || 'preview';
  const safeDate = generatedAt.replace(/\D/g, '').slice(0, 8) || 'latest';
  return `WolfyStock_${safeName}_${safeTicker}_${safeDate}.md`;
};

const escapeHtmlText = (value: string): string =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

const consumerMarkdownStateCellLabel = (value: string, language: ReportLanguage): string | null => {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  if (normalized === 'mixed') {
    return language === 'en' ? 'Composite summary' : '综合摘要';
  }
  if (normalized === 'insufficient') {
    return language === 'en' ? 'Evidence insufficient' : '证据不足';
  }
  if (normalized === 'fallback') {
    return language === 'en' ? 'Supplemental snapshot' : '补充快照';
  }
  if (normalized === 'real') {
    return language === 'en' ? 'Observed data' : '已观察数据';
  }
  return null;
};

const getMarkdownBodyFallback = (language: ReportLanguage): string =>
  language === 'en' ? 'Continue tracking while evidence is reviewed.' : '继续跟踪，等待证据复核。';

const getMarkdownLinkFallback = (language: ReportLanguage): string =>
  language === 'en' ? 'Reference material' : '研究资料';

const MARKDOWN_CODE_FENCE_PATTERN = /^\s*(?:`{3,}|~{3,})/;
const MARKDOWN_LINK_PATTERN = /(!?\[)([^\]\n]*)(\]\()([^\s)\n]+)(?:\s+"([^"\n]*)")?(\))/g;

const consumerSafeMarkdownPlainText = (
  value: unknown,
  language: ReportLanguage,
  fallback = getMarkdownBodyFallback(language),
): string => {
  const text = String(value ?? '').trim();
  if (!text) {
    return '';
  }
  const stateLabel = consumerMarkdownStateCellLabel(text, language);
  if (stateLabel) {
    return stateLabel;
  }
  return consumerSafeMarkdownCopy(text, fallback);
};

const consumerSafeMarkdownAttribute = (value: string): string => {
  const safeValue = consumerSafeMarkdownCopy(value, '').trim();
  return safeValue === value.trim() ? safeValue : '';
};

const sanitizeMarkdownLinks = (value: string, language: ReportLanguage): string => (
  value.replace(
    MARKDOWN_LINK_PATTERN,
    (
      _match,
      open: string,
      label: string,
      linkOpen: string,
      url: string,
      title: string | undefined,
      close: string,
    ) => {
      const fallbackLabel = getMarkdownLinkFallback(language);
      const safeLabel = consumerSafeMarkdownPlainText(label, language, fallbackLabel);
      const safeUrl = consumerSafeMarkdownAttribute(url) || '#';
      const safeTitle = title === undefined ? '' : consumerSafeMarkdownAttribute(title);
      const titlePart = safeTitle ? ` "${safeTitle}"` : '';
      return `${open}${safeLabel}${linkOpen}${safeUrl}${titlePart}${close}`;
    },
  )
);

const consumerSafeMarkdownInline = (
  value: unknown,
  language: ReportLanguage,
  fallback = getMarkdownBodyFallback(language),
): string => {
  const linkedText = sanitizeMarkdownLinks(String(value ?? ''), language);
  return consumerSafeMarkdownPlainText(linkedText, language, fallback);
};

const sanitizeMarkdownTableCells = (line: string, language: ReportLanguage): string => {
  if (!line.trim().startsWith('|')) {
    return line;
  }
  return line.replace(/(\|\s*)([^|\n]+?)(\s*(?=\|))/g, (match, prefix: string, cell: string, suffix: string) => {
    const cellText = cell.trim();
    if (/^:?-{3,}:?$/.test(cellText)) {
      return match;
    }
    const safeCell = consumerSafeMarkdownInline(cellText, language);
    return `${prefix}${safeCell}${suffix}`;
  });
};

const translateMarkdownTableHeaderLine = (line: string, language: ReportLanguage): string => {
  if (language !== 'zh' || !line.trim().startsWith('|')) {
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

const localizeAndSanitizeMarkdownLine = (line: string, language: ReportLanguage): string => {
  const headingMatch = line.match(/^(\s{0,3}#{1,6}\s+)(.+)$/);
  if (headingMatch?.[1] && headingMatch?.[2]) {
    const headingText = language === 'zh'
      ? localizeReportHeadingLabel(headingMatch[2], 'zh')
      : headingMatch[2];
    return `${headingMatch[1]}${consumerSafeMarkdownInline(headingText, language, getSummaryFallback(language))}`;
  }

  const bulletBoldMatch = line.match(/^(\s*(?:[-*+]|\d+[.)])\s+\*\*)([^*]+)(\*\*\s*[:：]?\s*)(.*)$/);
  if (bulletBoldMatch?.[1] && bulletBoldMatch?.[2] && bulletBoldMatch?.[3]) {
    const labelText = language === 'zh'
      ? localizeReportHeadingLabel(bulletBoldMatch[2], 'zh')
      : bulletBoldMatch[2];
    const bodyText = bulletBoldMatch[4] || '';
    const safeLabel = consumerSafeMarkdownInline(labelText, language);
    const safeBody = bodyText ? consumerSafeMarkdownInline(bodyText, language) : '';
    return `${bulletBoldMatch[1]}${safeLabel}${bulletBoldMatch[3]}${safeBody}`;
  }

  const bulletPlainMatch = line.match(/^(\s*(?:[-*+]|\d+[.)])\s+)(.+)$/);
  if (bulletPlainMatch?.[1] && bulletPlainMatch?.[2]) {
    const bulletText = language === 'zh'
      ? localizeReportHeadingLabel(bulletPlainMatch[2], 'zh')
      : bulletPlainMatch[2];
    return `${bulletPlainMatch[1]}${consumerSafeMarkdownInline(bulletText, language)}`;
  }

  const tableLine = translateMarkdownTableHeaderLine(line, language);
  if (tableLine.trim().startsWith('|')) {
    return sanitizeMarkdownTableCells(tableLine, language);
  }

  return consumerSafeMarkdownInline(tableLine, language);
};

const localizeAndSanitizeMarkdownContent = (content: string, language: ReportLanguage): string => {
  let isInsideCodeFence = false;
  return content
    .split('\n')
    .map((line) => {
      if (MARKDOWN_CODE_FENCE_PATTERN.test(line)) {
        isInsideCodeFence = !isInsideCodeFence;
        return line;
      }
      if (isInsideCodeFence) {
        return line;
      }
      return localizeAndSanitizeMarkdownLine(line, language);
    })
    .join('\n');
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

const ReportMarkdownMetadataStrip: React.FC<{
  captionClassName: string;
  generatedAt: string;
  normalizedLanguage: ReportLanguage;
  observationTime: string;
}> = ({ captionClassName, generatedAt, normalizedLanguage, observationTime }) => {
  if (!observationTime && !generatedAt) {
    return null;
  }

  const rows = [
    {
      label: normalizedLanguage === 'en' ? 'Observation time' : '观察时间',
      value: observationTime || (normalizedLanguage === 'en' ? 'Unavailable' : '暂不可用'),
    },
    {
      label: normalizedLanguage === 'en' ? 'Report generated' : '报告生成时间',
      value: generatedAt || (normalizedLanguage === 'en' ? 'Unavailable' : '暂不可用'),
    },
  ];

  return (
    <div
      className="grid min-w-0 gap-2 rounded-[1rem] border border-[var(--theme-panel-subtle-border)] bg-base/35 p-3 text-xs text-secondary-text sm:grid-cols-2"
      data-testid="report-observation-time-strip"
    >
      {rows.map((row) => (
        <div key={row.label} className="min-w-0">
          <p className={captionClassName}>{row.label}</p>
          <p className="mt-1 break-words leading-5 text-foreground/80">{row.value}</p>
        </div>
      ))}
    </div>
  );
};

const ReportMarkdownExportControls: React.FC<{
  content: string;
  fileName: string;
  normalizedLanguage: ReportLanguage;
  stockCode: string;
  stockName: string;
}> = ({ content, fileName, normalizedLanguage, stockCode, stockName }) => {
  const [exportState, setExportState] = useState<ReportExportState>('idle');
  const hasContent = Boolean(content.trim());
  const statusText = getReportExportStatusText(exportState, normalizedLanguage);
  const buttonClassName = 'home-surface-button inline-flex min-h-10 shrink-0 items-center justify-center rounded-lg px-4 py-2 text-sm text-secondary-text hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50';

  const handleCopy = async () => {
    if (!hasContent || !navigator.clipboard?.writeText) {
      setExportState('copyFailed');
      return;
    }

    const error = await navigator.clipboard.writeText(content)
      .then(() => null)
      .catch((copyError) => copyError);
    setExportState(error ? 'copyFailed' : 'copied');
  };

  const handleDownload = () => {
    if (!hasContent) {
      return;
    }

    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
    setExportState('downloaded');
  };

  const handlePrint = () => {
    if (!hasContent) {
      return;
    }

    const printWindow = window.open('', '_blank', 'width=960,height=1200');
    if (!printWindow) {
      window.print();
      setExportState('printReady');
      return;
    }

    printWindow.opener = null;
    printWindow.document.open();
    printWindow.document.write(`
      <!doctype html>
      <html>
        <head>
          <title>${escapeHtmlText(stockName || stockCode)} - WolfyStock</title>
          <style>
            body { margin: 0; background: #fff; color: #111827; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
            main { max-width: 820px; margin: 0 auto; padding: 40px 34px; }
            pre { white-space: pre-wrap; word-break: break-word; font-family: inherit; line-height: 1.58; font-size: 13px; }
            @media print { main { padding: 0; } }
          </style>
        </head>
        <body><main><pre id="wolfystock-preview-print-report"></pre></main></body>
      </html>
    `);
    const reportNode = printWindow.document.getElementById('wolfystock-preview-print-report');
    if (reportNode) {
      reportNode.textContent = content;
    }
    printWindow.document.close();
    printWindow.focus();
    window.setTimeout(() => printWindow.print(), 80);
    setExportState('printReady');
  };

  return (
    <div
      className="flex min-w-0 flex-col gap-2 rounded-[1rem] border border-[var(--theme-panel-subtle-border)] bg-base/35 p-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between"
      data-testid="report-export-controls"
    >
      <p className="text-xs leading-5 text-muted-text">
        {normalizedLanguage === 'en'
          ? 'Exports preserve the visible research evidence and do not add advice.'
          : '导出内容保留当前研究证据，不新增投资建议。'}
      </p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={buttonClassName} disabled={!hasContent} onClick={() => { void handleCopy(); }}>
          {exportState === 'copied'
            ? (normalizedLanguage === 'en' ? 'Copied' : '已复制')
            : (normalizedLanguage === 'en' ? 'Copy report' : '复制报告')}
        </button>
        <button type="button" className={buttonClassName} disabled={!hasContent} onClick={handleDownload}>
          {normalizedLanguage === 'en' ? 'Download Markdown' : '下载 Markdown'}
        </button>
        <button type="button" className={buttonClassName} disabled={!hasContent} onClick={handlePrint}>
          {normalizedLanguage === 'en' ? 'Print / PDF' : '打印 / PDF'}
        </button>
      </div>
      {statusText ? (
        <p className="text-xs leading-5 text-secondary-text" role="status">
          {statusText}
        </p>
      ) : null}
    </div>
  );
};

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
    observationTime: string;
  };
  headingClassName: string;
  localizedMarkdownContent: string;
  normalizedLanguage: ReportLanguage;
  reportGeneratedAt: string;
  reportMarkdownFileName: string;
  state: ReportMarkdownState;
  stockCode: string;
  stockName: string;
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
  reportGeneratedAt,
  reportMarkdownFileName,
  state,
  stockCode,
  stockName,
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
        <ReportMarkdownMetadataStrip
          captionClassName={captionClassName}
          generatedAt={reportGeneratedAt}
          normalizedLanguage={normalizedLanguage}
          observationTime={executiveSummary.observationTime}
        />
      </SupportPanel>
    </div>

    <ReportMarkdownExportControls
      content={localizedMarkdownContent}
      fileName={reportMarkdownFileName}
      normalizedLanguage={normalizedLanguage}
      stockCode={stockCode}
      stockName={stockName}
    />

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

  const localizedMarkdownContent = localizeAndSanitizeMarkdownContent(content, normalizedLanguage);

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
    const observationTime = getObservationTime(standardReport);
    return {
      coverageBoundary: getCoverageBoundaryText(coverageAudit.totalMissingFields, normalizedLanguage),
      firstLine: consumerSafeMarkdownCopy(firstLine, getSummaryFallback(normalizedLanguage)),
      observation: consumerSafeMarkdownCopy(observation, getObservationFallback(normalizedLanguage)),
      observationTime,
      confidence: consumerSafeMarkdownCopy(confidence, getUnstatedFallback(normalizedLanguage)),
      keyRisk: consumerSafeMarkdownCopy(keyRisk, getRiskBoundaryFallback(normalizedLanguage)),
    };
  })();
  const reportGeneratedAt = getReportGeneratedTime(standardReport);
  const reportMarkdownFileName = buildReportExportFileName(stockCode, stockName, reportGeneratedAt);

  const handleClose = () => {
    dispatch({ type: 'close' });
    onClose();
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
            reportGeneratedAt={reportGeneratedAt}
            reportMarkdownFileName={reportMarkdownFileName}
            state={state}
            stockCode={stockCode}
            stockName={stockName}
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
