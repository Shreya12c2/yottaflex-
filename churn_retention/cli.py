
"""Command line entry point for the YottaFlex churn and retention pipeline."""

import argparse
import csv
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .generator import generate
from .validation import validate
from .metrics import build_metrics
from .storage import (
    export_tables,
    export_sql,
    write_sqlite
)


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, obj):
    """Write JSON and create parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2),
        encoding="utf-8"
    )


def hashes(directory: Path, filenames=None):
    """Calculate SHA-256 hashes for selected CSV files."""
    result = {}
    paths = (
        [directory / name for name in filenames]
        if filenames is not None
        else sorted(directory.glob("*.csv"))
    )

    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Expected reproducibility file is missing: {path}")
        result[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

    return result


def export_ground_truth(records: list, output_dir: Path):
    """Export anomaly labels separately from generated feature data."""
    output_dir.mkdir(parents=True, exist_ok=True)

    write_json(output_dir / "ground_truth.json", records)

    csv_path = output_dir / "ground_truth.csv"
    fieldnames = [
        "issue_id",
        "issue_type",
        "entity",
        "record_id",
        "expected_detection"
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def export_features(features: dict, output_dir: Path):
    """Export the pre-prediction feature snapshot separately."""

    output_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        features[customer_id]
        for customer_id in sorted(features)
    ]

    if not rows:
        raise ValueError("Feature dataset is empty.")

    csv_path = output_dir / "features.csv"
    json_path = output_dir / "features.json"

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(rows)

    write_json(json_path, rows)

    return rows


def write_source_manifest(
    path: Path,
    args,
    generated,
    tables,
    features,
    validation
):
    """Record synthetic data provenance and output inventory."""

    manifest = {
        "project": "YottaFlex Churn and Retention Pipeline",
        "manifest_version": "1.1",
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "data_provenance": {
            "data_type": "synthetic",
            "external_data_used": False,
            "source_description": (
                "Records are generated programmatically by the project's "
                "synthetic data generator. No external customer records "
                "or personally identifiable information are used."
            ),
            "generator_module": "churn_retention.generator",
            "random_seed": args.seed,
            "customer_count_requested": args.customers,
            "months_requested": args.months,
            "prediction_date": generated["prediction_date"],
            "horizon_end": generated["horizon_end"]
        },
        "generation_parameters": {
            "seed": args.seed,
            "customers": args.customers,
            "months": args.months
        },
        "tables": {
            name: {
                "record_count": len(rows),
                "csv_file": f"{name}.csv",
                "json_file": f"{name}.json"
            }
            for name, rows in tables.items()
        },
        "feature_snapshot": {
            "record_count": len(features),
            "csv_file": "data/generated/features.csv",
            "json_file": "data/generated/features.json",
            "prediction_date": generated["prediction_date"],
            "temporal_rule": (
                "Behavioral features are calculated using records dated "
                "strictly before the prediction date."
            ),
            "fields": list(features[0].keys()) if features else []
        },
        "ground_truth": {
            "csv_file": "data/ground_truth/ground_truth.csv",
            "json_file": "data/ground_truth/ground_truth.json",
            "record_count": len(generated["ground_truth"]),
            "purpose": (
                "Contains labels for deliberately injected data-quality "
                "anomalies. It is separate from model input features."
            )
        },
        "validation": {
            "issue_count": validation["issue_count"],
            "passed": validation["passed"],
            "detected_issue_types": sorted({
                issue["issue_type"]
                for issue in validation.get("issues", [])
            })
        },
        "database": {
            "sqlite_file": "outputs/churn_retention.db",
            "schema_file": "outputs/schema.sql",
            "seed_file": "outputs/seed_data.sql"
        },
        "limitations": [
            "The dataset is synthetic and does not represent real customers.",
            "Retention and churn outcomes are simulated using generator rules.",
            "Experiment metrics are illustrative and do not establish "
            "real-world causal effectiveness.",
            "The feature snapshot contains pre-prediction behavioral "
            "features; ground-truth anomaly labels are not included."
        ]
    }

    write_json(path, manifest)


def run(args):
    """Generate data, validate, export and report."""

    generated = generate(
        args.customers,
        args.months,
        args.seed
    )

    data_dir = Path(args.data_dir)
    gt_dir = Path(args.ground_truth_dir)
    out_dir = Path(args.output_dir)
    reports_dir = out_dir / "reports"

    tables = generated["tables"]

    # Export all eleven entity tables, including subscription history.
    export_tables(tables, data_dir)

    # Export pre-prediction features separately.
    feature_rows = export_features(
        generated["features"],
        data_dir
    )

    # Export anomaly ground truth separately from feature data.
    export_ground_truth(generated["ground_truth"], gt_dir)

    # Validate generated entity tables.
    validation = validate(tables)

    # Calculate business and experiment metrics.
    metrics = build_metrics(
        tables,
        validation,
        args.customers
    )

    # Create SQLite and standalone SQL exports.
    write_sqlite(
        tables,
        out_dir / "churn_retention.db"
    )

    export_sql(
        tables,
        out_dir
    )

    # Validation report.
    write_json(
        reports_dir / "validation.json",
        validation
    )

    # Summary report.
    write_json(
        reports_dir / "summary.json",
        {
            "seed": args.seed,
            "months": args.months,
            "prediction_date": generated["prediction_date"],
            "horizon_end": generated["horizon_end"],
            "row_counts": {
                name: len(rows)
                for name, rows in tables.items()
            },
            "feature_rows": len(feature_rows),
            "metrics": metrics
        }
    )

    # Experiment report.
    write_json(
        reports_dir / "experiment_report.json",
        metrics
    )

    # Source and provenance manifest.
    write_source_manifest(
        reports_dir / "source_manifest.json",
        args,
        generated,
        tables,
        feature_rows,
        validation
    )

    # Optional same-seed reproducibility check.
    if args.verify_reproducibility:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)

            second_run = generate(
                args.customers,
                args.months,
                args.seed
            )

            export_tables(
                second_run["tables"],
                temp
            )

            export_features(
                second_run["features"],
                temp
            )

            temp_gt_dir = temp / "ground_truth"
            export_ground_truth(
                second_run["ground_truth"],
                temp_gt_dir
            )

            expected_data_csvs = [
                f"{name}.csv"
                for name, rows in second_run["tables"].items()
                if rows
            ] + ["features.csv"]

            reproducible = (
                hashes(data_dir, expected_data_csvs)
                == hashes(temp, expected_data_csvs)
                and hashes(gt_dir, ["ground_truth.csv"])
                == hashes(temp_gt_dir, ["ground_truth.csv"])
            )

        write_json(
            reports_dir / "reproducibility.json",
            {
                "same_seed_identical_csv_hashes": reproducible
            }
        )

        if not reproducible:
            raise SystemExit("Reproducibility check failed")

    print(
        f"Generated {args.customers:,} customers "
        f"across {args.months} months."
    )
    print(f"Prediction date: {generated['prediction_date']}")
    print(f"Feature rows exported: {len(feature_rows):,}")
    print(
        f"Validation found {validation['issue_count']} issue(s), "
        "including the intentionally injected cases."
    )
    print(f"SQLite database: {out_dir / 'churn_retention.db'}")
    print(f"SQL schema: {out_dir / 'schema.sql'}")
    print(f"SQL seed data: {out_dir / 'seed_data.sql'}")
    print(
        f"Source manifest: "
        f"{reports_dir / 'source_manifest.json'}"
    )
    print(f"Summary report: {reports_dir / 'summary.json'}")


def validate_existing(args):
    """Validate existing generated CSV entity tables."""

    data = {}

    table_names = [
        "customers",
        "subscriptions",
        "subscription_history",
        "usage_snapshots",
        "billing_events",
        "support_cases",
        "offers",
        "eligibility_rules",
        "campaign_contacts",
        "churn_outcomes",
        "retention_outcomes"
    ]

    for name in table_names:
        path = Path(args.data_dir) / f"{name}.csv"

        if not path.exists():
            raise SystemExit(f"Missing required file: {path}")

        with path.open(
            encoding="utf-8",
            newline=""
        ) as file:
            data[name] = list(csv.DictReader(file))

    result = validate(data)

    print(json.dumps(result, indent=2))

    raise SystemExit(
        0 if result["passed"] else 1
    )


def main():
    parser = argparse.ArgumentParser(
        description="YottaFlex churn and retention pipeline"
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True
    )

    run_parser = sub.add_parser(
        "run",
        help="generate data, validate, export and report"
    )

    run_parser.add_argument(
        "--customers",
        type=int,
        default=500
    )
    run_parser.add_argument(
        "--months",
        type=int,
        default=18
    )
    run_parser.add_argument(
        "--seed",
        type=int,
        default=20261022
    )
    run_parser.add_argument(
        "--data-dir",
        default=str(ROOT / "data" / "generated")
    )
    run_parser.add_argument(
        "--ground-truth-dir",
        default=str(ROOT / "data" / "ground_truth")
    )
    run_parser.add_argument(
        "--output-dir",
        default=str(ROOT / "outputs")
    )
    run_parser.add_argument(
        "--verify-reproducibility",
        action="store_true"
    )

    run_parser.set_defaults(func=run)

    validate_parser = sub.add_parser(
        "validate",
        help="validate existing generated CSV tables"
    )

    validate_parser.add_argument(
        "--data-dir",
        default=str(ROOT / "data" / "generated")
    )

    validate_parser.set_defaults(
        func=validate_existing
    )

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
