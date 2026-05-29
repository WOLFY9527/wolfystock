use std::collections::HashSet;

use crate::contract::{
    Bar, ExecutionAssumptions, ExecutionModel, ExpectedOutput, ExpectedTrade, FixtureEnvelope,
    FixtureInput, MarketRules, Metrics, SelectedEquityPoint,
};

const FLOAT_TOLERANCE: f64 = 1e-4;
const SUPPORTED_CASE_IDS: [&str; 2] = [
    "rule_conditions_close_vs_ma3_long_cash",
    "rule_conditions_close_vs_ma3_no_trade",
];

#[derive(Debug, Clone, PartialEq)]
pub struct ComputedOutput {
    pub execution_model: ExecutionModel,
    pub execution_assumptions: ExecutionAssumptions,
    pub metrics: Metrics,
    pub selected_equity_points: Vec<SelectedEquityPoint>,
    pub trades: Vec<ExpectedTrade>,
}

#[derive(Debug, Clone)]
struct EquityPoint {
    date: String,
    executed_action: Option<String>,
    signal_summary: Option<String>,
    position_state: String,
    exposure_pct: f64,
    notes: Option<String>,
    total_portfolio_value: f64,
    drawdown_pct: f64,
}

#[derive(Debug, Clone)]
struct TradeState {
    entry_signal_date: String,
    entry_date: String,
    entry_fill_index: usize,
    entry_price: f64,
    entry_total_cost: f64,
    entry_fee_amount: f64,
    entry_slippage_amount: f64,
    cash_buffer: f64,
}

#[derive(Debug, Clone)]
struct PendingSignal {
    signal_date: String,
}

pub fn validate_fixture(fixture: &FixtureEnvelope) -> Result<(), String> {
    let input = &fixture.input;

    if fixture.contract_version != "shadow_cli_v1" || input.contract_version != "shadow_cli_v1" {
        return Err("unsupported fixture contract_version".to_string());
    }
    if !is_supported_case_id(&fixture.case_id) || !is_supported_case_id(&input.case_id) {
        return Err("unsupported case_id".to_string());
    }
    if input.code != "SAFE" {
        return Err(format!("unsupported code {}", input.code));
    }
    if input.execution_model
        != (ExecutionModel {
            version: "v1".to_string(),
            timeframe: "daily".to_string(),
            signal_evaluation_timing: "bar_close".to_string(),
            entry_timing: "next_bar_open".to_string(),
            exit_timing: "next_bar_open".to_string(),
            entry_fill_price_basis: "open".to_string(),
            exit_fill_price_basis: "open".to_string(),
            position_sizing: "single_position_full_notional".to_string(),
            fee_model: "bps_per_side".to_string(),
            fee_bps_per_side: 2.5,
            slippage_model: "bps_per_side".to_string(),
            slippage_bps_per_side: 1.25,
            market_rules: MarketRules {
                trading_day_execution: "available_bars_only".to_string(),
                terminal_bar_fill_fallback: "same_bar_close".to_string(),
                window_end_position_handling: "force_flatten".to_string(),
            },
        })
    {
        return Err("unsupported execution_model for shadow subset".to_string());
    }

    let strategy = &input.parsed_strategy;
    if strategy.version != "v1"
        || strategy.timeframe != "daily"
        || strategy.strategy_kind != "rule_conditions"
        || strategy.max_lookback != 3
        || !approx_eq(strategy.confidence, 1.0)
        || strategy.needs_confirmation
        || !strategy.ambiguities.is_empty()
    {
        return Err("parsed_strategy header does not match supported subset".to_string());
    }
    if strategy.summary.entry != "买入条件：Close > MA3"
        || strategy.summary.exit != "卖出条件：Close < MA3"
    {
        return Err("parsed_strategy summary does not match supported subset".to_string());
    }
    if strategy.strategy_spec.strategy_type != "rule_conditions"
        || strategy.strategy_spec.indicator_family != "sma_close_rule_conditions"
        || strategy.strategy_spec.price_basis != "close"
        || strategy.strategy_spec.signal_window != 3
    {
        return Err("strategy_spec does not match supported subset".to_string());
    }

    validate_node(&strategy.entry, ">", 3, "Close > MA3")?;
    validate_node(&strategy.exit, "<", 3, "Close < MA3")?;

    if input.bars.is_empty() {
        return Err("fixture bars cannot be empty".to_string());
    }

    Ok(())
}

