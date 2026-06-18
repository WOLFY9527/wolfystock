import type React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { translate } from '../../i18n/core';
import NotFoundPage from '../NotFoundPage';

const navigate = vi.fn();

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: window.location.pathname.startsWith('/en') ? 'en' : 'zh',
    t: (key: string) => translate(window.location.pathname.startsWith('/en') ? 'en' : 'zh', key),
  }),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigate,
  };
});

describe('NotFoundPage', () => {
  beforeEach(() => {
    navigate.mockClear();
  });

  it('renders localized Chinese copy on /zh paths', () => {
    window.history.replaceState(window.history.state, '', '/zh/missing-route');

    const { container } = render(
      <MemoryRouter initialEntries={['/zh/missing-route']}>
        <NotFoundPage />
      </MemoryRouter>,
    );

    const pageShell = container.querySelector('[data-terminal-primitive="page-shell"]');
    const panel = container.querySelector('[data-terminal-primitive="panel"]');

    expect(pageShell).toBeTruthy();
    expect(pageShell).not.toHaveClass('min-h-screen');
    expect(panel).toBeTruthy();
    expect(screen.getByRole('heading', { name: translate('zh', 'notFound.title') })).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'notFound.body'))).toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('zh', 'notFound.cta') })).toBeInTheDocument();
    expect(document.title).toBe(translate('zh', 'notFound.documentTitle'));
    const pageText = document.body.textContent || '';
    expect(pageText).not.toMatch(/<script|theme|traceId|requestId|provider|debug|cache|runtime|sourceRef/i);
  });

  it('renders localized English copy on /en paths', () => {
    window.history.replaceState(window.history.state, '', '/en/missing-route');

    render(
      <MemoryRouter initialEntries={['/en/missing-route']}>
        <NotFoundPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: translate('en', 'notFound.title') })).toBeInTheDocument();
    expect(screen.getByText(translate('en', 'notFound.body'))).toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('en', 'notFound.cta') })).toBeInTheDocument();
    expect(document.title).toBe(translate('en', 'notFound.documentTitle'));
  });

  it('navigates back to the localized home route from the CTA', () => {
    window.history.replaceState(window.history.state, '', '/zh/missing-route');

    render(
      <MemoryRouter initialEntries={['/zh/missing-route']}>
        <NotFoundPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'notFound.cta') }));
    expect(navigate).toHaveBeenCalledWith('/zh');
  });
});
