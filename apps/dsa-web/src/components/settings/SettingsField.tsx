import { useState } from 'react';
import type React from 'react';
import { Badge } from '../common/Badge';
import { Select } from '../common/Select';
import { Input } from '../common/Input';
import { useI18n } from '../../contexts/UiLanguageContext';
import type { ConfigValidationIssue, SystemConfigFieldSchema, SystemConfigItem } from '../../types/systemConfig';
import { getFieldDescription, getFieldTitle } from '../../utils/systemConfigI18n';
import { cn } from '../../utils/cn';

function normalizeSelectOptions(options: SystemConfigFieldSchema['options'] = []) {
  return options.map((option) => {
    if (typeof option === 'string') {
      return { value: option, label: option };
    }

    return option;
  });
}

function isMultiValueField(item: SystemConfigItem): boolean {
  const validation = (item.schema?.validation ?? {}) as Record<string, unknown>;
  return Boolean(validation.multiValue ?? validation.multi_value);
}

function parseMultiValues(value: string): string[] {
  if (!value) {
    return [''];
  }

  const values = value.split(',').map((entry) => entry.trim());
  return values.length ? values : [''];
}

function serializeMultiValues(values: string[]): string {
  return values.map((entry) => entry.trim()).join(',');
}

function inferPasswordIconType(key: string): 'password' | 'key' {
  return key.toUpperCase().includes('PASSWORD') ? 'password' : 'key';
}

interface SettingsFieldProps {
  item: SystemConfigItem;
  value: string;
  disabled?: boolean;
  onChange: (key: string, value: string) => void;
  issues?: ConfigValidationIssue[];
}

const EMPTY_ISSUES: ConfigValidationIssue[] = [];

type SettingsFieldControlProps = {
  item: SystemConfigItem,
  value: string,
  disabled: boolean,
  onChange: (nextValue: string) => void,
  isPasswordEditable: boolean,
  onPasswordFocus: () => void,
  controlId: string,
  t: (key: string, vars?: Record<string, string | number | undefined>) => string,
};

const SettingsFieldControl: React.FC<SettingsFieldControlProps> = ({
  item,
  value,
  disabled,
  onChange,
  isPasswordEditable,
  onPasswordFocus,
  controlId,
  t,
}) => {
  const schema = item.schema;
  const commonClass = 'input-terminal border-border/55 bg-card/94 hover:border-border/75';
  const controlType = schema?.uiControl ?? 'text';
  const isMultiValue = isMultiValueField(item);

  if (controlType === 'textarea') {
    return (
      <textarea
        id={controlId}
        aria-label={item.key}
        className={`${commonClass} min-h-[92px] resize-y`}
        value={value}
        disabled={disabled || !schema?.isEditable}
        onChange={(event) => onChange(event.target.value)}
      />
    );
  }

  if (controlType === 'select' && schema?.options?.length) {
    return (
        <Select
          id={controlId}
          aria-label={item.key}
          value={value}
          onChange={onChange}
          options={normalizeSelectOptions(schema.options)}
          disabled={disabled || !schema.isEditable}
          placeholder={t('settings.selectPlaceholder')}
        />
      );
  }

  if (controlType === 'switch') {
    const checked = value.trim().toLowerCase() === 'true';
    return (
      <label className="inline-flex cursor-pointer items-center gap-3">
        <input
          id={controlId}
          type="checkbox"
          aria-label={item.key}
          className="settings-input-checkbox size-4 rounded border-border/70 bg-base"
          checked={checked}
          disabled={disabled || !schema?.isEditable}
          onChange={(event) => onChange(event.target.checked ? 'true' : 'false')}
        />
        <span className="text-sm text-secondary-text">{checked ? t('settings.enabledState') : t('settings.disabledState')}</span>
      </label>
    );
  }

  if (controlType === 'password') {
    const iconType = inferPasswordIconType(item.key);

    if (isMultiValue) {
      const values = parseMultiValues(value);
      const rowKeyCounts = new Map<string, number>();
      const rows = values.map((entry) => {
        const keyBase = entry || 'empty';
        const count = rowKeyCounts.get(keyBase) ?? 0;
        rowKeyCounts.set(keyBase, count + 1);
        return {
          entry,
          key: `${item.key}-${keyBase}-${count}`,
        };
      });

      return (
        <div className="space-y-2">
          {rows.map(({ entry, key }, index) => (
            <div className="flex items-center gap-2" key={key}>
              <div className="flex-1">
                <Input
                  type="password"
                  allowTogglePassword
                  iconType={iconType}
                  id={index === 0 ? controlId : `${controlId}-${index}`}
                  readOnly={!isPasswordEditable}
                  onFocus={onPasswordFocus}
                  value={entry}
                  disabled={disabled || !schema?.isEditable}
                  onChange={(event) => {
                    const nextValues = [...values];
                    nextValues[index] = event.target.value;
                    onChange(serializeMultiValues(nextValues));
                  }}
                />
              </div>
              <button
                type="button"
                className="inline-flex h-11 items-center justify-center rounded-xl border settings-border settings-surface-hover px-3 text-xs text-muted-text transition-colors hover:settings-surface-hover hover:text-danger disabled:cursor-not-allowed disabled:opacity-50"
                disabled={disabled || !schema?.isEditable || values.length <= 1}
                onClick={() => {
                  const nextValues = values.filter((_, rowIndex) => rowIndex !== index);
                  onChange(serializeMultiValues(nextValues.length ? nextValues : ['']));
                }}
              >
                {t('settings.deleteKey')}
              </button>
            </div>
          ))}

          <div className="flex items-center gap-2">
            <button
              type="button"
              className="inline-flex items-center justify-center rounded-lg border settings-border settings-surface-hover px-3 py-1 text-xs text-secondary-text transition-colors hover:settings-surface-hover hover:text-foreground"
              disabled={disabled || !schema?.isEditable}
              onClick={() => onChange(serializeMultiValues([...values, '']))}
            >
              {t('settings.addKey')}
            </button>
          </div>
        </div>
      );
    }

    return (
      <Input
        type="password"
        allowTogglePassword
        iconType={iconType}
        id={controlId}
        readOnly={!isPasswordEditable}
        onFocus={onPasswordFocus}
        value={value}
        disabled={disabled || !schema?.isEditable}
        onChange={(event) => onChange(event.target.value)}
      />
    );
  }

  const inputType = controlType === 'number' ? 'number' : controlType === 'time' ? 'time' : 'text';

  return (
    <input
      id={controlId}
      aria-label={item.key}
      type={inputType}
      className={commonClass}
      value={value}
      disabled={disabled || !schema?.isEditable}
      onChange={(event) => onChange(event.target.value)}
    />
  );
};

