import { useEffect, useRef, useState, type RefCallback } from 'react';

type ElementSize = {
  width: number;
  height: number;
};

type ElementSizeRef<T extends HTMLElement> = RefCallback<T> & {
  current: T | null;
};

const DEFAULT_SIZE: ElementSize = { width: 0, height: 0 };

export const useElementSize = <T extends HTMLElement>() => {
  const [node, setNode] = useState<T | null>(null);
  const [size, setSize] = useState<ElementSize>(DEFAULT_SIZE);
  const nextSizeRef = useRef<ElementSize>(DEFAULT_SIZE);
  const [ref] = useState<ElementSizeRef<T>>(() => {
    const handleNode = ((nextNode: T | null) => {
      handleNode.current = nextNode;
      setNode(nextNode);

      const nextSize = nextNode
        ? { width: nextNode.clientWidth, height: nextNode.clientHeight }
        : DEFAULT_SIZE;
      nextSizeRef.current = nextSize;
      setSize((current) => (
        current.width === nextSize.width && current.height === nextSize.height
          ? current
          : nextSize
      ));
    }) as ElementSizeRef<T>;

    handleNode.current = null;
    return handleNode;
  });

  useEffect(() => {
    if (!node) {
      return undefined;
    }

    let pendingFrame: number | null = null;

    const update = (width: number, height: number) => {
      if (width > 0 && height >= 0) {
        if (nextSizeRef.current.width === width && nextSizeRef.current.height === height) {
          return;
        }

        nextSizeRef.current = { width, height };
        if (pendingFrame !== null) {
          window.cancelAnimationFrame(pendingFrame);
        }

        pendingFrame = window.requestAnimationFrame(() => {
          pendingFrame = null;
          setSize(nextSizeRef.current);
        });
      }
    };

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }
      update(entry.contentRect.width, entry.contentRect.height);
    });

    observer.observe(node);

    return () => {
      if (pendingFrame !== null) {
        window.cancelAnimationFrame(pendingFrame);
      }
      observer.disconnect();
    };
  }, [node]);

  return { ref, size };
};
