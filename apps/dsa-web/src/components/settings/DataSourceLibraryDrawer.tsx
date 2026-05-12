import type React from 'react';
import { Button, ConfirmDialog, Drawer, Input, Select } from '../common';
import { formatDateTime, formatDurationMs } from '../../utils/format';
import {
  DATA_SOURCE_CAPABILITY_LABEL_KEYS,
  DATA_SOURCE_CAPABILITY_OPTIONS,
  DATA_SOURCE_CUSTOM_SCHEMA_OPTIONS,
  formatDataSourceCheckLine,
  type BuiltinDataSourceValidationResult,
  type CustomDataSourceRecord,
  type DataSourceEditorMode,
  type DataSourceLibraryEntry,
  type TranslateFn,
} from './dataSourceLibraryShared';

const CONTROL_GHOST_BUTTON_CLASS = 'px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/10 hover:bg-white/10 text-xs transition-colors';
const GHOST_TAG_CLASS = 'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] uppercase tracking-widest font-bold bg-white/5 text-white/40 border border-white/5';
const DRAWER_PANEL_CLASS = 'rounded-xl border border-white/5 bg-white/[0.02] px-4 py-3';
const DRAWER_LABEL_CLASS = 'text-[10px] uppercase tracking-widest text-white/40 mb-1.5 font-bold block';
const DRAWER_TEXTAREA_CLASS = 'min-h-[6rem] w-full resize-y rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-sm text-white transition-all placeholder:text-white/20 focus:border-indigo-500/50 focus:bg-white/[0.05] focus:outline-none focus:ring-1 focus:ring-indigo-500/50 disabled:cursor-not-allowed disabled:opacity-60';
const DRAWER_ADVANCED_SUMMARY_CLASS = 'mt-6 flex cursor-pointer list-none items-center gap-1.5 border-t border-white/5 pt-4 text-xs text-white/30 transition-colors hover:text-white [&::-webkit-details-marker]:hidden';
export const DRAWER_GHOST_FORM_SCOPE_CLASS = '[&_.input-surface]:!rounded-lg [&_.input-surface]:!border-white/5 [&_.input-surface]:!bg-white/[0.02] [&_.input-surface]:!py-2 [&_.input-surface]:!text-sm [&_.input-surface]:!text-white [&_.input-surface]:!transition-all [&_.input-surface]:placeholder:!text-white/20 [&_.input-surface]:focus:!border-indigo-500/50 [&_.input-surface]:focus:!bg-white/[0.05] [&_.input-surface]:focus:!outline-none [&_.input-surface]:focus:!ring-1 [&_.input-surface]:focus:!ring-indigo-500/50 [&_.theme-field-label]:!mb-1.5 [&_.theme-field-label]:!block [&_.theme-field-label]:!text-[10px] [&_.theme-field-label]:!font-bold [&_.theme-field-label]:!uppercase [&_.theme-field-label]:!tracking-widest [&_.theme-field-label]:!text-white/40';

type ManagedBuiltinDraft = {
  credential: string;
  secret: string;
  extraValue: string;
};

type DataSourceLibraryDrawerProps = {
  adminLocked: boolean;
  isOpen: boolean;
  isSaving: boolean;
  language: string;
  deleteTarget: DataSourceLibraryEntry | null;
  draft: CustomDataSourceRecord;
  entry: DataSourceLibraryEntry | null;
  mode: DataSourceEditorMode;
  managedBuiltinDraft: ManagedBuiltinDraft;
  onClose: () => void;
  onDeleteTargetChange: (value: string | null) => void;
  onDraftChange: React.Dispatch<React.SetStateAction<CustomDataSourceRecord>>;
  onManagedBuiltinDraftChange: React.Dispatch<React.SetStateAction<ManagedBuiltinDraft>>;
  onSave: () => void;
  onValidate: (sourceId: string) => void;
  onConfirmDelete: () => void;
  t: TranslateFn;
  validationResult?: BuiltinDataSourceValidationResult;
};

