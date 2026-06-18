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

  it('sanitizes unsafe title and message fields before rendering', () => {
    languageState.value = 'en';

    render(
      <ApiErrorAlert
        error={buildError({
          title: 'provider runtime failure',
          message: 'requestId=req-123 traceId=trace-999 token=bearer-abc cache adapter internal raw debug',
          rawMessage: 'provider stack trace requestId=req-123 traceId=trace-999 token=bearer-abc',
          category: 'unknown',
        })}
        actionLabel="Retry"
        onAction={() => undefined}
      />,
    );

    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('This request is temporarily unavailable.');
    expect(alert).toHaveTextContent('Please try again shortly.');
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    expect(alert.textContent || '').not.toMatch(/provider|runtime|requestId|traceId|token|bearer|cache|adapter|internal|raw|debug|stack/i);
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
    expect(screen.getByText(/If access is still blocked after sign-in, reopen the current page and try again\./)).toBeInTheDocument();
    expect(document.body.textContent || '').not.toContain('raw trace');
  });
});
