# Backtest System

## 服务归属

- 标准历史分析评估接口由 `src/services/backtest_service.py` 负责：
  - `POST /api/v1/backtest/run`
  - `POST /api/v1/backtest/prepare-samples`
  - `GET /api/v1/backtest/results`
  - `GET /api/v1/backtest/sample-status`
  - `GET /api/v1/backtest/runs`
  - `GET /api/v1/backtest/performance`
  - `GET /api/v1/backtest/performance/{code}`
  - `POST /api/v1/backtest/samples/clear`
  - `POST /api/v1/backtest/results/clear`
- 规则回测接口由 `src/services/rule_backtest_service.py` 负责：
  - `POST /api/v1/backtest/rule/parse`
  - `POST /api/v1/backtest/rule/run`
  - `POST /api/v1/backtest/rule/compare`
  - `GET /api/v1/backtest/rule/runs`
  - `GET /api/v1/backtest/rule/runs/{run_id}`
  - `GET /api/v1/backtest/rule/runs/{run_id}/status`
  - `GET /api/v1/backtest/rule/runs/{run_id}/support-bundle-manifest`
  - `GET /api/v1/backtest/rule/runs/{run_id}/support-bundle-reproducibility-manifest`
  - `GET /api/v1/backtest/rule/runs/{run_id}/export-index`
  - `GET /api/v1/backtest/rule/runs/{run_id}/execution-trace.json`
  - `GET /api/v1/backtest/rule/runs/{run_id}/execution-trace.csv`
  - `POST /api/v1/backtest/rule/runs/{run_id}/cancel`
  - `POST /api/v1/backtest/rule/universe-jobs`
  - `POST /api/v1/backtest/rule/universe-jobs/{job_id}/run`
  - `GET /api/v1/backtest/rule/universe-jobs/{job_id}/status`
  - `GET /api/v1/backtest/rule/universe-jobs/{job_id}/diagnostics`
  - `GET /api/v1/backtest/rule/universe-jobs/{job_id}/results`

## 异步 / 后台任务

- 规则回测 detail / status / history 以及 universe job status / diagnostics 现在会附带 additive `professionalReadiness` 诊断，用于明确当前系统“可做研究原型，不可宣称 professional quant ready”。
- 当前默认结论固定为 `overall_state=research_prototype`、`professional_quant_ready=false`。
- 这些 readiness 字段是 advisory-only：不改变单标的计算、成交假设、费用/滑点计算、基准计算、已存结果语义或 universe 执行顺序，也不新增 live provider 调用。

