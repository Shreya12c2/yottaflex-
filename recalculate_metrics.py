"""Recalculate reports from existing generated CSV files without regeneration."""

import csv
import json
from pathlib import Path

from churn_retention.metrics import build_metrics
from churn_retention.validation import validate


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "generated"
REPORTS_DIR = ROOT / "outputs" / "reports"

TABLE_NAMES = [
    "customers",
    "subscriptions",
    "usage_snapshots",
    "billing_events",
    "support_cases",
    "offers",
    "eligibility_rules",
    "campaign_contacts",
    "churn_outcomes",
    "retention_outcomes",
    "subscription_history",
]


def read_csv(path):
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def main():
    tables = {}
    for name in TABLE_NAMES:
        path = DATA_DIR / f"{name}.csv"
        if not path.exists():
            raise SystemExit(f"Required existing data file is missing: {path}")
        tables[name] = read_csv(path)

    # Read existing metadata first, so unrelated summary fields are preserved.
    summary_path = REPORTS_DIR / "summary.json"
    if not summary_path.exists():
        raise SystemExit(
            f"Existing summary report not found: {summary_path}. "
            "No reports were changed."
        )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    customer_count = len(tables["customers"])

    validation = validate(tables)
    metrics = build_metrics(tables, validation, customer_count)

    summary["row_counts"] = {
        name: len(rows) for name, rows in tables.items()
    }
    summary["metrics"] = metrics

    write_json(REPORTS_DIR / "validation.json", validation)
    write_json(REPORTS_DIR / "experiment_report.json", metrics)
    write_json(summary_path, summary)

    print("Metrics recalculated from existing CSV files.")
    print("The data generator was NOT called.")
    print(f"Customers loaded: {customer_count:,}")
    print(f"Valid churn outcomes: {metrics['metric_quality']['valid_churn_outcomes']:,}")
    print(f"Overall observed churn rate: {metrics['overall_observed_churn_rate']}")
    print(f"Treatment retention: {metrics['experiment']['treatment']['retention_rate']}")
    print(f"Control retention: {metrics['experiment']['control']['retention_rate']}")
    print(f"Incremental retention lift: {metrics['incremental_retention_lift']}")
    print(f"Realized offer cost total: {metrics['realized_offer_cost_total']}")
    print(f"Validation issues: {validation['issue_count']}")
    print(f"Updated reports in: {REPORTS_DIR}")


if __name__ == "__main__":
    main()
