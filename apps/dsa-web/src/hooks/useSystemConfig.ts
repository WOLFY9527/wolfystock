import { useEffect, useRef, useState } from 'react';
import { createParsedApiError, getParsedApiError, type ParsedApiError } from '../api/error';
import { systemConfigApi, SystemConfigConflictError, SystemConfigValidationError } from '../api/systemConfig';
import type {
  ConfigValidationIssue,
  SystemConfigCategorySchema,
  SystemConfigItem,
  SystemConfigUpdateItem,
} from '../types/systemConfig';

type ToastState = {
  type: 'success';
  message: string;
} | {
  type: 'error';
  error: ParsedApiError;
} | null;

type RetryAction = 'load' | 'save' | null;

type SaveResult = {
  success: boolean;
  message?: string;
  issues?: ConfigValidationIssue[];
};

type PersistSaveOptions = {
  validateBeforeSave: boolean;
  preserveDirty: boolean;
  successMessage: string;
};

const CATEGORY_DISPLAY_ORDER: Record<string, number> = {
  base: 10,
  ai_model: 20,
  data_source: 30,
  notification: 40,
  system: 50,
  agent: 55,
  backtest: 60,
  uncategorized: 99,
};

const SENSITIVE_KEY_PATTERN = /(api_?key|apikey|access_?token|refresh_?token|token|authorization|bearer|credential|private_?key|secret|password)/i;

function maskSecretForDisplay(value: string): string {
  const secret = String(value || '').trim();
  if (!secret) return '';
  if (/^sk-/i.test(secret) && secret.length > 7) return `sk-...${secret.slice(-4)}`;
  if (secret.includes('...') || secret === '***' || secret === '已配置') return secret;
  if (secret.length <= 8) return '已配置';
  return `${secret.slice(0, 4)}...${secret.slice(-4)}`;
}

function sanitizeConfigItems(items: SystemConfigItem[]): SystemConfigItem[] {
  return items.map((item) => {
    const isSensitive = Boolean(item.schema?.isSensitive) || SENSITIVE_KEY_PATTERN.test(item.key);
    if (!isSensitive || !item.value) {
      return item;
    }
    return {
      ...item,
      value: maskSecretForDisplay(item.value),
      isMasked: true,
    };
  });
}

function sortItemsByOrder(items: SystemConfigItem[]): SystemConfigItem[] {
  return [...items].sort((a, b) => {
    const left = a.schema?.displayOrder ?? 9999;
    const right = b.schema?.displayOrder ?? 9999;
    if (left !== right) {
      return left - right;
    }
    return a.key.localeCompare(b.key);
  });
}

function isMultiValueSchema(schema: SystemConfigItem['schema'] | undefined): boolean {
  const validation = (schema?.validation ?? {}) as Record<string, unknown>;
  return Boolean(validation.multiValue ?? validation.multi_value);
}

function normalizeFieldValue(value: string, schema: SystemConfigItem['schema'] | undefined): string {
  if (!isMultiValueSchema(schema)) {
    return value;
  }

  return value
    .split(',')
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0)
    .join(',');
}

