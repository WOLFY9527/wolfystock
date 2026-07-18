/**
 * Paper workbench drawer: preserves mounting, focus escape, and body scroll
 * locking while using the shared surface, border, and typography tokens.
 */
import type React from 'react';
import { useEffect, useEffectEvent, useId, useReducer, useRef } from 'react';
import { cn } from '../../utils/cn';
import { useI18n } from '../../contexts/UiLanguageContext';
import { shouldApplySafariA11yGuard } from '../../hooks/useSafariInteractionReady';

const BACKDROP_INTERACTION_GUARD_MS = 420;
const DRAWER_READY_DELAY_MS = 80;
const DRAWER_WARMUP_INTERVAL_MS = 100;
const DRAWER_WARMUP_WINDOW_MS = 500;
const DRAWER_CLOSE_DELAY_MS = 190;
const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

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

function getFocusableElements(container: HTMLElement | null): HTMLElement[] {
  if (!container) {
    return [];
  }
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter((element) => (
    isValidFocusCandidate(element, container)
  ));
}

function isHiddenOrInert(element: HTMLElement, boundary?: HTMLElement): boolean {
  let current: HTMLElement | null = element;
  while (current) {
    if (
      current.hidden
      || current.hasAttribute('inert')
      || current.getAttribute('aria-hidden') === 'true'
    ) {
      return true;
    }

    const style = window.getComputedStyle(current);
    if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse') {
      return true;
    }

    if (current === boundary) {
      return false;
    }
    current = current.parentElement;
  }

  return boundary != null;
}

function isValidFocusCandidate(element: HTMLElement | null, boundary?: HTMLElement): element is HTMLElement {
  return Boolean(
    element
    && element.isConnected
    && element.ownerDocument === document
    && (!boundary || boundary.contains(element))
    && element.tabIndex >= 0
    && !element.matches(':disabled')
    && element.getAttribute('aria-disabled') !== 'true'
    && !isHiddenOrInert(element, boundary),
  );
}

function focusContainer(container: HTMLElement): void {
  if (container.isConnected && !isHiddenOrInert(container)) {
    container.focus({ preventScroll: true });
  }
}

interface ModalOverlayEntry {
  root: HTMLElement;
  container: HTMLElement;
  dismiss: () => void;
  returnFocus: HTMLElement | null;
  getLayer: () => number;
}

const modalOverlayStack: ModalOverlayEntry[] = [];
const managedInertElements = new Set<HTMLElement>();
let bodyOverflowBeforeModal: string | null = null;
let topModalOverlay: ModalOverlayEntry | undefined;

function selectTopOverlay(): ModalOverlayEntry | undefined {
  return modalOverlayStack.reduce<ModalOverlayEntry | undefined>((topOverlay, entry) => {
    if (!topOverlay || entry.getLayer() > topOverlay.getLayer()) {
      return entry;
    }
    if (entry.getLayer() < topOverlay.getLayer() || entry.root === topOverlay.root) {
      return topOverlay;
    }
    const position = topOverlay.root.compareDocumentPosition(entry.root);
    return position & Node.DOCUMENT_POSITION_FOLLOWING ? entry : topOverlay;
  }, undefined);
}

function getTopOverlay(): ModalOverlayEntry | undefined {
  return topModalOverlay;
}

function restoreManagedInertState(): void {
  managedInertElements.forEach((element) => {
    element.removeAttribute('inert');
  });
  managedInertElements.clear();
}

function isolateTopOverlay(): void {
  restoreManagedInertState();
  const topOverlay = getTopOverlay();
  if (!topOverlay?.root.isConnected) {
    return;
  }

  let activeBranch = topOverlay.root;
  while (activeBranch.parentElement) {
    const parent = activeBranch.parentElement;
    Array.from(parent.children).forEach((sibling) => {
      if (sibling instanceof HTMLElement && sibling !== activeBranch && !sibling.hasAttribute('inert')) {
        sibling.setAttribute('inert', '');
        managedInertElements.add(sibling);
      }
    });
    if (parent === document.body) {
      break;
    }
    activeBranch = parent;
  }
}

function refreshModalOverlayOrder(): void {
  topModalOverlay = selectTopOverlay();
  isolateTopOverlay();
}

function focusOverlayBoundary(entry: ModalOverlayEntry, fromEnd = false): void {
  const focusableElements = getFocusableElements(entry.container);
  const target = fromEnd ? focusableElements.at(-1) : focusableElements[0];
  if (target) {
    target.focus({ preventScroll: true });
    return;
  }
  focusContainer(entry.container);
}

function handleModalKeyDown(event: KeyboardEvent): void {
  const topOverlay = getTopOverlay();
  if (!topOverlay) {
    return;
  }

  if (event.key === 'Escape') {
    event.preventDefault();
    event.stopPropagation();
    topOverlay.dismiss();
    return;
  }

  if (event.key !== 'Tab') {
    return;
  }

  const focusableElements = getFocusableElements(topOverlay.container);
  const activeElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const activeIndex = activeElement
    ? focusableElements.findIndex((element) => element === activeElement)
    : -1;
  const isOutside = !activeElement || !topOverlay.container.contains(activeElement);
  const isBoundary = event.shiftKey
    ? activeIndex <= 0
    : activeIndex === -1 || activeIndex >= focusableElements.length - 1;

  if (focusableElements.length === 0 || isOutside || isBoundary) {
    event.preventDefault();
    focusOverlayBoundary(topOverlay, event.shiftKey);
  }
}

