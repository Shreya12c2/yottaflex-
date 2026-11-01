# YottaFlex Customer Churn and Retention Experiment Pipeline

## 1. Project overview

This project builds a reproducible synthetic customer dataset and a retention-experiment pipeline. It generates customer and subscription histories, derives pre-prediction churn-risk features, evaluates offer eligibility, assigns eligible customers to experiment groups, simulates outcomes, and validates the resulting records.

The project is designed to demonstrate data modelling, data generation, temporal feature engineering, eligibility rules, experiment simulation, data-quality validation, and reproducible exports.

**Important:** All data is synthetic. The churn-risk score is a deterministic heuristic, not a trained machine-learning model. Retention outcomes and experiment metrics are simulated and do not establish real-world causal effectiveness.

## 2. Main capabilities

- Generate a parameterized synthetic dataset with a configurable customer count, history length, and random seed.
- Create related customer, subscription, subscription-history, usage, billing, support, offer, eligibility, campaign, churn, and retention records.
- Build customer-level features using records dated strictly before the prediction date.
- Apply explainable offer eligibility rules, including risk, subscription status, cooldown, and offer-cost constraints.
- Simulate treatment/control assignment and post-prediction outcomes.
- Inject and label four intentional data-quality anomalies.
- Validate identifiers, relationships, dates, eligibility, and experiment consistency.
- Export CSV, JSON, SQLite, and standalone SQL files, together with run and validation reports.

## 3. Requirements

- Python 3.10 or later.
- No third-party Python packages are required.

## 4. Setup and execution

### Windows Command Prompt

From the project root:

```cmd
py -m venv venv
venv\Scripts\activate
python -m churn_retention.cli run --customers 500 --months 18 --seed 20261022
python -m unittest discover -s tests -v
```

### Full-scale generation

```cmd
python -m churn_retention.cli run --customers 20000 --months 18 --seed 20261022
```

### Verify reproducibility

```cmd
python -m churn_retention.cli run --customers 20000 --months 18 --seed 20261022 --verify-reproducibility
```

The reproducibility option performs a second generation using the same parameters and compares generated CSV hashes.

### Validate existing generated data

```cmd
python -m churn_retention.cli validate --data-dir data/generated
```

### macOS/Linux

Create and activate a virtual environment with:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Then run the same project commands, using `python` in the activated environment.

## 5. Pipeline workflow

1. Generate customer and subscription master records.
2. Generate subscription-history events, usage snapshots, billing events, and support cases.
3. Generate offers and eligibility rules.
4. Build customer-level churn features from pre-prediction history.
5. Calculate an explainable, rule-based churn-risk score.
6. Evaluate offer eligibility using subscription status, risk score, prior campaign contact, and cost-to-margin limits.
7. Assign eligible customers to treatment or control groups.
8. Generate post-prediction churn and retention outcomes using seeded simulation rules.
9. Inject four intentional anomalies and preserve their ground-truth labels.
10. Validate records and relationships.
11. Export datasets, database files, a source manifest, and evaluation reports.

## 6. Data model

The current implementation generates **11 relational entities**:

- `Customer`
- `Subscription`
- `SubscriptionHistory`
- `UsageSnapshot`
- `BillingEvent`
- `SupportCase`
- `Offer`
- `EligibilityRule`
- `CampaignContact`
- `ChurnOutcome`
- `RetentionOutcome`

The generator currently creates one subscription per customer, while the relational schema supports multiple subscriptions per customer.

`SubscriptionHistory` records subscription lifecycle and plan-related changes with an effective date. `CampaignContact` records the customer, offer, experiment group, and eligibility traceability. `RetentionOutcome` records the simulated outcome associated with a campaign contact.

The feature snapshot is exported as a separate analytical dataset; it is not one of the 11 relational entities. The anomaly ground-truth file is also separate and must not be used as a model feature source.

See [docs/data_dictionary.md](docs/data_dictionary.md) for fields, keys, and relationships.

## 7. Prediction and feature generation

For the default 18-month run:

- Historical period: January 2025 through June 2026.
- Prediction date: `2026-07-01`.
- Prediction horizon end: `2026-09-29`.

The feature snapshot contains customer ID, prediction date, risk score and category, usage decline, failed-payment count, support-case count, monthly contribution margin, and pre-period average usage.

Behavioral features use records dated strictly before the prediction date. Ground-truth anomaly labels and post-prediction outcomes are kept separate from the feature inputs.

