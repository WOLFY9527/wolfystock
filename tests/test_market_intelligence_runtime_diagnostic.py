from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from src.services.options_market_data_provider import OptionsProviderUnavailable


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "diagnose_market_intelligence_runtime.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("diagnose_market_intelligence_runtime", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeTradierProbeTransport:
    def __init__(
        self,
        *,
        raw_secret: str = "synthetic_live_probe_secret_1234567890",
        chain_payload: dict | None = None,
    ) -> None:
        self.raw_secret = raw_secret
        self.chain_payload = chain_payload or {
            "options": {
                "option": [
                    {
                        "symbol": "TEM260619C00050000",
                        "option_type": "call",
                        "expiration_date": "2026-06-19",
                        "bid": "4.80",
                        "ask": "5.20",
                        "open_interest": "1480",
                        "greeks": {"mid_iv": "0.62", "delta": "0.61"},
                    },
                    {
                        "symbol": "TEM260619P00050000",
                        "option_type": "put",
                        "expiration_date": "2026-06-19",
                        "bid": None,
                        "ask": None,
                        "open_interest": None,
                        "greeks": {},
                    },
                ]
            },
        }
        self.calls: list[tuple[str, ...]] = []

    def get_quote(self, symbol: str) -> dict:
        self.calls.append(("quote", symbol))
        return {
            "quotes": {
                "quote": {
                    "symbol": symbol,
                    "last": 52.4,
                    "Authorization": f"Bearer {self.raw_secret}",
                }
            }
        }

    def get_expirations(self, symbol: str) -> dict:
        self.calls.append(("expirations", symbol))
        return {
            "expirations": {
                "date": ["2026-06-19", "2026-08-21"],
                "token": self.raw_secret,
            }
        }

    def get_chain(self, symbol: str, expiration: str | None = None) -> dict:
        self.calls.append(("chain", symbol, expiration or ""))
        return self.chain_payload


class _FailingTradierProbeTransport:
    def __init__(self, code: str, raw_secret: str) -> None:
        self.code = code
        self.raw_secret = raw_secret
        self.calls: list[tuple[str, str]] = []

    def get_quote(self, symbol: str) -> dict:
        self.calls.append(("quote", symbol))
        raise OptionsProviderUnavailable(
            "tradier",
            code=self.code,
            message=f"provider failed with Authorization Bearer {self.raw_secret}",
        )

    def get_expirations(self, symbol: str) -> dict:
        self.calls.append(("expirations", symbol))
        raise AssertionError("expirations should not run after quote failure")


def _providers_by_id(payload: dict) -> dict[str, dict]:
    return {
        str(item["providerId"]): item
        for item in payload["optionsLabProviderPreflight"]["providers"]
    }


