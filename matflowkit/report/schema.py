"""Versioned report schema factories."""


def deepmd_dataset_schema() -> dict:
    return {
        "schema_version": "1.0",
        "report_type": "deepmd_dataset",
        "dataset": {
            "format": "deepmd_npy",
            "systems": None,
            "frames": None,
            "elements": [],
        },
        "properties": {"energy": {}, "force": {}, "virial": {}},
        "composition": {},
        "duplicates": {},
        "warnings": [],
    }


def abacus_tasks_schema() -> dict:
    return {
        "schema_version": "1.0",
        "report_type": "abacus_tasks",
        "root": None,
        "summary": {
            "tasks": None,
            "pass": None,
            "incomplete": None,
            "expected": None,
            "expected_match": None,
            "calculations": {},
        },
        "jobs": [],
        "figures": {},
        "warnings": [],
    }
