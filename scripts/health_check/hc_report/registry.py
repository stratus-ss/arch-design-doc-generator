"""Registry-driven check evaluation pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from hc_report.evaluators._common import _CATEGORY_MAP
from hc_report.evaluators.components import evaluate_components
from hc_report.evaluators.day2 import evaluate_day2
from hc_report.evaluators.hardware import evaluate_hardware
from hc_report.evaluators.health import evaluate_cluster_health
from hc_report.evaluators.layered import evaluate_layered
from hc_report.evaluators.metrics import evaluate_metrics
from hc_report.evaluators.platform import evaluate_base_platform
from hc_report.evaluators.security import evaluate_security
from hc_report.evaluators.topology import evaluate_topology
from hc_report.models import CheckResult


@dataclass(frozen=True)
class CategoryEvaluatorSpec:
    """Defines one category evaluator in the check registry."""

    category_key: str
    evaluator: Callable[[dict, dict, str, str], list[CheckResult]]
    source: str = "deterministic"
    tags: tuple[str, ...] = field(default_factory=tuple)


def get_core_registry() -> tuple[CategoryEvaluatorSpec, ...]:
    """Return the canonical ordered list of deterministic category evaluators."""
    return (
        CategoryEvaluatorSpec("03_base_platform", evaluate_base_platform),
        CategoryEvaluatorSpec("04_topology", evaluate_topology),
        CategoryEvaluatorSpec("05_components", evaluate_components),
        CategoryEvaluatorSpec("06_layered", evaluate_layered),
        CategoryEvaluatorSpec("07_cluster_health", evaluate_cluster_health),
        CategoryEvaluatorSpec("08_day2", evaluate_day2),
        CategoryEvaluatorSpec("09_security", evaluate_security),
        CategoryEvaluatorSpec("10_metrics", evaluate_metrics),
        CategoryEvaluatorSpec("11_hardware", evaluate_hardware),
    )


def evaluate_from_registry(results: dict, registry: tuple[CategoryEvaluatorSpec, ...] | None = None) -> list[CheckResult]:
    """Evaluate checks using registry metadata and ordered evaluator specs."""
    specs = registry or get_core_registry()
    checks: list[CheckResult] = []

    for evaluator_spec in specs:
        category_id, category_name = _CATEGORY_MAP[evaluator_spec.category_key]
        category_data = results.get(evaluator_spec.category_key, {})
        if not category_data:
            checks.append(
                CheckResult(
                    category_id=category_id,
                    category_name=category_name,
                    check_id=f"{category_id}.category",
                    description=f"{category_name} (all)",
                    status="SKIPPED",
                    evidence="Category not collected",
                    source=evaluator_spec.source,
                    tags=list(evaluator_spec.tags),
                )
            )
            continue

        category_checks = evaluator_spec.evaluator(
            category_data, results, category_id, category_name,
        )
        for check_result in category_checks:
            if not check_result.source:
                check_result.source = evaluator_spec.source
            if not check_result.tags and evaluator_spec.tags:
                check_result.tags = list(evaluator_spec.tags)
        checks.extend(category_checks)

    return checks
