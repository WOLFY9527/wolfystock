import type React from 'react';
import { WorkspacePageHeader } from '../common/WorkspacePageHeader';
import { cn } from '../../utils/cn';
import {
  BENTO_SURFACE_ROOT_CLASS,
  CARD_KICKER_CLASS,
  getToneTextClass,
  getToneTextStyle,
  type SignalTone,
} from './theme';

export type BentoHeroItem = {
  label: string;
  value: React.ReactNode;
  detail?: React.ReactNode;
  tone?: SignalTone;
  testId?: string;
  valueTestId?: string;
  valueClassName?: string;
};

type BentoHeroStripProps = {
  items: BentoHeroItem[];
  className?: string;
  testId?: string;
};

export const BentoHeroStrip: React.FC<BentoHeroStripProps> = ({ items, className, testId }) => (
  <div
    data-testid={testId}
    className={cn('grid gap-3 md:grid-cols-2 xl:grid-cols-4', className)}
  >
    {items.map((item, index) => {
      const tone = item.tone || 'neutral';

      return (
        <div
          key={`${item.label}-${index}`}
          data-testid={item.testId}
          className="group relative overflow-hidden rounded-[18px] border border-white/5 bg-white/[0.01] px-4 py-4 backdrop-blur-2xl transition-all duration-200 ease-out hover:-translate-y-[1px] hover:border-white/[0.08] hover:bg-white/[0.02] sm:px-5 sm:py-5"
        >
          {tone !== 'neutral' ? (
            <div
              aria-hidden="true"
              className={cn(
                'pointer-events-none absolute right-[-2rem] top-[-2rem] h-20 w-20 rounded-full blur-[56px]',
                tone === 'bullish' ? 'bg-[#34D399]/14' : 'bg-[#FB7185]/14',
              )}
            />
          ) : null}
          <div className="relative z-10">
            <p className={CARD_KICKER_CLASS}>{item.label}</p>
            <p
              data-testid={item.valueTestId}
              className={cn(
                'mt-2.5 text-[1.35rem] font-semibold text-white sm:text-[1.55rem]',
                getToneTextClass(tone),
                item.valueClassName,
              )}
              style={getToneTextStyle(tone, tone !== 'neutral')}
            >
              {item.value}
            </p>
            {item.detail ? (
              <p className="mt-1.5 text-xs leading-5 text-white/56">{item.detail}</p>
            ) : null}
          </div>
        </div>
      );
    })}
  </div>
);

type PageChromeProps = {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  heroItems?: BentoHeroItem[];
  children?: React.ReactNode;
  headerChildren?: React.ReactNode;
  scrollMode?: 'contained' | 'page';
  pageClassName?: string;
  headerClassName?: string;
  headerContentClassName?: string;
  titleClassName?: string;
  descriptionClassName?: string;
  pageTestId?: string;
  heroTestId?: string;
};

export const PageChrome: React.FC<PageChromeProps> = ({
  eyebrow,
  title,
  description,
  actions,
  heroItems,
  children,
  headerChildren,
  scrollMode = 'contained',
  pageClassName,
  headerClassName,
  headerContentClassName,
  titleClassName,
  descriptionClassName,
  pageTestId,
  heroTestId,
}) => (
  <div
    data-testid={pageTestId}
    data-bento-surface="true"
    className={cn(
      'gemini-bento-page flex flex-col bg-black',
      scrollMode === 'page' ? 'min-h-full overflow-visible' : 'h-full min-h-0 overflow-hidden',
      BENTO_SURFACE_ROOT_CLASS,
      pageClassName,
    )}
  >
    <WorkspacePageHeader
      eyebrow={eyebrow}
      title={title}
      description={description}
      actions={actions}
      className={headerClassName}
      contentClassName={headerContentClassName}
      titleClassName={titleClassName}
      descriptionClassName={descriptionClassName}
    >
      {heroItems?.length ? <BentoHeroStrip items={heroItems} testId={heroTestId} /> : null}
      {headerChildren}
    </WorkspacePageHeader>
    <div className={cn('flex flex-col', scrollMode === 'page' ? 'min-h-0' : 'flex-1 min-h-0')}>
      {children}
    </div>
  </div>
);