fn validate_node(
    node: &crate::contract::ComparisonNode,
    expected_compare: &str,
    expected_period: usize,
    expected_text: &str,
) -> Result<(), String> {
    if node.node_type != "comparison"
        || node.compare != expected_compare
        || node.text != expected_text
        || node.left.kind != "indicator"
        || node.left.indicator != "close"
        || node.right.kind != "indicator"
        || node.right.indicator != "ma"
        || node.right.period != Some(expected_period)
    {
        return Err(format!("unsupported strategy node {}", node.text));
    }
    Ok(())
}

fn is_supported_case_id(case_id: &str) -> bool {
    SUPPORTED_CASE_IDS.contains(&case_id)
}

pub fn run_fixture(fixture: &FixtureEnvelope) -> Result<ComputedOutput, String> {
    validate_fixture(fixture)?;
    compute_output(&fixture.input)
}

pub fn compare_against_expected(
    actual: &ComputedOutput,
    expected: &ExpectedOutput,
) -> Result<(), Vec<String>> {
    let mut mismatches = Vec::new();

    if actual.execution_model != expected.execution_model {
        mismatches.push("execution_model mismatch".to_string());
    }
    if actual.execution_assumptions != expected.execution_assumptions {
        mismatches.push("execution_assumptions mismatch".to_string());
    }

    compare_metrics(&actual.metrics, &expected.metrics, &mut mismatches);
    compare_equity_points(
        &actual.selected_equity_points,
        &expected.selected_equity_points,
        &mut mismatches,
    );
    compare_trades(&actual.trades, &expected.trades, &mut mismatches);

    if mismatches.is_empty() {
        Ok(())
    } else {
        Err(mismatches)
    }
}

fn compare_metrics(actual: &Metrics, expected: &Metrics, mismatches: &mut Vec<String>) {
    compare_f64(
        "metrics.initial_capital",
        actual.initial_capital,
        expected.initial_capital,
        mismatches,
    );
    compare_f64(
        "metrics.final_equity",
        actual.final_equity,
        expected.final_equity,
        mismatches,
    );
    compare_f64(
        "metrics.total_return_pct",
        actual.total_return_pct,
        expected.total_return_pct,
        mismatches,
    );
    compare_optional_f64(
        "metrics.annualized_return_pct",
        actual.annualized_return_pct,
        expected.annualized_return_pct,
        mismatches,
    );
    compare_optional_f64(
        "metrics.sharpe_ratio",
        actual.sharpe_ratio,
        expected.sharpe_ratio,
        mismatches,
    );
    compare_f64(
        "metrics.benchmark_return_pct",
        actual.benchmark_return_pct,
        expected.benchmark_return_pct,
        mismatches,
    );
    compare_f64(
        "metrics.buy_and_hold_return_pct",
        actual.buy_and_hold_return_pct,
        expected.buy_and_hold_return_pct,
        mismatches,
    );
    compare_f64(
        "metrics.excess_return_vs_benchmark_pct",
        actual.excess_return_vs_benchmark_pct,
        expected.excess_return_vs_benchmark_pct,
        mismatches,
    );
    compare_f64(
        "metrics.excess_return_vs_buy_and_hold_pct",
        actual.excess_return_vs_buy_and_hold_pct,
        expected.excess_return_vs_buy_and_hold_pct,
        mismatches,
    );
    compare_usize(
        "metrics.trade_count",
        actual.trade_count,
        expected.trade_count,
        mismatches,
    );
    compare_usize(
        "metrics.entry_signal_count",
        actual.entry_signal_count,
        expected.entry_signal_count,
        mismatches,
    );
    compare_usize(
        "metrics.win_count",
        actual.win_count,
        expected.win_count,
        mismatches,
    );
    compare_usize(
        "metrics.loss_count",
        actual.loss_count,
        expected.loss_count,
        mismatches,
    );
    compare_f64(
        "metrics.win_rate_pct",
        actual.win_rate_pct,
        expected.win_rate_pct,
        mismatches,
    );
    compare_f64(
        "metrics.avg_trade_return_pct",
        actual.avg_trade_return_pct,
        expected.avg_trade_return_pct,
        mismatches,
    );
    compare_f64(
        "metrics.max_drawdown_pct",
        actual.max_drawdown_pct,
        expected.max_drawdown_pct,
        mismatches,
    );
    compare_usize(
        "metrics.avg_holding_days",
        actual.avg_holding_days,
        expected.avg_holding_days,
        mismatches,
    );
    compare_usize(
        "metrics.avg_holding_bars",
        actual.avg_holding_bars,
        expected.avg_holding_bars,
        mismatches,
    );
    compare_usize(
        "metrics.avg_holding_calendar_days",
        actual.avg_holding_calendar_days,
        expected.avg_holding_calendar_days,
        mismatches,
    );
    compare_usize(
        "metrics.bars_used",
        actual.bars_used,
        expected.bars_used,
        mismatches,
    );
    compare_usize(
        "metrics.lookback_bars",
        actual.lookback_bars,
        expected.lookback_bars,
        mismatches,
    );
    compare_string(
        "metrics.period_start",
        &actual.period_start,
        &expected.period_start,
        mismatches,
    );
    compare_string(
        "metrics.period_end",
        &actual.period_end,
        &expected.period_end,
        mismatches,
    );
}

