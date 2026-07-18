import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Drawer } from '../Drawer';
import { settleDrawerInteractionReady, settleDrawerOpen } from './modalTestHelpers';

describe('Drawer', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('closes when Escape is pressed while the drawer is open', async () => {
    const onClose = vi.fn();
    render(
      <Drawer isOpen onClose={onClose} title="Navigation">
        <div>content</div>
      </Drawer>,
    );

    await settleDrawerOpen();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('owns modal focus entry and keyboard containment while open', async () => {
    render(
      <Drawer isOpen onClose={vi.fn()} title="Navigation">
        <button type="button">First action</button>
        <button type="button">Last action</button>
      </Drawer>,
    );

    await settleDrawerInteractionReady();

    const drawer = screen.getByRole('dialog', { name: 'Navigation' });
    expect(drawer).toHaveAttribute('aria-modal', 'true');
    const closeButton = drawer.querySelector<HTMLButtonElement>('.drawer__close');
    expect(closeButton).not.toBeNull();
    expect(closeButton).toHaveFocus();

    within(drawer).getByRole('button', { name: 'Last action' }).focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(closeButton).toHaveFocus();

    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(within(drawer).getByRole('button', { name: 'Last action' })).toHaveFocus();
  });

  it('falls back to the drawer container when explicit and discovered targets are invalid', async () => {
    const { rerender } = render(
      <Drawer isOpen={false} onClose={vi.fn()} title="Navigation">
        <button type="button" disabled>Disabled action</button>
        <button type="button" hidden>Hidden action</button>
        <button type="button" inert>Inert action</button>
        <button type="button" style={{ display: 'none' }}>CSS hidden action</button>
      </Drawer>,
    );

    rerender(
      <Drawer isOpen onClose={vi.fn()} title="Navigation">
        <button type="button" disabled>Disabled action</button>
        <button type="button" hidden>Hidden action</button>
        <button type="button" inert>Inert action</button>
        <button type="button" style={{ display: 'none' }}>CSS hidden action</button>
      </Drawer>,
    );
    await act(async () => {
      await Promise.resolve();
    });

    const drawer = screen.getByRole('dialog', { name: 'Navigation' });
    drawer.querySelector('.drawer__close')?.remove();

    await settleDrawerInteractionReady();

    expect(drawer).toHaveFocus();
  });

  it('excludes disabled, hidden and inert elements from Tab boundaries', async () => {
    render(
      <Drawer isOpen onClose={vi.fn()} title="Navigation">
        <button type="button">Only valid action</button>
        <button type="button" disabled>Disabled action</button>
        <button type="button" hidden>Hidden action</button>
        <button type="button" inert>Inert action</button>
        <button type="button" style={{ visibility: 'hidden' }}>CSS hidden action</button>
      </Drawer>,
    );

    await settleDrawerInteractionReady();

    const drawer = screen.getByRole('dialog', { name: 'Navigation' });
    const closeButton = drawer.querySelector<HTMLButtonElement>('.drawer__close');
    const validAction = within(drawer).getByRole('button', { name: 'Only valid action' });
    expect(closeButton).not.toBeNull();

    validAction.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(closeButton).toHaveFocus();

    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(validAction).toHaveFocus();
  });

  it('keeps page content inert until close completes and restores valid invoking focus', async () => {
    const opener = document.createElement('button');
    opener.textContent = 'Open drawer';
    document.body.appendChild(opener);
    opener.focus();
    const { rerender } = render(
      <Drawer isOpen onClose={vi.fn()} title="Navigation">
        <button type="button">Drawer action</button>
      </Drawer>,
    );

    await settleDrawerInteractionReady();

    expect(opener.closest('[inert]')).not.toBeNull();

    rerender(
      <Drawer isOpen={false} onClose={vi.fn()} title="Navigation">
        <button type="button">Drawer action</button>
      </Drawer>,
    );
    await act(async () => {
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(189);
    });

    expect(opener).not.toHaveFocus();
    expect(opener.closest('[inert]')).not.toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });

    expect(opener.closest('[inert]')).toBeNull();
    expect(opener).toHaveFocus();
    opener.remove();
  });

  it('does not restore focus to an invoking element that becomes disabled', async () => {
    const opener = document.createElement('button');
    opener.textContent = 'Open drawer';
    document.body.appendChild(opener);
    opener.focus();
    const { rerender } = render(
      <Drawer isOpen onClose={vi.fn()} title="Navigation">
        <button type="button">Drawer action</button>
      </Drawer>,
    );

    await settleDrawerInteractionReady();
    opener.disabled = true;

    rerender(
      <Drawer isOpen={false} onClose={vi.fn()} title="Navigation">
        <button type="button">Drawer action</button>
      </Drawer>,
    );
    await act(async () => {
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(190);
    });

    expect(opener).not.toHaveFocus();
    opener.remove();
  });

  it('ignores the opening gesture on the backdrop before allowing outside-close interactions', async () => {
    const onClose = vi.fn();
    render(
      <Drawer isOpen onClose={onClose} title="Navigation">
        <div>content</div>
      </Drawer>,
    );

    const backdrop = screen.getByTestId('drawer-backdrop');
    expect(backdrop).toBeInTheDocument();

    fireEvent.pointerDown(backdrop);
    expect(onClose).not.toHaveBeenCalled();

    await settleDrawerInteractionReady();
    fireEvent.pointerDown(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does not close when pointerdown starts inside the drawer panel', async () => {
    const onClose = vi.fn();
    render(
      <Drawer isOpen onClose={onClose} title="Navigation">
        <div>content</div>
      </Drawer>,
    );

    await settleDrawerInteractionReady();

    const panel = screen.getByText('content').closest('dialog');
    expect(panel).not.toBeNull();

    fireEvent.pointerDown(panel!);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('can disable backdrop-close for drawers that must stay open until explicitly dismissed', async () => {
    const onClose = vi.fn();
    render(
      <Drawer isOpen onClose={onClose} title="Navigation" closeOnBackdropClick={false}>
        <div>content</div>
      </Drawer>,
    );

    const backdrop = screen.getByTestId('drawer-backdrop');
    expect(backdrop).toBeInTheDocument();

    await settleDrawerInteractionReady();
    fireEvent.pointerDown(backdrop);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('closes only once for a single outside interaction', async () => {
    const onClose = vi.fn();
    render(
      <Drawer isOpen onClose={onClose} title="Navigation">
        <div>content</div>
      </Drawer>,
    );

    const backdrop = screen.getByTestId('drawer-backdrop');
    expect(backdrop).toBeInTheDocument();

    await settleDrawerInteractionReady();
    fireEvent.pointerDown(backdrop);
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('cancels pending open animation work when unmounted before the drawer settles', () => {
    const cancelAnimationFrameSpy = vi.spyOn(window, 'cancelAnimationFrame');
    const onClose = vi.fn();
    const { unmount } = render(
      <Drawer isOpen onClose={onClose} title="Navigation">
        <div>content</div>
      </Drawer>,
    );

    unmount();

    expect(cancelAnimationFrameSpy).toHaveBeenCalled();
    act(() => {
      vi.runOnlyPendingTimers();
    });
    expect(onClose).not.toHaveBeenCalled();
  });
});
