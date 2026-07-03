import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { translate } from '../../../i18n/core';
import { expectNoRawI18nKeys } from '../../../test-utils/i18nRawKeySentinel';
import { AuthGuardOverlay } from '../AuthGuardOverlay';

const { languageState } = vi.hoisted(() => ({
  languageState: { value: 'zh' as 'zh' | 'en' },
}));

vi.mock('../../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: languageState.value,
    t: (key: string, vars?: Record<string, string | number | undefined>) => translate(languageState.value, key, vars),
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
    document.body.innerHTML = '';
  });

  it('renders the centered auth guard as a fixed frosted modal overlay in Chinese', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/zh/market-overview']}>
        <AuthGuardOverlay moduleName="市场总览" />
      </MemoryRouter>,
    );

    expect(screen.getByRole('dialog', { name: '需要登录' })).toHaveAttribute('aria-modal', 'true');
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
    expect(screen.getByRole('heading', { name: '需要登录' })).toBeInTheDocument();
    expect(screen.getByText('请先登录后继续访问该页面。')).toBeInTheDocument();
    expect(screen.getByText('登录后可返回刚才的研究页面。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '返回首页' })).toBeInTheDocument();
    expectNoRawI18nKeys(container);
    fireEvent.click(screen.getByRole('button', { name: '前往登录 市场总览' }));
    expect(navigate).toHaveBeenCalledWith('/zh/login?redirect=%2Fzh%2Fmarket-overview');
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

    expect(screen.getByRole('heading', { name: 'Sign-in required' })).toBeInTheDocument();
    expect(screen.getByText('Sign in before continuing to this page.')).toBeInTheDocument();
    expect(screen.getByText('After signing in, you can return to the research page you just opened.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Go to sign in Portfolio' })).toHaveClass('bg-[var(--wolfy-accent)]', 'text-[#f7f8ff]');
    expect(screen.getByRole('button', { name: 'Return home' })).toBeInTheDocument();
    expectNoRawI18nKeys(container);
    fireEvent.click(screen.getByRole('button', { name: 'Go to sign in Portfolio' }));
    expect(navigate).toHaveBeenCalledWith('/en/login?redirect=%2Fen%2Fportfolio');
  });

  it('prefers zh guest-gate copy on zh routes even when the UI language state is English', () => {
    languageState.value = 'en';

    render(
      <MemoryRouter initialEntries={['/zh/portfolio']}>
        <AuthGuardOverlay moduleName="持仓管理" />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: '需要登录' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Sign-in required' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '前往登录 持仓管理' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '返回首页' })).toBeInTheDocument();
  });

  it('moves focus to the primary login CTA when the blocking dialog opens', () => {
    const trigger = document.createElement('button');
    trigger.textContent = 'Protected route trigger';
    document.body.appendChild(trigger);
    trigger.focus();
    expect(trigger).toHaveFocus();

    render(
      <MemoryRouter initialEntries={['/zh/market-overview']}>
        <AuthGuardOverlay moduleName="市场总览" />
      </MemoryRouter>,
    );

    expect(screen.getByRole('button', { name: '前往登录 市场总览' })).toHaveFocus();
  });

  it('wraps Tab and Shift+Tab inside the auth dialog instead of exposing protected backdrop controls', () => {
    render(
      <MemoryRouter initialEntries={['/zh/portfolio']}>
        <AuthGuardOverlay moduleName="持仓管理">
          <button type="button">背景操作</button>
        </AuthGuardOverlay>
      </MemoryRouter>,
    );

    const loginCta = screen.getByRole('button', { name: '前往登录 持仓管理' });
    const safeExitButton = screen.getByRole('button', { name: '返回首页' });
    expect(loginCta).toHaveFocus();

    fireEvent.keyDown(document, { key: 'Tab' });
    expect(safeExitButton).toHaveFocus();
    expect(screen.getByRole('button', { name: '背景操作', hidden: true })).not.toHaveFocus();

    fireEvent.keyDown(document, { key: 'Tab' });
    expect(loginCta).toHaveFocus();
    expect(screen.getByRole('button', { name: '背景操作', hidden: true })).not.toHaveFocus();

    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(safeExitButton).toHaveFocus();
    expect(screen.getByRole('button', { name: '背景操作', hidden: true })).not.toHaveFocus();
  });

  it('restores focus to the previously focused element when the overlay unmounts', () => {
    const trigger = document.createElement('button');
    trigger.textContent = 'Open protected route';
    document.body.appendChild(trigger);
    trigger.focus();

    const { unmount } = render(
      <MemoryRouter initialEntries={['/zh/portfolio']}>
        <AuthGuardOverlay moduleName="持仓管理" />
      </MemoryRouter>,
    );

    expect(screen.getByRole('button', { name: '前往登录 持仓管理' })).toHaveFocus();

    unmount();

    expect(trigger).toHaveFocus();
  });

  it('keeps Escape non-dismissible and exposes an explicit safe exit without bypassing auth', () => {
    render(
      <MemoryRouter initialEntries={['/zh/portfolio']}>
        <AuthGuardOverlay moduleName="持仓管理" />
      </MemoryRouter>,
    );

    fireEvent.keyDown(document, { key: 'Escape' });

    expect(screen.getByRole('dialog', { name: '需要登录' })).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: '返回首页' }));
    expect(navigate).toHaveBeenCalledWith('/zh');

    fireEvent.click(screen.getByRole('button', { name: '前往登录 持仓管理' }));
    expect(navigate).toHaveBeenLastCalledWith('/zh/login?redirect=%2Fzh%2Fportfolio');
  });

  it('keeps the auth-required copy consumer-safe and free from raw auth or runtime terms', () => {
    render(
      <MemoryRouter initialEntries={['/zh/settings']}>
        <AuthGuardOverlay moduleName="个人设置" />
      </MemoryRouter>,
    );

    const overlayText = screen.getByTestId('auth-guard-card').textContent || '';
    expect(overlayText).not.toMatch(/token|session|cookie|bearer|auth header|debug|provider|runtime|stack|Error:|requestId|traceId|schemaVersion|policyVersion|raw|internal|local_db|fallback_source|fixture|adapter|cache/i);
    expect(overlayText).not.toMatch(/buy|sell|hold|recommend|target|stop|position size|买入|卖出|持有|推荐|目标价|止损|仓位建议|加仓|减仓/i);
  });
});
