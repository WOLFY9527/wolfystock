import type React from 'react';
import { ArrowRight, LockKeyhole, ShieldCheck } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useI18n } from '../../contexts/UiLanguageContext';
import { buildLoginPath, useProductSurface } from '../../hooks/useProductSurface';
import { cn } from '../../utils/cn';
import { buildLocalizedPath, parseLocaleFromPathname, stripLocalePrefix } from '../../utils/localeRouting';
import {
  getConsumerGroupLabel,
  resolveConsumerNavItem,
  resolveConsumerRouteStory,
} from './consumerAppNavigation';

type ConsumerRouteStoryProps = {
  className?: string;
};

function localizeTarget(target: string, routeLocale: 'zh' | 'en' | null): string {
  return routeLocale ? buildLocalizedPath(target, routeLocale) : target;
}

export const ConsumerRouteStory: React.FC<ConsumerRouteStoryProps> = ({ className }) => {
  const location = useLocation();
  const { language } = useI18n();
  const { isGuest } = useProductSurface();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const routePathname = stripLocalePrefix(location.pathname);
  const routeStory = resolveConsumerRouteStory(routePathname);
  const routeItem = resolveConsumerNavItem(routePathname);

  if (!routeStory || !routeItem) {
    return null;
  }

  const copy = routeStory.copy[language];
  const isLockedForGuest = Boolean(isGuest && routeItem.requiresAuth);
  const primaryTarget = isLockedForGuest
    ? buildLoginPath(`${location.pathname}${location.search}`)
    : routeStory.primaryTo ? localizeTarget(routeStory.primaryTo, routeLocale) : null;
  const secondaryTarget = routeStory.secondaryTo ? localizeTarget(routeStory.secondaryTo, routeLocale) : null;
  const groupLabel = getConsumerGroupLabel(routeStory.group, language);
  const lockLabel = language === 'en' ? 'Sign in required' : '需要登录';
  const primaryLabel = isLockedForGuest
    ? (language === 'en' ? 'Sign in to continue' : '登录后继续')
    : copy.primaryAction;

  return (
    <section
      data-testid="consumer-route-story"
      className={cn('consumer-route-story-band', className)}
      aria-label={language === 'en' ? 'Current workspace purpose' : '当前工作区用途'}
    >
      <div className="consumer-route-story-inner">
        <div className="consumer-route-story-copy">
          <div className="consumer-route-story-kicker">
            <span>{groupLabel}</span>
            <span aria-hidden="true">/</span>
            <span>{copy.eyebrow}</span>
            {isLockedForGuest ? (
              <span className="consumer-route-story-lock">
                <LockKeyhole className="size-3" aria-hidden="true" />
                {lockLabel}
              </span>
            ) : null}
          </div>
          <p className="consumer-route-story-title">{copy.title}</p>
          <p className="consumer-route-story-purpose">{copy.purpose}</p>
        </div>

        <div className="consumer-route-story-next">
          <div className="consumer-route-story-evidence">
            <ShieldCheck className="size-4 shrink-0" aria-hidden="true" />
            <span>{copy.evidence}</span>
          </div>
          <p className="consumer-route-story-boundary">{copy.boundary}</p>
          <div className="consumer-route-story-actions">
            {primaryTarget && primaryLabel ? (
              <Link className="consumer-route-story-action consumer-route-story-action--primary" to={primaryTarget}>
                <span>{primaryLabel}</span>
                <ArrowRight className="size-3.5" aria-hidden="true" />
              </Link>
            ) : null}
            {secondaryTarget && copy.secondaryAction ? (
              <Link className="consumer-route-story-action" to={secondaryTarget}>
                {copy.secondaryAction}
              </Link>
            ) : null}
          </div>
          <p className="consumer-route-story-nextstep">{copy.nextStep}</p>
        </div>
      </div>
    </section>
  );
};
