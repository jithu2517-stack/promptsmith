from __future__ import annotations

import re
from typing import Any

from promptsmith.models.types import TestCase, TestResult, RunResult


def evaluate_test_case(
    test_case: TestCase,
    run_result: RunResult,
) -> TestResult:
    """Evaluate a single test case against a run result."""
    checks: list[dict[str, Any]] = []
    passed = True

    if run_result.error:
        return TestResult(
            test_name=test_case.name,
            prompt_name=run_result.prompt_name,
            passed=False,
            checks=[{"check": "no_error", "passed": False, "message": run_result.error}],
            error=run_result.error,
        )

    response = run_result.response_text

    for pattern in test_case.expected_patterns:
        match = bool(re.search(pattern, response, re.IGNORECASE | re.DOTALL))
        checks.append(
            {
                "check": "expected_pattern",
                "pattern": pattern,
                "passed": match,
                "message": "Found" if match else "Not found",
            }
        )
        if not match:
            passed = False

    for pattern in test_case.forbidden_patterns:
        match = bool(re.search(pattern, response, re.IGNORECASE | re.DOTALL))
        checks.append(
            {
                "check": "forbidden_pattern",
                "pattern": pattern,
                "passed": not match,
                "message": "Found (forbidden)" if match else "Not found",
            }
        )
        if match:
            passed = False

    if test_case.min_tokens > 0:
        enough = run_result.tokens_output >= test_case.min_tokens
        checks.append(
            {
                "check": "min_tokens",
                "expected": test_case.min_tokens,
                "actual": run_result.tokens_output,
                "passed": enough,
                "message": f"{run_result.tokens_output} >= {test_case.min_tokens}" if enough else f"{run_result.tokens_output} < {test_case.min_tokens}",
            }
        )
        if not enough:
            passed = False

    if test_case.max_tokens > 0:
        within = run_result.tokens_output <= test_case.max_tokens
        checks.append(
            {
                "check": "max_tokens",
                "expected": test_case.max_tokens,
                "actual": run_result.tokens_output,
                "passed": within,
                "message": f"{run_result.tokens_output} <= {test_case.max_tokens}" if within else f"{run_result.tokens_output} > {test_case.max_tokens}",
            }
        )
        if not within:
            passed = False

    return TestResult(
        test_name=test_case.name,
        prompt_name=run_result.prompt_name,
        passed=passed,
        checks=checks,
        run_result=run_result,
    )
