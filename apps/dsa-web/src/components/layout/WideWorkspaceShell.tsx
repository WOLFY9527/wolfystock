import type React from 'react';
import { TerminalPageShell } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';

type WideWorkspaceProps = React.HTMLAttributes<HTMLDivElement> & {
  children?: React.ReactNode;
};

const WIDE_WORKSPACE_MAX_CLASS = 'workspace-width-near-full max-w-[1840px] 2xl:px-10';

export function WideWorkspacePageShell({ className, children, ...props }: WideWorkspaceProps) {
  return (
    <TerminalPageShell
      data-workspace-width="near-full"
      className={cn(WIDE_WORKSPACE_MAX_CLASS, className)}
      {...props}
    >
      {children}
    </TerminalPageShell>
  );
}

export function WideWorkspaceShellScope({ className, children, ...props }: WideWorkspaceProps) {
  return (
    <div
      data-workspace-width="near-full"
      className={cn(
        'workspace-width-near-full flex w-full min-w-0 flex-col overflow-x-hidden [--wolfy-workspace-shell-max:1840px] [&_[data-terminal-primitive="page-shell"]]:max-w-[var(--wolfy-workspace-shell-max)] [&_[data-terminal-primitive="page-shell"]]:2xl:px-10',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
