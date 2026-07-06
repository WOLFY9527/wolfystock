import type { ProductReadModel, ProductReadModelState } from '../types/productReadModel';

export type ProductReadModelTone = 'success' | 'warning' | 'error' | 'info' | 'disabled';

export function normalizeProductReadState(value?: string | null): ProductReadModelState {
  const normalized = String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[-\s]+/g, '_');
  if (!normalized) return 'no_evidence';
  return normalized;
}

export function productReadModelTone(state?: string | null): ProductReadModelTone {
  const normalized = normalizeProductReadState(state);
  if (normalized === 'available') return 'success';
  if (normalized === 'partial' || normalized === 'stale' || normalized === 'degraded' || normalized === 'pending') {
    return 'warning';
  }
  if (normalized === 'unavailable' || normalized === 'insufficient' || normalized === 'no_evidence' || normalized === 'rejected') {
    return 'error';
  }
  return 'disabled';
}

export function productReadStateLabel(state: string | null | undefined, language: 'zh' | 'en'): string {
  const normalized = normalizeProductReadState(state);
  const labels: Record<string, { zh: string; en: string }> = {
    available: { zh: '可用', en: 'Available' },
    partial: { zh: '部分可用', en: 'Partial' },
    stale: { zh: '已过期', en: 'Stale' },
    unavailable: { zh: '不可用', en: 'Unavailable' },
    insufficient: { zh: '证据不足', en: 'Insufficient' },
    no_evidence: { zh: '暂无证据', en: 'No evidence' },
    degraded: { zh: '降级可读', en: 'Degraded' },
    rejected: { zh: '已拒绝', en: 'Rejected' },
    pending: { zh: '待确认', en: 'Pending' },
  };
  return labels[normalized]?.[language] || (language === 'en' ? 'Not ready' : '暂未就绪');
}

export function productReadModelIsBlocking(model?: ProductReadModel | null): boolean {
  if (!model) return false;
  const state = normalizeProductReadState(model?.state);
  return model?.ready === false
    || state === 'unavailable'
    || state === 'insufficient'
    || state === 'no_evidence'
    || state === 'rejected'
    || Boolean(model?.blockingChildren?.length);
}

function productReadEvidenceLabel(value: string, language: 'zh' | 'en'): string {
  const normalized = String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_');
  const labels: Record<string, { zh: string; en: string }> = {
    coverage: { zh: '覆盖证据', en: 'Coverage evidence' },
    data_quality: { zh: '数据质量证据', en: 'Data quality evidence' },
    freshness: { zh: '新鲜度证据', en: 'Freshness evidence' },
    historical_coverage: { zh: '历史覆盖证据', en: 'Historical coverage evidence' },
    historical_data: { zh: '历史行情证据', en: 'Historical market evidence' },
    market_evidence: { zh: '市场证据', en: 'Market evidence' },
    money_flow: { zh: '资金流证据', en: 'Money flow evidence' },
    price_history: { zh: '价格历史证据', en: 'Price history evidence' },
    quality: { zh: '质量证据', en: 'Quality evidence' },
    stock_research_packet: { zh: '个股研究包证据', en: 'Stock research evidence' },
    structure_decision: { zh: '结构观察证据', en: 'Structure observation evidence' },
    technical_indicators: { zh: '技术指标证据', en: 'Technical indicator evidence' },
  };
  return labels[normalized]?.[language] || (language === 'en' ? 'Evidence module' : '证据模块');
}

export function productReadBlockingSummary(model: ProductReadModel | null | undefined, language: 'zh' | 'en'): string | null {
  const blockers = (model?.blockingChildren || []).filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
  if (!blockers.length) return null;
  const label = blockers.slice(0, 3).map((item) => productReadEvidenceLabel(item, language)).join(' / ');
  return language === 'en'
    ? `Critical evidence blocked: ${label}`
    : `关键证据阻塞：${label}`;
}

export function productReadFreshnessLabel(model: ProductReadModel | null | undefined, language: 'zh' | 'en'): string | null {
  if (!model) return null;
  const rawFreshness = model.freshness?.state || model.provenance?.freshness || null;
  const freshness = rawFreshness ? normalizeProductReadState(rawFreshness) : null;
  const asOf = model?.freshness?.asOf || model?.provenance?.asOf || null;
  if (!freshness && !asOf) return null;
  const status = productReadStateLabel(freshness || model?.state, language);
  if (!asOf) return language === 'en' ? `Freshness: ${status}` : `新鲜度：${status}`;
  return language === 'en' ? `Freshness: ${status} · as of ${asOf}` : `新鲜度：${status} · 截至 ${asOf}`;
}

export function productReadCoverageLabel(model: ProductReadModel | null | undefined, language: 'zh' | 'en'): string | null {
  const coverage = model?.coverage;
  if (!coverage) return null;
  const stateLabel = productReadStateLabel(coverage.state || model?.state, language);
  const available = coverage.availableBars ?? coverage.barCount ?? null;
  const required = coverage.requiredBars ?? null;
  if (available !== null && required !== null && required > 0) {
    return language === 'en'
      ? `Coverage: ${stateLabel} · ${available}/${required} bars`
      : `覆盖：${stateLabel} · ${available}/${required} 根`;
  }
  return language === 'en' ? `Coverage: ${stateLabel}` : `覆盖：${stateLabel}`;
}

export function productReadSourceClassLabel(sourceClass: string | null | undefined, language: 'zh' | 'en'): string {
  const normalized = String(sourceClass || '').trim().toLowerCase();
  const labels: Record<string, { zh: string; en: string }> = {
    historical_market_data: { zh: '历史行情证据', en: 'Historical evidence' },
    dashboard_read_models: { zh: '市场读模型', en: 'Market read model' },
    stock_evidence: { zh: '证据摘要', en: 'Evidence summary' },
    stock_research_packet: { zh: '个股研究包', en: 'Stock research packet' },
    structure_decision: { zh: '结构观察读模型', en: 'Structure read model' },
  };
  return labels[normalized]?.[language] || (language === 'en' ? 'Evidence summary' : '证据摘要');
}

export function productReadProvenanceLine(model: ProductReadModel | null | undefined, language: 'zh' | 'en'): string | null {
  if (!model?.provenance) return null;
  const source = productReadSourceClassLabel(model.provenance.sourceClass, language);
  const freshness = productReadStateLabel(model.provenance.freshness || model.freshness?.state || model.state, language);
  const quality = model.provenance.quality ? productReadStateLabel(String(model.provenance.quality), language) : null;
  const asOf = model.provenance.asOf || model.freshness?.asOf || null;
  const parts = [source, freshness, quality, asOf ? (language === 'en' ? `as of ${asOf}` : `截至 ${asOf}`) : null].filter(Boolean);
  return parts.join(' · ');
}

export function productReadClassificationDisplayState(model: ProductReadModel | null | undefined): string | null {
  return model?.classification?.displayState || null;
}

export function productReadStrongConclusionAllowed(model: ProductReadModel | null | undefined): boolean {
  return model?.classification?.strongConclusionAllowed !== false
    && model?.confidence?.strongConclusionAllowed !== false;
}
