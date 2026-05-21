type TooltipPositionSize = {
  contentSize: [number, number];
  viewSize: [number, number];
};

const viewportSize = () => ({
  width: typeof window !== 'undefined'
    ? window.innerWidth || document.documentElement.clientWidth || 0
    : 0,
  height: typeof window !== 'undefined'
    ? window.innerHeight || document.documentElement.clientHeight || 0
    : 0,
});

export const resolveHomeCandlestickTooltipPosition = (
  point: [number, number],
  size: TooltipPositionSize,
  chartRect?: Pick<DOMRect, 'left' | 'top'> | null,
  viewport = viewportSize(),
): [number, number] => {
  const margin = 10;
  const cursorGap = 14;
  const [contentWidth = 180, contentHeight = 96] = size.contentSize;
  const [viewWidth, viewHeight] = size.viewSize;
  const [mouseX, mouseY] = point;

  if (chartRect && viewport.width > 0 && viewport.height > 0) {
    let viewportX = chartRect.left + mouseX + cursorGap;
    if (viewportX + contentWidth + margin > viewport.width) {
      viewportX = chartRect.left + mouseX - contentWidth - cursorGap;
    }
    viewportX = Math.max(margin, Math.min(viewportX, viewport.width - contentWidth - margin));

    let viewportY = chartRect.top + mouseY - contentHeight - cursorGap;
    if (viewportY < margin) {
      viewportY = chartRect.top + mouseY + cursorGap;
    }
    viewportY = Math.max(margin, Math.min(viewportY, viewport.height - contentHeight - margin));

    return [viewportX - chartRect.left, viewportY - chartRect.top];
  }

  let x = mouseX + cursorGap;
  if (x + contentWidth + margin > viewWidth) {
    x = mouseX - contentWidth - cursorGap;
  }
  x = Math.max(margin, Math.min(x, viewWidth - contentWidth - margin));

  let y = mouseY - contentHeight - cursorGap;
  if (y < margin) {
    y = mouseY + cursorGap;
  }
  y = Math.max(margin, Math.min(y, viewHeight - contentHeight - margin));
  return [x, y];
};
