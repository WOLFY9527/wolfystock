import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import SystemSettingsPage from '../SystemSettingsPage';

vi.mock('../SettingsPage', () => ({
  default: () => <div>settings-page-core</div>,
}));

describe('SystemSettingsPage', () => {
  it('renders the system settings surface on the shared shell without a page-local black slab', () => {
    render(
      <MemoryRouter initialEntries={['/settings/system']}>
        <SystemSettingsPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: '系统设置' })).toBeInTheDocument();
    expect(screen.getByText('settings-page-core')).toBeInTheDocument();
    expect(screen.getByTestId('system-settings-page').className).not.toContain('bg-[#050505]');
    expect(screen.getByTestId('system-settings-shell-header').className).not.toContain('bg-[#050505]');
  });
});
