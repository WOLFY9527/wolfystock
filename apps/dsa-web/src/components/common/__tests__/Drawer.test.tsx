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
