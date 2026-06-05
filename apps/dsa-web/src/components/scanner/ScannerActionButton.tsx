import type { MouseEvent, ReactNode } from 'react';
import { TerminalButton } from '../terminal/TerminalPrimitives';

type ScannerActionButtonVariant = 'primary' | 'secondary' | 'compact';

export function ScannerActionButton({
  label,
  icon,
  onClick,
  disabled = false,
  title,
  variant = 'compact',
  testId,
}: {
  label: string;
  icon?: ReactNode;
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void;
  disabled?: boolean;
  title?: string;
  variant?: ScannerActionButtonVariant;
  testId?: string;
}) {
  const resolvedVariant = variant === 'primary' ? 'secondary' : variant;
  const sizeClass = resolvedVariant === 'secondary'
    ? 'h-12 px-3 py-2 text-xs md:h-9 md:py-1.5'
    : 'h-12 px-3 py-2 text-xs md:h-8 md:px-2.5 md:py-1';

  return (
    <TerminalButton
      type="button"
      data-testid={testId}
      variant={resolvedVariant}
      className={`min-w-0 ${sizeClass}`.trim()}
      onClick={(event) => {
        event.stopPropagation();
        onClick?.(event);
      }}
      disabled={disabled}
      title={title}
    >
      {icon}
      <span className="truncate">{label}</span>
    </TerminalButton>
  );
}
