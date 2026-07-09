import type React from 'react';
import { useEffect, useId, useRef } from 'react';
import { ArrowRight, Lock } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
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

/**
 * Consumer product auth boundary for guest-protected research workbench routes.
 * Owns capability identity → reason → honest preview posture → safe actions.
 * Not an admin AccessGate; not a paywall or marketing landing.
 */
export const AuthGuardOverlay: React.FC<AuthGuardOverlayProps> = ({ moduleName, children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { language } = useI18n();
  const titleId = useId();
  const bodyId = useId();
  const dialogRef = useRef<HTMLElement | null>(null);
  const cardRef = useRef<HTMLElement | null>(null);
  const loginActionRef = useRef<HTMLAnchorElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const displayLocale = routeLocale || language;
  const currentRoute = `${location.pathname}${location.search}${location.hash}`;
  const loginPath = routeLocale
    ? buildLocalizedPath(`/login?redirect=${encodeURIComponent(currentRoute)}`, routeLocale)
    : `/login?redirect=${encodeURIComponent(currentRoute)}`;
  const marketPath = routeLocale ? buildLocalizedPath('/market-overview', routeLocale) : '/market-overview';
  const homePath = routeLocale ? buildLocalizedPath('/', routeLocale) : '/';

  const statusLabel = translate(displayLocale, 'common.authRequiredState.title');
  const reasonBody = translate(displayLocale, 'common.authRequiredState.body');
  const reasonFollowup = translate(displayLocale, 'common.authRequiredState.followup');
  const primaryLabel = translate(displayLocale, 'common.authRequiredState.primaryAction');
  const reasonLabel = translate(displayLocale, 'common.authRequiredState.reasonLabel');
  const previewLabel = translate(displayLocale, 'common.authRequiredState.previewLabel');
  const previewBody = translate(displayLocale, 'common.authRequiredState.previewBody');
  const secondaryLabel = translate(displayLocale, 'common.authRequiredState.secondaryAction');
  const safeExitLabel = translate(displayLocale, 'common.authRequiredState.safeExitAction');
  const eyebrow = translate(displayLocale, 'common.authRequiredState.eyebrow');
  const capabilitySummary = translate(displayLocale, 'common.authRequiredState.capabilitySummary', {
    module: moduleName,
  });

  useEffect(() => {
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const initialFocusTarget = loginActionRef.current ?? getFocusableElements(cardRef.current)[0] ?? dialogRef.current;
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
          loginActionRef.current?.focus({ preventScroll: true });
        }
        return;
      }

      if (event.key !== 'Tab') {
        return;
      }

      const focusableElements = getFocusableElements(cardRef.current);
      const fallbackFocusTarget = loginActionRef.current ?? dialogRef.current;
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
      data-boundary-family="consumer-protected"
      className="auth-guard-overlay fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto no-scrollbar overflow-x-hidden px-4 pb-6 pt-4 sm:px-6 sm:pb-8 sm:pt-8"
    >
      {children ? (
        <div
          data-testid="auth-guard-backdrop-content"
          aria-hidden="true"
          className="auth-guard-backdrop pointer-events-none absolute inset-0 select-none overflow-hidden blur-[1.5px] saturate-50"
        >
          {children}
        </div>
      ) : (
        <div
          data-testid="auth-guard-ambient-backdrop"
          aria-hidden="true"
          className="auth-guard-backdrop pointer-events-none absolute inset-0 overflow-hidden opacity-75"
        >
          <div className="absolute inset-x-4 top-12 mx-auto grid max-w-6xl gap-3 sm:top-16">
            <div className="h-12 rounded-[14px] border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]" />
            <div className="grid gap-3 md:grid-cols-[minmax(0,1.7fr)_minmax(16rem,0.8fr)]">
              <div className="min-h-[18rem] rounded-[14px] border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-4 sm:min-h-[22rem]">
                <div className="mb-4 h-7 w-40 rounded-full bg-[var(--wolfy-surface-inset)]" />
                <div className="grid gap-2.5">
                  <div className="h-11 rounded-[10px] bg-[var(--wolfy-surface-inset-lift)]" />
                  <div className="h-11 rounded-[10px] bg-[var(--wolfy-surface-inset)]" />
                  <div className="h-11 rounded-[10px] bg-[var(--wolfy-surface-inset-lift)]" />
                  <div className="h-11 rounded-[10px] bg-[var(--wolfy-surface-inset)]" />
                </div>
              </div>
              <div className="hidden min-h-[22rem] rounded-[14px] border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-console)] p-4 md:block">
                <div className="mb-3 h-6 w-28 rounded-full bg-[var(--wolfy-surface-inset)]" />
                <div className="space-y-2.5">
                  <div className="h-14 rounded-[10px] bg-[var(--wolfy-surface-inset-lift)]" />
                  <div className="h-14 rounded-[10px] bg-[var(--wolfy-surface-inset)]" />
                  <div className="h-14 rounded-[10px] bg-[var(--wolfy-surface-inset-lift)]" />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div
        data-testid="auth-guard-scrim"
        className="auth-guard-scrim absolute inset-0 bg-[color:rgb(37_34_29_/_0.38)] backdrop-blur-[3px]"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_12%,rgba(212,165,116,0.14),transparent_32%),linear-gradient(180deg,rgba(255,253,248,0.1),transparent_40%)]"
        aria-hidden="true"
      />

      <section
        ref={cardRef}
        className="auth-guard-card relative z-10 mt-0 flex w-full max-w-[min(92vw,28.5rem)] flex-col overflow-hidden rounded-[16px] border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-elevated)] px-4 py-5 text-left shadow-[var(--wolfy-shadow-console)] sm:px-5 sm:py-6"
        data-testid="auth-guard-card"
      >
        <p
          className="auth-guard-eyebrow"
          data-testid="auth-guard-eyebrow"
        >
          {eyebrow}
        </p>

        <h2
          id={titleId}
          className="auth-guard-capability mt-1.5 text-[1.0625rem] font-semibold leading-snug text-[color:var(--wolfy-text-primary)] sm:text-[1.125rem]"
          data-testid="auth-guard-capability"
        >
          {moduleName}
        </h2>

        <p
          className="auth-guard-capability-summary mt-1 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]"
          data-testid="auth-guard-capability-summary"
        >
          {capabilitySummary}
        </p>

        <div
          className="auth-guard-status-band mt-4 flex flex-wrap items-start gap-3 rounded-[12px] border border-[color:var(--state-warning-border,rgb(151_103_49_/_0.38))] bg-[color:var(--state-warning-bg,rgb(212_165_116_/_0.16))] px-3 py-2.5"
          data-testid="auth-guard-status-band"
        >
          <div
            className="auth-guard-status-icon flex size-9 shrink-0 items-center justify-center rounded-full border border-[color:var(--state-warning-border,rgb(151_103_49_/_0.38))] bg-[color:var(--state-warning-bg-strong,rgb(212_165_116_/_0.24))] text-[color:var(--state-warning-text,#5a3a18)]"
            aria-hidden="true"
          >
            <Lock className="size-3.5" />
          </div>
          <div className="min-w-0 flex-1 space-y-1">
            <span
              className="auth-guard-status-pill inline-flex min-h-7 items-center gap-1.5 rounded-full border border-[color:var(--state-warning-border,rgb(151_103_49_/_0.38))] bg-[color:var(--state-warning-bg-strong,rgb(212_165_116_/_0.24))] px-2.5 py-0.5 text-[0.6875rem] font-bold uppercase tracking-[0.08em] text-[color:var(--state-warning-text,#5a3a18)]"
              data-testid="auth-guard-status-pill"
            >
              <span aria-hidden="true">▲</span>
              <span>{statusLabel}</span>
            </span>
            <p className="m-0 text-sm font-semibold leading-snug text-[color:var(--wolfy-text-primary)]">
              {statusLabel}
            </p>
          </div>
        </div>

        <div
          id={bodyId}
          className="auth-guard-reason mt-4 space-y-1.5"
          data-testid="auth-guard-reason"
        >
          <p className="auth-guard-section-label m-0 font-mono text-[0.625rem] font-semibold uppercase tracking-[0.12em] text-[color:var(--sage-deep,#365d3d)]">
            {reasonLabel}
          </p>
          <p className="m-0 text-sm leading-relaxed text-[color:var(--wolfy-text-secondary)]">
            {reasonBody}
          </p>
          <p className="m-0 text-sm leading-relaxed text-[color:var(--wolfy-text-secondary)]">
            {reasonFollowup}
          </p>
        </div>

        <div
          className="auth-guard-preview mt-3 rounded-[12px] border border-[color:var(--line,var(--wolfy-border-subtle))] bg-[color:var(--wolfy-surface-inset,rgb(255_253_248_/_0.55))] px-3 py-2.5"
          data-testid="auth-guard-preview-note"
        >
          <p className="auth-guard-section-label m-0 font-mono text-[0.625rem] font-semibold uppercase tracking-[0.12em] text-[color:var(--sage-deep,#365d3d)]">
            {previewLabel}
          </p>
          <p className="mt-1 m-0 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
            {previewBody}
          </p>
        </div>

        <div
          className="auth-guard-actions mt-5 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center"
          data-testid="auth-guard-actions"
        >
          <Link
            ref={loginActionRef}
            to={loginPath}
            className="auth-guard-action auth-guard-action--primary theme-primary-action inline-flex min-h-11 w-full items-center justify-center gap-1.5 rounded-[10px] border border-[color:var(--theme-button-primary-border,var(--sage-deep,#365d3d))] bg-[var(--theme-button-primary-bg,var(--sage-deep,#365d3d))] px-4 text-sm font-semibold text-[color:var(--theme-button-primary-text,var(--wolfy-inverse-text,#fbf8f3))] no-underline sm:w-auto sm:min-w-[9.5rem]"
            data-testid="auth-guard-primary-action"
            aria-label={`${primaryLabel} ${moduleName}`.trim()}
            onClick={(event) => {
              // Keep SPA navigation explicit for focus restoration and tests that spy navigate.
              event.preventDefault();
              navigate(loginPath);
            }}
          >
            <span>{primaryLabel}</span>
            <ArrowRight className="size-4 shrink-0" aria-hidden="true" />
          </Link>
          <Link
            to={marketPath}
            className="auth-guard-action auth-guard-action--secondary inline-flex min-h-11 w-full items-center justify-center rounded-[10px] border border-[color:var(--border-muted,var(--line))] bg-[var(--pill-bg,transparent)] px-4 text-sm font-semibold text-[color:var(--wolfy-text-primary)] no-underline sm:w-auto sm:min-w-[9.5rem]"
            data-testid="auth-guard-secondary-action"
            onClick={(event) => {
              event.preventDefault();
              navigate(marketPath);
            }}
          >
            {secondaryLabel}
          </Link>
          <Link
            to={homePath}
            className="auth-guard-action auth-guard-action--tertiary inline-flex min-h-10 w-full items-center justify-center rounded-[10px] px-3 text-sm font-medium text-[color:var(--wolfy-text-secondary)] no-underline sm:w-auto"
            data-testid="auth-guard-tertiary-action"
            onClick={(event) => {
              event.preventDefault();
              navigate(homePath);
            }}
          >
            {safeExitLabel}
          </Link>
        </div>
      </section>
    </section>
  );
};
