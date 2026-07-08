import type React from 'react';
import { useEffect, useId, useRef } from 'react';
import { Lock } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { TerminalButton } from '../terminal/TerminalPrimitives';
import { useI18n } from '../../contexts/UiLanguageContext';
import { translate } from '../../i18n/core';
import { buildLocalizedPath, parseLocaleFromPathname } from '../../utils/localeRouting';

type AuthGuardOverlayProps = {
  moduleName: string;
  children?: React.ReactNode;
};

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

function getFocusableElements(container: HTMLElement | null): HTMLElement[] {
  if (!container) {
    return [];
  }
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter((element) => (
    element.tabIndex >= 0 && !element.closest('[aria-hidden="true"]')
  ));
}

export const AuthGuardOverlay: React.FC<AuthGuardOverlayProps> = ({ moduleName, children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { language } = useI18n();
  const titleId = useId();
  const bodyId = useId();
  const dialogRef = useRef<HTMLElement | null>(null);
  const cardRef = useRef<HTMLElement | null>(null);
  const loginButtonRef = useRef<HTMLButtonElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const displayLocale = routeLocale || language;
  const currentRoute = `${location.pathname}${location.search}${location.hash}`;
  const loginPath = routeLocale
    ? buildLocalizedPath(`/login?redirect=${encodeURIComponent(currentRoute)}`, routeLocale)
    : `/login?redirect=${encodeURIComponent(currentRoute)}`;
  const homePath = routeLocale ? buildLocalizedPath('/', routeLocale) : '/';
  const title = translate(displayLocale, 'common.authRequiredState.title');
  const body = translate(displayLocale, 'common.authRequiredState.body');
  const followup = translate(displayLocale, 'common.authRequiredState.followup');
  const buttonLabel = translate(displayLocale, 'common.authRequiredState.primaryAction');
  const safeExitLabel = displayLocale === 'en' ? 'Return home' : '返回首页';

  useEffect(() => {
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const initialFocusTarget = loginButtonRef.current ?? getFocusableElements(cardRef.current)[0] ?? dialogRef.current;
    initialFocusTarget?.focus({ preventScroll: true });

    return () => {
      const previousFocus = previousFocusRef.current;
      if (previousFocus && document.contains(previousFocus)) {
        previousFocus.focus({ preventScroll: true });
      }
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        if (!cardRef.current?.contains(document.activeElement)) {
          loginButtonRef.current?.focus({ preventScroll: true });
        }
        return;
      }

      if (event.key !== 'Tab') {
        return;
      }

      const focusableElements = getFocusableElements(cardRef.current);
      const fallbackFocusTarget = loginButtonRef.current ?? dialogRef.current;
      if (focusableElements.length === 0) {
        event.preventDefault();
        fallbackFocusTarget?.focus({ preventScroll: true });
        return;
      }

      event.preventDefault();
      const activeElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      const activeIndex = activeElement ? focusableElements.findIndex((element) => element === activeElement) : -1;
      const nextIndex = event.shiftKey
        ? activeIndex <= 0 ? focusableElements.length - 1 : activeIndex - 1
        : activeIndex === -1 || activeIndex >= focusableElements.length - 1 ? 0 : activeIndex + 1;

      focusableElements[nextIndex]?.focus({ preventScroll: true });
    };

    document.addEventListener('keydown', handleKeyDown, true);
    return () => document.removeEventListener('keydown', handleKeyDown, true);
  }, []);

  return (
    <section
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={bodyId}
      tabIndex={-1}
      data-testid="auth-guard-overlay"
      className="fixed inset-0 z-[80] grid place-items-center overflow-hidden px-4 py-6 sm:px-6"
    >
      {children ? (
        <div
          data-testid="auth-guard-backdrop-content"
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 select-none overflow-hidden blur-[2px] saturate-50"
        >
          {children}
        </div>
      ) : (
        <div
          data-testid="auth-guard-ambient-backdrop"
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 overflow-hidden opacity-80"
        >
          <div className="absolute inset-x-4 top-14 mx-auto grid max-w-6xl gap-4 sm:top-20">
            <div className="h-14 rounded-[14px] border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]" />
            <div className="grid gap-4 md:grid-cols-[minmax(0,1.7fr)_minmax(18rem,0.8fr)]">
              <div className="min-h-[26rem] rounded-[14px] border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-4">
                <div className="mb-5 h-8 w-48 rounded-full bg-[var(--wolfy-surface-inset)]" />
                <div className="grid gap-3">
                  <div className="h-12 rounded-[10px] bg-[var(--wolfy-surface-inset-lift)]" />
                  <div className="h-12 rounded-[10px] bg-[var(--wolfy-surface-inset)]" />
                  <div className="h-12 rounded-[10px] bg-[var(--wolfy-surface-inset-lift)]" />
                  <div className="h-12 rounded-[10px] bg-[var(--wolfy-surface-inset)]" />
                </div>
              </div>
              <div className="hidden min-h-[26rem] rounded-[14px] border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-4 md:block">
                <div className="mb-4 h-7 w-32 rounded-full bg-[var(--wolfy-surface-inset)]" />
                <div className="space-y-3">
                  <div className="h-16 rounded-[10px] bg-[var(--wolfy-surface-inset-lift)]" />
                  <div className="h-16 rounded-[10px] bg-[var(--wolfy-surface-inset)]" />
                  <div className="h-16 rounded-[10px] bg-[var(--wolfy-surface-inset-lift)]" />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div
        data-testid="auth-guard-scrim"
        className="absolute inset-0 bg-[color:rgb(37_34_29_/_0.34)] backdrop-blur-md"
        aria-hidden="true"
      />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_18%,rgba(212,165,116,0.18),transparent_34%),linear-gradient(180deg,rgba(255,253,248,0.12),transparent_42%)]" aria-hidden="true" />

      <section
        ref={cardRef}
        className="relative z-10 flex w-[min(92vw,28rem)] flex-col items-center overflow-hidden rounded-[18px] border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-elevated)] px-5 py-6 text-center shadow-[var(--wolfy-shadow-console)] sm:px-6 sm:py-7"
        data-testid="auth-guard-card"
      >
        <div className="mx-auto mb-5 flex size-11 items-center justify-center rounded-full border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-inset-lift)] text-[color:var(--wolfy-text-muted)]">
          <Lock className="size-4" aria-hidden="true" />
        </div>
        <h2 id={titleId} className="text-base font-semibold text-[color:var(--wolfy-text-primary)]">{title}</h2>
        <div id={bodyId} className="mx-auto mt-3 max-w-[22rem] space-y-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
          <p>{body}</p>
          <p>{followup}</p>
        </div>
        <div className="mt-7 grid w-full gap-2 sm:grid-cols-2">
          <TerminalButton
            ref={loginButtonRef}
            variant="primary"
            className="h-11 w-full rounded-[10px] text-sm"
            aria-label={`${buttonLabel} ${moduleName}`.trim()}
            onClick={() => navigate(loginPath)}
          >
            {buttonLabel}
          </TerminalButton>
          <TerminalButton
            variant="secondary"
            className="h-11 w-full rounded-[10px] text-sm"
            onClick={() => navigate(homePath)}
          >
            {safeExitLabel}
          </TerminalButton>
        </div>
      </section>
    </section>
  );
};
