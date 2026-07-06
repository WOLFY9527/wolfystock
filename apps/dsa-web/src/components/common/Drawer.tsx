/**
 * Paper workbench drawer: preserves mounting, focus escape, and body scroll
 * locking while using the shared surface, border, and typography tokens.
 */
import type React from 'react';
import { useEffect, useEffectEvent, useId, useReducer, useRef } from 'react';
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

interface DrawerState {
  isMounted: boolean;
  uiState: 'open' | 'closed';
  isInteractionReady: boolean;
}

type DrawerAction =
  | { type: 'prepareToOpen' }
  | { type: 'openVisible' }
  | { type: 'enableInteraction' }
  | { type: 'prepareToClose' }
  | { type: 'finishClose' };

const createInitialDrawerState = (isOpen: boolean): DrawerState => ({
  isMounted: isOpen,
  uiState: isOpen ? 'open' : 'closed',
  isInteractionReady: isOpen,
});

function drawerReducer(state: DrawerState, action: DrawerAction): DrawerState {
  switch (action.type) {
    case 'prepareToOpen':
      return {
        isMounted: true,
        uiState: state.isMounted ? state.uiState : 'closed',
        isInteractionReady: false,
      };
    case 'openVisible':
      return {
        ...state,
        uiState: 'open',
      };
    case 'enableInteraction':
      return {
        ...state,
        isInteractionReady: true,
      };
    case 'prepareToClose':
      return {
        ...state,
        uiState: 'closed',
        isInteractionReady: false,
      };
    case 'finishClose':
      return {
        ...state,
        isMounted: false,
      };
    default:
      return state;
  }
}

function clearTimeoutRef(timerRef: { current: number | null }) {
  if (timerRef.current != null) {
    window.clearTimeout(timerRef.current);
    timerRef.current = null;
  }
}

function clearAnimationFrameRef(frameRef: { current: number | null }) {
  if (frameRef.current != null) {
    window.cancelAnimationFrame(frameRef.current);
    frameRef.current = null;
  }
}

function forceDrawerReflow(
  panel: HTMLDialogElement | null,
  closeButton: HTMLButtonElement | null,
) {
  panel?.getBoundingClientRect();
  void panel?.offsetHeight;
  closeButton?.getBoundingClientRect();
  void closeButton?.offsetHeight;
}

function incrementActiveDrawerCount() {
  activeDrawerCount += 1;
  return activeDrawerCount;
}

