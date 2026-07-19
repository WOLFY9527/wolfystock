# AGENTS.md

本文件是本仓库 AI 协作规则的唯一真源。更完整的项目手册由
`scripts/build_ai_project_manual.py` 生成到 `docs/AI_PROJECT_MANUAL.md`。
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
  应更新 `README.md`、`docs/AI_PROJECT_MANUAL.md` 的生成源，或任务指定的
  canonical 文档位置。

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
   本文件、`README.md`、`docs/AI_PROJECT_MANUAL.md` 和最小相关源码/测试。
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

## Worktree 环境

- 在任意 checkout 运行 `./wolfy bootstrap --ensure`，构建或复用 OS cache root 下经过验证的 content-addressed Python 与 Web snapshots；worktree 不得链接另一个 checkout 的 mutable dependency 目录。
- Python direct intent 由 `requirements.txt` 与 `requirements-dev.txt` 保存；`requirements-lock.json` 及其 CPython 3.11/3.12 lock family 是唯一 install authority。权威矩阵支持 CPython 3.11 Linux x86_64 runtime/development、Linux aarch64 runtime（Docker `linux/arm64` 归一化身份）、macOS arm64/x86_64 与 Windows AMD64 runtime/development，以及 CPython 3.12 macOS arm64/x86_64 与 Windows AMD64 runtime/development；不在矩阵内的 target/profile 必须在安装前失败。运行 `./wolfy lock python --check` 检查 freshness、pins、target artifact filenames/hashes、sdist build requirements、resolver 和完整 target matrix。
- 只有显式依赖审查可运行 `./wolfy lock python --update`；该命令固定使用 `uv 0.11.19` 作为 resolver，必须审查 direct/transitive diff，且 bootstrap、test、dev、CI、release qualification 不得隐式更新 lock。
- 无网络模式使用 `./wolfy bootstrap --ensure --offline`；缺少已验证 snapshot 或 locked artifact cache material 时必须显式失败。Linux `arm64` 与 `aarch64` 必须归一到同一 reviewed runtime projection。在线/离线 bootstrap 必须选择同一 target/profile graph 和 artifact projection，并使用 hash verification，禁止回退到 requirements resolution。
- Release container 必须按 BuildKit `TARGETARCH` 复用同一 Python lock authority：`amd64` 选择 Linux x86_64 CPython 3.11 runtime，`arm64` 选择 Linux aarch64 CPython 3.11 runtime；只允许 `--no-deps --require-hashes --no-build-isolation` 的 reviewed lock 安装，禁止 requirements intent、development lock、uv 或其他 resolver 进入镜像依赖安装路径。
- `bash scripts/bootstrap_worktree.sh --check` 与 `--apply` 仅是 `./wolfy env verify` 和 `./wolfy bootstrap --ensure` 的兼容 delegate，不拥有独立 fingerprint、安装或链接逻辑。

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
- `docs/AI_PROJECT_MANUAL.md` 是生成文件；需要改手册内容时，修改
  `scripts/build_ai_project_manual.py` 或 tiny canonical source，再运行生成器。
- 修改 AI 协作治理资产时，运行 `python scripts/check_ai_assets.py`。

## 交付要求

最终说明应包含改了什么、为什么、验证情况、未验证项、风险、回滚方式和最终
`git status`。若创建 commit，报告 commit hash；若任务禁止 push，则不要 push。
