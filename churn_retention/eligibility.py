from datetime import date
from typing import Optional


DEFAULT_MIN_RISK_SCORE = 35
DEFAULT_MAX_COST_MARGIN_PCT = 0.30
DEFAULT_MARGIN_RATE = 0.55
DEFAULT_COOLDOWN_DAYS = 90


def evaluate_offer_eligibility(
    customer_id: str,
    subscription_status: str,
    risk_score: int,
    monthly_fee: float,
    offers: list[dict],
    evaluation_date: str,
    previous_contact_date: Optional[str] = None,
    min_risk_score: int = DEFAULT_MIN_RISK_SCORE,
    max_cost_margin_pct: float = DEFAULT_MAX_COST_MARGIN_PCT,
    margin_rate: float = DEFAULT_MARGIN_RATE,
    cooldown_days: int = DEFAULT_COOLDOWN_DAYS,
) -> dict:
    """
    Evaluate whether a customer qualifies for a retention offer.

    Business rules:
    1. Subscription must be active.
    2. Churn risk score must meet the configured threshold.
    3. Customer must not have received an offer within the cooldown period.
    4. Offer cost must not exceed the allowed percentage of monthly margin.
    5. Only active offers can be selected.

    The most expensive affordable offer is selected.
    """

    reasons = []
    eligible_offers = []

    # Validate inputs.
    if not customer_id:
        raise ValueError("customer_id cannot be empty")

    if not 0 <= risk_score <= 100:
        raise ValueError("risk_score must be between 0 and 100")

    if monthly_fee < 0:
        raise ValueError("monthly_fee cannot be negative")

    if not 0 < max_cost_margin_pct <= 1:
        raise ValueError("max_cost_margin_pct must be between 0 and 1")

    if not 0 < margin_rate <= 1:
        raise ValueError("margin_rate must be between 0 and 1")

    if cooldown_days < 0:
        raise ValueError("cooldown_days cannot be negative")

    evaluation = date.fromisoformat(evaluation_date)

    # Calculate contribution margin and offer budget.
    monthly_margin = round(monthly_fee * margin_rate, 2)

    maximum_offer_cost = round(
        monthly_margin * max_cost_margin_pct, 2
    )

    # Rule 1: Subscription status.
    if subscription_status.lower() != "active":
        reasons.append("subscription_not_active")

    # Rule 2: Churn risk.
    if risk_score < min_risk_score:
        reasons.append("risk_score_below_threshold")

    # Rule 3: Previous offer contact and cooldown.
    if previous_contact_date:
        previous_date = date.fromisoformat(previous_contact_date)

        if previous_date > evaluation:
            raise ValueError(
                "previous_contact_date cannot be after evaluation_date"
            )

        days_since_contact = (evaluation - previous_date).days

        if days_since_contact < cooldown_days:
            reasons.append("offer_cooldown_active")

    # Rule 4: Find offers that fit within the customer's budget.
    for offer in offers:

        if not offer.get("active", False):
            continue

        cost = float(offer["estimated_cost"])

        if cost < 0:
            raise ValueError(
                f"Offer {offer.get('offer_id')} has a negative cost"
            )

        if cost <= maximum_offer_cost:
            eligible_offers.append(offer)

    if not eligible_offers:
        reasons.append("no_offer_within_margin_limit")

    # Final eligibility decision.
    eligible = len(reasons) == 0

    selected_offer = None

    if eligible:
        # Select the most expensive offer that remains within budget.
        selected_offer = max(
            eligible_offers,
            key=lambda offer: (
                float(offer["estimated_cost"]),
                offer["offer_id"]
            )
        )

    return {
        "customer_id": customer_id,
        "eligible": eligible,
        "selected_offer_id": (
            selected_offer["offer_id"]
            if selected_offer else None
        ),
        "selected_offer_cost": (
            round(float(selected_offer["estimated_cost"]), 2)
            if selected_offer else 0.0
        ),
        "risk_score": risk_score,
        "minimum_required_risk_score": min_risk_score,
        "monthly_fee": round(monthly_fee, 2),
        "monthly_margin": monthly_margin,
        "maximum_allowed_offer_cost": maximum_offer_cost,
        "max_cost_margin_pct": max_cost_margin_pct,
        "decision_reasons": reasons if reasons else ["eligible"],
        "rule_id": "RULE-2026-000001",
        "evaluation_date": evaluation_date
    }