"""Integrity and business-rule validation for the churn-retention pipeline."""

from collections import Counter, defaultdict
from datetime import date
import math


PK = {
    "customers": "customer_id",
    "subscriptions": "subscription_id",
    "subscription_history": "history_id",
    "usage_snapshots": "snapshot_id",
    "billing_events": "billing_event_id",
    "support_cases": "support_case_id",
    "offers": "offer_id",
    "eligibility_rules": "rule_id",
    "campaign_contacts": "contact_id",
    "churn_outcomes": "churn_id",
    "retention_outcomes": "retention_id",
}


def _as_bool(value):
    """Convert common CSV/Python boolean representations safely."""
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0 if math.isfinite(float(value)) else None

    if isinstance(value, str):
        value = value.strip().lower()

        if value in {"true", "1", "yes", "y"}:
            return True

        if value in {"false", "0", "no", "n", ""}:
            return False

    return None


def _number(value):
    """Return a finite float, or None for invalid/missing values."""
    if value in (None, ""):
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    return result if math.isfinite(result) else None


def validate(tables: dict) -> dict:
    """Validate keys, relationships, dates, ranges and experiment rules."""

    issues = []

    def issue(kind, entity, record_id, detail):
        issues.append({
            "issue_type": kind,
            "entity": entity,
            "record_id": record_id,
            "detail": detail,
        })

    def parse_date(value):
        if value in (None, ""):
            return None

        try:
            return date.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

    def check_date(record, entity, rid, field, required=False):
        value = record.get(field)
        parsed = parse_date(value)

        if (required and value in (None, "")) or (
            value not in (None, "") and parsed is None
        ):
            issue(
                "invalid_date", entity, rid,
                f"Invalid or missing {field}: {value}"
            )

        return parsed

    def check_date_order(record, entity, rid, earlier, later):
        first = check_date(record, entity, rid, earlier)
        second = check_date(record, entity, rid, later)

        if first and second and first > second:
            issue(
                "date_order", entity, rid,
                f"{earlier} occurs after {later}"
            )

    def check_nonnegative(record, entity, rid, field, required=False):
        value = record.get(field)
        number = _number(value)

        if number is None:
            if required or value not in (None, ""):
                issue(
                    "invalid_numeric", entity, rid,
                    f"{field} must be a finite number"
                )
        elif number < 0:
            issue(
                "negative_amount", entity, rid,
                f"{field} cannot be negative"
            )

        return number

    # 1. Required tables and primary keys.
    for entity in PK:
        if entity not in tables:
            issue("missing_table", entity, entity, "Required table is missing")

    if any(entity not in tables for entity in PK):
        return {
            "passed": False,
            "issue_count": len(issues),
            "issues": issues,
        }

    for entity, key in PK.items():
        ids = []

        for record in tables[entity]:
            record_id = record.get(key)

            if record_id in (None, ""):
                issue(
                    "missing_primary_key", entity, "UNKNOWN",
                    f"Missing required field {key}"
                )
            else:
                ids.append(record_id)

        for record_id, count in Counter(ids).items():
            if count > 1:
                issue(
                    "duplicate_primary_key", entity, record_id,
                    f"Appears {count} times"
                )

    # 2. Reference sets.
    customer_ids = {
        r["customer_id"]
        for r in tables["customers"]
        if r.get("customer_id")
    }

    subscription_by_id = {
        r["subscription_id"]: r
        for r in tables["subscriptions"]
        if r.get("subscription_id")
    }
    subscription_ids = set(subscription_by_id)

    offer_by_id = {
        r["offer_id"]: r
        for r in tables["offers"]
        if r.get("offer_id")
    }
    offer_ids = set(offer_by_id)

    contact_by_id = {
        r["contact_id"]: r
        for r in tables["campaign_contacts"]
        if r.get("contact_id")
    }
    contact_ids = set(contact_by_id)

    rule_ids = {
        r["rule_id"]
        for r in tables["eligibility_rules"]
        if r.get("rule_id")
    }

    # 3. Subscriptions.
    for r in tables["subscriptions"]:
        rid = r.get("subscription_id", "UNKNOWN")

        if r.get("customer_id") not in customer_ids:
            issue("foreign_key", "Subscription", rid, "Unknown customer_id")

        check_date(r, "Subscription", rid, "start_date", required=True)
        check_date_order(r, "Subscription", rid, "start_date", "end_date")

        check_nonnegative(
            r, "Subscription", rid, "monthly_fee", required=True
        )

        if r.get("status") not in {
            "active", "cancelled", "paused", "expired"
        }:
            issue(
                "invalid_enum", "Subscription", rid,
                f"Unsupported status: {r.get('status')}"
            )

    # 4. Subscription history.
    history_by_subscription = defaultdict(list)

    valid_history_events = {
        "subscription_created",
        "plan_changed",
        "status_changed",
    }

    for r in tables["subscription_history"]:
        rid = r.get("history_id", "UNKNOWN")
        sid = r.get("subscription_id")

        if sid not in subscription_ids:
            issue(
                "foreign_key", "SubscriptionHistory", rid,
                "Unknown subscription_id"
            )

        effective = check_date(
            r, "SubscriptionHistory", rid,
            "effective_date", required=True
        )

        if effective:
            history_by_subscription[sid].append((effective, r))

        if r.get("event_type") not in valid_history_events:
            issue(
                "invalid_enum", "SubscriptionHistory", rid,
                f"Unsupported event_type: {r.get('event_type')}"
            )

        for field in ("previous_fee", "new_fee"):
            check_nonnegative(r, "SubscriptionHistory", rid, field)

    for sid, entries in history_by_subscription.items():
        entries.sort(key=lambda item: (item[0], str(item[1].get("history_id", ""))))

        for index in range(1, len(entries)):
            if entries[index][0] < entries[index - 1][0]:
                issue(
                    "history_date_order", "SubscriptionHistory", sid,
                    "History dates are not chronological"
                )

    # 5. Usage snapshots.
    for r in tables["usage_snapshots"]:
        rid = r.get("snapshot_id", "UNKNOWN")

        if r.get("subscription_id") not in subscription_ids:
            issue("foreign_key", "usage_snapshots", rid, "Unknown subscription_id")

        month = r.get("month")

        try:
            parsed_month = date.fromisoformat(f"{month}-01") if month else None
        except (TypeError, ValueError):
            parsed_month = None

        if parsed_month is None:
            issue("invalid_date", "usage_snapshots", rid, f"Invalid month: {month}")

        for field in ("data_gb", "sessions", "active_days"):
            value = check_nonnegative(
                r, "usage_snapshots", rid, field, required=True
            )

            if (
                value is not None
                and field in {"sessions", "active_days"}
                and not value.is_integer()
            ):
                issue(
                    "invalid_numeric", "usage_snapshots", rid,
                    f"{field} must be an integer"
                )

        active_days = _number(r.get("active_days"))

        if active_days is not None and active_days > 31:
            issue(
                "invalid_range", "usage_snapshots", rid,
                "active_days cannot exceed 31"
            )

    # 6. Billing events.
    for r in tables["billing_events"]:
        rid = r.get("billing_event_id", "UNKNOWN")

        if r.get("subscription_id") not in subscription_ids:
            issue("foreign_key", "billing_events", rid, "Unknown subscription_id")

        check_date(
            r, "billing_events", rid, "event_date", required=True
        )

        event_type = r.get("event_type")

        # Payment amounts must be non-negative.
        # Plan-change adjustments may be negative because a downgrade
        # represents a reduction in the subscription fee.
        amount = _number(r.get("amount"))

        if amount is None:
            issue(
                "invalid_numeric", "BillingEvent", rid,
                "amount must be a finite number"
            )
        elif amount < 0 and not (
            isinstance(event_type, str)
            and event_type.startswith("plan_change:")
        ):
            issue(
                "negative_amount", "BillingEvent", rid,
                "Payment amount cannot be negative"
            )

        valid_event_type = (
            event_type in {"payment", "payment_retry"}
            or (
                isinstance(event_type, str)
                and event_type.startswith("plan_change:")
            )
        )

        if not valid_event_type:
            issue(
                "invalid_enum", "BillingEvent", rid,
                f"Unsupported event_type: {event_type}"
            )

        if r.get("status") not in {"paid", "failed", "completed"}:
            issue(
                "invalid_enum", "BillingEvent", rid,
                f"Unsupported status: {r.get('status')}"
            )

    # 7. Support cases.
    for r in tables["support_cases"]:
        rid = r.get("support_case_id", "UNKNOWN")

        if r.get("customer_id") not in customer_ids:
            issue("foreign_key", "SupportCase", rid, "Unknown customer_id")

        check_date(
            r, "SupportCase", rid, "opened_at", required=True
        )

        check_nonnegative(
            r, "SupportCase", rid, "resolution_hours", required=True
        )

        if r.get("priority") not in {"low", "medium", "high"}:
            issue(
                "invalid_enum", "SupportCase", rid,
                f"Unsupported priority: {r.get('priority')}"
            )

        if r.get("status") not in {"resolved", "closed", "open"}:
            issue(
                "invalid_enum", "SupportCase", rid,
                f"Unsupported status: {r.get('status')}"
            )

    # 8. Churn outcomes.
    for r in tables["churn_outcomes"]:
        rid = r.get("churn_id", "UNKNOWN")

        if r.get("customer_id") not in customer_ids:
            issue("foreign_key", "ChurnOutcome", rid, "Unknown customer_id")

        prediction = check_date(
            r, "ChurnOutcome", rid, "prediction_date", required=True
        )

        horizon_end = check_date(
            r, "ChurnOutcome", rid, "horizon_end", required=True
        )

        churn_value = r.get("churn_date")
        churn_date = check_date(r, "ChurnOutcome", rid, "churn_date")
        churned = _as_bool(r.get("churned"))

        if prediction and horizon_end and prediction > horizon_end:
            issue(
                "date_order", "ChurnOutcome", rid,
                "prediction_date occurs after horizon_end"
            )

        if churned is None:
            issue(
                "invalid_boolean", "ChurnOutcome", rid,
                "churned must be a boolean"
            )

        elif churned:
            if not r.get("churn_type"):
                issue(
                    "missing_churn_type", "ChurnOutcome", rid,
                    "Churned record requires churn_type"
                )
            elif r.get("churn_type") not in {"voluntary", "involuntary"}:
                issue(
                    "invalid_enum", "ChurnOutcome", rid,
                    f"Unsupported churn_type: {r.get('churn_type')}"
                )

            if churn_date is None:
                issue(
                    "missing_churn_date", "ChurnOutcome", rid,
                    "Churned record requires a valid churn_date"
                )

            if prediction and churn_date and churn_date < prediction:
                issue(
                    "churn_before_prediction", "ChurnOutcome", rid,
                    "Churn date precedes prediction date"
                )

            if horizon_end and churn_date and churn_date > horizon_end:
                issue(
                    "churn_after_horizon", "ChurnOutcome", rid,
                    "Churn date occurs after horizon_end"
                )

        else:
            if churn_value not in (None, ""):
                issue(
                    "unexpected_churn_date", "ChurnOutcome", rid,
                    "Non-churned record must not have churn_date"
                )

            if r.get("churn_type") not in (None, ""):
                issue(
                    "unexpected_churn_type", "ChurnOutcome", rid,
                    "Non-churned record must not have churn_type"
                )

        propensity = _number(r.get("baseline_churn_propensity"))

        if propensity is None or not 0 <= propensity <= 1:
            issue(
                "invalid_range", "ChurnOutcome", rid,
                "baseline_churn_propensity must be between 0 and 1"
            )

    # 9. Offers.
    for r in tables["offers"]:
        rid = r.get("offer_id", "UNKNOWN")

        check_nonnegative(
            r, "Offer", rid, "estimated_cost", required=True
        )

        discount = _number(r.get("discount_pct"))

        if discount is None or not 0 <= discount <= 100:
            issue(
                "invalid_range", "Offer", rid,
                "discount_pct must be between 0 and 100"
            )

        duration = _number(r.get("duration_months"))

        if duration is None or duration < 0 or not duration.is_integer():
            issue(
                "invalid_range", "Offer", rid,
                "duration_months must be a non-negative integer"
            )

        if _as_bool(r.get("active")) is None:
            issue(
                "invalid_boolean", "Offer", rid,
                "active must be a boolean"
            )

    # 10. Eligibility rules.
    for r in tables["eligibility_rules"]:
        rid = r.get("rule_id", "UNKNOWN")

        minimum = _number(r.get("min_risk_score"))

        if minimum is None or not 0 <= minimum <= 100:
            issue(
                "invalid_eligibility_rule", "EligibilityRule", rid,
                "Minimum risk score must be between 0 and 100"
            )

        margin = _number(r.get("max_cost_margin_pct"))

        if margin is None or not 0 < margin <= 1:
            issue(
                "invalid_eligibility_rule", "EligibilityRule", rid,
                "Maximum cost margin percentage must be between 0 and 1"
            )

        cooldown = _number(r.get("cooldown_days"))

        if cooldown is None or cooldown < 0 or not cooldown.is_integer():
            issue(
                "invalid_eligibility_rule", "EligibilityRule", rid,
                "cooldown_days must be a non-negative integer"
            )

    # 11. Campaign contacts.
    assignments = defaultdict(set)

    for r in tables["campaign_contacts"]:
        rid = r.get("contact_id", "UNKNOWN")
        customer_id = r.get("customer_id")
        offer_id = r.get("offer_id")

        if customer_id not in customer_ids:
            issue("foreign_key", "CampaignContact", rid, "Unknown customer_id")

        if offer_id not in offer_ids:
            issue("foreign_key", "CampaignContact", rid, "Unknown offer_id")

        rule_id = r.get("rule_id")
        if rule_id in (None, ""):
            issue("missing_eligibility_rule", "CampaignContact", rid,
                  "Campaign contact must retain the rule_id used for its decision")
        elif rule_id not in rule_ids:
            issue("foreign_key", "CampaignContact", rid, "Unknown rule_id")

        campaign_id = r.get("campaign_id")
        group = r.get("group")

        if customer_id and campaign_id and group:
            assignments[(customer_id, campaign_id)].add(group)

        if group not in {"treatment", "control"}:
            issue(
                "invalid_enum", "CampaignContact", rid,
                f"Unsupported group: {group}"
            )

        if r.get("eligibility_status") not in {"eligible", "ineligible"}:
            issue(
                "invalid_enum", "CampaignContact", rid,
                f"Unsupported eligibility_status: {r.get('eligibility_status')}"
            )

        estimated = check_nonnegative(
            r, "CampaignContact", rid, "estimated_cost", required=True
        )

        risk = _number(r.get("risk_score_at_contact"))

        if risk is None or not 0 <= risk <= 100:
            issue(
                "invalid_risk_score", "CampaignContact", rid,
                "risk_score_at_contact must be between 0 and 100"
            )

        if (
            r.get("eligibility_status") == "ineligible"
            or (risk is not None and risk < 35)
        ):
            issue(
                "offer_to_ineligible_customer", "CampaignContact", rid,
                "Customer does not satisfy minimum churn-risk eligibility"
            )

        # Preserve the inputs and explanation behind each eligibility decision.
        minimum_risk = _number(r.get("minimum_required_risk_score"))
        if minimum_risk is None or not 0 <= minimum_risk <= 100:
            issue("invalid_eligibility_trace", "CampaignContact", rid,
                  "minimum_required_risk_score must be between 0 and 100")

        monthly_margin = check_nonnegative(
            r, "CampaignContact", rid, "monthly_margin", required=True
        )

        max_cost_value = r.get("maximum_allowed_offer_cost")
        max_cost = _number(max_cost_value)
        if max_cost is None or max_cost < 0:
            issue("invalid_eligibility_trace", "CampaignContact", rid,
                  "maximum_allowed_offer_cost must be a non-negative number")
        elif estimated is not None and estimated > max_cost:
            issue(
                "offer_exceeds_margin_limit", "CampaignContact", rid,
                "Estimated offer cost exceeds maximum allowed offer cost"
            )

        margin_pct = _number(r.get("max_cost_margin_pct"))
        if margin_pct is None or not 0 < margin_pct <= 1:
            issue("invalid_eligibility_trace", "CampaignContact", rid,
                  "max_cost_margin_pct must be greater than 0 and at most 1")

        reasons = r.get("decision_reasons")
        if not isinstance(reasons, str) or not reasons.strip():
            issue("missing_decision_reason", "CampaignContact", rid,
                  "decision_reasons must contain the eligibility decision explanation")

        if (
            r.get("eligibility_status") == "eligible"
            and risk is not None
            and minimum_risk is not None
            and risk < minimum_risk
        ):
            issue("eligibility_rule_violation", "CampaignContact", rid,
                  "Eligible contact has a risk score below the recorded rule threshold")

        check_date(
            r, "CampaignContact", rid, "contact_date", required=True
        )

        if (
            offer_id in offer_by_id
            and _as_bool(offer_by_id[offer_id].get("active")) is False
        ):
            issue(
                "inactive_offer", "CampaignContact", rid,
                "Campaign contact references an inactive offer"
            )

    for (customer_id, campaign_id), groups in assignments.items():
        if len(groups) > 1:
            issue(
                "treatment_control_leakage",
                "CampaignContact",
                customer_id,
                f"{campaign_id}: {sorted(groups)}"
            )

    # 12. Retention outcomes.
    retained_by_customer = Counter()

    for r in tables["retention_outcomes"]:
        rid = r.get("retention_id", "UNKNOWN")
        contact_id = r.get("contact_id")
        customer_id = r.get("customer_id")

        contact = contact_by_id.get(contact_id)

        if contact is None:
            issue("foreign_key", "RetentionOutcome", rid, "Unknown contact_id")

        if customer_id not in customer_ids:
            issue("foreign_key", "RetentionOutcome", rid, "Unknown customer_id")

        if contact is not None and contact.get("customer_id") != customer_id:
            issue(
                "contact_customer_mismatch", "RetentionOutcome", rid,
                "customer_id does not match referenced campaign contact"
            )

        if contact is not None and contact.get("group") != "treatment":
            issue(
                "outcome_for_control", "RetentionOutcome", rid,
                "Retention outcome must reference a treatment contact"
            )

        retained = _as_bool(r.get("retained"))

        if retained is None:
            issue(
                "invalid_boolean", "RetentionOutcome", rid,
                "retained must be a boolean"
            )
        elif retained:
            retained_by_customer[customer_id] += 1

        responded = _as_bool(r.get("offer_responded"))
        if responded is None:
            issue(
                "invalid_boolean", "RetentionOutcome", rid,
                "offer_responded must be a boolean"
            )

        outcome_date = check_date(
            r, "RetentionOutcome", rid, "outcome_date", required=True
        )

        realized = check_nonnegative(
            r, "RetentionOutcome", rid,
            "realized_offer_cost", required=True
        )

        if responded is False and realized is not None and realized > 0:
            issue(
                "cost_without_offer_response", "RetentionOutcome", rid,
                "A non-responded offer must not have a positive realized offer cost"
            )

        if contact is not None:
            contact_date = parse_date(contact.get("contact_date"))

            if contact_date and outcome_date and outcome_date < contact_date:
                issue(
                    "date_order", "RetentionOutcome", rid,
                    "outcome_date precedes contact_date"
                )

            estimated = _number(contact.get("estimated_cost"))

            if (
                realized is not None
                and estimated is not None
                and realized > estimated
            ):
                issue(
                    "realized_cost_exceeds_estimate",
                    "RetentionOutcome",
                    rid,
                    "Realized offer cost exceeds estimated contact cost"
                )

    for customer_id, count in retained_by_customer.items():
        if count > 1:
            issue(
                "multiple_offer_attribution",
                "RetentionOutcome",
                customer_id,
                f"{count} retained attributions"
            )

    return {
        "passed": len(issues) == 0,
        "issue_count": len(issues),
        "issues": issues,
    }