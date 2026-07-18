import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ConfirmDialog } from '../ConfirmDialog';
import { Drawer } from '../Drawer';
import { advanceConfirmDialogClose, settleConfirmDialogOpen } from './modalTestHelpers';

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
  const originalInnerWidth = window.innerWidth;

  beforeEach(() => {
    vi.useFakeTimers();
    window.requestAnimationFrame = ((callback: FrameRequestCallback) => window.setTimeout(() => callback(performance.now()), 16)) as typeof window.requestAnimationFrame;
    window.cancelAnimationFrame = ((handle: number) => window.clearTimeout(handle)) as typeof window.cancelAnimationFrame;
  });

  afterEach(() => {
    window.requestAnimationFrame = originalRequestAnimationFrame;
    window.cancelAnimationFrame = originalCancelAnimationFrame;
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: originalInnerWidth });
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('keeps the dialog mounted through the close transition before unmounting', async () => {
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

    await settleConfirmDialogOpen();

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

    await advanceConfirmDialogClose(0);

    expect(screen.getByText('Delete position')).toBeInTheDocument();

    await advanceConfirmDialogClose(179);
    expect(screen.getByText('Delete position')).toBeInTheDocument();

    await advanceConfirmDialogClose(1);
    expect(screen.queryByText('Delete position')).not.toBeInTheDocument();
  });

  it('exposes modal dialog semantics and keeps keyboard focus inside', async () => {
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

    await settleConfirmDialogOpen();

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

  it('focuses the typed confirmation field first when a confirmation phrase is required', async () => {
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

    await settleConfirmDialogOpen();

    expect(screen.getByLabelText('Confirm')).toHaveFocus();
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeDisabled();
  });

  it('uses the latest cancel handler for the Escape listener', async () => {
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

    await settleConfirmDialogOpen();

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

  it('returns focus to the previous element when the dialog closes', async () => {
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

    await settleConfirmDialogOpen();

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

    await advanceConfirmDialogClose();

    expect(opener).toHaveFocus();
    opener.remove();
  });

  it('uses one ordered trap for a nested dialog and dismisses only the top overlay', async () => {
    const drawerClose = vi.fn();
    const dialogCancel = vi.fn();
    const addEventListenerSpy = vi.spyOn(document, 'addEventListener');
    const removeEventListenerSpy = vi.spyOn(document, 'removeEventListener');
    const { rerender, unmount } = render(
      <Drawer isOpen onClose={drawerClose} title="Navigation">
        <button type="button">Open confirmation</button>
        <ConfirmDialog
          isOpen={false}
          title="Delete position"
          message="This cannot be undone."
          confirmText="Delete"
          onConfirm={vi.fn()}
          onCancel={dialogCancel}
        />
      </Drawer>,
    );

    await act(async () => {
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(112);
    });
    const drawer = screen.getByRole('dialog', { name: 'Navigation' });
    const opener = within(drawer).getByRole('button', { name: 'Open confirmation' });
    opener.focus();

    rerender(
      <Drawer isOpen onClose={drawerClose} title="Navigation">
        <button type="button">Open confirmation</button>
        <ConfirmDialog
          isOpen
          title="Delete position"
          message="This cannot be undone."
          confirmText="Delete"
          onConfirm={vi.fn()}
          onCancel={dialogCancel}
        />
      </Drawer>,
    );
    await settleConfirmDialogOpen();

    const dialog = screen.getByRole('dialog', { name: 'Delete position' });
    const cancelButton = within(dialog).getByRole('button', { name: 'Cancel' });
    const confirmButton = within(dialog).getByRole('button', { name: 'Delete' });
    expect(cancelButton).toHaveFocus();
    expect(opener.closest('[inert]')).not.toBeNull();
    expect(addEventListenerSpy.mock.calls.filter(([type]) => type === 'keydown')).toHaveLength(1);

    confirmButton.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(cancelButton).toHaveFocus();
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(confirmButton).toHaveFocus();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(dialogCancel).toHaveBeenCalledTimes(1);
    expect(drawerClose).not.toHaveBeenCalled();

    rerender(
      <Drawer isOpen onClose={drawerClose} title="Navigation">
        <button type="button">Open confirmation</button>
        <ConfirmDialog
          isOpen={false}
          title="Delete position"
          message="This cannot be undone."
          confirmText="Delete"
          onConfirm={vi.fn()}
          onCancel={dialogCancel}
        />
      </Drawer>,
    );
    await advanceConfirmDialogClose();

    expect(opener.closest('[inert]')).toBeNull();
    expect(opener).toHaveFocus();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(drawerClose).toHaveBeenCalledTimes(1);

    unmount();
    expect(removeEventListenerSpy.mock.calls.filter(([type]) => type === 'keydown')).toHaveLength(1);
  });

  it('orders simultaneously mounted nested overlays at a narrow viewport', async () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 320 });
    const drawerClose = vi.fn();
    const dialogCancel = vi.fn();
    render(
      <Drawer isOpen onClose={drawerClose} title="Navigation">
        <button type="button">Drawer action</button>
        <ConfirmDialog
          isOpen
          title="Delete position"
          message="This cannot be undone."
          onConfirm={vi.fn()}
          onCancel={dialogCancel}
        />
      </Drawer>,
    );

    await act(async () => {
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(112);
    });

    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(dialogCancel).toHaveBeenCalledTimes(1);
    expect(drawerClose).not.toHaveBeenCalled();
  });

  it('preserves body and background state across rapid reopen and restores it on unmount', async () => {
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'clip';
    const addEventListenerSpy = vi.spyOn(document, 'addEventListener');
    const removeEventListenerSpy = vi.spyOn(document, 'removeEventListener');
    const opener = document.createElement('button');
    opener.textContent = 'Open confirm dialog';
    document.body.appendChild(opener);
    const preInertContent = document.createElement('div');
    preInertContent.setAttribute('inert', '');
    document.body.appendChild(preInertContent);
    opener.focus();
    const props = {
      title: 'Delete position',
      message: 'This cannot be undone.',
      onConfirm: vi.fn(),
      onCancel: vi.fn(),
    };
    const { rerender, unmount } = render(<ConfirmDialog isOpen {...props} />);

    await settleConfirmDialogOpen();
    expect(document.body.style.overflow).toBe('hidden');
    expect(opener.closest('[inert]')).not.toBeNull();
    expect(addEventListenerSpy.mock.calls.filter(([type]) => type === 'keydown')).toHaveLength(1);

    rerender(<ConfirmDialog isOpen={false} {...props} />);
    await advanceConfirmDialogClose(179);
    expect(opener).not.toHaveFocus();
    expect(document.body.style.overflow).toBe('hidden');

    rerender(<ConfirmDialog isOpen {...props} />);
    await settleConfirmDialogOpen();
    expect(document.body.style.overflow).toBe('hidden');
    expect(opener.closest('[inert]')).not.toBeNull();
    expect(addEventListenerSpy.mock.calls.filter(([type]) => type === 'keydown')).toHaveLength(1);
    expect(removeEventListenerSpy.mock.calls.filter(([type]) => type === 'keydown')).toHaveLength(0);

    unmount();
    expect(document.body.style.overflow).toBe('clip');
    expect(opener.closest('[inert]')).toBeNull();
    expect(preInertContent).toHaveAttribute('inert');
    expect(opener).toHaveFocus();
    expect(removeEventListenerSpy.mock.calls.filter(([type]) => type === 'keydown')).toHaveLength(1);

    opener.remove();
    preInertContent.remove();
    document.body.style.overflow = originalOverflow;
  });

  it('does not restore focus to a detached invoking element', async () => {
    const opener = document.createElement('button');
    opener.textContent = 'Open confirm dialog';
    document.body.appendChild(opener);
    opener.focus();
    const { unmount } = render(
      <ConfirmDialog
        isOpen
        title="Delete position"
        message="This cannot be undone."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    await settleConfirmDialogOpen();
    opener.remove();
    unmount();

    expect(opener).not.toHaveFocus();
  });
});
