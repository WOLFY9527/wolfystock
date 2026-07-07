import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { IntelligentImport } from '../IntelligentImport';
import { SystemConfigConflictError } from '../../../api/systemConfig';

const { extractFromImage, parseImport, onMergeStockList } = vi.hoisted(() => ({
  extractFromImage: vi.fn(),
  parseImport: vi.fn(),
  onMergeStockList: vi.fn(),
}));

vi.mock('../../../api/stocks', () => ({
  stocksApi: {
    parseImport,
    extractFromImage,
  },
}));

describe('IntelligentImport', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses visible buttons as the only file-picker activation owners', () => {
    const inputClick = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(() => undefined);
    const { container } = render(
      <IntelligentImport
        stockListValue=""
        onMergeStockList={onMergeStockList}
      />,
    );

    expect(container.querySelector('label')).toBeNull();

    const imageInput = screen.getByLabelText('选择图片');
    const dataInput = screen.getByLabelText('选择文件');
    expect(imageInput).toHaveAttribute('accept', '.jpg,.jpeg,.png,.webp,.gif');
    expect(dataInput).toHaveAttribute('accept', '.csv,.xlsx,.txt');

    fireEvent.click(screen.getByRole('button', { name: '选择图片' }));
    expect(inputClick).toHaveBeenLastCalledWith();
    expect(inputClick.mock.instances.at(-1)).toBe(imageInput);

    fireEvent.click(screen.getByRole('button', { name: '选择文件' }));
    expect(inputClick.mock.instances.at(-1)).toBe(dataInput);

    inputClick.mockRestore();
  });

  it('keeps file inputs disabled with their visible picker buttons', () => {
    render(
      <IntelligentImport
        stockListValue=""
        onMergeStockList={onMergeStockList}
        disabled
      />,
    );

    expect(screen.getByRole('button', { name: '选择图片' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '选择文件' })).toBeDisabled();
    expect(screen.getByLabelText('选择图片')).toBeDisabled();
    expect(screen.getByLabelText('选择文件')).toBeDisabled();
  });

  it('preserves the image and data file change handlers', async () => {
    extractFromImage.mockResolvedValue({
      items: [{ code: 'SH600519', name: 'Kweichow Moutai', confidence: 'high' }],
      codes: [],
    });
    parseImport.mockResolvedValue({
      items: [{ code: 'SZ000001', name: 'Ping An Bank', confidence: 'high' }],
      codes: [],
    });

    render(
      <IntelligentImport
        stockListValue=""
        onMergeStockList={onMergeStockList}
      />,
    );

    const imageFile = new File(['png'], 'watchlist.png', { type: 'image/png' });
    fireEvent.change(screen.getByLabelText('选择图片'), {
      target: { files: [imageFile] },
    });
    await screen.findByText('SH600519');
    expect(extractFromImage).toHaveBeenCalledWith(imageFile);

    const dataFile = new File(['code\n000001'], 'watchlist.csv', { type: 'text/csv' });
    fireEvent.change(screen.getByLabelText('选择文件'), {
      target: { files: [dataFile] },
    });
    await screen.findByText('SZ000001');
    expect(parseImport).toHaveBeenCalledWith(dataFile);
  });

  it('refreshes config state after a config version conflict', async () => {
    parseImport.mockResolvedValue({
      items: [{ code: 'SZ000001', name: 'Ping An Bank', confidence: 'high' }],
      codes: [],
    });
    onMergeStockList
      .mockRejectedValueOnce(new SystemConfigConflictError('配置版本冲突', 'v2'))
      .mockResolvedValueOnce(undefined);

    render(
      <IntelligentImport
        stockListValue="SH600000"
        onMergeStockList={onMergeStockList}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('或粘贴 CSV/Excel 复制的文本...'), {
      target: { value: '000001' },
    });
    fireEvent.click(screen.getByRole('button', { name: '解析' }));

    await screen.findByText('SZ000001');

    fireEvent.click(screen.getByRole('button', { name: '合并到自选股' }));

    await waitFor(() => {
      expect(onMergeStockList).toHaveBeenCalledTimes(2);
    });
    expect(onMergeStockList).toHaveBeenCalledWith('SH600000,SZ000001');
    expect(await screen.findByText('配置已更新，请再次点击「合并到自选股」')).toBeInTheDocument();
  });

  it('shows a unified message when merge saving fails', async () => {
    parseImport.mockResolvedValue({
      items: [{ code: 'SZ000002', name: 'Vanke', confidence: 'high' }],
      codes: [],
    });
    onMergeStockList.mockRejectedValueOnce({
      response: {
        status: 500,
        data: {
          message: 'Internal Server Error',
        },
      },
    });

    render(
      <IntelligentImport
        stockListValue="SH600000"
        onMergeStockList={onMergeStockList}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('或粘贴 CSV/Excel 复制的文本...'), {
      target: { value: '000002' },
    });
    fireEvent.click(screen.getByRole('button', { name: '解析' }));

    await screen.findByText('SZ000002');

    fireEvent.click(screen.getByRole('button', { name: '合并到自选股' }));

    await waitFor(() => {
      expect(onMergeStockList).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText('服务器暂时不可用，请稍后重试。')).toBeInTheDocument();
  });
});
