# WolfyStock Codex Model Routing

Purpose: choose Codex model and reasoning level efficiently without repeating the policy inside every task prompt.

Use this file for task planning and prompt headings. Keep model/reasoning labels outside the black-box prompt body unless the user explicitly asks otherwise.

## Default routing

| Task class | Recommended Codex model | Reasoning | Use when |
| --- | --- | --- | --- |
| Decision / architecture / high-risk audit | 5.5 | xhigh | The task defines boundaries, reviews architecture, chooses sequencing, evaluates protected-domain risk, or integrates reports from multiple workers. |
| Foundation / shared infrastructure execution | 5.4 | high | The task edits shell, global CSS/tokens, shared UI primitives, API boundaries, provider seams, security-adjacent code, or protected-domain-adjacent implementation after audit. |
| Audited bounded execution | 5.4 | high | The task has a clear audit-backed plan but still touches meaningful code or tests. |
| Low-risk bounded execution | 5.4 | medium | The task is a small docs/test/UI-detail patch with narrow allowed files and no shared architecture impact. |
| Read-only inventory / simple grep audit | 5.4 | medium | The task is purely read-only, low risk, and does not require architectural judgment. Escalate to 5.5+xhigh when the findings will drive core architecture decisions. |

## Heading format

Place this above the copyable prompt, not inside it:

```text
任务类型：架构/决策类
建议模型：Codex 5.5
推理：xhigh
```

```text
任务类型：执行类，已审计
建议模型：Codex 5.4
推理：high
```

```text
任务类型：低风险小补丁
建议模型：Codex 5.4
推理：medium
```

## Escalation rules

Use 5.5 + xhigh when any of these are true:

- multiple possible implementation strategies require judgment;
- the task affects long-term architecture or design language;
- the task touches shared shell, tokens, primitives, provider runtime, auth, portfolio accounting, scanner scoring, options ranking, or backtest calculations;
- a failed previous task needs root-cause diagnosis;
- several worker reports must be merged into a single execution plan.

Use 5.4 + high when the architecture is already decided but implementation still has regression risk.

Use 5.4 + medium only when the allowed files are narrow, behavior is obvious, and failure blast radius is low.

## Prompt-body rule

The copyable prompt body should stay model-agnostic. Put model choice in the surrounding task heading so the prompt remains reusable and cheaper.
