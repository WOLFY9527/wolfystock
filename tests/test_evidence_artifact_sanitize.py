from __future__ import annotations

import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from scripts import evidence_artifact_sanitize as sanitizer_script
from scripts.provider_operator_evidence_check import validate_provider_operator_evidence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "evidence_artifact_sanitize.py"
REDACTED = "<redacted>"


def _write_json(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "operator-artifact.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _sanitize(tmp_path: Path, payload: object) -> tuple[subprocess.CompletedProcess[str], Path]:
    source = _write_json(tmp_path, payload)
    output = tmp_path / "sanitized.json"
    result = _run("sanitize", "--input", source, "--output", output)
    return result, output


def _combined(result: subprocess.CompletedProcess[str], output: Path | None = None) -> str:
    text = result.stdout + result.stderr
    if output and output.exists():
        text += output.read_text(encoding="utf-8")
    return text


def _tmp_residue(directory: Path) -> list[Path]:
    return sorted(directory.glob(".*.tmp"))


def test_secret_markers_are_redacted_and_not_emitted(tmp_path: Path) -> None:
    raw_secret = "api_key=operator-secret-value-should-not-leak"

    result, output = _sanitize(tmp_path, {"providerName": "tradier", "notes": raw_secret})

    assert result.returncode == 0
    sanitized = json.loads(output.read_text(encoding="utf-8"))
    assert sanitized["notes"] == REDACTED
    assert raw_secret not in _combined(result, output)
    summary = json.loads(result.stdout)
    assert summary["summary"]["countsByCategory"]["secret_marker"] == 1


def test_raw_request_and_response_body_markers_are_redacted(tmp_path: Path) -> None:
    raw_request = "raw-request-body-value-should-not-leak"
    raw_response = "raw-response-body-value-should-not-leak"

    result, output = _sanitize(
        tmp_path,
        {
            "raw_request_body": {"body": raw_request},
            "response": f"raw response payload {raw_response}",
        },
    )

    assert result.returncode == 0
    sanitized = json.loads(output.read_text(encoding="utf-8"))
    assert sanitized["raw_request_body"]["body"] == REDACTED
    assert sanitized["response"] == REDACTED
    combined = _combined(result, output)
    assert raw_request not in combined
    assert raw_response not in combined
    assert "raw_request_body" not in result.stdout


def test_path_traversal_and_credential_urls_are_redacted(tmp_path: Path) -> None:
    traversal = "../operator-secrets.json"
    credential_url = "https://user:pass@example.invalid/internal"

    result, output = _sanitize(tmp_path, {"fileLabel": traversal, "callback": credential_url})

    assert result.returncode == 0
    sanitized = json.loads(output.read_text(encoding="utf-8"))
    assert sanitized["fileLabel"] == REDACTED
    assert sanitized["callback"] == REDACTED
    combined = _combined(result, output)
    assert traversal not in combined
    assert credential_url not in combined


def test_approval_wording_is_redacted_without_emitting_raw_phrase(tmp_path: Path) -> None:
    wording = "public " + "launch " + "GO" + " for this artifact"

    result, output = _sanitize(tmp_path, {"operatorConclusion": wording})

    assert result.returncode == 0
    assert json.loads(output.read_text(encoding="utf-8"))["operatorConclusion"] == REDACTED
    combined = _combined(result, output).lower()
    assert wording.lower() not in combined
    assert json.loads(result.stdout)["summary"]["countsByCategory"]["approval_wording"] == 1


def test_scan_mode_exits_non_zero_with_fail_on_findings_without_leaks(tmp_path: Path) -> None:
    raw_secret = "Be" "arer scan-secret-value-should-not-leak"
    source = _write_json(tmp_path, {"notes": raw_secret})

    result = _run("scan", "--input", source, "--fail-on-findings")

    assert result.returncode == 1
    assert raw_secret not in _combined(result)
    summary = json.loads(result.stdout)
    assert summary["mode"] == "scan"
    assert summary["summary"]["totalFindings"] == 1


def test_sanitized_output_can_reach_review_state_through_provider_validator(tmp_path: Path) -> None:
    payload = {
        "providerName": "tradier",
        "environment": "staging",
        "operator": "provider-ops",
        "observedAt": "2026-05-08T10:30:00Z",
        "probeMode": "manual_provider_probe",
        "networkCallsEnabled": False,
        "credentialPresence": "redacted",
        "circuitState": {"state": "closed", "summary": "No forced circuit override recorded."},
        "fallbackState": {"state": "unchanged", "summary": "Runtime fallback policy was observed only."},
        "outcome": "needs-review",
        "evidenceRedactionVersion": "provider_operator_redaction_v1",
        "notes": "token=provider-note-value-should-not-leak",
    }

    result, output = _sanitize(tmp_path, payload)

    assert result.returncode == 0
    validator_summary = validate_provider_operator_evidence(json.loads(output.read_text(encoding="utf-8")))
    assert validator_summary["status"] == "pass"
    assert validator_summary["artifact"]["outcome"] == "needs-review"


def test_broker_order_artifact_ids_payloads_urls_and_tokens_are_redacted(tmp_path: Path) -> None:
    broker_account_ref = "fixture-broker-account-ref-must-not-leak"
    account_id = "fixture-account-id-must-not-leak"
    order_id = "fixture-order-id-must-not-leak"
    request_id = "fixture-request-id-must-not-leak"
    account_label = "fixture-private-account-label-must-not-leak"
    broker_url = "https://broker-gateway.example.invalid/v1/accounts/fixture-broker-account-ref-must-not-leak"
    execution_payload = "fixture-execution-payload-must-not-leak"
    broker_token = "fixture-broker-token-must-not-leak"

    result, output = _sanitize(
        tmp_path,
        {
            "brokerAccountRef": broker_account_ref,
            "accountId": account_id,
            "orderId": order_id,
            "requestId": request_id,
            "accountMetadata": {"label": account_label, "tier": "synthetic"},
            "apiBaseUrl": broker_url,
            "executionPayload": {"body": execution_payload},
            "headers": {"token": broker_token},
        },
    )

    assert result.returncode == 0
    sanitized = json.loads(output.read_text(encoding="utf-8"))
    assert sanitized["brokerAccountRef"] == REDACTED
    assert sanitized["accountId"] == REDACTED
    assert sanitized["orderId"] == REDACTED
    assert sanitized["requestId"] == REDACTED
    assert sanitized["accountMetadata"]["label"] == REDACTED
    assert sanitized["accountMetadata"]["tier"] == REDACTED
    assert sanitized["apiBaseUrl"] == REDACTED
    assert sanitized["executionPayload"]["body"] == REDACTED
    assert sanitized["headers"]["token"] == REDACTED

    combined = _combined(result, output)
    for raw_value in (
        broker_account_ref,
        account_id,
        order_id,
        request_id,
        account_label,
        broker_url,
        execution_payload,
        broker_token,
    ):
        assert raw_value not in combined

    stdout = result.stdout
    for raw_field in ("brokerAccountRef", "accountId", "orderId", "requestId", "accountMetadata", "apiBaseUrl", "executionPayload"):
        assert raw_field not in stdout
    summary = json.loads(stdout)
    assert summary["summary"]["countsByCategory"]["broker_order_identity"] == 4
    assert summary["summary"]["countsByCategory"]["account_metadata"] == 1
    assert summary["summary"]["countsByCategory"]["endpoint_url"] == 1
    assert summary["summary"]["countsByCategory"]["raw_body_or_log"] == 1


def test_broker_import_export_alias_fields_are_redacted(tmp_path: Path) -> None:
    result, output = _sanitize(
        tmp_path,
        {
            "brokerApiUrl": "https://broker.example.invalid/api?token=fixture-url-token-must-not-leak",
            "accountNumber": "fixture-account-number-must-not-leak",
            "orderRef": "fixture-order-ref-must-not-leak",
            "permId": "fixture-perm-id-must-not-leak",
        },
    )

    assert result.returncode == 0
    sanitized = json.loads(output.read_text(encoding="utf-8"))
    assert sanitized["brokerApiUrl"] == REDACTED
    assert sanitized["accountNumber"] == REDACTED
    assert sanitized["orderRef"] == REDACTED
    assert sanitized["permId"] == REDACTED

    combined = _combined(result, output)
    for raw_value in (
        "broker.example.invalid",
        "fixture-url-token-must-not-leak",
        "fixture-account-number-must-not-leak",
        "fixture-order-ref-must-not-leak",
        "fixture-perm-id-must-not-leak",
    ):
        assert raw_value not in combined

    stdout = result.stdout
    for raw_field in ("brokerApiUrl", "accountNumber", "orderRef", "permId"):
        assert raw_field not in stdout


def test_broker_import_export_freeform_identifiers_are_redacted(tmp_path: Path) -> None:
    raw_note = (
        "broker account ref=fixture-broker-account-ref-must-not-leak; "
        "order id=fixture-order-id-must-not-leak; "
        "request id=fixture-request-id-must-not-leak; "
        "account label=fixture-account-label-must-not-leak"
    )

    result, output = _sanitize(tmp_path, {"operatorNote": raw_note})

    assert result.returncode == 0
    sanitized = json.loads(output.read_text(encoding="utf-8"))
    assert sanitized["operatorNote"] == REDACTED
    combined = _combined(result, output)
    assert raw_note not in combined
    assert "fixture-broker-account-ref-must-not-leak" not in combined
    assert "fixture-order-id-must-not-leak" not in combined
    assert "fixture-request-id-must-not-leak" not in combined
    assert "fixture-account-label-must-not-leak" not in combined


def test_default_sanitize_writes_deterministic_sibling_and_preserves_source(tmp_path: Path) -> None:
    source = _write_json(tmp_path, {"notes": "token=default-output-secret"})
    source_bytes = source.read_bytes()
    expected_output = tmp_path / "operator-artifact.sanitized.json"

    result = _run("sanitize", "--input", source)

    assert result.returncode == 0, result.stderr
    assert source.read_bytes() == source_bytes
    assert expected_output.exists()
    assert expected_output != source
    assert json.loads(expected_output.read_text(encoding="utf-8"))["notes"] == REDACTED
    report = json.loads(result.stdout)
    assert report["outputLabel"] == expected_output.name
    assert report["sourceArtifactMutated"] is False
    assert not _tmp_residue(tmp_path)


def test_explicit_output_preserves_source_and_existing_schema(tmp_path: Path) -> None:
    source = _write_json(tmp_path, {"operatorConclusion": "needs-review"})
    source_bytes = source.read_bytes()
    output = tmp_path / "explicit.sanitized.json"

    result = _run("sanitize", "--input", source, "--output", output)

    assert result.returncode == 0, result.stderr
    assert source.read_bytes() == source_bytes
    report = json.loads(result.stdout)
    assert report["schemaVersion"] == sanitizer_script.SCHEMA_VERSION
    assert report["mode"] == "sanitize"
    assert report["outputLabel"] == output.name
    assert report["sourceArtifactMutated"] is False
    assert "summary" in report and "findings" in report


def test_output_collision_fails_without_mutating_source_or_destination(tmp_path: Path) -> None:
    source = _write_json(tmp_path, {"notes": "token=collision-secret"})
    output = tmp_path / "operator-artifact.sanitized.json"
    destination_bytes = b'{"existing": true}\n'
    output.write_bytes(destination_bytes)
    source_bytes = source.read_bytes()

    result = _run("sanitize", "--input", source)

    assert result.returncode != 0
    assert "output already exists" in _combined(result)
    assert source.read_bytes() == source_bytes
    assert output.read_bytes() == destination_bytes
    assert not _tmp_residue(tmp_path)


def test_explicit_overwrite_replaces_destination_without_mutating_source(tmp_path: Path) -> None:
    source = _write_json(tmp_path, {"notes": "token=overwrite-secret"})
    output = tmp_path / "explicit.sanitized.json"
    output.write_text('{"existing": true}\n', encoding="utf-8")
    source_bytes = source.read_bytes()

    result = _run("sanitize", "--input", source, "--output", output, "--overwrite")

    assert result.returncode == 0, result.stderr
    assert source.read_bytes() == source_bytes
    assert json.loads(output.read_text(encoding="utf-8"))["notes"] == REDACTED
    assert json.loads(result.stdout)["sourceArtifactMutated"] is False
    assert not _tmp_residue(tmp_path)


def test_output_aliases_are_rejected_outside_explicit_in_place(tmp_path: Path) -> None:
    source = _write_json(tmp_path, {"notes": "token=alias-secret"})
    source_bytes = source.read_bytes()

    same_path = _run("sanitize", "--input", source, "--output", source, "--overwrite")

    assert same_path.returncode != 0
    assert "alias rejected" in _combined(same_path)
    assert source.read_bytes() == source_bytes

    alias = tmp_path / "alias.json"
    try:
        alias.symlink_to(source)
    except OSError:
        pytest.skip("symlinks are not supported in this environment")

    symlink_result = _run("sanitize", "--input", source, "--output", alias, "--overwrite")

    assert symlink_result.returncode != 0
    assert "alias rejected" in _combined(symlink_result)
    assert source.read_bytes() == source_bytes


def test_in_place_is_explicit_and_safely_sanitizes_source(tmp_path: Path) -> None:
    source = _write_json(tmp_path, {"notes": "token=in-place-secret"})

    result = _run("sanitize", "--input", source, "--in-place")

    assert result.returncode == 0, result.stderr
    assert json.loads(source.read_text(encoding="utf-8"))["notes"] == REDACTED
    report = json.loads(result.stdout)
    assert report["sourceArtifactMutated"] is True
    assert report["outputLabel"] == source.name
    assert not _tmp_residue(tmp_path)


def test_in_place_symlink_preserves_alias_and_sanitizes_target(tmp_path: Path) -> None:
    source = _write_json(tmp_path, {"notes": "token=in-place-symlink-secret"})
    alias = tmp_path / "alias.json"
    try:
        alias.symlink_to(source)
    except OSError:
        pytest.skip("symlinks are not supported in this environment")

    result = _run("sanitize", "--input", alias, "--in-place")

    assert result.returncode == 0, result.stderr
    assert alias.is_symlink()
    assert alias.resolve(strict=True) == source
    assert json.loads(source.read_text(encoding="utf-8"))["notes"] == REDACTED
    report = json.loads(result.stdout)
    assert report["sourceArtifactMutated"] is True
    assert report["outputLabel"] == alias.name
    assert not _tmp_residue(tmp_path)


def test_incompatible_in_place_flag_combinations_fail_safely(tmp_path: Path) -> None:
    source = _write_json(tmp_path, {"notes": "token=incompatible-secret"})
    source_bytes = source.read_bytes()
    output = tmp_path / "out.json"

    with_output = _run("sanitize", "--input", source, "--in-place", "--output", output)
    with_overwrite = _run("sanitize", "--input", source, "--in-place", "--overwrite")

    assert with_output.returncode != 0
    assert "--in-place cannot be combined with --output" in _combined(with_output)
    assert with_overwrite.returncode != 0
    assert "--overwrite cannot be combined with --in-place" in _combined(with_overwrite)
    assert source.read_bytes() == source_bytes
    assert not output.exists()
    assert not _tmp_residue(tmp_path)


def test_malformed_input_does_not_touch_default_destination(tmp_path: Path) -> None:
    source = tmp_path / "malformed.json"
    source.write_text('{"notes": ', encoding="utf-8")
    source_bytes = source.read_bytes()
    output = tmp_path / "malformed.sanitized.json"

    result = _run("sanitize", "--input", source)

    assert result.returncode != 0
    assert "input file is not readable JSON" in _combined(result)
    assert source.read_bytes() == source_bytes
    assert not output.exists()
    assert not _tmp_residue(tmp_path)


def test_missing_input_fails_without_creating_default_destination(tmp_path: Path) -> None:
    source = tmp_path / "missing.json"
    output = tmp_path / "missing.sanitized.json"

    result = _run("sanitize", "--input", source)

    assert result.returncode != 0
    assert "input file not found" in _combined(result)
    assert not output.exists()
    assert not _tmp_residue(tmp_path)


def test_default_destination_handles_posix_and_windows_style_filenames() -> None:
    assert sanitizer_script._default_output_path(Path("nested/artifact.json")) == Path("nested/artifact.sanitized.json")
    assert sanitizer_script._default_output_path(Path("artifact")) == Path("artifact.sanitized")
    assert sanitizer_script._default_output_path(Path("C:\\evidence\\artifact.json")) == Path(
        "C:\\evidence\\artifact.sanitized.json"
    )


def test_atomic_failure_before_replace_preserves_destination_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_json(tmp_path, {"notes": "token=atomic-failure-secret"})
    output = tmp_path / "atomic.sanitized.json"
    destination_bytes = b'{"existing": true}\n'
    output.write_bytes(destination_bytes)
    source_bytes = source.read_bytes()

    def fail_replace(_source: object, _target: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(sanitizer_script.os, "replace", fail_replace)

    with pytest.raises(SystemExit) as exc:
        sanitizer_script._sanitize_command(
            Namespace(
                input=str(source),
                output=str(output),
                in_place=False,
                overwrite=True,
                fail_on_findings=False,
            )
        )

    assert exc.value.code.startswith("[FAIL] replacement failed:")
    assert source.read_bytes() == source_bytes
    assert output.read_bytes() == destination_bytes
    assert not _tmp_residue(tmp_path)


def test_in_place_replacement_failure_preserves_source_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_json(tmp_path, {"notes": "token=in-place-failure-secret"})
    source_bytes = source.read_bytes()

    def fail_replace(_source: object, _target: object) -> None:
        raise OSError("simulated in-place replace failure")

    monkeypatch.setattr(sanitizer_script.os, "replace", fail_replace)

    with pytest.raises(SystemExit) as exc:
        sanitizer_script._sanitize_command(
            Namespace(
                input=str(source),
                output=None,
                in_place=True,
                overwrite=False,
                fail_on_findings=False,
            )
        )

    assert exc.value.code.startswith("[FAIL] replacement failed:")
    assert source.read_bytes() == source_bytes
    assert not _tmp_residue(tmp_path)


def test_write_failure_is_distinct_and_leaves_existing_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_json(tmp_path, {"notes": "token=write-failure-secret"})
    output = tmp_path / "write-failure.sanitized.json"
    destination_bytes = b'{"existing": true}\n'
    output.write_bytes(destination_bytes)
    source_bytes = source.read_bytes()

    def fail_named_temporary_file(*_args: object, **_kwargs: object) -> object:
        raise OSError("simulated temp creation failure")

    monkeypatch.setattr(sanitizer_script.tempfile, "NamedTemporaryFile", fail_named_temporary_file)

    with pytest.raises(SystemExit) as exc:
        sanitizer_script._sanitize_command(
            Namespace(
                input=str(source),
                output=str(output),
                in_place=False,
                overwrite=True,
                fail_on_findings=False,
            )
        )

    assert exc.value.code.startswith("[FAIL] write failed:")
    assert source.read_bytes() == source_bytes
    assert output.read_bytes() == destination_bytes
    assert not _tmp_residue(tmp_path)
