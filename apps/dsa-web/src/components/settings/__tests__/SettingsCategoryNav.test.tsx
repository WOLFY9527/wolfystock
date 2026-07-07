import { render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsCategoryNav } from '../SettingsCategoryNav';

vi.mock('../../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: 'zh',
    t: (key: string) => key,
  }),
}));

vi.mock('../../../utils/systemConfigI18n', () => ({
  getCategoryTitle: (_language: string, _category: string, title: string) => title,
}));

const categories = [
  { category: 'ai_model', title: 'AI 模型' },
  { category: 'data_source', title: '数据源' },
  { category: 'notification', title: '通知' },
];

const itemsByCategory = {
  ai_model: [{ key: 'AI_MODEL' }],
  data_source: [{ key: 'DATA_SOURCE_A' }, { key: 'DATA_SOURCE_B' }],
  notification: [],
};

describe('SettingsCategoryNav', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
  });

  it('exposes one current category and keeps focused category buttons visible', () => {
    render(
      <SettingsCategoryNav
        categories={categories as never}
        itemsByCategory={itemsByCategory as never}
        activeCategory="data_source"
        onSelect={vi.fn()}
        hideHeader
      />,
    );

    const nav = screen.getByRole('button', { name: /数据源/ }).closest('div');
    expect(nav?.querySelectorAll('[aria-current="true"]')).toHaveLength(1);
    expect(screen.getByRole('button', { name: /数据源/ })).toHaveAttribute('aria-current', 'true');
    expect(screen.getByRole('button', { name: /AI 模型/ })).not.toHaveAttribute('aria-current');
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ block: 'nearest', inline: 'nearest' });
    expect(within(screen.getByRole('button', { name: /数据源/ })).getByText('2')).toBeInTheDocument();
  });
});