function registerModalOverlay(entry: ModalOverlayEntry): () => void {
  if (modalOverlayStack.length === 0) {
    bodyOverflowBeforeModal = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', handleModalKeyDown, true);
  }
  modalOverlayStack.push(entry);
  refreshModalOverlayOrder();

  return () => {
    const index = modalOverlayStack.indexOf(entry);
    if (index === -1) {
      return;
    }
    const wasTopOverlay = topModalOverlay === entry;
    modalOverlayStack.splice(index, 1);
    refreshModalOverlayOrder();

    if (modalOverlayStack.length === 0) {
      document.removeEventListener('keydown', handleModalKeyDown, true);
      if (bodyOverflowBeforeModal === null) {
        throw new Error('Modal body overflow snapshot is missing during stack cleanup.');
      }
      document.body.style.overflow = bodyOverflowBeforeModal;
      bodyOverflowBeforeModal = null;
    }

    if (!wasTopOverlay) {
      return;
    }

    restoreInvokingFocus(entry.returnFocus);
  };
}

function focusInitialModalTarget(
  container: HTMLElement | null,
  explicitTargets: Array<HTMLElement | null>,
): void {
  const topOverlay = getTopOverlay();
  if (!container || topOverlay?.container !== container) {
    return;
  }
  const target = explicitTargets.find((element) => isValidFocusCandidate(element, container))
    ?? getFocusableElements(container)[0];
  if (target) {
    target.focus({ preventScroll: true });
    return;
  }
  focusContainer(container);
}

function restoreInvokingFocus(target: HTMLElement | null): void {
  const topOverlay = getTopOverlay();
  if (
    isValidFocusCandidate(target)
    && (!topOverlay || topOverlay.container.contains(target))
  ) {
    target.focus({ preventScroll: true });
    return;
  }
  if (topOverlay) {
    focusOverlayBoundary(topOverlay);
  }
}

interface ModalOverlayAuthority {
  register: typeof registerModalOverlay;
  focusInitial: typeof focusInitialModalTarget;
}

type DrawerComponent = React.FC<DrawerProps> & {
  overlayStack: ModalOverlayAuthority;
};

export const Drawer = (({
  isOpen,
  onClose,
  title,
  children,
  width = 'max-w-2xl',
  zIndex = 50,
  side = 'right',
  closeOnBackdropClick = true,
  bodyClassName,
}: DrawerProps) => {
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
  const zIndexRef = useRef(zIndex);
  const overlayRootRef = useRef<HTMLDivElement | null>(null);
  const panelRef = useRef<HTMLDialogElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const hasCapturedFocusRef = useRef(false);
  const hasAppliedInitialFocusRef = useRef(false);
  const handleClose = useEffectEvent(onClose);
  zIndexRef.current = zIndex;

  useEffect(() => {
    let isCancelled = false;

    clearTimeoutRef(closeTimerRef);

    if (!isOpen) {
      hasAppliedInitialFocusRef.current = false;
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
    if (!isOpen || hasCapturedFocusRef.current) {
      return;
    }
    previousFocusRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    hasCapturedFocusRef.current = true;
  }, [isOpen]);

  useEffect(() => {
    if (!state.isMounted) {
      return;
    }

    const root = overlayRootRef.current;
    const panel = panelRef.current;
    if (!root || !panel) {
      throw new Error('Mounted Drawer is missing its overlay root or dialog container.');
    }
    const unregister = registerModalOverlay({
      root,
      container: panel,
      dismiss: handleClose,
      returnFocus: previousFocusRef.current,
      getLayer: () => zIndexRef.current,
    });

    return () => {
      unregister();
      previousFocusRef.current = null;
      hasCapturedFocusRef.current = false;
      hasAppliedInitialFocusRef.current = false;
    };
  }, [state.isMounted]);

  useEffect(() => {
    if (state.isMounted) {
      refreshModalOverlayOrder();
    }
  }, [state.isMounted, zIndex]);

  useEffect(() => {
    if (!isOpen || !state.isInteractionReady || hasAppliedInitialFocusRef.current) {
      return;
    }

    hasAppliedInitialFocusRef.current = true;
    const panel = panelRef.current;
    const activeElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (panel && isValidFocusCandidate(activeElement, panel)) {
      return;
    }

    focusInitialModalTarget(panel, [closeButtonRef.current]);
  }, [isOpen, state.isInteractionReady]);

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

  const handleBackdropPointerDown = (event: React.PointerEvent<HTMLButtonElement>) => {
    if (!closeOnBackdropClick) {
      return;
    }
    if (backdropGuardRef.current) {
      return;
    }
    event.preventDefault();
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
    <div ref={overlayRootRef} className="fixed inset-0 overflow-hidden overscroll-contain" style={{ zIndex }} role="presentation">
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
        onPointerDown={handleBackdropPointerDown}
      />

      <div className={cn('drawer__frame absolute inset-y-0 flex w-full', sidePositionClass, width)}>
        <dialog
          ref={panelRef}
          open
          aria-labelledby={titleId}
          aria-modal="true"
          aria-hidden={shouldGuardA11y && !state.isInteractionReady ? true : undefined}
          aria-live={shouldGuardA11y ? (state.isInteractionReady ? 'polite' : 'off') : undefined}
          tabIndex={-1}
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
}) as DrawerComponent;

Drawer.overlayStack = {
  register: registerModalOverlay,
  focusInitial: focusInitialModalTarget,
};
