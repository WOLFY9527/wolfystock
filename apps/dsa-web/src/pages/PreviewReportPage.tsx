import type React from 'react';
import { Suspense, lazy } from 'react';
import { WorkspacePageHeader } from '../components/common/WorkspacePageHeader';
import { TerminalPageShell } from '../components/terminal/TerminalPrimitives';
import { previewChartFixtures, previewReport } from '../dev/reportPreviewFixture';
import { normalizeFrontendReportContract } from '../api/reportNormalizer';
import { useI18n } from '../contexts/UiLanguageContext';

const LazyStandardReportPanel = lazy(async () => {
  const module = await import('../components/report/StandardReportPanel');
  return { default: module.StandardReportPanel };
});

const PreviewReportPage: React.FC = () => {
  const { t } = useI18n();
  const normalizedPreviewReport = normalizeFrontendReportContract(previewReport);

  return (
    <TerminalPageShell
      className="flex-1 min-h-0 min-w-0 py-5 md:py-6"
      data-testid="preview-report-page"
    >
      <WorkspacePageHeader
        eyebrow={t('previewReport.eyebrow')}
        title={t('previewReport.title')}
        description={t('previewReport.description')}
        className="shrink-0"
      />

      <Suspense
        fallback={(
          <div
            data-testid="preview-report-loading"
            aria-busy="true"
            aria-live="polite"
            aria-label={t('previewReport.title')}
            className="theme-panel-subtle rounded-[1.25rem] p-5 md:px-6"
          >
            <div className="flex items-center gap-3">
              <div className="home-spinner size-5 animate-spin border-2" />
              <div className="flex-1 space-y-2">
                <p className="text-sm text-secondary-text">{t('app.loading')}</p>
                <div className="h-3 w-32 rounded-full bg-white/10" />
                <div className="h-3 w-full max-w-[22rem] rounded-full bg-white/5" />
              </div>
            </div>
          </div>
        )}
      >
        <LazyStandardReportPanel report={normalizedPreviewReport} chartFixtures={previewChartFixtures} />
      </Suspense>
    </TerminalPageShell>
  );
};

export default PreviewReportPage;