def test_runtime_diagnostic_no_base_url_stays_local_only(monkeypatch) -> None:
    module = _load_script_module()

    monkeypatch.setattr(
        module,
        "run_official_macro_live_smoke",
        lambda: (_ for _ in ()).throw(AssertionError("official macro live smoke should not run")),
    )
    monkeypatch.setattr(
        module,
        "run_rotation_radar_alpaca_live_smoke",
        lambda: (_ for _ in ()).throw(AssertionError("alpaca live smoke should not run")),
    )
    monkeypatch.setattr(
        module,
        "run_polygon_us_breadth_activation",
        lambda: (_ for _ in ()).throw(AssertionError("polygon live smoke should not run")),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("endpoint fetch should not run")),
    )
    monkeypatch.setattr(
        module,
        "_build_tradier_options_live_probe_transport",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("tradier live probe should not run")),
    )

    payload = module.collect_diagnostic_bundle()

    assert payload == {
        "officialMacroDiagnostic": {
            "status": "skipped",
            "credentialsPresent": False,
            "providerConstructed": False,
            "probePassed": False,
            "freshnessValid": False,
            "sourceMetadataValid": False,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledSeries": [],
            "missingSeries": [],
            "staleSeries": [],
            "reason": "not_requested",
        },
        "alpacaRotationDiagnostic": {
            "status": "skipped",
            "credentialsPresent": False,
            "providerConstructed": False,
            "probePassed": False,
            "freshnessValid": False,
            "sourceMetadataValid": False,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledWindows": [],
            "missingWindows": [],
            "staleWindows": [],
            "reason": "not_requested",
        },
        "polygonUsBreadthDiagnostic": {
            "status": "skipped",
            "credentialsPresent": False,
            "probePassed": False,
            "observationDate": None,
            "freshnessValid": False,
            "coverageCount": 0,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledMetrics": [],
            "missingMetrics": [
                "ADVANCERS",
                "DECLINERS",
                "UNCHANGED",
                "ADVANCE_DECLINE_RATIO",
                "NEW_HIGHS",
                "NEW_LOWS",
                "HIGH_LOW_RATIO",
            ],
            "reasonCodes": ["not_requested"],
        },
        "optionsLabProviderPreflight": {
            "providers": [
                {
                    "providerId": "ibkr",
                    "readinessState": "disabled",
                    "credentialsPresent": False,
                    "credentialCounts": {
                        "required": 1,
                        "configured": 0,
                        "invalid": 0,
                        "partial": 0,
                    },
                    "dryRunEnabled": False,
                    "liveCallsEnabled": False,
                    "brokerOrderEnabled": False,
                    "portfolioMutationEnabled": False,
                    "tradeable": False,
                    "liveProbe": {
                        "status": "disabled",
                        "enabled": False,
                        "explicitOptIn": False,
                        "reasonCode": "options_provider_live_probe_disabled_by_default",
                        "timeoutSeconds": 2.0,
                        "networkCallExecuted": False,
                    },
                },
                {
                    "providerId": "polygon",
                    "readinessState": "disabled",
                    "credentialsPresent": False,
                    "credentialCounts": {
                        "required": 1,
                        "configured": 0,
                        "invalid": 0,
                        "partial": 0,
                    },
                    "dryRunEnabled": False,
                    "liveCallsEnabled": False,
                    "brokerOrderEnabled": False,
                    "portfolioMutationEnabled": False,
                    "tradeable": False,
                    "liveProbe": {
                        "status": "disabled",
                        "enabled": False,
                        "explicitOptIn": False,
                        "reasonCode": "options_provider_live_probe_disabled_by_default",
                        "timeoutSeconds": 2.0,
                        "networkCallExecuted": False,
                    },
                },
                {
                    "providerId": "tradier",
                    "readinessState": "disabled",
                    "credentialsPresent": False,
                    "credentialCounts": {
                        "required": 1,
                        "configured": 0,
                        "invalid": 0,
                        "partial": 0,
                    },
                    "dryRunEnabled": False,
                    "liveCallsEnabled": False,
                    "brokerOrderEnabled": False,
                    "portfolioMutationEnabled": False,
                    "tradeable": False,
                    "liveProbe": {
                        "status": "disabled",
                        "enabled": False,
                        "explicitOptIn": False,
                        "reasonCode": "options_provider_live_probe_disabled_by_default",
                        "timeoutSeconds": 2.0,
                        "networkCallExecuted": False,
                    },
                },
            ]
        },
        "optionsAuthorityDiagnostics": {
            "diagnosticOnly": True,
            "decisionGrade": False,
            "warning": "Authority diagnostics and checklist completeness are diagnostic-only and not decisionGrade.",
            "surfaces": [
                {
                    "surface": "iv_rank",
                    "authorityState": "non_authoritative",
                    "authoritative": False,
                    "diagnosticOnly": True,
                    "reasonCodes": [
                        "iv_rank_authority_missing",
                        "iv_rank_synthetic_fixture_proxy",
                        "iv_rank_fixture_not_authoritative",
                    ],
                },
                {
                    "surface": "event_calendar",
                    "authorityState": "missing",
                    "authoritative": False,
                    "diagnosticOnly": True,
                    "reasonCodes": [
                        "event_calendar_authority_missing",
                        "event_calendar_missing",
                        "event_calendar_source_authority_missing",
                    ],
                },
                {
                    "surface": "expiration_calendar",
                    "authorityState": "non_authoritative",
                    "authoritative": False,
                    "diagnosticOnly": True,
                    "reasonCodes": [
                        "expiration_calendar_authority_missing",
                        "expiration_calendar_fixture_not_authoritative",
                        "expiration_calendar_synthetic_not_authoritative",
                    ],
                },
            ],
        },
        "optionsAuthorityOperatorSummary": {
            "diagnosticOnly": True,
            "decisionGrade": False,
            "warning": "Checklist or candidate completeness is diagnostic-only and not authority; candidate evidence is not decision readiness; this summary is not decisionGrade.",
            "surfaceCount": 8,
            "authoritySurfaces": [
                "iv_rank",
                "event_calendar",
                "expiration_calendar",
            ],
            "candidateSurfaces": [
                "event_calendar_candidate_gap",
                "event_calendar_registry_candidate",
                "expiration_calendar_candidate_gap",
                "expiration_calendar_registry_candidate",
                "expiration_calendar_candidate_evidence",
            ],
            "allAuthoritative": False,
            "anyAuthorityGrant": False,
            "rows": [
                {
                    "surface": "iv_rank",
                    "authorityState": "non_authoritative",
                    "authoritative": False,
                    "candidateOnly": False,
                    "authorityGrant": False,
                    "reasonCodes": [
                        "iv_rank_authority_missing",
                        "iv_rank_synthetic_fixture_proxy",
                        "iv_rank_fixture_not_authoritative",
                    ],
                },
                {
                    "surface": "event_calendar",
                    "authorityState": "missing",
                    "authoritative": False,
                    "candidateOnly": False,
                    "authorityGrant": False,
                    "reasonCodes": [
                        "event_calendar_authority_missing",
                        "event_calendar_missing",
                        "event_calendar_source_authority_missing",
                    ],
                },
                {
                    "surface": "expiration_calendar",
                    "authorityState": "non_authoritative",
                    "authoritative": False,
                    "candidateOnly": False,
                    "authorityGrant": False,
                    "reasonCodes": [
                        "expiration_calendar_authority_missing",
                        "expiration_calendar_fixture_not_authoritative",
                        "expiration_calendar_synthetic_not_authoritative",
                    ],
                },
                {
                    "surface": "event_calendar_candidate_gap",
                    "sourceType": "licensed_event_calendar_provider",
                    "authoritative": False,
                    "candidateOnly": True,
                    "authorityGrant": False,
                    "missingEvidenceFamilies": [
                        "internal_policy_grant_missing",
                        "source_identity_provenance_chain_missing",
                        "licensed_backing_missing",
                    ],
                },
                {
                    "surface": "event_calendar_registry_candidate",
                    "sourceType": "missing",
                    "authoritative": False,
                    "candidateOnly": True,
                    "authorityGrant": False,
                    "metadataFamilies": [
                        "provenance",
                        "entitlement",
                        "slaFreshness",
                    ],
                },
                {
                    "surface": "expiration_calendar_candidate_gap",
                    "sourceType": "occ_opra_exchange_or_licensed_expiration_calendar",
                    "authoritative": False,
                    "candidateOnly": True,
                    "authorityGrant": False,
                    "missingEvidenceFamilies": [
                        "internal_policy_grant_missing",
                        "source_authority_provenance_missing",
                        "occ_opra_exchange_licensed_source_metadata_missing",
                    ],
                },
                {
                    "surface": "expiration_calendar_registry_candidate",
                    "sourceType": "missing",
                    "authoritative": False,
                    "candidateOnly": True,
                    "authorityGrant": False,
                    "metadataFamilies": [
                        "provenance",
                        "entitlement",
                        "slaFreshness",
                    ],
                },
                {
                    "surface": "expiration_calendar_candidate_evidence",
                    "authoritative": False,
                    "candidateOnly": True,
                    "authorityGrant": False,
                    "missingEvidenceFamilies": [
                        "source_identity_and_provenance_chain",
                        "licensed_source_backing",
                        "venue_and_calendar_scope",
                    ],
                },
            ],
        },
        "optionsEventSourceCandidateGap": {
            "diagnosticOnly": True,
            "surface": "event_calendar",
            "candidateOnly": True,
            "authorityGrant": False,
            "candidateSourceClass": "licensed_event_calendar_provider",
            "missingEvidenceFamilies": [
                "internal_policy_grant_missing",
                "source_identity_provenance_chain_missing",
                "licensed_backing_missing",
                "entitlement_use_rights_missing",
                "sla_freshness_missing",
                "event_taxonomy_missing",
                "confirmation_status_missing",
                "event_identity_missing",
                "timezone_session_missing",
                "coverage_scope_missing",
            ],
            "forbiddenAuthorityInputs": [
                "event_presence",
                "event_count",
                "event_type",
                "timeline_evidence",
                "generic_macro_context",
                "provider_capabilities",
                "source_labels",
                "provider_self_claims",
                "fixture",
                "synthetic",
                "fallback",
                "dry_run",
                "stub",
                "adapter_contract",
                "request_shaped_evidence",
                "proxy",
                "current_provider_id:tradier",
                "current_provider_id:ibkr",
                "current_provider_id:polygon",
            ],
            "requiredEvidenceFamilies": {
                "internal_policy_grant": [
                    "wolfystock_internal_policy_grant",
                    "surface_authority_approval",
                ],
                "source_identity_provenance_chain": [
                    "non_blocked_source_class",
                    "source_identity",
                    "source_authority",
                    "provenance_chain",
                ],
                "licensed_backing": [
                    "licensed_provider",
                    "exchange",
                    "issuer",
                    "official_calendar",
                    "approved_calendar_scope",
                ],
                "entitlement_use_rights": [
                    "event_calendar_entitlement",
                    "decision_use_rights",
                    "redistribution_rights",
                    "live_delayed_status",
                    "sandbox_or_production",
                ],
                "sla_freshness": [
                    "as_of",
                    "freshness",
                    "max_age_policy",
                    "provider_sla_status",
                ],
                "event_taxonomy": [
                    "earnings",
                    "dividends",
                    "ex_dividend",
                    "splits",
                    "corporate_actions",
                    "fomc_macro_context_policy_scope",
                ],
                "confirmation_status": [
                    "confirmed_or_estimated",
                    "announcement_status",
                ],
                "event_identity": [
                    "provider_event_id",
                    "event_identity",
                ],
                "timezone_session": [
                    "event_date",
                    "event_time",
                    "session",
                    "timezone",
                ],
                "coverage_scope": [
                    "symbol_or_underlying_coverage",
                    "lookahead_window_or_date_range",
                    "coverage_metadata",
                ],
            },
            "nextSafeStep": "collect_observation_only_metadata_without_granting_authority",
        },
        "optionsEventSourceRegistryCandidate": {
            "diagnosticOnly": True,
            "candidateOnly": True,
            "sourceKey": "options_lab.event_calendar_candidate_evidence",
            "sourceType": "missing",
            "sourceLabel": "Event Calendar Candidate Evidence (diagnostic only)",
            "candidateSourceClass": "licensed_event_calendar_provider",
            "metadataFamilies": {
                "provenance": [
                    "licensed_provider",
                    "exchange",
                    "issuer",
                    "official_calendar",
                    "approved_internal_source",
                ],
                "entitlement": [
                    "event_calendar_entitlement",
                    "live_delayed_status",
                    "environment",
                    "sandbox_or_production",
                    "decision_use_rights_evidence",
                    "redistribution_rights",
                    "audit_timestamp",
                ],
                "slaFreshness": [
                    "as_of",
                    "freshness",
                    "max_age_policy",
                    "provider_sla_status",
                    "freshness_state",
                    "latency_or_error_state",
                ],
                "eventTaxonomy": [
                    "earnings",
                    "dividends",
                    "ex_dividend",
                    "dividends_ex_dividend",
                    "splits",
                    "corporate_actions",
                    "macro_context_relevance",
                    "fomc_macro_context_policy_scope",
                ],
                "confirmation": [
                    "confirmed_or_estimated",
                    "announcement_status",
                ],
                "eventIdentity": [
                    "provider_event_id",
                    "event_identity",
                ],
                "timezoneSession": [
                    "event_date",
                    "event_time",
                    "session",
                    "timezone",
                ],
                "coverageScope": [
                    "symbol_or_underlying_coverage",
                    "lookahead_window_or_date_range",
                    "coverage_metadata",
                ],
            },
            "forbiddenAuthorityInputs": [
                "event_presence",
                "event_count",
                "event_type",
                "timeline_evidence",
                "generic_macro_context",
                "provider_capabilities",
                "provider_capability_metadata",
                "candidate_gap_metadata",
                "source_labels",
                "provider_self_claims",
                "current_provider_id",
                "fixture",
                "synthetic",
                "fallback",
                "dry_run",
                "stub",
                "adapter_contract",
                "request_shaped_evidence",
                "proxy",
            ],
            "warning": "Registry metadata is diagnostic-only, candidate-only, and non-authoritative.",
            "nextSafeStep": "document_candidate_evidence_only_without_approval",
        },
        "optionsExpirationSourceCandidateGap": {
            "diagnosticOnly": True,
            "surface": "expiration_calendar",
            "candidateOnly": True,
            "authorityGrant": False,
            "candidateSourceClass": "occ_opra_exchange_or_licensed_expiration_calendar",
            "missingEvidenceFamilies": [
                "internal_policy_grant_missing",
                "source_authority_provenance_missing",
                "occ_opra_exchange_licensed_source_metadata_missing",
                "entitlement_use_rights_missing",
                "sla_freshness_missing",
                "expiration_taxonomy_missing",
                "adjusted_deliverable_corporate_action_evidence_missing",
            ],
            "forbiddenAuthorityInputs": [
                "coverage_completeness",
                "provider_self_claims",
                "provider_capabilities",
                "fixtures",
                "dry_run",
                "adapter_contract",
                "request_shaped_evidence",
                "proxy",
                "current_provider_id:tradier",
                "current_provider_id:ibkr",
                "current_provider_id:polygon",
            ],
            "requiredEvidenceFamilies": {
                "internal_policy_grant": [
                    "wolfystock_internal_policy_grant",
                    "surface_authority_approval",
                ],
                "source_authority_provenance": [
                    "source_authority",
                    "provenance_chain",
                    "approved_source_class",
                ],
                "occ_opra_exchange_licensed_source_metadata": [
                    "occ_or_opra_or_exchange_or_licensed_source",
                    "venue",
                    "calendar_scope",
                    "source_license",
                ],
                "entitlement_use_rights": [
                    "options_entitlement",
                    "decision_use_rights",
                    "redistribution_rights",
                    "environment",
                ],
                "sla_freshness": [
                    "as_of",
                    "freshness",
                    "max_age_policy",
                    "provider_sla_status",
                ],
                "expiration_taxonomy": [
                    "weekly",
                    "monthly",
                    "quarterly",
                    "standard",
                    "leaps",
                    "special_expirations",
                    "classification_source",
                ],
                "adjusted_deliverable_corporate_action_evidence": [
                    "occ_memo_or_equivalent",
                    "effective_date",
                    "adjusted_root_or_class",
                    "deliverable_components",
                    "multiplier",
                    "cash_in_lieu",
                    "standard_or_non_standard",
                    "contract_symbol_mapping",
                    "corporate_action_evidence",
                ],
            },
            "nextSafeStep": "collect_observation_only_metadata_without_granting_authority",
        },
        "optionsExpirationSourceCandidateEvidence": {
            "diagnosticOnly": True,
            "candidateOnly": True,
            "authorityGrant": False,
            "missingEvidenceFamilies": [
                "source_identity_and_provenance_chain",
                "licensed_source_backing",
                "venue_and_calendar_scope",
                "entitlement_and_decision_use_rights",
                "production_vs_sandbox",
                "delayed_vs_live_status",
                "freshness_sla_and_max_age",
                "expiration_dates_count_and_range",
                "expiration_taxonomy",
                "adjusted_deliverable_and_corporate_action_proof",
                "occ_memo_or_equivalent_reference",
                "sanitized_error_and_audit_state",
            ],
            "forbiddenAuthorityOutputs": [
                "authorityGrant true",
                "providerDecisionAuthority",
                "recommendationAuthority",
                "decisionGrade",
                "gateDecision",
                "sourceAuthorityAllowed",
                "provider routing",
                "live-call enablement",
            ],
        },
        "optionsExpirationSourceRegistryCandidate": {
            "diagnosticOnly": True,
            "candidateOnly": True,
            "sourceKey": "options_lab.expiration_calendar_candidate_evidence",
            "sourceType": "missing",
            "sourceLabel": "Expiration Calendar Candidate Evidence (diagnostic only)",
            "candidateSourceClass": "occ_opra_exchange_or_licensed_expiration_calendar",
            "metadataFamilies": {
                "provenance": [
                    "occ",
                    "opra",
                    "exchange",
                    "licensed_provider",
                ],
                "entitlement": [
                    "options_entitlement",
                    "live_delayed_status",
                    "environment",
                    "decision_use_rights_evidence",
                    "redistribution_rights",
                    "audit_timestamp",
                ],
                "slaFreshness": [
                    "as_of",
                    "freshness",
                    "max_age_policy",
                    "provider_sla_status",
                    "freshness_state",
                    "latency_or_error_state",
                ],
                "expirationTaxonomy": [
                    "weekly",
                    "monthly",
                    "quarterly",
                    "standard",
                    "leaps",
                    "special_expirations",
                    "classification_source",
                ],
                "adjustedDeliverableCorporateAction": [
                    "occ_memo_or_equivalent",
                    "effective_date",
                    "adjusted_root_or_class",
                    "deliverable_components",
                    "multiplier",
                    "cash_in_lieu",
                    "standard_or_non_standard",
                    "contract_symbol_mapping",
                    "corporate_action_evidence",
                ],
            },
            "forbiddenAuthorityInputs": [
                "coverage_completeness",
                "provider_capabilities",
                "provider_self_claims",
                "current_provider_id",
                "fixture",
                "synthetic",
                "fallback",
                "dry_run",
                "adapter_contract",
                "request_shaped_evidence",
                "proxy",
            ],
            "warning": "Registry metadata is diagnostic-only, candidate-only, and non-authoritative.",
            "nextSafeStep": "document_candidate_evidence_only_without_approval",
        },
        "optionsIvRankAuthority": {
            "diagnosticOnly": True,
            "authorityState": "non_authoritative",
            "authoritative": False,
            "providerId": "synthetic_options_lab_fixture",
            "sourceType": "synthetic_fixture_proxy",
            "sourceAuthority": None,
            "ivRankStatus": "available",
            "ivRankSource": "synthetic_fixture_proxy",
            "authorityPolicySource": None,
            "asOf": None,
            "freshness": None,
            "lookbackWindow": None,
            "dateRange": None,
            "methodology": "local_min_max_percentile_from_proxy_history_plus_selected_contract_iv",
            "providerReportedIvRankAvailable": False,
            "providerReportedIvPercentileAvailable": False,
            "historicalOptionIvSeriesAvailable": False,
            "coverageMetadata": {
                "proxyHistoryPoints": 7,
                "currentIvSampleCount": 7,
                "currentIvDerivedFrom": "selected_contract_implied_volatility",
            },
            "sandboxOrProduction": "not_provider_sourced",
            "reasonCodes": [
                "iv_rank_authority_missing",
                "iv_rank_synthetic_fixture_proxy",
                "iv_rank_fixture_not_authoritative",
                "iv_rank_historical_option_iv_series_missing",
                "iv_rank_provider_reported_percentile_missing",
                "iv_rank_source_authority_missing",
                "iv_rank_asof_or_freshness_missing",
                "iv_rank_lookback_missing",
            ],
            "requiredFutureAuthorityEvidence": [
                "providerId",
                "sourceType",
                "sourceAuthority",
                "authorityPolicySource",
                "asOf",
                "freshness",
                "lookbackWindow",
                "dateRange",
                "methodology",
                "providerReportedIvRank",
                "providerReportedIvPercentile",
                "historicalOptionIvSeriesAvailable",
                "coverageMetadata",
                "sandboxOrProduction",
            ],
        },
        "optionsEventCalendarAuthority": {
            "diagnosticOnly": True,
            "authorityState": "missing",
            "authoritative": False,
            "providerId": None,
            "sourceType": None,
            "sourceAuthority": None,
            "eventCalendarStatus": "unavailable",
            "authorityPolicySource": None,
            "asOf": None,
            "freshness": None,
            "eventTypesCovered": [],
            "symbolCoverage": [],
            "underlyingCoverage": [],
            "lookaheadWindow": None,
            "dateRange": None,
            "timezone": None,
            "sessionMetadata": {},
            "confirmationStatus": None,
            "eventId": None,
            "providerEventId": None,
            "coverageMetadata": {},
            "sandboxOrProduction": None,
            "reasonCodes": [
                "event_calendar_authority_missing",
                "event_calendar_missing",
                "event_calendar_source_authority_missing",
                "event_calendar_asof_or_freshness_missing",
                "event_calendar_coverage_metadata_missing",
                "event_calendar_confirmation_status_missing",
                "event_calendar_event_identity_missing",
            ],
            "requiredFutureAuthorityEvidence": [
                "providerId",
                "sourceType",
                "sourceAuthority",
                "authorityPolicySource",
                "asOf",
                "freshness",
                "eventTypesCovered",
                "symbolCoverage",
                "underlyingCoverage",
                "lookaheadWindow",
                "dateRange",
                "timezone",
                "sessionMetadata",
                "confirmationStatus",
                "eventId",
                "providerEventId",
                "coverageMetadata",
                "sandboxOrProduction",
            ],
        },
        "optionsExpirationCalendarAuthority": {
            "diagnosticOnly": True,
            "authorityState": "non_authoritative",
            "authoritative": False,
            "providerId": "synthetic_options_lab_fixture",
            "sourceType": "fixture",
            "sourceAuthority": None,
            "expirationCalendarStatus": "available",
            "authorityPolicySource": None,
            "asOf": "2026-05-06T13:45:00Z",
            "freshness": None,
            "underlying": "TEM",
            "symbol": "TEM",
            "expirationDates": ["2026-06-19", "2026-08-21"],
            "expirationCount": 2,
            "expirationTypes": ["monthly"],
            "dateRange": {
                "start": "2026-06-19",
                "end": "2026-08-21",
            },
            "lookaheadWindow": None,
            "coverageMetadata": {
                "expirationCoverage": "complete",
                "expirationCount": 2,
                "chainAvailability": "complete",
            },
            "exchange": None,
            "occ": None,
            "opra": None,
            "authorizedSourceMetadata": {},
            "sandboxOrProduction": "not_provider_sourced",
            "reasonCodes": [
                "expiration_calendar_authority_missing",
                "expiration_calendar_fixture_not_authoritative",
                "expiration_calendar_synthetic_not_authoritative",
                "expiration_calendar_source_authority_missing",
                "expiration_calendar_asof_or_freshness_missing",
                "expiration_calendar_coverage_not_authority",
            ],
            "requiredFutureAuthorityEvidence": [
                "providerId",
                "sourceType",
                "sourceAuthority",
                "authorityPolicySource",
                "asOf",
                "freshness",
                "underlying",
                "symbol",
                "expirationDates",
                "expirationCount",
                "expirationTypes",
                "dateRange",
                "lookaheadWindow",
                "coverageMetadata",
                "exchange",
                "occ",
                "opra",
                "authorizedSourceMetadata",
                "sandboxOrProduction",
            ],
        },
        "usBreadthAuthorityDiagnostic": {
            "providerConstructed": False,
            "probePassed": False,
            "freshnessValid": False,
            "sourceMetadataValid": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledMetrics": [],
            "missingMetrics": [
                "ADVANCERS",
                "DECLINERS",
                "UNCHANGED",
                "ADVANCE_DECLINE_RATIO",
                "NEW_HIGHS",
                "NEW_LOWS",
                "HIGH_LOW_RATIO",
            ],
            "staleMetrics": [],
            "reason": "authorized_us_market_breadth_feed_not_configured",
            "sourceLabel": "Official or Authorized US Market Breadth",
            "sourceTier": "official_or_authorized_licensed_feed",
            "trustLevel": "score_grade_when_configured",
        },
        "discrepancies": [],
    }


