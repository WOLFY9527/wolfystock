import { useCallback, useEffect, useMemo, useState } from 'react';
import { getApiErrorMessage, getParsedApiError } from '../../api/error';
import { systemConfigApi } from '../../api/systemConfig';
import {
  CUSTOM_DATA_SOURCE_LIBRARY_KEY,
  createEmptyCustomDataSource,
  DATA_SOURCE_CAPABILITY_LABEL_KEYS,
  DATA_SOURCE_LIBRARY_ITEMS,
  DATA_SOURCE_ROUTING_CAPABILITY_MAP,
  makeUniqueDataSourceId,
  parseCustomDataSourceLibrary,
  serializeCustomDataSourceLibrary,
  validateCustomDataSource,
  type BuiltinDataSourceValidationResult,
  type CustomDataSourceRecord,
  type DataSourceEditorMode,
  type DataSourceLibraryEntry,
  type DataRouteKey,
  type DataSourceValidationState,
  type TranslateFn,
} from './dataSourceLibraryShared';

type AllItemMap = Map<string, string>;
type DataSummary = Record<DataRouteKey, string[]>;
type SaveExternalItems = (items: Array<{ key: string; value: string }>, successMessage: string) => Promise<void>;

type UseDataSourceLibraryControllerArgs = {
  allItemMap: AllItemMap;
  dataSummary: DataSummary;
  dataPriorityKeys: Record<DataRouteKey, string>;
  saveExternalItems: SaveExternalItems;
  onDeleteSourceFromRoutes: (sourceId: string) => void;
  prettySourceLabel: (value: string) => string;
  t: TranslateFn;
};

const hasConfigValue = (value: string): boolean => String(value || '').trim().length > 0;
const splitCsv = (value?: string): string[] => (value || '')
  .split(',')
  .map((item) => item.trim())
  .filter(Boolean);
const builtinValidationSymbol = (sourceId: string): string => (sourceId === 'twelve_data' ? 'HK00700' : 'MSFT');
const uniqueValues = (values: Array<string | null | undefined>): string[] => {
  const next: string[] = [];
  values.forEach((value) => {
    const normalized = String(value || '').trim();
    if (!normalized || next.includes(normalized)) {
      return;
    }
    next.push(normalized);
  });
  return next;
};