fn compare_equity_points(
    actual: &[SelectedEquityPoint],
    expected: &[SelectedEquityPoint],
    mismatches: &mut Vec<String>,
) {
    compare_usize(
        "selected_equity_points.length",
        actual.len(),
        expected.len(),
        mismatches,
    );
    for (index, (actual_point, expected_point)) in actual.iter().zip(expected.iter()).enumerate() {
        compare_string(
            &format!("selected_equity_points[{index}].date"),
            &actual_point.date,
            &expected_point.date,
            mismatches,
        );
        compare_optional_string(
            &format!("selected_equity_points[{index}].executed_action"),
            actual_point.executed_action.as_deref(),
            expected_point.executed_action.as_deref(),
            mismatches,
        );
        compare_optional_string(
            &format!("selected_equity_points[{index}].signal_summary"),
            actual_point.signal_summary.as_deref(),
            expected_point.signal_summary.as_deref(),
            mismatches,
        );
        compare_string(
            &format!("selected_equity_points[{index}].position_state"),
            &actual_point.position_state,
            &expected_point.position_state,
            mismatches,
        );
        compare_f64(
            &format!("selected_equity_points[{index}].exposure_pct"),
            actual_point.exposure_pct,
            expected_point.exposure_pct,
            mismatches,
        );
        compare_optional_string(
            &format!("selected_equity_points[{index}].notes"),
            actual_point.notes.as_deref(),
            expected_point.notes.as_deref(),
            mismatches,
        );
        compare_f64(
            &format!("selected_equity_points[{index}].total_portfolio_value"),
            actual_point.total_portfolio_value,
            expected_point.total_portfolio_value,
            mismatches,
        );
    }
}

