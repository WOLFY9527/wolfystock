import type React from 'react';
import { useEffect, useMemo } from 'react';
import { WorkspacePageHeader } from '../components/common';
import { TerminalPageShell } from '../components/terminal';
import { StandardReportPanel } from '../components/report';
import { previewChartFixtures, previewReport } from '../dev/reportPreviewFixture';
import { normalizeFrontendReportContract } from '../api/reportNormalizer';
import { useI18n } from '../contexts/UiLanguageContext';

const PreviewReportPage: React.FC = () => {
  const { t } = useI18n();
  const normalizedPreviewReport = useMemo(
    () => normalizeFrontendReportContract(previewReport),
    [],
  );

  useEffect(() => {
    document.title = t('previewReport.documentTitle');
  }, [t]);

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

      <StandardReportPanel report={normalizedPreviewReport} chartFixtures={previewChartFixtures} />
    </TerminalPageShell>
  );
};

export default PreviewReportPage;
