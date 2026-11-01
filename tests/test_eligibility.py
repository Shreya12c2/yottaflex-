import unittest

from churn_retention.eligibility import (
    evaluate_offer_eligibility
)


class OfferEligibilityTests(unittest.TestCase):

    def setUp(self):
        self.offers = [
            {
                "offer_id": "OFF-2026-000001",
                "offer_type": "discount",
                "estimated_cost": 3.0,
                "active": True
            },
            {
                "offer_id": "OFF-2026-000002",
                "offer_type": "bonus_data",
                "estimated_cost": 5.0,
                "active": True
            },
            {
                "offer_id": "OFF-2026-000003",
                "offer_type": "loyalty_credit",
                "estimated_cost": 8.0,
                "active": True
            }
        ]

    def test_basic_customer_gets_affordable_offer(self):

        result = evaluate_offer_eligibility(
            customer_id="CUS-000001",
            subscription_status="active",
            risk_score=65,
            monthly_fee=25.0,
            offers=self.offers,
            evaluation_date="2026-07-01"
        )

        self.assertTrue(result["eligible"])
        self.assertEqual(
            result["selected_offer_id"],
            "OFF-2026-000001"
        )
        self.assertLessEqual(
            result["selected_offer_cost"],
            result["maximum_allowed_offer_cost"]
        )
        self.assertEqual(result["rule_id"], "RULE-2026-000001")
        self.assertEqual(result["minimum_required_risk_score"], 35)
        self.assertGreaterEqual(result["monthly_margin"], 0)
        self.assertGreaterEqual(result["max_cost_margin_pct"], 0)
        self.assertTrue(result["decision_reasons"])

    def test_standard_customer_gets_affordable_offer(self):

        result = evaluate_offer_eligibility(
            customer_id="CUS-000002",
            subscription_status="active",
            risk_score=70,
            monthly_fee=45.0,
            offers=self.offers,
            evaluation_date="2026-07-01"
        )

        self.assertTrue(result["eligible"])
        self.assertEqual(
            result["selected_offer_id"],
            "OFF-2026-000002"
        )

    def test_premium_customer_gets_highest_affordable_offer(self):

        result = evaluate_offer_eligibility(
            customer_id="CUS-000003",
            subscription_status="active",
            risk_score=80,
            monthly_fee=70.0,
            offers=self.offers,
            evaluation_date="2026-07-01"
        )

        self.assertTrue(result["eligible"])
        self.assertEqual(
            result["selected_offer_id"],
            "OFF-2026-000003"
        )

    def test_low_risk_customer_is_rejected(self):

        result = evaluate_offer_eligibility(
            customer_id="CUS-000004",
            subscription_status="active",
            risk_score=20,
            monthly_fee=70.0,
            offers=self.offers,
            evaluation_date="2026-07-01"
        )

        self.assertFalse(result["eligible"])
        self.assertIn(
            "risk_score_below_threshold",
            result["decision_reasons"]
        )
        self.assertEqual(result["selected_offer_id"], None)
        self.assertEqual(result["rule_id"], "RULE-2026-000001")

    def test_inactive_subscription_is_rejected(self):

        result = evaluate_offer_eligibility(
            customer_id="CUS-000005",
            subscription_status="cancelled",
            risk_score=80,
            monthly_fee=70.0,
            offers=self.offers,
            evaluation_date="2026-07-01"
        )

        self.assertFalse(result["eligible"])
        self.assertIn(
            "subscription_not_active",
            result["decision_reasons"]
        )

    def test_recent_offer_contact_triggers_cooldown(self):

        result = evaluate_offer_eligibility(
            customer_id="CUS-000006",
            subscription_status="active",
            risk_score=80,
            monthly_fee=70.0,
            offers=self.offers,
            evaluation_date="2026-07-01",
            previous_contact_date="2026-06-15"
        )

        self.assertFalse(result["eligible"])
        self.assertIn(
            "offer_cooldown_active",
            result["decision_reasons"]
        )

    def test_inactive_offers_are_not_selected(self):

        inactive_offers = [
            {
                "offer_id": "OFF-2026-000004",
                "offer_type": "discount",
                "estimated_cost": 2.0,
                "active": False
            }
        ]

        result = evaluate_offer_eligibility(
            customer_id="CUS-000007",
            subscription_status="active",
            risk_score=80,
            monthly_fee=70.0,
            offers=inactive_offers,
            evaluation_date="2026-07-01"
        )

        self.assertFalse(result["eligible"])
        self.assertIn(
            "no_offer_within_margin_limit",
            result["decision_reasons"]
        )

    def test_offer_cost_never_exceeds_margin_limit(self):

        result = evaluate_offer_eligibility(
            customer_id="CUS-000008",
            subscription_status="active",
            risk_score=90,
            monthly_fee=45.0,
            offers=self.offers,
            evaluation_date="2026-07-01"
        )

        if result["eligible"]:
            self.assertLessEqual(
                result["selected_offer_cost"],
                result["maximum_allowed_offer_cost"]
            )

    def test_future_previous_contact_date_is_rejected(self):

        with self.assertRaises(ValueError):
            evaluate_offer_eligibility(
                customer_id="CUS-000009",
                subscription_status="active",
                risk_score=80,
                monthly_fee=70.0,
                offers=self.offers,
                evaluation_date="2026-07-01",
                previous_contact_date="2026-08-01"
            )


if __name__ == "__main__":
    unittest.main()