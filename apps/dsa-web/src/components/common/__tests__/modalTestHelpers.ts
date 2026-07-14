import { act } from '@testing-library/react';
import { vi } from 'vitest';
import { flushAnimationFrames } from '../../../test-utils/asyncHarness';

const CONFIRM_DIALOG_RAF_MS = 16;
const CONFIRM_DIALOG_CLOSE_MS = 180;
const DRAWER_READY_DELAY_MS = 80;
const DRAWER_BACKDROP_GUARD_MS = 420;

export async function settleDrawerOpen(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
  });
  await flushAnimationFrames(2);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(DRAWER_READY_DELAY_MS);
  });
}

export async function settleDrawerInteractionReady(): Promise<void> {
  await settleDrawerOpen();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(DRAWER_BACKDROP_GUARD_MS);
  });
}

export async function settleConfirmDialogOpen(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(CONFIRM_DIALOG_RAF_MS * 2);
  });
}

export async function advanceConfirmDialogClose(ms = CONFIRM_DIALOG_CLOSE_MS): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await vi.advanceTimersByTimeAsync(ms);
  });
}
