#!/usr/bin/env python3
"""Compare normalized Quantik API portability reports.

The comparator intentionally ignores implementation metadata. It compares the
contract release, contract IDs, and per-case behavior emitted by each stack.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPORT_SCHEMA = "api-portability-report.v1"


def fail(message: str) -> None:
    raise ValueError(message)


def load_report(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        report = json.load(handle)
    if not isinstance(report, dict):
        fail(f"{path}: report must be a JSON object")
    if report.get("schema") != REPORT_SCHEMA:
        fail(f"{path}: schema must be {REPORT_SCHEMA}")
    if not isinstance(report.get("contracts_release"), str):
        fail(f"{path}: contracts_release must be a string")
    if not isinstance(report.get("contract_ids"), dict):
        fail(f"{path}: contract_ids must be an object")
    cases = report.get("cases")
    if not isinstance(cases, list) or not cases:
        fail(f"{path}: cases must be a non-empty list")
    seen: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            fail(f"{path}: cases[{index}] must be an object")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            fail(f"{path}: cases[{index}].case_id must be a non-empty string")
        if case_id in seen:
            fail(f"{path}: duplicate case_id {case_id}")
        seen.add(case_id)
    return report


def comparable(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "contracts_release": report["contracts_release"],
        "contract_ids": report["contract_ids"],
        "cases": sorted(report["cases"], key=lambda case: case["case_id"]),
    }


def compare_reports(paths: list[Path]) -> None:
    if len(paths) < 2:
        fail("at least two reports are required")
    reports = [(path, comparable(load_report(path))) for path in paths]
    baseline_path, baseline = reports[0]
    for path, candidate in reports[1:]:
        if candidate["contracts_release"] != baseline["contracts_release"]:
            fail(
                f"{path}: contracts_release {candidate['contracts_release']} "
                f"does not match {baseline_path} {baseline['contracts_release']}"
            )
        if candidate["contract_ids"] != baseline["contract_ids"]:
            fail(f"{path}: contract_ids do not match {baseline_path}")

        baseline_cases = {case["case_id"]: case for case in baseline["cases"]}
        candidate_cases = {case["case_id"]: case for case in candidate["cases"]}
        if set(candidate_cases) != set(baseline_cases):
            fail(f"{path}: case_id set does not match {baseline_path}")
        for case_id, baseline_case in baseline_cases.items():
            candidate_case = candidate_cases[case_id]
            if candidate_case != baseline_case:
                fail(f"{path}: case {case_id} does not match {baseline_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        compare_reports(args.reports)
    except Exception as exc:
        print(f"api portability report comparison failed: {exc}")
        return 1
    print(f"api portability reports match: {len(args.reports)} reports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
