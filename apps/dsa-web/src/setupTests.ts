import '@testing-library/jest-dom';

class IntersectionObserverMock implements IntersectionObserver {
  readonly root = null;
  readonly rootMargin = '';
  readonly thresholds = [0];

  disconnect() {}

  observe() {}

  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }

  unobserve() {}
}

Object.defineProperty(globalThis, 'IntersectionObserver', {
  writable: true,
  value: IntersectionObserverMock,
});

const TEST_LAYOUT_WIDTH = 1024;
const TEST_LAYOUT_HEIGHT = 320;

function testLayoutDimension(element: HTMLElement, dimension: 'width' | 'height'): number {
  const attributeValue = element.getAttribute(`data-test-${dimension}`);
  const attributeDimension = attributeValue ? Number(attributeValue) : Number.NaN;
  if (Number.isFinite(attributeDimension) && attributeDimension > 0) {
    return attributeDimension;
  }

  const inlineValue = element.style[dimension];
  if (inlineValue.endsWith('px')) {
    const inlineDimension = Number.parseFloat(inlineValue);
    if (Number.isFinite(inlineDimension) && inlineDimension > 0) {
      return inlineDimension;
    }
  }

  return dimension === 'width' ? TEST_LAYOUT_WIDTH : TEST_LAYOUT_HEIGHT;
}

Object.defineProperties(HTMLElement.prototype, {
  clientWidth: {
    configurable: true,
    get() {
      return testLayoutDimension(this as HTMLElement, 'width');
    },
  },
  clientHeight: {
    configurable: true,
    get() {
      return testLayoutDimension(this as HTMLElement, 'height');
    },
  },
});

class ResizeObserverMock implements ResizeObserver {
  readonly callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }

  disconnect() {}

  observe(target: Element) {
    const width = target instanceof HTMLElement
      ? target.clientWidth
      : TEST_LAYOUT_WIDTH;
    const height = target instanceof HTMLElement
      ? target.clientHeight
      : TEST_LAYOUT_HEIGHT;
    const contentRect = {
      x: 0,
      y: 0,
      top: 0,
      right: width,
      bottom: height,
      left: 0,
      width,
      height,
      toJSON: () => ({ width, height }),
    } as DOMRectReadOnly;

    this.callback([{
      target,
      contentRect,
      borderBoxSize: [],
      contentBoxSize: [],
      devicePixelContentBoxSize: [],
    } as unknown as ResizeObserverEntry], this);
  }

  unobserve() {}
}

Object.defineProperty(globalThis, 'ResizeObserver', {
  writable: true,
  value: ResizeObserverMock,
});

Object.defineProperty(window, 'scrollTo', {
  writable: true,
  value: () => undefined,
});

if (typeof HTMLCanvasElement !== 'undefined') {
  Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
    writable: true,
    value: () => ({
      fillRect: () => undefined,
      clearRect: () => undefined,
      getImageData: () => ({ data: [] }),
      putImageData: () => undefined,
      createImageData: () => [],
      setTransform: () => undefined,
      drawImage: () => undefined,
      save: () => undefined,
      fillText: () => undefined,
      restore: () => undefined,
      beginPath: () => undefined,
      moveTo: () => undefined,
      lineTo: () => undefined,
      closePath: () => undefined,
      stroke: () => undefined,
      translate: () => undefined,
      scale: () => undefined,
      rotate: () => undefined,
      arc: () => undefined,
      fill: () => undefined,
      measureText: () => ({ width: 0 }),
      transform: () => undefined,
      rect: () => undefined,
      clip: () => undefined,
    }),
  });
}
