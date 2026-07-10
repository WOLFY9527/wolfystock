import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { translate } from '../../../i18n/core';
import { AppErrorBoundary } from '../AppErrorBoundary';

const navigate = vi.fn();

const { languageState } = vi.hoisted(() => ({
  languageState: { value: 'zh' as 'zh' | 'en' },
}));

vi.mock('../../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: languageState.value,
    t: (key: string, vars?: Record<string, string | number | undefined>) => translate(languageState.value, key, vars),
  }),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigate,
  };
});

describe('AppErrorBoundary', () => {
  beforeEach(() => {
    languageState.value = 'zh';
    navigate.mockReset();
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows and focuses a sanitized fallback when a route throws at render time', async () => {
    const ThrowingRoute = () => {
      throw new TypeError('provider exploded stack trace token=abc');
    };

    render(
      <MemoryRouter initialEntries={['/zh/crash']}>
        <AppErrorBoundary>
          <ThrowingRoute />
        </AppErrorBoundary>
      </MemoryRouter>,
    );

    const alert = screen.getByTestId('app-error-boundary');
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveAttribute('tabindex', '-1');
    expect(screen.getByRole('alert')).toHaveTextContent(translate('zh', 'app.errorBoundaryTitle'));
    await waitFor(() => expect(alert).toHaveFocus());
    expect(screen.getByText(translate('zh', 'app.errorBoundaryBody'))).toBeInTheDocument();
    expect(document.body.textContent || '').not.toContain('TypeError');
    expect(document.body.textContent || '').not.toContain('provider exploded');
    expect(document.body.textContent || '').not.toContain('stack trace');
    expect(document.body.textContent || '').not.toContain('token=abc');
  });

  it('offers a safe route back home', () => {
    languageState.value = 'en';

    const ThrowingRoute = () => {
      throw new Error('raw runtime failure');
    };

    render(
      <MemoryRouter initialEntries={['/en/crash']}>
        <AppErrorBoundary>
          <ThrowingRoute />
        </AppErrorBoundary>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: translate('en', 'notFound.cta') }));
    expect(navigate).toHaveBeenCalledWith('/en');
  });
});
