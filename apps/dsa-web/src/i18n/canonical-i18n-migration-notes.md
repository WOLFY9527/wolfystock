# Canonical i18n Migration Notes

This inventory marks the remaining inline EN/ZH copy found in the final frontend sweep. These strings should move into `core.ts` under canonical namespaces before the next full i18n cleanup.

## Backtest Shared Copy

- `src/components/backtest/shared.tsx:117`-`184`: benchmark option labels and benchmark-mode fallbacks.
- `src/components/backtest/shared.tsx:317`-`351`: periodic strategy order, cash-policy, execution, exit-policy, and assumption copy.
- `src/components/backtest/shared.tsx:408`-`415`: rule-run status descriptions.
- `src/components/backtest/shared.tsx:465`-`543`: historical data-source, fallback, and diagnostics copy.
- `src/components/backtest/shared.tsx:612`-`936`: assumption labels, empty states, table headers, badges, and action labels.

## Portfolio Page Copy

- `src/pages/PortfolioPage.tsx:38`-`342`: broker, transaction direction, corporate action, and market labels.
- `src/pages/PortfolioPage.tsx:458`-`754`: attribution visual labels, badges, and FX empty-state copy.
- `src/pages/PortfolioPage.tsx:1775`-`1835`: portfolio attribution panel headings, chart titles, and top-slice labels.

## Deterministic Backtest Result Copy

- `src/pages/DeterministicBacktestResultPage.tsx:80`-`105`: tab labels.
- `src/pages/DeterministicBacktestResultPage.tsx:240`-`448`: robustness and risk-control additive panel labels.
- `src/pages/DeterministicBacktestResultPage.tsx:727`-`959`: page title, summary shell, active-run status, next-step, and export copy.
- `src/pages/DeterministicBacktestResultPage.tsx:1050`-`1740`: cancel dialog, banners, controls, parameter sections, scenario comparison, reusable setup, history comparison, and invalid-run copy.

## Preview Pages

- `src/pages/PreviewReportPage.tsx`: no remaining shell copy outside `previewReport.*`; dynamic report body may still include mixed-language fixture content from `src/dev/reportPreviewFixture.ts`.
- `src/pages/PreviewFullReportDrawerPage.tsx`: no remaining shell copy outside `previewFullReport.*`; drawer body content comes from localized `previewFullReport.markdown`.
