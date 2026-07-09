import type React from 'react';
import { ArrowRight, ShieldAlert } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card } from '../common/Card';
import { WorkspacePageHeader } from '../common/WorkspacePageHeader';

type ActionLink = {
  label: string;
  to: string;
};

type AccessGatePageProps = {
  eyebrow: string;
  title: string;
  description: string;
  bullets: string[];
  statusLabel?: string;
  note?: string;
  primaryAction: ActionLink;
  secondaryAction?: ActionLink;
  tertiaryAction?: ActionLink;
};

/**
 * Shared gate surface for prototype-disabled, permission-limited, and
 * admin-unavailable routes. Keeps route identity compact and puts state →
 * reason → boundary → safe action ahead of empty canvas space.
 */
export const AccessGatePage: React.FC<AccessGatePageProps> = ({
  eyebrow,
  title,
  description,
  bullets,
  statusLabel,
  note,
  primaryAction,
  secondaryAction,
  tertiaryAction,
}) => (
  <section
    className="access-gate"
    data-testid="access-gate-page"
    aria-labelledby="access-gate-state-heading"
  >
    <WorkspacePageHeader
      density="compact"
      className="access-gate-identity"
      contentClassName="access-gate-identity-layout"
      titleClassName="access-gate-identity-title"
      eyebrow={
        <span className="access-gate-identity-eyebrow" data-testid="access-gate-eyebrow">
          {eyebrow}
        </span>
      }
      title={
        <span id="access-gate-state-heading" data-testid="access-gate-state-heading">
          {title}
        </span>
      }
    />

    <Card className="access-gate-panel max-w-3xl">
      <div className="access-gate-state-band" data-testid="access-gate-state-band">
        <div className="access-gate-state-icon" aria-hidden="true">
          <ShieldAlert className="size-5" />
        </div>
        <div className="access-gate-state-copy min-w-0 flex-1">
          {statusLabel ? (
            <span
              className="access-gate-status-pill"
              data-testid="access-gate-status-pill"
            >
              <span className="access-gate-status-marker" aria-hidden="true">
                ▲
              </span>
              <span>{statusLabel}</span>
            </span>
          ) : null}
          <p className="access-gate-state-summary" data-testid="access-gate-state-summary">
            {title}
          </p>
        </div>
      </div>

      <div className="access-gate-reason" data-testid="access-gate-reason">
        <p className="access-gate-section-label">Why access is limited</p>
        <p className="access-gate-reason-body">{description}</p>
      </div>

      {bullets.length > 0 ? (
        <div className="access-gate-boundary" data-testid="access-gate-boundary">
          <p className="access-gate-section-label">Capability / evidence boundary</p>
          <ul className="access-gate-boundary-list">
            {bullets.map((item) => (
              <li key={item} className="access-gate-boundary-item">
                <span className="access-gate-boundary-marker" aria-hidden="true">
                  ■
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="access-gate-actions" data-testid="access-gate-actions">
        <Link
          to={primaryAction.to}
          className="access-gate-action access-gate-action--primary"
          data-testid="access-gate-primary-action"
        >
          <span>{primaryAction.label}</span>
          <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
        {secondaryAction ? (
          <Link
            to={secondaryAction.to}
            className="access-gate-action access-gate-action--secondary"
            data-testid="access-gate-secondary-action"
          >
            {secondaryAction.label}
          </Link>
        ) : null}
        {tertiaryAction ? (
          <Link
            to={tertiaryAction.to}
            className="access-gate-action access-gate-action--tertiary"
            data-testid="access-gate-tertiary-action"
          >
            {tertiaryAction.label}
          </Link>
        ) : null}
      </div>

      {note ? (
        <p className="access-gate-note" data-testid="access-gate-note">
          {note}
        </p>
      ) : null}
    </Card>
  </section>
);
