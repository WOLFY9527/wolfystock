# -*- coding: utf-8 -*-
"""Read-only backend surface contract parity snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Sequence

from fastapi.routing import APIRoute


_SCHEMA_VERSION_FIELDS = frozenset({"schemaVersion", "schema_version"})
_OBSERVATION_BOUNDARY_FIELDS = frozenset(
    {
        "noAdviceDisclosure",
        "no_advice_disclosure",
        "observationOnly",
        "observation_only",
        "decisionGrade",
        "decision_grade",
        "consumerActionBoundary",
        "marketActionabilityFrame",
        "options_consumer_scenario_frame",
    }
)
_DEGRADED_STATE_FIELDS = frozenset(
    {
        "dataQuality",
        "data_quality",
        "missingEvidence",
        "missing_evidence",
        "degradedInputs",
        "degraded_inputs",
        "evidenceGaps",
        "evidence_gaps",
        "researchReadiness",
        "research_readiness",
        "options_readiness",
        "options_research_readiness",
        "warning",
        "warnings",
        "limitations",
        "evidenceLimits",
        "quality_summary",
        "commonRiskFlags",
        "risk_warnings",
        "gate_issues",
    }
)
_CONSUMER_ISSUE_FIELDS = frozenset({"consumerIssues", "consumer_issues"})


@dataclass(frozen=True)
class RouteSpec:
    method: str
    path: str
    manual_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class SurfaceSpec:
    key: str
    label: str
    primary_route: RouteSpec
    related_routes: tuple[RouteSpec, ...] = ()
    schema_version_applicable: bool = True
    consumer_safe_issue_labels_status: str = "unknown"
    consumer_issue_fields_required: bool = False
    implementation_status: str = "implemented"
    notes: tuple[str, ...] = ()


@dataclass
class RouteSnapshot:
    method: str
    path: str
    exists: bool
    response_model: str | None
    typed_contract: bool
    auth_requirement: str
    contract_fields: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "path": self.path,
            "exists": self.exists,
            "responseModel": self.response_model,
            "typedContract": self.typed_contract,
        }


class AdminSurfaceContractReadinessService:
    """Build a bounded truth table for backend research surface contracts."""

    _SURFACES: tuple[SurfaceSpec, ...] = (
        SurfaceSpec(
            key="market_decision_cockpit",
            label="Market Decision Cockpit",
            primary_route=RouteSpec(
                method="GET",
                path="/api/v1/market/decision-cockpit",
                manual_fields=(
                    "schemaVersion",
                    "generatedAt",
                    "marketRegimeDecision",
                    "researchQueuePreview",
                    "optionsStructureStatus",
                    "cockpitSummary",
                    "noAdviceDisclosure",
                    "dataQuality",
                ),
            ),
            consumer_safe_issue_labels_status="raw_internal_codes_detected",
            notes=("Current endpoint contract is exposed through an untyped dict payload.",),
        ),
        SurfaceSpec(
            key="daily_intelligence",
            label="Daily Intelligence",
            primary_route=RouteSpec(method="GET", path="/api/v1/market/daily-intelligence"),
            consumer_safe_issue_labels_status="present",
            consumer_issue_fields_required=True,
        ),
        SurfaceSpec(
            key="market_overview",
            label="Market Overview",
            primary_route=RouteSpec(method="GET", path="/api/v1/market/temperature"),
            related_routes=(
                RouteSpec(
                    method="GET",
                    path="/api/v1/market/market-briefing",
                    manual_fields=(
                        "schemaVersion",
                        "source",
                        "updatedAt",
                        "items",
                        "marketSummarySections",
                        "dataQuality",
                        "freshnessStatus",
                        "consumerIssues",
                        "degradedInputs",
                        "noAdviceDisclosure",
                        "observationOnly",
                        "decisionGrade",
                        "isReliable",
                        "confidence",
                        "warning",
                        "temperatureAvailable",
                        "insufficientReliableInputs",
                        "disabledReason",
                        "unavailableReason",
                        "conclusionAllowed",
                    ),
                ),
            ),
            schema_version_applicable=False,
            consumer_safe_issue_labels_status="present",
            consumer_issue_fields_required=True,
            notes=("Readiness tracks the typed temperature plus market-briefing chain only.",),
        ),
        SurfaceSpec(
            key="research_radar",
            label="Research Radar",
            primary_route=RouteSpec(
                method="GET",
                path="/api/v1/research/radar",
                manual_fields=(
                    "schemaVersion",
                    "generatedAt",
                    "researchQueue",
                    "aggregateSummary",
                    "evidenceGaps",
                    "marketContextFit",
                    "noAdviceDisclosure",
                    "dataQuality",
                ),
            ),
            consumer_safe_issue_labels_status="present",
            consumer_issue_fields_required=True,
        ),
        SurfaceSpec(
            key="scanner",
            label="Scanner",
            primary_route=RouteSpec(method="GET", path="/api/v1/scanner/runs/{run_id}/research-overlay"),
            consumer_safe_issue_labels_status="present",
            consumer_issue_fields_required=True,
        ),
        SurfaceSpec(
            key="watchlist",
            label="Watchlist",
            primary_route=RouteSpec(method="GET", path="/api/v1/watchlist/research-overlay"),
            consumer_safe_issue_labels_status="present",
            consumer_issue_fields_required=True,
        ),
        SurfaceSpec(
            key="portfolio_structure_review",
            label="Portfolio Structure Review",
            primary_route=RouteSpec(method="GET", path="/api/v1/portfolio/structure-review"),
            consumer_safe_issue_labels_status="present",
            consumer_issue_fields_required=True,
        ),
        SurfaceSpec(
            key="scenario_lab",
            label="Scenario Lab",
            primary_route=RouteSpec(method="POST", path="/api/v1/market/scenario-lab"),
            consumer_safe_issue_labels_status="present",
        ),
        SurfaceSpec(
            key="stock_structure_decision",
            label="Stock Structure Decision",
            primary_route=RouteSpec(method="GET", path="/api/v1/stocks/{stock_code}/structure-decision"),
            consumer_safe_issue_labels_status="present",
            consumer_issue_fields_required=True,
        ),
        SurfaceSpec(
            key="options_gamma_observation",
            label="Options/Gamma Observation",
            primary_route=RouteSpec(method="POST", path="/api/v1/options/decision/evaluate"),
            related_routes=(
                RouteSpec(method="GET", path="/api/v1/options/underlyings/{symbol}/summary"),
                RouteSpec(method="GET", path="/api/v1/options/underlyings/{symbol}/expirations"),
                RouteSpec(method="GET", path="/api/v1/options/underlyings/{symbol}/chain"),
                RouteSpec(method="POST", path="/api/v1/options/analyze"),
                RouteSpec(method="POST", path="/api/v1/options/scenario"),
                RouteSpec(method="POST", path="/api/v1/options/strategies/compare"),
            ),
            schema_version_applicable=False,
            consumer_safe_issue_labels_status="present",
            implementation_status="fixture_only",
            notes=("Options Lab remains a fixture-backed observation surface with fail-closed provider limits.",),
        ),
    )

    def build_snapshot(self, *, routes: Sequence[object]) -> dict[str, object]:
        api_routes = [route for route in routes if isinstance(route, APIRoute)]
        surfaces = [self._build_surface_snapshot(spec, api_routes) for spec in self._SURFACES]
        status_counts: dict[str, int] = {}
        for item in surfaces:
            status = str(item["status"])
            status_counts[status] = status_counts.get(status, 0) + 1
        return {
            "generatedAt": datetime.now().isoformat(),
            "readOnly": True,
            "noExternalCalls": True,
            "liveEnforcement": False,
            "runtimeBehaviorChanged": False,
            "consumerVisible": False,
            "surfaces": surfaces,
            "summary": {
                "surfaceCount": len(surfaces),
                "statusCounts": status_counts,
            },
            "metadata": {
                "contract": "backend_surface_contract_parity_v1",
                "projection": "route_registry_contract_signals_only",
                "providerCallsAttempted": False,
                "cacheMutation": False,
                "authBehaviorChanged": False,
            },
        }

    def _build_surface_snapshot(self, spec: SurfaceSpec, routes: Sequence[APIRoute]) -> dict[str, object]:
        primary = self._route_snapshot(spec.primary_route, routes)
        related = [self._route_snapshot(route_spec, routes) for route_spec in spec.related_routes]
        route_snapshots = [primary, *related]
        route_status = self._route_status(route_snapshots)
        all_fields = set().union(*(snapshot.contract_fields for snapshot in route_snapshots))

        schema_version_status = (
            "not_applicable"
            if not spec.schema_version_applicable
            else self._field_status(all_fields, _SCHEMA_VERSION_FIELDS)
        )
        observation_boundary_status = self._field_status(all_fields, _OBSERVATION_BOUNDARY_FIELDS)
        degraded_state_shape_status = self._field_status(all_fields, _DEGRADED_STATE_FIELDS)
        consumer_safe_issue_labels_status = spec.consumer_safe_issue_labels_status
        consumer_safe_issue_labels_status = self._consumer_issue_status(
            fields=all_fields,
            default_status=consumer_safe_issue_labels_status,
            required=spec.consumer_issue_fields_required,
        )
        implementation_status = self._implementation_status(spec, primary, related)
        gaps = self._surface_gaps(
            spec=spec,
            primary=primary,
            related=related,
            schema_version_status=schema_version_status,
            observation_boundary_status=observation_boundary_status,
            degraded_state_shape_status=degraded_state_shape_status,
            consumer_safe_issue_labels_status=consumer_safe_issue_labels_status,
            implementation_status=implementation_status,
        )
        status = self._surface_status(
            primary=primary,
            route_status=route_status,
            gaps=gaps,
            implementation_status=implementation_status,
        )
        return {
            "surfaceKey": spec.key,
            "label": spec.label,
            "status": status,
            "routeStatus": route_status,
            "primaryRoute": primary.to_dict(),
            "relatedRoutes": [snapshot.to_dict() for snapshot in related],
            "authRequirement": {"status": "known", "label": primary.auth_requirement},
            "schemaVersionStatus": schema_version_status,
            "observationBoundaryStatus": observation_boundary_status,
            "degradedStateShapeStatus": degraded_state_shape_status,
            "consumerSafeIssueLabelsStatus": consumer_safe_issue_labels_status,
            "implementationStatus": implementation_status,
            "gaps": gaps,
            "notes": list(spec.notes),
        }

    @staticmethod
    def _route_status(route_snapshots: Sequence[RouteSnapshot]) -> str:
        if all(snapshot.exists for snapshot in route_snapshots):
            return "all_present"
        if any(snapshot.exists for snapshot in route_snapshots):
            return "partial"
        return "missing"

    @staticmethod
    def _field_status(fields: Iterable[str], candidates: set[str] | frozenset[str]) -> str:
        if any(field in candidates for field in fields):
            return "present"
        return "missing"

    @staticmethod
    def _consumer_issue_status(*, fields: Iterable[str], default_status: str, required: bool) -> str:
        fields_set = set(fields)
        if default_status == "raw_internal_codes_detected":
            return default_status
        has_consumer_issues = any(field in _CONSUMER_ISSUE_FIELDS for field in fields_set)
        if has_consumer_issues:
            return "present"
        if required:
            return "missing"
        return default_status

    def _route_snapshot(self, spec: RouteSpec, routes: Sequence[APIRoute]) -> RouteSnapshot:
        route = self._find_route(routes, method=spec.method, path=spec.path)
        if route is None:
            return RouteSnapshot(
                method=spec.method,
                path=spec.path,
                exists=False,
                response_model=None,
                typed_contract=False,
                auth_requirement="unknown",
                contract_fields=set(spec.manual_fields),
            )
        typed_contract = hasattr(route.response_model, "model_fields")
        contract_fields = self._contract_fields(route)
        if spec.manual_fields:
            contract_fields.update(spec.manual_fields)
        response_model = getattr(route.response_model, "__name__", None)
        if response_model is None and route.response_model is dict:
            response_model = "dict"
        return RouteSnapshot(
            method=spec.method,
            path=spec.path,
            exists=True,
            response_model=response_model,
            typed_contract=typed_contract,
            auth_requirement=self._auth_requirement(route),
            contract_fields=contract_fields,
        )

    @staticmethod
    def _find_route(routes: Sequence[APIRoute], *, method: str, path: str) -> APIRoute | None:
        for route in routes:
            methods = set(route.methods or set())
            if method in methods and route.path == path:
                return route
        return None

    @staticmethod
    def _contract_fields(route: APIRoute) -> set[str]:
        fields: set[str] = set()
        model = route.response_model
        if not hasattr(model, "model_fields"):
            return fields
        for name, field in model.model_fields.items():
            fields.add(name)
            alias = getattr(field, "alias", None)
            if alias:
                fields.add(str(alias))
        return fields

    @staticmethod
    def _auth_requirement(route: APIRoute) -> str:
        labels: list[str] = []
        for dependency in route.dependant.dependencies:
            call = dependency.call
            name = getattr(call, "__name__", "")
            module = getattr(call, "__module__", "")
            if module == "api.deps" and name == "get_current_user":
                labels.append("authenticated_user")
            elif module == "api.deps" and name == "get_optional_current_user":
                labels.append("optional_user")
            elif module == "api.deps" and name == "dependency":
                labels.append("admin_capability")
        if "admin_capability" in labels:
            return "admin_capability"
        if "authenticated_user" in labels:
            return "authenticated_user"
        if "optional_user" in labels:
            return "optional_user"
        return "public"

    @staticmethod
    def _implementation_status(spec: SurfaceSpec, primary: RouteSnapshot, related: Sequence[RouteSnapshot]) -> str:
        if not primary.exists:
            return "missing"
        if spec.implementation_status == "fixture_only":
            return "fixture_only"
        if not primary.typed_contract:
            return "contract_untyped"
        if any(not route.typed_contract for route in related if route.exists):
            return "mixed_contract_variants"
        return "implemented"

    @staticmethod
    def _surface_gaps(
        *,
        spec: SurfaceSpec,
        primary: RouteSnapshot,
        related: Sequence[RouteSnapshot],
        schema_version_status: str,
        observation_boundary_status: str,
        degraded_state_shape_status: str,
        consumer_safe_issue_labels_status: str,
        implementation_status: str,
    ) -> list[str]:
        gaps: list[str] = []
        if not primary.exists:
            gaps.append("primary_route_missing")
            return gaps
        if primary.auth_requirement == "unknown":
            gaps.append("auth_requirement_unknown")
        if not primary.typed_contract:
            gaps.append("response_model_untyped")
        if any(not route.exists for route in related):
            gaps.append("related_route_missing")
        if any(route.exists and not route.typed_contract for route in related):
            gaps.append("related_route_contract_untyped")
        if spec.schema_version_applicable and schema_version_status != "present":
            gaps.append("schema_version_missing")
        if observation_boundary_status != "present":
            gaps.append("observation_boundary_missing")
        if degraded_state_shape_status != "present":
            gaps.append("degraded_state_shape_missing")
        if consumer_safe_issue_labels_status == "raw_internal_codes_detected":
            gaps.append("consumer_issue_labels_not_safe")
        elif consumer_safe_issue_labels_status == "missing":
            gaps.append("consumer_issue_labels_missing")
        if implementation_status == "fixture_only":
            gaps.append("fixture_only_contract")
        return gaps

    @staticmethod
    def _surface_status(
        *,
        primary: RouteSnapshot,
        route_status: str,
        gaps: Sequence[str],
        implementation_status: str,
    ) -> str:
        if not primary.exists or route_status == "missing":
            return "missing_contract"
        if implementation_status == "fixture_only":
            return "ready_fixture_only"
        if "consumer_issue_labels_not_safe" in gaps:
            return "degraded_contract"
        if "response_model_untyped" in gaps or "related_route_contract_untyped" in gaps:
            return "mixed_contract"
        return "ready"
