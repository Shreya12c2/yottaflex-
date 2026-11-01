"""Experiment and operational metrics for the churn-retention pipeline.

Metrics use valid, unique records. Intentionally injected anomalies remain
visible in validation but are excluded where they would corrupt measurement.
"""
from datetime import date
from math import isfinite


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        value = value.strip().lower()
        if value in {"true", "1", "yes", "y"}:
            return True
        if value in {"false", "0", "no", "n", ""}:
            return False
    return None


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _nonnegative_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) and number >= 0 else None


def build_metrics(tables: dict, validation: dict, customers: int) -> dict:
    """Calculate churn, experiment and cost metrics with anomaly exclusions."""
    churn_rows = tables.get("churn_outcomes", [])
    contacts = tables.get("campaign_contacts", [])
    retention_rows = tables.get("retention_outcomes", [])

    # Keep one temporally valid churn outcome per customer.
    valid_churn = {}
    invalid_churn = 0
    duplicate_churn = 0

    for row in churn_rows:
        cid = row.get("customer_id")
        pred = _parse_date(row.get("prediction_date"))
        horizon = _parse_date(row.get("horizon_end"))
        churned = _as_bool(row.get("churned"))
        churn_date_value = row.get("churn_date")
        churn_date = _parse_date(churn_date_value) if churn_date_value else None

        is_valid = bool(cid) and pred is not None and horizon is not None
        is_valid = is_valid and pred <= horizon and churned is not None
        if is_valid and churned:
            is_valid = churn_date is not None and pred <= churn_date <= horizon
        elif is_valid:
            is_valid = not churn_date_value

        if not is_valid:
            invalid_churn += 1
            continue
        if cid in valid_churn:
            duplicate_churn += 1
            continue
        valid_churn[cid] = churned

    observed_churned = sum(valid_churn.values())
    observed_count = len(valid_churn)
    overall_rate = observed_churned / observed_count if observed_count else None

    # Identify customers assigned to both groups in the target campaign.
    target_contacts = [
        row for row in contacts
        if row.get("campaign_id") == "CMP-2026-000001"
        and row.get("eligibility_status") == "eligible"
        and row.get("group") in {"treatment", "control"}
    ]
    assignments = {}
    for row in target_contacts:
        cid = row.get("customer_id")
        if cid:
            assignments.setdefault(cid, set()).add(row["group"])

    leaked_customers = {
        cid for cid, groups in assignments.items() if len(groups) > 1
    }

    experiment = {}
    excluded_group_customers = 0
    for group in ("treatment", "control"):
        group_ids = {
            row.get("customer_id") for row in target_contacts
            if row.get("group") == group and row.get("customer_id")
        }
        excluded_group_customers += len(group_ids & leaked_customers)
        clean_ids = group_ids - leaked_customers
        valid_ids = [cid for cid in clean_ids if cid in valid_churn]

        count = len(valid_ids)
        churn_count = sum(valid_churn[cid] for cid in valid_ids)
        churn_rate = churn_count / count if count else None
        retention_rate = 1 - churn_rate if churn_rate is not None else None

        experiment[group] = {
            "customers": count,
            "churn_rate": round(churn_rate, 4) if churn_rate is not None else None,
            "retention_rate": round(retention_rate, 4) if retention_rate is not None else None,
        }

    treatment_retention = experiment["treatment"]["retention_rate"]
    control_retention = experiment["control"]["retention_rate"]
    lift = None
    if treatment_retention is not None and control_retention is not None:
        lift = round(treatment_retention - control_retention, 4)

    # Attribute costs only to unique, eligible treatment contacts with a
    # valid response outcome. Duplicate retained-outcome rows must not inflate
    # spend, and control/ineligible/orphan contacts must not contribute cost.
    contact_by_id = {
        row.get("contact_id"): row for row in contacts if row.get("contact_id")
    }
    cost_by_contact = {}
    duplicate_costs = 0
    invalid_costs = 0
    nonresponse_outcomes = 0
    for row in retention_rows:
        contact_id = row.get("contact_id")
        contact = contact_by_id.get(contact_id)
        responded = _as_bool(row.get("offer_responded"))
        cost = _nonnegative_float(row.get("realized_offer_cost"))

        if (
            not contact_id
            or contact is None
            or contact.get("eligibility_status") != "eligible"
            or contact.get("group") != "treatment"
            or responded is None
            or cost is None
        ):
            invalid_costs += 1
            continue

        if contact_id in cost_by_contact:
            duplicate_costs += 1
            continue

        if not responded:
            if cost > 0:
                invalid_costs += 1
            else:
                nonresponse_outcomes += 1
            continue

        cost_by_contact[contact_id] = cost

    return {
        "customers": customers,
        "observed_churned": observed_churned,
        "overall_observed_churn_rate": (
            round(overall_rate, 4) if overall_rate is not None else None
        ),
        "experiment": experiment,
        "incremental_retention_lift": lift,
        "realized_offer_cost_total": round(sum(cost_by_contact.values()), 2),
        "metric_quality": {
            "valid_churn_outcomes": observed_count,
            "invalid_churn_records_excluded": invalid_churn,
            "duplicate_churn_records_excluded": duplicate_churn,
            "experiment_customers_excluded_for_group_leakage": excluded_group_customers,
            "duplicate_cost_attributions_excluded": duplicate_costs,
            "invalid_cost_records_excluded": invalid_costs,
            "nonresponse_outcomes_excluded_from_offer_cost": nonresponse_outcomes,
            "unique_responded_treatment_contacts_with_cost": len(cost_by_contact),
        },
        "validation_issue_count": validation.get("issue_count", 0),
        "validation_issue_types": sorted({
            item.get("issue_type", "unknown")
            for item in validation.get("issues", [])
        }),
    }
