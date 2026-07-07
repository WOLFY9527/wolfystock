import type React from 'react';
import { useReducer, useRef } from 'react';
import { getApiErrorMessage } from '../../api/error';
import { stocksApi, type ExtractItem } from '../../api/stocks';
import { SystemConfigConflictError } from '../../api/systemConfig';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { SupportBanner, SupportPanel } from '../common/SupportSurface';

const IMG_EXT = ['.jpg', '.jpeg', '.png', '.webp', '.gif'];
const IMG_MAX = 5 * 1024 * 1024; // 5MB
const FILE_MAX = 2 * 1024 * 1024; // 2MB
const TEXT_MAX = 100 * 1024; // 100KB

interface IntelligentImportProps {
  stockListValue: string;
  onMergeStockList: (newValue: string) => void | Promise<void>;
  disabled?: boolean;
}

type ItemWithChecked = ExtractItem & { id: string; checked: boolean };

type ImportState = {
  items: ItemWithChecked[];
  isLoading: boolean;
  isMerging: boolean;
  error: string | null;
  isDragging: boolean;
  pasteText: string;
};

type ImportAction =
  | { type: 'setPasteText'; value: string }
  | { type: 'setDragging'; value: boolean }
  | { type: 'validationError'; message: string }
  | { type: 'loadStarted' }
  | { type: 'loadSucceeded'; items: ExtractItem[] }
  | { type: 'loadFailed'; message: string }
  | { type: 'pasteLoadSucceeded'; items: ExtractItem[] }
  | { type: 'mergeStarted' }
  | { type: 'mergeSucceeded' }
  | { type: 'mergeFailed'; message: string }
  | { type: 'toggleChecked'; id: string }
  | { type: 'toggleAll'; checked: boolean }
  | { type: 'removeItem'; id: string }
  | { type: 'clearAll' };

const INITIAL_IMPORT_STATE: ImportState = {
  items: [],
  isLoading: false,
  isMerging: false,
  error: null,
  isDragging: false,
  pasteText: '',
};

function importReducer(state: ImportState, action: ImportAction): ImportState {
  switch (action.type) {
    case 'setPasteText':
      return { ...state, pasteText: action.value };
    case 'setDragging':
      return { ...state, isDragging: action.value };
    case 'validationError':
      return { ...state, error: action.message };
    case 'loadStarted':
      return { ...state, error: null, isLoading: true };
    case 'loadSucceeded':
      return {
        ...state,
        items: mergeItems(state.items, action.items),
        isLoading: false,
      };
    case 'loadFailed':
      return { ...state, error: action.message, isLoading: false };
    case 'pasteLoadSucceeded':
      return {
        ...state,
        items: mergeItems(state.items, action.items),
        pasteText: '',
        isLoading: false,
      };
    case 'mergeStarted':
      return { ...state, error: null, isMerging: true };
    case 'mergeSucceeded':
      return { ...state, items: [], pasteText: '', isMerging: false };
    case 'mergeFailed':
      return { ...state, error: action.message, isMerging: false };
    case 'toggleChecked':
      return {
        ...state,
        items: state.items.map((item) => (
          item.id === action.id && item.code ? { ...item, checked: !item.checked } : item
        )),
      };
    case 'toggleAll':
      return {
        ...state,
        items: state.items.map((item) => (item.code ? { ...item, checked: action.checked } : item)),
      };
    case 'removeItem':
      return { ...state, items: state.items.filter((item) => item.id !== action.id) };
    case 'clearAll':
      return { ...state, items: [], pasteText: '', error: null };
    default:
      return state;
  }
}

function getConfidenceMeta(confidence: 'high' | 'medium' | 'low') {
  if (confidence === 'high') {
    return { label: '高', badge: 'success' as const };
  }
  if (confidence === 'low') {
    return { label: '低', badge: 'warning' as const };
  }
  return { label: '中', badge: 'default' as const };
}

function normalizeConfidence(confidence?: string | null): 'high' | 'medium' | 'low' {
  if (confidence === 'high' || confidence === 'low' || confidence === 'medium') {
    return confidence;
  }
  return 'medium';
}