function decrementActiveDrawerCount() {
  activeDrawerCount = Math.max(0, activeDrawerCount - 1);
  return activeDrawerCount;
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
  const [state, dispatch] = useReducer(drawerReducer, isOpen, createInitialDrawerState);
  const shouldGuardA11y = shouldApplySafariA11yGuard();
  const backdropGuardRef = useRef(isOpen);
  const backdropGuardTimerRef = useRef<number | null>(null);
  const openMountFrameRef = useRef<number | null>(null);
  const openReadyFrameRef = useRef<number | null>(null);
  const interactionReadyTimerRef = useRef<number | null>(null);
  const closeTimerRef = useRef<number | null>(null);
  const panelRef = useRef<HTMLDialogElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const handleEscapeKey = useEffectEvent((event: KeyboardEvent) => {
    if (event.key === 'Escape') {
      onClose();
    }
  });

  useEffect(() => {
    let isCancelled = false;

    clearTimeoutRef(closeTimerRef);

    if (!isOpen) {
      backdropGuardRef.current = false;
      clearTimeoutRef(backdropGuardTimerRef);
      clearAnimationFrameRef(openMountFrameRef);
      clearAnimationFrameRef(openReadyFrameRef);
      clearTimeoutRef(interactionReadyTimerRef);
      return;
    }

    backdropGuardRef.current = true;
    clearTimeoutRef(backdropGuardTimerRef);
    clearAnimationFrameRef(openMountFrameRef);
    clearAnimationFrameRef(openReadyFrameRef);
    clearTimeoutRef(interactionReadyTimerRef);

    queueMicrotask(() => {
      if (isCancelled) {
        return;
      }

      dispatch({ type: 'prepareToOpen' });
    });

    backdropGuardTimerRef.current = window.setTimeout(() => {
      backdropGuardRef.current = false;
      backdropGuardTimerRef.current = null;
    }, BACKDROP_INTERACTION_GUARD_MS);

    openMountFrameRef.current = window.requestAnimationFrame(() => {
      openMountFrameRef.current = null;
      openReadyFrameRef.current = window.requestAnimationFrame(() => {
        openReadyFrameRef.current = null;
        forceDrawerReflow(panelRef.current, closeButtonRef.current);
        dispatch({ type: 'openVisible' });
        interactionReadyTimerRef.current = window.setTimeout(() => {
          interactionReadyTimerRef.current = null;
          forceDrawerReflow(panelRef.current, closeButtonRef.current);
          dispatch({ type: 'enableInteraction' });
        }, DRAWER_READY_DELAY_MS);
      });
    });

    return () => {
      isCancelled = true;
      clearTimeoutRef(backdropGuardTimerRef);
      clearAnimationFrameRef(openMountFrameRef);
      clearAnimationFrameRef(openReadyFrameRef);
      clearTimeoutRef(interactionReadyTimerRef);
    };
  }, [isOpen]);

  useEffect(() => {
    let isCancelled = false;

    if (isOpen || !state.isMounted) {
      return;
    }

    queueMicrotask(() => {
      if (isCancelled) {
        return;
      }

      dispatch({ type: 'prepareToClose' });
    });
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null;
      dispatch({ type: 'finishClose' });
    }, DRAWER_CLOSE_DELAY_MS);

    return () => {
      isCancelled = true;
      clearTimeoutRef(closeTimerRef);
    };
  }, [state.isMounted, isOpen]);

  useEffect(() => () => {
    clearTimeoutRef(backdropGuardTimerRef);
    clearAnimationFrameRef(openMountFrameRef);
    clearAnimationFrameRef(openReadyFrameRef);
    clearTimeoutRef(interactionReadyTimerRef);
    clearTimeoutRef(closeTimerRef);
  }, []);

  useEffect(() => {
    if (!state.isMounted) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      handleEscapeKey(event);
    };

    document.addEventListener('keydown', onKeyDown);
    if (incrementActiveDrawerCount() === 1) {
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      if (decrementActiveDrawerCount() === 0) {
        document.body.style.overflow = '';
      }
    };
  }, [state.isMounted]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    let elapsedMs = 0;
    const forceReflow = () => {
      forceDrawerReflow(panelRef.current, closeButtonRef.current);
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

  if (!state.isMounted) return null;

  const titleId = title ? `drawer-title-${generatedId}` : undefined;
  const sidePositionClass = side === 'left' ? 'left-0 justify-start' : 'right-0 justify-end';
  const borderClass = side === 'left' ? 'border-r' : 'border-l';
  const panelStateClass = side === 'left'
    ? state.uiState === 'open'
      ? 'translate-x-0 opacity-100'
      : '-translate-x-full opacity-0'
    : state.uiState === 'open'
      ? 'translate-x-0 opacity-100'
      : 'translate-x-full opacity-0';

  return (
    <div className="fixed inset-0 overflow-hidden overscroll-contain" style={{ zIndex }} role="presentation">
      {/* Backdrop */}
      <button
        type="button"
        aria-label={t('common.closeDrawer')}
        data-testid="drawer-backdrop"
        data-state={state.uiState}
        className={cn(
          'absolute inset-0 border-0 bg-[color:var(--theme-overlay-backdrop)] p-0 transition-opacity duration-200 ease-out',
          state.uiState === 'open' && state.isInteractionReady ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0',
        )}
        onClick={handleBackdropClick}
      />

      <div className={cn('drawer__frame absolute inset-y-0 flex w-full', sidePositionClass, width)}>
        <dialog
          ref={panelRef}
          open
          aria-labelledby={titleId}
          aria-hidden={shouldGuardA11y && !state.isInteractionReady ? true : undefined}
          aria-live={shouldGuardA11y ? (state.isInteractionReady ? 'polite' : 'off') : undefined}
          className={cn(
            'drawer__panel relative m-0 flex h-full max-h-none w-full max-w-none flex-col border-0 bg-[color:var(--surface)] p-0 transition-all duration-200 ease-out',
            borderClass,
            'border-[color:var(--line)]',
            state.isInteractionReady ? 'pointer-events-auto' : 'pointer-events-none',
            panelStateClass,
          )}
          data-state={state.uiState}
        >
          <div className="drawer__header flex items-center justify-between border-b border-[color:var(--line)] px-4 py-3 sm:px-5 [padding-top:max(0.9rem,env(safe-area-inset-top))]">
            {title ? (
              <h2 id={titleId} className="drawer__title text-[11px] font-semibold uppercase tracking-[0.16em] text-secondary-text">
                {title}
              </h2>
            ) : <div />}
            <button
              ref={closeButtonRef}
              type="button"
              onClick={onClose}
              className="drawer__close inline-flex size-9 items-center justify-center rounded-xl border border-[color:var(--line)] bg-[color:var(--surface-3)] text-secondary-text transition-colors hover:border-[color:var(--sage)] hover:bg-[color:var(--surface-2)] hover:text-foreground"
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
        </dialog>
      </div>
    </div>
  );
};
