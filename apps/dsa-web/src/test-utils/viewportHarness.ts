/**
 * Deterministic viewport / matchMedia / ResizeObserver harness for jsdom.
 *
 * Contract:
 * - window.innerWidth/innerHeight and media-query matches stay in agreement
 * - layout defaults (clientWidth/clientHeight) track the active viewport
 * - media-query listeners receive realistic change events
 * - ResizeObserver observers are re-notified on viewport transitions
 * - every test starts and ends at the desktop default viewport
 */

export const DEFAULT_TEST_VIEWPORT_WIDTH = 1024;
export const DEFAULT_TEST_VIEWPORT_HEIGHT = 768;
export const DEFAULT_TEST_LAYOUT_HEIGHT = 320;

type MediaQueryListener = (event: MediaQueryListEvent) => void;

type HarnessMediaQueryList = MediaQueryList & {
  __harnessQuery: string;
  __harnessMatches: boolean;
  __harnessListeners: Set<MediaQueryListener>;
};

type TrackedResizeObserver = {
  callback: ResizeObserverCallback;
  targets: Set<Element>;
};

type ViewportState = {
  width: number;
  height: number;
};

const mediaQueryLists = new Set<HarnessMediaQueryList>();
const resizeObservers = new Set<TrackedResizeObserver>();

let viewport: ViewportState = {
  width: DEFAULT_TEST_VIEWPORT_WIDTH,
  height: DEFAULT_TEST_VIEWPORT_HEIGHT,
};

let installed = false;
let originalMatchMedia: typeof window.matchMedia | undefined;
let originalInnerWidthDescriptor: PropertyDescriptor | undefined;
let originalInnerHeightDescriptor: PropertyDescriptor | undefined;
let originalClientWidthDescriptor: PropertyDescriptor | undefined;
let originalClientHeightDescriptor: PropertyDescriptor | undefined;
let originalResizeObserver: typeof ResizeObserver | undefined;
let resizeBridgeInstalled = false;
let suppressResizeBridge = false;

function asPositiveNumber(value: unknown, fallback: number): number {
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return fallback;
  }
  return numeric;
}

function parsePx(value: string | null | undefined): number {
  if (!value) {
    return Number.NaN;
  }
  if (value.endsWith('px')) {
    return Number.parseFloat(value);
  }
  return Number(value);
}

function readExplicitLayoutDimension(element: HTMLElement, dimension: 'width' | 'height'): number {
  const attributeValue = element.getAttribute(`data-test-${dimension}`);
  const attributeDimension = parsePx(attributeValue);
  if (Number.isFinite(attributeDimension) && attributeDimension > 0) {
    return attributeDimension;
  }

  const inlineValue = element.style[dimension];
  const inlineDimension = parsePx(inlineValue);
  if (Number.isFinite(inlineDimension) && inlineDimension > 0) {
    return inlineDimension;
  }

  return Number.NaN;
}

export function getTestViewport(): Readonly<ViewportState> {
  return { width: viewport.width, height: viewport.height };
}

export function resolveTestLayoutDimension(
  element: HTMLElement,
  dimension: 'width' | 'height',
): number {
  const explicit = readExplicitLayoutDimension(element, dimension);
  if (Number.isFinite(explicit) && explicit > 0) {
    return explicit;
  }

  if (dimension === 'width') {
    return viewport.width;
  }

  // Charts and panels expect a stable non-zero height even when the viewport is tall.
  return DEFAULT_TEST_LAYOUT_HEIGHT;
}

function evaluateMediaQuery(query: string, width: number): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return false;
  }

  if (normalized.includes('prefers-color-scheme: dark')) {
    return false;
  }
  if (normalized.includes('prefers-color-scheme: light')) {
    return true;
  }
  if (normalized.includes('prefers-reduced-motion')) {
    return false;
  }

  const minWidth = normalized.match(/\(min-width:\s*([0-9.]+)px\)/);
  if (minWidth) {
    return width >= Number(minWidth[1]);
  }

  const maxWidth = normalized.match(/\(max-width:\s*([0-9.]+)px\)/);
  if (maxWidth) {
    return width <= Number(maxWidth[1]);
  }

  // Unknown queries stay false so tests that only care about width remain stable.
  return false;
}

