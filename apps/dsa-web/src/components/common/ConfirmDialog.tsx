/**
 * Paper workbench dialog: preserves the existing confirmation flow and portal
 * behavior while using shared modal, field, and action tokens.
 */
import type React from 'react';
import { useEffect, useEffectEvent, useId, useReducer, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Button } from './Button';
import { useI18n } from '../../contexts/UiLanguageContext';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  isDanger?: boolean;
  confirmationLabel?: string;
  confirmationHint?: string;
  confirmationValue?: string;
  confirmationPhrase?: string;
  onConfirmationValueChange?: (value: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
}

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

function getFocusableElements(container: HTMLElement | null): HTMLElement[] {
  if (!container) {
    return [];
  }
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter((element) => (
    element.tabIndex >= 0
    && element.getAttribute('aria-disabled') !== 'true'
    && !element.closest('[aria-hidden="true"]')
  ));
}

type DialogUiState = 'open' | 'closed';

type DialogState = {
  isMounted: boolean;
  uiState: DialogUiState;
};

type DialogAction =
  | { type: 'mount' }
  | { type: 'open' }
  | { type: 'close' }
  | { type: 'unmount' };

function createDialogState(isOpen: boolean): DialogState {
  return {
    isMounted: isOpen,
    uiState: isOpen ? 'open' : 'closed',
  };
}

