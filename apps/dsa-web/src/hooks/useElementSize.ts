import { useEffect, useRef, useState } from 'react';

type ElementSize = {
  width: number;
  height: number;
};

const DEFAULT_SIZE: ElementSize = { width: 0, height: 0 };

export const useElementSize = <T extends HTMLElement>() => {
  const ref = useRef<T | null>(null);
  const [size, setSize] = useState<ElementSize>(DEFAULT_SIZE);
  const frameRef = useRef<number | null>(null);
  const nextSizeRef = useRef<ElementSize>(DEFAULT_SIZE);

  useEffect(() => {
    const node = ref.current;
    if (!node) {
      return undefined;
    }

    const update = (width: number, height: number) => {
      if (width > 0 && height >= 0) {
        if (nextSizeRef.current.width === width && nextSizeRef.current.height === height) {
          return;
        }

        nextSizeRef.current = { width, height };
        if (frameRef.current !== null) {
          window.cancelAnimationFrame(frameRef.current);
        }

        frameRef.current = window.requestAnimationFrame(() => {
          frameRef.current = null;
          setSize(nextSizeRef.current);
        });
      }
    };

    update(node.clientWidth, node.clientHeight);

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }
      update(entry.contentRect.width, entry.contentRect.height);
    });

    observer.observe(node);

    return () => {
      const pendingFrame = frameRef.current;
      if (pendingFrame !== null) {
        window.cancelAnimationFrame(pendingFrame);
      }
      observer.disconnect();
    };
  }, []);

  return { ref, size };
};
