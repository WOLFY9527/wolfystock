# Audit Evidence

> Status: Canonical lifecycle policy for tracked audit Markdown
> Scope: temporary audit evidence only; never current architecture or product policy

Audit reports preserve bounded evidence for unfinished remediation or decision
work. They are not general onboarding material, launch approval, or canonical
domain documentation. Read one only when the current task names it or the
documentation manifest routes the task to it.

The machine-readable lifecycle owner is
[`docs/documentation-manifest.json`](../documentation-manifest.json). Every
tracked audit Markdown entry must declare:

- classification as `temporary_evidence`;
- an owner;
- its paired machine evidence when one exists;
- a concrete retirement condition;
- deletion as the retirement action;
- whether the machine artifact also retires;
- no archive or compatibility copy.

Current tracked audit evidence covers residual failure remediation, test
performance and ownership, official macro provider-order decision work, and
backend/frontend simplification roadmaps. Their exact lifecycle conditions are
generated into the project manual from the manifest.

When the retirement condition is met, first migrate any still-durable rule to
its canonical owner and remove executable references. Then delete the report
and eligible machine artifact in the same scoped change. Do not move it to an
archive, history, completed-report, or compatibility directory.
