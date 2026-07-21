# AGENTS.md

本文件是本仓库 AI 协作规则的唯一真源。`docs/README.md` 是按任务读取的文档
入口；`scripts/build_ai_project_manual.py` 生成
`docs/generated/AI_PROJECT_MANUAL.md` 作为导航目录，不作为第二规则源。
如果本文件、用户当前提示、代码现状或脚本结果冲突，优先级为：
当前用户明确要求 -> 本文件 -> 可执行代码/脚本/测试 -> 其他说明。

## 硬规则

- 遵循目录边界：
  - 后端：`src/`、`data_provider/`、`api/`、`bot/`
  - Web：`apps/dsa-web/`
  - Desktop：`apps/dsa-desktop/`
  - 脚本/部署/CI：`scripts/`、`.github/workflows/`、`docker/`
- 未经当前任务明确授权，不执行 `git commit`、`git tag`、`git push`、
  `git merge`、`git rebase`、删除分支或删除 worktree。
- 若任务明确授权 commit / integration / cleanup，也必须先完成验证、检查
  diff/status、确认无冲突/无意外文件/无密钥，再执行授权动作。
- commit message 使用英文，不添加 `Co-Authored-By`。
- 不写死密钥、账号、token、私有 URL、模型名、端口、绝对本机路径或环境差异逻辑。
- 不修改任务范围外文件；不要顺手重构、移动、删除或格式化无关文件。
- 不新增平行实现；优先复用已有模块、配置入口、脚本和测试。
- 新增或改变配置项时，同步 `.env.example` 和相关说明。
- 用户可见行为、CLI/API 行为、部署方式、通知方式、报告结构或文档模型变化，
  应更新 `README.md`、`docs/README.md` 路由到的 canonical 文档，或任务指定的
  canonical 文档位置；不要直接编辑生成文档。

## 受保护域

除非当前任务明确授权并给出验证路径，否则不要修改：

- provider 适配、provider 顺序、fallback、缓存/新鲜度、source authority、凭证和外部网络行为
- scanner 打分、筛选、排序、阈值、score 贡献和 live/fallback 标签
- backtest fills、成本、指标、benchmark、参数/赢家语义、universe 与 stored result 语义
- portfolio 账户、现金、持仓、交易、P&L、FX、cost basis、broker sync/import 与 ledger 语义
- auth/RBAC/security、session、cookie、CSRF/CORS、token/password、MFA、admin 保护
- DB migration、root config、依赖/lockfile、CI、发布流程
- broker/order 执行、买卖/加减仓/目标价/仓位建议等交易建议

不要引入 fake data、fallback payload、placeholder readiness、隐藏兼容层、raw provider
泄漏、交易建议或一次性 Markdown 报告来满足任务。

## 默认工作流

1. 先做只读发现：确认 `pwd`、branch、`git status --short --branch`，阅读当前提示、
   本文件、`docs/README.md`，再按任务路由读取最小相关 canonical 文档、源码和测试；
   不要求默认加载整个生成手册或全部文档。
2. 判断改动面：docs / backend / frontend / API/schema / provider / auth /
   portfolio / backtest / workflow / review。
3. 保持最小必要改动；复杂度或风险上升时先收敛范围再继续。
4. 运行能证明当前改动的最小验证集，不用无关测试堆砌“完整感”。
5. 完成前检查 `git diff`、`git status`、必要的 secret/link/format 检查。

## 按变更风险分级的完成证据

<!-- BEGIN COMPLETION_EVIDENCE_TIERS -->
本节只规定完成报告必须保留的证据，不改变风险选择、gate 选择、gate 执行、
topology、release policy 或其他验收规则。任务和仓库要求运行的验证仍必须运行；
报告简洁只允许去掉重复叙述，不允许省略必需证据。R0 到 R5 的要求逐级累积，
失败、跳过、不可用、未执行、静态推断或未评估均不得写成通过。

- **R0**：报告结果、相对 accepted base 的精确 changed files、focused/static
  validation 的完整命令与结果、commit hash/subject（未创建时明确说明）、可执行
  rollback、最终 clean/dirty status，以及 upstream 与 push state。
- **R1**：保留全部 R0 字段；另外说明受影响的 test/mechanical owner、节点或生成
  产物范围（如适用），不得用“小改动”省略 focused validation 或未验证项。
- **R2**：保留全部 R0/R1 字段；另外报告 protected owner、adjacent contracts、
  topology delta（未变化也要给出验证）、targeted integration evidence，以及
  residual risk。
- **R3**：保留全部 R2 字段；对 public contract 或 cross-owner integration 给出
  producer/consumer 和 combined-tree 身份、所有受影响 owner 的 targeted integration
  结果、精确 topology delta 与仍未验证的集成风险。
- **R4**：保留全部 R3 字段；另外报告完整 immutable evidence identity，包括
  accepted base/tree/commit、environment、dependency/config、command/selection、artifact
  hash 和适用的 candidate identity；列出全部 required protected gates，并分别保留
  first attempt 与每次 retry 的结果。触发 browser/UAT、release 或 remote 验证时，
  必须给出真实执行证据和精确身份；未触发、未授权或未执行时明确记录，不能推断通过。
- **R5**：保留全部 R4 字段；绑定 frozen candidate 的 source/tree/artifact/digest、
  complete protected gates、browser/UAT/release 与 target-environment 证据、first
  attempt/retry 历史、promotion/rollback identity，以及精确 remote ref/digest 验证和
  push state。任何 identity mismatch 都使相关证据失效，必须如实报告并重新资格化。

