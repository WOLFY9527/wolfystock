import { portfolioDecimalSign } from './portfolioDecimal';
import type { PortfolioDecimal } from '../types/portfolio';

export type { PortfolioDecimal };

/** Admin Users consumes this display projection without importing portfolio internals. */
export function presentAdminPortfolioDecimalSign(value: PortfolioDecimal): -1 | 0 | 1 {
  return portfolioDecimalSign(value);
}
