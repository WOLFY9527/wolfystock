import { getGlossaryTerm } from '../../data/glossaryTerms';
import { TermTooltip, type TermTooltipProps } from './TermTooltip';

export interface GlossaryTermProps
  extends Omit<TermTooltipProps, 'label' | 'labelEn' | 'explanation' | 'professionalNote' | 'caveat'> {
  termId: string;
  fallbackLabel?: string;
}

export function GlossaryTerm({ termId, fallbackLabel, ...props }: GlossaryTermProps) {
  const term = getGlossaryTerm(termId);

  if (!term) {
    return <>{fallbackLabel ?? termId}</>;
  }

  return (
    <TermTooltip
      {...props}
      label={term.labelZh}
      labelEn={term.labelEn}
      explanation={term.explanation}
      professionalNote={term.professionalNote}
      caveat={term.caveat}
    />
  );
}
