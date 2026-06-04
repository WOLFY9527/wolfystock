import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import SystemSettingsPage from '../SystemSettingsPage';

vi.mock('../SettingsPage', () => ({
  default: () => <div>settings-page-core</div>,
}));

describe('SystemSettingsPage', () => {
  it('renders the system settings surface through the lazy console boundary without duplicating route-local shell width or background slabs', async () => {
    render(
      <MemoryRouter initialEntries={['/settings/system']}>
        <SystemSettingsPage />
      </MemoryRouter>,
    );

    const pageRoot = screen.getByTestId('system-settings-page');
    const shellHeader = screen.getByTestId('system-settings-shell-header');
    const overviewStrip = screen.getByTestId('system-settings-l0-overview-strip');

    expect(screen.getByRole('heading', { name: '系统设置' })).toBeInTheDocument();
    expect(within(overviewStrip).getByText('信任状态')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('影响范围')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('建议动作')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('证据参考')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('最近更新')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('System operations / 下方运维中心')).toBeInTheDocument();
    expect(screen.getByText(/深层配置、原始字段和危险系统动作留在下方运维中心/)).toBeInTheDocument();
    expect(screen.queryByText(/control plane/i)).not.toBeInTheDocument();
    expect(screen.getByTestId('system-settings-loading')).toHaveAttribute('aria-busy', 'true');
    expect(await screen.findByText('settings-page-core')).toBeInTheDocument();
    expect(pageRoot).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(pageRoot).toHaveClass('w-full', 'max-w-[1600px]', 'mx-auto', 'px-4', 'xl:px-8', 'flex', 'flex-col', 'gap-5', 'min-h-0', 'flex-1', 'overflow-x-hidden', 'py-5', 'text-white', 'md:py-6');
    expect(pageRoot.className).not.toContain('bg-[#050505]');
    expect(shellHeader.className).not.toContain('max-w-[1600px]');
    expect(shellHeader.className).not.toContain('mx-auto');
    expect(shellHeader.className).not.toContain('px-4');
    expect(shellHeader.className).not.toContain('md:px-6');
    expect(shellHeader.className).not.toContain('xl:px-8');
    expect(shellHeader.className).not.toContain('bg-[#050505]');
  });
});
