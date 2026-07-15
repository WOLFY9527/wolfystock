import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  RoughBulletList,
  RoughSectionCard,
} from '../roughShellShared';

describe('roughShellShared de-cardification path', () => {
  it('keeps RoughSectionCard available for existing pages', () => {
    render(
      <RoughSectionCard eyebrow="队列" title="今日概览" data-testid="legacy-card">
        body
      </RoughSectionCard>,
    );

    const card = screen.getByTestId('legacy-card');
    expect(card).toHaveAttribute('data-rough-variant', 'section-card');
    expect(card).toHaveTextContent('今日概览');
    expect(card).toHaveClass('rounded-[16px]');
  });

  it('defaults bullet list to cards and offers rows migration variant', () => {
    const { rerender } = render(
      <RoughBulletList items={['条目一', '条目二']} emptyText="空" />,
    );

    const cardList = screen.getByText('条目一').closest('ul');
    expect(cardList).toHaveAttribute('data-rough-variant', 'bullet-cards');
    expect(screen.getByText('条目一').closest('li')).toHaveClass('rounded-xl');

    rerender(
      <RoughBulletList items={['行一', '行二']} emptyText="空" variant="rows" />,
    );
    const rowList = screen.getByText('行一').closest('ul');
    expect(rowList).toHaveAttribute('data-rough-variant', 'bullet-rows');
    expect(rowList).toHaveAttribute('data-research-frame', 'content');
    expect(rowList).toHaveClass('divide-y');
    expect(screen.getByText('行一').closest('li')?.className || '').not.toMatch(/rounded-xl/);
  });
});
