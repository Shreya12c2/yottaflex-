# Assumptions and Business Rules

This document records the assumptions used by the current synthetic-data generator and retention experiment. These are implementation assumptions, not claims about a real telecom business.

1. **Subscription cardinality:** The generator creates one subscription per customer. Subscription IDs follow `SUB-<customer-id>-01`. The database relationship permits a customer to have multiple subscriptions.
2. **Historical period:** Historical months are consecutive calendar months. The prediction date is the first day after the final historical month. With 18 months beginning in January 2025, the prediction date is `2026-07-01`.
3. **Prediction horizon:** The churn prediction horizon is 90 days; the default horizon end is `2026-09-29`.
4. **Churn definition:** A customer is labelled as churned when a cancellation event is generated within the prediction horizon.
5. **Churn type:** Churn is classified as voluntary or involuntary. Involuntary churn is associated with billing failures.
6. **Usage trend:** Usage decline compares average usage in the most recent three historical months with the preceding three months.
7. **Risk score:** The risk score is a deterministic weighted heuristic with contributions from usage decline (0–40), failed payments (0–25), support burden (0–20), and low engagement/seasonality (0–15). It is not a trained or calibrated machine-learning probability.
8. **Eligibility:** Offer eligibility requires an active subscription, risk score of at least 35, no prior campaign contact under the configured cooldown rule, and estimated offer cost no greater than 30% of estimated monthly contribution margin.
9. **Contribution margin:** Monthly contribution margin is approximated as monthly subscription fee multiplied by 55%.
10. **Experiment assignment:** Eligible customers are assigned to treatment or control using a seeded random process. The campaign-contact data records assignment and offer details; the control group is represented in experiment assignment data as implemented by the generator.
11. **Outcome simulation:** Post-period churn propensity is derived from pre-period features and modified by treatment assignment. A seeded random draw determines the simulated outcome.
12. **Offer response and cost:** Offer response is simulated for treated contacts. Non-response outcomes do not incur realized offer cost; cost is attributed to eligible treatment contacts with a valid response, subject to duplicate-attribution handling.
13. **Subscription history:** `SubscriptionHistory` stores dated subscription lifecycle and plan-related events, including the previous and new plan, fee, or status where applicable. It preserves event history rather than relying only on the current subscription row.
14. **Intentional anomalies:** Four deliberate anomalies are added and labelled in the separate ground-truth artifact: churn before prediction, offer to an ineligible customer, treatment/control leakage, and multiple offer attribution for a retained customer.
15. **Ground truth separation:** Ground-truth anomaly labels are evaluation metadata and are not included in the analytical feature snapshot.
16. **Synthetic results:** All customers, events, experiment assignments, and outcomes are synthetic. Experiment metrics are illustrative and do not establish real-world causal lift.