def test_runtime_diagnostic_options_authority_summary_is_sanitized_and_non_authoritative(monkeypatch) -> None:
    module = _load_script_module()

    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("endpoint fetch should not run")),
    )
    monkeypatch.setattr(
        module,
        "_build_tradier_options_live_probe_transport",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("tradier live probe should not run")),
    )

    payload = module.collect_diagnostic_bundle()
    summary = payload["optionsAuthorityDiagnostics"]
    serialized = json.dumps(summary, ensure_ascii=False, sort_keys=True)

    assert "optionsIvRankAuthority" in payload
    assert "optionsEventSourceCandidateGap" in payload
    assert "optionsEventCalendarAuthority" in payload
    assert "optionsExpirationCalendarAuthority" in payload
    assert summary["diagnosticOnly"] is True
    assert summary["decisionGrade"] is False
    assert "not decisiongrade" in summary["warning"].lower()
    assert [item["surface"] for item in summary["surfaces"]] == [
        "iv_rank",
        "event_calendar",
        "expiration_calendar",
    ]
    assert all(item["authoritative"] is False for item in summary["surfaces"])
    assert all(item["diagnosticOnly"] is True for item in summary["surfaces"])
    assert all(len(item["reasonCodes"]) <= 3 for item in summary["surfaces"])
    for blocked in ("http://", "https://", "Authorization", "Bearer", "token", "secret"):
        assert blocked not in serialized


