import type React from 'react';
import { cn } from '../../utils/cn';
import { CARD_KICKER_CLASS, SYSTEM_ACCENT_GLOW_CLASS, type SignalTone, getCardGlowClass } from './theme';

type BentoCardProps = {
  eyebrow: string;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
  tone?: SignalTone;
  accentGlow?: boolean;
  accentGlowClassName?: string;
  researchCard?: string;
  testId?: string;
};

export const BentoCard: React.FC<BentoCardProps> = ({
  eyebrow,
  title,
  subtitle,
  action,
  children,
  className,
  contentClassName,
  tone = 'neutral',
  accentGlow = false,
  accentGlowClassName = SYSTEM_ACCENT_GLOW_CLASS,
  researchCard,
  testId,
}) => (
  <section
    data-testid={testId}
    data-research-card={researchCard}
    className={cn(
      'group relative overflow-hidden rounded-[36px] border border-white/5 bg-white/[0.02] px-8 py-7 backdrop-blur-2xl transition-transform duration-200 ease-out md:px-10 md:py-8 [backface-visibility:hidden] [transform:translateZ(0)] hover:-translate-y-[2px]',
      className,
    )}
  >
    {accentGlow ? (
      <div
        aria-hidden="true"
        className={cn(
          'pointer-events-none absolute right-[-3rem] top-[-3rem] h-40 w-40 rounded-full blur-[72px]',
          accentGlowClassName || getCardGlowClass(tone),
        )}
      />
    ) : null}
    <div className={cn('relative z-10 flex h-full flex-col', contentClassName)}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className={CARD_KICKER_CLASS}>{eyebrow}</p>
          {title ? <h2 className="mt-2.5 min-w-0 break-words whitespace-normal text-lg font-semibold text-white">{title}</h2> : null}
          {subtitle ? <p className="mt-3 min-w-0 break-words whitespace-normal text-sm leading-relaxed text-white/58">{subtitle}</p> : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      <div className="relative z-10 mt-4 min-h-0 flex-1">{children}</div>
    </div>
  </section>
);