export function useDataSourceLibraryController({
  allItemMap,
  dataSummary,
  dataPriorityKeys,
  saveExternalItems,
  onDeleteSourceFromRoutes,
  prettySourceLabel,
  t,
}: UseDataSourceLibraryControllerArgs) {
  const [dataSourceValidationStatus, setDataSourceValidationStatus] = useState<Record<string, DataSourceValidationState>>({});
  const [builtinDataSourceValidationResults, setBuiltinDataSourceValidationResults] = useState<Record<string, BuiltinDataSourceValidationResult>>({});
  const customDataSourceLibrary = useMemo(
    () => parseCustomDataSourceLibrary(allItemMap.get(CUSTOM_DATA_SOURCE_LIBRARY_KEY) || ''),
    [allItemMap],
  );
  const [customDataSourceLibraryDraft, setCustomDataSourceLibraryDraft] = useState<CustomDataSourceRecord[]>(customDataSourceLibrary);
  useEffect(() => {
    setCustomDataSourceLibraryDraft(customDataSourceLibrary);
  }, [customDataSourceLibrary]);

  const dataSourceLibrary = useMemo<DataSourceLibraryEntry[]>(() => {
    const hasCredential = (patterns: RegExp[]): boolean => {
      if (!patterns.length) {
        return false;
      }
      for (const [key, value] of allItemMap.entries()) {
        if (!hasConfigValue(value)) {
          continue;
        }
        if (patterns.some((pattern) => pattern.test(key))) {
          return true;
        }
      }
      return false;
    };

    const builtInEntries = DATA_SOURCE_LIBRARY_ITEMS.map((source) => {
      const credentialValue = hasCredential(source.credentialPatterns) ? 'configured' : '';
      const configured = source.requireCredential ? Boolean(credentialValue) : true;
      const runtimeValidation = dataSourceValidationStatus[source.key];
      const remoteValidation = builtinDataSourceValidationResults[source.key];
      const validationState = runtimeValidation || (
        source.builtin && !source.requireCredential
          ? 'builtin'
          : configured
            ? 'configured_pending'
            : 'not_configured'
      );
      const capabilityLabels = source.capabilityKeys.map((capability) => t(DATA_SOURCE_CAPABILITY_LABEL_KEYS[capability]));
      const routeUsage = source.routeKeys.filter((routeKey) => dataSummary[routeKey].includes(source.key));
      const usable = source.builtin && !source.requireCredential
        ? true
        : configured && validationState !== 'failed';
      return {
        key: source.key,
        label: prettySourceLabel(source.key),
        kind: 'builtin' as const,
        builtin: true,
        baseUrl: '',
        configured,
        usable,
        validationState,
        validationMessage: validationState === 'builtin'
          ? t('settings.dataSourceValidationBuiltin')
          : validationState === 'loading'
            ? t('settings.dataSourceValidationChecking')
            : validationState === 'partial'
              ? (remoteValidation?.summary || t('settings.dataSourceValidationPartial'))
              : validationState === 'missing_key'
                ? (remoteValidation?.summary || t('settings.dataSourceValidationMissing'))
                : validationState === 'unsupported'
                  ? (remoteValidation?.summary || t('settings.dataSourceValidationUnsupported'))
                  : validationState === 'validated'
                    ? (remoteValidation?.summary || t('settings.dataSourceValidationRemoteSuccess'))
                    : validationState === 'failed'
                      ? (remoteValidation?.summary || t('settings.dataSourceValidationRemoteFailed'))
                      : validationState === 'configured_pending'
                        ? t('settings.dataSourceValidationConfiguredOnly')
                        : t('settings.dataSourceValidationMissing'),
        routeUsage,
        capabilityKeys: source.capabilityKeys,
        capabilityLabels,
        description: source.management
          ? t('settings.dataSourceCredentialDesc')
          : t('settings.dataSourceBuiltinDesc'),
        credentialRequired: Boolean(source.requireCredential),
        credentialValue,
        credentialSchema: source.credentialSchema || 'none',
        management: source.management,
      } satisfies DataSourceLibraryEntry;
    });

    const customEntries = customDataSourceLibraryDraft.map((record) => {
      const normalizedValidation = record.validation?.status || 'pending';
      const localValidation = dataSourceValidationStatus[record.id];
      const validationState = localValidation || normalizedValidation;
      const configured = Boolean(
        record.name.trim()
        && record.credential.trim()
        && (record.credentialSchema !== 'key_secret' || record.secret.trim())
        && record.capabilities.length,
      );
      const capabilityLabels = record.capabilities.map((capability) => t(DATA_SOURCE_CAPABILITY_LABEL_KEYS[capability]));
      const routeUsage = record.capabilities.reduce<DataRouteKey[]>((acc, capability) => {
        const routeKey = DATA_SOURCE_ROUTING_CAPABILITY_MAP[capability];
        if (routeKey && dataSummary[routeKey].includes(record.id)) {
          acc.push(routeKey);
        }
        return acc;
      }, []);
      const usable = configured && validationState !== 'failed';
      return {
        key: record.id,
        label: record.name,
        kind: 'custom' as const,
        builtin: false,
        baseUrl: record.baseUrl,
        configured,
        usable,
        validationState: validationState === 'validated' && configured
          ? 'validated'
          : validationState === 'failed'
            ? 'failed'
            : configured
              ? 'configured_pending'
              : 'not_configured',
        validationMessage: validationState === 'validated'
          ? t('settings.dataSourceValidationLocalSuccess')
          : validationState === 'failed'
            ? (record.validation?.message || t('settings.dataSourceValidationLocalFailed'))
            : configured
              ? t('settings.dataSourceValidationConfiguredOnly')
              : t('settings.dataSourceValidationMissing'),
        routeUsage,
        capabilityKeys: record.capabilities,
        capabilityLabels,
        description: record.description || t('settings.dataSourceCustomDesc'),
        credentialRequired: true,
        credentialValue: record.credential,
        credentialSchema: record.credentialSchema,
        customRecord: record,
      } satisfies DataSourceLibraryEntry;
    });

    return [...builtInEntries, ...customEntries];
  }, [allItemMap, builtinDataSourceValidationResults, customDataSourceLibraryDraft, dataSourceValidationStatus, dataSummary, prettySourceLabel, t]);

  const dataSourceRouteOptions = useMemo(() => {
    const grouped: Record<DataRouteKey, string[]> = {
      market: [],
      fundamentals: [],
      news: [],
      sentiment: [],
    };

    dataSourceLibrary.forEach((source) => {
      if (!source.usable) {
        return;
      }
      source.capabilityKeys.forEach((capability) => {
        const routeKey = DATA_SOURCE_ROUTING_CAPABILITY_MAP[capability];
        if (!routeKey) {
          return;
        }
        if (!grouped[routeKey].includes(source.key)) {
          grouped[routeKey].push(source.key);
        }
      });
    });

    return grouped;
  }, [dataSourceLibrary]);

  const dataSourceLibraryMap = useMemo(
    () => new Map<string, DataSourceLibraryEntry>(dataSourceLibrary.map((entry) => [entry.key, entry])),
    [dataSourceLibrary],
  );

  const [dataSourceLibraryDrawerOpen, setDataSourceLibraryDrawerOpen] = useState(false);
  const [dataSourceEditorId, setDataSourceEditorId] = useState<string | null>(null);
  const [dataSourceEditorDraft, setDataSourceEditorDraft] = useState<CustomDataSourceRecord>(createEmptyCustomDataSource());
  const [managedBuiltinDataSourceDraft, setManagedBuiltinDataSourceDraft] = useState({
    credential: '',
    secret: '',
    extraValue: '',
  });
  const [dataSourceDeleteTargetId, setDataSourceDeleteTargetId] = useState<string | null>(null);

  const dataSourceEditorEntry = useMemo(
    () => (dataSourceEditorId && dataSourceEditorId !== 'new'
      ? dataSourceLibraryMap.get(dataSourceEditorId) || null
      : null),
    [dataSourceEditorId, dataSourceLibraryMap],
  );
  const dataSourceDeleteTarget = useMemo(
    () => (dataSourceDeleteTargetId ? dataSourceLibraryMap.get(dataSourceDeleteTargetId) || null : null),
    [dataSourceDeleteTargetId, dataSourceLibraryMap],
  );

  const openCreateDataSourceDrawer = useCallback(() => {
    setDataSourceEditorId('new');
    setDataSourceEditorDraft(createEmptyCustomDataSource());
    setDataSourceLibraryDrawerOpen(true);
  }, []);

  const openEditDataSourceDrawer = useCallback((sourceId: string) => {
    setDataSourceEditorId(sourceId);
    setDataSourceLibraryDrawerOpen(true);
  }, []);

  const closeDataSourceDrawer = useCallback(() => {
    setDataSourceLibraryDrawerOpen(false);
    setDataSourceEditorId(null);
  }, []);

  const saveDataSourceEditor = useCallback(async () => {
    if (dataSourceEditorEntry?.management) {
      const { management } = dataSourceEditorEntry;
      const requiresCredential = management.credentialSchema !== 'none';
      const missingCredential = requiresCredential && !managedBuiltinDataSourceDraft.credential.trim();
      const missingSecret = management.credentialSchema === 'key_secret' && !managedBuiltinDataSourceDraft.secret.trim();
      const message = missingCredential
        ? t('settings.dataSourceValidationMissingCredential')
        : missingSecret
          ? t('settings.dataSourceValidationMissingSecret')
          : '';
      if (message) {
        setDataSourceValidationStatus((prev) => ({
          ...prev,
          [dataSourceEditorEntry.key]: 'failed',
        }));
        return;
      }

      const credentialValue = managedBuiltinDataSourceDraft.credential.trim();
      const saveToPlural = Boolean(management.pluralCredentialEnvKey && credentialValue.includes(','));
      const updatedItems: Array<{ key: string; value: string }> = [];
      if (management.credentialEnvKey) {
        updatedItems.push({ key: management.credentialEnvKey, value: saveToPlural ? '' : credentialValue });
      }
      if (management.pluralCredentialEnvKey) {
        updatedItems.push({
          key: management.pluralCredentialEnvKey,
          value: saveToPlural ? credentialValue : '',
        });
      }
      if (management.secretEnvKey) {
        updatedItems.push({
          key: management.secretEnvKey,
          value: managedBuiltinDataSourceDraft.secret.trim(),
        });
      }
      if (management.extraField) {
        updatedItems.push({
          key: management.extraField.envKey,
          value: managedBuiltinDataSourceDraft.extraValue.trim() || management.extraField.defaultValue,
        });
      }

      setDataSourceValidationStatus((prev) => ({
        ...prev,
        [dataSourceEditorEntry.key]: 'configured_pending',
      }));
      await saveExternalItems(updatedItems, t('settings.dataSourceSaved'));
      return;
    }

    const validation = validateCustomDataSource(dataSourceEditorDraft);
    if (!validation.valid) {
      const message = validation.issue === 'name'
        ? t('settings.dataSourceValidationMissingName')
        : validation.issue === 'credential'
          ? t('settings.dataSourceValidationMissingCredential')
          : validation.issue === 'secret'
            ? t('settings.dataSourceValidationMissingSecret')
            : validation.issue === 'capabilities'
              ? t('settings.dataSourceValidationMissingCapabilities')
              : t('settings.dataSourceValidationInvalidBaseUrl');
      setDataSourceValidationStatus((prev) => ({
        ...prev,
        [dataSourceEditorDraft.id || 'new']: 'failed',
      }));
      setDataSourceEditorDraft((prev) => ({
        ...prev,
        validation: { status: 'failed', message },
      }));
      return;
    }

    const currentId = dataSourceEditorId && dataSourceEditorId !== 'new'
      ? dataSourceEditorId
      : dataSourceEditorDraft.id || '';
    const finalId = dataSourceEditorId === 'new'
      ? makeUniqueDataSourceId(dataSourceEditorDraft.name || currentId || 'custom_source', [
        ...dataSourceLibrary.map((source) => source.key),
        currentId,
      ])
      : currentId;
    const nextRecord: CustomDataSourceRecord = {
      id: finalId,
      name: dataSourceEditorDraft.name.trim(),
      credentialSchema: dataSourceEditorDraft.credentialSchema,
      credential: dataSourceEditorDraft.credential.trim(),
      secret: dataSourceEditorDraft.secret.trim(),
      baseUrl: dataSourceEditorDraft.baseUrl.trim(),
      description: dataSourceEditorDraft.description.trim(),
      capabilities: uniqueValues(dataSourceEditorDraft.capabilities).map((capability) => capability as typeof dataSourceEditorDraft.capabilities[number]),
      validation: { status: 'pending' },
    };
    const nextLibrary = dataSourceEditorId === 'new'
      ? [...customDataSourceLibraryDraft.filter((record) => record.id !== finalId), nextRecord]
      : customDataSourceLibraryDraft.map((record) => (record.id === currentId ? nextRecord : record));
    setCustomDataSourceLibraryDraft(nextLibrary);
    setDataSourceEditorId(finalId);
    setDataSourceValidationStatus((prev) => ({
      ...prev,
      [finalId]: 'configured_pending',
    }));
    setDataSourceEditorDraft((prev) => ({
      ...prev,
      id: finalId,
      validation: { status: 'pending' },
    }));
    await saveExternalItems([
      { key: CUSTOM_DATA_SOURCE_LIBRARY_KEY, value: serializeCustomDataSourceLibrary(nextLibrary) },
    ], t('settings.dataSourceSaved'));
  }, [customDataSourceLibraryDraft, dataSourceEditorDraft, dataSourceEditorEntry, dataSourceEditorId, dataSourceLibrary, managedBuiltinDataSourceDraft, saveExternalItems, t]);

  const deleteDataSourceEntry = useCallback(async () => {
    if (!dataSourceDeleteTargetId) {
      return;
    }

    const source = dataSourceLibraryMap.get(dataSourceDeleteTargetId);
    if (!source?.customRecord) {
      setDataSourceDeleteTargetId(null);
      return;
    }

    const nextLibrary = customDataSourceLibraryDraft.filter((record) => record.id !== dataSourceDeleteTargetId);
    const cleanupByConfigKey = new Map<string, string>();
    [
      dataPriorityKeys.market,
      dataPriorityKeys.fundamentals,
      dataPriorityKeys.news,
      dataPriorityKeys.sentiment,
    ].forEach((configKey) => {
      const currentRoute = splitCsv(allItemMap.get(configKey));
      if (!currentRoute.includes(dataSourceDeleteTargetId)) {
        return;
      }
      cleanupByConfigKey.set(
        configKey,
        currentRoute.filter((value) => value !== dataSourceDeleteTargetId).join(','),
      );
    });

    setCustomDataSourceLibraryDraft(nextLibrary);
    setDataSourceValidationStatus((prev) => {
      if (!(dataSourceDeleteTargetId in prev)) {
        return prev;
      }
      const nextStatus = { ...prev };
      delete nextStatus[dataSourceDeleteTargetId];
      return nextStatus;
    });
    onDeleteSourceFromRoutes(dataSourceDeleteTargetId);
    setDataSourceLibraryDrawerOpen(false);
    setDataSourceEditorId(null);
    setDataSourceDeleteTargetId(null);

    await saveExternalItems([
      { key: CUSTOM_DATA_SOURCE_LIBRARY_KEY, value: serializeCustomDataSourceLibrary(nextLibrary) },
      ...[...cleanupByConfigKey.entries()].map(([key, value]) => ({ key, value })),
    ], t('settings.dataSourceDeleted'));
  }, [
    allItemMap,
    customDataSourceLibraryDraft,
    dataPriorityKeys.fundamentals,
    dataPriorityKeys.market,
    dataPriorityKeys.news,
    dataPriorityKeys.sentiment,
    dataSourceDeleteTargetId,
    dataSourceLibraryMap,
    onDeleteSourceFromRoutes,
    saveExternalItems,
    t,
  ]);

  const validateDataSourceEntry = useCallback(async (sourceId: string) => {
    const source = dataSourceLibraryMap.get(sourceId);
    if (!source) {
      return;
    }
    if (source.kind === 'custom' && source.customRecord) {
      const validation = validateCustomDataSource(source.customRecord);
      if (!validation.valid) {
        const message = validation.issue === 'name'
          ? t('settings.dataSourceValidationMissingName')
          : validation.issue === 'credential'
            ? t('settings.dataSourceValidationMissingCredential')
            : validation.issue === 'secret'
              ? t('settings.dataSourceValidationMissingSecret')
              : validation.issue === 'capabilities'
                ? t('settings.dataSourceValidationMissingCapabilities')
                : t('settings.dataSourceValidationInvalidBaseUrl');
        const nextLibrary = customDataSourceLibraryDraft.map((record) => (
          record.id === sourceId
            ? { ...record, validation: { status: 'failed' as const, message } }
            : record
        ));
        setCustomDataSourceLibraryDraft(nextLibrary);
        setDataSourceValidationStatus((prev) => ({ ...prev, [sourceId]: 'failed' }));
        await saveExternalItems([
          { key: CUSTOM_DATA_SOURCE_LIBRARY_KEY, value: serializeCustomDataSourceLibrary(nextLibrary) },
        ], message);
        return;
      }

      const probe = await systemConfigApi.testCustomDataSource({
        name: source.customRecord.name,
        baseUrl: source.customRecord.baseUrl,
        credentialSchema: source.customRecord.credentialSchema,
        credential: source.customRecord.credential,
        secret: source.customRecord.secret,
        timeoutSeconds: 5,
      });
      const nextStatus: DataSourceValidationState = probe.success ? 'validated' : 'failed';
      const parsedProbeError = getApiErrorMessage({
        response: {
          status: probe.statusCode ?? 400,
          data: {
            error: probe.error,
            message: probe.message,
            statusCode: probe.statusCode,
            checkedUrl: probe.checkedUrl,
            latencyMs: probe.latencyMs,
          },
          statusText: probe.error || probe.message || undefined,
        },
      }, t('settings.dataSourceValidationConnectivityFailed'));
      const message = probe.success
        ? probe.message || t('settings.dataSourceValidationConnectivitySuccess')
        : parsedProbeError;
      const nextLibrary = customDataSourceLibraryDraft.map((record) => (
        record.id === sourceId
          ? {
            ...record,
            validation: probe.success
              ? { status: 'validated' as const, message }
              : { status: 'failed' as const, message },
          }
          : record
      ));
      setCustomDataSourceLibraryDraft(nextLibrary);
      setDataSourceValidationStatus((prev) => ({ ...prev, [sourceId]: nextStatus }));
      await saveExternalItems([
        { key: CUSTOM_DATA_SOURCE_LIBRARY_KEY, value: serializeCustomDataSourceLibrary(nextLibrary) },
      ], message);
      return;
    }

    if (source.management) {
      const sourceState = source.management.pluralCredentialEnvKey && hasConfigValue(allItemMap.get(source.management.pluralCredentialEnvKey) || '')
        ? String(allItemMap.get(source.management.pluralCredentialEnvKey) || '')
        : source.management.credentialEnvKey
          ? String(allItemMap.get(source.management.credentialEnvKey) || '')
          : '';
      const draftAppliesToSource = dataSourceEditorEntry?.key === sourceId;
      const credential = draftAppliesToSource && managedBuiltinDataSourceDraft.credential.trim()
        ? managedBuiltinDataSourceDraft.credential.trim()
        : sourceState.trim();
      const secret = draftAppliesToSource && managedBuiltinDataSourceDraft.secret.trim()
        ? managedBuiltinDataSourceDraft.secret.trim()
        : source.management.secretEnvKey
          ? String(allItemMap.get(source.management.secretEnvKey) || '').trim()
          : '';
      setDataSourceValidationStatus((prev) => ({ ...prev, [sourceId]: 'loading' }));
      try {
        const result = await systemConfigApi.testBuiltinDataSource({
          provider: sourceId,
          symbol: builtinValidationSymbol(sourceId),
          credential,
          secret,
          timeoutSeconds: 5,
        });
        const nextStatus: DataSourceValidationState = result.status === 'success'
          ? 'validated'
          : result.status;
        setBuiltinDataSourceValidationResults((prev) => ({ ...prev, [sourceId]: result }));
        setDataSourceValidationStatus((prev) => ({ ...prev, [sourceId]: nextStatus }));
      } catch (error: unknown) {
        const parsed = getParsedApiError(error);
        const failedResult: BuiltinDataSourceValidationResult = {
          provider: sourceId,
          ok: false,
          status: 'failed',
          checkedAt: new Date().toISOString(),
          durationMs: 0,
          keyMasked: null,
          checks: [],
          summary: parsed.message || t('settings.dataSourceValidationRemoteFailed'),
          suggestion: t('settings.dataSourceValidationRetrySuggestion'),
        };
        setBuiltinDataSourceValidationResults((prev) => ({ ...prev, [sourceId]: failedResult }));
        setDataSourceValidationStatus((prev) => ({ ...prev, [sourceId]: 'failed' }));
      }
      return;
    }

    if (source.kind === 'builtin') {
      setDataSourceValidationStatus((prev) => ({ ...prev, [sourceId]: 'loading' }));
      try {
        const result = await systemConfigApi.testBuiltinDataSource({
          provider: sourceId,
          symbol: builtinValidationSymbol(sourceId),
          timeoutSeconds: 5,
        });
        const nextStatus: DataSourceValidationState = result.status === 'success'
          ? 'validated'
          : result.status;
        setBuiltinDataSourceValidationResults((prev) => ({ ...prev, [sourceId]: result }));
        setDataSourceValidationStatus((prev) => ({ ...prev, [sourceId]: nextStatus }));
      } catch (error: unknown) {
        const parsed = getParsedApiError(error);
        setBuiltinDataSourceValidationResults((prev) => ({
          ...prev,
          [sourceId]: {
            provider: sourceId,
            ok: false,
            status: 'failed',
            checkedAt: new Date().toISOString(),
            durationMs: 0,
            keyMasked: null,
            checks: [],
            summary: parsed.message || t('settings.dataSourceValidationRemoteFailed'),
            suggestion: t('settings.dataSourceValidationRetrySuggestion'),
          },
        }));
        setDataSourceValidationStatus((prev) => ({ ...prev, [sourceId]: 'failed' }));
      }
      return;
    }

    const nextStatus: DataSourceValidationState = source.usable ? 'validated' : 'failed';
    setDataSourceValidationStatus((prev) => ({ ...prev, [sourceId]: nextStatus }));
  }, [allItemMap, customDataSourceLibraryDraft, dataSourceEditorEntry?.key, dataSourceLibraryMap, managedBuiltinDataSourceDraft.credential, managedBuiltinDataSourceDraft.secret, saveExternalItems, t]);

  const managedBuiltinSourceState = useMemo(() => {
    if (!dataSourceEditorEntry?.management) {
      return null;
    }
    const { management } = dataSourceEditorEntry;
    const credentialValue = management.pluralCredentialEnvKey && hasConfigValue(allItemMap.get(management.pluralCredentialEnvKey) || '')
      ? String(allItemMap.get(management.pluralCredentialEnvKey) || '')
      : management.credentialEnvKey
        ? String(allItemMap.get(management.credentialEnvKey) || '')
        : '';
    const secretValue = management.secretEnvKey
      ? String(allItemMap.get(management.secretEnvKey) || '')
      : '';
    const extraValue = management.extraField
      ? String(allItemMap.get(management.extraField.envKey) || management.extraField.defaultValue || '')
      : '';
    return {
      credential: credentialValue,
      secret: secretValue,
      extraValue,
    };
  }, [allItemMap, dataSourceEditorEntry]);

  const dataSourceEditorMode: DataSourceEditorMode = dataSourceEditorId === 'new'
    ? 'create'
    : dataSourceEditorEntry?.builtin && !dataSourceEditorEntry.management
      ? 'view'
      : dataSourceEditorEntry?.builtin
        ? 'manage_builtin'
        : 'edit';
  const dataSourceEditorValidationResult = dataSourceEditorEntry
    ? builtinDataSourceValidationResults[dataSourceEditorEntry.key]
    : undefined;

  useEffect(() => {
    if (!dataSourceLibraryDrawerOpen) {
      return;
    }
    if (dataSourceEditorId === 'new') {
      setDataSourceEditorDraft(createEmptyCustomDataSource());
      return;
    }
    if (dataSourceEditorEntry?.customRecord) {
      setDataSourceEditorDraft(dataSourceEditorEntry.customRecord);
      return;
    }
    if (managedBuiltinSourceState) {
      setManagedBuiltinDataSourceDraft(managedBuiltinSourceState);
      return;
    }
    if (dataSourceEditorEntry?.builtin) {
      setDataSourceEditorDraft(createEmptyCustomDataSource());
    }
  }, [dataSourceEditorEntry, dataSourceEditorId, dataSourceLibraryDrawerOpen, managedBuiltinSourceState]);

  return {
    dataSourceDeleteTarget,
    dataSourceEditorDraft,
    dataSourceEditorEntry,
    dataSourceEditorMode,
    dataSourceEditorValidationResult,
    dataSourceLibrary,
    dataSourceLibraryDrawerOpen,
    dataSourceRouteOptions,
    managedBuiltinDataSourceDraft,
    closeDataSourceDrawer,
    deleteDataSourceEntry,
    openCreateDataSourceDrawer,
    openEditDataSourceDrawer,
    saveDataSourceEditor,
    setDataSourceDeleteTargetId,
    setDataSourceEditorDraft,
    setManagedBuiltinDataSourceDraft,
    validateDataSourceEntry,
  };
}
