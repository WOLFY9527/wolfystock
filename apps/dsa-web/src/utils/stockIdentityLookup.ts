import { canonicalStockSymbolFromValidation, stocksApi } from '../api/stocks';

/**
 * Keeps server-backed identity validation at the shared identity boundary so
 * navigation and entry presenters do not each become request owners.
 */
export async function resolveCanonicalStockSymbol(rawSymbol: string): Promise<string | null> {
  const validation = await stocksApi.verifyTickerExists(rawSymbol);
  return canonicalStockSymbolFromValidation(validation)?.symbol ?? null;
}
