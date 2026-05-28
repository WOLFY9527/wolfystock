/**
 * SpaceX live refactor: preserves side-drawer mounting, focus escape, and body
 * scroll locking while simplifying the shell into a quieter translucent panel
 * with restrained header typography and lighter close controls.
 */
import type React from 'react';
import { useEffect, useId, useRef, useState } from 'react';
import { cn } from '../../utils/cn';
import { useI18n } from '../../contexts/UiLanguageContext';
import { shouldApplySafariA11yGuard } from '../../hooks/useSafariInteractionReady';

let activeDrawerCount = 0;
const BACKDROP_INTERACTION_GUARD_MS = 420;
const DRAWER_READY_DELAY_MS = 80;
const DRAWER_WARMUP_INTERVAL_MS = 100;
const DRAWER_WARMUP_WINDOW_MS = 500;
const DRAWER_CLOSE_DELAY_MS = 190;

interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  width?: string;
  zIndex?: number;
  side?: 'left' | 'right';
  closeOnBackdropClick?: boolean;
  bodyClassName?: string;
}

export const Drawer: React.FC<DrawerProps> = ({
  isOpen,
  onClose,
  title,
  children,
  width = 'max-w-2xl',
  zIndex = 50,
  side = 'right',
  closeOnBackdropClick = true,
  bodyClassName,
}) => {
  const { t } = useI18n();
  const generatedId = useId();
  const [isMounted, setIsMounted] = useState(isOpen);
  const [uiState, setUiState] = useState<'open' | 'closed'>(isOpen ? 'open' : 'closed');
  const [isInteractionReady, setIsInteractionReady] = useState(isOpen);
  const shouldGuardA11y = shouldApplySafariA11yGuard();
  const backdropGuardRef = useRef(isOpen);
  const backdropGuardTimerRef = useRef<number | null>(null);
  const openMountFrameRef = useRef<number | null>(null);
  const openReadyFrameRef = useRef<number | null>(null);
  const interactionReadyTimerRef = useRef<number | null>(null);
  const closeTimerRef = useRef<number | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);


  useEffect(() => {
    if (closeTimerRef.current != null) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }

    if (!isOpen) {
      backdropGuardRef.current = false;
      setIsInteractionReady(false);
      if (backdropGuardTimerRef.current != null) {
        window.clearTimeout(backdropGuardTimerRef.current);
        backdropGuardTimerRef.current = null;
      }
      if (openMountFrameRef.current != null) {
        window.cancelAnimationFrame(openMountFrameRef.current);
        openMountFrameRef.current = null;
      }
      if (openReadyFrameRef.current != null) {
        window.cancelAnimationFrame(openReadyFrameRef.current);
        openReadyFrameRef.current = null;
      }
      if (interactionReadyTimerRef.current != null) {
        window.clearTimeout(interactionReadyTimerRef.current);
        interactionReadyTimerRef.current = null;
      }
      return;
    }

    backdropGuardRef.current = true;
    setIsInteractionReady(false);
    if (backdropGuardTimerRef.current != null) {
      window.clearTimeout(backdropGuardTimerRef.current);
      backdropGuardTimerRef.current = null;
    }
    if (openMountFrameRef.current != null) {
      window.cancelAnimationFrame(openMountFrameRef.current);
      openMountFrameRef.current = null;
    }
    if (openReadyFrameRef.current != null) {
      window.cancelAnimationFrame(openReadyFrameRef.current);
      openReadyFrameRef.current = null;
    }
    if (interactionReadyTimerRef.current != null) {
      window.clearTimeout(interactionReadyTimerRef.current);
      interactionReadyTimerRef.current = null;
    }

    backdropGuardTimerRef.current = window.setTimeout(() => {
      backdropGuardRef.current = false;
      backdropGuardTimerRef.current = null;
    }, BACKDROP_INTERACTION_GUARD_MS);

    openMountFrameRef.current = window.requestAnimationFrame(() => {
      openMountFrameRef.current = null;
      setIsMounted(true);
      openReadyFrameRef.current = window.requestAnimationFrame(() => {
        openReadyFrameRef.current = null;
        panelRef.current?.getBoundingClientRect();
        void panelRef.current?.offsetHeight;
        closeButtonRef.current?.getBoundingClientRect();
        void closeButtonRef.current?.offsetHeight;
        setUiState('open');
        interactionReadyTimerRef.current = window.setTimeout(() => {
          interactionReadyTimerRef.current = null;
          panelRef.current?.getBoundingClientRect();
          void panelRef.current?.offsetHeight;
          closeButtonRef.current?.getBoundingClientRect();
          void closeButtonRef.current?.offsetHeight;
          setIsInteractionReady(true);
        }, DRAWER_READY_DELAY_MS);
      });
    });

    return () => {
      if (backdropGuardTimerRef.current != null) {
        window.clearTimeout(backdropGuardTimerRef.current);
        backdropGuardTimerRef.current = null;
      }
      if (openMountFrameRef.current != null) {
        window.cancelAnimationFrame(openMountFrameRef.current);
        openMountFrameRef.current = null;
      }
      if (openReadyFrameRef.current != null) {
        window.cancelAnimationFrame(openReadyFrameRef.current);
        openReadyFrameRef.current = null;
      }
      if (interactionReadyTimerRef.current != null) {
        window.clearTimeout(interactionReadyTimerRef.current);
        interactionReadyTimerRef.current = null;
      }
    };
  }, [isOpen]);

  useEffect(() => {
    if (isOpen || !isMounted) {
      return;
    }

    queueMicrotask(() => setUiState('closed'));
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null;
      setIsMounted(false);
    }, DRAWER_CLOSE_DELAY_MS);

    return () => {
      if (closeTimerRef.current != null) {
        window.clearTimeout(closeTimerRef.current);
        closeTimerRef.current = null;
      }
    };
  }, [isMounted, isOpen]);

  useEffect(() => () => {
    if (backdropGuardTimerRef.current != null) {
      window.clearTimeout(backdropGuardTimerRef.current);
      backdropGuardTimerRef.current = null;
    }
    if (openMountFrameRef.current != null) {
      window.cancelAnimationFrame(openMountFrameRef.current);
      openMountFrameRef.current = null;
    }
    if (openReadyFrameRef.current != null) {
      window.cancelAnimationFrame(openReadyFrameRef.current);
      openReadyFrameRef.current = null;
    }
    if (interactionReadyTimerRef.current != null) {
      window.clearTimeout(interactionReadyTimerRef.current);
      interactionReadyTimerRef.current = null;
    }
    if (closeTimerRef.current != null) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!isMounted) {
      return;
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    activeDrawerCount++;
    if (activeDrawerCount === 1) {
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      activeDrawerCount--;
      if (activeDrawerCount === 0) {
        document.body.style.overflow = '';
      }
    };
  }, [isMounted, onClose]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    let elapsedMs = 0;
    const forceReflow = () => {
      panelRef.current?.getBoundingClientRect();
      void panelRef.current?.offsetHeight;
      closeButtonRef.current?.getBoundingClientRect();
      void closeButtonRef.current?.offsetHeight;
    };

    forceReflow();
    const intervalId = window.setInterval(() => {
      forceReflow();
      elapsedMs += DRAWER_WARMUP_INTERVAL_MS;
      if (elapsedMs >= DRAWER_WARMUP_WINDOW_MS) {
        window.clearInterval(intervalId);
      }
    }, DRAWER_WARMUP_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [isOpen]);

  const handleBackdropClick = () => {
    if (!closeOnBackdropClick) {
      return;
    }
    if (backdropGuardRef.current) {
      return;
    }
    onClose();
  };

  if (!isMounted) return null;

  const titleId = title ? `drawer-title-${generatedId}` : undefined;
  const sidePositionClass = side === 'left' ? 'left-0 justify-start' : 'right-0 justify-end';
  const borderClass = side === 'left' ? 'border-r' : 'border-l';
  const panelStateClass = side === 'left'
    ? uiState === 'open'
      ? 'translate-x-0 opacity-100'
      : '-translate-x-full opacity-0'
    : uiState === 'open'
      ? 'translate-x-0 opacity-100'
      : 'translate-x-full opacity-0';

  return (
    <div className="fixed inset-0 overflow-hidden overscroll-contain" style={{ zIndex }} role="presentation">
      {/* Backdrop */}
      <button
        type="button"
        aria-label={t('common.closeDrawer')}
        data-testid="drawer-backdrop"
        data-state={uiState}
        className={cn(
          'absolute inset-0 border-0 bg-black/60 p-0 transition-opacity duration-200 ease-out',
          uiState === 'open' && isInteractionReady ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0',
        )}
        onClick={handleBackdropClick}
      />

      <div className={cn('drawer__frame absolute inset-y-0 flex w-full', sidePositionClass, width)}>
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          aria-hidden={shouldGuardA11y && !isInteractionReady ? true : undefined}
          aria-live={shouldGuardA11y ? (isInteractionReady ? 'polite' : 'off') : undefined}
          className={cn(
            'drawer__panel relative flex h-full w-full flex-col bg-white/[0.02] backdrop-blur-sm transition-all duration-200 ease-out',
            borderClass,
            'border-white/5',
            isInteractionReady ? 'pointer-events-auto' : 'pointer-events-none',
            panelStateClass,
          )}
          data-state={uiState}
        >
          <div className="drawer__header flex items-center justify-between border-b border-white/10 px-4 py-3 sm:px-5 [padding-top:max(0.9rem,env(safe-area-inset-top))]">
            {title ? (
              <h2 id={titleId} className="drawer__title text-[11px] font-semibold uppercase tracking-[0.16em] text-secondary-text">
                {title}
              </h2>
            ) : <div />}
            <button
              ref={closeButtonRef}
              type="button"
              onClick={onClose}
              className="drawer__close inline-flex size-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] text-secondary-text transition-colors hover:border-white/20 hover:bg-white/[0.06] hover:text-foreground"
              aria-label={t('common.closeDrawer')}
            >
              <svg className="size-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div
            className={cn(
              'drawer__body flex h-full min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain no-scrollbar px-4 py-4 sm:px-5 sm:py-5 [padding-bottom:max(1rem,env(safe-area-inset-bottom))] [-webkit-overflow-scrolling:touch]',
              bodyClassName,
            )}
          >
            {children}
          </div>
        </div>
      </div>
    </div>
  );
};
