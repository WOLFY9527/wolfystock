import type React from 'react';
import { Suspense, lazy, useEffect, useState } from 'react';
import { historyApi } from '../../api/history';
import { Drawer } from '../common/Drawer';
import { SupportPanel } from '../common';
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

const LazyReportMarkdownTechnicalDetailsRenderer = lazy(async () => {
  const module = await import('./ReportMarkdownTechnicalDetailsRenderer');
  return { default: module.ReportMarkdownTechnicalDetailsRenderer };
});

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
  const [content, setContent] = useState<string>(initialContent ?? '');
  const [isLoading, setIsLoading] = useState(initialContent === undefined);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(true);
  const [hasOpenedTechnicalDetails, setHasOpenedTechnicalDetails] = useState(false);

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
      || (normalizedLanguage === 'en' ? 'Report content is available for review.' : '报告内容已生成，可继续复核。'),
    ).trim();
    const observation = String(
      summaryPanel?.operationAdvice
      || decisionPanel?.keyAction
      || (normalizedLanguage === 'en' ? 'Observation only' : '仅观察'),
    ).trim();
    const confidence = String(
      decisionPanel?.confidence
      || (normalizedLanguage === 'en' ? 'Unstated' : '未标注'),
    ).trim();
    const keyRisk = String(
      reasonLayer?.topRisk
      || highlights?.riskAlerts?.[0]
      || decisionPanel?.riskControlStrategy
      || (normalizedLanguage === 'en' ? 'No explicit risk item in the structured report.' : '结构化报告未给出明确风险条目。'),
    ).trim();
    return { firstLine, observation, confidence, keyRisk };
  })();

  const coverageCategoryLabel = (category: MissingFieldCategory): string => {
    if (category === 'integrated_unavailable') {
      return text.missingIntegratedUnavailable;
    }
    if (category === 'not_integrated_yet') {
      return text.missingNotIntegratedYet;
    }
    if (category === 'source_not_provided') {
      return text.missingSourceNotProvided;
    }
    if (category === 'not_applicable') {
      return text.missingNotApplicable;
    }
    return text.missingOther;
  };

  // Handle close with animation
  const handleClose = () => {
    setIsOpen(false);
    // Delay actual close to allow animation to complete
    setTimeout(onClose, 300);
  };

  useEffect(() => {
    if (initialContent !== undefined) {
      setContent(initialContent);
      setIsLoading(false);
      setError(null);
      return;
    }

    let isMounted = true;

    const fetchMarkdown = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const markdownContent = await historyApi.getMarkdown(recordId);
        if (isMounted) {
          setContent(markdownContent);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : loadReportFailedText);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchMarkdown();

    return () => {
      isMounted = false;
    };
  }, [initialContent, recordId, loadReportFailedText]);

  return (
    <Drawer isOpen={isOpen} onClose={handleClose} width="max-w-[min(96vw,112rem)]" zIndex={100}>
      <div className="mx-auto w-full max-w-[72rem] space-y-5 pb-1" data-testid="full-report-document-shell">
        <SupportPanel
          className="mb-1 px-5 py-4 md:px-6"
          title={stockName || stockCode}
          body={text.fullReport}
          icon={(
            <div className="flex size-8 items-center justify-center rounded-lg bg-[var(--home-action-report-bg)] text-[var(--home-action-report-text)]">
              <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
          )}
          titleClassName="mt-0 text-base font-semibold"
          bodyClassName="text-sm"
        >
        </SupportPanel>

        {isLoading ? (
          <SupportPanel
            centered
            className="flex h-64 flex-col items-center justify-center p-6"
            icon={<div className="home-spinner size-10 animate-spin border-[3px]" />}
            title={text.loadingReport}
            body={text.markdownLoadingBody}
          />
        ) : error ? (
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
        ) : (
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
              </SupportPanel>
            </div>

            <SupportPanel
              className="px-5 py-4 md:px-6"
              title={text.coverageAuditTitle}
              body={text.coverageAuditBody}
              titleClassName={headingClassName}
              bodyClassName="text-sm leading-6"
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
                          {coverageCategoryLabel(bucket.category)} ({bucket.entries.length})
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

            <details
              data-testid="report-technical-evidence-details"
              className="theme-panel-subtle rounded-[var(--cohere-radius-medium)] px-5 py-4 md:px-6"
              onToggle={(event) => {
                if (event.currentTarget.open) {
                  setHasOpenedTechnicalDetails(true);
                }
              }}
            >
              <summary className="cursor-pointer list-none text-sm font-semibold tracking-[0.06em] text-foreground">
                {normalizedLanguage === 'en' ? 'Technical details' : '技术细节'}
              </summary>
              <div className="mt-4 mx-auto w-full max-w-[86ch]">
                {hasOpenedTechnicalDetails ? (
                  <Suspense
                    fallback={(
                      <div
                        role="status"
                        aria-live="polite"
                        aria-busy="true"
                        data-testid="report-technical-details-loading"
                        className="rounded-xl border border-[var(--theme-panel-subtle-border)] bg-base/35 p-3 text-sm text-secondary-text"
                      >
                        {normalizedLanguage === 'en' ? 'Loading technical details…' : '正在加载技术细节…'}
                      </div>
                    )}
                  >
                    <LazyReportMarkdownTechnicalDetailsRenderer markdown={localizedMarkdownContent} />
                  </Suspense>
                ) : null}
              </div>
            </details>
          </div>
        )}

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
