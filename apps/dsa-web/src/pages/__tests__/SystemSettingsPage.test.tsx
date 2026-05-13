import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import SystemSettingsPage from '../SystemSettingsPage';

vi.mock('../SettingsPage', () => ({
  default: () => <div>settings-page-core</div>,
}));

describe('SystemSettingsPage', () => {
  it('renders the system settings surface on the shared shell without duplicating route-local shell width or background slabs', () => {
    render(
      <MemoryRouter initialEntries={['/settings/system']}>
        <SystemSettingsPage />
      </MemoryRouter>,
    );

    const pageRoot = screen.getByTestId('system-settings-page');
    const shellHeader = screen.getByTestId('system-settings-shell-header');

    expect(screen.getByRole('heading', { name: '系统设置' })).toBeInTheDocument();
    expect(screen.getByText('settings-page-core')).toBeInTheDocument();
    expect(pageRoot).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(pageRoot).toHaveClass('w-full', 'max-w-[1600px]', 'mx-auto', 'px-4', 'xl:px-8', 'flex', 'flex-col', 'gap-6');
    expect(pageRoot.className).not.toContain('bg-[#050505]');
    expect(shellHeader.className).not.toContain('max-w-[1600px]');
    expect(shellHeader.className).not.toContain('mx-auto');
    expect(shellHeader.className).not.toContain('px-4');
    expect(shellHeader.className).not.toContain('md:px-6');
    expect(shellHeader.className).not.toContain('xl:px-8');
    expect(shellHeader.className).not.toContain('bg-[#050505]');
  });
});
