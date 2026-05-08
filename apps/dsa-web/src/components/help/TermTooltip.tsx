import { type KeyboardEvent, type ReactNode, useId, useRef, useState } from 'react';
import { cn } from '../../utils/cn';

export interface TermTooltipProps {
  label: string;
  explanation: string;
  professionalNote: string;
  caveat?: string;
  labelEn?: string;
  children?: ReactNode;
  className?: string;
  triggerClassName?: string;
  panelClassName?: string;
  align?: 'start' | 'center';
}

export function TermTooltip({
  label,
  labelEn,
  explanation,
  professionalNote,
  caveat,
  children,
  className,
  triggerClassName,
  panelClassName,
  align = 'center',
}: TermTooltipProps) {
  const tooltipId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const pointerActivationRef = useRef(false);
  const [isOpen, setIsOpen] = useState(false);

  function close() {
    setIsOpen(false);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'Escape') {
      event.preventDefault();
      close();
      triggerRef.current?.focus();
    }
  }

  return (
    <span className={cn('relative inline-flex min-w-0 align-baseline', className)}>
      <button
        ref={triggerRef}
        type="button"
        className={cn(
          'group inline-flex min-w-0 items-center gap-1 rounded-md border border-transparent bg-transparent px-1 py-0.5 text-left text-current outline-none transition-all',
          'hover:border-cyan-300/20 hover:bg-white/[0.04] focus-visible:border-cyan-300/45 focus-visible:bg-white/[0.05] focus-visible:ring-2 focus-visible:ring-cyan-300/25',
          triggerClassName,
        )}
        aria-label={`${label} 术语说明`}
        aria-expanded={isOpen}
        aria-describedby={isOpen ? tooltipId : undefined}
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={close}
        onPointerDown={() => {
          pointerActivationRef.current = true;
        }}
        onFocus={() => {
          if (!pointerActivationRef.current) {
            setIsOpen(true);
          }
        }}
        onBlur={close}
        onClick={() => {
          pointerActivationRef.current = false;
          setIsOpen((current) => !current);
        }}
        onKeyDown={handleKeyDown}
      >
        {children ?? (
          <span className="truncate border-b border-dotted border-cyan-200/35 text-current decoration-transparent transition-colors group-hover:border-cyan-200/70">
            {label}
          </span>
        )}
      </button>
      {isOpen ? (
        <span
          id={tooltipId}
          role="tooltip"
          className={cn(
            'absolute top-full z-50 mt-2 w-[min(18rem,calc(100vw-2rem))] rounded-xl border border-white/10 bg-black/70 p-3 text-left text-xs leading-5 text-white/78 shadow-[0_18px_45px_rgba(0,0,0,0.45)] backdrop-blur-xl',
            'before:absolute before:-top-1.5 before:h-3 before:w-3 before:rotate-45 before:border-l before:border-t before:border-white/10 before:bg-black/70',
            align === 'center'
              ? 'left-1/2 -translate-x-1/2 before:left-1/2 before:-translate-x-1/2'
              : 'left-0 before:left-4',
            panelClassName,
          )}
        >
          <span className="block text-[11px] font-medium uppercase tracking-[0.18em] text-cyan-200/70">
            {labelEn ? `${label} / ${labelEn}` : label}
          </span>
          <span className="mt-2 block text-white/86">{explanation}</span>
          <span className="mt-2 block border-t border-white/8 pt-2 text-white/62">
            <span className="text-cyan-100/80">专业口径：</span>
            {professionalNote}
          </span>
          {caveat ? (
            <span className="mt-1.5 block text-amber-100/78">
              <span className="text-amber-200/90">使用边界：</span>
              {caveat}
            </span>
          ) : null}
        </span>
      ) : null}
    </span>
  );
}
