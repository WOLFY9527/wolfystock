import type React from 'react';
import {
  backtestStrategyDisplayCopy,
  buildPointAndShootStrategyDisplayText,
  getStrategyCatalogEntry,
  type BacktestLanguage,
} from './strategyCatalog';
import type { NormalStrategyTemplate } from './pointAndShootTemplateOptions';

type NormalBacktestTemplateInsightsProps = {
  language: BacktestLanguage;
  strategyTemplate: NormalStrategyTemplate;
  code: string;
  startDate: string;
  endDate: string;
  initialCapital: string;
};

const LABEL_CLASS = 'mb-2 text-[10px] font-bold uppercase tracking-widest text-white/40';

const NormalBacktestTemplateInsights: React.FC<NormalBacktestTemplateInsightsProps> = ({
  language,
  strategyTemplate,
  code,
  startDate,
  endDate,
  initialCapital,
}) => {
  const currentTemplate = getStrategyCatalogEntry(strategyTemplate);
  const templateName = currentTemplate?.name[language] || '';
  const templateDescription = backtestStrategyDisplayCopy(currentTemplate?.description[language] || '');
  const templateLogicSummary = backtestStrategyDisplayCopy(currentTemplate?.logicSummary[language] || '');
  const templatePreview = buildPointAndShootStrategyDisplayText(language, strategyTemplate, {
    code,
    startDate,
    endDate,
    initialCapital,
  });

  return (
    <div
      data-testid="normal-backtest-template-insights"
      className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]"
    >
      <div className="min-w-0 rounded-[24px] border border-white/5 bg-black/20 p-5">
        <p className={LABEL_CLASS}>{language === 'en' ? 'Selected template' : '模板摘要'}</p>
        <h3 className="mt-2 text-base font-semibold text-white">{templateName}</h3>
        <p className="mt-2 text-sm leading-6 text-white/60">{templateDescription}</p>
        <p className="mt-3 text-sm leading-6 text-white/48">{templateLogicSummary}</p>
        <p className="mt-3 text-xs leading-5 text-white/42">
          {language === 'en' ? 'Templates are for research simulations only and are not trading instructions.' : '模板仅用于研究模拟，不构成交易建议。'}
        </p>
      </div>
      <div className="min-w-0 rounded-[24px] border border-white/5 bg-black/20 p-5">
        <p className={LABEL_CLASS}>{language === 'en' ? 'Backtest rule preview' : '回测规则预览'}</p>
        <p className="mt-2 text-sm leading-7 text-white/72">{templatePreview}</p>
      </div>
    </div>
  );
};

export default NormalBacktestTemplateInsights;
