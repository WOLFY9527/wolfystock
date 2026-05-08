import { CircleHelp } from 'lucide-react';
import { cn } from '../../utils/cn';
import { TermTooltip, type TermTooltipProps } from './TermTooltip';

export type HelpHintProps = Omit<TermTooltipProps, 'children' | 'triggerClassName'> & {
  iconClassName?: string;
};

export function HelpHint({ iconClassName, className, ...props }: HelpHintProps) {
  return (
    <TermTooltip
      {...props}
      className={cn('inline-flex', className)}
      triggerClassName="h-6 w-6 justify-center rounded-full border-white/8 bg-white/[0.03] p-0 text-cyan-100/70 hover:text-cyan-50"
    >
      <CircleHelp className={cn('h-3.5 w-3.5', iconClassName)} aria-hidden="true" />
    </TermTooltip>
  );
}
