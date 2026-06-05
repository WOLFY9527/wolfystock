import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SystemSettingsPage from '../SystemSettingsPage';

const mockDraftResetTrigger = vi.fn();
const mockLegacyFactoryResetTrigger = vi.fn();

vi.mock('../SettingsPage', async () => {
  const React = await import('react');
  const MockSettingsPage = () => {
    const [draftResetOpened, setDraftResetOpened] = React.useState(false);
    const [legacyConfirmOpened, setLegacyConfirmOpened] = React.useState(false);

    return (
      <div>
        <div>settings-page-core</div>
        <button
          type="button"
          onClick={() => {
            mockDraftResetTrigger();
            setDraftResetOpened(true);
          }}
        >
          重置
        </button>
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
        {draftResetOpened ? <div>draft-reset-path-opened</div> : null}
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
    mockDraftResetTrigger.mockReset();
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

  it('clicking reset opens an explicit confirmation dialog before the draft reset executes', async () => {
    render(
      <MemoryRouter initialEntries={['/zh/settings/system']}>
        <SystemSettingsPage />
      </MemoryRouter>,
    );

    await screen.findByText('settings-page-core');

    fireEvent.click(screen.getByRole('button', { name: '重置' }));

    expect(await screen.findByRole('heading', { name: '确认重置？' })).toBeInTheDocument();
    expect(screen.getByText('所有未保存更改将丢失。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '确认重置' })).toBeInTheDocument();
    expect(mockDraftResetTrigger).not.toHaveBeenCalled();
    expect(screen.queryByText('draft-reset-path-opened')).not.toBeInTheDocument();
  });

  it('cancel does not execute the reset path', async () => {
    render(
      <MemoryRouter initialEntries={['/zh/settings/system']}>
        <SystemSettingsPage />
      </MemoryRouter>,
    );

    await screen.findByText('settings-page-core');

    fireEvent.click(screen.getByRole('button', { name: '重置' }));
    const cancelButtons = await screen.findAllByRole('button', { name: '取消' });
    fireEvent.click(cancelButtons.at(-1)!);

    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: '确认重置？' })).not.toBeInTheDocument();
    });
    expect(mockDraftResetTrigger).not.toHaveBeenCalled();
    expect(screen.queryByText('draft-reset-path-opened')).not.toBeInTheDocument();
  });

  it('confirm executes the existing draft reset path exactly once', async () => {
    render(
      <MemoryRouter initialEntries={['/zh/settings/system']}>
        <SystemSettingsPage />
      </MemoryRouter>,
    );

    await screen.findByText('settings-page-core');

    fireEvent.click(screen.getByRole('button', { name: '重置' }));
    fireEvent.click(await screen.findByRole('button', { name: '确认重置' }));

    await waitFor(() => {
      expect(mockDraftResetTrigger).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText('draft-reset-path-opened')).toBeInTheDocument();
  });

  it('keeps default-visible copy token/internal-safe while preserving the factory reset confirmation gate', async () => {
    render(
      <MemoryRouter initialEntries={['/zh/settings/system']}>
        <SystemSettingsPage />
      </MemoryRouter>,
    );

    await screen.findByText('settings-page-core');
    expect(screen.queryByText(/token|internal|debug|provider|cache|env|router|payload|credential/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '执行工厂重置' }));

    expect(await screen.findByRole('heading', { name: '确认重置系统设置？' })).toBeInTheDocument();
    expect(screen.getByText('所有未保存更改将丢失，系统初始化仍会进入现有确认步骤。')).toBeInTheDocument();
    const cancelButtons = screen.getAllByRole('button', { name: '取消' });
    const confirmResetButton = screen.getByRole('button', { name: '继续' });
    expect(cancelButtons.at(-1)).toBeInTheDocument();
    expect(confirmResetButton).toBeInTheDocument();
    expect(mockLegacyFactoryResetTrigger).not.toHaveBeenCalled();
    expect(screen.queryByText('legacy-factory-reset-path-opened')).not.toBeInTheDocument();

    fireEvent.click(cancelButtons.at(-1)!);

    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: '确认重置系统设置？' })).not.toBeInTheDocument();
    });
    expect(mockLegacyFactoryResetTrigger).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: '执行工厂重置' }));
    fireEvent.click(await screen.findByRole('button', { name: '继续' }));

    await waitFor(() => {
      expect(mockLegacyFactoryResetTrigger).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText('legacy-factory-reset-path-opened')).toBeInTheDocument();
  });
});
