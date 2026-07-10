import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { translate } from '../../i18n/core';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { previewReport } from '../../dev/reportPreviewFixture';
import { getDocumentTitle } from '../../utils/documentTitle';
import PreviewReportPage from '../PreviewReportPage';

const { standardReportPanelImportSpy } = vi.hoisted(() => ({
  standardReportPanelImportSpy: vi.fn(),
}));

vi.mock('../../components/report/StandardReportPanel', async () => {
  standardReportPanelImportSpy();
  await new Promise((resolve) => {
    setTimeout(resolve, 100);
  });

  return {
    StandardReportPanel: ({ report }: { report: { summary?: { analysisSummary?: string } } }) => (
      <div data-testid="standard-report-panel">{report.summary?.analysisSummary}</div>
    ),
  };
});

describe('PreviewReportPage', () => {
  it('renders preview workspace, shows a loading shell, and then resolves the report panel', async () => {
    render(
      <UiLanguageProvider>
        <PreviewReportPage />
      </UiLanguageProvider>,
    );

    const page = screen.getByTestId('preview-report-page');
    expect(page).toBeInTheDocument();
    expect(page).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(page).not.toHaveClass('workspace-page');
    expect(page).not.toHaveClass('workspace-page--preview');
    expect(screen.getByText(translate('zh', 'previewReport.title'))).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'previewReport.description'))).toBeInTheDocument();
    expect(getDocumentTitle('/__preview/report', 'zh')).toBe(translate('zh', 'previewReport.documentTitle'));
    expect(screen.getByTestId('preview-report-loading')).toBeInTheDocument();
    expect(await screen.findByTestId('standard-report-panel')).toHaveTextContent(previewReport.summary.analysisSummary);
    await waitFor(() => {
      expect(screen.queryByTestId('preview-report-loading')).not.toBeInTheDocument();
    });
    expect(standardReportPanelImportSpy).toHaveBeenCalledTimes(1);
  });

  it('renders English preview copy on /en routes', async () => {
    window.history.replaceState(window.history.state, '', '/en/__preview/report');

    render(
      <MemoryRouter initialEntries={['/en/__preview/report']}>
        <UiLanguageProvider>
          <PreviewReportPage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText(translate('en', 'previewReport.title'))).toBeInTheDocument();
    expect(screen.getByText(translate('en', 'previewReport.description'))).toBeInTheDocument();
    expect(getDocumentTitle('/en/__preview/report', 'zh')).toBe(translate('en', 'previewReport.documentTitle'));
    expect(await screen.findByTestId('standard-report-panel')).toBeInTheDocument();
  });
});
