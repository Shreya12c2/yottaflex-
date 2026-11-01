
"""CSV, JSON, SQL and SQLite export utilities."""

import csv
import json
import sqlite3
from pathlib import Path


# Shared schema used by both SQLite and standalone SQL exports.
SCHEMA = {
    "customers": """
        customer_id TEXT PRIMARY KEY,
        signup_date TEXT,
        region TEXT,
        segment TEXT,
        acquisition_channel TEXT,
        seasonal_user INTEGER
    """,
    "subscriptions": """
        subscription_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL REFERENCES customers(customer_id),
        plan TEXT,
        monthly_fee REAL,
        status TEXT,
        start_date TEXT,
        end_date TEXT
    """,
    "subscription_history": """
        history_id TEXT PRIMARY KEY,
        subscription_id TEXT NOT NULL REFERENCES subscriptions(subscription_id),
        event_type TEXT NOT NULL,
        previous_plan TEXT,
        new_plan TEXT,
        previous_fee REAL,
        new_fee REAL,
        previous_status TEXT,
        new_status TEXT,
        effective_date TEXT NOT NULL
    """,
    "usage_snapshots": """
        snapshot_id TEXT PRIMARY KEY,
        subscription_id TEXT NOT NULL REFERENCES subscriptions(subscription_id),
        month TEXT,
        data_gb REAL,
        sessions INTEGER,
        active_days INTEGER
    """,
    "billing_events": """
        billing_event_id TEXT PRIMARY KEY,
        subscription_id TEXT NOT NULL REFERENCES subscriptions(subscription_id),
        event_date TEXT,
        event_type TEXT,
        amount REAL,
        status TEXT
    """,
    "support_cases": """
        support_case_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL REFERENCES customers(customer_id),
        opened_at TEXT,
        category TEXT,
        priority TEXT,
        status TEXT,
        resolution_hours REAL
    """,
    "offers": """
        offer_id TEXT PRIMARY KEY,
        offer_type TEXT,
        discount_pct REAL,
        duration_months INTEGER,
        estimated_cost REAL,
        active INTEGER
    """,
    "eligibility_rules": """
        rule_id TEXT PRIMARY KEY,
        min_risk_score INTEGER,
        max_cost_margin_pct REAL,
        active_only INTEGER,
        cooldown_days INTEGER
    """,
    "campaign_contacts": """
        contact_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL REFERENCES customers(customer_id),
        offer_id TEXT NOT NULL REFERENCES offers(offer_id),
        group_name TEXT,
        contact_date TEXT,
        eligibility_status TEXT,
        risk_score_at_contact INTEGER,
        estimated_cost REAL,
        campaign_id TEXT,
        rule_id TEXT,
        minimum_required_risk_score INTEGER,
        monthly_margin REAL,
        maximum_allowed_offer_cost REAL,
        max_cost_margin_pct REAL,
        decision_reasons TEXT
    """,
    "churn_outcomes": """
        churn_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL REFERENCES customers(customer_id),
        prediction_date TEXT,
        horizon_end TEXT,
        churned INTEGER,
        churn_type TEXT,
        churn_date TEXT,
        baseline_churn_propensity REAL
    """,
    "retention_outcomes": """
        retention_id TEXT PRIMARY KEY,
        contact_id TEXT NOT NULL REFERENCES campaign_contacts(contact_id),
        customer_id TEXT NOT NULL REFERENCES customers(customer_id),
        retained INTEGER,
        realized_offer_cost REAL,
        outcome_date TEXT,
        offer_responded INTEGER
    """
}


# Maps generated field names to database column names.
COLUMN_MAP = {
    "campaign_contacts": {
        "group": "group_name"
    }
}


def database_columns(table_name, rows):
    """Return source field names and corresponding database column names."""
    source_columns = list(rows[0].keys())
    mapping = COLUMN_MAP.get(table_name, {})
    database_names = [mapping.get(column, column) for column in source_columns]
    return source_columns, database_names


