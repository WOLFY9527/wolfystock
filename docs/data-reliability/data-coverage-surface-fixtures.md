# Data Coverage Surface Fixtures

This catalog maps the current Data Coverage surface registry to bounded
product-level row states for documentation and test fixtures.

The examples below stay consumer-safe:

- they describe product posture instead of implementation details;
- they fail closed when coverage, freshness, or review state is incomplete;
- they use bounded user-facing copy only.

## Registry Coverage

| Surface | Route | Coverage focus | Consumer posture |
| --- | --- | --- | --- |
| Market Overview | `/zh/market-overview` | 市场总览状态 | 产品状态优先 |
| Liquidity | `/zh/market/liquidity-monitor` | 流动性观察状态 | 产品状态优先 |
| Rotation | `/zh/market/rotation-radar` | 轮动观察状态 | 产品状态优先 |
| Scanner | `/zh/scanner` | 候选观察状态 | 仅观察总结 |
| Single-stock | `/zh` | 个股研究摘要 | 仅观察总结 |
| Watchlist | `/zh/watchlist` | 关注列表状态 | 产品状态优先 |
| Portfolio | `/zh/portfolio` | 组合研究状态 | 产品状态优先 |
| Backtest | `/zh/backtest` | 回测结果状态 | 产品状态优先 |
| Options | `/zh/options-lab` | 期权结构观察状态 | 仅观察总结 |

## Row-State Fixture Catalog

| Surface | Route | Fixture state | Consumer-safe state | Product-level fail-closed reason | Consumer example copy |
| --- | --- | --- | --- | --- | --- |
| Market Overview | `/zh/market-overview` | 更新审查待完成 | `UPDATING` | 正在等待更新完成后再恢复完整展示。 | `数据更新中，稍后将自动刷新。` |
| Liquidity | `/zh/market/liquidity-monitor` | 降级后暂停评分 | `PAUSED` | 部分关键覆盖暂缺，当前评分暂停。 | `部分数据暂不可用，当前评分已暂停。` |
| Rotation | `/zh/market/rotation-radar` | 部分覆盖缺口 | `PARTIAL` | 部分轮动证据缺口仍在，当前结论降级。 | `部分数据暂不可用。` |
| Scanner | `/zh/scanner` | 授权复核未通过 | `INSUFFICIENT` | 独立授权复核尚未完成，候选仅供观察。 | `当前信号置信度较低，仅供观察。` |
| Single-stock | `/zh` | 最近一次可用快照 | `DELAYED` | 仅保留最近一次可用快照，避免误读为实时结论。 | `已使用最近一次可用数据。` |
| Watchlist | `/zh/watchlist` | 覆盖暂不可用 | `UNAVAILABLE` | 当前条目覆盖不可用，先停止展示可行动信号。 | `本模块暂不可用，请稍后重试。` |
| Portfolio | `/zh/portfolio` | 仅剩代理覆盖 | `INSUFFICIENT` | 当前仅有代理覆盖，不能作为完整研究结论。 | `当前信号置信度较低，仅供观察。` |
| Backtest | `/zh/backtest` | 展示复核未完成 | `UNAVAILABLE` | 展示复核尚未完成，结果先保持关闭。 | `本模块暂不可用，请稍后重试。` |
| Options | `/zh/options-lab` | 策略仅供观察 | `INSUFFICIENT` | 缺少独立授权复核，策略结论只能作为观察提示。 | `当前信号置信度较低，仅供观察。` |

## Consumer Copy Guardrails

- 先给用户一个有限的产品状态，再补一句短说明。
- 只描述用户当前能否继续观察、等待或稍后重试。
- 缺少覆盖、授权复核或展示复核时，一律保持 fail-closed。
- 不展开内部诊断、来源分层、实现细节或存储字段。
