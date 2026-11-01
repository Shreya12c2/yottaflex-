
"""Deterministic synthetic data generation for the churn-retention exercise."""

from __future__ import annotations

from datetime import date, timedelta
from calendar import monthrange
import random

from .eligibility import evaluate_offer_eligibility


PLANS = {
    "Basic": 25.0,
    "Standard": 45.0,
    "Premium": 70.0
}

REGIONS = ["North", "South", "East", "West"]
SEGMENTS = ["consumer", "small_business", "enterprise"]
CHANNELS = ["organic", "referral", "paid", "partner"]

SUPPORT_CATEGORIES = [
    "billing", "technical", "cancellation", "product"
]


def add_months(d: date, n: int) -> date:
    """Add calendar months to a date."""
    month = d.month - 1 + n
    year = d.year + month // 12
    month = month % 12 + 1

    return date(
        year,
        month,
        min(d.day, monthrange(year, month)[1])
    )


def make_id(prefix: str, n: int, width: int = 6) -> str:
    """Create a zero-padded identifier."""
    return f"{prefix}-{n:0{width}d}"


def generate(
    customers: int = 500,
    months: int = 18,
    seed: int = 20261022
) -> dict:
    """Generate synthetic customer, behavioral, campaign and outcome data."""

    if customers < 4:
        raise ValueError("At least 4 customers are required.")

    if months < 6:
        raise ValueError("At least 6 months of history are required.")

    rng = random.Random(seed)

    start_month = date(2025, 1, 1)
    prediction_date = add_months(start_month, months)
    horizon_end = prediction_date + timedelta(days=90)

    tables = {
        name: []
        for name in [
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
    }

    latent = {}
    subscription_by_customer = {}
    subscription_history_counter = 0

    # 1. CUSTOMER MASTER DATA

    for i in range(1, customers + 1):
        customer_id = make_id("CUS", i)

        signup_date = add_months(
            start_month,
            -rng.randint(1, 24)
        )

        segment = rng.choice(SEGMENTS)

        plan = rng.choices(
            list(PLANS.keys()),
            weights=[0.45, 0.40, 0.15]
        )[0]

        fee = PLANS[plan]
        seasonal = rng.random() < 0.12
        base_usage = rng.uniform(8, 120)

        if segment == "enterprise":
            base_usage *= 1.4

        propensity = rng.random()

        tables["customers"].append({
            "customer_id": customer_id,
            "signup_date": signup_date.isoformat(),
            "region": rng.choice(REGIONS),
            "segment": segment,
            "acquisition_channel": rng.choice(CHANNELS),
            "seasonal_user": seasonal
        })

        subscription_id = f"SUB-{customer_id}-01"

        subscription = {
            "subscription_id": subscription_id,
            "customer_id": customer_id,
            "plan": plan,
            "monthly_fee": round(fee, 2),
            "status": "active",
            "start_date": signup_date.isoformat(),
            "end_date": ""
        }

        tables["subscriptions"].append(subscription)
        subscription_by_customer[customer_id] = subscription

        # Preserve the initial subscription state as the first history event.
        subscription_history_counter += 1
        tables["subscription_history"].append({
            "history_id": make_id("SUBHIST", subscription_history_counter),
            "subscription_id": subscription_id,
            "event_type": "subscription_created",
            "previous_plan": "",
            "new_plan": plan,
            "previous_fee": "",
            "new_fee": round(fee, 2),
            "previous_status": "",
            "new_status": "active",
            "effective_date": signup_date.isoformat()
        })

        latent[customer_id] = {
            "sid": subscription_id,
            "plan": plan,
            "fee": fee,
            "base": base_usage,
            "seasonal": seasonal,
            "propensity": propensity,
            "segment": segment
        }

    # 2. OFFER MASTER DATA

    offer_definitions = [
        ("discount", 20, 3, 3.0),
        ("bonus_data", 0, 2, 5.0),
        ("loyalty_credit", 10, 1, 8.0)
    ]

    for i, (kind, discount, duration, cost) in enumerate(
        offer_definitions, 1
    ):
        tables["offers"].append({
            "offer_id": f"OFF-2026-{i:06d}",
            "offer_type": kind,
            "discount_pct": discount,
            "duration_months": duration,
            "estimated_cost": cost,
            "active": True
        })

    tables["offers"].append({
        "offer_id": "OFF-2026-000004",
        "offer_type": "control_holdout",
        "discount_pct": 0,
        "duration_months": 0,
        "estimated_cost": 0.0,
        "active": True
    })

    tables["eligibility_rules"].append({
        "rule_id": "RULE-2026-000001",
        "min_risk_score": 35,
        "max_cost_margin_pct": 0.30,
        "active_only": True,
        "cooldown_days": 90
    })

    # 3. GENERATE USAGE, BILLING AND SUPPORT HISTORY

    prior_usage = {}

    failed_counts = {
        cid: 0 for cid in latent
    }

    sub_to_customer = {
        meta["sid"]: cid
        for cid, meta in latent.items()
    }

    billing_counter = 0
    support_counter = 0

    for customer_id, meta in latent.items():
        previous_usage = []

        current_plan = meta["plan"]
        current_fee = meta["fee"]

        change_month = None

        if months > 6 and rng.random() < 0.12:
            change_month = rng.randint(6, months - 1)

        for m in range(months):
            month_date = add_months(start_month, m)

            # PLAN CHANGE

            if change_month == m:
                previous_plan = current_plan

                available_plans = [
                    p for p in PLANS
                    if p != current_plan
                ]

                current_plan = rng.choice(available_plans)
                new_fee = PLANS[current_plan]

                billing_counter += 1

                tables["billing_events"].append({
                    "billing_event_id": make_id(
                        "BILL", billing_counter
                    ),
                    "subscription_id": meta["sid"],
                    "event_date": month_date.isoformat(),
                    "event_type": (
                        f"plan_change:{previous_plan}->{current_plan}"
                    ),
                    "amount": round(new_fee - current_fee, 2),
                    "status": "completed"
                })

                subscription_history_counter += 1
                tables["subscription_history"].append({
                    "history_id": make_id(
                        "SUBHIST", subscription_history_counter
                    ),
                    "subscription_id": meta["sid"],
                    "event_type": "plan_changed",
                    "previous_plan": previous_plan,
                    "new_plan": current_plan,
                    "previous_fee": round(current_fee, 2),
                    "new_fee": round(new_fee, 2),
                    "previous_status": "active",
                    "new_status": "active",
                    "effective_date": month_date.isoformat()
                })

                current_fee = new_fee

            # MONTHLY USAGE

            seasonal_factor = 1.0

            if meta["seasonal"] and month_date.month in (6, 7, 8):
                seasonal_factor = 0.55

            decline_factor = (
                1.0
                - (
                    0.42
                    * meta["propensity"]
                    * (m / max(1, months - 1))
                )
            )

            usage = max(
                0.1,
                meta["base"]
                * seasonal_factor
                * decline_factor
                * rng.uniform(0.82, 1.18)
            )

            sessions = max(
                1,
                int(usage / rng.uniform(1.5, 3.5))
            )

            active_days = min(
                30,
                max(1, int(sessions * rng.uniform(0.35, 0.75)))
            )

            tables["usage_snapshots"].append({
                "snapshot_id": (
                    f"SNAP-{meta['sid']}-{month_date:%Y-%m}"
                ),
                "subscription_id": meta["sid"],
                "month": month_date.strftime("%Y-%m"),
                "data_gb": round(usage, 2),
                "sessions": sessions,
                "active_days": active_days
            })

            previous_usage.append(usage)

            # BILLING

            billing_counter += 1

            failed = rng.random() < (
                0.025 + 0.13 * meta["propensity"]
            )

            tables["billing_events"].append({
                "billing_event_id": make_id(
                    "BILL", billing_counter
                ),
                "subscription_id": meta["sid"],
                "event_date": month_date.replace(day=15).isoformat(),
                "event_type": "payment",
                "amount": round(current_fee, 2),
                "status": "failed" if failed else "paid"
            })

            if failed:
                billing_counter += 1

                tables["billing_events"].append({
                    "billing_event_id": make_id(
                        "BILL", billing_counter
                    ),
                    "subscription_id": meta["sid"],
                    "event_date": (
                        month_date.replace(day=20)
                        + timedelta(days=5)
                    ).isoformat(),
                    "event_type": "payment_retry",
                    "amount": round(current_fee, 2),
                    "status": (
                        "paid" if rng.random() < 0.7 else "failed"
                    )
                })

        prior_usage[customer_id] = previous_usage

        subscription = subscription_by_customer[customer_id]

        subscription["plan"] = current_plan
        subscription["monthly_fee"] = round(current_fee, 2)

        meta["plan"] = current_plan
        meta["fee"] = current_fee

        # SUPPORT CASES

        case_count = min(
            5,
            int(rng.random() * (1 + 4 * meta["propensity"]))
        )

        for _ in range(case_count):
            support_counter += 1

            opened = (
                add_months(
                    start_month,
                    rng.randrange(months)
                )
                + timedelta(days=rng.randint(0, 25))
            )

            tables["support_cases"].append({
                "support_case_id": make_id(
                    "CASE", support_counter
                ),
                "customer_id": customer_id,
                "opened_at": opened.isoformat(),
                "category": rng.choice(SUPPORT_CATEGORIES),
                "priority": rng.choice(["low", "medium", "high"]),
                "status": rng.choice(["resolved", "closed", "open"]),
                "resolution_hours": round(
                    rng.uniform(1, 96), 1
                )
            })

    # 4. AGGREGATE PRE-PREDICTION BILLING AND SUPPORT FEATURES

    for event in tables["billing_events"]:
        event_date = date.fromisoformat(event["event_date"])

        if (
            event["status"] == "failed"
            and event_date < prediction_date
        ):
            customer_id = sub_to_customer[
                event["subscription_id"]
            ]
            failed_counts[customer_id] += 1

    # Count only support cases opened strictly before prediction date.
    support_counts = {
        cid: 0 for cid in latent
    }

    for case in tables["support_cases"]:
        opened_date = date.fromisoformat(case["opened_at"])

        if opened_date < prediction_date:
            support_counts[case["customer_id"]] += 1

    # 5. PRE-PREDICTION FEATURES

    feature_rows = {}

    for customer_id, meta in latent.items():
        usage = prior_usage[customer_id]

        older_average = sum(usage[-6:-3]) / 3
        recent_average = sum(usage[-3:]) / 3

        decline_pct = max(
            0.0,
            (older_average - recent_average)
            / max(older_average, 0.01)
        )

        failed = failed_counts[customer_id]
        cases = support_counts[customer_id]

        low_engagement_score = (
            15 if recent_average < 12 else 0
        )

        risk_score = min(
            100,
            round(
                min(40, decline_pct * 65)
                + min(25, failed * 7)
                + min(20, cases * 5)
                + low_engagement_score
            )
        )

        monthly_margin = meta["fee"] * 0.55

        if risk_score >= 70:
            risk_category = "high"
        elif risk_score >= 35:
            risk_category = "medium"
        else:
            risk_category = "low"

        feature_rows[customer_id] = {
            "customer_id": customer_id,
            "prediction_date": prediction_date.isoformat(),
            "risk_score": risk_score,
            "risk_category": risk_category,
            "usage_decline_pct": round(decline_pct, 4),
            "failed_payments": failed,
            "support_cases": cases,
            "monthly_margin": round(monthly_margin, 2),
            "pre_period_avg_usage": round(recent_average, 2)
        }

    # 6. OFFER ELIGIBILITY

    contact_counter = 0
    outcome_counter = 0

    contact_by_customer = {}
    eligible_customers = []
    eligibility_by_customer = {}

    for customer_id, meta in latent.items():
        features = feature_rows[customer_id]

        eligibility = evaluate_offer_eligibility(
            customer_id=customer_id,
            subscription_status="active",
            risk_score=features["risk_score"],
            monthly_fee=meta["fee"],
            offers=tables["offers"],
            evaluation_date=prediction_date.isoformat(),
            min_risk_score=35,
            max_cost_margin_pct=0.30,
            margin_rate=0.55,
            cooldown_days=90
        )

        # Retain every eligibility decision, including rejections, so
        # campaign records and exception cases remain auditable.
        eligibility_by_customer[customer_id] = eligibility

        if eligibility["eligible"]:
            eligible_customers.append(
                (customer_id, meta, eligibility)
            )

    # 7. RANDOMIZED, BALANCED EXPERIMENT ASSIGNMENT

    rng.shuffle(eligible_customers)

    for index, (customer_id, meta, eligibility) in enumerate(
        eligible_customers
    ):
        features = feature_rows[customer_id]

        # Alternating assignment after random shuffling
        # ensures groups differ in size by at most one.
        group = (
            "treatment"
            if index % 2 == 0
            else "control"
        )

        selected_offer_id = (
            eligibility["selected_offer_id"]
            if group == "treatment"
            else "OFF-2026-000004"
        )

        selected_cost = (
            eligibility["selected_offer_cost"]
            if group == "treatment"
            else 0.0
        )

        contact_counter += 1

        contact = {
            "contact_id": make_id("CONTACT", contact_counter),
            "customer_id": customer_id,
            "offer_id": selected_offer_id,
            "group": group,
            "contact_date": prediction_date.isoformat(),
            "eligibility_status": "eligible",
            "risk_score_at_contact": features["risk_score"],
            "estimated_cost": selected_cost,
            "campaign_id": "CMP-2026-000001",
            "rule_id": eligibility["rule_id"],
            "minimum_required_risk_score": eligibility["minimum_required_risk_score"],
            "monthly_margin": eligibility["monthly_margin"],
            "maximum_allowed_offer_cost": eligibility["maximum_allowed_offer_cost"],
            "max_cost_margin_pct": eligibility["max_cost_margin_pct"],
            "decision_reasons": "|".join(eligibility["decision_reasons"])
        }

        tables["campaign_contacts"].append(contact)
        contact_by_customer[customer_id] = contact

    # 8. GENERATE CHURN AND RETENTION OUTCOMES

    for customer_id, meta in latent.items():
        features = feature_rows[customer_id]

        risk_score = features["risk_score"]
        failed = features["failed_payments"]

        baseline_probability = min(
            0.30,
            max(
                0.025,
                0.035
                + risk_score / 450
                + failed * 0.006
            )
        )

        contact = contact_by_customer.get(customer_id)

        treated = (
            contact is not None
            and contact["group"] == "treatment"
        )

        # Simulate whether a treatment customer responds to the offer
        # before calculating the churn outcome. Only a responding
        # customer receives the simulated retention benefit.
        offer_responded = (
            rng.random() < 0.75
            if treated
            else False
        )

        adjusted_probability = (
            baseline_probability * 0.72
            if treated and offer_responded
            else baseline_probability
        )

        churned = rng.random() < adjusted_probability

        churn_type = ""
        churn_date = ""

        if churned:
            churn_type = (
                "involuntary"
                if failed >= 2 and rng.random() < 0.55
                else "voluntary"
            )

            churn_date = (
                prediction_date
                + timedelta(days=rng.randint(1, 90))
            ).isoformat()

        outcome_counter += 1

        tables["churn_outcomes"].append({
            "churn_id": f"CHURN-{customer_id}-2026",
            "customer_id": customer_id,
            "prediction_date": prediction_date.isoformat(),
            "horizon_end": horizon_end.isoformat(),
            "churned": churned,
            "churn_type": churn_type,
            "churn_date": churn_date,
            "baseline_churn_propensity": round(
                baseline_probability, 4
            )
        })

        if treated:
            retained = not churned

            # A realized offer cost is incurred only when the customer
            # responds to the treatment offer.
            realized_cost = (
                contact["estimated_cost"]
                if offer_responded
                else 0.0
            )

            outcome_counter += 1

            tables["retention_outcomes"].append({
                "retention_id": make_id("RET", outcome_counter),
                "contact_id": contact["contact_id"],
                "customer_id": customer_id,
                "retained": retained,
                "offer_responded": offer_responded,
                "realized_offer_cost": round(realized_cost, 2),
                "outcome_date": horizon_end.isoformat()
            })

    # 9. INJECT LABELLED EDGE CASES

    ground_truth = []

    # EDGE CASE 1: CHURN BEFORE PREDICTION DATE

    churn_record = tables["churn_outcomes"][0]

    churn_record["churned"] = True
    churn_record["churn_type"] = "voluntary"

    churn_record["churn_date"] = (
        date.fromisoformat(churn_record["prediction_date"])
        - timedelta(days=2)
    ).isoformat()

    ground_truth.append({
        "issue_id": "GT-001",
        "issue_type": "churn_before_prediction",
        "entity": "ChurnOutcome",
        "record_id": churn_record["churn_id"],
        "expected_detection": (
            "churn_date must be on/after prediction_date"
        )
    })

    # EDGE CASE 2: OFFER TO INELIGIBLE CUSTOMER

    low_risk_customer = min(
        latent.keys(),
        key=lambda cid: feature_rows[cid]["risk_score"]
    )

    contact_counter += 1

    ineligible_contact_id = make_id(
        "CONTACT", contact_counter
    )

    low_risk_decision = eligibility_by_customer[low_risk_customer]

    tables["campaign_contacts"].append({
        "contact_id": ineligible_contact_id,
        "customer_id": low_risk_customer,
        "offer_id": "OFF-2026-000001",
        "group": "treatment",
        "contact_date": prediction_date.isoformat(),
        "eligibility_status": "ineligible",
        "risk_score_at_contact": feature_rows[
            low_risk_customer
        ]["risk_score"],
        "estimated_cost": 3.0,
        "campaign_id": "CMP-ANOMALY-001",
        "rule_id": low_risk_decision["rule_id"],
        "minimum_required_risk_score": low_risk_decision["minimum_required_risk_score"],
        "monthly_margin": low_risk_decision["monthly_margin"],
        "maximum_allowed_offer_cost": low_risk_decision["maximum_allowed_offer_cost"],
        "max_cost_margin_pct": low_risk_decision["max_cost_margin_pct"],
        "decision_reasons": "|".join(low_risk_decision["decision_reasons"])
    })

    ground_truth.append({
        "issue_id": "GT-002",
        "issue_type": "offer_to_ineligible_customer",
        "entity": "CampaignContact",
        "record_id": ineligible_contact_id,
        "expected_detection": (
            "risk score below eligibility threshold"
        )
    })

    # EDGE CASE 3: TREATMENT/CONTROL LEAKAGE

    if not eligible_customers:
        raise ValueError(
            "No eligible customers available for leakage test. "
            "Review eligibility configuration."
        )

    leakage_customer, _, leakage_eligibility = eligible_customers[0]

    contact_counter += 1

    control_contact_id = make_id(
        "CONTACT", contact_counter
    )

    tables["campaign_contacts"].append({
        "contact_id": control_contact_id,
        "customer_id": leakage_customer,
        "offer_id": "OFF-2026-000004",
        "group": "control",
        "contact_date": prediction_date.isoformat(),
        "eligibility_status": "eligible",
        "risk_score_at_contact": feature_rows[
            leakage_customer
        ]["risk_score"],
        "estimated_cost": 0.0,
        "campaign_id": "CMP-2026-000001",
        "rule_id": leakage_eligibility["rule_id"],
        "minimum_required_risk_score": leakage_eligibility["minimum_required_risk_score"],
        "monthly_margin": leakage_eligibility["monthly_margin"],
        "maximum_allowed_offer_cost": leakage_eligibility["maximum_allowed_offer_cost"],
        "max_cost_margin_pct": leakage_eligibility["max_cost_margin_pct"],
        "decision_reasons": "|".join(leakage_eligibility["decision_reasons"])
    })

    contact_counter += 1

    treatment_contact_id = make_id(
        "CONTACT", contact_counter
    )

    tables["campaign_contacts"].append({
        "contact_id": treatment_contact_id,
        "customer_id": leakage_customer,
        "offer_id": leakage_eligibility["selected_offer_id"],
        "group": "treatment",
        "contact_date": prediction_date.isoformat(),
        "eligibility_status": "eligible",
        "risk_score_at_contact": feature_rows[
            leakage_customer
        ]["risk_score"],
        "estimated_cost": leakage_eligibility["selected_offer_cost"],
        "campaign_id": "CMP-2026-000001",
        "rule_id": leakage_eligibility["rule_id"],
        "minimum_required_risk_score": leakage_eligibility["minimum_required_risk_score"],
        "monthly_margin": leakage_eligibility["monthly_margin"],
        "maximum_allowed_offer_cost": leakage_eligibility["maximum_allowed_offer_cost"],
        "max_cost_margin_pct": leakage_eligibility["max_cost_margin_pct"],
        "decision_reasons": "|".join(leakage_eligibility["decision_reasons"])
    })

    ground_truth.append({
        "issue_id": "GT-003",
        "issue_type": "treatment_control_leakage",
        "entity": "CampaignContact",
        "record_id": control_contact_id,
        "expected_detection": (
            "customer assigned to both experiment groups"
        )
    })

    # EDGE CASE 4: MULTIPLE RETENTION ATTRIBUTIONS

    original_retained = next(
        (
            row for row in tables["retention_outcomes"]
            if row["retained"]
        ),
        None
    )

    if original_retained is None:
        duplicate_customer = list(latent.keys())[3]

        contact_counter += 1

        duplicate_contact_id = make_id(
            "CONTACT", contact_counter
        )

        tables["campaign_contacts"].append({
            "contact_id": duplicate_contact_id,
            "customer_id": duplicate_customer,
            "offer_id": "OFF-2026-000001",
            "group": "treatment",
            "contact_date": prediction_date.isoformat(),
            "eligibility_status": "eligible",
            "risk_score_at_contact": feature_rows[
                duplicate_customer
            ]["risk_score"],
            "estimated_cost": 3.0,
            "campaign_id": "CMP-ANOMALY-004",
            "rule_id": eligibility_by_customer[duplicate_customer]["rule_id"],
            "minimum_required_risk_score": eligibility_by_customer[duplicate_customer]["minimum_required_risk_score"],
            "monthly_margin": eligibility_by_customer[duplicate_customer]["monthly_margin"],
            "maximum_allowed_offer_cost": eligibility_by_customer[duplicate_customer]["maximum_allowed_offer_cost"],
            "max_cost_margin_pct": eligibility_by_customer[duplicate_customer]["max_cost_margin_pct"],
            "decision_reasons": "|".join(eligibility_by_customer[duplicate_customer]["decision_reasons"])
        })

        outcome_counter += 1

        original_retained = {
            "retention_id": make_id("RET", outcome_counter),
            "contact_id": duplicate_contact_id,
            "customer_id": duplicate_customer,
            "retained": True,
            "offer_responded": True,
            "realized_offer_cost": 3.0,
            "outcome_date": horizon_end.isoformat()
        }

        tables["retention_outcomes"].append(original_retained)

    duplicate = dict(original_retained)

    outcome_counter += 1

    duplicate["retention_id"] = make_id(
        "RET", outcome_counter
    )

    tables["retention_outcomes"].append(duplicate)

    ground_truth.append({
        "issue_id": "GT-004",
        "issue_type": "multiple_offer_attribution",
        "entity": "RetentionOutcome",
        "record_id": duplicate["retention_id"],
        "expected_detection": (
            "customer has multiple retention attributions"
        )
    })

    return {
        "tables": tables,
        "ground_truth": ground_truth,
        "features": feature_rows,
        "prediction_date": prediction_date.isoformat(),
        "horizon_end": horizon_end.isoformat()
    }