function createMediaQueryList(query: string): HarnessMediaQueryList {
  const listeners = new Set<MediaQueryListener>();
  const mql = {
    __harnessQuery: query,
    __harnessMatches: evaluateMediaQuery(query, viewport.width),
    __harnessListeners: listeners,
    get matches() {
      return evaluateMediaQuery(query, viewport.width);
    },
    get media() {
      return query;
    },
    onchange: null as MediaQueryList['onchange'],
    addListener(listener: MediaQueryListener) {
      listeners.add(listener);
    },
    removeListener(listener: MediaQueryListener) {
      listeners.delete(listener);
    },
    addEventListener(type: string, listener: EventListenerOrEventListenerObject) {
      if (type !== 'change') {
        return;
      }
      if (typeof listener === 'function') {
        listeners.add(listener as MediaQueryListener);
      }
    },
    removeEventListener(type: string, listener: EventListenerOrEventListenerObject) {
      if (type !== 'change') {
        return;
      }
      if (typeof listener === 'function') {
        listeners.delete(listener as MediaQueryListener);
      }
    },
    dispatchEvent(event: Event): boolean {
      if (event.type !== 'change') {
        return false;
      }
      const changeEvent = event as MediaQueryListEvent;
      listeners.forEach((listener) => listener(changeEvent));
      if (typeof mql.onchange === 'function') {
        mql.onchange.call(mql, changeEvent);
      }
      return true;
    },
  } as HarnessMediaQueryList;

  mediaQueryLists.add(mql);
  return mql;
}

function notifyMediaQueryLists(): void {
  mediaQueryLists.forEach((mql) => {
    const nextMatches = evaluateMediaQuery(mql.__harnessQuery, viewport.width);
    const previousMatches = mql.__harnessMatches;
    mql.__harnessMatches = nextMatches;
    if (previousMatches === nextMatches) {
      return;
    }

    const event = {
      type: 'change',
      matches: nextMatches,
      media: mql.__harnessQuery,
      bubbles: false,
      cancelable: false,
    } as MediaQueryListEvent;

    mql.__harnessListeners.forEach((listener) => listener(event));
    if (typeof mql.onchange === 'function') {
      mql.onchange.call(mql, event);
    }
  });
}

function buildResizeObserverEntry(target: Element): ResizeObserverEntry {
  const width = target instanceof HTMLElement
    ? resolveTestLayoutDimension(target, 'width')
    : viewport.width;
  const height = target instanceof HTMLElement
    ? resolveTestLayoutDimension(target, 'height')
    : DEFAULT_TEST_LAYOUT_HEIGHT;

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

  return {
    target,
    contentRect,
    borderBoxSize: [{ inlineSize: width, blockSize: height }],
    contentBoxSize: [{ inlineSize: width, blockSize: height }],
    devicePixelContentBoxSize: [{ inlineSize: width, blockSize: height }],
  } as unknown as ResizeObserverEntry;
}

function notifyResizeObservers(): void {
  resizeObservers.forEach((observer) => {
    if (!observer.targets.size) {
      return;
    }
    const entries = Array.from(observer.targets).map((target) => buildResizeObserverEntry(target));
    observer.callback(entries, observer as unknown as ResizeObserver);
  });
}

class HarnessResizeObserver implements ResizeObserver {
  private readonly tracked: TrackedResizeObserver;

  constructor(callback: ResizeObserverCallback) {
    this.tracked = {
      callback,
      targets: new Set<Element>(),
    };
    resizeObservers.add(this.tracked);
  }

  observe(target: Element): void {
    this.tracked.targets.add(target);
    this.tracked.callback([buildResizeObserverEntry(target)], this);
  }

  unobserve(target: Element): void {
    this.tracked.targets.delete(target);
  }

  disconnect(): void {
    this.tracked.targets.clear();
    resizeObservers.delete(this.tracked);
  }
}

function assignViewport(width: number, height: number): void {
  viewport = {
    width: asPositiveNumber(width, DEFAULT_TEST_VIEWPORT_WIDTH),
    height: asPositiveNumber(height, DEFAULT_TEST_VIEWPORT_HEIGHT),
  };
}

export type SetTestViewportOptions = {
  width: number;
  height?: number;
  /** When false, only mutates viewport values without notifying listeners. Default true. */
  notify?: boolean;
  /** When false, skips window resize event. Default true when notify is true. */
  dispatchResize?: boolean;
};