- `POST /api/v1/backtest/rule/run` 默认异步提交，立即返回 `queued / parsing / running / summarizing / completed / failed / cancelled` 之一。
- 若传入 `wait_for_completion=true`，接口会同步执行并直接返回完整结果。
- `GET /api/v1/backtest/rule/runs/{run_id}/status` 提供轻量状态轮询，不必每次拉取完整详情。
- `GET /api/v1/backtest/rule/runs/{run_id}/support-bundle-manifest` 提供单条规则回测的紧凑 stored-first support bundle manifest。它复用既有 detail 读回结果中的 `run_timing`、`run_diagnostics`、`artifact_availability`、`readback_integrity` 与归一化 `result_authority.domains`，并只额外附带轻量 `artifact_counts`，用于 backend handoff、AI 调试和自动化脚本读取；默认不会把 `trades`、`equity_curve`、`audit_rows` 或完整 `execution_trace` 这类 heavy payload 直接塞进 manifest。
- `GET /api/v1/backtest/rule/runs/{run_id}/support-bundle-reproducibility-manifest` 提供与 support bundle manifest 同一条运行的紧凑 reproducibility manifest，复用相同的 `run_timing`、`run_diagnostics`、`artifact_availability`、`readback_integrity`，并补充 `execution_assumptions_fingerprint` 与压缩后的 `result_authority.domains.execution_trace` 摘要，便于 migration / replay / reproducibility 检查。
- `GET /api/v1/backtest/rule/runs/{run_id}/export-index` 提供单条规则回测当前可发现的导出项索引，当前稳定集合是：`support_bundle_manifest_json`、`support_bundle_reproducibility_manifest_json`、`execution_trace_json`、`execution_trace_csv`。两个 manifest 都会给出可直接读取的 API path；execution-trace JSON/CSV 现在也都暴露真实的 API path，而不再只是 service-file-only 提示。trace 可用性按当前 detail 读回后的 `execution_trace.rows` 是否非空判断，因此当历史运行缺少可导出的 trace rows 时，index 会稳定返回 `available=false` 与 `execution_trace_rows_missing`。
- `GET /api/v1/backtest/rule/runs/{run_id}/execution-trace.json` 与 `GET /api/v1/backtest/rule/runs/{run_id}/execution-trace.csv` 构成 support bundle 的 heavy trace 导出面：前者返回 AI / automation 更友好的结构化 trace payload，后者返回 operator / spreadsheet 更友好的 CSV 载荷。两者都与 export index 共用同一套 stored-first trace 可用性判断，在 trace rows 缺失时返回 `409 export_unavailable`，而不是伪造空导出。
- `POST /api/v1/backtest/rule/runs/{run_id}/cancel` 提供 best-effort cancel：对尚未完成的任务会标记为 `cancelled`；若任务已结束，则返回当前最终状态而不覆盖结果。
- `POST /api/v1/backtest/rule/universe-jobs` 创建 stored local-only universe job scaffold。创建阶段仅做本地日线数据预检：按规范化代码去重并排序、持久化 `sequence_index`、记录 compact per-symbol readiness row，并默认限制最多 500 个标的。缺少本地数据的标的会标记为 `skipped / blocked_missing_local_data`。创建接口不会执行单标的规则回测、不会调用 provider 拉取、不会写入 heavy run detail、不会启用 worker concurrency，也不会把 DuckDB 作为运行时真源。
- `POST /api/v1/backtest/rule/universe-jobs/{job_id}/run` 对已创建的 local-only universe job 做同步顺序执行。该路径只读取本地 `StockDaily` 行情，不调用 `_ensure_market_history`、provider fallback 或 DuckDB；标的按已持久化 `sequence_index` 顺序逐个运行既有规则回测引擎，单标的异常会写入 compact failed row 并继续后续标的。重复运行已执行任务会拒绝，避免重复写入同一 job/symbol 结果。
- `GET /api/v1/backtest/rule/universe-jobs/{job_id}/status` 返回 universe job 的轻量 metadata / progress counters，包括派生的 `processed_count`；`GET /api/v1/backtest/rule/universe-jobs/{job_id}/diagnostics` 返回只读 compact aggregation：progress 摘要、reason buckets、top/worst metric leaders、本地数据覆盖计数，以及 `local_only=true / live_provider_calls_executed=false / concurrency_enabled=false` 保证。该诊断面不会触发重算、不会拉 provider、不会读取 raw traces，也不会把 full per-symbol drill-down 塞进摘要。`GET /api/v1/backtest/rule/universe-jobs/{job_id}/results` 返回分页 compact symbol rows，单页上限为 100，并支持按 `status`、`reasonCode`、`symbol` 前缀、推断 `market`、以及 `sequence_index / total_return_pct / max_drawdown_pct / win_rate_pct / trades_count / elapsed_ms` 做过滤与排序。执行后的 compact row 只包含表格所需字段：symbol/status/reason、`total_return_pct`、`max_drawdown_pct`、`win_rate_pct`、`trades_count`、runtime 与少量本地数据诊断，不默认存储 raw trades、equity curve 或 execution trace。
- universe readiness 诊断会显式声明 `localDataCoverageState`、`pointInTimeUniverse=false`、`survivorshipBiasState=uncontrolled`、`providerCalls=false`。
- `POST /api/v1/backtest/rule/compare` 提供 compare-runs 的 stored-first 读路径：它只读取已持久化的已完成运行，不会重新执行回测；当前返回最小可信对比面，包含 metadata、`parsed_strategy`、核心 metrics、benchmark summary、`execution_model`、每条运行自身的 `result_authority`，以及七个 additive 顶层摘要：`market_code_comparison`、`period_comparison`、`comparison_summary`、`parameter_comparison`、`robustness_summary`、`comparison_profile` 与 `comparison_highlights`。`market_code_comparison` 只消费 compare items 中已持久化的 `metadata.code`，按规范化代码推断 `cn / hk / us` 市场，并显式区分 `same_code / same_market_different_code / different_market / partial_metadata / unavailable_metadata`，其中只有 `same_code` 会被标记为 `state=direct` 与 `directly_comparable=true`；`period_comparison` 只基于已持久化 compare items 中的 `metadata.period_start/period_end` 生成区间关系判断，不会 fallback 到重跑或隐式推断，并显式区分 `identical / overlapping / disjoint / partial / unavailable`；`comparison_summary` 固定以“请求顺序中的第一条可比运行”为 baseline，并只对少量已持久化指标生成 delta/可比性摘要；`parameter_comparison` 则只基于已持久化的 `parsed_strategy.strategy_spec` 与 parsed-strategy authority 诊断，回答这些运行是否属于同一规范化 strategy family/type，以及哪些参数键 shared / differing / missing；`robustness_summary` 只复用前述四个已计算 compare layers 的现成状态，统一给出 `highly_comparable / partially_comparable / context_limited / insufficient_context` 四档 overall state，以及 `market_code / metrics_baseline / parameter_set / periods` 四个维度各自的 `aligned / partial / divergent / unavailable` 摘要；`comparison_profile` 则进一步只基于这些已计算 layers，给出一个 deterministic 的主比较模式：`same_strategy_parameter_variants / same_code_different_periods / same_market_cross_code / cross_market_mixed / mixed_context / insufficient_context`；`comparison_highlights` 最后只基于 trusted `comparison_summary.metric_deltas`、`robustness_summary` 与 `comparison_profile`，对当前已受信的少量指标返回 `winner / tie / limited_context_winner / limited_context_tie / unavailable` highlights，不会把所有可见数字都静默拿来排序。
- `GET /api/v1/backtest/rule/runs/{run_id}` 继续作为完整详情接口，包含 `execution_trace`、交易明细和审计数据。
- 当前 deterministic indicator strategies 在既有 `均线交叉 / MACD / RSI` 主信号之外，新增支持 additive 的固定百分比风险控制扩展：`fixed stop-loss`、`take-profit` 与 `trailing stop`。当自然语言里出现 `止损 5%`、`止盈 10%` 或 `移动止损 8%` 这类 bounded percentage 规则时，解析结果会保留到 `parsed_strategy.strategy_spec.risk_controls.{stop_loss_pct,take_profit_pct,trailing_stop_pct}`，执行时仍按既有“收盘触发、下一根 bar 开盘离场”的成交语义运行；范围继续保持最小：单标的、单仓位、百分比阈值，不扩展到参数优化、多资产或组合级风控。
- detail/history 返回里的 `result_authority` 现会额外暴露 replay/audit reopen 诊断：`replay_payload_source` / `replay_payload_completeness` / `replay_payload_missing_sections` 以及 `audit_rows_source` / `daily_return_series_source` / `exposure_curve_source`，用于区分“直接读取已持久化 payload”“基于持久化 audit rows 修补缺失 section”“仅基于已存 run artifacts 回补 legacy payload”“未读取 detail / unavailable”等状态。
- `execution_model` reopen 同样遵循 stored-first：优先读取 `summary.execution_model`，其次回退到已持久化的 `summary.request.execution_model`，两者都不存在时才从已存 assumptions / row/request 派生兼容配置。`result_authority` 会同步暴露 `execution_model_source` / `execution_model_completeness` / `execution_model_missing_fields`，用来区分“直接命中持久化 snapshot”“基于持久化 snapshot 修补缺字段”“仅从 legacy assumptions 派生”的不同来源。
- `trade_rows` reopen 现在也显式遵循 stored-first：detail 读取会优先消费已持久化的 `rule_backtest_trades`，并在 `result_authority` 中新增 `trade_rows_source` / `trade_rows_completeness` / `trade_rows_missing_fields`。历史存量交易行若缺少 `entry_rule_json` / `exit_rule_json` / `notes` 等兼容字段，会返回稳定 shape 的 `trades` 列表并显式标记 `stored_rule_backtest_trades+compat_repair` / `stored_partial_repaired`；若 run row 声明存在交易但持久化 trade rows 已丢失，则会明确返回 `unavailable`，不再把空交易列表伪装成完整重开结果。
- 为了让 reopen/debug 流程不必再从 `result_authority` 的 `omitted` 状态或零散字段里反推“哪些 artifacts 真的存在”，status/detail/history 三个读面现在统一返回结构化 `artifact_availability` 摘要，并把同一份摘要写回 `summary.artifact_availability`。该摘要只回答最小问题：是否已有可重开的 stored summary、parsed strategy、metrics、execution model、comparison、trade rows、equity curve、execution trace、run diagnostics、run timing；若历史 summary 缺失这一块，服务会从当前持久化事实做兼容回填；若 stored summary 与当前 trade rows 等真实存储状态已经不一致，也会显式标记为 live-storage repair，而不是继续回放过期布尔值。
- 为了把“这次 reopen 到底有多可信”再收口一层，status/detail/history 现在还会统一返回结构化 `readback_integrity` 摘要。它不复制 payload 内容，只回答当前读回路径的 integrity：是否用了 legacy fallback、是否用了 live-storage repair、是否存在 summary/storage drift、哪些 drift domain 受影响、当前 summary 还缺哪些关键字段，以及整体 `integrity_level` 是 `stored_complete`、`stored_repaired`、`legacy_fallback` 还是 `drift_repaired`。这个摘要主要复用已有的 `result_authority` 与 `artifact_availability` 信号，不另起一套并行 provenance 系统。
- 为了让 detail/history 的 authority 诊断形状更稳定，`result_authority` 现在还会包含版本化的归一化域视图：`contract_version` + `domains`。`domains.<name>` 统一使用 `source` / `completeness` / `state` / `missing` / `missing_kind` 五个字段表达各诊断域，旧的扁平字段仍保留以兼容既有消费者。

