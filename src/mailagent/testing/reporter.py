"""Test result formatting and terminal output."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field


@dataclass
class TestResult:
    name: str
    passed: bool
    details: list[str] = field(default_factory=list)
    sub_results: list[TestResult] | None = None


def print_report(
    mode: str,
    inbox: str,
    results: list[TestResult],
    extra_footer: str | None = None,
) -> None:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    out = sys.stdout
    out.write(f"\nmailagent test {mode} — {total} tests, inbox: {inbox}\n\n")

    for result in results:
        mark = "\u2713" if result.passed else "\u2717"
        out.write(f"  {mark} {result.name}\n")
        for line in result.details:
            out.write(f"    {line}\n")

        if result.sub_results:
            sub_passed = sum(1 for s in result.sub_results if s.passed)
            sub_total = len(result.sub_results)
            mark_batch = "\u2713" if sub_passed == sub_total else "\u2717"
            # Rewrite header for batch
            # Already printed above; just show sub-results
            for i, sub in enumerate(result.sub_results, 1):
                sub_mark = "\u2713" if sub.passed else "\u2717"
                detail = sub.details[0] if sub.details else ""
                out.write(f"    #{i} {detail} {sub_mark}\n")

        out.write("\n")

    separator = "\u2501" * 50
    out.write(f"{separator}\n")
    out.write(f"Results: {passed} passed, {failed} failed\n")
    if extra_footer:
        out.write(extra_footer + "\n")
    out.write(f"{separator}\n")
