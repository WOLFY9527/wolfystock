import { describe, expect, it } from 'vitest';
import { serializeCsvCell, serializeCsvRow } from '../csvExport';

describe('csvExport', () => {
  it('neutralizes spreadsheet formula prefixes for string cells before CSV quoting', () => {
    expect(serializeCsvCell('=1+1')).toBe("'=1+1");
    expect(serializeCsvCell('+1+1')).toBe("'+1+1");
    expect(serializeCsvCell('-1+1')).toBe("'-1+1");
    expect(serializeCsvCell('@SUM(1,1)')).toBe('"\'@SUM(1,1)"');
    expect(serializeCsvCell('  =1+1')).toBe("'  =1+1");
    expect(serializeCsvCell('\t+1+1')).toBe("'\t+1+1");
    expect(serializeCsvCell('\r-1+1')).toBe('"\'\r-1+1"');
    expect(serializeCsvCell('\n@SUM(1,1)')).toBe('"\'\n@SUM(1,1)"');
    expect(serializeCsvCell('\u007f=1+1')).toBe("'\u007f=1+1");
  });

  it('preserves ordinary values while applying structural CSV quoting', () => {
    expect(serializeCsvCell(-12.5)).toBe('-12.5');
    expect(serializeCsvCell('profit +1+1 later')).toBe('profit +1+1 later');
    expect(serializeCsvCell('腾讯控股')).toBe('腾讯控股');
    expect(serializeCsvCell('ACME, Inc.')).toBe('"ACME, Inc."');
    expect(serializeCsvCell('He said "watch"')).toBe('"He said ""watch"""');
    expect(serializeCsvCell('first line\nsecond line')).toBe('"first line\nsecond line"');
  });

  it('serializes rows without converting numeric cells into text', () => {
    expect(serializeCsvRow(['=1+1', -3, 'ordinary'])).toBe("'=1+1,-3,ordinary");
    expect(serializeCsvRow(['=1+1', -3, 'ordinary'], { quote: 'always' })).toBe('"\'=1+1","-3","ordinary"');
  });
});