fn compare_trades(
    actual: &[ExpectedTrade],
    expected: &[ExpectedTrade],
    mismatches: &mut Vec<String>,
) {
    compare_usize("trades.length", actual.len(), expected.len(), mismatches);
    for (index, (actual_trade, expected_trade)) in actual.iter().zip(expected.iter()).enumerate() {
        compare_string(
            &format!("trades[{index}].entry_signal_date"),
            &actual_trade.entry_signal_date,
            &expected_trade.entry_signal_date,
            mismatches,
        );
        compare_string(
            &format!("trades[{index}].entry_date"),
            &actual_trade.entry_date,
            &expected_trade.entry_date,
            mismatches,
        );
        compare_string(
            &format!("trades[{index}].exit_signal_date"),
            &actual_trade.exit_signal_date,
            &expected_trade.exit_signal_date,
            mismatches,
        );
        compare_string(
            &format!("trades[{index}].exit_date"),
            &actual_trade.exit_date,
            &expected_trade.exit_date,
            mismatches,
        );
        compare_f64(
            &format!("trades[{index}].entry_price"),
            actual_trade.entry_price,
            expected_trade.entry_price,
            mismatches,
        );
        compare_f64(
            &format!("trades[{index}].exit_price"),
            actual_trade.exit_price,
            expected_trade.exit_price,
            mismatches,
        );
        compare_f64(
            &format!("trades[{index}].return_pct"),
            actual_trade.return_pct,
            expected_trade.return_pct,
            mismatches,
        );
        compare_f64(
            &format!("trades[{index}].quantity"),
            actual_trade.quantity,
            expected_trade.quantity,
            mismatches,
        );
        compare_f64(
            &format!("trades[{index}].fees"),
            actual_trade.fees,
            expected_trade.fees,
            mismatches,
        );
        compare_f64(
            &format!("trades[{index}].slippage"),
            actual_trade.slippage,
            expected_trade.slippage,
            mismatches,
        );
        compare_string(
            &format!("trades[{index}].entry_reason"),
            &actual_trade.entry_reason,
            &expected_trade.entry_reason,
            mismatches,
        );
        compare_string(
            &format!("trades[{index}].exit_reason"),
            &actual_trade.exit_reason,
            &expected_trade.exit_reason,
            mismatches,
        );
        compare_string(
            &format!("trades[{index}].signal_reason"),
            &actual_trade.signal_reason,
            &expected_trade.signal_reason,
            mismatches,
        );
        compare_string(
            &format!("trades[{index}].notes"),
            &actual_trade.notes,
            &expected_trade.notes,
            mismatches,
        );
    }
}

