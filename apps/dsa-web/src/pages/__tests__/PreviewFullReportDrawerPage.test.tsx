import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { translate } from '../../i18n/core';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import PreviewFullReportDrawerPage from '../PreviewFullReportDrawerPage';

vi.mock('../../components/common/Drawer', () => ({
  Drawer: ({ children }: { children: ReactNode }) => <div data-testid="drawer-shell">{children}</div>,
}));

describe('PreviewFullReportDrawerPage', () => {
  it('shows the route shell buttons on first paint', () => {
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
    expect(screen.getByRole('button', { name: translate('zh', 'previewFullReport.openChinese') })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('zh', 'previewFullReport.openEnglish') })).toBeInTheDocument();
  });

  it('renders localized markdown content after opening technical details in Chinese and English drawers', async () => {
    render(
      <MemoryRouter initialEntries={['/__preview/full-report']}>
        <UiLanguageProvider>
          <PreviewFullReportDrawerPage />
        </UiLanguageProvider>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'previewFullReport.openChinese') }));

    let technicalDetails = await screen.findByTestId('report-technical-evidence-details');
    fireEvent.click(within(technicalDetails).getByText('技术细节'));

    await waitFor(() => {
      expect(screen.getByText('一、结论摘要')).toBeInTheDocument();
    });
    expect(screen.getByRole('columnheader', { name: '字段' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '关闭' }));

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'previewFullReport.openEnglish') }));

    technicalDetails = await screen.findByTestId('report-technical-evidence-details');
    fireEvent.click(within(technicalDetails).getByText('Technical details'));

    await waitFor(() => {
      expect(screen.getByText('1. Executive Summary')).toBeInTheDocument();
    });
    expect(screen.getByRole('columnheader', { name: 'Field' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Intraday snapshot' })).toBeInTheDocument();
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
