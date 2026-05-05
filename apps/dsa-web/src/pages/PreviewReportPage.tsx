import type React from 'react';
import { useEffect, useMemo } from 'react';
import { WorkspacePageHeader } from '../components/common';
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
    <div className="workspace-page workspace-page--preview min-w-0" data-testid="preview-report-page">
      <WorkspacePageHeader
        eyebrow={t('previewReport.eyebrow')}
        title={t('previewReport.title')}
        description={t('previewReport.description')}
        className="shrink-0"
      />

      <StandardReportPanel report={normalizedPreviewReport} chartFixtures={previewChartFixtures} />
    </div>
  );
};

export default PreviewReportPage;
