import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { translate } from '../../i18n/core';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import PreviewFullReportDrawerPage from '../PreviewFullReportDrawerPage';

vi.mock('../../components/report', () => ({
  ReportMarkdown: ({ onClose, stockName, initialContent }: { onClose: () => void; stockName: string; initialContent: string }) => (
    <div>
      <div data-testid="report-markdown">drawer content</div>
      <div>{stockName}</div>
      <div data-testid="report-markdown-content">{initialContent}</div>
      <button type="button" onClick={onClose}>close</button>
    </div>
  ),
}));

describe('PreviewFullReportDrawerPage', () => {
  it('opens the drawer in Chinese and English', () => {
    render(
      <MemoryRouter initialEntries={['/__preview/full-report']}>
        <UiLanguageProvider>
          <PreviewFullReportDrawerPage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );

    const page = screen.getByTestId('preview-full-report-page');
    expect(page).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(page).not.toHaveClass('workspace-page');
    expect(page).not.toHaveClass('workspace-page--preview');

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'previewFullReport.openChinese') }));
    expect(screen.getByTestId('report-markdown')).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'previewFullReport.stockName'))).toBeInTheDocument();
    expect(screen.getByTestId('report-markdown-content').textContent).toContain(translate('zh', 'previewFullReport.markdown').slice(0, 24));

    fireEvent.click(screen.getByRole('button', { name: 'close' }));

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'previewFullReport.openEnglish') }));
    expect(screen.getByTestId('report-markdown')).toBeInTheDocument();
    expect(screen.getByText(translate('en', 'previewFullReport.stockName'))).toBeInTheDocument();
    expect(screen.getByTestId('report-markdown-content').textContent).toContain(translate('en', 'previewFullReport.markdown').slice(0, 24));
  });

  it('renders localized English shell copy on /en preview routes', () => {
    window.history.replaceState(window.history.state, '', '/en/__preview/full-report');

    render(
      <MemoryRouter initialEntries={['/en/__preview/full-report']}>
        <UiLanguageProvider>
          <PreviewFullReportDrawerPage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText(translate('en', 'previewFullReport.title'))).toBeInTheDocument();
    expect(screen.getByText(translate('en', 'previewFullReport.description'))).toBeInTheDocument();
    expect(screen.getByText(translate('en', 'previewFullReport.fullModeTitle'))).toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('en', 'previewFullReport.openEnglish') })).toBeInTheDocument();
    expect(document.title).toBe(translate('en', 'previewFullReport.documentTitle'));
  });
});
