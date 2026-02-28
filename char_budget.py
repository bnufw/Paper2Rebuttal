from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class CharBudgetResult:
    text: str
    chars: int
    attempts: int


def ensure_within_char_limit(
    draft: str,
    limit: int,
    compress: Callable[[str, int], str],
    max_attempts: int = 3,
) -> CharBudgetResult:
    if limit <= 0:
        raise ValueError("limit must be positive")

    text = draft or ""
    attempts = 0
    while len(text) > limit:
        if attempts >= max_attempts:
            raise ValueError(f"Unable to compress to <= {limit} characters after {max_attempts} attempts")
        attempts += 1
        text = compress(text, limit) or ""

    return CharBudgetResult(text=text, chars=len(text), attempts=attempts)


def split_must_keep_points(questions: list[str], max_points: int = 8) -> str:
    pts = []
    for q in questions[:max_points]:
        q = (q or "").strip()
        if q:
            pts.append(f"- {q}")
    return "\n".join(pts)

