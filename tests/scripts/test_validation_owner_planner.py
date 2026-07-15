from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import subprocess

import pytest

from scripts import validation_changed_files as planner


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "validation" / "validation_owners.json"
DUMMY_SHA = "1" * 40


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def write(repo: Path, path: str, content: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def init_repo(repo: Path) -> str:
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "validation@example.invalid")
    git(repo, "config", "user.name", "Validation Test")
    git(repo, "config", "core.autocrlf", "false")
    write(repo, "README.md", "base\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    return git(repo, "rev-parse", "HEAD")


def load_manifest() -> tuple[dict, str]:
    return planner.load_owner_manifest(MANIFEST_PATH, root=ROOT)


def changed(path: str, change_type: str = "modified") -> dict:
    return {
        "path": path,
        "changeTypes": [change_type],
        "sources": ["committed"],
        "ownershipTrees": ["base_and_candidate"],
        "observations": [
            {
                "path": path,
                "source": "committed",
                "status": "M",
                "changeType": change_type,
                "ownershipTree": "base_and_candidate",
            }
        ],
    }


def plan_for(paths: list[str], *, manifest: dict | None = None) -> dict:
    loaded, manifest_hash = load_manifest()
    selected_manifest = manifest or loaded
    return planner.build_shadow_plan_from_changes(
        [changed(path) for path in paths],
        selected_manifest,
        root=ROOT,
        base_ref="base",
        base_sha=DUMMY_SHA,
        candidate_ref="candidate",
        candidate_sha="2" * 40,
        change_source="committed",
        manifest_hash=manifest_hash,
    )


def change_by_path(plan: dict, path: str) -> dict:
    return next(change for change in plan["changes"] if change["path"] == path)


def test_clean_base_and_branch_ahead_commit_are_collected(tmp_path: Path) -> None:
    base_sha = init_repo(tmp_path)
    clean_observations, _, _ = planner.collect_shadow_observations(base_sha, "HEAD", root=tmp_path)
    assert clean_observations == []

    write(tmp_path, "scripts/tool.py", "print('shadow')\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "branch ahead")

    observations, resolved_base, candidate_sha = planner.collect_shadow_observations(
        base_sha,
        "HEAD",
        root=tmp_path,
    )
    changes = planner.aggregate_observations(observations)

    assert resolved_base == base_sha
    assert candidate_sha == git(tmp_path, "rev-parse", "HEAD")
    assert [change["path"] for change in changes] == ["scripts/tool.py"]
    assert changes[0]["sources"] == ["committed"]
    assert changes[0]["changeTypes"] == ["added"]


def test_branch_staged_unstaged_and_untracked_are_a_lossless_union(tmp_path: Path) -> None:
    write(tmp_path, "src/core.py", "VALUE = 1\n")
    write(tmp_path, "docs/guide.md", "base\n")
    base_sha = init_repo(tmp_path)

    write(tmp_path, "bot/committed.py", "COMMITTED = True\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "branch ahead")
    write(tmp_path, "api/staged.py", "STAGED = True\n")
    git(tmp_path, "add", "api/staged.py")
    write(tmp_path, "docs/guide.md", "unstaged\n")
    write(tmp_path, "mystery/untracked.bin", "untracked\n")

    observations, _, _ = planner.collect_shadow_observations(base_sha, "HEAD", root=tmp_path)
    changes = {change["path"]: change for change in planner.aggregate_observations(observations)}

    assert set(changes) == {
        "api/staged.py",
        "bot/committed.py",
        "docs/guide.md",
        "mystery/untracked.bin",
    }
    assert changes["bot/committed.py"]["sources"] == ["committed"]
    assert changes["api/staged.py"]["sources"] == ["staged"]
    assert changes["docs/guide.md"]["sources"] == ["unstaged"]
    assert changes["mystery/untracked.bin"]["sources"] == ["untracked"]


def test_rename_deletion_and_copy_include_source_and_destination_ownership(tmp_path: Path) -> None:
    write(tmp_path, "src/old_name.py", "RENAMED = 'unique'\n")
    write(tmp_path, "api/deleted.py", "DELETED = True\n")
    write(tmp_path, "src/copy_source.py", "COPIED = 'different unique content'\n")
    base_sha = init_repo(tmp_path)

    git(tmp_path, "mv", "src/old_name.py", "src/new_name.py")
    git(tmp_path, "rm", "-q", "api/deleted.py")
    write(tmp_path, "src/copy_destination.py", (tmp_path / "src/copy_source.py").read_text(encoding="utf-8"))
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "rename delete copy")

    observations, _, _ = planner.collect_shadow_observations(
        base_sha,
        "HEAD",
        root=tmp_path,
        change_source="committed",
    )
    changes = {change["path"]: change for change in planner.aggregate_observations(observations)}

    assert "rename_source" in changes["src/old_name.py"]["changeTypes"]
    assert changes["src/old_name.py"]["ownershipTrees"] == ["base"]
    assert "rename_destination" in changes["src/new_name.py"]["changeTypes"]
    assert "deleted" in changes["api/deleted.py"]["changeTypes"]
    assert changes["api/deleted.py"]["ownershipTrees"] == ["base"]
    assert "copy_source" in changes["src/copy_source.py"]["changeTypes"]
    assert "copy_destination" in changes["src/copy_destination.py"]["changeTypes"]


def test_overlapping_rules_union_all_owners_and_tiers() -> None:
    path = "src/services/market_scanner_service.py"

    plan = plan_for([path])
    item = change_by_path(plan, path)

    assert {"backend-python", "protected-scanner"}.issubset(item["matchedRules"])
    assert "direct.python.syntax" in item["ownerIds"]
    assert "complete.backend.non_network" in item["ownerIds"]
    assert "complete.scanner.contracts" in item["ownerIds"]
    assert "protected.baseline.compare" in item["ownerIds"]
    assert {"direct_owner", "bounded_integration", "complete_domain", "milestone", "release"}.issubset(
        item["selectedTiers"]
    )


def test_large_owner_union_is_retained_and_escalates_instead_of_truncating() -> None:
    manifest, _ = load_manifest()
    expanded = deepcopy(manifest)
    synthetic_owner_ids = []
    for index in range(30):
        owner_id = f"direct.synthetic.{index:02d}"
        synthetic_owner_ids.append(owner_id)
        expanded["owners"][owner_id] = {
            "tier": "direct_owner",
            "kind": "owner_identifier",
            "identifier": owner_id,
        }
    expanded["rules"].append(
        {
            "id": "synthetic-large-owner-union",
            "include": ["src/large_union.py"],
            "owners": {"direct_owner": synthetic_owner_ids},
        }
    )

    plan = plan_for(["src/large_union.py"], manifest=expanded)
    selected_owner_ids = {owner["id"] for owner in plan["owners"]}

    assert set(synthetic_owner_ids).issubset(selected_owner_ids)
    assert plan["ownerListsTruncated"] is False
    assert any(escalation["tier"] == "direct_owner" for escalation in plan["escalations"])
    assert "bounded.repository.integration" in selected_owner_ids
    assert "complete.repository.validation" in selected_owner_ids


def test_unknown_path_has_explicit_fail_closed_escalation() -> None:
    path = "unknown-zone/new-validation-input.xyz"

    plan = plan_for([path])
    item = change_by_path(plan, path)

    assert item["matchedRules"] == []
    assert item["authoritySource"] == "explicit_unknown_escalation"
    assert item["escalationReasons"] == ["unknown_validation_relevant_path"]
    assert path in plan["unknownPaths"]
    assert {"protected_baseline_comparison", "milestone", "release"}.issubset(item["selectedTiers"])


@pytest.mark.parametrize(
    ("path", "rule_id"),
    [
        ("data_provider/base.py", "protected-provider"),
        ("src/services/watchlist_service.py", "protected-existing-gate-domain-baseline"),
        ("src/core/scanner_profile.py", "protected-scanner"),
        ("src/core/backtest_engine.py", "protected-backtest"),
        ("src/services/portfolio_service.py", "protected-portfolio"),
        ("src/auth.py", "protected-auth-security"),
        ("src/services/portfolio_ibkr_sync_service.py", "protected-broker-order"),
        ("bot/feishu.py", "protected-external-network"),
        ("validation/validation_owners.json", "protected-owner-manifest"),
    ],
)
def test_every_agents_protected_domain_escalates(path: str, rule_id: str) -> None:
    plan = plan_for([path])
    item = change_by_path(plan, path)

    assert rule_id in item["matchedRules"]
    assert path in plan["protectedPaths"]
    assert {"protected_baseline_comparison", "milestone", "release"}.issubset(item["selectedTiers"])


@pytest.mark.parametrize(
    ("path", "rule_id"),
    [
        ("setup.cfg", "protected-root-config-lockfile"),
        ("apps/dsa-web/package-lock.json", "protected-root-config-lockfile"),
        ("api/v1/schemas/common.py", "protected-schema-contract"),
        (".github/workflows/ci.yml", "protected-workflow"),
        ("src/postgres_schema_bootstrap.py", "protected-database-migration"),
        ("apps/dsa-web/src/setupTests.ts", "protected-global-setup"),
    ],
)
def test_root_config_lock_schema_workflow_migration_and_global_setup_escalate(path: str, rule_id: str) -> None:
    plan = plan_for([path])
    item = change_by_path(plan, path)

    assert rule_id in item["matchedRules"]
    assert {"protected_baseline_comparison", "milestone", "release"}.issubset(item["selectedTiers"])


def test_related_test_inference_adds_but_does_not_replace_manifest_authority() -> None:
    path = "src/providers/validation.py"

    plan = plan_for([path])
    item = change_by_path(plan, path)

    assert item["authoritySource"] == "manifest_rule"
    assert item["matchedRules"]
    assert item["inferredOwners"] == ["direct.pytest.related_inference"]
    assert "tests/test_provider_validation.py" in item["inferredOwnerTargets"]


def test_deterministic_ordering_and_stable_output_hash() -> None:
    manifest, manifest_hash = load_manifest()
    changes = [changed("docs/DOCS_INDEX.md"), changed("src/providers/validation.py")]
    kwargs = {
        "root": ROOT,
        "base_ref": "base",
        "base_sha": DUMMY_SHA,
        "candidate_ref": "candidate",
        "candidate_sha": "2" * 40,
        "change_source": "committed",
        "manifest_hash": manifest_hash,
    }

    first = planner.build_shadow_plan_from_changes(changes, manifest, **kwargs)
    second = planner.build_shadow_plan_from_changes(list(reversed(changes)), manifest, **kwargs)

    assert first == second
    assert first["changedPaths"] == sorted(first["changedPaths"])
    assert first["planHash"] == planner.stable_hash(
        {key: value for key, value in first.items() if key != "planHash"}
    )


def test_t437_t438_locale_corpus_adds_bounded_and_browser_owners_to_current_classification() -> None:
    locale_paths = [
        "apps/dsa-web/e2e/locale-route-switch.spec.ts",
        "apps/dsa-web/src/App.tsx",
        "apps/dsa-web/src/__tests__/AppLocaleRouting.test.tsx",
        "apps/dsa-web/src/contexts/UiLanguageContext.tsx",
        "apps/dsa-web/src/contexts/__tests__/UiLanguageContext.test.tsx",
        "apps/dsa-web/src/i18n/__tests__/bootstrap.test.ts",
        "apps/dsa-web/src/i18n/catalogs/en.ts",
        "apps/dsa-web/src/i18n/catalogs/zh.ts",
        "apps/dsa-web/src/i18n/core.ts",
        "apps/dsa-web/src/main.tsx",
    ]

    current = planner.classify(locale_paths, root=ROOT)
    shadow = plan_for(locale_paths)
    owner_ids = {owner["id"] for owner in shadow["owners"]}

    assert current["tier"] == "frontend-component"
    assert current["hasProtectedDomain"] is False
    assert "bounded.web.locale" in owner_ids
    assert "browser.locale.route" in owner_ids
    assert "browser.changed.specs" in owner_ids
    assert shadow["unknownPaths"] == []
    assert shadow["ownerListsTruncated"] is False