def test_runtime_diagnostic_options_authority_operator_summary_is_compact_and_safe(monkeypatch) -> None:
    module = _load_script_module()

    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("endpoint fetch should not run")),
    )
    monkeypatch.setattr(
        module,
        "_build_tradier_options_live_probe_transport",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("tradier live probe should not run")),
    )

    payload = module.collect_diagnostic_bundle()
    summary = payload["optionsAuthorityOperatorSummary"]
    rows = {row["surface"]: row for row in summary["rows"]}
    serialized = json.dumps(summary, ensure_ascii=False, sort_keys=True)

    assert "optionsAuthorityDiagnostics" in payload
    assert "optionsEventSourceCandidateGap" in payload
    assert "optionsExpirationSourceCandidateGap" in payload
    assert "optionsEventSourceRegistryCandidate" in payload
    assert "optionsExpirationSourceRegistryCandidate" in payload
    assert "optionsExpirationSourceCandidateEvidence" in payload
    assert summary["diagnosticOnly"] is True
    assert summary["decisionGrade"] is False
    assert "not authority" in summary["warning"].lower()
    assert "not decision readiness" in summary["warning"].lower()
    assert "not decisiongrade" in summary["warning"].lower()
    assert summary["surfaceCount"] == 8
    assert summary["authoritySurfaces"] == [
        "iv_rank",
        "event_calendar",
        "expiration_calendar",
    ]
    assert summary["candidateSurfaces"] == [
        "event_calendar_candidate_gap",
        "event_calendar_registry_candidate",
        "expiration_calendar_candidate_gap",
        "expiration_calendar_registry_candidate",
        "expiration_calendar_candidate_evidence",
    ]
    assert summary["allAuthoritative"] is False
    assert summary["anyAuthorityGrant"] is False
    assert all(row["authoritative"] is False for row in summary["rows"])
    assert all(row["authorityGrant"] is False for row in summary["rows"])
    assert rows["iv_rank"]["reasonCodes"] == [
        "iv_rank_authority_missing",
        "iv_rank_synthetic_fixture_proxy",
        "iv_rank_fixture_not_authoritative",
    ]
    assert rows["event_calendar_candidate_gap"]["missingEvidenceFamilies"] == [
        "internal_policy_grant_missing",
        "source_identity_provenance_chain_missing",
        "licensed_backing_missing",
    ]
    assert rows["event_calendar_registry_candidate"]["metadataFamilies"] == [
        "provenance",
        "entitlement",
        "slaFreshness",
    ]
    assert rows["expiration_calendar_candidate_evidence"]["missingEvidenceFamilies"] == [
        "source_identity_and_provenance_chain",
        "licensed_source_backing",
        "venue_and_calendar_scope",
    ]
    for row in summary["rows"]:
        assert "providerRouting" not in row
        assert "liveCallEnablement" not in row
        assert "networkCallExecuted" not in row
    for blocked in ("http://", "https://", "Authorization", "Bearer", "token", "secret", "rawPayload"):
        assert blocked not in serialized


def test_runtime_diagnostic_options_authority_summary_includes_safe_checklist_summary(monkeypatch) -> None:
    module = _load_script_module()

    monkeypatch.setattr(
        module,
        "_collect_options_iv_rank_authority",
        lambda: {
            "diagnosticOnly": True,
            "authorityState": "non_authoritative",
            "authoritative": False,
            "reasonCodes": [
                "iv_rank_authority_missing",
                "iv_rank_provenance_evidence_missing",
                "iv_rank_methodology_evidence_missing",
                "iv_rank_sla_evidence_missing",
            ],
            "authorityEvidenceChecklist": {
                "provenance": {"present": False},
                "methodology": {"present": False},
                "coverage_scope": {"present": True},
            },
            "authorityEvidenceGapFamilies": ["provenance", "methodology"],
        },
    )
    monkeypatch.setattr(
        module,
        "_collect_options_event_calendar_authority",
        lambda: {
            "diagnosticOnly": True,
            "authorityState": "missing",
            "authoritative": False,
            "reasonCodes": ["event_calendar_authority_missing"],
        },
    )
    monkeypatch.setattr(
        module,
        "_collect_options_expiration_calendar_authority",
        lambda: {
            "diagnosticOnly": True,
            "authorityState": "non_authoritative",
            "authoritative": False,
            "reasonCodes": ["expiration_calendar_authority_missing"],
        },
    )

    payload = module.collect_diagnostic_bundle()
    iv_rank_summary = payload["optionsAuthorityDiagnostics"]["surfaces"][0]

    assert iv_rank_summary["checklistSummary"] == {
        "presentFamilies": ["coverage_scope"],
        "missingFamilies": ["provenance", "methodology"],
    }


def test_runtime_diagnostic_projects_expiration_source_candidate_gap_safely(monkeypatch) -> None:
    module = _load_script_module()

    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("endpoint fetch should not run")),
    )
    monkeypatch.setattr(
        module,
        "_build_tradier_options_live_probe_transport",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("tradier live probe should not run")),
    )

    payload = module.collect_diagnostic_bundle()
    projection = payload["optionsExpirationSourceCandidateGap"]
    serialized = json.dumps(projection, ensure_ascii=False, sort_keys=True)

    assert projection["diagnosticOnly"] is True
    assert projection["surface"] == "expiration_calendar"
    assert projection["candidateOnly"] is True
    assert projection["authorityGrant"] is False
    assert projection["candidateSourceClass"] == "occ_opra_exchange_or_licensed_expiration_calendar"
    assert projection["missingEvidenceFamilies"] == [
        "internal_policy_grant_missing",
        "source_authority_provenance_missing",
        "occ_opra_exchange_licensed_source_metadata_missing",
        "entitlement_use_rights_missing",
        "sla_freshness_missing",
        "expiration_taxonomy_missing",
        "adjusted_deliverable_corporate_action_evidence_missing",
    ]
    assert projection["forbiddenAuthorityInputs"] == [
        "coverage_completeness",
        "provider_self_claims",
        "provider_capabilities",
        "fixtures",
        "dry_run",
        "adapter_contract",
        "request_shaped_evidence",
        "proxy",
        "current_provider_id:tradier",
        "current_provider_id:ibkr",
        "current_provider_id:polygon",
    ]
    assert projection["requiredEvidenceFamilies"] == {
        "internal_policy_grant": [
            "wolfystock_internal_policy_grant",
            "surface_authority_approval",
        ],
        "source_authority_provenance": [
            "source_authority",
            "provenance_chain",
            "approved_source_class",
        ],
        "occ_opra_exchange_licensed_source_metadata": [
            "occ_or_opra_or_exchange_or_licensed_source",
            "venue",
            "calendar_scope",
            "source_license",
        ],
        "entitlement_use_rights": [
            "options_entitlement",
            "decision_use_rights",
            "redistribution_rights",
            "environment",
        ],
        "sla_freshness": [
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
        ],
        "expiration_taxonomy": [
            "weekly",
            "monthly",
            "quarterly",
            "standard",
            "leaps",
            "special_expirations",
            "classification_source",
        ],
        "adjusted_deliverable_corporate_action_evidence": [
            "occ_memo_or_equivalent",
            "effective_date",
            "adjusted_root_or_class",
            "deliverable_components",
            "multiplier",
            "cash_in_lieu",
            "standard_or_non_standard",
            "contract_symbol_mapping",
            "corporate_action_evidence",
        ],
    }
    assert projection["nextSafeStep"] == "collect_observation_only_metadata_without_granting_authority"
    for blocked in ("http://", "https://", "Authorization", "Bearer", "token", "secret", "rawPayload"):
        assert blocked not in serialized


