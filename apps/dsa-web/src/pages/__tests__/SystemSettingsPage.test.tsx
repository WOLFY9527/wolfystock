import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SystemSettingsPage from '../SystemSettingsPage';

const mockLegacyFactoryResetTrigger = vi.fn();

vi.mock('../SettingsPage', async () => {
  const React = await import('react');
  const MockSettingsPage = () => {
    const [legacyConfirmOpened, setLegacyConfirmOpened] = React.useState(false);

    return (
      <div>
        <div>settings-page-core</div>
        <button
          type="button"
          data-system-settings-reset-action="factory_reset"
          onClick={() => {
            mockLegacyFactoryResetTrigger();
            setLegacyConfirmOpened(true);
          }}
        >
          执行工厂重置
        </button>
        {legacyConfirmOpened ? <div>legacy-factory-reset-path-opened</div> : null}
      </div>
    );
  };

  return {
    default: MockSettingsPage,
  };
});

describe('SystemSettingsPage', () => {
  beforeEach(() => {
    mockLegacyFactoryResetTrigger.mockReset();
    window.history.pushState({}, '', '/settings/system');
  });

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
    expect(screen.getByText('管理员默认落点')).toBeInTheDocument();
    expect(
      screen.getByText('这里是管理员进入系统配置与控制事项的默认落点，不是缺失的独立仪表盘。请先确认全局风险、待处理配置和安全下一步，再进入下方运维中心。'),
    ).toBeInTheDocument();
    expect(within(overviewStrip).getByText('信任状态')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('影响范围')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('建议动作')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('证据参考')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('最近更新')).toBeInTheDocument();
    expect(within(overviewStrip).getByText('系统运维中心 / 下方摘要')).toBeInTheDocument();
    expect(screen.getByText('凭证、调度、系统状态与高风险操作仍需结合运维中心快照确认。')).toBeInTheDocument();
    expect(screen.getByText('详细配置项保留在下方运维中心。')).toBeInTheDocument();
    expect(screen.queryByText(/control plane/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/token|debug|provider|cache|env|router/i)).not.toBeInTheDocument();
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

  it('shows localized admin-landing copy on the english system settings route', async () => {
    window.history.pushState({}, '', '/en/settings/system');

    render(
      <MemoryRouter initialEntries={['/en/settings/system']}>
        <SystemSettingsPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: 'System Settings' })).toBeInTheDocument();
    expect(screen.getByText('Default admin landing')).toBeInTheDocument();
    expect(
      screen.getByText('This page is the default landing for admin settings and control work, not a missing standalone dashboard. Review overall risk, pending setup, and safe next steps before opening the control center below.'),
    ).toBeInTheDocument();
    expect(screen.getByText('System control center / summary below')).toBeInTheDocument();
    expect(screen.queryByText(/token|debug|provider|cache|env|router/i)).not.toBeInTheDocument();

    expect(await screen.findByText('settings-page-core')).toBeInTheDocument();
  });

  it('opens a reset confirmation layer before the legacy factory-reset path, cancels safely, and only forwards once on confirm', async () => {
    render(
      <MemoryRouter initialEntries={['/zh/settings/system']}>
        <SystemSettingsPage />
      </MemoryRouter>,
    );

    await screen.findByText('settings-page-core');

    fireEvent.click(screen.getByRole('button', { name: '执行工厂重置' }));

    expect(await screen.findByRole('heading', { name: '确认重置系统设置' })).toBeInTheDocument();
    expect(screen.getByText('该操作可能重置系统级设置，并清理与系统初始化相关的会话、分析与聊天历史、扫描/回测/持仓使用数据以及通知目标；执行后较难撤销。')).toBeInTheDocument();
    const cancelButtons = screen.getAllByRole('button', { name: '取消' });
    const confirmResetButton = screen.getByRole('button', { name: '确认重置' });
    expect(cancelButtons.at(-1)).toBeInTheDocument();
    expect(confirmResetButton).toBeInTheDocument();
    expect(mockLegacyFactoryResetTrigger).not.toHaveBeenCalled();
    expect(screen.queryByText('legacy-factory-reset-path-opened')).not.toBeInTheDocument();

    fireEvent.click(cancelButtons.at(-1)!);

    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: '确认重置系统设置' })).not.toBeInTheDocument();
    });
    expect(mockLegacyFactoryResetTrigger).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: '执行工厂重置' }));
    fireEvent.click(await screen.findByRole('button', { name: '确认重置' }));

    await waitFor(() => {
      expect(mockLegacyFactoryResetTrigger).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText('legacy-factory-reset-path-opened')).toBeInTheDocument();
  });
});
