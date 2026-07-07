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

  it('exposes modal dialog semantics and keeps keyboard focus inside', () => {
    const opener = document.createElement('button');
    opener.textContent = 'Open confirm dialog';
    document.body.appendChild(opener);
    opener.focus();

    render(
      <ConfirmDialog
        isOpen
        title="Delete position"
        message="This cannot be undone."
        confirmText="Delete"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    const dialog = screen.getByRole('dialog', { name: 'Delete position' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAccessibleDescription('This cannot be undone.');
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();

    screen.getByRole('button', { name: 'Delete' }).focus();
    act(() => {
      fireEvent.keyDown(document, { key: 'Tab' });
    });
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();

    act(() => {
      fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    });
    expect(screen.getByRole('button', { name: 'Delete' })).toHaveFocus();

    opener.remove();
  });

  it('focuses the typed confirmation field first when a confirmation phrase is required', () => {
    render(
      <ConfirmDialog
        isOpen
        title="Factory reset"
        message="Type the phrase to continue."
        confirmationPhrase="RESET"
        confirmationValue=""
        onConfirmationValueChange={vi.fn()}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByLabelText('Confirm')).toHaveFocus();
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeDisabled();
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

  it('returns focus to the previous element when the dialog closes', () => {
    const opener = document.createElement('button');
    opener.textContent = 'Open confirm dialog';
    document.body.appendChild(opener);
    opener.focus();

    const { rerender } = render(
      <ConfirmDialog
        isOpen
        title="Delete position"
        message="This cannot be undone."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();

    rerender(
      <ConfirmDialog
        isOpen={false}
        title="Delete position"
        message="This cannot be undone."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    act(() => {
      vi.advanceTimersByTime(180);
    });

    expect(opener).toHaveFocus();
    opener.remove();
  });
});
