import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { translate } from '../../i18n/core';
import ResetPasswordPage from '../ResetPasswordPage';

const { navigate, requestPasswordReset } = vi.hoisted(() => ({
  navigate: vi.fn(),
  requestPasswordReset: vi.fn(),
}));

vi.mock('../../api/auth', () => ({
  authApi: {
    requestPasswordReset,
  },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigate,
  };
});

describe('ResetPasswordPage', () => {
  const renderPage = (path = '/reset-password') => render(
    <MemoryRouter initialEntries={[path]}>
      <ResetPasswordPage />
    </MemoryRouter>,
  );

  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState(window.history.state, '', '/reset-password');
  });

  it('validates that an identifier is required before submitting', async () => {
    renderPage();

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'auth.reset.submit') }));

    expect(await screen.findByText(translate('zh', 'auth.reset.validationRequired'))).toBeInTheDocument();
    expect(requestPasswordReset).not.toHaveBeenCalled();
  });

  it('submits a reset request and shows the success state', async () => {
    requestPasswordReset.mockResolvedValue({
      ok: true,
      message: translate('zh', 'auth.reset.successBody'),
    });

    renderPage();

    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.reset.identifierLabel')), {
      target: { value: 'alice@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'auth.reset.submit') }));

    await waitFor(() => expect(requestPasswordReset).toHaveBeenCalledWith({ identifier: 'alice@example.com' }));
    expect(await screen.findByText(translate('zh', 'auth.reset.successTitle'))).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'auth.reset.successBody'))).toBeInTheDocument();
  });

  it('renders English canonical copy on localized routes', () => {
    window.history.replaceState(window.history.state, '', '/en/reset-password');
    renderPage('/en/reset-password');

    expect(screen.getByRole('heading', { name: translate('en', 'auth.reset.title') })).toBeInTheDocument();
    expect(screen.getByLabelText(translate('en', 'auth.reset.identifierLabel'))).toHaveAttribute(
      'placeholder',
      translate('en', 'auth.reset.identifierPlaceholder'),
    );
    expect(screen.getByRole('button', { name: translate('en', 'auth.reset.submit') })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: translate('en', 'auth.reset.backToLogin') })).toHaveAttribute(
      'href',
      '/en/login',
    );
  });

  it('preserves safe redirect values when linking back to login', () => {
    window.history.replaceState(window.history.state, '', '/reset-password?redirect=%2Fsettings');
    renderPage('/reset-password?redirect=%2Fsettings');

    expect(screen.getByRole('link', { name: translate('zh', 'auth.reset.backToLogin') })).toHaveAttribute(
      'href',
      '/login?redirect=%2Fsettings',
    );
  });

  it('does not send duplicate reset requests while the first submit is pending', async () => {
    let resolveRequest: (value: { ok: boolean; message: string }) => void = () => undefined;
    requestPasswordReset.mockReturnValue(new Promise((resolve) => {
      resolveRequest = resolve;
    }));

    renderPage();

    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.reset.identifierLabel')), {
      target: { value: 'alice@example.com' },
    });
    fireEvent.submit(screen.getByLabelText(translate('zh', 'auth.reset.identifierLabel')).closest('form') as HTMLFormElement);
    fireEvent.submit(screen.getByLabelText(translate('zh', 'auth.reset.identifierLabel')).closest('form') as HTMLFormElement);

    expect(requestPasswordReset).toHaveBeenCalledTimes(1);

    resolveRequest({ ok: true, message: translate('zh', 'auth.reset.successBody') });
    expect(await screen.findByText(translate('zh', 'auth.reset.successTitle'))).toBeInTheDocument();
  });
});
