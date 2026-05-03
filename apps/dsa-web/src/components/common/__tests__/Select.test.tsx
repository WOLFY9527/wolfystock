import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Select } from '../Select';

vi.mock('../../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    t: () => 'Select an option',
  }),
}));

describe('Select', () => {
  it('renders an invisible native select plus an aria-hidden overlay label', () => {
    const handleChange = vi.fn();
    render(
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
    expect(select).toHaveClass('select-surface', 'absolute', 'inset-0', 'z-10', 'h-full', 'w-full', 'opacity-0');

    const overlay = select.closest('.select-field__control')?.querySelector('.select-field__overlay');
    expect(overlay).toHaveAttribute('aria-hidden', 'true');
    expect(overlay).toHaveClass('pointer-events-none', 'flex', 'min-w-0', 'items-center', 'rounded-lg');

    const label = overlay?.querySelector('.select-field__value');
    expect(label).toHaveTextContent('United States market with a very long label');
    expect(label).toHaveClass('min-w-0', 'flex-1', 'truncate');

    const icon = overlay?.querySelector('.select-field__icon');
    expect(icon).toHaveClass('ml-2', 'shrink-0', 'text-white/40');
  });

  it('keeps native select behavior and updates the visible label when controlled value changes', () => {
    const handleChange = vi.fn();
    const { rerender } = render(
      <Select
        label="Market"
        value="us"
        onChange={handleChange}
        options={[
          { value: 'us', label: 'United States' },
          { value: 'hk', label: 'Hong Kong' },
        ]}
      />
    );

    const select = screen.getByLabelText('Market');
    fireEvent.change(select, { target: { value: 'hk' } });
    expect(handleChange).toHaveBeenCalledWith('hk');

    rerender(
      <Select
        label="Market"
        value="hk"
        onChange={handleChange}
        options={[
          { value: 'us', label: 'United States' },
          { value: 'hk', label: 'Hong Kong' },
        ]}
      />
    );

    expect(select.closest('.select-field__control')?.querySelector('.select-field__value')).toHaveTextContent('Hong Kong');
  });

  it('dims the overlay when disabled and keeps placeholder text readable', () => {
    render(
      <Select
        label="Market"
        value=""
        onChange={vi.fn()}
        placeholder="Pick a market"
        disabled
        options={[
          { value: 'us', label: 'United States' },
          { value: 'hk', label: 'Hong Kong' },
        ]}
      />
    );

    const select = screen.getByLabelText('Market');
    expect(select).toBeDisabled();
    expect(select.closest('.select-field__control')?.querySelector('.select-field__overlay')).toHaveClass('opacity-50');
    expect(select.closest('.select-field__control')?.querySelector('.select-field__value')).toHaveTextContent('Pick a market');
  });

  it('derives the visible label from option children when custom option markup is provided', () => {
    render(
      <Select label="Theme" value="crypto" onChange={vi.fn()}>
        <option value="">Select a theme</option>
        <optgroup label="Ready seed lists">
          <option value="crypto">Crypto miners</option>
        </optgroup>
      </Select>
    );

    const select = screen.getByLabelText('Theme');
    expect(select.closest('.select-field__control')?.querySelector('.select-field__value')).toHaveTextContent('Crypto miners');
  });
});
