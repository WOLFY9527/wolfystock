import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ConsumerEnglishPresentationBoundary } from '../ConsumerEnglishPresentationBoundary';

const { languageState } = vi.hoisted(() => ({
  languageState: { value: 'en' as 'zh' | 'en' },
}));

vi.mock('../../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({ language: languageState.value }),
}));

function renderBoundary(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <ConsumerEnglishPresentationBoundary surface="liquidity-monitor" title="Liquidity Monitor">
        <p>流动性监测 implementation</p>
      </ConsumerEnglishPresentationBoundary>
    </MemoryRouter>,
  );
}

describe('ConsumerEnglishPresentationBoundary', () => {
  beforeEach(() => {
    languageState.value = 'en';
    document.body.innerHTML = '';
  });

  it('fails closed to English-only copy and keeps the complete localized route target', () => {
    renderBoundary('/en/market/liquidity-monitor?view=detail#freshness');

    const boundary = screen.getByTestId('consumer-english-presentation-liquidity-monitor');
    expect(boundary).toHaveTextContent('English presentation');
    expect(boundary).toHaveTextContent('Liquidity Monitor');
    expect(boundary).not.toHaveTextContent('流动性监测 implementation');
    expect(screen.getByRole('link', { name: 'Open this surface in Chinese' })).toHaveAttribute(
      'href',
      '/zh/market/liquidity-monitor?view=detail#freshness',
    );
  });

  it('keeps the Chinese implementation untouched on a Chinese route', () => {
    languageState.value = 'zh';
    renderBoundary('/zh/market/liquidity-monitor');

    expect(screen.getByText('流动性监测 implementation')).toBeVisible();
    expect(screen.queryByTestId('consumer-english-presentation-boundary')).not.toBeInTheDocument();
  });
});
