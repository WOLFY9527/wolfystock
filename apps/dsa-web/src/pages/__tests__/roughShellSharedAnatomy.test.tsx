import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  RoughBulletList,
  RoughCompactKeyValue,
  RoughDisclosureSection,
  RoughEvidenceGroup,
  RoughResearchRows,
  RoughResearchSection,
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

  it('renders low-chrome research section and divided rows', () => {
    render(
      <RoughResearchSection eyebrow="证据" title="结构证据" data-testid="research-section">
        <RoughResearchRows
          data-testid="research-rows"
          rows={[
            { title: '关键区域', body: '仍在区间内', trailing: 'A' },
            { title: '量能', body: '待确认', trailing: 'B' },
          ]}
        />
      </RoughResearchSection>,
    );

    expect(screen.getByTestId('research-section')).toHaveAttribute('data-rough-variant', 'research-section');
    expect(screen.getByTestId('research-section')).toHaveAttribute('data-research-frame', 'section');
    expect(screen.getByTestId('research-section').className).toMatch(/border-b/);
    expect(screen.getByTestId('research-rows')).toHaveAttribute('data-research-frame', 'content');
    expect(screen.getByText('关键区域')).toBeInTheDocument();
    expect(screen.getByText('量能')).toBeInTheDocument();
  });

  it('supports grouped evidence, compact key-value, and disclosure sections', () => {
    render(
      <>
        <RoughEvidenceGroup label="因子证据" data-testid="evidence-group">
          <RoughCompactKeyValue
            data-testid="compact-kv"
            rows={[
              { key: 'a', label: '覆盖', value: '部分', detail: 'proxy != official' },
            ]}
          />
        </RoughEvidenceGroup>
        <RoughDisclosureSection title="详细限制" summary="默认折叠" data-testid="disclosure">
          <p>模型仅覆盖已披露证据</p>
        </RoughDisclosureSection>
      </>,
    );

    expect(screen.getByTestId('evidence-group')).toHaveAttribute('data-rough-variant', 'evidence-group');
    expect(screen.getByTestId('compact-kv')).toHaveAttribute('data-rough-variant', 'compact-key-value');
    expect(screen.getByText('proxy != official')).toBeInTheDocument();
    expect(screen.queryByText('模型仅覆盖已披露证据')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /展开/ }));
    expect(screen.getByText('模型仅覆盖已披露证据')).toBeInTheDocument();
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