const DataSourceLibraryDrawer: React.FC<DataSourceLibraryDrawerProps> = ({
  adminLocked,
  isOpen,
  isSaving,
  language,
  deleteTarget,
  draft,
  entry,
  mode,
  managedBuiltinDraft,
  onClose,
  onDeleteTargetChange,
  onDraftChange,
  onManagedBuiltinDraftChange,
  onSave,
  onValidate,
  onConfirmDelete,
  t,
  validationResult,
}) => (
  <>
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      title={mode === 'create'
        ? t('settings.dataSourceDrawerTitleCreate')
        : entry
          ? t('settings.dataSourceDrawerTitleEdit', { source: entry.label })
          : t('settings.dataSourceDrawerTitleFallback')}
      width="max-w-[min(100vw,44rem)]"
      zIndex={81}
      bodyClassName={DRAWER_GHOST_FORM_SCOPE_CLASS}
    >
      {mode === 'view' && entry ? (
        <div className="space-y-3">
          <div className={DRAWER_PANEL_CLASS}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-foreground">{entry.label}</p>
                <p className="mt-1 text-xs text-secondary-text">
                  {entry.builtin ? t('settings.dataSourceBuiltinKind') : t('settings.dataSourceCustomKind')}
                </p>
              </div>
              <span className={GHOST_TAG_CLASS}>{entry.validationMessage}</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {entry.capabilityLabels.map((capability) => (
                <span key={`drawer-${entry.key}-${capability}`} className={GHOST_TAG_CLASS}>
                  {capability}
                </span>
              ))}
            </div>
            <p className="mt-3 text-xs text-secondary-text">
              {t('settings.dataSourceUsedByLabel')}: {entry.routeUsage.length
                ? entry.routeUsage.map((routeKey) => t(`settings.dataRouteName.${routeKey}`)).join(' · ')
                : t('settings.dataSourceNotRouted')}
            </p>
            <p className="mt-1 text-xs text-muted-text">{entry.description}</p>
          </div>
          {validationResult ? (
            <div className={DRAWER_PANEL_CLASS} data-testid="builtin-data-source-validation-result">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-foreground">{validationResult.summary}</p>
                <span className={GHOST_TAG_CLASS}>{validationResult.status}</span>
              </div>
              <div className="mt-2 grid gap-1.5 text-xs text-secondary-text">
                <p>{t('settings.dataSourceValidationKeyMasked')}: {validationResult.keyMasked || t('settings.dataSourceValidationPublicProvider')}</p>
                <p>{language === 'zh' ? '校验时间' : 'Checked at'}: {formatDateTime(validationResult.checkedAt)}</p>
                <p>{t('settings.dataSourceValidationDuration')}: {formatDurationMs(validationResult.durationMs)}</p>
                {validationResult.checks.map((check) => (
                  <p key={`${validationResult.provider}-${check.name}`}>
                    {formatDataSourceCheckLine(check)} · {check.message}
                  </p>
                ))}
              </div>
              <p className="mt-2 text-xs text-muted-text">{validationResult.suggestion}</p>
            </div>
          ) : null}
          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              variant="settings-secondary"
              className={CONTROL_GHOST_BUTTON_CLASS}
              onClick={() => onValidate(entry.key)}
              disabled={adminLocked || isSaving || !entry.usable}
            >
              {t('settings.dataSourceValidateAction')}
            </Button>
          </div>
        </div>
      ) : mode === 'manage_builtin' && entry?.management ? (
        <div className="space-y-4">
          <div className="rounded-[var(--theme-panel-radius-lg)] border border-border/50 bg-base/40 px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-foreground">{entry.label}</p>
                <p className="mt-1 text-xs text-secondary-text">{t('settings.dataSourceBuiltinManageDesc')}</p>
              </div>
              <span className={GHOST_TAG_CLASS}>
                {entry.credentialSchema === 'key_secret'
                  ? t('settings.dataSourceSchemaKeySecret')
                  : entry.credentialSchema === 'single_key'
                    ? t('settings.dataSourceSchemaSingleKey')
                    : t('settings.dataSourceSchemaNone')}
              </span>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {entry.capabilityLabels.map((capability) => (
                <span key={`builtin-${entry.key}-${capability}`} className={GHOST_TAG_CLASS}>
                  {capability}
                </span>
              ))}
            </div>
            <p className="mt-3 text-xs text-secondary-text">
              {t('settings.dataSourceUsedByLabel')}: {entry.routeUsage.length
                ? entry.routeUsage.map((routeKey) => t(`settings.dataRouteName.${routeKey}`)).join(' · ')
                : t('settings.dataSourceNotRouted')}
            </p>
            <p className="mt-1 text-xs text-muted-text">{entry.description}</p>
          </div>

          <div className="space-y-3">
            {entry.management.fields.map((field) => (
              <Input
                key={field.name}
                type="password"
                allowTogglePassword
                iconType="key"
                label={t(field.labelKey)}
                value={field.name === 'secret' ? managedBuiltinDraft.secret : managedBuiltinDraft.credential}
                onChange={(event) => onManagedBuiltinDraftChange((prev) => ({
                  ...prev,
                  [field.name === 'secret' ? 'secret' : 'credential']: event.target.value,
                }))}
                disabled={isSaving}
                hint={t(field.hintKey)}
                placeholder={field.placeholder}
              />
            ))}
            {entry.management.extraField ? (
              <details>
                <summary className={DRAWER_ADVANCED_SUMMARY_CLASS}>
                  配置高级参数 (Advanced Settings) ▾
                </summary>
                <div className="mt-3 space-y-2">
                  <Select
                    label={t(entry.management.extraField.labelKey)}
                    value={managedBuiltinDraft.extraValue || entry.management.extraField.defaultValue}
                    onChange={(value) => onManagedBuiltinDraftChange((prev) => ({
                      ...prev,
                      extraValue: value,
                    }))}
                    options={entry.management.extraField.options}
                    disabled={isSaving}
                  />
                  <p className="text-xs text-muted-text">{t(entry.management.extraField.hintKey)}</p>
                </div>
              </details>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-secondary-text">{entry.validationMessage}</p>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="settings-secondary"
                className={CONTROL_GHOST_BUTTON_CLASS}
                onClick={() => onValidate(entry.key)}
                disabled={isSaving}
              >
                {t('settings.dataSourceValidateAction')}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="settings-primary"
                onClick={onSave}
                disabled={isSaving}
              >
                {t('settings.dataSourceEditorSaveAction')}
              </Button>
            </div>
          </div>
          {validationResult ? (
            <div className="rounded-[var(--theme-panel-radius-lg)] border border-border/50 bg-base/40 px-4 py-3" data-testid="builtin-data-source-validation-result">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-foreground">{validationResult.summary}</p>
                <span className={GHOST_TAG_CLASS}>{validationResult.status}</span>
              </div>
              <div className="mt-2 grid gap-1.5 text-xs text-secondary-text">
                <p>{t('settings.dataSourceValidationKeyMasked')}: {validationResult.keyMasked || t('settings.dataSourceValidationPublicProvider')}</p>
                <p>{language === 'zh' ? '校验时间' : 'Checked at'}: {formatDateTime(validationResult.checkedAt)}</p>
                <p>{t('settings.dataSourceValidationDuration')}: {formatDurationMs(validationResult.durationMs)}</p>
                {validationResult.checks.map((check) => (
                  <p key={`${validationResult.provider}-${check.name}`}>
                    {formatDataSourceCheckLine(check)} · {check.message}
                  </p>
                ))}
              </div>
              <p className="mt-2 text-xs text-muted-text">{validationResult.suggestion}</p>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="space-y-3">
          <div className={DRAWER_PANEL_CLASS}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-foreground">
                  {mode === 'create'
                    ? t('settings.dataSourceEditorCreateTitle')
                    : t('settings.dataSourceEditorEditTitle')}
                </p>
                <p className="mt-1 text-xs text-secondary-text">{t('settings.dataSourceEditorDesc')}</p>
              </div>
              <span className={GHOST_TAG_CLASS}>
                {draft.capabilities.length
                  ? t('settings.dataSourceConfiguredPending')
                  : t('settings.notConfigured')}
              </span>
            </div>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {DATA_SOURCE_CUSTOM_SCHEMA_OPTIONS.map((option) => {
                const active = draft.credentialSchema === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    className={active
                      ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-3 py-2 text-left shadow-[var(--glow-soft)]'
                      : 'rounded-[var(--theme-control-radius)] border border-border/60 bg-base/60 px-3 py-2 text-left'}
                    onClick={() => onDraftChange((prev) => ({
                      ...prev,
                      credentialSchema: option.value,
                      secret: option.value === 'key_secret' ? prev.secret : '',
                    }))}
                    disabled={isSaving}
                  >
                    <p className="text-sm font-medium text-foreground">{t(option.labelKey)}</p>
                    <p className="mt-1 text-xs text-secondary-text">{t(option.descriptionKey)}</p>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-3">
            <Input
              label={t('settings.dataSourceEditorName')}
              value={draft.name}
              onChange={(event) => onDraftChange((prev) => ({ ...prev, name: event.target.value }))}
              disabled={isSaving}
            />
            <Input
              type="password"
              allowTogglePassword
              iconType="key"
              label={t('settings.dataSourceFieldApiKey')}
              value={draft.credential}
              onChange={(event) => onDraftChange((prev) => ({ ...prev, credential: event.target.value }))}
              disabled={isSaving}
              hint={t('settings.dataSourceEditorCredentialHint')}
            />
            {draft.credentialSchema === 'key_secret' ? (
              <Input
                type="password"
                allowTogglePassword
                iconType="key"
                label={t('settings.dataSourceFieldSecretKey')}
                value={draft.secret}
                onChange={(event) => onDraftChange((prev) => ({ ...prev, secret: event.target.value }))}
                disabled={isSaving}
                hint={t('settings.dataSourceFieldSecretKeyHint')}
              />
            ) : null}
            <details>
              <summary className={DRAWER_ADVANCED_SUMMARY_CLASS}>
                配置高级参数 (Advanced Settings) ▾
              </summary>
              <div className="mt-3 space-y-3">
                <Input
                  label={t('settings.dataSourceEditorBaseUrl')}
                  value={draft.baseUrl}
                  onChange={(event) => onDraftChange((prev) => ({ ...prev, baseUrl: event.target.value }))}
                  disabled={isSaving}
                  hint={t('settings.dataSourceEditorBaseUrlHint')}
                  placeholder="https://example.com/v1"
                />
                <div>
                  <label className={DRAWER_LABEL_CLASS}>{t('settings.dataSourceEditorDescription')}</label>
                  <textarea
                    value={draft.description}
                    onChange={(event) => onDraftChange((prev) => ({ ...prev, description: event.target.value }))}
                    disabled={isSaving}
                    className={DRAWER_TEXTAREA_CLASS}
                  />
                </div>
                <div>
                  <p className={DRAWER_LABEL_CLASS}>{t('settings.dataSourceEditorCapabilities')}</p>
                  <div className="flex flex-wrap gap-2">
                    {DATA_SOURCE_CAPABILITY_OPTIONS.map((capability) => {
                      const active = draft.capabilities.includes(capability);
                      return (
                        <button
                          key={capability}
                          type="button"
                          className={active
                            ? 'rounded-lg border border-white/10 bg-white/10 px-3 py-1.5 text-xs font-medium text-white'
                            : 'rounded-lg border border-white/5 bg-white/[0.03] px-3 py-1.5 text-xs text-white/40 hover:bg-white/10'}
                          onClick={() => onDraftChange((prev) => {
                            const nextCapabilities = active
                              ? prev.capabilities.filter((item) => item !== capability)
                              : [...prev.capabilities, capability];
                            return { ...prev, capabilities: nextCapabilities };
                          })}
                          disabled={isSaving}
                        >
                          {t(DATA_SOURCE_CAPABILITY_LABEL_KEYS[capability])}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            </details>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-secondary-text">
              {mode === 'create'
                ? t('settings.dataSourceValidationAfterCreateHint')
                : draft.validation?.status === 'failed'
                  ? draft.validation.message || t('settings.dataSourceValidationLocalFailed')
                  : draft.validation?.status === 'validated'
                    ? t('settings.dataSourceValidationLocalSuccess')
                    : t('settings.dataSourceValidationConfiguredOnly')}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {mode !== 'create' && entry ? (
                <Button
                  type="button"
                  size="sm"
                  variant="danger-subtle"
                  onClick={() => onDeleteTargetChange(entry.key)}
                  disabled={isSaving}
                >
                  {t('settings.dataSourceDeleteAction')}
                </Button>
              ) : null}
              <Button
                type="button"
                size="sm"
                variant="settings-primary"
                onClick={onSave}
                disabled={isSaving}
              >
                {mode === 'create'
                  ? t('settings.dataSourceEditorCreateAction')
                  : t('settings.dataSourceEditorSaveAction')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </Drawer>

    <ConfirmDialog
      isOpen={deleteTarget !== null}
      title={t('settings.dataSourceDeleteConfirmTitle', { source: deleteTarget?.label || '' })}
      message={t('settings.dataSourceDeleteConfirmBody', { source: deleteTarget?.label || '' })}
      confirmText={t('settings.dataSourceDeleteAction')}
      cancelText={t('common.cancel')}
      isDanger
      onConfirm={onConfirmDelete}
      onCancel={() => onDeleteTargetChange(null)}
    />
  </>
);

export default DataSourceLibraryDrawer;