The risk score is a deterministic, explainable heuristic. It should not be interpreted as a calibrated probability of churn.

## 8. Eligibility and experiment assumptions

The default eligibility logic requires an active subscription, a minimum risk score of 35, no prior campaign contact under the configured cooldown rule, and estimated offer cost within 30% of estimated monthly contribution margin.

Monthly contribution margin is approximated as 55% of the subscription monthly fee. Eligible customers are assigned to treatment or control using a seeded random process. Treatment contacts receive offers; the experiment outcomes are simulated from documented rules and a seeded random draw.

The treatment/control comparison is therefore a synthetic demonstration, not evidence of actual campaign effectiveness.

See [docs/assumptions.md](docs/assumptions.md) for the business rules and modelling assumptions.

## 9. Intentional anomalies

Four anomalies are deliberately injected and retained for validation:

1. `churn_before_prediction` — a churn date precedes the prediction date.
2. `offer_to_ineligible_customer` — an offer contact violates the minimum risk eligibility threshold.
3. `treatment_control_leakage` — a customer appears in both experiment groups.
4. `multiple_offer_attribution` — a retained customer has multiple retention attributions.

The validation report is expected to show these four issues. Consequently, `passed` is `false` when these deliberate anomalies are present; this is intentional and should not be described as a clean validation pass. The separate `data/ground_truth/` directory stores the anomaly labels and is not a feature source.

## 10. Generated outputs

### `data/generated/`

Entity-level CSV and JSON files, plus `features.csv` and `features.json`.

### `data/ground_truth/`

- `ground_truth.csv`
- `ground_truth.json`

These files label the deliberately injected anomalies.

### `outputs/`

- `churn_retention.db` — SQLite database.
- `schema.sql` — standalone relational schema.
- `seed_data.sql` — generated SQL insert statements.
- `reports/summary.json` — run parameters, row counts, and metrics.
- `reports/validation.json` — validation issues and details.
- `reports/experiment_report.json` — treatment/control metrics.
- `reports/source_manifest.json` — data provenance and generated-file manifest.
- `reports/reproducibility.json` — hash comparison when reproducibility verification is enabled.

## 11. Recorded full-scale run

The included full-scale reports record a run with 20,000 customers, 18 months, and seed `20261022`.

| Dataset / metric | Recorded result |
|---|---:|
| Customers | 20,000 |
| Subscriptions | 20,000 |
| Subscription-history events | 22,270 |
| Usage snapshots | 360,000 |
| Billing events | 394,765 |
| Support cases | 20,555 |
| Campaign contacts | 4,780 |
| Churn outcomes | 20,000 |
| Retention outcomes | 2,390 |
| Feature rows | 20,000 |
| Observed churn rate | 9.74% |
| Treatment retention rate | 87.10% |
| Control retention rate | 83.21% |
| Simulated incremental retention lift | 3.89 percentage points |
| Realized offer cost | $8,301 |
| Intentional validation issues | 4 |

The included reproducibility report records identical CSV hashes for the same-seed verification. The validation report records the four expected anomaly types. These values describe the included synthetic run and may change if the parameters, seed, or implementation change.

## 12. Tests and verification

The project includes unit tests for offer eligibility and pipeline behavior. The latest test run reported by the candidate completed with **16 tests passing**.

The project also includes generated SQLite and standalone SQL artifacts. Verification evidence should be taken from the reports and database checks performed for the final repository snapshot; do not assume that a previous run verifies a later change.

## 13. Limitations

- All records and outcomes are synthetic; no external customer data is used.
- The churn-risk score is a heuristic, not a trained or calibrated model.
- Retention outcomes and experiment metrics are simulated.
- The experiment report does not include statistical significance tests or confidence intervals.
- The generator currently creates one subscription per customer, although the schema supports multiple subscriptions.
- The generated metrics are illustrative and should not be interpreted as a real-world forecast or causal estimate.

## 14. AI-use disclosure

A summary of AI assistance and prompt requests is maintained in [prompts/ai_prompt_history.md](prompts/ai_prompt_history.md). The prompt-history document explicitly distinguishes request summaries from a verbatim prompt export. The candidate should review the document, add any omitted AI-tool use, and ensure they can explain and defend all submitted implementation decisions.

## 15. Repository hygiene

Do not commit virtual environments, cache files, credentials, `.env` files, or other secrets. The repository `.gitignore` excludes common local environment and temporary files. Review the staged files before pushing the public repository.
