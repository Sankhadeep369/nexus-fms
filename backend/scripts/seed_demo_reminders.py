"""Seeds the Reminder Agent's Supabase table with demo reminders derived from
the actual current_contracts/ corpus — one AMC renewal reminder per active
vendor contract, due date computed from each contract's Effective Date plus
its stated term (defaults to 12 months if not explicitly found).

This gives the Reminder Agent UI real data to display immediately, rather
than an empty list on first use.

Usage (from 08_rag_app/backend, with venv active):
    python -m scripts.seed_demo_reminders --email you@example.com
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.core.config import settings

_EFFECTIVE_DATE_RE = re.compile(r"\|\s*Effective Date\s*\|\s*([^|]+?)\s*\|")
_VENDOR_RE = re.compile(r"\|\s*Vendor\s*\|\s*([^|]+?)\s*\|")
_CATEGORY_RE = re.compile(r"\|\s*Service Category\s*\|\s*([^|]+?)\s*\|")
_TERM_RE = re.compile(r"for\s+\w+\s+\((\d+)\)\s+months", re.IGNORECASE)

_MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}


def _parse_date(text: str) -> date | None:
    m = re.match(r"(\d{1,2})\s+(\w+)\s+(\d{4})", text.strip())
    if not m:
        return None
    day, month_name, year = m.groups()
    month = _MONTHS.get(month_name)
    if not month:
        return None
    return date(int(year), month, int(day))


def _add_months(d: date, months: int) -> date:
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    # Clamp day for short months (e.g. Jan 31 + 1 month -> Feb 28/29)
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                       31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def extract_contract_renewals() -> list[dict]:
    renewals = []
    for path in sorted(settings.corpus_dir.glob("current_contracts/*.txt")):
        text = path.read_text(encoding="utf-8", errors="replace")

        eff_match = _EFFECTIVE_DATE_RE.search(text)
        vendor_match = _VENDOR_RE.search(text)
        category_match = _CATEGORY_RE.search(text)
        term_match = _TERM_RE.search(text)

        if not (eff_match and vendor_match and category_match):
            print(f"  skip (missing fields): {path.name}")
            continue

        effective_date = _parse_date(eff_match.group(1))
        if not effective_date:
            print(f"  skip (unparseable date '{eff_match.group(1)}'): {path.name}")
            continue

        term_months = int(term_match.group(1)) if term_match else 12
        due_date = _add_months(effective_date, term_months)
        vendor = vendor_match.group(1).strip()
        category = category_match.group(1).strip()
        site = path.stem.rsplit("_", 1)[-1]  # e.g. "HQ", "Austin", "Plano", "FortWorth"

        renewals.append(
            {
                "title": f"{category} AMC Renewal — {vendor} ({site})",
                "due_date": due_date,
                "related_vendor": vendor,
                "notes": f"Contract effective {effective_date.isoformat()}, {term_months}-month term. Source: {path.name}",
            }
        )
    return renewals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True, help="Recipient email for the seeded reminders")
    args = parser.parse_args()

    from app.core.agents.reminder_store import get_reminder_store

    store = get_reminder_store()
    if store is None:
        print("ERROR: Supabase not configured (SUPABASE_URL / SUPABASE_ANON_KEY missing).")
        return

    renewals = extract_contract_renewals()
    print(f"\nExtracted {len(renewals)} contract renewals from corpus.\n")

    for r in renewals:
        store.create(
            title=r["title"],
            due_date=r["due_date"],
            recipient_email=args.email,
            notes=r["notes"],
            related_vendor=r["related_vendor"],
        )
        print(f"  seeded: {r['title']} -> due {r['due_date']}")

    print(f"\nDone. {len(renewals)} reminders created for {args.email}.")


if __name__ == "__main__":
    main()
