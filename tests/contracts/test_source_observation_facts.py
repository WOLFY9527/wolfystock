"""Focused contracts for immutable source observation facts."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from src.contracts.evidence import (
    ObservationFreshness,
    RawAvailability,
    SourceClass,
    SourceIdentity,
    SourceObservationFacts,
    merge_source_observations,
)
from src.services.source_confidence_contract import (
    SourceConfidenceContract,
    coerce_source_confidence_contract,
)
from src.services.source_provenance_contract import build_source_provenance


REPO_ROOT = Path(__file__).resolve().parents[2]


def _identity(
    *,
    source_id: str = "official_quotes",
    source_class: SourceClass = SourceClass.OFFICIAL,
    is_proxy: bool = False,
    is_synthetic: bool = False,
    is_fixture: bool = False,
) -> SourceIdentity:
    return SourceIdentity(
        source_id=source_id,
        source_class=source_class,
        is_proxy=is_proxy,
        is_synthetic=is_synthetic,
        is_fixture=is_fixture,
    )


def _facts(
    *,
    identity: SourceIdentity | None = None,
    availability: RawAvailability = RawAvailability.AVAILABLE,
    freshness: ObservationFreshness = ObservationFreshness.LIVE,
    cached: bool = False,
) -> SourceObservationFacts:
    return SourceObservationFacts(
        identity=identity or _identity(),
        observed_at=datetime(2026, 7, 17, 1, 2, 3, tzinfo=timezone.utc),
        as_of=datetime(2026, 7, 17, 1, 0, 0, tzinfo=timezone.utc),
        raw_availability=availability,
        freshness=freshness,
        is_cached=cached,
    )


def test_source_identity_is_immutable_and_round_trips_without_alias_coercion() -> None:
    identity = _identity(
        source_id="licensed.vendor-v2",
        source_class=SourceClass.LICENSED,
    )

    projected = identity.to_dict()

    assert SourceIdentity.from_dict(json.loads(json.dumps(projected))) == identity
    assert projected == {
        "sourceId": "licensed.vendor-v2",
        "sourceClass": "licensed",
        "isProxy": False,
        "isSynthetic": False,
        "isFixture": False,
    }
    with pytest.raises(FrozenInstanceError):
        identity.source_id = "other"  # type: ignore[misc]
    with pytest.raises(ValueError, match="unexpected source identity fields"):
        SourceIdentity.from_dict({**projected, "sourceLabel": "Vendor"})


def test_proxy_synthetic_and_fixture_identities_remain_distinct() -> None:
    proxy = _identity(
        source_id="public_quote_proxy",
        source_class=SourceClass.THIRD_PARTY,
        is_proxy=True,
    )
    synthetic = _identity(
        source_id="generated_scenario",
        source_class=SourceClass.UNKNOWN,
        is_synthetic=True,
    )
    fixture = _identity(
        source_id="quote_fixture",
        source_class=SourceClass.UNKNOWN,
        is_synthetic=True,
        is_fixture=True,
    )

    assert proxy.is_proxy and not proxy.is_synthetic and not proxy.is_fixture
    assert synthetic.is_synthetic and not synthetic.is_proxy and not synthetic.is_fixture
    assert fixture.is_fixture and fixture.is_synthetic and not fixture.is_proxy
    assert len({proxy, synthetic, fixture}) == 3
    with pytest.raises(ValueError, match="official source cannot be proxy"):
        _identity(is_proxy=True)
    with pytest.raises(ValueError, match="fixture source must also be synthetic"):
        _identity(
            source_id="bad_fixture",
            source_class=SourceClass.UNKNOWN,
            is_fixture=True,
        )


def test_observation_times_are_explicit_and_unrelated_timestamps_are_rejected() -> None:
    facts = _facts()
    projected = facts.to_dict()

    assert projected["observedAt"] == "2026-07-17T01:02:03Z"
    assert projected["asOf"] == "2026-07-17T01:00:00Z"
    assert SourceObservationFacts.from_dict(projected) == facts
    with pytest.raises(FrozenInstanceError):
        facts.is_cached = True  # type: ignore[misc]
    for unrelated_time in ("attemptedAt", "generatedAt", "updatedAt", "cacheSavedAt"):
        with pytest.raises(ValueError, match="unexpected source observation fields"):
            SourceObservationFacts.from_dict(
                {**projected, unrelated_time: projected["observedAt"]}
            )
    with pytest.raises(ValueError, match="timezone-aware"):
        SourceObservationFacts(
            identity=facts.identity,
            observed_at=datetime(2026, 7, 17, 1, 2, 3),
            as_of=facts.as_of,
            raw_availability=facts.raw_availability,
            freshness=facts.freshness,
        )


@pytest.mark.parametrize(
    ("case", "raw_value", "availability"),
    [
        ("authoritative_empty", [], RawAvailability.AVAILABLE),
        ("observed_zero", 0, RawAvailability.AVAILABLE),
        ("unavailable", None, RawAvailability.UNAVAILABLE),
        ("missing", None, RawAvailability.MISSING),
    ],
    ids=("authoritative-empty", "observed-zero", "unavailable", "missing"),
)
def test_raw_availability_preserves_empty_zero_unavailable_and_missing(
    case: str,
    raw_value: object,
    availability: RawAvailability,
) -> None:
    facts = _facts(availability=availability)
    envelope = {"facts": facts.to_dict(), "rawValue": raw_value}
    round_trip = json.loads(json.dumps(envelope))

    assert SourceObservationFacts.from_dict(round_trip["facts"]).raw_availability is availability
    assert round_trip["rawValue"] == raw_value
    if case in {"authoritative_empty", "observed_zero"}:
        assert facts.identity.source_class is SourceClass.OFFICIAL
        assert facts.raw_availability is RawAvailability.AVAILABLE
    if case == "missing":
        assert facts.raw_availability is not RawAvailability.UNKNOWN


def test_cache_and_merge_preserve_identity_and_only_degrade_facts() -> None:
    live = _facts()
    cached = live.as_cached(freshness=ObservationFreshness.DELAYED)
    stale = cached.degrade(
        raw_availability=RawAvailability.MISSING,
        freshness=ObservationFreshness.STALE,
    )
    merged = merge_source_observations((live, cached, stale))

    assert cached.identity == live.identity
    assert cached.observed_at == live.observed_at
    assert cached.as_of == live.as_of
    assert cached.is_cached is True
    assert merged.identity == live.identity
    assert merged.raw_availability is RawAvailability.MISSING
    assert merged.freshness is ObservationFreshness.STALE
    assert merged.is_cached is True
    with pytest.raises(ValueError, match="cannot upgrade freshness"):
        stale.degrade(freshness=ObservationFreshness.FRESH)
    with pytest.raises(ValueError, match="cannot upgrade raw availability"):
        stale.degrade(raw_availability=RawAvailability.AVAILABLE)
    with pytest.raises(ValueError, match="different source identities"):
        merge_source_observations(
            (
                live,
                _facts(identity=_identity(source_id="another_official_source")),
            )
        )


def test_provider_cache_api_round_trip_uses_canonical_facts_in_existing_adapter() -> None:
    provider_facts = _facts(
        identity=_identity(
            source_id="licensed_quote_feed",
            source_class=SourceClass.LICENSED,
        ),
        freshness=ObservationFreshness.FRESH,
    )
    provider_contract = SourceConfidenceContract.from_observation_facts(
        provider_facts,
        source_label="Licensed Quote Feed",
        confidence_weight=0.9,
        coverage=1.0,
    )
    cached_facts = provider_contract.to_observation_facts().as_cached(
        freshness=ObservationFreshness.DELAYED,
    )
    cached_contract = SourceConfidenceContract.from_observation_facts(
        cached_facts,
        source_label=provider_contract.source_label,
        confidence_weight=provider_contract.confidence_weight,
        coverage=provider_contract.coverage,
    )

    api_payload = json.loads(json.dumps(cached_contract.to_dict()))
    api_contract = coerce_source_confidence_contract(api_payload)

    assert api_contract.to_observation_facts() == cached_facts
    assert api_payload["sourceObservation"] == cached_facts.to_dict()
    assert api_payload["source"] == "licensed_quote_feed"
    assert api_payload["freshness"] == "delayed"
    assert api_payload["asOf"] == "2026-07-17T01:00:00Z"


def test_existing_provenance_adapter_projects_facts_without_parallel_reclassification() -> None:
    facts = _facts(
        identity=_identity(
            source_id="public_quote_proxy",
            source_class=SourceClass.THIRD_PARTY,
            is_proxy=True,
        ),
        freshness=ObservationFreshness.DELAYED,
        cached=True,
    )

    entry = build_source_provenance(
        source_observation=facts,
        source_label="Public Quote Proxy",
        evidence_domain="quote",
        authority_tier="observation_only",
        observation_only=True,
    )

    assert entry["sourceObservation"] == facts.to_dict()
    assert entry["sourceId"] == "public_quote_proxy"
    assert entry["freshnessState"] == "delayed"
    assert entry["sourceTier"] == "proxy"
    assert entry["fallbackOrProxy"] is True

    synthetic_facts = _facts(
        identity=_identity(
            source_id="synthetic_observation",
            source_class=SourceClass.UNKNOWN,
            is_synthetic=True,
        ),
        freshness=ObservationFreshness.FRESH,
    )
    synthetic_entry = build_source_provenance(
        source_observation=synthetic_facts,
        source_label="Synthetic Observation",
        authority_tier="score_grade",
        score_contribution_allowed=True,
    )
    assert synthetic_entry["sourceTier"] == "synthetic"
    assert synthetic_entry["scoreContributionAllowed"] is False


def test_adapters_reject_outer_fields_that_conflict_with_canonical_facts() -> None:
    facts = _facts()
    contract = SourceConfidenceContract.from_observation_facts(
        facts,
        source_label="Official Quotes",
    )

    conflicting_api_payload = contract.to_dict()
    conflicting_api_payload["source"] = "different_source"
    with pytest.raises(ValueError, match="conflicts with sourceObservation"):
        SourceConfidenceContract.from_dict(conflicting_api_payload)

    with pytest.raises(ValueError, match="conflicts with sourceObservation"):
        build_source_provenance(
            source_observation=facts,
            source_id="different_source",
            source_label="Official Quotes",
        )


@pytest.mark.parametrize(
    ("facts", "legacy_freshness"),
    [
        (
            _facts(
                identity=_identity(
                    source_id="public_quote_proxy",
                    source_class=SourceClass.THIRD_PARTY,
                    is_proxy=True,
                ),
                freshness=ObservationFreshness.DELAYED,
            ),
            "fallback",
        ),
        (
            _facts(
                identity=_identity(
                    source_id="synthetic_observation",
                    source_class=SourceClass.UNKNOWN,
                    is_synthetic=True,
                ),
                freshness=ObservationFreshness.FRESH,
            ),
            "synthetic",
        ),
        (
            _facts(
                identity=_identity(
                    source_id="fixture_observation",
                    source_class=SourceClass.UNKNOWN,
                    is_synthetic=True,
                    is_fixture=True,
                ),
                freshness=ObservationFreshness.FRESH,
            ),
            "synthetic",
        ),
        (
            _facts(
                availability=RawAvailability.UNAVAILABLE,
                freshness=ObservationFreshness.STALE,
            ),
            "unavailable",
        ),
    ],
    ids=(
        "proxy-degrades-to-fallback",
        "synthetic-remains-distinct",
        "fixture-remains-distinct",
        "unavailable-remains-distinct",
    ),
)
def test_legacy_policy_may_degrade_but_never_replace_canonical_facts(
    facts: SourceObservationFacts,
    legacy_freshness: str,
) -> None:
    contract = SourceConfidenceContract.from_observation_facts(
        facts,
        source_label="Bounded Source",
        confidence_weight=1.0,
    )

    projected = coerce_source_confidence_contract(contract).to_dict()
    round_trip = SourceConfidenceContract.from_dict(projected)

    assert projected["freshness"] == legacy_freshness
    assert round_trip.to_observation_facts() == facts


def test_legacy_adapter_does_not_invent_identity_from_source_name() -> None:
    contract = coerce_source_confidence_contract(
        {
            "source": "fixture_named_but_unclassified",
            "sourceLabel": "Unclassified",
            "freshness": "fresh",
            "confidenceWeight": 0.8,
            "coverage": 1.0,
        }
    )

    assert contract.is_synthetic is False
    assert contract.freshness.value == "fresh"
    with pytest.raises(ValueError, match="canonical sourceObservation"):
        contract.to_observation_facts()


def test_shared_kernel_contains_no_domain_readiness_or_presentation_policy() -> None:
    fact_fields = {
        field.name
        for cls in (SourceIdentity, SourceObservationFacts)
        for field in fields(cls)
    }
    forbidden_tokens = {
        "market",
        "scanner",
        "backtest",
        "portfolio",
        "readiness",
        "threshold",
        "confidence",
        "score",
        "label",
        "tone",
        "consumer_state",
    }

    kernel_source = (
        REPO_ROOT / "src/contracts/evidence/source_observation.py"
    ).read_text(encoding="utf-8").lower()
    assert fact_fields.isdisjoint(forbidden_tokens)
    assert set(_facts().to_dict()).isdisjoint(forbidden_tokens)
    assert all(token not in kernel_source for token in forbidden_tokens)


def test_source_observation_fact_types_have_one_definition_in_allowed_scope() -> None:
    definitions: dict[str, list[Path]] = {
        "SourceIdentity": [],
        "SourceObservationFacts": [],
        "RawAvailability": [],
        "ObservationFreshness": [],
    }
    production_files = list((REPO_ROOT / "src/contracts/evidence").glob("*.py")) + [
        path
        for path in (REPO_ROOT / "src/services").glob("*.py")
        if "source_confidence" in path.name or "provenance" in path.name or "trust" in path.name
    ]
    for path in production_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in definitions:
                definitions[node.name].append(path.relative_to(REPO_ROOT))

    expected = Path("src/contracts/evidence/source_observation.py")
    assert definitions == {name: [expected] for name in definitions}
