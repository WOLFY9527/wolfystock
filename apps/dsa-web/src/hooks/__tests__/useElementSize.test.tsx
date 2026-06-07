import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useElementSize } from '../useElementSize';

type ResizeObserverEntryLike = Pick<ResizeObserverEntry, 'contentRect'>;

class TestResizeObserver implements ResizeObserver {
  static instances: TestResizeObserver[] = [];

  readonly observe = vi.fn();
  readonly unobserve = vi.fn();
  readonly disconnect = vi.fn();

  constructor(readonly callback: ResizeObserverCallback) {
    TestResizeObserver.instances.push(this);
  }
}

const defineElementSize = (node: HTMLElement, width: number, height: number) => {
  Object.defineProperties(node, {
    clientWidth: { configurable: true, value: width },
    clientHeight: { configurable: true, value: height },
  });
};

const resizeEntry = (width: number, height: number): ResizeObserverEntryLike => ({
  contentRect: {
    width,
    height,
  } as DOMRectReadOnly,
});

describe('useElementSize', () => {
  const originalResizeObserver = globalThis.ResizeObserver;
  const originalRequestAnimationFrame = window.requestAnimationFrame;
  const originalCancelAnimationFrame = window.cancelAnimationFrame;

  beforeEach(() => {
    TestResizeObserver.instances = [];
    globalThis.ResizeObserver = TestResizeObserver;
    window.requestAnimationFrame = ((callback: FrameRequestCallback) => {
      callback(performance.now());
      return 1;
    }) as typeof window.requestAnimationFrame;
    window.cancelAnimationFrame = vi.fn() as typeof window.cancelAnimationFrame;
  });

  afterEach(() => {
    globalThis.ResizeObserver = originalResizeObserver;
    window.requestAnimationFrame = originalRequestAnimationFrame;
    window.cancelAnimationFrame = originalCancelAnimationFrame;
  });

  it('returns a stable ref callback and reads the mounted node size', () => {
    const { result } = renderHook(() => useElementSize<HTMLDivElement>());
    const initialRef = result.current.ref;
    const node = document.createElement('div');
    defineElementSize(node, 320, 180);

    expect(result.current.ref.current).toBeNull();

    act(() => {
      result.current.ref(node);
    });

    expect(result.current.ref).toBe(initialRef);
    expect(result.current.ref.current).toBe(node);
    expect(result.current.size).toEqual({ width: 320, height: 180 });
    expect(TestResizeObserver.instances).toHaveLength(1);
    expect(TestResizeObserver.instances[0].observe).toHaveBeenCalledWith(node);
  });

  it('updates size from ResizeObserver entries', () => {
    const { result } = renderHook(() => useElementSize<HTMLDivElement>());
    const node = document.createElement('div');
    defineElementSize(node, 320, 180);

    act(() => {
      result.current.ref(node);
    });
    const observer = TestResizeObserver.instances[0];

    act(() => {
      observer.callback(
        [resizeEntry(480, 240) as ResizeObserverEntry],
        observer,
      );
    });

    expect(result.current.size).toEqual({ width: 480, height: 240 });
  });

  it('resets to the default size and disconnects when the node detaches', () => {
    const { result } = renderHook(() => useElementSize<HTMLDivElement>());
    const node = document.createElement('div');
    defineElementSize(node, 320, 180);

    act(() => {
      result.current.ref(node);
    });
    const observer = TestResizeObserver.instances[0];

    act(() => {
      result.current.ref(null);
    });

    expect(result.current.ref.current).toBeNull();
    expect(result.current.size).toEqual({ width: 0, height: 0 });
    expect(observer.disconnect).toHaveBeenCalledTimes(1);
  });
});
