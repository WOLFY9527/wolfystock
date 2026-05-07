# Security Operator Acceptance Evidence Guide

This guide defines a sanitized, offline evidence artifact for two launch
blockers:

- MFA admin pilot operator acceptance.
- RBAC coarse fallback disabled staging acceptance.

The checker validates operator artifacts only. It does not change login,
session, MFA, RBAC, fallback behavior, route guards, admin capabilities, or
launch approval state. Final launch approval remains separate and must not be
claimed by this artifact.

## Safe Operator Checklist

Before attaching an artifact:

- Use only a staging or local acceptance environment label, not a URL with
  credentials.
- Use a bounded operator label such as `staging-operator-a`, not a real email,
  account name, or session identifier.
- Record timestamps and sampled control labels.
- Represent MFA pilot test accounts as sanitized role labels only, such as
  `admin_mfa_pilot` or `support_admin`.
- For RBAC fallback disabled acceptance, include `fallbackDisabled: true`.
- Include `runtimeBehaviorChanged: false` when recorded per section.
- Do not include screenshots, raw request bodies, raw response bodies, stack
  traces, debug payloads, cookies, session IDs, tokens, OTP seeds, recovery
  codes, passwords, private keys, or provider payloads.
- Do not include `launchApproved: true`, `releaseApproved: true`, or a launch
  decision of `GO`.

Run the offline validator:

```bash
python3 scripts/security_operator_acceptance_check.py --artifact <sanitized-security-operator-artifact.json>
```

A passing validator result returns `finalStatus: EVIDENCE-READY` with
`releaseApproved: false` and `launchApproved: false`.

## Sample Sanitized Artifact

```json
{
  "schemaVersion": "wolfystock_security_operator_acceptance_artifact_v1",
  "mfaAdminPilot": {
    "sanitizedOperator": "staging-operator-a",
    "timestamp": "2026-05-08T10:00:00Z",
    "environment": "staging",
    "outcome": "accepted",
    "sampledControls": ["mfa-required-login", "recovery-fallback", "rollback-check"],
    "evidenceRedactionVersion": "operator-redaction-v1",
    "testAccountRoleLabels": ["admin_mfa_pilot", "support_admin"],
    "runtimeBehaviorChanged": false
  },
  "rbacFallbackDisable": {
    "sanitizedOperator": "staging-operator-a",
    "timestamp": "2026-05-08T10:00:00Z",
    "environment": "staging",
    "outcome": "accepted",
    "sampledControls": ["legacy-admin-denied", "explicit-capability-allowed"],
    "evidenceRedactionVersion": "operator-redaction-v1",
    "fallbackDisabled": true,
    "legacyAdminDenied": true,
    "explicitCapabilitiesAccepted": true,
    "runtimeBehaviorChanged": false
  },
  "breakGlassRecovery": {
    "sanitizedOperator": "staging-operator-a",
    "timestamp": "2026-05-08T10:00:00Z",
    "environment": "staging",
    "outcome": "accepted",
    "sampledControls": ["break-glass-default-off", "recovery-code-fallback"],
    "evidenceRedactionVersion": "operator-redaction-v1",
    "breakGlassDefaultOff": true,
    "recoveryFallbackSampled": true,
    "runtimeBehaviorChanged": false
  },
  "adminRouteSampling": {
    "sanitizedOperator": "staging-operator-a",
    "timestamp": "2026-05-08T10:00:00Z",
    "environment": "staging",
    "outcome": "accepted",
    "sampledControls": ["admin-cost-route", "system-settings-route"],
    "evidenceRedactionVersion": "operator-redaction-v1",
    "sampledRoutes": ["/zh/admin/cost-observability", "/zh/settings/system"],
    "runtimeBehaviorChanged": false
  }
}
```

## Rejection Examples

The validator rejects artifacts that include sensitive or unbounded content:

```json
{
  "mfaAdminPilot": {
    "totpSecret": "[real value omitted]"
  }
}
```

```json
{
  "adminRouteSampling": {
    "rawRequestBody": "{\"cookie\":\"[redacted]\"}"
  }
}
```

```json
{
  "breakGlassRecovery": {
    "stackTrace": "Traceback (most recent call last)"
  }
}
```

The validator also rejects acceptance claims that belong to the final launch
gate:

```json
{
  "mfaAdminPilot": {
    "launchDecision": "GO"
  }
}
```

And it rejects incomplete launch-blocker evidence:

```json
{
  "rbacFallbackDisable": {
    "fallbackDisabled": false
  }
}
```

```json
{
  "mfaAdminPilot": {
    "testAccounts": [
      {
        "username": "[real username omitted]",
        "role": "admin"
      }
    ]
  }
}
```

## Scope Boundary

This evidence kit is intentionally not integrated into the global launch
acceptance matrix yet. It only validates sanitized operator attachments for
review. Runtime behavior is unchanged, and public launch approval remains
controlled by the existing launch acceptance process.
