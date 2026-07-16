import type React from 'react';
import { cn } from '../../utils/cn';

export const BRAND_WORDMARK_CLASSNAME = '';

type BrandLogoProps = {
  className?: string;
  alt?: string;
};

export const BrandLogo: React.FC<BrandLogoProps> = ({
  className,
  alt = 'WolfyStock logo',
}) => (
  <img
    src="/wolfystock-logo-mark.svg"
    alt={alt}
    className={cn('block shrink-0 object-contain', className)}
  />
);
