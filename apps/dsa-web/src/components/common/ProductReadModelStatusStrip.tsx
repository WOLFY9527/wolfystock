import type { ProductReadModel } from '../../types/productReadModel';
import {
  productReadBlockingSummary,
  productReadCoverageLabel,
  productReadFreshnessLabel,
  productReadModelTone,
  productReadProvenanceLine,
  productReadStateLabel,
} from '../../utils/productReadModelView';
import { StatusBadge } from '../ui/StatusBadge';

type ProductReadModelStatusStripProps = {
  model?: ProductReadModel | null;
  language: 'zh' | 'en';
  title?: string;
  testId?: string;
  className?: string;
};

export default function ProductReadModelStatusStrip({
  model,
  language,
  title,
  testId = 'product-read-model-status-strip',
  className = '',
}: ProductReadModelStatusStripProps) {
  if (!model) return null;

  const stateLabel = productReadStateLabel(model.state, language);
  const blocking = productReadBlockingSummary(model, language);
  const freshness = productReadFreshnessLabel(model, language);
  const coverage = productReadCoverageLabel(model, language);
  const provenance = productReadProvenanceLine(model, language);
  const description = blocking || coverage || freshness || provenance || (
    language === 'en'
      ? 'Readiness follows the backend product read model.'
      : '就绪度来自后端产品读模型。'
  );

  return (
    <section
      data-testid={testId}
      data-product-read-state={model.state || 'no_evidence'}
      data-product-read-ready={String(model.ready === true)}
      className={`rounded-lg border border-white/10 bg-white/[0.035] px-3 py-3 text-xs text-white/72 ${className}`}
    >
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-normal text-white/42">
          {title || (language === 'en' ? 'Read model' : '读模型')}
        </p>
        <StatusBadge status={productReadModelTone(model.state)} label={stateLabel} size="sm" />
      </div>
      <p className="mt-2 leading-5 text-white/72">{description}</p>
      {coverage && coverage !== description ? <p className="mt-1 leading-5 text-white/50">{coverage}</p> : null}
      {freshness && freshness !== description ? <p className="mt-1 leading-5 text-white/50">{freshness}</p> : null}
      {provenance && provenance !== description ? <p className="mt-1 leading-5 text-white/42">{provenance}</p> : null}
    </section>
  );
}
