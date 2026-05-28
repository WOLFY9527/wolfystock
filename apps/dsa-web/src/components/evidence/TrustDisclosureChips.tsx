import { TerminalChip } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';
import {
  TRUST_DISCLOSURE_LABELS,
  TRUST_DISCLOSURE_VARIANTS,
  resolveTrustDisclosureBuckets,
  type TrustDisclosureBucket,
} from '../../utils/trustDisclosure';

type TrustDisclosureChipsProps = {
  buckets?: Array<TrustDisclosureBucket | null | undefined | false>;
  terms?: Array<string | null | undefined>;
  maxBuckets?: number;
  className?: string;
  chipClassName?: string;
  'data-testid'?: string;
};

export function TrustDisclosureChips({
  buckets,
  terms,
  maxBuckets,
  className,
  chipClassName,
  'data-testid': dataTestId,
}: TrustDisclosureChipsProps) {
  const resolvedBuckets = resolveTrustDisclosureBuckets({ buckets, terms });
  const visibleBuckets = maxBuckets == null ? resolvedBuckets : resolvedBuckets.slice(0, maxBuckets);
  if (!visibleBuckets.length) return null;

  return (
    <div data-testid={dataTestId} className={cn('flex min-w-0 flex-wrap items-center gap-1.5', className)}>
      {visibleBuckets.map((bucket) => (
        <TerminalChip
          key={bucket}
          variant={TRUST_DISCLOSURE_VARIANTS[bucket]}
          className={chipClassName}
        >
          {TRUST_DISCLOSURE_LABELS[bucket]}
        </TerminalChip>
      ))}
    </div>
  );
}