function dialogReducer(state: DialogState, action: DialogAction): DialogState {
  if (action.type === 'mount') {
    if (state.isMounted) {
      return state;
    }
    return { isMounted: true, uiState: 'closed' };
  }

  if (action.type === 'open') {
    if (!state.isMounted || state.uiState === 'open') {
      return state;
    }
    return { ...state, uiState: 'open' };
  }

  if (action.type === 'close') {
    if (!state.isMounted || state.uiState === 'closed') {
      return state;
    }
    return { ...state, uiState: 'closed' };
  }

  if (!state.isMounted) {
    return state;
  }

  return { isMounted: false, uiState: 'closed' };
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  message,
  confirmText,
  cancelText,
  isDanger = false,
  confirmationLabel,
  confirmationHint,
  confirmationValue = '',
  confirmationPhrase,
  onConfirmationValueChange,
  onConfirm,
  onCancel,
}) => {
  const { t } = useI18n();
  const [{ isMounted, uiState }, dispatch] = useReducer(dialogReducer, isOpen, createDialogState);
  const handleCancel = useEffectEvent(onCancel);
  const titleId = useId();
  const messageId = useId();
  const surfaceRef = useRef<HTMLDivElement | null>(null);
  const cancelButtonRef = useRef<HTMLButtonElement | null>(null);
  const confirmationInputRef = useRef<HTMLInputElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const hasCapturedFocusRef = useRef(false);
  const hasAppliedInitialFocusRef = useRef(false);

  useEffect(() => {
    let mountFrame: number | null = null;
    let openFrame: number | null = null;
    let closeTimer: number | null = null;
    const cancelFrame = typeof window.cancelAnimationFrame === 'function'
      ? window.cancelAnimationFrame.bind(window)
      : window.clearTimeout.bind(window);

    if (isOpen) {
      mountFrame = window.requestAnimationFrame(() => {
        dispatch({ type: 'mount' });
        openFrame = window.requestAnimationFrame(() => {
          dispatch({ type: 'open' });
        });
      });
    } else if (isMounted) {
      queueMicrotask(() => {
        dispatch({ type: 'close' });
      });
      closeTimer = window.setTimeout(() => {
        dispatch({ type: 'unmount' });
      }, 180);
    }

    return () => {
      if (mountFrame !== null) {
        cancelFrame(mountFrame);
      }
      if (openFrame !== null) {
        cancelFrame(openFrame);
      }
      if (closeTimer !== null) {
        window.clearTimeout(closeTimer);
      }
    };
  }, [isOpen, isMounted]);

  useEffect(() => {
    if (!isMounted) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        handleCancel();
        return;
      }

      if (event.key !== 'Tab') {
        return;
      }

      const surface = surfaceRef.current;
      const focusableElements = getFocusableElements(surface);
      const fallbackFocusTarget = cancelButtonRef.current ?? surface;
      if (!surface || !fallbackFocusTarget) {
        return;
      }

      if (focusableElements.length === 0) {
        event.preventDefault();
        fallbackFocusTarget.focus({ preventScroll: true });
        return;
      }

      const activeElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      if (activeElement && !surface.contains(activeElement)) {
        const activeModal = activeElement.closest<HTMLElement>('[aria-modal="true"]');
        if (activeModal && activeModal !== surface) {
          return;
        }
        event.preventDefault();
        focusableElements[0]?.focus({ preventScroll: true });
        return;
      }

      const activeIndex = activeElement ? focusableElements.findIndex((element) => element === activeElement) : -1;
      if (event.shiftKey) {
        if (activeIndex <= 0) {
          event.preventDefault();
          focusableElements[focusableElements.length - 1]?.focus({ preventScroll: true });
        }
        return;
      }

      if (activeIndex === -1 || activeIndex >= focusableElements.length - 1) {
        event.preventDefault();
        focusableElements[0]?.focus({ preventScroll: true });
      }
    };

    document.addEventListener('keydown', handleKeyDown, true);
    return () => {
      document.removeEventListener('keydown', handleKeyDown, true);
    };
  }, [isMounted]);

  useEffect(() => {
    if (!isOpen) {
      hasAppliedInitialFocusRef.current = false;
      return;
    }

    if (!hasCapturedFocusRef.current) {
      previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      hasCapturedFocusRef.current = true;
    }
  }, [isOpen]);

  const normalizedTypedValue = String(confirmationValue || '');
  const requiresTypedConfirmation = Boolean(confirmationPhrase);
  const typedConfirmationMatched = !requiresTypedConfirmation || normalizedTypedValue === confirmationPhrase;

  useEffect(() => {
    if (!isOpen || !isMounted || hasAppliedInitialFocusRef.current) {
      return;
    }

    hasAppliedInitialFocusRef.current = true;
    const focusTarget = confirmationInputRef.current
      ?? cancelButtonRef.current
      ?? getFocusableElements(surfaceRef.current)[0]
      ?? surfaceRef.current;
    focusTarget?.focus({ preventScroll: true });
  }, [isOpen, isMounted]);

  useEffect(() => {
    if (isOpen || !hasCapturedFocusRef.current) {
      return;
    }

    const previousFocus = previousFocusRef.current;
    previousFocusRef.current = null;
    hasCapturedFocusRef.current = false;
    hasAppliedInitialFocusRef.current = false;
    if (previousFocus && document.contains(previousFocus)) {
      previousFocus.focus({ preventScroll: true });
    }
  }, [isOpen]);

  if (!isMounted) return null;

  const dialog = (
    <div
      className={`confirm-dialog fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-200 ease-out ${
        uiState === 'open' ? 'opacity-100' : 'opacity-0'
      }`}
      data-state={uiState}
    >
      <button
        type="button"
        aria-hidden="true"
        tabIndex={-1}
        className="theme-overlay-backdrop absolute inset-0 border-0 p-0"
        onClick={onCancel}
      />
      <div
        ref={surfaceRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={messageId}
        tabIndex={-1}
        className={`confirm-dialog__surface theme-modal-panel relative mx-4 w-full max-w-sm rounded-[var(--cohere-radius-medium)] border p-6 transition-all duration-200 ease-out ${
          uiState === 'open'
            ? 'translate-y-0 scale-100 opacity-100'
            : 'translate-y-1.5 scale-[0.985] opacity-0'
        }`}
        data-state={uiState}
      >
        <p className="confirm-dialog__eyebrow label-uppercase text-secondary-text">
          {isDanger ? t('common.confirmationRequired') : t('common.confirmAction')}
        </p>
        <h3 id={titleId} className="confirm-dialog__title text-[1.125rem] font-normal tracking-[-0.02em] text-foreground">{title}</h3>
        <p id={messageId} className="confirm-dialog__message mb-6 mt-2 text-sm leading-6 text-secondary-text">
          {message}
        </p>
        {requiresTypedConfirmation ? (
          <div className="mb-6">
            <label className="mb-2 block text-sm font-medium text-foreground">
              {confirmationLabel ?? t('common.confirm')}
            </label>
            <input
              ref={confirmationInputRef}
              aria-label={confirmationLabel ?? t('common.confirm')}
              className="input-surface h-10 w-full rounded-[var(--theme-control-radius)] px-3 text-sm"
              value={normalizedTypedValue}
              onChange={(event) => onConfirmationValueChange?.(event.target.value)}
            />
            <p className="mt-2 text-xs text-muted-text">
              {confirmationHint ?? confirmationPhrase}
            </p>
          </div>
        ) : null}
        <div className="confirm-dialog__actions flex flex-wrap justify-end gap-2">
          <Button ref={cancelButtonRef} variant="ghost" size="sm" onClick={onCancel}>
            {cancelText ?? t('common.cancel')}
          </Button>
          <Button
            variant={isDanger ? 'danger-subtle' : 'primary'}
            size="sm"
            onClick={onConfirm}
            disabled={!typedConfirmationMatched}
          >
            {confirmText ?? t('common.confirm')}
          </Button>
        </div>
      </div>
    </div>
  );

  return createPortal(dialog, document.body);
};
