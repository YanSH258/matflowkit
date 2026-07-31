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
