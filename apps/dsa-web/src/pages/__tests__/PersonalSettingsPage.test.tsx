import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { translate } from '../../i18n/core';
import {
  PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY,
  readPortfolioDisplayCurrency,
} from '../../utils/portfolioPreferences';
import PersonalSettingsPage from '../PersonalSettingsPage';

const zh = (key: string, vars?: Record<string, string | number | undefined>) => translate('zh', key, vars);

const {
  getNotificationPreferences,
  updateNotificationPreferences,
  setDataDensity,
  setLanguage,
  setMarketColorConvention,
  setNumberFormat,
  useAuthMock,
  useProductSurfaceMock,
} = vi.hoisted(() => ({
  getNotificationPreferences: vi.fn(),
  updateNotificationPreferences: vi.fn(),
  setDataDensity: vi.fn(),
  setLanguage: vi.fn(),
  setMarketColorConvention: vi.fn(),
  setNumberFormat: vi.fn(),
  useAuthMock: vi.fn(),
  useProductSurfaceMock: vi.fn(),
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: 'zh',
    setLanguage,
    t: (key: string, vars?: Record<string, string | number | undefined>) => translate('zh', key, vars),
  }),
}));

vi.mock('../../contexts/UiPreferencesContext', () => ({
  useUiPreferences: () => ({
    dataDensity: 'comfortable',
    marketColorConvention: 'redDownGreenUp',
    numberFormat: 'international',
    setDataDensity,
    setMarketColorConvention,
    setNumberFormat,
  }),
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('../../api/auth', () => ({
  authApi: {
    getNotificationPreferences,
    updateNotificationPreferences,
  },
}));

vi.mock('../../hooks/useProductSurface', () => ({
  buildLoginPath: (path: string) => `/login?redirect=${encodeURIComponent(path)}`,
  buildRegistrationPath: (path: string) => `/login?mode=create&redirect=${encodeURIComponent(path)}`,
  useProductSurface: () => useProductSurfaceMock(),
}));

vi.mock('../../components/settings/FontSizeSettingsCard', () => ({
  FontSizeSettingsCard: () => <div data-testid="font-size-card" />,
}));

vi.mock('../../components/settings/ChangePasswordCard', () => ({
  ChangePasswordCard: () => <div data-testid="change-password-card">修改密码</div>,
}));

describe('PersonalSettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    getNotificationPreferences.mockResolvedValue({
      channel: 'email',
      enabled: false,
      email: null,
      emailEnabled: false,
      discordEnabled: false,
      discordWebhook: null,
      deliveryAvailable: true,
      emailDeliveryAvailable: true,
      discordDeliveryAvailable: true,
      updatedAt: null,
    });
    updateNotificationPreferences.mockResolvedValue({
      channel: 'email',
      enabled: false,
      email: null,
      emailEnabled: false,
      discordEnabled: false,
      discordWebhook: null,
      deliveryAvailable: true,
      emailDeliveryAvailable: true,
      discordDeliveryAvailable: true,
      updatedAt: null,
    });
  });

  it('shows guest-only sign-in guidance without system links', () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      passwordChangeable: false,
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: true,
      isAdmin: false,
      loggedIn: false,
      currentUser: null,
    });

    const { container } = render(
      <MemoryRouter>
        <PersonalSettingsPage />
      </MemoryRouter>,
    );

    const heading = screen.getByRole('heading', { level: 1, name: '账户中心' });
    const workspace = screen.getByTestId('personal-settings-workspace');
    const settingsConsole = screen.getByTestId('personal-settings-console');
    const primaryBoard = screen.getByTestId('personal-settings-primary-board');
    const helpRail = screen.getByTestId('personal-settings-help-rail');
    expect(heading).toHaveClass('text-xl', 'md:text-2xl');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(container.querySelectorAll('main')).toHaveLength(0);
    expect(workspace).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(workspace).toHaveClass('w-full', 'max-w-[1600px]', 'mx-auto', 'px-4', 'xl:px-8', 'flex', 'flex-col', 'py-5', 'md:py-6');
    expect(workspace).not.toHaveClass('px-6', 'md:px-8', 'xl:px-12', 'py-8');
    expect(workspace).not.toHaveClass('max-w-4xl');
    expect(settingsConsole).toBeInTheDocument();
    expect(primaryBoard).toHaveAttribute('data-linear-primitive', 'console-board');
    expect(helpRail).toHaveAttribute('data-linear-primitive', 'context-rail');
    expect(screen.getByTestId('personal-settings-profile-header')).toBeInTheDocument();
    expect(screen.getByTestId('personal-settings-security-section')).toBeInTheDocument();
    expect(screen.getByTestId('personal-settings-privacy-section')).toBeInTheDocument();
    expect(screen.getByTestId('personal-settings-preferences-section')).toBeInTheDocument();
    expect(screen.getByText('账户与安全')).toBeInTheDocument();
    expect(screen.getByText('隐私设置')).toBeInTheDocument();
    expect(screen.getByText('显示与偏好')).toBeInTheDocument();
    expect(screen.getByText(zh('settings.personalGuestPreferencesTitle'))).toBeInTheDocument();
    expect(screen.queryByText(zh('settings.personalGuestPreferencesBody'))).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: zh('language.zh') })).not.toBeInTheDocument();
    expect(screen.getByText(zh('settings.dataDensityTitle'))).toBeInTheDocument();
    expect(screen.getByText(zh('settings.numberFormatTitle'))).toBeInTheDocument();
    expect(screen.getByText(zh('settings.portfolioDisplayTitle'))).toBeInTheDocument();
    expect(screen.getByText(zh('settings.portfolioDisplayDesc'))).toBeInTheDocument();
    expect(screen.getByText(zh('settings.portfolioDisplayNativeSettlementHint'))).toBeInTheDocument();
    expect(screen.getByRole('link', { name: zh('settings.personalGuestSignInAction') })).toHaveAttribute('href', '/login?redirect=%2Fsettings');
    expect(screen.getByRole('link', { name: zh('settings.personalGuestCreateAccountAction') })).toHaveAttribute('href', '/login?mode=create&redirect=%2Fsettings');
    expect(screen.queryByRole('link', { name: zh('nav.independentConsole') })).not.toBeInTheDocument();
    expect(screen.queryByText(/provider_timeout|MarketCache|generatedCandidates|failedCandidates/i)).not.toBeInTheDocument();
    expect(within(screen.getByTestId('personal-settings-boundary-disclosure')).getByRole('button')).toHaveAttribute('aria-expanded', 'false');
    expect(within(screen.getByTestId('personal-settings-help-disclosure')).getByRole('button')).toHaveAttribute('aria-expanded', 'false');
    expect(getNotificationPreferences).not.toHaveBeenCalled();
  });

  it('persists the default portfolio display currency without exposing secrets', () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      passwordChangeable: false,
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: true,
      isAdmin: false,
      loggedIn: false,
      currentUser: null,
    });

    render(
      <MemoryRouter>
        <PersonalSettingsPage />
      </MemoryRouter>,
    );

    expect(screen.getByText(zh('settings.portfolioDisplayDefaultCurrency'))).toBeInTheDocument();
    for (const currency of ['CNY', 'USD', 'HKD', 'EUR', 'JPY']) {
      expect(screen.getByRole('button', { name: currency })).toBeInTheDocument();
    }

    fireEvent.click(screen.getByRole('button', { name: 'HKD' }));

    expect(window.localStorage.getItem(PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY)).toBe('HKD');
    expect(readPortfolioDisplayCurrency()).toBe('HKD');
    expect(screen.getByText(zh('settings.portfolioDisplaySaved'))).toBeInTheDocument();
    expect(screen.queryByText(/API_KEY|SECRET|TOKEN|WEBHOOK/)).not.toBeInTheDocument();
  });

  it('keeps admin console links out of personal settings content', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      passwordChangeable: true,
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: true,
      loggedIn: true,
      currentUser: {
        username: 'admin',
        displayName: 'Admin',
      },
    });
    getNotificationPreferences.mockResolvedValue({
      channel: 'email',
      enabled: true,
      email: 'admin@example.com',
      emailEnabled: true,
      discordEnabled: true,
      discordWebhook: 'https://discord.com/api/webhooks/123/token',
      deliveryAvailable: true,
      emailDeliveryAvailable: true,
      discordDeliveryAvailable: true,
      updatedAt: '2026-04-15T09:00:00Z',
    });

    const { container } = render(
      <MemoryRouter>
        <PersonalSettingsPage />
      </MemoryRouter>,
    );

    const workspace = screen.getByTestId('personal-settings-workspace');
    const profileHeader = screen.getByTestId('personal-settings-profile-header');
    const saveButton = screen.getByRole('button', { name: zh('settings.personalNotificationSaveAction') });
    expect(container.querySelectorAll('main')).toHaveLength(0);
    expect(workspace).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(workspace).toHaveClass('w-full', 'max-w-[1600px]', 'mx-auto', 'px-4', 'xl:px-8', 'flex', 'flex-col', 'py-5', 'md:py-6');
    expect(workspace).not.toHaveClass('px-6', 'md:px-8', 'xl:px-12', 'py-8');
    await waitFor(() => expect(getNotificationPreferences).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId('personal-settings-console')).toBeInTheDocument();
    expect(screen.getByTestId('personal-settings-primary-board')).toHaveAttribute('data-linear-primitive', 'console-board');
    expect(screen.getByTestId('personal-settings-help-rail')).toHaveAttribute('data-linear-primitive', 'context-rail');
    expect(screen.getByRole('heading', { level: 1, name: '账户中心' })).toBeInTheDocument();
    expect(screen.getByTestId('personal-settings-account-row')).toBeInTheDocument();
    expect(screen.getByTestId('personal-settings-notification-row')).toBeInTheDocument();
    expect(screen.getByTestId('personal-settings-privacy-section')).toBeInTheDocument();
    expect(profileHeader).toHaveTextContent('Admin');
    expect(screen.getByText('账户与安全')).toBeInTheDocument();
    expect(screen.getByText('隐私设置')).toBeInTheDocument();
    expect(screen.getByText('显示与偏好')).toBeInTheDocument();
    expect(screen.queryByText(zh('settings.personalAdminConsoleTitle'))).not.toBeInTheDocument();
    expect(screen.queryByText(zh('settings.personalAdminConsoleDesc'))).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: zh('nav.independentConsole') })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: zh('adminNav.logs') })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /管理工具/ })).not.toBeInTheDocument();
    expect(screen.getByDisplayValue('admin@example.com')).toBeInTheDocument();
    expect(screen.getByDisplayValue('https://discord.com/api/webhooks/123/token')).toBeInTheDocument();
    expect(saveButton).toBeInTheDocument();
    expect(saveButton).toHaveAttribute('data-terminal-primitive', 'button');
    expect(within(screen.getByTestId('personal-settings-boundary-disclosure')).getByRole('button')).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByTestId('change-password-card')).toBeInTheDocument();
    expect(screen.getByText('修改密码')).toBeInTheDocument();
    expect(screen.getByTestId('font-size-card')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '紧凑' }));
    fireEvent.click(screen.getByRole('button', { name: /完整数字/ }));
    expect(setDataDensity).toHaveBeenCalledWith('compact');
    expect(setNumberFormat).toHaveBeenCalledWith('full');
  });

  it('saves email and Discord notification targets together for signed-in users', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      passwordChangeable: false,
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: false,
      loggedIn: true,
      currentUser: {
        username: 'alice',
        displayName: 'Alice',
      },
    });
    getNotificationPreferences.mockResolvedValue({
      channel: 'email',
      enabled: false,
      email: null,
      emailEnabled: false,
      discordEnabled: false,
      discordWebhook: null,
      deliveryAvailable: true,
      emailDeliveryAvailable: true,
      discordDeliveryAvailable: true,
      updatedAt: null,
    });
    updateNotificationPreferences.mockResolvedValue({
      channel: 'multi',
      enabled: true,
      email: 'alice@example.com',
      emailEnabled: true,
      discordEnabled: true,
      discordWebhook: 'https://discord.com/api/webhooks/999/token',
      deliveryAvailable: true,
      emailDeliveryAvailable: true,
      discordDeliveryAvailable: true,
      updatedAt: '2026-04-15T10:00:00Z',
    });

    render(
      <MemoryRouter>
        <PersonalSettingsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(getNotificationPreferences).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByLabelText(zh('settings.personalNotificationEmailToggle')));
    fireEvent.change(screen.getByLabelText(zh('settings.personalNotificationEmailLabel')), { target: { value: 'alice@example.com' } });
    fireEvent.click(screen.getByLabelText(zh('settings.personalNotificationDiscordToggle')));
    fireEvent.change(screen.getByLabelText(zh('settings.personalNotificationDiscordLabel')), {
      target: { value: 'https://discord.com/api/webhooks/999/token' },
    });
    fireEvent.click(screen.getByRole('button', { name: zh('settings.personalNotificationSaveAction') }));

    await waitFor(() => {
      expect(updateNotificationPreferences).toHaveBeenCalledWith({
        emailEnabled: true,
        email: 'alice@example.com',
        discordEnabled: true,
        discordWebhook: 'https://discord.com/api/webhooks/999/token',
      });
    });
    expect(await screen.findByText(zh('settings.personalNotificationTargetsSaved'))).toBeInTheDocument();
  });
});
