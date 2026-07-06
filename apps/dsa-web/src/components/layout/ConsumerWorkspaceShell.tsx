import type React from 'react';
import { AuthGuardOverlay } from '../auth/AuthGuardOverlay';
import { cn } from '../../utils/cn';

type ConsumerWorkspaceProps = React.HTMLAttributes<HTMLDivElement> & {
  children?: React.ReactNode;
};

const CONSUMER_SCOPE_CLASS =
  'consumer-workspace-scope workspace-width-near-full flex w-full min-w-0 flex-col overflow-x-hidden [--wolfy-consumer-shell-max:1880px] [&_[data-consumer-primitive="page-shell"]]:max-w-[var(--wolfy-consumer-shell-max)]';
const CONSUMER_PAGE_SHELL_CLASS =
  'consumer-page-shell mx-auto flex min-h-0 min-w-0 w-full max-w-[var(--wolfy-consumer-shell-max,1880px)] flex-col gap-5 px-4 py-5 text-[color:var(--wolfy-text-primary)] md:py-6 xl:px-8 2xl:px-10';

export function ConsumerWorkspaceScope({ className, children, ...props }: ConsumerWorkspaceProps) {
  return (
    <div data-workspace-width="near-full" className={cn(CONSUMER_SCOPE_CLASS, className)} {...props}>
      {children}
    </div>
  );
}

export function ConsumerWorkspacePageShell({ className, children, ...props }: ConsumerWorkspaceProps) {
  return (
    <div
      data-consumer-primitive="page-shell"
      data-terminal-primitive="page-shell"
      className={cn(CONSUMER_PAGE_SHELL_CLASS, className)}
      {...props}
    >
      {children}
    </div>
  );
}

function ConsumerProtectedBackdrop() {
  return (
    <ConsumerWorkspacePageShell
      aria-hidden="true"
      data-testid="consumer-protected-backdrop"
      className="pointer-events-none flex-1 select-none opacity-85"
    >
      <div className="flex min-w-0 flex-col gap-4">
        <div className="rounded-[16px] border border-[color:var(--line)] bg-[var(--wolfy-surface-console)] p-4">
          <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0 flex-1">
              <div className="h-3 w-28 rounded-full bg-[color:rgb(107_143_113_/_0.14)]" />
              <div className="mt-3 h-8 max-w-[26rem] rounded-[10px] bg-[var(--wolfy-surface-input)]" />
              <div className="mt-2 h-4 max-w-[38rem] rounded-full bg-[var(--wolfy-surface-rail)]" />
            </div>
            <div className="grid min-w-0 grid-cols-2 gap-2 lg:w-[22rem] lg:grid-cols-4">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="h-14 rounded-[12px] border border-[color:var(--line)] bg-[var(--wolfy-surface-input)]" />
              ))}
            </div>
          </div>
        </div>

        <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_clamp(18rem,21vw,22rem)]">
          <div className="min-w-0 rounded-[16px] border border-[color:var(--line)] bg-[var(--wolfy-surface-console)] p-4">
            <div className="h-10 rounded-[10px] bg-[var(--wolfy-surface-input)]" />
            <div className="mt-4 grid gap-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="h-14 rounded-[12px] border border-[color:var(--line)] bg-[var(--wolfy-surface-input)]" />
              ))}
            </div>
          </div>
          <aside className="min-w-0 rounded-[16px] border border-[color:var(--line)] bg-[var(--wolfy-surface-rail)] p-4">
            <div className="h-3 w-24 rounded-full bg-[color:rgb(212_165_116_/_0.16)]" />
            <div className="mt-3 h-20 rounded-[12px] bg-[var(--wolfy-surface-input)]" />
            <div className="mt-3 space-y-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="h-16 rounded-[12px] border border-[color:var(--line)] bg-[var(--wolfy-surface-input)]" />
              ))}
            </div>
          </aside>
        </div>
      </div>
    </ConsumerWorkspacePageShell>
  );
}

export function ConsumerProtectedFrame({
  moduleName,
  className,
  children,
}: {
  moduleName: string;
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className={cn('flex min-h-0 w-full flex-1 flex-col', className)}>
      <AuthGuardOverlay moduleName={moduleName}>
        {children ?? <ConsumerProtectedBackdrop />}
      </AuthGuardOverlay>
    </div>
  );
}
