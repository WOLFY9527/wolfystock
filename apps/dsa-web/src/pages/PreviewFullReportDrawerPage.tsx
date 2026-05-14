import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { WorkspacePageHeader } from '../components/common';
import { TerminalPageShell } from '../components/terminal';
import { ReportMarkdown } from '../components/report';
import { previewReport } from '../dev/reportPreviewFixture';
import { normalizeFrontendReportContract } from '../api/reportNormalizer';
import type { ReportLanguage } from '../types/analysis';
import { useI18n } from '../contexts/UiLanguageContext';
import { translate } from '../i18n/core';

const PreviewFullReportDrawerPage: React.FC = () => {
  const { t } = useI18n();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [language, setLanguage] = useState<ReportLanguage>('zh');
  const normalizedPreviewReport = useMemo(
    () => normalizeFrontendReportContract(previewReport),
    [],
  );

  useEffect(() => {
    document.title = t('previewFullReport.documentTitle');
  }, [t]);

  const content = language === 'en'
    ? translate('en', 'previewFullReport.markdown')
    : translate('zh', 'previewFullReport.markdown');
  const stockName = language === 'en'
    ? translate('en', 'previewFullReport.stockName')
    : translate('zh', 'previewFullReport.stockName');

  return (
    <TerminalPageShell
      className="flex-1 min-h-0 min-w-0 py-5 md:py-6"
      data-testid="preview-full-report-page"
    >
      <WorkspacePageHeader
        eyebrow={t('previewFullReport.eyebrow')}
        title={t('previewFullReport.title')}
        description={t('previewFullReport.description')}
      />

      <div className="theme-panel-solid rounded-[1.25rem] px-4 py-4 md:px-5">
        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{t('previewFullReport.fullModeTitle')}</p>
        <p className="mt-2 text-sm leading-6 text-secondary-text">
          {t('previewFullReport.fullModeBody')}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            className="home-surface-button rounded-lg px-4 py-2 text-sm"
            onClick={() => {
              setLanguage('zh');
              setDrawerOpen(true);
            }}
          >
            {t('previewFullReport.openChinese')}
          </button>
          <button
            type="button"
            className="home-surface-button rounded-lg px-4 py-2 text-sm"
            onClick={() => {
              setLanguage('en');
              setDrawerOpen(true);
            }}
          >
            {t('previewFullReport.openEnglish')}
          </button>
        </div>
      </div>

      {drawerOpen ? (
        <ReportMarkdown
          recordId={-1}
          stockName={stockName}
          stockCode="NVDA"
          onClose={() => setDrawerOpen(false)}
          reportLanguage={language}
          standardReport={normalizedPreviewReport.details?.standardReport}
          initialContent={content}
        />
      ) : null}
    </TerminalPageShell>
  );
};

export default PreviewFullReportDrawerPage;