def sql_literal(value):
    """Convert a Python value into a safe SQL literal."""
    if value is None:
        return "NULL"

    if isinstance(value, bool):
        return "1" if value else "0"

    if isinstance(value, (int, float)):
        return str(value)

    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def export_tables(tables: dict, output_dir: Path):
    """Export generated tables to CSV and JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, rows in tables.items():
        if not rows:
            continue

        with (output_dir / f"{name}.csv").open(
            "w", newline="", encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        with (output_dir / f"{name}.json").open(
            "w", encoding="utf-8"
        ) as file:
            json.dump(rows, file, indent=2)


def export_sql(tables: dict, output_dir: Path):
    """Export standalone SQL schema and seed-data scripts."""
    output_dir.mkdir(parents=True, exist_ok=True)

    schema_path = output_dir / "schema.sql"
    seed_path = output_dir / "seed_data.sql"

    schema_lines = [
        "-- YottaFlex churn and retention database schema",
        "-- Generated from the project data model.",
        "",
        "PRAGMA foreign_keys = ON;",
        ""
    ]

    # Drop child tables before parent tables.
    table_order = list(SCHEMA.keys())
    for table_name in reversed(table_order):
        schema_lines.append(f"DROP TABLE IF EXISTS {table_name};")

    schema_lines.append("")

    for table_name, definition in SCHEMA.items():
        schema_lines.append(
            f"CREATE TABLE {table_name} ({definition.strip()});"
        )

    schema_lines.append("")

    schema_path.write_text(
        "\n".join(schema_lines),
        encoding="utf-8"
    )

    seed_lines = [
        "-- YottaFlex churn and retention generated seed data",
        "-- Execute schema.sql before this file.",
        "",
        "PRAGMA foreign_keys = ON;",
        "BEGIN TRANSACTION;",
        ""
    ]

    # Parent tables are inserted before dependent tables.
    for table_name in table_order:
        rows = tables.get(table_name, [])

        if not rows:
            continue

        source_columns, database_names = database_columns(
            table_name, rows
        )

        columns_sql = ", ".join(database_names)

        seed_lines.append(f"-- {table_name}: {len(rows)} records")

        for row in rows:
            values_sql = ", ".join(
                sql_literal(row.get(column))
                for column in source_columns
            )

            seed_lines.append(
                f"INSERT INTO {table_name} ({columns_sql}) "
                f"VALUES ({values_sql});"
            )

        seed_lines.append("")

    seed_lines.extend([
        "COMMIT;",
        ""
    ])

    seed_path.write_text(
        "\n".join(seed_lines),
        encoding="utf-8"
    )


def write_sqlite(tables: dict, db_path: Path):
    """Create a SQLite database and insert all generated records."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        db_path.unlink()

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")

    try:
        for table_name, definition in SCHEMA.items():
            con.execute(
                f"CREATE TABLE {table_name} ({definition})"
            )

        # Insert parent tables before dependent tables.
        for table_name in SCHEMA:
            rows = tables.get(table_name, [])

            if not rows:
                continue

            source_columns, database_names = database_columns(
                table_name, rows
            )

            placeholders = ",".join("?" for _ in source_columns)
            columns_sql = ",".join(database_names)

            insert_sql = (
                f"INSERT INTO {table_name} "
                f"({columns_sql}) VALUES ({placeholders})"
            )

            values = [
                tuple(
                    int(value) if isinstance(value, bool) else value
                    for value in (
                        row.get(column) for column in source_columns
                    )
                )
                for row in rows
            ]

            con.executemany(insert_sql, values)

        con.commit()

        # Confirm SQLite accepted all records and foreign keys.
        foreign_key_errors = con.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if foreign_key_errors:
            raise RuntimeError(
                f"SQLite foreign-key check failed: {foreign_key_errors[:5]}"
            )

    finally:
        con.close()
