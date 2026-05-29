mod compute;
mod contract;

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use compute::{compare_against_expected, run_fixture};
use contract::load_fixture;

fn main() -> ExitCode {
    match run() {
        Ok(message) => {
            println!("{message}");
            ExitCode::SUCCESS
        }
        Err(error) => {
            eprintln!("{error}");
            ExitCode::from(1)
        }
    }
}

fn run() -> Result<String, String> {
    let mut args = env::args().skip(1);
    let fixture_path = args
        .next()
        .map(PathBuf::from)
        .ok_or_else(|| "usage: rule-backtest-shadow-cli <fixture-json-path>".to_string())?;
    if args.next().is_some() {
        return Err("usage: rule-backtest-shadow-cli <fixture-json-path>".to_string());
    }

    let fixture = load_fixture(&fixture_path)?;
    let actual = run_fixture(&fixture)?;
    match compare_against_expected(&actual, &fixture.expected_output) {
        Ok(()) => Ok(format!(
            "shadow fixture matched: case_id={} trades={} final_equity={:.6}",
            fixture.case_id, actual.metrics.trade_count, actual.metrics.final_equity
        )),
        Err(mismatches) => {
            let mut message = format!("shadow fixture mismatch: case_id={}", fixture.case_id);
            for mismatch in mismatches {
                message.push_str("\n- ");
                message.push_str(&mismatch);
            }
            Err(message)
        }
    }
}
