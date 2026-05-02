import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Drawer } from '../Drawer';

describe('Drawer', () => {
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
});
