import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { translate } from '../../i18n/core';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import PreviewReportPage from '../PreviewReportPage';

vi.mock('../../components/report', () => ({
  StandardReportPanel: () => <div data-testid="standard-report-panel">standard panel</div>,
}));

describe('PreviewReportPage', () => {
  it('renders preview workspace and report panel', () => {
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
    expect(document.title).toBe(translate('zh', 'previewReport.documentTitle'));
    expect(screen.getByTestId('standard-report-panel')).toBeInTheDocument();
  });

  it('renders English preview copy on /en routes', () => {
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
    expect(document.title).toBe(translate('en', 'previewReport.documentTitle'));
  });
});