function mergeItems(
  prev: ItemWithChecked[],
  newItems: ExtractItem[]
): ItemWithChecked[] {
  const byCode = new Map<string, ItemWithChecked>();
  const confOrder: Record<'high' | 'medium' | 'low', number> = {
    high: 3,
    medium: 2,
    low: 1,
  };
  const failed: ItemWithChecked[] = [];
  for (const p of prev) {
    if (p.code) {
      byCode.set(p.code, p);
    } else {
      failed.push(p);
    }
  }
  for (const it of newItems) {
    const normalizedConfidence = normalizeConfidence(it.confidence);
    if (it.code) {
      const existing = byCode.get(it.code);
      if (!existing) {
        byCode.set(it.code, {
          ...it,
          confidence: normalizedConfidence,
          id: `${it.code}-${Date.now()}-${Math.random().toString(36).slice(2)}`,
          checked: normalizedConfidence === 'high',
        });
      } else {
        const existingConfidence = normalizeConfidence(existing.confidence);
        const shouldUpgradeConfidence = confOrder[normalizedConfidence] > confOrder[existingConfidence];
        const shouldFillName = !existing.name && !!it.name;

        if (shouldUpgradeConfidence || shouldFillName) {
          byCode.set(it.code, {
            ...existing,
            name: it.name || existing.name,
            confidence: shouldUpgradeConfidence ? normalizedConfidence : existingConfidence,
            checked: shouldUpgradeConfidence
              ? (normalizedConfidence === 'high' ? true : existing.checked)
              : existing.checked,
          });
        }
      }
    } else {
      failed.push({
        ...it,
        confidence: normalizedConfidence,
        id: `fail-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        checked: false,
      });
    }
  }
  return [...byCode.values(), ...failed];
}

export const IntelligentImport: React.FC<IntelligentImportProps> = ({
  stockListValue,
  onMergeStockList,
  disabled,
}) => {
  const [state, dispatch] = useReducer(importReducer, INITIAL_IMPORT_STATE);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const dataInputRef = useRef<HTMLInputElement | null>(null);
  const {
    items,
    isLoading,
    isMerging,
    error,
    isDragging,
    pasteText,
  } = state;

  const parseCurrentList = () => {
    return stockListValue.split(',').flatMap((c) => {
      const trimmed = c.trim();
      return trimmed ? [trimmed] : [];
    });
  };

  const handleImageFile = async (file: File) => {
    const ext = '.' + (file.name.split('.').pop() ?? '').toLowerCase();
    if (!IMG_EXT.includes(ext)) {
      dispatch({ type: 'validationError', message: '图片仅支持 JPG、PNG、WebP、GIF' });
      return;
    }
    if (file.size > IMG_MAX) {
      dispatch({ type: 'validationError', message: '图片不超过 5MB' });
      return;
    }
    dispatch({ type: 'loadStarted' });
    try {
      const res = await stocksApi.extractFromImage(file);
      dispatch({ type: 'loadSucceeded', items: res.items ?? res.codes.map((c) => ({ code: c, name: null, confidence: 'medium' })) });
    } catch (e) {
      dispatch({ type: 'loadFailed', message: getApiErrorMessage(e, '识别失败，请重试') });
    }
  };

  const handleDataFile = async (file: File) => {
    if (file.size > FILE_MAX) {
      dispatch({ type: 'validationError', message: '文件不超过 2MB' });
      return;
    }
    dispatch({ type: 'loadStarted' });
    try {
      const res = await stocksApi.parseImport(file);
      dispatch({ type: 'loadSucceeded', items: res.items ?? res.codes.map((c) => ({ code: c, name: null, confidence: 'medium' })) });
    } catch (e) {
      dispatch({ type: 'loadFailed', message: getApiErrorMessage(e, '解析失败') });
    }
  };

  const handlePasteParse = () => {
    const t = pasteText.trim();
    if (!t) return;
    if (new Blob([t]).size > TEXT_MAX) {
      dispatch({ type: 'validationError', message: '粘贴文本不超过 100KB' });
      return;
    }
    dispatch({ type: 'loadStarted' });
    stocksApi
      .parseImport(undefined, t)
      .then((res) => {
        dispatch({ type: 'pasteLoadSucceeded', items: res.items ?? res.codes.map((c) => ({ code: c, name: null, confidence: 'medium' })) });
      })
      .catch((e) => {
        dispatch({ type: 'loadFailed', message: getApiErrorMessage(e, '解析失败') });
      });
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    dispatch({ type: 'setDragging', value: false });
    if (disabled || isLoading) return;
    const f = e.dataTransfer?.files?.[0];
    if (!f) return;
    const ext = '.' + (f.name.split('.').pop() ?? '').toLowerCase();
    if (IMG_EXT.includes(ext)) void handleImageFile(f);
    else void handleDataFile(f);
  };

  const onImageInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) void handleImageFile(f);
    e.target.value = '';
  };

  const onDataFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) void handleDataFile(f);
    e.target.value = '';
  };

  const toggleChecked = (id: string) => {
    dispatch({ type: 'toggleChecked', id });
  };

  const toggleAll = (checked: boolean) => {
    dispatch({ type: 'toggleAll', checked });
  };

  const removeItem = (id: string) => {
    dispatch({ type: 'removeItem', id });
  };

  const clearAll = () => {
    dispatch({ type: 'clearAll' });
  };

  const mergeToWatchlist = async () => {
    const toMerge = items.flatMap((i) => (i.checked && i.code ? [i.code] : []));
    if (toMerge.length === 0) return;
    const current = parseCurrentList();
    const merged = [...new Set([...current, ...toMerge])];
    const value = merged.join(',');

    dispatch({ type: 'mergeStarted' });
    try {
      await onMergeStockList(value);
      dispatch({ type: 'mergeSucceeded' });
    } catch (e) {
      if (e instanceof SystemConfigConflictError) {
        await onMergeStockList(value);
        dispatch({ type: 'mergeFailed', message: '配置已更新，请再次点击「合并到自选股」' });
      } else {
        dispatch({ type: 'mergeFailed', message: getApiErrorMessage(e, '合并保存失败') });
      }
    }
  };

  const { validCount, checkedCount } = items.reduce<{ validCount: number; checkedCount: number }>(
    (acc, i) => {
      if (i.code) {
        acc.validCount++;
        if (i.checked) acc.checkedCount++;
      }
      return acc;
    },
    { validCount: 0, checkedCount: 0 },
  );

  return (
    <div className="space-y-4">
      <div className="settings-surface-panel settings-border-strong rounded-xl border p-4 shadow-soft-card">
        <p className="text-sm font-medium text-foreground">支持图片、CSV/Excel 文件与剪贴板文本</p>
        <p className="mt-1 text-xs leading-5 text-secondary-text">
          图片识别需预先配置 Vision 模型。建议先人工核对解析结果，再合并到自选股。
        </p>
      </div>

      <div
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); dispatch({ type: 'setDragging', value: true }); }}
        onDragLeave={(e) => { e.preventDefault(); dispatch({ type: 'setDragging', value: false }); }}
        className={`flex min-h-[96px] flex-col gap-4 rounded-xl border border-dashed  p-4 transition-colors ${
          isDragging ? 'settings-drag-active' : 'settings-border-overlay settings-surface-overlay'
        } ${disabled || isLoading ? 'cursor-not-allowed opacity-60' : ''}`}
      >
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="settings-secondary"
            disabled={disabled || isLoading}
            onClick={() => imageInputRef.current?.click()}
          >
            选择图片
          </Button>
          <input
            ref={imageInputRef}
            type="file"
            accept=".jpg,.jpeg,.png,.webp,.gif"
            className="hidden"
            onChange={onImageInput}
            disabled={disabled || isLoading}
            aria-label="选择图片"
          />
          <Button
            type="button"
            variant="settings-secondary"
            disabled={disabled || isLoading}
            onClick={() => dataInputRef.current?.click()}
          >
            选择文件
          </Button>
          <input
            ref={dataInputRef}
            type="file"
            accept=".csv,.xlsx,.txt"
            className="hidden"
            onChange={onDataFileInput}
            disabled={disabled || isLoading}
            aria-label="选择文件"
          />
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <textarea
            placeholder="或粘贴 CSV/Excel 复制的文本..."
            aria-label="粘贴文本"
            className="input-surface settings-surface-strong settings-border-strong min-h-[72px] w-full rounded-xl border px-3 py-2 text-sm text-foreground shadow-soft-card transition-colors placeholder:text-muted-text focus:outline-none"
            value={pasteText}
            onChange={(e) => dispatch({ type: 'setPasteText', value: e.target.value })}
            disabled={disabled || isLoading}
          />
          <Button
            type="button"
            variant="settings-secondary"
            className="shrink-0 sm:self-start"
            onClick={handlePasteParse}
            disabled={disabled || isLoading || !pasteText.trim()}
          >
            解析
          </Button>
        </div>
      </div>

      {isLoading ? (
        <SupportPanel
          title="处理中..."
          body="正在解析文件或识别图片，请保持当前页面不要关闭。"
          className="rounded-xl"
        />
      ) : null}
      {error && (
        <SupportBanner tone="danger" title="导入失败" body={error} role="alert" />
      )}

      {items.length > 0 && (
        <div className="space-y-2">
          <SupportBanner
            tone="warning"
            title="建议逐条核对后再合并"
            body="高置信度默认勾选，中低置信度需手动确认，避免误把识别结果写入自选股。"
          />
          <div className="flex items-center justify-between">
            <span className="text-xs text-secondary-text">
              共 {validCount} 条可合并，已勾选 {checkedCount} 条
            </span>
            <div className="flex gap-2">
              <button type="button" className="text-xs text-secondary-text transition-colors hover:text-foreground" onClick={() => toggleAll(true)}>
                全选
              </button>
              <button type="button" className="text-xs text-secondary-text transition-colors hover:text-foreground" onClick={() => toggleAll(false)}>
                取消
              </button>
              <button type="button" className="text-xs text-secondary-text transition-colors hover:text-foreground" onClick={clearAll}>
                清空
              </button>
            </div>
          </div>
          <div className="max-h-[220px] space-y-1 overflow-y-auto no-scrollbar rounded-xl border settings-border-soft settings-surface-overlay-soft p-2">
            {items.map((it) => {
              const confidence = normalizeConfidence(it.confidence);
              const confidenceMeta = getConfidenceMeta(confidence);

              return (
                <div
                  key={it.id}
                  className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm ${
                    it.code ? 'border-border/40 bg-elevated/62' : 'border-danger/25 bg-danger/10'
                  }`}
                >
                  <input
                    type="checkbox"
                    className="settings-input-checkbox size-4 rounded border-border/70 bg-base"
                    checked={it.checked}
                    onChange={() => toggleChecked(it.id)}
                    disabled={!it.code || disabled}
                    aria-label={it.code || '解析失败'}
                  />
                  <span className={it.code ? 'font-medium text-foreground' : 'font-medium text-danger'}>
                    {it.code || '解析失败'}
                  </span>
                  {it.name && <span className="text-secondary-text">({it.name})</span>}
                  <div className="ml-auto flex items-center gap-2">
                    <Badge variant={confidenceMeta.badge} size="sm">
                      {confidenceMeta.label}
                    </Badge>
                    <button
                      type="button"
                      className="text-secondary-text transition-colors hover:text-foreground"
                      onClick={() => removeItem(it.id)}
                      disabled={disabled}
                    >
                      ×
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          <Button
            type="button"
            variant="settings-primary"
            className="mt-2"
            onClick={() => void mergeToWatchlist()}
            disabled={disabled || isMerging || checkedCount === 0}
          >
            {isMerging ? '保存中...' : '合并到自选股'}
          </Button>
        </div>
      )}
    </div>
  );
};
