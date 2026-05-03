import { render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it, vi } from 'vitest';
import { Select } from '../Select';

vi.mock('../../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    t: () => 'Select an option',
  }),
}));

describe('Select', () => {
  it('reserves arrow space and keeps the control shell overflow-safe', () => {
    const handleChange = vi.fn();
    const { container } = render(
      <Select
        label="Market"
        value="us"
        onChange={handleChange}
        options={[
          { value: 'us', label: 'United States market with a very long label' },
          { value: 'hk', label: 'Hong Kong' },
        ]}
      />
    );

    const select = screen.getByLabelText('Market');
    expect(select).toHaveClass('select-surface', 'ui-control-value', 'w-full', 'min-w-0', 'max-w-full', 'pr-10', 'appearance-none');

    const control = container.querySelector('.select-field__control');
    expect(control).toHaveClass('ui-control-shell', 'min-w-0', 'w-full', 'max-w-full');

    const icon = container.querySelector('.select-field__icon');
    expect(icon).toHaveClass('ui-control-icon', 'pointer-events-none');
  });

  it('keeps the SpaceX theme select override from erasing chevron padding', () => {
    const css = readFileSync(resolve(__dirname, '../../../index.css'), 'utf8');

    expect(css).toContain("html[data-theme='spacex'] select.select-surface");
    expect(css).toContain('padding-right: 2.5rem;');
    expect(css).toContain('letter-spacing: 0;');
  });
});
