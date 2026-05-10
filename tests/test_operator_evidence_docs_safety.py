import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

DOC_PATHS = (
    *sorted((REPO_ROOT / "docs" / "audits").glob("operator-evidence-*.md")),
    *sorted((REPO_ROOT / "docs" / "audits").glob("evidence-*.md")),
    REPO_ROOT / "docs" / "audits" / "public-launch-readiness-master.md",
    REPO_ROOT / "docs" / "audits" / "public-launch-gap-register.md",
    REPO_ROOT / "docs" / "audits" / "deployment-readiness-checklist.md",
    REPO_ROOT / "docs" / "audits" / "launch-acceptance-evidence-pack.md",
    REPO_ROOT / "docs" / "audits" / "release-rollback-runbook.md",
    REPO_ROOT / "docs" / "audits" / "db-retention-backup-restore-drill-plan.md",
    REPO_ROOT / "docs" / "audits" / "public-api-abuse-limiter-operator-note.md",
    REPO_ROOT / "scripts" / "README.md",
)

FORBIDDEN_RELEASE_WORDING = (
    "launch-approved",
    "production-ready",
    "automatic-GO",
    "public launch GO",
)

SECRET_MARKER_PATTERNS = (
    ("private key material", re.compile(r"BEGIN\s+(?:RSA\s+|DSA\s+|EC\s+|OPENSSH\s+|PGP\s+)?PRIVATE\s+KEY")),
    ("AWS access key id", re.compile(r"(?<![A-Z0-9])(AKIA|ASIA)[0-9A-Z]{16}(?![A-Z0-9])")),
    ("OpenAI-style API key", re.compile(r"(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]{24,}(?![A-Za-z0-9_])")),
    ("GitHub token", re.compile(r"(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9_]{24,}(?![A-Za-z0-9_])")),
    ("Slack token", re.compile(r"(?<![A-Za-z0-9_])xox[baprs]-[A-Za-z0-9-]{20,}(?![A-Za-z0-9_])")),
    ("Google API key", re.compile(r"(?<![A-Za-z0-9_])AIza[0-9A-Za-z_-]{30,}(?![A-Za-z0-9_])")),
    ("bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE)),
    ("raw URL credentials", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s<>\"'`]+:[^\s<>\"'`@]+@[^\s<>\"'`]+", re.IGNORECASE)),
)

UNSAFE_PLACEHOLDER_PATTERN = re.compile(
    r"(<[^>\n]*(?:secret|token|password|credential|cookie|session|dsn|"
    r"database[-_ ]?url|private[-_ ]?key|provider[-_ ]?payload|raw[-_ ]?log|"
    r"request[-_ ]?body|response[-_ ]?body|email|webhook|url)[^>\n]*>"
    r"|\{\{[^}\n]*(?:secret|token|password|credential|cookie|session|dsn|"
    r"database[-_ ]?url|private[-_ ]?key|provider[-_ ]?payload|raw[-_ ]?log|"
    r"request[-_ ]?body|response[-_ ]?body|email|webhook|url)[^}\n]*\}\})",
    re.IGNORECASE,
)


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def test_operator_evidence_docs_do_not_carry_release_or_secret_markers() -> None:
    findings: list[str] = []

    for path in DOC_PATHS:
        assert path.exists(), f"Expected documentation target is missing: {_relative(path)}"
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            lowered = line.lower()

            for wording in FORBIDDEN_RELEASE_WORDING:
                if wording.lower() in lowered:
                    findings.append(f"{_relative(path)}:{line_number} [forbidden release wording]")

            for rule, pattern in SECRET_MARKER_PATTERNS:
                if pattern.search(line):
                    findings.append(f"{_relative(path)}:{line_number} [{rule}]")

            if UNSAFE_PLACEHOLDER_PATTERN.search(line):
                findings.append(f"{_relative(path)}:{line_number} [unsafe placeholder]")

    assert not findings, "Unsafe operator evidence doc markers found:\n" + "\n".join(findings[:40])