def test_runtime_diagnostic_projects_event_source_candidate_gap_safely(monkeypatch) -> None:
    module = _load_script_module()

    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("endpoint fetch should not run")),
    )
    monkeypatch.setattr(
        module,
        "_build_tradier_options_live_probe_transport",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("tradier live probe should not run")),
    )

    payload = module.collect_diagnostic_bundle()
    projection = payload["optionsEventSourceCandidateGap"]
    serialized = json.dumps(projection, ensure_ascii=False, sort_keys=True)

    assert projection["diagnosticOnly"] is True
    assert projection["surface"] == "event_calendar"
    assert projection["candidateOnly"] is True
    assert projection["authorityGrant"] is False
    assert projection["candidateSourceClass"] == "licensed_event_calendar_provider"
    assert projection["missingEvidenceFamilies"] == [
        "internal_policy_grant_missing",
        "source_identity_provenance_chain_missing",
        "licensed_backing_missing",
        "entitlement_use_rights_missing",
        "sla_freshness_missing",
        "event_taxonomy_missing",
        "confirmation_status_missing",
        "event_identity_missing",
        "timezone_session_missing",
        "coverage_scope_missing",
    ]
    assert projection["forbiddenAuthorityInputs"] == [
        "event_presence",
        "event_count",
        "event_type",
        "timeline_evidence",
        "generic_macro_context",
        "provider_capabilities",
        "source_labels",
        "provider_self_claims",
        "fixture",
        "synthetic",
        "fallback",
        "dry_run",
        "stub",
        "adapter_contract",
        "request_shaped_evidence",
        "proxy",
        "current_provider_id:tradier",
        "current_provider_id:ibkr",
        "current_provider_id:polygon",
    ]
    assert projection["requiredEvidenceFamilies"] == {
        "internal_policy_grant": [
            "wolfystock_internal_policy_grant",
            "surface_authority_approval",
        ],
        "source_identity_provenance_chain": [
            "non_blocked_source_class",
            "source_identity",
            "source_authority",
            "provenance_chain",
        ],
        "licensed_backing": [
            "licensed_provider",
            "exchange",
            "issuer",
            "official_calendar",
            "approved_calendar_scope",
        ],
        "entitlement_use_rights": [
            "event_calendar_entitlement",
            "decision_use_rights",
            "redistribution_rights",
            "live_delayed_status",
            "sandbox_or_production",
        ],
        "sla_freshness": [
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
        ],
        "event_taxonomy": [
            "earnings",
            "dividends",
            "ex_dividend",
            "splits",
            "corporate_actions",
            "fomc_macro_context_policy_scope",
        ],
        "confirmation_status": [
            "confirmed_or_estimated",
            "announcement_status",
        ],
        "event_identity": [
            "provider_event_id",
            "event_identity",
        ],
        "timezone_session": [
            "event_date",
            "event_time",
            "session",
            "timezone",
        ],
        "coverage_scope": [
            "symbol_or_underlying_coverage",
            "lookahead_window_or_date_range",
            "coverage_metadata",
        ],
    }
    assert projection["nextSafeStep"] == "collect_observation_only_metadata_without_granting_authority"
    for blocked in ("http://", "https://", "Authorization", "Bearer", "token", "secret", "rawPayload"):
        assert blocked not in serialized


def test_runtime_diagnostic_projects_event_source_registry_candidate_safely(monkeypatch) -> None:
    module = _load_script_module()

    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("endpoint fetch should not run")),
    )
    monkeypatch.setattr(
        module,
        "_build_tradier_options_live_probe_transport",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("tradier live probe should not run")),
    )

    payload = module.collect_diagnostic_bundle()
    projection = payload["optionsEventSourceRegistryCandidate"]
    serialized = json.dumps(projection, ensure_ascii=False, sort_keys=True)

    assert projection["diagnosticOnly"] is True
    assert projection["candidateOnly"] is True
    assert projection["sourceKey"] == "options_lab.event_calendar_candidate_evidence"
    assert projection["sourceType"] == "missing"
    assert projection["sourceLabel"] == "Event Calendar Candidate Evidence (diagnostic only)"
    assert projection["candidateSourceClass"] == "licensed_event_calendar_provider"
    assert projection["metadataFamilies"] == {
        "provenance": [
            "licensed_provider",
            "exchange",
            "issuer",
            "official_calendar",
            "approved_internal_source",
        ],
        "entitlement": [
            "event_calendar_entitlement",
            "live_delayed_status",
            "environment",
            "sandbox_or_production",
            "decision_use_rights_evidence",
            "redistribution_rights",
            "audit_timestamp",
        ],
        "slaFreshness": [
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
            "freshness_state",
            "latency_or_error_state",
        ],
        "eventTaxonomy": [
            "earnings",
            "dividends",
            "ex_dividend",
            "dividends_ex_dividend",
            "splits",
            "corporate_actions",
            "macro_context_relevance",
            "fomc_macro_context_policy_scope",
        ],
        "confirmation": [
            "confirmed_or_estimated",
            "announcement_status",
        ],
        "eventIdentity": [
            "provider_event_id",
            "event_identity",
        ],
        "timezoneSession": [
            "event_date",
            "event_time",
            "session",
            "timezone",
        ],
        "coverageScope": [
            "symbol_or_underlying_coverage",
            "lookahead_window_or_date_range",
            "coverage_metadata",
        ],
    }
    assert projection["forbiddenAuthorityInputs"] == [
        "event_presence",
        "event_count",
        "event_type",
        "timeline_evidence",
        "generic_macro_context",
        "provider_capabilities",
        "provider_capability_metadata",
        "candidate_gap_metadata",
        "source_labels",
        "provider_self_claims",
        "current_provider_id",
        "fixture",
        "synthetic",
        "fallback",
        "dry_run",
        "stub",
        "adapter_contract",
        "request_shaped_evidence",
        "proxy",
    ]
    assert "non-authoritative" in projection["warning"].lower()
    assert projection["nextSafeStep"] == "document_candidate_evidence_only_without_approval"
    for forbidden_field in (
        "authorityGrant",
        "decisionGrade",
        "providerDecisionAuthority",
        "recommendationAuthority",
        "gateDecision",
        "sourceAuthorityAllowed",
        "providerRouting",
        "liveCallEnablement",
        "providerSelfClaimAuthority",
    ):
        assert forbidden_field not in projection
    for blocked in ("http://", "https://", "Authorization", "Bearer", "token", "secret", "rawPayload"):
        assert blocked not in serialized


def test_runtime_diagnostic_projects_expiration_source_registry_candidate_safely(monkeypatch) -> None:
    module = _load_script_module()

    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("endpoint fetch should not run")),
    )
    monkeypatch.setattr(
        module,
        "_build_tradier_options_live_probe_transport",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("tradier live probe should not run")),
    )

    payload = module.collect_diagnostic_bundle()
    projection = payload["optionsExpirationSourceRegistryCandidate"]
    serialized = json.dumps(projection, ensure_ascii=False, sort_keys=True)

    assert projection["diagnosticOnly"] is True
    assert projection["candidateOnly"] is True
    assert projection["sourceKey"] == "options_lab.expiration_calendar_candidate_evidence"
    assert projection["sourceType"] == "missing"
    assert projection["sourceLabel"] == "Expiration Calendar Candidate Evidence (diagnostic only)"
    assert projection["candidateSourceClass"] == "occ_opra_exchange_or_licensed_expiration_calendar"
    assert projection["metadataFamilies"] == {
        "provenance": [
            "occ",
            "opra",
            "exchange",
            "licensed_provider",
        ],
        "entitlement": [
            "options_entitlement",
            "live_delayed_status",
            "environment",
            "decision_use_rights_evidence",
            "redistribution_rights",
            "audit_timestamp",
        ],
        "slaFreshness": [
            "as_of",
            "freshness",
            "max_age_policy",
            "provider_sla_status",
            "freshness_state",
            "latency_or_error_state",
        ],
        "expirationTaxonomy": [
            "weekly",
            "monthly",
            "quarterly",
            "standard",
            "leaps",
            "special_expirations",
            "classification_source",
        ],
        "adjustedDeliverableCorporateAction": [
            "occ_memo_or_equivalent",
            "effective_date",
            "adjusted_root_or_class",
            "deliverable_components",
            "multiplier",
            "cash_in_lieu",
            "standard_or_non_standard",
            "contract_symbol_mapping",
            "corporate_action_evidence",
        ],
    }
    assert projection["forbiddenAuthorityInputs"] == [
        "coverage_completeness",
        "provider_capabilities",
        "provider_self_claims",
        "current_provider_id",
        "fixture",
        "synthetic",
        "fallback",
        "dry_run",
        "adapter_contract",
        "request_shaped_evidence",
        "proxy",
    ]
    assert "non-authoritative" in projection["warning"].lower()
    assert projection["nextSafeStep"] == "document_candidate_evidence_only_without_approval"
    for forbidden_field in (
        "authorityGrant",
        "decisionGrade",
        "providerDecisionAuthority",
        "recommendationAuthority",
        "gateDecision",
        "sourceAuthorityAllowed",
        "providerRouting",
        "liveCallEnablement",
        "providerSelfClaimAuthority",
    ):
        assert forbidden_field not in projection
    for blocked in ("http://", "https://", "Authorization", "Bearer", "token", "secret", "rawPayload"):
        assert blocked not in serialized


