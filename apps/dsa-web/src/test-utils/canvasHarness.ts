/**
 * CanvasRenderingContext2D surface required by zrender / ECharts canvas painter.
 *
 * Implements only methods and gradient objects that real chart paint paths invoke.
 * Does not no-op ECharts itself and does not swallow paint exceptions.
 */

type GradientStop = {
  offset: number;
  color: string;
};

export type CanvasGradientMock = {
  addColorStop: (offset: number, color: string) => void;
  __stops: GradientStop[];
};

export type CanvasPatternMock = {
  image: CanvasImageSource | null;
  repetition: string;
};

export type CanvasContextMock = CanvasRenderingContext2D & {
  __isHarnessCanvasContext: true;
};

function createGradientMock(): CanvasGradientMock {
  const stops: GradientStop[] = [];
  return {
    __stops: stops,
    addColorStop(offset: number, color: string) {
      stops.push({ offset, color });
    },
  };
}

function createPatternMock(
  image: CanvasImageSource | null,
  repetition: string,
): CanvasPatternMock {
  return { image, repetition };
}

export function createCanvasRenderingContext2DMock(
  canvas?: HTMLCanvasElement,
): CanvasContextMock {
  const gradient = () => createGradientMock() as unknown as CanvasGradient;

  const context: Partial<CanvasRenderingContext2D> & {
    __isHarnessCanvasContext: true;
    canvas: HTMLCanvasElement;
  } = {
    __isHarnessCanvasContext: true,
    canvas: canvas ?? ({} as HTMLCanvasElement),

    // State properties zrender mutates directly.
    fillStyle: '#000',
    strokeStyle: '#000',
    globalAlpha: 1,
    globalCompositeOperation: 'source-over',
    lineWidth: 1,
    lineCap: 'butt',
    lineJoin: 'miter',
    miterLimit: 10,
    lineDashOffset: 0,
    font: '10px sans-serif',
    textAlign: 'start',
    textBaseline: 'alphabetic',
    direction: 'inherit',
    shadowBlur: 0,
    shadowColor: 'rgba(0, 0, 0, 0)',
    shadowOffsetX: 0,
    shadowOffsetY: 0,
    imageSmoothingEnabled: true,
    imageSmoothingQuality: 'low',

    // Methods required by zrender canvas painter / graphic paths.
    fillRect: () => undefined,
    clearRect: () => undefined,
    strokeRect: () => undefined,
    getImageData: () => ({
      data: new Uint8ClampedArray(4),
      width: 1,
      height: 1,
      colorSpace: 'srgb',
    }) as ImageData,
    putImageData: () => undefined,
    createImageData: ((width: number, height?: number) => ({
      data: new Uint8ClampedArray(Math.max(1, width) * Math.max(1, height ?? width) * 4),
      width: Math.max(1, width),
      height: Math.max(1, height ?? width),
      colorSpace: 'srgb',
    })) as CanvasRenderingContext2D['createImageData'],
    // zrender canvas painter calls setTransform(a,b,c,d,e,f) with six numbers.
    // It never reads ctx.getTransform(). Pattern transforms use `new DOMMatrix()`
    // only when the global constructor exists (absent in jsdom), so a partial
    // DOMMatrix mock is unused surface and was an dishonest type claim.
    setTransform: () => undefined,
    resetTransform: () => undefined,
    drawImage: () => undefined,
    save: () => undefined,
    restore: () => undefined,
    beginPath: () => undefined,
    moveTo: () => undefined,
    lineTo: () => undefined,
    closePath: () => undefined,
    stroke: () => undefined,
    fill: () => undefined,
    clip: () => undefined,
    translate: () => undefined,
    scale: () => undefined,
    rotate: () => undefined,
    transform: () => undefined,
    arc: () => undefined,
    arcTo: () => undefined,
    ellipse: () => undefined,
    rect: () => undefined,
    quadraticCurveTo: () => undefined,
    bezierCurveTo: () => undefined,
    fillText: () => undefined,
    strokeText: () => undefined,
    measureText: () => ({
      width: 0,
      actualBoundingBoxAscent: 0,
      actualBoundingBoxDescent: 0,
      actualBoundingBoxLeft: 0,
      actualBoundingBoxRight: 0,
      fontBoundingBoxAscent: 0,
      fontBoundingBoxDescent: 0,
      alphabeticBaseline: 0,
      emHeightAscent: 0,
      emHeightDescent: 0,
      hangingBaseline: 0,
      ideographicBaseline: 0,
    }) as TextMetrics,
    setLineDash: () => undefined,
    getLineDash: () => [],
    createLinearGradient: () => gradient(),
    createRadialGradient: () => gradient(),
    createConicGradient: () => gradient(),
    createPattern: ((image: CanvasImageSource | null, repetition: string | null) => (
      createPatternMock(image, repetition ?? 'repeat') as unknown as CanvasPattern
    )) as CanvasRenderingContext2D['createPattern'],
    isPointInPath: () => false,
    isPointInStroke: () => false,
    drawFocusIfNeeded: () => undefined,
  };

  return context as CanvasContextMock;
}

let installed = false;
let originalGetContext: HTMLCanvasElement['getContext'] | undefined;

export function installCanvasHarness(): void {
  if (installed || typeof HTMLCanvasElement === 'undefined') {
    return;
  }

  originalGetContext = HTMLCanvasElement.prototype.getContext;

  Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
    configurable: true,
    writable: true,
    value: function getContext(
      this: HTMLCanvasElement,
      contextId: string,
      _options?: unknown,
    ) {
      if (contextId === '2d') {
        return createCanvasRenderingContext2DMock(this);
      }
      if (typeof originalGetContext === 'function') {
        return originalGetContext.call(this, contextId as '2d', _options as CanvasRenderingContext2DSettings);
      }
      return null;
    },
  });

  installed = true;
}

export function uninstallCanvasHarness(): void {
  if (!installed || typeof HTMLCanvasElement === 'undefined') {
    return;
  }

  if (originalGetContext) {
    Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
      configurable: true,
      writable: true,
      value: originalGetContext,
    });
  }

  installed = false;
}
