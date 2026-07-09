import type React from 'react';
import { cn } from '../../../utils/cn';
import { TerminalChip } from '../../terminal/TerminalPrimitives';
import { densityDataAttributes, normalizeResearchDensityMode } from './researchDensity';
import { MetaLabel, SectionTitle } from './ResearchTypography';
import type {
  ResearchDensityMode,
  ResearchLocale,
  ResearchQualityFacet,
  ResearchQualityFacetKind,
} from './types';

export type ResearchDataQualityCompositionProps = {
  title?: React.ReactNode;
  /** Structured quality facets — preserves semantic distinctions, does not invent taxonomy. */
  facets?: ResearchQualityFacet[];
  /**
   * Slot for existing semantic owners (ProductReadModelStatusStrip,
   * ConsumerResearchReadinessStrip, DenseStatusStrip, etc.).
   */
  statusSlot?: React.ReactNode;
  /** Optional coverage / readiness / packet strips already owned elsewhere. */
  coverageSlot?: React.ReactNode;
  density?: ResearchDensityMode;
  locale?: ResearchLocale;
  compact?: boolean;
  className?: string;
  children?: React.ReactNode;
  'data-testid'?: string;
};

const DEFAULT_TITLE: Record<ResearchLocale, string> = {
  zh: '数据质量',
  en: 'Data quality',
};

const FACET_KIND_HINT: Record<ResearchQualityFacetKind, { zh: string; en: string }> = {
  freshness: { zh: '新鲜度', en: 'Freshness' },
  coverage: { zh: '覆盖', en: 'Coverage' },
  authority: { zh: '权威性', en: 'Authority' },
  lineage: { zh: '来源链路', en: 'Lineage' },
  partial: { zh: '部分', en: 'Partial' },
  degraded: { zh: '降级', en: 'Degraded' },
  delayed: { zh: '延迟', en: 'Delayed' },
  cached: { zh: '缓存', en: 'Cached' },
  stale: { zh: '陈旧', en: 'Stale' },
  unavailable: { zh: '不可用', en: 'Unavailable' },
  blocked: { zh: '阻断', en: 'Blocked' },
  'observation-only': { zh: '仅观察', en: 'Observation only' },
};

function chipVariant(
  tone: ResearchQualityFacet['tone'],
  kind: ResearchQualityFacetKind,
): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (tone) return tone;
  if (kind === 'unavailable' || kind === 'blocked') return 'danger';
  if (kind === 'stale' || kind === 'degraded' || kind === 'partial' || kind === 'delayed') return 'caution';
  if (kind === 'observation-only' || kind === 'cached') return 'info';
  return 'neutral';
}

/**
 * Thin composition adapter for page-level research data quality.
 * Reuses existing semantic owners via slots; does not create a parallel taxonomy.
 *
 * Preserves:
 * - stale != fresh
 * - unavailable != zero
 * - proxy/authority via authority facet (caller-owned semantics)
 * - observation-only is explicit, not collapsed into available
 */
export function ResearchDataQualityComposition({
  title,
  facets,
  statusSlot,
  coverageSlot,
  density = 'research',
  locale = 'zh',
  compact = false,
  className,
  children,
  'data-testid': dataTestId = 'research-data-quality',
}: ResearchDataQualityCompositionProps) {
  const resolvedDensity = normalizeResearchDensityMode(density);
  const resolvedTitle = title ?? DEFAULT_TITLE[locale];
  const hasFacets = Boolean(facets?.length);
  const hasBody = hasFacets || statusSlot || coverageSlot || children;

  if (!hasBody) return null;

  return (
    <section
      data-testid={dataTestId}
      data-research-anatomy="data-quality"
      {...densityDataAttributes(resolvedDensity)}
      className={cn(
        'research-data-quality',
        compact && 'research-data-quality--compact',
        className,
      )}
    >
      <div className="research-data-quality__header">
        {compact ? (
          <MetaLabel>{resolvedTitle}</MetaLabel>
        ) : (
          <SectionTitle as="h3" className="research-data-quality__title">
            {resolvedTitle}
          </SectionTitle>
        )}
      </div>

      {statusSlot ? (
        <div className="research-data-quality__status-slot" data-quality-slot="status">
          {statusSlot}
        </div>
      ) : null}

      {hasFacets ? (
        <ul className="research-data-quality__facets" data-quality-facets>
          {facets!.map((facet, index) => (
            <li
              key={facet.key ?? `${facet.kind}-${index}`}
              className="research-data-quality__facet"
              data-quality-facet={facet.kind}
            >
              <div className="research-data-quality__facet-head">
                <TerminalChip variant={chipVariant(facet.tone, facet.kind)}>
                  {facet.label || FACET_KIND_HINT[facet.kind][locale]}
                </TerminalChip>
                {facet.value != null ? (
                  <span className="research-data-quality__facet-value">{facet.value}</span>
                ) : null}
              </div>
              {facet.detail ? (
                <p className="research-data-quality__facet-detail">{facet.detail}</p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      {coverageSlot ? (
        <div className="research-data-quality__coverage-slot" data-quality-slot="coverage">
          {coverageSlot}
        </div>
      ) : null}

      {children ? <div className="research-data-quality__extra">{children}</div> : null}
    </section>
  );
}