def test_runtime_diagnostic_projects_expiration_source_candidate_evidence_safely(
    monkeypatch,
) -> None:
    module = _load_script_module()

    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("endpoint fetch should not run")),
    )
    monkeypatch.setattr(
        module,
        "_build_tradier_options_live_probe_transport",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("tradier live probe should not run")),
    )

    payload = module.collect_diagnostic_bundle()
    projection = payload["optionsExpirationSourceCandidateEvidence"]
    serialized = json.dumps(projection, ensure_ascii=False, sort_keys=True)

    assert "optionsEventSourceCandidateGap" in payload
    assert "optionsExpirationSourceCandidateGap" in payload
    assert "optionsEventSourceRegistryCandidate" in payload
    assert "optionsExpirationSourceRegistryCandidate" in payload
    assert "optionsAuthorityDiagnostics" in payload
    assert "optionsIvRankAuthority" in payload
    assert "optionsEventCalendarAuthority" in payload
    assert "optionsExpirationCalendarAuthority" in payload
    assert projection == {
        "diagnosticOnly": True,
        "candidateOnly": True,
        "authorityGrant": False,
        "missingEvidenceFamilies": [
            "source_identity_and_provenance_chain",
            "licensed_source_backing",
            "venue_and_calendar_scope",
            "entitlement_and_decision_use_rights",
            "production_vs_sandbox",
            "delayed_vs_live_status",
            "freshness_sla_and_max_age",
            "expiration_dates_count_and_range",
            "expiration_taxonomy",
            "adjusted_deliverable_and_corporate_action_proof",
            "occ_memo_or_equivalent_reference",
            "sanitized_error_and_audit_state",
        ],
        "forbiddenAuthorityOutputs": [
            "authorityGrant true",
            "providerDecisionAuthority",
            "recommendationAuthority",
            "decisionGrade",
            "gateDecision",
            "sourceAuthorityAllowed",
            "provider routing",
            "live-call enablement",
        ],
    }
    assert projection["diagnosticOnly"] is True
    assert projection["candidateOnly"] is True
    assert projection["authorityGrant"] is False
    assert projection["missingEvidenceFamilies"]
    assert "decisionGrade" not in {
        key for key, value in projection.items() if key != "forbiddenAuthorityOutputs" and value is not False
    }
    for blocked in ("http://", "https://", "Authorization", "Bearer", "token", "secret", "rawPayload"):
        assert blocked not in serialized


def test_runtime_diagnostic_live_smoke_is_explicit_opt_in(monkeypatch) -> None:
    module = _load_script_module()
    calls = {"official": 0, "alpaca": 0, "polygon": 0}

    monkeypatch.setattr(
        module,
        "run_official_macro_live_smoke",
        lambda: calls.__setitem__("official", calls["official"] + 1) or {
            "credentialsPresent": True,
            "providerConstructed": True,
            "probePassed": True,
            "freshnessValid": True,
            "sourceMetadataValid": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "fulfilledSeries": ["VIXCLS", "SOFR"],
            "missingSeries": [],
            "staleSeries": [],
            "reason": None,
        },
    )
    monkeypatch.setattr(
        module,
        "run_rotation_radar_alpaca_live_smoke",
        lambda: calls.__setitem__("alpaca", calls["alpaca"] + 1) or {
            "credentialsPresent": False,
            "providerConstructed": False,
            "probePassed": False,
            "freshnessValid": False,
            "sourceMetadataValid": False,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledWindows": [],
            "missingWindows": ["5m", "15m", "60m", "1d"],
            "staleWindows": [],
            "reason": "credentials",
        },
    )
    monkeypatch.setattr(
        module,
        "run_polygon_us_breadth_activation",
        lambda: calls.__setitem__("polygon", calls["polygon"] + 1) or {
            "credentialsPresent": False,
            "providerConstructed": False,
            "probePassed": False,
            "observationDate": None,
            "freshnessValid": False,
            "coverageCount": 0,
            "sourceMetadataValid": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledMetrics": [],
            "missingMetrics": list(module.US_BREADTH_SYMBOLS),
            "reasonCodes": ["authorized_us_market_breadth_feed_not_configured"],
        },
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("endpoint fetch should not run")),
    )

    payload = module.collect_diagnostic_bundle(include_live_smoke=True)

    assert calls == {"official": 1, "alpaca": 1, "polygon": 1}
    assert payload["officialMacroDiagnostic"]["probePassed"] is True
    assert payload["alpacaRotationDiagnostic"]["reason"] == "credentials"
    assert payload["polygonUsBreadthDiagnostic"]["reasonCodes"] == [
        "authorized_us_market_breadth_feed_not_configured"
    ]


def test_runtime_diagnostic_includes_offline_options_lab_provider_preflight(monkeypatch) -> None:
    module = _load_script_module()
    sentinel_config = object()
    preflight_calls: list[tuple[str, object]] = []

    class FakeOptionsLiveProviderConfig:
        @staticmethod
        def from_env():
            return sentinel_config

    def fake_build_options_provider_live_readiness_preflight(provider_name: str, config=None, **kwargs):
        preflight_calls.append((provider_name, config))
        return {
            "providerName": provider_name,
            "readinessState": "dry_run_enabled" if provider_name == "tradier" else "disabled",
            "credentialsPresent": provider_name == "tradier",
            "credentialContract": {
                "requiredCredentialCount": 1,
                "configuredCredentialCount": 1 if provider_name == "tradier" else 0,
                "invalidCredentialCount": 0,
                "partialCredentialCount": 0,
            },
            "dryRunEnabled": provider_name == "tradier",
            "liveHttpCallsEnabled": False,
            "brokerOrderPathEnabled": False,
            "portfolioMutationPathEnabled": False,
            "tradeableData": False,
            "liveProbe": {
                "enabled": provider_name == "tradier",
                "explicitOptIn": provider_name == "tradier",
                "reasonCode": "options_provider_live_probe_operator_opt_in_ready"
                if provider_name == "tradier"
                else "options_provider_live_probe_disabled_by_default",
                "timeoutSeconds": 2.0,
                "networkCallExecuted": False,
                "apiKey": "must-not-leak",
            },
            "message": "token=must-not-leak",
            "providerCapabilities": {"accountId": "must-not-leak"},
        }

    monkeypatch.setattr(module, "OptionsLiveProviderConfig", FakeOptionsLiveProviderConfig)
    monkeypatch.setattr(
        module,
        "build_options_provider_live_readiness_preflight",
        fake_build_options_provider_live_readiness_preflight,
    )
    monkeypatch.setattr(
        module,
        "_fetch_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("endpoint fetch should not run")),
    )

    payload = module.collect_diagnostic_bundle()
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    assert preflight_calls == [("ibkr", sentinel_config), ("polygon", sentinel_config), ("tradier", sentinel_config)]
    assert payload["optionsLabProviderPreflight"] == {
        "providers": [
            {
                "providerId": "ibkr",
                "readinessState": "disabled",
                "credentialsPresent": False,
                "credentialCounts": {
                    "required": 1,
                    "configured": 0,
                    "invalid": 0,
                    "partial": 0,
                },
                "dryRunEnabled": False,
                "liveCallsEnabled": False,
                "brokerOrderEnabled": False,
                "portfolioMutationEnabled": False,
                "tradeable": False,
                "liveProbe": {
                    "status": "disabled",
                    "enabled": False,
                    "explicitOptIn": False,
                    "reasonCode": "options_provider_live_probe_disabled_by_default",
                    "timeoutSeconds": 2.0,
                    "networkCallExecuted": False,
                },
            },
            {
                "providerId": "polygon",
                "readinessState": "disabled",
                "credentialsPresent": False,
                "credentialCounts": {
                    "required": 1,
                    "configured": 0,
                    "invalid": 0,
                    "partial": 0,
                },
                "dryRunEnabled": False,
                "liveCallsEnabled": False,
                "brokerOrderEnabled": False,
                "portfolioMutationEnabled": False,
                "tradeable": False,
                "liveProbe": {
                    "status": "disabled",
                    "enabled": False,
                    "explicitOptIn": False,
                    "reasonCode": "options_provider_live_probe_disabled_by_default",
                    "timeoutSeconds": 2.0,
                    "networkCallExecuted": False,
                },
            },
            {
                "providerId": "tradier",
                "readinessState": "dry_run_enabled",
                "credentialsPresent": True,
                "credentialCounts": {
                    "required": 1,
                    "configured": 1,
                    "invalid": 0,
                    "partial": 0,
                },
                "dryRunEnabled": True,
                "liveCallsEnabled": False,
                "brokerOrderEnabled": False,
                "portfolioMutationEnabled": False,
                "tradeable": False,
                "liveProbe": {
                    "status": "ready",
                    "enabled": True,
                    "explicitOptIn": True,
                    "reasonCode": "options_provider_live_probe_operator_opt_in_ready",
                    "timeoutSeconds": 2.0,
                    "networkCallExecuted": False,
                },
            },
        ]
    }
    for blocked in ("must-not-leak", "token", "apiKey", "accountId"):
        assert blocked not in serialized


def test_runtime_diagnostic_parses_explicit_tradier_options_live_probe_cli() -> None:
    module = _load_script_module()

    args = module._parse_args(
        [
            "--options-live-probe",
            "--options-provider",
            "tradier",
            "--options-probe-symbol",
            "TEM",
        ]
    )

    assert args.options_live_probe is True
    assert args.options_provider == "tradier"
    assert args.options_probe_symbol == "TEM"
    assert args.options_probe_chain is False
    assert args.options_probe_expiration is None


def test_runtime_diagnostic_parses_explicit_tradier_chain_probe_cli() -> None:
    module = _load_script_module()

    args = module._parse_args(
        [
            "--options-live-probe",
            "--options-provider",
            "tradier",
            "--options-probe-symbol",
            "TEM",
            "--options-probe-chain",
            "--options-probe-expiration",
            "2026-06-19",
        ]
    )

    assert args.options_live_probe is True
    assert args.options_probe_chain is True
    assert args.options_probe_expiration == "2026-06-19"


