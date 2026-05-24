import { render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useSafariWarmActivation } from '../useSafariInteractionReady';

function WarmActivationProbe() {
  const { ref: buttonRef } = useSafariWarmActivation<HTMLButtonElement>(() => undefined);

  return (
    <button type="button" ref={buttonRef}>
      probe
    </button>
  );
}

describe('useSafariWarmActivation', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('releases the warmup pointer listener when unmounted', () => {
    const addEventListenerSpy = vi.spyOn(HTMLElement.prototype, 'addEventListener');
    const removeEventListenerSpy = vi.spyOn(HTMLElement.prototype, 'removeEventListener');

    const { unmount } = render(<WarmActivationProbe />);

    const pointerdownAddCalls = addEventListenerSpy.mock.calls.filter(([type]) => type === 'pointerdown').length;
    const pointerdownRemoveCallsBeforeUnmount = removeEventListenerSpy.mock.calls
      .filter(([type]) => type === 'pointerdown')
      .length;

    expect(pointerdownAddCalls).toBeGreaterThan(0);

    unmount();

    const pointerdownRemoveCallsAfterUnmount = removeEventListenerSpy.mock.calls
      .filter(([type]) => type === 'pointerdown')
      .length;

    expect(pointerdownRemoveCallsAfterUnmount).toBeGreaterThan(pointerdownRemoveCallsBeforeUnmount);
  });
});
