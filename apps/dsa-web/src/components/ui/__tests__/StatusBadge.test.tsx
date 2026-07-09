import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatusBadge } from '../StatusBadge';
import { getStatusLabel, normalizeStatus } from '../StatusBadge.helpers';

describe('StatusBadge', () => {
  it('maps success aliases to 成功', () => {
    expect(normalizeStatus('success')).toBe('success');
    expect(normalizeStatus('succeeded')).toBe('success');
    expect(normalizeStatus('completed')).toBe('success');
    expect(getStatusLabel('success')).toBe('成功');
    expect(getStatusLabel('succeeded')).toBe('成功');
    expect(getStatusLabel('completed')).toBe('成功');
  });

  it('maps failed aliases to 失败', () => {
    expect(normalizeStatus('failed')).toBe('failed');
    expect(normalizeStatus('error')).toBe('error');
    expect(getStatusLabel('failed')).toBe('失败');
    expect(getStatusLabel('error')).toBe('失败');
  });

  it('maps skipped aliases to 跳过', () => {
    expect(normalizeStatus('skipped')).toBe('skipped');
    expect(normalizeStatus('not_needed')).toBe('skipped');
    expect(getStatusLabel('skipped')).toBe('跳过');
    expect(getStatusLabel('not_needed')).toBe('跳过');
  });

  it('maps running aliases to 运行中', () => {
    expect(normalizeStatus('running')).toBe('running');
    expect(normalizeStatus('attempting')).toBe('running');
    expect(getStatusLabel('running')).toBe('运行中');
    expect(getStatusLabel('attempting')).toBe('运行中');
  });

  it('maps pending aliases to 等待中', () => {
    expect(normalizeStatus('pending')).toBe('pending');
    expect(normalizeStatus('queued')).toBe('pending');
    expect(getStatusLabel('pending')).toBe('等待中');
    expect(getStatusLabel('queued')).toBe('等待中');
  });

  it('maps partial to 部分失败', () => {
    expect(normalizeStatus('partial')).toBe('partial');
    expect(getStatusLabel('partial')).toBe('部分失败');
  });

  it('maps unknown to 未确认', () => {
    expect(normalizeStatus('unknown')).toBe('unknown');
    expect(getStatusLabel('unknown')).toBe('未确认');
  });

  it('applies label override', () => {
    render(<StatusBadge status="success" label="已通过校验" />);
    expect(screen.getByText('已通过校验')).toHaveAttribute('data-status', 'success');
  });

  it('uses explicit inverse foreground tokens for solid badges', () => {
    render(<StatusBadge status="success" variant="solid" label="已通过" />);

    expect(screen.getByText('已通过')).toHaveClass(
      'bg-[var(--state-success-text)]',
      'text-[color:var(--wolfy-inverse-text)]',
    );
  });

  it('keeps soft warning/info chips on shared state text tokens', () => {
    render(
      <>
        <StatusBadge status="warning" label="降级" />
        <StatusBadge status="partial" label="部分可用" />
        <StatusBadge status="info" label="信息" />
      </>,
    );

    expect(screen.getByText('降级')).toHaveClass(
      'bg-[var(--state-warning-bg)]',
      'text-[color:var(--state-warning-text)]',
    );
    expect(screen.getByText('部分可用')).toHaveClass(
      'text-[color:var(--state-warning-text)]',
    );
    expect(screen.getByText('信息')).toHaveClass(
      'text-[color:var(--state-info-text)]',
    );
  });

  it('does not render skipped as 成功', () => {
    render(<StatusBadge status="not_needed" />);
    expect(screen.getByText('跳过')).toBeInTheDocument();
    expect(screen.queryByText('成功')).not.toBeInTheDocument();
  });

  it('does not render unknown as 运行中', () => {
    render(<StatusBadge status="unknown" />);
    expect(screen.getByText('未确认')).toBeInTheDocument();
    expect(screen.queryByText('运行中')).not.toBeInTheDocument();
  });
});
