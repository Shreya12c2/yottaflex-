# Data Dictionary

All generated records are synthetic. Dates use ISO `YYYY-MM-DD`; monetary values are represented in USD; usage is measured in GB unless otherwise stated. Field-level implementation details are defined by the generated CSV/JSON files and the SQLite/SQL schema.

## Relational entities

| Entity | Primary key | Important fields | Relationship |
|---|---|---|---|
| `Customer` | `customer_id` | `signup_date`, `region`, `segment`, `acquisition_channel`, `seasonal_user` | One customer can have one or more subscriptions in the schema; current generator emits one |
| `Subscription` | `subscription_id` | `customer_id`, `plan`, `monthly_fee`, `status`, `start_date`, `end_date` | Many-to-one with Customer |
| `SubscriptionHistory` | `history_id` | `subscription_id`, `event_type`, `previous_plan`, `new_plan`, `previous_fee`, `new_fee`, `previous_status`, `new_status`, `effective_date` | Many-to-one with Subscription |
| `UsageSnapshot` | `snapshot_id` | `subscription_id`, `month`, `data_gb`, `sessions`, `active_days` | Many-to-one with Subscription |
| `BillingEvent` | `billing_event_id` | `subscription_id`, `event_date`, `event_type`, `amount`, `status` | Many-to-one with Subscription |
| `SupportCase` | `support_case_id` | `customer_id`, `opened_at`, `category`, `priority`, `status`, `resolution_hours` | Many-to-one with Customer |
| `Offer` | `offer_id` | `offer_type`, `discount_pct`, `duration_months`, `estimated_cost` | Referenced by CampaignContact |
| `EligibilityRule` | `rule_id` | `min_risk_score`, `max_cost_margin_pct`, `active_only` | Applied during offer eligibility evaluation |
| `CampaignContact` | `contact_id` | `customer_id`, `offer_id`, `group`, `contact_date`, `eligibility_status`, rule/decision traceability fields | References Customer and Offer; records experiment assignment/contact |
| `ChurnOutcome` | `churn_id` | `customer_id`, `prediction_date`, `horizon_end`, `churned`, `churn_type`, `churn_date` | Customer-level prediction-period outcome |
| `RetentionOutcome` | `retention_id` | `contact_id`, `customer_id`, `retained`, `offer_responded`, `realized_offer_cost`, `outcome_date` | References campaign contact and customer |

## Analytical and evaluation artifacts

| Artifact | Purpose | Feature input? |
|---|---|---|
| `features.csv` / `features.json` | Customer-level pre-prediction risk and behavior snapshot | Yes; this is the analytical feature export |
| `ground_truth.csv` / `ground_truth.json` | Labels the four deliberately injected data-quality anomalies | No |
| `summary.json` | Run parameters, entity counts, and summary metrics | No |
| `validation.json` | Validation result and detected issues | No |
| `experiment_report.json` | Treatment/control outcome metrics and cost summary | No |
| `source_manifest.json` | Data provenance, parameters, output file names, and record counts | No |
| `reproducibility.json` | Same-seed CSV hash comparison when enabled | No |

## Key and relationship conventions

- IDs are generated as stable, entity-specific identifiers and are intended to be unique within each entity.
- Child records reference parent identifiers; the schema defines the corresponding foreign keys.
- `SubscriptionHistory`, `UsageSnapshot`, and `BillingEvent` reference `Subscription`.
- `SupportCase` references `Customer`.
- `CampaignContact` references `Customer` and `Offer`.
- `RetentionOutcome` references a campaign contact and customer.
- Dates are stored in ISO format and are checked for temporal consistency.
- Monetary values and usage quantities are expected to be non-negative.
- Experiment groups use `treatment` and `control`.
- `ground_truth` is a separate evaluation artifact and must not be joined into the feature set.

## Validation conventions

Validation checks identifier uniqueness, foreign-key references, date consistency, eligibility traceability, experiment assignment issues, and the four intentional anomalies. The included full-scale validation report contains exactly these issue types:

- `churn_before_prediction`
- `offer_to_ineligible_customer`
- `treatment_control_leakage`
- `multiple_offer_attribution`

The validation report therefore has `passed: false` by design when the four injected anomalies are present. This is not a claim that the baseline generated data contains unintentional errors.
