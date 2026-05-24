import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { translate } from '../../i18n/core';
import { expectNoRawI18nKeys } from '../../test-utils/i18nRawKeySentinel';
import LoginPage from '../LoginPage';

const { navigate, useSearchParamsMock, useAuthMock } = vi.hoisted(() => ({
  navigate: vi.fn(),
  useSearchParamsMock: vi.fn(),
  useAuthMock: vi.fn(),
}));

vi.mock('../../hooks', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigate,
    useSearchParams: () => useSearchParamsMock(),
  };
});

describe('LoginPage', () => {
  const renderPage = () => render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );

  beforeEach(() => {
    vi.clearAllMocks();
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fsettings')]);
  });

  it('blocks first-time setup when confirmation does not match', async () => {
    const login = vi.fn();
    useAuthMock.mockReturnValue({
      authEnabled: false,
      login,
      passwordSet: false,
      setupState: 'no_password',
    });

    renderPage();

    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.passwordLabelSetup')), { target: { value: 'passwd6' } });
    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.passwordConfirmLabel')), { target: { value: 'passwd7' } });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'auth.login.submitSetup') }));

    expect(await screen.findByText(translate('zh', 'auth.login.errorPasswordMismatch'))).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it('navigates to redirect after a successful login', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login: vi.fn().mockResolvedValue({ success: true }),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.passwordLabelLogin')), { target: { value: 'passwd6' } });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'auth.login.submitLogin') }));

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/', { replace: true }));
  });

  it('enters create-account mode directly when requested by the route', () => {
    useSearchParamsMock.mockReturnValue([new URLSearchParams('mode=create&redirect=%2Fscanner')]);
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    expect(screen.getByRole('heading', { name: translate('zh', 'auth.login.heroTitleCreate') })).toBeInTheDocument();
    expect(screen.getByLabelText(translate('zh', 'auth.login.usernameLabel'))).toBeInTheDocument();
    expect(screen.getByLabelText(translate('zh', 'auth.login.displayNameLabel'))).toBeInTheDocument();
  });

  it('offers a single guest-mode exit path for direct login entry', () => {
    useSearchParamsMock.mockReturnValue([new URLSearchParams('')]);
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'auth.login.returnToGuest') }));

    expect(navigate).toHaveBeenCalledWith('/guest', { replace: true });
  });

  it('still sends redirected login entries back to guest mode instead of the source route', () => {
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fscanner')]);
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'auth.login.returnToGuest') }));

    expect(navigate).toHaveBeenCalledWith('/guest', { replace: true });
  });

  it('keeps locale-prefixed guest exits when opened from a localized route', () => {
    window.history.replaceState(window.history.state, '', '/en/login?redirect=%2Fen%2Fscanner');
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fen%2Fscanner')]);
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    fireEvent.click(screen.getByRole('button', { name: translate('en', 'auth.login.returnToGuest') }));

    expect(navigate).toHaveBeenCalledWith('/en/guest', { replace: true });
  });

  it('renders visible login copy in English for /en/login', () => {
    window.history.replaceState(window.history.state, '', '/en/login?redirect=%2Fen%2Fchat');
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fen%2Fchat')]);
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    const { container } = renderPage();

    expect(screen.getByRole('heading', { name: translate('en', 'auth.login.heroTitleLogin') })).toBeInTheDocument();
    expect(screen.queryByText(translate('en', 'auth.login.continueAfterLogin'))).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('en', 'auth.login.returnToGuest') })).toBeInTheDocument();
    expect(screen.getByLabelText(translate('en', 'auth.login.passwordLabelLogin'))).toBeInTheDocument();
    expect(screen.getByPlaceholderText(translate('en', 'auth.login.usernamePlaceholderLogin'))).toHaveAttribute('placeholder', 'Enter email or username');
    expect(screen.getByLabelText(translate('en', 'auth.login.usernameLabel'))).toHaveClass(
      '!px-4',
      'py-3',
      'bg-white/[0.03]',
      'border-white/10',
    );
    expect(screen.getByLabelText(translate('en', 'auth.login.passwordLabelLogin'))).toHaveClass(
      '!pl-4',
      '!pr-12',
      'py-3',
      'bg-white/[0.03]',
      'border-white/10',
    );
    expect(screen.getByRole('button', { name: translate('en', 'auth.login.submitLogin') })).toHaveClass(
      'mt-2',
      'bg-white',
      'text-black',
      'active:scale-95',
    );
    expect(screen.getByRole('button', { name: translate('en', 'auth.login.returnToGuest') })).toHaveClass(
      'mt-6',
      'text-xs',
      'text-white/30',
      'hover:text-white/60',
    );
    expect(screen.getByRole('button', { name: translate('en', 'auth.login.submitLogin') })).toBeInTheDocument();
    expectNoRawI18nKeys(container);
  });

  it('keeps login input adornments from sharing text space', () => {
    window.history.replaceState(window.history.state, '', '/login?redirect=%2Fscanner');
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fscanner')]);
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    const { container } = renderPage();
    const usernameInput = screen.getByLabelText(translate('zh', 'auth.login.usernameLabel'));
    const passwordInput = screen.getByLabelText(translate('zh', 'auth.login.passwordLabelLogin'));

    expect(container.querySelectorAll('.input-field__icon')).toHaveLength(0);
    expect(usernameInput).toHaveClass('!px-4');
    expect(usernameInput).not.toHaveClass('pl-12');
    expect(passwordInput).toHaveClass('!pl-4', '!pr-12');
    expect(passwordInput).not.toHaveClass('pl-12');
    expect(container.querySelectorAll('.input-field__trailing')).toHaveLength(1);
  });

  it('links the login page to the reset-password route', () => {
    window.history.replaceState(window.history.state, '', '/login?redirect=%2Fsettings');
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fsettings')]);
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    expect(screen.getByRole('link', { name: translate('zh', 'auth.login.forgotPassword') })).toHaveAttribute(
      'href',
      '/reset-password',
    );
  });
});
