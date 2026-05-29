use std::fs;
use std::path::Path;

use serde::Deserialize;

#[derive(Debug, Deserialize, Clone)]
pub struct FixtureEnvelope {
    pub contract_version: String,
    pub case_id: String,
    pub input: FixtureInput,
    pub expected_output: ExpectedOutput,
}

#[derive(Debug, Deserialize, Clone)]
pub struct FixtureInput {
    pub contract_version: String,
    pub case_id: String,
    pub code: String,
    pub initial_capital: f64,
    pub lookback_bars: usize,
    pub date_window: DateWindow,
    pub execution_model: ExecutionModel,
    pub parsed_strategy: ParsedStrategy,
    pub bars: Vec<Bar>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct DateWindow {
    pub start_date: String,
    pub end_date: String,
}

#[derive(Debug, Deserialize, Clone, PartialEq)]
pub struct ExecutionModel {
    pub version: String,
    pub timeframe: String,
    pub signal_evaluation_timing: String,
    pub entry_timing: String,
    pub exit_timing: String,
    pub entry_fill_price_basis: String,
    pub exit_fill_price_basis: String,
    pub position_sizing: String,
    pub fee_model: String,
    pub fee_bps_per_side: f64,
    pub slippage_model: String,
    pub slippage_bps_per_side: f64,
    pub market_rules: MarketRules,
}

#[derive(Debug, Deserialize, Clone, PartialEq)]
pub struct MarketRules {
    pub trading_day_execution: String,
    pub terminal_bar_fill_fallback: String,
    pub window_end_position_handling: String,
}

#[derive(Debug, Deserialize, Clone)]
pub struct ParsedStrategy {
    pub version: String,
    pub timeframe: String,
    pub strategy_kind: String,
    pub entry: ComparisonNode,
    pub exit: ComparisonNode,
    pub max_lookback: usize,
    pub confidence: f64,
    pub needs_confirmation: bool,
    pub ambiguities: Vec<serde_json::Value>,
    pub summary: StrategySummary,
    pub strategy_spec: StrategySpec,
}

#[derive(Debug, Deserialize, Clone)]
pub struct ComparisonNode {
    #[serde(rename = "type")]
    pub node_type: String,
    pub left: Operand,
    pub compare: String,
    pub right: Operand,
    pub text: String,
}

#[derive(Debug, Deserialize, Clone)]
pub struct Operand {
    pub kind: String,
    pub indicator: String,
    pub period: Option<usize>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct StrategySummary {
    pub entry: String,
    pub exit: String,
}

#[derive(Debug, Deserialize, Clone)]
pub struct StrategySpec {
    pub strategy_type: String,
    pub indicator_family: String,
    pub price_basis: String,
    pub signal_window: usize,
}

#[allow(dead_code)]
#[derive(Debug, Deserialize, Clone)]
pub struct Bar {
    pub date: String,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume: f64,
}

#[derive(Debug, Deserialize, Clone, PartialEq)]
pub struct ExpectedOutput {
    pub contract_version: String,
    pub case_id: String,
    pub execution_model: ExecutionModel,
    pub execution_assumptions: ExecutionAssumptions,
    pub metrics: Metrics,
    pub selected_equity_points: Vec<SelectedEquityPoint>,
    pub trades: Vec<ExpectedTrade>,
}

#[derive(Debug, Deserialize, Clone, PartialEq)]
pub struct ExecutionAssumptions {
    pub timeframe: String,
    pub indicator_price_basis: String,
    pub signal_evaluation_timing: String,
    pub entry_fill_timing: String,
    pub exit_fill_timing: String,
    pub default_fill_price_basis: String,
    pub position_sizing: String,
    pub fee_model: String,
    pub fee_bps_per_side: f64,
    pub slippage_model: String,
    pub slippage_bps_per_side: f64,
    pub benchmark_method: String,
    pub benchmark_price_basis: String,
}

#[derive(Debug, Deserialize, Clone, PartialEq)]
pub struct Metrics {
    pub initial_capital: f64,
    pub final_equity: f64,
    pub total_return_pct: f64,
    pub annualized_return_pct: Option<f64>,
    pub sharpe_ratio: Option<f64>,
    pub benchmark_return_pct: f64,
    pub buy_and_hold_return_pct: f64,
    pub excess_return_vs_benchmark_pct: f64,
    pub excess_return_vs_buy_and_hold_pct: f64,
    pub trade_count: usize,
    pub entry_signal_count: usize,
    pub win_count: usize,
    pub loss_count: usize,
    pub win_rate_pct: f64,
    pub avg_trade_return_pct: f64,
    pub max_drawdown_pct: f64,
    pub avg_holding_days: usize,
    pub avg_holding_bars: usize,
    pub avg_holding_calendar_days: usize,
    pub bars_used: usize,
    pub lookback_bars: usize,
    pub period_start: String,
    pub period_end: String,
}

#[derive(Debug, Deserialize, Clone, PartialEq)]
pub struct SelectedEquityPoint {
    pub date: String,
    pub executed_action: Option<String>,
    pub signal_summary: Option<String>,
    pub position_state: String,
    pub exposure_pct: f64,
    pub notes: Option<String>,
    pub total_portfolio_value: f64,
}

#[derive(Debug, Deserialize, Clone, PartialEq)]
pub struct ExpectedTrade {
    pub entry_signal_date: String,
    pub entry_date: String,
    pub exit_signal_date: String,
    pub exit_date: String,
    pub entry_price: f64,
    pub exit_price: f64,
    pub return_pct: f64,
    pub quantity: f64,
    pub fees: f64,
    pub slippage: f64,
    pub entry_reason: String,
    pub exit_reason: String,
    pub signal_reason: String,
    pub notes: String,
}

pub fn load_fixture(path: &Path) -> Result<FixtureEnvelope, String> {
    let payload = fs::read_to_string(path)
        .map_err(|error| format!("failed to read fixture {}: {error}", path.display()))?;
    serde_json::from_str::<FixtureEnvelope>(&payload)
        .map_err(|error| format!("failed to parse fixture {}: {error}", path.display()))
}
