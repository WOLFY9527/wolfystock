import React, { useId, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { useI18n } from '../../contexts/UiLanguageContext';
import { cn } from '../../utils/cn';

interface SelectOption {
  value: string;
  label: string;
}

interface FlattenedOption {
  value: string;
  label: string;
}

type SelectChildProps = {
  children?: React.ReactNode;
  label?: React.ReactNode;
  value?: unknown;
};

interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'onChange' | 'value'> {
  id?: string;
  value?: number | string;
  onChange: (value: string) => void;
  options?: SelectOption[];
  label?: string;
  labelClassName?: string;
  placeholder?: string;
  className?: string;
  controlClassName?: string;
  searchable?: boolean;
  searchPlaceholder?: string;
  emptyText?: string;
}

function normalizeSelectValue(value: unknown): string {
  if (value == null) return '';
  return String(value);
}

function readNodeText(node: React.ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(readNodeText).join('');
  if (React.isValidElement<SelectChildProps>(node)) return readNodeText(node.props.children);
  return '';
}

function flattenOptionChildren(children: React.ReactNode): FlattenedOption[] {
  const flattened: FlattenedOption[] = [];

  React.Children.forEach(children, (child) => {
    if (!React.isValidElement(child)) {
      return;
    }

    if (React.isValidElement<SelectChildProps>(child) && child.type === 'option') {
      const optionValue = normalizeSelectValue(child.props.value);
      const optionLabel = child.props.label ? String(child.props.label) : readNodeText(child.props.children);
      flattened.push({ value: optionValue, label: optionLabel });
      return;
    }

    if (React.isValidElement<SelectChildProps>(child) && child.type === 'optgroup') {
      flattened.push(...flattenOptionChildren(child.props.children));
    }
  });

  return flattened;
}

export const Select: React.FC<SelectProps> = ({
  id,
  value,
  onChange,
  options,
  label,
  labelClassName,
  placeholder,
  disabled = false,
  className = '',
  controlClassName = '',
  defaultValue,
  children,
  name,
  ...props
}) => {
  const { t } = useI18n();
  const selectId = useId();
  const resolvedId = id ?? selectId;
  const resolvedPlaceholder = placeholder ?? t('common.selectPlaceholder');
  const controlledValue = normalizeSelectValue(value);
  const isControlled = value != null;
  const [uncontrolledValue, setUncontrolledValue] = useState(() => normalizeSelectValue(defaultValue));
  const displayValue = isControlled ? controlledValue : uncontrolledValue;
  const invalid = props['aria-invalid'] === true || props['aria-invalid'] === 'true';
  const hasCustomChildren = React.Children.count(children) > 0;

  const flattenedOptions = hasCustomChildren
    ? flattenOptionChildren(children)
    : [
      ...(resolvedPlaceholder ? [{ value: '', label: resolvedPlaceholder }] : []),
      ...(options ?? []),
    ];

  const matched = flattenedOptions.find((option) => option.value === displayValue);
  const selectedLabel = matched
    ? matched.label
    : displayValue !== ''
      ? displayValue
      : resolvedPlaceholder ?? '';

  return (
    <div className={cn('select-field flex min-w-0 w-full max-w-full flex-col', className)}>
      {label ? <label htmlFor={resolvedId} className={cn('theme-field-label mb-2', labelClassName)}>{label}</label> : null}
      <div className={cn('select-field__control ui-control-shell group relative min-w-0 w-full max-w-full', controlClassName)}>
        <select
          id={resolvedId}
          name={name}
          value={displayValue}
          disabled={disabled}
          {...props}
          className={cn(
            'select-surface absolute inset-0 z-10 size-full min-w-0 cursor-pointer appearance-none truncate rounded-lg pr-10 opacity-0 outline-none',
            disabled ? 'cursor-not-allowed' : '',
          )}
          onChange={(e) => {
            if (!isControlled) {
              setUncontrolledValue(e.target.value);
            }
            onChange(e.target.value);
          }}
        >
          {!hasCustomChildren && resolvedPlaceholder ? (
            <option value="" disabled>
              {resolvedPlaceholder}
            </option>
          ) : null}
          {!hasCustomChildren
            ? (options ?? []).map((option) => (
              <option key={option.value} value={option.value} className="bg-[var(--surface-2)] text-foreground">
                {option.label}
              </option>
            ))
            : children}
        </select>

        <div
          aria-hidden="true"
          className={cn(
            'select-field__overlay pointer-events-none flex h-10 w-full min-w-0 items-center rounded-lg border bg-white/[0.02] px-3 py-2.5 text-sm text-white transition-all duration-200',
            invalid
              ? 'border-rose-500/50 text-rose-100'
              : 'border-white/10 group-focus-within:border-emerald-500/50',
            disabled ? 'opacity-50' : '',
          )}
        >
          <span className="select-field__value min-w-0 flex-1 truncate">{selectedLabel}</span>
          <ChevronDown className="select-field__icon ui-control-icon ml-2 size-4 shrink-0 text-white/40" />
        </div>
      </div>
    </div>
  );
};
