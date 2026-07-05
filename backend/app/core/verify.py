"""Answer verification pass (orchestration layer).

Cheap, deterministic self-checks run on an agent's answer before it ships:

  - table_integrity   — every Markdown table has a proper piped header + separator
                        and a consistent column count (catches a bolded pseudo-header
                        like "**Term | A | B**" that renders as text, not a table).
  - totals_reconcile  — a "Total" row equals the sum of its column (catches an
                        invented grand total).
  - currency_note     — when two currencies appear, a normalisation note is present
                        (so a reader never sees a raw USD-vs-INR comparison).

Deterministic agents (budget, portfolio) are correct by construction and should
pass with zero issues — verification is a safety net there.  For the LLM-synthesised
path (vendor_decision) `refine_answer` re-prompts the model to fix the specific
issues once before the answer is accepted or falls back.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("nexus.verify")

_SEPARATOR_RE = re.compile(r"^[\s|:\-]*-{3,}[\s|:\-]*$")
_AMOUNT_RE = re.compile(r"(?:\$|₹|INR|Rs\.?|USD)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
# Distinct currency markers, normalised.
_CCY_MARKERS = (("$", "USD"), ("usd", "USD"), ("₹", "INR"), ("inr", "INR"), ("rs.", "INR"))
_NORMALISATION_HINT = re.compile(
    r"convert|≈|1\s*usd|exchange rate|different currenc|like-for-like|per the rate", re.IGNORECASE
)
_TOTAL_TOLERANCE = 0.01


@dataclass(frozen=True)
class Issue:
    code: str
    detail: str


@dataclass
class VerifyReport:
    ok: bool
    issues: list[Issue]

    def summary(self) -> str:
        return "; ".join(f"{i.code}: {i.detail}" for i in self.issues)


# ---------------------------------------------------------------------------
# Table parsing
# ---------------------------------------------------------------------------

def _split_cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _find_tables(answer: str) -> list[dict]:
    """Return {header_line, sep_index, ncols, data_rows} for each Markdown table."""
    lines = answer.splitlines()
    tables = []
    for i, line in enumerate(lines):
        if "|" not in line or not _SEPARATOR_RE.match(line):
            continue
        header = lines[i - 1] if i > 0 else ""
        ncols = len(_split_cells(line))
        data = []
        j = i + 1
        while j < len(lines) and "|" in lines[j]:
            data.append(lines[j])
            j += 1
        tables.append({"header": header, "sep_index": i, "ncols": ncols, "data": data})
    return tables


def _num(cell: str) -> float | None:
    m = _AMOUNT_RE.search(cell)
    if m:
        return float(m.group(1).replace(",", ""))
    bare = re.fullmatch(r"\*{0,2}([\d,]+(?:\.\d+)?)\*{0,2}", cell.strip())
    return float(bare.group(1).replace(",", "")) if bare else None


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _check_table_integrity(answer: str, tables: list[dict]) -> list[Issue]:
    issues = []
    for t in tables:
        header = t["header"].strip()
        if "|" not in header:
            issues.append(Issue("malformed_table", "table separator has no piped header row above it"))
            continue
        # A header wrapped entirely in bold renders as text, not a table header.
        if header.startswith("**") and header.endswith("**"):
            issues.append(Issue("malformed_table", f"header is bold text, not a table row: {header[:50]}"))
        if len(_split_cells(header)) != t["ncols"]:
            issues.append(Issue("malformed_table", f"header/separator column count mismatch ({header[:40]})"))
    return issues


def _check_totals(tables: list[dict]) -> list[Issue]:
    issues = []
    for t in tables:
        total_row = next((r for r in t["data"] if "total" in r.lower()), None)
        if not total_row:
            continue
        total_cells = _split_cells(total_row)
        data_rows = [_split_cells(r) for r in t["data"] if r is not total_row and "total" not in r.lower()]
        for col in range(len(total_cells)):
            stated = _num(total_cells[col]) if col < len(total_cells) else None
            if stated is None:
                continue
            column_vals = [_num(dr[col]) for dr in data_rows if col < len(dr)]
            column_vals = [v for v in column_vals if v is not None]
            if len(column_vals) < 2:
                continue
            summed = sum(column_vals)
            if abs(summed - stated) / max(stated, 1.0) > _TOTAL_TOLERANCE:
                issues.append(Issue(
                    "total_mismatch",
                    f"stated total {stated:,.0f} != column sum {summed:,.0f}",
                ))
    return issues


def _check_currency_note(answer: str) -> list[Issue]:
    found = set()
    low = answer.lower()
    for marker, code in _CCY_MARKERS:
        if marker in (answer if marker == "$" or marker == "₹" else low):
            found.add(code)
    if len(found) >= 2 and not _NORMALISATION_HINT.search(answer):
        return [Issue("mixed_currency_no_note", f"currencies {sorted(found)} shown without a normalisation note")]
    return []


def verify_answer(answer: str, *, check_currency: bool = False) -> VerifyReport:
    """Run the deterministic self-checks and return a report."""
    if not answer or not answer.strip():
        return VerifyReport(ok=False, issues=[Issue("empty", "answer is empty")])
    tables = _find_tables(answer)
    issues: list[Issue] = []
    issues += _check_table_integrity(answer, tables)
    issues += _check_totals(tables)
    if check_currency:
        issues += _check_currency_note(answer)
    return VerifyReport(ok=not issues, issues=issues)


# ---------------------------------------------------------------------------
# Refine (LLM paths only)
# ---------------------------------------------------------------------------

_REFINE_PROMPT = """\
The following answer has specific formatting/consistency issues. Rewrite it fixing \
ONLY these issues. Keep every figure, name, and fact EXACTLY as written — do not add, \
remove, convert, or recompute any number.

ISSUES TO FIX:
{issues}

ANSWER TO FIX:
{answer}

Return only the corrected answer, no commentary."""


def refine_answer(answer: str, issues: list[Issue], api_key: str, model: str) -> str | None:
    """Ask the LLM to fix the listed issues without touching the facts. Returns the
    revised answer, or None on failure."""
    if not issues or not api_key:
        return None
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _REFINE_PROMPT.format(
                issues="\n".join(f"- {i.code}: {i.detail}" for i in issues),
                answer=answer,
            )}],
            max_tokens=800,
            temperature=0.0,
        )
        revised = resp.choices[0].message.content.strip()
        logger.info("verify: refined answer to fix %d issue(s)", len(issues))
        return revised or None
    except Exception as exc:
        logger.warning("verify: refine call failed (%s)", exc)
        return None
