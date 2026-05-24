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

    expect(screen.getByTestId('auth-guard-shell')).toHaveAttribute('data-workspace-width', 'near-full');
    expect(screen.getByTestId('auth-guard-shell')).toHaveClass(
      'flex',
      'w-full',
      'flex-1',
      'items-center',
      'justify-center',
      'py-10',
    );
    expect(screen.getByTestId('auth-guard-shell').className).not.toContain('bg-[#030303]/80');
    expect(screen.getByTestId('auth-guard-card')).toHaveClass(
      'w-full',
      'max-w-[28rem]',
      'border',
      'bg-[var(--wolfy-surface-console)]',
    );
    expect(screen.getByRole('heading', { name: '登录解锁 市场总览' })).toBeInTheDocument();
    expect(screen.getByText('游客模式仅支持首页基础查询。保存个人工作区、深度历史回溯及进阶指标测算，均需绑定正式账户。')).toBeInTheDocument();
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
    expect(screen.getByRole('button', { name: 'Sign in / Create account' })).toHaveClass('bg-[var(--wolfy-accent)]', 'text-[#f7f8ff]');
    expectNoRawI18nKeys(container);
    fireEvent.click(screen.getByRole('button', { name: 'Sign in / Create account' }));
    expect(navigate).toHaveBeenCalledWith('/en/login');
  });
});
