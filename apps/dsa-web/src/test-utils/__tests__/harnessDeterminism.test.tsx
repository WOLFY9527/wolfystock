import { act, render, screen, waitFor } from '@testing-library/react';
import { useEffect, useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { flushTestEffects } from '../asyncHarness';
import { createCanvasRenderingContext2DMock } from '../canvasHarness';
import {
  DEFAULT_TEST_VIEWPORT_HEIGHT,
  DEFAULT_TEST_VIEWPORT_WIDTH,
  getTestViewport,
  resetTestViewport,
  setTestViewport,
} from '../viewportHarness';

describe('frontend shared test harness determinism', () => {
  afterEach(() => {
    resetTestViewport();
    setTestViewport({
      width: DEFAULT_TEST_VIEWPORT_WIDTH,
      height: DEFAULT_TEST_VIEWPORT_HEIGHT,
      notify: false,
    });
  });

  it('keeps innerWidth and min-width media queries in agreement across desktop/mobile/desktop', () => {
    const desktopQuery = window.matchMedia('(min-width: 1024px)');
    const mobileQuery = window.matchMedia('(max-width: 767px)');

    expect(window.innerWidth).toBe(DEFAULT_TEST_VIEWPORT_WIDTH);
    expect(desktopQuery.matches).toBe(true);
    expect(mobileQuery.matches).toBe(false);

    setTestViewport({ width: 390, height: 844 });
    expect(window.innerWidth).toBe(390);
    expect(window.innerHeight).toBe(844);
    expect(desktopQuery.matches).toBe(false);
    expect(mobileQuery.matches).toBe(true);

    setTestViewport({ width: DEFAULT_TEST_VIEWPORT_WIDTH, height: DEFAULT_TEST_VIEWPORT_HEIGHT });
    expect(window.innerWidth).toBe(DEFAULT_TEST_VIEWPORT_WIDTH);
    expect(desktopQuery.matches).toBe(true);
    expect(mobileQuery.matches).toBe(false);
  });

  it('notifies matchMedia change listeners with realistic matches on viewport transitions', () => {
    const query = window.matchMedia('(min-width: 1024px)');
    const listener = vi.fn();
    query.addEventListener('change', listener);

    setTestViewport({ width: 390 });
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener.mock.calls[0]?.[0]).toMatchObject({
      type: 'change',
      matches: false,
      media: '(min-width: 1024px)',
    });

    setTestViewport({ width: 1280 });
    expect(listener).toHaveBeenCalledTimes(2);
    expect(listener.mock.calls[1]?.[0]).toMatchObject({
      matches: true,
    });
  });

  it('propagates viewport width into default clientWidth so compact chart layout can react', () => {
    setTestViewport({ width: 390, height: 844 });
    const node = document.createElement('div');
    document.body.appendChild(node);

    expect(node.clientWidth).toBe(390);
    expect(node.clientHeight).toBeGreaterThan(0);

    node.setAttribute('data-test-width', '640');
    expect(node.clientWidth).toBe(640);

    node.remove();
  });

  it('re-notifies ResizeObserver targets when the viewport changes', async () => {
    const observed: Array<{ width: number; height: number }> = [];
    const node = document.createElement('div');
    document.body.appendChild(node);

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }
      observed.push({
        width: entry.contentRect.width,
        height: entry.contentRect.height,
      });
    });

    observer.observe(node);
    expect(observed[0]?.width).toBe(DEFAULT_TEST_VIEWPORT_WIDTH);

    setTestViewport({ width: 390, height: 844 });
    expect(observed.at(-1)?.width).toBe(390);

    setTestViewport({ width: 1280 });
    expect(observed.at(-1)?.width).toBe(1280);

    observer.disconnect();
    node.remove();
  });

  it('resets viewport state after tests to prevent cross-test leakage', () => {
    setTestViewport({ width: 390, height: 844 });
    expect(getTestViewport().width).toBe(390);

    resetTestViewport();
    setTestViewport({
      width: DEFAULT_TEST_VIEWPORT_WIDTH,
      height: DEFAULT_TEST_VIEWPORT_HEIGHT,
      notify: false,
    });

    expect(window.innerWidth).toBe(DEFAULT_TEST_VIEWPORT_WIDTH);
    expect(window.matchMedia('(min-width: 1024px)').matches).toBe(true);
  });

  it('implements createLinearGradient with addColorStop for zrender paint paths', () => {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    expect(ctx).not.toBeNull();
    if (!ctx) {
      return;
    }

    expect(typeof ctx.createLinearGradient).toBe('function');
    expect(typeof ctx.createRadialGradient).toBe('function');
    expect(typeof ctx.setLineDash).toBe('function');

    const linear = ctx.createLinearGradient(0, 0, 100, 0);
    expect(typeof linear.addColorStop).toBe('function');
    linear.addColorStop(0, 'rgba(0,0,0,0)');
    linear.addColorStop(1, 'rgba(0,0,0,1)');

    const radial = ctx.createRadialGradient(0, 0, 0, 0, 0, 10);
    radial.addColorStop(0.5, '#fff');

    // Direct factory remains usable for unit-level assertions.
    const direct = createCanvasRenderingContext2DMock(canvas);
    expect(direct.__isHarnessCanvasContext).toBe(true);
    expect(typeof direct.createLinearGradient(0, 0, 1, 1).addColorStop).toBe('function');
  });

  it('flushes owned async work without arbitrary sleeps', async () => {
    let ticks = 0;
    window.setTimeout(() => {
      ticks += 1;
    }, 0);
    window.requestAnimationFrame(() => {
      ticks += 1;
    });

    await flushTestEffects(2);
    expect(ticks).toBe(2);
  });

  it('allows waitFor ownership of timer-driven React updates without harness interference', async () => {
    function Probe() {
      const [value, setValue] = useState('idle');
      useEffect(() => {
        const timer = window.setTimeout(() => setValue('ready'), 0);
        return () => window.clearTimeout(timer);
      }, []);
      return <div data-testid="probe">{value}</div>;
    }

    render(<Probe />);
    await waitFor(() => {
      expect(screen.getByTestId('probe')).toHaveTextContent('ready');
    });
  });

  it('supports desktop -> mobile -> desktop transitions with resize listeners', async () => {
    function ViewportProbe() {
      const [width, setWidth] = useState(window.innerWidth);
      useEffect(() => {
        const onResize = () => setWidth(window.innerWidth);
        window.addEventListener('resize', onResize);
        return () => window.removeEventListener('resize', onResize);
      }, []);
      return <div data-testid="viewport-probe">{width}</div>;
    }

    render(<ViewportProbe />);
    expect(screen.getByTestId('viewport-probe')).toHaveTextContent(String(DEFAULT_TEST_VIEWPORT_WIDTH));

    await act(async () => {
      setTestViewport({ width: 390, height: 844 });
    });
    expect(screen.getByTestId('viewport-probe')).toHaveTextContent('390');

    await act(async () => {
      setTestViewport({ width: 1280, height: 800 });
    });
    expect(screen.getByTestId('viewport-probe')).toHaveTextContent('1280');
  });
});