export const SettingsField: React.FC<SettingsFieldProps> = ({
  item,
  value,
  disabled = false,
  onChange,
  issues = EMPTY_ISSUES,
}) => {
  const { language, t } = useI18n();
  const schema = item.schema;
  const isMultiValue = isMultiValueField(item);
  const title = getFieldTitle(language, item.key, item.key);
  const description = getFieldDescription(language, item.key, schema?.description ?? undefined);
  const hasError = issues.some((issue) => issue.severity === 'error');
  const [isPasswordEditable, setIsPasswordEditable] = useState(false);
  const controlId = `setting-${item.key}`;

  return (
    <div
      className={cn(
        'rounded-[1.15rem] border settings-surface p-4 shadow-soft-card transition-all duration-200 hover:settings-surface-hover',
        hasError ? 'border-danger/40' : 'settings-border',
      )}
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <label className="theme-field-label" htmlFor={controlId}>
          {title}
        </label>
        {schema?.isSensitive ? (
          <Badge variant="history" size="sm">
            {t('settings.sensitive')}
          </Badge>
        ) : null}
        {!schema?.isEditable ? (
          <Badge variant="default" size="sm">
            {t('settings.readOnly')}
          </Badge>
        ) : null}
      </div>

      {description ? (
        <p className="mb-3 text-xs leading-5 text-muted-text" title={description}>
          {description}
        </p>
      ) : null}

      <div>
        <SettingsFieldControl
          t={t}
          item={item}
          value={value}
          disabled={disabled}
          onChange={(nextValue) => onChange(item.key, nextValue)}
          isPasswordEditable={isPasswordEditable}
          onPasswordFocus={() => setIsPasswordEditable(true)}
          controlId={controlId}
        />
      </div>

      {schema?.isSensitive ? (
        <p className="mt-3 text-[11px] leading-5 text-secondary-text">
          {t('settings.sensitiveHint')}
          {isMultiValue ? ` ${t('settings.sensitiveHintMulti')}` : ''}
        </p>
      ) : null}

      {issues.length ? (
        <div className="mt-2 space-y-1">
          {issues.map((issue) => (
            <p
              key={`${issue.code}-${issue.key}-${issue.severity}`}
              className={issue.severity === 'error' ? 'text-xs text-danger' : 'text-xs text-warning'}
            >
              {issue.message}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
};
