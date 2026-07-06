/**
 * Paper workbench dialog: preserves the existing confirmation flow and portal
 * behavior while using shared modal, field, and action tokens.
 */
import type React from 'react';
import { useEffect, useEffectEvent, useReducer } from 'react';
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
        handleCancel();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isMounted]);

  if (!isMounted) return null;
  const normalizedTypedValue = String(confirmationValue || '');
  const requiresTypedConfirmation = Boolean(confirmationPhrase);
  const typedConfirmationMatched = !requiresTypedConfirmation || normalizedTypedValue === confirmationPhrase;

  const dialog = (
    <div
      className={`confirm-dialog fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-200 ease-out ${
        uiState === 'open' ? 'opacity-100' : 'opacity-0'
      }`}
      data-state={uiState}
    >
      <button
        type="button"
        aria-label={cancelText ?? t('common.cancel')}
        className="theme-overlay-backdrop absolute inset-0 border-0 p-0"
        onClick={onCancel}
      />
      <div
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
        <h3 className="confirm-dialog__title text-[1.125rem] font-normal tracking-[-0.02em] text-foreground">{title}</h3>
        <p className="confirm-dialog__message mb-6 mt-2 text-sm leading-6 text-secondary-text">
          {message}
        </p>
        {requiresTypedConfirmation ? (
          <div className="mb-6">
            <label className="mb-2 block text-sm font-medium text-foreground">
              {confirmationLabel ?? t('common.confirm')}
            </label>
            <input
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
          <Button variant="ghost" size="sm" onClick={onCancel}>
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