def test_runtime_diagnostic_options_live_probe_missing_credentials_blocks_without_network(
    monkeypatch,
) -> None:
    module = _load_script_module()
    monkeypatch.delenv("TRADIER_API_TOKEN", raising=False)
    monkeypatch.delenv("TRADIER_SANDBOX_API_TOKEN", raising=False)
    monkeypatch.setattr(
        module,
        "_build_tradier_options_live_probe_transport",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("transport should not be built")),
    )

    payload = module.collect_diagnostic_bundle(
        options_live_probe=True,
        options_provider="tradier",
        options_probe_symbol="TEM",
        options_probe_chain=True,
    )
    tradier = _providers_by_id(payload)["tradier"]
    live_probe = tradier["liveProbe"]

    assert tradier["liveCallsEnabled"] is False
    assert tradier["tradeable"] is False
    assert live_probe["status"] == "blocked_missing_credentials"
    assert live_probe["explicitOptIn"] is True
    assert live_probe["networkCallExecuted"] is False
    assert live_probe["endpointClasses"] == []
    assert live_probe["providerId"] == "tradier"
    assert live_probe["endpointResults"] == []
    assert live_probe["sanitizedErrorCode"] == "options_provider_credentials_missing"


def test_runtime_diagnostic_options_live_probe_executes_mocked_tradier_transport_safely(
    monkeypatch,
) -> None:
    module = _load_script_module()
    raw_secret = "synthetic_live_probe_secret_1234567890"
    transport = _FakeTradierProbeTransport(raw_secret=raw_secret)
    monkeypatch.setenv("TRADIER_API_TOKEN", raw_secret)
    monkeypatch.setattr(
        module,
        "_build_tradier_options_live_probe_transport",
        lambda *args, **kwargs: transport,
    )

    payload = module.collect_diagnostic_bundle(
        options_live_probe=True,
        options_provider="tradier",
        options_probe_symbol="TEM",
    )
    tradier = _providers_by_id(payload)["tradier"]
    live_probe = tradier["liveProbe"]
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    assert transport.calls == [("quote", "TEM"), ("expirations", "TEM")]
    assert tradier["liveCallsEnabled"] is False
    assert tradier["brokerOrderEnabled"] is False
    assert tradier["portfolioMutationEnabled"] is False
    assert tradier["tradeable"] is False
    assert payload["optionsAuthorityDiagnostics"]["decisionGrade"] is False
    assert "decisionGrade" not in json.dumps(payload["optionsIvRankAuthority"], ensure_ascii=False, sort_keys=True)
    assert "decisionGrade" not in json.dumps(
        payload["optionsEventCalendarAuthority"], ensure_ascii=False, sort_keys=True
    )
    assert "decisionGrade" not in json.dumps(
        payload["optionsExpirationCalendarAuthority"], ensure_ascii=False, sort_keys=True
    )
    assert live_probe["providerId"] == "tradier"
    assert live_probe["status"] == "passed"
    assert live_probe["networkCallExecuted"] is True
    assert live_probe["endpointClasses"] == ["quote", "expirations"]
    assert live_probe["quoteShapeStatus"] == "object"
    assert live_probe["expirationCount"] == 2
    assert live_probe["chainContractCount"] == 0
    assert live_probe["chainHasBidAsk"] is False
    assert live_probe["chainHasBidAskCount"] == 0
    assert live_probe["chainHasOpenInterest"] is False
    assert live_probe["chainHasOpenInterestCount"] == 0
    assert live_probe["chainHasIvGreeks"] is False
    assert live_probe["chainHasIvGreeksCount"] == 0
    assert live_probe["endpointResults"] == [
        {
            "endpointClass": "quote",
            "status": "ok",
            "responseShape": {"status": "object", "count": 1},
        },
        {
            "endpointClass": "expirations",
            "status": "ok",
            "responseShape": {"status": "list", "count": 2},
        },
    ]
    for blocked in (
        raw_secret,
        "Authorization",
        "Bearer",
        "token",
        "rawPayload",
        "quote\": {",
        "expirations\": {",
        "place_order",
        "submit_order",
        "mutate_portfolio",
    ):
        assert blocked not in serialized


def test_runtime_diagnostic_options_chain_probe_executes_mocked_tradier_chain_safely(
    monkeypatch,
) -> None:
    module = _load_script_module()
    raw_secret = "synthetic_chain_probe_secret_1234567890"
    transport = _FakeTradierProbeTransport(raw_secret=raw_secret)
    monkeypatch.setenv("TRADIER_API_TOKEN", raw_secret)
    monkeypatch.setattr(
        module,
        "_build_tradier_options_live_probe_transport",
        lambda *args, **kwargs: transport,
    )

    payload = module.collect_diagnostic_bundle(
        options_live_probe=True,
        options_provider="tradier",
        options_probe_symbol="TEM",
        options_probe_chain=True,
    )
    tradier = _providers_by_id(payload)["tradier"]
    live_probe = tradier["liveProbe"]
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    assert transport.calls == [
        ("quote", "TEM"),
        ("expirations", "TEM"),
        ("chain", "TEM", "2026-06-19"),
    ]
    assert tradier["liveCallsEnabled"] is False
    assert tradier["brokerOrderEnabled"] is False
    assert tradier["portfolioMutationEnabled"] is False
    assert tradier["tradeable"] is False
    assert payload["optionsAuthorityDiagnostics"]["decisionGrade"] is False
    assert "decisionGrade" not in json.dumps(payload["optionsIvRankAuthority"], ensure_ascii=False, sort_keys=True)
    assert "decisionGrade" not in json.dumps(
        payload["optionsEventCalendarAuthority"], ensure_ascii=False, sort_keys=True
    )
    assert "decisionGrade" not in json.dumps(
        payload["optionsExpirationCalendarAuthority"], ensure_ascii=False, sort_keys=True
    )
    assert live_probe["providerId"] == "tradier"
    assert live_probe["status"] == "passed"
    assert live_probe["networkCallExecuted"] is True
    assert live_probe["endpointClasses"] == ["quote", "expirations", "chain"]
    assert live_probe["quoteShapeStatus"] == "object"
    assert live_probe["expirationCount"] == 2
    assert live_probe["chainContractCount"] == 2
    assert live_probe["chainHasBidAsk"] is True
    assert live_probe["chainHasBidAskCount"] == 1
    assert live_probe["chainHasOpenInterest"] is True
    assert live_probe["chainHasOpenInterestCount"] == 1
    assert live_probe["chainHasIvGreeks"] is True
    assert live_probe["chainHasIvGreeksCount"] == 1
    for blocked in (
        raw_secret,
        "Authorization",
        "Bearer",
        "token",
        "rawPayload",
        "options\": {",
        "place_order",
        "submit_order",
        "create_order",
        "mutate_portfolio",
        "sync_broker",
    ):
        assert blocked not in serialized


def test_runtime_diagnostic_options_chain_probe_malformed_payload_fails_closed_safely(
    monkeypatch,
) -> None:
    module = _load_script_module()
    raw_secret = "synthetic_malformed_chain_secret_1234567890"
    transport = _FakeTradierProbeTransport(
        raw_secret=raw_secret,
        chain_payload={"options": {"option": f"not-a-contract {raw_secret}"}},
    )
    monkeypatch.setenv("TRADIER_API_TOKEN", raw_secret)
    monkeypatch.setattr(
        module,
        "_build_tradier_options_live_probe_transport",
        lambda *args, **kwargs: transport,
    )

    payload = module.collect_diagnostic_bundle(
        options_live_probe=True,
        options_provider="tradier",
        options_probe_symbol="TEM",
        options_probe_chain=True,
    )
    live_probe = _providers_by_id(payload)["tradier"]["liveProbe"]
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    assert transport.calls == [
        ("quote", "TEM"),
        ("expirations", "TEM"),
        ("chain", "TEM", "2026-06-19"),
    ]
    assert live_probe["status"] == "failed_sanitized_provider_error"
    assert live_probe["sanitizedErrorCode"] == "options_provider_payload_unmappable"
    assert live_probe["endpointClasses"] == ["quote", "expirations", "chain"]
    assert live_probe["chainContractCount"] == 0
    assert live_probe["chainHasBidAsk"] is False
    assert live_probe["chainHasOpenInterest"] is False
    assert live_probe["chainHasIvGreeks"] is False
    assert live_probe["endpointResults"][-1] == {
        "endpointClass": "chain",
        "status": "error",
        "responseShape": {"status": "unknown", "count": 0},
    }
    for blocked in (raw_secret, "not-a-contract", "token", "secret", "Authorization", "Bearer"):
        assert blocked not in serialized


@pytest.mark.parametrize(
    "error_code",
    ["options_provider_http_error", "options_provider_payload_unmappable"],
)
def test_runtime_diagnostic_options_live_probe_sanitizes_provider_errors(
    monkeypatch,
    error_code: str,
) -> None:
    module = _load_script_module()
    raw_secret = "synthetic_error_probe_secret_1234567890"
    transport = _FailingTradierProbeTransport(error_code, raw_secret)
    monkeypatch.setenv("TRADIER_API_TOKEN", raw_secret)
    monkeypatch.setattr(
        module,
        "_build_tradier_options_live_probe_transport",
        lambda *args, **kwargs: transport,
    )

    payload = module.collect_diagnostic_bundle(
        options_live_probe=True,
        options_provider="tradier",
        options_probe_symbol="TEM",
    )
    live_probe = _providers_by_id(payload)["tradier"]["liveProbe"]
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    assert transport.calls == [("quote", "TEM")]
    assert live_probe["status"] == "failed_sanitized_provider_error"
    assert live_probe["networkCallExecuted"] is True
    assert live_probe["sanitizedErrorCode"] == error_code
    assert live_probe["endpointResults"] == [
        {
            "endpointClass": "quote",
            "status": "error",
            "responseShape": {"status": "unknown", "count": 0},
        }
    ]
    for blocked in (raw_secret, "Authorization", "Bearer", "provider failed", "token", "secret"):
        assert blocked not in serialized