## P5 Web 可用性收口

- `/backtest` 继续作为配置与发起页，不改动现有标准回测与规则回测的后端执行链路；本轮主要收口输入分组、按钮文案和状态提示，减少“要先做什么、下一步会发生什么”的理解成本。
- `/backtest/results/:runId` 会优先展示运行状态卡，再展示结果摘要与图表工作区。运行中页面使用 `GET /api/v1/backtest/rule/runs/{run_id}/status` 做轻量轮询，进入 `completed / failed / cancelled` 后自动停止刷新。
- `/backtest/compare?runIds=...` 现在作为最小可用 compare workbench 路由存在：它只消费既有 `POST /api/v1/backtest/rule/compare` 的 stored-first 返回，不会在前端重新拉多条 detail 后本地拼结论。当前结果页 `历史结果` tab 里会继续把当前运行固定为 baseline，并允许勾选额外 completed runs；点击 `打开比较工作台` 后，前端会把 `runIds` 以 query 形式带到 compare page，由新页面集中渲染 compare summary / robustness / profile / highlights / market / period / parameter 几个核心 section。
- 规则回测运行中会明确展示 `parsing / queued / running / summarizing / completed / cancelled / failed` 状态，并在可取消阶段暴露 `取消运行`。取消仍复用既有 `POST /api/v1/backtest/rule/runs/{run_id}/cancel`，不会改写已完成结果。
- 结果页首屏优先展示用户更容易理解的摘要指标：总收益、相对基准或买入持有、最大回撤、交易次数、胜率、期末权益；原始参数、执行假设、技术说明和历史结果下沉到标签页或 disclosure。
- `execution_trace` 继续来自既有结果详情响应，但 Web 端默认先显示“关键节点”视图，只突出买卖动作、fallback 与异常说明；完整逐行轨迹仍可切换查看，并继续支持 CSV / JSON 导出。
- Historical Evaluation 现在会用更直接的产品文案说明本次数据来自 `LocalParquet` 还是 fallback 路径；`requested_mode / resolved_source / fallback_used` 这类诊断字段仍保留，但默认折叠在“查看数据源诊断”中，避免干扰主流程。

