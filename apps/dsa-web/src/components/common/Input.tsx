/**
 * Paper workbench input: preserves labeling, validation, and password
 * visibility behavior while relying on shared control tokens.
 */
import type React from 'react';
import { useId, useState } from 'react';
import { Lock, Key } from 'lucide-react';
import { useI18n } from '../../contexts/UiLanguageContext';
import { cn } from '../../utils/cn';
import { EyeToggleIcon } from './EyeToggleIcon';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  labelClassName?: string;
  containerClassName?: string;
  hint?: string;
  error?: string;
  trailingAction?: React.ReactNode;
  /** Enables the built-in password visibility toggle. */
  allowTogglePassword?: boolean;
  /** Controls the leading icon style. */
  iconType?: 'password' | 'key' | 'none';
  /** Allows external visibility state control. */
  passwordVisible?: boolean;
  /** Notifies the parent when visibility changes in controlled mode. */
  onPasswordVisibleChange?: (visible: boolean) => void;
}

export const Input = ({ 
  label, 
  labelClassName,
  containerClassName = '',
  hint, 
  error, 
  className = '', 
  id, 
  trailingAction, 
  allowTogglePassword,
  iconType = 'none',
  passwordVisible,
  onPasswordVisibleChange,
  ...props 
}: InputProps) => {
  const { t } = useI18n();
  const generatedId = useId();
  const inputId = id ?? props.name ?? generatedId;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const describedBy = [props['aria-describedby'], errorId ?? hintId].filter(Boolean).join(' ') || undefined;
  const ariaInvalid = props['aria-invalid'] ?? (error ? true : undefined);

  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const isPasswordInput = props.type === 'password';
  const isVisibilityControlled = typeof passwordVisible === 'boolean';
  const visible = isVisibilityControlled ? passwordVisible : isPasswordVisible;
  const effectiveType = isPasswordInput && allowTogglePassword && visible ? 'text' : props.type;

  const renderLeadingIcon = () => {
    if (iconType === 'password') {
      return <Lock className="size-4 text-muted-text/55" />;
    }
    if (iconType === 'key') {
      return <Key className="size-4 text-muted-text/55" />;
    }
    return null;
  };

  const leadingIcon = renderLeadingIcon();
  const inputStyle = error
    ? {
      ...props.style,
      ['--input-surface-border-focus' as string]: 'hsla(var(--destructive), 0.4)',
      ['--input-surface-focus-ring' as string]: '0 0 0 2px hsla(var(--destructive), 0.12)',
    }
    : props.style;
  const controlState = props.disabled
    ? 'disabled'
    : error
      ? 'error'
      : 'ready';

  const defaultTrailingAction = isPasswordInput && allowTogglePassword ? (
    <button
      type="button"
      className={cn(
        'input-surface__toggle pointer-events-auto inline-flex size-7 items-center justify-center rounded-full border border-transparent bg-transparent transition-all duration-200 focus:outline-none focus:ring-2',
        visible
          ? 'text-foreground'
          : 'text-muted-text focus:ring-[var(--focus-ring)]'
      )}
      onClick={() => {
        const nextVisible = !visible;
        if (!isVisibilityControlled) {
          setIsPasswordVisible(nextVisible);
        }
        onPasswordVisibleChange?.(nextVisible);
      }}
      onMouseDown={(event) => event.preventDefault()}
      aria-label={visible ? t('common.hideContent') : t('common.showContent')}
      title={visible ? t('common.hide') : t('common.show')}
    >
      <EyeToggleIcon visible={visible} />
    </button>
  ) : null;

  const finalTrailingAction = trailingAction || defaultTrailingAction;

  return (
    <div className={cn('input-field flex min-w-0 w-full max-w-full flex-col', containerClassName)}>
      {label ? <label htmlFor={inputId} className={cn('theme-field-label mb-2', labelClassName)}>{label}</label> : null}
      <div className="input-field__control ui-control-shell relative flex min-w-0 w-full max-w-full items-center">
        {leadingIcon && (
          <div className="input-field__icon ui-control-icon absolute left-3 z-10">
            {leadingIcon}
          </div>
        )}
        <input
          id={inputId}
          aria-describedby={describedBy}
          aria-invalid={ariaInvalid}
          data-control-state={controlState}
          style={inputStyle}
          className={cn(
            'input-surface input-focus-glow h-10 w-full min-w-0 max-w-full rounded-xl border px-4 text-sm text-foreground transition-all placeholder:text-muted-text',
            'focus:outline-none',
            error ? 'border-danger/30' : '',
            leadingIcon ? 'pl-12' : '',
            finalTrailingAction ? 'pr-12' : '',
            'disabled:cursor-not-allowed disabled:opacity-60',
            className,
          )}
          {...props}
          type={effectiveType}
        />
        {finalTrailingAction ? (
          <div className="input-field__trailing ui-control-icon absolute inset-y-0 right-1.5 flex items-center">
            {finalTrailingAction}
          </div>
        ) : null}
      </div>
      {error ? (
        <p id={errorId} role="alert" className="mt-2 text-xs text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="mt-2 text-xs leading-5 text-secondary-text">
          {hint}
        </p>
      ) : null}
    </div>
  );
};
