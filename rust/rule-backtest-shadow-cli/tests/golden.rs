#[path = "../src/compute.rs"]
mod compute;
#[path = "../src/contract.rs"]
mod contract;

use std::path::PathBuf;
use std::process::Command;

fn fixture_path(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join(format!("../../tests/fixtures/backtest/{name}"))
}

#[test]
fn golden_fixtures_match_python_authoritative_expected_output() {
    for fixture_name in [
        "rule_backtest_compute_shadow_cli_v1.json",
        "rule_backtest_compute_shadow_cli_v2.json",
    ] {
        let fixture = contract::load_fixture(&fixture_path(fixture_name)).expect("fixture should load");
        let actual = compute::run_fixture(&fixture).expect("fixture should compute");

        compute::compare_against_expected(&actual, &fixture.expected_output)
            .expect("rust shadow output should match python-authoritative expected output");
    }
}

#[test]
fn cli_reports_success_for_supported_fixtures() {
    for (fixture_name, case_id) in [
        (
            "rule_backtest_compute_shadow_cli_v1.json",
            "rule_conditions_close_vs_ma3_long_cash",
        ),
        (
            "rule_backtest_compute_shadow_cli_v2.json",
            "rule_conditions_close_vs_ma3_no_trade",
        ),
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_rule-backtest-shadow-cli"))
            .arg(fixture_path(fixture_name))
            .output()
            .expect("cli should run");

        assert!(
            output.status.success(),
            "stdout: {}\nstderr: {}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );

        let stdout = String::from_utf8_lossy(&output.stdout);
        assert!(stdout.contains("shadow fixture matched"));
        assert!(stdout.contains(case_id));
    }
}

#[test]
fn unsupported_fixture_case_id_fails_closed() {
    let mut fixture =
        contract::load_fixture(&fixture_path("rule_backtest_compute_shadow_cli_v1.json"))
            .expect("fixture should load");
    fixture.case_id = "unsupported_case".to_string();
    fixture.input.case_id = "unsupported_case".to_string();

    let error = compute::run_fixture(&fixture).expect_err("unsupported case should fail closed");
    assert_eq!(error, "unsupported case_id");
}
