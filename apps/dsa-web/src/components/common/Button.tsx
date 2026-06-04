/**
 * SpaceX live refactor: preserves the shared button API and loading behavior
 * while normalizing controls around restrained ghost surfaces, tighter sizing,
 * and typography that inherits the active theme instead of hard-coding a boxy style.
 */
import React from 'react';
import { useI18n } from '../../contexts/UiLanguageContext';
import { cn } from '../../utils/cn';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'gradient' | 'danger' | 'danger-subtle' | 'settings-primary' | 'settings-secondary' | 'home-action-ai' | 'home-action-report';
  size?: 'sm' | 'md' | 'lg' | 'xl';
  isLoading?: boolean;
  loadingText?: string;
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
  'settings-primary': 'rounded-lg border border-white/10 bg-white/5 px-6 py-2.5 text-sm font-medium text-white transition-all hover:border-blue-500/40 hover:bg-white/10 hover:shadow-[0_0_15px_rgba(59,130,246,0.15)] !rounded-lg !border !border-white/10 !bg-white/5 !px-6 !py-2.5 !text-sm !font-medium !text-white !shadow-none hover:!border-blue-500/40 hover:!bg-white/10 hover:!shadow-[0_0_15px_rgba(59,130,246,0.15)]',
  'settings-secondary': 'bg-white/5 border border-white/10 text-white/70 hover:bg-white/10 hover:text-white rounded-lg px-5 py-2.5 text-sm font-medium transition-all !rounded-lg !border !border-white/10 !bg-white/5 !px-5 !py-2.5 !text-sm !font-medium !text-white/70 hover:!bg-white/10 hover:!text-white',
  outline: '',
  ghost: '',
  gradient: 'rounded-lg border border-white/10 bg-white/5 px-6 py-2.5 text-sm font-medium text-white transition-all hover:border-blue-500/40 hover:bg-white/10 hover:shadow-[0_0_15px_rgba(59,130,246,0.15)]',
  danger: '',
  'danger-subtle': '',
  'home-action-ai': '',
  'home-action-report': '',
} as const;

export const Button = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  loadingText,
  glow = false,
  className = '',
  disabled,
  type = 'button',
  ref,
  ...props
}: ButtonProps) => {
  const { t } = useI18n();
  const glowStyles = glow ? 'theme-accent-glow settings-glow-accent-hover' : '';
  const resolvedLoadingText = loadingText || (isLoading ? t('common.processing') : '');

  return (
    <button
      ref={ref}
      type={type}
      aria-busy={isLoading || undefined}
      data-variant={variant}
      data-size={size}
      className={cn(
        'pointer-events-auto inline-flex w-auto max-w-full cursor-pointer items-center justify-center gap-2 rounded-[var(--theme-button-radius)] border border-transparent bg-transparent font-normal whitespace-nowrap transition-[color,background-color,border-color,opacity,transform] duration-200 [backface-visibility:hidden] [transform:translateZ(0)]',
        'theme-focus-ring focus-visible:ring-offset-0 focus-visible:outline-none',
        'disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 disabled:transform-none',
        BUTTON_SIZE_STYLES[size],
        BUTTON_VARIANT_STYLES[variant],
        glowStyles,
        className,
      )}
      style={{
        fontFamily: 'var(--theme-button-font-family)',
        fontWeight: 'var(--theme-button-font-weight)',
        letterSpacing: 'var(--theme-button-letter-spacing)',
        textTransform: 'var(--theme-button-text-transform)',
      }}
      disabled={disabled || isLoading}
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
