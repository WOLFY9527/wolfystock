import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ConfirmDialog } from '../ConfirmDialog';

vi.mock('../../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    t: (key: string) => {
      if (key === 'common.cancel') return 'Cancel';
      if (key === 'common.confirm') return 'Confirm';
      if (key === 'common.confirmAction') return 'Confirm action';
      if (key === 'common.confirmationRequired') return 'Confirmation required';
      return key;
    },
  }),
}));

describe('ConfirmDialog', () => {
  const originalRequestAnimationFrame = window.requestAnimationFrame;
  const originalCancelAnimationFrame = window.cancelAnimationFrame;

  beforeEach(() => {
    vi.useFakeTimers();
    window.requestAnimationFrame = ((callback: FrameRequestCallback) => window.setTimeout(() => callback(performance.now()), 16)) as typeof window.requestAnimationFrame;
    window.cancelAnimationFrame = ((handle: number) => window.clearTimeout(handle)) as typeof window.cancelAnimationFrame;
  });

  afterEach(() => {
    window.requestAnimationFrame = originalRequestAnimationFrame;
    window.cancelAnimationFrame = originalCancelAnimationFrame;
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('keeps the dialog mounted through the close transition before unmounting', () => {
    const onCancel = vi.fn();
    const { rerender } = render(
      <ConfirmDialog
        isOpen
        title="Delete position"
        message="This cannot be undone."
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />
    );

    expect(screen.getByText('Delete position')).toBeInTheDocument();

    rerender(
      <ConfirmDialog
        isOpen={false}
        title="Delete position"
        message="This cannot be undone."
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />
    );

    expect(screen.getByText('Delete position')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(179);
    });
    expect(screen.getByText('Delete position')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.queryByText('Delete position')).not.toBeInTheDocument();
  });

  it('uses the latest cancel handler for the Escape listener', () => {
    const initialCancel = vi.fn();
    const latestCancel = vi.fn();
    const { rerender } = render(
      <ConfirmDialog
        isOpen
        title="Delete position"
        message="This cannot be undone."
        onConfirm={vi.fn()}
        onCancel={initialCancel}
      />
    );

    rerender(
      <ConfirmDialog
        isOpen
        title="Delete position"
        message="This cannot be undone."
        onConfirm={vi.fn()}
        onCancel={latestCancel}
      />
    );

    act(() => {
      fireEvent.keyDown(document, { key: 'Escape' });
    });

    expect(initialCancel).not.toHaveBeenCalled();
    expect(latestCancel).toHaveBeenCalledTimes(1);
  });
});
