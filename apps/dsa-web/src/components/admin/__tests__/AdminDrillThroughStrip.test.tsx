import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import AdminDrillThroughStrip from '../AdminDrillThroughStrip';

describe('AdminDrillThroughStrip', () => {
  it('renders only safe admin drill-through links and sanitizes query and hash values', () => {
    render(
      <AdminDrillThroughStrip
        dataTestId="admin-drill-through-strip"
        items={[
          {
            label: '查看相关日志',
            target: 'logs',
            evidenceType: 'request id',
            reason: '按安全引用继续排查',
            redacted: true,
            params: {
              tab: 'data_source',
              query: 'fallback market https://bad.example/?debug=HIDDEN',
              since: '24h',
              eventId: 'evt-42<script>',
              unsafeField: 'SHOULD_NOT_RENDER',
            },
          },
          {
            label: '查看证据工作流',
            target: 'evidence',
            evidenceType: 'sanitized evidence ref',
            reason: '继续核对离线复核步骤',
            redacted: true,
            params: {
              ref: 'provider_bundle',
              unsafeField: 'SHOULD_NOT_RENDER',
            },
            hash: 'schema-ref*',
          },
          {
            label: '非法跳转',
            target: 'logs',
            evidenceType: 'unsafe',
            reason: 'should be ignored',
            redacted: true,
            hrefOverride: 'https://bad.example/admin/logs',
          },
        ]}
      />,
    );

    const strip = screen.getByTestId('admin-drill-through-strip');
    const links = within(strip).getAllByRole('link');
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute('href', '/zh/admin/logs?tab=data_source&query=fallback%20market&since=24h&eventId=evt-42script');
    expect(links[1]).toHaveAttribute('href', '/zh/admin/evidence-workflow?ref=provider_bundle#schema-ref');
    expect(strip).toHaveTextContent('已脱敏引用');
    expect(strip).not.toHaveTextContent('unsafeField');
    expect(strip).not.toHaveTextContent('https://bad.example');
  });

  it('builds only existing admin routes', () => {
    render(
      <AdminDrillThroughStrip
        items={[
          {
            label: '电路诊断',
            target: 'providerCircuits',
            evidenceType: 'provider',
            reason: '按 provider 继续排查',
            params: { provider: 'Finnhub', routeFamily: 'analysis', since: '24h' },
          },
          {
            label: '用户详情',
            target: 'userDetail',
            userId: 'user-123',
            evidenceType: 'user',
            reason: '按安全用户标识查看详情',
            params: { tab: 'security', unsafeField: 'SHOULD_NOT_RENDER' },
          },
          {
            label: '非法跳转',
            target: 'logs',
            evidenceType: 'unsafe',
            reason: 'should be ignored',
            hrefOverride: 'https://bad.example/admin/logs',
          },
        ]}
      />,
    );

    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute('href', '/zh/admin/provider-circuits?provider=finnhub&routeFamily=analysis&since=24h');
    expect(links[1]).toHaveAttribute('href', '/zh/admin/users/user-123?tab=security');
  });
});
