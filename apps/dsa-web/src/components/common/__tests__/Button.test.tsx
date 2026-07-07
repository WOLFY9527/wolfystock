import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Button } from '../Button';

describe('Button', () => {
  it('renders children', () => {
    render(<Button>Click me</Button>);

    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
  });

  it('uses button type by default and exposes the selected variant', () => {
    render(<Button variant="danger">Delete</Button>);

    const button = screen.getByRole('button', { name: 'Delete' });
    expect(button).toHaveAttribute('type', 'button');
    expect(button).toHaveAttribute('data-variant', 'danger');
    expect(button).toHaveAttribute('data-action-intent', 'write');
    expect(button).toHaveAttribute('data-control-state', 'ready');
    expect(button.className).toContain('border');
  });

  it('disables the button when loading and shows loading text', () => {
    render(<Button isLoading loadingText="Saving">Save</Button>);

    const button = screen.getByRole('button', { name: /saving/i });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');
    expect(button).toHaveAttribute('data-control-state', 'loading');
    expect(screen.getByText('Saving')).toBeInTheDocument();
  });

  it('supports the danger-subtle variant', () => {
    render(<Button variant="danger-subtle">Bulk Delete</Button>);

    const button = screen.getByRole('button', { name: 'Bulk Delete' });
    expect(button).toHaveAttribute('data-variant', 'danger-subtle');
    expect(button.className).toContain('border');
    expect(button).not.toBeDisabled();
  });

  it('keeps write actions distinct from passive and navigation controls', () => {
    render(
      <>
        <Button variant="primary">Run scan</Button>
        <Button variant="secondary">Open details</Button>
        <Button variant="outline" actionIntent="navigate">Go to report</Button>
      </>
    );

    expect(screen.getByRole('button', { name: 'Run scan' })).toHaveAttribute('data-action-intent', 'write');
    expect(screen.getByRole('button', { name: 'Open details' })).toHaveAttribute('data-action-intent', 'passive');
    expect(screen.getByRole('button', { name: 'Go to report' })).toHaveAttribute('data-action-intent', 'navigate');
  });
});
