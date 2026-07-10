import { fireEvent, render, screen, waitFor, waitForElementToBeRemoved, within } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { translate } from '../../i18n/core';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { getDocumentTitle } from '../../utils/documentTitle';
import PreviewFullReportDrawerPage from '../PreviewFullReportDrawerPage';

vi.mock('../../components/common/Drawer', () => ({
  Drawer: ({ children }: { children: ReactNode }) => <div data-testid="drawer-shell">{children}</div>,
}));

const openTechnicalDetails = async (label: string) => {
  const technicalDetails = await screen.findByTestId('report-technical-evidence-details');
  fireEvent.click(within(technicalDetails).getByText(label));

  const loading = screen.queryByTestId('report-technical-details-loading');
  if (loading) {
    await waitForElementToBeRemoved(loading, { timeout: 5000 });
  }

  await screen.findByTestId('report-technical-details-renderer', {}, { timeout: 5000 });
};

describe('PreviewFullReportDrawerPage', () => {
  it('uses observation-only localized labels for preview and report copy', () => {
    expect(translate('zh', 'guestHome.decisionPanelEyebrow')).toBe('WolfyStock 研究判断');
    expect(translate('en', 'guestHome.decisionPanelEyebrow')).toBe('WolfyStock Research Decision');
    expect(translate('zh', 'report.idealEntry')).toBe('关键观察区间');
    expect(translate('en', 'report.idealEntry')).toBe('Observation range');
    expect(translate('en', 'report.noPosition')).toBe('No-position watch');
    expect(translate('en', 'report.holding')).toBe('Holding watch');
    expect(translate('zh', 'previewFullReport.markdown')).toContain('关键观察区间：120-121。');
    expect(translate('zh', 'previewFullReport.markdown')).not.toContain('理想买入区间：120-121。');
    expect(translate('en', 'previewFullReport.markdown')).toContain('Observation range: 120-121.');
    expect(translate('en', 'previewFullReport.markdown')).not.toContain('Ideal entry range: 120-121.');
  });

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

    await openTechnicalDetails('数据覆盖与证据明细');

    await waitFor(() => {
      expect(screen.getByText('一、结论摘要')).toBeInTheDocument();
    });
    expect(screen.getByRole('columnheader', { name: '字段' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '关闭' }));
    await waitForElementToBeRemoved(() => screen.queryByTestId('full-report-document-shell'));

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'previewFullReport.openEnglish') }));

    await openTechnicalDetails('Coverage and evidence details');

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
    expect(getDocumentTitle('/en/__preview/full-report', 'zh')).toBe(translate('en', 'previewFullReport.documentTitle'));
  });
});
