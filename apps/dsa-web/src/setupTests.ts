import './test-utils/axiosTestBootstrap';
import '@testing-library/jest-dom';
import { afterEach } from 'vitest';
import { installAsyncHarness } from './test-utils/asyncHarness';
import { installCanvasHarness } from './test-utils/canvasHarness';
import {
  DEFAULT_TEST_VIEWPORT_HEIGHT,
  DEFAULT_TEST_VIEWPORT_WIDTH,
  installViewportHarness,
  resetTestViewport,
  setTestViewport,
} from './test-utils/viewportHarness';

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

Object.defineProperty(window, 'scrollTo', {
  writable: true,
  value: () => undefined,
});

installViewportHarness();
installCanvasHarness();
installAsyncHarness();

afterEach(() => {
  // Guarantee no cross-test responsive leakage.
  resetTestViewport();
  setTestViewport({
    width: DEFAULT_TEST_VIEWPORT_WIDTH,
    height: DEFAULT_TEST_VIEWPORT_HEIGHT,
    notify: false,
  });
  document.body.style.overflow = '';
});