export function setTestViewport(options: SetTestViewportOptions): void {
  const nextWidth = asPositiveNumber(options.width, DEFAULT_TEST_VIEWPORT_WIDTH);
  const nextHeight = asPositiveNumber(options.height ?? viewport.height, DEFAULT_TEST_VIEWPORT_HEIGHT);
  const widthChanged = nextWidth !== viewport.width;
  const heightChanged = nextHeight !== viewport.height;

  assignViewport(nextWidth, nextHeight);

  if (options.notify === false) {
    return;
  }

  if (widthChanged) {
    notifyMediaQueryLists();
  }

  if (widthChanged || heightChanged) {
    notifyResizeObservers();
  }

  if (options.dispatchResize !== false) {
    suppressResizeBridge = true;
    try {
      window.dispatchEvent(new Event('resize'));
    } finally {
      suppressResizeBridge = false;
    }
  }
}

export function resetTestViewport(): void {
  mediaQueryLists.clear();
  resizeObservers.clear();
  assignViewport(DEFAULT_TEST_VIEWPORT_WIDTH, DEFAULT_TEST_VIEWPORT_HEIGHT);
  notifyMediaQueryLists();
  // Do not re-notify observers after clear; a fresh test tree will re-observe.
}

function installResizeBridge(): void {
  if (resizeBridgeInstalled) {
    return;
  }
  resizeBridgeInstalled = true;
  window.addEventListener('resize', () => {
    if (suppressResizeBridge) {
      return;
    }
    // Tests that only assign innerWidth and dispatch resize still need
    // matchMedia + ResizeObserver propagation for deterministic layout.
    notifyMediaQueryLists();
    notifyResizeObservers();
  });
}

export function installViewportHarness(): void {
  if (installed || typeof window === 'undefined') {
    return;
  }

  originalMatchMedia = window.matchMedia?.bind(window);
  originalInnerWidthDescriptor = Object.getOwnPropertyDescriptor(window, 'innerWidth');
  originalInnerHeightDescriptor = Object.getOwnPropertyDescriptor(window, 'innerHeight');
  originalClientWidthDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'clientWidth');
  originalClientHeightDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'clientHeight');
  originalResizeObserver = globalThis.ResizeObserver;

  assignViewport(DEFAULT_TEST_VIEWPORT_WIDTH, DEFAULT_TEST_VIEWPORT_HEIGHT);

  Object.defineProperty(window, 'innerWidth', {
    configurable: true,
    enumerable: true,
    get: () => viewport.width,
    set: (value: unknown) => {
      assignViewport(asPositiveNumber(value, viewport.width), viewport.height);
    },
  });

  Object.defineProperty(window, 'innerHeight', {
    configurable: true,
    enumerable: true,
    get: () => viewport.height,
    set: (value: unknown) => {
      assignViewport(viewport.width, asPositiveNumber(value, viewport.height));
    },
  });

  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: (query: string) => createMediaQueryList(query),
  });

  Object.defineProperties(HTMLElement.prototype, {
    clientWidth: {
      configurable: true,
      get() {
        return resolveTestLayoutDimension(this as HTMLElement, 'width');
      },
    },
    clientHeight: {
      configurable: true,
      get() {
        return resolveTestLayoutDimension(this as HTMLElement, 'height');
      },
    },
  });

  Object.defineProperty(globalThis, 'ResizeObserver', {
    configurable: true,
    writable: true,
    value: HarnessResizeObserver,
  });

  installResizeBridge();
  installed = true;
}

export function uninstallViewportHarness(): void {
  if (!installed) {
    return;
  }

  if (originalMatchMedia) {
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: originalMatchMedia,
    });
  }

  if (originalInnerWidthDescriptor) {
    Object.defineProperty(window, 'innerWidth', originalInnerWidthDescriptor);
  }
  if (originalInnerHeightDescriptor) {
    Object.defineProperty(window, 'innerHeight', originalInnerHeightDescriptor);
  }
  if (originalClientWidthDescriptor) {
    Object.defineProperty(HTMLElement.prototype, 'clientWidth', originalClientWidthDescriptor);
  }
  if (originalClientHeightDescriptor) {
    Object.defineProperty(HTMLElement.prototype, 'clientHeight', originalClientHeightDescriptor);
  }
  if (originalResizeObserver) {
    Object.defineProperty(globalThis, 'ResizeObserver', {
      configurable: true,
      writable: true,
      value: originalResizeObserver,
    });
  }

  mediaQueryLists.clear();
  resizeObservers.clear();
  installed = false;
}
