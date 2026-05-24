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

  it('renders the centered auth guard as a fixed frosted modal overlay in Chinese', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/zh/market-overview']}>
        <AuthGuardOverlay moduleName="市场总览" />
      </MemoryRouter>,
    );

    expect(screen.getByRole('dialog', { name: '登录解锁 市场总览' })).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByTestId('auth-guard-overlay')).toHaveClass(
      'fixed',
      'inset-0',
      'z-[80]',
      'grid',
      'place-items-center',
    );
    expect(screen.queryByTestId('auth-guard-shell')).not.toBeInTheDocument();
    expect(screen.getByTestId('auth-guard-scrim')).toHaveClass(
      'absolute',
      'inset-0',
      'backdrop-blur-md',
    );
    expect(screen.getByTestId('auth-guard-scrim').className).not.toContain('bg-black');
    expect(screen.getByTestId('auth-guard-card')).toHaveClass(
      'relative',
      'z-10',
      'w-[min(92vw,28rem)]',
      'border',
      'backdrop-blur-2xl',
    );
    expect(screen.getByRole('heading', { name: '登录解锁 市场总览' })).toBeInTheDocument();
    expect(screen.getByText('游客模式仅支持首页基础查询。保存个人工作区、深度历史回溯及进阶指标测算，均需绑定正式账户。')).toBeInTheDocument();
    expectNoRawI18nKeys(container);
    fireEvent.click(screen.getByRole('button', { name: '登录 / 创建账户' }));
    expect(navigate).toHaveBeenCalledWith('/zh/login');
  });

  it('keeps optional protected children as a non-interactive blurred backdrop', () => {
    render(
      <MemoryRouter initialEntries={['/zh/portfolio']}>
        <AuthGuardOverlay moduleName="持仓管理">
          <section data-testid="protected-page">locked portfolio surface</section>
        </AuthGuardOverlay>
      </MemoryRouter>,
    );

    expect(screen.getByTestId('auth-guard-backdrop-content')).toHaveAttribute('aria-hidden', 'true');
    expect(screen.getByTestId('auth-guard-backdrop-content')).toHaveClass(
      'pointer-events-none',
      'select-none',
      'blur-[2px]',
    );
    expect(screen.getByTestId('protected-page')).toHaveTextContent('locked portfolio surface');
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