def test_runtime_diagnostic_sanitizes_endpoint_and_provider_output(monkeypatch) -> None:
    module = _load_script_module()

    monkeypatch.setattr(
        module,
        "run_official_macro_live_smoke",
        lambda: {
            "credentialsPresent": True,
            "providerConstructed": True,
            "probePassed": True,
            "freshnessValid": True,
            "sourceMetadataValid": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "fulfilledSeries": ["VIXCLS", "SOFR", "DFF"],
            "missingSeries": [],
            "staleSeries": [],
            "reason": "token=fred-secret",
            "Authorization": "Bearer fred-secret",
            "headers": {"X-Api-Key": "fred-secret"},
        },
    )
    monkeypatch.setattr(
        module,
        "run_rotation_radar_alpaca_live_smoke",
        lambda: {
            "credentialsPresent": True,
            "providerConstructed": True,
            "probePassed": True,
            "freshnessValid": True,
            "sourceMetadataValid": True,
            "sourceAuthorityAllowed": True,
            "scoreContributionAllowed": True,
            "fulfilledWindows": ["5m", "15m", "60m", "1d"],
            "missingWindows": [],
            "staleWindows": [],
            "reason": "header=alpaca-secret",
            "apiKey": "alpaca-secret",
        },
    )
    monkeypatch.setattr(
        module,
        "run_polygon_us_breadth_activation",
        lambda: {
            "credentialsPresent": True,
            "providerConstructed": True,
            "probePassed": False,
            "observationDate": "2026-05-21",
            "freshnessValid": False,
            "coverageCount": 0,
            "sourceMetadataValid": True,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledMetrics": [],
            "missingMetrics": ["ADVANCERS"],
            "reasonCodes": ["api_key=polygon-secret", "polygon_eod_stale"],
            "requestUrl": "https://api.polygon.io/raw?apiKey=polygon-secret",
        },
        raising=False,
    )

    endpoint_payloads = {
        "/api/v1/market-overview/macro": {
            "freshness": "fallback",
            "providerHealth": {"status": "unavailable", "errorSummary": "token=macro-secret"},
            "items": [
                {"symbol": "VIX", "value": None, "isUnavailable": True, "rawHeaders": {"Authorization": "secret"}},
                {"symbol": "SOFR", "value": None, "isUnavailable": True},
            ],
            "headers": {"Cookie": "session=secret"},
        },
        "/api/v1/market/liquidity-monitor": {
            "score": {"regime": "unavailable", "includedIndicatorCount": 0},
            "freshness": {"status": "fallback"},
            "indicators": [
                {
                    "key": "vix_pressure",
                    "includedInScore": False,
                    "evidence": {"isUnavailable": True},
                    "coverageDiagnostics": {"scoreContributionAllowed": False},
                }
            ],
            "rawPayload": "X" * 5000,
        },
        "/api/v1/market/rotation-radar?market=US": {
            "freshness": "fallback",
            "metadata": {
                "quoteProvider": {
                    "present": False,
                    "status": "absent",
                    "asOf": "2026-05-22T10:00:00+08:00",
                    "headers": {"Authorization": "secret"},
                }
            },
            "summary": {
                "headlineEligibleThemeCount": 0,
                "observationThemeCount": 12,
                "noHeadlineReason": "fallback/static",
            },
            "themes": [{"sourceAuthorityAllowed": False, "scoreContributionAllowed": False}],
        },
        "/api/v1/market/temperature": {
            "temperatureAvailable": False,
            "disabledReason": "insufficient_reliable_inputs",
            "providerHealth": {"status": "partial"},
            "headers": {"Authorization": "secret"},
        },
        "/api/v1/market/data-readiness": {
            "readinessStatus": "misconfigured",
            "checks": [
                {"id": "local_us_parquet_dir", "status": "misconfigured"},
                {"id": "tushare_token", "status": "missing", "secretConfigured": False},
            ],
            "path": "/private/path/should/not/appear",
        },
        "/api/v1/market/us-breadth": {
            "source": "yfinance_proxy",
            "sourceType": "unofficial_proxy",
            "freshness": "delayed",
            "breadthClaimType": "representative_sample_breadth",
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "sourceAuthorityReason": "representative_sample_not_full_market_breadth",
            "items": [
                {"symbol": "SECTORS_UP", "value": 6, "source": "yfinance_proxy"},
                {"symbol": "RSP_SPY", "value": -0.4, "source": "yfinance_proxy"},
            ],
            "providerHealth": {"status": "cache"},
        },
    }

    def fake_fetch_json(base_url: str, path: str, timeout_seconds: float):
        assert base_url == "http://127.0.0.1:8000?token=top-secret"
        return 200, endpoint_payloads[path]

    monkeypatch.setattr(module, "_fetch_json", fake_fetch_json)

    payload = module.collect_diagnostic_bundle(
        base_url="http://127.0.0.1:8000?token=top-secret",
        include_live_smoke=True,
    )
    serialized = json.dumps(payload, ensure_ascii=False)

    assert payload["endpointReachability"]["baseUrl"] == "http://127.0.0.1:8000"
    assert payload["runtimeReadiness"]["marketOverviewMacro"]["available"] is False
    assert payload["runtimeReadiness"]["usBreadth"]["available"] is False
    assert payload["runtimeReadiness"]["usBreadth"]["breadthClaimType"] == "representative_sample_breadth"
    assert payload["runtimeReadiness"]["usBreadth"]["sourceAuthorityAllowed"] is False
    assert payload["runtimeReadiness"]["usBreadth"]["scoreContributionAllowed"] is False
    assert payload["runtimeReadiness"]["rotationRadar"]["available"] is False
    assert payload["runtimeReadiness"]["marketTemperature"]["temperatureAvailable"] is False
    assert payload["runtimeReadiness"]["dataReadiness"]["readinessStatus"] == "misconfigured"
    assert payload["polygonUsBreadthDiagnostic"]["reasonCodes"] == ["redacted", "polygon_eod_stale"]
    assert {"code": "diagnostic_pass_runtime_unavailable", "diagnostic": "officialMacroDiagnostic", "runtimeSurface": "marketOverviewMacro"} in payload["discrepancies"]
    assert {"code": "diagnostic_pass_runtime_unavailable", "diagnostic": "alpacaRotationDiagnostic", "runtimeSurface": "rotationRadar"} in payload["discrepancies"]

    for blocked in (
        "top-secret",
        "fred-secret",
        "alpaca-secret",
        "polygon-secret",
        "Authorization",
        "Cookie",
        "X-Api-Key",
        "requestUrl",
        "/private/path/should/not/appear",
        "rawPayload",
        "rawHeaders",
    ):
        assert blocked not in serialized


def test_runtime_diagnostic_keeps_polygon_breadth_probe_failure_fail_closed(monkeypatch) -> None:
    module = _load_script_module()
    monkeypatch.setenv("POLYGON_API_KEY", "polygon-test-key")

    monkeypatch.setattr(
        module,
        "run_official_macro_live_smoke",
        lambda: {
            "credentialsPresent": False,
            "providerConstructed": False,
            "probePassed": False,
            "freshnessValid": False,
            "sourceMetadataValid": False,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledSeries": [],
            "missingSeries": ["VIXCLS"],
            "staleSeries": [],
            "reason": "credentials",
        },
    )
    monkeypatch.setattr(
        module,
        "run_rotation_radar_alpaca_live_smoke",
        lambda: {
            "credentialsPresent": False,
            "providerConstructed": False,
            "probePassed": False,
            "freshnessValid": False,
            "sourceMetadataValid": False,
            "sourceAuthorityAllowed": False,
            "scoreContributionAllowed": False,
            "fulfilledWindows": [],
            "missingWindows": ["5m", "15m", "60m", "1d"],
            "staleWindows": [],
            "reason": "credentials",
        },
    )
    monkeypatch.setattr(
        module,
        "run_polygon_us_breadth_activation",
        lambda: (_ for _ in ()).throw(RuntimeError("polygon api_key=raw-secret")),
    )

    payload = module.collect_diagnostic_bundle(include_live_smoke=True)
    serialized = json.dumps(payload, ensure_ascii=False)

    assert "officialMacroDiagnostic" in payload
    assert "alpacaRotationDiagnostic" in payload
    assert payload["polygonUsBreadthDiagnostic"] == {
        "credentialsPresent": True,
        "probePassed": False,
        "observationDate": None,
        "freshnessValid": False,
        "coverageCount": 0,
        "sourceAuthorityAllowed": False,
        "scoreContributionAllowed": False,
        "fulfilledMetrics": [],
        "missingMetrics": [
            "ADVANCERS",
            "DECLINERS",
            "UNCHANGED",
            "ADVANCE_DECLINE_RATIO",
            "NEW_HIGHS",
            "NEW_LOWS",
            "HIGH_LOW_RATIO",
        ],
        "reasonCodes": ["unexpected_error"],
    }
    assert payload["discrepancies"] == []
    for reason_code in payload["polygonUsBreadthDiagnostic"]["reasonCodes"]:
        lowered = reason_code.lower()
        assert "http://" not in lowered
        assert "https://" not in lowered
        assert "api_key" not in lowered
        assert "apikey" not in lowered
        assert "secret" not in lowered
    assert "raw-secret" not in serialized
    assert "polygon-test-key" not in serialized
    assert "api_key" not in serialized
