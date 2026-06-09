import { expect, type Locator } from '@playwright/test';
import { findConsumerRawLeakage, type ConsumerRawLeakageGuardOptions } from '../../src/test-utils/consumerRawLeakageGuard';

export async function collectVisibleConsumerCopy(root: Locator) {
  return root.evaluate((element) => {
    const isVisible = (current: Element) => {
      const htmlElement = current as HTMLElement;
      if (htmlElement.hidden || current.getAttribute('aria-hidden') === 'true') {
        return false;
      }

      const style = window.getComputedStyle(htmlElement);
      if (style.display === 'none' || style.visibility === 'hidden') {
        return false;
      }

      const rect = htmlElement.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    };

    const texts = new Set<string>();
    const nodes = [element, ...Array.from(element.querySelectorAll('*'))];

    for (const current of nodes) {
      if (!isVisible(current)) {
        continue;
      }

      const htmlElement = current as HTMLElement;
      const visibleText = htmlElement.innerText?.trim();
      if (visibleText) {
        texts.add(visibleText);
      }

      for (const attribute of ['aria-label', 'title', 'alt', 'placeholder']) {
        const value = current.getAttribute(attribute)?.trim();
        if (value) {
          texts.add(value);
        }
      }
    }

    return Array.from(texts).join('\n');
  });
}

export async function expectNoConsumerRawLeakage(
  root: Locator,
  options: ConsumerRawLeakageGuardOptions & { label?: string } = {},
) {
  const combinedText = await collectVisibleConsumerCopy(root);
  const hits = findConsumerRawLeakage(combinedText, options);

  expect(
    hits.map((hit) => `${hit.pattern} :: ${hit.match} :: ${hit.context}`),
    `${options.label ?? 'consumer surface'} leaked raw/internal vocabulary`,
  ).toEqual([]);
}
