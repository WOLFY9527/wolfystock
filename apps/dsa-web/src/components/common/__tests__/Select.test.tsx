import { render, screen } from '@testing-library/react';
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
    expect(select).toHaveClass('ui-control-value', 'w-full', 'min-w-0', 'max-w-full', 'pr-10');

    const control = container.querySelector('.select-field__control');
    expect(control).toHaveClass('ui-control-shell', 'min-w-0', 'w-full', 'max-w-full');

    const icon = container.querySelector('.select-field__icon');
    expect(icon).toHaveClass('ui-control-icon');
  });
});
