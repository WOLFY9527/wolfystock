import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Drawer } from '../Drawer';

describe('Drawer', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('closes when Escape is pressed while the drawer is open', () => {
    const onClose = vi.fn();
    render(
      <Drawer isOpen onClose={onClose} title="Navigation">
        <div>content</div>
      </Drawer>,
    );

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
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

    fireEvent.click(backdrop);
    expect(onClose).not.toHaveBeenCalled();

    await new Promise((resolve) => window.setTimeout(resolve, 500));
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
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

    await new Promise((resolve) => window.setTimeout(resolve, 500));
    fireEvent.click(backdrop);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('cancels pending open animation work when unmounted before the drawer settles', () => {
    vi.useFakeTimers();
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
