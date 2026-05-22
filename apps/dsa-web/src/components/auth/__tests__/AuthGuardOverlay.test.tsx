import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { expectNoRawI18nKeys } from '../../../test-utils/i18nRawKeySentinel';
import { AuthGuardOverlay } from '../AuthGuardOverlay';

const { languageState } = vi.hoisted(() => ({
  languageState: { value: 'zh' as 'zh' | 'en' },
}));

vi.mock('../../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: languageState.value,
  }),
}));

const navigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigate,
  };
});

describe('AuthGuardOverlay', () => {
  beforeEach(() => {
    languageState.value = 'zh';
    navigate.mockReset();
  });

  it('renders the centered auth guard shell in Chinese', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/zh/market-overview']}>
        <AuthGuardOverlay moduleName="市场总览" />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('auth-guard-shell')).toHaveClass(
      'z-40',
      'flex',
      'w-full',
      'flex-1',
      'items-center',
      'justify-center',
      'bg-[#030303]/80',
      'backdrop-blur-sm',
    );
    expect(screen.getByTestId('auth-guard-card')).toHaveClass(
      'w-[360px]',
      'bg-white/[0.02]',
      'border',
      'border-white/5',
      'rounded-[24px]',
      'shadow-2xl',
    );
    expect(screen.getByRole('heading', { name: '登录解锁 市场总览' })).toBeInTheDocument();
    expectNoRawI18nKeys(container);
    fireEvent.click(screen.getByRole('button', { name: '登录 / 创建账户' }));
    expect(navigate).toHaveBeenCalledWith('/zh/login');
  });

  it('renders the English CTA copy and opens the localized login route', () => {
    languageState.value = 'en';

    const { container } = render(
      <MemoryRouter initialEntries={['/en/portfolio']}>
        <AuthGuardOverlay moduleName="Portfolio" />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'Sign in to unlock Portfolio' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign in / Create account' })).toHaveClass('bg-white', 'text-black', 'active:scale-95');
    expectNoRawI18nKeys(container);
    fireEvent.click(screen.getByRole('button', { name: 'Sign in / Create account' }));
    expect(navigate).toHaveBeenCalledWith('/en/login');
  });
});
