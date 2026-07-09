import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { translate } from '../../../i18n/core';
import { ConsumerProtectedFrame } from '../ConsumerWorkspaceShell';

const { languageState } = vi.hoisted(() => ({
  languageState: { value: 'en' as 'zh' | 'en' },
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
    useNavigate: () => vi.fn(),
  };
});

describe('ConsumerProtectedFrame', () => {
  beforeEach(() => {
    languageState.value = 'en';
    document.body.innerHTML = '';
  });

  it('owns the consumer protected boundary and routes module identity into AuthGuardOverlay', () => {
    render(
      <MemoryRouter initialEntries={['/en/scanner']}>
        <ConsumerProtectedFrame moduleName="Scanner" />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('consumer-protected-frame')).toHaveAttribute(
      'data-boundary-family',
      'consumer-protected',
    );
    expect(screen.getByTestId('consumer-protected-frame')).toHaveAttribute(
      'data-protected-module',
      'Scanner',
    );
    expect(screen.getByTestId('auth-guard-capability')).toHaveTextContent('Scanner');
    expect(screen.getByTestId('auth-guard-status-pill')).toHaveTextContent('Sign-in required');
    expect(screen.getByTestId('auth-guard-primary-action')).toBeInTheDocument();
    expect(screen.getByTestId('auth-guard-secondary-action')).toBeInTheDocument();
  });

  it('uses a static-orientation skeleton backdrop, not personalized research fixtures', () => {
    render(
      <MemoryRouter initialEntries={['/en/portfolio']}>
        <ConsumerProtectedFrame moduleName="Portfolio" />
      </MemoryRouter>,
    );

    const backdrop = screen.getByTestId('consumer-protected-backdrop');
    expect(backdrop).toHaveAttribute('data-preview-kind', 'static-orientation');
    expect(backdrop).toHaveAttribute('data-protected-module', 'Portfolio');
    expect(backdrop).toHaveAttribute('aria-hidden', 'true');
    expect(backdrop.textContent?.trim() || '').toBe('');
    expect(screen.getByTestId('auth-guard-preview-note')).toHaveTextContent(/static orientation/i);
    expect(screen.getByTestId('auth-guard-card').textContent || '').not.toMatch(
      /AAPL|\$|P&L|持仓盈亏|demo account|fixture/i,
    );
  });

  it('prefers explicit children as the protected backdrop when provided', () => {
    render(
      <MemoryRouter initialEntries={['/en/watchlist']}>
        <ConsumerProtectedFrame moduleName="Watchlist">
          <div data-testid="custom-backdrop">orientation only</div>
        </ConsumerProtectedFrame>
      </MemoryRouter>,
    );

    expect(screen.queryByTestId('consumer-protected-backdrop')).not.toBeInTheDocument();
    expect(screen.getByTestId('auth-guard-backdrop-content')).toContainElement(
      screen.getByTestId('custom-backdrop'),
    );
  });
});
