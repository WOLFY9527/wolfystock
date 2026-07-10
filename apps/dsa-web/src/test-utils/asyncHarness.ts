/**
 * Async React test lifecycle helpers.
 *
 * Goals:
 * - Provide explicit flush helpers for chart lazyUpdate / rAF paint settlement
 *   without arbitrary multi-second sleeps.
 * - Keep requestAnimationFrame deterministic in jsdom (mapped to a zero-delay
 *   timer) so layout hooks such as useElementSize can settle promptly.
 *
 * Intentionally does NOT wrap every setTimeout/setInterval in act():
 * Testing Library's waitFor polls via timers, and blanket act-wrapping breaks
 * that ownership model and can fail real assertions.
 *
 * Does not suppress console warnings or filter console.error.
 */

import { act } from '@testing-library/react';

type InstalledTimers = {
  setTimeout: typeof setTimeout;
  clearTimeout: typeof clearTimeout;
  requestAnimationFrame: typeof requestAnimationFrame;
  cancelAnimationFrame: typeof cancelAnimationFrame;
};

let installed = false;
let originals: InstalledTimers | null = null;

export function installAsyncHarness(): void {
  if (installed || typeof window === 'undefined') {
    return;
  }

  originals = {
    setTimeout: globalThis.setTimeout.bind(globalThis),
    clearTimeout: globalThis.clearTimeout.bind(globalThis),
    requestAnimationFrame: window.requestAnimationFrame.bind(window),
    cancelAnimationFrame: window.cancelAnimationFrame.bind(window),
  };

  const nativeSetTimeout = originals.setTimeout;
  const nativeClearTimeout = originals.clearTimeout;

  // Deterministic rAF: schedule on the next macrotask without inventing sleeps.
  window.requestAnimationFrame = ((callback: FrameRequestCallback) => (
    nativeSetTimeout(() => {
      callback(performance.now());
    }, 0) as unknown as number
  )) as typeof requestAnimationFrame;

  window.cancelAnimationFrame = ((handle: number) => {
    nativeClearTimeout(handle as unknown as ReturnType<typeof setTimeout>);
  }) as typeof cancelAnimationFrame;

  installed = true;
}

export function uninstallAsyncHarness(): void {
  if (!installed || !originals) {
    return;
  }

  window.requestAnimationFrame = originals.requestAnimationFrame;
  window.cancelAnimationFrame = originals.cancelAnimationFrame;
  originals = null;
  installed = false;
}

/**
 * Drain microtasks and one macrotask turn so chart lazyUpdate / rAF paint settle.
 * Uses real zero-delay timers (no arbitrary multi-second sleeps).
 */
export async function flushTestEffects(turns = 1): Promise<void> {
  const iterations = Math.max(1, turns);
  const nativeSetTimeout = originals?.setTimeout ?? globalThis.setTimeout.bind(globalThis);

  for (let index = 0; index < iterations; index += 1) {
    await act(async () => {
      await Promise.resolve();
      await new Promise<void>((resolve) => {
        nativeSetTimeout(() => resolve(), 0);
      });
    });
  }
}

/**
 * Flush pending animation frames that the harness maps onto zero-delay timers.
 */
export async function flushAnimationFrames(frames = 1): Promise<void> {
  await flushTestEffects(frames);
}

/**
 * Run a viewport or observer mutation inside React's act boundary.
 * Prefer this over raw window.innerWidth mutation when a mounted tree listens.
 */
export async function actTestUpdate(work: () => void | Promise<void>): Promise<void> {
  await act(async () => {
    await work();
  });
}