## 发布交接状态

- 当前分支的 backend backtest contract 已收口为 stored-first、additive-first：robustness、compare、support bundle、execution trace export、diagnostics 和 timing 都通过现有读面或只读导出面暴露，不要求前端重跑或重组后端结论。
- Web `/backtest` 和 `/backtest/results/:runId` 的新增 dashboard 面板只读消费 `strategy_spec.risk_controls` 与 `robustness_analysis`；它们不改变策略解析、执行、轮询、取消、compare API 或历史结果数据流。
- Web `/portfolio` 的 attribution dashboard 同样只读消费 additive `portfolio_attribution`、`account_attribution`、`industry_attribution`，不改变账本写入、快照计算、风险告警或导入/同步语义。
- Slices 14-16 已完成路由级/页面级 bundle hardening、键盘与 ARIA tooltip 回归、focused tests、lint、production build 和 production-preview 浏览器回归；当前 Vite large-chunk warning 已清除。
- 本轮 release close 后没有继续修改 backend、schemas、API 或 additive contract；`slice_report_14.json`、`slice_report_15.json`、`slice_report_16.json` 以及后续 slice report 都是本地交接记录，故意不纳入 git。
- 已知非阻塞项：还没有扩展成 chart-heavy advanced visualization layer；未来可以继续做更丰富的图表层、更多 compare 可视化、或更细的 accessibility semantics，但这些都不阻塞当前 release handoff。
- 安全/回滚姿态：新增 Web 面板和 chunk split 都是前端 additive/read-only 层，若 release 后需要降级，可优先回退对应前端 dashboard/lazy-loading commits；backend stored-first 读面与导出面仍保持兼容旧消费者。

