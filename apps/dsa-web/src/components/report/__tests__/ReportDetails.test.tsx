import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ReportDetails } from '../ReportDetails';

const writeTextMock = vi.fn();
let originalClipboard: Navigator['clipboard'] | undefined;

describe('ReportDetails', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    writeTextMock.mockReset();
    writeTextMock.mockResolvedValue(undefined);
    originalClipboard = navigator.clipboard;
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: writeTextMock,
      },
    });
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: originalClipboard,
    });
    vi.useRealTimers();
  });

  it('shows copied feedback only for the panel that was copied', async () => {
    const details = {
      rawResult: { signal: 'buy' },
      contextSnapshot: { source: 'cache' },
    };

    render(<ReportDetails details={details} audience="admin" />);

    fireEvent.click(screen.getByRole('button', { name: '原始分析结果' }));
    fireEvent.click(screen.getByRole('button', { name: '分析快照' }));

    const [rawCopyButton, snapshotCopyButton] = screen.getAllByRole('button', { name: '复制' });

    await act(async () => {
      fireEvent.click(rawCopyButton);
      await Promise.resolve();
    });

    expect(writeTextMock).toHaveBeenNthCalledWith(1, JSON.stringify(details.rawResult, null, 2));
    expect(screen.getByRole('button', { name: '已复制' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: '复制' })).toHaveLength(1);

    await act(async () => {
      fireEvent.click(snapshotCopyButton);
      await Promise.resolve();
    });

    expect(writeTextMock).toHaveBeenNthCalledWith(2, JSON.stringify(details.contextSnapshot, null, 2));
    expect(screen.getAllByRole('button', { name: '已复制' })).toHaveLength(2);

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.getAllByRole('button', { name: '复制' })).toHaveLength(2);
  });

  it('defaults to a user-safe summary without raw diagnostic panels', () => {
    const details = {
      rawResult: { provider: 'fixture-provider', schema: 'debug' },
      contextSnapshot: { source: 'cache' },
    };

    render(<ReportDetails details={details} recordId={42} />);

    expect(screen.getByText('普通用户页面已隐藏详细诊断。')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '原始分析结果' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '分析快照' })).not.toBeInTheDocument();
    expect(screen.queryByText(/fixture-provider|schema|debug|cache/)).not.toBeInTheDocument();
  });
});