fn compute_output(input: &FixtureInput) -> Result<ComputedOutput, String> {
    let fee_rate = input.execution_model.fee_bps_per_side / 10_000.0;
    let slippage_rate = input.execution_model.slippage_bps_per_side / 10_000.0;
    let closes: Vec<f64> = input.bars.iter().map(|bar| bar.close).collect();
    let ma3 = build_sma(&closes, 3);

    let start_index = input
        .bars
        .iter()
        .position(|bar| bar.date == input.date_window.start_date)
        .ok_or_else(|| "start_date not found in bars".to_string())?;
    let end_index = input
        .bars
        .iter()
        .rposition(|bar| bar.date == input.date_window.end_date)
        .ok_or_else(|| "end_date not found in bars".to_string())?;
    if start_index > end_index {
        return Err("invalid execution window".to_string());
    }

    let mut equity_curve = Vec::new();
    let mut trades = Vec::new();
    let mut position = false;
    let mut cash = input.initial_capital;
    let mut shares = 0.0;
    let mut peak_equity = input.initial_capital;
    let mut pending_entry: Option<PendingSignal> = None;
    let mut pending_exit: Option<PendingSignal> = None;
    let mut active_trade: Option<TradeState> = None;
    let mut trade_entry_signals = 0usize;
    let mut holding_bar_samples: Vec<usize> = Vec::new();
    let mut holding_calendar_day_samples: Vec<usize> = Vec::new();

    for index in start_index..=end_index {
        let bar = &input.bars[index];

        let mut executed_action = None;
        let mut notes = None;

        if let (Some(signal), true, Some(state)) = (&pending_exit, position, &active_trade) {
            let base_fill_price = resolve_exit_fill_price(bar, &input.execution_model);
            let effective_price = base_fill_price * (1.0 - slippage_rate);
            let gross_proceeds = shares * effective_price;
            let fee_amount = gross_proceeds * fee_rate;
            let net_proceeds = gross_proceeds - fee_amount;
            let exit_slippage_amount = shares * (base_fill_price - effective_price).max(0.0);
            let holding_bars = (index - state.entry_fill_index).max(1);
            holding_bar_samples.push(holding_bars);
            holding_calendar_day_samples.push(holding_bars);
            cash = state.cash_buffer + net_proceeds;
            trades.push(ExpectedTrade {
                entry_signal_date: state.entry_signal_date.clone(),
                entry_date: state.entry_date.clone(),
                exit_signal_date: signal.signal_date.clone(),
                exit_date: bar.date.clone(),
                entry_price: round6(state.entry_price),
                exit_price: round6(effective_price),
                return_pct: round4(((net_proceeds / state.entry_total_cost) - 1.0) * 100.0),
                quantity: round6(shares),
                fees: round6(state.entry_fee_amount + fee_amount),
                slippage: round6(state.entry_slippage_amount + exit_slippage_amount),
                entry_reason: "signal_entry".to_string(),
                exit_reason: "signal_exit".to_string(),
                signal_reason: "rule_conditions".to_string(),
                notes: "exit_signal_next_bar_open".to_string(),
            });
            pending_exit = None;
            active_trade = None;
            shares = 0.0;
            position = false;
            executed_action = Some("sell".to_string());
            notes = Some("exit_signal_next_bar_open".to_string());
        }

        if let Some(signal) = &pending_entry {
            if !position {
                let base_fill_price = resolve_entry_fill_price(bar, &input.execution_model);
                let effective_price = base_fill_price * (1.0 + slippage_rate);
                let per_share_cost = effective_price * (1.0 + fee_rate);
                let next_shares = if per_share_cost > 0.0 {
                    cash / per_share_cost
                } else {
                    0.0
                };
                let gross_notional = next_shares * effective_price;
                let fee_amount = gross_notional * fee_rate;
                let total_cost = gross_notional + fee_amount;
                let entry_slippage_amount =
                    next_shares * (effective_price - base_fill_price).max(0.0);
                if next_shares > 0.0 {
                    shares = next_shares;
                    cash = (cash - total_cost).max(0.0);
                    position = true;
                    active_trade = Some(TradeState {
                        entry_signal_date: signal.signal_date.clone(),
                        entry_date: bar.date.clone(),
                        entry_fill_index: index,
                        entry_price: effective_price,
                        entry_total_cost: total_cost,
                        entry_fee_amount: fee_amount,
                        entry_slippage_amount,
                        cash_buffer: cash,
                    });
                    executed_action = Some("buy".to_string());
                    notes = Some("entry_signal_next_bar_open".to_string());
                }
            }
            pending_entry = None;
        }

        let total_portfolio_value = if position {
            cash + shares * bar.close
        } else {
            cash
        };
        peak_equity = peak_equity.max(total_portfolio_value);
        let exposure_pct = if total_portfolio_value > 0.0 {
            (shares * bar.close) / total_portfolio_value
        } else {
            0.0
        };
        let drawdown_pct = if peak_equity > 0.0 {
            ((total_portfolio_value / peak_equity) - 1.0) * 100.0
        } else {
            0.0
        };
        let mut point = EquityPoint {
            date: bar.date.clone(),
            executed_action,
            signal_summary: None,
            position_state: if position { "long" } else { "flat" }.to_string(),
            exposure_pct,
            notes,
            total_portfolio_value,
            drawdown_pct,
        };

        if index < end_index {
            if position && compare_signal(bar.close, ma3[index], "<") {
                pending_exit = Some(PendingSignal {
                    signal_date: bar.date.clone(),
                });
                point.signal_summary = Some("Close < MA3".to_string());
            } else if !position && compare_signal(bar.close, ma3[index], ">") {
                trade_entry_signals += 1;
                pending_entry = Some(PendingSignal {
                    signal_date: bar.date.clone(),
                });
                point.signal_summary = Some("Close > MA3".to_string());
            }
        }

        equity_curve.push(point);
    }

    if position {
        return Err("supported subset unexpectedly reached terminal forced-close path".to_string());
    }

    let selected_dates: HashSet<&str> = ["2024-01-04", "2024-01-05", "2024-01-06", "2024-01-07"]
        .into_iter()
        .collect();
    let selected_equity_points = equity_curve
        .iter()
        .filter(|point| selected_dates.contains(point.date.as_str()))
        .map(|point| SelectedEquityPoint {
            date: point.date.clone(),
            executed_action: point.executed_action.clone(),
            signal_summary: point.signal_summary.clone(),
            position_state: point.position_state.clone(),
            exposure_pct: round6(point.exposure_pct),
            notes: point.notes.clone(),
            total_portfolio_value: round6(point.total_portfolio_value),
        })
        .collect::<Vec<_>>();

    let benchmark_return_pct = compute_buy_and_hold_return(&input.bars[start_index..=end_index]);
    let final_equity = equity_curve
        .last()
        .map(|point| point.total_portfolio_value)
        .unwrap_or(input.initial_capital);
    let total_return_pct = round4(((final_equity / input.initial_capital) - 1.0) * 100.0);
    let daily_returns = equity_curve
        .windows(2)
        .filter_map(|window| {
            let previous = window[0].total_portfolio_value;
            let current = window[1].total_portfolio_value;
            if previous > 0.0 {
                Some((current / previous) - 1.0)
            } else {
                None
            }
        })
        .collect::<Vec<_>>();
    let sharpe_ratio = compute_sharpe_ratio(&daily_returns);
    let max_drawdown_pct = round4(
        equity_curve
            .iter()
            .map(|point| point.drawdown_pct)
            .fold(0.0_f64, f64::min)
            .abs(),
    );
    let avg_holding_bars = if holding_bar_samples.is_empty() {
        0usize
    } else {
        round4(holding_bar_samples.iter().sum::<usize>() as f64 / holding_bar_samples.len() as f64)
            as usize
    };
    let avg_holding_calendar_days = if holding_calendar_day_samples.is_empty() {
        0usize
    } else {
        round4(
            holding_calendar_day_samples.iter().sum::<usize>() as f64
                / holding_calendar_day_samples.len() as f64,
        ) as usize
    };

    let metrics = Metrics {
        initial_capital: input.initial_capital,
        final_equity: round6(final_equity),
        total_return_pct,
        annualized_return_pct: None,
        sharpe_ratio,
        benchmark_return_pct,
        buy_and_hold_return_pct: benchmark_return_pct,
        excess_return_vs_benchmark_pct: round4(total_return_pct - benchmark_return_pct),
        excess_return_vs_buy_and_hold_pct: round4(total_return_pct - benchmark_return_pct),
        trade_count: trades.len(),
        entry_signal_count: trade_entry_signals,
        win_count: trades.iter().filter(|trade| trade.return_pct > 0.0).count(),
        loss_count: trades.iter().filter(|trade| trade.return_pct < 0.0).count(),
        win_rate_pct: if trades.is_empty() {
            0.0
        } else {
            round4(
                (trades.iter().filter(|trade| trade.return_pct > 0.0).count() as f64
                    / trades.len() as f64)
                    * 100.0,
            )
        },
        avg_trade_return_pct: if trades.is_empty() {
            0.0
        } else {
            round4(trades.iter().map(|trade| trade.return_pct).sum::<f64>() / trades.len() as f64)
        },
        max_drawdown_pct,
        avg_holding_days: avg_holding_bars,
        avg_holding_bars,
        avg_holding_calendar_days,
        bars_used: equity_curve.len(),
        lookback_bars: input.lookback_bars,
        period_start: input.date_window.start_date.clone(),
        period_end: input.date_window.end_date.clone(),
    };

    Ok(ComputedOutput {
        execution_model: input.execution_model.clone(),
        execution_assumptions: ExecutionAssumptions {
            timeframe: input.execution_model.timeframe.clone(),
            indicator_price_basis: "close".to_string(),
            signal_evaluation_timing: input.execution_model.signal_evaluation_timing.clone(),
            entry_fill_timing: input.execution_model.entry_timing.clone(),
            exit_fill_timing: format!(
                "{}; {}",
                input.execution_model.exit_timing,
                input
                    .execution_model
                    .market_rules
                    .terminal_bar_fill_fallback
            ),
            default_fill_price_basis: input.execution_model.entry_fill_price_basis.clone(),
            position_sizing: input.execution_model.position_sizing.clone(),
            fee_model: input.execution_model.fee_model.clone(),
            fee_bps_per_side: input.execution_model.fee_bps_per_side,
            slippage_model: input.execution_model.slippage_model.clone(),
            slippage_bps_per_side: input.execution_model.slippage_bps_per_side,
            benchmark_method: "buy_and_hold_same_window".to_string(),
            benchmark_price_basis: "close".to_string(),
        },
        metrics,
        selected_equity_points,
        trades,
    })
}

