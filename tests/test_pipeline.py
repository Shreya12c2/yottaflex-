import sqlite3
import tempfile
import unittest
from pathlib import Path

from churn_retention.generator import generate
from churn_retention.validation import validate
from churn_retention.metrics import build_metrics
from churn_retention.storage import export_sql, write_sqlite


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse one deterministic, representative dataset across pipeline tests.
        cls.generated = generate(500, 18, 20261022)
        cls.tables = cls.generated["tables"]
        cls.validation = validate(cls.tables)

    def test_fixed_seed_reproducible(self):
        second = generate(500, 18, 20261022)
        self.assertEqual(self.tables, second["tables"])
        self.assertEqual(
            self.generated["ground_truth"],
            second["ground_truth"]
        )

    def test_expected_entities_and_relationships(self):
        self.assertEqual(len(self.tables["customers"]), 500)
        customer_ids = {row["customer_id"] for row in self.tables["customers"]}
        subscription_ids = {
            row["subscription_id"] for row in self.tables["subscriptions"]
        }
        self.assertEqual(len(self.tables), 11)
        self.assertTrue(all(
            row["customer_id"] in customer_ids
            for row in self.tables["subscriptions"]
        ))
        self.assertTrue(all(
            row["subscription_id"] in subscription_ids
            for row in self.tables["usage_snapshots"]
        ))

    def test_four_anomaly_types_documented_and_detected(self):
        expected = {
            "churn_before_prediction",
            "offer_to_ineligible_customer",
            "treatment_control_leakage",
            "multiple_offer_attribution",
        }
        truth_types = {
            row["issue_type"] for row in self.generated["ground_truth"]
        }
        detected_types = {
            row["issue_type"] for row in self.validation["issues"]
        }
        self.assertEqual(truth_types, expected)
        self.assertEqual(detected_types, expected)
        self.assertEqual(self.validation["issue_count"], 4)

    def test_campaign_contacts_retain_eligibility_trace(self):
        required = {
            "rule_id",
            "minimum_required_risk_score",
            "monthly_margin",
            "maximum_allowed_offer_cost",
            "max_cost_margin_pct",
            "decision_reasons",
        }
        self.assertTrue(self.tables["campaign_contacts"])
        for contact in self.tables["campaign_contacts"]:
            self.assertTrue(required.issubset(contact))
            self.assertTrue(contact["rule_id"])
            self.assertTrue(contact["decision_reasons"])

    def test_retention_outcomes_record_offer_response(self):
        self.assertTrue(self.tables["retention_outcomes"])
        for outcome in self.tables["retention_outcomes"]:
            self.assertIn(outcome["offer_responded"], (True, False))

    def test_metrics_exclude_group_leakage_and_count_responded_cost(self):
        metrics = build_metrics(
            self.tables, self.validation, len(self.tables["customers"])
        )
        self.assertGreater(metrics["experiment"]["treatment"]["customers"], 0)
        self.assertGreater(metrics["experiment"]["control"]["customers"], 0)
        self.assertEqual(
            metrics["metric_quality"]["experiment_customers_excluded_for_group_leakage"],
            2,
        )
        self.assertGreaterEqual(metrics["realized_offer_cost_total"], 0)
        self.assertIn(
            "nonresponse_outcomes_excluded_from_offer_cost",
            metrics["metric_quality"],
        )

    def test_sqlite_and_standalone_sql_exports(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "test.db"
            sql_dir = root / "sql"
            write_sqlite(self.tables, db_path)
            export_sql(self.tables, sql_dir)

            connection = sqlite3.connect(db_path)
            try:
                self.assertEqual(
                    connection.execute("PRAGMA integrity_check").fetchone()[0],
                    "ok",
                )
                self.assertEqual(
                    connection.execute("PRAGMA foreign_key_check").fetchall(),
                    [],
                )
                contact_columns = {
                    row[1] for row in connection.execute(
                        "PRAGMA table_info(campaign_contacts)"
                    )
                }
                self.assertTrue({
                    "rule_id",
                    "minimum_required_risk_score",
                    "monthly_margin",
                    "maximum_allowed_offer_cost",
                    "max_cost_margin_pct",
                    "decision_reasons",
                }.issubset(contact_columns))
                retention_columns = {
                    row[1] for row in connection.execute(
                        "PRAGMA table_info(retention_outcomes)"
                    )
                }
                self.assertIn("offer_responded", retention_columns)
            finally:
                connection.close()

            self.assertTrue((sql_dir / "schema.sql").exists())
            self.assertTrue((sql_dir / "seed_data.sql").exists())


if __name__ == "__main__":
    unittest.main()
