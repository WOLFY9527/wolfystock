/**
 * Shared research-workbench button: preserves the existing API and loading
 * behavior while letting DESIGN.md tokens own the visual hierarchy.
 */
import React from 'react';
import { useI18n } from '../../contexts/UiLanguageContext';
import { cn } from '../../utils/cn';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'gradient' | 'danger' | 'danger-subtle' | 'settings-primary' | 'settings-secondary' | 'home-action-ai' | 'home-action-report';
  size?: 'sm' | 'md' | 'lg' | 'xl';
  actionIntent?: 'write' | 'navigate' | 'passive';
  isLoading?: boolean;
  loadingText?: string;
  /** Deprecated compatibility prop; shared glow styling was removed in T189. */
  glow?: boolean;
  ref?: React.Ref<HTMLButtonElement>;
}

const BUTTON_SIZE_STYLES = {
  sm: 'min-h-[34px] h-[34px] rounded-[var(--theme-button-radius)] px-3 text-[0.72rem]',
  md: 'min-h-[40px] h-10 rounded-[var(--theme-button-radius)] px-4 text-[0.75rem]',
  lg: 'min-h-[44px] h-11 rounded-[var(--theme-button-radius)] px-5 text-[0.78rem]',
  xl: 'min-h-[48px] h-12 rounded-[var(--theme-button-radius)] px-6 text-[0.8rem]',
} as const;

const BUTTON_VARIANT_STYLES = {
  primary: '',
  secondary: '',
  'settings-primary': '!rounded-[var(--theme-button-radius)] !border !border-[color:var(--theme-button-primary-border)] !bg-[var(--theme-button-primary-bg)] !px-6 !py-2.5 !text-sm !font-medium !text-[color:var(--theme-button-primary-text)] !shadow-none hover:!bg-[var(--sage-deep)]',
  'settings-secondary': '!rounded-[var(--theme-button-radius)] !border !border-[color:var(--theme-button-secondary-border)] !bg-[var(--theme-button-secondary-bg)] !px-5 !py-2.5 !text-sm !font-medium !text-[color:var(--theme-button-secondary-text)] !shadow-none hover:!border-[color:var(--line-strong)] hover:!bg-[var(--surface-3)]',
  outline: '',
  ghost: '',
  gradient: 'rounded-[var(--theme-button-radius)] border border-[color:var(--state-warning-border)] bg-[var(--state-warning-bg)] px-6 py-2.5 text-sm font-medium text-[color:var(--state-warning-text)] transition-all hover:bg-[var(--state-warning-bg-strong)]',
  danger: '',
  'danger-subtle': '',
  'home-action-ai': '',
  'home-action-report': '',
} as const;

const BUTTON_INTENT_BY_VARIANT: Record<NonNullable<ButtonProps['variant']>, NonNullable<ButtonProps['actionIntent']>> = {
  primary: 'write',
  secondary: 'passive',
  'settings-primary': 'write',
  'settings-secondary': 'passive',
  outline: 'navigate',
  ghost: 'passive',
  gradient: 'write',
  danger: 'write',
  'danger-subtle': 'write',
  'home-action-ai': 'write',
  'home-action-report': 'navigate',
};

export const Button = ({
  children,
  variant = 'primary',
  size = 'md',
  actionIntent,
  isLoading = false,
  loadingText,
  glow: _glow,
  className = '',
  disabled,
  type = 'button',
  ref,
  ...props
}: ButtonProps) => {
  const { t } = useI18n();
  void _glow;
  const resolvedLoadingText = loadingText || (isLoading ? t('common.processing') : '');
  const resolvedActionIntent = actionIntent ?? BUTTON_INTENT_BY_VARIANT[variant];
  const isDisabled = disabled || isLoading;

  return (
    <button
      ref={ref}
      type={type}
      aria-busy={isLoading || undefined}
      data-variant={variant}
      data-size={size}
      data-action-intent={resolvedActionIntent}
      data-control-state={isLoading ? 'loading' : isDisabled ? 'disabled' : 'ready'}
      className={cn(
        'pointer-events-auto inline-flex w-auto max-w-full cursor-pointer items-center justify-center gap-2 rounded-[var(--theme-button-radius)] border border-transparent bg-transparent font-normal whitespace-nowrap transition-[color,background-color,border-color,opacity,transform] duration-200 [backface-visibility:hidden] [transform:translateZ(0)]',
        'theme-focus-ring focus-visible:ring-offset-0 focus-visible:outline-none',
        'disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 disabled:transform-none',
        'active:translate-y-px',
        BUTTON_SIZE_STYLES[size],
        BUTTON_VARIANT_STYLES[variant],
        className,
      )}
      style={{
        fontFamily: 'var(--theme-button-font-family)',
        fontWeight: 'var(--theme-button-font-weight)',
        letterSpacing: 'var(--theme-button-letter-spacing)',
        textTransform: 'var(--theme-button-text-transform)',
      }}
      disabled={isDisabled}
      {...props}
    >
      {isLoading ? (
        <span className="flex items-center justify-center gap-2">
          <svg
            className="size-4 animate-spin text-current"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          {resolvedLoadingText}
        </span>
      ) : (
        children
      )}
    </button>
  );
};