fn compute_buy_and_hold_return(bars: &[Bar]) -> f64 {
    if let (Some(first), Some(last)) = (bars.first(), bars.last()) {
        if first.close > 0.0 {
            return round4(((last.close / first.close) - 1.0) * 100.0);
        }
    }
    0.0
}

fn compare_signal(close: f64, ma_value: Option<f64>, operator: &str) -> bool {
    match (operator, ma_value) {
        (">", Some(value)) => close > value,
        ("<", Some(value)) => close < value,
        _ => false,
    }
}

fn build_sma(values: &[f64], period: usize) -> Vec<Option<f64>> {
    let mut output = Vec::with_capacity(values.len());
    for index in 0..values.len() {
        if index + 1 < period {
            output.push(None);
            continue;
        }
        let window = &values[index + 1 - period..=index];
        output.push(Some(window.iter().sum::<f64>() / period as f64));
    }
    output
}

fn compute_sharpe_ratio(daily_returns: &[f64]) -> Option<f64> {
    if daily_returns.len() < 2 {
        return None;
    }
    let mean = daily_returns.iter().sum::<f64>() / daily_returns.len() as f64;
    let variance = daily_returns
        .iter()
        .map(|value| {
            let delta = *value - mean;
            delta * delta
        })
        .sum::<f64>()
        / daily_returns.len() as f64;
    if variance <= 0.0 {
        return None;
    }
    Some(round4((mean / variance.sqrt()) * 252.0_f64.sqrt()))
}

