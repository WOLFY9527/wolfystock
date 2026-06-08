# WolfyStock Data Reliability Docs

Status: helper-contract entry for bounded data-reliability docs.

Use this lane when a future task needs inert/pure helper boundaries without
broad repo search.

## Helper Contract Index

- [Data Coverage Matrix v1](./data-coverage-matrix-v1.md)
  - Inert contract only; does not wire API, frontend, provider runtime, cache,
    or scoring behavior.
- [Consumer Projection Examples](./data-coverage-consumer-projection-examples.md)
  - Product-language examples only; not runtime wiring or surface-availability
    proof.
- [Provider Source Confidence Contract](./provider-source-confidence-contract.md)
  - Authority/score/display boundary reference; keep fail-closed semantics.
- [Evidence Readiness Matrix](./evidence-readiness-matrix.md)
  - Read-only evidence boundary map; not a launch/readiness claim.

## Code And Guard Pointers

- `src/services/data_coverage_matrix_contract.py`
  - Pure inert helper; caller-supplied metadata only.
- `src/services/data_coverage_surface_registry.py`
  - Static planning registry only; not route wiring.
- `tests/test_data_coverage_matrix_contract.py`
  - Offline contract coverage.
- `tests/test_data_coverage_matrix_consumer_projection_examples.py`
  - Consumer projection examples/fixtures.
- `tests/test_pure_helper_import_boundaries.py`
  - Import-boundary guard for inert helper lanes.
