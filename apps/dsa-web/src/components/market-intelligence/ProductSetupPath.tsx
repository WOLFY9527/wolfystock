import type React from 'react';
import {
  buildDataSourcesSetupHref,
  buildProviderOpsSetupHref,
  type ProductSetupSurfaceKey,
} from '../../utils/productSetupSurface';

type ProductSetupPathProps = {
  surface: ProductSetupSurfaceKey;
  testId: string;
  className?: string;
};

const SETUP_ACTION_CLASS = 'inline-flex min-h-8 items-center rounded-md border border-white/[0.08] bg-white/[0.035] px-2.5 py-1 text-[11px] font-semibold text-white/72 transition-colors hover:border-cyan-200/25 hover:bg-white/[0.06] hover:text-white';

export const ProductSetupPath: React.FC<ProductSetupPathProps> = ({ surface, testId, className = '' }) => (
  <div
    data-testid={testId}
    className={[
      'mt-4 rounded-lg border border-cyan-200/12 bg-cyan-300/[0.035] px-3 py-3',
      className,
    ].filter(Boolean).join(' ')}
  >
    <div className="flex min-w-0 flex-col gap-3 md:flex-row md:items-start md:justify-between">
      <div className="min-w-0">
        <p className="text-[11px] font-semibold text-cyan-100/82">查看需配置的数据源</p>
        <p className="mt-1 max-w-3xl text-[11px] leading-5 text-white/52">
          改善证据覆盖 / 减少 fallback/proxy / 可能提升为可评分证据。是否进入评分仍由现有来源门槛决定。
        </p>
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        <a className={SETUP_ACTION_CLASS} href={buildProviderOpsSetupHref(surface)}>
          查看 Provider Ops
        </a>
        <a className={SETUP_ACTION_CLASS} href={buildDataSourcesSetupHref(surface)}>
          前往数据源设置
        </a>
      </div>
    </div>
  </div>
);
