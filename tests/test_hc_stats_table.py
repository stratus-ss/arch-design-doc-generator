"""Public-contract tests for HC §5.3 category summary arithmetic."""
from __future__ import annotations

from hc_report.models import CheckResult
from hc_report.renderer import _build_stats_rows

# Bug: §5.3 category row PASS+WARNING+FAIL+INFO+N/A does not equal Total
# Mutant: omit INFO from the row, or emit Total as the first number
# Contract: public


def _check(status: str, index: int) -> CheckResult:
    return CheckResult(
        category_id="7.1",
        category_name="Base Platform Checks",
        check_id=f"7.1.sample.{index}",
        description=status,
        status=status,
        evidence=status,
    )


def test_stats_rows_status_columns_sum_to_total() -> None:
    checks = [
        _check("PASS", 1),
        _check("PASS", 2),
        _check("WARNING", 3),
        _check("INFO", 4),
        _check("NOT_APPLICABLE", 5),
        _check("SKIPPED", 6),
    ]
    row = _build_stats_rows(checks).splitlines()[0]
    cells = row.strip("|").split("|")
    numbers: list[int] = []
    for cell in cells[1:]:
        numbers.append(int(cell.strip()))
    assert len(numbers) == 6
    pass_count, warning_count, fail_count, info_count, skipped_count, total = numbers
    assert info_count == 1
    assert skipped_count == 2
    assert total == 6
    assert pass_count + warning_count + fail_count + info_count + skipped_count == total
