import re
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ComplianceViolation:
    kind: str
    evidence: str


_URL_RE = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
_SHORTLINK_RE = re.compile(
    r"\b(?:bit\.ly|t\.co|tinyurl\.com|goo\.gl|ow\.ly|is\.gd|buff\.ly|lnkd\.in)/\S+",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

_PAST_TENSE_PATTERNS = [
    re.compile(r"\bwe\s+have\s+(updated|revised)\s+(the\s+)?(paper|manuscript)\b", re.IGNORECASE),
    re.compile(r"\bwe\s+(updated|revised)\s+(the\s+)?(paper|manuscript)\b", re.IGNORECASE),
]


def apply_icml_tense_fixes(text: str) -> str:
    if not text:
        return text
    fixed = text
    replacement = "we will incorporate this in the camera-ready / subsequent version"
    for pat in _PAST_TENSE_PATTERNS:
        fixed = pat.sub(replacement, fixed)
    return fixed


def scan_compliance_violations(text: str) -> List[ComplianceViolation]:
    violations: List[ComplianceViolation] = []
    if not text:
        return violations

    m = _URL_RE.search(text)
    if m:
        violations.append(ComplianceViolation(kind="url", evidence=m.group(0)[:120]))

    m = _SHORTLINK_RE.search(text)
    if m:
        violations.append(ComplianceViolation(kind="shortlink", evidence=m.group(0)[:120]))

    m = _EMAIL_RE.search(text)
    if m:
        violations.append(ComplianceViolation(kind="email", evidence=m.group(0)[:120]))

    for pat in _PAST_TENSE_PATTERNS:
        m = pat.search(text)
        if m:
            violations.append(ComplianceViolation(kind="past_tense_update_claim", evidence=m.group(0)[:120]))
            break

    return violations


def format_violations(violations: List[ComplianceViolation]) -> str:
    if not violations:
        return ""
    lines = []
    for v in violations:
        lines.append(f"- {v.kind}: {v.evidence}")
    return "\n".join(lines)