## 本地 US parquet 优先级

- 美股日线优先读取 `LOCAL_US_PARQUET_DIR`。
- 若未设置 `LOCAL_US_PARQUET_DIR`，兼容回退到 `US_STOCK_PARQUET_DIR`。
- 若本地 parquet 命中，`resolved_source` 会显示为 `LocalParquet`，不会触发在线抓取。
- 若本地 parquet 缺失或损坏，当前 backtest 流程会沿用既有数据抓取 fallback，并在响应里暴露 `requested_mode / resolved_source / fallback_used`。

## 本地运行 API

```bash
.venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8000
```

可选环境变量：

```bash
export LOCAL_US_PARQUET_DIR=/path/to/local/us/parquet
# 仅兼容旧配置时再使用
export US_STOCK_PARQUET_DIR=/path/to/local/us/parquet
```

## 冒烟脚本

- 当前仓库内可直接复用的已提交冒烟脚本会自动：
  - 启动临时 uvicorn
  - 关闭管理认证
  - 创建临时数据库
  - 准备本地 `LOCAL_US_PARQUET_DIR` fixture
  - 运行断言并自动清理临时文件

- 标准 backtest API 冒烟：

```bash
python3 scripts/smoke_backtest_standard.py
```

- 规则 backtest API 冒烟：

```bash
python3 scripts/smoke_backtest_rule.py
```

- 合并运行：

```bash
python3 scripts/smoke_backtest_standard.py && python3 scripts/smoke_backtest_rule.py
```

## 已知假设与限制

- 生产环境真实读取本地 parquet 仍依赖 `pyarrow` 或 `fastparquet`；若环境缺少 parquet engine，仓库内 smoke 脚本会注入测试用 shim 来验证 `LOCAL_US_PARQUET_DIR` 优先路径与异步接口行为。
- 规则回测的同步执行依赖本地数据库中已有行情，或依赖既有数据源 fallback 成功。
- `execution_trace` 的详情、CSV、JSON 导出以持久化 `audit_rows` 为真源；历史旧记录缺少该字段时，会在读取时回补并标记 `trace_rebuilt`。
- `execution_model` 详情字段现在也会在 reopen 时统一规范为稳定形状；历史记录若只保留了部分 execution-model snapshot，会显式标记 `stored_partial_repaired` 并列出缺失字段，而不是返回形状不完整的 payload。
- `trade_rows` 详情字段现在也会在 reopen 时统一规范为稳定形状；历史记录若只保留了部分 trade-row 辅助 JSON，会显式标记 `stored_partial_repaired` 并列出缺失字段；若 run row 指示存在交易但持久化交易行缺失，则会标记 `unavailable`，避免把“空列表”误读成“完整但零交易”。
- replay 可视化 reopen 同样遵循 stored-first：非空的已持久化 `summary.visualization.audit_rows` / `daily_return_series` / `exposure_curve` 会优先复用；若历史运行只存了部分或空数组，会显式标记 `stored_partial_repaired`、`derived_from_stored_run_artifacts` 或 `unavailable`，避免把 reopen 时的临时重建结果伪装成完整持久化 payload。
