import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { translate } from '../../../i18n/core';
import type { ParsedApiError } from '../../../api/error';
import { ApiErrorAlert } from '../ApiErrorAlert';

const { languageState } = vi.hoisted(() => ({
  languageState: { value: 'zh' as 'zh' | 'en' },
}));

vi.mock('../../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: languageState.value,
    t: (key: string, vars?: Record<string, string | number | undefined>) => translate(languageState.value, key, vars),
  }),
}));

function buildError(overrides: Partial<ParsedApiError> = {}): ParsedApiError {
  return {
    title: '请求失败',
    message: '请稍后重试。',
    rawMessage: 'provider exploded stack trace token=abc',
    category: 'upstream_unavailable',
    ...overrides,
  };
}

describe('ApiErrorAlert', () => {
  it('hides raw diagnostic details by default while keeping consumer-safe guidance', () => {
    render(<ApiErrorAlert error={buildError()} />);

    expect(screen.getByRole('alert')).toHaveTextContent('请求失败');
    expect(screen.getByText('请稍后重试。')).toBeInTheDocument();
    expect(screen.getByText('详细技术信息已隐藏。')).toBeInTheDocument();
    expect(document.body.textContent || '').not.toContain('provider exploded');
    expect(document.body.textContent || '').not.toContain('stack trace');
    expect(document.body.textContent || '').not.toContain('token=abc');
    expect(screen.queryByText('查看详情')).not.toBeInTheDocument();
  });

  it('renders localized auth-required guidance through i18n keys', () => {
    languageState.value = 'en';

    render(
      <ApiErrorAlert
        error={buildError({
          title: 'Authentication required',
          message: 'Sign in to continue.',
          rawMessage: 'session expired raw trace',
          category: 'auth_required',
        })}
      />,
    );

    expect(screen.getByText(/Sign in first, then reopen the page you were using\./)).toBeInTheDocument();
    expect(screen.getByText(/If access is still blocked after sign-in, verify the current session has not expired\./)).toBeInTheDocument();
    expect(document.body.textContent || '').not.toContain('raw trace');
  });
});
