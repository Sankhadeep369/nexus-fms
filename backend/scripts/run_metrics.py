"""NEXUS internal quality metrics.

Runs a representative test query for each of the 17 FM domains, checks each
response against quality criteria, and prints a summary report with per-domain
pass/fail and an overall score.

Usage (from 08_rag_app/backend, with venv active and uvicorn on :8000):
    python -m scripts.run_metrics
    python -m scripts.run_metrics --base-url http://127.0.0.1:8000
    python -m scripts.run_metrics --output metrics_report.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field

# Force UTF-8 output on Windows where the default codepage (cp1252) can't
# encode characters that appear in answer previews or detail strings.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Test suite — one query per FM domain
# ---------------------------------------------------------------------------

TEST_CASES: list[dict] = [
    {"domain": "HVAC & Chiller Plant",          "type": "checklist",
     "query": "What should I check weekly for the chiller plant?"},
    {"domain": "Electrical Systems",            "type": "factual",
     "query": "What documentation is needed for an electrical certificate renewal?"},
    {"domain": "Fire Safety & Life Safety",     "type": "checklist",
     "query": "What's included in a quarterly fire extinguisher inspection?"},
    {"domain": "Security & Surveillance",       "type": "factual",
     "query": "List common causes of CCTV downtime and how to fix them."},
    {"domain": "Plumbing & Water Systems",      "type": "factual",
     "query": "What are typical SLA response times for plumbing emergencies?"},
    {"domain": "Civil & Structural",            "type": "factual",
     "query": "What approvals are typically required before structural modifications in a commercial building?"},
    {"domain": "Parking & ANPR",               "type": "factual",
     "query": "How are ANPR barriers typically maintained in parking facilities?"},
    {"domain": "BMS & IT / Network",           "type": "factual",
     "query": "Which network and BMS components need regular license renewals?"},
    {"domain": "Energy Management",            "type": "checklist",
     "query": "What should be included in a monthly energy audit report?"},
    {"domain": "Housekeeping & Pest Control",  "type": "factual",
     "query": "Summarize the housekeeping SOP for common areas."},
    {"domain": "Waste Management",             "type": "factual",
     "query": "Summarize best practices for waste disposal compliance."},
    {"domain": "HSE & Permits",                "type": "factual",
     "query": "What PPE is required for electrical maintenance work?"},
    {"domain": "Vendor & Contract Management", "type": "checklist",
     "query": "Outline the steps for onboarding a new facilities vendor."},
    {"domain": "Budgeting & AMC Calendar",     "type": "draft",
     "query": "Draft a memo on an upcoming AMC renewal."},
    {"domain": "Compliance & Certificates",    "type": "checklist",
     "query": "Summarize this month's compliance checklist."},
    {"domain": "Emergency & BCP",              "type": "checklist",
     "query": "What's a typical emergency evacuation drill checklist?"},
    {"domain": "Landscaping & General Upkeep", "type": "factual",
     "query": "What routine maintenance tasks should be done quarterly for building exterior and landscaping?"},
]

# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------

_NON_LATIN = re.compile(
    r"[؀-ۿऀ-ॿঀ-৿฀-๿一-鿿぀-ヿ가-힯]"
)

_ARTIFACT_MARKERS = [
    "end of template", "do not reuse", "this response was assembled",
    "assembled from the attached", "note: the attached",
]

_FM_TERMS = [
    "maintenance", "contract", "vendor", "inspection", "compliance",
    "safety", "hvac", "electrical", "fire", "security", "plumbing",
    "audit", "checklist", "sop", "amc", "sla", "ppm", "noc", "bms",
]


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class CaseResult:
    domain: str
    query: str
    answer: str
    latency_ms: int
    cache_hit: bool
    valid: bool
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def score(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def total_checks(self) -> int:
        return len(self.checks)

    @property
    def passed(self) -> bool:
        return self.score == self.total_checks


def _run_checks(answer: str, valid: bool) -> list[CheckResult]:
    checks: list[CheckResult] = []

    # 1. Backend validation passed
    checks.append(CheckResult("backend_valid", valid, "" if valid else "backend returned valid:false"))

    # 2. English only
    m = _NON_LATIN.search(answer)
    checks.append(CheckResult(
        "english_only",
        m is None,
        f"found non-Latin at pos {m.start()}: '{answer[m.start():m.start()+15]}'" if m else "",
    ))

    # 3. No artifact leakage
    lower = answer.lower()
    artifact = next((a for a in _ARTIFACT_MARKERS if a in lower), None)
    checks.append(CheckResult("no_artifacts", artifact is None, artifact or ""))

    # 4. Reasonable length (50–1500 words)
    words = len(answer.split())
    checks.append(CheckResult(
        "reasonable_length",
        50 <= words <= 1500,
        f"{words} words (expected 50-1500)",
    ))

    # 5. FM relevance — at least 2 FM terms present
    found = [t for t in _FM_TERMS if t in lower]
    checks.append(CheckResult(
        "fm_relevant",
        len(found) >= 2,
        f"found: {found[:5]}" if found else "no FM terms detected",
    ))

    # 6. Not a fallback message
    is_fallback = "nexus wasn't able to produce" in lower or "nexus couldn't produce" in lower
    checks.append(CheckResult("not_fallback", not is_fallback, "answer is fallback message" if is_fallback else ""))

    return checks


# ---------------------------------------------------------------------------
# SSE consumer
# ---------------------------------------------------------------------------

def _call_chat(base_url: str, query: str) -> dict:
    req = urllib.request.Request(
        f"{base_url}/chat",
        data=json.dumps({"query": query, "mode": "simple"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    answer_parts: list[str] = []
    done_payload: dict = {}
    with urllib.request.urlopen(req, timeout=600) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            payload = json.loads(line[5:].strip())
            if payload["type"] == "token":
                answer_parts.append(payload["text"])
            elif payload["type"] == "done":
                done_payload = payload
    return {
        "answer": done_payload.get("final_answer") or "".join(answer_parts),
        "latency_ms": done_payload.get("latency_ms", {}).get("total", 0),
        "cache_hit": done_payload.get("cache_hit") is not None,
        "valid": done_payload.get("valid", True),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default=None, help="Save JSON report to this file")
    parser.add_argument("--skip-slow", action="store_true",
                        help="Skip queries not already in cache (avoids long waits)")
    args = parser.parse_args()

    results: list[CaseResult] = []
    total = len(TEST_CASES)

    print(f"\nNEXUS Quality Metrics  --  {total} test cases\n{'-' * 60}")

    for i, case in enumerate(TEST_CASES, 1):
        print(f"[{i:2}/{total}] {case['domain']}")
        print(f"       Q: {case['query'][:70]}...")

        t0 = time.time()
        try:
            data = _call_chat(args.base_url, case["query"])
        except Exception as exc:
            print(f"       ERROR: {exc}\n")
            results.append(CaseResult(
                domain=case["domain"], query=case["query"],
                answer="", latency_ms=0, cache_hit=False, valid=False,
                checks=[CheckResult("request", False, str(exc))],
            ))
            continue

        elapsed_s = time.time() - t0
        checks = _run_checks(data["answer"], data["valid"])
        result = CaseResult(
            domain=case["domain"],
            query=case["query"],
            answer=data["answer"],
            latency_ms=data["latency_ms"],
            cache_hit=data["cache_hit"],
            valid=data["valid"],
            checks=checks,
        )
        results.append(result)

        status = "PASS" if result.passed else "FAIL"
        cache_tag = " [cached]" if data["cache_hit"] else f" [{elapsed_s:.0f}s]"
        print(f"       {status}  {result.score}/{result.total_checks} checks{cache_tag}")
        for c in checks:
            if not c.passed:
                print(f"         FAIL {c.name}: {c.detail}")
        print()

    # -- Summary --------------------------------------------------------------
    passed_cases = sum(1 for r in results if r.passed)
    total_check_score = sum(r.score for r in results)
    total_checks = sum(r.total_checks for r in results)
    cached_count = sum(1 for r in results if r.cache_hit)

    print("-" * 60)
    print(f"Cases passed     : {passed_cases}/{total} ({100*passed_cases//total}%)")
    print(f"Check score      : {total_check_score}/{total_checks} ({100*total_check_score//total_checks}%)")
    print(f"Cached responses : {cached_count}/{total}")
    print(f"Failed cases     :")
    for r in results:
        if not r.passed:
            fails = [c.name for c in r.checks if not c.passed]
            print(f"  - {r.domain}: {', '.join(fails)}")
    print("-" * 60)

    if args.output:
        report = {
            "summary": {
                "cases_passed": passed_cases,
                "total_cases": total,
                "check_score": total_check_score,
                "total_checks": total_checks,
                "cached": cached_count,
            },
            "cases": [
                {
                    "domain": r.domain,
                    "query": r.query,
                    "passed": r.passed,
                    "score": r.score,
                    "total": r.total_checks,
                    "latency_ms": r.latency_ms,
                    "cache_hit": r.cache_hit,
                    "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in r.checks],
                    "answer_preview": r.answer[:200],
                }
                for r in results
            ],
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    main()