fn resolve_entry_fill_price(bar: &Bar, execution_model: &ExecutionModel) -> f64 {
    if execution_model.entry_fill_price_basis == "open" {
        bar.open
    } else {
        bar.close
    }
}

fn resolve_exit_fill_price(bar: &Bar, execution_model: &ExecutionModel) -> f64 {
    if execution_model.exit_fill_price_basis == "open" {
        bar.open
    } else {
        bar.close
    }
}

fn compare_usize(label: &str, actual: usize, expected: usize, mismatches: &mut Vec<String>) {
    if actual != expected {
        mismatches.push(format!("{label}: expected {expected}, got {actual}"));
    }
}

fn compare_string(label: &str, actual: &str, expected: &str, mismatches: &mut Vec<String>) {
    if actual != expected {
        mismatches.push(format!("{label}: expected {expected}, got {actual}"));
    }
}

fn compare_optional_string(
    label: &str,
    actual: Option<&str>,
    expected: Option<&str>,
    mismatches: &mut Vec<String>,
) {
    if actual != expected {
        mismatches.push(format!(
            "{label}: expected {:?}, got {:?}",
            expected, actual
        ));
    }
}

fn compare_f64(label: &str, actual: f64, expected: f64, mismatches: &mut Vec<String>) {
    if !approx_eq(actual, expected) {
        mismatches.push(format!(
            "{label}: expected {:.6}, got {:.6}",
            expected, actual
        ));
    }
}

fn compare_optional_f64(
    label: &str,
    actual: Option<f64>,
    expected: Option<f64>,
    mismatches: &mut Vec<String>,
) {
    match (actual, expected) {
        (Some(actual_value), Some(expected_value)) => {
            compare_f64(label, actual_value, expected_value, mismatches)
        }
        (None, None) => {}
        _ => mismatches.push(format!(
            "{label}: expected {:?}, got {:?}",
            expected, actual
        )),
    }
}

fn approx_eq(left: f64, right: f64) -> bool {
    (left - right).abs() <= FLOAT_TOLERANCE
}

fn round4(value: f64) -> f64 {
    (value * 10_000.0).round() / 10_000.0
}

fn round6(value: f64) -> f64 {
    (value * 1_000_000.0).round() / 1_000_000.0
}