无论报告层级，任务触发以下边界时都必须保留对应 evidence 与 rollback boundary：
auth/RBAC/owner isolation、persistence/transaction、provider isolation/source authority、
truth semantics、secrets/private paths、no-live、release identity、migration、browser、
target environment。特别保留 `missing != zero`、`not evaluated != passed`、
`skipped != passed`、`corrupt state != empty state`、`injected transport != live transport`
和 `task accepted != analysis completed`；不得用概括性“已验证”替代边界、命令、
结果、artifact identity 或限制条件。

若任务创建或依赖 temporary audit/evidence artifact，完成报告必须记录 artifact
classification、owner、仍存依赖、最早 retirement 条件和删除动作。只有在 durable
policy 已迁入 canonical authority、所有引用已移除且资格化前置条件满足后才能删除；
不得移动到 archive/historical/completed-report 目录，也不得保留 compatibility copy。
<!-- END COMPLETION_EVIDENCE_TIERS -->

## 文档路由

- `docs/documentation-manifest.json` 是 Markdown 分类、权威映射、任务路由、生成
  输出和 temporary audit 生命周期的机器真源。
- `docs/README.md` 是生成的短入口；按任务读取，不把 generated、historical 或
  temporary evidence 当作 canonical source。
- 代码、脚本、测试、schema 和 workflow 是最终 executable truth；文档只能说明
  owner 和合同，不能覆盖可执行结果。
- 修改文档体系时运行 `python scripts/check_documentation.py`、生成器 freshness、
  `python scripts/check_ai_assets.py` 及对应 focused tests。

## Worktree 环境

- 在任意 checkout 运行 `./wolfy bootstrap --ensure`；worktree 不得链接另一个
  checkout 的 mutable dependency 目录。
- `./wolfy`、reviewed Python lock family、target/profile fail-closed 规则、offline
  hash verification 和 container install boundary 的 canonical 说明在
  `docs/development/environment.md`；这些硬边界不得通过局部脚本或 fallback 改写。
- 只有显式依赖审查可运行 `./wolfy lock python --update`；bootstrap、test、dev、
  CI 和 release qualification 不得隐式更新 lock。
- `bash scripts/bootstrap_worktree.sh --check` 与 `--apply` 仅是现有 `./wolfy`
  命令的 delegate，不拥有独立 fingerprint、安装或链接逻辑。

## Worktree 生命周期

`scripts/worktree_preflight.py lifecycle` 是唯一的 verified worktree
lifecycle authority；它不拥有环境安装或 Git promotion authority。一个任务对应一个
独立 branch/worktree 和一个 commit。`status` 只读；`setup` 只复用完全匹配且 clean 的
registration、identity 和环境 fingerprint，其他 missing、mismatched、detached、stale 或
unverified 状态一律 fail closed，绝不 reset、clean、delete 或重用。

`cleanup` 只有在 validation passed、所需 LAND succeeded、candidate 与指定 remote ref
完全相等且本地状态 clean 后才能执行。push、merge、rebase 与 LAND 必须由显式的外部
authority 执行，preflight 不会调用或修复它们。允许的 mutation 仅为精确的
`git worktree add/remove/prune`、compare-and-delete `git update-ref` 和既有 `wolfy`
bootstrap；不得使用 force removal、stash、checkout-discard、recursive deletion 或自动
branch movement recovery。输出的 `wolfystock.worktree-lifecycle.v1` 保留
`not_evaluated`、`passed`、`failed`、`succeeded`、`refused`、`preserved` 等精确状态，
并以 identity 与 `resultHash` 绑定证据。

## 常用命令

运行：

```bash
python main.py
python main.py --debug
python main.py --dry-run
python main.py --stocks 600519,hk00700,AAPL
python main.py --market-review
python main.py --schedule
python main.py --serve
python main.py --serve-only
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

验证：

```bash
./scripts/ci_gate.sh
./wolfy lock python --check
./wolfy exec --profile test -- python -m pytest -m "not network"
python -m py_compile <changed_python_files>
./wolfy exec --profile test -- npm --prefix apps/dsa-web run lint
./wolfy exec --profile test -- npm --prefix apps/dsa-web run build
cd apps/dsa-desktop && npm install && npm run build
python scripts/build_ai_project_manual.py --check
python scripts/check_ai_assets.py
```

> Shell 说明：`scripts/*.sh` 与 `$(git rev-parse HEAD)` 是 POSIX shell
> （bash/sh）语法。Windows 请在 Git Bash、WSL 或提供 POSIX `sh` 的shell 中运行，
> 例如 `bash scripts/ci_gate.sh`。PowerShell 同样支持 `$(...)` 子表达式语法。

## AI 协作资产

- `CLAUDE.md` 必须保持为指向 `AGENTS.md` 的软链接。
- `.github/copilot-instructions.md` 与 `.github/instructions/*.instructions.md`
  是 GitHub/Copilot 镜像说明；若冲突，以本文件为准。
- `.claude/skills/` 是仓库内保留的 skill 资产；`.claude/reviews/` 是本地分析产物。
- `docs/README.md`、`docs/generated/AI_PROJECT_MANUAL.md` 与
  `docs/generated/AI_PROJECT_MANUAL_SOURCES.json` 是生成文件；修改
  `docs/documentation-manifest.json` 或相应 canonical source，再运行生成器。
- 修改 AI 协作治理资产时，运行 `python scripts/check_ai_assets.py`。

## 交付要求

最终说明应包含改了什么、为什么、验证情况、未验证项、风险、回滚方式和最终
`git status`。若创建 commit，报告 commit hash；若任务禁止 push，则不要 push。
