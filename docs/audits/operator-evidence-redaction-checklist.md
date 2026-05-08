# Operator Evidence Redaction Checklist

Date: 2026-05-08
Scope: review checklist for offline operator evidence artifacts and reports.

Use this checklist before running validators, before creating a manifest, and
before handing a packet to reviewers. The packet must contain sanitized
operator evidence only.

## Required Checks

- Secrets: no API keys, access tokens, refresh tokens, webhook URLs, passwords,
  password hashes, private keys, recovery codes, or real secret values.
- Cookies and sessions: no cookies, session IDs, CSRF tokens, browser storage
  exports, auth headers, or bearer tokens.
- Request and response bodies: no raw API bodies, GraphQL payloads, form posts,
  HTTP headers, query strings, screenshots of bodies, or copied curl output.
- Provider payloads: no raw market-data, broker, LLM, news, fundamentals,
  options-chain, entitlement, quota, or error payloads from providers.
- Database material: no DB dumps, table exports, DSNs, connection strings,
  credentials, row-level user data, migrations copied from live systems, or
  backup file listings with sensitive paths.
- Logs and tracebacks: no raw logs, stack traces, exception text, SQL traces,
  provider error bodies, prompt text, LLM responses, or debug dumps.
- Personal identifiers: no real user IDs, account IDs, email addresses, phone
  numbers, names, IP addresses, device identifiers, broker account labels, or
  support transcript content.
- Credential-bearing locations: no URLs, paths, bucket names, filenames, or
  labels that embed credentials, tenant identifiers, or private infrastructure
  details.
- Approval wording: no wording that implies a tool result automatically
  authorizes release, deployment, public exposure, or launch acceptance.

## Allowed Replacement Patterns

Use bounded, reviewer-useful substitutes:

- `<sanitized-operator-label>`
- `<staging-environment-label>`
- `<redacted-or-configured>`
- `<review-ticket-label>`
- `<release-candidate-sha>`
- status labels such as `accepted`, `rejected`, and `needs-review`
- reason codes such as `credential_presence_redacted`
- counts, booleans, timestamps, and policy-version labels

## Before Handoff

Confirm:

- every placeholder that must be replaced was replaced with sanitized content;
- no sanitizer placeholder was replaced by a raw secret or private value;
- validator output contains bounded summaries only;
- the manifest contains checksums and filename labels only;
- the rendered report contains no raw JSON bodies;
- rejected or advisory items are clearly marked for manual review.

If any check fails, stop the handoff, remove the unsafe artifact from the packet,
rebuild it from the source records with sanitized summaries, and rerun the
validator and manifest steps.