export function useSystemConfig() {
  // Server state
  const [configVersion, setConfigVersion] = useState<string>('');
  const [maskToken, setMaskToken] = useState<string>('******');
  const [serverItems, setServerItems] = useState<SystemConfigItem[]>([]);

  // UI state
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});
  const [activeCategory, setActiveCategory] = useState<string>('base');
  const [validationIssues, setValidationIssues] = useState<ConfigValidationIssue[]>([]);
  const [toast, setToast] = useState<ToastState>(null);

  // Request state
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [loadError, setLoadError] = useState<ParsedApiError | null>(null);
  const [saveError, setSaveError] = useState<ParsedApiError | null>(null);
  const [retryAction, setRetryAction] = useState<RetryAction>(null);
  const serverItemByKeyRef = useRef<Record<string, SystemConfigItem>>({});

  // Legacy unlock state is kept as always-open compatibility so system settings
  // can rely on authenticated admin identity instead of a second page-level gate.
  const adminUnlockToken = null;
  const adminUnlockExpiresAt = null;
  const isAdminUnlocked = true;

  const mergedItems = sortItemsByOrder(
    serverItems.map((item) => ({
      ...item,
      value: draftValues[item.key] ?? item.value,
    })),
  );

  const serverItemByKey = (() => {
    const map: Record<string, SystemConfigItem> = {};
    for (const item of serverItems) {
      map[item.key] = item;
    }
    return map;
  })();

  useEffect(() => {
    serverItemByKeyRef.current = serverItemByKey;
  }, [serverItemByKey]);

  const categories: SystemConfigCategorySchema[] = (() => {
    // Infer tabs from loaded config item schema metadata.
    const categoryMap = new Map<string, SystemConfigCategorySchema>();
    for (const item of mergedItems) {
      if (!item.schema) {
        continue;
      }

      const category = item.schema.category;
      if (!categoryMap.has(category)) {
        categoryMap.set(category, {
          category,
          title: category.replace('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase()),
          description: '',
          displayOrder: CATEGORY_DISPLAY_ORDER[category] ?? 999,
          fields: [],
        });
      }
      categoryMap.get(category)?.fields.push(item.schema);
    }

    return [...categoryMap.values()].sort((a, b) => a.displayOrder - b.displayOrder);
  })();

  const itemsByCategory = (() => {
    const map: Record<string, SystemConfigItem[]> = {};
    for (const item of mergedItems) {
      const category = item.schema?.category ?? 'uncategorized';
      if (!map[category]) {
        map[category] = [];
      }
      map[category].push(item);
    }
    return map;
  })();

  const dirtyKeys = (() => {
    const keys: string[] = [];
    for (const item of serverItems) {
      const draftRaw = draftValues[item.key];
      if (draftRaw === undefined) {
        continue;
      }

      const normalizedDraft = normalizeFieldValue(draftRaw, item.schema);
      const normalizedCurrent = normalizeFieldValue(item.value, item.schema);
      if (normalizedDraft !== normalizedCurrent) {
        keys.push(item.key);
      }
    }
    return keys;
  })();

  const hasDirty = dirtyKeys.length > 0;

  const issueByKey = (() => {
    const map: Record<string, ConfigValidationIssue[]> = {};
    for (const issue of validationIssues) {
      if (!map[issue.key]) {
        map[issue.key] = [];
      }
      map[issue.key].push(issue);
    }
    return map;
  })();

  const applyServerPayload = (
    items: SystemConfigItem[],
    version: string,
    token: string,
    options?: { preserveDirty?: boolean; committedKeys?: string[] },
  ) => {
    const sorted = sortItemsByOrder(sanitizeConfigItems(items));
    const previousServerMap = serverItemByKeyRef.current;
    const committedKeys = new Set(options?.committedKeys ?? []);
    const preserveDirty = options?.preserveDirty ?? false;

    setServerItems(sorted);
    setConfigVersion(version);
    setMaskToken(token || '******');

    setDraftValues((prevDraft) => {
      const nextDraft: Record<string, string> = {};
      for (const item of sorted) {
        if (committedKeys.has(item.key)) {
          nextDraft[item.key] = item.value;
          continue;
        }

        if (preserveDirty) {
          const previousServerValue = previousServerMap[item.key]?.value;
          const hasDraft = prevDraft[item.key] !== undefined;
          const wasDirty = hasDraft && prevDraft[item.key] !== previousServerValue;
          nextDraft[item.key] = wasDirty ? prevDraft[item.key] : item.value;
          continue;
        }

        nextDraft[item.key] = item.value;
      }
      return nextDraft;
    });

    const defaultCategory = sorted[0]?.schema?.category || 'base';
    setActiveCategory((current) => {
      const exists = sorted.some((item) => item.schema?.category === current);
      return exists ? current : defaultCategory;
    });
    setValidationIssues([]);
  };

  const load = async () => {
    setIsLoading(true);
    setLoadError(null);
    setRetryAction(null);

    try {
      const config = await systemConfigApi.getConfig(true);
      applyServerPayload(config.items, config.configVersion, config.maskToken);
      setToast(null);
    } catch (error: unknown) {
      setLoadError(getParsedApiError(error));
      setRetryAction('load');
    }
    setIsLoading(false);
  };

  const resetDraft = () => {
    const next: Record<string, string> = {};
    for (const item of serverItems) {
      next[item.key] = item.value;
    }
    setDraftValues(next);
    setValidationIssues([]);
    setSaveError(null);
  };

  const applyPartialUpdate = (updatedItems: Array<{ key: string; value: string }>) => {
    setDraftValues((prevDraft) => {
      const nextDraft = { ...prevDraft };
      for (const item of updatedItems) {
        nextDraft[item.key] = item.value;
      }
      return nextDraft;
    });
  };

  const setDraftValue = (key: string, value: string) => {
    setDraftValues((previous) => ({
      ...previous,
      [key]: value,
    }));
  };

  const getChangedItems = (): SystemConfigUpdateItem[] => {
    return dirtyKeys.reduce<SystemConfigUpdateItem[]>((acc, key) => {
      const serverItem = serverItemByKey[key];
      const normalizedValue = normalizeFieldValue(draftValues[key] ?? '', serverItem?.schema);
      const normalizedCurrent = normalizeFieldValue(serverItem?.value ?? '', serverItem?.schema);
      if (normalizedValue !== normalizedCurrent) {
        acc.push({ key, value: normalizedValue });
      }
      return acc;
    }, []);
  };

  const setAdminUnlockSession = (token: string, expiresAt: number) => {
    void token;
    void expiresAt;
  };

  const clearAdminUnlockSession = () => {};

  const persistItems = async (
    changedItems: SystemConfigUpdateItem[],
    options: PersistSaveOptions,
  ): Promise<void> => {
    if (!changedItems.length) {
      return;
    }

    if (options.validateBeforeSave) {
      const validateResult = await systemConfigApi.validate({ items: changedItems });
      setValidationIssues(validateResult.issues || []);

      if (!validateResult.valid) {
        throw createParsedApiError({
          title: '配置校验未通过',
          message: '请先修正表单错误后再保存。',
          rawMessage: '配置校验未通过，请先修正表单错误。',
          category: 'http_error',
        });
      }
    }

    const updateResult = await systemConfigApi.update({
      configVersion,
      maskToken,
      reloadNow: true,
      items: changedItems,
    });

    const refreshed = await systemConfigApi.getConfig(true);
    applyServerPayload(refreshed.items, refreshed.configVersion, refreshed.maskToken, {
      preserveDirty: options.preserveDirty,
      committedKeys: changedItems.map((item) => item.key),
    });

    const warningText = updateResult.warnings?.length
      ? `；警告：${updateResult.warnings.join('；')}`
      : '';
    setToast({ type: 'success', message: `${options.successMessage}${warningText}` });
  };

  const handleSaveFailure = (error: unknown, setRetryOnFailure: boolean) => {
    if (error instanceof SystemConfigValidationError) {
      setValidationIssues(error.issues);
      setSaveError(error.parsedError);
    } else if (error instanceof SystemConfigConflictError) {
      setSaveError(createParsedApiError({
        title: '配置版本冲突',
        message: `${error.message}，请先重新加载配置。`,
        rawMessage: error.parsedError.rawMessage,
        status: error.parsedError.status,
        category: error.parsedError.category,
      }));
    } else {
      setSaveError(getParsedApiError(error));
    }

    setToast({ type: 'error', error: getParsedApiError(error) });
    if (setRetryOnFailure) {
      setRetryAction('save');
    }
  };

  const save = async (): Promise<SaveResult> => {
    if (!hasDirty) {
      setToast({ type: 'success', message: '当前没有可保存的修改。' });
      return { success: true, message: '当前没有可保存的修改' };
    }

    setIsSaving(true);
    setSaveError(null);
    setRetryAction(null);

    const changedItems = getChangedItems();

    let result: SaveResult;
    try {
      await persistItems(changedItems, {
        validateBeforeSave: true,
        preserveDirty: false,
        successMessage: '配置已更新',
      });
      result = { success: true };
    } catch (error: unknown) {
      handleSaveFailure(error, true);
      result = { success: false, message: '保存失败' };
    }
    setIsSaving(false);
    return result;
  };

  const saveExternalItems = async (
    changedItems: SystemConfigUpdateItem[],
    successMessage = '配置已更新',
  ) => {
    setIsSaving(true);
    setSaveError(null);

    try {
      await persistItems(changedItems, {
        validateBeforeSave: false,
        preserveDirty: true,
        successMessage,
      });
    } catch (error: unknown) {
      handleSaveFailure(error, false);
      setIsSaving(false);
      throw error;
    }
    setIsSaving(false);
  };

  const retry = async () => {
    if (retryAction === 'load') {
      await load();
      return;
    }
    if (retryAction === 'save') {
      await save();
    }
  };

  const clearToast = () => {
    setToast(null);
  };

  return {
    // Server state
    configVersion,
    maskToken,
    serverItems,
    categories,
    itemsByCategory,
    issueByKey,

    // Unlock state
    adminUnlockToken,
    adminUnlockExpiresAt,
    isAdminUnlocked,

    // UI state
    activeCategory,
    setActiveCategory,
    hasDirty,
    dirtyCount: dirtyKeys.length,
    toast,
    clearToast,

    // Request state
    isLoading,
    isSaving,
    loadError,
    saveError,
    retryAction,

    // Actions
    load,
    retry,
    save,
    saveExternalItems,
    resetDraft,
    setDraftValue,
    applyPartialUpdate,
    setAdminUnlockSession,
    clearAdminUnlockSession,
  };
}
