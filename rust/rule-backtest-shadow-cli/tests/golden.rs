#[path = "../src/compute.rs"]
mod compute;
#[path = "../src/contract.rs"]
mod contract;

use std::path::PathBuf;
use std::process::Command;

fn fixture_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../tests/fixtures/backtest/rule_backtest_compute_shadow_cli_v1.json")
}

#[test]
fn golden_fixture_matches_python_authoritative_expected_output() {
    let fixture = contract::load_fixture(&fixture_path()).expect("fixture should load");
    let actual = compute::run_fixture(&fixture).expect("fixture should compute");

    compute::compare_against_expected(&actual, &fixture.expected_output)
        .expect("rust shadow output should match python-authoritative expected output");
}

#[test]
fn cli_reports_success_for_supported_fixture() {
    let output = Command::new(env!("CARGO_BIN_EXE_rule-backtest-shadow-cli"))
        .arg(fixture_path())
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
    assert!(stdout.contains("rule_conditions_close_vs_ma3_long_cash"));
}
