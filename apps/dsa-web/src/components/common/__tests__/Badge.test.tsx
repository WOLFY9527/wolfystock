import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Badge } from '../Badge';

describe('Badge', () => {
  it('uses shared readonly control state without legacy glow attributes', () => {
    render(<Badge variant="warning">部分可用</Badge>);

    const badge = screen.getByText('部分可用');
    expect(badge).toHaveAttribute('data-variant', 'warning');
    expect(badge).toHaveAttribute('data-control-state', 'readonly');
    expect(badge).not.toHaveAttribute('data-glow');
  });
});
