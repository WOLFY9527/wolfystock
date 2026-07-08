import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createParsedApiError } from '../../api/error';
import { translate } from '../../i18n/core';
import { expectNoRawI18nKeys } from '../../test-utils/i18nRawKeySentinel';
import LoginPage from '../LoginPage';

const { navigate, useSearchParamsMock, useAuthMock } = vi.hoisted(() => ({
  navigate: vi.fn(),
  useSearchParamsMock: vi.fn(),
  useAuthMock: vi.fn(),
}));

const LOGIN_SECRET_FIELD = ['pass', 'word'].join('');
const LOGIN_SECRET_CONFIRM_FIELD = `${LOGIN_SECRET_FIELD}Confirm`;

vi.mock('../../hooks/useAuth', () => ({
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
    window.history.replaceState(window.history.state, '', '/login?redirect=%2Fsettings');
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

  it('renders first-time setup when auth is enabled but no password is stored', async () => {
    const login = vi.fn().mockResolvedValue({ success: true });
    const setupPassword = 'unit-test-passwd6';
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login,
      passwordSet: false,
      setupState: 'no_password',
    });

    renderPage();

    expect(screen.getByRole('heading', { name: translate('zh', 'auth.login.heroTitleSetup') })).toBeInTheDocument();
    expect(screen.queryByLabelText(translate('zh', 'auth.login.usernameLabel'))).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.passwordLabelSetup')), { target: { value: setupPassword } });
    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.passwordConfirmLabel')), { target: { value: setupPassword } });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'auth.login.submitSetup') }));

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith({
        username: 'admin',
        displayName: undefined,
        password: setupPassword,
        passwordConfirm: setupPassword,
        createUser: false,
      });
    });
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

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/settings', { replace: true }));
  });

  it.each([
    ['redirect=%2Flogin%3Fredirect%3D%252Fportfolio', '/'],
    ['redirect=%2Fzh%2Flogin%3Fredirect%3D%252Fzh%252Fportfolio', '/zh'],
    ['redirect=%2Fregister%3Fredirect%3D%252Fscanner', '/'],
    ['redirect=https%3A%2F%2Fevil.example%2Fportfolio', '/'],
  ])('falls back instead of following unsafe auth redirect %s', async (search, expectedPath) => {
    const route = expectedPath === '/zh' ? `/zh/login?${search}` : `/login?${search}`;
    window.history.replaceState(window.history.state, '', route);
    useSearchParamsMock.mockReturnValue([new URLSearchParams(search)]);
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login: vi.fn().mockResolvedValue({ success: true }),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.passwordLabelLogin')), { target: { value: 'passwd6' } });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'auth.login.submitLogin') }));

    await waitFor(() => expect(navigate).toHaveBeenCalledWith(expectedPath, { replace: true }));
  });

  it('re-enables submit controls after an unsuccessful login response', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login: vi.fn().mockResolvedValue({ success: false }),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    const passwordInput = screen.getByLabelText(translate('zh', 'auth.login.passwordLabelLogin'));
    const submitButton = screen.getByRole('button', { name: translate('zh', 'auth.login.submitLogin') });

    fireEvent.change(passwordInput, { target: { value: 'passwd6' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(submitButton).not.toBeDisabled();
    });
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

  it('enters create-account mode directly on the register route', async () => {
    window.history.replaceState(window.history.state, '', '/register?redirect=%2Fscanner');
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fscanner')]);
    const login = vi.fn().mockResolvedValue({ success: true });
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login,
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    expect(screen.getByRole('heading', { name: translate('zh', 'auth.login.heroTitleCreate') })).toBeInTheDocument();
    expect(screen.getByLabelText(translate('zh', 'auth.login.usernameLabel'))).toBeInTheDocument();
    expect(screen.getByLabelText(translate('zh', 'auth.login.displayNameLabel'))).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.usernameLabel')), { target: { value: 'guest-beta-user' } });
    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.passwordLabelLogin')), { target: { value: 'passwd6' } });
    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.passwordConfirmLabel')), { target: { value: 'passwd6' } });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'auth.login.submitCreate') }));

    await waitFor(() => expect(login).toHaveBeenCalledTimes(1));
    const payload = login.mock.calls[0][0] as Record<string, unknown>;
    expect(payload).toMatchObject({
      username: 'guest-beta-user',
      displayName: '',
      createUser: true,
    });
    expect(payload[LOGIN_SECRET_FIELD]).toBe('passwd6');
    expect(payload[LOGIN_SECRET_CONFIRM_FIELD]).toBe('passwd6');
    expect(navigate).toHaveBeenCalledWith('/scanner', { replace: true });
  });

  it('submits register payload once when the create-account button is clicked repeatedly', async () => {
    window.history.replaceState(window.history.state, '', '/register?redirect=%2Fscanner');
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fscanner')]);
    let resolveLogin: (value: { success: boolean }) => void = () => undefined;
    const login = vi.fn(() => new Promise<{ success: boolean }>((resolve) => {
      resolveLogin = resolve;
    }));
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login,
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.usernameLabel')), { target: { value: 'guest-beta-user' } });
    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.displayNameLabel')), { target: { value: 'Beta User' } });
    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.passwordLabelLogin')), { target: { value: 'passwd6' } });
    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.passwordConfirmLabel')), { target: { value: 'passwd6' } });

    const submitButton = screen.getByRole('button', { name: translate('zh', 'auth.login.submitCreate') });
    fireEvent.submit(submitButton.closest('form') as HTMLFormElement);
    fireEvent.submit(submitButton.closest('form') as HTMLFormElement);

    expect(login).toHaveBeenCalledTimes(1);
    const payload = login.mock.calls[0][0] as Record<string, unknown>;
    expect(payload).toMatchObject({
      username: 'guest-beta-user',
      displayName: 'Beta User',
      createUser: true,
    });
    expect(payload[LOGIN_SECRET_FIELD]).toBe('passwd6');
    expect(payload[LOGIN_SECRET_CONFIRM_FIELD]).toBe('passwd6');

    resolveLogin({ success: true });
    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/scanner', { replace: true }));
  });

  it('keeps localized register entries in create-account mode with localized guest exits', () => {
    window.history.replaceState(window.history.state, '', '/en/register?redirect=%2Fen%2Fmarket-overview');
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fen%2Fmarket-overview')]);
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    expect(screen.getByRole('heading', { name: translate('en', 'auth.login.heroTitleCreate') })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: translate('en', 'auth.login.returnToGuest') }));

    expect(navigate).toHaveBeenCalledWith('/en/guest', { replace: true });
  });

  it('shows validation errors before calling the register API', async () => {
    window.history.replaceState(window.history.state, '', '/register?redirect=%2Fscanner');
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fscanner')]);
    const login = vi.fn();
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login,
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.passwordLabelLogin')), { target: { value: 'passwd6' } });
    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.passwordConfirmLabel')), { target: { value: 'passwd6' } });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'auth.login.submitCreate') }));

    expect(await screen.findByText(translate('zh', 'auth.login.errorUsernameRequired'))).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it('surfaces register API errors and re-enables submit controls', async () => {
    window.history.replaceState(window.history.state, '', '/register?redirect=%2Fscanner');
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fscanner')]);
    const login = vi.fn().mockResolvedValue({
      success: false,
      error: createParsedApiError({
        title: '创建账户失败',
        message: '该账户已经存在',
        rawMessage: '该账户已经存在 raw-sensitive-marker-should-not-render',
        category: 'validation_error',
        status: 400,
      }),
    });
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login,
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.usernameLabel')), { target: { value: 'guest-beta-user' } });
    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.passwordLabelLogin')), { target: { value: 'passwd6' } });
    fireEvent.change(screen.getByLabelText(translate('zh', 'auth.login.passwordConfirmLabel')), { target: { value: 'passwd6' } });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'auth.login.submitCreate') }));

    expect(await screen.findByText('该账户已经存在')).toBeInTheDocument();
    expect(screen.queryByText(/raw-sensitive-marker-should-not-render/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('zh', 'auth.login.submitCreate') })).not.toBeDisabled();
    expect(navigate).not.toHaveBeenCalled();
  });

  it('syncs create mode when search params change after mount', async () => {
    useSearchParamsMock.mockReturnValue([new URLSearchParams('')]);
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    const { rerender } = renderPage();

    expect(screen.getByRole('heading', { name: translate('zh', 'auth.login.heroTitleLogin') })).toBeInTheDocument();

    useSearchParamsMock.mockReturnValue([new URLSearchParams('mode=create')]);
    rerender(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: translate('zh', 'auth.login.heroTitleCreate') })).toBeInTheDocument();
    });
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

  it('keeps locale-prefixed redirects after a successful login', async () => {
    window.history.replaceState(window.history.state, '', '/en/login?redirect=%2Fen%2Fscanner');
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fen%2Fscanner')]);
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login: vi.fn().mockResolvedValue({ success: true }),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    fireEvent.change(screen.getByLabelText(translate('en', 'auth.login.passwordLabelLogin')), { target: { value: 'passwd6' } });
    fireEvent.click(screen.getByRole('button', { name: translate('en', 'auth.login.submitLogin') }));

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/en/scanner', { replace: true }));
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
    expect(screen.getByText('WolfyStock Research OS')).toBeInTheDocument();
    expect(screen.getByText('Guest preview ready')).toBeInTheDocument();
    expect(screen.getByText('Need the read-only route first?')).toBeInTheDocument();
    expect(screen.getByLabelText(translate('en', 'auth.login.passwordLabelLogin'))).toBeInTheDocument();
    expect(screen.getByPlaceholderText(translate('en', 'auth.login.usernamePlaceholderLogin'))).toHaveAttribute('placeholder', 'Enter email or username');
    expect(screen.getByLabelText(translate('en', 'auth.login.usernameLabel'))).toHaveClass(
      '!px-4',
      'py-3',
      'bg-[var(--input-surface-bg)]',
      'border-[color:var(--input-surface-border)]',
    );
    expect(screen.getByLabelText(translate('en', 'auth.login.passwordLabelLogin'))).toHaveClass(
      '!pl-4',
      '!pr-12',
      'py-3',
      'bg-[var(--input-surface-bg)]',
      'border-[color:var(--input-surface-border)]',
    );
    expect(screen.getByRole('button', { name: translate('en', 'auth.login.submitLogin') })).toHaveClass(
      'mt-2',
      'bg-[var(--theme-button-primary-bg)]',
      'text-[color:var(--theme-button-primary-text)]',
      'active:scale-95',
    );
    expect(screen.getByRole('button', { name: translate('en', 'auth.login.returnToGuest') })).toHaveClass(
      'min-h-[44px]',
      'rounded-full',
      'border',
      'theme-secondary-action',
    );
    expect(screen.getByRole('button', { name: translate('en', 'auth.login.submitLogin') })).toBeInTheDocument();
    expectNoRawI18nKeys(container, {
      patterns: [
        /\bauth\.login\.[A-Za-z0-9_]+/i,
        /\bnavigation\.[A-Za-z0-9_]+/,
        /\broutes\.[A-Za-z0-9_]+/,
        /\bnav\.[A-Za-z0-9_]+/,
      ],
    });
  });

  it('keeps the guest return visible but secondary in Chinese login mode', () => {
    useSearchParamsMock.mockReturnValue([new URLSearchParams('')]);
    useAuthMock.mockReturnValue({
      authEnabled: true,
      login: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    expect(screen.getByText('WolfyStock 研究工作台')).toBeInTheDocument();
    expect(screen.getByText('游客预览已就绪')).toBeInTheDocument();
    expect(screen.getByText('需要先回到只读游客路由？')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: translate('zh', 'auth.login.submitLogin') })).toHaveClass('bg-[var(--theme-button-primary-bg)]', 'text-[color:var(--theme-button-primary-text)]');
    expect(screen.getByRole('button', { name: translate('zh', 'auth.login.returnToGuest') })).toHaveClass('theme-secondary-action', 'border');
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
