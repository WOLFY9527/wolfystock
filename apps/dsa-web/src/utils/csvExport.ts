type CsvQuoteMode = 'minimal' | 'always';

type CsvCellOptions = {
  quote?: CsvQuoteMode;
};

const FORMULA_PREFIXES = new Set(['=', '+', '-', '@']);

function isIgnoredFormulaPrefixCharacter(char: string): boolean {
  const code = char.charCodeAt(0);
  return code <= 0x20 || (code >= 0x7f && code <= 0x9f);
}

function startsWithSpreadsheetFormulaPrefix(value: string): boolean {
  for (const char of value) {
    if (isIgnoredFormulaPrefixCharacter(char)) continue;
    return FORMULA_PREFIXES.has(char);
  }
  return false;
}

function neutralizeSpreadsheetFormulaText(value: string): string {
  return startsWithSpreadsheetFormulaPrefix(value) ? `'${value}` : value;
}

export function serializeCsvCell(value: unknown, options: CsvCellOptions = {}): string {
  const text = value == null ? '' : String(value);
  const safeText = typeof value === 'string' ? neutralizeSpreadsheetFormulaText(text) : text;
  const quoteAlways = options.quote === 'always';
  if (!quoteAlways && !/[",\r\n]/.test(safeText)) return safeText;
  return `"${safeText.replaceAll('"', '""')}"`;
}

export function serializeCsvRow(values: unknown[], options: CsvCellOptions = {}): string {
  return values.map((value) => serializeCsvCell(value, options)).join(',');
}
